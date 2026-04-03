# QUALITY GATE WIRING PLAN — V27.2

## Executive Summary

This document specifies EXACTLY where to insert the post-frame quality gate into the ATLAS V27 pipeline. The quality gate will introduce a review/variation/selection loop BETWEEN first frame generation and video generation, making B-roll script-aware while maintaining the V26 architectural separation of concerns.

**Current Pipeline Flow:**
```
generate-first-frames → [frames saved to first_frames/] → [operator calls kling-i2v manually]
```

**New Pipeline Flow:**
```
generate-first-frames → QUALITY GATE (review + variations + select) → render-videos (Kling/LTX)
```

---

## PART 1: V26 CONTROLLER INSERTION POINT

### Location: `atlas_v26_controller.py`, `render_scene()` method

**Current Structure (Lines 1024-2100+):**

The `render_scene()` method is the main orchestrator. It has 9 major phases plus probe shot system:

```
Phase A: SHOT AUTHORITY (lines 1194–1220)
   └─ Sets resolution, ref cap per shot

Phase B: EDITORIAL INTELLIGENCE (lines 1223–1259)
   └─ Tags for reuse, overlay, hold

Phase C: META DIRECTOR (lines 1262–1284)
   └─ 8-dimensional readiness check

Phase D: CONTINUITY MEMORY (lines 1287–1306)
   └─ Initialize spatial state tracking

Phase E: FILM ENGINE COMPILE (lines 1309–1412)
   └─ Unified prompt compilation
   ├─ E1.5: NARRATIVE BEAT INJECTION (lines 1415–1462)
   ├─ E2: DIALOGUE CINEMATOGRAPHY ENFORCER (lines 1465–1505)
   ├─ E3: PERPETUAL LEARNING (lines 1508–1536)
   ├─ E4: SCENE CONTINUITY ENFORCER (lines 1539–1562)
   ├─ E4b: LOCATION-AWARE BLOCKING ANALYZER (lines 1565–1595)
   └─ E5: SCENE VISUAL DNA + FOCAL ENFORCEMENT (lines 1598–1624)

Phase F: SHOT STATE COMPILE (lines 1627–1671)
   └─ Build ShotState objects with full render contract

Phase G: CHAIN POLICY (lines 1674–1711)
   └─ Classify chain membership (anchor, chain, independent, etc.)

Phase H: MODEL ROUTING (lines 1714–1749)
   └─ Route to LTX or Kling for video generation

Phase I: PAYLOAD VALIDATION (lines 1752–1784)
   └─ Model-safe enforcement, strip invalid params

EXECUTION (lines 1786+)
   └─ Delegate to orchestrator via compiled_batch
```

### Proposed New Phase: QUALITY GATE (After Phase I, Before EXECUTION)

**Insertion point:** Between line 1784 and line 1786

This new phase will:
1. Call quality gate API endpoint for per-shot review
2. Allow operator to approve/reject/request variations per shot
3. Collect variations if requested (multi-candidate generation)
4. Let operator select final frames before video generation
5. Analyze B-roll against story bible beats (narrative enrichment)

**Code Location for Insertion:**

```python
# ============================================================================
# PHASE J: QUALITY GATE (NEW — V27.2)
# Post-frame review, variations, and B-roll narrative enrichment
# ============================================================================
# [INSERT NEW CODE HERE — see PART 2 for exact implementation]
# ============================================================================

# ---- DELEGATE EXECUTION TO V26 THIN ENDPOINT ----
# V26.1: Film Engine compiled prompts go DIRECTLY to FAL via /api/v26/execute-generation.
# ... (rest of execution code continues at line 1786)
```

**What happens in Phase J:**

1. Collect all generated frames from orchestrator
2. For each shot, call `/api/v27/quality-gate/{project}/{scene_id}` with frame URL
3. Operator reviews frame + receives variation options + can override
4. Collect narrative analysis for B-roll shots (check against story bible)
5. Flag generic B-roll for enrichment before video generation
6. Return updated frames or request regeneration

---

## PART 2: NEW ORCHESTRATOR ENDPOINT

### File: `orchestrator_server.py`

### New Endpoint: `POST /api/v27/quality-gate/{project}/{scene_id}`

**Location to add:** After line 22678 (after the `generate-first-frames-turbo` endpoint, before other endpoints)

**Purpose:** Post-frame review and variation selection

