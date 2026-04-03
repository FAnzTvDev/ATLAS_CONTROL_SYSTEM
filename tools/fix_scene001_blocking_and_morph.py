#!/usr/bin/env python3
"""
FIX SCENE 001 — Blocking Direction + Anti-Morph Reinforcement
==============================================================
Three fixes:
1. Character blocking/facing direction per shot (from screenplay staging)
2. LTX anti-morph reinforcement (face identity lock per shot)
3. Scene plan wiring for doctrine compliance

Run: python3 tools/fix_scene001_blocking_and_morph.py
"""
import json
import shutil
import time
import re
from pathlib import Path

PROJECT = "victorian_shadows_ep1"
SP_PATH = f"/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{PROJECT}/shot_plan.json"

# Backup
backup = f"{SP_PATH}.backup_blocking_morph_{int(time.time())}"
shutil.copy2(SP_PATH, backup)
print(f"Backup: {backup}")

with open(SP_PATH) as f:
    sp = json.load(f)

# ============================================================================
# SCENE 001 BLOCKING MAP — from screenplay staging
# Each shot: character positions, facing, eyeline
# ============================================================================
BLOCKING = {
    "001_001A": {
        "type": "establishing",
        "blocking": "wide shot of grand foyer from entrance doorway, morning light streaming through stained glass windows above, dust sheets draped over furniture, dark chandelier hanging from high ceiling",
        "facing": None,  # No characters
        "eyeline": None,
    },
    "001_002B": {
        "type": "medium",
        "blocking": "Eleanor enters through heavy oak doors, stepping forward into the foyer, silhouetted against morning light behind her",
        "facing": "Eleanor faces INTO the room (camera right), three-quarter angle toward camera",
        "eyeline": "Eleanor's eyes scan left to right across the foyer",
    },
    "001_003B": {
        "type": "medium",
        "blocking": "Eleanor walks deeper into foyer, hand reaching out to touch a dust sheet on furniture",
        "facing": "Eleanor faces camera left, moving away from entrance deeper into house",
        "eyeline": "Eleanor looks down at furniture, then up at the chandelier",
    },
    "001_004B": {
        "type": "medium",
        "blocking": "Thomas stands at top of grand staircase looking down, one hand on carved banister, elevated position",
        "facing": "Thomas faces DOWN toward camera from elevated staircase position",
        "eyeline": "Thomas looks down at Eleanor in the foyer below",
    },
    "001_005B": {
        "type": "two_shot",
        "blocking": "Eleanor at bottom of stairs looking up, Thomas at top looking down, vertical separation between them",
        "facing": "Eleanor faces UP and camera-right toward Thomas. Thomas faces DOWN and camera-left toward Eleanor",
        "eyeline": "Eleanor looks up at Thomas. Thomas looks down at Eleanor. Vertical eye-line.",
    },
    "001_006B": {
        "type": "close_up",
        "blocking": "Eleanor in close-up, console table edge visible, she holds documents forward",
        "facing": "Eleanor faces camera-right (toward Thomas off-screen), chin slightly raised",
        "eyeline": "Eleanor's eyes directed camera-right at Thomas, assertive professional gaze",
    },
    "001_007B": {
        "type": "medium",
        "blocking": "Thomas descending staircase, one hand trailing banister, other hand gesturing dismissively at the house",
        "facing": "Thomas faces camera-left and slightly DOWN as he descends stairs toward Eleanor",
        "eyeline": "Thomas looks past Eleanor at the house around them, avoiding direct eye contact",
    },
    "001_008B": {
        "type": "close_up",
        "blocking": "Eleanor walking through foyer, notepad visible, pen moving, glancing sideways at walls",
        "facing": "Eleanor faces camera-left (following Thomas), profile to three-quarter angle",
        "eyeline": "Eleanor's eyes flick between her notepad and the room, cataloguing",
    },
    "001_009B": {
        "type": "two_shot",
        "blocking": "Thomas has stopped and turned to face Eleanor, one hand raised palm-up, other touching wall. Eleanor stands firm facing him",
        "facing": "Thomas faces camera-right toward Eleanor. Eleanor faces camera-left toward Thomas. Confrontational axis.",
        "eyeline": "Direct eye contact between Thomas and Eleanor, tension axis",
    },
    "001_010B": {
        "type": "close_up",
        "blocking": "Eleanor standing firm, documents held against chest like a shield, chin up",
        "facing": "Eleanor faces camera-right toward Thomas (matching 006B eyeline), defiant angle",
        "eyeline": "Eleanor stares directly at Thomas off-screen camera-right, unflinching",
    },
    "001_011C": {
        "type": "close_up",
        "blocking": "Thomas in profile, half his face in shadow, turned away looking toward dark hallway",
        "facing": "Thomas faces camera-LEFT, turned away from Eleanor, profile shot",
        "eyeline": "Thomas looks away from Eleanor into the dark hallway, voice drops",
    },
    "001_012A": {
        "type": "medium",
        "blocking": "Thomas crosses to large painting on wall, reaches toward it then pulls hand back, jaw set with determination",
        "facing": "Thomas faces the painting (camera-right), showing his profile or three-quarter back to camera",
        "eyeline": "Thomas stares at the painting, emotional connection to the past",
    },
}

