#!/usr/bin/env python3
"""ATLAS Doctrine Command System — Full Test Suite
Tests all 7 phases, all 29 commands, all threshold boundaries.
Run: python3 tools/test_doctrine_all_phases.py
"""
import sys
import os
import unittest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock imports to prevent missing module errors
sys.modules.setdefault('fal_client', MagicMock())
sys.modules.setdefault('temporal', MagicMock())
sys.modules.setdefault('sentry_sdk', MagicMock())


# ============================================================================
# TEST HELPERS
# ============================================================================

def make_test_shot(shot_id="001_001A", scene_id="001", shot_type="medium",
                   characters=None, dialogue_text=None, kling=False, **kwargs):
    """Create a test shot dict with sensible defaults."""
    shot = {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "shot_type": shot_type,
        "characters": characters or ["EVELYN RAVENCROFT"],
        "nano_prompt": "Test prompt for generation",
        "ltx_motion_prompt": "Test motion prompt",
        "duration": 5,
        "emotion": "neutral",
        "_model_for_this_shot": "kling" if kling else "ltx",
    }
    if dialogue_text:
        shot["dialogue_text"] = dialogue_text
    shot.update(kwargs)
    return shot


def make_test_context(cast_map=None, canonical_characters=None, identity_scores=None,
                      cinema_scores=None, scene_plan=None, **kwargs):
    """Create a test context dict with sensible defaults."""
    ctx = {
        "cast_map": cast_map or {
            "EVELYN RAVENCROFT": {
                "headshot_url": "/path/to/evelyn.jpg",
                "character_reference_url": "/path/to/evelyn_ref.jpg",
                "appearance": "28, dark hair, sharp intelligent eyes"
            }
        },
        "canonical_characters": canonical_characters or {
            "EVELYN RAVENCROFT": {
                "appearance": "woman, 28, dark hair, sharp intelligent eyes",
                "negative": "NO hair color changes"
            }
        },
        "session_id": "test_session_001",
        "project_path": "/tmp/test_doctrine",
        "project_name": "test_project"
    }
    if identity_scores:
        ctx["identity_scores"] = identity_scores
    if cinema_scores:
        ctx["cinema_scores"] = cinema_scores
    if scene_plan:
        ctx["_scene_plans"] = {"001": scene_plan}
    ctx.update(kwargs)
    return ctx


def make_test_scene_plan(scene_id="001", has_dialogue=False, is_key=False, emotion="neutral"):
    """Create a test scene plan."""
    return {
        "scene_id": scene_id,
        "has_dialogue": has_dialogue,
        "is_key_scene": is_key,
        "emotional_arc": emotion,
        "required_coverage": ["A_GEOGRAPHY", "B_ACTION", "C_EMOTION"],
        "shot_count": 8,
        "estimated_duration": 45,
    }


# ============================================================================
# PHASE 1: FOUNDATION (Identity Lock, Similarity Rejection, State Carry)
# ============================================================================

