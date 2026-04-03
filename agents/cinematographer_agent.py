#!/usr/bin/env python3
"""
Cinematographer Agent - Behavior Tree-Driven Shot Selection

Replaces fixed pattern-based shot generation with dynamic, context-driven
cinematography that simulates human directorial intuition.

Key Components:
1. Behavior Tree (BT) for event-based shot selection
2. Adaptive shot count based on scene complexity (Omega_i)
3. Quantum Evaluator for ensemble prompt scoring
4. Emotional state + Director Mindset injection
5. Disentangled camera (extrinsics) vs photography (intrinsics) controls
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math

# V3.2: Add parent directory to path for Config import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config

# ==============================================================================
# SEMANTIC PROMPT JSON V2 SCHEMA
# ==============================================================================

@dataclass
class CameraExtrinsics:
    """Camera position and movement (extrinsic parameters)."""
    shot_size: str = "MS"  # WS, MS, MCU, CU, ECU
    focal_length_mm: int = 35
    height_m: float = 1.6
    pitch_angle_deg: float = 0.0  # Negative = high angle, Positive = low angle
    roll_angle_deg: float = 0.0  # Dutch angle
    move_type: str = "locked"  # locked, dolly_in, dolly_out, pan, tilt, crane, tracking
    move_speed_m_per_s: float = 0.08  # Slow = cinematic

    def to_dict(self) -> Dict:
        return {
            "shot_size": self.shot_size,
            "focal_length_mm": self.focal_length_mm,
            "height_m": self.height_m,
            "pitch_angle_deg": self.pitch_angle_deg,
            "roll_angle_deg": self.roll_angle_deg,
            "move_type": self.move_type,
            "move_speed_m_per_s": self.move_speed_m_per_s
        }


@dataclass
class PhotographyIntrinsics:
    """Photographic/optical parameters (intrinsic parameters)."""
    bokeh_K: float = 0.4  # Blur intensity coefficient (0-1)
    refocused_disparity_df: float = 0.1  # Depth of field control
    shutter_speed_S: str = "1/48"  # Motion blur control
    color_temp_K: int = 4500  # Kelvin (3200=tungsten, 5600=daylight, 4100=cool)
    lighting_ratio: float = 2.0  # Key:fill ratio (higher = more dramatic)
    contrast: str = "high"  # low, medium, high
    grain: str = "subtle"  # none, subtle, heavy

    def to_dict(self) -> Dict:
        return {
            "bokeh_K": self.bokeh_K,
            "refocused_disparity_df": self.refocused_disparity_df,
            "shutter_speed_S": self.shutter_speed_S,
            "color_temp_K": self.color_temp_K,
            "lighting_ratio": self.lighting_ratio,
            "contrast": self.contrast,
            "grain": self.grain
        }


@dataclass
class DirectorMindset:
    """Director's psychological/emotional intent for the shot."""
    predator_threshold: float = 0.0  # 0-1, how much viewer feels hunted
    shadows_closing_in: bool = False
    viewer_as_prey: bool = False
    isolation_intensity: float = 0.0  # 0-1, how alone/small subject feels
    tension_level: float = 0.0  # 0-1, overall tension
    intimacy_level: float = 0.0  # 0-1, emotional closeness
    power_dynamic: str = "neutral"  # dominant, submissive, neutral, shifting

    def to_dict(self) -> Dict:
        return {
            "predator_threshold": self.predator_threshold,
            "shadows_closing_in": self.shadows_closing_in,
            "viewer_as_prey": self.viewer_as_prey,
            "isolation_intensity": self.isolation_intensity,
            "tension_level": self.tension_level,
            "intimacy_level": self.intimacy_level,
            "power_dynamic": self.power_dynamic
        }


@dataclass
class ActorControl:
    """Per-actor control conditioning."""
    identity_hash: str = ""
    pose_source: Optional[str] = None  # Path to pose reference
    controlnet: List[str] = field(default_factory=lambda: ["openpose"])
    emotional_state: str = ""
    blocking_position: str = ""  # left_third, center, right_third

    def to_dict(self) -> Dict:
        return {
            "identity_hash": self.identity_hash,
            "pose_source": self.pose_source,
            "controlnet": self.controlnet,
            "emotional_state": self.emotional_state,
            "blocking_position": self.blocking_position
        }


@dataclass
class AssetGridMetadata:
    """
    14-slot Asset Grid integration metadata.
    Determines which assets from the grid should be used for this specific shot.

    Slot semantics:
    - Slots 1-2: Primary characters (face references)
    - Slots 3-5: Additional characters
    - Slots 6-9: Location depths (wide_establishing, medium_coverage, detail_insert, overhead_anchor)
    - Slots 10-11: Props
    - Slot 12: Previous shot (auto-populated)
    - Slot 13: Frame blocking (reserved)
    - Slot 14: Quality anchor
    """
    characters_in_frame: List[str] = field(default_factory=list)
    primary_subject: Optional[str] = None  # Main character focus for this shot
    location_depth: str = "medium_coverage"  # Which location ref to use
    props_visible: List[str] = field(default_factory=list)
    quality_anchor: str = "TONE_ANCHOR"
    use_previous_shot: bool = False
    character_prominence: Dict[str, str] = field(default_factory=dict)  # character -> "full", "partial", "background"

    def to_dict(self) -> Dict:
        return {
            "characters_in_frame": self.characters_in_frame,
            "primary_subject": self.primary_subject,
            "location_depth": self.location_depth,
            "props_visible": self.props_visible,
            "quality_anchor": self.quality_anchor,
            "use_previous_shot": self.use_previous_shot,
            "character_prominence": self.character_prominence
        }


@dataclass
class SemanticPromptJSON:
    """
    The unified data contract for computational cinematography.
    Bridges high-level creative vision with low-level technical specs.
    """
    shot_id: str
    scene_metadata: Dict[str, Any]
    director_profile: str
    director_mindset: DirectorMindset
    events: List[str]
    camera: CameraExtrinsics
    photography: PhotographyIntrinsics
    actors: Dict[str, ActorControl] = field(default_factory=dict)
    asset_grid: AssetGridMetadata = field(default_factory=AssetGridMetadata)
    style_anchor: str = "cinematic, grounded, high_dynamic_range"
    consistency_pipeline_active: bool = True
    visual_prompt_string: str = ""
    ltx_duration_seconds: int = 8
    shot_role: str = "coverage"
    composition_tag: str = "rule_of_thirds"
    narrative_intent: str = ""
    emotional_turn: str = ""
    key_dramatic_question: str = ""

    def to_dict(self) -> Dict:
        return {
            "shot_id": self.shot_id,
            "scene_metadata": self.scene_metadata,
            "director_profile": self.director_profile,
            "director_mindset": self.director_mindset.to_dict(),
            "events": self.events,
            "director_knobs": {
                "camera": self.camera.to_dict(),
                "photography": self.photography.to_dict()
            },
            "actors": {k: v.to_dict() for k, v in self.actors.items()},
            "asset_grid": self.asset_grid.to_dict(),
            "generative_engine": {
                "style_anchor": self.style_anchor,
                "consistency_pipeline_active": self.consistency_pipeline_active
            },
            "output_assets": {
                "visual_prompt_string": self.visual_prompt_string
            },
            "ltx_duration_seconds": self.ltx_duration_seconds,
            "shot_role": self.shot_role,
            "composition_tag": self.composition_tag,
            "narrative_intent": self.narrative_intent,
            "emotional_turn": self.emotional_turn,
            "key_dramatic_question": self.key_dramatic_question
        }


# ==============================================================================
# BEHAVIOR TREE NODES
# ==============================================================================

class BTStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BTNode:
    """Base class for Behavior Tree nodes."""
    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        raise NotImplementedError


class BTSelector(BTNode):
    """Selector node - returns first successful child."""
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        for child in self.children:
            status, shots = child.tick(context)
            if status == BTStatus.SUCCESS:
                return status, shots
        return BTStatus.FAILURE, []


class BTSequence(BTNode):
    """Sequence node - all children must succeed, accumulates shots."""
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        all_shots = []
        for child in self.children:
            status, shots = child.tick(context)
            if status == BTStatus.FAILURE:
                return BTStatus.FAILURE, []
            all_shots.extend(shots)
        return BTStatus.SUCCESS, all_shots


class BTCondition(BTNode):
    """Condition node - checks a predicate."""
    def __init__(self, predicate: callable):
        self.predicate = predicate

    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        if self.predicate(context):
            return BTStatus.SUCCESS, []
        return BTStatus.FAILURE, []


class BTAction(BTNode):
    """Action node - generates shots based on context."""
    def __init__(self, action_fn: callable):
        self.action_fn = action_fn

    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        shots = self.action_fn(context)
        return BTStatus.SUCCESS, shots


class BTAccumulator(BTNode):
    """
    Accumulator node - runs ALL children and accumulates shots from all successful branches.
    Unlike BTSelector which stops at first match, this collects shots from EVERY matching condition.
    This enables comprehensive cinematography coverage (establishing + dialogue + reactions + inserts).
    """
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, context: Dict) -> Tuple[BTStatus, List[Dict]]:
        all_shots = []
        any_success = False
        for child in self.children:
            status, shots = child.tick(context)
            if status == BTStatus.SUCCESS:
                any_success = True
                all_shots.extend(shots)
        # Return success if ANY child succeeded, with accumulated shots
        return (BTStatus.SUCCESS, all_shots) if any_success else (BTStatus.FAILURE, [])


# ==============================================================================
# PROFILE SAMPLER - Weighted Distribution Sampling
# ==============================================================================

