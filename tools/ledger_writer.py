"""
ATLAS V26.1 — LEDGER WRITER
==============================
Structured decision logging for the V26.1 pipeline.

Every decision has: WHO decided, WHAT was decided, WHY, WHEN, and the EVIDENCE.
The ledger is append-only JSONL, never truncated, never overwritten.

Decision types:
  - COMPILE: Shot state compiled from shot_plan
  - ROUTE: Engine routing decision (ltx/kling/auto/dual)
  - VALIDATE: Payload validation result
  - CHAIN: Chain classification + source resolution
  - APPROVE: Keyframe approved/rejected with scores
  - ENDFRAME: End frame reuse verdict
  - GENERATE: FAL API call made with params
  - SCORE: Post-generation vision score
  - HALT: Pipeline halted with reason
  - OVERRIDE: Manual override by user/operator

Ledger location: pipeline_outputs/{project}/reports/v26_ledger.jsonl

Author: ATLAS Production System
Version: V26.1 | 2026-03-15
"""

import json
import os
import fcntl
import threading
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path


@dataclass
class LedgerEvent:
    """Structured event for V26.1 decision logging.

    Every event captures:
      - timestamp: ISO 8601 UTC (auto-filled if not provided)
      - session_id: unique session identifier for grouping decisions
      - event_type: one of COMPILE|ROUTE|VALIDATE|CHAIN|APPROVE|ENDFRAME|GENERATE|SCORE|HALT|OVERRIDE
      - shot_id: which shot this decision affects
      - scene_id: which scene contains the shot
      - decision: human-readable summary of the choice
      - evidence: structured data backing the decision
      - actor: who/what made the decision
      - confidence: 0.0-1.0 confidence in the decision
      - tags: searchable labels (e.g., ["dialogue", "character-ref", "missing"])
    """
    timestamp: str = ""
    session_id: str = ""
    event_type: str = ""  # COMPILE|ROUTE|VALIDATE|CHAIN|APPROVE|ENDFRAME|GENERATE|SCORE|HALT|OVERRIDE
    shot_id: str = ""
    scene_id: str = ""
    decision: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    actor: str = ""  # controller|router|validator|chain_policy|keyframe_gate|endframe_gate|vision|operator
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Auto-fill timestamp if empty."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_json_line(self) -> str:
        """Convert to JSONL format (single line)."""
        return json.dumps(asdict(self))


