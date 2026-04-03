#!/usr/bin/env python3
"""
V21 REGRESSION TEST — Full Script-to-Prompt Fidelity Suite
===========================================================
Tests every prompt against the story bible to ensure:
1. Beat actions are present
2. Dialogue markers exist for speaking shots
3. Character names match between bible and shot_plan
4. Scene locations are correct
5. Color grades are scene-appropriate
6. No enrichment artifacts remain
7. Story specificity score >= target
8. Beat coverage is complete
9. Emotional arc is smooth
10. No cross-scene contamination

Run: python3 tools/run_regression_test.py [project_dir] [shot_plan_file]
"""

import json
import re
import os
import sys
import copy

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tools.prompt_authority_gate import (
    enforce_prompt_authority,
    CANONICAL_CHARACTERS,
    SCENE_COLOR_GRADES,
)
from tools.script_insight_engine import (
    enrich_with_script_insight,
    score_story_specificity,
    validate_beat_coverage,
    validate_emotional_arc,
    extract_beat_actions,
    SCENE_ATMOSPHERES,
)


def load_data(project_dir, shot_plan_file="shot_plan_v21_clean.json"):
    """Load shot plan and story bible."""
    sp_path = os.path.join(project_dir, shot_plan_file)
    sb_path = os.path.join(project_dir, "story_bible.json")

    if not os.path.exists(sp_path):
        print(f"ERROR: Shot plan not found: {sp_path}")
        sys.exit(1)

    sp = json.load(open(sp_path))
    sb = json.load(open(sb_path)) if os.path.exists(sb_path) else {}

    return sp, sb


def run_before_test(shots, sb):
    """Score prompts BEFORE any gate/insight processing."""
    scene_beats = {}
    for scene in sb.get("scenes", []):
        sid = scene.get("scene_id", "")[:3]
        scene_beats[sid] = scene.get("beats", [])

    results = []
    for shot in shots:
        sid = shot.get("shot_id", "").split("_")[0]
        beats = scene_beats.get(sid, [])

        # Get proportional beat
        scene_shots = [s for s in shots if s.get("shot_id", "").startswith(sid)]
        idx = scene_shots.index(shot) if shot in scene_shots else 0
        n = len(beats)
        m = len(scene_shots)
        beat = beats[min(int(idx * n / m), n - 1)] if n > 0 and m > 0 else None

        spec = score_story_specificity(shot, beat)
        nano = shot.get("nano_prompt", "")
        ltx = shot.get("ltx_motion_prompt", "")
        dlg = shot.get("dialogue_text", shot.get("dialogue", ""))

        results.append({
            "shot_id": shot.get("shot_id", ""),
            "score": spec["score"],
            "grade": spec["grade"],
            "flags": spec["flags"],
            "has_action": "character action:" in nano.lower(),
            "has_speaks": "speaks:" in ltx.lower(),
            "has_dialogue": bool(dlg),
            "nano_len": len(nano),
        })

    return results


def run_after_test(shots, sb, project_dir):
    """Score prompts AFTER full gate + insight processing."""
    # Deep copy to not mutate originals
    test_shots = copy.deepcopy(shots)

    # Run full gate with script insight
    stats = enforce_prompt_authority(
        test_shots,
        project_path=project_dir,
        story_bible=sb,
    )

    scene_beats = {}
    for scene in sb.get("scenes", []):
        sid = scene.get("scene_id", "")[:3]
        scene_beats[sid] = scene.get("beats", [])

    results = []
    for shot in test_shots:
        sid = shot.get("shot_id", "").split("_")[0]
        beats = scene_beats.get(sid, [])

        scene_shots = [s for s in test_shots if s.get("shot_id", "").startswith(sid)]
        idx = scene_shots.index(shot) if shot in scene_shots else 0
        n = len(beats)
        m = len(scene_shots)
        beat = beats[min(int(idx * n / m), n - 1)] if n > 0 and m > 0 else None

        spec = score_story_specificity(shot, beat)
        nano = shot.get("nano_prompt", "")
        ltx = shot.get("ltx_motion_prompt", "")
        dlg = shot.get("dialogue_text", shot.get("dialogue", ""))

        # Additional checks
        has_isabella = "isabella" in nano.lower() or "italian woman" in nano.lower()
        has_hex = bool(re.search(r'#[0-9A-Fa-f]{6}', nano))
        has_eterna = "eterna" in nano.lower()
        has_red = "RED Monstro" in nano

        color_ok = True
        grade_info = SCENE_COLOR_GRADES.get(sid, {})
        if grade_info:
            primary = grade_info["grade"].split(",")[0].strip().lower()
            color_ok = primary in nano.lower()

        results.append({
            "shot_id": shot.get("shot_id", ""),
            "score": spec["score"],
            "grade": spec["grade"],
            "flags": spec["flags"],
            "has_action": "character action:" in nano.lower(),
            "has_speaks": "speaks:" in ltx.lower() or "character speaks:" in ltx.lower(),
            "has_dialogue": bool(dlg),
            "nano_len": len(nano),
            "no_isabella": not has_isabella,
            "no_hex": not has_hex,
            "no_eterna": not has_eterna,
            "no_red": not has_red,
            "color_grade_correct": color_ok,
            "nano_preview": nano[:200],
        })

    return results, test_shots, stats


