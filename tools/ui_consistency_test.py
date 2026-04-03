#!/usr/bin/env python3
"""
PHASE 5 VALIDATION - UI Truth & Consistency Lock

Validates:
1. All projects have same UI bundle structure
2. story_bible has required arrays (scenes, characters, locations)
3. shot_plan is primary execution truth
4. No UI behavior differences between projects

Exit code 0 = ALL PASS
Exit code 1 = FAIL
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Set

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

# Required fields in UI bundle
REQUIRED_STORY_BIBLE_FIELDS = ["scenes", "characters", "locations"]
REQUIRED_SHOT_FIELDS = ["shot_id", "duration", "nano_prompt"]
REQUIRED_SCENE_FIELDS = ["scene_id", "beats"]


def validate_ui_bundle(project: str) -> Dict:
    """Validate UI bundle structure for a project."""
    project_path = BASE_DIR / "pipeline_outputs" / project
    issues = []

    story_bible_path = project_path / "story_bible.json"
    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"

    structure = {
        "has_story_bible": False,
        "has_shot_plan": False,
        "has_cast_map": False,
        "story_bible_fields": [],
        "shot_plan_fields": [],
        "scene_count": 0,
        "shot_count": 0,
        "character_count": 0,
        "location_count": 0,
        "beats_total": 0,
        "scenes_with_beats": 0,
        "scenes_without_beats": 0
    }

    # Check story_bible
    if story_bible_path.exists():
        structure["has_story_bible"] = True
        with open(story_bible_path) as f:
            sb = json.load(f)

        for field in REQUIRED_STORY_BIBLE_FIELDS:
            if field in sb:
                structure["story_bible_fields"].append(field)
            else:
                issues.append(f"story_bible missing {field}")

        scenes = sb.get("scenes", [])
        structure["scene_count"] = len(scenes)
        structure["character_count"] = len(sb.get("characters", []))
        structure["location_count"] = len(sb.get("locations", []))

        for scene in scenes:
            beats = scene.get("beats", [])
            if beats:
                structure["scenes_with_beats"] += 1
                structure["beats_total"] += len(beats)
            else:
                structure["scenes_without_beats"] += 1

        # Check for V17 enforcement flag
        if not sb.get("_ui_enforced"):
            issues.append("story_bible not UI enforced (_ui_enforced flag missing)")

    else:
        issues.append("story_bible.json not found")

    # Check shot_plan
    if shot_plan_path.exists():
        structure["has_shot_plan"] = True
        with open(shot_plan_path) as f:
            sp = json.load(f)

        shots = sp.get("shots", [])
        structure["shot_count"] = len(shots)

        if shots:
            first_shot = shots[0]
            structure["shot_plan_fields"] = list(first_shot.keys())

            for field in REQUIRED_SHOT_FIELDS:
                if field not in first_shot:
                    issues.append(f"shots missing required field: {field}")

        # Check for shots without nano_prompt
        shots_no_prompt = [s for s in shots if not s.get("nano_prompt")]
        if shots_no_prompt:
            issues.append(f"{len(shots_no_prompt)} shots missing nano_prompt")

        # Check for shots without characters
        shots_no_chars = [s for s in shots if not s.get("characters")]
        if shots_no_chars:
            issues.append(f"{len(shots_no_chars)} shots missing characters")

    else:
        issues.append("BLOCKING: shot_plan.json not found")

    # Check cast_map
    if cast_map_path.exists():
        structure["has_cast_map"] = True
    else:
        issues.append("cast_map.json not found")

    return {
        "project": project,
        "structure": structure,
        "issues": issues,
        "valid": len([i for i in issues if "BLOCKING" in i]) == 0
    }


def compare_projects(results: List[Dict]) -> Dict:
    """Compare UI consistency across projects."""
    if len(results) < 2:
        return {"consistent": True, "differences": []}

    differences = []
    reference = results[0]

    for other in results[1:]:
        # Compare key structural elements
        ref_struct = reference["structure"]
        oth_struct = other["structure"]

        # Check scene/shot presence
        if ref_struct["has_story_bible"] != oth_struct["has_story_bible"]:
            differences.append(f"{reference['project']} vs {other['project']}: story_bible existence differs")

        if ref_struct["has_shot_plan"] != oth_struct["has_shot_plan"]:
            differences.append(f"{reference['project']} vs {other['project']}: shot_plan existence differs")

        # Check required fields
        ref_fields = set(ref_struct["story_bible_fields"])
        oth_fields = set(oth_struct["story_bible_fields"])
        if ref_fields != oth_fields:
            diff = ref_fields.symmetric_difference(oth_fields)
            differences.append(f"{reference['project']} vs {other['project']}: story_bible fields differ: {diff}")

        # Check beats presence pattern
        if ref_struct["scenes_with_beats"] > 0 and oth_struct["scenes_without_beats"] == oth_struct["scene_count"]:
            differences.append(f"{other['project']}: No scenes have beats (inconsistent with {reference['project']})")

    return {
        "consistent": len(differences) == 0,
        "differences": differences
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ui_consistency_test.py <project1> [project2] [project3] ...")
        print("\nAvailable projects:")
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        for p in sorted(pipeline_dir.iterdir()):
            if p.is_dir() and (p / "shot_plan.json").exists():
                print(f"  - {p.name}")
        sys.exit(1)

    projects = sys.argv[1:]
    results = []

    print(f"\n{'='*70}")
    print(f"  PHASE 5 VALIDATION: UI Consistency Test")
    print(f"  Projects: {', '.join(projects)}")
    print(f"{'='*70}")

    # Validate each project
    for project in projects:
        result = validate_ui_bundle(project)
        results.append(result)

        print(f"\n  [{project}]")
        print(f"    Story Bible: {'OK' if result['structure']['has_story_bible'] else 'MISSING'}")
        print(f"    Shot Plan: {'OK' if result['structure']['has_shot_plan'] else 'MISSING'}")
        print(f"    Cast Map: {'OK' if result['structure']['has_cast_map'] else 'MISSING'}")
        print(f"    Scenes: {result['structure']['scene_count']} ({result['structure']['scenes_with_beats']} with beats)")
        print(f"    Shots: {result['structure']['shot_count']}")
        print(f"    Characters: {result['structure']['character_count']}")
        print(f"    Locations: {result['structure']['location_count']}")

        if result["issues"]:
            print(f"    Issues:")
            for issue in result["issues"][:5]:
                print(f"      - {issue}")

    # Compare projects
    comparison = compare_projects(results)

    print(f"\n  CROSS-PROJECT CONSISTENCY:")
    if comparison["consistent"]:
        print(f"    All projects have consistent UI structure")
    else:
        print(f"    DIFFERENCES FOUND:")
        for diff in comparison["differences"]:
            print(f"      - {diff}")

    # Overall verdict
    all_valid = all(r["valid"] for r in results)
    consistent = comparison["consistent"]

    print(f"\n  {'='*60}")
    print(f"  OVERALL VERDICT: {'PASS' if (all_valid and consistent) else 'FAIL'}")
    print(f"    Individual Projects: {'ALL VALID' if all_valid else 'ISSUES FOUND'}")
    print(f"    Cross-Project Consistency: {'CONSISTENT' if consistent else 'INCONSISTENT'}")
    print(f"  {'='*60}\n")

    sys.exit(0 if (all_valid and consistent) else 1)


if __name__ == "__main__":
    main()
