# ATLAS ERROR DEEPDIVE — 2026-04-01 R56 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T11:10:00Z
**Run number:** R56
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R55_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (21st consecutive session R36–R56). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~2d 2h 22m** (~50.37h total from 2026-03-30T08:47:31 UTC to 2026-04-01T11:10:00 UTC). ⚑ **LEDGER NOW ~50.37h STALE — DEEPENING PAST 2-DAY MARK.**
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (21st consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R55→R56):** ~59m 14s (2026-04-01T10:10:46Z → 2026-04-01T11:10:00Z)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 PERMANENT_DATA_GAP 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R55: ⚑ OPEN-002 + OPEN-003 reach 55th report. ⚑ pipeline_outputs absent 21st session. Ledger ~50.37h stale (+1h). No code changes — session enforcer ✅ SYSTEM HEALTHY (18th consecutive code-stable session R39–R56)**

| Category | Count | Delta vs R55 | Status |
|----------|-------|-------------|--------|
| **PERMANENT_DATA_GAP** | 2 | counters +1 | OPEN-009 (**45th**) + OPEN-010 (**42nd**) — 21st consecutive absent pipeline_outputs session. |
| ARCHITECTURAL_DEBT | 1 | ⚑ counter = **55th** (OPEN-002) | Ledger ~50.37h stale — deepening past 2-day mark |
| STALE_DOC | 1 | ⚑ counter = **55th** (OPEN-003) | **55th consecutive report** |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R56 |
| **CODE CHANGES SINCE R55** | **NONE** | = | Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — unchanged. `find . -name "*.py" -newer R55_report.md` → 0. **18th consecutive code-stable session (R39–R56).** |
| **DATA CHANGES SINCE R55** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R55** | **0 frames, 0 videos** | = | **System idle — 37th consecutive idle generation report (R20–R56)** |

**Key findings R56:**

1. 🟢 **SESSION ENFORCER: ✅ SYSTEM HEALTHY — same as R39–R55.** Learning log: 0 regressions (22 fixes ALL CLEAR — live R56). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (confirmed R56).

2. ⚑ **OPEN-002 + OPEN-003 reach 55th consecutive report.** Both passive (ARCHITECTURAL_DEBT / STALE_DOC). Neither blocks generation.

3. ⚑ **LEDGER NOW ~50.37h STALE.** Estimated ledger age: **~2d 2h 22m** (~50.37h). R55 was ~49.39h. Now ~1h deeper past the 2-day mark. Operator attention strongly recommended to restore pipeline_outputs and trigger a generation run.

4. 🟢 **NO CODE CHANGES R55→R56 — 18TH CONSECUTIVE CODE-STABLE SESSION.** Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — identical R39–R56. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical. `find . -name "*.py" -newer [R55 report]` → 0 (confirmed live R56). Cycle interval: **59m 14s** — within normal operating range.

5. 🔴 **OPEN-009 + OPEN-010: PERMANENT_DATA_GAP — 21ST CONSECUTIVE ABSENT SESSION.** pipeline_outputs ABSENT confirmed live R56 (`if [ -d pipeline_outputs/victorian_shadows_ep1 ]` → ABSENT). No change in status or fix recipe.

6. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 55th consecutive report.** Estimated ledger age: **~2d 2h 22m stale** (~50.37h total). Self-resolves on next generation run. Past 48h/2-day threshold and growing ~1h per ECC cycle.

7. 🟡 **OPEN-003 STALE_DOC — 55th consecutive report.** `grep -c "WIRE-B" atlas_universal_runner.py → 0` confirmed live R56. `_fail_sids` at runner:5734 functional. Runner header V31.0 vs V36.5 CLAUDE.md — cosmetic only.

8. 🟢 **ALL 24 CONFIRMED-FIXED ITEMS STABLE.** Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522), Wire-B `_fail_sids` at runner:5734, VVO (5 call sites: 2610/3346/3491/3827/5861 — consistent with R52–R55 baseline), V37 (31 lines / 7 endpoints) — all confirmed live R56.

9. 🟢 **SYSTEM IDLE — 37th consecutive idle report (R20–R56).** Est. ~2d 2h 22m since last ledger entry. At ~60 min/cycle: R57 ≈ ~2d 3h ~22m stale if no generation run occurs.

10. 🟢 **VVO 5 CALL SITES CONFIRMED (R52 BASELINE STABLE).** Live grep R56: 2610 (`_vvo_preflight_e_shot`), 3346 (`_vvo_preflight_e_shot`), 3491 (`_vvo_run`), 3827 (`_vvo_chain_check`), 5861 (`_vvo_scene_stitch_check`). Runner mtime UNCHANGED — consistent with R52–R55 baseline.

11. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent. Non-blocking.

12. ℹ️ **All 5 env keys PRESENT** (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) — confirmed live R56.

13. ℹ️ **isinstance guard count: 10 `isinstance.*list)` hits confirmed live R56.** Consistent with R51–R55.

14. ℹ️ **LEDGER NOW ~50.37h STALE (deepening past 2-day mark).** No code-level escalation needed (ARCHITECTURAL_DEBT classification unchanged). Operator awareness flagged at elevated priority. Rate: +1h/cycle.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R56 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guards: 10 `isinstance.*list)` hits confirmed. T2-OR-18 defense-in-depth intact. | `grep -c "isinstance.*list)"` → 10 ✅ (live R56) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` import at runner:87, stub at runner:91, 3 call sites at runner:2408/2699/3281. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R56) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | Runner:24 = "Kling v3/pro PRIMARY". LTX guard at runner:533 (`_LTXRetiredGuard`). `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5. | runner:24/533/563 ✅ (live R56) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522) = 12 combined. Wire-B `_fail_sids` at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO **5** call sites (2610/3346/3491/3827/5861). V37: 7 endpoints. | Session enforcer ✅ (live R56); wire counts = 12 ✅ (live R56) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (45th): 4 API-path video_urls — **PERMANENT_DATA_GAP**. OPEN-010 (42nd): 4 ghost first_frame_urls — **PERMANENT_DATA_GAP**. | .env scan ✅ (live R56); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (21st session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. **~2d 2h 22m stale** (~50.37h). 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). Past 2-day mark and deepening. | Ledger: UNVERIFIED_CARRY_FORWARD (21st session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (21st session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R56). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R56) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R56 — same as R44–R55). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R56) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic. CLAUDE.md V36.5 content accurate. No [WIRE-B] label (functional). OPEN-003 — 55th report. | `grep -c "WIRE-B"` → 0 ✅ confirmed live R56 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R56. No changes from R55.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Confirmed live R56.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:563.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:533.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1540 (also 1503, 3325, 4540, 4722, 5212, 5290, 5627, 5726, 6111).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` at runner:497, called at runner:4755.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4967.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 lines containing `_V37`/`v37` in runner (live R56); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R56 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R56 (5493/5513/5515/5518/5520/5522).
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R56.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url.
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". Confirmed R56.

---

## 4. OPEN ISSUES

### 🔴 PERMANENT_DATA_GAP (45 reports): OPEN-009 — API-Path Prefix in video_url
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R56 status vs R55:** UNVERIFIED_CARRY_FORWARD — 21st consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. No change.

**PROOF RECEIPT (R56):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. pipeline_outputs dir absent (21st session).
```

**Fix (data patch — requires operator action, ~2 min):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   video_url = video_url.replace("/api/media?path=", "")
# Verify: grep "/api/media" pipeline_outputs/victorian_shadows_ep1/shot_plan.json | wc -l → 0
```

**Regression guard:** Only touch `video_url` on 4 shots. Must NOT touch: `first_frame_url`, `nano_prompt`, `_beat_action`, `_approval_status`. Confirm: `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY after patch.
**Classification:** PERMANENT_DATA_GAP. Root blocker: pipeline_outputs absent from workspace.

---

### 🔴 PERMANENT_DATA_GAP (42 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 42nd consecutive report.

**R56 status vs R55:** UNVERIFIED_CARRY_FORWARD — 21st consecutive session. No change.

**PROOF RECEIPT (R56):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live check was R35
CONFIRMS: Cannot live-verify. Root cause confirmed in R35; code unchanged since R39.
```

**Fix (data patch + re-generation — requires operator action):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Regression guard:** 001_M01.jpg confirmed present on disk (R35). scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05.
**Classification:** PERMANENT_DATA_GAP. Root blocker: pipeline_outputs absent from workspace.

---

### ⚑ OPEN-002 (ARCHITECTURAL_DEBT — **55th consecutive report** ⚑ LEDGER >2-DAY STALE DEEPENING)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~2d 2h 22m stale** (~50.37h total). Past 48h/2-day threshold and deepening at ~1h/cycle.

**PROOF RECEIPT (R56 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "... reward_ledger.jsonl ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-04-01T11:10:00 UTC = ~2d 2h 22m (~50.37h total)
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
NOTE: Ledger is now ~50.37h stale — +1h from R55. Rate: +~1h/ECC cycle. Operator attention required.
```

**Classification:** ARCHITECTURAL_DEBT (55th report). Self-resolves on next generation run. No code action required.

---

### ⚑ OPEN-003 (STALE_DOC — **55th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734. Runner header also shows V31.0 (vs V36.5 in CLAUDE.md) — cosmetic mismatch.

