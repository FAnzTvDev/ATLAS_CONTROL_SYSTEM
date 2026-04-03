from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, time, hashlib
import yaml

def now_ts() -> int:
    return int(time.time())

def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj, indent: int = 2):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)
    tmp.replace(path)

def stable_hash(obj) -> str:
    try:
        s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_config(repo_root: Path) -> dict:
    cfg_path = repo_root / "config.yaml"
    if not cfg_path.exists():
        # allow running from package dir
        cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@dataclass
class ProjectPaths:
    repo_root: Path
    project: str
    pipeline_outputs_dir: Path
    project_dir: Path
    actor_library: Path

def resolve_paths(project: str, repo_root: str | Path | None = None) -> ProjectPaths:
    rr = Path(repo_root or ".").resolve()
    cfg = load_config(rr)
    po = rr / cfg["paths"]["pipeline_outputs_dir"]
    pj = po / project
    actor_lib = rr / cfg["paths"]["actor_library_file"]
    return ProjectPaths(repo_root=rr, project=project, pipeline_outputs_dir=po, project_dir=pj, actor_library=actor_lib)

def normalize_char(name: str) -> str:
    return (name or "").strip().upper()

def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]
