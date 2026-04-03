# ATLAS ERROR DEEPDIVE — 2026-03-31 R25 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T03:12:32Z
**Run number:** R25
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R24_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 18h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R24 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (14th) + OPEN-010 (11th) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 24th report |
| STALE_DOC | 2 | OPEN-003 (24th), OPEN-005 (22nd) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R24** | **0** | = | Runner + orchestrator unchanged |
| **DATA CHANGES SINCE R24** | **0** | = | shot_plan.json unchanged (mtime: 20:22:12 EDT same as R24) |
| **GENERATION SINCE R24** | **0 frames, 0 videos** | = | **System idle — 6th consecutive idle report** |

**Key findings R25:**

1. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes, 0 regressions. Runner mtime 15:44:43 EDT — unchanged since R24. Orchestrator mtime 15:43:25 EDT — unchanged.

2. 🔴 **OPEN-009 META-CHRONIC: 14th consecutive report (R12→R25).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied since R23 first_frame_url fix. This is a ~2 min edit that has remained undone for 14 cycles.

3. 🔴 **OPEN-010 META-CHRONIC: 11th consecutive report (R15→R25).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all stamped APPROVED. Escalated to META-CHRONIC at R24 (10-report threshold). No operator action since escalation.

4. 🟡 **SYSTEM IDLE — 6th consecutive idle report (R20–R25).** No new generation, no code changes, no data changes. Ledger age: 18h21m (+60m from R24). System fully operational and ready to generate.

