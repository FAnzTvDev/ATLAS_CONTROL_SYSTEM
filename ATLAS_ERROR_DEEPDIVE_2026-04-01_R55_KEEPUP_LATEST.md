# ATLAS ERROR DEEPDIVE — 2026-04-01 R55 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T10:10:46Z
**Run number:** R55
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R54_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (20th consecutive session R36–R55). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~2d 1h 23m** (~49.39h total from 2026-03-30T08:47:31 UTC to 2026-04-01T10:10:46Z UTC). ⚑ **LEDGER NOW ~49.39h STALE — PAST 2-DAY MARK.**
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (20th consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R54→R55):** ~59m 35s (2026-04-01T09:11:11Z → 2026-04-01T10:10:46Z)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 PERMANENT_DATA_GAP 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R54: ⚑ OPEN-002 + OPEN-003 reach 54th report. ⚑ pipeline_outputs absent 20th session. Ledger ~49.39h stale. No code changes — session enforcer ✅ SYSTEM HEALTHY (17th consecutive code-stable session R39–R55)**

| Category | Count | Delta vs R54 | Status |
|----------|-------|-------------|--------|
| **PERMANENT_DATA_GAP** | 2 | counters +1 | OPEN-009 (**44th**) + OPEN-010 (**41st**) — 20th consecutive absent pipeline_outputs session. |
| ARCHITECTURAL_DEBT | 1 | ⚑ counter = **54th** (OPEN-002) | Ledger ~49.39h stale — past 2-day mark |
| STALE_DOC | 1 | ⚑ counter = **54th** (OPEN-003) | **54th consecutive report** |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R55 |
| **CODE CHANGES SINCE R54** | **NONE** | = | Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — unchanged. Orchestrator: mtime 2026-03-31 13:20:31 EDT — unchanged. `find . -name "*.py" -newer R54_report.md` → 0. **17th consecutive code-stable session (R39–R55).** |
| **DATA CHANGES SINCE R54** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R54** | **0 frames, 0 videos** | = | **System idle — 36th consecutive idle generation report (R20–R55)** |

**Key findings R55:**

1. 🟢 **SESSION ENFORCER: ✅ SYSTEM HEALTHY — same as R39–R54.** Learning log: 0 regressions (22 fixes ALL CLEAR — live R55). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (confirmed R55).

2. ⚑ **OPEN-002 + OPEN-003 reach 54th consecutive report.** Both passive (ARCHITECTURAL_DEBT / STALE_DOC). Neither blocks generation.

3. ⚑ **LEDGER NOW ~49.39h STALE.** Estimated ledger age: **~2d 1h 23m** (~49.39h). R54 was 48.39h (2-day crossing). Now deepening past the 2-day mark. Operator attention strongly recommended to restore pipeline_outputs and trigger a generation run.

4. 🟢 **NO CODE CHANGES R54→R55 — 17TH CONSECUTIVE CODE-STABLE SESSION.** Runner: 6,271 lines, mtime 2026-03-31 13:27:21 EDT — identical R39–R55. Orchestrator: mtime 2026-03-31 13:20:31 EDT — identical R39–R55. `find . -name "*.py" -newer [R54 report]` → 0 (confirmed live R55). Cycle interval: **59m 35s** — within normal operating range.

5. 🔴 **OPEN-009 + OPEN-010: PERMANENT_DATA_GAP — 20TH CONSECUTIVE ABSENT SESSION.** pipeline_outputs ABSENT confirmed live R55 (ABSENT at OS level). No change in status or fix recipe.

6. 🔴 **OPEN-002 ARCHITECTURAL_DEBT — 54th consecutive report.** Estimated ledger age: **~2d 1h 23m stale** (~49.39h total). Self-resolves on next generation run. Past 48h/2-day threshold and growing.

7. 🟡 **OPEN-003 STALE_DOC — 54th consecutive report.** `grep -c "WIRE-B" atlas_universal_runner.py → 0` confirmed live R55. `_fail_sids` at runner:5734 functional. Runner header V31.0 vs V36.5 CLAUDE.md — cosmetic only.

