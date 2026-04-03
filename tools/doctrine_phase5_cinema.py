"""
ATLAS Doctrine Phase 5 — Cinematographic Perception
The system must see film, not just faces.

Dual Perception Gate (identity + shot grammar), Motion Fidelity Check, Dramatic Function Scoring.

V24.2 | 2026-03-11
Author: ATLAS Production System
"""

import re
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from tools.doctrine_engine import (
    DoctrineGate,
    GateResult,
    LedgerEntry,
    RunLedger,
    CINEMA_PASS_THRESHOLD,
    CINEMA_REJECT_THRESHOLD,
)


class DramaticFunction(Enum):
    """Dramatic function tags for scenes."""
    ESTABLISH = "ESTABLISH"
    BUILD = "BUILD"
    PEAK = "PEAK"
    RELEASE = "RELEASE"
    TRANSITION = "TRANSITION"
    REVEAL = "REVEAL"
    INSERT = "INSERT"


class ShotSize(Enum):
    """Standard shot size classifications."""
    WIDE = "wide"
    ESTABLISHING = "establishing"
    LONG = "long"
    MASTER = "master"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    MCU = "MCU"
    ECU = "ECU"
    EXTREME_CLOSE_UP = "extreme_close_up"


class CameraAngle(Enum):
    """Standard camera angle classifications."""
    EYE_LEVEL = "eye_level"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    DUTCH = "dutch"
    BIRD_EYE = "bird_eye"
    WORM_EYE = "worm_eye"


@dataclass
class CinemaScore:
    """Per-dimension cinema score."""
    dimension: str
    score: float  # 0.0-1.0
    confidence: float  # 0.0-1.0 confidence in the score
    keywords_matched: List[str]
    reasoning: str


@dataclass
class MotionAnalysis:
    """Motion analysis results."""
    motion_detected: bool
    motion_magnitude: float  # 0.0-1.0
    motion_direction: Optional[str]
    motion_type_match: bool
    detected_type: Optional[str]
    expected_type: Optional[str]


