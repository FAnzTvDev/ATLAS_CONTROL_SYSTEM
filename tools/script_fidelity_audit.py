#!/usr/bin/env python3
"""
ATLAS V21.9 — Script Fidelity Audit Tool
=========================================
Reusable pipeline tool that cross-references ALL shot prompts against:
  1. Original screenplay text
  2. Enhanced story bible beats
  3. V21.9 regression checks (7 invariants)
  4. Pacing analysis
  5. Prompt quality metrics

USAGE:
  python3 tools/script_fidelity_audit.py <project> [--fix] [--json]

  --fix   Auto-fix issues found (generic actions, missing markers)
  --json  Output as JSON instead of text report

Designed to run AFTER fix-v16 as a final validation gate.
Every new script imported into ATLAS should be audited with this tool.

INTEGRATION:
  Called by orchestrator_server.py at:
    POST /api/v21/script-fidelity-audit
  Also callable standalone from CLI.
"""

import json, re, os, sys, argparse, tempfile
from collections import defaultdict, Counter
from pathlib import Path

# ─── Configuration ───
BASE = Path(__file__).parent.parent  # ATLAS_CONTROL_SYSTEM root
PIPELINE = BASE / "pipeline_outputs"

# ─── V21.9 Invariant Checks ───
HUMAN_MARKERS = [
    "character performs:", "character speaks:", "character reacts:",
    "micro-expression", "breathing", "chest rise", "blinks",
    "subtle eye movement", "lips moving", "face stable",
    "natural speech movement", "DIALOGUE PERFORMANCE MANDATORY"
]

GENERIC_NONE_PATTERNS = [
    r"Character action:\s*None\s+experiences",
    r"Character action:\s*None\s+explains",
    r"Character action:\s*None\s+warns",
    r"Character action:\s*None\s+reveals",
    r"Character action:\s*None\s+asks",
    r"Character action:\s*None\s+gathers",
]

NONE_REPLACEMENTS = {
    "None experiences the moment": "{char} holds the moment, present and engaged",
    "None explains situation": "{char} conveys information with measured authority",
    "None warns about danger": "{char} delivers warning with grave concern",
    "None reveals truth to another": "{char} reveals a difficult truth",
    "None asks questions": "{char} asks probing questions",
    "None gathers items": "{char} methodically gathers items",
}


def load_project(project_name):
    """Load all project data needed for audit."""
    proj_dir = PIPELINE / project_name

    # Load shot plan
    sp_path = proj_dir / "shot_plan.json"
    if not sp_path.exists():
        raise FileNotFoundError(f"No shot_plan.json in {proj_dir}")
    with open(sp_path) as f:
        sp_data = json.load(f)
    shots = sp_data.get("shots", sp_data) if isinstance(sp_data, dict) else sp_data

    # Load story bible
    sb_path = proj_dir / "story_bible.json"
    bible = {}
    if sb_path.exists():
        with open(sb_path) as f:
            bible = json.load(f)

    # Find original script
    script_text = ""
    for script_name in ["script.txt", "script.fountain", f"{project_name}_script.txt"]:
        spath = proj_dir / script_name
        if spath.exists():
            with open(spath) as f:
                script_text = f.read()
            break
    # Also check root
    if not script_text:
        for ext in ["*.txt", "*.fountain"]:
            for p in BASE.glob(ext):
                if "script" in p.name.lower() or project_name.split("_")[0] in p.name.lower():
                    with open(p) as f:
                        script_text = f.read()
                    break

    return shots, bible, script_text, sp_data, proj_dir


def extract_screenplay_dialogue(script_text):
    """Extract dialogue from screenplay format."""
    dialogue = defaultdict(list)
    current_char = None
    for line in script_text.split("\n"):
        stripped = line.strip()
        char_match = re.match(r'^\s{10,}([A-Z][A-Z\s\.]+?)(?:\s*\(.*\))?\s*$', line)
        if char_match and len(char_match.group(1).strip()) > 2:
            cname = char_match.group(1).strip()
            if cname not in ("CUT TO", "FADE TO", "SMASH CUT", "END OF"):
                current_char = cname
                continue
        if current_char and re.match(r'^\s{5,}', line) and stripped and not stripped.startswith('('):
            dialogue[current_char].append(stripped)
            if not line.rstrip().endswith('…'):
                current_char = None
    return dialogue


def build_beat_map(bible):
    """Build scene_id -> beats mapping from story bible."""
    beat_map = {}
    for sc in bible.get("scenes", []):
        sid = sc.get("scene_id", sc.get("id", ""))
        beat_map[sid] = sc.get("beats", [])
    return beat_map