**Request Body:**
```json
{
  "shot_id": "001_005B",
  "frame_url": "/api/media?path=first_frames/001_005B.jpg",
  "frame_base64": "...",  // Optional: raw JPG as base64
  "nano_prompt": "the film engine compiled prompt",
  "shot_type": "medium_close",
  "dialogue_text": "optional dialogue",
  "location": "GRAND FOYER",
  "characters": ["THOMAS", "ELEANOR"],
  "generate_variations": true,  // Request 3 candidates for selection
  "num_variations": 3,
  "skip_narrative_check": false,  // For B-roll: check against story bible
  "operator_feedback": "optional notes from operator"
}
```

**Response Body:**
```json
{
  "success": true,
  "shot_id": "001_005B",
  "quality_status": "APPROVED",  // or VARIATIONS_AVAILABLE or NEEDS_REGEN
  "selected_frame_url": "/api/media?path=first_frames/001_005B.jpg",
  "selected_frame_path": "first_frames/001_005B.jpg",
  "variations": [
    {
      "variant_id": "001_005B_var_1",
      "url": "/api/media?path=first_frames_variants/001_005B_var_1.jpg",
      "identity_score": 0.89,
      "composition_score": 0.82,
      "ranking": 1
    },
    {
      "variant_id": "001_005B_var_2",
      "url": "/api/media?path=first_frames_variants/001_005B_var_2.jpg",
      "identity_score": 0.85,
      "composition_score": 0.88,
      "ranking": 2
    },
    {
      "variant_id": "001_005B_var_3",
      "url": "/api/media?path=first_frames_variants/001_005B_var_3.jpg",
      "identity_score": 0.78,
      "composition_score": 0.75,
      "ranking": 3
    }
  ],
  "narrative_analysis": {
    "is_broll": false,
    "broll_narrative_check": null,  // Only if is_broll=true
    "story_beat": "Thomas confronts Eleanor about the letter",
    "beat_matches_visual": true,
    "warnings": []
  },
  "recommendation": "APPROVE — Identity 0.89, composition strong, dialogue markers clean",
  "operator_action_required": false
}
```

**Key Features:**

1. **Identity Scoring** — Uses vision service to verify character identity matches cast_map
2. **Composition Scoring** — Verifies framing matches shot type (close_up shows face fill, medium shows waist-up, etc.)
3. **Narrative Analysis** — For B-roll, checks beat keywords against story bible beats
4. **Variation Generation** — Optional 3-candidate multi-output from FAL with best-select ranking
5. **Blocking Gate** — Can recommend regeneration if identity <0.65 or composition mismatches shot type

**Supporting Functions to Create:**

