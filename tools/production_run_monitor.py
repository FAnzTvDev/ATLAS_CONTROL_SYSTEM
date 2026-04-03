"""
ATLAS V27.5.1 PRODUCTION RUN MONITOR
=====================================
Wraps the V26 controller render_scene() with full timing instrumentation,
call chain logging, and process analysis.

Usage:
    python3 tools/production_run_monitor.py <project> <scene_id> [--dry-run]

Outputs:
    - Real-time console logging of every phase
    - Timing breakdown per phase and per shot
    - FAL call count and cost estimation
    - Identity injection coverage report
    - Vision Judge verdict summary
    - Final process overview saved to reports/
"""

import sys
import os
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from functools import wraps
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ═══ TIMING INFRASTRUCTURE ═══

class PhaseTimer:
    """Tracks timing for every phase of the render pipeline."""

    def __init__(self):
        self.phases = {}
        self.fal_calls = []
        self.current_phase = None
        self._start = None
        self._global_start = None

    def start_global(self):
        self._global_start = time.time()

    def start(self, phase_name):
        self.current_phase = phase_name
        self._start = time.time()
        print(f"  [{self._elapsed():.1f}s] ▶ {phase_name}")

    def stop(self, detail=""):
        if self._start and self.current_phase:
            elapsed = time.time() - self._start
            self.phases[self.current_phase] = {
                "elapsed_ms": round(elapsed * 1000),
                "detail": detail,
            }
            status = "✓" if elapsed < 5 else "⚠" if elapsed < 30 else "⏱"
            print(f"  [{self._elapsed():.1f}s] {status} {self.current_phase}: {elapsed:.2f}s {detail}")
            self.current_phase = None
            self._start = None

    def log_fal_call(self, shot_id, model, n_candidates, elapsed_s, cost_est):
        self.fal_calls.append({
            "shot_id": shot_id,
            "model": model,
            "candidates": n_candidates,
            "elapsed_s": round(elapsed_s, 2),
            "cost_est": cost_est,
        })

    def _elapsed(self):
        return time.time() - self._global_start if self._global_start else 0

    def total_elapsed(self):
        return time.time() - self._global_start if self._global_start else 0

    def summary(self):
        total_fal = sum(c["elapsed_s"] for c in self.fal_calls)
        total_cost = sum(c["cost_est"] for c in self.fal_calls)
        total_candidates = sum(c["candidates"] for c in self.fal_calls)
        return {
            "total_elapsed_s": round(self.total_elapsed(), 2),
            "phase_timings": self.phases,
            "fal_calls": len(self.fal_calls),
            "fal_total_time_s": round(total_fal, 2),
            "fal_total_candidates": total_candidates,
            "fal_cost_estimate": f"${total_cost:.3f}",
        }


# ═══ MAIN MONITOR ═══

