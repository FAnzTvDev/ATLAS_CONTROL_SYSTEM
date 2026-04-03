#!/usr/bin/env python3
"""V21.9.1: Apply Authority Gate fixes directly to shot_plan.json.
Strips film stock, camera sensors, duplicate negatives, orphaned NO. etc.
Run after fix-v16 to ensure all prompts are clean.
"""
import json, sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.prompt_authority_gate import _process_prompt, ALWAYS_STRIP, enforce_prompt_authority, load_project_authority_config

project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v17"
base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline_outputs", project)
path = os.path.join(base, "shot_plan.json")

print(f"Loading {path}...")
with open(path) as f:
    data = json.load(f)

shots = data if isinstance(data, list) else data.get("shots", [])

# Load project config for canonical characters
load_project_authority_config(base)

# Phase 1: Process all nano and LTX prompts through the gate
nano_fixed = 0
ltx_fixed = 0
for s in shots:
    if not isinstance(s, dict):
        continue

    sid = s.get("scene_id", s.get("shot_id", "")[:3])
    chars = s.get("characters", [])
    if isinstance(chars, str):
        chars = [c.strip() for c in chars.split(",") if c.strip()]

    # Fix nano
    nano = s.get("nano_prompt", "")
    if nano:
        cleaned = _process_prompt(nano, sid, chars, is_ltx=False)
        if cleaned != nano:
            s["nano_prompt"] = cleaned
            nano_fixed += 1

    # Fix LTX
    ltx = s.get("ltx_motion_prompt", "")
    if ltx:
        cleaned = _process_prompt(ltx, sid, chars, is_ltx=True)
        if cleaned != ltx:
            s["ltx_motion_prompt"] = cleaned
            ltx_fixed += 1

# Save
with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(f"Fixed {nano_fixed} nano prompts, {ltx_fixed} LTX prompts")

# Phase 2: Verify no film stock remains
fuji = 0
red = 0
for s in shots:
    if not isinstance(s, dict):
        continue
    nano = s.get("nano_prompt", "")
    ltx = s.get("ltx_motion_prompt", "")
    if "Fujifilm" in nano or "Fujifilm" in ltx:
        fuji += 1
    if "RED Monstro" in nano or "RED Monstro" in ltx:
        red += 1

print(f"Remaining: Fujifilm={fuji}, RED Monstro={red}")
if fuji == 0 and red == 0:
    print("✅ ALL FILM STOCK STRIPPED — CLEAN")
else:
    print("❌ Film stock still present")