```python
# In orchestrator_server.py, around line 22678+:

def quality_gate_analyze_frame(
    frame_path: str,
    shot_data: Dict,
    cast_map: Dict,
    story_bible: Dict,
    project_path: Path,
) -> Dict:
    """
    Analyze a generated first frame against quality criteria.
    Returns dict with identity_score, composition_score, narrative_flags.
    """
    # Uses vision_analyzer to extract:
    # - Character identity confidence
    # - Framing composition (close_up vs medium vs wide actual %)
    # - Shot composition rules (eye-line, shoulder position, etc.)
    pass


def quality_gate_generate_variations(
    shot_data: Dict,
    nano_prompt: str,
    num_variations: int = 3,
) -> List[Dict]:
    """
    Generate 3 candidate frames using FAL with num_outputs=3.
    Score all variants and return ranked list.
    """
    # Call FAL with num_outputs=3
    # Score via Basal Ganglia
    # Rank by identity + composition
    # Return sorted list
    pass


def quality_gate_check_broll_narrative(
    shot_data: Dict,
    story_bible: Dict,
    scene_id: str,
) -> Dict:
    """
    For B-roll shots, verify against story_bible beats.
    Flag generic B-roll (no characters, no props, just empty room).
    """
    # Extract shot description
    # Get story_bible scene beats for this scene_id
    # Check: does B-roll description match any beat keywords?
    # Flag if: "empty room" / "environmental detail only" / generic patterns
    # Suggest narrative enrichment
    pass


@app.post("/api/v27/quality-gate/{project}/{scene_id}")
async def quality_gate_review(
    project: str,
    scene_id: str,
    request: Dict = Body(...),
):
    """
    V27.2 Quality Gate — post-frame review and variation selection.
    Called AFTER first-frame generation, BEFORE video generation.

    Allows operator to:
    - Review first frames
    - Approve or request variations
    - Flag generic B-roll for narrative enrichment
    - Select final frame from candidates
    """
    shot_id = request.get("shot_id")
    frame_url = request.get("frame_url")
    nano_prompt = request.get("nano_prompt", "")
    shot_data = request.get("shot_data", {})
    generate_variations = request.get("generate_variations", False)
    num_variations = request.get("num_variations", 3)
    skip_narrative_check = request.get("skip_narrative_check", False)

    project_path = get_project_path(project)

    # Load necessary data
    shot_plan_path = project_path / "shot_plan.json"
    story_bible_path = project_path / "story_bible.json"
    cast_map_path = project_path / "cast_map.json"

    with open(shot_plan_path) as f:
        sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])

    shot_obj = next((s for s in shots if s.get("shot_id") == shot_id), {})

    cast_map = {}
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)

    story_bible = {}
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)

    # Quality analysis
    quality_analysis = quality_gate_analyze_frame(
        frame_url, shot_obj, cast_map, story_bible, project_path
    )

    variations = []
    if generate_variations:
        variations = quality_gate_generate_variations(
            shot_obj, nano_prompt, num_variations
        )

    # B-roll narrative check
    narrative_analysis = {
        "is_broll": shot_obj.get("_broll", False),
        "broll_narrative_check": None,
        "warnings": []
    }
    if narrative_analysis["is_broll"] and not skip_narrative_check:
        broll_check = quality_gate_check_broll_narrative(
            shot_obj, story_bible, scene_id
        )
        narrative_analysis.update(broll_check)

    # Determine quality status
    identity_score = quality_analysis.get("identity_score", 0)
    composition_score = quality_analysis.get("composition_score", 0)

    if identity_score < 0.65 or composition_score < 0.60:
        quality_status = "NEEDS_REGEN"
        operator_action = True
    elif variations:
        quality_status = "VARIATIONS_AVAILABLE"
        operator_action = True
    else:
        quality_status = "APPROVED"
        operator_action = False

    return {
        "success": True,
        "shot_id": shot_id,
        "quality_status": quality_status,
        "selected_frame_url": frame_url,
        "selected_frame_path": frame_url.replace("/api/media?path=", ""),
        "variations": variations,
        "narrative_analysis": narrative_analysis,
        "identity_score": identity_score,
        "composition_score": composition_score,
        "recommendation": f"{quality_status} — Identity {identity_score:.2f}, Composition {composition_score:.2f}",
        "operator_action_required": operator_action,
    }
```

---

## PART 3: PIPELINE INTEGRATION

### Where `generate-first-frames` Calls Quality Gate

**File:** `orchestrator_server.py`, around line 21300+

After the generate-first-frames endpoint has called FAL and saved frames, it will:

1. For each shot, call `/api/v27/quality-gate/{project}/{scene_id}`
2. Collect results
3. If operator action required, return early with variation options
4. If all approved, continue to video generation (or offer it as next step)

**Code snippet to add in `generate_first_frames()`:**

Around line 21300, after all frames are generated and saved:

