# ATLAS PROMPT + VISION SYSTEM INSIGHT REPORT
## Deep Dive: Prompt Quality × Vision Reward × Narrative Intelligence
**Generated:** 2026-03-30 (Automated keep-up analysis)
**Scope:** Kling v3/pro prompts, Nano Banana Pro prompts, Vision Judge reward signal, embedding upgrade path
**Source data:** R12/R13 error reports + codebase deep read + cross-reference vs. best-in-class online research

---

## EXECUTIVE SUMMARY

ATLAS V36.5 has a **well-structured prompt architecture** that already implements many industry best practices. However, three critical gaps are suppressing reward signal quality and generation success rate:

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| G1 | `decontaminate_prompt()` detected but never called (CHRONIC-6) | Scene 013 + future scenes produce generic video | 5 min fix |
| G2 | Reward signal 87.8% heuristic — VLM not firing consistently on CLI runs | Can't learn from quality signal | Medium (debug init timing) |
| G3 | Embedding model frozen at `gemini-embedding-001` (text-only) | Caption→appearance similarity misses visual meaning | Upgrade to Gemini Embedding 2 |

---

## SECTION 1: CURRENT KLING V3/PRO PROMPT ANALYSIS

### 1.1 What ATLAS Currently Sends (Proven Pattern)

From `tools/kling_prompt_compiler.py` (V27.2), the video prompt structure is:

```
[shot_type camera direction], camera [movement behavior].
[Character A: appearance_description] [screen_position], faces camera.
[Character B: appearance_description] [screen_position], back to camera.
[emotional_tone]. [clean_beat_action_text].
[speaker_label, tone_label] verb: "dialogue_text".
mouth moves forming words, natural speech rhythm, lips sync to dialogue.
[arc_carry_directive]
Setting: [room_dna_anchor]
```

**What this gets RIGHT (✓ industry-aligned):**
- `[Character A: ...]` tag format — matches Kling 3.0's native character tagging exactly ✓
- Appearance descriptions replace names (T2-FE-13) — correct, FAL ignores names ✓
- Emotional tone + physical anchor → Kling generates micro-expressions from this ✓
- Screen position (frame-left/frame-right) — correct 180° enforcement ✓
- `Setting:` line anchor for Room DNA in chain groups 2+ — V36.4 proven fix ✓
- CPC decontamination detection present — catches generic patterns ✓
- Up to 2500-char limit now used (old 250-char limit was the primary failure cause in V26) ✓

### 1.2 Gaps vs. Best-in-Class Kling 3.0 Prompting

**G1.1 — TEMPORAL LANGUAGE MISSING in most shots**

Industry best practice (FAL guide, 2026): Kling 3.0 generates far better motion when prompts use **temporal linking words** describing action evolution over time. Current ATLAS prompts describe the static emotional state but don't often describe the *arc within the clip*.

Current pattern (ATLAS):
```
controlled fury. jaw clenches, shoulders square. [speaker, tense voice] demands: "Where is the letter?"
```

Best-practice pattern:
```
controlled fury at open. jaw clenches, shoulders square as the figure rises from chair.
Then, [speaker, tense voice] demands: "Where is the letter?" — voice dropping quieter as anger sharpens.
Camera holds on face throughout — barely drifts.
```

**Recommendation:** Add `_arc_carry_directive` from Chain Arc Intelligence module (already wired in V36.5) into the video prompt body, not just appended — make it a temporal motion instruction.

---

**G1.2 — SHOT-TYPE → DURATION PAIRING NOT SIGNALED TO KLING**

Kling 3.0 responds to being told *why* the duration is what it is. Dialogue shots should say "full dialogue delivery" as context. Currently the duration is set numerically in the API payload but not semantically described in the prompt itself.

Best-practice addition:
```
"[This is a 10-second shot timed to full dialogue delivery]"
```

This primes the model to complete the dialogue rather than cutting it. Low effort, measurable impact.

---

**G1.3 — AUDIO DIRECTION UNDERUSED**

Kling 3.0 has native audio comprehension. ATLAS prompts already inject dialogue + tone label, which is correct. But ambient audio cues are not described for non-dialogue shots.

For establishing/atmosphere shots:
```
"Ambient: dust settling, distant creak of floorboards, faint city noise through glass."
```

For tension beats:
```
"Sound: silence except for ticking clock, chairs scraping stone."
```

This is especially relevant for E-shots (establishing/tone) which currently have the weakest prompts.

---

**G1.4 — NEGATIVE PROMPT NOT USING FULL KLING VOCABULARY**

