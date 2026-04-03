"""
ATLAS Pipeline Wiring — V25.4
=============================
Single module that connects ALL brain modules to the production pipeline.

PROBLEM: V24/V25 brain modules exist and pass tests but are NOT wired into
the actual generation pipeline. The Film Engine, Creative Prompt Compiler,
Shot Authority, Continuity Memory, Vision Analyst — all tested, all disconnected.

SOLUTION: This module provides 5 pipeline hooks that orchestrator_server.py
calls at specific points. Each hook calls the relevant brain modules with
proper error handling (non-blocking per doctrine).

PIPELINE HOOKS:
  1. wire_fix_v16_final_compile(shot, context) — After enrichment, before save
     Calls: Film Engine compile + CPC decontaminate + camera token translate

  2. wire_pre_generation_gate(shots, project_path, cast_map) — Before FAL calls
     Calls: Shot Authority contracts + Meta Director readiness

  3. wire_post_generation_qa(shot, frame_path, project_path, cast_map) — After each frame
     Calls: Vision Analyst scoring

  4. wire_continuity_chain(shot, prev_shot, project_path, cast_map) — During chain pipeline
     Calls: Continuity Memory spatial state + reframe candidates

  5. wire_pre_stitch_editorial(shots, project_path) — Before FFmpeg stitch
     Calls: Editorial Intelligence cut/hold/overlay decisions

Each hook returns a WiringResult with:
  - success: bool
  - mutations: dict of what was changed
  - warnings: list of non-blocking issues
  - errors: list of failures (logged, not raised)

DOCTRINE: All hooks are NON-BLOCKING. If ANY brain module throws an exception,
the hook logs it and returns success=True with the error recorded. The pipeline
continues. This is the immune system — it helps, it never blocks.

LAW 235: NO camera brand names in ANY prompt path.
LAW 236: Creative Prompt Compiler is the IMMUNE SYSTEM.
LAW 237: is_prompt_generic() is the diagnostic.
LAW 239: EMOTION_PHYSICAL_MAP maps emotion×posture to PHYSICAL verbs.
LAW 211: FAL nano-banana-pro does NOT accept guidance_scale or num_inference_steps.
LAW 213: Shot Authority is NON-BLOCKING.
"""

import logging
import time
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger("atlas.pipeline_wiring")

# ============================================================================
# WIRING RESULT
# ============================================================================

@dataclass
class WiringResult:
    """Result from a pipeline wiring hook."""
    success: bool = True
    mutations: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)

    def merge(self, other: "WiringResult"):
        """Merge another result into this one."""
        self.mutations.update(other.mutations)
        self.warnings.extend(other.warnings)
        self.errors.extend(other.errors)
        self.timings.update(other.timings)
        if other.errors:
            # Errors are recorded but don't fail the pipeline
            pass


# ============================================================================
# HOOK 1: FIX-V16 FINAL COMPILE
# ============================================================================
# Called AFTER all enrichment layers (enforcement agent, cinematic enricher,
# scene anchors, beat fidelity, wardrobe/extras) and BEFORE saving shot_plan.
#
# This is the LAST CHANCE to fix prompts before they're persisted.
# It replaces the old pattern of "enrich then sanitize" with
# "enrich then COMPILE through the brain."

