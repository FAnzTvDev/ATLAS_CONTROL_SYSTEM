#!/usr/bin/env python3
"""
Generate ShotSpec JSON files from validated Blackwood beats.

This builder translates human-authored beat metadata into the ShotSpec DSL
so Phase 8.7 rendering inherits narrative intent (lens, blocking, ghost logic,
dialogue, etc.). It skips beats that still look templated, ensuring we never
auto-generate prompts off placeholder prose.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List

# Reuse placeholder heuristic used by the validator.
PLACEHOLDER_PATTERNS = [
    re.compile(r"^Story beat \\d+ for", re.IGNORECASE),
    re.compile(r"^Character actions for beat", re.IGNORECASE),
    re.compile(r"^Story revelation \\d+", re.IGNORECASE),
    re.compile(r"^Beat \\d+", re.IGNORECASE),
]

SHOT_TEMPLATES = [
    {
        "scale": "WS",
        "lens_mm": 24,
        "camera_move": "slow_dolly",
        "motif": "silver_caustics",
        "duration_sec": 8,
        "shot_role": "establishing",
    },
    {
        "scale": "MS",
        "lens_mm": 35,
        "camera_move": "handheld_micro",
        "motif": "highlight_stutter",
        "duration_sec": 6,
        "shot_role": "interaction",
    },
    {
        "scale": "MCU",
        "lens_mm": 85,
        "camera_move": "locked",
        "motif": "fractal_recursion",
        "duration_sec": 6,
        "shot_role": "detail",
    },
]


def _is_placeholder(value: str) -> bool:
    stripped = (value or "").strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in PLACEHOLDER_PATTERNS)


def _compose_prompt(scene: Dict, beat: Dict, template: Dict) -> str:
    setting = scene.get("location", "Interior - Unknown")
    tone = scene.get("tone", "")
    description = beat.get("description", "")
    action = beat.get("character_action", "")
    conflict = beat.get("conflict") or ""
    emotion = beat.get("emotion") or ""
    ghost_logic = beat.get("ghost_logic") or ""

    lines: List[str] = [
        f"{template['shot_role'].capitalize()} {template['scale']} shot inside {setting}.",
        description,
        action,
    ]
    if conflict and not _is_placeholder(conflict):
        lines.append(f"Conflict escalation: {conflict}.")
    if emotion and not _is_placeholder(emotion):
        lines.append(f"Emotional read: {emotion}.")
    if ghost_logic and not _is_placeholder(ghost_logic):
        lines.append(f"Supernatural logic: {ghost_logic}.")
    if tone:
        lines.append(f"Scene tone: {tone}.")

    lines.append(
        "Camera grammar: "
        f"{template['lens_mm']}mm lens, {template['camera_move']} pace, "
        "respect tungsten_cool_split palette, subtle 35mm grain."
    )
    lines.append("No on-screen text or captions.")

    return " ".join(segment.strip() for segment in lines if segment and segment.strip())


def _build_shot_entries(scene: Dict, beat: Dict) -> Iterable[Dict]:
    beat_number = beat.get("beat_number", 0)
    scene_id = scene.get("scene_id", "UNKNOWN_SCENE")
    base_id = f"{scene_id}_B{beat_number:02d}"
    dialogue = beat.get("dialogue") or beat.get("dialogue_text")
    sound_description = beat.get("sound_cue") or beat.get("sound_design") or "ambient creaks, distant wind"
    props = beat.get("props") or ["heirloom rosary", "lantern"]
    blocking = beat.get("blocking") or beat.get("character_action") or ""

    for index, template in enumerate(SHOT_TEMPLATES, start=1):
        shot_id = f"{base_id}_S{index}"
        yield {
            "shot_id": shot_id,
            "beat_ref": beat_number,
            "duration_sec": template["duration_sec"],
            "scale": template["scale"],
            "lens_mm": template["lens_mm"],
            "camera_move": template["camera_move"],
            "motifs": [template["motif"]],
            "lut": "tungsten_cool_split",
            "grain": "subtle_35mm",
            "constraints": {"period_authentic": True, "no_neon": True},
            "blocking": blocking,
            "props": props if isinstance(props, list) else [props],
            "lighting": beat.get("lighting") or scene.get("lighting") or "Candle amber vs cyan moon split",
            "exposure_event": {
                "trigger": beat.get("exposure_trigger") or "candle_flicker",
                "delta_ev": beat.get("exposure_delta", -0.2),
                "hold_sec": beat.get("exposure_hold_sec", 1.0),
            },
            "sound_cues": {
                "type": "diegetic",
                "description": sound_description,
            },
            "dialogue": dialogue if dialogue and not _is_placeholder(str(dialogue)) else None,
            "prompt": _compose_prompt(scene, beat, template),
        }


def _scene_header(scene: Dict) -> Dict:
    return {
        "series": "The Blackwood Estate",
        "scene_id": scene.get("scene_id"),
        "scene_title": scene.get("scene_title"),
        "location": scene.get("location"),
        "time": scene.get("time"),
        "atmosphere": scene.get("tone") or scene.get("scene_purpose"),
    }


def build_shotspec(scene: Dict) -> Dict:
    beats = scene.get("beats") or []
    usable_beats = [
        beat
        for beat in beats
        if not _is_placeholder(beat.get("description", ""))
        and not _is_placeholder(beat.get("character_action", ""))
    ]

    shots: List[Dict] = []
    skipped = []
    for beat in beats:
        if beat not in usable_beats:
            skipped.append(beat.get("beat_number"))
            continue
        shots.extend(_build_shot_entries(scene, beat))

    return {
        "scene": _scene_header(scene),
        "shots": shots,
        "ignored_beats": skipped,
    }


def write_scene_shotspec(output_dir: Path, scene: Dict) -> Path:
    shotspec = build_shotspec(scene)
    scene_id = scene.get("scene_id", "UNKNOWN_SCENE")
    out_path = output_dir / f"{scene_id}_shotspec.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(shotspec, indent=2))
    return out_path


def build_all(manifest_path: Path, output_dir: Path) -> List[Path]:
    manifest = json.loads(manifest_path.read_text())
    scenes = manifest.get("scenes") or []
    generated_paths: List[Path] = []

    for scene in scenes:
        out_path = write_scene_shotspec(output_dir, scene)
        generated_paths.append(out_path)

    return generated_paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate ShotSpec JSON from validated Blackwood beats."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("BLACKWOOD_EPISODE_1_COMPLETE.json"),
        help="Path to the episode manifest JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated_shotspecs"),
        help="Directory where shot spec files will be written.",
    )
    args = parser.parse_args()

    paths = build_all(args.manifest, args.output_dir)
    print(f"Generated {len(paths)} ShotSpec file(s) in {args.output_dir}.")
    for path in paths:
        print(f" - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
