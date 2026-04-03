# ATLAS ERROR DEEPDIVE — 2026-03-31 R28 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T06:09:00Z
**Run number:** R28
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R27_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 0d 21h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R27 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (17th) + OPEN-010 (14th) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | 27th report |
| STALE_DOC | 2 | OPEN-003 (27th), OPEN-005 (25th) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R27** | **0** | **= (idle)** | **Runner mtime unchanged at 23:46:04 EDT — no modification** |
| **DATA CHANGES SINCE R27** | **0** | = | shot_plan.json mtime unchanged (20:22:12 EDT) |
| **GENERATION SINCE R27** | **0 frames, 0 videos** | = | **System idle — 9th consecutive idle generation report (R20–R28)** |

**Key findings R28:**

1. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 22 fixes, 0 regressions (ALL CLEAR). Wire-A (6 hits via 12-total WIRE-A/C grep), Wire-B logic at runner:5700, Wire-C (6 hits). V37 governance hooks: 12 references in runner, 7 endpoints in orchestrator. CPC count=4.

2. 🟢 **ALL CANONICAL LINE POSITIONS STABLE (R27 → R28).** Runner total lines: 6,179 (unchanged). `_fail_sids` at runner:5700, `enrich_shots_with_arc` call at runner:4933, `isinstance` guard at runner:1512, `ACTIVE_VIDEO_MODEL` at runner:535, `LTX_FAST` guard at runner:505. No further runner modification since R26 expansion.

3. 🔴 **OPEN-009 META-CHRONIC: 17th consecutive report (R12→R28).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied. ~2 min edit remains unapplied.

4. 🔴 **OPEN-010 META-CHRONIC: 14th consecutive report (R15→R28).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all APPROVED. No operator action since META-CHRONIC escalation at R24.

5. 🟡 **SYSTEM IDLE (GENERATION) — 9th consecutive idle report (R20–R28).** No new frames or videos. Ledger age: 21h21m (+59m from R27). Automated keep-up cadence confirmed regular (~60m/cycle).

6. 🟡 **006_M02/M04 AWAITING_APPROVAL (8th consecutive report, R21–R28).** 008_M03b + 008_M04 REGEN_REQUESTED (unchanged since R21). No operator action.

7. 🟡 **REWARD SIGNAL FROZEN — 27th consecutive report.** 228 ledger entries (unchanged). 87.8% heuristic I=0.75 (36/41 last-entry-per-shot). 5 real-VLM shots unchanged: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). Self-resolves on next generation run.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R28) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1512. 97/97 arc positions. 62/62 M-shots with `_chain_group`. shot_plan.json mtime 20:22:12 EDT (unchanged from R27). | `isinstance(sp, list)` at runner:1512 ✅; arc_count=97/97 ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` count=4 in runner (unchanged). CPC confirmed wired. | `grep -c "_cpc_decontaminate" runner` → 4 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 25th). `_LTXRetiredGuard` error says "Use Seedance" (retired V31.0). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:535). CLAUDE.md V36.5 accurate. | runner:24 Seedance claim ✅; runner:535 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes, 0 regressions. Wire-A (6 hits), Wire-C (6 hits), `_fail_sids` at runner:5700. `enrich_shots_with_arc` imported at runner:65, called at runner:4933. | Session enforcer R28 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic). OPEN-009: 4 API-path video_urls (17th). OPEN-010: 4 ghost first_frame_urls (14th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, 21h21m stale). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). | Ledger scan R28 ✅ — identical to R27 |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/ (both unchanged). 6 scenes with `_lite.mp4`. OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED. run_report: success=True, errors=[]. | File counts + shot_plan scan R28 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5700 ✅. 6 lite stitch files confirmed — all mtimes unchanged. | `grep -n "_fail_sids"` → runner:5700 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits. Wire-C: 6 hits (12 total via combined grep). Runner stable — no modification since R26 expansion. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (25th). LTX guard error message says "Use Seedance" (persists from R26). CLAUDE.md V36.5 correct. | Confirmed via `sed -n '24p'` and `sed -n '504p'` R28 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R28. Identical to R26/R27.

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
✅ **V37 GOVERNANCE HOOKS** — 12 `_V37*` refs in runner; 7 `/api/v37` endpoints in orchestrator (mtime 15:43:25 EDT unchanged).
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR — R28 confirmed).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R28.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:535 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=4 in runner.
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (17 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R28 status vs R27:** UNCHANGED. No data patch applied. Runner mtime unchanged — no code change. shot_plan.json mtime unchanged (20:22:12 EDT).

**META-CHRONIC STATUS:** 17 consecutive reports (R12→R28). ~2 min edit has not been applied in 17 cycles.

**PROOF RECEIPT (R28 live):**
```
PROOF: python3 -c "import json,os; sp=json.load(open('pipeline_outputs/victorian_shadows_ep1/shot_plan.json')); shots=sp if isinstance(sp,list) else sp.get('shots',[]); print([s['shot_id'] for s in shots if '/api/media' in str(s.get('video_url',''))])"
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

