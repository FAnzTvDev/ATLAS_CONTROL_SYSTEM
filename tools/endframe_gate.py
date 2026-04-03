"""
ATLAS V26.1 — END-FRAME REUSE GATE
=====================================
Post-motion validation of video end frames for chain inheritance.

After LTX/Kling generates a video, we extract the last frame and ask:
"Can the next shot start from this frame?"

Reasons to BLOCK reuse:
  - Character has drifted (face morphed, wrong person appeared)
  - Environment has changed (room shifted, lighting dramatically different)
  - Frame is blurry/corrupted
  - Character is mid-motion (walking out of frame, turning away)
  - End frame shows a different scene context

Reasons to APPROVE:
  - Character identity preserved
  - Environment consistent with scene
  - Character in stable pose (standing, sitting, looking)
  - Frame is sharp and well-composed

DOCTRINE LAW 277: End-frame validation is NON-BLOCKING. If validation fails,
the frame is used with a degraded_safe flag rather than blocking the pipeline.
DOCTRINE LAW 278: Motion classification (static vs dynamic) determines reuse
eligibility. Dynamic motion (walking, turning, exiting) blocks end-frame reuse.
DOCTRINE LAW 279: End-frame blur detection uses Laplacian variance. Variance
< 100 is blurry; > 200 is sharp. 100-200 is acceptable for secondary shots.
"""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
import subprocess
import json


@dataclass
class EndFrameAnalysis:
    """Structured analysis of a video end frame for reuse eligibility."""

    frame_path: str  # Extracted end frame JPEG path
    identity_preserved: bool  # Character faces still match refs?
    environment_stable: bool  # Room/location consistent?
    character_stable: bool  # Not mid-motion (walking, turning)?
    sharpness_ok: bool  # Frame is not blurry?
    reuse_verdict: str  # "reuse" | "block" | "degrade_safe"
    block_reasons: List[str]  # Why reuse is blocked
    confidence: float  # 0.0-1.0: how confident in this analysis
    motion_classification: str  # "static" | "subtle" | "dynamic"
    frame_hash: str  # SHA256 of end frame
    analysis_timestamp: str  # ISO 8601


# Sharpness thresholds (Laplacian variance)
SHARPNESS_THRESHOLDS = {
    "blurry": 100,  # < 100: definitely blurry
    "acceptable": 200,  # 100-200: acceptable
    "sharp": 200,  # > 200: sharp
}

# Motion keywords that indicate dynamic motion (blocks reuse)
DYNAMIC_MOTION_KEYWORDS = [
    "walking",
    "running",
    "exiting",
    "entering",
    "turning",
    "spinning",
    "falling",
    "jumping",
    "gesturing wildly",
    "reaching",
    "stroking",
    "pacing",
    "stumbling",
    "rushing",
    "crawling",
]

# Motion keywords indicating static/subtle (allows reuse)
STATIC_MOTION_KEYWORDS = [
    "standing",
    "sitting",
    "kneeling",
    "lying",
    "looking",
    "staring",
    "breathing",
    "subtle",
    "micro",
    "listening",
    "watching",
    "contemplating",
]


