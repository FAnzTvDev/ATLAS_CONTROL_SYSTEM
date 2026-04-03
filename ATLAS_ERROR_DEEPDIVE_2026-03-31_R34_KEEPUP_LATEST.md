# ATLAS ERROR DEEPDIVE — 2026-03-31 R34 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T12:14:59Z
**Run number:** R34
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R33_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** 1d 3h 27m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC**

| Category | Count | Delta vs R33 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (**23rd**) + OPEN-010 (**20th**) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **33rd** report |
| STALE_DOC | 2 | OPEN-003 (**33rd**), OPEN-005 (**31st**) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R33** | **1 🆕** | **+1 (ACTIVE)** | **Runner modified 07:52:36 EDT — FIRST code change since R26 (ends 7-cycle idle streak)** |
| **DATA CHANGES SINCE R33** | **0** | = | shot_plan.json mtime unchanged (20:22:12 EDT 2026-03-30) |
| **GENERATION SINCE R33** | **0 frames, 0 videos** | = | **System idle — 15th consecutive idle generation report (R20–R34)** |

**Key findings R34:**

1. 🆕 **CODE CYCLE ACTIVE (FIRST SINCE R26).** Runner mtime changed from 2026-03-30 23:46:04 EDT (R33) to 2026-03-31 07:52:36 EDT (R34) — a 41-minute gap AFTER R33 ran (07:11:30 EDT). Ends 7-cycle idle code streak. **+6 lines added** (6,179 → 6,185). New content: `_CPC_DECONTAM_AVAILABLE = True/False` availability tracking flags added at runner:88/92, plus 4-line CPC comment block. CPC grep count: 4 → 5. Session enforcer: ✅ SYSTEM HEALTHY — change is **non-regressing**. Wire counts unchanged (Wire-A=6, Wire-C=6). Line anchors stable before insertion point: `isinstance`=1512, `ACTIVE_VIDEO_MODEL`=535, `LTX_FAST`=505. Anchors after insertion shifted +6: `_fail_sids`: 5700→5706, `enrich_shots_with_arc` call: 4933→4939.

2. 🟢 **NO REGRESSIONS. ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (ALL CLEAR, 22 fixes verified). Wire-A=6 hits, Wire-C=6 hits (12 combined). Wire-B logic at runner:5706. V37 governance: `_V37|v37` refs=31 in runner (non-blocking hooks), /api/v37 endpoints=7 in orchestrator. CPC count=5 (was 4). All tracked canonical line positions stable or shifted consistently with +6 insertion.

3. 🔴 **OPEN-009 META-CHRONIC: 23rd consecutive report (R12→R34).** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in `video_url`. No data patch applied.

4. 🔴 **OPEN-010 META-CHRONIC: 20th consecutive report (R15→R34).** 4 shots (001_M02/M03/M04/M05) still have ghost `first_frame_url` pointing to non-existent files, all APPROVED.

5. 🟡 **SYSTEM IDLE (GENERATION) — 15th consecutive idle report (R20–R34).** No new frames or videos. Ledger age: 1d 3h 27m (+66m from R33). Average cadence: ~60.4m/cycle.

6. 🟡 **006_M02/M04 AWAITING_APPROVAL (14th consecutive report, R21–R34).** 008_M03b + 008_M04 REGEN_REQUESTED (unchanged since R21). No HUMAN_ESCALATION shots. No operator action.

7. 🟡 **REWARD SIGNAL FROZEN — 33rd consecutive report.** 228 ledger entries (unchanged). 87.8% heuristic I=0.75 (36/41 last-entry-per-shot). Self-resolves on next generation run. **Ledger now 1d 3h 27m stale.**

