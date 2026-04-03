"""
CREATIVE DIRECTOR INTELLIGENCE — V27.2
======================================

This module is the FILMMAKER'S BRAIN that sits between the story bible
and the prompt compiler. It reads script beats, dialogue, and scene
context, then produces per-shot creative directives that get baked
into nano_prompt and ltx_motion_prompt at the ORIGIN — before any
generation happens.

WHAT IT DOES:
  1. PROP CONTINUITY — tracks what each character holds/carries across a scene
  2. BLOCKING INTELLIGENCE — maps character spatial relationships (distance, orientation)
  3. EMOTION ARC — escalation curve per character across scene beats
  4. PERFORMANCE DIRECTION — specific physical actions, not generic "speaks"
  5. SECOND-BY-SECOND MOTION CHOREOGRAPHY — frame-by-frame LTX instructions
  6. PRE-GENERATION CREATIVE AUDIT — flags issues BEFORE wasting a FAL call

WHY IT EXISTS:
  The V27.1.4d system solved WHERE characters are (room lock, position lock).
  This module solves WHAT characters are DOING — the acting, the props, the
  emotional escalation, the physical choreography that makes a scene feel
  directed rather than generated.

INTEGRATION:
  Called ONCE per scene during enrichment (after fix-v16, before generation).
  Writes directives into shot fields:
    shot["_cd_props"] = ["leather folder open in left hand"]
    shot["_cd_blocking"] = "6 feet apart, confrontational stance"
    shot["_cd_emotion"] = {"ELEANOR VOSS": "controlled_assertive", "THOMAS BLACKWOOD": "defensive_grief"}
    shot["_cd_performance"] = "Eleanor holds folder forward, index finger on a line item"
    shot["_cd_motion_choreography"] = "0-2s: Eleanor's hand lifts folder. 2-4s: ..."
    shot["_cd_nano_injection"] = "...text to prepend/append to nano_prompt..."
    shot["_cd_ltx_injection"] = "...text to prepend/append to ltx_motion_prompt..."
    shot["_cd_flags"] = ["PROP_MISSING", "BLOCKING_TOO_CLOSE"]

Author: ATLAS V27.2
Date: 2026-03-16
"""

from typing import Dict, List, Optional, Tuple
import re
import json


# ═══════════════════════════════════════════════════════════════════
# PROP TRACKING — What each character holds/carries across a scene
# ═══════════════════════════════════════════════════════════════════

# Props are extracted from story bible beats and dialogue context.
# Once a character picks up / is described with a prop, it persists
# until the script explicitly says they put it down or hand it off.

PROP_KEYWORDS = {
    # keyword in beat/dialogue → (prop_name, carrier_hint, visual_description)
    "briefcase": ("briefcase", None, "dark leather briefcase"),
    "folder": ("folder", None, "leather folder with documents"),
    "documents": ("folder", None, "leather folder with documents"),
    "financial": ("folder", None, "leather folder with financial documents"),
    "papers": ("folder", None, "papers in hand"),
    "letter": ("letter", None, "folded letter"),
    "envelope": ("envelope", None, "sealed envelope"),
    "photograph": ("photograph", None, "old photograph"),
    "key": ("key", None, "ornate brass key"),
    "keys": ("keys", None, "ring of old keys"),
    "glass": ("glass", None, "crystal glass"),
    "drink": ("glass", None, "glass of whiskey"),
    "phone": ("phone", None, "mobile phone"),
    "gun": ("gun", None, "handgun"),
    "knife": ("knife", None, "blade"),
    "book": ("book", None, "leather-bound book"),
    "diary": ("diary", None, "old diary"),
    "journal": ("journal", None, "worn journal"),
    "cane": ("cane", None, "walking cane"),
    "umbrella": ("umbrella", None, "black umbrella"),
    "bag": ("bag", None, "leather bag"),
    "suitcase": ("suitcase", None, "travel suitcase"),
    "will": ("document", None, "legal document"),
    "contract": ("document", None, "legal contract"),
    "deed": ("document", None, "property deed"),
    "painting": ("painting", None, None),  # mounted, not carried
    "portrait": ("portrait", None, None),  # mounted, not carried
    "banister": ("banister", None, None),  # touched, not carried
}

# Props that are HELD vs MOUNTED/FIXED (not carried between shots)
NON_PORTABLE_PROPS = {"painting", "portrait", "banister", "staircase", "chandelier",
                       "fireplace", "door", "window", "clock", "mirror"}