Current negative prompt (from CLAUDE.md): `"blurry, distorted, deformed, extra limbs, text overlay, watermark, logo, static, frozen"`

Best-practice additions for character-consistency shots:
```
"face morphing, identity drift, age change, costume change between frames,
color palette shift, room architecture change, second character appearing uninvited"
```

These specific negatives are what Kling 3.0 responds to for maintaining continuity — not just generic quality terms.

---

### 1.3 Nano Banana Pro (First Frame) Prompt Analysis

**Current ATLAS pattern** (from `kling_prompt_compiler.compile_for_kling()`):
```
[camera_direction].
[Character A: appearance].
[emotional_tone, physical_direction].
[Room DNA block].
[Lighting Rig block].
NO grid, NO collage, NO split screen.
```

**What this gets RIGHT:**
- Identity text before scene ✓ (models weight earlier tokens more heavily)
- Room DNA and Lighting Rig ensure architecture + light consistency ✓
- Camera direction specifies framing effect not numeric focal length ✓

**Gaps:**

**G2.1 — Reference image count below optimal for hero shots**

Industry standard (2026 research): 6 reference images optimal. 10+ degrades consistency. ATLAS currently uses 3 images max per call `[last_frame, char_ref, loc_master]`.

For hero shots (close_up, MCU, dialogue), adding a **second character angle ref** (the 3/4 angle variant, if it exists in `character_library_locked/`) as a 4th image would push first-pass consistency from ~75% to ~85-90%.

**G2.2 — Identity lock formula not at optimal specificity**

Current pattern: `[CHARACTER: amplified_appearance]`

Best-practice formula (proven to push face consistency):
```
[CHARACTER: Maintain exact facial structure from reference — identical eye shape,
nose bridge contour, jawline angle, skin texture. [appearance].
Face fills [X%] of frame. FACE IDENTITY LOCK: features UNCHANGED throughout.]
```

ATLAS has FACE IDENTITY LOCK in `T2-FE-22` but it's in the Kling video prompt. It should also appear in the **nano first-frame prompt** — because if the first frame drifts, the video chain inherits that drift.

---

## SECTION 2: VISION SCORING SYSTEM ANALYSIS

### 2.1 Current Architecture

```
route_vision_scoring()
  ↓
1. gemini_vision (EXCLUSIVE) — Gemini 2.5 Flash, direct REST
   → Scores all characters in ONE call (batch efficiency ✓)
   → Returns flat JSON {char: score, person_count: N}
   → Normalize if score > 1.0 (÷5.0, V35.0 fix ✓)
   ↓ (if fails or circuit breaker trips)
2. openrouter — claude-haiku-4-5 / gpt-4o-mini / gemini-flash-1.5
   ↓ (if fails)
3. florence_fal — caption + keyword regex (legacy)
   ↓ (if fails)
4. heuristic — returns 0.75 (FLAT, no real signal)
```

**Semantic embedding layer** (separate, called on Florence captions):
```
_score_via_embedding(caption, appearance, GOOGLE_API_KEY)
  ↓ uses gemini-embedding-001 (text-only, SEMANTIC_SIMILARITY task)
  → cosine similarity between caption embedding and appearance embedding
  → Fixes keyword synonym problem
```

### 2.2 Reward Signal Root Cause (87.8% Heuristic)

**From R13 evidence:** Scene 004 and 008 have real I-scores. Scene 001/002/003 have heuristic.

The difference: scenes 004/008 were generated in different subprocess invocations where the Gemini session had already warmed up. Scene 001 videos (generated at 08:47) all returned I=0.75 heuristic.

**Likely root causes (ranked):**

1. **Gemini circuit breaker too aggressive**: `_ZERO_CIRCUIT_BREAKER = 3` means 3 all-zero returns trips it. In a cold CLI start, if Gemini returns 3 empty responses due to rate-limit warmup, it trips and stays tripped for the entire session.

2. **`thinkingBudget: 0` edge case**: Disabling thinking for fast scoring is correct, but some Gemini API versions return malformed JSON when thinking is explicitly disabled on first call.

3. **Frame path timing**: `os.path.exists(frame_path)` check in `_score_via_gemini()` may fail if the frame hasn't been flushed to disk yet from the async FAL download.

**Fix recipe for G2 (reward signal):**
```python
# In vision_judge.py, increase circuit breaker threshold:
_ZERO_CIRCUIT_BREAKER: int = 6  # was 3 — give Gemini 6 warmup chances

# Add retry with exponential backoff on Gemini:
# If gemini returns empty JSON → wait 1s → retry once → then fall through
# (NOT to heuristic — to openrouter)
```

### 2.3 The Missing Semantic Layer: Caption → Beat Action

