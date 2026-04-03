"""
ATLAS Production Intelligence Graph — V1.0
==========================================
SQLite-backed queryable database that accumulates production intelligence
across ALL runs and ALL productions. NOT flat logs — structured, queryable data.

This is Layer 1 of the three intelligence layers:
  Layer 1: Production Intelligence Graph (THIS FILE)
  Layer 2: Director Brain        (director_brain.py)
  Layer 3: Doctrine Evolution    (doctrine_tracker.py)

WHAT IT STORES (per shot, persisted forever):
  - All reward scores (R, I, D, V, C, E)
  - Retry count and failure modes
  - Prompt config snapshot (nano_prompt hash + length)
  - Character IDs, room DNA, arc_position
  - Doctrine rules that fired
  - Scene metadata (project, episode, scene_id, shot_type)
  - Model used, generation timestamp

WHAT IT ENABLES (queries BEFORE new generation):
  - "What arc_position + scene_type combinations reliably score I >= 0.8?"
  - "Which room DNA configs have the best R score?"
  - "How many retries does a kitchen scene typically need?"
  - "What prompt length correlates to highest V_score?"
  - "Which character pairs have the worst identity drift?"

USAGE:
    from tools.production_intelligence import ProductionIntelligence, write_shot_outcome, query_similar_shots

    # Write outcome after every shot
    pi = ProductionIntelligence()
    pi.write_shot_outcome(project="victorian_shadows_ep1", scene_id="001", shot=shot_dict,
                          scores={"R":0.82,"I":0.90,"D":0.85,"V":0.50,"C":0.85,"E":1.0},
                          retries=0, verdict="PASS", model_used="kling_v3_pro",
                          doctrine_rules_fired=["IDENTITY_CONSISTENCY", "OTS_ENFORCER"])

    # Query before generating a new shot
    history = pi.query_similar_shots(arc_position="ESCALATE", shot_type="medium",
                                      scene_type="dialogue", limit=5)
    avg_retries = pi.get_avg_retries(arc_position="ESTABLISH", project="*")

Non-blocking: all writes are wrapped in try/except. Failures never halt generation.

DB Location:
  Series-level:  ~/.atlas/production_intelligence.db  (cross-project)
  Project-level: pipeline_outputs/{project}/production_intelligence.db  (project-local)
  Both are written simultaneously. Query checks series-level for cross-project intelligence.
"""

import sqlite3
import json
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── Schema version — bump when adding columns ──────────────────────────────
_SCHEMA_VERSION = 3
_SERIES_DB_PATH = Path.home() / ".atlas" / "production_intelligence.db"


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════════════

