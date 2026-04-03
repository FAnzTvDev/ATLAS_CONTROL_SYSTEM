"""
PHASE 1 FOUNDATION — ATLAS Doctrine Command System
Identity & Continuity Foundation Layer (10 Core Gates + 2 Utilities)

Identity Law 01-02: Character pack locking and similarity validation
Continuity Law 01-02: State extraction and carry validation
Executive Law 01-02: Shot classification and scene planning
Vision Law 01: Dual scoring requirement
Memory Law 01: Pattern stability
Reward Law 01: Narrative over metrics
Override Law 01: Mandatory escalation

Code 01: Source truth protection utility
Code 10: Language discipline transformer

Status: PRODUCTION READY V24.2 | Author: ATLAS Doctrine Engine
All gates wired to doctrine_engine GateResult, DoctrineGate, LedgerEntry, RunLedger, EscalationTracker
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
import json
from datetime import datetime
import re

# Import from doctrine_engine
try:
    from tools.doctrine_engine import (
        GateResult,
        DoctrineGate,
        LedgerEntry,
        RunLedger,
        EscalationTracker,
        IDENTITY_PASS_THRESHOLD,
        IDENTITY_ZONE2_FLOOR,
        CONTINUITY_LOSS_WARN_THRESHOLD,
        ESCALATION_CAPACITY_MULTIPLIER,
        PHASE_ORDER,
    )
except ImportError:
    # Fallback for development/testing
    from doctrine_engine import (
        GateResult,
        DoctrineGate,
        LedgerEntry,
        RunLedger,
        EscalationTracker,
        IDENTITY_PASS_THRESHOLD,
        IDENTITY_ZONE2_FLOOR,
        CONTINUITY_LOSS_WARN_THRESHOLD,
        ESCALATION_CAPACITY_MULTIPLIER,
        PHASE_ORDER,
    )


# ==============================================================================
# DATACLASSES: Carry State for Continuity
# ==============================================================================

@dataclass
class CharacterCarryState:
    """Per-character spatial and costume state snapshot."""
    name: str
    hair_placement: Optional[str] = None  # e.g., "down, wavy, dark brown"
    wardrobe_position: Optional[str] = None  # e.g., "dark jacket, white blouse"
    prop_possession: List[str] = field(default_factory=list)  # e.g., ["letter", "candle"]
    hand_state: Optional[str] = None  # e.g., "left hand holds candle, right at side"
    gaze_vector: Optional[str] = None  # e.g., "toward MARGARET", "camera", "downward"
    torso_angle: Optional[str] = None  # e.g., "frontal", "three-quarter-left", "profile"
    emotion_read: Optional[str] = None  # e.g., "grief", "determination"
    screen_position: Optional[str] = None  # e.g., "left-third", "center", "right-third"


@dataclass
class CarryState:
    """Full carry-state snapshot: all characters + scene context after a shot."""
    shot_id: str
    scene_id: str
    timestamp: str
    characters: List[CharacterCarryState] = field(default_factory=list)
    scene_context: Optional[str] = None  # e.g., "ritual chamber, candlelit, stone walls"
    lighting_condition: Optional[str] = None  # e.g., "warm amber from candles"
    camera_position: Optional[str] = None  # e.g., "wide establishing, 24mm equivalent"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "shot_id": self.shot_id,
            "scene_id": self.scene_id,
            "timestamp": self.timestamp,
            "characters": [asdict(c) for c in self.characters],
            "scene_context": self.scene_context,
            "lighting_condition": self.lighting_condition,
            "camera_position": self.camera_position,
        }


# ==============================================================================
# IDENTITY LAW 01 — Identity Pack Lock Gate
# ==============================================================================

class IdentityPackLockGate(DoctrineGate):
    """
    Validates that every character in a shot has a locked identity pack:
    - exists in cast_map
    - has headshot_url or character_reference_url (not None/empty)
    - has appearance description (canonical_characters or cast_map)

    If ANY character lacks a locked identity → REJECT
    """

    def __init__(self):
        super().__init__(
            gate_name="IDENTITY_LAW_01",
            gate_position="pre_generation",
            description="Identity Pack Lock — all characters must have locked identity"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Validate identity packs for all characters in shot.

        Args:
            shot: shot_plan entry
            context: must contain cast_map, canonical_characters

        Returns:
            GateResult.PASS if all characters locked, REJECT otherwise
        """
        cast_map = context.get("cast_map", {})
        canonical_chars = context.get("canonical_characters", {})
        # V25 FIX: check all character field names used across the codebase
        characters = (
            shot.get("characters") or
            shot.get("characters_present") or
            shot.get("reference_needed") or
            []
        )

        if not characters:
            # No characters in shot — pass trivially
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No characters in shot",
                details={}
            ))
            return GateResult.PASS

        locked_characters = {}
        rejected_characters = []

        for char_name in characters:
            if char_name not in cast_map:
                rejected_characters.append(f"{char_name} (not in cast_map)")
                continue

            cast_entry = cast_map[char_name]
            headshot = cast_entry.get("headshot_url") or cast_entry.get("character_reference_url")

            if not headshot:
                rejected_characters.append(f"{char_name} (no headshot/reference URL)")
                continue

            # Check for appearance description
            has_appearance = False
            if char_name in canonical_chars:
                has_appearance = bool(canonical_chars[char_name].get("appearance"))
            elif cast_entry.get("appearance"):
                has_appearance = True

            if not has_appearance:
                rejected_characters.append(f"{char_name} (no appearance description)")
                continue

            # Character is locked
            locked_characters[char_name] = True

        if rejected_characters:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="Character identity packs not locked",
                details={
                    "locked_characters": list(locked_characters.keys()),
                    "rejected_characters": rejected_characters,
                }
            ))
            return GateResult.REJECT

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"All {len(locked_characters)} characters have locked identity packs",
            details={"locked_characters": list(locked_characters.keys())}
        ))
        return GateResult.PASS


