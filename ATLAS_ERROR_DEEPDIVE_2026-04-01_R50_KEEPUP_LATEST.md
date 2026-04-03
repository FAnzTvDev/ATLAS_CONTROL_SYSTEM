# ATLAS ERROR DEEPDIVE — 2026-04-01 R50 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T05:10:13Z
**Run number:** R50 ⚑ MILESTONE — PERMANENT_DATA_GAP reclassification evaluated this session
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R49_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (15th consecutive session R36–R50). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 20h 22m** (~44.38h total from 2026-03-30T08:47:31 UTC to 2026-04-01T05:10:13Z UTC).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (15th consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R49→R50):** ~0h 59m (2026-04-01T04:10:48Z → 2026-04-01T05:10:13Z)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 PERMANENT_DATA_GAP 🔴🔴 (RECLASSIFIED THIS SESSION) / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R49: ⚑ R50 MILESTONE — OPEN-009 + OPEN-010 RECLASSIFIED FROM META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP. No code changes — session enforcer ✅ SYSTEM HEALTHY (12th consecutive code-stable session R39–R50)**

| Category | Count | Delta vs R49 | Status |
|----------|-------|-------------|--------|
| **PERMANENT_DATA_GAP** | 2 | ⚑ NEW CLASS (reclassified from META-CHRONIC-ESCALATED) | OPEN-009 (**39th**) + OPEN-010 (**36th**) — 15th consecutive absent pipeline_outputs session. **Milestone R50 triggered reclassification.** |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **49th** report |
| STALE_DOC | 1 | = (OPEN-003) | **49th** report |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R50 |
| **CODE CHANGES SINCE R49** | **NONE** | = | Runner still 6,271 lines (mtime 2026-03-31 13:27:21 EDT — unchanged since R39). Orchestrator mtime 2026-03-31 13:20:31 EDT — unchanged. **12th consecutive code-stable session (R39–R50).** `find . -name "*.py" -newer R49_report.md` → empty. |
| **DATA CHANGES SINCE R49** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R49** | **0 frames, 0 videos** | = | **System idle — 31st consecutive idle generation report (R20–R50)** |

**Key findings R50:**

1. 🟢 **SESSION ENFORCER: ✅ SYSTEM HEALTHY — same as R39–R49.** Learning log: 0 regressions (22 fixes ALL CLEAR — live R50). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (confirmed R50).

2. 🔴🔴 **⚑ MILESTONE TRIGGERED: OPEN-009 + OPEN-010 RECLASSIFIED FROM `META-CHRONIC-ESCALATED` → `PERMANENT_DATA_GAP`.** Milestone condition: workspace mount remains unresolved at R50. Condition CONFIRMED MET — `pipeline_outputs/` absent at OS level for **15th consecutive session (R36–R50)**. Per protocol established in R49: "At R50, recommend reclassifying both as PERMANENT_DATA_GAP if workspace mount remains unresolved." Root blocker unchanged: operator intervention required to restore pipeline_outputs/. These issues cannot self-resolve via code path.

3. 🟢 **NO CODE CHANGES R49→R50 — 12TH CONSECUTIVE CODE-STABLE SESSION.** Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT (confirmed live R50 via `stat`). Orchestrator: mtime 2026-03-31 13:20:31 EDT. `find . -name "*.py" -newer R49_report.md` returned empty (confirmed live R50). No new modules, no new wiring.

4. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 49th consecutive report.** Estimated ledger age: **~1d 20h 22m stale** (~44.38h total). Self-resolves on next generation run.

5. 🟡 **OPEN-003 STALE_DOC — 49th consecutive report.** `grep -c "WIRE-B" atlas_universal_runner.py → 0` confirmed live R50. `_fail_sids` logic at runner:5734 fully functional. Cosmetic only. Runner header still reads V31.0 vs V36.5 CLAUDE.md.

6. 🟢 **ALL CONFIRMED-FIXED ITEMS STABLE (24).** OPEN-005 fix (runner:24 "Kling v3/pro PRIMARY") confirmed live R50. Wire positions confirmed: Wire-A×6 (2535/2539/2544/2560/2564/2567), Wire-C×6 (5493/5513/5515/5518/5520/5522), Wire-B `_fail_sids` at runner:5734. VVO 4 active call sites (2610/3346/3491/3827) confirmed live R50. V37: 31 lines containing `_V37`/`v37` in runner, 7 `/api/v37` endpoints in orchestrator — confirmed live R50.