class CinemaScoreCalculator:
    """Calculates cinematographic quality scores from visual analysis."""

    # Shot size keywords → classifications
    SHOT_SIZE_KEYWORDS = {
        "wide shot": ShotSize.WIDE,
        "wide": ShotSize.WIDE,
        "establishing shot": ShotSize.ESTABLISHING,
        "establishing": ShotSize.ESTABLISHING,
        "long shot": ShotSize.LONG,
        "master shot": ShotSize.MASTER,
        "master": ShotSize.MASTER,
        "medium shot": ShotSize.MEDIUM,
        "medium": ShotSize.MEDIUM,
        "medium close-up": ShotSize.MEDIUM_CLOSE,
        "close-up": ShotSize.CLOSE_UP,
        "close up": ShotSize.CLOSE_UP,
        "MCU": ShotSize.MCU,
        "medium close-up": ShotSize.MCU,
        "ECU": ShotSize.ECU,
        "extreme close-up": ShotSize.ECU,
    }

    # Camera angle keywords
    ANGLE_KEYWORDS = {
        "eye level": CameraAngle.EYE_LEVEL,
        "low angle": CameraAngle.LOW_ANGLE,
        "low-angle": CameraAngle.LOW_ANGLE,
        "high angle": CameraAngle.HIGH_ANGLE,
        "high-angle": CameraAngle.HIGH_ANGLE,
        "dutch": CameraAngle.DUTCH,
        "dutch angle": CameraAngle.DUTCH,
        "bird's eye": CameraAngle.BIRD_EYE,
        "bird eye": CameraAngle.BIRD_EYE,
        "overhead": CameraAngle.BIRD_EYE,
        "worm's eye": CameraAngle.WORM_EYE,
        "worm eye": CameraAngle.WORM_EYE,
    }

    # Composition keywords
    COMPOSITION_KEYWORDS = [
        "rule of thirds",
        "centered",
        "leading lines",
        "depth",
        "layering",
        "foreground",
        "background",
        "negative space",
        "symmetrical",
        "asymmetrical",
    ]

    # Lighting keywords
    LIGHTING_KEYWORDS = {
        "high key": "high_key",
        "low key": "low_key",
        "silhouette": "silhouette",
        "backlighting": "backlighting",
        "side lighting": "side_lighting",
        "natural lighting": "natural",
        "dramatic lighting": "dramatic",
        "soft lighting": "soft",
        "hard lighting": "hard",
    }

    # Movement keywords
    MOVEMENT_KEYWORDS = {
        "dolly": "dolly",
        "push": "dolly",
        "pull": "dolly",
        "pan": "pan",
        "tilt": "tilt",
        "crane": "crane",
        "handheld": "handheld",
        "tracking": "tracking",
        "zoom": "zoom",
        "static": "static",
    }

    def score_shot_grammar(self, frame_analysis: Dict[str, Any]) -> Dict[str, CinemaScore]:
        """Score all 8 ShotBench dimensions from frame analysis.

        Args:
            frame_analysis: Output from vision service (captions, descriptions, etc.)

        Returns:
            Dict of dimension_name -> CinemaScore for all 8 dimensions
        """
        caption = frame_analysis.get("caption", "") or ""
        detection_text = frame_analysis.get("detection_text", "") or ""
        analysis_text = (caption + " " + detection_text).lower()

        scores = {}

        # Dimension 1: Shot Size
        scores["shot_size"] = self._score_shot_size(analysis_text)

        # Dimension 2: Camera Angle
        scores["camera_angle"] = self._score_camera_angle(analysis_text)

        # Dimension 3: Framing Composition
        scores["framing_composition"] = self._score_composition(analysis_text)

        # Dimension 4: Lens Behavior
        scores["lens_behavior"] = self._score_lens_behavior(analysis_text)

        # Dimension 5: Lighting Condition
        scores["lighting_condition"] = self._score_lighting_condition(analysis_text)

        # Dimension 6: Lighting Type
        scores["lighting_type"] = self._score_lighting_type(analysis_text)

        # Dimension 7: Camera Movement
        scores["camera_movement"] = self._score_movement(analysis_text)

        # Dimension 8: Composition Rule
        scores["composition_rule"] = self._score_composition_rule(analysis_text)

        return scores

    def _score_shot_size(self, text: str) -> CinemaScore:
        """Score shot size detection."""
        matched = []
        for keyword, size in self.SHOT_SIZE_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)

        confidence = min(len(matched) / 2.0, 1.0)
        score = 1.0 if matched else 0.3
        return CinemaScore(
            dimension="shot_size",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Matched {len(matched)} shot size keywords" if matched else "No explicit shot size detected",
        )

    def _score_camera_angle(self, text: str) -> CinemaScore:
        """Score camera angle detection."""
        matched = []
        for keyword, angle in self.ANGLE_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)

        confidence = min(len(matched) / 1.5, 1.0)
        score = 1.0 if matched else 0.4
        return CinemaScore(
            dimension="camera_angle",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Matched {len(matched)} angle keywords" if matched else "Assumed eye-level default",
        )

    def _score_composition(self, text: str) -> CinemaScore:
        """Score composition technique detection."""
        matched = []
        for keyword in self.COMPOSITION_KEYWORDS:
            if keyword in text:
                matched.append(keyword)

        score = min(len(matched) * 0.15 + 0.3, 1.0)
        confidence = min(len(matched) / 3.0, 1.0)
        return CinemaScore(
            dimension="framing_composition",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Detected {len(matched)} composition techniques",
        )

    def _score_lens_behavior(self, text: str) -> CinemaScore:
        """Score lens behavior (focus, depth of field, etc.)."""
        dof_markers = ["depth of field", "shallow focus", "focused", "sharp", "blur", "bokeh"]
        matched = [m for m in dof_markers if m in text]

        score = min(len(matched) * 0.2 + 0.4, 1.0)
        confidence = min(len(matched) / 2.0, 1.0)
        return CinemaScore(
            dimension="lens_behavior",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Depth of field characteristics detected: {len(matched)} markers",
        )

    def _score_lighting_condition(self, text: str) -> CinemaScore:
        """Score overall lighting condition (bright, dark, etc.)."""
        bright_markers = ["bright", "well-lit", "illuminated", "glowing"]
        dark_markers = ["dark", "dimly lit", "shadowy", "low light"]

        bright_count = sum(1 for m in bright_markers if m in text)
        dark_count = sum(1 for m in dark_markers if m in text)
        matched = ["bright"] * bright_count + ["dark"] * dark_count

        if bright_count > dark_count:
            score = 0.9
            reason = "Well-lit scene"
        elif dark_count > bright_count:
            score = 0.8
            reason = "Low-light scene"
        else:
            score = 0.7
            reason = "Neutral lighting"

        return CinemaScore(
            dimension="lighting_condition",
            score=score,
            confidence=0.8,
            keywords_matched=matched,
            reasoning=reason,
        )

    def _score_lighting_type(self, text: str) -> CinemaScore:
        """Score specific lighting technique."""
        matched = []
        for keyword, lighting_type in self.LIGHTING_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)

        score = min(len(matched) * 0.2 + 0.3, 1.0) if matched else 0.5
        confidence = min(len(matched) / 2.0, 1.0)
        return CinemaScore(
            dimension="lighting_type",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Detected {len(matched)} lighting techniques" if matched else "Neutral lighting approach",
        )

    def _score_movement(self, text: str) -> CinemaScore:
        """Score camera movement detection."""
        matched = []
        for keyword, motion in self.MOVEMENT_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)

        score = min(len(matched) * 0.25 + 0.2, 1.0) if matched else 0.3
        confidence = min(len(matched) / 2.0, 1.0)
        return CinemaScore(
            dimension="camera_movement",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Detected {len(matched)} movement types" if matched else "No explicit movement detected",
        )

    def _score_composition_rule(self, text: str) -> CinemaScore:
        """Score advanced composition rules (symmetry, balance, etc.)."""
        rule_markers = [
            "rule of thirds",
            "golden ratio",
            "symmetrical",
            "balanced",
            "diagonal",
            "leading",
        ]
        matched = [m for m in rule_markers if m in text]

        score = min(len(matched) * 0.2 + 0.4, 1.0)
        confidence = min(len(matched) / 2.0, 1.0)
        return CinemaScore(
            dimension="composition_rule",
            score=score,
            confidence=confidence,
            keywords_matched=matched,
            reasoning=f"Advanced composition rules detected: {len(matched)} markers",
        )

    def compare_to_intent(
        self,
        scores: Dict[str, CinemaScore],
        intended_shot_class: Optional[str],
        intended_function: Optional[str],
    ) -> float:
        """Compare calculated scores to intended shot class/function.

        Args:
            scores: Dict of dimension -> CinemaScore
            intended_shot_class: Expected shot size (e.g., "close_up", "wide")
            intended_function: Expected dramatic function (e.g., "PEAK", "ESTABLISH")

        Returns:
            Match score 0.0-1.0
        """
        if not intended_shot_class and not intended_function:
            return 0.5  # Neutral if no intent specified

        matches = 0
        total = 0

        # Check shot size match
        if intended_shot_class:
            total += 1
            actual_size = scores.get("shot_size")
            if actual_size and actual_size.score > 0.7:
                matches += 0.5

        # Check movement match
        if intended_function and intended_function in ["TRANSITION", "REVEAL"]:
            total += 1
            actual_movement = scores.get("camera_movement")
            if actual_movement and actual_movement.score > 0.5:
                matches += 0.5

        if total == 0:
            return 0.5

        return min(matches / total, 1.0)

    def get_function_grammar_map(self, function_tag: str) -> Dict[str, Any]:
        """Get expected grammar map for a dramatic function.

        Args:
            function_tag: Dramatic function (ESTABLISH, BUILD, PEAK, etc.)

        Returns:
            Dict with expected dimension values and thresholds
        """
        maps = {
            "ESTABLISH": {
                "shot_size": ["wide", "establishing", "long", "master"],
                "lighting_type": ["natural"],
                "camera_movement": "static",
                "composition_rule": "balanced",
                "expected_average": 0.72,
            },
            "BUILD": {
                "shot_size": ["medium", "medium_close"],
                "camera_movement": ["pan", "subtle_tracking"],
                "lighting_type": ["dramatic"],
                "composition_rule": "tension",
                "expected_average": 0.75,
            },
            "PEAK": {
                "shot_size": ["close_up", "MCU", "ECU"],
                "lighting_type": ["dramatic", "silhouette"],
                "framing_composition": "tight",
                "composition_rule": "focused",
                "expected_average": 0.85,
            },
            "RELEASE": {
                "shot_size": ["wide", "medium"],
                "lighting_type": ["soft"],
                "camera_movement": "slow",
                "composition_rule": "open",
                "expected_average": 0.70,
            },
            "TRANSITION": {
                "camera_movement": ["pan", "dolly", "tracking"],
                "shot_size": "varied",
                "composition_rule": "flowing",
                "expected_average": 0.68,
            },
            "REVEAL": {
                "composition_rule": ["foreground_background", "layered"],
                "lighting_type": ["dramatic"],
                "framing_composition": "complex",
                "expected_average": 0.78,
            },
            "INSERT": {
                "shot_size": ["ECU", "extreme_close_up"],
                "framing_composition": "detailed",
                "lighting_type": "focused",
                "expected_average": 0.75,
            },
        }
        return maps.get(function_tag, {})