class PropTracker:
    """Tracks what each character holds across a scene's shots."""

    def __init__(self):
        self._char_props: Dict[str, List[Dict]] = {}  # char_name → [{prop, visual, since_shot}]

    def extract_props_from_beat(self, beat_text: str, characters: List[str]) -> Dict[str, List[Dict]]:
        """Extract props mentioned in a story beat and assign to likely carrier."""
        found = {}
        beat_lower = beat_text.lower()

        for keyword, (prop_name, carrier_hint, visual) in PROP_KEYWORDS.items():
            if keyword in beat_lower and prop_name not in NON_PORTABLE_PROPS:
                # Determine who holds it
                carrier = carrier_hint
                if not carrier:
                    # Heuristic: prop mentioned near a character name
                    for char in characters:
                        char_parts = char.upper().split()
                        for part in char_parts:
                            if part.lower() in beat_lower:
                                # Check proximity: is the keyword within 80 chars of the name?
                                name_pos = beat_lower.find(part.lower())
                                key_pos = beat_lower.find(keyword)
                                if abs(name_pos - key_pos) < 80:
                                    carrier = char
                                    break
                        if carrier:
                            break
                    if not carrier and characters:
                        # Default: assign to first character mentioned with action verb
                        for char in characters:
                            char_first = char.split()[0].lower()
                            if char_first in beat_lower:
                                carrier = char
                                break
                        if not carrier:
                            carrier = characters[0]

                if carrier and visual:
                    if carrier not in found:
                        found[carrier] = []
                    found[carrier].append({
                        "prop": prop_name,
                        "visual": visual,
                        "source": "beat"
                    })

        return found

    def extract_props_from_dialogue(self, dialogue_text: str, speaker: str) -> Dict[str, List[Dict]]:
        """Extract props referenced in dialogue (character is likely holding/referencing them)."""
        found = {}
        if not dialogue_text:
            return found

        dial_lower = dialogue_text.lower()
        for keyword, (prop_name, _, visual) in PROP_KEYWORDS.items():
            if keyword in dial_lower and prop_name not in NON_PORTABLE_PROPS:
                # If they're talking about it, they or their scene partner likely has it
                if speaker and visual:
                    if speaker not in found:
                        found[speaker] = []
                    found[speaker].append({
                        "prop": prop_name,
                        "visual": visual,
                        "source": "dialogue_ref"
                    })

        return found

    def register_props(self, char_name: str, props: List[Dict], shot_id: str):
        """Register that a character holds these props as of this shot."""
        key = char_name.upper().strip()
        if key not in self._char_props:
            self._char_props[key] = []
        for p in props:
            # Don't duplicate
            existing = [x["prop"] for x in self._char_props[key]]
            if p["prop"] not in existing:
                self._char_props[key].append({
                    **p,
                    "since_shot": shot_id
                })

    def get_props(self, char_name: str) -> List[Dict]:
        """Get all props a character currently holds."""
        key = char_name.upper().strip()
        return self._char_props.get(key, [])

    def get_prop_prompt_fragment(self, char_name: str, shot_type: str) -> str:
        """Generate the prompt fragment describing what the character holds.

        For extreme close-ups, props may not be visible.
        For medium/wide shots, props should be explicitly described.
        """
        props = self.get_props(char_name)
        if not props:
            return ""

        # Close-ups: only mention if prop is near face
        skip_types = {"extreme_close_up", "extreme_close", "ecu"}
        if shot_type and shot_type.lower().replace("-", "_").replace(" ", "_") in skip_types:
            return ""

        # Build description
        visuals = [p["visual"] for p in props if p.get("visual")]
        if not visuals:
            return ""

        if len(visuals) == 1:
            return f"holding {visuals[0]}"
        else:
            return f"holding {', '.join(visuals[:-1])} and {visuals[-1]}"


# ═══════════════════════════════════════════════════════════════════
# EMOTION ARC — Tracks emotional escalation per character per scene
# ═══════════════════════════════════════════════════════════════════

EMOTION_KEYWORDS = {
    # keyword → (emotion, intensity 0-1)
    "demands": ("assertive", 0.7),
    "confronts": ("confrontational", 0.8),
    "insists": ("insistent", 0.6),
    "presents": ("controlled_professional", 0.4),
    "protests": ("defensive", 0.6),
    "refuses": ("defiant", 0.7),
    "grief": ("grief", 0.8),
    "reluctant": ("reluctant", 0.5),
    "defiance": ("defiant", 0.7),
    "absorbs": ("processing", 0.5),
    "tightens": ("controlled_tension", 0.6),
    "cracks": ("vulnerability", 0.7),
    "stares": ("fixated", 0.6),
    "hated": ("bitter", 0.7),
    "strangers": ("protective", 0.6),
    "pawing": ("disgust", 0.7),
    "detachment": ("professional_detachment", 0.3),
    "surveying": ("analytical", 0.3),
    "touching": ("tender", 0.5),
    "cooperation": ("demanding", 0.6),
    "agreement": ("firm", 0.6),
    "commissioned": ("sentimental", 0.6),
    "stays": ("defiant_final", 0.8),
}

