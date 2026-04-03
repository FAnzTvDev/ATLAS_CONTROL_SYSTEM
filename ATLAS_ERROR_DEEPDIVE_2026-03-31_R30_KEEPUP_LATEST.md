# ATLAS ERROR DEEPDIVE — 2026-03-31 R30 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T08:10:50Z
**Run number:** R30
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R29_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 23h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R29 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (19th) + OPEN-010 (16th) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 29th report |
| STALE_DOC | 2 | OPEN-003 (29th), OPEN-005 (27th) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R29** | **0** | **= (idle)** | **Runner mtime unchanged at 23:46:04 EDT — no modification** |
| **DATA CHANGES SINCE R29** | **0** | = | shot_plan.json mtime unchanged (20:22:12 EDT) |
| **GENERATION SINCE R29** | **0 frames, 0 videos** | = | **System idle — 11th consecutive idle generation report (R20–R30)** |

**Key findings R30:**

1. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 22 fixes, 0 regressions (ALL CLEAR). Wire-A+Wire-C = 12 combined hits (confirmed via grep -c "WIRE-A\|WIRE-C"). Wire-B logic at runner:5700. V37 governance: _V37 refs=4 in runner (non-blocking hooks), /api/v37 endpoints=7 in orchestrator. CPC count=4.

2. 🟢 **ALL CANONICAL LINE POSITIONS STABLE (R29 → R30).** Runner total lines: 6,179 (unchanged). `_fail_sids` at runner:5700, `enrich_shots_with_arc` call at runner:4933, `isinstance` guard at runner:1512, `ACTIVE_VIDEO_MODEL` at runner:535, `LTX_FAST` guard at runner:505. No runner modification since R26 expansion. **4th consecutive idle-code cycle post-R26.**

3. 🔴 **OPEN-009 META-CHRONIC: 19th consecutive report (R12→R30).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied. ~2 min edit remains unapplied.

4. 🔴 **OPEN-010 META-CHRONIC: 16th consecutive report (R15→R30).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all APPROVED. No operator action since META-CHRONIC escalation at R24.

5. 🟡 **SYSTEM IDLE (GENERATION) — 11th consecutive idle report (R20–R30).** No new frames or videos. Ledger age: 23h21m (+59m from R29). Automated keep-up cadence confirmed regular (~59–61m/cycle, 11th cycle confirmed).

6. 🟡 **006_M02/M04 AWAITING_APPROVAL (10th consecutive report, R21–R30).** 008_M03b + 008_M04 REGEN_REQUESTED (unchanged since R21). No operator action.

7. 🟡 **REWARD SIGNAL FROZEN — 29th consecutive report.** 228 ledger entries (unchanged). 87.8% heuristic I=0.75 (36/41 last-entry-per-shot). 5 real-VLM shots unchanged: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). Self-resolves on next generation run.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R30) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1512. 97/97 arc positions. 62/62 M-shots with `_chain_group`. shot_plan.json mtime 20:22:12 EDT (unchanged from R29). | `isinstance(sp, list)` at runner:1512 ✅; runner:4506 guard ✅; runner:1475 guard ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` count=4 in runner (unchanged). CPC confirmed wired. | `grep -c "_cpc_decontaminate" runner` → 4 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 27th). `_LTXRetiredGuard` error says "Use Seedance" (retired V31.0). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:535). CLAUDE.md V36.5 accurate. | runner:24 Seedance claim ✅ confirmed; runner:535 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes, 0 regressions. Wire-A (6 hits via combined 12 grep), Wire-C (6 hits), `_fail_sids` at runner:5700. `enrich_shots_with_arc` imported at runner:65, called at runner:4933. | Session enforcer R30 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic). OPEN-009: 4 API-path video_urls (19th). OPEN-010: 4 ghost first_frame_urls (16th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 23h21m stale). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). | Ledger scan R30 ✅ — identical to R29 |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/ (both unchanged). 6 scenes with `_lite.mp4`. OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED. run_report: success=True, errors=[]. | File counts + shot_plan scan R30 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5700 ✅. 6 lite stitch files confirmed — all mtimes unchanged. | `grep -n "_fail_sids"` → runner:5700 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits. Wire-C: 6 hits (12 total via combined grep). Runner stable — no modification since R26 expansion (4th idle-code cycle). | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (27th). LTX guard error message says "Use Seedance" (persists from R26). CLAUDE.md V36.5 correct. | Confirmed via sed -n '24p' and line 505 grep R30 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R30. Identical to R26/R27/R28/R29.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:535.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:505.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1512.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4933.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 4 `_V37*` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (mtime 15:43:25 EDT unchanged).
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R30 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R30.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:535 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=4 in runner.
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (19 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R30 status vs R29:** UNCHANGED. No data patch applied. Runner mtime unchanged — no code change. shot_plan.json mtime unchanged (20:22:12 EDT).

**META-CHRONIC STATUS:** 19 consecutive reports (R12→R30). ~2 min edit has not been applied in 19 cycles.

**PROOF RECEIPT (R30 live):**
```
PROOF: python3 scan → shots where '/api/media' in video_url
OUTPUT: ['008_E01', '008_E02', '008_E03', '008_M03b']
CONFIRMS: 4 video_url fields still carry /api/media?path= prefix. first_frame_url: 0 affected (FIXED R23).
```

**Remaining fix (data patch only — no code changes):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   video_url = video_url.replace("/api/media?path=", "")
# Total: 4 field changes
# Verify: grep "/api/media" pipeline_outputs/victorian_shadows_ep1/shot_plan.json | wc -l → should return 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url` (fixed R23), `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` still HEALTHY.

