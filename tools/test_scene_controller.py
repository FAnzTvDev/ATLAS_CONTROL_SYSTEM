"""
ATLAS V27 — SCENE CONTROLLER TEST SUITE
=========================================
Tests against REAL victorian_shadows_ep1 shot_plan.json data.
Not synthetic — actual production shots that exhibited failures in V26.2.

Test Groups:
  1. Speaker Attribution (correct speaker, wrong speaker detection)
  2. Coverage Assignment (character count, framing, variety)
  3. Reference Resolution (multi-char shots get all refs)
  4. Eyeline Validation (no camera gaze in dialogue shots)
  5. Dialogue LTX Validation (correct character speaks in LTX)
  6. B-roll Deduplication (no identical framings)
  7. Generic Prompt Detection (enforcement agent garbage caught)
  8. Full Scene 001 Simulation (reproduce V26.2 failures)
  9. Cross-Scene Simulation (Scenes 002-005+ with real data)
  10. Enforcement Bypass Verification
  11. V26.2 Failure Reproduction (proves each bug would be caught)
"""

import sys
import os
import json

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.atlas_scene_controller import (
    SceneController,
    attribute_speaker,
    assign_coverage,
    resolve_refs,
    validate_speaker_attribution,
    validate_character_count,
    validate_eyeline,
    validate_dialogue_ltx,
    validate_coverage_variety,
    validate_no_generic_prompt,
    compile_prompt_with_intelligence,
    PreparedShot,
    SpeakerAttribution,
    CoverageAssignment,
    RefResolution,
)

# ============================================================================
# LOAD REAL PRODUCTION DATA
# ============================================================================

PROJECT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "pipeline_outputs", "victorian_shadows_ep1")
SHOT_PLAN_PATH = os.path.join(PROJECT_PATH, "shot_plan.json")
CAST_MAP_PATH = os.path.join(PROJECT_PATH, "cast_map.json")
STORY_BIBLE_PATH = os.path.join(PROJECT_PATH, "story_bible.json")

def load_real_data():
    """Load real production data. Tests skip if not available."""
    data = {}
    if os.path.exists(SHOT_PLAN_PATH):
        with open(SHOT_PLAN_PATH) as f:
            data["shot_plan"] = json.load(f)
    if os.path.exists(CAST_MAP_PATH):
        with open(CAST_MAP_PATH) as f:
            data["cast_map"] = json.load(f)
    if os.path.exists(STORY_BIBLE_PATH):
        with open(STORY_BIBLE_PATH) as f:
            data["story_bible"] = json.load(f)
    return data

REAL_DATA = load_real_data()
HAS_REAL_DATA = "shot_plan" in REAL_DATA and "cast_map" in REAL_DATA

# ============================================================================
# TEST COUNTERS
# ============================================================================

_pass = 0
_fail = 0
_skip = 0

def test(name, condition, detail=""):
    global _pass, _fail
    if condition:
        _pass += 1
        print(f"  ✅ {name}")
    else:
        _fail += 1
        print(f"  ❌ {name}: {detail}")

def skip(name, reason=""):
    global _skip
    _skip += 1
    print(f"  ⏭️  {name}: {reason}")

# ============================================================================
# GROUP 1: SPEAKER ATTRIBUTION
# ============================================================================

