# ATLAS VISION ASSEMBLY LINE — SCENES 1-4 RUNSHEET
**Generated:** 2026-03-30
**Based on:** $2.275 stress test (13 clips, 9 content types, full D1-D20 scoring)
**Scope:** Autonomous vision correction loop for Victorian Shadows Scenes 001-004
**Mode:** Analysis only — no generation

---

## PART 1: STRESS TEST CATALOG — ALL 13 CLIPS

### Cost & Performance
- **Total spent:** $2.275 / $5.00 budget (45.5%)
- **Per-clip cost:** $0.175 flat (Kling v3/pro uniform pricing)
- **Elapsed range:** 122.7s (fastest: 07_CHAIN_RESOLVE) → 288.3s (slowest: 01_FANZ_PODCAST)
- **Average elapsed:** ~188s per clip

### Clip-by-Clip Scorecard

| ID | Label | Production | Genre | Arc | D7 Score | D14 Grade | Status |
|----|-------|-----------|-------|-----|----------|-----------|--------|
| 01_FANZ_PODCAST | FANZ Hosts Dialogue | podcast | podcast | ESTABLISH | 0.85 | **D** | Lighting violated — cool sports aesthetic instead of warm amber |
| 02_WHODUNIT_THRILLER | Corridor Tension | movie | thriller | ESCALATE | 0.95 | **B** | Excellent mood; darkness obscures room architecture for chain |
| 03_DRAMA_SAD | Emotional Turning Point | movie | whodunnit_drama | PIVOT | 0.625 | **F** | No environment — blank void, no window, no rain, no depth |
| 04_CINEMATIC_TRAILER | Epic Establishing Shot | movie | action | ESTABLISH | 0.98 | **A** | Gold standard — golden hour, low angle, epic scale, D8=true |
| 05_CHAIN_ESTABLISH | Detective Enters Room | movie | whodunnit_drama | ESTABLISH | 0.85 | **C** | Shot framing too tight — medium shot where WIDE was required |
| 06_CHAIN_ESCALATE | Sits, Notices Clue | movie | whodunnit_drama | ESCALATE | 0.88 | **B** | Good mood carry, but still too wide for emotional escalation |
| 07_CHAIN_RESOLVE | Picks Up Letter | movie | whodunnit_drama | RESOLVE | 0.95 | **A** | Gold standard — close insert, chain resolved, D8=true |
| 08_RUMBLE_FIGHT_WIDE | Fight Wide Shot | fight_broadcast | fight_broadcast | ESCALATE | 0.30 | **F** | Generated medium CU instead of required wide ring shot |
| 09_RUMBLE_FIGHTER_CU | Fighter Impact CU | fight_broadcast | fight_broadcast | PIVOT | 0.70 | **D** | Excessive headroom, missing impact moment, no ring context |
| 10_VYBE_STAGE_WIDE | Concert Stage Wide | music_video | music_video | ESTABLISH | 0.675 | **F** | Artist absent — wide shot of empty stage, D8=false |
| 11_VYBE_ARTIST_CU | Artist Emotional CU | music_video | music_video | ESCALATE | 0.825 | **C** | Strong emotion, but solid purple lighting vs declared golden |
| 12_JOKEBOX_CARTOON | Animated Comedy | bumper | comedy | ESTABLISH | 0.70 | **D** | Headroom too tight (head-to-frame-edge), rule-of-thirds failed |
| 13_VYBE_PODCAST | VYBE Recap Hosts | podcast | podcast | ESCALATE | 0.45 | **F** | Hosts entirely absent — studio wide with blurred hand only |

### Grade Distribution
```
A  ██░░░░░░░░  2/13 (15%) — 04_TRAILER, 07_CHAIN_RESOLVE
B  ██░░░░░░░░  2/13 (15%) — 02_THRILLER, 06_CHAIN_ESCALATE
C  ██░░░░░░░░  2/13 (15%) — 05_CHAIN_ESTABLISH, 11_VYBE_CU
D  ███░░░░░░░  3/13 (23%) — 01_PODCAST, 09_FIGHT_CU, 12_CARTOON
F  ████░░░░░░  4/13 (31%) — 03_DRAMA, 08_FIGHT_WIDE, 10_VYBE_WIDE, 13_VYBE_PODCAST
```
**First-pass acceptable (A/B/C):** 6/13 = 46%
**Hard failures (D/F):** 7/13 = 54%
**Auto-regen eligible (F only per VISION_BUDGET_CONFIG):** 4/13 = 31%

---

## PART 2: CALIBRATION FINDINGS — WHAT THE TEST PROVED

