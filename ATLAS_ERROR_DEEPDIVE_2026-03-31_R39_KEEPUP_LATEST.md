# ATLAS ERROR DEEPDIVE — 2026-03-31 R39 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T18:12:55Z
**Run number:** R39
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R38_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (4th consecutive session R36–R39). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 9h 25m** (from 2026-03-30T08:47:31 UTC to 2026-03-31T18:12:55Z UTC).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` ABSENT 4th consecutive session. OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R38: ✅ OPEN-005 CONFIRMED FIXED + NEW WIRING OBSERVED (VVO module, 53 runner lines added)**

| Category | Count | Delta vs R38 | Status |
|----------|-------|-------------|--------|
| **OPEN-005 CLOSED** | 1 | **NEW FIX** | Runner line 24 + LTX guard msg — both corrected. 35 reports → CLOSED. |
| **NEW CODE ACTIVITY** | Runner +53 lines | **CODE CHANGED** | Runner 6,218→6,271 lines. Orchestrator: new mtime. VVO wiring added. Opener override endpoint added. |
| **META-CHRONIC total** | 2 | = | OPEN-009 (**28th**) + OPEN-010 (**25th**) — UNVERIFIED_CARRY_FORWARD (4th session) |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **38th** report |
| STALE_DOC | 1 | **-1 (OPEN-005 CLOSED)** | OPEN-003 only (**38th**) |
| **CONFIRMED_FIXED** | **24** | **+1** | OPEN-005 added — 0 regressions |
| **CODE CHANGES SINCE R38** | **YES** | **NEW** | Runner +53 lines (mtime 08:32→13:27 EDT). Orchestrator +new endpoints (mtime 15:43→13:20 EDT, same date). |
| **DATA CHANGES SINCE R38** | 0 | = | pipeline_outputs absent — no verification possible. |
| **GENERATION SINCE R38** | **0 frames, 0 videos** | = | **System idle — 20th consecutive idle generation report (R20–R39)** |

**Key findings R39:**

1. ✅ **OPEN-005 CONFIRMED FIXED — 35th report CLOSED (LIVE R39).** Runner line 24 now reads `"Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0"` (was `"Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"`). LTX guard `__getattr__` now says `"Use Kling v3/pro."` (was `"Use Seedance"`). Both OPEN-005 components are fixed. Confirmed via live grep R39.

2. 🆕 **CODE CHANGED BETWEEN R38 AND R39.** Runner grew from 6,218 → 6,271 lines (+53). Orchestrator mtime advanced from 2026-03-30T15:43 to 2026-03-31T13:20. This is the first code activity since the R35 freeze (2026-03-31 08:32:39).

3. 🆕 **VVO MODULE WIRED — Video Vision Oversight (NON-BLOCKING).** `tools/video_vision_oversight.py` (84,731 bytes, mtime 2026-03-30 09:43) imported in runner at lines 366–392. 5 actual call sites wired: `_vvo_preflight_e_shot` (2 sites), `_vvo_run` (1 site), `_vvo_chain_check` (1 site), `_vvo_scene_stitch_check` (1 site). Session enforcer confirms: `video_vision_oversight.run_video_oversight() importable` and `_vvo_run called in runner — VVO fires after video generation`. VVO is WIRED (G3 level), not yet PROVEN (G4 needs generation run). Gemini-2.5-pro tier confirmed in module.

4. 🆕 **OPENER VALIDATOR WIRING.** Orchestrator has 3 new `api/v36/opener-analysis` endpoints: `/classify`, `/override`, `GET` base. `tools/opener_validator.py` (16,300 bytes, mtime 2026-03-28) referenced from orchestrator. `tools/scene_transition_manager.py` (20,784 bytes, mtime 2026-03-30) referenced from runner (~line 4812). These are non-blocking imports.

5. 🟢 **SESSION ENFORCER: 64 PASS / 0 WARN / 0 BLOCK — ✅ SYSTEM HEALTHY.** Identical result to R38. All 64 checks passing. Learning log: 0 regressions (22 fixes ALL CLEAR).

6. 🔴 **OPEN-009 META-CHRONIC: 28th consecutive report (R12→R39) — UNVERIFIED_CARRY_FORWARD.** 4th consecutive session without pipeline_outputs. No mechanism for self-resolution.

7. 🔴 **OPEN-010 META-CHRONIC: 25th consecutive report (R15→R39) — UNVERIFIED_CARRY_FORWARD.** Same cause. Data patch + regen required.

8. 🟡 **SYSTEM IDLE (GENERATION) — 20th consecutive idle report (R20–R39).** No new frames or videos. Estimated ledger age ~1d 9h 25m.

9. ℹ️ **run_lock.py still not probed by session_enforcer** — unchanged observation from R38. Non-blocking.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R39 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1540 canonical (T2-OR-18), also at 1503, 4540, 5212 (defense-in-depth). | `grep -n "isinstance.*list"` → runner:1540 ✅ (live R39) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` 3 call sites at runner:2408, 2699, 3281. Import at runner:87, stub at runner:91. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R39) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | **UPGRADE FROM 🟡 R38.** OPEN-005 FIXED — runner line 24 now says Kling PRIMARY. LTX guard says "Use Kling v3/pro". `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5 accurate. Enforcer count 47 in CLAUDE.md vs live 64 (cosmetic — unchanged). | runner:24 FIXED ✅; runner:563 → `"kling"` ✅ (live R39) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (64/0/0). Learning log: 0 regressions (22 fixes). Wire-A (12 combined A+C), Wire-B _fail_sids runner:5734, `enrich_shots_with_arc` runner:65/4967. VVO newly wired (5 call sites). | Session enforcer R39 ✅ (live) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009: 4 API-path video_urls (UNVERIFIED_CARRY_FORWARD 4th session). OPEN-010: 4 ghost first_frame_urls (UNVERIFIED_CARRY_FORWARD 4th session). | .env scan ✅ (live R39); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward from R35 — pipeline_outputs absent). Est. ~1d 9h 25m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (carry-forward R35). | Ledger: UNVERIFIED_CARRY_FORWARD (4th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD from R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. | File counts: UNVERIFIED_CARRY_FORWARD (4th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live). `_blocked_sids` / `_fail_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R39) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R39) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic mismatch. Enforcer count 47 in CLAUDE.md vs live 64 — cosmetic. CLAUDE.md V36.5 content accurate. OPEN-005 FIXED removes one 🟡 signal. | OPEN-005 confirmed fixed via live grep R39 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R39. OPEN-005 added this session.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 4540, 5212).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R39 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R39.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R39.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url (code path confirmed closed).
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". LTX guard: "Use Kling v3/pro." Both corrected. **35 consecutive reports → CLOSED.**

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (28 reports): OPEN-009 — API-Path Prefix in video_url
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (4th consecutive session without pipeline_outputs)

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R39 status vs R38:** UNVERIFIED_CARRY_FORWARD — 4th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. No code mechanism for self-resolution. Last live confirmation: R35 (2026-03-31T13:11Z).

