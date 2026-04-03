"""
ATLAS V37 — Asset Registry
Registers every generated asset with full metadata. Phase 1: metadata-only logging.
Authority: OBSERVE_ONLY — writes registry, never moves or deletes files.
"""
import json, os, hashlib, time
from pathlib import Path
from datetime import datetime, timezone

_REPO = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO / "pipeline_outputs" / "asset_registry.json"

def _load_registry():
    if _REGISTRY_PATH.exists():
        return json.loads(_REGISTRY_PATH.read_text())
    return {"version": "v37.0", "assets": {}, "created": datetime.now(timezone.utc).isoformat()}

def _save_registry(reg):
    _REGISTRY_PATH.write_text(json.dumps(reg, indent=2, default=str))

def register_asset(asset_path, asset_type, metadata=None):
    """Register an asset with full metadata. Returns asset_id."""
    if metadata is None:
        metadata = {}
    reg = _load_registry()

    path = Path(asset_path)
    asset_id = f"{metadata.get('episode_id', 'unknown')}_{metadata.get('shot_id', path.stem)}_{asset_type}_{int(time.time())}"

    entry = {
        "asset_id": asset_id,
        "asset_type": asset_type,  # first_frame, video_clip, stitch_master, audio
        "file_path": str(path),
        "file_exists": path.exists(),
        "file_size": path.stat().st_size if path.exists() else 0,
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "network_id": metadata.get("network_id", ""),
        "series_id": metadata.get("series_id", ""),
        "episode_id": metadata.get("episode_id", ""),
        "scene_id": metadata.get("scene_id", ""),
        "shot_id": metadata.get("shot_id", ""),
        "characters": metadata.get("characters", []),
        "location_id": metadata.get("location_id", ""),
        "model_used": metadata.get("model_used", ""),
        "generation_strategy": metadata.get("generation_strategy", ""),
        "qc_score": metadata.get("qc_score"),
        "approval_status": metadata.get("approval_status", "PENDING"),
        "publish_status": "NOT_PUBLISHED",
        "storage_tier": "HOT",
        "rights_status": metadata.get("rights_status", "UNREVIEWED"),
    }

    reg["assets"][asset_id] = entry
    _save_registry(reg)
    return asset_id

def get_asset(asset_id):
    reg = _load_registry()
    return reg["assets"].get(asset_id)

def get_assets_by_episode(episode_id):
    reg = _load_registry()
    return [a for a in reg["assets"].values() if a.get("episode_id") == episode_id]

def get_assets_by_series(series_id):
    reg = _load_registry()
    return [a for a in reg["assets"].values() if a.get("series_id") == series_id]

def get_registry_stats():
    reg = _load_registry()
    assets = list(reg["assets"].values())
    return {
        "total_assets": len(assets),
        "by_type": {t: sum(1 for a in assets if a["asset_type"] == t) for t in set(a["asset_type"] for a in assets)} if assets else {},
        "total_size_bytes": sum(a.get("file_size", 0) for a in assets),
        "registry_version": reg.get("version", "unknown")
    }

if __name__ == "__main__":
    stats = get_registry_stats()
    print(f"Asset Registry: {stats['total_assets']} assets, {stats['total_size_bytes'] / 1024 / 1024:.1f} MB")
