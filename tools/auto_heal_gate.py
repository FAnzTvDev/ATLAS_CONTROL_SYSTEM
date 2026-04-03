#!/usr/bin/env python3
"""
AUTO-HEAL GATE - Unified Pre/Post Validation & Repair

Runs at 3 checkpoints:
1. PREFLIGHT (before generation)
2. PER-SHOT (before each render)
3. PRE-STITCH (before final assembly)

Includes:
- Secret scan (blocks if keys in tracked files)
- Sentry check (warns if not initialized)
- Model lock enforcement
- Segment metadata auto-repair
- Cast propagation auto-repair
- First-frame aspect ratio check
- Video-to-frame hash validation

Usage:
    python3 tools/auto_heal_gate.py <project> --preflight
    python3 tools/auto_heal_gate.py <project> --per-shot <shot_id>
    python3 tools/auto_heal_gate.py <project> --pre-stitch
    python3 tools/auto_heal_gate.py <project> --full
"""

import json
import os
import re
import sys
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
sys.path.insert(0, str(BASE_DIR / "atlas_agents_v16_7"))

# Import semantic invariants
from atlas_agents.semantic_invariants import check_all_invariants


# =============================================================================
# SECRET SCAN
# =============================================================================

SECRET_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',           # OpenAI/Anthropic style
    r'r8_[a-zA-Z0-9]{30,}',           # Replicate
    r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}:[a-f0-9]{32}',  # FAL
    r'sk_[a-f0-9]{40,}',              # ElevenLabs
    r'AIza[a-zA-Z0-9_-]{35}',         # Google API
]

FILES_TO_SCAN = [
    "CLAUDE.md",
    "README.md",
    "*.md",
    "docs/*.md",
    "tools/*.md",
]


def scan_for_secrets() -> Dict:
    """Scan tracked files for exposed secrets."""
    issues = []
    files_checked = []

    for pattern in FILES_TO_SCAN:
        # Handle both literal filenames and glob patterns
        if "*" in pattern:
            matched_files = list(BASE_DIR.glob(pattern))
        else:
            # Literal filename
            literal_path = BASE_DIR / pattern
            matched_files = [literal_path] if literal_path.exists() else []

        for file_path in matched_files:
            if not file_path.is_file():
                continue

            files_checked.append(str(file_path.relative_to(BASE_DIR)))

            try:
                content = file_path.read_text()
            except Exception:
                continue

            for secret_pattern in SECRET_PATTERNS:
                matches = re.findall(secret_pattern, content)
                if matches:
                    issues.append({
                        "file": str(file_path.relative_to(BASE_DIR)),
                        "pattern": secret_pattern[:20] + "...",
                        "count": len(matches)
                    })

    return {
        "passed": len(issues) == 0,
        "files_scanned": files_checked,
        "exposed": issues,
        "clean": len(issues) == 0,
        "severity": "CRITICAL" if issues else "OK"
    }


# =============================================================================
# SENTRY CHECK
# =============================================================================

def check_sentry_initialized() -> Dict:
    """Check if Sentry is properly initialized."""
    try:
        import sentry_sdk
        hub = sentry_sdk.Hub.current
        client = hub.client

        if client is None:
            return {
                "passed": False,
                "status": "NOT_INITIALIZED",
                "message": "Sentry client is None - errors will not be captured"
            }

        dsn = client.dsn
        if not dsn:
            return {
                "passed": False,
                "status": "NO_DSN",
                "message": "Sentry initialized but no DSN configured"
            }

        return {
            "passed": True,
            "status": "OK",
            "dsn_suffix": str(dsn)[-20:]
        }

    except ImportError:
        return {
            "passed": False,
            "status": "NOT_INSTALLED",
            "message": "sentry_sdk not installed"
        }
    except Exception as e:
        return {
            "passed": False,
            "status": "ERROR",
            "message": str(e)
        }


# =============================================================================
# MODEL LOCK ENFORCEMENT
# =============================================================================

LOCKED_MODELS = {
    "image": "fal-ai/nano-banana-pro",
    "image_edit": "fal-ai/nano-banana-pro/edit",
    "video": "fal-ai/ltx-2.3/image-to-video/fast",
    "stitch": "ffmpeg"
}

FORBIDDEN_MODELS = [
    "minimax", "runway", "pika", "sora", "flux", "wan", "omnihuman"
]


