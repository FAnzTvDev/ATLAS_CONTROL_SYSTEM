# ATLAS ERROR DEEPDIVE — 2026-03-31 R33 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T11:11:30Z
**Run number:** R33
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R32_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 1d 2h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R32 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (**22nd**) + OPEN-010 (**19th**) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **32nd** report |
| STALE_DOC | 2 | OPEN-003 (**32nd**), OPEN-005 (**30th**) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R32** | **0** | **= (idle)** | **Runner mtime unchanged at 23:46:04 EDT — 7th consecutive idle-code cycle post-R26** |
| **DATA CHANGES SINCE R32** | **0** | = | shot_plan.json mtime unchanged (20:22:12 EDT) |
| **GENERATION SINCE R32** | **0 frames, 0 videos** | = | **System idle — 14th consecutive idle generation report (R20–R33)** |

**Key findings R33:**

1. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (ALL CLEAR, 22 fixes verified). Wire-A=6 hits, Wire-C=6 hits (12 combined). Wire-B logic at runner:5700. V37 governance: `_V37|v37` refs=31 in runner (non-blocking hooks), /api/v37 endpoints=7 in orchestrator. CPC count=4. All canonical line positions stable — **7th consecutive idle-code cycle**.

2. 🟢 **ALL CANONICAL LINE POSITIONS STABLE (R32 → R33).** Runner total lines: 6,179 (unchanged). `_fail_sids` at runner:5700, `enrich_shots_with_arc` call at runner:4933, `isinstance` guard at runner:1512, `ACTIVE_VIDEO_MODEL` at runner:535, `LTX_FAST` guard at runner:505. **7th consecutive idle-code cycle post-R26.**

3. 🔴 **OPEN-009 META-CHRONIC: 22nd consecutive report (R12→R33).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied. ~2 min edit remains unapplied.

4. 🔴 **OPEN-010 META-CHRONIC: 19th consecutive report (R15→R33).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all APPROVED. No operator action since META-CHRONIC escalation at R24.

5. 🟡 **SYSTEM IDLE (GENERATION) — 14th consecutive idle report (R20–R33).** No new frames or videos. Ledger age: 1d 2h 21m (+59m from R32). Average cycle cadence: ~60.1m/cycle (consistent).

6. 🟡 **006_M02/M04 AWAITING_APPROVAL (13th consecutive report, R21–R33).** 008_M03b + 008_M04 REGEN_REQUESTED (unchanged since R21). No operator action.

7. 🟡 **REWARD SIGNAL FROZEN — 32nd consecutive report.** 228 ledger entries (unchanged). 87.8% heuristic I=0.75 (36/41 last-entry-per-shot). 5 real-VLM shots unchanged: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). Self-resolves on next generation run. **Ledger now 1d 2h+ stale.**

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R33) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1512. 97/97 arc positions. 62/62 M-shots with `_chain_group`. shot_plan.json mtime 20:22:12 EDT (unchanged from R32). | `isinstance(sp, list)` at runner:1512 ✅; runner:4506 guard ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` count=4 in runner (unchanged). CPC confirmed wired at lines 87/2380/3247. | `grep -c "_cpc_decontaminate" runner` → 4 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 30th). `_LTXRetiredGuard` error says "Use Seedance" (retired V31.0). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:535). CLAUDE.md V36.5 accurate. | runner:24 Seedance claim confirmed ✅; runner:535 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (22 fixes). Wire-A (6 hits), Wire-C (6 hits), `_fail_sids` at runner:5700. `enrich_shots_with_arc` imported at runner:65, called at runner:4933. | Session enforcer R33 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic per session_enforcer). OPEN-009: 4 API-path video_urls (22nd). OPEN-010: 4 ghost first_frame_urls (19th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, **1d 2h 21m stale**). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). | Ledger scan R33 ✅ — identical to R32 |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/ (both unchanged). 6 scene_lite.mp4 files confirmed (scene001/002/003/004/006/008). OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED. run_report: success=True, errors=[]. | File counts + shot_plan scan R33 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5700 ✅. 6 scene_lite.mp4 files confirmed — all mtimes unchanged. | `grep -n "_fail_sids"` → runner:5700 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits (lines 2507/2511/2516/2532/2536/2539). Wire-C: 6 hits (lines 5459/5479/5481/5484/5486/5488). Runner stable — no modification since R26 expansion (7th idle-code cycle). | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (30th). LTX guard error message says "Use Seedance" (persists). CLAUDE.md V36.5 correct. | Confirmed via `sed -n '24p'` and lines 498-510 R33 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R33. Identical to R26/R27/R28/R29/R30/R31/R32.

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
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (mtime 15:43:25 EDT unchanged).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R33 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R33 (lines 5459/5479/5481/5484/5486/5488).
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:535 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=4 in runner.
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (22 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R33 status vs R32:** UNCHANGED. No data patch applied. Runner mtime unchanged — no code change. shot_plan.json mtime unchanged (20:22:12 EDT).

**META-CHRONIC: 22nd consecutive report (R12→R33).**

**PROOF RECEIPT (R33 live):**
```
PROOF: python3 scan → shots where '/api/media' in video_url
OUTPUT: ['008_E01', '008_E02', '008_E03', '008_M03b']
EXACT VALUES (unchanged from R32):
  008_E01: video_url=/api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_E01
  008_E02: video_url=/api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_E02
  008_E03: video_url=/api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_E03
  008_M03b: video_url=/api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_M03
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

