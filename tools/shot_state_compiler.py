#!/usr/bin/env python3
"""
ATLAS V26.1 — SHOT STATE COMPILER
==================================
Compiles raw shot_plan.json shots into structured ShotState objects.

Every shot compiles to a structured state object (not just prompts) with fields for:
project_id, scene_id, shot_id, render_mode, engine_preference, location_id, location_zone,
cast_ids, speaker, listener, wardrobe_ids, camera_axis, camera_side, framing, lens, shot_type,
world_positions, screen_positions, eyelines, motion_class, dialogue_phase, emotion_state,
continuity_from, approved_anchor_frame, chain_source_policy, fallback_policy, locked_prompt,
scene_locked, ledger_tags.

This is NOT just a data transfer object — it carries the render contract.

Usage:
    from tools.shot_state_compiler import ShotStateCompiler, CompileContext
    compiler = ShotStateCompiler(project_path)
    context = compiler.make_context(project_id, cast_map, scene_manifest, wardrobe_data, story_bible)
    shot_state = compiler.compile_shot(shot_dict, context, previous_shot_id="001_000A")
    scene_states = compiler.compile_scene("001", shots, context)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class CompileContext:
    """Carries all lookup data needed during shot compilation.

    This context is built once per scene and passed to all shot compilers
    to avoid repeated file I/O and lookups.
    """
    project_id: str
    project_path: str
    cast_map: Dict[str, Any] = field(default_factory=dict)
    scene_manifest: Dict[str, Any] = field(default_factory=dict)
    wardrobe_data: Dict[str, Any] = field(default_factory=dict)
    story_bible: Dict[str, Any] = field(default_factory=dict)
    previous_shot_id: Optional[str] = None
    render_mode_default: str = "auto"  # "ltx" | "kling" | "auto" | "dual"


@dataclass
class ShotState:
    """Fully populated structural state for a single shot.

    This carries EVERYTHING downstream modules need:
    - Render contract (engine, mode, resolution)
    - Blocking (characters, positions, eyelines)
    - Prompts (nano, ltx, negative)
    - References (character refs, location refs)
    - Continuity (chain source, previous shot)
    - Validation (blocking violations, ledger tags)
    """
    # Identity
    project_id: str
    scene_id: str
    shot_id: str

    # Engine & Render Contract
    render_mode: str = "auto"  # "ltx" | "kling" | "auto" | "dual"
    engine_preference: str = "ltx"  # Which to prefer if both available
    authority_tier: str = "production"  # "hero" | "production" | "establishing" | "broll"
    resolution: str = "1K"  # "1K" | "2K" | "4K"

    # Location
    location_id: str = ""
    location_zone: str = ""  # Sub-location like "GRAND_FOYER" within scene location

    # Cast & Dialogue
    cast_ids: List[str] = field(default_factory=list)  # Character names in shot
    speaker: Optional[str] = None  # Who is speaking (if any)
    listener: Optional[str] = None  # Who is listening (if any)
    wardrobe_ids: Dict[str, str] = field(default_factory=dict)  # char → look_id

    # Camera
    camera_axis: str = "A"  # "A" | "B" | "C" (coverage axis)
    camera_side: str = "center"  # "left" | "center" | "right" (180° rule)
    framing: str = "wide"  # "wide" | "medium" | "close" | "ECU"
    lens: str = "35mm"  # Focal length descriptor
    shot_type: str = "wide"  # "wide" | "medium" | "close" | "OTS" | "two-shot" etc
    focal_length: str = "35mm"

    # Blocking
    world_positions: Dict[str, str] = field(default_factory=dict)  # char → "standing at altar"
    screen_positions: Dict[str, str] = field(default_factory=dict)  # char → "left" | "center" | "right"
    eyelines: Dict[str, str] = field(default_factory=dict)  # char → target ("camera" | "partner" | "off-screen-left")

    # Motion & Performance
    motion_class: str = "static"  # "static" | "subtle" | "moderate" | "dynamic" | "extreme"
    dialogue_phase: str = "none"  # "none" | "speaking" | "listening" | "reaction"
    dialogue_text: str = ""
    emotion_state: str = "neutral"
    emotion_intensity: float = 0.0  # 0.0-1.0

    # Continuity
    continuity_from: Optional[str] = None  # shot_id of previous shot (for chaining)
    approved_anchor_frame: Optional[str] = None  # Path to approved first-frame image
    chain_source_policy: str = "fresh"  # "approved_endframe" | "approved_anchor" | "location_master" | "fresh"
    fallback_policy: str = "degrade_safe"  # "degrade_safe" | "halt" | "skip"

    # Prompts
    nano_prompt: str = ""
    ltx_prompt: str = ""
    negative_prompt: str = ""
    locked_prompt: bool = False  # True if prompt cannot be re-enriched

    # Scene Context
    scene_locked: bool = False  # True if scene plan is locked (before first shot generates)

    # Coverage & Render Behavior
    coverage_role: str = "A_GEOGRAPHY"  # "A_GEOGRAPHY" | "B_ACTION" | "C_EMOTION"
    is_broll: bool = False
    is_chain_candidate: bool = True  # Can this shot be part of an end-frame chain?

    # Quality & Authority
    render_ready: bool = False

    # Ledger Tags
    blocking_violations: List[str] = field(default_factory=list)  # Detected issues
    ledger_tags: List[str] = field(default_factory=list)  # Tracking tags for doctrine ledger

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# SHOT STATE COMPILER
# ============================================================================

class ShotStateCompiler:
    """Compiles raw shot_plan entries into structured ShotState objects."""

    MOTION_CLASS_KEYWORDS = {
        "static": ["stillness", "frozen", "motionless", "still", "no motion"],
        "subtle": ["subtle", "micro", "small", "gentle", "slight", "minimal"],
        "moderate": ["moves", "walks", "turns", "gestures", "shifts", "reaches", "leans"],
        "dynamic": ["runs", "jumps", "falls", "attacks", "explosive", "rapid", "swift"],
        "extreme": ["frantic", "chaotic", "violent", "intense", "frenetic"],
    }

    DIALOGUE_PHASE_KEYWORDS = {
        "speaking": ["speaks", "says", "dialogue", "voiceover", "monologue", "declares"],
        "listening": ["listens", "hears", "attends", "absorbs", "reacts to"],
        "reaction": ["reacts", "responds", "grimaces", "nods", "looks away"],
    }

    EMOTION_KEYWORDS = {
        "dread": ["dread", "fear", "terror", "panic", "horror"],
        "tension": ["tension", "suspense", "conflict", "struggle"],
        "grief": ["grief", "sorrow", "mourning", "loss", "despair"],
        "hope": ["hope", "uplift", "resolve", "triumph"],
        "confusion": ["confused", "disoriented", "bewildered"],
        "rage": ["rage", "anger", "fury", "wrath"],
        "resignation": ["resignation", "acceptance", "surrender"],
        "determination": ["determined", "resolved", "focused"],
    }

    def __init__(self, project_path: str):
        """Initialize compiler with project path."""
        self.project_path = Path(project_path)

    def make_context(
        self,
        project_id: str,
        cast_map: Dict[str, Any],
        scene_manifest: Dict[str, Any],
        wardrobe_data: Dict[str, Any],
        story_bible: Dict[str, Any],
        render_mode_default: str = "auto",
    ) -> CompileContext:
        """Create a CompileContext for batch compilation."""
        return CompileContext(
            project_id=project_id,
            project_path=str(self.project_path),
            cast_map=cast_map,
            scene_manifest=scene_manifest,
            wardrobe_data=wardrobe_data,
            story_bible=story_bible,
            render_mode_default=render_mode_default,
        )

    def compile_shot(
        self,
        shot: Dict[str, Any],
        context: CompileContext,
        previous_shot_id: Optional[str] = None,
    ) -> ShotState:
        """Compile a single raw shot dict into a ShotState.

        Args:
            shot: Raw shot dict from shot_plan.json
            context: CompileContext with project data
            previous_shot_id: shot_id of the previous shot (for continuity)

        Returns:
            ShotState: Fully populated structured state
        """
        shot_id = shot.get("shot_id", "UNKNOWN")
        scene_id = shot.get("scene_id", "")

        state = ShotState(
            project_id=context.project_id,
            scene_id=scene_id,
            shot_id=shot_id,
        )

        # Engine & Render
        state.render_mode = context.render_mode_default
        state.engine_preference = "ltx"
        state.locked_prompt = shot.get("locked_prompt", False)
        state.scene_locked = shot.get("scene_locked", False)

        # Location
        location = shot.get("location", "")
        state.location_id = location
        state.location_zone = self._extract_zone(location)

        # Cast & Dialogue
        state.cast_ids = shot.get("characters", [])
        state.speaker = self._infer_speaker(shot, context)
        state.listener = self._infer_listener(shot, state.speaker)
        state.dialogue_text = shot.get("dialogue_text", "")

        # Wardrobe
        state.wardrobe_ids = self._resolve_wardrobe(state.cast_ids, scene_id, context)

        # Camera & Framing
        state.camera_axis = shot.get("camera_axis", "A")
        state.camera_side = shot.get("camera_side", "center")
        state.shot_type = shot.get("type", shot.get("shot_type", "wide"))
        state.framing = shot.get("shot_size", "WS")
        state.lens = shot.get("lens_specs", "35mm")
        state.focal_length = self._extract_focal_length(state.lens)

        # Authority & Coverage
        state.coverage_role = shot.get("coverage_role", "A_GEOGRAPHY")
        state.authority_tier = self._infer_authority_tier(state.shot_type, state.coverage_role)
        state.resolution = self._authority_tier_to_resolution(state.authority_tier)
        state.is_broll = shot.get("b_roll", False)
        state.is_chain_candidate = self._is_chain_candidate(shot, state.is_broll)

        # Blocking
        state.world_positions = self._extract_positions(shot)
        state.screen_positions = self._extract_screen_positions(shot)
        state.eyelines = self._extract_eyelines(shot, context)

        # Motion & Performance
        state.motion_class = self._infer_motion_class(shot)
        state.dialogue_phase = self._infer_dialogue_phase(shot, state.dialogue_text)
        state.emotion_state = self._infer_emotion(shot)
        state.emotion_intensity = self._infer_emotion_intensity(shot)

        # Continuity
        state.continuity_from = previous_shot_id
        state.approved_anchor_frame = shot.get("approved_anchor_frame")
        state.chain_source_policy = self._determine_chain_source(
            state.is_broll, state.is_chain_candidate, shot_id
        )
        state.fallback_policy = "degrade_safe"

        # Prompts
        state.nano_prompt = shot.get("nano_prompt", "")
        state.ltx_prompt = shot.get("ltx_motion_prompt", "")
        state.negative_prompt = shot.get("negative_prompt", "")

        # Validation
        state.blocking_violations = self._detect_violations(state, context)
        state.ledger_tags = self._generate_ledger_tags(state)
        state.render_ready = len(state.blocking_violations) == 0

        return state

    def compile_scene(
        self,
        scene_id: str,
        shots: List[Dict[str, Any]],
        context: CompileContext,
    ) -> List[ShotState]:
        """Compile all shots in a scene, setting continuity_from links.

        Args:
            scene_id: The scene ID
            shots: List of raw shot dicts
            context: CompileContext with project data

        Returns:
            List[ShotState]: Compiled shots in order
        """
        compiled = []
        previous_shot_id = None

        for shot in shots:
            if shot.get("scene_id") != scene_id:
                continue

            state = self.compile_shot(shot, context, previous_shot_id)
            compiled.append(state)
            previous_shot_id = state.shot_id

        return compiled

    # ========================================================================
    # INFERENCE HELPERS
    # ========================================================================

    def _extract_zone(self, location: str) -> str:
        """Extract sub-location zone from location string.

        e.g., "RAVENCROFT MANOR - RITUAL ROOM" → "RITUAL ROOM"
        """
        if " - " in location:
            return location.split(" - ", 1)[1]
        return ""

    def _extract_focal_length(self, lens: str) -> str:
        """Extract numeric focal length from lens spec.

        e.g., "f/3.4 depth, 35mm" → "35mm"
        """
        match = re.search(r'(\d+)mm', lens)
        if match:
            return f"{match.group(1)}mm"
        return "35mm"

    def _infer_speaker(self, shot: Dict[str, Any], context: CompileContext) -> Optional[str]:
        """Infer who is speaking from dialogue or shot intent."""
        # Priority 1: Explicit speaker annotation
        if shot.get("speaker"):
            return shot.get("speaker")

        # Priority 2: Dialogue text + character list
        dialogue = shot.get("dialogue_text", "")
        characters = shot.get("characters", [])
        if dialogue and characters:
            # If only one character, they speak
            if len(characters) == 1:
                return characters[0]
            # If multiple, check story bible for speaker assignment
            speaker = self._lookup_beat_speaker(shot.get("beat_id"), context)
            if speaker:
                return speaker

        return None

    def _infer_listener(self, shot: Dict[str, Any], speaker: Optional[str]) -> Optional[str]:
        """Infer who is listening (if not the speaker)."""
        characters = shot.get("characters", [])
        if speaker and len(characters) > 1:
            for char in characters:
                if char != speaker:
                    return char
        return None

    def _lookup_beat_speaker(self, beat_id: Optional[str], context: CompileContext) -> Optional[str]:
        """Look up speaker from story bible beat."""
        if not beat_id or not context.story_bible:
            return None

        for scene in context.story_bible.get("scenes", []):
            for beat in scene.get("beats", []):
                if beat.get("beat_id") == beat_id:
                    return beat.get("speaker")
        return None

    def _resolve_wardrobe(
        self,
        characters: List[str],
        scene_id: str,
        context: CompileContext,
    ) -> Dict[str, str]:
        """Resolve wardrobe look_ids for characters in this scene."""
        wardrobe = {}
        wardrobe_data = context.wardrobe_data

        for char in characters:
            key = f"{char}::{scene_id}"
            if key in wardrobe_data:
                wardrobe[char] = wardrobe_data[key].get("look_id", "")

        return wardrobe

    def _infer_motion_class(self, shot: Dict[str, Any]) -> str:
        """Infer motion class from prompt and description."""
        text = (shot.get("nano_prompt", "") + " " + shot.get("description", "")).lower()

        for motion_class, keywords in self.MOTION_CLASS_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return motion_class

        return "static"

    def _infer_dialogue_phase(self, shot: Dict[str, Any], dialogue_text: str) -> str:
        """Infer dialogue phase from dialogue text and description."""
        text = (shot.get("nano_prompt", "") + " " + dialogue_text).lower()

        for phase, keywords in self.DIALOGUE_PHASE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return phase

        return "none"

    def _infer_emotion(self, shot: Dict[str, Any]) -> str:
        """Infer emotion from prompt and description."""
        text = (shot.get("nano_prompt", "") + " " + shot.get("description", "")).lower()

        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return emotion

        return "neutral"

    def _infer_emotion_intensity(self, shot: Dict[str, Any]) -> float:
        """Infer emotion intensity (0.0-1.0) from prompt language."""
        text = (shot.get("nano_prompt", "") + " " + shot.get("description", "")).lower()

        intensity_markers = {
            "extreme": 1.0,
            "intense": 0.9,
            "powerful": 0.8,
            "strong": 0.7,
            "subtle": 0.3,
            "minimal": 0.2,
        }

        for marker, intensity in intensity_markers.items():
            if marker in text:
                return intensity

        return 0.5

    def _infer_authority_tier(self, shot_type: str, coverage_role: str) -> str:
        """Determine authority tier (quality contract) for shot."""
        # Hero shots: close-ups, ECU, MCU, dialogue speakers
        if shot_type in ["close", "ECU", "MCU", "CU"]:
            return "hero"

        # Production: medium, OTS, two-shot
        if shot_type in ["medium", "OTS", "two-shot", "MS"]:
            return "production"

        # Establishing: wide, master
        if shot_type in ["wide", "master", "WS", "establishing"]:
            return "establishing"

        # B-roll: detail, insert, cutaway
        if shot_type in ["detail", "insert", "cutaway", "B-roll"]:
            return "broll"

        return "production"

    def _authority_tier_to_resolution(self, tier: str) -> str:
        """Map authority tier to resolution."""
        tier_map = {
            "hero": "2K",
            "production": "1K",
            "establishing": "1K",
            "broll": "1K",
        }
        return tier_map.get(tier, "1K")

    def _is_chain_candidate(self, shot: Dict[str, Any], is_broll: bool) -> bool:
        """Determine if shot is eligible for end-frame chaining."""
        # B-roll never chains to character shots
        if is_broll:
            return False

        # V.O.-only shots don't chain
        if shot.get("_child_vo"):
            return False

        # Intercut shots don't chain across locations
        if shot.get("_intercut"):
            return False

        # Must have characters or explicit approval
        has_chars = bool(shot.get("characters"))
        has_approval = shot.get("chain_approved", False)

        return has_chars or has_approval

    def _determine_chain_source(
        self,
        is_broll: bool,
        is_chain_candidate: bool,
        shot_id: str,
    ) -> str:
        """Determine the source policy for this shot's first frame."""
        if is_broll:
            return "fresh"

        if not is_chain_candidate:
            return "fresh"

        # Establishing shots use location master
        if shot_id.endswith("A"):
            return "location_master"

        # Chained character shots use approved end-frame
        if is_chain_candidate:
            return "approved_endframe"

        return "fresh"

    def _extract_positions(self, shot: Dict[str, Any]) -> Dict[str, str]:
        """Extract world positions from blocking description."""
        blocking = shot.get("character_blocking", "")
        positions = {}

        # Very basic extraction from blocking text
        if blocking:
            # This is a placeholder — real implementation would parse blocking more thoroughly
            for char in shot.get("characters", []):
                if char.lower() in blocking.lower():
                    positions[char] = blocking

        return positions

    def _extract_screen_positions(self, shot: Dict[str, Any]) -> Dict[str, str]:
        """Extract screen positions (left/center/right) for characters."""
        positions = {}
        characters = shot.get("characters", [])

        # Distribute characters across screen
        if len(characters) == 1:
            positions[characters[0]] = "center"
        elif len(characters) == 2:
            positions[characters[0]] = "left"
            positions[characters[1]] = "right"
        elif len(characters) >= 3:
            positions[characters[0]] = "left"
            positions[characters[1]] = "center"
            positions[characters[2]] = "right"

        return positions

    def _extract_eyelines(self, shot: Dict[str, Any], context: CompileContext) -> Dict[str, str]:
        """Extract eyeline targets for characters."""
        eyelines = {}
        characters = shot.get("characters", [])
        dialogue = shot.get("dialogue_text", "")

        # Single character → look at camera
        if len(characters) == 1:
            eyelines[characters[0]] = "camera"

        # Multiple characters → look at each other
        elif len(characters) == 2:
            eyelines[characters[0]] = characters[1]
            eyelines[characters[1]] = characters[0]

        # V.O. shot → look off-screen
        elif not characters and dialogue:
            eyelines["UNKNOWN"] = "off-screen-left"

        return eyelines

    def _detect_violations(self, state: ShotState, context: CompileContext) -> List[str]:
        """Detect blocking and consistency violations."""
        violations = []

        # Missing character reference in cast_map
        for char in state.cast_ids:
            if char not in context.cast_map:
                violations.append(f"Character '{char}' not in cast_map")

        # Dialogue without speaker attribution
        if state.dialogue_text and not state.speaker:
            violations.append("Dialogue present but no speaker identified")

        # No characters but dialogue
        if state.dialogue_text and not state.cast_ids:
            violations.append("Dialogue present but no characters in shot")

        return violations

    def _generate_ledger_tags(self, state: ShotState) -> List[str]:
        """Generate tracking tags for doctrine ledger."""
        tags = []

        if state.speaker:
            tags.append(f"speaker:{state.speaker}")

        if state.dialogue_text:
            tags.append("has_dialogue")

        if state.is_broll:
            tags.append("broll")

        if not state.is_chain_candidate:
            tags.append("no_chain")

        if state.emotion_intensity > 0.7:
            tags.append("high_emotion")

        if state.authority_tier == "hero":
            tags.append("hero_shot")

        return tags
