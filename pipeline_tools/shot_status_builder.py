#!/usr/bin/env python3
"""Build a consolidated shot-status registry for a scene.

The registry captures hero frame paths, latest video renders, and high-level
approval flags so the orchestration layer can skip already-locked shots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent


def load_manifest(scene_id: str) -> Dict:
    manifest_path = ROOT / "manifests" / f"marcus_scene_{scene_id}_dialogue.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text())


def load_blocking(scene_id: str) -> Dict:
    blocking_path = ROOT / "shared_brain" / "system_status" / f"scene_{scene_id}_blocking.json"
    if blocking_path.exists():
        return json.loads(blocking_path.read_text())

    fallback = ROOT / "REALRUNNER" / f"scene_{scene_id}_blocking.json"
    if fallback.exists():
        return json.loads(fallback.read_text())

    return {"hero_frames": {}}


def detect_videos(scene_id: str) -> Dict[str, str]:
    """Collect latest renders for the scene, checking repo + desktop output dirs."""
    candidates = [
        ROOT / "atlas_output" / "nano_banana",
        ROOT.parent / "atlas_output" / "nano_banana",
    ]

    videos: Dict[str, str] = {}
    for base in candidates:
        if not base.exists():
            continue
        for path in sorted(base.glob(f"{scene_id}_*.mp4")):
            videos[path.stem] = str(path)

    return videos


def build_status(scene_id: str) -> Dict[str, Dict]:
    manifest = load_manifest(scene_id)
    blocking = load_blocking(scene_id)
    hero_frames = blocking.get("hero_frames", {})
    videos = detect_videos(scene_id)

    registry: Dict[str, Dict] = {}
    for shot in manifest.get("shots", []):
        shot_id = shot.get("shot_id")
        hero = hero_frames.get(shot_id)
        video = videos.get(shot_id)

        status = "pending"
        if hero and video:
            status = "approved"
        elif hero or video:
            status = "needs_sync"
        else:
            status = "missing_assets"

        registry[shot_id] = {
            "hero_frame": hero,
            "latest_video": video,
            "status": status,
            "duration": shot.get("duration"),
            "dialogue": shot.get("dialogue", [])
        }

    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate shot status registry")
    parser.add_argument("--scene", default="004", help="Scene identifier, e.g., 004")
    parser.add_argument("--output", default=None, help="Optional path for the registry JSON")
    args = parser.parse_args()

    registry = build_status(args.scene)
    payload = {
        "scene_id": args.scene,
        "shot_status": registry
    }

    output_path = (
        Path(args.output)
        if args.output
        else ROOT / "REALRUNNER" / f"scene_{args.scene}_shot_status.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"💾 Shot status saved to {output_path}")


if __name__ == "__main__":
    main()