def wire_fix_v16_final_compile(shot: Dict, context: Dict) -> WiringResult:
    """
    Final compilation hook for fix-v16 pipeline.

    Args:
        shot: The shot dict (mutated in place)
        context: {
            "genre": str,
            "cast_map": dict,
            "scene_manifest": dict,
            "project_path": str or Path,
            "story_bible": dict (optional),
        }

    Returns:
        WiringResult with mutations applied to shot
    """
    result = WiringResult()
    shot_id = shot.get("shot_id", "unknown")

    # --- Step 1: Camera Token Translation (Law 235) ---
    t0 = time.time()
    try:
        from tools.film_engine import translate_camera_tokens
        genre = context.get("genre", "gothic_horror")

        for field_name in ["nano_prompt", "nano_prompt_final"]:
            text = shot.get(field_name, "")
            if not text:
                continue
            cleaned = translate_camera_tokens(text, genre)
            if cleaned != text:
                shot[field_name] = cleaned
                result.mutations[f"{shot_id}.{field_name}.camera_tokens_stripped"] = True

        result.timings["camera_token_translate"] = time.time() - t0
    except ImportError:
        result.warnings.append("film_engine not available — camera token translation skipped")
    except Exception as e:
        result.errors.append(f"camera_token_translate failed: {e}")

    # --- Step 2: Creative Prompt Compiler Decontamination (Law 236) ---
    t0 = time.time()
    try:
        from tools.creative_prompt_compiler import (
            decontaminate_prompt,
            is_prompt_generic,
            get_physical_direction
        )

        characters = shot.get("characters") or []
        emotion = shot.get("emotion", "neutral")
        posture = shot.get("posture", "standing")

        for field_name in ["nano_prompt", "nano_prompt_final"]:
            text = shot.get(field_name, "")
            if not text:
                continue

            # Decontaminate: strip generic patterns, inject physical replacements
            char_name = characters[0] if characters else ""
            cleaned = decontaminate_prompt(text, character=char_name, emotion=emotion)
            if cleaned != text:
                shot[field_name] = cleaned
                result.mutations[f"{shot_id}.{field_name}.cpc_decontaminated"] = True

            # Diagnostic: flag if still generic after decontamination
            if characters and is_prompt_generic(cleaned):
                result.warnings.append(
                    f"{shot_id}.{field_name}: STILL GENERIC after decontamination — "
                    f"may produce frozen video"
                )

        # For LTX motion prompt — inject physical direction if empty/generic
        ltx = shot.get("ltx_motion_prompt", "")
        if characters and ltx:
            if is_prompt_generic(ltx):
                phys = get_physical_direction(emotion, posture)
                if phys and phys not in ltx:
                    shot["ltx_motion_prompt"] = ltx.rstrip(". ") + f". {phys}"
                    result.mutations[f"{shot_id}.ltx.physical_direction_injected"] = True

        result.timings["cpc_decontaminate"] = time.time() - t0
    except ImportError:
        result.warnings.append("creative_prompt_compiler not available — decontamination skipped")
    except Exception as e:
        result.errors.append(f"cpc_decontaminate failed: {e}")

    # --- Step 3: Film Engine Compile (V24 brain cortex) ---
    t0 = time.time()
    try:
        from tools.film_engine import compile_shot_for_model

        cast_map = context.get("cast_map", {})
        fe_context = {
            "genre": context.get("genre", "gothic_horror"),
            "cast_map": cast_map,
            "scene_manifest": context.get("scene_manifest", {}),
        }

        compiled = compile_shot_for_model(shot, fe_context)

        if compiled:
            # Film Engine produces compiled prompts — use them as nano_prompt_final
            # V26.2 FIX: Film Engine returns "nano_prompt" and "ltx_motion_prompt", NOT "_compiled" suffix
            nano_compiled = compiled.get("nano_prompt", "")
            ltx_compiled = compiled.get("ltx_motion_prompt", "")

            existing_final = shot.get("nano_prompt_final", "")

            # Use Film Engine output if it's substantive (>50 chars)
            # Film Engine outputs are CLEANER (no stacking) so they may be shorter — that's OK
            if nano_compiled and len(nano_compiled) >= 50:
                shot["nano_prompt_final"] = nano_compiled
                shot["nano_prompt_v24"] = nano_compiled  # V26.2: generate-first-frames reads this
                shot["_film_engine_compiled"] = True
                result.mutations[f"{shot_id}.nano_prompt_final.film_engine_compiled"] = True

            if ltx_compiled and len(ltx_compiled) > len(shot.get("ltx_motion_prompt", "")):
                shot["ltx_motion_prompt"] = ltx_compiled
                shot["ltx_motion_prompt_v24"] = ltx_compiled  # V26.2: render-videos reads this
                result.mutations[f"{shot_id}.ltx.film_engine_compiled"] = True

            # Store negative prompt separately (V26.1 Law T2-FE-1)
            neg = compiled.get("_negative_prompt", "")
            if neg:
                shot["_negative_prompt"] = neg
                result.mutations[f"{shot_id}.negative_prompt_separated"] = True

            # Copy any injected flags
            if compiled.get("_continuity_injected"):
                result.mutations[f"{shot_id}.continuity_delta_injected"] = True
            if compiled.get("_broll_continuity_injected"):
                result.mutations[f"{shot_id}.broll_continuity_injected"] = True

        result.timings["film_engine_compile"] = time.time() - t0
    except ImportError:
        result.warnings.append("film_engine not available — compile skipped")
    except Exception as e:
        result.errors.append(f"film_engine_compile failed: {e}")

    # --- Step 4: Final Validation ---
    # Verify no camera brands survived
    for field_name in ["nano_prompt", "nano_prompt_final", "ltx_motion_prompt"]:
        text = shot.get(field_name, "")
        if not text:
            continue
        # Check for Law 235 violations
        brands = re.findall(
            r'(?i)(ARRI\s+Alexa|RED\s+(?:Monstro|DSMC)|Sony\s+Venice|Panavision|Cooke\s+S[47])',
            text
        )
        if brands:
            result.warnings.append(
                f"{shot_id}.{field_name}: Camera brand survived compilation: {brands}"
            )
            # Auto-strip as safety net
            for brand in brands:
                text = re.sub(re.escape(brand) + r'[^,.\n]*[,.]?\s*', '', text)
            shot[field_name] = re.sub(r',\s*,', ',', text).strip()
            result.mutations[f"{shot_id}.{field_name}.brand_safety_net"] = True

    return result