# ==============================================================================
# IDENTITY LAW 02 — Similarity Rejection Gate
# ==============================================================================

class SimilarityRejectionGate(DoctrineGate):
    """
    Post-generation identity validation using similarity scores.

    Score >= 0.90 (PASS threshold): character match accepted
    0.75 <= score < 0.90 (WARN zone): near-match, do NOT rationalize
    score < 0.75 (REJECT): "a cousin is not the character"

    Any REJECT → gate REJECT
    Any WARN (no REJECT) → gate WARN
    All PASS → gate PASS
    """

    def __init__(self):
        super().__init__(
            gate_name="IDENTITY_LAW_02",
            gate_position="post_generation",
            description="Similarity Rejection — validate character identity scores"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Validate identity scores for all characters in shot.

        Args:
            shot: shot_plan entry
            context: must contain identity_scores dict (char_name -> float)

        Returns:
            GateResult.REJECT if any score < 0.75
            GateResult.WARN if any score in [0.75, 0.90) with no rejects
            GateResult.PASS if all scores >= 0.90
        """
        identity_scores = context.get("identity_scores", {})
        characters = shot.get("characters", [])

        if not characters:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No characters in shot",
                details={}
            ))
            return GateResult.PASS

        if not identity_scores:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="No identity scores provided",
                details={"characters": characters}
            ))
            return GateResult.REJECT

        rejects = []
        warns = []
        passes = []

        for char_name in characters:
            raw_score = identity_scores.get(char_name)

            # NULL SCORE DEFENSE: None/null from quantum_runs = REJECT, not crash
            if raw_score is None:
                rejects.append({"character": char_name, "score": None, "reason": "null identity score — no measurement taken"})
                continue

            # Type defense: non-numeric scores = REJECT
            if not isinstance(raw_score, (int, float)):
                rejects.append({"character": char_name, "score": raw_score, "reason": "non-numeric identity score"})
                continue

            score = float(raw_score)

            if score < 0.75:  # Below Zone 1 floor = Zone 2 REJECT ("a cousin is not the character")
                rejects.append({"character": char_name, "score": score, "reason": "a cousin is not the character"})
            elif score < IDENTITY_PASS_THRESHOLD:  # 0.75 <= score < 0.90 = Zone 1 WARN
                warns.append({"character": char_name, "score": score, "reason": "near-match, not confirmed"})
            else:  # >= 0.90
                passes.append({"character": char_name, "score": score})

        if rejects:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="Character identity rejected (similarity too low)",
                details={"rejects": rejects, "warns": warns, "passes": passes}
            ))
            return GateResult.REJECT

        if warns:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.WARN,
                reason="Character identity near-match, not confirmed",
                details={"warns": warns, "passes": passes}
            ))
            return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"All {len(passes)} characters confirmed",
            details={"passes": passes}
        ))
        return GateResult.PASS


# ==============================================================================
# CHARACTER BLEED GATE — Detects unauthorized characters in prompts
# ==============================================================================

class CharacterBleedGate(DoctrineGate):
    """
    Pre-generation gate: validates that ONLY characters listed in shot["characters"]
    appear in the shot's nano_prompt and ltx_motion_prompt.

    The Blackwood bug: every prompt in Scene 2 injected ALL 5 characters
    even when only Eleanor should be in the shot. This gate catches that.

    Trigger: ANY generation request
    Check: scan nano_prompt + ltx_motion_prompt for known character names
           that are NOT in shot["characters"]
    REJECT: if unauthorized character names found in prompt
    WARN: never — character bleed is always contamination
    PASS: only intended characters appear in prompt
    """

    def __init__(self):
        super().__init__(
            gate_name="CHARACTER_BLEED_GATE",
            gate_position="pre_generation",
            description="Character Bleed — detect unauthorized characters in prompts"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Scan prompts for character names not in shot["characters"].

        Args:
            shot: shot_plan entry with nano_prompt, ltx_motion_prompt, characters
            context: must contain all_known_characters (list of all character names in project)

        Returns:
            GateResult.REJECT if unauthorized characters found
            GateResult.PASS if clean
        """
        intended_characters = set(shot.get("characters") or [])
        all_known = context.get("all_known_characters", [])
        nano_prompt = shot.get("nano_prompt", "") or ""
        ltx_prompt = shot.get("ltx_motion_prompt", "") or ""
        combined_prompt = (nano_prompt + " " + ltx_prompt).lower()

        if not all_known or not intended_characters:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No character roster or no intended characters",
                details={}
            ))
            return GateResult.PASS

        # Scan for unauthorized characters
        unauthorized = []
        for char_name in all_known:
            if char_name in intended_characters:
                continue  # This character belongs here
            # Check if this character's name appears in the prompt
            if char_name.lower() in combined_prompt:
                unauthorized.append(char_name)

        if unauthorized:
            bleed_ratio = (len(intended_characters) + len(unauthorized)) / max(len(intended_characters), 1)
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason=f"Character bleed: {len(unauthorized)} unauthorized characters in prompt",
                details={
                    "intended": list(intended_characters),
                    "unauthorized": unauthorized,
                    "bleed_ratio": bleed_ratio,
                }
            ))
            return GateResult.REJECT

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"Clean prompt — only {len(intended_characters)} intended characters",
            details={"intended": list(intended_characters)}
        ))
        return GateResult.PASS


