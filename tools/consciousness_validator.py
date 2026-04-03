"""
ATLAS V36.2 — CONSCIOUSNESS VALIDATOR
======================================
The final intelligence gate before generation. Validates that the full
consciousness chain is wired for every shot in every scene:

    Story Bible → Opener Classification → Shot Metadata → Frame Prompt → Video Prompt → Chain Strategy

This is the prefrontal cortex's last check: does the system UNDERSTAND
what it's about to generate, or is it about to spend money blindly?

Authority: QA layer (ADVISORY in V36.2, BLOCKING in V37+).
           Returns verdicts only, never mutates shot data.
           Controller reads verdicts and decides whether to proceed.

Usage:
    from tools.consciousness_validator import validate_scene_consciousness, validate_project_consciousness

    # Single scene
    result = validate_scene_consciousness("006", shots, sb_scene, cast_map)
    if not result["pass"]:
        for issue in result["issues"]:
            print(f"  [{issue['severity']}] {issue['layer']}: {issue['message']}")

    # Full project
    report = validate_project_consciousness(project_dir)
    print(report["summary"])
"""

import json
import os
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# CONSCIOUSNESS LAYERS — each validates one link in the chain
# ═══════════════════════════════════════════════════════════════

_COLD_OPEN_TYPES = {"DIALOGUE_OPENER", "COLD_OPEN", "REVELATION_OPENER"}
_NORMAL_OPENER_TYPES = {"ACTION_OPENER", "ATMOSPHERE_OPENER", "BROLL_OPENER"}
_ALL_OPENER_TYPES = _COLD_OPEN_TYPES | _NORMAL_OPENER_TYPES


def _validate_layer_1_story_bible(scene_id: str, sb_scene: dict) -> list:
    """Layer 1: Story Bible — does the scene have narrative intelligence?"""
    issues = []
    if not sb_scene:
        issues.append({
            "layer": "L1_STORY_BIBLE",
            "severity": "BLOCK",
            "message": f"Scene {scene_id}: No story bible entry found. Cannot generate without narrative intelligence.",
            "shot_id": None
        })
        return issues

    beats = sb_scene.get("beats", [])
    if not beats:
        issues.append({
            "layer": "L1_STORY_BIBLE",
            "severity": "BLOCK",
            "message": f"Scene {scene_id}: Story bible has 0 beats. No narrative structure to drive generation.",
            "shot_id": None
        })

    chars = sb_scene.get("characters", [])
    if not chars:
        issues.append({
            "layer": "L1_STORY_BIBLE",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Story bible lists 0 characters. May produce empty-room shots only.",
            "shot_id": None
        })

    location = sb_scene.get("location", "")
    if not location:
        issues.append({
            "layer": "L1_STORY_BIBLE",
            "severity": "WARN",
            "message": f"Scene {scene_id}: No location in story bible. Room DNA will be generic.",
            "shot_id": None
        })

    return issues


def _validate_layer_2_opener(scene_id: str, shots: list, sb_scene: dict) -> list:
    """Layer 2: Opener Classification — does the system know HOW to enter this scene?"""
    issues = []
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]
    if not scene_shots:
        issues.append({
            "layer": "L2_OPENER",
            "severity": "BLOCK",
            "message": f"Scene {scene_id}: No shots found in shot plan.",
            "shot_id": None
        })
        return issues

    # Check opener type exists on at least one shot
    opener_types = set()
    for s in scene_shots:
        ot = s.get("_scene_opener_type") or s.get("_opener_type") or ""
        if ot:
            opener_types.add(ot)

    if not opener_types:
        issues.append({
            "layer": "L2_OPENER",
            "severity": "BLOCK",
            "message": f"Scene {scene_id}: No opener classification on any shot. inject_scene_entry() not run.",
            "shot_id": None
        })
        return issues

    opener_type = list(opener_types)[0]

    if opener_type not in _ALL_OPENER_TYPES:
        issues.append({
            "layer": "L2_OPENER",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Unknown opener type '{opener_type}'. May not trigger correct chain logic.",
            "shot_id": None
        })

    # Validate cold-open consistency with story bible
    beats = sb_scene.get("beats", []) if sb_scene else []
    first_beat_has_dialogue = bool(beats and beats[0].get("dialogue"))

    if opener_type in _COLD_OPEN_TYPES and not first_beat_has_dialogue:
        issues.append({
            "layer": "L2_OPENER",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Classified as {opener_type} but first beat has no dialogue. "
                       f"Cold-open E-shot strip may be incorrect.",
            "shot_id": None
        })

    if opener_type not in _COLD_OPEN_TYPES and first_beat_has_dialogue:
        issues.append({
            "layer": "L2_OPENER",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Classified as {opener_type} but first beat HAS dialogue. "
                       f"Should this be DIALOGUE_OPENER? E-shots may waste money on a cold-open scene.",
            "shot_id": None
        })

    # Check M01 has opener prefix
    m01 = next((s for s in scene_shots if s.get("shot_id", "").endswith("_M01")), None)
    if m01 and opener_type in _COLD_OPEN_TYPES:
        prefix = m01.get("_opener_prefix", "")
        if not prefix:
            issues.append({
                "layer": "L2_OPENER",
                "severity": "WARN",
                "message": f"Scene {scene_id}: M01 has no _opener_prefix. Cold-open frame prompt "
                           f"won't carry 'mid-conversation' directive.",
                "shot_id": m01.get("shot_id")
            })

    return issues