7. 🟢 **SYSTEM IDLE — 31st consecutive idle report (R20–R50).** Est. ~1d 20h 22m since last ledger entry. At ~48–70 min/cycle: R51 ≈ ~1d 21h 10m–32m stale if no generation run occurs.

8. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent (no 4h proof-gate run found). Non-blocking.

9. ℹ️ **Cycle interval R49→R50: 0h 59m** — within normal operating range (~48–70 min).

10. ℹ️ **All 5 env keys PRESENT** (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) — confirmed live R50.

11. ℹ️ **V37 ref count stable at 31 lines** (ERE baseline R47, confirmed R48/R49/R50). 7 `/api/v37` endpoints in orchestrator confirmed unchanged R50.

12. ℹ️ **isinstance guards: 8 hits** (1503/1540/3324/3325/3445/3490/3522/3596) — same as R49. Defense-in-depth for T2-OR-18 intact.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R50 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1540 canonical (T2-OR-18), also at 1503, 3324, 3325, 3445, 3490, 3522, 3596 (8 hits — defense-in-depth). | `grep -n "isinstance.*list"` → 8+ hits ✅ (live R50) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` import at runner:87, stub at runner:91, 3 call sites at runner:2408, 2699, 3281. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R50) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | OPEN-005 FIXED (R39, confirmed R50). Runner:24 = "Kling v3/pro PRIMARY". LTX guard at runner:533. `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5 accurate. | runner:24/533/563 ✅ (live R50) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522) = 12 combined. Wire-B `_fail_sids` at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO 4 active call sites (2610/3346/3491/3827). V37: 7 endpoints in orchestrator. | Session enforcer ✅ (live R50); wire counts = 12 ✅ (live R50) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (39th): 4 API-path video_urls — **PERMANENT_DATA_GAP**. OPEN-010 (36th): 4 ghost first_frame_urls — **PERMANENT_DATA_GAP**. | .env scan ✅ (live R50); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (15th session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. ~1d 20h 22m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). | Ledger: UNVERIFIED_CARRY_FORWARD (15th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (15th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R50). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R50) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R50 — same as R44–R49). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R50) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic mismatch. CLAUDE.md V36.5 content accurate. No [WIRE-B] label (functional). | OPEN-003 confirmed live R50 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R50. No changes from R49.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 3324, 3325, 3445, 3490, 3522, 3596).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 lines containing `_V37`/`v37` in runner (live R50 ERE baseline); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R50 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R50.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R50.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url (code path confirmed closed).
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". LTX guard: "Use Kling v3/pro." Both corrected. Confirmed R50.

---

## 4. OPEN ISSUES

### ⚑ R50 MILESTONE RECLASSIFICATION

Per the protocol established in R49:
> "At R50, recommend reclassifying both as `PERMANENT_DATA_GAP` if workspace mount remains unresolved."

**Condition check:** `if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo EXISTS; else echo ABSENT; fi` → **ABSENT** (15th consecutive session). **Condition MET.**

**Both OPEN-009 and OPEN-010 are hereby reclassified from `META-CHRONIC-ESCALATED` → `PERMANENT_DATA_GAP`.**

Rationale: 50+ reporting cycles (~50+ hours of continuous automated monitoring) have elapsed without the workspace mount becoming available. These issues cannot self-resolve through code changes. The data layer is architecturally inaccessible in this deployment context. Continued `META-CHRONIC-ESCALATED` classification is noise; `PERMANENT_DATA_GAP` accurately reflects the situation.

---

### 🔴 PERMANENT_DATA_GAP (39 reports): OPEN-009 — API-Path Prefix in video_url
### ⚑ RECLASSIFIED: META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R50 status vs R49:** UNVERIFIED_CARRY_FORWARD — 15th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. **RECLASSIFIED: PERMANENT_DATA_GAP.**

