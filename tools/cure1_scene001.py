#!/usr/bin/env python3
"""
CURE 1 — Scene 001 prompt repair for LTX-2.3 baseline test.

Fixes:
- Broken timing formats (0-6.6.6.0s, 0-7.:)
- Generic filler text ("experiences the moment", "key motion: experiences")
- Truncated nano_prompts ("enters the dust")
- Motion timing: dialogue from frame 1 (Law 231)
- No camera brands (Law 235)

Writes backup before modifying.
"""
import json, shutil, os
from datetime import datetime
from pathlib import Path

PROJECT = "victorian_shadows_ep1"
BASE = Path("pipeline_outputs") / PROJECT
SHOT_PLAN = BASE / "shot_plan.json"

# ═══════════════════════════════════════════════════════════════════
# SCENE 001: HARGROVE ESTATE - GRAND FOYER, INT, MORNING
# Characters: ELEANOR VOSS (mid-30s, auburn bun, charcoal blazer)
#             THOMAS BLACKWOOD (60s, silver hair, rumpled navy suit)
# Atmosphere: dust-filtered morning light, faded grandeur, tension
# ═══════════════════════════════════════════════════════════════════

FIXES = {
    "001_001C": {
        "nano_prompt": (
            "Extreme close-up, dust particles floating in morning light "
            "through stained glass windows. Victorian foyer detail — ornate "
            "door handle, dust sheets draped over furniture. Faded grandeur, "
            "professional tension. Desaturated period palette, cool morning tones.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "Slow drift through dust particles catching morning light. "
            "Camera creeps forward through stained glass shadows. "
            "Dust motes swirl in golden beams, furniture shapes "
            "emerge beneath dust sheets. Continuous forward motion, "
            "no cuts. face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_002A": {
        "nano_prompt": (
            "Wide establishing shot, INT. HARGROVE ESTATE grand Victorian foyer. "
            "Morning light streams through tall stained glass windows. "
            "Dust sheets cover furniture, dark chandelier overhead. "
            "Grand staircase with worn carpet, oil paintings on walls. "
            "A briefcase sits on the dusty console table near the entrance. "
            "Desaturated period palette, cool morning tones.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "Slow establishing dolly forward through the grand foyer. "
            "Camera reveals the full space — chandelier, staircase, "
            "dust-covered furniture, stained glass light patterns on floor. "
            "Continuous forward drift, settling on the staircase. "
            "Atmospheric dust particles in light beams. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_003B": {
        "nano_prompt": (
            "Medium close-up, ELEANOR VOSS stands in the Hargrove Estate foyer. "
            "Woman in her mid-30s, auburn hair pulled back in severe bun, "
            "piercing grey-green eyes, charcoal blazer over black turtleneck. "
            "She speaks with professional detachment, eyes scanning the room. "
            "Morning light through stained glass, dust-filtered atmosphere. "
            "Desaturated period palette.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "ELEANOR VOSS speaks directly, jaw set with professional resolve, "
            "delivering dialogue with controlled intensity from the first frame. "
            "character speaks: lips moving naturally, subtle hand gesture toward "
            "the room. Eyes scan the foyer mid-sentence. Camera holds steady on "
            "speaker, slight drift. Continuous speaking performance throughout. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_004C": {
        "nano_prompt": (
            "Close-up, THOMAS BLACKWOOD listens with grief in the foyer. "
            "Man in his early 60s, distinguished silver hair, deep weathered lines, "
            "weary dark eyes, rumpled navy suit. He reacts to Eleanor's words — "
            "jaw tightens, eyes downcast with pain. Morning light on his face. "
            "Desaturated period palette.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "THOMAS BLACKWOOD reacts with visible grief from the first frame. "
            "character reacts: jaw muscle tightens, eyes lower from Eleanor "
            "to the floor, brows pull together. One slow blink of suppressed "
            "emotion. Hand grips the banister rail. Camera holds tight on face, "
            "reading the weight of loss. Continuous reaction, no frozen pause. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_005B": {
        "nano_prompt": (
            "Medium close-up, ELEANOR VOSS at the dusty console table. "
            "Woman in her mid-30s, auburn bun, charcoal blazer. "
            "She pulls a thick folder from her open briefcase, presenting "
            "the financial reality. Professional, unflinching. "
            "Morning light, dust-filtered, faded grandeur. "
            "Desaturated period palette.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "ELEANOR VOSS speaks firmly, holding the folder open as evidence. "
            "character speaks: lips move with precise diction, free hand gestures "
            "at the paperwork. Eyes locked on Thomas with professional insistence. "
            "She taps the folder once for emphasis mid-sentence. Camera holds "
            "steady on speaker with gentle drift. Continuous speaking performance. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_006C": {
        "nano_prompt": (
            "Close-up, THOMAS BLACKWOOD processing the financial blow. "
            "Man in his early 60s, silver hair, weathered face, rumpled navy suit. "
            "He looks away from Eleanor toward the staircase, jaw clenched. "
            "Morning light catches the lines on his face. "
            "Desaturated period palette.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "THOMAS BLACKWOOD turns slowly away from Eleanor, processing the news. "
            "character reacts: head turns toward the staircase, eyes searching "
            "upward for the portrait. Breathing visible in chest movement. "
            "One hand releases the banister and drops to his side. "
            "Camera follows the head turn with subtle pan. "
            "Continuous emotional reaction, no frozen pause. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
    
    "001_007C": {
        "nano_prompt": (
            "Close-up, ELEANOR VOSS watches Thomas gaze at the portrait. "
            "Her professional mask cracks slightly — the faintest recognition "
            "of his pain. Auburn bun, grey-green eyes reflecting morning light. "
            "She speaks the final line about the painting with quiet authority. "
            "Desaturated period palette.\n\n"
            "NO grid, NO collage, NO split screen, NO extra people, "
            "NO morphing faces, NO watermarks, NO text"
        ),
        "ltx_motion_prompt": (
            "ELEANOR VOSS speaks with measured authority, a crack in her composure. "
            "character speaks: lips form the words carefully, eyes shifting "
            "between Thomas and the painting above the staircase. "
            "Subtle swallow before the final statement. Camera holds tight. "
            "Professional mask intact but strain visible in the eyes. "
            "Continuous speaking performance throughout. "
            "face stable NO morphing NO grid NO split screen"
        ),
    },
}

def main():
    # Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = SHOT_PLAN.with_name(f"shot_plan.json.backup_cure1_{ts}")
    shutil.copy2(str(SHOT_PLAN), str(backup))
    print(f"Backup: {backup.name}")
    
    with open(SHOT_PLAN) as f:
        data = json.load(f)
    
    shots = data.get("shots", [])
    fixed = 0
    
    for shot in shots:
        sid = shot.get("shot_id", "")
        if sid in FIXES:
            fix = FIXES[sid]
            
            # Store old values for before/after
            old_nano = shot.get("nano_prompt", "")
            old_ltx = shot.get("ltx_motion_prompt", "")
            
            # Apply fixes
            shot["nano_prompt"] = fix["nano_prompt"]
            shot["nano_prompt_final"] = fix["nano_prompt"]  # Keep in sync
            shot["ltx_motion_prompt"] = fix["ltx_motion_prompt"]
            
            # Mark as CURE1 applied
            shot["_cure1_applied"] = True
            shot["_cure1_timestamp"] = datetime.now().isoformat()
            
            fixed += 1
            print(f"\n{'='*60}")
            print(f"FIXED: {sid}")
            print(f"{'='*60}")
            print(f"OLD nano (first 100): {old_nano[:100]}...")
            print(f"NEW nano (first 100): {fix['nano_prompt'][:100]}...")
            print(f"OLD ltx (first 100):  {old_ltx[:100]}...")
            print(f"NEW ltx (first 100):  {fix['ltx_motion_prompt'][:100]}...")
    
    # Save
    with open(SHOT_PLAN, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"CURE 1 COMPLETE: {fixed}/7 shots fixed")
    print(f"Backup at: {backup.name}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