### FINDING 1: Arc Position is the #1 Failure Axis
**D8 arc_obligation fulfilled:** Only 3/13 (23%) passed.
- RESOLVE: 100% success (07_CHAIN_RESOLVE Grade A) — close inserts are faithful to intent
- ESTABLISH: 2/5 passed — the model generates medium shots when you ask for wide
- ESCALATE: 1/4 passed — the model doesn't tighten framing without explicit instruction
- PIVOT: 0/2 passed — no visible emotional shift registered in either pivot test

**Calibration rule baked in:**
Arc position must inject **framing instruction overrides** into the Kling prompt, not just atmosphere text:
- ESTABLISH → "WIDE SHOT. Full room geography visible. Character small in space."
- ESCALATE → "MEDIUM SHOT. Tighter than establishing. Emotional pressure readable on face."
- PIVOT → "MEDIUM CLOSE-UP. Visible emotional state change. Before/after contrast in single frame."
- RESOLVE → "CLOSE-UP or INSERT. Object or face. The beat lands here. Narrow attention."

### FINDING 2: Genre Lighting is the #2 Failure Axis
**D10 genre_standard matches:** 7/13 matched or partially matched.
The model defaults to "dramatic broadcast cool-toned" regardless of genre request.

| What was requested | What was delivered | D10 result |
|---|---|---|
| Warm amber podcast 3-point | Cool black/red sports broadcast | violated |
| 4:1 warm amber Victorian lamp | Dark, cold, under-lit | partial |
| Grey overcast grief window light | Blank dark void, no window | violated |
| Warm amber lamp (chain) | Warm amber lamp | **matches** |
| Arena overhead 3:1 even | ??? (wrong shot type) | violated |

**Calibration rule:** Genre lighting ratio must be stated as a visual ratio + a specific **color temperature** + a **motivated source** in the Kling prompt. Abstract genre labels are ignored.

Winning formula (from 07_CHAIN_RESOLVE, Grade A):
`"warm amber lamp light. Victorian drawing room. Same color temperature as previous shot. Soft bokeh background."`

Failing formula (from 03_DRAMA_SAD, Grade F):
`"Grey overcast natural window light"` → delivered opaque black background

### FINDING 3: Environment Presence is the #3 Failure Axis
**D2 location_score average across all clips:** 0.65
- Blank/void backgrounds appeared in 03, 08 (wrong shot), 13 (hosts missing)
- Stress test proved: **the room must be explicitly architectural in the prompt**, not described as atmosphere

D2 failures are recoverable with Room DNA injection — proven by 05-07 Victorian chain where the room stayed consistent once explicitly described.

### FINDING 4: Chain Intelligence — PROVEN WORKING
The chain test (05→06→07) showed the mechanism works:
- 05_CHAIN_ESTABLISH: C grade (framing wrong, but room established)
- 06_CHAIN_ESCALATE: B grade (room carried, framing improved)
- 07_CHAIN_RESOLVE: A grade (tight, chain resolved perfectly)

The chain intelligence **improves across the arc**. Opening frames define the room. Middle frames carry it. Closing frame inherits and resolves. This is the V36.5 arc intelligence in action.

### FINDING 5: D6 Hard Artifact Detection — Clean
0 AI artifacts detected across all 13 clips (D6=[] on every shot). The Kling v3/pro model has strong temporal stability. The failure modes are **compositional and narrative**, not AI-artifact.

### FINDING 6: Headroom is a Systematic QC Gap
D18 headroom_correct failed on: 04 (motivated), 09, 10, 12, 13.
This is a **mechanical correction** — the Kling prompt needs explicit headroom language:
- `"Headroom: 8-12% of frame above subject's head. Not crown-to-edge. Not excessive sky."`

### CALIBRATION BASELINES FOR WHODUNNIT_DRAMA (Victorian Shadows)
Based on clips 02, 05, 06, 07 (same genre):

| Dimension | Baseline | Target for Scenes 1-4 |
|---|---|---|
| D1 identity | 0.80–1.00 (char shots) | ≥ 0.70 gate |
| D2 location | 0.60–0.90 | ≥ 0.60 gate (explicit room DNA) |
| D3 blocking | 0.70–0.90 | ≥ 0.60 gate |
| D4 mood | 0.80–1.00 | ≥ 0.65 gate |
| D7 overall | 0.85–0.95 (A/B range) | ≥ 0.65 proceed to Kling |
| D8 arc | 50% pass rate without arc override | Enforce framing override per arc |
| D14 grade | B achievable without override; A with | Target B+ average per scene |
| Lighting | 4:1, warm amber lamp, motivated | Explicit in every Kling prompt |
| Genre failures | arc_position_not_fulfilled, framing_too_wide | Arc framing override applied |

---

## PART 3: THE ASSEMBLY LINE — 4-LAYER AUTONOMOUS CORRECTION LOOP