EMOTION_TO_PHYSICAL = {
    # emotion → physical direction for the actor
    "assertive": "chin lifted, shoulders squared, direct gaze, folder held forward",
    "confrontational": "leaning slightly forward, jaw set, eyes locked on opponent",
    "controlled_professional": "posture straight, expression neutral-firm, gestures precise",
    "defensive": "weight shifts back, hand grips nearest surface, eyes narrow",
    "defiant": "chin up, body rigid, hands clenched or gripping, refuses to yield ground",
    "grief": "shoulders slightly hunched, eyes distant, hand reaches for something familiar",
    "reluctant": "body turned slightly away, feet planted, movement slow and resistant",
    "processing": "stillness, jaw tightens, eyes drop then rise, breath held",
    "controlled_tension": "micro-expressions only, jaw clenches, knuckles white on held object",
    "vulnerability": "mask slips for one beat, eyes glisten, quickly recovers composure",
    "professional_detachment": "measured movements, clinical gaze, emotional distance in posture",
    "analytical": "eyes scanning methodically, head tilts, assessing",
    "tender": "fingers gentle, movement slow, eyes soft",
    "protective": "body language shields the space, voice drops, intensity rises",
    "fixated": "eyes locked on one point, body still, world narrows to that object",
    "sentimental": "voice softens, hand touches the referenced object, eyes warm",
    "defiant_final": "full stop, plants feet, voice drops to controlled steel, no negotiation",
    "firm": "steady gaze, measured tone, no give in posture",
    "bitter": "lips thin, words clipped, barely controlled",
    "disgust": "slight recoil, nostrils flare, words come with visible effort",
}


class EmotionArc:
    """Tracks emotional state per character across a scene."""

    def __init__(self):
        self._arc: Dict[str, List[Dict]] = {}  # char → [{shot_id, emotion, intensity, physical}]

    def analyze_beat(self, beat_text: str, characters: List[str]) -> Dict[str, Dict]:
        """Analyze a beat for emotional content per character."""
        result = {}
        beat_lower = beat_text.lower()

        for char in characters:
            best_emotion = None
            best_intensity = 0.0
            char_lower = char.lower()
            char_first = char.split()[0].lower() if char else ""

            # Check if character is mentioned in the beat
            char_in_beat = char_lower in beat_lower or char_first in beat_lower

            for keyword, (emotion, intensity) in EMOTION_KEYWORDS.items():
                if keyword in beat_lower:
                    # Higher weight if keyword is near character mention
                    effective_intensity = intensity
                    if char_in_beat:
                        kw_pos = beat_lower.find(keyword)
                        for name_part in [char_lower, char_first]:
                            if name_part in beat_lower:
                                name_pos = beat_lower.find(name_part)
                                if abs(name_pos - kw_pos) < 60:
                                    effective_intensity = intensity * 1.3

                    if effective_intensity > best_intensity:
                        best_intensity = min(effective_intensity, 1.0)
                        best_emotion = emotion

            if best_emotion:
                physical = EMOTION_TO_PHYSICAL.get(best_emotion, "")
                result[char] = {
                    "emotion": best_emotion,
                    "intensity": round(best_intensity, 2),
                    "physical": physical
                }

        return result

    def register(self, char_name: str, shot_id: str, emotion_data: Dict):
        """Register emotion state for a character at a shot."""
        key = char_name.upper().strip()
        if key not in self._arc:
            self._arc[key] = []
        self._arc[key].append({
            "shot_id": shot_id,
            **emotion_data
        })

    def get_current(self, char_name: str) -> Optional[Dict]:
        """Get most recent emotion state for a character."""
        key = char_name.upper().strip()
        arc = self._arc.get(key, [])
        return arc[-1] if arc else None

    def get_escalation_note(self, char_name: str) -> str:
        """Get a note about how the character's emotion has been escalating."""
        key = char_name.upper().strip()
        arc = self._arc.get(key, [])
        if len(arc) < 2:
            return ""
        prev = arc[-2]
        curr = arc[-1]
        delta = curr.get("intensity", 0) - prev.get("intensity", 0)
        if delta > 0.15:
            return f"ESCALATING from {prev['emotion']} to {curr['emotion']}"
        elif delta < -0.15:
            return f"DE-ESCALATING from {prev['emotion']} to {curr['emotion']}"
        else:
            return f"HOLDING at {curr['emotion']}"


# ═══════════════════════════════════════════════════════════════════
# BLOCKING INTELLIGENCE — Character spatial relationships
# ═══════════════════════════════════════════════════════════════════

