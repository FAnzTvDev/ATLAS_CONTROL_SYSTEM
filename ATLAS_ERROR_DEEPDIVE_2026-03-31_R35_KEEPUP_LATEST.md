# ATLAS ERROR DEEPDIVE — 2026-03-31 R35 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T13:11:00Z
**Run number:** R35
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R34_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 1d 4h 22m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R34 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (**24th**) + OPEN-010 (**21st**) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **34th** report |
| STALE_DOC | 2 | OPEN-003 (**34th**), OPEN-005 (**32nd**) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R34** | **2 🆕** | **+2 (ACTIVE)** | Runner +33 lines (6,185→6,218). New module: `tools/run_lock.py` (created 08:31 EDT). Second code change today; R34 noted first (+6 lines, CPC tracking at 07:52 EDT). |
| **DATA CHANGES SINCE R34** | **0** | = | shot_plan.json mtime unchanged (20:22:12 EDT 2026-03-30) |
| **GENERATION SINCE R34** | **0 frames, 0 videos** | = | **System idle — 16th consecutive idle generation report (R20–R35)** |

**Key findings R35:**

1. 🆕 **SECOND CODE CYCLE TODAY — `tools/run_lock.py` created (08:31 EDT) + runner wired (+33 lines at 08:32 EDT).** New V37 Run Lock system: `tools/run_lock.py` (2,883 bytes, 80 lines). Defines 7 verified systems + 5 blocked systems. Runner imports `from run_lock import is_system_allowed, get_run_lock_report, reset_run_lock` with `_RUN_LOCK_AVAILABLE` flag at lines 95–103. CLI gains `--locked` (default, enables regression guard) and `--unlocked` (dev override) flags. **Non-blocking: stubs degrade gracefully if import fails.** Session enforcer ✅ SYSTEM HEALTHY — change is non-regressing.

2. ⚠️ **NEW OBSERVATION: `_RUN_LOCK_AVAILABLE` NOT YET PROBED IN SESSION_ENFORCER.** session_enforcer.py was last modified 2026-03-29 (before run_lock.py was created today). Per UPGRADE VALIDATION PROTOCOL, wiring probes for new modules should be added to session_enforcer. The run_lock import pattern follows the same non-blocking stub pattern as `_VVO_AVAILABLE`, `_SMART_STITCHER`, etc. — but none of those patterns includes a session_enforcer probe either. Low priority (system healthy, stubs prevent crashes). Flagged as OBSERVATION, not CONFIRMED_BUG.

3. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (22 fixes, ALL CLEAR). Wire-A=6, Wire-C=6 (12 combined unchanged). Wire-B logic at runner:5717 (+11 from R34:5706 — consistent with +9 from run_lock import block + 2-line minor discrepancy). Arc call: 4950 (+11 from R34:4939). isinstance guard: 1523 (stable — before insertion point). ACTIVE_VIDEO_MODEL: 546 (was 535 in R34 — **+11 shift noted, was 535 in R33/R34, now 546**). LTX guard: 516 (was 505 in R34 — +11).

4. 🔴 **OPEN-009 META-CHRONIC: 24th consecutive report (R12→R35).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied. shot_plan.json mtime unchanged.

5. 🔴 **OPEN-010 META-CHRONIC: 21st consecutive report (R15→R35).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all APPROVED. No operator action.

6. 🟡 **SYSTEM IDLE (GENERATION) — 16th consecutive idle report (R20–R35).** No new frames or videos. Ledger age: 1d 4h 22m (+~55m from R34). Average cadence: ~60.4m/cycle.

7. 🟡 **006_M02/M04 AWAITING_APPROVAL (15th consecutive report, R21–R35).** 008_M03b + 008_M04 REGEN_REQUESTED (unchanged since R21). 0 HUMAN_ESCALATION shots.

