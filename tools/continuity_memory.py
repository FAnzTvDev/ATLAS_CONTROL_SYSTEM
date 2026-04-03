"""
ATLAS V24.1 — CONTINUITY MEMORY ENGINE (Spatial Continuity Layer)
=================================================================
The missing layer between VisionAnalyst and Film Engine.

Instead of relying on text delta prompts to maintain shot-to-shot continuity,
this module stores STRUCTURED spatial state from each shot's end frame and
injects it as concrete geometry into the next shot's generation.

Brain mapping:
  - Working memory (prefrontal): holds current scene spatial state
  - Spatial memory (parietal): character positions, camera geometry
  - Procedural memory (cerebellum): learned reframe patterns
  - Episodic memory (hippocampal): shot-to-shot transition history

Architecture:
  VisionAnalyst reads end frame → ContinuityMemory stores state →
  ReframeCandidateGenerator proposes options → BasalGanglia scores →
  MetaDirector picks top 2 → Film Engine compiles winner → render

Usage:
  from tools.continuity_memory import ContinuityMemory
  mem = ContinuityMemory(project_path)
  mem.store_shot_state(shot_id, spatial_state)
  candidates = mem.generate_reframe_candidates(shot, previous_state)
  delta = mem.compile_continuity_delta(selected_candidate, previous_state)
"""

