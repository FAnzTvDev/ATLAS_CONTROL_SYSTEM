#!/usr/bin/env python3
"""
VVO Real-Video Test — V3.0 Two-Tier Upgrade Validation
=======================================================
Tests upgraded video_vision_oversight on ACTUAL generated clips from
victorian_shadows_ep1 Scene 006.

GOOD clips (should PASS):
  - multishot_g1_006_M01.mp4  — Eleanor in kitchen, AUTO_APPROVED (M01 = ESTABLISH arc)
  - multishot_g3_006_M03.mp4  — Nadia reveals journal, AUTO_APPROVED (M03 = PIVOT arc)

BAD clips (should CATCH ISSUES):
  - multishot_g3_006_M03_v364.mp4 — Old M03 before kitchen fix (gray/white void environment)
  - multishot_g4_006_M04_v364.mp4 — Old M04 before kitchen fix (white void)

CHAIN tests:
  - M01 → M02 chain transition (same scene, check continuity)
  - M02 → M03 chain transition (check if environment held)

SCENE STITCH test (if a stitched file exists):
  - Evaluates full scene assembly quality

Usage:
  python3 tools/test_vvo_real.py
  python3 tools/test_vvo_real.py --quick   (frame-based only, no video upload)
  python3 tools/test_vvo_real.py --full    (full video upload to Gemini)
  python3 tools/test_vvo_real.py --chain   (chain transition tests only)
  python3 tools/test_vvo_real.py --stitch  (scene stitch test only)
"""

from __future__ import annotations
import json
import os
import sys
import time
import argparse
from pathlib import Path

# ── ENV LOAD (must happen before importing VVO) ─────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── PATHS ────────────────────────────────────────────────────────────────────
_ROOT   = Path(__file__).parent.parent
_PROJ   = _ROOT / "pipeline_outputs" / "victorian_shadows_ep1"
_VIDEOS = _PROJ / "videos_kling_lite"
_SP     = _PROJ / "shot_plan.json"
_SB     = _PROJ / "story_bible.json"

# Good clips (AUTO_APPROVED)
GOOD_M01 = str(_VIDEOS / "multishot_g1_006_M01.mp4")
GOOD_M02 = str(_VIDEOS / "multishot_g2_006_M02.mp4")
GOOD_M03 = str(_VIDEOS / "multishot_g3_006_M03.mp4")
GOOD_M04 = str(_VIDEOS / "multishot_g4_006_M04.mp4")

# Bad clips (old v364 — before kitchen environment fix)
BAD_M03  = str(_VIDEOS / "multishot_g3_006_M03_v364.mp4")
BAD_M04  = str(_VIDEOS / "multishot_g4_006_M04_v364.mp4")

# ── LOAD SHOT PLAN & STORY BIBLE ─────────────────────────────────────────────
def _load_shot(shot_id: str) -> dict:
    if not _SP.exists():
        return {"shot_id": shot_id}
    sp = json.loads(_SP.read_text())
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    for s in shots:
        if s.get("shot_id") == shot_id:
            return s
    return {"shot_id": shot_id}

def _load_story_bible() -> dict:
    if _SB.exists():
        return json.loads(_SB.read_text())
    return {}

# ── IMPORT VVO ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(_ROOT / "tools"))
sys.path.insert(0, str(_ROOT))
try:
    import video_vision_oversight as vvo
    print(f"✅ VVO imported successfully")
    print(f"   CRITICAL model : {vvo._GEMINI_CRITICAL_MODEL}")
    print(f"   VIDEO model    : {vvo._GEMINI_VIDEO_MODEL}")
    print(f"   FRAME model    : {vvo._GEMINI_FRAME_MODEL}")
    api_key = vvo._get_api_key()
    print(f"   API key present: {'YES (' + api_key[:8] + '...)' if api_key else 'NO — will skip full-video tests'}")