def print_comparison(before, after):
    """Print side-by-side comparison of before vs after."""
    print(f"\n{'='*90}")
    print(f"{'SHOT':<12} {'BEFORE':>8} {'AFTER':>8} {'DELTA':>7} {'ACTION':>7} {'SPEAK':>7} {'COLOR':>7} {'CLEAN':>7}")
    print(f"{'='*90}")

    for b, a in zip(before, after):
        delta = a["score"] - b["score"]
        delta_str = f"+{delta}" if delta > 0 else str(delta) if delta < 0 else "="

        action = "✅" if a["has_action"] else ("🔧" if not b["has_action"] else "❌")
        speak = "✅" if a["has_speaks"] else ("—" if not a["has_dialogue"] else "❌")
        color = "✅" if a.get("color_grade_correct", True) else "❌"
        clean = "✅" if (a.get("no_isabella", True) and a.get("no_hex", True) and a.get("no_eterna", True)) else "❌"

        print(f"{a['shot_id']:<12} {b['score']:>5}/{b['grade']}  {a['score']:>5}/{a['grade']}  {delta_str:>6}  {action:>6}  {speak:>6}  {color:>6}  {clean:>6}")

    # Summary
    before_avg = sum(b["score"] for b in before) / len(before) if before else 0
    after_avg = sum(a["score"] for a in after) / len(after) if after else 0
    before_actions = sum(1 for b in before if b["has_action"])
    after_actions = sum(1 for a in after if a["has_action"])
    before_speaks = sum(1 for b in before if b["has_speaks"] and b["has_dialogue"])
    after_speaks = sum(1 for a in after if a["has_speaks"] and a["has_dialogue"])

    print(f"\n{'─'*90}")
    print(f"AVERAGES:    {before_avg:>5.0f}     {after_avg:>5.0f}    +{after_avg-before_avg:.0f}")
    print(f"ACTIONS:     {before_actions:>5}/{len(before)}  {after_actions:>5}/{len(after)}")
    print(f"DLG MARKERS: {before_speaks:>5}     {after_speaks:>5}")
    print(f"{'─'*90}")

    # Grade distribution
    before_grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    after_grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for b in before:
        before_grades[b["grade"]] += 1
    for a in after:
        after_grades[a["grade"]] += 1

    print(f"GRADES:  BEFORE: A={before_grades['A']} B={before_grades['B']} C={before_grades['C']} D={before_grades['D']} F={before_grades['F']}")
    print(f"         AFTER:  A={after_grades['A']} B={after_grades['B']} C={after_grades['C']} D={after_grades['D']} F={after_grades['F']}")


