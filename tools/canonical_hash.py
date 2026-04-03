#!/usr/bin/env python3
"""
CANONICAL HASH - Deterministic State Hashing

Produces identical hashes for identical project state regardless of:
- Timestamp fields
- Key ordering
- Whitespace variations

Usage:
    python3 tools/canonical_hash.py <project>
    python3 tools/canonical_hash.py kord_v17 --compare <other_project>
"""

import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

# Keys to strip (volatile, non-semantic)
VOLATILE_KEYS = {
    "_generated_at",
    "_last_modified",
    "_approved_at",
    "_created_at",
    "timestamp",
    "run_id",
    "job_id",
    "generated_at",
    "last_modified",
    "checked_at",
    "created",
    "_ui_enforced",
    "_ui_enforced_version"
}

# Files that define canonical state
CANONICAL_FILES = [
    "story_bible.json",
    "shot_plan.json",
    "cast_map.json"
]


def strip_volatile(obj: Any) -> Any:
    """Recursively strip volatile keys from object."""
    if isinstance(obj, dict):
        return {
            k: strip_volatile(v)
            for k, v in obj.items()
            if k not in VOLATILE_KEYS
        }
    elif isinstance(obj, list):
        return [strip_volatile(item) for item in obj]
    else:
        return obj


def canonical_serialize(obj: Any) -> str:
    """Serialize object to canonical JSON string."""
    # Strip volatile keys
    cleaned = strip_volatile(obj)
    # Sort keys, no whitespace variations
    return json.dumps(cleaned, sort_keys=True, separators=(',', ':'))


def hash_string(s: str) -> str:
    """SHA256 hash of string."""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def hash_file(file_path: Path) -> Dict[str, str]:
    """Hash a single file canonically."""
    if not file_path.exists():
        return {"exists": False, "hash": None}

    try:
        with open(file_path) as f:
            data = json.load(f)
        canonical = canonical_serialize(data)
        return {
            "exists": True,
            "hash": hash_string(canonical),
            "size": len(canonical)
        }
    except Exception as e:
        return {"exists": True, "hash": None, "error": str(e)}


def hash_project_state(project: str) -> Dict:
    """
    Hash entire project canonical state.

    Returns:
        {
            "project": str,
            "combined_hash": str,
            "per_file_hashes": {filename: hash},
            "semantic_version": str
        }
    """
    project_path = BASE_DIR / "pipeline_outputs" / project

    if not project_path.exists():
        return {"error": f"Project {project} not found"}

    per_file = {}
    combined_data = []

    for filename in CANONICAL_FILES:
        file_path = project_path / filename
        result = hash_file(file_path)
        per_file[filename] = result

        if result.get("hash"):
            combined_data.append(f"{filename}:{result['hash']}")

    # Add semantic invariants version
    invariants_path = BASE_DIR / "atlas_agents_v16_7" / "atlas_agents" / "semantic_invariants.py"
    if invariants_path.exists():
        inv_hash = hash_string(invariants_path.read_text())
        per_file["semantic_invariants.py"] = {"hash": inv_hash[:16]}
        combined_data.append(f"invariants:{inv_hash[:16]}")

    # Combined hash
    combined_str = "|".join(sorted(combined_data))
    combined_hash = hash_string(combined_str)

    return {
        "project": project,
        "combined_hash": combined_hash,
        "per_file_hashes": per_file,
        "canonical_files": CANONICAL_FILES,
        "semantic_version": "v17"
    }


def compare_projects(project1: str, project2: str) -> Dict:
    """Compare canonical state of two projects."""
    hash1 = hash_project_state(project1)
    hash2 = hash_project_state(project2)

    if "error" in hash1 or "error" in hash2:
        return {"match": False, "error": hash1.get("error") or hash2.get("error")}

    differences = []
    for filename in CANONICAL_FILES:
        h1 = hash1["per_file_hashes"].get(filename, {}).get("hash")
        h2 = hash2["per_file_hashes"].get(filename, {}).get("hash")
        if h1 != h2:
            differences.append(filename)

    return {
        "match": len(differences) == 0,
        "project1_hash": hash1["combined_hash"],
        "project2_hash": hash2["combined_hash"],
        "differences": differences
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/canonical_hash.py <project> [--compare <other>]")
        sys.exit(1)

    project = sys.argv[1]

    if "--compare" in sys.argv:
        idx = sys.argv.index("--compare")
        if idx + 1 < len(sys.argv):
            other = sys.argv[idx + 1]
            result = compare_projects(project, other)
            print(json.dumps(result, indent=2))
            sys.exit(0 if result.get("match") else 1)

    result = hash_project_state(project)
    print(json.dumps(result, indent=2))

    if "error" not in result:
        print(f"\nCombined Hash: {result['combined_hash'][:16]}...")


if __name__ == "__main__":
    main()
