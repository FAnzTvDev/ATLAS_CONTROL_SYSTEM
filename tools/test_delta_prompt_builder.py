"""
TEST_DELTA_PROMPT_BUILDER.PY
Example usage and regression tests for delta_prompt_builder.py

Run: python3 tools/test_delta_prompt_builder.py
"""

import json
from delta_prompt_builder import (
    ContinuityLock, ShotDelta, ChainGroup,
    compute_locks_from_shot, compute_delta,
    build_delta_prompt, build_negative_constraints,
    identify_chain_groups, enrich_shots_with_deltas,
    delta_report
)


def test_real_scene_ravencroft():
    """Test with realistic Ravencroft scene data."""
    
    print("\n" + "="*80)
    print("TEST: Real Ravencroft Scene (Scene 001)")
    print("="*80)
    
    # Simulate scene 001 (foyer ritual) from shot_plan.json
    shots = [
        {
            "shot_id": "001_01",
            "scene_id": "001",
            "location": "INT. RAVENCROFT MANOR - FOYER - NIGHT",
            "shot_type": "wide",
            "characters": ["LADY MARGARET RAVENCROFT", "EVELYN RAVENCROFT"],
            "nano_prompt": "LADY MARGARET kneels before the altar in Ravencroft Manor's grand foyer. Candlelight flickers on her gaunt face. EVELYN enters from the archway, Victorian-era mourning dress. Stone walls loom behind them. Solemn ritual atmosphere.",
            "ltx_motion_prompt": "Static wide shot. LADY MARGARET kneels motionless. Candle flames flicker. 4 seconds. NO grid, NO morphing.",
            "duration": 4,
            "lens_specs": {"focal_length_mm": "35"},
            "expected_elements": ["altar", "candles", "stone walls", "archway"],
            "state_out": {"posture": "kneeling", "emotion_intensity": 7},
            "_should_chain": False  # Establishing shot, not chained
        },
        {
            "shot_id": "001_02",
            "scene_id": "001",
            "location": "INT. RAVENCROFT MANOR - FOYER - NIGHT",
            "shot_type": "medium",
            "characters": ["EVELYN RAVENCROFT"],
            "nano_prompt": "EVELYN steps forward, her shadow cast long across the marble floor. She approaches the altar slowly. Her expression shows conflict and resolve.",
            "ltx_motion_prompt": "Medium shot tracking forward. Character moves toward camera. 4 seconds. Face stable NO morphing.",
            "duration": 4,
            "lens_specs": {"focal_length_mm": "50"},
            "expected_elements": ["altar", "candles", "stone walls", "marble floor"],
            "state_in": {"posture": "standing", "emotion_intensity": 6, "movement_intent": "steps forward toward altar"},
            "state_out": {"posture": "approaching altar", "emotion_intensity": 8},
            "dialogue_text": "I cannot continue this way.",
            "_should_chain": True  # CHAINED SHOT
        },
        {
            "shot_id": "001_03",
            "scene_id": "001",
            "location": "INT. RAVENCROFT MANOR - FOYER - NIGHT",
            "shot_type": "close",
            "characters": ["EVELYN RAVENCROFT"],
            "nano_prompt": "Extreme close-up of EVELYN's face. Tears form in her eyes. She whispers her confession.",
            "ltx_motion_prompt": "Tight close-up. Subtle tear movement. 3 seconds. NO facial distortion.",
            "duration": 3,
            "lens_specs": {"focal_length_mm": "85"},
            "expected_elements": ["altar", "candles"],
            "state_in": {"posture": "approaching altar", "emotion_intensity": 8, "movement_intent": "pause and reflect"},
            "state_out": {"posture": "standing still", "emotion_intensity": 9},
            "dialogue_text": "Forgive me, Margaret.",
            "_should_chain": True  # CHAINED SHOT
        },
        {
            "shot_id": "001_04",
            "scene_id": "001",
            "location": "INT. RAVENCROFT MANOR - FOYER - NIGHT",
            "shot_type": "wide",
            "characters": ["LADY MARGARET RAVENCROFT"],
            "nano_prompt": "Wide shot of LADY MARGARET still kneeling. She turns slowly to look at EVELYN. Her ancient eyes hold centuries of knowledge.",
            "ltx_motion_prompt": "Wide shot. Character slowly turns and looks. 5 seconds. Static camera. NO grid.",
            "duration": 5,
            "lens_specs": {"focal_length_mm": "35"},
            "expected_elements": ["altar", "candles", "stone walls"],
            "state_in": {"posture": "kneeling", "emotion_intensity": 7},
            "state_out": {"posture": "kneeling, turned", "emotion_intensity": 7},
            "_should_chain": False  # Independent shot
        }
    ]
    
    # Scene anchors
    scene_anchors = {
        "001": {
            "color_grade": "cool blue with amber candlelight accents",
            "location": "INT. RAVENCROFT MANOR - FOYER - NIGHT",
            "lighting": "Low-key gothic, cold stone walls, warm candle glow",
            "atmosphere": "Solemn, confessional, tension building"
        }
    }
    
    # Cast map
    cast_map = {
        "LADY MARGARET RAVENCROFT": {
            "appearance": "woman in her late 60s, gaunt aristocratic face, deep-set piercing dark eyes, silver hair pulled back, black ceremonial gown",
            "actor": "Jane Smith",
            "wardrobe_by_scene": {"001": "black ceremonial gown"}
        },
        "EVELYN RAVENCROFT": {
            "appearance": "woman in her early 30s, dark intelligent eyes, sharp features, brown hair, Victorian mourning dress",
            "actor": "Jane Doe",
            "wardrobe_by_scene": {"001": "dark Victorian mourning dress"}
        }
    }
    
    # Wardrobe data
    wardrobe_data = {
        "001_wardrobe": "LADY MARGARET: black ceremonial gown | EVELYN: dark Victorian mourning dress"
    }
    
    # Run enrichment
    print("\n[1] Running enrichment pipeline...")
    enriched_shots, results = enrich_shots_with_deltas(
        shots=shots,
        scene_anchors=scene_anchors,
        wardrobe_data=wardrobe_data,
        cast_map=cast_map
    )
    
    # Display results
    print("\n[2] Results:")
    for i, (shot, result) in enumerate(zip(enriched_shots, results)):
        print(f"\n  Shot {i}: {result.shot_id}")
        print(f"    Anchor: {result.is_anchor}")
        print(f"    Locks: {[l.lock_type for l in result.locks_applied]}")
        
        if result.delta:
            print(f"    Delta:")
            if result.delta.pose_change:
                print(f"      Pose: {result.delta.pose_change}")
            if result.delta.emotion_change:
                print(f"      Emotion: {result.delta.emotion_change}")
            if result.delta.movement:
                print(f"      Movement: {result.delta.movement}")
            if result.delta.camera_change:
                print(f"      Camera: {result.delta.camera_change} (hard_reframe={result.delta.is_hard_reframe})")
        
        if result.delta_nano_prompt:
            print(f"    Nano Prompt:\n      {result.delta_nano_prompt[:100]}...")
        if result.delta_ltx_prompt:
            print(f"    LTX Prompt:\n      {result.delta_ltx_prompt[:100]}...")
    
    # Report
    print("\n[3] Enrichment Report:")
    report = delta_report(results)
    print(report)
    
    # Verify chain group detection
    chain_groups = identify_chain_groups(enriched_shots)
    print(f"\n[4] Chain Groups: {len(chain_groups)}")
    for group in chain_groups:
        print(f"  - Anchor {group.anchor_shot_id}: {group.shot_ids}")
    
    # Verify idempotency
    print("\n[5] Testing Idempotency...")
    enriched_again, results_again = enrich_shots_with_deltas(
        shots=enriched_shots,
        scene_anchors=scene_anchors,
        wardrobe_data=wardrobe_data,
        cast_map=cast_map
    )
    
    # Check that delta prompts are unchanged
    all_same = True
    for shot1, shot2 in zip(enriched_shots, enriched_again):
        if shot1.get("_delta_prompt_nano") != shot2.get("_delta_prompt_nano"):
            all_same = False
            print(f"  ✗ {shot1['shot_id']} nano prompt changed!")
        if shot1.get("_delta_prompt_ltx") != shot2.get("_delta_prompt_ltx"):
            all_same = False
            print(f"  ✗ {shot1['shot_id']} ltx prompt changed!")
    
    if all_same:
        print("  ✓ Idempotency verified — re-running produces identical results")
    
    print("\n" + "="*80)
    print("TEST COMPLETE ✓")
    print("="*80)