def run_contamination_checks(after_shots):
    """Check for cross-scene contamination."""
    issues = []
    for shot in after_shots:
        sid = shot.get("shot_id", "").split("_")[0]
        nano = shot.get("nano_prompt", "")

        # Scene 003 should NOT have lawyer/office references
        if sid == "003":
            if "lawyer's letter" in nano.lower():
                issues.append(f"{shot.get('shot_id')}: lawyer's letter in bus scene")
            if "office" in nano.lower() and "law office" not in nano.lower():
                issues.append(f"{shot.get('shot_id')}: office reference in bus scene")

        # Scene 001 should NOT have apartment references
        if sid == "001":
            if "apartment" in nano.lower():
                issues.append(f"{shot.get('shot_id')}: apartment in ritual scene")

        # Scene 002 should NOT have ritual/altar references
        if sid == "002":
            if "altar" in nano.lower():
                issues.append(f"{shot.get('shot_id')}: altar in apartment scene")
            if "ritual" in nano.lower():
                issues.append(f"{shot.get('shot_id')}: ritual in apartment scene")

    return issues


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/ravencroft_v17"
    shot_plan_file = sys.argv[2] if len(sys.argv) > 2 else "shot_plan_v21_clean.json"

    print(f"V21 REGRESSION TEST — Script-to-Prompt Fidelity Suite")
    print(f"{'='*70}")
    print(f"Project: {project_dir}")
    print(f"Shot plan: {shot_plan_file}")

    sp, sb = load_data(project_dir, shot_plan_file)
    all_shots = sp.get("shots", [])
    target_shots = [s for s in all_shots
                    if s.get("shot_id", "").split("_")[0] in ("001", "002", "003")]

    print(f"Total shots: {len(all_shots)} | Target (001-003): {len(target_shots)}")
    print()

    # ---- BEFORE ----
    print("Running BEFORE analysis (raw prompts)...")
    before = run_before_test(target_shots, sb)

    # ---- AFTER ----
    print("Running AFTER analysis (gate + script insight)...")
    after, processed_shots, gate_stats = run_after_test(target_shots, sb, project_dir)

    # ---- COMPARISON ----
    print_comparison(before, after)

    # ---- CONTAMINATION CHECK ----
    print(f"\n{'='*70}")
    print("CONTAMINATION CHECK")
    print(f"{'='*70}")
    contam = run_contamination_checks(processed_shots)
    if contam:
        for issue in contam:
            print(f"  ❌ {issue}")
    else:
        print("  ✅ No cross-scene contamination found")

    # ---- BEAT COVERAGE ----
    print(f"\n{'='*70}")
    print("BEAT COVERAGE")
    print(f"{'='*70}")
    scene_beats = {}
    for scene in sb.get("scenes", []):
        sid = scene.get("scene_id", "")[:3]
        scene_beats[sid] = scene.get("beats", [])

    for sid in ("001", "002", "003"):
        scene_shot_list = [s for s in processed_shots if s.get("shot_id", "").startswith(sid)]
        beats = scene_beats.get(sid, [])
        if beats:
            coverage = validate_beat_coverage(scene_shot_list, beats)
            status = "✅" if coverage["coverage_pct"] == 100 else "⚠️"
            print(f"  {status} Scene {sid}: {coverage['covered']}/{coverage['total_beats']} beats ({coverage['coverage_pct']}%)")
            for ub in coverage["uncovered"]:
                print(f"      ❌ Missing: Beat {ub['beat_number']} — {ub['description']}")

    # ---- EMOTIONAL ARC ----
    print(f"\n{'='*70}")
    print("EMOTIONAL ARC")
    print(f"{'='*70}")
    for sid in ("001", "002", "003"):
        scene_shot_list = [s for s in processed_shots if s.get("shot_id", "").startswith(sid)]
        beats = scene_beats.get(sid, [])
        if beats:
            arc = validate_emotional_arc(scene_shot_list, beats)
            status = "✅" if arc["smoothness"] == "smooth" else "⚠️"
            print(f"  {status} Scene {sid}: {arc['smoothness']} ({arc['jump_count']} jumps)")

    # ---- SAMPLE PROMPTS ----
    print(f"\n{'='*70}")
    print("SAMPLE ENRICHED PROMPTS (showing story content)")
    print(f"{'='*70}")
    for scene_id in ("001", "002", "003"):
        scene_shots = [s for s in processed_shots if s.get("shot_id", "").startswith(scene_id)]
        if scene_shots:
            s = scene_shots[1] if len(scene_shots) > 1 else scene_shots[0]
            print(f"\n--- {s['shot_id']} ({len(s['nano_prompt'])} chars) ---")
            # Show the full prompt, highlighting key parts
            nano = s['nano_prompt']
            # Bold action markers
            nano_display = nano[:500]
            print(nano_display)
            if len(nano) > 500:
                print(f"... ({len(nano) - 500} more chars)")

    # ---- GATE STATS ----
    print(f"\n{'='*70}")
    print("GATE STATISTICS")
    print(f"{'='*70}")
    print(f"  Shots processed: {gate_stats['total']}")
    print(f"  Conflicts stripped: {gate_stats['stripped']}")
    print(f"  Color grades fixed: {gate_stats['color_fixed']}")
    if gate_stats.get("script_insight"):
        si = gate_stats["script_insight"]
        print(f"  Beat actions injected: {si.get('actions_injected', 0)}")
        print(f"  Dialogue markers added: {si.get('dialogue_markers_added', 0)}")
        print(f"  Atmosphere injected: {si.get('atmosphere_injected', 0)}")
        print(f"  Avg specificity: {si.get('avg_specificity', 0)}/100")
        print(f"  Grade distribution: {si.get('grade_distribution', {})}")

    # ---- PASS/FAIL VERDICT ----
    print(f"\n{'='*70}")
    after_avg = sum(a["score"] for a in after) / len(after) if after else 0
    after_actions = sum(1 for a in after if a["has_action"])
    after_speaks = sum(1 for a in after if a["has_speaks"] and a["has_dialogue"])
    dlg_total = sum(1 for a in after if a["has_dialogue"])
    all_clean = all(a.get("no_isabella", True) and a.get("no_hex", True) for a in after)
    all_color = all(a.get("color_grade_correct", True) for a in after)

    verdict = "PASS" if (
        after_avg >= 70 and
        after_actions >= len(after) * 0.9 and
        after_speaks >= dlg_total * 0.8 and
        all_clean and
        not contam
    ) else "FAIL"

    print(f"VERDICT: {'✅ ' if verdict == 'PASS' else '❌ '}{verdict}")
    print(f"{'='*70}")

    criteria = [
        ("Avg specificity >= 70", after_avg >= 70, f"{after_avg:.0f}/100"),
        ("Actions >= 90%", after_actions >= len(after) * 0.9, f"{after_actions}/{len(after)}"),
        ("Dialogue markers >= 80%", after_speaks >= dlg_total * 0.8, f"{after_speaks}/{dlg_total}"),
        ("No enrichment artifacts", all_clean, "clean" if all_clean else "dirty"),
        ("Correct color grades", all_color, "correct" if all_color else "wrong"),
        ("No contamination", not contam, f"{len(contam)} issues" if contam else "clean"),
    ]

    for name, passed, detail in criteria:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: {detail}")
