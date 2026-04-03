#!/usr/bin/env python3
"""
tools/validate_freeze.py
========================

One-command validation harness for Codex Window D.
Pings the running server, uploads a sample script, verifies manifests,
and ensures project-scoped asset isolation.

V15.1: Auto-switches to LAB mode for validation, then returns to PROD.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_OUTPUTS = REPO_ROOT / "pipeline_outputs"
DEFAULT_SCRIPT = REPO_ROOT / "test_scripts" / "atlanta_nightmare_2026.fountain"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ATLAS Freeze Validation Harness")
    parser.add_argument("--base-url", default="http://localhost:9999", help="Atlas server base URL")
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT, help="Script to upload for validation")
    parser.add_argument("--runtime", default="5min", help="Runtime label for upload")
    parser.add_argument("--genre", default="gothic_horror", help="Genre label for upload")
    parser.add_argument("--tolerance", type=float, default=0.10, help="Runtime variance tolerance (fraction)")
    parser.add_argument("--no-auto-mode", action="store_true", help="Don't auto-switch to LAB mode")
    return parser.parse_args()


def add_check(checks: List[Dict[str, Any]], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def get_freeze_status(session: requests.Session, base_url: str) -> Dict[str, Any]:
    """Get current freeze lock status."""
    try:
        resp = session.get(f"{base_url}/health/freeze", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"locked": False, "mode": "UNKNOWN"}


def set_freeze_mode(session: requests.Session, base_url: str, mode: str) -> bool:
    """Set freeze mode (LAB or PROD). Returns True on success."""
    try:
        resp = session.post(
            f"{base_url}/health/freeze/mode",
            json={"mode": mode},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("success", False)
    except Exception as e:
        print(f"Warning: Could not set freeze mode: {e}", file=sys.stderr)
    return False


def ensure_health(session: requests.Session, base_url: str, checks: List[Dict[str, Any]]) -> None:
    resp = session.get(f"{base_url}/health", timeout=10)
    ok = resp.status_code == 200
    add_check(checks, "health_endpoint", ok, f"status_code={resp.status_code}")
    resp.raise_for_status()


def upload_script(session: requests.Session, base_url: str, script_path: Path, runtime: str, genre: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    files = {
        "file": (script_path.name, script_path.read_bytes(), "text/plain")
    }
    data = {
        "project_name": script_path.stem,
        "runtime": runtime,
        "genre": genre,
        "generate_assets": "false"
    }
    start = time.time()
    resp = session.post(f"{base_url}/api/v15/script/import-and-validate", files=files, data=data, timeout=600)
    elapsed = int((time.time() - start) * 1000)
    add_check(checks, "script_upload_request", resp.status_code == 200, f"{elapsed}ms")
    resp.raise_for_status()
    payload = resp.json()
    status_ok = payload.get("status") in {"success", "needs_attention"}
    add_check(checks, "script_upload_status", status_ok, payload.get("status", "unknown"))
    return payload


def load_manifest(project_slug: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    manifest_path = PIPELINE_OUTPUTS / project_slug / "dry_run_manifest.json"
    exists = manifest_path.exists()
    add_check(checks, "manifest_exists", exists, str(manifest_path))
    if not exists:
        raise FileNotFoundError(f"Manifest missing for project: {project_slug}")
    data = json.loads(manifest_path.read_text())
    add_check(checks, "manifest_hash_present", "_manifest_hash" in data, data.get("_manifest_hash", "missing"))
    return data


def validate_manifest(manifest: Dict[str, Any], tolerance: float, checks: List[Dict[str, Any]]) -> None:
    scenes = manifest.get("scene_manifest", [])
    shots = manifest.get("shot_manifest", [])
    entities = manifest.get("entity_manifest", {})
    beats = sum(len(scene.get("beats", [])) for scene in scenes)

    add_check(checks, "scene_count", len(scenes) > 0, f"{len(scenes)} scenes")
    add_check(checks, "entity_manifest_present", bool(entities), f"characters={len(entities.get('characters', []))}, locations={len(entities.get('locations', []))}")
    add_check(checks, "beats_to_shots", not (beats > 0 and len(shots) == 0), f"beats={beats}, shots={len(shots)}")
    add_check(checks, "shot_expansion_flag", manifest.get("_shot_expansion_complete", False), "_shot_expansion_complete")

    min_duration_ok = all((shot.get("duration") or shot.get("duration_requested") or 0) >= 6 for shot in shots)
    add_check(checks, "duration_floor", min_duration_ok, ">= 6 seconds per shot")

    target_runtime = manifest.get("_duration_target_seconds") or sum(shot.get("duration", shot.get("duration_requested", 10)) for shot in shots)
    total_duration = sum(shot.get("duration", shot.get("duration_requested", 10)) for shot in shots)
    variance = abs(total_duration - target_runtime) / target_runtime if target_runtime else 0
    add_check(checks, "runtime_tolerance", variance <= tolerance, f"target={target_runtime}s total={total_duration}s variance={variance:.2%}")

    slot_pack = manifest.get("_slot_pack")
    add_check(checks, "slot_pack_present", bool(slot_pack), "slot pack stats attached")

    slot_usage_present = all("slot_usage" in shot for shot in shots)
    add_check(checks, "slot_usage_per_shot", slot_usage_present, "each shot carries slot_usage")

    episode_factory = manifest.get("_episode_factory")
    add_check(checks, "episode_factory_metadata", bool(episode_factory), "Episode Factory summary attached")


def validate_asset_isolation(session: requests.Session, base_url: str, project_slug: str, checks: List[Dict[str, Any]]) -> None:
    forbidden_tokens = ["ravencroft_v15", "character_library_locked/ravencroft", "ravencroft_manor"]

    def no_bleed(data: Dict[str, Any], key: str) -> bool:
        for item in data.get(key, []):
            path = (item.get("path") or item.get("url") or "").lower()
            if any(token in path for token in forbidden_tokens):
                return False
        return True

    loc_resp = session.get(f"{base_url}/api/assets/location-masters?project={project_slug}", timeout=30)
    loc_ok = loc_resp.status_code == 200 and no_bleed(loc_resp.json(), "masters")
    add_check(checks, "location_isolation", loc_ok, f"status={loc_resp.status_code}")

    char_resp = session.get(f"{base_url}/api/assets/character-refs?project={project_slug}", timeout=30)
    char_ok = char_resp.status_code == 200 and no_bleed(char_resp.json(), "characters")
    add_check(checks, "character_isolation", char_ok, f"status={char_resp.status_code}")


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    checks: List[Dict[str, Any]] = []
    session = requests.Session()

    # V15.1: Check freeze status and auto-switch to LAB if needed
    original_mode = None
    if not args.no_auto_mode:
        freeze_status = get_freeze_status(session, base_url)
        if freeze_status.get("locked", False):
            original_mode = freeze_status.get("mode", "PROD")
            print(f"[FREEZE-AWARE] Server is frozen (mode={original_mode}). Switching to LAB for validation...")
            if set_freeze_mode(session, base_url, "LAB"):
                print("[FREEZE-AWARE] Switched to LAB mode")
            else:
                print("[FREEZE-AWARE] Warning: Could not switch to LAB mode, validation may fail")

    try:
        ensure_health(session, base_url, checks)
        payload = upload_script(session, base_url, args.script, args.runtime, args.genre, checks)
        project_slug = payload.get("project")
        if not project_slug:
            raise RuntimeError("Upload response missing project slug")

        manifest = load_manifest(project_slug, checks)
        validate_manifest(manifest, args.tolerance, checks)
        validate_asset_isolation(session, base_url, project_slug, checks)

    finally:
        # V15.1: Restore original mode
        if original_mode and not args.no_auto_mode:
            print(f"[FREEZE-AWARE] Restoring original mode: {original_mode}")
            set_freeze_mode(session, base_url, original_mode)

    passed = all(c["passed"] for c in checks)
    print("\n=== ATLAS FREEZE VALIDATION REPORT ===")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        detail = f" ({check['detail']})" if check["detail"] else ""
        print(f"[{status}] {check['name']}{detail}")

    print("\nResult:", "PASS ✅" if passed else "FAIL ❌")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nValidation failed: {exc}", file=sys.stderr)
        sys.exit(1)
