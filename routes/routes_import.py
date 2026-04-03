"""
V23 Script Import Routes
Handles: screenplay import, story bible generation, auto-casting

Endpoints:
- POST /v6/script/full-import                    — ONE import pipeline for all scripts
- POST /auto/generate-story-bible                — LLM narrative expansion
- POST /v6/casting/auto-cast                     — Match characters to AI actors
- POST /v21/import-validation-gate               — Pre-save validation
"""

from fastapi import APIRouter, Body, UploadFile, File, HTTPException
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["import"])


# ============================================================================
# FULL IMPORT PIPELINE
# ============================================================================

@router.post("/v6/script/full-import")
async def full_import_screenplay(
    request: Dict[str, Any] = Body(...),
    screenplay_file: Optional[UploadFile] = File(None)
) -> Dict[str, Any]:
    """
    V21: Full Import Pipeline — THE ONLY entry point for new projects

    ONE import pipeline for all scripts. No other endpoint creates projects.

    Import sequence:
    1. Text extraction → raw screenplay text
    2. Scene header counting → INT./EXT. lines → _canonical_scene_count (IMMUTABLE)
    3. Character normalization → Phase 1B alias resolution → canonical names only
    4. Story bible → V6 header ingest OR LLM generation (must match scene count)
    5. Shot expansion → scenes → shots with ABC coverage
    6. Import validation gate → 8 checks, CRITICAL failures reject import
    7. Save → only after gate passes

    Request:
        project (str): Project name
        screenplay_text (str, optional): Screenplay content (if not uploading file)
        screenplay_file (file, optional): Upload screenplay
        story_bible (dict, optional): Pre-made story bible to use

    Response:
        project (str): Project name
        status (str): "imported" | "validation_failed"
        scene_count (int): Canonical scene count (from INT./EXT. headers)
        shot_count (int): Total shots generated (ABC coverage)
        characters_found (int): Unique characters
        characters_normalized (int): Aliases resolved
        cast_map_entries (int): Characters in cast_map
        story_bible_source (str): "V6_header_ingest" | "llm_generated" | "provided"
        validation_results (dict): 8 gate checks status
        errors (list): Blocking validation failures
        elapsed_seconds (float): Import time

    Validation Gate (8 checks):
    1. Scene count > 0
    2. Character count > 0
    3. Story bible scene count == screenplay scene count
    4. No hollow scenes (every scene has beats/description)
    5. Character normalization success (no aliases remain)
    6. Dialogue preservation (beats retain dialogue)
    7. INTERCUT integrity (scene separation correct)
    8. Shot expansion completed (no empty scenes)

    Invariants:
        - NEVER bypasses import validation gate
        - NEVER allows hollow scenes to save
        - Scene count comes ONLY from INT./EXT. header count
        - Character names normalized BEFORE shot building
        - _canonical_scene_count stamped and immutable
        - One and ONLY ONE entry point for projects

    TODO: Extract implementation from orchestrator_server.py lines ~5500-6200
    """
    project = request.get("project")
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' field")

    screenplay_text = request.get("screenplay_text")
    story_bible = request.get("story_bible")

    # Read from file if uploaded
    if screenplay_file:
        screenplay_text = (await screenplay_file.read()).decode('utf-8')
    elif not screenplay_text:
        raise HTTPException(status_code=400, detail="Must provide screenplay_text or screenplay_file")

    logger.info(f"[FULL-IMPORT] Importing project={project}, screenplay_bytes={len(screenplay_text)}")

    # PLACEHOLDER: Call actual service layer function
    # return await service.full_import_screenplay(project, screenplay_text, story_bible)

    return {
        "project": project,
        "status": "not_implemented",
        "message": "⚠️  Full import route created but implementation pending Phase 3 migration"
    }


# ============================================================================
# STORY BIBLE GENERATION
# ============================================================================