def _validate_layer_3_shot_intelligence(scene_id: str, shots: list, cast_map: dict) -> list:
    """Layer 3: Shot Intelligence — does each shot know WHAT it's generating?"""
    issues = []
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    for s in scene_shots:
        sid = s.get("shot_id", "?")
        is_e_shot = "_E" in sid

        # Beat action — the story-driven verb
        beat_action = s.get("_beat_action", "")
        if not beat_action and not is_e_shot:
            issues.append({
                "layer": "L3_SHOT_INTEL",
                "severity": "WARN",
                "message": f"{sid}: No _beat_action. Prompt will lack story-driven character verb.",
                "shot_id": sid
            })

        # Characters vs cast_map
        chars = s.get("characters") or []
        if chars and cast_map:
            for c in chars:
                cname = c if isinstance(c, str) else c.get("name", "")
                if cname and cname not in cast_map:
                    # Try case-insensitive
                    found = any(k.upper() == cname.upper() for k in cast_map)
                    if not found:
                        issues.append({
                            "layer": "L3_SHOT_INTEL",
                            "severity": "WARN",
                            "message": f"{sid}: Character '{cname}' not in cast_map. Identity injection will fail.",
                            "shot_id": sid
                        })

        # Dialogue shots must have characters
        dialogue = s.get("dialogue_text") or s.get("_beat_dialogue") or ""
        if dialogue and not chars and not is_e_shot:
            issues.append({
                "layer": "L3_SHOT_INTEL",
                "severity": "BLOCK",
                "message": f"{sid}: Has dialogue but 0 characters. FAL will generate a talking void.",
                "shot_id": sid
            })

        # Description exists
        desc = s.get("description") or s.get("nano_prompt") or ""
        if not desc and not beat_action:
            issues.append({
                "layer": "L3_SHOT_INTEL",
                "severity": "BLOCK",
                "message": f"{sid}: No description AND no _beat_action. Nothing to generate from.",
                "shot_id": sid
            })

    return issues


def _validate_layer_4_chain_strategy(scene_id: str, shots: list) -> list:
    """Layer 4: Chain Strategy — is the generation plan coherent?"""
    issues = []
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]
    if not scene_shots:
        return issues

    opener_type = ""
    for s in scene_shots:
        ot = s.get("_scene_opener_type") or s.get("_opener_type") or ""
        if ot:
            opener_type = ot
            break

    is_cold_open = opener_type in _COLD_OPEN_TYPES

    e_shots = [s for s in scene_shots if "_E" in s.get("shot_id", "")]
    m_shots = [s for s in scene_shots if "_M" in s.get("shot_id", "")]

    if is_cold_open and e_shots:
        # E-shots will be stripped at runtime, but their presence in shot_plan is OK
        # (the runner strips them dynamically). Just note it.
        issues.append({
            "layer": "L4_CHAIN",
            "severity": "INFO",
            "message": f"Scene {scene_id}: {opener_type} — {len(e_shots)} E-shots in plan will be "
                       f"stripped at runtime. {len(m_shots)} M-shots will chain.",
            "shot_id": None
        })

    if not is_cold_open and not e_shots and len(m_shots) > 1:
        issues.append({
            "layer": "L4_CHAIN",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Normal opener ({opener_type}) but 0 E-shots in plan. "
                       f"Scene will start abruptly without establishing the space.",
            "shot_id": None
        })

    if not m_shots:
        issues.append({
            "layer": "L4_CHAIN",
            "severity": "BLOCK",
            "message": f"Scene {scene_id}: 0 M-shots (character shots). Nothing to generate.",
            "shot_id": None
        })

    # Check shot ordering makes sense
    shot_ids = [s.get("shot_id", "") for s in scene_shots]
    if shot_ids != sorted(shot_ids):
        issues.append({
            "layer": "L4_CHAIN",
            "severity": "WARN",
            "message": f"Scene {scene_id}: Shots not in sorted order. Chain may produce wrong sequence.",
            "shot_id": None
        })

    return issues