class V26Ledger:
    """Append-only ledger writer for V26.1 decision logging.

    File location: pipeline_outputs/{project}/reports/v26_ledger.jsonl
    Format: JSONL (one LedgerEvent per line)
    Thread-safe: fcntl.LOCK_EX on every write
    Non-blocking: IOError/OSError logged to stderr, pipeline continues
    """

    def __init__(self, project_path: str, session_id: str):
        """Initialize ledger for a project.

        Args:
            project_path: /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{project}
            session_id: unique session identifier for grouping events
        """
        self.project_path = Path(project_path)
        self.session_id = session_id
        self.lock = threading.Lock()

        # Create reports directory if needed
        self.reports_dir = self.project_path / "reports"
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"[LEDGER] Warning: Could not create reports dir: {e}", file=sys.stderr)

        self.ledger_path = self.reports_dir / "v26_ledger.jsonl"
        self._in_memory_events: List[LedgerEvent] = []

    def write(self, event: LedgerEvent) -> bool:
        """Append event to JSONL ledger.

        Thread-safe with fcntl.LOCK_EX. Flushes immediately.
        Non-blocking: returns False on I/O error, continues pipeline.

        Args:
            event: LedgerEvent to write

        Returns:
            True if written, False if error occurred
        """
        # Ensure session_id is set
        if not event.session_id:
            event.session_id = self.session_id

        # Ensure timestamp is set
        if not event.timestamp:
            event.timestamp = datetime.utcnow().isoformat() + "Z"

        # Store in memory for get_session_events()
        with self.lock:
            self._in_memory_events.append(event)

        # Write to disk
        try:
            with open(self.ledger_path, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(event.to_json_line() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return True
        except (IOError, OSError) as e:
            print(f"[LEDGER] Write error for shot {event.shot_id}: {e}", file=sys.stderr)
            return False

    def log_compile(self, shot_id: str, scene_id: str, shot_state: Dict[str, Any]) -> bool:
        """Log COMPILE event — shot compiled from shot_plan.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            shot_state: dict with nano_prompt, ltx_motion_prompt, model, etc.

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="COMPILE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Compiled shot {shot_id} for {shot_state.get('model', 'unknown')} generation",
            evidence={
                "model": shot_state.get("model", ""),
                "duration_seconds": shot_state.get("duration_seconds"),
                "has_dialogue": bool(shot_state.get("dialogue_text")),
                "has_character_refs": bool(shot_state.get("character_references")),
                "coverage_role": shot_state.get("coverage_role", ""),
            },
            actor="controller",
            confidence=1.0,
            tags=["compile"],
        )
        return self.write(event)

    def log_route(self, shot_id: str, scene_id: str, engine: str, reason: str,
                  fallback: Optional[str] = None) -> bool:
        """Log ROUTE event — engine routing decision.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            engine: chosen engine (ltx|kling|auto|dual)
            reason: why this engine was chosen
            fallback: fallback engine if primary fails

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="ROUTE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Routed shot {shot_id} to {engine} engine",
            evidence={
                "primary_engine": engine,
                "routing_reason": reason,
                "fallback_engine": fallback or "none",
            },
            actor="router",
            confidence=0.95,
            tags=["route", engine],
        )
        return self.write(event)

    def log_validate(self, shot_id: str, scene_id: str, engine: str,
                    stripped_params: Dict[str, Any], violations: List[str]) -> bool:
        """Log VALIDATE event — payload validation.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            engine: which engine was validated for
            stripped_params: parameters that were validated/cleaned
            violations: list of violations found and corrected

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="VALIDATE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Validated {engine} payload for shot {shot_id}",
            evidence={
                "engine": engine,
                "violations_count": len(violations),
                "violations": violations,
                "params_keys": list(stripped_params.keys()),
            },
            actor="validator",
            confidence=1.0,
            tags=["validate", engine] + (["violations"] if violations else []),
        )
        return self.write(event)

    def log_chain(self, shot_id: str, scene_id: str, classification: str,
                  source_policy: str, chain_from: Optional[str] = None) -> bool:
        """Log CHAIN event — chain classification + source.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            classification: anchor|chain|end_frame_reframe|independent_parallel|bootstrap_establishing
            source_policy: which policy made the classification
            chain_from: if chained, which shot it chains from

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="CHAIN",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Classified shot {shot_id} as {classification}",
            evidence={
                "classification": classification,
                "source_policy": source_policy,
                "chain_from": chain_from or "none",
            },
            actor="chain_policy",
            confidence=0.95,
            tags=["chain", classification],
        )
        return self.write(event)

    def log_approve(self, shot_id: str, scene_id: str, verdict: str,
                   scores: Dict[str, float], reasons: List[str]) -> bool:
        """Log APPROVE event — keyframe approved/rejected with scores.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            verdict: APPROVED|REJECTED
            scores: dict of scored metrics (identity, location, composition, etc.)
            reasons: list of reasons for the verdict

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="APPROVE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Keyframe {shot_id} {verdict}",
            evidence={
                "verdict": verdict,
                "scores": scores,
                "reasons": reasons,
            },
            actor="keyframe_gate",
            confidence=scores.get("overall_confidence", 0.85),
            tags=["approve", verdict.lower()] + list(scores.keys()),
        )
        return self.write(event)

    def log_endframe(self, shot_id: str, scene_id: str, verdict: str,
                    analysis: Dict[str, Any]) -> bool:
        """Log ENDFRAME event — end frame reuse verdict.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            verdict: REUSED|REGENERATED|FALLBACK
            analysis: dict with analysis results (dramatic equivalence, hash match, etc.)

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="ENDFRAME",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"End frame for shot {shot_id}: {verdict}",
            evidence={
                "verdict": verdict,
                **analysis,
            },
            actor="endframe_gate",
            confidence=analysis.get("confidence", 0.85),
            tags=["endframe", verdict.lower()],
        )
        return self.write(event)

    def log_generate(self, shot_id: str, scene_id: str, engine: str,
                    endpoint: str, params_summary: Dict[str, Any]) -> bool:
        """Log GENERATE event — FAL API call made.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            engine: which engine was called
            endpoint: API endpoint or function called
            params_summary: summary of parameters sent (not full params)

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="GENERATE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Generated frame for shot {shot_id} via {engine}",
            evidence={
                "engine": engine,
                "endpoint": endpoint,
                "params": params_summary,
            },
            actor="controller",
            confidence=1.0,
            tags=["generate", engine, endpoint],
        )
        return self.write(event)

    def log_score(self, shot_id: str, scene_id: str, score_type: str,
                 score_value: float, evidence: Dict[str, Any]) -> bool:
        """Log SCORE event — post-generation vision score.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            score_type: identity|location|composition|sharpness|continuity
            score_value: 0.0-1.0 score
            evidence: dict with scoring details

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="SCORE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Vision scored {score_type} for shot {shot_id}: {score_value:.3f}",
            evidence={
                "score_type": score_type,
                "score_value": score_value,
                **evidence,
            },
            actor="vision",
            confidence=score_value,  # Confidence reflects the score itself
            tags=["score", score_type],
        )
        return self.write(event)

    def log_halt(self, shot_id: str, scene_id: str, reason: str,
                evidence: Dict[str, Any]) -> bool:
        """Log HALT event — pipeline halted.

        Args:
            shot_id: shot identifier (may be "" if scene-level halt)
            scene_id: scene identifier
            reason: why pipeline was halted
            evidence: dict with halt details

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="HALT",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Pipeline halted: {reason}",
            evidence={
                "halt_reason": reason,
                **evidence,
            },
            actor="controller",
            confidence=1.0,
            tags=["halt"],
        )
        return self.write(event)

    def log_override(self, shot_id: str, scene_id: str, field: str,
                    old_value: Any, new_value: Any, operator: str) -> bool:
        """Log OVERRIDE event — manual override by operator.

        Args:
            shot_id: shot identifier
            scene_id: scene identifier
            field: which field was overridden
            old_value: previous value
            new_value: new value
            operator: who made the override

        Returns:
            True if written
        """
        event = LedgerEvent(
            session_id=self.session_id,
            event_type="OVERRIDE",
            shot_id=shot_id,
            scene_id=scene_id,
            decision=f"Operator overrode {field} for shot {shot_id}",
            evidence={
                "field": field,
                "old_value": str(old_value),
                "new_value": str(new_value),
                "operator": operator,
            },
            actor="operator",
            confidence=1.0,
            tags=["override", field],
        )
        return self.write(event)

    def get_session_events(self) -> List[LedgerEvent]:
        """Get all events from current session (in-memory).

        Returns:
            List of LedgerEvent objects
        """
        with self.lock:
            return list(self._in_memory_events)

    def get_shot_history(self, shot_id: str) -> List[LedgerEvent]:
        """Get all events for a specific shot.

        Reads from disk to get complete history across all sessions.

        Args:
            shot_id: shot identifier

        Returns:
            List of LedgerEvent objects for this shot
        """
        events = []
        try:
            if not self.ledger_path.exists():
                return events

            with open(self.ledger_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("shot_id") == shot_id:
                            event = LedgerEvent(**data)
                            events.append(event)
                    except json.JSONDecodeError:
                        print(f"[LEDGER] Warning: Could not parse JSON line: {line[:80]}", file=sys.stderr)
                        continue
        except (IOError, OSError) as e:
            print(f"[LEDGER] Read error for shot {shot_id}: {e}", file=sys.stderr)

        return events

    def get_halt_events(self) -> List[LedgerEvent]:
        """Get all HALT events from current session.

        Returns:
            List of LedgerEvent objects with event_type == "HALT"
        """
        with self.lock:
            return [e for e in self._in_memory_events if e.event_type == "HALT"]


# Singleton instance per project (optional, for convenience)
_ledger_instances: Dict[str, V26Ledger] = {}
_ledger_lock = threading.Lock()


def get_ledger(project_path: str, session_id: str) -> V26Ledger:
    """Get or create ledger instance for a project (thread-safe singleton).

    Args:
        project_path: project directory path
        session_id: unique session identifier

    Returns:
        V26Ledger instance
    """
    key = str(project_path)
    with _ledger_lock:
        if key not in _ledger_instances:
            _ledger_instances[key] = V26Ledger(project_path, session_id)
        return _ledger_instances[key]
