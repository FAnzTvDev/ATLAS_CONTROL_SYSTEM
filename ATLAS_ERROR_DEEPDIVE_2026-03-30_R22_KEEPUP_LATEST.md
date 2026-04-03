# ATLAS ERROR DEEPDIVE — 2026-03-30 R22 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T00:21:00Z (approx)
**Run number:** R22
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R21_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 15h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 2 CONFIRMED_BUG / 1 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R21 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **CONFIRMED_BUG** | 2 | = | OPEN-009 (11th, META-CHRONIC) + OPEN-010 (8th) |
| **META-CHRONIC** | 1 | = | OPEN-009 now 11 consecutive reports |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 21st report |
| STALE_DOC | 2 | OPEN-003 (21st), OPEN-005 (19th) | Cosmetic |
| **CONFIRMED_FIXED** | **22** | = | 22 confirmed — 0 regressions |
| **CODE CHANGES SINCE R21** | **0 files** | = | **System fully idle** |
| **GENERATION SINCE R21** | **0 frames, 0 videos** | = | **System fully idle** |

**Key findings R22:**

1. 🟢 **NO REGRESSIONS. ALL 22 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. 0 blocks. Learning log: 22 fixes, 0 regressions. Runner mtime 2026-03-30T19:44:43Z — **unchanged from R21**. Orchestrator mtime 2026-03-30T19:43:25Z — unchanged. Zero code changes between R21 and R22.

2. 🔴 **OPEN-009 PERSISTS AS META-CHRONIC (11th consecutive report, R12→R22).** API-path prefix on 8 fields across 4 shots (008_E01/E02/E03/M03b) confirmed identical state. No data patch applied by operator. This constitutes 11 consecutive report cycles with fix loop failure. Escalation remains active.

3. 🟡 **SYSTEM FULLY IDLE — 3rd consecutive idle report (R20, R21, R22).** No frames, no videos, no code changes, no data patches generated since R19. Ledger age: 15h21m (+60m from R21). 228 entries, 41 unique shots. Production state frozen at R19 baseline.

4. 🟡 **OPEN-010 PERSISTS (8th consecutive).** 4 shots (001_M02/M03/M04/M05) retain ghost first_frame_url pointing to non-existent files, all APPROVED. Identical to R21.

5. 🟡 **OPEN-002 REWARD SIGNAL (21st consecutive, ARCHITECTURAL_DEBT).** 87.8% heuristic I=0.75 — unchanged. 5 real-VLM shots remain the only non-heuristic entries. Resolves on next generation run.

6. 🟡 **006_M02 + 006_M04 STILL AWAITING_APPROVAL (2nd consecutive report).** First noted R21. These 2 shots in scene 006 have generated videos but have not been approved or rejected. Non-blocking; scene_006_stitched.mp4 (15MB) exists.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R22) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes. Bare-list guard at runner:1504. 97/97 arc positions. 62/62 M-shots with `_chain_group`. | `isinstance(sp, list)` at runner:1504 ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` imported at runner:87 (try/except), called at runner:2372 (nano) and runner:3206 (Kling). Runner mtime 19:44:43Z — unchanged from R21. | `grep -n "_cpc_decontaminate" runner` → lines 87, 91, 2372, 3206 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 claim Seedance PRIMARY (STALE_DOC-19). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:527). CLAUDE.md V36.5 accurate. | `sed -n '24p'` → "Seedance v2.0 PRIMARY"; runner:527 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (runner:461, 4560), Wire-C (12 combined A/B/C matches), Chain arc (runner:65+4772), all doctrine hooks wired. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY ✅ |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available (gemini_vision, openrouter, florence_fal, heuristic). OPEN-010: 4 ghost first_frame_urls. OPEN-009: 4 API-path first_frame_urls (underlying files exist). | Enforcer output + env scan R22 ✅ |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 15h21m stale). 87.8% heuristic I=0.75 (latest-per-shot). 5 real-VLM shots: 008_M01(1.0), 008_M02(0.9), 008_M04(0.8), 004_M01(1.0), 004_M02(1.0). Resolves on next generation run. | Ledger analysis — identical to R21 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/ (35 actual + 27 chain lastframe files). 30 MP4s in videos_kling_lite/. 5 scenes stitched (001/002/004/006/008). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path shots. 2 AWAITING_APPROVAL (006_M02, 006_M04). 2 REGEN_REQUESTED (008_M03b, 008_M04). run_report: success=True, errors=[]. | File counts + shot_plan scan R22 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5539 ✅. 5 stitched scenes confirmed (scene_001/002/004/006/008). All stitch files unchanged since R21. | `grep -n "_fail_sids"` → runner:5539 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C: 12 combined A/B/C matches. All Wire-C branches intact. Runner unmodified since R21. | `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39) persist. CLAUDE.md V36.5 correct. No code changes since R21. | Same as R21 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

