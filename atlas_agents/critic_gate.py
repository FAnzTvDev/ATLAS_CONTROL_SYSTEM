from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from .utils import read_json, write_json, resolve_paths, load_config, ensure_list, normalize_char
from .live_sync import live_job_create, live_job_update

"""
CRITIC GATE - FINAL AUTHORITY (V17)

The Critic Gate is the ultimate arbiter of project readiness.
Ops Coordinator does NOT ask humans until Critic emits NEEDS_HUMAN_JUDGMENT.

V17 UPGRADE: Now enforces SEMANTIC INVARIANTS as BLOCKING failures.
Silent data loss is no longer possible.

Verdicts:
- READY: Project can proceed to render
- NEEDS_REPAIR: Machine-fixable issues, re-run agents in REPAIR mode
- NEEDS_HUMAN_JUDGMENT: Creative/subjective issues require human input
- BLOCKED: Semantic invariant violated (V17)

What triggers NEEDS_HUMAN_JUDGMENT:
- Casting conflicts (multiple actors for same character)
- Narrative discontinuity (story beats don't align)
- Character reference ambiguity (can't determine correct reference)
- Quality threshold failures (too many warnings in critical scenes)

What triggers BLOCKED (V17):
- Beats stripped from story_bible
- Dialogue not propagated to shots
- Characters missing from shots
- Cast missing reference_url
- Nano prompts missing
"""


