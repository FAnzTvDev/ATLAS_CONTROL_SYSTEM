#!/usr/bin/env python3
"""
tools/chain_intelligence_gate.py — V36.5 Chain Intelligence Gate
================================================================
Two-phase autonomous quality enforcement for the ATLAS generation pipeline.

PHASE 1 — PRE-GENERATION GATE (before Kling API call):
  Validates the shot plan entry and rejects with specific error codes before
  any money is spent. Zero-cost protection layer.

PHASE 2 — POST-GENERATION GATE (after video returns, before next chain link):
  Analyzes generated video using Gemini Vision for quality failures.
  Does NOT just flag — triggers auto-regen with tightened constraints.
  Max MAX_REGEN_ATTEMPTS (2) auto-regen cycles, then flags for human review.

Key principles:
  - "Fix on first try" not "review and patch"
  - Every failure has a targeted regen_patch (not a generic retry)
  - Vision checks are arc-position-aware (ESTABLISH vs ESCALATE vs RESOLVE)
  - Chain contracts carry position state across shots (no spatial teleportation)

Integration:
    from chain_intelligence_gate import (
        validate_pre_generation,
        validate_post_generation,
        enforce_chain_quality,
        compute_duration_for_shot,
        run_full_validation,
    )

Authority: QA layer — returns verdicts only. Controller acts on them.
           enforce_chain_quality() is the exception: it calls a user-supplied
           regen_fn directly to implement the auto-fix loop.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("atlas.chain_gate")

# ── CONSTANTS ────────────────────────────────────────────────────────────────

MAX_REGEN_ATTEMPTS     = 2
DURATION_TOLERANCE_S   = 0.5      # ±0.5s acceptable for actual vs requested video duration

# Auto duration scaling thresholds
DIALOGUE_MIN_WORDS_10S = 10       # > 10 words → minimum 10s
DIALOGUE_MIN_WORDS_20S = 20       # > 20 words → 2-clip stitch (20s)
ESHOT_DEFAULT_DURATION = 5.0      # B-roll / atmosphere shots
DIALOGUE_WPS           = 2.3      # natural speech pace: words per second
DIALOGUE_BUFFER_S      = 1.5      # buffer appended to word-count minimum

# Exit action keywords — forbidden in non-RESOLVE shots
_EXIT_KEYWORDS = [
    "walks out", "exits", "closes door", "leaves the room",
    "steps out", "walks away", "releases", "transition out",
    "turns to leave", "heads out", "departs", "walks through",
    "steps through", "exits frame", "walks off",
]

# Movement keywords that signal an action mid-flight (for truncation detection)
_MOTION_KEYWORDS = [
    "walking", "running", "crossing", "approaching", "moving toward",
    "stepping", "reaching", "turning", "rising", "falling", "swinging",
]

# Arc position constants (mirrors chain_arc_intelligence.py — no import to stay lightweight)
ARC_ESTABLISH = "ESTABLISH"
ARC_ESCALATE  = "ESCALATE"
ARC_PIVOT     = "PIVOT"
ARC_RESOLVE   = "RESOLVE"


# ── ERROR CODES ──────────────────────────────────────────────────────────────

class GateError:
    # Pre-generation
    CHARACTER_NAME_LEAK     = "CHARACTER_NAME_LEAK"
    DURATION_TOO_SHORT      = "DURATION_TOO_SHORT"
    EXIT_IN_NON_RESOLVE     = "EXIT_IN_NON_RESOLVE"
    LOCATION_MISMATCH       = "LOCATION_MISMATCH"
    ORPHAN_SHOT             = "ORPHAN_SHOT"
    MISSING_NEGATIVE_CHAR   = "MISSING_NEGATIVE_CHAR"
    DUPLICATE_DIALOGUE      = "DUPLICATE_DIALOGUE"
    POSITION_CONTRADICTION  = "POSITION_CONTRADICTION"
    # Post-generation
    DURATION_MISMATCH       = "DURATION_MISMATCH"
    FROZEN_DIALOGUE         = "FROZEN_DIALOGUE"
    ACTION_TRUNCATED        = "ACTION_TRUNCATED"
    CHAIN_CONTRACT_FAIL     = "CHAIN_CONTRACT_FAIL"
    POSITION_MISMATCH       = "POSITION_MISMATCH"
    # Arc-specific
    ESTABLISH_NO_ROOM_DNA   = "ESTABLISH_NO_ROOM_DNA"
    ESTABLISH_NO_CHARACTER  = "ESTABLISH_NO_CHARACTER"
    ESCALATE_NO_PROGRESSION = "ESCALATE_NO_PROGRESSION"
    PIVOT_NO_SHIFT          = "PIVOT_NO_SHIFT"
    RESOLVE_EXIT_DETECTED   = "RESOLVE_EXIT_DETECTED"
    RESOLVE_UNCLEAN_END     = "RESOLVE_UNCLEAN_END"


# ── DATACLASSES ──────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    """Result of a pre- or post-generation gate check."""
    passed: bool
    errors: list[str]          = field(default_factory=list)
    warnings: list[str]        = field(default_factory=list)
    regen_suggestion: str      = ""   # Human-readable fix description
    regen_patch: dict[str, Any] = field(default_factory=dict)  # Machine-readable patch for runner
    auto_fix_applied: bool     = False
    attempts: int              = 0    # How many regen attempts consumed


@dataclass
class ChainContract:
    """
    Spatial + identity contract extracted from the LAST FRAME of a generated video.
    Carried forward as the expected opening state of the NEXT shot in the chain.
    """
    shot_id: str
    last_frame_path: str
    character_positions: dict[str, str]   = field(default_factory=dict)
    # char_name → "frame-left" | "frame-right" | "center" | "offscreen" | "unknown"
    room_dna_visible: bool    = True
    character_present: bool   = True
    emotional_state: str      = "neutral"
    action_state: str         = "static"   # "static"|"walking"|"sitting"|"exiting"|"unknown"
    raw_description: str      = ""
    extraction_method: str    = "heuristic"   # "gemini" | "heuristic" | "unavailable"


# ── UTILITY: VIDEO / FRAME TOOLS ─────────────────────────────────────────────

def _get_video_duration(video_path: str) -> float | None:
    """Return actual video duration in seconds using ffprobe. Returns None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.debug(f"ffprobe failed for {video_path}: {e}")
        return None


def _extract_frame(video_path: str, position: float = 1.0) -> str | None:
    """
    Extract a single frame from a video at position (0.0=start, 0.5=middle, 1.0=end).
    Returns path to a temp JPEG, or None on failure.
    """
    try:
        duration = _get_video_duration(video_path)
        if not duration or duration < 0.1:
            return None

        timestamp = max(0.0, min(duration * position, duration - 0.05))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{timestamp:.2f}",
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                tmp.name,
            ],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and Path(tmp.name).exists():
            return tmp.name
        return None
    except Exception as e:
        logger.debug(f"Frame extraction failed for {video_path} at {position}: {e}")
        return None


