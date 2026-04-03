from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
from .utils import read_json, write_json, now_ts, stable_hash, load_config, resolve_paths

# ---- Live job feed + recent renders feed (truth layer for UI) ----
# Design: store as JSON files in pipeline_outputs/<project>/ so server can return them directly.

def to_media_url(abs_path: str, repo_root: Path | None = None) -> str:
    rr = (repo_root or Path(".")).resolve()
    cfg = load_config(rr)
    prefix = cfg["paths"].get("media_url_prefix", "/api/media?path=")
    # Always emit /api/media?path= for safety (works regardless of /media mounts)
    return f"{prefix}{abs_path}"

def jobs_path(project_dir: Path) -> Path:
    return project_dir / "_live_jobs.json"

def recent_path(project_dir: Path) -> Path:
    return project_dir / "_recent_renders.json"

def load_jobs(project_dir: Path) -> Dict[str, Any]:
    return read_json(jobs_path(project_dir), default={"jobs": []}) or {"jobs": []}

def save_jobs(project_dir: Path, jobs_obj: Dict[str, Any]):
    write_json(jobs_path(project_dir), jobs_obj)

def live_job_create(project: str, job_type: str, payload: dict, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    jobs_obj = load_jobs(p.project_dir)
    job_id = payload.get("job_id") or f"job-{now_ts()}-{len(jobs_obj['jobs'])+1}"
    job = {
        "job_id": job_id,
        "project": project,
        "type": job_type,
        "status": "queued",
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "payload": payload,
        "error": None,
    }
    jobs_obj["jobs"].insert(0, job)
    save_jobs(p.project_dir, jobs_obj)
    return {"success": True, "job": job}

def live_job_update(project: str, job_id: str, status: str, extra: dict | None = None, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    jobs_obj = load_jobs(p.project_dir)
    found = False
    for j in jobs_obj["jobs"]:
        if j.get("job_id") == job_id:
            j["status"] = status
            j["updated_at"] = now_ts()
            if extra:
                j.update(extra)
            found = True
            break
    if not found:
        return {"success": False, "error": f"job_id not found: {job_id}"}
    save_jobs(p.project_dir, jobs_obj)
    return {"success": True, "job_id": job_id, "status": status}

def recent_renders_scan(project: str, repo_root: str | Path | None = None) -> dict:
    """Minimal scanner: looks for common output files under pipeline_outputs/<project>/renders.
    If your real pipeline stores elsewhere, update SEARCH_DIRS.
    """
    p = resolve_paths(project, repo_root=repo_root)
    rr = p.repo_root
    cfg = load_config(rr)
    proj_dir = p.project_dir

    SEARCH_DIRS = [
        proj_dir / "renders",
        proj_dir / "render_gallery",
        proj_dir / "outputs",
    ]

    items: List[dict] = []
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        for fp in sorted(d.rglob("*")):
            if fp.is_dir():
                continue
            low = fp.name.lower()
            if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov")):
                items.append({
                    "name": fp.name,
                    "abs_path": str(fp.resolve()),
                    "path": to_media_url(str(fp.resolve()), repo_root=rr),
                    "type": "video" if low.endswith((".mp4", ".mov")) else "image",
                    "updated_at": int(fp.stat().st_mtime),
                })

    payload = {"project": project, "items": items[:200], "hash": stable_hash(items[:200]), "scanned_at": now_ts()}
    write_json(recent_path(proj_dir), payload)
    return {"success": True, **payload}

def get_jobs(project: str, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    return load_jobs(p.project_dir)

def get_recent(project: str, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    return read_json(recent_path(p.project_dir), default={"project": project, "items": []}) or {"project": project, "items": []}
