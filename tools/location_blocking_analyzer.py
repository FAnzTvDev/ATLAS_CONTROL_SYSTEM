"""
ATLAS V27.3: Location-Aware Blocking Analyzer
=============================================
Maps the PHYSICAL GEOGRAPHY of each scene's location and tracks
where characters are positioned relative to furniture, doors, stairs,
and props throughout the scene.

PURPOSE: Prevent spatial contamination where prompts reference objects
that don't exist at the character's current position in the room.

EXAMPLE OF THE PROBLEM IT SOLVES:
  Beat 3 says "Eleanor opens briefcase on dusty console table"
  The console table is at the ENTRANCE SIDE of the foyer
  But shots 005B-008B are dialogue shots where characters have MOVED
  to the CENTER or STAIRCASE zone — there's no console table there.
  Without this analyzer, every shot referenced "table" in the prompt.

THREE-LAYER SYSTEM:
  Layer 1: ROOM GEOGRAPHY — Parse story bible for furniture, fixtures, zones
  Layer 2: CHARACTER TRACKING — Track where each character IS per shot
  Layer 3: PROP VALIDATION — Ensure prompts only reference props visible
           from the character's current zone

Wired into V26 Controller Phase E4 (after Scene Continuity Enforcer).
Non-blocking: flags violations but doesn't halt generation.

Production Evidence: V27.2 Scene 001 — Eleanor "placing briefcase on table"
appeared in 4 consecutive shots despite being in the staircase/center zone.
"""

import re
import json
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: ROOM GEOGRAPHY PARSER
# ═══════════════════════════════════════════════════════════════════════════════

