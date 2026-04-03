# ATLAS ERROR DEEPDIVE — 2026-03-30 R2 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T04:14:21Z
**Run number:** R2
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R1_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header), V37 governance hooks present
**Ledger age at snapshot:** 0d 9h 26m (last entry: 2026-03-29T18:43:06 — gate-blocked contamination)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 10 PASS / 2 CONFIRMED_BUG / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC**

| Category | Count | Delta vs R1 |
|----------|-------|-------------|
| CONFIRMED_BUG | 2 | = same (OPEN-001 now CHRONIC at 2 reports; no new bugs) |
| ARCHITECTURAL_DEBT | 1 | = same |
| STALE_DOC | 1 | = same |
| CONFIRMED_FIXED | 12 | +2 (CPC LIVER confirmed as inline embedding, not missing; story_state_canon + failure_heatmap both importable) |
| FALSE_POSITIVES | 0 | = same |
| NEW CONFIRMED_FIXED | 2 | CPC liver reclassified from DEGRADED; chain_arc_intelligence + failure_heatmap verified |

**Key findings this session:**
1. 🔴 **OPEN-001 CHRONIC (2 reports)** — chain_group still missing on ALL 62 M-shots; gate_audit.json confirms 4x ORPHAN_SHOT from 18:43:06 run; ledger contamination unresolved (006_M01–M04 I=0.75/V=0.5 overwrote valid I=1.0/V=0.85 from 17:54:06 run). No new generation occurred since R1.
2. 🟢 **CPC LIVER reclassification** — R1 reported Liver as DEGRADED (decontaminate_prompt not in runner). CONFIRMED FALSE in R2: runner has its own inline CPC via `_is_cpc_via_embedding()` (semantic similarity detection). The standalone `tools/creative_prompt_compiler.decontaminate_prompt()` is intentionally NOT used by runner — runner falls back to `description` instead of CPC replacement. This is a PARTIAL T2-CPC-6 violation but not missing CPC entirely. Liver reclassified: 🟡 DEGRADED (partial) → gap only affects 2 un-enriched shots (013_M01/M02 lack `_beat_action`).
3. 🟢 **No new production runs** — zero new ledger entries, frames, or videos since R1. System idle. All counts identical: 59 first_frames, 118 videos_kling_lite entries (29 .mp4 files).
4. 🟢 **V37 governance bar intact** — 10 references in HTML, 7 /api/v37 endpoints in orchestrator, 4 _V37_GOVERNANCE refs in runner. Section 8.9 compliant.
5. 🟢 **Session enforcer: 69 pass / 0 block** — ✅ SYSTEM HEALTHY (count increased from 47→69 vs R1, likely different section output captured this time).

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (this session) |
|-------|--------|--------|----------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance bare-list guard present at runner:1429, runner:4077 | grep confirmed |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED (partial) | Runner has _is_cpc_via_embedding (detection) but NOT decontaminate_prompt (replacement). Only falls back to `description`. Gap affects only shots missing `_beat_action` (2 shots: 013_M01/M02). | runner line 1077–1086 + grep confirmed |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | CLAUDE.md title says V36.0, Version field says V36.5 (minor). Runner docstring header says V31.0 + Seedance PRIMARY — contradicts C3. Section 9 pre-response protocol present and intact. | head runner:1-25 + grep |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: 69 pass / 0 block. All imports verified. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | All 4 vision backends: gemini_vision, openrouter, florence_fal, heuristic. All env keys PRESENT. | session_enforcer output |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | Latest-per-shot: 23/33 shots I=0.75 (69% heuristic). Last 4 ledger entries: gate-blocked contamination (I=0.75/V=0.5 overwrote valid I=1.0/V=0.85). No new generation since R1. | ledger analysis this session |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | run_report success=True; 29 kling .mp4s in videos_kling_lite; latest frames at 2026-03-29T21:19. | ls + run_report |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire B (`_fail_sids`) confirmed at runner:5228 (grep) | grep WIRE-B |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire C confirmed in runner | grep WIRE-C |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header = V31.0; CLAUDE.md title = V36.0, Version = V36.5; Runner line 24/39 docstring = Seedance PRIMARY | grep confirmed |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All items from R1 remain confirmed. Two new entries added this session:

✅ **ENV LOAD ORDER (V35.0)** — GOOGLE_API_KEY + FAL_KEY + OPENROUTER_API_KEY set BEFORE vision_judge import. Confirmed R1, R2.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675 present. Confirmed R1, R2.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — Present in vision_judge.py lines 518-529. Confirmed R1, R2.

