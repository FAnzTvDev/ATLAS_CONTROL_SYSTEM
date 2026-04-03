"""
ATLAS_PROJECT_TRUTH.json Generator
====================================
Creates a single canonical truth object per project that the UI, planner,
controller, and render runner all read from.

This is the #1 mandatory fix from the strategic assessment:
"If the system cannot read from one authoritative truth object, it will keep
inventing state across modules."

The truth object contains:
  - Canonical character refs (resolved, validated paths)
  - Canonical location refs (resolved, validated paths)
  - Shot order + chain order per scene
  - Dialogue ownership (who speaks in each shot)
  - Continuity locks (which shots are chained, what confidence)
  - READY / NOT_READY state per scene

Usage:
    python3 tools/project_truth_generator.py <project_name>

    # Or import:
    from tools.project_truth_generator import generate_project_truth
    truth = generate_project_truth("victorian_shadows_ep1")
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_project_truth(project_name: str) -> dict:
    """Generate the canonical ATLAS_PROJECT_TRUTH.json for a project."""

    project_path = Path(f"pipeline_outputs/{project_name}")
    if not project_path.exists():
        return {"error": f"Project not found: {project_path}"}

    # Load all source files
    sp_path = project_path / "shot_plan.json"
    cm_path = project_path / "cast_map.json"
    sb_path = project_path / "story_bible.json"
    wd_path = project_path / "wardrobe.json"

    shots = []
    cast_map = {}
    story_bible = {}
    wardrobe = {}

    if sp_path.exists():
        with open(sp_path) as f:
            sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])

    if cm_path.exists():
        with open(cm_path) as f:
            cast_map = json.load(f)

    if sb_path.exists():
        with open(sb_path) as f:
            story_bible = json.load(f)

    if wd_path.exists():
        with open(wd_path) as f:
            wardrobe = json.load(f)

    # ═══ BUILD TRUTH OBJECT ═══

    truth = {
        "_version": "V27.5.1",
        "_generated_at": datetime.utcnow().isoformat(),
        "_project": project_name,
        "_source_files": {
            "shot_plan": str(sp_path),
            "cast_map": str(cm_path),
            "story_bible": str(sb_path),
        },
        "characters": {},
        "locations": {},
        "scenes": {},
        "readiness": {},
    }

    # ── 1. CANONICAL CHARACTER REFS ──
    ff_dir = project_path / "first_frames"
    char_lib = project_path / "character_library_locked"

    for char_name, char_data in cast_map.items():
        if char_name.startswith("_"):
            continue

        # Find canonical reference
        ref_url = char_data.get("character_reference_url", "") or ""
        headshot = char_data.get("headshot_url", "") or ""
        appearance = char_data.get("appearance", "") or ""

        # Validate ref exists on disk
        ref_valid = False
        ref_resolved = ""
        for candidate in [ref_url, headshot]:
            if candidate:
                # Extract path from /api/media?path=... or raw path
                raw = candidate.replace("/api/media?path=", "").split("?")[0]
                if os.path.exists(raw):
                    ref_valid = True
                    ref_resolved = raw
                    break

        # Check character_library_locked for CHAR_REFERENCE
        if not ref_valid and char_lib.exists():
            safe_name = char_name.replace(" ", "_").upper()
            for pattern in [f"{safe_name}_CHAR_REFERENCE.jpg", f"{safe_name}_CHAR_REFERENCE.png"]:
                p = char_lib / pattern
                if p.exists():
                    ref_valid = True
                    ref_resolved = str(p)
                    break

        truth["characters"][char_name] = {
            "appearance": appearance,
            "ref_path": ref_resolved,
            "ref_valid": ref_valid,
            "wardrobe": wardrobe.get(char_name, {}),
            "shot_count": sum(1 for s in shots if char_name in [
                c if isinstance(c, str) else c.get("name", "")
                for c in (s.get("characters") or [])
            ]),
        }

    # ── 2. CANONICAL LOCATION REFS ──
    loc_dir = project_path / "location_masters"

    # Extract unique locations from story bible
    sb_scenes = story_bible.get("scenes", [])
    locations = set()
    for sc in sb_scenes:
        loc = sc.get("location", "")
        if loc:
            locations.add(loc)

    for loc_name in sorted(locations):
        # Find location master on disk
        loc_masters = []
        if loc_dir.exists():
            safe = loc_name.replace(" ", "_").replace("/", "_").upper()
            for f in loc_dir.iterdir():
                if safe in f.stem.upper() or loc_name.upper().replace(" ", "_") in f.stem.upper():
                    loc_masters.append(str(f))

        has_base = any("master" in m.lower() and "reverse" not in m.lower() and "medium" not in m.lower() for m in loc_masters) or len(loc_masters) > 0
        has_reverse = any("reverse" in m.lower() for m in loc_masters)
        has_medium = any("medium" in m.lower() for m in loc_masters)

        truth["locations"][loc_name] = {
            "master_paths": loc_masters,
            "has_base_master": has_base,
            "has_reverse_angle": has_reverse,
            "has_medium_interior": has_medium,
            "angle_count": len(loc_masters),
            "ots_ready": has_base and has_reverse,  # Need both for shot/reverse-shot
        }

    # ── 3. SCENES: SHOT ORDER + CHAIN ORDER + DIALOGUE OWNERSHIP ──
    scene_ids = sorted(set(
        s.get("scene_id", s.get("shot_id", "???")[:3]) for s in shots
    ))

    for scene_id in scene_ids:
        scene_shots = [s for s in shots if s.get("scene_id", s.get("shot_id", "???")[:3]) == scene_id]

        # Shot order
        shot_order = [s.get("shot_id") for s in scene_shots]

        # Dialogue ownership
        dialogue_map = {}
        for s in scene_shots:
            dlg = s.get("dialogue_text", "") or ""
            if dlg:
                chars = [c if isinstance(c, str) else c.get("name", "") for c in (s.get("characters") or [])]
                dialogue_map[s.get("shot_id")] = {
                    "speaker": chars[0] if chars else "UNKNOWN",
                    "text": dlg[:100],
                    "characters_present": chars,
                }

        # Chain analysis
        chain_info = []
        for i, s in enumerate(scene_shots):
            chain_from = s.get("chain_source", s.get("_chain_from", ""))
            chain_conf = s.get("chain_confidence", "")
            chain_info.append({
                "shot_id": s.get("shot_id"),
                "chains_from": chain_from,
                "confidence": chain_conf,
            })

        # Readiness check per scene
        issues = []
        char_shots = [s for s in scene_shots if s.get("characters")]
        broll_shots = [s for s in scene_shots if not s.get("characters")]

        # Check: all character shots have nano_prompt
        no_prompt = [s.get("shot_id") for s in scene_shots if not s.get("nano_prompt")]
        if no_prompt:
            issues.append(f"Missing nano_prompt: {no_prompt}")

        # Check: all characters have valid refs
        scene_chars = set()
        for s in scene_shots:
            for c in (s.get("characters") or []):
                name = c if isinstance(c, str) else c.get("name", "")
                scene_chars.add(name)

        for c in scene_chars:
            char_truth = truth["characters"].get(c, {})
            if not char_truth.get("ref_valid"):
                issues.append(f"Invalid/missing ref for {c}")

        # Check: scene has location master
        scene_bible = next((sc for sc in sb_scenes if sc.get("scene_id") == scene_id or str(sc.get("scene_number")) == scene_id), None)
        scene_location = scene_bible.get("location", "") if scene_bible else ""
        loc_truth = truth["locations"].get(scene_location, {})
        if not loc_truth.get("has_base_master"):
            issues.append(f"No location master for '{scene_location}'")

        # Check: dialogue shots have OTS coverage if multi-character
        has_ots = any(s.get("shot_type", "").lower() in ("ots", "over_the_shoulder") for s in scene_shots)
        dialogue_shots = [s for s in scene_shots if s.get("dialogue_text")]
        multi_char_dialogue = [s for s in dialogue_shots if len(s.get("characters", [])) >= 2]
        if multi_char_dialogue and not has_ots and not loc_truth.get("ots_ready"):
            issues.append("Multi-char dialogue but no OTS coverage or reverse angle")

        # Check: first_frames exist
        ff_count = sum(1 for s in scene_shots
                      if (project_path / "first_frames" / f"{s.get('shot_id')}.jpg").exists())

        state = "READY" if not issues else "NOT_READY"

        truth["scenes"][scene_id] = {
            "shot_order": shot_order,
            "shot_count": len(scene_shots),
            "character_shots": len(char_shots),
            "broll_shots": len(broll_shots),
            "dialogue_map": dialogue_map,
            "chain_order": chain_info,
            "location": scene_location,
            "characters": sorted(scene_chars),
            "first_frames_on_disk": ff_count,
            "state": state,
            "issues": issues,
        }

        truth["readiness"][scene_id] = state

    # ── 4. GLOBAL READINESS ──
    ready_scenes = sum(1 for v in truth["readiness"].values() if v == "READY")
    total_scenes = len(truth["readiness"])
    truth["_global_readiness"] = {
        "ready_scenes": ready_scenes,
        "total_scenes": total_scenes,
        "ready_pct": round(ready_scenes / max(total_scenes, 1) * 100, 1),
        "all_ready": ready_scenes == total_scenes,
    }

    # Save
    output_path = project_path / "ATLAS_PROJECT_TRUTH.json"
    with open(output_path, "w") as f:
        json.dump(truth, f, indent=2)

    return truth


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tools/project_truth_generator.py <project_name>")
        sys.exit(1)

    project = sys.argv[1]
    truth = generate_project_truth(project)

    if "error" in truth:
        print(f"ERROR: {truth['error']}")
        sys.exit(1)

    # Summary
    print(f"\nATLAS PROJECT TRUTH — {project}")
    print(f"{'='*50}")
    print(f"Characters: {len(truth['characters'])}")
    for name, data in truth["characters"].items():
        ref_status = "✓" if data["ref_valid"] else "✗"
        print(f"  {ref_status} {name} ({data['shot_count']} shots)")

    print(f"\nLocations: {len(truth['locations'])}")
    for name, data in truth["locations"].items():
        angles = data["angle_count"]
        ots = "OTS-ready" if data["ots_ready"] else "needs reverse"
        print(f"  {name}: {angles} angles ({ots})")

    print(f"\nScenes: {len(truth['scenes'])}")
    for sid, data in truth["scenes"].items():
        state_icon = "✓" if data["state"] == "READY" else "✗"
        ff = data["first_frames_on_disk"]
        total = data["shot_count"]
        print(f"  {state_icon} Scene {sid}: {total} shots, {ff}/{total} frames, {data['state']}")
        if data["issues"]:
            for issue in data["issues"]:
                print(f"    ⚠ {issue}")

    print(f"\nGlobal: {truth['_global_readiness']['ready_scenes']}/{truth['_global_readiness']['total_scenes']} scenes READY ({truth['_global_readiness']['ready_pct']}%)")
    print(f"\nSaved: pipeline_outputs/{project}/ATLAS_PROJECT_TRUTH.json")
