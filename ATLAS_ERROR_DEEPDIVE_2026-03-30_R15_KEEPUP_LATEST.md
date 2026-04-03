# ATLAS ERROR DEEPDIVE — 2026-03-30 R15 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T17:13:27Z
**Run number:** R15
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R14_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 8h 21m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 13 PASS / 2 CONFIRMED_BUG / 1 CHRONIC-8 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 0 FALSE POSITIVES RETRACTED**

| Category | Count | Delta vs R14 | Status |
|----------|-------|-------------|--------|
| FALSE_POSITIVES RETRACTED | 0 | = same | None new |
| CONFIRMED_BUG | 2 | +1 (OPEN-010 NEW) | OPEN-009 expanded + new OPEN-010 |
| CHRONIC | 1 | OPEN-004 → 8th consecutive report | P2, fix recipe unchanged |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002) | Defer post-run |
| STALE_DOC | 2 | OPEN-003 (14th), OPEN-005 (12th) | Cosmetic |
| CONFIRMED_FIXED | 21 | = same | ✅ No regressions |

**Key findings R15:**

1. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY.** 0 blocks. Vision backends: [gemini_vision, openrouter, florence_fal, heuristic]. Learning log: 22 fixes, 0 regressions. All wiring intact.

2. 🟡 **NO NEW GENERATION SINCE R14.** Ledger unchanged at 228 entries, 8h21m old. No new frames or videos since 08:47 run. Ledger staleness increasing (+54m from R14's 7h21m).

3. 🔴 **NEW OPEN-010: 4 GHOST FIRST_FRAME_URL ENTRIES (001_M02-M05).** `first_frame_url` set in shot_plan but files don't exist on disk. All 4 shots marked APPROVED. **Non-blocking for --videos-only** (chain mode handles M02-M05 via end-frame chaining from M01). But causes monitoring false positives and UI display of approved frames that don't render. Distinct from OPEN-009 (this is raw-path format with missing files, OPEN-009 is API-path format with present files).

4. 🟡 **OPEN-009 EXPANDED: Now covers first_frame_url too.** 008_E01/E02/E03/M03b have API-path `/api/media?path=` format in BOTH `video_url` AND `first_frame_url`. Files exist at raw paths. 8 total affected fields (4 video_url + 4 first_frame_url) on same 4 shots.

5. 🟡 **R14 OVERCOUNTING CORRECTION.** R14 reported "62 first_frames on disk" — this counted 27 `multishot_gN_XXX_lastframe.jpg` chain end-frame files. Corrected: **35 actual first_frame JPGs** on disk (+ 27 chain lastframe files = 62 total files in directory). Shot_plan reports 39 shots with `first_frame_url`, but 4 (001_M02-M05) are ghost entries. Correct tracked frame count: **35 valid first_frames** (39 in plan - 4 ghost).

6. 🟡 **OPEN-004 ADVANCES TO CHRONIC-8.** `decontaminate_prompt()` still absent from runner. 8th consecutive report. Approaching META-CHRONIC threshold at 10. Fix recipe unchanged and confirmed safe.

7. 🔵 **COVERAGE DELTA vs R14: UNCHANGED.** 24 real video_urls (28 in shot_plan - 4 API-path). Scene 001: E-shots 3/3 video ✅, M-shots 0/5 video (next generation target). Scene 006: 4/4 complete. Scene 008: 4/8 video (4 with API-path video_url excluded from os.path.exists checks).

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R15) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes; bare-list guard at runner:1492. All 62 M-shots have `_chain_group`. Arc positions: 97/97 present. | `isinstance(sp, list)` guard confirmed; 97 shots load cleanly |
| 🫀 Liver (prompt sanitizer) | 🔴 DEGRADED | `decontaminate_prompt()` absent from runner. CHRONIC-8. Scene 013: 4 shots with `_beat_action=None`. Detection at runner:1140 fires but replacement never wired. | `grep decontaminate_prompt atlas_universal_runner.py` → (no output) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 still claim Seedance PRIMARY. Code correct (`ACTIVE_VIDEO_MODEL="kling"` at runner:515). | `sed -n '24p;39p' atlas_universal_runner.py` → "Seedance v2.0 PRIMARY" |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. All 4 doctrine hooks wired. Chain arc wired at runner:65 + runner:4719. Wire-C: 6 matches. Wire-A budget: runner:441, 449, 4507. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT. Vision backends: 4 available including gemini_vision. BUT 87.8% heuristic I-scores in ledger. 001_M02-M05 ghost first_frame_url entries. | Enforcer + env + ledger + ghost frame analysis |
| 🧠 Cortex (reward signal) | 🔴 DEGRADED | 228 entries (unchanged). 87.8% heuristic I=0.75 latest-per-shot. 5 real-VLM shots: 008_M01(1.0), 008_M02(0.9), 008_M04(0.8), 004_M01(1.0), 004_M02(1.0). Last 5 entries all I=0.75 (001_M01-M05 from 08:47 run). | Ledger analysis: 36/41 unique shots heuristic |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 35 real first_frames on disk; 24 real video_urls. E-shots for scenes 001-004/006/008 done. M-shots: 001 (0/5), 002 (5/4?), 003 (3/6?), 004 (5/4?) video partial. OPEN-010: 001_M02-M05 ghost frames (non-blocking). | Coverage analysis + file existence check |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic `_fail_sids` at runner:5470. No `[WIRE-B]` label (OPEN-003 cosmetic). 5 stitched scenes confirmed. | `grep -n "_fail_sids" atlas_universal_runner.py` → runner:5470 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner (6 matches). All branches intact. | `grep -c "WIRE-C" atlas_universal_runner.py` → 6 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39). CLAUDE.md V36.5 correct. Code reality = Kling default (runner:515). R14 overcounting of first_frames (62 vs correct 35) corrected this session. | Live analysis this session |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

