#!/usr/bin/env python3
"""Generate mock scene clips without hitting external video APIs.

For each shot in the manifest, this tool builds a silent MP4 placeholder using
hero frames (or a fallback colour slate) and records the dialogue/audio notes
so timing can be rehearsed locally.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = "ffmpeg"


def build_mock_clip(out_path: Path, duration: float, hero_frame: Path | None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if hero_frame and hero_frame.exists():
        cmd = [
            FFMPEG,
            "-y",
            "-loop",
            "1",
            "-i",
            str(hero_frame),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ]
    else:
        cmd = [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=1920x1080:d={duration}",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ]

    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create mock scene preview clips")
    parser.add_argument("--scene", default="004", help="Scene identifier, e.g., 004")
    parser.add_argument(
        "--output",
        default=None,
        help="Directory for mock renders (defaults to mock_outputs/<scene>)",
    )
    args = parser.parse_args()

    scene_id = args.scene
    manifest_path = ROOT / "manifests" / f"marcus_scene_{scene_id}_dialogue.json"
    blocking_path = ROOT / "shared_brain" / "system_status" / f"scene_{scene_id}_blocking.json"
    if not blocking_path.exists():
        fallback_blocking = ROOT / "REALRUNNER" / f"scene_{scene_id}_blocking.json"
        blocking_path = fallback_blocking if fallback_blocking.exists() else None

    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    hero_frames = {}
    if blocking_path and blocking_path.exists():
        hero_frames = json.loads(blocking_path.read_text()).get("hero_frames", {})

    output_root = Path(args.output) if args.output else ROOT / "mock_outputs" / scene_id
    output_root.mkdir(parents=True, exist_ok=True)

    registry: Dict[str, Dict] = {}

    for shot in manifest.get("shots", []):
        shot_id = shot.get("shot_id")
        duration = float(shot.get("duration", 6))
        dialogue = shot.get("dialogue", [])
        audio_note = shot.get("audio_note")
        hero_frame = hero_frames.get(shot_id)
        hero_path = Path(hero_frame) if hero_frame else None
        mock_clip = output_root / f"{shot_id}_mock.mp4"

        build_mock_clip(mock_clip, duration, hero_path)

        registry[shot_id] = {
            "mock_clip": str(mock_clip),
            "duration": duration,
            "dialogue": dialogue,
            "audio_note": audio_note,
            "hero_frame": hero_frame,
        }

    (output_root / "scene_registry.json").write_text(json.dumps(registry, indent=2))
    print(f"✅ Mock clips rendered to {output_root}")


if __name__ == "__main__":
    main()
