#!/usr/bin/env python3
"""
ATLAS V27.1 — Batch Enricher
=============================
Enriches ALL unenriched shots with:
  1. _dp_ref_selection (DP framing standards → best ref angle per shot type)
  2. _fal_image_urls_resolved (actual file paths for FAL image_urls)
  3. dialogue_performance (physical performance direction for dialogue shots)
  4. Dialogue marker deduplication

This is the same enrichment that was manually applied to Scene 001,
now automated for all remaining scenes.

Usage:
    python3 tools/batch_enricher.py [project_path]
"""

import json
import os
import sys
import re
import glob
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# DP Framing Standards: shot_type → ideal ref angles
SHOT_TYPE_REF_MAP = {
    "establishing": {"char_angle": None, "loc_angle": "wide_exterior", "lens": "16-24mm", "notes": "No character refs for establishing"},
    "wide": {"char_angle": "full_body", "loc_angle": "wide_interior", "lens": "24-35mm", "notes": "Full body for wide coverage"},
    "medium": {"char_angle": "three_quarter", "loc_angle": "medium_interior", "lens": "50mm", "notes": "Standard coverage"},
    "medium_close_up": {"char_angle": "three_quarter", "loc_angle": "medium_interior", "lens": "50-65mm", "notes": "Tighter framing"},
    "close_up": {"char_angle": "headshot", "loc_angle": None, "lens": "85-105mm", "notes": "Face detail, no location ref needed"},
    "extreme_close_up": {"char_angle": "headshot", "loc_angle": None, "lens": "105-135mm", "notes": "Maximum face detail"},
    "over_the_shoulder": {"char_angle": "three_quarter", "loc_angle": "reverse_angle", "lens": "75-85mm", "notes": "OTS needs reverse angle for depth"},
    "two_shot": {"char_angle": "three_quarter", "loc_angle": "medium_interior", "lens": "35-50mm", "notes": "Both characters visible"},
    "insert": {"char_angle": None, "loc_angle": "detail_insert", "lens": "85-105mm", "notes": "Detail/prop shot"},
    "reaction": {"char_angle": "headshot", "loc_angle": None, "lens": "85mm", "notes": "Face reaction"},
    "master": {"char_angle": "full_body", "loc_angle": "wide_interior", "lens": "24-35mm", "notes": "Master shot coverage"},
}

# CPC Emotion → Physical Direction (from T2-CPC-4)
EMOTION_PHYSICAL_MAP = {
    "anger": {"standing": "fists clench at sides, jaw tightens", "sitting": "grips armrest, leans forward aggressively"},
    "grief": {"standing": "shoulders drop, hand covers mouth", "sitting": "slumps forward, head bows"},
    "fear": {"standing": "steps backward, arms cross defensively", "sitting": "presses back into chair, grips seat edge"},
    "determination": {"standing": "squares shoulders, lifts chin", "sitting": "plants hands on table, straightens spine"},
    "suspicion": {"standing": "narrows eyes, tilts head slightly", "sitting": "leans back, crosses arms slowly"},
    "resentment": {"standing": "jaw clenches, turns partially away", "sitting": "grips knee, looks away then back"},
    "curiosity": {"standing": "leans forward slightly, head tilts", "sitting": "edges forward in seat, eyes widen"},
    "tenderness": {"standing": "reaches toward other person, softens posture", "sitting": "turns body toward other, hand extends"},
    "authority": {"standing": "feet planted wide, hands behind back", "sitting": "fingers steepled, chin level"},
    "defiance": {"standing": "chin up, feet planted, arms crossed", "sitting": "leans back, one arm draped casually"},
    "vulnerability": {"standing": "arms wrap around self, shoulders curl", "sitting": "hunches forward, hands clasped between knees"},
    "shock": {"standing": "freezes mid-step, hand rises to chest", "sitting": "jerks upright, hands grip armrests"},
}


def find_char_ref(project_path, char_name, angle="headshot"):
    """Find the best character reference file for a given angle."""
    char_key = char_name.replace(" ", "_")
    lib_path = os.path.join(project_path, "character_library_locked")

    # Priority order for finding refs
    if angle == "headshot":
        patterns = [f"{char_key}_CHAR_REFERENCE.jpg", f"{char_key}_headshot.jpg", f"{char_key}*.jpg"]
    elif angle == "three_quarter":
        patterns = [f"{char_key}_three_quarter.jpg", f"{char_key}_CHAR_REFERENCE.jpg", f"{char_key}*.jpg"]
    elif angle == "full_body":
        patterns = [f"{char_key}_full_body.jpg", f"{char_key}_three_quarter.jpg", f"{char_key}_CHAR_REFERENCE.jpg"]
    elif angle == "profile":
        patterns = [f"{char_key}_profile.jpg", f"{char_key}_three_quarter.jpg", f"{char_key}_CHAR_REFERENCE.jpg"]
    else:
        patterns = [f"{char_key}_CHAR_REFERENCE.jpg", f"{char_key}*.jpg"]

    for pattern in patterns:
        matches = glob.glob(os.path.join(lib_path, pattern))
        if matches:
            return matches[0]
    return None