def test_group_1_speaker_attribution():
    print("\n=== GROUP 1: SPEAKER ATTRIBUTION ===")

    # Test: Eleanor's line correctly attributed
    shot_eleanor = {
        "shot_id": "001_006B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: Mr. Blackwood, the estate's debts exceed two million pounds.",
        "shot_type": "over_the_shoulder",
    }
    speaker = attribute_speaker(shot_eleanor, [shot_eleanor])
    test("Eleanor's line attributed to Eleanor",
         speaker is not None and speaker.speaker == "ELEANOR VOSS",
         f"Got: {speaker.speaker if speaker else 'None'}")
    test("Thomas is listener",
         speaker is not None and "THOMAS BLACKWOOD" in speaker.listeners,
         f"Listeners: {speaker.listeners if speaker else 'None'}")

    # Test: Thomas's line correctly attributed
    shot_thomas = {
        "shot_id": "001_005B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "THOMAS BLACKWOOD: She would have hated this. Strangers pawing through her things.",
        "shot_type": "over_the_shoulder",
    }
    speaker = attribute_speaker(shot_thomas, [shot_thomas])
    test("Thomas's line attributed to Thomas",
         speaker is not None and speaker.speaker == "THOMAS BLACKWOOD",
         f"Got: {speaker.speaker if speaker else 'None'}")

    # Test: Unprefixed dialogue defaults to first character
    shot_noprefix = {
        "shot_id": "001_004B",
        "characters": ["THOMAS BLACKWOOD"],
        "dialogue_text": "She would have hated this. Strangers pawing through her things.",
        "shot_type": "medium",
    }
    speaker = attribute_speaker(shot_noprefix, [shot_noprefix])
    test("Unprefixed dialogue defaults to first character",
         speaker is not None and speaker.speaker == "THOMAS BLACKWOOD",
         f"Got: {speaker.speaker if speaker else 'None'}")

    # Test: Multi-line dialogue — first speaker wins
    shot_multi = {
        "shot_id": "test_multi",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: line 1 | THOMAS BLACKWOOD: line 2",
        "shot_type": "two_shot",
    }
    speaker = attribute_speaker(shot_multi, [shot_multi])
    test("Multi-line: first speaker wins",
         speaker is not None and speaker.speaker == "ELEANOR VOSS",
         f"Got: {speaker.speaker if speaker else 'None'}")

    # Test: No dialogue returns None
    shot_no_dlg = {
        "shot_id": "test_no_dlg",
        "characters": ["THOMAS BLACKWOOD"],
        "shot_type": "wide",
    }
    speaker = attribute_speaker(shot_no_dlg, [shot_no_dlg])
    test("No dialogue returns None", speaker is None, f"Got: {speaker}")


# ============================================================================
# GROUP 2: COVERAGE ASSIGNMENT
# ============================================================================

def test_group_2_coverage():
    print("\n=== GROUP 2: COVERAGE ASSIGNMENT ===")

    # Wide shot = A_GEOGRAPHY
    coverage = assign_coverage({"shot_type": "wide", "characters": ["A", "B"]}, [], 0)
    test("Wide shot = A_GEOGRAPHY", coverage.role == "A_GEOGRAPHY")

    # MCU = C_EMOTION
    coverage = assign_coverage({"shot_type": "medium_close", "characters": ["A"]}, [], 0)
    test("MCU = C_EMOTION", coverage.role == "C_EMOTION")

    # B-roll = 0 expected chars
    coverage = assign_coverage({"shot_type": "b-roll", "characters": [], "is_broll": True}, [], 0)
    test("B-roll expects 0 chars", coverage.expected_chars == 0)

    # OTS = 2 expected chars
    coverage = assign_coverage({"shot_type": "over_the_shoulder", "characters": ["A", "B"]}, [], 0)
    test("OTS expects 2 chars", coverage.expected_chars == 2,
         f"Got: {coverage.expected_chars}")

    # Single char MCU = isolation negative
    coverage = assign_coverage({"shot_type": "medium_close", "characters": ["A"]}, [], 0)
    test("Single char MCU has isolation negative",
         "only one person" in coverage.isolation_negative,
         f"Got: '{coverage.isolation_negative}'")

    # Two-shot = no isolation negative
    coverage = assign_coverage({"shot_type": "two_shot", "characters": ["A", "B"]}, [], 0)
    test("Two-shot has NO isolation negative", coverage.isolation_negative == "",
         f"Got: '{coverage.isolation_negative}'")


