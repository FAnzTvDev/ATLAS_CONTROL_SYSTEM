# ATLAS ERROR DEEPDIVE — 2026-03-30 R17 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T19:11:08Z
**Run number:** R17
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R16_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 10h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 13 PASS / 2 CONFIRMED_BUG / 1 META-CHRONIC 🔴 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 0 FALSE POSITIVES RETRACTED**

| Category | Count | Delta vs R16 | Status |
|----------|-------|-------------|--------|
| FALSE_POSITIVES RETRACTED | 0 | = same | None new |
| CONFIRMED_BUG | 2 | = same | OPEN-009 (6th) + OPEN-010 (3rd) |
| **META-CHRONIC** | **1** | **OPEN-004 → 🔴 META-CHRONIC (10th consecutive)** | **⛔ PROCESS FAILURE — ESCALATE** |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002) | 16th report |
| STALE_DOC | 2 | OPEN-003 (16th), OPEN-005 (14th) | Cosmetic |
| CONFIRMED_FIXED | 21 | = same | ✅ No regressions |
| CODE/DATA CHANGES SINCE R16 | 0 | = same | No new files modified (only .claude/settings.local.json) |

**Key findings R17:**

1. 🔴 **⛔ OPEN-004 IS NOW META-CHRONIC — 10 CONSECUTIVE REPORTS.** `decontaminate_prompt()` remains absent from `atlas_universal_runner.py` for the **10th straight hourly report**. This formally triggers the META-CHRONIC classification — a process-failure designation defined in the keep-up protocol. The fix recipe has been confirmed safe for 10 consecutive reports, is 6 lines, non-breaking, and has existed unchanged since R8. **Human intervention is mandatory. This issue has outlived every escalation path without resolution.**

2. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY.** 0 blocks. Vision backends: [gemini_vision, openrouter, florence_fal, heuristic]. Learning log: 22 fixes, 0 regressions. Identical to R16.

3. 🟡 **NO NEW GENERATION SINCE R16.** Ledger unchanged at 228 entries. Ledger now 10h21m stale (+60m from R16's 9h21m). Only file change since R16: `.claude/settings.local.json` (tool config, not production code). All production files (runner mtime: 2026-03-30T13:43:58Z) unchanged.

4. 🟡 **OPEN-009 PERSISTS (6th report).** 4 shots (008_E01/E02/E03/M03b) retain `/api/media?path=` prefix in both `video_url` AND `first_frame_url`. 8 total affected fields. Data patch still pending.

5. 🟡 **OPEN-010 PERSISTS (3rd report).** 001_M02/M03/M04/M05 retain ghost `first_frame_url` entries pointing to non-existent files, all APPROVED. Non-blocking for generation. Data patch pending.

6. 🔵 **ALL PRIOR CONFIRMED-FIXED (21 ITEMS) INTACT.** No regressions detected via learning log or manual verification.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R17) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes. Bare-list guard at runner:1492. 97/97 arc positions present. 62/62 M-shots with `_chain_group`. | `isinstance(sp, list)` guard at runner:1492 ✅; arc_position 97/97 |
| 🫀 Liver (prompt sanitizer) | 🔴 SICK | `decontaminate_prompt()` **META-CHRONIC: 10th report absent**. CPC detection fires (runner:~1141) but replacement not wired. runner:~1148 falls to `base = s.get("description","")` instead of calling `decontaminate_prompt()`. | `grep -c "decontaminate_prompt" atlas_universal_runner.py` → **0** |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 claim Seedance PRIMARY (STALE_DOC-14). Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:515). CLAUDE.md V36.5 accurate. | `sed -n '24p;39p'` → "Seedance v2.0 PRIMARY"; runner:515 → `"kling"` ✅ |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. Wire-A (runner:441,449,4507), Wire-C (12 combined A/B/C matches), Chain arc (runner:65+4719), all doctrine hooks wired. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available. BUT 87.8% heuristic I-scores. OPEN-010: 4 ghost first_frame_urls. OPEN-009: 4 API-path first_frame_urls. | Enforcer + env presence + ledger analysis |
| 🧠 Cortex (reward signal) | 🔴 DEGRADED | 228 entries (unchanged). 87.8% heuristic I=0.75 (latest-per-shot). 5 real-VLM shots. Last 5 ledger entries: 001_M01-M05, all I=0.75, V=0.5. 10h21m stale. | Ledger: 36/41 unique shots heuristic; distribution same as R16 |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 35 real first_frames on disk + 27 chain lastframe files (62 total JPGs). 24 real video_urls. Scene 006: 4/4 ✅. Scenes 005,007-013: 0 videos. OPEN-010: 001_M02-M05 ghost frames. run_report: success=True, errors=[]. | Coverage scan: same as R16 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic `_fail_sids` at runner:5470 ✅. No `[WIRE-B]` label (OPEN-003 cosmetic). 5 stitched scenes confirmed in stitched_scenes/ (scene_001_stitched, scene_002_stitched, scene_004_full_7shots, scene_006_stitched, scene_008_full_8shots). | `grep -n "_fail_sids" atlas_universal_runner.py` → runner:5470 ✅ |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C: 12 combined A/B/C matches. All Wire-C branches intact. | `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` → 12 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39) persist unchanged. CLAUDE.md V36.5 correct. No modifications since R16. | Same as R16 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