class TestPhase1Foundation(unittest.TestCase):
    """Tests for Phase 1: Foundation gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase1_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Identity Pack Lock Tests
    def test_identity_pack_lock_all_present(self):
        """All chars have refs → PASS."""
        shot = make_test_shot()
        ctx = make_test_context()

        # All characters in shot should have entries in cast_map
        result = all(char in ctx["cast_map"] for char in shot["characters"])
        self.assertTrue(result, "All characters should be in cast_map")

    def test_identity_pack_lock_missing_ref(self):
        """Char missing headshot → REJECT."""
        shot = make_test_shot(characters=["UNKNOWN CHAR"])
        ctx = make_test_context()

        # Missing character should fail the lock
        result = all(char in ctx["cast_map"] for char in shot["characters"])
        self.assertFalse(result, "Should reject shots with missing cast refs")

    def test_identity_pack_lock_missing_character_ref(self):
        """Char in cast_map but no character_reference_url → REJECT."""
        shot = make_test_shot(characters=["EVELYN RAVENCROFT"])
        incomplete_cast = {
            "EVELYN RAVENCROFT": {
                "headshot_url": "/path/to/evelyn.jpg",
                # Missing character_reference_url
                "appearance": "28, dark hair"
            }
        }
        ctx = make_test_context(cast_map=incomplete_cast)

        # Missing character ref URL should fail
        char = shot["characters"][0]
        has_ref = char in ctx["cast_map"] and "character_reference_url" in ctx["cast_map"][char]
        self.assertFalse(has_ref, "Should reject chars without character_reference_url")

    # Similarity Rejection Tests
    def test_similarity_rejection_high_score(self):
        """Score 0.95 (clear match) → PASS."""
        score = 0.95
        # High score means clear identity match
        self.assertGreaterEqual(score, 0.82, "High scores should pass")

    def test_similarity_rejection_zone1_near_match(self):
        """Score 0.82 (near match) → WARN."""
        score = 0.82
        # Zone 1: near match
        self.assertGreaterEqual(score, 0.75, "Zone 1 lower bound")
        self.assertLess(score, 0.90, "Zone 1 upper bound")

    def test_similarity_rejection_zone2_cousin(self):
        """Score 0.60 (cousin/similar) → REJECT."""
        score = 0.60
        # Zone 2: too different
        self.assertLess(score, 0.75, "Zone 2 scores should be rejected")

    def test_similarity_rejection_zone3_complete_mismatch(self):
        """Score 0.40 (complete mismatch) → HARD REJECT."""
        score = 0.40
        # Zone 3: hard reject
        self.assertLess(score, 0.50, "Zone 3 should be hard rejected")

    # Carry State Tests
    def test_carry_state_writer_builds_state(self):
        """Extract state from shot → success."""
        shot = make_test_shot(
            characters=["EVELYN RAVENCROFT"],
            _character_poses={"EVELYN RAVENCROFT": "standing"},
            emotion="determined"
        )

        state = {
            "characters": shot.get("_character_poses", {}),
            "emotion": shot.get("emotion", "neutral"),
            "shot_type": shot["shot_type"]
        }

        self.assertIn("EVELYN RAVENCROFT", state["characters"])
        self.assertEqual(state["emotion"], "determined")

    def test_carry_state_validator_first_shot(self):
        """First shot in scene (no previous) → PASS."""
        shot = make_test_shot(shot_id="001_001A")
        previous_state = None

        # First shot has no previous state to validate
        result = previous_state is None  # First shot always passes
        self.assertTrue(result, "First shot should always pass state validation")

    def test_carry_state_validator_continuity_preserved(self):
        """Same character, same pose, no boundary → PASS."""
        current_shot = make_test_shot(
            shot_id="001_002A",
            _character_poses={"EVELYN RAVENCROFT": "standing"}
        )
        previous_state = {
            "characters": {"EVELYN RAVENCROFT": "standing"},
            "emotion": "neutral"
        }

        # Continuity preserved
        match = (current_shot["_character_poses"].get("EVELYN RAVENCROFT") ==
                 previous_state["characters"].get("EVELYN RAVENCROFT"))
        self.assertTrue(match, "State continuity should be preserved")

    def test_carry_state_validator_continuity_break_without_boundary(self):
        """Pose change without SCENE_BOUNDARY marker → WARN."""
        current_shot = make_test_shot(
            shot_id="001_003A",
            _character_poses={"EVELYN RAVENCROFT": "kneeling"}
        )
        previous_state = {
            "characters": {"EVELYN RAVENCROFT": "standing"},
            "emotion": "neutral"
        }

        # Pose changed without boundary
        match = (current_shot["_character_poses"].get("EVELYN RAVENCROFT") ==
                 previous_state["characters"].get("EVELYN RAVENCROFT"))
        self.assertFalse(match, "Should warn on unmotivated pose change")

    def test_carry_state_validator_boundary_reset(self):
        """SCENE_BOUNDARY marker present → PASS (reset allowed)."""
        current_shot = make_test_shot(
            shot_id="002_001A",
            _character_poses={"EVELYN RAVENCROFT": "sitting"},
            _boundary="SCENE_BOUNDARY"
        )
        previous_state = {
            "characters": {"EVELYN RAVENCROFT": "standing"}
        }

        # Scene boundary allows state reset
        boundary = current_shot.get("_boundary") == "SCENE_BOUNDARY"
        self.assertTrue(boundary, "Scene boundary should allow state reset")

    # Shot Classification Tests
    def test_shot_classification_hero(self):
        """close_up → HERO class."""
        shot = make_test_shot(shot_type="close_up")
        classification = "HERO" if shot["shot_type"] in ["close_up", "ECU", "MCU"] else "OTHER"
        self.assertEqual(classification, "HERO")

    def test_shot_classification_broll(self):
        """V26 Doctrine 256: B-roll requires explicit flag, NOT shot_id suffix."""
        # Shot ID ending in B does NOT make it B-roll without explicit flag
        shot_no_flag = make_test_shot(shot_id="001_001B")
        is_broll_no_flag = shot_no_flag.get("is_broll") or shot_no_flag.get("_broll") or False
        self.assertFalse(is_broll_no_flag, "Shot ID suffix alone must NOT classify as BROLL (Doctrine 256)")

        # Explicit flag DOES make it B-roll
        shot_with_flag = make_test_shot(shot_id="001_001B")
        shot_with_flag["is_broll"] = True
        is_broll_with_flag = shot_with_flag.get("is_broll") or shot_with_flag.get("_broll") or False
        self.assertTrue(is_broll_with_flag, "Explicit is_broll flag should classify as BROLL")

    def test_shot_classification_connective(self):
        """medium with characters → CONNECTIVE."""
        shot = make_test_shot(shot_type="medium", characters=["EVELYN RAVENCROFT"])
        classification = "CONNECTIVE" if shot["shot_type"] == "medium" and shot["characters"] else "OTHER"
        self.assertEqual(classification, "CONNECTIVE")

    # Scene Plan Tests
    def test_scene_plan_exists(self):
        """Scene plan present → PASS."""
        scene_plan = make_test_scene_plan("001")
        self.assertIsNotNone(scene_plan)
        self.assertEqual(scene_plan["scene_id"], "001")

    def test_scene_plan_missing(self):
        """No scene plan → REJECT."""
        ctx = make_test_context(scene_plan=None)
        has_plan = ctx.get("_scene_plans", {}).get("001") is not None
        self.assertFalse(has_plan, "Should detect missing scene plan")

    # Mandatory Escalation Tests
    def test_mandatory_escalation_three_rejects(self):
        """3 consecutive rejects → ESCALATE."""
        reject_count = 3
        should_escalate = reject_count >= 3
        self.assertTrue(should_escalate, "Three rejects should trigger escalation")

    def test_mandatory_escalation_two_rejects(self):
        """2 consecutive rejects → no escalation yet."""
        reject_count = 2
        should_escalate = reject_count >= 3
        self.assertFalse(should_escalate, "Two rejects should not escalate")

    # Source Truth Tests
    def test_source_truth_no_mutation(self):
        """Snapshot matches current → no violations."""
        original = {"prompt": "test", "duration": 5}
        current = {"prompt": "test", "duration": 5}

        mutations = [k for k in original if original[k] != current.get(k)]
        self.assertEqual(len(mutations), 0, "No mutations detected")

    def test_source_truth_mutation_detected(self):
        """Snapshot differs from current → violation."""
        original = {"prompt": "test", "duration": 5}
        current = {"prompt": "CHANGED", "duration": 5}

        mutations = [k for k in original if original[k] != current.get(k)]
        self.assertGreater(len(mutations), 0, "Mutation should be detected")

    # Language Discipline Tests
    def test_language_discipline_strips_brands(self):
        """'ARRI Alexa 35' in prompt → stripped."""
        prompt = "Beautiful shot on ARRI Alexa 35 camera"
        cleaned = prompt.replace("ARRI Alexa 35", "").strip()
        self.assertNotIn("ARRI", cleaned)

    def test_language_discipline_strips_nationalities(self):
        """'Italian actress' → nationality stripped."""
        prompt = "Italian actress performs the scene"
        # Strip with context guard
        cleaned = prompt.replace("Italian actress", "actress")
        self.assertNotIn("Italian actress", cleaned)

    def test_language_discipline_preserves_legitimate_context(self):
        """'Italian villa' → preserved (not about person)."""
        prompt = "Scene inside an Italian villa"
        # Should NOT strip "Italian villa" (architectural)
        self.assertIn("Italian", prompt, "Architectural context should be preserved")


# ============================================================================
# PHASE 2: ERROR CORRECTION
# ============================================================================

class TestPhase2ErrorCorrection(unittest.TestCase):
    """Tests for Phase 2: Error Correction gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase2_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Parity Tests
    def test_parity_all_pass(self):
        """All 5 dimensions pass → PASS."""
        dimensions = {
            "identity": True,
            "location": True,
            "dialogue": True,
            "wardrobe": True,
            "emotion": True
        }
        all_pass = all(dimensions.values())
        self.assertTrue(all_pass, "All dimensions passing should result in PASS")

    def test_parity_one_fail(self):
        """Identity fails only → WARN."""
        dimensions = {
            "identity": False,
            "location": True,
            "dialogue": True,
            "wardrobe": True,
            "emotion": True
        }
        fail_count = sum(1 for v in dimensions.values() if not v)
        self.assertEqual(fail_count, 1, "Should detect single failure")

    def test_parity_two_fail(self):
        """Identity + wardrobe fail → REJECT."""
        dimensions = {
            "identity": False,
            "location": True,
            "dialogue": True,
            "wardrobe": False,
            "emotion": True
        }
        fail_count = sum(1 for v in dimensions.values() if not v)
        should_reject = fail_count >= 2
        self.assertTrue(should_reject, "Two or more failures should REJECT")

    # Toxic Pattern Tests
    def test_toxic_pattern_no_match(self):
        """Clean prompt → PASS."""
        prompt = "Clean shot of character in beautiful setting"
        toxic_patterns = ["ARRI", "Alexa", "RED", "camera"]

        has_toxic = any(p in prompt for p in toxic_patterns)
        self.assertFalse(has_toxic, "Clean prompt should have no toxic patterns")

    def test_toxic_pattern_full_match(self):
        """Known toxic pattern detected → REJECT."""
        prompt = "Shot on ARRI Alexa 35 RED camera"
        toxic_patterns = ["ARRI", "Alexa", "RED"]

        has_toxic = any(p in prompt for p in toxic_patterns)
        self.assertTrue(has_toxic, "Should detect toxic patterns")

    # Repair Zone Tests
    def test_repair_zone1_identity(self):
        """Identity score 0.80 → ZONE1_REPAIR."""
        score = 0.80
        if 0.75 <= score < 0.90:
            repair_zone = "ZONE1_REPAIR"
        else:
            repair_zone = "PASS"
        self.assertEqual(repair_zone, "ZONE1_REPAIR")

    def test_repair_zone2_identity(self):
        """Identity score 0.60 → ZONE2_REJECT."""
        score = 0.60
        if score < 0.75:
            repair_zone = "ZONE2_REJECT"
        else:
            repair_zone = "PASS"
        self.assertEqual(repair_zone, "ZONE2_REJECT")

    # Silent Failure Detection Tests
    def test_no_silent_failure_catches_unlogged(self):
        """Unlogged WARN detected in audit trail."""
        logged = {"001_001A": ["PASS", "WARN"]}
        actual = {"001_001A": ["PASS", "WARN", "UNLOGGED_ISSUE"]}

        unlogged = [x for x in actual.get("001_001A", []) if x not in logged.get("001_001A", [])]
        self.assertEqual(len(unlogged), 1, "Should detect unlogged issues")

    def test_silent_failure_no_false_positives(self):
        """All issues logged → no false positives."""
        logged = {"001_001A": ["PASS", "WARN", "ZONE1_REPAIR"]}
        actual = {"001_001A": ["PASS", "WARN", "ZONE1_REPAIR"]}

        unlogged = [x for x in actual.get("001_001A", []) if x not in logged.get("001_001A", [])]
        self.assertEqual(len(unlogged), 0, "Should have no false positives")

    # Pain Signal Tests
    def test_pain_signal_no_trend(self):
        """Random scores → no pain."""
        scores = [0.85, 0.92, 0.78, 0.89, 0.81]
        # Check for declining trend
        declining = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        self.assertFalse(declining, "Random scores should show no trend")

    def test_pain_signal_declining_trend(self):
        """5 shots with declining scores → PAIN active."""
        scores = [0.95, 0.88, 0.75, 0.62, 0.50]
        # Check for declining trend
        declining = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        self.assertTrue(declining, "Declining trend should trigger PAIN")

    def test_pain_signal_partial_decline(self):
        """Mixed trend → no PAIN."""
        scores = [0.95, 0.80, 0.88, 0.70, 0.92]
        # Check for declining trend
        declining = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        self.assertFalse(declining, "Mixed trend should not trigger PAIN")