def _validate_layer_5_prompt_readiness(scene_id: str, shots: list) -> list:
    """Layer 5: Prompt Readiness — are the prompts free of contamination?"""
    issues = []
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    _GENERIC_PATTERNS = [
        "experiences the moment", "present and engaged", "natural movement begins",
        "subtle expression", "the scene unfolds", "character reacts naturally",
    ]

    for s in scene_shots:
        sid = s.get("shot_id", "?")
        nano = s.get("nano_prompt") or ""
        desc = s.get("description") or ""
        prompt_text = (nano + " " + desc).lower()

        # Check for generic contamination
        for pattern in _GENERIC_PATTERNS:
            if pattern in prompt_text:
                issues.append({
                    "layer": "L5_PROMPT",
                    "severity": "WARN",
                    "message": f"{sid}: Generic pattern detected: '{pattern}'. CPC should decontaminate at runtime.",
                    "shot_id": sid
                })
                break  # one per shot is enough

        # Check for repetition (corrupted stacked prompts)
        if len(nano) > 90:
            for i in range(0, len(nano) - 30):
                substr = nano[i:i+30]
                if nano.count(substr) >= 3:
                    issues.append({
                        "layer": "L5_PROMPT",
                        "severity": "BLOCK",
                        "message": f"{sid}: Prompt has 3+ repetitions of 30-char substring. Corrupted from stacked enrichment.",
                        "shot_id": sid
                    })
                    break

        # Check for location proper names that FAL renders as text
        _LOCATION_NAMES = ["HARGROVE", "BLACKWOOD", "RAVENCROFT", "ESTATE"]
        for name in _LOCATION_NAMES:
            if name in (nano + " " + desc):
                issues.append({
                    "layer": "L5_PROMPT",
                    "severity": "WARN",
                    "message": f"{sid}: Location proper name '{name}' in prompt. FAL may render as text overlay.",
                    "shot_id": sid
                })
                break

    return issues