**PROOF (R56 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py
OUTPUT: 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: 5734:    _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R56.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.
**Classification:** STALE_DOC. 55th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED
*(37th consecutive carry-forward)*

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 21st session).

**PROOF (R56 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (21st consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 37th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R56)

### 6.1 LEDGER AGE: ~50.37h — +1h FROM R55

Ledger age advances to ~50.37h, approximately 1h deeper than R55 (~49.39h). The situation remains unchanged from a code perspective (ARCHITECTURAL_DEBT, self-resolves on generation). At the current ECC cycle rate of ~60min, R57 will be at ~51.4h if no generation run occurs. The ledger has now been stale for over 2 full days.

### 6.2 PIPELINE_OUTPUTS ABSENT — 21ST CONSECUTIVE SESSION (R36–R56)

Root cause (unchanged): `pipeline_outputs/` absent at OS level in mounted workspace — confirmed live R56 via `if [ -d pipeline_outputs/victorian_shadows_ep1 ]`. Consistent with workspace folder being a separate mount that may not persist between Cowork sessions. All code checks fully live; all data checks remain UNVERIFIED_CARRY_FORWARD.

### 6.3 SYSTEM STABLE — 18TH CONSECUTIVE CODE-STABLE SESSION

No .py files modified since R55 (confirmed live: `find . -name "*.py" -newer ATLAS_ERROR_DEEPDIVE_2026-04-01_R55_KEEPUP_LATEST.md` → 0). The ATLAS codebase remains in the same state since 2026-03-31 13:27:21 EDT. All wires intact. No regressions. Session enforcer ✅ SYSTEM HEALTHY for 18 consecutive sessions.

### 6.4 OPEN-002 + OPEN-003 REACH 55TH REPORT

Both OPEN-002 (ARCHITECTURAL_DEBT) and OPEN-003 (STALE_DOC) reach their 55th consecutive report. Neither has a code-blocking implication:
- **OPEN-002** resolves immediately upon next generation run. Ledger now ~50.37h stale.
- **OPEN-003** is a one-line comment addition, requires operator to edit runner.

### 6.5 VVO + WIRE BASELINES STABLE (R52 BASELINE NOW HELD FOR 5 SESSIONS)

All wire and VVO baselines from R52 confirmed identical in R56 (5th consecutive confirmation):
- Wire-A: 6 hits (same lines 2535/2539/2544/2560/2564/2567)
- Wire-C: 6 hits (same lines 5493/5513/5515/5518/5520/5522)
- Wire-B: 0 labels, `_fail_sids` functional at runner:5734
- VVO: 5 call sites (same lines 2610/3346/3491/3827/5861)

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG / CHRONIC / META-CHRONIC issues eligible. Current state has none of these classes.

**No fixes are prioritised this session.** All open issues are PERMANENT_DATA_GAP (requires operator data access), ARCHITECTURAL_DEBT (self-resolves on generation), or STALE_DOC (cosmetic).

**Operator action recommended (when pipeline_outputs is next accessible) — priority order:**
1. ⚑ Restore `pipeline_outputs/` to workspace mount — root unblocks all data-layer issues
2. Apply OPEN-009 data patch (4 video_url edits, ~2 min)
3. Run `--frames-only` for scene 001 to regenerate ghost frames (OPEN-010)
4. Add `# ── [WIRE-B]` comment at runner:5734 (OPEN-003, ~30 sec)
5. Review/approve 006_M02 + 006_M04 in UI filmstrip (PRODUCTION_GAP)
6. Regen 008_M03b + 008_M04 (PRODUCTION_GAP)

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ Session enforcer → ✅ SYSTEM HEALTHY (confirmed live R56)
□ WIRE-A (6 hits: 2535/2539/2544/2560/2564/2567) → ✅ confirmed live R56
□ WIRE-C (6 hits: 5493/5513/5515/5518/5520/5522) → ✅ confirmed live R56
□ WIRE-B _fail_sids at runner:5734 → ✅ confirmed live R56
□ ACTIVE_VIDEO_MODEL="kling" at runner:563 → ✅ confirmed live R56
□ LTX_FAST = _LTXRetiredGuard() at runner:533 → ✅ confirmed live R56
□ enrich_shots_with_arc at runner:65/4967 → ✅ confirmed live R56
□ _cpc_decontaminate at runner:87/2408/2699/3281 → ✅ confirmed live R56
□ _wire_a_reset at runner:497/4755 → ✅ confirmed live R56
□ VVO 5 call sites (2610/3346/3491/3827/5861) → ✅ confirmed live R56 (R52 baseline stable ×5 sessions)
□ V37: 31 lines in runner, 7 endpoints in orchestrator → ✅ confirmed live R56
□ Learning log: 0 regressions (22 fixes ALL CLEAR) → ✅ confirmed live R56
□ All 5 env keys PRESENT → ✅ confirmed live R56
□ isinstance guard (T2-OR-18): 10 `isinstance.*list)` hits → ✅ confirmed live R56
□ Runner line count: 6,271 lines, mtime 2026-03-31 13:27:21 EDT → ✅ confirmed live R56
□ find . -name "*.py" -newer R55_report.md → 0 (no new code) ✅ confirmed live R56
```

---

## 9. DOCUMENT LINEAGE

- Prior: ATLAS_ERROR_DEEPDIVE_2026-04-01_R55_KEEPUP_LATEST.md
- This: ATLAS_ERROR_DEEPDIVE_2026-04-01_R56_KEEPUP_LATEST.md
- System version: V36.5

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T11:10:00Z",
  "run_number": "R56",
  "cycle_interval_minutes": 59,
  "cycle_interval_seconds": 14,
  "ledger_age_hours": 50.37,
  "ledger_milestone": "PAST_48H_2DAY_THRESHOLD_DEEPENING",
  "ledger_status": "UNVERIFIED_CARRY_FORWARD",
  "pipeline_outputs_present": false,
  "pipeline_outputs_absent_sessions": 21,
  "code_stable_sessions": 18,
  "session_enforcer": "SYSTEM_HEALTHY",
  "learning_log_regressions": 0,
  "vision_backends": ["gemini_vision", "openrouter", "florence_fal", "heuristic"],
  "generation_idle_sessions": 37,
  "wire_a_hits": 6,
  "wire_a_lines": [2535, 2539, 2544, 2560, 2564, 2567],
  "wire_c_hits": 6,
  "wire_c_lines": [5493, 5513, 5515, 5518, 5520, 5522],
  "wire_bc_combined": 12,
  "wire_b_label_hits": 0,
  "wire_b_functional": true,
  "wire_b_line": 5734,
  "vvo_call_sites": 5,
  "vvo_call_lines": [2610, 3346, 3491, 3827, 5861],
  "v37_lines_runner": 31,
  "v37_endpoints_orchestrator": 7,
  "env_keys_present": 5,
  "isinstance_guards": 10,
  "runner_line_count": 6271,
  "runner_mtime": "2026-03-31T13:27:21-04:00",
  "orchestrator_mtime": "2026-03-31T13:20:31-04:00",
  "new_py_files_since_r55": 0,
  "milestones_this_session": [
    "OPEN-002 55th report",
    "OPEN-003 55th report",
    "pipeline_outputs 21st absent session",
    "LEDGER ~50.37h stale (deepening past 2-day mark, +1h from R55)",
    "VVO R52 baseline held 5 consecutive sessions"
  ],
  "precision_upgrades_this_session": [],
  "permanent_data_gap_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 45,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1/ ABSENT (21st session). Last live scan R35.",
      "fix_recipe": "4x video_url.replace('/api/media?path=', '') in shot_plan.json. ~2 min. Requires pipeline_outputs access.",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 42,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1/ ABSENT (21st session). Last live scan R35.",
      "fix_recipe": "Clear first_frame_url on 001_M02-M05, set AWAITING_APPROVAL, run --frames-only, review, --videos-only.",
      "regression_guard": ["001_M01.jpg", "scene001_lite.mp4", "all other shots"]
    }
  ],
  "architectural_debt_issues": [
    {
      "id": "OPEN-002",
      "consecutive_reports": 55,
      "class": "ARCHITECTURAL_DEBT",
      "ledger_age_hours": 50.37,
      "ledger_milestone": "PAST_48H_2DAY_THRESHOLD_DEEPENING",
      "note": "Self-resolves on next generation run. 55th report — no code action required. Ledger now ~50.37h stale, +1h from R55."
    }
  ],
  "stale_doc_issues": [
    {
      "id": "OPEN-003",
      "consecutive_reports": 55,
      "class": "STALE_DOC",
      "fix_recipe": "Add '# ── [WIRE-B] Quality gate stitch filter' at runner:5734. ~30 seconds.",
      "note": "55th report. Logic functional. Cosmetic only."
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
  "recommended_next_action": "no_action",
  "operator_action_required": true,
  "operator_action_priority": "ELEVATED",
  "operator_action_summary": "⚑ Ledger now ~50.37h stale (deepening past 2-day mark, +1h/cycle). Restore pipeline_outputs/ to workspace mount, then: (1) apply OPEN-009 data patch, (2) regen 001_M02-M05 frames, (3) add WIRE-B comment, (4) approve 006_M02+M04, (5) regen 008_M03b+M04."
}
```
