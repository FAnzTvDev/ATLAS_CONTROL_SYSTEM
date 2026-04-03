#!/usr/bin/env python3
"""
Project State Helpers
---------------------
Stores per-project defaults (manifest path, story bible, last pipeline outputs)
so the UI and agents can auto-populate forms.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "state" / "project_state.json"

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ravencroft_manor": {
        "manifest_path": str(BASE_DIR / "manifests" / "TEASER_FINAL.json"),
        "story_bible_path": str(BASE_DIR / "ravencroft_story_bible.json"),
        "pipeline_output_dir": "",
        "shot_plan_path": "",
        "vision_dir": "",
    },
    "blackwood_estate": {
        "manifest_path": str(BASE_DIR / "blackwood_WORKING_3_SCENES.json"),
        "story_bible_path": str(BASE_DIR / "blackwood_story_bible.json"),
        "pipeline_output_dir": "",
        "shot_plan_path": "",
        "vision_dir": "",
    },
}


def _load_state() -> Dict[str, Dict[str, Any]]:
    if not STATE_PATH.exists():
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text("{}")
        return {}
    try:
        return json.loads(STATE_PATH.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _save_state(state: Dict[str, Dict[str, Any]]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def get_project_state(slug: str) -> Dict[str, Any]:
    slug = slug or ""
    state = _load_state()
    merged = dict(DEFAULTS.get(slug, {}))
    merged.update(state.get(slug, {}))
    return merged


def update_project_state(slug: str, **kwargs: Any) -> Dict[str, Any]:
    slug = slug or ""
    state = _load_state()
    current = state.get(slug, {})
    current.update({k: v for k, v in kwargs.items() if v is not None})
    state[slug] = current
    _save_state(state)
    return get_project_state(slug)
