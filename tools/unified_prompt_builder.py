#!/usr/bin/env python3
"""
UNIFIED PROMPT BUILDER — V25.1
================================
ONE function builds the COMPLETE prompt. ONE time. FINAL.

Design principle: What you see in UI = What goes to FAL = What you get back.

V25.1 UPDATE: Integrated Creative Prompt Compiler for:
- Motivated LTX motion (replaces generic CAMERA_TIMING templates)
- Decontamination pass (strips all generic filler patterns)
- 6-discipline quality scoring (Writer, Director, DP, Editor, Actor, Sound)

Order of operations (all in one pass):
1. Base prompt (from shot_plan)
2. Creative LTX motion (motivated by shot type + emotion + beat) ← V25.1
3. Wardrobe (if characters present)
4. Emotion/Acting (if characters present)
5. Location atmosphere
6. Director camera style
7. Gold standard negatives
8. Decontamination sweep ← V25.1
9. Length cap

Result is FINAL. Saved to nano_prompt_final / ltx_motion_prompt_final.
No further modification allowed.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.unified_prompt_builder")

# Try to import Creative Prompt Compiler (V25.1)
try:
    from tools.creative_prompt_compiler import (
        build_ltx_motion,
        decontaminate_prompt,
        is_prompt_generic,
        validate_prompt_quality,
    )
    HAS_CPC = True
except ImportError:
    HAS_CPC = False
    logger.warning("[UNIFIED] Creative Prompt Compiler not available — using legacy templates")

# ============================================================
# CAMERA TIMING TEMPLATES (LEGACY FALLBACK — only used if CPC unavailable)
# ============================================================
CAMERA_TIMING = {
    # V25.5: Legacy fallback — only fires if CPC unavailable. Uses motivated language, not static holds.
    "dialogue": "character speaks with purpose from first frame, engaged, face stable, character consistent",
    "close_up": "character performs controlled tension, weight shifts visible, face stable NO morphing",
    "extreme_close_up": "character performs micro-adjustments, eyes active, face stable NO morphing",
    "medium_close_up": "character performs controlled tension, posture engaged, face stable NO morphing",
    "wide": "slow controlled push into space, atmosphere deepens, architectural depth visible",
    "establishing": "measured reveal of space, environmental texture, atmosphere established",
    "master": "slow controlled push into space, atmosphere deepens, scale established",
    "reaction": "character reacts, processing what was said, face stable NO morphing",
    "insert": "detail visible, shallow depth of field, texture readable, NO morphing, NO face generation",
    "detail": "detail visible, shallow depth of field, texture readable, NO morphing, NO face generation",
    "cutaway": "environmental detail, atmospheric texture, NO morphing, NO face generation",
    "default": "measured movement, purposeful blocking, face stable NO morphing",
}

# ============================================================
# GOLD STANDARD NEGATIVES
# ============================================================
GOLD_NANO_NEGATIVES = "NO grid, NO collage, NO split screen, NO extra people, NO morphing faces, NO watermarks, NO text overlays, NO babies, NO children unless script specifies"
GOLD_LTX_SUFFIX_CHAR = "face stable NO morphing, character consistent"
GOLD_LTX_SUFFIX_DIALOGUE = "face stable, character consistent, natural speech movement, lips moving"
GOLD_LTX_SUFFIX_ENV = "NO morphing, NO face generation, environment only"

# ============================================================
# MAIN BUILDER FUNCTION
# ============================================================
def build_final_prompts(
    shot: Dict,
    wardrobe: Optional[Dict] = None,
    emotion_layer: Optional[Dict] = None,
    location_data: Optional[Dict] = None,
    director_profile: Optional[Dict] = None,
    cast_map: Optional[Dict] = None,
    story_bible: Optional[Dict] = None,
) -> Tuple[str, str]:
    """
    Build FINAL nano_prompt and ltx_motion_prompt for a shot.

    This is the ONE function that creates the complete prompt.
    All enrichment happens here, in order, with dedup checks.

    V25.1: Uses Creative Prompt Compiler for motivated motion direction
    instead of generic CAMERA_TIMING templates.

    Returns: (nano_prompt_final, ltx_motion_prompt_final)
    """
    shot_id = shot.get("shot_id", "")
    scene_id = shot.get("scene_id", "") or (shot_id.split("_")[0] if "_" in shot_id else "")
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
    characters = shot.get("characters", [])
    has_chars = bool(characters)
    has_dialogue = bool(shot.get("dialogue_text") or shot.get("dialogue"))
    duration = shot.get("duration", 8)
    character = characters[0] if characters else ""

    # Infer emotion from shot metadata
    emotion = _infer_emotion(shot, emotion_layer)

    # Get beat description for this shot
    beat_desc = _get_beat_description(shot, story_bible)

    # Start with base prompts
    nano = shot.get("nano_prompt", "") or ""
    ltx = shot.get("ltx_motion_prompt", "") or ""

    # ── LAYER 1: Creative LTX Motion (V25.1) ──
    # Replaces generic CAMERA_TIMING with motivated, research-backed motion
    if HAS_CPC:
        coverage_role = shot.get("coverage_role", "")
        creative_ltx = build_ltx_motion(
            shot_type=shot_type,
            character=character,
            emotion=emotion,
            has_dialogue=has_dialogue,
            beat_desc=beat_desc,
            duration=duration,
            coverage_role=coverage_role,
        )
        # V25.6: CPC is the AUTHORITY on LTX content — always use its output
        # fix-v16 is structural plumbing only (durations, segments, coverage)
        # CPC owns all motion/performance/dialogue direction
        if creative_ltx:
            ltx = creative_ltx
    else:
        # Legacy fallback: use CAMERA_TIMING templates
        if has_dialogue:
            timing_key = "dialogue"
        else:
            timing_key = shot_type if shot_type in CAMERA_TIMING else "default"
        timing = CAMERA_TIMING[timing_key]
        if timing.split(",")[0] not in ltx:
            ltx = timing + ". " + ltx if ltx else timing

    # ── LAYER 2: Wardrobe (characters only) ──
    if has_chars and wardrobe:
        wardrobe_tag = _get_wardrobe_for_shot(wardrobe, shot)
        if wardrobe_tag and "wearing:" not in nano.lower():
            nano = f"{character} wearing: {wardrobe_tag}. " + nano
            ltx = f"wardrobe continuity: {character} same outfit throughout. " + ltx

    # ── LAYER 3: Emotion/Acting (characters only) ──
    if has_chars and emotion_layer:
        acting_block = _get_emotion_for_shot(emotion_layer, shot)
        if acting_block and "ACTING" not in ltx:
            # Insert after first sentence
            parts = ltx.split(". ", 1)
            if len(parts) > 1:
                ltx = parts[0] + ". " + acting_block + ". " + parts[1]
            else:
                ltx = ltx + ". " + acting_block

    # ── LAYER 4: Location Atmosphere ──
    if location_data:
        location_desc = _get_location_description(location_data, shot)
        if location_desc and "Setting:" not in nano:
            nano = nano + f" Setting: {location_desc}"

    # ── LAYER 5: Director Camera Style (ONE time only) ──
    if director_profile and "director camera:" not in ltx:
        director_motion = director_profile.get("camera_philosophy", "")
        if director_motion:
            ltx = ltx + f". director camera: {director_motion}"

    # ── LAYER 6: Gold Standard Negatives ──
    if "NO grid" not in nano:
        nano = nano.rstrip(". ") + ". " + GOLD_NANO_NEGATIVES

    if has_chars:
        if has_dialogue:
            if "face stable" not in ltx:
                ltx = ltx.rstrip(". ") + ", " + GOLD_LTX_SUFFIX_DIALOGUE
        else:
            if "face stable" not in ltx:
                ltx = ltx.rstrip(". ") + ", " + GOLD_LTX_SUFFIX_CHAR
    else:
        if "NO morphing" not in ltx:
            ltx = ltx.rstrip(". ") + ", " + GOLD_LTX_SUFFIX_ENV

    # ── LAYER 7: Duration Tag ──
    if f"{int(duration)}s" not in ltx:
        ltx = ltx.rstrip(". ") + f", {int(duration)}s"

    # ── LAYER 8 (V25.1): DECONTAMINATION SWEEP ──
    # Final check — strip any generic patterns that survived all layers
    if HAS_CPC:
        if is_prompt_generic(nano):
            nano = decontaminate_prompt(nano, character, emotion, beat_desc)
        if is_prompt_generic(ltx):
            ltx = decontaminate_prompt(ltx, character, emotion, beat_desc)

    # ── FINAL: Clean up and cap length ──
    nano = _clean_prompt(nano, max_len=3000)
    ltx = _clean_prompt(ltx, max_len=1500)

    logger.info(f"[UNIFIED] {shot_id}: nano={len(nano)} chars, ltx={len(ltx)} chars")

    return nano, ltx


def _infer_emotion(shot: Dict, emotion_layer: Optional[Dict] = None) -> str:
    """Infer emotion from shot metadata, emotion layer, or prompt content."""
    # Check emotion_layer first
    if emotion_layer:
        acting = _get_emotion_for_shot(emotion_layer, shot)
        if acting:
            # Extract emotion keyword from acting block
            for e in ["grief", "tension", "anger", "fear", "revelation", "joy", "love"]:
                if e in acting.lower():
                    return e

    # Check state_in
    state_in = shot.get("state_in", {})
    if isinstance(state_in, dict):
        for char_state in state_in.values():
            if isinstance(char_state, dict):
                e = char_state.get("emotion", "") or char_state.get("emotion_read", "")
                if e:
                    return e

    # Infer from nano content
    nano = (shot.get("nano_prompt") or "").lower()
    if any(w in nano for w in ["grief", "mourn", "loss", "sorrow"]):
        return "grief"
    if any(w in nano for w in ["tension", "dread", "fear", "ominous"]):
        return "tension"
    if any(w in nano for w in ["anger", "rage", "furious", "confront"]):
        return "anger"
    if any(w in nano for w in ["reveal", "discover", "shock"]):
        return "revelation"

    return "neutral"


def _get_beat_description(shot: Dict, story_bible: Optional[Dict] = None) -> str:
    """Get beat description for proportional mapping."""
    if not story_bible:
        return ""

    shot_id = shot.get("shot_id", "")
    scene_id = shot_id.split("_")[0] if "_" in shot_id else ""
    if not scene_id:
        return ""

    scenes = story_bible.get("scenes", [])
    scene_beats = []
    for sc in scenes:
        sc_id = str(sc.get("scene_id", sc.get("scene_number", ""))).zfill(3)
        if sc_id == scene_id:
            scene_beats = sc.get("beats", sc.get("story_beats", []))
            break

    if not scene_beats:
        return ""

    # Use character_action if available, fall back to description
    # Proportional mapping would need shot index, but we can use the first available
    for beat in scene_beats:
        action = beat.get("character_action", "")
        if action and "experiences" not in action.lower():
            return action

    for beat in scene_beats:
        desc = beat.get("description", "")
        if desc:
            return desc

    return ""


def _get_wardrobe_for_shot(wardrobe: Dict, shot: Dict) -> str:
    """Get wardrobe tag for shot's character/scene."""
    chars = shot.get("characters", [])
    if not chars:
        return ""
    scene_id = shot.get("scene_id", "")
    char = chars[0].upper()

    char_wardrobe = wardrobe.get(char, {})
    scene_look = char_wardrobe.get(scene_id, char_wardrobe.get("default", {}))
    return scene_look.get("wardrobe_tag", "")