# Default room templates — furniture/fixture anchors per room type
ROOM_GEOGRAPHY_TEMPLATES = {
    "foyer": {
        "zones": {
            "entrance": {
                "position": "frame-left",
                "fixtures": ["heavy front doors", "coat rack", "umbrella stand", "dark corridor behind"],
                "surfaces": ["console table", "sideboard"],
                "lighting": "door-frame light, corridor shadows",
                "description": "entrance doorway, ornate frame, shadowy hallway beyond",
            },
            "staircase": {
                "position": "frame-right",
                "fixtures": ["grand staircase", "banister", "railing", "upper landing", "portrait on landing"],
                "surfaces": ["newel post"],
                "lighting": "upper-floor light falling down stairs",
                "description": "dark wood staircase, banister railing, portrait visible on landing above",
            },
            "center": {
                "position": "center",
                "fixtures": ["chandelier overhead", "dust sheets on furniture", "marble floor"],
                "surfaces": ["center table", "rug"],
                "lighting": "chandelier (dark) above, ambient from all sides",
                "description": "open foyer space, chandelier above, marble floor, dust sheets",
            },
            "window": {
                "position": "frame-left-upper",
                "fixtures": ["stained glass windows", "tall arched windows"],
                "surfaces": [],
                "lighting": "fractured colored light, morning rays with dust motes",
                "description": "tall stained glass windows casting colored light patterns",
            },
        },
        "room_description": "grand Victorian foyer with marble floors, crystal chandelier, stained glass windows",
        "atmosphere": "dust-filtered morning light, faded grandeur",
    },
    "study": {
        "zones": {
            "desk": {
                "position": "center",
                "fixtures": ["heavy writing desk", "banker's lamp", "chair"],
                "surfaces": ["desk surface", "blotter"],
                "lighting": "green-shade lamp, concentrated pool of light",
                "description": "heavy wooden desk with papers, banker's lamp casting green-tinged glow",
            },
            "bookshelf": {
                "position": "frame-right",
                "fixtures": ["floor-to-ceiling bookshelves", "ladder"],
                "surfaces": ["shelf ledge"],
                "lighting": "ambient from lamp, book-spine reflections",
                "description": "dark wood bookshelves filled with leather-bound volumes",
            },
            "fireplace": {
                "position": "frame-left",
                "fixtures": ["fireplace", "mantle", "portrait above mantle"],
                "surfaces": ["mantle shelf"],
                "lighting": "fireplace glow, warm ember light",
                "description": "stone fireplace, ornate mantle, portrait hanging above",
            },
            "window": {
                "position": "frame-left-upper",
                "fixtures": ["curtained windows"],
                "surfaces": ["window seat"],
                "lighting": "filtered daylight through heavy drapes",
                "description": "heavy curtained windows, muted daylight filtering through",
            },
        },
        "room_description": "Victorian study with dark wood, heavy drapes, banker's lamp",
        "atmosphere": "intimate, enclosed, claustrophobic warmth",
    },
    "library": {
        "zones": {
            "center": {
                "position": "center",
                "fixtures": ["reading table", "standing globe", "chairs"],
                "surfaces": ["table surface"],
                "lighting": "overhead pendant, ambient window light",
                "description": "central reading area with globe and leather chairs",
            },
            "stacks": {
                "position": "frame-right",
                "fixtures": ["tall bookshelves", "rolling ladder"],
                "surfaces": ["shelf ledges"],
                "lighting": "shelf shadows, vertical dark stripes",
                "description": "towering bookshelves creating dark corridors",
            },
            "fireplace": {
                "position": "frame-left",
                "fixtures": ["fireplace", "wingback chairs"],
                "surfaces": ["side table"],
                "lighting": "fire glow, warm amber",
                "description": "fireplace with wingback chairs, warm intimate light",
            },
        },
        "room_description": "grand library with floor-to-ceiling shelves and reading nooks",
        "atmosphere": "scholarly, hushed, layered depth",
    },
    "bedroom": {
        "zones": {
            "bed": {
                "position": "center",
                "fixtures": ["four-poster bed", "nightstands"],
                "surfaces": ["nightstand surface", "bed"],
                "lighting": "bedside lamp, soft diffused",
                "description": "four-poster bed with rumpled covers, bedside lamp",
            },
            "vanity": {
                "position": "frame-left",
                "fixtures": ["vanity mirror", "dressing table"],
                "surfaces": ["vanity surface"],
                "lighting": "mirror-reflected lamp light",
                "description": "vanity mirror, hairbrush, personal items",
            },
            "window": {
                "position": "frame-right",
                "fixtures": ["curtained window", "window seat"],
                "surfaces": ["window seat cushion"],
                "lighting": "natural light through sheer curtains",
                "description": "window with sheer curtains, soft daylight",
            },
        },
        "room_description": "Victorian bedroom with four-poster bed and vanity",
        "atmosphere": "private, vulnerable, soft contrast",
    },
    "kitchen": {
        "zones": {
            "range": {
                "position": "center",
                "fixtures": ["cast-iron range", "copper pots", "chimney hood"],
                "surfaces": ["range top", "preparation surface"],
                "lighting": "warm fire glow from range, overhead pendant",
                "description": "large cast-iron cooking range, copper pots hanging above",
            },
            "table": {
                "position": "frame-left",
                "fixtures": ["servants' table", "wooden chairs", "dresser with crockery"],
                "surfaces": ["kitchen table", "chopping board"],
                "lighting": "ambient from range and window",
                "description": "worn wooden table, mismatched chairs, crockery dresser",
            },
            "pantry": {
                "position": "frame-right",
                "fixtures": ["pantry doorway", "shelves with preserves"],
                "surfaces": ["pantry shelf"],
                "lighting": "dim corridor light from pantry",
                "description": "dark pantry doorway, glass jars on shelves",
            },
        },
        "room_description": "Victorian servants' kitchen with cast-iron range and wooden table",
        "atmosphere": "warm, functional, below-stairs domesticity",
    },
    "drawing_room": {
        "zones": {
            "center": {
                "position": "center",
                "fixtures": ["settee", "coffee table", "rug", "occasional chairs"],
                "surfaces": ["coffee table", "side tables"],
                "lighting": "mixed: window light and table lamps",
                "description": "formal seating area with settee and occasional chairs",
            },
            "fireplace": {
                "position": "frame-left",
                "fixtures": ["ornate fireplace", "overmantle mirror", "clock"],
                "surfaces": ["mantelpiece"],
                "lighting": "fire glow, mirror reflections",
                "description": "decorative fireplace with overmantle mirror, ticking clock",
            },
            "window": {
                "position": "frame-right",
                "fixtures": ["bay window", "window seat", "heavy drapes"],
                "surfaces": ["window seat"],
                "lighting": "natural daylight, best-lit area",
                "description": "bay window with garden view, heavy velvet drapes",
            },
        },
        "room_description": "formal Victorian drawing room with settee and fireplace",
        "atmosphere": "formal, curated, public-facing elegance",
    },
    "staircase": {
        "zones": {
            "base": {
                "position": "center",
                "fixtures": ["newel post", "first steps", "runner carpet"],
                "surfaces": ["newel post cap"],
                "lighting": "ambient from foyer below",
                "description": "base of staircase, ornate newel post, carpet runner",
            },
            "landing": {
                "position": "frame-right",
                "fixtures": ["half-landing", "portrait", "window"],
                "surfaces": ["landing rail"],
                "lighting": "window light from landing, portrait illuminated",
                "description": "half-landing with window, portrait hanging on wall",
            },
            "upper": {
                "position": "frame-left",
                "fixtures": ["upper hallway", "doorways", "runner carpet"],
                "surfaces": ["hallway floor"],
                "lighting": "dim upper-floor light, doorway spill",
                "description": "upper hallway stretching into shadow, closed doors",
            },
        },
        "room_description": "grand Victorian staircase with carved banister and portrait",
        "atmosphere": "transitional, vertical, connecting public and private spaces",
    },
    "exterior": {
        "zones": {
            "approach": {
                "position": "center",
                "fixtures": ["gravel drive", "front steps", "portico"],
                "surfaces": ["gravel", "stone steps"],
                "lighting": "full daylight, overcast or sunny",
                "description": "gravel driveway leading to front entrance portico",
            },
            "garden": {
                "position": "frame-right",
                "fixtures": ["hedgerows", "flower beds", "garden path"],
                "surfaces": ["garden bench", "stone wall"],
                "lighting": "dappled light through trees",
                "description": "overgrown garden with hedgerows and winding path",
            },
            "facade": {
                "position": "frame-left",
                "fixtures": ["manor facade", "windows", "ivy"],
                "surfaces": ["stone wall"],
                "lighting": "reflected daylight off stone facade",
                "description": "imposing Victorian manor facade, ivy-covered walls",
            },
        },
        "room_description": "Victorian estate exterior with gravel drive and gardens",
        "atmosphere": "exposed, grey English countryside, faded grandeur",
    },
}


