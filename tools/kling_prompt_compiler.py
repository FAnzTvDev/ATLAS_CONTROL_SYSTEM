#!/usr/bin/env python3
"""
ATLAS V27.2 — Kling Prompt Compiler
====================================
REWRITTEN based on Kling 3.0 API research (FAL prompting guide, March 2026).

KEY INSIGHT FROM RESEARCH:
  Kling 3.0 understands CINEMATIC LANGUAGE — scene coverage, composition,
  pacing, continuity. Prompts that reference filmmaking concepts outperform
  prompts that focus only on visual attributes.

  OLD (wrong): 250 chars, stripped to skeleton → model had nothing to work with
  NEW (correct): Up to 2500 chars, directorial format:
    Scene → Characters → Action → Camera → Dialogue → Atmosphere

Kling 3.0 Vocabulary (from FAL guide):
  - Character tags: [Character A: Role, appearance] with dialogue
  - Dialogue format: [Character, tone]: "dialogue text"
  - Camera: tracking, following, freezing, panning, POV, shot-reverse-shot
  - Motion: explicit over-time instructions ("then", "as", "while")
  - Audio: native — describe who speaks and ambient sound
  - Identity: ++element++ emphasis for critical elements
  - cfg_scale: 0.5 default, negative_prompt supported
  - Duration: 3-15 seconds

Design Principle:
  Think like a DIRECTOR, not a photographer. Describe the SCENE as a
  direction to actors and camera, not a list of visual attributes.
  Trust Kling's native physics — don't over-choreograph body movement.
  DO specify: dialogue, emotion, camera behavior, character relationships.
  DON'T specify: frame-by-frame body physics (that's LTX territory).

Usage:
    from tools.kling_prompt_compiler import compile_for_kling, compile_video_for_kling
    kling_frame_prompt = compile_for_kling(shot, cast_map)
    kling_video_prompt = compile_video_for_kling(shot, cast_map, context)
"""

import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# KLING EMOTION → PERFORMANCE DIRECTION
# ─────────────────────────────────────────────
# Kling understands natural-language emotion. Give it emotional INTENT
# plus one anchoring physical action. Trust the model for micro-expressions.
KLING_EMOTION_DIRECTION = {
    "anger":          ("controlled fury", "jaw clenches, shoulders square"),
    "grief":          ("quiet devastation", "shoulders drop, breath catches"),
    "fear":           ("rising dread", "steps back, eyes widen"),
    "determination":  ("steely resolve", "straightens up, chin lifts"),
    "suspicion":      ("guarded wariness", "eyes narrow, weight shifts back"),
    "resentment":     ("bitter composure", "looks away, jaw tightens"),
    "curiosity":      ("engaged attention", "leans forward, brow lifts"),
    "tenderness":     ("gentle warmth", "reaches out, voice softens"),
    "authority":      ("commanding presence", "stands firm, eye contact direct"),
    "defiance":       ("bold resistance", "chin lifts, fists clench"),
    "vulnerability":  ("exposed fragility", "arms wrap around self, voice trembles"),
    "shock":          ("stunned stillness", "freezes mid-motion, breath stops"),
    "confrontation":  ("aggressive intent", "leans in, voice drops low"),
    "accusation":     ("pointed intensity", "points forward, voice sharpens"),
    "resignation":    ("weary acceptance", "sighs deeply, shoulders sag"),
    "tension":        ("held breath", "holds still, muscles tight"),
    "desperation":    ("frantic urgency", "voice breaks, hands shake"),
    "contempt":       ("cold dismissal", "slight sneer, turns away"),
    "longing":        ("aching desire", "gaze lingers, hand reaches"),
    "triumph":        ("barely contained victory", "slight smile, posture opens"),
}

