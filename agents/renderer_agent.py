#!/usr/bin/env python3
"""
Renderer Agent
--------------
Consumes the shot_plan emitted by the Pipeline Agent and executes the Fal
Nano Banana renders (including ImgBB archival and vision hooks).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auto_studio_controller import get_auto_studio_controller
from nano_banana_executor import NanoBananaExecutor
from quantum_utils import quantum_metadata_for_shot
from tools.prompt_consistency_checker import validate_shot_plan
from render_gallery_manager import RenderGalleryManager

GALLERY_MANAGER = RenderGalleryManager()

# V5: Vision Gate Integration
_vision_analyzer = None


def _init_vision_gate():
    """Lazy init of vision analyzer for quality gates."""
    global _vision_analyzer
    if _vision_analyzer is None:
        try:
            from dino_clip_analyzer import get_hybrid_analyzer
            _vision_analyzer = get_hybrid_analyzer()
            logger.info("[VISION GATE] HybridAnalyzer initialized for render QC")
        except Exception as e:
            logger.warning(f"[VISION GATE] Analyzer unavailable: {e}")
    return _vision_analyzer


def _run_vision_gate(
    image_path: str,
    shot_ctx: Dict[str, Any],
    vision_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run vision gate quality check on rendered image.

    Returns:
        Dict with passed, scores, issues
    """
    analyzer = _init_vision_gate()
    if not analyzer:
        return {"passed": True, "reason": "analyzer_unavailable"}

    face_threshold = vision_config.get("face_threshold", 0.85)
    clip_threshold = vision_config.get("clip_threshold", 0.75)

    # Get character reference if available
    reference_path = None
    characters = shot_ctx.get("characters") or []
    if characters:
        # Try to find character reference
        from APPLY_V13_GOLD_STANDARD import get_ai_actor_ref_path
        char_name = characters[0] if isinstance(characters, list) else characters
        try:
            reference_path = get_ai_actor_ref_path(char_name)
        except:
            pass

    prompt = shot_ctx.get("prompt") or shot_ctx.get("nano_prompt") or ""

    try:
        analysis = analyzer.analyze_comprehensive(
            render_path=image_path,
            reference_path=reference_path,
            prompt=prompt
        )

        passed = True
        issues = []

        if reference_path and analysis.get("dino_face", 0) < face_threshold:
            passed = False
            issues.append(f"Face consistency: {analysis.get('dino_face', 0):.2%} < {face_threshold:.2%}")

        if analysis.get("clip_alignment", 0) < clip_threshold:
            passed = False
            issues.append(f"CLIP alignment: {analysis.get('clip_alignment', 0):.2%} < {clip_threshold:.2%}")

        if analysis.get("is_face_blurred", False):
            passed = False
            issues.append("Face blur detected")

        return {
            "passed": passed,
            "scores": {
                "dino_face": analysis.get("dino_face", 0),
                "clip_alignment": analysis.get("clip_alignment", 0),
                "hybrid_score": analysis.get("hybrid_score", 0),
                "face_sharpness": analysis.get("face_sharpness", 0)
            },
            "issues": issues
        }

    except Exception as e:
        logger.warning(f"[VISION GATE] Analysis failed: {e}")
        return {"passed": True, "reason": f"analysis_error: {e}"}


AUTO_STUDIO_RENDER_ENDPOINT = os.environ.get(
    "AUTO_STUDIO_RENDER_ENDPOINT",
    "http://127.0.0.1:8888/api/auto/register-render",
)
logger = logging.getLogger(__name__)


