#!/usr/bin/env python3
"""Populate scene manifests with story-aware dialogue/audio metadata.

This utility reads a dialogue template (story bible extract) and injects
`dialogue` and `audio_note` fields into a production manifest. It is a simple
bridge so the execution pipeline can forward explicit spoken lines to the
video generator without human copy/paste.

Usage:
    python pipeline_tools/dialogue_autowriter.py \
        --manifest manifests/marcus_scene_004_dialogue.json \
        --template dialogue_templates/scene_004.json

Pass --dry-run to preview changes without writing to disk. The script keeps a
`.bak` copy of the manifest by default so the previous state can be restored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"❌ Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"❌ Invalid JSON in {path}: {exc}") from exc


def apply_dialogue(manifest: Dict[str, Any], template: Dict[str, Any]) -> List[str]:
    """Inject dialogue/audio metadata. Returns list of change descriptions."""
    shot_lookup = {shot["shot_id"]: shot for shot in template.get("shots", [])}
    changes: List[str] = []

    for shot in manifest.get("shots", []):
        shot_id = shot.get("shot_id")
        if not shot_id or shot_id not in shot_lookup:
            continue

        template_shot = shot_lookup[shot_id]

        if "dialogue" in template_shot:
            new_dialogue = template_shot["dialogue"]
            if shot.get("dialogue") != new_dialogue:
                shot["dialogue"] = new_dialogue
                changes.append(f"dialogue → {shot_id}")

        if "audio_note" in template_shot:
            new_audio = template_shot["audio_note"]
            if shot.get("audio_note") != new_audio:
                shot["audio_note"] = new_audio
                changes.append(f"audio_note → {shot_id}")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject dialogue into a scene manifest")
    parser.add_argument("--manifest", required=True, help="Path to the scene manifest JSON")
    parser.add_argument("--template", required=True, help="Path to the dialogue template JSON")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    parser.add_argument("--no-backup", action="store_true", help="Skip writing a .bak copy")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    template_path = Path(args.template)

    manifest_data = load_json(manifest_path)
    template_data = load_json(template_path)

    changes = apply_dialogue(manifest_data, template_data)

    if not changes:
        print("✅ Manifest already contains template dialogue; no changes needed.")
        return

    if args.dry_run:
        print("📝 Dry run – pending updates:")
        for change in changes:
            print(f"  • {change}")
        return

    if not args.no_backup:
        backup_path = manifest_path.with_suffix(manifest_path.suffix + ".bak")
        backup_path.write_text(json.dumps(load_json(manifest_path), indent=2))

    manifest_path.write_text(json.dumps(manifest_data, indent=2))
    print(f"💾 Updated {manifest_path} with {len(changes)} changes:")
    for change in changes:
        print(f"  • {change}")


if __name__ == "__main__":
    main()
