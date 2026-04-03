"""
ATLAS V19 Legacy Run Adapter
==============================

Imports V9 (and other legacy) manifests into the V19 run system.
Maps legacy shot IDs, frame paths, and video paths into the UI bundle schema
so they appear in filmstrip and screening room alongside modern runs.

Design:
- Read-only: never modifies legacy files
- Creates a run entry in runs/{project}/
- Maps legacy fields to bundle schema
- Supports V9 manifest format (RAVENCROFT_V9_LTX_MANIFEST.json)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("atlas.v9_legacy_adapter")


# ============================================================================
# V9 MANIFEST → BUNDLE SCHEMA MAPPER
# ============================================================================

def import_v9_manifest(
    manifest_path: Path,
    project_path: Path,
    run_id: str = "v9_legacy",
) -> Dict:
    """
    Import a V9-style manifest into the V19 run system.

    Args:
        manifest_path: Path to V9 manifest JSON
        project_path: Project pipeline_outputs path
        run_id: Run identifier (default: "v9_legacy")

    Returns:
        Dict with run metadata and shot mappings
    """
    manifest_path = Path(manifest_path)
    project_path = Path(project_path)

    if not manifest_path.exists():
        return {"status": "error", "error": f"Manifest not found: {manifest_path}"}

    with open(manifest_path) as f:
        manifest = json.load(f)

    # V9 manifest structure:
    # { scenes: [ { scene_id, narrative_purpose, shots: [ { shot_id, ... } ] } ] }
    scenes = manifest.get("scenes", [])
    if not scenes:
        return {"status": "error", "error": "No scenes in manifest"}

    # Map shots to bundle schema
    bundle_shots = []
    shot_count = 0
    scene_count = 0

    for scene in scenes:
        scene_id = scene.get("scene_id", f"scene_{scene_count}")
        scene_count += 1

        scene_shots = scene.get("shots", [])
        for shot in scene_shots:
            shot_count += 1
            v9_id = shot.get("shot_id", f"shot_{shot_count}")

            # Map V9 fields to bundle schema
            bundle_shot = {
                "shot_id": v9_id,
                "scene_id": scene_id,
                "type": _map_v9_shot_type(shot),
                "duration": shot.get("duration", shot.get("duration_seconds", 6)),
                "duration_seconds": shot.get("duration", shot.get("duration_seconds", 6)),
                "characters": shot.get("characters", []),
                "location": shot.get("location", scene.get("location", "")),
                "nano_prompt": shot.get("prompt", shot.get("nano_prompt", "")),
                "ltx_motion_prompt": shot.get("ltx_motion", shot.get("ltx_motion_prompt", "")),
                "dialogue_text": shot.get("dialogue", ""),
                # V9-specific fields preserved
                "_v9_narrative_purpose": scene.get("narrative_purpose", ""),
                "_v9_continuity_ref": shot.get("continuity_ref", ""),
                "_v9_character_blocking": shot.get("character_blocking", ""),
                "_run_id": run_id,
            }

            # Resolve frame/video paths
            frame_path = _resolve_v9_media(shot, project_path, "frame")
            video_path = _resolve_v9_media(shot, project_path, "video")
            if frame_path:
                bundle_shot["first_frame_url"] = f"/api/media?path={frame_path}"
                bundle_shot["first_frame_path"] = str(frame_path)
            if video_path:
                bundle_shot["video_url"] = f"/api/media?path={video_path}"
                bundle_shot["video_path"] = str(video_path)

            bundle_shots.append(bundle_shot)

    # Create run metadata
    run_meta = {
        "run_id": run_id,
        "run_type": "legacy",
        "source_manifest": str(manifest_path),
        "render_version": "v9",
        "timestamp": datetime.now().isoformat(),
        "shot_count": len(bundle_shots),
        "scene_count": scene_count,
        "character_library": manifest.get("character_library", {}),
    }

    # Save run data
    runs_dir = project_path / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_path = runs_dir / f"{run_id}.json"
    run_data = {
        "metadata": run_meta,
        "shots": bundle_shots,
    }
    with open(run_path, "w") as f:
        json.dump(run_data, f, indent=2)

    logger.info(f"Imported V9 manifest: {len(bundle_shots)} shots, {scene_count} scenes → {run_path}")

    return {
        "status": "success",
        "run_id": run_id,
        "run_path": str(run_path),
        "shot_count": len(bundle_shots),
        "scene_count": scene_count,
        "metadata": run_meta,
    }


def list_runs(project_path: Path) -> List[Dict]:
    """List all available runs for a project."""
    runs_dir = Path(project_path) / "runs"
    if not runs_dir.exists():
        return []

    runs = []
    for run_file in sorted(runs_dir.glob("*.json")):
        try:
            with open(run_file) as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            runs.append({
                "run_id": meta.get("run_id", run_file.stem),
                "run_type": meta.get("run_type", "unknown"),
                "render_version": meta.get("render_version", "?"),
                "timestamp": meta.get("timestamp", ""),
                "shot_count": meta.get("shot_count", len(data.get("shots", []))),
            })
        except Exception:
            continue

    return runs


def get_run_bundle(project_path: Path, run_id: str) -> Optional[Dict]:
    """Get a run's shot data in bundle-compatible format."""
    run_path = Path(project_path) / "runs" / f"{run_id}.json"
    if not run_path.exists():
        return None

    with open(run_path) as f:
        data = json.load(f)

    return data


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _map_v9_shot_type(shot: Dict) -> str:
    """Map V9 shot descriptions to ATLAS shot types."""
    prompt = (shot.get("prompt", "") + " " + shot.get("shot_type", "")).lower()

    if "establishing" in prompt or "exterior" in prompt:
        return "establishing"
    if "close-up" in prompt or "close up" in prompt or "macro" in prompt:
        return "close"
    if "over the shoulder" in prompt or "ots" in prompt:
        return "over_the_shoulder"
    if "wide" in prompt or "24mm" in prompt or "full room" in prompt:
        return "wide"
    if "insert" in prompt or "detail" in prompt:
        return "insert"
    if "reaction" in prompt:
        return "reaction"
    if "two-shot" in prompt or "two shot" in prompt:
        return "two_shot"
    return "medium"  # Default


def _resolve_v9_media(shot: Dict, project_path: Path, media_type: str) -> Optional[Path]:
    """Try to resolve V9 frame/video paths from multiple locations."""
    shot_id = shot.get("shot_id", "")

    if media_type == "frame":
        candidates = [
            project_path / "first_frames" / f"{shot_id}.jpg",
            project_path / "first_frames" / f"{shot_id}.png",
            project_path / "v9_frames" / f"{shot_id}.jpg",
        ]
        # Also check shot's own path reference
        if shot.get("frame_path"):
            candidates.insert(0, Path(shot["frame_path"]))
    else:
        candidates = [
            project_path / "videos" / f"{shot_id}.mp4",
            project_path / "v9_videos" / f"{shot_id}.mp4",
        ]
        if shot.get("video_path"):
            candidates.insert(0, Path(shot["video_path"]))

    for c in candidates:
        if c.exists():
            return c

    return None
