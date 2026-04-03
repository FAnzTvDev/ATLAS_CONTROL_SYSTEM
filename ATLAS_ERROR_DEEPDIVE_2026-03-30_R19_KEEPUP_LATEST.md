# ATLAS ERROR DEEPDIVE — 2026-03-30 R19 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T21:15:00Z
**Run number:** R19
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R18_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 12h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 2 CONFIRMED_BUG / 0 META-CHRONIC 🟢 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R18 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | **0** | = | None new |
| **CONFIRMED_BUG** | **2** | = | OPEN-009 (8th) + OPEN-010 (5th) |
| **META-CHRONIC** | **0** | = | Remains cleared since R18 |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 18th report |
| STALE_DOC | 2 | OPEN-003 (18th), OPEN-005 (16th) | Cosmetic |
| **CONFIRMED_FIXED** | **22** | = | 22 confirmed — 0 regressions |
| **CODE CHANGES SINCE R18** | **0 files** | = | System idle |

**Key findings R19:**

1. 🟢 **NO REGRESSIONS. ALL 22 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. 0 blocks. Learning log: 22 fixes, 0 regressions. CPC decontamination (OPEN-004 fix) confirmed still wired at runner:87 (import), runner:2372 (nano path), runner:3206 (Kling path).

2. 🟡 **SYSTEM IDLE — NO GENERATION, NO CODE CHANGES SINCE R18.** Runner mtime unchanged (2026-03-30T19:44:43Z). Orchestrator mtime unchanged (2026-03-30T19:43:25Z). Ledger 12h21m stale (+60m from R18). 228 entries, 41 unique shots. No new files.

3. 🟡 **LEDGER FIELD SCHEMA NOTE (R19 CLARIFICATION):** Prior reports used `I_score`/`V_score`/`C_score` field names in narrative text; actual ledger schema uses single-char keys `I`, `V`, `C`, `R`, `D`, `E`. This has no impact on reported values — the R18 analysis was correct. Confirmed: 36/41 = 87.8% heuristic I=0.75, 5 real-VLM shots. Identical to R18.

4. 🟡 **OPEN-009 PERSISTS (8th consecutive).** 4 shots (008_E01/E02/E03/M03b) retain `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. Data patch pending.

5. 🟡 **OPEN-010 PERSISTS (5th consecutive).** 4 shots (001_M02/M03/M04/M05) retain ghost `first_frame_url` entries pointing to non-existent files, all APPROVED. Non-blocking.

6. 🔵 **VIDEO COVERAGE UNCHANGED.** Scene 006: 4/4 videos (only fully complete scene). Scenes 001-005, 007-013: partial or zero. 30 MP4s total in videos_kling_lite. No new generation.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R19) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes. Bare-list guard at runner:1504. 97/97 arc positions present. 62/62 M-shots with `_chain_group`. | `isinstance(sp, list)` at runner:1504 ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | OPEN-004 resolved R18. `_cpc_decontaminate` imported at runner:87 (try/except non-blocking), called at runner:2372 (nano frame path) and runner:3206 (Kling video path). Runner mtime unchanged — fix persists. | `grep -n "_cpc_decontaminate" runner` → lines 87, 91, 2372, 3206 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 claim Seedance PRIMARY (STALE_DOC-16). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:527). CLAUDE.md V36.5 accurate. | `sed -n '24p'` → "Seedance v2.0 PRIMARY"; runner:527 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (runner:461, 4560), Wire-C (12 combined A/B/C matches), Chain arc (runner:65+4772), all doctrine hooks wired. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available (gemini_vision, openrouter, florence_fal, heuristic). OPEN-010: 4 ghost first_frame_urls. OPEN-009: 4 API-path first_frame_urls. | Enforcer output + env scan R19 ✅ |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 12h21m stale). 87.8% heuristic I=0.75 (latest-per-shot). 5 real-VLM shots: 008_M01(1.0), 008_M02(0.9), 008_M04(0.8), 004_M01(1.0), 004_M02(1.0). Resolves on next generation run with Gemini/OpenRouter active. | Ledger analysis — corrected field `I` (not `I_score`) — same distribution as R18 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 total JPGs in first_frames/ (35 actual first_frames + 27 chain lastframe files). 30 MP4s in videos_kling_lite. Scene 006: 4/4 (only 100% scene). Scenes 001-005/008: partial. OPEN-010: 001_M02-M05 ghost frames. run_report: success=True, errors=[]. | File counts + shot_plan scan R19 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic `_fail_sids` at runner:5539 ✅. `[WIRE-B]` label absent (OPEN-003 cosmetic). 5+ stitched scenes confirmed in stitched_scenes/. | `grep -n "_fail_sids" atlas_universal_runner.py` → runner:5539 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C: 12 combined A/B/C matches. All Wire-C branches intact. Runner unmodified since R18. | `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39) persist. CLAUDE.md V36.5 correct. No code changes since R18. | Same as R18 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

