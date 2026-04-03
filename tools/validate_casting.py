#!/usr/bin/env python3
"""
PHASE 3 VALIDATION - Cast & Character Execution

Validates:
1. No shot has empty characters[]
2. All cast_map entries have reference_url
3. All characters appear in cast_map
4. Extras pools properly marked

Exit code 0 = PASS
Exit code 1 = FAIL
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")


def validate_casting(project: str) -> dict:
    """Validate casting for a project."""
    project_path = BASE_DIR / "pipeline_outputs" / project

    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"

    issues = []
    stats = {
        "total_shots": 0,
        "shots_with_chars": 0,
        "shots_empty_chars": 0,
        "cast_entries": 0,
        "cast_with_refs": 0,
        "cast_missing_refs": 0,
        "extras_pools": 0
    }

    # Load shot_plan
    if not shot_plan_path.exists():
        return {"valid": False, "issues": ["shot_plan.json not found"], "stats": stats}

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots = shot_plan.get("shots", [])
    stats["total_shots"] = len(shots)

    # Check 1: No empty characters[]
    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        chars = shot.get("characters", [])

        if chars:
            stats["shots_with_chars"] += 1
        else:
            stats["shots_empty_chars"] += 1
            issues.append(f"BLOCKING: {shot_id} has empty characters[]")

    # Load cast_map
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)

        for name, data in cast_map.items():
            if name.startswith("_"):
                continue
            if not isinstance(data, dict):
                continue

            stats["cast_entries"] += 1

            if data.get("is_extras_pool"):
                stats["extras_pools"] += 1

            if data.get("reference_url"):
                stats["cast_with_refs"] += 1
            else:
                stats["cast_missing_refs"] += 1
                is_extras = data.get("is_extras_pool", False)
                if not is_extras:
                    issues.append(f"WARNING: {name} missing reference_url")
    else:
        issues.append("WARNING: cast_map.json not found")

    # Check 2: All characters in shots appear in cast_map
    all_chars = set()
    for shot in shots:
        for c in shot.get("characters", []):
            char_name = c.upper() if isinstance(c, str) else str(c).upper()
            all_chars.add(char_name)

    cast_names = {k.upper() for k in cast_map.keys() if not k.startswith("_")} if cast_map_path.exists() else set()

    for char in all_chars:
        if char and char not in cast_names:
            issues.append(f"WARNING: Character {char} not in cast_map")

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
        print("Usage: python3 validate_casting.py <project>")
        print("\nAvailable projects:")
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        for p in sorted(pipeline_dir.iterdir()):
            if p.is_dir() and (p / "shot_plan.json").exists():
                print(f"  - {p.name}")
        sys.exit(1)

    project = sys.argv[1]
    result = validate_casting(project)

    print(f"\n{'='*60}")
    print(f"  PHASE 3 VALIDATION: {project}")
    print(f"{'='*60}")

    print(f"\n  STATS:")
    for k, v in result["stats"].items():
        print(f"    {k}: {v}")

    if result["issues"]:
        print(f"\n  ISSUES ({len(result['issues'])}):")
        for issue in result["issues"][:20]:  # Show first 20
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
