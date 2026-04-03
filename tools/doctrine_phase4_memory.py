"""
DOCTRINE PHASE 4 — Memory, Learning, and Feedback System
Learns from generation outcomes and guides future decisions through pattern confirmation and belief decay.

Key Systems:
  1. Ledger Activation: Feed-forward learning from session ledger entries
  2. Pattern Confirmation: Stable vs provisional patterns with threshold-based promotion
  3. Belief Decay: Time-based confidence decay for stale or unconfirmed patterns

v24.2 — Integrated with doctrine_engine GateResult/DoctrineGate/RunLedger
"""

import json
import os
import tempfile
import fcntl
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import hashlib

# Constants from doctrine_engine
BELIEF_DECAY_STALE = 10  # Sessions until stable pattern demotes to provisional
BELIEF_DECAY_DELETE = 20  # Sessions until provisional pattern is deleted
PATTERN_CONFIRMATION_THRESHOLD = 3  # Confirmations needed to go stable
CONFIDENCE_STABLE = 0.8
CONFIDENCE_PROVISIONAL = 0.3
CONFIDENCE_DECAYED = 0.4


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ActorProfileUpdate:
    """Learning about how an actor performs under specific conditions."""
    character_name: str
    condition: str  # e.g., "low_light_three_quarter", "high_key_medium"
    confidence_adjustment: float  # +/- delta to apply to current confidence
    source_session: str
    source_shots: List[str]  # shot_ids that contributed evidence
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ActorProfileUpdate":
        return cls(**d)


@dataclass
class PromptTemplateRisk:
    """Learning about risky or problematic prompt templates."""
    template_hash: str
    template_snippet: str  # first 100 chars for identification
    risk_score: float  # 0.0-1.0, higher = more risky
    failure_count: int
    failure_types: List[str]  # list of deviation types (identity_drift, location_bleed, etc)
    last_failure_session: str
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "PromptTemplateRisk":
        return cls(**d)


@dataclass
class ModelRoutingUpdate:
    """Learning about which models perform best under which conditions."""
    shot_class: str  # HERO/CONNECTIVE/ESTABLISHING/BROLL
    lighting_condition: str  # high_key/low_key/natural/mixed
    emotional_register: str  # tension/calm/grief/hope/conflict/resolution
    preferred_model: str  # model that performed best
    performance_delta: float  # how much better than alternative (0.0-1.0)
    confirmation_count: int  # how many sessions confirmed this
    source_sessions: List[str]
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ModelRoutingUpdate":
        return cls(**d)


@dataclass
class LearnedPattern:
    """A stable or provisional learning across sessions."""
    pattern_id: str
    pattern_type: str  # actor_profile / prompt_template / model_routing
    condition_key: str  # composite key describing comparable context
    outcome: str  # what was learned
    confirmation_count: int
    confirmation_sessions: List[str]
    confidence_score: float  # 0.0-1.0
    status: str  # provisional / stable
    first_observed: str
    last_confirmed: str

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "LearnedPattern":
        return cls(**d)


@dataclass
class DecayReport:
    """Result of a belief decay housekeeping pass."""
    patterns_reviewed: int
    patterns_demoted: int  # stable → provisional
    patterns_deleted: int  # provisional → removed
    patterns_flagged: int  # flagged for manual review
    session_number: int
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# LEDGER ACTIVATION SYSTEM — Feed-Forward Learning
# ============================================================================