22 items total — all intact, 0 regressions confirmed R22.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:490/497.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1504.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` at runner:461, called at runner:4560.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4772.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R22 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:~1141.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 12 combined A/B/C matches confirmed R22.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:527 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED IN RUNNER** — `_cpc_decontaminate` imported at runner:87 (try/except non-blocking), called at runner:2372 (nano frame path) AND runner:3206 (Kling video path). Runner mtime 19:44:43Z unchanged. Fix persists.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (11 reports): OPEN-009 — API-Path Prefix in video_url/first_frame_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) have `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. All underlying files confirmed to exist on disk. Stitch proven non-blocking (scene_008_full_8shots.mp4 created successfully). Data inconsistency only. Re-run risk: if runner tries `os.path.exists(video_url)` with API-path format, may cause unnecessary re-generation.

**META-CHRONIC STATUS:** 11 consecutive reports (R12→R22). Fix loop has failed. This is formally a process failure per keep-up protocol. Operator must apply 3-minute data patch OR formally accept as tolerated known state.

**PROOF RECEIPT (R22 live):**
```
PROOF: python3 -c "import json; sp=json.load(open('pipeline_outputs/victorian_shadows_ep1/shot_plan.json')); shots=sp if isinstance(sp,list) else sp['shots']; api_v=[s['shot_id'] for s in shots if '/api/media' in str(s.get('video_url',''))]; print(f'API_PATH_VIDEO_URL: {len(api_v)} shots: {api_v}')"
OUTPUT:
  API_PATH_VIDEO_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
  API_PATH_FIRST_FRAME_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
  All 4 underlying video + frame files confirmed present on disk (R20 verification still valid)
  scene_008_full_8shots.mp4: exists=True (85MB)
CONFIRMS: Identical to R21. 8 API-path fields persist. Data inconsistency only.
```

**Fix recipe (data patch only — no code changes required):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   Strip "/api/media?path=" prefix from both video_url and first_frame_url
# Total: 8 field changes
# Verify: grep "/api/media" shot_plan.json | wc -l → should return 0
```

**Regression guard:** This patch touches only `video_url` and `first_frame_url` fields for 4 shots. Must NOT touch: `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`, `_arc_carry_directive`. Confirm after patch: `python3 tools/session_enforcer.py` still HEALTHY.

**Classification:** META-CHRONIC (data inconsistency — API-path prefix). Non-blocking for stitch and generation. 11th consecutive report.

---

### OPEN-010 (CONFIRMED_BUG — R15→R22, Non-blocking, 8th consecutive report)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` set pointing to files that **do not exist on disk**. All 4 carry `_approval_status=APPROVED`.

**PROOF RECEIPT (R22 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED
    001_M03: 001_M03.jpg approval=APPROVED
    001_M04: 001_M04.jpg approval=APPROVED
    001_M05: 001_M05.jpg approval=APPROVED
CONFIRMS: Identical to R21. 4 ghost entries with APPROVED status persist.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk, chain proceeds from M01 anchor. scene_001_stitched.mp4 (32MB) exists from 2026-03-25. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Classification:** CONFIRMED_BUG (data integrity — ghost frame references). Non-blocking for generation. 8th consecutive report.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 21st consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot, I=0.75). Pattern is self-resolving on next generation run. No code fix required.

**PROOF RECEIPT (R22 live):**
```
PROOF: python3 ledger I-score distribution
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R21)
  UNIQUE_SHOTS: 41
  HEURISTIC_I (I=0.75): 36/41 = 87.8%
  REAL_VLM: 5/41
  REAL_VLM_SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 15h21m (up from 14h21m at R21)
CONFIRMS: No new generation. Identical to R21 distribution.
```

**Classification:** ARCHITECTURAL_DEBT (21st report). Pattern resolves in next generation run if Gemini/OpenRouter fires.

---

### OPEN-003 (STALE_DOC — 21st consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5539. Logic functional (`_fail_sids` at runner:5539 ✅).

