# ATLAS ERROR DEEPDIVE — 2026-03-31 R38 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-31T17:10:26Z
**Run number:** R38
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-31_R37_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header — OPEN-005)
**Ledger age at snapshot:** NOT VERIFIABLE THIS SESSION — `pipeline_outputs/victorian_shadows_ep1/` ABSENT (3rd consecutive session). Last confirmed R35: 2026-03-30T08:47:31 UTC. Current estimate: **~1d 8h 22m** (from 2026-03-30T08:47:31 UTC to 2026-03-31T17:10:26Z UTC = 1d 8h 22m 55s).
**Atlas project:** victorian_shadows_ep1
**Note on data-dependent checks:** `pipeline_outputs/victorian_shadows_ep1/` is ABSENT from this workspace session for the **3rd consecutive time** (R36, R37, R38). Per R37 explicit policy: "if absent R38, reclassify OPEN-009/OPEN-010 confirmations as UNVERIFIED_CARRY_FORWARD." That reclassification is applied below. Code checks fully live this session.

---

## 1. EXECUTIVE SUMMARY

**Score: 14 PASS / 0 CONFIRMED_BUG / 2 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC | DELTA vs R37: 0 new issues, OPEN-009/OPEN-010 reclassified to UNVERIFIED_CARRY_FORWARD per R37 policy**

| Category | Count | Delta vs R37 | Status |
|----------|-------|-------------|--------|
| **FALSE_POSITIVES RETRACTED** | 0 | = | None this session |
| **META-CHRONIC total** | 2 | = | OPEN-009 (**27th**) + OPEN-010 (**24th**) — now UNVERIFIED_CARRY_FORWARD |
| ARCHITECTURAL_DEBT | 1 | = (OPEN-002) | **37th** report |
| STALE_DOC | 2 | OPEN-003 (**37th**), OPEN-005 (**35th**) | Cosmetic |
| **CONFIRMED_FIXED** | **23** | = | 23 confirmed — 0 regressions |
| **CODE CHANGES SINCE R37** | **0** | **= (STABLE)** | Runner 6,218 lines, mtime 2026-03-31 08:32:39 EDT (unchanged 3rd consecutive cycle). No new .py files. |
| **DATA CHANGES SINCE R37** | **0** | = | pipeline_outputs absent — no verification possible. Runner mtime unchanged confirms no production run. |
| **GENERATION SINCE R37** | **0 frames, 0 videos** | = | **System idle — 19th consecutive idle generation report (R20–R38)** |

**Key findings R38:**

1. 🟢 **CODE FROZEN — NO CHANGES (3RD CONSECUTIVE CYCLE).** Runner 6,218 lines, mtime 2026-03-31 08:32:39 EDT — identical to R35/R36/R37. No new .py files created. No proof gate files found. System fully quiescent.

2. 🟢 **SESSION ENFORCER: 64 PASS / 0 WARN / 0 BLOCK — ✅ SYSTEM HEALTHY.** Identical to R36 and R37. All 64 checks passing. `✅ SYSTEM HEALTHY` confirmed live this session.

3. 🟢 **ALL 23 CONFIRMED-FIXED ITEMS INTACT.** Wire-A=6, Wire-C=6 (12 combined), Wire-B at runner:5717, isinstance at runner:1523, arc call at runner:4950, CPC call sites 2391/2682/3264 — all confirmed live this session. Learning log: 0 regressions (22 fixes ALL CLEAR).

4. 🔴 **OPEN-009 META-CHRONIC: 27th consecutive report (R12→R38) — UNVERIFIED_CARRY_FORWARD.** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in `video_url`. Per R37 policy, now reclassified from "carry-forward R36" to **UNVERIFIED_CARRY_FORWARD** (3rd consecutive session without pipeline_outputs). Last live confirmation: R35. No mechanism for self-resolution.