BLOCKING_BY_SHOT_TYPE = {
    # shot_type → default blocking description
    "establishing": "characters not yet visible, room geography only",
    "b-roll": "no character blocking, atmospheric detail",
    "wide": "characters separated by 8-10 feet, dwarfed by room, emotional distance visible",
    "closing": "characters separated by 8-10 feet, neither moves toward the other, vast space between",
    "medium": "character at conversational distance, 4-5 feet from camera",
    "two_shot": "characters 5-6 feet apart, facing each other, confrontational stance",
    "over_the_shoulder": "characters 3-4 feet apart, one shoulder fills foreground",
    "medium_close": "single character, waist-up framing, 3 feet from camera",
    "close_up": "single character, face fills frame, 2 feet from camera",
    "extreme_close_up": "eyes and mouth only, intimate proximity",
    "reaction": "single character, face and upper body, capturing micro-expression",
    "insert": "object detail, no character blocking",
}

BLOCKING_MODIFIERS = {
    # emotion → blocking modifier
    "confrontational": "characters squared off, neither gives ground, eye-lines locked",
    "defensive": "one character turned slightly away, protecting their space",
    "assertive": "forward-leaning posture, closing distance, commanding the space",
    "grief": "turned toward object of grief, body language shields vulnerability",
    "defiant": "planted, immovable, occupying their ground with purpose",
    "vulnerability": "micro-retreat, half-step back, before catching themselves",
}


def get_blocking_direction(shot_type: str, characters: List[str],
                           emotions: Dict[str, Dict], beat_text: str = "") -> str:
    """Generate blocking direction for a shot based on type, characters, and emotion."""
    base = BLOCKING_BY_SHOT_TYPE.get(
        shot_type.lower().replace("-", "_").replace(" ", "_"),
        "standard conversational distance"
    )

    if not characters:
        return base

    # Add emotion-driven modifiers
    modifiers = []
    for char in characters:
        emo = emotions.get(char, {})
        emotion_name = emo.get("emotion", "")
        if emotion_name in BLOCKING_MODIFIERS:
            modifiers.append(f"{char.split()[0]}: {BLOCKING_MODIFIERS[emotion_name]}")

    # Beat-driven distance adjustments
    beat_lower = (beat_text or "").lower()
    if any(w in beat_lower for w in ["separated", "apart", "distance", "vast", "space between"]):
        base = base.replace("5-6 feet", "8-10 feet").replace("4-5 feet", "6-8 feet")
    if any(w in beat_lower for w in ["close", "intimate", "leans in", "steps toward"]):
        base = base.replace("5-6 feet", "3-4 feet").replace("8-10 feet", "5-6 feet")

    if modifiers:
        return f"{base}. {'. '.join(modifiers)}"
    return base


# ═══════════════════════════════════════════════════════════════════
# MOTION CHOREOGRAPHY — Second-by-second LTX video instructions
# ═══════════════════════════════════════════════════════════════════

def build_motion_choreography(shot: Dict, emotion_data: Dict[str, Dict],
                               prop_tracker: PropTracker,
                               duration: float = 5.0) -> str:
    """Build second-by-second motion choreography for LTX video prompt.

    This replaces generic "character speaks" with specific frame-by-frame
    physical direction that tells the video model exactly what to animate.
    """
    shot_type = (shot.get("shot_type") or "").lower().replace("-", "_").replace(" ", "_")
    characters = shot.get("characters") or []
    dialogue = shot.get("dialogue_text") or ""
    description = shot.get("description") or shot.get("shot_description") or ""

    if not characters:
        # B-roll / establishing: atmospheric motion
        return _build_atmospheric_choreography(shot_type, description, duration)

    if len(characters) == 1:
        return _build_solo_choreography(
            characters[0], shot_type, dialogue, description,
            emotion_data.get(characters[0], {}),
            prop_tracker, duration
        )
    else:
        return _build_multi_choreography(
            characters, shot_type, dialogue, description,
            emotion_data, prop_tracker, duration
        )


def _build_atmospheric_choreography(shot_type: str, description: str, duration: float) -> str:
    """Atmospheric motion for establishing/b-roll shots."""
    desc_lower = description.lower()

    motions = []
    if "dust" in desc_lower:
        motions.append("dust motes drift slowly through light beam")
    if "light" in desc_lower or "window" in desc_lower:
        motions.append("light shifts subtly as clouds pass outside")
    if "candle" in desc_lower or "flame" in desc_lower:
        motions.append("candle flames flicker, casting moving shadows")
    if "door" in desc_lower:
        motions.append("heavy door creaks open slowly revealing interior")
    if "chandelier" in desc_lower:
        motions.append("chandelier crystals catch light, prismatic shimmer")

    if not motions:
        motions = ["subtle ambient movement, shadows shift"]

    # Build timeline
    seg = duration / len(motions)
    parts = []
    for i, m in enumerate(motions):
        t_start = round(i * seg, 1)
        t_end = round((i + 1) * seg, 1)
        parts.append(f"{t_start}-{t_end}s: {m}")

    return ". ".join(parts)


