from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
from .utils import read_json, write_json, resolve_paths, normalize_char, ensure_list, load_config
from .live_sync import live_job_create, live_job_update


def find_cast_entry(cname: str, cast_map: dict) -> Optional[dict]:
    """
    Find a cast entry with fuzzy matching.
    Handles: "EVELYN" -> "EVELYN RAVENCROFT", "LADY MARGARET" -> "LADY MARGARET RAVENCROFT"
    """
    if not cname:
        return None

    cname_upper = cname.upper().strip()

    # 1. Exact match (case variations)
    for key in [cname, cname.title(), cname.lower(), cname_upper]:
        if key in cast_map:
            return cast_map[key]

    # 2. Check for aliases (_alias_of field)
    for key, entry in cast_map.items():
        if key.startswith("_"):
            continue
        if isinstance(entry, dict) and entry.get("_alias_of"):
            alias_of = entry.get("_alias_of", "").upper()
            if cname_upper == key.upper() or cname_upper == alias_of:
                return entry

    # 3. Partial match - "EVELYN" matches "EVELYN RAVENCROFT"
    for key, entry in cast_map.items():
        if key.startswith("_"):
            continue
        if not isinstance(entry, dict):
            continue
        key_upper = key.upper()
        # Check if cname is a prefix/start of a full name
        if key_upper.startswith(cname_upper + " "):
            return entry
        # Check if cname appears as first name or significant part
        key_parts = key_upper.split()
        if len(key_parts) > 1 and key_parts[0] == cname_upper:
            return entry

    return None


def propagate_cast_to_shots(project: str, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    cfg = load_config(p.repo_root)
    proj_dir = p.project_dir

    job = live_job_create(project, "cast-propagate", {"project": project}, repo_root=p.repo_root)
    job_id = job["job"]["job_id"]
    live_job_update(project, job_id, "running", repo_root=p.repo_root)

    cast_map_path = proj_dir / "cast_map.json"
    shot_plan_path = proj_dir / "shot_plan.json"

    cast_map = read_json(cast_map_path, default=None)
    shots = read_json(shot_plan_path, default=None)

    if not cast_map or not shots:
        live_job_update(project, job_id, "failed", {"error": "Missing cast_map.json or shot_plan.json"}, repo_root=p.repo_root)
        return {"success": False, "blocking": ["missing_cast_or_shots"], "warnings": [], "shots_updated": 0}

    if isinstance(shots, dict) and "shots" in shots:
        shots_list = shots["shots"]
        wrapper = shots
    else:
        shots_list = shots
        wrapper = None

    shots_updated = 0
    warnings = []
    blocking = []

    for sh in shots_list:
        chars = ensure_list(sh.get("characters"))
        # V16.7: Handle case where ai_actor_cast is a string (legacy) or dict or None
        existing_cast = sh.get("ai_actor_cast")
        shot_cast = existing_cast if isinstance(existing_cast, dict) else {}
        changed = False

        for c in chars:
            if isinstance(c, dict):
                cname = normalize_char(c.get("name") or "")
            else:
                cname = normalize_char(str(c))

            if not cname:
                continue
            entry = find_cast_entry(cname, cast_map)
            if not entry:
                warnings.append(f"uncast_character_in_shot:{sh.get('shot_id')}:{cname}")
                continue

            # EXTRAS POOL entries don't require references - they use stock actors
            is_extras_pool = entry.get("is_extras_pool", False)
            ref = entry.get("headshot_url") or entry.get("reference_url") or ""
            if not ref and not is_extras_pool:
                blocking.append(f"missing_reference_url:{cname}")
                continue

            shot_cast[cname] = {
                "ai_actor": entry.get("ai_actor") or entry.get("visual_actor") or "Unknown",
                "ai_actor_id": entry.get("ai_actor_id"),
                "reference_url": ref,
                "is_extras_pool": is_extras_pool
            }
            changed = True

        if changed:
            sh["ai_actor_cast"] = shot_cast
            shots_updated += 1

    # Persist back
    if wrapper is not None:
        wrapper["shots"] = shots_list
        write_json(shot_plan_path, wrapper)
    else:
        write_json(shot_plan_path, shots_list)

    status = "completed" if not blocking else "failed"
    live_job_update(project, job_id, status, {"warnings": warnings[:50], "blocking": blocking[:50], "shots_updated": shots_updated}, repo_root=p.repo_root)
    return {"success": status == "completed", "blocking": blocking, "warnings": warnings, "shots_updated": shots_updated, "artifact": str(shot_plan_path)}
