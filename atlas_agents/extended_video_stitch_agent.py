"""
EXTENDED VIDEO STITCH AGENT - V25.8
====================================
Upgraded from V17 FFmpeg-only concat to LTX-2.3 extend-video API.

STRATEGY (3-tier):
1. LTX extend-video (PREFERRED): Uses fal-ai/ltx-2.3/extend-video to seamlessly
   continue from a base video. The model reads context frames and maintains motion,
   style, and audio continuity. No visible splice point.
2. FFmpeg concat (FALLBACK): If extend-video API fails or is not available,
   fall back to the original segment concat approach.
3. Skip (SMART): If a shot is ≤20s, no extension needed at all.

BEHAVIORAL RULES:
- NOT all shots need extension — most are 3-8s
- Only shots with duration > 20s trigger extension
- Each extension adds up to 20s (can chain: 20s base → extend 20s → extend 20s = 60s)
- Extend-video costs $0.10/s vs render $0.04/s — use only when needed
- Context window: model reads 1-20s of source video as reference
- Blocking-aware: extension prompt includes what happens NEXT in the scene

DO NOT RE-BREAK:
- NEVER extend B-roll beyond its natural duration
- NEVER extend without checking if base video exists first
- NEVER chain more than 3 extensions (60s max practical limit — quality degrades)
- ALWAYS preserve the base video — extensions create NEW files
- FFmpeg concat remains as fallback — NEVER remove it
"""

import json
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# V25.8: LTX EXTEND-VIDEO API
# ============================================================================

LTX_EXTEND_MODEL = "fal-ai/ltx-2.3/extend-video"
LTX_EXTEND_COST_PER_SEC = 0.10
LTX_EXTEND_MAX_DURATION = 20  # max seconds per extension call
LTX_EXTEND_MAX_CHAINS = 3     # quality degrades after 3 extensions (60s total)


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ], capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip()) if result.stdout.strip() else 0
    except Exception:
        return 0


def _upload_to_r2_for_extend(video_path: Path, project: str) -> Optional[str]:
    """
    Upload video to R2 for a permanent URL that the extend API can read.
    Returns R2 public URL or None on failure.

    Law 229: R2 permanent URLs are the ONLY acceptable image/video source.
    """
    try:
        import boto3
        account_id = os.environ.get("ATLAS_R2_ACCOUNT_ID", "")
        access_key = os.environ.get("ATLAS_R2_ACCESS_KEY_ID", "")
        secret_key = os.environ.get("ATLAS_R2_SECRET_KEY", "")
        bucket = os.environ.get("ATLAS_R2_BUCKET", "rumble-fanz")
        public_url = os.environ.get("ATLAS_R2_PUBLIC_URL", "")

        if not all([account_id, access_key, secret_key, public_url]):
            logger.warning("[EXTEND] R2 not configured — cannot upload for extend API")
            return None

        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        r2_key = f"atlas-frames/{project}/extend_source/{video_path.name}"
        s3.upload_file(str(video_path), bucket, r2_key, ExtraArgs={"ContentType": "video/mp4"})
        url = f"{public_url}/{r2_key}"
        logger.info(f"[EXTEND] Uploaded {video_path.name} to R2: {url}")
        return url

    except ImportError:
        logger.warning("[EXTEND] boto3 not available — R2 upload skipped")
        return None
    except Exception as e:
        logger.warning(f"[EXTEND] R2 upload failed: {e}")
        return None


def _fal_upload_video(video_path: Path) -> Optional[str]:
    """Upload video via fal_client for a temporary URL (fallback if R2 fails)."""
    try:
        import fal_client
        url = fal_client.upload_file(str(video_path))
        logger.info(f"[EXTEND] Uploaded {video_path.name} via fal_client: {url}")
        return url
    except Exception as e:
        logger.warning(f"[EXTEND] fal_client upload failed: {e}")
        return None