**PROOF (R22 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5539 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Cosmetic only. Unchanged from R21.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5539. One line.

**Classification:** STALE_DOC. 21st consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 19th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY. Code default is Kling (runner:527).

**PROOF (R22 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:527: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Docstring wrong, code correct. Unchanged from R21.
```

**Classification:** STALE_DOC. 19th consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (2nd consecutive report, first noted R21)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. Scene 006 is the most complete scene (scene_006_stitched.mp4 exists, all 4 shots have video_url). These 2 shots have generated videos on disk but have not been approved or thumbed-down by the operator.

**PROOF (R22 live):**
```
PROOF: shot_plan approval status scan
OUTPUT: AWAITING_APPROVAL: 2 ['006_M02', '006_M04']
CONFIRMS: Same as R21. No operator action taken.
```

**Impact:** Low. Non-blocking. Existing stitch is complete. Operator should review and approve or regen.

**Classification:** PRODUCTION_GAP (system works, operator action pending). Not a code bug. 2nd consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported by R21.

---

## 6. NEW OBSERVATIONS (R22 only)

### 6.1 Third Consecutive Idle Report

R20, R21, and now R22 are all idle — no generation, no code changes, no data patches. The production system has been in a frozen hold state for 3 consecutive hourly intervals. This is expected if the operator is offline. The system is fully healthy and can proceed the moment operator initiates work.

### 6.2 OPEN-009 Age Assessment

With 11 consecutive reports, OPEN-009 is now tied with OPEN-003/OPEN-002 for report longevity. The fix is trivially simple (8 field edits, zero code, zero generation, ~3 minutes). The only reason it persists is the absence of operator action. This is the clearest demonstration of the META-CHRONIC classification: the issue is not technically hard, the fix loop has simply not been executed. Operator should treat this as a to-do item with near-zero cost.

### 6.3 Ledger Staleness Trend

| Report | Ledger Age |
|--------|-----------|
| R19 | ~13h21m |
| R20 | 13h21m |
| R21 | 14h21m |
| **R22** | **15h21m** |

Staleness growing +60m per report cycle as expected during idle period. Vision backends remain ready (4 backends available, all keys present). System will resume accurate I-scoring on next generation.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 META-CHRONIC (data patch) | 3 min | Strip `/api/media?path=` prefix from 8 fields in shot_plan.json | NO — data hygiene, META-CHRONIC escalation |
| **P2** | OPEN-010 (ghost frames + re-gen 001 M-shots) | 10 min | Clear first_frame_url + reset approval for 001_M02-M05, then --frames-only 001 | NO — UI artifacts + needed before clean videos-only 001 |
| **P3** | 006_M02/M04 AWAITING_APPROVAL | 2 min | Operator review in UI filmstrip → thumbs-up or thumbs-down | NO — production gap |
| **P4** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge fires with Gemini/OpenRouter | NO — observational |
| **P5** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5539 | NO — cosmetic |
| **P5** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**P0 count: 0. No P0 blockers. System ready for generation (pending OPEN-009 P1 data patch — recommended but not required).**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R22: 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (R18 confirmed, R22 unchanged)
□ [P1] Apply OPEN-009 META-CHRONIC patch: normalize 8 API-path fields (008_E01/E02/E03/M03b video_url + first_frame_url)
□ [P2] Apply OPEN-010 patch: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P2] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P2] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P3] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R22 via session_enforcer)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: stitch already complete (scene_008_full_8shots.mp4). Only re-stitch if M03b/M04 are regen'd.
```

---

## 9. DELTA FROM R21

| Signal | R21 | R22 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 1 | 1 | = | OPEN-009 persists at 11th report |
| **CONFIRMED_FIXED** | 22 | 22 | = | 0 regressions |
| **P0 blockers** | 0 | 0 | = | Clean |
| Files modified since R21 | 0 | **0** | = | **System idle — 3rd consecutive** |
| runner mtime | 19:44:43Z | 19:44:43Z | = | Unchanged |
| orchestrator mtime | 19:43:25Z | 19:43:25Z | = | Unchanged |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 14h21m | **15h21m** | **+60m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | Persists — 11th META-CHRONIC report |
| API-path first_frame_url | 4 (OPEN-009) | 4 | = | Persists |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | Persists |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| AWAITING_APPROVAL shots | 2 | 2 | = | 006_M02 + 006_M04 |
| OPEN-002 consecutive | 20 | **21** | **+1** | Arch debt |
| OPEN-003 consecutive | 20 | **21** | **+1** | Cosmetic |
| OPEN-005 consecutive | 18 | **19** | **+1** | Cosmetic |
| OPEN-009 consecutive | 10 | **11** | **+1** | META-CHRONIC |
| OPEN-010 consecutive | 7 | **8** | **+1** | Confirmed bug |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| First_frames on disk | 62 | 62 | = | |
| Shot plan total | 97 | 97 | = | |
| Videos in kling_lite | 30 MP4s | 30 MP4s | = | |
| Stitched scenes | 5 | 5 | = | scene_001/002/004/006/008 |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |

---

## 10. GENERATION READINESS ASSESSMENT (R22)

**Recommended next generation sequence (unchanged from R21):**

```bash
# Step 0 (META-CHRONIC data patch — 3 min):
# Edit shot_plan.json: strip "/api/media?path=" from 8 fields on 008_E01/E02/E03/M03b

# Step 1 (OPEN-010 data patch + re-gen — 10-15 min):
# Edit shot_plan.json: first_frame_url="" + _approval_status="AWAITING_APPROVAL" for 001_M02-M05
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# Review 001_M02-M05 in UI → approve

# Step 2 (Scene 001 videos):
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --videos-only

# Step 3 (Scene 008 regen for M03b + M04):
# After operator reviews scene_008_full_8shots.mp4 and decides to regen M03b/M04:
python3 atlas_universal_runner.py victorian_shadows_ep1 008 --mode lite --videos-only

# Step 4 (006_M02/M04 approval):
# Review in UI filmstrip → thumbs-up → stitch already done, optional re-stitch
```

**Production state: 5 scenes stitched, 2 scenes partial (001, 008). Ready for operator-driven completion once data patches applied.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T00:21:00Z",
  "ledger_age_hours": 15.35,
  "run_number": 22,
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R21_KEEPUP_LATEST.md",
  "meta_chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 11,
      "class": "META-CHRONIC",
      "description": "4 shots (008_E01/E02/E03/M03b) have /api/media?path= prefix in video_url and first_frame_url",
      "proof_receipt": "python3 shot_plan scan → API_PATH_VIDEO_URL: 4, API_PATH_FIRST_FRAME_URL: 4 — identical to R21",
      "fix_recipe": "Strip /api/media?path= prefix from 8 fields in shot_plan.json — no code change",
      "regression_guard": ["session_enforcer still HEALTHY after patch", "do not touch nano_prompt/_beat_action/_approval_status/_chain_group/_arc_position"]
    }
  ],
  "chronic_issues": [
    {
      "id": "OPEN-010",
      "consecutive_reports": 8,
      "class": "CONFIRMED_BUG",
      "description": "4 shots (001_M02-M05) have ghost first_frame_url pointing to non-existent files, all APPROVED",
      "proof_receipt": "python3 os.path.exists check → GHOST_FIRST_FRAME_URLS: 4 — identical to R21",
      "fix_recipe": "Clear first_frame_url + reset to AWAITING_APPROVAL for 001_M02-M05, then --frames-only",
      "regression_guard": ["001_M01.jpg still present on disk", "scene_001_stitched.mp4 preserved"]
    }
  ],
  "false_positives_retracted": [],
  "organ_health": {
    "skeleton": "HEALTHY",
    "liver": "HEALTHY",
    "immune": "DEGRADED",
    "nervous": "HEALTHY",
    "eyes": "DEGRADED",
    "cortex": "DEGRADED",
    "cinematographer": "DEGRADED",
    "editor": "HEALTHY",
    "regenerator": "HEALTHY",
    "doctrine_doc": "DEGRADED"
  },
  "system_idle": true,
  "consecutive_idle_reports": 3,
  "code_changes_since_prior": 0,
  "new_generation_since_prior": 0,
  "session_enforcer_result": "HEALTHY",
  "learning_log_regressions": 0,
  "recommended_next_action": "apply_data_patch_OPEN009_then_generation",
  "p0_blockers": 0,
  "confirmed_fixed_count": 22
}
```

---

*Document lineage: R01 → R02 → … → R20 → R21 → **R22***
*Prior report: ATLAS_ERROR_DEEPDIVE_2026-03-30_R21_KEEPUP_LATEST.md*
*Generated by: ATLAS keep-up automated task (scheduled hourly)*