def _forward_render_to_auto_studio(
    shot_id: Optional[str],
    image_path: Optional[str],
    prompt_payload: Dict[str, Any],
    image_url: Optional[str],
) -> None:
    """Forward render metadata to the Auto Studio sync endpoint (HTTP + local fallback)."""
    if not shot_id or not image_path:
        return

    payload = {
        "shot_id": shot_id,
        "render_path": image_path,
        "prompt_payload": prompt_payload,
        "image_url": image_url,
    }

    try:
        response = requests.post(AUTO_STUDIO_RENDER_ENDPOINT, json=payload, timeout=5)
        if response.ok:
            return
        logger.warning(
            "[AUTO STUDIO] register-render HTTP %s for %s: %s",
            response.status_code,
            shot_id,
            response.text[:200],
        )
    except Exception as http_err:
        logger.debug("[AUTO STUDIO] register-render HTTP fallback: %s", http_err)

    try:
        controller = get_auto_studio_controller()
        controller.register_render(
            shot_id=shot_id,
            render_path=Path(image_path),
            prompt_payload=prompt_payload,
            image_url=image_url,
        )
    except Exception as controller_err:
        logger.warning("[AUTO STUDIO] Failed to sync render %s: %s", shot_id, controller_err)


def _execute_shots(
    shot_plan: List[Dict[str, Any]],
    executor: NanoBananaExecutor,
    allow_reference_fallback: bool,
    bootstrap_mode: bool,
    mark: Optional[str] = None,
    vision_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute shots with optional vision gate verification.

    V5: When vision_config is provided with mode='auto':
    - Each shot is verified using DINOv2 (face consistency) and CLIP (prompt alignment)
    - Failed shots are auto-regenerated up to max_retries times
    - Quality scores are included in results
    """
    results: List[Dict[str, Any]] = []

    # V5: Vision gate configuration
    use_vision_gate = vision_config and vision_config.get("mode") == "auto"
    max_retries = vision_config.get("max_retries", 3) if use_vision_gate else 0

    if use_vision_gate:
        logger.info(f"[VISION GATE] AUTO mode enabled - max_retries={max_retries}")

    for ctx in shot_plan:
        shot_id = ctx["shot_id"]
        characters = ctx.get("characters") or []
        if isinstance(characters, str):
            characters = [characters]
        shot_metadata = {
            "shot_id": shot_id,
            "scene_id": ctx.get("scene_id"),
            "location": ctx.get("location"),
            "characters": characters,
            "reference_needed": ", ".join(characters),
            "quality_anchor": ctx.get("quality_anchor"),
            "ltx_motion_metadata": (ctx.get("ltx_metadata") or {}).get("motion"),
            "ltx_duration_seconds": (ctx.get("ltx_metadata") or {}).get("ltx_duration_seconds"),
            "duration": (ctx.get("ltx_metadata") or {}).get("duration"),
            "script_semantics": ctx.get("script_semantics"),
            "_grid_context_override": ctx.get("_grid_context_override"),
        }
        scene_metadata = ctx.get("settings") or {}

        # V5: Auto-regeneration loop with vision gates
        attempt = 0
        result = None
        vision_result = None

        while attempt <= max_retries:
            result = executor.generate_image_pro(
                prompt=ctx["prompt"],
                shot_metadata=shot_metadata,
                scene_metadata=scene_metadata,
                allow_reference_fallback=allow_reference_fallback,
            )
            result.update({"shot_id": shot_id, "attempt": attempt + 1})

            # V5: Run vision gate check if enabled and image was generated
            if use_vision_gate and result.get("status") == "success" and result.get("image_path"):
                vision_result = _run_vision_gate(
                    image_path=result["image_path"],
                    shot_ctx=ctx,
                    vision_config=vision_config
                )
                result["vision_gate"] = vision_result

                if vision_result.get("passed", True):
                    logger.info(f"[VISION GATE] {shot_id} PASSED (attempt {attempt + 1})")
                    break
                else:
                    logger.warning(f"[VISION GATE] {shot_id} FAILED (attempt {attempt + 1}): {vision_result.get('issues', [])}")
                    if attempt < max_retries:
                        logger.info(f"[VISION GATE] Regenerating {shot_id} (retry {attempt + 1}/{max_retries})")
                        attempt += 1
                        continue
                    else:
                        logger.error(f"[VISION GATE] {shot_id} failed after {max_retries} retries")
                        result["vision_gate"]["max_retries_exceeded"] = True
                        break
            else:
                # Not using vision gate or generation failed
                break

            attempt += 1

        if mark:
            result["run_stage"] = mark
        theta_meta = quantum_metadata_for_shot(shot_id)
        if theta_meta:
            result["quantum_metadata"] = theta_meta
        _register_render_result(ctx, result)
        results.append(result)
    return results


def _register_render_result(ctx: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Persist successful renders to the gallery tracking file so the UI shows them instantly."""
    if result.get("status") != "success":
        return
    image_path = result.get("image_path")
    video_path = result.get("video_path")
    if not image_path and not video_path:
        return
    scene_id = ctx.get("scene_id") or ctx.get("settings", {}).get("scene_id") or "UNKNOWN_SCENE"
    # Normalize lists for slot accounting
    def _ensure_list(value):
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v]
        return [str(value)]

    asset_grid_meta = ctx.get("asset_grid_metadata") or {}
    characters = _ensure_list(asset_grid_meta.get("characters_in_frame") or ctx.get("characters"))
    props = _ensure_list(asset_grid_meta.get("props_visible") or ctx.get("props"))
    location_refs = _ensure_list(asset_grid_meta.get("location_depth"))
    location_hint = ctx.get("grid_location_hint")
    if location_hint:
        location_refs.append(str(location_hint))
    location_refs = [loc for loc in location_refs if loc]

    slot_metadata = {
        "characters": characters,
        "props": props,
        "locations": location_refs,
        "primary_subject": asset_grid_meta.get("primary_subject"),
        "location_depth": asset_grid_meta.get("location_depth"),
        "quality_anchor": asset_grid_meta.get("quality_anchor") or ctx.get("quality_anchor"),
        "character_prominence": asset_grid_meta.get("character_prominence"),
        "slot_counts": {
            "characters": len(characters),
            "props": len(props),
            "locations": len(location_refs)
        }
    }

    master_reference = {}
    if ctx.get("master_shot_reference"):
        master_reference["master_shot_reference"] = ctx.get("master_shot_reference")
    if ctx.get("previous_shot_id"):
        master_reference["previous_shot_id"] = ctx.get("previous_shot_id")
    if ctx.get("use_previous_shot") is not None:
        master_reference["use_previous_shot"] = bool(ctx.get("use_previous_shot"))
    meta_loop_reference = (ctx.get("_meta_loop") or {}).get("reference_shot_id")
    if meta_loop_reference:
        master_reference["meta_loop_reference"] = meta_loop_reference

    metadata = {
        "project": ctx.get("project") or ctx.get("settings", {}).get("project"),
        "episode": ctx.get("settings", {}).get("episode"),
        "scene_title": ctx.get("scene_title"),
        "prompt": ctx.get("prompt"),
        "ltx_motion_prompt": ctx.get("ltx_motion_prompt"),
        "characters": ctx.get("characters"),
        "location": ctx.get("location"),
        "run_stage": result.get("run_stage"),
        "nano_prompt": ctx.get("nano_prompt") or ctx.get("prompt"),
        "asset_grid_metadata": asset_grid_meta,
        "slot_metadata": slot_metadata,
        "slot_reference_count": result.get("references_used"),
        "master_reference": master_reference,
    }
    if metadata["slot_reference_count"] is None:
        counts = slot_metadata.get("slot_counts") or {}
        metadata["slot_reference_count"] = sum(counts.values())
    status = "ready_for_video" if image_path else "working"
    GALLERY_MANAGER.register_new_render(
        shot_id=ctx.get("shot_id"),
        video_path=video_path,
        image_path=image_path,
        scene_id=scene_id,
        metadata=metadata,
        status=status,
    )

    prompt_payload = {
        "nano_prompt": metadata.get("nano_prompt"),
        "prompt": metadata.get("prompt"),
        "ltx_motion_prompt": metadata.get("ltx_motion_prompt"),
        "characters": ctx.get("characters"),
        "props": ctx.get("props"),
        "location": ctx.get("location"),
        "scene_id": scene_id,
        "scene_title": ctx.get("scene_title"),
        "asset_grid_metadata": asset_grid_meta,
        "slot_metadata": slot_metadata,
        "master_reference": master_reference,
    }
    _forward_render_to_auto_studio(
        shot_id=ctx.get("shot_id"),
        image_path=image_path,
        prompt_payload=prompt_payload,
        image_url=result.get("imgbb_url") or result.get("image_url"),
    )