def extend_video_ltx(
    base_video_path: Path,
    extend_duration: float,
    prompt: str,
    project: str,
    output_path: Path,
    context_seconds: float = 5.0,
) -> Tuple[bool, str]:
    """
    Extend a video using LTX-2.3 extend-video API.

    Args:
        base_video_path: Path to the base video to extend
        extend_duration: How many seconds to add (1-20)
        prompt: What happens in the extended portion
        project: Project name (for R2 upload path)
        output_path: Where to save the extended video
        context_seconds: How many seconds of source to use as reference (1-20)

    Returns:
        (success: bool, message: str)
    """
    try:
        import fal_client
    except ImportError:
        return False, "fal_client not installed"

    if not base_video_path.exists():
        return False, f"Base video not found: {base_video_path}"

    # Clamp duration to API limits
    extend_duration = max(1.0, min(extend_duration, LTX_EXTEND_MAX_DURATION))
    context_seconds = max(1.0, min(context_seconds, 20.0))

    # Upload base video — R2 first (permanent), fal_client fallback (temporary)
    video_url = _upload_to_r2_for_extend(base_video_path, project)
    if not video_url:
        video_url = _fal_upload_video(base_video_path)
    if not video_url:
        return False, "Failed to upload base video to any storage"

    # Build API arguments
    arguments = {
        "video_url": video_url,
        "duration": extend_duration,
        "mode": "end",
        "context": context_seconds,
    }
    if prompt and prompt.strip():
        arguments["prompt"] = prompt.strip()

    logger.info(f"[EXTEND] Calling {LTX_EXTEND_MODEL}: +{extend_duration}s, context={context_seconds}s")

    try:
        result = fal_client.run(LTX_EXTEND_MODEL, arguments=arguments)
    except Exception as e:
        return False, f"LTX extend API call failed: {e}"

    # Extract video URL from result
    video_data = result.get("video", {}) if isinstance(result, dict) else {}
    extended_url = video_data.get("url", "")
    if not extended_url:
        return False, f"No video URL in extend response: {result}"

    # Download the extended video
    try:
        import urllib.request
        urllib.request.urlretrieve(extended_url, str(output_path))
        actual_dur = get_video_duration(output_path)
        cost = extend_duration * LTX_EXTEND_COST_PER_SEC
        logger.info(f"[EXTEND] Success: {output_path.name} = {actual_dur:.1f}s (cost: ${cost:.2f})")
        return True, f"Extended to {actual_dur:.1f}s (cost: ${cost:.2f})"
    except Exception as e:
        return False, f"Failed to download extended video: {e}"


def stitch_videos(segment_paths: List[Path], output_path: Path) -> bool:
    """Stitch multiple video segments into one using ffmpeg concat. (V17 FALLBACK)"""
    if not segment_paths:
        return False

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for seg in segment_paths:
            f.write(f"file '{seg}'\n")
        concat_file = f.name

    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            str(output_path)
        ], capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            return True
        else:
            print(f"FFmpeg error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Stitch failed: {e}")
        return False
    finally:
        Path(concat_file).unlink(missing_ok=True)


# ============================================================================
# SHOT EXTENSION STRATEGY DECISION
# ============================================================================

def should_extend(shot: dict, max_single_duration: float = 20) -> bool:
    """
    Decide if a shot needs extension beyond its base render.

    Returns True ONLY when:
    - duration > max_single_duration (model-dependent: LTX=20s, Kling3=15s, KlingPro=10s)
    - NOT a B-roll shot (B-roll stays short)
    - NOT marked _no_extend
    """
    duration = shot.get("duration", shot.get("duration_seconds", 0))
    if duration <= max_single_duration:
        return False

    # V26 DOCTRINE: Coverage suffixes are editorial, not runtime — check flags only
    if shot.get("_broll", False) or shot.get("is_broll", False):
        return False

    # Respect explicit no-extend flag
    if shot.get("_no_extend", False):
        return False

    return True


def compute_extension_plan(shot: dict) -> List[dict]:
    """
    Compute a chain of extensions needed for a shot.

    Example: 55s shot → base 20s + extend 20s + extend 15s = 3 steps

    Returns list of extension steps:
    [
        {"step": 0, "type": "base_render", "duration": 20},
        {"step": 1, "type": "extend", "duration": 20, "context": 5},
        {"step": 2, "type": "extend", "duration": 15, "context": 5},
    ]
    """
    total = shot.get("duration", shot.get("duration_seconds", 20))
    if total <= 20:
        return [{"step": 0, "type": "base_render", "duration": total}]

    plan = []
    remaining = total

    # Step 0: base render (max 20s)
    base_dur = min(remaining, 20)
    plan.append({"step": 0, "type": "base_render", "duration": base_dur})
    remaining -= base_dur

    # Extensions (max 20s each, max 3 chains)
    step = 1
    while remaining > 0 and step <= LTX_EXTEND_MAX_CHAINS:
        ext_dur = min(remaining, LTX_EXTEND_MAX_DURATION)
        # Use more context for longer extensions (better continuity)
        context = min(5.0, base_dur)
        plan.append({
            "step": step,
            "type": "extend",
            "duration": ext_dur,
            "context": context,
        })
        remaining -= ext_dur
        step += 1

    if remaining > 0:
        logger.warning(
            f"[EXTEND] Shot {shot.get('shot_id', '?')}: {remaining}s remaining "
            f"after {LTX_EXTEND_MAX_CHAINS} extensions — capping at "
            f"{total - remaining}s total"
        )

    return plan