# ==============================================================================
# CONTINUITY LAW 01 — Carry State Writer
# ==============================================================================

class CarryStateWriter(DoctrineGate):
    """
    After each shot, extract and write carry-state record to context.
    Carry-state includes character spatial state, wardrobe, props, gaze, emotion.

    Used by next shot for continuity validation.
    """

    def __init__(self):
        super().__init__(
            gate_name="CONTINUITY_LAW_01",
            gate_position="post_generation",
            description="Carry State Writer — extract spatial state after generation"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Extract and store carry-state from shot.

        Args:
            shot: shot_plan entry with state_out, wardrobe, etc.
            context: will be updated with _carry_state_registry and _last_carry_state

        Returns:
            GateResult.PASS if carry-state built, WARN if extraction incomplete
        """
        shot_id = shot.get("shot_id", "unknown")
        scene_id = shot.get("scene_id", "unknown")
        characters = shot.get("characters", [])

        # Initialize registry if needed
        if "_carry_state_registry" not in context:
            context["_carry_state_registry"] = {}

        character_states = []

        # Extract per-character state
        state_out = shot.get("state_out", {})
        wardrobe_data = shot.get("_wardrobe_data", {})
        character_descriptions = shot.get("_character_descriptions", {})

        for char_name in characters:
            char_state_out = state_out.get(char_name, {})
            wardrobe_info = wardrobe_data.get(char_name, {})
            char_desc = character_descriptions.get(char_name, {})

            char_carry = CharacterCarryState(
                name=char_name,
                hair_placement=char_desc.get("hair"),
                wardrobe_position=wardrobe_info.get("wardrobe_tag") or char_desc.get("clothing"),
                prop_possession=char_state_out.get("props", []),
                hand_state=char_state_out.get("hand_state"),
                gaze_vector=char_state_out.get("gaze_target"),
                torso_angle=char_state_out.get("posture"),
                emotion_read=char_state_out.get("emotion"),
                screen_position=char_state_out.get("position"),
            )
            character_states.append(char_carry)

        # Build full carry-state
        carry_state = CarryState(
            shot_id=shot_id,
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            characters=character_states,
            scene_context=shot.get("_scene_context"),
            lighting_condition=shot.get("_lighting_condition"),
            camera_position=shot.get("_camera_position"),
        )

        # Store in registry and as "last"
        context["_carry_state_registry"][shot_id] = carry_state
        context["_last_carry_state"] = carry_state

        verdict = GateResult.PASS if character_states else GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot_id,
            verdict=verdict,
            reason=f"Carry-state extracted for {len(character_states)} characters" if character_states else "No character states extracted",
            details={
                "characters_extracted": [c.name for c in character_states],
                "carry_state_id": shot_id,
            }
        ))

        return verdict


# ==============================================================================
# CONTINUITY LAW 02 — Carry State Validator
# ==============================================================================

class CarryStateValidator(DoctrineGate):
    """
    Validate that current shot respects carry-state from previous shot.

    Checks: wardrobe match, prop continuity, character presence

    Boundary types (scene break, time skip) reset state expectations.
    """

    def __init__(self):
        super().__init__(
            gate_name="CONTINUITY_LAW_02",
            gate_position="post_generation",
            description="Carry State Validator — verify continuity from previous shot"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Validate carry-state continuity.

        Args:
            shot: current shot_plan entry
            context: contains _last_carry_state, _carry_state_registry

        Returns:
            GateResult.PASS if no breaks or boundary authorized reset
            GateResult.WARN if minor breaks (1) without authorization
            GateResult.REJECT if 2+ breaks without authorization
        """
        # Get boundary type
        boundary_type = shot.get("_boundary_type", "HARD_CONTINUOUS")

        # Boundary-authorized resets
        if boundary_type in ("SCENE_BOUNDARY", "TIME_SKIP", "LOCATION_CHANGE"):
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason=f"Boundary reset authorized: {boundary_type}",
                details={"boundary_type": boundary_type}
            ))
            return GateResult.PASS

        prev_state = context.get("_last_carry_state")
        if not prev_state:
            # First shot — no previous state to validate against
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="First shot in sequence, no previous state",
                details={}
            ))
            return GateResult.PASS

        # Compare current to previous
        continuity_breaks = []

        current_characters = shot.get("characters", [])
        prev_characters = {c.name for c in prev_state.characters}

        # Character presence check
        missing_chars = prev_characters - set(current_characters)
        if missing_chars:
            continuity_breaks.append(f"missing characters from previous shot: {missing_chars}")

        # Wardrobe continuity check (simplified)
        current_wardrobe = shot.get("_wardrobe_data", {})
        for prev_char in prev_state.characters:
            if prev_char.wardrobe_position and prev_char.name in current_characters:
                current_wardrobe_tag = current_wardrobe.get(prev_char.name, {}).get("wardrobe_tag", "")
                if current_wardrobe_tag and current_wardrobe_tag != prev_char.wardrobe_position:
                    continuity_breaks.append(f"{prev_char.name} wardrobe changed without authorization")

        # Prop continuity check (simplified)
        for prev_char in prev_state.characters:
            if prev_char.prop_possession and prev_char.name in current_characters:
                current_props = shot.get("_character_descriptions", {}).get(prev_char.name, {}).get("props", [])
                # If previous had props, current should mention them
                if not any(p in str(current_props) for p in prev_char.prop_possession):
                    continuity_breaks.append(f"{prev_char.name} props lost without explanation")

        if len(continuity_breaks) >= 2:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="Multiple continuity breaks without boundary authorization",
                details={"breaks": continuity_breaks}
            ))
            return GateResult.REJECT

        if len(continuity_breaks) == 1:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.WARN,
                reason="Minor continuity break",
                details={"breaks": continuity_breaks}
            ))
            return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason="Carry-state validated",
            details={}
        ))
        return GateResult.PASS


