"""
Scene 002 Cinematic Analysis Runner
Uploads all 7 Scene 002 Kling videos to Gemini Vision, scores 8 dimensions,
and saves results to pipeline_outputs/victorian_shadows_ep1/
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# ── Load .env ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
dotenv_path = BASE / ".env"
if dotenv_path.exists():
    for line in dotenv_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "tools"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scene002_analysis")

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT     = "victorian_shadows_ep1"
SCENE_ID    = "002"
OUTPUT_DIR  = BASE / "pipeline_outputs" / PROJECT
VIDEOS_DIR  = OUTPUT_DIR / "videos_kling_lite"
SHOT_PLAN   = OUTPUT_DIR / "shot_plan.json"
CAST_MAP    = OUTPUT_DIR / "cast_map.json"

# Scene 002 video filenames in generation order
SCENE002_VIDEOS = {
    "002_E01": "multishot_g1_002_E01.mp4",
    "002_E02": "multishot_g2_002_E02.mp4",
    "002_E03": "multishot_g3_002_E03.mp4",
    "002_M01": "multishot_g4_002_M01.mp4",
    "002_M02": "multishot_g5_002_M02.mp4",
    "002_M03": "multishot_g6_002_M03.mp4",
    "002_M04": "multishot_g7_002_M04.mp4",
}

def load_data():
    with open(SHOT_PLAN) as f:
        raw = json.load(f)
    shots = raw if isinstance(raw, list) else raw.get("shots", [])

    cast = {}
    if CAST_MAP.exists():
        with open(CAST_MAP) as f:
            cast = json.load(f)

    scene_shots = {s["shot_id"]: s for s in shots if str(s.get("shot_id","")).startswith(SCENE_ID)}
    return scene_shots, cast


def run_analysis():
    from tools.auto_revision_judge import AutoRevisionJudge, _get_video_duration_s, _score_duration

    logger.info(f"=== Scene {SCENE_ID} Cinematic Analysis ===")
    logger.info(f"Videos dir: {VIDEOS_DIR}")

    scene_shots, cast_map = load_data()
    logger.info(f"Loaded {len(scene_shots)} shots, {len(cast_map)} cast entries")

    judge = AutoRevisionJudge()
    logger.info(f"Judge backend available: {judge.available}")

    shot_ids = ["002_E01", "002_E02", "002_E03", "002_M01", "002_M02", "002_M03", "002_M04"]
    results  = []
    t_start  = time.time()

    for i, shot_id in enumerate(shot_ids):
        shot = scene_shots.get(shot_id)
        if not shot:
            logger.warning(f"Shot {shot_id} not found in shot_plan")
            results.append({"shot_id": shot_id, "verdict": "SKIP", "reason": "Not in shot_plan"})
            continue

        video_fname = SCENE002_VIDEOS.get(shot_id)
        video_path  = str(VIDEOS_DIR / video_fname) if video_fname else None

        if not video_path or not os.path.exists(video_path):
            logger.warning(f"Video not found: {video_path}")
            results.append({"shot_id": shot_id, "verdict": "SKIP", "reason": f"Video not found: {video_fname}"})
            continue

        next_shot = scene_shots.get(shot_ids[i + 1]) if i + 1 < len(shot_ids) else None

        logger.info(f"[{i+1}/{len(shot_ids)}] Analyzing {shot_id} → {video_fname}")

        try:
            verdict = judge.judge(video_path, shot, cast_map, next_shot=next_shot)
            rec     = verdict.to_dict()

            # Add extra metadata for the report
            rec["video_filename"]  = video_fname
            rec["target_duration"] = shot.get("duration")
            rec["shot_type"]       = shot.get("shot_type")
            rec["characters"]      = shot.get("characters") or []
            rec["beat_action"]     = shot.get("_beat_action") or ""
            rec["beat_atmosphere"] = shot.get("_beat_atmosphere") or ""
            rec["dialogue_text"]   = (shot.get("dialogue_text") or "")[:120]
            rec["nano_prompt"]     = (shot.get("nano_prompt") or "")[:200]

            results.append(rec)
            logger.info(
                f"  → {verdict.verdict}  overall={verdict.overall:.3f}  "
                f"({verdict.analysis_ms}ms)"
            )
            if verdict.regen_instruction:
                logger.info(f"  REGEN: {verdict.regen_instruction[:120]}…")

        except Exception as e:
            logger.error(f"Analysis failed for {shot_id}: {e}")
            results.append({"shot_id": shot_id, "verdict": "ERROR", "reason": str(e),
                            "video_filename": video_fname or ""})

    total_s = time.time() - t_start

    # ── Build summary statistics ───────────────────────────────────────────────
    verdicts   = [r.get("verdict") for r in results]
    approvals  = verdicts.count("APPROVE")
    warns      = verdicts.count("WARN")
    rejects    = verdicts.count("REJECT")
    errors     = verdicts.count("ERROR") + verdicts.count("SKIP")

    # Per-dimension averages (only from valid Gemini results)
    dim_totals = {}
    dim_counts = {}
    for r in results:
        for dim, ds in r.get("dimensions", {}).items():
            score = ds.get("score", 0) if isinstance(ds, dict) else 0
            dim_totals[dim] = dim_totals.get(dim, 0) + score
            dim_counts[dim] = dim_counts.get(dim, 0) + 1

    dim_averages = {
        k: round(dim_totals[k] / dim_counts[k], 3)
        for k in dim_totals if dim_counts[k] > 0
    }

    # Auto-reject criteria derived from this analysis
    auto_reject_triggers = []
    for r in results:
        for dim, ds in r.get("dimensions", {}).items():
            score = ds.get("score", 1.0) if isinstance(ds, dict) else 1.0
            if score < 0.52 and r.get("verdict") in ("REJECT", "WARN"):
                auto_reject_triggers.append({
                    "shot_id":   r["shot_id"],
                    "dimension": dim,
                    "score":     score,
                    "fix":       ds.get("fix", "") if isinstance(ds, dict) else "",
                })

    # Derive recommended thresholds from data
    recommended_thresholds = {}
    for dim, avg in dim_averages.items():
        # Recommend reject threshold at mean - 1.5*std_dev (approx)
        scores = [
            r.get("dimensions", {}).get(dim, {}).get("score", avg)
            for r in results
            if isinstance(r.get("dimensions", {}).get(dim), dict)
        ]
        if scores:
            mean  = sum(scores) / len(scores)
            variance = sum((x - mean)**2 for x in scores) / len(scores)
            std   = variance**0.5
            recommended_thresholds[dim] = {
                "approve": round(min(0.90, mean + 0.5 * std), 2),
                "warn":    round(max(0.30, mean - 0.5 * std), 2),
                "reject":  round(max(0.20, mean - 1.5 * std), 2),
                "scene002_mean": round(mean, 3),
                "scene002_std":  round(std, 3),
            }

    output_json = {
        "project":    PROJECT,
        "scene_id":   SCENE_ID,
        "analysis_at": datetime.utcnow().isoformat() + "Z",
        "total_duration_s": round(total_s, 1),
        "summary": {
            "shots_analyzed": len(results),
            "approve": approvals,
            "warn":    warns,
            "reject":  rejects,
            "errors":  errors,
            "pass_rate": round(approvals / max(len(results) - errors, 1), 3),
        },
        "dimension_averages": dim_averages,
        "recommended_thresholds": recommended_thresholds,
        "auto_reject_triggers": auto_reject_triggers,
        "shots": results,
    }

    # ── Save JSON ──────────────────────────────────────────────────────────────
    json_path = OUTPUT_DIR / "scene002_cinematic_analysis.json"
    with open(json_path, "w") as f:
        json.dump(output_json, f, indent=2)
    logger.info(f"✓ Saved JSON → {json_path}")

    # ── Save Markdown ──────────────────────────────────────────────────────────
    md_path = OUTPUT_DIR / "scene002_cinematic_analysis.md"
    write_markdown_report(output_json, md_path)
    logger.info(f"✓ Saved Markdown → {md_path}")

    # ── Print summary ──────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print(f"SCENE 002 CINEMATIC ANALYSIS — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print("="*70)
    print(f"  Shots:    {approvals} APPROVE  {warns} WARN  {rejects} REJECT  {errors} SKIP")
    print(f"  Duration: {total_s:.1f}s total analysis time")
    print(f"\nDIMENSION AVERAGES:")
    for dim, avg in sorted(dim_averages.items(), key=lambda x: x[1]):
        bar    = "█" * int(avg * 10)
        status = "✓" if avg >= 0.72 else ("⚠" if avg >= 0.52 else "✗")
        print(f"  {status} {dim:28s}  {avg:.3f}  {bar:10s}")
    print(f"\nAUTO-REJECT TRIGGERS FOUND: {len(auto_reject_triggers)}")
    for t in auto_reject_triggers:
        print(f"  {t['shot_id']:12s}  {t['dimension']:25s}  {t['score']:.2f}  {t['fix'][:60]}")
    print("="*70)

    return output_json


def write_markdown_report(data: dict, path: Path):
    summary = data["summary"]
    dim_avg = data.get("dimension_averages", {})
    thresholds = data.get("recommended_thresholds", {})
    shots   = data["shots"]
    triggers = data.get("auto_reject_triggers", [])

    lines = [
        f"# Scene 002 Cinematic Analysis",
        f"",
        f"**Project:** {data['project']}  ",
        f"**Analyzed:** {data['analysis_at']}  ",
        f"**Analysis time:** {data['total_duration_s']}s  ",
        f"",
        f"## Summary",
        f"",
        f"| Verdict | Count |",
        f"|---------|-------|",
        f"| ✅ APPROVE | {summary['approve']} |",
        f"| ⚠️ WARN    | {summary['warn']} |",
        f"| ❌ REJECT  | {summary['reject']} |",
        f"| ⏭️ SKIP   | {summary.get('errors',0)} |",
        f"| **Pass rate** | **{summary['pass_rate']:.1%}** |",
        f"",
        f"## Dimension Averages (Scene 002 baseline)",
        f"",
        f"| Dimension | Avg Score | Status |",
        f"|-----------|-----------|--------|",
    ]
    for dim, avg in sorted(dim_avg.items(), key=lambda x: x[1]):
        status = "✅ PASS" if avg >= 0.72 else ("⚠️ WARN" if avg >= 0.52 else "❌ FAIL")
        lines.append(f"| {dim} | {avg:.3f} | {status} |")

    lines += [
        f"",
        f"## Recommended Auto-Reject Thresholds",
        f"",
        f"Derived from Scene 002 data (mean ± σ analysis). Use these in `pre_video_gate.py` PostVideoGate.",
        f"",
        f"| Dimension | REJECT below | WARN below | APPROVE above | Scene002 mean | σ |",
        f"|-----------|-------------|------------|---------------|---------------|---|",
    ]
    for dim, t in thresholds.items():
        lines.append(
            f"| {dim} | {t['reject']} | {t['warn']} | {t['approve']} "
            f"| {t['scene002_mean']} | {t['scene002_std']} |"
        )

    lines += [
        f"",
        f"## Auto-Reject Triggers Found",
        f"",
        f"Shots and dimensions that fell below the WARN threshold — these would trigger auto-regen.",
        f"",
        f"| Shot | Dimension | Score | Fix |",
        f"|------|-----------|-------|-----|",
    ]
    for t in triggers:
        fix_short = (t.get("fix") or "")[:80]
        lines.append(f"| {t['shot_id']} | {t['dimension']} | {t['score']:.2f} | {fix_short} |")

    if not triggers:
        lines.append("| — | — | — | No auto-reject triggers found |")

    lines += [
        f"",
        f"## Per-Shot Analysis",
        f"",
    ]

    for shot in shots:
        sid     = shot.get("shot_id", "?")
        verdict = shot.get("verdict", "?")
        overall = shot.get("overall", 0)
        icon    = {"APPROVE": "✅", "WARN": "⚠️", "REJECT": "❌", "SKIP": "⏭️", "ERROR": "💥"}.get(verdict, "?")
        vfname  = shot.get("video_filename", "")
        beat    = (shot.get("beat_action") or "")[:80]
        chars   = ", ".join(shot.get("characters") or []) or "none"
        regen   = shot.get("regen_instruction", "")

        lines += [
            f"### {icon} {sid} — {verdict}  (overall={overall:.3f})",
            f"",
            f"- **File:** `{vfname}`",
            f"- **Shot type:** {shot.get('shot_type')}  |  **Characters:** {chars}",
            f"- **Beat action:** {beat}",
            f"- **Target duration:** {shot.get('target_duration')}s  |  "
            f"**Actual:** {shot.get('dimensions', {}).get('duration_match', {}).get('observation', '?') if isinstance(shot.get('dimensions',{}).get('duration_match'), dict) else '?'}",
        ]

        if shot.get("dimensions"):
            lines.append(f"")
            lines.append(f"| Dimension | Score | Verdict | Observation |")
            lines.append(f"|-----------|-------|---------|-------------|")
            for dim, ds in shot["dimensions"].items():
                if isinstance(ds, dict):
                    score  = ds.get("score", 0)
                    verd   = ds.get("verdict", "?")
                    obs    = (ds.get("observation") or "")[:100]
                    v_icon = "✅" if verd == "PASS" else ("⚠️" if verd == "WARN" else "❌")
                    lines.append(f"| {dim} | {score:.3f} | {v_icon} {verd} | {obs} |")

        if regen:
            lines += [f"", f"**Regen instruction:** {regen}"]

        if shot.get("hard_rejects"):
            lines += [f"", f"**⛔ Hard rejects:** {', '.join(shot['hard_rejects'])}"]

        lines.append(f"")

    lines += [
        f"---",
        f"",
        f"## Auto-Revision Criteria Definition",
        f"",
        f"Based on this Scene 002 analysis, the following criteria are recommended for the",
        f"`AutoRevisionJudge` system and `PreVideoGate.PostVideoGate`:",
        f"",
        f"### Hard Reject Rules (override overall score → always REJECT)",
        f"",
        f"| Dimension | Threshold | Rationale |",
        f"|-----------|-----------|-----------|",
        f"| `duration_match` | < 0.50 | Dialogue will be cut off if video is too short |",
        f"| `identity_consistency` | < 0.40 | Character drift ruins continuity irreparably |",
        f"| `story_beat_accuracy` | < 0.30 | Wrong action means wrong story — must regenerate |",
        f"",
        f"### Soft Warn/Reject Rules (contribute to overall score)",
        f"",
        f"| Dimension | REJECT | WARN | Notes |",
        f"|-----------|--------|------|-------|",
        f"| `dialogue_timing` | < 0.45 | 0.45–0.65 | Only for dialogue shots |",
        f"| `cinematic_tone` | < 0.40 | 0.40–0.65 | Gothic Victorian requires dark amber warmth |",
        f"| `camera_work` | < 0.40 | 0.40–0.65 | Shot type must match specification |",
        f"| `character_blocking` | < 0.45 | 0.45–0.65 | 180° rule must be respected |",
        f"| `end_frame_continuity` | < 0.35 | 0.35–0.60 | Chain integrity depends on clean exits |",
        f"",
        f"### Diagnostic Regen Instructions (injected on REJECT)",
        f"",
        f"Each rejected dimension injects a `[FIX — DIMENSION_NAME]` directive prepended to",
        f"the next generation attempt's nano_prompt. The Kling prompt compiler reads these",
        f"as highest-priority corrections.",
        f"",
        f"*Generated by `tools/auto_revision_judge.py` — ATLAS V31.0*",
    ]

    path.write_text("\n".join(lines))


if __name__ == "__main__":
    run_analysis()
