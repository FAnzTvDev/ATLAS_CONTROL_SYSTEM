# ATLAS ERROR DEEPDIVE — 2026-04-01 R45 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T00:11:00Z
**Run number:** R45
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R44_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (10th consecutive session R36–R45). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 15h 23m** (from 2026-03-30T08:47:31 UTC to 2026-04-01T00:11:00Z UTC).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (10th consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R44→R45):** ~60 min (2026-03-31T23:10:24Z → 2026-04-01T00:11:00Z)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC-ESCALATED 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R44: NO CODE CHANGES — session enforcer 64 PASS / 0 BLOCK maintained (7th consecutive code-stable session)**

| Category | Count | Delta vs R44 | Status |
|----------|-------|-------------|--------|
| **META-CHRONIC-ESCALATED** | 2 | = (both escalated R40) | OPEN-009 (**34th**) + OPEN-010 (**31st**) — 10th consecutive absent pipeline_outputs session |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **44th** report |
| STALE_DOC | 1 | = (OPEN-003) | **44th** report |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R45 |
| **CODE CHANGES SINCE R44** | **NONE** | = | Runner still 6,271 lines (mtime 2026-03-31 13:27 EDT — unchanged since R39). Orchestrator mtime 2026-03-31 13:20 EDT — unchanged. 7th consecutive code-stable session (R39–R45). |
| **DATA CHANGES SINCE R44** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R44** | **0 frames, 0 videos** | = | **System idle — 26th consecutive idle generation report (R20–R45)** |

**Key findings R45:**

1. 🟢 **SESSION ENFORCER: 64 PASS / 0 WARN / 0 BLOCK — ✅ SYSTEM HEALTHY.** Identical to R39–R44. All 64 checks passing. Learning log: 0 regressions (22 fixes ALL CLEAR). Vision backends available: gemini_vision + openrouter + florence_fal + heuristic.

2. 🔴🔴 **META-CHRONIC-ESCALATED: OPEN-009 (34th report) + OPEN-010 (31st report).** `pipeline_outputs/` absent **entirely** at the OS level — 10th consecutive session (R36–R45). Both issues remain UNVERIFIED_CARRY_FORWARD. Root blocker: workspace mount / operator must run generation to recreate directory.

3. 🟢 **NO CODE CHANGES R44→R45 — 7TH CONSECUTIVE CODE-STABLE SESSION.** Runner: 6,271 lines, mtime 2026-03-31 13:27 EDT (unchanged since R39). Orchestrator: mtime 2026-03-31 13:20 EDT (unchanged since R39). No new modules, no new wiring.

4. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 44th consecutive report.** Estimated ledger age: **~1d 15h 23m stale** (~60 min older than R44). Self-resolves on next generation run.

5. 🟡 **OPEN-003 STALE_DOC — 44th consecutive report.** `grep -c "WIRE-B" atlas_universal_runner.py → 0` confirmed live R45. `_fail_sids` logic at runner:5734 fully functional. Cosmetic only.

6. 🟢 **ALL CONFIRMED-FIXED ITEMS STABLE (24).** OPEN-005 fix (runner:24 "Kling v3/pro PRIMARY", LTX guard "Use Kling v3/pro") confirmed via live grep R45. VVO wiring: 4 import lines (runner:366-392) + call sites at 2610, 3346, 3491, 3827 — G3 level, G4 unproven (requires generation run). **NEW R45: VVO call site at runner:3827 (`_vvo_chain_check`) now confirmed in addition to prior 3 call sites.**

7. 🟢 **SYSTEM IDLE — 26th consecutive idle report (R20–R45).** Est. ~1d 15h 23m since last ledger entry. At ~60 min/cycle: R46 ≈ ~1d 16h 23m stale if no generation run occurs.

8. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent (no 4h proof-gate run found). Non-blocking.