def run_monitored_render(project_name, scene_id, dry_run=False):
    """Execute a V26 controller render with full monitoring."""

    timer = PhaseTimer()
    timer.start_global()
    report = {
        "project": project_name,
        "scene_id": scene_id,
        "started_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "v27_5_1_systems": {},
        "phases": {},
        "shots": {},
        "errors": [],
    }

    print(f"\n{'='*70}")
    print(f"  ATLAS V27.5.1 PRODUCTION RUN MONITOR")
    print(f"  Project: {project_name} | Scene: {scene_id} | {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*70}\n")

    # ── PHASE 0: Pre-flight checks ──
    timer.start("Phase 0: Pre-flight checks")

    project_path = Path(f"pipeline_outputs/{project_name}")
    if not project_path.exists():
        print(f"  [ABORT] Project not found: {project_path}")
        return None

    shot_plan_path = project_path / "shot_plan.json"
    cast_map_path = project_path / "cast_map.json"
    story_bible_path = project_path / "story_bible.json"

    missing = []
    for p in [shot_plan_path, cast_map_path, story_bible_path]:
        if not p.exists():
            missing.append(p.name)
    if missing:
        print(f"  [ABORT] Missing files: {', '.join(missing)}")
        return None

    # Load data for analysis
    with open(shot_plan_path) as f:
        sp = json.load(f)
    if isinstance(sp, list):
        shots = sp
    else:
        shots = sp.get("shots", [])

    with open(cast_map_path) as f:
        cast_map = json.load(f)

    scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
    char_shots = [s for s in scene_shots if s.get("characters")]
    broll_shots = [s for s in scene_shots if not s.get("characters")]
    dialogue_shots = [s for s in scene_shots if s.get("dialogue_text")]

    timer.stop(f"{len(scene_shots)} shots ({len(char_shots)} char, {len(broll_shots)} broll, {len(dialogue_shots)} dialogue)")

    report["scene_summary"] = {
        "total_shots": len(scene_shots),
        "character_shots": len(char_shots),
        "broll_shots": len(broll_shots),
        "dialogue_shots": len(dialogue_shots),
        "unique_characters": list(set(
            c if isinstance(c, str) else c.get("name", "")
            for s in scene_shots
            for c in (s.get("characters") or [])
        )),
    }

    # ── PHASE 1: Learning Log regression check ──
    timer.start("Phase 1: Learning Log regression check")
    try:
        from tools.atlas_learning_log import LearningLog
        ll = LearningLog()
        regressions = ll.check_regression()
        if regressions:
            for r in regressions:
                print(f"    ⚠ REGRESSION: {r['bug_id']}")
            report["v27_5_1_systems"]["learning_log"] = {"status": "REGRESSION", "count": len(regressions)}
        else:
            report["v27_5_1_systems"]["learning_log"] = {"status": "CLEAN", "fixes_verified": len(ll._entries)}
        timer.stop(f"{len(ll._entries)} fixes verified, {len(regressions)} regressions")
    except Exception as e:
        timer.stop(f"SKIPPED: {e}")
        report["v27_5_1_systems"]["learning_log"] = {"status": "SKIPPED", "error": str(e)}

    # ── PHASE 2: Identity injection simulation ──
    timer.start("Phase 2: Identity injection simulation")
    injection_results = {}
    try:
        from tools.prompt_identity_injector import inject_identity_into_prompt

        injected_count = 0
        skipped_count = 0
        for shot in scene_shots:
            sid = shot.get("shot_id", "?")
            prompt = shot.get("nano_prompt", "") or ""
            chars = shot.get("characters", []) or []
            char_names = [c if isinstance(c, str) else c.get("name", "") for c in chars]
            shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
            dialogue = shot.get("dialogue_text", "") or ""

            result = inject_identity_into_prompt(prompt, char_names, cast_map, shot_type, dialogue)

            had_identity_before = "[CHARACTER:" in prompt
            has_identity_after = "[CHARACTER:" in result

            if chars and has_identity_after and not had_identity_before:
                injected_count += 1
                injection_results[sid] = "INJECTED"
            elif not chars:
                has_negative = "no people" in result.lower() or "No people" in result
                injection_results[sid] = "NEGATIVE_CONSTRAINT" if has_negative else "EMPTY_OK"
            elif had_identity_before:
                injection_results[sid] = "ALREADY_HAD"
                skipped_count += 1
            else:
                injection_results[sid] = "NO_CHANGE"
                skipped_count += 1

        coverage = injected_count / max(len(char_shots), 1) * 100
        report["v27_5_1_systems"]["identity_injection"] = {
            "status": "OK" if coverage > 90 else "DEGRADED",
            "injected": injected_count,
            "skipped": skipped_count,
            "coverage_pct": round(coverage, 1),
            "per_shot": injection_results,
        }
        timer.stop(f"{injected_count}/{len(char_shots)} injected ({coverage:.0f}% coverage)")
    except Exception as e:
        timer.stop(f"FAILED: {e}")
        report["v27_5_1_systems"]["identity_injection"] = {"status": "FAILED", "error": str(e)}

    # ── PHASE 3: Multi-candidate count simulation ──
    timer.start("Phase 3: Multi-candidate count plan")
    try:
        from tools.multi_candidate_selector import get_candidate_count

        total_candidates = 0
        candidate_plan = {}
        for shot in scene_shots:
            sid = shot.get("shot_id", "?")
            count = get_candidate_count(shot)
            candidate_plan[sid] = count
            total_candidates += count

        hero_count = sum(1 for v in candidate_plan.values() if v == 3)
        prod_count = sum(1 for v in candidate_plan.values() if v == 2)
        broll_count = sum(1 for v in candidate_plan.values() if v == 1)

        # Cost estimate: ~$0.02 per FAL image generation
        cost_per_image = 0.02
        estimated_cost = total_candidates * cost_per_image

        report["v27_5_1_systems"]["multi_candidate"] = {
            "status": "OK",
            "total_candidates": total_candidates,
            "hero_3x": hero_count,
            "production_2x": prod_count,
            "broll_1x": broll_count,
            "estimated_cost": f"${estimated_cost:.2f}",
            "per_shot": candidate_plan,
        }
        timer.stop(f"{total_candidates} total candidates ({hero_count}×3 + {prod_count}×2 + {broll_count}×1) ≈ ${estimated_cost:.2f}")
    except Exception as e:
        timer.stop(f"FAILED: {e}")
        report["v27_5_1_systems"]["multi_candidate"] = {"status": "FAILED", "error": str(e)}

    # ── PHASE 4: Prompt corruption scan ──
    timer.start("Phase 4: Prompt corruption scan")
    corrupted = []
    for shot in scene_shots:
        sid = shot.get("shot_id", "?")
        for field in ["nano_prompt", "ltx_motion_prompt"]:
            prompt = shot.get(field, "") or ""
            if len(prompt) > 100:
                for i in range(0, min(len(prompt) - 30, 200), 10):
                    sub = prompt[i:i+30]
                    if prompt.count(sub) >= 3:
                        corrupted.append({"shot_id": sid, "field": field, "substring": sub[:20]})
                        break

    report["v27_5_1_systems"]["corruption_scan"] = {
        "status": "CLEAN" if not corrupted else "CORRUPTED",
        "corrupted_count": len(corrupted),
        "details": corrupted,
    }
    timer.stop(f"{'CLEAN' if not corrupted else f'{len(corrupted)} CORRUPTED PROMPTS'}")

    # ── PHASE 5: Vision Judge readiness ──
    timer.start("Phase 5: Vision Judge readiness check")
    try:
        from tools.vision_judge import judge_frame, extract_identity_markers, score_caption_against_markers

        # Check that markers can be extracted for all characters in scene
        marker_coverage = {}
        for shot in char_shots:
            for c in (shot.get("characters") or []):
                name = c if isinstance(c, str) else c.get("name", "")
                if name and name not in marker_coverage:
                    appearance = cast_map.get(name, {}).get("appearance", "")
                    markers = extract_identity_markers(appearance)
                    marker_coverage[name] = {
                        "marker_count": len(markers),
                        "markers": [m[0] for m in markers[:5]],
                        "appearance_length": len(appearance),
                    }

        all_have_markers = all(v["marker_count"] > 0 for v in marker_coverage.values())
        report["v27_5_1_systems"]["vision_judge"] = {
            "status": "READY" if all_have_markers else "DEGRADED",
            "character_markers": marker_coverage,
        }
        timer.stop(f"{len(marker_coverage)} characters profiled, {'all have markers' if all_have_markers else 'SOME MISSING MARKERS'}")
    except Exception as e:
        timer.stop(f"FAILED: {e}")
        report["v27_5_1_systems"]["vision_judge"] = {"status": "FAILED", "error": str(e)}

    # ── PHASE 6: Scene Visual DNA check ──
    timer.start("Phase 6: Scene Visual DNA availability")
    try:
        from tools.scene_visual_dna import build_scene_dna, get_focal_length_enforcement, build_scene_lighting_rig

        with open(story_bible_path) as f:
            story_bible = json.load(f)

        # Find scene in story bible
        scene_data = None
        scenes = story_bible.get("scenes", [])
        for s in scenes:
            if s.get("scene_id") == scene_id or str(s.get("scene_number")) == scene_id:
                scene_data = s
                break

        if scene_data:
            dna = build_scene_dna(scene_data)
            lighting = build_scene_lighting_rig(scene_data)
            focal_sample = get_focal_length_enforcement("close_up")
            report["v27_5_1_systems"]["scene_dna"] = {
                "status": "READY",
                "dna_length": len(dna) if dna else 0,
                "lighting_length": len(lighting) if lighting else 0,
                "focal_sample": focal_sample[:80] if focal_sample else "NONE",
            }
            timer.stop(f"DNA: {len(dna) if dna else 0} chars, Lighting: {len(lighting) if lighting else 0} chars")
        else:
            report["v27_5_1_systems"]["scene_dna"] = {"status": "NO_SCENE_DATA"}
            timer.stop("Scene not found in story bible")
    except Exception as e:
        timer.stop(f"SKIPPED: {e}")
        report["v27_5_1_systems"]["scene_dna"] = {"status": "SKIPPED", "error": str(e)}

    # ── SUMMARY ──
    print(f"\n{'='*70}")
    print(f"  PRE-FLIGHT COMPLETE — {timer.total_elapsed():.1f}s total")
    print(f"{'='*70}")

    # System status matrix
    print(f"\n  V27.5.1 SYSTEM STATUS:")
    for sys_name, sys_data in report["v27_5_1_systems"].items():
        status = sys_data.get("status", "UNKNOWN")
        icon = "✓" if status in ("OK", "CLEAN", "READY") else "⚠" if status in ("DEGRADED", "SKIPPED") else "✗"
        print(f"    {icon} {sys_name}: {status}")

    # Shot execution plan
    print(f"\n  EXECUTION PLAN:")
    print(f"    Shots to generate: {len(scene_shots)}")
    print(f"    Total FAL candidates: {report['v27_5_1_systems'].get('multi_candidate', {}).get('total_candidates', '?')}")
    print(f"    Estimated cost: {report['v27_5_1_systems'].get('multi_candidate', {}).get('estimated_cost', '?')}")
    print(f"    Characters: {', '.join(report['scene_summary']['unique_characters'][:5])}")

    if dry_run:
        print(f"\n  [DRY RUN] Stopping before FAL calls.")
        print(f"  To execute live: python3 tools/production_run_monitor.py {project_name} {scene_id}")
    else:
        print(f"\n  ▶ STARTING LIVE RENDER...")
        timer.start("Phase 7: V26 Controller render_scene()")

        try:
            # Start the orchestrator server in-process for imports
            os.environ["ATLAS_FORCE_JSON"] = "1"  # Skip PostgreSQL requirement

            from atlas_v26_controller import V26Controller

            controller = V26Controller(project_name)
            result = controller.render_scene(scene_id, skip_probe=True)

            timer.stop(f"render complete")

            report["render_result"] = result

            # Extract per-shot data
            shot_results = result.get("shot_results", [])
            if isinstance(shot_results, dict):
                shot_results = list(shot_results.values())

            generated = sum(1 for s in shot_results if s.get("generated"))
            failed = sum(1 for s in shot_results if not s.get("generated"))

            print(f"\n  RENDER RESULTS:")
            print(f"    Generated: {generated}/{len(shot_results)}")
            print(f"    Failed: {failed}")

            # Identity scores
            identity_scores = [s.get("identity_score", -1) for s in shot_results if s.get("identity_score", -1) >= 0]
            if identity_scores:
                avg_id = sum(identity_scores) / len(identity_scores)
                print(f"    Identity avg: {avg_id:.3f}")

            # Vision Judge verdicts
            vj_verdicts = defaultdict(int)
            for s in shot_results:
                vj = s.get("vision_judge", {})
                if vj:
                    vj_verdicts[vj.get("verdict", "NONE")] += 1
            if vj_verdicts:
                print(f"    Vision Judge: {dict(vj_verdicts)}")

            # Keyframe verdicts
            kf_verdicts = defaultdict(int)
            for s in shot_results:
                kf = s.get("keyframe_verdict", "")
                if kf:
                    kf_verdicts[kf] += 1
            if kf_verdicts:
                print(f"    Keyframe: {dict(kf_verdicts)}")

            # Compliance
            compliance = result.get("doctrine_compliance", result.get("render_results", {}).get("compliance_score", "N/A"))
            print(f"    Compliance: {compliance}")

            # Per-shot breakdown
            print(f"\n  PER-SHOT BREAKDOWN:")
            for s in shot_results:
                sid = s.get("shot_id", "?")
                gen = "✓" if s.get("generated") else "✗"
                id_score = s.get("identity_score", -1)
                vj = s.get("vision_judge", {}).get("verdict", "—")
                kf = s.get("keyframe_verdict", "—")
                print(f"    {gen} {sid}: identity={id_score:.2f}, vj={vj}, kf={kf}")

        except Exception as e:
            timer.stop(f"FAILED: {e}")
            report["errors"].append({"phase": "render", "error": str(e)})
            import traceback
            traceback.print_exc()

    # ── SAVE REPORT ──
    report["completed_at"] = datetime.utcnow().isoformat()
    report["timing"] = timer.summary()

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"production_run_{project_name}_{scene_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  Report saved: {report_path}")
    print(f"  Total time: {timer.total_elapsed():.1f}s")
    print(f"{'='*70}\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATLAS V27.5.1 Production Run Monitor")
    parser.add_argument("project", help="Project name (e.g., ravencroft_v22)")
    parser.add_argument("scene_id", help="Scene ID to render (e.g., 001)")
    parser.add_argument("--dry-run", action="store_true", help="Pre-flight only, no FAL calls")
    args = parser.parse_args()

    run_monitored_render(args.project, args.scene_id, dry_run=args.dry_run)