# ==============================================================================
# EXECUTIVE LAW 01 — Shot Classification Gate
# ==============================================================================

class ShotClassificationGate(DoctrineGate):
    """
    Classify shot into: HERO, CONNECTIVE, BROLL, INSERT, RESET

    Assigns model tier, prompt budget, and ref count based on classification.
    Always PASS (classification is assignment, not validation).
    """

    def __init__(self):
        super().__init__(
            gate_name="EXECUTIVE_LAW_01",
            gate_position="pre_generation",
            description="Shot Classification — assign class, model tier, budget, refs"
        )

    # Classification thresholds
    HERO_SHOT_TYPES = {"close_up", "MCU", "ECU", "close", "extreme_close"}
    CONNECTIVE_SHOT_TYPES = {"medium", "OTS", "two_shot", "mid_shot"}
    BROLL_SHOT_TYPES = {"broll", "establishing", "master", "wide"}
    INSERT_SHOT_TYPES = {"insert", "detail", "cutaway", "detail_shot"}
    RESET_SHOT_TYPES = {"establishing", "master", "wide"}

    # Model and budget assignment
    MODEL_ASSIGNMENT = {
        "HERO": "kling_pro",
        "CONNECTIVE": "kling_standard",
        "BROLL": "ltx2_fast",
        "INSERT": "ltx2_fast",
        "RESET": "ltx2_fast",
    }

    PROMPT_BUDGET = {
        "HERO": 200,
        "CONNECTIVE": 120,
        "BROLL": 60,
        "INSERT": 60,
        "RESET": 80,
    }

    REF_COUNT = {
        "HERO": 3,
        "CONNECTIVE": 2,
        "BROLL": 0,
        "INSERT": 1,
        "RESET": 1,
    }

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Classify shot and assign model tier, budget, ref count.

        Args:
            shot: shot_plan entry
            context: unused for classification

        Returns:
            GateResult.PASS always (classification is assignment)
        """
        shot_type = shot.get("shot_type", "").lower()
        characters = shot.get("characters", [])
        has_dialogue = bool(shot.get("dialogue_text"))
        is_emotional_peak = shot.get("_dramatic_function") == "emotional_peak"
        is_broll = bool(shot.get("_broll") or shot.get("_no_chain", False))  # V26 DOCTRINE: suffixes are editorial, not runtime

        # Classify
        classification = "CONNECTIVE"  # default

        if is_broll:
            classification = "BROLL"
        elif shot_type in self.INSERT_SHOT_TYPES:
            classification = "INSERT"
        elif (shot_type in self.HERO_SHOT_TYPES) or has_dialogue or is_emotional_peak:
            classification = "HERO"
        elif shot_type in self.CONNECTIVE_SHOT_TYPES and characters:
            classification = "CONNECTIVE"
        elif shot_type in self.RESET_SHOT_TYPES:
            classification = "RESET"

        # Assign tier, budget, refs
        model_tier = self.MODEL_ASSIGNMENT.get(classification, "ltx2_fast")
        prompt_budget = self.PROMPT_BUDGET.get(classification, 120)
        ref_count = self.REF_COUNT.get(classification, 2)

        # Store in shot
        shot["_doctrine_class"] = classification
        shot["_doctrine_model"] = model_tier
        shot["_doctrine_prompt_budget"] = prompt_budget
        shot["_doctrine_ref_count"] = ref_count

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"Shot classified as {classification}",
            details={
                "classification": classification,
                "model_tier": model_tier,
                "prompt_budget": prompt_budget,
                "ref_count": ref_count,
                "shot_type": shot_type,
            }
        ))

        return GateResult.PASS


# ==============================================================================
# EXECUTIVE LAW 02 — Scene Plan Existence Gate
# ==============================================================================

class ScenePlanExistenceGate(DoctrineGate):
    """
    Verify that a complete scene_plan exists for the shot's scene.

    scene_plan must have: shot_classes, model_tiers, peak_shots, event_boundaries, reanchor_positions
    """

    def __init__(self):
        super().__init__(
            gate_name="EXECUTIVE_LAW_02",
            gate_position="pre_generation",
            description="Scene Plan Existence — verify scene planning complete"
        )

    REQUIRED_FIELDS = {"shot_classes", "model_tiers", "peak_shots", "event_boundaries", "reanchor_positions"}

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Check that scene_plan exists and is complete.

        Args:
            shot: shot_plan entry
            context: must contain scene_plan dict

        Returns:
            GateResult.REJECT if scene_plan missing entirely
            GateResult.WARN if fields missing
            GateResult.PASS if complete
        """
        scene_id = shot.get("scene_id", "unknown")

        # ROOT CAUSE FIX: Four different callers write scene plans under four different keys.
        # The gate must resolve all of them in priority order rather than requiring
        # one canonical key that no caller consistently uses.
        #   "scene_plan"   — what this gate originally expected (nothing writes this)
        #   "_scene_plans" — what DoctrineRunner and test_doctrine_all_phases.py write
        #   "scene_plans"  — what UC tests and real orchestrator context write
        #   "scene_plan_map" — future-proofing alias
        scene_plan_registry = (
            context.get("_scene_plans") or      # DoctrineRunner + unit tests
            context.get("scene_plans") or       # UC tests + orchestrator
            context.get("scene_plan_map") or    # alias
            context.get("scene_plan") or        # original (nothing writes this)
            {}
        )
        scene_plan = scene_plan_registry.get(scene_id) if isinstance(scene_plan_registry, dict) else None

        if not scene_plan:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason=f"Scene plan missing for {scene_id}",
                details={"scene_id": scene_id}
            ))
            return GateResult.REJECT

        missing_fields = self.REQUIRED_FIELDS - set(vars(scene_plan).keys() if hasattr(scene_plan, '__dict__') else scene_plan.keys())

        if missing_fields:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.WARN,
                reason=f"Scene plan incomplete for {scene_id}",
                details={"missing_fields": list(missing_fields), "scene_id": scene_id}
            ))
            return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"Scene plan complete for {scene_id}",
            details={"scene_id": scene_id, "field_count": len(vars(scene_plan)) if hasattr(scene_plan, '__dict__') else len(scene_plan)}
        ))
        return GateResult.PASS