class DualPerceptionGate(DoctrineGate):
    """Gate 1: Dual Perception — Identity + Shot Grammar independent scoring."""

    def __init__(self, project_path: str):
        """Initialize Dual Perception Gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "post_generation", "CINEMA_LAW_01")

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run dual perception gate.

        Scores two independent paths:
        - Vision Pass A: Identity metrics (face, hair, wardrobe, silhouette)
        - Vision Pass B: Shot grammar (8 ShotBench dimensions)

        Args:
            shot: Shot plan dictionary
            context: Optional context with vision scores

        Returns:
            GateResult verdict
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")

        # Vision Pass A: Identity
        identity_scores = context.get("identity_scores", {})
        identity_verdict = self._run_identity_pass(identity_scores)

        # Vision Pass B: Shot Grammar
        cinema_scores = context.get("cinema_scores", {})
        cinema_verdict = self._run_cinema_pass(cinema_scores)

        # Combined logic
        if identity_verdict == GateResult.PASS and cinema_verdict == GateResult.PASS:
            final_result = GateResult.PASS
            reason = "DUAL_PERCEPTION_PASS"
        elif cinema_verdict == GateResult.REJECT:
            final_result = GateResult.REJECT
            reason = "CINEMA_GRAMMAR_REJECT"
        elif cinema_verdict == GateResult.WARN or identity_verdict == GateResult.WARN:
            final_result = GateResult.WARN
            reason = "PERCEPTION_WARNING"
        else:
            final_result = GateResult.PASS
            reason = "DUAL_PERCEPTION_ACCEPTABLE"

        # Compute deviation score
        deviation_score = self._compute_deviation_score(identity_verdict, cinema_verdict)

        # Log to ledger
        prompt_hash = self._compute_prompt_hash(shot.get("nano_prompt", ""))
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=final_result.value,
            deviation_score=deviation_score,
            deviation_type="cinema",
            correction_applied=False,
            model_used="dual_perception",
            prompt_hash=prompt_hash,
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=reason,
            extra_data={
                "identity_verdict": identity_verdict.value,
                "cinema_verdict": cinema_verdict.value,
                "identity_pass_score": identity_scores.get("overall", 0.0),
                "cinema_pass_score": cinema_scores.get("overall_average", 0.0),
            },
        )
        self._write_ledger(entry)

        return final_result

    def _run_identity_pass(self, identity_scores: Dict[str, float]) -> GateResult:
        """Run identity-only perception pass.

        Args:
            identity_scores: Dict with face_structure, hair_match, wardrobe_match, silhouette_match

        Returns:
            GateResult
        """
        if not identity_scores:
            return GateResult.WARN  # No data available

        # Weighted average: face=0.5, hair=0.2, wardrobe=0.2, silhouette=0.1
        face = identity_scores.get("face_structure", 0.0)
        hair = identity_scores.get("hair_match", 0.0)
        wardrobe = identity_scores.get("wardrobe_match", 0.0)
        silhouette = identity_scores.get("silhouette_match", 0.0)

        overall = (face * 0.5 + hair * 0.2 + wardrobe * 0.2 + silhouette * 0.1)

        if overall >= 0.90:
            return GateResult.PASS
        elif overall >= 0.75:
            return GateResult.WARN
        else:
            return GateResult.REJECT

    def _run_cinema_pass(self, cinema_scores: Dict[str, Any]) -> GateResult:
        """Run shot grammar perception pass using 8 ShotBench dimensions.

        Args:
            cinema_scores: Dict with dimension scores (CinemaScore objects or floats)

        Returns:
            GateResult
        """
        if not cinema_scores:
            return GateResult.WARN  # No data available

        # Extract numerical scores from CinemaScore objects or dicts
        dimension_scores = []
        low_dimensions = 0

        for dimension, value in cinema_scores.items():
            if isinstance(value, float):
                score = value
            elif isinstance(value, dict):
                score = value.get("score", 0.0)
            else:
                score = getattr(value, "score", 0.0)

            dimension_scores.append(score)
            if score < 0.50:
                low_dimensions += 1

        if not dimension_scores:
            return GateResult.WARN

        overall = sum(dimension_scores) / len(dimension_scores)

        # Verdict logic
        if overall < CINEMA_REJECT_THRESHOLD:
            return GateResult.REJECT
        elif overall < CINEMA_PASS_THRESHOLD or low_dimensions >= 2:
            return GateResult.WARN
        else:
            return GateResult.PASS

    def _compute_deviation_score(self, identity_verdict: GateResult, cinema_verdict: GateResult) -> float:
        """Compute overall deviation score from both verdicts.

        Args:
            identity_verdict: Result from identity pass
            cinema_verdict: Result from cinema pass

        Returns:
            Deviation score 0.0-1.0 (0=ideal, 1=severe)
        """
        # Map verdicts to deviation scores
        verdict_score_map = {
            GateResult.PASS: 0.0,
            GateResult.WARN: 0.4,
            GateResult.REJECT: 1.0,
        }

        identity_dev = verdict_score_map.get(identity_verdict, 0.5)
        cinema_dev = verdict_score_map.get(cinema_verdict, 0.5)

        # Cinema deviation weighted heavier for this gate
        return (identity_dev * 0.3 + cinema_dev * 0.7)


class MotionFidelityGate(DoctrineGate):
    """Gate 2: Motion Fidelity Check — Validates motion execution."""

    def __init__(self, project_path: str):
        """Initialize Motion Fidelity Gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "post_generation", "CINEMA_LAW_02")

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run motion fidelity gate.

        Checks if specified motion was executed correctly in output.

        Args:
            shot: Shot plan dictionary with camera_movement
            context: Optional context with motion_analysis

        Returns:
            GateResult verdict
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")

        # Get motion spec from shot
        motion_spec = shot.get("camera_movement")
        if not motion_spec or motion_spec == "static":
            return GateResult.PASS  # No motion required

        # Get motion analysis from context
        motion_analysis = context.get("motion_analysis", {})

        if not motion_analysis:
            # No motion analysis available
            entry = LedgerEntry(
                shot_id=shot_id,
                gate_result=GateResult.WARN.value,
                deviation_score=0.3,
                deviation_type="cinema",
                correction_applied=False,
                model_used="motion_fidelity",
                prompt_hash=self._compute_prompt_hash(shot.get("ltx_motion_prompt", "")),
                session_timestamp=self.session_timestamp,
                gate_position=self.gate_position,
                reason_code="MOTION_ANALYSIS_UNAVAILABLE",
                extra_data={"motion_spec": motion_spec},
            )
            self._write_ledger(entry)
            return GateResult.WARN

        motion_detected = motion_analysis.get("motion_detected", False)
        motion_magnitude = motion_analysis.get("motion_magnitude", 0.0)
        motion_type_match = motion_analysis.get("motion_type_match", False)
        detected_type = motion_analysis.get("detected_type")

        # Logic
        if not motion_detected:
            # Static output when motion was specified
            final_result = GateResult.REJECT
            reason = "MOTION_STATIC_OUTPUT"
        elif motion_magnitude < 0.60:
            # Weak motion
            final_result = GateResult.WARN
            reason = "MOTION_WEAK_MAGNITUDE"
        elif not motion_type_match:
            # Wrong motion type
            final_result = GateResult.WARN
            reason = "MOTION_TYPE_MISMATCH"
        else:
            # Motion detected and matches
            final_result = GateResult.PASS
            reason = "MOTION_FIDELITY_PASS"

        # Log
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=final_result.value,
            deviation_score=1.0 - motion_magnitude if motion_detected else 1.0,
            deviation_type="cinema",
            correction_applied=False,
            model_used="motion_fidelity",
            prompt_hash=self._compute_prompt_hash(shot.get("ltx_motion_prompt", "")),
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=reason,
            extra_data={
                "motion_spec": motion_spec,
                "motion_detected": motion_detected,
                "motion_magnitude": motion_magnitude,
                "detected_type": detected_type,
                "motion_type_match": motion_type_match,
            },
        )
        self._write_ledger(entry)

        return final_result