def _validate_layer_6_opener_video_consciousness(scene_id: str, shots: list) -> list:
    """Layer 6: Opener → Video Consciousness — will the video prompt carry opener energy?"""
    issues = []
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    opener_type = ""
    opener_energy = ""
    for s in scene_shots:
        ot = s.get("_scene_opener_type") or s.get("_opener_type") or ""
        if ot:
            opener_type = ot
            opener_energy = s.get("_opener_energy", "")
            break

    if not opener_type:
        return issues  # Already caught by Layer 2

    # M01 should have opener_prefix for frame prompt
    m01 = next((s for s in scene_shots if s.get("shot_id", "").endswith("_M01")), None)
    if m01:
        if opener_type in _COLD_OPEN_TYPES:
            prefix = m01.get("_opener_prefix", "")
            if not prefix:
                issues.append({
                    "layer": "L6_VIDEO_CONSCIOUSNESS",
                    "severity": "WARN",
                    "message": f"Scene {scene_id} M01: Cold open but no _opener_prefix. "
                               f"Frame will lack 'mid-conversation' directive.",
                    "shot_id": m01.get("shot_id")
                })

        # opener_energy should exist
        if not opener_energy:
            issues.append({
                "layer": "L6_VIDEO_CONSCIOUSNESS",
                "severity": "INFO",
                "message": f"Scene {scene_id}: No _opener_energy field. Video directive will still fire "
                           f"from _scene_opener_type, but energy context is missing.",
                "shot_id": None
            })

    # Beat atmosphere should exist for at least some shots (mood direction)
    atm_count = sum(1 for s in scene_shots if s.get("_beat_atmosphere"))
    if atm_count == 0:
        issues.append({
            "layer": "L6_VIDEO_CONSCIOUSNESS",
            "severity": "INFO",
            "message": f"Scene {scene_id}: No shots have _beat_atmosphere. Video prompts will lack mood direction.",
            "shot_id": None
        })

    return issues


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def validate_scene_consciousness(
    scene_id: str,
    shots: list,
    sb_scene: Optional[dict] = None,
    cast_map: Optional[dict] = None,
    verbose: bool = True
) -> dict:
    """
    Validate the full consciousness chain for a single scene.

    Returns:
        {
            "scene_id": "006",
            "pass": True/False,
            "issues": [...],
            "summary": "Scene 006: 6 layers validated — 0 BLOCK, 2 WARN, 1 INFO",
            "layers": {
                "L1_STORY_BIBLE": "PASS",
                "L2_OPENER": "PASS",
                ...
            }
        }
    """
    all_issues = []
    all_issues.extend(_validate_layer_1_story_bible(scene_id, sb_scene or {}))
    all_issues.extend(_validate_layer_2_opener(scene_id, shots, sb_scene or {}))
    all_issues.extend(_validate_layer_3_shot_intelligence(scene_id, shots, cast_map or {}))
    all_issues.extend(_validate_layer_4_chain_strategy(scene_id, shots))
    all_issues.extend(_validate_layer_5_prompt_readiness(scene_id, shots))
    all_issues.extend(_validate_layer_6_opener_video_consciousness(scene_id, shots))

    blocks = [i for i in all_issues if i["severity"] == "BLOCK"]
    warns = [i for i in all_issues if i["severity"] == "WARN"]
    infos = [i for i in all_issues if i["severity"] == "INFO"]

    passed = len(blocks) == 0

    # Per-layer status
    layers = {}
    for layer_name in ["L1_STORY_BIBLE", "L2_OPENER", "L3_SHOT_INTEL",
                        "L4_CHAIN", "L5_PROMPT", "L6_VIDEO_CONSCIOUSNESS"]:
        layer_issues = [i for i in all_issues if i["layer"] == layer_name]
        layer_blocks = [i for i in layer_issues if i["severity"] == "BLOCK"]
        if layer_blocks:
            layers[layer_name] = "BLOCK"
        elif [i for i in layer_issues if i["severity"] == "WARN"]:
            layers[layer_name] = "WARN"
        else:
            layers[layer_name] = "PASS"

    opener_type = ""
    for s in shots:
        if s.get("shot_id", "").startswith(f"{scene_id}_"):
            opener_type = s.get("_scene_opener_type") or s.get("_opener_type") or ""
            if opener_type:
                break

    summary = (f"Scene {scene_id} ({opener_type or 'UNKNOWN'}): "
               f"6 layers validated — {len(blocks)} BLOCK, {len(warns)} WARN, {len(infos)} INFO"
               f" → {'PASS' if passed else 'BLOCKED'}")

    if verbose:
        print(f"\n{'═' * 70}")
        print(f"  CONSCIOUSNESS VALIDATOR — Scene {scene_id}")
        print(f"{'═' * 70}")
        print(f"  Opener: {opener_type or 'NOT SET'}")
        print(f"  Verdict: {'✅ PASS' if passed else '🔴 BLOCKED'}")
        print(f"  Issues: {len(blocks)} block, {len(warns)} warn, {len(infos)} info")
        print(f"{'─' * 70}")
        for layer_name, status in layers.items():
            icon = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "🔴")
            print(f"  {icon} {layer_name}: {status}")
        if all_issues:
            print(f"{'─' * 70}")
            for issue in all_issues:
                icon = "🔴" if issue["severity"] == "BLOCK" else ("⚠️" if issue["severity"] == "WARN" else "ℹ️")
                shot_tag = f" [{issue['shot_id']}]" if issue.get("shot_id") else ""
                print(f"  {icon} {issue['layer']}{shot_tag}: {issue['message']}")
        print(f"{'═' * 70}\n")

    return {
        "scene_id": scene_id,
        "pass": passed,
        "issues": all_issues,
        "summary": summary,
        "layers": layers,
        "opener_type": opener_type,
        "block_count": len(blocks),
        "warn_count": len(warns),
        "info_count": len(infos),
    }


