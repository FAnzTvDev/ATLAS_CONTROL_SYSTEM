#!/usr/bin/env python3
"""
ATLAS_BUILD_ACCEPTOR Tests - V13.5
==================================

Comprehensive test suite for the Build Acceptor Agent.
Tests all decision paths, gate validations, and integration with SIMULATION_GATES.

Run with: python3 -m pytest tests/test_build_acceptor.py -v
Or standalone: python3 tests/test_build_acceptor.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from dataclasses import asdict
from typing import Dict, List

from ATLAS_BUILD_ACCEPTOR import (
    ATLASBuildAcceptorAgent,
    AcceptorDecision,
    Decision,
    NextAction,
    SimulationSnapshot,
    evaluate_build_phase,
    should_auto_continue,
    should_halt,
    get_build_acceptor,
)


class TestDecisionTypes(unittest.TestCase):
    """Test that decision types work correctly"""

    def test_decision_enum_values(self):
        """Verify Decision enum has correct values"""
        self.assertEqual(Decision.BLOCK.value, "BLOCK")
        self.assertEqual(Decision.ACCEPT.value, "ACCEPT")
        self.assertEqual(Decision.ACCEPT_AND_CONTINUE.value, "ACCEPT_AND_CONTINUE")

    def test_next_action_enum_values(self):
        """Verify NextAction enum has correct values"""
        self.assertEqual(NextAction.HALT.value, "halt")
        self.assertEqual(NextAction.CONTINUE.value, "continue")
        self.assertEqual(NextAction.AUTO_CONTINUE.value, "auto_continue")


class TestAcceptorDecision(unittest.TestCase):
    """Test AcceptorDecision dataclass"""

    def test_decision_to_dict(self):
        """Test AcceptorDecision serialization"""
        decision = AcceptorDecision(
            decision=Decision.ACCEPT,
            confidence=0.85,
            reasons=["Test reason"],
            next_action=NextAction.CONTINUE,
        )
        d = decision.to_dict()

        self.assertEqual(d["decision"], "ACCEPT")
        self.assertEqual(d["confidence"], 0.85)
        self.assertEqual(d["reasons"], ["Test reason"])
        self.assertEqual(d["next_action"], "continue")

    def test_decision_to_json(self):
        """Test AcceptorDecision JSON serialization"""
        decision = AcceptorDecision(
            decision=Decision.BLOCK,
            confidence=0.0,
            reasons=["Critical failure"],
            next_action=NextAction.HALT,
        )
        json_str = decision.to_json()

        self.assertIn('"decision": "BLOCK"', json_str)
        self.assertIn('"next_action": "halt"', json_str)


class TestCleanPass(unittest.TestCase):
    """Test scenarios that should pass cleanly (ACCEPT_AND_CONTINUE)"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_clean_validation_pass(self):
        """Clean validation with all checks passing"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "test_project",
                "characters": [
                    {"name": "MAYA", "scenes": [1, 2]},
                    {"name": "JACK", "scenes": [1]}
                ],
                "scenes": [
                    {"scene_id": 1, "characters": ["MAYA", "JACK"]},
                    {"scene_id": 2, "characters": ["MAYA"]}
                ],
                "shot_plan": {
                    "shots": [
                        {
                            "shot_id": "1_001",
                            "scene_id": 1,
                            "duration": 10,
                            "nano_prompt": "A detailed establishing shot of the scene",
                            "characters": ["MAYA"]
                        },
                        {
                            "shot_id": "1_002",
                            "scene_id": 1,
                            "duration": 8,
                            "nano_prompt": "Medium shot of MAYA and JACK talking",
                            "characters": ["MAYA", "JACK"]
                        }
                    ]
                }
            },
            validation_results={
                "passed": True,
                "issues": [],
                "blocking_issues": []
            }
        )

        self.assertEqual(result.decision, Decision.ACCEPT_AND_CONTINUE)
        self.assertEqual(result.next_action, NextAction.AUTO_CONTINUE)
        self.assertGreater(result.confidence, 0.9)
        self.assertTrue(should_auto_continue(result))
        self.assertFalse(should_halt(result))

    def test_single_character_scene(self):
        """Single character scene should pass"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "mono_scene",
                "characters": [{"name": "SOLO"}],
                "scenes": [{"scene_id": 1, "characters": ["SOLO"]}],
                "shot_plan": {
                    "shots": [
                        {
                            "shot_id": "1_001",
                            "duration": 12,
                            "nano_prompt": "SOLO walks through empty corridor",
                            "characters": ["SOLO"]
                        }
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.ACCEPT_AND_CONTINUE)


class TestHardGateFailures(unittest.TestCase):
    """Test hard gate failures that should BLOCK"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_ai_actor_name_embedded(self):
        """AI actor name in character should block"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "contaminated",
                "characters": [{"name": "Agent MAYA CHEN"}],
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results={
                "passed": False,
                "issues": [
                    {
                        "code": "AI_ACTOR_NAME_EMBEDDED",
                        "message": "Character contains AI actor name",
                        "severity": "CRITICAL"
                    }
                ],
                "blocking_issues": [
                    {"code": "AI_ACTOR_NAME_EMBEDDED", "message": "AI actor name embedded"}
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertEqual(result.next_action, NextAction.HALT)
        self.assertTrue(should_halt(result))
        self.assertIn("AI_ACTOR_NAME_EMBEDDED", str(result.reasons))

    def test_ai_actor_as_character(self):
        """AI actor used as character name should block"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "actor_as_char",
                "characters": [{"name": "Maya Chen"}],
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results={
                "passed": False,
                "issues": [
                    {"code": "AI_ACTOR_AS_CHARACTER", "message": "Maya Chen is AI actor", "severity": "CRITICAL"}
                ],
                "blocking_issues": [
                    {"code": "AI_ACTOR_AS_CHARACTER", "message": "Maya Chen is AI actor"}
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertTrue(should_halt(result))

    def test_pronoun_as_character(self):
        """Pronoun used as character should block"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "pronoun_char",
                "characters": [{"name": "He"}],
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results={
                "passed": False,
                "issues": [
                    {"code": "PRONOUN_AS_CHARACTER", "message": "'He' is a pronoun", "severity": "CRITICAL"}
                ],
                "blocking_issues": [
                    {"code": "PRONOUN_AS_CHARACTER", "message": "'He' is a pronoun"}
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)

    def test_timeline_violation(self):
        """Timeline violation should block"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "timeline_error",
                "characters": [],
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results={
                "passed": False,
                "issues": [
                    {"code": "TIMELINE_VIOLATION", "message": "Scene 5 before Scene 1", "severity": "CRITICAL"}
                ],
                "blocking_issues": [
                    {"code": "TIMELINE_VIOLATION", "message": "Scene order violated"}
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)

    def test_zero_shots(self):
        """Zero shots should block when validation fails"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "empty",
                "characters": [{"name": "TEST"}],
                "scenes": [{"scene_id": 1}],
                "shot_plan": {"shots": []}
            },
            validation_results={
                "passed": False,
                "issues": [
                    {"code": "ZERO_SHOTS", "message": "No shots generated", "severity": "CRITICAL"}
                ],
                "blocking_issues": [
                    {"code": "ZERO_SHOTS", "message": "No shots"}
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)


class TestSimulationIntegrity(unittest.TestCase):
    """Test simulation integrity checks"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_character_contamination_detected(self):
        """Character appearing in wrong scene should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "contaminated",
                "characters": [
                    {"name": "MAYA", "scenes": [1]},  # MAYA only in scene 1
                    {"name": "JACK", "scenes": [2]}   # JACK only in scene 2
                ],
                "scenes": [
                    {"scene_id": 1, "characters": ["MAYA", "JACK"]},  # JACK shouldn't be here!
                    {"scene_id": 2, "characters": ["JACK"]}
                ],
                "shot_plan": {"shots": []}
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("CONTAMINATION", str(result.reasons).upper())

    def test_zero_duration_shots_blocked(self):
        """Shots with zero duration should block"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "zero_dur",
                "characters": [{"name": "TEST"}],
                "scenes": [{"scene_id": 1}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 0, "nano_prompt": "test prompt with content"},
                        {"shot_id": "1_002", "duration": 10, "nano_prompt": "another test prompt"}
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("DURATION", str(result.reasons).upper())


class TestSilentFailureDetection(unittest.TestCase):
    """Test silent failure detection"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_empty_nano_prompts_detected(self):
        """Most shots having empty prompts should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "empty_prompts",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "", "characters": ["MAYA"]},
                        {"shot_id": "1_002", "duration": 10, "nano_prompt": "", "characters": ["MAYA"]},
                        {"shot_id": "1_003", "duration": 10, "nano_prompt": "x", "characters": ["MAYA"]},
                        {"shot_id": "1_004", "duration": 10, "nano_prompt": "", "characters": ["MAYA"]},
                        {"shot_id": "1_005", "duration": 10, "nano_prompt": "", "characters": ["MAYA"]},
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("SILENT_FAILURE", str(result.reasons))

    def test_duplicate_shot_ids_detected(self):
        """Duplicate shot IDs should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "dup_ids",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "A detailed shot", "characters": ["MAYA"]},
                        {"shot_id": "1_001", "duration": 8, "nano_prompt": "Another shot", "characters": ["MAYA"]},  # DUPLICATE!
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("Duplicate", str(result.reasons))

    def test_unknown_character_in_shot(self):
        """Shot referencing unknown character should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "unknown_char",
                "characters": [{"name": "MAYA"}],  # Only MAYA exists
                "scenes": [{"scene_id": 1}],
                "shot_plan": {
                    "shots": [
                        {
                            "shot_id": "1_001",
                            "duration": 10,
                            "nano_prompt": "Detailed shot prompt here",
                            "characters": ["MAYA", "UNKNOWN_PERSON"]  # UNKNOWN_PERSON doesn't exist!
                        }
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("unknown character", str(result.reasons).lower())

    def test_validation_passed_but_no_characters(self):
        """Validation passed but no characters should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "no_chars",
                "characters": [],  # No characters!
                "scenes": [{"scene_id": 1}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "A shot with content"}
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("no characters", str(result.reasons).lower())


class TestScriptLogicValidation(unittest.TestCase):
    """Test script structure logic validation"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_unknown_speaker_in_dialogue(self):
        """Dialogue from unknown speaker should be detected"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "unknown_speaker",
                "characters": [{"name": "MAYA"}],  # Only MAYA
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            script_structure={
                "scenes": [
                    {
                        "scene_id": 1,
                        "dialogue": [
                            {"character": "MAYA", "line": "Hello"},
                            {"character": "GHOST", "line": "Boo!"}  # GHOST not in characters!
                        ]
                    }
                ]
            }
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("UNKNOWN_SPEAKER", str(result.reasons))

    def test_vo_speaker_allowed(self):
        """V.O. and O.S. speakers should not trigger errors"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "vo_test",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "Maya in scene", "characters": ["MAYA"]}
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            script_structure={
                "scenes": [
                    {
                        "scene_id": 1,
                        "dialogue": [
                            {"character": "V.O.", "line": "Narration"},
                            {"character": "MAYA", "line": "Hello"}
                        ],
                        "actions": ["Maya enters"]
                    }
                ]
            }
        )

        # V.O. should not cause block
        self.assertNotIn("UNKNOWN_SPEAKER", str(result.reasons))


class TestIntentAlignment(unittest.TestCase):
    """Test planner intent vs outcome alignment"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_runtime_variance_warning(self):
        """Large runtime variance should trigger warning"""
        # Create enough shots with valid prompts to avoid silent failure detection
        shots = [
            {"shot_id": f"1_{i:03d}", "duration": 10,
             "nano_prompt": f"A detailed cinematic shot number {i} showing MAYA in the scene",
             "characters": ["MAYA"]}
            for i in range(6)
        ]

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "runtime_off",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {"shots": shots},
                "total_duration": 60  # Actual: 60 seconds
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            planner_outputs={
                "target_runtime": 300  # Target: 300 seconds (5 minutes)
            }
        )

        # Should trigger soft warning, not block
        self.assertEqual(result.decision, Decision.ACCEPT)
        self.assertIn("RUNTIME_VARIANCE", str(result.reasons))

    def test_shot_count_variance_warning(self):
        """Large shot count variance should trigger warning"""
        # Create valid shots with proper prompts
        shots = [
            {"shot_id": f"1_{i:03d}", "duration": 10,
             "nano_prompt": f"A detailed cinematic shot number {i} showing MAYA in the scene",
             "characters": ["MAYA"]}
            for i in range(10)
        ]

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "shot_off",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {"shots": shots}
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            planner_outputs={
                "expected_shot_count": 50  # Expected 50, got 10 (80% off)
            }
        )

        self.assertEqual(result.decision, Decision.ACCEPT)
        self.assertIn("SHOT_COUNT_VARIANCE", str(result.reasons))


class TestContinuityValidation(unittest.TestCase):
    """Test continuity checking against prior snapshots"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_character_removal_breaks_continuity(self):
        """Removing characters should break continuity"""
        # Create prior snapshot with 3 characters
        prior = SimulationSnapshot(
            project="continuity_test",
            phase="casting",
            character_ids=["MAYA", "JACK", "SARAH"],
            scene_ids=["1", "2", "3"],
            shot_count=10,
            total_duration=120,
            artifact_hashes={}
        )

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "continuity_test",
                "characters": [{"name": "MAYA"}],  # Only MAYA - JACK and SARAH removed!
                "scenes": [{"scene_id": 1}],
                "shot_plan": {"shots": []}
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            prior_snapshot=prior
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("CONTINUITY_BREAK", str(result.reasons))

    def test_major_scene_changes_break_continuity(self):
        """Changing more than half of scenes should break continuity"""
        prior = SimulationSnapshot(
            project="scene_test",
            phase="shot_planning",
            character_ids=["MAYA"],
            scene_ids=["1", "2", "3", "4"],  # 4 scenes
            shot_count=20,
            total_duration=200,
            artifact_hashes={}
        )

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "scene_test",
                "characters": [{"name": "MAYA"}],
                "scenes": [
                    {"scene_id": 10},  # Completely different scenes!
                    {"scene_id": 11},
                    {"scene_id": 12}
                ],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "10_001", "duration": 10, "nano_prompt": "Test shot", "characters": ["MAYA"]}
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []},
            prior_snapshot=prior
        )

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("CONTINUITY_BREAK", str(result.reasons))


class TestSnapshotManagement(unittest.TestCase):
    """Test snapshot creation and management"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_snapshot_creation(self):
        """Test that snapshots are created correctly"""
        context = {
            "project": "snapshot_test",
            "characters": [{"name": "MAYA"}, {"name": "JACK"}],
            "scenes": [{"scene_id": 1}, {"scene_id": 2}],
            "shot_plan": {
                "shots": [
                    {"shot_id": "1_001", "duration": 10},
                    {"shot_id": "1_002", "duration": 8}
                ]
            },
            "story_bible": {"title": "Test Story"}
        }

        snapshot = self.acceptor.create_snapshot(context, "first_frames")

        self.assertEqual(snapshot.project, "snapshot_test")
        self.assertEqual(snapshot.phase, "first_frames")
        self.assertEqual(len(snapshot.character_ids), 2)
        self.assertEqual(len(snapshot.scene_ids), 2)
        self.assertEqual(snapshot.shot_count, 2)
        self.assertEqual(snapshot.total_duration, 18)
        self.assertIn("story_bible", snapshot.artifact_hashes)

    def test_snapshot_hash_computation(self):
        """Test that snapshot hashes are deterministic"""
        data = {"key": "value", "nested": {"a": 1}}

        hash1 = SimulationSnapshot.compute_hash(data)
        hash2 = SimulationSnapshot.compute_hash(data)

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)  # Truncated to 16 chars

    def test_snapshot_history_tracking(self):
        """Test that acceptor tracks snapshot history"""
        self.acceptor.create_snapshot(
            {"project": "test1", "characters": [], "scenes": [], "shot_plan": {"shots": []}},
            "phase1"
        )
        self.acceptor.create_snapshot(
            {"project": "test2", "characters": [], "scenes": [], "shot_plan": {"shots": []}},
            "phase2"
        )

        self.assertEqual(len(self.acceptor.snapshot_history), 2)

        latest = self.acceptor.get_latest_snapshot()
        self.assertEqual(latest.phase, "phase2")