8. 🟢 **ALL 24 CONFIRMED-FIXED ITEMS STABLE.** Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522), Wire-B `_fail_sids` at runner:5734, VVO (5 call sites: 2610/3346/3491/3827/5861 — consistent with R52–R54 baseline), V37 (31 lines / 7 endpoints) — all confirmed live R55.

9. 🟢 **SYSTEM IDLE — 36th consecutive idle report (R20–R55).** Est. ~2d 1h 23m since last ledger entry. At ~60 min/cycle: R56 ≈ ~2d 2h ~23m stale if no generation run occurs.

10. 🟢 **VVO 5 CALL SITES CONFIRMED (R52 BASELINE STABLE).** Live grep R55: 2610 (`_vvo_preflight_e_shot`), 3346 (`_vvo_preflight_e_shot`), 3491 (`_vvo_run`), 3827 (`_vvo_chain_check`), 5861 (`_vvo_scene_stitch_check`). Runner mtime UNCHANGED — consistent with R52–R54 baseline.

11. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent. Non-blocking.

12. ℹ️ **All 5 env keys PRESENT** (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) — confirmed live R55.

13. ℹ️ **isinstance guard count: 10 `isinstance.*list)` hits confirmed live R55.** Consistent with R51–R54.

14. ℹ️ **LEDGER NOW ~49.39h STALE (continuing past 2-day mark).** No code-level escalation needed (ARCHITECTURAL_DEBT classification unchanged). Operator awareness flagged at elevated priority.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R55 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guards: 10 `isinstance.*list)` hits confirmed. T2-OR-18 defense-in-depth intact. | `grep -c "isinstance.*list)"` → 10 ✅ (live R55) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` import at runner:87, stub at runner:91, 3 call sites at runner:2408/2699/3281. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R55) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | Runner:24 = "Kling v3/pro PRIMARY". LTX guard at runner:533 (`_LTXRetiredGuard`). `ACTIVE_VIDEO_MODEL="kling"` at runner:563. CLAUDE.md V36.5. | runner:24/533/563 ✅ (live R55) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Wire-A (6 hits: 2535/2539/2544/2560/2564/2567), Wire-C (6 hits: 5493/5513/5515/5518/5520/5522) = 12 combined. Wire-B `_fail_sids` at runner:5734. `enrich_shots_with_arc` at runner:65/4967. VVO **5** call sites (2610/3346/3491/3827/5861). V37: 7 endpoints. | Session enforcer ✅ (live R55); wire counts = 12 ✅ (live R55) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (44th): 4 API-path video_urls — **PERMANENT_DATA_GAP**. OPEN-010 (41st): 4 ghost first_frame_urls — **PERMANENT_DATA_GAP**. | .env scan ✅ (live R55); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (20th session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. **~2d 1h 23m stale** (~49.39h). 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). Past 2-day mark and growing. | Ledger: UNVERIFIED_CARRY_FORWARD (20th session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. | File counts: UNVERIFIED_CARRY_FORWARD (20th session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5734 (live R55). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5734 ✅ (live R55) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R55 — same as R44–R54). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R55) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic. CLAUDE.md V36.5 content accurate. No [WIRE-B] label (functional). OPEN-003 — 54th report. | `grep -c "WIRE-B"` → 0 ✅ confirmed live R55 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R55. No changes from R54.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Confirmed live R55.
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
✅ **V37 GOVERNANCE HOOKS** — 31 lines containing `_V37`/`v37` in runner (live R55); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R55 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R55 (5493/5513/5515/5518/5520/5522).
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:563 confirmed R55.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2408/2699/3281).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url.
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". Confirmed R55.

---

## 4. OPEN ISSUES

### 🔴 PERMANENT_DATA_GAP (44 reports): OPEN-009 — API-Path Prefix in video_url
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R55 status vs R54:** UNVERIFIED_CARRY_FORWARD — 20th consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. No change.

**PROOF RECEIPT (R55):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. pipeline_outputs dir absent (20th session).
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

### 🔴 PERMANENT_DATA_GAP (41 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 41st consecutive report.

**R55 status vs R54:** UNVERIFIED_CARRY_FORWARD — 20th consecutive session. No change.

**PROOF RECEIPT (R55):**
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

### ⚑ OPEN-002 (ARCHITECTURAL_DEBT — **54th consecutive report** ⚑ LEDGER >2-DAY STALE)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~2d 1h 23m stale** (~49.39h total). Past 48h/2-day threshold (crossed R54) and continuing to grow.

**PROOF RECEIPT (R55 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: python3 -c "... reward_ledger.jsonl ..." → LEDGER_ERR: No such file or directory
TIMESTAMP_ESTIMATE: 2026-03-30T08:47:31 UTC → 2026-04-01T10:10:46 UTC = ~2d 1h 23m (~49.39h total)
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
NOTE: Ledger is now ~49.39h stale — growing past 2-day mark. Operator attention required.
```