8. 🟡 **REWARD SIGNAL FROZEN — 34th consecutive report.** 228 ledger entries (unchanged). 87.8% heuristic I=0.75 (36/41 last-entry-per-shot). Self-resolves on next generation run. **Ledger now 1d 4h 22m stale.**

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R35) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1523 (+11 from R34:1512 — consistent with +11 shift). 97/97 arc positions (ESTABLISH/ESCALATE/PIVOT/RESOLVE). 62/62 M-shots with `_chain_group`. shot_plan.json mtime 20:22:12 EDT (unchanged). | `isinstance(sp, list)` at runner:1523 ✅; arc scan ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` count=5 in runner (stable from R34). CPC call sites: runner:2391, 2682, 3264 (+11 shift from R34:2380, 2671, 3253). Import at runner:87, fallback at runner:91, `_CPC_DECONTAM_AVAILABLE` at runner:88/92. | `grep -c "_cpc_decontaminate" runner` → 5 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 32nd). `_LTXRetiredGuard` error says "Use Seedance" (retired V31.0). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:546). CLAUDE.md V36.5 accurate. | runner:24 Seedance claim confirmed ✅; runner:546 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (22 fixes). Wire-A (6 hits), Wire-C (6 hits), `_fail_sids` at runner:5717 (+11 from R34). `enrich_shots_with_arc` imported at runner:65 (stable), called at runner:4950 (+11 from R34:4939). `_RUN_LOCK_AVAILABLE` wired at runner:95–103 (NEW — not yet probed by enforcer). | Session enforcer R35 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic per session_enforcer). OPEN-009: 4 API-path video_urls (24th). OPEN-010: 4 ghost first_frame_urls (21st). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, **1d 4h 22m stale**). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). Identical to R34. | Ledger scan R35 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/ (unchanged). 6 scene_lite.mp4 + 4 scene_lite_audio.mp4 (created 2026-03-30, first noted R34). OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED, 0 HUMAN_ESCALATION. run_report: success=True, errors=[]. | File counts + shot_plan scan R35 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5717 (shifted +11 from R34:5706, logic functional) ✅. 6 scene_lite.mp4 + 4 audio variants unchanged since 2026-03-30. | `grep -n "_fail_sids"` → runner:5717 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits. Wire-C: 6 hits. 12 combined unchanged. Positions shifted +11 from R34 consistent with insertion. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (32nd). LTX guard error message says "Use Seedance" (persists). CLAUDE.md V36.5 correct. | Confirmed via grep R35 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R35. Identical to R26–R34.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:546.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:516.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1523.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65 (stable), called at runner:4950 (+11 from R34:4939 — consistent with +11 shift).
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator.
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R35 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R35.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:546 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=5 in runner (stable; call sites 2391/2682/3264 shifted +11 — consistent).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (24 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. first_frame_url was fully fixed (operator data patch, R23). All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R35 status vs R34:** UNCHANGED. No data patch applied. shot_plan.json mtime unchanged (20:22:12 EDT 2026-03-30).

**META-CHRONIC: 24th consecutive report (R12→R35).**

**PROOF RECEIPT (R35 live):**
```
PROOF: python3 scan → shots where '/api/media' in video_url
OUTPUT: ['008_E01', '008_E02', '008_E03', '008_M03b']
EXACT VALUES (unchanged from R12–R34):
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
# Total: 4 field changes, ~2 min
# Verify: grep "/api/media" pipeline_outputs/victorian_shadows_ep1/shot_plan.json | wc -l → 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url`, `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` still HEALTHY.