@router.post("/auto/generate-story-bible")
async def generate_story_bible(request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    V21: LLM Story Bible Generation

    Expands screenplay into detailed story bible:
    - 6 fields per scene: beats, description, atmosphere, characters_present, int_ext, time_of_day
    - 4 fields per beat: description, character_action, dialogue, atmosphere
    - Character visual details and blocking
    - Location atmospherics

    Request:
        project (str): Project name
        screenplay_text (str, optional): Full screenplay (if re-gen from scratch)
        focus_scenes (list, optional): Only regenerate these scenes

    Response:
        project (str): Project name
        status (str): "generated" | "failed"
        scene_count (int): Bible scenes created
        beats_total (int): Total beats across all scenes
        enriched_fields (dict): Beat enrichment coverage
        elapsed_seconds (float): Generation time

    Invariants:
        - Scene count MUST match _canonical_scene_count from import
        - BLOCKS if count mismatch (prevents hollow saves)
        - Every scene MUST have beats + description
        - LLM provides character_action field (for later CHECK 5B injection)

    TODO: Extract implementation from orchestrator_server.py lines ~9800-10500
    """
    project = request.get("project")
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' field")

    screenplay_text = request.get("screenplay_text")
    focus_scenes = request.get("focus_scenes")

    logger.info(f"[GEN-STORY-BIBLE] Generating bible for project={project}, scenes={focus_scenes or 'all'}")

    # PLACEHOLDER: Call actual service layer function
    # return await service.generate_story_bible(project, screenplay_text, focus_scenes)

    return {
        "project": project,
        "status": "not_implemented",
        "message": "⚠️  Generate story bible route created but implementation pending Phase 3 migration"
    }


# ============================================================================
# AUTO-CAST CHARACTERS
# ============================================================================

@router.post("/v6/casting/auto-cast")
async def auto_cast_project(request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    V17.2: Auto-Cast Characters

    Matches each character to best AI actor from library (50 actors):
    - Appearance matching (visual similarity scoring)
    - Character trait matching (personality/tone)
    - Dialect/accent options
    - Age range compatibility
    - Narrative role importance

    Cast map created: character_name → actor_name + metadata

    Request:
        project (str): Project name
        manual_overrides (dict, optional): {character: actor_name}

    Response:
        project (str): Project name
        status (str): "cast_complete" | "partial_cast" | "failed"
        characters_cast (int): Characters with actors
        characters_uncast (int): Still need manual assignment
        cast_map_entries (int): Entries in cast_map.json
        actor_suggestions (dict): {character: [actor1, actor2, actor3]}
        elapsed_seconds (float): Casting time

    Invariants:
        - NEVER removes cast_map entries (idempotent)
        - Merge rule: if alias cast separately from canonical, reconcile them
        - _is_alias_of entries are hidden from UI (bundle builder filters them)
        - Lock field persists across re-cast

    TODO: Extract implementation from orchestrator_server.py lines ~5300-5500
    """
    project = request.get("project")
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' field")

    manual_overrides = request.get("manual_overrides", {})

    logger.info(f"[AUTO-CAST] Casting project={project}, manual_overrides={len(manual_overrides)}")

    # PLACEHOLDER: Call actual service layer function
    # return await service.auto_cast_project(project, manual_overrides)

    return {
        "project": project,
        "status": "not_implemented",
        "message": "⚠️  Auto-cast route created but implementation pending Phase 3 migration"
    }


# ============================================================================
# IMPORT VALIDATION GATE
# ============================================================================

@router.post("/v21/import-validation-gate")
async def import_validation_gate(request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    V21.9: Pre-Save Validation Gate

    Runs 8 critical checks before allowing import to save.

    Request:
        project (str): Project name
        dry_run (bool): Report only, don't persist

    Response:
        project (str): Project name
        status (str): "PASS" | "FAIL"
        checks: [
            {
                "name": "scene_count_valid",
                "status": "PASS",
                "detail": "25 scenes found"
            },
            ...
        ]
        critical_failures (int): 0 = safe to save
        warnings (int): Non-blocking issues
        elapsed_seconds (float): Validation time

    Gate Checks:
    1. scene_count > 0 and matches INT./EXT. headers
    2. character_count > 0
    3. story_bible.scene_count == screenplay.scene_count
    4. No hollow scenes (every scene has beats or description)
    5. Character normalization complete (aliases resolved)
    6. Dialogue preserved in beats
    7. INTERCUT integrity (no cross-location bleed)
    8. Shot expansion success (all scenes have shots)

    Invariants:
        - BLOCKS save if ANY check fails
        - WARNS on non-critical issues

    TODO: Extract implementation from orchestrator_server.py (canonical_ingestion.py integration)
    """
    project = request.get("project")
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' field")

    dry_run = request.get("dry_run", False)

    logger.info(f"[IMPORT-VALIDATION-GATE] Running for project={project}, dry_run={dry_run}")

    # PLACEHOLDER: Call actual service layer function
    # return await service.run_import_validation_gate(project, dry_run)

    return {
        "project": project,
        "status": "not_implemented",
        "message": "⚠️  Import validation gate route created but implementation pending Phase 3 migration"
    }
