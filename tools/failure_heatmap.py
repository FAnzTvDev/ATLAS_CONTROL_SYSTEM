"""
tools/failure_heatmap.py — ATLAS V36 Failure Heatmap System

Cybernetic control layer: measures production health across three loops.
  Inner Loop  — shot correctness (shot type, OTS, char count, EXT/INT, artifacts)
  Middle Loop — scene continuity (room consistency, screen direction, eyeline)
  Outer Loop  — production stability (runner, ledger, video_url, completion rate)

Usage:
    from tools.failure_heatmap import build_heatmap, assess_production_readiness, generate_executive_view
    heatmap = build_heatmap('pipeline_outputs/victorian_shadows_ep1/shot_plan.json',
                             'pipeline_outputs/victorian_shadows_ep1/first_frames',
                             'pipeline_outputs/victorian_shadows_ep1/videos_kling_lite')
    print(assess_production_readiness(heatmap))
    print(generate_executive_view(heatmap))
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# V36 AUTHORITY LOCK
# This module is OBSERVATION ONLY.
# It CANNOT modify shot_plan.json, prompts, or any generation state.
# It CANNOT trigger regen or change thresholds.
# It reports. Humans decide. Controller acts.
_AUTHORITY_LEVEL = "OBSERVE_ONLY"


def _assert_observe_only():
    """Called before any write attempt — raises if heatmap tries to mutate state."""
    raise PermissionError(
        "V36 AUTHORITY VIOLATION: Heatmap is observe-only. Cannot mutate production state."
    )


# ─────────────────────────────────────────────────────────────────────────────
# FAILURE TAXONOMY  (locked constants — append-only)
# ─────────────────────────────────────────────────────────────────────────────

CREATIVE_FAILURES: dict[str, str] = {
    "OTS_DIRECTION_FAIL":  "Wrong character foreground in over-the-shoulder",
    "SHOT_TYPE_FAIL":      "Wide generated as insert or vice versa",
    "CHARACTER_COUNT_FAIL": "Wrong number of people in frame",
    "LOCATION_CONTEXT_FAIL": "EXT/INT mismatch or wrong room",
    "PROP_BEAT_FAIL":      "Story beat action not executed",
    "ARTIFACT_FAIL":       "AI text, phantom limbs, composite seams",
    "IDENTITY_DRIFT":      "Character appearance changed",
    "CONTINUITY_DRIFT":    "Spatial/temporal break between shots",
}

OPERATIONAL_FAILURES: dict[str, str] = {
    "VIDEO_URL_MISSING":       "Generated but metadata not updated",
    "FILE_STATE_MISMATCH":     "File exists but shot_plan disagrees",
    "RUNNER_DEAD":             "Background process terminated",
    "LEDGER_STALE":            "Reward ledger not updated",
    "SCORE_HEURISTIC_ONLY":    "Vision returned flat 0.75",
    "PROCESS_TIMEOUT":         "API call exceeded time limit",
    "API_RETRY_EXHAUSTED":     "Max retries hit",
}

ALL_FAILURE_CODES: dict[str, str] = {**CREATIVE_FAILURES, **OPERATIONAL_FAILURES}

# Cinematic severity weights (0-3) per failure code
CINEMATIC_SEVERITY: dict[str, int] = {
    "OTS_DIRECTION_FAIL":      3,
    "SHOT_TYPE_FAIL":          3,
    "CHARACTER_COUNT_FAIL":    3,
    "LOCATION_CONTEXT_FAIL":   2,
    "PROP_BEAT_FAIL":          2,
    "ARTIFACT_FAIL":           3,
    "IDENTITY_DRIFT":          3,
    "CONTINUITY_DRIFT":        2,
    "VIDEO_URL_MISSING":       0,
    "FILE_STATE_MISMATCH":     0,
    "RUNNER_DEAD":             0,
    "LEDGER_STALE":            0,
    "SCORE_HEURISTIC_ONLY":    0,
    "PROCESS_TIMEOUT":         0,
    "API_RETRY_EXHAUSTED":     0,
}

SYSTEM_SEVERITY: dict[str, int] = {
    "OTS_DIRECTION_FAIL":      0,
    "SHOT_TYPE_FAIL":          0,
    "CHARACTER_COUNT_FAIL":    0,
    "LOCATION_CONTEXT_FAIL":   0,
    "PROP_BEAT_FAIL":          0,
    "ARTIFACT_FAIL":           1,
    "IDENTITY_DRIFT":          1,
    "CONTINUITY_DRIFT":        1,
    "VIDEO_URL_MISSING":       3,
    "FILE_STATE_MISMATCH":     2,
    "RUNNER_DEAD":             3,
    "LEDGER_STALE":            2,
    "SCORE_HEURISTIC_ONLY":    1,
    "PROCESS_TIMEOUT":         2,
    "API_RETRY_EXHAUSTED":     3,
}

# ─────────────────────────────────────────────────────────────────────────────
# SEVERITY MODEL
# ─────────────────────────────────────────────────────────────────────────────

def compute_heat(cinematic_severity: int, system_severity: int) -> int:
    """Both 0-3 scale. Returns 0-6 heat score."""
    return cinematic_severity + system_severity


def heat_for_code(failure_code: str) -> int:
    """Return heat score (0-6) for a given failure code."""
    c = CINEMATIC_SEVERITY.get(failure_code, 0)
    s = SYSTEM_SEVERITY.get(failure_code, 0)
    return compute_heat(c, s)


def heat_color(heat: int) -> str:
    """Map heat 0-6 to display color label."""
    if heat == 0:
        return "green"
    if heat <= 2:
        return "yellow"
    if heat <= 4:
        return "orange"
    return "red"


# ─────────────────────────────────────────────────────────────────────────────
# PER-SHOT METRICS SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

SHOT_METRICS_SCHEMA: dict[str, type] = {
    "scene_id":              str,
    "shot_id":               str,
    "declared_shot_type":    str,   # from shot_plan
    "detected_shot_type":    str,   # from vision analysis (if available)
    "expected_char_count":   int,
    "detected_char_count":   int,   # from vision (if available)
    "expected_context":      str,   # EXT or INT
    "detected_context":      str,
    "artifact_flag":         bool,
    "continuity_flag":       bool,
    "first_pass_status":     str,   # PASS / FAIL / REGEN
    "regen_count":           int,
    "final_status":          str,   # APPROVED / REGEN_REQUESTED / AWAITING_APPROVAL
    "generation_cost":       float,
    "generation_time":       float,
    "analysis_confidence":   float,
    "primary_failure_code":  str,   # from taxonomy
    "secondary_failure_code": str,
}


def _empty_metrics(shot_id: str, scene_id: str) -> dict[str, Any]:
    return {
        "scene_id":               scene_id,
        "shot_id":                shot_id,
        "declared_shot_type":     "",
        "detected_shot_type":     "",
        "expected_char_count":    0,
        "detected_char_count":    -1,   # -1 = unknown
        "expected_context":       "",
        "detected_context":       "",
        "artifact_flag":          False,
        "continuity_flag":        False,
        "first_pass_status":      "UNKNOWN",
        "regen_count":            0,
        "final_status":           "",
        "generation_cost":        0.0,
        "generation_time":        0.0,
        "analysis_confidence":    0.0,
        "primary_failure_code":   "",
        "secondary_failure_code": "",
        # computed below
        "heat":                   0,
        "frame_on_disk":          False,
        "video_on_disk":          False,
        "identity_score":         None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION HEALTH THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

THRESHOLDS: dict[str, Any] = {
    "green": {
        "first_pass_success":    0.90,
        "hard_semantic_fail":    0.05,
        "operational_fail":      0.02,
        "video_url_completeness": 1.0,
    },
    "yellow": {
        "first_pass_success":    0.75,
        "recurring_family":      0.10,
    },
    "red": {
        "operational_severity_3": True,
        "clustered_hard_fails":   0.25,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_shot_plan(shot_plan_path: str) -> list[dict]:
    with open(shot_plan_path, "r") as f:
        sp = json.load(f)
    return sp if isinstance(sp, list) else sp.get("shots", [])


def _load_ledger(project_dir: str) -> dict[str, dict]:
    """Load reward_ledger.jsonl keyed by shot_id, keeping last entry per shot."""
    ledger_path = os.path.join(project_dir, "reward_ledger.jsonl")
    ledger: dict[str, dict] = {}
    if not os.path.exists(ledger_path):
        return ledger
    try:
        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    sid = entry.get("shot_id", "")
                    if sid:
                        ledger[sid] = entry
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return ledger


def _detect_context(shot: dict) -> str:
    """Infer expected EXT/INT from location and frame description."""
    loc = (shot.get("location") or "").upper()
    desc = (shot.get("_frame_description") or shot.get("description") or "").upper()
    nano = (shot.get("nano_prompt") or "").upper()[:200]
    text = f"{loc} {desc} {nano}"
    if text.strip().startswith("EXT") or " EXT " in text or "EXTERIOR" in text:
        return "EXT"
    if text.strip().startswith("INT") or " INT " in text or "INTERIOR" in text:
        return "INT"
    return "INT"  # default


def _detect_failure_codes(
    shot: dict,
    frame_on_disk: bool,
    video_on_disk: bool,
    ledger_entry: dict | None,
    identity_score: float | None,
) -> tuple[str, str]:
    """
    Derive primary and secondary failure codes from shot fields + file state.
    Returns (primary_code, secondary_code).
    """
    codes: list[str] = []

    approval = shot.get("_approval_status", "")
    qa_flag = shot.get("_qa_flag", "")
    regen_note = shot.get("_regen_note", "")
    regen_note_str = (regen_note or "").upper()
    qa_str = (qa_flag or "").upper()
    nano = (shot.get("nano_prompt") or "").upper()[:300]

    # ── Operational failures ─────────────────────────────────────────────────

    # Video URL in shot_plan but file missing on disk
    video_url = shot.get("video_url") or shot.get("video_path") or ""
    if video_url and not video_on_disk:
        codes.append("FILE_STATE_MISMATCH")

    # Shot has no video url at all (and not a pure frame-only scene)
    if not video_url and not video_on_disk:
        codes.append("VIDEO_URL_MISSING")

    # Identity score stuck at flat 0.75 heuristic
    i_score = shot.get("_frame_identity_score")
    if i_score is not None and abs(float(i_score) - 0.75) < 0.001:
        codes.append("SCORE_HEURISTIC_ONLY")

    # ── Creative failures (from QA flag text + regen notes) ──────────────────

    if "OTS" in qa_str or "OVER-THE-SHOULDER" in qa_str or "OVER THE SHOULDER" in qa_str:
        codes.append("OTS_DIRECTION_FAIL")

    if ("TEXT" in qa_str and ("AI" in qa_str or "ARTIFICIAL" in qa_str)) or \
       "CONTAMINATION" in qa_str or "TEXT CONTAMINATION" in regen_note_str or \
       ("TEXT" in regen_note_str and "BOOK" in regen_note_str):
        codes.append("ARTIFACT_FAIL")

    if "LOCATION" in regen_note_str or "ROOM" in regen_note_str or \
       "LOCATION" in qa_str or "STAIRCASE" in regen_note_str:
        codes.append("LOCATION_CONTEXT_FAIL")

    if "IDENTITY" in qa_str or "WRONG PERSON" in qa_str or "DRIFT" in qa_str:
        codes.append("IDENTITY_DRIFT")

    if approval == "REGEN_REQUESTED" and not codes:
        # Regen requested but no specific code yet — try to infer
        if regen_note_str:
            if any(k in regen_note_str for k in ("FACE", "HAIR", "CLOTHING", "APPEARANCE")):
                codes.append("IDENTITY_DRIFT")
            elif any(k in regen_note_str for k in ("ROOM", "LOCATION", "WALL", "STAIRCASE", "FLOOR")):
                codes.append("LOCATION_CONTEXT_FAIL")
            elif any(k in regen_note_str for k in ("SHOT", "FRAME", "WIDE", "CLOSE", "INSERT")):
                codes.append("SHOT_TYPE_FAIL")
            else:
                codes.append("PROP_BEAT_FAIL")
        elif not frame_on_disk:
            codes.append("FILE_STATE_MISMATCH")

    # Low identity score from ledger
    if identity_score is not None and identity_score < 0.25 and "IDENTITY_DRIFT" not in codes:
        codes.append("IDENTITY_DRIFT")

    primary = codes[0] if codes else ""
    secondary = codes[1] if len(codes) > 1 else ""
    return primary, secondary


# ─────────────────────────────────────────────────────────────────────────────
# CORE BUILD FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_heatmap(
    shot_plan_path: str,
    first_frames_dir: str,
    videos_dir: str,
) -> dict[str, Any]:
    """
    Build the full heatmap from current system state.

    Returns:
        {
          'shots': [per-shot metrics dicts],
          'scenes': {scene_id: scene-level aggregates},
          'failure_families': {code: count},
          'operational': {...health summary},
          'summary': {...global aggregates},
          'generated_at': ISO timestamp,
        }
    """
    t0 = time.time()

    shots = _load_shot_plan(shot_plan_path)
    project_dir = os.path.dirname(shot_plan_path)
    ledger = _load_ledger(project_dir)

    # Index files on disk (basename → True)
    def _index_dir(d: str) -> set[str]:
        if os.path.isdir(d):
            return {f.lower() for f in os.listdir(d)}
        return set()

    frame_files = _index_dir(first_frames_dir)
    video_files = _index_dir(videos_dir)

    # ── Per-shot metrics ─────────────────────────────────────────────────────
    shot_metrics: list[dict] = []
    failure_family_counts: dict[str, int] = defaultdict(int)

    for shot in shots:
        sid = shot.get("shot_id", "unknown")
        scene_id = shot.get("scene_id", "?")
        m = _empty_metrics(sid, scene_id)

        # Basic declared fields
        m["declared_shot_type"] = shot.get("shot_type", "")
        m["expected_char_count"] = len(shot.get("characters") or [])
        m["expected_context"] = _detect_context(shot)
        m["final_status"] = shot.get("_approval_status", "")

        # File state
        ff_url = shot.get("first_frame_url") or shot.get("first_frame_path") or ""
        ff_basename = os.path.basename(ff_url).lower() if ff_url else f"{sid.lower()}.jpg"
        vid_url = shot.get("video_url") or shot.get("video_path") or ""
        vid_basename = os.path.basename(vid_url).lower() if vid_url else ""

        m["frame_on_disk"] = ff_basename in frame_files if ff_basename else False
        m["video_on_disk"] = (vid_basename in video_files) if vid_basename else False

        # Identity score
        raw_i = shot.get("_identity_score") or shot.get("_frame_identity_score")
        ledger_entry = ledger.get(sid)
        if ledger_entry:
            ledger_i = ledger_entry.get("I")
            # prefer ledger score if it's not the flat heuristic
            if ledger_i is not None and abs(float(ledger_i) - 0.75) > 0.001:
                raw_i = ledger_i
        m["identity_score"] = float(raw_i) if raw_i is not None else None

        # First-pass status
        approval = shot.get("_approval_status", "")
        if approval == "APPROVED":
            m["first_pass_status"] = "PASS"
        elif approval == "REGEN_REQUESTED":
            m["first_pass_status"] = "FAIL"
        elif approval == "AUTO_APPROVED":
            m["first_pass_status"] = "PASS"
        elif not m["frame_on_disk"]:
            m["first_pass_status"] = "FAIL"
        else:
            m["first_pass_status"] = "PENDING"

        # Regen count (check _regen_note existence as proxy)
        if shot.get("_regen_note"):
            m["regen_count"] = 1
        if approval == "REGEN_REQUESTED":
            m["regen_count"] = max(m["regen_count"], 1)

        # Artifact flag from QA
        qa_str = (shot.get("_qa_flag") or "").upper()
        m["artifact_flag"] = "TEXT" in qa_str or "CONTAMINATION" in qa_str or "PHANTOM" in qa_str

        # Continuity flag
        m["continuity_flag"] = "CONTINUITY" in qa_str or "DRIFT" in qa_str

        # Failure code detection
        primary, secondary = _detect_failure_codes(
            shot, m["frame_on_disk"], m["video_on_disk"],
            ledger_entry, m["identity_score"]
        )
        m["primary_failure_code"] = primary
        m["secondary_failure_code"] = secondary

        if primary:
            failure_family_counts[primary] += 1
        if secondary:
            failure_family_counts[secondary] += 1

        # Heat score
        if primary:
            m["heat"] = heat_for_code(primary)
        else:
            m["heat"] = 0

        # Analysis confidence (based on whether we have ledger + real I-score)
        if ledger_entry and m["identity_score"] is not None and abs(float(m["identity_score"]) - 0.75) > 0.001:
            m["analysis_confidence"] = 0.9
        elif m["identity_score"] is not None:
            m["analysis_confidence"] = 0.5
        else:
            m["analysis_confidence"] = 0.2

        shot_metrics.append(m)

    # ── Scene-level aggregates ────────────────────────────────────────────────
    scene_agg: dict[str, dict] = {}
    scene_shots: dict[str, list] = defaultdict(list)
    for m in shot_metrics:
        scene_shots[m["scene_id"]].append(m)

    for scene_id, s_list in scene_shots.items():
        total = len(s_list)
        pass_count = sum(1 for m in s_list if m["first_pass_status"] == "PASS")
        fail_count = sum(1 for m in s_list if m["first_pass_status"] == "FAIL")
        has_video = sum(1 for m in s_list if m["video_on_disk"])
        has_frame = sum(1 for m in s_list if m["frame_on_disk"])
        max_heat = max((m["heat"] for m in s_list), default=0)
        avg_heat = sum(m["heat"] for m in s_list) / total if total else 0
        failure_codes_in_scene = [m["primary_failure_code"] for m in s_list if m["primary_failure_code"]]

        # Scene completeness
        if has_video == total:
            completeness = "COMPLETE"
        elif has_video > 0:
            completeness = "PARTIAL"
        elif has_frame == total:
            completeness = "FRAMES_ONLY"
        else:
            completeness = "MISSING"

        scene_agg[scene_id] = {
            "scene_id":       scene_id,
            "total_shots":    total,
            "pass_count":     pass_count,
            "fail_count":     fail_count,
            "pending_count":  total - pass_count - fail_count,
            "video_count":    has_video,
            "frame_count":    has_frame,
            "first_pass_rate": round(pass_count / total, 3) if total else 0.0,
            "video_completion": round(has_video / total, 3) if total else 0.0,
            "max_heat":       max_heat,
            "avg_heat":       round(avg_heat, 2),
            "completeness":   completeness,
            "failure_codes":  failure_codes_in_scene,
        }

    # ── Global summary ────────────────────────────────────────────────────────
    total_shots = len(shot_metrics)
    pass_shots = sum(1 for m in shot_metrics if m["first_pass_status"] == "PASS")
    fail_shots = sum(1 for m in shot_metrics if m["first_pass_status"] == "FAIL")
    pending_shots = total_shots - pass_shots - fail_shots
    frames_on_disk = sum(1 for m in shot_metrics if m["frame_on_disk"])
    videos_on_disk = sum(1 for m in shot_metrics if m["video_on_disk"])
    regen_shots = sum(1 for m in shot_metrics if m["regen_count"] > 0)
    heuristic_only = sum(1 for m in shot_metrics if "SCORE_HEURISTIC_ONLY" in [m["primary_failure_code"], m["secondary_failure_code"]])
    hard_fails = sum(1 for m in shot_metrics if m.get("heat", 0) >= 3)

    # Operational checks
    file_state_mismatches = failure_family_counts.get("FILE_STATE_MISMATCH", 0)
    video_url_missing = failure_family_counts.get("VIDEO_URL_MISSING", 0)
    has_ops_severity_3 = any(
        heat_for_code(c) >= 5
        for c, cnt in failure_family_counts.items()
        if cnt > 0 and c in OPERATIONAL_FAILURES
    )

    # Ledger staleness: check if any generated shots have no ledger entry
    shots_needing_ledger = [m for m in shot_metrics if m["frame_on_disk"]]
    shots_with_ledger = sum(1 for m in shots_needing_ledger if ledger.get(m["shot_id"]))
    ledger_coverage = shots_with_ledger / len(shots_needing_ledger) if shots_needing_ledger else 1.0

    summary = {
        "total_shots":         total_shots,
        "pass_shots":          pass_shots,
        "fail_shots":          fail_shots,
        "pending_shots":       pending_shots,
        "frames_on_disk":      frames_on_disk,
        "videos_on_disk":      videos_on_disk,
        "regen_count":         regen_shots,
        "first_pass_rate":     round(pass_shots / total_shots, 3) if total_shots else 0.0,
        "video_completeness":  round(videos_on_disk / total_shots, 3) if total_shots else 0.0,
        "frame_completeness":  round(frames_on_disk / total_shots, 3) if total_shots else 0.0,
        "hard_semantic_fails": hard_fails,
        "hard_semantic_rate":  round(hard_fails / total_shots, 3) if total_shots else 0.0,
        "heuristic_only_shots": heuristic_only,
        "heuristic_only_rate": round(heuristic_only / total_shots, 3) if total_shots else 0.0,
        "file_state_mismatches": file_state_mismatches,
        "has_ops_severity_3":  has_ops_severity_3,
        "ledger_coverage":     round(ledger_coverage, 3),
        "scene_count":         len(scene_agg),
        "build_time_s":        round(time.time() - t0, 3),
    }

    return {
        "shots":            shot_metrics,
        "scenes":           scene_agg,
        "failure_families": dict(failure_family_counts),
        "operational": {
            "file_state_mismatches": file_state_mismatches,
            "video_url_missing":     video_url_missing,
            "heuristic_only_shots":  heuristic_only,
            "ledger_coverage":       round(ledger_coverage, 3),
            "has_ops_severity_3":    has_ops_severity_3,
        },
        "summary":       summary,
        "generated_at":  datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION READINESS ASSESSMENT
# ─────────────────────────────────────────────────────────────────────────────

def assess_production_readiness(heatmap_data: dict) -> str:
    """
    Returns GREEN / YELLOW / RED based on thresholds.

    GREEN  — ≥90% first-pass, <5% hard semantic fails, <2% ops fails, 100% video_url completeness
    YELLOW — 75-89% first-pass OR recurring failure family >10% of shots
    RED    — ops severity-3 hit OR <75% first-pass OR hard fails cluster >25%
    """
    s = heatmap_data["summary"]
    ops = heatmap_data["operational"]

    first_pass = s["first_pass_rate"]
    hard_semantic = s["hard_semantic_rate"]
    # ops fail rate = ops failures / total shots
    total = s["total_shots"]
    ops_fail_count = ops["file_state_mismatches"] + ops["video_url_missing"]
    ops_fail_rate = ops_fail_count / total if total else 0.0

    # Recurring failure family: any single family > 10% of shots
    ff = heatmap_data["failure_families"]
    max_family_rate = max((cnt / total for cnt in ff.values() if total), default=0.0)

    # RED checks (any one triggers RED)
    if ops["has_ops_severity_3"]:
        return "RED"
    if first_pass < THRESHOLDS["red"]["clustered_hard_fails"]:
        # actually THRESHOLDS["red"]["clustered_hard_fails"] is for hard fails —
        # use first_pass < 0.25 as direct check
        pass
    if hard_semantic > THRESHOLDS["red"]["clustered_hard_fails"]:
        return "RED"
    if first_pass < THRESHOLDS["yellow"]["first_pass_success"]:
        return "RED"

    # GREEN checks (all must pass)
    if (
        first_pass >= THRESHOLDS["green"]["first_pass_success"]
        and hard_semantic <= THRESHOLDS["green"]["hard_semantic_fail"]
        and ops_fail_rate <= THRESHOLDS["green"]["operational_fail"]
        and max_family_rate <= THRESHOLDS["green"]["hard_semantic_fail"]
    ):
        return "GREEN"

    # Otherwise YELLOW
    return "YELLOW"


# ─────────────────────────────────────────────────────────────────────────────
# VIEW GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

_HEAT_GLYPH = {0: "·", 1: "▪", 2: "▫", 3: "◈", 4: "◉", 5: "⬛", 6: "🔴"}
_STATUS_GLYPH = {"PASS": "✓", "FAIL": "✗", "PENDING": "⏳", "UNKNOWN": "?"}


def generate_director_view(heatmap_data: dict) -> str:
    """
    Simple visual: scene × shot grid with heat glyphs + failure codes.
    Designed for the filmmaker reviewing production coverage.
    """
    lines = ["╔══════════════════════════════════════════════════════════╗",
             "║           ATLAS DIRECTOR VIEW — PRODUCTION HEATMAP       ║",
             "╚══════════════════════════════════════════════════════════╝",
             ""]

    shots_by_scene: dict[str, list] = defaultdict(list)
    for m in heatmap_data["shots"]:
        shots_by_scene[m["scene_id"]].append(m)

    for scene_id in sorted(shots_by_scene):
        agg = heatmap_data["scenes"].get(scene_id, {})
        completeness = agg.get("completeness", "?")
        fpr = agg.get("first_pass_rate", 0.0)
        comp_label = {
            "COMPLETE": "✅ VIDEO DONE",
            "PARTIAL": "▶ PARTIAL VIDEO",
            "FRAMES_ONLY": "🖼 FRAMES ONLY",
            "MISSING": "❌ MISSING",
        }.get(completeness, completeness)

        lines.append(f"  SCENE {scene_id}  {comp_label}  [pass={fpr:.0%}]")

        row = "  "
        for m in sorted(shots_by_scene[scene_id], key=lambda x: x["shot_id"]):
            heat = m.get("heat", 0)
            glyph = _HEAT_GLYPH.get(heat, "?")
            status = _STATUS_GLYPH.get(m["first_pass_status"], "?")
            code = m["primary_failure_code"][:4] if m["primary_failure_code"] else "    "
            row += f" {m['shot_id'].split('_')[1]:4s}{status}{glyph}{code}"

        lines.append(row)
        lines.append("")

    # Failure legend
    lines.append("  HEAT GLYPHS: · =0  ▪=1  ▫=2  ◈=3  ◉=4  ⬛=5  🔴=6")
    lines.append("  STATUS: ✓=pass  ✗=fail  ⏳=pending")
    lines.append("")

    # Top failure codes
    ff = heatmap_data["failure_families"]
    if ff:
        lines.append("  TOP FAILURE FAMILIES:")
        for code, cnt in sorted(ff.items(), key=lambda x: -x[1])[:6]:
            desc = ALL_FAILURE_CODES.get(code, code)
            heat = heat_for_code(code)
            lines.append(f"    [{cnt:3d}] heat={heat} {code:30s} {desc}")

    return "\n".join(lines)


def generate_systems_view(heatmap_data: dict) -> str:
    """
    Dense diagnostic: every failure code, process health, state mismatches.
    Designed for the engineer debugging production.
    """
    s = heatmap_data["summary"]
    ops = heatmap_data["operational"]
    ff = heatmap_data["failure_families"]

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║            ATLAS SYSTEMS VIEW — DIAGNOSTIC DENSE         ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "  ── GENERATION STATE ─────────────────────────────────────",
        f"  Total shots:          {s['total_shots']}",
        f"  Frames on disk:       {s['frames_on_disk']} / {s['total_shots']}  ({s['frame_completeness']:.0%})",
        f"  Videos on disk:       {s['videos_on_disk']} / {s['total_shots']}  ({s['video_completeness']:.0%})",
        f"  APPROVED:             {s['pass_shots']}",
        f"  REGEN_REQUESTED:      {s['fail_shots']}",
        f"  PENDING:              {s['pending_shots']}",
        f"  Regen events:         {s['regen_count']}",
        "",
        "  ── CREATIVE FAILURES ─────────────────────────────────────",
    ]

    for code, desc in CREATIVE_FAILURES.items():
        cnt = ff.get(code, 0)
        heat = heat_for_code(code)
        marker = " ⚠ " if cnt > 0 else "   "
        lines.append(f"  {marker}{code:30s} cnt={cnt:3d}  heat={heat}  {desc}")

    lines += [
        "",
        "  ── OPERATIONAL FAILURES ──────────────────────────────────",
    ]

    for code, desc in OPERATIONAL_FAILURES.items():
        cnt = ff.get(code, 0)
        heat = heat_for_code(code)
        marker = " ⚠ " if cnt > 0 else "   "
        lines.append(f"  {marker}{code:30s} cnt={cnt:3d}  heat={heat}  {desc}")

    lines += [
        "",
        "  ── PROCESS HEALTH ────────────────────────────────────────",
        f"  Ledger coverage:      {ops['ledger_coverage']:.0%}  ({int(ops['ledger_coverage'] * s['frames_on_disk'])}/{s['frames_on_disk']} shots scored)",
        f"  Heuristic-only shots: {ops['heuristic_only_shots']}  (vision returned flat 0.75)",
        f"  File-state mismatches:{ops['file_state_mismatches']}",
        f"  Video URL missing:    {ops['video_url_missing']}",
        f"  Ops severity-3 hit:   {ops['has_ops_severity_3']}",
        "",
        "  ── PER-SCENE STATE ───────────────────────────────────────",
    ]

    for scene_id in sorted(heatmap_data["scenes"]):
        a = heatmap_data["scenes"][scene_id]
        codes = ", ".join(set(a["failure_codes"])) if a["failure_codes"] else "—"
        lines.append(
            f"  Scene {scene_id}: {a['completeness']:14s} "
            f"pass={a['first_pass_rate']:.0%}  "
            f"heat_max={a['max_heat']}  "
            f"fails=[{codes}]"
        )

    lines += [
        "",
        f"  Heatmap built at {heatmap_data.get('generated_at', '?')}  "
        f"(build_time={s.get('build_time_s', 0):.3f}s)",
    ]

    return "\n".join(lines)


def generate_executive_view(heatmap_data: dict) -> str:
    """
    Compressed: pass rate, regens/scene, common failure, cost, ETA.
    Designed for a quick production status check.
    """
    s = heatmap_data["summary"]
    readiness = assess_production_readiness(heatmap_data)

    status_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(readiness, "⚪")

    # Most common failure
    ff = heatmap_data["failure_families"]
    if ff:
        top_code, top_cnt = max(ff.items(), key=lambda x: x[1])
        top_desc = ALL_FAILURE_CODES.get(top_code, top_code)
    else:
        top_code, top_cnt, top_desc = "—", 0, "none"

    # Regens per scene
    regens_per_scene = round(s["regen_count"] / s["scene_count"], 1) if s["scene_count"] else 0

    # Scene completion
    scenes = heatmap_data["scenes"]
    complete_scenes = sum(1 for a in scenes.values() if a["completeness"] == "COMPLETE")
    partial_scenes = sum(1 for a in scenes.values() if a["completeness"] == "PARTIAL")
    frame_only = sum(1 for a in scenes.values() if a["completeness"] == "FRAMES_ONLY")
    missing_scenes = sum(1 for a in scenes.values() if a["completeness"] == "MISSING")

    lines = [
        f"  {status_emoji} PRODUCTION READINESS: {readiness}",
        f"  {'─'*52}",
        f"  First-pass rate:   {s['first_pass_rate']:.0%}  ({s['pass_shots']}/{s['total_shots']} shots approved)",
        f"  Frame coverage:    {s['frame_completeness']:.0%}  ({s['frames_on_disk']}/{s['total_shots']} on disk)",
        f"  Video coverage:    {s['video_completeness']:.0%}  ({s['videos_on_disk']}/{s['total_shots']} on disk)",
        f"  Regen events:      {s['regen_count']} total  ({regens_per_scene}/scene avg)",
        f"  Hard fails (≥3):   {s['hard_semantic_fails']} shots  ({s['hard_semantic_rate']:.0%})",
        f"  Vision quality:    {s['heuristic_only_shots']} shots stuck at heuristic 0.75",
        f"  Ledger coverage:   {s['ledger_coverage']:.0%} of frames scored",
        f"  {'─'*52}",
        f"  Scene breakdown:   {complete_scenes} complete | {partial_scenes} partial video | {frame_only} frames-only | {missing_scenes} missing",
        f"  Top failure:       [{top_cnt}×] {top_code} — {top_desc}",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="ATLAS V36 Failure Heatmap")
    parser.add_argument("--project-dir", default="pipeline_outputs/victorian_shadows_ep1",
                        help="Project directory")
    parser.add_argument("--videos-dir", default=None, help="Override videos dir name")
    parser.add_argument("--view", choices=["director", "systems", "executive", "all"],
                        default="all")
    args = parser.parse_args()

    shot_plan = os.path.join(args.project_dir, "shot_plan.json")
    frames_dir = os.path.join(args.project_dir, "first_frames")
    vids_dir = os.path.join(args.project_dir, args.videos_dir or "videos_kling_lite")

    heatmap = build_heatmap(shot_plan, frames_dir, vids_dir)
    readiness = assess_production_readiness(heatmap)

    if args.view in ("executive", "all"):
        print(generate_executive_view(heatmap))
        print()
    if args.view in ("director", "all"):
        print(generate_director_view(heatmap))
        print()
    if args.view in ("systems", "all"):
        print(generate_systems_view(heatmap))