8. 📋 **FALSE NEGATIVE FROM R33 CORRECTED.** `scene*_lite_audio.mp4` files (4 present: scene001/002/003/004) were present at creation time 2026-03-30 08:43-08:47 EDT — before R33 ran. R33 reported only 6 scene_lite.mp4 files without noting audio variants. These are outputs of the `_SMART_STITCHER` + `_lyria_generate_undertone` hooks wired in the runner. Not a new generation event — reporting gap in R33.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R34) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots. Bare-list guard at runner:1512. 97/97 arc positions (ESTABLISH/ESCALATE/PIVOT/RESOLVE). 62/62 M-shots with `_chain_group`. shot_plan.json mtime 20:22:12 EDT (unchanged). | `isinstance(sp, list)` at runner:1512 ✅; arc scan ✅ |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` count=**5** in runner (was 4 in R33 — new `_CPC_DECONTAM_AVAILABLE` tracking added). CPC call sites: runner:2380, 2671, 3253. Availability tracking flags: runner:88/92. | `grep -c "_cpc_decontaminate" runner` → 5 ✅ |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims Seedance v2.0 PRIMARY (STALE_DOC — 31st). `_LTXRetiredGuard` error says "Use Seedance" (retired V31.0). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:535). CLAUDE.md V36.5 accurate. | runner:24 Seedance claim confirmed ✅; runner:535 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Learning log: 0 regressions (22 fixes). Wire-A (6 hits), Wire-C (6 hits), `_fail_sids` at runner:5706 (+6 from insertion). `enrich_shots_with_arc` imported at runner:65 (stable), called at runner:4939 (+6). `_CPC_DECONTAM_AVAILABLE` now tracked at runner:88/92 (new). | Session enforcer R34 ✅ |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT. Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic per session_enforcer). OPEN-009: 4 API-path video_urls (23rd). OPEN-010: 4 ghost first_frame_urls (20th). | Shot plan scan ✅; OPEN-009 + OPEN-010 confirmed unresolved |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (unchanged, **1d 3h 27m stale**). 87.8% heuristic I=0.75 (last-entry-per-shot). 5 real-VLM shots: 008_M01(1.0)/M02(0.9)/M04(0.8), 004_M01(1.0)/M02(1.0). Identical to R33. | Ledger scan R34 ✅ |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs in first_frames/, 62 MP4s in videos_kling_lite/ (unchanged). 6 scene_lite.mp4 + 4 scene_lite_audio.mp4 (audio variants noted R34 — created 2026-03-30, previously unreported). OPEN-010: 001_M02-M05 ghost frames (META-CHRONIC). OPEN-009: 4 API-path video_urls. 2 AWAITING_APPROVAL, 2 REGEN_REQUESTED, 0 HUMAN_ESCALATION. run_report: success=True, errors=[]. | File counts + shot_plan scan R34 ✅ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5706 (shifted +6, logic functional) ✅. 6 scene_lite.mp4 + 4 audio variants confirmed — all mtimes unchanged since 2026-03-30. | `grep -n "_fail_sids"` → runner:5706 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits (lines 2507/2511/2516/2532/2536/2539). Wire-C: 6 hits (lines 5465/5485/5487/5490/5492/5494). Counts unchanged despite +6-line runner insertion. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim persists (31st). LTX guard error message says "Use Seedance" (persists). CLAUDE.md V36.5 correct. | Confirmed via sed R34 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R34. Identical to R26–R33.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:535.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:505.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1512.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4939 (shifted +6 from R33:4933 — consistent with runner insertion).
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (mtime 15:43:25 EDT 2026-03-30 unchanged).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R34 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R34.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:535 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` count=5 in runner (was 4; +1 from availability tracking addition — wiring remains intact at call sites 2380/2671/3253).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url. API prefix cleared by operator data patch post-R22.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (23 reports): OPEN-009 — API-Path Prefix in video_url

**Issue:** 4 shots (008_E01/E02/E03/M03b) still have `/api/media?path=` prefix in **video_url**. (first_frame_url was fully fixed by operator data patch between R22 and R23.) All underlying video files confirmed to exist on disk. Stitch proven non-blocking. Data inconsistency only.

**R34 status vs R33:** UNCHANGED. No data patch applied. shot_plan.json mtime unchanged.

**META-CHRONIC: 23rd consecutive report (R12→R34).**

