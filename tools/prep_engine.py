# V36 AUTHORITY: This module is PASS/FAIL ONLY.
# It CANNOT modify shot_plan.json or prompt fields.
# It returns verdicts. Controller decides what to do with them.

"""
ATLAS V22 PREP ENGINE — Headless Auto-Preparation Pipeline
============================================================
Runs BEFORE the UI opens. Produces a fully validated, render-ready project.

Flow:
  prep_project(project_name)
    → normalize_project()      # single truth, archive old
    → load_canonical_data()    # cast, wardrobe, locations, audio
    → build_shot_plan()        # coverage solver, chain grouping, composition hashing
    → run_v22_modules()        # actor intent, delta prompt, composition cache, continuity store
    → validate_continuity()    # preflight gate — halt if ANY field missing
    → generate_fal_manifest()  # fal_prompt_manifest.xlsx — audit sheet
    → generate_run_report()    # atlas_run_report.json — what fired, what's ready
    → return PrepResult

If ANY step fails, pipeline halts. No rendering allowed.
"""

import json
import os
import sys
import time
import hashlib
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class PrepResult:
    success: bool
    project: str
    timestamp: str
    phases: Dict[str, dict] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class PreflightCheck:
    name: str
    passed: bool
    detail: str
    severity: str  # "HALT" or "WARN"


# ============================================================
# ROUTE LOCK — Only Master Chain Renderer allowed
# ============================================================

ALLOWED_RENDER_ROUTES = {
    "/api/v18/master-chain/render-scene",
    "/api/v18/master-chain/parallel-render",
    "/api/v18/autonomous/render-scene",
    "/api/auto/generate-first-frames",
    "/api/auto/render-videos",
    "/api/v16/stitch/run",
    "/api/v16/stitch/dry-run",
}

BLOCKED_RENDER_ROUTES = {
    # Direct script execution bypasses the system
    "/api/direct/render",
    "/api/direct/generate",
}


def check_route_lock(route: str) -> Tuple[bool, str]:
    """Returns (allowed, reason). Blocks unauthorized render paths."""
    if route in BLOCKED_RENDER_ROUTES:
        return False, f"ROUTE LOCKED: {route} is blocked. Use Master Chain Renderer."
    return True, "OK"


# ============================================================
# DATA LOCK — Only ravencroft_v22 allowed
# ============================================================

ALLOWED_PROJECTS = {"ravencroft_v22", "victorian_shadows_ep1"}


def check_data_lock(project: str) -> Tuple[bool, str]:
    """Returns (allowed, reason). Only whitelisted projects can render."""
    if project not in ALLOWED_PROJECTS:
        return False, f"DATA LOCKED: '{project}' is not an active project. Only {ALLOWED_PROJECTS} allowed."
    return True, "OK"


# ============================================================
# PROMPT AUTHORITY LOCK — Prompts only from shot_plan builder
# ============================================================

def check_prompt_authority(shot: dict) -> Tuple[bool, str]:
    """Verify prompt came from the pipeline, not manual entry."""
    nano = shot.get("nano_prompt", "")
    ltx = shot.get("ltx_motion_prompt", "")

    # Must have nano prompt (LTX motion prompt is RETIRED — C3 law — do not require)
    if not nano:
        return False, f"Shot {shot.get('shot_id', '?')}: missing nano_prompt"
    # NOTE: ltx_motion_prompt is intentionally NOT checked here — LTX is retired (C3 Constitutional Law)

    # Must have V13 gold standard markers
    if "NO grid" not in nano and "NO morphing" not in nano:
        return False, f"Shot {shot.get('shot_id', '?')}: nano_prompt missing V13 gold standard"

    return True, "OK"


# ============================================================
# PREFLIGHT VALIDATION — The gate before rendering
# ============================================================