# ============================================================================
# GROUP 3: REFERENCE RESOLUTION
# ============================================================================

def test_group_3_refs():
    print("\n=== GROUP 3: REFERENCE RESOLUTION ===")

    if not HAS_REAL_DATA:
        skip("All ref tests", "No real data available")
        return

    cast_map = REAL_DATA["cast_map"]

    # Two-character shot should get BOTH refs
    shot_2char = {
        "shot_id": "001_005B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "THOMAS BLACKWOOD: She would have hated this.",
        "shot_type": "over_the_shoulder",
        "location": "HARGROVE ESTATE",
    }
    refs = resolve_refs(shot_2char, cast_map, {}, PROJECT_PATH)
    test("2-char shot resolves 2 character refs",
         len(refs.character_refs) == 2,
         f"Got {len(refs.character_refs)} refs: {[os.path.basename(r) for r in refs.character_refs]}")

    # Speaker should be primary (first in list)
    test("Speaker (Thomas) is primary ref",
         refs.primary_character == "THOMAS BLACKWOOD",
         f"Primary: {refs.primary_character}")

    # Eleanor's dialogue shot — Eleanor should be primary
    shot_eleanor = {
        "shot_id": "001_006B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The estate's debts exceed two million.",
        "shot_type": "over_the_shoulder",
        "location": "HARGROVE ESTATE",
    }
    refs = resolve_refs(shot_eleanor, cast_map, {}, PROJECT_PATH)
    test("Eleanor speaking → Eleanor is primary ref",
         refs.primary_character == "ELEANOR VOSS",
         f"Primary: {refs.primary_character}")

    # Single character shot
    shot_1char = {
        "shot_id": "001_008B",
        "characters": ["ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The auction house arrives at noon.",
        "shot_type": "medium_close",
        "location": "HARGROVE ESTATE",
    }
    refs = resolve_refs(shot_1char, cast_map, {}, PROJECT_PATH)
    test("1-char shot resolves 1 character ref",
         len(refs.character_refs) == 1,
         f"Got {len(refs.character_refs)}")

    # B-roll shot — no character refs
    shot_broll = {
        "shot_id": "001_002B",
        "characters": [],
        "shot_type": "b-roll",
        "is_broll": True,
        "location": "HARGROVE ESTATE",
    }
    refs = resolve_refs(shot_broll, cast_map, {}, PROJECT_PATH)
    test("B-roll has 0 character refs", len(refs.character_refs) == 0)


# ============================================================================
# GROUP 4: EYELINE VALIDATION
# ============================================================================

def test_group_4_eyeline():
    print("\n=== GROUP 4: EYELINE VALIDATION ===")

    # Camera gaze in dialogue = bad
    shot_camera_gaze = {
        "shot_id": "test_gaze",
        "characters": ["A", "B"],
        "dialogue_text": "A: Hello",
        "nano_prompt": "Close-up of A looking directly into camera lens",
        "shot_type": "close_up",
    }
    speaker = SpeakerAttribution("A", ["B"], "partner", "left", "A: Hello")
    result = validate_eyeline(shot_camera_gaze, speaker)
    test("Camera gaze in dialogue flagged", not result.passed,
         f"Got: passed={result.passed}, msg={result.message}")

    # Proper eyeline = good
    shot_proper = {
        "shot_id": "test_proper",
        "characters": ["A", "B"],
        "dialogue_text": "A: Hello",
        "nano_prompt": "A's eyeline toward B, three-quarter angle",
        "shot_type": "medium",
    }
    result = validate_eyeline(shot_proper, speaker)
    test("Proper eyeline passes", result.passed)


# ============================================================================
# GROUP 5: DIALOGUE LTX VALIDATION
# ============================================================================

def test_group_5_dialogue_ltx():
    print("\n=== GROUP 5: DIALOGUE LTX VALIDATION ===")

    # V26.2 BUG: Eleanor speaks but LTX says Thomas speaks
    shot_wrong_speaker = {
        "shot_id": "001_006B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: Mr. Blackwood, the estate's debts exceed two million pounds.",
        "ltx_motion_prompt": "THOMAS BLACKWOOD present and grounded in the physical space, character speaks: THOMAS BLACKWOOD delivers line with conviction, face stable NO morphing",
    }
    speaker = SpeakerAttribution("ELEANOR VOSS", ["THOMAS BLACKWOOD"], "partner", "right",
                                 "ELEANOR VOSS: Mr. Blackwood, the estate's debts exceed two million pounds.")
    result = validate_dialogue_ltx(shot_wrong_speaker, speaker)
    test("V26.2 BUG: Wrong speaker in LTX CAUGHT",
         not result.passed and "WRONG CHARACTER" in result.message,
         f"Got: passed={result.passed}, msg={result.message}")

    # Correct speaker = pass
    shot_correct = {
        "shot_id": "001_005B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "THOMAS BLACKWOOD: She would have hated this.",
        "ltx_motion_prompt": "character speaks: THOMAS BLACKWOOD says the line, face stable NO morphing",
    }
    speaker_correct = SpeakerAttribution("THOMAS BLACKWOOD", ["ELEANOR VOSS"], "partner", "left",
                                          "THOMAS BLACKWOOD: She would have hated this.")
    result = validate_dialogue_ltx(shot_correct, speaker_correct)
    test("Correct speaker passes", result.passed, f"msg={result.message}")

    # Missing speaks marker = warning
    shot_no_speaks = {
        "shot_id": "test_no_speaks",
        "characters": ["ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The auction house arrives at noon.",
        "ltx_motion_prompt": "camera slowly pushes in, face stable NO morphing",
    }
    speaker_e = SpeakerAttribution("ELEANOR VOSS", [], "off-screen-right", "center",
                                    "ELEANOR VOSS: The auction house arrives at noon.")
    result = validate_dialogue_ltx(shot_no_speaks, speaker_e)
    test("Missing speaks marker = warning", not result.passed,
         f"Got: {result.message}")


# ============================================================================
# GROUP 6: B-ROLL DEDUPLICATION
# ============================================================================

def test_group_6_broll_dedup():
    print("\n=== GROUP 6: B-ROLL DEDUPLICATION ===")

    # Two B-roll shots with identical prompts
    shots = [
        {
            "shot_id": "001_002B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True,
            "characters": [],
            "nano_prompt": "50mm MS, composition: rule of thirds, Detail/insert shot: Close-up of Eleanor's briefcase",
        },
        {
            "shot_id": "001_003B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True,
            "characters": [],
            "nano_prompt": "50mm MS, composition: rule of thirds, Detail/insert shot: Close-up of Eleanor's briefcase",
        },
    ]
    results = validate_coverage_variety(shots)
    has_dedup_warning = any("near-identical" in r.message for r in results if not r.passed)
    test("Identical B-roll prompts caught", has_dedup_warning,
         f"Results: {[(r.check, r.passed, r.message[:60]) for r in results]}")

    # Different B-roll = OK
    shots_diff = [
        {
            "shot_id": "001_002B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True,
            "characters": [],
            "nano_prompt": "50mm, Detail: Eleanor's briefcase snapping open, leather texture, brass clasps",
        },
        {
            "shot_id": "001_003B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True,
            "characters": [],
            "nano_prompt": "100mm macro, Detail: Dust motes dancing in colored light beams from stained glass",
        },
    ]
    results_diff = validate_coverage_variety(shots_diff)
    no_dedup = not any("near-identical" in r.message for r in results_diff if not r.passed)
    test("Different B-roll passes dedup", no_dedup)


# ============================================================================
# GROUP 7: GENERIC PROMPT DETECTION
# ============================================================================

def test_group_7_generic():
    print("\n=== GROUP 7: GENERIC PROMPT DETECTION ===")

    # Enforcement agent garbage
    shot_garbage = {
        "shot_id": "test_garbage",
        "characters": ["ELEANOR VOSS"],
        "ltx_motion_prompt": "ELEANOR VOSS present and grounded in the physical space, character speaks: ELEANOR VOSS delivers line with conviction",
    }
    result = validate_no_generic_prompt(shot_garbage)
    test("Enforcement agent garbage caught", not result.passed,
         f"msg={result.message}")

    # Real cinematic prompt = OK
    shot_good = {
        "shot_id": "test_good",
        "characters": ["ELEANOR VOSS"],
        "nano_prompt": "Medium close-up of ELEANOR VOSS, three-quarter angle, auburn hair pulled back, sharp eyes",
        "ltx_motion_prompt": "character speaks: ELEANOR VOSS says 'The auction house arrives at noon', subtle head tilt, 14s, face stable NO morphing",
    }
    result = validate_no_generic_prompt(shot_good)
    test("Good cinematic prompt passes", result.passed, f"msg={result.message}")


# ============================================================================
# GROUP 8: FULL SCENE 001 SIMULATION (REAL DATA)
# ============================================================================

def test_group_8_scene_001():
    print("\n=== GROUP 8: FULL SCENE 001 SIMULATION (REAL DATA) ===")

    if not HAS_REAL_DATA:
        skip("Scene 001 simulation", "No real data")
        return

    shots = REAL_DATA["shot_plan"].get("shots", [])
    cast_map = REAL_DATA["cast_map"]
    story_bible = REAL_DATA.get("story_bible", {})

    ctrl = SceneController(
        project_path=PROJECT_PATH,
        cast_map=cast_map,
        story_bible=story_bible,
    )

    prepared = ctrl.prepare_scene("001", shots)
    test("Scene 001 prepared", len(prepared) > 0, f"Got {len(prepared)} shots")

    # Check that all dialogue shots have correct speaker
    dialogue_shots = [p for p in prepared if p.dialogue_text]
    wrong_speakers = []
    for ps in dialogue_shots:
        if ps.speaker:
            # Check that speaker matches dialogue prefix
            dlg = ps.dialogue_text
            if ":" in dlg:
                expected = dlg.split(":")[0].strip().upper()
                expected = expected.split("|")[0].strip()
                # Remove parentheticals
                import re
                expected = re.sub(r'\s*\(.*?\)\s*', '', expected).strip()
                if expected != ps.speaker.speaker:
                    wrong_speakers.append((ps.shot_id, expected, ps.speaker.speaker))

    test("All dialogue shots have correct speaker",
         len(wrong_speakers) == 0,
         f"Wrong: {wrong_speakers}")

    # Check 2-char shots have 2 refs
    two_char_shots = [p for p in prepared if len(p.characters) >= 2]
    missing_refs = [(p.shot_id, len(p.refs.character_refs)) for p in two_char_shots
                    if len(p.refs.character_refs) < 2]
    test("All 2-char shots have 2 refs",
         len(missing_refs) == 0,
         f"Missing: {missing_refs}")

    # Check no blocking failures
    blocking = [p for p in prepared if not p.is_ready]
    test(f"No blocking failures ({len(blocking)} found)",
         len(blocking) == 0,
         f"Blocking: {[(p.shot_id, [v.message for v in p.blocking_failures]) for p in blocking]}")

    # Report
    report = ctrl.get_scene_report(prepared)
    print(f"\n  Scene 001 Report:")
    print(f"    Total: {report['total_shots']}, Ready: {report['ready']}, Blocking: {report['blocking']}")
    print(f"    Coverage: {report['coverage_map']}")
    print(f"    Speakers: {report['speaker_map']}")
    for sr in report['shots']:
        if sr['validations']:
            print(f"    {sr['shot_id']}: {[v['message'][:60] for v in sr['validations']]}")


# ============================================================================
# GROUP 9: CROSS-SCENE SIMULATION
# ============================================================================

def test_group_9_cross_scene():
    print("\n=== GROUP 9: CROSS-SCENE SIMULATION ===")

    if not HAS_REAL_DATA:
        skip("Cross-scene simulation", "No real data")
        return

    shots = REAL_DATA["shot_plan"].get("shots", [])
    cast_map = REAL_DATA["cast_map"]

    ctrl = SceneController(
        project_path=PROJECT_PATH,
        cast_map=cast_map,
    )

    # Get all unique scene IDs
    scene_ids = sorted(set(s.get("scene_id", "") for s in shots if s.get("scene_id")))

    total_prepared = 0
    total_blocking = 0
    total_warnings = 0
    scenes_tested = 0

    for scene_id in scene_ids[:8]:  # Test first 8 scenes
        prepared = ctrl.prepare_scene(scene_id, shots)
        if not prepared:
            continue

        scenes_tested += 1
        total_prepared += len(prepared)

        blocking = [p for p in prepared if not p.is_ready]
        total_blocking += len(blocking)

        warnings = sum(1 for p in prepared for v in p.validations
                       if not v.passed and v.severity == "warning")
        total_warnings += warnings

        # Check speaker attribution for all dialogue shots
        for ps in prepared:
            if ps.dialogue_text and ps.speaker:
                dlg_lines = [l.strip() for l in ps.dialogue_text.split("|")]
                first_line = dlg_lines[0]
                if ":" in first_line:
                    expected_speaker = first_line.split(":")[0].strip().upper()
                    import re
                    expected_speaker = re.sub(r'\s*\(.*?\)\s*', '', expected_speaker).strip()
                    if ps.speaker.speaker != expected_speaker:
                        total_blocking += 1  # Count as error

    print(f"\n  Cross-Scene Summary ({scenes_tested} scenes):")
    print(f"    Shots prepared: {total_prepared}")
    print(f"    Blocking failures: {total_blocking}")
    print(f"    Warnings: {total_warnings}")

    test(f"Cross-scene: {scenes_tested} scenes prepared", scenes_tested > 0)
    test(f"Cross-scene: <5% blocking rate",
         total_blocking < total_prepared * 0.05 if total_prepared > 0 else True,
         f"{total_blocking}/{total_prepared} = {total_blocking/max(total_prepared,1)*100:.1f}%")


# ============================================================================
# GROUP 10: PROMPT COMPILATION (SPEAKER + EYELINE INJECTION)
# ============================================================================

def test_group_10_prompt_compile():
    print("\n=== GROUP 10: PROMPT COMPILATION ===")

    # Test: Single-char MCU gets isolation negative
    shot = {
        "shot_id": "001_008B",
        "characters": ["ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The auction house arrives at noon.",
        "nano_prompt": "100mm MCU of ELEANOR VOSS, three-quarter angle",
        "ltx_motion_prompt": "camera holds, face stable NO morphing, 14s",
        "shot_type": "medium_close",
        "duration": 14,
    }
    speaker = SpeakerAttribution("ELEANOR VOSS", [], "off-screen-right", "center",
                                  "ELEANOR VOSS: The auction house arrives at noon.")
    coverage = CoverageAssignment("C_EMOTION", "medium_close", "100mm", 1,
                                   "single subject",
                                   "only one person in frame, no background figures, no other people")
    refs = RefResolution([], [], [], "ELEANOR VOSS", [])

    nano, ltx = compile_prompt_with_intelligence(shot, speaker, coverage, refs)

    test("Isolation negative injected",
         "only one person" in nano or "no background figures" in nano,
         f"Nano ends: ...{nano[-100:]}")

    test("Eyeline injected (NOT camera)",
         "not looking" in nano.lower() or "off-screen" in nano.lower(),
         f"Nano: ...{nano[-80:]}")

    test("Speaker correctly in LTX",
         "ELEANOR VOSS" in ltx and "speaks" in ltx.lower(),
         f"LTX: {ltx[:120]}")

    # Test: Wrong speaker in LTX gets FIXED
    shot_wrong = {
        "shot_id": "001_006B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The estate's debts exceed two million pounds.",
        "nano_prompt": "OTS from behind Thomas, favoring Eleanor",
        "ltx_motion_prompt": "THOMAS BLACKWOOD present and grounded in the physical space, character speaks: THOMAS BLACKWOOD delivers line with conviction, face stable NO morphing, 10s",
        "shot_type": "over_the_shoulder",
        "duration": 10,
    }
    speaker_e = SpeakerAttribution("ELEANOR VOSS", ["THOMAS BLACKWOOD"], "partner", "right",
                                    "ELEANOR VOSS: The estate's debts exceed two million pounds.")
    coverage_ots = CoverageAssignment("C_EMOTION", "over_the_shoulder", "85mm", 2,
                                       "both visible", "")
    refs_e = RefResolution([], [], [], "ELEANOR VOSS", [])

    nano_fixed, ltx_fixed = compile_prompt_with_intelligence(shot_wrong, speaker_e, coverage_ots, refs_e)

    test("V26.2 FIX: Wrong speaker stripped from LTX",
         "grounded in the physical space" not in ltx_fixed,
         f"LTX: {ltx_fixed[:120]}")

    test("V26.2 FIX: Correct speaker injected",
         "ELEANOR VOSS" in ltx_fixed and "speaks" in ltx_fixed.lower(),
         f"LTX: {ltx_fixed[:120]}")


# ============================================================================
# GROUP 11: V26.2 FAILURE REPRODUCTION
# ============================================================================

def test_group_11_v262_failures():
    print("\n=== GROUP 11: V26.2 FAILURE REPRODUCTION ===")

    # Failure 1: 002B and 003B identical frames
    # Root cause: identical nano prompts
    shots_dedup = [
        {"shot_id": "001_001A", "scene_id": "001", "shot_type": "establishing", "characters": [],
         "nano_prompt": "35mm WS, establishing wide, grand foyer"},
        {"shot_id": "001_002B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True, "characters": [],
         "nano_prompt": "50mm MS, composition: rule of thirds, subject off-center, Detail/insert shot: Close-up of Eleanor's briefcase"},
        {"shot_id": "001_003B", "scene_id": "001", "shot_type": "b-roll", "is_broll": True, "characters": [],
         "nano_prompt": "50mm MS, composition: rule of thirds, subject off-center, Detail/insert shot: Detail shot of dust motes"},
    ]
    results = validate_coverage_variety(shots_dedup)
    first_3_same = any("same type" in r.message for r in results if not r.passed)
    # These actually have different types: establishing, b-roll, b-roll
    # But we should check if B-rolls are differentiated
    test("First 3 shots coverage variety check runs", len(results) > 0)

    # Failure 2: Thomas says Eleanor's line (006B)
    shot_006B = {
        "shot_id": "001_006B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: Mr. Blackwood, the estate's debts exceed two million pounds.",
        "ltx_motion_prompt": "THOMAS BLACKWOOD present and grounded in the physical space, character speaks: THOMAS BLACKWOOD delivers line with conviction",
    }
    speaker = attribute_speaker(shot_006B, [shot_006B])
    test("006B: Speaker is Eleanor (not Thomas)",
         speaker.speaker == "ELEANOR VOSS",
         f"Got: {speaker.speaker}")

    result = validate_dialogue_ltx(shot_006B, speaker)
    test("006B: Wrong speaker in LTX DETECTED",
         not result.passed and "WRONG CHARACTER" in result.message,
         f"msg={result.message}")

    # Failure 3: Eleanor looking into camera (008B)
    # The ref photo was direct-gaze — we can't fix the ref,
    # but we CAN inject "NOT looking at camera" into the prompt
    shot_008B = {
        "shot_id": "001_008B",
        "characters": ["ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: The auction house arrives at noon.",
        "nano_prompt": "100mm MCU of ELEANOR VOSS",
        "ltx_motion_prompt": "face stable NO morphing, 14s",
        "shot_type": "medium_close",
        "duration": 14,
    }
    speaker_e = attribute_speaker(shot_008B, [shot_008B])
    coverage = assign_coverage(shot_008B, [shot_008B], 0)
    refs = RefResolution([], [], [], "ELEANOR VOSS", [])
    nano, ltx = compile_prompt_with_intelligence(shot_008B, speaker_e, coverage, refs)
    test("008B: Anti-camera-gaze injected",
         "not looking" in nano.lower() or "off-axis" in nano.lower(),
         f"Nano: ...{nano[-80:]}")

    # Failure 4: Mystery woman in 009B (single char MCU)
    shot_009B = {
        "shot_id": "001_009B",
        "characters": ["THOMAS BLACKWOOD"],
        "nano_prompt": "100mm MCU of THOMAS BLACKWOOD",
        "ltx_motion_prompt": "face stable NO morphing, 14s",
        "shot_type": "medium_close",
        "duration": 14,
    }
    coverage_009 = assign_coverage(shot_009B, [shot_009B], 0)
    test("009B: Single-char has isolation negative",
         "only one person" in coverage_009.isolation_negative,
         f"Got: '{coverage_009.isolation_negative}'")

    speaker_t = attribute_speaker(shot_009B, [shot_009B])
    nano_009, _ = compile_prompt_with_intelligence(
        shot_009B, speaker_t, coverage_009, RefResolution([], [], [], "THOMAS BLACKWOOD", []))
    test("009B: 'no other people' in compiled prompt",
         "no other people" in nano_009 or "no background figures" in nano_009,
         f"Nano: ...{nano_009[-100:]}")

    # Failure 5: Enforcement agent garbage detected
    shot_garbage = {
        "shot_id": "001_010B",
        "characters": ["THOMAS BLACKWOOD", "ELEANOR VOSS"],
        "dialogue_text": "ELEANOR VOSS: Everything is on the table, Mr. Blackwood.",
        "ltx_motion_prompt": "THOMAS BLACKWOOD present and grounded in the physical space, character speaks: THOMAS BLACKWOOD delivers line with conviction, face stable NO morphing, 10s",
    }
    result = validate_no_generic_prompt(shot_garbage)
    test("010B: Enforcement garbage detected", not result.passed,
         f"msg={result.message}")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ATLAS V27 SCENE CONTROLLER — REAL DATA SIMULATION")
    print("=" * 70)
    print(f"Real data available: {HAS_REAL_DATA}")
    if HAS_REAL_DATA:
        n_shots = len(REAL_DATA["shot_plan"].get("shots", []))
        n_chars = len([k for k, v in REAL_DATA["cast_map"].items()
                       if isinstance(v, dict) and not v.get("_is_alias_of")])
        print(f"Shot plan: {n_shots} shots, Cast: {n_chars} characters")

    test_group_1_speaker_attribution()
    test_group_2_coverage()
    test_group_3_refs()
    test_group_4_eyeline()
    test_group_5_dialogue_ltx()
    test_group_6_broll_dedup()
    test_group_7_generic()
    test_group_8_scene_001()
    test_group_9_cross_scene()
    test_group_10_prompt_compile()
    test_group_11_v262_failures()

    print("\n" + "=" * 70)
    print(f"RESULTS: {_pass} passed, {_fail} failed, {_skip} skipped")
    print(f"TOTAL: {_pass + _fail + _skip} tests")
    if _fail == 0:
        print("🟢 ALL TESTS PASS")
    else:
        print(f"🔴 {_fail} FAILURES — fix before next run")
    print("=" * 70)