class TestConvenienceFunctions(unittest.TestCase):
    """Test the convenience functions for orchestrator integration"""

    def test_evaluate_build_phase(self):
        """Test the main convenience function"""
        result = evaluate_build_phase(
            simulation_context={
                "project": "convenience_test",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "Test prompt", "characters": ["MAYA"]}
                    ]
                }
            },
            validation_results={"passed": True, "issues": [], "blocking_issues": []}
        )

        self.assertIsInstance(result, AcceptorDecision)
        self.assertIn(result.decision, [Decision.BLOCK, Decision.ACCEPT, Decision.ACCEPT_AND_CONTINUE])

    def test_should_auto_continue_helper(self):
        """Test should_auto_continue helper"""
        auto_decision = AcceptorDecision(
            decision=Decision.ACCEPT_AND_CONTINUE,
            confidence=1.0,
            reasons=[],
            next_action=NextAction.AUTO_CONTINUE
        )

        self.assertTrue(should_auto_continue(auto_decision))

        halt_decision = AcceptorDecision(
            decision=Decision.BLOCK,
            confidence=0.0,
            reasons=["Error"],
            next_action=NextAction.HALT
        )

        self.assertFalse(should_auto_continue(halt_decision))

    def test_should_halt_helper(self):
        """Test should_halt helper"""
        halt_decision = AcceptorDecision(
            decision=Decision.BLOCK,
            confidence=0.0,
            reasons=["Error"],
            next_action=NextAction.HALT
        )

        self.assertTrue(should_halt(halt_decision))

        continue_decision = AcceptorDecision(
            decision=Decision.ACCEPT,
            confidence=0.7,
            reasons=["Warning"],
            next_action=NextAction.CONTINUE
        )

        self.assertFalse(should_halt(continue_decision))