21 items total — unchanged from R16.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:485.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1492.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` at runner:4507.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4719.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:~1141.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — `[WIRE-C]` labels at runner (12 combined A/B/C matches confirmed R17).
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:515 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.

---

## 4. OPEN ISSUES

### ⛔ META-CHRONIC (10 consecutive reports: R8→R17): OPEN-004 — decontaminate_prompt absent from runner

**Issue:** `decontaminate_prompt()` not called in `atlas_universal_runner.py`. CPC detection fires (runner:~1141) but replacement call never wired. Detection logs a warning and falls back to `base = s.get("description", "")`. Generic-contaminated choreography silently converts to raw description fallback rather than being cleaned by CPC.

**META-CHRONIC ESCALATION STATUS:**
- This issue has been open for **10 consecutive hourly keep-up reports** (R8 through R17).
- It formally crosses the META-CHRONIC threshold defined in the keep-up protocol.
- The fix recipe has been confirmed safe and unchanged for 10 consecutive reports.
- Fix effort: **5 minutes, 6 lines, non-blocking, try/except wrapped**.
- This is a **process failure**: the fix exists, is proven safe, and has simply not been applied.
- **Recommended action: Human applies fix before R18. If OPEN-004 reaches R18 unfixed, escalate to system architect.**

**PROOF RECEIPT (R17 live):**
```
PROOF: grep -c "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: 0
CONFIRMS: Function not called in runner. (CPC module has it — not runner.)

PROOF: sed -n '1135,1152p' atlas_universal_runner.py
OUTPUT:
        base = action
        if not base:
            clean_choreo = _TIMESTAMP_PAT.sub("", s.get("_choreography", "")).replace("Then,", "").strip()
            if choreo_is_generic:
                base = s.get("description", "")
            elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
                import logging as _log
                _log.getLogger("atlas.runner").warning(
                    f"CPC-EMBED: shot {s.get('shot_id','?')} choreography is semantically "
                    f"generic (cosine > {_CPC_SIM_THRESHOLD}) — falling back to description"
                )
                base = s.get("description", "")
            else:
                base = clean_choreo
CONFIRMS: Both CPC-keyword and CPC-embedding branches fall to s.get("description","").
          decontaminate_prompt() would replace this with cleaned choreography.
          10th consecutive report confirms absence.
```

**Fix recipe (6 lines, non-breaking, try/except wrapper):**
```python
# At runner ~line 1146 (within the CPC-EMBED elif branch), replace:
#     base = s.get("description", "")
# with:
            try:
                from tools.creative_prompt_compiler import decontaminate_prompt as _dcp
                base = _dcp(clean_choreo, s.get("_emotional_state", ""))
            except Exception:
                base = s.get("description", "")  # Non-blocking fallback
