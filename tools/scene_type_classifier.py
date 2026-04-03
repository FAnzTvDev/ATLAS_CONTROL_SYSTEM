"""
V21.2: Scene Type Classifier — Context-Aware Dialogue Grammar
==============================================================
Classifies scenes by physical configuration, not rigid templates.
Restores V9-level intelligence by matching coverage to physical reality.

Scene Types:
  RITUAL          — ceremonial, non-conversational, atmospheric
  MONTAGE         — rapid cuts across multiple locations, no sustained dialogue
  SHARED_DIALOGUE — characters physically together, full coverage available
  PHONE_DIALOGUE  — characters in separate locations, intercut coverage
  INTERCUT        — cross-cutting between parallel actions/locations
  VOICEOVER       — narrator or off-screen character, visual metaphor shots
  SOLO_ATMOSPHERE — single character alone, internal/haunting moments
  CONFRONTATION   — high-tension shared dialogue, faster cuts, tighter framing

Example Usage:
  from tools.scene_type_classifier import classify_scene, get_micro_template
  from tools.scene_type_classifier import apply_scene_classifications

  # Single scene classification
  scene_type, confidence, reason = classify_scene(
      scene_shots=shot_plan["shots"][0:12],  # Scene 001
      scene_id="001"
  )

  # Apply to all shots in project
  summary = apply_scene_classifications(
      all_shots=shot_plan["shots"],
      story_bible=story_bible
  )

  # Print violations
  for scene_id, info in summary.items():
      if info["violations"]:
          print(f"Scene {scene_id} ({info['type']}): {len(info['violations'])} coverage issues")

Author: Claude
Date: 2026-02-28
Version: V21.2
"""

import json
import re
from typing import List, Dict, Tuple, Optional, Any


# =============================================================================
# RAVENCROFT-SPECIFIC SCENE OVERRIDES
# =============================================================================

RAVENCROFT_SCENE_OVERRIDES = {
    "000": {
        "type": "MONTAGE",
        "reason": "Show Open title sequence — rapid dissolves across 9 locations, no sustained dialogue",
    },
    "001": {
        "type": "RITUAL",
        "reason": "Binding ritual — Margaret + robed figures, ceremonial chanting, atmospheric, one V.O. line from child",
    },
    "002": {
        "type": "PHONE_DIALOGUE",
        "reason": "BJ script: 'INTERCUT WITH: INT. LAW OFFICE - DAY' — Evelyn in apartment, Lawyer in office, phone call",
        "locations": ["INT. CITY APARTMENT", "INT. LAW OFFICE"],
        "note": "Lawyer never physically present — all coverage is per-location, NO shared 2-shot",
    },
    "003": {
        "type": "SOLO_ATMOSPHERE",
        "reason": "Bus journey — Evelyn alone traveling, quick insert shots (email, map, text), no dialogue partner",
    },
    "004": {
        "type": "SHARED_DIALOGUE",
        "reason": "Village pub — Evelyn enters, talks to Clara face-to-face, locals react, all same physical space",
    },
    "005": {
        "type": "SHARED_DIALOGUE",
        "reason": "Manor gates/foyer — Evelyn meets Arthur, first physical encounter, same space",
        "note": "First meeting — more geography shots to establish the manor",
    },
    "006": {
        "type": "SHARED_DIALOGUE",
        "reason": "Hallway tour — Evelyn + Arthur walking together, East Wing mentioned",
    },
    "007": {
        "type": "SHARED_DIALOGUE",
        "reason": "Study — will terms discussion, Evelyn + Arthur seated, intimate shared space",
    },
    "008": {
        "type": "SOLO_ATMOSPHERE",
        "reason": "First night bedroom — Evelyn alone, footsteps, music box, haunting atmosphere",
    },
    "009": {
        "type": "SHARED_DIALOGUE",
        "reason": "Grounds/cliffs — Evelyn + Arthur walking outdoors, guarded conversation",
    },
    "010": {
        "type": "SHARED_DIALOGUE",
        "reason": "Library — Evelyn discovers photo, Arthur present, shared tension",
    },
    "011": {
        "type": "SHARED_DIALOGUE",
        "reason": "Village cafe — Evelyn meets Dr. Elias Ward, face-to-face conversation",
    },
    "012": {
        "type": "SHARED_DIALOGUE",
        "reason": "Return to pub — Evelyn, Clara, Arthur arrives, multi-character same space",
    },
    "013": {
        "type": "SOLO_ATMOSPHERE",
        "reason": "Evelyn alone exploring — internal discovery, atmospheric",
    },
    "014": {
        "type": "SHARED_DIALOGUE",
        "reason": "Elias shares research — face-to-face dialogue with documents",
    },
    "015": {
        "type": "CONFRONTATION",
        "reason": "Arthur confrontation — high tension, 'house doesn't like to be left alone', direct conflict",
    },
    "016": {
        "type": "SOLO_ATMOSPHERE",
        "reason": "Night storm / East Wing corridor — Evelyn alone, child crying, horror atmosphere",
    },
    "017": {
        "type": "CONFRONTATION",
        "reason": "Study confrontation with Arthur — direct conflict about danger, ominous clarity",
    },
    "018": {
        "type": "SHARED_DIALOGUE",
        "reason": "Signing papers — Evelyn commits, house reacts, climactic decision moment",
    },
}


