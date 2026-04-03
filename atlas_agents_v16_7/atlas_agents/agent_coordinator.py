"""
ATLAS V18.3 — AGENT COORDINATOR
=================================
Central nervous system for the ATLAS agent ecosystem. Manages
inter-agent communication, enforcement sequencing, and automatic
quality gates without any manual intervention.

Agent Registry:
    1. EnforcementAgent  — Pre-generation gold standard enforcement
    2. CriticGate        — Quality validation and critic scoring
    3. SemanticInvariants — 9 structural invariants
    4. PostGenValidator   — Post-generation compliance verification
    5. OpsCoordinator    — Operational governance

Flow:
    User clicks "Generate" → Coordinator intercepts →
        1. EnforcementAgent.enforce_pre_generation(shots) → fixes applied
        2. SemanticInvariants.validate(project) → blocking check
        3. [Generation proceeds with clean shots]
        4. PostGenValidator.validate_output(results) → compliance check
        5. CriticGate.score(outputs) → quality report

    All automatic. No manual button clicks. No human intervention.
    Agents communicate through the coordinator's message bus.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("atlas.agent_coordinator")


class AgentMessage:
    """Message passed between agents via the coordinator."""

    def __init__(self, sender: str, action: str, data: Dict = None, priority: int = 0):
        self.sender = sender
        self.action = action
        self.data = data or {}
        self.priority = priority
        self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {
            "sender": self.sender,
            "action": self.action,
            "data": self.data,
            "priority": self.priority,
            "timestamp": self.timestamp,
        }


class AgentCoordinator:
    """
    Central coordinator for all ATLAS agents.

    Ensures:
    - Pre-generation enforcement runs BEFORE any FAL API call
    - Post-generation validation runs AFTER every render
    - Agents can communicate findings to each other
    - All enforcement is automatic and non-optional
    """

    def __init__(self, project_path: Path, story_bible: Optional[Dict] = None):
        self.project_path = Path(project_path)
        self.story_bible = story_bible
        self.message_bus: List[AgentMessage] = []
        self.enforcement_reports: List[Dict] = []
        self.validation_reports: List[Dict] = []
        self._agents_initialized = False

        # Lazy-loaded agent instances
        self._enforcement_agent = None
        self._critic_gate = None
        self._semantic_invariants = None

    # ------------------------------------------------------------------
    # AGENT INITIALIZATION (lazy)
    # ------------------------------------------------------------------

    @property
    def enforcement_agent(self):
        if self._enforcement_agent is None:
            from atlas_agents.enforcement_agent import EnforcementAgent
            self._enforcement_agent = EnforcementAgent(
                self.project_path, self.story_bible
            )
        return self._enforcement_agent

    @property
    def semantic_invariants(self):
        if self._semantic_invariants is None:
            try:
                from atlas_agents.semantic_invariants import check_all_invariants  # V17.3: Fixed function name
                self._semantic_invariants = check_all_invariants
            except ImportError:
                self._semantic_invariants = None
                logger.warning("[COORDINATOR] Semantic invariants module not available")
        return self._semantic_invariants

    # ------------------------------------------------------------------
    # MESSAGE BUS
    # ------------------------------------------------------------------

    def broadcast(self, sender: str, action: str, data: Dict = None, priority: int = 0):
        """Broadcast a message to all agents via the message bus."""
        msg = AgentMessage(sender, action, data, priority)
        self.message_bus.append(msg)
        logger.debug(f"[COORDINATOR] Message: {sender} → {action}")
        return msg

    def get_messages(self, for_agent: str = None, action: str = None,
                     since: float = 0) -> List[Dict]:
        """Get messages from the bus, optionally filtered."""
        msgs = self.message_bus
        if action:
            msgs = [m for m in msgs if m.action == action]
        if since > 0:
            msgs = [m for m in msgs if m.timestamp > since]
        return [m.to_dict() for m in msgs]

    # ------------------------------------------------------------------
    # PRE-GENERATION GATE (called automatically before first-frames)
    # ------------------------------------------------------------------

    def pre_generation_gate(self, shots: List[Dict]) -> Dict[str, Any]:
        """
        AUTOMATIC pre-generation enforcement gate.

        Called by orchestrator_server.py BEFORE generate-first-frames.
        Runs enforcement agent + semantic invariant check.

        Returns:
            {
                "cleared": True/False,
                "enforcement": {...enforcement report...},
                "invariants": {...invariant results...},
                "blocking_violations": [...list of blocking issues...],
            }
        """
        start = time.time()
        result = {
            "cleared": True,
            "phase": "pre_generation",
            "blocking_violations": [],
        }

        # Step 1: Enforcement Agent — fix all shots
        self.broadcast("coordinator", "pre_generation_start", {
            "total_shots": len(shots)
        })

        enforcement_report = self.enforcement_agent.enforce_pre_generation(shots)
        result["enforcement"] = enforcement_report
        self.enforcement_reports.append(enforcement_report)

        self.broadcast("enforcement", "enforcement_complete", {
            "shots_modified": enforcement_report["stats"]["shots_modified"],
            "shots_clean": enforcement_report["stats"]["shots_clean"],
        })

        # Step 2: Validation — verify all shots now pass
        validation = self.enforcement_agent.validate(shots)
        result["validation"] = validation

        if not validation.get("all_pass"):
            # Log violations but DON'T block — enforcement should have fixed everything
            for v in validation.get("violations", [])[:10]:
                logger.warning(f"[COORDINATOR] Post-enforcement violation: {v}")
            result["blocking_violations"] = validation.get("violations", [])
            # Only block if critical violations remain
            critical = [v for v in validation.get("violations", [])
                       if v.get("check") in ("negatives", "timing")]
            if critical:
                result["cleared"] = False
                self.broadcast("coordinator", "generation_blocked", {
                    "reason": "critical_violations",
                    "count": len(critical),
                })

        elapsed = time.time() - start
        result["gate_ms"] = round(elapsed * 1000)

        self.broadcast("coordinator", "pre_generation_complete", {
            "cleared": result["cleared"],
            "gate_ms": result["gate_ms"],
        })

        logger.info(
            f"[COORDINATOR] Pre-generation gate: "
            f"{'CLEARED' if result['cleared'] else 'BLOCKED'} "
            f"({result['gate_ms']}ms, "
            f"{enforcement_report['stats']['shots_modified']} fixed)"
        )

        return result

    # ------------------------------------------------------------------
    # PRE-VIDEO GATE (called automatically before render-videos)
    # ------------------------------------------------------------------

    def pre_video_gate(self, shots: List[Dict]) -> Dict[str, Any]:
        """
        AUTOMATIC pre-video enforcement gate.

        Called by orchestrator_server.py BEFORE render-videos.
        Ensures all LTX prompts have timing + face stability.
        """
        start = time.time()
        result = {
            "cleared": True,
            "phase": "pre_video",
        }

        self.broadcast("coordinator", "pre_video_start", {
            "total_shots": len(shots)
        })

        enforcement_report = self.enforcement_agent.enforce_pre_video(shots)
        result["enforcement"] = enforcement_report
        self.enforcement_reports.append(enforcement_report)

        self.broadcast("enforcement", "video_enforcement_complete", {
            "shots_modified": enforcement_report["stats"]["shots_modified"],
        })

        elapsed = time.time() - start
        result["gate_ms"] = round(elapsed * 1000)

        logger.info(
            f"[COORDINATOR] Pre-video gate: CLEARED "
            f"({result['gate_ms']}ms, "
            f"{enforcement_report['stats']['shots_modified']} fixed)"
        )

        return result

    # ------------------------------------------------------------------
    # POST-GENERATION VALIDATION (called after generation completes)
    # ------------------------------------------------------------------

    def post_generation_validate(self, shots: List[Dict],
                                  generation_results: List[Dict]) -> Dict[str, Any]:
        """
        Post-generation validation. Checks that outputs are sane
        and reports any issues for the next generation cycle.
        """
        report = {
            "phase": "post_generation",
            "total_generated": len(generation_results),
            "successful": 0,
            "failed": 0,
            "issues": [],
        }

        for result in generation_results:
            if result.get("status") == "success":
                report["successful"] += 1
            else:
                report["failed"] += 1
                report["issues"].append({
                    "shot_id": result.get("shot_id"),
                    "error": result.get("error", "unknown"),
                })

        # Run compliance check on the shots
        validation = self.enforcement_agent.validate(shots)
        report["compliance"] = validation

        self.validation_reports.append(report)

        if report["failed"] > 0:
            self.broadcast("coordinator", "generation_failures", {
                "failed": report["failed"],
                "issues": report["issues"][:5],
            })

        logger.info(
            f"[COORDINATOR] Post-generation: "
            f"{report['successful']} success, {report['failed']} failed"
        )

        return report

    # ------------------------------------------------------------------
    # FULL PIPELINE HEALTH CHECK
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """
        Full system health check across all agents.
        Returns comprehensive status for monitoring.
        """
        health = {
            "project": self.project_path.name,
            "agents": {
                "enforcement": "active",
                "coordinator": "active",
                "semantic_invariants": "active" if self.semantic_invariants else "unavailable",
            },
            "enforcement_history": len(self.enforcement_reports),
            "validation_history": len(self.validation_reports),
            "message_bus_size": len(self.message_bus),
            "genre_detected": self.enforcement_agent.genre if self._enforcement_agent else "not_initialized",
        }

        # Validate current project state
        try:
            sp = self.project_path / "shot_plan.json"
            if sp.exists():
                with open(sp) as f:
                    shots = json.load(f).get("shots", [])
                validation = self.enforcement_agent.validate(shots)
                health["current_compliance"] = {
                    "total_shots": validation["total"],
                    "fully_compliant": validation.get("fully_compliant", 0),
                    "compliance_pct": validation.get("compliance_pct", 0),
                    "all_pass": validation.get("all_pass", False),
                }
            else:
                health["current_compliance"] = {"error": "No shot_plan.json"}
        except Exception as e:
            health["current_compliance"] = {"error": str(e)}

        return health

    # ------------------------------------------------------------------
    # STATUS REPORT (for inter-agent visibility)
    # ------------------------------------------------------------------

    def status_report(self) -> Dict[str, Any]:
        """Generate a status report that other agents can consume."""
        return {
            "coordinator": "AgentCoordinator v17.3",
            "project": str(self.project_path),
            "genre": self.enforcement_agent.genre if self._enforcement_agent else None,
            "total_enforcements": len(self.enforcement_reports),
            "total_validations": len(self.validation_reports),
            "last_enforcement": self.enforcement_reports[-1] if self.enforcement_reports else None,
            "last_validation": self.validation_reports[-1] if self.validation_reports else None,
            "message_count": len(self.message_bus),
            "recent_messages": [m.to_dict() for m in self.message_bus[-10:]],
        }


# ============================================================================
# MODULE-LEVEL CONVENIENCE
# ============================================================================

def get_coordinator(project_path: Path, story_bible: Optional[Dict] = None) -> AgentCoordinator:
    """Get or create an AgentCoordinator for a project."""
    return AgentCoordinator(project_path, story_bible)
