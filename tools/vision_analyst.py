"""
ATLAS V24 — VISION ANALYST (Meta-Observer / Scene Health Evaluator)
===================================================================
Post-render evaluator that reviews scenes as SEQUENCES, not individual frames.
Produces Scene Health Score across 8 dimensions, flags regressions,
and generates improvement recommendations for the next render pass.

Brain mapping:
  - Higher visual cortex: Pattern recognition across frames
  - Temporal lobe: Sequence continuity analysis
  - Prefrontal evaluation: Quality judgment and recommendations

Usage:
  from tools.vision_analyst import VisionAnalyst
  analyst = VisionAnalyst(project_path)
  report = analyst.evaluate_scene(scene_id, shots, frames)
"""

import json
import os
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# SCENE HEALTH DIMENSIONS (8 total)
# ============================================================================

HEALTH_DIMENSIONS = {
    "identity_consistency": {
        "weight": 0.20,
        "description": "Same character looks the same across all shots in scene",
        "threshold_pass": 0.80,
        "threshold_warn": 0.60,
    },
    "environment_stability": {
        "weight": 0.15,
        "description": "Room/location doesn't drift between shots",
        "threshold_pass": 0.75,
        "threshold_warn": 0.55,
    },
    "color_grade_coherence": {
        "weight": 0.10,
        "description": "Color temperature and grade consistent within scene",
        "threshold_pass": 0.80,
        "threshold_warn": 0.60,
    },
    "blocking_continuity": {
        "weight": 0.15,
        "description": "Character positions consistent across consecutive shots",
        "threshold_pass": 0.70,
        "threshold_warn": 0.50,
    },
    "pacing_rhythm": {
        "weight": 0.10,
        "description": "Shot durations create appropriate pacing for scene emotion",
        "threshold_pass": 0.70,
        "threshold_warn": 0.50,
    },
    "dialogue_fidelity": {
        "weight": 0.10,
        "description": "Speaking shots show mouth movement, reaction shots show listening",
        "threshold_pass": 0.75,
        "threshold_warn": 0.55,
    },
    "cinematic_variety": {
        "weight": 0.10,
        "description": "Mix of wide/medium/close shots, not repetitive angles",
        "threshold_pass": 0.65,
        "threshold_warn": 0.45,
    },
    "emotional_arc": {
        "weight": 0.10,
        "description": "Scene emotion builds/resolves appropriately per act position",
        "threshold_pass": 0.65,
        "threshold_warn": 0.45,
    },
}

# ============================================================================
# PACING PROFILES
# ============================================================================

PACING_PROFILES = {
    "allegro": {
        "avg_shot_duration": 6.0,
        "max_shot_duration": 10,
        "min_shots_per_minute": 8,
        "description": "Fast cutting, tension, chase, confrontation",
    },
    "andante": {
        "avg_shot_duration": 8.0,
        "max_shot_duration": 14,
        "min_shots_per_minute": 5,
        "description": "Walking pace, exploration, conversation",
    },
    "adagio": {
        "avg_shot_duration": 12.0,
        "max_shot_duration": 20,
        "min_shots_per_minute": 3,
        "description": "Slow, contemplative, emotional, ritual",
    },
    "moderato": {
        "avg_shot_duration": 8.0,
        "max_shot_duration": 16,
        "min_shots_per_minute": 4,
        "description": "Balanced, standard dramatic pacing",
    },
}

