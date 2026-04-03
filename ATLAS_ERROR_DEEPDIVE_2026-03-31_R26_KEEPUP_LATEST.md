# ATLAS ERROR DEEPDIVE — 2026-03-31 R26 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T04:21:00Z
**Run number:** R26
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R25_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 19h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R25 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (15th) + OPEN-010 (12th) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 25th report |
| STALE_DOC | 2 | OPEN-003 (25th), OPEN-005 (23rd) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R25** | **1** | **+1 🆕** | **Runner modified post-R25 at 23:46:04 EDT (+161 lines lower section)** |
| **DATA CHANGES SINCE R25** | **0** | = | shot_plan.json unchanged (mtime: 20:22:12 EDT same as R25) |
| **GENERATION SINCE R25** | **0 frames, 0 videos** | = | **System idle — 7th consecutive idle generation report** |

**Key findings R26:**

1. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes, 0 regressions. Wire-A (6 hits), Wire-C (6 hits). All V37 governance hooks present (4 references each).

2. 🆕 **NEW FINDING: RUNNER MODIFIED POST-R25.** Runner mtime changed from 15:44:43 EDT to 23:46:04 EDT on 2026-03-30 (approximately 33 minutes after R25 was generated at 03:12Z/23:12 EDT). File size: 366,204 bytes, 6,179 total lines. Lower section expanded by ~161 lines (enrich_shots_with_arc call shifted 4772→4933; _fail_sids shifted 5539→5700). Session enforcer HEALTHY — modification did NOT break any wires. First code change after 6 consecutive idle code reports (R20–R25).

3. 🔴 **OPEN-009 META-CHRONIC: 15th consecutive report (R12→R26).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied since R23 first_frame_url fix. ~2 min edit undone for 15 cycles.

4. 🔴 **OPEN-010 META-CHRONIC: 12th consecutive report (R15→R26).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all stamped APPROVED. No operator action since META-CHRONIC escalation at R24.

5. 🟡 **SYSTEM IDLE (GENERATION) — 7th consecutive idle report (R20–R26).** No new frames or videos. Ledger age: 19h21m (+60m from R25). Despite runner modification, no generation was triggered.

6. 🟡 **006_M02/M04 AWAITING_APPROVAL (6th consecutive report, R21–R26).** No operator action.

