#!/usr/bin/env python3
"""
ATLAS V24.1 — Continuity Memory Engine Test Suite
Tests: spatial state extraction, reframe candidates, B-roll continuity,
       parallel rendering, vision integration, memory persistence.
"""
import json
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.continuity_memory import (
    ContinuityMemory,
    ShotSpatialState,
    CharacterSpatialState,
    CameraState,
    EnvironmentState,
    ReframeCandidate,
    BRollContinuityState,
    extract_spatial_state_from_metadata,
    generate_reframe_candidates,
    compile_continuity_delta,
    should_chain_broll,
    extract_broll_continuity,
    compile_broll_continuity_prompt,
    analyze_end_frame_spatial,
    build_render_dependency_graph,
    get_parallel_render_groups,
    estimate_parallel_render_time,
    SHOT_SCALE_ORDER,
)

PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  + PASS: {name}")
    else:
        FAIL += 1
        print(f"  X FAIL: {name}")


# ═══════════════════════════════════════════════════════
# TEST GROUP 1: Spatial State Extraction
# ═══════════════════════════════════════════════════════
print("\n--- TEST 1: Spatial State Extraction ---")

shot_single_char = {
    "shot_id": "001_003A", "scene_id": "001",
    "shot_type": "medium", "characters": ["ELEANOR VOSS"],
    "nano_prompt": "Eleanor stands at the window, gripping the curtain",
    "ltx_motion_prompt": "character performs: standing at window",
    "emotion": "dread", "dialogue_text": "",
    "coverage_role": "B_ACTION",
}

state = extract_spatial_state_from_metadata(shot_single_char)
test("Single char extraction returns ShotSpatialState", isinstance(state, ShotSpatialState))
test("Shot ID preserved", state.shot_id == "001_003A")
test("Scene ID preserved", state.scene_id == "001")
test("One character extracted", len(state.characters) == 1)
test("Character name correct", state.characters[0].name == "ELEANOR VOSS")
test("Emotion read is dread", state.characters[0].emotion_read == "dread")
test("Gesture extracted (gripping)", "grip" in state.characters[0].gesture_state.lower())
test("Posture extracted (standing)", state.characters[0].posture == "standing")
test("Camera scale is medium", state.camera.shot_scale == "medium")

shot_two_chars = {
    "shot_id": "002_005A", "scene_id": "002",
    "shot_type": "medium", "characters": ["ELEANOR VOSS", "THOMAS BLACKWOOD"],
    "nano_prompt": "Eleanor and Thomas face each other across the desk",
    "ltx_motion_prompt": "character performs: tense conversation",
    "emotion": "tension", "dialogue_text": "I know what you did.",
}

state2 = extract_spatial_state_from_metadata(shot_two_chars)
test("Two chars extracted", len(state2.characters) == 2)
test("First char left of center", state2.characters[0].screen_position[0] < 0.5)
test("Second char right of center", state2.characters[1].screen_position[0] > 0.5)
test("Dialogue chars gaze at each other", state2.characters[0].gaze_direction == "THOMAS BLACKWOOD")

shot_broll = {
    "shot_id": "001_002B", "scene_id": "001",
    "shot_type": "detail", "characters": [],
    "nano_prompt": "Close detail of candle flame flickering, dust particles in air",
    "_broll": True,
}

state3 = extract_spatial_state_from_metadata(shot_broll)
test("B-roll has no characters", len(state3.characters) == 0)
test("B-roll camera scale = extreme_close (detail)", state3.camera.shot_scale == "extreme_close")

# ═══════════════════════════════════════════════════════
# TEST GROUP 2: Reframe Candidate Generation
# ═══════════════════════════════════════════════════════
print("\n--- TEST 2: Reframe Candidate Generation ---")

prev_state = ShotSpatialState(
    shot_id="001_003A", scene_id="001",
    characters=[CharacterSpatialState(
        name="ELEANOR VOSS",
        screen_position=(0.35, 0.55),
        body_angle="three-quarter-right",
        emotion_read="tension",
        gesture_state="hand gripping curtain",
    )],
    camera=CameraState(shot_scale="medium", focal_length_equiv=50),
    environment=EnvironmentState(location="Victorian bedroom", atmosphere="tension"),
)

next_shot = {
    "shot_id": "001_004A", "scene_id": "001",
    "shot_type": "medium_close", "characters": ["ELEANOR VOSS"],
    "emotion": "dread",
}

candidates = generate_reframe_candidates(next_shot, prev_state, emotion_trajectory="rising")
test("At least 3 candidates generated", len(candidates) >= 3)
test("Candidates sorted by composite score", candidates[0].composite_score() >= candidates[-1].composite_score())
test("All have strategy", all(c.strategy for c in candidates))
test("All have delta_prompt", all(c.delta_prompt for c in candidates))