# Anti-CGI quality markers — detect AI artifacts
CGI_ARTIFACT_PATTERNS = [
    "plastic_skin",       # Overly smooth skin texture
    "dead_eyes",          # No eye highlight/catch light
    "symmetry_lock",      # Unnaturally perfect facial symmetry
    "float_hands",        # Hands disconnected from physics
    "wax_figure",         # Uncanny valley stillness
    "light_bleed",        # Inconsistent light source direction
    "morph_ghost",        # Frame-to-frame face morphing artifacts
    "clone_crowd",        # Repeated faces in background crowds
    "texture_swim",       # Textures shifting/swimming across frames
    "edge_glow",          # Unnatural glow around character edges
]


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ShotEvaluation:
    """Evaluation results for a single shot."""
    shot_id: str
    frame_path: Optional[str] = None
    video_path: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)
    artifacts_detected: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    vision_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        if not self.scores:
            return 0.0
        total = 0.0
        for dim_name, score in self.scores.items():
            weight = HEALTH_DIMENSIONS.get(dim_name, {}).get("weight", 0.1)
            total += score * weight
        return round(total, 4)


@dataclass
class SceneHealthReport:
    """Full health report for a scene."""
    scene_id: str
    timestamp: str = ""
    total_shots: int = 0
    evaluated_shots: int = 0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    verdict: str = "PENDING"  # PASS, WARN, FAIL, PENDING
    shot_evaluations: List[Dict] = field(default_factory=list)
    artifacts_summary: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    pacing_analysis: Dict[str, Any] = field(default_factory=dict)
    sequence_issues: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SequenceIssue:
    """A continuity issue between consecutive shots."""
    shot_a_id: str
    shot_b_id: str
    issue_type: str  # identity_jump, env_drift, color_shift, blocking_teleport
    severity: str    # critical, warning, info
    description: str
    dimension: str
    score_impact: float


# ============================================================================
# VISION ANALYST ENGINE
# ============================================================================