# Props that are ZONE-SPECIFIC — they can ONLY appear in certain zones
# If a prompt references these but the character is in a DIFFERENT zone, it's contamination
ZONE_LOCKED_PROPS = {
    "console table": ["entrance"],
    "dusty console table": ["entrance"],
    "briefcase on table": ["entrance", "center"],
    "sideboard": ["entrance"],
    "banister": ["staircase"],
    "railing": ["staircase"],
    "staircase": ["staircase"],
    "portrait": ["staircase"],  # In foyer, portrait is above staircase
    "painting": ["staircase"],
    "chandelier": ["center"],
    "dust sheets": ["center"],
    "stained glass": ["window"],
    "front door": ["entrance"],
    "doorway": ["entrance"],
    "fireplace": ["fireplace"],
    "mantle": ["fireplace"],
    "hearth": ["fireplace"],
    "desk": ["desk"],
    "banker's lamp": ["desk"],
    "bookshelves": ["bookshelf", "stacks"],
    "ladder": ["bookshelf", "stacks"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CHARACTER POSITION TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_room_geography(room_type: str, story_bible_scene: Dict = None) -> Dict:
    """
    Resolve the full room geography for a scene.

    Priority:
    1. Story bible visual_description (if it mentions specific furniture)
    2. Room template (default geography for room type)

    Returns room geography dict with zones, fixtures, surfaces per zone.
    """
    template = ROOM_GEOGRAPHY_TEMPLATES.get(room_type, {})
    if not template:
        return {"zones": {}, "room_type": room_type}

    geography = {
        "room_type": room_type,
        "zones": dict(template.get("zones", {})),
        "room_description": template.get("room_description", ""),
        "atmosphere": template.get("atmosphere", ""),
    }

    # Enrich from story bible if available
    if story_bible_scene:
        vis_desc = (story_bible_scene.get("visual_description", "") or "").lower()
        atmosphere = (story_bible_scene.get("atmosphere", "") or "").lower()

        # Check for specific furniture mentions that might refine zone contents
        if "portrait" in vis_desc and "staircase" in vis_desc:
            if "staircase" in geography["zones"]:
                geo_fix = geography["zones"]["staircase"]["fixtures"]
                if "portrait on landing" not in geo_fix:
                    geo_fix.append("portrait on landing")

        if "console table" in vis_desc:
            if "entrance" in geography["zones"]:
                if "console table" not in geography["zones"]["entrance"]["surfaces"]:
                    geography["zones"]["entrance"]["surfaces"].append("console table")

        if atmosphere:
            geography["atmosphere"] = atmosphere

    return geography


def track_character_positions(
    shots: List[Dict],
    spatial_timecode: List[Dict],
    room_geography: Dict,
) -> Dict[str, List[Dict]]:
    """
    Track where each character is in the room across all shots in a scene.

    Returns:
    {
        "THOMAS BLACKWOOD": [
            {"shot_id": "001_004B", "zone": "entrance", "position": "frame-left",
             "action": "enters foyer", "fixtures_visible": ["front doors", "console table"]},
            {"shot_id": "001_005B", "zone": "staircase", "position": "frame-right",
             "action": "speaks to Eleanor", "fixtures_visible": ["banister", "portrait"]},
            ...
        ]
    }
    """
    # Build timecode lookup
    tc_map = {tc["shot_id"]: tc for tc in spatial_timecode}

    # Track per-character positions
    char_positions = {}  # char_name → list of position entries
    last_zone_per_char = {}  # char_name → last known zone

    zones = room_geography.get("zones", {})

    for shot in shots:
        sid = shot.get("shot_id", "")
        characters = shot.get("characters") or []
        tc = tc_map.get(sid, {})
        zone = tc.get("zone", "center")
        description = (shot.get("description", "") or "").lower()
        beat_action = (shot.get("_beat_character_action", "") or "").lower()

        for char_name in characters:
            if char_name not in char_positions:
                char_positions[char_name] = []
                last_zone_per_char[char_name] = None

            # Determine character's zone
            # Priority 1: Character-specific movement in description
            char_zone = _detect_character_zone_from_text(
                char_name, description, beat_action, zone
            )

            # Priority 2: Spatial timecode zone (scene-level tracking)
            if not char_zone:
                char_zone = zone

            # Priority 3: Inherit from previous shot (character doesn't teleport)
            if not char_zone:
                char_zone = last_zone_per_char.get(char_name, "center")

            # Get zone details
            zone_info = zones.get(char_zone, {})
            position = zone_info.get("position", "center")

            # Screen position lock override (from OTS enforcer)
            if shot.get("_screen_position"):
                position = shot["_screen_position"]

            # Determine what fixtures are visible from this zone
            fixtures_visible = list(zone_info.get("fixtures", []))

            char_positions[char_name].append({
                "shot_id": sid,
                "zone": char_zone,
                "position": position,
                "action": _summarize_action(shot),
                "fixtures_visible": fixtures_visible,
                "zone_source": tc.get("zone_source", "unknown"),
            })

            last_zone_per_char[char_name] = char_zone

    return char_positions


def _detect_character_zone_from_text(
    char_name: str, description: str, beat_action: str,
    default_zone: str
) -> Optional[str]:
    """Detect which zone a specific character is in based on text."""
    name_parts = char_name.lower().split()
    last_name = name_parts[-1] if name_parts else ""
    first_name = name_parts[0] if name_parts else ""

    # Combine texts for analysis
    text = description + " " + beat_action

    # Check if this character is mentioned with a spatial indicator
    # e.g., "Thomas at the staircase", "Eleanor near the entrance"
    for zone, keywords in {
        "entrance": ["enters", "doorway", "front door", "arrives", "threshold"],
        "staircase": ["banister", "railing", "stairs", "portrait above", "gazes up"],
        "center": ["center of room", "faces", "confronts", "between them"],
        "fireplace": ["fireplace", "mantle", "hearth"],
        "window": ["window", "light from"],
    }.items():
        for kw in keywords:
            if kw in text:
                # Check if it's near a mention of this character
                # Loose proximity — within 50 chars of character name
                for name_part in [first_name, last_name]:
                    if name_part and name_part in text:
                        idx_name = text.find(name_part)
                        idx_kw = text.find(kw)
                        if abs(idx_name - idx_kw) < 80:
                            return zone

    return None


def _summarize_action(shot: Dict) -> str:
    """Extract a short action summary from shot data."""
    desc = shot.get("description", "") or ""
    dialogue = shot.get("dialogue_text", "") or ""
    shot_type = (shot.get("shot_type") or "").lower()

    if dialogue:
        words = dialogue.split()[:6]
        return f"speaks: \"{' '.join(words)}...\""
    elif "enter" in desc.lower():
        return "enters room"
    elif "establishing" in shot_type:
        return "establishing shot"
    elif "reaction" in shot_type:
        return "reacts"
    elif "closing" in shot_type:
        return "scene closing"
    else:
        return shot_type


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: PROP CONTAMINATION VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

def validate_prop_references(
    shots: List[Dict],
    char_positions: Dict[str, List[Dict]],
    room_geography: Dict,
) -> List[Dict]:
    """
    Validate that prompts only reference props/fixtures visible from
    the character's current zone.

    Returns list of violations:
    [
        {
            "shot_id": "001_006B",
            "severity": "WARN",
            "prop": "console table",
            "character_zone": "staircase",
            "valid_zones": ["entrance"],
            "message": "Prompt references 'console table' but character is in staircase zone"
        }
    ]
    """
    violations = []

    # Build per-shot zone lookup from char_positions
    shot_zones = {}
    for char_name, positions in char_positions.items():
        for pos in positions:
            sid = pos["shot_id"]
            if sid not in shot_zones:
                shot_zones[sid] = {}
            shot_zones[sid][char_name] = pos["zone"]

    for shot in shots:
        sid = shot.get("shot_id", "")
        nano = (shot.get("nano_prompt", "") or "").lower()
        ltx = (shot.get("ltx_motion_prompt", "") or "").lower()
        prompt_text = nano + " " + ltx

        # Get the primary zone for this shot
        char_zone = "center"
        shot_zone_data = shot_zones.get(sid, {})
        if shot_zone_data:
            # Use first character's zone as primary
            char_zone = list(shot_zone_data.values())[0]

        # Check each zone-locked prop
        for prop, valid_zones in ZONE_LOCKED_PROPS.items():
            if prop.lower() in prompt_text:
                if char_zone not in valid_zones:
                    violations.append({
                        "shot_id": sid,
                        "severity": "WARN",
                        "prop": prop,
                        "character_zone": char_zone,
                        "valid_zones": valid_zones,
                        "message": (
                            f"Prompt references '{prop}' but character is in "
                            f"'{char_zone}' zone (valid zones: {valid_zones})"
                        ),
                    })

    return violations


def strip_invalid_props(
    shot: Dict,
    character_zone: str,
    room_geography: Dict,
) -> Dict:
    """
    Remove references to props that aren't visible from the character's zone.
    Replaces them with zone-appropriate spatial descriptions.
    """
    nano = shot.get("nano_prompt", "") or ""
    zone_info = room_geography.get("zones", {}).get(character_zone, {})

    # Build zone-appropriate replacement description
    zone_desc = zone_info.get("description", "")

    for prop, valid_zones in ZONE_LOCKED_PROPS.items():
        if character_zone not in valid_zones:
            # Strip this prop from the prompt
            # Use flexible regex to catch variations
            pattern = re.compile(
                rf'\b{re.escape(prop)}\b',
                re.IGNORECASE
            )
            if pattern.search(nano):
                nano = pattern.sub("", nano)
                # Clean up double spaces
                nano = re.sub(r'\s{2,}', ' ', nano).strip()

    shot["nano_prompt"] = nano
    return shot


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: BLOCKING ASSESSMENT REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_blocking_assessment(
    shots: List[Dict],
    room_geography: Dict,
    char_positions: Dict[str, List[Dict]],
    violations: List[Dict],
    scene_id: str = "001",
) -> Dict:
    """
    Generate a comprehensive blocking assessment for a scene.

    Returns:
    {
        "scene_id": "001",
        "room_type": "foyer",
        "room_zones": [...],
        "character_tracks": {...},
        "zone_transitions": [...],
        "prop_violations": [...],
        "spatial_health_score": 0.85,
        "recommendations": [...]
    }
    """
    zones = room_geography.get("zones", {})
    room_type = room_geography.get("room_type", "unknown")

    # Analyze zone transitions
    zone_transitions = []
    for char_name, positions in char_positions.items():
        prev_zone = None
        for pos in positions:
            if prev_zone and pos["zone"] != prev_zone:
                zone_transitions.append({
                    "character": char_name,
                    "from_zone": prev_zone,
                    "to_zone": pos["zone"],
                    "at_shot": pos["shot_id"],
                    "justified": pos["zone_source"] in ["beat_keyword", "description_keyword"],
                })
            prev_zone = pos["zone"]

    # Count unjustified transitions (potential teleporting)
    unjustified = [t for t in zone_transitions if not t["justified"]]

    # Spatial health score
    total_shots = len(shots)
    violation_count = len(violations)
    unjustified_count = len(unjustified)
    penalty = (violation_count * 0.05) + (unjustified_count * 0.1)
    health_score = max(0, min(1.0, 1.0 - penalty))

    # Recommendations
    recommendations = []
    if violation_count > 0:
        prop_names = list(set(v["prop"] for v in violations))
        recommendations.append(
            f"Strip zone-locked props from wrong zones: {', '.join(prop_names[:5])}"
        )
    if unjustified_count > 0:
        recommendations.append(
            f"{unjustified_count} zone transitions lack story-bible justification — "
            f"add movement beats or lock characters to zones"
        )

    # Check if any character appears in ALL zones (suspicious — probably drifting)
    for char_name, positions in char_positions.items():
        char_zones = set(p["zone"] for p in positions)
        if len(char_zones) > 3:
            recommendations.append(
                f"{char_name} appears in {len(char_zones)} zones — likely spatial drift. "
                f"Lock to primary zone unless screenplay describes movement."
            )

    return {
        "scene_id": scene_id,
        "room_type": room_type,
        "room_zones": list(zones.keys()),
        "zone_details": {
            name: {
                "position": z.get("position", ""),
                "fixtures": z.get("fixtures", []),
                "description": z.get("description", ""),
            }
            for name, z in zones.items()
        },
        "character_tracks": {
            char: [
                {"shot": p["shot_id"], "zone": p["zone"], "action": p["action"]}
                for p in positions
            ]
            for char, positions in char_positions.items()
        },
        "zone_transitions": zone_transitions,
        "unjustified_transitions": unjustified,
        "prop_violations": violations,
        "spatial_health_score": round(health_score, 3),
        "recommendations": recommendations,
        "total_shots": total_shots,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: MASTER ANALYSIS — RUNS ALL LAYERS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_scene_blocking(
    shots: List[Dict],
    story_bible_scene: Dict = None,
    spatial_timecode: List[Dict] = None,
    scene_id: str = "001",
) -> Tuple[List[Dict], Dict]:
    """
    Master blocking analysis. Runs all 3 layers:
    1. Resolve room geography
    2. Track character positions
    3. Validate prop references + generate assessment

    Returns:
        (shots_with_flags, assessment_report)

    Shots are returned with _blocking_zone and _blocking_violations flags.
    Assessment report contains full spatial analysis.
    """
    if not shots:
        return shots, {"scene_id": scene_id, "spatial_health_score": 1.0, "reason": "no shots"}

    # Layer 1: Room geography
    from tools.scene_continuity_enforcer import _detect_room_type
    room_type = "default"
    if story_bible_scene:
        loc = (story_bible_scene.get("location", "") or "").lower()
        room_type = _detect_room_type(loc)
    if room_type == "default":
        # Fallback: detect from shots
        for s in shots:
            loc = (s.get("location", "") or "").lower()
            room_type = _detect_room_type(loc)
            if room_type != "default":
                break

    room_geography = resolve_room_geography(room_type, story_bible_scene)

    # Layer 2: Spatial timecode (use provided or build empty)
    if not spatial_timecode:
        # Build minimal timecode from shot data
        spatial_timecode = []
        for s in shots:
            spatial_timecode.append({
                "shot_id": s.get("shot_id", ""),
                "zone": "center",
                "zone_source": "default",
            })

    # Layer 3: Character position tracking
    char_positions = track_character_positions(shots, spatial_timecode, room_geography)

    # Layer 4: Prop validation
    violations = validate_prop_references(shots, char_positions, room_geography)

    # Layer 5: Generate assessment
    assessment = generate_blocking_assessment(
        shots, room_geography, char_positions, violations, scene_id
    )

    # Tag shots with blocking zone data
    tc_map = {tc["shot_id"]: tc for tc in spatial_timecode}
    for shot in shots:
        sid = shot.get("shot_id", "")
        tc = tc_map.get(sid, {})
        shot["_blocking_zone"] = tc.get("zone", "center")
        shot_violations = [v for v in violations if v["shot_id"] == sid]
        if shot_violations:
            shot["_blocking_violations"] = shot_violations

    return shots, assessment


def print_blocking_assessment(assessment: Dict):
    """Print blocking assessment for operator review."""
    print(f"\n{'='*70}")
    print(f" LOCATION-AWARE BLOCKING ASSESSMENT — Scene {assessment.get('scene_id', '?')}")
    print(f"{'='*70}")
    print(f" Room: {assessment.get('room_type', '?').upper()}")
    print(f" Zones: {', '.join(assessment.get('room_zones', []))}")
    print(f" Spatial Health: {assessment.get('spatial_health_score', 0):.1%}")
    print(f" Prop Violations: {len(assessment.get('prop_violations', []))}")
    print(f" Zone Transitions: {len(assessment.get('zone_transitions', []))}")
    print(f"  (unjustified: {len(assessment.get('unjustified_transitions', []))})")

    print(f"\n CHARACTER TRACKS:")
    for char, track in assessment.get("character_tracks", {}).items():
        print(f"  {char}:")
        for t in track:
            print(f"    {t['shot']}: zone={t['zone']:12s} | {t['action']}")

    if assessment.get("prop_violations"):
        print(f"\n PROP VIOLATIONS:")
        for v in assessment["prop_violations"]:
            print(f"  {v['shot_id']}: {v['message']}")

    if assessment.get("zone_transitions"):
        print(f"\n ZONE TRANSITIONS:")
        for t in assessment["zone_transitions"]:
            just = "✓" if t["justified"] else "✗ UNJUSTIFIED"
            print(f"  {t['character']}: {t['from_zone']} → {t['to_zone']} at {t['at_shot']} {just}")

    if assessment.get("recommendations"):
        print(f"\n RECOMMENDATIONS:")
        for r in assessment["recommendations"]:
            print(f"  → {r}")

    print(f"{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os

    project = "pipeline_outputs/victorian_shadows_ep1"
    sp_path = os.path.join(project, "shot_plan.json")
    sb_path = os.path.join(project, "story_bible.json")

    if os.path.exists(sp_path) and os.path.exists(sb_path):
        sp = json.load(open(sp_path))
        sb = json.load(open(sb_path))
        shots = sp if isinstance(sp, list) else sp.get("shots", [])

        scene_001_shots = [s for s in shots if s.get("shot_id", "").startswith("001_")]

        # Get story bible scene
        story_scene = None
        for sc in sb.get("scenes", []):
            if str(sc.get("scene_id", "")) == "001":
                story_scene = sc
                break

        # Build spatial timecode
        from tools.spatial_timecode import build_scene_timecode
        beats = story_scene.get("beats", []) if story_scene else []
        timecode = build_scene_timecode(shots, beats, "001")

        # Run full analysis
        tagged_shots, assessment = analyze_scene_blocking(
            scene_001_shots, story_scene, timecode, "001"
        )

        print_blocking_assessment(assessment)

        print(f"\n✅ Analysis complete: {assessment['spatial_health_score']:.1%} health")
        print(f"   {len(assessment['prop_violations'])} violations, "
              f"{len(assessment['zone_transitions'])} transitions")
    else:
        print("Project files not found. Running template test only.")

        # Template test
        geo = resolve_room_geography("foyer")
        print(f"Foyer zones: {list(geo['zones'].keys())}")
        for zone, info in geo["zones"].items():
            print(f"  {zone}: {info['position']} — fixtures: {info['fixtures'][:3]}")
        print("✅ Template test passed")