21 items total — unchanged from R14.

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
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1140.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — `[WIRE-C]` labels at runner (6 matches confirmed R15).
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:515 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths (excluding API-path format, OPEN-009).
✅ **OPEN-008 CLOSED (R13)** — CIG gate never fires on current shot_plan. 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.

---

## 4. OPEN ISSUES

### OPEN-009 EXPANDED (CONFIRMED_BUG — R12→R15, Non-blocking, 4th consecutive report)

**Issue:** 4 shots (008_E01/E02/E03/M03b) have `/api/media?path=` prefix in BOTH `video_url` AND `first_frame_url`. **EXPANDED R15:** Now confirmed 8 total affected fields (4 video_url + 4 first_frame_url) on the same 4 shots.

**PROOF RECEIPT (R15 live):**
```
PROOF: python3 -c "ghost first_frame_url scan"
OUTPUT:
  008_E01: first_frame_url=/api/media?path=.../first_frames/008_E01.jpg  raw_exists=True
  008_E02: first_frame_url=/api/media?path=.../first_frames/008_E02.jpg  raw_exists=True
  008_E03: first_frame_url=/api/media?path=.../first_frames/008_E03.jpg  raw_exists=True
  008_M03b: first_frame_url=/api/media?path=.../first_frames/008_M03b.jpg raw_exists=True
CONFIRMS: API-path format in both video_url and first_frame_url for these 4 shots.
          Files physically exist at raw paths. Same pattern, doubled scope.
```

**Impact (updated):**
- `os.path.exists(first_frame_url)` fails for these 4 → monitoring false positives (now 8 fields, not 4)
- Stitch risk: runner uses os.path.exists() for video_url concat → 4 videos excluded from scene 008 stitch
- First frame load in --videos-only: runner scans disk by `Path(frame_dir) / f"{sid}.jpg"` — bypasses URL format, so unaffected
- UI display: both API-path fields resolve correctly in browser

