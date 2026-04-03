#!/usr/bin/env python3
"""
HIGGSFIELD BROWSER RUNNER — Victorian Shadows Auto Paste
=========================================================
Uses Claude-in-Chrome MCP to autonomously navigate cloud.higgsfield.ai,
select characters, paste prompts, and fire generations.

This script emits a tab-by-tab action plan that the browser agent executes.
Run this from within a Claude session that has Chrome MCP access.

USAGE:
  python3 higgsfield_browser_runner.py --scene 001 --shot-type all
  python3 higgsfield_browser_runner.py --scene 001 002 003 --batch
"""

import json
import sys
from pathlib import Path
from higgsfield_auto_director import (
    CHARACTERS, LOCATIONS, SCENES,
    build_scene_shot_list, build_higgsfield_prompt,
    OUTPUT_DIR
)


# ─── CHROME MCP ACTION PLAN GENERATOR ────────────────────────────────────────

def generate_tab_action_plan(scene_ids: list[str]) -> list[dict]:
    """
    Generate a structured action plan for Chrome MCP.
    Each action represents one tab operation in Higgsfield Cinema Studio 2.5.
    """
    actions = []
    tab_number = 1

    for scene_id in scene_ids:
        scene = next((s for s in SCENES if s["id"] == scene_id), None)
        if not scene:
            continue

        shots = build_scene_shot_list(scene)

        for i, shot in enumerate(shots):
            job_id = f"{scene_id}_{i+1:02d}"
            soul_tags = [CHARACTERS[c]["soul_id_tag"] for c in shot["characters"] if c in CHARACTERS]
            char_names = shot["characters"]

            action = {
                "tab": tab_number,
                "job_id": job_id,
                "url": "https://cloud.higgsfield.ai/cinema-studio",
                "shot_type": shot["shot_type"],
                "location": shot["location"],
                "characters": char_names,
                "soul_id_tags": soul_tags,
                "duration_seconds": shot["duration"],
                "prompt": shot["prompt"],
                "negative_prompt": shot["negative_prompt"],
                "steps": [
                    {"step": 1, "action": "navigate", "target": "https://cloud.higgsfield.ai/cinema-studio"},
                    {"step": 2, "action": "click", "target": "New Generation button or + button"},
                    {"step": 3, "action": "select_model", "target": "Cinema Studio 2.5"},
                    *([{
                        "step": 4 + idx,
                        "action": "select_soul_id",
                        "target": f"SoulCast / Soul ID selector",
                        "value": soul_tag,
                        "character": char_names[idx] if idx < len(char_names) else "",
                    } for idx, soul_tag in enumerate(soul_tags[:2])]),
                    {
                        "step": 4 + len(soul_tags),
                        "action": "set_duration",
                        "target": "Duration selector",
                        "value": f"{shot['duration']}s",
                    },
                    {
                        "step": 5 + len(soul_tags),
                        "action": "paste_prompt",
                        "target": "Main prompt textarea",
                        "value": shot["prompt"],
                    },
                    {
                        "step": 6 + len(soul_tags),
                        "action": "paste_negative",
                        "target": "Negative prompt textarea",
                        "value": shot["negative_prompt"],
                    },
                    {
                        "step": 7 + len(soul_tags),
                        "action": "click_generate",
                        "target": "Generate button",
                        "note": f"Fires job {job_id} — costs ~{_estimate_credits(shot['duration'])} credits",
                    },
                ],
                "estimated_credits": _estimate_credits(shot["duration"]),
            }
            actions.append(action)
            tab_number += 1

    return actions


def _estimate_credits(duration_s: int) -> int:
    """Rough credit estimate: 5s ≈ 10 credits, 10s ≈ 20 credits."""
    return duration_s * 2


# ─── CLIPBOARD-READY PROMPT SEQUENCE ─────────────────────────────────────────

def generate_clipboard_sequence(scene_ids: list[str]) -> list[dict]:
    """
    Generate a flat sequence of clipboard payloads ready for auto-paste.
    Each entry has what to paste, where to paste it, and what to click.
    """
    sequence = []

    for scene_id in scene_ids:
        scene = next((s for s in SCENES if s["id"] == scene_id), None)
        if not scene:
            continue

        shots = build_scene_shot_list(scene)
        soul_tags = [CHARACTERS[c]["soul_id_tag"] for c in scene["chars"] if c in CHARACTERS]

        for i, shot in enumerate(shots):
            job_id = f"{scene_id}_{i+1:02d}"
            job_soul_tags = [CHARACTERS[c]["soul_id_tag"] for c in shot["characters"] if c in CHARACTERS]

            sequence.append({
                "job_id": job_id,
                "scene": scene_id,
                "shot_number": i + 1,
                "shot_type": shot["shot_type"],
                "location": shot["location"],
                "characters": shot["characters"],
                # What the browser agent needs to do:
                "browser_actions": {
                    "1_navigate": "https://cloud.higgsfield.ai/cinema-studio",
                    "2_soul_ids": job_soul_tags,  # Select these Soul IDs
                    "3_duration": f"{shot['duration']}",
                    "4_prompt_text": shot["prompt"],
                    "5_negative_text": shot["negative_prompt"],
                    "6_click": "GENERATE",
                },
                "credits_estimate": _estimate_credits(shot["duration"]),
            })

    return sequence