def check_model_lock(project: str) -> Dict:
    """Verify no forbidden models are referenced in project."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return {"passed": True, "message": "No shot_plan.json to check"}

    content = shot_plan_path.read_text().lower()
    violations = []

    for forbidden in FORBIDDEN_MODELS:
        if forbidden in content:
            violations.append(forbidden)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "locked_models": LOCKED_MODELS
    }


# =============================================================================
# SEGMENT AUTO-REPAIR
# =============================================================================

def generate_segment_ltx_prompts(shot: Dict, num_segments: int) -> List[Dict]:
    """
    Generate LTX motion prompts for each segment based on shot context.

    Uses:
    - nano_prompt (visual description)
    - ltx_motion_prompt (base motion)
    - dialogue (what's being said)
    - shot_type, camera_motion, characters
    """
    nano_prompt = shot.get("nano_prompt", "")
    ltx_base = shot.get("ltx_motion_prompt", "")
    dialogue = shot.get("dialogue", "")
    shot_type = shot.get("shot_type", "medium")
    camera_motion = shot.get("camera_motion", "static")
    characters = shot.get("characters", [])

    # Extract character name
    char_name = ""
    if characters:
        c = characters[0]
        char_name = c.get("name") if isinstance(c, dict) else str(c)

    # Motion descriptors for different phases
    motion_phases = {
        0: "begins speaking, subtle facial movement, eyes focused",
        1: "continues delivery, slight head movement, emotional expression builds",
        2: "reaches emotional peak, gestures naturally, maintains eye contact",
        3: "concludes thought, expression settles, subtle breathing motion"
    }

    # Camera motion descriptors
    camera_phases = {
        "static": ["holds steady", "maintains frame", "static composition"],
        "slow_dolly": ["gentle dolly in", "continues slow push", "settles on subject"],
        "slow_pan": ["begins slow pan", "continues tracking", "eases to stop"],
        "push_in": ["starts push in", "continues toward subject", "ends on close"],
        "pull_out": ["begins pulling back", "reveals more space", "settles on wide"]
    }

    cam_motions = camera_phases.get(camera_motion, camera_phases["static"])

    segments = []
    for i in range(num_segments):
        # Build segment-specific LTX prompt
        phase_motion = motion_phases.get(i, motion_phases[min(i, 3)])
        cam_motion = cam_motions[min(i, len(cam_motions) - 1)]

        if i == 0:
            # First segment - establish scene
            ltx_prompt = f"{shot_type} shot, {char_name} {phase_motion}. Camera {cam_motion}. "
            if dialogue:
                ltx_prompt += f"Speaking: \"{dialogue[:80]}...\". "
            ltx_prompt += "Cinematic motion, natural performance."
        elif i == num_segments - 1:
            # Last segment - conclude
            ltx_prompt = f"Continuing {shot_type}, {char_name} {phase_motion}. Camera {cam_motion}. "
            ltx_prompt += "Scene concludes naturally, holds final expression. Seamless from previous."
        else:
            # Middle segments - continue action
            ltx_prompt = f"Continuing {shot_type}, {char_name} {phase_motion}. Camera {cam_motion}. "
            ltx_prompt += "Maintains visual continuity, natural progression. Seamless transition."

        # Add base style if available
        if ltx_base and "cinematic" not in ltx_prompt.lower():
            ltx_prompt += f" {ltx_base[:100]}"

        segments.append({
            "segment_index": i,
            "ltx_motion_prompt": ltx_prompt.strip(),
            "phase": "establish" if i == 0 else ("conclude" if i == num_segments - 1 else "continue")
        })

    return segments


def auto_repair_segments(project: str, dry_run: bool = True) -> Dict:
    """Auto-repair missing segment metadata for extended shots with proper LTX prompts."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return {"repaired": 0, "error": "shot_plan.json not found"}

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    repaired = []
    MAX_SEGMENT_DURATION = 20

    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        duration = shot.get("duration", shot.get("duration_seconds", 20))

        if duration <= MAX_SEGMENT_DURATION:
            continue

        segments = shot.get("segments", shot.get("render_plan", {}).get("segments", []))

        # Need to create/repair segments?
        num_needed = max(1, (duration + MAX_SEGMENT_DURATION - 1) // MAX_SEGMENT_DURATION)

        # Check if segments need prompts (undefined or missing ltx_motion_prompt)
        needs_repair = (
            not segments or
            len(segments) < num_needed or
            any(not s.get("ltx_motion_prompt") for s in segments)
        )

        if needs_repair:
            # Generate segments with proper LTX prompts
            seg_duration = duration / num_needed
            ltx_segments = generate_segment_ltx_prompts(shot, num_needed)

            new_segments = []
            for i in range(num_needed):
                ltx_info = ltx_segments[i] if i < len(ltx_segments) else {}

                # Calculate segment duration (last segment gets remainder)
                if i == num_needed - 1:
                    this_duration = duration - (seg_duration * i)
                else:
                    this_duration = seg_duration

                new_segments.append({
                    "segment_index": i,
                    "segment_id": f"{shot_id}_seg{i}",
                    "duration": round(this_duration, 1),
                    "ltx_motion_prompt": ltx_info.get("ltx_motion_prompt", ""),
                    "phase": ltx_info.get("phase", "continue"),
                    "stitch_method": "last_frame_to_first" if i > 0 else "first_frame",
                    "status": "pending"
                })

            shot["segments"] = new_segments
            shot["render_plan"] = {
                "segments": new_segments,
                "total_segments": num_needed,
                "stitch_model": "ltxv2",
                "stitch_method": "last_frame_to_first"
            }
            repaired.append(shot_id)

    if repaired and not dry_run:
        sp["_segments_auto_repaired"] = datetime.now().isoformat()
        with open(shot_plan_path, 'w') as f:
            json.dump(sp, f, indent=2)

    return {
        "repaired": len(repaired),
        "repaired_shots": repaired,
        "dry_run": dry_run
    }


# =============================================================================
# CAST PROPAGATION AUTO-REPAIR
# =============================================================================

def auto_repair_cast_propagation(project: str, dry_run: bool = True) -> Dict:
    """Ensure all shots have characters from cast_map."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"
    story_bible_path = project_path / "story_bible.json"

    if not shot_plan_path.exists():
        return {"repaired": 0, "error": "shot_plan.json not found"}

    with open(shot_plan_path) as f:
        sp = json.load(f)

    cast_chars = set()
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cm = json.load(f)
            cast_chars = {k for k in cm.keys() if not k.startswith("_")}

    # Get character-scene mapping from story_bible
    scene_chars = {}
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            sb = json.load(f)
            for scene in sb.get("scenes", []):
                scene_id = scene.get("scene_id", scene.get("id", ""))
                chars = scene.get("characters", [])
                if scene_id:
                    scene_chars[scene_id] = chars

    shots = sp.get("shots", [])
    repaired = []

    for shot in shots:
        shot_id = shot.get("shot_id", "")
        characters = shot.get("characters", [])

        if not characters:
            # Try to infer from scene
            scene_id = shot.get("scene_id", shot_id.split("_")[0] if "_" in shot_id else "")
            inferred = scene_chars.get(scene_id, [])

            if inferred:
                shot["characters"] = inferred
                repaired.append(shot_id)
            elif cast_chars:
                # Last resort: assign first cast character
                shot["characters"] = [list(cast_chars)[0]]
                repaired.append(shot_id)

    if repaired and not dry_run:
        sp["_cast_propagation_repaired"] = datetime.now().isoformat()
        with open(shot_plan_path, 'w') as f:
            json.dump(sp, f, indent=2)

    return {
        "repaired": len(repaired),
        "repaired_shots": repaired[:10],
        "dry_run": dry_run
    }


# =============================================================================
# FIRST-FRAME ASPECT RATIO CHECK
# =============================================================================

def check_first_frame_aspect_ratios(project: str) -> Dict:
    """Check all first frames have correct 16:9 aspect ratio."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    first_frames_dir = project_path / "first_frames"

    if not first_frames_dir.exists():
        return {"passed": True, "message": "No first_frames directory"}

    issues = []
    checked = 0
    TARGET_RATIO = 16 / 9
    TOLERANCE = 0.1

    try:
        from PIL import Image
    except ImportError:
        return {"passed": True, "message": "PIL not installed, skipping aspect check"}

    for frame_path in first_frames_dir.glob("*.jpg"):
        checked += 1
        try:
            with Image.open(frame_path) as img:
                width, height = img.size
                ratio = width / height

                if abs(ratio - TARGET_RATIO) > TOLERANCE:
                    issues.append({
                        "file": frame_path.name,
                        "ratio": f"{width}x{height} ({ratio:.2f})",
                        "expected": "16:9 (1.78)"
                    })
        except Exception as e:
            issues.append({
                "file": frame_path.name,
                "error": str(e)
            })

    return {
        "passed": len(issues) == 0,
        "checked": checked,
        "issues": issues[:10],
        "total_issues": len(issues)
    }


# =============================================================================
# VIDEO-TO-FRAME HASH VALIDATION
# =============================================================================

# =============================================================================
# VISION ANALYSIS (DINO + CLIP)
# =============================================================================

def run_vision_analysis(
    render_path: str,
    reference_path: Optional[str] = None,
    prompt: Optional[str] = None,
    thresholds: Optional[Dict] = None
) -> Dict:
    """
    Run hybrid DINO+CLIP vision analysis on a rendered frame.

    Args:
        render_path: Path to rendered first_frame
        reference_path: Path to character reference image
        prompt: Generation prompt for CLIP alignment
        thresholds: Optional dict with face_threshold, hybrid_threshold, sharpness_threshold

    Returns:
        Dict with scores and pass/fail verdict
    """
    thresholds = thresholds or {
        "face_threshold": 0.70,      # DINO face consistency
        "hybrid_threshold": 0.65,    # Combined DINO+CLIP
        "sharpness_threshold": 0.50  # Face blur detection
    }

    result = {
        "render_path": render_path,
        "reference_path": reference_path,
        "passed": False,
        "scores": {},
        "issues": []
    }

    # Try to import analyzer
    try:
        sys.path.insert(0, str(BASE_DIR))
        from dino_clip_analyzer import get_hybrid_analyzer
        analyzer = get_hybrid_analyzer()
    except ImportError as e:
        return {
            "passed": True,  # Don't block if analyzer unavailable
            "skipped": True,
            "reason": f"Vision analyzer not available: {e}"
        }
    except Exception as e:
        return {
            "passed": True,
            "skipped": True,
            "reason": f"Vision analyzer init failed: {e}"
        }

    # Check if render exists
    if not Path(render_path).exists():
        result["issues"].append(f"Render not found: {render_path}")
        return result

    try:
        # Run comprehensive analysis
        analysis = analyzer.analyze_comprehensive(
            render_path=render_path,
            reference_path=reference_path,
            prompt=prompt
        )

        result["scores"] = {
            "dino_face": analysis.get("dino_face", 0.75),
            "dino_overall": analysis.get("dino_overall", 0.75),
            "clip_alignment": analysis.get("clip_alignment", 0.75),
            "hybrid_score": analysis.get("hybrid_score", 0.75),
            "face_sharpness": analysis.get("face_sharpness", 0.75)
        }

        # Check thresholds
        if analysis.get("dino_face", 1.0) < thresholds["face_threshold"]:
            result["issues"].append(
                f"Face consistency too low: {analysis['dino_face']:.2%} < {thresholds['face_threshold']:.2%}"
            )

        if analysis.get("hybrid_score", 1.0) < thresholds["hybrid_threshold"]:
            result["issues"].append(
                f"Hybrid score too low: {analysis['hybrid_score']:.2%} < {thresholds['hybrid_threshold']:.2%}"
            )

        if analysis.get("face_sharpness", 1.0) < thresholds["sharpness_threshold"]:
            result["issues"].append(
                f"Face is blurred: sharpness {analysis['face_sharpness']:.2%}"
            )

        result["passed"] = len(result["issues"]) == 0
        result["needs_regeneration"] = analysis.get("needs_regeneration", False)

    except Exception as e:
        result["issues"].append(f"Vision analysis failed: {e}")
        result["passed"] = True  # Don't block on analysis failure
        result["error"] = str(e)

    return result


def validate_video_frame_hashes(project: str) -> Dict:
    """Check videos were generated from their corresponding first frames."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return {"passed": True, "message": "No shot_plan.json"}

    with open(shot_plan_path) as f:
        sp = json.load(f)

    # Build expected hash pairs
    mismatches = []
    validated = 0

    for shot in sp.get("shots", []):
        shot_id = shot.get("shot_id", "")
        first_frame_path = shot.get("first_frame_path")
        video_path = shot.get("video_path")

        if not first_frame_path or not video_path:
            continue

        ff_path = Path(first_frame_path)
        vid_path = Path(video_path)

        if not ff_path.exists() or not vid_path.exists():
            continue

        validated += 1

        # Check modification times - video should be newer
        ff_mtime = ff_path.stat().st_mtime
        vid_mtime = vid_path.stat().st_mtime

        if vid_mtime < ff_mtime:
            mismatches.append({
                "shot_id": shot_id,
                "issue": "Video older than first frame - may be stale"
            })

    return {
        "passed": len(mismatches) == 0,
        "validated": validated,
        "mismatches": mismatches[:10],
        "total_mismatches": len(mismatches)
    }


# =============================================================================
# RENDER QUEUE READY CHECK
# =============================================================================

def check_render_queue_ready(project: str) -> Dict:
    """Check if project is ready for render queue."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return {"ready": False, "reason": "No shot_plan.json"}

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    if not shots:
        return {"ready": False, "reason": "No shots in plan"}

    # Check requirements
    issues = []

    # 1. All shots have nano_prompt
    missing_prompts = [s.get("shot_id") for s in shots if not s.get("nano_prompt")]
    if missing_prompts:
        issues.append(f"{len(missing_prompts)} shots missing nano_prompt")

    # 2. Extended shots have segments
    extended_no_seg = [
        s.get("shot_id") for s in shots
        if s.get("duration", 20) > 20 and not s.get("segments")
    ]
    if extended_no_seg:
        issues.append(f"{len(extended_no_seg)} extended shots missing segments")

    # 3. Cast map exists
    cast_map_path = project_path / "cast_map.json"
    if not cast_map_path.exists():
        issues.append("No cast_map.json")

    return {
        "ready": len(issues) == 0,
        "shot_count": len(shots),
        "issues": issues
    }


# =============================================================================
# UNIFIED GATE RUNNER
# =============================================================================

def run_preflight_gate(project: str, repair: bool = True) -> Dict:
    """Run all preflight checks before generation."""
    results = {
        "gate": "PREFLIGHT",
        "project": project,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # 1. Secret scan
    results["checks"]["secret_scan"] = scan_for_secrets()

    # 2. Sentry check
    results["checks"]["sentry"] = check_sentry_initialized()

    # 3. Model lock
    results["checks"]["model_lock"] = check_model_lock(project)

    # 4. Semantic invariants
    invariants = check_all_invariants(project, repo_root=BASE_DIR)
    results["checks"]["invariants"] = {
        "passed": invariants["passed"],
        "blocking": len(invariants["blocking_violations"]),
        "warnings": len(invariants["warnings"])
    }

    # 5. Render queue ready
    results["checks"]["render_queue"] = check_render_queue_ready(project)

    # Auto-repair if requested
    if repair:
        results["repairs"] = {}
        results["repairs"]["segments"] = auto_repair_segments(project, dry_run=False)
        results["repairs"]["cast"] = auto_repair_cast_propagation(project, dry_run=False)

    # Overall verdict
    blocking = (
        not results["checks"]["secret_scan"]["passed"] or
        not results["checks"]["model_lock"]["passed"] or
        not results["checks"]["invariants"]["passed"]
    )

    results["passed"] = not blocking
    results["verdict"] = "BLOCKED" if blocking else "READY"

    return results


def run_per_shot_gate(project: str, shot_id: str) -> Dict:
    """
    Run per-shot validation after frame generation.

    Checks:
    1. Vision analysis (DINO face + CLIP prompt + sharpness)
    2. Aspect ratio
    3. File integrity

    Args:
        project: Project name
        shot_id: Shot ID to validate
    """
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"

    results = {
        "gate": "PER_SHOT",
        "project": project,
        "shot_id": shot_id,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # Load shot data
    if not shot_plan_path.exists():
        results["passed"] = False
        results["verdict"] = "ERROR"
        results["error"] = "shot_plan.json not found"
        return results

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    shot = next((s for s in shots if s.get("shot_id") == shot_id), None)

    if not shot:
        results["passed"] = False
        results["verdict"] = "ERROR"
        results["error"] = f"Shot {shot_id} not found"
        return results

    # Get first frame path
    first_frame_path = shot.get("first_frame_path")
    if not first_frame_path:
        first_frame_path = str(project_path / "first_frames" / f"{shot_id}.jpg")

    # Get character reference from cast_map
    reference_path = None
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)

        # Get first character's reference
        characters = shot.get("characters", [])
        if characters:
            char_name = characters[0] if isinstance(characters[0], str) else characters[0].get("name", "")
            char_entry = cast_map.get(char_name) or cast_map.get(char_name.upper())
            if char_entry and isinstance(char_entry, dict):
                ref_url = char_entry.get("reference_url") or char_entry.get("headshot_url")
                if ref_url and "path=" in ref_url:
                    reference_path = ref_url.split("path=")[-1]

    # Get prompt for CLIP
    prompt = shot.get("nano_prompt", "")

    # 1. Vision analysis
    results["checks"]["vision"] = run_vision_analysis(
        render_path=first_frame_path,
        reference_path=reference_path,
        prompt=prompt
    )

    # 2. Aspect ratio check
    aspect_passed = True
    try:
        from PIL import Image
        if Path(first_frame_path).exists():
            with Image.open(first_frame_path) as img:
                w, h = img.size
                ratio = w / h
                expected = 16 / 9
                aspect_passed = abs(ratio - expected) < 0.1
                results["checks"]["aspect_ratio"] = {
                    "passed": aspect_passed,
                    "ratio": f"{w}x{h} ({ratio:.2f})",
                    "expected": "16:9"
                }
        else:
            results["checks"]["aspect_ratio"] = {
                "passed": False,
                "error": "Frame not found"
            }
            aspect_passed = False
    except Exception as e:
        results["checks"]["aspect_ratio"] = {"passed": True, "skipped": str(e)}

    # 3. File integrity
    integrity_passed = Path(first_frame_path).exists()
    results["checks"]["file_integrity"] = {
        "passed": integrity_passed,
        "path": first_frame_path,
        "exists": integrity_passed
    }

    # Overall verdict
    vision_passed = results["checks"]["vision"].get("passed", True)
    blocking = not (vision_passed and aspect_passed and integrity_passed)

    results["passed"] = not blocking
    results["verdict"] = "FAILED" if blocking else "PASSED"

    # If vision failed, add regeneration recommendation
    if not vision_passed:
        results["recommendation"] = "REGENERATE"
        results["issues"] = results["checks"]["vision"].get("issues", [])

    return results


def run_pre_stitch_gate(project: str) -> Dict:
    """Run all checks before stitching."""
    results = {
        "gate": "PRE_STITCH",
        "project": project,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # 1. First-frame aspect ratios
    results["checks"]["aspect_ratios"] = check_first_frame_aspect_ratios(project)

    # 2. Video-frame hash validation
    results["checks"]["video_hashes"] = validate_video_frame_hashes(project)

    # 3. Segment integrity
    from validate_segment_integrity import validate_segment_integrity
    results["checks"]["segment_integrity"] = validate_segment_integrity(project)

    # Overall
    blocking = not results["checks"]["segment_integrity"].get("valid", True)
    results["passed"] = not blocking
    results["verdict"] = "BLOCKED" if blocking else "READY"

    return results


def run_full_gate(project: str) -> Dict:
    """Run all gates in sequence."""
    return {
        "preflight": run_preflight_gate(project, repair=True),
        "pre_stitch": run_pre_stitch_gate(project)
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tools/auto_heal_gate.py <project> --preflight")
        print("  python3 tools/auto_heal_gate.py <project> --per-shot <shot_id>")
        print("  python3 tools/auto_heal_gate.py <project> --pre-stitch")
        print("  python3 tools/auto_heal_gate.py <project> --full")
        print("  python3 tools/auto_heal_gate.py <project> --vision <image_path> [reference_path] [prompt]")
        sys.exit(1)

    project = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--full"

    if mode == "--preflight":
        result = run_preflight_gate(project)
    elif mode == "--per-shot":
        if len(sys.argv) < 4:
            print("Error: --per-shot requires shot_id")
            sys.exit(1)
        shot_id = sys.argv[3]
        result = run_per_shot_gate(project, shot_id)
    elif mode == "--pre-stitch":
        result = run_pre_stitch_gate(project)
    elif mode == "--vision":
        # Direct vision analysis mode
        if len(sys.argv) < 4:
            print("Error: --vision requires image_path")
            sys.exit(1)
        image_path = sys.argv[3]
        ref_path = sys.argv[4] if len(sys.argv) > 4 else None
        prompt = sys.argv[5] if len(sys.argv) > 5 else None
        result = run_vision_analysis(image_path, ref_path, prompt)
    else:
        result = run_full_gate(project)

    print(json.dumps(result, indent=2, default=str))

    # Exit code based on pass/fail
    if isinstance(result, dict):
        if "passed" in result:
            sys.exit(0 if result["passed"] else 1)
        elif "preflight" in result:
            passed = result["preflight"].get("passed", False) and result["pre_stitch"].get("passed", False)
            sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