5. 🟡 **006_M02/M04 AWAITING_APPROVAL (5th consecutive report, R21–R25).** No operator action. 008_M03b/M04 also remain REGEN_REQUESTED.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R25) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1504. 97/97 arc positions. 62 M-shots with `_chain_group`. | `isinstance(sp, list)` at runner:1504 ✅; shot_plan loads cleanly ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` at 4 locations in runner (lines 87, 91, 2372, 3206). Runner mtime unchanged. | `grep -c "_cpc_decontaminate" runner` → 4 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 22nd). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:527). CLAUDE.md V36.5 accurate. | runner:24 → Seedance claim; runner:527 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (6 hits), Wire-C (6 hits), Wire-B logic at 5539 (label absent). Chain arc wired. | Session enforcer output R25 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available. OPEN-009: 4 API-path video_urls (14th). OPEN-010: 4 ghost first_frame_urls (11th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 18h21m stale). 87.8% heuristic I=0.75 (last-entry-per-shot basis). 5 real-VLM shots: 008_M01/M02/M04, 004_M01/M02. Resolves on next generation. | Ledger scan R25 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/. 6 scenes with `_lite.mp4`. OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED. run_report: success=True, errors=[]. | File counts + shot_plan scan R25 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5539 ✅. 6 lite stitch files: scene001 (18M), scene002 (21M), scene003 (15M), scene004 (21M), scene006 (8.5M), scene008 (6.9M). | `grep -n "_fail_sids"` → runner:5539 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits. Wire-C: 6 hits. Combined 12 (A+C; B label absent but logic intact). Runner unmodified since R24. | `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (22nd). CLAUDE.md V36.5 correct. No code changes. | Same as R24 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R25. Identical to R24.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
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
✅ **V37 GOVERNANCE HOOKS** — 4 lines in runner (runner:300/302/5040/5474), 7 endpoints in orchestrator.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R25 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 12 combined A/C matches confirmed R25.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:527 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at runner:87, 2372, 3206.
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (14 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R25 status vs R24:** UNCHANGED. No data patch applied since R23 was written.

**META-CHRONIC STATUS:** 14 consecutive reports (R12→R25). ~2 min edit has not been applied in 14 cycles.

**PROOF RECEIPT (R25 live):**
```
PROOF: python3 -c "import json; sp=json.load(open('pipeline_outputs/victorian_shadows_ep1/shot_plan.json')); shots=sp if isinstance(sp,list) else sp.get('shots',[]); api_video=[s['shot_id'] for s in shots if '/api/media' in str(s.get('video_url',''))]; print(api_video)"
OUTPUT: ['008_E01', '008_E02', '008_E03', '008_M03b']
CONFIRMS: 4 video_url fields still carry /api/media?path= prefix. first_frame_url: 0 affected (FIXED R23).
```

**Remaining fix (data patch only — no code changes):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   video_url = video_url.replace("/api/media?path=", "")
# Total: 4 field changes
# Verify: grep "/api/media" shot_plan.json | wc -l → should return 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url` (just fixed in R23), `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` still HEALTHY.

**Classification:** META-CHRONIC (14th report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (11 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 11th consecutive report.

**R25 status vs R24:** UNCHANGED. No operator action taken since META-CHRONIC escalation at R24.

**PROOF RECEIPT (R25 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R24. 11th consecutive confirmation. META-CHRONIC escalated at R24.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk. scene001_lite.mp4 (18M) was generated using the chain from M01. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk. scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05.

**Classification:** META-CHRONIC (11th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 24th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger frozen at 228 entries for 18h21m.

**PROOF RECEIPT (R25 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R24)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 = [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 18h21m (up +60m from R24's 17h21m)
CONFIRMS: No new generation. Identical to R24 distribution.
```

**Note:** I-score distribution includes both 0.75 heuristic entries and entries with I ∈ {0.0, 0.08, 0.15} from early production runs (poor VLM scores, not heuristic). Per last-entry-per-shot accounting (most recent), 87.8% remain at 0.75. Raw entry distribution: I=0.75: 161/228 entries; I=1.0: 31 entries; I=0.9: 6; I=0.8: 5; I=0.0: 5; I=0.08: 8; other: 12.

**Classification:** ARCHITECTURAL_DEBT (24th report). Resolves on next generation run. Vision backends available (4 backends, all keys present).

---

### OPEN-003 (STALE_DOC — 24th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5539. Logic functional (`_fail_sids` at runner:5539 confirmed ✅).

**PROOF (R25 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5539 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Cosmetic only. Unchanged from R24.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5539. One line.

**Classification:** STALE_DOC. 24th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 22nd consecutive report)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:527).

**PROOF (R25 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:527: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Docstring wrong, code correct. Unchanged from R24.
```

**Classification:** STALE_DOC. 22nd consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (5th consecutive report, R21–R25)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. Scene 006 is complete (scene006_lite.mp4 exists, 8.5M, dated 2026-03-29 17:54). Videos generated but not approved or regen'd by operator.

**Also:** 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21.

**PROOF (R25 live):**
```
PROOF: shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 5th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 5th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R24.

---

## 6. NEW OBSERVATIONS (R25 only)

### 6.1 I-Score Methodology Clarification

R25 confirms: the 87.8% heuristic figure (R24 protocol) is based on **last-entry-per-shot** accounting. The raw entry distribution reveals 67/228 entries with I ≠ 0.75 (29.4% of all entries are non-heuristic). This is not a new finding — it is consistent with R24 — but the raw entry data shows real VLM scoring did fire meaningfully on later production runs (scenes 004, 006, 008). The distribution improvement will resume on the next generation run.

### 6.2 Sixth Consecutive Idle Report

R20–R25 = 6 consecutive reports with zero new generation. This is the longest idle streak since initial production. Key metrics stable:
- Runner: unchanged (mtime 15:44:43 EDT, R24→R25 identical)
- Orchestrator: unchanged (mtime 15:43:25 EDT)
- shot_plan.json: unchanged (mtime 20:22:12 EDT)
- Learning log: 22 fixes, 0 regressions

System at complete rest but fully operational.

### 6.3 Ledger Staleness Trend (6-Report View)

| Report | Ledger Age |
|--------|-----------|
| R20 | 13h21m |
| R21 | 14h21m |
| R22 | 15h21m |
| R23 | 16h21m |
| R24 | 17h21m |
| **R25** | **18h21m** |

Staleness growing exactly +60m per report cycle. Clean 1h interval confirms automated keep-up is running on schedule.

### 6.4 META-CHRONIC Persistence Summary

Both META-CHRONIC issues have been documented with identical fix recipes since their first appearance. Neither has received operator action:

| Issue | First Appeared | META-CHRONIC Since | Consecutive Idle Reports Since Escalation |
|-------|---------------|-------------------|------------------------------------------|
| OPEN-009 (video_url patch) | R12 | R12 (META-CHRONIC from start) | 6 (R20–R25) |
| OPEN-010 (ghost frames regen) | R15 | R24 (escalated at 10-report threshold) | 2 (R24–R25) |

Combined fix time: ~12 min. Neither issue blocks active generation.

### 6.5 No Proof Gate Report Available

No `ATLAS_PROOF_GATE_*.md` files found in the workspace. Proof gate classifications are not available to override keep-up classifications this cycle.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 REMAINING (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, 14th META-CHRONIC |
| **P1** | OPEN-010 (ghost frames + re-gen 001 M-shots) | 10 min | Clear first_frame_url + reset approval for 001_M02-M05, then --frames-only 001 | NO — but META-CHRONIC data integrity risk if re-stitch attempted |
| **P2** | 006_M02/M04 AWAITING_APPROVAL | 2 min | Operator review in UI → thumbs-up or thumbs-down | NO — production gap |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge fires with Gemini/OpenRouter | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5539 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**P0 count: 0. No P0 blockers. System ready for generation.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R25: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (R18 confirmed, R25 unchanged)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R25 via session_enforcer)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4, 6.9M). Only re-stitch if M03b/M04 regen'd.
```

---

## 9. DELTA FROM R24

| Signal | R24 | R25 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (14th) + OPEN-010 (11th) |
| **OPEN-009 consecutive** | 13 | **14** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 10 | **11** | **+1** | No operator action since META-CHRONIC escalation |
| **CONFIRMED_FIXED** | 23 | 23 | = | No new items |
| Code files modified since R24 | 0 | **0** | = | Runner + orchestrator unchanged |
| runner mtime | 15:44:43 EDT | 15:44:43 EDT | = | Unchanged |
| orchestrator mtime | 15:43:25 EDT | 15:43:25 EDT | = | Unchanged |
| shot_plan.json mtime | 20:22:12 EDT | 20:22:12 EDT | = | **Unchanged — 2nd consecutive fully static report** |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 17h21m | **18h21m** | **+60m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | 14th META-CHRONIC |
| API-path first_frame_url | 0 (FIXED R23) | 0 | = | Confirmed fixed |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | 11th META-CHRONIC |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| AWAITING_APPROVAL shots | 2 | 2 | = | 006_M02 + 006_M04 |
| OPEN-002 consecutive | 23 | **24** | **+1** | Arch debt |
| OPEN-003 consecutive | 23 | **24** | **+1** | Cosmetic |
| OPEN-005 consecutive | 21 | **22** | **+1** | Cosmetic |
| 006_M02/M04 consecutive | 4 | **5** | **+1** | Production gap |
| Session enforcer | HEALTHY | HEALTHY | = | |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| First_frames on disk | 62 | 62 | = | |
| Videos in kling_lite | 62 total | 62 total | = | |
| Lite stitches (.mp4) | 6 scenes | 6 scenes | = | scene001-004,006,008 |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |
| P0 blockers | 0 | 0 | = | Clean |
| Idle code reports | 5 | **6** | **+1** | R20-R25 |

---

## 10. GENERATION READINESS ASSESSMENT (R25)

**System is fully operational. Two META-CHRONIC data patches recommended before generation.**

**Recommended next generation sequence:**

```bash
# Step 0 (META-CHRONIC data patch OPEN-009 — 2 min):
# Edit shot_plan.json: strip "/api/media?path=" from video_url on 008_E01/E02/E03/M03b

# Step 1 (META-CHRONIC data patch OPEN-010 + re-gen — 10-15 min):
# Edit shot_plan.json: first_frame_url="" + _approval_status="AWAITING_APPROVAL" for 001_M02-M05
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# Review 001_M02-M05 in UI → approve

# Step 2 (Scene 001 videos):
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --videos-only

# Step 3 (Scene 008 regen for M03b + M04 if desired):
python3 atlas_universal_runner.py victorian_shadows_ep1 008 --mode lite --videos-only

# Step 4 (006_M02/M04 approval):
# Review in UI filmstrip → thumbs-up → optional re-stitch
```

**Production state: 6 scenes with lite stitch (001/002/003/004/006/008). Scene 001 M-shots need re-generation (OPEN-010 META-CHRONIC). Scene 008 M03b/M04 need REGEN_REQUESTED resolution. Total ~12 min data patches + ~30 min generation to reach clean state.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T03:12:32Z",
  "ledger_age_hours": 18.35,
  "run_number": 25,
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-31_R24_KEEPUP_LATEST.md",
  "meta_chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 14,
      "class": "META-CHRONIC",
      "description": "4 shots (008_E01/E02/E03/M03b) still have /api/media?path= prefix in video_url. first_frame_url RESOLVED (R23).",
      "progress_this_cycle": "No change from R24. video_url patch not applied.",
      "proof_receipt": "python3 scan → API_PATH_VIDEO_URL: ['008_E01','008_E02','008_E03','008_M03b']",
      "fix_recipe": "Strip /api/media?path= from video_url on 008_E01/E02/E03/M03b — no code change, ~2 min",
      "regression_guard": ["session_enforcer still HEALTHY after patch", "do not touch first_frame_url (fixed R23)"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 11,
      "class": "META-CHRONIC",
      "description": "4 shots (001_M02-M05) have ghost first_frame_url pointing to non-existent files, all APPROVED. Escalated from CONFIRMED_BUG at R24 (10-report threshold).",
      "progress_this_cycle": "No change from R24. No operator action since META-CHRONIC escalation.",
      "proof_receipt": "python3 os.path.exists check → GHOST_FIRST_FRAME_URLS: 4 — 001_M02/M03/M04/M05 all missing",
      "fix_recipe": "Clear first_frame_url + reset to AWAITING_APPROVAL for 001_M02-M05, then --frames-only",
      "regression_guard": ["001_M01.jpg still present on disk", "scene001_lite.mp4 preserved"]
    }
  ],
  "chronic_issues": [],
  "false_positives_retracted": [],
  "newly_confirmed_fixed": [],
  "newly_escalated": [],
  "organ_health": {
    "skeleton": "HEALTHY",
    "liver": "HEALTHY",
    "immune": "DEGRADED",
    "nervous": "HEALTHY",
    "eyes": "SICK",
    "cortex": "DEGRADED",
    "cinematographer": "DEGRADED",
    "editor": "HEALTHY",
    "regenerator": "HEALTHY",
    "doctrine_doc": "DEGRADED"
  },
  "system_idle": true,
  "consecutive_idle_code_reports": 6,
  "data_patch_applied_since_prior": false,
  "code_changes_since_prior": 0,
  "new_generation_since_prior": 0,
  "session_enforcer_result": "HEALTHY",
  "session_enforcer_pass_count": "HEALTHY (no blocks)",
  "learning_log_regressions": 0,
  "recommended_next_action": "apply_both_meta_chronic_data_patches_then_generation",
  "p0_blockers": 0,
  "confirmed_fixed_count": 23,
  "meta_chronic_count": 2,
  "stale_doc_count": 2,
  "architectural_debt_count": 1,
  "production_gap_count": 1,
  "new_issues_this_cycle": 0,
  "key_note": "System fully idle R20-R25 (6 cycles). All 23 confirmed-fixed items intact. No regressions. Both META-CHRONIC issues unresolved — combined ~12 min fix."
}
```

---

*Document lineage: R01 → R02 → … → R23 → R24 → **R25***
*Prior report: ATLAS_ERROR_DEEPDIVE_2026-03-31_R24_KEEPUP_LATEST.md*
*Generated by: ATLAS keep-up automated task (scheduled hourly)*