# ==============================================================================
# VISION LAW 01 — Dual Scoring Requirement (stub)
# ==============================================================================

class DualScoringRequirementGate(DoctrineGate):
    """
    Verify that BOTH identity_scores AND cinema_scores are present.

    Phase 5 will provide actual scoring logic.
    For now, checks that both dicts exist and are populated.
    """

    def __init__(self):
        super().__init__(
            gate_name="VISION_LAW_01",
            gate_position="post_generation",
            description="Dual Scoring Requirement — verify identity + cinematographic scoring"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Check that both identity_scores and cinema_scores are present.

        Args:
            shot: shot_plan entry
            context: must contain identity_scores and cinema_scores dicts

        Returns:
            GateResult.REJECT if identity_scores missing
            GateResult.WARN if cinema_scores missing (Phase 5 not active)
            GateResult.PASS if both present
        """
        identity_scores = context.get("identity_scores")
        cinema_scores = context.get("cinema_scores")

        if not identity_scores:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="Identity scoring not run",
                details={}
            ))
            return GateResult.REJECT

        if not cinema_scores:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.WARN,
                reason="Cinematographic scoring not run (Phase 5 not yet active)",
                details={"identity_scores_present": True}
            ))
            return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason="Both identity and cinematographic scores present",
            details={
                "identity_score_count": len(identity_scores),
                "cinema_score_count": len(cinema_scores),
            }
        ))
        return GateResult.PASS


# ==============================================================================
# MEMORY LAW 01 — Pattern Stability Check (stub)
# ==============================================================================

class PatternStabilityGate(DoctrineGate):
    """
    Stub for Phase 4 learning system.
    Checks if learned preferences have minimum confirmation count.

    Phase 4 will fully implement learning and preference tracking.
    """

    def __init__(self):
        super().__init__(
            gate_name="MEMORY_LAW_01",
            gate_position="pre_generation",
            description="Pattern Stability Check — verify learned preferences confirmed"
        )

    CONFIRMATION_THRESHOLD = 3

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Check pattern stability of learned preferences.

        Args:
            shot: shot_plan entry
            context: may contain learned_preferences dict

        Returns:
            GateResult.WARN if preferences are provisional (count < 3)
            GateResult.PASS if no preferences or all confirmed
        """
        learned_preferences = context.get("learned_preferences", {})

        if not learned_preferences:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No learned preferences applied",
                details={}
            ))
            return GateResult.PASS

        provisional = []
        confirmed = []

        for pref_name, pref_data in learned_preferences.items():
            count = pref_data.get("confirmation_count", 0)
            if count < self.CONFIRMATION_THRESHOLD:
                provisional.append({"preference": pref_name, "confirmations": count})
            else:
                confirmed.append({"preference": pref_name, "confirmations": count})

        if provisional:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.WARN,
                reason="Provisional preferences applied (Phase 4 learning)",
                details={"provisional": provisional, "confirmed": confirmed}
            ))
            return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"All {len(confirmed)} learned preferences confirmed",
            details={"confirmed": confirmed}
        ))
        return GateResult.PASS