22 items total — all intact, 0 regressions confirmed R19.

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
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R19 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:~1141.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 12 combined A/B/C matches confirmed R19.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:527 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED IN RUNNER** — `_cpc_decontaminate` imported at runner:87 (try/except non-blocking), called at runner:2372 (nano frame path) AND runner:3206 (Kling video path). Runner mtime 19:44:43Z unchanged. Fix persists.

---

## 4. OPEN ISSUES

### OPEN-009 (CONFIRMED_BUG — R12→R19, Non-blocking, 8th consecutive report)

**Issue:** 4 shots (008_E01/E02/E03/M03b) have `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. Files exist at raw paths. Stitch risk for scene 008.

**PROOF RECEIPT (R19 live):**
```
PROOF: python3 shot_plan API-path scan
OUTPUT:
  API_PATH_VIDEO_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
  API_PATH_FIRST_FRAME_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
CONFIRMS: Identical to R18. 8 total affected fields persist.
```

**Impact:** Stitch risk for scene 008 (4 videos excluded from stitch via os.path.exists). 008_M03b also carries `REGEN_REQUESTED`. UI correctly resolves API-path format in browser.

**Fix recipe (data patch only — no code changes required):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   Strip "/api/media?path=" prefix from both video_url and first_frame_url
# Total: 8 field changes
```

**Classification:** CONFIRMED_BUG (data inconsistency). Non-blocking for generation. Stitch risk for scene 008.

---

### OPEN-010 (CONFIRMED_BUG — R15→R19, Non-blocking, 5th consecutive report)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` set pointing to files that **do not exist on disk**. All 4 carry `_approval_status=APPROVED`.

**PROOF RECEIPT (R19 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: pipeline_outputs/.../first_frames/001_M02.jpg  approval=APPROVED
    001_M03: pipeline_outputs/.../first_frames/001_M03.jpg  approval=APPROVED
    001_M04: pipeline_outputs/.../first_frames/001_M04.jpg  approval=APPROVED
    001_M05: pipeline_outputs/.../first_frames/001_M05.jpg  approval=APPROVED
CONFIRMS: Identical to R18. 4 ghost entries with APPROVED status persist.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk, chain proceeds from M01 anchor. Functionally correct for re-run. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Classification:** CONFIRMED_BUG (data integrity — ghost frame references). Non-blocking for generation.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 18th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot, I=0.75). Pattern is self-resolving on next generation run. No code fix required.

**PROOF RECEIPT (R19 live):**
```
PROOF: python3 ledger I-score distribution (field key 'I', not 'I_score')
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged)
  UNIQUE_SHOTS: 41
  HEURISTIC_I (I=0.75): 36/41 = 87.8%
  REAL_VLM (I!=0.75,!=None): 5/41
  REAL_VLM_SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 12h21m (up from 11h21m at R18)
CONFIRMS: No new generation. Identical to R18 distribution.
```

**R19 FIELD SCHEMA CLARIFICATION:** Prior reports referred to `I_score`/`V_score`/`C_score` in narrative text. Actual ledger JSON keys are single-char: `I`, `V`, `C`, `R`, `D`, `E`. The numeric values and analysis have been correct throughout — this is a narrative terminology mismatch only. R19 analysis confirmed using correct key `I`.