# ─── PRINT CHROME MCP INSTRUCTIONS ───────────────────────────────────────────

def print_chrome_instructions(scene_ids: list[str]):
    """
    Print step-by-step instructions optimized for Claude-in-Chrome MCP execution.
    """
    sequence = generate_clipboard_sequence(scene_ids)
    total_credits = sum(j["credits_estimate"] for j in sequence)

    print(f"\n{'='*70}")
    print("CHROME MCP BROWSER AUTOMATION PLAN")
    print(f"Victorian Shadows EP1 — {len(sequence)} shots across {len(scene_ids)} scenes")
    print(f"Estimated credits: ~{total_credits} (varies by plan/model)")
    print(f"{'='*70}\n")

    print("SETUP (do once):")
    print("  1. Open Claude with Chrome MCP connected")
    print("  2. Ensure cloud.higgsfield.ai is loaded and you're logged in")
    print("  3. Have Soul IDs pre-created for Eleanor, Thomas, Nadia, Raymond, Harriet")
    print()

    for job in sequence:
        print(f"─── JOB {job['job_id']}: {job['shot_type'].upper()} ───")
        print(f"Location: {job['location']}")
        print(f"Characters: {', '.join(job['characters']) or 'NONE (empty shot)'}")
        print(f"Soul IDs to select: {', '.join(job['browser_actions']['2_soul_ids']) or 'SKIP'}")
        print(f"Duration: {job['browser_actions']['3_duration']}s")
        print(f"Credits: ~{job['credits_estimate']}")
        print()
        print("PROMPT (paste this):")
        print(job["browser_actions"]["4_prompt_text"])
        print()
        print("NEGATIVE (paste this):")
        print(job["browser_actions"]["5_negative_text"])
        print()
        print("→ CLICK: GENERATE")
        print()


# ─── EXPORT STRUCTURED JSON FOR BROWSER AGENT ────────────────────────────────

def export_browser_plan(scene_ids: list[str]):
    """Export the full browser automation plan as JSON for the Chrome MCP agent."""

    plan = {
        "project": "Victorian Shadows EP1",
        "platform": "cloud.higgsfield.ai",
        "model": "Cinema Studio 2.5",
        "total_jobs": 0,
        "scenes": scene_ids,
        "execution_plan": generate_clipboard_sequence(scene_ids),
        "character_soul_ids": {
            name: data["soul_id_tag"] for name, data in CHARACTERS.items()
        },
        "notes": [
            "Each job = one Cinema Studio generation",
            "Open one tab per job for parallel execution",
            "Soul IDs must be pre-created at cloud.higgsfield.ai/soul-id",
            "API access requires Studio/Enterprise plan",
            "Browser automation fallback for Free/Creator plans",
        ]
    }
    plan["total_jobs"] = len(plan["execution_plan"])

    out_path = OUTPUT_DIR / "browser_automation_plan.json"
    with open(out_path, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"\n✅ Browser automation plan saved: {out_path}")
    print(f"   {plan['total_jobs']} jobs | Ready for Chrome MCP agent")
    return out_path


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", nargs="+", default=["001", "002", "003"])
    parser.add_argument("--mode",  default="export", choices=["export", "print", "both"])
    args = parser.parse_args()

    if args.mode in ("print", "both"):
        print_chrome_instructions(args.scene)

    if args.mode in ("export", "both"):
        export_browser_plan(args.scene)
        plan_path = OUTPUT_DIR / "browser_automation_plan.json"
        with open(plan_path) as f:
            plan = json.load(f)
        print(f"\n📊 Summary:")
        for scene_id in args.scene:
            scene_jobs = [j for j in plan["execution_plan"] if j["scene"] == scene_id]
            credits = sum(j["credits_estimate"] for j in scene_jobs)
            print(f"  Scene {scene_id}: {len(scene_jobs)} shots, ~{credits} credits")
        print(f"  TOTAL: {plan['total_jobs']} shots")