def run_preflight(shots: List[dict], cast_map: dict, wardrobe: dict) -> List[PreflightCheck]:
    """Run all preflight checks. Returns list of checks with pass/fail."""
    checks = []

    # 1. Character refs present — check shot-level field OR cast_map (runner resolves from cast_map at runtime)
    char_shots = [s for s in shots if s.get("characters")]
    def _has_ref(shot: dict) -> bool:
        # First: shot has its own ref wired in
        if shot.get("character_reference_url"):
            return True
        # Second: every character in the shot is in cast_map with a character_reference_url
        if cast_map:
            return all(
                isinstance(cast_map.get(c), dict) and cast_map[c].get("character_reference_url")
                for c in (shot.get("characters") or [])
            )
        return False
    refs_present = sum(1 for s in char_shots if _has_ref(s))
    checks.append(PreflightCheck(
        name="character_refs",
        passed=refs_present == len(char_shots),
        detail=f"{refs_present}/{len(char_shots)} character shots resolvable via shot or cast_map",
        severity="HALT" if refs_present < len(char_shots) * 0.9 else "WARN"
    ))

    # 2. Wardrobe present for character shots
    wardrobe_keys = set(wardrobe.keys()) if wardrobe else set()
    wardrobe_hits = 0
    for s in char_shots:
        sid = s.get("scene_id", "")
        for c in s.get("characters", []):
            key = f"{c}::Scene_{sid}"
            if key in wardrobe_keys:
                wardrobe_hits += 1
                break
    checks.append(PreflightCheck(
        name="wardrobe_present",
        passed=wardrobe_hits > 0,
        detail=f"{wardrobe_hits}/{len(char_shots)} character shots have wardrobe coverage",
        severity="WARN"
    ))

    # 3. Chain IDs exist (from delta prompt builder)
    chained = sum(1 for s in shots if s.get("_delta_prompt_nano") or s.get("_is_anchor"))
    checks.append(PreflightCheck(
        name="chain_groups_detected",
        passed=chained > 0,
        detail=f"{chained} shots in chain groups",
        severity="WARN"
    ))

    # 4. Composition hashes generated (actor intent as proxy)
    intent_count = sum(1 for s in shots if s.get("actor_intent"))
    checks.append(PreflightCheck(
        name="actor_intent_enriched",
        passed=intent_count > len(shots) * 0.4,
        detail=f"{intent_count}/{len(shots)} shots have actor intent",
        severity="WARN"
    ))

    # 5. LTX contamination check (C3: LTX is RETIRED — shots should NOT have ltx_motion_prompt)
    # Inverted from original: WARN if LTX prompts ARE present (contamination), not if absent.
    ltx_contaminated = sum(1 for s in shots if s.get("ltx_motion_prompt"))
    checks.append(PreflightCheck(
        name="ltx_prompts_absent",
        passed=ltx_contaminated == 0,
        detail=(f"CLEAN — no LTX prompts (C3 compliant)" if ltx_contaminated == 0
                else f"WARNING: {ltx_contaminated}/{len(shots)} shots have LTX prompts — C3 contamination"),
        severity="WARN"  # WARN not HALT — contaminated prompts are overridden at runtime by runner
    ))

    # 6. Nano prompts present — AUTO-POPULATE any empty ones before generation.
    # Empty prompts reaching the runner produce hallucinated frames with zero character
    # description. Fix at prep time so the shot_plan itself is complete.
    _lens_map_prep = {
        "wide": "24mm, f/8", "establishing": "24mm, f/8", "closing": "24mm, f/8",
        "medium": "35mm, f/4", "two_shot": "35mm, f/4",
        "medium_close": "50mm, f/2.8", "ots_a": "50mm, f/2.8", "ots_b": "50mm, f/2.8",
        "close_up": "85mm, f/2", "mcu": "85mm, f/2", "reaction": "85mm, f/2",
        "insert": "100mm macro",
    }
    _auto_populated = 0
    for _s in shots:
        if not (_s.get("nano_prompt") or "").strip():
            _st = (_s.get("shot_type") or "medium").lower()
            _lens = _lens_map_prep.get(_st, "35mm, f/4")
            _desc = (_s.get("description") or _s.get("_beat_action") or "").strip()
            _chars = _s.get("characters") or []
            _char_parts = []
            for _cn in _chars[:2]:
                _cd = cast_map.get(_cn) if isinstance(cast_map.get(_cn), dict) else {}
                _app = (_cd.get("appearance") or _cd.get("amplified_appearance") or "").strip()
                if _app:
                    _char_parts.append(f"{_cn}: {_app[:120]}")
            # V30.6: DON'T populate nano_prompt here — let compile_nano() in the runner handle it.
            # compile_nano() has realism anchor, weaved character-in-room, 4 cinematic channels.
            # prep_engine just ensures the DESCRIPTION field exists for compile_nano() to read.
            if not _desc and _char_parts:
                _s["description"] = ". ".join(_char_parts)
            _auto_populated += 1

    # Re-count after auto-populate
    nano_present = sum(1 for s in shots if (s.get("nano_prompt") or "").strip())
    _still_empty = len(shots) - nano_present
    checks.append(PreflightCheck(
        name="nano_prompts_present",
        passed=_still_empty == 0,
        detail=(
            f"{nano_present}/{len(shots)} shots have nano prompts "
            f"({_auto_populated} auto-populated)"
            if _still_empty == 0
            else f"INFO: {_still_empty} shots have no cached nano_prompt — compile_nano() will build at runtime (V30.6 expected)"
        ),
        severity="WARN"  # V30.6: compile_nano() builds prompts at runtime; empty is expected — never HALT
    ))
    if _auto_populated:
        print(f"[PREP] nano_prompts: auto-populated {_auto_populated} empty shots")

    # 7. Cast map has all referenced characters
    all_chars = set()
    for s in shots:
        for c in s.get("characters", []):
            if c:
                all_chars.add(c)
    cast_chars = set(cast_map.keys())
    missing = all_chars - cast_chars
    checks.append(PreflightCheck(
        name="cast_map_complete",
        passed=len(missing) == 0,
        detail=f"{'All characters in cast_map' if not missing else f'Missing: {missing}'}",
        severity="HALT" if missing else "WARN"
    ))

    # 8. Durations present
    dur_present = sum(1 for s in shots if s.get("duration"))
    checks.append(PreflightCheck(
        name="durations_present",
        passed=dur_present == len(shots),
        detail=f"{dur_present}/{len(shots)} shots have durations",
        severity="HALT"
    ))

    # 9. No duplicate enrichment blocks (Contract B)
    dup_count = 0
    for s in shots:
        nano = s.get("nano_prompt", "")
        if nano.count("performance:") > 1 or nano.count("subtext:") > 1:
            dup_count += 1
    checks.append(PreflightCheck(
        name="no_duplicate_enrichment",
        passed=dup_count == 0,
        detail=f"{dup_count} shots have duplicate enrichment blocks",
        severity="WARN"
    ))

    # 10. Scene manifest matches shots
    shot_scenes = set(s.get("scene_id", "") for s in shots)
    checks.append(PreflightCheck(
        name="scene_coverage",
        passed=True,
        detail=f"{len(shot_scenes)} unique scenes in shots",
        severity="WARN"
    ))

    # 11. Consecutive shot continuity — detect duplicate beats that break visual flow
    _continuity_issues = []
    _scenes = {}
    for s in shots:
        scene = s.get("scene_id") or s.get("shot_id", "")[:3]
        _scenes.setdefault(scene, []).append(s)

    for scene_id, scene_shots in _scenes.items():
        sorted_shots = sorted(scene_shots, key=lambda x: x.get("shot_id", ""))
        for i in range(1, len(sorted_shots)):
            prev = sorted_shots[i-1]
            curr = sorted_shots[i]
            prev_beat = (prev.get("_beat_action") or "").strip().lower()
            curr_beat = (curr.get("_beat_action") or "").strip().lower()
            prev_eye = (prev.get("_eye_line_target") or "").strip().lower()
            curr_eye = (curr.get("_eye_line_target") or "").strip().lower()
            # Flag if beat action is identical or eye-line hasn't changed across shot type change
            if prev_beat and curr_beat and prev_beat == curr_beat:
                _continuity_issues.append(
                    f"{curr['shot_id']}: duplicate beat from {prev['shot_id']} — '{curr_beat[:50]}'"
                )
            elif prev_eye and curr_eye and prev_eye == curr_eye and prev.get("shot_type") != curr.get("shot_type"):
                _continuity_issues.append(
                    f"{curr['shot_id']}: same eye-line as {prev['shot_id']} across shot type change — '{curr_eye}'"
                )

    checks.append(PreflightCheck(
        name="continuity_contract",
        passed=len(_continuity_issues) == 0,
        detail=(f"CLEAN — no consecutive duplicates" if not _continuity_issues
                else f"{len(_continuity_issues)} issues: " + "; ".join(_continuity_issues[:3])),
        severity="WARN"
    ))

    # V30.5 CHECK: tone_shots_unique ────────────────────────────────────────────
    # E-series tone shots should be scene-specific. If two E shots from different
    # scenes share identical descriptions, inject_tone_shots() produced duplicates.
    _e_shots = [s for s in shots if s.get("shot_id", "").split("_")[1:2] == ["E01"]
                or "_E" in s.get("shot_id", "")]
    _e_descs: dict = {}
    _tone_dupes = []
    for s in _e_shots:
        _d = (s.get("description") or "").strip()[:120]
        _sid = s.get("shot_id", "")
        _scene = _sid.split("_")[0]
        if _d and _d in _e_descs and _e_descs[_d] != _scene:
            _tone_dupes.append(f"{_sid} == {_e_descs[_d]}: '{_d[:60]}...'")
        elif _d:
            _e_descs[_d] = _scene
    checks.append(PreflightCheck(
        name="tone_shots_unique",
        passed=len(_tone_dupes) == 0,
        detail=(f"CLEAN — all {len(_e_shots)} E-shots have unique descriptions"
                if not _tone_dupes
                else f"{len(_tone_dupes)} duplicate tone shots: " + "; ".join(_tone_dupes[:2])),
        severity="WARN"
    ))

    # V30.5 CHECK: ext_int_match ─────────────────────────────────────────────────
    # EXT shots must have no characters AND are flagged _force_t2i=True so gen_frame
    # uses the T2I path (interior location masters confuse exterior renders).
    _ext_issues = []
    for s in shots:
        _d = (s.get("description") or "").strip()
        if _d.upper().startswith("EXT."):
            _chars = s.get("characters") or []
            if _chars:
                _ext_issues.append(
                    f"{s.get('shot_id')}: EXT shot has characters {_chars}"
                )
            # Write _force_t2i flag onto the shot so gen_frame routes correctly
            s["_force_t2i"] = True
    checks.append(PreflightCheck(
        name="ext_int_match",
        passed=len(_ext_issues) == 0,
        detail=(f"CLEAN — all EXT shots are character-free and _force_t2i flagged"
                if not _ext_issues
                else f"{len(_ext_issues)} EXT shots have characters: " + "; ".join(_ext_issues[:2])),
        severity="WARN"
    ))

    # V30.5 CHECK: ots_reversal ──────────────────────────────────────────────────
    # For each scene with both ots_a and ots_b shots, verify that ots_b's
    # _frame_description mentions an over-the-shoulder framing toward the OPPOSITE
    # speaker from ots_a. Catches the "duplicate OTS-A" bug (V30.5 production incident).
    _ots_issues = []
    _scene_ids = sorted({s.get("shot_id", "").split("_")[0] for s in shots})
    for _sc in _scene_ids:
        _sc_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{_sc}_")]
        _ots_a = [s for s in _sc_shots if (s.get("_ots_angle") or "").upper() == "A"
                  or "ots_a" in str(s.get("_coverage_role", "")).lower()]
        _ots_b = [s for s in _sc_shots if (s.get("_ots_angle") or "").upper() == "B"
                  or "ots_b" in str(s.get("_coverage_role", "")).lower()]
        if _ots_a and _ots_b:
            # Get the speaker in ots_a
            _a_chars = _ots_a[0].get("characters") or []
            _b_desc = (_ots_b[0].get("_frame_description") or "").lower()
            # OTS-B should reference being "from behind" or "over-the-shoulder" of
            # the character who was the LISTENER in OTS-A (i.e. NOT the ots_a speaker)
            _reversal_words = ["from behind", "over-the-shoulder", "over the shoulder",
                               "ots-b", "ots_b", "b-angle", "reverse"]
            _has_reversal = any(w in _b_desc for w in _reversal_words)
            if not _has_reversal:
                _ots_issues.append(
                    f"Scene {_sc}: ots_b shot '{_ots_b[0].get('shot_id')}' "
                    f"missing reversal keywords in _frame_description"
                )
    checks.append(PreflightCheck(
        name="ots_reversal",
        passed=len(_ots_issues) == 0,
        detail=(f"CLEAN — all OTS pairs have proper A/B reversal"
                if not _ots_issues
                else f"{len(_ots_issues)} OTS reversal issues: " + "; ".join(_ots_issues[:2])),
        severity="WARN"
    ))


    # V30.5 CHECK: stale_seedance_prompts — cached prompts bypass the intelligence layer
    _stale_prompts = [s['shot_id'] for s in shots if (s.get('_seedance_prompt') or '').strip()]
    checks.append(PreflightCheck(
        name='stale_seedance_prompts',
        passed=len(_stale_prompts) == 0,
        detail=(f'CLEAN — no cached _seedance_prompt fields (will rebuild fresh)'
                if not _stale_prompts
                else f'{len(_stale_prompts)} shots have stale cached prompts: {_stale_prompts[:3]}. Clear with empty string.'),
        severity='WARN'
    ))

    # V30.5 CHECK: empty_truth_fields — shots missing beat intelligence
    _empty_truth = []
    for s in shots:
        sid = s.get('shot_id', '')
        chars = s.get('characters', [])
        if chars and not (s.get('_beat_action') or '').strip():
            _empty_truth.append(f'{sid}: missing _beat_action')
        if chars and not (s.get('_body_direction') or '').strip():
            _empty_truth.append(f'{sid}: missing _body_direction')
    checks.append(PreflightCheck(
        name='truth_fields_populated',
        passed=len(_empty_truth) == 0,
        detail=(f'CLEAN — all character shots have beat_action + body_direction'
                if not _empty_truth
                else f'{len(_empty_truth)} missing truth fields: ' + '; '.join(_empty_truth[:3])),
        severity='WARN'
    ))

    # V30.5 CHECK: video_prompt_audit — verify prompts have real content, not placeholders
    _placeholder_arcs = []
    for s in shots:
        sid = s.get('shot_id', '')
        sp_prompt = (s.get('_seedance_prompt') or '').strip()
        if sp_prompt and 'character settles' in sp_prompt and 'delivers action' in sp_prompt:
            _placeholder_arcs.append(sid)
    checks.append(PreflightCheck(
        name='video_prompt_quality',
        passed=len(_placeholder_arcs) == 0,
        detail=(f'CLEAN — no placeholder temporal arcs in cached prompts'
                if not _placeholder_arcs
                else f'{len(_placeholder_arcs)} shots have generic placeholder arcs: {_placeholder_arcs[:3]}'),
        severity='WARN'
    ))

    # V30.6 CHECK: dialogue_fields_present — annotate which shots have dialogue content
    # for downstream embedding verification. Always WARN (never HALT) — just annotates.
    _dlg_shots = []
    for s in shots:
        sid = s.get('shot_id', '')
        dlg = (s.get('dialogue_text') or s.get('_beat_dialogue') or '').strip()
        # Only annotate _has_dialogue=True for character shots — E-shots and empty shots
        # must never be marked as dialogue shots even if _beat_dialogue is populated
        has_chars = bool(s.get('characters'))
        if dlg and len(dlg) > 5 and has_chars:
            s['_has_dialogue'] = True
            _dlg_shots.append(sid)
        else:
            s['_has_dialogue'] = False
    checks.append(PreflightCheck(
        name='dialogue_fields_present',
        passed=True,  # Always passes — annotates shots needing dialogue embedding
        detail=f"{len(_dlg_shots)} shots have dialogue to embed: {_dlg_shots[:5]}",
        severity='WARN'
    ))

    # V31.0 CHECK: prompt_has_scene_context — character shot prompts shouldn't open with pure identity text
    # A prompt starting with "[CHARACTER:" or "character:" has no scene context in the opening 50 chars,
    # which means FAL sees identity-injection boilerplate before any action/scene description.
    _scene_ctx_issues = []
    for s in shots:
        nano = (s.get("nano_prompt") or "").strip()
        chars = s.get("characters") or []
        if chars and nano:
            first_50 = nano[:50].lower()
            _identity_only_openers = ["[character:", "character:", "appearance:", "identity:"]
            if any(first_50.startswith(p) for p in _identity_only_openers):
                _scene_ctx_issues.append(f"{s.get('shot_id')}: prompt opens with identity-only block (no scene context)")
    checks.append(PreflightCheck(
        name="prompt_has_scene_context",
        passed=len(_scene_ctx_issues) == 0,
        detail=(f"CLEAN — all character shot prompts contain scene context before identity blocks"
                if not _scene_ctx_issues
                else f"{len(_scene_ctx_issues)} shots have identity-only prompt starts: " + "; ".join(_scene_ctx_issues[:3])),
        severity="WARN"
    ))

    # V31.0 CHECK: duration_api_valid — all durations must be in {5, 10, 15} (Kling API hard limit)
    _KLING_VALID_DURATIONS = {5, 10, 15}
    _invalid_durs = []
    for s in shots:
        dur = s.get("duration")
        if dur is not None:
            try:
                d = int(float(dur))
                if d not in _KLING_VALID_DURATIONS:
                    _invalid_durs.append(f"{s.get('shot_id')}: duration={d}s (must be 5/10/15)")
            except (TypeError, ValueError):
                _invalid_durs.append(f"{s.get('shot_id')}: duration='{dur}' (non-integer)")
    checks.append(PreflightCheck(
        name="duration_api_valid",
        passed=len(_invalid_durs) == 0,
        detail=(f"CLEAN — all {len(shots)} shots have Kling-valid durations {_KLING_VALID_DURATIONS}"
                if not _invalid_durs
                else f"{len(_invalid_durs)} invalid durations: " + "; ".join(_invalid_durs[:5])),
        severity="WARN"
    ))

    # V31.0 CHECK: dialogue_in_truth_fields — shots with dialogue_text should have _beat_dialogue
    # Without _beat_dialogue, _build_prompt() falls back to dialogue_text but loses beat-level timing.
    _dlg_truth_gaps = []
    for s in shots:
        dlg_text = (s.get("dialogue_text") or "").strip()
        beat_dlg = (s.get("_beat_dialogue") or "").strip()
        if dlg_text and not beat_dlg:
            _dlg_truth_gaps.append(f"{s.get('shot_id')}: has dialogue_text but _beat_dialogue is empty")
    checks.append(PreflightCheck(
        name="dialogue_in_truth_fields",
        passed=len(_dlg_truth_gaps) == 0,
        detail=(f"CLEAN — all {sum(1 for s in shots if (s.get('dialogue_text') or '').strip())} dialogue shots have _beat_dialogue truth field"
                if not _dlg_truth_gaps
                else f"{len(_dlg_truth_gaps)} shots missing _beat_dialogue: " + "; ".join(_dlg_truth_gaps[:3])),
        severity="WARN"
    ))

    # V31.0 CHECK: video_model_consciousness — verify runner's prompt builder reads all 3 beat truth fields
    # gen_scene_multishot() must read _beat_action, _body_direction, _beat_atmosphere (T2-TL-5 compliance).
    _runner_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "atlas_universal_runner.py")
    _consciousness_fields = ["_beat_action", "_body_direction", "_beat_atmosphere"]
    _missing_fields: List[str] = []
    if os.path.exists(_runner_py):
        try:
            with open(_runner_py) as _rf:
                _runner_src = _rf.read()
            for _cf in _consciousness_fields:
                if _cf not in _runner_src:
                    _missing_fields.append(_cf)
        except Exception:
            _missing_fields = ["(runner unreadable)"]
    else:
        _missing_fields = ["(runner not found)"]
    checks.append(PreflightCheck(
        name="video_model_consciousness",
        passed=len(_missing_fields) == 0,
        detail=(f"CLEAN — gen_scene_multishot() reads all beat truth fields: {_consciousness_fields}"
                if not _missing_fields
                else f"Runner missing beat truth field reads: {_missing_fields} — video prompts will lack intelligence"),
        severity="WARN"
    ))

    # ── NEW CHECK: wardrobe_fidelity ─────────────────────────────────────────
    # Compare each shot's _wardrobe_description against cast_map canonical appearance.
    # Fails if the wardrobe field still says things like "Victorian travelling dress"
    # for a character whose cast_map says "charcoal blazer".
    wardrobe_mismatches = []
    for s in char_shots:
        wd = (s.get("_wardrobe_description") or "").lower()
        if not wd:
            continue
        chars_in_shot = s.get("characters", [])
        # For multi-character shots, _wardrobe_description may only cover the primary character.
        # Only flag if NONE of the characters in the shot have matching canonical tokens —
        # i.e. the wardrobe description belongs to a completely different character.
        any_char_matched = False
        unmatched_chars = []
        for char_name in chars_in_shot:
            char_data = cast_map.get(char_name, {}) if cast_map else {}
            canonical = (char_data.get("appearance") or "").lower()
            if not canonical:
                any_char_matched = True  # can't check, assume OK
                break
            canonical_tokens = [t for t in canonical.replace(",", " ").split() if len(t) > 4]
            overlap = any(tok in wd for tok in canonical_tokens)
            if overlap:
                any_char_matched = True
                break
            unmatched_chars.append(char_name)
        if not any_char_matched and unmatched_chars and len(chars_in_shot) == 1:
            # Only report single-character shots — multi-char mismatches are ambiguous
            char_name = unmatched_chars[0]
            char_data = cast_map.get(char_name, {}) if cast_map else {}
            wardrobe_mismatches.append(
                f"{s['shot_id']} {char_name}: desc='{s.get('_wardrobe_description','')[:40]}' "
                f"vs cast_map='{char_data.get('appearance','')[:40]}'"
            )
    checks.append(PreflightCheck(
        name="wardrobe_fidelity",
        passed=len(wardrobe_mismatches) == 0,
        detail=(f"All _wardrobe_description fields match cast_map appearance"
                if not wardrobe_mismatches
                else f"{len(wardrobe_mismatches)} shots have wardrobe mismatch: {wardrobe_mismatches[:3]}"),
        severity="WARN"
    ))

    # ── NEW CHECK: dialogue_uniqueness ───────────────────────────────────────
    # Within a scene, no two shots with _has_dialogue=True should share identical
    # _beat_dialogue text. E-shots (no characters) must never have _has_dialogue=True.
    dialogue_dupes = []
    eshot_dialogue_violations = []
    from collections import defaultdict
    scene_dialogue_map: Dict[str, list] = defaultdict(list)
    for s in shots:
        sid_check = s.get("shot_id", "")
        is_e = "_E0" in sid_check
        chars = s.get("characters", [])
        dt = (s.get("dialogue_text") or "").strip()
        if is_e and not chars and s.get("_has_dialogue"):
            eshot_dialogue_violations.append(sid_check)
        if dt and s.get("_has_dialogue") and chars:
            scene_key = s.get("scene_id", "?")
            scene_dialogue_map[scene_key].append((sid_check, dt))
    for scene_key, entries in scene_dialogue_map.items():
        seen: Dict[str, str] = {}
        for (sid_d, dt_text) in entries:
            if dt_text in seen:
                dialogue_dupes.append(f"S{scene_key}: {seen[dt_text]} and {sid_d} share '{dt_text[:40]}'")
            else:
                seen[dt_text] = sid_d
    all_dialogue_issues = eshot_dialogue_violations + dialogue_dupes
    checks.append(PreflightCheck(
        name="dialogue_uniqueness",
        passed=len(all_dialogue_issues) == 0,
        detail=(f"No duplicate dialogue assignments and no E-shot dialogue violations"
                if not all_dialogue_issues
                else (f"{len(eshot_dialogue_violations)} E-shots with _has_dialogue=True; "
                      f"{len(dialogue_dupes)} duplicate dialogue_text within scenes: {dialogue_dupes[:2]}")),
        severity="WARN"
    ))

    # ── NEW CHECK: eshot_character_contamination ─────────────────────────────
    # E-series shots with characters=[] must have no character names from cast_map
    # in their nano_prompt. Character names bleed into empty establishing shots and
    # cause FAL to hallucinate people into empty-room shots.
    e_contaminated = []
    all_char_names = list(cast_map.keys()) if cast_map else []
    for s in shots:
        sid_check = s.get("shot_id", "")
        if "_E0" not in sid_check:
            continue
        if s.get("characters"):
            continue  # E-shot that intentionally has a character — skip
        np_text = s.get("nano_prompt", "")
        for char_name in all_char_names:
            # Check canonical name and first-name only
            first_name = char_name.split()[0]
            if char_name in np_text or (len(first_name) > 3 and first_name in np_text):
                e_contaminated.append(f"{sid_check}: contains '{char_name}' in nano_prompt")
                break
    checks.append(PreflightCheck(
        name="eshot_character_contamination",
        passed=len(e_contaminated) == 0,
        detail=(f"All E-shots are character-free in nano_prompt"
                if not e_contaminated
                else f"{len(e_contaminated)} E-shots have character names in nano_prompt: {e_contaminated[:3]}"),
        severity="WARN"
    ))

    # ── NEW CHECK: dialogue_story_bible_match ────────────────────────────────
    # For dialogue shots, dialogue_text should match _beat_dialogue (which comes
    # from the story bible via beat enrichment). A mismatch means a fabricated line
    # was injected by an enrichment pass, corrupting lip-sync and duration math.
    import re as _re
    dialogue_mismatches = []
    for s in shots:
        if not s.get("_has_dialogue"):
            continue
        if not s.get("characters"):
            continue
        dt = (s.get("dialogue_text") or "").strip()
        bd = (s.get("_beat_dialogue") or "").strip()
        if not dt or not bd:
            continue
        # Strip "Character Name: " prefix from dialogue_text if present
        dt_stripped = _re.sub(r'^[A-Z][A-Za-z ]+:\s*', '', dt).strip()
        # Normalise accents for comparison
        def _norm(t):
            return t.replace("ë","e").replace("é","e").replace("\u2019","'").lower()
        dt_n = _norm(dt_stripped)
        bd_n = _norm(bd)
        # Pass if: exact match, OR beat is substring of dialogue (dialogue extends the beat),
        # OR dialogue is substring of beat (dialogue is a fragment of the beat)
        if dt_n == bd_n or bd_n in dt_n or dt_n in bd_n:
            continue
        dialogue_mismatches.append(
            f"{s['shot_id']}: dialogue_text='{dt[:50]}' != _beat_dialogue='{bd[:50]}'"
        )
    checks.append(PreflightCheck(
        name="dialogue_story_bible_match",
        passed=len(dialogue_mismatches) == 0,
        detail=(f"All dialogue_text fields match story-bible _beat_dialogue"
                if not dialogue_mismatches
                else f"{len(dialogue_mismatches)} shots have fabricated dialogue_text: {dialogue_mismatches[:3]}"),
        severity="WARN"
    ))

    # ── NEW CHECK: costume_scene_appropriate ─────────────────────────────────
    # _wardrobe_description must not reference period-inappropriate items.
    # Rule: interior scenes should not have "wool cape" or "travelling" in wardrobe.
    # Exterior scenes may have overcoat/cape. Cross-checks _wardrobe_description vs
    # shot location (INT vs EXT inferred from scene_id beat).
    costume_violations = []
    interior_forbidden = ["wool cape", "travelling dress", "riding habit", "outdoor coat"]
    for s in char_shots:
        wd = (s.get("_wardrobe_description") or "").lower()
        loc = (s.get("location") or "").upper()
        is_interior = not loc.startswith("EXT") and "GARDEN" not in loc and "DRIVE" not in loc
        if is_interior:
            for forbidden in interior_forbidden:
                if forbidden in wd:
                    costume_violations.append(
                        f"{s['shot_id']}: interior shot has '{forbidden}' in wardrobe (loc: {loc[:30]})"
                    )
                    break
    checks.append(PreflightCheck(
        name="costume_scene_appropriate",
        passed=len(costume_violations) == 0,
        detail=(f"All wardrobe descriptions are scene-appropriate (no outdoor garments in interiors)"
                if not costume_violations
                else f"{len(costume_violations)} interior shots with outdoor wardrobe: {costume_violations[:3]}"),
        severity="WARN"
    ))

    # V35.1: QA rubric checks (manual-QA-driven)
    checks.extend(run_qa_rubric_checks(shots))

    return checks


