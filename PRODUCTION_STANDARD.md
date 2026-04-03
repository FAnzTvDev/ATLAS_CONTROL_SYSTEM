# PRODUCTION_STANDARD.md — ATLAS Universal Project Standard
**Version:** V1.0 (2026-03-23)
**Applies to:** ALL ATLAS projects — Victorian Shadows, Crown Heights, AIFL, and every future project.
**Authority:** This document defines the universal pipeline contract. CLAUDE.md defines system-level laws.
**Rule:** If this standard is violated, generation HALTS. No exceptions. No project gets special treatment.

---

## 1. PROJECT INITIALIZATION CHECKLIST

Every new project MUST satisfy ALL items before the first frame is generated. Run in this order.

### 1A. Required Files

| File | Location | Required Fields |
|------|----------|-----------------|
| `shot_plan.json` | `pipeline_outputs/{project}/shot_plan.json` | `shot_id`, `shot_type`, `characters[]`, `description`, `scene_id`, `duration` |
| `story_bible.json` | `pipeline_outputs/{project}/story_bible.json` | `scenes[]`, `locations[]`, `characters[]`, `cinematography_style` |
| `cast_map.json` | `pipeline_outputs/{project}/cast_map.json` | `appearance`, `amplified_appearance`, `character_reference_url` per character |

Missing any file = HALT. Missing any required field = WARN (blocking in future versions).

### 1B. Location Masters

Every unique location in `story_bible.json` MUST have:
- At minimum: 1 wide master (`{location_key}_master.jpg`)
- For scenes with OTS dialogue: reverse angle (`{location_key}_reverse_angle.jpg`) — MANDATORY
- Production ready: `_medium_interior.jpg` variant as well

Location masters live in `pipeline_outputs/{project}/location_masters/`.

Generate location masters via:
```bash
POST /api/v27/create-location-refs
{"project": "{project}"}
```

### 1C. Beat Enrichment

Run ONCE after story bible is generated. Writes permanent truth fields onto every shot.

```bash
python3 tools/beat_enrichment.py {project}
```

Confirms by setting `_beat_enriched: true` on each shot. Populates:
- `_beat_ref` — which story beat this shot serves
- `_beat_action` — the character VERB (walk, confront, discover — not "stands in")
- `_beat_dialogue` — dialogue text pulled from story bible
- `_beat_atmosphere` — emotional atmosphere for this beat
- `_body_direction` — specific body action from CPC EMOTION_PHYSICAL_MAP
- `_eye_line_target` — where the character looks (derived from beat action)
- `_cut_motivation` — WHY the camera cuts here

Do NOT re-run unless story bible changes. Check `_beat_enriched: true` first.

### 1D. Prep Engine Preflight

```bash
python3 prep_engine.py preflight {project}
```

Must exit with **0 HALTs**. Warnings are acceptable. Fix HALTs before proceeding.

Common HALT causes and fixes:
- `character_refs missing` → regenerate cast via `/api/v6/casting/auto-cast`
- `ltx_prompts_present` (contamination) → run `python3 tools/post_fixv16_sanitizer.py {project}`
- `scene_contract missing` → run scene truth compiler on affected scenes

### 1E. Session Enforcer

```bash
python3 tools/session_enforcer.py
```

Must report **✅ SYSTEM HEALTHY** (0 blocking issues). This verifies:
- 31 checks including model routing, generation gate, doctrine hooks
- All 17 systems importable
- CLAUDE.md doctrine present and intact
- No regressions in the learning log

**Do not touch any generation endpoint until session_enforcer passes.**

### 1F. Environment Variables

Verify `.env` contains all required keys before any run:

```
FAL_KEY=...
MUAPI_KEY=...
OPENROUTER_API_KEY=...
GOOGLE_API_KEY=...
REPLICATE_API_TOKEN=...
ELEVENLABS_API_KEY=...
```

FAL_KEY and GOOGLE_API_KEY MUST be loaded BEFORE vision_judge import (runner lines 75–88).

---

## 2. PROMPT STANDARD

### 2A. nano_prompt Field

- `nano_prompt` is **OPTIONAL** in shot_plan.json
- If empty/absent, `prep_engine` auto-populates from `_beat_action` + shot fields at runtime
- Never block generation because nano_prompt is missing — this is a WARN, not a HALT (V30.1)

### 2B. compile_nano() — 4 Cinematic Channels (Always Applied)