5. 🔴 **OPEN-010 META-CHRONIC: 24th consecutive report (R15→R38) — UNVERIFIED_CARRY_FORWARD.** 4 shots (001_M02/M03/M04/M05) have ghost `first_frame_url`. Per R37 policy, reclassified to **UNVERIFIED_CARRY_FORWARD**. Last live confirmation: R35.

6. 🟡 **SYSTEM IDLE (GENERATION) — 19th consecutive idle report (R20–R38).** No new frames or videos. Estimated ledger age ~1d 8h 22m. Average cadence: ~60.3m/cycle.

7. 🟡 **DATA VERIFIABILITY GAP (3RD CONSECUTIVE SESSION).** `pipeline_outputs/victorian_shadows_ep1/` absent across R36, R37, and now R38. Policy threshold met: OPEN-009 and OPEN-010 status is now formally UNVERIFIED_CARRY_FORWARD. All code checks fully live.

8. ⚠️ **OBSERVATION UNCHANGED: `_RUN_LOCK_AVAILABLE` still not probed in session_enforcer.** session_enforcer.py mtime 2026-03-29 22:38:42 EDT — unchanged since R35. run_lock.py (2883 bytes, mtime 2026-03-31 08:31) wired in runner but not explicitly checked in enforcer. Non-blocking. Low priority.

9. ℹ️ **NO PROOF_GATE FILES FOUND.** `ls ATLAS_PROOF_GATE*.md` → 0 results. Proof-gate task has not run or has not written its output. This is a monitoring observation only.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R38 — live unless flagged) |
|-------|--------|--------|----------------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | `isinstance` guard at runner:1523 (live). Multiple guard locations: 1486, 1523, 4523. | `grep -n "isinstance.*list"` → runner:1523 ✅ (live R38) |
| 🫀 Liver (prompt sanitizer) | 🟢 HEALTHY | `_cpc_decontaminate` 3 call sites at runner:2391, 2682, 3264 (live). Import at runner:87, stub at runner:91. | `grep -n "_cpc_decontaminate"` → 5 hits ✅ (live R38) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header line 24 claims "Seedance v2.0 PRIMARY" (STALE_DOC — 35th). `_LTXRetiredGuard` at runner:516 (stale "Use Seedance" message). Code correct: `ACTIVE_VIDEO_MODEL="kling"` at runner:546. CLAUDE.md V36.5 accurate. Enforcer count 47 in CLAUDE.md vs live 64 (cosmetic). | runner:24 stale ✅; runner:546 → `"kling"` ✅ (live R38) |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (64/0/0). Learning log: 0 regressions (22 fixes). Wire-A (6), Wire-C (6), `_fail_sids` runner:5717, `enrich_shots_with_arc` runner:65/4950. | Session enforcer R38 ✅ (live) |
| 👁️ Eyes (vision/identity) | 🔴 SICK | All 5 env keys PRESENT (live: FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available (gemini_vision + openrouter + florence_fal + heuristic per enforcer). OPEN-009: 4 API-path video_urls (UNVERIFIED_CARRY_FORWARD 3rd session). OPEN-010: 4 ghost first_frame_urls (UNVERIFIED_CARRY_FORWARD 3rd session). | .env scan ✅ (live R38); OPEN-009/OPEN-010 UNVERIFIED_CARRY_FORWARD |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 228 entries (carry-forward from R35 — pipeline_outputs absent). Est. ~1d 8h 22m stale. 87.8% heuristic I=0.75. 5 real-VLM shots (carry-forward R35). | Ledger: UNVERIFIED_CARRY_FORWARD (3rd session) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 JPGs / 62 MP4s (UNVERIFIED_CARRY_FORWARD from R35). OPEN-010: 001_M02-M05 ghost frames. OPEN-009: 4 API-path video_urls. Approval status: UNVERIFIED_CARRY_FORWARD. | File counts: UNVERIFIED_CARRY_FORWARD (3rd session) |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B `_fail_sids` at runner:5717 (live). `_blocked_sids` / `_fail_sids` logic intact. | `grep -n "_fail_sids"` → runner:5717 ✅ (live R38) |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-A: 6 hits, Wire-C: 6 hits, 12 combined (live). | `grep -c "WIRE-A\|WIRE-C"` → 12 ✅ (live R38) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header line 24 Seedance claim (35th). LTX guard error says "Use Seedance" (stale since V31.0). CLAUDE.md enforcer count 47 vs live 64 (cosmetic). CLAUDE.md V36.5 content accurate. | Confirmed via live grep R38 ✅ |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

23 items total — all intact, 0 regressions confirmed R38. Identical to R26–R37.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE).
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py confirmed (enforcer).
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py confirmed (enforcer).
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() confirmed in runner.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — ACTIVE_VIDEO_MODEL="kling" at runner:546.
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:516.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1523 (also 1486, 4523).
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` confirmed in runner.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4950.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — 31 `_V37|v37` refs in runner (non-blocking hooks); 7 `/api/v37` endpoints in orchestrator (enforcer-confirmed).
✅ **LEARNING LOG** — 0 regressions (ALL CLEAR — R38 confirmed, 22 fixes verified).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` confirmed in runner.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — 6 Wire-C hits confirmed R38.
✅ **CHAIN_GROUP SET ON M-SHOTS** — 62/62 M-shots confirmed R35 (UNVERIFIED_CARRY_FORWARD — data unchangeable; code unchanged).
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:546 confirmed R38.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.
✅ **OPEN-004 CLOSED (R18) — CPC DECONTAMINATION WIRED** — `_cpc_decontaminate` at 3 call sites (2391/2682/3264).
✅ **OPEN-009 first_frame_url portion (CLOSED R23)** — All 4 shots (008_E01/E02/E03/M03b) have proper disk-path first_frame_url (UNVERIFIED_CARRY_FORWARD data portion, but code path confirmed closed).

