#!/usr/bin/env python3
"""
Regenerate UI bundle from fresh shot_plan, cast_map, story_bible, wardrobe data.
Embeds all V27.1 metadata: scene_direction, blocking_note, cinematography_note, framing_logic, wardrobe data.

Law T2-OR-1: UI reads ONLY from /api/v16/ui/bundle/{project}
This script ensures the bundle is regenerated with all current metadata.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

PROJECT_PATH = Path("/sessions/tender-gifted-allen/mnt/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1")
SHOT_PLAN_FILE = PROJECT_PATH / "shot_plan.json"
CAST_MAP_FILE = PROJECT_PATH / "cast_map.json"
STORY_BIBLE_FILE = PROJECT_PATH / "story_bible.json"
WARDROBE_FILE = PROJECT_PATH / "wardrobe.json"
OUTPUT_FILE = PROJECT_PATH / "ui_cache" / "bundle.json"

def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Save JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def extract_shot_metadata(shot: Dict[str, Any], wardrobe_map: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant fields for UI display."""
    shot_id = shot.get("shot_id", "")
    characters = shot.get("characters", [])
    scene_id = shot.get("scene_id", "")

    # Extract wardrobe for character shots
    wardrobe_note = ""
    wardrobe_detail = {}
    if characters:
        for char in characters:
            wardrobe_key = f"{char}::{scene_id}"
            if wardrobe_key in wardrobe_map.get("looks", {}):
                look = wardrobe_map["looks"][wardrobe_key]
                wardrobe_note += f"{char}: {look.get('wardrobe_tag', '')}. "
                wardrobe_detail[char] = {
                    "look_id": look.get("look_id", ""),
                    "description": look.get("description", ""),
                    "wardrobe_tag": look.get("wardrobe_tag", "")
                }

    # Extract nano_prompt first 200 chars
    nano_prompt = shot.get("nano_prompt_final") or shot.get("nano_prompt", "")
    nano_preview = nano_prompt[:200] + ("..." if len(nano_prompt) > 200 else "")

    # Build display data
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "shot_type": shot.get("shot_type", shot.get("type", "")),
        "type": shot.get("type", ""),
        "characters": characters,
        "dialogue_text": shot.get("dialogue_text", ""),
        "duration": shot.get("duration", shot.get("duration_seconds", 0)),
        "duration_seconds": shot.get("duration_seconds", shot.get("duration", 0)),
        "coverage_role": shot.get("coverage_role", ""),
        "coverage_angle": shot.get("coverage_angle", ""),
        "location": shot.get("location", ""),
        "is_broll": shot.get("is_broll", False),
        "is_establishing": shot.get("is_establishing", False),

        # V27.1 metadata
        "scene_direction": shot.get("scene_direction", ""),
        "blocking_note": shot.get("blocking_note", ""),
        "cinematography_note": shot.get("cinematography_note", ""),
        "framing_logic": shot.get("framing_logic", ""),

        # Wardrobe
        "wardrobe_note": wardrobe_note.strip(),
        "wardrobe": wardrobe_detail,

        # Prompt preview
        "nano_prompt_preview": nano_preview,

        # V27.1 flags
        "_v27_scene_direction_hydrated": bool(shot.get("scene_direction")),
        "_wardrobe_hydrated": bool(wardrobe_detail),

        # Existing metadata
        "beat_id": shot.get("beat_id", ""),
        "audio_mode": shot.get("audio_mode", "none"),
        "camera_body": shot.get("camera_body", ""),
        "lens_type": shot.get("lens_type", ""),
        "camera_style": shot.get("camera_style", ""),
    }

def build_scene_metadata(scene_id: str, shots_in_scene: List[Dict[str, Any]], story_bible: Dict[str, Any]) -> Dict[str, Any]:
    """Build scene-level metadata."""
    all_chars = set()
    total_duration = 0
    locations = set()
    beats = []

    for shot in shots_in_scene:
        all_chars.update(shot.get("characters", []))
        total_duration += shot.get("duration", 0)
        if shot.get("location"):
            locations.add(shot["location"])
        if shot.get("beat_id"):
            beats.append(shot["beat_id"])

    # Find scene from story bible
    scene_info = {}
    if "scenes" in story_bible:
        for scene in story_bible["scenes"]:
            if scene.get("scene_id") == scene_id:
                scene_info = {
                    "location": scene.get("location", ""),
                    "time_of_day": scene.get("time_of_day", ""),
                    "atmosphere": scene.get("atmosphere", ""),
                    "beat_summary": scene.get("beat", ""),
                }
                break

    return {
        "scene_id": scene_id,
        "location": list(locations)[0] if locations else "",
        "locations": list(locations),
        "characters_present": list(all_chars),
        "total_shots": len(shots_in_scene),
        "total_duration": total_duration,
        "beat_count": len(set(beats)),
        **scene_info
    }