# ============================================================================
# HOOK 2: PRE-GENERATION GATE
# ============================================================================
# Called BEFORE any FAL API calls. Returns per-shot authority contracts
# that dictate resolution, ref cap, quality tier.

def wire_pre_generation_gate(
    shots: List[Dict],
    project_path: str,
    cast_map: Dict
) -> WiringResult:
    """
    Pre-generation gate: Shot Authority + Meta Director readiness.

    Returns WiringResult with mutations dict containing per-shot contracts:
      mutations["shot_contracts"] = {shot_id: ShotContract}
      mutations["readiness"] = {shot_id: ReadinessResult}
    """
    result = WiringResult()

    # --- Shot Authority Contracts ---
    t0 = time.time()
    try:
        from tools.shot_authority import build_shot_contract, pre_authorize_scene

        contracts = {}
        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")
            try:
                # Resolve ref_urls from cast_map for this shot's characters
                _chars = shot.get("characters") or []
                _ref_urls = []
                for _c in _chars:
                    _c_name = _c if isinstance(_c, str) else str(_c)
                    _c_entry = cast_map.get(_c_name, {})
                    _ref = _c_entry.get("character_reference_url") or _c_entry.get("reference_url") or _c_entry.get("headshot_url", "")
                    if _ref:
                        _ref_urls.append(_ref)
                contract = build_shot_contract(shot, cast_map, _ref_urls)
                # Serialize contract to dict for JSON-safe storage
                _cd = {
                    "resolution": contract.fal_params.get("resolution", "1K") if hasattr(contract, 'fal_params') and contract.fal_params else "1K",
                    "max_refs": contract.fal_params.get("max_refs", 5) if hasattr(contract, 'fal_params') and contract.fal_params else 5,
                    "num_candidates": contract.fal_params.get("_num_candidates", 1) if hasattr(contract, 'fal_params') and contract.fal_params else 1,
                    "quality_tier": getattr(contract, 'quality_tier', 'production'),
                    "authority_score": getattr(contract, 'authority_score', 0.5),
                }
                contracts[shot_id] = _cd

                # Apply contract params to shot for downstream use
                shot["_authority_resolution"] = _cd["resolution"]
                shot["_authority_max_refs"] = _cd["max_refs"]
                shot["_authority_quality_tier"] = _cd["quality_tier"]
                shot["_num_candidates"] = _cd["num_candidates"]

            except Exception as e:
                result.warnings.append(f"Shot authority failed for {shot_id}: {e}")
                # Default contract
                shot["_authority_resolution"] = "1K"
                shot["_authority_max_refs"] = 5
                shot["_authority_quality_tier"] = "production"

        result.mutations["shot_contracts"] = contracts
        result.timings["shot_authority"] = time.time() - t0

    except ImportError:
        result.warnings.append("shot_authority not available — using defaults")
        for shot in shots:
            shot["_authority_resolution"] = "1K"
            shot["_authority_max_refs"] = 5
            shot["_authority_quality_tier"] = "production"
    except Exception as e:
        result.errors.append(f"shot_authority gate failed: {e}")

    # --- Meta Director Readiness ---
    t0 = time.time()
    try:
        from tools.meta_director import MetaDirector

        md = MetaDirector(project_path)
        readiness = {}

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")
            scene_id = shot.get("scene_id", "")
            try:
                ready = md.check_shot_readiness(shot, {"scene_id": scene_id})
                readiness[shot_id] = ready

                # Store readiness verdict on shot
                if hasattr(ready, 'ready'):
                    shot["_meta_director_ready"] = ready.ready
                elif isinstance(ready, dict):
                    shot["_meta_director_ready"] = ready.get("ready", True)
                else:
                    shot["_meta_director_ready"] = bool(ready)

            except Exception as e:
                result.warnings.append(f"Meta Director readiness check failed for {shot_id}: {e}")
                shot["_meta_director_ready"] = True  # Non-blocking default

        result.mutations["readiness"] = readiness
        result.timings["meta_director"] = time.time() - t0

    except ImportError:
        result.warnings.append("meta_director not available — readiness checks skipped")
    except Exception as e:
        result.errors.append(f"meta_director gate failed: {e}")

    return result