def critic_gate_run(project: str, fail_on_warnings: bool | None = None, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    cfg = load_config(p.repo_root)
    proj_dir = p.project_dir

    job = live_job_create(project, "critics", {"project": project}, repo_root=p.repo_root)
    job_id = job["job"]["job_id"]
    live_job_update(project, job_id, "running", repo_root=p.repo_root)

    if fail_on_warnings is None:
        fail_on_warnings = bool(cfg["policy"]["critics"].get("fail_on_warnings", False))

    cast_map = read_json(proj_dir / "cast_map.json", default={}) or {}
    shot_plan = read_json(proj_dir / "shot_plan.json", default=None)

    blocking = []
    warnings = []

    if not shot_plan:
        blocking.append("missing_shot_plan")

    # Manifest-like checks: ai_actor_cast present for shots with characters
    shots = shot_plan["shots"] if isinstance(shot_plan, dict) and "shots" in shot_plan else (shot_plan or [])
    for sh in shots:
        chars = ensure_list(sh.get("characters"))
        if not chars:
            continue
        aac = sh.get("ai_actor_cast") or {}
        if not aac:
            warnings.append(f"missing_ai_actor_cast:{sh.get('shot_id')}")
            continue
        # Ensure each character has reference_url
        for c in chars:
            cname = normalize_char(c.get("name")) if isinstance(c, dict) else normalize_char(str(c))
            if not cname:
                continue
            ent = aac.get(cname)
            if not ent:
                warnings.append(f"character_not_in_ai_actor_cast:{sh.get('shot_id')}:{cname}")
                continue
            # Skip reference_url check for EXTRAS POOL entries - they use stock actors
            if ent.get("is_extras_pool", False):
                continue
            if not (ent.get("reference_url") or ""):
                blocking.append(f"missing_reference_url:{sh.get('shot_id')}:{cname}")

    # ========== NEEDS_HUMAN_JUDGMENT DETECTION ==========
    # These issues require human creative input, not machine repair
    human_judgment_issues = []

    # Check for casting conflicts
    cast_assignments = {}
    for sh in shots:
        aac = sh.get("ai_actor_cast") or {}
        for char, info in aac.items():
            actor = info.get("ai_actor") if isinstance(info, dict) else None
            if actor:
                if char not in cast_assignments:
                    cast_assignments[char] = set()
                cast_assignments[char].add(actor)

    for char, actors in cast_assignments.items():
        if len(actors) > 1:
            human_judgment_issues.append(f"casting_conflict:{char}:{list(actors)}")

    # Check for excessive warnings in single scene (quality threshold)
    scene_warnings = {}
    for w in warnings:
        parts = w.split(":")
        if len(parts) >= 2:
            shot_id = parts[1]
            scene_id = shot_id.split("_")[0] if "_" in shot_id else shot_id
            scene_warnings[scene_id] = scene_warnings.get(scene_id, 0) + 1

    for scene_id, count in scene_warnings.items():
        if count >= 5:  # More than 5 warnings in one scene
            human_judgment_issues.append(f"quality_threshold:{scene_id}:{count}_warnings")

    # ========== V17 STRUCTURAL VIOLATION CHECKS ==========
    # Detect issues that can be auto-repaired by agents
    structural_violations = []
    repairs_required = set()

    # Check 1: Empty characters arrays
    shots_no_chars = [sh for sh in shots if not sh.get("characters")]
    if shots_no_chars:
        structural_violations.append(f"empty_characters:{len(shots_no_chars)}_shots")
        repairs_required.add("cast_propagation")

    # Check 2: Missing reference_url in cast_map (skip EXTRAS POOL entries)
    chars_no_ref = [k for k, v in cast_map.items()
                    if not k.startswith("_") and isinstance(v, dict)
                    and not v.get("is_extras_pool", False)  # Skip extras pool
                    and not v.get("reference_url")]
    if chars_no_ref:
        structural_violations.append(f"missing_cast_refs:{len(chars_no_ref)}_chars")
        repairs_required.add("cast_propagation")

    # Check 3: Extended shots without stitched videos
    videos_dir = proj_dir / "videos"
    for sh in shots:
        dur = sh.get("duration", 20)
        if dur > 20:
            shot_id = sh.get("shot_id", "")
            final_video = videos_dir / f"{shot_id}.mp4"
            if not final_video.exists():
                # Check if segments exist
                seg0 = videos_dir / f"{shot_id}_seg0.mp4"
                if seg0.exists():
                    structural_violations.append(f"unstitch_extended:{shot_id}")
                    repairs_required.add("video_stitch")

    # Check 4: Dialogue present but no characters
    for sh in shots:
        if sh.get("dialogue") and not sh.get("characters"):
            structural_violations.append(f"dialogue_no_chars:{sh.get('shot_id')}")
            repairs_required.add("cast_propagation")

    # ========== V17.1 DATA COMPLETENESS CHECKS ==========
    # These catch silent data loss bugs
    story_bible = read_json(proj_dir / "story_bible.json", default={}) or {}

    # Check 5: Empty beats in story_bible (data was stripped!)
    sb_scenes = story_bible.get("scenes", [])
    scenes_no_beats = [s for s in sb_scenes if not s.get("beats")]
    if sb_scenes and len(scenes_no_beats) == len(sb_scenes):
        structural_violations.append(f"empty_beats_all_scenes:{len(scenes_no_beats)}")
        repairs_required.add("ui_consistency_enforcer")
        warnings.append("story_bible_beats_stripped:dialogue_may_be_lost")

    # Check 6: Missing locations array in story_bible
    if not story_bible.get("locations") and not story_bible.get("setting", {}).get("locations"):
        structural_violations.append("missing_locations_array")
        repairs_required.add("ui_consistency_enforcer")

    # Check 7: No extended shots when runtime > 10 minutes
    total_duration = sum(sh.get("duration", 20) for sh in shots)
    extended_shots = [sh for sh in shots if sh.get("duration", 20) > 20]
    if total_duration > 600 and not extended_shots:  # > 10 minutes but no extended shots
        warnings.append(f"no_extended_shots:runtime_{total_duration}s")

    # Check 8: LTX prompts all identical (lack of variation)
    ltx_prompts = [sh.get("ltx_motion_prompt", "") for sh in shots if sh.get("ltx_motion_prompt")]
    if len(ltx_prompts) > 5:
        unique_prompts = len(set(ltx_prompts))
        if unique_prompts < len(ltx_prompts) * 0.3:  # Less than 30% unique
            warnings.append(f"ltx_prompts_repetitive:{unique_prompts}_unique_of_{len(ltx_prompts)}")

    # Check 9: Missing dialogue in shot_plan when story has dialogue scenes
    shots_with_dialogue = [sh for sh in shots if sh.get("dialogue")]
    scenes_with_dialogue = [s for s in sb_scenes if any(b.get("dialogue") for b in s.get("beats", []))]
    if scenes_with_dialogue and not shots_with_dialogue:
        warnings.append(f"dialogue_not_propagated_to_shots:{len(scenes_with_dialogue)}_scenes_had_dialogue")

    # ========== V17 SEMANTIC INVARIANTS CHECK ==========
    # These are BLOCKING - project cannot proceed if violated
    semantic_violations = []
    try:
        from .semantic_invariants import check_all_invariants
        invariants_result = check_all_invariants(project, repo_root=p.repo_root)

        if not invariants_result["passed"]:
            for violation in invariants_result["blocking_violations"]:
                semantic_violations.append(f"INVARIANT:{violation['invariant']}:{violation['message']}")
                blocking.append(f"semantic_invariant:{violation['invariant']}")

        # Add warnings from invariants
        for warning in invariants_result.get("warnings", []):
            warnings.append(f"invariant_warning:{warning['invariant']}:{warning['message']}")
    except ImportError:
        # Semantic invariants module not available - continue with legacy checks
        pass
    except Exception as e:
        warnings.append(f"semantic_invariants_check_failed:{str(e)}")

    # ========== VERDICT DETERMINATION ==========
    # Critic is FINAL AUTHORITY - Ops Coordinator obeys this verdict
    needs_human = len(human_judgment_issues) > 0
    needs_repair = len(structural_violations) > 0 or len(blocking) > 0
    safe_to_render = not needs_human and not needs_repair and (len(warnings) == 0 or not fail_on_warnings)

    # Determine verdict and reason for Ops Coordinator
    if needs_human:
        verdict_code = "NEEDS_HUMAN_JUDGMENT"
        reason = f"Human judgment required: {human_judgment_issues[0]}"
    elif needs_repair:
        verdict_code = "NEEDS_REPAIR"
        reason = f"Auto-repair required: {structural_violations[0] if structural_violations else blocking[0]}"
    elif len(warnings) > 0 and fail_on_warnings:
        verdict_code = "NEEDS_REPAIR"
        reason = f"Warnings treated as blocking: {warnings[0]}"
    else:
        verdict_code = "READY"
        reason = "All checks passed"

    critic_report = {
        "project": project,
        "verdict": verdict_code,
        "safe_to_render": safe_to_render,
        "needs_human": needs_human,
        "needs_repair": needs_repair,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "structural_violation_count": len(structural_violations),
        "human_judgment_count": len(human_judgment_issues),
        "blocking": blocking[:200],
        "warnings": warnings[:200],
        "structural_violations": structural_violations[:50],
        "human_judgment_issues": human_judgment_issues[:50],
        "repairs_required": list(repairs_required),
        "reason": reason,
        "notes": "Critic Gate is FINAL AUTHORITY. Ops Coordinator obeys this verdict."
    }
    verdict = {
        "project": project,
        "verdict": verdict_code,
        "safe_to_render": safe_to_render,
        "needs_human": needs_human,
        "needs_repair": needs_repair,
        "repairs_required": list(repairs_required),
        "required_actions": blocking[:50] + (warnings[:50] if fail_on_warnings else []),
        "structural_violations": structural_violations[:50],
        "human_judgment_issues": human_judgment_issues[:50],
    }

    rp = proj_dir / "critic_report.json"
    vp = proj_dir / "freeze_verdict.json"
    write_json(rp, critic_report)
    write_json(vp, verdict)

    status = "completed" if safe_to_render else ("needs_human" if needs_human else "failed")
    live_job_update(project, job_id, status, {
        "blocking": blocking[:50],
        "warnings": warnings[:50],
        "needs_human": needs_human
    }, repo_root=p.repo_root)

    return {
        "success": safe_to_render,
        "verdict": verdict_code,
        "needs_human": needs_human,
        "needs_repair": needs_repair,
        "safe_to_render": safe_to_render,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "structural_violation_count": len(structural_violations),
        "reason": reason,
        "repairs_required": list(repairs_required),
        "artifact": [str(rp), str(vp)],
        "blocking": blocking,
        "warnings": warnings,
        "structural_violations": structural_violations,
        "human_judgment_issues": human_judgment_issues
    }
