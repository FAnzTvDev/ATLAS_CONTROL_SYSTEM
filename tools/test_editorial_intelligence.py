#!/usr/bin/env python3
"""
V25.3 Editorial Intelligence — Unit Tests
Rule C of the Autonomous Build Covenant: Green Is Not the Success Condition.
These tests prove the editor's brain ACTUALLY makes correct editorial decisions.

Test groups:
  1. Murch Cut Point Scoring (Rule of Six)
  2. ASL Governor (genre/emotion targets)
  3. Audio Transition Classification (J/L cuts)
  4. Frame Reuse Detection
  5. B-Roll Overlay Detection
  6. Hold-vs-Cut Decisions
  7. Full Editorial Plan (integration)
  8. AI Gap Workaround Mapping
  9. Stitch Plan Generation
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
print("EDITORIAL INTELLIGENCE TESTS")
print("=" * 60)

from tools.editorial_intelligence import (
    score_cut_point, compute_scene_asl_target, classify_audio_transition,
    analyze_frame_reuse, analyze_broll_overlays, analyze_hold_opportunities,
    build_editorial_plan, apply_editorial_tags, filter_shots_for_generation,
    build_overlay_stitch_plan, editorial_report,
    MURCH_WEIGHTS, ASL_TARGETS, EMOTION_ASL_MODIFIER, AI_GAP_WORKAROUNDS,
    _is_character_static, _same_blocking, _is_same_framing,
)

# ============================================================
# GROUP 1: Murch Cut Point Scoring
# ============================================================
print("\n--- Group 1: Murch Cut Point Scoring ---")

# Emotion escalation: grief → revelation should score high
shot_grief = {"shot_id": "001_003C", "emotion": "grief", "dialogue_text": "I never told her",
              "characters": ["EVELYN"], "location": "MANOR", "shot_type": "close_up",
              "coverage_role": "C_EMOTION", "duration": 5}
shot_revelation = {"shot_id": "001_004B", "emotion": "revelation", "dialogue_text": "The will was forged",
                   "characters": ["EVELYN"], "location": "MANOR", "shot_type": "medium",
                   "coverage_role": "B_ACTION", "duration": 4, "_beat_action": "reveals truth"}

score = score_cut_point(shot_grief, shot_revelation)
test("Grief→revelation scores high emotion",
     score["scores"]["emotion"] >= 0.9, f"Got: {score['scores']['emotion']}")
test("Grief→revelation total > 0.7",
     score["total"] > 0.7, f"Got: {score['total']}")
test("Grief→revelation recommends CUT",
     score["recommendation"] == "CUT", f"Got: {score['recommendation']}")

# Same emotion, same framing = weak cut (should suggest HOLD)
shot_neutral_a = {"shot_id": "002_001A", "emotion": "neutral", "characters": ["THOMAS"],
                  "location": "OFFICE", "shot_type": "medium", "coverage_role": "B_ACTION", "duration": 4}
shot_neutral_b = {"shot_id": "002_002A", "emotion": "neutral", "characters": ["THOMAS"],
                  "location": "OFFICE", "shot_type": "medium", "coverage_role": "B_ACTION", "duration": 4}

weak_score = score_cut_point(shot_neutral_a, shot_neutral_b)
test("Same emotion scores low",
     weak_score["scores"]["emotion"] <= 0.4, f"Got: {weak_score['scores']['emotion']}")
test("Same setup total < 0.55",
     weak_score["total"] < 0.55, f"Got: {weak_score['total']}")

# Location change should drop spatial score
shot_manor = {"shot_id": "003_001A", "emotion": "tension", "characters": ["EVELYN"],
              "location": "MANOR LIBRARY", "shot_type": "wide", "coverage_role": "A_GEOGRAPHY", "duration": 5}
shot_office = {"shot_id": "003_002A", "emotion": "tension", "characters": ["LAWYER"],
               "location": "LAWYER OFFICE", "shot_type": "medium", "coverage_role": "B_ACTION", "duration": 4}

loc_score = score_cut_point(shot_manor, shot_office)
test("Location change drops spatial score",
     loc_score["scores"]["spatial"] < 0.3, f"Got: {loc_score['scores']['spatial']}")

# Verify Murch weights sum to ~1.0
weight_sum = sum(MURCH_WEIGHTS.values())
test("Murch weights sum to ~1.0",
     0.99 <= weight_sum <= 1.01, f"Got: {weight_sum}")

# Shared characters improve eye_trace
score_shared = score_cut_point(
    {"characters": ["EVELYN"], "emotion": "neutral", "location": "A", "shot_type": "wide",
     "coverage_role": "A_GEOGRAPHY", "duration": 5},
    {"characters": ["EVELYN"], "emotion": "tension", "dialogue_text": "hello",
     "location": "A", "shot_type": "close_up", "coverage_role": "C_EMOTION", "duration": 4},
)
test("Shared characters boost eye_trace",
     score_shared["scores"]["eye_trace"] >= 0.8, f"Got: {score_shared['scores']['eye_trace']}")


# ============================================================
# GROUP 2: ASL Governor
# ============================================================
print("\n--- Group 2: ASL Governor ---")

# Gothic horror target should be 4-12s range
gothic_shots = [
    {"shot_id": f"001_{i:03d}", "duration": 6, "emotion": "dread"} for i in range(10)
]
asl = compute_scene_asl_target(gothic_shots, "gothic_horror", "dread")
test("Gothic horror ASL target > 5s",
     asl["target_asl"] > 5.0, f"Got: {asl['target_asl']}")
test("Gothic horror with dread has modifier > 1.0",
     asl["target_asl"] > ASL_TARGETS["gothic_horror"][1], f"Base: {ASL_TARGETS['gothic_horror'][1]}, Got: {asl['target_asl']}")
test("Scene with uniform 6s durations is within range",
     asl["within_range"], f"Range: {asl['min_asl']}-{asl['max_asl']}, Current: {asl['current_asl']}")

# Action genre should have much shorter target
action_shots = [{"shot_id": f"act_{i}", "duration": 2.5} for i in range(20)]
action_asl = compute_scene_asl_target(action_shots, "action", "anger")
test("Action ASL target < 3s",
     action_asl["target_asl"] < 3.0, f"Got: {action_asl['target_asl']}")

# Very short shots should get flagged
short_shots = [{"shot_id": "001_001", "duration": 1.0}]
short_asl = compute_scene_asl_target(short_shots, "gothic_horror", "neutral")
test("1s shot flagged as too short for gothic horror",
     len(short_asl["adjustments"]) >= 1, f"Got adjustments: {short_asl['adjustments']}")

# Very long shot should get flagged
long_shots = [{"shot_id": "001_001", "duration": 25.0}]
long_asl = compute_scene_asl_target(long_shots, "gothic_horror", "neutral")
test("25s shot flagged for gothic horror",
     len(long_asl["adjustments"]) >= 1, f"Got adjustments: {long_asl['adjustments']}")

# Empty scene should return safe defaults
empty_asl = compute_scene_asl_target([], "drama")
test("Empty scene returns valid defaults",
     empty_asl["target_asl"] > 0, f"Got: {empty_asl}")


# ============================================================
# GROUP 3: Audio Transition Classification (J/L Cuts)
# ============================================================
print("\n--- Group 3: Audio Transition Classification ---")

dialogue_shot = {"shot_id": "001_001C", "dialogue_text": "I know the truth", "characters": ["EVELYN"]}
broll_shot = {"shot_id": "001_002B", "_broll": True, "characters": []}
next_dialogue = {"shot_id": "001_003C", "dialogue_text": "What do you mean?", "characters": ["THOMAS"]}
reaction_shot = {"shot_id": "001_004C", "nano_prompt": "EVELYN reacts, face shifts", "characters": ["EVELYN"]}

test("Dialogue → B-roll = l_cut",
     classify_audio_transition(dialogue_shot, broll_shot) == "l_cut")
test("B-roll → dialogue = j_cut",
     classify_audio_transition(broll_shot, next_dialogue) == "j_cut")
test("Dialogue → dialogue = straight_cut",
     classify_audio_transition(dialogue_shot, next_dialogue) == "straight_cut")
test("Dialogue → reaction = l_cut",
     classify_audio_transition(dialogue_shot, reaction_shot) == "l_cut")
test("B-roll → B-roll = no_audio",
     classify_audio_transition(broll_shot, {"_broll": True}) == "no_audio")


# ============================================================
# GROUP 4: Frame Reuse Detection
# ============================================================
print("\n--- Group 4: Frame Reuse Detection ---")

static_shots = [
    {"shot_id": "001_001C", "characters": ["EVELYN"], "location": "MANOR LIBRARY",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN sitting, tears in her eyes, hands still", "duration": 5},
    {"shot_id": "001_002C", "characters": ["EVELYN"], "location": "MANOR LIBRARY",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN sitting, grief pools in her gaze", "duration": 4},
]
reuse = analyze_frame_reuse(static_shots)
test("Detects frame reuse for static same-framing",
     any(d.decision == "reuse_frame" for d in reuse),
     f"Got: {[d.decision for d in reuse]}")

# Different locations should NOT reuse
diff_loc_shots = [
    {"shot_id": "001_001C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN sitting still", "duration": 5},
    {"shot_id": "001_002C", "characters": ["EVELYN"], "location": "GARDEN",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN sitting still", "duration": 5},
]
no_reuse = analyze_frame_reuse(diff_loc_shots)
test("No reuse across different locations",
     not any(d.decision == "reuse_frame" for d in no_reuse))

# Moving character should NOT reuse
moving_shots = [
    {"shot_id": "001_001C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "medium", "coverage_role": "B_ACTION",
     "nano_prompt": "EVELYN walks across the room, approaches the window", "duration": 5},
    {"shot_id": "001_002C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "medium", "coverage_role": "B_ACTION",
     "nano_prompt": "EVELYN turns around sharply", "duration": 4},
]
no_move_reuse = analyze_frame_reuse(moving_shots)
test("No reuse when character is moving",
     not any(d.decision == "reuse_frame" for d in no_move_reuse))


# ============================================================
# GROUP 5: B-Roll Overlay Detection
# ============================================================
print("\n--- Group 5: B-Roll Overlay Detection ---")

overlay_shots = [
    {"shot_id": "001_001C", "dialogue_text": "She never told me the truth",
     "characters": ["EVELYN"], "location": "MANOR", "scene_id": "001"},
    {"shot_id": "001_002B", "_broll": True, "shot_type": "detail",
     "characters": [], "location": "MANOR", "scene_id": "001",
     "nano_prompt": "candle flames flicker in the dark"},
    {"shot_id": "001_003C", "dialogue_text": "I found the letter",
     "characters": ["EVELYN"], "location": "MANOR", "scene_id": "001"},
]
overlays = analyze_broll_overlays(overlay_shots)
test("Detects B-roll overlay between dialogue shots",
     len(overlays) >= 1, f"Got: {len(overlays)}")
test("Overlay references the dialogue shot",
     overlays[0].source_shot_id == "001_001C" if overlays else False,
     f"Got: {overlays[0].source_shot_id if overlays else 'none'}")

# B-roll NOT after dialogue = no overlay
no_overlay_shots = [
    {"shot_id": "001_001A", "characters": [], "location": "MANOR",
     "scene_id": "001", "nano_prompt": "wide establishing shot"},
    {"shot_id": "001_002B", "_broll": True, "characters": [],
     "location": "MANOR", "scene_id": "001"},
]
no_overlays = analyze_broll_overlays(no_overlay_shots)
test("No overlay when previous is not dialogue",
     len(no_overlays) == 0, f"Got: {len(no_overlays)}")


# ============================================================
# GROUP 6: Hold-vs-Cut Decisions
# ============================================================
print("\n--- Group 6: Hold-vs-Cut Decisions ---")

hold_candidates = [
    {"shot_id": "001_001C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN standing still, tears forming", "duration": 5},
    {"shot_id": "001_002C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN standing still, grief deepens", "duration": 4},
]
holds = analyze_hold_opportunities(hold_candidates)
test("Detects hold opportunity for same static framing",
     any(d.decision == "hold_extend" for d in holds),
     f"Got: {[d.decision for d in holds]}")

# Different framing should NOT hold
diff_frame_shots = [
    {"shot_id": "001_001A", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "wide", "coverage_role": "A_GEOGRAPHY",
     "nano_prompt": "EVELYN standing still", "duration": 5},
    {"shot_id": "001_002C", "characters": ["EVELYN"], "location": "MANOR",
     "scene_id": "001", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "nano_prompt": "EVELYN standing still, tight on face", "duration": 4},
]
no_holds = analyze_hold_opportunities(diff_frame_shots)
# Should NOT suggest holding when framing changes (different shot type = different visual info)
test("No hold when framing changes (wide → close_up)",
     not any(d.decision == "hold_extend" and d.confidence >= 0.8 for d in no_holds),
     f"Got: {[(d.decision, d.confidence) for d in no_holds]}")


# ============================================================
# GROUP 7: Full Editorial Plan (Integration)
# ============================================================
print("\n--- Group 7: Full Editorial Plan ---")

scene_shots = [
    {"shot_id": "003_001A", "characters": ["EVELYN", "THOMAS"], "location": "MANOR STUDY",
     "scene_id": "003", "shot_type": "wide", "coverage_role": "A_GEOGRAPHY",
     "emotion": "tension", "nano_prompt": "wide establishing shot, EVELYN and THOMAS face each other",
     "duration": 6},
    {"shot_id": "003_002C", "characters": ["EVELYN"], "location": "MANOR STUDY",
     "scene_id": "003", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "emotion": "tension", "dialogue_text": "You knew all along",
     "nano_prompt": "EVELYN close up, jaw clenched, speaking with intensity", "duration": 5},
    {"shot_id": "003_003B", "_broll": True, "characters": [], "location": "MANOR STUDY",
     "scene_id": "003", "shot_type": "detail",
     "nano_prompt": "tight on the sealed letter on the desk, candlelight", "duration": 3},
    {"shot_id": "003_004C", "characters": ["THOMAS"], "location": "MANOR STUDY",
     "scene_id": "003", "shot_type": "close_up", "coverage_role": "C_EMOTION",
     "emotion": "grief", "nano_prompt": "THOMAS reacts, weight sinks, eyes averted",
     "dialogue_text": "I had no choice", "duration": 5},
]

plan = build_editorial_plan(scene_shots, scene_id="003", genre="gothic_horror")
test("Plan has correct total shots",
     plan.total_shots == 4, f"Got: {plan.total_shots}")
test("Plan detects B-roll overlay",
     plan.overlay_count >= 1, f"Got: {plan.overlay_count}")
test("Plan has cut scores",
     hasattr(plan, '_cut_scores') and len(plan._cut_scores) > 0,
     f"Got: {len(getattr(plan, '_cut_scores', []))}")
test("Plan has ASL report",
     hasattr(plan, '_asl_report') and plan._asl_report.get("target_asl", 0) > 0,
     f"Got: {getattr(plan, '_asl_report', {})}")

# Report generation
report = editorial_report(plan)
test("Report is non-empty string",
     len(report) > 100, f"Got {len(report)} chars")
test("Report contains ASL data",
     "ASL" in report, f"Report snippet: {report[:200]}")

# Apply tags
tagged_count = apply_editorial_tags(scene_shots, plan)
test("Tags applied to shots",
     tagged_count >= 1, f"Got: {tagged_count}")


# ============================================================
# GROUP 8: AI Gap Workaround Mapping
# ============================================================
print("\n--- Group 8: AI Gap Workaround Mapping ---")

test("AI_GAP_WORKAROUNDS has character_drift",
     "character_drift" in AI_GAP_WORKAROUNDS)
test("AI_GAP_WORKAROUNDS has environment_inconsistency",
     "environment_inconsistency" in AI_GAP_WORKAROUNDS)
test("AI_GAP_WORKAROUNDS has temporal_coherence",
     "temporal_coherence" in AI_GAP_WORKAROUNDS)
test("AI_GAP_WORKAROUNDS has morphing_artifacts",
     "morphing_artifacts" in AI_GAP_WORKAROUNDS)
test("AI_GAP_WORKAROUNDS has dialogue_lip_sync",
     "dialogue_lip_sync" in AI_GAP_WORKAROUNDS)

# Each workaround maps to an editorial solution
for gap_name, gap_data in AI_GAP_WORKAROUNDS.items():
    test(f"  {gap_name} has editorial_solution",
         gap_data.get("editorial_solution") in ("frame_reuse", "hold_extend", "overlay_broll"),
         f"Got: {gap_data.get('editorial_solution')}")


# ============================================================
# GROUP 9: Stitch Plan Generation
# ============================================================
print("\n--- Group 9: Stitch Plan Generation ---")

stitch_shots = [
    {"shot_id": "001_001C", "duration": 5},
    {"shot_id": "001_002B", "_overlay_on": "001_001C", "_overlay_type": "cutaway", "duration": 3},
    {"shot_id": "001_003C", "_reuse_frame_from": "001_001C", "_editorial_skip_gen": True, "duration": 4},
    {"shot_id": "001_004C", "_hold_extension": 2.0, "_hold_source": "001_003C",
     "_editorial_skip_gen": True, "duration": 2},
    {"shot_id": "001_005C", "duration": 5},  # Normal sequential
]

stitch_plan = build_overlay_stitch_plan(stitch_shots)
test("Stitch plan has 5 entries",
     len(stitch_plan) == 5, f"Got: {len(stitch_plan)}")
test("First shot is sequential",
     stitch_plan[0]["type"] == "sequential")
test("Second shot is overlay",
     stitch_plan[1]["type"] == "overlay")
test("Overlay references correct base shot",
     stitch_plan[1].get("overlay_on") == "001_001C")
test("Third shot is reuse",
     stitch_plan[2]["type"] == "reuse")
test("Fourth shot is hold",
     stitch_plan[3]["type"] == "hold")
test("Fifth shot is sequential",
     stitch_plan[4]["type"] == "sequential")

# Generation filter
need_gen, skip_gen = filter_shots_for_generation(stitch_shots)
test("Filter identifies 3 shots needing generation",
     len(need_gen) == 3, f"Got: {len(need_gen)}")
test("Filter identifies 2 shots to skip",
     len(skip_gen) == 2, f"Got: {len(skip_gen)}")


# ============================================================
# GROUP 10: Helper Functions
# ============================================================
print("\n--- Group 10: Helper Functions ---")

test("Static character detected (sitting, no movement)",
     _is_character_static({"nano_prompt": "EVELYN sitting still, grief in her eyes"}))
test("Moving character detected (walks across)",
     not _is_character_static({"nano_prompt": "EVELYN walks across the room to the window"}))
test("Dialogue without movement is static",
     _is_character_static({"dialogue_text": "I know", "nano_prompt": "EVELYN speaks firmly"}))

test("Same blocking detected",
     _same_blocking(
         {"characters": ["EVELYN"], "location": "MANOR", "shot_id": "001_001"},
         {"characters": ["EVELYN"], "location": "MANOR", "shot_id": "001_002"},
     ))
test("Different characters = different blocking",
     not _same_blocking(
         {"characters": ["EVELYN"], "location": "MANOR", "shot_id": "001_001"},
         {"characters": ["THOMAS"], "location": "MANOR", "shot_id": "001_002"},
     ))

test("Same framing detected (close_up + close_up)",
     _is_same_framing(
         {"shot_type": "close_up", "coverage_role": "C_EMOTION"},
         {"shot_type": "close_up", "coverage_role": "C_EMOTION"},
     ))
test("Close variants count as same framing",
     _is_same_framing(
         {"shot_type": "close_up", "coverage_role": "C_EMOTION"},
         {"shot_type": "extreme_close_up", "coverage_role": "C_EMOTION"},
     ))
test("Wide vs close = different framing",
     not _is_same_framing(
         {"shot_type": "wide", "coverage_role": "A_GEOGRAPHY"},
         {"shot_type": "close_up", "coverage_role": "C_EMOTION"},
     ))


# ============================================================
# GROUP 11: Emotion Inference (the fix that production exposed)
# ============================================================
print("\n--- Group 11: Emotion Inference ---")

from tools.editorial_intelligence import _infer_emotion_from_prompt

test("Infers dread from dark/ominous prompt",
     _infer_emotion_from_prompt({"nano_prompt": "dark shadows creep through the ominous corridor"}) == "dread")
test("Infers revelation from shock/discover prompt",
     _infer_emotion_from_prompt({"nano_prompt": "she discovers the hidden letter, stunned realization"}) == "revelation")
test("Infers grief from mourning prompt",
     _infer_emotion_from_prompt({"nano_prompt": "tears stream down her face, grief overwhelms"}) == "grief")
test("Infers fear from terrified prompt",
     _infer_emotion_from_prompt({"nano_prompt": "she backs away terrified, panic in her eyes"}) == "fear")
test("Returns neutral for generic prompt",
     _infer_emotion_from_prompt({"nano_prompt": "woman standing in a room"}) == "neutral")
test("Prefers explicit emotion field over inference",
     _infer_emotion_from_prompt({"emotion": "anger", "nano_prompt": "dark ominous corridor"}) == "anger")
test("Handles int emotion_level without crashing",
     _infer_emotion_from_prompt({"emotion_level": 7, "nano_prompt": "dark corridor"}) == "dread")
test("Handles None emotion without crashing",
     _infer_emotion_from_prompt({"emotion": None, "nano_prompt": "gentle warmth between them"}) == "love")


# ============================================================
# GROUP 12: Production Stress Test (real Victorian Shadows data)
# ============================================================
print("\n--- Group 12: Production Stress Test ---")

import json
SHOT_PLAN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "pipeline_outputs", "victorian_shadows_ep1", "shot_plan.json")
if os.path.exists(SHOT_PLAN_PATH):
    with open(SHOT_PLAN_PATH) as f:
        real_plan = json.load(f)
    if isinstance(real_plan, list):
        real_plan = {"shots": real_plan}
    real_shots = real_plan.get("shots", [])

    if len(real_shots) > 20:
        # Emotion inference covers real data
        real_emotions = [_infer_emotion_from_prompt(s) for s in real_shots]
        non_neutral = sum(1 for e in real_emotions if e != "neutral")
        test(f"Emotion inference covers >60% of {len(real_shots)} real shots",
             non_neutral / len(real_shots) > 0.6,
             f"Got: {non_neutral}/{len(real_shots)} = {100*non_neutral//len(real_shots)}%")

        # Murch scores differentiate (not all same score)
        real_scenes = {}
        for s in real_shots:
            sid = s.get("scene_id", s.get("shot_id", "").split("_")[0])
            real_scenes.setdefault(sid, []).append(s)

        all_scores = []
        for sid in sorted(real_scenes.keys()):
            ss = real_scenes[sid]
            for i in range(1, len(ss)):
                cs = score_cut_point(ss[i-1], ss[i])
                all_scores.append(cs["total"])

        if all_scores:
            score_range = max(all_scores) - min(all_scores)
            avg_score = sum(all_scores) / len(all_scores)
            strong = sum(1 for s in all_scores if s >= 0.55)

            test(f"Murch scores have range > 0.2 (differentiation)",
                 score_range > 0.2, f"Got range: {score_range:.3f}")
            test(f"Average Murch > 0.55 (healthy cut quality)",
                 avg_score > 0.55, f"Got: {avg_score:.3f}")
            test(f">40% of cuts score strong (editorial confidence)",
                 strong / len(all_scores) > 0.4,
                 f"Got: {strong}/{len(all_scores)} = {100*strong//len(all_scores)}%")
            test(f"Best cut > 0.8 (emotion escalation detected)",
                 max(all_scores) > 0.8, f"Got max: {max(all_scores):.3f}")

        # B-roll overlays detected in real data
        total_overlays = 0
        for sid in sorted(real_scenes.keys()):
            ss = real_scenes[sid]
            plan = build_editorial_plan(ss, scene_id=sid, genre="gothic_horror")
            total_overlays += plan.overlay_count

        # V26 Doctrine 256: Use explicit flags, not shot_id suffix
        broll_count = sum(1 for s in real_shots if s.get("_broll") or s.get("is_broll"))
        test(f"Detects overlays for B-roll ({broll_count} B-roll shots in data)",
             total_overlays > 0 if broll_count > 0 else True,
             f"Got: {total_overlays} overlays from {broll_count} B-roll shots")
    else:
        print("  SKIP  Not enough real shots for stress test")
else:
    print("  SKIP  Victorian Shadows shot plan not found — production stress test skipped")


# ============================================================
# RESULTS
# ============================================================
print()
print("=" * 60)
print(f"EDITORIAL INTELLIGENCE: {PASS} PASS, {FAIL} FAIL out of {TOTAL} tests")
if FAIL == 0:
    print("ALL TESTS PASS — Editor's cerebellum verified")
else:
    print(f"  {FAIL} FAILURES — fix before production use")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