7. ⚠️ **LTX GUARD ERROR MESSAGE ANOMALY (NEW OBSERVATION).** `_LTXRetiredGuard.__getattr__` at runner:504 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — "Use Seedance" is stale guidance since Seedance is also retired (V31.0). Functionally harmless (LTX won't fire) but the message would misdirect an operator hitting this error. Classified STALE_DOC sub-item under OPEN-005.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R26) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1512. 97/97 arc positions. 62/62 M-shots with `_chain_group`. | `isinstance(sp, list)` at runner:1512 ✅; shot_plan loads cleanly ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` at 4 locations in runner (lines 87, 91, 2372, 3206 approx — runner modified but grep count=4 confirmed). | `grep -c "_cpc_decontaminate" runner` → 4 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 23rd). `_LTXRetiredGuard` error message says "Use Seedance" (retired). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:535). CLAUDE.md V36.5 accurate. | runner:24 → Seedance claim; runner:535 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (6 hits), Wire-C (6 hits). Runner modified post-R25 — all wires survive modification. | Session enforcer R26 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic). OPEN-009: 4 API-path video_urls (15th). OPEN-010: 4 ghost first_frame_urls (12th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 19h21m stale). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). | Ledger scan R26 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/. 6 scenes with `_lite.mp4` (scene001-004,006,008). OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED. run_report: success=True, errors=[]. | File counts + shot_plan scan R26 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5700 ✅ (line number shifted from 5539 due to runner modification — logic intact). 6 lite stitch files confirmed (scene001-004,006,008). | `grep -n "_fail_sids"` → runner:5700 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits. Wire-C: 6 hits. Runner modified post-R25 — both wire sets survive. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (23rd). LTX guard error message says "Use Seedance" (newly noted). CLAUDE.md V36.5 correct. | Same as R25 + new LTX guard anomaly noted |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R26. Identical to R25. Runner modified post-R25 but NO confirmed-fixed items broken.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675 (approx).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529 (approx).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:535.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:505.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1512.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4933.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 4 `_V37_GOVERNANCE` refs + 4 `_v37_register_asset` + 4 `_v37_log_cost` in runner; 7 endpoints in orchestrator (unchanged mtime 15:43:25 EDT).
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R26 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R26.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:535 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=4 in runner.
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (15 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R26 status vs R25:** UNCHANGED. No data patch applied. Runner modified post-R25 but did not touch shot_plan.json (mtime unchanged at 20:22:12 EDT).

**META-CHRONIC STATUS:** 15 consecutive reports (R12→R26). ~2 min edit has not been applied in 15 cycles.

**PROOF RECEIPT (R26 live):**
```
PROOF: python3 shot_plan scan → [s['shot_id'] for s if '/api/media' in str(s.get('video_url',''))]
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

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url` (fixed R23), `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` still HEALTHY.

**Classification:** META-CHRONIC (15th report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (12 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 12th consecutive report.

**R26 status vs R25:** UNCHANGED. No operator action. shot_plan.json mtime unchanged. Runner modification did not touch shot_plan.json data.

**PROOF RECEIPT (R26 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R25. 12th consecutive confirmation.
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

**Classification:** META-CHRONIC (12th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 25th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger frozen at 228 entries for 19h21m.

**PROOF RECEIPT (R26 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R25)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 = [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 19h21m (+60m from R25's 18h21m)
CONFIRMS: No new generation. Identical distribution to R25.
```

**Classification:** ARCHITECTURAL_DEBT (25th report). Resolves on next generation run. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic).

---

### OPEN-003 (STALE_DOC — 25th consecutive report)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5700 (line shifted from 5539 due to runner modification post-R25 — logic intact, label still absent).

**PROOF (R26 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5700 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Line shifted (+161) due to runner modification — logic not broken.
```

**Note:** Line number shift (5539→5700) is a new observation consistent with runner modification post-R25.

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5700. One line.

**Classification:** STALE_DOC. 25th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 23rd consecutive report)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:535).

**NEW SUB-ISSUE R26:** `_LTXRetiredGuard.__getattr__` at runner:504 emits error message `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — the "Use Seedance" guidance is stale since Seedance is also retired (V31.0). If an operator hits this error, they would be misdirected. Functionally harmless (LTX won't fire under any normal path).

**PROOF (R26 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: sed -n '504p' atlas_universal_runner.py
OUTPUT: "def __getattr__(self, _):  raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Seedance.")"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:535: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Docstring wrong + LTX error message misdirects to retired system. Code behavior correct.
```

**Classification:** STALE_DOC. 23rd consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (6th consecutive report, R21–R26)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists (8.5M, dated 2026-03-29 17:54). Videos generated but not approved or regen'd by operator.

**Also:** 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21.

**PROOF (R26 live):**
```
PROOF: shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 6th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 6th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R25.

---

## 6. NEW OBSERVATIONS (R26 only)

### 6.1 Runner Modified Post-R25 — 161-Line Lower-Section Expansion

**This is the most significant finding of R26.** The runner was modified approximately 33 minutes after R25 was written (R25 timestamp: 03:12Z on 2026-03-31; runner mtime: 23:46:04 EDT = 03:46:04Z on 2026-03-31).

**Evidence of modification:**
- Runner mtime: 15:44:43 EDT (R25) → 23:46:04 EDT (R26) — +8h03m
- Runner total lines: 6,179 (vs R25 which did not record exact total — but reported as stable at ~6,000+ lines)
- Line number shifts:
  - `LTX_FAST = _LTXRetiredGuard()`: 490 → 505 (+15)
  - `ACTIVE_VIDEO_MODEL`: 527 → 535 (+8)
  - `isinstance(sp, list)` guard: 1504 → 1512 (+8)
  - `enrich_shots_with_arc` call: ~4772 → 4933 (+161)
  - `_fail_sids`: 5539 → 5700 (+161)
- Pattern: ~8-15 line shift in upper section; ~161 line shift in lower generation section. Consistent with a block of ~161 lines inserted in the generation pipeline area (around original line 4700-5000).

**Impact assessment:**
- Session enforcer: ✅ SYSTEM HEALTHY (runs AFTER modification)
- Learning log: 0 regressions
- All V37 governance hooks: intact (4 × _V37_GOVERNANCE, _v37_register_asset, _v37_log_cost)
- Wire-A (6), Wire-C (6), _fail_sids logic at 5700: all present
- chain_arc_intelligence: unchanged (mtime 2026-03-29)
- shot_plan.json: unchanged (no generation triggered)

**Conclusion:** Modification is BENIGN to all confirmed-fixed items. No regressions. The +161 lines in the lower generation section likely represent a new feature addition or enhancement in the scene generation/stitch logic area. **No action required** — this is informational. Future reports should track the new line positions as canonical.

### 6.2 Seventh Consecutive Idle Generation Report

R20–R26 = 7 consecutive reports with zero new generation. Runner was modified but no generation was triggered (shot_plan.json unchanged). This is the longest idle generation streak since initial production. Ledger staleness: +60m per cycle, now at 19h21m.

### 6.3 Ledger Staleness Trend (7-Report View)

| Report | Ledger Age |
|--------|-----------|
| R20 | 13h21m |
| R21 | 14h21m |
| R22 | 15h21m |
| R23 | 16h21m |
| R24 | 17h21m |
| R25 | 18h21m |
| **R26** | **19h21m** |

Staleness growing exactly +60m per report cycle. Clean 1h interval confirms automated keep-up running on schedule.

### 6.4 META-CHRONIC Persistence Summary (Updated R26)

| Issue | First Appeared | META-CHRONIC Since | Consecutive Reports |
|-------|---------------|-------------------|---------------------|
| OPEN-009 (video_url patch) | R12 | R12 | **15 (R12→R26)** |
| OPEN-010 (ghost frames regen) | R15 | R24 | **12 (R15→R26; META-CHRONIC from R24)** |

Combined fix time: ~12 min. Neither issue blocks active generation.

### 6.5 No Proof Gate Report Available

No `ATLAS_PROOF_GATE_*.md` files found in the workspace. Proof gate classifications are not available to override keep-up classifications this cycle.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, 15th META-CHRONIC |
| **P1** | OPEN-010 (ghost frames + re-gen 001 M-shots) | 10 min | Clear first_frame_url + reset approval for 001_M02-M05, then --frames-only 001 | NO — but META-CHRONIC data integrity risk if re-stitch attempted |
| **P2** | 006_M02/M04 AWAITING_APPROVAL | 2 min | Operator review in UI → thumbs-up or thumbs-down | NO — production gap |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge fires with Gemini/OpenRouter | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5700 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance + LTX error msg) | 3 min | Update runner header line 24 + fix `_LTXRetiredGuard` error message to say "Use Kling" | NO — cosmetic |

**P0 count: 0. No P0 blockers. System ready for generation.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R26: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (count=4 confirmed R26)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R26 via session_enforcer)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4). Only re-stitch if M03b/M04 regen'd.
□ Note runner line number changes: _fail_sids now at 5700, enrich_shots_with_arc at 4933, isinstance at 1512
```

---

## 9. DELTA FROM R25

| Signal | R25 | R26 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (15th) + OPEN-010 (12th) |
| **OPEN-009 consecutive** | 14 | **15** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 11 | **12** | **+1** | No operator action |
| **CONFIRMED_FIXED** | 23 | 23 | = | No new items |
| **Code files modified since R25** | 0 | **1** | **🆕+1** | **Runner modified 23:46:04 EDT — 161 lines added lower section** |
| runner mtime | 15:44:43 EDT | **23:46:04 EDT** | **🆕 CHANGED** | Post-R25 modification |
| runner total lines | ~same | 6,179 | — | First measured precisely R26 |
| orchestrator mtime | 15:43:25 EDT | 15:43:25 EDT | = | Unchanged |
| shot_plan.json mtime | 20:22:12 EDT | 20:22:12 EDT | = | Unchanged |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 18h21m | **19h21m** | **+60m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | 15th META-CHRONIC |
| API-path first_frame_url | 0 (FIXED R23) | 0 | = | Confirmed fixed |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | 12th META-CHRONIC |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| AWAITING_APPROVAL shots | 2 | 2 | = | 006_M02 + 006_M04 |
| OPEN-002 consecutive | 24 | **25** | **+1** | Arch debt |
| OPEN-003 consecutive | 24 | **25** | **+1** | Cosmetic; Wire-B line shifted 5539→5700 |
| OPEN-005 consecutive | 22 | **23** | **+1** | Cosmetic + new LTX guard msg anomaly noted |
| 006_M02/M04 consecutive | 5 | **6** | **+1** | Production gap |
| Session enforcer | HEALTHY | HEALTHY | = | Post-modification ✅ |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| First_frames on disk | 62 | 62 | = | |
| Videos in kling_lite | 62 total | 62 total | = | |
| Lite stitches (.mp4) | 6 scenes | 6 scenes | = | scene001-004,006,008 |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |
| P0 blockers | 0 | 0 | = | Clean |
| Idle generation reports | 6 | **7** | **+1** | R20-R26 |
| Idle code reports | 6 | **0** | **↩️ RESET** | Runner modified post-R25 |

---

## 10. GENERATION READINESS ASSESSMENT (R26)

**System is fully operational. Two META-CHRONIC data patches recommended before generation. Runner modification post-R25 is benign — all wires confirmed intact.**

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
  "session_timestamp": "2026-03-31T04:21:00Z",
  "ledger_age_hours": 19.35,
  "run_number": 26,
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-31_R25_KEEPUP_LATEST.md",
  "meta_chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 15,
      "class": "META-CHRONIC",
      "description": "4 shots (008_E01/E02/E03/M03b) still have /api/media?path= prefix in video_url. first_frame_url RESOLVED (R23).",
      "progress_this_cycle": "No change from R25. video_url patch not applied. Runner modified but shot_plan.json unchanged.",
      "proof_receipt": "python3 scan → API_PATH_VIDEO_URL: ['008_E01','008_E02','008_E03','008_M03b']",
      "fix_recipe": "Strip /api/media?path= from video_url on 008_E01/E02/E03/M03b — no code change, ~2 min",
      "regression_guard": ["session_enforcer still HEALTHY after patch", "do not touch first_frame_url (fixed R23)"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 12,
      "class": "META-CHRONIC",
      "description": "4 shots (001_M02-M05) have ghost first_frame_url pointing to non-existent files, all APPROVED.",
      "progress_this_cycle": "No change from R25. No operator action. Runner modified but shot_plan.json unchanged.",
      "proof_receipt": "python3 os.path.exists check → GHOST_FIRST_FRAME_URLS: 4 — 001_M02/M03/M04/M05 all missing",
      "fix_recipe": "Clear first_frame_url + reset to AWAITING_APPROVAL for 001_M02-M05, then --frames-only",
      "regression_guard": ["001_M01.jpg still present on disk", "scene001_lite.mp4 preserved"]
    }
  ],
  "chronic_issues": [],
  "false_positives_retracted": [],
  "newly_confirmed_fixed": [],
  "newly_escalated": [],
  "new_observations": [
    {
      "id": "NEW-R26-001",
      "class": "RUNNER_MODIFICATION",
      "description": "Runner modified post-R25 at 23:46:04 EDT. +161 lines in lower generation section (4700-5000 area). All wires intact. Session enforcer HEALTHY. 0 regressions.",
      "impact": "BENIGN — no confirmed-fixed items broken",
      "line_position_updates": {
        "_fail_sids": 5700,
        "enrich_shots_with_arc_call": 4933,
        "isinstance_guard": 1512,
        "ACTIVE_VIDEO_MODEL": 535,
        "LTX_FAST_guard": 505
      }
    },
    {
      "id": "NEW-R26-002",
      "class": "STALE_DOC_SUB",
      "description": "_LTXRetiredGuard error message at runner:504 says 'Use Seedance' — Seedance also retired (V31.0). Misdirects operator if triggered. Functionally harmless.",
      "impact": "COSMETIC — LTX won't fire under normal operation"
    }
  ],
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
  "system_idle_generation": true,
  "consecutive_idle_generation_reports": 7,
  "consecutive_idle_code_reports": 0,
  "data_patch_applied_since_prior": false,
  "code_changes_since_prior": 1,
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
  "runner_line_positions_canonical_r26": {
    "LTX_FAST_guard": 505,
    "ACTIVE_VIDEO_MODEL": 535,
    "isinstance_sp_list": 1512,
    "enrich_shots_with_arc_import": 65,
    "enrich_shots_with_arc_call": 4933,
    "fail_sids": 5700,
    "wire_a_count": 6,
    "wire_c_count": 6,
    "cpc_decontaminate_count": 4,
    "v37_governance_count": 4
  },
  "key_note": "Runner modified post-R25 (first code change after 6 idle code reports). +161 lines lower generation section. All wires intact. Both META-CHRONICs persist (15th + 12th). Combined ~12 min data fix ready to apply."
}
```

---

*Document lineage: R01 → R02 → … → R24 → R25 → **R26***
*Prior report: ATLAS_ERROR_DEEPDIVE_2026-03-31_R25_KEEPUP_LATEST.md*
*Generated by: ATLAS keep-up automated task (scheduled hourly)*
