"""
ATLAS Doctrine Tracker — V1.0
==============================
Tracks which doctrine rules fire, correlates them to output quality,
and proposes evolution suggestions based on production data.

This is Layer 3 of the three intelligence layers:
  Layer 1: Production Intelligence Graph  (production_intelligence.py)
  Layer 2: Director Brain                 (director_brain.py)
  Layer 3: Doctrine Evolution             (THIS FILE)

WHAT IT TRACKS:
  Per rule, per session:
    - fired_count: how many times this rule was checked
    - passed_count: how many times it passed
    - blocked_count: how many times it hard-blocked generation
    - warned_count: how many times it warned (non-blocking)
    - avg_R_when_passed: avg reward score when rule passed
    - avg_R_when_failed: avg reward score when rule failed
    - avg_I_when_passed: avg identity score when rule passed
    - fail_modes: list of specific failure reasons observed

  Cross-session analytics:
    - Which rules have degrading pass rates over time?
    - Which rules correlate most strongly with high R scores?
    - Which rules are never failing (may be too loose or never firing)?
    - Which rule combinations produce the best quality?

OUTPUTS:
  - pipeline_outputs/{project}/doctrine_rule_analytics.jsonl (per-session)
  - ~/.atlas/doctrine_evolution.db (SQLite cross-session store)
  - Printed suggestions at end of session via get_evolution_suggestions()

USAGE:
    from tools.doctrine_tracker import DoctrineTracker

    tracker = DoctrineTracker(project_dir=Path("pipeline_outputs/victorian_shadows_ep1"))

    # Log a rule firing (call this from doctrine_engine or gate wrappers)
    tracker.log_rule_firing(
        rule_id="IDENTITY_CONSISTENCY",
        shot_id="001_M02",
        result="PASS",         # PASS / WARN / BLOCK
        reason="",
        scores={"R": 0.82, "I": 0.90}
    )

    # After scene, correlate to reward ledger
    tracker.correlate_to_reward_ledger(reward_ledger)

    # At end of session, get evolution suggestions
    suggestions = tracker.get_evolution_suggestions()
    for s in suggestions:
        print(f"  [{s['priority']}] {s['rule_id']}: {s['suggestion']}")

INTEGRATION:
    This tracker is designed to be called from:
    1. doctrine_engine.py: wrap RunLedger.write() to also call tracker.log_rule_firing()
    2. atlas_universal_runner.py: at end of each scene after reward ledger is computed
    3. session_enforcer.py: at session end to emit evolution report
"""

import json
import sqlite3
import logging
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── DB path ─────────────────────────────────────────────────────────────
_DOCTRINE_DB_PATH = Path.home() / ".atlas" / "doctrine_evolution.db"