# =============================================================================
# MICRO-TEMPLATES: CINEMATIC GRAMMAR PER SCENE TYPE
# =============================================================================

MICRO_TEMPLATES = {
    "MONTAGE": {
        "description": "Rapid cuts across multiple locations, no sustained dialogue, high energy",
        "coverage_rules": {
            "require_ots": False,
            "require_2shot": False,
            "require_reaction": False,
            "allow_geography": True,
            "max_cut_duration": 8,
            "min_cut_duration": 4,
            "allow_inserts": True,
        },
        "forbidden": ["sustained_dialogue_coverage", "2-shot", "OTS"],
        "recommended_shot_types": ["establishing", "detail", "medium", "close"],
        "pacing": "fast",
        "chain_behavior": "no_chain",  # Each shot independent
    },
    "RITUAL": {
        "description": "Ceremonial, non-conversational, atmospheric, symbolic imagery",
        "coverage_rules": {
            "require_ots": False,
            "require_2shot": False,
            "require_reaction": False,
            "allow_geography": True,
            "max_cut_duration": 14,
            "min_cut_duration": 6,
            "allow_inserts": True,
        },
        "forbidden": ["casual_2shot", "phone_intercut"],
        "recommended_shot_types": ["close", "detail", "medium", "establishing"],
        "pacing": "slow",
        "chain_behavior": "chain_atmosphere",  # Chain for environment continuity
    },
    "SHARED_DIALOGUE": {
        "description": "Characters physically together, full conversation coverage available",
        "coverage_rules": {
            "require_ots": True,
            "require_2shot": True,
            "require_reaction": True,
            "allow_geography": True,
            "max_cut_duration": 12,
            "min_cut_duration": 6,
            "allow_inserts": True,
        },
        "forbidden": ["cross_location_cut"],
        "recommended_shot_types": ["over_the_shoulder", "medium_close", "two_shot", "reaction", "medium"],
        "pacing": "moderate",
        "chain_behavior": "chain_blocking",  # Chain for character position continuity
    },
    "PHONE_DIALOGUE": {
        "description": "Characters in separate locations, intercut coverage, no physical contact",
        "coverage_rules": {
            "require_ots": False,   # NO shared OTS — characters not together
            "require_2shot": False,  # NO 2-shot — characters not together
            "require_reaction": True,
            "allow_geography": True,
            "max_cut_duration": 10,
            "min_cut_duration": 6,
            "allow_inserts": True,  # Environmental cutaways between lines
        },
        "forbidden": ["2-shot", "shared_OTS", "characters_in_same_frame"],
        "recommended_shot_types": ["medium_close", "close", "medium", "reaction", "detail"],
        "pacing": "moderate",
        "chain_behavior": "chain_per_location",  # Chain within location, break between
    },
    "INTERCUT": {
        "description": "Cross-cutting between parallel actions/locations, high energy",
        "coverage_rules": {
            "require_ots": False,
            "require_2shot": False,
            "require_reaction": True,
            "allow_geography": True,
            "max_cut_duration": 8,
            "min_cut_duration": 4,
            "allow_inserts": True,
        },
        "forbidden": ["2-shot", "shared_OTS", "slow_pacing"],
        "recommended_shot_types": ["medium_close", "close", "medium", "establishing", "detail"],
        "pacing": "fast",
        "chain_behavior": "no_chain",  # Different locations = no chaining
    },
    "VOICEOVER": {
        "description": "Narrator or off-screen character, visual metaphor shots, internal narration",
        "coverage_rules": {
            "require_ots": False,
            "require_2shot": False,
            "require_reaction": False,
            "allow_geography": True,
            "max_cut_duration": 14,
            "min_cut_duration": 6,
            "allow_inserts": True,
        },
        "forbidden": ["speaker_on_screen", "lip_sync_matching"],
        "recommended_shot_types": ["medium", "establishing", "detail", "close"],
        "pacing": "slow",
        "chain_behavior": "chain_atmosphere",
    },
    "SOLO_ATMOSPHERE": {
        "description": "Single character alone, internal/haunting moments, atmospheric isolation",
        "coverage_rules": {
            "require_ots": False,
            "require_2shot": False,
            "require_reaction": False,
            "allow_geography": True,
            "max_cut_duration": 14,
            "min_cut_duration": 6,
            "allow_inserts": True,
        },
        "forbidden": ["dialogue_coverage_pattern", "2-shot"],
        "recommended_shot_types": ["medium", "close", "establishing", "detail", "medium_close"],
        "pacing": "slow",
        "chain_behavior": "chain_atmosphere",
    },
    "CONFRONTATION": {
        "description": "High-tension shared dialogue, faster cuts, tighter framing, peak conflict",
        "coverage_rules": {
            "require_ots": True,
            "require_2shot": True,
            "require_reaction": True,
            "allow_geography": False,  # No wide establishing mid-confrontation
            "max_cut_duration": 8,
            "min_cut_duration": 4,
            "allow_inserts": False,  # No environmental distractions
        },
        "forbidden": ["slow_establishing", "environmental_insert_during_peak"],
        "recommended_shot_types": ["over_the_shoulder", "close", "medium_close", "reaction", "two_shot"],
        "pacing": "fast",
        "chain_behavior": "chain_blocking",
    },
}


