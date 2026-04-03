"""
ATLAS V21.10 - ACTOR INTENT LAYER
Per-character micro-action, tempo, eyeline, and intent extraction & injection

This module extracts psychological and physical intent from story beats and 
injects character-specific micro-actions into nano and LTX prompts.

Version: V21.10
Author: ATLAS Narrative Engine
Status: PRODUCTION
"""

import logging
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
import json

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ============================================================================
# CHARACTER INTENT DATA STRUCTURES
# ============================================================================

@dataclass
class CharacterIntent:
    """Per-character intent snapshot for a shot."""
    
    emotion: str  # anxious, commanding, defiant, grieving, suspicious, calm, fearful, angry, tender, resigned
    stature: str  # rigid, relaxed, hunched, upright, leaning, collapsed, guarded, open
    eyeline_target: str  # character name, object, "camera", "distance", "floor", "away"
    tempo: str  # still, slow, measured, normal, urgent, frantic
    micro_action: str  # specific physical action: "grips candle tightly", "adjusts collar"
    hand_state: str  # free, holding_candle, gripping_arm, clasped, pointing, reaching, clenched
    movement_intent: str  # none, approach, retreat, circle, turn_away, step_forward, kneel, rise
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_nano_marker(self, character_name: str) -> str:
        """Generate nano_prompt marker for this character."""
        return (
            f"{character_name} stands {self.stature}, "
            f"eyes on {self.eyeline_target}, "
            f"{self.micro_action}"
        )
    
    def to_ltx_marker(self, character_name: str) -> str:
        """Generate LTX motion prompt marker for this character."""
        markers = []
        if self.movement_intent and self.movement_intent != "none":
            markers.append(f"{character_name} {self.movement_intent}")
        markers.append(f"{self.micro_action}")
        markers.append(f"{self.tempo} pace")
        return ", ".join(markers)


# ============================================================================
# EMOTION-GESTURE MAPPING
# ============================================================================

EMOTION_GESTURE_MAP: Dict[str, List[str]] = {
    "anxious": [
        "fingers fidget with fabric",
        "weight shifts from foot to foot",
        "jaw tightens visibly",
        "breath quickens slightly",
        "eyes dart to exits",
        "hands clutch together",
    ],
    "commanding": [
        "chin raised imperiously",
        "hands rest at sides, fingers spread",
        "shoulders squared and broad",
        "stance widens to claim space",
        "gaze steady and piercing",
        "breathing deep and controlled",
    ],
    "defiant": [
        "arms crossed over chest",
        "jaw set firm",
        "eye contact unwavering",
        "body angled away protectively",
        "head tilted in challenge",
        "lips pressed thin",
    ],
    "grieving": [
        "shoulders rounded inward",
        "eyes downcast and distant",
        "hand moves to chest",
        "breathing shallow and slow",
        "weight sinks forward",
        "movements deliberately gentle",
    ],
    "suspicious": [
        "head tilted in interrogation",
        "eyes narrowed and searching",
        "body angled away slightly",
        "hands held close",
        "jaw shifts thinking",
        "gaze doesn't break contact",
    ],
    "calm": [
        "posture relaxed but alert",
        "breathing steady and deep",
        "hands rest open",
        "expression serene",
        "movements economical",
        "eyes soft but present",
    ],
    "fearful": [
        "body shrinks inward",
        "hands clutch reflexively",
        "eyes dart nervously",
        "breathing becomes rapid",
        "stance narrows",
        "movements become small and cautious",
    ],
    "angry": [
        "fists clench tightly",
        "jaw works with tension",
        "breathing becomes sharp",
        "body leans forward aggressively",
        "eyes flash with intensity",
        "muscles visibly tense",
    ],
    "tender": [
        "head tilts in sympathy",
        "hand reaches out gently",
        "expression softens noticeably",
        "breathing slows",
        "touch becomes careful",
        "eyes fill with warmth",
    ],
    "resigned": [
        "shoulders slump slightly",
        "gaze becomes unfocused",
        "movements lose urgency",
        "breathing becomes regular",
        "hands settle passively",
        "posture accepts defeat",
    ],
}

# ============================================================================
# EYELINE RULES BY SHOT TYPE
# ============================================================================

