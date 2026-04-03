"""
Phase 6: Human Sovereignty and Override Architecture
======================================================

The system may be autonomous in operation. It must never be sovereign in purpose.

Three systems enforce human authority at critical boundaries:
1. HARD STOP PROTOCOL — system-level emergency halt (always available)
2. DIRECTOR CONSTRAINT LOCK — immutable instruction enforcement (post-generation validation)
3. LEARNED PREFERENCE SUBORDINATION — explicit instructions always override learned patterns (pre-generation gate)

All three guarantee that no autonomous decision can override explicit human direction.
"""

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from tools.doctrine_engine import (
    GateResult,
    DoctrineGate,
    LedgerEntry,
    RunLedger,
    EscalationTracker,
)


# ============================================================================
# SOVEREIGNTY LAW 01 — Hard Stop Protocol
# ============================================================================


@dataclass
class HardStopReport:
    """Record of a hard stop execution."""
    timestamp: str
    reason: str
    issued_by: str
    active_shots_interrupted: List[str]
    ledger_flushed: bool
    session_id: str


class HardStopProtocol:
    """
    System-level emergency mechanism for immediate pipeline halt.

    NOT a gate — a core protocol that supersedes all agents.
    Can be invoked at any time, always succeeds, always records.
    """

    def __init__(self, session_id: str = "unknown"):
        """Initialize hard stop protocol.

        Args:
            session_id: Current session identifier
        """
        self.session_id = session_id
        self.hard_stops_path = "reports/hard_stops.jsonl"

    def execute_hard_stop(
        self,
        context: Dict[str, Any],
        reason: str,
        issued_by: str = "human"
    ) -> HardStopReport:
        """
        Execute immediate hard stop of pipeline.

        Step 1: Set hard stop flag in context
        Step 2: Set pipeline state to HALTED
        Step 3: Record active shot_ids from context
        Step 4: Flush ledger to disk if available
        Step 5: Write stop record to reports/hard_stops.jsonl

        This operation ALWAYS succeeds. No exceptions can prevent it.

        Args:
            context: Current execution context
            reason: Human-readable reason for hard stop
            issued_by: Who issued the stop (e.g., "charles", "juice", "automated_safety")

        Returns:
            HardStopReport with full details of the halt
        """
        timestamp = datetime.utcnow().isoformat()

        # Step 1: Set hard stop flag
        context["_hard_stop_active"] = True

        # Step 2: Set pipeline state
        context["_pipeline_state"] = "HALTED"

        # Step 3: Record active shot_ids
        active_shots = context.get("_generation_queue", [])
        if isinstance(active_shots, dict):
            active_shots = list(active_shots.keys())
        elif not isinstance(active_shots, list):
            active_shots = []

        # Step 4: Flush ledger if available
        ledger_flushed = False
        if isinstance(context.get("_ledger"), RunLedger):
            try:
                context["_ledger"].flush()
                ledger_flushed = True
            except Exception:
                # Ledger flush failure does NOT prevent hard stop
                ledger_flushed = False

        # Step 5: Write stop record to hard_stops.jsonl
        stop_record = {
            "timestamp": timestamp,
            "reason": reason,
            "issued_by": issued_by,
            "pipeline_state_at_halt": context.get("_pipeline_state", "UNKNOWN"),
            "active_shot_ids": active_shots,
            "ledger_flushed": ledger_flushed,
            "session_id": self.session_id,
        }

        self._append_hard_stop_record(stop_record)

        # Build report
        report = HardStopReport(
            timestamp=timestamp,
            reason=reason,
            issued_by=issued_by,
            active_shots_interrupted=active_shots,
            ledger_flushed=ledger_flushed,
            session_id=self.session_id,
        )

        return report

    def check_hard_stop(self, context: Dict[str, Any]) -> bool:
        """
        Check if hard stop is currently active.

        Args:
            context: Current execution context

        Returns:
            True if hard stop is active, False otherwise
        """
        return context.get("_hard_stop_active", False)

    def clear_hard_stop(
        self,
        context: Dict[str, Any],
        cleared_by: str
    ) -> bool:
        """
        Clear hard stop and resume pipeline.

        Only humans can clear hard stops. Requires explicit clearance action.

        Args:
            context: Current execution context
            cleared_by: Who cleared the hard stop

        Returns:
            True if clearance succeeded
        """
        timestamp = datetime.utcnow().isoformat()

        # Only humans can clear
        if cleared_by not in ("charles", "juice", "human"):
            return False

        # Clear flags
        context["_hard_stop_active"] = False
        context["_pipeline_state"] = "IDLE"

        # Record clearance
        clearance_record = {
            "timestamp": timestamp,
            "action": "hard_stop_cleared",
            "cleared_by": cleared_by,
            "session_id": self.session_id,
        }

        self._append_hard_stop_record(clearance_record)

        return True

    def _append_hard_stop_record(self, record: Dict[str, Any]) -> None:
        """
        Atomically append record to hard_stops.jsonl.

        Args:
            record: Record dict to append
        """
        os.makedirs("reports", exist_ok=True)

        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir="reports",
            delete=False,
            suffix=".jsonl.tmp"
        ) as tmp:
            tmp_path = tmp.name
            # Append to existing file content if present
            if os.path.exists(self.hard_stops_path):
                with open(self.hard_stops_path, "r") as f:
                    tmp.write(f.read())
            # Append new record
            tmp.write(json.dumps(record) + "\n")

        # Atomic replace
        os.replace(tmp_path, self.hard_stops_path)