def _encode_image_base64(image_path: str) -> str | None:
    """Encode image to base64 string for Gemini API."""
    import base64
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _call_gemini_vision(image_path: str, prompt: str) -> str | None:
    """
    Send an image + prompt to Gemini Vision. Returns response text or None.
    Non-blocking — if Gemini is unavailable, returns None silently.
    """
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Upload inline via base64
        import PIL.Image
        img = PIL.Image.open(image_path)
        response = model.generate_content([prompt, img])
        return response.text if response.text else None

    except ImportError:
        logger.debug("google.generativeai not installed — Gemini vision unavailable")
        return None
    except Exception as e:
        logger.debug(f"Gemini vision call failed: {e}")
        return None


def _cleanup_frames(*paths: str | None) -> None:
    """Remove temp frame files silently."""
    for p in paths:
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


# ── UTILITY: SHOT FIELD ACCESSORS ────────────────────────────────────────────

def _get_text_fields(shot: dict) -> list[str]:
    """Return all user-visible text fields for keyword search."""
    return [
        shot.get("_beat_action") or "",
        shot.get("nano_prompt") or "",
        shot.get("_frame_prompt") or "",
        shot.get("_choreography") or "",
        shot.get("_beat_atmosphere") or "",
        shot.get("_arc_carry_directive") or "",
    ]


def _is_e_shot(shot: dict) -> bool:
    """Return True if this is an E-type (establishing/atmosphere) shot."""
    sid = shot.get("shot_id") or ""
    stype = shot.get("shot_type") or ""
    return bool(re.search(r"_E\d", sid)) or "establishing" in stype.lower() or "atmosphere" in stype.lower()


def _is_m_shot(shot: dict) -> bool:
    """Return True if this is a main (M-type) character shot."""
    sid = shot.get("shot_id") or ""
    return bool(re.search(r"_M\d", sid))


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


# ── AUTO DURATION SCALING ─────────────────────────────────────────────────────

def compute_duration_for_shot(shot: dict) -> float:
    """
    Compute the correct duration for a shot based on dialogue length and shot type.

    Rules:
        - No dialogue + E-shot/B-roll → ESHOT_DEFAULT_DURATION (5s)
        - dialogue_text > DIALOGUE_MIN_WORDS_20S (20) → 20s (2-clip stitch flag set)
        - dialogue_text > DIALOGUE_MIN_WORDS_10S (10) → 10s minimum
        - Any dialogue → max(word_count / DIALOGUE_WPS + DIALOGUE_BUFFER_S, existing_duration)
        - Enforce Kling hard limit: snap to 5 or 10
    """
    dialogue = (shot.get("dialogue_text") or "").strip()
    existing = float(shot.get("duration") or 5.0)

    if not dialogue:
        if _is_e_shot(shot):
            return ESHOT_DEFAULT_DURATION
        return max(existing, ESHOT_DEFAULT_DURATION)

    wc = _word_count(dialogue)
    word_based_min = round(wc / DIALOGUE_WPS + DIALOGUE_BUFFER_S, 1)

    if wc > DIALOGUE_MIN_WORDS_20S:
        return 20.0   # 2-clip stitch required
    elif wc > DIALOGUE_MIN_WORDS_10S:
        return max(word_based_min, 10.0)
    else:
        return max(word_based_min, existing, 5.0)


# ══════════════════════════════════════════════════════════════════════════════
# PRE-GENERATION GATE — 8 validators
# ══════════════════════════════════════════════════════════════════════════════

def _check_character_name_leak(shot: dict, story_bible: dict | None) -> list[str]:
    """
    E-shots must not contain character names in any text field.
    Character references cause FAL to generate phantom people in establishing shots.
    """
    if not _is_e_shot(shot):
        return []

    # Build character name list from story bible
    char_names: list[str] = []
    if story_bible:
        for char in story_bible.get("characters", []):
            name = char.get("name") or char.get("character_name") or ""
            if name:
                char_names.append(name.upper())
                # Also add first name only
                parts = name.split()
                if parts:
                    char_names.append(parts[0].upper())

    # Also use cast from shot.characters list
    for c in shot.get("characters") or []:
        char_names.append(c.upper())
        parts = c.split()
        if parts:
            char_names.append(parts[0].upper())

    char_names = list(set(char_names))

    errors = []
    combined = " ".join(_get_text_fields(shot)).upper()
    for name in char_names:
        if name and len(name) > 2 and name in combined:
            errors.append(
                f"{GateError.CHARACTER_NAME_LEAK}: E-shot '{shot.get('shot_id')}' "
                f"contains character name '{name}' — will generate phantom figure. "
                f"Remove name from nano_prompt, _beat_action, _frame_prompt."
            )
            break  # one error per shot is enough

    return errors


def _check_duration_vs_dialogue(shot: dict) -> list[str]:
    """
    Dialogue text requires minimum duration for the character to finish speaking.
    Reject if current duration is below the word-count-derived minimum.
    """
    dialogue = (shot.get("dialogue_text") or "").strip()
    if not dialogue:
        return []

    current_dur = float(shot.get("duration") or 5.0)
    wc = _word_count(dialogue)
    minimum = round(wc / DIALOGUE_WPS + DIALOGUE_BUFFER_S, 1)

    if current_dur < minimum - 0.1:   # small tolerance
        return [
            f"{GateError.DURATION_TOO_SHORT}: shot '{shot.get('shot_id')}' "
            f"duration={current_dur}s for {wc} words, need {minimum}s. "
            f"Auto-scale to {compute_duration_for_shot(shot)}s."
        ]
    return []


def _check_exit_in_non_resolve(shot: dict) -> list[str]:
    """
    Exit actions break the spatial chain for all subsequent shots.
    Only RESOLVE shots may contain exits.
    """
    arc = (shot.get("_arc_position") or "").upper()
    if arc == ARC_RESOLVE or not arc:
        return []

    combined = " ".join(_get_text_fields(shot)).lower()
    for kw in _EXIT_KEYWORDS:
        if kw in combined:
            return [
                f"{GateError.EXIT_IN_NON_RESOLVE}: shot '{shot.get('shot_id')}' "
                f"arc={arc} contains exit action '{kw}'. "
                f"Exit actions are only permitted in RESOLVE shots. "
                f"Remove or defer to final shot of scene."
            ]
    return []