EYELINE_RULES: Dict[str, str] = {
    "OTS_A": "B character",  # Over-shoulder shot of A looks at B
    "OTS_B": "A character",  # Over-shoulder shot of B looks at A
    "close": "dialogue partner or specified target",
    "ECU": "dialogue partner or specified target",
    "reaction": "speaker",
    "two_shot": "dialogue partner",
    "establishing": "distance",
    "medium": "dialogue partner or environment",
    "wide": "environment or distance",
    "insert": "object or detail",
    "cutaway": "environment",
}

# ============================================================================
# EMOTION KEYWORD EXTRACTION (IMPROVED MATCHING)
# ============================================================================

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "grieving": ["grief", "griev", "mourn", "sorrow", "tears", "tearful", "weep", "devastated", "heartbroken", "bereav"],
    "anxious": ["anxious", "worried", "nervous", "tense", "uneasy", "apprehensive", "disturb", "unease"],
    "commanding": ["command", "order", "demand", "authority", "powerful", "dominant", "control", "authorit"],
    "defiant": ["defiant", "rebellious", "refuse", "resist", "confront", "challenge", "oppose", "opposes"],
    "suspicious": ["suspicious", "distrust", "doubt", "question", "wary", "guard", "cautious", "skeptic"],
    "calm": ["calm", "serene", "peaceful", "compos", "tranquil", "ease", "center"],
    "fearful": ["fear", "terrified", "scared", "dread", "panic", "horror", "alarm", "frighten", "terror"],
    "angry": ["anger", "furious", "enrage", "wrath", "hostile", "bitter", "resentful", "resentment"],
    "tender": ["tender", "lov", "affection", "gentle", "car", "devot", "warm"],
    "resigned": ["resign", "accept", "surrender", "give up", "defeat", "weary", "spent"],
}

# ============================================================================
# MOVEMENT INTENT PATTERNS
# ============================================================================

MOVEMENT_KEYWORDS: Dict[str, List[str]] = {
    "approach": ["approach", "walk toward", "move closer", "step forward", "advance", "enter"],
    "retreat": ["retreat", "back away", "step back", "withdraw", "move away", "flee"],
    "circle": ["circle", "move around", "pace", "orbit"],
    "turn_away": ["turn away", "look away", "turn to leave", "look back"],
    "step_forward": ["step forward", "take a step", "advance", "lean in"],
    "kneel": ["kneel", "drop to knee", "bow", "genuflect"],
    "rise": ["rise", "stand up", "get up", "rise to feet", "straighten"],
    "collapse": ["collapse", "fall", "crumple", "sink down"],
}

# ============================================================================
# STATURE & HAND STATE PATTERNS
# ============================================================================

STATURE_KEYWORDS: Dict[str, List[str]] = {
    "rigid": ["stiff", "rigid", "tense", "unbend", "wooden", "unyield"],
    "relaxed": ["relaxed", "loose", "ease", "comfort", "natural"],
    "hunched": ["hunched", "bent", "curved", "stoop", "round", "collapse inward"],
    "upright": ["upright", "straight", "stand tall", "erect", "compos"],
    "leaning": ["lean", "tilt", "angle", "slope", "incline"],
    "collapsed": ["collapse", "crumple", "fallen", "prone", "defeat"],
    "guarded": ["guard", "defensive", "protect", "shield", "close"],
    "open": ["open", "expose", "vulner", "unguard", "receptive"],
}

HAND_STATE_KEYWORDS: Dict[str, List[str]] = {
    "holding_candle": ["candle", "flame", "light", "torch"],
    "gripping_arm": ["grip", "hold", "clutch", "grab arm"],
    "clasped": ["clasp", "hold", "wrap", "intertwine"],
    "pointing": ["point", "indicate", "gesture", "direct"],
    "reaching": ["reach", "extend", "stretch", "grasp"],
    "clenched": ["clench", "fist", "grip", "squeeze"],
}

# ============================================================================
# TEMPO PATTERNS
# ============================================================================

TEMPO_KEYWORDS: Dict[str, List[str]] = {
    "still": ["frozen", "still", "motionless", "statue", "unmov"],
    "slow": ["slowly", "deliberate", "measured", "careful", "gradual"],
    "measured": ["measured", "control", "paced", "even", "steady"],
    "normal": ["normally", "casual", "natural", "ordinary"],
    "urgent": ["quickly", "fast", "urgent", "hurried", "rush"],
    "frantic": ["frantically", "frenzied", "hectic", "wild", "chaotic"],
}