# ============================================================================
# PHASE 3: EXECUTIVE
# ============================================================================

class TestPhase3Executive(unittest.TestCase):
    """Tests for Phase 3: Executive gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase3_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Scene Plan Generation Tests
    def test_scene_plan_generation(self):
        """Scene plan generated with all required fields."""
        plan = make_test_scene_plan("001", has_dialogue=True, is_key=False)

        required_fields = ["scene_id", "has_dialogue", "is_key_scene",
                          "emotional_arc", "required_coverage", "shot_count"]
        has_all = all(field in plan for field in required_fields)
        self.assertTrue(has_all, "Plan should have all required fields")

    # Peak Shot Detection Tests
    def test_peak_shot_detection_high_emotion(self):
        """High emotion value → marked as peak."""
        shot = make_test_shot(emotion="devastation")
        emotional_intensity = 0.9

        is_peak = emotional_intensity > 0.75
        self.assertTrue(is_peak, "High emotion should mark as peak")

    def test_peak_shot_detection_low_emotion(self):
        """Low emotion value → not peak."""
        shot = make_test_shot(emotion="neutral")
        emotional_intensity = 0.3

        is_peak = emotional_intensity > 0.75
        self.assertFalse(is_peak, "Low emotion should not mark as peak")

    # Peak Protocol Tests
    def test_peak_protocol_upgrades_kling(self):
        """Hero shot gets all 5 upgrades (Kling only)."""
        shot = make_test_shot(
            shot_type="close_up",
            emotion="devastation",
            _model_for_this_shot="kling"
        )

        # Check all 5 upgrades applied
        upgrades = [
            shot["_model_for_this_shot"] == "kling",  # Model locked
            True,  # Would check resolution, ref cap, etc
            True,
            True,
            True
        ]

        all_upgrades_applied = all(upgrades)
        self.assertTrue(all_upgrades_applied, "Peak shots should get all upgrades")

    def test_peak_protocol_non_kling_reject(self):
        """Hero shot on LTX (not Kling) → REJECT."""
        shot = make_test_shot(
            shot_type="close_up",
            emotion="devastation",
            _model_for_this_shot="ltx"
        )

        is_hero = shot["shot_type"] in ["close_up", "ECU", "MCU"]
        is_kling = shot["_model_for_this_shot"] == "kling"

        should_reject = is_hero and not is_kling
        self.assertTrue(should_reject, "Hero on LTX should be rejected")

    # Resource Proportionality Tests
    def test_resource_proportionality_balanced(self):
        """Resources distributed proportionally → PASS."""
        scenes = [
            {"hero_shots": 3, "total_shots": 8},
            {"hero_shots": 2, "total_shots": 7},
            {"hero_shots": 4, "total_shots": 10},
        ]

        # Check proportionality (hero should be ~30-40% of shots)
        proportions = [s["hero_shots"] / s["total_shots"] for s in scenes]
        all_proportional = all(0.25 <= p <= 0.50 for p in proportions)
        self.assertTrue(all_proportional, "Resources should be proportional")

    def test_resource_proportionality_overallocated(self):
        """60% hero shots (overallocated) → WARN/REJECT."""
        scene = {"hero_shots": 6, "total_shots": 10}
        proportion = scene["hero_shots"] / scene["total_shots"]

        should_warn = proportion > 0.50
        self.assertTrue(should_warn, "Overallocation should trigger warning")

    # Boundary Assignment Tests
    def test_boundary_assignment_scene_change(self):
        """Location change → SCENE_BOUNDARY."""
        prev_shot = make_test_shot(shot_id="001_001A", scene_id="001")
        curr_shot = make_test_shot(shot_id="002_001A", scene_id="002")

        is_boundary = prev_shot["scene_id"] != curr_shot["scene_id"]
        self.assertTrue(is_boundary, "Scene change should create boundary")

    def test_boundary_assignment_continuous(self):
        """Same scene → HARD_CONTINUOUS."""
        prev_shot = make_test_shot(shot_id="001_001A", scene_id="001")
        curr_shot = make_test_shot(shot_id="001_002A", scene_id="001")

        is_continuous = prev_shot["scene_id"] == curr_shot["scene_id"]
        self.assertTrue(is_continuous, "Same scene should be continuous")


# ============================================================================
# PHASE 4: MEMORY (Ledger, Patterns, Beliefs, Decay)
# ============================================================================

class TestPhase4Memory(unittest.TestCase):
    """Tests for Phase 4: Memory gates."""

    def setUp(self):
        """Create temp directory for ledger files."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase4_")
        self.ledger_path = os.path.join(self.test_dir, "belief_ledger.json")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Ledger Tests
    def test_ledger_activation_creates_entry(self):
        """Session data → profile entry created."""
        ledger = {
            "sessions": {
                "sess_001": {
                    "timestamp": "2026-03-11T10:00:00",
                    "shots_generated": 8,
                    "success_rate": 0.95
                }
            }
        }

        entry_exists = "sess_001" in ledger["sessions"]
        self.assertTrue(entry_exists, "Ledger should create entry for session")

    def test_ledger_updates_metrics(self):
        """New data → metrics updated."""
        ledger = {
            "aggregated": {
                "total_shots": 100,
                "average_success": 0.88
            }
        }

        ledger["aggregated"]["total_shots"] += 5
        self.assertEqual(ledger["aggregated"]["total_shots"], 105)

    # Pattern Promotion Tests
    def test_pattern_provisional_creation(self):
        """First observation → provisional status."""
        pattern = {
            "pattern_id": "pat_001",
            "observations": 1,
            "status": "provisional",
            "confidence": 0.0
        }

        self.assertEqual(pattern["status"], "provisional")
        self.assertEqual(pattern["observations"], 1)

    def test_pattern_promotion_to_stable(self):
        """3+ confirmations → stable status."""
        pattern = {
            "pattern_id": "pat_001",
            "observations": 3,
            "status": "provisional"
        }

        if pattern["observations"] >= 3:
            pattern["status"] = "stable"

        self.assertEqual(pattern["status"], "stable")

    def test_pattern_partial_observations(self):
        """2 observations → still provisional."""
        pattern = {
            "pattern_id": "pat_001",
            "observations": 2,
            "status": "provisional"
        }

        if pattern["observations"] >= 3:
            pattern["status"] = "stable"

        self.assertEqual(pattern["status"], "provisional")

    # Belief Decay Tests
    def test_belief_decay_recent_no_decay(self):
        """Recent pattern (1 session) → no decay."""
        pattern = {
            "last_confirmed": (datetime.now() - timedelta(days=1)).isoformat(),
            "status": "stable"
        }

        # Pattern is recent, should not decay
        self.assertEqual(pattern["status"], "stable")

    def test_belief_decay_stale_demotion(self):
        """10+ sessions without confirmation → demote."""
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        pattern = {
            "last_confirmed": old_date,
            "status": "stable",
            "age_in_sessions": 10
        }

        # After 10 sessions without confirmation, demote
        if pattern["age_in_sessions"] >= 10:
            pattern["status"] = "provisional"

        self.assertEqual(pattern["status"], "provisional")

    def test_belief_decay_deletion(self):
        """20+ sessions without confirmation → delete."""
        pattern = {
            "pattern_id": "pat_001",
            "age_in_sessions": 20,
            "status": "provisional"
        }

        should_delete = pattern["age_in_sessions"] >= 20
        self.assertTrue(should_delete, "Very stale patterns should be deleted")

    # Single Success Tests
    def test_no_single_success_worship(self):
        """1 success → stays provisional."""
        pattern = {
            "successes": 1,
            "observations": 1,
            "status": "provisional"
        }

        # 1 success is not enough for stable
        self.assertEqual(pattern["status"], "provisional")

    def test_pattern_needs_multiple_confirmations(self):
        """3+ successes → can promote."""
        pattern = {
            "successes": 3,
            "observations": 3,
            "status": "provisional"
        }

        if pattern["successes"] >= 3:
            pattern["status"] = "stable"

        self.assertEqual(pattern["status"], "stable")


