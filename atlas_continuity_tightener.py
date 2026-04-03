"""
ATLAS CONTINUITY TIGHTENER V1.0 (Nano Pro Edit only; no Qwen)

Goal:
- Stop "rebuilding the room" every shot.
- Make the chain image-dominant (last frame -> next first frame).
- Enforce strict prompt separation:
    * SCENE LOCK (environment) lives once per scene (immutable)
    * SHOT ACTION (movement/emotion) per shot
    * CAMERA REFRAME (angle change only) when needed
- Use Nano Pro Edit for BOTH:
    1) first-frame creation (scene anchor)
    2) camera reframe edits (angle changes) on last_frame
- LTX/Kling only generate video from the first frame.
- Extract last frame and chain forward.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("atlas.continuity_tightener")

# -----------------------------
# 1) POLICY (THE ACTUAL RULES)
# -----------------------------

@dataclass(frozen=True)
class ContinuityPolicy:
    # If True: shot prompts cannot restate environment nouns (room, walls, candles, altar, etc.)
    forbid_env_in_shot_prompt: bool = True

    # If True: all reframes must use image edit instruction "do not change environment"
    strict_reframe_only: bool = True

    # When chaining, we never "recreate location"; we always transform from last_frame.
    chain_requires_last_frame: bool = True

    # Optional: enforce that the scene lock is attached to Shot 1 only
    scene_lock_only_on_first_shot: bool = True

    # If True: hair/wardrobe stable language is always injected
    force_appearance_lock_language: bool = True


POLICY = ContinuityPolicy()


# -----------------------------------------
# 2) TEMPLATES (PROMPT ROLES + LANGUAGE)
# -----------------------------------------

APPEARANCE_LOCK = """APPEARANCE LOCK (do not change):
- Preserve exact face identity and features.
- Preserve hairstyle, hair length, hairline, hair texture.
- Preserve wardrobe cut, color, fabric, and accessories.
- Preserve skin tone and age.
- No morphing, no face drift, no outfit swap.""".strip()

# This is the key: we stop describing the room every shot.
REFRAME_ONLY_HEADER = """REFRAME ONLY:
Use the provided image as the single source of truth.
Change ONLY camera framing and lens feel as instructed.
Do NOT change environment, room layout, props, objects, symbols, candles, altar, walls, floor, ceiling, windows, lighting direction, shadows, or color grade.
Do NOT add or remove anything.
Do NOT relocate characters or props.""".strip()

# Scene lock is allowed only once (Shot 1), then we rely on chaining.
SCENE_LOCK_HEADER = """SCENE LOCK (immutable for this scene):
This defines the environment. Keep it consistent for the entire scene.""".strip()

# Shot action should be lightweight and only movement/emotion/blocking.
SHOT_ACTION_HEADER = """SHOT ACTION:
Only describe character action, blocking, emotion, and moment-to-moment change.
Do NOT restate the room, environment, or set dressing.""".strip()


# ------------------------------------------
# 3) ENV-DRIFT GUARD (ENFORCE THE CHANGE)
# ------------------------------------------

# These nouns cause rebuilds when restated in shot prompts.
# Add project-specific drift nouns here.
ENV_DRIFT_PATTERNS = [
    r"\britual\b",
    r"\bchamber\b",
    r"\broom\b",
    r"\baltar\b",
    r"\bcandles?\b",
    r"\bsigils?\b",
    r"\bstone\b",
    r"\bwalls?\b",
    r"\bwindow\b",
    r"\bmoonlight\b",
    r"\bgothic\b",
    r"\bcathedral\b",
    r"\bcrypt\b",
    r"\bthrone\b",
    r"\btorch\b",
    r"\bmanor\b",
    r"\bfoyer\b",
    r"\bhallway\b",
    r"\bchapel\b",
    r"\bparlour\b",
    r"\bparlor\b",
    r"\blibrary\b",
    r"\bfireplace\b",
    r"\bchandelier\b",
    r"\bstaircase\b",
    r"\bcorridor\b",
    r"\bdungeon\b",
    r"\bcellar\b",
    r"\bgraveyard\b",
    r"\bcemetery\b",
]

_ENV_DRIFT_RE = re.compile("|".join(ENV_DRIFT_PATTERNS), re.IGNORECASE)


def check_env_drift(shot_action_text: str) -> List[str]:
    """
    Returns list of environment words found in shot action text.
    Empty list = clean.
    """
    if not shot_action_text:
        return []
    return _ENV_DRIFT_RE.findall(shot_action_text or "")


def strip_env_from_prompt(prompt_text: str) -> str:
    """
    Strips environment nouns from a prompt to make it action-only.
    Used as auto-fix when wiring into existing prompts.
    Works at clause-level (comma-separated) for maximum precision.
    Returns cleaned text.
    """
    if not prompt_text:
        return ""
    # Split into sentences first, then clauses within sentences
    sentences = re.split(r'(?<=[.!;])\s+', prompt_text)
    if len(sentences) <= 1:
        # No sentence breaks — treat commas as clause separators
        sentences = [prompt_text]

    clean = []
    for s in sentences:
        if not _ENV_DRIFT_RE.search(s):
            clean.append(s)
        else:
            # Split on commas AND "in the" / "with" / "at the" prepositional phrases
            # Keep clauses that describe CHARACTER ACTION, strip clauses about ENVIRONMENT
            clauses = re.split(r',\s*|\s+(?:in the|at the|with the|inside the|within the|of the)\s+', s)
            kept = [c.strip() for c in clauses if c.strip() and not _ENV_DRIFT_RE.search(c)]
            if kept:
                clean.append(", ".join(kept))
    result = " ".join(clean).strip()
    # Clean up trailing commas, double spaces
    result = re.sub(r',\s*$', '', result)
    result = re.sub(r'\s{2,}', ' ', result)
    return result if result and len(result) > 10 else prompt_text  # Fallback if too much was stripped


def assert_shot_prompt_has_no_env(shot_action_text: str, auto_fix: bool = False) -> str:
    """
    Enforces: once chaining is active, the shot action prompt cannot re-describe environment.
    This is the main reason the ritual room keeps changing.

    If auto_fix=True, strips env words instead of raising.
    Returns cleaned text.
    """
    if not POLICY.forbid_env_in_shot_prompt:
        return shot_action_text or ""

    drift_words = check_env_drift(shot_action_text)
    if drift_words:
        if auto_fix:
            cleaned = strip_env_from_prompt(shot_action_text)
            logger.info(f"[TIGHTENER] Auto-stripped env words from shot prompt: {drift_words}")
            return cleaned
        else:
            raise ValueError(
                "SHOT PROMPT CONTAINS ENVIRONMENT WORDS.\n"
                "This causes set rebuild drift.\n"
                "Fix: remove environment nouns (room/altar/candles/etc.) from the shot action prompt.\n"
                f"Offending words: {drift_words}\n"
                f"Text: {shot_action_text[:200]}"
            )
    return shot_action_text or ""


# -----------------------------------------
# 4) PROMPT COMPILERS
# -----------------------------------------

def compile_anchor_prompt(
    *,
    scene_lock_text: str,
    shot_action_text: str,
    wardrobe_tag: str = "",
    character_name: str = "",
) -> str:
    """
    Produces the Nano Pro Edit text prompt for the ANCHOR FRAME (Shot 1 of scene).
    This is the ONLY time environment is described.
    """
    parts = []

    if POLICY.force_appearance_lock_language:
        parts.append(APPEARANCE_LOCK)

    if scene_lock_text:
        parts.append(SCENE_LOCK_HEADER)
        parts.append(scene_lock_text.strip())

    if wardrobe_tag and character_name:
        parts.append(f"WARDROBE: {character_name} wearing {wardrobe_tag}")

    parts.append(SHOT_ACTION_HEADER)
    parts.append(shot_action_text.strip() if shot_action_text else "(establishing shot)")

    return "\n\n".join(parts).strip()


def compile_chain_prompt(
    *,
    shot_action_text: str,
    wardrobe_tag: str = "",
    character_name: str = "",
    auto_fix_env: bool = True,
) -> str:
    """
    Produces the Nano Pro Edit text prompt for CHAINED SHOTS (Shot 2+).
    Environment is NEVER restated — it comes from the input image.
    """
    # Enforce no env words
    cleaned_action = assert_shot_prompt_has_no_env(shot_action_text, auto_fix=auto_fix_env)

    parts = []

    if POLICY.force_appearance_lock_language:
        parts.append(APPEARANCE_LOCK)

    # Explicit instruction: environment comes from image
    parts.append("ENVIRONMENT: Provided by reference image. Do not modify.")

    if wardrobe_tag and character_name:
        parts.append(f"WARDROBE: {character_name} wearing {wardrobe_tag}")

    parts.append(SHOT_ACTION_HEADER)
    parts.append(cleaned_action if cleaned_action else "(continue from previous)")

    return "\n\n".join(parts).strip()


def compile_reframe_prompt(
    *,
    camera_instruction: str,
    character_name: str = "",
) -> str:
    """
    Produces the Nano Pro Edit prompt used to turn last_frame -> angle variant.
    Camera-only changes. Zero environment modification.
    """
    parts = []

    if POLICY.force_appearance_lock_language:
        parts.append(APPEARANCE_LOCK)

    if POLICY.strict_reframe_only:
        parts.append(REFRAME_ONLY_HEADER)

    if character_name:
        parts.append(f"Keep {character_name} in frame with same pose and expression.")

    parts.append(f"CAMERA CHANGE:\n{camera_instruction.strip()}")

    return "\n\n".join(parts).strip()


# -----------------------------------------
# 5) SCENE LOCK EXTRACTOR
# -----------------------------------------

def extract_scene_lock(
    *,
    scene_manifest_entry: Dict,
    story_bible: Optional[Dict] = None,
    location_description: str = "",
) -> str:
    """
    Builds the one-time scene lock text from scene manifest + story bible.
    This describes the environment ONCE and is never repeated.
    """
    parts = []

    # Location from scene manifest
    loc = scene_manifest_entry.get("location", "")
    if loc:
        parts.append(f"Location: {loc}")

    # Location description (from location_masters or inject_location_descriptions)
    if location_description:
        parts.append(f"Setting: {location_description}")

    # Time of day
    tod = scene_manifest_entry.get("time_of_day", "")
    if tod:
        parts.append(f"Time: {tod}")

    # Color grade anchor (from scene_anchor_system)
    color_grade = scene_manifest_entry.get("color_grade", "")
    if color_grade:
        parts.append(f"Color grade: {color_grade}")

    # Lighting
    lighting = scene_manifest_entry.get("lighting", "")
    if lighting:
        parts.append(f"Lighting: {lighting}")

    # Key props from story bible
    if story_bible:
        scenes = story_bible.get("scenes", [])
        for sb_scene in scenes:
            if sb_scene.get("scene_id") == scene_manifest_entry.get("scene_id"):
                props = sb_scene.get("props", [])
                if props:
                    parts.append(f"Props: {', '.join(props)}")
                atmosphere = sb_scene.get("atmosphere", "")
                if atmosphere:
                    parts.append(f"Atmosphere: {atmosphere}")
                break

    return "\n".join(parts).strip()


# -----------------------------------------
# 6) SHOT ACTION EXTRACTOR
# -----------------------------------------

def extract_shot_action(shot: Dict) -> str:
    """
    Extracts ONLY the action/blocking/emotion content from a shot.
    Strips any environment description that may have been injected by enrichment layers.
    """
    # Primary: beat description (script fidelity)
    beat = shot.get("beat_description", "")

    # Character action markers
    action_markers = []
    nano = shot.get("nano_prompt", "")
    for marker in ["Character action:", "character performs:"]:
        if marker in nano:
            idx = nano.index(marker)
            end = nano.find(".", idx + len(marker))
            if end == -1:
                end = min(idx + 200, len(nano))
            action_markers.append(nano[idx:end].strip())

    # Dialogue
    dialogue = shot.get("dialogue_text", shot.get("dialogue", ""))

    # Emotion
    emotion = shot.get("emotion", "")

    parts = []
    if beat:
        parts.append(beat)
    elif action_markers:
        parts.append(" ".join(action_markers))

    if dialogue:
        chars = shot.get("characters", [])
        speaker = chars[0] if isinstance(chars, list) and chars else "Character"
        parts.append(f'{speaker} speaks: "{dialogue[:150]}"')

    if emotion:
        parts.append(f"Emotion: {emotion}")

    action_text = ". ".join(parts).strip()

    # Auto-strip any env words that leaked in
    return strip_env_from_prompt(action_text)


# -----------------------------------------
# 7) CAMERA INSTRUCTION BUILDER
# -----------------------------------------

CAMERA_ANGLES = {
    "wide_master": "Wide master shot at 24mm focal length. Full environment visible. Characters at medium distance.",
    "medium_tight": "Medium tight shot at 85mm focal length. Character from waist up. Shallow depth of field.",
    "close_detail": "Close-up detail shot at 135mm focal length. Face fills frame. Extreme shallow DOF. Intimate.",
}

def get_camera_instruction(angle_name: str) -> str:
    """Returns the camera instruction for a named angle."""
    return CAMERA_ANGLES.get(angle_name, CAMERA_ANGLES["wide_master"])


# -----------------------------------------
# 8) INTEGRATION HELPERS
# -----------------------------------------

def should_use_tightener(shot: Dict, is_first_in_scene: bool, prev_last_frame: Optional[str]) -> bool:
    """
    Determines if a shot should use the continuity tightener.
    Returns True for chainable shots that have a previous last frame.
    """
    if is_first_in_scene:
        return True  # Always use tightener for anchor frame
    if not prev_last_frame:
        return False  # No chain frame = can't tighten
    # B-roll and inserts don't use tightener (they're independent)
    if shot.get("_broll") or shot.get("_no_chain", False):  # V26 DOCTRINE: suffixes are editorial, not runtime
        return False
    stype = (shot.get("type") or shot.get("shot_type") or "").lower()
    if stype in ("insert", "cutaway", "detail", "b-roll", "b_roll"):
        return False
    return True


def get_tightened_nano_prompt(
    *,
    shot: Dict,
    is_first_in_scene: bool,
    scene_lock_text: str,
    prev_last_frame: Optional[str],
    wardrobe_tag: str = "",
) -> Tuple[str, str]:
    """
    Returns (prompt, mode) where mode is "anchor" | "chain" | "independent".
    This is the main entry point for the chain loop.
    """
    chars = shot.get("characters", [])
    char_name = chars[0] if isinstance(chars, list) and chars else ""
    shot_action = extract_shot_action(shot)

    if is_first_in_scene:
        prompt = compile_anchor_prompt(
            scene_lock_text=scene_lock_text,
            shot_action_text=shot_action,
            wardrobe_tag=wardrobe_tag,
            character_name=char_name,
        )
        return prompt, "anchor"

    if prev_last_frame and should_use_tightener(shot, is_first_in_scene, prev_last_frame):
        prompt = compile_chain_prompt(
            shot_action_text=shot_action,
            wardrobe_tag=wardrobe_tag,
            character_name=char_name,
            auto_fix_env=True,
        )
        return prompt, "chain"

    # Independent shot (B-roll, insert, etc.)
    prompt = compile_anchor_prompt(
        scene_lock_text=scene_lock_text,
        shot_action_text=shot_action,
        wardrobe_tag=wardrobe_tag,
        character_name=char_name,
    )
    return prompt, "independent"


# -----------------------------------------
# 9) SYSTEM OVERVIEW (FOR LOGGING/DISPLAY)
# -----------------------------------------

SYSTEM_OVERVIEW = """
ATLAS CONTINUITY MODE: NANO PRO EDIT ONLY (NO QWEN)

What changed:
- The chain is now image-dominant.
- We generate ONE first frame per shot (anchor or reframe).
- Continuity comes from last_frame -> next first_frame using Nano Pro Edit in reframe-only mode.

Rules enforced:
1) Scene Lock is applied only once at Shot 1 (the anchor frame).
2) Shot prompts after Shot 1 are action-only (movement/emotion).
   If environment words appear, they are auto-stripped.
3) Camera changes are done ONLY by editing the previous last frame
   (reframe-only instruction). Environment cannot change.
4) Variants still exist as post-shot options for review.
   They never drive the chain unless user selects them.

Expected result:
- Room stops shifting between shots.
- Background stays locked to anchor frame.
- Blocking and staging stay consistent.
- Quality improves because we stop re-simulating the set.

Prompt architecture:
  ANCHOR (Shot 1): APPEARANCE_LOCK + SCENE_LOCK + SHOT_ACTION
  CHAIN  (Shot 2+): APPEARANCE_LOCK + "env from image" + SHOT_ACTION (no env words)
  REFRAME (angles): APPEARANCE_LOCK + REFRAME_ONLY + CAMERA_CHANGE
""".strip()
