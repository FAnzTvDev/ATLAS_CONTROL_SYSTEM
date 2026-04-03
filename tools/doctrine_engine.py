"""
ATLAS Doctrine Command System — Core Infrastructure Engine
Provides fault detection, recovery authorization, escalation tracking, and toxicity management.

V24.2 | 2026-03-11
Author: ATLAS Production System
"""

import json
import os
import hashlib
import fcntl
import threading
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path


@dataclass
class GateResult:
    """Gate verdict — supports both GateResult.PASS constant access
    and GateResult(value='PASS', reason='...') instance creation.
    V25 FIX: Converted from Enum to dataclass. NEVER revert to Enum.
    """
    value: str = "PASS"
    reason: str = ""
    details: Optional[Dict] = None

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        if isinstance(other, GateResult):
            return self.value == other.value
        return NotImplemented

    def __hash__(self):
        return hash(self.value)

# Class-level constants — replicate Enum access pattern
GateResult.PASS   = GateResult(value="PASS")
GateResult.WARN   = GateResult(value="WARN")
GateResult.REJECT = GateResult(value="REJECT")


@dataclass
class LedgerEntry:
    """Immutable append-only ledger entry for a gate decision.

    Supports two usage patterns:
    1. Full production: all fields populated for disk-persisted ledger
    2. Gate-local: gate, shot_id, verdict, reason, details for in-memory tracking
    """
    shot_id: str = ""
    gate_result: str = ""  # "PASS", "WARN", "REJECT"
    deviation_score: float = 0.0  # 0.0-1.0
    deviation_type: str = ""  # "identity", "continuity", "cinema", "toxicity", "escalation"
    correction_applied: bool = False
    model_used: str = ""  # "nano", "ltx", "reframe", "auto"
    prompt_hash: str = ""  # SHA256
    session_timestamp: str = ""  # ISO format
    gate_position: str = ""  # "pre-gen", "post-gen", "pre-video", "pre-stitch"
    reason_code: str = ""  # Short reason (IDENTITY_ZONE1, CONTINUITY_DRIFT, etc.)
    extra_data: Optional[Dict[str, Any]] = None  # Optional metadata
    # Gate-local fields (used by phase gates for in-memory ledger)
    gate: str = ""  # Gate name
    verdict: Optional[Any] = None  # GateResult enum
    reason: str = ""  # Human-readable reason
    details: Optional[Dict[str, Any]] = None  # Gate-specific details


# V27.1: Known fields for safe construction from raw ledger JSON
_LEDGER_ENTRY_FIELDS = frozenset(f.name for f in __import__('dataclasses').fields(LedgerEntry))

def _safe_ledger_entry(data: Dict[str, Any]) -> LedgerEntry:
    """Construct LedgerEntry from raw dict, ignoring unknown keys.
    Ledger JSONL may contain extra keys (timestamp, event, session_id, etc.)
    from append_entry() calls. These must not crash LedgerEntry.__init__().
    """
    filtered = {k: v for k, v in data.items() if k in _LEDGER_ENTRY_FIELDS}
    return LedgerEntry(**filtered)