# =============================================================================
# PATTERN DETECTION KEYWORDS
# =============================================================================

RITUAL_KEYWORDS = [
    r'\britual\b', r'\bceremony\b', r'\bceremoni', r'\bchanting\b', r'\bchant\b',
    r'\bincantation\b', r'\bcandles?\b', r'\baltar\b', r'\bsacred\b', r'\bsacrifice\b',
    r'\bbinding\b', r'\bspell\b', r'\bmystic\b', r'\bcircle\b', r'\brobed\b',
]

VOICEOVER_KEYWORDS = [
    r'\bvoice[\s-]?over\b', r'\bV\.O\.\b', r'\bnarrat', r'\binternal\s+narrat',
    r'\bthoughts?\b', r'\bin\s+her\s+head\b', r'\bwhisper',
]

CONFRONTATION_KEYWORDS = [
    r'\bconfront', r'\banger\b', r'\brage\b', r'\bfury\b', r'\btension\b',
    r'\baccuse\b', r'\baccusation\b', r'\bblame\b', r'\bconflict\b', r'\bdanger\b',
]

PHONE_KEYWORDS = [
    r'\bphone\b', r'\bcall\b', r'\bphone\s+call\b', r'\btalking.*phone\b',
]

INTERCUT_KEYWORDS = [
    r'\bintercut\b', r'\bcross[\s-]cut\b', r'\bcross[\s-]location\b',
    r'\bparallel\b', r'\bsimultaneous\b',
]

SOLO_KEYWORDS = [
    r'\balone\b', r'\bsolitary\b', r'\bsolo\b', r'\bisolat', r'\bshe\'?s\s+alone\b',
]


# =============================================================================
# CLASSIFICATION LOGIC
# =============================================================================