# ============================================================================
# MAIN EXTRACTION FUNCTIONS
# ============================================================================

def extract_emotion_from_beat(beat_description: str) -> str:
    """
    Extract primary emotion from beat description text.
    
    Args:
        beat_description: Text from story bible beat
    
    Returns:
        Emotion string (or "calm" as default)
    """
    if not beat_description:
        return "calm"
    
    text = beat_description.lower()
    
    # Check each emotion's keywords in order of specificity
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                logger.debug(f"[ACTOR_INTENT] Extracted emotion '{emotion}' from beat (matched '{keyword}')")
                return emotion
    
    return "calm"  # Default fallback


def extract_stature_from_beat(beat_description: str) -> str:
    """
    Extract character stature/posture from beat description.
    
    Args:
        beat_description: Text from story bible beat
    
    Returns:
        Stature string (or "upright" as default)
    """
    if not beat_description:
        return "upright"
    
    text = beat_description.lower()
    
    for stature, keywords in STATURE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                logger.debug(f"[ACTOR_INTENT] Extracted stature '{stature}' from beat")
                return stature
    
    return "upright"  # Default fallback


def extract_movement_from_beat(beat_description: str) -> str:
    """
    Extract movement intent from beat description.
    
    Args:
        beat_description: Text from story bible beat
    
    Returns:
        Movement intent string (or "none" as default)
    """
    if not beat_description:
        return "none"
    
    text = beat_description.lower()
    
    for movement, keywords in MOVEMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                logger.debug(f"[ACTOR_INTENT] Extracted movement '{movement}' from beat")
                return movement
    
    return "none"


def extract_hand_state_from_beat(beat_description: str) -> str:
    """
    Extract hand state/props from beat description.
    
    Args:
        beat_description: Text from story bible beat
    
    Returns:
        Hand state string
    """
    if not beat_description:
        return "free"
    
    text = beat_description.lower()
    
    for hand_state, keywords in HAND_STATE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                logger.debug(f"[ACTOR_INTENT] Extracted hand state '{hand_state}' from beat")
                return hand_state
    
    return "free"


def extract_tempo_from_beat(beat_description: str) -> str:
    """
    Extract movement tempo from beat description.
    
    Args:
        beat_description: Text from story bible beat
    
    Returns:
        Tempo string (or "measured" as default)
    """
    if not beat_description:
        return "measured"
    
    text = beat_description.lower()
    
    for tempo, keywords in TEMPO_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                logger.debug(f"[ACTOR_INTENT] Extracted tempo '{tempo}' from beat")
                return tempo
    
    return "measured"


def extract_eyeline_target(
    shot_role: str,
    characters_present: List[str],
    beat_description: str,
    character_idx: int = 0
) -> str:
    """
    Determine eyeline target for character based on shot role and context.
    
    Args:
        shot_role: Shot type (e.g., "OTS_A", "close", "reaction")
        characters_present: List of character names in shot
        beat_description: Beat text for additional context
        character_idx: Index of current character in characters_present list
    
    Returns:
        Eyeline target string
    """
    shot_role_lower = shot_role.lower() if shot_role else ""
    
    # Check EYELINE_RULES for shot type
    for rule_key, rule_val in EYELINE_RULES.items():
        if rule_key.lower() in shot_role_lower:
            # OTS_A/OTS_B have special handling
            if "OTS" in shot_role.upper() and len(characters_present) > 1:
                if "OTS_A" in shot_role.upper():
                    return characters_present[1] if len(characters_present) > 1 else "distance"
                elif "OTS_B" in shot_role.upper():
                    return characters_present[0] if len(characters_present) > 0 else "distance"
            
            # For two-shots and dialogue, look at other character
            if shot_role_lower == "two_shot" and len(characters_present) > 1:
                other_idx = 1 - character_idx
                return characters_present[other_idx]
            
            # Default rule value
            if "dialogue partner" in rule_val:
                return characters_present[1-character_idx] if len(characters_present) > 1 else "camera"
            
            return rule_val
    
    # Check beat for eyeline clues
    if beat_description:
        beat_lower = beat_description.lower()
        for char in characters_present:
            if char.lower() in beat_lower and "looks at" in beat_lower:
                return char
    
    # Default fallbacks
    if len(characters_present) > 1:
        return characters_present[1 - character_idx]
    
    return "distance"