_SCHEMA_SQL = """
-- Shot outcomes: one row per generated shot
CREATE TABLE IF NOT EXISTS shot_outcomes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,                  -- ISO timestamp
    project           TEXT NOT NULL,
    episode           TEXT NOT NULL DEFAULT '',
    scene_id          TEXT NOT NULL,
    shot_id           TEXT NOT NULL,
    shot_type         TEXT NOT NULL DEFAULT '',       -- medium, close_up, ots, etc.
    arc_position      TEXT NOT NULL DEFAULT '',       -- ESTABLISH/ESCALATE/PIVOT/RESOLVE
    scene_type        TEXT NOT NULL DEFAULT '',       -- dialogue/action/establishing/solo
    characters_json   TEXT NOT NULL DEFAULT '[]',     -- JSON array of character names
    room_dna_hash     TEXT NOT NULL DEFAULT '',       -- SHA256 of room DNA text
    prompt_hash       TEXT NOT NULL DEFAULT '',       -- SHA256 of nano_prompt
    prompt_len        INTEGER NOT NULL DEFAULT 0,
    model_used        TEXT NOT NULL DEFAULT '',
    R                 REAL NOT NULL DEFAULT 0,
    I                 REAL NOT NULL DEFAULT 0,
    D                 REAL NOT NULL DEFAULT 0,
    V                 REAL NOT NULL DEFAULT 0,
    C                 REAL NOT NULL DEFAULT 0,
    E                 REAL NOT NULL DEFAULT 0,
    retries           INTEGER NOT NULL DEFAULT 0,
    verdict           TEXT NOT NULL DEFAULT '',       -- PASS/REVIEW/FAIL
    failure_modes_json TEXT NOT NULL DEFAULT '[]',   -- JSON array of failure strings
    doctrine_rules_json TEXT NOT NULL DEFAULT '[]',  -- JSON array of fired rule IDs
    beat_ref          TEXT NOT NULL DEFAULT '',
    run_id            TEXT NOT NULL DEFAULT ''        -- unique per run session
);

-- Scene outcomes: aggregated after each scene completes
CREATE TABLE IF NOT EXISTS scene_outcomes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    project           TEXT NOT NULL,
    scene_id          TEXT NOT NULL,
    shot_count        INTEGER NOT NULL DEFAULT 0,
    pass_count        INTEGER NOT NULL DEFAULT 0,
    fail_count        INTEGER NOT NULL DEFAULT 0,
    avg_R             REAL NOT NULL DEFAULT 0,
    avg_I             REAL NOT NULL DEFAULT 0,
    avg_retries       REAL NOT NULL DEFAULT 0,
    total_cost_usd    REAL NOT NULL DEFAULT 0,
    generation_mins   REAL NOT NULL DEFAULT 0,
    run_id            TEXT NOT NULL DEFAULT ''
);

-- Prompt configs: track which prompt patterns produced which quality
CREATE TABLE IF NOT EXISTS prompt_configs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    project           TEXT NOT NULL,
    shot_id           TEXT NOT NULL,
    arc_position      TEXT NOT NULL DEFAULT '',
    shot_type         TEXT NOT NULL DEFAULT '',
    prompt_hash       TEXT NOT NULL,
    prompt_len        INTEGER NOT NULL DEFAULT 0,
    has_room_dna      INTEGER NOT NULL DEFAULT 0,     -- bool
    has_lighting_rig  INTEGER NOT NULL DEFAULT 0,
    has_identity_block INTEGER NOT NULL DEFAULT 0,
    has_ots_direction  INTEGER NOT NULL DEFAULT 0,
    has_dialogue      INTEGER NOT NULL DEFAULT 0,
    I_score           REAL NOT NULL DEFAULT 0,
    R_score           REAL NOT NULL DEFAULT 0
);

-- Character drift log: track when identity fails
CREATE TABLE IF NOT EXISTS character_drift (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    project           TEXT NOT NULL,
    scene_id          TEXT NOT NULL,
    shot_id           TEXT NOT NULL,
    character_name    TEXT NOT NULL,
    I_score           REAL NOT NULL DEFAULT 0,
    drift_detected    INTEGER NOT NULL DEFAULT 0,     -- bool
    drift_severity    TEXT NOT NULL DEFAULT '',       -- mild/moderate/severe
    ref_used          TEXT NOT NULL DEFAULT ''        -- path to ref image used
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_shot_arc     ON shot_outcomes(arc_position, shot_type);
CREATE INDEX IF NOT EXISTS idx_shot_project ON shot_outcomes(project, scene_id);
CREATE INDEX IF NOT EXISTS idx_shot_verdict ON shot_outcomes(verdict);
CREATE INDEX IF NOT EXISTS idx_scene_project ON scene_outcomes(project);
CREATE INDEX IF NOT EXISTS idx_prompt_hash  ON prompt_configs(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_drift_char   ON character_drift(character_name, project);
"""


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION INTELLIGENCE CLASS
# ═══════════════════════════════════════════════════════════════════════════

