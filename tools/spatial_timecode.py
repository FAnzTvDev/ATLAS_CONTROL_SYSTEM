"""
V27.1.4 SPATIAL TIMECODE TRACKER

Tracks WHERE characters are within a room across a scene's shots.
The DP angle selector uses this to maintain spatial consistency —
if shot N showed the fireplace corner, shot N+1 should still reference
the fireplace area, not jump to a completely different wall.

PRINCIPLE: The camera tells the audience WHERE to look. If two adjacent
shots show different walls of a room, the audience gets spatially confused.
Adjacent shots should share a spatial zone unless the blocking explicitly
moves characters to a new position.

SPATIAL ZONES within a room:
  "entrance"     — front door, coat rack, umbrella stand area
  "staircase"    — grand staircase, banister, upper landing
  "fireplace"    — fireplace wall, mantle, portrait area
  "center"       — middle of room, rug, chandelier overhead
  "window"       — window wall, natural light area

ZONE PROPAGATION RULES:
  1. Establishing/wide shots → "center" (full geography)
  2. B-roll → inherits previous zone or "center"
  3. Character shots → zone determined by:
     a. Beat description keywords (enters, touches banister, stares at portrait)
     b. Previous shot's zone (if no movement keyword, STAY in same zone)
     c. Dialogue context (presenting documents → "center", looking at portrait → "staircase")
  4. OTS pairs → BOTH shots use the SAME zone (they're in the same conversation)
  5. Adjacent shots NEVER jump zones unless a beat describes movement

ZONE → ANGLE MAPPING:
  "entrance"  → reverse_angle (faces entrance door)
  "staircase" → base (faces staircase)
  "fireplace" → medium_interior (faces fireplace wall)
  "center"    → base (default wide view)
  "window"    → reverse_angle or medium_interior

This replaces the simple shot_type → angle mapping with a spatially-aware
system that understands WHERE the characters are AT THIS POINT in the scene.
"""

import re
from typing import Dict, List, Optional, Tuple


# Keywords that indicate spatial zones
ZONE_KEYWORDS = {
    "entrance": ["enters", "arriving", "doorway", "front door", "entrance", "walks in",
                  "comes in", "steps inside", "briefcase in hand"],
    "staircase": ["staircase", "banister", "railing", "stairs", "landing", "portrait above",
                   "stares at", "looking up", "painting above", "commissioned"],
    "fireplace": ["fireplace", "mantle", "fire", "hearth", "warmth", "portrait above mantle",
                   "candelabra", "embers"],
    "center": ["presents", "demands", "confronts", "argues", "discussion", "face to face",
                "stands between", "cooperation", "financial", "numbers", "auction",
                "agreement", "table"],
    "window": ["window", "light", "outside", "garden view", "looking out"],
}

# Zone → preferred location angle
ZONE_ANGLE_MAP = {
    "entrance": "reverse_angle",
    "staircase": "base",
    "fireplace": "medium_interior",
    "center": "base",
    "window": "reverse_angle",
}


def detect_zone_from_text(text: str) -> Optional[str]:
    """Detect spatial zone from text (beat description, dialogue, shot description)."""
    if not text:
        return None
    text_lower = text.lower()
    scores = {}
    for zone, keywords in ZONE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[zone] = score
    if scores:
        return max(scores, key=scores.get)
    return None


def build_scene_timecode(
    shots: List[Dict],
    beats: List,
    scene_id: str = "001"
) -> List[Dict]:
    """
    Build spatial timecode for a scene.

    Returns list of dicts:
    [
        {"shot_id": "001_005B", "zone": "staircase", "angle_pref": "base",
         "zone_source": "beat_keyword", "prev_zone": "entrance"},
        ...
    ]
    """
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]
    if not scene_shots:
        return []

    # Parse beat descriptions for zone indicators
    beat_zones = []
    for b in beats:
        desc = b.get("description", "") if isinstance(b, dict) else str(b)
        zone = detect_zone_from_text(desc)
        beat_zones.append({"description": desc, "zone": zone})

    # Map shots to beats (approximate: distribute shots across beats)
    n_shots = len(scene_shots)
    n_beats = len(beat_zones)
    shot_beat_map = {}
    if n_beats > 0:
        for i, shot in enumerate(scene_shots):
            # Simple proportional mapping
            beat_idx = min(int(i * n_beats / n_shots), n_beats - 1)
            shot_beat_map[shot.get("shot_id", "")] = beat_idx

    # Build timecode with zone propagation
    timecode = []
    current_zone = "center"  # Default starting zone

    for i, shot in enumerate(scene_shots):
        sid = shot.get("shot_id", "")
        shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
        dialogue = shot.get("dialogue_text", "") or ""
        description = shot.get("description", "") or ""
        beat_idx = shot_beat_map.get(sid, 0)
        prev_zone = current_zone

        # Determine zone for this shot
        zone = None
        zone_source = "inherited"

        # Priority 1: Beat description keywords (strongest signal — script says WHERE)
        if beat_idx < len(beat_zones) and beat_zones[beat_idx]["zone"]:
            zone = beat_zones[beat_idx]["zone"]
            zone_source = "beat_keyword"

        # Priority 2: Shot description keywords
        if not zone and description:
            zone = detect_zone_from_text(description)
            if zone:
                zone_source = "description_keyword"

        # Priority 3: Dialogue keywords (weaker — infers from what they're talking about)
        if not zone and dialogue:
            zone = detect_zone_from_text(dialogue)
            if zone:
                zone_source = "dialogue_keyword"

        # Priority 4: OTS shots inherit from their pair partner
        if not zone and "over_the_shoulder" in shot_type:
            # OTS shots stay in the same zone as the previous shot
            zone = current_zone
            zone_source = "ots_pair_inherit"

        # Priority 5: Establishing/wide/closing → center (full geography)
        if not zone and shot_type in ["establishing", "wide", "closing"]:
            zone = "center"
            zone_source = "wide_default"

        # Priority 6: Inherit from previous shot (no movement detected = stay put)
        if not zone:
            zone = current_zone
            zone_source = "spatial_continuity"

        # Get angle preference from zone
        angle_pref = ZONE_ANGLE_MAP.get(zone, "base")

        timecode.append({
            "shot_id": sid,
            "shot_type": shot_type,
            "beat_index": beat_idx,
            "zone": zone,
            "prev_zone": prev_zone,
            "zone_source": zone_source,
            "angle_pref": angle_pref,
            "zone_changed": zone != prev_zone,
        })

        current_zone = zone

    return timecode