class ProfileSampler:
    """
    Samples camera settings from director profile distributions.
    Ensures variety by using weighted random selection instead of hardcoded values.

    V15 CODEX A3: Uses deterministic seeding for reproducibility.
    Same project + scene + beat → same camera decisions
    """

    def __init__(self, profile: Dict):
        self.profile = profile
        self.camera_policy = profile.get("camera_policy", {})
        self.lighting_policy = profile.get("lighting_policy", {})
        self.pov_policy = profile.get("story_pov_policy", {})
        self.coverage_policy = profile.get("coverage_policy", {})
        self.rhythm_policy = profile.get("rhythm_policy", {})
        # V15 CODEX A3: Use instance-level RNG for deterministic seeding
        self._rng = random.Random()
        self._seed_counter = 0

    def set_context_seed(self, project_id: str, scene_id: str = "", beat_id: str = "", shot_index: int = 0):
        """
        V15 CODEX A3: Set deterministic seed from context.
        Same context → same random choices → reproducible results.
        """
        seed_string = f"{project_id}:{scene_id}:{beat_id}:{shot_index}"
        hash_bytes = hashlib.sha256(seed_string.encode()).digest()
        seed = int.from_bytes(hash_bytes[:8], byteorder='big')
        self._rng = random.Random(seed)
        self._seed_counter = shot_index

    def sample_focal_length(self, role: str = "coverage") -> int:
        """Sample focal length from preferred list or distribution."""
        preferred = self.camera_policy.get("preferred_focal_lengths_mm", [35])
        avoid = self.camera_policy.get("avoid_focal_lengths_mm", [])

        # Filter out avoided focal lengths
        valid = [fl for fl in preferred if fl not in avoid]
        if not valid:
            valid = [35]  # Fallback

        # Role-based weighting
        if role in ["establishing", "isolation_wide", "atmosphere_dread"]:
            # Favor wider for establishing
            weights = [1.5 if fl <= 28 else 1.0 for fl in valid]
        elif role in ["reaction", "terror_reaction", "contemplative"]:
            # Favor longer for close-ups
            weights = [1.5 if fl >= 40 else 1.0 for fl in valid]
        else:
            weights = [1.0] * len(valid)

        # V15 CODEX A3: Use instance RNG for determinism
        return self._rng.choices(valid, weights=weights)[0]

    def sample_shot_size(self, role_hint: str = "coverage") -> str:
        """Sample shot size from distribution."""
        dist = self.camera_policy.get("shot_size_distribution", {})
        if not dist:
            dist = {"WS": 0.25, "MS": 0.40, "CU": 0.25, "ECU": 0.10}

        sizes = list(dist.keys())
        weights = list(dist.values())

        # Role-based override
        if role_hint in ["establishing", "isolation_wide"]:
            return "WS"
        elif role_hint in ["reaction", "terror_reaction", "ritual_detail"]:
            return "CU"

        # V15 CODEX A3: Use instance RNG for determinism
        return self._rng.choices(sizes, weights=weights)[0]

    def sample_movement(self, role_hint: str = "coverage") -> str:
        """Sample camera movement from distribution."""
        dist = self.camera_policy.get("movement_bias", {})
        if not dist:
            dist = {"static": 0.3, "slow_dolly": 0.4, "slow_pan_tilt": 0.2, "handheld": 0.1}

        moves = list(dist.keys())
        weights = list(dist.values())

        # Filter out zero-weight options
        valid_moves = [(m, w) for m, w in zip(moves, weights) if w > 0]
        if not valid_moves:
            return "locked"

        moves, weights = zip(*valid_moves)
        # V15 CODEX A3: Use instance RNG for determinism
        return self._rng.choices(list(moves), weights=list(weights))[0]

    def sample_angle(self) -> Tuple[float, float]:
        """Sample camera angle (pitch, roll) from distribution."""
        dist = self.camera_policy.get("angle_bias", {})
        if not dist:
            return (0.0, 0.0)

        angles = list(dist.keys())
        weights = list(dist.values())

        # Filter out zero-weight
        valid = [(a, w) for a, w in zip(angles, weights) if w > 0]
        if not valid:
            return (0.0, 0.0)

        angles, weights = zip(*valid)
        # V15 CODEX A3: Use instance RNG for determinism
        selected = self._rng.choices(list(angles), weights=list(weights))[0]

        # Map to actual angles
        angle_map = {
            "eye_level": (0.0, 0.0),
            "slight_low": (5.0, 0.0),    # Low angle looking up
            "slight_high": (-10.0, 0.0),  # High angle looking down
            "dutch": (0.0, 8.0)           # Tilted horizon
        }
        return angle_map.get(selected, (0.0, 0.0))

    def sample_color_temp(self) -> int:
        """Sample color temperature from lighting policy."""
        base = self.lighting_policy.get("base_color_temp_K", 4500)
        variation = self.lighting_policy.get("color_temp_variation_K", 300)
        # V15 CODEX A3: Use instance RNG for determinism
        return self._rng.randint(base - variation, base + variation)

    def sample_lighting_ratio(self) -> float:
        """Sample lighting ratio from policy range."""
        range_vals = self.lighting_policy.get("lighting_ratio_range", [1.5, 2.5])
        if len(range_vals) >= 2:
            # V15 CODEX A3: Use instance RNG for determinism
            return round(self._rng.uniform(range_vals[0], range_vals[1]), 1)
        return 2.0

    def get_contrast(self) -> str:
        """Get contrast from profile."""
        return self.lighting_policy.get("contrast_bias", "medium_high")

    def get_grain(self) -> str:
        """Get grain from profile."""
        return self.profile.get("global_aesthetic", {}).get("grain", "subtle")

    def is_pov_subjective(self) -> bool:
        """Determine if this shot should be subjective POV."""
        prob = self.pov_policy.get("subjective_probability", 0.3)
        # V15 CODEX A3: Use instance RNG for determinism
        return self._rng.random() < prob


# ==============================================================================
# ASSET GRID INTELLIGENCE - Determines assets per shot
# ==============================================================================

# Location depth mapping based on shot size
SHOT_SIZE_TO_LOCATION_DEPTH = {
    "WS": "wide_establishing",
    "EWS": "wide_establishing",
    "FS": "wide_establishing",
    "MS": "medium_coverage",
    "MWS": "medium_coverage",
    "MCU": "medium_coverage",
    "CU": "detail_insert",
    "ECU": "detail_insert",
    "XCU": "detail_insert"
}

# Shot roles that typically show no/minimal characters
ENVIRONMENT_SHOT_ROLES = {
    "establishing", "atmosphere_dread", "location_detail", "insert",
    "cutaway", "transition", "environment"
}

# Shot roles focused on specific characters
CHARACTER_FOCUS_ROLES = {
    "participant_A": 0,       # First character
    "participant_B": 1,       # Second character
    "reaction_A": 0,
    "reaction_B": 1,
    "close_A": 0,
    "close_B": 1,
    "OTS_A_favoring_B": 1,    # Over-shoulder of A, favoring B
    "OTS_B_favoring_A": 0,    # Over-shoulder of B, favoring A
}


def determine_shot_assets(
    shot_role: str,
    shot_size: str,
    scene_characters: List[str],
    beat_props: List[str],
    beat: Dict,
    is_first_shot: bool = False
) -> AssetGridMetadata:
    """
    Intelligently determine which assets from the 14-slot grid to use for this shot.

    This is the "cinematographer intelligence" that decides:
    - Which characters appear in frame (not all scene characters in every shot!)
    - Which location depth reference to use (wide/medium/detail)
    - Which props are visible
    - Character prominence levels

    Args:
        shot_role: Role like "establishing", "participant_A", "reaction_B"
        shot_size: Camera shot size like "WS", "MS", "CU"
        scene_characters: All characters in the scene
        beat_props: Props mentioned in this beat
        beat: Full beat data for additional context
        is_first_shot: Whether this is the first shot in a sequence

    Returns:
        AssetGridMetadata with intelligent asset selection
    """
    asset_grid = AssetGridMetadata()

    # 1. Determine location depth from shot size
    asset_grid.location_depth = SHOT_SIZE_TO_LOCATION_DEPTH.get(shot_size, "medium_coverage")

    # 2. Determine characters in frame based on shot role
    if shot_role in ENVIRONMENT_SHOT_ROLES:
        # Environment/establishing shots: no characters or very small in frame
        asset_grid.characters_in_frame = []
        asset_grid.primary_subject = None
        asset_grid.character_prominence = {}

    elif shot_role in CHARACTER_FOCUS_ROLES:
        # Character-specific shots
        char_idx = CHARACTER_FOCUS_ROLES[shot_role]
        if char_idx < len(scene_characters):
            focus_char = scene_characters[char_idx]
            asset_grid.characters_in_frame = [focus_char]
            asset_grid.primary_subject = focus_char

            # Determine prominence based on shot size
            if shot_size in ["CU", "ECU", "XCU", "MCU"]:
                asset_grid.character_prominence[focus_char] = "full"
            else:
                asset_grid.character_prominence[focus_char] = "partial"

            # For OTS shots, include the "over" character as background
            if "OTS" in shot_role:
                other_idx = 1 if char_idx == 0 else 0
                if other_idx < len(scene_characters):
                    other_char = scene_characters[other_idx]
                    if other_char not in asset_grid.characters_in_frame:
                        asset_grid.characters_in_frame.append(other_char)
                    asset_grid.character_prominence[other_char] = "background"

    elif shot_role in ["two_shot", "dialogue_coverage", "master"]:
        # Two-shot or master: all scene characters
        asset_grid.characters_in_frame = list(scene_characters[:2])
        if scene_characters:
            asset_grid.primary_subject = scene_characters[0]
        for char in asset_grid.characters_in_frame:
            asset_grid.character_prominence[char] = "full" if shot_size in ["MS", "MCU"] else "partial"

    elif shot_role == "group_wide":
        # Group shot: all characters, smaller prominence
        asset_grid.characters_in_frame = list(scene_characters)
        if scene_characters:
            asset_grid.primary_subject = scene_characters[0]
        for char in asset_grid.characters_in_frame:
            asset_grid.character_prominence[char] = "background"

    else:
        # Default coverage: include all characters with varying prominence
        asset_grid.characters_in_frame = list(scene_characters)
        if scene_characters:
            asset_grid.primary_subject = scene_characters[0]
        for i, char in enumerate(asset_grid.characters_in_frame):
            if i == 0:
                asset_grid.character_prominence[char] = "full" if shot_size in ["CU", "MCU"] else "partial"
            else:
                asset_grid.character_prominence[char] = "partial" if shot_size in ["MS", "MWS"] else "background"

    # 3. Determine props visibility based on shot size and beat content
    if beat_props:
        if shot_size in ["CU", "ECU", "XCU"]:
            # Close-ups: show hero props prominently
            asset_grid.props_visible = beat_props[:2]  # Max 2 hero props
        elif shot_size in ["MS", "MCU"]:
            # Medium shots: show props if relevant
            asset_grid.props_visible = beat_props[:1]  # 1 prop
        else:
            # Wide shots: props may be visible but not focus
            asset_grid.props_visible = []

    # 4. Check beat for dialogue to infer speaker (but NOT for environment shots)
    dialogue = beat.get("dialogue") or beat.get("dialogue_text")
    if dialogue and not asset_grid.primary_subject and scene_characters:
        # Only infer speaker if this isn't an environment/establishing shot
        if shot_role not in ENVIRONMENT_SHOT_ROLES:
            # If there's dialogue and no subject set, first character is likely speaker
            asset_grid.primary_subject = scene_characters[0]
            if scene_characters[0] not in asset_grid.characters_in_frame:
                asset_grid.characters_in_frame.insert(0, scene_characters[0])

    # 5. Set previous shot usage (not first shot in sequence)
    asset_grid.use_previous_shot = not is_first_shot

    # 6. Default quality anchor
    asset_grid.quality_anchor = "TONE_ANCHOR"

    return asset_grid


# ==============================================================================
# SCENE CONTEXT ANALYZER
# ==============================================================================