def _normalize_location(location: str) -> str:
    """Normalize location names for comparison."""
    if not location:
        return ""
    loc = location.upper()
    # Strip INT./EXT. prefixes
    loc = re.sub(r'^(INT\.|EXT\.)\s*', '', loc)
    # Strip time-of-day suffixes
    loc = re.sub(r'\s*[-–—]\s*(DAY|NIGHT|DAWN|DUSK|CONTINUOUS)$', '', loc)
    return loc.strip()


def _extract_locations(scene_shots: List[Dict]) -> Dict[str, int]:
    """Extract and count distinct locations in a scene.
    Returns dict of {normalized_location: count}"""
    locations = {}
    for shot in scene_shots:
        loc = shot.get('location', shot.get('setting', ''))
        if loc:
            norm_loc = _normalize_location(loc)
            locations[norm_loc] = locations.get(norm_loc, 0) + 1
    return locations


def _extract_speaking_characters(scene_shots: List[Dict]) -> Dict[str, int]:
    """Extract characters with dialogue.
    Returns dict of {character_name: dialogue_count}"""
    speakers = {}
    for shot in scene_shots:
        # Check shot-level dialogue
        dialogue = shot.get('dialogue_text', shot.get('dialogue', ''))
        if dialogue:
            # Try to detect speaker from prompt or shot metadata
            speaker = shot.get('primary_character', '')
            if not speaker:
                # Try to extract from dialogue marker like "EVELYN: ..."
                match = re.match(r'^([A-Z][A-Z\s]+?):\s*', dialogue)
                if match:
                    speaker = match.group(1).strip()
            if speaker:
                speakers[speaker] = speakers.get(speaker, 0) + 1
    return speakers


def _count_characters_on_screen(scene_shots: List[Dict]) -> int:
    """Count distinct characters present on screen in the scene."""
    characters = set()
    for shot in scene_shots:
        # Characters in shot metadata
        for char_field in ['characters', 'character_list', 'primary_character', 'secondary_characters']:
            chars = shot.get(char_field)
            if chars:
                if isinstance(chars, str):
                    characters.update([c.strip() for c in chars.split(',') if c.strip()])
                elif isinstance(chars, list):
                    characters.update(chars)
    return len(characters)


def _has_pattern(scene_shots: List[Dict], keywords: List[str]) -> Tuple[bool, float]:
    """Check if any pattern keywords match in scene data.
    Returns (found, confidence 0-1)"""
    total_matches = 0
    total_searchable = 0

    for shot in scene_shots:
        searchable_text = []

        # Gather all text fields
        for field in ['nano_prompt', 'ltx_motion_prompt', 'dialogue_text', 'dialogue',
                      'location', 'setting', 'description', '_scene_description']:
            text = shot.get(field, '')
            if text:
                searchable_text.append(str(text))

        if not searchable_text:
            continue

        combined_text = ' '.join(searchable_text).lower()
        total_searchable += len(combined_text)

        for pattern in keywords:
            matches = len(re.findall(pattern, combined_text, re.IGNORECASE))
            total_matches += matches

    if total_searchable == 0:
        return False, 0.0

    confidence = min(1.0, total_matches / max(1, total_searchable / 100))
    return total_matches > 0, confidence


