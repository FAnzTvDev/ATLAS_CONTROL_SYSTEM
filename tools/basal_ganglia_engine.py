"""
ATLAS V24 — BASAL GANGLIA ENGINE (Action Selection)
====================================================
Competitive candidate scoring for shot selection.
Generates multiple candidates, scores across 6 dimensions,
selects winner via Go/No-Go pathway, records reward memory.

Brain mapping:
  - Direct pathway (Go): Allow candidate if score > threshold
  - Indirect pathway (No-Go): Suppress candidate if score < threshold
  - Dopamine: Reward memory from composite scores

Usage:
  from tools.basal_ganglia_engine import BasalGangliaEngine
  engine = BasalGangliaEngine(project_path)
  winner = engine.select_best_candidate(candidates, shot, context)
"""

import json
import os
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# SCORING DIMENSIONS (6 total)
# ============================================================================

@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    dimension: str
    score: float           # 0.0-1.0
    weight: float          # How much this matters
    evidence: str = ""     # Why this score
    is_go: bool = True     # True = pass, False = suppress

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


# Dimension weights (must sum to 1.0)
DIMENSION_WEIGHTS = {
    "identity_fidelity": 0.25,    # Face matches canonical reference
    "blocking_accuracy": 0.20,     # Character position matches beat direction
    "cinematic_rhythm": 0.15,      # Shot size progresses naturally
    "emotional_arc": 0.15,         # Emotion intensity follows trajectory
    "environment_lock": 0.15,      # Location matches scene anchor
    "prompt_fidelity": 0.10,       # Output matches prompt intent
}

# Go/No-Go thresholds
GO_THRESHOLD = 0.60          # Candidate must score above this to pass
NOGO_THRESHOLD = 0.40        # Below this triggers regeneration
WINNING_THRESHOLD = 0.85     # Above this is a winning pattern


@dataclass
class CandidateResult:
    """Result of evaluating a single candidate."""
    candidate_id: str
    dimension_scores: Dict[str, DimensionScore] = field(default_factory=dict)
    composite_score: float = 0.0
    verdict: str = "pending"  # "go", "no_go", "winner"
    evidence: List[str] = field(default_factory=list)

    def compute_composite(self):
        """Calculate weighted composite score."""
        if not self.dimension_scores:
            self.composite_score = 0.0
            return
        self.composite_score = sum(
            ds.weighted_score for ds in self.dimension_scores.values()
        )
        # Determine verdict
        if self.composite_score >= WINNING_THRESHOLD:
            self.verdict = "winner"
        elif self.composite_score >= GO_THRESHOLD:
            self.verdict = "go"
        else:
            self.verdict = "no_go"


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def score_identity_fidelity(
    candidate: dict,
    shot: dict,
    cast_map: dict,
) -> DimensionScore:
    """
    Score how well the candidate preserves character identity.
    Uses vision scores if available, falls back to prompt analysis.
    """
    score = 0.7  # Default baseline
    evidence = "baseline score (no vision data)"

    # Check if vision scores exist on the candidate
    vision = candidate.get("vision", candidate.get("_vision_scores", {}))
    if vision:
        identity_score = vision.get("identity", vision.get("face_score", 0))
        if identity_score > 0:
            score = identity_score
            evidence = f"vision identity score: {identity_score:.2f}"

    # Check if characters are present and have refs
    characters = shot.get("characters", [])
    if not characters:
        score = 1.0  # No characters = no identity to check
        evidence = "no characters in shot (landscape/B-roll)"

    has_ref = any(
        cast_map.get(c, {}).get("character_reference_url")
        for c in characters if isinstance(cast_map.get(c), dict)
    )
    if not has_ref and characters:
        score *= 0.8  # Penalty for missing refs
        evidence += " | missing character reference images"

    is_go = score >= 0.70
    return DimensionScore(
        dimension="identity_fidelity",
        score=score,
        weight=DIMENSION_WEIGHTS["identity_fidelity"],
        evidence=evidence,
        is_go=is_go,
    )