class SceneContextAnalyzer:
    """Analyzes scene/beat to extract events and emotional context."""

    @staticmethod
    def extract_events(beat: Dict, scene: Dict) -> List[str]:
        """Extract cinematographically relevant events from beat."""
        events = []
        text = json.dumps(beat).lower() + json.dumps(scene).lower()

        # Character movement events
        if any(kw in text for kw in ["approach", "walks toward", "moves closer", "enters"]):
            events.append("character_approach")
        if any(kw in text for kw in ["retreat", "backs away", "flees", "runs", "escape"]):
            events.append("character_retreat")
        if any(kw in text for kw in ["arrives", "enters room", "comes in"]):
            events.append("character_arrival")

        # Dialogue events
        if beat.get("dialogue") or "says" in text or "speaks" in text:
            chars = scene.get("characters_present", [])
            if len(chars) >= 2:
                events.append("dialogue_two_hander")
            else:
                events.append("dialogue_monologue")

        # Emotional events
        if any(kw in text for kw in ["confronts", "argues", "accuses", "threatens"]):
            events.append("confrontation")
        if any(kw in text for kw in ["discovers", "finds", "realizes", "reveals"]):
            events.append("revelation")
        if any(kw in text for kw in ["alone", "isolated", "solitary", "waits"]):
            events.append("isolation")

        # Horror/supernatural events
        if any(kw in text for kw in ["ghost", "apparition", "spirit", "haunting"]):
            events.append("supernatural_presence")
        if any(kw in text for kw in ["ritual", "ceremony", "summoning", "chanting"]):
            events.append("ritual_ceremony")

        # Environmental events
        if any(kw in text for kw in ["establishing", "exterior", "location", "manor looming"]):
            events.append("establishing_location")

        # World opening / first-impression beats
        if any(kw in text for kw in ["world opening", "world-opening", "[world opening]", "house introduction", "first impression of manor"]):
            events.append("world_opening")

        # Prop still-life plates
        if any(kw in text for kw in ["[insert detail]", "[prop plate]", "still-life", "still life", "object centered detail"]):
            events.append("prop_plate")

        # Off-camera audio emphasis
        if any(kw in text for kw in ["(o.s.)", "offscreen", "off-screen", "off camera", "off-camera"]):
            events.append("off_camera_audio")

        # Shadow figure silhouettes
        if any(kw in text for kw in ["shadow figure", "shadowy figure", "silhouette on wall", "shadows stretch", "shadow on wall"]):
            events.append("shadow_silhouette")

        return events if events else ["default_coverage"]

    @staticmethod
    def calculate_complexity_omega(beat: Dict, scene: Dict) -> float:
        """
        Calculate scene complexity score Omega_i (0-1).
        Higher = more complex = more coverage needed.
        """
        omega = 0.3  # Base complexity

        # Dialogue complexity
        dialogue = beat.get("dialogue", "")
        if dialogue:
            words = len(dialogue.split())
            omega += min(0.2, words / 200)  # Long dialogue = more complex

        # Character count
        chars = scene.get("characters_present", [])
        omega += min(0.15, len(chars) * 0.05)

        # Emotional intensity
        text = json.dumps(beat).lower()
        emotional_keywords = ["terror", "grief", "rage", "despair", "revelation", "confrontation"]
        for kw in emotional_keywords:
            if kw in text:
                omega += 0.1
                break

        # Action density
        action_keywords = ["runs", "fights", "chases", "escapes", "attacks"]
        for kw in action_keywords:
            if kw in text:
                omega += 0.1
                break

        return min(1.0, omega)

    @staticmethod
    def extract_emotional_state(beat: Dict, scene: Dict) -> Dict[str, Any]:
        """Extract emotional context for narrative fidelity."""
        text = json.dumps(beat).lower()

        # Detect emotional turn
        emotional_turn = ""
        if "but then" in text or "suddenly" in text:
            emotional_turn = "reversal"
        elif any(kw in text for kw in ["realizes", "discovers"]):
            emotional_turn = "revelation"
        elif any(kw in text for kw in ["escalates", "intensifies"]):
            emotional_turn = "escalation"

        # Detect dramatic question
        key_question = ""
        if "will" in text and "?" in text:
            key_question = "uncertainty"
        elif any(kw in text for kw in ["danger", "threat", "risk"]):
            key_question = "survival"
        elif any(kw in text for kw in ["truth", "secret", "hidden"]):
            key_question = "revelation"

        # Actor internal states
        actor_states = {}
        for char in scene.get("characters_present", []):
            char_lower = char.lower()
            if "fear" in text or "terror" in text:
                actor_states[char] = ["fearful", "trembling"]
            elif "anger" in text or "rage" in text:
                actor_states[char] = ["angry", "aggressive"]
            elif "grief" in text or "crying" in text:
                actor_states[char] = ["grieving", "vulnerable"]
            else:
                actor_states[char] = ["neutral", "observant"]

        return {
            "emotional_turn": emotional_turn,
            "key_dramatic_question": key_question,
            "actor_internal_states": actor_states
        }


# ==============================================================================
# SHOT GENERATORS (Behavior Tree Actions)
# ==============================================================================

def generate_establishing_shots(context: Dict) -> List[Dict]:
    """Generate establishing/location shots with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl = sampler.sample_focal_length("establishing")
        move = sampler.sample_movement("establishing")
        pitch, roll = sampler.sample_angle()
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
    else:
        fl, move, pitch, roll = 24, "slow_crane_descending", -10, 0
        color_temp, ratio = 4100, 2.5

    return [{
        "role": "establishing",
        "camera": CameraExtrinsics(
            shot_size="WS",
            focal_length_mm=fl,
            height_m=2.0,
            pitch_angle_deg=pitch if pitch != 0 else -10,
            roll_angle_deg=roll,
            move_type=move if move != "static" else "slow_crane_descending",
            move_speed_m_per_s=0.05
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.2,
            color_temp_K=color_temp,
            lighting_ratio=ratio
        ),
        "composition": "symmetrical_or_leading_lines",
        "include_characters": False,
        "duration_seconds": 10,
        "ltx_duration": 16
    }]


def generate_dialogue_two_shot(context: Dict) -> List[Dict]:
    """Generate coverage for two-character dialogue with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        # Sample varied focal lengths for each shot
        fl_master = sampler.sample_focal_length("dialogue_master")
        fl_ots = sampler.sample_focal_length("ots_coverage")
        fl_reaction = sampler.sample_focal_length("reaction")
        move_master = sampler.sample_movement("dialogue_master")
        color_temp = sampler.sample_color_temp()
        pitch_a, roll_a = sampler.sample_angle()
        pitch_b, roll_b = sampler.sample_angle()
    else:
        fl_master, fl_ots, fl_reaction = 35, 50, 75
        move_master = "slow_dolly"
        color_temp = 4500
        pitch_a, roll_a, pitch_b, roll_b = 0, 0, 0, 0

    return [
        # Master two-shot
        {
            "role": "dialogue_master",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_master,
                pitch_angle_deg=pitch_a,
                roll_angle_deg=roll_a,
                move_type=move_master,
                move_speed_m_per_s=0.03
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.5,
                color_temp_K=color_temp
            ),
            "composition": "two_shot_balanced",
            "include_characters": True,
            "duration_seconds": 8,
            "ltx_duration": 14
        },
        # OTS favoring speaker A
        {
            "role": "ots_speaker_a",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_ots,
                pitch_angle_deg=pitch_b,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.6,
                color_temp_K=color_temp,
                refocused_disparity_df=0.15
            ),
            "composition": "over_shoulder_right_third",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 10
        },
        # OTS favoring speaker B
        {
            "role": "ots_speaker_b",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_ots,
                pitch_angle_deg=pitch_a,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.6,
                color_temp_K=color_temp,
                refocused_disparity_df=0.15
            ),
            "composition": "over_shoulder_left_third",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 10
        },
        # Reaction close-up
        {
            "role": "reaction",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_reaction,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.7,
                color_temp_K=color_temp
            ),
            "composition": "rule_of_thirds_left",
            "include_characters": True,
            "duration_seconds": 4,
            "ltx_duration": 6
        }
    ]


def generate_confrontation_shots(context: Dict) -> List[Dict]:
    """Generate shots for confrontational scenes with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_master = sampler.sample_focal_length("tension_master")
        fl_power = sampler.sample_focal_length("power_shot")
        fl_vuln = sampler.sample_focal_length("vulnerability")
        move = sampler.sample_movement("tension_master")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
    else:
        fl_master, fl_power, fl_vuln = 35, 75, 50
        move = "slow_dolly_in"
        color_temp = 4500
        ratio = 3.0

    return [
        # Tension master
        {
            "role": "tension_master",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_master,
                move_type=move if move != "static" else "slow_dolly_in",
                move_speed_m_per_s=0.02
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.4,
                color_temp_K=color_temp,
                lighting_ratio=ratio,
                contrast="high"
            ),
            "composition": "two_shot_tension",
            "include_characters": True,
            "duration_seconds": 8,
            "ltx_duration": 14
        },
        # Power shot (dominant character)
        {
            "role": "power_shot",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_power,
                pitch_angle_deg=5,  # Low angle = power
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.65,
                color_temp_K=color_temp,
                lighting_ratio=ratio + 0.5
            ),
            "composition": "centered_dominant",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 12
        },
        # Vulnerability shot (subordinate)
        {
            "role": "vulnerability",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_vuln,
                pitch_angle_deg=-10,  # High angle = vulnerability
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.5,
                color_temp_K=color_temp,
                lighting_ratio=2.0
            ),
            "composition": "off_center_lower",
            "include_characters": True,
            "duration_seconds": 5,
            "ltx_duration": 8
        }
    ]


def generate_isolation_shots(context: Dict) -> List[Dict]:
    """Generate shots emphasizing character isolation with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_wide = sampler.sample_focal_length("isolation_wide")
        fl_close = sampler.sample_focal_length("contemplative")
        move = sampler.sample_movement("isolation_wide")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
        pitch, roll = sampler.sample_angle()
    else:
        fl_wide, fl_close = 24, 85
        move = "slow_pull_back"
        color_temp = 4000
        ratio = 2.5
        pitch, roll = 0, 0

    return [
        # Wide isolation
        {
            "role": "isolation_wide",
            "camera": CameraExtrinsics(
                shot_size="WS",
                focal_length_mm=fl_wide,
                pitch_angle_deg=pitch,
                roll_angle_deg=roll,
                move_type=move if move != "static" else "slow_pull_back",
                move_speed_m_per_s=0.04
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.2,
                color_temp_K=color_temp,
                lighting_ratio=ratio
            ),
            "composition": "small_figure_vast_space",
            "include_characters": True,
            "duration_seconds": 10,
            "ltx_duration": 20  # Long hold for isolation
        },
        # Contemplative close
        {
            "role": "contemplative",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_close,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.75,
                color_temp_K=color_temp,
                refocused_disparity_df=0.2
            ),
            "composition": "profile_left_third",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 12
        }
    ]