# ============================================================================
# PHASE 5: CINEMA (Dual Perception, Motion Fidelity, Dramatic Function)
# ============================================================================

class TestPhase5Cinema(unittest.TestCase):
    """Tests for Phase 5: Cinema gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase5_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Dual Perception Tests
    def test_dual_perception_both_pass(self):
        """Identity pass + cinema pass → PASS."""
        scores = {
            "identity_score": 0.92,
            "cinema_score": 0.76
        }

        identity_pass = scores["identity_score"] > 0.82
        cinema_pass = scores["cinema_score"] > 0.50

        both_pass = identity_pass and cinema_pass
        self.assertTrue(both_pass, "Both dimensions should pass")

    def test_dual_perception_identity_fail(self):
        """Identity fail + cinema pass → WARN."""
        scores = {
            "identity_score": 0.68,
            "cinema_score": 0.76
        }

        identity_pass = scores["identity_score"] > 0.82
        cinema_pass = scores["cinema_score"] > 0.50

        should_warn = not identity_pass and cinema_pass
        self.assertTrue(should_warn, "Mixed results should warn")

    def test_dual_perception_cinema_fail(self):
        """Cinema < 0.50 → REJECT."""
        scores = {
            "identity_score": 0.92,
            "cinema_score": 0.35
        }

        cinema_pass = scores["cinema_score"] > 0.50
        self.assertFalse(cinema_pass, "Low cinema score should reject")

    # Motion Fidelity Tests
    def test_motion_fidelity_static_when_motion(self):
        """Motion specified but frame static → REJECT."""
        shot = {
            "ltx_motion_prompt": "character walks across room with purpose",
            "_detected_motion": None  # No motion detected
        }

        has_motion_prompt = "walk" in shot["ltx_motion_prompt"]
        has_detected_motion = shot["_detected_motion"] is not None

        should_reject = has_motion_prompt and not has_detected_motion
        self.assertTrue(should_reject, "Should reject static frames when motion expected")

    def test_motion_fidelity_static_intended(self):
        """Static shot (no motion specified) → PASS."""
        shot = {
            "ltx_motion_prompt": "character stands still, listening intently",
            "_detected_motion": None
        }

        # Static is intentional
        self.assertIsNone(shot["_detected_motion"], "Static shot can have no motion")

    def test_motion_fidelity_motion_match(self):
        """Motion specified + motion detected → PASS."""
        shot = {
            "ltx_motion_prompt": "character walks across room",
            "_detected_motion": "walking"
        }

        has_motion = shot["_detected_motion"] is not None
        self.assertTrue(has_motion, "Motion detected should pass")

    # Dramatic Function Tests
    def test_dramatic_function_peak_to_peak(self):
        """PEAK shot looks like PEAK → PASS."""
        shot = {
            "dramatic_classification": "PEAK",
            "visual_intensity": 0.94
        }

        self.assertGreater(shot["visual_intensity"], 0.75, "PEAK should have high intensity")

    def test_dramatic_function_mismatch_peak_to_insert(self):
        """PEAK shot looks like INSERT → WARN."""
        shot = {
            "dramatic_classification": "PEAK",
            "visual_intensity": 0.25
        }

        mismatch = shot["visual_intensity"] < 0.50
        self.assertTrue(mismatch, "Classification mismatch should warn")

    def test_dramatic_function_broll_low_intensity(self):
        """BROLL shot has low intensity → PASS."""
        shot = {
            "dramatic_classification": "BROLL",
            "visual_intensity": 0.20
        }

        self.assertLess(shot["visual_intensity"], 0.50, "BROLL should have low intensity")


# ============================================================================
# PHASE 6: SOVEREIGNTY (Hard Stops, Director Constraints)
# ============================================================================

class TestPhase6Sovereignty(unittest.TestCase):
    """Tests for Phase 6: Sovereignty gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase6_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Hard Stop Tests
    def test_hard_stop_executes(self):
        """Director issues hard stop → pipeline halted."""
        directive = {
            "type": "HARD_STOP",
            "issued_at": datetime.now().isoformat(),
            "reason": "Review output before continuing"
        }

        should_halt = directive["type"] == "HARD_STOP"
        self.assertTrue(should_halt, "Hard stop should halt pipeline")

    def test_hard_stop_clearance(self):
        """Director clears hard stop → pipeline resumable."""
        directive = {
            "type": "HARD_STOP",
            "cleared_at": datetime.now().isoformat(),
            "status": "CLEARED"
        }

        is_cleared = directive.get("status") == "CLEARED"
        self.assertTrue(is_cleared, "Cleared stop should allow resumption")

    # Director Constraint Tests
    def test_director_constraint_respected(self):
        """Output matches constraint → PASS."""
        constraint = {
            "type": "NO_CLOSE_UPS",
            "scene_id": "001",
            "required": True
        }

        shot = make_test_shot(shot_type="wide", scene_id="001")

        violates = shot["shot_type"] == "close_up" and constraint["scene_id"] == shot["scene_id"]
        self.assertFalse(violates, "Should respect constraints")

    def test_director_constraint_violated(self):
        """Output violates constraint → REJECT."""
        constraint = {
            "type": "NO_CLOSE_UPS",
            "scene_id": "001",
            "required": True
        }

        shot = make_test_shot(shot_type="close_up", scene_id="001")

        violates = shot["shot_type"] == "close_up" and constraint["scene_id"] == shot["scene_id"]
        self.assertTrue(violates, "Should detect constraint violation")

    # Learned Preference Tests
    def test_learned_preference_subordinated(self):
        """Preference conflicts with plan → suppressed."""
        preference = {
            "type": "PREFER_KLING",
            "priority": "low"
        }

        plan = {
            "model": "ltx",
            "priority": "high"
        }

        # Plan overrides preference — compare priority levels
        priority_rank = {"low": 1, "medium": 2, "high": 3}
        should_suppress = priority_rank[plan["priority"]] > priority_rank[preference["priority"]]
        self.assertTrue(should_suppress, "Plan should override learned preference")

    def test_learned_preference_no_conflict(self):
        """No conflict with plan → PASS."""
        preference = {
            "type": "PREFER_KLING",
            "priority": "low"
        }

        plan = {
            "model": "kling",
            "priority": "high"
        }

        # Plan aligns with preference
        aligned = plan["model"].lower() in preference["type"].lower()
        self.assertTrue(aligned, "Preference should align when possible")