# ─────────────────────────────────────────────
# SHOT TYPE → KLING CAMERA DIRECTION
# ─────────────────────────────────────────────
# Kling responds to cinematic camera vocabulary.
# Describe the VISUAL EFFECT, not just the label.
KLING_CAMERA_DIRECTION = {
    "close_up":          "Close-up, face fills frame, shallow depth of field",
    "medium_close":      "Medium close-up, head and shoulders, background softly blurred",
    "medium_close_up":   "Medium close-up, head and shoulders, background softly blurred",
    "extreme_close_up":  "Extreme close-up, eyes and mouth only, everything else out of focus",
    "medium":            "Medium shot, waist up, room context visible",
    "over_the_shoulder":  "Over-the-shoulder shot",
    "two_shot":          "Two shot, both characters visible, confrontational framing",
    "reaction":          "Reaction close-up, face fills frame, capturing micro-expression",
    "wide":              "Wide shot, full room geography visible, deep depth of field",
    "establishing":      "Establishing wide, full environment, characters small in frame",
    "closing":           "Closing shot, slow pull back, atmosphere settling",
}

# ─────────────────────────────────────────────
# PERFORMANCE VERBS (Kling prefers these over generic "speaks")
# ─────────────────────────────────────────────
KLING_PERFORMANCE_VERBS = {
    "anger":          "confronts",
    "grief":          "whispers",
    "fear":           "stammers",
    "determination":  "declares",
    "suspicion":      "questions",
    "resentment":     "retorts",
    "curiosity":      "asks",
    "tenderness":     "murmurs",
    "authority":      "commands",
    "defiance":       "challenges",
    "vulnerability":  "confesses",
    "shock":          "gasps",
    "confrontation":  "demands",
    "accusation":     "accuses",
    "resignation":    "admits",
    "tension":        "states",
}


def _get_appearance(char_name: str, cast_map: Optional[Dict]) -> str:
    """Get character appearance from cast_map (case-insensitive).

    T2-FE-13: FAL models don't know character NAMES.
    This returns the VISUAL DESCRIPTION that the model CAN understand.
    """
    if not cast_map or not char_name:
        return ""
    for key, val in cast_map.items():
        if key.upper() == char_name.upper():
            if isinstance(val, dict):
                return val.get("appearance", "")[:150]
    return ""


def _appearance_label(char_name: str, cast_map: Optional[Dict]) -> str:
    """Get a SHORT appearance-based label for a character (no names).

    T2-FE-13: FAL doesn't know names. Instead of 'THOMAS BLACKWOOD',
    return 'silver-haired man in navy suit' — what the model can see.
    """
    app = _get_appearance(char_name, cast_map)
    if not app:
        return "person"
    # Extract the most visually distinctive features for a short label
    # Take first 60 chars which typically has gender, age, key features
    short = app.split(",")[0].strip() if "," in app else app[:60]
    return short.lower()


def _get_emotion_direction(emotion: str) -> tuple:
    """Get (tone_label, physical_direction) for an emotion.

    Handles both single keywords ("anger") and full narrative beats
    ("Eleanor presents the financial reality and demands cooperation").
    Scans the text for emotion keywords and returns the best match.
    """
    emotion_key = emotion.lower().strip()
    if emotion_key in KLING_EMOTION_DIRECTION:
        return KLING_EMOTION_DIRECTION[emotion_key]
    # Fuzzy match: check if any key is contained in the emotion string
    for key, val in KLING_EMOTION_DIRECTION.items():
        if key in emotion_key:
            return val
    # V27.2: Parse narrative beats for emotional intent keywords
    # "demands cooperation" → confrontation, "refuses to let go" → defiance
    NARRATIVE_EMOTION_MAP = {
        "demands": "confrontation", "confronts": "confrontation", "argues": "confrontation",
        "presents": "authority", "declares": "authority", "announces": "authority",
        "refuses": "defiance", "resists": "defiance", "challenges": "defiance",
        "enters": "determination", "arrives": "determination", "approaches": "determination",
        "stares": "tension", "watches": "tension", "observes": "suspicion",
        "grief": "grief", "mourns": "grief", "cries": "grief",
        "follows reluctantly": "resignation", "reluctant": "resignation",
        "professional detachment": "authority", "surveying": "authority",
        "financial reality": "authority", "cooperation": "confrontation",
        "portrait": "longing", "memory": "longing", "remembers": "longing",
    }
    for phrase, mapped_emotion in NARRATIVE_EMOTION_MAP.items():
        if phrase in emotion_key:
            if mapped_emotion in KLING_EMOTION_DIRECTION:
                return KLING_EMOTION_DIRECTION[mapped_emotion]
    return ("intense focus", "subtle shift in posture")