**META-CHRONIC: 28th consecutive report (R12→R39).**

**PROOF RECEIPT (R39):**
```
PROOF: ls pipeline_outputs/victorian_shadows_ep1/ 2>/dev/null || echo "pipeline_outputs ABSENT"
OUTPUT: pipeline_outputs ABSENT (4th consecutive session)
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35; no code or data mechanism to self-heal.
LIKELIHOOD STILL OPEN: ~99% (data patches require operator action, zero generation runs occurred)
```

**Remaining fix (data patch only — no code changes):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   video_url = video_url.replace("/api/media?path=", "")
# Total: 4 field changes, ~2 min
# Verify: grep "/api/media" pipeline_outputs/victorian_shadows_ep1/shot_plan.json | wc -l → 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url`, `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` → 64 PASS / 0 BLOCK.

**Classification:** META-CHRONIC (28th report). Data hygiene. ~2 min fix. UNVERIFIED_CARRY_FORWARD (4th session).

---

### ⏱️ META-CHRONIC (25 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (4th consecutive session without pipeline_outputs)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 25th consecutive report.

**R39 status vs R38:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. 4th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. Last live confirmation: R35.

**META-CHRONIC STATUS:** 25 consecutive reports (R15→R39).

**PROOF RECEIPT (R39):**
```
PROOF: ls pipeline_outputs/victorian_shadows_ep1/ 2>/dev/null || echo "pipeline_outputs ABSENT"
OUTPUT: pipeline_outputs ABSENT (4th consecutive session)
STATUS: UNVERIFIED_CARRY_FORWARD — last live check was R35
CONFIRMS: Cannot live-verify. 001_M01.jpg is the only confirmed existing frame (R35).
LIKELIHOOD STILL OPEN: ~99% (requires operator regen run, zero runs occurred)
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists on disk. scene001_lite.mp4 confirmed present (R35). UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk (R35). scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05. `python3 tools/session_enforcer.py` → 64 PASS after patch.

**Classification:** META-CHRONIC (25th report). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD (4th session).

---

### OPEN-002 (ARCHITECTURAL_DEBT — **38th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 9h 25m stale** (cannot verify directly — 4th consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R39 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: Estimated time delta from last confirmed ledger entry (2026-03-30T08:47:31 UTC) to now (2026-03-31T18:12:55Z)
DELTA: 1 day + 9h + 25m + 24s = ~1d 9h 25m
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (38th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **38th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734.

**PROOF (R39 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py → runner:5734 ✅ (logic intact, live R39)
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R39.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.

**Classification:** STALE_DOC. 38th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. Unchanged since R21. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 4th session).

**PROOF (R39 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent (4th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 19th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. OPEN-005 was a genuine STALE_DOC that has now been FIXED and moved to CONFIRMED_FIXED.

---

## 6. NEW OBSERVATIONS (R39)

### 6.1 OPEN-005 CLOSED — STALE DOCSTRING FIXED (35-REPORT CLOSURE)

**What changed (live R39 grep):**
- **Line 24 (was):** `"P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"`
- **Line 24 (now):** `"P2. Videos: ALL shots parallel → Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0"`
- **LTX guard `__getattr__` (was):** `raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Seedance.")`
- **LTX guard `__getattr__` (now):** `raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Kling v3/pro.")`