```
┌─────────────────────────────────────────────────────────────────────┐
│  ASSEMBLY LINE — PARALLEL SCENE GENERATION WITH VISION GATES       │
│                                                                     │
│  SCENE 001 ─────────────────────────────────────────────────────┐  │
│  SCENE 002 ─────────────────────────────────────────────────────┤  │
│  SCENE 003 ─────────────────────────────────────────────────────┤  │
│  SCENE 004 ─────────────────────────────────────────────────────┘  │
│                                                                     │
│  Within each scene, shots run SEQUENTIALLY (end-frame chain).      │
│  Across scenes, all 4 run IN PARALLEL (assembly line efficiency).  │
│                                                                     │
│  Each shot passes through 4 layers before the next shot runs.      │
└─────────────────────────────────────────────────────────────────────┘
```

### LAYER 1 — Nano Frame Generation + Identity Gate

**What runs:** `fal-ai/nano-banana-pro/edit` (character shots) or `fal-ai/nano-banana-pro` (E-shots)

**Pre-flight enrichment applied BEFORE the call:**
1. `[CHARACTER:]` identity block injected from cast_map (amplified — V27.5)
2. `[ROOM DNA:]` block from `tools/scene_visual_dna.py` (locked room architecture)
3. `[LIGHTING RIG:]` block — 4:1, warm amber lamp, motivated window/lamp source
4. `[ARC FRAMING:]` override based on shot's `_arc_position`:
   - ESTABLISH → "WIDE SHOT — full room geography, character small in space"
   - ESCALATE → "MEDIUM SHOT — tighter than establishing, emotional pressure on face"
   - PIVOT → "MEDIUM CLOSE-UP — visible emotion shift, before/after readable in frame"
   - RESOLVE → "CLOSE-UP or INSERT — narrow attention, beat lands here"
5. `[HEADROOM:]` → "8-12% above head, no cropping, no excessive sky"

**Post-generation vision gate (D1 identity scoring via Gemini 2.5 Flash):**
```
Character shots:  D1 ≥ 0.70 → PASS to Layer 2
                  D1 0.50–0.69 → FLAG for review, proceed cautiously
                  D1 < 0.50 → REGEN (max 1 attempt per Wire A budget)

E-shots (no char): D6 must = [] (no phantom characters)
                   Any character detected → REGEN with explicit "no people" constraint
```

**Budget guardrail:** Wire A budget = 2 regens per scene. If exhausted → FLAG shot, do not block generation.

---

### LAYER 2 — Vision Doctrine D1-D20 Pre-Flight Before Kling

**What runs:** `run_video_oversight()` on the first frame (frame-based mode, Gemini 2.5 Flash)

**This layer fires AFTER Nano generates the frame, BEFORE Kling generates video.**
Purpose: catch frame-level failures cheaply ($0.002 vs $0.175 for video regen).

**Scoring thresholds:**

| Check | Threshold | Action on Fail |
|---|---|---|
| D7 overall score | < 0.65 → BLOCK Kling call | Re-run Layer 1 (1x only), then proceed with warning |
| D8 arc_obligation | false + D14=D/F → BLOCK | Inject arc framing override, re-run Layer 1 |
| D8 arc_obligation | false + D14=B/C → WARN | Proceed to Kling with arc carry note |
| D10 genre_standard | "violated" → PATCH | Inject corrected lighting ratio into Kling prompt |
| D12 production_format | "wrong_format" → BLOCK | Flag shot, do not generate video, escalate to operator |
| D14 grade | A/B/C → PASS | Proceed to Layer 3 |
| D14 grade | D → ADVISORY | Proceed with _preflightWarning on shot |
| D14 grade | F → BLOCK | Re-run Layer 1 (1x only), if still F → proceed with _preflightFailed flag |
| D16 violation list | Non-empty → LOG | Write violations to shot._d16_violations for Layer 4 |

**D10 patch logic (automatic prompt correction before Kling):**
- `lighting_mismatches_genre_tone` → append to Kling prompt: "Warm amber lamp light. Victorian interior. Soft shadows. 4:1 lighting ratio."
- `arc_position_not_fulfilled` → inject arc framing override (see Layer 1)
- `no_environmental_storytelling` → inject Room DNA into Kling prompt

**Output written to shot plan:**
```json
{
  "_layer2_d7": 0.88,
  "_layer2_d14": "B",
  "_layer2_passed": true,
  "_layer2_violations": ["arc_position_location_continuity_failed"],
  "_kling_prompt_patches": ["lighting_ratio_patch", "arc_carry_note"]
}
```

---

### LAYER 3 — Kling Video Generation with Chain Intelligence

**What runs:** `fal-ai/kling-video/v3/pro/image-to-video` with multi-prompt

**Chain architecture (V36.5 arc-aware):**

```
Shot N-1 last frame ──► Shot N start_image_url
                        + char_ref (elements[])
                        + loc_master (Room DNA anchor — V36.4 fix)
                        + arc_carry_directive in Kling prompt
```