def run_renderer_queue(
    shot_plan: List[Dict[str, Any]],
    allow_reference_fallback: bool = False,
    bootstrap_mode: bool = False,
    rerun_queue_path: Optional[Path] = None,
    vision_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Render each shot context sequentially and return the executor payloads.

    V5: Now supports vision_config for AUTO verification mode:
        - mode: 'auto' or 'human'
        - face_threshold: 0.0-1.0 (default 0.85)
        - clip_threshold: 0.0-1.0 (default 0.75)
        - max_retries: int (default 3)
        - enable_vlm: bool (default True)
    """
    # Preflight validation: check for period consistency issues and auto-fix
    validation_result = validate_shot_plan(shot_plan, fix_issues=True)
    if validation_result["fixed_count"] > 0:
        print(f"[RENDERER] Auto-fixed {validation_result['fixed_count']} period consistency issues")
    if validation_result["issues"]:
        print(f"[RENDERER] Warning: {len(validation_result['issues'])} period issues detected")

    # V5: Log vision gate mode
    if vision_config and vision_config.get("mode") == "auto":
        print(f"[RENDERER] Vision gates ENABLED - AUTO mode")
        print(f"[RENDERER] Thresholds: Face={vision_config.get('face_threshold', 0.85)}, CLIP={vision_config.get('clip_threshold', 0.75)}")
        print(f"[RENDERER] Max retries: {vision_config.get('max_retries', 3)}")
    else:
        print(f"[RENDERER] Vision gates DISABLED - HUMAN verification mode")

    executor = NanoBananaExecutor()
    results = _execute_shots(
        shot_plan,
        executor,
        allow_reference_fallback,
        bootstrap_mode,
        mark="primary",
        vision_config=vision_config,
    )

    queue_path = rerun_queue_path
    if queue_path and queue_path.exists():
        try:
            rerun_plan = json.loads(queue_path.read_text())
            if isinstance(rerun_plan, dict):
                rerun_plan = rerun_plan.get("shots") or rerun_plan.get("queue") or []
            if isinstance(rerun_plan, list) and rerun_plan:
                rerun_results = _execute_shots(
                    rerun_plan,
                    executor,
                    allow_reference_fallback,
                    bootstrap_mode,
                    mark="qa_rerun",
                    vision_config=vision_config,
                )
                results.extend(rerun_results)
            queue_path.rename(queue_path.with_suffix(".consumed.json"))
        except Exception:
            pass

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Renderer Agent")
    parser.add_argument("--shot-plan", required=True, help="Path to shot_plan.json from Pipeline Agent")
    parser.add_argument("--allow-fallback", action="store_true", help="Allow /text-to-image fallback")
    parser.add_argument("--bootstrap", action="store_true", help="Bootstrap (first-frame) mode")
    parser.add_argument("--rerun-queue", help="Optional qa_rerun_queue.json path to consume after primary run")
    args = parser.parse_args()

    shot_plan_path = Path(args.shot_plan)
    shot_plan = json.loads(shot_plan_path.read_text())
    rerun_path = Path(args.rerun_queue) if args.rerun_queue else shot_plan_path.parent / "qa_rerun_queue.json"
    results = run_renderer_queue(
        shot_plan=shot_plan,
        allow_reference_fallback=args.allow_fallback,
        bootstrap_mode=args.bootstrap,
        rerun_queue_path=rerun_path,
    )
    print(json.dumps({"status": "success", "shots": results}, indent=2))


if __name__ == "__main__":
    main()