# ALSO replace the same pattern in the choreo_is_generic branch above it (~line 1140):
#     base = s.get("description", "")
# with the same try/except block.
```

**Regression guard:** After fix, verify runner syntax OK (`python3 -c "import ast; ast.parse(open('atlas_universal_runner.py').read()); print('OK')"`). Run scene 013 `--frames-only` on 1 shot. Verify prompt no longer contains GENERIC_PATTERNS. Verify scenes 001-008 prompt structure unchanged.

**Classification:** META-CHRONIC (10 consecutive). PROCESS FAILURE. Fix recipe confirmed safe for 10 reports.

---

### OPEN-009 (CONFIRMED_BUG — R12→R17, Non-blocking, 6th consecutive report)

**Issue:** 4 shots (008_E01/E02/E03/M03b) have `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. 8 total affected fields. Files exist at raw paths. Stitch risk for scene 008.

**PROOF RECEIPT (R17 live):**
```
PROOF: python3 shot_plan API-path scan
OUTPUT:
  API_PATH_VIDEO_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
  API_PATH_FIRST_FRAME_URL: 4 shots: ['008_E01', '008_E02', '008_E03', '008_M03b']
CONFIRMS: Identical to R16. 8 total affected fields persist. No change.
```

**Impact:** Stitch risk for scene 008 (4 videos excluded from stitch via os.path.exists). 008_M03b also carries `REGEN_REQUESTED`. UI correctly resolves API-path format in browser.

**Fix recipe (data patch only):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   Strip "/api/media?path=" prefix from both video_url and first_frame_url
# Total: 8 field changes, no code changes required
```

**Classification:** CONFIRMED_BUG (data inconsistency). Non-blocking for generation. Stitch risk for scene 008.

---

### OPEN-010 (CONFIRMED_BUG — R15→R17, Non-blocking, 3rd consecutive report)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` set pointing to files that **do not exist on disk**. All 4 carry `_approval_status=APPROVED`.

**PROOF RECEIPT (R17 live):**
```
PROOF: python3 os.path.exists check for first_frame_url fields
OUTPUT:
  GHOST_FIRST_FRAME_URLS (missing file): 4
    001_M02: pipeline_outputs/.../first_frames/001_M02.jpg  approval=APPROVED
    001_M03: pipeline_outputs/.../first_frames/001_M03.jpg  approval=APPROVED
    001_M04: pipeline_outputs/.../first_frames/001_M04.jpg  approval=APPROVED
    001_M05: pipeline_outputs/.../first_frames/001_M05.jpg  approval=APPROVED
CONFIRMS: Same as R16. 4 ghost entries with APPROVED status persist.
```

**Why non-blocking:** `--videos-only` scans disk directly — only 001_M01.jpg exists, chain proceeds from M01 anchor. Functionally correct. UI shows broken thumbnails for 001_M02-M05.

**Fix recipe (data patch + re-generation):**
```python
# 1. In shot_plan.json: for 001_M02/M03/M04/M05:
#    Set first_frame_url = ""
#    Set _approval_status = "AWAITING_APPROVAL"
# 2. Run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# 3. Review M02-M05 in UI filmstrip → thumbs-up → then --videos-only
```

**Classification:** CONFIRMED_BUG (data integrity — ghost frame references). Non-blocking for generation.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 16th consecutive report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot). Unchanged.

**PROOF RECEIPT (R17 live):**
```
PROOF: ledger I-score distribution analysis
OUTPUT:
  TOTAL_ENTRIES: 228 (unchanged)
  UNIQUE_SHOTS: 41
  HEURISTIC_I (I=0.75): 36/41 = 87.8%
  REAL_VLM (I!=0.75): 5/41
  REAL_VLM_SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LEDGER_AGE: 10h21m
CONFIRMS: No new generation. Identical to R16 distribution.
```

**Classification:** ARCHITECTURAL_DEBT (16th report). Pattern resolves in next generation run if Gemini/OpenRouter fires. Defer to next run.

---

### OPEN-003 (STALE_DOC — 16th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5470. Logic functional (`_fail_sids` at runner:5470 ✅).

