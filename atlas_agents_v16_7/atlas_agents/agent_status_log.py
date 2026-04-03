"""
ATLAS Agent Status Log - Append-Only Event Log

Structured agent summaries are timestamped and append-only.
This provides:
1. Auditability - full history of agent actions
2. Temporal replay meaning - can reconstruct state at any point
3. Debugging - trace exactly what happened and when

Each agent emits a status entry when it completes.
Ops Coordinator reads the log to make decisions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal

AgentState = Literal["STARTED", "COMPLETE", "FAILED", "SKIPPED"]


class AgentStatusLog:
    """
    Append-only log of agent status events.
    File: pipeline_outputs/{project}/_agent_status.json
    """

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.log_path = self.project_path / "_agent_status.json"

    def _read_log(self) -> List[dict]:
        """Read existing log entries."""
        if not self.log_path.exists():
            return []
        with open(self.log_path) as f:
            return json.load(f)

    def _append(self, entry: dict):
        """Append entry to log (never overwrite)."""
        entries = self._read_log()
        entries.append(entry)
        with open(self.log_path, "w") as f:
            json.dump(entries, f, indent=2)

    def emit(
        self,
        agent: str,
        state: AgentState,
        run_id: str,
        facts: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> dict:
        """
        Emit an agent status event.

        Args:
            agent: Agent name (e.g., "cast_agent", "plan_fixer")
            state: STARTED, COMPLETE, FAILED, SKIPPED
            run_id: Execution context run_id
            facts: Machine-readable output (counts, paths, etc.)
            error: Error message if FAILED
            duration_ms: How long agent took

        Returns:
            The emitted entry
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": run_id,
            "agent": agent,
            "state": state,
            "facts": facts or {},
            "error": error,
            "duration_ms": duration_ms
        }

        self._append(entry)
        return entry

    def get_latest_by_agent(self, agent: str) -> Optional[dict]:
        """Get the most recent entry for an agent."""
        entries = self._read_log()
        for entry in reversed(entries):
            if entry.get("agent") == agent:
                return entry
        return None

    def get_run_entries(self, run_id: str) -> List[dict]:
        """Get all entries for a specific run."""
        entries = self._read_log()
        return [e for e in entries if e.get("run_id") == run_id]

    def get_run_summary(self, run_id: str) -> dict:
        """
        Summarize a run's status for Ops Coordinator decision-making.

        Returns:
            {
                "agents_complete": ["cast_agent", "plan_fixer"],
                "agents_failed": [],
                "agents_pending": ["critic_gate"],
                "all_passed": True,
                "blocking_errors": []
            }
        """
        entries = self.get_run_entries(run_id)

        complete = []
        failed = []
        errors = []

        # Track latest state per agent
        agent_states = {}
        for entry in entries:
            agent_states[entry["agent"]] = entry

        for agent, entry in agent_states.items():
            if entry["state"] == "COMPLETE":
                complete.append(agent)
            elif entry["state"] == "FAILED":
                failed.append(agent)
                if entry.get("error"):
                    errors.append(f"{agent}: {entry['error']}")

        return {
            "agents_complete": complete,
            "agents_failed": failed,
            "all_passed": len(failed) == 0,
            "blocking_errors": errors,
            "total_entries": len(entries)
        }


def create_agent_summary(
    agent: str,
    project: str,
    state: AgentState,
    **facts
) -> dict:
    """
    Create a structured agent summary for handoff.

    This is the contract between agents and Ops Coordinator.

    Example:
        summary = create_agent_summary(
            agent="cast_agent",
            project="kord_v17",
            state="COMPLETE",
            characters=20,
            extras_pools=6,
            cast_map_path="/path/to/cast_map.json"
        )
    """
    return {
        "agent": agent,
        "project": project,
        "state": state,
        "facts": facts,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
