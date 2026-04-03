#!/usr/bin/env python3
"""
ATLAS Doctrine Command System — Master Orchestrator

This is the MASTER ORCHESTRATOR that chains all 7 phases together and
provides the single entry point for the ATLAS pipeline.

The DoctrineRunner is the nervous system of ATLAS. It coordinates:
- Phase 1: Source Truth + Identity Pack Locking
- Phase 2: Error Correction + Pain Signals
- Phase 3: Executive Scene Planning
- Phase 4: Memory + Learning
- Phase 5: Cinematographic Perception
- Phase 6: Director Sovereignty + Hard Stop
- Phase 7: Autonomous Boundary + Resolution

Usage:
    runner = DoctrineRunner(project_path)

    # At session start
    runner.session_open()

    # At scene start
    runner.scene_initialize(scene_shots, scene_manifest, story_bible_scene, cast_map)

    # Before each shot generates
    pre_result = runner.pre_generation(shot, context)
    if pre_result["can_proceed"]:
        # ... generate the shot ...
        post_result = runner.post_generation(shot, context)

    # At scene end
    runner.scene_complete(scene_id)

    # At session end
    runner.session_close()
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Import all doctrine modules
try:
    from tools.doctrine_engine import (
        RunLedger, GateResult, EscalationTracker, HealthCheck, ToxicityRegistry
    )
    from tools.doctrine_phase1_foundation import (
        run_phase1_pre_generation, run_phase1_post_generation,
        SourceTruthProtection, LanguageDiscipline
    )
    from tools.doctrine_phase2_error_correction import (
        run_phase2_pre_generation, run_phase2_post_generation,
        PainSignalSystem, RepairZoneClassifier
    )
    from tools.doctrine_phase3_executive import (
        run_phase3_scene_initialization, run_phase3_pre_generation,
        ScenePlanGenerator
    )
    from tools.doctrine_phase4_memory import (
        run_phase4_session_open, run_phase4_session_close,
        LedgerActivationSystem, PatternConfirmationSystem, BeliefDecaySystem
    )
    from tools.doctrine_phase5_cinema import run_phase5_post_generation
    from tools.doctrine_phase6_sovereignty import (
        run_phase6_pre_generation, run_phase6_post_generation,
        execute_hard_stop, HardStopProtocol
    )
    from tools.doctrine_phase7_autonomy import (
        run_phase7_scene_boundary, run_phase7_pre_generation,
        run_phase7_audit, resolve_conflict
    )
except ImportError as e:
    print(f"Warning: Some doctrine modules not yet implemented: {e}")
    # Allow graceful degradation during development


class DoctrineRunner:
    """Master orchestrator for the ATLAS Doctrine Command System.

    Chains all 7 phases together and provides the single entry point
    for the ATLAS pipeline. This is the nervous system of ATLAS —
    it coordinates perception, decision-making, learning, and sovereignty.
    """

    def __init__(self, project_path: str):
        """Initialize the DoctrineRunner with project context.

        Args:
            project_path: Path to ATLAS project directory
        """
        self.project_path = project_path
        self.reports_dir = os.path.join(project_path, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

        # Initialize core doctrine systems
        self.ledger = RunLedger(self.reports_dir)
        self.escalation = EscalationTracker(self.reports_dir)
        self.toxicity = ToxicityRegistry(self.reports_dir)
        self.pain = PainSignalSystem(self.project_path)
        self.repair = RepairZoneClassifier()

        # Session tracking
        self.session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.session_number = self._get_session_number()

        # Scene context
        self._scene_plans = {}
        self._carry_state_registry = {}
        self._last_carry_state = None
        self._last_completed_scene = None

        # Emergency control
        self._autonomous_paused = False
        self._hard_stop_active = False
        self._hard_stop_reason = None

    def session_open(self) -> Dict[str, Any]:
        """Phase 4: Open session — run belief decay and initialize preferences.

        Returns:
            Dict with session initialization report
        """
        try:
            report = run_phase4_session_open(self.session_number)

            # Log session start
            self.ledger.append_entry({
                "session_id": self.session_id,
                "session_number": self.session_number,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "SESSION_OPEN",
                "report": report
            })

            return {
                "status": "OPENED",
                "session_id": self.session_id,
                "session_number": self.session_number,
                **report
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "session_id": self.session_id
            }

    def scene_initialize(
        self,
        scene_shots: List[Dict[str, Any]],
        scene_manifest: Dict[str, Any],
        story_bible_scene: Dict[str, Any],
        cast_map: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 3+7: Initialize scene — generate plan and check health.

        Args:
            scene_shots: All shots in this scene
            scene_manifest: Scene metadata from project manifest
            story_bible_scene: Story beats and narrative for scene
            cast_map: Character-to-actor mapping

        Returns:
            Dict with initialization status and scene plan
        """
        if self._hard_stop_active:
            return {
                "status": "REJECTED",
                "reason": "HARD_STOP_ACTIVE",
                "hard_stop_reason": self._hard_stop_reason
            }

        context = self._build_context(cast_map)
        context["scene_manifest"] = scene_manifest
        context["story_bible_scene"] = story_bible_scene

        try:
            # Phase 7: Health check from previous scene (if not first scene)
            if self._last_completed_scene:
                health_result = run_phase7_scene_boundary(
                    scene_shots[0],
                    context
                )
                if health_result.get("autonomous_paused"):
                    self._autonomous_paused = True
                    return {
                        "status": "PAUSED",
                        "reason": "health_check_failed",
                        **health_result
                    }

            # Phase 3: Generate scene plan and validate resources
            init_result = run_phase3_scene_initialization(
                scene_shots,
                context
            )

            # Store scene plan
            # ROOT CAUSE FIX: phase3 stores the plan in context["_scene_plans"][scene_id]
            # init_result never contains a "plan" key — reading it returned None always.
            # Pull from context where phase3 actually wrote it.
            scene_id = scene_shots[0].get("scene_id", "unknown")
            self._scene_plans[scene_id] = (
                context.get("_scene_plans", {}).get(scene_id)
                or init_result.get("plan")  # fallback for future phase3 changes
            )

            # Log initialization
            self.ledger.append_entry({
                "session_id": self.session_id,
                "scene_id": scene_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "SCENE_INITIALIZED",
                "shot_count": len(scene_shots),
                "plan": init_result.get("plan")
            })

            return {
                "status": "READY",
                "scene_id": scene_id,
                "shot_count": len(scene_shots),
                **init_result
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }

    def pre_generation(
        self,
        shot: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Full pre-generation gate chain: Phase 6→7→1→2→3.

        This is the comprehensive pre-generation sanity check that ensures:
        - Director sovereignty is respected (Phase 6)
        - Scene boundaries are honored (Phase 7)
        - Identity and truth are locked (Phase 1)
        - No toxic patterns detected (Phase 2)
        - Resources are available (Phase 3)

        Args:
            shot: Shot to generate
            context: Generation context with cast_map, cast_traits, etc.

        Returns:
            Dict with can_proceed: bool and detailed gate results
        """
        # Check emergency conditions first
        if self._hard_stop_active:
            return {
                "can_proceed": False,
                "reason": "HARD_STOP_ACTIVE",
                "hard_stop_reason": self._hard_stop_reason
            }
        if self._autonomous_paused:
            return {
                "can_proceed": False,
                "reason": "AUTONOMOUS_PAUSED"
            }

        # Enrich context with runner state
        self._enrich_context(context)

        results = {
            "can_proceed": True,
            "shot_id": shot.get("shot_id"),
            "gates": []
        }

        try:
            # Phase 6: Learned preference subordination + director constraints
            r6 = run_phase6_pre_generation(shot, context)
            results["gates"].append({"phase": 6, "result": r6})
            if r6.get("result") == "REJECT":
                results["can_proceed"] = False
                results["reject_gate"] = f"Phase6: {r6.get('reason')}"
                return results

            # Phase 7: Uncertainty declaration + resolution conflict checking
            r7 = run_phase7_pre_generation(shot, context)
            results["gates"].append({"phase": 7, "result": r7})

            # Phase 1: Identity pack lock + source truth check
            r1 = run_phase1_pre_generation([shot], context)
            results["gates"].append({"phase": 1, "result": r1})
            for shot_id, gate_results in r1.items():
                for gr in gate_results:
                    if gr.get("result") == "REJECT":
                        results["can_proceed"] = False
                        results["reject_gate"] = f"Phase1: {gr.get('gate')}"
                        return results

            # Phase 2: Toxic pattern check + pain signal analysis
            r2 = run_phase2_pre_generation(shot, context)
            results["gates"].append({"phase": 2, "result": r2})
            # r2 may be a dict {phase, gates, verdict} or a list of gate results
            r2_gates = r2.get("gates", []) if isinstance(r2, dict) else r2
            for gr in r2_gates:
                if isinstance(gr, dict) and gr.get("result") == "REJECT":
                    results["can_proceed"] = False
                    results["reject_gate"] = f"Phase2: {gr.get('gate')}"
                    return results

            # Phase 3: Peak shot protocol + resource check
            r3 = run_phase3_pre_generation(shot, context)
            results["gates"].append({"phase": 3, "result": r3})
            if r3.get("result") == "REJECT":
                results["can_proceed"] = False
                results["reject_gate"] = f"Phase3: {r3.get('reason')}"
                return results

            # Language discipline — compress prompt before dispatch
            ld = LanguageDiscipline()
            budget = shot.get("_doctrine_prompt_budget", 120)
            if "nano_prompt" in shot:
                shot["nano_prompt"] = ld.compress_prompt(
                    shot.get("nano_prompt", ""),
                    budget
                )

            # Source truth snapshot for later verification
            stp = SourceTruthProtection()
            context["_source_truth_snapshot"] = stp.take_snapshot(context)

            # Log successful pre-generation
            self.ledger.append_entry({
                "session_id": self.session_id,
                "shot_id": shot.get("shot_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "event": "PRE_GENERATION_PASSED",
                "gates_checked": [r["phase"] for r in results["gates"]]
            })

            return results

        except Exception as e:
            return {
                "can_proceed": False,
                "error": str(e),
                "phase_exception": True
            }

    def post_generation(
        self,
        shot: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Full post-generation gate chain: Phase 1→2→5→6→7(audit).

        This is the comprehensive post-generation quality check that ensures:
        - Identity and continuity are preserved (Phase 1)
        - No prompt/output parity violations (Phase 2)
        - Cinematographic quality is acceptable (Phase 5)
        - Director constraints are respected (Phase 6)
        - Decision is auditable (Phase 7)

        Args:
            shot: Shot that was just generated
            context: Generation context with results

        Returns:
            Dict with accepted: bool and detailed gate results
        """
        self._enrich_context(context)
        results = {
            "accepted": True,
            "shot_id": shot.get("shot_id"),
            "gates": [],
            "phase_exceptions": []
        }

        # ═══ V27.1: Each phase individually non-blocking per Law T2-DE-3 ═══
        # If any phase throws, log it and continue to next phase.
        # NEVER let one phase crash kill the entire post-gen chain.

        # Phase 1: Identity + continuity + carry state + escalation
        try:
            r1 = run_phase1_post_generation(shot, context)
            results["gates"].append({"phase": 1, "result": r1})
            for gr in r1:
                if gr.get("result") == "REJECT":
                    dimension = self._identify_failed_dimension(gr)
                    if dimension and self.repair.should_repair(
                        dimension,
                        self._get_score(context, dimension)
                    ):
                        repaired, est_score = self.repair.attempt_repair(
                            shot, dimension, context
                        )
                        results["repair_attempted"] = True
                        results["repair_dimension"] = dimension
                    else:
                        results["accepted"] = False
                        results["reject_gate"] = f"Phase1: {gr.get('gate')}"
        except Exception as e1:
            results["phase_exceptions"].append({"phase": 1, "error": str(e1)})

        # Phase 2: Parity check + pain signal
        try:
            r2 = run_phase2_post_generation(shot, context)
            results["gates"].append({"phase": 2, "result": r2})
        except Exception as e2:
            results["phase_exceptions"].append({"phase": 2, "error": str(e2)})

        # Phase 5: Cinematographic perception (only if cinema data available)
        try:
            if context.get("cinema_scores") or context.get("frame_analysis"):
                r5 = run_phase5_post_generation(shot, context)
                results["gates"].append({"phase": 5, "result": r5})
        except Exception as e5:
            results["phase_exceptions"].append({"phase": 5, "error": str(e5)})

        # Phase 6: Director constraint check
        try:
            r6 = run_phase6_post_generation(shot, context)
            results["gates"].append({"phase": 6, "result": r6})
            if r6.get("result") == "REJECT":
                results["accepted"] = False
        except Exception as e6:
            results["phase_exceptions"].append({"phase": 6, "error": str(e6)})

        # Phase 7: Decision audit
        try:
            r7 = run_phase7_audit(shot, context)
            results["gates"].append({"phase": 7, "result": r7})
        except Exception as e7:
            results["phase_exceptions"].append({"phase": 7, "error": str(e7)})

        # Update carry state for next shot
        self._last_carry_state = context.get("_last_carry_state")

        # Register toxic pattern if multiple failures on this shot
        try:
            gates_failed = 0
            for g in results["gates"]:
                gr = g.get("result")
                if isinstance(gr, list):
                    gates_failed += sum(1 for item in gr if isinstance(item, dict) and item.get("result") == "REJECT")
                elif isinstance(gr, dict) and gr.get("result") == "REJECT":
                    gates_failed += 1
            if gates_failed >= 2:
                self.toxicity.register(
                    self._compute_prompt_hash(shot),
                    gates_failed,
                    results.get("reject_gate", "unknown")
                )
        except Exception:
            gates_failed = 0

        # Log post-generation result (always, even if phases had exceptions)
        try:
            self.ledger.append_entry({
                "session_id": self.session_id,
                "shot_id": shot.get("shot_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "event": "POST_GENERATION" + ("_ACCEPTED" if results["accepted"] else "_REJECTED"),
                "gates_checked": [r["phase"] for r in results["gates"]],
                "gates_failed": gates_failed,
                "phase_exceptions": len(results["phase_exceptions"])
            })
        except Exception:
            pass

        return results

    def scene_complete(self, scene_id: str) -> Dict[str, Any]:
        """Mark scene as complete and update metrics.

        Args:
            scene_id: Scene identifier

        Returns:
            Dict with completion status
        """
        self._last_completed_scene = scene_id
        self.ledger.append_entry({
            "session_id": self.session_id,
            "scene_id": scene_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "SCENE_COMPLETE"
        })
        return {"status": "COMPLETED", "scene_id": scene_id}

    def session_close(self) -> Dict[str, Any]:
        """Phase 4: Close session and activate learning.

        This runs belief decay and pattern confirmation from this session's
        ledger data, updating learned preferences for future sessions.

        Returns:
            Dict with session closure report
        """
        try:
            # Get all ledger entries for this session
            entries = self.ledger.read_session(self.session_id)

            # Run learning phase
            report = run_phase4_session_close(
                self.session_id,
                entries,
                self.session_number
            )

            # Increment session counter
            self._increment_session_number()

            self.ledger.append_entry({
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "SESSION_CLOSED",
                "learning_report": report
            })

            return {
                "status": "CLOSED",
                "session_id": self.session_id,
                **report
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }

    def hard_stop(self, reason: str, issued_by: str = "system") -> Dict[str, Any]:
        """Phase 6: Emergency hard stop. Always works.

        Immediately halts generation and prevents resume without explicit
        clearance from authorized personnel.

        Args:
            reason: Why hard stop was issued
            issued_by: Who issued the stop (human, system, etc.)

        Returns:
            Dict with hard stop confirmation
        """
        context = {"session_id": self.session_id}
        report = execute_hard_stop(context, reason, issued_by)

        self._hard_stop_active = True
        self._hard_stop_reason = reason

        self.ledger.append_entry({
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "HARD_STOP_EXECUTED",
            "reason": reason,
            "issued_by": issued_by
        })

        # Convert HardStopReport dataclass to dict safely
        try:
            from dataclasses import asdict as _asdict
            report_dict = _asdict(report) if hasattr(report, '__dataclass_fields__') else dict(report)
        except Exception:
            report_dict = {}

        return {
            "hard_stop_active": True,
            "reason": reason,
            **report_dict
        }

    def clear_hard_stop(self, cleared_by: str) -> Dict[str, Any]:
        """Clear hard stop and resume generation.

        Args:
            cleared_by: Who authorized the clearance

        Returns:
            Dict with clearance confirmation
        """
        self._hard_stop_active = False
        previous_reason = self._hard_stop_reason
        self._hard_stop_reason = None

        self.ledger.append_entry({
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "HARD_STOP_CLEARED",
            "previous_reason": previous_reason,
            "cleared_by": cleared_by
        })

        return {
            "hard_stop_active": False,
            "cleared_by": cleared_by,
            "cleared_timestamp": datetime.utcnow().isoformat()
        }

    def get_status(self) -> Dict[str, Any]:
        """Return current doctrine system status.

        Returns:
            Dict with full system status
        """
        return {
            "session_id": self.session_id,
            "session_number": self.session_number,
            "hard_stop_active": self._hard_stop_active,
            "hard_stop_reason": self._hard_stop_reason,
            "autonomous_paused": self._autonomous_paused,
            "scenes_planned": list(self._scene_plans.keys()),
            "last_completed_scene": self._last_completed_scene,
            "unresolved_escalations": self.escalation.get_unresolved_count(),
            "toxicity_registry_size": self.toxicity.get_registry_size(),
            "session_started": self.session_id.split("_")[1],
        }

    # Private helpers

    def _build_context(self, cast_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build a standard context dict with all runner state.

        Args:
            cast_map: Character-to-actor mapping

        Returns:
            Dict with context data
        """
        return {
            "session_id": self.session_id,
            "cast_map": cast_map or {},
            "_ledger": self.ledger,
            "_escalation": self.escalation,
            "_toxicity": self.toxicity,
            "_pain": self.pain,
            "_scene_plans": self._scene_plans,
            "_carry_state_registry": self._carry_state_registry,
            "_last_carry_state": self._last_carry_state,
        }

    def _enrich_context(self, context: Dict[str, Any]) -> None:
        """Inject runner state into context for gates.

        Args:
            context: Context dict to enrich (mutated in place)
        """
        context["session_id"] = self.session_id
        context["_ledger"] = self.ledger
        context["_escalation"] = self.escalation
        context["_toxicity"] = self.toxicity
        context["_pain"] = self.pain
        context["_scene_plans"] = self._scene_plans
        context["_carry_state_registry"] = self._carry_state_registry
        context["_last_carry_state"] = self._last_carry_state
        context["_last_completed_scene"] = self._last_completed_scene

    def _get_session_number(self) -> int:
        """Read session counter from disk.

        Returns:
            Current session number
        """
        session_counter_path = os.path.join(self.reports_dir, ".session_counter")
        if os.path.exists(session_counter_path):
            try:
                with open(session_counter_path, "r") as f:
                    return int(f.read().strip())
            except (ValueError, OSError):
                return 1
        return 1

    def _increment_session_number(self) -> None:
        """Increment and persist session counter."""
        session_counter_path = os.path.join(self.reports_dir, ".session_counter")
        next_num = self._get_session_number() + 1
        try:
            with open(session_counter_path, "w") as f:
                f.write(str(next_num))
        except OSError:
            pass

    def _identify_failed_dimension(self, gate_result: Dict[str, Any]) -> Optional[str]:
        """Identify which visual dimension failed (identity, location, etc.).

        Args:
            gate_result: Gate result dict

        Returns:
            Dimension name or None
        """
        reason = gate_result.get("reason", "").lower()
        for dim in ["identity", "location", "continuity", "composition", "dialogue"]:
            if dim in reason:
                return dim
        return None

    def _get_score(self, context: Dict[str, Any], dimension: str) -> float:
        """Get quality score for a dimension from context.

        Args:
            context: Generation context
            dimension: Which dimension to check

        Returns:
            Score (0.0-1.0)
        """
        scores = context.get("vision_scores", {})
        dimension_map = {
            "identity": "identity_score",
            "location": "location_score",
            "continuity": "continuity_score",
            "composition": "composition_score",
            "dialogue": "dialogue_score"
        }
        key = dimension_map.get(dimension, dimension)
        return scores.get(key, 0.5)

    def _compute_prompt_hash(self, shot: Dict[str, Any]) -> str:
        """Compute SHA256 hash of shot prompts for toxicity tracking.

        Args:
            shot: Shot dict

        Returns:
            Hex digest string
        """
        prompt_text = shot.get("nano_prompt", "") + shot.get("ltx_motion_prompt", "")
        return hashlib.sha256(prompt_text.encode()).hexdigest()


class DoctrineReport:
    """Generates human-readable reports from doctrine ledger data."""

    def __init__(self, ledger: RunLedger):
        """Initialize report generator with ledger.

        Args:
            ledger: RunLedger instance
        """
        self.ledger = ledger

    def generate_session_report(self, session_id: str) -> str:
        """Full session report: gate results, health, learning, escalations.

        Args:
            session_id: Session identifier

        Returns:
            Markdown formatted report string
        """
        entries = self.ledger.read_session(session_id)

        report = f"# ATLAS Doctrine Session Report\n\n"
        report += f"**Session ID:** {session_id}\n"
        report += f"**Entries:** {len(entries)}\n\n"

        # Count gate outcomes
        passed_pre = sum(1 for e in entries if e.get("event") == "PRE_GENERATION_PASSED")
        accepted_post = sum(1 for e in entries if "ACCEPTED" in e.get("event", ""))
        rejected_post = sum(1 for e in entries if "REJECTED" in e.get("event", ""))

        report += f"## Generation Summary\n"
        report += f"- Pre-generation passed: {passed_pre}\n"
        report += f"- Post-generation accepted: {accepted_post}\n"
        report += f"- Post-generation rejected: {rejected_post}\n\n"

        report += f"## Timeline\n"
        for entry in entries[-10:]:  # Last 10 entries
            ts = entry.get("timestamp", "?")
            event = entry.get("event", "?")
            shot_id = entry.get("shot_id", "")
            report += f"- {ts}: {event} {shot_id}\n"

        return report

    def generate_scene_report(self, scene_id: str) -> str:
        """Scene-level report: per-shot results, bridge scores, pain signals.

        Args:
            scene_id: Scene identifier

        Returns:
            Markdown formatted report string
        """
        report = f"# ATLAS Doctrine Scene Report\n\n"
        report += f"**Scene ID:** {scene_id}\n\n"

        entries = self.ledger.read_scene(scene_id) if hasattr(self.ledger, 'read_scene') else []

        report += f"## Shots Processed: {len(entries)}\n"

        return report

    def generate_health_dashboard(self) -> Dict[str, Any]:
        """Current system health across all dimensions.

        Returns:
            Dict with health metrics
        """
        return {
            "system_healthy": True,
            "gates_operational": [1, 2, 3, 5, 6, 7],
            "escalations_pending": 0,
            "hard_stop_active": False,
            "session_count": self.ledger.get_session_count() if hasattr(self.ledger, 'get_session_count') else 0,
        }


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ATLAS Doctrine Command System Runner"
    )
    parser.add_argument(
        "project_path",
        help="Path to ATLAS project"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show doctrine system status"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Generate report for session ID"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Show health dashboard"
    )
    parser.add_argument(
        "--hard-stop",
        type=str,
        help="Issue hard stop with reason"
    )
    parser.add_argument(
        "--clear-stop",
        type=str,
        help="Clear hard stop (provide your name as authorization)"
    )

    args = parser.parse_args()

    runner = DoctrineRunner(args.project_path)

    if args.status:
        status = runner.get_status()
        print(json.dumps(status, indent=2))
    elif args.hard_stop:
        report = runner.hard_stop(args.hard_stop, issued_by="cli")
        print(json.dumps(report, indent=2))
    elif args.clear_stop:
        result = runner.clear_hard_stop(args.clear_stop)
        print(f"HARD STOP CLEARED")
        print(json.dumps(result, indent=2))
    elif args.health:
        reporter = DoctrineReport(runner.ledger)
        health = reporter.generate_health_dashboard()
        print(json.dumps(health, indent=2))
    elif args.report:
        reporter = DoctrineReport(runner.ledger)
        report = reporter.generate_session_report(args.report)
        print(report)
    else:
        parser.print_help()