---

## 4. OPEN ISSUES

### ⏱️ META-CHRONIC (27 reports): OPEN-009 — API-Path Prefix in video_url
### ⚠️ STATUS CHANGE: UNVERIFIED_CARRY_FORWARD (3rd consecutive session without pipeline_outputs)

**Issue:** 4 shots (008_E01/E02/E03/M03b) carry `/api/media?path=` prefix in **video_url**. first_frame_url was fully fixed (operator data patch, R23). All underlying video files confirmed to exist on disk (last verified R35). Stitch proven non-blocking. Data inconsistency only.

**R38 status vs R37:** UNVERIFIED_CARRY_FORWARD — per R37 explicit policy, reclassified from "carry-forward" to UNVERIFIED_CARRY_FORWARD because `pipeline_outputs/victorian_shadows_ep1/` is absent for the 3rd consecutive session (R36/R37/R38). Last live confirmation: R35 (2026-03-31T13:11Z, ~4h before current R38 time). No mechanism for self-resolution exists; issue is highly unlikely to have changed.

**META-CHRONIC: 27th consecutive report (R12→R38).**

**PROOF RECEIPT (R38):**
```
PROOF: pipeline_outputs/victorian_shadows_ep1/ directory absent from workspace (3rd consecutive session)
OUTPUT: `ls pipeline_outputs/ 2>/dev/null` → "pipeline_outputs ABSENT"
STATUS: UNVERIFIED_CARRY_FORWARD — last live scan was R35 (2026-03-31T13:11Z)
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

**Classification:** META-CHRONIC (27th report). Data hygiene. ~2 min fix. UNVERIFIED_CARRY_FORWARD flag applied R38 per R37 policy.

---

### ⏱️ META-CHRONIC (24 reports): OPEN-010 — Ghost first_frame_url on 001_M02-M05
### ⚠️ STATUS CHANGE: UNVERIFIED_CARRY_FORWARD (3rd consecutive session without pipeline_outputs)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` pointing to files that do not exist on disk. All 4 carry `_approval_status=APPROVED`. 24th consecutive report.

