# ATLAS V27.2 Quality Gate — Wiring Plan & Documentation

This directory contains the complete specification for wiring a post-frame quality gate into the ATLAS V27 pipeline. The quality gate introduces a review/variation/selection loop between first frame generation and video generation.

## Files in This Documentation Set

### 1. **QUALITY_GATE_WIRING_PLAN.md** (Primary Reference — 900 lines)
   - **Complete technical specification**
   - Exact line numbers for code insertion points
   - Full code snippets for all new endpoints
   - Supporting function signatures and purposes
   - Data structure changes and schemas
   - Testing strategy and success criteria

   **Read this file to:**
   - Understand exact WHERE to insert code (file + line number)
   - See complete code for new endpoints
   - Understand request/response formats
   - Plan implementation phases

### 2. **QUALITY_GATE_IMPLEMENTATION_SUMMARY.txt** (Quick Reference)
   - Executive summary of the wiring plan
   - High-level overview of changes
   - Key locations in code files
   - 3-phase implementation timeline
   - Success criteria checklist

   **Read this file to:**
   - Get the 5-minute version of the plan
   - Understand what changes where
   - See implementation phases
   - Check success criteria

### 3. **QUALITY_GATE_ARCHITECTURE_DIAGRAM.txt** (Visual Reference)
   - ASCII architecture diagrams
   - Current vs. new pipeline flow
   - Data flow through endpoints
   - Quality metrics and scoring rules
   - Vision integration details
   - B-roll narrative enrichment flow
   - Controller phase structure

   **Read this file to:**
   - Visualize the pipeline architecture
   - Understand data flow
   - See scoring thresholds
   - Understand phase structure

## Quick Start

### For Implementation
1. Read **QUALITY_GATE_WIRING_PLAN.md** (PART 1 and PART 2)
2. Understand insertion points in `atlas_v26_controller.py` and `orchestrator_server.py`
3. Follow PART 3 for generate-first-frames integration
4. Implement supporting functions from PART 9

### For Review
1. Start with **QUALITY_GATE_IMPLEMENTATION_SUMMARY.txt**
2. Review architecture in **QUALITY_GATE_ARCHITECTURE_DIAGRAM.txt**
3. Dive into details in **QUALITY_GATE_WIRING_PLAN.md** as needed

## Key Points at a Glance

**What is the quality gate?**
- A post-frame review system that validates generated first frames
- Runs AFTER first frame generation, BEFORE video generation
- Allows operators to approve, request variations, or reject frames
- Makes B-roll script-aware by checking against story bible

**Where does it insert into the pipeline?**
- V26 Controller: New Phase J at line 1785 (deferred to orchestrator)
- Orchestrator: Two new endpoints for analysis and selection
- Integration: Added to generate-first-frames endpoint

**What does it do?**
1. Analyze each generated frame (identity score, composition score)
2. [Optional] Generate 3 variants per frame via FAL
3. Check B-roll against story bible beats for narrative content
4. Let operator select final frames before video generation
5. Lock frames for video generation (Kling/LTX)

**How does it fit with existing architecture?**
- Maintains V26 separation: Film Engine (prompt authority), Orchestrator (execution)
- Non-blocking: if quality gate fails, pipeline continues (advisory mode)
- Can be promoted to blocking gate later via doctrine
- Uses existing vision analyzer + Basal Ganglia components

## Implementation Timeline

### Phase 1 (Week 1): Core Quality Gate
- [ ] Add `/api/v27/quality-gate/{project}/{scene_id}` endpoint
- [ ] Implement identity/composition analysis
- [ ] Integrate into generate-first-frames
- [ ] Basic B-roll narrative check

### Phase 2 (Week 2): Variations & Selection
- [ ] Add `/api/v27/quality-gate-select/{project}` endpoint
- [ ] Multi-candidate generation (FAL num_outputs=3)
- [ ] Ranking via Basal Ganglia
- [ ] UI for operator selection

### Phase 3 (Week 3): Automation
- [ ] Auto-approve high-scoring frames
- [ ] Auto-flag generic B-roll
- [ ] Connect to render-videos
- [ ] Optional doctrine blocking