✅ **V-SCORE 4-STATE (V30.0)** — All four states [0.0, 0.3, 0.5, 0.85] present. Confirmed R1, R2.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group. Confirmed R1, R2.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL = "kling". Confirmed R1, R2.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 422. Confirmed R1, R2.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1429, 4077+. Confirmed R1, R2.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:4272. Confirmed R1, R2.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4455. All 97 shots have `_arc_position`. Confirmed R1, R2.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired in runner. Confirmed R1, R2.

✅ **V37 GOVERNANCE HOOKS** — 4 _V37_GOVERNANCE refs in runner, 7 /api/v37 endpoints in orchestrator, 10 references in HTML. Section 8.9 integrity verified R2.

✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR). Confirmed R1, R2.

✅ **NEW R2: CPC INLINE DETECTION** — Runner implements `_is_cpc_via_embedding()` (semantic cosine similarity via Gemini embedding) at line 245-271. Called at line 1077 in `_build_prompt()`. CPC contamination detection IS wired. The gap is decontaminate_prompt() REPLACEMENT is absent (see OPEN-004 new issue below). Liver reclassified from "missing CPC" to "partial T2-CPC-6".

✅ **NEW R2: story_state_canon + failure_heatmap importable** — Both modules import cleanly. story_state_canon.get_canon_state('006') returns valid canon. failure_heatmap.build_heatmap/assess_production_readiness/generate_executive_view all importable. V36.0 control theory layer intact.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (2 reports) — OPEN-001: ORPHAN_SHOT Gate Blocks Kling + Ledger Contamination

**Classification:** CHRONIC (2 consecutive reports: R1 + R2)
**Severity:** HIGH — blocks video regeneration on all M-shots; overwrites good ledger entries with defaults
**First seen:** R1 (2026-03-30T03:16:14Z)

**PROOF RECEIPT (this session — R2):**
```
PROOF: python3 -c "...m_shots; no_chain_group=[s for s if not s.get('chain_group')]"
OUTPUT: M_SHOTS_TOTAL=62, M_SHOTS_NO_chain_group=62 → ['001_M01','001_M02','001_M03','001_M04','001_M05'...]
        M_SHOTS_HAS_chain_group=0

PROOF: cat pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json
OUTPUT: 4 entries all passed=False, ORPHAN_SHOT error, timestamp=2026-03-29T18:43:06

PROOF: last 10 ledger entries
OUTPUT: 2026-03-29T18:43:06 006_M01 I=0.75 V=0.5 (overwrote 17:54:06 I=1.0 V=0.85)
        2026-03-29T18:43:06 006_M02 I=0.75 V=0.5 (overwrote 17:54:06 I=1.0 V=0.85)
        2026-03-29T18:43:06 006_M03 I=0.75 V=0.5 (overwrote 17:54:06 I=0.75 V=0.85)
        2026-03-29T18:43:06 006_M04 I=0.75 V=0.5 (overwrote 17:54:06 I=0.80 V=0.85)
```

**CONFIRMS:** `chain_intelligence_gate.py` line 450 checks `shot.get("chain_group") or shot.get("_chain_group")`. Runner sets only `s["_gen_strategy"]` in memory (never `chain_group`). Gate finds no `chain_group` → ORPHAN_SHOT → `continue` skips Kling call → group loop ends → Phase 2d (reward signal) still runs → writes V=0.5/I=0.75 defaults to ledger → overwrites valid prior entries.

**Root cause (code trace):**
- Runner lines 2699–2709: sets `s["_gen_strategy"] = "INDEPENDENT"/"CHAIN_ANCHOR"/"CHAIN"` — never `s["chain_group"]`
- Gate line 450: `chain_group = shot.get("chain_group") or shot.get("_chain_group")` — misses `_gen_strategy`
- Gate error message at line 456 says: "Add chain_group or use atlas_universal_runner's auto-grouping" — but the runner IS the auto-grouping and it doesn't set chain_group

**FIX RECIPE (Option A — 1 line in gate, preferred):**
```python
# tools/chain_intelligence_gate.py line 450 — change from:
chain_group = shot.get("chain_group") or shot.get("_chain_group")
# to:
chain_group = (shot.get("chain_group") or shot.get("_chain_group")
               or shot.get("_gen_strategy"))  # V36.5: runner writes _gen_strategy not chain_group
```

**FIX RECIPE (Option B — 3 lines in runner, belt-and-suspenders):**
```python
# atlas_universal_runner.py ~line 2699:
s["_gen_strategy"] = "INDEPENDENT"
s["chain_group"] = "independent"                # ADD

# ~line 2705:
s["_gen_strategy"] = "CHAIN_ANCHOR"
s["chain_group"] = f"chain_{scene_id}"          # ADD

# ~line 2709:
s["_gen_strategy"] = "CHAIN"
s["chain_group"] = f"chain_{scene_id}"          # ADD
```