**Per arc-position Kling prompt structure:**

```
ESTABLISH:
"[ARC: ESTABLISH] WIDE SHOT. [Room DNA compact: room type, architecture].
 [Character action]. [Lighting: warm amber lamp, 4:1, motivated source].
 Full room geography visible. This frame declares the room's visual law.
 [Headroom: 8-12%]. [FACE IDENTITY LOCK]. [BODY PERFORMANCE FREE]."

ESCALATE:
"[ARC: ESCALATE] MEDIUM SHOT. SAME [room]. SAME amber lighting — carried from opening.
 [Character action — rising tension]. Framing tighter than establishing shot.
 [Lighting: same source, same direction]. Emotional pressure readable.
 [FACE IDENTITY LOCK]. [BODY PERFORMANCE FREE]."

PIVOT:
"[ARC: PIVOT] MEDIUM CLOSE-UP. Visible emotional shift on face. [Character action — beat turns].
 Room still present in bokeh. SAME amber behind. Tighter than ESCALATE.
 The emotional register changes in this frame. [FACE IDENTITY LOCK]. [BODY PERFORMANCE FREE]."

RESOLVE:
"[ARC: RESOLVE] CLOSE-UP or INSERT. [Object or face]. Warm amber bokeh behind.
 Narrow attention — [beat lands here]. Quiet completion. Chain releases after this.
 [FACE IDENTITY LOCK]. [BODY PERFORMANCE FREE]."
```

**Room DNA anchor (V36.4 proven fix):**
Every reframe call uses `image_urls = [last_frame, char_ref, loc_master]` — the location master as 3rd slot prevents room DNA contamination across chain groups.

**Chain group handoff:**
```
Group 1 end-frame → Group 2 start_image_url (automatic)
+ Room DNA text block re-injected in reframe prompt (prevents gray-void drift)
+ Arc position transitions: ESTABLISH → ESCALATE → PIVOT → RESOLVE
```

**Outgoing hints (scene boundary):**
Last shot of each scene gets `_arc_release = true` — Room DNA is released, next scene starts fresh ESTABLISH.

---

### LAYER 4 — Post-Gen Vision Oversight + Auto-Regen (Grade F Only)

**What runs:** `run_video_oversight(video_path, shot, story_bible, use_full_video=True)` via Gemini 2.5 Flash (per-shot) and Gemini 2.5 Pro (chain transitions + scene stitch)

**Regen policy:** `regen_on_grade_f_only = True`, `max_regen_per_shot = 1`

**Tier 1 — Full video analysis (Gemini 2.5 Flash, per shot):**
Checks that cannot be caught on a single frame:
- ACTION_COMPLETION — does the beat action actually finish?
- FROZEN_SEGMENT — any freeze ≥ 0.5s at any timestamp?
- DIALOGUE_SYNC — mouth movement continuity across speaking duration?
- EMOTIONAL_ARC — does body language match arc_position (ESTABLISH/ESCALATE/PIVOT/RESOLVE)?
- CHARACTER_CONTINUITY — does start-frame match end-frame for chain handoff?

**Tier 1 — Chain transition check (Gemini 2.5 Pro, between shots):**
After Shot N video is generated, compare with Shot N-1 end-frame:
- Position continuity (character spatial state)
- Costume continuity (no wardrobe drift)
- Lighting continuity (same color temperature carried)
- Arc progression (does the emotional temperature rise shot-to-shot?)

**Tier 2 — Scene stitch check (Gemini 2.5 Pro, after all shots):**
After FFmpeg stitch, upload full scene:
- Cut naturalness
- Emotional arc coherence (ESTABLISH → ESCALATE → PIVOT → RESOLVE readable)
- Jarring transitions flagged with timecode

**Auto-regen decision matrix:**
```
Grade A → LOG success, proceed
Grade B → LOG, proceed (advisory notes)
Grade C → LOG violations to _d16_violations, proceed with warning
Grade D → FLAG shot (_layer4_flag=true), proceed (no regen)
Grade F + hard reject dimension → AUTO-REGEN (1x max)
Grade F + budget exceeded → CONTAMINATE shot (_chain_contaminated=true), skip downstream shots
Grade F (2nd attempt) → HUMAN ESCALATION flag, proceed to stitch anyway
```

**Hard reject dimensions that trigger Grade F auto-regen:**
- FROZEN_SEGMENT detected in full video
- ACTION_COMPLETION = false (beat never executed)
- CHARACTER_CONTINUITY = fail (identity drift between start and end frame)
- DIALOGUE_SYNC = failed (mouth not moving during dialogue)

**Budget tracking:**
```python
VisionBudgetTracker:
  max_regen_per_shot = 1
  max_kling_calls_multiplier = 1.5  (scene cap)
  max_episode_multiplier = 1.3       (episode cap)
  daily_gemini_budget_usd = 5.0
  stop_chain_on_budget_exceeded = True
```

