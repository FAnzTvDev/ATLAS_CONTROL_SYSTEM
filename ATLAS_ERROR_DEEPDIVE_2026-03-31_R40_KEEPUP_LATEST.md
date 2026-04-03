# ATLAS ERROR DEEPDIVE — 2026-03-31 R40 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T19:10:35Z
**Run number:** R40
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R39_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (5th consecutive session R36–R40). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 10h 23m** (from 2026-03-30T08:47:31 UTC to 2026-03-31T19:10:35Z UTC).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (5th consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. R39 threshold policy triggered: escalating to META-CHRONIC-ESCALATED. All code checks fully live this session.

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC-ESCALATED 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R39: NO CODE CHANGES — session enforcer 64 PASS / 0 BLOCK maintained**

| Category | Count | Delta vs R39 | Status |
|----------|-------|-------------|--------|
| **META-CHRONIC-ESCALATED** | 2 | **ESCALATED from META-CHRONIC** | OPEN-009 (**29th**) + OPEN-010 (**26th**) — 5th consecutive absent pipeline_outputs session — R39 escalation threshold TRIGGERED |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **39th** report |
| STALE_DOC | 1 | = (OPEN-003) | **39th** report |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R40 |
| **CODE CHANGES SINCE R39** | **NONE** | = | Runner still 6,271 lines (mtime 13:27 EDT — R39 session). Orchestrator mtime 13:20 EDT — unchanged. |
| **DATA CHANGES SINCE R39** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R39** | **0 frames, 0 videos** | = | **System idle — 21st consecutive idle generation report (R20–R40)** |

**Key findings R40:**

1. 🟢 **SESSION ENFORCER: 64 PASS / 0 WARN / 0 BLOCK — ✅ SYSTEM HEALTHY.** Identical to R39. All 64 checks passing. Learning log: 0 regressions (22 fixes ALL CLEAR).

2. 🔴🔴 **META-CHRONIC-ESCALATED: OPEN-009 (29th report) + OPEN-010 (26th report).** R39 stated: "recommend escalating to META-CHRONIC-ESCALATED if pipeline_outputs absent again at R40." That threshold is now triggered. `pipeline_outputs/` is absent **entirely** at the OS level — not just the subdirectory. This is a workspace mounting issue. Operator must either: (a) remount the workspace folder, or (b) run generation which would re-create the directory.

3. 🟢 **NO CODE CHANGES R39→R40.** Runner: 6,271 lines, mtime 2026-03-31 13:27 EDT (same as R39 snapshot). Orchestrator: mtime 2026-03-31 13:20 EDT (same as R39). No new modules, no new wiring. System is code-stable.

4. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 39th consecutive report.** Estimated ledger age: **~1d 10h 23m stale**. ~58 min older than R39. Self-resolves on next generation run.

5. 🟡 **OPEN-003 STALE_DOC — 39th consecutive report.** No `[WIRE-B]` label at runner:5734. `_fail_sids` logic fully functional (live confirmed R40). Cosmetic only.

6. 🟢 **ALL CONFIRMED-FIXED ITEMS STABLE.** OPEN-005 fix (runner:24 "Kling v3/pro PRIMARY", LTX guard "Use Kling v3/pro") confirmed via live grep R40. VVO wiring: 4 import lines at runner:367-380, 5 call sites — G3 level, G4 unproven.

7. 🟢 **SYSTEM IDLE — 21st consecutive idle report (R20–R40).** Est. ~1d 10h 23m since last ledger entry. At ~58-62 min/cycle: R41 ≈ ~1d 11h 21m stale if no generation run occurs.

8. ℹ️ **run_lock.py enforcer probe still absent** — unchanged observation. Non-blocking.

9. ℹ️ **Opener validator / scene_transition_manager** — observed R39, unchanged. Non-blocking. Session enforcer does not probe these yet.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R40 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1540 canonical (T2-OR-18), also at 1503, 3324, 4540 (defense-in-depth). | `grep -n "isinstance.*list"` → runner:1540 ✅ (live R40) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` 3 call sites at runner:2408, 2699, 3281. Import at runner:87, stub at runner:91. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R40) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | OPEN-005 FIXED (R39, confirmed R40). Runner:24 = "Kling v3/pro PRIMARY". LTX guard = "Use Kling v3/pro". `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5 accurate. | runner:24 ✅; runner:563 → `"kling"` ✅ (live R40) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (64/0/0). Wire-A (6 hits), Wire-C (6 hits) = 12 combined. Wire-B _fail_sids at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO 4 import lines + 5 call sites. | Session enforcer R40 ✅ (live); wire counts ✅ (live R40) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (29th): 4 API-path video_urls — META-CHRONIC-ESCALATED. OPEN-010 (26th): 4 ghost first_frame_urls — META-CHRONIC-ESCALATED. | .env scan ✅ (live R40); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (5th session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. ~1d 10h 23m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). | Ledger: UNVERIFIED_CARRY_FORWARD (5th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. Pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (5th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R40). `_blocked_sids` / `_fail_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R40) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R40 — same as R39). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R40) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic mismatch. Enforcer count 47 in CLAUDE.md vs live 64 — cosmetic. CLAUDE.md V36.5 content accurate. OPEN-003 = no [WIRE-B] label (functional). | OPEN-003 confirmed live R40 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R40. No changes from R39.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 3324, 4540).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R40 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R40.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R40.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url (code path confirmed closed).
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". LTX guard: "Use Kling v3/pro." Both corrected. Confirmed R40.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC-ESCALATED (29 reports): OPEN-009 — API-Path Prefix in video_url
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (5th consecutive session — R39 escalation threshold TRIGGERED)

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R40 status vs R39:** UNVERIFIED_CARRY_FORWARD — 5th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. `pipeline_outputs/` directory is absent **entirely** at the OS level. R39 escalation threshold triggered.

**META-CHRONIC-ESCALATED: 29th consecutive report (R12→R40).**

**PROOF RECEIPT (R40):**
```
PROOF: ls pipeline_outputs/ 2>/dev/null || echo "pipeline_outputs dir ABSENT entirely"
OUTPUT: pipeline_outputs dir ABSENT entirely
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. Pipeline_outputs dir absent at OS level — workspace mounting issue.
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

**Classification:** META-CHRONIC-ESCALATED (29th report). Data hygiene. ~2 min fix. UNVERIFIED_CARRY_FORWARD (5th session). **Root blocker: pipeline_outputs absent from workspace.**

---

### ⏱️ META-CHRONIC-ESCALATED (26 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (5th consecutive session — R39 escalation threshold TRIGGERED)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 26th consecutive report.

**R40 status vs R39:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. 5th consecutive session without `pipeline_outputs/`. R39 escalation threshold triggered.

**META-CHRONIC-ESCALATED: 26 consecutive reports (R15→R40).**

**PROOF RECEIPT (R40):**
```
PROOF: ls pipeline_outputs/ 2>/dev/null || echo "pipeline_outputs dir ABSENT entirely"
OUTPUT: pipeline_outputs dir ABSENT entirely
STATUS: UNVERIFIED_CARRY_FORWARD — last live check was R35
CONFIRMS: Cannot live-verify. 001_M01.jpg was the only confirmed existing frame (R35).
LIKELIHOOD STILL OPEN: ~99% (requires operator regen run, zero runs occurred)
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg existed on disk (R35). scene001_lite.mp4 confirmed present (R35). UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk (R35). scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05. `python3 tools/session_enforcer.py` → 64 PASS after patch.

**Classification:** META-CHRONIC-ESCALATED (26th report). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD (5th session). **Root blocker: pipeline_outputs absent from workspace.**

---

### OPEN-002 (ARCHITECTURAL_DEBT — **39th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 10h 23m stale** (cannot verify directly — 5th consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R40 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "import json,datetime; ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-03-31T19:10:35 UTC = ~1d 10h 23m
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (39th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **39th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734.

**PROOF (R40 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py → runner:5734 ✅ (logic intact, live R40)
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R40.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.

**Classification:** STALE_DOC. 39th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. Unchanged since R21. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 5th session).

**PROOF (R40 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (5th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 20th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R40)

### 6.1 NO CODE CHANGES R39→R40 — SYSTEM CODE-STABLE

Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — **identical to R39 snapshot**. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical to R39. No new modules added. No new endpoints. No new wiring. All R39 observations carry forward without change.

### 6.2 META-CHRONIC-ESCALATED THRESHOLD TRIGGERED FOR OPEN-009 + OPEN-010

R39 stated: *"recommend escalating OPEN-009 and OPEN-010 to META-CHRONIC-ESCALATED status if pipeline_outputs is absent again at R40."* The threshold is now triggered. Both issues are upgraded from META-CHRONIC → **META-CHRONIC-ESCALATED**.

Root cause: `pipeline_outputs/` is absent at the OS level in the mounted workspace — not just the subdirectory. This is consistent with the workspace folder being a separate mount that may not persist between Cowork sessions. The fix requires operator action: either explicitly regenerate (`--frames-only` for a scene) which recreates the directory, or verify the workspace folder is correctly selected/mounted.

### 6.3 TWENTY-FIRST CONSECUTIVE IDLE GENERATION — R20 THROUGH R40

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R39 | ~1d 9h 25m | 20th |
| **R40** | **~1d 10h 23m** | **21st** |

At ~58-62 min/cycle: R41 ≈ ~1d 11h 21m stale if no generation occurs.

### 6.4 VVO MODULE — G3 WIRED, G4 UNPROVEN (UNCHANGED FROM R39)

`tools/video_vision_oversight.py` (84,731 bytes, mtime 2026-03-30 09:43) wired at runner:367-380 (4 import lines) with 5 active call sites: `_vvo_preflight_e_shot` (2 sites), `_vvo_run` (1 site), `_vvo_chain_check` (1 site), `_vvo_scene_stitch_check` (1 site). Session enforcer confirms VVO importable + `_vvo_run` wired. G4 proof requires a live generation run.

### 6.5 WORKSPACE MOUNT DIAGNOSTIC NOTE

The `pipeline_outputs/` directory is absent **entirely** — not just the victorian_shadows_ep1 subdirectory. This is consistent with the workspace folder not being accessible in this Cowork session. The directory would be recreated automatically on the first generation run (`atlas_universal_runner.py` creates it). No code fix is needed — operator access to workspace is the blocker.

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC items:

| Priority | Issue | Class | Est. Time | Fix Type |
|----------|-------|-------|-----------|----------|
| P1 | OPEN-009: 4 video_url API-path prefix (29th report) | META-CHRONIC-ESCALATED | ~2 min | Data patch (shot_plan.json, 4 fields) — requires workspace access |
| P2 | OPEN-010: 4 ghost first_frame_url + regen 001_M02-M05 (26th report) | META-CHRONIC-ESCALATED | ~15 min | Data patch + `--frames-only` run — requires workspace access |
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
□ Runner ACTIVE_VIDEO_MODEL = "kling" (runner:563) — confirmed R40
□ LTX_FAST = _LTXRetiredGuard() (runner:533) — confirmed R40
□ OPEN-005 fix intact — runner:24 "Kling v3/pro PRIMARY" — confirmed R40
□ LTX guard says "Use Kling v3/pro" (runner:532) — confirmed R40
□ Wire-A present (6 hits) — confirmed R40
□ Wire-C present (6 hits) — confirmed R40
□ Wire-B _fail_sids at runner:5734 — confirmed R40
□ isinstance guard at runner:1540 — confirmed R40
□ _cpc_decontaminate at runner:2408/2699/3281 — confirmed R40
□ enrich_shots_with_arc at runner:65 + runner:4967 — confirmed R40
□ All 5 env keys in .env — confirmed R40
□ Learning log 0 regressions — confirmed R40
□ Session enforcer 64 PASS / 0 BLOCK — confirmed R40
□ V37 endpoints (7) in orchestrator — confirmed R40
□ VVO import block at runner:367-380 — confirmed R40
```

---

## 9. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R39_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R40_KEEPUP_LATEST.md`
**Lineage:** R35 (baseline, live data) → R36 (first absent) → R37 → R38 → R39 (OPEN-005 CLOSED; VVO wired) → R40 (META-CHRONIC-ESCALATED threshold triggered; no code changes)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T19:10:35Z",
  "ledger_age_hours": 34.38,
  "ledger_age_string": "~1d 10h 23m",
  "ledger_status": "UNVERIFIED_CARRY_FORWARD_5TH_SESSION",
  "runner_lines": 6271,
  "runner_mtime": "2026-03-31T13:27:21-04:00",
  "orchestrator_mtime": "2026-03-31T13:20:31-04:00",
  "code_changed_since_prior": false,
  "session_enforcer": {
    "pass": 64,
    "warn": 0,
    "block": 0,
    "status": "SYSTEM_HEALTHY"
  },
  "learning_log_regressions": 0,
  "pipeline_outputs_present": false,
  "pipeline_outputs_note": "Absent entirely at OS level (not just subdirectory) — 5th consecutive session",
  "generation_idle_reports": 21,
  "meta_chronic_escalated": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 29,
      "class": "META-CHRONIC-ESCALATED",
      "description": "4 shots with /api/media?path= prefix in video_url",
      "proof_receipt": "pipeline_outputs dir ABSENT entirely — UNVERIFIED_CARRY_FORWARD_5TH_SESSION",
      "fix_recipe": "Data patch: replace('/api/media?path=','') on video_url for 008_E01/E02/E03/M03b",
      "fix_time_estimate": "~2 min",
      "blocker": "pipeline_outputs workspace not mounted",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 26,
      "class": "META-CHRONIC-ESCALATED",
      "description": "4 shots (001_M02-M05) with ghost first_frame_url pointing to non-existent files",
      "proof_receipt": "pipeline_outputs dir ABSENT entirely — UNVERIFIED_CARRY_FORWARD_5TH_SESSION",
      "fix_recipe": "Clear first_frame_url + set AWAITING_APPROVAL on 001_M02-M05 then run --frames-only",
      "fix_time_estimate": "~15 min (includes regen)",
      "blocker": "pipeline_outputs workspace not mounted",
      "regression_guard": ["001_M01 (confirmed on disk R35)", "scene001_lite.mp4 (confirmed R35)"]
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "consecutive_reports": 39,
      "class": "ARCHITECTURAL_DEBT",
      "description": "87.8% heuristic I-scores in reward ledger — self-resolves on next gen run",
      "ledger_age_estimate_hours": 34.38
    }
  ],
  "stale_doc": [
    {
      "id": "OPEN-003",
      "consecutive_reports": 39,
      "class": "STALE_DOC",
      "description": "No [WIRE-B] label at runner:5734 — logic functional, cosmetic only",
      "fix_recipe": "Add '# ── [WIRE-B] Quality gate stitch filter' comment at runner:5734"
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_count": 24,
  "vvo_status": "G3_WIRED_G4_UNPROVEN",
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
  "recommended_next_action": "operator_must_mount_workspace_or_run_generation",
  "escalation_note": "R39 threshold triggered: OPEN-009/OPEN-010 upgraded to META-CHRONIC-ESCALATED. Root blocker is workspace mount, not code. Single generation run would resolve both data issues and ledger staleness."
}
```