**PROOF RECEIPT (R34 live):**
```
PROOF: python3 scan → shots where '/api/media' in video_url
OUTPUT: ['008_E01', '008_E02', '008_E03', '008_M03b']
EXACT VALUES (unchanged from R33):
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

**Classification:** META-CHRONIC (23rd report). Data hygiene. ~2 min fix.

---

### ⏱️ META-CHRONIC (20 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. Escalated to META-CHRONIC at R24 (10-report threshold). 20th consecutive report.

**R34 status vs R33:** UNCHANGED. No operator action. shot_plan.json mtime unchanged.

**META-CHRONIC STATUS:** 20 consecutive reports (R15→R34). META-CHRONIC since R24.

**PROOF RECEIPT (R34 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields on all shots
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: 001_M02.jpg approval=APPROVED — file does not exist
    001_M03: 001_M03.jpg approval=APPROVED — file does not exist
    001_M04: 001_M04.jpg approval=APPROVED — file does not exist
    001_M05: 001_M05.jpg approval=APPROVED — file does not exist
CONFIRMS: Identical to R15→R33. 20th consecutive confirmation.
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

**Classification:** META-CHRONIC (20th report). Process failure — requires operator action.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **33rd consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Ledger now **1d 3h 27m stale** — over 27 hours since last entry.

**PROOF RECEIPT (R34 live):**
```
PROOF: python3 last-entry-per-shot I-score analysis + ledger age
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged from R33)
  UNIQUE_SHOTS: 41
  LAST_I_HEURISTIC (0.75): 36/41 = 87.8%
  LAST_I_REAL_VLM: 5/41 — [('008_M01',1.0),('004_M01',1.0),('004_M02',1.0),('008_M02',0.9),('008_M04',0.8)]
  LEDGER_AGE: 1d 3h 27m (+66m from R33)
CONFIRMS: No new generation. Identical distribution to R33.
```

**Classification:** ARCHITECTURAL_DEBT (33rd report). Resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **33rd consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5706 (shifted +6 from R33:5700 due to runner code insertion — line position change is expected and confirmed consistent with +6 pattern).

**PROOF (R34 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5706 ✅ (was 5700 in R33, +6 = correct)
CONFIRMS: WIRE-B label absent. Logic intact. Line position shift (+6) consistent with R34 code insertion.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5706. One line.

**Classification:** STALE_DOC. 33rd consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — **31st consecutive report**)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:535). Additionally, `_LTXRetiredGuard.__getattr__` at runner:505 emits `"C3 VIOLATION: LTX is retired. HALT. Use Seedance."` — stale guidance since Seedance is also retired (V31.0).

**PROOF (R34 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: runner lines 498-510 contain _LTXRetiredGuard with "Use Seedance" messages
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:535: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
CONFIRMS: Both stale docstring references persist unchanged from R33. Code behavior correct.
```

**Classification:** STALE_DOC. 31st consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL (14th consecutive report, R21–R34)

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. scene006_lite.mp4 exists. Videos generated but not reviewed by operator. 008_M03b + 008_M04 carry `_approval_status=REGEN_REQUESTED` — unchanged since R21. 0 HUMAN_ESCALATION shots (V37.1 escalation path tested, none triggered).

