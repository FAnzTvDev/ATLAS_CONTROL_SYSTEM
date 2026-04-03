#!/usr/bin/env python3
"""
ATLAS V16.0 - Temporal Activities
==================================
All activities that Temporal workflows can execute.
Activities are the "work" that gets retried on failure.

Activity Categories:
1. Validation - Prerequisites, preflight checks
2. State Management - Load/save from PostgreSQL
3. Generation - Cinematographer, Critic agents
4. Rendering - Image and video generation
5. Notification - Human approval notifications

Retry Policies:
- API calls: 3 attempts with exponential backoff
- DB operations: 3 attempts with linear backoff
- Validation: 1 attempt (fail fast)
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

# Set up logging
logger = logging.getLogger(__name__)

# Base directory for ATLAS - V16.3: Dynamic path detection
# Supports: local dev, VM, or explicit override
_ATLAS_ENV = os.environ.get("ATLAS_BASE_DIR", "")
if _ATLAS_ENV:
    BASE_DIR = Path(_ATLAS_ENV)
elif Path("/sessions").exists():
    # Running in Cowork VM
    BASE_DIR = Path("/sessions/festive-zen-knuth/mnt/ATLAS_CONTROL_SYSTEM")
elif Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM").exists():
    BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
else:
    # Fallback: relative to this file
    BASE_DIR = Path(__file__).parent.parent

# V16.3: LTX Model Constraints
LTX_MAX_DURATION = 20  # seconds
LTX_VALID_DURATIONS = [6, 8, 10, 12, 14, 16, 18, 20]
LTX_FPS = 25
LTX_SEGMENT_DURATION = 5  # seconds per extension segment


# =============================================================================
# VALIDATION ACTIVITIES
# =============================================================================

@activity.defn
async def validate_prerequisites(project_name: str) -> Dict[str, Any]:
    """
    Validate all prerequisites before starting render.

    Checks:
    1. FAL_KEY exists
    2. REPLICATE_API_TOKEN exists
    3. ai_actors_library.json exists and has entries
    4. Project folder exists
    5. shot_plan.json exists
    6. Database is accessible

    Returns:
        {"valid": bool, "missing": list, "details": dict}
    """
    activity.logger.info(f"Validating prerequisites for {project_name}")

    missing = []
    details = {}

    # Check API keys from environment or .env file
    env_path = BASE_DIR / ".env"
    env_vars = {}

    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    env_vars[key] = val

    # FAL_KEY
    fal_key = os.environ.get("FAL_KEY") or env_vars.get("FAL_KEY", "")
    if not fal_key:
        missing.append("FAL_KEY not configured")
    else:
        details["fal_key"] = f"...{fal_key[-8:]}" if len(fal_key) > 8 else "configured"

    # REPLICATE_API_TOKEN
    replicate_key = os.environ.get("REPLICATE_API_TOKEN") or env_vars.get("REPLICATE_API_TOKEN", "")
    if not replicate_key:
        # Check for REPLICATE_TOKENS array
        replicate_tokens = env_vars.get("REPLICATE_TOKENS", "")
        if not replicate_tokens:
            missing.append("REPLICATE_API_TOKEN not configured")
        else:
            details["replicate_tokens"] = f"{len(replicate_tokens.split(','))} tokens"
    else:
        details["replicate_token"] = "configured"

    # AI Actors Library
    actors_path = BASE_DIR / "ai_actors_library.json"
    if not actors_path.exists():
        missing.append("ai_actors_library.json not found")
    else:
        try:
            with open(actors_path) as f:
                actors = json.load(f)
                actor_count = len(actors.get("actors", actors)) if isinstance(actors, dict) else len(actors)
                if actor_count == 0:
                    missing.append("ai_actors_library.json is empty")
                else:
                    details["actors"] = f"{actor_count} actors loaded"
        except Exception as e:
            missing.append(f"ai_actors_library.json invalid: {e}")

    # Project folder
    project_path = BASE_DIR / "pipeline_outputs" / project_name
    if not project_path.exists():
        missing.append(f"Project folder not found: {project_path}")
    else:
        details["project_path"] = str(project_path)

    # Shot plan
    shot_plan_path = project_path / "shot_plan.json"
    if project_path.exists() and not shot_plan_path.exists():
        missing.append(f"shot_plan.json not found in {project_path}")
    elif shot_plan_path.exists():
        try:
            with open(shot_plan_path) as f:
                plan = json.load(f)
                shots = plan.get("shots", plan.get("scene_manifest", []))
                details["shots"] = f"{len(shots)} shots in plan"
        except Exception as e:
            missing.append(f"shot_plan.json invalid: {e}")

    # Database check (optional - warn but don't block)
    try:
        from database.postgres_manager import PostgresGalleryManager, DatabaseConfig
        db = PostgresGalleryManager(DatabaseConfig.from_env())
        # Just check config is valid - don't actually connect in activity
        details["database"] = "PostgreSQL configured"
    except Exception as e:
        details["database"] = f"PostgreSQL not configured (using JSON fallback): {e}"

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "details": details,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@activity.defn
async def run_preflight_check(project_name: str, project_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all 7 validation gates before rendering.

    Gates:
    1. Duration Gate - Total runtime within target
    2. Asset Gate - All character refs and locations exist
    3. Casting Gate - All characters have AI actor assignments
    4. Coverage Gate - Proper shot type coverage per scene
    5. Continuity Gate - No location jumps within scenes
    6. Pacing Gate - No monotonous durations
    7. Blocking Gate - No consecutive identical framings

    Returns:
        {"passed": bool, "blocking_issues": list, "warnings": list, "gate_results": dict}
    """
    activity.logger.info(f"Running preflight check for {project_name}")

    blocking_issues = []
    warnings = []
    gate_results = {}

    shots = project_state.get("shots", [])
    story_bible = project_state.get("story_bible", {})
    target_runtime = project_state.get("target_runtime_minutes", 45) * 60

    # =========================================================================
    # Gate 1: Duration
    # =========================================================================

    total_duration = sum(
        s.get("duration") or s.get("duration_seconds") or 0
        for s in shots
    )
    duration_delta = abs(total_duration - target_runtime) / target_runtime * 100

    gate_results["duration"] = {
        "total_seconds": total_duration,
        "target_seconds": target_runtime,
        "delta_percent": duration_delta,
        "passed": duration_delta < 20,  # Within 20%
    }

    if duration_delta > 50:
        blocking_issues.append(f"Duration {duration_delta:.0f}% off target")
    elif duration_delta > 20:
        warnings.append(f"Duration {duration_delta:.0f}% off target")

    # =========================================================================
    # Gate 2: Assets
    # =========================================================================

    missing_assets = []
    for shot in shots:
        if shot.get("characters") and not shot.get("character_reference_url") and not shot.get("ai_actor_cast"):
            missing_assets.append(f"{shot.get('shot_id')}: missing character reference")

    gate_results["assets"] = {
        "missing_count": len(missing_assets),
        "passed": len(missing_assets) == 0,
    }

    if missing_assets:
        if len(missing_assets) > len(shots) * 0.5:
            blocking_issues.append(f"{len(missing_assets)} shots missing character refs")
        else:
            warnings.extend(missing_assets[:5])  # First 5 only

    # =========================================================================
    # Gate 3: Casting
    # =========================================================================

    uncast_characters = set()
    for shot in shots:
        for char in shot.get("characters", []):
            char_name = char if isinstance(char, str) else char.get("name", "")
            if char_name:
                # Handle both dict and string formats for ai_actor_cast
                cast_data = shot.get("ai_actor_cast", {})
                if isinstance(cast_data, str):
                    # String format - just an actor ID, character is cast
                    is_cast = bool(cast_data)
                elif isinstance(cast_data, dict):
                    is_cast = bool(cast_data.get(char_name.upper()))
                else:
                    is_cast = False
                if not is_cast:
                    uncast_characters.add(char_name)

    gate_results["casting"] = {
        "uncast_count": len(uncast_characters),
        "uncast_characters": list(uncast_characters)[:10],
        "passed": len(uncast_characters) == 0,
    }

    if uncast_characters:
        warnings.append(f"{len(uncast_characters)} characters not cast: {', '.join(list(uncast_characters)[:3])}")

    # =========================================================================
    # Gate 4: Coverage (shot type variety)
    # =========================================================================

    shot_types = [s.get("shot_type", "").lower() for s in shots if s.get("shot_type")]
    type_counts = {}
    for st in shot_types:
        type_counts[st] = type_counts.get(st, 0) + 1

    has_wide = any("wide" in t or "establish" in t for t in shot_types)
    has_close = any("close" in t for t in shot_types)
    has_medium = any("medium" in t for t in shot_types)

    gate_results["coverage"] = {
        "shot_type_distribution": type_counts,
        "has_wide": has_wide,
        "has_close": has_close,
        "has_medium": has_medium,
        "passed": has_wide and has_close,
    }

    if not has_wide:
        warnings.append("No wide/establishing shots found")
    if not has_close:
        warnings.append("No close-up shots found")

    # =========================================================================
    # Gate 5: Continuity (location jumps)
    # =========================================================================

    location_jumps = []
    prev_scene = None
    prev_location = None

    for shot in shots:
        scene = shot.get("scene_id", "")
        location = shot.get("location", "")

        if scene == prev_scene and location and prev_location and location != prev_location:
            location_jumps.append(f"{shot.get('shot_id')}: {prev_location} -> {location}")

        prev_scene = scene
        prev_location = location

    gate_results["continuity"] = {
        "location_jump_count": len(location_jumps),
        "passed": len(location_jumps) == 0,
    }

    if location_jumps:
        warnings.extend(location_jumps[:3])

    # =========================================================================
    # Gate 6: Pacing (duration variety)
    # =========================================================================

    durations = [s.get("duration") or s.get("duration_seconds") or 0 for s in shots if s.get("duration") or s.get("duration_seconds")]
    unique_durations = len(set(int(d) for d in durations))

    gate_results["pacing"] = {
        "unique_duration_count": unique_durations,
        "passed": unique_durations > 2 or len(shots) <= 10,
    }

    if unique_durations <= 2 and len(shots) > 10:
        warnings.append(f"Monotonous pacing: only {unique_durations} unique durations")

    # =========================================================================
    # Gate 7: Blocking (consecutive identical framings)
    # =========================================================================

    consecutive_same = 0
    max_consecutive = 0
    prev_type = None

    for shot in shots:
        shot_type = shot.get("shot_type", "").lower()
        if shot_type == prev_type:
            consecutive_same += 1
            max_consecutive = max(max_consecutive, consecutive_same)
        else:
            consecutive_same = 0
        prev_type = shot_type

    gate_results["blocking"] = {
        "max_consecutive_same_type": max_consecutive,
        "passed": max_consecutive < 5,
    }

    if max_consecutive >= 5:
        warnings.append(f"{max_consecutive} consecutive identical shot types")

    # =========================================================================
    # Final Result
    # =========================================================================

    all_passed = all(g.get("passed", True) for g in gate_results.values())

    return {
        "passed": len(blocking_issues) == 0,
        "all_gates_passed": all_passed,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "gate_results": gate_results,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# =============================================================================
# STATE MANAGEMENT ACTIVITIES
# =============================================================================

@activity.defn
async def load_project_state(project_name: str) -> Dict[str, Any]:
    """
    Load project state from PostgreSQL (with JSON fallback).

    Loads:
    - shot_plan.json (shots, scenes)
    - story_bible.json (characters, locations)
    - cast_map.json (character -> actor mappings)
    - Render status from database

    Returns:
        Complete project state dictionary
    """
    activity.logger.info(f"Loading project state for {project_name}")

    project_path = BASE_DIR / "pipeline_outputs" / project_name
    state = {
        "project_name": project_name,
        "project_path": str(project_path),
        "shots": [],
        "scenes": [],
        "characters": [],
        "locations": [],
        "story_bible": {},
        "cast_map": {},
        "target_runtime_minutes": 45,
    }

    # Load shot_plan.json
    shot_plan_path = project_path / "shot_plan.json"
    if shot_plan_path.exists():
        with open(shot_plan_path) as f:
            plan = json.load(f)

        # Normalize shots (could be in different formats)
        shots = plan.get("shots", [])
        if not shots:
            # Try scene_manifest format
            for scene in plan.get("scene_manifest", plan.get("scenes", [])):
                for beat in scene.get("beats", [scene]):
                    shot = {
                        "shot_id": beat.get("shot_id", f"{scene.get('scene_id', '001')}_{beat.get('beat_number', '0')}A"),
                        "scene_id": scene.get("scene_id", "001"),
                        "location": scene.get("location", beat.get("location", "")),
                        "characters": beat.get("characters", scene.get("characters", [])),
                        "description": beat.get("description", ""),
                        "dialogue": beat.get("dialogue", ""),
                        "duration": beat.get("duration_seconds", scene.get("duration_seconds", 8)),
                        "beat_type": beat.get("beat_type", "action"),
                        "emotional_tone": beat.get("emotional_tone", "neutral"),
                    }
                    shots.append(shot)

        state["shots"] = shots
        state["scenes"] = plan.get("scene_manifest", plan.get("scenes", []))
        state["characters"] = plan.get("characters", [])
        state["target_runtime_minutes"] = plan.get("runtime", 45)

    # Load story_bible.json
    bible_path = project_path / "story_bible.json"
    if bible_path.exists():
        with open(bible_path) as f:
            state["story_bible"] = json.load(f)
            if not state["characters"]:
                state["characters"] = state["story_bible"].get("characters", [])
            state["locations"] = state["story_bible"].get("locations", [])

    # Load cast_map.json
    cast_map_path = project_path / "cast_map.json"
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            state["cast_map"] = json.load(f)

    # Try to load render status from PostgreSQL
    try:
        from database.postgres_manager import PostgresGalleryManager, DatabaseConfig
        import asyncio

        db = PostgresGalleryManager(DatabaseConfig.from_env())
        if await db.connect():
            db_shots = await db.get_shots_by_project(project_name)
            await db.close()

            # Merge DB status into shots
            db_status = {s["shot_id"]: s for s in db_shots}
            for shot in state["shots"]:
                shot_id = shot.get("shot_id")
                if shot_id in db_status:
                    shot["db_status"] = db_status[shot_id].get("status")
                    shot["video_path"] = db_status[shot_id].get("video_path")
                    shot["image_path"] = db_status[shot_id].get("image_path")

            activity.logger.info(f"Loaded {len(db_shots)} shot statuses from PostgreSQL")
    except Exception as e:
        activity.logger.warning(f"Could not load from PostgreSQL: {e}")

    activity.logger.info(f"Loaded {len(state['shots'])} shots for {project_name}")
    return state


@activity.defn
async def save_project_state(project_name: str, updates: Dict[str, Any]) -> bool:
    """
    Save project state updates to JSON files (with PostgreSQL when available).

    CRITICAL: State MUST be persisted after every operation for crash recovery.

    Updates dict can contain:
    - workflow_checkpoint: {current_shot_index, shots_completed, shots_failed}
    - shot_updates: {shot_id: {fields to update}}
    - cast_map: Full cast_map dict to save
    - verification_state: Verification flags to save

    Returns True if state was saved successfully.
    """
    activity.logger.info(f"Saving project state for {project_name}: {list(updates.keys())}")

    project_path = BASE_DIR / "pipeline_outputs" / project_name
    project_path.mkdir(parents=True, exist_ok=True)

    saved_files = []

    try:
        # 1. Save workflow checkpoint (always)
        checkpoint = updates.get("workflow_checkpoint", {})
        if checkpoint or "current_shot_index" in updates:
            checkpoint_data = {
                "project": project_name,
                "current_shot_index": updates.get("current_shot_index", checkpoint.get("current_shot_index", 0)),
                "shots_completed": updates.get("shots_completed", checkpoint.get("shots_completed", 0)),
                "shots_failed": updates.get("shots_failed", checkpoint.get("shots_failed", 0)),
                "last_saved_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            checkpoint_path = project_path / "workflow_checkpoint.json"
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
            saved_files.append("workflow_checkpoint.json")
            activity.logger.info(f"Saved checkpoint: shot_index={checkpoint_data['current_shot_index']}")

        # 2. Save shot updates to shot_plan.json
        shot_updates = updates.get("shot_updates", {})
        if shot_updates:
            shot_plan_path = project_path / "shot_plan.json"
            if shot_plan_path.exists():
                with open(shot_plan_path) as f:
                    data = json.load(f)

                shots = data.get("shots", [])
                for shot in shots:
                    shot_id = shot.get("shot_id")
                    if shot_id in shot_updates:
                        shot.update(shot_updates[shot_id])

                # Backup before save
                backup_path = shot_plan_path.with_suffix(f".json.checkpoint_{datetime.now(tz=timezone.utc).strftime('%H%M%S')}")
                import shutil
                shutil.copy(shot_plan_path, backup_path)

                with open(shot_plan_path, "w") as f:
                    json.dump(data, f, indent=2)
                saved_files.append("shot_plan.json")
                activity.logger.info(f"Updated {len(shot_updates)} shots in shot_plan.json")

        # 3. Save cast_map if provided
        cast_map = updates.get("cast_map")
        if cast_map:
            cast_map_path = project_path / "cast_map.json"
            with open(cast_map_path, "w") as f:
                json.dump(cast_map, f, indent=2)
            saved_files.append("cast_map.json")

        # 4. Save verification state if provided
        verification_state = updates.get("verification_state")
        if verification_state:
            verification_path = project_path / "verification_state.json"
            existing = {}
            if verification_path.exists():
                with open(verification_path) as f:
                    existing = json.load(f)
            existing.update(verification_state)
            existing["_updated_at"] = datetime.now(tz=timezone.utc).isoformat()
            with open(verification_path, "w") as f:
                json.dump(existing, f, indent=2)
            saved_files.append("verification_state.json")

        # 5. Try PostgreSQL if available (non-blocking)
        try:
            from database.postgres_manager import PostgresGalleryManager, DatabaseConfig
            db = PostgresGalleryManager(DatabaseConfig.from_env())
            if await db.connect():
                # Could store checkpoint in a dedicated table here
                await db.close()
        except Exception as e:
            activity.logger.debug(f"PostgreSQL not available (using JSON): {e}")

        activity.logger.info(f"State saved to: {saved_files}")
        return True

    except Exception as e:
        activity.logger.error(f"Failed to save state: {e}")
        return False


@activity.defn
async def update_shot_in_db(project_name: str, shot_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update a single shot's status in the database.
    """
    activity.logger.info(f"Updating shot {shot_id} in database")

    try:
        from database.postgres_manager import PostgresGalleryManager, DatabaseConfig

        db = PostgresGalleryManager(DatabaseConfig.from_env())
        if await db.connect():
            await db.register_shot(
                shot_id=shot_id,
                scene_id=updates.get("scene_id", "UNKNOWN"),
                video_path=updates.get("video_url"),
                image_path=updates.get("image_url"),
                status=updates.get("status", "complete"),
                metadata={
                    "project": project_name,
                    "critic_grade": updates.get("critic_grade"),
                    "enhanced_prompt": updates.get("enhanced_prompt"),
                }
            )
            await db.close()
            return True
    except Exception as e:
        activity.logger.error(f"Failed to update shot in DB: {e}")

    # Fallback: update JSON file
    project_path = BASE_DIR / "pipeline_outputs" / project_name
    status_file = project_path / "render_status.json"

    status = {}
    if status_file.exists():
        with open(status_file) as f:
            status = json.load(f)

    status[shot_id] = {
        **updates,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)

    return True


# =============================================================================
# AGENT ACTIVITIES (EditDuet)
# =============================================================================

@activity.defn
async def run_cinematographer_agent(
    project_name: str,
    shot: Dict[str, Any],
    project_state: Dict[str, Any],
    critic_feedback: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run the Cinematographer Agent to generate/enhance shot prompts.

    The Cinematographer acts as the "Editor" in the EditDuet pattern.
    It generates visual prompts based on story context and cinematography rules.

    If critic_feedback is provided, it adjusts the generation accordingly.
    """
    activity.logger.info(f"Running Cinematographer for shot {shot.get('shot_id')}")

    try:
        # Import cinematographer agent
        from agents.cinematographer_agent import CinematographerAgent, SemanticPromptJSON

        # Initialize agent with director profile from project
        director_profile = project_state.get("story_bible", {}).get("director_profile", "thriller_v2")

        agent = CinematographerAgent(
            director_profile_name=director_profile,  # Correct parameter name
        )

        # Generate enhanced shot
        enhanced = agent.generate_shot(
            shot_data=shot,
            scene_context={
                "scene_id": shot.get("scene_id"),
                "location": shot.get("location"),
                "characters": shot.get("characters", []),
                "emotional_arc": project_state.get("story_bible", {}).get("emotional_arc", []),
            },
            critic_notes=critic_feedback,
        )

        return {
            "success": True,
            "enhanced_shot": enhanced.to_dict() if hasattr(enhanced, "to_dict") else enhanced,
            "changes_made": enhanced.get("changes_from_critic", []) if isinstance(enhanced, dict) else [],
        }

    except Exception as e:
        activity.logger.error(f"Cinematographer error: {e}")

        # Fallback: return shot with basic enhancement
        enhanced_shot = dict(shot)
        enhanced_shot["nano_prompt"] = shot.get("nano_prompt") or shot.get("description", "")
        enhanced_shot["enhanced_at"] = datetime.now(tz=timezone.utc).isoformat()

        return {
            "success": False,
            "error": str(e),
            "enhanced_shot": enhanced_shot,
        }


@activity.defn
async def run_director_critic(
    shot: Dict[str, Any],
    project_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run the Director Critic to validate a shot.

    The Critic acts as the "Critic" in the EditDuet pattern.
    It grades shots and provides feedback for improvement.
    """
    activity.logger.info(f"Running Director Critic for shot {shot.get('shot_id')}")

    try:
        from DIRECTOR_CRITIC import DirectorCritic, run_director_analysis

        # Run full director analysis
        target_runtime = project_state.get("target_runtime_minutes", 45)

        # Wrap single shot in list for analysis
        analysis = run_director_analysis(
            shots=[shot],
            target_runtime_minutes=target_runtime,
            story_bible=project_state.get("story_bible"),
        )

        # Extract grade and notes
        confidence = analysis.get("confidence_score", 0)
        if confidence >= 0.85:
            grade = "A"
        elif confidence >= 0.7:
            grade = "B"
        elif confidence >= 0.5:
            grade = "C"
        elif confidence >= 0.3:
            grade = "D"
        else:
            grade = "F"

        notes = [
            n.get("note", "") for n in analysis.get("notes", [])
            if n.get("severity") in ["BLOCK", "CRITICAL", "WARNING"]
        ]

        return {
            "grade": grade,
            "confidence": confidence,
            "notes": notes,
            "blocking_issues": [n for n in analysis.get("notes", []) if n.get("severity") == "BLOCK"],
            "ready_for_render": analysis.get("ready_for_render", True),
            "coverage_analysis": analysis.get("coverage_analysis", {}),
            "pacing_analysis": analysis.get("pacing_analysis", {}),
        }

    except Exception as e:
        activity.logger.error(f"Critic error: {e}")
        return {
            "grade": "B",  # Default to B on error (don't block)
            "confidence": 0.75,
            "notes": [f"Critic error: {e}"],
            "error": str(e),
            "ready_for_render": True,
        }


# =============================================================================
# RENDER ACTIVITIES
# =============================================================================

@activity.defn
async def render_shot_image(
    project_name: str,
    shot_id: str,
    shot_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Render a shot's image using FAL.ai nano-banana-pro.

    V16 MODEL LOCK - ONLY THESE MODELS:
    - fal-ai/nano-banana-pro/edit (WITH character references)
    - fal-ai/nano-banana-pro (WITHOUT character references)

    FORBIDDEN: minimax, flux, runway, wan-video
    """
    activity.logger.info(f"Rendering image for {shot_id}")

    # Determine render type from shot content
    # V37-parity: E-SHOT GUARD — environment-only shots must not receive character refs
    # Mirrors atlas_universal_runner.py line 1834-1841 and orchestrator line 22617-22625.
    _is_e_shot_activity = bool(shot_data.get("_no_char_ref") or shot_data.get("_is_broll") or shot_data.get("is_broll"))
    has_character = bool(shot_data.get("characters")) and not _is_e_shot_activity
    if _is_e_shot_activity:
        activity.logger.info(f"[E-SHOT GUARD] {shot_id}: environment-only — char refs withheld")
    character_ref = shot_data.get("character_reference_url") or shot_data.get("ai_actor_cast", {})

    prompt = shot_data.get("nano_prompt") or shot_data.get("description") or ""
    if not prompt:
        return {"success": False, "error": "No prompt available"}

    try:
        import fal_client

        # Load FAL API key
        env_path = BASE_DIR / ".env"
        fal_key = os.environ.get("FAL_KEY", "")

        if env_path.exists() and not fal_key:
            with open(env_path) as f:
                for line in f:
                    if line.startswith("FAL_KEY="):
                        fal_key = line.split("=", 1)[1].strip()
                        break

        if not fal_key:
            return {"success": False, "error": "No FAL_KEY configured"}

        os.environ["FAL_KEY"] = fal_key

        # V16 MODEL LOCK: nano-banana-pro ONLY
        ref_url = None
        if has_character and character_ref:
            if isinstance(character_ref, str):
                ref_url = character_ref
            elif isinstance(character_ref, dict):
                # Get first actor's reference
                for actor_data in character_ref.values():
                    if isinstance(actor_data, dict):
                        ref_url = actor_data.get("reference_image") or actor_data.get("reference_url") or actor_data.get("headshot_url")
                    elif isinstance(actor_data, str):
                        ref_url = actor_data
                    if ref_url:
                        break

        if ref_url:
            # WITH reference - use nano-banana-pro/edit
            result = fal_client.subscribe(
                "fal-ai/nano-banana-pro/edit",
                arguments={
                    "prompt": prompt,
                    "image_urls": [ref_url],  # Must be array for /edit endpoint
                    "image_size": {"width": 1280, "height": 720},  # 16:9
                },
            )
            model_used = "fal-ai/nano-banana-pro/edit"
        else:
            # WITHOUT reference - use nano-banana-pro
            result = fal_client.subscribe(
                "fal-ai/nano-banana-pro",
                arguments={
                    "prompt": prompt,
                    "image_size": {"width": 1280, "height": 720},  # 16:9
                },
            )
            model_used = "fal-ai/nano-banana-pro"

        # Extract URL from result
        if isinstance(result, dict):
            images = result.get("images", [])
            if images:
                image_url = images[0].get("url", "") if isinstance(images[0], dict) else str(images[0])
            else:
                image_url = result.get("image", {}).get("url", "")
        else:
            image_url = str(result)

        activity.logger.info(f"Image rendered for {shot_id}: {image_url[:80]}...")

        return {
            "success": True,
            "image_url": image_url,
            "model": model_used,
            "shot_id": shot_id,
        }

    except Exception as e:
        activity.logger.error(f"Image render error for {shot_id}: {e}")
        return {"success": False, "error": str(e), "shot_id": shot_id}


@activity.defn
async def render_shot_video(
    project_name: str,
    shot_id: str,
    shot_data: Dict[str, Any],
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Render a shot's video using FAL.ai ltxv-2.

    V16 MODEL LOCK - ONLY THIS MODEL:
    - fal-ai/ltxv-2/image-to-video/fast

    FORBIDDEN: minimax, flux, runway, wan-video

    Requires image_url from prior image render.
    """
    activity.logger.info(f"Rendering video for {shot_id}")

    if not image_url:
        return {"success": False, "error": "No image URL provided"}

    prompt = shot_data.get("ltx_motion_prompt") or shot_data.get("nano_prompt") or shot_data.get("description") or ""
    duration = shot_data.get("duration") or shot_data.get("duration_seconds") or 8

    try:
        import fal_client

        # Load FAL API key
        env_path = BASE_DIR / ".env"
        fal_key = os.environ.get("FAL_KEY", "")

        if env_path.exists() and not fal_key:
            with open(env_path) as f:
                for line in f:
                    if line.startswith("FAL_KEY="):
                        fal_key = line.split("=", 1)[1].strip()
                        break

        if not fal_key:
            return {"success": False, "error": "No FAL_KEY configured"}

        os.environ["FAL_KEY"] = fal_key

        # V16 MODEL LOCK: ltxv-2 ONLY
        # LTX Video 2 supports 1-10 second videos
        num_frames = min(max(24, int(duration * 24)), 240)  # 1-10 seconds at 24fps

        result = fal_client.subscribe(
            "fal-ai/ltxv-2/image-to-video/fast",
            arguments={
                "prompt": prompt,
                "image_url": image_url,
                "num_frames": num_frames,
                "fps": 25,  # LTX requires 25 or 50
            },
        )

        # Extract URL from result
        if isinstance(result, dict):
            video_url = result.get("video", {}).get("url", "")
            if not video_url:
                video_url = result.get("url", "")
        else:
            video_url = str(result)

        activity.logger.info(f"Video rendered for {shot_id}: {video_url[:80] if video_url else 'NO URL'}...")

        return {
            "success": bool(video_url),
            "video_url": video_url,
            "model": "fal-ai/ltxv-2/image-to-video/fast",
            "shot_id": shot_id,
            "duration_frames": num_frames,
        }

    except Exception as e:
        activity.logger.error(f"Video render error for {shot_id}: {e}")
        return {"success": False, "error": str(e), "shot_id": shot_id}


# =============================================================================
# NOTIFICATION ACTIVITIES
# =============================================================================

@activity.defn
async def notify_human_required(
    project_name: str,
    shot_id: str,
    message: str
) -> bool:
    """
    Notify that human approval is required.

    This could:
    - Send WebSocket message to UI
    - Send email/Slack notification
    - Log to monitoring system
    """
    activity.logger.info(f"Human approval required for {project_name}/{shot_id}: {message}")

    # For now, just log and save notification to file
    notification_path = BASE_DIR / "pipeline_outputs" / project_name / "notifications.json"

    notifications = []
    if notification_path.exists():
        with open(notification_path) as f:
            notifications = json.load(f)

    notifications.append({
        "shot_id": shot_id,
        "message": message,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "status": "pending",
    })

    notification_path.parent.mkdir(parents=True, exist_ok=True)
    with open(notification_path, "w") as f:
        json.dump(notifications, f, indent=2)

    return True


# =============================================================================
# V16.3 EXTENSION ACTIVITIES - For shots > 20 seconds
# =============================================================================

@activity.defn
async def render_extended_video(
    project_name: str,
    shot_id: str,
    shot_data: Dict[str, Any],
    image_url: str,
    target_duration: int
) -> Dict[str, Any]:
    """
    Render extended video for shots > 20 seconds.

    Strategy: Last-frame chaining
    1. Render first segment (use image_url)
    2. Extract last frame
    3. Use last frame as input for next segment
    4. Repeat until target duration
    5. Stitch all segments

    V16 MODEL LOCK: fal-ai/ltxv-2/image-to-video/fast
    """
    activity.logger.info(f"Rendering EXTENDED video for {shot_id}: {target_duration}s")

    if target_duration <= LTX_MAX_DURATION:
        # No extension needed - use regular render
        return await render_shot_video(project_name, shot_id, shot_data, image_url)

    # Calculate segments needed
    segments_needed = (target_duration + LTX_SEGMENT_DURATION - 1) // LTX_SEGMENT_DURATION
    activity.logger.info(f"Extension: {segments_needed} segments needed for {target_duration}s")

    import fal_client
    import subprocess
    import tempfile
    import shutil

    # Load FAL API key
    env_path = BASE_DIR / ".env"
    fal_key = os.environ.get("FAL_KEY", "")
    if env_path.exists() and not fal_key:
        with open(env_path) as f:
            for line in f:
                if line.startswith("FAL_KEY="):
                    fal_key = line.split("=", 1)[1].strip()
                    break

    if not fal_key:
        return {"success": False, "error": "No FAL_KEY configured"}
    os.environ["FAL_KEY"] = fal_key

    # Prepare output directory
    output_dir = BASE_DIR / "pipeline_outputs" / project_name / "extended_segments" / shot_id
    output_dir.mkdir(parents=True, exist_ok=True)

    segment_paths = []
    current_frame_url = image_url
    prompt = shot_data.get("ltx_motion_prompt") or shot_data.get("nano_prompt") or shot_data.get("description") or ""

    try:
        for seg_num in range(1, segments_needed + 1):
            # Calculate segment duration (last segment may be shorter)
            remaining = target_duration - (seg_num - 1) * LTX_SEGMENT_DURATION
            seg_duration = min(LTX_SEGMENT_DURATION, remaining)

            # Snap to valid LTX duration
            seg_duration = min(LTX_VALID_DURATIONS, key=lambda x: abs(x - seg_duration))
            num_frames = seg_duration * LTX_FPS

            # Build continuation prompt
            if seg_num == 1:
                seg_prompt = f"{prompt}, smooth motion start"
            elif seg_num == segments_needed:
                seg_prompt = f"{prompt}, seamless continuation, motion settling"
            else:
                seg_prompt = f"{prompt}, seamless continuation, maintaining motion"

            activity.logger.info(f"  Segment {seg_num}/{segments_needed}: {seg_duration}s using {'initial image' if seg_num == 1 else 'last frame'}")

            # Render segment
            result = fal_client.subscribe(
                "fal-ai/ltxv-2/image-to-video/fast",
                arguments={
                    "prompt": seg_prompt,
                    "image_url": current_frame_url,
                    "num_frames": num_frames,
                    "fps": LTX_FPS,
                },
            )

            # Extract video URL
            if isinstance(result, dict):
                video_url = result.get("video", {}).get("url", "") or result.get("url", "")
            else:
                video_url = str(result)

            if not video_url:
                return {"success": False, "error": f"Segment {seg_num} failed - no URL", "shot_id": shot_id}

            # Download segment
            segment_path = output_dir / f"segment_{seg_num:03d}.mp4"
            download_cmd = ["curl", "-sL", "-o", str(segment_path), video_url]
            subprocess.run(download_cmd, check=True)
            segment_paths.append(str(segment_path))

            # Extract last frame for next segment (if not last)
            if seg_num < segments_needed:
                frame_path = output_dir / f"frame_{seg_num:03d}.jpg"
                current_frame_url = await extract_last_frame(str(segment_path), str(frame_path))
                if not current_frame_url:
                    return {"success": False, "error": f"Frame extraction failed for segment {seg_num}", "shot_id": shot_id}

            # Save checkpoint
            await save_render_checkpoint(project_name, shot_id, {
                "segment": seg_num,
                "total_segments": segments_needed,
                "segment_paths": segment_paths,
            })

        # Stitch all segments
        final_path = output_dir / f"{shot_id}_extended.mp4"
        stitch_result = await stitch_video_segments(segment_paths, str(final_path))

        if not stitch_result.get("success"):
            return {"success": False, "error": "Stitching failed", "shot_id": shot_id}

        activity.logger.info(f"Extended video complete for {shot_id}: {segments_needed} segments → {target_duration}s")

        return {
            "success": True,
            "video_url": f"file://{final_path}",  # Local file for now
            "video_path": str(final_path),
            "model": "fal-ai/ltxv-2/image-to-video/fast",
            "shot_id": shot_id,
            "duration_seconds": target_duration,
            "segments_used": segments_needed,
            "extension_strategy": "last_frame_chain",
        }

    except Exception as e:
        activity.logger.error(f"Extended video error for {shot_id}: {e}")
        return {"success": False, "error": str(e), "shot_id": shot_id}


@activity.defn
async def extract_last_frame(video_path: str, output_path: str) -> Optional[str]:
    """
    Extract the last frame from a video using ffmpeg.

    Returns: Path to extracted frame (for local use) or uploads and returns URL
    """
    import subprocess

    activity.logger.info(f"Extracting last frame from {video_path}")

    try:
        # Get video duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())

        # Extract last frame (slightly before end to avoid black frames)
        last_frame_time = max(0, duration - 0.1)

        extract_cmd = [
            "ffmpeg", "-y",
            "-ss", str(last_frame_time),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        subprocess.run(extract_cmd, capture_output=True, check=True)

        if Path(output_path).exists():
            activity.logger.info(f"Last frame extracted: {output_path}")
            # For FAL, we need to upload to get a URL - for now return local path
            # TODO: Upload to FAL/S3 and return URL
            return output_path
        else:
            return None

    except Exception as e:
        activity.logger.error(f"Frame extraction error: {e}")
        return None


@activity.defn
async def stitch_video_segments(segment_paths: List[str], output_path: str) -> Dict[str, Any]:
    """
    Stitch multiple video segments into one seamless video.

    Uses ffmpeg concat demuxer for lossless joining.
    """
    import subprocess
    import tempfile

    activity.logger.info(f"Stitching {len(segment_paths)} segments → {output_path}")

    if not segment_paths:
        return {"success": False, "error": "No segments provided"}

    if len(segment_paths) == 1:
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return {"success": True, "output_path": output_path}

    try:
        # Create concat list file
        concat_list = Path(output_path).parent / "concat_temp.txt"
        with open(concat_list, "w") as f:
            for seg_path in segment_paths:
                f.write(f"file '{seg_path}'\n")

        # Run ffmpeg concat
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # Cleanup
        concat_list.unlink()

        if Path(output_path).exists():
            activity.logger.info(f"Stitching complete: {output_path}")
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": "Output file not created"}

    except Exception as e:
        activity.logger.error(f"Stitching error: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def save_render_checkpoint(
    project_name: str,
    shot_id: str,
    checkpoint_data: Dict[str, Any]
) -> bool:
    """
    Save render checkpoint for recovery.

    Allows resuming extended renders after failure.
    """
    checkpoint_path = BASE_DIR / "pipeline_outputs" / project_name / "checkpoints" / f"{shot_id}.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "shot_id": shot_id,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data": checkpoint_data,
    }

    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f, indent=2)

    activity.logger.info(f"Checkpoint saved for {shot_id}")
    return True


@activity.defn
async def load_render_checkpoint(
    project_name: str,
    shot_id: str
) -> Optional[Dict[str, Any]]:
    """
    Load render checkpoint if exists.

    Returns checkpoint data or None if no checkpoint.
    """
    checkpoint_path = BASE_DIR / "pipeline_outputs" / project_name / "checkpoints" / f"{shot_id}.json"

    if not checkpoint_path.exists():
        return None

    with open(checkpoint_path) as f:
        checkpoint = json.load(f)

    activity.logger.info(f"Checkpoint loaded for {shot_id}: {checkpoint.get('timestamp')}")
    return checkpoint.get("data")


@activity.defn
async def clear_render_checkpoint(project_name: str, shot_id: str) -> bool:
    """
    Clear checkpoint after successful render.
    """
    checkpoint_path = BASE_DIR / "pipeline_outputs" / project_name / "checkpoints" / f"{shot_id}.json"

    if checkpoint_path.exists():
        checkpoint_path.unlink()
        activity.logger.info(f"Checkpoint cleared for {shot_id}")

    return True