---

## PART 4: PER-SCENE RUNSHEETS

### SCENE 001 — GRAND FOYER (Eleanor + Thomas)
**Current status:** 8/8 frames ✅, 8/8 videos ✅ — **OLD outputs (pre-vision-doctrine)**
**Action required:** Archive old outputs → run --frames-only → review → run --videos-only

**Shot inventory:**
| Shot | Type | Arc Position | Characters | Layer 1 Priority |
|------|------|-------------|-----------|-----------------|
| 001_E01 | E-shot | ESTABLISH | none | Empty constraint (no people) |
| 001_E02 | E-shot | ESTABLISH | none | Empty constraint (no people) |
| 001_E03 | E-shot | ESTABLISH | none | Empty constraint (no people) |
| 001_M01 | Master | ESTABLISH | Eleanor | D1 ≥ 0.70 (Eleanor identity) |
| 001_M02 | Dialogue OTS | ESCALATE | Eleanor, Thomas | D1 ≥ 0.70 both, D3 ≥ 0.60 blocking |
| 001_M03 | Dialogue OTS | ESCALATE | Eleanor, Thomas | OTS-A/B angle alternation |
| 001_M04 | Reaction | ESCALATE | Thomas | Thomas gazing at portrait |
| 001_M05 | Close/insert | RESOLVE | Thomas (portrait) | Harriet portrait as subject |

**Genre/lighting calibration:**
- Genre: `whodunnit_drama` → 4:1 ratio, motivated single source
- Light source: morning stained glass, muted gold/amber, dust-filtered
- Palette: muted golds, warm browns, cool slate grey shadows
- Palette hazard: NO cool sports broadcast blue — calibrated from 01_FANZ_PODCAST failure

**Layer 2 pre-flight thresholds:**
- D7 ≥ 0.65 → proceed to Kling
- D8 arc_obligation critical on 001_E01-E03 (WIDE establishing shots must declare room)
- D10: if `lighting_mismatches_genre_tone` → patch with "morning light through stained glass, warm amber golds, muted Victorian interior"

**Layer 3 chain sequence:**
```
001_M01 (ESTABLISH) → 001_M02 (ESCALATE) → 001_M03 (ESCALATE) → 001_M04 (ESCALATE) → 001_M05 (RESOLVE)
       ↑ scene first frame                                                                      ↑ arc releases
```
Room DNA: `single curved dark mahogany staircase with carved balusters, marble floors, oil portrait above staircase, dark crystal chandelier, ornate console table, dust sheets`

**Layer 4 auto-regen triggers:**
- 001_M02/M03 (OTS dialogue): DIALOGUE_SYNC = failed → regen
- 001_M04 (Thomas reaction): FROZEN_SEGMENT → regen
- 001_M05 (portrait resolve): ACTION_COMPLETION = false → regen

**Expected cost:** 8 shots × $0.175 + up to 4 regens × $0.175 = $1.40–$2.10

---

### SCENE 002 — LIBRARY (Nadia solo)
**Current status:** 1/7 frames ⚠️, 0/7 videos ❌ — **needs full run from scratch**
**Action required:** Run --frames-only → review → run --videos-only

**Shot inventory:**
| Shot | Type | Arc Position | Characters | Special |
|------|------|-------------|-----------|---------|
| 002_E01 | E-shot | ESTABLISH | none | Library exterior with warm window glow |
| 002_E02 | E-shot | ESTABLISH | none | Rich bookshelf detail |
| 002_E03 | E-shot | ESTABLISH | none | Book spine insert |
| 002_M01 | Medium | ESTABLISH | Nadia | Nadia photographs shelves |
| 002_M02 | Medium | ESCALATE | Nadia | Letter falls, Nadia catches |
| 002_M03 | Close | PIVOT | Nadia | Expression shifts to shock (PIVOT) |
| 002_M04 | Close | RESOLVE | Nadia | Pockets letter, glances at door |

**SOLO SCENE RULES (T2-FE-35):**
- NO off-camera partner direction in any shot
- Dialogue is self-directed: "reading aloud", "expression shifts", "eyes scanning"
- 002_M02 dialogue: `"My dearest Thomas, the house keeps our secrets..."` → Nadia reading aloud, not speaking to someone
- 002_M04 is silent action only

**Genre/lighting calibration:**
- Genre: `whodunnit_drama`, interior library
- Light: "warm golden afternoon light from tall windows, dust motes visible, leather book warmth"
- Palette: warm amber on spines, cool shadow in corners
- CRITICAL hazard: Do NOT deliver blank dark void (stress test 03_DRAMA_SAD = F grade on same palette description). Must explicitly state: "tall windows casting rectangles of afternoon gold, floor-to-ceiling bookshelves, mahogany desk visible, first edition spines"