```python
    # ===================================================================
    # V27.2 QUALITY GATE — Post-Frame Review and Variation Selection
    # After first frames are saved, run quality gate for each shot.
    # Operator can review, request variations, or approve.
    # B-roll is checked against story_bible for narrative content.
    # ===================================================================
    if request.get("enable_quality_gate", True):  # Default on, can disable
        quality_gate_results = {}
        _qg_blocked = False

        try:
            for shot in shots:
                shot_id = shot.get("shot_id")

                # Find the generated frame
                first_frames_dir = project_path / "first_frames"
                frame_path = None
                for ext in [".jpg", ".jpeg", ".png"]:
                    candidate = first_frames_dir / f"{shot_id}{ext}"
                    if candidate.exists():
                        frame_path = str(candidate)
                        break

                if not frame_path:
                    logger.warning(f"[V27.2 QG] No frame found for {shot_id}")
                    continue

                # Call quality gate
                qg_url = f"http://localhost:9999/api/v27/quality-gate/{project}/{scene_filter or 'batch'}"
                qg_payload = {
                    "shot_id": shot_id,
                    "frame_url": f"/api/media?path={frame_path}",
                    "nano_prompt": shot.get("nano_prompt", ""),
                    "shot_type": shot.get("shot_type", ""),
                    "dialogue_text": shot.get("dialogue_text", ""),
                    "location": shot.get("location", ""),
                    "characters": shot.get("characters", []),
                    "generate_variations": request.get("quality_gate_variations", False),
                    "skip_narrative_check": False,
                }

                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    try:
                        qg_resp = await client.post(qg_url, json=qg_payload)
                        if qg_resp.status_code == 200:
                            qg_result = qg_resp.json()
                            quality_gate_results[shot_id] = qg_result

                            # Check for blocks
                            if qg_result.get("quality_status") == "NEEDS_REGEN":
                                _qg_blocked = True
                                logger.warning(f"[V27.2 QG] {shot_id}: NEEDS_REGEN (identity {qg_result.get('identity_score',.0):.2f})")
                        else:
                            logger.error(f"[V27.2 QG] {shot_id}: HTTP {qg_resp.status_code}")
                    except Exception as e:
                        logger.warning(f"[V27.2 QG] {shot_id}: Request failed: {e}")

        except Exception as e:
            logger.warning(f"[V27.2 QG] Quality gate error (non-blocking): {e}")

        # Return quality gate results to operator if variations available or blocks exist
        if quality_gate_results:
            return {
                "success": True,
                "frames_generated": len(shots),
                "quality_gate_results": quality_gate_results,
                "blocked_for_review": _qg_blocked,
                "next_step": "POST /api/v27/quality-gate-select with selected frames, then POST /api/auto/render-videos",
                "broll_warnings": [
                    result.get("narrative_analysis", {})
                    for result in quality_gate_results.values()
                    if result.get("narrative_analysis", {}).get("is_broll")
                    and result.get("narrative_analysis", {}).get("warnings")
                ]
            }
```

---

## PART 4: FRAME SELECTION ENDPOINT

### New Endpoint: `POST /api/v27/quality-gate-select/{project}`

This endpoint is called AFTER operator reviews quality gate results and selects final frames.

**Location:** `orchestrator_server.py`, after the quality-gate endpoint

**Purpose:** Operator selects which frame variants to use before video generation

**Request Body:**
```json
{
  "project": "ravencroft_v17",
  "scene_id": "001",
  "selections": [
    {
      "shot_id": "001_005B",
      "selected_variant": "001_005B_var_1",  // or None to keep original
      "approved": true
    },
    {
      "shot_id": "001_006B",
      "selected_variant": null,  // Keep original
      "approved": true
    },
    {
      "shot_id": "001_007B",
      "selected_variant": null,
      "approved": false,
      "reason": "Needs regeneration - bad lighting"
    }
  ]
}
```

**Response Body:**
```json
{
  "success": true,
  "frames_locked": 8,
  "frames_needing_regen": 1,
  "next_step": "POST /api/auto/render-videos for Kling/LTX video generation",
  "video_endpoint": "/api/auto/render-videos"
}
```

**Code to add:**

```python
@app.post("/api/v27/quality-gate-select/{project}")
async def quality_gate_select_frames(project: str, request: Dict = Body(...)):
    """
    V27.2 Quality Gate Selection — operator finalizes frame choices.

    Called after operator reviews /api/v27/quality-gate results.
    Operator selects which frame variants to use for video generation.
    """
    selections = request.get("selections", [])
    scene_id = request.get("scene_id", "")

    project_path = get_project_path(project)
    first_frames_dir = project_path / "first_frames"
    variants_dir = project_path / "first_frames_variants"

    approved_count = 0
    regen_count = 0

    for selection in selections:
        shot_id = selection.get("shot_id")
        selected_variant = selection.get("selected_variant")
        approved = selection.get("approved", False)

        if not approved:
            regen_count += 1
            logger.info(f"[V27.2 QGS] {shot_id}: Marked for regeneration")
            continue

        if selected_variant:
            # Copy selected variant to main first_frames/ as the active frame
            variant_path = variants_dir / f"{selected_variant}.jpg"
            if variant_path.exists():
                import shutil
                target_path = first_frames_dir / f"{shot_id}.jpg"
                shutil.copy2(str(variant_path), str(target_path))
                logger.info(f"[V27.2 QGS] {shot_id}: Selected variant {selected_variant}")
                approved_count += 1
        else:
            # Keep original frame in place
            approved_count += 1

    logger.info(f"[V27.2 QGS] Frames locked: {approved_count} approved, {regen_count} need regen")

    return {
        "success": True,
        "frames_locked": approved_count,
        "frames_needing_regen": regen_count,
        "next_step": "POST /api/auto/render-videos for video generation",
        "video_endpoint": "/api/auto/render-videos",
    }
```

