#!/usr/bin/env python3
"""
SEGMENT INTEGRITY VALIDATOR

Validates:
- Extended shots have segments
- Segment indices are contiguous (0, 1, 2, ...)
- Sum of segment durations == shot duration (±tolerance)
- No orphan segment files
- No 6s videos for 60s shots

Usage:
    python3 tools/validate_segment_integrity.py <project>
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
DURATION_TOLERANCE = 2.0  # seconds


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


def validate_segment_integrity(project: str) -> Dict:
    """Validate segment integrity for a project."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    shot_plan_path = project_path / "shot_plan.json"
    videos_dir = project_path / "videos"

    issues = []
    stats = {
        "total_shots": 0,
        "extended_shots": 0,
        "shots_with_segments": 0,
        "segments_valid": 0,
        "segments_invalid": 0,
        "orphan_segments": 0,
        "duration_mismatches": 0
    }

    if not shot_plan_path.exists():
        return {"valid": False, "issues": ["shot_plan.json not found"], "stats": stats}

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots = shot_plan.get("shots", [])
    stats["total_shots"] = len(shots)

    # Track expected segment files
    expected_segments = set()
    found_segments = set()

    # Validate each shot
    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        duration = shot.get("duration", shot.get("duration_seconds", 20))
        segments = shot.get("segments", shot.get("render_plan", {}).get("segments", []))

        if duration > 20:
            stats["extended_shots"] += 1

            # Check 1: Extended shots must have segments
            if not segments:
                # Check if segments are auto-computed
                num_segs = max(1, (duration + 19) // 20)
                if num_segs > 1:
                    issues.append(f"BLOCKING: {shot_id} ({duration}s) has no segments defined")
                    stats["segments_invalid"] += 1
                    continue

            stats["shots_with_segments"] += 1

            # Check 2: Segment indices contiguous
            if segments:
                indices = []
                for seg in segments:
                    idx = seg.get("segment_index", seg.get("segment_id", ""))
                    if isinstance(idx, int):
                        indices.append(idx)
                    elif isinstance(idx, str) and "_S" in idx:
                        try:
                            indices.append(int(idx.split("_S")[-1]) - 1)
                        except:
                            pass

                if indices:
                    indices.sort()
                    expected_indices = list(range(len(indices)))
                    if indices != expected_indices:
                        issues.append(f"WARNING: {shot_id} has non-contiguous segment indices: {indices}")

            # Check 3: Sum of segment durations
            if segments:
                seg_total = sum(s.get("duration", 0) for s in segments)
                if abs(seg_total - duration) > DURATION_TOLERANCE:
                    issues.append(f"WARNING: {shot_id} segment sum ({seg_total}s) != planned ({duration}s)")
                    stats["duration_mismatches"] += 1

            # Track expected segment files
            num_segs = len(segments) if segments else max(1, (duration + 19) // 20)
            for i in range(num_segs):
                expected_segments.add(f"{shot_id}_seg{i}.mp4")

            # Check 4: Final video duration if exists
            final_video = videos_dir / f"{shot_id}.mp4"
            if final_video.exists():
                actual_dur = get_video_duration(final_video)
                if actual_dur < duration * 0.5:
                    issues.append(f"BLOCKING: {shot_id} final video is {actual_dur:.1f}s but should be {duration}s")
                    stats["duration_mismatches"] += 1
                elif abs(actual_dur - duration) > DURATION_TOLERANCE:
                    issues.append(f"WARNING: {shot_id} duration mismatch: {actual_dur:.1f}s vs {duration}s")

            stats["segments_valid"] += 1

    # Check 5: Orphan segments
    if videos_dir.exists():
        for seg_file in videos_dir.glob("*_seg*.mp4"):
            found_segments.add(seg_file.name)
            if seg_file.name not in expected_segments:
                # Extract shot_id
                parts = seg_file.stem.split("_seg")
                if len(parts) == 2:
                    shot_id = parts[0]
                    # Only flag as orphan if shot exists but doesn't need this segment
                    shot_in_plan = any(s.get("shot_id") == shot_id for s in shots)
                    if shot_in_plan:
                        stats["orphan_segments"] += 1
                        issues.append(f"WARNING: Orphan segment {seg_file.name}")

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
        print("Usage: python3 tools/validate_segment_integrity.py <project>")
        sys.exit(1)

    project = sys.argv[1]
    result = validate_segment_integrity(project)

    print(f"\n{'='*60}")
    print(f"  SEGMENT INTEGRITY VALIDATION: {project}")
    print(f"{'='*60}")

    print(f"\n  STATS:")
    for k, v in result["stats"].items():
        print(f"    {k}: {v}")

    if result["issues"]:
        print(f"\n  ISSUES ({len(result['issues'])}):")
        for issue in result["issues"][:15]:
            print(f"    - {issue}")
        if len(result["issues"]) > 15:
            print(f"    ... and {len(result['issues']) - 15} more")

    print(f"\n  VERDICT: {'PASS' if result['valid'] else 'FAIL'}")
    print(f"    Blocking: {result['blocking_count']}")
    print(f"    Warnings: {result['warning_count']}")
    print(f"{'='*60}\n")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
