"""
UI CONSISTENCY ENFORCER - V17

Ensures all projects have the same data structure for UI rendering.
When data is missing, derives it from shot_plan (single source of truth).

Rules:
- Story Bible structure must match expected UI schema
- Missing beats are derived from shot_plan
- Missing dialogue is extracted from shots
- UI should never show "empty" - graceful degradation with placeholder content
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def run_ui_consistency_enforcer(project: str, repo_root: Path = None) -> dict:
    """
    Enforce consistent UI data structure across projects.

    Fixes:
    1. story_bible.scenes without beats → derive from shot_plan
    2. story_bible.scenes without dialogue → extract from shot_plan
    3. story_bible missing locations → extract from scenes
    4. story_bible.characters missing details → derive from cast_map

    Returns:
        {
            "agent": "ui_consistency_enforcer",
            "state": "COMPLETE",
            "facts": {
                "scenes_enriched": N,
                "beats_created": N,
                "dialogue_extracted": N,
                "locations_added": N
            }
        }
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent.parent

    repo_root = Path(repo_root)
    project_path = repo_root / "pipeline_outputs" / project

    story_bible_path = project_path / "story_bible.json"
    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"

    if not shot_plan_path.exists():
        return {"agent": "ui_consistency_enforcer", "state": "FAILED", "error": "No shot_plan.json"}

    # Load files
    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    if story_bible_path.exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)
    else:
        story_bible = {}

    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)
    else:
        cast_map = {}

    scenes_enriched = 0
    beats_created = 0
    dialogue_extracted = 0
    locations_added = 0

    # ============================================================
    # PHASE 1: Build scene→shots mapping from shot_plan
    # ============================================================
    scene_shots = {}
    for shot in shot_plan.get("shots", []):
        scene_id = shot.get("scene_id", "")
        if not scene_id:
            # Try to extract from shot_id (e.g., "001_001A" → "001")
            shot_id = shot.get("shot_id", "")
            if "_" in shot_id:
                scene_id = shot_id.split("_")[0]

        if scene_id:
            if scene_id not in scene_shots:
                scene_shots[scene_id] = []
            scene_shots[scene_id].append(shot)

    # ============================================================
    # PHASE 2: Ensure story_bible has scenes array
    # ============================================================
    if "scenes" not in story_bible or not story_bible["scenes"]:
        story_bible["scenes"] = []

        # Create scenes from shot_plan
        for scene_id in sorted(scene_shots.keys()):
            shots = scene_shots[scene_id]
            first_shot = shots[0] if shots else {}

            story_bible["scenes"].append({
                "scene_id": scene_id,
                "title": first_shot.get("scene_title", f"Scene {scene_id}"),
                "location": first_shot.get("location", "UNKNOWN"),
                "time_of_day": first_shot.get("time_of_day", "DAY"),
                "beats": [],
                "shots": [s.get("shot_id") for s in shots]
            })
            scenes_enriched += 1

    # ============================================================
    # PHASE 3: Enrich scenes with missing data
    # ============================================================
    for scene in story_bible.get("scenes", []):
        scene_id = str(scene.get("scene_id", "")).zfill(3)
        shots = scene_shots.get(scene_id, [])

        # Ensure beats exist
        if not scene.get("beats"):
            scene["beats"] = []

            # Create beats from shots
            beat_number = 1
            for shot in shots:
                beat = {
                    "beat_number": beat_number,
                    "beat_type": "action",
                    "description": shot.get("nano_prompt", shot.get("description", "")),
                    "characters": shot.get("characters", []),
                    "dialogue": shot.get("dialogue", ""),
                    "emotional_beat": shot.get("emotional_beat", ""),
                    "emotional_tone": shot.get("emotional_tone", "neutral"),
                    "shot_id": shot.get("shot_id", "")
                }

                # Determine beat type from dialogue presence
                if beat["dialogue"]:
                    beat["beat_type"] = "dialogue"
                    dialogue_extracted += 1

                scene["beats"].append(beat)
                beats_created += 1
                beat_number += 1

            scenes_enriched += 1

        # Ensure shots array exists
        if not scene.get("shots"):
            scene["shots"] = [s.get("shot_id") for s in shots]

        # Ensure location exists
        if not scene.get("location") and shots:
            scene["location"] = shots[0].get("location", "UNKNOWN")

        # Ensure time_of_day exists
        if not scene.get("time_of_day") and shots:
            scene["time_of_day"] = shots[0].get("time_of_day", "DAY")

        # Ensure int_ext exists
        if not scene.get("int_ext"):
            scene["int_ext"] = "INT"

        # Ensure estimated_duration_seconds exists
        if not scene.get("estimated_duration_seconds"):
            scene["estimated_duration_seconds"] = sum(
                s.get("duration", 20) for s in shots
            )

    # ============================================================
    # PHASE 4: Ensure locations array exists
    # ============================================================
    if not story_bible.get("locations"):
        locations_set = set()

        # From story_bible.setting.locations
        if story_bible.get("setting", {}).get("locations"):
            for loc in story_bible["setting"]["locations"]:
                if isinstance(loc, dict):
                    locations_set.add(loc.get("name", ""))
                else:
                    locations_set.add(str(loc))

        # From scenes
        for scene in story_bible.get("scenes", []):
            if scene.get("location"):
                locations_set.add(scene["location"])

        # From shot_plan
        for shot in shot_plan.get("shots", []):
            if shot.get("location"):
                locations_set.add(shot["location"])

        # Build locations array
        story_bible["locations"] = []
        for loc_name in sorted(locations_set):
            if loc_name and loc_name != "UNKNOWN":
                story_bible["locations"].append({
                    "name": loc_name,
                    "source": "extracted"
                })
                locations_added += 1

    # ============================================================
    # PHASE 5: Ensure characters array has full details
    # ============================================================
    if not story_bible.get("characters"):
        story_bible["characters"] = []

        for char_name, char_data in cast_map.items():
            if char_name.startswith("_"):
                continue
            if not isinstance(char_data, dict):
                continue

            story_bible["characters"].append({
                "name": char_name,
                "role": "supporting",
                "ai_actor": char_data.get("ai_actor", ""),
                "headshot_url": char_data.get("headshot_url", ""),
                "is_extras_pool": char_data.get("is_extras_pool", False)
            })
    else:
        # Enrich existing characters with cast_map data
        for char in story_bible["characters"]:
            char_name = char.get("name", "").upper()
            if char_name in cast_map:
                char_data = cast_map[char_name]
                if isinstance(char_data, dict):
                    if not char.get("ai_actor"):
                        char["ai_actor"] = char_data.get("ai_actor", "")
                    if not char.get("headshot_url"):
                        char["headshot_url"] = char_data.get("headshot_url", "")

    # ============================================================
    # PHASE 6: Add UI metadata flags
    # ============================================================
    story_bible["_ui_enforced"] = True
    story_bible["_ui_enforced_version"] = "v17"

    # Save enriched story_bible
    with open(story_bible_path, "w") as f:
        json.dump(story_bible, f, indent=2)

    return {
        "agent": "ui_consistency_enforcer",
        "state": "COMPLETE",
        "facts": {
            "scenes_enriched": scenes_enriched,
            "beats_created": beats_created,
            "dialogue_extracted": dialogue_extracted,
            "locations_added": locations_added,
            "total_scenes": len(story_bible.get("scenes", [])),
            "total_beats": sum(len(s.get("beats", [])) for s in story_bible.get("scenes", []))
        }
    }