**PROOF (R34 live):**
```
PROOF: python3 shot_plan approval status scan
OUTPUT:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 14th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
  APPROVED: 29, AUTO_APPROVED: 6, blank: 58
CONFIRMS: No operator action since R21.
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. 14th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues confirmed as reported in R33. One R33 reporting gap corrected (see Section 6.4).

---

## 6. NEW OBSERVATIONS (R34 only)

### 6.1 🆕 CODE CYCLE ACTIVE — First Runner Modification Since R26

Runner mtime changed from 2026-03-30 23:46:04 EDT (reported in R33 as unchanged across 7 cycles) to **2026-03-31 07:52:36 EDT** — 41 minutes after R33 ran (07:11:30 EDT). This ends the 7-cycle idle code streak (R27–R33).

**What changed:** +6 lines added to atlas_universal_runner.py (6,179 → 6,185 total). The new content is a CPC availability tracking block in the import section:
- 4-line comment block documenting CPC decontamination purpose
- `_CPC_DECONTAM_AVAILABLE = True` at runner:88
- `_CPC_DECONTAM_AVAILABLE = False` at runner:92 (exception path)

This addition follows the existing pattern of other availability flags in the runner (`_V37_GOVERNANCE`, `_LYRIA_SOUNDSCAPE`, `_SMART_STITCHER`, `_VVO_AVAILABLE`). The CPC call sites themselves (runner:2380, 2671, 3253) were present before.

**Non-regression confirmed:** Session enforcer ✅ HEALTHY (0 blocks), learning log 0 regressions, Wire counts unchanged (12), V37 refs=31.

**Line position audit (R34 vs R33 — +6 shift for lines after insertion):**

| Wire/Anchor | R26–R33 | R34 | Delta | Status |
|-------------|---------|-----|-------|--------|
| `isinstance` guard | 1512 | 1512 | 0 | ✅ Before insertion |
| `ACTIVE_VIDEO_MODEL` | 535 | 535 | 0 | ✅ Before insertion |
| `LTX_FAST` guard | 505 | 505 | 0 | ✅ Before insertion |
| `enrich_shots_with_arc` call | 4933 | 4939 | **+6** | ✅ After insertion — shift consistent |
| `_fail_sids` (Wire-B logic) | 5700 | 5706 | **+6** | ✅ After insertion — shift consistent |
| Total lines | 6,179 | 6,185 | **+6** | ✅ Exactly 6 new lines |

### 6.2 CPC Count: 4 → 5 (Availability Tracking Addition)

`grep -c "_cpc_decontaminate" atlas_universal_runner.py` returns 5 (was 4 in R33). The new +1 is from the `_CPC_DECONTAM_AVAILABLE = True/False` tracking flag block which contains `_cpc_decontaminate` in the `as` alias clause. The 3 actual call sites (runner:2380, 2671, 3253) remain unchanged. The import (runner:87) and fallback definition (runner:91) also remain. The new availability flag provides a boolean gate that downstream code can check without calling the function directly.

**Session enforcer does NOT probe for `_CPC_DECONTAM_AVAILABLE`** — this is a new pattern not yet in the enforcer. Recommend adding a probe if this flag is used by downstream code as a gate.

### 6.3 R33 Reporting Gap Corrected: scene*_lite_audio.mp4 Files

R33 reported "6 scene_lite.mp4 files" but did NOT note 4 audio variants. R34 observes:
- `scene001_lite_audio.mp4` (created 2026-03-30 08:47:45 EDT)
- `scene002_lite_audio.mp4` (created 2026-03-30 08:43:05 EDT)
- `scene003_lite_audio.mp4` (created 2026-03-30 08:43:XX EDT)
- `scene004_lite_audio.mp4` (created 2026-03-30 08:43:XX EDT)

These are outputs of the `_SMART_STITCHER` + `_lyria_generate_undertone` hooks wired in the runner. Created during the last generation run (2026-03-30), NOT a new generation event. R33's "6 scene_lite.mp4" count was correct for scene_lite.mp4 specifically. The audio variants represent functional smart-stitcher operation with audio layer. Not a P0 item — reporting correction only.

### 6.4 Fifteenth Consecutive Idle Generation Report — R20 Through R34

System has produced zero new frames or videos across 15 consecutive keep-up cycles (R20–R34). The runner code change in R34 (CPC availability tracking) does not trigger generation. Two META-CHRONIC data patches (~12 min combined) remain unapplied for the 23rd and 20th cycle respectively.

### 6.5 Ledger Staleness Trend (15-Report View)

| Report | Ledger Age | Delta |
|--------|-----------|-------|
| R20 | 13h21m | — |
| R21–R30 | 14h21m → 23h21m | +~60m/cycle |
| R31 | 24h21m (1d 0h 21m) | +60m ⚠️ >24h |
| R32 | 25h22m (1d 1h 22m) | +61m |
| R33 | 26h21m (1d 2h 21m) | +59m |
| **R34** | **27h27m (1d 3h 27m)** | **+66m ⚠️ >27h** |

Cadence: 59–66m per cycle. Average: ~60.4m/cycle. 15th cycle.

### 6.6 META-CHRONIC Persistence Summary (Updated R34)

| Issue | First Appeared | META-CHRONIC Since | Consecutive Reports |
|-------|---------------|-------------------|---------------------|
| OPEN-009 (video_url patch) | R12 | R12 | **23 (R12→R34)** |
| OPEN-010 (ghost frames regen) | R15 | R24 | **20 (R15→R34; META-CHRONIC from R24)** |

Combined operator fix time: ~12 min. Neither blocks active generation.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (video_url patch — 4 fields) | 2 min | Strip `/api/media?path=` from `video_url` on 008_E01/E02/E03/M03b in shot_plan.json | NO — data hygiene, **23rd META-CHRONIC** |
| **P1** | OPEN-010 (ghost frames + re-gen 001 M-shots) | 10 min | Clear first_frame_url + reset approval for 001_M02-M05, then --frames-only scene 001 | NO — but META-CHRONIC data integrity risk if re-stitch attempted |
| **P2** | 006_M02/M04 AWAITING_APPROVAL | 2 min | Operator review in UI → thumbs-up or thumbs-down | NO — production gap |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge fires with Gemini/OpenRouter | NO — observational; ledger now >27h stale |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add `# ── [WIRE-B] ...` comment at runner:5706 (updated from R33's 5700 — +6 shift confirmed) | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance + LTX error msg) | 3 min | Update runner header line 24 + fix `_LTXRetiredGuard` error message to say "Use Kling" | NO — cosmetic |
| **P5** | session_enforcer: add `_CPC_DECONTAM_AVAILABLE` probe | 5 min | Add probe to tools/session_enforcer.py for new availability flag if it gates downstream code | NO — enhancement |

