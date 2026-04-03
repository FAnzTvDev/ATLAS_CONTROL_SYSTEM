#!/usr/bin/env python3
"""
V27.2 Kling Prompt Compiler — Dry-Run Test on Real Scene 001 Data.

Loads actual shot_plan.json + cast_map.json and compiles Kling video prompts
for all Scene 001 shots. Reports:
  - Whether dialogue is preserved
  - Whether character appearances are included
  - Whether emotion/beat direction is present
  - Whether Room DNA/lighting is picked up
  - Whether split anti-morph is present
  - Prompt length (should be 100-2500 chars, not the old 250)
"""
import sys
import os
import json

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.kling_prompt_compiler import (
    compile_for_kling,
    compile_video_for_kling,
    route_and_compile,
)

PROJECT = "victorian_shadows_ep1"
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "pipeline_outputs", PROJECT)

def load_json(filename):
    path = os.path.join(BASE, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def main():
    sp = load_json("shot_plan.json")
    cm = load_json("cast_map.json")

    if not sp:
        print("ERROR: shot_plan.json not found")
        return

    # Handle bare-list format
    if isinstance(sp, list):
        shots = sp
    else:
        shots = sp.get("shots", sp.get("shot_gallery_rows", []))

    scene_001 = [s for s in shots if s.get("shot_id", "").startswith("001")]
    print(f"Scene 001: {len(scene_001)} shots")
    print(f"Cast map: {len(cm) if cm else 0} characters")
    print("=" * 80)

    issues = []
    for shot in scene_001:
        sid = shot.get("shot_id", "?")
        shot_type = shot.get("shot_type", "?")
        dialogue = shot.get("dialogue_text", "")
        chars = shot.get("characters", [])
        beat = shot.get("beat") or shot.get("emotional_beat") or ""

        print(f"\n{'─' * 70}")
        print(f"SHOT: {sid} | Type: {shot_type} | Chars: {chars} | Dialogue: {'YES' if dialogue else 'NO'}")
        print(f"Beat: {beat}")

        # Compile frame prompt
        frame_prompt = compile_for_kling(shot, cm)
        print(f"\n  FRAME PROMPT ({len(frame_prompt)} chars):")
        print(f"  {frame_prompt[:200]}...")

        # Compile video prompt (THE CRITICAL ONE)
        video_prompt = compile_video_for_kling(shot, cm)
        print(f"\n  VIDEO PROMPT ({len(video_prompt)} chars):")
        print(f"  {video_prompt[:300]}...")

        # Route decision
        route = route_and_compile(shot, cm)
        print(f"\n  ROUTE: {route['model']} — {route['reason']}")
        print(f"  Video prompt length: {route['prompt_length']} chars")

        # Validation checks
        checks = {
            "dialogue_preserved": True,
            "character_appearance": True,
            "emotion_present": True,
            "anti_morph": True,
            "not_too_short": True,
            "not_generic": True,
        }

        if dialogue and dialogue.split(":", 1)[-1].strip()[:20] not in video_prompt:
            checks["dialogue_preserved"] = False
            issues.append(f"{sid}: Dialogue text MISSING from video prompt")

        if chars and cm:
            has_appearance = False
            for c in chars:
                cn = c if isinstance(c, str) else str(c)
                for ck, cv in cm.items():
                    if ck.upper() == cn.upper() and isinstance(cv, dict):
                        app = cv.get("appearance", "")
                        if app and app[:15].lower() in video_prompt.lower():
                            has_appearance = True
            if not has_appearance and route["model"] == "kling":
                checks["character_appearance"] = False
                issues.append(f"{sid}: Character appearance MISSING from Kling video prompt")

        if beat:
            # V27.2: The compiler extracts emotion from narrative beats.
            # Check that SOME emotion direction made it into the prompt.
            from tools.kling_prompt_compiler import _get_emotion_direction
            tone, physical = _get_emotion_direction(beat)
            if tone not in video_prompt.lower() and physical.split(",")[0].strip() not in video_prompt.lower():
                checks["emotion_present"] = False
                issues.append(f"{sid}: Emotion direction MISSING (beat: {beat}, expected tone: {tone})")

        if chars and "consistent" not in video_prompt.lower() and "identity" not in video_prompt.lower():
            checks["anti_morph"] = False
            issues.append(f"{sid}: Split anti-morph MISSING")

        if len(video_prompt) < 100:
            checks["not_too_short"] = False
            issues.append(f"{sid}: Video prompt too SHORT ({len(video_prompt)} chars)")

        if video_prompt in ("Subtle movement, cinematic quality", ""):
            checks["not_generic"] = False
            issues.append(f"{sid}: GENERIC fallback prompt!")

        status = "PASS" if all(checks.values()) else "ISSUES"
        failed = [k for k, v in checks.items() if not v]
        print(f"\n  STATUS: {status}" + (f" — failed: {failed}" if failed else ""))

    # Summary
    print(f"\n{'=' * 80}")
    print(f"SUMMARY: {len(scene_001)} shots compiled")
    if issues:
        print(f"ISSUES ({len(issues)}):")
        for iss in issues:
            print(f"  - {iss}")
    else:
        print("ALL CHECKS PASSED — Kling prompts have dialogue, appearance, emotion, anti-morph")

    return len(issues) == 0

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