**Classification:** META-CHRONIC (17th report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (14 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 14th consecutive report.

**R28 status vs R27:** UNCHANGED. No operator action. shot_plan.json mtime unchanged. Runner stable — no new code changes.

**META-CHRONIC STATUS:** 14 consecutive reports (R15→R28). META-CHRONIC since R24.

**PROOF RECEIPT (R28 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R27. 14th consecutive confirmation.
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

**Classification:** META-CHRONIC (14th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 27th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger frozen at 228 entries for 21h21m.

**PROOF RECEIPT (R28 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R27)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 = [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 21h21m (+59m from R27's 20h22m)
CONFIRMS: No new generation. Identical distribution to R27.
```

**Classification:** ARCHITECTURAL_DEBT (27th report). Resolves on next generation run. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic) confirmed via session_enforcer.

---

### OPEN-003 (STALE_DOC — 27th consecutive report)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5700 (confirmed stable R28 — line position unchanged from R27).

**PROOF (R28 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5700 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Line position stable at 5700.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5700. One line.

**Classification:** STALE_DOC. 27th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 25th consecutive report)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:535). Additionally, `_LTXRetiredGuard.__getattr__` at runner:504 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — stale guidance since Seedance is also retired (V31.0).

**PROOF (R28 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: sed -n '504p' atlas_universal_runner.py
OUTPUT: "    def __getattr__(self, _):  raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Seedance.")"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:535: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Both stale docstring references persist unchanged from R27. Code behavior correct.
```

**Classification:** STALE_DOC. 25th consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (8th consecutive report, R21–R28)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists (8.5M, dated 2026-03-29 17:54). Videos generated but not reviewed by operator. 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21.

**PROOF (R28 live):**
```
PROOF: python3 shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 8th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 8th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R27.

---

## 6. NEW OBSERVATIONS (R28 only)

### 6.1 Ninth Consecutive Idle Generation Report — R20 Through R28

System has produced zero new frames or videos across 9 consecutive keep-up cycles (R20–R28). Runner was modified between R25 and R26 (+161 lines), but no generation was triggered. The system is in a clean steady-state: all wires intact, all 23 confirmed-fixed items verified, 0 regressions, session enforcer HEALTHY. The only outstanding actions are two META-CHRONIC data patches (~12 min combined) and an operator UI review of pending/regen_requested shots.

### 6.2 Ledger Staleness Trend (9-Report View)

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
| **R28** | **21h21m** | **+59m** |

Cadence: 59–61m per cycle. Automated keep-up running on schedule. Ledger will remain stale until next human-initiated generation run.

### 6.3 META-CHRONIC Persistence Summary (Updated R28)

| Issue | First Appeared | META-CHRONIC Since | Consecutive Reports |
|-------|---------------|-------------------|---------------------|
| OPEN-009 (video_url patch) | R12 | R12 | **17 (R12→R28)** |
| OPEN-010 (ghost frames regen) | R15 | R24 | **14 (R15→R28; META-CHRONIC from R24)** |

Combined operator fix time: ~12 min. Neither blocks active generation.

### 6.4 Complete System Stability Post-R26 Expansion

Runner mtime (23:46:04 EDT 2026-03-30) and orchestrator mtime (15:43:25 EDT 2026-03-30) are both identical to R27 measurements. All canonical wire positions stable across three consecutive reports (R26 baseline → R27 verification → R28 verification):

| Wire | Line (R26) | Line (R27) | Line (R28) | Status |
|------|-----------|-----------|-----------|--------|
| `_fail_sids` (Wire-B logic) | 5700 | 5700 | **5700** | ✅ Stable |
| `enrich_shots_with_arc` call | 4933 | 4933 | **4933** | ✅ Stable |
| `isinstance` guard | 1512 | 1512 | **1512** | ✅ Stable |
| `ACTIVE_VIDEO_MODEL` | 535 | 535 | **535** | ✅ Stable |
| `LTX_FAST` guard | 505 | 505 | **505** | ✅ Stable |

### 6.5 No Proof Gate Report Available

No `ATLAS_PROOF_GATE_*.md` files found. Proof gate classifications are not available to override keep-up classifications this cycle.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, 17th META-CHRONIC |
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
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R28: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (count=4 confirmed R28)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R28 via session_enforcer: 4 backends)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4). Only re-stitch if M03b/M04 regen'd.
□ Canonical runner line positions (stable from R26, verified R28): _fail_sids=5700, enrich_shots_with_arc=4933, isinstance=1512, ACTIVE_VIDEO_MODEL=535, LTX_FAST guard=505.
```

---

## 9. DELTA FROM R27

| Signal | R27 | R28 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (17th) + OPEN-010 (14th) |
| **OPEN-009 consecutive** | 16 | **17** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 13 | **14** | **+1** | No operator action |
| **CONFIRMED_FIXED** | 23 | 23 | = | No new items |
| **Code files modified since R27** | 0 | **0** | = | **Stable — 2nd idle code cycle post-R26** |
| runner mtime | 23:46:04 EDT | 23:46:04 EDT | = | Stable |
| runner total lines | 6,179 | 6,179 | = | Stable |
| orchestrator mtime | 15:43:25 EDT | 15:43:25 EDT | = | Unchanged |
| shot_plan.json mtime | 20:22:12 EDT | 20:22:12 EDT | = | Unchanged |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 20h22m | **21h21m** | **+59m** | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | 17th META-CHRONIC |
| API-path first_frame_url | 0 (FIXED R23) | 0 | = | Confirmed fixed |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | 14th META-CHRONIC |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| AWAITING_APPROVAL shots | 2 | 2 | = | 006_M02 + 006_M04 |
| OPEN-002 consecutive | 26 | **27** | **+1** | Arch debt |
| OPEN-003 consecutive | 26 | **27** | **+1** | Cosmetic; _fail_sids at runner:5700 stable |
| OPEN-005 consecutive | 24 | **25** | **+1** | Cosmetic stale docstring + LTX error msg |
| 006_M02/M04 consecutive | 7 | **8** | **+1** | Production gap |
| Session enforcer | HEALTHY | HEALTHY | = | ✅ |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| First_frames on disk | 62 | 62 | = | |
| Videos in kling_lite | 62 | 62 | = | |
| Lite stitches (.mp4) | 6 scenes | 6 scenes | = | scene001-004,006,008 |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |
| P0 blockers | 0 | 0 | = | Clean |
| Idle generation reports | 8 | **9** | **+1** | R20-R28 |
| Idle code reports | 1 | **2** | **+1** | Post-R26 stable |
| New observations | 1 | 1 | = | System stability + cadence |

---

## 10. GENERATION READINESS ASSESSMENT (R28)

**System is fully operational. Two META-CHRONIC data patches recommended before generation. All wires and governance hooks confirmed intact. No new issues or code changes since R26. Session enforcer HEALTHY. P0 count: 0.**

**Recommended next generation sequence (unchanged from R26/R27):**

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

**Production state:** 6 scenes with lite stitch (001/002/003/004/006/008). Scene 001 M-shots need re-generation (OPEN-010 META-CHRONIC). Scene 008 M03b/M04 need REGEN_REQUESTED resolution. Total ~12 min data patches + ~30 min generation to reach clean state.

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T06:09:00Z",
  "ledger_age_hours": 21.35,
  "run_number": 28,
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-31_R27_KEEPUP_LATEST.md",
  "meta_chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 17,
      "class": "META-CHRONIC",
      "description": "4 shots (008_E01/E02/E03/M03b) still have /api/media?path= prefix in video_url. first_frame_url RESOLVED (R23).",
      "progress_this_cycle": "No change from R27. video_url patch not applied. Runner and shot_plan.json unchanged.",
      "proof_receipt": "python3 scan → API_PATH_VIDEO_URL: ['008_E01','008_E02','008_E03','008_M03b']",
      "fix_recipe": "Strip /api/media?path= from video_url on 008_E01/E02/E03/M03b — no code change, ~2 min",
      "regression_guard": ["session_enforcer still HEALTHY after patch", "do not touch first_frame_url (fixed R23)"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 14,
      "class": "META-CHRONIC",
      "description": "4 shots (001_M02-M05) have ghost first_frame_url pointing to non-existent files, all APPROVED.",
      "progress_this_cycle": "No change from R27. No operator action. Runner and shot_plan.json unchanged.",
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
      "id": "NEW-R28-001",
      "class": "STABILITY_CONFIRMATION",
      "description": "Runner mtime identical to R27 (23:46:04 EDT). All wire line positions stable across 3 reports (R26/R27/R28). 9th consecutive idle generation cycle.",
      "impact": "BENIGN — system in clean steady-state, awaiting operator generation trigger"
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
  "consecutive_idle_generation_reports": 9,
  "consecutive_idle_code_reports": 2,
  "data_patch_applied_since_prior": false,
  "code_changes_since_prior": 0,
  "new_generation_since_prior": 0,
  "session_enforcer_result": "HEALTHY",
  "learning_log_regressions": 0,
  "recommended_next_action": "apply_both_meta_chronic_data_patches_then_generation",
  "p0_blockers": 0,
  "confirmed_fixed_count": 23,
  "meta_chronic_count": 2,
  "stale_doc_count": 2,
  "architectural_debt_count": 1,
  "production_gap_count": 1,
  "new_issues_this_cycle": 0,
  "runner_line_positions_canonical_r28": {
    "_fail_sids": 5700,
    "enrich_shots_with_arc_call": 4933,
    "isinstance_guard": 1512,
    "ACTIVE_VIDEO_MODEL": 535,
    "LTX_FAST_guard": 505,
    "runner_total_lines": 6179,
    "runner_mtime": "2026-03-30T23:46:04-04:00",
    "note": "All positions stable across R26/R27/R28 — 3-report stability confirmed"
  }
}
```