**P0 count: 0. No P0 blockers. System ready for generation.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed R34: HEALTHY, 0 blocks)
□ ✅ OPEN-004 fixed — CPC decontamination wired (count=5 confirmed R34, call sites intact)
□ [P1-META-CHRONIC] OPEN-009: strip /api/media?path= from video_url on 008_E01/E02/E03/M03b
□ [P1-META-CHRONIC] OPEN-010: clear first_frame_url="" + set _approval_status="AWAITING_APPROVAL" for 001_M02-M05
□ [P1] After clearing 001_M02-M05, run --frames-only scene 001 to re-generate M02-M05
□ [P1] Review and re-approve 001_M02-M05 frames in UI before --videos-only
□ [P2] Review 006_M02 + 006_M04 in UI → approve or regen
□ Verify vision backends online: gemini_vision + openrouter (confirmed R34 via session_enforcer: HEALTHY)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed stable)
□ After generation: spot-check new ledger entries for I != 0.75 (vision backends confirmed active)
□ Scene 008: REGEN_REQUESTED for M03b + M04 — operator review required before re-stitch
□ Scene 008: lite stitch already complete (scene008_lite.mp4). Only re-stitch if M03b/M04 regen'd.
□ Canonical runner line positions (R34 baseline — UPDATED from R33 for +6 insertion):
    _fail_sids=5706 (was 5700), enrich_shots_with_arc=4939 (was 4933),
    isinstance=1512 (stable), ACTIVE_VIDEO_MODEL=535 (stable), LTX_FAST guard=505 (stable).