**Layer 2 calibration note:**
- 002_M03 is PIVOT — must show visible emotion shift. D8 failure likely on first attempt.
- Patch: inject "MEDIUM CLOSE-UP. Her expression visibly changes — eyes widen, breath stops. The before and after readable in this single frame." into Kling prompt before generation.

**Layer 3 chain sequence:**
```
002_M01 (ESTABLISH) → 002_M02 (ESCALATE) → 002_M03 (PIVOT) → 002_M04 (RESOLVE)
                              ↑ letter falls here                     ↑ arc releases
```
Room DNA: `floor-to-ceiling bookshelves with leather-bound volumes, mahogany desk, tall windows with afternoon light, first editions visible on shelves, warm amber interior`

**Expected cost:** 7 shots × $0.175 + up to 3 regens = $1.225–$1.75

---

### SCENE 003 — DRAWING ROOM (Eleanor + Raymond)
**Current status:** 8/9 frames ⚠️ (003_M03b missing), 0/9 videos ❌ — **needs videos**
**Action required:** Generate 003_M03b frame → then run --videos-only for all 9 shots

**Shot inventory:**
| Shot | Type | Arc Position | Characters | Special |
|------|------|-------------|-----------|---------|
| 003_E01 | E-shot | ESTABLISH | none | Drawing room with dust sheets |
| 003_E02 | E-shot | ESTABLISH | none | Piano under dust sheet |
| 003_E03 | E-shot | ESTABLISH | none | Silver candelabra detail |
| 003_M01 | Medium | ESTABLISH | Eleanor | Eleanor tagging items, clipboard |
| 003_M02 | Medium | ESCALATE | Eleanor, Raymond | Raymond in doorway, watching |
| 003_M03 | Dialogue OTS | ESCALATE | Eleanor, Raymond | Raymond: "The Steinway alone is worth sixty thousand" |
| 003_M03b | Dialogue OTS | ESCALATE | Eleanor, Raymond | OTS reverse angle (missing frame) |
| 003_M04 | Dialogue CU | PIVOT | Raymond | Raymond threat: "information about how Harriet died" |
| 003_M05 | Reaction CU | RESOLVE | Eleanor | Eleanor: "Is that a threat, Mr. Cross?" |

**TWO-CHARACTER BLOCKING (T2-FE-29):**
- Raymond: frame-RIGHT (he occupies space aggressively — rule him into threatening side)
- Eleanor: frame-LEFT (professional, measured — anchor of reason)
- D3 blocking gate: ≥ 0.60 required (stress test showed multi-char shots need explicit blocking)
- Layer 1 must inject: `[BLOCKING: Eleanor frame-LEFT professional posture. Raymond frame-RIGHT blocking doorway, arms folded, imposing.]`

**Genre/lighting calibration:**
- Genre: `whodunnit_drama`, dim drawing room
- Light: "dim interior, white dust sheets creating ghostly shapes, single lamp or indirect window light, menacing undertone"
- Raymond's burgundy shirt is a DANGER visual signal — must be explicit in his character block
- Hazard: DO NOT let the dust sheets become blank white void (same trap as 03_DRAMA_SAD)

**Layer 2 pre-flight on 003_M04 (PIVOT — Raymond threat):**
- D8 arc_obligation must show visible PIVOT. Raymond leans in, voice drops, body language shifts.
- Patch if D8=false: inject "His body language changes — leans closer, drops to whispered register. The room's emotional temperature shifts in this frame."

**Layer 3 chain sequence:**
```
003_M01 (ESTABLISH) → 003_M02 (ESCALATE) → 003_M03 (ESCALATE) → 003_M03b (ESCALATE) → 003_M04 (PIVOT) → 003_M05 (RESOLVE)
```
Room DNA: `furniture under white dust sheets creating ghostly draped shapes, Steinway piano under sheet, silver candelabras on mantle, crystal display cases, dim ambient light, drawing room architecture`

**OTS pair integrity (003_M03/003_M03b):**
These must be opposite angles per T2-FE-14:
- 003_M03 = OTS-A: Raymond frame-RIGHT facing camera, Eleanor frame-LEFT foreground shoulder
- 003_M03b = OTS-B: Eleanor frame-LEFT facing camera, Raymond frame-RIGHT foreground shoulder

**Expected cost:** 9 shots × $0.175 + up to 4 regens = $1.575–$2.275

---

### SCENE 004 — GARDEN (Thomas solo)
**Current status:** 7/7 frames ✅, 7/7 videos ✅ — **OLD outputs (pre-vision-doctrine)**
**Action required:** Archive old outputs → run --frames-only → review → run --videos-only