def get_timecode_angle_for_shot(
    shot_id: str,
    timecode: List[Dict]
) -> Optional[str]:
    """Get the spatially-aware angle preference for a specific shot."""
    for tc in timecode:
        if tc["shot_id"] == shot_id:
            return tc["angle_pref"]
    return None


def print_timecode(timecode: List[Dict]):
    """Print timecode for debugging/operator review."""
    for tc in timecode:
        zone_flag = " ← ZONE CHANGE" if tc["zone_changed"] else ""
        print(
            f"  {tc['shot_id']} | {tc['shot_type']:20s} | "
            f"zone={tc['zone']:12s} | angle={tc['angle_pref']:16s} | "
            f"src={tc['zone_source']:20s}{zone_flag}"
        )


# === SELF-TEST ===
if __name__ == "__main__":
    import json
    import os

    project = "pipeline_outputs/victorian_shadows_ep1"
    sp_path = os.path.join(project, "shot_plan.json")
    sb_path = os.path.join(project, "story_bible.json")

    if os.path.exists(sp_path) and os.path.exists(sb_path):
        sp = json.load(open(sp_path))
        sb = json.load(open(sb_path))
        shots = sp if isinstance(sp, list) else sp.get("shots", [])

        for scene in sb.get("scenes", []):
            sid = str(scene.get("scene_id", ""))
            if sid == "001":
                beats = scene.get("beats", [])
                tc = build_scene_timecode(shots, beats, sid)
                print(f"=== SCENE {sid} SPATIAL TIMECODE ===")
                print_timecode(tc)
                break
    else:
        print("Project files not found, running unit tests only")

    # Unit tests
    test_beats = [
        {"description": "Eleanor enters the foyer with briefcase"},
        {"description": "Thomas touches the banister with grief"},
        {"description": "Eleanor presents the financial demands"},
        {"description": "Thomas stares at portrait above staircase"},
    ]
    test_shots = [
        {"shot_id": "001_001A", "shot_type": "establishing"},
        {"shot_id": "001_002B", "shot_type": "b-roll"},
        {"shot_id": "001_005B", "shot_type": "over_the_shoulder", "dialogue_text": "She would have hated this"},
        {"shot_id": "001_006B", "shot_type": "over_the_shoulder", "dialogue_text": "The estate's debts exceed"},
        {"shot_id": "001_007B", "shot_type": "two_shot", "dialogue_text": "I know what the numbers say"},
        {"shot_id": "001_008B", "shot_type": "medium_close", "dialogue_text": "The auction house arrives"},
        {"shot_id": "001_009B", "shot_type": "medium_close", "dialogue_text": "That painting. Harriet commissioned"},
    ]
    tc = build_scene_timecode(test_shots, test_beats, "001")
    print("\n=== UNIT TEST ===")
    print_timecode(tc)

    # Verify: 007B and 008B should be in same zone (no jump)
    z7 = next(t for t in tc if t["shot_id"] == "001_007B")
    z8 = next(t for t in tc if t["shot_id"] == "001_008B")
    assert not z8["zone_changed"], f"008B should NOT jump zones! Was {z7['zone']} → {z8['zone']}"
    print("\n✅ Spatial continuity: 007B → 008B stays in same zone")

    # Verify: 009B should change zone (portrait/staircase reference)
    z9 = next(t for t in tc if t["shot_id"] == "001_009B")
    print(f"✅ 009B zone: {z9['zone']} (source: {z9['zone_source']})")