class LedgerActivationSystem:
    """
    Processes session ledger entries to generate actor profile updates,
    prompt template risks, and model routing recommendations.
    """

    def __init__(self):
        self.actor_profiles: Dict[str, Dict] = {}
        self.prompt_risks: Dict[str, PromptTemplateRisk] = {}
        self.model_routes: Dict[str, ModelRoutingUpdate] = {}

    def activate_session_learning(
        self, session_id: str, ledger_entries: List[Dict]
    ) -> Dict:
        """
        Process ledger entries from a session and generate updates.

        Args:
            session_id: session identifier
            ledger_entries: list of ledger entries from RunLedger

        Returns:
            dict with keys:
              - actor_profile_updates: count
              - prompt_template_risks: count
              - model_routing_updates: count
        """
        if not ledger_entries:
            return {
                "actor_profile_updates": 0,
                "prompt_template_risks": 0,
                "model_routing_updates": 0,
            }

        # Group entries by type
        by_character = defaultdict(list)
        by_template = defaultdict(list)
        by_model_route = defaultdict(list)

        for entry in ledger_entries:
            verdict = entry.get("verdict", "UNKNOWN")
            gate_id = entry.get("gate_id", "")
            shot_id = entry.get("shot_id", "")
            context = entry.get("context", {})

            # Extract learnable signals
            character_name = context.get("character_name")
            if character_name and verdict != "UNKNOWN":
                lighting = context.get("lighting_condition", "unknown")
                shot_type = context.get("shot_type", "unknown")
                condition = f"{lighting}_{shot_type}"
                by_character[character_name].append({
                    "verdict": verdict,
                    "condition": condition,
                    "shot_id": shot_id,
                    "gate_id": gate_id,
                })

            # Template hash from gate_id (simplified)
            if gate_id and verdict in ["REJECT", "WARN"]:
                template_hash = hashlib.sha256(
                    gate_id.encode()
                ).hexdigest()[:16]
                by_template[template_hash].append({
                    "verdict": verdict,
                    "shot_id": shot_id,
                    "gate_id": gate_id,
                    "deviation": entry.get("deviation_detail", ""),
                })

            # Model routing from model selection
            model_used = context.get("model_used")
            if model_used and verdict != "UNKNOWN":
                shot_class = context.get("shot_class", "UNKNOWN")
                lighting = context.get("lighting_condition", "unknown")
                emotion = context.get("emotional_register", "unknown")
                route_key = f"{shot_class}_{lighting}_{emotion}_{model_used}"
                by_model_route[route_key].append({
                    "verdict": verdict,
                    "shot_id": shot_id,
                    "model": model_used,
                })

        # Generate actor profile updates
        actor_updates_count = self._process_actor_profiles(
            by_character, session_id
        )

        # Generate prompt template risks
        template_risks_count = self._process_template_risks(
            by_template, session_id
        )

        # Generate model routing updates
        model_routes_count = self._process_model_routing(
            by_model_route, session_id
        )

        return {
            "actor_profile_updates": actor_updates_count,
            "prompt_template_risks": template_risks_count,
            "model_routing_updates": model_routes_count,
        }

    def _process_actor_profiles(
        self, by_character: Dict[str, List[Dict]], session_id: str
    ) -> int:
        """Generate actor profile updates from character performance."""
        updates_generated = 0
        for character_name, entries in by_character.items():
            # Group by condition
            by_condition = defaultdict(lambda: {"pass": 0, "warn": 0, "reject": 0})
            shot_ids_per_condition = defaultdict(list)

            for entry in entries:
                condition = entry["condition"]
                verdict = entry["verdict"].upper()
                by_condition[condition][verdict.lower()] += 1
                shot_ids_per_condition[condition].append(entry["shot_id"])

            # Apply confidence adjustments
            for condition, counts in by_condition.items():
                total = sum(counts.values())
                if total < 2:
                    continue

                warn_rate = counts.get("warn", 0) / total
                reject_rate = counts.get("reject", 0) / total
                pass_rate = counts.get("pass", 0) / total

                confidence_delta = 0.0
                if warn_rate >= 0.66 or reject_rate >= 0.33:
                    # Character struggles under this condition
                    confidence_delta = -0.15
                elif pass_rate >= 0.8:
                    # Character excels under this condition
                    confidence_delta = +0.10

                if confidence_delta != 0.0:
                    update = ActorProfileUpdate(
                        character_name=character_name,
                        condition=condition,
                        confidence_adjustment=confidence_delta,
                        source_session=session_id,
                        source_shots=shot_ids_per_condition[condition],
                        timestamp=datetime.now().isoformat(),
                    )
                    self.actor_profiles[
                        f"{character_name}_{condition}"
                    ] = update
                    updates_generated += 1

        return updates_generated

    def _process_template_risks(
        self, by_template: Dict[str, List[Dict]], session_id: str
    ) -> int:
        """Generate prompt template risk scores from failure patterns."""
        updates_generated = 0
        for template_hash, entries in by_template.items():
            failure_types = []
            for entry in entries:
                deviation = entry.get("deviation", "generic")
                if deviation and deviation not in failure_types:
                    failure_types.append(deviation)

            reject_count = sum(
                1 for e in entries if e.get("verdict") == "REJECT"
            )
            warn_count = sum(1 for e in entries if e.get("verdict") == "WARN")

            # Risk score: 0.0 = safe, 1.0 = very dangerous
            risk_score = min(0.95, (reject_count * 0.5 + warn_count * 0.25) / len(entries))

            if reject_count >= 2 or risk_score > 0.4:
                update = PromptTemplateRisk(
                    template_hash=template_hash,
                    template_snippet=entries[0].get("gate_id", "")[:100],
                    risk_score=risk_score,
                    failure_count=len(entries),
                    failure_types=failure_types,
                    last_failure_session=session_id,
                    timestamp=datetime.now().isoformat(),
                )
                self.prompt_risks[template_hash] = update
                updates_generated += 1

        return updates_generated

    def _process_model_routing(
        self, by_model_route: Dict[str, List[Dict]], session_id: str
    ) -> int:
        """Generate model routing preferences from performance comparison."""
        updates_generated = 0
        by_route_key = defaultdict(lambda: defaultdict(list))

        for route_key, entries in by_model_route.items():
            parts = route_key.rsplit("_", 1)
            if len(parts) != 2:
                continue
            base_key = parts[0]
            model = parts[1]
            by_route_key[base_key][model].extend(entries)

        # Compare models for same route
        for base_key, model_entries in by_route_key.items():
            if len(model_entries) < 2:
                continue

            model_scores = {}
            for model, entries in model_entries.items():
                pass_count = sum(
                    1 for e in entries if e.get("verdict") == "PASS"
                )
                pass_rate = pass_count / len(entries) if entries else 0
                model_scores[model] = pass_rate

            best_model = max(model_scores, key=model_scores.get)
            best_rate = model_scores[best_model]

            # Check if best model is significantly better
            other_rates = [
                r for m, r in model_scores.items() if m != best_model
            ]
            if other_rates:
                avg_other = sum(other_rates) / len(other_rates)
                delta = best_rate - avg_other

                if delta > 0.15:  # Significant improvement
                    parts = base_key.split("_")
                    if len(parts) >= 3:
                        update = ModelRoutingUpdate(
                            shot_class=parts[0],
                            lighting_condition=parts[1],
                            emotional_register=parts[2],
                            preferred_model=best_model,
                            performance_delta=delta,
                            confirmation_count=1,
                            source_sessions=[session_id],
                            timestamp=datetime.now().isoformat(),
                        )
                        self.model_routes[base_key] = update
                        updates_generated += 1

        return updates_generated

    def get_actor_confidence(
        self, character_name: str, condition: str
    ) -> Optional[float]:
        """Retrieve confidence adjustment for character under condition."""
        key = f"{character_name}_{condition}"
        update = self.actor_profiles.get(key)
        return update.confidence_adjustment if update else None

    def get_template_risk(self, template_hash: str) -> float:
        """Retrieve risk score for a prompt template."""
        risk = self.prompt_risks.get(template_hash)
        return risk.risk_score if risk else 0.0

    def get_preferred_model(
        self, shot_class: str, lighting: str, emotion: str
    ) -> Optional[str]:
        """Retrieve preferred model for combination of conditions."""
        key = f"{shot_class}_{lighting}_{emotion}"
        route = self.model_routes.get(key)
        return route.preferred_model if route else None