Regardless of nano_prompt source, Film Engine's `compile_nano()` applies all 4 channels:

| Channel | Block | Content |
|---------|-------|---------|
| Identity | `[CHARACTER: ...]` | Amplified appearance from cast_map — LOUDER distinctive features |
| Environment | `[ROOM DNA: ...]` | Immutable room architecture (8 templates in scene_visual_dna.py) |
| Aesthetic | `[AESTHETIC: ...]` | Anti-CGI constraints + color science |
| Performance | `[PERFORMANCE: ...]` | Truth fields translated to body/eye-line direction |

### 2C. Character Woven Into Room — NOT Separate Blocks

Character is described within the room context, not as isolated blocks:

```
# WRONG (stacked blocks — causes spatial drift)
[CHARACTER: tall silver-haired man in navy suit]
[ROOM DNA: curved mahogany staircase, dark paneling]

# CORRECT (character woven into environment)
[CHARACTER: tall silver-haired man in navy suit standing at the base of the curved
mahogany staircase, dark wood paneling behind him]
```

### 2D. Beat Action = Character VERB

`_beat_action` is a SPECIFIC VERB, not a state:

```
# WRONG
"stands in the library"
"is present"
"experiences the moment"

# CORRECT
"confronts"
"reaches for"
"turns sharply away from"
"discovers"
"presses against"
```

CPC `EMOTION_PHYSICAL_MAP` enforces this. If generic verb detected, `decontaminate_prompt()` replaces it.

### 2E. Anti-CGI Aesthetic Block (MANDATORY for ALL shots)

Every nano_prompt MUST include in `[AESTHETIC:]`:

```
NO CGI, NO airbrushed skin, NO digital artifact, NO plastic sheen.
Realistic skin texture with pores and micro-imperfections.
Film grain: {genre_grain}. Color science: {color_science}.
```

Genre-specific values from `scene_visual_dna.py`:
- Gothic horror: heavy grain, cool desaturated shadows, warm amber practical lights
- Drama: medium grain, warm natural tones, motivated lighting
- Action: minimal grain, high contrast, punchy colors

### 2F. Shot Type → Behavioral Camera Language

Do NOT use lens specs alone. Describe the VISUAL EFFECT:

| Shot Type | Camera Language |
|-----------|----------------|
| `establishing` | "Full room geography visible, deep depth of field, all architectural features sharp" |
| `wide` | "Full figure visible, room context dominant, characters secondary to environment" |
| `medium` | "Waist-up visible, room atmospheric behind, balanced composition" |
| `medium_close` | "Head and shoulders fill frame, background soft with vague shapes" |
| `close_up` | "Face fills 80% of frame, background compressed flat and completely blurred" |
| `extreme_close_up` | "Single feature (eyes / hands / object) dominates, extreme shallow DOF" |
| `ots` | See T2-FE-14 / T2-FE-17 for full OTS framing rules |
| `reaction` | "Tight on face, micro-expression visible, specific movement choreography required" |

Numeric focal lengths (85mm, 50mm) are SECONDARY and should follow behavioral description, never replace it.

### 2G. Location Proper Names — STRIP BEFORE FAL

Strip ALL location proper names before any prompt reaches FAL:

```
"HARGROVE ESTATE" → "the estate"
"RAVENCROFT MANOR" → "the manor"
"BLACKWOOD LIBRARY" → "the library"
```

`strip_location_names()` in `prompt_identity_injector.py` handles this automatically.
FAL interprets capitalized proper nouns as text overlay instructions — they appear burned into frames.

---

## 3. GENERATION STANDARD

### 3A. Frame Generation

```
MAX_PARALLEL = 4  (never higher — FAL rate limits)
Model (with refs)  = fal-ai/nano-banana-pro/edit
Model (no refs)    = fal-ai/nano-banana-pro
Output dir         = pipeline_outputs/{project}/first_frames/
Naming             = {shot_id}.jpg  (NO _lite, NO _full, NO _v2 suffixes)
```

**CRITICAL naming rule:** First frames are ALWAYS `first_frames/{shot_id}.jpg`. Never create variant directories. One canonical output.

### 3B. Image Reference Slot Ordering

```
@image1 = start_frame (for /edit model) OR omitted (for T2I)
@image2 = character headshot (highest attention)
@image3 = three_quarter ref (for hero shots: close_up, MCU, OTS)
@image4 = location master (lowest priority)
```

Never put location master at @image2 or @image3. Character identity always wins slots 2+3.