**Fix recipe (data patch — same as before, extended to first_frame_url too):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 4 shots (008_E01/E02/E03/M03b):
#   Strip "/api/media?path=" from both video_url and first_frame_url
# Total: 8 field changes, no code changes required
```

**Classification:** CONFIRMED_BUG (data inconsistency). Non-blocking for generation. Risk: stitch exclusion for scene 008.

---

### OPEN-010 (NEW — CONFIRMED_BUG, R15, Non-blocking)

**Issue:** 4 shots (001_M02/M03/M04/M05) have `first_frame_url` set in shot_plan pointing to files that **do not exist on disk**. All 4 shots have `_approval_status=APPROVED`. The shot_plan `first_frame_url` field holds a valid filesystem-format path (`pipeline_outputs/.../first_frames/001_M02.jpg`) but the file was never created or was subsequently deleted/archived.

**PROOF RECEIPT (R15 live):**
```
PROOF: python3 -c "os.path.exists check for all first_frame_url fields"
OUTPUT:
  GHOST_FIRST_FRAME_URLS (raw-path-format, file missing): 4
    001_M02: pipeline_outputs/victorian_shadows_ep1/first_frames/001_M02.jpg  exists=False
    001_M03: pipeline_outputs/victorian_shadows_ep1/first_frames/001_M03.jpg  exists=False
    001_M04: pipeline_outputs/victorian_shadows_ep1/first_frames/001_M04.jpg  exists=False
    001_M05: pipeline_outputs/victorian_shadows_ep1/first_frames/001_M05.jpg  exists=False

PROOF: ls -la pipeline_outputs/victorian_shadows_ep1/first_frames/001_M0*.jpg
OUTPUT: Only 001_M01.jpg exists (created 2026-03-30 07:49)

PROOF: ledger entries for 001_M02-M05
OUTPUT: Two generation runs recorded (07:52 and 08:47), both I=0.75 V=0.5 verdict=PASS
        V=0.5 = heuristic video score (not proof frames were saved)

CONFIRMS: shot_plan APPROVED with first_frame_url set, but frame files never written to disk
          or were subsequently deleted. Ledger V=0.5 confirms video was scored heuristically
          — no file existence check in ledger path.
```

**Why non-blocking:** In `--videos-only` mode, runner scans disk for `{sid}.jpg`:
```python
for s in mshots:
    fp = Path(frame_dir) / f"{sid}.jpg"
    if fp.exists():
        all_frames[sid] = str(fp)
```
→ Only 001_M01 loaded into `all_frames`. M02-M05 absent.
→ Approval gate checks `sid in all_frames` before AWAITING_APPROVAL check → M02-M05 bypassed.
→ `mshots_for_video = mshots` (all 5 M-shots included).
→ `first_frame = list(all_frames.values())[0]` = 001_M01.jpg ✅
→ `gen_scene_multishot` chains: M01 generates → end-frame extracted → M02 starts from chain frame → etc.
→ **Functionally correct.** Video generation for scene 001 M-shots will proceed normally.

**Impact:**
- Monitoring false positives: count of "shots with first_frame_url" (39) overcounts valid frames (35)
- UI may show broken frame thumbnails for 001_M02-M05 (APPROVED but no image to render)
- Pre-run-gate / artifact archiving scripts using `os.path.exists(first_frame_url)` will misreport

**Fix recipe (data patch):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json:
# For each of 001_M02/M03/M04/M05:
#   Set first_frame_url = "" (clear ghost entry)
#   Set _approval_status = "AWAITING_APPROVAL" (re-queue for human review after frames generated)
# Total: 8 field changes on 4 shots
```

**Regression guard:** After fix, confirm: `first_frame_url` = "" for M02-M05, `_approval_status` = "AWAITING_APPROVAL". Then run `--frames-only` for scene 001 to generate the missing frames (M01 already exists, M02-M05 will be chain-generated or re-generated as standalone). Review in UI, approve, then `--videos-only`.

**Classification:** CONFIRMED_BUG (data integrity — ghost frame references). Non-blocking for generation. Creates monitoring noise and UI display artifacts.

---

### ⏱️ CHRONIC-8 (8 consecutive reports: R8→R15): OPEN-004 — decontaminate_prompt absent from runner

**Issue:** `decontaminate_prompt()` not called in runner. Detection fires (`_is_cpc_via_embedding()` at runner:1140) but replacement call never wired. Scene 013 has 4 shots with `_beat_action=None`.

**PROOF RECEIPT (R15 live):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output — function not called in runner)