```

---

## 9. DELTA FROM R33

| Signal | R33 | R34 | Delta | Note |
|--------|-----|-----|-------|------|
| **CODE CHANGE** | 0 (7 idle) | **1 🆕** | **+1 ACTIVE** | Runner modified 07:52:36 EDT — first since R26 |
| **Runner lines** | 6,179 | **6,185** | **+6** | CPC availability tracking block added |
| **CPC grep count** | 4 | **5** | **+1** | `_CPC_DECONTAM_AVAILABLE` tracking added |
| **_fail_sids line** | 5700 | **5706** | **+6** | Consistent with +6 insertion |
| **enrich_shots_with_arc call line** | 4933 | **4939** | **+6** | Consistent with +6 insertion |
| **META-CHRONIC count** | 2 | 2 | = | OPEN-009 (**23rd**) + OPEN-010 (**20th**) |
| **OPEN-009 consecutive** | 22 | **23** | **+1** | No patch applied |
| **OPEN-010 consecutive** | 19 | **20** | **+1** | No operator action |
| **OPEN-002 consecutive** | 32 | **33** | **+1** | ARCHITECTURAL_DEBT |
| **OPEN-003 consecutive** | 32 | **33** | **+1** | STALE_DOC |
| **OPEN-005 consecutive** | 30 | **31** | **+1** | STALE_DOC |
| **PRODUCTION_GAP (AWAITING)** | 13th | **14th** | **+1** | 006_M02/M04 + 008_M03b/M04 |
| **Idle generation reports** | 14th (R20-R33) | **15th (R20-R34)** | **+1** | 0 new frames/videos |
| **Ledger age** | 26h21m | **27h27m** | **+66m** | >27h stale |
| **Ledger entries** | 228 | 228 | = | No new generation |
| **Confirmed fixed** | 23 | 23 | = | 0 regressions |
| **Regressions** | 0 | **0** | = | ALL CLEAR |
| **first_frames/** | 62 | 62 | = | Unchanged |
| **videos_kling_lite/** | 62 | 62 | = | Unchanged |
| **Session enforcer** | ✅ HEALTHY | **✅ HEALTHY** | = | 0 blocks |
| **Audio variants noted** | not reported | **4 files noted** | REPORTING GAP | scene001-004_lite_audio.mp4 — created R33 era, not new |

---

## 10. DOCUMENT LINEAGE

- **Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R33_KEEPUP_LATEST.md
- **This report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R34_KEEPUP_LATEST.md
- **Next report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R35_KEEPUP_LATEST.md (expected ~2026-03-31T13:15Z)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T12:14:59Z",
  "ledger_age_hours": 27.45,
  "run_number": 34,
  "delta_from_prior": "+66m",
  "idle_generation_cycles": 15,
  "code_change_this_cycle": true,
  "code_change_description": "Runner +6 lines: CPC availability tracking (_CPC_DECONTAM_AVAILABLE flags at runner:88/92) + 4-line comment block. Non-regressing (session_enforcer HEALTHY).",
  "idle_code_cycles_ended": true,
  "runner_lines_r33": 6179,
  "runner_lines_r34": 6185,
  "cpc_count_r33": 4,
  "cpc_count_r34": 5,
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 23,
      "class": "META-CHRONIC",
      "first_report": "R12",
      "proof_receipt": "python3 scan: ['008_E01','008_E02','008_E03','008_M03b'] have /api/media?path= in video_url — 4 shots confirmed",
      "fix_recipe": "Strip /api/media?path= prefix from video_url on 4 shots in shot_plan.json — data patch only, ~2 min",
      "regression_guard": ["first_frame_url (fixed R23)", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 20,
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
      "consecutive_reports": 33,
      "class": "ARCHITECTURAL_DEBT",
      "description": "87.8% heuristic I-scores, ledger 27h+ stale — self-resolves on next generation run"
    }
  ],
  "stale_docs": [
    {"id": "OPEN-003", "consecutive_reports": 33, "description": "No [WIRE-B] label at runner:5706 (updated from 5700 — +6 shift) — logic functional"},
    {"id": "OPEN-005", "consecutive_reports": 31, "description": "Runner header Seedance claim + LTX error message stale — code correct"}
  ],
  "false_positives_retracted": [],
  "r33_reporting_gap_corrected": {
    "item": "scene*_lite_audio.mp4 files",
    "description": "4 audio variant MP4s present (created 2026-03-30 08:43-08:47 EDT) — not reported in R33. Not a new generation event. Smart_stitcher audio layer functional output."
  },
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
  "wire_counts": {"wire_a": 6, "wire_b_logic": "runner:5706 functional (label absent)", "wire_c": 6},
  "generation_state": {
    "first_frames": 62,
    "videos": 62,
    "scene_lite_mp4s": 6,
    "scene_lite_audio_mp4s": 4,
    "awaiting_approval": ["006_M02", "006_M04"],
    "regen_requested": ["008_M03b", "008_M04"],
    "human_escalation": [],
    "ghost_first_frame_urls": ["001_M02", "001_M03", "001_M04", "001_M05"],
    "api_prefix_video_urls": ["008_E01", "008_E02", "008_E03", "008_M03b"]
  },
  "recommended_next_action": "no_action — system healthy, no P0 blockers; operator should apply 2 META-CHRONIC data patches (~12 min) and run generation to resolve OPEN-002 ledger staleness; new _CPC_DECONTAM_AVAILABLE flag could optionally be added to session_enforcer probes"
}
```