def analyze_end_frame(
    video_path: str,
    shot_state: dict,
    cast_map: dict,
    vision_service=None,
) -> EndFrameAnalysis:
    """
    Analyze end frame of a generated video for chain reuse eligibility.

    Args:
        video_path: Path to generated video (MP4)
        shot_state: Shot dict from shot_plan.json
        cast_map: Character → AI actor map
        vision_service: Vision service instance (if None, use heuristic)

    Returns:
        EndFrameAnalysis with reuse verdict and evidence
    """
    from datetime import datetime
    import tempfile
    import os

    timestamp = datetime.utcnow().isoformat() + "Z"

    # Extract end frame from video
    with tempfile.TemporaryDirectory() as tmpdir:
        endframe_path = os.path.join(tmpdir, "endframe.jpg")

        try:
            endframe_path = extract_end_frame(video_path, endframe_path)
            if endframe_path is None:
                return EndFrameAnalysis(
                    frame_path="",
                    identity_preserved=False,
                    environment_stable=False,
                    character_stable=False,
                    sharpness_ok=False,
                    reuse_verdict="block",
                    block_reasons=["Failed to extract end frame from video"],
                    confidence=0.0,
                    motion_classification="unknown",
                    frame_hash="unknown",
                    analysis_timestamp=timestamp,
                )
        except Exception as e:
            return EndFrameAnalysis(
                frame_path="",
                identity_preserved=False,
                environment_stable=False,
                character_stable=False,
                sharpness_ok=False,
                reuse_verdict="block",
                block_reasons=[f"End frame extraction failed: {str(e)}"],
                confidence=0.0,
                motion_classification="unknown",
                frame_hash="unknown",
                analysis_timestamp=timestamp,
            )

        # If no vision service, use heuristic
        if vision_service is None:
            return heuristic_end_frame_check(shot_state, endframe_path, timestamp)

        try:
            frame_hash = _sha256_file(endframe_path)
        except Exception:
            frame_hash = "unknown"

        # Vision-based analysis
        try:
            # Identity preservation
            identity_preserved = _verify_identity_at_endframe(
                endframe_path, shot_state, cast_map, vision_service
            )

            # Environment stability
            environment_stable = _verify_environment_at_endframe(
                endframe_path, shot_state, vision_service
            )

            # Character motion classification
            motion_classification = _classify_motion_at_endframe(
                endframe_path, shot_state, vision_service
            )
            character_stable = motion_classification in ["static", "subtle"]

            # Sharpness check
            sharpness_ok = _check_sharpness(endframe_path)

        except Exception as e:
            print(f"[endframe_gate] Vision analysis failed: {e}. Using heuristic.")
            return heuristic_end_frame_check(shot_state, endframe_path, timestamp)

        # Determine verdict
        block_reasons = []
        if not identity_preserved:
            block_reasons.append("Character identity drifted or changed")
        if not environment_stable:
            block_reasons.append("Environment/location inconsistent with scene")
        if not character_stable:
            block_reasons.append(
                f"Character in dynamic motion ({motion_classification}) — cannot anchor next shot"
            )
        if not sharpness_ok:
            block_reasons.append("End frame is blurry or corrupted")

        if block_reasons:
            # Determine if degraded_safe or full block
            # degraded_safe: one minor issue (e.g., slight blur) but otherwise OK
            # block: multiple issues or critical failure
            if len(block_reasons) == 1 and "blurry" in block_reasons[0]:
                reuse_verdict = "degrade_safe"
                confidence = 0.3
            else:
                reuse_verdict = "block"
                confidence = 0.2
        else:
            reuse_verdict = "reuse"
            confidence = 0.85

        return EndFrameAnalysis(
            frame_path=endframe_path,
            identity_preserved=identity_preserved,
            environment_stable=environment_stable,
            character_stable=character_stable,
            sharpness_ok=sharpness_ok,
            reuse_verdict=reuse_verdict,
            block_reasons=block_reasons,
            confidence=confidence,
            motion_classification=motion_classification,
            frame_hash=frame_hash,
            analysis_timestamp=timestamp,
        )