Both components of OPEN-005 corrected in a single code edit. Confirmed live R39.

### 6.2 VVO MODULE — WIRED (G3), NOT YET PROVEN (G4)

`video_vision_oversight.py` (84,731 bytes) was already present since R36 (mtime 2026-03-30 09:43), but its wiring into the runner is now confirmed via runner lines 362–398. Five active call sites:
- `_vvo_preflight_e_shot(best, shot, _gfa_sb)` — runner:2610 (E-shot pre-gen frame check)
- `_vvo_preflight_e_shot(_pf_fp, _pf_s, _vvo_sb)` — runner:3346 (parallel frame gen path)
- `_vvo_run(outpath, _vvo_shot, _vvo_sb)` — runner:3491 (post-video oversight)
- `_vvo_chain_check(_prev_vid, chain_local, _next_shot_for_vvo)` — runner:3827 (chain transition)
- `_vvo_scene_stitch_check(outpath, _sc_shots_all)` — runner:5861 (scene stitch check)

Session enforcer confirms VVO importable + `_vvo_run` wired. Per 4-gate protocol: VVO is at G3 (wired). G4 (proven via live generation) requires a production run.

### 6.3 OPENER VALIDATOR / SCENE TRANSITION MANAGER — NEW ENDPOINTS

Three new orchestrator endpoints added under `/api/v36/opener-analysis/{project}`:
- `GET /api/v36/opener-analysis/{project}` — retrieve manifest
- `POST /api/v36/opener-analysis/{project}/classify` — classify opening type
- `POST /api/v36/opener-analysis/{project}/override` — override opener_type

These use `tools/opener_validator.py` and `tools/scene_transition_manager.py`. Both files importable. This system handles scene opening type classification (COLD_OPEN, SOFT_OPEN, etc.) and allows operator override. Non-blocking. Session enforcer does not probe these yet.

### 6.4 DATA VERIFIABILITY GAP — 4TH CONSECUTIVE SESSION (ESCALATION THRESHOLD)

R37 policy stated: "if absent R38, reclassify as UNVERIFIED_CARRY_FORWARD." R38 applied that. This is now the 4th consecutive session (R36–R39). Per R39: recommend escalating OPEN-009 and OPEN-010 to **META-CHRONIC-ESCALATED** status if pipeline_outputs is absent again at R40. The data patches are simple (~2 min and ~15 min) — the barrier is purely operator access to the workspace.

### 6.5 TWENTIETH CONSECUTIVE IDLE GENERATION — R20 THROUGH R39

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R38 | ~1d 8h 22m | 19th |
| R39 | ~1d 9h 25m | **20th** |

At ~62min/cycle: **R40 ≈ ~1d 10h 27m stale** (if no generation run occurs).

### 6.6 LINE NUMBER SHIFTS — ALL CONFIRMED