def _get_emotion_for_shot(emotion_layer: Dict, shot: Dict) -> str:
    """Get ACTING block for shot."""
    shot_id = shot.get("shot_id", "")
    scene_id = shot.get("scene_id", "") or (shot_id.split("_")[0] if "_" in shot_id else "")
    scene_key = f"scene_{scene_id}"

    scene_emotions = emotion_layer.get(scene_key, {})
    shot_emotion = scene_emotions.get(shot_id, {})
    return shot_emotion.get("acting_block", "")


def _get_location_description(location_data: Dict, shot: Dict) -> str:
    """Get location atmosphere description."""
    location = shot.get("location", "")
    return location_data.get(location, {}).get("atmosphere", "")


def _clean_prompt(text: str, max_len: int = 3000) -> str:
    """Clean up prompt text and cap length."""
    import re
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.+', '.', text)
    text = re.sub(r',+', ',', text)
    if len(text) > max_len:
        text = text[:max_len-3] + "..."
    return text.strip()


# ============================================================
# BATCH PROCESSOR — Apply to all shots at once
# ============================================================
def build_all_final_prompts(
    shots: List[Dict],
    project_path: Path,
    cast_map: Optional[Dict] = None,
) -> int:
    """
    Build final prompts for ALL shots in one pass.
    Loads wardrobe, emotion, location data once and applies to all.

    V25.1: Also loads story_bible for beat descriptions and
    runs Creative Prompt Compiler decontamination.

    Returns: number of shots processed
    """
    # Load support data
    wardrobe = _load_json(project_path / "wardrobe.json")
    emotion_layer = _load_json(project_path / "emotion_layer.json")
    story_bible = _load_json(project_path / "story_bible.json")

    # Extract location data from story bible
    location_data = {}
    if isinstance(story_bible, dict):
        for loc in story_bible.get("locations", []):
            loc_name = loc.get("name", "")
            location_data[loc_name] = loc

    # Get director profile if available
    director_profile = None
    if isinstance(story_bible, dict):
        director_profile = story_bible.get("director_profile", {})

    # Build prompts for each shot
    count = 0
    for shot in shots:
        nano_final, ltx_final = build_final_prompts(
            shot=shot,
            wardrobe=wardrobe,
            emotion_layer=emotion_layer,
            location_data=location_data,
            director_profile=director_profile,
            cast_map=cast_map,
            story_bible=story_bible,
        )

        # Save as FINAL — these are what go to FAL
        shot["nano_prompt_final"] = nano_final
        shot["ltx_motion_prompt_final"] = ltx_final
        shot["_unified_builder_applied"] = True
        count += 1

    logger.info(f"[UNIFIED] Built final prompts for {count} shots")
    return count


def _load_json(path: Path) -> Dict:
    """Load JSON file, return empty dict on error."""
    try:
        if path.exists():
            return json.load(open(path))
    except Exception:
        pass
    return {}