def score_blocking_accuracy(
    candidate: dict,
    shot: dict,
    previous_shot: Optional[dict] = None,
) -> DimensionScore:
    """
    Score how well character placement matches beat direction.
    Checks for unmotivated pose changes from previous shot.
    """
    score = 0.7
    evidence = "baseline"

    # Check if beat action exists and was reflected
    beat_action = shot.get("_beat_action", shot.get("description", ""))
    if beat_action:
        # Check if the candidate's prompt contains the action
        prompt = candidate.get("nano_prompt", candidate.get("nano_prompt_final", ""))
        if beat_action[:30].lower() in prompt.lower():
            score = 0.85
            evidence = "beat action reflected in prompt"
        else:
            score = 0.60
            evidence = "beat action may not be reflected"

    # Check pose continuity with previous shot
    if previous_shot:
        prev_state_out = previous_shot.get("state_out", {})
        curr_state_in = shot.get("state_in", {})
        if prev_state_out and curr_state_in:
            # Compare character poses
            mismatches = 0
            for char_name in shot.get("characters", []):
                prev_pose = prev_state_out.get(char_name, {}).get("pose", "")
                curr_pose = curr_state_in.get(char_name, {}).get("pose", "")
                if prev_pose and curr_pose and prev_pose != curr_pose:
                    # Pose changed — check if motivated
                    if not shot.get("_connector_shot"):
                        mismatches += 1
            if mismatches > 0:
                score -= 0.15 * mismatches
                evidence += f" | {mismatches} unmotivated pose change(s)"

    return DimensionScore(
        dimension="blocking_accuracy",
        score=max(0, min(1, score)),
        weight=DIMENSION_WEIGHTS["blocking_accuracy"],
        evidence=evidence,
        is_go=score >= 0.50,
    )


def score_cinematic_rhythm(
    candidate: dict,
    shot: dict,
    previous_shots: List[dict] = None,
) -> DimensionScore:
    """
    Score shot-size progression and cinematic variety.
    Avoids monotony (same framing repeated) and unmotivated jumps.
    """
    score = 0.75
    evidence = "baseline"

    if not previous_shots or len(previous_shots) < 2:
        return DimensionScore(
            dimension="cinematic_rhythm",
            score=score,
            weight=DIMENSION_WEIGHTS["cinematic_rhythm"],
            evidence="insufficient history for rhythm analysis",
            is_go=True,
        )

    # Check for shot-type monotony
    current_type = shot.get("shot_type", "medium").lower()
    recent_types = [s.get("shot_type", "").lower() for s in previous_shots[-3:]]

    if recent_types and all(t == current_type for t in recent_types):
        score -= 0.20
        evidence = f"monotony: {current_type} repeated {len(recent_types)+1} times"

    # Check for coverage role variety
    current_role = shot.get("coverage_role", "")
    recent_roles = [s.get("coverage_role", "") for s in previous_shots[-2:]]
    if recent_roles and current_role and current_role not in recent_roles:
        score += 0.10
        evidence += " | good coverage variety"

    # Check shot-size progression (wide->medium->close is natural)
    SIZE_ORDER = {"establishing": 0, "wide": 1, "master": 1, "medium_wide": 2,
                  "medium": 3, "medium_close": 4, "close": 5, "extreme_close": 6}
    current_size = SIZE_ORDER.get(current_type, 3)
    if previous_shots:
        prev_type = previous_shots[-1].get("shot_type", "medium").lower()
        prev_size = SIZE_ORDER.get(prev_type, 3)
        size_jump = abs(current_size - prev_size)
        if size_jump <= 2:
            score += 0.05  # Natural progression
        elif size_jump >= 4:
            score -= 0.10  # Jarring jump
            evidence += f" | large size jump ({prev_type}->{current_type})"

    return DimensionScore(
        dimension="cinematic_rhythm",
        score=max(0, min(1, score)),
        weight=DIMENSION_WEIGHTS["cinematic_rhythm"],
        evidence=evidence,
        is_go=score >= 0.40,
    )