def _build_solo_choreography(char: str, shot_type: str, dialogue: str,
                              description: str, emotion: Dict,
                              prop_tracker: PropTracker, duration: float) -> str:
    """Solo character motion choreography."""
    char_first = char.split()[0] if char else "Character"
    physical = emotion.get("physical", "")
    emotion_name = emotion.get("emotion", "neutral")
    props = prop_tracker.get_props(char)
    prop_desc = props[0]["visual"] if props else ""

    # Split duration into 3 acts
    act1 = round(duration * 0.3, 1)
    act2 = round(duration * 0.6, 1)
    act3 = round(duration, 1)

    parts = []

    # ACT 1: Setup — establish the character's physical state
    setup_actions = []
    if prop_desc and shot_type not in ("extreme_close_up", "close_up"):
        setup_actions.append(f"{char_first} holds {prop_desc}")
    if "grief" in emotion_name:
        setup_actions.append(f"{char_first}'s hand rests on nearest surface, weight shifted")
    elif "assertive" in emotion_name or "professional" in emotion_name:
        setup_actions.append(f"{char_first} stands straight, chin level")
    elif "defiant" in emotion_name:
        setup_actions.append(f"{char_first} plants feet, body rigid")
    else:
        setup_actions.append(f"{char_first} holds position")

    parts.append(f"0-{act1}s: {', '.join(setup_actions)}")

    # ACT 2: Action — the dialogue/performance beat
    if dialogue:
        # Extract key emotional words from dialogue
        action_desc = f"{char_first} delivers line"
        if "jaw" in physical:
            action_desc += ", jaw working"
        if "lean" in physical:
            action_desc += ", leans forward slightly"
        if "grip" in physical:
            action_desc += ", grip tightens"
        if prop_desc:
            action_desc += f", {prop_desc} shifts in hand"
        parts.append(f"{act1}-{act2}s: {action_desc}")
    else:
        # Reaction or non-dialogue
        if "processing" in emotion_name or "reaction" in shot_type:
            parts.append(f"{act1}-{act2}s: {char_first} absorbs the moment, jaw tightens, eyes shift")
        else:
            parts.append(f"{act1}-{act2}s: {char_first} {physical.split(',')[0] if physical else 'subtle weight shift'}")

    # ACT 3: Resolution — the emotional landing
    if "vulnerability" in emotion_name:
        parts.append(f"{act2}-{act3}s: mask slips for one beat, eyes glisten, quickly recovers")
    elif "defiant" in emotion_name:
        parts.append(f"{act2}-{act3}s: holds ground, no movement, absolute stillness signals resolve")
    elif "grief" in emotion_name:
        parts.append(f"{act2}-{act3}s: breath catches, hand tightens, eyes stay fixed on memory")
    elif prop_desc and "folder" in prop_desc:
        parts.append(f"{act2}-{act3}s: glances down at {prop_desc}, back up with renewed purpose")
    else:
        parts.append(f"{act2}-{act3}s: settles into stillness, emotional weight lands")

    return ". ".join(parts)


