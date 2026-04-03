#!/usr/bin/env python3
"""
Pipeline Agent
--------------
Validates assets/meta state, builds per-shot contexts with grid overrides,
and emits shot_plan / render_queue JSON that the Renderer Agent can consume.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable

from PIL import Image, ImageDraw, ImageFont

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from episode_generator import (  # pylint: disable=import-error
    GRID_MIN_SLOTS,
    _build_grid_context_override,
    _build_semantic_prompt,
    _count_grid_slots,
    _filter_grid_context,
)
from reference_validator import ReferenceValidator

logger = logging.getLogger(__name__)

CHAR_LIB_PATH = PROJECT_ROOT / "character_library.json"
LOCATION_LIB_PATH = PROJECT_ROOT / "location_library.json"
QUALITY_LIB_PATH = PROJECT_ROOT / "quality_anchor_library.json"
LOCKED_CHAR_DIR = PROJECT_ROOT / "character_library_locked"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2))


def _collect_shots(manifest: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    if manifest.get("shots"):
        yield from manifest["shots"]
    for scene in manifest.get("scenes", []):
        for shot in scene.get("shots", []):
            yield shot


def _find_character_asset(project_slug: str, name: str) -> Optional[Path]:
    base_dir = LOCKED_CHAR_DIR / project_slug
    if not base_dir.exists():
        return None
    slug = _slugify(name).upper()
    direct = base_dir / f"{slug}_LOCKED_REFERENCE.jpg"
    if direct.exists():
        return direct
    matches = sorted(base_dir.glob(f"*{slug}*.jpg"))
    if matches:
        return matches[0]
    return _create_character_asset(project_slug, name)


def _synthesize_placeholder(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (768, 512), color=(15, 15, 20))
    draw = ImageDraw.Draw(img)
    text = label[:60]
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover - pillow fallback
        font = None
    draw.text((20, 20), text, fill=(200, 200, 210), font=font)
    img.save(path, format="JPEG")


def _create_character_asset(project_slug: str, name: str) -> Optional[Path]:
    base_dir = LOCKED_CHAR_DIR / project_slug
    base_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name).upper() or "CHARACTER"
    candidate = base_dir / f"{slug}_LOCKED_REFERENCE.jpg"
    _synthesize_placeholder(candidate, f"{name} reference")
    return candidate


def _ensure_character_entry(name: str, project_slug: str, char_lib: Dict[str, Any]) -> bool:
    if not name or name in char_lib:
        return False
    asset = _find_character_asset(project_slug, name)
    if not asset:
        logger.warning("⚠️ Character asset not found for %s", name)
        return False
    url = str(asset.resolve())
    char_lib[name] = {
        "face_neutral": {"url": url, "description": f"{name} locked reference"},
        "body_reference": {"url": url, "description": f"{name} wardrobe reference"},
    }
    logger.info("   ↳ Auto-registered character asset for %s", name)
    return True


def _find_location_assets(project_slug: str, location_name: str) -> List[Path]:
    cache_dir = LOCKED_CHAR_DIR / project_slug / "asset_cache"
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(location_name)
    candidates: List[Path] = []
    for asset_path in cache_dir.glob("location_*.jpg"):
        stem = asset_path.stem.lower()
        if any(token for token in slug.split("_") if token and token in stem):
            candidates.append(asset_path)
    if not candidates:
        candidates = sorted(cache_dir.glob("location_*.jpg"))
    if not candidates:
        synthesized = []
        for idx in range(1, 5):
            placeholder = cache_dir / f"location_{slug or 'generic'}_angle{idx}.jpg"
            _synthesize_placeholder(placeholder, f"{location_name} angle {idx}")
            synthesized.append(placeholder)
        return synthesized
    return sorted(candidates)[:4]


def _ensure_location_entry(name: str, project_slug: str, loc_lib: Dict[str, Any]) -> bool:
    if not name or name in loc_lib:
        return False
    refs = _find_location_assets(project_slug, name)
    if not refs:
        logger.warning("⚠️ Location references not found for %s", name)
        return False
    depth = {}
    for idx, ref in enumerate(refs, start=1):
        depth[f"angle_{idx}"] = {
            "url": str(ref.resolve()),
            "slot_priority": idx,
            "description": f"{name} reference {idx}",
        }
    loc_lib[name] = {"depth_references": depth, "primary_style": name}
    logger.info("   ↳ Auto-registered location refs for %s", name)
    return True


def _find_quality_asset(project_slug: str, anchor_name: str) -> Optional[Path]:
    cache_dir = LOCKED_CHAR_DIR / project_slug / "asset_cache"
    if not cache_dir.exists():
        return None
    slug = _slugify(anchor_name)
    for prefix in ("quality_anchor", "prop", "location"):
        matches = sorted(cache_dir.glob(f"{prefix}*.jpg"))
        for match in matches:
            if slug and slug in match.stem.lower():
                return match
    matches = sorted(cache_dir.glob("quality_anchor_*.jpg"))
    if matches:
        return matches[0]
    placeholder = cache_dir / f"quality_anchor_{_slugify(anchor_name) or 'tone'}.jpg"
    _synthesize_placeholder(placeholder, f"{anchor_name} quality anchor")
    return placeholder


def _ensure_quality_anchor_entry(name: str, project_slug: str, qa_lib: Dict[str, Any]) -> bool:
    if not name:
        return False
    key = name.strip().upper()
    if key in qa_lib:
        return False
    asset = _find_quality_asset(project_slug, name)
    if not asset:
        logger.warning("⚠️ Quality anchor asset not found for %s", name)
        return False
    qa_lib[key] = {
        "url": str(asset.resolve()),
        "description": f"{name} reference",
    }
    logger.info("   ↳ Auto-registered quality anchor %s", name)
    return True


def auto_generate_assets_for_manifest(manifest: Dict[str, Any], project_slug: str) -> None:
    shots = list(_collect_shots(manifest))
    if not shots:
        return
    char_lib = _load_json(CHAR_LIB_PATH)
    loc_lib = _load_json(LOCATION_LIB_PATH)
    qa_lib = _load_json(QUALITY_LIB_PATH)
    char_changed = loc_changed = qa_changed = False
    for shot in shots:
        for character in shot.get("characters") or []:
            if _ensure_character_entry(character, project_slug, char_lib):
                char_changed = True
        location = shot.get("location")
        if location and _ensure_location_entry(location, project_slug, loc_lib):
            loc_changed = True
        quality_anchor = shot.get("quality_anchor")
        if quality_anchor and _ensure_quality_anchor_entry(quality_anchor, project_slug, qa_lib):
            qa_changed = True
    if char_changed:
        _save_json(CHAR_LIB_PATH, char_lib)
    if loc_changed:
        _save_json(LOCATION_LIB_PATH, loc_lib)
    if qa_changed:
        _save_json(QUALITY_LIB_PATH, qa_lib)
    if char_changed or loc_changed or qa_changed:
        logger.info(
            "✅ Auto-generated assets – characters:%s locations:%s anchors:%s",
            char_changed,
            loc_changed,
            qa_changed,
        )


def build_shot_plan(
    manifest: Dict[str, Any],
    story_bible_path: Path,
    concept: str,
    project_slug: str,
    characters: Optional[List[str]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Core pipeline agent routine. Ensures the grid is wired, then builds
    shot metadata + render queue using the smart manifest content.
    """
    if settings and settings.get("auto_generate_missing_assets"):
        auto_generate_assets_for_manifest(manifest, project_slug)

    validator = ReferenceValidator(
        story_bible_path=str(story_bible_path),
        character_library_path="character_library.json",
        location_library_path="location_library.json",
        quality_anchor_library_path="quality_anchor_library.json",
    )
    grid_override = _build_grid_context_override(validator)
    slot_count = _count_grid_slots(grid_override)
    if slot_count < GRID_MIN_SLOTS:
        raise RuntimeError(
            f"Asset grid incomplete: {slot_count}/14 slots wired. "
            "Relabel/validate assets before running the renderer."
        )

    manifest_scenes = manifest.get("scenes", [])
    scene_lookup = {scene.get("scene_id"): scene for scene in manifest_scenes}

    plan: List[Dict[str, Any]] = []
    queue: List[str] = []
    base_characters = characters or manifest.get("characters_present") or []
    if isinstance(base_characters, str):
        base_characters = [base_characters]

    for shot in manifest.get("shots", []):
        scene_meta = scene_lookup.get(shot.get("scene_id"), {})
        prompt = _build_semantic_prompt(shot, scene_meta, concept)
        shot_characters = shot.get("characters") or base_characters
        if isinstance(shot_characters, str):
            shot_characters = [shot_characters]
        shot_props = shot.get("props") or []

        shot_grid_context = _filter_grid_context(
            grid_override,
            shot_characters or [],
            shot.get("location"),
            shot.get("quality_anchor"),
            shot_props,
        )
        shot_grid_context["shot_entry"] = {
            "location": shot.get("location"),
            "characters": shot_characters,
            "quality_anchor": shot.get("quality_anchor"),
            "props": shot_props,
            "use_previous_shot": shot.get("use_previous_shot", False),
        }

        shot_context = {
            "shot_id": shot["shot_id"],
            "scene_id": shot.get("scene_id"),
            "project": project_slug,
            "prompt": prompt,
            "characters": shot_characters,
            "location": shot.get("location"),
            "quality_anchor": shot.get("quality_anchor"),
            "ltx_metadata": {
                "duration": shot.get("duration"),
                "ltx_duration_seconds": shot.get("ltx_duration_seconds"),
                "motion": shot.get("ltx_motion_metadata"),
            },
            "script_semantics": shot.get("script_semantics"),
            "props": shot_props,
            "_grid_context_override": shot_grid_context,
            "settings": settings or {},
        }
        plan.append(shot_context)
        queue.append(shot["shot_id"])

    return {
        "grid_slots": slot_count,
        "project": project_slug,
        "shot_plan": plan,
        "render_queue": queue,
    }