def generate_supernatural_shots(context: Dict) -> List[Dict]:
    """Generate shots for supernatural/horror moments with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_dread = sampler.sample_focal_length("atmosphere_dread")
        fl_terror = sampler.sample_focal_length("terror_reaction")
        fl_glimpse = sampler.sample_focal_length("supernatural_glimpse")
        move = sampler.sample_movement("atmosphere_dread")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
    else:
        fl_dread, fl_terror, fl_glimpse = 24, 85, 50
        move = "imperceptible_drift"
        color_temp = 3800
        ratio = 4.0

    return [
        # Dread atmosphere
        {
            "role": "atmosphere_dread",
            "camera": CameraExtrinsics(
                shot_size="WS",
                focal_length_mm=fl_dread,
                move_type=move if move in ["slow_dolly", "slow_pan_tilt"] else "imperceptible_drift",
                move_speed_m_per_s=0.01
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.3,
                color_temp_K=color_temp,
                lighting_ratio=ratio,
                contrast="high"
            ),
            "composition": "empty_space_dread",
            "include_characters": False,
            "duration_seconds": 10,
            "ltx_duration": 18
        },
        # Witness terror
        {
            "role": "terror_reaction",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_terror,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.8,
                color_temp_K=color_temp
            ),
            "composition": "face_in_shadow",
            "include_characters": True,
            "duration_seconds": 4,
            "ltx_duration": 6
        },
        # Fleeting glimpse
        {
            "role": "supernatural_glimpse",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_glimpse,
                move_type="subtle_handheld"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.4,
                color_temp_K=color_temp,
                shutter_speed_S="1/30"  # Slight blur
            ),
            "composition": "partial_frame",
            "include_characters": False,
            "duration_seconds": 3,
            "ltx_duration": 4
        }
    ]


def generate_ritual_shots(context: Dict) -> List[Dict]:
    """Generate shots for ritual/ceremony scenes with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        # Sample varied focal lengths for each shot role
        fl_estab = sampler.sample_focal_length("ritual_establishing")
        fl_part = sampler.sample_focal_length("ritual_participant")
        fl_detail = sampler.sample_focal_length("ritual_detail")
        move_estab = sampler.sample_movement("ritual_establishing")
        move_part = sampler.sample_movement("ritual_participant")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
        pitch1, roll1 = sampler.sample_angle()
        pitch2, roll2 = sampler.sample_angle()
    else:
        fl_estab, fl_part, fl_detail = 24, 85, 100
        move_estab = "slow_crane_descending"
        move_part = "slow_push"
        color_temp = 3500
        ratio = 5.0
        pitch1, roll1, pitch2, roll2 = -15, 0, 0, 0

    return [
        # Ritual establishing
        {
            "role": "ritual_establishing",
            "camera": CameraExtrinsics(
                shot_size="WS",
                focal_length_mm=fl_estab,
                pitch_angle_deg=pitch1 if pitch1 != 0 else -15,
                roll_angle_deg=roll1,
                move_type=move_estab if move_estab != "static" else "slow_crane_descending",
                move_speed_m_per_s=0.03
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.25,
                color_temp_K=color_temp,
                lighting_ratio=ratio
            ),
            "composition": "symmetrical_dread",
            "include_characters": True,
            "duration_seconds": 10,
            "ltx_duration": 16
        },
        # Participant close
        {
            "role": "ritual_participant",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_part,
                pitch_angle_deg=pitch2,
                roll_angle_deg=roll2,
                move_type=move_part if move_part != "static" else "slow_push",
                move_speed_m_per_s=0.02
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.7,
                color_temp_K=color_temp - 300  # Slightly warmer for close-up
            ),
            "composition": "face_in_shadow",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 10
        },
        # Ritual detail
        {
            "role": "ritual_detail",
            "camera": CameraExtrinsics(
                shot_size="ECU",
                focal_length_mm=fl_detail,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.9,
                color_temp_K=color_temp - 200,
                refocused_disparity_df=0.25
            ),
            "composition": "object_centered",
            "include_characters": False,
            "duration_seconds": 4,
            "ltx_duration": 6
        }
    ]


def generate_approach_shots(context: Dict) -> List[Dict]:
    """Generate shots for character approach/movement with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_track = sampler.sample_focal_length("approach_tracking")
        fl_pov = sampler.sample_focal_length("pov_adjacent")
        move = sampler.sample_movement("approach_tracking")
        color_temp = sampler.sample_color_temp()
        pitch, roll = sampler.sample_angle()
    else:
        fl_track, fl_pov = 35, 50
        move = "tracking_alongside"
        color_temp = 4500
        pitch, roll = 0, 0

    return [
        # Tracking approach
        {
            "role": "approach_tracking",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_track,
                pitch_angle_deg=pitch,
                roll_angle_deg=roll,
                move_type=move if move != "static" else "tracking_alongside",
                move_speed_m_per_s=0.1
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.4,
                color_temp_K=color_temp
            ),
            "composition": "rule_of_thirds_leading",
            "include_characters": True,
            "duration_seconds": 8,
            "ltx_duration": 14
        },
        # POV adjacent
        {
            "role": "pov_adjacent",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_pov,
                move_type="handheld_follow"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.5,
                color_temp_K=color_temp
            ),
            "composition": "back_of_head_profile",
            "include_characters": True,
            "duration_seconds": 6,
            "ltx_duration": 10
        }
    ]


def generate_revelation_shots(context: Dict) -> List[Dict]:
    """Generate shots for discovery/revelation moments with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_approach = sampler.sample_focal_length("discovery_approach")
        fl_react = sampler.sample_focal_length("revelation_reaction")
        fl_reveal = sampler.sample_focal_length("reveal_object")
        move = sampler.sample_movement("discovery_approach")
        color_temp = sampler.sample_color_temp()
        pitch, roll = sampler.sample_angle()
    else:
        fl_approach, fl_react, fl_reveal = 35, 85, 50
        move = "slow_push"
        color_temp = 4500
        pitch, roll = 0, 0

    return [
        # Approach to discovery
        {
            "role": "discovery_approach",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_approach,
                pitch_angle_deg=pitch,
                roll_angle_deg=roll,
                move_type=move if move != "static" else "slow_push",
                move_speed_m_per_s=0.03
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.4,
                color_temp_K=color_temp
            ),
            "composition": "approaching_subject",
            "include_characters": True,
            "duration_seconds": 8,
            "ltx_duration": 14
        },
        # Reaction punch
        {
            "role": "revelation_reaction",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_react,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.75,
                color_temp_K=color_temp
            ),
            "composition": "face_revelation",
            "include_characters": True,
            "duration_seconds": 3,
            "ltx_duration": 4  # Short punch
        },
        # Reveal detail
        {
            "role": "reveal_object",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_reveal,
                move_type="reveal_pan"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.5,
                color_temp_K=color_temp
            ),
            "composition": "object_revealed",
            "include_characters": False,
            "duration_seconds": 6,
            "ltx_duration": 10
        }
    ]


def generate_default_coverage(context: Dict) -> List[Dict]:
    """Generate default balanced coverage with profile-sampled variety."""
    sampler = context.get("sampler")

    if sampler:
        fl_master = sampler.sample_focal_length("master")
        fl_coverage = sampler.sample_focal_length("coverage")
        fl_insert = sampler.sample_focal_length("insert")
        move = sampler.sample_movement("master")
        color_temp = sampler.sample_color_temp()
        pitch, roll = sampler.sample_angle()
    else:
        fl_master, fl_coverage, fl_insert = 35, 50, 85
        move = "slow_crane_descending"
        color_temp = 4500
        pitch, roll = 0, 0

    return [
        # Master
        {
            "role": "master",
            "camera": CameraExtrinsics(
                shot_size="MS",
                focal_length_mm=fl_master,
                pitch_angle_deg=pitch,
                roll_angle_deg=roll,
                move_type=move if move != "static" else "slow_crane_descending"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.4,
                color_temp_K=color_temp
            ),
            "composition": "balanced_composition",
            "include_characters": True,
            "duration_seconds": 7,
            "ltx_duration": 12
        },
        # Coverage
        {
            "role": "coverage",
            "camera": CameraExtrinsics(
                shot_size="MCU",
                focal_length_mm=fl_coverage,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.5,
                color_temp_K=color_temp
            ),
            "composition": "rule_of_thirds",
            "include_characters": True,
            "duration_seconds": 5,
            "ltx_duration": 10
        },
        # Insert
        {
            "role": "insert",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl_insert,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.6,
                color_temp_K=color_temp
            ),
            "composition": "detail_insert",
            "include_characters": False,
            "duration_seconds": 4,
            "ltx_duration": 6
        }
    ]


def generate_broll_atmosphere(context: Dict) -> List[Dict]:
    """Generate atmosphere b-roll shots - no characters, pure location/mood."""
    sampler = context.get("sampler")

    if sampler:
        fl = sampler.sample_focal_length("establishing")
        move = sampler.sample_movement("establishing")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
    else:
        fl, move = 24, "slow_pan_tilt"
        color_temp, ratio = 4100, 3.0

    return [{
        "role": "broll_atmosphere",
        "camera": CameraExtrinsics(
            shot_size="WS",
            focal_length_mm=fl,
            move_type=move if move != "static" else "slow_pan_tilt",
            move_speed_m_per_s=0.02
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.2,
            color_temp_K=color_temp,
            lighting_ratio=ratio
        ),
        "composition": "atmospheric_wide",
        "include_characters": False,
        "duration_seconds": 8,
        "ltx_duration": 14
    }]


def generate_insert_cutaways(context: Dict) -> List[Dict]:
    """Generate detail insert/cutaway shots - props, hands, objects."""
    sampler = context.get("sampler")

    if sampler:
        fl = sampler.sample_focal_length("insert")
        color_temp = sampler.sample_color_temp()
    else:
        fl = 100
        color_temp = 4500

    return [
        # Detail insert
        {
            "role": "insert_detail",
            "camera": CameraExtrinsics(
                shot_size="ECU",
                focal_length_mm=fl,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.85,
                color_temp_K=color_temp,
                refocused_disparity_df=0.3
            ),
            "composition": "macro_detail",
            "include_characters": False,
            "duration_seconds": 3,
            "ltx_duration": 4
        },
        # Contextual cutaway
        {
            "role": "cutaway",
            "camera": CameraExtrinsics(
                shot_size="CU",
                focal_length_mm=fl - 15,
                move_type="locked"
            ),
            "photography": PhotographyIntrinsics(
                bokeh_K=0.6,
                color_temp_K=color_temp
            ),
            "composition": "object_in_context",
            "include_characters": False,
            "duration_seconds": 4,
            "ltx_duration": 6
        }
    ]


def generate_world_opening_shots(context: Dict) -> List[Dict]:
    """Static world-opening plates for manor or environment introductions."""
    sampler = context.get("sampler")
    if sampler:
        fl = sampler.sample_focal_length("world_opening")
        color_temp = sampler.sample_color_temp()
        ratio = sampler.sample_lighting_ratio()
    else:
        fl = 24
        color_temp = 4300
        ratio = 3.0

    return [{
        "role": "world_opening",
        "b_roll": True,
        "suppress_mindset": True,
        "camera": CameraExtrinsics(
            shot_size="WS",
            focal_length_mm=fl,
            move_type="locked",
            move_speed_m_per_s=0.0
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.1,
            color_temp_K=color_temp,
            lighting_ratio=ratio
        ),
        "composition": "architectural_balance",
        "include_characters": False,
        "duration_seconds": 8,
        "ltx_duration": 12,
        "descriptor": "static world-opening plate showcasing the manor and its surroundings"
    }]