# ==============================================================================
# REWARD LAW 01 — Narrative Over Metric Gate
# ==============================================================================

class NarrativeOverMetricGate(DoctrineGate):
    """
    Validates that technical correctness (identity scores) aligns with dramatic function.

    A shot can be technically perfect but dramatically wrong.
    This gate catches that mismatch.
    """

    def __init__(self):
        super().__init__(
            gate_name="REWARD_LAW_01",
            gate_position="post_generation",
            description="Narrative Over Metric — verify dramatic function vs technical quality"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Validate that visual grammar matches dramatic function.

        Args:
            shot: shot_plan entry with _dramatic_function tag
            context: may contain visual_grammar classification

        Returns:
            GateResult.WARN if technically clean but dramatically wrong
            GateResult.PASS if no dramatic function tag or match found
        """
        dramatic_function = shot.get("_dramatic_function")

        if not dramatic_function:
            # No dramatic function assigned — can't evaluate
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No dramatic function tag",
                details={}
            ))
            return GateResult.PASS

        visual_grammar = context.get("visual_grammar_classification", {}).get(shot.get("shot_id", "unknown"))

        if not visual_grammar:
            # Can't assess without visual grammar classification
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="Visual grammar classification not available",
                details={"dramatic_function": dramatic_function}
            ))
            return GateResult.PASS

        # Check if grammar matches function
        grammar_matches = self._grammar_matches_function(dramatic_function, visual_grammar)

        if not grammar_matches:
            # Technically clean but dramatically wrong
            identity_score = context.get("identity_scores", {}).get(
                shot.get("characters", [None])[0] if shot.get("characters") else None, 0.0
            )
            is_technically_clean = identity_score >= IDENTITY_PASS_THRESHOLD

            if is_technically_clean:
                self.ledger.append(LedgerEntry(
                    gate=self.gate_name,
                    shot_id=shot.get("shot_id", "unknown"),
                    verdict=GateResult.WARN,
                    reason="Technically clean but dramatically wrong",
                    details={
                        "dramatic_function": dramatic_function,
                        "visual_grammar": visual_grammar,
                        "identity_score": identity_score,
                    }
                ))
                return GateResult.WARN

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason=f"Grammar matches function: {dramatic_function}",
            details={"visual_grammar": visual_grammar}
        ))
        return GateResult.PASS

    @staticmethod
    def _grammar_matches_function(dramatic_function: str, visual_grammar: str) -> bool:
        """Simple heuristic for function-grammar matching."""
        # Emotional peaks should use close framing
        if dramatic_function in ("emotional_peak", "revelation"):
            return "close" in visual_grammar.lower() or "MCU" in visual_grammar or "ECU" in visual_grammar
        # Establishing/transitions should be wide
        if dramatic_function in ("transition", "location_reveal"):
            return "wide" in visual_grammar.lower() or "establishing" in visual_grammar.lower()
        # Default: some match found
        return True


# ==============================================================================
# OVERRIDE LAW 01 — Mandatory Escalation Gate
# ==============================================================================

class MandatoryEscalationGate(DoctrineGate):
    """
    FINAL gate (runs LAST in post-generation sequence).
    Detects 5 escalation triggers and mandates human review.

    Escalation triggers:
    1. Three consecutive REJECTs on same shot
    2. Deviation in protected identity field
    3. Prompt hash mismatch not traced to known enrichment
    4. Gate returned no state (None/error)
    5. Scene reject rate > 20%
    """

    def __init__(self):
        super().__init__(
            gate_name="OVERRIDE_LAW_01",
            gate_position="post_generation",
            description="Mandatory Escalation — detect 5 escalation triggers"
        )

    def run(self, shot: Dict[str, Any], context: Dict[str, Any]) -> GateResult:
        """
        Check escalation triggers.

        Args:
            shot: shot_plan entry
            context: contains escalation_tracker, rejection history, etc.

        Returns:
            GateResult.REJECT + escalation if any trigger fires
            GateResult.PASS if no triggers
        """
        escalation_tracker = context.get("escalation_tracker")

        if not escalation_tracker:
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.PASS,
                reason="No escalation tracker, baseline pass",
                details={}
            ))
            return GateResult.PASS

        triggers = []

        # Trigger 1: Three consecutive REJECTs
        recent_rejections = escalation_tracker.recent_rejections_for_shot(shot.get("shot_id", "unknown"))
        if len(recent_rejections) >= 3:
            triggers.append({
                "trigger": 1,
                "description": "Three consecutive REJECTs",
                "count": len(recent_rejections),
            })

        # Trigger 2: Identity field deviation
        protected_identity = shot.get("_protected_identity", {})
        current_identity = shot.get("_current_identity", {})
        if protected_identity and current_identity:
            for field in ["name", "canonical_appearance", "canonical_costume"]:
                if protected_identity.get(field) != current_identity.get(field):
                    triggers.append({
                        "trigger": 2,
                        "description": f"Protected identity field deviation: {field}",
                        "field": field,
                    })

        # Trigger 3: Prompt hash mismatch
        prompt_hash_before = shot.get("_prompt_hash_pregeneration")
        prompt_hash_after = shot.get("_prompt_hash_postgeneration")
        if prompt_hash_before and prompt_hash_after and prompt_hash_before != prompt_hash_after:
            enrichment_hash = shot.get("_expected_enrichment_hash")
            if enrichment_hash != prompt_hash_after:
                triggers.append({
                    "trigger": 3,
                    "description": "Prompt hash mismatch not traced to known enrichment",
                })

        # Trigger 4: Gate returned no state (error)
        if shot.get("_gate_error_count", 0) > 0:
            triggers.append({
                "trigger": 4,
                "description": "Gate error (returned None/error)",
                "error_count": shot.get("_gate_error_count", 0),
            })

        # Trigger 5: Scene reject rate > 20%
        scene_id = shot.get("scene_id", "unknown")
        scene_stats = context.get("scene_reject_stats", {}).get(scene_id, {})
        if scene_stats:
            total = scene_stats.get("total_shots", 1)
            rejects = scene_stats.get("rejected_shots", 0)
            reject_rate = rejects / total if total > 0 else 0.0
            if reject_rate > 0.20:
                triggers.append({
                    "trigger": 5,
                    "description": f"Scene reject rate > 20% ({rejects}/{total})",
                    "reject_rate": reject_rate,
                })

        if triggers:
            context["_escalation_active"] = True
            self.ledger.append(LedgerEntry(
                gate=self.gate_name,
                shot_id=shot.get("shot_id", "unknown"),
                verdict=GateResult.REJECT,
                reason="Escalation mandated",
                details={"escalation_triggers": triggers}
            ))
            return GateResult.REJECT

        self.ledger.append(LedgerEntry(
            gate=self.gate_name,
            shot_id=shot.get("shot_id", "unknown"),
            verdict=GateResult.PASS,
            reason="No escalation triggers detected",
            details={}
        ))
        return GateResult.PASS


# ==============================================================================
# CODE 01 — Source Truth Protection Utility
# ==============================================================================

class SourceTruthProtection:
    """
    Utility for protecting source truth from mutation.
    Maintains list of protected fields that generation cannot modify.
    """

    PROTECTED_FIELDS = {
        "shot_id",
        "scene_id",
        "characters",  # list of character names
        "_movie_lock_contracts",
        "_canonical_character_refs",
        "_scene_manifest_truth",
        "_prompt_authority_gate_result",
    }

    @classmethod
    def take_snapshot(cls, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Take immutable snapshot of protected fields.

        Args:
            project_data: full project dict (shot_plan, cast_map, etc.)

        Returns:
            Frozen dict of protected fields
        """
        snapshot = {}

        for field in cls.PROTECTED_FIELDS:
            if field in project_data:
                value = project_data[field]
                # Deep copy to freeze
                snapshot[field] = json.loads(json.dumps(value, default=str))

        return snapshot

    @classmethod
    def validate_no_mutation(
        cls,
        before_snapshot: Dict[str, Any],
        after_snapshot: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect mutations in protected fields.

        Args:
            before_snapshot: snapshot before generation
            after_snapshot: snapshot after generation

        Returns:
            List of violations (empty if clean)
        """
        violations = []

        for field in cls.PROTECTED_FIELDS:
            before = before_snapshot.get(field)
            after = after_snapshot.get(field)

            if before != after:
                violations.append({
                    "field": field,
                    "before": before,
                    "after": after,
                    "severity": "CRITICAL",
                })

        return violations


# ==============================================================================
# CODE 10 — Language Discipline Transformer
# ==============================================================================

class LanguageDiscipline:
    """
    Utility for prompt hygiene: compression, brand stripping, deduplication, negatives.
    """

    BRAND_JARGON = [
        r"\bARRI\s+Alexa\b",
        r"\bRED\s+DSMC\b",
        r"\bSony\s+Venice\b",
        r"\bPanavision\b",
        r"\bKodak\s+Vision3\b",
        r"\bFuji\s+Eterna\b",
        r"35mm\s+film\s+stock",
    ]

    DUPLICATE_ATMOSPHERE = [
        "cinematic", "dramatic", "moody", "atmospheric",
        "warm", "cold", "golden", "amber", "teal",
        "candlelit", "moonlit", "sunlit",
    ]

    @classmethod
    def compress_prompt(cls, prompt: str, target_budget: int) -> str:
        """
        Compress prompt to word budget.

        Args:
            prompt: original prompt
            target_budget: target word count

        Returns:
            Compressed prompt or original if already under budget
        """
        words = prompt.split()
        if len(words) <= target_budget:
            return prompt

        # Keep first 70% and last 30% of budget (preserves first frame setup and negatives)
        keep_first = int(target_budget * 0.7)
        keep_last = target_budget - keep_first

        compressed = " ".join(words[:keep_first]) + " ... " + " ".join(words[-keep_last:])
        return compressed

    @classmethod
    def strip_brand_jargon(cls, prompt: str) -> str:
        """Remove camera brand names, film stocks, etc."""
        result = prompt
        for pattern in cls.BRAND_JARGON:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        return result

    @classmethod
    def strip_duplicate_tokens(cls, prompt: str) -> str:
        """Remove repeated atmosphere/mood tokens."""
        words = prompt.split()
        seen = set()
        result = []

        for word in words:
            word_lower = word.lower().rstrip(".,!?;:")
            if word_lower not in cls.DUPLICATE_ATMOSPHERE or word_lower not in seen:
                result.append(word)
                if word_lower in cls.DUPLICATE_ATMOSPHERE:
                    seen.add(word_lower)

        return " ".join(result)

    @classmethod
    def strip_conflicting_descriptors(cls, prompt: str) -> str:
        """Remove contradictory adjective pairs."""
        conflicts = [
            (r"bright.*dark", ""),
            (r"warm.*cold", ""),
            (r"fast.*slow", ""),
            (r"sharp.*blurry", ""),
        ]

        result = prompt
        for pattern, replacement in conflicts:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    @classmethod
    def move_negatives(cls, prompt: str) -> Tuple[str, str]:
        """
        Extract negative instructions to separate string.

        Args:
            prompt: full prompt with negatives mixed in

        Returns:
            (clean_prompt, negative_prompt)
        """
        lines = prompt.split("\n")
        clean = []
        negatives = []

        for line in lines:
            if any(word in line.lower() for word in ["NOT", "NO ", "NEVER", "AVOID", "negative"]):
                negatives.append(line)
            else:
                clean.append(line)

        return "\n".join(clean), "\n".join(negatives)

    @classmethod
    def check_budget(cls, prompt: str, budget: int) -> Tuple[bool, int]:
        """
        Check if prompt fits word budget.

        Args:
            prompt: prompt text
            budget: word limit

        Returns:
            (within_budget: bool, word_count: int)
        """
        word_count = len(prompt.split())
        return word_count <= budget, word_count


# ==============================================================================
# TOP-LEVEL RUNNERS
# ==============================================================================

def run_phase1_pre_generation(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Run all Phase 1 pre-generation gates in order.

    Gates: IDENTITY_LAW_01, EXECUTIVE_LAW_01, EXECUTIVE_LAW_02, MEMORY_LAW_01

    Args:
        shots: list of shot_plan entries
        context: global context (cast_map, scene_plan, etc.)

    Returns:
        Dict mapping shot_id to list of gate results
    """
    gates = [
        IdentityPackLockGate(),
        ShotClassificationGate(),
        ScenePlanExistenceGate(),
        PatternStabilityGate(),
    ]

    results = {}

    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        shot_results = []

        for gate in gates:
            result = gate.run(shot, context)
            shot_results.append({
                "gate": gate.gate_name,
                "result": result.value,
            })

            # Stop on REJECT
            if result == GateResult.REJECT:
                break

        results[shot_id] = shot_results

    return results


def run_phase1_post_generation(shot: Dict[str, Any], context: Dict[str, Any]) -> List[Dict]:
    """
    Run all Phase 1 post-generation gates in order.

    Gates: IDENTITY_LAW_02, CONTINUITY_LAW_01, CONTINUITY_LAW_02,
           VISION_LAW_01, NARRATIVE_OVER_METRIC, MANDATORY_ESCALATION (LAST)

    Args:
        shot: single shot_plan entry
        context: global context

    Returns:
        List of gate results
    """
    gates = [
        SimilarityRejectionGate(),
        CarryStateWriter(),
        CarryStateValidator(),
        DualScoringRequirementGate(),
        NarrativeOverMetricGate(),
        MandatoryEscalationGate(),  # ALWAYS LAST
    ]

    results = []

    for gate in gates:
        result = gate.run(shot, context)
        results.append({
            "gate": gate.gate_name,
            "result": result.value,
        })

        # MANDATORY_ESCALATION halts on REJECT
        if gate.gate_name == "OVERRIDE_LAW_01" and result == GateResult.REJECT:
            break

    return results


if __name__ == "__main__":
    # Basic test of gate initialization
    print("ATLAS Doctrine Phase 1 Foundation — Loaded")
    print(f"Identity gates: {IdentityPackLockGate.gate_name}, {SimilarityRejectionGate.gate_name}")
    print(f"Continuity gates: {CarryStateWriter.gate_name}, {CarryStateValidator.gate_name}")
    print(f"Executive gates: {ShotClassificationGate.gate_name}, {ScenePlanExistenceGate.gate_name}")
    print(f"Vision/Memory gates: {DualScoringRequirementGate.gate_name}, {PatternStabilityGate.gate_name}")
    print(f"Reward/Override gates: {NarrativeOverMetricGate.gate_name}, {MandatoryEscalationGate.gate_name}")
    print(f"Utilities: SourceTruthProtection, LanguageDiscipline")