# ============================================================================
# HOOK 3: POST-GENERATION QA
# ============================================================================
# Called AFTER each frame is generated. Scores visual health.

def wire_post_generation_qa(
    shot: Dict,
    frame_path: str,
    project_path: str,
    cast_map: Dict
) -> WiringResult:
    """
    Post-generation QA: Vision Analyst 8-dimension scoring.

    Returns WiringResult with mutations containing vision scores.
    """
    result = WiringResult()

    if not frame_path or not Path(frame_path).exists():
        result.warnings.append(f"Frame not found at {frame_path} — QA skipped")
        return result

    t0 = time.time()
    try:
        from tools.vision_analyst import VisionAnalyst

        va = VisionAnalyst(project_path)
        # Score the generated frame across 8 dimensions
        # This is advisory — scores are stored but don't block
        scores = {}

        shot_id = shot.get("shot_id", "unknown")
        characters = shot.get("characters") or []

        # Use vision analyst's scoring if available
        if hasattr(va, 'analyze_frame'):
            analysis = va.analyze_frame(frame_path, shot, cast_map)
            if analysis:
                scores = analysis if isinstance(analysis, dict) else {"overall": analysis}
        elif hasattr(va, 'score_frame'):
            score = va.score_frame(frame_path, shot, cast_map)
            if score:
                scores = score if isinstance(score, dict) else {"overall": score}

        if scores:
            shot["_vision_scores"] = scores
            result.mutations[f"{shot_id}.vision_scores"] = scores

            # Flag low scores as warnings
            overall = scores.get("overall", 1.0)
            if isinstance(overall, (int, float)) and overall < 0.5:
                result.warnings.append(
                    f"{shot_id}: Low vision score ({overall:.2f}) — may need regeneration"
                )

        result.timings["vision_analyst"] = time.time() - t0

    except ImportError:
        result.warnings.append("vision_analyst not available — post-gen QA skipped")
    except Exception as e:
        result.errors.append(f"vision_analyst QA failed: {e}")

    return result