**Shot inventory:**
| Shot | Type | Arc Position | Characters | Special |
|------|------|-------------|-----------|---------|
| 004_E01 | E-shot | ESTABLISH | none | Garden exterior, grey sky |
| 004_E02 | E-shot | ESTABLISH | none | Dead roses on rusted trellis |
| 004_E03 | E-shot | ESTABLISH | none | Dry cracked fountain |
| 004_M01 | Medium | ESTABLISH | Thomas | Thomas on bench, velvet box |
| 004_M02 | Close | ESCALATE | Thomas | Turning box over and over |
| 004_M03 | Reaction | PIVOT | Thomas | Hears Eleanor's call, closes box quickly |
| 004_M04 | Wide | RESOLVE | Thomas | Rises slowly, looks back at fountain |

**CRITICAL LESSON FROM STRESS TEST — 03_DRAMA_SAD:**
Test clip 03 had the same brief: "grey overcast exterior, grief, isolation, cool blues" — and scored D14=F.
Reason: The model delivered a blank dark void instead of an actual exterior environment.

**Fix baked in:** Every 004 shot must explicitly state architectural elements:
- `"Overgrown Victorian garden. Dead roses on rusted iron trellises. Dry cracked stone fountain. Weathered bench. Grey overcast sky. Rolling countryside beyond stone wall. Actual exterior — sky visible, ground visible, garden depth visible."`
- E-shots must have: `"No people. Empty garden. Dead roses close-up visible. Overgrown texture."`

**SOLO SCENE:**
- Thomas only. No dialogue in M01-M03. M04 is silent action.
- No off-camera partner direction in any prompt.
- Thomas body language: "turns velvet box in hands", "slow deliberate movement", "grief visible in posture"

**Thomas identity requirements:**
- Distinguished silver hair, deep weathered lines on face, rumpled navy suit
- Velvet box is a REQUIRED PROP in 004_M01 and 004_M02 shots
- D3 blocking gate: ≥ 0.55 (solo scenes have simpler blocking requirements)

**Layer 3 chain sequence:**
```
004_M01 (ESTABLISH) → 004_M02 (ESCALATE) → 004_M03 (PIVOT) → 004_M04 (RESOLVE)
      ↑ Thomas on bench                            ↑ box closes                  ↑ arc releases
```
Room DNA: `overgrown Victorian garden, dead roses on rusted iron trellises, dry cracked stone fountain, weathered wooden bench, grey overcast sky, stone wall boundary, wild grass and weeds visible`

**Expected cost:** 7 shots × $0.175 + up to 3 regens = $1.225–$1.75

---

## PART 5: CONSOLIDATED ASSEMBLY LINE THRESHOLDS

### Layer 1 — Nano Gate (per shot type)
| Shot Type | D1 Identity Gate | D6 Empty Gate | Regen Trigger |
|---|---|---|---|
| Character solo | ≥ 0.70 | N/A | D1 < 0.50 |
| Character multi | ≥ 0.70 each | N/A | D1 < 0.50 or D3 < 0.40 |
| E-shot (empty) | N/A | [] (empty) | Any character detected |
| Insert/prop | ≥ 0.70 if person visible | N/A | D1 < 0.50 |

### Layer 2 — Pre-Flight Gate (before Kling)
| Metric | Pass Threshold | Action on Fail |
|---|---|---|
| D7 overall | ≥ 0.65 | Regen frame (1x), then proceed with warning |
| D8 arc_obligation | true | Inject framing override if false |
| D10 genre_standard | matches or partial | Patch Kling prompt if violated |
| D12 production_format | correct | Block Kling if wrong_format |
| D14 grade | A/B/C → pass | D → warn, F → regen frame 1x |

### Layer 3 — Chain Intelligence (per scene)
| Parameter | Value |
|---|---|
| Arc position enrichment | All shots: ESTABLISH→ESCALATE→PIVOT→RESOLVE |
| Room DNA anchor | image_urls[2] = loc_master (V36.4) |
| Room DNA text | Injected in every reframe prompt |
| Arc framing override | In every Kling prompt (not just atmosphere) |
| End-frame chaining | Shot N last frame → Shot N+1 start |
| Scene boundary | _arc_release on final shot, DNA released for Scene N+1 |

### Layer 4 — Post-Gen Oversight (per shot + chain + stitch)
| Trigger | Condition | Action |
|---|---|---|
| Per-shot auto-regen | D14=F + hard reject | Regen (1x max) |
| Per-shot flag | D14=D | _layer4_flag, no regen |
| Chain contamination | Budget exceeded | _chain_contaminated, skip downstream |
| Chain transition | Gemini 2.5 Pro check | Advisory report |
| Scene stitch | Full scene upload | Advisory report + flagged timecodes |