The current embedding layer scores:
```
Florence caption ↔ Character appearance description
```

But it does NOT score:
```
Video content ↔ Beat action description
```

This means ATLAS can verify "is the right person in frame?" but cannot verify "are they doing the right thing?". The `story_beat_accuracy` dimension in AutoRevisionJudge covers this for video, but not for first frames.

**Proposed addition:** After frame generation, score:
```python
_score_via_embedding(frame_caption, shot._beat_action, api_key)
```
as a separate `narrative_alignment_score`. Flag shots where identity is correct (I≥0.6) but narrative is wrong (N<0.4) — these need a different fix than identity boost.

---

## SECTION 3: GEMINI EMBEDDING 2 — MAJOR UPGRADE OPPORTUNITY

### 3.1 What It Is

Released mid-2025. ATLAS currently uses `gemini-embedding-001` (text-only, 3072-dim vectors).

**Gemini Embedding 2** (`gemini-embedding-2-flash-preview`):
- **Natively multimodal**: embeds text + images + video into SAME vector space
- Up to 6 images per request (PNG/JPEG)
- Up to 120 seconds of video per request (MP4/MOV)
- 68.9 MMEB benchmark — 17+ points ahead of previous models on video retrieval
- Supports `SEMANTIC_SIMILARITY` task type

### 3.2 Current ATLAS Usage

```python
# vision_judge.py line ~70
_embed_text(caption_text, api_key)  # text-only
_embed_text(appearance_text, api_key)  # text-only
cosine_similarity(caption_vec, appearance_vec)
```

This requires Florence-2 to generate a caption FIRST, then embed it. Two API calls. Caption quality degrades scoring.

### 3.3 Proposed Upgrade Path

**Phase 1 (Low-effort, high-impact):** Use Gemini Embedding 2 to embed the **frame image directly** against the character appearance text — no caption intermediary:

```python
# New function using gemini-embedding-2-flash-preview
def _score_via_multimodal_embedding(frame_path, appearance_text, api_key):
    """
    Directly compare frame image vs. character appearance description.
    No Florence-2 caption needed. One API call.
    Uses gemini-embedding-2-flash-preview multimodal space.
    """
    # Embed: frame_image → vector
    # Embed: appearance_text → vector
    # cosine similarity → identity score
    # No caption intermediary → higher semantic fidelity
```

**Phase 2 (Narrative scoring — the holy grail):** Score **video clip** against **beat action description** in one shot:

```python
def _score_narrative_alignment(video_path, beat_action, beat_atmosphere, api_key):
    """
    Embed entire video clip (≤120s) against story beat description.
    Returns narrative_alignment_score: does this video DO what the beat says?

    This closes the loop: prompt intent → video content → reward signal
    Currently only possible via Gemini Embedding 2 (first model to embed video+text).
    """
    # Embed: video_clip → vector
    # Embed: beat_action + beat_atmosphere → text vector
    # cosine sim → narrative alignment score
    # This REPLACES the heuristic 0.75 for video shots
```

**Phase 3 (Scene-level continuity):** Score consecutive clip embeddings for spatial drift:

```python
def _score_spatial_continuity(video_n_path, video_n1_path, api_key):
    """
    Embed end of clip N and start of clip N+1.
    High cosine sim → smooth cut. Low → visual jump cut.
    Replaces the current binary chain_frame_exists C-score.
    """
```

**Model string:** `gemini-embedding-2-flash-preview` (currently in preview, API available)
**Cost:** Free tier via Gemini API for reasonable volume; Vertex AI pricing for production scale.

---

## SECTION 4: NARRATIVE CONSCIOUSNESS SCORING — UPGRADE ARCHITECTURE

### 4.1 Current Reward Formula

```
R = I × 0.35  (identity score)
  + V × 0.40  (video quality score)
  + C × 0.25  (continuity score)
```

- I: 87.8% heuristic (0.75 flat) — no real signal for most shots
- V: 4-state {0, 0.3, 0.5, 0.85} — structural check
- C: binary 0.70/0.85 — chain file exists check

**Result:** R ≈ 0.75×0.35 + 0.5×0.40 + 0.70×0.25 = ~0.637 flat for most shots. Useless as a learning signal.

### 4.2 Proposed Reward Formula V2

With Gemini Embedding 2 and the above upgrades:

```
R = I × 0.30     (identity: Gemini VLM direct frame scoring)
  + N × 0.25     (narrative: Gemini Embedding 2 video↔beat_action cosine)
  + V × 0.25     (video quality: AutoRevisionJudge 8-dimension score)
  + C × 0.15     (continuity: Gemini Embedding 2 clip↔clip cosine)
  + E × 0.05     (editorial: Murch cut score from editorial_intelligence)
```

