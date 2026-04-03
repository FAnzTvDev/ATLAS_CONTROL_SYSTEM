"""
ATLAS Doctrine Phase 7 — Autonomous Creation Laws

The highest-order laws governing ATLAS when operating without real-time human supervision.
Four systems: Decision Auditability, Uncertainty Declaration, Health Check Before Continuation,
and Prime Directive conflict resolution.

V24.2 | 2026-03-11
Author: ATLAS Production System
"""

import json
import os
import hashlib
import fcntl
import threading
import functools
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any, Callable, Tuple
from datetime import datetime
from pathlib import Path

from tools.doctrine_engine import (
    GateResult, DoctrineGate, LedgerEntry, RunLedger,
    EscalationTracker, HealthCheck, ToxicityRegistry,
    SCENE_REJECT_CEILING, TOXICITY_GROWTH_CEILING
)


# ============================================================================
# AUTONOMY LAW 01 — Decision Auditability
# ============================================================================

@dataclass
class DecisionRecord:
    """Immutable audit trail for a routing or gate decision."""
    decision_type: str  # e.g., "model_routing", "shot_classification", "gate_verdict"
    reason_code: str    # e.g., "EXECUTIVE_LAW_01_HERO_CLASSIFICATION"
    rule_invoked: str   # Which law/command caused this
    data_used: Dict[str, Any]  # What data was compared
    output: str         # What was decided
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = 0.9  # 0.0-1.0, how confident in this decision

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return asdict(self)