**R38 status vs R37:** UNVERIFIED_CARRY_FORWARD — same reason as OPEN-009. 3rd consecutive session without `pipeline_outputs/victorian_shadows_ep1/`. Last live confirmation: R35.

**META-CHRONIC STATUS:** 24 consecutive reports (R15→R38).

**PROOF RECEIPT (R38):**
```
PROOF: pipeline_outputs/victorian_shadows_ep1/ absent (3rd consecutive session)
OUTPUT: `ls pipeline_outputs/` → "pipeline_outputs ABSENT"
STATUS: UNVERIFIED_CARRY_FORWARD — last live check was R35
CONFIRMS: Cannot live-verify. 001_M01.jpg is the only confirmed existing frame (R35).
LIKELIHOOD STILL OPEN: ~99% (requires operator regen run, zero runs occurred)
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

**Regression guard:** 001_M01.jpg confirmed present on disk (R35). scene001_lite.mp4 preserved. Do not touch shots outside 001_M02-M05. `python3 tools/session_enforcer.py` → 64 PASS after patch.

**Classification:** META-CHRONIC (24th report). Process failure — requires operator action. UNVERIFIED_CARRY_FORWARD flag applied R38.

---

### OPEN-002 (ARCHITECTURAL_DEBT — **37th consecutive report**)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (last-entry-per-shot basis). Pattern is self-resolving on next generation run. Estimated ledger age: **~1d 8h 22m stale** (cannot verify directly this session — 3rd consecutive absence of pipeline_outputs).

**PROOF RECEIPT (R38 — UNVERIFIED_CARRY_FORWARD, ledger absent):**
```
PROOF: Estimated time delta from last confirmed ledger entry (2026-03-30T08:47:31 UTC) to now (2026-03-31T17:10:26Z)
DELTA: 1 day + 8h + 22m + 55s = ~1d 8h 22m
CARRY-FORWARD: 228 entries, 36/41 = 87.8% heuristic I=0.75 (last-entry-per-shot, R35 data)
REAL-VLM: 5/41 shots: 008_M01(1.0), 004_M01(1.0), 004_M02(1.0), 008_M02(0.9), 008_M04(0.8)
```

**Classification:** ARCHITECTURAL_DEBT (37th report). Self-resolves on next generation run.

---

### OPEN-003 (STALE_DOC — **37th consecutive report**)

**Issue:** No `[WIRE-B]` label in atlas_universal_runner.py. `_fail_sids` logic is functional at runner:5717.

**PROOF (R38 live):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
PROOF: grep -n "_fail_sids" atlas_universal_runner.py → runner:5717 ✅ (logic intact, live R38)
CONFIRMS: WIRE-B label absent. Logic functional. LIVE verification R38.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5717. One line, ~30 seconds.

**Classification:** STALE_DOC. 37th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — **35th consecutive report**)

**Issue:** Runner header line 24 claims "Seedance v2.0 PRIMARY (muapi.ai)". Code default is Kling (runner:546). Additionally, `_LTXRetiredGuard.__getattr__` at runner:516 emits stale "Use Seedance" message.

**PROOF (R38 live):**
```
PROOF: sed -n '24p' atlas_universal_runner.py
OUTPUT: "  P2. Videos:          ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1 → runner:546 → "kling" ✅
PROOF: runner:516 → LTX_FAST = _LTXRetiredGuard() with stale "Use Seedance" message
CONFIRMS: Both stale docstring references persist unchanged from R37. Code behavior correct.
```

**Classification:** STALE_DOC. 35th consecutive report. Code behavior correct.

---

### PRODUCTION_GAP — 006_M02 + 006_M04 AWAITING_APPROVAL / 008_M03b + 008_M04 REGEN_REQUESTED

**Issue:** 2 shots in scene 006 carry `_approval_status=AWAITING_APPROVAL`. 2 shots in scene 008 carry `_approval_status=REGEN_REQUESTED`. Unchanged since R21. Now UNVERIFIED_CARRY_FORWARD (pipeline_outputs absent 3rd session).

**PROOF (R38 — UNVERIFIED_CARRY_FORWARD):**
```
NOTE: pipeline_outputs absent (3rd consecutive session). Carry-forward from R36:
  AWAITING_APPROVAL: ['006_M02', '006_M04'] — 18th consecutive report
  REGEN_REQUESTED: ['008_M03b', '008_M04'] — unchanged since R21
  HUMAN_ESCALATION: [] — 0 shots escalated