9. ℹ️ **MILESTONE APPROACHING: OPEN-009 at 34 reports, OPEN-010 at 31 reports.** At R50, recommended reclassification as `PERMANENT_DATA_GAP` if workspace mount remains unresolved.

10. ℹ️ **run_lock.py enforcer probe still absent** — unchanged observation. Non-blocking.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R45 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1540 canonical (T2-OR-18), also at 1503, 3324, 3445 (defense-in-depth). | `grep -n "isinstance.*list"` → runner:1540 ✅ (live R45) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` 3 call sites at runner:2408, 2699, 3281. Import at runner:87, stub at runner:91. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R45) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | OPEN-005 FIXED (R39, confirmed R45). Runner:24 = "Kling v3/pro PRIMARY". LTX guard = "Use Kling v3/pro." `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5 accurate. | runner:24 ✅; runner:563 → `"kling"` ✅ (live R45) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (64/0/0). Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522) = 12 combined. Wire-B `_fail_sids` at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO 4 import lines + 4 active call sites (2610/3346/3491/3827). | Session enforcer R45 ✅ (live); wire counts = 12 ✅ (live R45) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (34th): 4 API-path video_urls — META-CHRONIC-ESCALATED. OPEN-010 (31st): 4 ghost first_frame_urls — META-CHRONIC-ESCALATED. | .env scan ✅ (live R45); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (10th session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. ~1d 15h 23m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). | Ledger: UNVERIFIED_CARRY_FORWARD (10th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (10th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R45). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R45) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R45 — same as R44). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R45) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic mismatch. Enforcer count 47 in CLAUDE.md vs live 64 — cosmetic. CLAUDE.md V36.5 content accurate. OPEN-003 = no [WIRE-B] label (functional). | OPEN-003 confirmed live R45 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R45. No changes from R44.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 3324, 3445).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R45 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R45.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R45.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url (code path confirmed closed).
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". LTX guard: "Use Kling v3/pro." Both corrected. Confirmed R45.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC-ESCALATED (34 reports): OPEN-009 — API-Path Prefix in video_url
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (10th consecutive session)

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R45 status vs R44:** UNVERIFIED_CARRY_FORWARD — 10th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. `pipeline_outputs/` directory is absent **entirely** at the OS level.

**META-CHRONIC-ESCALATED: 34th consecutive report (R12→R45).**