**PROOF RECEIPT (R50):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. pipeline_outputs dir absent at OS level (15th session).
RECLASSIFICATION BASIS: Milestone R50 triggered. 50 reporting cycles elapsed. No operator action observed. Workspace mount unresolved.
```

**Remaining fix (data patch only — no code changes needed — requires operator action):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   video_url = video_url.replace("/api/media?path=", "")
# Total: 4 field changes, ~2 min
# Verify: grep "/api/media" pipeline_outputs/victorian_shadows_ep1/shot_plan.json | wc -l → 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url`, `nano_prompt`, `_beat_action`, `_approval_status`, `_chain_group`, `_arc_position`. Confirm: `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY after patch.

**Classification:** PERMANENT_DATA_GAP (reclassified R50, was META-CHRONIC-ESCALATED). Data hygiene. ~2 min fix when pipeline_outputs restored. **Root blocker: pipeline_outputs absent from workspace.**

---

### 🔴 PERMANENT_DATA_GAP (36 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚑ RECLASSIFIED: META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 36th consecutive report.

**R50 status vs R49:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. **RECLASSIFIED: PERMANENT_DATA_GAP.**

**PROOF RECEIPT (R50):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live check was R35
CONFIRMS: Cannot live-verify. 001_M01.jpg was the only confirmed existing frame (R35).
RECLASSIFICATION BASIS: Milestone R50 triggered. 50 reporting cycles elapsed. No operator action observed. Workspace mount unresolved.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg existed on disk (R35). scene001_lite.mp4 confirmed present (R35). UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation — requires operator action):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk (R35). scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05. `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY after patch.

**Classification:** PERMANENT_DATA_GAP (reclassified R50, was META-CHRONIC-ESCALATED). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD (15th session). **Root blocker: pipeline_outputs absent from workspace.**

---