def score_emotional_arc(
    candidate: dict,
    shot: dict,
    lite_data: dict = None,
) -> DimensionScore:
    """
    Score emotion intensity against the film's emotional trajectory.
    Uses Global Perception data from PROJECT_TRUTH.
    """
    score = 0.70
    evidence = "baseline"

    if not lite_data:
        return DimensionScore(
            dimension="emotional_arc",
            score=score,
            weight=DIMENSION_WEIGHTS["emotional_arc"],
            evidence="no global perception data available",
            is_go=True,
        )

    trajectory = lite_data.get("emotional_trajectory", {})
    target_intensity = trajectory.get("current", 0.5)

    # Check if shot has emotion data
    emotion = shot.get("emotion", shot.get("emotion_state", ""))
    if emotion:
        # Map emotion words to intensity
        HIGH_INTENSITY = {"anger", "fury", "rage", "terror", "despair", "agony", "explosive"}
        MED_INTENSITY = {"tension", "suspicion", "dread", "grief", "determination", "urgency"}
        LOW_INTENSITY = {"calm", "neutral", "resigned", "hope", "contemplative", "tender"}

        emotion_lower = emotion.lower()
        if any(w in emotion_lower for w in HIGH_INTENSITY):
            shot_intensity = 0.85
        elif any(w in emotion_lower for w in MED_INTENSITY):
            shot_intensity = 0.60
        else:
            shot_intensity = 0.35

        # Score based on alignment with trajectory
        diff = abs(shot_intensity - target_intensity)
        if diff <= 0.15:
            score = 0.90
            evidence = f"emotion aligned with trajectory (target: {target_intensity:.1f})"
        elif diff <= 0.30:
            score = 0.70
            evidence = f"emotion close to trajectory"
        else:
            score = 0.50
            evidence = f"emotion misaligned (shot: {shot_intensity:.1f} vs target: {target_intensity:.1f})"

    return DimensionScore(
        dimension="emotional_arc",
        score=score,
        weight=DIMENSION_WEIGHTS["emotional_arc"],
        evidence=evidence,
        is_go=score >= 0.40,
    )


def score_environment_lock(
    candidate: dict,
    shot: dict,
) -> DimensionScore:
    """
    Score location consistency with scene anchor.
    """
    score = 0.75
    evidence = "baseline"

    vision = candidate.get("vision", candidate.get("_vision_scores", {}))
    if vision:
        loc_score = vision.get("location", vision.get("location_score", 0))
        if loc_score > 0:
            score = loc_score
            evidence = f"vision location score: {loc_score:.2f}"

    # Check if location master exists
    if shot.get("_has_location_master"):
        score = min(1.0, score + 0.05)
        evidence += " | location master available"

    return DimensionScore(
        dimension="environment_lock",
        score=score,
        weight=DIMENSION_WEIGHTS["environment_lock"],
        evidence=evidence,
        is_go=score >= 0.55,
    )


def score_prompt_fidelity(
    candidate: dict,
    shot: dict,
) -> DimensionScore:
    """
    Score how well the generated output matches the prompt intent.
    Uses CLIP score if available, otherwise prompt analysis.
    """
    score = 0.70
    evidence = "baseline"

    vision = candidate.get("vision", candidate.get("_vision_scores", {}))
    if vision:
        clip_score = vision.get("clip", vision.get("clip_score", 0))
        if clip_score > 0:
            # CLIP scores are typically 0.20-0.35 range
            score = min(1.0, clip_score / 0.35)
            evidence = f"CLIP score: {clip_score:.3f}"

    # Check for performance marker
    ltx = candidate.get("ltx_motion_prompt", candidate.get("ltx_prompt_lite", ""))
    if shot.get("characters") and ltx:
        has_marker = any(m in ltx.lower() for m in
                        ["character speaks:", "character performs:", "character reacts:"])
        if has_marker:
            score = min(1.0, score + 0.10)
            evidence += " | performance marker present"
        else:
            score -= 0.15
            evidence += " | MISSING performance marker"

    return DimensionScore(
        dimension="prompt_fidelity",
        score=max(0, min(1, score)),
        weight=DIMENSION_WEIGHTS["prompt_fidelity"],
        evidence=evidence,
        is_go=score >= 0.50,
    )


# ============================================================================
# BASAL GANGLIA ENGINE
# ============================================================================

