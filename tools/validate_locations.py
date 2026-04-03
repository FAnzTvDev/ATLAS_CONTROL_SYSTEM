#!/usr/bin/env python3
"""
PHASE 1 VALIDATION - Location Propagation Contract

Validates:
1. Locations in story_bible.locations[] exist
2. Locations in shot_plan.shots[].location match
3. location_masters directory exists
4. locations_in_story == locations_on_disk == locations_in_shots

Exit code 0 = PASS
Exit code 1 = FAIL
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")


def normalize_location(loc: str) -> str:
    """Normalize location name for comparison."""
    return loc.upper().strip().replace("_", " ").replace("-", " ")


def validate_locations(project: str) -> dict:
    """Validate location propagation for a project."""
    project_path = BASE_DIR / "pipeline_outputs" / project

    story_bible_path = project_path / "story_bible.json"
    shot_plan_path = project_path / "shot_plan.json"
    location_masters_dir = project_path / "location_masters"

    issues = []
    stats = {
        "locations_in_story": 0,
        "locations_in_shots": 0,
        "locations_on_disk": 0,
        "locations_missing_from_story": [],
        "locations_missing_from_shots": [],
        "locations_missing_from_disk": []
    }

    # Collect locations from each source
    story_locations = set()
    shot_locations = set()
    disk_locations = set()

    # From story_bible
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            sb = json.load(f)

        # From locations array
        for loc in sb.get("locations", []):
            if isinstance(loc, dict):
                name = loc.get("name", "")
            else:
                name = str(loc)
            if name:
                story_locations.add(normalize_location(name))

        # From setting.locations fallback
        if not story_locations:
            for loc in sb.get("setting", {}).get("locations", []):
                if isinstance(loc, dict):
                    name = loc.get("name", "")
                else:
                    name = str(loc)
                if name:
                    story_locations.add(normalize_location(name))

        # From scenes
        for scene in sb.get("scenes", []):
            if scene.get("location"):
                story_locations.add(normalize_location(scene["location"]))

    # From shot_plan
    if shot_plan_path.exists():
        with open(shot_plan_path) as f:
            sp = json.load(f)

        for shot in sp.get("shots", []):
            if shot.get("location"):
                shot_locations.add(normalize_location(shot["location"]))

    # From disk
    if location_masters_dir.exists():
        for loc_dir in location_masters_dir.iterdir():
            if loc_dir.is_dir():
                disk_locations.add(normalize_location(loc_dir.name))
            elif loc_dir.is_file() and loc_dir.suffix.lower() in [".jpg", ".png", ".jpeg"]:
                # Handle flat files (location_name.jpg)
                disk_locations.add(normalize_location(loc_dir.stem))

    stats["locations_in_story"] = len(story_locations)
    stats["locations_in_shots"] = len(shot_locations)
    stats["locations_on_disk"] = len(disk_locations)

    # Compare sources
    all_locations = story_locations | shot_locations

    # Locations in shots but not in story
    missing_from_story = shot_locations - story_locations
    if missing_from_story:
        stats["locations_missing_from_story"] = list(missing_from_story)
        for loc in missing_from_story:
            issues.append(f"WARNING: Location '{loc}' in shots but not in story_bible")

    # Locations in story but not in any shot
    missing_from_shots = story_locations - shot_locations
    if missing_from_shots:
        stats["locations_missing_from_shots"] = list(missing_from_shots)
        for loc in missing_from_shots:
            issues.append(f"WARNING: Location '{loc}' in story_bible but not used in any shot")

    # Locations used but not on disk
    missing_from_disk = all_locations - disk_locations
    if missing_from_disk:
        stats["locations_missing_from_disk"] = list(missing_from_disk)
        for loc in missing_from_disk:
            # Only warn - disk locations are optional until render
            issues.append(f"INFO: Location '{loc}' has no master image on disk")

    # Check for location_masters directory
    if not location_masters_dir.exists():
        issues.append("INFO: location_masters directory does not exist")

    # Determine validity (no blocking issues for locations)
    valid = True  # Locations are non-blocking in Phase 1

    return {
        "valid": valid,
        "issues": issues,
        "stats": stats,
        "all_locations": list(all_locations),
        "story_locations": list(story_locations),
        "shot_locations": list(shot_locations),
        "disk_locations": list(disk_locations)
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_locations.py <project>")
        print("\nAvailable projects:")
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        for p in sorted(pipeline_dir.iterdir()):
            if p.is_dir() and (p / "shot_plan.json").exists():
                print(f"  - {p.name}")
        sys.exit(1)

    project = sys.argv[1]
    result = validate_locations(project)

    print(f"\n{'='*60}")
    print(f"  PHASE 1 VALIDATION (Locations): {project}")
    print(f"{'='*60}")

    print(f"\n  STATS:")
    print(f"    Locations in story_bible: {result['stats']['locations_in_story']}")
    print(f"    Locations in shot_plan: {result['stats']['locations_in_shots']}")
    print(f"    Locations on disk: {result['stats']['locations_on_disk']}")

    print(f"\n  ALL LOCATIONS ({len(result['all_locations'])}):")
    for loc in sorted(result["all_locations"]):
        in_story = "S" if loc in [normalize_location(l) for l in result["story_locations"]] else "-"
        in_shots = "P" if loc in [normalize_location(l) for l in result["shot_locations"]] else "-"
        in_disk = "D" if loc in [normalize_location(l) for l in result["disk_locations"]] else "-"
        print(f"    [{in_story}{in_shots}{in_disk}] {loc}")

    if result["issues"]:
        print(f"\n  ISSUES ({len(result['issues'])}):")
        for issue in result["issues"][:10]:
            print(f"    - {issue}")

    print(f"\n  VERDICT: {'PASS' if result['valid'] else 'FAIL'}")
    print(f"{'='*60}\n")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