# ============================================================================
# HOOK 4: CONTINUITY CHAIN
# ============================================================================
# Called during master chain pipeline between shots.

def wire_continuity_chain(
    shot: Dict,
    prev_shot: Optional[Dict],
    project_path: str,
    cast_map: Dict,
    scene_context: Optional[Dict] = None
) -> WiringResult:
    """
    Continuity chain hook: spatial state + reframe candidates.

    Returns WiringResult with:
      mutations["spatial_state"] = extracted spatial state
      mutations["reframe_candidates"] = list of candidates
      mutations["continuity_delta"] = compiled delta prompt
    """
    result = WiringResult()
    shot_id = shot.get("shot_id", "unknown")

    if not prev_shot:
        result.warnings.append(f"{shot_id}: No previous shot — first in chain, skipping continuity")
        return result

    # --- Extract spatial state from previous shot ---
    t0 = time.time()
    try:
        from tools.continuity_memory import (
            ContinuityMemory,
            extract_spatial_state_from_metadata,
            generate_reframe_candidates,
            compile_continuity_delta
        )

        # Extract spatial state from the previous shot
        prev_state = extract_spatial_state_from_metadata(prev_shot, cast_map)
        if prev_state:
            result.mutations["spatial_state"] = prev_state

        # Generate reframe candidates for current shot
        candidates = generate_reframe_candidates(
            shot, prev_state,
            cast_map=cast_map,
            scene_context=scene_context or {}
        )
        if candidates:
            result.mutations["reframe_candidates"] = candidates

            # Compile delta from best candidate
            best = candidates[0] if candidates else None
            if best:
                delta = compile_continuity_delta(best, prev_state, shot)
                if delta:
                    result.mutations["continuity_delta"] = delta
                    # Inject delta into shot context for Film Engine
                    shot["_continuity_delta"] = delta

        # Store spatial state for persistence
        try:
            cm = ContinuityMemory(project_path)
            if prev_state:
                cm.store_shot_state(prev_shot.get("shot_id", ""), prev_state)
        except Exception as e:
            result.warnings.append(f"ContinuityMemory persistence failed: {e}")

        result.timings["continuity_chain"] = time.time() - t0

    except ImportError:
        result.warnings.append("continuity_memory not available — chain continuity skipped")
    except Exception as e:
        result.errors.append(f"continuity_chain failed: {e}")

    return result


# ============================================================================
# HOOK 5: PRE-STITCH EDITORIAL
# ============================================================================
# Called before FFmpeg stitch. Returns edit decisions.

def wire_pre_stitch_editorial(
    shots: List[Dict],
    project_path: str
) -> WiringResult:
    """
    Pre-stitch editorial hook: cut/hold/overlay decisions.

    Returns WiringResult with:
      mutations["editorial_plan"] = {shot_id: EditDecision}
      mutations["stitch_order"] = ordered list of shot_ids with editorial tags
    """
    result = WiringResult()

    t0 = time.time()
    try:
        from tools.editorial_intelligence import (
            score_cut_point,
            analyze_broll_overlays,
            compute_scene_asl_target,
            filter_shots_for_generation,
            classify_audio_transition
        )

        editorial_plan = {}

        for i, shot in enumerate(shots):
            shot_id = shot.get("shot_id", "unknown")
            prev_shot = shots[i-1] if i > 0 else None
            next_shot = shots[i+1] if i < len(shots) - 1 else None

            try:
                # Score the cut point between this shot and previous
                if prev_shot:
                    cut_score = score_cut_point(prev_shot, shot)
                    editorial_plan[shot_id] = {
                        "cut_score": cut_score,
                        "action": "cut" if cut_score > 0.45 else "hold",
                    }

                    # Classify audio transition
                    audio_trans = classify_audio_transition(prev_shot, shot)
                    editorial_plan[shot_id]["audio_transition"] = audio_trans
                else:
                    editorial_plan[shot_id] = {"cut_score": 1.0, "action": "cut"}

            except Exception as e:
                result.warnings.append(f"Editorial scoring failed for {shot_id}: {e}")
                editorial_plan[shot_id] = {"cut_score": 0.5, "action": "cut"}

        # Analyze B-roll overlay opportunities
        try:
            overlays = analyze_broll_overlays(shots)
            if overlays:
                for overlay in overlays:
                    sid = overlay.get("shot_id", "")
                    if sid in editorial_plan:
                        editorial_plan[sid]["overlay"] = overlay
        except Exception:
            pass

        result.mutations["editorial_plan"] = editorial_plan
        result.timings["editorial"] = time.time() - t0

    except ImportError:
        result.warnings.append("editorial_intelligence not available — editorial planning skipped")
    except Exception as e:
        result.errors.append(f"editorial planning failed: {e}")

    return result


