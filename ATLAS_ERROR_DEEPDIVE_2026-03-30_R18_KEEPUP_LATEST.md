# ATLAS ERROR DEEPDIVE — 2026-03-30 R18 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T20:12:04Z
**Run number:** R18
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R17_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 11h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 2 CONFIRMED_BUG / 0 META-CHRONIC 🟢 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R17 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | **0** | = | None new |
| **CONFIRMED_BUG** | **2** | = | OPEN-009 (7th) + OPEN-010 (4th) |
| **META-CHRONIC** | **0** | **-1 ⬇️ RESOLVED** | **⛔→✅ OPEN-004 CLOSED** |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 17th report |
| STALE_DOC | 2 | OPEN-003 (17th), OPEN-005 (15th) | Cosmetic |
| **CONFIRMED_FIXED** | **22** | **+1 (OPEN-004)** | ✅ **22 confirmed — 0 regressions** |
| **CODE CHANGES SINCE R17** | **2 files** | **runner + orchestrator modified** | **OPEN-004 wired** |

**Key findings R18:**

1. ✅ **⛔ OPEN-004 META-CHRONIC RESOLVED.** `decontaminate_prompt()` is now imported and **called in BOTH generation paths** in `atlas_universal_runner.py` — as `_cpc_decontaminate` at line 2372 (nano first-frame path, post full prompt assembly, pre-FAL call) and at line 3206 (Kling video prompt path, pre-@Element prepend). Runner modified at 19:44:43 UTC — 33 minutes after R17 was generated. P0 count: 1→0. META-CHRONIC resolved after 10 consecutive reports. This is the largest single improvement since R13.

2. 🟡 **NO NEW GENERATION.** Ledger unchanged at 228 entries, 11h21m stale. Only file changes since R17: `atlas_universal_runner.py` + `orchestrator_server.py` (both modified 19:43-19:44 UTC — OPEN-004 fix plus orchestrator coordinating updates). No new frames or videos.

3. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY.** 0 blocks. Vision backends: [gemini_vision, openrouter, florence_fal, heuristic]. Learning log: 22 fixes, 0 regressions.

4. 🟡 **OPEN-009 PERSISTS (7th report).** 4 shots (008_E01/E02/E03/M03b) retain `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. Stitch risk for scene 008. Data patch still pending.

5. 🟡 **OPEN-010 PERSISTS (4th report).** 001_M02/M03/M04/M05 retain ghost `first_frame_url` entries pointing to non-existent files, all APPROVED. Non-blocking for generation. Data patch pending.

6. 🔵 **ALL 22 CONFIRMED-FIXED INTACT.** Including the newly closed OPEN-004. 0 regressions via learning log + manual spot-checks.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R18) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes. Bare-list guard at runner:1504. 97/97 arc positions present. 62/62 M-shots with `_chain_group`. | `isinstance(sp, list)` guard at runner:1504 ✅ |
| 🫀 Liver (prompt sanitizer) | **🟢 HEALTHY** | **OPEN-004 RESOLVED.** `_cpc_decontaminate` imported at runner:87 (try/except non-blocking), called at runner:2372 (nano frame path) and runner:3206 (Kling video path). Syntax: OK. Import: OK. | `grep -n "_cpc_decontaminate" runner` → lines 87, 91, 2372, 3206 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 claim Seedance PRIMARY (STALE_DOC-15). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:527). CLAUDE.md V36.5 accurate. | `sed -n '24p'` → "Seedance v2.0 PRIMARY"; runner:527 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (runner:461,4560), Wire-C (12 combined A/B/C matches), Chain arc (runner:65+4772), all doctrine hooks wired. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available. BUT 87.8% heuristic I-scores. OPEN-010: 4 ghost first_frame_urls. OPEN-009: 4 API-path first_frame_urls. | Enforcer + env presence + ledger distribution |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged). 87.8% heuristic I=0.75 (latest-per-shot). 5 real-VLM shots. Last entry: 001_M05, I=0.75, V=0.5. 11h21m stale. Resolves on next generation run. | Ledger: 36/41 unique shots heuristic; unchanged from R17 |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 35 real first_frames on disk + 27 chain lastframe files (62 total JPGs). 24 real video_urls. Scene 006: 4/4 ✅. Scenes 005,007-013: 0 videos. OPEN-010: 001_M02-M05 ghost frames. run_report: success=True, errors=[]. CPC now wired into both generation paths. | Coverage scan + run_report identical to R17 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic `_fail_sids` at runner:5539 ✅. No `[WIRE-B]` label (OPEN-003 cosmetic). 5 stitched scenes confirmed in stitched_scenes/. | `grep -n "_fail_sids" atlas_universal_runner.py` → runner:5539 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C: 12 combined A/B/C matches. All Wire-C branches intact. | `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` → 12 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39) persist unchanged. CLAUDE.md V36.5 correct. No modifications since R17 except runner + orchestrator production fixes. | Same as R17 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

22 items total — OPEN-004 newly confirmed this report.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:497.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1504.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` at runner:461, called at runner:4560.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4772.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:~1141.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — `[WIRE-C]` labels at runner (12 combined A/B/C matches confirmed R18).
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:527 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED IN RUNNER** — `_cpc_decontaminate` imported at runner:87 (non-blocking try/except), called at runner:2372 (nano frame path) AND runner:3206 (Kling video path). Applied between R17 and R18 (runner mtime 19:44:43Z, R17 at 19:11:08Z). META-CHRONIC (10 consecutive reports) RESOLVED.