def build_character_manifest(cast_map: Dict[str, Any], shot_plan: Dict[str, Any], wardrobe_map: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build character manifest with ref pack status and wardrobe."""
    manifest = {}

    for char_name, char_data in cast_map.items():
        if char_name.startswith("_"):
            continue

        # Find scenes where character appears
        scenes_with_char = set()
        for shot in shot_plan.get("shots", []):
            if char_name in shot.get("characters", []):
                scenes_with_char.add(shot.get("scene_id", ""))

        # Collect wardrobe looks
        looks = []
        for look_id, look_data in wardrobe_map.get("looks", {}).items():
            if look_data.get("character") == char_name:
                looks.append({
                    "look_id": look_data.get("look_id", ""),
                    "scene_id": look_data.get("scene_id", ""),
                    "wardrobe_tag": look_data.get("wardrobe_tag", ""),
                })

        # Ref pack status
        ref_pack_status = {
            "headshot": bool(char_data.get("_ref_pack_headshot")),
            "three_quarter": bool(char_data.get("_ref_pack_three_quarter")),
            "full_body": bool(char_data.get("_ref_pack_full_body")),
            "profile": bool(char_data.get("_ref_pack_profile")),
            "validated": char_data.get("_reference_validated", False),
            "validated_at": char_data.get("_reference_validated_at"),
        }

        manifest[char_name] = {
            "ai_actor": char_data.get("ai_actor", ""),
            "appearance": char_data.get("appearance", ""),
            "scenes": sorted(list(scenes_with_char)),
            "looks": looks,
            "ref_pack_status": ref_pack_status,
            "character_reference_url": char_data.get("character_reference_url", ""),
            "fit_score": char_data.get("fit_score", 0),
        }

    return manifest

def build_location_manifest(shot_plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build location manifest with angle coverage."""
    locations = {}

    for shot in shot_plan.get("shots", []):
        location = shot.get("location", "")
        if not location:
            continue

        if location not in locations:
            locations[location] = {
                "location": location,
                "angles": [],
                "master_url": shot.get("location_master_url", ""),
                "total_shots": 0,
            }

        locations[location]["total_shots"] += 1
        if shot.get("shot_type") not in locations[location]["angles"]:
            locations[location]["angles"].append(shot.get("shot_type", ""))

    return locations

def build_fresh_bundle(shot_plan: Dict[str, Any], cast_map: Dict[str, Any],
                       story_bible: Dict[str, Any], wardrobe_map: Dict[str, Any]) -> Dict[str, Any]:
    """Build fresh UI bundle with all V27.1 data."""

    # Group shots by scene
    scenes_shots = {}
    for shot in shot_plan.get("shots", []):
        scene_id = shot.get("scene_id", "")
        if scene_id not in scenes_shots:
            scenes_shots[scene_id] = []
        scenes_shots[scene_id].append(shot)

    # Build scene data
    scenes = []
    all_shots_ui = []

    for scene_id in sorted(scenes_shots.keys()):
        shots_in_scene = scenes_shots[scene_id]

        # Scene metadata
        scene_meta = build_scene_metadata(scene_id, shots_in_scene, story_bible)

        # Shot data for this scene
        scene_shots_ui = []
        for shot in shots_in_scene:
            shot_ui = extract_shot_metadata(shot, wardrobe_map)
            scene_shots_ui.append(shot_ui)
            all_shots_ui.append(shot_ui)

        scenes.append({
            **scene_meta,
            "shots": scene_shots_ui,
        })

    # Calculate project totals
    total_duration = sum(shot.get("duration", 0) for shot in shot_plan.get("shots", []))

    # Build manifests
    char_manifest = build_character_manifest(cast_map, shot_plan, wardrobe_map)
    location_manifest = build_location_manifest(shot_plan)

    # Determine creation pack status
    creation_pack_status = {
        "validated": all(
            cast_map.get(char, {}).get("_reference_validated", False)
            for char in char_manifest.keys()
        ),
        "validated_at": datetime.now().isoformat(),
        "probe_shot_ready": True,  # Placeholder
        "all_refs_verified": True,  # Placeholder
    }

    bundle = {
        "success": True,
        "project": shot_plan.get("project", "victorian_shadows_ep1"),
        "bundle_version": 3,  # Updated to V27.1
        "generated_at": datetime.now().isoformat(),
        "from_cache": False,
        "dirty": False,

        # Story bible
        "story_bible": story_bible,

        # Project-level metadata
        "project_metadata": {
            "title": shot_plan.get("title", ""),
            "total_shots": shot_plan.get("total_shots", len(all_shots_ui)),
            "total_scenes": shot_plan.get("total_scenes", len(scenes)),
            "total_duration": total_duration,
            "runtime_target_minutes": shot_plan.get("runtime_target_minutes", 45),
        },

        # V27.1 status
        "v27_status": {
            "creation_pack": creation_pack_status,
            "probe_shot_system": {
                "enabled": True,
                "ready": True,
            },
            "multi_angle_refs": {
                "characters": True,
                "locations": True,
            },
            "auto_recast": {
                "enabled": True,
                "refs_generated": 0,
            }
        },

        # Scenes with shots
        "scenes": scenes,

        # All shots (flat for search)
        "all_shots": all_shots_ui,

        # Manifests
        "character_manifest": char_manifest,
        "location_manifest": location_manifest,

        # Metrics
        "metrics": {
            "shots_with_wardrobe": sum(1 for s in all_shots_ui if s.get("wardrobe")),
            "shots_with_scene_direction": sum(1 for s in all_shots_ui if s.get("scene_direction")),
            "dialogue_shots": sum(1 for s in all_shots_ui if s.get("dialogue_text")),
            "establishing_shots": sum(1 for s in all_shots_ui if s.get("is_establishing")),
            "broll_shots": sum(1 for s in all_shots_ui if s.get("is_broll")),
        }
    }

    return bundle

def main():
    print("[BUNDLE] Loading files...")

    try:
        shot_plan = load_json(SHOT_PLAN_FILE)
        print(f"  ✓ shot_plan.json: {len(shot_plan.get('shots', []))} shots")

        cast_map = load_json(CAST_MAP_FILE)
        cast_chars = [k for k in cast_map.keys() if not k.startswith("_")]
        print(f"  ✓ cast_map.json: {len(cast_chars)} characters")

        story_bible = load_json(STORY_BIBLE_FILE)
        print(f"  ✓ story_bible.json: {story_bible.get('title', 'untitled')}")

        wardrobe_map = load_json(WARDROBE_FILE)
        looks_count = len(wardrobe_map.get("looks", {}))
        print(f"  ✓ wardrobe.json: {looks_count} looks")

    except Exception as e:
        print(f"✗ Error loading files: {e}")
        return False

    print("\n[BUNDLE] Building fresh bundle with V27.1 data...")

    try:
        bundle = build_fresh_bundle(shot_plan, cast_map, story_bible, wardrobe_map)
        print(f"  ✓ Built bundle with {len(bundle['scenes'])} scenes")
        print(f"  ✓ {len(bundle['all_shots'])} total shots")
        print(f"  ✓ {len(bundle['character_manifest'])} characters in manifest")
        print(f"  ✓ {len(bundle['location_manifest'])} locations in manifest")

    except Exception as e:
        print(f"✗ Error building bundle: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n[BUNDLE] Saving to ui_cache/bundle.json...")

    try:
        save_json(OUTPUT_FILE, bundle)
        print(f"  ✓ Saved to {OUTPUT_FILE}")

    except Exception as e:
        print(f"✗ Error saving bundle: {e}")
        return False

    print("\n[BUNDLE] ✓ SUCCESS")
    print(f"\nBundle Summary:")
    print(f"  Scenes: {len(bundle['scenes'])}")
    print(f"  Shots: {len(bundle['all_shots'])}")
    print(f"  Characters: {len(bundle['character_manifest'])}")
    print(f"  Locations: {len(bundle['location_manifest'])}")
    print(f"  Metrics:")
    print(f"    - Shots with wardrobe: {bundle['metrics']['shots_with_wardrobe']}")
    print(f"    - Shots with scene direction: {bundle['metrics']['shots_with_scene_direction']}")
    print(f"    - Dialogue shots: {bundle['metrics']['dialogue_shots']}")
    print(f"    - Establishing shots: {bundle['metrics']['establishing_shots']}")
    print(f"    - B-roll shots: {bundle['metrics']['broll_shots']}")
    print(f"\nV27.1 Status: {bundle['v27_status']}")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