def select_micro_action(emotion: str, beat_description: str = "") -> str:
    """
    Select appropriate micro-action based on emotion.
    Attempts to match beat-specific actions first, then uses generic emotion gestures.
    
    Args:
        emotion: Detected emotion
        beat_description: Original beat text for context
    
    Returns:
        Micro-action string
    """
    # If beat has specific actions, prefer those
    if beat_description:
        # Look for verb patterns that suggest micro-actions
        action_patterns = [
            r"(\w+s\s+(?:the\s+)?\w+(?:\s+\w+)?)",  # "grips the candle", "adjusts collar"
            r"((?:voice|eyes|hands)\s+\w+)",  # "voice quivers", "eyes search"
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, beat_description, re.IGNORECASE)
            if matches:
                logger.debug(f"[ACTOR_INTENT] Extracted specific action: {matches[0]}")
                return matches[0]
    
    # Fall back to emotion-based gesture map
    if emotion in EMOTION_GESTURE_MAP:
        gestures = EMOTION_GESTURE_MAP[emotion]
        # Return first (most common) gesture for this emotion
        return gestures[0] if gestures else "stands naturally"
    
    return "stands naturally"


# ============================================================================
# MAIN CHARACTER INTENT EXTRACTION
# ============================================================================

def extract_character_intent(
    shot: Dict[str, Any],
    beat: Optional[Dict[str, Any]] = None,
    characters_present: Optional[List[str]] = None,
    character_name: str = ""
) -> CharacterIntent:
    """
    Extract full CharacterIntent for a specific character in a shot.
    
    Args:
        shot: Shot dictionary from shot_plan
        beat: Story bible beat (optional)
        characters_present: List of character names in shot
        character_name: Specific character to extract intent for
    
    Returns:
        CharacterIntent dataclass
    """
    if characters_present is None:
        characters_present = shot.get("characters", [])
    
    if not character_name and characters_present:
        character_name = characters_present[0]
    
    beat_description = ""
    if beat:
        beat_description = beat.get("description", "") or beat.get("action", "")
    
    shot_role = shot.get("shot_role", shot.get("shot_type", "medium"))
    
    # Extract intent components
    emotion = extract_emotion_from_beat(beat_description)
    stature = extract_stature_from_beat(beat_description)
    movement = extract_movement_from_beat(beat_description)
    hand_state = extract_hand_state_from_beat(beat_description)
    tempo = extract_tempo_from_beat(beat_description)
    
    char_idx = characters_present.index(character_name) if character_name in characters_present else 0
    eyeline = extract_eyeline_target(shot_role, characters_present, beat_description, char_idx)
    
    micro_action = select_micro_action(emotion, beat_description)
    
    logger.debug(
        f"[ACTOR_INTENT] Extracted intent for {character_name}: "
        f"emotion={emotion}, stature={stature}, movement={movement}"
    )
    
    return CharacterIntent(
        emotion=emotion,
        stature=stature,
        eyeline_target=eyeline,
        tempo=tempo,
        micro_action=micro_action,
        hand_state=hand_state,
        movement_intent=movement,
    )


def extract_all_character_intents(
    shot: Dict[str, Any],
    beat: Optional[Dict[str, Any]] = None,
) -> Dict[str, CharacterIntent]:
    """
    Extract CharacterIntent for ALL characters in a shot.
    
    Args:
        shot: Shot dictionary
        beat: Story bible beat
    
    Returns:
        Dict mapping character name → CharacterIntent
    """
    characters = shot.get("characters", [])
    intents = {}
    
    for char_name in characters:
        try:
            intents[char_name] = extract_character_intent(
                shot, beat, characters, char_name
            )
        except Exception as e:
            logger.warning(f"[ACTOR_INTENT] Failed to extract intent for {char_name}: {e}")
            # Provide fallback intent
            intents[char_name] = CharacterIntent(
                emotion="calm",
                stature="upright",
                eyeline_target="distance",
                tempo="measured",
                micro_action="stands naturally",
                hand_state="free",
                movement_intent="none",
            )
    
    return intents