def validate_ui_consistency(project: str, repo_root: Path = None) -> dict:
    """
    Validate that a project has consistent UI data structure.
    Returns issues found without modifying data.
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent.parent

    repo_root = Path(repo_root)
    project_path = repo_root / "pipeline_outputs" / project

    story_bible_path = project_path / "story_bible.json"
    shot_plan_path = project_path / "shot_plan.json"

    issues = []

    if not shot_plan_path.exists():
        issues.append("missing_shot_plan")
        return {"valid": False, "issues": issues}

    if not story_bible_path.exists():
        issues.append("missing_story_bible")
    else:
        with open(story_bible_path) as f:
            story_bible = json.load(f)

        # Check scenes
        scenes = story_bible.get("scenes", [])
        if not scenes:
            issues.append("no_scenes")
        else:
            scenes_without_beats = [s for s in scenes if not s.get("beats")]
            if scenes_without_beats:
                issues.append(f"scenes_without_beats:{len(scenes_without_beats)}")

            scenes_without_location = [s for s in scenes if not s.get("location")]
            if scenes_without_location:
                issues.append(f"scenes_without_location:{len(scenes_without_location)}")

        # Check locations
        if not story_bible.get("locations"):
            issues.append("no_locations_array")

        # Check characters
        if not story_bible.get("characters"):
            issues.append("no_characters_array")

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "kord_v17"

    print(f"=== VALIDATING {project} ===")
    validation = validate_ui_consistency(project)
    print(json.dumps(validation, indent=2))

    if not validation["valid"]:
        print(f"\n=== ENFORCING UI CONSISTENCY ON {project} ===")
        result = run_ui_consistency_enforcer(project)
        print(json.dumps(result, indent=2))
