"""
ATLAS Doctrine Phase 3 — Executive Intelligence and Scene Planning
Implements executive laws for scene planning, peak shot protocols, and resource proportionality.

V24.2 | 2026-03-11
Author: ATLAS Production System
"""

import json
import hashlib
import re
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path

from tools.doctrine_engine import (
    GateResult,
    DoctrineGate,
    LedgerEntry,
    RunLedger,
    IDENTITY_PASS_THRESHOLD,
    CONTINUITY_PASS_THRESHOLD,
    CINEMA_PASS_THRESHOLD,
    CINEMA_REJECT_THRESHOLD,
)


class ShotClass(Enum):
    """Shot classification for resource allocation."""
    HERO = "HERO"
    CONNECTIVE = "CONNECTIVE"
    BROLL = "BROLL"
    INSERT = "INSERT"
    RESET = "RESET"


class BoundaryType(Enum):
    """Continuity boundary types between consecutive shots."""
    HARD_CONTINUOUS = "HARD_CONTINUOUS"
    SOFT_CONTINUOUS = "SOFT_CONTINUOUS"
    SCENE_BOUNDARY = "SCENE_BOUNDARY"
    REVEAL_BOUNDARY = "REVEAL_BOUNDARY"
    TIME_SKIP = "TIME_SKIP"


class ContinuityLevel(Enum):
    """Enforcement level for carry-state between shots."""
    STRICT = "STRICT"
    MODERATE = "MODERATE"
    RESET = "RESET"