class DramaticFunctionGate(DoctrineGate):
    """Gate 3: Dramatic Function Scoring — Validates function match."""

    def __init__(self, project_path: str):
        """Initialize Dramatic Function Gate.

        Args:
            project_path: Path to ATLAS project
        """
        super().__init__(project_path, "post_generation", "CINEMA_LAW_03")
        self.calculator = CinemaScoreCalculator()

    def run(self, shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> GateResult:
        """Run dramatic function gate.

        Validates that shot matches intended dramatic function's visual grammar.

        Args:
            shot: Shot plan dictionary with _dramatic_function tag
            context: Optional context with cinema_scores

        Returns:
            GateResult verdict
        """
        context = context or {}
        shot_id = shot.get("shot_id", "unknown")

        # Get function tag from shot
        function_tag = shot.get("_dramatic_function")
        if not function_tag:
            return GateResult.PASS  # Can't evaluate without function

        # Get cinema scores
        cinema_scores = context.get("cinema_scores", {})
        if not cinema_scores:
            return GateResult.WARN

        # Get expected grammar map
        grammar_map = self.calculator.get_function_grammar_map(function_tag)
        if not grammar_map:
            return GateResult.PASS  # Unknown function

        # Score function match
        function_match = self._compute_function_match(cinema_scores, grammar_map, function_tag)

        # Determine verdict
        if function_match < 0.30 and context.get("has_identity_failure"):
            # Combined failure with identity issues
            final_result = GateResult.REJECT
            reason = "FUNCTION_AND_IDENTITY_MISMATCH"
        elif function_match < 0.50:
            final_result = GateResult.WARN
            reason = "FUNCTION_MISMATCH"
        else:
            final_result = GateResult.PASS
            reason = "FUNCTION_MATCH_PASS"

        # Log
        entry = LedgerEntry(
            shot_id=shot_id,
            gate_result=final_result.value,
            deviation_score=1.0 - function_match,
            deviation_type="cinema",
            correction_applied=False,
            model_used="dramatic_function",
            prompt_hash=self._compute_prompt_hash(shot.get("nano_prompt", "")),
            session_timestamp=self.session_timestamp,
            gate_position=self.gate_position,
            reason_code=reason,
            extra_data={
                "function_tag": function_tag,
                "function_match_score": function_match,
            },
        )
        self._write_ledger(entry)

        return final_result

    def _compute_function_match(
        self,
        cinema_scores: Dict[str, Any],
        grammar_map: Dict[str, Any],
        function_tag: str,
    ) -> float:
        """Compute match between cinema scores and expected grammar.

        Args:
            cinema_scores: Calculated cinema scores (dict of dimension -> score)
            grammar_map: Expected grammar for function
            function_tag: Dramatic function name

        Returns:
            Match score 0.0-1.0
        """
        if not grammar_map:
            return 0.5

        expected_avg = grammar_map.get("expected_average", 0.70)

        # Extract overall average from cinema_scores
        dimension_scores = []
        for key, value in cinema_scores.items():
            if isinstance(value, float):
                dimension_scores.append(value)
            elif isinstance(value, dict):
                dimension_scores.append(value.get("score", 0.0))
            else:
                dimension_scores.append(getattr(value, "score", 0.0))

        if not dimension_scores:
            return 0.5

        actual_avg = sum(dimension_scores) / len(dimension_scores)

        # Simple match: how close to expected average
        match_score = 1.0 - abs(actual_avg - expected_avg)
        return max(0.0, min(match_score, 1.0))


def run_phase5_post_generation(
    shot: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    project_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run Phase 5 post-generation cinematographic gates.

    Args:
        shot: Shot plan dictionary
        context: Optional context with vision scores
        project_path: Path to ATLAS project (defaults to /sessions/.../mnt/ATLAS_CONTROL_SYSTEM)

    Returns:
        List of gate results [{gate: str, result: GateResult.value}, ...]
    """
    if not project_path:
        project_path = str(Path(__file__).parent.parent)

    context = context or {}
    results = []

    # Calculate cinema scores if raw analysis available
    if "frame_analysis" in context and "cinema_scores" not in context:
        calculator = CinemaScoreCalculator()
        context["cinema_scores"] = calculator.score_shot_grammar(context["frame_analysis"])

    # Gate 1: Dual Perception
    dual = DualPerceptionGate(project_path)
    result_1 = dual.run(shot, context)
    results.append({"gate": "CINEMA_LAW_01", "result": result_1.value})

    # Gate 2: Motion Fidelity (only if motion specified)
    if shot.get("camera_movement") and shot["camera_movement"] != "static":
        motion = MotionFidelityGate(project_path)
        result_2 = motion.run(shot, context)
        results.append({"gate": "CINEMA_LAW_02", "result": result_2.value})

    # Gate 3: Dramatic Function
    dramatic = DramaticFunctionGate(project_path)
    result_3 = dramatic.run(shot, context)
    results.append({"gate": "CINEMA_LAW_03", "result": result_3.value})

    return results