class DecisionAuditGate(DoctrineGate):
    """AUTONOMY_LAW_01: Every decision must be traceable to a rule."""

    def __init__(self, project_path: str):
        """Initialize decision audit gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "all", "AUTONOMY_LAW_01")
        self.audit_file = self.project_path / "reports" / "decision_audit.jsonl"
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self._lock = threading.RLock()

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Check that every decision has an audit trail.

        Args:
            shot: Shot plan dictionary
            context: Optional context containing _last_decision

        Returns:
            GateResult.PASS if audit trail exists and complete
            GateResult.WARN if missing reason_code
            GateResult.REJECT if no audit trail at all
        """
        context = context or {}
        last_decision = context.get("_last_decision")
        shot_id = shot.get("shot_id", "unknown")

        if last_decision is None:
            # No decision was tracked
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result="REJECT",
                deviation_score=1.0,
                deviation_type="autonomy",
                correction_applied=False,
                model_used="auto",
                prompt_hash="",
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="AUTONOMY_LAW_01_UNAUTHORIZED_DECISION",
                extra_data={"error": "No audit trail found for decision"}
            )
            self._write_ledger(entry)
            self._write_audit(shot_id, "REJECT", "No audit trail tracked")
            return GateResult.REJECT

        # Validate decision record structure
        required_keys = ["decision_type", "reason_code", "rule_invoked", "data_used", "output"]
        missing_keys = [k for k in required_keys if k not in last_decision]

        if missing_keys:
            # Decision exists but is incomplete
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result="WARN",
                deviation_score=0.5,
                deviation_type="autonomy",
                correction_applied=False,
                model_used="auto",
                prompt_hash="",
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="AUTONOMY_LAW_01_INCOMPLETE_DECISION",
                extra_data={"missing_keys": missing_keys}
            )
            self._write_ledger(entry)
            self._write_audit(shot_id, "WARN", f"Decision missing keys: {missing_keys}")
            return GateResult.WARN

        # Decision is complete and auditable
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result="PASS",
            deviation_score=0.0,
            deviation_type="autonomy",
            correction_applied=False,
            model_used="auto",
            prompt_hash="",
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=last_decision.get("reason_code", "AUTONOMY_LAW_01_PASS"),
            extra_data={
                "decision_type": last_decision.get("decision_type"),
                "rule_invoked": last_decision.get("rule_invoked")
            }
        )
        self._write_ledger(entry)
        self._write_audit(shot_id, "PASS", "Decision audit trail complete")
        return GateResult.PASS

    def require_audit(self, func: Callable) -> Callable:
        """Decorator: require audit trail for a routing/decision function.

        The decorated function MUST set context["_last_decision"] before returning.

        Example:
            @gate.require_audit
            def route_model_choice(shot, context):
                # ...logic...
                context["_last_decision"] = DecisionRecord(...)
                return chosen_model
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the function
            result = func(*args, **kwargs)

            # Extract context from args/kwargs
            context = None
            if "context" in kwargs:
                context = kwargs["context"]
            elif len(args) > 1:
                context = args[1]  # Assuming (shot, context, ...)

            if context is None:
                raise ValueError(
                    f"{func.__name__} requires context argument for audit trail"
                )

            # Check that _last_decision was set
            if "_last_decision" not in context:
                raise ValueError(
                    f"{func.__name__} did not set context['_last_decision'] — "
                    "decorated functions must track all decisions for auditability"
                )

            return result

        return wrapper

    def _write_audit(self, shot_id: str, verdict: str, note: str) -> None:
        """Write to decision audit log."""
        with self._lock:
            entry = {
                "shot_id": shot_id,
                "verdict": verdict,
                "note": note,
                "timestamp": datetime.utcnow().isoformat()
            }

            with open(self.audit_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(entry, default=str) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ============================================================================
# AUTONOMY LAW 02 — Uncertainty Declaration
# ============================================================================

class UncertaintyDeclarationGate(DoctrineGate):
    """AUTONOMY_LAW_02: Declare all uncertainties and apply conservative defaults."""

    def __init__(self, project_path: str):
        """Initialize uncertainty declaration gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "pre_generation", "AUTONOMY_LAW_02")

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Declare uncertainties across all decision dimensions.

        For each dimension:
        - If scene_plan instruction exists → KNOWN
        - If stable learned preference exists → KNOWN
        - If provisional learned preference only → UNCERTAIN
        - If nothing exists → UNCERTAIN (apply conservative default)

        Args:
            shot: Shot plan dictionary
            context: Optional context with scene_plan, cast_map, etc.

        Returns:
            GateResult.PASS always (uncertainty is handled, not blocked)
            Sets shot["_uncertain_dimensions"] and shot["_human_review_required"]
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")
        scene_plan = context.get("scene_plan", {})
        cast_map = context.get("cast_map", {})
        carry_state = context.get("carry_state", {})

        uncertain_dims = []

        # Dimension 1: Model Tier
        model_tier_known = False
        if scene_plan.get("model_tier_override"):
            model_tier_known = True
            shot["_model_tier"] = scene_plan["model_tier_override"]
        elif context.get("learned_model_preference_stable"):
            model_tier_known = True
            shot["_model_tier"] = context["learned_model_preference_stable"]
        else:
            uncertain_dims.append("model_tier")
            shot["_model_tier"] = "ltx2_fast"  # Conservative default

        # Dimension 2: Prompt Structure
        prompt_structure_known = False
        if scene_plan.get("prompt_template"):
            prompt_structure_known = True
            shot["_prompt_structure"] = "scene_plan"
        elif context.get("template_library"):
            prompt_structure_known = True
            shot["_prompt_structure"] = "learned_template"
        else:
            uncertain_dims.append("prompt_structure")
            shot["_prompt_structure"] = "minimal"  # Conservative default

        # Dimension 3: Identity References
        identity_refs_known = False
        if shot.get("characters") and cast_map:
            # Check if all characters are in cast_map
            missing_refs = [c for c in shot.get("characters", []) if c not in cast_map]
            if not missing_refs:
                identity_refs_known = True
                shot["_identity_enforcement_threshold"] = 0.85
            else:
                uncertain_dims.append("identity_refs")
                shot["_identity_enforcement_threshold"] = 0.95  # Conservative
        else:
            uncertain_dims.append("identity_refs")
            shot["_identity_enforcement_threshold"] = 0.95  # Conservative

        # Dimension 4: Continuity State
        continuity_known = False
        if carry_state.get(shot_id):
            continuity_known = True
            shot["_continuity_state"] = "explicit"
        elif scene_plan.get("continuity_locked"):
            continuity_known = True
            shot["_continuity_state"] = "scene_locked"
        else:
            uncertain_dims.append("continuity_state")
            shot["_continuity_state"] = "strict"  # Conservative default

        # Store uncertainties on shot
        shot["_uncertain_dimensions"] = uncertain_dims
        shot["_human_review_required"] = len(uncertain_dims) > 0

        # Log to ledger
        verdict = GateResult.WARN if uncertain_dims else GateResult.PASS
        deviation_score = len(uncertain_dims) * 0.25  # 0.25 per uncertain dimension

        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=verdict.value,
            deviation_score=min(1.0, deviation_score),
            deviation_type="autonomy",
            correction_applied=False,
            model_used="auto",
            prompt_hash="",
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code="AUTONOMY_LAW_02_UNCERTAINTY_DECLARATION",
            extra_data={
                "uncertain_dimensions": uncertain_dims,
                "conservative_defaults_applied": {
                    "model_tier": shot["_model_tier"],
                    "prompt_structure": shot["_prompt_structure"],
                    "identity_enforcement_threshold": shot["_identity_enforcement_threshold"],
                    "continuity_state": shot["_continuity_state"]
                }
            }
        )
        self._write_ledger(entry)

        return GateResult.PASS  # Always PASS — uncertainty is handled conservatively