# ============================================================================
# CONVENIENCE: FULL PIPELINE STATUS
# ============================================================================

def get_wiring_status() -> Dict:
    """
    Returns the current wiring status of all brain modules.
    Useful for health checks and debugging.
    """
    status = {}

    modules = {
        "film_engine": ("tools.film_engine", ["compile_shot_for_model", "translate_camera_tokens"]),
        "creative_prompt_compiler": ("tools.creative_prompt_compiler", ["decontaminate_prompt", "is_prompt_generic", "get_physical_direction"]),
        "continuity_memory": ("tools.continuity_memory", ["ContinuityMemory", "extract_spatial_state_from_metadata", "generate_reframe_candidates"]),
        "shot_authority": ("tools.shot_authority", ["build_shot_contract", "pre_authorize_scene"]),
        "basal_ganglia": ("tools.basal_ganglia_engine", ["BasalGangliaEngine"]),
        "meta_director": ("tools.meta_director", ["MetaDirector"]),
        "vision_analyst": ("tools.vision_analyst", ["VisionAnalyst"]),
        "editorial_intelligence": ("tools.editorial_intelligence", ["score_cut_point", "filter_shots_for_generation"]),
        "doctrine_engine": ("tools.doctrine_engine", []),
    }

    for name, (module_path, functions) in modules.items():
        try:
            mod = __import__(module_path, fromlist=functions or ["__name__"])
            available_fns = [f for f in functions if hasattr(mod, f)]
            status[name] = {
                "available": True,
                "functions": available_fns,
                "missing": [f for f in functions if f not in available_fns],
            }
        except ImportError as e:
            status[name] = {
                "available": False,
                "error": str(e),
            }
        except Exception as e:
            status[name] = {
                "available": False,
                "error": f"Load error: {e}",
            }

    return status


# ============================================================================
# WIRING REPORT (for logging/debugging)
# ============================================================================

def format_wiring_report(result: WiringResult, hook_name: str) -> str:
    """Format a WiringResult as a human-readable report string."""
    lines = [f"[WIRING:{hook_name}] success={result.success}"]

    if result.mutations:
        lines.append(f"  Mutations ({len(result.mutations)}):")
        for k, v in list(result.mutations.items())[:10]:
            lines.append(f"    {k}: {v}")
        if len(result.mutations) > 10:
            lines.append(f"    ... and {len(result.mutations) - 10} more")

    if result.warnings:
        lines.append(f"  Warnings ({len(result.warnings)}):")
        for w in result.warnings[:5]:
            lines.append(f"    ⚠️  {w}")

    if result.errors:
        lines.append(f"  Errors ({len(result.errors)}):")
        for e in result.errors[:5]:
            lines.append(f"    ❌ {e}")

    if result.timings:
        total = sum(result.timings.values())
        lines.append(f"  Timings (total={total:.3f}s):")
        for k, v in result.timings.items():
            lines.append(f"    {k}: {v:.3f}s")

    return "\n".join(lines)