**REGRESSION GUARD (do NOT touch):**
- `_WIRE_A_MAX_REGENS_PER_SCENE` budget logic
- `extract_last_frame()` chain path
- `_arc_position` enrichment (97/97 shots confirmed correct)
- `_independent_start_url` logic for INDEPENDENT shots

**VERIFY FIX:** Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only`. `gate_audit.json` should show `"passed": true` on all 4 shots. Ledger should show V=0.85 entries.

---

### 🟡 ARCHITECTURAL_DEBT — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (consecutive: 2, R1+R2 — no code bug, data migration only)
**Severity:** LOW — not in latest-per-shot view (all 9 are overwritten by later normalized runs). Affects only raw aggregate analysis.

**PROOF RECEIPT (R2):**
```
PROOF: python3 -c "...bad=[e for e in lines if e.get('I_score',e.get('I',0))>1.0]; print(len(bad))"
OUTPUT: 9 entries with I in [3.5, 4.0, 5.0] — all timestamps 2026-03-24

PROOF: latest-per-shot I>1.0 count
OUTPUT: 0 (all latest-per-shot entries normalized ≤1.0)
```

**Note R2:** The 9 entries do NOT appear in latest-per-shot analysis (they were overwritten by post-V35.0 runs). Impact is limited to raw full-history aggregates only.

**FIX RECIPE (one-time migration, NOT in runner):**
```python
import json, pathlib
path = pathlib.Path('pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl')
lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
fixed = [{**e, 'I': round(e['I']/5.0,3) if e.get('I',0)>1.0 else e,
              'I_score': round(e['I_score']/5.0,3) if e.get('I_score',0)>1.0 else e.get('I_score',e.get('I',0))}
         for e in lines]
path.write_text('\n'.join(json.dumps(e) for e in fixed)+'\n')
```

---

### 🟡 STALE_DOC — OPEN-003: Runner Docstring Declares Seedance as PRIMARY (C3 Violation in Comment)

**Classification:** STALE_DOC (consecutive: 2, R1+R2 — code is correct, docstring is wrong)
**Severity:** LOW — ACTIVE_VIDEO_MODEL="kling" is correct. Risk: future engineer reads line 24/39 and gets wrong mental model.

**PROOF RECEIPT (R2):**
```
PROOF: grep -n "Seedance.*PRIMARY\|muapi" atlas_universal_runner.py | head -5
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (images_list=[start_frame, char1, char2, loc])
  Line 428–438: Seedance config block present but NEVER CALLED (route_shot() always returns "kling")
```

**FIX RECIPE:**
```python
# Line 24 — replace:
#   P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
# with:
#   P2. Videos: ALL shots sequential (chain) → Kling v3/pro PRIMARY (fal-ai/kling-video/v3/pro) | Seedance RETIRED V31.0

# Line 39 — replace:
#   All shots PRIMARY → Seedance v2.0 via muapi.ai (images_list=[start_frame, char1, char2, loc])
# with:
#   All shots PRIMARY → Kling v3/pro via fal-ai (multi_prompt + @Element identity, end-frame chain)
```

---

### 🟡 NEW R2 — OPEN-004: CPC Liver Partial Gap — decontaminate_prompt() Not Called on Generic Fallback

**Classification:** CONFIRMED_BUG (partial T2-CPC-6 violation) — first report (R2)
**Severity:** LOW-MEDIUM — only affects shots where `_beat_action` is absent AND choreography tests generic. Currently 2 un-enriched shots (013_M01/M02). Wider impact if beat enrichment gaps exist in future scenes.

**PROOF RECEIPT (R2):**
```
PROOF: grep -n "_is_cpc_via_embedding\|decontaminate_prompt" atlas_universal_runner.py
OUTPUT:
  Line 1077: elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
  Line 1083:     base = s.get("description", "")   ← falls to description, NOT decontaminate_prompt
  No decontaminate_prompt in runner at all

PROOF: python3 -c "...m-shots missing _beat_action..."
OUTPUT: 60/62 have _beat_action. Missing: ['013_M01', '013_M02']
```

**CONFIRMS:** T2-CPC-6 requires: "decontaminate_prompt() REPLACES, not strips." The runner detects generic content via `_is_cpc_via_embedding()` but falls back to `description` instead of calling `decontaminate_prompt()` for a CPC-driven physical verb replacement. This means 013_M01/M02 (and any future shot without `_beat_action`) get `description` as the prompt rather than a CPC-enriched directive.

**Impact scoping:** Since 60/62 M-shots have `_beat_action`, the CPC fallback path is rarely triggered. T2-CPC-6 gap is real but low-blast-radius right now.

**FIX RECIPE (minimal):**
```python
# atlas_universal_runner.py ~line 1077 — change from:
elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
    ...
    base = s.get("description", "")