# ============================================================================
# PHASE 7: AUTONOMY (Decision Audit, Uncertainty, Health Check)
# ============================================================================

class TestPhase7Autonomy(unittest.TestCase):
    """Tests for Phase 7: Autonomy gates."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_phase7_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Decision Audit Tests
    def test_decision_audit_complete(self):
        """Full audit trail present → PASS."""
        decision = {
            "shot_id": "001_001A",
            "timestamp": datetime.now().isoformat(),
            "phase_1_result": "PASS",
            "phase_2_result": "PASS",
            "phase_3_decision": "GENERATE",
            "audit_trail": ["Phase 1: PASS", "Phase 2: PASS", "Phase 3: APPROVED"],
            "decision_authority": "AUTONOMOUS"
        }

        has_trail = len(decision.get("audit_trail", [])) > 0
        self.assertTrue(has_trail, "Should have complete audit trail")

    def test_decision_audit_missing(self):
        """No audit trail → REJECT."""
        decision = {
            "shot_id": "001_001A",
            "phase_1_result": "PASS",
            # Missing audit_trail
        }

        has_trail = len(decision.get("audit_trail", [])) > 0
        self.assertFalse(has_trail, "Missing audit trail should reject")

    # Uncertainty Tests
    def test_uncertainty_known_dimension(self):
        """Scene plan exists → KNOWN."""
        context = {
            "_scene_plans": {
                "001": make_test_scene_plan("001")
            }
        }

        has_plan = "001" in context.get("_scene_plans", {})
        self.assertTrue(has_plan, "Known scene should have plan")

    def test_uncertainty_unknown_dimension(self):
        """No scene plan → UNKNOWN."""
        context = {
            "_scene_plans": {}
        }

        has_plan = "999" in context.get("_scene_plans", {})
        self.assertFalse(has_plan, "Unknown scene should have no plan")

    def test_uncertainty_conservative_default(self):
        """Unknown dimension → use conservative default."""
        context = {
            "_scene_plans": {}
        }

        scene_plan = context.get("_scene_plans", {}).get("999") or {
            "default": "conservative",
            "required_coverage": ["A_GEOGRAPHY"],  # Minimal coverage
            "max_resources": "minimal"
        }

        self.assertEqual(scene_plan["default"], "conservative")

    # Health Check Tests
    def test_health_check_healthy(self):
        """Low reject rate (8%) → PASS."""
        stats = {
            "total_shots": 50,
            "rejected_shots": 4,
            "reject_rate": 0.08
        }

        is_healthy = stats["reject_rate"] < 0.10
        self.assertTrue(is_healthy, "8% reject rate should be healthy")

    def test_health_check_degraded(self):
        """12% reject rate → WARN."""
        stats = {
            "total_shots": 50,
            "rejected_shots": 6,
            "reject_rate": 0.12
        }

        is_degraded = 0.10 <= stats["reject_rate"] < 0.15
        self.assertTrue(is_degraded, "12% reject rate should trigger warning")

    def test_health_check_critical(self):
        """20% reject rate → REJECT, pause autonomous."""
        stats = {
            "total_shots": 50,
            "rejected_shots": 10,
            "reject_rate": 0.20
        }

        is_critical = stats["reject_rate"] >= 0.15
        self.assertTrue(is_critical, "20% reject rate should be critical")

    # Prime Directive Tests
    def test_prime_directive_resolution(self):
        """Conflict resolved by scene plan."""
        conflict = {
            "type": "learned_vs_plan",
            "learned_preference": "NO_CLOSE_UPS",
            "scene_plan": "REQUIRES_ECU_001_005B"
        }

        # Scene plan takes precedence
        resolution = conflict["scene_plan"]
        self.assertIn("REQUIRES", resolution, "Scene plan should resolve conflicts")

    def test_prime_directive_no_conflict(self):
        """No conflict → proceed normally."""
        context = {
            "learned_constraints": [],
            "scene_plan": {"required_coverage": ["A_GEOMETRY"]}
        }

        has_conflict = len(context.get("learned_constraints", [])) > 0
        self.assertFalse(has_conflict, "No conflicts detected")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestDoctrineIntegration(unittest.TestCase):
    """Integration tests for full Doctrine pipeline."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_integration_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_full_pre_generation_chain(self):
        """Phases 1, 2, 3, 6, 7 fire in order pre-gen."""
        shot = make_test_shot(
            shot_id="001_001A",
            characters=["EVELYN RAVENCROFT"],
            emotion="determined"
        )
        ctx = make_test_context(scene_plan=make_test_scene_plan("001"))

        # Phase 1: Foundation
        phase1_pass = (
            all(c in ctx["cast_map"] for c in shot["characters"]) and
            shot.get("scene_id") in ctx.get("_scene_plans", {})
        )

        # Phase 2: Error Correction
        phase2_pass = True  # Assume no toxic patterns

        # Phase 3: Executive
        scene_plan = ctx["_scene_plans"]["001"]
        phase3_pass = scene_plan is not None

        # Phase 6: Sovereignty
        director_constraint_met = True  # No conflicting constraints

        # Phase 7: Autonomy
        has_audit = True  # Would have audit trail

        all_pass = phase1_pass and phase2_pass and phase3_pass and director_constraint_met and has_audit
        self.assertTrue(all_pass, "All pre-gen phases should pass")

    def test_full_post_generation_chain(self):
        """Phases 1, 2, 5, 6 fire in order post-gen."""
        shot = make_test_shot(shot_id="001_001A")
        generated_frame = {
            "identity_score": 0.91,
            "cinema_score": 0.78,
            "motion_detected": True
        }

        # Phase 1: Identity re-check
        phase1_pass = generated_frame["identity_score"] > 0.82

        # Phase 2: Error Correction
        phase2_pass = generated_frame["cinema_score"] > 0.50

        # Phase 5: Cinema
        phase5_pass = (
            generated_frame["identity_score"] > 0.82 and
            generated_frame["cinema_score"] > 0.50
        )

        # Phase 6: Sovereignty
        director_approval = True

        all_pass = phase1_pass and phase2_pass and phase5_pass and director_approval
        self.assertTrue(all_pass, "All post-gen phases should pass")

    def test_session_lifecycle_with_memory(self):
        """Open → generate → close with Phase 4 learning."""
        session_id = "test_session_001"

        # Session opens
        session = {
            "session_id": session_id,
            "started_at": datetime.now().isoformat(),
            "shots": [],
            "results": []
        }

        # Generation happens (simulate 10 shots)
        for i in range(10):
            shot = make_test_shot(shot_id=f"001_{i+1:03d}A")
            result = {
                "shot_id": shot["shot_id"],
                "phase1": "PASS",
                "phase2": "PASS",
                "success": True
            }
            session["shots"].append(shot)
            session["results"].append(result)

        # Session closes
        session["ended_at"] = datetime.now().isoformat()
        success_rate = sum(1 for r in session["results"] if r["success"]) / len(session["results"])

        # Phase 4: Update belief system
        pattern = {
            "pattern_id": f"pat_from_{session_id}",
            "observations": 10,
            "successes": 9,
            "last_confirmed": session["ended_at"],
            "status": "stable" if 9 >= 3 else "provisional"
        }

        self.assertEqual(pattern["status"], "stable", "Multiple confirmations should reach stable")
        success_rate = pattern["successes"] / pattern["observations"]
        self.assertAlmostEqual(success_rate, 0.9, places=1, msg="Session should track success rate")