# ============================================================================
# PATTERN CONFIRMATION SYSTEM — Threshold-Based Promotion
# ============================================================================

class PatternConfirmationSystem:
    """
    Tracks learnable patterns and promotes them from provisional to stable
    once they reach PATTERN_CONFIRMATION_THRESHOLD confirmations.
    """

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        self.patterns_file = os.path.join(report_dir, "learned_patterns.json")
        self.patterns: Dict[str, LearnedPattern] = self._load_patterns()

    def _load_patterns(self) -> Dict[str, LearnedPattern]:
        """Load patterns from disk."""
        if not os.path.exists(self.patterns_file):
            return {}

        try:
            with open(self.patterns_file, "r") as f:
                data = json.load(f)
            return {
                pattern_id: LearnedPattern.from_dict(p)
                for pattern_id, p in data.items()
            }
        except Exception:
            return {}

    def _save_patterns(self) -> None:
        """Save patterns to disk atomically."""
        os.makedirs(self.report_dir, exist_ok=True)
        data = {pid: p.to_dict() for pid, p in self.patterns.items()}

        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.report_dir, delete=False, suffix=".json"
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            os.replace(tmp_path, self.patterns_file)
        except Exception as e:
            print(f"WARNING: Failed to save patterns: {e}")

    def record_outcome(
        self,
        pattern_type: str,
        condition_key: str,
        outcome: str,
        session_id: str,
    ) -> LearnedPattern:
        """
        Record an outcome for a pattern, promoting to stable if threshold met.

        Args:
            pattern_type: actor_profile / prompt_template / model_routing
            condition_key: comparable context identifier
            outcome: what was learned
            session_id: session that confirmed it

        Returns:
            LearnedPattern (updated or newly created)
        """
        pattern_id = f"{pattern_type}_{condition_key}_{outcome}"

        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            pattern.confirmation_count += 1
            if session_id not in pattern.confirmation_sessions:
                pattern.confirmation_sessions.append(session_id)
            pattern.last_confirmed = datetime.now().isoformat()

            # Check for promotion to stable
            if (
                pattern.status == "provisional"
                and pattern.confirmation_count >= PATTERN_CONFIRMATION_THRESHOLD
            ):
                pattern.status = "stable"
                pattern.confidence_score = CONFIDENCE_STABLE
        else:
            pattern = LearnedPattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                condition_key=condition_key,
                outcome=outcome,
                confirmation_count=1,
                confirmation_sessions=[session_id],
                confidence_score=CONFIDENCE_PROVISIONAL,
                status="provisional",
                first_observed=datetime.now().isoformat(),
                last_confirmed=datetime.now().isoformat(),
            )
            self.patterns[pattern_id] = pattern

        self._save_patterns()
        return pattern

    def get_stable_patterns(self, pattern_type: Optional[str] = None) -> List[LearnedPattern]:
        """Get all stable patterns, optionally filtered by type."""
        patterns = [
            p
            for p in self.patterns.values()
            if p.status == "stable"
            and (pattern_type is None or p.pattern_type == pattern_type)
        ]
        return patterns

    def get_provisional_patterns(self, pattern_type: Optional[str] = None) -> List[LearnedPattern]:
        """Get all provisional patterns, optionally filtered by type."""
        patterns = [
            p
            for p in self.patterns.values()
            if p.status == "provisional"
            and (pattern_type is None or p.pattern_type == pattern_type)
        ]
        return patterns

    def is_stable(
        self, pattern_type: str, condition_key: str, outcome: str
    ) -> bool:
        """Check if a pattern has reached stable status."""
        pattern_id = f"{pattern_type}_{condition_key}_{outcome}"
        pattern = self.patterns.get(pattern_id)
        return pattern is not None and pattern.status == "stable"

    def get_confidence(
        self, pattern_type: str, condition_key: str, outcome: str
    ) -> float:
        """Get confidence score for a pattern (0.0 if unknown)."""
        pattern_id = f"{pattern_type}_{condition_key}_{outcome}"
        pattern = self.patterns.get(pattern_id)
        return pattern.confidence_score if pattern else 0.0