---

## PART 5: B-ROLL NARRATIVE ENRICHMENT

### How Quality Gate Makes B-Roll Script-Aware

**Concept:** When a B-roll shot is flagged as "generic" (no characters, no props, just environment), the quality gate suggests enrichment from story_bible beats.

**Implementation in `quality_gate_check_broll_narrative()`:**

```python
def quality_gate_check_broll_narrative(
    shot_data: Dict,
    story_bible: Dict,
    scene_id: str,
) -> Dict:
    """
    Check B-roll shot against story_bible beats.
    Flag generic B-roll for narrative enrichment.

    Returns dict with:
    - is_generic_broll: bool
    - beat_keywords: list of keywords from story beats
    - suggestions: list of narrative elements to add
    - warnings: list of concerns
    """

    # Extract B-roll description
    broll_desc = shot_data.get("description", "")
    broll_nano = shot_data.get("nano_prompt", "")

    # Generic patterns (V27.1 Creation Pack list)
    GENERIC_PATTERNS = [
        "environmental detail",
        "empty room",
        "no people",
        "atmosphere only",
        "context shot",
        "establishing view",
        "landscape",
        "wide angle",
        "establishing shot",
        "external establishing",
        "distant view",
    ]

    is_generic = any(
        pattern.lower() in (broll_desc + " " + broll_nano).lower()
        for pattern in GENERIC_PATTERNS
    )

    # Get story_bible beats for this scene
    scene_beats = []
    for scene in story_bible.get("scenes", []):
        if str(scene.get("scene_id")) == str(scene_id):
            scene_beats = scene.get("beats", [])
            break

    # Extract narrative keywords from beats
    beat_keywords = set()
    for beat in scene_beats:
        description = beat.get("description", "")
        # Extract nouns/verbs: "Thomas approaches the staircase" → ["Thomas", "staircase"]
        words = description.split()
        for word in words:
            if len(word) > 4:  # Skip small words
                beat_keywords.add(word.lower())

    # If generic, suggest narrative elements
    suggestions = []
    warnings = []

    if is_generic:
        warnings.append(f"Generic B-roll detected: missing narrative context from story beats")

        # Suggest props/elements from beats
        if beat_keywords:
            suggestions.append(f"Add story-relevant props: {', '.join(list(beat_keywords)[:3])}")

        # Suggest character activity
        for beat in scene_beats:
            char_action = beat.get("character_action", "")
            if char_action and "move" in char_action.lower():
                suggestions.append(f"Show character movement: {char_action}")
                break

    return {
        "is_generic_broll": is_generic,
        "beat_keywords": list(beat_keywords)[:5],
        "suggestions": suggestions,
        "warnings": warnings,
    }
```

**Example Output:**

B-roll shot `001_009B` (establishing library):
```json
{
  "is_generic_broll": true,
  "beat_keywords": ["fireplace", "letter", "shadows", "mahogany", "Eleanor"],
  "suggestions": [
    "Add story-relevant props: fireplace, letter, mahogany furnishings",
    "Show light catching the letter on the desk",
    "Add shadows suggesting late evening (time_of_day: dusk)"
  ],
  "warnings": [
    "Generic B-roll detected: missing narrative context from story beats"
  ]
}
```

Operator then has option to:
- Approve as-is
- Request variation with "add fireplace prominent, letter visible on desk"
- Regenerate with enriched prompt

---

## PART 6: WORKFLOW SUMMARY

### Old Workflow (Current)
```
1. POST /api/auto/generate-first-frames
   → frames saved to first_frames/
   → operator gets notification

2. Operator manually calls POST /api/v17/shot/kling-i2v for each shot
   → Kling generates video
```

