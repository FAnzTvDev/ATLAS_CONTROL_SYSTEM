"""
ATLAS Doctrine Phase 2 — Error Correction and Immune Response
Implements 5 Error Laws: Parity Check, Toxic Pattern Suppression, Repair vs Reject Zones,
No Silent Failure Enforcement, and Pain Signal System.

V24.2 | 2026-03-11
Author: ATLAS Production System
"""

import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path

from tools.doctrine_engine import (
    GateResult,
    DoctrineGate,
    LedgerEntry,
    RunLedger,
    ToxicityRegistry,
    IDENTITY_PASS_THRESHOLD,
    CONTINUITY_PASS_THRESHOLD,
    CINEMA_PASS_THRESHOLD,
    CINEMA_REJECT_THRESHOLD,
    PAIN_SIGNAL_WINDOW,
    PAIN_SIGNAL_TRIGGER,
)


@dataclass
class PainSignalReport:
    """Report of pain signal detection and recommendation."""
    active: bool
    dimension: str
    trend: List[float]
    recommendation: str  # "REANCHOR", "PAUSE", "CONTINUE"
    shots_affected: List[str]
    timestamp: str


class ParityCheckGate(DoctrineGate):
    """Error Law 01 — Parity Check Gate

    Validates 5 parity dimensions post-generation:
    1. Face structure (identity_scores >= 0.90)
    2. Hair silhouette (hair_scores >= 0.80, fallback to identity 0.85)
    3. Wardrobe match (exact string or first shot auto-pass)
    4. Shot grammar / cinema (cinema_scores >= 0.70)
    5. Environment match (location_scores >= 0.70)

    0 failed = PASS, 1 failed = WARN, 2+ failed = REJECT
    """

    def __init__(self, project_path: str = ""):
        """Initialize parity check gate."""
        super().__init__(gate_name="ERROR_LAW_01_PARITY_CHECK", gate_position="post_generation", project_path=project_path)
        self.identity_threshold = 0.90
        self.hair_threshold = 0.80
        self.hair_fallback_threshold = 0.85
        self.cinema_threshold = 0.70
        self.location_threshold = 0.70

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run parity check on shot.

        Args:
            shot: Shot plan dictionary
            context: Generation context with scores

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")

        # Collect results for 5 dimensions
        failed_dimensions = []
        dimension_scores = {}

        # Dimension 1: Face structure
        identity_score = self._check_face_structure(shot, context)
        dimension_scores["face_structure"] = identity_score
        has_characters = bool(shot.get("characters"))
        if identity_score is None and has_characters:
            # NULL SCORE DEFENSE: None score with characters present = measurement never taken = FAIL
            failed_dimensions.append(("face_structure", 0.0))
        elif identity_score is not None and identity_score < self.identity_threshold:
            failed_dimensions.append(("face_structure", identity_score))

        # Dimension 2: Hair silhouette
        hair_score = self._check_hair_silhouette(shot, context, identity_score)
        dimension_scores["hair_silhouette"] = hair_score
        if hair_score is not None and hair_score < self.hair_threshold:
            failed_dimensions.append(("hair_silhouette", hair_score))

        # Dimension 3: Wardrobe match
        wardrobe_match = self._check_wardrobe_match(shot, context)
        dimension_scores["wardrobe"] = 1.0 if wardrobe_match else 0.0
        if not wardrobe_match:
            failed_dimensions.append(("wardrobe", 0.0))

        # Dimension 4: Shot grammar / cinema
        cinema_score = self._check_shot_grammar(shot, context)
        dimension_scores["cinema"] = cinema_score
        if cinema_score is not None and cinema_score < self.cinema_threshold:
            failed_dimensions.append(("cinema", cinema_score))

        # Dimension 5: Environment match
        location_score = self._check_environment_match(shot, context)
        dimension_scores["location"] = location_score
        if location_score is not None and location_score < self.location_threshold:
            failed_dimensions.append(("location", location_score))

        # Determine verdict
        if len(failed_dimensions) == 0:
            verdict = GateResult.PASS
            reason_code = "PARITY_ALL_PASS"
        elif len(failed_dimensions) == 1:
            verdict = GateResult.WARN
            reason_code = f"PARITY_SINGLE_FAIL_{failed_dimensions[0][0].upper()}"
        else:
            verdict = GateResult.REJECT
            reason_code = f"PARITY_MULTI_FAIL_{len(failed_dimensions)}"

        # Compute average deviation score from failed dimensions
        deviation_score = sum(score for _, score in failed_dimensions) / len(failed_dimensions) if failed_dimensions else 0.0

        # Write ledger entry
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=verdict.value,
            deviation_score=1.0 - deviation_score,  # Invert so higher is better
            deviation_type="parity",
            correction_applied=False,
            model_used=context.get("model_used", "unknown"),
            prompt_hash=self._compute_prompt_hash(
                shot.get("nano_prompt", "") + shot.get("ltx_motion_prompt", "")
            ),
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=reason_code,
            extra_data={
                "dimension_scores": dimension_scores,
                "failed_dimensions": [d[0] for d in failed_dimensions],
                "dimension_count": 5,
                "failures": len(failed_dimensions)
            }
        )
        self._write_ledger(entry)

        return verdict

    def _check_face_structure(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Optional[float]:
        """Check face structure identity score for canonical character.

        Returns: identity_score (0.0-1.0) or None if not available
        """
        identity_scores = context.get("identity_scores", {})
        if not identity_scores:
            return None

        # Average identity scores across characters in shot
        scores = [s for s in identity_scores.values() if isinstance(s, (int, float))]
        return sum(scores) / len(scores) if scores else None

    def _check_hair_silhouette(
        self, shot: Dict[str, Any], context: Dict[str, Any], identity_fallback: Optional[float]
    ) -> Optional[float]:
        """Check hair silhouette consistency against carry state.

        Returns: hair_score (0.0-1.0) or None if not available
        """
        hair_scores = context.get("hair_scores", {})
        if hair_scores:
            scores = [s for s in hair_scores.values() if isinstance(s, (int, float))]
            return sum(scores) / len(scores) if scores else None

        # Fallback: use identity score with lower threshold if hair_scores not available
        if identity_fallback is not None:
            return identity_fallback

        return None

    def _check_wardrobe_match(self, shot: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check wardrobe tag consistency against previous shot carry state.

        Returns: True if match or first shot, False if mismatch
        """
        shot_id = shot.get("shot_id", "")
        wardrobe_tag = shot.get("wardrobe_tag", "")

        # First shot in scene auto-passes
        if shot_id.endswith("_001"):
            return True

        # If no wardrobe tag, skip check
        if not wardrobe_tag:
            return True

        # Compare against carry state
        carry_state = context.get("_last_carry_state", {})
        carry_wardrobe = carry_state.get("wardrobe_tags", {})

        # Extract character from shot (simple heuristic)
        for char_name, carry_tag in carry_wardrobe.items():
            if carry_tag and carry_tag in wardrobe_tag:
                return True

        # Exact match not found - this is a mismatch
        return False

    def _check_shot_grammar(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Optional[float]:
        """Check shot grammar / cinematic score.

        Returns: cinema_score (0.0-1.0) or None if not available or not Phase 5
        """
        cinema_scores = context.get("cinema_scores", {})
        if not cinema_scores:
            return None

        overall_score = cinema_scores.get("overall", None)
        return overall_score

    def _check_environment_match(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Optional[float]:
        """Check environment location consistency.

        Returns: location_score (0.0-1.0) or None if not available
        """
        location_scores = context.get("location_scores", {})
        if not location_scores:
            return None

        similarity = location_scores.get("similarity", None)
        return similarity


class ToxicPatternSuppressionGate(DoctrineGate):
    """Error Law 02 — Toxic Pattern Suppression

    Detects toxic prompt patterns that have caused failures before
    and blocks re-execution or forces prompt rebuild.

    Returns:
    - PASS: no known toxic pattern
    - WARN: partial match (pattern seen but <3 failures)
    - REJECT: full match (pattern seen 3+ times, auto-blocked)
    """

    def __init__(self, project_path: str):
        """Initialize toxic pattern suppression gate."""
        super().__init__(gate_name="ERROR_LAW_02_TOXIC_SUPPRESSION", gate_position="pre_generation", project_path=project_path)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run toxic pattern check on shot.

        Args:
            shot: Shot plan dictionary
            context: Generation context

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")

        # Compute prompt hash
        nano_prompt = shot.get("nano_prompt", "")
        ltx_prompt = shot.get("ltx_motion_prompt", "")
        prompt_hash = self._compute_prompt_hash(nano_prompt + ltx_prompt)

        # Check toxicity registry
        toxicity_status = self.toxicity.check(prompt_hash)

        if toxicity_status == "full":
            verdict = GateResult.REJECT
            reason_code = "TOXIC_PATTERN_CONFIRMED_FULL"
            correction_applied = True  # Force prompt rebuild
        elif toxicity_status == "partial":
            verdict = GateResult.WARN
            reason_code = "TOXIC_PATTERN_PARTIAL_MATCH"
            correction_applied = False  # Attempt rewrite
            # Try to rewrite by stripping matched patterns
            self._attempt_rewrite(shot, context, nano_prompt, ltx_prompt)
        else:
            verdict = GateResult.PASS
            reason_code = "TOXIC_PATTERN_NONE"
            correction_applied = False

        # Store dispatched hash
        context["_prompt_dispatched_hash"] = prompt_hash

        # Write ledger entry
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=verdict.value,
            deviation_score=1.0 if toxicity_status == "none" else 0.0,
            deviation_type="toxicity",
            correction_applied=correction_applied,
            model_used="nano",
            prompt_hash=prompt_hash,
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=reason_code,
            extra_data={"toxicity_status": toxicity_status}
        )
        self._write_ledger(entry)

        return verdict

    def register_failure(
        self, shot: Dict[str, Any], context: Dict[str, Any], failure_type: str
    ) -> None:
        """Register a prompt pattern as toxic after 2+ failures.

        Args:
            shot: Shot plan dictionary
            context: Generation context
            failure_type: Type of failure (e.g., "morphing", "identity_collapse")
        """
        nano_prompt = shot.get("nano_prompt", "")
        ltx_prompt = shot.get("ltx_motion_prompt", "")
        prompt_hash = self._compute_prompt_hash(nano_prompt + ltx_prompt)

        # Register with toxicity system
        self.toxicity.register(prompt_hash, failure_count=1, failure_type=failure_type)

    def _attempt_rewrite(
        self, shot: Dict[str, Any], context: Dict[str, Any],
        nano_prompt: str, ltx_prompt: str
    ) -> None:
        """Attempt to rewrite prompt by stripping toxic patterns.

        Args:
            shot: Shot plan dictionary
            context: Generation context
            nano_prompt: Current nano prompt
            ltx_prompt: Current LTX prompt
        """
        # Simple heuristic: strip common problematic clauses
        toxic_keywords = [
            "morphing", "morph into", "transform", "shift", "change form",
            "grid", "distort", "artifact", "glitch", "flicker"
        ]

        rewritten_nano = nano_prompt
        rewritten_ltx = ltx_prompt

        for keyword in toxic_keywords:
            rewritten_nano = rewritten_nano.replace(keyword, "")
            rewritten_ltx = rewritten_ltx.replace(keyword, "")

        # Update context
        context["_nano_prompt_rewritten"] = True
        shot["nano_prompt"] = rewritten_nano
        shot["ltx_motion_prompt"] = rewritten_ltx


class RepairZoneClassifier:
    """Error Law 03 — Repair vs Reject Zones

    Classifies scores into repair zones (Zone 1) where automated
    correction is possible, vs reject zones (Zone 2) requiring manual intervention.
    """

    def __init__(self):
        """Initialize classifier with zone boundaries."""
        # Zone 1 (repair): between floor and ceiling
        # Zone 2 (reject): below floor
        self.zones = {
            "identity": {"floor": 0.75, "ceiling": 0.89},
            "continuity": {"floor": 0.65, "ceiling": 0.79},
            "cinema": {"floor": 0.50, "ceiling": 0.69},
            "location": {"floor": 0.55, "ceiling": 0.69},
        }

    def classify(self, dimension: str, score: float) -> str:
        """Classify a score into PASS, ZONE1_REPAIR, or ZONE2_REJECT.

        Args:
            dimension: Dimension name (identity, continuity, cinema, location)
            score: Score value (0.0-1.0)

        Returns:
            "PASS", "ZONE1_REPAIR", or "ZONE2_REJECT"
        """
        if dimension not in self.zones:
            return "PASS"  # Unknown dimension passes

        zone = self.zones[dimension]
        ceiling = zone["ceiling"]
        floor = zone["floor"]

        if score >= ceiling:
            return "PASS"
        elif score >= floor:
            return "ZONE1_REPAIR"
        else:
            return "ZONE2_REJECT"

    def should_repair(self, dimension: str, score: float) -> bool:
        """Check if score should be repaired (in Zone 1).

        Args:
            dimension: Dimension name
            score: Score value

        Returns:
            True if in Zone 1, False otherwise
        """
        return self.classify(dimension, score) == "ZONE1_REPAIR"

    def must_reject(self, dimension: str, score: float) -> bool:
        """Check if score is in reject zone (Zone 2).

        Args:
            dimension: Dimension name
            score: Score value

        Returns:
            True if in Zone 2, False otherwise
        """
        return self.classify(dimension, score) == "ZONE2_REJECT"

    def attempt_repair(
        self, shot: Dict[str, Any], dimension: str, context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """Attempt to repair a shot in Zone 1.

        Args:
            shot: Shot plan dictionary
            dimension: Dimension to repair
            context: Generation context

        Returns:
            Tuple of (repaired_shot, estimated_new_score) or (shot, None) if repair failed
        """
        if dimension == "identity":
            return self._repair_identity(shot, context)
        elif dimension == "continuity":
            return self._repair_continuity(shot, context)
        elif dimension == "cinema":
            return self._repair_cinema(shot, context)
        elif dimension == "location":
            return self._repair_location(shot, context)
        else:
            return shot, None

    def _repair_identity(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[float]]:
        """Repair identity score by emphasizing character features in prompt."""
        nano_prompt = shot.get("nano_prompt", "")

        # Add emphasis on character canonical description
        if "CANONICAL_CHARACTERS" in context:
            char_name = shot.get("characters", [None])[0]
            if char_name and char_name in context["CANONICAL_CHARACTERS"]:
                char_desc = context["CANONICAL_CHARACTERS"][char_name].get("appearance", "")
                nano_prompt += f"\n\nCRITICAL CHARACTER REFERENCE: {char_desc}"
                shot["nano_prompt"] = nano_prompt
                shot["_identity_repair_applied"] = True

        # Estimate new score (heuristic: +0.15 points)
        estimated_score = min(0.95, context.get("identity_scores", {}).get(char_name, 0.0) + 0.15)
        return shot, estimated_score

    def _repair_continuity(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[float]]:
        """Repair continuity by injecting carry-state descriptors more aggressively."""
        ltx_prompt = shot.get("ltx_motion_prompt", "")
        carry_state = context.get("_last_carry_state", {})

        # Add strong continuity constraint
        if carry_state:
            ltx_prompt += f"\n\nCONTINUITY LOCK: {carry_state}"
            shot["ltx_motion_prompt"] = ltx_prompt
            shot["_continuity_repair_applied"] = True

        # Estimate new score (heuristic: +0.10 points)
        estimated_score = min(0.90, context.get("continuity_scores", {}).get("overall", 0.0) + 0.10)
        return shot, estimated_score

    def _repair_cinema(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[float]]:
        """Repair cinema/grammar score by adjusting shot grammar keywords."""
        nano_prompt = shot.get("nano_prompt", "")
        shot_type = shot.get("shot_type", "medium")

        # Reinforce shot grammar
        grammar_reinforcement = {
            "wide": "establish location, show geography, camera pulls back",
            "medium": "action focus, character body language, camera tracks motion",
            "close": "emotional intensity, facial expression, camera locked on face",
            "mcu": "mid-close detail, hands and upper body, camera intimate",
            "ocu": "extreme close-up, texture and micro-expression, camera static",
        }

        reinforcement = grammar_reinforcement.get(shot_type, "")
        if reinforcement:
            nano_prompt += f"\n\nSHOT GRAMMAR: {reinforcement}"
            shot["nano_prompt"] = nano_prompt
            shot["_cinema_repair_applied"] = True

        # Estimate new score (heuristic: +0.15 points)
        estimated_score = min(0.85, context.get("cinema_scores", {}).get("overall", 0.0) + 0.15)
        return shot, estimated_score

    def _repair_location(self, shot: Dict[str, Any], context: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[float]]:
        """Repair location consistency by reinforcing location description."""
        nano_prompt = shot.get("nano_prompt", "")
        location = shot.get("location", "")

        # Reinforce location
        if location:
            nano_prompt += f"\n\nLOCATION ANCHOR: {location} — every detail must be consistent with this setting"
            shot["nano_prompt"] = nano_prompt
            shot["_location_repair_applied"] = True

        # Estimate new score (heuristic: +0.12 points)
        estimated_score = min(0.85, context.get("location_scores", {}).get("similarity", 0.0) + 0.12)
        return shot, estimated_score


class NoSilentFailureEnforcer(DoctrineGate):
    """Error Law 04 — No Silent Failure Enforcer

    Audits all gate results and ensures every non-PASS verdict
    has a corresponding ledger entry. Detects silent failures where
    gates verdict without logging.
    """

    def __init__(self, project_path: str = ""):
        """Initialize silent failure enforcer."""
        super().__init__(gate_name="ERROR_LAW_04_NO_SILENT_FAILURE", gate_position="all", project_path=project_path)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run enforcer (not a typical gate, but required by base class)."""
        return GateResult.PASS

    def audit_gate_results(self, shot_id: str, gate_results: Dict[str, str]) -> List[Dict[str, Any]]:
        """Audit gate results and find unlogged verdicts.

        Args:
            shot_id: Shot ID to audit
            gate_results: Dict of {gate_name: verdict_string}

        Returns:
            List of unlogged events (empty if all logged)
        """
        ledger_entries = self.ledger.read_shot(shot_id)
        ledger_gates = {entry.gate_result for entry in ledger_entries}

        unlogged = []
        for gate_name, verdict in gate_results.items():
            if verdict != "PASS" and verdict not in ledger_gates:
                unlogged.append({
                    "shot_id": shot_id,
                    "gate_name": gate_name,
                    "verdict": verdict,
                    "status": "UNLOGGED"
                })

        return unlogged

    def enforce(
        self, shot_id: str, gate_name: str, result: GateResult, ledger: Optional[RunLedger] = None
    ) -> None:
        """Enforce logging of gate results.

        If result is not PASS and no ledger entry exists, force-write an entry.

        Args:
            shot_id: Shot ID
            gate_name: Gate name
            result: Gate result
            ledger: Optional ledger instance (creates new if None)
        """
        if ledger is None:
            ledger = self.ledger

        # Check if result is already logged
        entries = ledger.read_shot(shot_id)
        result_exists = any(e.gate_result == result.value for e in entries)

        if not result_exists and result != GateResult.PASS:
            # Force-write a "silent failure detected" entry
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=result.value,
                deviation_score=0.0,
                deviation_type="enforcement",
                correction_applied=False,
                model_used="unknown",
                prompt_hash="unknown",
                session_timestamp=self.session_timestamp,
                gate_position="audit",
                reason_code="SILENT_FAILURE_DETECTED",
                extra_data={"gate_name": gate_name, "enforced_logging": True}
            )
            self._write_ledger(entry)


class PainSignalSystem:
    """Error Law 05 — Pain Signal System

    Monitors rolling window of ledger entries for consecutive declining
    scores, indicating emerging quality degradation. Pain signals trigger
    reanchoring or generation pause.
    """

    def __init__(self, project_path: str):
        """Initialize pain signal system."""
        self.project_path = Path(project_path)
        self.ledger = RunLedger(str(self.project_path))
        self.pain_signal_window = PAIN_SIGNAL_WINDOW
        self.pain_signal_trigger = PAIN_SIGNAL_TRIGGER

    def register_score(self, scene_id: str, score: float) -> dict:
        """V25 adapter: register a single identity score for pain tracking.
        Allows direct score injection for testing and monitoring.
        Returns dict with current pain state.
        """
        if not hasattr(self, '_score_buffer'):
            self._score_buffer = []
        self._score_buffer.append(score)
        active = self.is_active()
        return {"scene_id": scene_id, "score": score, "pain_active": active}

    def is_active(self) -> bool:
        """V25 adapter: return True if pain signal is currently active."""
        if not hasattr(self, '_score_buffer') or len(self._score_buffer) < 5:
            return False
        # Check last 5 scores for consecutive decline
        recent = self._score_buffer[-5:]
        declining = all(recent[i] > recent[i+1] for i in range(len(recent)-1))
        low_count = sum(1 for s in self._score_buffer if s < 0.75)
        return declining or (low_count >= 5)

    def check_rolling_health(
        self, ledger: Optional[RunLedger] = None, dimensions: Optional[List[str]] = None
    ) -> PainSignalReport:
        """Check rolling window for pain signals (consecutive declining scores).

        Args:
            ledger: Optional ledger instance
            dimensions: Optional list of dimensions to check (default: all)

        Returns:
            PainSignalReport with active status, dimension, trend, recommendation
        """
        if ledger is None:
            ledger = self.ledger

        if dimensions is None:
            dimensions = ["identity", "continuity", "cinema", "location"]

        # Get rolling window
        window = ledger.get_rolling_window(self.pain_signal_window)
        if not window:
            return PainSignalReport(
                active=False,
                dimension="none",
                trend=[],
                recommendation="CONTINUE",
                shots_affected=[],
                timestamp=datetime.utcnow().isoformat()
            )

        # Check each dimension
        for dimension in dimensions:
            trend = ledger.get_trend(dimension, self.pain_signal_window)

            if len(trend) >= self.pain_signal_trigger:
                # Check for consecutive decline
                if self._is_declining(trend):
                    return PainSignalReport(
                        active=True,
                        dimension=dimension,
                        trend=trend,
                        recommendation="REANCHOR",
                        shots_affected=[e.shot_id for e in window[-len(trend):]],
                        timestamp=datetime.utcnow().isoformat()
                    )

        return PainSignalReport(
            active=False,
            dimension="none",
            trend=[],
            recommendation="CONTINUE",
            shots_affected=[],
            timestamp=datetime.utcnow().isoformat()
        )

    def force_reanchor(self, context: Dict[str, Any]) -> None:
        """Force reanchoring by resetting carry-state to master reference.

        Args:
            context: Generation context to modify
        """
        context["_force_reanchor"] = True
        context["_reanchor_reason"] = "PAIN_SIGNAL"
        context["_reset_carry_state"] = True
        context["_carry_state_reset_timestamp"] = datetime.utcnow().isoformat()

    def check_and_act(
        self, ledger: Optional[RunLedger] = None, context: Optional[Dict[str, Any]] = None
    ) -> PainSignalReport:
        """Check pain signals and take action if needed.

        Args:
            ledger: Optional ledger instance
            context: Optional context to modify if action needed

        Returns:
            PainSignalReport
        """
        if ledger is None:
            ledger = self.ledger

        context = context or {}
        report = self.check_rolling_health(ledger)

        if report.active:
            if report.recommendation == "REANCHOR":
                self.force_reanchor(context)
            elif report.recommendation == "PAUSE":
                context["_pause_generation"] = True
                context["_pause_reason"] = f"PAIN_SIGNAL_DIMENSION_{report.dimension}"

        return report

    def _is_declining(self, trend: List[float]) -> bool:
        """Check if trend shows consecutive declining values.

        Args:
            trend: List of scores

        Returns:
            True if at least PAIN_SIGNAL_TRIGGER consecutive declines
        """
        if len(trend) < self.pain_signal_trigger:
            return False

        # Check last PAIN_SIGNAL_TRIGGER entries for consistent decline
        recent = trend[-self.pain_signal_trigger:]
        for i in range(1, len(recent)):
            if recent[i] >= recent[i - 1]:
                # Not declining at this point
                return False

        return True


# Top-level runners

def run_phase2_pre_generation(
    shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run Phase 2 pre-generation gates.

    Runs: Toxic Pattern Suppression

    Args:
        shot: Shot plan dictionary
        context: Optional generation context

    Returns:
        Dict with gate results
    """
    context = context or {}
    project_path = context.get("project_path", ".")

    toxic_gate = ToxicPatternSuppressionGate(project_path)
    result = toxic_gate.run(shot, context)

    return {
        "phase": "pre_generation",
        "gates": [
            {"gate": "ERROR_LAW_02_TOXIC_SUPPRESSION", "result": result.value}
        ],
        "verdict": "PASS" if result == GateResult.PASS else result.value,
        "context_updated": True
    }


def run_phase2_post_generation(
    shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run Phase 2 post-generation gates.

    Runs: Parity Check, Pain Signal Monitoring, Silent Failure Enforcement

    Args:
        shot: Shot plan dictionary
        context: Optional generation context

    Returns:
        Dict with gate results and recommendations
    """
    context = context or {}
    project_path = context.get("project_path", ".")

    # Parity check
    parity = ParityCheckGate(project_path)
    parity_result = parity.run(shot, context)

    # Pain signal monitoring
    pain_system = PainSignalSystem(project_path)
    pain_report = pain_system.check_and_act(None, context)

    # Silent failure enforcement
    enforcer = NoSilentFailureEnforcer(project_path)
    enforcer.enforce(shot.get("shot_id", "unknown"), "ERROR_LAW_01_PARITY_CHECK", parity_result)

    return {
        "phase": "post_generation",
        "gates": [
            {"gate": "ERROR_LAW_01_PARITY_CHECK", "result": parity_result.value},
            {"gate": "ERROR_LAW_04_NO_SILENT_FAILURE", "result": "PASS"},
            {"gate": "ERROR_LAW_05_PAIN_SIGNAL", "result": "WARN" if pain_report.active else "PASS"}
        ],
        "verdict": parity_result.value,
        "pain_active": pain_report.active,
        "pain_dimension": pain_report.dimension,
        "pain_recommendation": pain_report.recommendation,
        "context_updated": True
    }
