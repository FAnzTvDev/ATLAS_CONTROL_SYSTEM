"""
ATLAS Execution Context - Immutable Mode Registry

This is the keystone of agent governance. All agents MUST:
1. Check for valid execution_context.json before running
2. Refuse to run if mode is missing or contradictory
3. Obey the mode without exception

Modes:
- LOCKED: Read-only verification, no writes
- VERIFY: Read + compare against expected state
- REPAIR: Fix issues found by critics
- OVERWRITE: Force regenerate all artifacts
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal

ExecutionMode = Literal["LOCKED", "VERIFY", "REPAIR", "OVERWRITE"]


class ExecutionContextError(Exception):
    """Raised when execution context is invalid or missing."""
    pass


class ExecutionContext:
    """
    Immutable execution context for agent runs.
    Once locked, mode cannot change until run completes.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.context_path = self.repo_root / "execution_context.json"
        self._context: Optional[dict] = None

    def load(self) -> dict:
        """Load existing context. Raises if missing."""
        if not self.context_path.exists():
            raise ExecutionContextError(
                f"No execution_context.json at {self.context_path}. "
                "Run ops_coordinator.begin_run() first."
            )
        with open(self.context_path) as f:
            self._context = json.load(f)
        return self._context

    def begin_run(
        self,
        mode: ExecutionMode,
        projects: List[str],
        initiated_by: str = "human",
        model_lock: Optional[dict] = None
    ) -> dict:
        """
        Start a new execution run. Creates immutable context.
        """
        if self.context_path.exists():
            existing = self.load()
            if existing.get("locked") and not existing.get("completed_at"):
                raise ExecutionContextError(
                    f"Run {existing['run_id']} is still active. "
                    "Complete or abort it before starting a new run."
                )

        self._context = {
            "run_id": str(uuid.uuid4())[:8],
            "mode": mode,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "projects": projects,
            "locked": True,
            "model_lock": model_lock or {
                "first_frame": "fal-ai/nano-banana-pro",
                "video": "fal-ai/ltx-2.3/image-to-video/fast"
            },
            "initiated_by": initiated_by,
            "completed_at": None,
            "final_verdict": None
        }

        self._save()
        return self._context

    def complete_run(self, verdict: str) -> dict:
        """Mark run as complete with final verdict."""
        if not self._context:
            self.load()

        self._context["completed_at"] = datetime.utcnow().isoformat() + "Z"
        self._context["final_verdict"] = verdict
        self._context["locked"] = False

        self._save()
        return self._context

    def get_mode(self) -> ExecutionMode:
        """Get current execution mode. Raises if not set."""
        if not self._context:
            self.load()
        return self._context["mode"]

    def is_write_allowed(self) -> bool:
        """Check if writes are allowed in current mode."""
        mode = self.get_mode()
        return mode in ("REPAIR", "OVERWRITE")

    def validate_for_agent(self, agent_name: str) -> None:
        """
        Validate context before agent runs.
        Raises ExecutionContextError if agent should refuse to run.
        """
        if not self._context:
            self.load()

        if not self._context.get("locked"):
            raise ExecutionContextError(
                f"Agent {agent_name} refusing: context not locked"
            )

        if self._context.get("completed_at"):
            raise ExecutionContextError(
                f"Agent {agent_name} refusing: run already completed"
            )

        if not self._context.get("mode"):
            raise ExecutionContextError(
                f"Agent {agent_name} refusing: no mode set"
            )

    def _save(self):
        """Write context to disk."""
        with open(self.context_path, "w") as f:
            json.dump(self._context, f, indent=2)


def require_context(agent_name: str):
    """
    Decorator to ensure agent has valid execution context.

    Usage:
        @require_context("cast_agent")
        def run_cast_agent(project, repo_root):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            repo_root = kwargs.get("repo_root") or (args[1] if len(args) > 1 else None)
            if not repo_root:
                raise ExecutionContextError(
                    f"Agent {agent_name}: repo_root required for context validation"
                )

            ctx = ExecutionContext(repo_root)
            ctx.validate_for_agent(agent_name)

            # Inject context into kwargs
            kwargs["_execution_context"] = ctx
            return func(*args, **kwargs)

        return wrapper
    return decorator
