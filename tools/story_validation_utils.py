"""Utility helpers for Story-First validation pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

PLACEHOLDER_PATTERNS = [
    re.compile(r"^Story beat \\d+ for", re.IGNORECASE),
    re.compile(r"^Character actions for beat", re.IGNORECASE),
    re.compile(r"^Story revelation \\d+", re.IGNORECASE),
    re.compile(r"^Beat \\d+", re.IGNORECASE),
]

REQUIRED_BEAT_FIELDS = ["description", "character_action", "revelation"]
DESIRED_BEAT_FIELDS = ["goal", "conflict", "turn", "emotion", "ghost_logic"]


def _is_placeholder(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in PLACEHOLDER_PATTERNS)


def _needs_ghost_logic(scene: Dict) -> bool:
    tone = (scene.get("tone") or "").lower()
    purpose = (scene.get("scene_purpose") or "").lower()
    location = (scene.get("location") or "").lower()
    keywords = (tone, purpose, location)
    return any(
        trigger in field
        for trigger in ("ghost", "specter", "spirit", "manifest", "haunt")
        for field in keywords
    )


def validate_scene(scene: Dict) -> Tuple[List[str], List[str]]:
    beat_errors: List[str] = []
    warnings: List[str] = []
    needs_ghost = _needs_ghost_logic(scene)

    beats = scene.get("beats") or []
    if not beats:
        beat_errors.append(f"[{scene.get('scene_id')}] Missing beats array; cannot validate.")
        return beat_errors, warnings

    for beat in beats:
        beat_num = beat.get("beat_number", "?")
        prefix = f"[{scene.get('scene_id')} :: beat {beat_num}]"

        for field in REQUIRED_BEAT_FIELDS:
            value = beat.get(field)
            if value is None or _is_placeholder(str(value)):
                beat_errors.append(f"{prefix} `{field}` is missing or templated.")

        for field in DESIRED_BEAT_FIELDS:
            value = beat.get(field)
            if value is None or not str(value).strip():
                warnings.append(f"{prefix} `{field}` missing; consider adding.")

        if needs_ghost:
            ghost_logic = beat.get("ghost_logic")
            if ghost_logic is None or _is_placeholder(str(ghost_logic)):
                beat_errors.append(f"{prefix} Scene implies supernatural activity but `ghost_logic` is absent.")

    return beat_errors, warnings


def build_report(manifest_path: Path) -> Dict[str, List[str]]:
    data = json.loads(manifest_path.read_text())
    scenes = data.get("scenes") or []

    report: Dict[str, List[str]] = {"errors": [], "warnings": []}

    if not scenes:
        report["errors"].append("Manifest contains no scenes.")
        return report

    for scene in scenes:
        errors, warnings = validate_scene(scene)
        report["errors"].extend(errors)
        report["warnings"].extend(warnings)

    return report


def save_report(report_path: Path, report: Dict[str, List[str]]) -> None:
    lines: List[str] = ["# Story Validation Report", ""]

    if report["errors"]:
        lines.append("## Errors")
        lines.extend(f"- {entry}" for entry in report["errors"])
        lines.append("")
    else:
        lines.extend(["## Errors", "- None 🎉", ""])

    if report["warnings"]:
        lines.append("## Warnings")
        lines.extend(f"- {entry}" for entry in report["warnings"])
    else:
        lines.extend(["## Warnings", "- None"])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines))


__all__ = [
    "build_report",
    "save_report",
    "validate_scene",
]