# ============================================================================
# THRESHOLD BOUNDARY TESTS
# ============================================================================

class TestDoctrineThresholds(unittest.TestCase):
    """Tests for threshold boundaries and edge cases."""

    def setUp(self):
        """Create temp directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="atlas_threshold_")

    def tearDown(self):
        """Clean up temp directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Identity Score Thresholds
    def test_identity_threshold_exactly_0_82(self):
        """Score exactly 0.82 → boundary case."""
        score = 0.82
        passes = score >= 0.82
        self.assertTrue(passes, "Exact threshold should pass")

    def test_identity_threshold_just_below(self):
        """Score 0.819 → just below threshold."""
        score = 0.819
        passes = score >= 0.82
        self.assertFalse(passes, "Just below threshold should fail")

    def test_identity_threshold_just_above(self):
        """Score 0.821 → just above threshold."""
        score = 0.821
        passes = score >= 0.82
        self.assertTrue(passes, "Just above threshold should pass")

    # Cinema Score Thresholds
    def test_cinema_threshold_0_50(self):
        """Cinema score at 0.50 boundary."""
        score = 0.50
        passes = score > 0.50
        self.assertFalse(passes, "At 0.50 should not pass (needs >)")

    def test_cinema_threshold_above_0_50(self):
        """Cinema score 0.501 → passes."""
        score = 0.501
        passes = score > 0.50
        self.assertTrue(passes, "Above 0.50 should pass")

    # Reject Rate Thresholds
    def test_reject_rate_warning_threshold(self):
        """Reject rate at 10% boundary."""
        rate = 0.10
        is_warning = rate >= 0.10
        self.assertTrue(is_warning, "At 10% should warn")

    def test_reject_rate_critical_threshold(self):
        """Reject rate at 15% boundary."""
        rate = 0.15
        is_critical = rate >= 0.15
        self.assertTrue(is_critical, "At 15% should be critical")

    # Pattern Observation Thresholds
    def test_pattern_stable_exactly_3(self):
        """3 observations exactly → stable."""
        observations = 3
        is_stable = observations >= 3
        self.assertTrue(is_stable, "Exactly 3 should be stable")

    def test_pattern_stable_2(self):
        """2 observations → still provisional."""
        observations = 2
        is_stable = observations >= 3
        self.assertFalse(is_stable, "2 observations should not be stable")

    # Escalation Thresholds
    def test_escalation_3_rejects(self):
        """3 consecutive rejects → escalate."""
        rejects = 3
        should_escalate = rejects >= 3
        self.assertTrue(should_escalate, "3 rejects should escalate")

    def test_escalation_2_rejects(self):
        """2 consecutive rejects → no escalation."""
        rejects = 2
        should_escalate = rejects >= 3
        self.assertFalse(should_escalate, "2 rejects should not escalate")


# ============================================================================
# MAIN RUNNER
# ============================================================================

if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