def classify_scene(
    scene_shots: List[Dict],
    story_bible_scene: Optional[Dict] = None,
    scene_id: Optional[str] = None
) -> Tuple[str, float, str]:
    """
    Classify a scene's physical configuration for cinematic grammar selection.

    Priority order:
      1. Manual override from RAVENCROFT_SCENE_OVERRIDES
      2. Story bible explicit type
      3. Auto-detection from shot data

    Args:
        scene_shots: List of shot dicts for the scene
        story_bible_scene: Optional story bible scene dict
        scene_id: Optional scene ID for override lookup

    Returns:
        (scene_type, confidence, reason) where confidence is 0-1
    """

    # Priority 1: Manual override
    if scene_id and scene_id in RAVENCROFT_SCENE_OVERRIDES:
        override = RAVENCROFT_SCENE_OVERRIDES[scene_id]
        return override["type"], 1.0, override["reason"]

    # Priority 2: Story bible explicit type
    if story_bible_scene and story_bible_scene.get('scene_type'):
        sb_type = story_bible_scene['scene_type'].upper()
        if sb_type in MICRO_TEMPLATES:
            reason = f"Explicit type from story bible: {story_bible_scene.get('scene_type')}"
            return sb_type, 0.95, reason

    # Priority 3: Auto-detect from shot data
    if not scene_shots:
        return "SHARED_DIALOGUE", 0.5, "No shots available (defaulting)"

    # Gather scene metadata
    locations = _extract_locations(scene_shots)
    speakers = _extract_speaking_characters(scene_shots)
    num_characters = _count_characters_on_screen(scene_shots)
    shot_count = len(scene_shots)

    # Check for pattern keywords
    is_ritual, ritual_conf = _has_pattern(scene_shots, RITUAL_KEYWORDS)
    is_voiceover, vo_conf = _has_pattern(scene_shots, VOICEOVER_KEYWORDS)
    is_confrontation, conf_conf = _has_pattern(scene_shots, CONFRONTATION_KEYWORDS)
    is_phone, phone_conf = _has_pattern(scene_shots, PHONE_KEYWORDS)
    is_intercut, intercut_conf = _has_pattern(scene_shots, INTERCUT_KEYWORDS)
    is_solo, solo_conf = _has_pattern(scene_shots, SOLO_KEYWORDS)

    # Decision tree

    # MONTAGE: 4+ locations, many shots, high cut count
    if len(locations) >= 4 and shot_count >= 8:
        reason = f"Multiple locations ({len(locations)}) with {shot_count} shots = montage pacing"
        return "MONTAGE", min(0.9, 0.5 + len(locations) * 0.15), reason

    # RITUAL: Ritual keywords strong + ceremonial atmosphere
    if is_ritual and ritual_conf > 0.4:
        reason = f"Ritual keywords detected (confidence {ritual_conf:.2f})"
        return "RITUAL", min(0.95, ritual_conf + 0.2), reason

    # PHONE_DIALOGUE: 2+ locations + phone keywords OR intercut with phone markers
    if (len(locations) >= 2 and is_phone) or (is_phone and is_intercut):
        reason = f"Phone dialogue across {len(locations)} locations"
        return "PHONE_DIALOGUE", min(0.95, phone_conf + 0.3), reason

    # INTERCUT: 2+ locations + intercut keywords
    if len(locations) >= 2 and is_intercut and intercut_conf > 0.3:
        reason = f"Intercut pattern detected ({len(locations)} locations)"
        return "INTERCUT", min(0.9, intercut_conf + 0.2), reason

    # VOICEOVER: V.O. keywords + no multi-character dialogue
    if is_voiceover and vo_conf > 0.3:
        reason = f"Voice-over narration detected (confidence {vo_conf:.2f})"
        return "VOICEOVER", min(0.9, vo_conf + 0.2), reason

    # SOLO_ATMOSPHERE: Single character OR solo keywords
    if (num_characters <= 1 or is_solo) and not speakers:
        reason = f"Solo character scene ({num_characters} char(s), no dialogue)"
        return "SOLO_ATMOSPHERE", min(0.95, 0.6 + solo_conf), reason

    # CONFRONTATION: 2 characters + confrontation keywords + high intensity
    if num_characters <= 2 and speakers and is_confrontation and conf_conf > 0.3:
        reason = f"High-tension dialogue detected (confidence {conf_conf:.2f})"
        return "CONFRONTATION", min(0.9, conf_conf + 0.3), reason

    # SHARED_DIALOGUE: Default for dialogue scenes, same location, multiple speakers
    if speakers and len(locations) <= 1:
        reason = f"Shared dialogue scene ({len(speakers)} speakers, {len(locations)} location)"
        return "SHARED_DIALOGUE", 0.85, reason

    # Default
    reason = f"Defaulting based on {len(speakers)} speakers, {len(locations)} location(s)"
    return "SHARED_DIALOGUE", 0.6, reason


def get_micro_template(scene_type: str) -> Dict[str, Any]:
    """
    Return the cinematic micro-template for a given scene type.

    Args:
        scene_type: One of the MICRO_TEMPLATES keys

    Returns:
        Template dict with coverage rules, forbidden patterns, pacing, etc.
    """
    return MICRO_TEMPLATES.get(scene_type, MICRO_TEMPLATES["SHARED_DIALOGUE"])