def generate_prop_plate_shots(context: Dict) -> List[Dict]:
    """Still-life prop plates for ritual objects or key details."""
    sampler = context.get("sampler")
    if sampler:
        fl = sampler.sample_focal_length("insert")
        color_temp = sampler.sample_color_temp()
    else:
        fl = 90
        color_temp = 4400

    beat = context.get("beat", {})
    scene = context.get("scene", {})
    props = beat.get("props") or scene.get("scene_props") or scene.get("allowed_props") or []
    focus_prop = props[0] if props else "ritual object"

    return [{
        "role": "prop_plate",
        "b_roll": True,
        "suppress_mindset": True,
        "camera": CameraExtrinsics(
            shot_size="ECU",
            focal_length_mm=fl,
            move_type="locked"
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.9,
            color_temp_K=color_temp,
            refocused_disparity_df=0.35
        ),
        "composition": "still_life",
        "include_characters": False,
        "duration_seconds": 4,
        "ltx_duration": 6,
        "descriptor": f"still-life insert highlighting {focus_prop}"
    }]


def generate_off_camera_audio_plate(context: Dict) -> List[Dict]:
    """Hold on an empty frame while off-camera audio plays."""
    sampler = context.get("sampler")
    if sampler:
        fl = sampler.sample_focal_length("atmosphere")
        color_temp = sampler.sample_color_temp()
    else:
        fl = 35
        color_temp = 4000

    beat = context.get("beat", {})
    audio_note = ""
    dialogue = beat.get("dialogue")
    if isinstance(dialogue, str) and dialogue.strip():
        audio_note = f"off-camera audio: {dialogue.strip()}"
    elif beat.get("description"):
        audio_note = "off-camera child voice echoes through corridor"

    return [{
        "role": "off_camera_audio",
        "b_roll": True,
        "suppress_mindset": True,
        "camera": CameraExtrinsics(
            shot_size="MS",
            focal_length_mm=fl,
            move_type="locked"
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.3,
            color_temp_K=color_temp
        ),
        "composition": "negative_space",
        "include_characters": False,
        "duration_seconds": 5,
        "ltx_duration": 8,
        "audio_note": audio_note or "off-camera presence is heard while frame stays empty"
    }]


def generate_shadow_silhouette_shot(context: Dict) -> List[Dict]:
    """Shadow/silhouette plate for supernatural hints."""
    sampler = context.get("sampler")
    if sampler:
        fl = sampler.sample_focal_length("shadow")
        color_temp = sampler.sample_color_temp()
    else:
        fl = 50
        color_temp = 3800

    return [{
        "role": "shadow_silhouette",
        "b_roll": True,
        "suppress_mindset": True,
        "camera": CameraExtrinsics(
            shot_size="MCU",
            focal_length_mm=fl,
            move_type="locked"
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.4,
            color_temp_K=color_temp,
            lighting_ratio=6.0
        ),
        "composition": "shadow_play",
        "include_characters": False,
        "duration_seconds": 4,
        "ltx_duration": 6,
        "descriptor": "shadow figure glides along the manor wall, silhouette-only insert"
    }]


def generate_character_reactions(context: Dict) -> List[Dict]:
    """Generate character reaction shots - emotional beats."""
    sampler = context.get("sampler")

    if sampler:
        fl = sampler.sample_focal_length("reaction")
        color_temp = sampler.sample_color_temp()
    else:
        fl = 85
        color_temp = 4500

    return [{
        "role": "reaction",
        "camera": CameraExtrinsics(
            shot_size="CU",
            focal_length_mm=fl,
            move_type="locked"
        ),
        "photography": PhotographyIntrinsics(
            bokeh_K=0.75,
            color_temp_K=color_temp
        ),
        "composition": "face_emotion",
        "include_characters": True,
        "duration_seconds": 4,
        "ltx_duration": 6
    }]


# ==============================================================================
# BEHAVIOR TREE CONSTRUCTION
# ==============================================================================

def build_cinematographer_bt() -> BTNode:
    """
    Build the master Behavior Tree for shot selection.

    CRITICAL FIX: Uses BTAccumulator instead of BTSelector.
    BTAccumulator runs ALL matching branches and accumulates shots.
    This enables comprehensive coverage: establishing + dialogue + reactions + inserts.

    A real cinematographer doesn't just shoot ONE type - they cover the scene completely.
    """
    return BTAccumulator([
        # PRIMARY SHOTS - Event-driven main coverage

        # Establishing shots (first shot of scene)
        BTSequence([
            BTCondition(lambda ctx: "establishing_location" in ctx.get("events", []) and ctx.get("is_first_beat", False)),
            BTAction(generate_establishing_shots)
        ]),

        # World-opening plates (scripted first-impression beats)
        BTSequence([
            BTCondition(lambda ctx: "world_opening" in ctx.get("events", [])),
            BTAction(generate_world_opening_shots)
        ]),

        # Prop still-life plates
        BTSequence([
            BTCondition(lambda ctx: "prop_plate" in ctx.get("events", [])),
            BTAction(generate_prop_plate_shots)
        ]),

        # Off-camera audio plates
        BTSequence([
            BTCondition(lambda ctx: "off_camera_audio" in ctx.get("events", [])),
            BTAction(generate_off_camera_audio_plate)
        ]),

        # Shadow figure inserts
        BTSequence([
            BTCondition(lambda ctx: "shadow_silhouette" in ctx.get("events", [])),
            BTAction(generate_shadow_silhouette_shot)
        ]),

        # Supernatural/horror
        BTSequence([
            BTCondition(lambda ctx: "supernatural_presence" in ctx.get("events", [])),
            BTAction(generate_supernatural_shots)
        ]),

        # Ritual ceremony
        BTSequence([
            BTCondition(lambda ctx: "ritual_ceremony" in ctx.get("events", [])),
            BTAction(generate_ritual_shots)
        ]),

        # Confrontation
        BTSequence([
            BTCondition(lambda ctx: "confrontation" in ctx.get("events", [])),
            BTAction(generate_confrontation_shots)
        ]),

        # Revelation/discovery
        BTSequence([
            BTCondition(lambda ctx: "revelation" in ctx.get("events", [])),
            BTAction(generate_revelation_shots)
        ]),

        # Dialogue two-hander
        BTSequence([
            BTCondition(lambda ctx: "dialogue_two_hander" in ctx.get("events", [])),
            BTAction(generate_dialogue_two_shot)
        ]),

        # Character approach
        BTSequence([
            BTCondition(lambda ctx: "character_approach" in ctx.get("events", [])),
            BTAction(generate_approach_shots)
        ]),

        # Isolation
        BTSequence([
            BTCondition(lambda ctx: "isolation" in ctx.get("events", [])),
            BTAction(generate_isolation_shots)
        ]),

        # SUPPLEMENTARY COVERAGE - Real cinematography needs these

        # B-roll atmosphere (every scene gets atmosphere)
        BTSequence([
            BTCondition(lambda ctx: ctx.get("needs_broll", True)),
            BTAction(generate_broll_atmosphere)
        ]),

        # Insert/cutaway shots (when props mentioned or detail needed)
        BTSequence([
            BTCondition(lambda ctx: bool(ctx.get("props", [])) or "ritual_ceremony" in ctx.get("events", [])),
            BTAction(generate_insert_cutaways)
        ]),

        # Character reactions (when multiple characters present)
        BTSequence([
            BTCondition(lambda ctx: len(ctx.get("characters", [])) >= 1),
            BTAction(generate_character_reactions)
        ]),

        # Default coverage (fallback if nothing else matched)
        BTSequence([
            BTCondition(lambda ctx: not ctx.get("_has_primary_coverage", False)),
            BTAction(generate_default_coverage)
        ])
    ])


# ==============================================================================
# QUANTUM EVALUATOR (Ensemble Prompt Scoring)
# ==============================================================================

class QuantumEvaluator:
    """
    Generates and scores multiple prompt variants to find optimal shot.
    Uses classical ensemble evaluation (not actual quantum computing).

    V15 CODEX A3: Uses deterministic seeding for reproducibility.
    """

    def __init__(self, director_profile: Dict):
        self.profile = director_profile
        # V15 CODEX A3: Instance-level RNG for deterministic evaluation
        self._rng = random.Random()

    def set_context_seed(self, project_id: str, scene_id: str = "", shot_id: str = ""):
        """V15 CODEX A3: Set deterministic seed from context."""
        seed_string = f"quantum:{project_id}:{scene_id}:{shot_id}"
        hash_bytes = hashlib.sha256(seed_string.encode()).digest()
        seed = int.from_bytes(hash_bytes[:8], byteorder='big')
        self._rng = random.Random(seed)

    def generate_variants(self, base_shot: Dict, count: int = 3) -> List[Dict]:
        """Generate N variants of a shot by perturbing parameters."""
        variants = [base_shot.copy()]

        # Convert dataclass objects to dicts for deep copy
        shot_for_copy = {}
        for k, v in base_shot.items():
            if hasattr(v, 'to_dict'):
                shot_for_copy[k] = v.to_dict()
            else:
                shot_for_copy[k] = v

        for i in range(count - 1):
            variant = json.loads(json.dumps(shot_for_copy))  # Deep copy

            # Perturb focal length
            camera = variant.get("camera", {})
            if isinstance(camera, CameraExtrinsics):
                camera = camera.to_dict()
            base_fl = camera.get("focal_length_mm", 35)
            # V15 CODEX A3: Use instance RNG for determinism
            camera["focal_length_mm"] = self._rng.choice([
                max(24, base_fl - 10),
                base_fl,
                min(100, base_fl + 15)
            ])

            # Perturb color temp
            photo = variant.get("photography", {})
            if isinstance(photo, PhotographyIntrinsics):
                photo = photo.to_dict()
            base_ct = photo.get("color_temp_K", 4500)
            # V15 CODEX A3: Use instance RNG for determinism
            photo["color_temp_K"] = self._rng.choice([
                base_ct - 300,
                base_ct,
                base_ct + 300
            ])

            # Perturb bokeh
            base_bokeh = photo.get("bokeh_K", 0.5)
            # V15 CODEX A3: Use instance RNG for determinism
            photo["bokeh_K"] = round(self._rng.uniform(
                max(0.1, base_bokeh - 0.15),
                min(0.95, base_bokeh + 0.15)
            ), 2)

            variant["camera"] = camera
            variant["photography"] = photo
            variants.append(variant)

        return variants

    def score_variant(self, variant: Dict, context: Dict) -> float:
        """
        Score a variant based on director profile alignment.
        Returns score 0-1 (higher = better).
        """
        score = 0.5  # Base score

        # Check camera movement alignment
        profile_moves = self.profile.get("camera_movement_profile", {})
        camera = variant.get("camera", {})
        if isinstance(camera, CameraExtrinsics):
            camera = camera.to_dict()
        move = camera.get("move_type", "locked")

        for move_type, probability in profile_moves.items():
            if move_type in move:
                score += probability * 0.3
                break

        # Check shot size distribution alignment
        shot_scale = self.profile.get("shot_scale_profile", {})
        shot_size = camera.get("shot_size", "MS")
        if shot_size in shot_scale:
            score += shot_scale[shot_size] * 0.2

        # Check emotional alignment (via mindset)
        events = context.get("events", [])
        mindset = context.get("mindset", {})

        if "supernatural_presence" in events and mindset.get("predator_threshold", 0) > 0.5:
            score += 0.15

        if "isolation" in events and mindset.get("isolation_intensity", 0) > 0.5:
            score += 0.1

        # Diversity penalty (avoid too similar to previous)
        # This would check against a pool of already selected shots

        return min(1.0, score)

    def select_best(self, variants: List[Dict], context: Dict) -> Dict:
        """Select the highest-scoring variant."""
        if not variants:
            return {}

        scored = [(v, self.score_variant(v, context)) for v in variants]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]