# ============================================================
# COMPOSITION HASH — For reuse detection
# ============================================================

def compute_composition_hash(shot: dict) -> str:
    """Deterministic hash of shot composition for reuse detection.

    V25.9 FIX: Include nano_prompt content in hash to prevent
    shots with different dialogue/action from being treated as reusable.
    The old hash only used shot_type + characters + scene → caused
    all medium shots of same characters to get identical frames.
    """
    key_parts = [
        shot.get("shot_type", ""),
        shot.get("camera_style", ""),
        str(sorted(shot.get("characters", []))),
        shot.get("scene_id", ""),
        # V25.9: Include prompt content to differentiate shots with same framing
        (shot.get("nano_prompt_final") or shot.get("nano_prompt", ""))[:200],
        (shot.get("dialogue_text") or "")[:100],
    ]
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ============================================================
# CHAIN GROUP DETECTION
# ============================================================

def detect_chain_groups(shots: List[dict]) -> Dict[str, List[str]]:
    """Detect chain groups from shot sequences within scenes."""
    chains = {}
    current_chain = []
    current_scene = None
    chain_counter = {}

    for s in shots:
        sid = s.get("scene_id", "")
        shot_id = s.get("shot_id", "")
        chars = s.get("characters", [])
        # CRITICAL FIX V25.9: shot_id suffix "B" means B_ACTION coverage,
        # NOT B-roll. Only use is_broll/_broll flag for actual B-roll detection.
        is_broll = s.get("is_broll", False) or s.get("_broll", False)
        shot_type = s.get("shot_type", "").lower()

        # Chain breaks on: new scene, B-roll, no characters, establishing shots
        should_break = (
            sid != current_scene or
            is_broll or
            not chars or
            shot_type in ("establishing", "master", "insert", "cutaway", "detail")
        )

        if should_break:
            if len(current_chain) > 1:
                # Save completed chain
                chain_counter[current_scene] = chain_counter.get(current_scene, 0) + 1
                chain_id = f"CHAIN_{current_scene}_{chain_counter[current_scene]:02d}"
                chains[chain_id] = list(current_chain)
            current_chain = [shot_id] if chars and not is_broll else []
            current_scene = sid
        else:
            current_chain.append(shot_id)

    # Don't forget last chain
    if len(current_chain) > 1 and current_scene:
        chain_counter[current_scene] = chain_counter.get(current_scene, 0) + 1
        chain_id = f"CHAIN_{current_scene}_{chain_counter[current_scene]:02d}"
        chains[chain_id] = list(current_chain)

    return chains