def validate_scene_coverage(
    scene_shots: List[Dict],
    scene_type: str
) -> List[Dict[str, Any]]:
    """
    Validate that a scene's shot coverage matches its type's cinematic grammar.

    Args:
        scene_shots: List of shot dicts
        scene_type: Detected or assigned scene type

    Returns:
        List of violation dicts (empty = all good)
        Each violation has: rule, severity, message, [shots]
    """
    template = get_micro_template(scene_type)
    violations = []
    shot_count = len(scene_shots)

    if not scene_shots:
        return violations

    shot_types = [
        (s.get('type', s.get('shot_type', '')).lower())
        for s in scene_shots
    ]

    # ==== PHONE_DIALOGUE & INTERCUT: Strict location separation ====
    if scene_type in ("PHONE_DIALOGUE", "INTERCUT"):
        # Count locations
        locations = _extract_locations(scene_shots)

        # Should have 2+ locations in phone/intercut
        if len(locations) < 2 and scene_type == "PHONE_DIALOGUE":
            violations.append({
                "rule": "PHONE_NEEDS_LOCATIONS",
                "severity": "warning",
                "message": f"Phone scene should have 2+ locations, found {len(locations)}",
                "locations": list(locations.keys()),
            })

        # NO 2-shots allowed (characters not physically together)
        two_shots = [
            s for s in scene_shots
            if any(t in s.get('type', '') + s.get('shot_type', '')
                   for t in ['two_shot', 'two-shot', '2-shot'])
        ]
        if two_shots:
            violations.append({
                "rule": "NO_2SHOT_IN_PHONE",
                "severity": "blocking",
                "message": (
                    f"Phone/intercut scene has {len(two_shots)} two-shots — "
                    "characters aren't physically together"
                ),
                "shots": [s['shot_id'] for s in two_shots],
            })

        # Warning for shared OTS (should be single-character OTS)
        if scene_type == "PHONE_DIALOGUE":
            ots_shots = [
                s for s in scene_shots
                if any(t in s.get('type', '') + s.get('shot_type', '')
                       for t in ['over_the_shoulder', 'over-the-shoulder', 'ots'])
            ]
            if ots_shots:
                violations.append({
                    "rule": "VERIFY_OTS_SINGLE_CHAR",
                    "severity": "warning",
                    "message": (
                        f"Phone scene has {len(ots_shots)} OTS shots — "
                        "verify these are single-character (not shared framing)"
                    ),
                    "shots": [s['shot_id'] for s in ots_shots],
                })

    # ==== RITUAL: Should have detail/insert shots for ritual elements ====
    if scene_type == "RITUAL":
        detail_shots = [
            s for s in scene_shots
            if (s.get('type', '') in ('detail', 'insert') or
                s.get('_broll') or
                'detail' in s.get('shot_type', '').lower())
        ]
        if len(detail_shots) < 2:
            violations.append({
                "rule": "RITUAL_NEEDS_DETAIL",
                "severity": "warning",
                "message": (
                    f"Ritual scene has only {len(detail_shots)} detail/insert shots — "
                    "ritual elements need visual coverage (candles, altar, objects, etc.)"
                ),
                "shot_count": len(scene_shots),
            })

    # ==== CONFRONTATION: Should have reaction shots ====
    if scene_type == "CONFRONTATION":
        reaction_count = sum(
            1 for t in shot_types if 'reaction' in t
        )
        if reaction_count < 1:
            violations.append({
                "rule": "CONFRONTATION_NEEDS_REACTIONS",
                "severity": "warning",
                "message": (
                    f"Confrontation scene has {reaction_count} reaction shots — "
                    "tension needs visible character reactions"
                ),
            })

        # Verify tight framing (not too many wide shots)
        wide_count = sum(
            1 for t in shot_types
            if any(w in t for w in ['wide', 'establishing', 'master'])
        )
        if wide_count > shot_count * 0.4:  # More than 40% wide shots
            violations.append({
                "rule": "CONFRONTATION_TIGHT_FRAMING",
                "severity": "warning",
                "message": (
                    f"Confrontation scene has {wide_count}/{shot_count} wide shots — "
                    "should favor tight framing for tension"
                ),
            })

    # ==== SOLO_ATMOSPHERE: Verify isolation ====
    if scene_type == "SOLO_ATMOSPHERE":
        speakers = _extract_speaking_characters(scene_shots)
        num_chars = _count_characters_on_screen(scene_shots)

        if num_chars > 1:
            violations.append({
                "rule": "SOLO_ISOLATION",
                "severity": "warning",
                "message": (
                    f"Solo atmosphere scene has {num_chars} characters on screen — "
                    "verify this is intentional (e.g., crowd reaction to solo character)"
                ),
            })

        if len(speakers) > 1:
            violations.append({
                "rule": "SOLO_NO_DIALOGUE",
                "severity": "warning",
                "message": (
                    f"Solo atmosphere scene has {len(speakers)} speaking characters — "
                    "consider if this should be SHARED_DIALOGUE instead"
                ),
                "speakers": list(speakers.keys()),
            })

    # ==== SHARED_DIALOGUE: Requires 2-shot and OTS ====
    if scene_type == "SHARED_DIALOGUE":
        locations = _extract_locations(scene_shots)

        # Multiple locations = likely intercut, not shared dialogue
        if len(locations) > 1:
            violations.append({
                "rule": "SHARED_DIALOGUE_SINGLE_LOCATION",
                "severity": "warning",
                "message": (
                    f"Shared dialogue scene has {len(locations)} locations — "
                    "consider if this should be PHONE_DIALOGUE or INTERCUT"
                ),
                "locations": list(locations.keys()),
            })

        # Should have at least one 2-shot
        two_shots = [
            s for s in scene_shots
            if any(t in s.get('type', '') + s.get('shot_type', '')
                   for t in ['two_shot', 'two-shot', '2-shot'])
        ]
        if not two_shots:
            violations.append({
                "rule": "SHARED_DIALOGUE_NEEDS_2SHOT",
                "severity": "warning",
                "message": (
                    f"Shared dialogue scene has {len(two_shots)} two-shots — "
                    "typically need at least 1 for character relationship"
                ),
            })

    # ==== MONTAGE: Should NOT have sustained dialogue ====
    if scene_type == "MONTAGE":
        speakers = _extract_speaking_characters(scene_shots)
        total_dialogue = sum(
            1 for s in scene_shots
            if s.get('dialogue_text') or s.get('dialogue')
        )

        if total_dialogue > shot_count * 0.5:  # More than 50% dialogue shots
            violations.append({
                "rule": "MONTAGE_NO_SUSTAINED_DIALOGUE",
                "severity": "warning",
                "message": (
                    f"Montage has {total_dialogue}/{shot_count} dialogue shots — "
                    "montages are typically dialogue-light"
                ),
            })

    return violations