def _get_performance_verb(emotion: str) -> str:
    """Get dialogue performance verb for an emotion."""
    emotion_key = emotion.lower().strip()
    if emotion_key in KLING_PERFORMANCE_VERBS:
        return KLING_PERFORMANCE_VERBS[emotion_key]
    for key, val in KLING_PERFORMANCE_VERBS.items():
        if key in emotion_key:
            return val
    return "delivers"


def _strip_names_from_text(text: str, characters: list, cast_map: Optional[Dict] = None) -> str:
    """Remove ALL character names from text — FAL doesn't know names (T2-FE-13).

    Scans BOTH the shot's characters[] AND the full cast_map for names to strip.
    Replaces character names with appearance-based labels:
      'Eleanor opens briefcase' → 'the auburn-haired woman opens briefcase'
      'THOMAS BLACKWOOD: pawing' → 'the silver-haired man: pawing'
      'Mr. Blackwood' → 'the silver-haired man'
      'Harriet' → 'the figure'
    """
    result = text

    # Build complete name list from BOTH characters[] and cast_map
    all_names = {}  # name_variant → appearance_label
    for char in characters:
        cn = char if isinstance(char, str) else str(char)
        label = _appearance_label(cn, cast_map) if cast_map else "the figure"
        if not label or label == "person":
            label = "the figure"
        elif not label.startswith("the "):
            label = f"the {label}"
        all_names[cn] = label
        # First name
        if " " in cn:
            all_names[cn.split()[0]] = label
            # Last name too (for "Mr. Blackwood", "Ms. Voss")
            for part in cn.split()[1:]:
                if len(part) > 2:
                    all_names[part] = label

    # Also scan cast_map for names not in this shot's characters[]
    if cast_map:
        for cm_name in cast_map:
            if cm_name not in all_names:
                label = _appearance_label(cm_name, cast_map)
                if not label or label == "person":
                    label = "the figure"
                elif not label.startswith("the "):
                    label = f"the {label}"
                all_names[cm_name] = label
                if " " in cm_name:
                    for part in cm_name.split():
                        if len(part) > 2:
                            all_names[part] = label

    # Sort by length descending so "THOMAS BLACKWOOD" is replaced before "THOMAS"
    for name in sorted(all_names.keys(), key=len, reverse=True):
        if len(name) <= 2:
            continue
        label = all_names[name]
        result = re.sub(r'\b' + re.escape(name) + r'\b', label, result, flags=re.IGNORECASE)

    return result


def _extract_dialogue_speaker_and_text(shot: Dict, cast_map: Optional[Dict] = None) -> tuple:
    """Extract (speaker_name, dialogue_text) from shot data.

    Returns the speaker NAME (for internal routing) and the CLEANED dialogue
    text with names stripped (T2-FE-13).

    V27.2: Handles multi-segment dialogue format:
    "CHAR: text | CHAR: more text" → "text more text" (names stripped, pipes cleaned)
    """
    dialogue = shot.get("dialogue_text") or shot.get("dialogue") or ""
    if not dialogue:
        return "", ""
    dialogue = dialogue.strip()
    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    # Build set of character name variants for stripping from dialogue markers
    _char_names_upper = set()
    for c in characters:
        c_str = c if isinstance(c, str) else str(c)
        _char_names_upper.add(c_str.upper())
        for part in c_str.upper().split():
            if len(part) > 2:
                _char_names_upper.add(part)

    # Also pull names from full cast_map for thorough stripping
    if cast_map:
        for k in cast_map:
            if isinstance(cast_map[k], dict) and cast_map[k].get("appearance"):
                _char_names_upper.add(k.upper())
                for part in k.upper().split():
                    if len(part) > 2:
                        _char_names_upper.add(part)

    # Split on pipe segments and extract clean text from each
    segments = dialogue.split("|")
    speaker = ""
    text_parts = []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        # Try to extract "NAME: text" pattern
        if ":" in seg[:60]:
            before_colon = seg.split(":", 1)[0].strip().upper()
            after_colon = seg.split(":", 1)[1].strip()

            # Check if before_colon is a character name marker
            is_name_marker = before_colon in _char_names_upper
            if not is_name_marker:
                # Check if it's a partial match (e.g. "THOMAS BLACKWOOD" or just "THOMAS")
                for cn in _char_names_upper:
                    if before_colon == cn or before_colon in cn.split() or cn in before_colon.split():
                        is_name_marker = True
                        break

            if is_name_marker:
                # This is "CHARACTER_NAME: dialogue text" — extract just the text
                if not speaker:
                    # Use first speaker found for routing
                    for c in characters:
                        c_up = c.upper() if isinstance(c, str) else str(c).upper()
                        if before_colon == c_up or before_colon in set(c_up.split()):
                            speaker = c if isinstance(c, str) else str(c)
                            break
                text_parts.append(after_colon)
            else:
                # Not a name marker — keep the whole segment (might be mid-sentence with colon)
                text_parts.append(seg)
        else:
            text_parts.append(seg)

    if not speaker and characters:
        speaker = characters[0] if isinstance(characters[0], str) else str(characters[0])

    # Join all text parts into clean dialogue
    text = " ".join(t.strip() for t in text_parts if t.strip())

    # Strip quotes
    text = text.strip('"').strip("'").strip()

    # T2-FE-13: Final pass — strip any remaining character names from dialogue text
    if cast_map:
        text = _strip_names_from_text(text, characters, cast_map)

    return speaker, text