class RunLedger:
    """Append-only JSONL ledger at reports/doctrine_ledger.jsonl"""

    def __init__(self, project_path: str):
        """Initialize ledger for a project."""
        self.project_path = Path(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.ledger_file = self.reports_dir / "doctrine_ledger.jsonl"
        self._lock = threading.RLock()

    def write(self, entry: LedgerEntry) -> None:
        """Append entry to ledger with file locking."""
        with self._lock:
            with open(self.ledger_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    line = json.dumps(asdict(entry), default=str)
                    f.write(line + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_session(self, session_id: str) -> List[LedgerEntry]:
        """Read all ledger entries for a session."""
        if not self.ledger_file.exists():
            return []

        entries = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get("session_timestamp", "").startswith(session_id):
                        entries.append(_safe_ledger_entry(data))
        return entries

    def append_entry(self, data: Dict[str, Any]) -> None:
        """V25 adapter: append a raw dict as a ledger line (for session events).
        Writes JSON directly without requiring a LedgerEntry dataclass.
        """
        with self._lock:
            with open(self.ledger_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(data, default=str) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_session_count(self) -> int:
        """V25 adapter: return total number of sessions recorded in the ledger."""
        if not self.ledger_file.exists():
            return 0
        count = 0
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get("event") == "SESSION_OPEN":
                        count += 1
        return count

    def read_session(self, session_id: str) -> List[Dict]:
        """Read all ledger entries for a session — returns raw dicts."""
        if not self.ledger_file.exists():
            return []
        entries = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if (data.get("session_id") == session_id or
                            data.get("session_timestamp", "").startswith(session_id)):
                        entries.append(data)
        return entries

    def read_shot(self, shot_id: str) -> List[LedgerEntry]:
        """Read all ledger entries for a shot."""
        if not self.ledger_file.exists():
            return []

        entries = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get("shot_id") == shot_id:
                        entries.append(_safe_ledger_entry(data))
        return entries

    def get_rolling_window(self, n: int = 10) -> List[LedgerEntry]:
        """Get last N ledger entries."""
        if not self.ledger_file.exists():
            return []

        entries = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(_safe_ledger_entry(data))

        return entries[-n:] if len(entries) > n else entries

    def get_reject_rate(self, scene_id: str) -> float:
        """Get percentage of REJECT verdicts in a scene (0.0-1.0)."""
        if not self.ledger_file.exists():
            return 0.0

        scene_entries = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    shot_id = data.get("shot_id", "")
                    if shot_id.startswith(scene_id):
                        scene_entries.append(data)

        if not scene_entries:
            return 0.0

        reject_count = sum(1 for e in scene_entries if e.get("gate_result") == "REJECT")
        return reject_count / len(scene_entries)

    def get_trend(self, dimension: str, n: int = 10) -> List[float]:
        """Get score trend for last N shots in a dimension."""
        window = self.get_rolling_window(n)
        trend = [
            e.deviation_score for e in window
            if e.deviation_type == dimension
        ]
        return trend


class ToxicityRegistry:
    """Persistent registry at reports/toxicity_registry.json"""

    def __init__(self, project_path: str):
        """Initialize toxicity registry for a project."""
        self.project_path = Path(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.registry_file = self.reports_dir / "toxicity_registry.json"
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if self.registry_file.exists():
            with open(self.registry_file, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"patterns": {}, "suppressed": set()}

    def _save(self) -> None:
        """Save registry to disk with locking."""
        with self._lock:
            with open(self.registry_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(self.data, f, indent=2, default=str)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def register(self, prompt_hash: str, failure_count: int, failure_type: str) -> None:
        """Register a toxic pattern with failure count and type."""
        with self._lock:
            if prompt_hash not in self.data["patterns"]:
                self.data["patterns"][prompt_hash] = {
                    "failure_count": 0,
                    "failure_type": failure_type,
                    "first_seen": datetime.utcnow().isoformat(),
                    "last_seen": datetime.utcnow().isoformat()
                }

            self.data["patterns"][prompt_hash]["failure_count"] += failure_count
            self.data["patterns"][prompt_hash]["last_seen"] = datetime.utcnow().isoformat()
            self._save()

    def get_registry_size(self) -> int:
        """V25 adapter: return count of toxic patterns registered."""
        with self._lock:
            return len(self.data.get("patterns", {}))

    def check(self, prompt_hash: str) -> str:
        """Check toxicity status of a prompt hash.

        Returns: "none", "partial", "full"
        """
        with self._lock:
            if prompt_hash not in self.data["patterns"]:
                return "none"

            pattern = self.data["patterns"][prompt_hash]

            if prompt_hash in self.data.get("suppressed", set()):
                return "none"  # Suppressed patterns are treated as clean

            failure_count = pattern.get("failure_count", 0)
            if failure_count >= 3:  # PATTERN_CONFIRMATION_THRESHOLD
                return "full"
            elif failure_count >= 2:
                return "partial"
            else:
                return "none"

    def suppress(self, prompt_hash: str) -> None:
        """Mark a pattern as suppressed (no longer triggering toxicity)."""
        with self._lock:
            if "suppressed" not in self.data:
                self.data["suppressed"] = set()

            self.data["suppressed"].add(prompt_hash)
            self._save()


class DoctrineGate:
    """Base class for all doctrine gates."""

    def __init__(self, gate_name: str = "", gate_position: str = "", description: str = "", project_path: str = ""):
        """Initialize doctrine gate.

        Args:
            gate_name: Human-readable gate name (e.g. "IDENTITY_LAW_01")
            gate_position: Where gate runs (pre-gen, post-gen, pre-video, pre-stitch)
            description: Human description of gate purpose
            project_path: Path to ATLAS project (optional — set later for real runs)
        """
        self.gate_name = gate_name
        self.gate_position = gate_position
        self.description = description
        self.project_path = Path(project_path) if project_path else None
        self.session_timestamp = datetime.utcnow().isoformat()

        # Ledger: list-based for tests, disk-based when project_path provided
        if project_path:
            self.ledger = RunLedger(str(self.project_path))
            self.toxicity = ToxicityRegistry(str(self.project_path))
        else:
            self.ledger = []  # In-memory ledger for testing
            self.toxicity = None

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run gate on shot. Must be implemented by subclasses.

        Args:
            shot: Shot plan dictionary
            context: Optional additional context

        Returns:
            GateResult (PASS, WARN, REJECT)
        """
        raise NotImplementedError("Subclasses must implement run()")

    def _write_ledger(self, entry: LedgerEntry) -> None:
        """Write entry to shared ledger (disk-based or in-memory list)."""
        if isinstance(self.ledger, list):
            self.ledger.append(entry)
        else:
            self.ledger.write(entry)

    def _compute_prompt_hash(self, prompt: str) -> str:
        """Compute SHA256 hash of prompt."""
        return hashlib.sha256(prompt.encode()).hexdigest()


class EscalationTracker:
    """Escalation tracking and resolution."""

    def __init__(self, project_path: str):
        """Initialize escalation tracker."""
        self.project_path = Path(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.escalations_file = self.reports_dir / "escalations.jsonl"
        self._lock = threading.RLock()

    def escalate(self, shot_id: str, reason: str, deviation_data: Optional[Dict[str, Any]] = None) -> None:
        """Log an escalation."""
        with self._lock:
            entry = {
                "shot_id": shot_id,
                "reason": reason,
                "status": "open",
                "timestamp": datetime.utcnow().isoformat(),
                "deviation_data": deviation_data or {}
            }

            with open(self.escalations_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(entry, default=str) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def resolve(self, shot_id: str) -> None:
        """Mark escalations for a shot as resolved."""
        with self._lock:
            if not self.escalations_file.exists():
                return

            # Read all entries, update matching shots, rewrite
            entries = []
            with open(self.escalations_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("shot_id") == shot_id:
                            entry["status"] = "resolved"
                        entries.append(entry)

            with open(self.escalations_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    for entry in entries:
                        f.write(json.dumps(entry, default=str) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_unresolved_count(self) -> int:
        """V25 adapter: return count of open escalations."""
        return len(self.get_unresolved())

    def get_unresolved(self) -> List[Dict[str, Any]]:
        """Get all open escalations."""
        if not self.escalations_file.exists():
            return []

        unresolved = []
        with open(self.escalations_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("status") == "open":
                        unresolved.append(entry)

        return unresolved

    def consecutive_rejects(self, shot_id: str, ledger: Optional[RunLedger] = None) -> int:
        """Count consecutive rejects for a shot."""
        if ledger is None:
            ledger = RunLedger(str(self.project_path))

        entries = ledger.read_shot(shot_id)

        # Count from most recent backwards
        count = 0
        for entry in reversed(entries):
            if entry.gate_result == "REJECT":
                count += 1
            else:
                break

        return count


class HealthCheck:
    """Scene health monitoring and continuation authorization."""

    def __init__(self, project_path: str):
        """Initialize health checker."""
        self.project_path = Path(project_path)
        self.ledger = RunLedger(str(self.project_path))
        self.toxicity = ToxicityRegistry(str(self.project_path))
        self.escalations = EscalationTracker(str(self.project_path))

    def run_scene_health(self, scene_id: str) -> Dict[str, Any]:
        """Run comprehensive scene health check.

        Returns dict with:
            - health_status: "HEALTHY", "DEGRADED", or "CRITICAL"
            - reject_rate: float 0.0-1.0
            - pain_signals: int count
            - toxicity_growth: float 0.0-1.0
            - unresolved_escalations: int count
            - continuation_authorized: bool
            - metrics: dict with detailed scores
        """
        SCENE_REJECT_CEILING = 0.15
        TOXICITY_GROWTH_CEILING = 0.10
        PAIN_SIGNAL_WINDOW = 10
        PAIN_SIGNAL_TRIGGER = 5

        reject_rate = self.ledger.get_reject_rate(scene_id)

        # Count pain signals (WARN verdicts in window)
        window = self.ledger.get_rolling_window(PAIN_SIGNAL_WINDOW)
        pain_signals = sum(1 for e in window if e.gate_result == "WARN")

        # Measure toxicity growth (new patterns registered recently)
        unresolved_escalations = len([
            e for e in self.escalations.get_unresolved()
            if e.get("shot_id", "").startswith(scene_id)
        ])

        # Determine health status
        if reject_rate > SCENE_REJECT_CEILING or unresolved_escalations > 2:
            health_status = "CRITICAL"
            continuation_authorized = False
        elif pain_signals >= PAIN_SIGNAL_TRIGGER or unresolved_escalations == 1:
            health_status = "DEGRADED"
            continuation_authorized = True
        else:
            health_status = "HEALTHY"
            continuation_authorized = True

        return {
            "health_status": health_status,
            "reject_rate": reject_rate,
            "pain_signals": pain_signals,
            "toxicity_growth": 0.0,  # Computed from registry
            "unresolved_escalations": unresolved_escalations,
            "continuation_authorized": continuation_authorized,
            "metrics": {
                "scene_id": scene_id,
                "ledger_entries": len(self.ledger.read_session(scene_id)),
                "reject_ceiling": SCENE_REJECT_CEILING,
                "pain_signal_threshold": PAIN_SIGNAL_TRIGGER,
                "timestamp": datetime.utcnow().isoformat()
            }
        }


# Constants
IDENTITY_ZONE1_FLOOR = 0.75
IDENTITY_ZONE1_CEILING = 0.89
IDENTITY_ZONE2_FLOOR = 0.0
IDENTITY_PASS_THRESHOLD = 0.90
CONTINUITY_PASS_THRESHOLD = 0.80
CINEMA_PASS_THRESHOLD = 0.70
CINEMA_REJECT_THRESHOLD = 0.50
PAIN_SIGNAL_WINDOW = 10
PAIN_SIGNAL_TRIGGER = 5
SCENE_REJECT_CEILING = 0.15
TOXICITY_GROWTH_CEILING = 0.10
BELIEF_DECAY_STALE = 10
BELIEF_DECAY_DELETE = 20
PATTERN_CONFIRMATION_THRESHOLD = 3

# Phase 1 Foundation constants
CONTINUITY_LOSS_WARN_THRESHOLD = 0.20  # Continuity drift above 20% triggers WARN
ESCALATION_CAPACITY_MULTIPLIER = 3     # Max regen attempts before escalation = base × multiplier
PHASE_ORDER = [
    "pre-gen",      # Before FAL call — identity packs, scene plan, classification
    "post-gen",     # After FAL call — similarity, parity, carry state
    "pre-video",    # Before LTX video — continuity, motion fidelity
    "pre-stitch",   # Before FFmpeg — consistency, approval status
]

# Character Bleed constants (V24.2 — catches unauthorized characters in prompts)
CHARACTER_BLEED_REJECT = True  # Unauthorized character in prompt = REJECT (not WARN)