def check_beat_injection(scene_shots, beats):
    """Check if story bible beats are reflected in shot prompts."""
    if not beats:
        return 1.0, []
    results = []
    for i, beat in enumerate(beats):
        desc = beat.get("description", "")
        char_action = beat.get("character_action", "")
        beat_text = (char_action or desc).lower()
        if not beat_text:
            results.append({"beat_idx": i, "covered": True, "note": "empty"})
            continue

        beat_words = set(re.findall(r'\b[a-z]{4,}\b', beat_text))
        beat_words -= {"that", "this", "with", "from", "into", "they", "their", "there",
                       "have", "been", "were", "what", "when", "where", "which", "about",
                       "some", "more", "also", "just", "very", "each", "other", "than",
                       "then", "only", "over", "such", "after", "none", "experiences"}

        if not beat_words:
            results.append({"beat_idx": i, "covered": True, "note": "no significant words"})
            continue

        best_overlap = 0
        best_shot = None
        for s in scene_shots:
            shot_text = " ".join([
                s.get("nano_prompt", ""), s.get("ltx_motion_prompt", ""),
                s.get("description", ""), s.get("dialogue_text", "") or ""
            ]).lower()
            shot_words = set(re.findall(r'\b[a-z]{4,}\b', shot_text))
            overlap = len(beat_words & shot_words)
            ratio = overlap / len(beat_words) if beat_words else 0
            if ratio > best_overlap:
                best_overlap = ratio
                best_shot = s.get("shot_id", "?")

        covered = best_overlap >= 0.3
        results.append({
            "beat_idx": i, "covered": covered, "overlap": best_overlap,
            "best_shot": best_shot, "desc": desc[:80]
        })

    covered_count = sum(1 for r in results if r["covered"])
    return covered_count / len(results) if results else 1.0, results


def run_regression_checks(shots):
    """Run all V21.9 regression invariant checks."""
    issues = {
        "morphing_conflict": [],
        "silent_speaks": [],
        "establishing_dialogue": [],
        "landscape_ltx_empty": [],
        "human_on_characterless": [],
        "generic_none_actions": [],
        "missing_performance_marker": [],
    }

    for s in shots:
        sid = s.get("shot_id", "?")
        nano = s.get("nano_prompt", "")
        ltx = s.get("ltx_motion_prompt", "")
        chars = s.get("characters", [])
        stype = s.get("shot_type", "")
        dlg = s.get("dialogue_text", "") or ""

        if "NO morphing" in ltx and "morphing ENABLED" in ltx:
            issues["morphing_conflict"].append(sid)

        if "SILENT" in ltx and "character speaks:" in ltx:
            issues["silent_speaks"].append(sid)

        if stype == "establishing" and (sid.endswith("_000A") or sid.endswith("_001A")):
            if dlg and len(dlg) > 5:
                issues["establishing_dialogue"].append(sid)

        if not chars and len(ltx.strip()) < 50:
            issues["landscape_ltx_empty"].append(sid)

        if not chars:
            for marker in HUMAN_MARKERS:
                if marker in ltx:
                    issues["human_on_characterless"].append(f"{sid}: '{marker}'")
                    break

        for pattern in GENERIC_NONE_PATTERNS:
            if re.search(pattern, nano):
                issues["generic_none_actions"].append(sid)
                break

        if chars:
            has_marker = any(m in ltx for m in ["character performs:", "character speaks:", "character reacts:"])
            if not has_marker:
                issues["missing_performance_marker"].append(sid)

    return issues


def auto_fix_issues(shots):
    """Auto-fix generic actions and missing markers. Returns fix count."""
    fixes = 0
    for s in shots:
        chars = s.get("characters", [])
        nano = s.get("nano_prompt", "")
        ltx = s.get("ltx_motion_prompt", "")

        # Fix generic "None" actions
        if chars:
            for old, new_tmpl in NONE_REPLACEMENTS.items():
                key = f"Character action: {old}"
                if key in nano:
                    replacement = f"Character action: {new_tmpl.format(char=chars[0])}"
                    s["nano_prompt"] = nano.replace(key, replacement)
                    nano = s["nano_prompt"]
                    fixes += 1
        else:
            for pattern in GENERIC_NONE_PATTERNS:
                if re.search(pattern, nano):
                    s["nano_prompt"] = re.sub(r'Character action:\s*None\s+\w+[^.]*\.?\s*', '', nano)
                    nano = s["nano_prompt"]
                    fixes += 1
                    break

        # Fix missing performance markers
        ltx = s.get("ltx_motion_prompt", "")
        if chars and not any(m in ltx for m in ["character performs:", "character speaks:", "character reacts:"]):
            dlg = s.get("dialogue_text", "") or ""
            ca_match = re.search(r'Character action:\s*([^.]+)', s.get("nano_prompt", ""))
            beat_action = ca_match.group(1).strip() if ca_match else ""

            if dlg:
                marker = f"character speaks: {chars[0]} delivers dialogue"
            elif beat_action and "None" not in beat_action:
                marker = f"character performs: {beat_action}"
            else:
                marker = f"character performs: {chars[0]} present and engaged"

            if "Timing:" in ltx:
                s["ltx_motion_prompt"] = ltx.replace("Timing:", f"{marker}, Timing:")
            else:
                s["ltx_motion_prompt"] = f"{marker}, {ltx}"
            fixes += 1

    return fixes


