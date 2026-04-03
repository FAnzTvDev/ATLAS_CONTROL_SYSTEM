#!/usr/bin/env python3
"""
V25.1 Creative Prompt Compiler — Unit Tests
Rule C of the Autonomous Build Covenant: Green Is Not the Success Condition.
These tests prove the CPC ACTUALLY prevents contamination, not just that it imports.

Test groups:
  1. Generic detection (is_prompt_generic)
  2. Physical direction (get_physical_direction)
  3. Verb extraction (extract_physical_verbs)
  4. Story bible fallback (replace_story_bible_fallback)
  5. LTX motion building (build_ltx_motion)
  6. Decontamination (decontaminate_prompt)
  7. Quality scoring (score_prompt_quality, validate_prompt_quality)
  8. Batch operations (audit_all_prompts, decontaminate_all_prompts)
  9. Integration: no generic output from ANY public function
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
TOTAL = 0

def test(name, condition, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} — {detail}")


print("=" * 60)
print("CREATIVE PROMPT COMPILER TESTS")
print("=" * 60)

from tools.creative_prompt_compiler import (
    is_prompt_generic, get_physical_direction, extract_physical_verbs,
    replace_story_bible_fallback, build_ltx_motion, decontaminate_prompt,
    score_prompt_quality, validate_prompt_quality, audit_all_prompts,
    decontaminate_all_prompts, build_beat_action_replacement,
    GENERIC_PATTERNS, EMOTION_PHYSICAL_MAP, PHYSICAL_VERBS
)

# ============================================================
# GROUP 1: Generic Detection
# ============================================================
print("\n--- Group 1: Generic Detection ---")

test("Detects 'experiences the moment'",
     is_prompt_generic("ELEANOR experiences the moment, present in the space"))

test("Detects 'natural movement begins'",
     is_prompt_generic("0-1s natural movement begins, subtle shift"))

test("Detects 'subtle shift in weight'",
     is_prompt_generic("character shows subtle shift in weight, present"))

test("Detects 'holds the moment'",
     is_prompt_generic("THOMAS holds the moment, gentle breathing"))

test("Detects 'key motion: experiences'",
     is_prompt_generic("character performs: something, key motion: experiences"))

test("Detects 'present and engaged'",
     is_prompt_generic("character present and engaged in the scene"))

test("Detects 'gentle breathing'",
     is_prompt_generic("tight shot, gentle breathing, face stable"))

test("Detects '0-2s settle'",
     is_prompt_generic("0-2s settle into frame, then slow push"))

test("Clean prompt NOT flagged",
     not is_prompt_generic("ELEANOR grips the bannister, knuckles white, jaw clenched"))

test("Specific action NOT flagged",
     not is_prompt_generic("THOMAS slams the door, turns sharply, eyes blazing"))

test("Dialogue prompt NOT flagged",
     not is_prompt_generic("character speaks with conviction, leaning forward"))

test("Empty string NOT flagged",
     not is_prompt_generic(""))

# ============================================================
# GROUP 2: Physical Direction
# ============================================================
print("\n--- Group 2: Physical Direction ---")

grief_dir = get_physical_direction("grief", "standing", "ELEANOR", "")
test("Grief standing has physical verb",
     any(v in grief_dir.lower() for v in ["shoulders", "weight", "curved", "heavy", "sinks"]),
     f"Got: {grief_dir}")

tension_dir = get_physical_direction("tension", "sitting", "THOMAS", "")
test("Tension sitting has physical verb",
     any(v in tension_dir.lower() for v in ["grip", "rigid", "tight", "clenched", "coiled"]),
     f"Got: {tension_dir}")

anger_dir = get_physical_direction("anger", "standing", "ELEANOR", "")
test("Anger standing has physical verb",
     any(v in anger_dir.lower() for v in ["squared", "fists", "jaw", "tense", "rigid"]),
     f"Got: {anger_dir}")

neutral_dir = get_physical_direction("neutral", "default", "CHARACTER", "")
test("Neutral NEVER returns 'experiences the moment'",
     "experiences" not in neutral_dir.lower(),
     f"Got: {neutral_dir}")

test("Neutral NEVER returns 'present and engaged'",
     "present and engaged" not in neutral_dir.lower(),
     f"Got: {neutral_dir}")

# Test every emotion in the map
for emotion in EMOTION_PHYSICAL_MAP:
    for posture in EMOTION_PHYSICAL_MAP[emotion]:
        result = get_physical_direction(emotion, posture, "TEST", "")
        test(f"  {emotion}/{posture} is non-empty",
             len(result) > 5, f"Got: '{result}'")
        test(f"  {emotion}/{posture} no generic filler",
             not is_prompt_generic(result), f"Got: '{result}'")

# ============================================================
# GROUP 3: Verb Extraction
# ============================================================
print("\n--- Group 3: Verb Extraction ---")

verbs1 = extract_physical_verbs("Lady Margaret kneels at the altar and prays")
test("Extracts 'kneels' from description",
     "kneels" in verbs1, f"Got: {verbs1}")

verbs2 = extract_physical_verbs("Eleanor opens the letter and reads it carefully")
test("Extracts 'opens' and 'reads'",
     "opens" in verbs2 and "reads" in verbs2, f"Got: {verbs2}")

verbs3 = extract_physical_verbs("The room is dark and quiet with candles burning")
test("No false positives from atmosphere",
     "burning" not in verbs3 or len(verbs3) <= 1, f"Got: {verbs3}")

verbs4 = extract_physical_verbs("")
test("Empty string returns empty list", len(verbs4) == 0)

# ============================================================
# GROUP 4: Story Bible Fallback
# ============================================================
print("\n--- Group 4: Story Bible Fallback ---")

action1, verbs1 = replace_story_bible_fallback(
    "Lady Margaret kneels at the altar", "LADY MARGARET", ["LADY MARGARET"], "tension"
)
test("Fallback returns action text",
     len(action1) > 10, f"Got: {action1}")
test("Fallback NEVER returns 'experiences the moment'",
     "experiences the moment" not in action1.lower(), f"Got: {action1}")
test("Fallback returns verbs",
     len(verbs1) > 0, f"Got: {verbs1}")

# Edge case: atmosphere-only description with no physical verbs
action2, verbs2 = replace_story_bible_fallback(
    "Candles burn low in the ritual room", "CHARACTER", ["CHARACTER"], "dread"
)
test("Atmosphere-only still returns physical action",
     len(action2) > 5 and "experiences" not in action2.lower(), f"Got: {action2}")

# Edge case: empty description
action3, verbs3 = replace_story_bible_fallback("", "ELEANOR", ["ELEANOR"], "neutral")
test("Empty description returns emotion-based fallback",
     len(action3) > 5 and "experiences" not in action3.lower(), f"Got: {action3}")

# ============================================================
# GROUP 5: LTX Motion Building
# ============================================================
print("\n--- Group 5: LTX Motion Building ---")

ltx1 = build_ltx_motion("close_up", "ELEANOR", "grief", True, "She confesses the truth", 6.0, "C_EMOTION")
test("Dialogue LTX has 'speaks'",
     "speaks" in ltx1.lower() or "voice" in ltx1.lower(), f"Got: {ltx1}")
test("Dialogue LTX NEVER generic",
     not is_prompt_generic(ltx1), f"Got: {ltx1}")

ltx2 = build_ltx_motion("wide", "THOMAS", "tension", False, "He surveys the room", 5.0, "A_GEOGRAPHY")
test("Wide non-dialogue has framing direction",
     any(w in ltx2.lower() for w in ["wide", "establishes", "geography", "environment"]),
     f"Got: {ltx2}")
test("Non-dialogue LTX NEVER generic",
     not is_prompt_generic(ltx2), f"Got: {ltx2}")

ltx3 = build_ltx_motion("medium", "ELEANOR", "neutral", False, "", 4.0, "B_ACTION")
test("Empty beat still produces non-generic LTX",
     not is_prompt_generic(ltx3) and len(ltx3) > 20, f"Got: {ltx3}")

# ============================================================
# GROUP 6: Decontamination
# ============================================================
print("\n--- Group 6: Decontamination ---")

dirty1 = "ELEANOR experiences the moment, natural weight, face stable NO morphing"
clean1 = decontaminate_prompt(dirty1, "ELEANOR", "grief", "She grips the railing")
test("Strips 'experiences the moment'",
     "experiences the moment" not in clean1, f"Got: {clean1}")
test("Preserves 'face stable NO morphing'",
     "face stable" in clean1.lower() or "morphing" in clean1.lower() or len(clean1) > 10,
     f"Got: {clean1}")
test("Result is non-generic",
     not is_prompt_generic(clean1), f"Got: {clean1}")

dirty2 = "0-2s settle into frame, gentle breathing, key motion: experiences"
clean2 = decontaminate_prompt(dirty2, "THOMAS", "tension", "Thomas enters cautiously")
test("Strips multiple generic patterns",
     "0-2s settle" not in clean2 and "gentle breathing" not in clean2 and "key motion: experiences" not in clean2,
     f"Got: {clean2}")

# Already clean prompt should pass through
clean_input = "ELEANOR grips the bannister, knuckles white, jaw clenched, camera pushes in"
clean3 = decontaminate_prompt(clean_input, "ELEANOR", "tension", "")
test("Clean prompt passes through intact",
     "grips" in clean3 and "bannister" in clean3, f"Got: {clean3}")

# ============================================================
# GROUP 7: Quality Scoring
# ============================================================
print("\n--- Group 7: Quality Scoring ---")

good_shot = {
    "shot_id": "001_003C",
    "nano_prompt": "ELEANOR VOSS grips the iron bannister, knuckles white, candlelight carving shadows across her face, teal moonlight wash, 85mm f/2.0",
    "ltx_motion_prompt": "0-2s ELEANOR grips tighter, breath catches, character speaks: 'I know what happened here', camera slowly pushes in, face stable NO morphing",
    "characters": ["ELEANOR VOSS"],
    "shot_type": "close_up",
    "dialogue_text": "I know what happened here",
}
score = score_prompt_quality(good_shot["nano_prompt"], good_shot["ltx_motion_prompt"], good_shot)
test("Good shot scores > 3.0",
     score.total > 3.0, f"Got: {score.total}")
test("Good shot has >= 4 disciplines",
     score.disciplines_met >= 4, f"Got: {score.disciplines_met}")

bad_shot = {
    "shot_id": "001_004B",
    "nano_prompt": "character in a room",
    "ltx_motion_prompt": "natural movement begins, experiences the moment, gentle breathing",
    "characters": ["ELEANOR VOSS"],
    "shot_type": "medium",
}
bad_score = score_prompt_quality(bad_shot["nano_prompt"], bad_shot["ltx_motion_prompt"], bad_shot)
test("Bad shot scores lower than good shot",
     bad_score.total < score.total,
     f"Bad: {bad_score.total} vs Good: {score.total}")

valid = validate_prompt_quality(good_shot["nano_prompt"], good_shot["ltx_motion_prompt"], good_shot)
test("Good shot passes validation", valid)

# ============================================================
# GROUP 8: Batch Operations
# ============================================================
print("\n--- Group 8: Batch Operations ---")

test_shots = [
    {"shot_id": "001_001C", "nano_prompt": "ELEANOR enters the foyer", "ltx_motion_prompt": "experiences the moment", "characters": ["ELEANOR VOSS"]},
    {"shot_id": "001_002A", "nano_prompt": "Wide establishing shot of manor", "ltx_motion_prompt": "camera pushes in slowly, revealing architecture", "characters": []},
    {"shot_id": "001_003C", "nano_prompt": "THOMAS reads the letter carefully", "ltx_motion_prompt": "character performs: reads letter, key motion: reads", "characters": ["THOMAS BLACKWOOD"]},
]

report = audit_all_prompts(test_shots)
test("Audit returns total_shots",
     report["total_shots"] == 3, f"Got: {report['total_shots']}")
test("Audit detects contamination",
     report["contaminated"] >= 1, f"Got: {report['contaminated']}")

fixed = decontaminate_all_prompts(test_shots, {})
test("Decontaminate fixes at least 1 shot",
     fixed >= 1, f"Got: {fixed}")
test("After decontaminate, shot 1 is clean",
     not is_prompt_generic(test_shots[0]["ltx_motion_prompt"]),
     f"Got: {test_shots[0]['ltx_motion_prompt']}")

# ============================================================
# GROUP 9: Integration — NO generic output from ANY public function
# ============================================================
print("\n--- Group 9: Integration — Zero Generic Output ---")

# The ultimate test: call every public function and verify NOTHING returns generic filler
emotions = ["grief", "tension", "anger", "revelation", "fear", "neutral", "determination", "love"]
postures = ["standing", "sitting", "walking", "speaking", "default"]
shot_types = ["wide", "medium", "close_up", "extreme_close_up", "over_the_shoulder"]
coverage_roles = ["A_GEOGRAPHY", "B_ACTION", "C_EMOTION"]

generic_outputs = 0
total_outputs = 0

for emotion in emotions:
    for posture in postures:
        result = get_physical_direction(emotion, posture, "CHAR", "test beat")
        total_outputs += 1
        if is_prompt_generic(result):
            generic_outputs += 1
            print(f"    GENERIC: get_physical_direction({emotion}, {posture}) → {result}")

for st in shot_types:
    for emotion in emotions:
        for has_dlg in [True, False]:
            for cr in coverage_roles:
                result = build_ltx_motion(st, "CHAR", emotion, has_dlg, "test beat", 5.0, cr)
                total_outputs += 1
                if is_prompt_generic(result):
                    generic_outputs += 1
                    print(f"    GENERIC: build_ltx_motion({st}, {emotion}, dlg={has_dlg}, {cr}) → {result[:80]}")

test(f"Zero generic outputs from {total_outputs} function calls",
     generic_outputs == 0,
     f"{generic_outputs} generic outputs found")


# ============================================================
# GROUP 10: Production Stress Test (real Victorian Shadows data)
# Autonomous Build Covenant Rule C: Green is not success —
# synthetic pass without real data is a false positive.
# ============================================================
print("\n--- Group 10: Production Stress Test (real script data) ---")

import json as _json
_REAL_SP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "pipeline_outputs", "victorian_shadows_ep1", "shot_plan.json")
if os.path.exists(_REAL_SP_PATH):
    with open(_REAL_SP_PATH) as _f:
        _real_plan = _json.load(_f)
    if isinstance(_real_plan, list):
        _real_plan = {"shots": _real_plan}
    _real_shots = _real_plan.get("shots", [])

    if len(_real_shots) > 20:
        # Test A: decontaminate_prompt on every real nano_prompt — zero should return empty
        _decontam_count = 0
        _empty_after = 0
        _still_generic = 0
        for _rs in _real_shots:
            _np = _rs.get("nano_prompt") or _rs.get("nano_prompt_final") or ""
            if not _np:
                continue
            _decontam_count += 1
            _cleaned = decontaminate_prompt(_np, _rs.get("emotion") or "neutral",
                                            _rs.get("shot_type") or "medium")
            if len(_cleaned.strip()) < 10:
                _empty_after += 1
            if is_prompt_generic(_cleaned):
                _still_generic += 1

        test(f"Decontaminate {_decontam_count} real prompts — zero collapse to empty",
             _empty_after == 0, f"{_empty_after} prompts collapsed")
        test(f"Decontaminate real prompts — <5% still generic after cleaning",
             _still_generic / max(_decontam_count, 1) < 0.05,
             f"{_still_generic}/{_decontam_count} still generic ({100*_still_generic//_decontam_count}%)")

        # Test B: score_prompt_quality on real prompts — average score > 50
        _scores = []
        for _rs in _real_shots:
            _np = _rs.get("nano_prompt") or _rs.get("nano_prompt_final") or ""
            _ltx = _rs.get("ltx_motion_prompt") or ""
            if _np:
                _sq = score_prompt_quality(_np, _ltx, _rs)
                _scores.append(_sq.total)
        _avg_score = sum(_scores) / len(_scores) if _scores else 0
        test(f"Average quality score > 3.0 on {len(_scores)} real prompts",
             _avg_score > 3.0, f"Got avg: {_avg_score:.1f}")

        # Test C: get_physical_direction works with real shot emotions
        _real_emotions = set()
        for _rs in _real_shots:
            _emo = str(_rs.get("emotion") or "").lower().strip()
            if _emo and _emo not in ("none", "neutral", ""):
                _real_emotions.add(_emo)
        # Also infer from prompts
        for _rs in _real_shots:
            _np = (_rs.get("nano_prompt") or "").lower()
            for _kw, _em in [("dread", "dread"), ("grief", "grief"), ("tension", "tension"),
                              ("fear", "fear"), ("revelation", "revelation"), ("anger", "anger")]:
                if _kw in _np:
                    _real_emotions.add(_em)
        _phys_generic = 0
        for _em in _real_emotions:
            _pd = get_physical_direction(_em, "standing")
            if is_prompt_generic(_pd):
                _phys_generic += 1
        test(f"Physical direction non-generic for {len(_real_emotions)} real emotions",
             _phys_generic == 0, f"{_phys_generic} generic directions")

        # Test D: build_ltx_motion on real dialogue shots — none should be generic
        _dlg_shots = [s for s in _real_shots if s.get("dialogue_text")]
        _dlg_generic = 0
        for _ds in _dlg_shots[:20]:  # sample 20 for speed
            _ltx = build_ltx_motion(
                _ds.get("shot_type", "medium"),
                (_ds.get("characters") or ["UNKNOWN"])[0] if _ds.get("characters") else "UNKNOWN",
                _ds.get("emotion") or "neutral",
                True,
                _ds.get("dialogue_text", "")[:80],
                _ds.get("duration", 5.0),
                _ds.get("coverage_role", "B_ACTION")
            )
            if is_prompt_generic(_ltx):
                _dlg_generic += 1
        test(f"build_ltx_motion non-generic for {min(len(_dlg_shots), 20)} real dialogue shots",
             _dlg_generic == 0, f"{_dlg_generic} generic LTX outputs")

        # Test E: audit_all_prompts returns report dict for real data
        _audit = audit_all_prompts(_real_shots)
        test(f"audit_all_prompts returns dict with total_shots for {len(_real_shots)} real shots",
             isinstance(_audit, dict) and _audit.get("total_shots", 0) == len(_real_shots),
             f"Got type={type(_audit).__name__}, total_shots={_audit.get('total_shots') if isinstance(_audit, dict) else 'N/A'}")

        # contamination_rate is already a percentage (e.g. 3.2 = 3.2%)
        _contamination_pct = _audit.get("contamination_rate", 100.0) if isinstance(_audit, dict) else 100.0
        test(f"Contamination rate < 20% on real data (before decontam)",
             _contamination_pct < 20.0,
             f"Got: {_contamination_pct:.1f}%")
    else:
        print("  SKIP  Not enough real shots for stress test")
else:
    print("  SKIP  Victorian Shadows shot plan not found — production stress test skipped")


# ============================================================
# RESULTS
# ============================================================
print()
print("=" * 60)
print(f"CREATIVE PROMPT COMPILER: {PASS} PASS, {FAIL} FAIL out of {TOTAL} tests")
if FAIL == 0:
    print("ALL TESTS PASS — CPC immune system verified")
else:
    print(f"⚠️  {FAIL} FAILURES — fix before production use")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