# ==============================================================================
# PROMPT BUILDER
# ==============================================================================

class SemanticPromptBuilder:
    """Builds the final natural language prompt from structured data."""

    # Emotional state to visual manifestation mapping
    EMOTION_VISUALS = {
        "fear": "wide eyes catching light, shallow rapid breathing, trembling hands",
        "dread": "slow creeping horror across features, involuntary step backward",
        "terror": "paralyzed with fear, mouth agape in silent scream",
        "grief": "tears welling, shoulders hunched inward, face crumpling",
        "anger": "jaw clenched, nostrils flared, hands balled into fists",
        "determination": "steely gaze, set jaw, purposeful stance",
        "confusion": "furrowed brow, head tilted, searching eyes",
        "shock": "frozen mid-motion, blood draining from face",
        "apprehensive": "wide watchful eyes, tense shoulders, guarded posture",
        "curious": "leaning forward slightly, eyes bright with interest"
    }

    # V15.2 FIX: Director mindset to visual language - using CONCRETE visual cues, not metaphors
    # "camera behaves like predator" is NOT a visual description - LTX/image models can't render metaphors
    MINDSET_PHRASES = {
        "predator_threshold": "slow dolly, low angle, tracking movement",  # V15.2: Concrete camera terms
        "shadows_closing_in": "deep shadows, vignette framing, chiaroscuro lighting",  # V15.2: Visual lighting terms
        "viewer_as_prey": "wide angle distortion, low camera height",  # V15.2: Concrete lens/camera terms
        "isolation_intensity": "vast negative space, small figure in frame"  # V15.2: Compositional terms
    }

    @classmethod
    def build_prompt(
        cls,
        shot: Dict,
        scene: Dict,
        beat: Dict,
        characters: List[Dict],
        director_profile: Dict,
        mindset: DirectorMindset,
        director_library_profile: Optional[Dict] = None,  # V3.5: Named director from library
        writer_profile: Optional[Dict] = None  # V3.5: Writer voice characteristics
    ) -> str:
        """
        Build the complete visual prompt string.

        CRITICAL: Must include:
        1. Camera/cinematographic language
        2. Character visuals from asset grid (physical, costume, signature_items)
        3. Beat action/props from script
        4. Emotional state visualization
        5. Location and atmosphere
        6. V3.5: Director visual_signature (lighting, lens preferences)
        7. V3.5: Writer voice influence on action descriptions
        """
        parts = []

        # V3.5 FIX: Extract director visual_signature
        visual_sig = {}
        if director_library_profile:
            visual_sig = director_library_profile.get("visual_signature", {})

        # 1. Camera/lens specs - V3.5: Use director's lens_preferences
        camera = shot.get("camera", {})
        if isinstance(camera, CameraExtrinsics):
            camera = camera.to_dict()

        move = camera.get("move_type", "locked").replace("_", " ")
        fl = camera.get("focal_length_mm", 35)
        size = camera.get("shot_size", "MS")

        # V3.5: Apply director's movement vocabulary if available
        movement_vocab = visual_sig.get("movement_vocabulary", {})
        if movement_vocab:
            # Map shot context to movement vocabulary
            if "horror" in str(scene.get("emotion", "")).lower():
                move = movement_vocab.get("horror", move)
            elif "tension" in str(beat.get("description", "")).lower():
                move = movement_vocab.get("tension", move)
            elif "revelation" in str(beat.get("description", "")).lower():
                move = movement_vocab.get("revelation", move)
            elif movement_vocab.get("default"):
                move = movement_vocab.get("default", move)

        # V15.4 FIX: Use V5.4 GOLD STANDARD prompt structure
        # Instead of technical "24mm WS", use natural language "Wide establishing shot of {location}"
        # This matches the prompts from ravencroft_v13_fresh/shot_plan.json which produced quality frames

        # Get location from scene for natural language prompt
        location = scene.get("location", "")

        # Map shot size to natural language description (V5.4 gold standard)
        SHOT_SIZE_TO_DESC = {
            "EWS": "Extreme wide establishing shot",
            "WS": "Wide establishing shot",
            "WI": "Wide establishing shot",
            "FS": "Full shot",
            "MS": "Medium shot",
            "ME": "Medium shot",
            "MCU": "Medium close-up",
            "CU": "Close-up",
            "CL": "Close-up",
            "ECU": "Extreme close-up detail",
            "EX": "Extreme close-up detail",
            "OTS": "Over-the-shoulder shot",
            "OV": "Over-the-shoulder shot",
            "POV": "Point-of-view shot",
            "TWO": "Two-shot",
            "TW": "Two-shot",
            "INSERT": "Insert detail shot",
            "ESTABLISHING": "Wide establishing shot",
            "WIDE": "Wide shot",
            "MEDIUM": "Medium shot",
            "CLOSE": "Close-up",
        }
        shot_desc = SHOT_SIZE_TO_DESC.get(size.upper(), f"{size} shot")

        # V5.4: Start with natural language shot description
        if location:
            parts.append(f"{shot_desc} of {location}")

        # V5.4: Get emotional beat from beat data for prompt
        emotional_beat = beat.get("emotional_beat", beat.get("emotional_tone", ""))

        # V5.4: Get director's lens preferences for "Shot on {lens}" format
        lens_prefs = visual_sig.get("lens_preferences", {})
        # Map shot size to lens preference key
        lens_key_map = {
            "WS": "establishing", "WI": "establishing", "EWS": "establishing",
            "MS": "dialogue", "ME": "dialogue", "FS": "dialogue",
            "CU": "intimate", "CL": "intimate", "MCU": "intimate",
            "ECU": "intimate", "EX": "intimate",
            "OTS": "dialogue", "OV": "dialogue",
        }
        lens_key = lens_key_map.get(size.upper(), "dialogue")
        lens_str = lens_prefs.get(lens_key, f"{fl}mm")

        # V5.4: Add "Shot on {lens}" in natural language format (like V13 gold)
        parts.append(f"Shot on {lens_str}")

        descriptor = shot.get("descriptor")
        if descriptor:
            parts.append(descriptor)

        # 3. CRITICAL: Characters with FULL visual markers from asset grid
        # V3.5 FIX: PRIORITIZE image_prompt from AI Actors library!
        if shot.get("include_characters", True) and characters:
            char_descs = []
            for char in characters:
                name = char.get('name', 'character')

                # V3.5: PREFER image_prompt if available (rich AI actor description)
                image_prompt = char.get('image_prompt', '')
                wardrobe_hex = char.get('wardrobe_hex', '')

                if image_prompt:
                    # Use full AI actor image_prompt (already includes physical+costume+wardrobe)
                    # Format: "NAME, [image_prompt contents]"
                    char_descs.append(f"{name.upper()}, {image_prompt}")
                else:
                    # Fallback to building from components
                    physical = char.get('physical', '')
                    costume = char.get('costume', '')
                    signature = char.get('signature_items', '')

                    desc = name
                    details = []
                    if physical:
                        details.append(physical)
                    if costume:
                        details.append(f"wearing {costume}")
                    if wardrobe_hex:
                        details.append(f"wardrobe {wardrobe_hex}")
                    if signature:
                        details.append(signature)

                    if details:
                        desc += f" ({', '.join(details)})"
                    char_descs.append(desc)

            if char_descs:
                parts.append(", ".join(char_descs))

        # 4. CRITICAL: Beat description/action from script
        beat_description = beat.get("description", "")
        if beat_description:
            parts.append(beat_description)

        # V15.1: CRITICAL FIX - Include script_line_ref and dialogue_text from shot
        # These fields contain the ACTUAL script content that was extracted
        script_line_ref = shot.get("script_line_ref", "")
        if script_line_ref and script_line_ref not in beat_description:
            # Clean up script reference for prompt
            script_clean = script_line_ref.replace("(O.S.)", "").replace("(V.O.)", "").strip()
            if len(script_clean) > 250:
                script_clean = script_clean[:250] + "..."
            if script_clean:
                parts.append(f"[{script_clean}]")

        dialogue_text = shot.get("dialogue_text", "") or beat.get("dialogue_text", "")
        if dialogue_text and dialogue_text not in str(parts):
            # Include dialogue for character performance guidance
            dialogue_clean = dialogue_text.strip()
            if len(dialogue_clean) > 150:
                dialogue_clean = dialogue_clean[:150] + "..."
            if dialogue_clean:
                parts.append(f"speaking: \"{dialogue_clean}\"")

        # 5. CRITICAL: Beat action with props
        # V3.5 FIX: Apply writer's page_aesthetic to action description style
        beat_action = beat.get("action", "")
        if beat_action:
            # Clean up action text for prompt use
            action_clean = beat_action.replace("(O.S.)", "").replace("(V.O.)", "").strip()
            if len(action_clean) > 200:
                action_clean = action_clean[:200] + "..."

            # V3.5: Add writer's action line style if available
            if writer_profile:
                page_aesthetic = writer_profile.get("page_aesthetic", {})
                action_style = page_aesthetic.get("action_lines", "")
                if action_style and len(action_clean) > 20:
                    # Don't duplicate if already stylized
                    if action_style.lower() not in action_clean.lower():
                        action_clean = f"{action_clean} [{action_style}]"

            parts.append(action_clean)

        # 6. CRITICAL: Props from beat
        props = beat.get("props")
        if not props:
            props = scene.get("scene_props", [])
        if props:
            if isinstance(props, list):
                props_str = ", ".join(props[:4])
            else:
                props_str = str(props)
            parts.append(props_str)

        # 7. Emotional state injection
        emotional_context = beat.get("emotional_state", "")
        if emotional_context:
            for emotion, visual in cls.EMOTION_VISUALS.items():
                if emotion in emotional_context.lower():
                    parts.append(visual)
                    break

        # Also check description for emotional cues
        desc_lower = beat_description.lower() if beat_description else ""
        if not emotional_context:
            for emotion, visual in cls.EMOTION_VISUALS.items():
                if emotion in desc_lower:
                    parts.append(visual)
                    break

        # 8. Director mindset injection
        mindset_parts = []
        if not shot.get("suppress_mindset"):
            if mindset.predator_threshold > 0.5:
                mindset_parts.append(cls.MINDSET_PHRASES["predator_threshold"])
            if mindset.shadows_closing_in:
                mindset_parts.append(cls.MINDSET_PHRASES["shadows_closing_in"])
            if mindset.isolation_intensity > 0.5:
                mindset_parts.append(cls.MINDSET_PHRASES["isolation_intensity"])
        if mindset_parts:
            parts.append(", ".join(mindset_parts))

        # 9. Location context
        location = scene.get("location", "")
        if location:
            parts.append(location)

        # 10. Scene atmosphere/tone
        scene_tone = scene.get("tone", "")
        if scene_tone:
            parts.append(scene_tone)

        # 11. Photography/lighting with specific color temps
        # V3.5 FIX: PREFER director's lighting_signature from directors_library
        photo = shot.get("photography", {})
        if isinstance(photo, PhotographyIntrinsics):
            photo = photo.to_dict()

        lighting_sig = visual_sig.get("lighting_signature", {})

        if lighting_sig:
            # V5.4 FIX: Use director's lighting in V5.4 GOLD STANDARD format
            # Format: "Lighting: candlelight amber, moonlight blue, never mixed artificially"
            lighting_palette = lighting_sig.get("palette", "")
            lighting_ratio = lighting_sig.get("ratio", "")
            lighting_instruments = lighting_sig.get("instruments", [])

            if lighting_palette:
                parts.append(f"Lighting: {lighting_palette}")
            if lighting_ratio:
                parts.append(lighting_ratio)
            if lighting_instruments:
                parts.append(f"lighting instruments: {', '.join(lighting_instruments[:3])}")
        else:
            # Fallback to generic lighting based on color temp
            color_temp = photo.get("color_temp_K", 4500)
            if color_temp < 3500:
                parts.append(f"warm tungsten lighting, {color_temp}K")
            elif color_temp < 4000:
                parts.append(f"tungsten_cool_split lighting, {color_temp}K")
            elif color_temp > 5000:
                parts.append(f"cool daylight, {color_temp}K")
            else:
                parts.append(f"mixed practical lighting, {color_temp}K")

            ratio = photo.get("lighting_ratio", 2.0)
            if ratio > 4.0:
                parts.append("extreme contrast, pitch black shadows")
            elif ratio > 3.0:
                parts.append("high contrast, deep shadows")
            elif ratio > 2.0:
                parts.append("dramatic lighting ratio")

        # V5.4 FIX: Add director's color_grade in GOLD STANDARD format
        # Format: "Color palette: Desaturated with amber accents, shadows: Deep blue-black, never crushed"
        color_grade = visual_sig.get("color_grade", {})
        if color_grade:
            grade_parts = []
            if color_grade.get("primary"):
                grade_parts.append(color_grade["primary"])
            if color_grade.get("shadow_tone"):
                grade_parts.append(f"shadows: {color_grade['shadow_tone']}")
            if grade_parts:
                parts.append(f"Color palette: {', '.join(grade_parts)}")

        # 12. Style anchor from director profile
        style = director_profile.get("global_aesthetic", {})
        tone = style.get("tone", ["cinematic"])
        if isinstance(tone, list):
            parts.append(", ".join(tone[:2]))
        else:
            parts.append(tone)

        audio_note = shot.get("audio_note")
        if audio_note:
            parts.append(audio_note)

        # 13. Shot role tag
        role = shot.get("role", "coverage")
        parts.append(f"[{role.replace('_', ' ')}]")

        # 14. Period authenticity - derive from location/scene context
        import re
        location_upper = location.upper()

        # Check for explicit year patterns (1800s, 1900s, etc.)
        year_match = re.search(r'\b(1[78]\d{2}|19[0-4]\d)\b', location)

        if year_match:
            year = year_match.group(1)
            if year.startswith("18"):
                period = f"Victorian era {year}, period authentic costumes and props"
            elif year.startswith("19") and int(year) < 1950:
                period = f"Early 20th century {year}, period authentic"
            else:
                period = f"{year} period authentic"
        elif "DECADES AGO" in location_upper or "VICTORIAN" in location_upper:
            period = "Victorian era, period authentic"
        elif "MEDIEVAL" in location_upper or "CASTLE" in location_upper:
            period = "Medieval era, period authentic"
        elif "1890" in location or "1880" in location or "1870" in location:
            period = "Victorian era 1890s, period authentic costumes and props"
        elif "NIGHT" in location_upper:
            # Night doesn't imply a time period, check for historical markers
            period = "cinematic night lighting"
        else:
            # Default to present day only if no historical markers found
            period = "contemporary period"
        parts.append(period)

        # V5.4 FIX: Add emotional beat from beat data
        # Format: "Emotional beat: establishment" (like V13 gold)
        if emotional_beat:
            parts.append(f"Emotional beat: {emotional_beat}")

        # V5.4 FIX: Add final quality markers (V13 GOLD STANDARD)
        # These are the key quality markers that made V13 prompts produce cinematic results
        parts.append("Cinematic composition, 16:9 aspect ratio, film grain, professional cinematography")

        return ", ".join(filter(None, parts))


