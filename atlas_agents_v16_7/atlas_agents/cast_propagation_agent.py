"""
CAST PROPAGATION AGENT - V17

Makes casting structurally complete and irreversible.

Fixes:
1. cast_map.json entries missing reference_url
2. shot_plan.json shots with empty characters[] arrays

Rules:
- Casting truth lives in cast_map.json
- Shot execution truth lives in shot_plan.json
- UI must never infer or guess characters
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def run_cast_propagation(project: str, repo_root: Path = None) -> dict:
    """
    Fix casting and propagation for a project.

    Returns:
        {
            "agent": "cast_propagation",
            "state": "COMPLETE",
            "facts": {
                "cast_entries_fixed": N,
                "shots_fixed": N,
                "extras_pools": N
            }
        }
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent.parent

    repo_root = Path(repo_root)
    project_path = repo_root / "pipeline_outputs" / project

    cast_map_path = project_path / "cast_map.json"
    shot_plan_path = project_path / "shot_plan.json"
    story_bible_path = project_path / "story_bible.json"

    if not shot_plan_path.exists():
        return {"agent": "cast_propagation", "state": "FAILED", "error": "No shot_plan.json"}

    # Load AI actors library for reference URLs
    actors_lib_path = repo_root / "ai_actors_library.json"
    actor_refs = {}
    if actors_lib_path.exists():
        with open(actors_lib_path) as f:
            lib = json.load(f)
        for actor in lib.get("actors", []):
            name = actor.get("name", "")
            ref = actor.get("locked_reference_url") or actor.get("headshot_url")
            if name and ref:
                actor_refs[name] = ref

    # ============================================================
    # PHASE 1: Fix cast_map reference_url
    # ============================================================
    cast_entries_fixed = 0
    extras_pools = 0

    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)
    else:
        cast_map = {}

    for char_name, char_data in cast_map.items():
        if char_name.startswith("_"):
            continue
        if not isinstance(char_data, dict):
            continue

        # Check if it's an extras pool
        is_extras = any(kw in char_name.upper() for kw in
                       ["DWARVES", "ELVES", "COUNCIL", "CROWD", "MEMBERS",
                        "VILLAGERS", "GUARDS", "SOLDIERS", "ALL ", "GROUP"])

        if is_extras:
            char_data["is_extras_pool"] = True
            extras_pools += 1
        else:
            char_data["is_extras_pool"] = False

        # Fix missing reference_url
        if not char_data.get("reference_url"):
            ai_actor = char_data.get("ai_actor", "")
            if ai_actor and ai_actor in actor_refs:
                char_data["reference_url"] = actor_refs[ai_actor]
                char_data["headshot_url"] = actor_refs[ai_actor]
                cast_entries_fixed += 1

    # Save fixed cast_map
    with open(cast_map_path, "w") as f:
        json.dump(cast_map, f, indent=2)

    # ============================================================
    # PHASE 2: Build scene→characters mapping from story_bible
    # ============================================================
    scene_characters = {}

    if story_bible_path.exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)

        # Try to get characters from scenes
        for scene in story_bible.get("scenes", []):
            scene_id = str(scene.get("scene_id", scene.get("id", ""))).zfill(3)

            chars = set()

            # From scene.characters
            for c in scene.get("characters", []):
                if isinstance(c, dict):
                    chars.add(c.get("name", "").upper())
                else:
                    chars.add(str(c).upper())

            # From beats
            for beat in scene.get("beats", []):
                if isinstance(beat, dict):
                    for c in beat.get("characters", []):
                        if isinstance(c, dict):
                            chars.add(c.get("name", "").upper())
                        else:
                            chars.add(str(c).upper())
                    # From dialogue speaker
                    dialogue = beat.get("dialogue", "")
                    if dialogue:
                        match = re.match(r"([A-Z][A-Z\s]+):", dialogue)
                        if match:
                            chars.add(match.group(1).strip())

            if chars:
                scene_characters[scene_id] = list(chars)

    # ============================================================
    # PHASE 3: Propagate characters to shots
    # ============================================================
    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots_fixed = 0
    cast_char_names = [k.upper() for k in cast_map.keys() if not k.startswith("_")]

    for shot in shot_plan.get("shots", []):
        shot_id = shot.get("shot_id", "")
        scene_id = shot.get("scene_id", "")

        current_chars = shot.get("characters", [])

        # If empty, try to populate
        if not current_chars:
            inferred_chars = []

            # Method 1: From scene_characters mapping
            if scene_id in scene_characters:
                inferred_chars = scene_characters[scene_id]

            # Method 2: From nano_prompt - find character names
            if not inferred_chars:
                prompt = ((shot.get("nano_prompt") or "") + " " +
                         (shot.get("description") or "") + " " +
                         (shot.get("dialogue") or "")).upper()
                for cn in cast_char_names:
                    if cn and len(cn) > 2 and cn in prompt:
                        inferred_chars.append(cn)

            # Method 3: If still empty, use first non-extras character
            if not inferred_chars:
                for cn, cd in cast_map.items():
                    if cn.startswith("_"):
                        continue
                    if isinstance(cd, dict) and not cd.get("is_extras_pool"):
                        inferred_chars = [cn]
                        break

            if inferred_chars:
                shot["characters"] = inferred_chars
                shots_fixed += 1

        # Build ai_actor_cast for this shot
        ai_actor_cast = {}
        for char in shot.get("characters", []):
            char_upper = char.upper() if isinstance(char, str) else char
            if char_upper in cast_map:
                cd = cast_map[char_upper]
                if isinstance(cd, dict):
                    ai_actor_cast[char_upper] = {
                        "ai_actor": cd.get("ai_actor"),
                        "reference_url": cd.get("reference_url"),
                        "headshot_url": cd.get("headshot_url"),
                        "is_extras_pool": cd.get("is_extras_pool", False)
                    }

        if ai_actor_cast:
            shot["ai_actor_cast"] = ai_actor_cast
            # Set primary character reference for generation
            first_char = shot["characters"][0] if shot.get("characters") else None
            if first_char and first_char.upper() in ai_actor_cast:
                shot["character_reference_url"] = ai_actor_cast[first_char.upper()].get("reference_url")

    # Save fixed shot_plan
    with open(shot_plan_path, "w") as f:
        json.dump(shot_plan, f, indent=2)

    return {
        "agent": "cast_propagation",
        "state": "COMPLETE",
        "facts": {
            "cast_entries_fixed": cast_entries_fixed,
            "shots_fixed": shots_fixed,
            "extras_pools": extras_pools,
            "total_shots": len(shot_plan.get("shots", []))
        }
    }


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "kord_v17"
    result = run_cast_propagation(project)
    print(json.dumps(result, indent=2))