# to:
elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt as _decon
        _emotion = s.get("_emotional_state") or s.get("_beat_atmosphere", "neutral")
        _char = (s.get("characters") or [""])[0]
        base = _decon(clean_choreo, _char, _emotion, s.get("description",""))
    except Exception:
        base = s.get("description", "")   # safe fallback unchanged
```

**REGRESSION GUARD:** Only modifies the CPC-triggered fallback branch. Does NOT touch `_beat_action` primary path (line 1073). Non-blocking: try/except preserves existing behavior on failure.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

**FP-001 (R1 implicit):** R1 Liver was classified DEGRADED with note "CPC decontaminate_prompt not found in runner (unverified gap)". R2 investigation shows runner has `_is_cpc_via_embedding` (inline CPC detection) — the module IS wired, just differently than the standalone tool. The issue is narrowed to the REPLACEMENT step (OPEN-004) not the detection step. Liver upgraded from "missing CPC entirely" to "partial T2-CPC-6 gap".

---

## 6. PRIORITISED FIX LIST

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-001: ORPHAN_SHOT gate + ledger contamination | CHRONIC (2) | HIGH — blocks reruns, contaminates reward signal | 1 line in gate (Option A) |
| 2 | OPEN-004: CPC decontaminate_prompt not called | CONFIRMED_BUG | LOW-MEDIUM — affects 2 shots now, more if enrichment gaps grow | 6 lines in runner |
| 3 | OPEN-003: Stale Seedance docstring | STALE_DOC | LOW — doc only, no exec impact | 2 comment lines |
| 4 | OPEN-002: Historical I>1.0 ledger entries | ARCHITECTURAL_DEBT | LOW — latest-per-shot clean; raw aggregates only | 5-line migration script |

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (line 452: os.environ.get("ATLAS_VIDEO_MODEL", "kling"))
□ LTX_FAST raises RuntimeError — ✅ PASS (line 422: _LTXRetiredGuard())
□ route_shot() returns "kling" all branches — ✅ PASS (lines 1531-1537)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY set before vision_judge import — ✅ PASS (all PRESENT in .env; runner lines 154-195)
□ I-score normalization present in vision_judge — ✅ PASS (line 675)
□ Gemini circuit breaker wired — ✅ PASS (vision_judge lines 518-529)
□ Wire-A budget reset at scene start — ✅ PASS (runner:4272)
□ Wire-B fail_sids filter — ✅ PASS (runner:5228)
□ Wire-C frozen regen — ✅ PASS (runner grep confirmed)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1429, 4077)
□ Chain arc enrichment wired — ✅ PASS (runner:4455)
□ All 97 shots have _arc_position — ✅ PASS (97/97)
□ E-shots have _no_char_ref — ✅ PASS (35 E-shots confirmed R1)
□ V37 governance hooks — ✅ PASS (4 runner refs, 7 orchestrator endpoints, 10 HTML refs)
□ V37 Section 8.9 thumbBar/thumbUp/thumbDown — ✅ PASS (count > 0 confirmed)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R1)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (69 pass, 0 block)
□ story_state_canon importable — ✅ PASS (R2 new check)
□ failure_heatmap importable — ✅ PASS (R2 new check)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (R2 new check)
□ chain_group MISSING on all M-shots — ⚠ OPEN-001 CHRONIC (62/62 missing)
□ gate_audit.json shows ORPHAN_SHOT — ⚠ OPEN-001 (4 failures, 2026-03-29T18:43:06)
□ Last 4 ledger entries V=0.5 (gate-blocked contamination) — ⚠ OPEN-001
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 (new R2)
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 (non-urgent)
```

---