## New Endpoints

### POST /api/v27/quality-gate/{project}/{scene_id}
Analyzes a generated first frame and returns quality metrics.

**Request:**
```json
{
  "shot_id": "001_005B",
  "frame_url": "/api/media?path=first_frames/001_005B.jpg",
  "nano_prompt": "...",
  "shot_type": "medium_close",
  "characters": ["THOMAS"],
  "generate_variations": true,
  "num_variations": 3
}
```

**Response:**
```json
{
  "success": true,
  "quality_status": "APPROVED",
  "identity_score": 0.89,
  "composition_score": 0.82,
  "variations": [...],
  "narrative_analysis": {...},
  "operator_action_required": false
}
```

### POST /api/v27/quality-gate-select/{project}
Operator finalizes frame selections before video generation.

**Request:**
```json
{
  "scene_id": "001",
  "selections": [
    {
      "shot_id": "001_005B",
      "selected_variant": "001_005B_var_1",
      "approved": true
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "frames_locked": 8,
  "frames_needing_regen": 1,
  "next_endpoint": "/api/auto/render-videos"
}
```

## B-Roll Script Awareness

The quality gate makes B-roll narrative-aware:

1. **Detection:** Flags generic B-roll ("empty room", "no people", etc.)
2. **Analysis:** Extracts keywords from story bible beats
3. **Suggestions:** Recommends narrative enrichment (props, character action, etc.)
4. **Options:** Operator can approve original, request variation, or skip

Example:
```
Shot 001_009B: "library interior, dark wood"
Story beats mention: fireplace, shadows, letter, Eleanor

Suggestions:
- Add fireplace prominent in frame
- Show light catching letter on desk
- Add subtle character shadow

Operator can:
✓ Approve as-is
↻ Request variation with "add fireplace, letter visible"
✗ Reject for regeneration
```

## Success Criteria

The quality gate is complete when:
- ✓ POST /api/v27/quality-gate/{project}/{scene_id} functional
- ✓ Identity and composition scores returned with frames
- ✓ Variations generated on request (3 candidates)
- ✓ Variants ranked by Basal Ganglia
- ✓ B-roll flagged for narrative enrichment
- ✓ Operator can select final frames before video gen
- ✓ Selected variants saved to first_frames/
- ✓ Full workflow: generate-first-frames → quality-gate → select → render-videos

## Files Modified

### atlas_v26_controller.py
- **render_scene() method** (line 1024)
- **Insert Phase J** (after line 1784)
- Non-blocking advisory phase

### orchestrator_server.py
- **generate_first_frames() endpoint** (line 20926)
  - Add quality gate calls after frame generation (line ~21300)
- **NEW: quality_gate_review() endpoint** (after line 22678)
  - POST /api/v27/quality-gate/{project}/{scene_id}
- **NEW: quality_gate_select_frames() endpoint** (after quality_gate_review)
  - POST /api/v27/quality-gate-select/{project}

## Supporting Functions to Create

- `quality_gate_analyze_frame()` — Vision analysis
- `quality_gate_generate_variations()` — FAL multi-output
- `quality_gate_check_broll_narrative()` — Story bible matching
- `rank_frame_variants()` — Basal Ganglia ranking

## Architecture Reference

```
Current (V27.1):
  generate-first-frames → [save frames] → [operator manually calls kling-i2v]

New (V27.2):
  generate-first-frames 
    → [save frames]
    → /api/v27/quality-gate (analyze)
    → [operator reviews + selects]
    → /api/v27/quality-gate-select (lock)
    → /api/auto/render-videos (Kling/LTX)
```

## Questions?

Refer to:
1. QUALITY_GATE_WIRING_PLAN.md — Detailed technical spec
2. QUALITY_GATE_ARCHITECTURE_DIAGRAM.txt — Visual reference
3. QUALITY_GATE_IMPLEMENTATION_SUMMARY.txt — Quick overview

---

**Document Created:** 2026-03-17
**ATLAS Version:** V27.2
**Status:** Research phase (planning complete, ready for implementation)