# ── Known doctrine rule IDs (from CLAUDE.md sections) ───────────────────
# These are the canonical rule identifiers used across the system.
KNOWN_RULE_IDS = {
    # Film Engine rules (T2-FE-*)
    "NEGATIVE_VOCAB_SEPARATION",       # T2-FE-1
    "CAMERA_BRANDS_STRIPPED",          # T2-FE-2
    "DIALOGUE_MARKERS_INJECTED",       # T2-FE-3
    "CPC_DECONTAMINATION",             # T2-FE-4
    "FILM_STOCK_STRIPPED",             # T2-FE-5
    "ANTI_MORPH_SPLIT",                # T2-FE-22
    "SCENE_VISUAL_DNA_LOCKED",         # T2-FE-23
    "ROOM_DNA_PRESENT",                # subcheck of above
    "LIGHTING_RIG_LOCKED",             # T2-FE-25
    "IDENTITY_BLOCK_PRESENT",          # T2-FE-27
    "LOCATION_NAMES_STRIPPED",         # T2-FE-28
    "SOCIAL_BLOCKING_PRESENT",         # T2-FE-29
    "EMPTY_SHOT_NEG_CONSTRAINT",       # T2-FE-30
    "SOLO_SCENE_NO_PARTNER_DIR",       # T2-FE-35
    "DIALOGUE_DURATION_PROTECTED",     # T2-FE-16 / T2-OR-12
    # Truth layer rules (T2-TL-*)
    "SCENE_CONTRACT_PRESENT",          # T2-TL-2
    "BEAT_TRUTH_FIELDS_PRESENT",       # T2-TL-3
    "TRUTH_FIELDS_IMMUTABLE",          # T2-TL-4
    # Chain policy rules (T2-CP-*)
    "OTS_PAIR_ALTERNATES",             # T2-CP-9
    "BROLL_NO_CHAR_CHAIN",             # T2-CP-4
    # Shot authority rules (T2-SA-*)
    "FAL_PARAMS_CORRECT",              # T2-SA-1
    "RESOLUTION_CORRECT",              # T2-SA-2
    # Continuity rules (T2-CM-*)
    "CONTINUITY_SUPPLEMENTARY",        # T2-CM-1
    # Orchestrator rules (T2-OR-*)
    "LOCATION_ROOM_LOCKED",            # T2-OR-13
    "FACE_SHOTS_KEEP_ROOM",            # T2-OR-14
    # Vision judge outcomes (result categories)
    "IDENTITY_CONSISTENCY",            # vision_judge I-score gate
    "VIDEO_NOT_FROZEN",                # V-score >= 0.5
    "CHAIN_FRAME_PRESENT",             # C-score
    # Chain arc rules (V36.5)
    "ARC_POSITION_ASSIGNED",
    "ROOM_DNA_IN_REFRAME",             # V36.4 chain env drift fix
    "LOCATION_MASTER_IN_REFRAME",      # V36.4
    # Generation gate checks
    "CHAR_REFS_EXIST",
    "LOC_REFS_EXIST",
    "MODEL_LOCK_ENFORCED",
    "DIALOGUE_INTEGRITY",
}

# ── Evolution rule categories ───────────────────────────────────────────
_CATEGORY_MAP = {
    "NEGATIVE_VOCAB_SEPARATION":    "prompt_quality",
    "CAMERA_BRANDS_STRIPPED":       "prompt_quality",
    "DIALOGUE_MARKERS_INJECTED":    "dialogue",
    "CPC_DECONTAMINATION":          "prompt_quality",
    "ANTI_MORPH_SPLIT":             "video_quality",
    "SCENE_VISUAL_DNA_LOCKED":      "environment",
    "ROOM_DNA_PRESENT":             "environment",
    "LIGHTING_RIG_LOCKED":          "environment",
    "IDENTITY_BLOCK_PRESENT":       "identity",
    "IDENTITY_CONSISTENCY":         "identity",
    "SOCIAL_BLOCKING_PRESENT":      "blocking",
    "OTS_PAIR_ALTERNATES":          "blocking",
    "DIALOGUE_DURATION_PROTECTED":  "dialogue",
    "VIDEO_NOT_FROZEN":             "video_quality",
    "CHAIN_FRAME_PRESENT":          "continuity",
    "ARC_POSITION_ASSIGNED":        "arc",
    "ROOM_DNA_IN_REFRAME":          "environment",
    "LOCATION_MASTER_IN_REFRAME":   "environment",
}


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RuleFiring:
    """A single rule firing event."""
    rule_id: str
    shot_id: str
    session_ts: str
    project: str
    result: str            # PASS / WARN / BLOCK
    reason: str = ""
    I_score: float = 0.0
    R_score: float = 0.0
    arc_position: str = ""
    shot_type: str = ""