# ==============================================================================
# CINEMATOGRAPHER AGENT (Main Class)
# ==============================================================================

class CinematographerAgent:
    """
    Main agent that orchestrates behavior tree evaluation,
    quantum evaluation, and prompt generation.
    """

    def __init__(
        self,
        story_bible_path: Optional[Path] = None,
        director_profile_path: Optional[Path] = None,
        director_profile_name: str = "thriller_v2",  # V3.2: Changed from ravencroft_gothic_v2 to neutral default
        asset_grid_path: Optional[Path] = None,
        genre: str = "thriller"  # V3.5: Genre for director/writer assignment
    ):
        self.behavior_tree = build_cinematographer_bt()
        self.analyzer = SceneContextAnalyzer()

        # Load director profile (technical camera settings)
        self.director_profile = self._load_director_profile(
            director_profile_path, director_profile_name
        )

        # V3.5 FIX: Load directors_library.json for visual_signature
        self.director_library_profile = self._load_director_from_library(genre)

        # V3.5 FIX: Load writers_library.json for voice characteristics
        self.writer_profile = self._load_writer_from_library(genre)

        # Load story bible for character data
        self.story_bible = self._load_story_bible(story_bible_path)

        # Load asset grid for character visuals (CRITICAL for prompts)
        self.asset_grid = self._load_asset_grid(asset_grid_path)

        # Build character lookup from both sources
        self.character_lookup = self._build_character_lookup()

        # Create ProfileSampler for distribution-based camera variety
        self.profile_sampler = ProfileSampler(self.director_profile)

        self.quantum_evaluator = QuantumEvaluator(self.director_profile)

    def _load_director_profile(
        self, path: Optional[Path], name: str
    ) -> Dict:
        """Load director profile from JSON."""
        if path and path.exists():
            profiles = json.loads(path.read_text())
            return profiles.get(name, {})

        # Try default path - V3.2: Use Config for portability
        default_path = Config.ATLAS_ROOT / "director_profiles_v2.json"
        if default_path.exists():
            profiles = json.loads(default_path.read_text())
            return profiles.get(name, {})

        return {}

    def _load_director_from_library(self, genre: str) -> Dict:
        """
        V3.5 FIX: Load named director from directors_library.json based on genre.
        Returns full director profile with visual_signature, shot_braintree_overrides, etc.
        """
        library_path = Config.ATLAS_ROOT / "directors_library.json"
        if not library_path.exists():
            return {}

        try:
            library = json.loads(library_path.read_text())
            mapping = library.get("genre_to_director_mapping", {})
            director_id = mapping.get(genre) or mapping.get("thriller", "D005")

            for director in library.get("directors", []):
                if director.get("id") == director_id:
                    return director

            # Fallback to first director if no match
            directors = library.get("directors", [])
            return directors[0] if directors else {}
        except Exception:
            return {}

    def _load_writer_from_library(self, genre: str) -> Dict:
        """
        V3.5 FIX: Load named writer from writers_library.json based on genre.
        Returns full writer profile with voice_characteristics, sample_scripts, etc.
        """
        library_path = Config.ATLAS_ROOT / "writers_library.json"
        if not library_path.exists():
            return {}

        try:
            library = json.loads(library_path.read_text())
            mapping = library.get("genre_to_writer_mapping", {})

            # Build mapping from writer genres if no explicit mapping
            if not mapping:
                for writer in library.get("writers", []):
                    for w_genre in writer.get("genres", []):
                        if w_genre not in mapping:
                            mapping[w_genre] = writer.get("id")

            writer_id = mapping.get(genre) or "W001"

            for writer in library.get("writers", []):
                if writer.get("id") == writer_id:
                    return writer

            # Fallback to first writer if no match
            writers = library.get("writers", [])
            return writers[0] if writers else {}
        except Exception:
            return {}

    def _load_story_bible(self, path: Optional[Path]) -> Dict:
        """Load story bible for character data."""
        if path and path.exists():
            return json.loads(path.read_text())

        default_path = Config.ATLAS_ROOT / "ravencroft_story_bible.json"
        if default_path.exists():
            return json.loads(default_path.read_text())

        return {}

    def _load_asset_grid(self, path: Optional[Path]) -> Dict:
        """Load asset grid for character visuals (CRITICAL for prompts)."""
        if path and path.exists():
            return json.loads(path.read_text())

        # Try default asset grid paths - V3.2: Use Config for portability
        default_paths = [
            Config.ATLAS_ROOT / "asset_grids/ravencroft_manor_asset_grid_LATEST.json",
            Config.ATLAS_ROOT / "asset_grids/ravencroft_manor_asset_grid_FIXED.json",
        ]
        for default_path in default_paths:
            if default_path.exists():
                return json.loads(default_path.read_text())

        return {}

    def _build_character_lookup(self) -> Dict[str, Dict]:
        """
        Build lookup for character descriptions.
        CRITICAL: Merges data from both story bible AND asset grid.
        Asset grid has the visual_markers needed for prompts.
        """
        lookup = {}

        # First load from story bible
        for char in self.story_bible.get("characters", []):
            name = char.get("name", "")
            if name:
                lookup[name.lower()] = char
                first = name.split()[0].lower()
                lookup[first] = char

        # Then overlay/merge from asset grid (has visual_markers)
        for char in self.asset_grid.get("characters", {}).get("entries", []):
            name = char.get("name", "")
            if name:
                key = name.lower()
                first = name.split()[0].lower()

                # Extract visual markers into flat structure for prompt builder
                visual = char.get("visual_markers", {})
                char_data = {
                    "name": name,
                    "physical": visual.get("physical", ""),
                    "costume": visual.get("costume", ""),
                    "signature_items": visual.get("signature_items", ""),
                    # V3.5 FIX: Include AI Actor image_prompt and wardrobe_hex!
                    "image_prompt": visual.get("image_prompt", "") or char.get("image_prompt", ""),
                    "wardrobe_hex": visual.get("wardrobe_hex", "") or char.get("wardrobe_hex", ""),
                    "ltx_motion_default": char.get("ltx_motion_default", ""),
                    "image_url": char.get("image_url", ""),
                    "source_path": char.get("source_path", "")
                }

                # Merge with existing or create new
                if key in lookup:
                    lookup[key].update(char_data)
                else:
                    lookup[key] = char_data

                if first not in lookup:
                    lookup[first] = char_data

        return lookup

    def _get_character_descriptions(self, names: List[str]) -> List[Dict]:
        """
        Get full character descriptions including AI Actor image_prompt.
        V3.5 FIX: Now extracts image_prompt for use in SemanticPromptBuilder.
        """
        descriptions = []
        for name in names:
            key = name.lower()
            if key in self.character_lookup:
                char = self.character_lookup[key]
                visual = char.get("visual_markers", {})
                descriptions.append({
                    "name": char.get("name", name),
                    "physical": visual.get("physical", "") or char.get("physical", ""),
                    "costume": visual.get("costume", "") or char.get("costume", ""),
                    "signature_items": visual.get("signature_items", "") or char.get("signature_items", ""),
                    # V3.5 FIX: Include AI Actor's rich image_prompt!
                    "image_prompt": visual.get("image_prompt", "") or char.get("image_prompt", ""),
                    "wardrobe_hex": visual.get("wardrobe_hex", "") or char.get("wardrobe_hex", ""),
                    "ltx_motion_default": char.get("ltx_motion_default", ""),
                })
        return descriptions

    def propose_shot_count(self, beat_duration: float, omega: float, available: int) -> int:
        """Determine shot count using beat duration and complexity."""
        base_seconds = 6 if omega >= 0.7 else 8 if omega >= 0.4 else 10
        beat_duration = max(beat_duration, base_seconds)
        target = max(1, math.ceil(beat_duration / base_seconds))
        if available > 0:
            target = min(target, available)
        return target

    def generate_shots_for_beat(
        self,
        beat: Dict,
        scene: Dict,
        beat_index: int = 0
    ) -> List[SemanticPromptJSON]:
        """
        Generate cinematographic coverage for a beat using BT + Quantum evaluation.
        Now with multi-event coverage for richer cinematography.
        """
        # Extract events and context
        coverage_directive = beat.get("coverage_directive") or scene.get("coverage_directive") or {}

        events = self.analyzer.extract_events(beat, scene)
        forced_events = coverage_directive.get("force_events") or []
        if forced_events:
            # Preserve order while ensuring unique entries
            events = list(dict.fromkeys(forced_events + events))
        omega = self.analyzer.calculate_complexity_omega(beat, scene)
        emotional = self.analyzer.extract_emotional_state(beat, scene)

        # Build director mindset from beat context
        mindset = DirectorMindset()
        text = json.dumps(beat).lower()
        if any(kw in text for kw in ["terror", "horror", "dread"]):
            mindset.predator_threshold = 0.7
            mindset.shadows_closing_in = True
        if "isolation" in events:
            mindset.isolation_intensity = 0.8
        if "confrontation" in events:
            mindset.tension_level = 0.7

        # Create BT context with ProfileSampler for camera variety
        context = {
            "beat": beat,
            "scene": scene,
            "events": events,
            "omega": omega,
            "emotional": emotional,
            "mindset": mindset.to_dict(),
            "sampler": self.profile_sampler,  # CRITICAL: Enables distribution-based camera variety
            "is_first_beat": beat_index == 0,
            "props": beat.get("props") or scene.get("scene_props", []),
            "characters": beat.get("characters", []) or scene.get("characters_present", []),
            "coverage_directive": coverage_directive
        }

        # Run behavior tree for primary shots
        status, shot_proposals = self.behavior_tree.tick(context)

        # For multi-event beats, run BT for each major event to get coverage variety
        if len(events) > 1:
            # Priority order for secondary events (skip establishing, get story coverage)
            priority_events = [
                "dialogue_two_hander", "confrontation", "revelation",
                "supernatural_presence", "ritual_ceremony", "isolation",
                "character_approach"
            ]
            for event in priority_events:
                if event in events:
                    # Create context with only this event to trigger that branch
                    single_event_ctx = context.copy()
                    single_event_ctx["events"] = [event]
                    _, additional_shots = self.behavior_tree.tick(single_event_ctx)
                    # Add shots that weren't already proposed
                    for shot in additional_shots:
                        if shot.get("role") not in [s.get("role") for s in shot_proposals]:
                            shot_proposals.extend(additional_shots[:2])  # Max 2 per event type
                            break

        beat_duration = (
            coverage_directive.get("duration_seconds")
            or beat.get("duration_seconds")
            or 8
        )
        if beat_duration <= 0:
            beat_duration = 8
        available_shots = len(shot_proposals)
        if available_shots == 0:
            return []
        target_override = coverage_directive.get("target_shots")
        if target_override:
            target_count = min(max(1, target_override), available_shots)
        else:
            target_count = self.propose_shot_count(beat_duration, omega, available_shots)
        selected_shots = shot_proposals[:target_count]

        # V3.2: Extended allowed durations to match LTX valid values for more variety
        allowed_durations = [6, 8, 10, 12, 14, 16, 18, 20]
        avg_duration = beat_duration / max(1, target_count)
        per_shot_duration = coverage_directive.get("ltx_duration_seconds")
        if not per_shot_duration:
            # Ensure minimum variety - use actual beat duration for pacing, not just closest
            per_shot_duration = min(allowed_durations, key=lambda d: abs(d - max(8, avg_duration)))

        # Get character descriptions
        char_names = scene.get("characters_present", [])
        characters = self._get_character_descriptions(char_names)

        # Generate final shots
        final_shots = []
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        suffixes = []
        for idx in range(len(selected_shots)):
            letter = alphabet[idx % len(alphabet)]
            repeat = idx // len(alphabet)
            suffixes.append(letter if repeat == 0 else f"{letter}{repeat}")

        for i, shot in enumerate(selected_shots):
            # Quantum evaluation for high-value beats
            if omega >= 0.6:
                variants = self.quantum_evaluator.generate_variants(shot, 3)
                shot = self.quantum_evaluator.select_best(variants, context)

            # Build camera/photo objects
            camera_data = shot.get("camera", {})
            if isinstance(camera_data, dict):
                camera = CameraExtrinsics(**{
                    k: v for k, v in camera_data.items()
                    if k in CameraExtrinsics.__dataclass_fields__
                })
            else:
                camera = camera_data

            photo_data = shot.get("photography", {})
            if isinstance(photo_data, dict):
                photo = PhotographyIntrinsics(**{
                    k: v for k, v in photo_data.items()
                    if k in PhotographyIntrinsics.__dataclass_fields__
                })
            else:
                photo = photo_data

            # Build visual prompt
            # V3.5 FIX: Pass director_library_profile and writer_profile for full integration
            prompt = SemanticPromptBuilder.build_prompt(
                shot=shot,
                scene=scene,
                beat=beat,
                characters=characters if shot.get("include_characters", True) else [],
                director_profile=self.director_profile,
                mindset=mindset,
                director_library_profile=self.director_library_profile,  # V3.5: Named director
                writer_profile=self.writer_profile  # V3.5: Writer voice
            )

            # V3.2: Snap LTX duration to valid values - check both field names
            # Patterns use "ltx_duration", SemanticPromptJSON uses "ltx_duration_seconds"
            ltx_dur = shot.get("ltx_duration") or shot.get("ltx_duration_seconds") or shot.get("duration_seconds") or per_shot_duration

            # Create semantic prompt JSON
            shot_id = f"{scene.get('scene_id', 'SCENE')}_{beat_index:03d}{suffixes[i]}"

            # === ASSET GRID INTELLIGENCE ===
            # Determine which assets from 14-slot grid to use for this shot
            shot_role = shot.get("role", "coverage")
            shot_size = camera.shot_size if hasattr(camera, 'shot_size') else shot.get("camera", {}).get("shot_size", "MS")
            beat_props = beat.get("props", [])
            if isinstance(beat_props, str):
                beat_props = [p.strip() for p in beat_props.split(",") if p.strip()]

            asset_grid = determine_shot_assets(
                shot_role=shot_role,
                shot_size=shot_size,
                scene_characters=char_names,
                beat_props=beat_props,
                beat=beat,
                is_first_shot=(i == 0)
            )

            semantic_shot = SemanticPromptJSON(
                shot_id=shot_id,
                scene_metadata={
                    "location_ext_int": scene.get("location", ""),
                    "narrative_intent": emotional.get("emotional_turn", ""),
                    "scene_complexity_score": omega,
                    "beat_number": beat_index
                },
                director_profile=self.director_profile.get("id", "default"),
                director_mindset=mindset,
                events=events,
                camera=camera,
                photography=photo,
                asset_grid=asset_grid,  # NEW: Per-shot asset intelligence
                style_anchor=self.director_profile.get("global_aesthetic", {}).get(
                    "tone", ["cinematic"]
                )[0] if isinstance(
                    self.director_profile.get("global_aesthetic", {}).get("tone"), list
                ) else "cinematic",
                visual_prompt_string=prompt,
                ltx_duration_seconds=ltx_dur,
                shot_role=shot_role,
                composition_tag=shot.get("composition", "balanced"),
                narrative_intent=beat.get("description", ""),
                emotional_turn=emotional.get("emotional_turn", ""),
                key_dramatic_question=emotional.get("key_dramatic_question", "")
            )

            final_shots.append(semantic_shot)

        return final_shots