### New Workflow (V27.2)
```
1. POST /api/auto/generate-first-frames
   → frames saved to first_frames/
   → [NEW] internally calls /api/v27/quality-gate for each shot
   → returns quality_gate_results with variations available

2. Operator reviews POST /api/v27/quality-gate results
   → sees identity scores, composition scores
   → sees B-roll narrative warnings
   → can request variations per shot

3. If variations needed: POST /api/v27/quality-gate with generate_variations=true
   → FAL generates 3 candidates per shot
   → Basal Ganglia ranks them
   → operator selects best

4. Operator confirms selections: POST /api/v27/quality-gate-select
   → selected variants copied to first_frames/
   → frames locked for video generation

5. [Automated or manual] POST /api/auto/render-videos
   → Kling/LTX generates videos using locked frames
   → same as before, but frames are quality-reviewed
```

---

## PART 7: SPECIFIC CODE LOCATIONS

### File 1: `atlas_v26_controller.py`

**Line 1024:** `def render_scene(self, scene_id: str, ...)`

**Insert Phase J at:**
- **After line 1784** (end of Phase I: Payload Validation)
- **Before line 1786** (start of DELEGATE EXECUTION comment)

**Code to insert:**
```python
        # ==================================================================
        # PHASE J: QUALITY GATE (V27.2) — Post-Frame Review & B-Roll Enrichment
        # Runs AFTER all prompts are compiled and validated.
        # Called by orchestrator's generate-first-frames after FAL returns frames.
        # Results allow operator to review, request variations, approve, or regen.
        # B-roll is checked for narrative content vs. story_bible beats.
        # ==================================================================
        # NOTE: This phase is non-blocking for now (advisory).
        # Quality gate blocking can be enabled later via doctrine config.
        #
        # The actual quality gate review happens in orchestrator_server.py:
        #   POST /api/v27/quality-gate/{project}/{scene_id}
        # This controller phase would be called if we want pre-execution analysis.
        # For now, quality gate is deferred to post-generation in orchestrator.

        result["phases"]["quality_gate"] = {
            "status": "deferred_to_post_generation",
            "operator_action_required": "review generated frames via /api/v27/quality-gate",
            "next_endpoints": [
                "POST /api/v27/quality-gate/{project}/{scene_id}",
                "POST /api/v27/quality-gate-select/{project}"
            ]
        }
        logger.info(f"[V27.2 QG] Quality gate deferred to post-generation (orchestrator)")
        # ==================================================================
```

### File 2: `orchestrator_server.py`

**Location 1: Quality Gate Analysis Endpoint**
- **After line 22678** (after `generate-first-frames-turbo` endpoint)

**Location 2: Quality Gate Selection Endpoint**
- **After Quality Gate Analysis Endpoint**

**Location 3: Modifications to `generate_first_frames()` endpoint**
- **Around line 21300** (after all frames are generated)

See code snippets in PART 2 and PART 3 above.

---

## PART 8: SUPPORTING FUNCTIONS NEEDED

### Function 1: `quality_gate_analyze_frame()`
- **Purpose:** Run vision analysis on generated frame
- **Inputs:** frame path, shot_data, cast_map, story_bible
- **Outputs:** identity_score, composition_score, framing_issues
- **Location:** New in `orchestrator_server.py` or tools/quality_gate.py

### Function 2: `quality_gate_generate_variations()`
- **Purpose:** FAL call with num_outputs=3 for multi-candidate selection
- **Inputs:** shot_data, nano_prompt, num_variations
- **Outputs:** List of variant dicts with paths, scores, rankings
- **Location:** New in `orchestrator_server.py` or tools/quality_gate.py

### Function 3: `quality_gate_check_broll_narrative()`
- **Purpose:** Analyze B-roll against story_bible beats
- **Inputs:** shot_data, story_bible, scene_id
- **Outputs:** Dict with is_generic_broll, beat_keywords, suggestions, warnings
- **Location:** New in `orchestrator_server.py` or tools/quality_gate.py

### Function 4: `rank_frame_variants()`
- **Purpose:** Score multiple frames via Basal Ganglia
- **Inputs:** List of frame URLs/paths
- **Outputs:** Ranked list by identity + composition score
- **Location:** tools/basal_ganglia_evaluator.py (extend existing)

---

## PART 9: DATA STRUCTURE CHANGES

### No changes to shot_plan.json schema
- Frames are stored in `first_frames/` (existing)
- Variants stored in `first_frames_variants/` (new directory, optional)

### No changes to cast_map.json or story_bible.json
- Quality gate reads these as-is