def compile_for_kling(shot: Dict, cast_map: Optional[Dict] = None) -> str:
    """
    Compile a Kling-optimized FIRST FRAME (image) prompt.

    This is for nano-banana-pro text-to-image generation.
    Kling-specific: character tags, appearance, atmosphere.
    Max 2500 chars. Directorial language.
    """
    parts = []

    # 1. Camera direction
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
    cam_dir = KLING_CAMERA_DIRECTION.get(shot_type, "Medium shot, waist up")
    parts.append(cam_dir)

    # 2. Characters with appearance (Kling character tag format)
    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    is_ots = "over_the_shoulder" in shot_type or "ots" in shot_type
    speaker = shot.get("_ots_speaker", "")
    listener = shot.get("_ots_listener", "")

    # T2-FE-13: FAL doesn't know names — use APPEARANCE DESCRIPTIONS only
    if is_ots and speaker and listener:
        sp_app = _get_appearance(speaker, cast_map) or "speaker"
        ls_app = _get_appearance(listener, cast_map) or "listener"
        parts.append(f"[Character A: {sp_app}] faces camera")
        parts.append(f"[Character B: {ls_app}] back to camera, shoulder visible foreground")
    elif characters:
        for i, char in enumerate(characters[:2]):
            cn = char if isinstance(char, str) else str(char)
            app = _get_appearance(cn, cast_map)
            if app:
                parts.append(f"[Character {'AB'[i]}: {app}]")
            else:
                parts.append(f"[Character {'AB'[i]}: person]")

    # 3. Emotional state (natural language — Kling's strength)
    beat = shot.get("beat") or shot.get("emotional_beat") or ""
    emotion = beat.lower().strip() if beat else ""
    if emotion:
        tone, physical = _get_emotion_direction(emotion)
        parts.append(f"{tone}, {physical}")

    # 4. Room DNA (if baked)
    room_dna = ""
    nano = shot.get("nano_prompt", "")
    dna_match = re.search(r'\[ROOM DNA:([^\]]+)\]', nano)
    if dna_match:
        room_dna = dna_match.group(1).strip()[:200]
        parts.append(room_dna)
    else:
        # Location atmosphere
        location = shot.get("location", "")
        if location:
            parts.append(location[:100])

    # 5. Lighting rig (if baked)
    rig_match = re.search(r'\[LIGHTING RIG:([^\]]+)\]', nano)
    if rig_match:
        parts.append(rig_match.group(1).strip()[:100])

    # Combine
    prompt = ". ".join(p.strip().rstrip(".") for p in parts if p.strip())
    prompt += ". NO grid, NO collage, NO split screen"

    # Enforce 2500 char limit
    if len(prompt) > 2500:
        prompt = prompt[:2497] + "..."

    return prompt