**PROOF (R17):**
```
PROOF: grep -c "WIRE-B" atlas_universal_runner.py → 0
       grep -n "_fail_sids" atlas_universal_runner.py → runner:5470 ✅
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5470.

**Classification:** STALE_DOC. 16th consecutive report. Logic functional. Cosmetic only.

---

### OPEN-005 (STALE_DOC — 14th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY. Code default is Kling (runner:515).

**PROOF (R17):**
```
PROOF: sed -n '24p;39p' atlas_universal_runner.py
OUTPUT line 24: "...ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
OUTPUT line 39: "All shots PRIMARY → Seedance v2.0 via muapi.ai..."
PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:515 ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") ✅
```

**Classification:** STALE_DOC. 14th consecutive report. Code behavior correct.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 21 confirmed-fixed items remain intact. No new reclassifications.

---

## 6. NEW OBSERVATIONS (R17 only)

### 6.1 No Production Code or Data Changes Since R16

```
PROOF: find ATLAS_CONTROL_SYSTEM -newer R16_report.md \( -name "*.py" -o -name "*.json" \)
OUTPUT: /sessions/.../ATLAS_CONTROL_SYSTEM/.claude/settings.local.json (tool config only)
CONFIRMS: Zero production code or data changes since R16. Runner mtime: 2026-03-30T13:43:58Z
          (same as R16). System remains fully idle since 08:47 UTC run.
```

### 6.2 META-CHRONIC Threshold Formally Crossed by OPEN-004

Under the keep-up protocol: "META-CHRONIC = 10+ consecutive reports, fix loop has failed."
OPEN-004 has now been present for exactly 10 consecutive reports (R8 through R17). The escalation path is:
- R8: First reported (CHRONIC-1)
- R16: CHRONIC-9, "one report from META-CHRONIC"
- **R17: META-CHRONIC. Process failure classification. Requires human acknowledgment before R18.**

The fix recipe is defined, safe, and minimal. The issue is purely organizational — no technical blocker exists.

### 6.3 Scene Coverage Unchanged (identical to R16)

```
Scene 006: 4/4 (100%) ✅ — only complete scene
Scene 001: 3/8 (37%) — E01,E02,E03 only
Scene 002: 5/7 (71%)
Scene 003: 3/9 (33%)
Scene 004: 5/7 (71%)
Scene 008: 4/8 (50%) — all 4 have API-path format (OPEN-009)
Scenes 005,007,009-013: 0 videos
```

### 6.4 videos_kling_lite/ Note (R17 clarification)

The directory contains 62 total files: 30 MP4s + 32 supporting files (JPGs, TXT, JSON). `wc -l` on `ls` output counted all files. The R16 "62 total" was corrected this session — 30 MP4s confirmed via `ls *.mp4 | wc -l`. No change.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **⛔ P0** | **OPEN-004 (META-CHRONIC: CPC decontamination missing)** | **5 min** | 6-line try/except at runner:~1146,~1140 — replace 2 `base = s.get("description","")` fallbacks with `decontaminate_prompt(clean_choreo, ...)` | NO — but process failure at R18 if unresolved |
| **P1** | OPEN-009/010 combined data patch | 3 min | Strip API-path prefix from 8 fields; clear ghost first_frame_url + reset approval for 001_M02-M05 | NO — stitch risk + UI artifacts only |
| **P3** | OPEN-002 (reward signal) | 0 min code | Run generation — vision_judge will fire. Issue resolves itself with production use | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5470 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**OPEN-004 upgraded from P1 to ⛔ P0** due to META-CHRONIC formal escalation.

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed: 0 blocks R17)
□ ⛔ URGENT: Apply OPEN-004 fix: 6-line try/except at runner:~1140,~1146 calling decontaminate_prompt()
□ Apply OPEN-009/010 combined patch: normalize 8 API-path fields + clear 4 ghost first_frame_urls + reset APPROVED→AWAITING_APPROVAL for 001_M02-M05
□ After clearing 001_M02-M05 first_frame_url, run --frames-only scene 001 to re-generate M02-M05
□ Review and re-approve 001_M02-M05 frames in UI
□ Verify vision backends online: gemini_vision + openrouter (confirmed R17)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real VLM scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (0/97 CIG blocks confirmed R17)
□ Verify decontaminate_prompt fix: run scene 013 --frames-only, check prompt for generic patterns
```

---

## 9. DELTA FROM R16