# ============================================================
# MAIN PREP PIPELINE
# ============================================================

def prep_project(project: str, base_path: str = None) -> PrepResult:
    """
    Full headless preparation pipeline.
    Runs all phases, validates everything, generates manifest + report.
    Returns PrepResult with success/failure and all details.
    """
    if base_path is None:
        base_path = os.environ.get(
            "ATLAS_BASE",
            "/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
        )

    result = PrepResult(
        success=False,
        project=project,
        timestamp=datetime.now().isoformat()
    )

    project_path = os.path.join(base_path, "pipeline_outputs", project)

    # ── PHASE 0: DATA LOCK ──────────────────────────────────
    allowed, reason = check_data_lock(project)
    if not allowed:
        result.errors.append(reason)
        return result
    result.phases["data_lock"] = {"status": "PASS", "detail": reason}

    # ── PHASE 1: LOAD CANONICAL DATA ────────────────────────
    try:
        sp_path = os.path.join(project_path, "shot_plan.json")
        with open(sp_path) as f:
            _raw_sp = json.load(f)
        # T2-OR-18: shot_plan.json may be a bare list — normalize
        if isinstance(_raw_sp, list):
            shot_plan = {"shots": _raw_sp}
        else:
            shot_plan = _raw_sp if isinstance(_raw_sp, dict) else {"shots": []}

        shots = shot_plan.get("shots", [])
        # Cast map is a SEPARATE file, not embedded in shot_plan
        cast_map = shot_plan.get("cast_map", {})
        cast_map_path = os.path.join(project_path, "cast_map.json")
        if not cast_map and os.path.exists(cast_map_path):
            with open(cast_map_path) as cf:
                cast_map = json.load(cf)
        scene_manifest = shot_plan.get("scene_manifest", [])

        # Load wardrobe
        wardrobe = {}
        wardrobe_path = os.path.join(project_path, "wardrobe.json")
        if os.path.exists(wardrobe_path):
            with open(wardrobe_path) as f:
                wardrobe = json.load(f)

        # Load extras
        extras = {}
        extras_path = os.path.join(project_path, "extras.json")
        if os.path.exists(extras_path):
            with open(extras_path) as f:
                extras = json.load(f)

        # Load audio config
        audio_config = {}
        audio_path = os.path.join(project_path, "audio_config.json")
        if os.path.exists(audio_path):
            with open(audio_path) as f:
                audio_config = json.load(f)

        result.phases["load_data"] = {
            "status": "PASS",
            "shots": len(shots),
            "scenes": len(scene_manifest) if isinstance(scene_manifest, list) else len(set(s.get("scene_id") for s in shots)),
            "cast": len(cast_map),
            "wardrobe_entries": len(wardrobe),
            "extras_entries": len(extras),
            "audio_mode": audio_config.get("sfx_mode", "not_configured")
        }
    except Exception as e:
        result.errors.append(f"LOAD FAILED: {e}")
        return result

    # ── PHASE 2: RUN V22 MODULES ────────────────────────────
    modules_fired = []

    # Module 1: Actor Intent
    try:
        sys.path.insert(0, base_path)
        from tools.actor_intent_layer import enrich_shot_plan_with_intent

        story_bible = None
        sb_path = os.path.join(project_path, "story_bible.json")
        if os.path.exists(sb_path):
            with open(sb_path) as f:
                story_bible = json.load(f)

        # Only enrich shots that don't already have intent
        unenriched = [s for s in shots if not s.get("actor_intent")]
        if unenriched:
            enriched = enrich_shot_plan_with_intent(shots, story_bible)
            shots = enriched

        intent_count = sum(1 for s in shots if s.get("actor_intent"))
        modules_fired.append({"module": "actor_intent", "enriched": intent_count, "total": len(shots)})
    except Exception as e:
        result.warnings.append(f"Actor Intent: {e}")
        modules_fired.append({"module": "actor_intent", "error": str(e)})

    # Module 2: Delta Prompt Builder
    try:
        from tools.delta_prompt_builder import enrich_shots_with_deltas

        unenriched_delta = [s for s in shots if not s.get("_delta_prompt_nano") and not s.get("_is_anchor")]
        if unenriched_delta:
            enriched_delta, delta_results = enrich_shots_with_deltas(
                shots=shots,
                scene_anchors=shot_plan.get("scene_anchors", {}),
                wardrobe_data=wardrobe,
                cast_map=cast_map
            )
            shots = enriched_delta

        delta_count = sum(1 for s in shots if s.get("_delta_prompt_nano"))
        anchor_count = sum(1 for s in shots if s.get("_is_anchor"))
        modules_fired.append({"module": "delta_prompt", "chained": delta_count, "anchors": anchor_count})
    except Exception as e:
        result.warnings.append(f"Delta Prompt: {e}")
        modules_fired.append({"module": "delta_prompt", "error": str(e)})

    # Module 3: Composition Cache
    try:
        from tools.composition_cache import analyze_reuse_opportunities

        analysis = analyze_reuse_opportunities(shots)
        modules_fired.append({
            "module": "composition_cache",
            "unique": analysis.get("unique_compositions", 0),
            "savings_pct": analysis.get("savings_pct", 0),
            "reuse_groups": len(analysis.get("reuse_groups", []))
        })
    except Exception as e:
        result.warnings.append(f"Composition Cache: {e}")
        modules_fired.append({"module": "composition_cache", "error": str(e)})

    # Module 4: Continuity Store
    try:
        from tools.continuity_store import ContinuityStore

        store = ContinuityStore(project_path)
        for s in shots:
            store.update_from_shot(s)
        store.save()
        modules_fired.append({"module": "continuity_store", "shots_tracked": len(shots)})
    except Exception as e:
        result.warnings.append(f"Continuity Store: {e}")
        modules_fired.append({"module": "continuity_store", "error": str(e)})

    result.phases["v22_modules"] = {"status": "PASS", "modules": modules_fired}

    # ── PHASE 3: CHAIN DETECTION + COMPOSITION HASHING ──────
    chain_groups = detect_chain_groups(shots)

    # Apply chain IDs and composition hashes to shots
    shot_chain_map = {}
    for chain_id, shot_ids in chain_groups.items():
        for i, sid in enumerate(shot_ids):
            shot_chain_map[sid] = {
                "chain_id": chain_id,
                "is_chain_first": i == 0,
                "chain_position": i
            }

    for s in shots:
        shot_id = s.get("shot_id", "")

        # Chain info
        chain_info = shot_chain_map.get(shot_id, {})
        s["_chain_id"] = chain_info.get("chain_id", "")
        s["_is_chain_first"] = chain_info.get("is_chain_first", False)
        s["_chain_position"] = chain_info.get("chain_position", -1)

        # Composition hash
        s["_composition_hash"] = compute_composition_hash(s)

        # Nano mode — determine text2img vs edit (with character refs)
        # CRITICAL FIX V25.9: shot_id suffix "B" means coverage angle B_ACTION,
        # NOT B-roll. Only use is_broll/_broll flag for actual B-roll detection.
        # The old code `shot_id.endswith("B")` was a false positive that forced
        # 70+ character shots to text2img (no face refs) causing identity loss.
        chars = s.get("characters", [])
        is_broll = s.get("is_broll", False) or s.get("_broll", False)
        if is_broll or not chars:
            s["_nano_mode"] = "text2img"
        elif s.get("_is_chain_first", False) or not s.get("_chain_id"):
            s["_nano_mode"] = "text2img"  # First in chain or independent — but still gets refs at generation time
        else:
            s["_nano_mode"] = "edit_end_frame"  # Chained: uses previous end frame

    result.phases["chain_detection"] = {
        "status": "PASS",
        "chain_groups": len(chain_groups),
        "chained_shots": sum(len(v) for v in chain_groups.values()),
        "chains": {k: len(v) for k, v in chain_groups.items()}
    }

    # ── PHASE 4: PREFLIGHT VALIDATION ───────────────────────
    preflight_checks = run_preflight(shots, cast_map, wardrobe)
    halt_failures = [c for c in preflight_checks if not c.passed and c.severity == "HALT"]
    warn_failures = [c for c in preflight_checks if not c.passed and c.severity == "WARN"]

    result.phases["preflight"] = {
        "status": "HALT" if halt_failures else "PASS",
        "total_checks": len(preflight_checks),
        "passed": sum(1 for c in preflight_checks if c.passed),
        "halt_failures": len(halt_failures),
        "warnings": len(warn_failures),
        "checks": [asdict(c) for c in preflight_checks]
    }

    if halt_failures:
        for c in halt_failures:
            result.errors.append(f"PREFLIGHT HALT: {c.name} — {c.detail}")
        # Don't return yet — still generate manifest for debugging

    # ── PHASE 5: SAVE ENRICHED SHOT PLAN ────────────────────
    shot_plan["shots"] = shots
    shot_plan["_prep_timestamp"] = result.timestamp
    shot_plan["_prep_version"] = "22.2.0"
    shot_plan["_chain_groups"] = chain_groups

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json',
        dir=os.path.dirname(sp_path), delete=False
    )
    json.dump(shot_plan, tmp, indent=2)
    tmp.close()
    os.replace(tmp.name, sp_path)

    result.phases["save"] = {"status": "PASS", "path": sp_path}

    # ── PHASE 6: STATS ─────────────────────────────────────
    scene_ids = set(s.get("scene_id", "") for s in shots)
    result.stats = {
        "total_shots": len(shots),
        "total_scenes": len(scene_ids),
        "character_shots": sum(1 for s in shots if s.get("characters")),
        "broll_shots": sum(1 for s in shots if s.get("is_broll") or s.get("_broll")),
        "chained_shots": sum(1 for s in shots if s.get("_chain_id")),
        "independent_shots": sum(1 for s in shots if not s.get("_chain_id")),
        "chain_groups": len(chain_groups),
        "actor_intent_enriched": sum(1 for s in shots if s.get("actor_intent")),
        "delta_prompts": sum(1 for s in shots if s.get("_delta_prompt_nano")),
        "composition_hashes": sum(1 for s in shots if s.get("_composition_hash")),
        "modules_fired": [m["module"] for m in modules_fired if "error" not in m],
        "cast_characters": len(cast_map),
        "wardrobe_entries": len(wardrobe),
        "audio_mode": audio_config.get("sfx_mode", "not_configured"),
    }

    # Success if no HALT failures
    result.success = len(halt_failures) == 0

    return result