@dataclass
class ScenePlan:
    """Complete execution plan for a scene."""
    scene_id: str
    shot_classes: Dict[str, str]  # shot_id → "HERO"/"CONNECTIVE"/"BROLL"/"INSERT"/"RESET"
    model_tiers: Dict[str, str]  # shot_id → "kling_pro"/"kling_standard"/"ltx2_fast"
    prompt_budgets: Dict[str, int]  # shot_id → word count
    ref_counts: Dict[str, int]  # shot_id → ref count
    peak_shots: List[str]  # shot_ids identified as emotional peaks
    event_boundaries: List[Dict[str, Any]]  # dicts with shot_index, boundary_type
    reanchor_positions: List[str]  # shot_ids where master frame reanchor occurs
    continuity_levels: Dict[str, str]  # shot_id → "STRICT"/"MODERATE"/"RESET"
    resource_distribution: Dict[str, float] = field(default_factory=dict)  # class → percentage
    boundary_types: Dict[str, str] = field(default_factory=dict)  # shot_id → boundary_type
    locked: bool = False
    plan_hash: str = ""
    generated_at: str = ""

    def compute_hash(self) -> str:
        """Compute immutable hash of this plan."""
        content = json.dumps({
            "scene_id": self.scene_id,
            "shot_classes": self.shot_classes,
            "model_tiers": self.model_tiers,
            "prompt_budgets": self.prompt_budgets,
            "peak_shots": sorted(self.peak_shots),
            "reanchor_positions": sorted(self.reanchor_positions),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class BoundaryTypeAssigner:
    """Assigns continuity boundary types between consecutive shots."""

    # Time indicators
    TIME_INDICATORS = {
        "LATER": "TIME_SKIP",
        "MOMENTS LATER": "SOFT_CONTINUOUS",
        "MORNING": "SCENE_BOUNDARY",
        "AFTERNOON": "SCENE_BOUNDARY",
        "EVENING": "SCENE_BOUNDARY",
        "NIGHT": "SCENE_BOUNDARY",
        "DAWN": "SCENE_BOUNDARY",
        "DUSK": "SCENE_BOUNDARY",
        "CONTINUOUS": "HARD_CONTINUOUS",
        "SAME": "HARD_CONTINUOUS",
    }

    # Narrative keywords indicating boundaries
    REVEAL_KEYWORDS = ["discovers", "reveals", "realizes", "suddenly", "realizes", "shock", "gasp"]
    NARRATIVE_BOUNDARY_KEYWORDS = ["years later", "next day", "later", "next morning", "fade to"]

    def assign_boundaries(
        self,
        scene_shots: List[Dict[str, Any]],
        beat_map: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Assign boundary types to all shots in a scene.

        Args:
            scene_shots: List of shot dictionaries for the scene
            beat_map: Optional beat metadata

        Returns:
            Dict mapping shot_id → boundary_type
        """
        boundaries = {}

        for i, shot in enumerate(scene_shots):
            shot_id = shot.get("shot_id", f"shot_{i}")

            if i == 0:
                # First shot is always a scene boundary (new context)
                boundaries[shot_id] = BoundaryType.SCENE_BOUNDARY.value
                continue

            prev_shot = scene_shots[i - 1]
            boundary = self._determine_boundary(shot, prev_shot, beat_map)
            boundaries[shot_id] = boundary

        return boundaries

    def _determine_boundary(
        self,
        current_shot: Dict[str, Any],
        previous_shot: Dict[str, Any],
        beat_map: Optional[Dict[str, Any]] = None
    ) -> str:
        """Determine boundary type between two consecutive shots."""

        # Check for explicit scene/location transitions
        curr_location = current_shot.get("location", "").upper()
        prev_location = previous_shot.get("location", "").upper()

        if curr_location != prev_location and curr_location and prev_location:
            return BoundaryType.SCENE_BOUNDARY.value

        # Check time-of-day changes
        curr_time = current_shot.get("time_of_day", "").upper()
        prev_time = previous_shot.get("time_of_day", "").upper()

        for indicator, btype in self.TIME_INDICATORS.items():
            if indicator in curr_time and indicator not in ["CONTINUOUS", "SAME"]:
                return btype

        # Check beat transitions
        curr_beat_id = str(current_shot.get("beat_id", "")).strip()
        prev_beat_id = str(previous_shot.get("beat_id", "")).strip()

        if curr_beat_id != prev_beat_id and curr_beat_id and prev_beat_id:
            # Check if this is a reveal-type beat transition
            beat_desc = current_shot.get("beat_description", "").lower()
            for keyword in self.REVEAL_KEYWORDS:
                if keyword in beat_desc:
                    return BoundaryType.REVEAL_BOUNDARY.value

            # Otherwise soft continuity for beat transitions
            return BoundaryType.SOFT_CONTINUOUS.value

        # Check narrative content for boundaries
        dialogue = (current_shot.get("dialogue") or "").lower()
        description = current_shot.get("description", "").lower()
        full_text = f"{dialogue} {description}".lower()

        for keyword in self.NARRATIVE_BOUNDARY_KEYWORDS:
            if keyword in full_text:
                return BoundaryType.TIME_SKIP.value

        # Default: hard continuity (same location, same beat, no time jump)
        return BoundaryType.HARD_CONTINUOUS.value

    @staticmethod
    def get_continuity_enforcement(boundary_type: str) -> Dict[str, Any]:
        """Get enforcement parameters for a boundary type.

        Returns:
            Dict with enforce_level, carry_state, and tolerance
        """
        params = {
            BoundaryType.HARD_CONTINUOUS.value: {
                "enforce_level": ContinuityLevel.STRICT.value,
                "carry_state": True,
                "tolerance": 0.05,
            },
            BoundaryType.SOFT_CONTINUOUS.value: {
                "enforce_level": ContinuityLevel.MODERATE.value,
                "carry_state": True,
                "tolerance": 0.15,
            },
            BoundaryType.SCENE_BOUNDARY.value: {
                "enforce_level": ContinuityLevel.RESET.value,
                "carry_state": False,
                "tolerance": 0.0,
            },
            BoundaryType.REVEAL_BOUNDARY.value: {
                "enforce_level": ContinuityLevel.RESET.value,
                "carry_state": False,
                "tolerance": 0.0,
            },
            BoundaryType.TIME_SKIP.value: {
                "enforce_level": ContinuityLevel.RESET.value,
                "carry_state": False,
                "tolerance": 0.0,
            },
        }
        return params.get(boundary_type, params[BoundaryType.HARD_CONTINUOUS.value])


class ScenePlanGenerator:
    """Generates comprehensive execution plans for scenes."""

    # Emotion keywords for peak detection
    PEAK_EMOTIONS = [
        "intense", "climax", "reveals", "confronts", "screams", "demands",
        "cries", "whispers", "pleads", "conflict", "breakthrough", "rupture",
        "sacrifice", "reconciliation", "betrayal", "triumph", "devastation"
    ]

    def generate(
        self,
        scene_shots: List[Dict[str, Any]],
        scene_manifest: Optional[Dict[str, Any]] = None,
        story_bible_scene: Optional[Dict[str, Any]] = None,
        cast_map: Optional[Dict[str, Any]] = None
    ) -> ScenePlan:
        """Generate complete scene plan from shots and context.

        Args:
            scene_shots: List of shot dictionaries
            scene_manifest: Optional scene metadata from manifest
            story_bible_scene: Optional scene data from story bible
            cast_map: Optional character casting data

        Returns:
            Complete ScenePlan with all fields populated
        """
        scene_id = scene_shots[0].get("scene_id", "unknown") if scene_shots else "unknown"

        # Step 1: Classify shots
        shot_classes = self._classify_shots(scene_shots)

        # Step 2: Identify emotional peaks
        peak_shots = self._identify_peak_shots(scene_shots, story_bible_scene)

        # Step 3: Identify event boundaries
        event_boundaries = self._identify_event_boundaries(scene_shots)

        # Step 4: Assign boundary types
        assigner = BoundaryTypeAssigner()
        boundary_types = assigner.assign_boundaries(scene_shots)

        # Step 5: Set reanchor positions
        reanchor_positions = self._compute_reanchor_positions(
            scene_shots, peak_shots, event_boundaries
        )

        # Step 6: Assign model tiers
        model_tiers = self._assign_model_tiers(shot_classes)

        # Step 7: Assign prompt budgets
        prompt_budgets = self._assign_prompt_budgets(shot_classes)

        # Step 8: Assign ref counts
        ref_counts = self._assign_ref_counts(shot_classes)

        # Step 9: Assign continuity levels
        continuity_levels = {
            shot.get("shot_id"): assigner.get_continuity_enforcement(
                boundary_types.get(shot.get("shot_id"), "HARD_CONTINUOUS")
            )["enforce_level"]
            for shot in scene_shots
        }

        # Step 10: Calculate resource distribution
        resource_distribution = self._calculate_resource_distribution(shot_classes)

        plan = ScenePlan(
            scene_id=scene_id,
            shot_classes=shot_classes,
            model_tiers=model_tiers,
            prompt_budgets=prompt_budgets,
            ref_counts=ref_counts,
            peak_shots=peak_shots,
            event_boundaries=event_boundaries,
            reanchor_positions=reanchor_positions,
            continuity_levels=continuity_levels,
            resource_distribution=resource_distribution,
            boundary_types=boundary_types,
            locked=True,
            generated_at=datetime.utcnow().isoformat(),
        )

        plan.plan_hash = plan.compute_hash()
        return plan

    def _classify_shots(self, scene_shots: List[Dict[str, Any]]) -> Dict[str, str]:
        """Classify each shot into HERO, CONNECTIVE, BROLL, INSERT, or RESET."""
        classifications = {}

        for shot in scene_shots:
            shot_id = shot.get("shot_id", "unknown")
            shot_type = shot.get("shot_type", "").lower()
            characters = shot.get("characters", [])
            dialogue = shot.get("dialogue", "")

            # B-roll detection
            broll_flag = shot.get("_broll", False)
            if broll_flag or "broll" in shot_type or shot.get("_no_chain", False):  # V26 DOCTRINE: suffixes are editorial, not runtime
                classifications[shot_id] = ShotClass.BROLL.value
                continue

            # Insert/detail detection
            if shot_type in ["insert", "detail", "cutaway"]:
                classifications[shot_id] = ShotClass.INSERT.value
                continue

            # Reset detection (new location, full reset)
            if shot.get("_reset_shot") or "reset" in shot_type.lower():
                classifications[shot_id] = ShotClass.RESET.value
                continue

            # Hero detection (close-ups, high emotion, dialogue)
            if (shot_type in ["close_up", "mcu", "ecu", "ocu"] or
                shot.get("_emotion_intensity", 0) >= 7 or
                len(dialogue or "") > 100):
                classifications[shot_id] = ShotClass.HERO.value
                continue

            # Default: connective
            classifications[shot_id] = ShotClass.CONNECTIVE.value

        return classifications

    def _identify_peak_shots(
        self,
        scene_shots: List[Dict[str, Any]],
        story_bible_scene: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Identify emotionally significant shots (peaks)."""
        peaks = []

        for shot in scene_shots:
            shot_id = shot.get("shot_id", "")
            emotion_intensity = shot.get("_emotion_intensity", 0) or shot.get("state_out", {}).get("emotion_intensity", 0)
            beat_description = shot.get("beat_description", "").lower()
            dialogue = ( shot.get('dialogue') or '' ).lower()
            full_text = f"{beat_description} {dialogue}".lower()

            # Emotion threshold check
            if emotion_intensity >= 8:
                peaks.append(shot_id)
                continue

            # Keyword check
            for keyword in self.PEAK_EMOTIONS:
                if keyword in full_text:
                    peaks.append(shot_id)
                    break

            # Dialogue conflict markers
            conflict_words = ["demands", "screams", "whispers", "pleads", "confronts", "betrays"]
            for word in conflict_words:
                if word in dialogue:
                    peaks.append(shot_id)
                    break

        return peaks

    def _identify_event_boundaries(self, scene_shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify narrative event boundaries (beat transitions, reveals, etc.)."""
        boundaries = []

        for i, shot in enumerate(scene_shots):
            if i == 0:
                continue

            prev_shot = scene_shots[i - 1]
            curr_beat_id = str(shot.get("beat_id", "")).strip()
            prev_beat_id = str(prev_shot.get("beat_id", "")).strip()

            if curr_beat_id != prev_beat_id and curr_beat_id and prev_beat_id:
                boundaries.append({
                    "shot_index": i,
                    "shot_id": shot.get("shot_id"),
                    "boundary_type": "BEAT_TRANSITION",
                    "from_beat": prev_beat_id,
                    "to_beat": curr_beat_id,
                })

        return boundaries

    def _compute_reanchor_positions(
        self,
        scene_shots: List[Dict[str, Any]],
        peak_shots: List[str],
        event_boundaries: List[Dict[str, Any]]
    ) -> List[str]:
        """Compute positions where master frame reanchoring should occur."""
        reanchor = []

        # Every 5th shot
        for i, shot in enumerate(scene_shots):
            if i % 5 == 0:
                reanchor.append(shot.get("shot_id"))

        # At every peak shot
        reanchor.extend(peak_shots)

        # At every event boundary
        for boundary in event_boundaries:
            reanchor.append(boundary.get("shot_id"))

        # Remove duplicates and sort
        return sorted(set(reanchor))

    def _assign_model_tiers(self, shot_classes: Dict[str, str]) -> Dict[str, str]:
        """Assign model tiers based on shot classification."""
        tiers = {}
        for shot_id, shot_class in shot_classes.items():
            if shot_class == ShotClass.HERO.value:
                tiers[shot_id] = "kling_pro"
            elif shot_class == ShotClass.CONNECTIVE.value:
                tiers[shot_id] = "kling_standard"
            else:
                tiers[shot_id] = "ltx2_fast"

        return tiers

    def _assign_prompt_budgets(self, shot_classes: Dict[str, str]) -> Dict[str, int]:
        """Assign word count budgets for prompts."""
        budgets = {}
        budgets_by_class = {
            ShotClass.HERO.value: 200,
            ShotClass.CONNECTIVE.value: 120,
            ShotClass.BROLL.value: 60,
            ShotClass.INSERT.value: 60,
            ShotClass.RESET.value: 80,
        }

        for shot_id, shot_class in shot_classes.items():
            budgets[shot_id] = budgets_by_class.get(shot_class, 100)

        return budgets

    def _assign_ref_counts(self, shot_classes: Dict[str, str]) -> Dict[str, int]:
        """Assign maximum reference image counts."""
        ref_counts = {}
        counts_by_class = {
            ShotClass.HERO.value: 3,
            ShotClass.CONNECTIVE.value: 2,
            ShotClass.BROLL.value: 0,
            ShotClass.INSERT.value: 1,
            ShotClass.RESET.value: 1,
        }

        for shot_id, shot_class in shot_classes.items():
            ref_counts[shot_id] = counts_by_class.get(shot_class, 1)

        return ref_counts

    def _calculate_resource_distribution(self, shot_classes: Dict[str, str]) -> Dict[str, float]:
        """Calculate percentage resource distribution by class."""
        class_counts = {}
        for shot_class in shot_classes.values():
            class_counts[shot_class] = class_counts.get(shot_class, 0) + 1

        total = sum(class_counts.values())
        if total == 0:
            return {}

        # Weight by shot class resource intensity
        weights = {
            ShotClass.HERO.value: 5.0,
            ShotClass.CONNECTIVE.value: 2.0,
            ShotClass.BROLL.value: 0.5,
            ShotClass.INSERT.value: 0.5,
            ShotClass.RESET.value: 1.5,
        }

        weighted_totals = {
            cls: class_counts.get(cls, 0) * weights.get(cls, 1.0)
            for cls in [ShotClass.HERO.value, ShotClass.CONNECTIVE.value,
                        ShotClass.BROLL.value, ShotClass.INSERT.value, ShotClass.RESET.value]
        }

        total_weight = sum(weighted_totals.values())
        if total_weight == 0:
            return {cls: 0.0 for cls in weighted_totals}

        return {
            cls: round((weighted_totals[cls] / total_weight) * 100, 2)
            for cls in weighted_totals
        }


class MandatoryScenePlanGate(DoctrineGate):
    """EXECUTIVE LAW 03 — Validates scene plan exists and is complete."""

    def __init__(self, project_path: str):
        """Initialize gate."""
        super().__init__(gate_name="EXECUTIVE_LAW_03_RESOURCE_PROPORTIONALITY", gate_position="scene_initialization", project_path=project_path)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Validate scene plan for the shot's scene.

        Args:
            shot: Shot dictionary
            context: Generation context with _scene_plans

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        context = context or {}
        scene_id = shot.get("scene_id", "unknown")
        shot_id = shot.get("shot_id", "unknown")

        scene_plans = context.get("_scene_plans", {})
        plan = scene_plans.get(scene_id)

        if not plan:
            return GateResult.REJECT

        # Validate required fields
        required_fields = [
            "shot_classes", "model_tiers", "prompt_budgets", "ref_counts",
            "peak_shots", "event_boundaries", "reanchor_positions",
            "continuity_levels"
        ]

        missing_fields = [f for f in required_fields if not getattr(plan, f, None)]

        if missing_fields:
            # Try to auto-fill
            for field_name in missing_fields:
                if not getattr(plan, field_name, None):
                    setattr(plan, field_name, {})

            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=GateResult.WARN.value,
                deviation_score=0.3,
                deviation_type="planning",
                correction_applied=True,
                model_used="executor",
                prompt_hash=self._compute_prompt_hash(""),
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="SCENE_PLAN_AUTO_FILLED",
                extra_data={"missing_fields": missing_fields}
            )
            self._write_ledger(entry)
            return GateResult.WARN

        return GateResult.PASS


class PeakShotProtocolGate(DoctrineGate):
    """EXECUTIVE LAW 04 — Enforces quality upgrades for peak shots."""

    def __init__(self, project_path: str):
        """Initialize gate."""
        super().__init__(gate_name="EXECUTIVE_LAW_04_SHOT_BUDGET", gate_position="pre_generation", project_path=project_path)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Apply peak shot protocol to enhance hero/peak shots.

        Args:
            shot: Shot dictionary
            context: Generation context with _scene_plans

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        context = context or {}
        scene_id = shot.get("scene_id", "unknown")
        shot_id = shot.get("shot_id", "unknown")

        scene_plans = context.get("_scene_plans", {})
        plan = scene_plans.get(scene_id)

        if not plan:
            return GateResult.PASS  # Plan doesn't exist yet, skip

        # Check if this is a peak shot
        is_peak = shot_id in plan.peak_shots or \
                  plan.shot_classes.get(shot_id) == ShotClass.HERO.value

        if not is_peak:
            return GateResult.PASS

        upgrades_applied = []

        # Upgrade 1: Model must be kling_pro
        current_model = plan.model_tiers.get(shot_id, "ltx2_fast")
        if current_model != "kling_pro":
            plan.model_tiers[shot_id] = "kling_pro"
            shot["_model_tier"] = "kling_pro"
            upgrades_applied.append("MODEL_UPGRADED_TO_KLING_PRO")

        # Upgrade 2: Ref count must be maximum (3)
        current_refs = plan.ref_counts.get(shot_id, 0)
        if current_refs < 3:
            plan.ref_counts[shot_id] = 3
            shot["_max_refs"] = 3
            upgrades_applied.append("REF_COUNT_UPGRADED_TO_3")

        # Upgrade 3: Prompt budget extended to 200+
        current_budget = plan.prompt_budgets.get(shot_id, 0)
        if current_budget < 200:
            plan.prompt_budgets[shot_id] = 200
            shot["_prompt_budget"] = 200
            upgrades_applied.append("PROMPT_BUDGET_EXTENDED_TO_200")

        # Upgrade 4: Force Phase 5 scoring
        shot["_require_cinema_scoring"] = True
        upgrades_applied.append("CINEMA_SCORING_REQUIRED")

        # Upgrade 5: Raise identity threshold
        shot["_identity_threshold"] = 0.95
        upgrades_applied.append("IDENTITY_THRESHOLD_RAISED_TO_0.95")

        shot["_peak_upgrades_applied"] = upgrades_applied

        # Determine result
        if len(upgrades_applied) == 5:
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=GateResult.PASS.value,
                deviation_score=0.0,
                deviation_type="planning",
                correction_applied=False,
                model_used="executor",
                prompt_hash=self._compute_prompt_hash(""),
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="PEAK_SHOT_PROTOCOL_COMPLETE",
                extra_data={"upgrades": upgrades_applied}
            )
            self._write_ledger(entry)
            return GateResult.PASS
        else:
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=GateResult.WARN.value,
                deviation_score=0.2,
                deviation_type="planning",
                correction_applied=True,
                model_used="executor",
                prompt_hash=self._compute_prompt_hash(""),
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="PEAK_SHOT_PARTIAL_UPGRADE",
                extra_data={"upgrades": upgrades_applied, "total": 5}
            )
            self._write_ledger(entry)
            return GateResult.WARN


class ResourceProportionalityGate(DoctrineGate):
    """EXECUTIVE LAW 05 — Validates resource distribution across shot classes."""

    def __init__(self, project_path: str):
        """Initialize gate."""
        super().__init__(gate_name="EXECUTIVE_LAW_05_MODEL_TIER", gate_position="scene_initialization", project_path=project_path)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Validate resource proportionality for a scene.

        Args:
            shot: Any shot from the scene (used to identify scene_id)
            context: Generation context with scene shots

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        context = context or {}
        scene_id = shot.get("scene_id", "unknown")
        shot_id = shot.get("shot_id", "unknown")

        # Get all shots for this scene
        scene_shots = context.get("_scene_shots", {}).get(scene_id, [])
        if not scene_shots:
            return GateResult.PASS  # Can't validate without scene data

        scene_plans = context.get("_scene_plans", {})
        plan = scene_plans.get(scene_id)
        if not plan:
            return GateResult.PASS

        # Calculate actual resource distribution
        hero_shots = [s for s in scene_shots if plan.shot_classes.get(s.get("shot_id")) == ShotClass.HERO.value]
        other_shots = [s for s in scene_shots if plan.shot_classes.get(s.get("shot_id")) != ShotClass.HERO.value]

        # Model costs: kling_pro=3.0, kling_standard=2.0, ltx2_fast=1.0
        model_costs = {"kling_pro": 3.0, "kling_standard": 2.0, "ltx2_fast": 1.0}

        def compute_cost(shots: List[Dict[str, Any]]) -> float:
            total = 0.0
            for s in shots:
                sid = s.get("shot_id")
                model = plan.model_tiers.get(sid, "ltx2_fast")
                refs = plan.ref_counts.get(sid, 1)
                budget = plan.prompt_budgets.get(sid, 100)
                cost = model_costs.get(model, 1.0) * refs * (budget / 100.0)
                total += cost
            return total

        hero_cost = compute_cost(hero_shots)
        other_cost = compute_cost(other_shots)
        total_cost = hero_cost + other_cost

        if total_cost == 0:
            return GateResult.PASS

        hero_pct = (hero_cost / total_cost) * 100
        other_pct = 100 - hero_pct

        # Validate proportions
        hero_ceiling = 60.0
        other_ceiling = 40.0

        violations = []

        if hero_pct > hero_ceiling:
            violations.append(f"HERO_OVERALLOCATED_{hero_pct:.1f}pct")

        if other_pct > other_ceiling:
            violations.append(f"OTHER_OVERALLOCATED_{other_pct:.1f}pct")

        if violations:
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=GateResult.REJECT.value,
                deviation_score=abs(hero_pct - 50.0) / 100.0,
                deviation_type="resource_allocation",
                correction_applied=False,
                model_used="executor",
                prompt_hash=self._compute_prompt_hash(""),
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="RESOURCE_DISPROPORTION",
                extra_data={
                    "hero_pct": round(hero_pct, 2),
                    "other_pct": round(other_pct, 2),
                    "violations": violations
                }
            )
            self._write_ledger(entry)
            return GateResult.REJECT

        return GateResult.PASS


def run_phase3_scene_initialization(
    scene_shots: List[Dict[str, Any]],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Phase 3 initialization: generate scene plan and validate resources.

    Args:
        scene_shots: All shots in the scene
        context: Shared generation context

    Returns:
        Dict with initialization results
    """
    if not scene_shots:
        return {"status": "EMPTY_SCENE", "scene_id": "unknown"}

    scene_id = scene_shots[0].get("scene_id", "unknown")
    project_path = context.get("project_path", ".")

    # Step 1: Assign boundary types
    assigner = BoundaryTypeAssigner()
    boundaries = assigner.assign_boundaries(scene_shots, context.get("beat_map", {}))

    for shot in scene_shots:
        shot_id = shot.get("shot_id")
        shot["_boundary_type"] = boundaries.get(shot_id, BoundaryType.HARD_CONTINUOUS.value)

    # Step 2: Generate scene plan if not exists
    if scene_id not in context.get("_scene_plans", {}):
        generator = ScenePlanGenerator()
        plan = generator.generate(
            scene_shots,
            context.get("scene_manifest"),
            context.get("story_bible_scene"),
            context.get("cast_map")
        )
        context.setdefault("_scene_plans", {})[scene_id] = plan

    # Store scene shots in context for resource validation
    context.setdefault("_scene_shots", {})[scene_id] = scene_shots

    # Step 3: Validate scene plan exists
    plan_gate = MandatoryScenePlanGate(project_path)
    plan_result = plan_gate.run(scene_shots[0], context)

    # Step 4: Check resource proportionality
    resource_gate = ResourceProportionalityGate(project_path)
    resource_result = resource_gate.run(scene_shots[0], context)

    plan = context.get("_scene_plans", {}).get(scene_id)

    return {
        "scene_id": scene_id,
        "status": "INITIALIZED",
        "plan_result": plan_result.value,
        "resource_result": resource_result.value,
        "boundaries_assigned": len(boundaries),
        "peak_shots": plan.peak_shots if plan else [],
        "total_shots": len(scene_shots),
        "resource_distribution": plan.resource_distribution if plan else {},
    }


def run_phase3_pre_generation(
    shot: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Phase 3 pre-generation: apply peak shot protocol.

    Args:
        shot: Shot being prepared
        context: Shared generation context

    Returns:
        Dict with gate result and any upgrades applied
    """
    project_path = context.get("project_path", ".")
    peak_gate = PeakShotProtocolGate(project_path)
    result = peak_gate.run(shot, context)

    upgrades = shot.get("_peak_upgrades_applied", [])

    return {
        "gate": "EXECUTIVE_LAW_04",
        "result": result.value,
        "shot_id": shot.get("shot_id"),
        "upgrades_applied": upgrades,
        "model_tier": shot.get("_model_tier"),
        "max_refs": shot.get("_max_refs"),
        "identity_threshold": shot.get("_identity_threshold"),
    }