# ============================================================================
# PROMPT INJECTION
# ============================================================================

def inject_intent_into_nano_prompt(
    nano_prompt: str,
    intents: Dict[str, CharacterIntent]
) -> str:
    """
    Inject character intents into nano_prompt.
    
    Args:
        nano_prompt: Original nano prompt text
        intents: Dict of character name → CharacterIntent
    
    Returns:
        Enhanced nano prompt with intent markers
    """
    if not intents:
        return nano_prompt
    
    # Skip if intent markers already present
    if "stands" in nano_prompt and "eyes on" in nano_prompt:
        logger.debug("[ACTOR_INTENT] Intent markers already present in nano prompt, skipping")
        return nano_prompt
    
    # Build intent section
    intent_lines = []
    for char_name, intent in intents.items():
        marker = intent.to_nano_marker(char_name)
        intent_lines.append(marker)
    
    if not intent_lines:
        return nano_prompt
    
    intent_section = "\n".join(intent_lines)
    
    # Inject before "NO grid" or at end
    if "NO grid" in nano_prompt:
        nano_prompt = nano_prompt.replace("NO grid", f"{intent_section}\n\nNO grid")
    else:
        nano_prompt = f"{nano_prompt}\n\n{intent_section}"
    
    logger.debug(f"[ACTOR_INTENT] Injected intent markers into nano prompt")
    return nano_prompt


def inject_intent_into_ltx_prompt(
    ltx_prompt: str,
    intents: Dict[str, CharacterIntent]
) -> str:
    """
    Inject character intents into LTX motion prompt.
    
    Args:
        ltx_prompt: Original LTX prompt text
        intents: Dict of character name → CharacterIntent
    
    Returns:
        Enhanced LTX prompt with intent markers
    """
    if not intents:
        return ltx_prompt
    
    # Skip if intent markers already present (check for "performs:")
    if "performs:" in ltx_prompt or "character action:" in ltx_prompt:
        logger.debug("[ACTOR_INTENT] Character action markers already present in LTX, skipping")
        return ltx_prompt
    
    # Build intent section for LTX
    intent_lines = []
    for char_name, intent in intents.items():
        marker = intent.to_ltx_marker(char_name)
        intent_lines.append(f"{char_name}: {marker}")
    
    if not intent_lines:
        return ltx_prompt
    
    intent_section = "\n".join(intent_lines)
    
    # Inject before "NO " constraints or at end
    if "NO " in ltx_prompt:
        # Find first "NO" and insert before it
        idx = ltx_prompt.index("NO")
        ltx_prompt = ltx_prompt[:idx] + f"{intent_section}\n\n" + ltx_prompt[idx:]
    else:
        ltx_prompt = f"{ltx_prompt}\n\n{intent_section}"
    
    logger.debug(f"[ACTOR_INTENT] Injected {len(intents)} character intent markers into LTX prompt")
    return ltx_prompt


def inject_intent_into_prompts(
    nano_prompt: str,
    ltx_prompt: str,
    intents: Dict[str, CharacterIntent]
) -> Tuple[str, str]:
    """
    Inject character intents into both nano and LTX prompts.
    
    Args:
        nano_prompt: Nano prompt text
        ltx_prompt: LTX motion prompt text
        intents: Dict of character intents
    
    Returns:
        Tuple of (enhanced nano_prompt, enhanced ltx_prompt)
    """
    nano_prompt = inject_intent_into_nano_prompt(nano_prompt, intents)
    ltx_prompt = inject_intent_into_ltx_prompt(ltx_prompt, intents)
    return nano_prompt, ltx_prompt


# ============================================================================
# BATCH ENRICHMENT
# ============================================================================