def apply_scene_classifications(
    all_shots: List[Dict],
    story_bible: Optional[Dict] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Classify all scenes in a project and persist metadata to each shot.

    Args:
        all_shots: All shot dicts from shot_plan
        story_bible: Optional story bible dict

    Returns:
        Summary dict: {scene_id: {type, confidence, reason, violations, pacing, ...}}

    Also mutates all_shots to add:
        _scene_type: The classified scene type
        _scene_template: Same as _scene_type (for downstream agents)
        _scene_classification_confidence: Confidence score 0-1
    """

    # Group shots by scene
    scenes = {}
    for shot in all_shots:
        scene_id = shot.get('scene_id', '?')
        if scene_id not in scenes:
            scenes[scene_id] = []
        scenes[scene_id].append(shot)

    summary = {}

    for scene_id in sorted(scenes.keys()):
        scene_shots = scenes[scene_id]

        # Look up story bible scene
        sb_scene = None
        if story_bible and isinstance(story_bible.get('scenes'), list):
            for sc in story_bible['scenes']:
                if isinstance(sc, dict) and sc.get('scene_id') == scene_id:
                    sb_scene = sc
                    break

        # Classify
        scene_type, confidence, reason = classify_scene(
            scene_shots=scene_shots,
            story_bible_scene=sb_scene,
            scene_id=scene_id
        )

        # Get template
        template = get_micro_template(scene_type)

        # Validate coverage
        violations = validate_scene_coverage(scene_shots, scene_type)

        # Persist to each shot
        for shot in scene_shots:
            shot['_scene_type'] = scene_type
            shot['_scene_template'] = scene_type  # For downstream agents
            shot['_scene_classification_confidence'] = confidence

        summary[scene_id] = {
            "type": scene_type,
            "confidence": confidence,
            "reason": reason,
            "shot_count": len(scene_shots),
            "violations": violations,
            "pacing": template.get("pacing", "moderate"),
            "chain_behavior": template.get("chain_behavior", "chain_blocking"),
            "template": template,
            "description": template.get("description", ""),
        }

    return summary


# =============================================================================
# REPORTING & ANALYSIS
# =============================================================================

def print_classification_report(summary: Dict[str, Dict[str, Any]]):
    """Print a human-readable classification report."""
    print("\n" + "=" * 80)
    print("SCENE TYPE CLASSIFICATION REPORT")
    print("=" * 80)

    type_counts = {}
    violation_count = 0
    blocking_count = 0

    for scene_id in sorted(summary.keys()):
        info = summary[scene_id]
        scene_type = info['type']
        confidence = info['confidence']
        violations = info.get('violations', [])

        type_counts[scene_type] = type_counts.get(scene_type, 0) + 1
        violation_count += len(violations)
        blocking_count += sum(1 for v in violations if v.get('severity') == 'blocking')

        status = "✓" if not violations else ("✗ BLOCKING" if blocking_count else "⚠ WARNING")
        print(f"\n{status} Scene {scene_id:>3}: {scene_type:20} "
              f"({info['shot_count']} shots, {confidence:.2f} conf)")
        print(f"    {info['reason']}")
        print(f"    Pacing: {info['pacing']}, Chaining: {info['chain_behavior']}")

        if violations:
            for viol in violations:
                sev_icon = "✗" if viol['severity'] == 'blocking' else "⚠"
                print(f"      {sev_icon} {viol['rule']}: {viol['message']}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total scenes: {len(summary)}")
    print(f"Total violations: {violation_count} ({blocking_count} blocking)")
    print("\nScene type breakdown:")
    for scene_type in sorted(type_counts.keys()):
        count = type_counts[scene_type]
        pct = 100 * count / len(summary)
        print(f"  {scene_type:20}: {count:2} scenes ({pct:5.1f}%)")


# =============================================================================
# MAIN: Example usage with Ravencroft project
# =============================================================================

if __name__ == "__main__":
    import os
    import sys

    # Try to load Ravencroft shot plan
    project_path = os.path.expanduser(
        "~/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/ravencroft_v17"
    )
    shot_plan_path = os.path.join(project_path, "shot_plan.json")
    story_bible_path = os.path.join(project_path, "story_bible.json")

    if not os.path.exists(shot_plan_path):
        print(f"Error: shot_plan.json not found at {shot_plan_path}")
        print("This script should be run from ATLAS_CONTROL_SYSTEM directory")
        sys.exit(1)

    # Load data
    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    story_bible = None
    if os.path.exists(story_bible_path):
        with open(story_bible_path) as f:
            story_bible = json.load(f)

    all_shots = shot_plan.get('shots', [])
    print(f"Loaded {len(all_shots)} shots from {len(set(s.get('scene_id') for s in all_shots))} scenes")

    # Classify all scenes
    summary = apply_scene_classifications(all_shots, story_bible)

    # Print report
    print_classification_report(summary)

    # Save classification to shot plan
    shot_plan_out = os.path.join(project_path, "shot_plan_classified.json")
    with open(shot_plan_out, 'w') as f:
        json.dump(shot_plan, f, indent=2)
    print(f"\n✓ Saved classified shot plan to {shot_plan_out}")

    # Also save summary
    summary_out = os.path.join(project_path, "scene_classifications.json")
    with open(summary_out, 'w') as f:
        # Make summary JSON-serializable (remove template dicts)
        summary_clean = {}
        for sid, info in summary.items():
            summary_clean[sid] = {k: v for k, v in info.items() if k != 'template'}
        json.dump(summary_clean, f, indent=2)
    print(f"✓ Saved classification summary to {summary_out}")