**Classification:** ARCHITECTURAL_DEBT (18th report). Pattern resolves in next generation run if Gemini/OpenRouter fires. With OPEN-004 now wired, next run will also exercise CPC decontamination for the first time in production.

---

### OPEN-003 (STALE_DOC — 18th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5539. Logic functional (`_fail_sids` at runner:5539 ✅).

**PROOF (R19 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5539 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Cosmetic only.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5539. One line.

**Classification:** STALE_DOC. 18th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 16th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY. Code default is Kling (runner:527).

**PROOF (R19 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "...ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:527 ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Docstring wrong, code correct.
```

**Classification:** STALE_DOC. 16th consecutive report. Code behavior correct.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 22 confirmed-fixed items intact (R19 live verification). No reclassifications.

---

## 6. NEW OBSERVATIONS (R19 only)

### 6.1 System Fully Idle Since R18

No code files modified, no new generation frames or videos, no data patches applied. This is a pure steady-state report — all signals identical to R18 except:
- Ledger staleness: 11h21m → 12h21m
- OPEN-002 consecutive: 17 → 18
- OPEN-003 consecutive: 17 → 18
- OPEN-005 consecutive: 15 → 16
- OPEN-009 consecutive: 7 → 8
- OPEN-010 consecutive: 4 → 5

### 6.2 Ledger Schema Clarification (Non-blocking)

The reward ledger uses single-character field names (`I`, `V`, `C`, `R`, `D`, `E`). Early in R19 analysis, a check using `I_score`/`V_score`/`C_score` returned all-None, triggering a potential false alarm. Investigation confirmed: R18's reported distribution (87.8% heuristic I=0.75) was correct — prior analysis was using correct key `I` internally. This R19 observation is logged for future schema documentation only.

**No open issue raised** — the ledger is functioning correctly, the prior reports were numerically accurate. This is a terminology consistency note for CLAUDE.md or a future ledger wrapper utility.

### 6.3 Scene 008 Compounded Risk

008_M03b carries BOTH OPEN-009 (API-path prefix on video_url and first_frame_url) AND `REGEN_REQUESTED`. Scene 008 has 4/8 videos — the 4 with valid paths would stitch but the 4 with API-path prefix would be excluded. If operator wants to stitch scene 008, BOTH OPEN-009 patch AND M03b regen must be completed first.

**008_M04 note:** video_url is a valid filesystem path (not API-path). Only 008_M04's first_frame_url uses API-path format. 008_M04's REGEN_REQUESTED status means operator previously thumbed-down — review before proceeding.

### 6.4 CPC Quality Note (Carry-forward from R18)

The R18 observation about CPC output quality remains: replacement text (`"ELEANOR present and grounded in the physical space naturally"`) still contains mildly generic language. This is a calibration concern for the EMOTION_PHYSICAL_MAP, not a wiring failure. Wiring is confirmed. Calibration can be tuned in a future session without risking regressions.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009/010 combined data patch | 3 min | Strip API-path prefix from 8 fields; clear ghost first_frame_url + reset approval for 001_M02-M05 | NO — stitch risk + UI artifacts only |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge will fire with Gemini/OpenRouter active | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5539 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**P0 count: 0. No P0 blockers. System ready for generation after P1 data patches.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R19: 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (R18 confirmed, R19 unchanged)
□ Apply OPEN-009 patch: normalize 8 API-path fields (008_E01/E02/E03/M03b video_url + first_frame_url)
□ Apply OPEN-010 patch: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ Verify vision backends online: gemini_vision + openrouter (confirmed R19 via session_enforcer)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed R18; stable)
□ Verify CPC fired: check runner output for "[CPC] Decontamination import warning" (should NOT appear — means success)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ After generation: spot-check nano_prompt in new shots for absence of generic patterns ("experiences the moment", "present and engaged")
□ Scene 008 stitch: requires OPEN-009 patch + 008_M03b regen first
```

---

## 9. DELTA FROM R18

| Signal | R18 | R19 | Delta | Note |
|--------|-----|-----|-------|------|
| **FALSE_POSITIVES_RETRACTED** | 0 | 0 | = | None |
| **CONFIRMED_FIXED** | 22 | 22 | = | 0 regressions |
| **P0 blockers** | 0 | 0 | = | Clean |
| Files modified since R18 | 2 prod | **0** | **-2** | **System idle** |
| runner mtime | 19:44:43Z | 19:44:43Z | = | Unchanged |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 11h21m | **12h21m** | **+60m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | Persists |
| API-path first_frame_url | 4 (OPEN-009) | 4 | = | Persists |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | Persists |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| OPEN-003 consecutive | 17 | **18** | **+1** | Cosmetic |
| OPEN-005 consecutive | 15 | **16** | **+1** | Cosmetic |
| OPEN-002 consecutive | 17 | **18** | **+1** | Arch debt |
| OPEN-009 consecutive | 7 | **8** | **+1** | Data patch pending |
| OPEN-010 consecutive | 4 | **5** | **+1** | Data patch pending |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| Scenes 100% video | 1 (006) | 1 (006) | = | |
| First_frames on disk | 62 total | 62 total | = | |
| Shot plan total | 97 | 97 | = | |
| Videos in kling_lite | 30 MP4s | 30 MP4s | = | |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |

**R19 summary: Pure steady-state report. No code changes, no new generation, no new bugs. System idle since R18. All 22 confirmed-fixed items intact. 0 P0 blockers. 2 P1 data patches (OPEN-009/010) still pending. OPEN-002 reward signal stale at 12h21m — resolves on next generation run. Session enforcer HEALTHY. CPC decontamination confirmed wired.**

---

## 10. GENERATION READINESS ASSESSMENT (R19)

**Recommended next generation sequence (unchanged from R18):**

```bash
# Step 1: Apply data patches (OPEN-009/010) — human edits shot_plan.json
# Strip "/api/media?path=" from 8 fields (008_E01/E02/E03/M03b video_url + first_frame_url)
# Set first_frame_url="" + _approval_status="AWAITING_APPROVAL" for 001_M02-M05

# Step 2: Re-generate missing 001 M-shots first frames
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# ↑ CPC decontamination now active for first time in production

# Step 3: Generate scene videos (CPC active — first run with decontamination)
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only

# Step 4: Address 008_M03b regen (after OPEN-009 patch)
# → Review 008_M04 (REGEN_REQUESTED but has valid video — operator decision)
```

**Current blockers:**
- ✅ OPEN-004: RESOLVED — CPC decontamination wired (persists R19)
- ⚠️ OPEN-010: Clear 001_M02-M05 ghost first_frame_url + re-generate frames before --videos-only
- ⚠️ OPEN-009: Patch scene 008 video/frame URLs before stitch
- ✅ CIG gate: 0/97 shots blocked
- ✅ Session enforcer: HEALTHY
- ✅ Vision backends: online (4 backends confirmed R19)
- ✅ No P0 blockers

---

## 11. DOCUMENT LINEAGE

- R1-R7: Hourly incremental baseline and consolidation
- R8: OPEN-004 first reported; OPEN-008 first reported (later retracted R13)
- R9-R12: OPEN-008 persisted as P0 (false positive throughout)
- R13: OPEN-008 + OPEN-006 retracted. System cleared of all P0 blockers.
- R14: OPEN-004 advances to CHRONIC-7. No new bugs.
- R15: OPEN-010 NEW. OPEN-009 expanded. OPEN-004 → CHRONIC-8.
- R16: No new bugs. OPEN-004 → CHRONIC-9. P1 priority upgrade.
- R17: No new bugs. **OPEN-004 → META-CHRONIC (10 consecutive). P0 upgrade. Process failure designation.**
- R18: Runner + orchestrator modified post-R17. **OPEN-004 RESOLVED — CPC `decontaminate_prompt` wired in both generation paths. 22nd confirmed-fixed. P0 count: 1→0. META-CHRONIC CLEARED.**
- **R19 (CURRENT):** System idle. No code changes, no new generation. All signals identical to R18 except ledger age (+60m) and consecutive counts (+1 each). 0 new bugs. 0 regressions.

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T21:15:00Z",
  "run_number": 19,
  "prior_report": "R18",
  "system_version": "V36.5",
  "ledger_age_minutes": 741,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 22,
    "confirmed_bug": 2,
    "meta_chronic": 0,
    "architectural_debt": 1,
    "stale_doc": 2,
    "false_positives_retracted": 0,
    "p0_blockers": 0
  },
  "key_signals": {
    "code_files_modified_since_r18": 0,
    "data_files_modified_since_r18": 0,
    "cpc_decontaminate_call_sites": [2372, 3206],
    "cpc_import_line": 87,
    "cig_gate_blocked_shots": 0,
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "api_path_first_frame_urls": 4,
    "ghost_first_frame_urls_missing_file": 4,
    "total_ghost_fields": 12,
    "regen_requested_shots": 2,
    "regen_requested_shot_ids": ["008_M03b", "008_M04"],
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "ledger_age_minutes": 741,
    "ledger_field_schema_note": "Keys are single-char I/V/C/R/D/E — not I_score/V_score/C_score. Narrative terminology corrected R19.",
    "shots_with_video_url_in_plan": 28,
    "real_video_urls_excluding_api_path": 24,
    "first_frame_jpgs_on_disk_total": 62,
    "first_frame_jpgs_actual_shot_frames": 35,
    "first_frame_jpgs_chain_lastframe_files": 27,
    "shots_with_first_frame_url_in_plan": 39,
    "shots_with_valid_first_frame_url": 35,
    "mp4_files_videos_kling_lite": 30,
    "mp4_files_videos_dir": 0,
    "scenes_100pct_video": ["006"],
    "scenes_partial_video": ["001", "002", "003", "004", "008"],
    "scenes_no_video": ["005", "007", "009", "010", "011", "012", "013"],
    "p0_blockers": 0,
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13,
    "run_report_success": true,
    "learning_log_fixes": 22,
    "learning_log_regressions": 0,
    "arc_positions_present": 97,
    "chain_groups_present": 62,
    "approval_status": {
      "APPROVED": 29,
      "AUTO_APPROVED": 6,
      "AWAITING_APPROVAL": 2,
      "REGEN_REQUESTED": 2,
      "empty": 58
    }
  },
  "false_positives_retracted": [],
  "open_issues": [
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 8,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "affected_fields": ["video_url", "first_frame_url"],
      "total_affected_fields": 8
    },
    {
      "id": "OPEN-010",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 5,
      "affected_shots": ["001_M02", "001_M03", "001_M04", "001_M05"],
      "description": "first_frame_url set but file missing. APPROVED status. Non-blocking for --videos-only."
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "consecutive_reports": 18
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 18
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 16
    }
  ],
  "newly_resolved": [],
  "system_idle_since": "2026-03-30T19:44:43Z",
  "generation_readiness": {
    "scenes_ready_for_video_after_patch": ["001", "002", "003", "004"],
    "scenes_need_frames_first": ["005", "007", "009", "010", "011", "012", "013"],
    "gate_blocking_any_scene": false,
    "p0_blockers": 0,
    "pre_condition_001": "Clear OPEN-010 ghost first_frame_urls + re-run --frames-only 001 + re-approve M02-M05",
    "recommended_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only",
    "cpc_decontamination_active": true,
    "note": "Next generation will be first production run with CPC decontamination active end-to-end"
  },
  "recommended_next_action": "apply_p1_data_patches_then_frames_only_001_then_videos_only_001_004"
}
```

---

**END REPORT**

*ATLAS R19 — Keep-up detection complete. Pure steady-state. 0 P0 blockers. 0 new bugs. 0 regressions. 22 confirmed-fixed intact. System idle since R18 (no code changes, no generation). Ledger 12h21m stale. OPEN-009/010 data patches (P1) pending. Session enforcer HEALTHY. CPC decontamination confirmed wired. Next generation run will be first production exercise of CPC decontamination end-to-end.*