# ============================================================================
# ANTI-MORPH REINFORCEMENT for LTX
# ============================================================================
ANTI_MORPH = (
    "CRITICAL: face stable throughout entire shot, NO face morphing, NO face warping, "
    "NO facial feature shifting, NO identity drift, maintain exact same face from first "
    "frame to last frame, locked facial structure, consistent bone structure, "
    "NO age shifting, NO gender shifting, NO skin tone change"
)

fixes_blocking = 0
fixes_ltx_morph = 0
fixes_nano_facing = 0

for shot in sp.get("shots", []):
    if shot.get("scene_id") != "001":
        continue
    sid = shot["shot_id"]
    if sid not in BLOCKING:
        continue

    block = BLOCKING[sid]

    # === FIX 1: Inject blocking/facing into nano_prompt ===
    nano = shot.get("nano_prompt", "") or ""

    # Replace generic action with specific blocking
    old_action = re.search(r"Character action:\s*[^.]+\.", nano)
    new_action = f"Character action: {block['blocking']}."
    if block.get("facing"):
        new_action += f" Facing: {block['facing']}."
    if block.get("eyeline"):
        new_action += f" Eyeline: {block['eyeline']}."

    if old_action:
        nano = nano.replace(old_action.group(0), new_action)
        fixes_nano_facing += 1
    else:
        nano = nano.rstrip() + " " + new_action
        fixes_nano_facing += 1

    shot["nano_prompt"] = nano
    if shot.get("nano_prompt_final"):
        nf = shot["nano_prompt_final"]
        old_nf = re.search(r"Character action:\s*[^.]+\.", nf)
        if old_nf:
            shot["nano_prompt_final"] = nf.replace(old_nf.group(0), new_action)

    print(f"[BLOCKING] {sid}: {block['type']} | facing: {(block.get('facing') or 'N/A')[:60]}")

    # === FIX 2: Reinforce anti-morph in LTX ===
    ltx = shot.get("ltx_motion_prompt", "") or ""

    # Check if anti-morph already present
    if "face stable throughout" not in ltx:
        # Find existing "face stable NO morphing" and replace with stronger version
        if "face stable NO morphing" in ltx:
            ltx = ltx.replace("face stable NO morphing", ANTI_MORPH)
            fixes_ltx_morph += 1
        elif "face stable" in ltx:
            ltx = ltx.replace("face stable", ANTI_MORPH)
            fixes_ltx_morph += 1
        else:
            # Inject at start of LTX prompt
            ltx = ANTI_MORPH + ". " + ltx
            fixes_ltx_morph += 1

    shot["ltx_motion_prompt"] = ltx

# Save
with open(SP_PATH, "w") as f:
    json.dump(sp, f, indent=2)

print(f"\nDone:")
print(f"  {fixes_nano_facing} nano prompts updated with blocking/facing/eyeline")
print(f"  {fixes_ltx_morph} LTX prompts reinforced with anti-morph")
print(f"  Shot plan saved")
