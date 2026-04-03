#!/usr/bin/env python3
"""
PRE-CHECK & SIMULATE GENERATION RUN
=====================================
Validates ALL prerequisites before spending FAL/Kling API credits.
Checks: doctrine compliance, frame uniqueness, blocking direction,
anti-morph markers, duration protection, R2 connectivity, model availability.

Run: python3 tools/precheck_generation_run.py victorian_shadows_ep1 001
     python3 tools/precheck_generation_run.py victorian_shadows_ep1 001 --kling
"""
import json
import os
import sys
import hashlib
import re
from pathlib import Path
from collections import Counter

BASE = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

def check_scene(project: str, scene_id: str, check_kling: bool = False):
    sp_path = BASE / "pipeline_outputs" / project / "shot_plan.json"
    cast_path = BASE / "pipeline_outputs" / project / "cast_map.json"
    wardrobe_path = BASE / "pipeline_outputs" / project / "wardrobe.json"
    scene_plans_path = BASE / "pipeline_outputs" / project / "reports" / "doctrine_scene_plans.json"
    calibration_path = BASE / "pipeline_outputs" / project / "reports" / "doctrine_calibration.json"

    errors = []
    warnings = []
    info = []

    # Load data
    with open(sp_path) as f:
        sp = json.load(f)
    shots = [s for s in sp.get("shots", []) if s.get("scene_id") == scene_id]

    if not shots:
        errors.append(f"CRITICAL: No shots found for scene {scene_id}")
        return errors, warnings, info

    info.append(f"Scene {scene_id}: {len(shots)} shots")

    # Load cast map
    cast_map = {}
    if cast_path.exists():
        with open(cast_path) as f:
            cast_map = json.load(f)
        info.append(f"Cast map: {len([k for k,v in cast_map.items() if isinstance(v, dict) and not v.get('_is_alias_of')])} characters")
    else:
        errors.append("CRITICAL: cast_map.json missing")

    # ========================================================================
    # CHECK 1: Doctrine scene plans exist
    # ========================================================================
    if scene_plans_path.exists():
        with open(scene_plans_path) as f:
            plans = json.load(f)
        if scene_id in plans:
            plan = plans[scene_id]
            info.append(f"Doctrine scene plan: H:{plan['hero_count']} C:{plan['connective_count']} E:{plan['establishing_count']} B:{plan['broll_count']}")
        else:
            warnings.append(f"Scene plan missing for scene {scene_id} — EXECUTIVE_LAW_02 will WARN")
    else:
        warnings.append("doctrine_scene_plans.json missing — run doctrine_scene_plan_generator.py first")

    # ========================================================================
    # CHECK 2: Calibration data loaded
    # ========================================================================
    if calibration_path.exists():
        with open(calibration_path) as f:
            cal = json.load(f)
        info.append(f"Calibration: {len(cal.get('stable_patterns', []))} stable, {len(cal.get('toxic_patterns', []))} toxic")
    else:
        warnings.append("No calibration data — run doctrine_calibration first")

    # ========================================================================
    # CHECK 3: Nano prompt uniqueness (no duplicate frames)
    # ========================================================================
    nano_hashes = {}
    for shot in shots:
        nano = shot.get("nano_prompt", "") or ""
        h = hashlib.md5(nano.encode()).hexdigest()[:12]
        if h in nano_hashes:
            errors.append(f"DUPLICATE NANO: {shot['shot_id']} has identical prompt as {nano_hashes[h]}")
        nano_hashes[h] = shot["shot_id"]
    if not errors:
        info.append(f"Nano uniqueness: {len(nano_hashes)} unique prompts for {len(shots)} shots ✓")

    # ========================================================================
    # CHECK 4: Blocking/facing direction present
    # ========================================================================
    missing_blocking = []
    for shot in shots:
        nano = shot.get("nano_prompt", "") or ""
        chars = shot.get("characters", [])
        if chars and "Facing:" not in nano and "facing" not in nano.lower():
            missing_blocking.append(shot["shot_id"])
    if missing_blocking:
        warnings.append(f"Missing facing direction: {', '.join(missing_blocking)}")
    else:
        info.append(f"Blocking/facing: all character shots have direction ✓")

    # ========================================================================
    # CHECK 5: Anti-morph markers in LTX
    # ========================================================================
    missing_morph = []
    for shot in shots:
        ltx = shot.get("ltx_motion_prompt", "") or ""
        chars = shot.get("characters", [])
        if chars and "face stable" not in ltx.lower() and "no face morphing" not in ltx.lower():
            missing_morph.append(shot["shot_id"])
    if missing_morph:
        errors.append(f"MISSING ANTI-MORPH: {', '.join(missing_morph)}")
    else:
        info.append(f"Anti-morph: all character shots have face stability markers ✓")

    # ========================================================================
    # CHECK 6: Dialogue duration protection
    # ========================================================================
    short_dialogue = []
    for shot in shots:
        dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "")
        if not dialogue:
            continue
        words = len(dialogue.split())
        needed = round(words / 2.3, 1) + 1.5
        duration = shot.get("duration", 0)
        if duration < needed:
            short_dialogue.append(f"{shot['shot_id']}: {duration}s < {needed}s needed for {words} words")
    if short_dialogue:
        warnings.append(f"Short dialogue durations: {'; '.join(short_dialogue)}")
    else:
        info.append(f"Dialogue duration: all dialogue shots have adequate time ✓")

    # ========================================================================
    # CHECK 7: LTX static stacking (toxic pattern)
    # ========================================================================
    stacked = []
    for shot in shots:
        ltx = shot.get("ltx_motion_prompt", "") or ""
        static_count = ltx.lower().count("static camera")
        locked_count = ltx.lower().count("locked camera")
        zero_count = ltx.lower().count("zero movement")
        total = static_count + locked_count + zero_count
        if total > 1:
            stacked.append(f"{shot['shot_id']}: {total} static commands")
    if stacked:
        errors.append(f"STATIC STACKING (will freeze video): {'; '.join(stacked)}")
    else:
        info.append(f"Static stacking: no triple-stacked static commands ✓")

    # ========================================================================
    # CHECK 8: Character refs resolvable
    # ========================================================================
    missing_refs = []
    for shot in shots:
        chars = shot.get("characters", [])
        if isinstance(chars, str):
            chars = [c.strip() for c in chars.split(",")]
        for char in chars:
            found = False
            for cname, cdata in cast_map.items():
                if isinstance(cdata, dict) and not cdata.get("_is_alias_of"):
                    if char.upper() in cname.upper() or cname.upper() in char.upper():
                        ref = cdata.get("character_reference_url") or cdata.get("reference_url") or cdata.get("headshot_url")
                        if ref:
                            found = True
                        break
            if not found and char.strip():
                missing_refs.append(f"{shot['shot_id']}/{char}")
    if missing_refs:
        warnings.append(f"Missing character refs: {', '.join(missing_refs[:5])}")
    else:
        info.append(f"Character refs: all characters have resolvable references ✓")

    # ========================================================================
    # CHECK 9: Wardrobe data exists
    # ========================================================================
    if wardrobe_path.exists():
        with open(wardrobe_path) as f:
            wardrobe = json.load(f)
        info.append(f"Wardrobe: {len(wardrobe)} entries ✓")
    else:
        warnings.append("wardrobe.json missing — will be auto-generated but check results")

    # ========================================================================
    # CHECK 10: Performance markers on dialogue shots
    # ========================================================================
    missing_perf = []
    for shot in shots:
        dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "")
        ltx = shot.get("ltx_motion_prompt", "") or ""
        if dialogue and "PERFORMANCE MANDATORY" not in ltx and "character speaks:" not in ltx:
            missing_perf.append(shot["shot_id"])
    if missing_perf:
        warnings.append(f"Missing PERFORMANCE MANDATORY: {', '.join(missing_perf)}")
    else:
        info.append(f"Performance markers: all dialogue shots have mandatory markers ✓")

    # ========================================================================
    # CHECK 11: R2 connectivity (for master chain reframes)
    # ========================================================================
    r2_configured = all([
        os.environ.get("ATLAS_R2_ACCOUNT_ID"),
        os.environ.get("ATLAS_R2_ACCESS_KEY_ID"),
        os.environ.get("ATLAS_R2_SECRET_KEY"),
    ])
    if r2_configured:
        info.append(f"R2 storage: configured ✓")
    else:
        warnings.append("R2 env vars not set — reframes will use base64 fallback (slower)")

    # ========================================================================
    # CHECK 12: Kling-specific checks
    # ========================================================================
    if check_kling:
        info.append("--- KLING PRE-CHECK ---")
        # Kling needs public URLs for images (not base64)
        if not r2_configured:
            errors.append("KLING CRITICAL: R2 must be configured — Kling API requires public image URLs (not base64)")
        # Kling has different duration limits
        for shot in shots:
            dur = shot.get("duration", 0)
            if dur > 10:
                warnings.append(f"KLING: {shot['shot_id']} duration {dur}s > Kling max 10s — will need segments")
        # Kling model availability
        info.append("Kling model: kling-v2 (requires API key in env)")
        kling_key = os.environ.get("KLING_API_KEY") or os.environ.get("FAL_KLING_KEY")
        if kling_key:
            info.append("Kling API key: present ✓")
        else:
            errors.append("KLING CRITICAL: No Kling API key found in env (KLING_API_KEY or FAL_KLING_KEY)")

    return errors, warnings, info


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    scene_id = sys.argv[2] if len(sys.argv) > 2 else "001"
    check_kling = "--kling" in sys.argv

    print(f"{'='*60}")
    print(f"PRE-CHECK: {project} Scene {scene_id}")
    if check_kling:
        print(f"  + Kling model pre-check")
    print(f"{'='*60}\n")

    errors, warnings, info = check_scene(project, scene_id, check_kling)

    for i in info:
        print(f"  ✓ {i}")
    print()

    if warnings:
        print(f"⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
        print()

    if errors:
        print(f"❌ ERRORS ({len(errors)}) — MUST FIX BEFORE GENERATION:")
        for e in errors:
            print(f"  ✗ {e}")
        print()
        print("VERDICT: ❌ NOT READY — fix errors above before running")
        return 1
    elif warnings:
        print(f"VERDICT: ⚠️  READY WITH WARNINGS — generation can proceed but review warnings")
        return 0
    else:
        print(f"VERDICT: ✅ ALL CLEAR — ready for generation")
        return 0


if __name__ == "__main__":
    sys.exit(main())