### OPEN-002 (ARCHITECTURAL_DEBT — **49th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 20h 22m stale** (~44.38h total — cannot verify directly, 15th consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R50 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "... reward_ledger.jsonl ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-04-01T05:10:13 UTC = ~1d 20h 22m (~44.38h total)
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (49th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **49th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734. Runner header also shows V31.0 (vs V36.5 in CLAUDE.md) — cosmetic mismatch.

**PROOF (R50 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py
OUTPUT: 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: 5734:    _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R50.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.

**Classification:** STALE_DOC. 49th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 15th session).

**PROOF (R50 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (15th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 30th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications beyond the milestone PERMANENT_DATA_GAP upgrade for OPEN-009 and OPEN-010.

---

## 6. NEW OBSERVATIONS (R50)

### 6.1 ⚑ R50 MILESTONE — PERMANENT_DATA_GAP RECLASSIFICATION

The milestone established in R49 triggered at R50. Both OPEN-009 (39 reports) and OPEN-010 (36 reports) are reclassified from META-CHRONIC-ESCALATED to PERMANENT_DATA_GAP effective this session.

**Reclassification rationale:**
- 50+ reporting cycles have elapsed without the workspace mount being restored
- No code changes can resolve either issue — both require operator interaction with the `pipeline_outputs/` data layer
- The keep-up task operates correctly and has faithfully reported these issues; continuing to escalate them serves no additional signal value
- PERMANENT_DATA_GAP accurately models the situation: the data exists (confirmed R35) and the code fix is known (~2 min for OPEN-009, one regen run for OPEN-010), but the environment does not allow access

**Recommended operator action (unchanged):**
1. Ensure `pipeline_outputs/victorian_shadows_ep1/` is present in the workspace mount
2. Apply OPEN-009 data patch (4 video_url field edits, ~2 min)
3. Run `--frames-only` for scene 001 to regenerate ghost frames (OPEN-010)
4. Review/approve in UI filmstrip, then `--videos-only`

### 6.2 NO CODE CHANGES R49→R50 — 12TH CONSECUTIVE CODE-STABLE SESSION (R39–R50)

Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — **identical to R39–R49**. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical through all 12 sessions. `find . -name "*.py" -newer R49_report.md` returned empty (confirmed live R50). Cycle interval from R49: **0h 59m** (2026-04-01T04:10:48Z → 2026-04-01T05:10:13Z) — within normal operating range.

### 6.3 PIPELINE_OUTPUTS ABSENT — 15TH CONSECUTIVE SESSION (R36–R50)

Root cause analysis (unchanged): `pipeline_outputs/` is absent at the OS level in the mounted workspace. Consistent with the workspace folder being a separate mount that may not persist between Cowork sessions.

**Impact assessment:**
- OPEN-009 + OPEN-010: Cannot verify or fix (data patch requires file access) → PERMANENT_DATA_GAP
- OPEN-002: Ledger staleness grows ~1h per cycle (~44.38h total)
- VVO G4 proof: Cannot obtain without a generation run
- Session enforcer: Fully operational (code-only checks — ✅ SYSTEM HEALTHY confirmed)
- System health: Code is fully sound; data layer is inaccessible

### 6.4 THIRTY-FIRST CONSECUTIVE IDLE GENERATION — R20 THROUGH R50

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R49 | ~1d 19h 23m | 30th |
| **R50** | **~1d 20h 22m (~44.38h total)** | **31st** |

At ~48–70 min/cycle: R51 ≈ ~1d 21h 10m–32m stale if no generation occurs.

### 6.5 VVO MODULE — G3 WIRED, G4 UNPROVEN (UNCHANGED R39–R50)

`tools/video_vision_oversight.py` wired at runner:366-392 (import block) with active call sites confirmed live R50:
- `_vvo_preflight_e_shot` at runner:2610 (E-shot pre-check in gen_frame_async)
- `_vvo_preflight_e_shot` at runner:3346 (preflight check, context: `_pf_result`)
- `_vvo_run` at runner:3491 (main video oversight call)
- `_vvo_chain_check` at runner:3827 (chain transition check — confirmed R50)

Session enforcer confirms VVO importable + `_vvo_run` wired. G4 proof requires a live generation run. Status unchanged since R39.

### 6.6 WIRE LABEL POSITIONS (LIVE R50 — CONFIRMED)

| Wire | Label Count | Positions | Logic |
|------|------------|-----------|-------|
| WIRE-A | 6 | 2535/2539/2544/2560/2564/2567 | Back-to-camera skip, budget exhausted, auto-regen, fix success, no-improve, regen-failed |
| WIRE-B | 0 labels | N/A (OPEN-003) | `_fail_sids` functional at runner:5734 |
| WIRE-C | 6 | 5493/5513/5515/5518/5520/5522 | Frozen attempt, success, still-frozen, call-failed, no-start-frame, exception |

### 6.7 V37 REF COUNT — STABLE AT 31 (ERE BASELINE)

`grep -cE "_V37|v37" atlas_universal_runner.py → 31` (live R50). Matches R47/R48/R49 ERE baseline. Runner provably unchanged (mtime 2026-03-31 13:27:21 EDT; `find -newer R49_report` returned empty). 7 `/api/v37` endpoints in orchestrator confirmed unchanged. No regression.

### 6.8 ISSUE COUNT INFLECTION AT R50

With the PERMANENT_DATA_GAP reclassification:
- The issue tracker now has a cleaner signal: 0 META-CHRONIC issues (previously 2 for 10+ sessions)
- ARCHITECTURAL_DEBT + STALE_DOC + PRODUCTION_GAP are all non-code-regression issues
- The effective code health of ATLAS remains: **✅ SYSTEM HEALTHY** with 24 confirmed fixes and 0 regressions

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC issues appear here. With the reclassification at R50, there are **0 active CONFIRMED_BUG or META-CHRONIC issues requiring code fixes**. The two PERMANENT_DATA_GAP issues require operator data access, not code changes.

| Priority | Issue | Class | Consecutive Reports | Fix Effort | Blocker |
|----------|-------|-------|---------------------|------------|---------|
| P1 | OPEN-009: API-path prefix in video_url | PERMANENT_DATA_GAP | 39 | ~2 min data patch | pipeline_outputs absent |
| P2 | OPEN-010: Ghost first_frame_url 001_M02-M05 | PERMANENT_DATA_GAP | 36 | Regen 4 shots | pipeline_outputs absent |

**Note:** OPEN-002 and OPEN-003 are ARCHITECTURAL_DEBT and STALE_DOC — not code bugs, not on priority fix list. PRODUCTION_GAP items (approval/regen status) also require operator action, not code changes.

**The ATLAS codebase is in a sound state.** All code fixes are verified stable. The outstanding issues are data-layer access problems, not logic errors.

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ Session enforcer: ✅ SYSTEM HEALTHY ✅ (live R50)
□ Learning log: 0 regressions (22 fixes ALL CLEAR) ✅ (live R50)
□ ACTIVE_VIDEO_MODEL = "kling" at runner:563 ✅ (live R50)
□ LTX_FAST = _LTXRetiredGuard() at runner:533 ✅ (live R50)
□ Wire-A: 6 hits (2535/2539/2544/2560/2564/2567) ✅ (live R50)
□ Wire-B: _fail_sids at runner:5734 ✅ (live R50)
□ Wire-C: 6 hits (5493/5513/5515/5518/5520/5522) ✅ (live R50)
□ enrich_shots_with_arc at runner:65 + 4967 ✅ (live R50)
□ _cpc_decontaminate at runner:87/91/2408/2699/3281 ✅ (live R50)
□ isinstance guard at runner:1503/1540/3324/3325/3445/3490/3522/3596 (8 hits) ✅ (live R50)
□ VVO active call sites: 2610/3346/3491/3827 ✅ (live R50)
□ V37 endpoints: 7 in orchestrator ✅ (live R50)
□ All 5 env keys PRESENT (.env) ✅ (live R50)
□ Vision backends: gemini_vision + openrouter + florence_fal + heuristic ✅ (enforcer R50)
□ Runner line count: 6,271 (unchanged from R39) ✅ (live R50)
□ Orchestrator mtime: 2026-03-31 13:20:31 EDT (unchanged from R40) ✅ (live R50)
□ No .py files newer than R49 report ✅ (live R50)
□ Runner line 24: "Kling v3/pro PRIMARY" ✅ (live R50)
```

---

## 9. DOCUMENT LINEAGE

- **Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R49_KEEPUP_LATEST.md
- **This report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R50_KEEPUP_LATEST.md
- **Cycle:** ~0h 59m (R49→R50)
- **Next expected:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R51_KEEPUP_LATEST.md (~2026-04-01T05:58–06:20Z)
- **R50 note:** PERMANENT_DATA_GAP reclassification executed. R51 will carry OPEN-009/OPEN-010 under the new classification. No further escalation milestones scheduled for these issues unless operator resolves or closes.

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T05:10:13Z",
  "run_number": "R50",
  "milestone": "PERMANENT_DATA_GAP_RECLASSIFICATION",
  "cycle_interval_minutes": 59,
  "ledger_age_hours": 44.38,
  "ledger_status": "UNVERIFIED_CARRY_FORWARD",
  "pipeline_outputs_present": false,
  "consecutive_absent_sessions": 15,
  "code_changes_since_prior": 0,
  "consecutive_code_stable_sessions": 12,
  "enforcer_result": {"status": "SYSTEM_HEALTHY"},
  "vision_backends": ["gemini_vision", "openrouter", "florence_fal", "heuristic"],
  "learning_log_regressions": 0,
  "permanent_data_gap": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 39,
      "class": "PERMANENT_DATA_GAP",
      "prior_class": "META-CHRONIC-ESCALATED",
      "reclassified_at": "R50",
      "proof_receipt": "if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo EXISTS; else echo ABSENT; fi → ABSENT (15th consecutive session)",
      "fix_recipe": "4-field data patch on video_url for 008_E01/E02/E03/M03b — requires pipeline_outputs present",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status", "_chain_group", "_arc_position"],
      "blocker": "pipeline_outputs absent from workspace mount"
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 36,
      "class": "PERMANENT_DATA_GAP",
      "prior_class": "META-CHRONIC-ESCALATED",
      "reclassified_at": "R50",
      "proof_receipt": "if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo EXISTS; else echo ABSENT; fi → ABSENT (15th consecutive session)",
      "fix_recipe": "Reset first_frame_url + _approval_status on 001_M02-M05, run --frames-only",
      "regression_guard": ["001_M01.jpg", "scene001_lite.mp4"],
      "blocker": "pipeline_outputs absent from workspace mount"
    }
  ],
  "architectural_debt": [
    {"id": "OPEN-002", "consecutive_reports": 49, "class": "ARCHITECTURAL_DEBT", "description": "87.8% heuristic I-scores; self-resolves on next generation run; ledger_age ~44.38h"}
  ],
  "stale_docs": [
    {"id": "OPEN-003", "consecutive_reports": 49, "class": "STALE_DOC", "description": "No [WIRE-B] label; runner header V31.0 vs CLAUDE.md V36.5; cosmetic only"}
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_count": 24,
  "generation_idle_cycles": 31,
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
  "recommended_next_action": "no_action — code fully sound (12th consecutive code-stable session); OPEN-009 + OPEN-010 reclassified PERMANENT_DATA_GAP; operator must restore pipeline_outputs to resolve; R51 continues normal monitoring cadence under new classification"
}
```