### 3C. Hero vs. Production vs. B-Roll Classification

| Shot Type | Class | Refs | Resolution |
|-----------|-------|------|------------|
| `close_up`, `extreme_close_up`, dialogue MCU | HERO | headshot + three_quarter + location | 2K |
| `medium`, `ots`, `two_shot`, `reaction` | PRODUCTION | headshot + location | 1K |
| `establishing`, `wide`, `b_roll`, `insert` | B-ROLL / ESTABLISHING | no char ref + location | 1K |

Dialogue shots always get +1K resolution boost regardless of class (T2-SA-4).

### 3D. Vision Scoring (Post-Frame)

After every frame generation:
1. Gemini Vision 2.5 Flash scores identity (GOOGLE_API_KEY must be loaded BEFORE import)
2. Circuit breaker: 3 consecutive all-zero results → trip → fall to legacy chain
3. Legacy chain: claude_haiku → openrouter → florence_fal → heuristic (0.75)
4. Identity threshold: I < 0.55 → REGEN (Wire A), I ≥ 0.55 → PASS

Wire A budget: **max 2 regens per scene** (`_WIRE_A_MAX_REGENS_PER_SCENE = 2`).
If budget exhausted: flag for review, do NOT retry endlessly.

### 3E. _approval_status Field

All frames-only runs (`--frames-only`) MUST set on every shot:
```json
"_approval_status": "AWAITING_APPROVAL"
```

This field gates video generation. Never auto-approve. Human review is mandatory.

---

## 4. APPROVAL GATE

The approval gate is the quality checkpoint between frames and videos.
**This is a human step. It cannot be automated.**

### 4A. Approval Actions

| Action | Sets Field | Effect |
|--------|-----------|--------|
| Thumbs up | `_approval_status: "APPROVED"` | Shot eligible for video generation |
| Thumbs down | `_approval_status: "REGEN_REQUESTED"` | Archives old frame, regens with identity boost |

### 4B. Regen on Rejection

When `REGEN_REQUESTED`:
1. Archive existing frame to `_archived_runs/{timestamp}/{shot_id}.jpg`
2. Identity boost: add `AMPLIFICATION_MAP` upgrades to all character descriptors
3. Resolution escalation: 1K → 2K, 2K → 4K
4. Regenerate via same model path (no model change)
5. Set `_approval_status: "AWAITING_APPROVAL"` again — human must re-review

### 4C. --videos-only Behavior

`--videos-only` mode ONLY processes shots where `_approval_status == "APPROVED"`.
Shots with `AWAITING_APPROVAL`, `REGEN_REQUESTED`, or missing `_approval_status` are silently skipped.

Never bypass this. Running videos on unapproved frames wastes Seedance quota on bad identity.

### 4D. Stale Artifact Rule

Before any generation run, archive stale artifacts:
```bash
python3 tools/pre_run_gate.py {project} {scene_id}
```

The UI must ALWAYS show current-run results only. Old frames in `first_frames/` are NOT "generated" — they are artifacts from a previous run.

---

## 5. VIDEO STANDARD

### 5A. Model Routing

```
Primary:  Seedance V2.0 via muapi.ai  (MUAPI_KEY)
Fallback: fal-ai/kling-video/v3/pro/image-to-video  (character-heavy scenes)
RETIRED:  fal-ai/ltx-2/image-to-video/fast  ← DO NOT USE. Raises RuntimeError.
```

Kling fallback triggers when Seedance quota is exhausted or on explicit `--model kling` flag.

### 5B. End-Frame Chaining (MANDATORY)

```
Shot N   → generate video → extract last frame → save as {shot_id}_end_frame.jpg
Shot N+1 → last frame of Shot N = @image1 (start_image)
```

This forces spatial and character continuity across cuts. Scenes without chaining show teleportation artifacts.

Execution: sequential within scene, parallel across scenes.

### 5C. Seedance images_list Slot Ordering

```python
images_list = [
    start_frame_url,     # @image1 — end frame from previous shot (or first_frame for shot 1)
    char1_ref_url,       # @image2 — primary character headshot (HIGHEST attention)
    char2_ref_url,       # @image3 — three_quarter ref or second character
    location_master_url  # @image4 — room architecture (lowest priority)
]
```

Never put location at slot 2. Never exceed 4 images in list.

Role assignment string (required by Seedance V2.0):
```
"@image2 and @image3 define character faces and clothing. @image4 shows the room architecture."
```