def _write_outputs(output_dir: Path, payload: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "shot_plan.json").write_text(json.dumps(payload["shot_plan"], indent=2))
    (output_dir / "render_queue.json").write_text(json.dumps(payload["render_queue"], indent=2))
    summary = {
        "grid_slots": payload["grid_slots"],
        "project": payload["project"],
        "shot_count": len(payload["shot_plan"]),
    }
    (output_dir / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))


def run_pipeline_agent(
    manifest_path: Path,
    story_bible_path: Path,
    concept: str,
    project_slug: str,
    characters: Optional[List[str]] = None,
    settings: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """High-level helper used by CLI and API endpoints."""
    manifest = json.loads(manifest_path.read_text())
    settings = settings or {}
    payload = build_shot_plan(
        manifest=manifest,
        story_bible_path=story_bible_path,
        concept=concept,
        project_slug=project_slug,
        characters=characters,
        settings=settings,
    )
    target_dir = output_dir or manifest_path.parent / "pipeline_outputs"
    _write_outputs(target_dir, payload)
    payload["output_dir"] = str(target_dir)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pipeline agent to build shot plans.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--story-bible", required=True, help="Path to story bible JSON")
    parser.add_argument("--concept", required=True, help="Episode/scene concept string")
    parser.add_argument("--project", required=True, help="Project slug (e.g., ravencroft_manor)")
    parser.add_argument("--characters", help="Comma-separated default characters")
    parser.add_argument("--settings", help="Optional JSON string of settings overrides")
    parser.add_argument("--output", help="Directory for shot_plan/render_queue JSON")
    parser.add_argument("--auto-generate-assets", action="store_true", help="Automatically register missing characters/locations/anchors")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    story_bible_path = Path(args.story_bible)
    default_characters = None
    if args.characters:
        default_characters = [c.strip() for c in args.characters.split(",") if c.strip()]
    settings = json.loads(args.settings) if args.settings else {}
    if args.auto_generate_assets:
        settings["auto_generate_missing_assets"] = True

    payload = run_pipeline_agent(
        manifest_path=manifest_path,
        story_bible_path=story_bible_path,
        concept=args.concept,
        project_slug=args.project,
        characters=default_characters,
        settings=settings,
        output_dir=Path(args.output) if args.output else None,
    )
    print(json.dumps({"status": "success", **payload}, indent=2))


if __name__ == "__main__":
    main()