**Classification:** META-CHRONIC (24th report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (21 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 21st consecutive report.

**R35 status vs R34:** UNCHANGED. No operator action. shot_plan.json mtime unchanged.

**META-CHRONIC STATUS:** 21 consecutive reports (R15→R35). META-CHRONIC since R24.

**PROOF RECEIPT (R35 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R34. 21st consecutive confirmation.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk. scene001_lite.mp4 confirmed present (08:47 EDT 2026-03-30). UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk. scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05.

**Classification:** META-CHRONIC (21st report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **34th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger now **1d 4h 22m stale** — over 28 hours since last entry.

**PROOF RECEIPT (R35 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis + ledger age
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R34)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 — [('008_M01',1.0),('004_M01',1.0),('004_M02',1.0),('008_M02',0.9),('008_M04',0.8)]
  LEDGER_AGE: 1d 4h 22m (+55m from R34)
CONFIRMS: No new generation. Identical distribution to R34.
```

**Classification:** ARCHITECTURAL_DEBT (34th report). Resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **34th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5717 (shifted +11 from R34:5706 — consistent with +11 line insertion pattern confirmed R35).

**PROOF (R35 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5717 ✅ (+11 from R34:5706 consistent)
CONFIRMS: WIRE-B label absent. Logic intact. Line position shift (+11) consistent with R35 code insertions.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5717. One line.

**Classification:** STALE_DOC. 34th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — **32nd consecutive report**)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:546). Additionally, `_LTXRetiredGuard.__getattr__` at runner:516 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — stale guidance since Seedance is also retired (V31.0).

**PROOF (R35 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1 → runner:546 → "kling" ✅
PROOF: runner:516 → LTX_FAST = _LTXRetiredGuard() with stale "Use Seedance" message
CONFIRMS: Both stale docstring references persist unchanged from R34. Code behavior correct.
```

**Classification:** STALE_DOC. 32nd consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (15th consecutive report, R21–R35)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists. Videos generated but not reviewed by operator. 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21. 0 HUMAN_ESCALATION shots.

**PROOF (R35 live):**
```
PROOF: python3 shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 15th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 15th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R34.

---

## 6. NEW OBSERVATIONS (R35 only)

### 6.1 🆕 V37 RUN LOCK SYSTEM — `tools/run_lock.py` Created (08:31 EDT)

**What it is:** New `tools/run_lock.py` module (80 lines, 2,883 bytes) defines the V37 Regression Guard. It maintains two lists:
- `V37_VERIFIED_SYSTEMS` (7 entries): nano_eshot_frames, kling_video_gen, chain_propagation, vvo_character_bleed, prompt_decontamination, chain_intelligence_gate, consciousness_controller.
- `V37_BLOCKED_SYSTEMS` (5 entries): v26_orchestrator, seedance_pipeline, old_frame_reuse, independent_m_frames, duplicate_vvo_preflight.

**What it does:** `RunLock` singleton class. `is_system_allowed(name)` returns True for verified, False+log for blocked, False+log for unknown. `get_run_lock_report()` returns status dict. `reset_run_lock()` resets singleton for new run.

**Runner wiring (lines 95–103 + 6176–6218):**
- Import block: `from run_lock import is_system_allowed, get_run_lock_report, reset_run_lock` with `_RUN_LOCK_AVAILABLE = True/False` tracking.
- CLI `--locked` flag (default on): calls `reset_run_lock()` + `get_run_lock_report()` at preflight, announces verified count (7).
- CLI `--unlocked` flag: prints warning, continues without lock.
- Post-run report: prints blocked attempt count if any.

**Non-blocking:** Stubs prevent crashes if `run_lock.py` is unavailable. `is_system_allowed` stub returns True (pass-through). System remains fully functional without run_lock.

**Pattern match:** Follows established runner pattern (`_VVO_AVAILABLE`, `_SMART_STITCHER`, `_LYRIA_SOUNDSCAPE`, `_V37_GOVERNANCE`).

### 6.2 ⚠️ SESSION_ENFORCER NOT YET UPDATED FOR RUN_LOCK

**Observation:** `tools/session_enforcer.py` was last modified 2026-03-29 22:38 EDT — before `tools/run_lock.py` was created today. Per UPGRADE VALIDATION PROTOCOL (CLAUDE.md Section 3):

> "Add WIRING PROBE to session_enforcer.py — probe checks that the module is CALLED (not just imported) in the runner"

The run_lock module follows G3 (session_enforcer passes — SYSTEM HEALTHY) because the enforcer doesn't probe for it. The G4 gate (live generation test) has also not been run. This means run_lock is at level WIRED (runner imports it) but not PROVEN (no live generation test has confirmed its effect).

**Impact:** LOW — system degrades gracefully to pass-through stubs. The run_lock does not affect any existing generation behavior; it only adds preflight logging and post-run blocked-attempt reporting. No quality gate depends on it.

**Classification:** OBSERVATION (not CONFIRMED_BUG). Enforcer will update naturally when operator adds probe.

### 6.3 LINE ANCHOR SHIFT AUDIT (R35 vs R34 — +11 total)

The runner grew from 6,185 (R34) to 6,218 (R35) = **+33 lines**. The `_fail_sids` anchor shifted from 5706→5717 = **+11** (not +33 — the bulk of +33 was at end of file in CLI/main block which is after _fail_sids). Breakdown:

| Wire/Anchor | R33 | R34 | R35 | R33→R35 Δ |
|-------------|-----|-----|-----|-----------|
| `isinstance` guard | 1512 | 1512 | 1523 | +11 |
| `ACTIVE_VIDEO_MODEL` | 535 | 535 | 546 | +11 |
| `LTX_FAST` guard | 505 | 505 | 516 | +11 |
| `enrich_shots_with_arc` call | 4933 | 4939 | 4950 | +17 |
| `_fail_sids` (Wire-B logic) | 5700 | 5706 | 5717 | +17 |
| Total lines | 6,179 | 6,185 | 6,218 | +39 |

Note: R34 inserted ~line 88 (+6 shift for code after that point). R35 inserted at ~line 95 (run_lock block, +9 lines) which shifted lines after 95 by +9 cumulative with R34's +6 = +15 total cumulative. But _fail_sids and enrich_shots_with_arc shifted +17 from R33 (not +15), suggesting a small additional edit near those function bodies or minor line count discrepancy in R33 baseline. The +33 total includes ~24 lines in the CLI main block (after _fail_sids location) which would NOT shift _fail_sids. All logic verified intact.

### 6.4 SIXTEENTH CONSECUTIVE IDLE GENERATION REPORT — R20 THROUGH R35

System has produced zero new frames or videos across 16 consecutive keep-up cycles (R20–R35). Two META-CHRONIC data patches (~12 min combined) remain unapplied for the 24th and 21st cycle respectively. Code activity is high (3 runner modifications this week: R26 CPC tracking, R34 CPC availability flags, R35 run_lock wiring) but no generation triggered.

### 6.5 Ledger Staleness Trend (Updated R35)

| Report | Ledger Age | Delta |
|--------|-----------|-------|
| R20 | 13h21m | — |
| R30 | 23h21m | +~60m/cycle |
| R34 | 1d 3h 27m | ~60m/cycle |
| R35 | 1d 4h 22m | **+55m** |

Consistent ~60min/cycle growth. At current rate: **R40 ≈ 1d 9h stale**.

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC items:

| Priority | Issue | Class | Est. Time | Fix Type |
|----------|-------|-------|-----------|----------|
| P1 | OPEN-009: 4 video_url API-path prefix (24th report) | META-CHRONIC | ~2 min | Data patch (shot_plan.json, 4 fields) |
| P2 | OPEN-010: 4 ghost first_frame_url + regen 001_M02-M05 (21st report) | META-CHRONIC | ~15 min | Data patch + `--frames-only` run |
| P3 | OPEN-003: Add `[WIRE-B]` comment at runner:5717 | STALE_DOC | <1 min | 1-line code comment |
| P4 | OPEN-005: Fix runner line 24 + LTX guard message | STALE_DOC | ~2 min | 2-line docstring edit |

**NOT listed (correct omissions):**
- OPEN-002 (ARCHITECTURAL_DEBT — no quick fix)
- run_lock enforcer probe (OBSERVATION — non-blocking)
- Ledger staleness (PRODUCTION_GAP — self-resolves on generation)

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL = "kling" — runner:546 ✅
□ LTX_FAST = _LTXRetiredGuard() — runner:516 ✅
□ isinstance guard — runner:1523 ✅
□ enrich_shots_with_arc imported — runner:65 ✅
□ enrich_shots_with_arc called — runner:4950 ✅
□ Wire-A hits — 6 ✅
□ Wire-C hits — 6 ✅
□ Wire-B _fail_sids — runner:5717 ✅
□ CPC decontaminate — 3 call sites (2391/2682/3264) ✅
□ Session enforcer → SYSTEM HEALTHY ✅
□ Learning log → 0 regressions (22 fixes) ✅
□ V37 governance refs — 31 in runner ✅
□ /api/v37 endpoints — 7 in orchestrator ✅
□ All 5 env keys PRESENT ✅
□ run_report success=True, errors=[] ✅
```

---

## 9. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R34_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R35_KEEPUP_LATEST.md`
**Run number delta:** R34 → R35 (+1)
**Open issues carried forward:** OPEN-002 (34th), OPEN-003 (34th), OPEN-005 (32nd), OPEN-009 (24th), OPEN-010 (21st), PRODUCTION_GAP (15th)
**New issues added:** 0
**False positives retracted:** 0
**Consecutive idle generation cycles:** 16 (R20–R35)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T13:11:00Z",
  "ledger_age_hours": 28.37,
  "runner_lines": 6218,
  "runner_mtime": "2026-03-31T08:32:39-04:00",
  "new_modules_this_cycle": ["tools/run_lock.py"],
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 24,
      "class": "META-CHRONIC",
      "proof_receipt": "python3 scan → ['008_E01', '008_E02', '008_E03', '008_M03b'] have /api/media?path= in video_url",
      "fix_recipe": "video_url.replace('/api/media?path=', '') on 4 shots in shot_plan.json",
      "regression_guard": ["first_frame_url untouched", "session_enforcer HEALTHY after patch"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 21,
      "class": "META-CHRONIC",
      "proof_receipt": "python3 os.path.exists → 001_M02/M03/M04/M05 first_frame_url missing from disk, all APPROVED",
      "fix_recipe": "Set first_frame_url='' + _approval_status=AWAITING_APPROVAL, run --frames-only for scene 001",
      "regression_guard": ["001_M01.jpg preserved", "scene001_lite.mp4 preserved"]
    }
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
  "session_enforcer_result": "SYSTEM_HEALTHY",
  "learning_log_regressions": 0,
  "wire_counts": {"wire_a": 6, "wire_c": 6, "wire_b_location": 5717},
  "new_module_probe_gap": {
    "module": "tools/run_lock.py",
    "in_runner": true,
    "in_session_enforcer": false,
    "impact": "LOW — non-blocking stubs prevent crash; pass-through behavior unchanged"
  },
  "recommended_next_action": "apply_data_patch_OPEN009_OPEN010",
  "recommended_secondary_action": "run_proof_gate",
  "generation_idle_cycles": 16
}
```