```

**Classification:** PRODUCTION_GAP (operator action pending). Not a code bug. UNVERIFIED_CARRY_FORWARD.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All open issues carry forward as reported in R37.

---

## 6. NEW OBSERVATIONS (R38)

### 6.1 DATA VERIFIABILITY GAP — 3RD CONSECUTIVE SESSION (POLICY THRESHOLD MET)

**Observation:** R36, R37, and now R38 sessions all lack access to `pipeline_outputs/victorian_shadows_ep1/`. The R37 report explicitly specified: "if pipeline_outputs remains absent in R38, these should be explicitly flagged as UNVERIFIED_CARRY_FORWARD rather than CONFIRMED." That policy has been applied this session to OPEN-009, OPEN-010, ledger data, file counts, and approval status.

**Practical implication:** The open issues' classification as META-CHRONIC remains appropriate — no code mechanism or generation run could have resolved them. However, their confirmed status now rests on 3-session-old data (R35, 2026-03-31T13:11Z, ~4h prior to R37).

**Recommended action:** Operator should ensure R39 mounts pipeline_outputs, OR apply both data patches (OPEN-009: ~2 min, OPEN-010: ~15 min + regen) directly. If neither occurs by R39, suggest escalating to META-CHRONIC-ESCALATED status.

### 6.2 NINETEENTH CONSECUTIVE IDLE GENERATION — R20 THROUGH R38

System has produced zero new frames or videos across 19 consecutive keep-up cycles. Code activity paused completely at R35 (runner last modified 2026-03-31 08:32:39 EDT, now 3 cycles stale).

| Report | Est. Ledger Age | Idle Cycle |
|--------|----------------|------------|
| R20 | 13h 21m | 1st |
| R30 | 23h 21m | 11th |
| R37 | ~1d 7h 23m | 18th |
| R38 | ~1d 8h 22m | **19th** |

At ~60min/cycle: **R39 ≈ ~1d 9h 22m stale** (if no generation run occurs).

### 6.3 NO PROOF_GATE FILES FOUND

**Observation:** `ls ATLAS_PROOF_GATE*.md` returned 0 results. The proof-gate task (designed to run every 4h) either has not produced output files, or its output goes to a different path. This is an informational observation — the proof-gate task may be consuming data from this report's `PROOF_GATE_FEED` section but not writing its own report. No action required.

### 6.4 ADDITIONAL isinstance GUARD LOCATIONS (NEW OBSERVATION)

**Observation:** R37 and prior reports cited `isinstance` guard at runner:1523. Live R38 grep reveals THREE isinstance guard locations:
- runner:1486 — `_is_list_sync = isinstance(_sp_raw_sync, list)`
- runner:1523 — `shots = sp if isinstance(sp, list) else sp.get("shots", [])` (the canonical T2-OR-18 guard)
- runner:4523 — `is_list = isinstance(sp_raw, list)`

All three are defense-in-depth. T2-OR-18 confirmed at multiple points in the pipeline. No issue — strengthened confidence in HEALTHY status for this organ.

---

## 7. PRIORITISED FIX LIST

Only CONFIRMED_BUG or CHRONIC/META-CHRONIC items:

| Priority | Issue | Class | Est. Time | Fix Type |
|----------|-------|-------|-----------|----------|
| P1 | OPEN-009: 4 video_url API-path prefix (27th report) | META-CHRONIC | ~2 min | Data patch (shot_plan.json, 4 fields) |
| P2 | OPEN-010: 4 ghost first_frame_url + regen 001_M02-M05 (24th report) | META-CHRONIC | ~15 min | Data patch + `--frames-only` run |
| P3 | OPEN-003: Add `[WIRE-B]` comment at runner:5717 | STALE_DOC | <1 min | 1-line code comment |
| P4 | OPEN-005: Fix runner line 24 + LTX guard message | STALE_DOC | ~2 min | 2-line docstring edit |

**NOT listed (correct omissions):**
- OPEN-002 (ARCHITECTURAL_DEBT — no quick fix, self-resolves on next gen)
- run_lock enforcer probe (OBSERVATION — non-blocking)
- Ledger staleness (PRODUCTION_GAP — self-resolves on generation)

---

## 8. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL = "kling" — runner:546 ✅ (live R38)
□ LTX_FAST = _LTXRetiredGuard() — runner:516 ✅ (live R38)
□ isinstance guard (T2-OR-18) — runner:1523 (also 1486, 4523) ✅ (live R38)
□ enrich_shots_with_arc imported — runner:65 ✅ (live R38)
□ enrich_shots_with_arc called — runner:4950 ✅ (live R38)
□ Wire-A hits — 6 ✅ (live R38)
□ Wire-C hits — 6 ✅ (live R38)
□ Wire-B _fail_sids — runner:5717 ✅ (live R38)
□ CPC decontaminate — 3 call sites (2391/2682/3264) ✅ (live R38)
□ Session enforcer → 64 PASS / 0 WARN / 0 BLOCK ✅ (live R38)
□ Learning log → 0 regressions (22 fixes) ✅ (live R38)
□ All 5 env keys PRESENT ✅ (live R38)
□ run_lock.py exists (2883 bytes, mtime 2026-03-31 08:31:38 EDT) ✅ (live R38)
□ session_enforcer.py mtime 2026-03-29 22:38:42 EDT (unchanged — run_lock not yet probed) ℹ️
□ orchestrator_server.py mtime 2026-03-30 15:43:25 EDT (stable, 2nd cycle noted) ℹ️
□ V37 governance refs — 31 in runner ✅ (live R38)
□ /api/v37 endpoints — 7 in orchestrator (enforcer-confirmed) ✅ (live R38)
□ pipeline_outputs/victorian_shadows_ep1/ — ABSENT 3rd consecutive session ⚠️ (UNVERIFIED_CARRY_FORWARD applied)
□ OPEN-009/OPEN-010 — UNVERIFIED_CARRY_FORWARD (policy met R38, last live: R35) ⚠️
```
*(ℹ️ = informational observation; ⚠️ = data gap or policy change — see Section 6)*

