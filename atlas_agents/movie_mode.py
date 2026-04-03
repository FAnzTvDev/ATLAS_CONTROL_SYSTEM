"""
MOVIE_MODE Guardrails for ATLAS V18.3

In MOVIE_MODE (production), the system:
- BLOCKS code-level changes (signature drift)
- ALLOWS data-level healing (missing fields, aliases, segment metadata)
- LOGS all mutations to Sentry
- REQUIRES director approval for casting changes

In DEV_MODE, the system:
- WARNS but allows signature regeneration
- Allows all repairs
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Mode detection
def get_execution_mode() -> str:
    """Get current execution mode from environment or config."""
    # Check environment variable first
    mode = os.environ.get("ATLAS_MODE", "").upper()
    if mode in ("MOVIE", "PRODUCTION", "LOCKED"):
        return "MOVIE"
    if mode in ("DEV", "DEVELOPMENT"):
        return "DEV"

    # Check FACTORY_SIGNATURE.json
    sig_path = Path(__file__).parent.parent.parent.parent / "FACTORY_SIGNATURE.json"
    if sig_path.exists():
        import json
        with open(sig_path) as f:
            sig = json.load(f)
        if sig.get("factory_mode") == "LOCKED":
            return "MOVIE"

    return "DEV"


def is_movie_mode() -> bool:
    """Check if running in MOVIE (production) mode."""
    return get_execution_mode() == "MOVIE"


# Allowed mutations in MOVIE_MODE (data-level only)
MOVIE_MODE_ALLOWED_MUTATIONS = {
    "cast_map.json": ["_aliases", "_approved", "_approved_at"],  # Alias/approval metadata
    "shot_plan.json": ["segments", "render_plan", "_segments_auto_repaired"],  # Segment data
    "first_frames/*": True,  # Generated assets
    "videos/*": True,  # Generated assets
    "director_overrides.json": True,  # Director edits always allowed
}

MOVIE_MODE_BLOCKED_MUTATIONS = [
    "*.py",  # Code changes
    "schema_*.json",  # Schema changes
    "FACTORY_SIGNATURE.json",  # Signature changes
    "ai_actors_library.json",  # Actor library changes
    "directors_library.json",  # Director library changes
    "writers_library.json",  # Writer library changes
]


def check_mutation_allowed(file_path: str, field: str = None) -> Dict[str, Any]:
    """
    Check if a mutation is allowed in current mode.
    Returns: {"allowed": bool, "reason": str}
    """
    mode = get_execution_mode()

    if mode == "DEV":
        return {"allowed": True, "reason": "DEV mode allows all mutations"}

    # MOVIE mode - strict checking
    file_name = Path(file_path).name

    # Check blocked patterns
    for pattern in MOVIE_MODE_BLOCKED_MUTATIONS:
        if pattern.startswith("*"):
            if file_name.endswith(pattern[1:]):
                return {
                    "allowed": False,
                    "reason": f"MOVIE_MODE blocks {pattern} mutations"
                }
        elif file_name == pattern:
            return {
                "allowed": False,
                "reason": f"MOVIE_MODE blocks {file_name} mutations"
            }

    # Check allowed patterns
    for pattern, allowed_fields in MOVIE_MODE_ALLOWED_MUTATIONS.items():
        if pattern.endswith("/*"):
            dir_name = pattern[:-2]
            if dir_name in file_path:
                return {"allowed": True, "reason": f"Generated asset in {dir_name}"}
        elif file_name == pattern:
            if allowed_fields is True:
                return {"allowed": True, "reason": f"{file_name} is fully writable"}
            if field and field in allowed_fields:
                return {"allowed": True, "reason": f"{field} is allowed in {file_name}"}
            if field:
                return {
                    "allowed": False,
                    "reason": f"Field '{field}' not in allowed list for {file_name}"
                }
            return {"allowed": True, "reason": f"{file_name} is writable (no field specified)"}

    # Default: allow in MOVIE mode for unlisted files (they might be new outputs)
    return {"allowed": True, "reason": "File not in blocked list"}


def log_mutation(file_path: str, mutation_type: str, details: Dict = None):
    """Log a mutation event (to console and Sentry if available)."""
    mode = get_execution_mode()
    timestamp = datetime.now().isoformat()

    log_entry = {
        "timestamp": timestamp,
        "mode": mode,
        "file": file_path,
        "mutation": mutation_type,
        "details": details or {}
    }

    print(f"[{mode}] MUTATION: {mutation_type} on {file_path}")

    # Log to Sentry in MOVIE mode
    if mode == "MOVIE":
        try:
            import sentry_sdk
            sentry_sdk.add_breadcrumb(
                category="mutation",
                message=f"{mutation_type}: {file_path}",
                level="info",
                data=details
            )
        except ImportError:
            pass

    return log_entry