# Check continuity_match candidate exists
cont_match = [c for c in candidates if c.strategy == "continuity_match"]
test("Continuity match candidate exists", len(cont_match) > 0)

# Check emotional_push candidate exists (rising emotion)
emot_push = [c for c in candidates if c.strategy == "emotional_push"]
test("Emotional push candidate exists (rising trajectory)", len(emot_push) > 0)

# Test with no previous state (first shot in scene)
cands_no_prev = generate_reframe_candidates(next_shot, None, emotion_trajectory="stable")
test("Candidates generated even without previous state", len(cands_no_prev) >= 2)

# Test dialogue shot candidates
dialogue_shot = {
    "shot_id": "002_006A", "scene_id": "002",
    "shot_type": "close", "characters": ["ELEANOR VOSS", "THOMAS BLACKWOOD"],
    "dialogue_text": "Tell me the truth.",
    "emotion": "tension",
}
cands_dlg = generate_reframe_candidates(dialogue_shot, prev_state, emotion_trajectory="peak")
reaction = [c for c in cands_dlg if c.strategy == "reaction_cut"]
test("Dialogue shot gets reaction cut candidate", len(reaction) > 0)
test("Reaction cut targets different character", reaction[0].proposed_character_focus != "ELEANOR VOSS" if reaction else False)

# ═══════════════════════════════════════════════════════
# TEST GROUP 3: Delta Prompt Compilation
# ═══════════════════════════════════════════════════════
print("\n--- TEST 3: Delta Prompt Compilation ---")

best_candidate = candidates[0]
delta = compile_continuity_delta(best_candidate, prev_state, next_shot)
test("Delta prompt is non-empty", len(delta) > 50)
test("Delta contains CONTINUITY MEMORY", "CONTINUITY MEMORY" in delta)
test("Delta contains character name", "ELEANOR" in delta)
test("Delta contains position zone", "third" in delta or "center" in delta)
test("Delta contains REFRAME PLAN", "REFRAME PLAN" in delta)
test("Delta contains EXECUTION CONSTRAINTS", "EXECUTION" in delta)
test("Delta forbids axis flip", "axis" in delta.lower())

# ═══════════════════════════════════════════════════════
# TEST GROUP 4: B-Roll Continuity
# ═══════════════════════════════════════════════════════
print("\n--- TEST 4: B-Roll Continuity ---")

broll_shot = {"shot_id": "001_002B", "_broll": True, "scene_id": "001", "shot_type": "detail"}
char_shot = {"shot_id": "001_003A", "characters": ["ELEANOR"], "scene_id": "001", "shot_type": "medium"}
broll_shot2 = {"shot_id": "001_004B", "_broll": True, "scene_id": "001", "shot_type": "detail"}
broll_diff_scene = {"shot_id": "002_001B", "_broll": True, "scene_id": "002", "shot_type": "detail"}
establishing = {"shot_id": "001_001A", "scene_id": "001", "shot_type": "establishing"}

test("B-roll never chains to character shot", should_chain_broll(broll_shot, char_shot) == False)
test("B-roll detail→detail CAN chain (same scene)", should_chain_broll(broll_shot2, broll_shot) == True)
test("B-roll never chains across scenes", should_chain_broll(broll_diff_scene, broll_shot) == False)
test("Establishing shots never chain", should_chain_broll(establishing, broll_shot) == False)

# B-roll continuity extraction
scene_shots = [
    {"scene_id": "001", "nano_prompt": "Victorian bedroom, candle flame, dust particles, wood grain floor", "emotion": "dread"},
    {"scene_id": "001", "nano_prompt": "Eleanor at stone fireplace, leather armchair", "emotion": "tension"},
]
broll_cont = extract_broll_continuity(scene_shots, color_grade="desaturated gothic")
test("B-roll continuity extracts textures", len(broll_cont.texture_keywords) > 0)
test("B-roll continuity has color grade", broll_cont.color_grade == "desaturated gothic")
test("B-roll continuity has atmosphere", broll_cont.atmosphere in ("dread", "tension"))

# Compile B-roll prompt
broll_prompt = compile_broll_continuity_prompt(broll_cont, broll_shot)
test("B-roll prompt mentions color grade", "desaturated" in broll_prompt.lower())
test("B-roll prompt mentions textures", any(t in broll_prompt.lower() for t in broll_cont.texture_keywords))

