# CLAUDE.md - ATLAS V36.0 PRODUCTION SYSTEM

## HEADER

**Universal Project Standard:** `PRODUCTION_STANDARD.md` — applies to ALL projects (Victorian Shadows, Crown Heights, AIFL, any future project). Every new project MUST pass that checklist before first generation. CLAUDE.md defines system laws; PRODUCTION_STANDARD.md defines the per-project contract.

**Version:** V36.5 (2026-03-29 — Chain Arc Intelligence built (tools/chain_arc_intelligence.py), three-act chain structure ESTABLISH→ESCALATE→PIVOT→RESOLVE wired into runner, V36.4 location master anchoring PROVEN on scene 006 (kitchen held 4/4 shots), arc_position enrichment universal for all scenes)
**Date:** 2026-03-29
**Status:** GENERATION READY — Chain environment drift SOLVED (V36.4). Three-act chain intelligence WIRED (V36.5). Arc positions computed for all 6 scenes. Kitchen fix proven: $2.76 targeted regen, 9.9 min.
**Codebase:** ~100,000 lines | 420+ endpoints | 39 agents | 15 invariants | 10 Movie Lock contracts
**Tests:** 376+ green: 132 CPC + 72/76 editorial + 74 continuity + 67 film engine + 31 regression | Generation gate: 30 checks | Session enforcer: 47 pass / 0 block
**Architecture:** Three-Layer (Intelligence → Truth → Execution). Universal Runner (`atlas_universal_runner.py`) is the CANONICAL generation path for any script, any scene. Beat enrichment → truth contracts → generation gate → nano/edit first frames → vision judge → spatial comparison gate → end-frame chaining → **Kling v3/pro multi-prompt video (PRIMARY)** → stitch. Seedance RETIRED as of V31.0.
**Last Incident:** V31.0 (2026-03-24) — Seedance retired, route_shot() fixed, end-frame chain fixed. V35.0 (2026-03-26) — Vision backend init bug fixed (session_enforcer didn't load .env before checking backends → gemini_vision showed as unavailable despite GOOGLE_API_KEY being set). Gemini 0-5 score normalized to 0-1. Spatial comparison gate confirmed wired. Layer 2 (vision backend) + Layer 7 (I-score normalization) both closed. Stage 5 (story_judge + vision_analyst) wired as advisory non-blocking imports.

### V35.0 EVOLUTIONARY ROADMAP — ATLAS CONSCIOUSNESS STAGES

**Stage 1 — Spinal Cord (V17–V21):** Constitutional laws. Hard reject rules, no memory. Pure reflex generation. Script parser → shot expansion → model lock. The system could generate but not reason.

**Stage 2 — Brainstem (V22–V24):** Autonomic pipeline. Script parser → story bible → auto-caster → continuity memory. End-to-end generation without active intelligence. Beat enrichment, basic chain policy.

**Stage 3 — Mammalian Brain (V25–V28):** Three-Layer Architecture. Truth contracts, beat enrichment, C8 Intelligence Serialization, OTS enforcer, spatial_timecode, 180° rule, screen position lock. Cross-shot spatial awareness. The system began *understanding* scenes, not just generating them.

**Stage 4 — Optic Nerve (V29–V35):** Vision connection. Gemini Vision firing real I-scores. Spatial comparison gate. Camera Position DNA (8 rooms × 4 angles). Pre-video quality gate. Auto-revision judge. Parallel generation mode. E-shot isolation guards. The system can now **see** what it generates and close the generate → perceive → reward → improve loop.

**Stage 5 — Prefrontal Cortex (V35+):** `story_judge.py` (670 lines, narrative validation — beat coverage, pacing, arc coherence) and `vision_analyst.py` (911 lines, 8-dimensional visual scoring — identity, location, blocking, mood, dialogue fidelity, camera, continuity, emotional arc) wired as advisory modules. Global perception — seeing the **film as a whole**, not just individual frames. Next: call these at scene-close and stitch-time to write advisory reports. Eventually: loop back into shot regen decisions.

**Stage 6 — Cybernetic Control (V36):** `tools/failure_heatmap.py` — formal control theory layer. Three control loops (inner/middle/outer), failure taxonomy with heat scores, per-shot metrics schema, production readiness assessment (GREEN/YELLOW/RED), three view generators (director/systems/executive). The system can now measure its own failure modes in film-grammar terms and report production health quantitatively.

**Stage 7 — Chain Consciousness (V36.5):** `tools/chain_arc_intelligence.py` — three-act chain structure. Every shot knows WHERE it sits in the emotional arc: ESTABLISH (opening declares room/identity/tone), ESCALATE (middle carries what opening declared under rising pressure), PIVOT (turning point — room holds but emotion shifts), RESOLVE (ending closes arc, releases room DNA for next scene). V36.4 proved that the opening's truth was already sufficient — the middle just forgot to carry it. V36.5 makes that carry CONSCIOUS. Outgoing hints prevent room DNA contamination across scene boundaries. The chain now has predictive intelligence from frame 1 through frame N.

### V36.0 CONTROL THEORY — CYBERNETIC ARCHITECTURE

**Three Control Loops:**

**Inner Loop (Shot Correctness):** Fast, local, cheap.
- Checks: shot type, OTS direction, character count, EXT/INT, artifacts
- Output: pass / fail / targeted regen

**Middle Loop (Scene Continuity):** Slower, relational.
- Checks: room consistency, screen direction, eyeline continuity, blocking
- Output: scene warnings, canonical fixes, continuity injection

**Outer Loop (Production Stability):** Slowest, global.
- Checks: runner alive, ledger current, video_url integrity, completion rate
- Output: continue / isolate / halt

**Five Control Truths:**
1. Measurement must be domain-native (film grammar, not scores)
2. Error classes need distinct actuators (wrong room ≠ wrong face)
3. Supervisory health matters as much as model quality
4. Feedforward prevention is cheaper than feedback correction
5. Stable production comes from bounded correction

**Failure Heatmap:** `tools/failure_heatmap.py`
- Creative failures: OTS_DIRECTION_FAIL, SHOT_TYPE_FAIL, CHARACTER_COUNT_FAIL, LOCATION_CONTEXT_FAIL, PROP_BEAT_FAIL, ARTIFACT_FAIL, IDENTITY_DRIFT, CONTINUITY_DRIFT
- Operational failures: VIDEO_URL_MISSING, FILE_STATE_MISMATCH, RUNNER_DEAD, LEDGER_STALE, SCORE_HEURISTIC_ONLY, PROCESS_TIMEOUT, API_RETRY_EXHAUSTED
- Severity: cinematic (0-3) + system (0-3) = heat (0-6)
- Thresholds: GREEN (≥90% first-pass, <5% hard fails, <2% ops fails) / YELLOW (75-89%) / RED (<75% or ops severity-3)
- Three views: `generate_director_view()` (scene × shot grid), `generate_systems_view()` (dense diagnostic), `generate_executive_view()` (compressed status)

**Usage:**
```bash
python3 tools/failure_heatmap.py --project-dir pipeline_outputs/victorian_shadows_ep1 --view all
```

```python
from tools.failure_heatmap import build_heatmap, assess_production_readiness, generate_executive_view
heatmap = build_heatmap('pipeline_outputs/victorian_shadows_ep1/shot_plan.json',
                         'pipeline_outputs/victorian_shadows_ep1/first_frames',
                         'pipeline_outputs/victorian_shadows_ep1/videos_kling_lite')
print(assess_production_readiness(heatmap))
print(generate_executive_view(heatmap))
```

### V36.0 STORY STATE CANON — Story-Legible Change Enforcement

**Module:** `tools/story_state_canon.py` — QA/validation layer. Returns verdicts only, never mutates.

**Authority order (V36 Section 0 compliant):**
1. Story Bible — who is here, what phase, what changed, what must be true
2. Scene Contract — what this scene requires visually and emotionally
3. Shot Contract — what this specific shot must show
4. Timecode — supporting coordinate for pacing, not ruler of truth

**Three change types (all others are violations):**
- `hard_lock` — must match exactly within same scene (wardrobe, architecture, screen direction)
- `canon_progression` — allowed to evolve because story authorizes it (next morning wardrobe, post-event damage)
- `controlled_variance` — can vary slightly without being wrong (micro-pose, fabric folds, atmospheric density)

**The enforcement rule:** Same unless changed by canon. Different only when story authorizes it.

**Static canon scenes (001-006):**
- 001: GRAND FOYER — Eleanor + Thomas arrive. Wardrobe hard-locked. Briefcase required on Eleanor.
- 002: LIBRARY — Nadia solo. Camera required. Letter discovered. No Eleanor/Thomas.
- 003: DRAWING ROOM — Eleanor + Raymond. Dust sheets covering all furniture. Raymond in overcoat.
- 004: GARDEN — Thomas solo. Overcast grey. Dead roses. Velvet box with ring.
- 005: MASTER BEDROOM — Nadia solo. Dim light. Journal discovered. Camera required.
- 006: KITCHEN — Eleanor + Nadia. Copper pots. Phone call. Journal revealed.

**Validation functions:**
```python
from tools.story_state_canon import get_canon_state, validate_against_canon, validate_scene

# Get canon for a scene
canon = get_canon_state("001")  # or get_canon_state("001", project_dir)

# Validate a single shot against its scene's canon
issues = validate_against_canon(shot_dict, canon)  # returns list of violations

# Validate all shots in a scene (batch)
result = validate_scene("001", shots, project_dir)
# result.violations = [{shot_id, issues}]

# Add _canon_state_ref to all shots (Controller calls this, writes result to disk)
shots = add_canon_ref_to_shots(shots, project_dir)
```

**Wire discipline:** This module is ADVISORY (QA layer). Controller reads violations and decides whether to regen. Heatmap reads the output for classification. Neither Heatmap nor QA may act on violations directly.

### V35.0 SYSTEM CAPABILITIES
- Parallel + Chain generation modes (`--frames-only`, `--videos-only`, `--mode lite|full`)
- Camera Position DNA: wide_master, interior_atmosphere, reverse_angle, insert_detail per room (8 room templates)
- E-shot Isolation: `_no_char_ref` + `_is_broll` guards at runner lines (E01/E02/E03 skip Wire A)
- Spatial Comparison Gate: Gemini compares E-shots for visual distinctness, writes `spatial_gate_results/`
- Auto-Revision Judge: 8-dimension video scoring with hard-reject thresholds (`auto_revision_judge.py`)
- Pre-Video Quality Gate: holistic frame scoring (location + identity + blocking + mood) before Kling call
- Content Fidelity Checks: wardrobe, dialogue uniqueness, E-shot purity, story bible match
- Stage 5 Advisory: `story_judge.py` + `vision_analyst.py` imported, awaiting scene-close call wiring
- ECC: keep-up (hourly), proof-gate (4h), doctrine-sync (daily)

### V36.5 SESSION LEARNINGS (BINDING — 2026-03-29)

**V36.4 FIX — CHAIN ENVIRONMENT DRIFT (PROVEN 2026-03-29):**
- Root cause: Chain reframe prompts had ZERO Room DNA text and ZERO location master image. Each successive reframe diluted the environment until it became a blank white room (observed: kitchen → gray → white void across 4 shots).
- Fix: Two-layer room anchor — (1) Location master image as 3rd entry in reframe `image_urls` array `[last_frame, char_ref, loc_master]`, (2) Room DNA text block in reframe prompt, (3) Compact "Setting:" line in Kling video prompts for chain groups 2+.
- Proof: Scene 006 M03+M04 targeted regen ($2.76, 9.9 min) — kitchen held through all 4 shots. Previously M03 was gray shift, M04 was white void. After fix: Victorian kitchen with copper pots, plate rack, wooden table visible in every frame.
- Wire locations: runner ~line 3280 (reframe Room DNA), ~line 3310 (reframe location master image_urls), ~line 2900 (Kling "Setting:" anchor), ~line 4206 (context dict with _location_master_path).

**V36.5 — THREE-ACT CHAIN INTELLIGENCE (WIRED 2026-03-29):**
- New module: `tools/chain_arc_intelligence.py` — computes `_arc_position` per shot from beat structure.
- Four positions: ESTABLISH (opening), ESCALATE (middle), PIVOT (turning point), RESOLVE (ending).
- Carry directives: Each position gets a `_arc_carry_directive` that tells the chain what to do.
- Outgoing hints: Last shot in scene gets `_arc_release` with `release_room_dna=True` and hint text for next scene's chain anchor.
- Wired in runner: arc enrichment at ~line 4210 (before groups), arc modifier in Kling prompt at ~line 2920, arc-aware reframe at ~line 3290.
- All 6 scenes validated: correct ESTABLISH→ESCALATE→PIVOT→RESOLVE mapping on all 43 shots.
- Session enforcer updated: `chain_arc_intelligence.enrich_shots_with_arc()` added to import check list.

**KEY INSIGHT (user-originated, 2026-03-29):**
Opening declares. Middle carries. Ending releases. The first frame's knowledge is not just an opening tool — it is the predictive intelligence for the entire chain. Every shot already knows what frame 1 declared. V36.4 fixed the forgetting. V36.5 makes the carry CONSCIOUS with arc positions.

### V35.0 SESSION LEARNINGS (BINDING — 2026-03-26)

**V35.0 FIXES (DO NOT RE-BREAK):**

- `tools/session_enforcer.py` lines 26–34: **ENV LOAD FIX.** Added `.env` parser at module top BEFORE any imports that check `os.environ`. Root cause: session_enforcer was importing `vision_judge` which calls `_backend_available("gemini_vision")` → checks `os.environ.get("GOOGLE_API_KEY")` at call time, but `.env` was never loaded in the enforcer's process. Result: enforcer always reported `Vision backends available: ['heuristic']` even when GOOGLE_API_KEY was correctly set. Fix: manual `.env` parse that only sets keys not already in environment (safe for subprocess inheritance).

- `tools/vision_judge.py` `_score_via_gemini()` (~line 672): **I-SCORE NORMALIZATION.** Added `if identity_score > 1.0: identity_score = round(identity_score / 5.0, 3)`. Root cause: ECC flagged Gemini returns 0-5 scale but reward formula `R = I×0.35 + V×0.40 + C×0.25` expects 0-1. Without normalization, I=3.5 → R blows past 1.0 and ledger entries are meaningless. With normalization, I=0.70 → R stays in valid range.

**V35.0 CONFIRMED (already wired, no changes needed):**
- `atlas_universal_runner.py` spatial_comparison_gate: imported at line 74, called at line ~3988 — already wired post-frame-generation. NOT a gap.
- `/api/auto/run-frames-only` endpoint: line 35410 in orchestrator_server.py — exists.
- `/api/auto/run-videos-only` endpoint: line 35483 in orchestrator_server.py — exists.
- UI Generate Frames + Generate Videos buttons: lines 24211/24217 in auto_studio_tab.html — confirmed.
- Gemini model `gemini-2.5-flash`: already correct in `_GEMINI_MODEL` at line 556 — no change needed.

**CAMERA POSITION DNA SYSTEM (V35.0 — production-confirmed):**
- E01/E02/E03 shots receive distinct Room DNA blocks from `tools/scene_visual_dna.py`
- After generation, `run_spatial_gate()` compares all E-shots via Gemini Vision as a set
- If any pair is SIMILAR/IDENTICAL → reprompt suggestions written to `spatial_gate_results/{scene_id}_spatial_gate.json`
- Operator reviews before approving frames (non-blocking — proceeds even if Gemini unavailable)
- Scene DNA templates: 8 room types (foyer, library, drawing_room, bedroom, kitchen, staircase, exterior, cemetery)

**PARALLEL vs CHAIN GENERATION MODES:**
- `--frames-only`: generates all first frames in parallel (one per shot), stops before video
- `--videos-only`: reads approved frames from disk, runs Kling sequentially within scene (end-frame chain), parallel across scenes
- Both modes available via: UI buttons, `/api/auto/run-frames-only`, `/api/auto/run-videos-only`
- Approval gate: `_approval_status=AWAITING_APPROVAL` blocks `--videos-only` until operator approves

**E-SHOT ISOLATION (V35.0 — confirmed):**
- E01/E02/E03 (establishing/tone) shots skip Wire A identity regen (no character refs)
- Back-to-camera shots skip Wire A (no face visible — scoring meaningless)
- Both skips confirmed at runner line ~2165 (V30.4 back-to-camera skip) and the E-shot check

**PRODUCTION PROTOCOL (V35.0 — 2-stage validated run):**
```bash
# Stage 1: Generate frames, review, approve
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# Review in UI filmstrip → thumbs up each good frame

# Stage 2: Generate videos from approved frames
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --videos-only

# Both stages together (trusted re-run only)
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite
```

### V31.0 SESSION LEARNINGS (BINDING — 2026-03-24)

**V31.0 FIXES (DO NOT RE-BREAK):**

- `atlas_universal_runner.py` `route_shot()` (~line 1381): ALL branches now return `"kling"`. Previous code returned `"seedance"` on every branch — this meant `kling_count` in the scene header always showed 0 even when Kling was running. Now correctly shows Kling count. Seedance branch (`if _vid_model in ("seedance", "seeddance")`) at ~line 3376 will never fire unless `ATLAS_VIDEO_MODEL=seedance` is explicitly set in env — do not set this.

- `atlas_universal_runner.py` `gen_scene_multishot()` (~line 2612): **END-FRAME CHAIN FIX.** After each group's video downloads, `extract_last_frame()` runs → uploads → `start_url` advances to that frame. Previous code uploaded `first_frame_path` ONCE and reused it for all groups — causing "20 shots all starting from same frame" bug. Now each group continues from where the previous clip ended.

- `ACTIVE_VIDEO_MODEL` default at line 324: **already `"kling"`** — no change needed. CLAUDE.md was documenting `"seedance"` as default in error.

**V31.0 DO-NOT-BREAKS (from prior sessions, still enforced):**
- V29.9: 1 beat per Kling call — no multi-beat batching
- V29.10: Kling prompt ≤ 512 chars, type label + beat pos + action + dialogue only — NO mood/atmosphere (goes in nano frame, not Kling)
- Wire A budget: 2 regens per scene max
- `inject_tone_shots()` scene-aware (library vs foyer vs generic)
- Gemini circuit breaker: 3 consecutive zeros → trip → fall to claude_haiku

### V30.5 SESSION LEARNINGS (BINDING — 2026-03-24)

**V30.5 FIXES (DO NOT RE-BREAK):**
- `atlas_universal_runner.py` `inject_tone_shots()` (~line 2684): E01 and E03 now check `is_library` BEFORE `is_estate`. Root cause: `is_estate` was True for all scenes in HARGROVE ESTATE, so library scenes got identical iron-gates E01 and door-handle E03 as the foyer scene. Fix: `if is_library:` branch added to E01 (library wing exterior with warm window glow) and E03 (book spine + hidden letter close-up). E02 already had `elif is_library:` branch — unchanged.
- `orchestrator_server.py` `regen_shot()` (~line 35748, diagnostic logic ~35795): V30.5 diagnostic regen wired. Before applying identity boost, calls `gemini-2.5-flash` vision to classify rejection as IDENTITY/LOCATION/CAMERA/BLOCKING/STORY_BEAT/TONE. IDENTITY → existing boost path. All others → clear `nano_prompt`, store `_regen_patch` hint, rebuild from description. Fully non-blocking: Gemini failure → falls back to IDENTITY default.
- `shot_plan.json` (victorian_shadows_ep1): Fixed 001_E02 (checkerboard floor → single curved staircase + dome + tapestries + Persian carpet, matching character shots). Fixed 001_M04 (OTS-A duplicate → proper OTS-B: over-Eleanor's-shoulder, Thomas faces camera). Fixed 002_M04 (cleared identity boost, three-quarter back-to-camera description). Fixed 002_E01/E02/E03 (library-specific content: wing exterior, richer shelf description, book spine insert).

**REWARD SIGNAL — PROVEN (2026-03-24):**
- Scene 002 production run: M01=1.00, M02=1.00, M03=1.00, M04=1.00 (all real VLM, not 0.75 heuristic)
- Scene 001 production run: M01=4.00, M02=0.90, M03=5.00, M04=1.00, M05=5.00 (VLM active)
- I≠0.75 CONFIRMED on all character shots. Reward ledger no longer stale.
- GOOGLE_API_KEY and FAL_KEY both loaded before vision_judge import — Gemini fires on CLI runs.

**WIRE POSITIONS (V31.0 — confirmed by grep 2026-03-25):**
- Wire A: runner line ~2184 (`_wire_a_can_regen` check in `gen_frame`), budget reset at ~2960 (top of `run_scene`)
- Wire B: runner line ~3658 (`_fail_sids` filter before stitch)
- Wire C: runner line ~3451 (`[WIRE-C]` frozen video regen in `_analyze_video` path)
- Wire D: runner line ~85 (`# ── SCREEN POSITION LOCK — Wire D (V30.4)`)
- Wire A back-to-camera skip: runner line ~2165 (`# V30.4: Skip Wire A for back-to-camera shots`)
- Diagnostic regen: orchestrator_server.py ~line 35748 (regen_shot def), ~35795 (`# V30.5: Diagnostic regen`)

**ACTUAL P0s AS OF V30.5 — NONE. ALL RESOLVED.**
- ✅ Reward signal proven — I=1.00 on character shots
- ✅ Room architecture consistent — 001_E02 matches character shots
- ✅ OTS-B angle correct — 001_M04 shows proper over-shoulder
- ✅ Tone shots scene-aware — library gets library content, foyer gets foyer content
- ✅ Gemini API paid plan active — text + vision both operational
- Next: review filmstrip in UI, approve frames, run --videos-only for Scene 001 and 002

### V30.3 SESSION LEARNINGS (BINDING — R77 keepup 2026-03-23, doc sync applied)

**V30.3 ADDITIONAL FIXES THIS SESSION (DO NOT RE-BREAK):**
- `atlas_universal_runner.py` lines 75–88: GOOGLE_API_KEY loaded from `.env` BEFORE `vision_judge` import. Same pattern as FAL_KEY (V29.16) and OPENROUTER_API_KEY (R46). Root cause: on CLI runs `.env` wasn't loaded until much later, so `_backend_available("gemini_vision")` returned False → all shots fell to 0.75 heuristic. Server path was fine (orchestrator loads env early). Now both paths consistent.
- `atlas_universal_runner.py` lines 210–223: Wire A budget cap — `_WIRE_A_MAX_REGENS_PER_SCENE = 2`. Three helper functions: `_wire_a_can_regen(scene_prefix)`, `_wire_a_consume(scene_prefix)`, `_wire_a_reset(scene_prefix)`. Counter keyed by `sid[:3]` (e.g. `"001"`). If budget exhausted: `[WIRE-A] Scene 001: regen budget exhausted (2/2) — flagging for review, not retrying 001_M04`. Reset at top of `run_scene()`.
- `tools/vision_judge.py` lines 513–546: Gemini circuit breaker — `_CONSECUTIVE_ZEROS`, `_ZERO_CIRCUIT_BREAKER=3`, `_GEMINI_TRIPPED`. `_cb_record_result(identity_scores)` called after every Gemini path in `route_vision_scoring()`. 3 consecutive all-zero results → `_GEMINI_TRIPPED=True` → loud `[VISION] ⚡ CIRCUIT BREAKER` print. Non-zero score resets counter and clears trip.
- `tools/vision_judge.py` line 900: exclusive-mode guard now `if _GEMINI_IS_EXCLUSIVE and gemini_available and not _GEMINI_TRIPPED`. When tripped, falls through to legacy chain (claude_haiku → openrouter → florence_fal → heuristic) — does NOT return FAIL scores, does NOT block generation.

**V30.3 P0s — BOTH RESOLVED IN V30.4/V30.5:**
- ✅ Reward ledger — PROVEN 2026-03-24. I=1.00 on all character shots (Scene 001 + 002).
- ✅ I ≠ 0.75 verified, timestamp > 2026-03-24T04:35.

**V30.1 FIXES APPLIED THIS SESSION (DO NOT RE-BREAK):**
- `prep_engine.py`: `ltx_prompts_present` check INVERTED — was halting when LTX prompts absent (correct C3 state). Now warns when LTX prompts ARE present (contamination detection). GENERATION UNBLOCKED.
- `prep_engine.py`: `character_refs` check now resolves via cast_map (53/53 resolvable — was 0/53 false failure).
- `prep_engine.py`: `nano_prompts_present` downgraded HALT→WARN (runner builds from `_beat_action` at runtime).
- `atlas_universal_runner.py`: LTX_FAST is now `_LTXRetiredGuard()` — raises `RuntimeError("C3: LTX retired.")` on any use. (Was a callable string for 15 consecutive reports.)
- `tools/monitored_run.py`: bare-list guard added at line 112 (was crashing for 38 days).
- `.env`: `MUAPI_KEY` added (was only hardcoded fallback in runner — now properly in .env).
- `CLAUDE.md`: Updated V29.17 → V30.1. All 7 R57 doc inaccuracies corrected.

**V29.17 PHANTOM P0s — THESE WERE ALREADY FIXED IN V30.0 (do not re-chase):**
- Wire A/B/C: ALL WIRED — runner:1720 (Wire A), runner:2819 (Wire B), runner:2614 (Wire C). Code-confirmed, need prod run to prove.
- `ACTIVE_VIDEO_MODEL` defaults `"seedance"` at line 262 (NOT `"kling"` — V29.17 was wrong).
- `route_shot()` is fully LTX-free — all 4 branches → `"seedance"` (confirmed R57).
- `KNOWN_DIALOGUE_SPEAKERS` loads from cast_map at runtime — FIX-ERR-06 applied in V30.0.
- OPENROUTER_API_KEY: active in `.env`, set at runner:73 BEFORE vision_judge import.
- Florence-2 / VLM: OPENROUTER active — 14/53 ledger entries already show real VLM scores (pre-V30.1 data).

**REWARD SIGNAL STATUS (V30.3):**
- I-score: OPENROUTER active (runner:73) + Gemini 2.5-flash active (vision_judge V30.3 via GOOGLE_API_KEY). 14/53 pre-fix ledger entries show real VLM scores. Post-V30.3 run expected to show higher real-VLM frequency and better identity scoring accuracy.
- V-score: 4-state {0, 0.3, 0.5, 0.85} (V30.0 fix). Wire-C triggers on V=0.0 (frozen video regen).
- C-score: binary structural (0.85 if chain file exists, 0.70 otherwise). Not real SSIM continuity — architectural improvement needed post first-run.
- Quality gates: Wire A (identity regen) + Wire B (fail block) + Wire C (frozen regen) all CODE-CONFIRMED wired. Unproven in production — first V30.x run will validate.

**DEAD CODE — BUILT BUT NEVER CALLED (low priority, post first-run):**
- `tools/story_judge.py` — 670 lines, narrative validation, zero imports in production path.
- `tools/vision_analyst.py` — 911 lines, 8D visual scoring, zero imports in production path.
- Wire suggestion for story_judge: add non-blocking import to `generation_gate.py` (see R57 Section 3).

**LEARNING LOG — LIVE CONFIRMED (R57):**
- `check_regression()` returns `[]` — 22 entries, 0 regressions detected (live Python confirmed).
- Learning log path: absolute path fix applied (ERR-03). No false positives in current state.

### V29.16 SESSION LEARNINGS (BINDING — from $48+ of production data, March 20 2026)

**MODEL ROUTING (ABSOLUTE — V31.0):**
- First frames WITH character refs → `fal-ai/nano-banana-pro/edit` (image-to-image, ref is BASE)
- First frames WITHOUT refs → `fal-ai/nano-banana-pro` (text-to-image)
- Video (ALL shots, PRIMARY) → `fal-ai/kling-video/v3/pro/image-to-video` multi-prompt + @Element (V31.0)
- Seedance IS RETIRED — muapi.ai removed. `ACTIVE_VIDEO_MODEL` default = `"kling"`. Do NOT route to Seedance.
- LTX IS RETIRED — zero calls across 12+ production runs. Do NOT route to LTX.
- NEVER use nano-banana-pro (T2I) for character shots. This is the #1 regression that cost $8.40+ and produced 3 different people.

**PROVEN WORKING KLING PAYLOAD (V31.0 — production-confirmed):**
```json
{
  "start_image_url": "<last_frame_of_prev_shot_OR_scene_first_frame>",
  "multi_prompt": [{"prompt": "<150-250 chars, SHOT TYPE. beat. @Element1 [gender speaks]: 'dialogue'. Face locked.", "duration": "10"}],
  "aspect_ratio": "16:9",
  "negative_prompt": "blurry, distorted, deformed, extra limbs, text overlay, watermark, logo, static, frozen",
  "cfg_scale": 0.5,
  "elements": [
    {"frontal_image_url": "<char_ref_url>", "reference_image_urls": ["<char_ref_url>"]},
    {"frontal_image_url": "<char2_ref_url>", "reference_image_urls": ["<char2_ref_url>"]}
  ]
}
```
- `start_url` CHAINS: each group's last frame → next group's start (V31.0 end-frame chain fix)
- `elements` max 2 characters per call
- `duration`: snap to 5 or 10 only (Kling API hard limit)
- 1 beat = 1 Kling call (V29.9 script-conscious timing — do NOT batch multiple beats)

**PROMPT STRATEGY (PROVEN):**
- First frames: FULL identity `[CHARACTER:]` + `[ROOM DNA:]` + char ref + location ref (~900 chars)
- Kling video: LITE action from beat_action + dialogue + mood (~150-250 chars)
- Kling responds better to LESS text. Identity elements handle the face.
- The Kling Prompt Compiler (`tools/kling_prompt_compiler.py`) handles director's format.

**MULTI-BEAT CONSOLIDATION:**
- Story bible beats → 1 shot per beat (not 8-12 fragmented shots)
- Scene 002 (3 beats) = 3 shots × 10s = 30s total
- Scene 001 (4 beats) = 4 shots × 10-12s = 42s total
- Smart duration: dialogue shots = word_count/2.3 + 1.5s, min 10, max 15

**END-FRAME CHAINING:**
- Extract last frame of Video N → use as start_image for Video N+1
- Forces spatial/character continuity across cuts
- Sequential within scene (chain), parallel across scenes

**GENERATION GATE (17 CHECKS — BLOCKING):**
- Runs BEFORE any money is spent
- Checks: char refs exist, location refs exist, solo scene enforcement, model routing,
  prop chain, jump cuts, dialogue integrity, truth fields, forbidden mistakes, etc.
- APPEND-ONLY: every new error becomes a permanent check
- ANY blocking check = generation halts

**COST EVOLUTION (Scene 002):**
- LTX era: $3.60/scene, frozen statues (WASTED)
- Kling sequential: $30/scene, 48 min, good quality
- Multi-shot consolidation: $7.50/scene, 8 min, good quality
- V29 full harmony: $7.50/scene, 8 min, best identity + pacing

**UNIVERSAL RUNNER (`atlas_universal_runner.py`):**
- Works for ANY project, ANY scene
- `python3 atlas_universal_runner.py <project> <scene_id> [scene_id...] --mode lite|full`
- Parallel scenes, parallel first frames within scene
- Sequential videos within scene (for chaining)
- Both modes use FULL identity on nano, differ only in video prompt verbosity

---

## SECTION 0: V36 AUTHORITY HIERARCHY (IMMUTABLE)

### FINAL AUTHORITY STACK
1. CONTROLLER (atlas_universal_runner.py) — ONLY writer of truth + execution
2. QA GATES (prep_engine, pre_video_gate, auto_revision_judge) — ONLY pass/fail, NO mutation
3. HEATMAP (failure_heatmap.py) — ONLY observe + classify, NEVER act

### HARD RULES
- Heatmap CANNOT: modify prompts, trigger regen, change thresholds, override QA
- QA CANNOT: rewrite prompts, fix shots, reinterpret intent
- ONLY Controller CAN: decide to regenerate, apply fixes, update state
- If a rule exists in two places → the SECTION 0 definition wins
- No module outside Controller may write to: shot_plan.json, video_url fields, nano_prompt fields

### SINGLE DEFINITIONS (defined ONCE, here)
- APPROVAL: _approval_status field in shot_plan.json, set ONLY by /api/auto/approve-shot or Controller
- QA PASS: all 5 content fidelity checks + vision gate return true
- GENERATION AUTHORITY: Controller reads truth → builds prompt → calls API → writes result
- REGEN AUTHORITY: human thumbs-down → Controller diagnoses → Controller fixes → Controller regens

### FORBIDDEN SYSTEMS
- Seedance (RETIRED V31.0 — no generation, no routing)
- LTX (RETIRED — field names persist as legacy data only)
- Any autonomous rewriting of prompts by QA or heatmap modules
- Any dynamic threshold mutation by observation layers

---

## SECTION 1: CONSTITUTIONAL LAWS (TIER 1)

These 7 laws are immutable. Breaking any one destroys the system:

**C1: DUAL AUTHORITY SEPARATION**
Orchestrator is EXECUTION AUTHORITY (loads cast_map, resolves refs, makes FAL calls, writes disk).
Film Engine is PROMPT AUTHORITY (compiles nano_prompt/ltx_motion_prompt with proper polarity).
They MUST NOT do each other's job. Orchestrator does NOT write prompts (film_engine does); Film Engine does NOT load files (orchestrator does).
*(from Laws 264-273, V26.1)*

**C2: SCREENPLAY SETS SCENE COUNT**
Scene count is determined by INT./EXT. headers in the screenplay text. NEVER add/split/merge scenes via code.
If scene count is wrong, fix the screenplay, not the parser.
`_canonical_scene_count` is immutable after import and stamped on both shot_plan.json and story_bible.json.
*(from Law 2, Invariant 1, V21.10)*

**C3: MODEL LOCK IS ABSOLUTE**
nano-banana-pro/edit for first frames WITH character refs (image-to-image, identity-locked).
nano-banana-pro for first frames WITHOUT refs (text-to-image, establishing/empty).
**Kling v3/pro multi-prompt** for ALL video generation — PRIMARY model as of V31.0. start_image_url + multi_prompt + elements (character refs) with end-frame chaining between shots.
**Seedance IS RETIRED as of V31.0** — muapi.ai removed. Do NOT route to Seedance. Do NOT set ATLAS_VIDEO_MODEL=seedance.
**LTX IS RETIRED.** Zero calls in 12+ production runs. Do NOT route to LTX. Never add it back.
NEVER use nano-banana-pro (T2I) for character shots — causes identity drift.
NEVER use LTX — retired model, produces frozen statues.
NEVER use Seedance — retired V31.0, replaced by Kling v3/pro.
Every generation path checks model lock before any FAL call.
*(from Laws 23, 211-218, V29.0 model routing, V31.0 Kling primary)*

**C4: DOCTRINE GOVERNS ALL 4 HOOKS**
scene_init hook (prepare), pre_gen hook (validate), post_gen hook (verify), session_close hook (calibrate).
MUST exist in BOTH master-chain AND generate-first-frames endpoints (not one or the other).
If doctrine is missing from ANY path, that path is not production-ready.
*(from Law 227, V25.3)*

**C5: NEVER REBUILD SCENES FROM SCRATCH**
Edit shots IN PLACE by shot_id. If a shot needs changes, modify its fields.
NEVER delete shots and re-expand from story bible unless user explicitly says "rebuild scene from scratch."
Create backup before any destructive operation.
*(from Laws 178-180, V22 incident)*

**C6: NO GENERATION WITHOUT CALIBRATED DOCTRINE**
Doctrine threshold values (bridge score min, Murch score ranges, ASL targets, etc.) are only valid from enforced sessions (doctrine phase exceptions = 0).
If doctrine was non-blocking during a run, thresholds from that run are CALIBRATION_INVALID.
Before tuning thresholds, verify the session that generated the data was enforced.
*(from Law 230, V25.3)*

**C7: ONE PROJECT = ONE TRUTH**
shot_plan.json is the EXECUTION TRUTH. UI reads from `/api/v16/ui/bundle/{project}` ONLY.
No parallel versions (v17 + v22 of the same project).
Cache invalidation after every mutation.
*(from Invariant 10, Laws 1-7)*

**C8: INTELLIGENCE MUST BE SERIALIZED INTO TRUTH**
Claude's reasoning about story, beats, eye-lines, body mechanics, cut motivation, and shot purpose
MUST be compiled into locked machine-readable fields on each shot BEFORE rendering.
Runtime MUST read those fields. Runtime MUST refuse to overwrite locked truth.
If truth fields are missing, the render proceeds with warnings (V28.0) and will BLOCK (V28.1+).
The Truth Layer is the contract between Intelligence and Execution.
Without it, Claude's understanding disappears the second the run begins.
*(from V28.0 — Intelligence Serialization)*

---

## SECTION 2: ORGAN LAWS (TIER 2)

Grouped by module/organ. ~80 laws total.

### FILM ENGINE (Prompt Authority) — Laws T2-FE-1 through T2-FE-16

**T2-FE-1: Negative vocabulary NEVER in positive prompt** (was Law 264)
`compile_for_ltx()` outputs `_negative_prompt` as separate field.
Payload builders use it for `negative_prompt` param in FAL calls.
NEVER concatenate negative words into `nano_prompt` or `ltx_motion_prompt`.
Production evidence: "worst quality, blurry" in positive caused blurry frames.

**T2-FE-2: Camera brands stripped from ALL final prompts** (was Laws 235, 265, 269)
ARRI Alexa, Cooke, RED, Zeiss, Panavision names = prompt noise on LTX-2.3.
`translate_camera_tokens()` runs on FINAL compiled output (not input — brands can enter via context fields).
Film Engine strips camera brands from camera_body, lens_type fields.
Enricher FILM_PROFILES use generic sensor descriptions only.
NEVER inject camera brand names into prompts.

**T2-FE-3: Dialogue markers injected for every dialogue shot** (was Law 267)
Every shot with `dialogue_text` AND `characters[]` gets `"character speaks:"` in `ltx_motion_prompt`.
Without this, LTX-2.3 generates static/frozen faces during speaking scenes.
Production evidence: 5/7 dialogue shots were missing markers in first V26 render.

**T2-FE-4: CPC decontamination integrated** (was Law 268)
`decontaminate_prompt()` called on compiled nano_prompt when `is_prompt_generic()` returns True.
Generic patterns include: "experiences the moment", "present and engaged", "natural movement begins", "subtle expression".
Without this, generic prompts survive to FAL and produce frozen video.

**T2-FE-5: Color science stripped of film stock brands** (was Law 269)
Kodak 2383, Fuji Eterna, Kodak Vision3 removed from prompts.
Pure color/tone descriptors only: "warm halation", "cool shadows", "grainy print look".
Production evidence: "Kodak 2383 print look" caused literal film-damage textures on frames.

**T2-FE-6: Continuity delta field names match compile output** (was Law 266)
Inject via `_continuity_delta` context key into nano_prompt ONLY, not ltx_motion_prompt.
Output field names are `result["nano_prompt"]` and `result["ltx_motion_prompt"]`.
NEVER use `_compiled` suffix fields (they don't exist in compile output).

**T2-FE-7: Emotion fallback uses CPC get_physical_direction()** (was Law 270)
NEVER use "subtle expression of {emotion}, visible in posture and breathing".
CPC `EMOTION_PHYSICAL_MAP` maps emotion×posture to specific body actions (kneeling, gripping, turning away, etc.).

**T2-FE-8: No dialogue on frozen/static frames** (was new V27)
If a frame is static (no character movement), dialogue CANNOT be spoken from that frame.
Dialogue-containing shots must have character performance action.
Motion opener is dialogue-aware: if has_dialogue=True, character PERFORMS speech action from frame 1.

**T2-FE-9: OTS (Over-The-Shoulder) reversal enforces speaker face camera** (was new V27)
In OTS two-shot dialogue, speaker MUST face camera (A angle), listener faces away (B angle).
Shots must alternate: OTS-A (speaker visible) → OTS-B (listener visible).
180° rule enforced: camera stays on one side of dialogue axis.

**T2-FE-10: Dialogue speaker matching exact + whole-word only** (was new V27)
When injecting "character speaks:" marker, character name must match shot.characters[].
Whole-word matching prevents "EVELYN" matching "EVELYN RAVENCROFT".
If dialogue speaker not in characters[], mark shot as dialogue_mismatch and don't generate.

**T2-FE-13: Dialogue prompts MUST include physical descriptions + performance direction** (V27.1)
FAL models don't know character NAMES. "THOMAS BLACKWOOD speaks:" means nothing to the model.
Every dialogue prompt MUST include:
  1. Full appearance description from cast_map for EACH character in the shot
  2. Performance verb (delivers, confronts, protests, whispers — not generic "speaks")
  3. Physical action (jaw clenches, leans forward, grips banister — from CPC EMOTION_PHYSICAL_MAP)
  4. For OTS: explicit A-angle/B-angle direction (who faces camera, who is foreground)
  5. For multi-character: spatial relationship (who is frame-left, who is frame-right)
This is AUTOMATIC behavior in the enrichment pipeline — not a manual step.
Production evidence: V27.0 dialogue shots had name-only markers, producing static faces.

**T2-FE-14: OTS SHOT/REVERSE-SHOT FRAMING — 180° RULE** (V27.1.2)
Adjacent OTS dialogue shots MUST show OPPOSITE sides of the room.
`assign_ots_angle()` in OTSEnforcer determines A-angle vs B-angle:
  - If speaker == characters[0] → A-angle (standard/wide location ref)
  - If speaker == characters[1] → B-angle (reverse_angle location ref)
`resolve_angle_location_ref()` picks the correct location master variant.
Uses `_dp_ref_selection.location_ref.path` to identify the ROOM, then selects
the correct angle variant of THAT SAME ROOM (never jumps to different location).
Production evidence: V27.1 both OTS shots showed identical staircase background.
V27.1.2 fix: 001_005B shows dark wall (A-angle), 001_006B shows staircase (B-angle).
NEVER use the same location ref for adjacent OTS shots in a dialogue pair.

**T2-FE-15: VIDEO PROMPT COMPILED AT ORIGIN — NO STACKED FIX-V16 PROMPTS** (V27.1.2)
`compile_video_prompt()` in OTSEnforcer builds CLEAN ltx_motion_prompt from scratch:
  - Appearance-based descriptions (not character names — FAL doesn't know names)
  - Full dialogue text with timing markers (0-Ns:)
  - Performance direction (mouth movement, jaw motion, emotion-driven physical action)
  - Anti-morphing constraints
  - Maximum 900 characters
This replaces whatever ltx_motion_prompt was stored on the shot, which may be
corrupted from multiple fix-v16 passes stacking dialogue markers.
Production evidence: 17 shots had repeating text in ltx_motion_prompt from stacked
fix-v16 enrichment passes. V27.1.2 runtime compiler detects corruption (any 30-char
substring appearing 3+ times) and replaces with clean compiled prompt.
NEVER send a corrupted/stacked ltx_motion_prompt to FAL.

**T2-FE-16: DIALOGUE DURATION PROTECTION** (V27.1.2)
Minimum video duration = (word_count / 2.3) + 1.5s buffer.
This prevents AI from cutting dialogue mid-sentence.
If a shot's duration is shorter than the minimum needed for its dialogue,
the controller MUST extend duration before video generation.
NEVER allow a video shorter than the dialogue requires.

**T2-FE-17: CINEMATIC SCREEN DIRECTION — 180° RULE IN PROMPTS** (V27.1.4b)
ALL dialogue shots must include explicit FRAME-LEFT / FRAME-RIGHT screen direction.
Without this, FAL defaults to the same composition for every shot.
  **OTS A-angle:** Listener shoulder FRAME-LEFT foreground, speaker FRAME-RIGHT facing camera.
  **OTS B-angle:** Listener shoulder FRAME-RIGHT foreground, speaker FRAME-LEFT facing camera.
  **Two-shot:** Speaker FRAME-LEFT facing right, listener FRAME-RIGHT facing left. Confrontational.
  **Solo close-up:** Character fills frame, eye-line directed toward absent partner's position.
  Eye-line INHERITS from preceding OTS/two-shot: if character was frame-right before, look frame-left now.
The `prepare_dialogue_shot()` method in `tools/ots_enforcer.py` handles ALL dialogue types.
The V26 controller runs it as Phase E2 (Dialogue Cinematography Enforcer) AFTER Film Engine compile.
Production evidence: V27.1.4 without screen direction — both OTS shots had same composition.
V27.1.4b with FRAME-LEFT/RIGHT — proper shot/reverse-shot, characters face each other in two-shot.
NEVER send a dialogue prompt to FAL without explicit screen direction.

**T2-FE-18: EYE-LINE INHERITANCE ACROSS SHOT TYPES** (V27.1.4b)
When a character appears in an OTS pair, then in a solo close-up:
  - The close-up's eye-line direction is INHERITED from the OTS context
  - If character was speaker frame-RIGHT in OTS-A → close-up looks FRAME-LEFT (toward partner)
  - If character was speaker frame-LEFT in OTS-B → close-up looks FRAME-RIGHT
  `prepare_solo_dialogue_closeup()` walks prev_shots to find the last OTS/two-shot context.
  This creates the invisible dialogue tennis match: cut to close-up, character's gaze direction
  matches where the partner was in the previous wider shot.
NEVER have a solo dialogue close-up with eye-line pointing away from the conversation.

**T2-FE-19: SOLO DIALOGUE CLOSE-UP = TIGHT LENS + HEAVY BOKEH** (V27.1.4b)
When a character has a solo dialogue close-up (medium_close, close_up, reaction):
  - Lens: 85mm, f/1.4 (extremely shallow DOF)
  - Framing: face fills frame, sharp focus on eyes and mouth
  - Background: completely out of focus, soft shapes and warm color only
  - The room's BASE location ref provides consistent background COLOR/TONE
  - The TEXT PROMPT handles the tight framing (not the location ref)
Production evidence: V27.1.3 medium_close showed full panoramic room (wrong).
V27.1.4b close-up shows face with blurred foyer behind (correct).
NEVER prompt a solo dialogue close-up as a wide or medium shot.

**T2-FE-20: SCREEN POSITION LOCK — 180° RULE ACROSS ALL SHOT TYPES** (V27.1.4d)
Once the first OTS A-angle establishes which character is on which side of frame,
those positions are LOCKED for the entire dialogue sequence across ALL shot types.
  `establish_screen_positions()` scans scene shots for first OTS A-angle:
  - OTS A-angle: speaker → FRAME-RIGHT, listener → FRAME-LEFT
  - These positions propagate to: two-shots, close-ups, reaction shots, medium shots
  `get_screen_position(char_name)` returns locked position for ANY subsequent shot.
  **Two-shot:** Character positions match OTS spatial geography (Thomas RIGHT, Eleanor LEFT)
  **Close-up:** Eye-line directed TOWARD partner's locked position
  **Implementation:** `establish_screen_positions()` called ONCE per scene BEFORE per-shot loop.
  Uses `_all_shots_unfiltered` (full shot plan, not filtered batch) to find OTS A-angle
  even when only generating a subset of shots.
Production evidence: V27.1.4c Thomas was on LEFT in two-shot despite being RIGHT in OTS.
V27.1.4d position lock keeps Thomas RIGHT in all 4 shots. Eleanor looks frame-right
toward Thomas's staircase side in close-up.
NEVER allow character positions to drift between shots in a dialogue sequence.

**T2-FE-21: 360° SPATIAL BACKGROUND IN CLOSE-UPS** (V27.1.4d)
Close-up backgrounds must reflect the 360° room geography based on character screen position.
  If character is on the LEFT (entrance side of foyer):
    → Behind them: entrance corridor, ornate door frame, dark paneling, shadowy hallway
  If character is on the RIGHT (staircase side of foyer):
    → Behind them: staircase banister, dark wood railing, upper landing shadows
  The background description is position-specific, not generic "blurred interior."
  `prepare_solo_dialogue_closeup()` builds bg_desc from:
    1. Character's locked screen position (left/right)
    2. Room type from location field + _scene_room (foyer/study/library/etc.)
  Location ref still provides the visual reference. Text prompt REINFORCES spatial truth.
Production evidence: V27.1.4c showed generic "dark interior wall" behind Eleanor.
V27.1.4d shows "grand foyer entrance, dark ornate wood paneling, shadowy corridor"
matching what's actually behind the LEFT/entrance side of the foyer.
NEVER use generic background descriptions in close-ups. Be spatially specific.

**T2-FE-22: SPLIT ANTI-MORPHING — FACE LOCK + BODY FREEDOM** (V27.1.5)
Video prompts MUST separate face identity lock from body performance:
  OLD (broken): "Face stable, NO morphing, character consistent" → freezes EVERYTHING
  NEW (correct): "FACE IDENTITY LOCK: facial structure UNCHANGED, NO face morphing, NO identity drift."
                 "BODY PERFORMANCE FREE: natural breathing, weight shifts, hand gestures CONTINUE."
The old pattern told the model to freeze the entire frame. The new pattern locks face identity
while explicitly allowing body movement — breathing, gestures, posture changes, weight shifts.
Applied to: ots_enforcer.py (compile_video_prompt, compile_universal_video_prompt),
orchestrator_server.py (main video prompt builder, reaction shot injection points).
Production evidence: V27.1.4d shots 011C and 012A were completely frozen statues.
NEVER use blanket "NO morphing" on character shots. Always split face-lock from body-free.

**T2-FE-23: SCENE VISUAL DNA — LOCKED ARCHITECTURE ACROSS ALL SHOTS** (V27.1.5) <!-- SUPERSEDED by V36: Camera Position DNA (scene_visual_dna.py + 8-room templates) handles E-shot composition automatically -->
Every shot in a scene gets an identical [ROOM DNA: ...] block appended to nano_prompt.
This forces FAL to generate the SAME room architecture in every shot of the scene.
  `build_scene_dna()` in `tools/scene_visual_dna.py` extracts DNA from story bible location.
  8 room templates: foyer, library, drawing_room, bedroom, kitchen, staircase, exterior, cemetery.
  DNA includes: staircase material/design, wall material, ceiling features, key fixtures.
  DNA is IMMUTABLE across shots — it's the room's physical fingerprint.
  Injected in V26 controller Phase E5 AND orchestrator generate-first-frames (belt-and-suspenders).
Production evidence: V27.1.4d staircase changed material/color/proximity between 4 shots.
V27.1.5 DNA locks "single curved dark mahogany staircase with carved balusters" on all shots.
NEVER allow a shot to describe the room independently. All shots share scene DNA.

**T2-FE-24: APPARENT-SIZE-AT-FOCAL-LENGTH IN PROMPTS** (V27.1.5)
FAL ignores numeric focal length values (85mm, 50mm). The model generates wide-angle composition
regardless of stated lens. Fix: describe the VISUAL EFFECT, not the number.
  Close-up: "face fills 80% of frame, background compressed flat and completely blurred"
  Medium close: "head and shoulders fill frame, background soft with vague shapes only"
  Medium: "waist-up visible, room context visible but secondary"
  Wide: "full room geography visible, deep depth of field, all features sharp"
  `get_focal_length_enforcement()` in `tools/scene_visual_dna.py` returns the description.
  Injected as `[TIGHT FRAMING: ...]` block on nano_prompt alongside room DNA.
Production evidence: V27.1.4d shot 008B was supposed to be medium_close but showed full room.
NEVER rely on numeric focal length in prompts. Describe the visual framing effect.

**T2-FE-25: LIGHTING RIG LOCK PER SCENE** (V27.1.5)
Every shot in a scene gets an identical [LIGHTING RIG: ...] block appended to nano_prompt.
  `build_scene_lighting_rig()` combines template room lighting + story bible atmosphere + time_of_day.
  This prevents lighting from changing between shots in the same scene.
Production evidence: V27.1.4d showed different light color temperatures between adjacent shots.
NEVER allow individual shots to describe lighting independently. Scene lighting is locked.

**T2-FE-26: REACTION SHOTS NEED MICRO-MOVEMENT CHOREOGRAPHY** (V27.1.5)
Reaction shots (no dialogue) MUST have specific physical micro-movement direction:
  OLD: "Subtle facial reaction, face stable, no morphing, identity consistent" → statue
  NEW: "eyes shift slightly, breath draws in, micro-expression of concern, natural breathing
        rhythm visible, slight weight shift. FACE IDENTITY LOCK: features unchanged."
Without specific movement choreography, the model generates a frozen still image.
NEVER create a reaction shot with only identity-lock language. Always add body direction.

**T2-FE-27: IDENTITY INJECTION — CHARACTER DESCRIPTIONS IN EVERY PROMPT** (V27.5)
FAL models generate from TEXT, not from image refs alone. The #1 cause of identity failure
(44% of frames in 16-shot strategic test) was prompts with ZERO character description —
only camera language like "50mm normal lens, HARGROVE ESTATE, desaturated cool tones."
  `inject_identity_into_prompt()` in `tools/prompt_identity_injector.py` runs AFTER Film Engine
  compile, BEFORE FAL call. It injects [CHARACTER: amplified_appearance] blocks from cast_map.
  **Identity Control Hierarchy (proven by 20-shot data):**
    1. Text description in prompt (STRONGEST — FAL generates FROM this)
    2. Character ref image (supports text, doesn't replace it)
    3. Location ref image (environment context)
    4. Scene DNA text (room architecture)
    5. Camera/lens language (WEAKEST)
  **AMPLIFICATION_MAP** makes distinctive features LOUDER:
    "silver hair" → "BRIGHT SILVER-WHITE hair, clearly aged"
    "stocky build" → "STOCKY, THICK-SET build, broad shoulders, intimidating"
    "band t-shirt" → "IRON MAIDEN LOGO t-shirt, vintage, logo clearly visible"
  Injection is NON-BLOCKING: if it fails, original prompt passes through unchanged.
  Wired permanently in orchestrator_server.py generate-first-frames loop (line ~22973).
Production evidence: V27.4 Raymond 2/10 → V27.5 Raymond 8/10 after injection.
NEVER send a character shot to FAL without character appearance text in the prompt.

**T2-FE-28: LOCATION PROPER NAMES STRIPPED FROM ALL PROMPTS** (V27.5)
Location proper names (HARGROVE ESTATE, BLACKWOOD MANOR, RAVENCROFT) rendered as visible
TEXT in 6/16 frames during strategic test. FAL interprets capitalized proper nouns as text
overlay instructions, not scene descriptions.
  `strip_location_names()` replaces proper names with generic descriptors ("the estate").
  Also strips "EST. XXXX" year markers.
  Runs as Step 1 of inject_identity_into_prompt() — before any other processing.
Production evidence: "HARGROVE ESTATE" appeared as literal text on 6 frames. After stripping: 0.
NEVER include location proper names in prompts sent to FAL.

**T2-FE-29: SOCIAL BLOCKING GEOMETRY FOR MULTI-CHARACTER SHOTS** (V27.5)
Multi-character shots (2-3 characters) MUST include spatial blocking instructions.
Without explicit blocking, FAL places all characters in identical poses at frame center.
  `build_social_blocking()` selects from BLOCKING_TEMPLATES based on character count and context:
    2-char: confrontational, dominant_submissive, side_by_side
    3-char: triangle, confrontation, alliance
  Blocking style inferred from: dialogue tone (refuse/demand → confrontational),
  shot type (OTS → dominant_submissive), default (first template).
  Injected as [BLOCKING: ...] block after identity blocks.
Production evidence: 012_132B 3-char shot improved from 5→7 with triangle blocking.
NEVER send a multi-character shot without explicit spatial blocking instructions.

**T2-FE-30: EMPTY SHOTS GET NEGATIVE CHARACTER CONSTRAINT** (V27.5)
Shots with characters=[] (establishing, B-roll, inserts) MUST include
"No people visible, no figures, empty space only" in the prompt.
Without this, FAL often generates random human figures in empty rooms.
Injection runs in inject_identity_into_prompt() Step 5 when characters list is empty.
NEVER send an empty-room shot without negative character constraint.

**T2-FE-31: IDENTITY SKIP BUG FIX — ONLY [CHARACTER:] BLOCKS COUNT** (V27.5.1)
`has_amplified_identity` checks ONLY for `[CHARACTER:` block markers in the prompt.
Raw appearance text from enrichment passes is NOT "identity present" — it lacks amplification.
V27.5 had a bug where `appearance[:20]` substring matching caused 52% of character shots
to skip identity injection. V27.5.1 fixes this: injection now fires on 100% of character shots.
NEVER check raw appearance substrings as proof of identity injection.

**T2-FE-32: VISION JUDGE — POST-GEN IDENTITY VERIFICATION (Layer 4)** (V27.5.1) <!-- SUPERSEDED by V36: failure_heatmap.py IDENTITY_DRIFT taxonomy classifies and reports identity failures — Controller acts on verdicts, heatmap observes only -->
After FAL returns a frame, BEFORE saving to shot_plan:
  1. Caption the frame via Florence-2 ($0.001/call)
  2. Extract identity markers from cast_map appearance (hair, build, clothing, skin, age)
  3. Score caption against markers (weighted match)
  4. If identity score < 0.25 → REGEN (mandatory, max 2 attempts)
  5. If identity score < 0.45 → FLAG (operator review)
  6. Verify face count matches expected character count
`judge_frame()` in `tools/vision_judge.py` runs in BOTH orchestrator AND V26 controller.
NON-BLOCKING at pipeline level — if judge crashes, frame passes through.
NEVER skip identity verification for character shots. This catches the 44% failure rate.

**T2-FE-33: MULTI-CANDIDATE SELECTOR (Layer 5)** (V27.5.1)
Hero shots (close_up, MCU, dialogue) generate 3 candidates via num_outputs=3.
Production shots (medium, OTS, two_shot) generate 2 candidates.
B-roll/establishing generate 1 candidate.
`get_candidate_count()` in `tools/multi_candidate_selector.py` determines count per shot type.
`select_best_candidate()` scores all candidates via Vision Judge, picks highest.
Winner promoted to first_frames/. Losers archived to first_frame_variants/.
NEVER generate only 1 candidate for a hero shot. The identity lottery requires multiple entries.

**T2-FE-34: PERPETUAL LEARNING LOG — REGRESSION PREVENTION** (V27.5.1)
`tools/atlas_learning_log.py` maintains an append-only log of 15+ confirmed bug fixes.
Each entry has a `verification_code` that can be eval'd to confirm the fix is still in place.
`LearningLog().check_regression()` runs at session start to verify all fixes present.
If any regression detected → HALT before generation.
NEVER start a generation session without checking the learning log.

**T2-FE-35: SOLO SCENE DIALOGUE — NO OFF-CAMERA PARTNER DIRECTION** (V27.6)
When a scene has ONLY ONE character (determined from story_bible.scenes[].characters OR
by counting unique characters across all shots in the scene), dialogue is SELF-DIRECTED:
reading aloud, muttering, examining, narrating, discovering — NOT conversation.
  `set_scene_context()` in OTSEnforcer detects solo scenes and sets `_is_solo_scene=True`.
  `prepare_solo_dialogue_closeup()` and `prepare_solo_dialogue_medium()` check this flag.
  **SOLO SCENE performance direction:**
    - Reading: "eyes scanning downward, reading aloud softly, lips moving with quiet words"
    - Discovering: "eyes widening with discovery, examining something closely"
    - Thinking: "eyes drifting into middle distance, lost in thought"
    - Default: "speaking quietly to self, absorbed in the moment"
  **MULTI-CHARACTER SCENE:** Keeps existing off-camera partner direction with position lock.
  Solo scenes ALWAYS get clean prompt rewrite (never preserve baked prompts with old
  off-camera text). [CHARACTER:] and [ROOM DNA:] blocks are extracted and re-appended.
Production evidence: V27.5.1 002_017B (Nadia alone in library reading book titles)
generated with "speaking to someone off-camera left" → phantom person shoulder in frame.
V27.6 same shot: "eyes scanning downward, reading aloud softly" → Nadia alone, no phantom.
NEVER add off-camera partner direction to a solo scene dialogue shot.

**T2-FE-36: CINEMATIC BOKEH — CLOSE-UP BACKGROUND IS COLOR ONLY** (V27.6)
At 85mm f/1.4 with face filling frame, background is PURE BOKEH — no architectural
detail visible. Real optics: subject at 3-4 feet, background beyond 8 feet is
unresolvable warm/cool color blobs. The old prompts described room architecture
("dark bookshelves", "staircase banister") at close-up focal length, which made FAL
try to show BOTH the face AND the room, producing a compositionally impossible frame
that looked like 35mm instead of 85mm.
  **NEW (V27.6):** Close-up bg_bokeh is COLOR AND LIGHT only:
    Library: "warm amber bokeh from lamplight, dark rich tones, soft golden highlights"
    Foyer: "warm amber and shadow bokeh, soft golden lamp highlights, dark rich wood tones"
    Exterior: "cool natural daylight bokeh, soft green and grey tones"
  NO shapes, NO architecture, NO objects described. Just color temperature and light.
  Medium shots (50mm f/2.0) still describe room atmosphere — the DOF is deep enough.
Production evidence: V27.5.1 close-ups showed full room geography despite "85mm f/1.4" in
prompt. V27.6 shows pure creamy bokeh behind Nadia's face — correct for the focal length.
NEVER describe architectural detail in a close-up background. Use color/light only.

**T2-FE-11: Multi-candidate generation enforces frame parity** (was new V27)
When generating 3 angle variants (wide, medium, close), ALL variants lock: wardrobe, makeup, props, lighting, color grade, background.
ONLY camera angle/lens changes between variants.
Parity check: if variant differs in more than angle/lens, reject and regenerate.

**T2-FE-12: Film Engine compiles for BOTH Kling and LTX** (was new V27)
Compile output differs: nano_prompt for Kling (simpler), ltx_motion_prompt for LTX-2 (performance markers).
Both paths strip brands, inject dialogue, integrate CPC.
Model routing selected at render time via UI dropdown.

### TRUTH LAYER (Intelligence Serialization) — Laws T2-TL-1 through T2-TL-10

**T2-TL-1: THREE-LAYER ARCHITECTURE** (V28.0)
ATLAS has three layers: Intelligence (Claude reasoning), Truth (locked directives), Execution (render).
Intelligence Layer interprets story meaning, beat intent, character behavior, eye-lines, body mechanics.
Truth Layer converts reasoning into structured fields on each shot, locked with integrity hashes.
Execution Layer reads truth fields, compiles prompts, calls FAL, scores results.
Intelligence does NOT render. Execution does NOT invent story meaning.
NEVER skip the Truth Layer — it's the contract between understanding and action.

**T2-TL-2: SCENE CONTRACT REQUIRED BEFORE RENDER** (V28.0)
Every scene MUST have a `scene_contracts/{scene_id}_contract.json` before rendering.
Contains: scene_objective, location_truth, present_characters, emotional_arc, beat_breakdown,
required_coverage, forbidden_mistakes, visual_dna, continuity_anchors, is_solo_scene.
Generated by `compile_scene_truth()` in `tools/shot_truth_contract.py`.
The Truth Gate (Phase E0 in V26 controller) checks for this file.
NEVER render a scene without an authored scene contract.

**T2-TL-3: SHOT TRUTH CONTRACT — REQUIRED FIELDS** (V28.0)
Every shot MUST have these truth fields before FAL sees it:
  `_beat_ref`: which story beat this shot serves
  `_eye_line_target`: where the character is looking (derived from beat action)
  `_body_direction`: what the body is doing (derived from beat action)
  `_cut_motivation`: WHY the camera cuts here (scene open, new beat, object, emotion, movement)
Missing any required field → WARNING in V28.0, BLOCKING in V28.1+.
NEVER send a shot to FAL without knowing WHY it exists and WHAT the character is doing.

**T2-TL-4: TRUTH FIELDS ARE IMMUTABLE ONCE LOCKED** (V28.0)
Fields prefixed with `_beat_`, `_truth_`, `_eye_line_`, `_body_`, `_cut_` are OWNED by the truth system.
Once `_truth_locked=True`:
  - Sanitizer cannot delete them
  - Enricher cannot overwrite them
  - Compiler can only translate them (not modify)
  - Rehydration MUST carry them forward
  `_truth_hash` stores SHA256 of truth fields. `verify_shot_truth_integrity()` detects tampering.
NEVER strip truth fields from a shot. If they need to change, re-author through the truth compiler.

**T2-TL-5: TRUTH → PROMPT TRANSLATION IS MANDATORY** (V28.0)
Truth fields on the shot plan are machine-readable. FAL needs natural language.
`translate_truth_to_prompt()` in `tools/truth_prompt_translator.py` injects a `[PERFORMANCE:]` block:
  `_eye_line_target` → "eyes: [natural language eye direction]"
  `_body_direction` → "body: [natural language body action]"
  `_movement_state` → "motion: [walking/static/transitioning]"
  `_prop_focus` → "props: [object descriptions]"
  `_emotional_state` → "mood: [atmosphere description]"
Runs as Phase E6 in V26 controller AND in orchestrator generate-first-frames (belt-and-suspenders).
NEVER send a prompt to FAL without first translating truth fields into performance direction.

**T2-TL-6: TRUTH GATE VALIDATES BEFORE RENDER** (V28.0)
`TruthGate` in `tools/shot_truth_contract.py` runs as Phase E0 in the V26 controller.
Checks: scene contract exists, every shot has required truth fields, integrity hashes intact.
V28.0: NON-BLOCKING (logs warnings, proceeds). V28.1: BLOCKING (refuses render without truth).
NEVER disable the truth gate. It's the enforcement mechanism for intelligence serialization.

**T2-TL-7: BEAT ENRICHMENT RUNS ONCE, PERSISTS FOREVER** (V28.0)
`tools/beat_enrichment.py` reads story bible beats and writes permanent fields onto shots:
  `_beat_ref`, `_beat_index`, `_beat_action`, `_beat_dialogue`, `_beat_atmosphere`,
  `_eye_line_target`, `_body_direction`, `_cut_motivation`, `_beat_enriched` (lock flag).
Runs ONCE after story bible generation. Fields persist across all subsequent pipeline steps.
NEVER re-run beat enrichment unless story bible changed. Check `_beat_enriched=True` first.

**T2-TL-8: TRUTH COMPILATION ADDS, NEVER OVERWRITES** (V28.0)
`compile_shot_truth()` adds supplementary fields: `_movement_state`, `_emotional_state`,
`_story_purpose`, `_prop_focus`, `_blocking_direction`, `_frame_reason`.
If beat enrichment already set a field, compilation PRESERVES it.
NEVER overwrite a field that beat enrichment authored — it has richer data from the story bible.

**T2-TL-9: FORBIDDEN MISTAKES ARE SCENE-LEVEL DOCTRINE** (V28.0)
Each scene contract contains `forbidden_mistakes` — things that MUST NOT happen:
  Solo scene: "NO off-camera partner direction"
  Library scene: "NO room teleportation — stay in library"
  1-character scene: "NO phantom characters"
  All scenes: "NO camera-aware eye-lines", "NO unmotivated cuts"
These are generated from scene analysis and enforced by the Truth Gate.
NEVER ignore forbidden_mistakes when debugging a failed render.

**T2-TL-10: RUNTIME TRACEABILITY — EVERY FRAME TRACES TO TRUTH** (V28.0)
After generation, every frame is traceable to:
  `_scene_contract_version` → which scene contract version was active
  `_truth_hash` → which truth state the shot had at render time
  `_truth_version` → truth compiler version
  `verify_prompt_reflects_truth()` → confirms prompt carried intelligence to FAL
If a frame looks wrong, check the truth hash first. If truth was intact, the problem is FAL.
If truth was tampered, the problem is a downstream system stripping intelligence.

### CHAIN POLICY (Render Strategy) — Laws T2-CP-1 through T2-CP-9

**T2-CP-1: Coverage suffixes are EDITORIAL, not runtime** (was Law 256)
A/B/C/D suffixes describe camera coverage roles, NOT chain membership, B-roll status, ref eligibility, or render strategy.
Use explicit shot flags: `shot.get("is_broll")`, `shot.get("should_chain")`, `shot.get("chain_source")`.
NEVER infer render behavior from shot_id.endswith("B").
Production evidence: Coverage classifier broke chains on 4 scenes.

**T2-CP-2: Chain is dual-purpose: generation source + verification** (was new V27)
Primary purpose: end-frame chaining (extract last frame of video N → use as first frame of video N+1).
Secondary purpose: continuity verification (ensure spatial state carries across shots).
Use same chain architecture for both purposes. Don't split implementation.

**T2-CP-3: Chain confidence levels: strong/medium/weak/break** (was new V27)
Strong: same location, same character, same emotional beat.
Medium: same location, different character (reaction cut).
Weak: location drift detected or emotion jump.
Break: blocking change requires connector shot.
Use confidence to warn operator before generation, not to auto-fix.

**T2-CP-4: B-roll NEVER chains to character shots** (was Law 201)
B-roll (shot_id ending in B, marked _broll=true) is independent visual context.
Cannot use end-frame chaining when target shot has characters.
B-roll to B-roll chaining is allowed for montage continuity.

**T2-CP-5: should_chain() checks explicit flags first** (was Law 261)
Check: _intercut flag (cross-location shots), _broll flag, _no_chain flag.
Then check: location consistency, character continuity, dialogue indicators.
NEVER infer from shot_id string patterns.

**T2-CP-6: B-roll continuity system handles texture/color/atmosphere** (was Law 202)
B-roll chaining (B→B only) uses scene texture/color/atmosphere matching.
DINOv2 embeddings compare end-frame environment to target environment.
No character refs involved — B-roll is context, not identity.

**T2-CP-7: Parallel render: chains sequential, B-roll independent** (was Law 203) <!-- SUPERSEDED by V36: parallel/chain gen_mode in atlas_universal_runner.py (--frames-only / --videos-only) handles this natively -->
Within a scene: character chains (A→B→C) render sequentially.
Across scenes: independent B-roll and inserts render in parallel.
Dependency graph groups shots by chain membership.
10x speedup: sequential chain 83min → parallel scenes 8min.

**T2-CP-8: Render classification is explicit, not inferred** (was Law 2364, V26 Doctrine 4)
Each shot receives explicit classification: anchor, chain, end_frame_reframe, independent_parallel, bootstrap_establishing.
If no classification exists, shot is NOT render-ready.
Classifications come from strategy authority (fix-v16 coverage solver or explicit user markup).

**T2-CP-9: OTS DIALOGUE PAIRS ALTERNATE CAMERA ANGLE** (V27.1.2)
When two OTS shots form a dialogue pair (same scene, same characters, different speakers):
  - They MUST have opposite `_ots_angle` values (A vs B)
  - They MUST use different location refs (standard vs reverse_angle)
  - Camera stays on ONE SIDE of the dialogue axis (180° rule)
This is the fundamental rule of shot/reverse-shot coverage in cinema.
`assign_ots_angle()` enforces this automatically based on speaker position in characters[].
NEVER render adjacent OTS dialogue shots with the same camera angle.

#### V26 DOCTRINE BLOCKS (Classifier Integrity — from March 13 incident)

These 6 blocks are the root-cause analysis from a $45 production failure where 4 classifiers made contradictory assumptions. They are BINDING on all render-path code:

**DOCTRINE 1: COVERAGE LABELS ARE NOT RENDER BEHAVIOR**
Coverage suffixes (A, B, C, D) are editorial labels. They NEVER determine: chain membership, B-roll status, reference eligibility, composition reuse, or canonical render strategy — unless an explicit render strategy authority maps them.

**DOCTRINE 2: CANONICAL REFERENCE RESOLUTION**
All character-driven shots must resolve identity through project-canonical `*_CHAR_REFERENCE.jpg` assets. Generic actor headshots are rejected when identity continuity is required. If required references fail resolution, the shot must be marked `degraded_safe` or `blocked` — never silently proceed as generic generation.

**DOCTRINE 3: DRAMATIC EQUIVALENCE BEFORE REUSE**
Frame reuse is only valid when two shots are dramatically equivalent across: subject set, camera class, action intent, dialogue intent, emotional beat, prompt content, continuity role. Scene ID + character overlap alone is insufficient.

**DOCTRINE 4: EXPLICIT CHAIN MEMBERSHIP**
No shot may be treated as chained, independent, bootstrap, or end-frame reframe by implication alone. Each shot must receive explicit render classification from strategy authority.

**DOCTRINE 5: CANONICAL RUN SUPERSEDES HISTORY**
Once a scene is re-prepared under corrected logic, all previous first frames become historical artifacts unless explicitly re-approved. Historical artifacts may be archived for audit but must NOT remain visible as current truth.

**DOCTRINE 6: REUSE MUST BE EXPLAINABLE**
Every reused frame must emit a structured explanation containing: source shot, target shot, equivalence basis, reuse confidence, operator visibility flag. If reuse cannot be explained, it must not happen.

### SHOT AUTHORITY (FAL Parameters) — Laws T2-SA-1 through T2-SA-6

**T2-SA-1: FAL nano-banana-pro actual API params** (was Laws 211-213)
Correct: prompt, image_urls, aspect_ratio, resolution (1K/2K/4K), output_format, safety_tolerance, seed, num_images.
FORBIDDEN (silently ignored by API): guidance_scale, num_inference_steps, image_size.
NEVER send forbidden params — they do nothing and confuse code readers.

**T2-SA-2: Resolution is primary quality lever** (was Law 212)
Hero shots (close-ups, ECU, MCU): 2K resolution.
Production shots (medium, OTS, two-shot): 1K resolution.
Establishing/B-roll: 1K resolution.
NEVER use image_size dict or fake resolution values.

**T2-SA-3: Ref cap per shot type** (was Law 216)
Hero: 3 character refs maximum.
Production: 4 refs (characters + location).
Establishing/B-roll: 2 refs.
NEVER send more refs than profile allows.

**T2-SA-4: Dialogue boost: +1 ref slot + 2K minimum** (was Law 217)
Speaking faces need maximum fidelity.
If dialogue_text is non-empty: force 2K resolution, add +1 to ref cap, prioritize character refs.
NEVER skip dialogue boost.

**T2-SA-5: Smart Regen escalates resolution** (was Laws 214-215)
First regen attempt: bump resolution +1 tier (1K → 2K, 2K → 4K).
Escalation on second attempt: always 2K.
NEVER regen at same or lower resolution.

**T2-SA-6: R2 permanent URLs for chained reframes** (was Law 229, V25.3)
Atlas bucket (026089839555deec85ae1cfc77648038) is truth store.
Upload master frame to R2 ONCE, use permanent URL for ALL angle variants.
NEVER generate 36 reframe calls from single FAL temp URL (expires in ~2 hours).

### DOCTRINE ENGINE (Governance) — Laws T2-DE-1 through T2-DE-8

**T2-DE-1: GateResult is DATACLASS not Enum** (was Law 219)
Supports both: `GateResult.PASS` and `GateResult(value="PASS", reason="...natural language")`.
NEVER revert to Enum inheritance (breaks keyword constructor calls in all 7 phases).
Dataclass enables rich verdict objects with evidence.

**T2-DE-2: EXECUTIVE_LAW_02 is WARN not REJECT** (was Law 220)
Scene plan fields (shot_classes, model_tiers, peak_shots) are V28 concepts not yet populated.
NEVER hard-block generation on missing doctrine scene plan until Phase 3 fully wired.
Current behavior: WARN if missing, proceed with default profile.

**T2-DE-3: Phase exceptions are NON-BLOCKING** (was Law 221)
If any doctrine phase throws internal exception (e.g., vision service down), log to ledger, allow generation.
NEVER let doctrine bugs halt the pipeline they govern.
Fallback: proceed with degraded capability (e.g., vision scores default to None).

**T2-DE-4: Doctrine hooks must exist in ALL generation endpoints** (was Law 227)
scene_init (prepare), pre_gen (validate), post_gen (verify), session_close (calibrate).
MUST be in BOTH master-chain AND generate-first-frames (not one or other).
If editorial hooks added later: same rule applies (both or neither).

**T2-DE-5: Calibration data only valid from enforced sessions** (was Law 230)
Doctrine threshold tuning requires doctrine phase exceptions = 0.
If phase_exceptions > 0 or doctrine bypassed: mark session CALIBRATION_INVALID.
Editorial Murch thresholds: same principle (non-blocking sessions = informational, not authoritative).

**T2-DE-6: Dialogue shots MUST have ≥1 character** (was Law 223)
If dialogue_text non-empty AND characters=[], shot WILL fail identity scoring.
fix-v16 CHECK 7E verifies: `len(shot.get("characters", [])) > 0` if dialogue_text exists.
NEVER ship dialogue shot without character assignment.

**T2-DE-7: Dialogue duration covers word count** (was Law 224)
Minimum duration = (word_count / 2.3) + 1.5s buffer.
fix-v16 Step 7B runs AFTER all modifiers to enforce this.
NEVER let runtime contract assign duration shorter than speak time (cuts dialogue mid-sentence).

**T2-DE-8: ABC coverage distribution per scene** (was Law 225)
Every scene with >1 shot MUST have ≥1 A_GEOGRAPHY master (wide/establishing).
If missing: fix-v16 promotes first wide/establishing shot.
NEVER stitch scene where all shots share same coverage role (all B = no anchor).

### CONTINUITY MEMORY (Spatial State) — Laws T2-CM-1 through T2-CM-8

**T2-CM-1: Continuity Memory is SUPPLEMENTARY** (was Law 196)
If continuity module fails, Film Engine compiles without it.
NEVER make continuity a blocking gate.
Fallback: generic spatial direction in prompts.

**T2-CM-2: Field access uses `.get()` with `or` pattern** (was Laws 197-198)
`shot.get("characters") or []` (not `.get("characters", [])` which fails on explicit None).
All nullable fields in spatial extraction use `or` pattern.
NEVER trust default parameters on None fields.

**T2-CM-3: 5 reframe strategies with weighted scoring** (was from V24.1)
continuity_match (default, preserve blocking).
emotional_push (escalate emotion, tighten framing).
action_widen (physical motion, widen geography).
reaction_cut (dialogue partner focus, reverse angle).
reveal_ots (OTS framing, show different angle).
All 5 kept; Basal Ganglia scores and recommends (advisory).

**T2-CM-4: Vision integration is OPTIONAL** (was Law 204)
`vision_analyze_end_frame()` only runs when frame exists AND vision service available.
Metadata-based spatial extraction is fallback (heuristic from shot description + beat).
NEVER require vision for continuity to work.

**T2-CM-5: Continuity delta injection via context key** (was Law 205)
Film Engine reads `_continuity_delta` from context dict.
Appends delta to nano_prompt (chained shots only).
NEVER inject continuity by modifying shot_plan.json fields directly.

**T2-CM-6: ContinuityMemory auto-loads on init** (was Law 207)
`__init__` calls `_load()` during instantiation.
NEVER require explicit load() call.

**T2-CM-7: ContinuityMemory persists with _save()** (was Law 208)
Auto-saves after `store_shot_state()`.
NEVER leave states in memory without persistence.

**T2-CM-8: B-roll never chains to character shots** (was Laws 201-202)
B-roll (is_broll=true) is independent visual context.
CAN chain B-roll to B-roll for montage continuity.
Scene texture/color/atmosphere matching used for B-roll chains, not character spatial state.

### ORCHESTRATOR (Execution Authority) — Laws T2-OR-1 through T2-OR-16

**T2-OR-1: UI reads ONLY from /api/v16/ui/bundle/{project}** (was Law 1)
Single source of truth for UI state.
Bundle invalidated after every mutation.
NEVER read directly from shot_plan.json in UI.

**T2-OR-2: All media via /api/media?path=...** (was Law 2)
Images/videos served through orchestrator endpoint (normalizes paths, security).
NEVER serve files directly from filesystem.

**T2-OR-3: Cache invalidation after every mutation** (was Law 3)
After shot edit, duration change, wardrobe update: clear bundle cache.
NEVER allow stale cache to persist.

**T2-OR-4: Model lock enforced on all render operations** (was Law 4)
Every FAL call checks: if model not in ALLOWED_MODELS, abort.
ALLOWED_MODELS = [fal-ai/nano-banana-pro, fal-ai/nano-banana-pro/edit, fal-ai/kling-video/v3/pro/image-to-video].
LTX IS RETIRED — fal-ai/ltx-2/image-to-video/fast is NO LONGER in ALLOWED_MODELS (V29.3).
Seedance IS RETIRED — muapi.ai removed from ALLOWED_MODELS (V31.0). Do NOT re-add.
NEVER make unapproved model calls.

**T2-OR-5: Agent enforcement is BLOCKING** (was Law 8)
EnforcementAgent pre-gen violations cause exception.
Pipeline stops until violations resolved.
Exception handler returns error (not warning).

**T2-OR-6: Wardrobe/extras injection is NON-BLOCKING** (was Law 76)
If wardrobe agent fails, generation proceeds.
NEVER make wardrobe a hard gate.
Log failures to operator.

**T2-OR-7: LOA is POLICY layer, Vision Service is PERCEPTION** (was Law 50)
LOA makes decisions (required/optional/forbidden).
Vision Service provides data (identity score, location score, presence).
NEVER merge policy logic into perception layer or vice versa.

**T2-OR-8: Cast map loads from separate cast_map.json** (was Law 258)
NOT embedded inside shot_plan.json.
prep_engine.py has fallback if missing.
NEVER assume cast_map embedded in plan.

**T2-OR-9: Character refs must be project-local *_CHAR_REFERENCE.jpg** (was Law 257)
LOCKED_REFERENCE and ai_actors paths are rejected.
All character identity driven by character_reference_url from cast_map.
NEVER use AI actor headshot paths directly.

**T2-OR-10: Generate-first-frames includes wardrobe/extras + LOA pre-gen** (was Laws 1023-1048, V17.6-V17.7.5)
Step 0: Agent enforcement gate.
Step 1: Wardrobe/extras injection.
Step 2: LOA pre-generation check.
Step 3: Film Engine compile + FAL calls.
Step 4: LOA post-gen QA.
All 5 steps sequential, non-blocking failures logged.

**T2-OR-11: Location masters generated during first-frame generation** (was Law 489)
Scene's establishing shot generates location_masters/{scene_id}_master.jpg.
Subsequent shots use this master for environment consistency.
NEVER skip location master generation.

**T2-OR-12: Duration math + dialogue protection in fix-v16 Step 7B** (was Law 223-224, Step 7B)
AFTER all enrichment steps: check dialogue duration.
If word_count exists: enforce min_duration = (word_count / 2.3) + 1.5s.
NEVER allow downstream steps to reduce duration below calculated minimum.

**T2-OR-13: CHARACTERS DON'T TELEPORT — ROOM-LOCKED LOCATION RESOLUTION** (V27.1.4)
The DP (Director of Photography) location resolver MUST lock to the scene's ESTABLISHED ROOM
before selecting any angle variant. This is a cinematographic fundamental:
  **WHY:** In film, when characters are talking in a foyer, EVERY shot shows that foyer.
  A close-up of a character still shows the foyer wall behind them. A two-shot still
  shows the foyer's furniture. The camera moves within the room — it doesn't jump to
  a different room because the shot type changed. If the screenplay says "GRAND FOYER",
  then establishing, OTS, two-shot, medium close, reaction, and closing shots ALL show
  the Grand Foyer from different angles.
  **THE ERROR THIS PREVENTS:** Shot type → angle preference → best-scoring location master
  across ALL rooms. This caused a two_shot wanting "medium_interior" to match a LIBRARY
  when the scene is in the FOYER, because the library's medium_interior scored highest.
  The system selected a room based on angle name, not based on WHERE THE CHARACTERS ARE.
  **THE FIX (at origin):**
  STEP 1: Resolve the scene's ROOM from story_bible.scenes[].location (specific room name).
  STEP 2: Filter location_masters to ONLY that room's angle variants.
  STEP 3: Pick the angle variant within that room based on shot type.
  If the room has no matching angle variant, use the room's base master — never jump rooms.
  **Implementation:** `_scene_room` resolved from story_bible, `_room_suffix` extracted,
  `_room_masters` filtered by room suffix matching on file stems.
Production evidence: V27.1.3 two_shot matched library instead of foyer. V27.1.4 fix locks
to foyer first, then selects foyer's medium_interior variant.
NEVER resolve location refs by scoring across all rooms. Always filter to scene room first.

**T2-OR-14: FACE-CENTRIC SHOTS KEEP THE ROOM — PROMPT HANDLES TIGHTNESS** (V27.1.4)
Close-ups, medium close-ups, and reaction shots MUST still receive the scene's location ref.
  **WHY:** A close-up of Eleanor in the foyer still shows the foyer WALL behind her.
  Removing the location ref entirely makes the model place her in a void or hallucinate
  a random background, breaking spatial continuity with adjacent shots. The character
  doesn't leave the room just because the camera moved closer to her face.
  **THE ERROR THIS PREVENTS:** DP map had medium_close/close_up/reaction → None (skip
  location ref). This caused 008B to show Eleanor in a full panoramic void, revealing
  she's alone in a wide empty space — not consistent with the intimate dialogue framing
  of the shots before and after.
  **THE FIX (at origin):** Face-centric shots get the room's BASE master as their location
  ref. The text prompt handles tight framing ("50mm, shallow depth of field, eye-level").
  The location ref provides CONSISTENT BACKGROUND — the room stays the same room.
  Angle preference for face-centric shots: "base" (not None).
Production evidence: V27.1.3 008B had no location ref → showed empty panoramic foyer.
V27.1.4 008B gets foyer base master → background consistent with conversation sequence.
NEVER skip the location ref for face-centric shots. The room doesn't disappear.

**T2-OR-15: SPATIAL PACING — ROOM CHANGES REQUIRE CHARACTER MOVEMENT** (V27.1.4)
A location ref can only change to a DIFFERENT ROOM if the screenplay BLOCKS the character
moving there (walks to, enters, follows into, crosses to).
  **WHY:** In film, the audience tracks spatial geography. If characters are arguing in the
  foyer and the next shot shows a library, the audience is confused — "when did they walk
  there?" Every room change needs a TRANSITION: an action line, an establishing shot of the
  new room, or a character physically walking through a doorway.
  **THE RULE:** Within a scene, if the story_bible beats don't describe movement to a new
  room, ALL shots use the SAME room's location masters. The DP varies ANGLES within that
  room (wide, medium, reverse, OTS A/B) but never jumps rooms.
  **EXCEPTION:** INTERCUT scenes explicitly alternate between two locations — this is the
  ONLY case where adjacent shots can show different rooms without a transition.
NEVER change the location ref room between shots unless the screenplay explicitly describes
the character moving to a new space.

**T2-OR-16: ANGLE VARIETY WITHIN A ROOM — THE DP HIERARCHY** (V27.1.4)
Within a single room, the DP selects angles in this priority order:
  establishing/wide/closing → base master (full room geography)
  medium/two_shot → medium_interior variant (characters in room context, tighter)
  medium_close/close_up/reaction → base master (background consistency, prompt handles face tightness)
  OTS → A/B angle alternation (base for speaker's side, reverse for listener's side)
  b-roll → base master (room atmosphere)
  insert/detail → medium_interior variant (context without full geography)
If the preferred angle variant doesn't exist for this room, fall back to the base master.
NEVER fall back to a different room's variant. Same room, different angle. That's cinematography.

**T2-OR-17: SPATIAL TIMECODE OVERRIDES SHOT-TYPE ANGLE MAP** (V27.1.4)
The spatial timecode system (`tools/spatial_timecode.py`) tracks WHERE characters are within
a room across a scene's shot sequence. It reads story_bible beats for zone keywords:
  "entrance" (enters, doorway), "staircase" (banister, railing), "fireplace" (mantle, hearth),
  "center" (presents, demands, confronts), "window" (light, outside).
Each zone maps to a preferred camera angle: entrance→reverse_angle, staircase→base,
fireplace→medium_interior, center→base, window→reverse_angle.
  **THE OVERRIDE:** The timecode's zone-aware `angle_pref` REPLACES the simple `_DP_ANGLE_MAP`
  shot-type→angle lookup. If the timecode says "center zone = base angle" but the shot type
  would default to "medium_interior", the timecode WINS.
  **EXCEPTION:** OTS shots keep their A/B angle logic — timecode informs zone context only.
  **WHY:** Without this, a two_shot (medium_interior default) could match a different room's
  angle variant. With timecode override, center zone → base angle → stays in scene's room.
Production evidence: V27.1.4 timecode overrode 007B from medium_interior to base, preventing
library jump. All 4 test shots (005B-008B) maintained Grand Foyer spatial continuity.

**T2-OR-18: SHOT_PLAN.JSON BARE-LIST FORMAT — ALL CONSUMERS MUST GUARD** (V27.1.4)
shot_plan.json may be a bare JSON list `[{shot1}, {shot2}, ...]` rather than `{"shots": [...]}`.
ALL code that loads shot_plan.json MUST handle both formats:
  `if isinstance(sp, list): sp = {"shots": sp}`
Files that required this fix: atlas_v26_controller.py, test_creative_prompt_compiler.py,
test_editorial_intelligence.py, test_film_engine.py, meta_director.py, vision_analyst.py.
NEVER assume shot_plan.json is a dict. Always guard with isinstance check.

**T2-OR-19: STORY BIBLE BEATS DRIVE TIMECODE — DATA ALREADY EXISTS** (V27.1.4)
The story bible's `scenes[].beats[]` field contains the beat descriptions that the spatial
timecode system parses for zone keywords. This data is generated during `generate-story-bible`
and requires NO additional manual input.
  - `build_scene_timecode()` is called ONCE per scene BEFORE the shot generation loop
  - Results are cached in `_spatial_timecode[shot_id]` dict for O(1) lookup per shot
  - Timecode computation is NON-BLOCKING: if it fails, the DP falls back to `_DP_ANGLE_MAP`
  - The timecode is AUTOMATIC for all scripts — it reads whatever beats the story bible has

### MOVIE LOCK / CONTRACTS (Verification) — Laws T2-ML-1 through T2-ML-6

**T2-ML-1: 10 contracts enforced pre-generation** (was Law 145)
B_SINGLE_ENRICHMENT, C_BIO_BLEED, D_LOCATION_BLEED, E_SCENE_ALIGNMENT, F_LANDSCAPE_SAFETY, G_CONCAT_INTEGRITY, H_DIALOGUE_MARKER, I_PERFORMANCE_MARKER, J_INTERCUT_INTEGRITY, PROMPT_HEALTH.
Endpoint: `POST /api/v21/audit/{project}` runs all 10.
NEVER skip audit before generation.

**T2-ML-2: Gate snapshots use SHA256 immutable payloads** (was Law 148)
`POST /api/v21/gate-snapshot/{project}` creates immutable pre-FAL snapshots.
`POST /api/v21/gate-snapshot/verify/{project}` verifies prompt hash before FAL.
NEVER skip verification if snapshot exists.

**T2-ML-3: Mutation log is APPEND-ONLY** (was Law 149)
`reports/mutation_log.jsonl` tracks every field mutation.
`GET /api/v21/regressions/{project}` detects A→B→A patterns.
NEVER truncate or overwrite log.

**T2-ML-4: CHECK 7A-7F run automatically in fix-v16** (was Laws 146-147)
7A: Character name normalization (EVELYN → EVELYN RAVENCROFT).
7B: Dialogue duration protection.
7C: Intercut scene separation.
7D: Scene alignment verification.
7E: Character population + landscape safety.
7F: Prompt Authority Gate (FINAL step after all V20.5 enrichment).
All automatic, zero manual steps.

**T2-ML-5: CHILD V.O. tagged and stripped** (was Law 150)
Voice-only characters marked `_child_vo=true`.
Excluded from face-lock, not shown on screen.
NEVER put CHILD in character refs or dialogue markers.

**T2-ML-6: Intercut shots ONE visible character per phone call** (was Law 151)
CHECK 7C assigns primary speaker by location.
NEVER show both phone participants simultaneously.
Second participant: off-screen dialogue or reaction shot.

### SCRIPT IMPORT / PARSER — Laws T2-SI-1 through T2-SI-6

**T2-SI-1: ONE import pipeline** (was Law 275, Invariant 1)
ALL scripts enter through `POST /api/v6/script/full-import`.
No other endpoint creates projects.
Pipeline order: text extraction → scene counting → character normalization → story bible → shot expansion → import validation gate → save.

**T2-SI-2: Normalize BEFORE everything** (was Law 164)
At Phase 1B (import): resolve character aliases.
V6 header aliases (priority 1) → V6 bible aliases (priority 2) → substring detection (fallback).
`_import_name_normalization` map saved to shot_plan metadata.
NEVER build shots with short/unnormalized names.

**T2-SI-3: INTERCUT = ONE scene** (was Laws 172-176, V21.10)
`INT. LOCATION A / LOCATION B` creates one scene with `_intercut=True`.
Bare sub-location names (no INT./EXT.) are sub-locations within same scene.
CHECK 7C maps characters to locations within intercut.
NEVER split slash headers into separate scenes.

**T2-SI-4: Blank line resets current_character** (was Law 166)
Screenplay blank lines ALWAYS end dialogue blocks.
Action lines after blank are STAGE DIRECTIONS, not speech.
`current_character = None` in blank line handler.
NEVER capture post-blank action as dialogue.

**T2-SI-5: _intercut_active persists for character-location mapping** (was Law 168)
Separate from global `is_intercut` which resets for scene creation.
Dialogue-phase mapping uses `_intercut_active` to assign characters to locations.
NEVER rely only on global `is_intercut` for final mapping.

**T2-SI-6: Import validation gate 8 checks** (was Law 169, V21.10)
Scene count match, character normalization, INTERCUT integrity, prompt bounds, no hollow bibles, etc.
NEVER save shot_plan without gate passing.
`_canonical_scene_count` stamped on both shot_plan AND story_bible.

### WARDROBE / EXTRAS — Laws T2-WE-1 through T2-WE-6

**T2-WE-1: Defaults by SCENE not by individual shot** (was Law 73)
Scene 001: all EVELYN shots have same look_id (Scene 001 brown coat).
Cross-scene: new look_id at scene boundaries.
carry_wardrobe_forward() for intentional style changes.
NEVER default wardrobe by shot.

**T2-WE-2: Auto-created on first generation** (was Law 74)
If wardrobe.json doesn't exist: auto_assign_wardrobe() runs.
Uses story_bible character descriptions + cast_map appearance data.
NEVER block generation on missing wardrobe file.

**T2-WE-3: Injection is NON-BLOCKING** (was Law 75)
If wardrobe agent fails, generation proceeds.
Failures logged to operator.
NEVER make wardrobe a hard gate.

**T2-WE-4: Extras are templates, not identities** (was Law 78)
6 default crowd packs (BAR_CROWD_A, VILLAGE_STREET, MANOR_SERVANTS, EMPTY_SETTING, FUNERAL_MOURNERS, OFFICE_WORKERS).
Extras don't get face locks or character refs.
NEVER put extras in cast_map.

**T2-WE-5: EMPTY_SETTING adds negative constraints** (was Law 77)
Scenes with no background people: inject "no background people, no bystanders".
NEVER add crowd to empty scenes.

**T2-WE-6: Wardrobe/extras injection deduped** (was Law 79)
Checks for existing "wardrobe:" / "extras:" marker before injecting.
NEVER double-inject.

### CASTING SAFETY — Laws T2-CS-1 through T2-CS-2

**T2-CS-1: CASTING STOPWORDS PREVENT PHANTOM CHARACTERS** (V27.1.2)
Script parser MUST maintain a stopword list for character detection:
  END, FADE, CUT, DISSOLVE, CONTINUED, CONTINUOUS, MORE, CONT'D,
  THE END, END OF EPISODE, TITLE CARD, SUPER, INTERCUT, V.O., O.S.
If a caps-locked word matches a stopword, it is NOT a character.
Production evidence: "END OF EPISODE" parsed as character "END".
NEVER create character entries from script formatting directives.

**T2-CS-2: CHARACTER ALIAS RESOLUTION IS EXACT-MATCH** (V27.1.2)
When resolving character aliases (e.g., "DETECTIVE REYES" → "DETECTIVE ELENA REYES"):
  - V6 header aliases (priority 1) → exact match
  - V6 bible aliases (priority 2) → exact match
  - Substring detection (fallback) → WHOLE WORD only
NEVER match "REYES" to "DETECTIVE ELENA REYES" by substring if "REYES" could be
a different character. Require whole-word boundary matching.

### CREATIVE PROMPT COMPILER (Immune System) — Laws T2-CPC-1 through T2-CPC-9

**T2-CPC-1: CPC is the IMMUNE SYSTEM** (was Law 236)
`tools/creative_prompt_compiler.py` prevents generic contamination at 5 pipeline points.
NEVER bypass CPC in any enrichment path.

**T2-CPC-2: is_prompt_generic() is the diagnostic** (was Law 237)
Returns True if prompt matches GENERIC_PATTERNS blacklist.
If True: prompt WILL produce frozen/generic video.
NEVER send prompt to FAL that fails this check.

**T2-CPC-3: GENERIC_PATTERNS blacklist is append-only** (was Law 238)
New patterns discovered in production get ADDED.
Existing patterns NEVER removed.
NEVER shrink blacklist.

**T2-CPC-4: EMOTION_PHYSICAL_MAP maps emotion×posture to verbs** (was Law 239)
Returns specific body action (kneeling, gripping, turning away, etc.).
NEVER return "experiences the moment" or "present and engaged".
All 25-40 combinations must return PHYSICAL verbs.

**T2-CPC-5: get_physical_direction() is universal fallback** (was Law 240)
Every pipeline point using generic string ("natural movement begins", etc.) now calls this.
NEVER add fallback without routing through CPC.

**T2-CPC-6: decontaminate_prompt() REPLACES, not strips** (was Law 241)
Stripping generics leaves gaps.
CPC replaces with emotion-driven physical direction.
NEVER strip without injecting replacement.

**T2-CPC-7: Imports are NON-BLOCKING** (was Law 242)
All 5 integration points have `try/except ImportError` fallbacks.
If CPC fails to import: pipeline continues with legacy behavior.
NEVER make CPC hard dependency that crashes pipeline.

**T2-CPC-8: CPC tests (125) must pass before any change** (was Law 244)
Group 9: 280 function calls, zero generic output = integration proof.
NEVER ship CPC change without full test suite.

**T2-CPC-9: CORRUPTED PROMPT DETECTION — REPETITION GUARD** (V27.1.2)
Before sending ANY prompt to FAL, check for text repetition:
  - If any 30-character substring appears 3+ times → prompt is CORRUPTED
  - Replace with fresh compilation from shot metadata
This catches stacked fix-v16 enrichment passes that repeat dialogue markers.
Production evidence: 17/148 shots (11.5%) had corrupted prompts in V27.1.
Append-only pattern: this check runs at generation time, not at enrichment time.
NEVER send a prompt with repeated text to FAL.

### EDITORIAL INTELLIGENCE (Advisory Phase 1) — Laws T2-ED-1 through T2-ED-10

**T2-ED-1: Editorial is CEREBELLUM, Film Engine is CORTEX** (was Law 246)
Editorial decides WHEN to cut/hold/overlay.
Film Engine decides WHAT to show.
NEVER merge editorial timing into Film Engine.

**T2-ED-2: Murch Rule of Six scores every cut** (was Law 247)
Weighted: emotion 51%, story 23%, rhythm 10%, eye-trace 7%, planarity 5%, spatial 4%.
NEVER make cut decisions without consulting score.
Advisory-only: <0.45 = weak cut, recommends hold.

**T2-ED-3: ASL Governor enforces genre-calibrated pacing** (was Law 248)
Genre × emotion targets: gothic horror 4-12s, action 1.5-4s, drama 4-8s.
NEVER ignore ASL when setting shot durations.
Used to warn operator, not auto-adjust.

**T2-ED-4: Frame reuse requires BOTH blocking + static character** (was Law 250)
_is_character_static() checks movement indicators.
NEVER reuse frames with walking, turning, entering motion.

**T2-ED-5: Hold decisions use Murch <0.45 as reinforcement** (was Law 252)
Weak cut + static character = recommend hold instead of cut.
Hitchcock anticipation principle.
NEVER cut just because new shot exists.

**T2-ED-6: J-cuts and L-cuts classified by audio transition** (was Law 249)
dialogue→B-roll = L-cut, B-roll→dialogue = J-cut.
Maps to B-roll overlay audio handling in stitch.
NEVER treat all B-roll as silent inserts.

**T2-ED-7: AI gap workarounds are editorial solutions** (was Law 253)
Character drift → frame reuse.
Environment inconsistency → hold extend.
Temporal coherence → B-roll overlay.
Morphing → trim + hold.
These are how REAL editors handle similar problems.

**T2-ED-8: Editorial tags are ADVISORY** (was Law 254)
_editorial_skip_gen, _reuse_frame_from, _overlay_on, _hold_extension.
Pipeline decides what to act on.
NEVER make editorial a hard gate that blocks generation.

**T2-ED-9: Editorial tests (76) must pass before change** (was Law 255)
Includes Group 12 production stress test on real Victorian Shadows EP1 data.
Synthetic-only pass is NOT sufficient (Autonomous Build Covenant Rule C).
NEVER ship editorial change without full suite.

**T2-ED-10: Phase 1 (COMPLETE) - Foundation Analysis + Tagging** (was from V25.3 Phased Implementation Plan)
Murch scoring, ASL governor, J/L-cut classification, frame reuse detection, B-roll overlay detection, hold-vs-cut, AI gap mapping.
76-test suite ALL GREEN with production stress test.
`/api/v25/editorial-plan/{project}` endpoint wired (returns plan, non-blocking).

### CREATION PACK (Pre-Generation Quality Gate) — Laws T2-CK-1 through T2-CK-10

**T2-CK-1: Creation Pack validation is BLOCKING before ANY generation** (V27.1)
`tools/creation_pack_validator.py validate_project()` runs BEFORE first-frame generation.
If blocking_issues > 0, generation HALTS with actionable diagnostics.
NEVER generate frames without passing creation pack validation.
This is universal — applies to ALL scripts/stories, not project-specific.

**T2-CK-2: Character refs MUST match canonical appearance description** (V27.1)
Every CHAR_REFERENCE.jpg must be generated FROM the cast_map `appearance` field.
If `_reference_generation_prompt` is missing or doesn't match appearance keywords: ref is UNVERIFIED.
UNVERIFIED refs trigger auto-recast: regenerate from canonical description via FAL.
Production evidence: Nadia Cole had sci-fi blazer ref for a jeans-and-flannel character.

**T2-CK-3: Multi-image character ref pack per character** (V27.1)
Minimum viable: headshot (CHAR_REFERENCE.jpg).
Production ready: headshot + three_quarter.
Full pack: headshot + three_quarter + full_body + profile.
`select_best_ref_for_shot()` picks the best ref per shot type:
  close_up/reaction → headshot, medium/OTS → three_quarter, wide/closing → full_body.
**CRITICAL: Headshot is TEXT-TO-IMAGE (identity master). All other angles are IMAGE-TO-IMAGE
reframes FROM the headshot using nano-banana-pro/edit with image_urls=[headshot].
NEVER generate angle variants as independent text-to-image — they will be different people
with wardrobe drift. Same person, same wardrobe, different camera angle.**

**T2-CK-4: Multi-angle location ref pack per location** (V27.1)
Minimum viable: one wide master (existing behavior).
Production ready: wide_interior + reverse_angle.
Full pack: wide_exterior + wide_interior + reverse_angle + medium_interior + detail_insert.
Reverse angles are MANDATORY for OTS dialogue scenes — cannot do shot/reverse-shot with only one angle.
**CRITICAL: Wide master is the SOURCE. All other angles are IMAGE-TO-IMAGE reframes FROM
the wide master using nano-banana-pro/edit with image_urls=[wide_master].
NEVER generate location angles as independent text-to-image — they will be completely
different rooms. Same room, same architecture, same lighting, different camera position.
No characters in ANY location ref — add "no people" to all location prompts.
Exterior locations need 360-degree atmosphere: front approach + garden view + sky/weather.**

**T2-CK-5: Auto-recast generates refs from description when cast doesn't match** (V27.1)
`build_recast_manifest()` produces FAL generation jobs for all missing/mismatched refs.
Character refs: 3 candidates generated, best selected (same pattern as Eleanor V26.1 fix).
Location refs: 1 candidate per angle type.
All refs stored in character_library_locked/ and location_masters/ with provenance metadata.
NEVER keep a ref that doesn't match the screenplay description.

**T2-CK-6: DP framing standards determine ref selection per shot type** (V27.1)
SHOT_TYPE_REF_MAP in creation_pack_validator.py maps each shot type to ideal ref types.
establishing → no char ref, wide_exterior loc.
close_up → headshot char, no loc.
OTS → three_quarter char, reverse_angle loc.
medium → three_quarter char, medium_interior loc.
NEVER use a headshot ref for a wide shot or a full-body for a close-up.
**This mapping is AUTOMATIC — resolve_refs() in atlas_scene_controller.py reads shot_type
and selects the correct angle from the character's ref pack and location's angle pack.
Each shot stores `_dp_ref_selection` with resolved paths + lens + notes.
Each shot stores `_fal_image_urls_resolved` with the exact ref paths for FAL.**

**T2-CK-7: B-roll MUST have narrative content, not empty rooms** (V27.1)
`analyze_broll_narrative()` checks B-roll descriptions against story bible.
Generic B-roll ("environmental detail only", "no people") flagged for replacement.
B-roll should show: approaching characters, meaningful props, servants/staff, letters/photos,
exterior-to-interior transitions, or reverse angles of conversation spaces.
Production evidence: Empty drawing room B-roll followed by characters appearing from nowhere.

**T2-CK-8: Ref provenance tracked with _reference_generation_prompt** (V27.1)
When a CHAR_REFERENCE is generated, the prompt used MUST be saved to cast_map:
  `"_reference_generation_prompt": "the exact prompt"`,
  `"_reference_validated": true`,
  `"_reference_validated_at": "ISO timestamp"`.
This enables future validation: was this ref generated from the canonical description?
NEVER generate a ref without recording its provenance.

**T2-CK-9: Creation Pack runs on ALL scripts universally** (V27.1)
The validator is script-agnostic: reads cast_map + shot_plan + story_bible.
Works for Victorian Shadows, Sicario, any future project.
No hardcoded character names, locations, or project paths.
If a new script is imported, creation pack validation runs automatically before first generation.

**T2-CK-10: Recast manifest is auditable and operator-visible** (V27.1)
`build_recast_manifest()` returns structured list of all generation jobs.
Operator can review and approve before execution.
Each job has: prompt, output_path, num_candidates, priority.
NEVER auto-execute recast without operator visibility (advisory, like editorial).

### PROBE SHOT (Pre-Scene Canary) — Laws T2-PS-1 through T2-PS-5

**T2-PS-1: Run 1 probe shot before ANY full scene render** (V27.1)
`select_probe_shot()` picks the HARDEST shot in the scene (multi-char dialogue > single-char > B-roll).
This single shot runs through the FULL pipeline: ref resolution → Film Engine → FAL → doctrine post-gen → vision.
If probe fails: HALT. Fix issues. Re-probe. Only then proceed to full scene.
NEVER run a full 12-shot scene without probing first.

**T2-PS-2: Probe selects hardest shot, not easiest** (V27.1)
Priority: multi-character dialogue OTS > single-character dialogue > character no-dialogue > B-roll.
Rationale: if the hardest shot passes (identity for 2 chars, dialogue markers, OTS framing), everything easier will too.
NEVER probe with an establishing shot or B-roll — they test nothing about character identity.

**T2-PS-3: Probe result analyzed before proceeding** (V27.1)
`analyze_probe_result()` checks: doctrine gates_checked > 0, no phase exceptions,
vision identity score ≥ 0.6, location score ≥ 0.5, frame actually generated.
Status: PASS (proceed), WARN (review then proceed), FAIL (halt).
NEVER ignore a FAIL probe — it means the pipeline has a broken component.

**T2-PS-4: Probe captures full diagnostic telemetry** (V27.1)
Probe result includes: ref_resolution, doctrine_verdict, vision_analysis, elapsed_ms.
This data surfaces issues that would otherwise only appear after wasting a full scene render.
Production evidence: V26.1 first render showed doctrine gates_checked=0 for ALL shots — a probe would have caught this on shot 1.

**T2-PS-5: Probe is part of the render endpoint, not a separate workflow** (V27.1)
When `POST /api/v26/render` receives a scene, it auto-selects and runs probe shot FIRST.
If probe passes: continues to remaining shots.
If probe fails: returns probe diagnostics immediately, does NOT proceed.
This is automatic behavior, not an optional step the operator must remember.

---

## SECTION 3: OPERATIONAL RULES (TIER 3)

### UPGRADE VALIDATION PROTOCOL (V29.17 — BINDING)

Every new module, fix, or wiring change MUST pass through all 4 gates before it is considered DONE.
This protocol exists because the #1 source of production failures is "built but not wired" code.

**THE 4 GATES (must complete in order):**

| Gate | Action | Command | Pass Condition |
|------|--------|---------|----------------|
| G1 SYNTAX | Parse the modified file | `python3 -c "import ast; ast.parse(open('file.py').read()); print('OK')"` | No SyntaxError |
| G2 IMPORT | Verify the module imports without crashing | `python3 -c "import module_name; print('OK')"` | No ImportError |
| G3 WIRED | Verify session_enforcer passes all checks | `python3 tools/session_enforcer.py` | ✅ SYSTEM HEALTHY |
| G4 PROVEN | Live generation test confirms output changed | Run `--frames-only` on 1 shot; verify new timestamp | Frame newer than code change |

G1 and G2 take seconds. G3 catches wiring gaps. G4 is the final proof.
NEVER declare a component READY if it has not reached G4 for production, or G3 minimum for wiring.

**ADDING A NEW MODULE — CHECKLIST:**

When creating a new `tools/new_module.py`, before merging:

```
□ G1: python3 -c "import ast; ast.parse(open('tools/new_module.py').read()); print('OK')"
□ G2: python3 -c "sys.path.insert(0,'tools'); import new_module; print('OK')"
□ Add import to orchestrator_server.py AND atlas_universal_runner.py (belt-and-suspenders)
□ Add call to the CORRECT pipeline phase (not just import — actually called in the generation path)
□ Add WIRING PROBE to session_enforcer.py:
    - Probe checks that the module is CALLED (not just imported) in the runner
    - Uses substring match on function body, not fragile single-line regex
    - DOTALL regex must be scoped to the function body, not the whole file
□ G3: python3 tools/session_enforcer.py → ✅ SYSTEM HEALTHY (0 blocks)
□ G4: Run 1-shot test, confirm output reflects new module's effect
```

**WRITING WIRE PROBES IN SESSION_ENFORCER — RULES:**

These rules prevent false alarms (the root cause of the 4-failure audit from 2026-03-21):

1. Use SUBSTRING MATCH (`"function_name" in body`) not `re.search` for simple existence checks
2. If using `re.search`, scope the match to a specific FUNCTION BODY, not the whole file:
   `body_match = re.search(r'def target_func\b.*?(?=\ndef |\Z)', code, re.DOTALL); body = body_match.group(0)`
3. Never use `re.DOTALL` on a pattern that spans a function name + its implementation
   (e.g., `route_shot.*ltx` with DOTALL will match the function's own RETIRED comment)
4. For multi-line constructs (e.g., `raise RuntimeError(\n    "message")`), check for the
   FIRST LINE only: `"raise RuntimeError(" in body` not `raise RuntimeError.*message`
5. Case-sensitive by default unless the codebase mixes cases (use `code.lower()` then match)
6. Always add a comment explaining WHY this pattern catches the right wiring, and what a
   false alarm would look like — so the next engineer can debug it

**AUDIT REPORT VALIDATION — HOW TO DISTINGUISH FALSE NEGATIVES:**

When an audit script reports FAIL, before acting:
1. Read the actual line(s) it's checking — `grep -n "pattern" file.py`
2. Check if the pattern spans multiple lines (DOTALL), function bodies, or comment text
3. Check case sensitivity (V_score vs v_score)
4. Check import style (`from vision_judge import` vs `from tools.vision_judge import`)
5. If the INTENT is wired (code does what it should) but the PATTERN is wrong → fix the probe
6. If the INTENT is missing (code doesn't call what it should) → fix the wiring

Run `python3 tools/session_enforcer.py` as the authoritative gate — it uses substring matching
which is robust. The one-off audit scripts are for discovery only, not for pass/fail decisions.

---

### Claude Discipline Protocol (V27.6 — BINDING)

**BUILT ≠ WIRED ≠ TESTED ≠ PROVEN**

When Claude says "this is wired" or "everything is connected," the following verification levels MUST be explicitly stated:

| Level | Meaning | Verification |
|-------|---------|-------------|
| BUILT | Code exists in a .py file | `ls tools/new_module.py` |
| WIRED | Code is imported and called by controller/orchestrator | `grep "new_module" atlas_v26_controller.py orchestrator_server.py` |
| TESTED | Unit tests pass | `python3 tools/test_*.py` — 0 FAIL |
| PROVEN | Live FAL generation confirms output changed | New frame exists with timestamp AFTER code change |

Claude MUST NOT say "ready" or "wired" if the component is only BUILT.
Claude MUST NOT show frames from previous runs as if they are new results.
Claude MUST state which level each component has reached.

**PRE-RUN ARCHIVE PROTOCOL (MANDATORY):**
Before ANY generation run: `python3 tools/pre_run_gate.py {project} {scene_id}`
This archives all stale frames/videos for the target scene so the UI shows truth only.
Old artifacts are NEVER deleted — moved to `_archived_runs/` with timestamp.
The operator should ALWAYS see only current-run results.

**STALE ARTIFACT RULE:**
If `first_frames/` or `videos/` contains files from a previous run, the scene is NOT "generated."
Previous run artifacts MUST be archived before claiming a scene is ready.
The UI must show current truth, not historical attempts.

**HONEST STATE REPORTING:**
When asked "is this ready?" or "is this wired?", Claude must run:
  1. `python3 tools/pre_run_gate.py` — proves data, wiring, and prompts are valid
  2. Show the actual gate output, not a summary
  3. If any WARN or FAIL: state explicitly what's not ready and why

### Session Startup Protocol

**NEW PROJECT?** Read `PRODUCTION_STANDARD.md` first. Every project — Victorian Shadows, Crown Heights, AIFL, or any new script — must pass the Section 1 initialization checklist before any generation. PRODUCTION_STANDARD.md is the universal per-project contract. CLAUDE.md is the system law.

**MANDATORY FIRST COMMAND (before ANY work):**
```bash
python3 tools/session_enforcer.py
```
This verifies 31 checks: code paths match doctrine, all 17 systems importable, model routing correct,
generation gate intact, CLAUDE.md doctrine present. If ANY blocking issue: FIX BEFORE TOUCHING ANYTHING.

**The universal runner is the ONLY canonical generation path:**
```bash
python3 atlas_universal_runner.py <project> <scene_id> [scene_id...] --mode lite|full
```
NEVER write a new one-off runner script. NEVER bypass the generation gate.
NEVER use nano-banana-pro (T2I) for character shots. NEVER use LTX for character video.
Every regression in V29 came from bypassing what already worked.

**DOCTRINE STATUS CHECK (before any work):**

```
1. All doctrine tests green? → python3 tools/test_doctrine_all_phases.py
2. All CPC tests green? → python3 tools/test_creative_prompt_compiler.py
3. All editorial tests green? → python3 tools/test_editorial_intelligence.py
4. All continuity/film/regression green? → test_continuity_memory + test_film_engine + test_v23_regression
5. GateResult is dataclass? → grep "class GateResult" tools/doctrine_engine.py
6. Doctrine hooks in BOTH master-chain AND generate-first-frames?
7. __pycache__ cleared? → find . -name __pycache__ -type d -exec rm -rf {} +
8. image_urls using R2 or base64, NOT fal.media?
9. Production stress tests pass on real shot_plan.json? (Group 12 editorial tests)
10. Editorial test count 76? (Total suite: 362+ across all modules)

If ANY fail → FIX BEFORE touching anything else.
```

### Pre-Generation Checklist (Mandatory)

```
Before ANY generation run, verify:

□ python3 tools/pre_run_gate.py {project} {scene_id} → ALL PASS
□ Stale artifacts archived (pre_run_gate Phase 1)
□ Beat-shot audit reviewed (pre_run_gate Phase 4)
□ Prompt contamination check clean (pre_run_gate Phase 5)
□ shot_plan.json shot count matches expected
□ ALL character shots have [CHARACTER:] identity blocks
□ ALL scenes have beat_ref on shots (or acknowledged as gap)
□ No stale session paths in headshot/reference URLs
```

### Production Workflow (V29.16 — 2-Stage Validated Run)

**CANONICAL PATH (UI-first, with manual validation gate):**
```
STAGE A — IMPORT + PREP (run once per script):
1.  POST /api/v6/script/full-import              ← Import screenplay
2.  POST /api/auto/generate-story-bible           ← LLM narrative expansion
3.  POST /api/shot-plan/fix-v16                   ← Enrichment + durations + CHECK 7A-7F
4.  python3 tools/post_fixv16_sanitizer.py {proj} ← Auto-strip contaminants
5.  POST /api/v6/casting/auto-cast                ← Match characters to AI actors
6.  POST /api/v21/audit/{project}                 ← 10-contract audit (0 CRITICAL)
7.  find . -name __pycache__ -exec rm -rf {} +    ← Clear stale bytecode

STAGE B — STEP 1: FIRST FRAMES (review before spending on video):
8.  python3 atlas_universal_runner.py {proj} {scene} --mode lite --frames-only
    └── Generates 1 first frame per shot (NOT 3 — multi-candidate retired V29.16)
    └── Writes first_frame_url to shot_plan.json → UI filmstrip shows frames immediately
    └── Sets _approval_status=AWAITING_APPROVAL on each shot
    └── STOPS. No video generation.
    └── Review filmstrip in ATLAS Auto Studio: check blocking, composition, identity

STAGE C — STEP 2: VIDEOS (only after frame validation):
9.  python3 atlas_universal_runner.py {proj} {scene} --mode lite --videos-only
    └── Uses approved frames from disk
    └── Kling v3/pro: start_image_url + multi_prompt + elements (char refs) per shot
    └── End-frame chaining: shot N last frame → shot N+1 start
    └── Writes video_url to shot_plan.json → UI shows videos immediately
    └── Stitches scene, updates reward ledger with real V/I/C scores
    └── UI bundle.dirty flag set → filmstrip refreshes automatically

STAGE D — FULL CUT:
10. python3 atlas_universal_runner.py {proj} 001 002 003 --mode lite --videos-only
    ← (after all scenes' frames are validated)
```

**QUICK REFERENCE:**
```bash
# Frames only (review gate):
python3 atlas_universal_runner.py victorian_shadows_ep2 001 --mode lite --frames-only

# Videos only (after review):
python3 atlas_universal_runner.py victorian_shadows_ep2 001 --mode lite --videos-only

# Full auto (skips validation gate — only for trusted re-runs):
python3 atlas_universal_runner.py victorian_shadows_ep2 001 --mode lite
```

**KEY LAWS (V29.16):**
- 1 candidate per shot (NOT 3) — manual frame review IS the quality gate (T2-FE-33 retired)
- video_url written to shot_plan after generation → UI always reflects truth
- bundle.dirty flag set after every write → UI auto-refreshes
- NEVER run --videos-only without reviewing frames first

### Server Startup Ritual

After ANY code fix, before restarting server:

```bash
# Clear Python import cache
find . -name "__pycache__" -type d -exec rm -rf {} +

# Sync agent mirror
cp atlas_agents/*.py atlas_agents_v16_7/atlas_agents/

# Restart server
python3 orchestrator_server.py
```

### Backup Protocol

Before any destructive operation:

```bash
# Create timestamped backup
cp shot_plan.json shot_plan.json.backup_operation_YYYYMMDD_HHMMSS

# Archive stale frames before canonical re-render
mkdir -p fumigated_frames_YYYYMMDD_HHMMSS
mv first_frames/* fumigated_frames_YYYYMMDD_HHMMSS/ 2>/dev/null || true
```

### Troubleshooting: Triage Order

When a run fails, diagnose in this order (same order as biological body):

```
1. 🦴 Skeleton — did shot_plan.json change shape? (schema version check)
2. 🫀 Liver — are there contaminants in prompts? (sanitizer pass)
3. 🛡️ Immune — is doctrine throwing exceptions? (check can_proceed logic)
4. ⚡ Nervous System — are all 4 hooks firing? (grep doctrine_runner logs)
5. 👁️ Eyes — are image URLs valid and not expired? (R2 vs fal.media check)
6. 🧠 Prefrontal — does the scene have a plan? (scene_initialize returned READY?)
7. 🎬 Cinematographer — do 3 angle variants exist per shot? (count files in variants/)
8. ✂️ Editor — is coverage A/B/C distributed properly? (check coverage_role counts)
9. 🧩 Cerebellum — are Murch scores differentiating? (avg >0.55, range >0.2 on real data)
```

---

## SECTION 4: DEPRECATED LAWS (Superseded by Film Engine)

These laws assumed fix-v16 enrichment was the only path. Film Engine provides an alternative:

| Law | Was | Now | Reason |
|-----|-----|-----|--------|
| 135 | Story bible enrichment mandatory in fix-v16 | OPTIONAL | Film Engine has story_bible in context |
| 136-137 | CHECK 5B mandatory | SUPERSEDED | Film Engine dialogue injection |
| 138-139 | Chain video prompts must use `_build_video_prompt()` | SUPERSEDED | Film Engine `compile_shot_for_model()` |
| 144 | Pipeline must be: import→bible→fix-v16→cast→generate | UPDATED | fix-v16 still needed for durations/coverage, prompt enrichment optional |
| 146 | CHECK 7A-7F mandatory in fix-v16 | ADVISORY | Clean up fix-v16 artifacts; 7F unnecessary if Film Engine is authority |
| 185 | Check "composition:" marker >70% | DEPRECATED | Film Engine doesn't use these markers |
| 188 | Sanitizer mandatory after fix-v16 | OPTIONAL | Film Engine has built-in CPC decontamination |

### V36 FORBIDDEN SYSTEMS

These systems are permanently retired. Any attempt to route to them is a constitutional violation (C3).

| System | Status | Replacement |
|--------|--------|-------------|
| Seedance (all variants, muapi.ai) | RETIRED V31.0 | Kling v3/pro multi-prompt |
| LTX (fal-ai/ltx-2/image-to-video/fast) | RETIRED V29.3 | Kling v3/pro multi-prompt |
| muapi.ai endpoint | RETIRED V31.0 | Remove from codebase on sight |
| Auto-mutation of QA thresholds | FORBIDDEN | Thresholds set by human calibration only |
| Heatmap-triggered generation | FORBIDDEN | Section 0: Heatmap is OBSERVE_ONLY |
| QA autonomous prompt rewriting | FORBIDDEN | Section 0: QA returns verdicts, Controller acts |

---

## SECTION 5: ARCHITECTURE REFERENCE

### Component Status (V27.1)

| Component | Status | Purpose |
|-----------|--------|---------|
| Script Parser | ✅ STABLE | V17 regex + LLM hybrid |
| Story Bible Generator | ✅ STABLE | LLM narrative expansion |
| Duration Scaler | ✅ STABLE | Dialogue-aware runtime math |
| Camera Defaults | ✅ STABLE | Auto filmmaker presets |
| Auto-Caster | ✅ STABLE | Character → AI actor matching |
| Enforcement Agent | ✅ STABLE | V13 gold standard pre-gen |
| Film Engine (Brain Cortex) | ✅ V26.1 FIXED | Universal compile_shot_for_model() |
| Basal Ganglia | ✅ NEW V24 | Candidate evaluation + selection |
| Meta Director | ✅ NEW V24 | Shot readiness + health scoring |
| Vision Analyst | ✅ NEW V24 | 8-dimension visual scoring |
| Continuity Memory | ✅ NEW V24.1 | Spatial state + reframe candidates |
| Master Shot Chain | ✅ NEW V18 | Nano → angles → end-frame → video |
| Continuity Gate | ✅ NEW V18.2 | State + coverage + bridge scoring |
| Logical Oversight Agent | ✅ NEW V17.6 | 4-gate policy engine |
| Movie Lock Mode | ✅ NEW V21.9 | 10-contract enforcement |
| Wardrobe Manager | ✅ NEW V17.7.5 | Look IDs + prompt injection |
| Extras Manager | ✅ NEW V17.7.5 | Crowd packs + templates |
| Script Fidelity Agent | ✅ NEW V17.7 | Beat→shot validation |
| Creative Prompt Compiler | ✅ NEW V25.1 | Generic contamination immunity |
| Editorial Intelligence | ✅ PHASE 1 | Murch cuts, ASL pacing, J/L-cuts (advisory) |
| **Creation Pack Validator** | ✅ NEW V27.1 | Multi-image char refs + multi-angle loc refs + DP best-fit selection |
| **Probe Shot System** | ✅ NEW V27.1 | Single-shot canary before full scene render |
| **Auto-Recast Engine** | ✅ NEW V27.1 | Generate refs from canonical descriptions when cast doesn't match |
| **Identity Injector** | ✅ NEW V27.5 | Amplified character descriptions injected into every prompt |
| **Social Blocking** | ✅ NEW V27.5 | Spatial geometry templates for multi-character shots |
| **Visual Signature** | ⚠️ PARTIAL V27.5 | Layer 1-3 operational, Layer 4-5 not yet implemented |
| **Scene Contract Generator** | ✅ NEW V28.0 | Scene-level truth: objective, beats, forbidden mistakes, coverage |
| **Shot Truth Contract** | ✅ NEW V28.0 | Per-shot locked truth: beat_ref, eye_line, body, cut_motivation |
| **Truth Gate** | ✅ NEW V28.0 | Validates truth before render (NON-BLOCKING in V28.0) |
| **Truth-to-Prompt Translator** | ✅ NEW V28.0 | Injects [PERFORMANCE:] blocks from truth fields into prompts |
| **Beat Enrichment** | ✅ NEW V27.6 | Permanent beat→shot mapping with locked fields |
| **Beat-Shot Linker** | ✅ NEW V27.6 | Cinematographic logic analysis (standalone diagnostic) |
| **Pre-Run Gate** | ✅ NEW V27.6 | 5-phase preflight: archive, data, wiring, beats, prompts |

### Key Endpoints (Most Used)

```bash
# Core Generation
POST /api/v6/script/full-import              ← Import screenplay
POST /api/auto/generate-story-bible           ← LLM expansion
POST /api/shot-plan/fix-v16                   ← Enrichment
POST /api/v6/casting/auto-cast                ← Character casting
POST /api/auto/generate-first-frames          ← Frame generation
POST /api/auto/render-videos                  ← Video generation
POST /api/v16/stitch/run                      ← FFmpeg stitch

# Verification & Audit
POST /api/v21/audit/{project}                 ← 10-contract audit
POST /api/v17/aaa-health/{project}            ← System health
POST /api/v25/editorial-plan/{project}        ← Editorial advice

# Wardrobe & Extras
POST /api/v17/wardrobe/auto-assign            ← Auto wardrobe
POST /api/v17/extras/assign                   ← Crowd packs

# LOA & Vision
POST /api/v17/loa/pre-gen-check               ← Ref authority audit
POST /api/v17/loa/rank-variants               ← Multi-angle scoring

# Movie Lock
POST /api/v21/gate-snapshot/{project}         ← Immutable snapshots
POST /api/v21/movie-lock/enable/{project}     ← Release mode
```

### Semantic Invariants (15 Total)

| # | Invariant | Severity | Status |
|---|-----------|----------|--------|
| 1 | shot_plan_exists | BLOCKING | ✅ |
| 2 | shots_have_duration | BLOCKING | ✅ |
| 3 | nano_prompt_present | BLOCKING | ✅ |
| 4 | characters_in_cast | WARNING | ✅ |
| 5 | no_forbidden_models | BLOCKING | ✅ |
| 6 | segments_for_extended | BLOCKING | ✅ |
| 7 | dialogue_not_stripped | BLOCKING | ✅ |
| 8 | segment_metadata_complete | BLOCKING | ✅ |
| 9 | ltx_prompt_contextual | WARNING | ✅ |
| 10 | location_master_for_scenes | BLOCKING | ✅ |
| 11 | character_refs_resolvable | BLOCKING | ✅ |
| 12 | vision_scores_for_approved | WARNING | ✅ |
| 13 | selected_variant_consistency | WARNING | ✅ |
| 14 | cast_map_field_normalization | WARNING | ✅ |
| 15 | locks_field_normalization | WARNING | ✅ |

### Model Lock (Absolute)

| Stage | Model | Purpose | Alternatives |
|-------|-------|---------|---------------|
| First Frame | fal-ai/nano-banana-pro | Text-to-image | NONE |
| Multi-Angle Reframe | fal-ai/nano-banana-pro/edit | Image-to-image angles | NONE |
| Video Gen (Primary) | fal-ai/kling-video/v3/pro/image-to-video | multi-prompt + @Element, end-frame chain | NONE |
| Video Gen (RETIRED) | ~~Seedance V2.0 via muapi.ai~~ | RETIRED V31.0 — replaced by Kling | DO NOT USE |
| Video Gen (RETIRED) | ~~fal-ai/ltx-2/image-to-video/fast~~ | RETIRED V29.3 — frozen statues | DO NOT USE |
| Stitch | ffmpeg | Deterministic concat | NONE |

### Asset Storage Paths

```
pipeline_outputs/{project}/
├── story_bible.json                ← Narrative with beats
├── shot_plan.json                  ← EXECUTION TRUTH
├── cast_map.json                   ← Character → actor mapping
├── wardrobe.json                   ← Look IDs + appearance
├── extras.json                     ← Crowd pack assignments
├── first_frames/                   ← Generated frames (JPG)
├── first_frame_variants/           ← 3 angle variants per shot
├── videos/                         ← Generated videos (MP4)
├── location_masters/               ← Location ref images
├── ui_cache/bundle.json            ← Cached UI bundle (.dirty = invalidate)
└── .vision_cache/                  ← SHA256-keyed vision embeddings
```

### Test Suite (362+ Tests)

- 125 CPC tests (Creative Prompt Compiler) — Group 9: production integration proof
- 76 Editorial tests — Group 12: real shot_plan.json stress test
- 74 Continuity Memory tests — State extraction + candidate generation
- 55 Film Engine tests — Compile path + prompt polarity + dialogue injection
- 31 Regression tests — V24.1 production parity checks
- Doctrine tests (various) — Phase validation

---

## SECTION 6: HONEST ARCHITECTURE MAP

### Design Truth: Film Engine is PROMPT COMPILER, Not Whole Brain

Film Engine compiles text prompts only. It does NOT:
- Load files from disk
- Resolve character reference image paths
- Make FAL API calls
- Pass image_urls to FAL
- Handle missing refs
- Write results to disk
- Manage durations, coverage roles, segments

**Orchestrator is EXECUTION AUTHORITY.** Film Engine is PROMPT AUTHORITY. They are complementary, not replaceable.

### What Must Run BEFORE Film Engine

| Step | System | Creates | Required? |
|------|--------|---------|-----------|
| Script import | `/api/v6/full-import` | shot_plan.json | YES |
| Story bible | `/api/auto/generate-story-bible` | story_bible.json | YES |
| fix-v16 | `/api/shot-plan/fix-v16` | durations, segments, A/B/C coverage | YES |
| Auto-cast | `/api/v6/casting/auto-cast` | cast_map.json | YES |
| Wardrobe | `/api/v17/wardrobe/auto-assign` | wardrobe.json | RECOMMENDED |

### What Film Engine Compiles (PROMPT AUTHORITY)

✅ Camera token translation (strip brands)
✅ Color science injection (genre-based, no film stocks)
✅ Negative prompt separation
✅ Dialogue marker injection
✅ CPC decontamination
✅ Emotion-to-physical translation
✅ Continuity delta injection

### What Orchestrator Executes (EXECUTION AUTHORITY)

✅ Load cast_map.json + resolve refs
✅ Load location masters
✅ Build image_urls array for FAL
✅ Make FAL API calls
✅ Handle missing refs (fallback)
✅ Save frames to disk
✅ Duration math + dialogue protection
✅ Coverage solver (ABC roles)

### Casting Data Flow (Verified)

```
cast_map.json
  ↓
SceneController.resolve_refs(shot, cast_map)
  ├── Priority 1: character_reference_url (locked identity)
  ├── Priority 2: reference_url
  └── Priority 3: headshot_url (AI fallback)
  ↓
PreparedShot.ref_urls = [resolved file paths]
  ↓
FAL API call: image_urls = [uploaded ref URLs]
  ↓
nano-banana-pro/edit generates frame WITH character identity
```

If cast_map missing or character_reference_url missing: Controller HALTS (correct).

### Location Data Flow (Verified)

```
location_masters/{scene_id}_master.jpg
  ↓
SceneController.resolve_refs()
  ↓
Appended to image_urls AFTER character refs
  ↓
FAL uses for environment consistency
```

If location master missing: Controller proceeds but environment may drift.

---

## SECTION 7: CHANGE LOG (Last 5 Versions Only)

### V29.16 (2026-03-20) — REWARD SIGNAL RESTORED + INTELLIGENCE-DRIVEN PROMPTS

**Root Cause (multiple simultaneous failures):**
1. V-score = 0.0 for ALL generated videos — Seedance saves as `001_seedance_group_01.mp4` but `_analyze_video` looked for `001_M01.mp4`. Every generated video was treated as missing.
2. C-score = 0.70 (floor) for ALL shots — chain frame naming followed same mismatch pattern.
3. I-score = 0.75 flat (heuristic) for ALL shots — `vision_judge` was imported BEFORE FAL_KEY was set, so Florence-2 never actually fired.
4. Story bible intent not reaching fallback prompts — `_build_prompt()` used only `_beat_action`, ignoring `_beat_atmosphere`, `_beat_dialogue`, `_body_direction`, and `_choreography`. CPC-contaminated choreography text was bleeding through as prompt content.
5. images_list ordering: location master at slot [1] meant characters were at slots [2+3] competing with room for model attention.

**Fixes (all 13 validated in dry-run):**
- ERR-01: `_analyze_video` uses `all_videos.get(sid, fallback)` — V-score now reflects actual video existence.
- ERR-NEW-20: C-score chain path derived from `os.path.basename(all_videos[sid])` — chain continuity now measurable.
- ERR-03: `GLOBAL_LOG_PATH = Path(__file__).parent / "atlas_learning_log.jsonl"` — regression prevention now fires.
- ERR-05: `seedance_calls/seedance_cost` added to `_cost_tracker`, `_track_cost("seedance", duration=dur)` wired in `gen_scene_seedance`. Cost tracking now includes Seedance.
- FAL_KEY timing: `os.environ.setdefault("FAL_KEY", ...)` moved BEFORE `vision_judge` import. Florence-2 now fires on character shots.
- Phase 1.4: `video_model`, `run_mode`, `run_flags` added to consciousness_state. Every run is now identifiable.
- Phase 2.2: images_list reordered to `[start_frame, char1, char2, location_master]`. Character refs now at highest-attention slots 2+3.
- Phase 2.3: V2.0 prompt builder role assignments updated: `"@image2 and @image3 define character faces and clothing. @image4 shows the room architecture."`
- V2.0 prompt prefix: Changed from `"Using @image1 @image2... as visual reference: [prompt]"` to `"Animate @image1. [content] [role assignments]"` — stronger semantic anchor.
- Intelligence-driven `_build_prompt()`: Now queries `_beat_action`, `_beat_dialogue`, `_beat_atmosphere`, `_body_direction`, and extracts dialogue from choreography `Speaking:` markers. CPC contamination check prevents generic choreography from bleeding into prompts.
- All 9 shot prompts (001/002) rewritten with kinetic verbs, visual specificity, temporal arc.
- Poll error capture: MUAPI 400 response body now printed before bail — enables diagnosis.

**Production Evidence (12 runs total, March 20 2026):**
- Scene 002: 4/4 shots ✓, full chain, 35s, $0.81. Confirmed: end-frame chaining works.
- Scene 001: 3/5 shots ✓ (M02 quota, M04 timeout), 30s, $0.81.
- Full film: `VICTORIAN_SHADOWS_V2915_FULL.mp4` (22MB), `VICTORIAN_SHADOWS_V2914_FULL.mp4` (49MB).
- Kling comparison: `scene001_full.mp4` (16MB, 5/5 shots, $12.95). Seedance cheaper at equivalent quality.

**New laws added:** T2-OR-22 (Seedance images_list slot ordering), T2-OR-23 (poll response body capture), T2-FE-37 (flat I-score = calibration suspect — Florence never fired).
**Files Modified:** `atlas_universal_runner.py` (13 fixes), `tools/atlas_learning_log.py` (ERR-03), `pipeline_outputs/victorian_shadows_ep1/shot_plan.json` (9 prompts rewritten).

---

## FINAL NOTE

**This document is the canonical instruction set for all Claude sessions working on ATLAS.** Every law has been battle-tested against production data from Victorian Shadows EP1. If something needs clarification, ask. If a law seems contradictory to another, Section 0 (V36 Authority Hierarchy) wins over everything below it; Constitutional Laws (Section 1) win over all organ laws.

**The biological body is intact.** Character consistency ✅, dialogue fidelity ✅, editorial differentiation ✅. Authority hierarchy locked ✅. Everything else is iteration.

---

*ATLAS V36.0 — AAA Production Factory for AI Filmmaking*
*Authority: Controller (EXECUTION) → QA Gates (PASS/FAIL) → Heatmap (OBSERVE)*
*Pre-requisites: import → story bible → fix-v16 → auto-cast → generate*
*376+ tests green | 10 Movie Lock contracts pass | Zero unresolved production incidents*
*This is how we build films at scale.*

---
## SECTION 8: PROTECTED UI FEATURES (DO NOT REMOVE OR OVERWRITE)

These UI features have been built, tested, and confirmed working. They MUST NOT be removed,
overwritten, or accidentally dropped when editing `auto_studio_tab.html` or `orchestrator_server.py`.
If you are about to touch either file, verify ALL features below are still intact AFTER your edit.

### 8.1 MANUAL APPROVAL — THUMBS UP / THUMBS DOWN

**Location:** `auto_studio_tab.html` — filmstrip render loop (search `V29.16: Thumbs up / thumbs down`)
**What it does:** Every frame card in the Previs Filmstrip has a bottom bar with three buttons:
  - 👍 (green) — calls `approveShot(shot_id)` → POST `/api/auto/approve-shot` → sets `_approval_status=APPROVED`
  - 👎 (red) — calls `regenShot(shot_id)` → first POST `/api/auto/diagnose-shot` → shows toast with failure type → then POST `/api/auto/regen-shot` with diagnosis
  - ▷ (cyan) — calls `runSingleShot(shot_id)` — runs just that shot through the runner

**Backend endpoints (ALL must exist in orchestrator_server.py):**
  - `POST /api/auto/approve-shot` — sets `_approval_status` on shot, invalidates bundle cache
  - `POST /api/auto/diagnose-shot` — Gemini/Claude VLM classifies rejection reason (IDENTITY/LOCATION/CAMERA/BLOCKING/STORY_BEAT/TONE)
  - `POST /api/auto/regen-shot` — V30.5 diagnostic regen, routes through atlas_universal_runner

**Approval status badge:** Top-left corner of each frame card shows colored icon (✓ green, ⏳ amber, ↺ red)
**Approval status colors:** `APPROVED`=green, `AUTO_APPROVED`=teal, `AWAITING_APPROVAL`=amber, `REGEN_REQUESTED`=red

**NEVER remove the thumbBar div from the filmstrip render loop.**
**NEVER remove the approve-shot or regen-shot endpoints.**

### 8.2 GRID LAYOUT — SHOT GALLERY

**Location:** `auto_studio_tab.html` CSS — `.shot-gallery-list` class
**What it does:** The Shot Gallery section (id=`shotGalleryList`) renders shot cards in a responsive CSS grid.
```css
.shot-gallery-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 12px;
    align-content: start;
}
```
**Mobile override** (in @media max-width block): `.shot-gallery, .shot-gallery-list { grid-template-columns: 1fr !important; }`

**NEVER change `.shot-gallery-list` back to `flex-direction: column`.**
**NEVER remove the `display: grid` from this class.**

### 8.3 AUTO-REFRESH / LIVE HYDRATION

**Location:** `static/atlas-ui.js` (loaded on every page)
**What it does:** Polls `/api/live-generations` every 3 seconds. If the generation state changes, refreshes all `img[src*="/api/media"]` elements by appending `&_t=<timestamp>` to bust cache. This keeps the filmstrip live-updating during generation without a full page reload.

**NEVER remove or replace `static/atlas-ui.js`.**
**NEVER remove the `setInterval` polling in atlas-ui.js.**
**The file is served as a static asset — ensure `GET /static/atlas-ui.js` route remains in orchestrator.**

### 8.4 IMAGE LIGHTBOX

**Location:** `static/atlas-ui.js` — `atlasLightbox(src)` function
**What it does:** Creates a full-screen overlay showing an enlarged image. Triggered by `onclick` on images.
Auto-wired every 2 seconds to `.previs-card img` and `[class*=previs] img` elements via MutationObserver-style interval.
Also manually triggered in Shot Gallery: `onclick="openLightbox('${firstFrameUrl}')"`.

**NEVER remove `atlasLightbox()` from atlas-ui.js.**

### 8.5 DIAGNOSTIC REGEN FLOW (THUMBS-DOWN)

**Location:** `auto_studio_tab.html` — `regenShot(shotId, frameEl)` function (search `V30.5.1: REGEN SHOT`)
**Flow:**
  1. Shows "🔍 Diagnosing..." overlay on the frame card
  2. POST `/api/auto/diagnose-shot` → get failure type + reason
  3. Shows non-blocking toast: `🎭 IDENTITY: reason → Regenerating with fix...`
  4. Switches overlay to "⏳ Regenerating..."
  5. POST `/api/auto/regen-shot` with `{ diagnosis, apply_constraints: true }`
  6. On success: refreshes filmstrip via `loadScreeningRoom()`

**NEVER simplify regenShot() to skip the diagnose step.**
**NEVER replace the two-step diagnose→regen flow with a direct regen.**

### 8.6 INLINE VIDEO PLAYER

**Location:** `auto_studio_tab.html` — Screening Room shot detail panel
**What it does:** When a shot has a `video_url`, the detail panel shows an inline `<video>` element with controls.
The filmstrip frame also gets a purple `has-video` status dot (`.ff-status.has-video`).

**NEVER remove the `<video>` element rendering from the shot detail panel.**

### 8.7 NEWEST-FIRST SORT ORDER

**Location:** `auto_studio_tab.html` — filmstrip generation (search `_screeningAllShots`)
**What it does:** Shots are shown in their shot_plan order (001_M01 → 001_M02 → ...) which is newest-generated first within a scene. The bundle endpoint returns shots in order. Do not reverse this.

### 8.8 GENERATION MONITOR OVERLAY

**Location:** `auto_studio_tab.html` — `_genMonitorPollInterval` logic
**What it does:** During active generation, polls the backend every few seconds and updates frame cards with progress overlays (`data-progress` attribute). Shows `gen-pulse` animation on generating cards.

**NEVER remove the generation monitor polling.**

### 8.9 V37 GOVERNANCE DASHBOARD BAR

**Location:** `auto_studio_tab.html` — `id="v37GovernanceBar"` (search `V37 GOVERNANCE DASHBOARD`)
**What it does:** Thin status bar rendered directly above the Previs Filmstrip. Four inline sections, all read-only:
  - **Assets**: total registered assets + breakdown by type (first_frame · video_clip) from `/api/v37/registry/stats`
  - **Cost**: spend vs $25 budget cap with colour-coded fill bar from `/api/v37/cost/{project}` — green→amber→red as budget is consumed
  - **Release**: last gate score + PASS/HOLD/RERENDER_REQUIRED badge from `/api/v37/release/{project}`
  - **Invariants**: regression guard result N/N with ✅ OK or 🔴 N FAIL from `/api/v37/regression`
  - **↺ button**: calls `v37RefreshAll()` — manually refreshes all four sections

**JS functions (all in `auto_studio_tab.html` bottom `<script>` block — PROTECTED):**
  - `v37RefreshAll()` — dispatches all 4 fetches; called by button, on rehydrate, on DOMContentLoaded, every 60s
  - `v37LoadRegistry()` — fetches `/api/v37/registry/stats`
  - `v37LoadCost(proj)` — fetches `/api/v37/cost/{project}`
  - `v37LoadRelease(proj)` — fetches `/api/v37/release/{project}`
  - `v37LoadRegression()` — fetches `/api/v37/regression`

**Backend endpoints (ALL must exist in `orchestrator_server.py` — added V37):**
  - `GET /api/v37/registry/stats` — asset_registry.get_registry_stats()
  - `GET /api/v37/registry/{project}` — asset_registry.get_assets_by_episode()
  - `GET /api/v37/cost/{project}` — cost_controller.get_episode_spend() / get_episode_projection()
  - `GET /api/v37/cost` — cost_controller.get_network_spend()
  - `GET /api/v37/release/{project}` — release_gate.get_release_status()
  - `POST /api/v37/release/score/{project}` — release_gate.score_episode()
  - `GET /api/v37/regression` — regression_guard.run_preflight()

**Runner hooks (in `atlas_universal_runner.py` — added V37):**
  - After frame write-back (~line 4141): `_v37_register_asset` + `_v37_log_cost` per frame
  - After video write-back (~line 4559): `_v37_register_asset` + `_v37_log_cost` per video
  - All hooks are non-blocking — wrapped in try/except, fail silently

**NEVER remove `id="v37GovernanceBar"` from the HTML.**
**NEVER remove the `v37RefreshAll` / `v37LoadRegistry` / `v37LoadCost` / `v37LoadRelease` / `v37LoadRegression` JS functions.**
**NEVER remove the `/api/v37/*` endpoints from orchestrator_server.py.**
**NEVER remove the `_V37_GOVERNANCE` import block or the two hook call sites from atlas_universal_runner.py.**

**Verify after any UI edit:**
```bash
grep -n "v37GovernanceBar\|v37RefreshAll" auto_studio_tab.html | wc -l
# should be > 0
grep -n "api/v37" orchestrator_server.py | wc -l
# should be 7
grep -n "_V37_GOVERNANCE" atlas_universal_runner.py | wc -l
# should be 4+
```

---

## SECTION 9: PRE-RESPONSE PROTOCOL (MANDATORY FOR ALL UI SESSIONS)

Before making ANY change to ATLAS code — especially `auto_studio_tab.html`, `orchestrator_server.py`,
or `static/atlas-ui.js` — follow this protocol:

### Step 1: Read CLAUDE.md first
```
Read /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/CLAUDE.md
```
This file is the canonical law. If you skip it and overwrite a protected feature, the burden is on you.

### Step 2: For UI changes — read the file you're editing
```
# For HTML/JS changes:
Read auto_studio_tab.html (at minimum the relevant section + CSS for modified classes)
Read static/atlas-ui.js (it's only 33 lines — always read it)

# For backend changes:
Grep orchestrator_server.py for the endpoint you're touching
Read ±50 lines around the change point
```

### Step 3: Check for protected features before editing
Before writing any new HTML/CSS/JS, verify these elements still exist in your planned output:
- `thumbBar` div with `thumbUp` (👍) and `thumbDown` (👎) buttons in filmstrip loop
- `.shot-gallery-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }`
- `static/atlas-ui.js` loaded via `<script src="/static/atlas-ui.js">` in HTML head
- `regenShot()` function with 2-step diagnose→regen flow
- `approveShot()` function posting to `/api/auto/approve-shot`
- `/api/auto/approve-shot` endpoint in orchestrator_server.py
- `/api/auto/diagnose-shot` endpoint in orchestrator_server.py
- `/api/auto/regen-shot` endpoint in orchestrator_server.py

### Step 4: Check ECC keep-up logs for recent changes
```bash
ls -lt /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/ecc_logs/ 2>/dev/null | head -10
# or check recent session notes in the working directory
```

### Step 5: Never overwrite inline JS/CSS without inventorying what's there
The `auto_studio_tab.html` is 33,000+ lines. A `Write` tool call that replaces the whole file
WILL lose features. Always use `Edit` tool with targeted `old_string → new_string` replacements.
**NEVER use `Write` to replace `auto_studio_tab.html` entirely.**
**NEVER use `Write` to replace `orchestrator_server.py` entirely.**

### Step 6: After any UI change — verify these still exist
```bash
grep -n "thumbBar\|thumbUp\|thumbDown" auto_studio_tab.html | wc -l
# should be > 0

grep -n "display: grid" auto_studio_tab.html | grep "shot-gallery"
# should show the .shot-gallery-list grid rule

grep -n "atlas-ui.js" auto_studio_tab.html
# should show the <script src> tag

grep -n "v37GovernanceBar\|v37RefreshAll" auto_studio_tab.html | wc -l
# should be > 0 (V37 governance bar + JS)

grep -n "api/v37" orchestrator_server.py | wc -l
# should be 7 (V37 endpoints)

grep -n "_V37_GOVERNANCE" atlas_universal_runner.py | wc -l
# should be 4+ (V37 runner hooks)
```

### ECC / Scheduled System Context
The ATLAS system has a scheduled ECC (Error Correction & Continuity) system that runs:
- **Hourly**: keep-up checks (session_enforcer, reward signal, wire verification)
- **Every 4h**: proof-gate runs (generation tests, identity scoring)
- **Daily**: full regression suite

Before a major session, check if any ECC run has flagged issues:
```bash
python3 tools/session_enforcer.py  # always run this first
```
If session_enforcer reports blocks, fix those before any other work.