def _build_multi_choreography(characters: List[str], shot_type: str, dialogue: str,
                                description: str, emotions: Dict[str, Dict],
                                prop_tracker: PropTracker, duration: float) -> str:
    """Multi-character motion choreography (OTS, two-shot, wide)."""
    char_names = [c.split()[0] for c in characters[:2]]
    if len(char_names) < 2:
        char_names.append("Other")

    # Determine speaker from dialogue
    speaker_idx = 0
    if dialogue:
        dial_upper = dialogue.upper()
        for i, c in enumerate(characters[:2]):
            if c.upper() in dial_upper:
                speaker_idx = i
                break

    speaker = char_names[speaker_idx]
    listener = char_names[1 - speaker_idx]
    speaker_emo = emotions.get(characters[speaker_idx], {})
    listener_emo = emotions.get(characters[1 - speaker_idx], {})

    speaker_props = prop_tracker.get_props(characters[speaker_idx])
    listener_props = prop_tracker.get_props(characters[1 - speaker_idx])
    speaker_prop = speaker_props[0]["visual"] if speaker_props else ""
    listener_prop = listener_props[0]["visual"] if listener_props else ""

    act1 = round(duration * 0.25, 1)
    act2 = round(duration * 0.6, 1)
    act3 = round(duration * 0.85, 1)
    act4 = round(duration, 1)

    parts = []

    # ACT 1: Establish spatial relationship
    if "over_the_shoulder" in shot_type or "ots" in shot_type:
        fg = listener  # foreground (back to camera)
        bg = speaker   # background (faces camera)
        fg_prop = f" with {listener_prop}" if listener_prop else ""
        parts.append(f"0-{act1}s: {fg}'s shoulder foreground{fg_prop}, {bg} faces camera, begins speaking")
    elif "two_shot" in shot_type:
        parts.append(f"0-{act1}s: {speaker} and {listener} face each other, confrontational distance")
    else:  # wide
        parts.append(f"0-{act1}s: both figures visible in room, separated by space")

    # ACT 2: Speaker performance
    if dialogue:
        sp_physical = speaker_emo.get("physical", "speaks with purpose")
        sp_action = sp_physical.split(",")[0] if "," in sp_physical else sp_physical
        if speaker_prop:
            parts.append(f"{act1}-{act2}s: {speaker} {sp_action}, gestures with {speaker_prop}")
        else:
            parts.append(f"{act1}-{act2}s: {speaker} {sp_action}, mouth moves with dialogue")
    else:
        parts.append(f"{act1}-{act2}s: {speaker} holds position, tension visible in posture")

    # ACT 3: Listener reaction
    l_physical = listener_emo.get("physical", "listens intently")
    l_action = l_physical.split(",")[0] if "," in l_physical else l_physical
    if listener_prop:
        parts.append(f"{act2}-{act3}s: {listener} {l_action}, {listener_prop} shifts in grip")
    else:
        parts.append(f"{act2}-{act3}s: {listener} {l_action}")

    # ACT 4: Beat landing
    parts.append(f"{act3}-{act4}s: both hold position, emotional weight of the exchange lands")

    return ". ".join(parts)


# ═══════════════════════════════════════════════════════════════════
# PRE-GENERATION CREATIVE AUDIT
# ═══════════════════════════════════════════════════════════════════

def audit_shot_creative(shot: Dict, prop_tracker: PropTracker,
                         emotion_arc: EmotionArc) -> List[str]:
    """Audit a shot for creative issues BEFORE generation.

    Returns list of flags (empty = good to go).
    """
    flags = []
    shot_id = shot.get("shot_id", "?")
    shot_type = (shot.get("shot_type") or "").lower()
    characters = shot.get("characters") or []
    dialogue = shot.get("dialogue_text") or ""
    nano = shot.get("nano_prompt") or ""
    ltx = shot.get("ltx_motion_prompt") or ""

    # CHECK 1: Character with props should have prop in prompt
    for char in characters:
        props = prop_tracker.get_props(char)
        if props and shot_type not in ("extreme_close_up", "close_up", "ecu"):
            prop_names = [p["visual"] for p in props]
            for pv in prop_names:
                # Check if any prop keyword appears in the nano_prompt
                prop_words = pv.lower().split()
                if not any(w in nano.lower() for w in prop_words if len(w) > 3):
                    flags.append(f"PROP_MISSING:{char}:{pv}")

    # CHECK 2: Dialogue shot without performance direction
    if dialogue and "speaks" not in ltx.lower() and "delivers" not in ltx.lower() \
       and "mouth" not in ltx.lower() and "jaw" not in ltx.lower():
        flags.append("NO_PERFORMANCE_DIRECTION")

    # CHECK 3: Wide/closing shot with characters too close (check for distance language)
    if shot_type in ("wide", "closing") and len(characters) >= 2:
        if "separated" not in nano.lower() and "apart" not in nano.lower() \
           and "distance" not in nano.lower() and "space between" not in nano.lower():
            flags.append("BLOCKING_TOO_CLOSE:wide_shot_needs_separation")

    # CHECK 4: Reaction shot that reads as establishing
    if "reaction" in shot_type and len(characters) == 1:
        if "wide" in nano.lower() or "full body" in nano.lower() or "room" in nano.lower():
            if "face" not in nano.lower() and "close" not in nano.lower():
                flags.append("REACTION_FRAMED_TOO_WIDE")

    # CHECK 5: Arms crossed when character should be holding something
    for char in characters:
        props = prop_tracker.get_props(char)
        if props:
            if "arms crossed" in nano.lower() or "arms folded" in nano.lower():
                flags.append(f"ARMS_CROSSED_WITH_PROP:{char}")

    return flags


# ═══════════════════════════════════════════════════════════════════
# MAIN ENRICHMENT FUNCTION — Called per scene
# ═══════════════════════════════════════════════════════════════════