**Classification:** META-CHRONIC (19th report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (16 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 16th consecutive report.

**R30 status vs R29:** UNCHANGED. No operator action. shot_plan.json mtime unchanged. Runner stable — no new code changes.

**META-CHRONIC STATUS:** 16 consecutive reports (R15→R30). META-CHRONIC since R24.

**PROOF RECEIPT (R30 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R29. 16th consecutive confirmation.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk. scene001_lite.mp4 (18M, mtime 2026-03-30 08:47) was generated using the chain from M01. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk. scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05.

**Classification:** META-CHRONIC (16th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 29th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger frozen at 228 entries for 23h21m.

**PROOF RECEIPT (R30 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R29)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 = [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 23h21m (+59m from R29's 22h22m)
CONFIRMS: No new generation. Identical distribution to R29.
```

**Classification:** ARCHITECTURAL_DEBT (29th report). Resolves on next generation run. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic) confirmed via session_enforcer.

---

### OPEN-003 (STALE_DOC — 29th consecutive report)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5700 (confirmed stable R30 — line position unchanged from R26).

**PROOF (R30 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5700 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Line position stable at 5700 (5th consecutive confirmation).
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5700. One line.

**Classification:** STALE_DOC. 29th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 27th consecutive report)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:535). Additionally, `_LTXRetiredGuard.__getattr__` at runner:505 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — stale guidance since Seedance is also retired (V31.0).

**PROOF (R30 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: runner line 505 contains _LTXRetiredGuard with "Use Seedance" message
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:535: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Both stale docstring references persist unchanged from R29. Code behavior correct.
```

**Classification:** STALE_DOC. 27th consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (10th consecutive report, R21–R30)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists (8.5M, dated 2026-03-29 17:54). Videos generated but not reviewed by operator. 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21.

**PROOF (R30 live):**
```
PROOF: python3 shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 10th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 10th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R29.

---

## 6. NEW OBSERVATIONS (R30 only)

### 6.1 Eleventh Consecutive Idle Generation Report — R20 Through R30

System has produced zero new frames or videos across 11 consecutive keep-up cycles (R20–R30). All wires intact, all 23 confirmed-fixed items verified, 0 regressions, session enforcer HEALTHY. The two META-CHRONIC data patches (~12 min combined) remain unapplied.

### 6.2 Ledger Staleness Trend (11-Report View)

| Report | Ledger Age | Delta |
|--------|-----------|-------|
| R20 | 13h21m | — |
| R21 | 14h21m | +60m |
| R22 | 15h21m | +60m |
| R23 | 16h21m | +60m |
| R24 | 17h21m | +60m |
| R25 | 18h21m | +60m |
| R26 | 19h21m | +60m |
| R27 | 20h22m | +61m |
| R28 | 21h21m | +59m |
| R29 | 22h22m | +61m |
| **R30** | **23h21m** | **+59m** |

Cadence: 59–61m per cycle. Automated keep-up running on schedule. Average cadence: 60.1m/cycle.

### 6.3 META-CHRONIC Persistence Summary (Updated R30)

| Issue | First Appeared | META-CHRONIC Since | Consecutive Reports |
|-------|---------------|-------------------|---------------------|
| OPEN-009 (video_url patch) | R12 | R12 | **19 (R12→R30)** |
| OPEN-010 (ghost frames regen) | R15 | R24 | **16 (R15→R30; META-CHRONIC from R24)** |

Combined operator fix time: ~12 min. Neither blocks active generation.

### 6.4 Four Consecutive Idle Code Cycles Post-R26

Runner mtime (23:46:04 EDT 2026-03-30) and orchestrator mtime (15:43:25 EDT 2026-03-30) are both identical across R27, R28, R29, and now R30 — four consecutive reports with zero code modification. All canonical wire positions stable across five consecutive reports (R26 baseline → R27 → R28 → R29 → R30):

| Wire | Line (R26) | R27 | R28 | R29 | **R30** | Status |
|------|-----------|-----|-----|-----|---------|--------|
| `_fail_sids` (Wire-B logic) | 5700 | 5700 | 5700 | 5700 | **5700** | ✅ Stable |
| `enrich_shots_with_arc` call | 4933 | 4933 | 4933 | 4933 | **4933** | ✅ Stable |
| `isinstance` guard | 1512 | 1512 | 1512 | 1512 | **1512** | ✅ Stable |
| `ACTIVE_VIDEO_MODEL` | 535 | 535 | 535 | 535 | **535** | ✅ Stable |
| `LTX_FAST` guard | 505 | 505 | 505 | 505 | **505** | ✅ Stable |

### 6.5 No Proof Gate Report Available

No `ATLAS_PROOF_GATE_*.md` files found. Proof gate classifications are not available to override keep-up classifications this cycle.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, 19th META-CHRONIC |
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
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R30: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (count=4 confirmed R30)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R30 via session_enforcer: HEALTHY)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4). Only re-stitch if M03b/M04 regen'd.
□ Canonical runner line positions (stable from R26, verified R27/R28/R29/R30): _fail_sids=5700, enrich_shots_with_arc=4933, isinstance=1512, ACTIVE_VIDEO_MODEL=535, LTX_FAST guard=505.
```

---

## 9. DELTA FROM R29

| Signal | R29 | R30 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (19th) + OPEN-010 (16th) |
| **OPEN-009 consecutive** | 18 | **19** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 15 | **16** | **+1** | No operator action |
| **CONFIRMED_FIXED** | 23 | 23 | = | No new items |
| **Code files modified since R29** | 0 | **0** | = | **Stable — 4th idle code cycle post-R26** |
| runner mtime | 23:46:04 EDT | 23:46:04 EDT | = | Stable |
| runner total lines | 6,179 | 6,179 | = | Stable |
| orchestrator mtime | 15:43:25 EDT | 15:43:25 EDT | = | Unchanged |
| shot_plan.json mtime | 20:22:12 EDT | 20:22:12 EDT | = | Unchanged |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 22h22m | **23h21m** | **+59m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | 19th META-CHRONIC |
| API-path first_frame_url | 0 (FIXED R23) | 0 | = | Confirmed fixed |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | 16th META-CHRONIC |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| AWAITING_APPROVAL shots | 2 | 2 | = | 006_M02 + 006_M04 |
| OPEN-002 consecutive | 28 | **29** | **+1** | Arch debt |
| OPEN-003 consecutive | 28 | **29** | **+1** | Cosmetic; _fail_sids at runner:5700 stable |
| OPEN-005 consecutive | 26 | **27** | **+1** | Cosmetic stale docstring + LTX error msg |
| 006_M02/M04 consecutive | 9 | **10** | **+1** | Production gap |
| Session enforcer | HEALTHY | HEALTHY | = | ✅ |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| First_frames on disk | 62 | 62 | = | |
| Videos in kling_lite | 62 | 62 | = | |
| Lite stitches (.mp4) | 6 scenes | 6 scenes | = | scene001-004,006,008 |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |
| P0 blockers | 0 | 0 | = | Clean |
| Idle generation reports | 10 | **11** | **+1** | R20-R30 |
| Idle code reports | 3 | **4** | **+1** | Post-R26 stable |

---

## 10. PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T08:10:50Z",
  "run_number": "R30",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-31_R29_KEEPUP_LATEST.md",
  "ledger_age_hours": 23.35,
  "ledger_entries": 228,
  "ledger_last_entry": "001_M05",
  "code_modified_since_prior": false,
  "data_modified_since_prior": false,
  "idle_generation_cycles": 11,
  "idle_code_cycles": 4,
  "session_enforcer_result": "HEALTHY",
  "learning_log_regressions": 0,
  "runner_line_count": 6179,
  "runner_mtime": "2026-03-30T23:46:04-04:00",
  "orchestrator_mtime": "2026-03-30T15:43:25-04:00",
  "shot_plan_mtime": "2026-03-30T20:22:12-04:00",
  "first_frames_on_disk": 62,
  "videos_on_disk": 62,
  "lite_stitches": 6,
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "description": "API-path prefix in video_url on 008_E01/E02/E03/M03b",
      "consecutive_reports": 19,
      "class": "META-CHRONIC",
      "first_appeared": "R12",
      "meta_chronic_since": "R12",
      "proof_receipt": "python3 scan: ['008_E01', '008_E02', '008_E03', '008_M03b'] have /api/media in video_url",
      "fix_recipe": "strip /api/media?path= from video_url on 4 shots in shot_plan.json",
      "effort_minutes": 2,
      "blocking": false,
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"]
    },
    {
      "id": "OPEN-010",
      "description": "Ghost first_frame_url on 001_M02/M03/M04/M05 (files missing on disk, all APPROVED)",
      "consecutive_reports": 16,
      "class": "META-CHRONIC",
      "first_appeared": "R15",
      "meta_chronic_since": "R24",
      "proof_receipt": "python3 os.path.exists check: 001_M02/M03/M04/M05 first_frame_url → file not found",
      "fix_recipe": "clear first_frame_url + set AWAITING_APPROVAL for 001_M02-M05, then --frames-only scene 001",
      "effort_minutes": 10,
      "blocking": false,
      "regression_guard": ["001_M01.jpg on disk", "scene001_lite.mp4 preserved"]
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "description": "87.8% heuristic I-scores — self-resolves on next generation",
      "consecutive_reports": 29,
      "class": "ARCHITECTURAL_DEBT"
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "description": "No WIRE-B label in runner — _fail_sids at runner:5700 is functional",
      "consecutive_reports": 29,
      "class": "STALE_DOC"
    },
    {
      "id": "OPEN-005",
      "description": "Runner header line 24 claims Seedance PRIMARY; LTXRetiredGuard says 'Use Seedance'",
      "consecutive_reports": 27,
      "class": "STALE_DOC"
    }
  ],
  "production_gaps": [
    {
      "id": "GAP-006",
      "description": "006_M02+M04 AWAITING_APPROVAL; 008_M03b+M04 REGEN_REQUESTED",
      "consecutive_reports": 10,
      "class": "PRODUCTION_GAP"
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_count": 23,
  "p0_blockers": 0,
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
  "canonical_wire_positions": {
    "_fail_sids": 5700,
    "enrich_shots_with_arc": 4933,
    "isinstance_guard": 1512,
    "ACTIVE_VIDEO_MODEL": 535,
    "LTX_FAST_guard": 505
  },
  "recommended_next_action": "run_generation"
}
```

---

*Document lineage: R1 → R2 → ... → R28 → R29 → **R30***
*Generated: 2026-03-31T08:10:50Z by automated keep-up task*
*ATLAS V36.5 — AAA Production Factory for AI Filmmaking*