class TestGateSummary(unittest.TestCase):
    """Test gate summary generation"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_gate_summary_counts(self):
        """Test that gate summary counts are accurate"""
        result = self.acceptor.evaluate(
            simulation_context={
                "project": "summary_test",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {
                    "shots": [
                        {"shot_id": "1_001", "duration": 10, "nano_prompt": "Test", "characters": ["MAYA"]}
                    ]
                }
            },
            validation_results={
                "passed": False,
                "issues": [
                    {"code": "AI_ACTOR_AS_CHARACTER", "message": "Hard failure", "severity": "CRITICAL"},
                    {"code": "SHORT_DIALOGUE", "message": "Soft warning"},
                    {"code": "POTENTIAL_DUPLICATE", "message": "Another soft warning"},
                    {"code": "UNKNOWN_CODE", "message": "Other issue"}
                ],
                "blocking_issues": []
            }
        )

        summary = result.gate_summary
        self.assertEqual(summary["total_gates"], 4)
        self.assertEqual(summary["hard_failures"], 1)  # AI_ACTOR_AS_CHARACTER
        self.assertEqual(summary["soft_warnings"], 2)  # SHORT_DIALOGUE, POTENTIAL_DUPLICATE


class TestIntegrationWithSimulationGates(unittest.TestCase):
    """Test integration with existing SIMULATION_GATES.py"""

    def setUp(self):
        self.acceptor = ATLASBuildAcceptorAgent()

    def test_semantic_gate_format_compatibility(self):
        """Test that Build Acceptor handles Semantic Gate output format"""
        # Format that SIMULATION_GATES produces
        validation_results = {
            "passed": False,
            "issues": [
                {
                    "gate": "SEMANTIC_GATE",
                    "code": "INVALID_CHARACTER_NAME",
                    "severity": "critical",
                    "message": "'He' is not a valid character name (pronoun/term)",
                    "auto_fix_available": True,
                    "auto_fix_action": "REMOVE_CHARACTER:He"
                }
            ],
            "blocking_issues": [
                {"code": "PRONOUN_AS_CHARACTER", "message": "'He' is a pronoun"}
            ]
        }

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "semantic_test",
                "characters": [{"name": "He"}],
                "scenes": [],
                "shot_plan": {"shots": []}
            },
            validation_results=validation_results
        )

        # Should block due to pronoun
        self.assertEqual(result.decision, Decision.BLOCK)

    def test_temporal_gate_format_compatibility(self):
        """Test that Build Acceptor handles Temporal Gate output format"""
        validation_results = {
            "passed": True,  # Temporal issues are warnings
            "issues": [
                {
                    "gate": "TEMPORAL_GATE",
                    "code": "RUNTIME_DEVIATION",
                    "severity": "warning",
                    "message": "Runtime 180s vs target 300s (40% deviation)",
                }
            ],
            "blocking_issues": []
        }

        # Create valid shots with proper prompts to avoid silent failure detection
        shots = [
            {"shot_id": f"1_{i:03d}", "duration": 10,
             "nano_prompt": f"A detailed cinematic shot number {i} showing MAYA in the scene",
             "characters": ["MAYA"]}
            for i in range(5)
        ]

        result = self.acceptor.evaluate(
            simulation_context={
                "project": "temporal_test",
                "characters": [{"name": "MAYA"}],
                "scenes": [{"scene_id": 1, "characters": ["MAYA"]}],
                "shot_plan": {"shots": shots}
            },
            validation_results=validation_results
        )

        # Should pass (warnings don't block)
        self.assertNotEqual(result.decision, Decision.BLOCK)


def run_all_tests():
    """Run all tests and print summary"""
    print("=" * 70)
    print("ATLAS_BUILD_ACCEPTOR Test Suite - V13.5")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()

    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