import json
import os
import logging
import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class CharacterSpatialState:
    """Spatial state of a single character in frame."""
    name: str
    screen_position: Tuple[float, float] = (0.5, 0.5)  # normalized x, y
    body_angle: str = "frontal"  # frontal, three-quarter-left, three-quarter-right, profile-left, profile-right, back
    gaze_direction: str = "camera"  # camera, left, right, up, down, character-name
    emotion_read: str = "neutral"
    emotion_intensity: float = 0.5  # 0.0 = flat, 1.0 = extreme
    gesture_state: str = "neutral"  # e.g. "hand gripping curtain", "arms crossed"
    posture: str = "standing"  # standing, sitting, kneeling, leaning, walking
    depth_plane: str = "mid"  # foreground, mid, background

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CameraState:
    """Camera geometry state."""
    shot_scale: str = "medium"  # extreme_wide, wide, medium_wide, medium, medium_close, close, extreme_close
    focal_length_equiv: int = 50  # mm equivalent
    axis_line: str = "preserved"  # preserved, crossed, neutral
    camera_motion: str = "static"  # static, slow_push, slow_pull, pan_left, pan_right, dolly, handheld
    height: str = "eye_level"  # low, eye_level, high, overhead
    screen_direction: str = "left_to_right"  # left_to_right, right_to_left, neutral

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnvironmentState:
    """Scene environment state."""
    location: str = ""
    light_direction: str = "neutral"  # screen_left, screen_right, overhead, behind, neutral
    light_quality: str = "natural"  # natural, warm_practical, cold_clinical, dramatic_contrast, soft_diffuse
    atmosphere: str = "neutral"  # tension, calm, dread, hope, melancholy, etc.
    key_props: List[str] = field(default_factory=list)
    background_depth: str = "medium"  # shallow (bokeh), medium, deep (everything sharp)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShotSpatialState:
    """Complete spatial state of a single shot's end frame."""
    shot_id: str
    scene_id: str
    timestamp: str = ""
    characters: List[CharacterSpatialState] = field(default_factory=list)
    camera: CameraState = field(default_factory=CameraState)
    environment: EnvironmentState = field(default_factory=EnvironmentState)
    motion_vector: str = "static"  # describes active motion at frame end
    frame_hash: str = ""  # SHA256 of the actual frame image if available

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class ReframeCandidate:
    """A proposed reframe for the next shot."""
    candidate_id: str
    strategy: str  # "continuity_match", "emotional_push", "action_widen", "reveal_ots", "reaction_cut"
    description: str  # human-readable description
    proposed_camera: CameraState = field(default_factory=CameraState)
    proposed_character_focus: str = ""  # which character to focus on
    continuity_score: float = 0.0  # 0-1, how well this preserves spatial continuity
    cinematic_score: float = 0.0  # 0-1, how good this is cinematically
    emotional_fit: float = 0.0  # 0-1, how well this fits the emotional arc
    cost_preference: str = "neutral"  # "kling_preferred", "ltx_ok", "neutral"
    delta_prompt: str = ""  # the structured delta verbiage for generation

    def composite_score(self, weights: dict = None) -> float:
        w = weights or {"continuity": 0.40, "cinematic": 0.35, "emotion": 0.25}
        return (
            self.continuity_score * w.get("continuity", 0.40)
            + self.cinematic_score * w.get("cinematic", 0.35)
            + self.emotional_fit * w.get("emotion", 0.25)
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["composite_score"] = self.composite_score()
        return d


# ============================================================================
# CONSTANTS — SHOT SCALE ORDERING + REFRAME RULES
# ============================================================================

SHOT_SCALE_ORDER = [
    "extreme_wide", "wide", "medium_wide", "medium",
    "medium_close", "close", "extreme_close",
]

SHOT_SCALE_FOCAL = {
    "extreme_wide": 14, "wide": 24, "medium_wide": 35,
    "medium": 50, "medium_close": 65, "close": 85,
    "extreme_close": 135,
}

# ============================================================================
# V26.1: SMART CHAIN CLASSIFICATION
# ============================================================================
# Three chain modes replace the old binary "chain or not" decision:
#   REFRAME         — Same primary character, different angle (end-frame reframe)
#   BLOCKING_AWARE  — Different character (dialogue cut), generate fresh WITH spatial memory
#   INDEPENDENT     — B-roll, establishing, no characters (no chain, no delta)

def classify_chain_transition(prev_shot: dict, curr_shot: dict) -> str:
    """Classify the transition between two shots for chain pipeline.

    Returns one of: "REFRAME", "BLOCKING_AWARE", "INDEPENDENT"

    REFRAME: Same primary character in both shots → end-frame reframe (env locked by image).
    BLOCKING_AWARE: Different primary character (dialogue cut) → generate fresh first frame
        but inject continuity delta describing previous shot's spatial state so blocking,
        environment, and lighting remain consistent.
    INDEPENDENT: No characters, B-roll, establishing → standard text-to-image, no chain.
    """
    # INDEPENDENT: no characters, b-roll, establishing, explicitly no-chain
    curr_chars = curr_shot.get("characters") or []
    if isinstance(curr_chars, str):
        curr_chars = [c.strip() for c in curr_chars.split(",") if c.strip()]
    if not curr_chars:
        return "INDEPENDENT"

    curr_type = (curr_shot.get("type") or curr_shot.get("shot_type") or "").lower()
    if curr_shot.get("_broll") or curr_shot.get("_no_chain") or curr_type in ("b-roll", "b_roll", "broll", "establishing", "master"):
        return "INDEPENDENT"

    if not prev_shot:
        return "INDEPENDENT"

    prev_chars = prev_shot.get("characters") or []
    if isinstance(prev_chars, str):
        prev_chars = [c.strip() for c in prev_chars.split(",") if c.strip()]
    if not prev_chars:
        return "BLOCKING_AWARE"  # Previous had no chars, but current does — fresh gen with awareness

    # Compare primary characters (first in list = primary/focus)
    prev_primary = prev_chars[0].upper().strip() if prev_chars else ""
    curr_primary = curr_chars[0].upper().strip() if curr_chars else ""

    # Same primary character → REFRAME (same moment, different angle)
    if prev_primary == curr_primary:
        # Additional check: if shot is widening significantly (close → wide), use BLOCKING_AWARE
        # because reframing a close-up to a wide shot produces artifacts
        prev_scale = _normalize_shot_scale((prev_shot.get("type") or prev_shot.get("shot_type") or "").lower())
        curr_scale = _normalize_shot_scale(curr_type)
        prev_idx = SHOT_SCALE_ORDER.index(prev_scale) if prev_scale in SHOT_SCALE_ORDER else 3
        curr_idx = SHOT_SCALE_ORDER.index(curr_scale) if curr_scale in SHOT_SCALE_ORDER else 3
        if curr_idx < prev_idx - 2:
            # Widening by 3+ steps (e.g., close → wide) — reframe would stretch/distort
            return "BLOCKING_AWARE"
        return "REFRAME"

    # Different primary character → BLOCKING_AWARE (dialogue cut, reaction cut)
    return "BLOCKING_AWARE"


def _normalize_shot_scale(shot_type: str) -> str:
    """Normalize shot type to scale category."""
    _map = {
        "establishing": "extreme_wide", "wide": "wide", "mws": "medium_wide",
        "medium_wide": "medium_wide", "medium": "medium", "med": "medium",
        "mcu": "medium_close", "medium_close": "medium_close",
        "close_up": "close", "close": "close", "cu": "close",
        "ecu": "extreme_close", "extreme_close": "extreme_close",
        "detail": "extreme_close", "insert": "extreme_close",
        "reaction": "medium_close", "ots": "medium_close",
        "two_shot": "medium", "closing": "wide",
    }
    return _map.get(shot_type, "medium")


# Reframe strategies based on emotional intensity change
EMOTION_REFRAME_MAP = {
    "rising": ["emotional_push", "continuity_match"],  # tighten
    "falling": ["action_widen", "reveal_ots"],  # widen
    "peak": ["emotional_push", "reaction_cut"],  # extreme close or reaction
    "stable": ["continuity_match", "action_widen"],  # maintain or slight variety
}

# Camera movement suggestions by emotion
EMOTION_CAMERA_MAP = {
    "dread": "slow_push",
    "tension": "static",
    "calm": "slow_pull",
    "hope": "slow_pull",
    "grief": "static",
    "anger": "handheld",
    "revelation": "slow_push",
    "resignation": "static",
    "fear": "handheld",
    "love": "slow_push",
    "suspense": "slow_push",
    "relief": "slow_pull",
}

# Body angle descriptions for prompt injection
BODY_ANGLE_PROMPTS = {
    "frontal": "facing camera directly",
    "three-quarter-left": "angled slightly left of camera, three-quarter view",
    "three-quarter-right": "angled slightly right of camera, three-quarter view",
    "profile-left": "in left profile, looking screen-left",
    "profile-right": "in right profile, looking screen-right",
    "back": "facing away from camera, showing back",
}

# Screen position descriptions
POSITION_ZONE_MAP = {
    (0.0, 0.33): "left third",
    (0.33, 0.66): "center frame",
    (0.66, 1.0): "right third",
}

DEPTH_PROMPTS = {
    "foreground": "in the foreground, close to camera",
    "mid": "at mid-depth in the frame",
    "background": "in the background, further from camera",
}


# ============================================================================
# SPATIAL STATE EXTRACTION FROM SHOT METADATA
# ============================================================================

def extract_spatial_state_from_metadata(shot: dict, cast_map: dict = None) -> ShotSpatialState:
    """
    Extract spatial state from shot metadata (no vision required).
    This is the deterministic/heuristic path — used when no actual frame
    exists yet or as a baseline before vision analysis refines it.
    """
    shot_id = shot.get("shot_id") or "unknown"
    scene_id = shot.get("scene_id") or "unknown"
    characters = shot.get("characters") or []
    shot_type = (shot.get("shot_type") or "medium").lower().replace(" ", "_")
    nano = shot.get("nano_prompt") or ""
    ltx = shot.get("ltx_motion_prompt") or ""
    combined = nano + " " + ltx

    # ── Character states ──
    char_states = []
    for i, char_name in enumerate(characters):
        cs = CharacterSpatialState(name=char_name)

        # Position heuristic: single char = center, two = left/right split
        if len(characters) == 1:
            cs.screen_position = (0.5, 0.55)
        elif len(characters) == 2:
            cs.screen_position = (0.35, 0.55) if i == 0 else (0.65, 0.55)
        else:
            spread = 0.7 / max(1, len(characters) - 1)
            cs.screen_position = (0.15 + i * spread, 0.55)

        # Body angle from shot type
        if "ots" in shot_type or "over" in shot_type:
            cs.body_angle = "three-quarter-right" if i == 0 else "three-quarter-left"
        elif "profile" in combined.lower():
            cs.body_angle = "profile-right"
        elif "back" in shot_type:
            cs.body_angle = "back"
        else:
            cs.body_angle = "three-quarter-right" if i % 2 == 0 else "frontal"

        # Emotion from shot metadata
        emotion = shot.get("emotion", "neutral")
        cs.emotion_read = emotion
        cs.emotion_intensity = _estimate_emotion_intensity(emotion)

        # Gesture from prompt parsing
        cs.gesture_state = _extract_gesture(combined, char_name)

        # Posture from prompt
        cs.posture = _extract_posture(combined, char_name)

        # Gaze
        if shot.get("dialogue_text") and len(characters) > 1:
            other = characters[1 - i] if len(characters) == 2 else "other"
            cs.gaze_direction = other
        else:
            cs.gaze_direction = "camera" if "close" in shot_type else "neutral"

        char_states.append(cs)

    # ── Camera state ──
    cam = CameraState()
    cam.shot_scale = _normalize_shot_scale(shot_type)
    cam.focal_length_equiv = SHOT_SCALE_FOCAL.get(cam.shot_scale, 50)
    cam.camera_motion = _extract_camera_motion(combined)

    coverage = shot.get("coverage_role") or ""
    if "A_GEOGRAPHY" in coverage:
        cam.shot_scale = "wide"
        cam.focal_length_equiv = 24
    elif "C_EMOTION" in coverage:
        cam.shot_scale = "close"
        cam.focal_length_equiv = 85

    # ── Environment state ──
    env = EnvironmentState()
    env.location = shot.get("location", "")
    env.atmosphere = shot.get("emotion", "neutral")
    env.key_props = _extract_props(combined)
    env.light_direction = _extract_light_direction(combined)

    return ShotSpatialState(
        shot_id=shot_id,
        scene_id=scene_id,
        timestamp=datetime.now().isoformat(),
        characters=char_states,
        camera=cam,
        environment=env,
    )


# ============================================================================
# REFRAME CANDIDATE GENERATOR
# ============================================================================

def generate_reframe_candidates(
    shot: dict,
    previous_state: Optional[ShotSpatialState],
    beat_intent: str = "",
    emotion_trajectory: str = "stable",
    num_candidates: int = 3,
) -> List[ReframeCandidate]:
    """
    Generate reframe candidates for the NEXT shot based on previous state.

    Args:
        shot: The next shot's metadata (what we're generating for)
        previous_state: Spatial state from the previous shot's end frame
        beat_intent: The story beat intention ("reveal", "escalate", "resolve")
        emotion_trajectory: "rising", "falling", "peak", "stable"
        num_candidates: How many candidates to generate

    Returns:
        List of ReframeCandidate, scored and ready for BasalGanglia ranking
    """
    candidates = []
    shot_type = (shot.get("shot_type") or "medium").lower().replace(" ", "_")
    characters = shot.get("characters") or []
    has_dialogue = bool((shot.get("dialogue_text") or "").strip())
    prev_scale = previous_state.camera.shot_scale if previous_state else "medium"
    prev_scale_idx = SHOT_SCALE_ORDER.index(prev_scale) if prev_scale in SHOT_SCALE_ORDER else 3

    # Strategy pool based on emotion trajectory
    strategies = EMOTION_REFRAME_MAP.get(emotion_trajectory, ["continuity_match", "action_widen"])

    # ── Always generate: Continuity Match (conservative, preserve blocking) ──
    cand1 = _build_continuity_match(shot, previous_state, prev_scale, characters)
    candidates.append(cand1)

    # ── Dialogue with multiple characters: PRIORITIZE reaction cut ──
    if has_dialogue and len(characters) > 1:
        cand_react = _build_reaction_cut(shot, previous_state, characters, has_dialogue)
        candidates.append(cand_react)

    # ── Emotional Push (tighten based on intensity) ──
    if "emotional_push" in strategies or emotion_trajectory in ("rising", "peak"):
        cand2 = _build_emotional_push(shot, previous_state, prev_scale_idx, characters, has_dialogue)
        candidates.append(cand2)

    # ── Action Widen / Reveal (loosen for geography/blocking clarity) ──
    cand3 = _build_action_widen(shot, previous_state, prev_scale_idx, characters)
    candidates.append(cand3)

    # ── Reaction Cut (if not already added for non-dialogue multi-char) ──
    if not has_dialogue and len(characters) > 1:
        cand4 = _build_reaction_cut(shot, previous_state, characters, has_dialogue)
        candidates.append(cand4)

    # ── Over-the-Shoulder (classic coverage for 2+ characters) ──
    if len(characters) >= 2:
        cand5 = _build_ots_candidate(shot, previous_state, characters)
        candidates.append(cand5)

    # Trim to requested count
    candidates = candidates[:num_candidates]

    # Score all candidates
    for c in candidates:
        c.continuity_score = _score_continuity(c, previous_state)
        c.cinematic_score = _score_cinematic(c, previous_state, emotion_trajectory)
        c.emotional_fit = _score_emotional_fit(c, shot, emotion_trajectory)

    # Sort by composite score (best first)
    candidates.sort(key=lambda c: c.composite_score(), reverse=True)

    return candidates


# ============================================================================
# CANDIDATE BUILDERS
# ============================================================================

def _build_continuity_match(
    shot: dict, prev: Optional[ShotSpatialState], prev_scale: str, characters: list
) -> ReframeCandidate:
    """Conservative: preserve previous blocking, minimal camera change."""
    cam = CameraState()
    cam.shot_scale = prev_scale
    cam.focal_length_equiv = SHOT_SCALE_FOCAL.get(prev_scale, 50)
    cam.camera_motion = "static"
    cam.axis_line = "preserved"

    focus = characters[0] if characters else ""
    desc = f"Maintain {prev_scale} framing"
    if prev and prev.characters:
        pc = prev.characters[0]
        desc += f", preserve {pc.name} at {_position_zone(pc.screen_position)}"

    delta = _build_delta_prompt(
        "continuity_match", cam, prev, focus,
        "Preserve exact blocking, position, and body angle from previous shot."
    )

    return ReframeCandidate(
        candidate_id=f"{shot.get('shot_id','?')}_cont",
        strategy="continuity_match",
        description=desc,
        proposed_camera=cam,
        proposed_character_focus=focus,
        cost_preference="ltx_ok",
        delta_prompt=delta,
    )


def _build_emotional_push(
    shot: dict, prev: Optional[ShotSpatialState],
    prev_idx: int, characters: list, has_dialogue: bool
) -> ReframeCandidate:
    """Tighten for emotional emphasis — push closer to face/emotion."""
    target_idx = min(prev_idx + 1, len(SHOT_SCALE_ORDER) - 1)
    if has_dialogue:
        target_idx = max(target_idx, 4)  # at least medium_close for dialogue
    target_scale = SHOT_SCALE_ORDER[target_idx]

    cam = CameraState()
    cam.shot_scale = target_scale
    cam.focal_length_equiv = SHOT_SCALE_FOCAL.get(target_scale, 65)
    cam.camera_motion = "slow_push"
    cam.axis_line = "preserved"

    focus = characters[0] if characters else ""
    emotion = shot.get("emotion", "tension")
    desc = f"Push to {target_scale} for emotional emphasis ({emotion})"

    delta = _build_delta_prompt(
        "emotional_push", cam, prev, focus,
        f"Tighten framing to emphasize {emotion}. Preserve character position "
        f"and body angle. Push camera closer, facial expression becomes dominant."
    )

    return ReframeCandidate(
        candidate_id=f"{shot.get('shot_id','?')}_emot",
        strategy="emotional_push",
        description=desc,
        proposed_camera=cam,
        proposed_character_focus=focus,
        cost_preference="kling_preferred" if has_dialogue else "neutral",
        delta_prompt=delta,
    )


def _build_action_widen(
    shot: dict, prev: Optional[ShotSpatialState],
    prev_idx: int, characters: list
) -> ReframeCandidate:
    """Widen for blocking clarity or tension release."""
    target_idx = max(prev_idx - 1, 0)
    target_scale = SHOT_SCALE_ORDER[target_idx]

    cam = CameraState()
    cam.shot_scale = target_scale
    cam.focal_length_equiv = SHOT_SCALE_FOCAL.get(target_scale, 35)
    cam.camera_motion = "slow_pull"
    cam.axis_line = "preserved"

    focus = ""  # wider = all characters
    desc = f"Widen to {target_scale} for blocking clarity"

    delta = _build_delta_prompt(
        "action_widen", cam, prev, focus,
        "Pull back to reveal more environment and character blocking. "
        "Preserve screen direction and character placement."
    )

    return ReframeCandidate(
        candidate_id=f"{shot.get('shot_id','?')}_wide",
        strategy="action_widen",
        description=desc,
        proposed_camera=cam,
        proposed_character_focus=focus,
        cost_preference="ltx_ok",
        delta_prompt=delta,
    )


def _build_reaction_cut(
    shot: dict, prev: Optional[ShotSpatialState],
    characters: list, has_dialogue: bool
) -> ReframeCandidate:
    """Switch focus to listening/reacting character."""
    # If prev focused on char[0], switch to char[1]
    prev_focus = ""
    if prev and prev.characters:
        prev_focus = prev.characters[0].name

    focus_idx = 0
    for i, c in enumerate(characters):
        if c != prev_focus:
            focus_idx = i
            break
    focus = characters[focus_idx] if focus_idx < len(characters) else characters[0]

    cam = CameraState()
    cam.shot_scale = "medium_close"
    cam.focal_length_equiv = 65
    cam.camera_motion = "static"
    cam.screen_direction = "right_to_left" if prev and prev.camera.screen_direction == "left_to_right" else "left_to_right"

    desc = f"Reaction cut to {focus}"
    delta = _build_delta_prompt(
        "reaction_cut", cam, prev, focus,
        f"{focus} listens and reacts. Show emotional response on face. "
        f"Reverse screen direction for shot/reverse-shot pattern."
    )

    return ReframeCandidate(
        candidate_id=f"{shot.get('shot_id','?')}_react",
        strategy="reaction_cut",
        description=desc,
        proposed_camera=cam,
        proposed_character_focus=focus,
        cost_preference="kling_preferred",
        delta_prompt=delta,
    )


def _build_ots_candidate(
    shot: dict, prev: Optional[ShotSpatialState], characters: list
) -> ReframeCandidate:
    """Over-the-shoulder for two-character dialogue coverage."""
    focus = characters[0]
    ots_char = characters[1] if len(characters) > 1 else characters[0]

    cam = CameraState()
    cam.shot_scale = "medium_close"
    cam.focal_length_equiv = 65
    cam.camera_motion = "static"
    cam.axis_line = "preserved"

    desc = f"Over-the-shoulder: {ots_char}'s shoulder, focus on {focus}"
    delta = _build_delta_prompt(
        "reveal_ots", cam, prev, focus,
        f"Over-the-shoulder from behind {ots_char}, facing {focus}. "
        f"{ots_char}'s shoulder/back in foreground blur. "
        f"Preserve 180-degree axis line."
    )

    return ReframeCandidate(
        candidate_id=f"{shot.get('shot_id','?')}_ots",
        strategy="reveal_ots",
        description=desc,
        proposed_camera=cam,
        proposed_character_focus=focus,
        cost_preference="kling_preferred",
        delta_prompt=delta,
    )


# ============================================================================
# DELTA PROMPT BUILDER — Structured continuity verbiage
# ============================================================================

def _build_delta_prompt(
    strategy: str,
    proposed_camera: CameraState,
    previous_state: Optional[ShotSpatialState],
    focus_character: str,
    instruction: str,
) -> str:
    """
    Build structured delta prompt that injects spatial memory into generation.
    This replaces vague text like "continue naturally" with concrete geometry.
    """
    parts = []

    # Section 1: CONTINUITY MEMORY
    if previous_state and previous_state.characters:
        parts.append("CONTINUITY MEMORY:")
        parts.append("Previous shot final frame establishes:")
        for cs in previous_state.characters:
            zone = _position_zone(cs.screen_position)
            angle_desc = BODY_ANGLE_PROMPTS.get(cs.body_angle, cs.body_angle)
            parts.append(f"- {cs.name} at {zone}, {angle_desc}")
            if cs.gesture_state and cs.gesture_state != "neutral":
                parts.append(f"  gesture: {cs.gesture_state}")
            if cs.emotion_read and cs.emotion_read != "neutral":
                parts.append(f"  emotion: {cs.emotion_read}")

        # Camera memory
        parts.append(f"- Camera: {previous_state.camera.shot_scale}, "
                     f"direction {previous_state.camera.screen_direction}")
        if previous_state.environment.light_direction != "neutral":
            parts.append(f"- Light: from {previous_state.environment.light_direction}")

    # Section 2: REFRAME PLAN
    parts.append("")
    parts.append("REFRAME PLAN:")
    parts.append(instruction)
    parts.append(f"- Target framing: {proposed_camera.shot_scale} "
                f"({proposed_camera.focal_length_equiv}mm equivalent)")
    if proposed_camera.camera_motion != "static":
        parts.append(f"- Camera motion: {proposed_camera.camera_motion}")
    if focus_character:
        parts.append(f"- Focus: {focus_character}")

    # Section 3: MODEL EXECUTION CONSTRAINTS
    parts.append("")
    parts.append("EXECUTION CONSTRAINTS:")
    parts.append("- DO NOT reset character pose to default idle")
    parts.append("- DO NOT flip screen direction / axis line")
    parts.append("- Preserve facial identity from reference")
    if strategy == "continuity_match":
        parts.append("- Minimal change from previous frame composition")
    elif strategy == "emotional_push":
        parts.append("- Allow tighter framing but preserve blocking position")
    elif strategy == "reaction_cut":
        parts.append("- Reverse shot direction for dialogue pattern")
        parts.append("- Show listening/reaction, not speaking")

    return "\n".join(parts)


def compile_continuity_delta(
    candidate: ReframeCandidate,
    previous_state: Optional[ShotSpatialState],
    shot: dict,
) -> str:
    """
    Compile the final continuity delta string ready for prompt injection.
    This gets appended to the Film Engine compiled prompt.
    """
    if not candidate.delta_prompt:
        return ""

    # Add shot-specific context
    parts = [candidate.delta_prompt]

    # Add character-specific carryover
    if previous_state:
        for cs in previous_state.characters:
            if cs.name in (shot.get("characters") or []):
                if cs.gesture_state and cs.gesture_state != "neutral":
                    parts.append(f"Continue {cs.name}'s gesture: {cs.gesture_state}")

    return "\n".join(parts)


# ============================================================================
# CONTINUITY MEMORY STORE (per-project persistence)
# ============================================================================

class ContinuityMemory:
    """
    Per-project continuity memory — stores spatial state across shots.
    Persists to disk as JSON for crash recovery.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.memory_dir = os.path.join(project_path, "continuity_memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self._states: Dict[str, ShotSpatialState] = {}
        self._transition_log: List[dict] = []
        self._load()

    def _load(self):
        """Load persisted memory from disk."""
        state_file = os.path.join(self.memory_dir, "spatial_states.json")
        if os.path.exists(state_file):
            try:
                data = json.load(open(state_file))
                for shot_id, state_data in data.items():
                    self._states[shot_id] = self._dict_to_state(state_data)
                logger.info(f"Loaded {len(self._states)} spatial states from memory")
            except Exception as e:
                logger.warning(f"Failed to load continuity memory: {e}")

        log_file = os.path.join(self.memory_dir, "transitions.jsonl")
        if os.path.exists(log_file):
            try:
                with open(log_file) as f:
                    self._transition_log = [json.loads(line) for line in f if line.strip()]
            except Exception:
                pass

    def _save(self):
        """Persist current memory to disk."""
        state_file = os.path.join(self.memory_dir, "spatial_states.json")
        data = {sid: s.to_dict() for sid, s in self._states.items()}
        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_transition(self, transition: dict):
        """Append a transition to the log."""
        log_file = os.path.join(self.memory_dir, "transitions.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(transition) + "\n")

    def store_shot_state(
        self, shot_id: str, state: ShotSpatialState
    ):
        """Store spatial state for a shot (typically after vision analysis of end frame)."""
        self._states[shot_id] = state
        self._save()
        logger.info(f"Stored spatial state for {shot_id}: "
                    f"{len(state.characters)} chars, camera={state.camera.shot_scale}")

    def get_shot_state(self, shot_id: str) -> Optional[ShotSpatialState]:
        """Retrieve stored spatial state for a shot."""
        return self._states.get(shot_id)

    def get_previous_state(self, shot_id: str, scene_shots: List[dict]) -> Optional[ShotSpatialState]:
        """Get the spatial state of the shot immediately before this one in scene order."""
        shot_ids = [s.get("shot_id", "") for s in scene_shots]
        try:
            idx = shot_ids.index(shot_id)
            if idx > 0:
                prev_id = shot_ids[idx - 1]
                return self._states.get(prev_id)
        except ValueError:
            pass
        return None

    def generate_candidates(
        self,
        shot: dict,
        scene_shots: List[dict],
        beat_intent: str = "",
        emotion_trajectory: str = "stable",
        num_candidates: int = 3,
    ) -> List[ReframeCandidate]:
        """
        Generate reframe candidates using stored memory.
        Convenience method that wraps generate_reframe_candidates().
        """
        prev_state = self.get_previous_state(shot.get("shot_id", ""), scene_shots)
        return generate_reframe_candidates(
            shot, prev_state, beat_intent, emotion_trajectory, num_candidates
        )

    def record_transition(
        self,
        from_shot_id: str,
        to_shot_id: str,
        selected_candidate: ReframeCandidate,
        alternate_candidate: Optional[ReframeCandidate] = None,
    ):
        """Record a shot-to-shot transition decision."""
        transition = {
            "timestamp": datetime.now().isoformat(),
            "from_shot": from_shot_id,
            "to_shot": to_shot_id,
            "selected": selected_candidate.to_dict(),
            "alternate": alternate_candidate.to_dict() if alternate_candidate else None,
        }
        self._transition_log.append(transition)
        self._save_transition(transition)

    def get_scene_memory(self, scene_id: str) -> List[ShotSpatialState]:
        """Get all stored states for a scene, in order."""
        scene_states = [
            (sid, s) for sid, s in self._states.items()
            if s.scene_id == scene_id
        ]
        scene_states.sort(key=lambda x: x[0])
        return [s for _, s in scene_states]

    def get_emotion_arc(self, scene_id: str) -> List[Tuple[str, float]]:
        """Extract emotion trajectory from scene memory."""
        states = self.get_scene_memory(scene_id)
        arc = []
        for state in states:
            if state.characters:
                avg_intensity = sum(c.emotion_intensity for c in state.characters) / len(state.characters)
                primary_emotion = state.characters[0].emotion_read
                arc.append((primary_emotion, avg_intensity))
        return arc

    def get_statistics(self) -> dict:
        """Return memory statistics."""
        scenes = set(s.scene_id for s in self._states.values())
        return {
            "total_states": len(self._states),
            "scenes_tracked": len(scenes),
            "transitions_logged": len(self._transition_log),
            "memory_dir": self.memory_dir,
        }

    def clear_scene(self, scene_id: str):
        """Clear memory for a specific scene (e.g., before re-render)."""
        to_remove = [sid for sid, s in self._states.items() if s.scene_id == scene_id]
        for sid in to_remove:
            del self._states[sid]
        self._save()

    @staticmethod
    def _dict_to_state(d: dict) -> ShotSpatialState:
        """Reconstruct ShotSpatialState from dict."""
        chars = []
        for cd in (d.get("characters") or []):
            cs = CharacterSpatialState(
                name=cd.get("name") or "",
                screen_position=tuple(cd.get("screen_position") or [0.5, 0.5]),
                body_angle=cd.get("body_angle", "frontal"),
                gaze_direction=cd.get("gaze_direction", "camera"),
                emotion_read=cd.get("emotion_read", "neutral"),
                emotion_intensity=cd.get("emotion_intensity", 0.5),
                gesture_state=cd.get("gesture_state", "neutral"),
                posture=cd.get("posture", "standing"),
                depth_plane=cd.get("depth_plane", "mid"),
            )
            chars.append(cs)

        cam_d = d.get("camera") or {}
        cam = CameraState(
            shot_scale=cam_d.get("shot_scale", "medium"),
            focal_length_equiv=cam_d.get("focal_length_equiv", 50),
            axis_line=cam_d.get("axis_line", "preserved"),
            camera_motion=cam_d.get("camera_motion", "static"),
            height=cam_d.get("height", "eye_level"),
            screen_direction=cam_d.get("screen_direction", "left_to_right"),
        )

        env_d = d.get("environment") or {}
        env = EnvironmentState(
            location=env_d.get("location", ""),
            light_direction=env_d.get("light_direction", "neutral"),
            light_quality=env_d.get("light_quality", "natural"),
            atmosphere=env_d.get("atmosphere", "neutral"),
            key_props=env_d.get("key_props", []),
            background_depth=env_d.get("background_depth", "medium"),
        )

        return ShotSpatialState(
            shot_id=d.get("shot_id", ""),
            scene_id=d.get("scene_id", ""),
            timestamp=d.get("timestamp", ""),
            characters=chars,
            camera=cam,
            environment=env,
            motion_vector=d.get("motion_vector", "static"),
            frame_hash=d.get("frame_hash", ""),
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _normalize_shot_scale(shot_type: str) -> str:
    """Map shot_type strings to canonical scale names."""
    mapping = {
        "extreme_wide": "extreme_wide", "establishing": "extreme_wide",
        "wide": "wide", "full": "wide", "master": "wide",
        "medium_wide": "medium_wide", "mws": "medium_wide",
        "medium": "medium", "mid": "medium",
        "medium_close": "medium_close", "mcu": "medium_close", "medium_close_up": "medium_close",
        "close": "close", "close_up": "close", "cu": "close",
        "extreme_close": "extreme_close", "ecu": "extreme_close", "detail": "extreme_close",
        "insert": "extreme_close",
    }
    return mapping.get(shot_type, "medium")


def _estimate_emotion_intensity(emotion: str) -> float:
    """Map emotion to intensity float."""
    intensities = {
        "neutral": 0.3, "calm": 0.2, "hope": 0.4, "love": 0.5,
        "tension": 0.6, "suspense": 0.7, "dread": 0.8, "fear": 0.85,
        "anger": 0.9, "grief": 0.75, "revelation": 0.7,
        "resignation": 0.5, "relief": 0.4,
    }
    return intensities.get(emotion.lower(), 0.5)


def _extract_gesture(text: str, char_name: str = "") -> str:
    """Extract gesture state from prompt text."""
    gesture_patterns = [
        (r"gripping?\s+(\w+[\w\s]*)", "gripping {0}"),
        (r"holding?\s+(\w+[\w\s]*)", "holding {0}"),
        (r"arms?\s+crossed", "arms crossed"),
        (r"hands?\s+clasped", "hands clasped"),
        (r"pointing", "pointing"),
        (r"reaching", "reaching"),
        (r"hand\s+on\s+(\w+)", "hand on {0}"),
        (r"clutching", "clutching"),
        (r"writing", "writing"),
        (r"reading", "reading"),
    ]
    for pattern, template in gesture_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return template.format(match.group(1).strip()[:30])
            except (IndexError, AttributeError):
                return template.replace("{0}", "")
    return "neutral"


def _extract_posture(text: str, char_name: str = "") -> str:
    """Extract posture from prompt text."""
    postures = {
        r"stand": "standing", r"sit": "sitting", r"kneel": "kneeling",
        r"lean": "leaning", r"walk": "walking", r"lying": "lying",
        r"crouch": "crouching", r"pace": "pacing",
    }
    for pattern, posture in postures.items():
        if re.search(pattern, text, re.IGNORECASE):
            return posture
    return "standing"


def _extract_camera_motion(text: str) -> str:
    """Extract camera motion from prompt text."""
    motions = {
        r"push[\s-]?in": "slow_push", r"dolly[\s-]?in": "slow_push",
        r"pull[\s-]?back": "slow_pull", r"dolly[\s-]?out": "slow_pull",
        r"pan\s*left": "pan_left", r"pan\s*right": "pan_right",
        r"handheld": "handheld", r"tracking": "tracking",
        r"crane": "crane", r"tilt": "tilt",
        r"static": "static", r"locked": "static",
    }
    for pattern, motion in motions.items():
        if re.search(pattern, text, re.IGNORECASE):
            return motion
    return "static"


def _extract_light_direction(text: str) -> str:
    """Extract light direction from prompt text."""
    if re.search(r"light.*from.*left|backlit.*left|window.*left", text, re.I):
        return "screen_left"
    if re.search(r"light.*from.*right|backlit.*right|window.*right", text, re.I):
        return "screen_right"
    if re.search(r"overhead|top.*light|ceiling", text, re.I):
        return "overhead"
    if re.search(r"backlit|backlight|silhouette", text, re.I):
        return "behind"
    return "neutral"


def _extract_props(text: str) -> List[str]:
    """Extract key props from prompt text."""
    prop_patterns = [
        r"letter", r"book", r"candle", r"key", r"portrait",
        r"photograph", r"glass", r"bottle", r"knife", r"gun",
        r"phone", r"document", r"ring", r"watch", r"envelope",
        r"newspaper", r"lamp", r"mirror", r"curtain", r"door",
    ]
    found = []
    for pattern in prop_patterns:
        if re.search(r"\b" + pattern + r"\b", text, re.IGNORECASE):
            found.append(pattern)
    return found[:5]  # cap at 5


def _position_zone(pos: Tuple[float, float]) -> str:
    """Convert screen position to zone description."""
    x = pos[0] if isinstance(pos, (tuple, list)) else 0.5
    if x < 0.33:
        return "left third"
    elif x < 0.66:
        return "center frame"
    else:
        return "right third"


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def _score_continuity(candidate: ReframeCandidate, prev: Optional[ShotSpatialState]) -> float:
    """Score how well a candidate preserves spatial continuity."""
    if not prev:
        return 0.7  # no previous = baseline

    score = 0.5
    prev_scale = prev.camera.shot_scale
    prop_scale = candidate.proposed_camera.shot_scale

    # Same scale = high continuity
    if prev_scale == prop_scale:
        score += 0.3
    # Adjacent scale = moderate
    elif abs(SHOT_SCALE_ORDER.index(prev_scale) - SHOT_SCALE_ORDER.index(prop_scale)) <= 1:
        score += 0.2
    # Big jump = low
    else:
        score += 0.05

    # Axis preservation
    if candidate.proposed_camera.axis_line == "preserved":
        score += 0.15

    # Strategy bonus
    if candidate.strategy == "continuity_match":
        score += 0.05

    return min(score, 1.0)


def _score_cinematic(
    candidate: ReframeCandidate,
    prev: Optional[ShotSpatialState],
    emotion_trajectory: str,
) -> float:
    """Score cinematic quality — visual variety, not just continuity."""
    score = 0.5

    if prev:
        prev_scale = prev.camera.shot_scale
        prop_scale = candidate.proposed_camera.shot_scale

        # Variety is good (different from prev = higher cinematic)
        if prev_scale != prop_scale:
            score += 0.2

        # Emotional match
        if emotion_trajectory == "rising" and candidate.strategy == "emotional_push":
            score += 0.2
        elif emotion_trajectory == "falling" and candidate.strategy == "action_widen":
            score += 0.2
        elif emotion_trajectory == "stable" and candidate.strategy == "continuity_match":
            score += 0.1

    # Dialogue gets reaction cut bonus
    if candidate.strategy == "reaction_cut":
        score += 0.15

    # OTS is classic cinema
    if candidate.strategy == "reveal_ots":
        score += 0.1

    return min(score, 1.0)


def _score_emotional_fit(
    candidate: ReframeCandidate, shot: dict, emotion_trajectory: str
) -> float:
    """Score how well the candidate fits the emotional moment."""
    score = 0.5
    emotion = shot.get("emotion", "neutral").lower()
    intensity = _estimate_emotion_intensity(emotion)

    # High intensity → close shots score better
    prop_idx = SHOT_SCALE_ORDER.index(candidate.proposed_camera.shot_scale)
    if intensity > 0.7 and prop_idx >= 4:  # close or tighter
        score += 0.3
    elif intensity < 0.4 and prop_idx <= 2:  # wide or wider
        score += 0.2
    else:
        score += 0.1

    # Trajectory match
    if emotion_trajectory == "rising" and candidate.strategy in ("emotional_push", "reaction_cut"):
        score += 0.15
    elif emotion_trajectory == "peak" and candidate.strategy == "emotional_push":
        score += 0.2

    return min(score, 1.0)


# ============================================================================
# VISION INTEGRATION — End-Frame Analysis Entry Point
# ============================================================================

def analyze_end_frame_spatial(
    shot: dict,
    vision_result: Optional[dict] = None,
    cast_map: dict = None,
) -> ShotSpatialState:
    """
    Analyze a shot's end frame and return spatial state.

    If vision_result is provided (from FAL/Florence-2), uses actual detections.
    Otherwise falls back to metadata-based heuristic extraction.

    This is the entry point that VisionAnalyst calls after frame analysis.
    """
    # Start with metadata-based baseline
    state = extract_spatial_state_from_metadata(shot, cast_map)

    if vision_result:
        # Upgrade with actual vision detections
        detections = vision_result.get("detections", [])
        caption = vision_result.get("caption", "")

        # Update character positions from face/person detections
        person_boxes = [d for d in detections if d.get("label") in ("person", "face")]
        for i, cs in enumerate(state.characters):
            if i < len(person_boxes):
                box = person_boxes[i]
                cx = (box.get("x1", 0) + box.get("x2", 1)) / 2
                cy = (box.get("y1", 0) + box.get("y2", 1)) / 2
                cs.screen_position = (round(cx, 3), round(cy, 3))

        # Update emotion from caption if available
        if caption:
            for cs in state.characters:
                if cs.name.lower() in caption.lower() or len(state.characters) == 1:
                    extracted_emotion = _extract_emotion_from_caption(caption)
                    if extracted_emotion:
                        cs.emotion_read = extracted_emotion

        # Compute frame hash for verification
        if vision_result.get("frame_hash"):
            state.frame_hash = vision_result["frame_hash"]

    return state


def _extract_emotion_from_caption(caption: str) -> str:
    """Extract dominant emotion from Florence-2 caption."""
    emotion_keywords = {
        "tense": "tension", "worried": "dread", "afraid": "fear",
        "angry": "anger", "sad": "grief", "calm": "calm",
        "happy": "hope", "smiling": "hope", "serious": "tension",
        "contemplat": "resignation", "shock": "revelation",
        "crying": "grief", "scared": "fear", "determined": "resolve",
    }
    caption_lower = caption.lower()
    for keyword, emotion in emotion_keywords.items():
        if keyword in caption_lower:
            return emotion
    return ""


# ============================================================================
# B-ROLL CONTINUITY SYSTEM — Texture/Color/Atmosphere Matching
# ============================================================================
# B-roll shots DON'T chain to character shots (no end-frame chain), but they
# DO need to match the SCENE's visual texture, color grade, and atmosphere.
# This section ensures B-roll gets master references for continuity.

@dataclass
class BRollContinuityState:
    """Visual continuity state for B-roll/atmosphere shots."""
    scene_id: str
    color_grade: str = ""  # from scene_anchor_system
    dominant_palette: List[str] = field(default_factory=list)  # e.g. ["desaturated", "cold blue", "amber highlight"]
    texture_keywords: List[str] = field(default_factory=list)  # e.g. ["wood grain", "dust particles", "candlelight"]
    atmosphere: str = ""
    location_master_url: str = ""  # reference image for location consistency
    time_of_day: str = ""
    weather_light: str = ""  # "overcast", "golden hour", "night practical"

    def to_dict(self) -> dict:
        return asdict(self)


# B-roll chaining rules — which types CAN chain to each other
BROLL_CHAIN_RULES = {
    # B-roll type → can chain to these types
    "establishing": [],  # never chains — sets new context
    "detail": ["detail", "insert"],  # detail→detail is OK (montage of objects)
    "insert": ["detail", "insert"],
    "atmosphere": ["atmosphere"],  # atmosphere→atmosphere for mood sequences
    "transition": [],  # transitions are bridges, don't chain
    "texture": ["texture", "detail"],  # texture montage is valid
    "cutaway": [],  # cutaways are independent
}

# Shot types that should NEVER chain to the previous shot
NEVER_CHAIN_TYPES = {
    "establishing", "master", "extreme_wide",
    "cutaway", "transition",
}

# Shot types that CAN chain to same-type B-roll (texture montages)
BROLL_MONTAGE_OK = {
    "detail", "insert", "texture", "atmosphere",
}


def should_chain_broll(current_shot: dict, previous_shot: dict) -> bool:
    """
    Determine if a B-roll shot should chain to the previous shot.

    Rules:
    1. B-roll NEVER chains to character shots (different visual context)
    2. B-roll CAN chain to other B-roll IF same scene AND compatible types
    3. Establishing/master shots NEVER chain
    4. Detail→detail montages ARE allowed (e.g., scanning across objects on desk)
    """
    # If current is not B-roll, use normal chaining rules
    if not (current_shot.get("_broll") or current_shot.get("_no_chain", False)):  # V26 DOCTRINE: suffixes are editorial, not runtime
        return False  # Not a B-roll decision — defer to normal chain logic

    # B-roll never chains to character shots
    if previous_shot.get("characters"):
        return False

    # Must be same scene
    if current_shot.get("scene_id") != previous_shot.get("scene_id"):
        return False

    # Check type compatibility
    curr_type = (current_shot.get("shot_type") or "").lower().replace(" ", "_")
    prev_type = (previous_shot.get("shot_type") or "").lower().replace(" ", "_")

    if curr_type in NEVER_CHAIN_TYPES or prev_type in NEVER_CHAIN_TYPES:
        return False

    # Both are montage-compatible types
    if curr_type in BROLL_MONTAGE_OK and prev_type in BROLL_MONTAGE_OK:
        return True

    return False


def extract_broll_continuity(
    scene_shots: List[dict],
    scene_manifest: dict = None,
    color_grade: str = "",
) -> BRollContinuityState:
    """
    Extract the visual continuity state that B-roll shots in a scene
    should match. Pulls from scene master reference, color grade anchors,
    and the dominant visual texture of character shots.
    """
    scene_id = ""
    textures = []
    atmospheres = []
    location_master = ""

    for s in scene_shots:
        scene_id = s.get("scene_id", scene_id)
        nano = (s.get("nano_prompt") or "").lower()

        # Extract texture keywords from character shots (B-roll should match)
        for tex in ["wood", "stone", "glass", "metal", "fabric", "dust",
                     "candle", "smoke", "rain", "fog", "shadow", "fire",
                     "silk", "leather", "velvet", "marble", "brick", "rust"]:
            if tex in nano:
                textures.append(tex)

        # Collect atmosphere
        atmo = s.get("emotion", "")
        if atmo:
            atmospheres.append(atmo)

        # Find location master
        if s.get("location_master_url") and not location_master:
            location_master = s["location_master_url"]

    # Derive dominant atmosphere
    from collections import Counter
    atmo_counts = Counter(atmospheres)
    dominant_atmo = atmo_counts.most_common(1)[0][0] if atmo_counts else "neutral"

    # Get scene-level info from manifest
    time_of_day = ""
    if scene_manifest and isinstance(scene_manifest, dict):
        time_of_day = scene_manifest.get("time_of_day", "")

    return BRollContinuityState(
        scene_id=scene_id,
        color_grade=color_grade,
        dominant_palette=_derive_palette(color_grade, dominant_atmo),
        texture_keywords=list(set(textures))[:8],
        atmosphere=dominant_atmo,
        location_master_url=location_master,
        time_of_day=time_of_day,
    )


def compile_broll_continuity_prompt(
    broll_state: BRollContinuityState,
    shot: dict,
) -> str:
    """
    Compile continuity instructions for a B-roll shot based on scene state.
    This ensures B-roll matches the scene's visual texture and color.
    """
    parts = ["SCENE VISUAL CONTINUITY:"]

    if broll_state.color_grade:
        parts.append(f"Color grade: {broll_state.color_grade}")

    if broll_state.dominant_palette:
        parts.append(f"Palette: {', '.join(broll_state.dominant_palette)}")

    if broll_state.texture_keywords:
        parts.append(f"Match textures: {', '.join(broll_state.texture_keywords[:4])}")

    if broll_state.atmosphere:
        parts.append(f"Atmosphere: {broll_state.atmosphere}")

    if broll_state.time_of_day:
        parts.append(f"Time: {broll_state.time_of_day}")

    parts.append("Ensure visual consistency with surrounding character shots.")
    parts.append("NO bright/warm drift if scene is cold. NO cold drift if scene is warm.")

    return "\n".join(parts)


def _derive_palette(color_grade: str, atmosphere: str) -> List[str]:
    """Derive color palette from grade + atmosphere."""
    palette_map = {
        "dread": ["desaturated", "cold blue shadow", "sickly amber highlight"],
        "tension": ["muted contrast", "steel grey", "warm practicals only"],
        "calm": ["soft natural", "warm diffuse", "pastel earth tones"],
        "hope": ["warm golden", "gentle contrast", "open highlights"],
        "grief": ["desaturated", "cool blue", "low contrast"],
        "anger": ["hot contrast", "deep red shadows", "blown highlights"],
        "suspense": ["dark low-key", "selective warm", "deep shadows"],
    }
    return palette_map.get(atmosphere, ["neutral grade", "balanced tones"])


# ============================================================================
# VISION-INTEGRATED END-FRAME ANALYSIS
# ============================================================================
# Uses the actual vision_service.py (Florence-2, DINOv2, ArcFace) to
# extract real spatial data from rendered frames.

def vision_analyze_end_frame(
    frame_path: str,
    shot: dict,
    cast_map: dict = None,
    location_master_path: str = None,
) -> dict:
    """
    Full vision analysis of an end frame using ATLAS vision service.
    Returns structured spatial data that gets stored in ContinuityMemory.

    Uses:
    - Florence-2 (FAL): detailed caption + object detection
    - DINOv2: location similarity vs master
    - ArcFace: identity verification vs cast headshots

    This is the REAL vision path (costs FAL credits).
    The metadata-based extract_spatial_state_from_metadata() is the FREE path.
    """
    result = {
        "caption": "",
        "detections": [],
        "identity_scores": {},
        "location_score": 0.0,
        "frame_hash": "",
        "provider": "none",
    }

    # Compute frame hash for cache/verification
    if os.path.exists(frame_path):
        with open(frame_path, "rb") as f:
            result["frame_hash"] = hashlib.sha256(f.read()).hexdigest()[:16]

    try:
        from tools.vision_service import get_vision_service
        vs = get_vision_service("auto")

        # 1. Caption (Florence-2) — describes what's in the frame
        caption_result = vs.caption(frame_path)
        result["caption"] = caption_result.get("caption", "")
        result["provider"] = caption_result.get("provider", "unknown")

        # 2. Identity scoring per character
        characters = shot.get("characters") or []
        if cast_map and characters:
            for char_name in characters:
                char_data = cast_map.get(char_name, {})
                if isinstance(char_data, dict):
                    ref_url = char_data.get("headshot_url", "")
                    if ref_url and os.path.exists(ref_url):
                        id_result = vs.score_identity(
                            frame_path, ref_url,
                            expected_face_count=len(characters)
                        )
                        result["identity_scores"][char_name] = {
                            "similarity": id_result.get("face_similarity", 0),
                            "detected": id_result.get("face_detected", False),
                        }

        # 3. Location similarity
        if location_master_path and os.path.exists(location_master_path):
            loc_result = vs.score_location(frame_path, location_master_path)
            result["location_score"] = loc_result.get("location_similarity", 0)

        # 4. Empty room detection (for B-roll/atmosphere shots)
        if not characters:
            empty_result = vs.detect_empty_room(frame_path, characters)
            result["empty_room"] = not empty_result.get("has_person", False)

    except ImportError:
        logger.warning("Vision service not available — using metadata-only analysis")
    except Exception as e:
        logger.warning(f"Vision analysis failed: {e} — using metadata fallback")

    return result


# ============================================================================
# PARALLEL RENDERING AWARENESS
# ============================================================================
# When rendering multiple scenes in parallel, each scene has its OWN
# continuity chain. But within a scene, shots MUST be sequential if they
# need end-frame chaining. This module tracks which shots can be parallel
# vs which must wait for the previous shot's end frame.

@dataclass
class RenderDependency:
    """Describes a shot's rendering dependency."""
    shot_id: str
    scene_id: str
    depends_on: Optional[str] = None  # shot_id this depends on (for end-frame)
    can_parallel: bool = True  # True = can render alongside other scenes
    chain_position: int = 0  # 0 = independent, 1+ = position in chain
    is_scene_anchor: bool = False  # True = first shot in scene (generates master)
    is_broll: bool = False
    render_group: str = ""  # shots in same group must be sequential

    def to_dict(self) -> dict:
        return asdict(self)


def build_render_dependency_graph(
    shots: List[dict],
) -> List[RenderDependency]:
    """
    Build a dependency graph for parallel rendering.

    Rules:
    1. Different scenes CAN render in parallel (each has own master)
    2. Within a scene, chained shots MUST be sequential (need end-frame)
    3. B-roll within a scene CAN render parallel to character chain
    4. Scene anchor (first shot) must render first
    5. Independent shots (inserts, cutaways) can render parallel

    Returns ordered list of RenderDependency objects.
    """
    from collections import defaultdict
    scenes = defaultdict(list)
    for s in shots:
        scenes[s.get("scene_id", "?")].append(s)

    dependencies = []

    for scene_id in sorted(scenes.keys()):
        scene_shots = scenes[scene_id]
        chain_position = 0
        last_chained_id = None

        for i, shot in enumerate(scene_shots):
            sid = shot.get("shot_id", "?")
            is_broll = bool(shot.get("_broll", False) or shot.get("_no_chain", False))  # V26 DOCTRINE: suffixes are editorial, not runtime
            is_no_chain = shot.get("_no_chain", False)
            has_chars = len(shot.get("characters") or []) > 0
            shot_type = (shot.get("shot_type") or "").lower()

            dep = RenderDependency(
                shot_id=sid,
                scene_id=scene_id,
                render_group=f"scene_{scene_id}",
            )

            # First shot in scene = anchor
            if i == 0:
                dep.is_scene_anchor = True
                dep.chain_position = 0
                dep.depends_on = None
                dep.can_parallel = True  # can start with other scene anchors
                chain_position = 1
                last_chained_id = sid

            # B-roll = independent within scene
            elif is_broll or is_no_chain:
                dep.is_broll = True
                dep.chain_position = 0
                dep.depends_on = None  # doesn't need previous end-frame
                dep.can_parallel = True
                dep.render_group = f"scene_{scene_id}_broll"

            # Insert/cutaway/establishing = independent
            elif shot_type in ("insert", "cutaway", "establishing", "detail"):
                dep.chain_position = 0
                dep.depends_on = None
                dep.can_parallel = True
                dep.render_group = f"scene_{scene_id}_independent"

            # Character shot that needs chaining
            elif has_chars and last_chained_id:
                dep.chain_position = chain_position
                dep.depends_on = last_chained_id
                dep.can_parallel = False  # must wait for previous
                dep.render_group = f"scene_{scene_id}_chain"
                chain_position += 1
                last_chained_id = sid

            # Default: assume it chains
            else:
                dep.chain_position = chain_position
                dep.depends_on = last_chained_id
                dep.can_parallel = last_chained_id is None
                dep.render_group = f"scene_{scene_id}_chain"
                chain_position += 1
                last_chained_id = sid

            dependencies.append(dep)

    return dependencies


def get_parallel_render_groups(
    dependencies: List[RenderDependency],
) -> Dict[str, List[str]]:
    """
    Group shots into parallel-safe render batches.

    Returns dict of group_name → [shot_ids] where shots within
    a group must be sequential, but groups can run in parallel.
    """
    groups: Dict[str, List[str]] = {}
    for dep in dependencies:
        group = dep.render_group or f"ungrouped_{dep.scene_id}"
        if group not in groups:
            groups[group] = []
        groups[group].append(dep.shot_id)
    return groups


def estimate_parallel_render_time(
    dependencies: List[RenderDependency],
    frame_time_s: float = 8.0,
    video_time_s: float = 25.0,  # weighted avg of Kling + LTX
) -> dict:
    """
    Estimate render time with parallel execution vs sequential.

    Returns:
        sequential_time: if everything runs one-by-one
        parallel_time: if parallel groups run simultaneously
        speedup: ratio
    """
    groups = get_parallel_render_groups(dependencies)
    per_shot_time = frame_time_s + video_time_s

    # Sequential: every shot one by one
    total_shots = len(dependencies)
    sequential = total_shots * per_shot_time

    # Parallel: longest group determines total time
    group_times = {}
    for group_name, shot_ids in groups.items():
        group_times[group_name] = len(shot_ids) * per_shot_time

    parallel = max(group_times.values()) if group_times else sequential

    return {
        "sequential_seconds": sequential,
        "parallel_seconds": parallel,
        "speedup": round(sequential / max(parallel, 1), 2),
        "groups": len(groups),
        "longest_chain": max(len(v) for v in groups.values()) if groups else 0,
        "independent_shots": sum(1 for d in dependencies if d.can_parallel),
    }