---

## 9. DOCUMENT LINEAGE

**Prior report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R37_KEEPUP_LATEST.md`
**This report:** `ATLAS_ERROR_DEEPDIVE_2026-03-31_R38_KEEPUP_LATEST.md`
**Run number delta:** R37 → R38 (+1)
**Open issues carried forward:** OPEN-002 (37th), OPEN-003 (37th), OPEN-005 (35th), OPEN-009 (27th — UNVERIFIED_CARRY_FORWARD), OPEN-010 (24th — UNVERIFIED_CARRY_FORWARD), PRODUCTION_GAP (18th — UNVERIFIED_CARRY_FORWARD)
**New issues added:** 0
**False positives retracted:** 0
**Consecutive idle generation cycles:** 19 (R20–R38)
**Consecutive sessions without pipeline_outputs access:** 3 (R36–R38) — POLICY THRESHOLD MET

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-31T17:10:26Z",
  "session_id": "youthful-brave-hamilton",
  "ledger_age_hours_estimate": 32.38,
  "ledger_verified_live": false,
  "pipeline_outputs_accessible": false,
  "consecutive_sessions_without_pipeline_outputs": 3,
  "unverified_carry_forward_applied": ["OPEN-009", "OPEN-010", "PRODUCTION_GAP", "ledger_data", "file_counts"],
  "runner_lines": 6218,
  "runner_mtime": "2026-03-31T08:32:39-04:00",
  "orchestrator_mtime": "2026-03-30T15:43:25-04:00",
  "session_enforcer_mtime": "2026-03-29T22:38:42-04:00",
  "run_lock_py_bytes": 2883,
  "run_lock_py_mtime": "2026-03-31T08:31:00-04:00",
  "code_changes_this_cycle": 0,
  "consecutive_cycles_no_code_change": 3,
  "session_enforcer_result": "SYSTEM_HEALTHY",
  "session_enforcer_pass": 64,
  "session_enforcer_warn": 0,
  "session_enforcer_block": 0,
  "learning_log_regressions": 0,
  "learning_log_fixes": 22,
  "wire_counts": {
    "wire_a": 6,
    "wire_c": 6,
    "wire_a_c_combined": 12,
    "wire_b_location": 5717
  },
  "isinstance_guard_locations": [1486, 1523, 4523],
  "cpc_call_sites": [2391, 2682, 3264],
  "v37_governance_refs_in_runner": 31,
  "v37_api_endpoints_in_orchestrator": 7,
  "proof_gate_files_found": 0,
  "chronic_issues": [
    {
      "id": "OPEN-009",
      "consecutive_reports": 27,
      "class": "META-CHRONIC",
      "verification_status": "UNVERIFIED_CARRY_FORWARD",
      "last_live_confirmation": "R35 (2026-03-31T13:11Z)",
      "proof_receipt": "pipeline_outputs absent 3rd consecutive session. Last live: R35 → ['008_E01','008_E02','008_E03','008_M03b'] have /api/media?path= in video_url. Self-heal probability: ~0%.",
      "fix_recipe": "video_url.replace('/api/media?path=', '') on 4 shots in shot_plan.json — ~2 min data patch",
      "regression_guard": ["first_frame_url untouched", "session_enforcer 64 PASS after patch"]
    },
    {
      "id": "OPEN-010",
      "consecutive_reports": 24,
      "class": "META-CHRONIC",
      "verification_status": "UNVERIFIED_CARRY_FORWARD",
      "last_live_confirmation": "R35 (2026-03-31T13:11Z)",
      "proof_receipt": "pipeline_outputs absent 3rd consecutive session. Last live: R35 → 001_M02/M03/M04/M05 first_frame_url missing from disk, all APPROVED.",
      "fix_recipe": "Set first_frame_url='' + _approval_status=AWAITING_APPROVAL on 4 shots, run --frames-only for scene 001",
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
  "new_module_probe_gap": {
    "module": "tools/run_lock.py",
    "in_runner": true,
    "in_session_enforcer": false,
    "impact": "LOW — non-blocking; enforcer HEALTHY without it"
  },
  "new_observation": "isinstance guard found at 3 locations (1486, 1523, 4523) — defense-in-depth, previously only 1523 cited",
  "data_verifiability_note": "pipeline_outputs absent R36/R37/R38 (3rd consecutive). OPEN-009/OPEN-010 confirmations formally UNVERIFIED_CARRY_FORWARD per R37 policy. Code checks fully live. If absent R39, recommend META-CHRONIC-ESCALATED status.",
  "recommended_next_action": "apply_data_patch_OPEN009_OPEN010",
  "recommended_secondary_action": "run_generation_victorian_shadows_001",
  "generation_idle_cycles": 19,
  "data_gap_cycles": 3
}
```