class BasalGangliaEngine:
    """
    The action selection engine. Evaluates candidates, selects winner,
    records reward memory.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.reward_log_path = os.path.join(project_path, "reports", "reward_log.jsonl")
        os.makedirs(os.path.dirname(self.reward_log_path), exist_ok=True)

    def evaluate_candidate(
        self,
        candidate: dict,
        shot: dict,
        cast_map: dict = None,
        previous_shot: dict = None,
        previous_shots: list = None,
        lite_data: dict = None,
    ) -> CandidateResult:
        """
        Score a single candidate across all 6 dimensions.
        Returns CandidateResult with Go/No-Go verdict.
        """
        result = CandidateResult(
            candidate_id=candidate.get("variant_id", candidate.get("shot_id", "unknown")),
        )

        # Score each dimension
        result.dimension_scores["identity_fidelity"] = score_identity_fidelity(
            candidate, shot, cast_map or {}
        )
        result.dimension_scores["blocking_accuracy"] = score_blocking_accuracy(
            candidate, shot, previous_shot
        )
        result.dimension_scores["cinematic_rhythm"] = score_cinematic_rhythm(
            candidate, shot, previous_shots
        )
        result.dimension_scores["emotional_arc"] = score_emotional_arc(
            candidate, shot, lite_data
        )
        result.dimension_scores["environment_lock"] = score_environment_lock(
            candidate, shot
        )
        result.dimension_scores["prompt_fidelity"] = score_prompt_fidelity(
            candidate, shot
        )

        # Compute composite
        result.compute_composite()

        # Build evidence summary
        for dim_name, ds in result.dimension_scores.items():
            status = "GO" if ds.is_go else "NO-GO"
            result.evidence.append(f"{dim_name}: {ds.score:.2f} [{status}] - {ds.evidence}")

        return result

    def select_best_candidate(
        self,
        candidates: List[dict],
        shot: dict,
        cast_map: dict = None,
        previous_shot: dict = None,
        previous_shots: list = None,
        lite_data: dict = None,
    ) -> Tuple[dict, CandidateResult]:
        """
        The Go/No-Go pathway. Evaluate all candidates, select the winner.

        Returns: (winning_candidate, result)
        If ALL candidates fail No-Go threshold, returns (best_of_worst, result)
        with result.verdict = "no_go" signaling regeneration needed.
        """
        if not candidates:
            raise ValueError("No candidates to evaluate")

        if len(candidates) == 1:
            result = self.evaluate_candidate(
                candidates[0], shot, cast_map, previous_shot, previous_shots, lite_data
            )
            self._record_reward(shot, candidates[0], result)
            return candidates[0], result

        # Evaluate all candidates
        results = []
        for candidate in candidates:
            result = self.evaluate_candidate(
                candidate, shot, cast_map, previous_shot, previous_shots, lite_data
            )
            results.append((candidate, result))

        # Sort by composite score (highest first)
        results.sort(key=lambda x: x[1].composite_score, reverse=True)

        winner_candidate, winner_result = results[0]

        # Check if winner passes Go threshold
        if winner_result.composite_score < NOGO_THRESHOLD:
            logger.warning(
                f"[BASAL GANGLIA] All candidates below No-Go threshold for {shot.get('shot_id')}. "
                f"Best: {winner_result.composite_score:.2f}. Regeneration recommended."
            )
            winner_result.verdict = "no_go"

        # Record reward
        self._record_reward(shot, winner_candidate, winner_result)

        logger.info(
            f"[BASAL GANGLIA] {shot.get('shot_id')}: selected {winner_result.candidate_id} "
            f"(score: {winner_result.composite_score:.2f}, verdict: {winner_result.verdict})"
        )

        return winner_candidate, winner_result

    def _record_reward(self, shot: dict, candidate: dict, result: CandidateResult):
        """Write reward entry to append-only log."""
        prompt = candidate.get("nano_prompt_final", candidate.get("nano_prompt", ""))
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        entry = {
            "shot_id": shot.get("shot_id", ""),
            "candidate_id": result.candidate_id,
            "prompt_hash": prompt_hash,
            "composite_score": round(result.composite_score, 4),
            "verdict": result.verdict,
            "dimension_scores": {
                name: round(ds.score, 4)
                for name, ds in result.dimension_scores.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
            "is_winning_pattern": result.verdict == "winner",
        }

        try:
            with open(self.reward_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"[BASAL GANGLIA] Failed to write reward log: {e}")

    def get_statistics(self) -> dict:
        """Get engine statistics from reward log."""
        stats = {"total_evaluations": 0, "winners": 0, "go": 0, "no_go": 0, "avg_score": 0.0}

        if not os.path.exists(self.reward_log_path):
            return stats

        scores = []
        with open(self.reward_log_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    stats["total_evaluations"] += 1
                    if entry.get("verdict") == "winner":
                        stats["winners"] += 1
                    elif entry.get("verdict") == "go":
                        stats["go"] += 1
                    else:
                        stats["no_go"] += 1
                    scores.append(entry.get("composite_score", 0))
                except json.JSONDecodeError:
                    continue

        if scores:
            stats["avg_score"] = round(sum(scores) / len(scores), 4)

        return stats


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_path = os.path.join(base, "pipeline_outputs", project)

    engine = BasalGangliaEngine(project_path)
    stats = engine.get_statistics()
    print(f"\n[BASAL GANGLIA] Statistics for {project}:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