**Classification:** META-CHRONIC (22nd report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (19 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 19th consecutive report.

**R33 status vs R32:** UNCHANGED. No operator action. shot_plan.json mtime unchanged. Runner stable.

**META-CHRONIC STATUS:** 19 consecutive reports (R15→R33). META-CHRONIC since R24.

**PROOF RECEIPT (R33 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R32. 19th consecutive confirmation.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk. scene001_lite.mp4 (confirmed present) was generated using the chain from M01. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk. scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05.

**Classification:** META-CHRONIC (19th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **32nd consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger now **1d 2h 21m stale** — over 26 hours since last entry.

**PROOF RECEIPT (R33 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis + ledger age
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R32)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8% (87%)
  LAST_I_REAL_VLM: 5/41 — [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 1d 2h 21m (+59m from R32, >26 hours stale)
CONFIRMS: No new generation. Identical distribution to R32.
```

**Classification:** ARCHITECTURAL_DEBT (32nd report). Resolves on next generation run. Vision backends: 4 available confirmed via session_enforcer.

---

### OPEN-003 (STALE_DOC — **32nd consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5700 (confirmed stable R33 — line position unchanged from R26).

**PROOF (R33 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5700 ✅
CONFIRMS: WIRE-B label absent. Logic intact. Line position stable at 5700 (8th consecutive confirmation since R26 baseline).
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5700. One line.

**Classification:** STALE_DOC. 32nd consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — **30th consecutive report**)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:535). Additionally, `_LTXRetiredGuard.__getattr__` at runner:505 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — stale guidance since Seedance is also retired (V31.0).

**PROOF (R33 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: runner lines 498-510 contain _LTXRetiredGuard with "Use Seedance" messages
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:535: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Both stale docstring references persist unchanged from R32. Code behavior correct.
```

**Classification:** STALE_DOC. 30th consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (13th consecutive report, R21–R33)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists. Videos generated but not reviewed by operator. 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21.

**PROOF (R33 live):**
```
PROOF: python3 shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 13th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 13th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R32.

---

## 6. NEW OBSERVATIONS (R33 only)

### 6.1 Fourteenth Consecutive Idle Generation Report — R20 Through R33

System has produced zero new frames or videos across 14 consecutive keep-up cycles (R20–R33). All wires intact, all 23 confirmed-fixed items verified, 0 regressions, session enforcer HEALTHY. The two META-CHRONIC data patches (~12 min combined) remain unapplied for the 22nd and 19th cycle respectively. No P0 blockers exist.

### 6.2 Ledger Now 26+ Hours Stale (R33)

The reward ledger last entry (2026-03-30T08:47:31) is now 1d 2h 21m old — over 26 hours without generation. This is a PRODUCTION_GAP milestone continuation, not a code failure. All vision backends remain available (4 confirmed) and will fire on next generation run.

### 6.3 Seven Consecutive Idle Code Cycles (R27→R33)

Runner mtime (23:46:04 EDT 2026-03-30) and orchestrator mtime (15:43:25 EDT 2026-03-30) are identical across R27, R28, R29, R30, R31, R32, and now R33 — **seven consecutive reports with zero code modification.** Canonical wire positions stable across eight consecutive confirmations (R26 baseline → R33):

| Wire | Line (R26) | R27 | R28 | R29 | R30 | R31 | R32 | **R33** | Status |
|------|-----------|-----|-----|-----|-----|-----|-----|---------|--------|
| `_fail_sids` (Wire-B logic) | 5700 | 5700 | 5700 | 5700 | 5700 | 5700 | 5700 | **5700** | ✅ Stable |
| `enrich_shots_with_arc` call | 4933 | 4933 | 4933 | 4933 | 4933 | 4933 | 4933 | **4933** | ✅ Stable |
| `isinstance` guard | 1512 | 1512 | 1512 | 1512 | 1512 | 1512 | 1512 | **1512** | ✅ Stable |
| `ACTIVE_VIDEO_MODEL` | 535 | 535 | 535 | 535 | 535 | 535 | 535 | **535** | ✅ Stable |
| `LTX_FAST` guard | 505 | 505 | 505 | 505 | 505 | 505 | 505 | **505** | ✅ Stable |

### 6.4 Ledger Staleness Trend (14-Report View)

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
| R30 | 23h21m | +59m |
| R31 | 24h21m (1d 0h 21m) | +60m ⚠️ >24h |
| R32 | 25h22m (1d 1h 22m) | +61m ⚠️ >25h |
| **R33** | **26h21m (1d 2h 21m)** | **+59m ⚠️ >26h** |

Cadence: 59–61m per cycle. Automated keep-up running on schedule. Average cadence: ~60.1m/cycle. 14th cycle.

### 6.5 META-CHRONIC Persistence Summary (Updated R33)

| Issue | First Appeared | META-CHRONIC Since | Consecutive Reports |
|-------|---------------|-------------------|---------------------|
| OPEN-009 (video_url patch) | R12 | R12 | **22 (R12→R33)** |
| OPEN-010 (ghost frames regen) | R15 | R24 | **19 (R15→R33; META-CHRONIC from R24)** |

Combined operator fix time: ~12 min. Neither blocks active generation.

### 6.6 No Proof Gate Report Available

No `ATLAS_PROOF_GATE_*.md` files found. Proof gate classifications are not available to override keep-up classifications this cycle.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, **22nd META-CHRONIC** |
| **P1** | OPEN-010 (ghost frames + re-gen 001 M-shots) | 10 min | Clear first_frame_url + reset approval for 001_M02-M05, then --frames-only scene 001 | NO — but META-CHRONIC data integrity risk if re-stitch attempted |
| **P2** | 006_M02/M04 AWAITING_APPROVAL | 2 min | Operator review in UI → thumbs-up or thumbs-down | NO — production gap |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge fires with Gemini/OpenRouter | NO — observational; ledger now >26h stale |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5700 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance + LTX error msg) | 3 min | Update runner header line 24 + fix `_LTXRetiredGuard` error message to say "Use Kling" | NO — cosmetic |

**P0 count: 0. No P0 blockers. System ready for generation.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R33: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (count=4 confirmed R33)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R33 via session_enforcer: HEALTHY)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4). Only re-stitch if M03b/M04 regen'd.
□ Canonical runner line positions (stable from R26, verified R27/R28/R29/R30/R31/R32/R33): _fail_sids=5700, enrich_shots_with_arc=4933, isinstance=1512, ACTIVE_VIDEO_MODEL=535, LTX_FAST guard=505.
```

---

## 9. DELTA FROM R32

| Signal | R32 | R33 | Delta | Note |
|--------|-----|-----|-------|------|
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (**22nd**) + OPEN-010 (**19th**) |
| **OPEN-009 consecutive** | 21 | **22** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 18 | **19** | **+1** | No operator action |
| **OPEN-002 consecutive** | 31 | **32** | **+1** | ARCHITECTURAL_DEBT |
| **OPEN-003 consecutive** | 31 | **32** | **+1** | STALE_DOC |
| **OPEN-005 consecutive** | 29 | **30** | **+1** | STALE_DOC |
| **PRODUCTION_GAP (AWAITING)** | 12th | **13th** | **+1** | 006_M02/M04 + 008_M03b/M04 |
| **Idle generation reports** | 13th (R20-R32) | **14th (R20-R33)** | **+1** | 0 new frames/videos |
| **Idle code cycles** | 6th | **7th** | **+1** | Runner/orchestrator mtimes unchanged |
| **Ledger age** | 25h22m | **26h21m** | **+59m** | >26h stale |
| **Ledger entries** | 228 | 228 | = | No new generation |
| **Confirmed fixed** | 23 | 23 | = | 0 regressions |
| **Regressions** | 0 | **0** | = | ALL CLEAR |
| **first_frames/** | 62 | 62 | = | Unchanged |
| **videos_kling_lite/** | 62 | 62 | = | Unchanged |
| **Session enforcer** | ✅ HEALTHY | **✅ HEALTHY** | = | 0 blocks |

---

## 10. DOCUMENT LINEAGE

- **Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R32_KEEPUP_LATEST.md
- **This report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R33_KEEPUP_LATEST.md
- **Next report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R34_KEEPUP_LATEST.md (expected ~2026-03-31T12:11Z)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T11:11:30Z",
  "ledger_age_hours": 26.35,
  "run_number": 33,
  "delta_from_prior": "+59m",
  "idle_generation_cycles": 14,
  "idle_code_cycles": 7,
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 22,
      "class": "META-CHRONIC",
      "first_report": "R12",
      "proof_receipt": "python3 scan: ['008_E01','008_E02','008_E03','008_M03b'] have /api/media?path= in video_url — 4 shots confirmed",
      "fix_recipe": "Strip /api/media?path= prefix from video_url on 4 shots in shot_plan.json — data patch only, ~2 min",
      "regression_guard": ["first_frame_url (fixed R23)", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 19,
      "class": "META-CHRONIC",
      "first_report": "R15",
      "proof_receipt": "python3 scan: 001_M02/M03/M04/M05 — first_frame_url points to non-existent files, all APPROVED",
      "fix_recipe": "Clear first_frame_url + set AWAITING_APPROVAL for 001_M02-M05, then --frames-only scene 001",
      "regression_guard": ["001_M01.jpg (present)", "scene001_lite.mp4 (preserved)", "shots outside 001_M02-M05"]
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "consecutive_reports": 32,
      "class": "ARCHITECTURAL_DEBT",
      "description": "87.8% heuristic I-scores, ledger 26h+ stale — self-resolves on next generation run"
    }
  ],
  "stale_docs": [
    {"id": "OPEN-003", "consecutive_reports": 32, "description": "No [WIRE-B] label at runner:5700 — logic functional"},
    {"id": "OPEN-005", "consecutive_reports": 30, "description": "Runner header Seedance claim + LTX error message stale — code correct"}
  ],
  "false_positives_retracted": [],
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
  "confirmed_fixed_count": 23,
  "regressions": 0,
  "session_enforcer": "HEALTHY",
  "wire_counts": {"wire_a": 6, "wire_b_logic": "runner:5700 functional (label absent)", "wire_c": 6},
  "generation_state": {
    "first_frames": 62,
    "videos": 62,
    "scene_lite_mp4s": 6,
    "awaiting_approval": ["006_M02", "006_M04"],
    "regen_requested": ["008_M03b", "008_M04"],
    "ghost_first_frame_urls": ["001_M02", "001_M03", "001_M04", "001_M05"],
    "api_prefix_video_urls": ["008_E01", "008_E02", "008_E03", "008_M03b"]
  },
  "recommended_next_action": "no_action — system healthy, no P0 blockers; operator should apply 2 META-CHRONIC data patches (~12 min) and run generation to resolve OPEN-002 ledger staleness"
}
```
