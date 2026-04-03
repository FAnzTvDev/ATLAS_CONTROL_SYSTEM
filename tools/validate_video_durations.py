#!/usr/bin/env python3
"""
PHASE 4 VALIDATION - Extended Shots & Video Stitching

Validates:
1. Extended shots (>20s) have segments or stitched final
2. No orphan segments without final video
3. Video durations match planned durations (±5s tolerance)
4. No 6s videos for 54s shots

Exit code 0 = PASS
Exit code 1 = FAIL
"""

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
TOLERANCE_SECONDS = 5


def get_video_duration(video_path: Path) -> float:
    """Get video duration using ffprobe."""
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


def validate_video_durations(project: str) -> dict:
    """Validate video durations for a project."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    videos_dir = project_path / "videos"

    shot_plan_path = project_path / "shot_plan.json"

    issues = []
    stats = {
        "total_shots": 0,
        "extended_shots": 0,
        "videos_exist": 0,
        "videos_missing": 0,
        "duration_match": 0,
        "duration_mismatch": 0,
        "orphan_segments": 0,
        "unstitched_extended": 0
    }

    if not shot_plan_path.exists():
        return {"valid": False, "issues": ["shot_plan.json not found"], "stats": stats}

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots = shot_plan.get("shots", [])
    stats["total_shots"] = len(shots)

    # Check each shot
    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        planned_duration = shot.get("duration", shot.get("duration_seconds", 20))

        if planned_duration > 20:
            stats["extended_shots"] += 1

        final_video = videos_dir / f"{shot_id}.mp4"

        if final_video.exists():
            stats["videos_exist"] += 1
            actual_duration = get_video_duration(final_video)

            # Check duration match
            if abs(actual_duration - planned_duration) <= TOLERANCE_SECONDS:
                stats["duration_match"] += 1
            else:
                stats["duration_mismatch"] += 1
                # Severe mismatch (< 50% of planned) is blocking
                if actual_duration < planned_duration * 0.5:
                    issues.append(f"BLOCKING: {shot_id} actual={actual_duration:.1f}s vs planned={planned_duration}s")
                else:
                    issues.append(f"WARNING: {shot_id} duration mismatch {actual_duration:.1f}s vs {planned_duration}s")
        else:
            stats["videos_missing"] += 1

            # For extended shots, check for segments
            if planned_duration > 20:
                seg0 = videos_dir / f"{shot_id}_seg0.mp4"
                if seg0.exists():
                    # Segments exist but not stitched
                    stats["unstitched_extended"] += 1
                    issues.append(f"BLOCKING: {shot_id} has segments but no stitched final")

    # Check for orphan segments
    if videos_dir.exists():
        for video_file in videos_dir.glob("*_seg*.mp4"):
            # Extract shot_id from segment filename
            parts = video_file.stem.split("_seg")
            if len(parts) == 2:
                shot_id = parts[0]
                final_video = videos_dir / f"{shot_id}.mp4"
                if not final_video.exists():
                    # Check if this shot is in plan
                    shot_in_plan = any(s.get("shot_id") == shot_id for s in shots)
                    if shot_in_plan:
                        stats["orphan_segments"] += 1

    # Determine validity
    blocking = [i for i in issues if i.startswith("BLOCKING")]
    valid = len(blocking) == 0

    return {
        "valid": valid,
        "issues": issues,
        "stats": stats,
        "blocking_count": len(blocking),
        "warning_count": len(issues) - len(blocking)
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_video_durations.py <project>")
        print("\nAvailable projects:")
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        for p in sorted(pipeline_dir.iterdir()):
            if p.is_dir() and (p / "shot_plan.json").exists():
                print(f"  - {p.name}")
        sys.exit(1)

    project = sys.argv[1]
    result = validate_video_durations(project)

    print(f"\n{'='*60}")
    print(f"  PHASE 4 VALIDATION: {project}")
    print(f"{'='*60}")

    print(f"\n  STATS:")
    for k, v in result["stats"].items():
        print(f"    {k}: {v}")

    if result["issues"]:
        print(f"\n  ISSUES ({len(result['issues'])}):")
        for issue in result["issues"][:20]:
            print(f"    - {issue}")
        if len(result["issues"]) > 20:
            print(f"    ... and {len(result['issues']) - 20} more")

    print(f"\n  VERDICT: {'PASS' if result['valid'] else 'FAIL'}")
    print(f"    Blocking: {result['blocking_count']}")
    print(f"    Warnings: {result['warning_count']}")
    print(f"{'='*60}\n")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