def find_location_ref(project_path, shot, angle="wide_interior"):
    """Find location master for a shot."""
    loc_path = os.path.join(project_path, "location_masters")

    # Get scene location from shot
    location = shot.get("location", shot.get("scene_location", ""))
    scene_id = shot.get("scene_id", "")

    # Normalize location name for file matching
    loc_key = location.replace(" ", "_").replace("-", "_").replace("'", "").upper()
    loc_key_clean = re.sub(r'[^A-Z0-9_]', '', loc_key)

    # Search patterns
    if angle == "reverse_angle":
        patterns = [f"*{loc_key_clean}*reverse*", f"*{scene_id}*reverse*", f"*reverse*"]
    elif angle == "wide_exterior":
        patterns = [f"*{loc_key_clean}*exterior*", f"*{loc_key_clean}*wide*", f"*{loc_key_clean}*master*"]
    elif angle == "medium_interior":
        patterns = [f"*{loc_key_clean}*medium*", f"*{loc_key_clean}*interior*", f"*{loc_key_clean}*.jpg"]
    elif angle == "detail_insert":
        patterns = [f"*{loc_key_clean}*detail*", f"*{loc_key_clean}*insert*", f"*{loc_key_clean}*.jpg"]
    else:
        patterns = [f"*{loc_key_clean}*.jpg", f"*{scene_id}*master*"]

    for pattern in patterns:
        matches = glob.glob(os.path.join(loc_path, pattern))
        if matches:
            return matches[0]

    # Fallback: any location master for this scene
    scene_masters = glob.glob(os.path.join(loc_path, f"*{scene_id}*"))
    if scene_masters:
        return scene_masters[0]

    # Broader fallback: any matching location name
    all_masters = glob.glob(os.path.join(loc_path, "*.jpg"))
    for m in all_masters:
        if loc_key_clean[:10] in os.path.basename(m).upper():
            return m

    return None


def build_dialogue_performance(shot, cast_map):
    """
    Build dialogue performance direction for a dialogue shot (T2-FE-13).
    Includes physical descriptions + performance verbs + actions.
    """
    dialogue = shot.get("dialogue_text", "")
    if not dialogue:
        return ""

    characters = shot.get("characters") or []
    if not characters:
        return ""

    # Parse which character is speaking
    speaker = None
    for char in characters:
        if char.upper() in dialogue.upper():
            speaker = char
            break
    if not speaker:
        speaker = characters[0]

    # Get character appearance
    char_data = cast_map.get(speaker, {})
    appearance = char_data.get("appearance", "")

    # Get emotional context
    beat = shot.get("beat", shot.get("emotional_beat", ""))
    emotion = beat.lower() if beat else "determination"

    # Map to physical direction
    posture = "standing"  # default
    shot_type = (shot.get("shot_type") or "").lower()
    if "sitting" in (shot.get("description", "") + shot.get("action", "")).lower():
        posture = "sitting"

    # Get physical direction from CPC
    physical = EMOTION_PHYSICAL_MAP.get(emotion, {}).get(
        posture, "controlled intensity, weight of emotion visible in posture"
    )

    # Performance verb (not generic "speaks")
    PERF_VERBS = {
        "anger": "confronts", "grief": "murmurs", "fear": "whispers urgently",
        "determination": "declares", "suspicion": "questions pointedly",
        "resentment": "delivers with restrained bitterness", "curiosity": "inquires",
        "tenderness": "says softly", "authority": "commands", "defiance": "protests",
        "vulnerability": "confesses", "shock": "stammers",
    }
    verb = PERF_VERBS.get(emotion, "delivers")

    # Build performance direction
    parts = [f"{speaker} faces camera and {verb}"]
    if physical:
        parts.append(physical)
    if appearance:
        # Add key appearance details
        parts.append(f"({appearance[:80]})")

    # OTS-specific direction
    if shot_type == "over_the_shoulder" and len(characters) > 1:
        listener = [c for c in characters if c != speaker][0]
        parts.append(f"A-ANGLE: {speaker} faces camera (speaker), {listener} back-to-camera (listener)")

    return ". ".join(parts)