def compile_video_for_kling(shot: Dict, cast_map: Optional[Dict] = None,
                             context: Optional[Dict] = None) -> str:
    """
    Compile a Kling-optimized VIDEO prompt (image-to-video).

    THIS IS THE KEY FUNCTION — called by the Kling I2V endpoint.

    Kling 3.0 video prompts should read like director's instructions:
      Scene → Characters → Action over time → Dialogue → Camera behavior

    Kling understands:
      - Natural-language emotion direction
      - Dialogue with character attribution and tone
      - Camera movement described as behavior over time
      - Native physics for body motion (don't over-specify)

    Trust Kling for: body physics, micro-expressions, breathing, weight shifts
    Specify for Kling: WHO speaks, WHAT they say, HOW they feel, WHERE camera goes

    Max 2500 chars (Kling's actual limit, not the old 250).
    """
    parts = []
    context = context or {}

    # ── 1. CAMERA DIRECTION (cinematic intent) ──
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
    cam_dir = KLING_CAMERA_DIRECTION.get(shot_type, "Medium shot")

    # Add camera movement behavior
    is_ots = "over_the_shoulder" in shot_type or "ots" in shot_type
    is_closeup = shot_type in ("close_up", "medium_close", "medium_close_up",
                                "extreme_close_up", "reaction")

    if is_ots:
        parts.append(f"{cam_dir}, camera holds steady on dialogue axis")
    elif is_closeup:
        parts.append(f"{cam_dir}, camera barely drifts, holding intimate distance")
    elif shot_type in ("wide", "establishing"):
        parts.append(f"{cam_dir}, slow subtle push in")
    else:
        parts.append(cam_dir)

    # ── 2. CHARACTERS WITH APPEARANCE + SPATIAL POSITION ──
    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    speaker_name = shot.get("_ots_speaker", "")
    listener_name = shot.get("_ots_listener", "")
    screen_positions = {}  # char_name → frame-left/frame-right

    # Extract screen positions from existing prompt
    nano = shot.get("nano_prompt", "")
    for char in characters:
        cn = char if isinstance(char, str) else str(char)
        cn_first = cn.split()[0].upper()
        if f"{cn_first}" in nano.upper():
            if "FRAME-LEFT" in nano.upper() and cn_first in nano.upper().split("FRAME-LEFT")[0][-50:]:
                screen_positions[cn] = "frame-left"
            elif "FRAME-RIGHT" in nano.upper() and cn_first in nano.upper().split("FRAME-RIGHT")[0][-50:]:
                screen_positions[cn] = "frame-right"

    # T2-FE-13: FAL doesn't know names — use APPEARANCE DESCRIPTIONS only
    if is_ots and speaker_name and listener_name:
        sp_app = _get_appearance(speaker_name, cast_map) or "speaker"
        ls_app = _get_appearance(listener_name, cast_map) or "listener"
        sp_pos = screen_positions.get(speaker_name, "frame-right")
        ls_pos = screen_positions.get(listener_name, "frame-left")
        parts.append(
            f"[Character A: {sp_app}] {sp_pos}, faces camera. "
            f"[Character B: {ls_app}] {ls_pos}, back to camera, shoulder visible"
        )
    elif len(characters) >= 2 and shot_type == "two_shot":
        for i, char in enumerate(characters[:2]):
            cn = char if isinstance(char, str) else str(char)
            app = _get_appearance(cn, cast_map) or "person"
            pos = screen_positions.get(cn, "frame-left" if i == 0 else "frame-right")
            parts.append(f"[Character {'AB'[i]}: {app}] {pos}")
    elif characters:
        cn = characters[0] if isinstance(characters[0], str) else str(characters[0])
        app = _get_appearance(cn, cast_map) or "person"
        parts.append(f"[Character A: {app}]")

    # ── 3. EMOTION + PERFORMANCE DIRECTION ──
    beat = shot.get("beat") or shot.get("emotional_beat") or ""
    emotion = beat.lower().strip() if beat else ""
    beat_action = shot.get("_beat_character_action", "")

    if emotion:
        tone, physical = _get_emotion_direction(emotion)
        if beat_action:
            # T2-FE-13: Strip ALL character names from beat action (uses full cast_map)
            clean_action = _strip_names_from_text(beat_action, characters, cast_map)
            parts.append(f"{tone}. {clean_action}")
        else:
            parts.append(f"{tone}, {physical}")

    # ── 4. DIALOGUE (Kling's native audio comprehension) ──
    # T2-FE-13: Use appearance label, NOT character name — FAL doesn't know names
    speaker, dialogue_text = _extract_dialogue_speaker_and_text(shot, cast_map)
    if dialogue_text and speaker:
        verb = _get_performance_verb(emotion) if emotion else "delivers"
        tone_label = _get_emotion_direction(emotion)[0] if emotion else "measured"
        speaker_label = _appearance_label(speaker, cast_map)
        dlg_trimmed = dialogue_text[:300]
        parts.append(
            f'[{speaker_label}, {tone_label} voice] {verb}: "{dlg_trimmed}"'
        )
        parts.append(f"mouth moves forming words, natural speech rhythm, lips sync to dialogue")

    # ── 5. TIMED CHOREOGRAPHY (if baked from quality gate) ──
    # Extract per-second action choreography and convert to Kling directorial beats
    timed_choreo = shot.get("_timed_choreography") or ""
    if not timed_choreo:
        ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in ltx:
            # Capture everything between TIMED CHOREOGRAPHY: and next section marker
            choreo_match = re.search(
                r'TIMED CHOREOGRAPHY:\s*(.+?)(?=\[|FACE IDENTITY|BODY PERFORMANCE|$)',
                ltx, re.DOTALL
            )
            if choreo_match:
                timed_choreo = choreo_match.group(1).strip()

    if timed_choreo:
        # T2-FE-13: Strip character names from choreography
        timed_choreo = _strip_names_from_text(timed_choreo, characters, cast_map)

        # Convert LTX per-second timestamps to Kling directorial flow
        # "0-2s: he faces her. 2-4s: she extends folder" → "He faces her. Then she extends folder"
        choreo_clean = re.sub(r'\d+-\d+s:\s*', '', timed_choreo)
        beats = [b.strip() for b in choreo_clean.split('.') if b.strip() and len(b.strip()) > 5]

        if beats:
            # Kling gets 3-4 directional beats with "then" transitions
            kling_choreo = beats[0].capitalize()
            for b in beats[1:4]:
                b_clean = b.strip()
                if b_clean and b_clean[0].isupper():
                    kling_choreo += f". Then {b_clean[0].lower()}{b_clean[1:]}"
                else:
                    kling_choreo += f". Then {b_clean}"
            parts.append(kling_choreo)

    # ── 6. SPLIT ANTI-MORPH (V27.2 — face lock + body free — T2-FE-22) ──
    if characters:
        parts.append(
            "FACE IDENTITY LOCK: facial structure UNCHANGED, NO face morphing, NO identity drift. "
            "BODY PERFORMANCE FREE: natural breathing, weight shifts, hand gestures CONTINUE."
        )

    # ── 7. ROOM ATMOSPHERE (condensed from DNA — Kling doesn't need full DNA) ──
    room_dna = context.get("_room_dna", "")
    if not room_dna:
        dna_match = re.search(r'\[ROOM DNA:([^\]]+)\]', nano)
        if dna_match:
            room_dna = dna_match.group(1).strip()

    # V27.2: Fallback — extract room description from location field or description
    # T2-FE-13: Strip character surnames from location names to prevent contamination
    if not room_dna:
        location = shot.get("location", "") or shot.get("scene_location", "") or ""
        description = shot.get("description", "") or shot.get("scene_description", "") or ""
        if location:
            # Strip character-associated names from location (e.g., "HARGROVE ESTATE" → "ESTATE")
            loc_clean = location
            if cast_map:
                for k in cast_map:
                    if isinstance(cast_map[k], dict) and cast_map[k].get("appearance"):
                        for part in k.upper().split():
                            if len(part) > 3 and part in loc_clean.upper():
                                loc_clean = re.sub(r'(?i)\b' + re.escape(part) + r"('?s?)?\s*", '', loc_clean).strip()
            loc_clean = re.sub(r'\s+', ' ', loc_clean).strip(" -_")
            room_dna = loc_clean if loc_clean else location
            if description:
                desc_clean = _strip_names_from_text(description[:100], [], cast_map) if cast_map else description[:100]
                room_dna += f". {desc_clean}"

    if room_dna:
        # Extract just the key architectural words for atmosphere
        parts.append(f"Setting: {room_dna[:150]}")

    lighting = context.get("_lighting_rig", "")
    if not lighting:
        rig_match = re.search(r'\[LIGHTING RIG:([^\]]+)\]', nano)
        if rig_match:
            lighting = rig_match.group(1).strip()
    if lighting:
        parts.append(lighting[:80])

    # ── COMBINE AND ENFORCE LIMIT ──
    prompt = ". ".join(p.strip().rstrip(".") for p in parts if p.strip())

    # Enforce 2500 char limit (Kling's actual max)
    if len(prompt) > 2500:
        prompt = prompt[:2497] + "..."

    logger.info(f"[KLING-COMPILE] {shot.get('shot_id', '?')}: {len(prompt)} chars, "
                f"dialogue={'YES' if dialogue_text else 'NO'}, "
                f"emotion={emotion or 'none'}")

    return prompt