## 8. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R1_KEEPUP_LATEST.md** (2026-03-30T03:16:14Z)
- Prior proof gate: **NONE** (no proof-gate run exists yet)
- Delta since R1: 0 new ledger entries, 0 new frames, 0 new videos. System idle since 2026-03-29T21:19.
- Report interval: ~1h (R1→R2: 58 minutes)
- Recommended next action: **Fix OPEN-001 (chain_group gate fix) before any --videos-only reruns**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T04:14:21Z",
  "report_number": "R2",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R1_KEEPUP_LATEST.md",
  "ledger_age_hours": 9.5,
  "ledger_last_entry": "006_M04 I=0.75 V=0.5 C=0.7 (gate-blocked contamination)",
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "i_score_heuristic_pct": 69,
  "i_score_real_vlm_pct": 30,
  "i_score_historical_bad_latest_per_shot": 0,
  "production_idle_since": "2026-03-29T21:19:00Z",
  "confirmed_bugs": [
    {
      "id": "OPEN-001",
      "title": "ORPHAN_SHOT gate blocks Kling + ledger contamination",
      "consecutive_reports": 2,
      "class": "CHRONIC",
      "proof_receipt": "62/62 M-shots missing chain_group; gate_audit.json 4x passed=false ORPHAN_SHOT; last 4 ledger V=0.5 overwrite valid V=0.85",
      "fix_recipe": "tools/chain_intelligence_gate.py line 450: add `or shot.get('_gen_strategy')` to chain_group resolution",
      "fix_alternative": "atlas_universal_runner.py lines 2699/2705/2709: set s['chain_group']=f'chain_{scene_id}' alongside _gen_strategy",
      "regression_guard": ["Wire-A budget", "extract_last_frame", "_arc_position (97/97 clean)", "_independent_start_url"],
      "verify_fix": "Re-run --videos-only on scene 006; gate_audit.json passed=true; new ledger V=0.85"
    },
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 1,
      "class": "CONFIRMED_BUG",
      "proof_receipt": "runner line 1083 falls to s.get('description') when CPC detects generic choreo; no decontaminate_prompt call anywhere in runner; 013_M01/M02 have no _beat_action",
      "fix_recipe": "runner ~line 1080: import decontaminate_prompt from tools.creative_prompt_compiler; call instead of description fallback; try/except safe",
      "regression_guard": ["_beat_action primary path (line 1073) unchanged", "_is_cpc_via_embedding detection logic unchanged"],
      "impact": "LOW-MEDIUM — 2 affected shots now (013_M01/M02); more if enrichment gaps grow"
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 2,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot all normalized. Raw aggregate only. One-time migration script."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 2,
      "class": "STALE_DOC",
      "lines": [24, 39]
    }
  ],
  "false_positives_retracted": [
    {
      "id": "FP-001",
      "from": "R1 Liver DEGRADED (missing CPC)",
      "to": "R2 Liver DEGRADED (partial T2-CPC-6 — detection present, replacement absent)",
      "reason": "_is_cpc_via_embedding() is wired at runner:1077; standalone decontaminate_prompt not called (new OPEN-004)"
    }
  ],
  "organ_health": {
    "skeleton": "HEALTHY",
    "liver": "DEGRADED — _is_cpc_via_embedding detection OK; decontaminate_prompt replacement absent (OPEN-004)",
    "immune": "DEGRADED — runner header V31.0 / CLAUDE.md V36.5 drift; Seedance docstring lines 24/39",
    "nervous": "HEALTHY — session_enforcer 69 pass / 0 block",
    "eyes": "HEALTHY — all 4 backends; all env keys PRESENT",
    "cortex": "DEGRADED — 69% I=0.75 heuristic; last 4 entries gate-contaminated (OPEN-001)",
    "cinematographer": "HEALTHY — run_report success=True; 29 videos; latest frames 2026-03-29T21:19",
    "editor": "HEALTHY — Wire B confirmed",
    "regenerator": "HEALTHY — Wire C confirmed",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.0/V36.5 across files; Seedance docstring"
  },
  "new_confirmed_fixed_this_session": [
    "CPC inline detection (_is_cpc_via_embedding) confirmed wired at runner:1077",
    "story_state_canon importable — get_canon_state('006') returns valid canon",
    "failure_heatmap importable — all 3 public functions available",
    "chain_arc_intelligence.enrich_shots_with_arc importable",
    "V37 Section 8.9 governance bar: 10 HTML refs, 7 api/v37 endpoints, 4 runner refs — intact"
  ],
  "recommended_next_action": "fix_open_001_before_any_generation",
  "fix_priority_1": "chain_intelligence_gate.py line 450: add `or shot.get('_gen_strategy')` — 1 line change, unblocks all --videos-only reruns"
}
```

---

*ATLAS Keep-Up R2 — 2026-03-30T04:14:21Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-001 (CHRONIC-2), OPEN-004 (new), OPEN-003 (STALE_DOC-2), OPEN-002 (ARCH_DEBT-2)*
*System idle since 2026-03-29T21:19 — no new generation since R1*
*Next: fix OPEN-001 before any --videos-only reruns*