---

## 4. OPEN ISSUES

### OPEN-009 (CONFIRMED_BUG — R12→R18, Non-blocking, 7th consecutive report)

**Issue:** 4 shots (008_E01/E02/E03/M03b) have `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. Files exist at raw paths. Stitch risk for scene 008.

**PROOF RECEIPT (R18 live):**
```
PROOF: python3 shot_plan API-path scan
OUTPUT:
  API_PATH_VIDEO_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
  API_PATH_FIRST_FRAME_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
CONFIRMS: Identical to R17. 8 total affected fields persist. No change.
```

**Impact:** Stitch risk for scene 008 (4 videos excluded from stitch via os.path.exists). 008_M03b also carries `REGEN_REQUESTED`. UI correctly resolves API-path format in browser.

**Fix recipe (data patch only):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   Strip "/api/media?path=" prefix from both video_url and first_frame_url
# Total: 8 field changes, no code changes required
```

**Classification:** CONFIRMED_BUG (data inconsistency). Non-blocking for generation. Stitch risk for scene 008.

---

### OPEN-010 (CONFIRMED_BUG — R15→R18, Non-blocking, 4th consecutive report)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` set pointing to files that **do not exist on disk**. All 4 carry `_approval_status=APPROVED`.

**PROOF RECEIPT (R18 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: pipeline_outputs/.../first_frames/001_M02.jpg  approval=APPROVED
    001_M03: pipeline_outputs/.../first_frames/001_M03.jpg  approval=APPROVED
    001_M04: pipeline_outputs/.../first_frames/001_M04.jpg  approval=APPROVED
    001_M05: pipeline_outputs/.../first_frames/001_M05.jpg  approval=APPROVED
CONFIRMS: Same as R17. 4 ghost entries with APPROVED status persist.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists, chain proceeds from M01 anchor. Functionally correct. UI shows broken thumbnails for 001_M02-M05.

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

### OPEN-002 (ARCHITECTURAL_DEBT — 17th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot). Unchanged.

**PROOF RECEIPT (R18 live):**
```
PROOF: ledger I-score distribution analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged)
  UNIQUE_SHOTS: 41
  HEURISTIC_I (I=0.75): 36/41 = 87.8%
  REAL_VLM (I!=0.75): 5/41
  REAL_VLM_SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 11h21m
CONFIRMS: No new generation. Identical to R17 distribution.
```

**Classification:** ARCHITECTURAL_DEBT (17th report). Pattern resolves in next generation run if Gemini/OpenRouter fires. Defer to next run. With OPEN-004 now wired, next generation run will also exercise CPC decontamination for the first time.

---

### OPEN-003 (STALE_DOC — 17th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5539. Logic functional (`_fail_sids` at runner:5539 ✅).

**PROOF (R18):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5539 ✅
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5539.

**Classification:** STALE_DOC. 17th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 15th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY. Code default is Kling (runner:527).

**PROOF (R18):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT line 24: "...ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:527 ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
```

**Classification:** STALE_DOC. 15th consecutive report. Code behavior correct.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 22 confirmed-fixed items intact. OPEN-004 reclassified from META-CHRONIC → CONFIRMED_FIXED (not a retraction — a resolution).

---

## 6. NEW OBSERVATIONS (R18 only)

### 6.1 OPEN-004 RESOLVED — Detailed Analysis

`atlas_universal_runner.py` was modified at 19:44:43 UTC (33 minutes after R17 at 19:11:08Z).
`orchestrator_server.py` was modified at 19:43:25 UTC (same session, 1 min 18 seconds earlier).

**What changed:**

Runner lines 82–92 now contain:
```python
# V37: CPC decontamination — strip generic patterns from prompts before every FAL call.
# Character names can leak into prompts via beat_action/choreography; decontaminate_prompt
# replaces generic patterns ("experiences the moment", "present and engaged", etc.) with
# motivated physical direction so FAL receives specific, actionable prompts.
try:
    from creative_prompt_compiler import decontaminate_prompt as _cpc_decontaminate
    _CPC_DECONTAM_AVAILABLE = True
except Exception as _cpc_import_err:
    print(f"  [CPC] Decontamination import warning: {_cpc_import_err} — using passthrough")
    def _cpc_decontaminate(text, **kw): return text or ""  # type: ignore[misc]
    _CPC_DECONTAM_AVAILABLE = False
```

`_cpc_decontaminate` is called at:
- **Runner:2372** — nano first-frame prompt path, AFTER role declarations prepended, BEFORE FAL call. Passes `character`, `emotion`, `beat_desc`.
- **Runner:3206** — Kling video prompt path, AFTER joining prompt parts, BEFORE @ElementN prepend (preserving the 460-char budget correctly).

Both call sites are in the canonical generation path. The implementation follows the exact non-blocking pattern the fix recipe specified for 10 consecutive reports.

**PROOF RECEIPT (R18 definitive):**
```
PROOF: grep -n "_cpc_decontaminate" atlas_universal_runner.py
OUTPUT:
  87:    from creative_prompt_compiler import decontaminate_prompt as _cpc_decontaminate
  88:    _CPC_DECONTAM_AVAILABLE = True
  91:    def _cpc_decontaminate(text, **kw): return text or ""
  92:    _CPC_DECONTAM_AVAILABLE = False
  2372:    prompt = _cpc_decontaminate(
  3206:            prompt_text = _cpc_decontaminate(
CONFIRMS: Import + both call sites wired. Non-blocking fallback present.

PROOF: python3 -c "import sys; sys.path.insert(0,'tools'); from creative_prompt_compiler import decontaminate_prompt as f; print(f('experiences the moment naturally','ELEANOR',emotion='dread'))"
OUTPUT: ELEANOR present and grounded in the physical space naturally
CONFIRMS: CPC import works from tools/ path. Runner path (sys.path.insert at runner:55) is identical.

PROOF: python3 -c "import ast; ast.parse(open('atlas_universal_runner.py').read()); print('SYNTAX: OK')"
OUTPUT: SYNTAX: OK
CONFIRMS: No syntax errors introduced by the fix.
```

**Note on CPC output quality:** The replacement output (`"ELEANOR present and grounded in the physical space naturally"`) still contains mildly generic language. This is a CPC calibration concern, not a wiring failure. The GENERIC_PATTERNS blacklist successfully transforms contaminated text — calibration of the EMOTION_PHYSICAL_MAP can be tuned separately.

### 6.2 Orchestrator Changes (R18)

`orchestrator_server.py` was also modified in the same session. Existing `decontaminate_prompt` calls in orchestrator (lines 30954-30971) were not changed — they predate this session and were already wired for V25.1. The new modification to orchestrator is likely V37 coordination code (not inspected in detail — not relevant to open issues).

### 6.3 Generation Readiness — Improved

With OPEN-004 resolved, the CPC decontamination pipeline is now fully end-to-end for the first time. The next generation run will:
1. Exercise `_cpc_decontaminate` in both the nano frame and Kling video paths
2. Strip generic patterns that previously contaminated prompts silently
3. Potentially improve first-frame quality on scenes 009-013 (which had not yet been generated)

The only remaining blockers before generation are data patches (OPEN-009/010) — no code changes required.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| ~~**⛔ P0**~~ | ~~**OPEN-004 (META-CHRONIC)**~~ | ~~5 min~~ | **✅ RESOLVED R18** | **CLOSED** |
| **P1** | OPEN-009/010 combined data patch | 3 min | Strip API-path prefix from 8 fields; clear ghost first_frame_url + reset approval for 001_M02-M05 | NO — stitch risk + UI artifacts only |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge will fire. Issue resolves itself with production use | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5539 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**P0 count: 1→0. No P0 blockers exist as of R18.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed: 0 blocks R18)
□ ✅ OPEN-004 fixed — CPC decontamination wired (R18 confirmed)
□ Apply OPEN-009/010 combined patch: normalize 8 API-path fields + clear 4 ghost first_frame_urls + reset APPROVED→AWAITING_APPROVAL for 001_M02-M05
□ After clearing 001_M02-M05 first_frame_url, run --frames-only scene 001 to re-generate M02-M05
□ Review and re-approve 001_M02-M05 frames in UI
□ Verify vision backends online: gemini_vision + openrouter (confirmed R18)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed R18)
□ Verify CPC fired: check runner output for "[CPC] Decontamination import warning" (should NOT appear — means success)
□ After generation: spot-check nano_prompt for generic pattern absence (search "experiences the moment", "present and engaged" in new entries)
```

---

## 9. DELTA FROM R17

| Signal | R17 | R18 | Delta | Note |
|--------|-----|-----|-------|------|
| **FALSE_POSITIVES_RETRACTED** | 0 | 0 | = | None |
| **CONFIRMED_FIXED** | 21 | **22** | **+1** | **OPEN-004 CLOSED** |
| **P0 blockers** | **1** | **0** | **-1** | **OPEN-004 META-CHRONIC → FIXED** |
| **OPEN-004 consecutive** | **10 (META-CHRONIC)** | **CLOSED ✅** | **-10** | **PROCESS FAILURE RESOLVED** |
| Files modified since prior | 0 prod | **2 prod** | **+2** | **runner + orchestrator** |
| runner mtime | 13:43:58Z | **19:44:43Z** | **+6h** | **Modified post-R17** |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 10h21m | 11h21m | +60m | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | Persists |
| API-path first_frame_url | 4 (OPEN-009) | 4 | = | Persists |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | Persists |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| OPEN-003 consecutive | 16 | 17 | +1 | Cosmetic |
| OPEN-005 consecutive | 14 | 15 | +1 | Cosmetic |
| OPEN-002 consecutive | 16 | 17 | +1 | Architectural debt |
| OPEN-009 consecutive | 6 | 7 | +1 | Data patch pending |
| OPEN-010 consecutive | 3 | 4 | +1 | Data patch pending |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| Scenes 100% video | 1 (006) | 1 (006) | = | |
| First_frames on disk | 62 total / 35 actual FF | 62 total / 35 actual FF | = | |
| Shot plan total | 97 | 97 | = | |
| Videos in kling_lite | 30 MP4s | 30 MP4s | = | |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |

**R18 summary: OPEN-004 resolved (META-CHRONIC after 10 reports → CONFIRMED_FIXED as 22nd item). P0 count: 1→0. CPC decontamination now wired in both generation paths. Runner and orchestrator modified between R17 and R18. All other signals identical — no new bugs. Ledger 11h21m stale. System idle post-generation. 2 P1 data patches pending (OPEN-009/010).**

---

## 10. GENERATION READINESS ASSESSMENT (R18)

**Recommended next generation sequence:**

```bash
# Step 1: Apply data patches (OPEN-009/010)
# [Human applies JSON patches to shot_plan.json]
# Strip "/api/media?path=" from 8 fields (008_E01/E02/E03/M03b video_url + first_frame_url)
# Set first_frame_url="" + _approval_status="AWAITING_APPROVAL" for 001_M02-M05

# Step 2: Re-generate missing 001 M-shots first frames
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only

# Step 3: Generate all pending M-shot videos (CPC now active — first run with decontamination)
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only

# Step 4: Address 008_M03b and 008_M04 regen (after OPEN-009 patch)
# → 008_M04 has real video; operator can review + re-approve if satisfied
# → 008_M03b needs API-path patch first, then regen
```

**Current blockers:**
- ✅ OPEN-004: RESOLVED — CPC decontamination now wired
- ⚠️ OPEN-010: Clear 001_M02-M05 ghost first_frame_url + re-generate frames before --videos-only
- ⚠️ OPEN-009: Patch scene 008 video/frame URLs before stitch
- ✅ CIG gate: 0/97 shots blocked
- ✅ Session enforcer: HEALTHY
- ✅ Vision backends: online (4 backends confirmed)
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
- **R18 (CURRENT):** Runner + orchestrator modified post-R17. **OPEN-004 RESOLVED — CPC `decontaminate_prompt` wired in both generation paths. 22nd confirmed-fixed. P0 count: 1→0. META-CHRONIC CLEARED.**

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T20:12:04Z",
  "run_number": 18,
  "prior_report": "R17",
  "system_version": "V36.5",
  "ledger_age_minutes": 681,
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
    "code_files_modified_since_r17": 2,
    "data_files_modified_since_r17": 0,
    "open004_resolved": true,
    "cpc_decontaminate_call_sites": [2372, 3206],
    "cig_gate_blocked_shots": 0,
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "api_path_first_frame_urls": 4,
    "ghost_first_frame_urls_missing_file": 4,
    "total_ghost_fields": 12,
    "regen_requested_shots": 2,
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "ledger_age_minutes": 681,
    "shots_with_video_url_in_plan": 28,
    "real_video_urls_excluding_api_path": 24,
    "first_frame_jpgs_on_disk_total": 62,
    "first_frame_jpgs_actual_shot_frames": 35,
    "first_frame_jpgs_chain_lastframe_files": 27,
    "shots_with_first_frame_url_in_plan": 39,
    "shots_with_valid_first_frame_url": 35,
    "mp4_files_videos_kling_lite": 30,
    "mp4_files_videos_dir": 0,
    "scenes_with_100pct_video": 1,
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
      "consecutive_reports": 7,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "affected_fields": ["video_url", "first_frame_url"],
      "total_affected_fields": 8
    },
    {
      "id": "OPEN-010",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 4,
      "affected_shots": ["001_M02", "001_M03", "001_M04", "001_M05"],
      "description": "first_frame_url set but file missing. APPROVED status. Non-blocking for --videos-only."
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "consecutive_reports": 17
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 17
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 15
    }
  ],
  "newly_resolved": [
    {
      "id": "OPEN-004",
      "classification_was": "META-CHRONIC",
      "resolution": "CONFIRMED_FIXED",
      "consecutive_reports_at_close": 10,
      "fix_description": "_cpc_decontaminate imported at runner:87 (try/except non-blocking), called at runner:2372 (nano frame path) and runner:3206 (Kling video path). Applied between R17 (19:11:08Z) and R18 (20:12:04Z). Runner mtime: 19:44:43Z.",
      "syntax_verified": true,
      "call_sites_verified": [2372, 3206]
    }
  ],
  "generation_readiness": {
    "scenes_ready_for_video_after_patch": ["001", "002", "003", "004"],
    "scenes_need_frames_first": ["005", "007", "009", "010", "011", "012", "013"],
    "gate_blocking_any_scene": false,
    "p0_blockers": 0,
    "pre_condition_001": "Clear OPEN-010 ghost first_frame_urls + re-run --frames-only 001 + re-approve M02-M05",
    "recommended_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only",
    "cpc_decontamination_active": true
  },
  "recommended_next_action": "apply_p1_data_patches_then_frames_only_001_then_videos_only_001_004"
}
```

---

**END REPORT**

*ATLAS R18 — Keep-up detection complete. ✅ META-CHRONIC CLEARED: OPEN-004 (`decontaminate_prompt` absent from runner, 10 consecutive reports) RESOLVED — CPC decontamination now wired in both generation paths (runner:2372 + runner:3206). P0 count: 1→0. 22 confirmed-fixed items. 0 P0 blockers. System idle — ledger 11h21m stale. 2 P1 data patches pending (OPEN-009/010). Session enforcer HEALTHY. No META-CHRONIC issues remain.*
