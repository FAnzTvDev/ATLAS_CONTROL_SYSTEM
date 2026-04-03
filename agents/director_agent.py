#!/usr/bin/env python3
"""
Director Agent
--------------
Wraps the shot-expansion logic so manifests can be regenerated using the
configured director profiles (ravencroft_gothic, sicario_tension, etc.).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any

from template_shot_expander import expand_manifest_with_shots


def regenerate_shot_manifest(
    manifest_path: Path,
    story_bible_path: Path,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Regenerate the manifest with shot coverage and return metadata."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not story_bible_path.exists():
        raise FileNotFoundError(f"Story bible not found: {story_bible_path}")

    manifest = json.loads(manifest_path.read_text())
    updated_manifest, total_shots = expand_manifest_with_shots(
        manifest,
        story_bible_path,
        director_profile=profile,
    )
    manifest_path.write_text(json.dumps(updated_manifest, indent=2))
    return {
        "status": "ok",
        "manifest_path": str(manifest_path),
        "story_bible_path": str(story_bible_path),
        "director_profile": updated_manifest.get("director_profile"),
        "total_shots": total_shots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Director Agent – regenerate shot manifest")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--story-bible", required=True, help="Path to story bible JSON")
    parser.add_argument("--profile", help="Director profile name (ravencroft_gothic, sicario_tension, etc.)")
    args = parser.parse_args()
    result = regenerate_shot_manifest(
        manifest_path=Path(args.manifest),
        story_bible_path=Path(args.story_bible),
        profile=args.profile,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