| Signal | R16 | R17 | Delta | Note |
|--------|-----|-----|-------|------|
| FALSE_POSITIVES_RETRACTED | 0 new | 0 new | = | None |
| CONFIRMED_FIXED | 21 | 21 | = | All intact |
| P0 blockers | 0 | **1** | **+1** | **OPEN-004 → META-CHRONIC = P0** |
| Files modified since prior | 0 | 0 prod | = | Only .claude/settings.local.json |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 9h21m | 10h21m | +60m | Idle |
| API-path video_url | 4 (OPEN-009) | 4 | = | Persists |
| API-path first_frame_url | 4 (OPEN-009) | 4 | = | Persists |
| Ghost first_frame_url | 4 (OPEN-010) | 4 | = | Persists |
| REGEN_REQUESTED shots | 2 | 2 | = | 008_M03b + 008_M04 |
| **OPEN-004 consecutive** | 9 (CHRONIC-9) | **10 (META-CHRONIC)** | **+1** | **⛔ PROCESS FAILURE** |
| OPEN-003 consecutive | 15 | 16 | +1 | Cosmetic |
| OPEN-005 consecutive | 13 | 14 | +1 | Cosmetic |
| OPEN-002 consecutive | 15 | 16 | +1 | Architectural debt |
| OPEN-009 consecutive | 5 | 6 | +1 | Data patch pending |
| OPEN-010 consecutive | 2 | 3 | +1 | Data patch pending |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score | 87.8% | 87.8% | = | No new run |
| Scenes 100% video | 1 (006) | 1 (006) | = | |
| First_frames on disk | 62 total / 35 actual FF | 62 total / 35 actual FF | = | |
| Valid first_frames in plan | 35 | 35 | = | 39 - 4 ghost |
| Shot plan total | 97 | 97 | = | |
| Videos in kling_lite | 30 MP4s | 30 MP4s | = | + 32 supporting files |
| Learning log fixes | 22 | 22 | = | 0 regressions |
| Arc positions present | 97/97 | 97/97 | = | |

**R17 summary: OPEN-004 crosses META-CHRONIC threshold (10 consecutive reports). All other findings identical to R16. No new bugs. No new fixes. System idle. P0 count increases from 0 to 1 — process failure designation for unresolved OPEN-004.**

---

## 10. GENERATION READINESS ASSESSMENT (R17)

**Recommended next generation sequence (after fixes):**

```bash
# ⛔ Step 0 (MANDATORY): Apply OPEN-004 decontaminate_prompt fix
# [Human applies 6-line fix at runner:~1140 and ~1146]

# Step 1: Apply data patches (OPEN-009/010)
# [Human applies JSON patches to shot_plan.json]

# Step 2: Re-generate missing 001 M-shots first frames
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only

# Step 3: Generate all pending M-shot videos
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only

# Step 4: Address 008_M03b and 008_M04 regen
# → 008_M04 has real video; operator can review + re-approve if satisfied
# → 008_M03b needs API-path patch first, then regen
```

**Current blockers:**
- ⛔ OPEN-004 (META-CHRONIC): Apply decontaminate_prompt fix before generating scenes 009-013
- ⚠️ OPEN-010: Clear 001_M02-M05 ghost first_frame_url + re-generate frames before --videos-only
- ⚠️ OPEN-009: Patch scene 008 video/frame URLs before stitch
- ✅ CIG gate: 0/97 shots blocked
- ✅ Session enforcer: HEALTHY
- ✅ Vision backends: online (4 backends confirmed)

---

## 11. DOCUMENT LINEAGE

