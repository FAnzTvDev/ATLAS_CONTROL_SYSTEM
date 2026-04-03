# ATLAS ERROR DEEPDIVE — 2026-04-01 R48 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T03:22:05Z
**Run number:** R48
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R47_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (13th consecutive session R36–R48). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 18h 34m** (~42.58h total from 2026-03-30T08:47:31 UTC to 2026-04-01T03:22:05Z UTC).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (13th consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R47→R48):** ~1h 10m (2026-04-01T02:11:18Z → 2026-04-01T03:22:05Z)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC-ESCALATED 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R47: NO CODE CHANGES — session enforcer 64 PASS / 0 BLOCK maintained (10th consecutive code-stable session)**

| Category | Count | Delta vs R47 | Status |
|----------|-------|-------------|--------|
| **META-CHRONIC-ESCALATED** | 2 | = (both escalated R40) | OPEN-009 (**37th**) + OPEN-010 (**34th**) — 13th consecutive absent pipeline_outputs session |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **47th** report |
| STALE_DOC | 1 | = (OPEN-003) | **47th** report |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R48 |
| **CODE CHANGES SINCE R47** | **NONE** | = | Runner still 6,271 lines (mtime 2026-03-31 13:27:21 EDT — unchanged since R39). Orchestrator mtime 2026-03-31 13:20:31 EDT — unchanged. 10th consecutive code-stable session (R39–R48). |
| **DATA CHANGES SINCE R47** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R47** | **0 frames, 0 videos** | = | **System idle — 29th consecutive idle generation report (R20–R48)** |

**Key findings R48:**

1. 🟢 **SESSION ENFORCER: 64 PASS / 0 WARN / 0 BLOCK — ✅ SYSTEM HEALTHY.** Identical to R39–R47. All 64 checks passing (counted via indented line output). Learning log: 0 regressions (22 fixes ALL CLEAR).

2. 🔴🔴 **META-CHRONIC-ESCALATED: OPEN-009 (37th report) + OPEN-010 (34th report).** `pipeline_outputs/` absent **entirely** at the OS level — 13th consecutive session (R36–R48). Both issues remain UNVERIFIED_CARRY_FORWARD. Root blocker: workspace mount / operator must run generation to recreate directory.

3. 🟢 **NO CODE CHANGES R47→R48 — 10TH CONSECUTIVE CODE-STABLE SESSION.** Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT (confirmed live R48 via `stat`). Orchestrator: mtime 2026-03-31 13:20:31 EDT. No new modules, no new wiring. `find . -name "*.py" -newer R47_report.md` returned NOTHING (confirmed live R48).

4. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 47th consecutive report.** Estimated ledger age: **~1d 18h 34m stale** (~42.58h total). Self-resolves on next generation run.

5. 🟡 **OPEN-003 STALE_DOC — 47th consecutive report.** `grep -c "WIRE-B" atlas_universal_runner.py → 0` confirmed live R48. `_fail_sids` logic at runner:5734 fully functional. Cosmetic only. Runner header still reads V31.0 vs V36.5 CLAUDE.md.

6. 🟢 **ALL CONFIRMED-FIXED ITEMS STABLE (24).** OPEN-005 fix (runner:24 "Kling v3/pro PRIMARY") confirmed live R48. Wire positions all confirmed: Wire-A×6 (2535/2539/2544/2560/2564/2567), Wire-C×6 (5493/5513/5515/5518/5520/5522), Wire-B `_fail_sids` at runner:5734. VVO 4 active call sites (2610/3346/3491/3827) confirmed live R48. V37: 31 lines containing `_V37`/`v37` refs in runner (grep -cE), 7 `/api/v37` endpoints in orchestrator.

7. 🟢 **SYSTEM IDLE — 29th consecutive idle report (R20–R48).** Est. ~1d 18h 34m since last ledger entry. At ~60–70 min/cycle: R49 ≈ ~1d 19h 34m–44m stale if no generation run occurs.

8. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent (no 4h proof-gate run found). Non-blocking.

9. ℹ️ **MILESTONE NOTE: OPEN-009 at 37 reports (13 cycles to R50), OPEN-010 at 34 reports (16 cycles to R50).** At R50, recommend reclassifying both as `PERMANENT_DATA_GAP` if workspace mount remains unresolved.

10. ℹ️ **All 5 env keys PRESENT** (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) — confirmed live R48.