def enrich_shot_plan_with_intent(
    shots: List[Dict[str, Any]],
    story_bible: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Enrich all shots in a shot plan with character intent data.
    
    This is the main entry point for integrating actor_intent_layer into the pipeline.
    Adds `actor_intent` field to each shot (Dict[str, CharacterIntent dict]).
    
    Args:
        shots: List of shot dictionaries from shot_plan
        story_bible: Story bible data (optional)
    
    Returns:
        Enriched shots list with actor_intent field
    """
    if not shots:
        logger.warning("[ACTOR_INTENT] No shots provided for enrichment")
        return shots
    
    logger.info(f"[ACTOR_INTENT] Beginning enrichment of {len(shots)} shots")
    
    enriched_shots = []
    skipped = 0
    
    for shot in shots:
        # Skip if already enriched (idempotent)
        if "actor_intent" in shot:
            logger.debug(f"[ACTOR_INTENT] Shot {shot.get('shot_id')} already has actor_intent, skipping")
            skipped += 1
            enriched_shots.append(shot)
            continue
        
        # Find matching beat from story bible
        beat = None
        if story_bible:
            scene_id = shot.get("scene_id")
            # Handle both dict and list format for scenes
            scenes_data = story_bible.get("scenes", {})
            if isinstance(scenes_data, list):
                scene = next((s for s in scenes_data if s.get("scene_id") == scene_id), {})
            else:
                scene = scenes_data.get(scene_id, {})
            beats = scene.get("beats", [])
            
            # Simple beat matching: use shot index within scene
            shot_index = shot.get("shot_index", 0)
            if 0 <= shot_index < len(beats):
                beat = beats[shot_index]
        
        # Extract intents for all characters in shot
        intents = extract_all_character_intents(shot, beat)
        
        # Add actor_intent field to shot
        shot_copy = shot.copy()
        shot_copy["actor_intent"] = {
            char_name: intent.to_dict()
            for char_name, intent in intents.items()
        }
        
        # Optionally inject into prompts (non-breaking, only if prompts exist)
        if shot_copy.get("nano_prompt"):
            ltx_prompt = shot_copy.get("ltx_motion_prompt", "")
            try:
                shot_copy["nano_prompt"], shot_copy["ltx_motion_prompt"] = inject_intent_into_prompts(
                    shot_copy["nano_prompt"],
                    ltx_prompt,
                    intents
                )
            except Exception as e:
                logger.warning(f"[ACTOR_INTENT] Failed to inject intent into shot {shot.get('shot_id')}: {e}")
        
        enriched_shots.append(shot_copy)
    
    logger.info(
        f"[ACTOR_INTENT] Enrichment complete: {len(enriched_shots) - skipped} shots enriched, "
        f"{skipped} skipped (already enriched)"
    )
    
    return enriched_shots


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_emotion(emotion: str) -> bool:
    """Validate that emotion string is in known emotion set."""
    return emotion in EMOTION_GESTURE_MAP


def validate_intent(intent: CharacterIntent) -> bool:
    """Validate CharacterIntent has all required fields with valid values."""
    required = [
        "emotion", "stature", "eyeline_target", "tempo",
        "micro_action", "hand_state", "movement_intent"
    ]
    
    for field in required:
        if not getattr(intent, field, ""):
            logger.warning(f"[ACTOR_INTENT] Intent missing field: {field}")
            return False
    
    return True


def intent_to_readable_string(intent: CharacterIntent, character_name: str = "") -> str:
    """Convert CharacterIntent to human-readable description string."""
    prefix = f"{character_name} " if character_name else ""
    
    return (
        f"{prefix}is {intent.emotion}, standing {intent.stature}, "
        f"looking {intent.eyeline_target}. "
        f"{intent.micro_action} at a {intent.tempo} pace. "
        f"Movement: {intent.movement_intent}. "
        f"Hands: {intent.hand_state}."
    )


# ============================================================================
# VERSION & METADATA
# ============================================================================

ACTOR_INTENT_LAYER_VERSION = "V21.10"
ACTOR_INTENT_LAYER_STATUS = "PRODUCTION"

def get_module_info() -> Dict[str, str]:
    """Get module version and status information."""
    return {
        "module": "actor_intent_layer",
        "version": ACTOR_INTENT_LAYER_VERSION,
        "status": ACTOR_INTENT_LAYER_STATUS,
        "emotions_supported": list(EMOTION_GESTURE_MAP.keys()),
        "character_intent_fields": [
            "emotion", "stature", "eyeline_target", "tempo",
            "micro_action", "hand_state", "movement_intent"
        ],
    }


if __name__ == "__main__":
    # Example usage
    print("[ACTOR_INTENT] Module Information:")
    info = get_module_info()
    for key, val in info.items():
        if isinstance(val, list):
            print(f"  {key}: {', '.join(val)}")
        else:
            print(f"  {key}: {val}")