- R1-R7: Hourly incremental baseline and consolidation
- R8: OPEN-004 first reported; OPEN-008 first reported (later retracted R13)
- R9-R12: OPEN-008 persisted as P0 (false positive throughout)
- R13: OPEN-008 + OPEN-006 retracted. System cleared of all P0 blockers.
- R14: OPEN-004 advances to CHRONIC-7. No new bugs.
- R15: OPEN-010 NEW. OPEN-009 expanded. OPEN-004 → CHRONIC-8.
- R16: No new bugs. OPEN-004 → CHRONIC-9 ⚠️ (META-CHRONIC at R17). P1 priority upgrade.
- **R17 (CURRENT):** No new bugs. No new fixes. **OPEN-004 → META-CHRONIC (10 consecutive). P0 upgrade. Process failure designation. P0 count: 0→1. Human fix mandatory before R18.**

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T19:11:08Z",
  "run_number": 17,
  "prior_report": "R16",
  "system_version": "V36.5",
  "ledger_age_minutes": 621,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 21,
    "confirmed_bug": 2,
    "meta_chronic": 1,
    "architectural_debt": 1,
    "stale_doc": 2,
    "false_positives_retracted": 0,
    "p0_blockers": 1
  },
  "key_signals": {
    "code_files_modified_since_r16": 0,
    "data_files_modified_since_r16": 0,
    "cig_gate_blocked_shots": 0,
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "api_path_first_frame_urls": 4,
    "ghost_first_frame_urls_missing_file": 4,
    "total_ghost_fields": 12,
    "regen_requested_shots": 2,
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "ledger_age_minutes": 621,
    "shots_with_video_url_in_plan": 28,
    "real_video_urls_excluding_api_path": 24,
    "first_frame_jpgs_on_disk_total": 62,
    "first_frame_jpgs_actual_shot_frames": 35,
    "first_frame_jpgs_chain_lastframe_files": 27,
    "shots_with_first_frame_url_in_plan": 39,
    "shots_with_valid_first_frame_url": 35,
    "mp4_files_videos_kling_lite": 30,
    "mp4_files_videos_dir": 0,
    "scenes_with_100pct_video": 1,
    "p0_blockers": 1,
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13,
    "run_report_success": true,
    "learning_log_fixes": 22,
    "learning_log_regressions": 0,
    "arc_positions_present": 97,
    "chain_groups_present": 62,
    "approval_status": {
      "APPROVED": 29,
      "AUTO_APPROVED": 6,
      "AWAITING_APPROVAL": 2,
      "REGEN_REQUESTED": 2,
      "empty": 58
    }
  },
  "false_positives_retracted": [],
  "open_issues": [
    {
      "id": "OPEN-004",
      "classification": "META-CHRONIC",
      "severity": "P0",
      "blocking": false,
      "consecutive_reports": 10,
      "meta_chronic": true,
      "process_failure": true,
      "fix_effort_minutes": 5,
      "fix_recipe": "6-line try/except at runner:~1140 and ~1146 replacing two 'base = s.get(description)' fallbacks with decontaminate_prompt(clean_choreo, ...)",
      "human_action_required": true,
      "escalate_if_unfixed_at": "R18"
    },
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 6,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "affected_fields": ["video_url", "first_frame_url"],
      "total_affected_fields": 8
    },
    {
      "id": "OPEN-010",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 3,
      "affected_shots": ["001_M02", "001_M03", "001_M04", "001_M05"],
      "description": "first_frame_url set but file missing. APPROVED status. Non-blocking for --videos-only."
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "consecutive_reports": 16
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 16
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 14
    }
  ],
  "generation_readiness": {
    "scenes_ready_for_video_after_patch": ["001", "002", "003", "004"],
    "scenes_need_frames_first": ["005", "007", "009", "010", "011", "012", "013"],
    "gate_blocking_any_scene": false,
    "pre_condition_001": "Clear OPEN-010 ghost first_frame_urls + re-run --frames-only 001 + re-approve M02-M05",
    "recommended_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only",
    "recommended_pre_fix": "MANDATORY: Apply OPEN-004 decontaminate_prompt fix before any generation"
  },
  "recommended_next_action": "HUMAN_FIX_OPEN004_NOW_then_p1_patches_then_frames_only_001_then_videos_only_001_004"
}
```

---

**END REPORT**

*ATLAS R17 — Keep-up detection complete. ⛔ META-CHRONIC ESCALATION: OPEN-004 (`decontaminate_prompt` absent from runner) has reached 10 consecutive reports — formal process-failure classification. All other signals identical to R16: no new bugs, no new fixes, no code/data changes. Ledger 10h21m stale — system idle. P0 count: 0→1. Session enforcer HEALTHY. 2 P1 data patches pending (OPEN-009/010). Human fix of OPEN-004 is mandatory before R18.*
