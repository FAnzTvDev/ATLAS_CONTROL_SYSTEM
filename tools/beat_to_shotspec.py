#!/usr/bin/env python3
"""
Beat → ShotSpec Generator

Converts validated story beats into machine-readable ShotSpec JSON
using cinema library templates and character bible descriptions.

ENHANCED: Pattern-based shot generation for cinematographic variety.
Each beat type gets unique ABC coverage instead of cloning same camera.

Usage:
    python3 tools/beat_to_shotspec.py --episode BLACKWOOD_EPISODE_1_COMPLETE.json --scene 001
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ==============================================================================
# SHOT VARIANT SYSTEM - Cinematographic variety for each beat type
# ==============================================================================

@dataclass
class ShotVariant:
    """Defines a single shot within a pattern (A, B, or C angle)."""
    suffix: str                    # "A", "B", "C"
    camera_move: str              # "slow_push", "locked", "handheld_track", etc.
    lens_and_size: str            # "24mm WS", "50mm MCU", "85mm CU", etc.
    composition_tag: str          # "centered_subject", "rule_of_thirds_left", etc.
    include_characters: bool      # Whether to include character descriptions
    role: str                     # "establishing", "reaction", "detail", etc.
    duration_seconds: int = 6     # Default duration for still
    ltx_duration_seconds: int = 12  # Default duration for motion


# ==============================================================================
# LTXv2 DURATION CONSTRAINTS: 4-20 seconds in 2-second intervals
# Valid values: 4, 6, 8, 10, 12, 14, 16, 18, 20
# ==============================================================================

def snap_to_ltx_duration(seconds: int) -> int:
    """Snap duration to valid LTXv2 value (4-20s, 2-second intervals)."""
    valid = [4, 6, 8, 10, 12, 14, 16, 18, 20]
    clamped = max(4, min(20, seconds))
    return min(valid, key=lambda x: abs(x - clamped))


# Pattern library: Each beat type gets unique cinematographic coverage
# Durations are script-appropriate: short for action/inserts, long for atmosphere
SHOT_PATTERNS: Dict[str, List[ShotVariant]] = {
    # Horror ritual - slow dread build with detail inserts
    # Long establishing (tension), medium emotional (reaction), short detail (insert)
    "horror_ritual": [
        ShotVariant("A", "slow_crane_descending", "24mm WS", "symmetrical_dread", True, "establishing", 8, 16),  # Long hold for dread
        ShotVariant("B", "slow_push", "85mm CU", "face_in_shadow", True, "emotional_anchor", 6, 10),  # Medium for reaction
        ShotVariant("C", "locked", "100mm ECU", "object_detail", False, "ritual_prop_detail", 4, 6),  # Short insert
    ],

    # Dialogue two-hander - coverage for conversation
    # Medium master, standard dialogue coverage, short reactions
    "dialogue_two_hander": [
        ShotVariant("A", "slow_dolly", "35mm MS", "two_shot_balanced", True, "master_shot", 8, 14),  # Master holds
        ShotVariant("B", "locked", "50mm MCU", "over_shoulder_favoring_speaker", True, "dialogue_primary", 6, 10),
        ShotVariant("C", "locked", "75mm CU", "listener_reaction", True, "reaction_shot", 4, 6),  # Short reaction
    ],

    # Solo isolation - character alone in space
    # LONG wide to emphasize loneliness, medium close, short detail
    "solo_isolation": [
        ShotVariant("A", "slow_pull_back", "24mm WS", "small_figure_vast_space", True, "isolation_wide", 10, 20),  # MAX for isolation
        ShotVariant("B", "locked", "85mm CU", "contemplative_profile", True, "emotional_close", 6, 12),
        ShotVariant("C", "slow_tilt_down", "50mm MS", "hands_or_feet_detail", False, "body_language_detail", 4, 8),
    ],

    # Travel/exterior - movement through environment
    # Medium tracking, medium follow, short environment
    "travel_exterior": [
        ShotVariant("A", "tracking_alongside", "35mm MS", "rule_of_thirds_leading", True, "travel_master", 8, 14),
        ShotVariant("B", "handheld_follow", "50mm MCU", "back_of_head_or_profile", True, "pov_adjacent", 6, 10),
        ShotVariant("C", "locked", "24mm WS", "environment_establishing", False, "location_context", 5, 8),
    ],

    # Discovery/revelation - building to a reveal
    # Medium approach, SHORT reaction (impact), medium reveal
    "discovery_revelation": [
        ShotVariant("A", "slow_push", "35mm MS", "approaching_subject", True, "approach_shot", 8, 14),
        ShotVariant("B", "locked", "85mm CU", "reaction_face", True, "reaction_moment", 3, 4),  # SHORT punch
        ShotVariant("C", "reveal_pan", "50mm MCU", "object_revealed", False, "reveal_detail", 6, 10),
    ],

    # Confrontation - tension between characters
    # Medium master, medium power, short vulnerability
    "confrontation": [
        ShotVariant("A", "slow_dolly_in", "35mm MS", "two_shot_tension", True, "tension_master", 8, 14),
        ShotVariant("B", "locked", "75mm CU", "dominant_character", True, "power_shot", 6, 12),
        ShotVariant("C", "low_angle", "50mm MCU", "subordinate_character", True, "vulnerability_shot", 4, 8),
    ],

    # Ghost/supernatural - unsettling otherworldly presence
    # LONG empty dread, short terror reaction, very short glimpse
    "apparition_supernatural": [
        ShotVariant("A", "imperceptible_drift", "24mm WS", "empty_space_dread", False, "atmosphere_wide", 10, 18),  # Long dread
        ShotVariant("B", "locked", "85mm CU", "witness_terror", True, "fear_reaction", 3, 6),  # Quick terror
        ShotVariant("C", "subtle_handheld", "50mm MS", "partial_glimpse", False, "supernatural_hint", 2, 4),  # Fleeting
    ],

    # Investigation - character examining/searching
    # Medium tracking, medium POV, short clue insert
    "investigation": [
        ShotVariant("A", "slow_tracking", "35mm MS", "following_search", True, "investigation_master", 8, 14),
        ShotVariant("B", "pov_tilt", "50mm MCU", "examining_detail", False, "pov_discovery", 6, 10),
        ShotVariant("C", "locked", "100mm ECU", "clue_detail", False, "evidence_insert", 3, 4),  # Quick insert
    ],

    # Escape/pursuit - kinetic action
    # All SHORT for kinetic energy
    "escape_pursuit": [
        ShotVariant("A", "handheld_chase", "24mm WS", "full_body_running", True, "action_wide", 5, 8),  # Fast
        ShotVariant("B", "whip_pan", "35mm MS", "looking_back", True, "tension_glance", 2, 4),  # Very quick
        ShotVariant("C", "locked", "50mm MCU", "obstacle_or_pursuer", False, "threat_detail", 3, 6),  # Quick threat
    ],

    # Emotional moment - character processing
    # Long for emotional weight, medium anchor, short detail
    "emotional_beat": [
        ShotVariant("A", "slow_push", "50mm MS", "body_language_full", True, "emotional_master", 8, 16),  # Long emotion
        ShotVariant("B", "locked", "85mm CU", "eyes_emotion", True, "emotional_anchor", 6, 12),
        ShotVariant("C", "locked", "100mm ECU", "telling_detail", False, "emotional_detail", 4, 6),
    ],

    # Default generic - balanced coverage
    # Medium across the board
    "default_generic": [
        ShotVariant("A", "slow_crane_descending", "35mm MS", "balanced_composition", True, "master", 7, 12),
        ShotVariant("B", "locked", "50mm MCU", "medium_close", True, "coverage", 5, 10),
        ShotVariant("C", "locked", "85mm CU", "detail_insert", False, "insert", 4, 6),
    ],
}


def classify_beat_pattern(beat: Dict, scene: Dict) -> str:
    """
    Analyze beat content to select the most appropriate shot pattern.
    Returns a key from SHOT_PATTERNS.
    """
    # Combine all text for analysis
    beat_text = json.dumps(beat).lower()
    description = beat.get('description', '').lower()
    dialogue = beat.get('dialogue', '').lower()
    action = beat.get('character_action', '').lower()
    beat_label = beat.get('beat', '').lower()

    combined = f"{beat_text} {description} {dialogue} {action} {beat_label}"

    # Priority-ordered pattern matching

    # 1. Supernatural/ghost - highest priority for horror
    if any(kw in combined for kw in ['ghost', 'apparition', 'spirit', 'supernatural', 'haunting',
                                      'specter', 'phantom', 'ethereal', 'otherworldly', 'possession']):
        return "apparition_supernatural"

    # 2. Ritual/ceremony - gothic horror staple
    if any(kw in combined for kw in ['ritual', 'ceremony', 'summoning', 'incantation', 'sacrifice',
                                      'altar', 'candle', 'symbol', 'circle', 'chanting', 'culminates']):
        return "horror_ritual"

    # 3. Escape/chase - kinetic action
    if any(kw in combined for kw in ['escape', 'flee', 'chase', 'run', 'pursuit', 'running',
                                      'hurry', 'rush', 'frantic']):
        return "escape_pursuit"

    # 4. Confrontation - tension scenes
    if any(kw in combined for kw in ['confront', 'argue', 'conflict', 'tension', 'standoff',
                                      'accusation', 'demand', 'threaten', 'challenge']):
        return "confrontation"

    # 5. Discovery/revelation
    if any(kw in combined for kw in ['discover', 'reveal', 'find', 'realize', 'uncover',
                                      'revelation', 'secret', 'hidden', 'truth']):
        return "discovery_revelation"

    # 6. Investigation/search
    if any(kw in combined for kw in ['examine', 'search', 'investigate', 'explore', 'look for',
                                      'inspect', 'study', 'analyze']):
        return "investigation"

    # 7. Dialogue - check for conversation indicators
    if dialogue or any(kw in combined for kw in ['says', 'tells', 'asks', 'replies', 'speaks',
                                                   'conversation', 'discusses', 'explains']):
        # Check if it's a two-hander or solo delivery
        chars = scene.get('characters_present', [])
        if len(chars) >= 2:
            return "dialogue_two_hander"
        return "solo_isolation"

    # 8. Solo/isolation
    if any(kw in combined for kw in ['alone', 'isolated', 'solitary', 'trapped', 'confined',
                                      'locked', 'waiting', 'contemplating']):
        return "solo_isolation"

    # 9. Travel/movement
    if any(kw in combined for kw in ['travel', 'walking', 'moving', 'entering', 'arriving',
                                      'approaching', 'leaving', 'corridor', 'hallway']):
        return "travel_exterior"

    # 10. Emotional moments
    if any(kw in combined for kw in ['grief', 'tears', 'crying', 'sobbing', 'mourning',
                                      'overwhelmed', 'devastated', 'emotional', 'heartbreak']):
        return "emotional_beat"

    # Default fallback
    return "default_generic"


def parse_lens_size(lens_and_size: str) -> Tuple[int, str]:
    """Parse '85mm CU' into (85, 'CU')."""
    match = re.match(r'(\d+)mm\s+(\w+)', lens_and_size)
    if match:
        return int(match.group(1)), match.group(2)
    return 35, "MS"  # Fallback


class BeatToShotSpecGenerator:
    """
    Converts validated story beats into ShotSpec objects
    using cinema library templates
    """

    NAME_ALIASES = {
        "evelyn": "Evelyn Ravencroft",
        "arthur": "Arthur Pembroke",
        "clara": "Clara Whitmore",
        "elias": "Elias Finch",
        "lady margaret": "Lady Margaret Ravencroft",
        "lady margaret ravencroft": "Lady Margaret Ravencroft",
        "child": "Ravencroft Heir Child",
        "heir child": "Ravencroft Heir Child"
    }

    def __init__(
        self,
        cinema_library_path: str = "cinema_library.json",
        story_bible_path: str = "blackwood_story_bible.json"
    ):
        self.cinema_library = self._load_json(cinema_library_path)
        self.story_bible = self._load_json(story_bible_path)

        # Extract character lookup
        self.character_lookup = {}
        for char in self.story_bible.get('characters', []):
            name = char.get('name')
            if not name:
                continue
            key = name.lower()
            self.character_lookup[key] = char
            parts = key.split()
            if parts:
                self.character_lookup[parts[0]] = char
                self.character_lookup[parts[-1]] = char

        # Extract location lookup
        raw_locations = self.story_bible.get('locations')
        if not raw_locations:
            raw_locations = self.story_bible.get('key_locations', [])
        self.locations = {
            loc['name']: loc
            for loc in raw_locations
            if isinstance(loc, dict) and loc.get('name')
        }

        # Template lookup
        self.templates = self.cinema_library.get('templates', {})

        logger.info("="*80)
        logger.info("🎬 BEAT → SHOTSPEC GENERATOR INITIALIZED")
        logger.info("="*80)
        logger.info(f"📚 Loaded {len(self.templates)} cinema templates")
        logger.info(f"👥 Loaded {len(self.character_lookup)} characters")
        logger.info(f"📍 Loaded {len(self.locations)} locations")
        logger.info("="*80)

    def _load_json(self, path: str) -> Dict:
        """Load JSON file"""
        with open(path, 'r') as f:
            return json.load(f)

    def _classify_beat(self, beat: Dict) -> str:
        """
        Classify beat type based on content
        Returns template key from cinema_library
        """
        # Check for explicit beat type
        if 'beat_type' in beat:
            return beat['beat_type']

        # Classify by content
        beat_text = json.dumps(beat).lower()

        # Ghost appearance
        if any(keyword in beat_text for keyword in ['ghost', 'apparition', 'supernatural', 'spirit']):
            return 'apparition_insert'

        # Escape/chase
        if any(keyword in beat_text for keyword in ['escape', 'flee', 'chase', 'run', 'pursuit']):
            return 'escape_handheld'

        # Trapped/isolated
        if any(keyword in beat_text for keyword in ['trapped', 'locked', 'isolated', 'alone', 'confined']):
            return 'isolation_static'

        # Discovery/revelation
        if any(keyword in beat_text for keyword in ['discover', 'reveal', 'find', 'realize', 'uncover']):
            return 'revelation_slow_dolly'

        # Investigation
        if any(keyword in beat_text for keyword in ['examine', 'search', 'investigate', 'explore']):
            return 'investigation_medium'

        # Dialogue
        if 'dialogue' in beat or 'conversation' in beat_text:
            return 'dialogue_two_shot'

        # Confrontation
        if any(keyword in beat_text for keyword in ['confront', 'argue', 'conflict', 'face off']):
            return 'confrontation_close'

        # POV/subjective
        if any(keyword in beat_text for keyword in ['pov', 'perspective', 'sees', 'watches']):
            return 'pov_subjective'

        # Establishing/transition
        if any(keyword in beat_text for keyword in ['establish', 'location', 'arrival', 'enter']):
            return 'transition_environment'

        # Default to dread build
        return 'dread_build_wide'

    def _select_template(self, beat_type: str, beat: Dict) -> Dict:
        """Select appropriate template from cinema library"""
        # Direct lookup
        if beat_type in self.templates:
            return self.templates[beat_type]

        # Fallback to dread_build_wide
        logger.warning(f"   ⚠️  Unknown beat type '{beat_type}', using dread_build_wide")
        return self.templates['dread_build_wide']

    def _get_character_descriptions(self, character_names: List[str]) -> List[Dict]:
        """Get full character descriptions from story bible - ENHANCED"""
        descriptions = []
        for raw_name in character_names:
            if not raw_name:
                continue

            # Try NAME_ALIASES first
            canonical = self.NAME_ALIASES.get(str(raw_name).strip().lower(), raw_name)
            name_key = str(canonical).strip().lower()

            # Try exact match
            char = self.character_lookup.get(name_key)

            # Try multi-word partial match (all words)
            if not char and " " in name_key:
                parts = name_key.split()
                for part in parts:
                    if part in self.character_lookup:
                        char = self.character_lookup[part]
                        logger.info(f"   Matched '{raw_name}' via partial key '{part}'")
                        break

            # Try first word only
            if not char:
                first_word = name_key.split()[0] if name_key else ""
                if first_word and first_word in self.character_lookup:
                    char = self.character_lookup[first_word]
                    logger.info(f"   Matched '{raw_name}' via first word '{first_word}'")

            if char:
                descriptions.append({
                    'name': char.get('name', raw_name),
                    'physical': char.get('visual_markers', {}).get('physical', ''),
                    'costume': char.get('visual_markers', {}).get('costume', ''),
                    'signature_items': char.get('visual_markers', {}).get('signature_items', ''),
                    'personality': char.get('personality_traits', [])
                })
                logger.info(f"   ✓ Loaded character: {char.get('name', raw_name)}")
            else:
                logger.warning(f"   ⚠️  Character '{raw_name}' not found in story bible")

        return descriptions

    def _build_cinematic_prompt(
        self,
        beat: Dict,
        template: Dict,
        characters: List[Dict],
        location: Optional[Dict],
        angle: str
    ) -> str:
        """
        Build cinema-literate prompt from template + metadata

        Format: Camera/lens specs, character descriptions, blocking,
        lighting details, emotional action, narrative purpose
        """
        parts = []

        # 1. Camera and lens
        camera_desc = f"{template['camera_move']} {template['lens_mm']}mm {template['scale']}"
        if template.get('speed'):
            camera_desc += f" at {template['speed']}"
        parts.append(camera_desc)

        # 2. Character descriptions (if present) - WITH OFF-SCREEN HANDLING
        if characters and angle != 'C':  # C angle often environment-only
            char_descs = []

            # Detect off-screen characters from dialogue
            off_screen_chars = set()
            dialogue = beat.get('dialogue', '')
            if dialogue:
                import re
                # Match pattern: "CHARACTER (O.S.)" or "CHARACTER(O.S.)"
                os_matches = re.findall(r'(\w+)\s*\(O\.S\.\)', dialogue, re.IGNORECASE)
                for match in os_matches:
                    off_screen_chars.add(match.lower())
                    logger.info(f"   Detected off-screen character: {match}")

            for char in characters:
                # Check if this character is marked off-screen using set intersection
                # This handles multi-word names like "Ravencroft Heir Child"
                char_words = set(char['name'].lower().split())

                # Skip if ANY word in character name matches off_screen markers
                if char_words & off_screen_chars:  # Set intersection
                    logger.info(f"   Excluding {char['name']} from visual (marked O.S.)")
                    continue

                # Build character description with signature items (BUG #5 fix)
                desc = f"{char['name']} ({char['physical']}, wearing {char['costume']}"
                if char.get('signature_items'):
                    desc += f", holding {char['signature_items']}"
                desc += ")"
                char_descs.append(desc)

            if char_descs:
                parts.append(", ".join(char_descs))

        # 3. Blocking
        blocking = template['blocking']
        if angle == 'A':
            blocking = blocking.replace('two-shot', 'wide establishing')
        elif angle == 'C':
            blocking = 'environment detail, no characters visible'
        parts.append(blocking)

        # 3.5. Props (from beat) - BUG #3 FIX
        if beat.get('props'):
            prop_list = ", ".join(beat['props'])
            parts.append(prop_list)

        # 4. Location context
        if location:
            loc_desc = location.get('description', '')
            if loc_desc:
                parts.append(loc_desc)

        # 5. Lighting (detailed)
        light = template['lighting']
        light_desc = f"{light['style']} lighting"
        if 'color_temp' in light:
            light_desc += f", {light['color_temp']}"
        if 'ratios' in light:
            light_desc += f", {light['ratios']}"
        if 'atmosphere' in light:
            light_desc += f", {light['atmosphere']}"
        parts.append(light_desc)

        # 6. Emotional action (from beat)
        if 'character_action' in beat:
            parts.append(beat['character_action'])
        if 'emotional_state' in beat:
            parts.append(f"emotional state: {beat['emotional_state']}")

        # 7. Narrative purpose (from beat)
        if 'revelation' in beat or 'reveal' in beat:
            parts.append(beat.get('revelation', beat.get('reveal', '')))

        # 8. Visual motifs (from beat)
        if 'visual' in beat:
            parts.append(beat['visual'])

        # Combine with proper grammar
        prompt = ", ".join(filter(None, parts))

        # Add period continuity
        period = self.story_bible.get('time_period') or self.story_bible.get('season') or "Victorian era 1893"
        prompt += f", {period} period authentic"

        return prompt

    def _expand_semantic_prompt(
        self,
        beat: Dict,
        scene: Dict,
        variant: ShotVariant,
        characters: List[Dict],
        location: Optional[Dict]
    ) -> str:
        """
        Build a semantically rich prompt with deep contextual understanding.
        Goes beyond surface description to capture emotional and narrative depth.
        """
        parts = []

        # 1. Camera and technical specs from variant
        lens_mm, scale = parse_lens_size(variant.lens_and_size)
        camera_desc = f"{variant.camera_move.replace('_', ' ')} {lens_mm}mm {scale}"
        parts.append(camera_desc)

        # 2. Composition directive
        composition = variant.composition_tag.replace('_', ' ')
        parts.append(f"composition: {composition}")

        # 3. Character descriptions with SEMANTIC context
        if variant.include_characters and characters:
            char_parts = []
            for char in characters:
                # Build rich character description
                desc = f"{char['name']}"
                if char.get('physical'):
                    desc += f" ({char['physical']}"
                if char.get('costume'):
                    desc += f", wearing {char['costume']}"
                if char.get('signature_items'):
                    desc += f", {char['signature_items']}"
                desc += ")" if '(' in desc else ""
                char_parts.append(desc)
            if char_parts:
                parts.append(", ".join(char_parts))

        # 4. SEMANTIC EXPANSION - Transform shallow descriptions to deep context
        beat_description = beat.get('description', '') or beat.get('beat', '')
        emotional_state = beat.get('emotional_state', '')
        character_action = beat.get('character_action', '')
        revelation = beat.get('revelation', '') or beat.get('reveal', '')

        # Expand vague phrases into specific visual/emotional context
        semantic_expansion = self._semantic_deepening(
            beat_description, emotional_state, character_action, revelation, scene
        )
        if semantic_expansion:
            parts.append(semantic_expansion)

        # 5. Location with atmospheric detail
        if location:
            loc_desc = location.get('description', '')
            atmosphere = location.get('atmosphere', '')
            if loc_desc:
                parts.append(loc_desc)
            if atmosphere:
                parts.append(atmosphere)

        # 6. Props (context-aware)
        if beat.get('props'):
            props_context = self._contextualize_props(beat['props'], beat_description)
            parts.append(props_context)

        # 7. Lighting from template (enhanced)
        if hasattr(self, '_current_template') and self._current_template:
            light = self._current_template.get('lighting', {})
            if light:
                light_desc = f"{light.get('style', 'natural')} lighting"
                if light.get('color_temp'):
                    light_desc += f", {light['color_temp']}"
                if light.get('atmosphere'):
                    light_desc += f", {light['atmosphere']}"
                parts.append(light_desc)

        # 8. Shot role context
        parts.append(f"[{variant.role.replace('_', ' ')}]")

        # 9. Period authenticity
        period = self.story_bible.get('time_period') or self.story_bible.get('season') or "Victorian era 1893"
        parts.append(f"{period} period authentic")

        # Combine with proper grammar
        prompt = ", ".join(filter(None, parts))
        return prompt

    def _semantic_deepening(
        self,
        description: str,
        emotional_state: str,
        action: str,
        revelation: str,
        scene: Dict
    ) -> str:
        """
        Transform vague/shallow descriptions into rich semantic context.
        'Something goes wrong' → specific visual/emotional manifestation.
        """
        semantic_parts = []

        # Map common vague phrases to specific visual descriptions
        VAGUE_TO_SPECIFIC = {
            "something goes wrong": "moment of horrified realization, face contorting with dawning dread, hands trembling",
            "things get worse": "escalating terror visible in widened eyes, backing away slowly, breath catching",
            "tension builds": "palpable unease, shifting weight anxiously, furtive glances at shadows",
            "discovers the truth": "shock of revelation washing over features, color draining from face",
            "realizes the danger": "sudden freeze of recognition, survival instinct awakening",
            "confronts": "steeling resolve visible in set jaw, squared shoulders despite trembling hands",
            "escapes": "desperate flight, adrenaline-fueled urgency, looking back with terror",
            "investigates": "cautious approach, examining with mix of curiosity and dread",
            "waits": "tense stillness, hyperaware of every sound, time stretching agonizingly",
            "remembers": "distant gaze as memory surfaces, present fading as past intrudes",
        }

        # Check for vague phrases and expand
        desc_lower = description.lower()
        for vague, specific in VAGUE_TO_SPECIFIC.items():
            if vague in desc_lower:
                semantic_parts.append(specific)
                break

        # Add emotional state with visual manifestation
        if emotional_state:
            emotion_visual = self._emotion_to_visual(emotional_state)
            if emotion_visual:
                semantic_parts.append(emotion_visual)

        # Add action with cinematic framing
        if action:
            semantic_parts.append(action)

        # Add revelation/story beat significance
        if revelation:
            semantic_parts.append(f"narrative pivot: {revelation}")

        # Scene tone integration
        scene_tone = scene.get('tone', '') or scene.get('scene_purpose', '')
        if scene_tone and scene_tone not in ' '.join(semantic_parts):
            semantic_parts.append(f"tone: {scene_tone}")

        return ", ".join(filter(None, semantic_parts))

    def _emotion_to_visual(self, emotion: str) -> str:
        """Convert emotional state to visible physical manifestation."""
        EMOTION_VISUALS = {
            "fear": "wide eyes catching light, shallow rapid breathing, trembling hands",
            "dread": "slow creeping horror across features, involuntary step backward",
            "terror": "paralyzed with fear, mouth agape in silent scream",
            "grief": "tears welling, shoulders hunched inward, face crumpling",
            "anger": "jaw clenched, nostrils flared, hands balled into fists",
            "determination": "steely gaze, set jaw, purposeful stance",
            "confusion": "furrowed brow, head tilted, searching eyes",
            "shock": "frozen mid-motion, blood draining from face",
            "suspicion": "narrowed eyes, guarded posture, calculated stillness",
            "hope": "light returning to eyes, tentative straightening of posture",
            "despair": "hollow gaze, slack posture, all fight drained away",
            "curiosity": "leaning forward, eyes bright with interest",
            "resignation": "shoulders dropping, long exhale, accepting fate",
        }
        emotion_lower = emotion.lower()
        for key, visual in EMOTION_VISUALS.items():
            if key in emotion_lower:
                return visual
        return emotion  # Return original if no match

    def _contextualize_props(self, props: List[str], context: str) -> str:
        """Make props contextually relevant to the scene."""
        if not props:
            return ""
        prop_list = ", ".join(props)
        # Add context about how props are used/positioned
        return f"visible props: {prop_list}"

    def generate_shotspecs(
        self,
        beat: Dict,
        scene: Dict,
        beat_index: int = 0
    ) -> List[Dict]:
        """
        Convert validated beat to 3 ShotSpec objects (ABC coverage)
        using PATTERN-BASED shot selection for cinematographic variety.

        Args:
            beat: Validated beat dictionary
            scene: Scene metadata (location, characters_present, etc.)
            beat_index: Index within scene for shot numbering

        Returns:
            List of 3 ShotSpec dictionaries (A, B, C angles) with varied cameras
        """
        # Classify beat using old system for template selection
        beat_type = self._classify_beat(beat)

        # Select template (for lighting, sound, etc.)
        template = self._select_template(beat_type, beat)
        self._current_template = template  # Store for prompt building

        # NEW: Select shot pattern for ABC variety
        pattern_key = classify_beat_pattern(beat, scene)
        pattern_variants = SHOT_PATTERNS.get(pattern_key, SHOT_PATTERNS["default_generic"])

        logger.info(f"   Pattern: {pattern_key} → {len(pattern_variants)} variants")

        # Get character descriptions
        char_names = scene.get('characters_present', [])
        characters = self._get_character_descriptions(char_names)

        # Get location - FUZZY MATCHING (BUG #2 FIX)
        location = None
        if 'location' in scene:
            loc_name = scene['location'].lower()

            # Try exact match first
            for loc_key, loc_data in self.locations.items():
                if loc_key.lower() == loc_name:
                    location = loc_data
                    logger.info(f"   Location exact match: {loc_key}")
                    break

            # Try partial match (either direction)
            if not location:
                for loc_key, loc_data in self.locations.items():
                    loc_key_lower = loc_key.lower()
                    loc_words = set(loc_key_lower.split())
                    scene_words = set(loc_name.replace('_', ' ').split())

                    if loc_words & scene_words:
                        location = loc_data
                        logger.info(f"   Location fuzzy match: {loc_key} (from {scene['location']})")
                        break

            if not location:
                logger.warning(f"   ⚠️  Location '{scene['location']}' not matched in story bible")

        # Build ABC coverage using PATTERN VARIANTS
        shotspecs = []
        for variant in pattern_variants:
            lens_mm, scale = parse_lens_size(variant.lens_and_size)

            # Build semantically rich prompt
            prompt = self._expand_semantic_prompt(
                beat=beat,
                scene=scene,
                variant=variant,
                characters=characters if variant.include_characters else [],
                location=location
            )

            shotspec = {
                "shot_id": f"{scene['scene_id']}_{beat_index:03d}{variant.suffix}",
                "beat_id": beat.get('beat_id', f"beat_{beat_index:03d}"),
                "scale": scale,
                "lens_mm": lens_mm,
                "camera_move": variant.camera_move,
                "speed": template.get('speed'),
                "depth_of_field": template.get('depth_of_field', 'standard'),
                "lut": "tungsten_cool_split",
                "blocking": template.get('blocking', ''),
                "lighting": template.get('lighting', {}),
                "sound_cues": template.get('sound_cues', []),
                "dialogue_text": beat.get('dialogue'),
                "props": beat.get('props', []),
                "constraints": {
                    "period_authentic": True,
                    "no_neon": True,
                    "no_captions": True,
                    "no_subtitles": True,
                    "no_modern_elements": True
                },
                "prompt": prompt,
                "emotional_intent": beat.get('emotional_state'),
                "narrative_purpose": beat.get('revelation', beat.get('reveal')),
                "template_used": beat_type,
                "pattern_used": pattern_key,
                "shot_role": variant.role,
                "composition": variant.composition_tag,
                "reference_film": template.get('reference_film'),
                # FIXED: Duration at top level for UI visibility
                # FIXED: Duration snapped to valid LTXv2 intervals (4-20s, 2s steps)
                "duration": variant.duration_seconds,
                "duration_target": f"{variant.duration_seconds} seconds",
                "ltx_duration_seconds": snap_to_ltx_duration(variant.ltx_duration_seconds),
                "pacing": template.get('pacing')
            }

            # Add quantum params if present
            if 'quantum_params' in beat:
                shotspec['quantum_params'] = beat['quantum_params']

            shotspecs.append(shotspec)

            logger.info(f"      {variant.suffix}: {variant.camera_move} {lens_mm}mm {scale} ({variant.role})")

        return shotspecs

    def process_scene(self, scene: Dict) -> List[Dict]:
        """
        Process entire scene, generating ShotSpecs for all beats

        Args:
            scene: Scene dictionary with beats

        Returns:
            List of all ShotSpec dictionaries for scene
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🎬 PROCESSING SCENE: {scene.get('scene_title', 'Unknown')}")
        logger.info(f"{'='*80}")

        all_shotspecs = []
        beats = scene.get('beats', [])

        for beat_idx, beat in enumerate(beats):
            logger.info(f"\n   Beat {beat_idx + 1}/{len(beats)}: {beat.get('beat', 'Unknown')}")

            shotspecs = self.generate_shotspecs(
                beat=beat,
                scene=scene,
                beat_index=beat_idx
            )

            logger.info(f"   ✅ Generated {len(shotspecs)} ShotSpecs (ABC coverage)")
            for spec in shotspecs:
                logger.info(f"      • {spec['shot_id']}: {spec['scale']} {spec['lens_mm']}mm {spec['camera_move']}")

            all_shotspecs.extend(shotspecs)

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ SCENE COMPLETE: {len(all_shotspecs)} total ShotSpecs")
        logger.info(f"{'='*80}")

        return all_shotspecs

    def process_episode(self, episode: Dict, output_path: str = None) -> Dict:
        """
        Process entire episode, generating ShotSpecs for all scenes

        Args:
            episode: Episode structure dictionary
            output_path: Optional path to save ShotSpec manifest

        Returns:
            Complete ShotSpec manifest
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🎬 PROCESSING EPISODE: {episode.get('episode_title', 'Unknown')}")
        logger.info(f"{'='*80}")

        manifest = {
            "episode_title": episode.get('episode_title'),
            "episode_metadata": {
                "total_scenes": len(episode.get('scenes', [])),
                "total_runtime": episode.get('total_runtime'),
                "story_bible": "blackwood_story_bible.json",
                "cinema_library": "cinema_library.json"
            },
            "scenes": []
        }

        total_shotspecs = 0
        for scene in episode.get('scenes', []):
            shotspecs = self.process_scene(scene)

            manifest['scenes'].append({
                "scene_id": scene['scene_id'],
                "scene_title": scene['scene_title'],
                "shotspecs": shotspecs
            })

            total_shotspecs += len(shotspecs)

        manifest['episode_metadata']['total_shotspecs'] = total_shotspecs

        # Save manifest
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"\n✅ ShotSpec manifest saved: {output_path}")

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ EPISODE COMPLETE")
        logger.info(f"   Total Scenes: {manifest['episode_metadata']['total_scenes']}")
        logger.info(f"   Total ShotSpecs: {total_shotspecs}")
        logger.info(f"{'='*80}")

        return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate ShotSpecs from validated beats")
    parser.add_argument("--episode", required=True, help="Episode JSON file")
    parser.add_argument("--scene", help="Process single scene ID (optional)")
    parser.add_argument("--output", help="Output ShotSpec manifest path")
    args = parser.parse_args()

    # Load episode
    with open(args.episode, 'r') as f:
        episode = json.load(f)

    # Initialize generator
    generator = BeatToShotSpecGenerator()

    # Process scene or full episode
    if args.scene:
        # Find scene
        scene = None
        for s in episode.get('scenes', []):
            if s['scene_id'] == args.scene:
                scene = s
                break

        if not scene:
            logger.error(f"❌ Scene {args.scene} not found")
            exit(1)

        shotspecs = generator.process_scene(scene)

        # Save single scene
        if args.output:
            output = {
                "scene_id": scene['scene_id'],
                "scene_title": scene['scene_title'],
                "shotspecs": shotspecs
            }
            with open(args.output, 'w') as f:
                json.dump(output, f, indent=2)
            logger.info(f"\n✅ Scene ShotSpecs saved: {args.output}")
    else:
        # Process full episode
        output_path = args.output or f"shotspec_manifest_{episode.get('episode_title', 'episode')}.json"
        manifest = generator.process_episode(episode, output_path)
