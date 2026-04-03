"""
ATLAS V37 — Regression Guard
Permanent invariant checks that must pass before any merge or deploy.
Authority: OBSERVE_ONLY (V36 Section 0) — reports violations, never fixes them.
"""
import subprocess, sys, os, json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_RUNNER = _REPO / "atlas_universal_runner.py"

# ── Invariant definitions ──────────────────────────────────────
INVARIANTS = {
    "bible_authority_precedence": {
        "file": "atlas_universal_runner.py",
        "pattern": "_has_bible_aesthetic",
        "description": "Bible atmosphere must override genre DNA"
    },
    "outgoing_reframe_current_shot": {
        "file": "atlas_universal_runner.py",
        "pattern": "REFRAME→",
        "description": "Reframe directives appended to outgoing shot, not incoming"
    },
    "e_shot_independent_default": {
        "file": "atlas_universal_runner.py",
        "pattern": "_independent_start_url",
        "description": "E-shots get independent first frames by default"
    },
    "dialogue_chain_preserved": {
        "file": "atlas_universal_runner.py",
        "pattern": "CHAIN_ANCHOR",
        "description": "First dialogue group anchors the chain"
    },
    "locked_prompt_immutable": {
        "file": "atlas_universal_runner.py",
        "pattern": 'dialogue_text") or s.get("_beat_dialogue")',
        "description": "Dialogue fallback reads both dialogue_text and _beat_dialogue"
    },
    "controller_orchestrator_separation": {
        "file": "tools/failure_heatmap.py",
        "pattern": "OBSERVE_ONLY",
        "description": "Heatmap remains observe-only, never writes production state"
    },
    "missing_cast_halts_prep": {
        "file": "tools/prep_engine.py",
        "pattern": "character_refs",
        "description": "Missing cast reference triggers preflight gate"
    },
    "hybrid_fields_present": {
        "file": "atlas_universal_runner.py",
        "pattern": "_gen_strategy",
        "description": "V36.1 hybrid generation strategy field exists"
    },
    "composition_cache_none_safe": {
        "file": "tools/composition_cache.py",
        "pattern": 'or "")',
        "description": "Composition cache handles None dialogue_text safely"
    },
    "chain_halt_on_failure": {
        "file": "atlas_universal_runner.py",
        "pattern": "CHAIN BROKEN",
        "description": "Chain halts on end-frame extraction failure"
    }
}

def run_preflight(verbose=True):
    """Run all invariant checks. Returns (pass_count, fail_count, results)."""
    results = []
    for name, inv in INVARIANTS.items():
        filepath = _REPO / inv["file"]
        if not filepath.exists():
            results.append({"name": name, "status": "FAIL", "reason": f"File not found: {inv['file']}"})
            continue

        content = filepath.read_text(errors="ignore")
        found = inv["pattern"] in content
        status = "PASS" if found else "FAIL"
        results.append({
            "name": name,
            "status": status,
            "description": inv["description"],
            "pattern": inv["pattern"],
            "file": inv["file"],
            "reason": "" if found else f"Pattern '{inv['pattern']}' not found in {inv['file']}"
        })

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    if verbose:
        print(f"═══ ATLAS V37 REGRESSION GUARD ═══")
        print(f"Invariants: {pass_count} PASS / {fail_count} FAIL / {len(results)} total")
        print()
        for r in results:
            icon = "✅" if r["status"] == "PASS" else "🔴"
            print(f"  {icon} {r['name']}: {r['description']}")
            if r["reason"]:
                print(f"     ↳ {r['reason']}")

        if fail_count > 0:
            print(f"\n🔴 REGRESSION DETECTED — {fail_count} invariant(s) broken")
            print("   DO NOT MERGE until all invariants pass")
        else:
            print(f"\n✅ ALL INVARIANTS HOLD — safe to proceed")

    return pass_count, fail_count, results

if __name__ == "__main__":
    p, f, _ = run_preflight()
    sys.exit(1 if f > 0 else 0)
