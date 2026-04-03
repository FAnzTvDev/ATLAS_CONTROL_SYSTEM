#!/usr/bin/env python3
"""
DOCTRINE SCENE PLAN GENERATOR
==============================
Auto-generates scene_plan data from existing shot_plan.json so
EXECUTIVE_LAW_02 can PASS instead of WARN.

Scene plan fields:
  - shot_classes: HERO/CONNECTIVE/ESTABLISHING/BROLL per shot
  - model_tiers: quality tier per shot (hero/production/establishing/broll)
  - peak_shots: shots with highest emotional intensity
  - event_boundaries: scene transitions / act breaks
  - reanchor_positions: shots that reset visual anchor (establishing/wide)

Run: python3 tools/doctrine_scene_plan_generator.py victorian_shadows_ep1
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any


SHOT_CLASS_MAP = {
    # Close-ups = HERO (maximum quality)
    "close_up": "HERO", "MCU": "HERO", "ECU": "HERO",
    "close-up": "HERO", "medium_close_up": "HERO",
    # Medium = CONNECTIVE
    "medium": "CONNECTIVE", "OTS": "CONNECTIVE", "two_shot": "CONNECTIVE",
    "medium_wide": "CONNECTIVE", "over_the_shoulder": "CONNECTIVE",
    # Wide = ESTABLISHING
    "wide": "ESTABLISHING", "establishing": "ESTABLISHING",
    "master": "ESTABLISHING", "extreme_wide": "ESTABLISHING",
    # B-roll/insert = BROLL
    "insert": "BROLL", "detail": "BROLL", "cutaway": "BROLL",
}

MODEL_TIER_MAP = {
    "HERO": "hero",
    "CONNECTIVE": "production",
    "ESTABLISHING": "establishing",
    "BROLL": "broll",
}


def classify_shot(shot: Dict) -> str:
    """Classify shot into HERO/CONNECTIVE/ESTABLISHING/BROLL."""
    shot_type = (shot.get("shot_type") or "medium").lower().replace(" ", "_")

    # Check explicit B-roll markers
    if shot.get("_broll") or shot.get("_no_chain"):
        return "BROLL"

    # Check by shot type
    for key, cls in SHOT_CLASS_MAP.items():
        if key in shot_type:
            return cls

    # Dialogue shots are at minimum CONNECTIVE, often HERO
    if shot.get("dialogue_text") or shot.get("dialogue"):
        chars = shot.get("characters", [])
        if len(chars) == 1:
            return "HERO"  # Single speaker close-up
        return "CONNECTIVE"

    return "CONNECTIVE"  # Default


def detect_peak_shots(shots: List[Dict]) -> List[str]:
    """Find emotionally peak shots — dialogue climaxes, long dialogue, key beats."""
    peaks = []
    for shot in shots:
        dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "")
        if not dialogue:
            continue
        words = len(dialogue.split())
        # Long dialogue = peak moment
        if words > 20:
            peaks.append(shot["shot_id"])
        # Question marks or exclamation = emotional intensity
        elif "?" in dialogue or "!" in dialogue:
            peaks.append(shot["shot_id"])
    return peaks


def detect_reanchor_positions(shots: List[Dict]) -> List[str]:
    """Find shots that reset visual anchor — wide/establishing shots."""
    reanchors = []
    for i, shot in enumerate(shots):
        shot_type = (shot.get("shot_type") or "").lower()
        # First shot is always an anchor
        if i == 0:
            reanchors.append(shot["shot_id"])
        # Wide/establishing shots reset the anchor
        elif "wide" in shot_type or "establishing" in shot_type or "master" in shot_type:
            reanchors.append(shot["shot_id"])
    return reanchors


def detect_event_boundaries(shots: List[Dict]) -> List[str]:
    """Find shots at dramatic transitions — character entrances, topic shifts."""
    boundaries = []
    prev_chars = set()
    for shot in shots:
        chars = set(shot.get("characters", []))
        # Character set change = event boundary
        if chars and chars != prev_chars and prev_chars:
            boundaries.append(shot["shot_id"])
        prev_chars = chars if chars else prev_chars
    return boundaries


def generate_scene_plan(project: str) -> Dict[str, Dict]:
    """Generate scene_plan for all scenes in a project."""
    base = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs") / project
    sp_path = base / "shot_plan.json"

    with open(sp_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])

    # Group by scene
    by_scene: Dict[str, List[Dict]] = {}
    for shot in shots:
        sid = shot.get("scene_id", "unknown")
        by_scene.setdefault(sid, []).append(shot)

    scene_plans = {}
    for scene_id, scene_shots in sorted(by_scene.items()):
        shot_classes = {}
        model_tiers = {}

        for shot in scene_shots:
            cls = classify_shot(shot)
            shot_classes[shot["shot_id"]] = cls
            model_tiers[shot["shot_id"]] = MODEL_TIER_MAP[cls]

        peak_shots = detect_peak_shots(scene_shots)
        event_boundaries = detect_event_boundaries(scene_shots)
        reanchor_positions = detect_reanchor_positions(scene_shots)

        scene_plans[scene_id] = {
            "shot_classes": shot_classes,
            "model_tiers": model_tiers,
            "peak_shots": peak_shots,
            "event_boundaries": event_boundaries,
            "reanchor_positions": reanchor_positions,
            "shot_count": len(scene_shots),
            "hero_count": sum(1 for c in shot_classes.values() if c == "HERO"),
            "connective_count": sum(1 for c in shot_classes.values() if c == "CONNECTIVE"),
            "establishing_count": sum(1 for c in shot_classes.values() if c == "ESTABLISHING"),
            "broll_count": sum(1 for c in shot_classes.values() if c == "BROLL"),
            "_generated_by": "doctrine_scene_plan_generator",
            "_generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        }

    return scene_plans


def save_scene_plans(project: str):
    """Generate and save scene plans to project reports."""
    plans = generate_scene_plan(project)
    base = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs") / project
    out_path = base / "reports" / "doctrine_scene_plans.json"
    os.makedirs(out_path.parent, exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(plans, f, indent=2)

    print(f"Scene plans generated: {out_path}")
    for scene_id, plan in sorted(plans.items()):
        print(f"  Scene {scene_id}: {plan['shot_count']} shots | "
              f"H:{plan['hero_count']} C:{plan['connective_count']} "
              f"E:{plan['establishing_count']} B:{plan['broll_count']} | "
              f"{len(plan['peak_shots'])} peaks, {len(plan['reanchor_positions'])} anchors")

    return plans


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    save_scene_plans(project)