### Auto-Regen Decision Tree
```
Video generated
     │
     ▼
Layer 4 vision oversight
     │
     ├── Grade A/B/C ──────────────────────────► PASS → next shot
     │
     ├── Grade D ──────────────────────────────► FLAG (_layer4_flag) → next shot
     │
     └── Grade F ──────────────────────────────► Has hard reject?
                                                        │
                                                    YES ─┤
                                                        │
                                                        ▼
                                                 Budget available?
                                                        │
                                                   YES ─┼─ NO ─► CONTAMINATE chain → skip
                                                        │
                                                        ▼
                                                 Regen (1x, with D16 patch)
                                                        │
                                                        ▼
                                                 Grade F again?
                                                        │
                                                   YES ─┤
                                                        ▼
                                                 HUMAN ESCALATION
                                                 (_needs_review=true)
                                                 Proceed to stitch anyway
```

---

## PART 6: TOTAL COST PROJECTION — SCENES 1-4

| Scene | Shots | Base Cost | Max Regen Cost | Total Range |
|---|---|---|---|---|
| 001 (Foyer) | 8 | $1.40 | +$0.70 | $1.40–$2.10 |
| 002 (Library) | 7 | $1.225 | +$0.525 | $1.225–$1.75 |
| 003 (Drawing Room) | 9 | $1.575 | +$0.70 | $1.575–$2.275 |
| 004 (Garden) | 7 | $1.225 | +$0.525 | $1.225–$1.75 |
| **TOTAL** | **31** | **$5.425** | **+$2.45** | **$5.425–$7.875** |

**Gemini vision costs (Layer 2 + Layer 4):**
- Per-shot pre-flight: 31 shots × $0.002 = $0.062
- Per-shot post-gen: 31 shots × $0.002 = $0.062
- Chain transitions: 27 transitions × $0.002 = $0.054
- Scene stitch checks: 4 × $0.004 = $0.016 (2.5 Pro)
- **Gemini total: ~$0.19**

**Projected total run cost: $5.61–$8.07** (well within $25 episode budget)

---

## PART 7: EXECUTION COMMANDS (WHEN READY TO GENERATE)

```bash
# STEP 0: Verify session enforcer passes
python3 tools/session_enforcer.py

# STEP 1: Archive old outputs for Scenes 001 and 004
python3 tools/pre_run_gate.py victorian_shadows_ep1 001
python3 tools/pre_run_gate.py victorian_shadows_ep1 004

# STEP 2: Generate missing frame for Scene 003
python3 atlas_universal_runner.py victorian_shadows_ep1 003 --mode lite --frames-only
# Review 003_M03b specifically in UI filmstrip → thumbs up if correct

# STEP 3: Run all 4 scenes frames-only IN PARALLEL (assembly line)
# Each scene gets its own process — they run concurrently
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only &
python3 atlas_universal_runner.py victorian_shadows_ep1 002 --mode lite --frames-only &
python3 atlas_universal_runner.py victorian_shadows_ep1 004 --mode lite --frames-only &
wait

# STEP 4: Review all frames in UI filmstrip
# → Thumbs up approved frames
# → Thumbs down rejects (diagnostic regen triggered automatically)

# STEP 5: Videos-only once all frames approved (parallel across scenes, sequential within)
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --videos-only &
python3 atlas_universal_runner.py victorian_shadows_ep1 002 --mode lite --videos-only &
python3 atlas_universal_runner.py victorian_shadows_ep1 003 --mode lite --videos-only &
python3 atlas_universal_runner.py victorian_shadows_ep1 004 --mode lite --videos-only &
wait

# STEP 6: Check V37 governance dashboard
# Cost bar, release gate, regression guard — all should be GREEN
```

---

## SUMMARY: WHAT THE STRESS TEST CALIBRATED

The $2.275 test gave us 5 binding facts that are now baked into every layer:

1. **Arc framing override is mandatory** — narrative atmosphere text alone does not change shot size. Must inject explicit `WIDE SHOT`, `MEDIUM CLOSE-UP` etc. as directive not description.

2. **Genre lighting must be specific** — "warm amber" fails. "4:1 key-to-fill, warm amber lamp at frame-left, motivated single source, soft fill only where physically motivated" succeeds.

3. **Environment is architectural, not atmospheric** — "grief-filled grey room" → blank void. "Dry cracked stone fountain, dead roses on rusted iron trellises, grey overcast sky, stone wall boundary visible" → actual garden.

4. **Chain resolve beats are the most reliable** — Grade A achievable on RESOLVE shots without intervention. The system naturally converges to resolution. Use this: push the arc toward RESOLVE with deliberate shot design.

5. **Headroom is a mechanical QC fix** — every prompt gets: "Headroom: 8-12% above subject's head. Not crown-to-edge." Cheap to add, prevents systematic D18 failures.

---
*ATLAS V36.5 Vision Assembly Line — Calibrated from $2.275 stress test, 2026-03-30*
*Author: ATLAS Vision Doctrine system + production calibration data*