def validate_project_consciousness(
    project_dir: str,
    verbose: bool = True
) -> dict:
    """
    Validate consciousness for ALL scenes in a project.
    This is the universal pre-generation intelligence gate.

    Returns:
        {
            "pass": True/False,
            "scenes": {"001": {...}, "002": {...}, ...},
            "summary": "13 scenes: 13 PASS, 0 BLOCKED — consciousness chain intact",
            "total_blocks": 0,
            "total_warns": 5,
        }
    """
    project_path = Path(project_dir)
    sp_path = project_path / "shot_plan.json"
    sb_path = project_path / "story_bible.json"
    cm_path = project_path / "cast_map.json"

    if not sp_path.exists():
        return {"pass": False, "summary": f"shot_plan.json not found at {sp_path}", "scenes": {}}

    with open(sp_path) as f:
        sp = json.load(f)
    shots = sp if isinstance(sp, list) else sp.get("shots", [])

    sb_scenes = []
    if sb_path.exists():
        with open(sb_path) as f:
            sb = json.load(f)
        sb_scenes = sb.get("scenes", [])

    cast_map = {}
    if cm_path.exists():
        with open(cm_path) as f:
            cast_map = json.load(f)

    # Build sb map
    sb_map = {}
    for sc in sb_scenes:
        sid = sc.get("scene_id") or sc.get("scene_number", "")
        sb_map[str(sid).zfill(3)] = sc

    # Get all scene IDs
    scene_ids = sorted(set(s.get("shot_id", "")[:3] for s in shots if s.get("shot_id")))

    if verbose:
        print(f"\n{'╔' + '═' * 68 + '╗'}")
        print(f"{'║'} {'ATLAS V36.2 CONSCIOUSNESS VALIDATOR':^66s} {'║'}")
        print(f"{'║'} {'Story Bible → Opener → Shots → Prompts → Videos → Chain':^66s} {'║'}")
        print(f"{'╚' + '═' * 68 + '╝'}")
        print(f"\n  Project: {project_dir}")
        print(f"  Scenes: {len(scene_ids)} | Shots: {len(shots)} | Cast: {len(cast_map)} characters")
        print(f"  Story Bible: {len(sb_scenes)} scenes")

    results = {}
    total_blocks = 0
    total_warns = 0
    total_infos = 0
    pass_count = 0
    block_count = 0

    for sid in scene_ids:
        sb_scene = sb_map.get(sid)
        result = validate_scene_consciousness(sid, shots, sb_scene, cast_map, verbose=verbose)
        results[sid] = result
        total_blocks += result["block_count"]
        total_warns += result["warn_count"]
        total_infos += result["info_count"]
        if result["pass"]:
            pass_count += 1
        else:
            block_count += 1

    all_pass = block_count == 0
    summary = (f"{len(scene_ids)} scenes: {pass_count} PASS, {block_count} BLOCKED — "
               f"{'consciousness chain intact ✅' if all_pass else 'ISSUES DETECTED 🔴'}")

    if verbose:
        print(f"\n{'═' * 70}")
        print(f"  FINAL VERDICT: {summary}")
        print(f"  Total: {total_blocks} blocks, {total_warns} warnings, {total_infos} info")
        print(f"{'═' * 70}\n")

    return {
        "pass": all_pass,
        "scenes": results,
        "summary": summary,
        "total_blocks": total_blocks,
        "total_warns": total_warns,
        "total_infos": total_infos,
        "scene_count": len(scene_ids),
        "pass_count": pass_count,
        "block_count": block_count,
    }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 tools/consciousness_validator.py <project_dir> [scene_id]")
        print("  Full project: python3 tools/consciousness_validator.py pipeline_outputs/victorian_shadows_ep1")
        print("  Single scene: python3 tools/consciousness_validator.py pipeline_outputs/victorian_shadows_ep1 006")
        sys.exit(1)

    project_dir = sys.argv[1]

    if len(sys.argv) >= 3:
        # Single scene mode
        scene_id = sys.argv[2]
        sp_path = Path(project_dir) / "shot_plan.json"
        sb_path = Path(project_dir) / "story_bible.json"
        cm_path = Path(project_dir) / "cast_map.json"

        with open(sp_path) as f:
            sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])

        sb_scene = None
        if sb_path.exists():
            with open(sb_path) as f:
                sb = json.load(f)
            for sc in sb.get("scenes", []):
                sid = sc.get("scene_id") or sc.get("scene_number", "")
                if str(sid).zfill(3) == scene_id:
                    sb_scene = sc
                    break

        cast_map = {}
        if cm_path.exists():
            with open(cm_path) as f:
                cast_map = json.load(f)

        result = validate_scene_consciousness(scene_id, shots, sb_scene, cast_map)
        sys.exit(0 if result["pass"] else 1)
    else:
        # Full project mode
        report = validate_project_consciousness(project_dir)
        sys.exit(0 if report["pass"] else 1)