11. ℹ️ **V37 ref count stable at 31 lines** (`grep -cE "_V37|v37"` — ERE baseline established R47, confirmed R48). 7 `/api/v37` endpoints in orchestrator confirmed unchanged.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R48 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1540 canonical (T2-OR-18), also at 1503, 3324, 3445 (defense-in-depth). | `grep -n "isinstance.*list"` → runner:1503/1540/3324/3325/3445/3490 ✅ (live R48) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` import at runner:87, stub at runner:91, 3 call sites at runner:2408, 2699, 3281. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R48) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | OPEN-005 FIXED (R39, confirmed R48). Runner:24 = "Kling v3/pro PRIMARY". LTX guard at runner:533. `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5 accurate. | runner:24/533/563 ✅ (live R48) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (64/0/0). Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522) = 12 combined. Wire-B `_fail_sids` at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO 4 active call sites (2610/3346/3491/3827). V37: 7 endpoints in orchestrator. | Session enforcer R48 ✅ (live); wire counts = 12 ✅ (live R48) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (37th): 4 API-path video_urls — META-CHRONIC-ESCALATED. OPEN-010 (34th): 4 ghost first_frame_urls — META-CHRONIC-ESCALATED. | .env scan ✅ (live R48); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (13th session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. ~1d 18h 34m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). | Ledger: UNVERIFIED_CARRY_FORWARD (13th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (13th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R48). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R48) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R48 — same as R44/R45/R46/R47). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R48) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic mismatch. Enforcer count 47 in CLAUDE.md vs live 64 — cosmetic. CLAUDE.md V36.5 content accurate. OPEN-003 = no [WIRE-B] label (functional). | OPEN-003 confirmed live R48 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R48. No changes from R47.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 3324, 3325, 3445, 3490).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 lines containing `_V37`/`v37` in runner (live R48 ERE baseline); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R48 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R48.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R48.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url (code path confirmed closed).
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". LTX guard: "Use Kling v3/pro." Both corrected. Confirmed R48.

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC-ESCALATED (37 reports): OPEN-009 — API-Path Prefix in video_url
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (13th consecutive session)

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R48 status vs R47:** UNVERIFIED_CARRY_FORWARD — 13th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. `pipeline_outputs/` directory is absent **entirely** at the OS level.

**META-CHRONIC-ESCALATED: 37th consecutive report (R12→R48).**

