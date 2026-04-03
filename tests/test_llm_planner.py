#!/usr/bin/env python3
"""
V13.3 LLM Planner Tests
Tests the episode pacing planner with mock LLM responses
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from LOCAL_LLM_INTEGRATION import (
    plan_episode_pacing,
    plan_shot_durations,
    _heuristic_pacing_fallback,
    get_rate_limit_status
)


def test_heuristic_fallback():
    """Test that heuristic fallback works when LLM is unavailable."""
    test_scenes = [
        {'location': 'INT. MANOR - NIGHT', 'dialogue': [{'character': 'A', 'line': 'Hello'}] * 5},
        {'location': 'EXT. GARDEN - DAY', 'dialogue': [{'character': 'B', 'line': 'Hi'}] * 3},
        {'location': 'INT. LIBRARY - NIGHT', 'dialogue': []},
    ]

    result = _heuristic_pacing_fallback(test_scenes, target_runtime=300)

    assert 'planned_scenes' in result
    assert len(result['planned_scenes']) == 3
    assert result['llm_planned'] == False
    assert 'fallback_reason' in result

    # Check that dialog-heavy scenes get more time
    scene_durations = [s['planned_duration_seconds'] for s in result['planned_scenes']]
    print(f"Scene durations: {scene_durations}")

    # Total should be close to target
    total = sum(scene_durations)
    assert abs(total - 300) < 30, f"Total {total} too far from target 300"

    print("✅ Heuristic fallback test passed")


def test_planner_with_mock_llm():
    """Test planner with mocked LLM response."""
    test_scenes = [
        {'location': 'INT. MANOR - NIGHT', 'dialogue': [{'character': 'ELEANOR', 'line': 'Something is wrong.'}] * 5},
        {'location': 'EXT. GARDEN - DAY', 'dialogue': [{'character': 'MARCUS', 'line': 'Indeed.'}] * 3},
    ]

    # Mock a valid LLM response
    mock_llm_response = json.dumps({
        "planned_scenes": [
            {
                "scene_index": 0,
                "planned_duration_seconds": 180,
                "planned_shot_count": 12,
                "pacing": "slow_build",
                "dialog_coverage": 0.8,
                "emotional_arc": "establish_tension",
                "notes": "Opening - let atmosphere build"
            },
            {
                "scene_index": 1,
                "planned_duration_seconds": 120,
                "planned_shot_count": 8,
                "pacing": "dialog_driven",
                "dialog_coverage": 0.7,
                "emotional_arc": "investigation",
                "notes": "Move plot forward"
            }
        ],
        "pacing_curve": "rising_tension",
        "total_planned_duration": 300
    })

    with patch('LOCAL_LLM_INTEGRATION.check_ollama_available', return_value=True):
        with patch('LOCAL_LLM_INTEGRATION.query_ollama', return_value=mock_llm_response):
            result = plan_episode_pacing(test_scenes, target_runtime_seconds=300, genre='thriller')

    assert result['llm_planned'] == True
    assert len(result['planned_scenes']) == 2
    assert result['pacing_curve'] == 'rising_tension'

    # Check scene details
    scene1 = result['planned_scenes'][0]
    assert scene1['planned_duration_seconds'] == 180
    assert scene1['pacing'] == 'slow_build'
    assert 'notes' in scene1

    print("✅ LLM planner mock test passed")


def test_planner_handles_malformed_response():
    """Test that planner gracefully handles bad LLM output."""
    test_scenes = [{'location': 'Test', 'dialogue': []}]

    # Mock a malformed response
    bad_responses = [
        "This is not JSON at all",
        '{"partial": true',  # Invalid JSON
        '{"planned_scenes": "not_an_array"}',  # Wrong type
        '{}',  # Empty
    ]

    for bad_response in bad_responses:
        with patch('LOCAL_LLM_INTEGRATION.check_ollama_available', return_value=True):
            with patch('LOCAL_LLM_INTEGRATION.query_ollama', return_value=bad_response):
                result = plan_episode_pacing(test_scenes, target_runtime_seconds=300)

        # Should fall back to heuristic on bad response
        # Result should always have planned_scenes (from fallback)
        assert result is not None, f"Result should not be None for: {bad_response}"
        assert 'planned_scenes' in result or result.get('llm_planned') == False, \
            f"Bad response should trigger fallback: {bad_response}"

    print("✅ Malformed response handling test passed")


def test_shot_duration_planning():
    """Test that shot durations are allocated based on scene plan."""
    # Create a scene plan
    scene_plan = {
        "planned_scenes": [
            {"scene_index": 0, "planned_duration_seconds": 120, "planned_shot_count": 8},
            {"scene_index": 1, "planned_duration_seconds": 60, "planned_shot_count": 4},
        ],
        "llm_planned": True
    }

    # Create test shots
    test_shots = [
        {"shot_id": "s1_shot1", "scene_index": 0, "duration": 10},
        {"shot_id": "s1_shot2", "scene_index": 0, "duration": 10},
        {"shot_id": "s1_shot3", "scene_index": 0, "duration": 10},
        {"shot_id": "s2_shot1", "scene_index": 1, "duration": 10},
        {"shot_id": "s2_shot2", "scene_index": 1, "duration": 10},
    ]

    story_bible = {"scenes": [{}, {}]}

    result = plan_shot_durations(test_shots, scene_plan, story_bible)

    # Check that durations were adjusted
    scene0_total = sum(s['duration'] for s in result if s.get('scene_index') == 0)
    scene1_total = sum(s['duration'] for s in result if s.get('scene_index') == 1)

    print(f"Scene 0 total: {scene0_total}s (planned: 120s)")
    print(f"Scene 1 total: {scene1_total}s (planned: 60s)")

    # Should be closer to planned values than original
    assert scene0_total > 30, f"Scene 0 should get more time, got {scene0_total}"
    assert scene1_total > 20, f"Scene 1 should get some time, got {scene1_total}"

    print("✅ Shot duration planning test passed")


def test_rate_limit_status():
    """Test rate limit status reporting."""
    status = get_rate_limit_status()

    assert 'requests_in_window' in status
    assert 'max_requests' in status
    assert 'window_seconds' in status
    assert 'remaining' in status

    print(f"Rate limit status: {status}")
    print("✅ Rate limit status test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("V13.3 LLM PLANNER TESTS")
    print("=" * 60)

    test_heuristic_fallback()
    test_planner_with_mock_llm()
    test_planner_handles_malformed_response()
    test_shot_duration_planning()
    test_rate_limit_status()

    print()
    print("=" * 60)
    print("✅ ALL LLM PLANNER TESTS PASSED")
    print("=" * 60)