@dataclass
class RuleStats:
    """Aggregated statistics for a single doctrine rule."""
    rule_id: str
    category: str = ""
    fired_count: int = 0
    passed_count: int = 0
    warned_count: int = 0
    blocked_count: int = 0
    pass_rate: float = 0.0
    avg_R_when_passed: float = 0.0
    avg_R_when_failed: float = 0.0
    avg_I_when_passed: float = 0.0
    avg_I_when_failed: float = 0.0
    R_delta: float = 0.0          # avg_R_passed - avg_R_failed (impact metric)
    trend: str = "STABLE"          # IMPROVING / STABLE / DEGRADING
    sessions_seen: int = 0
    last_seen: str = ""
    fail_modes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvolutionSuggestion:
    """A suggested doctrine evolution based on production data."""
    rule_id: str
    priority: str          # HIGH / MEDIUM / LOW
    category: str
    suggestion: str        # Human-readable suggestion
    evidence: str          # Data backing the suggestion
    suggested_action: str  # "tighten" / "loosen" / "promote_to_blocking" / "investigate" / "retire"
    confidence: float = 0.5

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# DOCTRINE TRACKER
# ═══════════════════════════════════════════════════════════════════════════

class DoctrineTracker:
    """
    Tracks doctrine rule firings and correlates to output quality.
    Writes to SQLite cross-session store and per-project JSONL analytics.
    Non-blocking: all failures caught and logged.
    """

    def __init__(self, project_dir: Optional[Path] = None, project: str = ""):
        self._project_dir = Path(project_dir) if project_dir else None
        self._project = project
        self._session_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._firings: List[RuleFiring] = []                 # in-memory this session
        self._reward_map: Dict[str, Dict] = {}               # shot_id → reward entry
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── Initialization ──────────────────────────────────────────────────────

    def _init_db(self):
        try:
            _DOCTRINE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(_DOCTRINE_DB_PATH), check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS rule_firings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT NOT NULL,
                    session_ts  TEXT NOT NULL,
                    project     TEXT NOT NULL DEFAULT '',
                    rule_id     TEXT NOT NULL,
                    shot_id     TEXT NOT NULL DEFAULT '',
                    result      TEXT NOT NULL,
                    reason      TEXT NOT NULL DEFAULT '',
                    I_score     REAL NOT NULL DEFAULT 0,
                    R_score     REAL NOT NULL DEFAULT 0,
                    arc_position TEXT NOT NULL DEFAULT '',
                    shot_type   TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS rule_session_stats (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_ts      TEXT NOT NULL,
                    project         TEXT NOT NULL DEFAULT '',
                    rule_id         TEXT NOT NULL,
                    category        TEXT NOT NULL DEFAULT '',
                    fired_count     INTEGER NOT NULL DEFAULT 0,
                    passed_count    INTEGER NOT NULL DEFAULT 0,
                    warned_count    INTEGER NOT NULL DEFAULT 0,
                    blocked_count   INTEGER NOT NULL DEFAULT 0,
                    avg_R_passed    REAL NOT NULL DEFAULT 0,
                    avg_R_failed    REAL NOT NULL DEFAULT 0,
                    avg_I_passed    REAL NOT NULL DEFAULT 0,
                    avg_I_failed    REAL NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_rf_rule ON rule_firings(rule_id, result);
                CREATE INDEX IF NOT EXISTS idx_rf_proj ON rule_firings(project, session_ts);
                CREATE INDEX IF NOT EXISTS idx_rss_rule ON rule_session_stats(rule_id);
            """)
            self._db.commit()
        except Exception as e:
            logger.warning(f"[DT] DB init failed: {e}")
            self._db = None

    # ── Public API ──────────────────────────────────────────────────────────

    def log_rule_firing(
        self,
        rule_id: str,
        shot_id: str = "",
        result: str = "PASS",    # PASS / WARN / BLOCK
        reason: str = "",
        scores: Optional[Dict] = None,
        arc_position: str = "",
        shot_type: str = "",
    ):
        """
        Log a single doctrine rule firing event.
        Call this from doctrine_engine, gate handlers, or directly from runner.
        Non-blocking.
        """
        try:
            scores = scores or {}
            firing = RuleFiring(
                rule_id=rule_id,
                shot_id=shot_id,
                session_ts=self._session_ts,
                project=self._project,
                result=result,
                reason=reason,
                I_score=scores.get("I", 0.0),
                R_score=scores.get("R", 0.0),
                arc_position=arc_position,
                shot_type=shot_type,
            )
            self._firings.append(firing)

            if self._db:
                self._db.execute("""
                    INSERT INTO rule_firings
                    (ts, session_ts, project, rule_id, shot_id, result, reason,
                     I_score, R_score, arc_position, shot_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    datetime.utcnow().isoformat(),
                    self._session_ts, self._project,
                    rule_id, shot_id, result, reason,
                    firing.I_score, firing.R_score,
                    arc_position, shot_type,
                ))
                self._db.commit()
        except Exception as e:
            logger.warning(f"[DT] log_rule_firing failed: {e}")

    def log_gate_result(self, gate_result: Any, shot_id: str = "",
                         scores: Optional[Dict] = None):
        """
        Log from a doctrine_engine GateResult or LedgerEntry.
        Convenience wrapper that infers rule_id from gate/reason_code.
        """
        try:
            # Handle GateResult (dataclass) or LedgerEntry
            if hasattr(gate_result, "reason_code") and gate_result.reason_code:
                rule_id = gate_result.reason_code
            elif hasattr(gate_result, "gate") and gate_result.gate:
                rule_id = gate_result.gate.upper().replace(" ", "_")
            elif hasattr(gate_result, "deviation_type") and gate_result.deviation_type:
                rule_id = gate_result.deviation_type.upper()
            else:
                rule_id = "UNKNOWN_GATE"

            verdict = str(getattr(gate_result, "gate_result", "") or
                          getattr(gate_result, "verdict", "") or
                          getattr(gate_result, "value", "PASS"))

            result_map = {"PASS": "PASS", "WARN": "WARN", "REJECT": "BLOCK",
                          "BLOCK": "BLOCK", "FAIL": "BLOCK"}
            result = result_map.get(verdict.upper(), "PASS")

            reason = str(getattr(gate_result, "reason", "") or
                         getattr(gate_result, "reason_code", ""))

            self.log_rule_firing(rule_id=rule_id, shot_id=shot_id,
                                  result=result, reason=reason, scores=scores)
        except Exception as e:
            logger.warning(f"[DT] log_gate_result failed: {e}")

    def correlate_to_reward_ledger(self, reward_ledger: List[Dict]):
        """
        After a scene's reward ledger is computed, correlate rule firings
        to final quality scores. Updates in-memory firing records.
        Non-blocking.
        """
        try:
            self._reward_map = {e["shot_id"]: e for e in reward_ledger}
            # Update R_score on recent firings that have matching shot_id
            for f in self._firings:
                if f.shot_id in self._reward_map:
                    entry = self._reward_map[f.shot_id]
                    f.R_score = entry.get("R", f.R_score)
                    f.I_score = entry.get("I", f.I_score)
                    # Update DB row too
                    if self._db:
                        try:
                            self._db.execute("""
                                UPDATE rule_firings SET R_score=?, I_score=?
                                WHERE session_ts=? AND shot_id=? AND rule_id=?
                            """, (f.R_score, f.I_score, f.session_ts, f.shot_id, f.rule_id))
                        except Exception:
                            pass
            if self._db:
                self._db.commit()
        except Exception as e:
            logger.warning(f"[DT] correlate_to_reward_ledger failed: {e}")

    def get_session_stats(self) -> Dict[str, RuleStats]:
        """
        Compute per-rule statistics for the current session.
        Returns dict of rule_id → RuleStats.
        """
        stats: Dict[str, RuleStats] = {}
        try:
            # Group firings by rule_id
            by_rule: Dict[str, List[RuleFiring]] = defaultdict(list)
            for f in self._firings:
                by_rule[f.rule_id].append(f)

            for rule_id, firings in by_rule.items():
                passed  = [f for f in firings if f.result == "PASS"]
                warned  = [f for f in firings if f.result == "WARN"]
                blocked = [f for f in firings if f.result == "BLOCK"]
                failed  = warned + blocked

                avg_R_pass = sum(f.R_score for f in passed) / max(len(passed), 1)
                avg_R_fail = sum(f.R_score for f in failed) / max(len(failed), 1)
                avg_I_pass = sum(f.I_score for f in passed) / max(len(passed), 1)
                avg_I_fail = sum(f.I_score for f in failed) / max(len(failed), 1)

                fail_modes = list({f.reason for f in failed if f.reason})[:5]

                stats[rule_id] = RuleStats(
                    rule_id=rule_id,
                    category=_CATEGORY_MAP.get(rule_id, "general"),
                    fired_count=len(firings),
                    passed_count=len(passed),
                    warned_count=len(warned),
                    blocked_count=len(blocked),
                    pass_rate=round(len(passed) / max(len(firings), 1), 3),
                    avg_R_when_passed=round(avg_R_pass, 3),
                    avg_R_when_failed=round(avg_R_fail, 3),
                    avg_I_when_passed=round(avg_I_pass, 3),
                    avg_I_when_failed=round(avg_I_fail, 3),
                    R_delta=round(avg_R_pass - avg_R_fail, 3),
                    last_seen=datetime.utcnow().isoformat(),
                    fail_modes=fail_modes,
                )
        except Exception as e:
            logger.warning(f"[DT] get_session_stats failed: {e}")
        return stats

    def get_evolution_suggestions(self) -> List[EvolutionSuggestion]:
        """
        Analyze session stats and cross-session history.
        Return prioritized evolution suggestions for doctrine rules.
        """
        suggestions: List[EvolutionSuggestion] = []
        try:
            session_stats = self.get_session_stats()
            cross_stats   = self._get_cross_session_stats()

            for rule_id, stats in session_stats.items():
                s = self._analyze_rule(rule_id, stats,
                                        cross_stats.get(rule_id, {}))
                if s:
                    suggestions.append(s)

            # Check for rules from KNOWN_RULE_IDS that never fired (potential gaps)
            for rule_id in KNOWN_RULE_IDS:
                if rule_id not in session_stats:
                    suggestions.append(EvolutionSuggestion(
                        rule_id=rule_id,
                        priority="LOW",
                        category=_CATEGORY_MAP.get(rule_id, "general"),
                        suggestion=f"Rule {rule_id} never fired this session. May not be wired.",
                        evidence="fired_count=0",
                        suggested_action="investigate",
                        confidence=0.3,
                    ))

            # Sort by priority
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            suggestions.sort(key=lambda s: (priority_order.get(s.priority, 3), -s.confidence))
        except Exception as e:
            logger.warning(f"[DT] get_evolution_suggestions failed: {e}")
        return suggestions

    def write_analytics_report(self) -> Optional[Path]:
        """
        Write session doctrine analytics to JSONL file in project dir.
        Returns path to report, or None if failed.
        """
        try:
            stats = self.get_session_stats()
            suggestions = self.get_evolution_suggestions()

            # Write per-project JSONL
            if self._project_dir:
                report_path = self._project_dir / "doctrine_rule_analytics.jsonl"
                with open(str(report_path), "a") as f:
                    record = {
                        "session_ts": self._session_ts,
                        "project": self._project,
                        "rule_stats": {k: v.to_dict() for k, v in stats.items()},
                        "evolution_suggestions": [s.to_dict() for s in suggestions[:10]],
                        "total_firings": len(self._firings),
                        "rules_tracked": len(stats),
                    }
                    f.write(json.dumps(record) + "\n")

                # Write human-readable summary
                summary_path = self._project_dir / "director_notes" / "doctrine_summary.json"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                with open(str(summary_path), "w") as f:
                    json.dump({
                        "session_ts": self._session_ts,
                        "rules_tracked": len(stats),
                        "total_firings": len(self._firings),
                        "top_impact_rules": self._get_top_impact_rules(stats),
                        "degrading_rules": self._get_degrading_rules(stats),
                        "never_failing_rules": self._get_never_failing_rules(stats),
                        "suggestions": [s.to_dict() for s in suggestions[:5]],
                    }, f, indent=2)

                # Write to cross-session DB
                self._write_session_stats_to_db(stats)

                print(f"  [DOCTRINE TRACKER] Analytics written: {len(stats)} rules, "
                      f"{len(self._firings)} firings, "
                      f"{sum(1 for s in suggestions if s.priority=='HIGH')} HIGH priority suggestions")
                return report_path
        except Exception as e:
            logger.warning(f"[DT] write_analytics_report failed: {e}")
        return None

    # ── Cross-Session Analytics ─────────────────────────────────────────────

    def _get_cross_session_stats(self) -> Dict[str, Dict]:
        """Query historical rule performance from DB."""
        result = {}
        if not self._db:
            return result
        try:
            rows = self._db.execute("""
                SELECT rule_id,
                       SUM(fired_count) as total_fired,
                       AVG(avg_R_passed) as hist_R_passed,
                       AVG(avg_R_failed) as hist_R_failed,
                       COUNT(DISTINCT session_ts) as sessions
                FROM rule_session_stats
                WHERE project = ? OR project = ''
                GROUP BY rule_id
            """, (self._project,)).fetchall()
            for row in rows:
                result[row["rule_id"]] = dict(row)
        except Exception as e:
            logger.warning(f"[DT] cross-session query failed: {e}")
        return result

    def _write_session_stats_to_db(self, stats: Dict[str, RuleStats]):
        if not self._db:
            return
        try:
            for rule_id, s in stats.items():
                self._db.execute("""
                    INSERT INTO rule_session_stats
                    (session_ts, project, rule_id, category, fired_count, passed_count,
                     warned_count, blocked_count, avg_R_passed, avg_R_failed,
                     avg_I_passed, avg_I_failed)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    self._session_ts, self._project,
                    rule_id, s.category,
                    s.fired_count, s.passed_count,
                    s.warned_count, s.blocked_count,
                    s.avg_R_when_passed, s.avg_R_when_failed,
                    s.avg_I_when_passed, s.avg_I_when_failed,
                ))
            self._db.commit()
        except Exception as e:
            logger.warning(f"[DT] _write_session_stats_to_db failed: {e}")

    # ── Analysis ───────────────────────────────────────────────────────────

    def _analyze_rule(
        self,
        rule_id: str,
        stats: RuleStats,
        cross: Dict,
    ) -> Optional[EvolutionSuggestion]:
        """Analyze a single rule and return an evolution suggestion if warranted."""

        category = _CATEGORY_MAP.get(rule_id, "general")

        # Rule with high R_delta (big quality impact when it fails) → promote to blocking
        if stats.R_delta >= 0.20 and stats.blocked_count == 0 and stats.warned_count > 0:
            return EvolutionSuggestion(
                rule_id=rule_id,
                priority="HIGH",
                category=category,
                suggestion=(f"Rule {rule_id} has R_delta={stats.R_delta:.2f} — shots fail worse "
                             f"when this rule fires WARN vs PASS. Promote to BLOCKING."),
                evidence=(f"Fired {stats.fired_count}x. "
                          f"avg_R_pass={stats.avg_R_when_passed:.2f} vs "
                          f"avg_R_fail={stats.avg_R_when_failed:.2f}. "
                          f"pass_rate={stats.pass_rate:.0%}"),
                suggested_action="promote_to_blocking",
                confidence=min(0.5 + stats.R_delta, 0.95),
            )

        # Rule with degrading pass rate and high fire count → investigate
        if stats.fired_count >= 5 and stats.pass_rate < 0.70:
            cross_pass_rate = (cross.get("total_fired", 0) and
                                cross.get("hist_R_passed", 0) > stats.avg_R_when_passed)
            return EvolutionSuggestion(
                rule_id=rule_id,
                priority="HIGH" if stats.pass_rate < 0.50 else "MEDIUM",
                category=category,
                suggestion=(f"Rule {rule_id} pass rate {stats.pass_rate:.0%} is below 70%. "
                             f"Failing {stats.warned_count + stats.blocked_count}/{stats.fired_count} shots. "
                             f"Investigate root cause or tighten upstream prevention."),
                evidence=(f"fail_modes={stats.fail_modes[:3]}, "
                          f"avg_R_fail={stats.avg_R_when_failed:.2f}"),
                suggested_action="investigate",
                confidence=0.75,
            )

        # Rule that never fails (always passes) with high fire count → may be too loose
        if stats.fired_count >= 8 and stats.pass_rate == 1.0:
            return EvolutionSuggestion(
                rule_id=rule_id,
                priority="LOW",
                category=category,
                suggestion=(f"Rule {rule_id} passes 100% of {stats.fired_count} checks. "
                             f"May be too loose or checking the wrong condition. Review threshold."),
                evidence=f"fired={stats.fired_count}, pass_rate=1.00",
                suggested_action="investigate",
                confidence=0.4,
            )

        # Rule with low R_delta but blocking frequently → may be too strict
        if stats.blocked_count >= 3 and stats.R_delta < 0.05 and stats.avg_R_when_passed < 0.75:
            return EvolutionSuggestion(
                rule_id=rule_id,
                priority="MEDIUM",
                category=category,
                suggestion=(f"Rule {rule_id} is blocking {stats.blocked_count} shots but R_delta={stats.R_delta:.2f} "
                             f"suggests marginal quality impact. Consider downgrading to WARN."),
                evidence=(f"blocked={stats.blocked_count}, avg_R_pass={stats.avg_R_when_passed:.2f}, "
                          f"R_delta={stats.R_delta:.2f}"),
                suggested_action="loosen",
                confidence=0.5,
            )

        return None

    def _get_top_impact_rules(self, stats: Dict[str, RuleStats]) -> List[Dict]:
        """Return rules with highest R_delta (most quality impact)."""
        sorted_rules = sorted(stats.values(), key=lambda s: s.R_delta, reverse=True)
        return [{"rule_id": s.rule_id, "R_delta": s.R_delta,
                 "category": s.category, "fired": s.fired_count}
                for s in sorted_rules[:5] if s.R_delta > 0.05]

    def _get_degrading_rules(self, stats: Dict[str, RuleStats]) -> List[Dict]:
        """Return rules with low and worsening pass rates."""
        return [{"rule_id": s.rule_id, "pass_rate": s.pass_rate,
                 "category": s.category, "fail_modes": s.fail_modes[:2]}
                for s in stats.values()
                if s.pass_rate < 0.70 and s.fired_count >= 3]

    def _get_never_failing_rules(self, stats: Dict[str, RuleStats]) -> List[str]:
        """Return rules that never failed (may be too loose or not properly wired)."""
        return [s.rule_id for s in stats.values()
                if s.pass_rate == 1.0 and s.fired_count >= 5]

    def close(self):
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL CONVENIENCE (drop-in integration without instantiation)
# ═══════════════════════════════════════════════════════════════════════════

_GLOBAL_TRACKER: Optional[DoctrineTracker] = None

def get_tracker(project_dir: Optional[Path] = None,
                project: str = "") -> DoctrineTracker:
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        _GLOBAL_TRACKER = DoctrineTracker(project_dir=project_dir, project=project)
    return _GLOBAL_TRACKER


def log_rule(rule_id: str, shot_id: str = "", result: str = "PASS",
             reason: str = "", scores: Optional[Dict] = None,
             arc_position: str = "", shot_type: str = ""):
    """Drop-in rule logging. Non-blocking."""
    try:
        get_tracker().log_rule_firing(rule_id=rule_id, shot_id=shot_id,
                                      result=result, reason=reason, scores=scores,
                                      arc_position=arc_position, shot_type=shot_type)
    except Exception:
        pass


def log_gate(gate_result: Any, shot_id: str = "", scores: Optional[Dict] = None):
    """Drop-in gate result logging. Non-blocking."""
    try:
        get_tracker().log_gate_result(gate_result, shot_id=shot_id, scores=scores)
    except Exception:
        pass


def finalize_session(reward_ledger: Optional[List[Dict]] = None,
                     project_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Called at end of session. Correlates to ledger, writes analytics.
    Returns path to analytics report.
    Non-blocking.
    """
    try:
        tracker = get_tracker(project_dir)
        if reward_ledger:
            tracker.correlate_to_reward_ledger(reward_ledger)
        return tracker.write_analytics_report()
    except Exception as e:
        logger.warning(f"[DT] finalize_session failed: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# RUNNER INTEGRATION HELPER
# Wraps the generation gate result dict (from atlas_universal_runner.py)
# and extracts rule firings automatically.
# ═══════════════════════════════════════════════════════════════════════════

def extract_firings_from_gate_result(gate_result: Dict, shot_id: str,
                                      scores: Optional[Dict] = None):
    """
    Extract rule firings from a generation gate result dict.
    gate_result format: {"passed": [...], "warned": [...], "blocked": [...], "total_checks": N}
    Non-blocking.
    """
    try:
        tracker = get_tracker()
        for rule_id in gate_result.get("passed", []):
            tracker.log_rule_firing(rule_id=str(rule_id), shot_id=shot_id,
                                     result="PASS", scores=scores)
        for rule_id in gate_result.get("warned", []):
            tracker.log_rule_firing(rule_id=str(rule_id), shot_id=shot_id,
                                     result="WARN", scores=scores)
        for rule_id in gate_result.get("blocked", []):
            tracker.log_rule_firing(rule_id=str(rule_id), shot_id=shot_id,
                                     result="BLOCK", scores=scores)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("Doctrine Evolution DB:", _DOCTRINE_DB_PATH)
    print("Exists:", _DOCTRINE_DB_PATH.exists())

    if len(sys.argv) > 1 and sys.argv[1] == "report":
        # Read existing analytics from a project
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        analytics_path = project_dir / "doctrine_rule_analytics.jsonl"
        if analytics_path.exists():
            lines = analytics_path.read_text().strip().split("\n")
            if lines:
                latest = json.loads(lines[-1])
                print(f"\nLatest session: {latest['session_ts']}")
                print(f"Rules tracked: {latest['rules_tracked']}")
                print(f"Total firings: {latest['total_firings']}")
                print("\nEvolution suggestions:")
                for s in latest.get("evolution_suggestions", []):
                    print(f"  [{s['priority']}] {s['rule_id']}: {s['suggestion'][:80]}")
        else:
            print(f"No analytics file at {analytics_path}")
    else:
        # Demo: simulate a session
        print("\nRunning demo simulation...")
        tracker = DoctrineTracker(project="demo_project")
        # Simulate firings
        for i in range(5):
            tracker.log_rule_firing("IDENTITY_BLOCK_PRESENT", f"001_M0{i+1}",
                                     "PASS" if i < 4 else "WARN",
                                     scores={"R": 0.82 if i < 4 else 0.45, "I": 0.9})
        for i in range(3):
            tracker.log_rule_firing("ROOM_DNA_PRESENT", f"001_M0{i+1}",
                                     "PASS", scores={"R": 0.82, "I": 0.88})
        tracker.log_rule_firing("VIDEO_NOT_FROZEN", "001_M03", "BLOCK",
                                 reason="V_score=0.1", scores={"R": 0.30, "V": 0.1})

        stats = tracker.get_session_stats()
        suggestions = tracker.get_evolution_suggestions()

        print("\n--- Session Stats ---")
        for rule_id, s in stats.items():
            print(f"  {rule_id}: fired={s.fired_count} pass_rate={s.pass_rate:.0%} R_delta={s.R_delta:.2f}")

        print("\n--- Evolution Suggestions ---")
        for s in suggestions:
            print(f"  [{s.priority}] {s.rule_id}: {s.suggestion[:80]}")