# ============================================================================
# BELIEF DECAY SYSTEM — Time-Based Confidence Decay
# ============================================================================

class BeliefDecaySystem:
    """
    Runs periodic housekeeping to demote stale patterns and delete forgotten ones.
    Prevents outdated learnings from incorrectly guiding decisions.
    """

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        self.patterns_file = os.path.join(report_dir, "learned_patterns.json")

    def run_decay_pass(self, current_session_number: int) -> DecayReport:
        """
        Run a full decay pass across all patterns.

        Args:
            current_session_number: current session number for age calculation

        Returns:
            DecayReport with results
        """
        if not os.path.exists(self.patterns_file):
            return DecayReport(
                patterns_reviewed=0,
                patterns_demoted=0,
                patterns_deleted=0,
                patterns_flagged=0,
                session_number=current_session_number,
                timestamp=datetime.now().isoformat(),
            )

        # Load patterns
        try:
            with open(self.patterns_file, "r") as f:
                data = json.load(f)
            patterns = {
                pid: LearnedPattern.from_dict(p) for pid, p in data.items()
            }
        except Exception as e:
            print(f"WARNING: Failed to load patterns for decay: {e}")
            return DecayReport(
                patterns_reviewed=0,
                patterns_demoted=0,
                patterns_deleted=0,
                patterns_flagged=0,
                session_number=current_session_number,
                timestamp=datetime.now().isoformat(),
            )

        reviewed = 0
        demoted = 0
        deleted = 0
        flagged = 0
        patterns_to_delete = []

        # Extract session number from last confirmed timestamp
        for pattern_id, pattern in patterns.items():
            reviewed += 1
            last_confirmed = pattern.last_confirmed

            # Simplified: if last_confirmed is a string ISO timestamp,
            # we estimate sessions_since by checking how recent it is
            # In production, track explicit session numbers
            sessions_since = self._estimate_sessions_since(last_confirmed, current_session_number)

            if pattern.status == "stable":
                # Stable patterns decay if stale
                if sessions_since >= BELIEF_DECAY_STALE:
                    pattern.status = "provisional"
                    pattern.confidence_score = CONFIDENCE_DECAYED
                    demoted += 1
                elif sessions_since >= 7:
                    flagged += 1

            elif pattern.status == "provisional":
                # Provisional patterns are deleted if old enough
                if sessions_since >= BELIEF_DECAY_DELETE:
                    patterns_to_delete.append(pattern_id)
                    deleted += 1
                elif sessions_since >= 15:
                    flagged += 1

        # Remove deleted patterns
        for pattern_id in patterns_to_delete:
            del patterns[pattern_id]

        # Save updated patterns
        self._save_patterns(patterns)

        return DecayReport(
            patterns_reviewed=reviewed,
            patterns_demoted=demoted,
            patterns_deleted=deleted,
            patterns_flagged=flagged,
            session_number=current_session_number,
            timestamp=datetime.now().isoformat(),
        )

    def _estimate_sessions_since(self, iso_timestamp: str, current_session_number: int) -> int:
        """
        Estimate sessions since timestamp.
        Simplified: assume sessions happen regularly (~1 per day).
        In production, track explicit session numbers in patterns.
        """
        try:
            last_dt = datetime.fromisoformat(iso_timestamp)
            now = datetime.now()
            days_since = (now - last_dt).days
            # Rough estimate: 1 session per day
            return max(0, days_since)
        except Exception:
            return 0

    def _save_patterns(self, patterns: Dict[str, LearnedPattern]) -> None:
        """Save patterns to disk atomically."""
        os.makedirs(self.report_dir, exist_ok=True)
        data = {pid: p.to_dict() for pid, p in patterns.items()}

        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.report_dir, delete=False, suffix=".json"
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            os.replace(tmp_path, self.patterns_file)
        except Exception as e:
            print(f"WARNING: Failed to save decayed patterns: {e}")