class ProductionIntelligence:
    """
    Queryable production intelligence graph backed by SQLite.
    Writes to both series-level (~/.atlas/) and project-level DBs.
    All operations are non-blocking: exceptions are caught and logged.
    """

    def __init__(self, project_dir: Optional[Path] = None):
        self._project_dir = Path(project_dir) if project_dir else None
        self._series_db: Optional[sqlite3.Connection] = None
        self._project_db: Optional[sqlite3.Connection] = None
        self._run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._init_dbs()

    # ── Initialization ──────────────────────────────────────────────────────

    def _init_dbs(self):
        """Initialize series-level and (optionally) project-level DBs."""
        # Series-level: always
        try:
            _SERIES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._series_db = sqlite3.connect(str(_SERIES_DB_PATH), check_same_thread=False)
            self._series_db.row_factory = sqlite3.Row
            self._apply_schema(self._series_db)
        except Exception as e:
            logger.warning(f"[PI] Series DB init failed: {e}")
            self._series_db = None

        # Project-level: only if project_dir provided
        if self._project_dir:
            try:
                proj_db_path = self._project_dir / "production_intelligence.db"
                self._project_db = sqlite3.connect(str(proj_db_path), check_same_thread=False)
                self._project_db.row_factory = sqlite3.Row
                self._apply_schema(self._project_db)
            except Exception as e:
                logger.warning(f"[PI] Project DB init failed: {e}")
                self._project_db = None

    def _apply_schema(self, conn: sqlite3.Connection):
        """Create tables and indexes if they don't exist."""
        cur = conn.cursor()
        cur.executescript(_SCHEMA_SQL)
        cur.executescript(_INDEX_SQL)
        cur.execute("INSERT OR REPLACE INTO schema_info VALUES (?, ?)",
                    ("version", str(_SCHEMA_VERSION)))
        conn.commit()

    def _exec_both(self, sql: str, params: tuple):
        """Execute a write on both series and project DBs (non-blocking)."""
        for db, name in [(self._series_db, "series"), (self._project_db, "project")]:
            if db is None:
                continue
            try:
                db.execute(sql, params)
                db.commit()
            except Exception as e:
                logger.warning(f"[PI] Write to {name} DB failed: {e}")

    def _query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Query series DB first, fall back to project DB."""
        for db in [self._series_db, self._project_db]:
            if db is None:
                continue
            try:
                cur = db.execute(sql, params)
                return cur.fetchone()
            except Exception as e:
                logger.warning(f"[PI] Query failed: {e}")
        return None

    def _query_all(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Query series DB (cross-project intelligence)."""
        db = self._series_db or self._project_db
        if db is None:
            return []
        try:
            cur = db.execute(sql, params)
            return cur.fetchall()
        except Exception as e:
            logger.warning(f"[PI] Query all failed: {e}")
            return []

    # ── Write Operations ────────────────────────────────────────────────────

    def write_shot_outcome(
        self,
        project: str,
        scene_id: str,
        shot: Dict[str, Any],
        scores: Dict[str, float],
        retries: int = 0,
        verdict: str = "PASS",
        model_used: str = "kling_v3_pro",
        doctrine_rules_fired: Optional[List[str]] = None,
        failure_modes: Optional[List[str]] = None,
        episode: str = "",
    ):
        """
        Write a shot's outcome to the production intelligence graph.
        Called after every shot generation, non-blocking.
        """
        try:
            shot_id   = shot.get("shot_id", "")
            shot_type = shot.get("shot_type", shot.get("type", ""))
            arc_pos   = shot.get("_arc_position", "")
            beat_ref  = shot.get("_beat_ref", "")
            chars     = shot.get("characters") or []
            nano      = shot.get("nano_prompt", "") or ""
            room_dna  = shot.get("_room_dna", "") or ""

            # Infer scene type from shot content
            has_dialogue = bool(shot.get("dialogue_text", ""))
            char_count   = len(chars)
            if char_count == 0:
                scene_type = "establishing"
            elif char_count == 1:
                scene_type = "solo_dialogue" if has_dialogue else "solo_action"
            else:
                scene_type = "dialogue" if has_dialogue else "multi_char"

            room_hash   = hashlib.sha256(room_dna.encode()).hexdigest()[:16]
            prompt_hash = hashlib.sha256(nano.encode()).hexdigest()[:16]

            sql = """
                INSERT INTO shot_outcomes
                (ts, project, episode, scene_id, shot_id, shot_type, arc_position,
                 scene_type, characters_json, room_dna_hash, prompt_hash, prompt_len,
                 model_used, R, I, D, V, C, E, retries, verdict,
                 failure_modes_json, doctrine_rules_json, beat_ref, run_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
            params = (
                datetime.utcnow().isoformat(),
                project, episode, scene_id, shot_id, shot_type, arc_pos,
                scene_type,
                json.dumps(chars),
                room_hash, prompt_hash, len(nano),
                model_used,
                scores.get("R", 0), scores.get("I", 0), scores.get("D", 0),
                scores.get("V", 0), scores.get("C", 0), scores.get("E", 0),
                retries, verdict,
                json.dumps(failure_modes or []),
                json.dumps(doctrine_rules_fired or []),
                beat_ref, self._run_id,
            )
            self._exec_both(sql, params)

            # Also write prompt config row
            self._write_prompt_config(project, shot, scores, nano, arc_pos, shot_type)

            # Write character drift rows
            if chars:
                self._write_character_drift(project, scene_id, shot_id, chars,
                                             scores.get("I", 0))
        except Exception as e:
            logger.warning(f"[PI] write_shot_outcome failed for {shot.get('shot_id','?')}: {e}")

    def _write_prompt_config(self, project, shot, scores, nano, arc_pos, shot_type):
        sql = """
            INSERT INTO prompt_configs
            (ts, project, shot_id, arc_position, shot_type, prompt_hash, prompt_len,
             has_room_dna, has_lighting_rig, has_identity_block, has_ots_direction,
             has_dialogue, I_score, R_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        params = (
            datetime.utcnow().isoformat(),
            project,
            shot.get("shot_id", ""),
            arc_pos, shot_type,
            hashlib.sha256(nano.encode()).hexdigest()[:16],
            len(nano),
            int("[ROOM DNA:" in nano),
            int("[LIGHTING RIG:" in nano),
            int("[CHARACTER:" in nano),
            int("FRAME-LEFT" in nano or "FRAME-RIGHT" in nano),
            int(bool(shot.get("dialogue_text"))),
            scores.get("I", 0),
            scores.get("R", 0),
        )
        self._exec_both(sql, params)

    def _write_character_drift(self, project, scene_id, shot_id, chars, i_score):
        severity = "none"
        drift = False
        if i_score < 0.5:
            drift, severity = True, "severe"
        elif i_score < 0.65:
            drift, severity = True, "moderate"
        elif i_score < 0.75:
            drift, severity = True, "mild"

        for char in chars:
            sql = """
                INSERT INTO character_drift
                (ts, project, scene_id, shot_id, character_name, I_score,
                 drift_detected, drift_severity, ref_used)
                VALUES (?,?,?,?,?,?,?,?,?)
            """
            self._exec_both(sql, (
                datetime.utcnow().isoformat(),
                project, scene_id, shot_id, char,
                i_score, int(drift), severity, "",
            ))

    def write_scene_outcome(
        self,
        project: str,
        scene_id: str,
        reward_ledger: List[Dict],
        total_cost_usd: float = 0.0,
        generation_mins: float = 0.0,
    ):
        """Write aggregated scene outcome after all shots complete."""
        try:
            if not reward_ledger:
                return
            pass_count = sum(1 for e in reward_ledger if e.get("verdict") == "PASS")
            fail_count = sum(1 for e in reward_ledger if e.get("verdict") == "FAIL")
            avg_R = sum(e.get("R", 0) for e in reward_ledger) / len(reward_ledger)
            avg_I = sum(e.get("I", 0) for e in reward_ledger) / len(reward_ledger)
            avg_retries = sum(e.get("retries", 0) for e in reward_ledger) / len(reward_ledger)

            sql = """
                INSERT INTO scene_outcomes
                (ts, project, scene_id, shot_count, pass_count, fail_count,
                 avg_R, avg_I, avg_retries, total_cost_usd, generation_mins, run_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """
            self._exec_both(sql, (
                datetime.utcnow().isoformat(),
                project, scene_id, len(reward_ledger),
                pass_count, fail_count,
                round(avg_R, 4), round(avg_I, 4), round(avg_retries, 3),
                total_cost_usd, generation_mins, self._run_id,
            ))
        except Exception as e:
            logger.warning(f"[PI] write_scene_outcome failed: {e}")

    # ── Query Operations ────────────────────────────────────────────────────

    def query_similar_shots(
        self,
        arc_position: str = "",
        shot_type: str = "",
        scene_type: str = "",
        project: str = "",
        limit: int = 10,
    ) -> List[Dict]:
        """
        Find past shots with similar context. Used BEFORE generation to
        predict likely quality and retry count.

        Returns list of dicts with scores, retries, verdict.
        """
        conditions = []
        params = []
        if arc_position:
            conditions.append("arc_position = ?")
            params.append(arc_position)
        if shot_type:
            conditions.append("shot_type = ?")
            params.append(shot_type)
        if scene_type:
            conditions.append("scene_type = ?")
            params.append(scene_type)
        if project and project != "*":
            conditions.append("project = ?")
            params.append(project)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT shot_id, project, scene_id, arc_position, shot_type, scene_type,
                   R, I, D, V, C, E, retries, verdict, ts
            FROM shot_outcomes
            {where}
            ORDER BY ts DESC
            LIMIT ?
        """
        params.append(limit)
        rows = self._query_all(sql, tuple(params))
        return [dict(r) for r in rows]

    def get_avg_retries(self, arc_position: str = "", project: str = "*") -> float:
        """Average retry count for a given arc_position across all projects."""
        params: list = []
        conditions = []
        if arc_position:
            conditions.append("arc_position = ?")
            params.append(arc_position)
        if project and project != "*":
            conditions.append("project = ?")
            params.append(project)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        row = self._query_one(f"SELECT AVG(retries) as avg_r FROM shot_outcomes {where}", tuple(params))
        if row and row["avg_r"] is not None:
            return round(float(row["avg_r"]), 2)
        return 0.0

    def get_best_prompt_config(self, arc_position: str, shot_type: str) -> Dict:
        """
        Find the prompt configuration that correlates with highest I_score
        for this arc_position + shot_type combination.
        Returns dict of feature flags that worked best.
        """
        row = self._query_one("""
            SELECT has_room_dna, has_lighting_rig, has_identity_block,
                   has_ots_direction, has_dialogue, AVG(I_score) as avg_I,
                   COUNT(*) as cnt
            FROM prompt_configs
            WHERE arc_position = ? AND shot_type = ? AND I_score >= 0.75
            GROUP BY has_room_dna, has_lighting_rig, has_identity_block, has_ots_direction, has_dialogue
            ORDER BY avg_I DESC
            LIMIT 1
        """, (arc_position, shot_type))

        if row:
            return {
                "has_room_dna":       bool(row["has_room_dna"]),
                "has_lighting_rig":   bool(row["has_lighting_rig"]),
                "has_identity_block": bool(row["has_identity_block"]),
                "has_ots_direction":  bool(row["has_ots_direction"]),
                "has_dialogue":       bool(row["has_dialogue"]),
                "avg_I_score":        round(float(row["avg_I"]), 3),
                "sample_count":       int(row["cnt"]),
            }
        return {}

    def get_character_drift_rate(self, character_name: str, project: str = "*") -> Dict:
        """
        Return drift statistics for a character across productions.
        Use this before generation to know if a character needs extra identity reinforcement.
        """
        cond = "WHERE character_name = ?"
        params: list = [character_name]
        if project and project != "*":
            cond += " AND project = ?"
            params.append(project)

        row = self._query_one(f"""
            SELECT COUNT(*) as total,
                   SUM(drift_detected) as drift_count,
                   AVG(I_score) as avg_I
            FROM character_drift {cond}
        """, tuple(params))

        if row and row["total"]:
            total = int(row["total"])
            drift = int(row["drift_count"] or 0)
            return {
                "character": character_name,
                "total_shots": total,
                "drift_count": drift,
                "drift_rate": round(drift / total, 3),
                "avg_I_score": round(float(row["avg_I"] or 0), 3),
                "risk_level": "HIGH" if drift / total > 0.3 else "MEDIUM" if drift / total > 0.15 else "LOW",
            }
        return {"character": character_name, "total_shots": 0, "drift_rate": 0.0, "risk_level": "UNKNOWN"}

    def get_production_summary(self, project: str) -> Dict:
        """Full production intelligence summary for a project."""
        shots_row = self._query_one("""
            SELECT COUNT(*) as total, AVG(R) as avg_R, AVG(I) as avg_I,
                   AVG(retries) as avg_retries,
                   SUM(CASE WHEN verdict='PASS' THEN 1 ELSE 0 END) as passes,
                   SUM(CASE WHEN verdict='FAIL' THEN 1 ELSE 0 END) as fails
            FROM shot_outcomes WHERE project = ?
        """, (project,))

        arc_rows = self._query_all("""
            SELECT arc_position, COUNT(*) as cnt, AVG(R) as avg_R, AVG(I) as avg_I
            FROM shot_outcomes WHERE project = ?
            GROUP BY arc_position ORDER BY avg_R DESC
        """, (project,))

        drift_rows = self._query_all("""
            SELECT character_name, COUNT(*) as shots,
                   SUM(drift_detected) as drifts, AVG(I_score) as avg_I
            FROM character_drift WHERE project = ?
            GROUP BY character_name ORDER BY avg_I ASC
        """, (project,))

        return {
            "project": project,
            "total_shots":  int(shots_row["total"]) if shots_row else 0,
            "avg_R":        round(float(shots_row["avg_R"] or 0), 3) if shots_row else 0,
            "avg_I":        round(float(shots_row["avg_I"] or 0), 3) if shots_row else 0,
            "avg_retries":  round(float(shots_row["avg_retries"] or 0), 2) if shots_row else 0,
            "pass_rate":    round(int(shots_row["passes"] or 0) / max(int(shots_row["total"] or 1), 1), 3) if shots_row else 0,
            "fail_rate":    round(int(shots_row["fails"] or 0) / max(int(shots_row["total"] or 1), 1), 3) if shots_row else 0,
            "arc_breakdown": [dict(r) for r in arc_rows],
            "character_drift": [dict(r) for r in drift_rows],
        }

    def get_pre_generation_intel(self, shot: Dict, project: str) -> Dict:
        """
        One-call summary of intelligence relevant BEFORE generating this shot.
        Returns:
          - predicted_retries: likely number of retries needed
          - risk_level: LOW/MEDIUM/HIGH
          - best_prompt_config: feature flags that correlated with high I_score
          - character_drift_risks: characters with high drift rates
          - similar_shots_avg_R: average reward from similar past shots
        """
        arc_pos   = shot.get("_arc_position", "")
        shot_type = shot.get("shot_type", shot.get("type", ""))
        chars     = shot.get("characters") or []

        avg_retries    = self.get_avg_retries(arc_position=arc_pos)
        best_config    = self.get_best_prompt_config(arc_pos, shot_type)
        similar        = self.query_similar_shots(arc_position=arc_pos, shot_type=shot_type, limit=20)
        char_risks     = [self.get_character_drift_rate(c) for c in chars]

        avg_similar_R  = sum(s.get("R", 0) for s in similar) / max(len(similar), 1)
        high_risk_chars = [r for r in char_risks if r.get("risk_level") == "HIGH"]

        risk_level = "HIGH" if (avg_retries > 1.5 or high_risk_chars) else \
                     "MEDIUM" if (avg_retries > 0.8 or avg_similar_R < 0.65) else "LOW"

        return {
            "shot_id":            shot.get("shot_id", ""),
            "arc_position":       arc_pos,
            "shot_type":          shot_type,
            "predicted_retries":  avg_retries,
            "risk_level":         risk_level,
            "best_prompt_config": best_config,
            "character_drift_risks": char_risks,
            "similar_shots_count": len(similar),
            "similar_shots_avg_R": round(avg_similar_R, 3),
            "recommendation":     _build_recommendation(risk_level, best_config, high_risk_chars),
        }

    def close(self):
        for db in [self._series_db, self._project_db]:
            if db:
                try:
                    db.close()
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (module-level, for simple one-liner use)
# ═══════════════════════════════════════════════════════════════════════════

_GLOBAL_PI: Optional[ProductionIntelligence] = None

def _get_global(project_dir: Optional[Path] = None) -> ProductionIntelligence:
    global _GLOBAL_PI
    if _GLOBAL_PI is None:
        _GLOBAL_PI = ProductionIntelligence(project_dir)
    return _GLOBAL_PI


def write_shot_outcome(project: str, scene_id: str, shot: Dict,
                       scores: Dict, retries: int = 0, verdict: str = "PASS",
                       model_used: str = "kling_v3_pro",
                       doctrine_rules_fired: Optional[List[str]] = None,
                       project_dir: Optional[Path] = None):
    """Module-level convenience wrapper — non-blocking."""
    try:
        pi = _get_global(project_dir)
        pi.write_shot_outcome(project=project, scene_id=scene_id, shot=shot,
                              scores=scores, retries=retries, verdict=verdict,
                              model_used=model_used,
                              doctrine_rules_fired=doctrine_rules_fired)
    except Exception as e:
        logger.warning(f"[PI] write_shot_outcome wrapper failed: {e}")


def query_similar_shots(arc_position: str = "", shot_type: str = "",
                        limit: int = 10) -> List[Dict]:
    """Module-level convenience wrapper."""
    try:
        return _get_global().query_similar_shots(arc_position=arc_position,
                                                  shot_type=shot_type, limit=limit)
    except Exception:
        return []


def get_pre_generation_intel(shot: Dict, project: str = "",
                              project_dir: Optional[Path] = None) -> Dict:
    """Module-level convenience wrapper for pre-generation intelligence."""
    try:
        pi = _get_global(project_dir)
        return pi.get_pre_generation_intel(shot, project)
    except Exception:
        return {"risk_level": "UNKNOWN", "predicted_retries": 0.0}


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _build_recommendation(risk_level: str, best_config: Dict,
                           high_risk_chars: List[Dict]) -> str:
    parts = []
    if risk_level == "HIGH":
        parts.append("HIGH RISK: Expect retries. Consider boosting identity reinforcement.")
    if high_risk_chars:
        names = ", ".join(c["character"] for c in high_risk_chars)
        parts.append(f"Characters with high drift history: {names}. Use multi-ref injection.")
    if best_config:
        missing = []
        if not best_config.get("has_room_dna"):
            missing.append("ROOM DNA")
        if not best_config.get("has_identity_block"):
            missing.append("[CHARACTER:] block")
        if missing:
            parts.append(f"High-scoring configs always include: {', '.join(missing)}")
    return " | ".join(parts) if parts else "No special guidance — standard pipeline."


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        project_arg = sys.argv[1]
        pi = ProductionIntelligence()
        summary = pi.get_production_summary(project_arg)
        print(json.dumps(summary, indent=2))
    else:
        print("Usage: python3 production_intelligence.py <project_name>")
        print("       python3 production_intelligence.py victorian_shadows_ep1")
        pi = ProductionIntelligence()
        print(f"\nSeries DB: {_SERIES_DB_PATH}")
        print(f"Exists: {_SERIES_DB_PATH.exists()}")