class VisionAnalyst:
    """
    Meta-observer that evaluates rendered scenes as sequences.
    Reviews frames and videos for quality, continuity, and fidelity.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.reports_dir = os.path.join(project_path, "reports", "vision_analyst")
        os.makedirs(self.reports_dir, exist_ok=True)

        # Load project data
        self.cast_map = self._load_json("cast_map.json")
        self.story_bible = self._load_json("story_bible.json")
        self.shot_plan = self._load_json("shot_plan.json")

        # Load previous reports for regression detection
        self.previous_reports = self._load_previous_reports()

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self.project_path, filename)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        return {}

    def _load_previous_reports(self) -> Dict[str, SceneHealthReport]:
        """Load most recent report per scene for regression comparison."""
        reports = {}
        if not os.path.exists(self.reports_dir):
            return reports
        for fname in sorted(os.listdir(self.reports_dir)):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self.reports_dir, fname)) as f:
                        data = json.load(f)
                        scene_id = data.get("scene_id", "")
                        if scene_id:
                            reports[scene_id] = data
                except Exception:
                    pass
        return reports

    # ────────────────────────────────────────────
    # SCENE EVALUATION (Primary entry point)
    # ────────────────────────────────────────────

    def evaluate_scene(
        self,
        scene_id: str,
        shots: List[dict],
        pacing_target: str = "moderato",
        act_position: Optional[str] = None,
    ) -> SceneHealthReport:
        """
        Evaluate an entire scene as a sequence.

        Args:
            scene_id: Scene identifier
            shots: List of shot dicts (must be in scene order)
            pacing_target: allegro/andante/adagio/moderato
            act_position: "setup"/"confrontation"/"resolution" for arc context

        Returns:
            SceneHealthReport with all dimensions scored
        """
        report = SceneHealthReport(
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            total_shots=len(shots),
        )

        if not shots:
            report.verdict = "FAIL"
            report.recommendations.append("No shots found for scene")
            return report

        # Evaluate each shot individually
        shot_evals = []
        for shot in shots:
            ev = self._evaluate_shot(shot)
            shot_evals.append(ev)
            report.evaluated_shots += 1

        report.shot_evaluations = [asdict(ev) for ev in shot_evals]

        # Score each dimension across the full sequence
        report.dimension_scores = {
            "identity_consistency": self._score_identity_consistency(shots, shot_evals),
            "environment_stability": self._score_environment_stability(shots, shot_evals),
            "color_grade_coherence": self._score_color_grade(shots),
            "blocking_continuity": self._score_blocking_continuity(shots),
            "pacing_rhythm": self._score_pacing(shots, pacing_target),
            "dialogue_fidelity": self._score_dialogue_fidelity(shots),
            "cinematic_variety": self._score_cinematic_variety(shots),
            "emotional_arc": self._score_emotional_arc(shots, act_position),
        }

        # Compute composite
        report.composite_score = sum(
            score * HEALTH_DIMENSIONS[dim]["weight"]
            for dim, score in report.dimension_scores.items()
        )
        report.composite_score = round(report.composite_score, 4)

        # Verdict
        if report.composite_score >= 0.75:
            report.verdict = "PASS"
        elif report.composite_score >= 0.55:
            report.verdict = "WARN"
        else:
            report.verdict = "FAIL"

        # Sequence continuity analysis
        report.sequence_issues = self._analyze_sequence_continuity(shots, shot_evals)

        # Pacing analysis
        report.pacing_analysis = self._analyze_pacing(shots, pacing_target)

        # Artifact summary
        artifact_counts = {}
        for ev in shot_evals:
            for art in ev.artifacts_detected:
                artifact_counts[art] = artifact_counts.get(art, 0) + 1
        report.artifacts_summary = artifact_counts

        # Generate recommendations
        report.recommendations = self._generate_recommendations(
            report, shots, shot_evals, pacing_target, act_position
        )

        # Regression check against previous
        regressions = self._check_regression(scene_id, report)
        if regressions:
            report.recommendations.insert(0, f"REGRESSION DETECTED: {'; '.join(regressions)}")

        # Save report
        self._save_report(report)

        return report

    # ────────────────────────────────────────────
    # PER-SHOT EVALUATION
    # ────────────────────────────────────────────

    def _evaluate_shot(self, shot: dict) -> ShotEvaluation:
        """Evaluate a single shot's quality markers."""
        ev = ShotEvaluation(shot_id=shot.get("shot_id", "unknown"))

        # Check for frame/video paths
        ev.frame_path = shot.get("first_frame_url", shot.get("first_frame_path", ""))
        ev.video_path = shot.get("video_path", "")

        # Pull existing vision scores if available
        vision = shot.get("vision", {})
        if vision:
            ev.vision_data = vision
            ev.scores["identity_consistency"] = vision.get("identity", 0.5)
            ev.scores["environment_stability"] = vision.get("location", 0.5)

        # Check for artifact indicators in prompt/metadata
        ev.artifacts_detected = self._detect_artifacts_from_metadata(shot)

        # Score from available data
        has_gold_neg = "NO morphing" in shot.get("ltx_motion_prompt", "")
        has_face_stable = "face stable" in shot.get("ltx_motion_prompt", "")
        has_performance = any(
            m in shot.get("ltx_motion_prompt", "")
            for m in ["character performs:", "character speaks:", "character reacts:"]
        )

        if has_gold_neg and has_face_stable:
            ev.scores.setdefault("identity_consistency", 0.7)
        if has_performance:
            ev.scores.setdefault("dialogue_fidelity", 0.7)

        return ev

    def _detect_artifacts_from_metadata(self, shot: dict) -> List[str]:
        """Check metadata for known CGI artifact risk factors."""
        artifacts = []

        # Long duration increases morph risk
        duration = shot.get("duration", 6)
        if duration >= 18:
            artifacts.append("morph_ghost")

        # Many characters increases clone risk
        chars = shot.get("characters", [])
        if len(chars) >= 4:
            artifacts.append("clone_crowd")

        # Check for missing gold standard protections
        ltx = shot.get("ltx_motion_prompt", "")
        if "NO morphing" not in ltx and chars:
            artifacts.append("morph_ghost")
        if "face stable" not in ltx and chars:
            artifacts.append("wax_figure")

        return artifacts

    # ────────────────────────────────────────────
    # DIMENSION SCORING
    # ────────────────────────────────────────────

    def _score_identity_consistency(self, shots: List[dict], evals: List[ShotEvaluation]) -> float:
        """Score character identity consistency across scene."""
        if not shots:
            return 0.5

        # Collect per-character appearance counts
        char_shots = {}
        for shot in shots:
            for char in shot.get("characters", []):
                char_shots.setdefault(char, []).append(shot.get("shot_id"))

        if not char_shots:
            return 0.8  # No characters = no identity issues

        # Check that character shots have vision identity scores
        identity_scores = []
        for ev in evals:
            if "identity_consistency" in ev.scores:
                identity_scores.append(ev.scores["identity_consistency"])

        if identity_scores:
            return round(sum(identity_scores) / len(identity_scores), 4)

        # Fallback: check that all character shots have gold standard
        gold_count = sum(
            1 for s in shots
            if s.get("characters") and "NO morphing" in s.get("ltx_motion_prompt", "")
        )
        char_shot_count = sum(1 for s in shots if s.get("characters"))
        if char_shot_count == 0:
            return 0.8
        return round(gold_count / char_shot_count, 4)

    def _score_environment_stability(self, shots: List[dict], evals: List[ShotEvaluation]) -> float:
        """Score environment consistency — same room shouldn't drift."""
        if len(shots) < 2:
            return 0.8

        # Check all shots have same location
        locations = set()
        for s in shots:
            loc = s.get("location", "").strip()
            if loc:
                locations.add(loc.upper())

        location_score = 1.0 if len(locations) <= 1 else max(0.3, 1.0 - (len(locations) - 1) * 0.2)

        # Factor in vision location scores
        env_scores = [
            ev.scores.get("environment_stability", 0.7) for ev in evals
            if "environment_stability" in ev.scores
        ]

        if env_scores:
            vision_avg = sum(env_scores) / len(env_scores)
            return round((location_score * 0.4 + vision_avg * 0.6), 4)

        return round(location_score, 4)

    def _score_color_grade(self, shots: List[dict]) -> float:
        """Score color grade consistency within scene."""
        if not shots:
            return 0.5

        # Check for scene anchor color grade
        scene_ids = set(s.get("scene_id", "") for s in shots)
        if len(scene_ids) > 1:
            return 0.6  # Mixed scenes get lower base

        # Check prompts for conflicting color language
        color_terms = set()
        for s in shots:
            prompt = s.get("nano_prompt", "") + " " + s.get("nano_prompt_final", "")
            for term in ["cold", "warm", "teal", "amber", "golden", "blue", "green", "red", "neutral"]:
                if term in prompt.lower():
                    color_terms.add(term)

        # Many conflicting color terms = poor coherence
        if len(color_terms) <= 2:
            return 0.9
        elif len(color_terms) <= 4:
            return 0.7
        else:
            return 0.5

    def _score_blocking_continuity(self, shots: List[dict]) -> float:
        """Score character position continuity between consecutive shots."""
        if len(shots) < 2:
            return 0.8

        issues = 0
        pairs = 0
        for i in range(len(shots) - 1):
            a, b = shots[i], shots[i + 1]
            # Check if chained shots share characters
            chars_a = set(a.get("characters", []))
            chars_b = set(b.get("characters", []))
            shared = chars_a & chars_b
            if not shared:
                continue
            pairs += 1

            # Check state_out → state_in consistency
            state_out = a.get("state_out", {})
            state_in = b.get("state_in", {})
            for char in shared:
                out_pose = state_out.get(char, {}).get("pose", "")
                in_pose = state_in.get(char, {}).get("pose", "")
                if out_pose and in_pose and out_pose != in_pose:
                    # Pose changed without connector
                    if not b.get("_connector_shot"):
                        issues += 1

        if pairs == 0:
            return 0.8
        return round(max(0.3, 1.0 - (issues / pairs) * 0.3), 4)

    def _score_pacing(self, shots: List[dict], target: str) -> float:
        """Score pacing against target tempo profile."""
        profile = PACING_PROFILES.get(target, PACING_PROFILES["moderato"])

        durations = [s.get("duration", 6) for s in shots]
        if not durations:
            return 0.5

        avg_dur = sum(durations) / len(durations)
        target_avg = profile["avg_shot_duration"]

        # How close is actual avg to target
        deviation = abs(avg_dur - target_avg) / target_avg
        avg_score = max(0.0, 1.0 - deviation)

        # Check for over-long shots
        max_dur = profile["max_shot_duration"]
        over_long = sum(1 for d in durations if d > max_dur)
        duration_score = max(0.3, 1.0 - (over_long / len(durations)) * 0.5)

        # Variety score — not all shots same duration
        unique_durations = len(set(durations))
        variety_score = min(1.0, unique_durations / max(3, len(durations) * 0.3))

        return round(avg_score * 0.5 + duration_score * 0.3 + variety_score * 0.2, 4)

    def _score_dialogue_fidelity(self, shots: List[dict]) -> float:
        """Score dialogue shot quality."""
        dialogue_shots = [s for s in shots if s.get("dialogue_text")]
        if not dialogue_shots:
            return 0.8  # No dialogue = no issues

        score_sum = 0
        for s in dialogue_shots:
            ltx = s.get("ltx_motion_prompt", "")
            has_speaks = "character speaks:" in ltx
            has_perform = "character performs:" in ltx or "character reacts:" in ltx

            if has_speaks:
                score_sum += 1.0
            elif has_perform:
                score_sum += 0.6
            else:
                score_sum += 0.2

        return round(score_sum / len(dialogue_shots), 4)

    def _score_cinematic_variety(self, shots: List[dict]) -> float:
        """Score shot type variety — good filmmaking uses diverse angles."""
        if len(shots) < 3:
            return 0.7

        types = [s.get("shot_type", "medium") for s in shots]
        unique_types = set(types)

        # At minimum: wide + medium + close
        has_wide = any(t in ("wide", "establishing", "master", "medium_wide") for t in types)
        has_medium = any(t in ("medium", "medium_close", "over_the_shoulder") for t in types)
        has_close = any(t in ("close", "extreme_close", "close_up", "insert") for t in types)

        coverage = sum([has_wide, has_medium, has_close])
        coverage_score = coverage / 3.0

        # Variety score
        variety_score = min(1.0, len(unique_types) / max(3, len(shots) * 0.3))

        # Repetition penalty — same type back to back
        repeats = sum(1 for i in range(1, len(types)) if types[i] == types[i-1])
        repeat_penalty = repeats / max(1, len(types) - 1)

        return round(coverage_score * 0.5 + variety_score * 0.3 + (1.0 - repeat_penalty) * 0.2, 4)

    def _score_emotional_arc(self, shots: List[dict], act_position: Optional[str]) -> float:
        """Score emotional progression through the scene."""
        if len(shots) < 2:
            return 0.7

        # Check emotion intensity progression
        intensities = []
        for s in shots:
            state_out = s.get("state_out", {})
            for char, state in state_out.items():
                if isinstance(state, dict):
                    intensities.append(state.get("emotion_intensity", 5))

        if not intensities:
            return 0.6

        # Scenes should have SOME emotional movement
        intensity_range = max(intensities) - min(intensities)
        if intensity_range == 0:
            return 0.5  # Flat emotion = boring

        # Act-appropriate direction
        if act_position == "setup":
            # Setup should build — end higher than start
            builds = intensities[-1] > intensities[0]
            return 0.8 if builds else 0.6
        elif act_position == "resolution":
            # Resolution should resolve — arc down or stabilize
            resolves = intensities[-1] <= intensities[len(intensities)//2]
            return 0.8 if resolves else 0.6
        else:
            # Confrontation — should peak somewhere
            peak_pos = intensities.index(max(intensities)) / len(intensities)
            return 0.8 if 0.3 < peak_pos < 0.9 else 0.6

    # ────────────────────────────────────────────
    # SEQUENCE ANALYSIS
    # ────────────────────────────────────────────

    def _analyze_sequence_continuity(
        self, shots: List[dict], evals: List[ShotEvaluation]
    ) -> List[Dict]:
        """Detect continuity issues between consecutive shots."""
        issues = []

        for i in range(len(shots) - 1):
            a, b = shots[i], shots[i + 1]
            a_id = a.get("shot_id", "")
            b_id = b.get("shot_id", "")

            # Skip if B-roll or independent
            if b.get("_broll") or b.get("_no_chain"):
                continue

            # Check for intercut jumps
            if a.get("_intercut") or b.get("_intercut"):
                continue

            # Identity jump — shared character with low vision score
            shared_chars = set(a.get("characters", [])) & set(b.get("characters", []))
            if shared_chars:
                a_vision = a.get("vision", {}).get("identity", 0.7)
                b_vision = b.get("vision", {}).get("identity", 0.7)
                if a_vision < 0.6 or b_vision < 0.6:
                    issues.append({
                        "shot_a_id": a_id,
                        "shot_b_id": b_id,
                        "issue_type": "identity_jump",
                        "severity": "critical" if min(a_vision, b_vision) < 0.4 else "warning",
                        "description": f"Identity score drops to {min(a_vision, b_vision):.2f} between shots",
                        "dimension": "identity_consistency",
                    })

            # Environment drift — location mismatch
            loc_a = a.get("location", "").upper()
            loc_b = b.get("location", "").upper()
            if loc_a and loc_b and loc_a != loc_b:
                issues.append({
                    "shot_a_id": a_id,
                    "shot_b_id": b_id,
                    "issue_type": "env_drift",
                    "severity": "critical",
                    "description": f"Location changes from '{loc_a}' to '{loc_b}' within same scene",
                    "dimension": "environment_stability",
                })

            # Color grade shift check (via prompt analysis)
            grade_a = self._extract_grade_terms(a)
            grade_b = self._extract_grade_terms(b)
            if grade_a and grade_b and grade_a != grade_b:
                issues.append({
                    "shot_a_id": a_id,
                    "shot_b_id": b_id,
                    "issue_type": "color_shift",
                    "severity": "warning",
                    "description": f"Color grade terms differ: {grade_a} vs {grade_b}",
                    "dimension": "color_grade_coherence",
                })

        return issues

    def _extract_grade_terms(self, shot: dict) -> str:
        """Extract dominant color grade term from prompt."""
        prompt = (shot.get("nano_prompt_final", "") or shot.get("nano_prompt", "")).lower()
        for term in ["cold desaturated", "warm amber", "teal", "golden hour", "high contrast", "neutral"]:
            if term in prompt:
                return term
        return ""

    # ────────────────────────────────────────────
    # PACING ANALYSIS
    # ────────────────────────────────────────────

    def _analyze_pacing(self, shots: List[dict], target: str) -> Dict:
        """Detailed pacing analysis."""
        profile = PACING_PROFILES.get(target, PACING_PROFILES["moderato"])
        durations = [s.get("duration", 6) for s in shots]

        if not durations:
            return {"error": "no durations"}

        total_runtime = sum(durations)
        avg_duration = total_runtime / len(durations)

        return {
            "target_profile": target,
            "target_avg_duration": profile["avg_shot_duration"],
            "actual_avg_duration": round(avg_duration, 1),
            "total_runtime_seconds": total_runtime,
            "shot_count": len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "duration_distribution": {
                "short_4_6": sum(1 for d in durations if d <= 6),
                "medium_8_12": sum(1 for d in durations if 8 <= d <= 12),
                "long_14_20": sum(1 for d in durations if d >= 14),
            },
            "shots_per_minute": round(len(durations) / (total_runtime / 60), 1) if total_runtime > 0 else 0,
        }

    # ────────────────────────────────────────────
    # RECOMMENDATIONS
    # ────────────────────────────────────────────

    def _generate_recommendations(
        self,
        report: SceneHealthReport,
        shots: List[dict],
        evals: List[ShotEvaluation],
        pacing_target: str,
        act_position: Optional[str],
    ) -> List[str]:
        """Generate actionable recommendations based on scores."""
        recs = []

        for dim, score in report.dimension_scores.items():
            threshold = HEALTH_DIMENSIONS[dim]["threshold_warn"]
            if score < threshold:
                recs.append(self._recommendation_for_dimension(dim, score, shots, evals))

        # Artifact-specific recommendations
        artifact_counts = report.artifacts_summary
        if artifact_counts.get("morph_ghost", 0) > 2:
            recs.append(
                f"MORPH RISK: {artifact_counts['morph_ghost']} shots at risk of face morphing. "
                "Consider shortening durations or adding stronger face stability constraints."
            )
        if artifact_counts.get("wax_figure", 0) > 0:
            recs.append(
                f"QUALITY: {artifact_counts['wax_figure']} shots missing face stability markers. "
                "Run fix-v16 to inject gold standard negatives."
            )

        # Pacing recommendations
        pacing = report.pacing_analysis
        if pacing.get("actual_avg_duration", 0) > PACING_PROFILES.get(pacing_target, {}).get("avg_shot_duration", 10) * 1.5:
            recs.append(
                f"PACING: Average shot duration ({pacing['actual_avg_duration']}s) is significantly above "
                f"target for {pacing_target} ({PACING_PROFILES[pacing_target]['avg_shot_duration']}s). "
                "Consider tighter cuts or splitting long shots."
            )

        return recs

    def _recommendation_for_dimension(
        self, dim: str, score: float, shots: List[dict], evals: List[ShotEvaluation]
    ) -> str:
        """Generate specific recommendation for a failed dimension."""
        recs_map = {
            "identity_consistency": f"IDENTITY ({score:.2f}): Character faces may drift. Increase face stability markers or regenerate low-scoring shots.",
            "environment_stability": f"ENVIRONMENT ({score:.2f}): Room/location drifting between shots. Check end-frame chaining and env drift guard.",
            "color_grade_coherence": f"COLOR ({score:.2f}): Color grade inconsistent. Verify scene anchor system is applying correct grade.",
            "blocking_continuity": f"BLOCKING ({score:.2f}): Character positions jump between shots. May need connector shots or state tracking.",
            "pacing_rhythm": f"PACING ({score:.2f}): Shot durations don't match target tempo. Review duration scaling.",
            "dialogue_fidelity": f"DIALOGUE ({score:.2f}): Speaking shots missing performance markers. Run fix-v16 CHECK 5B.",
            "cinematic_variety": f"VARIETY ({score:.2f}): Shot types too repetitive. Add more wide/close variety.",
            "emotional_arc": f"EMOTION ({score:.2f}): Emotional progression flat or misplaced. Review beat injection.",
        }
        return recs_map.get(dim, f"{dim} ({score:.2f}): Below threshold.")

    # ────────────────────────────────────────────
    # REGRESSION DETECTION
    # ────────────────────────────────────────────

    def _check_regression(self, scene_id: str, current: SceneHealthReport) -> List[str]:
        """Compare against previous report for this scene."""
        prev = self.previous_reports.get(scene_id)
        if not prev:
            return []

        regressions = []
        prev_scores = prev.get("dimension_scores", {})

        for dim, current_score in current.dimension_scores.items():
            prev_score = prev_scores.get(dim, 0)
            if current_score < prev_score - 0.1:  # >10% regression
                regressions.append(
                    f"{dim}: {prev_score:.2f} → {current_score:.2f} "
                    f"(dropped {(prev_score - current_score):.2f})"
                )

        if current.composite_score < prev.get("composite_score", 0) - 0.05:
            regressions.insert(0,
                f"COMPOSITE: {prev.get('composite_score', 0):.2f} → {current.composite_score:.2f}"
            )

        return regressions

    # ────────────────────────────────────────────
    # PERSISTENCE
    # ────────────────────────────────────────────

    def _save_report(self, report: SceneHealthReport):
        """Save report to disk."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"scene_{report.scene_id}_{ts}.json"
        path = os.path.join(self.reports_dir, filename)
        try:
            import tempfile
            data = report.to_dict()
            fd, tmp = tempfile.mkstemp(dir=self.reports_dir, suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
            logger.info(f"Vision analyst report saved: {path}")
        except Exception as e:
            logger.error(f"Failed to save vision analyst report: {e}")

    # ────────────────────────────────────────────
    # BATCH EVALUATION
    # ────────────────────────────────────────────

    def evaluate_all_scenes(
        self,
        pacing_targets: Optional[Dict[str, str]] = None,
        act_positions: Optional[Dict[str, str]] = None,
    ) -> Dict[str, SceneHealthReport]:
        """Evaluate all scenes in the project."""
        shots_data = self.shot_plan if isinstance(self.shot_plan, list) else self.shot_plan.get("shots", [])
        if not shots_data:
            return {}

        # Group shots by scene
        scenes = {}
        for shot in shots_data:
            sid = shot.get("scene_id", "")
            scenes.setdefault(sid, []).append(shot)

        results = {}
        for scene_id in sorted(scenes.keys()):
            target = (pacing_targets or {}).get(scene_id, "moderato")
            act_pos = (act_positions or {}).get(scene_id)
            report = self.evaluate_scene(scene_id, scenes[scene_id], target, act_pos)
            results[scene_id] = report
            logger.info(
                f"Scene {scene_id}: {report.verdict} "
                f"(composite={report.composite_score:.3f}, "
                f"shots={report.evaluated_shots})"
            )

        return results

    def generate_project_health_summary(self) -> Dict[str, Any]:
        """Generate a project-level health summary from all scene reports."""
        reports = self.evaluate_all_scenes()

        if not reports:
            return {"status": "NO_DATA", "scenes": 0}

        scene_scores = [r.composite_score for r in reports.values()]
        scene_verdicts = [r.verdict for r in reports.values()]

        all_artifacts = {}
        all_issues = []
        for r in reports.values():
            for art, count in r.artifacts_summary.items():
                all_artifacts[art] = all_artifacts.get(art, 0) + count
            all_issues.extend(r.sequence_issues)

        return {
            "status": "PASS" if all(v == "PASS" for v in scene_verdicts) else "NEEDS_REVIEW",
            "scenes_evaluated": len(reports),
            "scenes_passing": sum(1 for v in scene_verdicts if v == "PASS"),
            "scenes_warning": sum(1 for v in scene_verdicts if v == "WARN"),
            "scenes_failing": sum(1 for v in scene_verdicts if v == "FAIL"),
            "avg_composite_score": round(sum(scene_scores) / len(scene_scores), 4),
            "min_composite_score": round(min(scene_scores), 4),
            "max_composite_score": round(max(scene_scores), 4),
            "total_sequence_issues": len(all_issues),
            "critical_issues": sum(1 for i in all_issues if i.get("severity") == "critical"),
            "artifact_summary": all_artifacts,
            "per_scene": {
                sid: {
                    "score": r.composite_score,
                    "verdict": r.verdict,
                    "shots": r.total_shots,
                    "issues": len(r.sequence_issues),
                }
                for sid, r in sorted(reports.items())
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