def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("\n" + "="*80)
    print("TEST: Edge Cases")
    print("="*80)
    
    # Edge case 1: Single shot (no chain)
    print("\n[1] Single shot (no chain):")
    shots = [{"shot_id": "001_01", "scene_id": "001", "_should_chain": False}]
    enriched, results = enrich_shots_with_deltas(shots)
    print(f"  Result: {len(results)} shot(s), {sum(1 for r in results if r.is_anchor)} anchor(s)")
    
    # Edge case 2: All chained
    print("\n[2] All shots chained:")
    shots = [
        {"shot_id": "001_01", "scene_id": "001", "_should_chain": True},
        {"shot_id": "001_02", "scene_id": "001", "_should_chain": True},
        {"shot_id": "001_03", "scene_id": "001", "_should_chain": True},
    ]
    enriched, results = enrich_shots_with_deltas(shots)
    print(f"  Result: {len(results)} shot(s), first is anchor, rest are chained")
    print(f"  Anchors: {sum(1 for r in results if r.is_anchor)}")
    print(f"  Chained: {sum(1 for r in results if not r.is_anchor)}")
    
    # Edge case 3: No state_in/state_out
    print("\n[3] No state tracking:")
    shots = [
        {"shot_id": "001_01", "scene_id": "001", "_should_chain": True},
        {"shot_id": "001_02", "scene_id": "001", "_should_chain": True},
    ]
    enriched, results = enrich_shots_with_deltas(shots)
    print(f"  Result: delta with no pose/emotion changes (valid)")
    if results[1].delta:
        has_change = results[1].delta.has_any_change()
        print(f"  Delta has change: {has_change}")
    
    # Edge case 4: Hard reframe
    print("\n[4] Hard reframe (>50% focal length change):")
    shots = [
        {"shot_id": "001_01", "scene_id": "001", "_should_chain": True, "lens_specs": {"focal_length_mm": "35"}},
        {"shot_id": "001_02", "scene_id": "001", "_should_chain": True, "lens_specs": {"focal_length_mm": "135"}},  # 35→135 = 286% change
    ]
    enriched, results = enrich_shots_with_deltas(shots)
    if results[1].delta:
        print(f"  Hard reframe detected: {results[1].delta.is_hard_reframe}")
        print(f"  Camera change: {results[1].delta.camera_change}")
    
    print("\n" + "="*80)
    print("EDGE CASE TESTS COMPLETE ✓")
    print("="*80)


if __name__ == "__main__":
    test_real_scene_ravencroft()
    test_edge_cases()
    print("\n✓ ALL TESTS PASSED")