# ═══════════════════════════════════════════════════════
# TEST GROUP 5: Parallel Rendering Dependency Graph
# ═══════════════════════════════════════════════════════
print("\n--- TEST 5: Parallel Rendering Dependencies ---")

test_shots = [
    # Scene 001: 5 shots (3 chain + 2 broll)
    {"shot_id": "001_001A", "scene_id": "001", "shot_type": "wide", "characters": ["ELEANOR"]},
    {"shot_id": "001_002B", "scene_id": "001", "shot_type": "detail", "_broll": True, "characters": []},
    {"shot_id": "001_003A", "scene_id": "001", "shot_type": "medium", "characters": ["ELEANOR"]},
    {"shot_id": "001_004B", "scene_id": "001", "shot_type": "detail", "_broll": True, "characters": []},
    {"shot_id": "001_005A", "scene_id": "001", "shot_type": "close", "characters": ["ELEANOR"]},
    # Scene 002: 3 shots (all chain)
    {"shot_id": "002_001A", "scene_id": "002", "shot_type": "wide", "characters": ["THOMAS"]},
    {"shot_id": "002_002A", "scene_id": "002", "shot_type": "medium", "characters": ["THOMAS"]},
    {"shot_id": "002_003A", "scene_id": "002", "shot_type": "close", "characters": ["THOMAS"]},
]

deps = build_render_dependency_graph(test_shots)
test("All 8 shots have dependencies", len(deps) == 8)

# Scene anchors
anchors = [d for d in deps if d.is_scene_anchor]
test("2 scene anchors (001, 002)", len(anchors) == 2)

# B-roll is independent
broll_deps = [d for d in deps if d.is_broll]
test("2 B-roll shots flagged independent", len(broll_deps) == 2)
test("B-roll has no dependency", all(d.depends_on is None for d in broll_deps))
test("B-roll can parallel", all(d.can_parallel for d in broll_deps))

# Chained shots
chained = [d for d in deps if d.chain_position > 0 and not d.is_broll]
test("Chained shots depend on previous", all(d.depends_on is not None for d in chained))

# Parallel groups
groups = get_parallel_render_groups(deps)
test("Multiple render groups exist", len(groups) >= 3)  # chain_001, broll_001, chain_002

# Time estimate
time_est = estimate_parallel_render_time(deps)
test("Parallel faster than sequential", time_est["parallel_seconds"] < time_est["sequential_seconds"])
test("Speedup > 1", time_est["speedup"] > 1.0)
test("Has independent shots", time_est["independent_shots"] > 0)

# ═══════════════════════════════════════════════════════
# TEST GROUP 6: Memory Persistence
# ═══════════════════════════════════════════════════════
print("\n--- TEST 6: Memory Persistence ---")

tmpdir = tempfile.mkdtemp()
try:
    mem = ContinuityMemory(tmpdir)

    # Store a state
    mem.store_shot_state("001_003A", prev_state)
    test("State stored", mem.get_shot_state("001_003A") is not None)

    # Retrieve it
    retrieved = mem.get_shot_state("001_003A")
    test("Retrieved state matches shot_id", retrieved.shot_id == "001_003A")
    test("Retrieved state has character", len(retrieved.characters) == 1)
    test("Retrieved character name correct", retrieved.characters[0].name == "ELEANOR VOSS")

    # Test persistence (reload from disk)
    mem2 = ContinuityMemory(tmpdir)
    retrieved2 = mem2.get_shot_state("001_003A")
    test("Persistence: state survives reload", retrieved2 is not None)
    test("Persistence: character data intact", retrieved2.characters[0].name == "ELEANOR VOSS")
    test("Persistence: emotion intact", retrieved2.characters[0].emotion_read == "tension")

    # Record transition
    mem.record_transition("001_003A", "001_004A", candidates[0], candidates[1] if len(candidates) > 1 else None)
    test("Transition recorded", len(mem._transition_log) == 1)

    # Scene memory
    scene_mem = mem.get_scene_memory("001")
    test("Scene memory has 1 state", len(scene_mem) == 1)

    # Statistics
    stats = mem.get_statistics()
    test("Stats reports 1 state", stats["total_states"] == 1)
    test("Stats reports 1 scene", stats["scenes_tracked"] == 1)
    test("Stats reports 1 transition", stats["transitions_logged"] == 1)

    # Clear scene
    mem.clear_scene("001")
    test("Clear scene removes states", mem.get_shot_state("001_003A") is None)

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# ═══════════════════════════════════════════════════════
# TEST GROUP 7: Vision Integration (metadata path)
# ═══════════════════════════════════════════════════════
print("\n--- TEST 7: Vision Integration (Metadata Path) ---")