# ============================================================================
# AUTONOMY LAW 03 — Health Check Before Continuation
# ============================================================================

@dataclass
class HealthReport:
    """Health status report at scene boundaries."""
    scene_id: str
    reject_rate: float  # 0.0-1.0
    pain_active: bool
    pain_dimension: str  # e.g., "identity", "continuity"
    toxicity_growth: float  # 0.0-1.0
    unresolved_escalations: int
    health_status: str  # "HEALTHY" / "DEGRADED" / "CRITICAL"
    continuation_authorized: bool
    enforcement_adjustment: str  # "NORMAL" / "ELEVATED" / "MAXIMUM"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return asdict(self)


class HealthCheckGate(DoctrineGate):
    """AUTONOMY_LAW_03: Health check before continuing to next scene."""

    def __init__(self, project_path: str):
        """Initialize health check gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "scene_boundary", "AUTONOMY_LAW_03")
        self.health_checker = HealthCheck(project_path)
        self.escalation_tracker = EscalationTracker(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Check scene health before continuing to next scene.

        Args:
            shot: Current shot (used to identify current scene context)
            context: Optional context with previous_scene_id, etc.

        Returns:
            GateResult.REJECT if scene is unhealthy
            GateResult.WARN if degraded
            GateResult.PASS if healthy

        Sets context["_autonomous_paused"] = True if REJECT
        Sets context["_enforcement_adjustment"] = "ELEVATED" or "MAXIMUM" if WARN
        """
        context = context or {}
        previous_scene_id = context.get("previous_scene_id", "unknown")

        if previous_scene_id == "unknown":
            # First shot, no previous scene to check
            return GateResult.PASS

        # Compute health metrics
        reject_rate = self.ledger.get_reject_rate(previous_scene_id)
        toxicity_data = self._compute_toxicity_growth()
        toxicity_growth = toxicity_data["growth_rate"]

        unresolved = self.escalation_tracker.get_unresolved()
        unresolved_escalations = len(unresolved)

        pain_active = context.get("_pain_signal_active", False)
        pain_dimension = context.get("_pain_dimension", "none")

        # Determine health status and authorization
        health_status = "HEALTHY"
        continuation_authorized = True
        enforcement_adjustment = "NORMAL"
        notes = []

        # Check thresholds
        if reject_rate >= SCENE_REJECT_CEILING:
            health_status = "CRITICAL"
            continuation_authorized = False
            notes.append(f"REJECT rate {reject_rate:.1%} >= ceiling {SCENE_REJECT_CEILING:.1%}")
        elif reject_rate > 0.10:
            health_status = "DEGRADED"
            enforcement_adjustment = "ELEVATED"
            notes.append(f"REJECT rate {reject_rate:.1%} in elevated zone (10-15%)")

        if pain_active:
            health_status = "CRITICAL"
            continuation_authorized = False
            notes.append(f"PAIN signal active in dimension: {pain_dimension}")

        if toxicity_growth >= TOXICITY_GROWTH_CEILING:
            health_status = "CRITICAL"
            continuation_authorized = False
            notes.append(f"Toxicity growth {toxicity_growth:.1%} >= ceiling {TOXICITY_GROWTH_CEILING:.1%}")
        elif toxicity_growth > 0.05:
            if health_status != "CRITICAL":
                health_status = "DEGRADED"
            enforcement_adjustment = "ELEVATED"
            notes.append(f"Toxicity growth {toxicity_growth:.1%} in elevated zone (5-10%)")

        if unresolved_escalations > 0:
            health_status = "CRITICAL"
            continuation_authorized = False
            notes.append(f"{unresolved_escalations} unresolved escalations")

        # Build report
        report = HealthReport(
            scene_id=previous_scene_id,
            reject_rate=reject_rate,
            pain_active=pain_active,
            pain_dimension=pain_dimension,
            toxicity_growth=toxicity_growth,
            unresolved_escalations=unresolved_escalations,
            health_status=health_status,
            continuation_authorized=continuation_authorized,
            enforcement_adjustment=enforcement_adjustment,
            notes=notes
        )

        self._write_health_report(report)

        # Apply result
        verdict = GateResult.PASS
        if not continuation_authorized:
            context["_autonomous_paused"] = True
            verdict = GateResult.REJECT
        elif enforcement_adjustment != "NORMAL":
            context["_enforcement_adjustment"] = enforcement_adjustment
            if health_status == "DEGRADED":
                verdict = GateResult.WARN

        # Log to ledger
        entry = LedgerEntry(
            shot_id=shot.get("shot_id", "boundary"),
            gate_result=verdict.value,
            deviation_score=reject_rate,  # Use reject rate as deviation proxy
            deviation_type="autonomy",
            correction_applied=False,
            model_used="auto",
            prompt_hash="",
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code="AUTONOMY_LAW_03_HEALTH_CHECK",
            extra_data={
                "scene_id": previous_scene_id,
                "health_status": health_status,
                "continuation_authorized": continuation_authorized
            }
        )
        self._write_ledger(entry)

        return verdict

    def _compute_toxicity_growth(self) -> Dict[str, Any]:
        """Compute toxicity growth rate from registry.

        Returns dict with growth_rate (0.0-1.0) and pattern counts.
        """
        registry = self.toxicity
        patterns = registry.data.get("patterns", {})

        if not patterns:
            return {"growth_rate": 0.0, "pattern_count": 0, "high_confidence_count": 0}

        high_confidence = sum(
            1 for p in patterns.values()
            if p.get("failure_count", 0) >= 3
        )

        # Growth rate: high confidence patterns as percentage of total
        growth_rate = high_confidence / max(len(patterns), 1)

        return {
            "growth_rate": growth_rate,
            "pattern_count": len(patterns),
            "high_confidence_count": high_confidence
        }

    def _write_health_report(self, report: HealthReport) -> None:
        """Write health report to disk."""
        reports_file = self.reports_dir / "health_reports.jsonl"

        with open(reports_file, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(report.to_dict(), default=str) + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ============================================================================
# AUTONOMY LAW 04 — Prime Directive (Conflict Resolution)
# ============================================================================

@dataclass
class ConflictResolution:
    """Resolution of a rule conflict via Prime Directive."""
    conflict_type: str  # e.g., "model_selection", "prompt_structure"
    rule_a: str        # First competing rule
    rule_b: str        # Second competing rule
    resolution_source: str  # "scene_plan" / "story_bible" / "director_constraint" / "escalation"
    chosen_rule: str   # Which rule won
    reason: str        # Why this rule won
    escalated: bool    # Whether escalated to human
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return asdict(self)


class PrimeDirectiveResolver:
    """AUTONOMY_LAW_04: Resolve conflicts between competing rules via narrative intent.

    The question is always: "which option best serves the intended film?"
    """

    def __init__(self, project_path: str):
        """Initialize Prime Directive resolver.

        Args:
            project_path: Path to ATLAS project
        """
        self.project_path = Path(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.conflicts_file = self.reports_dir / "unresolved_conflicts.jsonl"
        self._lock = threading.RLock()

    def resolve_conflict(
        self,
        rule_a: str,
        rule_b: str,
        shot: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ConflictResolution:
        """Resolve a conflict between two competing rules.

        Resolution hierarchy:
        1. Scene Plan guidance (explicit director intent)
        2. Story Bible narrative intent
        3. Director constraints (locked creative decisions)
        4. Escalate to human

        Args:
            rule_a: First rule identifier
            rule_b: Second rule identifier
            shot: Shot plan dictionary
            context: Optional context with scene_plan, story_bible, director_constraints

        Returns:
            ConflictResolution with chosen rule and reason
        """
        context = context or {}
        scene_plan = context.get("scene_plan", {})
        story_bible = context.get("story_bible", {})
        director_constraints = context.get("director_constraints", {})

        conflict_type = f"{rule_a}_vs_{rule_b}"

        # Step 1: Check Scene Plan
        if scene_plan.get(f"resolve_{rule_a}_vs_{rule_b}"):
            chosen = scene_plan[f"resolve_{rule_a}_vs_{rule_b}"]
            resolution = ConflictResolution(
                conflict_type=conflict_type,
                rule_a=rule_a,
                rule_b=rule_b,
                resolution_source="scene_plan",
                chosen_rule=chosen,
                reason=f"Scene plan explicitly resolves: choose {chosen}",
                escalated=False
            )
            self.log_conflict(resolution)
            return resolution

        # Step 2: Check Story Bible narrative intent
        scene_id = shot.get("scene_id", "unknown")
        if story_bible.get(scene_id):
            scene_data = story_bible[scene_id]
            narrative_intent = scene_data.get("narrative_intent", "")

            # Simple heuristic: if narrative intent mentions rule_a concepts, prefer it
            if narrative_intent and self._intent_favors(narrative_intent, rule_a, rule_b):
                resolution = ConflictResolution(
                    conflict_type=conflict_type,
                    rule_a=rule_a,
                    rule_b=rule_b,
                    resolution_source="story_bible",
                    chosen_rule=rule_a,
                    reason=f"Narrative intent aligns with {rule_a}",
                    escalated=False
                )
                self.log_conflict(resolution)
                return resolution

        # Step 3: Check Director Constraints
        if director_constraints.get(rule_a):
            resolution = ConflictResolution(
                conflict_type=conflict_type,
                rule_a=rule_a,
                rule_b=rule_b,
                resolution_source="director_constraint",
                chosen_rule=rule_a,
                reason=f"Director constraint locks: {rule_a}",
                escalated=False
            )
            self.log_conflict(resolution)
            return resolution

        # Step 4: No resolution found — escalate
        resolution = ConflictResolution(
            conflict_type=conflict_type,
            rule_a=rule_a,
            rule_b=rule_b,
            resolution_source="escalation",
            chosen_rule="ESCALATED",
            reason=f"No guidance found for {rule_a} vs {rule_b} — requires human decision",
            escalated=True
        )
        self.log_conflict(resolution)
        return resolution

    def _intent_favors(self, narrative_intent: str, rule_a: str, rule_b: str) -> bool:
        """Heuristic: does narrative intent favor rule_a over rule_b?

        Very simple keyword matching. In production, could use embedding similarity.
        """
        intent_lower = narrative_intent.lower()

        # Extract keywords from rule names
        rule_a_keywords = rule_a.lower().split("_")
        rule_b_keywords = rule_b.lower().split("_")

        a_matches = sum(1 for kw in rule_a_keywords if kw in intent_lower)
        b_matches = sum(1 for kw in rule_b_keywords if kw in intent_lower)

        return a_matches > b_matches

    def log_conflict(self, resolution: ConflictResolution) -> None:
        """Write conflict resolution to log.

        Args:
            resolution: ConflictResolution to log
        """
        with self._lock:
            with open(self.conflicts_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(resolution.to_dict(), default=str) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ============================================================================
# Top-level Runner Functions
# ============================================================================

def run_phase7_scene_boundary(
    shot: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Phase 7 scene boundary: health check before next scene.

    Args:
        shot: Current shot plan
        context: Execution context with previous_scene_id, pain signals, etc.
        project_path: Path to ATLAS project

    Returns:
        Dict with gate result and autonomy pause status
    """
    if not project_path:
        return {"error": "project_path required"}

    health_gate = HealthCheckGate(project_path)
    result = health_gate.run(shot, context or {})

    return {
        "gate": "AUTONOMY_LAW_03",
        "result": result.value,
        "autonomous_paused": (context or {}).get("_autonomous_paused", False),
        "enforcement_adjustment": (context or {}).get("_enforcement_adjustment", "NORMAL")
    }


def run_phase7_pre_generation(
    shot: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Phase 7 pre-gen: uncertainty declaration.

    Args:
        shot: Shot plan dictionary
        context: Execution context with scene_plan, cast_map, etc.
        project_path: Path to ATLAS project

    Returns:
        Dict with gate result and uncertain dimensions
    """
    if not project_path:
        return {"error": "project_path required"}

    uncertainty = UncertaintyDeclarationGate(project_path)
    result = uncertainty.run(shot, context or {})

    return {
        "gate": "AUTONOMY_LAW_02",
        "result": result.value,
        "uncertain_dimensions": shot.get("_uncertain_dimensions", []),
        "human_review_required": shot.get("_human_review_required", False)
    }


def run_phase7_audit(
    shot: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Phase 7 audit: decision auditability check.

    Args:
        shot: Shot plan dictionary
        context: Execution context with _last_decision
        project_path: Path to ATLAS project

    Returns:
        Dict with gate result and audit status
    """
    if not project_path:
        return {"error": "project_path required"}

    audit = DecisionAuditGate(project_path)
    result = audit.run(shot, context or {})

    last_decision = (context or {}).get("_last_decision", {})

    return {
        "gate": "AUTONOMY_LAW_01",
        "result": result.value,
        "audit_trail_complete": result == GateResult.PASS,
        "decision_type": last_decision.get("decision_type"),
        "reason_code": last_decision.get("reason_code")
    }


def resolve_conflict(
    rule_a: str,
    rule_b: str,
    shot: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Phase 7 prime directive: resolve rule conflicts.

    Args:
        rule_a: First competing rule identifier
        rule_b: Second competing rule identifier
        shot: Shot plan dictionary
        context: Execution context with scene_plan, story_bible, director_constraints
        project_path: Path to ATLAS project

    Returns:
        Dict with resolution details
    """
    if not project_path:
        return {"error": "project_path required"}

    resolver = PrimeDirectiveResolver(project_path)
    resolution = resolver.resolve_conflict(rule_a, rule_b, shot, context or {})

    return {
        "gate": "AUTONOMY_LAW_04",
        "conflict_type": resolution.conflict_type,
        "chosen_rule": resolution.chosen_rule,
        "resolution_source": resolution.resolution_source,
        "reason": resolution.reason,
        "escalated": resolution.escalated
    }


__all__ = [
    "DecisionRecord",
    "DecisionAuditGate",
    "UncertaintyDeclarationGate",
    "HealthReport",
    "HealthCheckGate",
    "ConflictResolution",
    "PrimeDirectiveResolver",
    "run_phase7_scene_boundary",
    "run_phase7_pre_generation",
    "run_phase7_audit",
    "resolve_conflict"
]