def enrich_scene_creative(shots: List[Dict], story_bible_scene: Dict,
                           cast_map: Dict = None) -> List[Dict]:
    """
    MAIN ENTRY POINT — Enrich all shots in a scene with creative intelligence.

    Called ONCE per scene, enriches every shot with:
      _cd_props, _cd_blocking, _cd_emotion, _cd_performance,
      _cd_motion_choreography, _cd_nano_injection, _cd_ltx_injection, _cd_flags

    Args:
        shots: List of shot dicts for this scene
        story_bible_scene: The scene entry from story_bible.json
        cast_map: Optional cast_map.json for appearance data

    Returns:
        The shots list, enriched in-place with _cd_* fields
    """
    prop_tracker = PropTracker()
    emotion_arc = EmotionArc()

    # Extract scene-level data
    beats = story_bible_scene.get("beats", [])
    scene_chars = story_bible_scene.get("characters", [])
    location = story_bible_scene.get("location", "")

    # PHASE 1: Scan all beats for props and emotions
    # This gives us scene-wide context before we process individual shots
    all_beat_text = " ".join(
        b.get("description", b.get("text", str(b))) if isinstance(b, dict) else str(b)
        for b in beats
    )

    # Extract props from beats
    beat_props = prop_tracker.extract_props_from_beat(all_beat_text, scene_chars)
    for char, props in beat_props.items():
        prop_tracker.register_props(char, props, "scene_init")

    # Also scan shot descriptions and dialogue for additional props
    for shot in shots:
        desc = shot.get("description") or shot.get("shot_description") or ""
        dialogue = shot.get("dialogue_text") or ""
        characters = shot.get("characters") or []

        desc_props = prop_tracker.extract_props_from_beat(desc, characters)
        for char, props in desc_props.items():
            prop_tracker.register_props(char, props, shot.get("shot_id", ""))

        # Check dialogue for prop references
        if dialogue:
            for char in characters:
                if char.upper() in dialogue.upper():
                    dial_props = prop_tracker.extract_props_from_dialogue(dialogue, char)
                    for c, ps in dial_props.items():
                        prop_tracker.register_props(c, ps, shot.get("shot_id", ""))

    # PHASE 2: Assign beat emotions to shots
    # Map beats to shots based on position in scene
    beat_texts = []
    for b in beats:
        if isinstance(b, dict):
            beat_texts.append(b.get("description", b.get("text", str(b))))
        else:
            beat_texts.append(str(b))

    # PHASE 3: Enrich each shot
    for i, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"unknown_{i}")
        shot_type = shot.get("shot_type") or ""
        characters = shot.get("characters") or []
        dialogue = shot.get("dialogue_text") or ""
        description = shot.get("description") or shot.get("shot_description") or ""
        duration = shot.get("duration") or 5.0

        # --- Emotion ---
        # Find the most relevant beat for this shot
        relevant_beat = ""
        if beat_texts:
            # Map shot index to beat proportionally
            beat_idx = min(int(i / max(len(shots), 1) * len(beat_texts)), len(beat_texts) - 1)
            relevant_beat = beat_texts[beat_idx]

        # Also use shot description and dialogue for emotion
        emotion_context = f"{relevant_beat} {description} {dialogue}"
        char_emotions = emotion_arc.analyze_beat(emotion_context, characters)

        for char, emo in char_emotions.items():
            emotion_arc.register(char, shot_id, emo)

        shot["_cd_emotion"] = char_emotions

        # --- Props ---
        char_prop_fragments = {}
        for char in characters:
            frag = prop_tracker.get_prop_prompt_fragment(char, shot_type)
            if frag:
                char_prop_fragments[char] = frag

        shot["_cd_props"] = char_prop_fragments

        # --- Blocking ---
        blocking = get_blocking_direction(shot_type, characters, char_emotions, relevant_beat)
        shot["_cd_blocking"] = blocking

        # --- Performance Direction ---
        perf_parts = []
        for char in characters:
            emo = char_emotions.get(char, {})
            physical = emo.get("physical", "")
            escalation = emotion_arc.get_escalation_note(char)
            char_first = char.split()[0]
            if physical:
                perf_parts.append(f"{char_first}: {physical}")
            if escalation:
                perf_parts.append(f"  [{escalation}]")
        shot["_cd_performance"] = ". ".join(perf_parts)

        # --- Motion Choreography ---
        choreography = build_motion_choreography(
            shot, char_emotions, prop_tracker, float(duration)
        )
        shot["_cd_motion_choreography"] = choreography

        # --- Nano Prompt Injection ---
        nano_injection_parts = []
        for char in characters:
            prop_frag = char_prop_fragments.get(char, "")
            if prop_frag:
                char_first = char.split()[0]
                nano_injection_parts.append(f"{char_first} {prop_frag}")

        if blocking and characters:
            # Add blocking for multi-char shots
            if len(characters) >= 2:
                nano_injection_parts.append(blocking)

        # Add emotional state
        for char in characters:
            emo = char_emotions.get(char, {})
            physical = emo.get("physical", "")
            if physical:
                char_first = char.split()[0]
                nano_injection_parts.append(f"{char_first}: {physical}")

        shot["_cd_nano_injection"] = ". ".join(nano_injection_parts) if nano_injection_parts else ""

        # --- LTX Motion Injection ---
        shot["_cd_ltx_injection"] = choreography  # The choreography IS the LTX injection

        # --- Pre-generation Audit ---
        flags = audit_shot_creative(shot, prop_tracker, emotion_arc)
        shot["_cd_flags"] = flags

    return shots