# ============================================================================
# TOP-LEVEL RUNNERS
# ============================================================================

def run_phase4_session_close(
    session_id: str, ledger_entries: List[Dict], session_number: int
) -> Dict:
    """
    End-of-session learning activation.

    Args:
        session_id: session identifier
        ledger_entries: list of ledger entries from RunLedger
        session_number: current session number

    Returns:
        dict with learning_summary and outcomes
    """
    # Step 1: Activate ledger learning
    activator = LedgerActivationSystem()
    learning_summary = activator.activate_session_learning(session_id, ledger_entries)

    # Step 2: Record outcomes for pattern confirmation
    confirmer = PatternConfirmationSystem()

    # Extract patterns from learning summary and record them
    pattern_count = 0
    if learning_summary.get("actor_profile_updates", 0) > 0:
        for char_cond, update in activator.actor_profiles.items():
            confirmer.record_outcome(
                pattern_type="actor_profile",
                condition_key=update.condition,
                outcome=f"confidence_delta_{update.confidence_adjustment:.2f}",
                session_id=session_id,
            )
            pattern_count += 1

    if learning_summary.get("prompt_template_risks", 0) > 0:
        for template_hash, risk in activator.prompt_risks.items():
            confirmer.record_outcome(
                pattern_type="prompt_template",
                condition_key=template_hash,
                outcome=f"risk_{risk.risk_score:.2f}",
                session_id=session_id,
            )
            pattern_count += 1

    if learning_summary.get("model_routing_updates", 0) > 0:
        for route_key, route in activator.model_routes.items():
            confirmer.record_outcome(
                pattern_type="model_routing",
                condition_key=route_key,
                outcome=f"prefer_{route.preferred_model}",
                session_id=session_id,
            )
            pattern_count += 1

    return {
        "learning_summary": learning_summary,
        "patterns_recorded": pattern_count,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }


def run_phase4_session_open(current_session_number: int) -> Dict:
    """
    Start-of-session housekeeping — run belief decay and report.

    Args:
        current_session_number: current session number

    Returns:
        dict with decay_report and session info
    """
    decay = BeliefDecaySystem()
    report = decay.run_decay_pass(current_session_number)

    return {
        "decay_report": {
            "reviewed": report.patterns_reviewed,
            "demoted": report.patterns_demoted,
            "deleted": report.patterns_deleted,
            "flagged": report.patterns_flagged,
        },
        "session_number": current_session_number,
        "timestamp": report.timestamp,
    }


if __name__ == "__main__":
    # Quick test
    print("DOCTRINE PHASE 4 — Memory, Learning, and Feedback System")
    print("Systems: LedgerActivationSystem, PatternConfirmationSystem, BeliefDecaySystem")
