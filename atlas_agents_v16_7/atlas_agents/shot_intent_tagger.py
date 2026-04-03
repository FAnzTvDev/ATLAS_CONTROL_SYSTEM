"""
ATLAS V18.3 — Shot Intent Tagger
=================================
Fills the 4 missing intent fields on every shot:
  1. purpose       — WHY this shot exists (ESTABLISH, REVEAL, TENSION, COMFORT, TRANSITION, etc.)
  2. coverage_role  — WHAT camera role it plays (A_MASTER, B_CLOSE, C_INSERT, OTS_LEFT, OTS_RIGHT, REACTION, CUTAWAY)
  3. wardrobe_lock  — PER-CHARACTER wardrobe state key for continuity enforcement
  4. expected_elements — WHAT must be visible in the frame for the shot to "pass"

Sources of truth (in priority order):
  - Story bible beats (beat_type, description, dialogue, characters, emotional_tone)
  - Existing shot metadata (intent_tags, blocking_role, shot_role, _narrative, emotional_beat)
  - Character data from cast_map (wardrobe, appearance)
  - Scene context (location, time_of_day, int_ext)

This module is DETERMINISTIC — no LLM calls. Pure rule-based inference.
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("atlas.intent_tagger")

# ─────────────────────────────────────────────────────
# PURPOSE MAPPING — intent_tags + beat_type → purpose
# ─────────────────────────────────────────────────────

# Maps (intent_tag, beat_type, shot_role) → purpose
PURPOSE_RULES = [
    # Direct intent_tag matches (highest priority)
    ({"intent_tags": "establish"},      "ESTABLISH"),
    ({"intent_tags": "reveal"},         "REVEAL"),
    ({"intent_tags": "tension"},        "TENSION"),
    ({"intent_tags": "confrontation"},  "CONFRONTATION"),
    ({"intent_tags": "climax"},         "CLIMAX"),
    ({"intent_tags": "resolution"},     "RESOLUTION"),
    ({"intent_tags": "dialogue"},       "DIALOGUE"),
    ({"intent_tags": "atmosphere"},     "ATMOSPHERE"),
    ({"intent_tags": "despair"},        "EMOTION"),
    ({"intent_tags": "defeat"},         "EMOTION"),
    ({"intent_tags": "resolve"},        "EMOTION"),
    ({"intent_tags": "decision"},       "DECISION"),
    ({"intent_tags": "reversal"},       "REVERSAL"),
    ({"intent_tags": "shift"},          "TRANSITION"),
    ({"intent_tags": "threat"},         "THREAT"),
    ({"intent_tags": "escalation"},     "ESCALATION"),
    ({"intent_tags": "narrative"},      "NARRATIVE"),

    # Shot role fallbacks
    ({"shot_role": "establishing"},     "ESTABLISH"),
    ({"shot_role": "b-roll"},           "ATMOSPHERE"),
    ({"shot_role": "transition"},       "TRANSITION"),
    ({"shot_role": "insert"},           "INSERT"),
    ({"shot_role": "reaction"},         "REACTION"),
]

# ─────────────────────────────────────────────────────
# COVERAGE ROLE MAPPING — shot_type + blocking_role → coverage_role
# ─────────────────────────────────────────────────────

COVERAGE_ROLE_MAP = {
    # (shot_type, blocking_role) → coverage_role
    ("establishing", "master"):     "A_MASTER",
    ("wide", "master"):             "A_MASTER",
    ("wide", "establishing"):       "A_MASTER",
    ("medium", "master"):           "B_MEDIUM",
    ("medium", "single"):           "B_MEDIUM",
    ("medium", "two_shot"):         "B_TWO_SHOT",
    ("close-up", "single"):         "C_CLOSE",
    ("close-up", "master"):         "C_CLOSE",
    ("close-up", "insert"):         "C_INSERT",
    ("extreme_close", "single"):    "C_ECU",
    ("extreme_close", "insert"):    "C_INSERT",
    ("reaction", "reaction"):       "REACTION",
    ("reaction", "single"):         "REACTION",
    ("insert", "insert"):           "C_INSERT",
    ("insert", "cutaway"):          "CUTAWAY",
    ("b-roll", "master"):           "CUTAWAY",
    ("action", "master"):           "A_MASTER",
    ("action", "single"):           "B_MEDIUM",
    ("aerial", "master"):           "A_MASTER",
    ("dialogue", "single"):         "B_MEDIUM",
    ("dialogue", "master"):         "A_MASTER",
    ("dialogue", "two_shot"):       "B_TWO_SHOT",
}

# Fallback by shot_type alone
COVERAGE_FALLBACK = {
    "establishing": "A_MASTER",
    "wide":         "A_MASTER",
    "medium":       "B_MEDIUM",
    "close-up":     "C_CLOSE",
    "extreme_close": "C_ECU",
    "insert":       "C_INSERT",
    "reaction":     "REACTION",
    "b-roll":       "CUTAWAY",
    "action":       "B_MEDIUM",
    "aerial":       "A_MASTER",
    "dialogue":     "B_MEDIUM",
}

# ─────────────────────────────────────────────────────
# EXPECTED ELEMENTS — inferred from beat description + location + characters
# ─────────────────────────────────────────────────────

# Common prop/element keywords to extract from beat descriptions
ELEMENT_PATTERNS = [
    (r'\b(candle|candles)\b', 'candles'),
    (r'\b(altar|stone altar)\b', 'altar'),
    (r'\b(symbol|symbols|carved)\b', 'carved_symbols'),
    (r'\b(book|books|journal|diary)\b', 'book'),
    (r'\b(letter|letters|envelope)\b', 'letter'),
    (r'\b(photo|photograph|picture|portrait)\b', 'photograph'),
    (r'\b(phone|cellphone|mobile)\b', 'phone'),
    (r'\b(laptop|computer|screen|monitor)\b', 'computer'),
    (r'\b(car|vehicle|automobile)\b', 'vehicle'),
    (r'\b(gun|pistol|weapon|knife|blade)\b', 'weapon'),
    (r'\b(door|doorway|entrance)\b', 'door'),
    (r'\b(window|glass|pane)\b', 'window'),
    (r'\b(mirror)\b', 'mirror'),
    (r'\b(ring|necklace|jewelry|pendant|amulet)\b', 'jewelry'),
    (r'\b(file|folder|document|papers|bills)\b', 'documents'),
    (r'\b(desk|table)\b', 'desk'),
    (r'\b(chair|seat|sofa|couch)\b', 'seating'),
    (r'\b(blood|stain)\b', 'blood'),
    (r'\b(rain|storm|lightning|thunder)\b', 'storm'),
    (r'\b(fire|flame|torch)\b', 'fire'),
    (r'\b(painting|artwork|frame)\b', 'artwork'),
    (r'\b(staircase|stairs|steps)\b', 'staircase'),
    (r'\b(hallway|corridor|passage)\b', 'hallway'),
    (r'\b(garden|hedge|tree|vine)\b', 'garden'),
    (r'\b(gate|fence|iron)\b', 'gate'),
    (r'\b(coffin|casket|tomb|grave)\b', 'burial'),
    (r'\b(clock|timepiece|watch)\b', 'clock'),
    (r'\b(key|keys|lockbox)\b', 'key'),
    (r'\b(map|blueprint|floor.?plan)\b', 'map'),
    (r'\b(mask|costume|disguise)\b', 'disguise'),
    (r'\b(food|meal|plate|glass|wine|drink)\b', 'food_drink'),
    (r'\b(bed|pillow|blanket|sheet)\b', 'bed'),
    (r'\b(smoke|fog|mist|haze)\b', 'atmospheric_effect'),
]


def infer_purpose(shot: Dict, beat: Optional[Dict] = None) -> str:
    """
    Infer the shot's PURPOSE from intent_tags, beat_type, shot_role, and narrative role.
    Returns a canonical purpose string.
    """
    intent_tags = shot.get("intent_tags", []) or []
    shot_role = shot.get("shot_role", "")
    narrative = shot.get("_narrative", {}) or {}
    narrative_role = narrative.get("role", "")

    # Priority 1: intent_tags match
    for rule in PURPOSE_RULES:
        condition = rule[0]
        purpose = rule[1]
        if "intent_tags" in condition:
            if condition["intent_tags"] in intent_tags:
                return purpose
        if "shot_role" in condition:
            if condition["shot_role"] == shot_role or condition["shot_role"] == narrative_role:
                return purpose

    # Priority 2: beat_type from story bible
    if beat:
        bt = beat.get("beat_type", "")
        if bt == "establishing":
            return "ESTABLISH"
        elif bt == "dialogue":
            return "DIALOGUE"
        elif bt == "action":
            return "ACTION"
        elif bt == "reaction":
            return "REACTION"
        elif bt == "transition":
            return "TRANSITION"

    # Priority 3: emotional_beat heuristic
    eb = shot.get("emotional_beat", "")
    if "Opening" in eb:
        return "ESTABLISH"
    if "Climax" in eb or "climax" in eb.lower():
        return "CLIMAX"
    if "Resolution" in eb:
        return "RESOLUTION"

    # Default
    return "NARRATIVE"


def infer_coverage_role(shot: Dict) -> str:
    """
    Infer the shot's COVERAGE ROLE (camera designation) from shot_type + blocking_role.
    Returns: A_MASTER, B_MEDIUM, B_TWO_SHOT, C_CLOSE, C_ECU, C_INSERT, REACTION, CUTAWAY, OTS_LEFT, OTS_RIGHT
    """
    shot_type = shot.get("type", shot.get("shot_type", "medium")).lower()
    blocking = shot.get("blocking_role", "").lower()

    # Check screen_direction for OTS detection
    screen_dir = shot.get("screen_direction", "").lower()
    if "ots" in blocking or "over" in blocking:
        if "left" in screen_dir or "left" in blocking:
            return "OTS_LEFT"
        elif "right" in screen_dir or "right" in blocking:
            return "OTS_RIGHT"
        return "OTS_LEFT"  # default OTS

    # Exact match
    key = (shot_type, blocking)
    if key in COVERAGE_ROLE_MAP:
        return COVERAGE_ROLE_MAP[key]

    # Partial match on shot_type
    for (st, br), role in COVERAGE_ROLE_MAP.items():
        if st == shot_type:
            return role

    # Fallback by type
    return COVERAGE_FALLBACK.get(shot_type, "B_MEDIUM")


def infer_wardrobe_lock(shot: Dict, cast_map: Dict, scene_id: str, time_of_day: str = "") -> Dict[str, str]:
    """
    Generate wardrobe lock keys per character for continuity enforcement.
    Format: {CHARACTER_NAME: "scene_id_time_wardrobe_v1"}
    """
    characters = shot.get("characters", []) or []
    if not characters:
        return {}

    tod = (time_of_day or shot.get("time_of_day", "day")).lower().replace(" ", "_")
    location = (shot.get("location", "") or "").lower().replace(" ", "_").replace("-", "_")[:20]
    wardrobe = {}

    for char_name in characters:
        # Build a deterministic wardrobe key
        # Same character + same scene + same time_of_day = same wardrobe
        char_key = char_name.upper().replace(" ", "_")
        wardrobe_key = f"{char_key}_s{scene_id}_{tod}_v1"
        wardrobe[char_name] = wardrobe_key

    return wardrobe


def infer_expected_elements(shot: Dict, beat: Optional[Dict] = None) -> List[str]:
    """
    Extract expected visual elements from beat description, nano_prompt, and script_line_ref.
    Returns list of canonical element names that SHOULD be visible in the frame.
    """
    elements = set()

    # Gather all text to scan
    texts = []
    if beat:
        texts.append(beat.get("description", ""))
        texts.append(beat.get("dialogue", ""))
    texts.append(shot.get("script_line_ref", ""))
    texts.append(shot.get("nano_prompt", ""))
    texts.append(shot.get("location", ""))

    combined = " ".join(t for t in texts if t).lower()

    # Run pattern matching
    for pattern, element_name in ELEMENT_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            elements.add(element_name)

    # Always expect characters if present
    chars = shot.get("characters", [])
    if chars:
        for c in chars:
            elements.add(f"character:{c}")

    # Location-based defaults
    location = (shot.get("location", "") or "").lower()
    if "apartment" in location or "room" in location or "office" in location:
        elements.add("interior_space")
    elif "exterior" in location or "outside" in location or "street" in location or "garden" in location:
        elements.add("exterior_space")

    return sorted(elements)


def find_beat_for_shot(shot: Dict, story_bible: Dict) -> Optional[Dict]:
    """
    Find the story bible beat that corresponds to this shot's beat_id.
    """
    beat_id = shot.get("beat_id", "")
    scene_id = shot.get("scene_id", "")
    if not beat_id or not scene_id:
        return None

    # Parse beat number from beat_id (format: "001_beat_3")
    parts = beat_id.split("_beat_")
    if len(parts) != 2:
        return None

    try:
        beat_num = int(parts[1])
    except ValueError:
        return None

    # Find the scene in story bible
    for scene in story_bible.get("scenes", []):
        if str(scene.get("scene_id", "")) == str(scene_id):
            beats = scene.get("beats", [])
            # beat_number is 1-indexed in story bible
            for b in beats:
                if b.get("beat_number") == beat_num or b.get("beat_number") == beat_num + 1:
                    return b
            # Also try by index
            if 0 <= beat_num < len(beats):
                return beats[beat_num]
            break

    return None


def tag_single_shot(shot: Dict, story_bible: Dict, cast_map: Dict, force: bool = False) -> Dict[str, Any]:
    """
    Tag a single shot with intent metadata.
    Returns dict of new fields to merge onto the shot.

    If force=False, only fills fields that are currently empty/missing.
    If force=True, overwrites all intent fields.
    """
    updates = {}
    beat = find_beat_for_shot(shot, story_bible)

    # 1. Purpose
    if force or not shot.get("purpose"):
        updates["purpose"] = infer_purpose(shot, beat)

    # 2. Coverage role
    if force or not shot.get("coverage_role"):
        updates["coverage_role"] = infer_coverage_role(shot)

    # 3. Wardrobe lock
    if force or not shot.get("wardrobe_lock"):
        scene_id = shot.get("scene_id", "")
        tod = shot.get("time_of_day", "")
        updates["wardrobe_lock"] = infer_wardrobe_lock(shot, cast_map, scene_id, tod)

    # 4. Expected elements
    if force or not shot.get("expected_elements"):
        updates["expected_elements"] = infer_expected_elements(shot, beat)

    return updates


def tag_all_shots(
    shot_plan: Dict,
    story_bible: Dict,
    cast_map: Dict,
    force: bool = False
) -> Tuple[Dict, int, List[str]]:
    """
    Tag all shots in the shot plan with intent metadata.

    Returns: (updated_shot_plan, num_tagged, list_of_changes)
    """
    shots = shot_plan.get("shots", [])
    num_tagged = 0
    changes = []

    for shot in shots:
        shot_id = shot.get("shot_id", "?")
        updates = tag_single_shot(shot, story_bible, cast_map, force=force)

        if updates:
            for key, value in updates.items():
                old = shot.get(key)
                if old != value:
                    shot[key] = value
                    changes.append(f"{shot_id}: {key} = {value if not isinstance(value, dict) else '...'}")
            num_tagged += 1

    return shot_plan, num_tagged, changes


def coverage_completeness_report(shots: List[Dict], scene_id: str = "") -> Dict:
    """
    Analyze coverage completeness for a scene or all shots.
    Returns report with scores and gaps.
    """
    if scene_id:
        scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
    else:
        scene_shots = shots

    if not scene_shots:
        return {"score": 0, "grade": "F", "gaps": ["No shots found"]}

    # Required coverage per scene
    roles = [s.get("coverage_role", "") for s in scene_shots]
    purposes = [s.get("purpose", "") for s in scene_shots]

    has_master = any(r.startswith("A_") for r in roles)
    has_medium = any(r.startswith("B_") for r in roles)
    has_close = any(r.startswith("C_") for r in roles)
    has_dialogue = any(p == "DIALOGUE" for p in purposes)
    has_establish = any(p == "ESTABLISH" for p in purposes)

    # Check for back-to-back identical coverage roles
    back_to_back = 0
    for i in range(1, len(roles)):
        if roles[i] and roles[i] == roles[i-1]:
            back_to_back += 1

    gaps = []
    score = 100

    if not has_master:
        gaps.append("Missing A_MASTER (establishing/wide shot)")
        score -= 25
    if not has_close and len(scene_shots) > 2:
        gaps.append("Missing C_CLOSE (no close-up coverage)")
        score -= 15
    if not has_establish:
        gaps.append("Missing ESTABLISH purpose shot")
        score -= 15
    if back_to_back > 0:
        gaps.append(f"{back_to_back} back-to-back identical coverage roles")
        score -= back_to_back * 5

    # Lens variety check
    lenses = set()
    for s in scene_shots:
        lens = s.get("lens_specs", "")
        if lens:
            lenses.add(lens)
    if len(lenses) < 2 and len(scene_shots) > 3:
        gaps.append(f"Low lens variety ({len(lenses)} unique)")
        score -= 10

    score = max(0, min(100, score))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

    return {
        "scene_id": scene_id or "all",
        "total_shots": len(scene_shots),
        "score": score,
        "grade": grade,
        "gaps": gaps,
        "coverage_roles": {r: roles.count(r) for r in set(roles) if r},
        "purposes": {p: purposes.count(p) for p in set(purposes) if p},
        "has_master": has_master,
        "has_medium": has_medium,
        "has_close": has_close,
        "lens_variety": len(lenses),
        "back_to_back_violations": back_to_back,
    }


# ─────────────────────────────────────────────────────
# WARDROBE CONTINUITY CHECK
# ─────────────────────────────────────────────────────

def check_wardrobe_continuity(shots: List[Dict]) -> List[Dict]:
    """
    Check for wardrobe continuity issues across shots in the same scene.
    Returns list of issues found.
    """
    issues = []
    # Group shots by scene
    scenes = {}
    for s in shots:
        sid = s.get("scene_id", "?")
        scenes.setdefault(sid, []).append(s)

    for scene_id, scene_shots in scenes.items():
        # Track wardrobe keys per character across scene
        char_wardrobe = {}
        for shot in sorted(scene_shots, key=lambda x: x.get("shot_id", "")):
            wl = shot.get("wardrobe_lock", {})
            if not wl:
                continue
            for char, key in wl.items():
                if char in char_wardrobe:
                    if char_wardrobe[char] != key:
                        issues.append({
                            "scene_id": scene_id,
                            "shot_id": shot.get("shot_id"),
                            "character": char,
                            "expected": char_wardrobe[char],
                            "got": key,
                            "type": "wardrobe_drift"
                        })
                else:
                    char_wardrobe[char] = key

    return issues