# ============================================================================
# SOVEREIGNTY LAW 02 — Director Constraint Lock
# ============================================================================


@dataclass
class DirectorConstraint:
    """Immutable constraint set by director/producer."""
    constraint_id: str
    field: str  # e.g., "character_behavior", "scene_tone", "visual_style"
    value: str  # locked value
    scope: str  # "shot", "scene", "project"
    scope_id: str  # shot_id, scene_id, or project name
    set_by: str  # "charles", "juice", etc.
    timestamp: str
    locked: bool = True


@dataclass
class ConstraintViolation:
    """Record of a constraint violation in generated output."""
    constraint: DirectorConstraint
    actual_value: str
    severity: str  # "stylistic" or "critical"
    shot_id: str
    timestamp: str
    description: str = ""


class DirectorConstraintLock:
    """
    Enforces immutable director constraints throughout generation.

    Constraints are written before generation and cannot be modified by agents.
    Post-generation validation detects violations.
    """

    def __init__(self):
        """Initialize constraint lock system."""
        self.constraints_path = "reports/director_constraints.json"
        self.violations_path = "reports/constraint_violations.jsonl"
        self._constraints: Dict[str, DirectorConstraint] = {}
        self._load_constraints()

    def set_constraint(
        self,
        field: str,
        value: str,
        scope: str,
        scope_id: str,
        set_by: str,
    ) -> DirectorConstraint:
        """
        Create and persist a director constraint.

        Args:
            field: What is being constrained
            value: The locked value
            scope: "shot", "scene", or "project"
            scope_id: Identifier for scope
            set_by: Who set this constraint

        Returns:
            Persisted DirectorConstraint
        """
        timestamp = datetime.utcnow().isoformat()
        constraint_id = f"{scope}_{scope_id}_{field}_{timestamp[:19]}"

        constraint = DirectorConstraint(
            constraint_id=constraint_id,
            field=field,
            value=value,
            scope=scope,
            scope_id=scope_id,
            set_by=set_by,
            timestamp=timestamp,
            locked=True,
        )

        self._constraints[constraint_id] = constraint
        self._persist_constraints()

        return constraint

    def get_constraints(self, scope_id: str) -> List[DirectorConstraint]:
        """
        Get all constraints for a scope.

        Args:
            scope_id: Scope identifier (shot_id, scene_id, or project name)

        Returns:
            List of constraints for this scope
        """
        return [c for c in self._constraints.values() if c.scope_id == scope_id]

    def get_constraint(
        self,
        field: str,
        scope_id: str
    ) -> Optional[DirectorConstraint]:
        """
        Get a specific constraint by field and scope.

        Args:
            field: Constraint field
            scope_id: Scope identifier

        Returns:
            DirectorConstraint or None
        """
        for c in self._constraints.values():
            if c.field == field and c.scope_id == scope_id:
                return c
        return None

    def remove_constraint(
        self,
        constraint_id: str,
        removed_by: str
    ) -> bool:
        """
        Remove a constraint. Only humans can do this.

        Args:
            constraint_id: ID of constraint to remove
            removed_by: Who removed it

        Returns:
            True if removal succeeded
        """
        if removed_by not in ("charles", "juice", "human"):
            return False

        if constraint_id not in self._constraints:
            return False

        constraint = self._constraints.pop(constraint_id)

        # Log the removal
        removal_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": "constraint_removed",
            "constraint_id": constraint_id,
            "removed_by": removed_by,
            "constraint": asdict(constraint),
        }

        self._append_removal_record(removal_record)
        self._persist_constraints()

        return True

    def validate_output(
        self,
        shot: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[ConstraintViolation]:
        """
        Check if generated output violates any constraints.

        Args:
            shot: Generated shot data
            context: Execution context

        Returns:
            List of ConstraintViolation objects (empty if no violations)
        """
        violations: List[ConstraintViolation] = []
        shot_id = shot.get("shot_id", "unknown")

        # Get constraints applicable to this shot
        applicable = self.get_constraints(shot_id)

        for constraint in applicable:
            # Check constraint against output
            actual = shot.get(constraint.field, "")

            if actual != constraint.value:
                # Determine severity
                severity = self._assess_severity(constraint.field)

                violation = ConstraintViolation(
                    constraint=constraint,
                    actual_value=str(actual),
                    severity=severity,
                    shot_id=shot_id,
                    timestamp=datetime.utcnow().isoformat(),
                    description=f"Expected {constraint.field}='{constraint.value}' but got '{actual}'",
                )

                violations.append(violation)

        return violations

    def _assess_severity(self, field: str) -> str:
        """
        Assess severity of a constraint violation.

        Args:
            field: Field name

        Returns:
            "stylistic" or "critical"
        """
        critical_fields = {
            "character_behavior",
            "scene_tone",
            "narrative_outcome",
            "plot_point",
        }

        return "critical" if field in critical_fields else "stylistic"

    def _persist_constraints(self) -> None:
        """Atomically persist all constraints to disk."""
        os.makedirs("reports", exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir="reports",
            delete=False,
            suffix=".json.tmp"
        ) as tmp:
            tmp_path = tmp.name
            constraints_dict = {
                cid: asdict(c) for cid, c in self._constraints.items()
            }
            json.dump(constraints_dict, tmp, indent=2)

        os.replace(tmp_path, self.constraints_path)

    def _load_constraints(self) -> None:
        """Load constraints from disk if file exists."""
        if not os.path.exists(self.constraints_path):
            return

        try:
            with open(self.constraints_path, "r") as f:
                data = json.load(f)
                for cid, c_dict in data.items():
                    constraint = DirectorConstraint(
                        constraint_id=c_dict["constraint_id"],
                        field=c_dict["field"],
                        value=c_dict["value"],
                        scope=c_dict["scope"],
                        scope_id=c_dict["scope_id"],
                        set_by=c_dict["set_by"],
                        timestamp=c_dict["timestamp"],
                        locked=c_dict.get("locked", True),
                    )
                    self._constraints[cid] = constraint
        except Exception:
            pass  # Load failure is not fatal

    def _append_removal_record(self, record: Dict[str, Any]) -> None:
        """Append constraint removal record to violations log."""
        os.makedirs("reports", exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir="reports",
            delete=False,
            suffix=".jsonl.tmp"
        ) as tmp:
            tmp_path = tmp.name
            if os.path.exists(self.violations_path):
                with open(self.violations_path, "r") as f:
                    tmp.write(f.read())
            tmp.write(json.dumps(record) + "\n")

        os.replace(tmp_path, self.violations_path)


class DirectorConstraintGate(DoctrineGate):
    """
    Post-generation gate: validate output against director constraints.

    Severity levels:
    - Stylistic violations: log + flag for review
    - Critical violations: REJECT + block delivery
    """

    def __init__(self):
        """Initialize constraint validation gate."""
        super().__init__()
        self.gate_position = "post_generation"
        self.gate_name = "SOVEREIGNTY_LAW_02_CONSTRAINT_VALIDATION"
        self.constraint_lock = DirectorConstraintLock()

    def run(
        self,
        shot: Dict[str, Any],
        context: Dict[str, Any]
    ) -> GateResult:
        """
        Validate shot against director constraints.

        Args:
            shot: Generated shot data
            context: Execution context

        Returns:
            GateResult with PASS/WARN/REJECT
        """
        violations = self.constraint_lock.validate_output(shot, context)

        if not violations:
            return GateResult(value="PASS", reason="No constraint violations")

        # Separate by severity
        critical = [v for v in violations if v.severity == "critical"]
        stylistic = [v for v in violations if v.severity == "stylistic"]

        # Record all violations
        ledger = context.get("_ledger")
        if isinstance(ledger, RunLedger):
            for violation in violations:
                ledger.log(
                    LedgerEntry(
                        gate="SOVEREIGNTY_LAW_02",
                        verdict=violation.severity,
                        reason=violation.description,
                        shot_id=shot.get("shot_id", "unknown"),
                        timestamp=violation.timestamp,
                    )
                )

        if critical:
            reason = f"CRITICAL: {len(critical)} constraint violation(s): " + ", ".join(
                [f"{v.constraint.field}" for v in critical]
            )
            return GateResult(value="REJECT", reason=reason)

        if stylistic:
            reason = f"{len(stylistic)} stylistic constraint violation(s) for review"
            return GateResult(value="WARN", reason=reason)

        return GateResult(value="PASS", reason="All constraints satisfied")


# ============================================================================
# SOVEREIGNTY LAW 03 — Learned Preference Subordination
# ============================================================================


class LearnedPreferenceSubordinationGate(DoctrineGate):
    """
    Pre-generation gate: suppress learned preferences when explicit instructions exist.

    Design principle: Learned preferences are ADVISORY only. Explicit Scene Plan
    instructions and Director Constraints are MANDATORY. Any conflict is resolved
    in favor of explicit instructions.
    """

    def __init__(self):
        """Initialize subordination gate."""
        super().__init__()
        self.gate_position = "pre_generation"
        self.gate_name = "SOVEREIGNTY_LAW_03_PREFERENCE_SUBORDINATION"
        self.constraint_lock = DirectorConstraintLock()

    def run(
        self,
        shot: Dict[str, Any],
        context: Dict[str, Any]
    ) -> GateResult:
        """
        Check for preference-vs-instruction conflicts.

        Args:
            shot: Shot plan data
            context: Execution context

        Returns:
            GateResult with PASS/WARN/REJECT
        """
        suppressed_preferences: List[str] = []
        conflicts: List[str] = []

        # Get learned preferences from context (Phase 4 memory system)
        learned_prefs = context.get("_learned_preferences", {})
        if not isinstance(learned_prefs, dict):
            learned_prefs = {}

        # Get explicit constraints
        shot_id = shot.get("shot_id", "unknown")
        constraints = self.constraint_lock.get_constraints(shot_id)
        constraint_fields = {c.field for c in constraints}

        # Get scene plan instructions (if available)
        scene_plan = context.get("_scene_plan", {})
        scene_instructions = scene_plan.get("instructions", {})
        instruction_fields = set(scene_instructions.keys())

        # Check each learned preference
        for pref_field, pref_value in learned_prefs.items():
            # Check for explicit constraint
            if pref_field in constraint_fields:
                constraint = self.constraint_lock.get_constraint(pref_field, shot_id)
                if constraint and constraint.value != pref_value:
                    suppressed_preferences.append(pref_field)
                    conflicts.append(
                        f"{pref_field}: learned={pref_value} vs constraint={constraint.value}"
                    )

            # Check for scene plan instruction
            if pref_field in instruction_fields:
                instruction_value = scene_instructions[pref_field]
                if instruction_value != pref_value:
                    suppressed_preferences.append(pref_field)
                    conflicts.append(
                        f"{pref_field}: learned={pref_value} vs instruction={instruction_value}"
                    )

        # Store suppressed preferences for debugging
        context["_suppressed_preferences"] = suppressed_preferences

        # Log to ledger
        ledger = context.get("_ledger")
        if isinstance(ledger, RunLedger) and suppressed_preferences:
            ledger.log(
                LedgerEntry(
                    gate="SOVEREIGNTY_LAW_03",
                    verdict="SUPPRESSED_PREFERENCES",
                    reason=f"Suppressed {len(suppressed_preferences)} learned preference(s)",
                    shot_id=shot_id,
                    timestamp=datetime.utcnow().isoformat(),
                )
            )

        if conflicts:
            reason = f"Explicit instructions override {len(conflicts)} learned preference conflict(s)"
            return GateResult(value="WARN", reason=reason)

        return GateResult(value="PASS", reason="No preference conflicts")


# ============================================================================
# Top-Level Runners
# ============================================================================


def run_phase6_pre_generation(
    shot: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Phase 6 pre-generation: enforce learned preference subordination.

    Ensures that explicit instructions always take priority over learned patterns.

    Args:
        shot: Shot plan data
        context: Execution context

    Returns:
        Dict with gate result
    """
    gate = LearnedPreferenceSubordinationGate()
    result = gate.run(shot, context)

    return {
        "gate": "SOVEREIGNTY_LAW_03",
        "result": result.value,
        "reason": result.reason,
    }


def run_phase6_post_generation(
    shot: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Phase 6 post-generation: validate director constraints.

    Ensures that generated output respects all explicit director instructions.

    Args:
        shot: Generated shot data
        context: Execution context

    Returns:
        Dict with gate result
    """
    gate = DirectorConstraintGate()
    result = gate.run(shot, context)

    return {
        "gate": "SOVEREIGNTY_LAW_02",
        "result": result.value,
        "reason": result.reason,
    }


def execute_hard_stop(
    context: Dict[str, Any],
    reason: str,
    issued_by: str = "human",
    session_id: str = "unknown"
) -> HardStopReport:
    """
    Emergency hard stop: immediate halt of pipeline.

    This is ALWAYS available and ALWAYS succeeds. Can be called at any time
    to halt the system. No exceptions can prevent a hard stop.

    Args:
        context: Current execution context
        reason: Human-readable reason for hard stop
        issued_by: Who issued the stop (default: "human")
        session_id: Current session ID

    Returns:
        HardStopReport with details of the halt
    """
    protocol = HardStopProtocol(session_id=session_id)
    return protocol.execute_hard_stop(context, reason, issued_by)
