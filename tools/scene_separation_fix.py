#!/usr/bin/env python3
"""
SCENE SEPARATION FIX — V21
============================
Fixes the narrative grammar issues identified by comparing V9 vs V20/V21:

1. Scene 002: Lawyer intercuts are correctly separated (✅ already done)
   - 002_009A, 002_010A, 002_011R are at LAW OFFICE with LAWYER character
   - Other 002 shots are at CITY APARTMENT with EVELYN

2. Scene 003: Remove V.O. dialogue contamination from bus journey
   - Bus scenes should be VISUAL ONLY (or V.O. reaction shots)
   - Lawyer V.O. lines should NOT generate lawyer on screen
   - Evelyn's reactions to V.O. should show HER face, not blank

3. Shot ordering: Ensure intercuts alternate correctly
   - Evelyn line → Lawyer response → Evelyn reaction (not random order)

4. Scene 003 location: Story bible says "LAW OFFICE" but shots are BUS
   - The story_bible scene location is WRONG — fix it
"""

import json
import os
import re
import sys


def fix_scene_003_vo_contamination(shots):
    """
    Scene 003 (Bus Journey) has LAWYER V.O. dialogue in several shots.
    These shots should NOT show the Lawyer — they should show:
    - Evelyn reacting on the bus (for shots with EVELYN dialogue)
    - Landscape/bus visuals (for V.O. lines from Lawyer)

    This fix:
    1. Removes Lawyer as a visible character in Scene 003
    2. Marks V.O. dialogue as V.O. only (no lip sync for Lawyer)
    3. Ensures Evelyn reaction shots show Evelyn, not empty shots
    """
    fixed = 0
    for shot in shots:
        if not shot.get("shot_id", "").startswith("003"):
            continue

        dlg = shot.get("dialogue_text", "") or shot.get("dialogue", "") or ""
        nano = shot.get("nano_prompt", "")
        ltx = shot.get("ltx_motion_prompt", "")
        chars = shot.get("characters", [])

        # If this shot has LAWYER V.O. dialogue
        if "LAWYER" in dlg and ("V.O." in dlg or "v.o." in dlg.lower()):
            # Remove any Lawyer character reference — Lawyer is V.O. only
            if "LAWYER" in str(chars):
                chars = [c for c in chars if "LAWYER" not in c.upper()]
                shot["characters"] = chars
                fixed += 1

            # If shot has Evelyn's dialogue too, make it a REACTION shot
            if "EVELYN" in dlg:
                if "EVELYN" not in str(chars):
                    chars.append("EVELYN")
                    shot["characters"] = chars

                # Add reaction direction to nano
                if "reaction" not in nano.lower() and "listening" not in nano.lower():
                    reaction_text = "Evelyn listens intently, emotional reaction on her face."
                    shot["nano_prompt"] = nano + " " + reaction_text
                    fixed += 1

            # Mark V.O. in LTX so Lawyer doesn't get lip sync
            if "LAWYER" in dlg and "V.O." not in ltx:
                shot["ltx_motion_prompt"] = ltx + " Voice-over audio only, no lip sync for off-screen character."
                fixed += 1

        # If shot has ONLY Evelyn's dialogue (no V.O.)
        elif "EVELYN" in dlg and "LAWYER" not in dlg:
            # Ensure Evelyn is in characters
            if "EVELYN" not in str(chars):
                chars.append("EVELYN")
                shot["characters"] = chars
                fixed += 1

    return fixed


def fix_scene_002_intercut_order(shots):
    """
    Ensure Scene 002 shots alternate correctly during the phone call:
    - Establishing (Evelyn's apartment)
    - Letter reading (Evelyn)
    - Phone pickup (Evelyn)
    - INTERCUT: Lawyer → Evelyn → Lawyer → Evelyn
    - Final reaction (Evelyn)

    The shots already have correct characters assigned.
    This function validates the order makes narrative sense.
    """
    scene_002 = [s for s in shots if s.get("shot_id", "").startswith("002")]

    # Check that Lawyer shots are interleaved, not clustered
    is_lawyer = ["LAWYER" in str(s.get("characters", [])).upper() for s in scene_002]

    issues = []
    for i in range(len(is_lawyer) - 1):
        # Two consecutive Lawyer shots = bad pacing
        if is_lawyer[i] and is_lawyer[i+1]:
            issues.append(f"Back-to-back Lawyer shots: {scene_002[i].get('shot_id')} and {scene_002[i+1].get('shot_id')}")

    return issues