**PROOF RECEIPT (R48):**
```
PROOF: if [ -d pipeline_outputs ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: pipeline_outputs ABSENT
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

**Classification:** META-CHRONIC-ESCALATED (37th report). Data hygiene. ~2 min fix. UNVERIFIED_CARRY_FORWARD (13th session). **Root blocker: pipeline_outputs absent from workspace.**

**⚠️ MILESTONE NOTE:** At R50 (**13 cycles / ~13 hours away**), recommend reclassifying as `PERMANENT_DATA_GAP` if workspace mount remains unresolved.

---

### ⏱️ META-CHRONIC-ESCALATED (34 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚠️ STATUS: UNVERIFIED_CARRY_FORWARD (13th consecutive session)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 34th consecutive report.

**R48 status vs R47:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. 13th consecutive session without `pipeline_outputs/`.

**META-CHRONIC-ESCALATED: 34 consecutive reports (R15→R48).**

**PROOF RECEIPT (R48):**
```
PROOF: if [ -d pipeline_outputs ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: pipeline_outputs ABSENT
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

**Classification:** META-CHRONIC-ESCALATED (34th report). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD (13th session). **Root blocker: pipeline_outputs absent from workspace.**

**⚠️ MILESTONE NOTE:** At R50 (**16 cycles / ~16 hours away**), recommend reclassifying as `PERMANENT_DATA_GAP` if workspace unresolved.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **47th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 18h 34m stale** (~42.58h total — cannot verify directly, 13th consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R48 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "... reward_ledger.jsonl ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-04-01T03:22:05 UTC = ~1d 18h 34m (~42.58h total)
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (47th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **47th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734. Runner header also shows V31.0 (vs V36.5 in CLAUDE.md) — cosmetic mismatch.

**PROOF (R48 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py → runner:5734 ✅ (logic intact, live R48)
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R48.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.

**Classification:** STALE_DOC. 47th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. Unchanged since R21. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 13th session).

**PROOF (R48 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (13th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 28th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R48)

### 6.1 NO CODE CHANGES R47→R48 — 10TH CONSECUTIVE CODE-STABLE SESSION (R39–R48)

Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — **identical to R39/R40/R41/R42/R43/R44/R45/R46/R47**. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical through all 10 sessions. `find . -name "*.py" -newer R47_report.md` returned NOTHING (confirmed live R48). Cycle interval from R47: +1h 10m (2026-04-01T02:11:18Z → 2026-04-01T03:22:05Z). No new modules added. No new endpoints. No new wiring.

### 6.2 PIPELINE_OUTPUTS ABSENT — 13TH CONSECUTIVE SESSION (R36–R48)

Root cause analysis (unchanged): `pipeline_outputs/` is absent at the OS level in the mounted workspace. Consistent with the workspace folder being a separate mount that may not persist between Cowork sessions. The directory would be recreated automatically on the first generation run.

**Impact assessment:**
- OPEN-009 + OPEN-010: Cannot verify or fix (data patch requires file access)
- OPEN-002: Ledger staleness grows ~1h per cycle (~42.58h total)
- VVO G4 proof: Cannot obtain without a generation run
- Session enforcer: Fully operational (code-only checks — 64 PASS confirmed)
- System health: Code is fully sound; data layer is inaccessible

### 6.3 TWENTY-NINTH CONSECUTIVE IDLE GENERATION — R20 THROUGH R48

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R47 | ~1d 17h 23m | 28th |
| **R48** | **~1d 18h 34m (~42.58h total)** | **29th** |

At ~60–70 min/cycle: R49 ≈ ~1d 19h 34m–44m stale if no generation occurs.

### 6.4 VVO MODULE — G3 WIRED, G4 UNPROVEN (UNCHANGED R39–R48)

`tools/video_vision_oversight.py` wired at runner:366-392 (import block) with active call sites confirmed live R48:
- `_vvo_preflight_e_shot` at runner:2610 (E-shot pre-check in gen_frame_async)
- `_vvo_preflight_e_shot` at runner:3346 (preflight check, context: `_pf_result`)
- `_vvo_run` at runner:3491 (main video oversight call)
- `_vvo_chain_check` at runner:3827 (chain transition check — confirmed R47, re-confirmed R48)

Session enforcer confirms VVO importable + `_vvo_run` wired. G4 proof requires a live generation run.

### 6.5 WIRE LABEL POSITIONS (LIVE R48 — CONFIRMED)

| Wire | Label Count | Positions | Logic |
|------|------------|-----------|-------|
| WIRE-A | 6 | 2535/2539/2544/2560/2564/2567 | Back-to-camera skip, budget exhausted, auto-regen, fix success, no-improve, regen-failed |
| WIRE-B | 0 labels | N/A (OPEN-003) | `_fail_sids` functional at runner:5734 |
| WIRE-C | 6 | 5493/5513/5515/5518/5520/5522 | Frozen attempt, success, still-frozen, call-failed, no-start-frame, exception |

### 6.6 MILESTONE COUNTDOWN — R50 RECLASSIFICATION WINDOW

| Issue | Current Count | Milestone | Cycles Remaining |
|-------|--------------|-----------|-----------------|
| OPEN-009 | 37th report | R50 → PERMANENT_DATA_GAP | **13 cycles (~13h)** |
| OPEN-010 | 34th report | R50 → PERMANENT_DATA_GAP | **16 cycles (~16h)** |

If workspace mount remains unresolved at R50, both issues should be reclassified as `PERMANENT_DATA_GAP` — indicating they cannot be resolved without operator intervention that has not occurred in 50+ reporting cycles (~50+ hours).

### 6.7 V37 REF COUNT — STABLE AT 31 (ERE BASELINE)

`grep -cE "_V37|v37" atlas_universal_runner.py → 31` (live R48). Matches R47 ERE baseline. Runner provably unchanged (mtime 2026-03-31 13:27:21 EDT; `find -newer` returned nothing). 7 `/api/v37` endpoints in orchestrator confirmed unchanged. No regression.

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC issues appear here:

| Priority | Issue | Class | Consecutive Reports | Fix Effort | Blocker |
|----------|-------|-------|---------------------|------------|---------|
| P1 | OPEN-009: API-path prefix in video_url | META-CHRONIC-ESCALATED | 37 | ~2 min data patch | pipeline_outputs absent |
| P2 | OPEN-010: Ghost first_frame_url 001_M02-M05 | META-CHRONIC-ESCALATED | 34 | Regen 4 shots | pipeline_outputs absent |

**Operator action required for both P1 and P2.** Root blocker: the `pipeline_outputs/victorian_shadows_ep1/` directory is absent from the workspace mount. When operator next runs a generation session:
1. `pipeline_outputs/` will be recreated by the runner
2. P1 fix (4-field data patch) can be applied immediately
3. P2 fix (regen 001_M02-M05) should follow in `--frames-only` mode

OPEN-002 and OPEN-003 are ARCHITECTURAL_DEBT and STALE_DOC respectively — not code bugs, not on priority fix list.

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ Session enforcer: 64 PASS / 0 BLOCK ✅ (live R48)
□ Learning log: 0 regressions (22 fixes ALL CLEAR) ✅ (live R48)
□ ACTIVE_VIDEO_MODEL = "kling" at runner:563 ✅ (live R48)
□ LTX_FAST = _LTXRetiredGuard() at runner:533 ✅ (live R48)
□ Wire-A: 6 hits (2535/2539/2544/2560/2564/2567) ✅ (live R48)
□ Wire-B: _fail_sids at runner:5734 ✅ (live R48)
□ Wire-C: 6 hits (5493/5513/5515/5518/5520/5522) ✅ (live R48)
□ enrich_shots_with_arc at runner:65 + 4967 ✅ (live R48)
□ _cpc_decontaminate at runner:87/91/2408/2699/3281 ✅ (live R48)
□ isinstance guard at runner:1503/1540/3324/3325/3445/3490 ✅ (live R48)
□ VVO active call sites: 2610/3346/3491/3827 ✅ (live R48)
□ V37 endpoints: 7 in orchestrator ✅ (live R48)
□ All 5 env keys PRESENT (.env) ✅ (live R48)
□ Vision backends: gemini_vision + openrouter + florence_fal + heuristic ✅ (enforcer R48)
□ Runner line count: 6,271 (unchanged from R39) ✅ (live R48)
□ Orchestrator mtime: 2026-03-31 13:20:31 EDT (unchanged from R40) ✅ (live R48)
```

---

## 9. DOCUMENT LINEAGE

- **Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R47_KEEPUP_LATEST.md
- **This report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R48_KEEPUP_LATEST.md
- **Cycle:** ~1h 10m (R47→R48)
- **Next expected:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R49_KEEPUP_LATEST.md (~2026-04-01T04:22Z)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T03:22:05Z",
  "run_number": "R48",
  "ledger_age_hours": 42.58,
  "ledger_status": "UNVERIFIED_CARRY_FORWARD",
  "pipeline_outputs_present": false,
  "consecutive_absent_sessions": 13,
  "code_changes_since_prior": 0,
  "consecutive_code_stable_sessions": 10,
  "enforcer_result": {"pass": 64, "warn": 0, "block": 0, "status": "SYSTEM_HEALTHY"},
  "vision_backends": ["gemini_vision", "openrouter", "florence_fal", "heuristic"],
  "learning_log_regressions": 0,
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 37,
      "class": "META-CHRONIC-ESCALATED",
      "proof_receipt": "if [ -d pipeline_outputs ]; then echo EXISTS; else echo ABSENT; fi → ABSENT (13th consecutive session)",
      "fix_recipe": "4-field data patch on video_url for 008_E01/E02/E03/M03b — requires pipeline_outputs present",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"],
      "blocker": "pipeline_outputs absent from workspace mount",
      "milestone_at_report": 50,
      "cycles_to_milestone": 13
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 34,
      "class": "META-CHRONIC-ESCALATED",
      "proof_receipt": "if [ -d pipeline_outputs ]; then echo EXISTS; else echo ABSENT; fi → ABSENT (13th consecutive session)",
      "fix_recipe": "Reset first_frame_url + _approval_status on 001_M02-M05, run --frames-only",
      "regression_guard": ["001_M01.jpg", "scene001_lite.mp4"],
      "blocker": "pipeline_outputs absent from workspace mount",
      "milestone_at_report": 50,
      "cycles_to_milestone": 16
    }
  ],
  "architectural_debt": [
    {"id": "OPEN-002", "consecutive_reports": 47, "class": "ARCHITECTURAL_DEBT", "description": "87.8% heuristic I-scores; self-resolves on next generation run; ledger_age ~42.58h"}
  ],
  "stale_docs": [
    {"id": "OPEN-003", "consecutive_reports": 47, "class": "STALE_DOC", "description": "No [WIRE-B] label; runner header V31.0 vs CLAUDE.md V36.5; cosmetic only"}
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_count": 24,
  "generation_idle_cycles": 29,
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
  "recommended_next_action": "no_action — code fully sound; operator must run generation to resolve P1/P2 and restore pipeline_outputs; R50 reclassification milestone approaching for OPEN-009 (13 cycles) and OPEN-010 (16 cycles)"
}
```