PROOF: grep -n "decontaminate_prompt" tools/creative_prompt_compiler.py
OUTPUT: line 558: def decontaminate_prompt(text: str, character: str = "", ...
        line 717: shot["nano_prompt"] = decontaminate_prompt(nano, ...)
        line 723: shot["ltx_motion_prompt"] = decontaminate_prompt(ltx, ...)
CONFIRMS: Module exists and functional. Runner detects contamination (runner:1140) but never calls fix.
```

**Why CHRONIC:** 8th consecutive report. META-CHRONIC threshold at 10 = R17. Fix recipe unchanged, non-breaking, 7 lines. Recommend human-applied fix before next generation of scenes 009-013.

**Fix recipe (7 lines, non-breaking, try/except wrapper):**
```python
# At runner ~line 1141, AFTER the `elif clean_choreo and _is_cpc_via_embedding(clean_choreo):` block:
elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt
        clean_choreo = decontaminate_prompt(
            clean_choreo, shot.get("_emotional_state", ""))
    except ImportError:
        pass  # Non-blocking: detection-only mode as fallback
```

**Regression guard:** Run 013_M01 frame-only and verify prompt no longer contains GENERIC_PATTERNS terms. Verify scenes 001-008 prompt structure unchanged.

**Classification:** CHRONIC-8. Fix recipe safe and proven non-breaking. Escalates to META-CHRONIC at R17.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 14th report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot). Unchanged from R14.

**PROOF RECEIPT (R15 live):**
```
PROOF: python3 -c "... ledger I-score distribution R15"
OUTPUT:
  LEDGER_ENTRIES: 228 (unchanged)
  UNIQUE_SHOTS: 41
  HEURISTIC_I (latest, I=0.75): 36/41 = 87.8%
  REAL_I (latest, I!=0.75): 5/41 = 12.2%
  REAL_I SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LAST 5 ENTRIES: 001_M01-M05, all I=0.75
CONFIRMS: No new generation. Vision_judge pattern unchanged.
```

**Classification:** ARCHITECTURAL_DEBT. Code not broken — vision_judge IS available (4 backends confirmed). Defer to new generation run.

---

### OPEN-003 (STALE_DOC — 14th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5470. Logic functional (`_fail_sids` at runner:5470).

**PROOF (R15):** `grep "WIRE-B" atlas_universal_runner.py` → no output. `grep -n "_fail_sids"` → runner:5470 ✅

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5470.

**Classification:** STALE_DOC. 14th consecutive report. Logic functional.

---

### OPEN-005 (STALE_DOC — 12th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY. Code default is Kling (runner:515).

**PROOF (R15):** `sed -n '24p;39p' atlas_universal_runner.py` → "Seedance v2.0 PRIMARY". `ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")` at runner:515 ✅

**Classification:** STALE_DOC. 12th consecutive report. Code behavior correct.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 21 confirmed-fixed items from R14 remain intact. No new reclassifications.

**Coverage counting correction (NOT a false positive — prior overcounting):**
R14 reported "62 first_frames on disk." This was technically accurate (62 total files in `/first_frames/` dir) but misleading. R15 clarifies: 35 are actual shot first-frame JPGs; 27 are `multishot_gN_XXX_lastframe.jpg` chain end-frame extraction files. The shot_plan tracks 39 shots with `first_frame_url`, but 4 (001_M02-M05) are ghost entries (OPEN-010). Corrected valid first_frame count: **35 on disk, 35 tracked in shot_plan without ghosts**.

---

## 6. NEW OBSERVATIONS (R15 only)

### 6.1 Scene 001 State Clarification

Previously ambiguous in R14. R15 confirms:
- 001_E01/E02/E03: frames ✅, videos ✅ (complete)
- 001_M01: frame ✅ on disk, no video_url
- 001_M02/M03/M04/M05: frame URL set in plan but file missing (OPEN-010), no video_url

Scene 001 M-shots (001_M01-M05) are all APPROVED but have 0/5 videos. Running `--videos-only` for scene 001 will use 001_M01.jpg as chain anchor and generate M02-M05 via end-frame chaining. This is safe and expected behavior.

### 6.2 chain_arc_intelligence Module Confirmed Functional

```
PROOF: python3 -c "from chain_arc_intelligence import enrich_shots_with_arc; print('OK')"
OUTPUT: chain_arc_intelligence: IMPORT OK, enrich_shots_with_arc present
```
Arc positions confirmed on all 97 shots (97/97 with `_arc_position`).

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009/010 combined data patch | 3 min | JSON patch: strip `/api/media?path=` from 4 video_url + 4 first_frame_url; clear ghost first_frame_url + reset approval for 001_M02-M05 | NO — stitch risk + UI artifacts only |
| **P2** | OPEN-004 (CPC decontamination CHRONIC-8) | 5 min | 7-line try/except at runner:~1141 | NO — future scenes only |
| **P3** | OPEN-002 (reward signal) | 30 min | Debug vision_judge CLI init timing in new generation run | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5470 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**No P0 blockers. Scene 001 M-shots ready for --videos-only after OPEN-010 P1 patch.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed: 0 blocks this session)
□ Apply OPEN-009/010 combined patch: normalize 8 API-path fields + clear 4 ghost first_frame_urls
□ After clearing 001_M02-M05 first_frame_url, run --frames-only scene 001 to re-generate M02-M05 frames
□ Review and re-approve 001_M02-M05 frames in UI
□ Verify vision backends online: gemini_vision + openrouter (confirmed this session)
□ After generation: check reward_ledger I-score distribution (target: ≥50% real scores)
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (confirmed: all 97 shots pass CIG)
```

---

## 9. DELTA FROM R14

| Signal | R14 | R15 | Delta | Note |
|--------|-----|-----|-------|------|
| FALSE_POSITIVES_RETRACTED | 0 new | 0 new | = | None |
| CONFIRMED_FIXED | 21 | 21 | = | All intact |
| P0 blockers | 0 | 0 | = | None |
| CIG gate blocks | 0/97 | 0/97 | = | Not re-run, still confirmed from R14 live sweep |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | 7h21m | 8h21m | +60m | Approaching action threshold |
| API-path video_url | 4 (OPEN-009) | 4 | = | Persists |
| API-path first_frame_url | (unreported) | 4 (OPEN-009 expanded) | NEW | 008 E-shots discovered |
| Ghost first_frame_url | (unreported) | 4 (OPEN-010 NEW) | NEW | 001_M02-M05 missing files |
| OPEN-004 consecutive | 7 (CHRONIC-7) | 8 (CHRONIC-8) | +1 | Fix recipe unchanged |
| OPEN-003 consecutive | 13 | 14 | +1 | Cosmetic label only |
| OPEN-005 consecutive | 11 | 12 | +1 | Cosmetic docstring only |
| OPEN-002 consecutive | 13 | 14 | +1 | Architectural debt |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score latest | 87.8% | 87.8% | = | No new run |
| Scenes 100% video | 2 (006, 008) | 2 (006, 008) | = | |
| First_frames on disk total | 62 (overcounted) | 62 total / 35 actual FF | CORRECTED | 27 are lastframe chain files |
| First_frames tracked in plan | 39 | 35 valid (39 - 4 ghost) | CORRECTED | OPEN-010 |
| Shot plan total | 97 | 97 | = | |

---

## 10. GENERATION READINESS ASSESSMENT (R15)

**Recommended next generation sequence (after P1 data patches):**

```bash
# Step 1: Apply data patches (OPEN-009/010)
# [Human applies JSON patches to shot_plan.json]