def fix_scene_003_characters(shots):
    """
    Ensure Scene 003 shots have EVELYN as character when she should be visible.
    Many shots have empty characters[] but show Evelyn on the bus.
    """
    fixed = 0
    for shot in shots:
        if not shot.get("shot_id", "").startswith("003"):
            continue

        chars = shot.get("characters", [])
        nano = shot.get("nano_prompt", "").lower()

        # If nano mentions Evelyn but characters is empty
        if ("evelyn" in nano or "her" in nano or "she" in nano) and not chars:
            # Don't add for pure landscape/establishing shots
            if shot.get("shot_type", "") not in ("establishing", "wide", "extreme_wide"):
                shot["characters"] = ["EVELYN"]
                fixed += 1

    return fixed


def fix_story_bible_scene_003_location(story_bible):
    """
    Story bible says Scene 003 location is "LAW OFFICE" but it should be
    "BUS / COASTAL ROAD". The law office contaminated from Scene 002 merger.
    """
    fixed = False
    for scene in story_bible.get("scenes", []):
        sid = scene.get("scene_id", "")[:3]
        if sid == "003":
            old_loc = scene.get("location", "")
            if "LAW OFFICE" in old_loc.upper() or "OFFICE" in old_loc.upper():
                scene["location"] = "BUS / COASTAL ROAD"
                print(f"  Fixed Scene 003 location: '{old_loc}' → 'BUS / COASTAL ROAD'")
                fixed = True
    return fixed


def add_intercut_markers(shots):
    """
    Add [INTERCUT] markers to shots that alternate between locations.
    This tells the chain pipeline NOT to chain these shots (they're independent).
    """
    marked = 0
    scene_002 = [s for s in shots if s.get("shot_id", "").startswith("002")]

    prev_location = None
    for shot in scene_002:
        chars = shot.get("characters", [])
        is_lawyer = "LAWYER" in str(chars).upper()
        curr_location = "LAW OFFICE" if is_lawyer else "APARTMENT"

        if prev_location and curr_location != prev_location:
            # This is an intercut transition
            if not shot.get("_intercut"):
                shot["_intercut"] = True
                shot["_intercut_from"] = prev_location
                shot["_intercut_to"] = curr_location
                marked += 1

        prev_location = curr_location

    return marked


# ============================================================
# MAIN
# ============================================================

def apply_scene_fixes(project_dir):
    """Apply all scene separation fixes."""

    sp_clean = os.path.join(project_dir, "shot_plan_v21_clean.json")
    sp_enriched = os.path.join(project_dir, "shot_plan_v21_enriched.json")
    sb_path = os.path.join(project_dir, "story_bible.json")

    results = {"clean": {}, "enriched": {}}

    for label, sp_path in [("clean", sp_clean), ("enriched", sp_enriched)]:
        if not os.path.exists(sp_path):
            print(f"  SKIP: {os.path.basename(sp_path)} not found")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(sp_path)}")
        print(f"{'='*60}")

        sp = json.load(open(sp_path))
        shots = sp.get("shots", [])
        target = [s for s in shots if s.get("shot_id", "").split("_")[0] in ("001", "002", "003")]

        print(f"  Total shots: {len(shots)}, Target: {len(target)}")

        # Fix 1: Scene 003 V.O. contamination
        vo_fixed = fix_scene_003_vo_contamination(target)
        print(f"  Scene 003 V.O. fixes: {vo_fixed}")

        # Fix 2: Scene 002 intercut order check
        order_issues = fix_scene_002_intercut_order(target)
        if order_issues:
            for issue in order_issues:
                print(f"  ⚠️ {issue}")
        else:
            print(f"  Scene 002 intercut order: ✅ OK")

        # Fix 3: Scene 003 character assignment
        char_fixed = fix_scene_003_characters(target)
        print(f"  Scene 003 character fixes: {char_fixed}")

        # Fix 4: Add intercut markers
        intercut_marked = add_intercut_markers(target)
        print(f"  Intercut markers added: {intercut_marked}")

        # Save
        with open(sp_path, 'w') as f:
            json.dump(sp, f, indent=2)
        print(f"  Saved: {os.path.basename(sp_path)}")

        results[label] = {
            "vo_fixed": vo_fixed,
            "char_fixed": char_fixed,
            "intercut_marked": intercut_marked,
            "order_issues": order_issues,
        }

    # Fix story bible location
    if os.path.exists(sb_path):
        print(f"\n{'='*60}")
        print("Fixing Story Bible")
        print(f"{'='*60}")
        sb = json.load(open(sb_path))
        loc_fixed = fix_story_bible_scene_003_location(sb)
        if loc_fixed:
            with open(sb_path, 'w') as f:
                json.dump(sb, f, indent=2)
            print(f"  Story bible saved")
        else:
            print(f"  Scene 003 location already correct")

    return results


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/ravencroft_v17"

    print("SCENE SEPARATION FIX — V21")
    print("="*60)
    print(f"Project: {project_dir}")

    results = apply_scene_fixes(project_dir)

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")