def estimate_extension_cost(shot: dict) -> float:
    """Estimate the cost of extending a shot."""
    plan = compute_extension_plan(shot)
    cost = 0.0
    for step in plan:
        if step["type"] == "extend":
            cost += step["duration"] * LTX_EXTEND_COST_PER_SEC
    return cost


# ============================================================================
# MAIN RUNNER — V25.8 SMART EXTENSION
# ============================================================================

def run_extended_video_stitch(
    project: str,
    repo_root: Path = None,
    use_extend_api: bool = True,
    video_model: str = "ltx",
) -> dict:
    """
    Process all extended shots (>model_max) in a project.

    V25.8 STRATEGY (MODEL-AWARE):
    - LTX (max 20s): Use extend-video API for seamless continuation, FFmpeg fallback
    - Kling 3.0 (max 15s): No extend API — FFmpeg segment concat only
    - Kling Pro (max 10s): No extend API — FFmpeg segment concat only

    1. For each shot exceeding model's max duration, check if base video exists
    2. If LTX + use_extend_api=True: call LTX extend-video for seamless continuation
    3. If Kling or extend fails: fall back to FFmpeg segment concat
    4. If no segments and no base video: mark as missing

    Args:
        project: Project name
        repo_root: Repository root path
        use_extend_api: True = use LTX extend when available, False = FFmpeg only
        video_model: "ltx" (max 20s, has extend), "kling" (max 15s, no extend),
                     "kling_pro" (max 10s, no extend)

    Returns:
        {
            "agent": "extended_video_stitcher",
            "version": "V25.8",
            "state": "COMPLETE",
            "facts": {
                "extended_ltx": N,       # Used LTX extend-video API
                "stitched_ffmpeg": N,    # Fell back to FFmpeg concat
                "already_done": N,       # Already at target duration
                "missing_base": N,       # No base video to extend from
                "skipped": N,            # ≤20s, no extension needed
                "total_extend_cost": float,
            }
        }
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent

    repo_root = Path(repo_root)
    project_path = repo_root / "pipeline_outputs" / project

    shot_plan_path = project_path / "shot_plan.json"
    videos_dir = project_path / "videos"

    # Model-aware duration thresholds
    MODEL_MAX_DURATIONS = {"ltx": 20, "kling": 15, "kling_pro": 10}
    MODEL_HAS_EXTEND = {"ltx": True, "kling": False, "kling_pro": False}
    max_dur = MODEL_MAX_DURATIONS.get(video_model, 20)
    can_extend = MODEL_HAS_EXTEND.get(video_model, False) and use_extend_api

    if not shot_plan_path.exists():
        return {"agent": "extended_video_stitcher", "version": "V25.8",
                "state": "FAILED", "error": "No shot_plan.json"}

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    stats = {
        "extended_ltx": 0,
        "stitched_ffmpeg": 0,
        "already_done": 0,
        "missing_base": 0,
        "skipped": 0,
        "total_extend_cost": 0.0,
        "details": [],
    }

    for shot in shot_plan.get("shots", []):
        shot_id = shot.get("shot_id", "")
        duration = shot.get("duration", shot.get("duration_seconds", 20))

        # Skip shots that don't need extension (model-aware threshold)
        if not should_extend(shot, max_single_duration=max_dur):
            stats["skipped"] += 1
            continue

        final_video = videos_dir / f"{shot_id}.mp4"

        # Already at target duration?
        if final_video.exists():
            actual_dur = get_video_duration(final_video)
            if actual_dur >= duration - 2:
                stats["already_done"] += 1
                shot["video_path"] = str(final_video)
                continue

        # Compute extension plan
        plan = compute_extension_plan(shot)
        logger.info(f"[EXTEND] {shot_id}: {duration}s total, {len(plan)} steps")

        # === TIER 1: LTX Extend-Video API (only if model supports it) ===
        if can_extend and len(plan) > 1:
            base_video = videos_dir / f"{shot_id}_seg0.mp4"
            # Also check for base video without _seg0 suffix (might be ≤20s first render)
            if not base_video.exists():
                base_video = final_video  # might exist as a short base render

            if base_video.exists():
                current_video = base_video
                extend_success = True

                for step in plan[1:]:  # skip step 0 (base_render)
                    ext_dur = step["duration"]
                    ctx = step.get("context", 5.0)

                    # Build continuation prompt from shot data
                    ext_prompt = _build_extension_prompt(shot, step["step"])

                    ext_output = videos_dir / f"{shot_id}_ext{step['step']}.mp4"

                    ok, msg = extend_video_ltx(
                        base_video_path=current_video,
                        extend_duration=ext_dur,
                        prompt=ext_prompt,
                        project=project,
                        output_path=ext_output,
                        context_seconds=ctx,
                    )

                    if ok:
                        current_video = ext_output
                        stats["total_extend_cost"] += ext_dur * LTX_EXTEND_COST_PER_SEC
                        logger.info(f"[EXTEND] {shot_id} step {step['step']}: {msg}")
                    else:
                        logger.warning(f"[EXTEND] {shot_id} step {step['step']} failed: {msg}")
                        extend_success = False
                        break

                if extend_success and current_video != final_video:
                    # The final extended video IS the output
                    import shutil
                    shutil.copy2(str(current_video), str(final_video))
                    actual_dur = get_video_duration(final_video)
                    shot["video_path"] = str(final_video)
                    shot["_extended_via"] = "ltx_extend_api"
                    shot["_extend_steps"] = len(plan) - 1
                    stats["extended_ltx"] += 1
                    stats["details"].append({
                        "shot_id": shot_id,
                        "method": "ltx_extend",
                        "target": duration,
                        "actual": actual_dur,
                        "steps": len(plan) - 1,
                    })
                    logger.info(f"[EXTEND] {shot_id}: LTX extend complete — {actual_dur:.1f}s")
                    continue
                # If extend failed, fall through to FFmpeg

        # === TIER 2: FFmpeg Segment Concat (FALLBACK) ===
        segments = shot.get("segments", [])
        num_segments = len(segments) if segments else max(1, (duration + 19) // 20)
        segment_paths = []

        for i in range(num_segments):
            seg_path = videos_dir / f"{shot_id}_seg{i}.mp4"
            if seg_path.exists():
                segment_paths.append(seg_path)

        if len(segment_paths) >= 2:
            logger.info(f"[STITCH] {shot_id}: FFmpeg fallback — {len(segment_paths)} segments")
            if stitch_videos(segment_paths, final_video):
                actual_dur = get_video_duration(final_video)
                shot["video_path"] = str(final_video)
                shot["_extended_via"] = "ffmpeg_concat"
                stats["stitched_ffmpeg"] += 1
                stats["details"].append({
                    "shot_id": shot_id,
                    "method": "ffmpeg_concat",
                    "target": duration,
                    "actual": actual_dur,
                    "segments": len(segment_paths),
                })
                logger.info(f"[STITCH] {shot_id}: FFmpeg concat — {actual_dur:.1f}s")
                continue

        # === TIER 3: Nothing worked ===
        stats["missing_base"] += 1
        logger.warning(f"[EXTEND] {shot_id}: No base video or segments found")

    # Save updated shot_plan
    with open(shot_plan_path, "w") as f:
        json.dump(shot_plan, f, indent=2)

    state = "COMPLETE" if stats["missing_base"] == 0 else "PARTIAL"

    return {
        "agent": "extended_video_stitcher",
        "version": "V25.8",
        "state": state,
        "facts": {k: v for k, v in stats.items() if k != "details"},
        "details": stats["details"],
    }


def _build_extension_prompt(shot: dict, step_number: int) -> str:
    """
    Build a continuation prompt for the extension.
    Uses shot's action description and blocking to guide what happens next.
    """
    parts = []

    # Extract action/motion direction from the shot
    nano = shot.get("nano_prompt") or shot.get("nano_prompt_final") or ""
    ltx = shot.get("ltx_motion_prompt") or ""

    # Pull character action if present
    import re
    action_match = re.search(r'[Cc]haracter (?:performs|action)[:\s]+([^.]+)', nano)
    if action_match:
        parts.append(action_match.group(1).strip())

    # Pull motion direction from LTX
    motion_match = re.search(r'character (?:performs|speaks|reacts)[:\s]+([^.]+)', ltx)
    if motion_match and motion_match.group(1).strip() not in " ".join(parts):
        parts.append(motion_match.group(1).strip())

    # If this is a later extension, add continuity instruction
    if step_number > 1:
        parts.append("continuous motion, maintaining character position and blocking")

    # Dialogue continuation
    dialogue = (shot.get("dialogue_text") or shot.get("dialogue") or "").strip()
    if dialogue and step_number == 1:
        # First extension often covers the dialogue delivery
        speaker = (shot.get("characters") or ["character"])[0] if shot.get("characters") else "character"
        parts.append(f"{speaker} continues speaking with natural gesture")

    if parts:
        return ". ".join(parts) + "."
    return "natural motion continues, maintaining scene composition and character positions"


# ============================================================================
# STANDALONE
# ============================================================================

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "kord_v17"
    use_api = "--ffmpeg-only" not in sys.argv
    result = run_extended_video_stitch(project, use_extend_api=use_api)
    print(json.dumps(result, indent=2))