def _check_location_mismatch(shot: dict, scene_shots: list[dict], story_bible: dict | None) -> list[str]:
    """
    All shots in a scene must use the same room.
    Check that room_dna / location fields don't name a different location than the scene's designated room.
    """
    sid = shot.get("shot_id") or ""
    scene_prefix = sid[:3]

    # Determine this scene's canonical location from story bible
    canonical_location = ""
    if story_bible:
        for sc in story_bible.get("scenes", []):
            sc_id = str(sc.get("scene_id") or sc.get("scene_number") or "").zfill(3)
            if sc_id == scene_prefix:
                canonical_location = (sc.get("location") or "").lower()
                break

    # If we can't determine canonical location, skip this check
    if not canonical_location:
        return []

    # Extract location words from canonical (e.g. "grand foyer" → {"grand", "foyer"})
    canon_words = set(canonical_location.lower().split())

    # Check room_dna or _scene_room field against canonical
    room_dna = (shot.get("room_dna") or shot.get("_scene_room") or "").lower()
    if not room_dna:
        return []   # No room DNA to check against

    room_words = set(room_dna.lower().split())

    # Rooms that are clearly different (crude but effective for common cases)
    _ROOM_TYPES = ["foyer", "library", "kitchen", "bedroom", "staircase",
                   "garden", "drawing", "hallway", "study", "office", "ballroom"]

    canon_room_type  = next((r for r in _ROOM_TYPES if r in canonical_location), None)
    shot_room_type   = next((r for r in _ROOM_TYPES if r in room_dna), None)

    if canon_room_type and shot_room_type and canon_room_type != shot_room_type:
        return [
            f"{GateError.LOCATION_MISMATCH}: shot '{sid}' room_dna='{room_dna}' "
            f"does not match scene location='{canonical_location}'. "
            f"Scene {scene_prefix} is locked to '{canon_room_type}'. "
            f"Update room_dna to match canonical scene location."
        ]
    return []


def _check_orphan_shot(shot: dict) -> list[str]:
    """M-type shots must belong to a chain_group — solo M-shots break end-frame chaining."""
    if not _is_m_shot(shot):
        return []

    chain_group = shot.get("chain_group") or shot.get("_chain_group")
    if not chain_group:
        return [
            f"{GateError.ORPHAN_SHOT}: M-shot '{shot.get('shot_id')}' "
            f"has no chain_group assignment. "
            f"M-shots require chain_group for end-frame chaining. "
            f"Add chain_group or use atlas_universal_runner's auto-grouping."
        ]
    return []


def _check_missing_negative_constraints(shot: dict) -> list[str]:
    """
    E-shots of type BROLL or ATMOSPHERE must have 'No people visible' unless flagged character-present.
    Without this, FAL generates random figures in empty-room shots.
    """
    if not _is_e_shot(shot):
        return []

    # If explicitly flagged as character-present, skip
    if shot.get("_character_present") or (shot.get("characters") or []):
        return []

    stype = (shot.get("shot_type") or "").lower()
    if "establishing" not in stype and "atmosphere" not in stype and "broll" not in stype and "b_roll" not in stype:
        # Only enforce for clearly empty-room shot types
        if shot.get("characters"):
            return []  # Has characters — skip

    combined = " ".join(_get_text_fields(shot)).lower()
    if "no people" not in combined and "no figures" not in combined and "empty" not in combined:
        return [
            f"{GateError.MISSING_NEGATIVE_CHAR}: E-shot '{shot.get('shot_id')}' "
            f"(type={stype}) has no 'No people visible' constraint. "
            f"Add 'No people visible, no figures, empty space only' to nano_prompt."
        ]
    return []


def _check_duplicate_dialogue(shot: dict, scene_shots: list[dict]) -> list[str]:
    """
    Duplicate dialogue text across shots in the same scene produces identical video clips.
    This usually indicates a copy-paste error in the shot plan.
    """
    dialogue = (shot.get("dialogue_text") or "").strip()
    if not dialogue or len(dialogue) < 10:
        return []

    sid = shot.get("shot_id")
    for other in scene_shots:
        if other.get("shot_id") == sid:
            continue
        other_dialogue = (other.get("dialogue_text") or "").strip()
        if other_dialogue and other_dialogue.lower() == dialogue.lower():
            return [
                f"{GateError.DUPLICATE_DIALOGUE}: shot '{sid}' has identical dialogue_text "
                f"to shot '{other.get('shot_id')}'. Duplicate dialogue will produce identical clips. "
                f"Verify this is intentional (e.g. repeated line) or fix the shot plan."
            ]
    return []


def _check_position_continuity(shot: dict, scene_shots: list[dict]) -> list[str]:
    """
    Verify that the opening action of a shot doesn't contradict the closing action
    of the previous shot in the chain — prevents spatial teleportation.

    Uses heuristic keyword detection: if previous shot ends with character climbing stairs
    and this shot opens with character at the bottom, that's a contradiction.
    """
    sid = shot.get("shot_id") or ""
    chain_group = shot.get("chain_group") or shot.get("_chain_group")
    if not chain_group:
        return []   # Can't check without chain membership

    # Find previous shot in same chain_group
    same_group = [s for s in scene_shots if
                  (s.get("chain_group") or s.get("_chain_group")) == chain_group
                  and (s.get("shot_id") or "") != sid]
    if not same_group:
        return []

    # Sort by arc_index to find the shot that comes just before this one
    def arc_idx(s: dict) -> int:
        return s.get("_arc_index", 999)

    this_idx = shot.get("_arc_index", 0)
    prev_shots = [s for s in same_group if arc_idx(s) < this_idx]
    if not prev_shots:
        return []

    prev_shot = max(prev_shots, key=arc_idx)
    prev_end_state = prev_shot.get("_blocking_end_state") or ""
    if not prev_end_state:
        return []

    # Heuristic: "leaving or near exit" in prev → opening should not be "enters" / "arrives"
    this_action = (shot.get("_beat_action") or "").lower()

    if "leaving" in prev_end_state or "exits" in prev_end_state:
        if "enters" in this_action or "arrives" in this_action or "walks in" in this_action:
            return [
                f"{GateError.POSITION_CONTRADICTION}: shot '{sid}' opens with entry/arrival "
                f"but previous shot '{prev_shot.get('shot_id')}' ended with character exiting. "
                f"Spatial contradiction — character cannot arrive in a room they just left. "
                f"Review chain ordering or adjust beat actions."
            ]

    return []