def dedup_dialogue_markers(text):
    """Remove stacked duplicate dialogue markers from enrichment pipeline."""
    if not text:
        return text
    # Remove repeated "character speaks:" blocks
    text = re.sub(r'(character speaks:.*?)(\1)+', r'\1', text, flags=re.IGNORECASE)
    # Remove repeated PERFORMANCE MANDATORY blocks
    text = re.sub(r'(PERFORMANCE MANDATORY:.*?)(\1)+', r'\1', text, flags=re.IGNORECASE)
    return text


def enrich_shot(shot, cast_map, project_path):
    """Enrich a single shot with DP ref selection + FAL URLs + dialogue performance."""
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()

    # Normalize shot_type
    type_map = {
        "broll": "insert", "b-roll": "insert", "cutaway": "insert",
        "detail": "insert", "mcu": "medium_close_up", "ecu": "extreme_close_up",
        "cu": "close_up", "ots": "over_the_shoulder", "ms": "medium",
    }
    shot_type_norm = type_map.get(shot_type, shot_type)

    # Get DP spec
    dp_spec = SHOT_TYPE_REF_MAP.get(shot_type_norm, SHOT_TYPE_REF_MAP["medium"])

    # Build ref selection
    dp_selection = {"dp_spec": dp_spec, "char_refs": {}, "location_ref": None}
    fal_urls = []

    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    # Character refs
    if dp_spec.get("char_angle") and characters:
        for char_name in characters:
            ref_path = find_char_ref(project_path, char_name, dp_spec["char_angle"])
            if ref_path:
                dp_selection["char_refs"][char_name] = {
                    "angle": dp_spec["char_angle"],
                    "path": ref_path,
                }
                fal_urls.append(ref_path)

    # Location ref
    loc_angle = dp_spec.get("loc_angle")
    if loc_angle:
        loc_path = find_location_ref(project_path, shot, loc_angle)
        if loc_path:
            dp_selection["location_ref"] = {
                "angle": loc_angle,
                "path": loc_path,
            }
            fal_urls.append(loc_path)

    shot["_dp_ref_selection"] = dp_selection
    shot["_fal_image_urls_resolved"] = fal_urls

    # Dialogue performance enrichment
    if shot.get("dialogue_text") and not shot.get("dialogue_performance"):
        perf = build_dialogue_performance(shot, cast_map)
        if perf:
            shot["dialogue_performance"] = perf

    # Dedup dialogue markers in ltx_motion_prompt
    if shot.get("ltx_motion_prompt"):
        shot["ltx_motion_prompt"] = dedup_dialogue_markers(shot["ltx_motion_prompt"])

    return shot


def enrich_project(project_path="pipeline_outputs/victorian_shadows_ep1"):
    """Enrich all unenriched shots across all scenes."""
    sp_path = os.path.join(project_path, "shot_plan.json")
    sp = json.load(open(sp_path))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    cm = json.load(open(os.path.join(project_path, "cast_map.json")))

    enriched_count = 0
    already_count = 0
    failed_count = 0

    for shot in shots:
        if shot.get("_dp_ref_selection") and shot.get("_fal_image_urls_resolved"):
            already_count += 1
            continue

        try:
            enrich_shot(shot, cm, project_path)
            enriched_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to enrich {shot.get('shot_id')}: {e}")

    # Save
    with open(sp_path, "w") as f:
        json.dump(shots, f, indent=2)

    return {
        "total_shots": len(shots),
        "already_enriched": already_count,
        "newly_enriched": enriched_count,
        "failed": failed_count,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    result = enrich_project(project)
    print(json.dumps(result, indent=2))

    # Verify
    sp = json.load(open(os.path.join(project, "shot_plan.json")))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    scenes = {}
    for s in shots:
        sid = s.get("scene_id", "?")
        scenes.setdefault(sid, []).append(s)

    print("\nPer-scene enrichment status:")
    for sid, sc_shots in sorted(scenes.items()):
        enriched = sum(1 for s in sc_shots if s.get("_dp_ref_selection"))
        fal = sum(1 for s in sc_shots if s.get("_fal_image_urls_resolved"))
        perf = sum(1 for s in sc_shots if s.get("dialogue_performance"))
        dialogue = sum(1 for s in sc_shots if s.get("dialogue_text"))
        print(f"  Scene {sid}: {enriched}/{len(sc_shots)} DP | {fal}/{len(sc_shots)} FAL | {perf}/{dialogue} dialogue_perf")