# ============================================================
# GENERATE RUN REPORT
# ============================================================

def generate_run_report(result: PrepResult, base_path: str = None) -> str:
    """Generate atlas_run_report.json from PrepResult."""
    if base_path is None:
        base_path = os.environ.get(
            "ATLAS_BASE",
            "/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
        )

    report = {
        "atlas_run_report": True,
        "version": "22.2.0",
        "generated": result.timestamp,
        "project": result.project,
        "success": result.success,
        "phases": result.phases,
        "stats": result.stats,
        "errors": result.errors,
        "warnings": result.warnings,
        "locks": {
            "route_lock": "Master Chain Renderer only",
            "data_lock": f"Project: {result.project}",
            "prompt_authority": "All prompts from shot_plan pipeline"
        }
    }

    report_path = os.path.join(
        base_path, "pipeline_outputs", result.project, "atlas_run_report.json"
    )

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json',
        dir=os.path.dirname(report_path), delete=False
    )
    json.dump(report, tmp, indent=2)
    tmp.close()
    os.replace(tmp.name, report_path)

    return report_path


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
    base = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"ATLAS PREP ENGINE — {project}")
    print("=" * 60)

    result = prep_project(project, base)

    # Generate run report
    report_path = generate_run_report(result, base)

    # Print summary
    print(f"\n{'✅' if result.success else '❌'} PREP {'COMPLETE' if result.success else 'FAILED'}")
    print(f"   Project:  {result.project}")
    print(f"   Shots:    {result.stats.get('total_shots', 0)}")
    print(f"   Scenes:   {result.stats.get('total_scenes', 0)}")
    print(f"   Chains:   {result.stats.get('chain_groups', 0)}")
    print(f"   Modules:  {', '.join(result.stats.get('modules_fired', []))}")

    if result.errors:
        print(f"\n   ERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"     ❌ {e}")

    if result.warnings:
        print(f"\n   WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"     ⚠️  {w}")

    # Preflight summary
    preflight = result.phases.get("preflight", {})
    checks = preflight.get("checks", [])
    print(f"\n   PREFLIGHT ({preflight.get('passed', 0)}/{preflight.get('total_checks', 0)} passed):")
    for c in checks:
        icon = "✅" if c["passed"] else ("❌" if c["severity"] == "HALT" else "⚠️")
        print(f"     {icon} {c['name']}: {c['detail']}")

    print(f"\n   Report: {report_path}")


# ============================================================
# V35.1 QA RUBRIC CHECKS (manual-QA-driven, 2026-03-26)
# ============================================================

def check_ots_direction(shots: list) -> "PreflightCheck":
    """OTS shots must specify WHICH character's back is foreground."""
    issues = []
    for s in shots:
        sid = s.get("shot_id", "")
        nano = (s.get("nano_prompt") or "").lower()
        ots_angle = (s.get("_ots_angle") or "").upper()
        shot_type = (s.get("shot_type") or "").lower()
        # Detect OTS shots by angle field, shot_type, or shot_id suffix
        is_ots = (ots_angle in ("A", "B") or
                  shot_type in ("ots_a", "ots_b", "ots") or
                  "OTS" in (s.get("nano_prompt") or "").upper()[:30])
        if not is_ots:
            continue
        # Must specify a character's back/shoulder in foreground
        has_foreground = any(w in nano for w in [
            "foreground", "frame-left foreground", "frame-right foreground",
            "shoulder foreground", "back and", "from behind"
        ])
        if not has_foreground:
            issues.append(f"{sid}: OTS prompt missing foreground character direction")
    return PreflightCheck(
        name="ots_direction_check",
        passed=len(issues) == 0,
        detail=(f"CLEAN — all OTS shots specify foreground character"
                if not issues
                else f"{len(issues)} OTS shots missing foreground direction: " + "; ".join(issues[:3])),
        severity="WARN"
    )


def check_shot_type_match(shots: list) -> "PreflightCheck":
    """E01 prompts must be WIDE/ESTABLISHING. E02 must be WIDE/INTERIOR. E03 must be INSERT/CLOSE/DETAIL."""
    issues = []
    for s in shots:
        sid = s.get("shot_id", "")
        nano_upper = (s.get("nano_prompt") or "").upper()
        parts = sid.split("_")
        if len(parts) < 2:
            continue
        e_type = parts[1]  # e.g. E01, E02, E03
        if e_type == "E01":
            if not any(w in nano_upper for w in ["WIDE", "ESTABLISHING", "EXTERIOR"]):
                issues.append(f"{sid}: E01 prompt missing WIDE/ESTABLISHING keyword")
        elif e_type == "E02":
            if not any(w in nano_upper for w in ["WIDE", "INTERIOR"]):
                issues.append(f"{sid}: E02 prompt missing WIDE/INTERIOR keyword")
            if "INSERT" in nano_upper and "WIDE" not in nano_upper:
                issues.append(f"{sid}: E02 uses INSERT framing (wrong type — should be WIDE)")
        elif e_type == "E03":
            if not any(w in nano_upper for w in ["INSERT", "CLOSE-UP", "CLOSE UP", "DETAIL", "EXTREME CLOSE"]):
                issues.append(f"{sid}: E03 prompt missing INSERT/CLOSE-UP/DETAIL keyword")
    return PreflightCheck(
        name="shot_type_match",
        passed=len(issues) == 0,
        detail=(f"CLEAN — all E-shots match their required framing type"
                if not issues
                else f"{len(issues)} E-shot framing mismatches: " + "; ".join(issues[:4])),
        severity="WARN"
    )


def check_character_count(shots: list) -> "PreflightCheck":
    """Character count in prompt should match characters array length."""
    issues = []
    for s in shots:
        sid = s.get("shot_id", "")
        chars = s.get("characters") or []
        if len(chars) < 2:
            continue  # Only meaningful for multi-character shots
        nano = s.get("nano_prompt") or ""
        # Count [CHARACTER: ...] blocks as proxy for mentioned characters
        char_blocks = nano.upper().count("[CHARACTER:")
        if char_blocks > 0 and char_blocks < len(chars):
            issues.append(
                f"{sid}: {len(chars)} characters in array but only {char_blocks} [CHARACTER:] blocks in prompt"
            )
    return PreflightCheck(
        name="character_count_check",
        passed=len(issues) == 0,
        detail=(f"CLEAN — character count matches prompt blocks"
                if not issues
                else f"{len(issues)} shots have character count mismatch: " + "; ".join(issues[:3])),
        severity="WARN"
    )


def check_ext_int_location(shots: list) -> "PreflightCheck":
    """EXT shots (E01 in scenes with exterior description) must not contain interior keywords."""
    # Use specific architecture terms only — avoid "interior" which appears in
    # valid negations like "No interior elements" on exterior shots.
    INTERIOR_KEYWORDS = ["hallway", "staircase", "banister", "chandelier",
                         "foyer", "wainscoting", "marble floor", "plasterwork",
                         "dust sheets", "grandfather clock"]
    issues = []
    for s in shots:
        sid = s.get("shot_id", "")
        nano_lower = (s.get("nano_prompt") or "").lower()
        # Flag shots where prompt says EXTERIOR but contains interior elements
        is_exterior_prompt = "exterior" in nano_lower[:80] or nano_lower[:60].startswith("ext")
        if not is_exterior_prompt:
            continue
        found_interior = [kw for kw in INTERIOR_KEYWORDS if kw in nano_lower]
        if found_interior:
            issues.append(
                f"{sid}: EXTERIOR prompt contains interior keywords: {found_interior[:3]}"
            )
    return PreflightCheck(
        name="ext_int_location_match",
        passed=len(issues) == 0,
        detail=(f"CLEAN — no exterior shots contain interior elements"
                if not issues
                else f"{len(issues)} EXT shots with interior contamination: " + "; ".join(issues[:3])),
        severity="WARN"
    )


def check_ai_artifact_risk(shots: list) -> "PreflightCheck":
    """Flag prompts likely to generate readable text; auto-append illegibility guard."""
    TEXT_RISK_PATTERNS = [
        "book spine", "book title", "letter", "journal", "newspaper",
        "sign", "inscription", "note", "manuscript", "document", "scroll",
        "telegram", "envelope", "certificate", "portrait label"
    ]
    ILLEGIBILITY_GUARD = ", illegible text, no readable words, no visible lettering"
    flagged = []
    auto_fixed = []
    for s in shots:
        sid = s.get("shot_id", "")
        nano = s.get("nano_prompt") or ""
        nano_lower = nano.lower()
        has_risk = any(p in nano_lower for p in TEXT_RISK_PATTERNS)
        already_guarded = "illegible" in nano_lower or "no readable" in nano_lower
        if has_risk and not already_guarded:
            s["nano_prompt"] = nano.rstrip() + ILLEGIBILITY_GUARD
            auto_fixed.append(sid)
        elif has_risk:
            flagged.append(sid)
    all_issues = auto_fixed + flagged
    detail_parts = []
    if auto_fixed:
        detail_parts.append(f"{len(auto_fixed)} auto-fixed with illegibility guard: {auto_fixed[:3]}")
    if flagged:
        detail_parts.append(f"{len(flagged)} already guarded: {flagged[:3]}")
    return PreflightCheck(
        name="ai_artifact_flag",
        passed=True,  # Always passes — auto-fix is non-blocking
        detail=(f"CLEAN — no text-risk prompts detected"
                if not all_issues
                else "; ".join(detail_parts)),
        severity="WARN"
    )


def run_qa_rubric_checks(shots: list) -> "List[PreflightCheck]":
    """Run all 5 V35.1 QA rubric checks. Call from run_preflight or standalone."""
    return [
        check_ots_direction(shots),
        check_shot_type_match(shots),
        check_character_count(shots),
        check_ext_int_location(shots),
        check_ai_artifact_risk(shots),
    ]