def analyze_pacing(shots):
    """Analyze duration distribution and prompt quality per scene."""
    scene_shots = defaultdict(list)
    for s in shots:
        scene_shots[s.get("scene_id", "???")].append(s)

    pacing = {}
    for sid, sc_shots in scene_shots.items():
        n = len(sc_shots)
        total_dur = sum(s.get("duration", 0) for s in sc_shots)
        pacing[sid] = {
            "n_shots": n,
            "total_duration": total_dur,
            "avg_duration": total_dur / n if n else 0,
            "n_dialogue": sum(1 for s in sc_shots if s.get("dialogue_text")),
            "dialogue_ratio": sum(1 for s in sc_shots if s.get("dialogue_text")) / n if n else 0,
            "nano_avg": sum(len(s.get("nano_prompt", "")) for s in sc_shots) // n if n else 0,
            "ltx_avg": sum(len(s.get("ltx_motion_prompt", "")) for s in sc_shots) // n if n else 0,
            "types": dict(Counter(s.get("shot_type", "?") for s in sc_shots)),
            "roles": dict(Counter(s.get("coverage_role", "?") for s in sc_shots)),
        }
    return pacing


def generate_report(project, shots, bible, script_text, regressions, pacing, beat_map, do_fix=False):
    """Generate comprehensive audit report."""
    scene_shots = defaultdict(list)
    for s in shots:
        scene_shots[s.get("scene_id", "???")].append(s)

    lines = []
    lines.append("=" * 90)
    lines.append(f"ATLAS SCRIPT FIDELITY AUDIT — {project}")
    lines.append(f"Shots: {len(shots)} | Bible Scenes: {len(bible.get('scenes',[]))} | "
                 f"Beats: {sum(len(b) for b in beat_map.values())}")
    lines.append("=" * 90)

    # Scene-by-scene beat coverage
    lines.append("\nSECTION 1: BEAT COVERAGE BY SCENE")
    lines.append("-" * 60)
    total_beat_cov = []
    for sid in sorted(scene_shots.keys()):
        beats = beat_map.get(sid, [])
        if beats:
            cov, details = check_beat_injection(scene_shots[sid], beats)
            total_beat_cov.append(cov)
            uncovered = [d for d in details if not d["covered"]]
            status = "✅" if cov >= 0.9 else "⚠️" if cov >= 0.7 else "❌"
            lines.append(f"  {status} Scene {sid}: {cov*100:.0f}% ({sum(1 for d in details if d['covered'])}/{len(details)} beats)")
            for ub in uncovered[:2]:
                lines.append(f"      UNCOVERED: {ub.get('desc','')[:60]} (overlap={ub.get('overlap',0):.0%})")

    if total_beat_cov:
        avg_beat = sum(total_beat_cov) / len(total_beat_cov)
        lines.append(f"\n  OVERALL BEAT COVERAGE: {avg_beat*100:.0f}%")

    # Regression checks
    lines.append(f"\nSECTION 2: V21.9 REGRESSION INVARIANTS")
    lines.append("-" * 60)
    all_clean = True
    for name, issue_list in regressions.items():
        status = "✅" if not issue_list else f"❌ {len(issue_list)}"
        if issue_list:
            all_clean = False
        lines.append(f"  {status} {name}")
        for item in issue_list[:3]:
            lines.append(f"      → {item}")

    if all_clean:
        lines.append(f"  ✅ ALL INVARIANTS PASSING")

    # Pacing
    lines.append(f"\nSECTION 3: PACING")
    lines.append("-" * 60)
    total_runtime = sum(p["total_duration"] for p in pacing.values())
    lines.append(f"  Runtime: {total_runtime}s ({total_runtime/60:.1f}min)")
    lines.append(f"  {'Scene':>5} | {'Shots':>5} | {'Dur':>5} | {'Dlg%':>5} | {'Nano':>5} | {'LTX':>4}")
    for sid in sorted(pacing.keys()):
        p = pacing[sid]
        lines.append(f"  {sid:>5} | {p['n_shots']:>5} | {p['total_duration']:>5} | {p['dialogue_ratio']*100:>4.0f}% | {p['nano_avg']:>5} | {p['ltx_avg']:>4}")

    # Prompt quality
    lines.append(f"\nSECTION 4: PROMPT QUALITY")
    lines.append("-" * 60)
    nano_lens = [len(s.get("nano_prompt", "")) for s in shots]
    ltx_lens = [len(s.get("ltx_motion_prompt", "")) for s in shots]
    performs = sum(1 for s in shots if "character performs:" in s.get("ltx_motion_prompt", ""))
    speaks = sum(1 for s in shots if "character speaks:" in s.get("ltx_motion_prompt", ""))
    char_shots = sum(1 for s in shots if s.get("characters"))

    lines.append(f"  Nano: avg={sum(nano_lens)//len(nano_lens)} min={min(nano_lens)} max={max(nano_lens)}")
    lines.append(f"  LTX:  avg={sum(ltx_lens)//len(ltx_lens)} min={min(ltx_lens)} max={max(ltx_lens)}")
    lines.append(f"  Markers: performs={performs} speaks={speaks} char_shots={char_shots}")

    # Story bible divergence warnings
    if script_text:
        lines.append(f"\nSECTION 5: SCRIPT ↔ STORY BIBLE DIVERGENCE WARNINGS")
        lines.append("-" * 60)
        lines.append(f"  ⚠️  ALWAYS review story bible against original screenplay")
        lines.append(f"  ⚠️  LLM story bible expansion can INVENT/CHANGE content")
        lines.append(f"  ⚠️  Common issues: dialogue changes, character placement,")
        lines.append(f"      timeline alterations, scene reordering, prop changes")

    # Auto-fix summary
    if do_fix:
        fix_count = auto_fix_issues(shots)
        lines.append(f"\nSECTION 6: AUTO-FIX RESULTS")
        lines.append("-" * 60)
        lines.append(f"  Applied {fix_count} automatic fixes")
        lines.append(f"  (generic actions replaced, missing markers added)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="ATLAS Script Fidelity Audit")
    parser.add_argument("project", help="Project name (e.g., ravencroft_v17)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues found")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    # Load
    shots, bible, script_text, sp_data, proj_dir = load_project(args.project)
    beat_map = build_beat_map(bible)

    # Auto-fix if requested
    fix_count = 0
    if args.fix:
        fix_count = auto_fix_issues(shots)

    # Analyze
    regressions = run_regression_checks(shots)
    pacing = analyze_pacing(shots)

    if args.json:
        # JSON output for API integration
        scene_shots = defaultdict(list)
        for s in shots:
            scene_shots[s.get("scene_id", "???")].append(s)

        beat_coverage = {}
        for sid in sorted(scene_shots.keys()):
            beats = beat_map.get(sid, [])
            if beats:
                cov, details = check_beat_injection(scene_shots[sid], beats)
                beat_coverage[sid] = {
                    "coverage": round(cov, 3),
                    "total_beats": len(beats),
                    "covered": sum(1 for d in details if d["covered"]),
                    "uncovered": [d for d in details if not d["covered"]]
                }

        result = {
            "project": args.project,
            "total_shots": len(shots),
            "total_beats": sum(len(b) for b in beat_map.values()),
            "beat_coverage": beat_coverage,
            "regressions": {k: len(v) for k, v in regressions.items()},
            "regression_details": regressions,
            "pacing": pacing,
            "prompt_quality": {
                "nano_avg": sum(len(s.get("nano_prompt","")) for s in shots) // len(shots),
                "ltx_avg": sum(len(s.get("ltx_motion_prompt","")) for s in shots) // len(shots),
                "performs": sum(1 for s in shots if "character performs:" in s.get("ltx_motion_prompt","")),
                "speaks": sum(1 for s in shots if "character speaks:" in s.get("ltx_motion_prompt","")),
            },
            "fixes_applied": fix_count,
            "all_clean": all(not v for v in regressions.values()),
        }
        print(json.dumps(result, indent=2))
    else:
        # Text report
        report = generate_report(args.project, shots, bible, script_text, regressions, pacing, beat_map, args.fix)
        print(report)

        # Save report
        report_path = proj_dir / "SCRIPT_FIDELITY_AUDIT.txt"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved: {report_path}")

    # Save fixed shot plan if --fix
    if args.fix and fix_count > 0:
        if isinstance(sp_data, dict):
            sp_data["shots"] = shots
        else:
            sp_data = shots
        tmp = tempfile.NamedTemporaryFile(mode="w", dir=str(proj_dir), suffix=".json", delete=False)
        json.dump(sp_data, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, str(proj_dir / "shot_plan.json"))
        print(f"Shot plan saved with {fix_count} fixes")

    # Exit code: 0 if clean, 1 if issues
    has_issues = any(v for v in regressions.values())
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()