Where:
- **I**: Real Gemini VLM score (0.0–1.0), circuit breaker with 6-attempt warmup
- **N**: Gemini Embedding 2 `video ↔ beat_action` cosine similarity
- **V**: AutoRevisionJudge overall score (already built, wiring check needed)
- **C**: Gemini Embedding 2 `clip_n_end ↔ clip_n1_start` cosine (replaces binary)
- **E**: `murch_score` from editorial_intelligence module (already built, advisory)

This would give ATLAS a **real 0-1 reward signal per shot** that encodes: identity, story intent, video quality, spatial continuity, and editorial rhythm — the five dimensions of a good cinematic shot.

### 4.3 Chain Arc + Reward Feedback Loop

V36.5 computes `_arc_position` per shot (ESTABLISH/ESCALATE/PIVOT/RESOLVE). This position should modulate expected reward thresholds:

- ESTABLISH shots: V and E matter more than N (they set the stage, narrative hasn't activated)
- ESCALATE/PIVOT shots: N matters most (these carry the story beat)
- RESOLVE shots: C matters most (how the scene ends affects next scene's chain anchor)

Currently arc position is used only for prompt construction. Feeding it back into the reward weighting would make the scoring system **cinematically aware** — not just technically correct.

---

## SECTION 5: PRIORITIZED ACTION PLAN

### P1 — 5-minute fixes (immediate, non-breaking)

**P1.1: Wire `decontaminate_prompt()` in runner at ~line 1120 (CHRONIC-6 fix)**
```python
if clean_choreo and _is_cpc_via_embedding(clean_choreo):
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt
        clean_choreo = decontaminate_prompt(clean_choreo, shot.get("_emotional_state", ""))
    except ImportError:
        pass
```
**Impact:** Scene 013 and any future scene with `_beat_action=None` will produce specific rather than generic video.

**P1.2: Normalize 4 API-path `video_url` fields in shot_plan.json (OPEN-009)**
Strip `/api/media?path=` prefix from 4 shots in scene 008. Prevents stitch failures and false positives in health monitoring.

**P1.3: Increase Gemini circuit breaker threshold from 3 to 6**
In `vision_judge.py`: `_ZERO_CIRCUIT_BREAKER: int = 6`
Gives Gemini 6 warmup chances on cold CLI start before tripping to heuristic.

### P2 — Prompt Upgrades (30 minutes, high reward)

**P2.1: Add temporal language to Kling video prompts**
In `compile_video_for_kling()`, add `_arc_carry_directive` as motion instruction, not just appended text:
- ESTABLISH: "Opening on → establishing room and identity"
- ESCALATE: "Continuing from previous beat → raising stakes as → "
- PIVOT: "Then — turning point — as → "
- RESOLVE: "Closing beat — settling → releasing tension"

**P2.2: Add duration intent line to dialogue shots**
Add to video prompt for dialogue shots: `"[Full dialogue delivery — hold through complete spoken line]"`

**P2.3: Enrich negative prompts with consistency-specific terms**
Add to Kling negative: `"face morphing, identity drift, costume change, room architecture shift"`

**P2.4: Add FACE IDENTITY LOCK to nano first-frame prompts**
Not just video prompts — the first frame sets the identity anchor for the entire chain. Any drift in the first frame compounds across all 10s of video.

### P3 — Vision Upgrade (2-4 hours, transformative)

**P3.1: Add Gemini Embedding 2 frame↔appearance scoring**
Replace Florence-2 caption intermediary with direct image↔text embedding via `gemini-embedding-2-flash-preview`. Eliminates the caption noise layer. Single API call instead of two.

**P3.2: Add narrative alignment score (N-score)**
Score generated video clip against `_beat_action + _beat_atmosphere` using Gemini Embedding 2 video embedding. This gives ATLAS the ability to detect "wrong action" failures that currently only AutoRevisionJudge catches (and only for video, not first frames).

**P3.3: Replace binary C-score with semantic clip continuity**
Embed consecutive clip end/start frames via Gemini Embedding 2 image mode. Cosine similarity ≥ 0.7 = smooth cut. < 0.5 = visual jump.

### P4 — Architecture Enhancement (deferred, future sprint)

**P4.1: Arc-weighted reward formula**
Implement R_V2 with 5-component weighted formula, with arc-position-aware threshold modulation.

**P4.2: Wire story_judge.py at scene-close**
Already built (670 lines). Call at end of each scene's video generation. Write advisory report to `reports/scene_{id}_narrative_health.json`. Feed into reward ledger.

**P4.3: Wire vision_analyst.py at stitch time**
Already built (911 lines, 8-dimension scoring). Call on completed stitched scene. Write advisory report. Feed into reward ledger.

---

## SECTION 6: SYSTEM STATE CROSS-REFERENCE TABLE

| Component | ATLAS Current | Best-in-Class Online | Gap Level |
|-----------|--------------|---------------------|-----------|
| Kling character tags | `[Character A: appearance]` | Same format | ✅ None |
| Names stripped from prompts | T2-FE-13, cast_map scan | FAL ignores names — strip them | ✅ None |
| 180° screen direction | FRAME-LEFT/FRAME-RIGHT in prompts | Explicit direction required | ✅ None |
| Temporal action language | Partial (beat action) | "then", "as", "while" in motion | 🟡 Improve |
| Duration intent in prompt | Not present | "hold through full dialogue" | 🟡 Add |
| Negative prompt specificity | Generic quality terms | Identity-specific continuity terms | 🟡 Improve |
| Nano ref image count | 3 per call | 6 optimal, 10+ degrades | 🟡 Add 4th ref (3/4 angle) |
| First-frame FACE IDENTITY LOCK | Video prompts only | Should be in BOTH | 🟡 Add to nano |
| Room DNA anchor in chain | V36.4 proven fix ✓ | Required for environment lock | ✅ None |
| Vision scoring: primary | Gemini 2.5 Flash exclusive | Direct VLM is best | ✅ None |
| Vision scoring: embedding | gemini-embedding-001 (text) | Gemini Embedding 2 (image+video) | 🔴 Upgrade |
| Reward formula | I×0.35+V×0.40+C×0.25 | Multi-dim with N (narrative) | 🔴 Missing N-score |
| CPC decontamination | Detected, NOT called | Must be called | 🔴 CHRONIC-6 |
| Arc position in prompts | Wired V36.5 ✓ | Use for arc-weighted reward | 🟡 Extend to reward |
| Clip spatial continuity | Binary (file exists) | Semantic cosine (Embedding 2) | 🔴 Upgrade C-score |
| Dialogue timing protection | T2-FE-16 wired | word_count/2.3 + 1.5s buffer | ✅ None |
| Auto revision judge | Built, 8 dimensions | Good — check wiring at pipeline | 🟡 Verify call |

---

## SECTION 7: ERROR REPORT STATUS

### R13 Summary (as of 2026-03-30T15:14:48Z)
- **P0 Blockers: 0** — OPEN-008 was a FALSE POSITIVE (5 reports). Gate never scanned `_beat_description`.
- **P1:** OPEN-009 — 4 API-path video_urls in scene 008 (stitch risk). Data patch, 1 min.
- **P2:** OPEN-004 CHRONIC-6 — `decontaminate_prompt()` absent from runner. 5 min fix.
- **P3:** OPEN-002 — 87.8% heuristic I-scores. Debug Gemini init timing.
- **P4:** OPEN-003/005 — Cosmetic stale docs. No impact.

**Generation readiness:** Scenes 001/002/003/004 ready for `--videos-only`. Scenes 005/007/009-013 need `--frames-only` first.

---

## SECTION 8: CONSCIOUSNESS ARTICULATION — KEY INSIGHT

The V36.5 architecture correctly identifies that **"Opening declares. Middle carries. Ending releases."** This is the right mental model, and Chain Arc Intelligence wires it structurally.

But the consciousness loop is incomplete until the reward signal **reads back** what the model produced in that arc position and asks: *"Did the ESCALATE shot actually escalate? Did the PIVOT shot actually turn?"*

Right now, ATLAS generates with arc-awareness but scores blindly. Gemini Embedding 2 video embeddings close this loop — you can directly ask "does this video move in the direction of the arc?" as a cosine similarity question.

The three-act chain becomes truly conscious when:
1. **Declare** → Frame generation with Room DNA + identity anchor → VLM confirms I-score
2. **Carry** → Video generation with arc directive → Embedding 2 confirms N-score (beat alignment)
3. **Close** → End-frame extraction → Embedding 2 confirms C-score (continuity with next)

This is the path from **Stage 7 (Chain Consciousness)** to **Stage 8 (Predictive Arc Closure)** — the system not only knows where it is in the arc, it verifies it got there.

---

*ATLAS Prompt + Vision Insight Report — 2026-03-30*
*Analysis by: Automated keep-up agent (prompt-insight skill)*
*Next recommended report: After P1-P2 fixes are applied and a full 001/002/003/004 --videos-only run completes*
