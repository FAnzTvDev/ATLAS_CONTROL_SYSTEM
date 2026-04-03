#!/usr/bin/env python3
"""Inject framing matrices, continuity notes, and motion metadata for every shot.

This script enforces the Marcus 004-style guardrails:
  * rule-of-thirds anchors for primary/secondary subjects
  * continuity references to neighboring shots
  * timeline roles so prompts carry pacing intent
  * LTX motion metadata with start/end beats

Run this anytime the manifest changes:
    python tools/apply_framing_matrix.py blackwood_parallel_test.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROLE_SEQUENCE = [
    "establishing_plate",
    "detail_insert",
    "dialogue_call",
    "dialogue_response",
    "symbol_insert",
    "exit_marker"
]

ANCHOR_ORDER = {
    "wide": ("left_third", "right_third"),
    "medium": ("center_left_third", "center_right_third"),
    "closeup": ("center", None),
    "insert": ("center", None),
    "over_shoulder": ("near_right", "far_left"),
    "medium_closeup": ("center_left_third", None)
}

CAMERA_HEIGHT = {
    "wide": "waist_height",
    "medium": "chest_height",
    "over_shoulder": "eye_level",
    "closeup": "eye_level",
    "insert": "object_plane"
}

DEPTH_TAG = {
    "wide": "deep_focus",
    "medium": "controlled_depth",
    "closeup": "shallow_depth",
    "insert": "macro_plane"
}


def _parse_refs(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [ref.strip() for ref in value.split(',') if ref.strip()]


def _anchors(shot_type: str, refs: List[str]) -> Dict[str, Optional[str]]:
    base = ANCHOR_ORDER.get(shot_type, ("center", None))
    primary_anchor, secondary_anchor = base
    if not refs:
        return {"primary_anchor": "center", "secondary_anchor": None}
    if len(refs) == 1:
        return {"primary_anchor": primary_anchor or "center", "secondary_anchor": None}
    return {
        "primary_anchor": primary_anchor or "left_third",
        "secondary_anchor": secondary_anchor or "right_third"
    }


def _timeline_role(idx: int) -> str:
    return ROLE_SEQUENCE[idx % len(ROLE_SEQUENCE)]


def _continuity(prev_id: Optional[str], next_id: Optional[str], scene_id: str) -> str:
    head = prev_id or f"scene {scene_id} cold open"
    tail = next_id or f"scene {scene_id} outro"
    return f"Match framing from {head} and hand off cleanly to {tail}."


def _motion_metadata(shot: Dict) -> Dict[str, str]:
    blocking = shot.get('character_blocking') or 'Undefined blocking'
    camera = shot.get('camera') or 'camera'
    return {
        "start_pose": f"Camera {camera} at action start, honoring {blocking.split(',')[0].strip()} grounding.",
        "end_pose": f"Conclude with {blocking} locked before cutting.",
        "tempo": f"{shot.get('duration', 6)}s beat per Marcus 004 cadence"
    }


def inject(path: Path) -> None:
    data = json.loads(path.read_text())
    for scene in data.get('scenes', []):
        shots = scene.get('shots', [])
        for idx, shot in enumerate(shots):
            refs = _parse_refs(shot.get('reference_needed'))
            anchors = _anchors(shot.get('type', '').lower(), refs)
            framing = shot.get('framing_matrix', {})
            framing.update({
                "primary_subject": refs[0] if refs else shot.get('type', 'environment'),
                "primary_anchor": anchors['primary_anchor'],
                "secondary_subject": refs[1] if len(refs) > 1 else None,
                "secondary_anchor": anchors.get('secondary_anchor'),
                "camera_height": CAMERA_HEIGHT.get(shot.get('type', '').lower(), 'eye_level'),
                "depth_intent": DEPTH_TAG.get(shot.get('type', '').lower(), 'controlled_depth')
            })
            shot['framing_matrix'] = framing

            prev_id = shots[idx - 1]['shot_id'] if idx > 0 else None
            next_id = shots[idx + 1]['shot_id'] if idx + 1 < len(shots) else None
            shot['continuity_prev'] = prev_id
            shot['continuity_next'] = next_id
            shot['continuity_note'] = _continuity(prev_id, next_id, scene['scene_id'])
            shot['timeline_role'] = shot.get('timeline_role') or _timeline_role(idx)
            shot['ltx_motion_metadata'] = _motion_metadata(shot)

    path.write_text(json.dumps(data, indent=2))
    print(f"✅ Injected framing metadata into {path}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python tools/apply_framing_matrix.py <manifest.json>")
        sys.exit(1)
    manifest_path = Path(sys.argv[1]).expanduser().resolve()
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        sys.exit(2)
    inject(manifest_path)


if __name__ == "__main__":
    main()