### New Optional Fields (can be added to shot_plan.json)
```json
{
  "shot_id": "001_005B",
  ...existing fields...,
  "_quality_gate_status": "APPROVED",  // or VARIATIONS_AVAILABLE, NEEDS_REGEN
  "_selected_variant": null,  // or "001_005B_var_1" if variant was selected
  "_quality_identity_score": 0.89,
  "_quality_composition_score": 0.82,
  "_broll_narrative_check": {
    "is_generic": false,
    "beat_keywords": ["staircase", "shadows"],
    "suggestions": []
  }
}
```

---

## PART 10: TESTING STRATEGY

### Unit Tests to Add

1. **test_quality_gate_analyze_frame.py**
   - Test identity scoring with known good/bad frames
   - Test composition scoring for close_up vs wide vs medium

2. **test_quality_gate_broll_narrative.py**
   - Test generic B-roll detection
   - Test beat keyword extraction from story_bible
   - Test suggestion generation

3. **test_quality_gate_variations.py**
   - Test FAL call with num_outputs=3
   - Test ranking algorithm
   - Test variant path generation

### Integration Tests

1. **test_generate_first_frames_with_quality_gate.py**
   - Full flow: generate-first-frames → quality gate → select → success response

2. **test_broll_enrichment.py**
   - B-roll generic detection → suggestion generation → operator sees warnings

---

## PART 11: TIMELINE & PHASING

### Phase 1: Core Quality Gate (Week 1)
- Add `/api/v27/quality-gate/{project}/{scene_id}` endpoint
- Implement quality_gate_analyze_frame() with vision service
- Integrate into generate-first-frames return response
- B-roll narrative check (basic pattern matching)

### Phase 2: Variations & Selection (Week 2)
- Add `/api/v27/quality-gate-select/{project}` endpoint
- Implement quality_gate_generate_variations() with FAL multi-output
- Add ranking logic (Basal Ganglia integration)
- Add UI elements for operator selection

### Phase 3: Automation (Week 3)
- Auto-approve frames with identity > 0.85 + composition > 0.80
- Auto-flag generic B-roll for narrative enrichment
- Connect to render-videos endpoint (auto-proceed or prompt operator)
- Add doctrine blocking option (make quality gate a hard gate)

---

## PART 12: SUCCESS CRITERIA

✓ Quality gate endpoint callable via POST /api/v27/quality-gate/{project}/{scene_id}
✓ Identity and composition scores returned
✓ Variations generated when requested (num_outputs=3 from FAL)
✓ Ranking of variants by Basal Ganglia
✓ B-roll flagged for narrative enrichment
✓ Operator can select frames before video generation
✓ Selected variants saved back to first_frames/
✓ Workflow: generate-first-frames → quality-gate → select → render-videos

---

## APPENDIX: V26 CONTROLLER PHASE REFERENCE

For quick reference, here are the exact line numbers of all V26 phases:

| Phase | Topic | Lines | Status |
|-------|-------|-------|--------|
| A | Shot Authority | 1194–1220 | ✓ |
| B | Editorial Intelligence | 1223–1259 | ✓ |
| C | Meta Director | 1262–1284 | ✓ |
| D | Continuity Memory | 1287–1306 | ✓ |
| E | Film Engine Compile | 1309–1412 | ✓ |
| E1.5 | Narrative Beat Injection | 1415–1462 | ✓ |
| E2 | Dialogue Cinematography Enforcer | 1465–1505 | ✓ |
| E3 | Perpetual Learning | 1508–1536 | ✓ |
| E4 | Scene Continuity Enforcer | 1539–1562 | ✓ |
| E4b | Location-Aware Blocking Analyzer | 1565–1595 | ✓ |
| E5 | Scene Visual DNA + Focal Enforcement | 1598–1624 | ✓ |
| F | Shot State Compile | 1627–1671 | ✓ |
| G | Chain Policy | 1674–1711 | ✓ |
| H | Model Routing | 1714–1749 | ✓ |
| I | Payload Validation | 1752–1784 | ✓ |
| **J** | **Quality Gate (NEW)** | **1785–?** | **⬜ PLANNED** |
| EXEC | Execution | 1786+ | ✓ |

---

## END OF PLAN

This document provides the EXACT wiring needed to insert the quality gate into ATLAS V27.2. All code locations are specified with line numbers. All supporting functions are detailed with signatures and purposes. The B-roll narrative enrichment is fully designed to be script-aware.

**Next Step for Implementation:** Begin Phase 1 (Core Quality Gate) with the endpoint at orchestrator_server.py, approximately after line 22678.
