from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from .utils import read_json, write_json, resolve_paths, load_config
from .live_sync import live_job_create, live_job_update

def _make_segments(shot_id: str, total: int, max_seg: int, floor: int) -> List[dict]:
    segs = []
    remaining = total
    idx = 1
    while remaining > 0:
        dur = min(max_seg, remaining)
        # Avoid tiny tail segment: merge into previous if under floor
        if remaining < floor and segs:
            segs[-1]["duration"] += remaining
            remaining = 0
            break
        segs.append({
            "segment_id": f"{shot_id}_S{idx}",
            "duration": dur,
            "continuation_rule": "initial" if idx == 1 else "continue_from_previous",
            "segment_prompt": ""  # filled later
        })
        remaining -= dur
        idx += 1
    return segs

def plan_fixer_run(project: str, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    cfg = load_config(p.repo_root)
    proj_dir = p.project_dir

    job = live_job_create(project, "plan-fixer", {"project": project}, repo_root=p.repo_root)
    job_id = job["job"]["job_id"]
    live_job_update(project, job_id, "running", repo_root=p.repo_root)

    shot_plan_path = proj_dir / "shot_plan.json"
    shots = read_json(shot_plan_path, default=None)
    if not shots:
        live_job_update(project, job_id, "failed", {"error": "Missing shot_plan.json"}, repo_root=p.repo_root)
        return {"success": False, "blocking": ["missing_shot_plan"], "warnings": [], "shots_updated": 0}

    if isinstance(shots, dict) and "shots" in shots:
        shots_list = shots["shots"]
        wrapper = shots
    else:
        shots_list = shots
        wrapper = None

    pol = cfg["policy"]["render_plan"]
    max_single = int(pol.get("max_single_render_seconds", 20))
    floor = int(pol.get("segment_floor_seconds", 6))

    updated = 0
    for sh in shots_list:
        dur = sh.get("duration") or sh.get("duration_s") or sh.get("seconds")
        try:
            dur = int(dur)
        except Exception:
            continue
        if dur <= max_single:
            continue

        shot_id = sh.get("shot_id") or sh.get("id") or "SHOT"
        segs = _make_segments(shot_id, dur, max_single, floor)

        # prompts: minimal continuity rules
        base_prompt = sh.get("prompt") or sh.get("ltx_prompt") or sh.get("image_prompt") or ""
        for i, seg in enumerate(segs):
            if i == 0:
                seg["segment_prompt"] = base_prompt + "\n\n[SEGMENT] Establishing. Match character identity, wardrobe, lighting."
            else:
                seg["segment_prompt"] = base_prompt + "\n\n[SEGMENT] CONTINUE FROM PREVIOUS FRAME. Preserve identity, lighting, camera intent. No jump cuts."

        sh.setdefault("render_plan", {})
        sh["render_plan"]["segments"] = segs
        updated += 1

    if wrapper is not None:
        wrapper["shots"] = shots_list
        write_json(shot_plan_path, wrapper)
    else:
        write_json(shot_plan_path, shots_list)

    live_job_update(project, job_id, "completed", {"shots_updated": updated}, repo_root=p.repo_root)
    return {"success": True, "blocking": [], "warnings": [], "shots_updated": updated, "artifact": str(shot_plan_path)}