**PROOF RECEIPT (R45):**
```
PROOF: ls pipeline_outputs/ 2>/dev/null || echo "pipeline_outputs dir ABSENT entirely"
OUTPUT: pipeline_outputs dir ABSENT entirely
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. pipeline_outputs dir absent at OS level.
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

**Classification:** META-CHRONIC-ESCALATED (34th report). Data hygiene. ~2 min fix. UNVERIFIED_CARRY_FORWARD (10th session). **Root blocker: pipeline_outputs absent from workspace.**

**⚠️ MILESTONE NOTE:** At R50, recommend reclassifying as `PERMANENT_DATA_GAP` if workspace mount remains unresolved.

---

### ⏱️ META-CHRONIC-ESCALATED (31 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (10th consecutive session)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 31st consecutive report.

**R45 status vs R44:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. 10th consecutive session without `pipeline_outputs/`.

**META-CHRONIC-ESCALATED: 31 consecutive reports (R15→R45).**

**PROOF RECEIPT (R45):**
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

**Classification:** META-CHRONIC-ESCALATED (31st report). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD (10th session). **Root blocker: pipeline_outputs absent from workspace.**

**⚠️ MILESTONE NOTE:** At R50, recommend reclassifying as `PERMANENT_DATA_GAP` if workspace mount remains unresolved.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **44th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 15h 23m stale** (cannot verify directly — 10th consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R45 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "... reward_ledger.jsonl ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-04-01T00:11:00 UTC = ~1d 15h 23m (~39.39h total)
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (44th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **44th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734.

**PROOF (R45 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py → runner:5734 ✅ (logic intact, live R45)
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R45.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.

**Classification:** STALE_DOC. 44th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. Unchanged since R21. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 10th session).

**PROOF (R45 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (10th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 25th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R45)

### 6.1 NO CODE CHANGES R44→R45 — 7TH CONSECUTIVE CODE-STABLE SESSION (R39–R45)

Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — **identical to R39/R40/R41/R42/R43/R44**. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical to R39 through R44. No new modules added. No new endpoints. No new wiring. All R44 observations carry forward without change.

### 6.2 PIPELINE_OUTPUTS ABSENT — 10TH CONSECUTIVE SESSION (R36–R45)

Root cause analysis (unchanged): `pipeline_outputs/` is absent at the OS level in the mounted workspace. Consistent with the workspace folder being a separate mount that may not persist between Cowork sessions. The directory would be recreated automatically on the first generation run. No code fix needed — operator workspace access is the blocker.

**Impact assessment:**
- OPEN-009 + OPEN-010: Cannot verify or fix (data patch requires file access)
- OPEN-002: Ledger staleness grows ~1h per cycle
- VVO G4 proof: Cannot obtain without a generation run
- Session enforcer: Fully operational (code-only checks)
- System health: Code is sound; data layer is inaccessible

### 6.3 TWENTY-SIXTH CONSECUTIVE IDLE GENERATION — R20 THROUGH R45

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R44 | ~1d 14h 22m | 25th |
| **R45** | **~1d 15h 23m** | **26th** |

At ~60 min/cycle: R46 ≈ ~1d 16h 23m stale if no generation occurs.

### 6.4 VVO MODULE — G3 WIRED, G4 UNPROVEN (UNCHANGED FROM R39–R44) + NEW: 4TH CALL SITE CONFIRMED

`tools/video_vision_oversight.py` wired at runner:366-392 (4 import lines) with active call sites confirmed live R45:
- `_vvo_preflight_e_shot` at runner:2610 (E-shot pre-check in gen_frame_async)
- `_vvo_preflight_e_shot` at runner:3346 (preflight check, context: `_pf_result`)
- `_vvo_run` at runner:3491 (main video oversight call)
- `_vvo_chain_check` at runner:3827 (chain transition check — **newly confirmed R45**)

**NEW R45:** `_vvo_chain_check` call at runner:3827 directly confirmed via live grep (`_chain_result = _vvo_chain_check(_prev_vid, chain_local, _next_shot_for_vvo)`). This is the 4th active call site, all previously in the confirmed list but runner:3827 not individually specified. Now recorded.

Session enforcer confirms VVO importable + `_vvo_run` wired. G4 proof requires a live generation run. No change from R44 in terms of overall G3/G4 status.

### 6.5 WIRE LABEL POSITIONS (LIVE R45 — FOR REFERENCE)

| Wire | Label Count | Positions | Logic |
|------|------------|-----------|-------|
| WIRE-A | 6 | 2535, 2539, 2544, 2560, 2564, 2567 | Identity regen loop — confirmed functional |
| WIRE-B | 0 | runner:5734 `_fail_sids` (no label) | Stitch filter — functional, label absent (OPEN-003) |
| WIRE-C | 6 | 5493, 5513, 5515, 5518, 5520, 5522 | Frozen video regen — confirmed functional |

### 6.6 ESCALATION TRAJECTORY — OPEN-009 / OPEN-010

Both issues approaching structural milestone:
- OPEN-009 at **34 reports** — R50 deadline: 16 cycles away (~16 hours at 60 min/cycle)
- OPEN-010 at **31 reports** — R50 deadline: 19 cycles away
- Root blocker for both: `pipeline_outputs/` workspace mount not persisting between Cowork sessions.
- **Single action resolves both**: operator runs `python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only` in an active session with workspace mounted.
- **If pipeline_outputs appear before R50**: retract UNVERIFIED_CARRY_FORWARD, apply live verification immediately.

### 6.7 SYSTEM DATE CROSSED MIDNIGHT — APRIL 1, 2026

Report timestamps now in April. Report file named `2026-04-01_R45`. Lineage unbroken; issue ages accurate.

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC items:

| Priority | Issue | Class | Est. Time | Fix Type |
|----------|-------|-------|-----------|----------|
| P1 | OPEN-009: 4 video_url API-path prefix (34th report) | META-CHRONIC-ESCALATED | ~2 min | Data patch (shot_plan.json, 4 fields) — requires workspace access |
| P2 | OPEN-010: 4 ghost first_frame_url + regen 001_M02-M05 (31st report) | META-CHRONIC-ESCALATED | ~15 min | Data patch + `--frames-only` run — requires workspace access |
| P3 | OPEN-003: Add `[WIRE-B]` comment at runner:5734 | STALE_DOC | <1 min | 1-line code comment |

**NOT listed (correct omissions):**
- OPEN-002 (ARCHITECTURAL_DEBT — no quick fix, self-resolves on next gen)
- VVO G4 proof (PRODUCTION_GAP — needs generation run, not a bug)
- run_lock enforcer probe (OBSERVATION — non-blocking)
- Ledger staleness (PRODUCTION_GAP — self-resolves on generation)

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ Runner ACTIVE_VIDEO_MODEL = "kling" (runner:563) — confirmed R45
□ LTX_FAST = _LTXRetiredGuard() (runner:533) — confirmed R45
□ OPEN-005 fix intact — runner:24 "Kling v3/pro PRIMARY" — confirmed R45
□ LTX guard says "Use Kling v3/pro" (runner:528/532) — confirmed R45
□ Wire-A present (6 hits: 2535/2539/2544/2560/2564/2567) — confirmed R45
□ Wire-C present (6 hits: 5493/5513/5515/5518/5520/5522) — confirmed R45
□ Wire-B _fail_sids at runner:5734 — confirmed R45
□ isinstance guard at runner:1540 (also 1503, 3324) — confirmed R45
□ _cpc_decontaminate at runner:2408/2699/3281 — confirmed R45
□ enrich_shots_with_arc at runner:65 + runner:4967 — confirmed R45
□ All 5 env keys in .env — confirmed R45
□ Learning log 0 regressions — confirmed R45
□ Session enforcer 64 PASS / 0 BLOCK — confirmed R45
□ V37 endpoints (7) in orchestrator — confirmed R45
□ VVO import block at runner:366-392 + 4 call sites (2610/3346/3491/3827) — confirmed R45
□ ACTIVE_VIDEO_MODEL="kling" at runner:563 — confirmed R45
□ _fail_sids/_blocked_sids/_frozen_sids all present at runner:5734-5742 — confirmed R45
□ V37 runner hooks: 31 _V37|v37 refs — confirmed R45
```