**Classification:** ARCHITECTURAL_DEBT (54th report). Self-resolves on next generation run. No code action required.

---

### ⚑ OPEN-003 (STALE_DOC — **54th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5734. Runner header also shows V31.0 (vs V36.5 in CLAUDE.md) — cosmetic mismatch.

**PROOF (R55 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py
OUTPUT: 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: 5734:    _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R55.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5734. One line, ~30 seconds.
**Classification:** STALE_DOC. 54th consecutive report. Logic functional. Cosmetic only.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED
*(36th consecutive carry-forward)*

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 20th session).

**PROOF (R55 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent entirely (20th consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 36th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 24 confirmed-fixed items stable. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R55)

### 6.1 LEDGER CONTINUES PAST 2-DAY MARK (~49.39h)

Ledger age crosses to ~49.39h at this session — approximately 1 hour deeper than the 2-day milestone crossed in R54. The situation is unchanged from a code perspective (ARCHITECTURAL_DEBT, self-resolves on generation), but the staleness window continues to widen at ~1h per ECC cycle. At ~60min/cycle, R56 will reach ~50.4h if no generation occurs.

### 6.2 PIPELINE_OUTPUTS ABSENT — 20TH CONSECUTIVE SESSION (R36–R55)

Root cause (unchanged): `pipeline_outputs/` absent at OS level in mounted workspace — confirmed live R55 via `if [ -d pipeline_outputs/victorian_shadows_ep1 ]`. Consistent with workspace folder being a separate mount that may not persist between Cowork sessions. All code checks fully live; all data checks remain UNVERIFIED_CARRY_FORWARD.

### 6.3 SYSTEM STABLE — 17TH CONSECUTIVE CODE-STABLE SESSION

No .py files modified since R54 (confirmed live: `find . -name "*.py" -newer ATLAS_ERROR_DEEPDIVE_2026-04-01_R54_KEEPUP_LATEST.md` → 0). The ATLAS codebase remains in the same state since 2026-03-31 13:27:21 EDT. All wires intact. No regressions.

### 6.4 OPEN-002 + OPEN-003 REACH 54TH REPORT

Both OPEN-002 (ARCHITECTURAL_DEBT) and OPEN-003 (STALE_DOC) reach their 54th consecutive report. Neither has a code-blocking implication:
- **OPEN-002** resolves immediately upon next generation run. Ledger now ~49.39h stale.
- **OPEN-003** is a one-line comment addition, requires operator to edit runner.

### 6.5 VVO + WIRE BASELINES STABLE (R52 BASELINE NOW HELD FOR 4 SESSIONS)

All wire and VVO baselines from R52 confirmed identical in R55:
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
□ Session enforcer → ✅ SYSTEM HEALTHY (confirmed live R55)
□ WIRE-A (6 hits: 2535/2539/2544/2560/2564/2567) → ✅ confirmed live R55
□ WIRE-C (6 hits: 5493/5513/5515/5518/5520/5522) → ✅ confirmed live R55
□ WIRE-B _fail_sids at runner:5734 → ✅ confirmed live R55
□ ACTIVE_VIDEO_MODEL="kling" at runner:563 → ✅ confirmed live R55
□ LTX_FAST = _LTXRetiredGuard() at runner:533 → ✅ confirmed live R55
□ enrich_shots_with_arc at runner:65/4967 → ✅ confirmed live R55
□ _cpc_decontaminate at runner:87/2408/2699/3281 → ✅ confirmed live R55
□ _wire_a_reset at runner:497/4755 → ✅ confirmed live R55
□ VVO 5 call sites (2610/3346/3491/3827/5861) → ✅ confirmed live R55 (R52 baseline stable ×4 sessions)
□ V37: 31 lines in runner, 7 endpoints in orchestrator → ✅ confirmed live R55
□ Learning log: 0 regressions (22 fixes ALL CLEAR) → ✅ confirmed live R55
□ All 5 env keys PRESENT → ✅ confirmed live R55
□ isinstance guard (T2-OR-18): 10 `isinstance.*list)` hits → ✅ confirmed live R55
□ Runner line count: 6,271 lines, mtime 2026-03-31 13:27:21 EDT → ✅ confirmed live R55
□ find . -name "*.py" -newer R54_report.md → 0 (no new code) ✅ confirmed live R55
```

---

## 9. DOCUMENT LINEAGE

- Prior: ATLAS_ERROR_DEEPDIVE_2026-04-01_R54_KEEPUP_LATEST.md
- This: ATLAS_ERROR_DEEPDIVE_2026-04-01_R55_KEEPUP_LATEST.md
- System version: V36.5

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T10:10:46Z",
  "run_number": "R55",
  "cycle_interval_minutes": 59,
  "cycle_interval_seconds": 35,
  "ledger_age_hours": 49.39,
  "ledger_milestone": "PAST_48H_2DAY_THRESHOLD_GROWING",
  "ledger_status": "UNVERIFIED_CARRY_FORWARD",
  "pipeline_outputs_present": false,
  "pipeline_outputs_absent_sessions": 20,
  "code_stable_sessions": 17,
  "session_enforcer": "SYSTEM_HEALTHY",
  "learning_log_regressions": 0,
  "vision_backends": ["gemini_vision", "openrouter", "florence_fal", "heuristic"],
  "generation_idle_sessions": 36,
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
  "new_py_files_since_r54": 0,
  "milestones_this_session": [
    "OPEN-002 54th report",
    "OPEN-003 54th report",
    "pipeline_outputs 20th absent session",
    "LEDGER ~49.39h stale (growing past 2-day mark)"
  ],
  "precision_upgrades_this_session": [],
  "permanent_data_gap_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 44,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1/ ABSENT (20th session). Last live scan R35.",
      "fix_recipe": "4x video_url.replace('/api/media?path=', '') in shot_plan.json. ~2 min. Requires pipeline_outputs access.",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 41,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1/ ABSENT (20th session). Last live scan R35.",
      "fix_recipe": "Clear first_frame_url on 001_M02-M05, set AWAITING_APPROVAL, run --frames-only, review, --videos-only.",
      "regression_guard": ["001_M01.jpg", "scene001_lite.mp4", "all other shots"]
    }
  ],
  "architectural_debt_issues": [
    {
      "id": "OPEN-002",
      "consecutive_reports": 54,
      "class": "ARCHITECTURAL_DEBT",
      "ledger_age_hours": 49.39,
      "ledger_milestone": "PAST_48H_2DAY_THRESHOLD_GROWING",
      "note": "Self-resolves on next generation run. 54th report — no code action required. Ledger now ~49.39h stale."
    }
  ],
  "stale_doc_issues": [
    {
      "id": "OPEN-003",
      "consecutive_reports": 54,
      "class": "STALE_DOC",
      "fix_recipe": "Add '# ── [WIRE-B] Quality gate stitch filter' at runner:5734. ~30 seconds.",
      "note": "54th report. Logic functional. Cosmetic only."
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
  "operator_action_summary": "⚑ Ledger now ~49.39h stale (past 2-day mark, growing ~1h/cycle). Restore pipeline_outputs/ to workspace mount, then: (1) apply OPEN-009 data patch, (2) regen 001_M02-M05 frames, (3) add WIRE-B comment, (4) approve 006_M02+M04, (5) regen 008_M03b+M04."
}
```