# ==============================================================================
# EXPORT FUNCTION
# ==============================================================================

def process_scene_with_cinematographer(
    scene: Dict,
    story_bible_path: Optional[Path] = None,
    director_profile_name: str = "thriller_v2",  # V3.2: Changed from ravencroft_gothic_v2
    genre: str = "thriller"  # V3.5: Genre for director/writer library lookup
) -> List[Dict]:
    """
    Process a scene and generate cinematographic coverage.
    Returns list of shot specifications in dict format.

    V3.5 FIX: Now passes genre to CinematographerAgent for:
    - Director lookup from directors_library.json (visual_signature, lighting)
    - Writer lookup from writers_library.json (voice_characteristics)
    """
    agent = CinematographerAgent(
        story_bible_path=story_bible_path,
        director_profile_name=director_profile_name,
        genre=genre  # V3.5: Pass genre for library lookups
    )

    all_shots = []
    beats = scene.get("beats", [])

    for beat_idx, beat in enumerate(beats):
        shots = agent.generate_shots_for_beat(beat, scene, beat_idx)
        for shot in shots:
            all_shots.append(shot.to_dict())

    return all_shots


__all__ = [
    "CinematographerAgent",
    "SemanticPromptJSON",
    "CameraExtrinsics",
    "PhotographyIntrinsics",
    "DirectorMindset",
    "AssetGridMetadata",
    "determine_shot_assets",
    "SHOT_SIZE_TO_LOCATION_DEPTH",
    "process_scene_with_cinematographer"
]