---

## 9. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R44_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-04-01_R45_KEEPUP_LATEST.md`
**Lineage:** R35 (baseline, live data) → R36 (first absent) → R37 → R38 → R39 (OPEN-005 CLOSED; VVO wired) → R40 (META-CHRONIC-ESCALATED threshold triggered) → R41 → R42 → R43 → R44 (9th consecutive absent session; code-stable 6th consecutive) → **R45 (10th consecutive absent session; code-stable 7th consecutive; date crossed to April 1)**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T00:11:00Z",
  "ledger_age_hours": 39.39,
  "ledger_age_string": "~1d 15h 23m",
  "ledger_status": "UNVERIFIED_CARRY_FORWARD_10TH_SESSION",
  "cycle_interval_minutes": 60,
  "runner_lines": 6271,
  "runner_mtime": "2026-03-31T13:27:21-04:00",
  "runner_mtime_changed_since_r44": false,
  "orchestrator_mtime": "2026-03-31T13:20:31-04:00",
  "orchestrator_mtime_changed_since_r44": false,
  "code_changed_since_prior": false,
  "code_stable_consecutive_sessions": 7,
  "session_enforcer": {
    "pass": 64,
    "warn": 0,
    "block": 0,
    "status": "SYSTEM_HEALTHY"
  },
  "learning_log_regressions": 0,
  "pipeline_outputs_present": false,
  "pipeline_outputs_consecutive_absent_sessions": 10,
  "pipeline_outputs_note": "Absent entirely at OS level — 10th consecutive session (R36-R45). Workspace mount required.",
  "generation_idle_reports": 26,
  "meta_chronic_escalated": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 34,
      "class": "META-CHRONIC-ESCALATED",
      "description": "4 shots with /api/media?path= prefix in video_url",
      "proof_receipt": "pipeline_outputs dir ABSENT entirely — UNVERIFIED_CARRY_FORWARD_10TH_SESSION",
      "fix_recipe": "Data patch: replace('/api/media?path=','') on video_url for 008_E01/E02/E03/M03b",
      "fix_time_estimate": "~2 min",
      "blocker": "pipeline_outputs workspace not mounted",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"],
      "milestone_note": "At R50 (~16 cycles), recommend reclassifying as permanent-data-gap if workspace mount not resolved."
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 31,
      "class": "META-CHRONIC-ESCALATED",
      "description": "4 shots (001_M02-M05) with ghost first_frame_url pointing to non-existent files",
      "proof_receipt": "pipeline_outputs dir ABSENT entirely — UNVERIFIED_CARRY_FORWARD_10TH_SESSION",
      "fix_recipe": "Clear first_frame_url + set AWAITING_APPROVAL on 001_M02-M05 then run --frames-only",
      "fix_time_estimate": "~15 min (includes regen)",
      "blocker": "pipeline_outputs workspace not mounted",
      "regression_guard": ["001_M01 (confirmed on disk R35)", "scene001_lite.mp4 (confirmed R35)"],
      "milestone_note": "At R50 (~19 cycles), recommend reclassifying as permanent-data-gap if workspace unresolved."
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "consecutive_reports": 44,
      "class": "ARCHITECTURAL_DEBT",
      "description": "87.8% heuristic I-scores in reward ledger — self-resolves on next gen run",
      "ledger_age_estimate_hours": 39.39
    }
  ],
  "stale_doc": [
    {
      "id": "OPEN-003",
      "consecutive_reports": 44,
      "class": "STALE_DOC",
      "description": "No [WIRE-B] label at runner:5734 — logic functional, cosmetic only",
      "fix_recipe": "Add '# ── [WIRE-B] Quality gate stitch filter' comment at runner:5734"
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_count": 24,
  "new_observations": [
    "VVO 4th call site confirmed: _vvo_chain_check at runner:3827",
    "Date crossed midnight into April 1, 2026 — report lineage unbroken",
    "OPEN-009 R50 milestone: ~16 cycles away",
    "OPEN-010 R50 milestone: ~19 cycles away"
  ],
  "vvo_status": "G3_WIRED_G4_UNPROVEN",
  "vvo_call_sites": [2610, 3346, 3491, 3827],
  "wire_positions": {
    "WIRE_A_hits": 6,
    "WIRE_A_lines": [2535, 2539, 2544, 2560, 2564, 2567],
    "WIRE_B_label": false,
    "WIRE_B_logic_line": 5734,
    "WIRE_C_hits": 6,
    "WIRE_C_lines": [5493, 5513, 5515, 5518, 5520, 5522]
  },
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
  "escalation_note": "OPEN-009/OPEN-010 now 34/31 consecutive reports at META-CHRONIC-ESCALATED. Both data issues + ledger staleness + VVO G4 proof all resolve with a single generation run. Root blocker: workspace mount not persisting between sessions. 10th consecutive session absent. Code is fully healthy (64 PASS enforcer) — only data layer is inaccessible. Milestone review at R50 to reclassify both as permanent-data-gap if workspace unresolved (~16 cycles / ~16 hours from R45)."
}
```
