"""
ATLAS V23 BaseAgent — Standard Agent Interface

All active agents inherit from this base class.
Provides consistent validation, auto-fix, and logging patterns.

The BaseAgent pattern ensures:
- Uniform reporting across all 25+ agents
- Consistent error handling and recovery
- Auto-fix capability without code duplication
- Proper timing instrumentation
- Blocking vs. advisory classification

Usage:
    class MyAgent(BaseAgent):
        def validate(self, shots, project_path, **kwargs):
            report = AgentReport("MyAgent", "v23.0")
            # Run validation logic
            if bad_thing:
                report.add_finding("critical", "CODE", "message", shot_id="001_001")
            return report

    agent = MyAgent("MyAgent", "v23.0", blocking=True)
    report = agent.run(shots, project_path)
    if report.status == "fail":
        # Generation blocked
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import time
import json
import logging

logger = logging.getLogger("atlas.agents")


@dataclass
class AgentFinding:
    """Single finding from an agent validation run."""
    level: str  # "critical", "warning", "info"
    code: str  # e.g. "BIO_BLEED", "MISSING_REF", "POSE_CHANGE"
    message: str
    shot_id: Optional[str] = None
    auto_fixed: bool = False
    details: Optional[Dict] = None


@dataclass
class AgentReport:
    """Complete report from an agent validation run."""
    agent_name: str
    agent_version: str
    status: str = "pass"  # "pass", "warn", "fail"
    findings: List[AgentFinding] = field(default_factory=list)
    auto_fixes_applied: int = 0
    shots_checked: int = 0
    duration_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        """Count of critical-severity findings."""
        return sum(1 for f in self.findings if f.level == "critical")

    @property
    def warning_count(self) -> int:
        """Count of warning-severity findings."""
        return sum(1 for f in self.findings if f.level == "warning")

    @property
    def info_count(self) -> int:
        """Count of informational findings."""
        return sum(1 for f in self.findings if f.level == "info")

    def add_finding(self, level, code, message, shot_id=None, auto_fixed=False, details=None):
        """Add a finding to the report and update status."""
        self.findings.append(AgentFinding(level=level, code=code, message=message,
                                          shot_id=shot_id, auto_fixed=auto_fixed, details=details))
        if level == "critical" and not auto_fixed:
            self.status = "fail"
        elif level == "warning" and self.status == "pass":
            self.status = "warn"

    def to_dict(self) -> Dict:
        """Serialize report to JSON-compatible dict."""
        return {
            "agent": self.agent_name,
            "version": self.agent_version,
            "status": self.status,
            "findings_count": len(self.findings),
            "critical": self.critical_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "auto_fixes": self.auto_fixes_applied,
            "shots_checked": self.shots_checked,
            "duration_ms": round(self.duration_ms, 1),
            "findings": [
                {"level": f.level, "code": f.code, "message": f.message,
                 "shot_id": f.shot_id, "auto_fixed": f.auto_fixed}
                for f in self.findings
            ]
        }

    def to_json(self) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class BaseAgent(ABC):
    """
    Base class for all ATLAS agents.

    All agents must implement validate().
    Agents may optionally implement auto_fix().

    Subclass Pattern:
        1. Inherit from BaseAgent
        2. Implement validate() — return AgentReport
        3. Optionally implement auto_fix() — return modified shots
        4. Call self.run(shots, project_path) to execute validate→fix→validate chain

    Error Handling:
        - Critical findings block generation if blocking=True
        - Warning findings log but don't block
        - Info findings are advisory only
        - Exceptions in auto_fix are caught and logged as warnings

    Timing:
        - self.run() measures total time including auto-fix
        - Report.duration_ms is milliseconds
    """

    def __init__(self, name: str, version: str, blocking: bool = True):
        """
        Initialize agent.

        Args:
            name: Agent identifier (e.g. "EnforcementAgent")
            version: Version string (e.g. "v23.0")
            blocking: If True, critical findings block generation
        """
        self.name = name
        self.version = version
        self.blocking = blocking  # If True, failures block generation
        self._logger = logging.getLogger(f"atlas.agents.{name}")

    @abstractmethod
    def validate(self, shots: List[Dict], project_path: Path, **kwargs) -> AgentReport:
        """
        Main validation method. All agents MUST implement this.

        Validation should:
        - Check all shots for invariant violations
        - Log findings via report.add_finding()
        - Return AgentReport with status set appropriately

        Args:
            shots: List of shot dicts from shot_plan.json
            project_path: Path to project directory
            **kwargs: Agent-specific parameters (cast_map, story_bible, scene_manifest, etc.)

        Returns:
            AgentReport with findings and status

        Example:
            report = AgentReport("MyAgent", "v23.0")
            for shot in shots:
                if not shot.get("nano_prompt"):
                    report.add_finding("critical", "MISSING_NANO",
                                       "Shot missing nano_prompt", shot_id=shot["shot_id"])
            return report
        """
        pass

    def auto_fix(self, shots: List[Dict], project_path: Path, **kwargs) -> List[Dict]:
        """
        Optional auto-fix capability. Override in subclass if agent can fix issues.

        Auto-fix should:
        - Modify shots IN PLACE or create copies
        - Return the (possibly modified) shots list
        - NOT remove shots (only mutate fields)

        Default implementation: returns shots unchanged.

        Args:
            shots: List of shot dicts
            project_path: Path to project directory
            **kwargs: Same kwargs as validate()

        Returns:
            Modified shots list (or original if no changes)
        """
        return shots

    def run(self, shots: List[Dict], project_path: Path, auto_fix_enabled: bool = True, **kwargs) -> AgentReport:
        """
        Standard execution flow: validate → optionally auto_fix → re-validate.

        This is the primary entry point for running an agent.
        Orchestrates the full validate→fix→validate chain with proper error handling.

        Args:
            shots: List of shot dicts from shot_plan.json
            project_path: Path to project directory
            auto_fix_enabled: If True, attempt auto_fix on findings (default True)
            **kwargs: Agent-specific parameters passed to validate/auto_fix

        Returns:
            Final AgentReport after validation and optional auto-fix

        Flow:
            1. Start timer
            2. Call validate() → get initial report
            3. If auto_fix_enabled and there are fixable issues:
               a. Call auto_fix() to modify shots
               b. Call validate() again on modified shots
               c. Compare before/after to compute fixes_applied
            4. Stop timer, set duration_ms
            5. Log summary
            6. Return report
        """
        start = time.time()

        # Initial validation
        report = self.validate(shots, project_path, **kwargs)
        report.shots_checked = len(shots)

        # Auto-fix if enabled and there are fixable issues
        if auto_fix_enabled and report.status in ("warn", "fail"):
            fixable = [f for f in report.findings if not f.auto_fixed and f.level in ("critical", "warning")]
            if fixable:
                self._logger.info(f"[{self.name}] Attempting auto-fix for {len(fixable)} findings...")
                try:
                    fixed_shots = self.auto_fix(shots, project_path, **kwargs)
                    # Verify shot count didn't change (safety check)
                    if len(fixed_shots) != len(shots):
                        self._logger.warning(f"[{self.name}] auto_fix changed shot count: {len(shots)} → {len(fixed_shots)}")
                    # Re-validate after fix
                    re_report = self.validate(fixed_shots, project_path, **kwargs)
                    re_report.shots_checked = len(shots)
                    # Count how many issues were fixed
                    re_report.auto_fixes_applied = (report.critical_count - re_report.critical_count) + \
                                                   (report.warning_count - re_report.warning_count)
                    report = re_report
                except Exception as e:
                    self._logger.warning(f"[{self.name}] Auto-fix failed: {e}")
                    report.add_finding("warning", "AUTO_FIX_FAILED", f"Auto-fix error: {str(e)}")

        report.duration_ms = (time.time() - start) * 1000
        self._logger.info(f"[{self.name}] {report.status.upper()} — {report.critical_count} critical, "
                          f"{report.warning_count} warnings ({report.duration_ms:.0f}ms)")
        return report

    def __repr__(self):
        return f"<{self.name} v{self.version} {'BLOCKING' if self.blocking else 'advisory'}>"


# ────────────────────────────────────────────────────────────
# Agent Registry — All Active Agents for V23 Phase 4
# ────────────────────────────────────────────────────────────

ACTIVE_AGENTS = [
    # Core enforcement (blocking)
    "enforcement_agent.EnforcementAgent",          # V23.0 | V13 gold standard enforcement
    "semantic_invariants.SemanticInvariantsAgent", # V23.0 | 15 invariants (11 blocking, 4 warning)
    "critic_gate.CriticGate",                      # V23.0 | Final authority on readiness

    # Script & narrative (blocking)
    "script_fidelity_agent.ScriptFidelityAgent",   # V23.0 | Beat→shot validation + dialogue fidelity

    # Continuity & state (blocking)
    "continuity_gate.ContinuityGate",              # V23.0 | State tracking + coverage + pose validation

    # Vision & oversight (warning-level)
    "logical_oversight_agent.LogicalOversightAgent", # V23.0 | 4-gate LOA policy engine

    # Costume & production (non-blocking)
    "wardrobe_extras_agent.WardrobeExtrasAgent",   # V23.0 | Wardrobe look IDs + crowd packs

    # Chain & rendering (blocking during render)
    "master_shot_chain_agent.MasterShotChainAgent",       # V23.0 | Master shot chain pipeline
    "autonomous_director_agent.AutonomousDirectorAgent",  # V23.0 | 9-stage autonomous render

    # Orchestration (meta-agent)
    "agent_coordinator.AgentCoordinator",          # V23.0 | Central hub + message bus
]

# Agents archived in V23 Phase 2 refactor (kept for reference)
ARCHIVED_AGENTS = [
    # Legacy v9-v20 agents (removed due to V21 rewrite)
    "v9_legacy_adapter",
    "staleness_agent",
    "pre_production_validator",
    "script_auto_advancer",
    "scene_template_enforcer",
    "viewer_retention_engine",
    "script_compliance_validator",
    "v20_story_intelligence",
    "v20_shot_type_enricher",
]

# Planned for future phases
EXPERIMENTAL_AGENTS = [
    # V24+ features under development
    # "dialogue_timing_agent",
    # "performance_capture_agent",
    # "music_beat_sync_agent",
]