def apply_creative_directives(shot: Dict) -> Dict:
    """
    Apply the _cd_* fields into the actual nano_prompt and ltx_motion_prompt.

    Called at generation time (after enrichment, before FAL call).
    This modifies the shot in place.
    """
    nano = shot.get("nano_prompt") or ""
    ltx = shot.get("ltx_motion_prompt") or ""

    # Inject prop + blocking + emotion into nano_prompt
    cd_nano = shot.get("_cd_nano_injection", "")
    if cd_nano and cd_nano not in nano:
        # Append after the first sentence (which is usually the lens/framing description)
        first_period = nano.find(". ")
        if first_period > 0 and first_period < 200:
            nano = nano[:first_period + 2] + cd_nano + ". " + nano[first_period + 2:]
        else:
            nano = nano + ". " + cd_nano

    # Inject motion choreography into ltx_motion_prompt
    cd_ltx = shot.get("_cd_ltx_injection", "")
    if cd_ltx and cd_ltx not in ltx:
        # Replace generic motion with choreography
        # Find and replace common generic phrases
        generic_patterns = [
            "natural movement begins",
            "subtle breathing motion",
            "character speaks naturally",
            "gentle ambient motion",
        ]
        replaced = False
        for gp in generic_patterns:
            if gp in ltx.lower():
                ltx = ltx.replace(gp, cd_ltx)
                replaced = True
                break

        if not replaced:
            # Append choreography
            if len(ltx) + len(cd_ltx) < 900:  # LTX 900 char limit
                ltx = ltx.rstrip(". ") + ". " + cd_ltx
            else:
                # Replace last portion with choreography (more important than generic ending)
                available = 900 - len(cd_ltx) - 5
                if available > 200:
                    ltx = ltx[:available] + ". " + cd_ltx

    shot["nano_prompt"] = nano
    shot["ltx_motion_prompt"] = ltx

    return shot


# ═══════════════════════════════════════════════════════════════════
# CREATIVE REPORT — Pre-generation analysis for operator review
# ═══════════════════════════════════════════════════════════════════

def generate_creative_report(shots: List[Dict], scene_id: str = "") -> str:
    """Generate a human-readable creative director report for operator review.

    This is what the operator sees BEFORE approving generation.
    """
    lines = [
        f"═══ CREATIVE DIRECTOR REPORT — Scene {scene_id} ═══",
        f"Shots: {len(shots)}",
        ""
    ]

    flags_total = 0
    for shot in shots:
        sid = shot.get("shot_id", "?")
        stype = shot.get("shot_type", "?")
        chars = shot.get("characters") or []
        flags = shot.get("_cd_flags") or []
        props = shot.get("_cd_props") or {}
        emotion = shot.get("_cd_emotion") or {}
        blocking = shot.get("_cd_blocking") or ""
        choreo = shot.get("_cd_motion_choreography") or ""

        status = "FLAGGED" if flags else "READY"
        flags_total += len(flags)

        lines.append(f"── {sid} | {stype} | {status} ──")

        if chars:
            lines.append(f"  Characters: {', '.join(chars)}")

        if props:
            for c, p in props.items():
                lines.append(f"  Prop: {c.split()[0]} → {p}")

        if emotion:
            for c, e in emotion.items():
                lines.append(f"  Emotion: {c.split()[0]} → {e.get('emotion', '?')} ({e.get('intensity', 0):.1f})")

        if blocking:
            lines.append(f"  Blocking: {blocking[:100]}")

        if choreo:
            lines.append(f"  Motion: {choreo[:120]}...")

        if flags:
            for f in flags:
                lines.append(f"  ⚠ FLAG: {f}")

        lines.append("")

    lines.append(f"═══ TOTAL FLAGS: {flags_total} ═══")
    if flags_total > 0:
        lines.append("Review flagged shots before generation.")
    else:
        lines.append("All shots clear for generation.")

    return "\n".join(lines)