def validate_pre_generation(
    shot: dict,
    scene_shots: list[dict] | None = None,
    story_bible: dict | None = None,
) -> GateResult:
    """
    Run all pre-generation checks on a single shot.

    Args:
        shot:        The shot dict from shot_plan.json
        scene_shots: All shots in the same scene (for cross-shot checks)
        story_bible: Parsed story_bible.json (for location + character data)

    Returns:
        GateResult with passed=True if no blocking errors found.
        Warnings are non-blocking. Errors block generation.
    """
    scene_shots = scene_shots or []
    all_errors: list[str]   = []
    all_warnings: list[str] = []

    # Run all 8 validators
    all_errors.extend(_check_character_name_leak(shot, story_bible))
    all_errors.extend(_check_duration_vs_dialogue(shot))
    all_errors.extend(_check_exit_in_non_resolve(shot))
    all_errors.extend(_check_location_mismatch(shot, scene_shots, story_bible))
    all_errors.extend(_check_orphan_shot(shot))
    all_errors.extend(_check_missing_negative_constraints(shot))
    all_errors.extend(_check_duplicate_dialogue(shot, scene_shots))
    all_errors.extend(_check_position_continuity(shot, scene_shots))

    # Warnings: duration auto-scaling suggestions
    ideal_duration = compute_duration_for_shot(shot)
    current_dur = float(shot.get("duration") or 5.0)
    if ideal_duration != current_dur and not any(GateError.DURATION_TOO_SHORT in e for e in all_errors):
        if ideal_duration > current_dur + 1.0:
            all_warnings.append(
                f"Duration scaling: shot '{shot.get('shot_id')}' "
                f"current={current_dur}s → recommended={ideal_duration}s "
                f"({'2-clip stitch' if ideal_duration >= 20 else 'dialogue padding'})"
            )

    passed = len(all_errors) == 0
    return GateResult(
        passed=passed,
        errors=all_errors,
        warnings=all_warnings,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST-GENERATION GATE — vision-powered analysis with auto-fix
# ══════════════════════════════════════════════════════════════════════════════

def _check_frozen_dialogue(video_path: str, shot: dict) -> tuple[bool, str, dict]:
    """
    Detect frozen/statue dialogue: character lips not moving during a dialogue beat.

    Uses Gemini to compare mouth state across 3 frames (start, middle, end).
    Returns (frozen_detected, description, regen_patch).
    """
    dialogue = (shot.get("dialogue_text") or "").strip()
    if not dialogue:
        return False, "", {}

    chars = shot.get("characters") or []
    char_desc = f"{chars[0]} speaking" if chars else "a character speaking"

    frame_start  = _extract_frame(video_path, 0.1)
    frame_middle = _extract_frame(video_path, 0.5)
    frame_end    = _extract_frame(video_path, 0.9)

    try:
        if not any([frame_start, frame_middle, frame_end]):
            return False, "no frames extracted", {}

        # Use the clearest frame available for analysis
        analysis_frame = frame_middle or frame_start or frame_end

        prompt = (
            f"Look at this video frame. The scene shows {char_desc} delivering dialogue: "
            f'"{dialogue[:80]}". '
            "Answer ONLY with a JSON object: "
            '{"mouth_open": true/false, "speaking_visible": true/false, '
            '"body_animated": true/false, "frozen_statue": true/false, '
            '"confidence": "high"/"medium"/"low"}. '
            "frozen_statue=true if the character looks like a still photograph with no movement cues."
        )

        response = _call_gemini_vision(analysis_frame, prompt)
        if not response:
            return False, "gemini unavailable", {}

        # Parse JSON from Gemini response
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if not json_match:
            return False, f"gemini response unparseable: {response[:100]}", {}

        data = json.loads(json_match.group(0))
        frozen = data.get("frozen_statue", False) or (
            not data.get("mouth_open", True) and not data.get("body_animated", True)
        )

        if frozen:
            patch = {
                "_regen_frozen_fix": True,
                "nano_prompt_suffix": (
                    " CHARACTER ACTIVELY SPEAKING: mouth open and moving with dialogue, "
                    "jaw animated, natural facial muscle movement, head micro-movements, "
                    "NOT a still photograph. Body breathing and gesturing."
                ),
                "_negative_prompt_addition": "frozen, static, still image, statue, no movement",
            }
            return True, f"Frozen dialogue detected (confidence={data.get('confidence','?')})", patch

        return False, "dialogue animation verified", {}

    finally:
        _cleanup_frames(frame_start, frame_middle, frame_end)


def _check_action_truncation(video_path: str, shot: dict) -> tuple[bool, str, dict]:
    """
    Detect clips that end mid-action — character in motion at final frame when
    they should be stationary for a clean chain handoff.

    Checks if the beat_action implies movement that should complete within the clip.
    """
    beat_action = (shot.get("_beat_action") or "").lower()
    has_motion_beat = any(kw in beat_action for kw in _MOTION_KEYWORDS)

    arc = (shot.get("_arc_position") or "").upper()
    # Only strictly enforce for non-RESOLVE shots feeding into next chain link
    if arc == ARC_RESOLVE:
        return False, "RESOLVE shots may end in motion", {}

    last_frame = _extract_frame(video_path, 0.95)
    if not last_frame:
        return False, "no final frame extracted", {}

    try:
        chars = shot.get("characters") or []
        char_desc = chars[0] if chars else "the character"

        prompt = (
            f"Look at this final frame of a video clip. "
            f"The character ({char_desc}) should be settling into a static pose for a clean cut. "
            "Answer ONLY with JSON: "
            '{"mid_motion": true/false, "motion_type": "walking/reaching/turning/static/unknown", '
            '"clean_handoff": true/false, "confidence": "high"/"medium"/"low"}. '
            "mid_motion=true if the character is clearly in the middle of a physical movement "
            "that has not completed (body leaning forward while walking, arm mid-swing, etc)."
        )

        response = _call_gemini_vision(last_frame, prompt)
        if not response:
            # Fall back to heuristic if no Gemini
            if has_motion_beat:
                current_dur = float(shot.get("duration") or 5.0)
                if current_dur <= 5.0:
                    return True, "heuristic: motion beat + short duration likely truncated", {
                        "_regen_truncation_fix": True,
                        "duration_extension_s": 3.0,
                    }
            return False, "gemini unavailable, heuristic clean", {}

        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if not json_match:
            return False, "gemini response unparseable", {}

        data = json.loads(json_match.group(0))
        truncated = data.get("mid_motion", False) and not data.get("clean_handoff", True)

        if truncated:
            current_dur = float(shot.get("duration") or 5.0)
            extension = 3.0 if current_dur < 10.0 else 5.0
            patch = {
                "_regen_truncation_fix": True,
                "duration_extension_s": extension,
                "nano_prompt_suffix": (
                    f" Action completes fully within clip. Character settles into "
                    f"static pose by final frame. Clean chain handoff position."
                ),
            }
            motion_type = data.get("motion_type", "unknown")
            return True, f"Action truncated mid-motion (type={motion_type}, confidence={data.get('confidence','?')})", patch

        return False, "clean action ending verified", {}

    finally:
        _cleanup_frames(last_frame)


def extract_chain_contract(video_path: str, shot: dict) -> ChainContract:
    """
    Extract the ChainContract from the last frame of a generated video.
    This becomes the expected opening state for the next shot.

    Uses Gemini Vision when available; falls back to heuristic from shot metadata.
    """
    sid = shot.get("shot_id", "unknown")
    last_frame = _extract_frame(video_path, 0.95)

    if not last_frame:
        # Heuristic fallback from shot metadata
        chars = shot.get("characters") or []
        return ChainContract(
            shot_id=sid,
            last_frame_path="",
            character_positions={c: "unknown" for c in chars},
            room_dna_visible=True,
            character_present=bool(chars),
            emotional_state=shot.get("_beat_atmosphere", "neutral"),
            action_state="unknown",
            raw_description="heuristic — no frame extracted",
            extraction_method="heuristic",
        )

    try:
        chars = shot.get("characters") or []
        char_list = ", ".join(chars) if chars else "any characters"

        prompt = (
            f"Analyze this final frame of a video clip. Characters: {char_list}. "
            "Extract the spatial state for chain handoff. Answer ONLY with JSON: "
            '{"character_positions": {"<name>": "frame-left|frame-right|center|offscreen"}, '
            '"room_dna_visible": true/false, '
            '"character_present": true/false, '
            '"emotional_state": "neutral|tense|resolved|shocked|fearful|hopeful|angry|sad", '
            '"action_state": "static|walking|sitting|exiting|approaching|unknown", '
            '"room_description": "<5 word description of room architecture visible>"}. '
            "If no characters visible, character_present=false. "
            "room_dna_visible=true if you can identify the room type from architecture."
        )

        response = _call_gemini_vision(last_frame, prompt)

        if response:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return ChainContract(
                    shot_id=sid,
                    last_frame_path=last_frame,
                    character_positions=data.get("character_positions", {}),
                    room_dna_visible=data.get("room_dna_visible", True),
                    character_present=data.get("character_present", bool(chars)),
                    emotional_state=data.get("emotional_state", "neutral"),
                    action_state=data.get("action_state", "static"),
                    raw_description=data.get("room_description", ""),
                    extraction_method="gemini",
                )

        # Gemini unavailable — heuristic
        arc = (shot.get("_arc_position") or "").upper()
        action = (shot.get("_beat_action") or "").lower()
        action_state = "static"
        if any(kw in action for kw in _MOTION_KEYWORDS):
            action_state = "walking"
        if any(kw in action for kw in _EXIT_KEYWORDS):
            action_state = "exiting"

        return ChainContract(
            shot_id=sid,
            last_frame_path=last_frame,
            character_positions={c: "unknown" for c in chars},
            room_dna_visible=True,
            character_present=bool(chars),
            emotional_state=shot.get("_beat_atmosphere", "neutral"),
            action_state=action_state,
            raw_description="heuristic from metadata",
            extraction_method="heuristic",
        )

    except Exception as e:
        logger.debug(f"Chain contract extraction failed for {sid}: {e}")
        chars = shot.get("characters") or []
        return ChainContract(
            shot_id=sid,
            last_frame_path=last_frame or "",
            extraction_method="unavailable",
        )


def _check_chain_contract_match(
    shot: dict,
    prev_contract: ChainContract | None,
) -> tuple[bool, str]:
    """
    Validate that this shot's opening matches the previous shot's closing contract.
    Returns (match_ok, error_description).
    """
    if not prev_contract:
        return True, ""

    # If previous shot ended with character exiting, current should NOT have characters arriving
    if prev_contract.action_state == "exiting":
        this_action = (shot.get("_beat_action") or "").lower()
        if "enters" in this_action or "arrives" in this_action:
            return False, (
                f"Chain contract mismatch: previous shot '{prev_contract.shot_id}' "
                f"ended with character exiting, but '{shot.get('shot_id')}' "
                f"opens with character arriving. Spatial contradiction."
            )

    # If previous shot had room DNA, current should too (room continuity)
    if prev_contract.room_dna_visible and not prev_contract.action_state == "exiting":
        # Just a warning, not a hard fail
        pass

    return True, ""


def _check_arc_specific_vision(
    video_path: str,
    shot: dict,
    prev_contract: ChainContract | None = None,
) -> tuple[bool, list[str], dict]:
    """
    Arc-position-specific vision checks using Gemini.
    Returns (passed, errors, regen_patch).

    ESTABLISH: room DNA visible, character identity present, lighting baseline set
    ESCALATE:  emotional progression from previous (different expression)
    PIVOT:     dramatic shift visible
    RESOLVE:   clean landing, no exit actions, emotional resolution
    """
    arc = (shot.get("_arc_position") or "").upper()
    if not arc:
        return True, [], {}

    errors: list[str] = []
    patch: dict       = {}

    mid_frame = _extract_frame(video_path, 0.5)
    if not mid_frame:
        return True, [], {}   # Can't check without a frame

    try:
        sid = shot.get("shot_id", "?")

        if arc == ARC_ESTABLISH:
            # ESTABLISH: room DNA and character identity must be locked from frame 1
            prompt = (
                "This is an ESTABLISHING shot that sets the scene's visual baseline. "
                "Answer ONLY with JSON: "
                '{"room_architecture_clear": true/false, '
                '"character_visible": true/false, '
                '"lighting_defined": true/false, '
                '"room_type": "<single word: foyer/library/kitchen/bedroom/other>", '
                '"identity_readable": true/false}. '
                "room_architecture_clear=true if you can identify specific architectural features "
                "(not just 'a room'). identity_readable=true if character appearance is distinctive."
            )
            response = _call_gemini_vision(mid_frame, prompt)
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    if not data.get("room_architecture_clear", True):
                        errors.append(
                            f"{GateError.ESTABLISH_NO_ROOM_DNA}: ESTABLISH shot '{sid}' "
                            f"room architecture not clearly visible. "
                            f"Room DNA not locked — all subsequent chain shots will drift."
                        )
                        patch["_regen_establish_fix"] = True
                        patch["nano_prompt_suffix"] = (
                            " ESTABLISH SHOT REQUIREMENTS: distinctive room architecture clearly "
                            "visible in frame, all key fixtures present, lighting character established, "
                            "room type immediately identifiable. This sets the chain's visual law."
                        )
                    chars = shot.get("characters") or []
                    if chars and not data.get("character_visible", True):
                        errors.append(
                            f"{GateError.ESTABLISH_NO_CHARACTER}: ESTABLISH shot '{sid}' "
                            f"expects characters {chars} but none visible in frame."
                        )

        elif arc == ARC_ESCALATE:
            # ESCALATE: should look emotionally different from previous shot
            if prev_contract and prev_contract.emotional_state:
                prompt = (
                    f"This video shows an ESCALATION beat. "
                    f"The previous shot ended with emotional state: '{prev_contract.emotional_state}'. "
                    "Has the emotional intensity or expression changed? "
                    "Answer ONLY with JSON: "
                    '{"emotional_progression": true/false, '
                    '"current_emotion": "<word>", '
                    '"tension_level": "low/medium/high/peak"}. '
                    "emotional_progression=true if expression/body language is different from neutral/previous."
                )
                response = _call_gemini_vision(mid_frame, prompt)
                if response:
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                        if not data.get("emotional_progression", True) and data.get("tension_level") == "low":
                            errors.append(
                                f"{GateError.ESCALATE_NO_PROGRESSION}: ESCALATE shot '{sid}' "
                                f"shows no emotional progression from previous shot "
                                f"(previous={prev_contract.emotional_state}, current={data.get('current_emotion','?')}). "
                                f"Escalation beat must show rising emotional intensity."
                            )
                            patch["_regen_escalate_fix"] = True
                            patch["nano_prompt_suffix"] = (
                                " ESCALATION REQUIRED: visible emotional intensification from previous beat. "
                                "Body language more tense, expression more engaged, stakes visibly higher."
                            )

        elif arc == ARC_PIVOT:
            # PIVOT: dramatic shift should be visible
            prompt = (
                "This is a PIVOT shot — the emotional turning point of the scene. "
                "Answer ONLY with JSON: "
                '{"dramatic_shift_visible": true/false, '
                '"shift_type": "expression/body_language/both/none", '
                '"intensity": "subtle/moderate/strong"}. '
                "dramatic_shift_visible=true if there is a clear change in character "
                "expression or body posture suggesting something significant has changed."
            )
            response = _call_gemini_vision(mid_frame, prompt)
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    if not data.get("dramatic_shift_visible", True) and data.get("intensity") == "subtle":
                        errors.append(
                            f"{GateError.PIVOT_NO_SHIFT}: PIVOT shot '{sid}' "
                            f"shows no clear dramatic shift (intensity=subtle). "
                            f"Pivot beat requires visible emotional/physical turning point."
                        )
                        patch["_regen_pivot_fix"] = True
                        patch["nano_prompt_suffix"] = (
                            " PIVOT MOMENT: clear visible shift in character expression/posture. "
                            "This is the scene's turning point — reaction must be readable and distinct."
                        )

        elif arc == ARC_RESOLVE:
            # RESOLVE: clean landing, no exits, emotional resolution visible
            last_frame = _extract_frame(video_path, 0.92)
            check_frame = last_frame or mid_frame

            prompt = (
                "This is a RESOLVE shot — the final beat of a scene. "
                "Answer ONLY with JSON: "
                '{"clean_ending": true/false, '
                '"character_exiting": true/false, '
                '"emotional_resolution": true/false, '
                '"stable_final_frame": true/false}. '
                "clean_ending=true if the character is settled in a stable position. "
                "character_exiting=true if the character is mid-exit or leaving frame. "
                "emotional_resolution=true if body language suggests completion/closure."
            )
            response = _call_gemini_vision(check_frame, prompt)
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    if data.get("character_exiting", False):
                        errors.append(
                            f"{GateError.RESOLVE_EXIT_DETECTED}: RESOLVE shot '{sid}' "
                            f"ends with character mid-exit. RESOLVE shots must have clean, "
                            f"stable final frames for proper scene close."
                        )
                        patch["_regen_resolve_fix"] = True
                        patch["nano_prompt_suffix"] = (
                            " RESOLVE REQUIREMENTS: character settles into final position, "
                            "does NOT exit frame. Scene closes with character present and still. "
                            "Clean final frame for scene boundary."
                        )
                    elif not data.get("stable_final_frame", True):
                        errors.append(
                            f"{GateError.RESOLVE_UNCLEAN_END}: RESOLVE shot '{sid}' "
                            f"final frame is unstable (mid-motion). "
                            f"Final shot must end with character at rest."
                        )

            if last_frame and last_frame != mid_frame:
                _cleanup_frames(last_frame)

        return len(errors) == 0, errors, patch

    finally:
        _cleanup_frames(mid_frame)


def _check_position_chain_handoff(
    shot: dict,
    prev_contract: ChainContract | None,
) -> tuple[bool, list[str]]:
    """
    Validate that character positions in the opening of this shot
    match the closing positions from the previous shot's contract.
    """
    if not prev_contract or not prev_contract.character_positions:
        return True, []

    errors = []

    # Only check when Gemini extracted real positions (not heuristic)
    if prev_contract.extraction_method == "heuristic":
        return True, []

    # Check characters that appear in both shots
    this_chars = set(shot.get("characters") or [])
    prev_chars = set(prev_contract.character_positions.keys())
    shared = this_chars & prev_chars

    for char in shared:
        prev_pos = prev_contract.character_positions.get(char, "unknown")
        if prev_pos == "unknown":
            continue

        # The shot's own screen position (if set by OTSEnforcer or screen_position_lock)
        this_pos = shot.get("_screen_positions", {}).get(char, "unknown")
        if this_pos == "unknown":
            continue

        if prev_pos != this_pos:
            errors.append(
                f"{GateError.POSITION_MISMATCH}: character '{char}' was at {prev_pos} "
                f"in shot '{prev_contract.shot_id}' but expected at {this_pos} in "
                f"'{shot.get('shot_id')}'. Screen position teleportation breaks 180° rule."
            )

    return len(errors) == 0, errors


def validate_post_generation(
    shot: dict,
    video_path: str,
    chain_contract: ChainContract | None = None,
    prev_contract: ChainContract | None = None,
) -> GateResult:
    """
    Run all post-generation quality checks on a generated video.

    Args:
        shot:           Shot dict from shot_plan.json
        video_path:     Path to the generated .mp4 file
        chain_contract: Previously extracted contract from this shot's last frame (if available)
        prev_contract:  Chain contract from the PREVIOUS shot (for position continuity)

    Returns:
        GateResult with passed=True if all checks pass.
        On failure, regen_patch contains targeted constraints for auto-regen.
    """
    if not Path(video_path).exists():
        return GateResult(
            passed=False,
            errors=[f"Video file not found: {video_path}"],
        )

    all_errors: list[str]   = []
    all_warnings: list[str] = []
    merged_patch: dict      = {}

    # ── 1. Duration verification ─────────────────────────────────────
    actual_dur = _get_video_duration(video_path)
    requested_dur = float(shot.get("duration") or 5.0)

    if actual_dur is not None:
        if abs(actual_dur - requested_dur) > DURATION_TOLERANCE_S:
            msg = (
                f"{GateError.DURATION_MISMATCH}: shot '{shot.get('shot_id')}' "
                f"requested={requested_dur}s actual={actual_dur:.1f}s "
                f"(tolerance=±{DURATION_TOLERANCE_S}s)"
            )
            if actual_dur < requested_dur - DURATION_TOLERANCE_S:
                all_errors.append(msg)
                merged_patch["duration_extension_s"] = requested_dur - actual_dur + 1.0
            else:
                all_warnings.append(msg + " — video longer than requested (acceptable)")

    # ── 2. Frozen dialogue detection ─────────────────────────────────
    frozen, frozen_desc, frozen_patch = _check_frozen_dialogue(video_path, shot)
    if frozen:
        all_errors.append(
            f"{GateError.FROZEN_DIALOGUE}: shot '{shot.get('shot_id')}' — {frozen_desc}. "
            f"Auto-regen with lip movement constraints."
        )
        merged_patch.update(frozen_patch)

    # ── 3. Action truncation ─────────────────────────────────────────
    truncated, trunc_desc, trunc_patch = _check_action_truncation(video_path, shot)
    if truncated:
        all_errors.append(
            f"{GateError.ACTION_TRUNCATED}: shot '{shot.get('shot_id')}' — {trunc_desc}. "
            f"Extend duration and regen."
        )
        merged_patch.update(trunc_patch)

    # ── 4. Arc-specific vision checks ────────────────────────────────
    arc_ok, arc_errors, arc_patch = _check_arc_specific_vision(video_path, shot, prev_contract)
    all_errors.extend(arc_errors)
    merged_patch.update(arc_patch)

    # ── 5. Chain contract position handoff ───────────────────────────
    pos_ok, pos_errors = _check_position_chain_handoff(shot, prev_contract)
    all_errors.extend(pos_errors)

    # ── 6. Chain contract match (previous → this) ────────────────────
    contract_ok, contract_err = _check_chain_contract_match(shot, prev_contract)
    if not contract_ok:
        all_errors.append(f"{GateError.CHAIN_CONTRACT_FAIL}: {contract_err}")

    # Build regen suggestion from patch
    regen_suggestion = ""
    if merged_patch:
        parts = []
        if merged_patch.get("_regen_frozen_fix"):
            parts.append("Inject lip-movement directives")
        if merged_patch.get("_regen_truncation_fix"):
            parts.append(f"Extend duration by {merged_patch.get('duration_extension_s', 3)}s")
        if merged_patch.get("_regen_establish_fix"):
            parts.append("Strengthen room DNA anchor in ESTABLISH shot")
        if merged_patch.get("_regen_escalate_fix"):
            parts.append("Add emotional escalation directive")
        if merged_patch.get("_regen_pivot_fix"):
            parts.append("Amplify dramatic shift in PIVOT beat")
        if merged_patch.get("_regen_resolve_fix"):
            parts.append("Lock RESOLVE ending — prevent character exit")
        regen_suggestion = " | ".join(parts)

    passed = len(all_errors) == 0
    return GateResult(
        passed=passed,
        errors=all_errors,
        warnings=all_warnings,
        regen_suggestion=regen_suggestion,
        regen_patch=merged_patch,
    )


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-FIX LOOP — enforce_chain_quality()
# ══════════════════════════════════════════════════════════════════════════════

def enforce_chain_quality(
    shot: dict,
    video_path: str,
    regen_fn: Callable[[dict, dict], tuple[str, bool]],
    prev_contract: ChainContract | None = None,
    max_attempts: int = MAX_REGEN_ATTEMPTS,
) -> tuple[str, ChainContract | None, GateResult]:
    """
    Full autonomous enforcement loop.

    1. Run post-generation gate on the provided video
    2. If failed: apply regen_patch, call regen_fn(shot, patch) to get new video
    3. Re-check the new video
    4. Repeat up to max_attempts times
    5. If still failing after max_attempts: flag for human review, return last video

    Args:
        shot:         Shot dict from shot_plan.json
        video_path:   Path to initially generated video
        regen_fn:     Callable(shot, patch) → (new_video_path: str, success: bool)
                      Caller supplies this — usually wraps the Kling API call.
        prev_contract: Chain contract from the previous shot (for position checks)
        max_attempts: Max regen cycles (default MAX_REGEN_ATTEMPTS=2)

    Returns:
        (final_video_path, chain_contract_from_final_video, final_gate_result)
        chain_contract is None if extraction failed.
        final_gate_result.auto_fix_applied=True if any regen was needed.
        final_gate_result.attempts = number of regen cycles used.
    """
    sid = shot.get("shot_id", "?")
    current_path = video_path
    attempts_used = 0
    auto_fix_applied = False

    for attempt in range(max_attempts + 1):  # attempt 0 = initial check, 1..max = regen attempts
        is_initial = (attempt == 0)
        gate = validate_post_generation(
            shot=shot,
            video_path=current_path,
            prev_contract=prev_contract,
        )

        if gate.passed:
            logger.info(f"[CHAIN_GATE] {sid} PASSED after {attempts_used} regen(s)")
            break

        if attempt >= max_attempts:
            # Out of attempts — flag for human review
            gate.errors.append(
                f"[HUMAN_REVIEW_REQUIRED]: {sid} failed post-gen gate after "
                f"{max_attempts} regen attempts. Manual inspection needed. "
                f"Remaining issues: {'; '.join(gate.errors[:2])}"
            )
            logger.warning(
                f"[CHAIN_GATE] {sid} flagged for HUMAN REVIEW after "
                f"{max_attempts} auto-regen attempts. Issues: {gate.errors}"
            )
            break

        # ── Apply patch and regen ────────────────────────────────────
        patch = gate.regen_patch.copy()

        # Apply duration extension if needed
        if "duration_extension_s" in patch:
            current_dur = float(shot.get("duration") or 5.0)
            new_dur = current_dur + patch["duration_extension_s"]
            # Snap to Kling's valid durations (5 or 10)
            shot["duration"] = 10.0 if new_dur > 7.0 else 5.0
            logger.info(f"[CHAIN_GATE] {sid} extending duration: {current_dur}s → {shot['duration']}s")

        # Apply prompt suffix if provided
        if "nano_prompt_suffix" in patch:
            existing = shot.get("nano_prompt") or ""
            suffix = patch["nano_prompt_suffix"]
            if suffix not in existing:
                shot["nano_prompt"] = existing + suffix
            logger.info(f"[CHAIN_GATE] {sid} prompt tightened: ...{suffix[:60]}")

        # Apply negative prompt additions
        if "_negative_prompt_addition" in patch:
            existing_neg = shot.get("_negative_prompt") or ""
            addition = patch["_negative_prompt_addition"]
            if addition not in existing_neg:
                shot["_negative_prompt"] = (existing_neg + ", " + addition).strip(", ")

        logger.info(
            f"[CHAIN_GATE] {sid} attempt {attempt + 1}/{max_attempts}: "
            f"regen_fn called with patch={list(patch.keys())}"
        )

        try:
            new_path, success = regen_fn(shot, patch)
            if success and Path(new_path).exists():
                current_path = new_path
                attempts_used += 1
                auto_fix_applied = True
            else:
                logger.warning(f"[CHAIN_GATE] {sid} regen_fn returned failure at attempt {attempt+1}")
                break
        except Exception as e:
            logger.error(f"[CHAIN_GATE] {sid} regen_fn raised exception: {e}")
            break

    # Extract final chain contract from winning video
    contract = None
    try:
        contract = extract_chain_contract(current_path, shot)
    except Exception as e:
        logger.debug(f"[CHAIN_GATE] {sid} contract extraction failed: {e}")

    # Build final GateResult with attempt metadata
    final_gate = validate_post_generation(
        shot=shot,
        video_path=current_path,
        prev_contract=prev_contract,
    )
    final_gate.auto_fix_applied = auto_fix_applied
    final_gate.attempts = attempts_used

    return current_path, contract, final_gate


# ══════════════════════════════════════════════════════════════════════════════
# FULL PLAN VALIDATION — run_full_validation()
# ══════════════════════════════════════════════════════════════════════════════

def run_full_validation(
    shot_plan_path: str,
    story_bible_path: str | None = None,
) -> dict[str, Any]:
    """
    Validate ALL shots in a shot plan against the pre-generation gate.
    Produces a structured report useful for review before spending on generation.

    Args:
        shot_plan_path:   Path to shot_plan.json
        story_bible_path: Path to story_bible.json (optional, enables location checks)

    Returns:
        {
            "total_shots": int,
            "passed": int,
            "failed": int,
            "warnings_only": int,
            "failure_breakdown": {error_code: count},
            "duration_corrections": [{shot_id, current, recommended}],
            "shot_results": [{shot_id, passed, errors, warnings}],
            "summary": str,
        }
    """
    sp_path = Path(shot_plan_path)
    if not sp_path.exists():
        return {"error": f"shot_plan.json not found: {shot_plan_path}"}

    with open(sp_path) as f:
        sp = json.load(f)
    if isinstance(sp, list):
        sp = {"shots": sp}
    shots = sp.get("shots", [])

    story_bible: dict | None = None
    if story_bible_path and Path(story_bible_path).exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)

    # Group shots by scene for cross-shot checks
    scene_map: dict[str, list[dict]] = {}
    for s in shots:
        sid = s.get("shot_id") or ""
        prefix = sid[:3] if len(sid) >= 3 else "000"
        scene_map.setdefault(prefix, []).append(s)

    total = len(shots)
    passed_count = 0
    failed_count = 0
    warn_only_count = 0
    failure_breakdown: dict[str, int] = {}
    duration_corrections: list[dict]  = []
    shot_results: list[dict]          = []

    for shot in shots:
        sid = shot.get("shot_id") or "?"
        prefix = sid[:3] if len(sid) >= 3 else "000"
        scene_shots = scene_map.get(prefix, [])

        result = validate_pre_generation(shot, scene_shots, story_bible)

        shot_results.append({
            "shot_id": sid,
            "passed": result.passed,
            "errors": result.errors,
            "warnings": result.warnings,
            "arc_position": shot.get("_arc_position", "?"),
        })

        if result.passed:
            if result.warnings:
                warn_only_count += 1
            else:
                passed_count += 1
        else:
            failed_count += 1
            for err in result.errors:
                # Extract error code (first token before colon)
                code = err.split(":")[0].strip()
                failure_breakdown[code] = failure_breakdown.get(code, 0) + 1

        # Track duration corrections
        ideal = compute_duration_for_shot(shot)
        current = float(shot.get("duration") or 5.0)
        if abs(ideal - current) > 0.5:
            duration_corrections.append({
                "shot_id": sid,
                "current_s": current,
                "recommended_s": ideal,
                "reason": "2-clip stitch" if ideal >= 20 else "dialogue minimum",
            })

    clean_pass = passed_count + warn_only_count
    summary_lines = [
        f"CHAIN INTELLIGENCE GATE — Pre-Generation Report",
        f"{'='*50}",
        f"Total shots:    {total}",
        f"✓ Pass:         {clean_pass} ({100*clean_pass//max(total,1)}%)",
        f"⚠ Warn only:   {warn_only_count}",
        f"✗ Fail:         {failed_count}",
    ]
    if failure_breakdown:
        summary_lines.append(f"\nFailure breakdown:")
        for code, count in sorted(failure_breakdown.items(), key=lambda x: -x[1]):
            summary_lines.append(f"  {code}: {count}")
    if duration_corrections:
        summary_lines.append(f"\nDuration corrections needed: {len(duration_corrections)}")
        for dc in duration_corrections[:5]:
            summary_lines.append(
                f"  {dc['shot_id']}: {dc['current_s']}s → {dc['recommended_s']}s ({dc['reason']})"
            )
        if len(duration_corrections) > 5:
            summary_lines.append(f"  ... and {len(duration_corrections)-5} more")

    gate_color = "✅ READY" if failed_count == 0 else f"❌ {failed_count} SHOTS NEED FIXES"
    summary_lines.append(f"\n{gate_color}")

    return {
        "total_shots": total,
        "passed": clean_pass,
        "failed": failed_count,
        "warnings_only": warn_only_count,
        "failure_breakdown": failure_breakdown,
        "duration_corrections": duration_corrections,
        "shot_results": shot_results,
        "summary": "\n".join(summary_lines),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════════════

def _print_report(report: dict[str, Any]) -> None:
    """Pretty-print a validation report to stdout."""
    print(f"\n{report['summary']}")

    if report.get("failed", 0) > 0:
        print(f"\n{'─'*50}")
        print("FAILING SHOTS:")
        for sr in report.get("shot_results", []):
            if not sr["passed"] and sr["errors"]:
                print(f"\n  [{sr.get('arc_position','?'):10s}] {sr['shot_id']}")
                for err in sr["errors"]:
                    print(f"    ✗ {err[:120]}")

    if any(sr["warnings"] for sr in report.get("shot_results", [])):
        print(f"\n{'─'*50}")
        print("WARNINGS (non-blocking):")
        for sr in report.get("shot_results", []):
            for w in sr.get("warnings", []):
                print(f"  ⚠ [{sr['shot_id']}] {w[:100]}")

    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tools/chain_intelligence_gate.py <shot_plan.json> [story_bible.json]")
        print("  python3 tools/chain_intelligence_gate.py pipeline_outputs/victorian_shadows_ep1")
        sys.exit(1)

    arg = sys.argv[1]
    arg_path = Path(arg)

    # Accept project directory or direct file path
    if arg_path.is_dir():
        sp_path = arg_path / "shot_plan.json"
        sb_path = arg_path / "story_bible.json"
    else:
        sp_path = arg_path
        sb_path = Path(sys.argv[2]) if len(sys.argv) > 2 else sp_path.parent / "story_bible.json"

    if not sp_path.exists():
        print(f"ERROR: {sp_path} not found")
        sys.exit(1)

    report = run_full_validation(
        str(sp_path),
        str(sb_path) if sb_path.exists() else None,
    )
    _print_report(report)
    sys.exit(0 if report.get("failed", 0) == 0 else 1)