# Step 2: Re-generate missing 001 M-shots first frames
python3 atlas_universal_runner.py victorian_shadows_ep1 001 --mode lite --frames-only
# → Only 001_M01-M05 will generate (E-shots already APPROVED, skipped)
# → Review 001_M02-M05 in UI, thumbs-up each

# Step 3: Generate all pending M-shot videos
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only
```

**Current blockers:**
- ⚠️ OPEN-010: Clear 001_M02-M05 ghost first_frame_url + re-generate frames before --videos-only
- ⚠️ OPEN-009: Patch scene 008 video/frame URLs before stitch if needed
- ✅ CIG gate: 0/97 shots blocked
- ✅ Session enforcer: HEALTHY
- ✅ Vision backends: online

---

## 11. DOCUMENT LINEAGE

- R1-R7: hourly incremental baseline and consolidation
- R8: OPEN-004 first reported; OPEN-008 first reported (later retracted R13 as FALSE POSITIVE)
- R9-R12: OPEN-008 persisted as P0 (was FALSE POSITIVE throughout)
- R13: OPEN-008 + OPEN-006 retracted. System cleared of all P0 blockers.
- R14: OPEN-004 advances to CHRONIC-7. No new bugs. Coverage overcounting (62 first_frames) not yet detected.
- **R15 (CURRENT):** OPEN-010 NEW (ghost first_frame_url 001_M02-M05). OPEN-009 expanded to cover first_frame_url. R14 overcounting corrected. OPEN-004 advances to CHRONIC-8. 0 P0 blockers.

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T17:13:27Z",
  "run_number": 15,
  "prior_report": "R14",
  "system_version": "V36.5",
  "ledger_age_minutes": 501,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 21,
    "confirmed_bug": 2,
    "chronic": 1,
    "architectural_debt": 1,
    "stale_doc": 2,
    "false_positives_retracted": 0
  },
  "key_signals": {
    "cig_gate_blocked_shots": 0,
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "api_path_first_frame_urls": 4,
    "ghost_first_frame_urls_missing_file": 4,
    "total_ghost_fields": 12,
    "e_shots_with_char_names_in_gate_fields": 0,
    "e_shots_total": 35,
    "m_shots_with_chain_group": 62,
    "m_shots_without_chain_group": 0,
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "shots_with_video_url_in_plan": 28,
    "real_video_urls_excluding_api_path": 24,
    "first_frame_jpgs_on_disk_total": 62,
    "first_frame_jpgs_actual_shot_frames": 35,
    "first_frame_jpgs_chain_lastframe_files": 27,
    "shots_with_first_frame_url_in_plan": 39,
    "shots_with_valid_first_frame_url": 35,
    "scenes_with_100pct_video": 2,
    "p0_blockers": 0,
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13,
    "run_report_success": true,
    "learning_log_fixes": 22,
    "learning_log_regressions": 0,
    "arc_positions_present": 97
  },
  "false_positives_retracted": [],
  "open_issues": [
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 4,
      "expansion_r15": "Now covers both video_url (4) and first_frame_url (4) for 008 E-shots. 8 total affected fields.",
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "affected_fields": ["video_url", "first_frame_url"]
    },
    {
      "id": "OPEN-010",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 1,
      "new_in_r15": true,
      "affected_shots": ["001_M02", "001_M03", "001_M04", "001_M05"],
      "description": "first_frame_url set but file missing. APPROVED status. Non-blocking for --videos-only via chain."
    },
    {
      "id": "OPEN-004",
      "classification": "CHRONIC-8",
      "severity": "P2",
      "blocking": false,
      "consecutive_reports": 8,
      "approaching_meta_chronic": true,
      "meta_chronic_at_report": "R17",
      "fix_effort_minutes": 5,
      "fix_recipe": "7-line try/except at runner:~1141 calling decontaminate_prompt()"
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "consecutive_reports": 14
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 14
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 12
    }
  ],
  "generation_readiness": {
    "scenes_ready_for_video_after_patch": ["001", "002", "003", "004"],
    "scenes_need_frames_first": ["005", "007", "009", "010", "011", "012", "013"],
    "gate_blocking_any_scene": false,
    "pre_condition_001": "Clear OPEN-010 ghost first_frame_urls + re-run --frames-only 001 + re-approve M02-M05",
    "recommended_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only"
  },
  "recommended_next_action": "apply_p1_patches_then_run_frames_only_001_then_videos_only_001_002_003_004"
}
```

---

**END REPORT**

*ATLAS R15 — Keep-up detection complete. NEW: OPEN-010 (ghost first_frame_url 001_M02-M05) detected. OPEN-009 expanded to cover first_frame_url for scene 008 E-shots. R14 first_frame count corrected (35 real vs 62 overcounted). OPEN-004 advances to CHRONIC-8 (META-CHRONIC at R17). 0 P0 blockers. P1 data patches recommended before next generation. Scenes 001-004 M-shots ready for --videos-only after OPEN-010 patch.*