def extract_end_frame(video_path: str, output_path: str) -> Optional[str]:
    """
    Extract last frame from video using ffmpeg.

    Uses: ffprobe to get duration, then ffmpeg to seek to -0.1 seconds
    and extract that frame as JPEG.

    Args:
        video_path: Path to MP4 video
        output_path: Where to save extracted frame JPEG

    Returns:
        output_path on success, None on failure
    """
    import subprocess
    import json

    try:
        # Get video duration
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video_path,
        ]
        result = subprocess.run(
            probe_cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"[endframe_gate] ffprobe failed: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))

        if duration <= 0:
            print(f"[endframe_gate] Invalid duration: {duration}")
            return None

        # Seek to -0.1 seconds before end
        seek_time = max(0, duration - 0.1)

        # Extract frame
        extract_cmd = [
            "ffmpeg",
            "-ss",
            str(seek_time),
            "-i",
            video_path,
            "-vframes",
            "1",
            "-f",
            "image2",
            "-q:v",
            "2",  # Quality: 2 = very high
            output_path,
        ]

        result = subprocess.run(
            extract_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"[endframe_gate] ffmpeg extraction failed: {result.stderr}")
            return None

        if Path(output_path).exists():
            return output_path
        else:
            print(f"[endframe_gate] Output file not created: {output_path}")
            return None

    except subprocess.TimeoutExpired:
        print(f"[endframe_gate] ffmpeg timeout for {video_path}")
        return None
    except Exception as e:
        print(f"[endframe_gate] Extraction exception: {e}")
        return None


def heuristic_end_frame_check(
    shot_state: dict, endframe_path: Optional[str] = None, timestamp: str = None
) -> EndFrameAnalysis:
    """
    Heuristic end-frame validation when vision is unavailable.

    Rules:
    - Static/subtle motion → reuse OK
    - Dynamic motion → block
    - Dialogue shots → block (can't assume stable pose)
    - Establish/wide shots → reuse OK (less dependent on exact pose)
    """
    from datetime import datetime

    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"

    # Motion classification from prompt
    ltx_motion_prompt = shot_state.get("ltx_motion_prompt", "")
    motion_classification = _classify_motion_from_text(ltx_motion_prompt)

    # Check for dialogue
    has_dialogue = bool(shot_state.get("dialogue_text"))

    block_reasons = []

    # Rule 1: Dynamic motion blocks reuse
    if motion_classification == "dynamic":
        block_reasons.append("Dynamic motion at end frame (heuristic: walking/turning/exiting)")
        character_stable = False
    else:
        character_stable = True

    # Rule 2: Dialogue shots are risky (we don't know final pose)
    if has_dialogue:
        block_reasons.append(
            "Dialogue shot — cannot assume stable pose at end (heuristic: dialogue motion unpredictable)"
        )

    # Environment stability: assume OK for same-scene shots
    environment_stable = True
    location = shot_state.get("location", "")
    if not location:
        block_reasons.append("No location specified — cannot verify environment")
        environment_stable = False

    # Identity: assume OK (no way to check without vision)
    identity_preserved = True

    # Sharpness: can't check without image, assume OK
    sharpness_ok = True

    # Determine verdict
    if block_reasons:
        if len(block_reasons) == 1 and "dialogue" in block_reasons[0]:
            reuse_verdict = "degrade_safe"
            confidence = 0.4
        else:
            reuse_verdict = "block"
            confidence = 0.3
    else:
        reuse_verdict = "reuse"
        confidence = 0.5  # Heuristic: lower confidence than vision-based

    return EndFrameAnalysis(
        frame_path=endframe_path or "",
        identity_preserved=identity_preserved,
        environment_stable=environment_stable,
        character_stable=character_stable,
        sharpness_ok=sharpness_ok,
        reuse_verdict=reuse_verdict,
        block_reasons=block_reasons,
        confidence=confidence,
        motion_classification=motion_classification,
        frame_hash="unknown",
        analysis_timestamp=timestamp,
    )


def _verify_identity_at_endframe(
    frame_path: str, shot_state: dict, cast_map: dict, vision_service
) -> bool:
    """Check if character faces at end frame match refs."""
    characters = shot_state.get("characters", [])

    # No characters → no identity check needed
    if not characters:
        return True

    try:
        # Ask vision service: do faces in frame match character refs?
        result = vision_service.verify_end_frame_identity(
            frame_path, characters, cast_map
        )
        if result is not None:
            return result
    except Exception:
        pass

    # Fallback: assume identity preserved (we can't verify)
    return True


def _verify_environment_at_endframe(
    frame_path: str, shot_state: dict, vision_service
) -> bool:
    """Check if environment at end frame matches scene location."""
    location = shot_state.get("location", "")
    if not location:
        return True

    try:
        caption = vision_service.get_caption(frame_path)
        location_words = location.lower().split()
        caption_lower = caption.lower()

        # Check if location keywords appear in caption
        matches = sum(1 for word in location_words if word in caption_lower)
        if len(location_words) > 0:
            keyword_score = matches / len(location_words)
            return keyword_score >= 0.5  # At least 50% of location keywords match
    except Exception:
        pass

    # Fallback: assume environment is stable
    return True


def _classify_motion_at_endframe(
    frame_path: str, shot_state: dict, vision_service
) -> str:
    """
    Classify motion at end frame: static, subtle, or dynamic.

    Returns: "static" | "subtle" | "dynamic"
    """
    ltx_motion_prompt = shot_state.get("ltx_motion_prompt", "")

    try:
        # First try vision service
        caption = vision_service.get_caption(frame_path)
        return _classify_motion_from_text(caption)
    except Exception:
        pass

    # Fallback: use LTX motion prompt
    return _classify_motion_from_text(ltx_motion_prompt)


def _classify_motion_from_text(text: str) -> str:
    """
    Classify motion as static, subtle, or dynamic based on text keywords.

    Returns: "static" | "subtle" | "dynamic"
    """
    text_lower = text.lower()

    # Check for dynamic motion keywords
    for keyword in DYNAMIC_MOTION_KEYWORDS:
        if keyword in text_lower:
            return "dynamic"

    # Check for static motion keywords
    for keyword in STATIC_MOTION_KEYWORDS:
        if keyword in text_lower:
            # Further check: is it subtle or just static?
            if "subtle" in text_lower or "micro" in text_lower:
                return "subtle"
            else:
                return "static"

    # Default: assume subtle motion
    return "subtle"


def _check_sharpness(frame_path: str) -> bool:
    """
    Check frame sharpness using Laplacian variance.

    Variance < 100: blurry
    Variance 100-200: acceptable
    Variance > 200: sharp

    Returns: True if acceptable or sharp, False if blurry
    """
    try:
        from PIL import Image
        import numpy as np
        import cv2

        # Load image
        img = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False

        # Compute Laplacian variance
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        variance = laplacian.var()

        # Threshold: < 100 is blurry
        return variance >= SHARPNESS_THRESHOLDS["blurry"]

    except Exception as e:
        print(f"[endframe_gate] Sharpness check failed: {e}")
        # Assume sharp if we can't check
        return True


def _sha256_file(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    import hashlib

    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
