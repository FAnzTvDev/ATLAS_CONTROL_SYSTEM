# ATLAS ERROR DEEPDIVE — 2026-04-01 R58 (KEEP-UP LATEST)

**Session timestamp:** 2026-04-01T13:12:13Z
**Run number:** R58
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-04-01_R57_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — cosmetic mismatch, OPEN-003)
**Ledger age at snapshot:** UNVERIFIED_CARRY_FORWARD — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (23rd consecutive session R36–R58). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~2d 4h 24m** (~52.41h total). ⚑ **LEDGER NOW ~52.41h STALE — +1.03h FROM R57 (~51.38h).**
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` dir ABSENT entirely (23rd consecutive session). OPEN-009/OPEN-010 remain UNVERIFIED_CARRY_FORWARD. All code checks fully live this session.
**Cycle interval (R57→R58):** ~62m 49s (2026-04-01T12:10:24Z → 2026-04-01T13:13:13Z approx)

---

## 1. EXECUTIVE SUMMARY

**Score: 15 PASS / 0 CONFIRMED_BUG / 2 PERMANENT_DATA_GAP 🔴🔴 / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC | DELTA vs R57: ⚑ NEW CODE CHANGE — RUNNER MODIFIED (mtime 2026-04-01 08:28:47 EDT, +132 lines, 6271→6403). THREE NEW INTELLIGENCE MODULES WIRED (director_brain, production_intelligence, doctrine_tracker) + LYRIA SOUNDSCAPE HOOK. All non-blocking, G1+G2 pass. Session enforcer ✅ SYSTEM HEALTHY but NOT UPDATED for new modules. OPEN-002+OPEN-003 reach 57th report. Ledger ~52.41h stale (+1.03h). 20th consecutive code-stable then modified session — first code change since R39-baseline.**

| Category | Count | Delta vs R57 | Status |
|----------|-------|-------------|--------|
| **CODE CHANGE** | **+132 lines** | ⚑ **FIRST SINCE R39 BASELINE** | Runner modified 2026-04-01 08:28:47 EDT. 3 new modules + Lyria hook wired. |
| **PERMANENT_DATA_GAP** | 2 | counters +1 | OPEN-009 (**47th**) + OPEN-010 (**44th**) — 23rd consecutive absent pipeline_outputs session. |
| ARCHITECTURAL_DEBT | 1 | ⚑ counter = **57th** (OPEN-002) | Ledger ~52.41h stale — deepening past 2-day mark at +~1h/cycle |
| STALE_DOC | 1 | ⚑ counter = **57th** (OPEN-003) | **57th consecutive report** |
| **NEW CONCERN** | 1 | NEW | Session enforcer NOT updated for 4 new modules. WIRED but UNMONITORED. |
| **CONFIRMED_FIXED** | **24** | = | 0 regressions confirmed R58. All 24 carry forward. |
| **DATA CHANGES SINCE R57** | 0 | = | pipeline_outputs absent — no verification possible |
| **GENERATION SINCE R57** | **0 frames, 0 videos** | = | **System idle — 39th consecutive idle generation report (R20–R58)** |

**Key findings R58:**

1. ⚑ **RUNNER MODIFIED SINCE R57 — FIRST CODE CHANGE SINCE R39 BASELINE.** mtime changed from `2026-03-31 13:27:21 EDT` (R57 confirmed) to `2026-04-01 08:28:47 EDT` (R58 live). Line count: 6,271 → 6,403 (+132 lines). This breaks the "19th consecutive code-stable session" streak. The 20th cycle produced the first code change.

2. ⚑ **THREE NEW INTELLIGENCE MODULES WIRED (non-blocking):**
   - `tools/director_brain.py` (738 lines) — Layer 2, `_db_pre_scene_brief()` called at runner:4775 (pre-scene) + scene-close eval at runner:6155. G1 OK, G2 IMPORTABLE (live R58).
   - `tools/production_intelligence.py` (703 lines) — Layer 1, `_pi_write_shot()` at runner:6121 + `write_scene_outcome()` at runner:6135. G1 OK, G2 IMPORTABLE (live R58).
   - `tools/doctrine_tracker.py` (793 lines) — Layer 3, `_dt_finalize()` at runner:6167 + `_dt_extract_gate()` at runner:6162. G1 OK, G2 IMPORTABLE (live R58).
   - All three: non-blocking pattern (try/except stubs). Gate level: WIRED (G1+G2 pass). G4 UNPROVEN — requires production run.

3. ⚑ **LYRIA SOUNDSCAPE HOOK DISCOVERED.** `tools/lyria_score_generator` imported at runner:319/325 (non-blocking), called at runner:5968 post-scene (not frames-only). G2: IMPORTABLE (live R58). Non-blocking. Advisory only.

4. 🟡 **SESSION ENFORCER NOT UPDATED for new modules.** `session_enforcer.py` has no wiring probes for `director_brain`, `production_intelligence`, `doctrine_tracker`, or `lyria_score_generator`. Consequence: enforcer gives no signal about whether these are correctly wired in future code changes. Classification: DEGRADED_MONITORING (not a production blocker — all modules non-blocking). Fix: add wiring probes to session_enforcer.py (Upgrade Validation Protocol G3 step not completed for these 4 modules).

5. 🟢 **SESSION ENFORCER: ✅ SYSTEM HEALTHY (live R58).** All 22 learning log fixes verified (0 regressions). Vision backends: gemini_vision + openrouter + florence_fal + heuristic. Session enforcer result unchanged from R39–R57 pattern.

6. 🟢 **ALL PRIOR WIRES INTACT (line numbers shifted due to +132 lines):**
   - Wire-A: 6 hits — now at 2583/2587/2592/2608/2612/2615 (were 2535/2539/2544/2560/2564/2567 in R57, +48 delta)
   - Wire-B `_fail_sids`: now at line 5801 (was 5734, +67 delta)
   - Wire-C: 6 hits — now at 5560/5580/5582/5585/5587/5589 (were 5493/5513/5515/5518/5520/5522, +67 delta)
   - VVO: 5 call sites — now at 2658/3394/3539/3875/5928 (were 2610/3346/3491/3827/5861, +48/+67 delta)
   - V37 `_V37_GOVERNANCE`: 4 lines at 311/313/5302/5736 (consistent)

7. ⚑ **OPEN-002 + OPEN-003 reach 57th consecutive report.** Passive. Neither blocks generation.

8. ⚑ **LEDGER NOW ~52.41h STALE.** Estimated: **2d 4h 24m**. Past 2-day threshold by >4h. Rate: +~1h/cycle. R59 estimate: ~53.4h if no generation run.

9. 🔴 **OPEN-009 + OPEN-010: PERMANENT_DATA_GAP — 23rd consecutive absent session.** `pipeline_outputs/victorian_shadows_ep1` ABSENT confirmed live R58.

10. ℹ️ **All 5 env keys PRESENT** (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) — confirmed live R58.

11. ℹ️ **isinstance guard count: 10 `isinstance.*list)` hits** — consistent with R51–R57.

12. ℹ️ **V37 `_V37_GOVERNANCE`: 4 confirmed lines (311/313/5302/5736).** Meets CLAUDE.md 4+ expectation. 7 `/api/v37` endpoints in orchestrator confirmed (enforcer). Consistent with R57.

13. ℹ️ **No proof gate reports present** — `ATLAS_PROOF_GATE_*.md` absent. Non-blocking.

14. ℹ️ **Orchestrator mtime unchanged: 2026-03-31 13:20:31 EDT** — identical R57. Orchestrator line count: 51,161.

15. ℹ️ **RUNNER DOCSTRING STILL V31.0** — header line 1 unchanged despite +132 lines of intelligence modules added. OPEN-003 persists.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R58 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guards: 10 `isinstance.*list)` hits confirmed. T2-OR-18 defense-in-depth intact. | `grep -c "isinstance.*list)"` → 10 ✅ (live R58) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` import at runner:87, stub at runner:91, 3 call sites at runner:2456/2747/3329 (shifted +48 from R57). | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R58) |
| 🛡️ Immune (doctrine) | 🟢 HEALTHY | Runner line 24 = "Kling v3/pro PRIMARY". LTX guard at runner:581 (`_LTXRetiredGuard`). `ACTIVE_VIDEO_MODEL="kling"` at runner:611. CLAUDE.md V36.5. | runner:24/581/611 ✅ (live R58) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. Wire-A (6 hits: 2583/2587/2592/2608/2612/2615), Wire-C (6 hits: 5560/5580/5582/5585/5587/5589) = 12 combined. Wire-B `_fail_sids` at runner:5801. `enrich_shots_with_arc` at runner:65/5034. VVO **5** call sites (2658/3394/3539/3875/5928). V37: 7 endpoints (orchestrator). **NEW: 3 Intel layers + Lyria wired (non-blocking, G1+G2 pass).** | Session enforcer ✅ (live R58); wire counts = 12 ✅ (live R58) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live). Vision backends: gemini_vision + openrouter + florence_fal + heuristic (enforcer-confirmed). OPEN-009 (47th): 4 API-path video_urls — **PERMANENT_DATA_GAP**. OPEN-010 (44th): 4 ghost first_frame_urls — **PERMANENT_DATA_GAP**. | .env scan ✅ (live R58); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD (23rd session) |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward R35 — pipeline_outputs absent). Est. **~2d 4h 24m stale** (~52.41h). 87.8% heuristic I=0.75. 5 real-VLM shots (R35 data). Past 2-day mark and deepening. | Ledger: UNVERIFIED_CARRY_FORWARD (23rd session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. pipeline_outputs absent entirely at OS level. **NEW: Director Brain wired at pre-scene (runner:4775) — will enhance prompt quality on next run.** | File counts: UNVERIFIED_CARRY_FORWARD (23rd session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5801 (live R58, shifted from 5734+67). `_blocked_sids` / `_fail_sids` / `_frozen_sids` logic intact. | `grep -n "_fail_sids"` → runner:5801 ✅ (live R58) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A+C: 12 combined hits (live R58 — shifted from R57 line numbers, count unchanged). All 6 Wire-A + 6 Wire-C present. | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R58) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 (vs V36.5 CLAUDE.md) — cosmetic. CLAUDE.md V36.5 content accurate. No [WIRE-B] label (functional at runner:5801). OPEN-003 — 57th report. | `grep -c "WIRE-B"` → 0 ✅ confirmed live R58 |
| 🧠 Intelligence (new) | 🟡 PARTIAL | 3 Intel layers (director_brain/production_intelligence/doctrine_tracker) + Lyria: G1+G2 pass, WIRED, non-blocking. Session enforcer NOT updated — UNMONITORED. G4 UNPROVEN. | G1+G2 ✅ (live R58); session_enforcer probe ABSENT |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

24 items total — 0 regressions confirmed R58. No changes from R57. All line numbers shifted due to +132 new lines in runner but functional positions verified live.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Confirmed live R58.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:611 (shifted +48 from R57:563).
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:581 (shifted +48 from R57:533).
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` 10 hits confirmed (runner:1540 shifted, full set preserved).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner; called in `run_scene()`.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:5034 (shifted from 4967).
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — `_V37_GOVERNANCE` at 4 runner lines (311/313/5302/5736); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed). CLAUDE.md 4+ expectation MET.
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R58 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R58 (5560/5580/5582/5585/5587/5589, shifted +67 from R57).
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:611 confirmed R58 (shifted from 563).
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2456/2747/3329, shifted).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots have proper disk-path first_frame_url.
✅ **OPEN-005 CLOSED (R39) — STALE DOCSTRING FIXED** — Runner line 24: "Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0". Confirmed R58.

---

## 4. OPEN ISSUES

### 🔴 PERMANENT_DATA_GAP (47 reports): OPEN-009 — API-Path Prefix in video_url
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url fully fixed (R23). All underlying video files confirmed on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R58 status vs R57:** UNVERIFIED_CARRY_FORWARD — 23rd consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. No change.

**PROOF RECEIPT (R58):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. Issue confirmed in R35. pipeline_outputs dir absent (23rd session).
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

### 🔴 PERMANENT_DATA_GAP (44 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
*(Reclassified META-CHRONIC-ESCALATED → PERMANENT_DATA_GAP at R50 milestone)*

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 44th consecutive report.

**R58 status vs R57:** UNVERIFIED_CARRY_FORWARD — 23rd consecutive session. No change.

**PROOF RECEIPT (R58):**
```
PROOF: if [ -d pipeline_outputs/victorian_shadows_ep1 ]; then echo "EXISTS"; else echo "ABSENT"; fi
OUTPUT: PIPELINE_OUTPUTS: ABSENT
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35
CONFIRMS: Cannot live-verify. pipeline_outputs absent (23rd session).
```

**Fix (requires operator action):**
```bash
# Stage 1 — generate fresh frames:
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# Stage 2 — review in UI, approve valid frames
# Stage 3 — OPEN-010 self-resolves as frames exist on disk and are approved
```

**Classification:** PERMANENT_DATA_GAP. Root blocker: pipeline_outputs absent from workspace.

---

### ⏱️ ARCHITECTURAL_DEBT (57th report): OPEN-002 — Reward Ledger Staleness
*(Carried forward R2–R58. Self-resolves on next generation run.)*

**Issue:** Last ledger entry: 2026-03-30T08:47:31 UTC (R35 confirmed). Estimated age as of R58: **~2d 4h 24m (~52.41h)**. Past 2-day mark by >4h. At ~1h/cycle rate: R59 ≈ ~53.4h if no generation.

**R58 status vs R57:** +1.03h deeper. No code change. Self-resolves on next `--frames-only` or full generation run.

**PROOF RECEIPT (R58):**
```
PROOF: python3 -c "import datetime; last=datetime.datetime(2026,3,30,8,47,31,tzinfo=datetime.timezone.utc); now=datetime.datetime.now(datetime.timezone.utc); d=now-last; print(f'{d.days}d {d.seconds//3600}h {(d.seconds%3600)//60}m / {d.total_seconds()/3600:.2f}h')"
OUTPUT: 2d 4h 24m / 52.41h
CONFIRMS: Ledger ~52.41h stale. deepening at +~1h/cycle.
```

**Fix:** Run any generation: `python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only`
**Classification:** ARCHITECTURAL_DEBT. Self-resolves. Operator attention recommended.

---

### ⏱️ STALE_DOC (57th report): OPEN-003 — Runner Header Version Mismatch
*(Carried forward R2–R58. Cosmetic only — no functional impact.)*

**Issue:** `atlas_universal_runner.py` docstring line 3 reads `"ATLAS UNIVERSAL RUNNER V31.0"` but CLAUDE.md header is V36.5. `grep -c "WIRE-B" atlas_universal_runner.py → 0` (functional Wire-B at runner:5801 as `_fail_sids` — label missing, function present). The +132 line addition this cycle did NOT update the runner header.

**R58 status vs R57:** No change in classification. Counter increments to 57th. Runner was modified (new modules added) but header not updated — OPEN-003 persists after the code change.

**PROOF RECEIPT (R58):**
```
PROOF: head -4 atlas_universal_runner.py && grep -c "WIRE-B" atlas_universal_runner.py
OUTPUT: line 3: "ATLAS UNIVERSAL RUNNER V31.0 — Kling v3 Pro PRIMARY, End-Frame Chain Fix"
        grep result: 0
CONFIRMS: Docstring V31.0 ≠ CLAUDE.md V36.5. WIRE-B label absent (function present at line 5801).
```

**Fix (≤2 lines):**
```python
# In atlas_universal_runner.py, line 3:
# Change: "ATLAS UNIVERSAL RUNNER V31.0 — Kling v3 Pro PRIMARY, End-Frame Chain Fix"
# To:     "ATLAS UNIVERSAL RUNNER V36.5 — Kling v3 Pro PRIMARY, Chain Arc Intelligence"
# Verify: head -4 atlas_universal_runner.py | grep "V36.5"
```
**Regression guard:** Only touch line 3 docstring. Must NOT touch any import, function, or variable. Confirm: `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY after edit.
**Classification:** STALE_DOC. Cosmetic. Low priority.

---

### 🟡 NEW CONCERN (1st report): OPEN-011 — Session Enforcer Missing Probes for New Intelligence Modules

**Issue:** `tools/session_enforcer.py` was NOT updated when `director_brain.py`, `production_intelligence.py`, `doctrine_tracker.py`, and `lyria_score_generator.py` were wired into `atlas_universal_runner.py`. The session enforcer (G3 gate per Upgrade Validation Protocol) is therefore blind to whether these modules are correctly wired. Future code edits could silently unwire them without the enforcer detecting it.

**R58 status:** Newly discovered this session. 1st report.

**PROOF RECEIPT (R58):**
```
PROOF: grep -n "director_brain\|production_intelligence\|doctrine_tracker\|lyria" tools/session_enforcer.py
OUTPUT: (no output — no matches)
CONFIRMS: Session enforcer has zero probes for the 4 new intelligence modules.
```

**Severity:** LOW-MEDIUM. All 4 modules are non-blocking (stubs on import failure). Generation will not halt if they break. But silent unwiring won't be caught.

**Fix recipe (Upgrade Validation Protocol G3 compliance — ~15-20 lines in session_enforcer.py):**
```python
# In tools/session_enforcer.py, add to the harmony system imports section:
# Check 1: director_brain wired in runner
_db_call = "_db_pre_scene_brief" in runner_code
_checks.append(("Director Brain pre-scene call wired", _db_call,
                "grep for '_db_pre_scene_brief' in runner — non-blocking advisory", True))

# Check 2: production_intelligence wired
_pi_call = "_pi_write_shot" in runner_code or "_pi_inst" in runner_code
_checks.append(("ProductionIntelligence write wired", _pi_call,
                "grep for '_pi_write_shot' or '_pi_inst' in runner — non-blocking advisory", True))

# Check 3: doctrine_tracker wired
_dt_call = "_dt_finalize" in runner_code
_checks.append(("DoctrineTracker finalize wired", _dt_call,
                "grep for '_dt_finalize' in runner — non-blocking advisory", True))

# Check 4: lyria wired
_lyria_call = "_lyria_generate_undertone" in runner_code
_checks.append(("Lyria soundscape hook wired", _lyria_call,
                "grep for '_lyria_generate_undertone' in runner — non-blocking advisory", True))
```
**Note:** These should be advisory (non-blocking) checks since all 4 modules are non-blocking in production.
**Regression guard:** Only add new checks. Must NOT modify existing checks. Confirm: `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY (same or more checks) after edit.
**Classification:** DEGRADED_MONITORING. Fix recommended before next code change cycle.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. No issues reclassified from open → false positive this session.

---

## 6. PRIORITISED FIX LIST

*(Only CONFIRMED_BUG, CHRONIC/META-CHRONIC, and DEGRADED_MONITORING items — never ARCHITECTURAL_DEBT alone)*

| Priority | Issue | Class | Action |
|----------|-------|-------|--------|
| P1 | OPEN-011 — Enforcer missing probes for 4 new modules | DEGRADED_MONITORING | Add ~15-20 lines to session_enforcer.py. Fast fix. |
| P2 | OPEN-002 — Ledger staleness ~52.41h | ARCHITECTURAL_DEBT | Run: `python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only` |
| P3 | OPEN-003 — Runner header V31.0 vs V36.5 | STALE_DOC | 2-line docstring fix (low priority) |
| P4 | OPEN-009 — API-path video_url prefix | PERMANENT_DATA_GAP | Requires pipeline_outputs back in workspace (operator) |
| P5 | OPEN-010 — Ghost first_frame_urls | PERMANENT_DATA_GAP | Requires pipeline_outputs + generation run (operator) |

**Recommended immediate action:** Fix OPEN-011 (session enforcer probes) to maintain G3 monitoring coverage for new intelligence modules. Then run a generation to resolve OPEN-002 and prove the new intelligence layers (G4 gate).

---

## 7. ANTI-REGRESSION CHECKLIST (MACHINE-READABLE)

```
□ Session enforcer: python3 tools/session_enforcer.py → ✅ SYSTEM HEALTHY
□ Wire-A count: grep -c "WIRE-A" atlas_universal_runner.py → 6
□ Wire-C count: grep -c "WIRE-C" atlas_universal_runner.py → 6
□ Wire-A+C combined: grep -c "WIRE-A\|WIRE-C" atlas_universal_runner.py → 12
□ Wire-B functional: grep -n "_fail_sids" atlas_universal_runner.py → present (currently :5801)
□ ACTIVE_VIDEO_MODEL: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | grep '"kling"' → present
□ LTX guard: grep -n "_LTXRetiredGuard" atlas_universal_runner.py → present (:581)
□ isinstance guards: grep -c "isinstance.*list)" atlas_universal_runner.py → 10
□ CPC call sites: grep -c "_cpc_decontaminate" atlas_universal_runner.py → 5
□ enrich_shots_with_arc: grep -c "enrich_shots_with_arc" atlas_universal_runner.py → 2
□ V37 governance: grep -n "_V37_GOVERNANCE" atlas_universal_runner.py | wc -l → 4
□ V37 endpoints: grep -c "api/v37" orchestrator_server.py → 7
□ VVO call sites: grep -c "_vvo_preflight_e_shot\|_vvo_run\b\|_vvo_chain_check\|_vvo_scene_stitch_check" atlas_universal_runner.py → 10+ (imports + calls)
□ Director Brain wired: grep -c "_db_pre_scene_brief" atlas_universal_runner.py → 2+
□ ProductionIntelligence wired: grep -c "_pi_write_shot\|_pi_inst" atlas_universal_runner.py → 2+
□ DoctrineTracker wired: grep -c "_dt_finalize" atlas_universal_runner.py → 2+
□ Lyria wired: grep -c "_lyria_generate_undertone" atlas_universal_runner.py → 2+
□ Learning log: 0 regressions — python3 -c "import sys; sys.path.insert(0,'tools'); from atlas_learning_log import LearningLog; r=LearningLog().check_regression(); print(len(r))" → 0
□ All 5 env keys: FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY PRESENT in .env
```

---

## 8. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-04-01_R57_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-04-01_R58_KEEPUP_LATEST.md`
**Run N:** 58
**Cycle interval:** ~62m 49s (R57→R58)
**Code stable streak:** BROKEN at R58 (was 19 consecutive stable sessions R39–R57, now modified)
**Generation idle streak:** 39th consecutive idle (R20–R58)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-04-01T13:12:13Z",
  "ledger_age_hours": 52.41,
  "run_number": 58,
  "code_changed_this_cycle": true,
  "code_change_summary": "atlas_universal_runner.py +132 lines (6271→6403). 3 new intelligence modules (director_brain, production_intelligence, doctrine_tracker) + Lyria soundscape hook wired. All non-blocking. G1+G2 pass. G3 partial (enforcer not updated). G4 UNPROVEN.",
  "new_modules_wired": [
    {"name": "director_brain", "gate": "G2", "call_site": "runner:4775 + runner:6155", "blocking": false},
    {"name": "production_intelligence", "gate": "G2", "call_site": "runner:6121 + runner:6135", "blocking": false},
    {"name": "doctrine_tracker", "gate": "G2", "call_site": "runner:6167 + runner:6162", "blocking": false},
    {"name": "lyria_score_generator", "gate": "G2", "call_site": "runner:5968", "blocking": false}
  ],
  "open_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 47,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1 ABSENT — 23rd session (live R58)",
      "fix_recipe": "video_url.replace('/api/media?path=', '') on 4 shots in shot_plan.json",
      "regression_guard": ["first_frame_url", "nano_prompt", "_beat_action", "_approval_status"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 44,
      "class": "PERMANENT_DATA_GAP",
      "proof_receipt": "pipeline_outputs/victorian_shadows_ep1 ABSENT — 23rd session (live R58)",
      "fix_recipe": "atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only",
      "regression_guard": []
    },
    {
      "id": "OPEN-002",
      "consecutive_reports": 57,
      "class": "ARCHITECTURAL_DEBT",
      "proof_receipt": "Ledger age: 2d 4h 24m / 52.41h (live calculation R58)",
      "fix_recipe": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only",
      "regression_guard": []
    },
    {
      "id": "OPEN-003",
      "consecutive_reports": 57,
      "class": "STALE_DOC",
      "proof_receipt": "head -4 atlas_universal_runner.py → line 3: V31.0 / grep -c WIRE-B → 0 (live R58)",
      "fix_recipe": "Change runner line 3 docstring from V31.0 to V36.5",
      "regression_guard": ["imports", "functions", "variables — docstring only"]
    },
    {
      "id": "OPEN-011",
      "consecutive_reports": 1,
      "class": "DEGRADED_MONITORING",
      "proof_receipt": "grep -n 'director_brain|production_intelligence|doctrine_tracker|lyria' tools/session_enforcer.py → (no matches) (live R58)",
      "fix_recipe": "Add 4 advisory wiring probes to session_enforcer.py for new intelligence modules",
      "regression_guard": ["all existing session_enforcer checks — add only, never modify"]
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
    "doctrine_doc": "DEGRADED",
    "intelligence_layers": "PARTIAL"
  },
  "session_enforcer_result": "SYSTEM_HEALTHY",
  "learning_log_regressions": 0,
  "runner_mtime": "2026-04-01 08:28:47 EDT",
  "runner_lines": 6403,
  "runner_delta_from_prior": "+132 lines",
  "code_stable_streak_broken": true,
  "generation_idle_streak": 39,
  "recommended_next_action": "fix_enforcer_probes_then_run_generation"
}
```