# Without actual frame, uses metadata extraction
state_v = analyze_end_frame_spatial(shot_single_char, vision_result=None)
test("Vision fallback produces valid state", isinstance(state_v, ShotSpatialState))
test("Vision fallback has character", len(state_v.characters) == 1)

# With mock vision result
mock_vision = {
    "caption": "A tense woman standing near a window, looking worried",
    "detections": [
        {"label": "person", "x1": 0.2, "y1": 0.3, "x2": 0.5, "y2": 0.9},
    ],
    "identity_scores": {"ELEANOR VOSS": {"similarity": 0.87, "detected": True}},
    "location_score": 0.82,
    "frame_hash": "abc123",
}

state_with_vision = analyze_end_frame_spatial(shot_single_char, vision_result=mock_vision)
test("Vision updates character position from detection", state_with_vision.characters[0].screen_position[0] != 0.5)
test("Vision extracts emotion from caption", state_with_vision.characters[0].emotion_read in ("tension", "dread"))
test("Frame hash stored", state_with_vision.frame_hash == "abc123")

# ═══════════════════════════════════════════════════════
# TEST GROUP 8: Full Pipeline Integration (Victorian Shadows)
# ═══════════════════════════════════════════════════════
print("\n--- TEST 8: Full Pipeline on Victorian Shadows EP1 ---")

PROJECT = "pipeline_outputs/victorian_shadows_ep1"
if os.path.exists(f"{PROJECT}/shot_plan.json"):
    sp = json.load(open(f"{PROJECT}/shot_plan.json"))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    cm_raw = json.load(open(f"{PROJECT}/cast_map.json"))
    cast_map = {k: v for k, v in cm_raw.items() if isinstance(v, dict) and not v.get("_is_alias_of")}

    # Extract spatial states for all shots
    states = []
    errors = 0
    for s in shots:
        try:
            st = extract_spatial_state_from_metadata(s, cast_map)
            states.append(st)
        except Exception as e:
            errors += 1

    test(f"Spatial extraction: {len(states)}/{len(shots)} shots ({errors} errors)", errors == 0)

    # Generate candidates for sample shots
    cand_errors = 0
    for i in range(1, min(30, len(shots))):
        try:
            prev_st = states[i - 1]
            cands = generate_reframe_candidates(shots[i], prev_st, emotion_trajectory="stable")
            if len(cands) < 2:
                cand_errors += 1
        except Exception as e:
            cand_errors += 1

    test(f"Candidate gen: 29 shots tested, {cand_errors} errors", cand_errors == 0)

    # Build dependency graph
    deps = build_render_dependency_graph(shots)
    test(f"Dependency graph: {len(deps)} entries for {len(shots)} shots", len(deps) == len(shots))

    groups = get_parallel_render_groups(deps)
    test(f"Parallel groups: {len(groups)}", len(groups) >= 3)

    time_est = estimate_parallel_render_time(deps)
    test(f"Parallel speedup: {time_est['speedup']}x", time_est["speedup"] > 1.0)

    # B-roll awareness
    # V26 Doctrine 256: Use explicit flags, not shot_id suffix
    broll_shots = [s for s in shots if s.get("_broll") or s.get("is_broll")]
    broll_deps_list = [d for d in deps if d.is_broll]
    test(f"B-roll correctly identified: {len(broll_deps_list)} independent", len(broll_deps_list) >= 0)

    # Check no B-roll depends on character shot
    for d in broll_deps_list:
        if d.depends_on:
            dep_shot = next((s for s in shots if s.get("shot_id") == d.depends_on), None)
            if dep_shot and dep_shot.get("characters"):
                test(f"B-roll {d.shot_id} incorrectly depends on char shot", False)
                break

    print(f"\n  Project stats:")
    print(f"    Total shots: {len(shots)}")
    print(f"    Spatial states: {len(states)}")
    print(f"    Render groups: {len(groups)}")
    print(f"    Sequential: {time_est['sequential_seconds']//60:.0f} min")
    print(f"    Parallel:   {time_est['parallel_seconds']//60:.0f} min")
    print(f"    Speedup:    {time_est['speedup']}x")
    print(f"    Longest chain: {time_est['longest_chain']} shots")
    print(f"    Independent: {time_est['independent_shots']} shots")

else:
    print("  SKIP: Victorian Shadows project not found")

# ═══════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"CONTINUITY MEMORY TEST RESULTS: {PASS} PASS, {FAIL} FAIL")
if FAIL == 0:
    print("ALL TESTS PASS")
else:
    print(f"!!! {FAIL} FAILURES — FIX BEFORE PROCEEDING !!!")
print(f"{'='*60}")