def compile_for_ltx(shot: Dict, cast_map: Optional[Dict] = None) -> str:
    """
    Return the full LTX prompt as-is (or from ltx_motion_prompt).
    LTX benefits from maximum prompt density.

    T2-FE-15: Keep LTX prompts full — camera + physical chain +
    performance verb + emotion + environment. Max 900 chars.
    """
    ltx = shot.get("ltx_motion_prompt", "")
    if not ltx:
        ltx = shot.get("nano_prompt", "")

    # Enforce 900 char max
    if len(ltx) > 900:
        ltx = ltx[:897] + "..."

    return ltx


def route_and_compile(shot: Dict, cast_map: Optional[Dict] = None,
                      context: Optional[Dict] = None) -> Dict:
    """
    Route shot to optimal model and compile appropriate prompt.

    Returns: {
        "model": "kling" | "ltx",
        "frame_prompt": str,      # For first-frame generation
        "video_prompt": str,      # For image-to-video generation
        "reason": str,
        "prompt_length": int
    }
    """
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
    has_dialogue = bool(shot.get("dialogue_text"))
    has_characters = bool(shot.get("characters"))

    # Routing logic (from probe evidence)
    use_kling = False
    reason = ""

    if has_dialogue and has_characters:
        use_kling = True
        reason = "Dialogue shot — Kling identity lock + native voice"
    elif shot_type in ("reaction", "close_up", "extreme_close_up", "medium_close_up", "medium_close"):
        use_kling = True
        reason = f"{shot_type} — Kling micro-expression fidelity"
    elif "over_the_shoulder" in shot_type or "ots" in shot_type:
        use_kling = True
        reason = "OTS dialogue — Kling two-character native handling"
    else:
        reason = f"{shot_type} — LTX motion + environment detail"

    if use_kling:
        frame_prompt = compile_for_kling(shot, cast_map)
        video_prompt = compile_video_for_kling(shot, cast_map, context)
        return {
            "model": "kling",
            "frame_prompt": frame_prompt,
            "video_prompt": video_prompt,
            "reason": reason,
            "prompt_length": len(video_prompt),
        }
    else:
        ltx_prompt = compile_for_ltx(shot, cast_map)
        return {
            "model": "ltx",
            "frame_prompt": shot.get("nano_prompt", ""),
            "video_prompt": ltx_prompt,
            "reason": reason,
            "prompt_length": len(ltx_prompt),
        }


def batch_route_and_compile(shots: list, cast_map: dict,
                             context: Optional[Dict] = None) -> Dict:
    """Route all shots and return routing summary."""
    results = {"kling": [], "ltx": [], "routing": {}}

    for shot in shots:
        shot_id = shot.get("shot_id", "?")
        route = route_and_compile(shot, cast_map, context)
        results["routing"][shot_id] = route

        if route["model"] == "kling":
            results["kling"].append(shot_id)
        else:
            results["ltx"].append(shot_id)

    results["summary"] = {
        "total": len(shots),
        "kling_count": len(results["kling"]),
        "ltx_count": len(results["ltx"]),
        "kling_pct": round(100 * len(results["kling"]) / max(len(shots), 1), 1),
    }

    return results