R38 cited specific runner line numbers. All shifted by +17 due to the VVO import block (lines 362–398 = 26 new lines added; net shift ~17 at downstream reference points). Updated positions:
- `ACTIVE_VIDEO_MODEL`: 546 → 563
- `LTX_FAST`: 516 → 533
- `isinstance` T2-OR-18: 1523 → 1540
- `_fail_sids` Wire-B: 5717 → 5734
- `enrich_shots_with_arc` call: 4950 → 4967

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC items:

| Priority | Issue | Class | Est. Time | Fix Type |
|----------|-------|-------|-----------|----------|
| P1 | OPEN-009: 4 video_url API-path prefix (28th report) | META-CHRONIC | ~2 min | Data patch (shot_plan.json, 4 fields) |
| P2 | OPEN-010: 4 ghost first_frame_url + regen 001_M02-M05 (25th report) | META-CHRONIC | ~15 min | Data patch + `--frames-only` run |
| P3 | OPEN-003: Add `[WIRE-B]` comment at runner:5734 | STALE_DOC | <1 min | 1-line code comment |

**NOT listed (correct omissions):**
- OPEN-002 (ARCHITECTURAL_DEBT — no quick fix, self-resolves on next gen)
- VVO G4 proof (PRODUCTION_GAP — needs generation run, not a bug)
- run_lock enforcer probe (OBSERVATION — non-blocking)
- Ledger staleness (PRODUCTION_GAP — self-resolves on generation)
- Opener validator enforcer probe (OBSERVATION — new module, non-blocking)

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL = "kling" — runner:563 ✅ (live R39)
□ LTX_FAST = _LTXRetiredGuard() — runner:533 ✅ (live R39)
□ LTX guard message = "Use Kling v3/pro." — runner:528/532 ✅ FIXED (was "Use Seedance")
□ Runner line 24 = Kling PRIMARY — runner:24 ✅ FIXED (was Seedance PRIMARY)
□ isinstance guard (T2-OR-18) — runner:1540 (also 1503, 4540, 5212) ✅ (live R39)
□ enrich_shots_with_arc imported — runner:65 ✅ (live R39)
□ enrich_shots_with_arc called — runner:4967 ✅ (live R39)
□ Wire-A+C hits — 12 ✅ (live R39)
□ Wire-B _fail_sids — runner:5734 ✅ (live R39)
□ CPC decontaminate — 3 call sites (2408/2699/3281) ✅ (live R39)
□ Session enforcer → 64 PASS / 0 WARN / 0 BLOCK ✅ (live R39)
□ Learning log → 0 regressions (22 fixes) ✅ (live R39)
□ All 5 env keys PRESENT ✅ (live R39)
□ VVO wired — 5 call sites (2610/3346/3491/3827/5861) ✅ G3 confirmed (live R39)
□ VVO importable — ✅ (live R39)
□ V37 governance refs — 31 in runner ✅ (live R39)
□ /api/v37 endpoints — 7 in orchestrator ✅ (live R39)
□ run_lock.py exists (2883 bytes) ✅ (live R39, not yet probed by enforcer) ℹ️
□ session_enforcer.py mtime 2026-03-29 22:38:42 EDT (unchanged) ℹ️
□ orchestrator_server.py mtime 2026-03-31 13:20:31 EDT (NEW — updated this cycle) ⚠️
□ pipeline_outputs/victorian_shadows_ep1/ — ABSENT 4th consecutive session ⚠️ (UNVERIFIED_CARRY_FORWARD)
□ OPEN-009/OPEN-010 — UNVERIFIED_CARRY_FORWARD (4th session — escalation if R40 absent) ⚠️
```
*(ℹ️ = informational observation; ⚠️ = data gap, policy flag, or new file — see Section 6)*

---

## 9. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R38_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R39_KEEPUP_LATEST.md`
**Run number delta:** R38 → R39 (+1)
**Open issues carried forward:** OPEN-002 (38th), OPEN-003 (38th), OPEN-009 (28th — UNVERIFIED_CARRY_FORWARD), OPEN-010 (25th — UNVERIFIED_CARRY_FORWARD), PRODUCTION_GAP (19th — UNVERIFIED_CARRY_FORWARD)
**Issues CLOSED this session:** OPEN-005 (35 reports → CONFIRMED_FIXED) ✅
**New issues added:** 0
**False positives retracted:** 0
**New wiring confirmed:** VVO (G3), Opener Validator (G1/G2)
**Consecutive idle generation cycles:** 20 (R20–R39)
**Consecutive sessions without pipeline_outputs access:** 4 (R36–R39) — ESCALATION THRESHOLD at R40

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T18:12:55Z",
  "session_id": "busy-vigilant-edison",
  "ledger_age_hours_estimate": 33.42,
  "ledger_verified_live": false,
  "pipeline_outputs_accessible": false,
  "consecutive_sessions_without_pipeline_outputs": 4,
  "unverified_carry_forward_applied": ["OPEN-009", "OPEN-010", "PRODUCTION_GAP", "ledger_data", "file_counts"],
  "runner_lines": 6271,
  "runner_mtime": "2026-03-31T13:27:21-04:00",
  "runner_lines_delta_from_r38": 53,
  "orchestrator_lines": 51161,
  "orchestrator_mtime": "2026-03-31T13:20:31-04:00",
  "session_enforcer_mtime": "2026-03-29T22:38:42-04:00",
  "run_lock_py_bytes": 2883,
  "code_changes_this_cycle": true,
  "consecutive_cycles_no_code_change": 0,
  "session_enforcer_result": "SYSTEM_HEALTHY",
  "session_enforcer_pass": 64,
  "session_enforcer_warn": 0,
  "session_enforcer_block": 0,
  "learning_log_regressions": 0,
  "learning_log_fixes": 22,
  "wire_counts": {
    "wire_a_c_combined": 12,
    "wire_b_location": 5734
  },
  "isinstance_guard_locations": [1503, 1540, 4540, 5212],
  "cpc_call_sites": [2408, 2699, 3281],
  "v37_governance_refs_in_runner": 31,
  "v37_api_endpoints_in_orchestrator": 7,
  "vvo_call_sites": [2610, 3346, 3491, 3827, 5861],
  "vvo_wiring_level": "G3",
  "new_endpoints": ["/api/v36/opener-analysis/{project}", "/api/v36/opener-analysis/{project}/classify", "/api/v36/opener-analysis/{project}/override"],
  "issues_closed_this_session": ["OPEN-005"],
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 28,
      "class": "META-CHRONIC",
      "verification_status": "UNVERIFIED_CARRY_FORWARD",
      "last_live_confirmation": "R35 (2026-03-31T13:11Z)",
      "proof_receipt": "pipeline_outputs absent 4th consecutive session. Self-heal probability: ~0%.",
      "fix_recipe": "video_url.replace('/api/media?path=', '') on 4 shots in shot_plan.json — ~2 min data patch",
      "regression_guard": ["first_frame_url untouched", "session_enforcer 64 PASS after patch"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 25,
      "class": "META-CHRONIC",
      "verification_status": "UNVERIFIED_CARRY_FORWARD",
      "last_live_confirmation": "R35 (2026-03-31T13:11Z)",
      "proof_receipt": "pipeline_outputs absent 4th consecutive session. 001_M02/M03/M04/M05 ghost first_frame_urls.",
      "fix_recipe": "Set first_frame_url='' + _approval_status=AWAITING_APPROVAL on 4 shots, run --frames-only for scene 001",
      "regression_guard": ["001_M01.jpg preserved", "scene001_lite.mp4 preserved"]
    }
  ],
  "false_positives_retracted": [],
  "organ_health": {
    "skeleton": "HEALTHY",
    "liver": "HEALTHY",
    "immune": "HEALTHY",
    "nervous": "HEALTHY",
    "eyes": "SICK",
    "cortex": "DEGRADED",
    "cinematographer": "DEGRADED",
    "editor": "HEALTHY",
    "regenerator": "HEALTHY",
    "doctrine_doc": "DEGRADED"
  },
  "new_module_probe_gap": {
    "modules": ["tools/run_lock.py", "tools/opener_validator.py", "tools/scene_transition_manager.py"],
    "in_runner": true,
    "in_session_enforcer": false,
    "impact": "LOW — non-blocking; enforcer HEALTHY without them"
  },
  "data_verifiability_note": "pipeline_outputs absent R36/R37/R38/R39 (4th consecutive). OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD. If R40 also absent, escalate to META-CHRONIC-ESCALATED.",
  "recommended_next_action": "apply_data_patch_OPEN009_OPEN010",
  "recommended_secondary_action": "run_generation_victorian_shadows_001",
  "generation_idle_cycles": 20,
  "data_gap_cycles": 4,
  "escalation_threshold_met": true,
  "escalation_note": "4th consecutive data gap session. R40 absence should trigger META-CHRONIC-ESCALATED reclassification for OPEN-009 + OPEN-010."
}
```