### 5D. Wire B — FAIL/FROZEN Block

Wire B (runner:2819) blocks shots with `V_score = 0` or `_generation_status = "FAILED"` from stitch.

If a shot is blocked by Wire B:
1. Review the shot in UI
2. Manual retry via `/api/auto/render-videos` with `{"shot_ids": ["{shot_id}"]}`
3. If still blocked: mark as `_editorial_skip_gen: true` and bridge with B-roll

Never stitch a film with Wire B blocks unresolved — the timeline will have silent gaps.

### 5E. Wire C — Frozen Video Detection

Wire C (runner:2614) detects frozen video by sampling frame difference across the clip.
If `V_score = 0.0` (completely frozen):
1. Retry with motion-boost prompt prefix: `"Dynamic movement, continuous action, NO freeze frames. {original_prompt}"`
2. One retry only
3. If still frozen: flag `_frozen_video: true`, exclude from stitch

V-score states:
- `0.0` = completely frozen (Wire C triggers)
- `0.3` = minimal motion (borderline — log, don't block)
- `0.5` = moderate motion (acceptable)
- `0.85` = strong motion (target)

---

## 6. VISION STANDARD

### 6A. Gemini Vision 2.5 Flash — Primary Scorer

Gemini Vision is the exclusive scorer when `GOOGLE_API_KEY` is set.

```python
# vision_judge.py exclusive-mode guard (V30.3)
if _GEMINI_IS_EXCLUSIVE and gemini_available and not _GEMINI_TRIPPED:
    # Use Gemini
```

**Critical:** `GOOGLE_API_KEY` MUST be loaded from `.env` BEFORE `vision_judge` is imported.
This is handled in `atlas_universal_runner.py` lines 75–88. If running orchestrator path, env is loaded early. Both paths now consistent.

### 6B. Identity Scoring Thresholds

| I-score | Action |
|---------|--------|
| < 0.55 | REGEN (Wire A) |
| 0.55 – 0.69 | FLAG for operator review |
| ≥ 0.70 | PASS |
| = 0.75 flat | SUSPECT — heuristic fired (Gemini wasn't available) |

If you see `I = 0.75` on every shot, Gemini is not running. Check GOOGLE_API_KEY is loaded before import.

### 6C. Circuit Breaker Behavior

```
3 consecutive all-zero identity scores → _GEMINI_TRIPPED = True
→ Print: "[VISION] ⚡ CIRCUIT BREAKER TRIPPED"
→ Fall to: claude_haiku → openrouter → florence_fal → heuristic
→ Non-zero result resets counter and clears trip
```

Circuit breaker does NOT return FAIL scores and does NOT block generation — it degrades gracefully.

### 6D. Semantic Embedding Filter (V30.2)

Florence-2 captions are scored against expected content via Gemini Embedding semantic similarity, not keyword regex. This catches:
- "a man with grey hair" matching "silver-haired gentleman" (semantic match, literal mismatch)
- "someone in dark clothing" NOT matching "navy suit" (semantic mismatch caught)

Threshold: semantic similarity > 0.72 = PASS, < 0.72 = flagged.

### 6E. What Vision Does NOT Check (Roadmap)

Vision currently checks IDENTITY only. It does NOT verify:
- Beat action matching (did character do what `_beat_action` says?)
- Spatial positioning (did 180° rule hold?)
- Prop presence (is the letter/knife/ring in the shot?)

These are roadmap items (action verification, prop tracking). Do not assume they are enforced.

---

## 7. SELF-HEALING (ECC — Error-Correcting Code)

The ATLAS ECC system runs three scheduled maintenance tasks. These run independently of production sessions.

### 7A. keep-up (Hourly)

**Purpose:** Detect and classify issues before they become blockers.

```bash
# Scheduled via cron or scheduled-tasks MCP
python3 tools/keepup.py --mode detect
```

Detection categories:
- `PHANTOM_P0` — issue already fixed, re-reported as new
- `REAL_P0` — genuine blocking issue requiring action
- `REGRESSION` — previously fixed issue re-broken

Output goes to `tools/keepup_report_{timestamp}.json`. Review before acting.

### 7B. atlas-proof-gate (Every 4 Hours)

**Purpose:** Verify reported fixes are actually wired and working before any developer action.

```bash
python3 tools/session_enforcer.py  # The authoritative gate
```

The 4-gate protocol (for any new fix):
1. `G1 SYNTAX` — `python3 -c "import ast; ast.parse(open('file.py').read()); print('OK')"`
2. `G2 IMPORT` — module imports without crash
3. `G3 WIRED` — session_enforcer passes all checks
4. `G4 PROVEN` — live generation confirms output changed

Never declare a fix DONE without reaching G4 for production changes, G3 minimum for wiring.

### 7C. atlas-doctrine-sync (Daily)

**Purpose:** Audit CLAUDE.md for accuracy against current codebase state.

Checks:
- Line numbers referenced in CLAUDE.md still contain the described code
- Model lock constants match what's actually in runner/orchestrator
- Wire A/B/C triggers are at the stated line numbers
- No phantom P0s in the "ACTUAL P0s" section

If drift detected: update CLAUDE.md (doc sync pass). Tag updates as `R{N} keepup applied`.

### 7D. Filesystem Access Requirement

All scheduled tasks require read/write access to:
- `~/Desktop/ATLAS_CONTROL_SYSTEM/` — all project files
- `~/Desktop/ATLAS_CONTROL_SYSTEM/tools/` — all tool scripts
- `~/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/` — project data

Ensure these paths are pre-approved in task scheduler permissions before scheduling.

---

## 8. INFRASTRUCTURE

### 8A. Server

```bash
# Start server
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
python3 orchestrator_server.py
# Runs on port 9999
```

After any code change:
```bash
# Clear Python import cache FIRST
find . -name "__pycache__" -type d -exec rm -rf {} +
# Then restart
python3 orchestrator_server.py
```

### 8B. Cloudflare Tunnel

```bash
# Named tunnel "atlas" → atlas.fanztv.com
cloudflared tunnel run atlas
```

Tunnel routes all orchestrator traffic. Running locally means the tunnel must be active for any remote access.

**Known bottleneck:** Image serving through tunnel is slow for large batches. Images should be served via R2 CDN directly (see Roadmap 9A).

### 8C. Glob Patterns in Python — CRITICAL

When using glob patterns in Python scripts:

```python
# CORRECT — per-extension globs
import glob
jpg_files = glob.glob("first_frames/*.jpg")
png_files = glob.glob("first_frames/*.png")
files = jpg_files + png_files

# WRONG — bash brace expansion does NOT work in Python glob
files = glob.glob("first_frames/*.{jpg,png}")  # Returns EMPTY on macOS
```

This has caused silent failures in batch processing. Always use separate globs per extension.

### 8D. Project Directory Layout (Canonical)

```
pipeline_outputs/{project}/
├── shot_plan.json                  ← EXECUTION TRUTH (bare list OR dict with "shots" key)
├── story_bible.json                ← Narrative with beats
├── cast_map.json                   ← Character → actor mapping
├── wardrobe.json                   ← Look IDs + appearance
├── extras.json                     ← Crowd pack assignments
├── first_frames/                   ← Generated frames — {shot_id}.jpg ONLY
├── videos/                         ← Generated videos — {shot_id}.mp4
├── location_masters/               ← Location ref images
├── scene_contracts/                ← Scene truth contracts
├── ui_cache/bundle.json            ← Cached UI bundle
├── _archived_runs/                 ← Stale artifacts (timestamped subdirs, NEVER delete)
└── .vision_cache/                  ← SHA256-keyed vision embeddings
```

**shot_plan.json format guard (ALL consumers):**
```python
sp = json.load(f)
if isinstance(sp, list):
    sp = {"shots": sp}
shots = sp["shots"]
```

### 8E. R2 Permanent URLs for Chained Reframes

When generating angle variants or reframes that will be chained:
1. Upload master frame to R2 bucket ONCE
2. Use permanent R2 URL for ALL downstream references
3. Never use `fal.media` temporary URLs in chains — they expire in ~2 hours

R2 bucket: `026089839555deec85ae1cfc77648038`

---

## 9. ROADMAP (Post First Production Run)

These items are confirmed architectural improvements. Do not implement before first V30.x run validates the current architecture.

### 9A. R2 CDN for Image Serving (HIGH PRIORITY)

**Problem:** All images currently serve through cloudflared tunnel → bandwidth bottleneck on batch filmstrip loads.
**Solution:** Generate R2 signed URLs for direct image access, bypassing tunnel for media.
**Impact:** 10x faster filmstrip loading for scenes with 12+ shots.

### 9B. Cross-Shot Continuity via Gemini Embedding 2

**File:** `tools/cross_shot_memory.py` (to be built)
**Purpose:** Track character spatial position, prop state, wardrobe state across shots using semantic embeddings.
**Current C-score:** Binary structural (0.85 if chain file exists, 0.70 otherwise) — not real continuity.
**Target:** SSIM-level continuity scoring across adjacent shots.

### 9C. Action Verification in Vision Judge

**Problem:** Vision currently only checks identity. Beat action is never verified (did character actually do `_beat_action`?).
**Solution:** Second Gemini Vision call on each frame with action-specific prompt:
- `"Does this image show a person {_beat_action}? Yes/No and confidence."`
**Gate:** Action score < 0.5 → flag for review (not block — advisory in v1).

### 9D. Firebase Realtime for Live Filmstrip Updates

**Problem:** UI filmstrip only refreshes on manual reload or bundle.dirty poll.
**Solution:** Firebase Realtime Database push on every frame/video write → filmstrip auto-updates.
**Impact:** Removes need for manual page refresh during long generation runs.

### 9E. Filmstrip Grid Drag-to-Shot Reorder

Allow drag-and-drop reordering of shots in filmstrip grid. Writes new `shot_order` field to shot_plan without changing `shot_id` values. Stitch respects `shot_order`.

### 9F. Easy Download Buttons

Per-shot download (JPG, MP4) and per-scene download (stitched MP4, ZIP of frames) via `/api/v30/download/{project}/{shot_id}`.

### 9G. Full Auto-Scene After Validation

After human validates all frames in a scene, a single "Approve All & Generate Videos" button triggers `--videos-only` for all APPROVED shots in that scene. Currently requires manual CLI invocation.

---

## APPENDIX A: QUICK REFERENCE COMMANDS

```bash
# Full pipeline for a new project
POST /api/v6/script/full-import
POST /api/auto/generate-story-bible
POST /api/shot-plan/fix-v16
python3 tools/post_fixv16_sanitizer.py {project}
POST /api/v6/casting/auto-cast
python3 tools/beat_enrichment.py {project}
POST /api/v21/audit/{project}
python3 prep_engine.py preflight {project}
python3 tools/session_enforcer.py

# Generate frames (review gate)
python3 atlas_universal_runner.py {project} 001 --mode lite --frames-only

# Review in UI, approve/reject

# Generate videos (after review)
python3 atlas_universal_runner.py {project} 001 --mode lite --videos-only

# Full multi-scene run (after ALL scenes validated)
python3 atlas_universal_runner.py {project} 001 002 003 --mode lite --videos-only
```

## APPENDIX B: COST BENCHMARKS (V29.16 Production Data)

| Stage | Cost | Time | Notes |
|-------|------|------|-------|
| Frame generation (per scene, 3-4 shots) | ~$0.30 | 2-3 min | nano-banana-pro/edit at 2K |
| Video generation (per scene, Seedance) | ~$0.81 | 8 min | 3-4 shots × ~10s each |
| Video generation (per scene, Kling) | ~$7.50 | 8 min | fallback only |
| Full scene (frames + videos) | ~$1.11 | 10-11 min | target cost per scene |

Historical comparison:
- LTX era: $3.60/scene, frozen statues (WASTED — never use LTX)
- Kling sequential: $30/scene, 48 min (too expensive for production)
- V29.16 Seedance: $0.81/scene, 8 min (CURRENT TARGET)

## APPENDIX C: IDENTITY CONTROL HIERARCHY

Ranked by actual influence on FAL output (proven by 20-shot strategic test):

1. **Text description in prompt** (STRONGEST) — FAL generates directly from this
2. **Character ref image** (`@image2`) — supports text, doesn't replace it
3. **Three-quarter ref** (`@image3`) — additional angle reinforcement for hero shots
4. **Location ref image** (`@image4`) — environment context only
5. **Scene DNA text** (`[ROOM DNA:]`) — architecture lock
6. **Camera/lens numbers** (WEAKEST) — FAL mostly ignores numeric focal lengths

Implication: a shot with no character description in nano_prompt will produce a RANDOM PERSON even with the correct ref image attached. Identity injection is mandatory on all character shots.

---

*PRODUCTION_STANDARD.md — Universal for all ATLAS projects.*
*Last updated: 2026-03-23. Update this file when pipeline architecture changes.*
*Questions? Check CLAUDE.md Section 2 (Organ Laws) for module-specific detail.*