except ImportError as e:
    print(f"❌ VVO import failed: {e}")
    sys.exit(1)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _sep(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")

def _exists(path: str, label: str) -> bool:
    exists = os.path.exists(path)
    size = os.path.getsize(path) // 1024 if exists else 0
    status = f"✅ {size}KB" if exists else "❌ MISSING"
    print(f"  {label}: {status}")
    return exists

def _show_result(label: str, report, t: float) -> None:
    print(f"\n[{label}] ({t:.1f}s)")
    if hasattr(report, "passed"):
        verdict = "✅ PASS" if report.passed else "❌ FAIL"
        print(f"  Overall: {verdict}")
        if report.failure_summary:
            print(f"  Summary: {report.failure_summary[:200]}")
        for r in report.oversight_results:
            flag = "✅" if r.passed else "❌"
            print(f"  [{flag} {r.check}] {r.description[:150]}")
        if hasattr(report, "regen_patch") and report.regen_patch:
            print(f"  Regen patch: {json.dumps(report.regen_patch, indent=2)[:300]}")
    elif isinstance(report, dict):
        if report.get("skipped"):
            print(f"  ⚠️  SKIPPED — {report.get('reason', '?')}")
        else:
            for k, v in report.items():
                if k == "regen_patch":
                    if v:
                        print(f"  regen_patch: {json.dumps(v, indent=2)[:200]}")
                else:
                    print(f"  {k}: {v}")

def _show_full_result(label: str, result: dict, t: float) -> None:
    print(f"\n[{label}] ({t:.1f}s)")
    if result.get("skipped"):
        print(f"  ⚠️  SKIPPED — {result.get('reason', '?')}")
        return
    print(f"  overall_pass      : {result.get('overall_pass', '?')}")
    print(f"  action_completion : {result.get('action_completion', '?')}")
    print(f"  frozen_segment    : {result.get('frozen_segment', '?')}")
    print(f"  dialogue_sync     : {result.get('dialogue_sync', '?')}")
    print(f"  emotional_arc     : {result.get('emotional_arc', '?')}")
    print(f"  char_start_state  : {str(result.get('character_start_state',''))[:100]}")
    print(f"  char_end_state    : {str(result.get('character_end_state',''))[:100]}")
    if result.get("environment_description"):
        print(f"  environment       : {str(result.get('environment_description',''))[:120]}")
    if result.get("failure_notes"):
        print(f"  failure_notes     : {result['failure_notes'][:200]}")
    if result.get("regen_patch"):
        print(f"  regen_patch       : {json.dumps(result['regen_patch'])[:200]}")

def _show_chain_result(label: str, result: dict, t: float) -> None:
    print(f"\n[{label}] ({t:.1f}s)")
    if result.get("skipped"):
        print(f"  ⚠️  SKIPPED — {result.get('reason', '?')}")
        return
    seamless = result.get("seamless", True)
    print(f"  seamless        : {'✅ YES' if seamless else '❌ NO'}")
    print(f"  position_jump   : {result.get('position_jump', False)}")
    print(f"  costume_change  : {result.get('costume_change', False)}")
    print(f"  lighting_shift  : {result.get('lighting_shift', False)}")
    print(f"  spatial_mismatch: {result.get('spatial_mismatch', False)}")
    if result.get("issues"):
        print(f"  issues          : {result['issues']}")
    print(f"  end_state_v1    : {str(result.get('end_state_v1',''))[:120]}")
    print(f"  start_state_v2  : {str(result.get('start_state_v2',''))[:120]}")
    if result.get("notes"):
        print(f"  notes           : {result['notes'][:200]}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST SECTIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_frame_based(story_bible: dict) -> None:
    """Frame-based checks (Tier 2 — fast, no upload)."""
    _sep("TIER 2: FRAME-BASED CHECKS (gemini-2.5-flash, no upload)")

    shots_to_test = [
        ("GOOD 006_M01", GOOD_M01, "006_M01"),
        ("GOOD 006_M03", GOOD_M03, "006_M03"),
        ("BAD  006_M03_v364", BAD_M03,  "006_M03"),
        ("BAD  006_M04_v364", BAD_M04,  "006_M04"),
    ]

    for label, path, shot_id in shots_to_test:
        if not os.path.exists(path):
            print(f"\n  [{label}] ⚠️  FILE MISSING: {path}")
            continue
        shot = _load_shot(shot_id)
        print(f"\nTesting {label}...")
        t0 = time.time()
        report = vvo.run_video_oversight(path, shot, story_bible, use_full_video=False)
        _show_result(label, report, time.time() - t0)


def test_full_video(story_bible: dict) -> None:
    """Full video upload checks (Tier 1 — temporal, uses gemini-2.5-flash per-shot)."""
    _sep("TIER 1: FULL VIDEO ANALYSIS (gemini-2.5-flash, upload to Gemini)")

    shots_to_test = [
        ("GOOD 006_M01 [ESTABLISH arc]", GOOD_M01, "006_M01"),
        ("GOOD 006_M03 [PIVOT arc]",     GOOD_M03, "006_M03"),
        ("BAD  006_M03_v364 [gray void]", BAD_M03, "006_M03"),
        ("BAD  006_M04_v364 [white void]", BAD_M04, "006_M04"),
    ]

    for label, path, shot_id in shots_to_test:
        if not os.path.exists(path):
            print(f"\n  [{label}] ⚠️  FILE MISSING: {path}")
            continue
        shot = _load_shot(shot_id)
        print(f"\nTesting {label} (uploading {os.path.getsize(path)//1024}KB to Gemini)...")
        t0 = time.time()
        result = vvo.analyze_full_video(path, shot, story_bible)
        _show_full_result(label, result, time.time() - t0)


def test_chain_transition(story_bible: dict) -> None:
    """Chain transition checks (Tier 1 CRITICAL — uses gemini-2.5-pro)."""
    _sep("TIER 1 CRITICAL: CHAIN TRANSITIONS (gemini-2.5-pro — narrative reasoning)")

    transitions = [
        ("M01→M02 [kitchen paces → worktable]", GOOD_M01, GOOD_M02, "006_M01", "006_M02"),
        ("M02→M03 [worktable → revelation]",     GOOD_M02, GOOD_M03, "006_M02", "006_M03"),
        ("M03→M04 [revelation → face-off]",      GOOD_M03, GOOD_M04, "006_M03", "006_M04"),
        # Bad chain: old M03 into old M04 — both void, should show lighting_shift/mismatch
        ("BAD M03v364→M04v364 [void→void]",      BAD_M03,  BAD_M04,  "006_M03", "006_M04"),
    ]

    for label, p1, p2, sid1, sid2 in transitions:
        if not os.path.exists(p1) or not os.path.exists(p2):
            print(f"\n  [{label}] ⚠️  Missing one or both files")
            continue
        prev_shot = _load_shot(sid1)
        curr_shot = _load_shot(sid2)
        sz = (os.path.getsize(p1) + os.path.getsize(p2)) // 1024
        print(f"\nTesting {label} (uploading {sz}KB total)...")
        t0 = time.time()
        result = vvo.analyze_chain_transition(p1, p2, prev_shot, curr_shot)
        _show_chain_result(label, result, time.time() - t0)


def test_scene_stitch(story_bible: dict) -> None:
    """Scene stitch check (Tier 1 CRITICAL — uses gemini-2.5-pro on stitched scene)."""
    _sep("TIER 1 CRITICAL: SCENE STITCH (gemini-2.5-pro — narrative arc scoring)")

    # Look for a stitched scene file
    candidates = [
        _VIDEOS.parent / "stitched_scenes" / "scene_006_review.mp4",
        _VIDEOS.parent / "stitched_scenes" / "006_full.mp4",
        _VIDEOS.parent / "scene_006_stitch.mp4",
    ]

    stitched = None
    for c in candidates:
        if c.exists():
            stitched = str(c)
            break

    if not stitched:
        # Stitch on the fly with ffmpeg if all 4 shots exist
        good_clips = [GOOD_M01, GOOD_M02, GOOD_M03, GOOD_M04]
        if all(os.path.exists(c) for c in good_clips):
            import tempfile, subprocess
            print("  No pre-stitched file found — stitching M01..M04 with ffmpeg for test...")
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            concat_txt = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            for c in good_clips:
                concat_txt.write(f"file '{c}'\n")
            concat_txt.flush()
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", concat_txt.name, "-c", "copy", tmp.name,
                   "-loglevel", "error"]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode == 0 and os.path.getsize(tmp.name) > 0:
                stitched = tmp.name
                print(f"  ✅ Stitched to temp file: {os.path.getsize(stitched)//1024}KB")
            else:
                print(f"  ❌ ffmpeg stitch failed: {r.stderr.decode()[:200]}")
                return
        else:
            print("  ⚠️  No stitched file and missing clips — skipping stitch test")
            return

    shots = [_load_shot(f"006_M0{i}") for i in range(1, 5)]
    print(f"\nTesting scene stitch ({os.path.getsize(stitched)//1024}KB)...")
    t0 = time.time()
    result = vvo.analyze_scene_stitch(stitched, shots)
    elapsed = time.time() - t0

    print(f"\n[SCENE STITCH 006 — full narrative assessment] ({elapsed:.1f}s)")
    if result.get("skipped"):
        print(f"  ⚠️  SKIPPED — {result.get('reason', '?')}")
        return
    print(f"  overall_quality   : {result.get('overall_quality', '?')}")
    print(f"  cut_naturalness   : {result.get('cut_naturalness', '?')}")
    print(f"  emotional_arc     : {result.get('emotional_arc', '?')}")
    print(f"  narrative_flow    : {result.get('narrative_flow', '?')}")
    jt = result.get("jarring_transitions", [])
    if jt:
        print(f"  jarring_cuts      : {jt}")
    if result.get("notes"):
        print(f"  notes             : {result['notes'][:400]}")


def test_run_oversight_end_to_end(story_bible: dict, use_full: bool = False) -> None:
    """End-to-end run_video_oversight() — the same function called from the runner."""
    _sep(f"END-TO-END: run_video_oversight() — {'FULL VIDEO' if use_full else 'FRAME-BASED'}")
    print("(This mirrors exactly what atlas_universal_runner.py calls after each video generation)\n")

    shots_to_test = [
        ("GOOD 006_M01", GOOD_M01, "006_M01", True),
        ("GOOD 006_M03", GOOD_M03, "006_M03", True),
        ("BAD  006_M03_v364", BAD_M03, "006_M03", False),
        ("BAD  006_M04_v364", BAD_M04, "006_M04", False),
    ]

    pass_count = fail_count = skip_count = 0
    for label, path, shot_id, should_pass in shots_to_test:
        if not os.path.exists(path):
            print(f"  [{label}] ⚠️  FILE MISSING — skip")
            continue
        shot = _load_shot(shot_id)
        t0 = time.time()
        report = vvo.run_video_oversight(path, shot, story_bible, use_full_video=use_full)
        elapsed = time.time() - t0

        passed = report.passed
        correct = (passed == should_pass)
        result_str = "✅ PASS" if passed else "❌ FAIL"
        correct_str = "✓ CORRECT" if correct else "✗ UNEXPECTED"
        print(f"  {result_str} [{correct_str}] {label} ({elapsed:.1f}s)")
        if not passed:
            if report.failure_summary:
                print(f"    → {report.failure_summary[:180]}")
            for r in report.oversight_results:
                if not r.passed:
                    print(f"    • [{r.check}] {r.description[:120]}")
        if passed:
            pass_count += 1
        else:
            fail_count += 1

    print(f"\n  Results: {pass_count} passed, {fail_count} failed")
    print(f"  (Expected: 2 PASS for good clips, 2 FAIL for bad clips)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="VVO Real-Video Test Suite")
    parser.add_argument("--quick",  action="store_true", help="Frame-based only (fast, no upload)")
    parser.add_argument("--full",   action="store_true", help="Full video upload tests")
    parser.add_argument("--chain",  action="store_true", help="Chain transition tests only")
    parser.add_argument("--stitch", action="store_true", help="Scene stitch test only")
    parser.add_argument("--e2e",    action="store_true", help="End-to-end run_video_oversight test")
    args = parser.parse_args()

    run_all = not any([args.quick, args.full, args.chain, args.stitch, args.e2e])

    print("\n" + "█" * 60)
    print("  VVO V3.0 REAL-VIDEO TEST — victorian_shadows_ep1 Scene 006")
    print("█" * 60)

    # Check file availability
    print("\nChecking test files:")
    _exists(GOOD_M01, "GOOD M01 (AUTO_APPROVED ESTABLISH)")
    _exists(GOOD_M02, "GOOD M02 (AWAITING_APPROVAL)")
    _exists(GOOD_M03, "GOOD M03 (AUTO_APPROVED PIVOT)")
    _exists(GOOD_M04, "GOOD M04 (AWAITING_APPROVAL)")
    _exists(BAD_M03,  "BAD  M03_v364 (old, gray void)")
    _exists(BAD_M04,  "BAD  M04_v364 (old, before fix)")

    story_bible = _load_story_bible()
    sb_status = f"✅ loaded ({len(json.dumps(story_bible))} chars)" if story_bible else "⚠️  not found"
    print(f"\nStory bible: {sb_status}")

    if not vvo._get_api_key():
        print("\n⚠️  WARNING: No GOOGLE_API_KEY — full-video and frame checks needing Gemini will SKIP")
        print("   Frame-based pixel-diff checks will still run.\n")

    if run_all or args.quick:
        test_frame_based(story_bible)

    if (run_all or args.full) and vvo._get_api_key():
        test_full_video(story_bible)

    if (run_all or args.chain) and vvo._get_api_key():
        test_chain_transition(story_bible)

    if (run_all or args.stitch) and vvo._get_api_key():
        test_scene_stitch(story_bible)

    if run_all or args.e2e:
        use_full = bool(vvo._get_api_key())
        test_run_oversight_end_to_end(story_bible, use_full=use_full)

    print("\n" + "═" * 60)
    print("  VVO V3.0 TEST COMPLETE")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
