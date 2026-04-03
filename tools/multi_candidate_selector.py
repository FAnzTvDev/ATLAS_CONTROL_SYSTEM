"""
ATLAS V27.5.1 MULTI-CANDIDATE SELECTOR (Layer 5)
==================================================
Generates N candidates for character-critical shots.
Vision Judge scores each candidate. Best wins.

THE PROBLEM (from 16-shot strategic test):
  012_140B: Thomas MCU generated Nadia instead. 1 candidate, 0/10.
  If 3 candidates had been generated, at least 1 would show the right person.

THE FIX:
  1. Shot type determines candidate count (hero=3, production=2, broll=1)
  2. All candidates generated in parallel (same FAL call with num_outputs=N)
  3. Vision Judge scores each candidate against character markers
  4. Best candidate promoted to first_frames/, others archived

COST MODEL:
  FAL nano-banana-pro charges per IMAGE, not per call.
  3 candidates = 3x the image cost ($0.09 vs $0.03 for hero shots).
  But a WRONG identity costs a full regen cycle anyway.
  Net savings: prevent 44% identity regen rate → 3x cost but 2.3x fewer regens.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.multi_candidate")


# ═══ CANDIDATE COUNT BY SHOT TYPE ═══
# Hero shots (face-critical) get 3 candidates.
# Production shots get 2.
# B-roll/establishing get 1 (no identity to verify).

HERO_SHOT_TYPES = {
    "close_up", "medium_close", "extreme_close_up",
    "reaction", "insert_face", "portrait",
}

PRODUCTION_SHOT_TYPES = {
    "medium", "medium_full", "ots", "over_the_shoulder",
    "two_shot", "group",
}

BROLL_SHOT_TYPES = {
    "establishing", "wide", "insert", "b_roll", "broll",
    "detail", "environmental", "closing",
}


def get_candidate_count(shot: dict) -> int:
    """Determine how many candidates to generate for a shot.

    Args:
        shot: Shot dict from shot_plan

    Returns:
        Number of candidates (1, 2, or 3)
    """
    shot_type = (shot.get("shot_type") or "").lower().strip()
    characters = shot.get("characters", []) or []
    has_dialogue = bool(shot.get("dialogue_text"))

    # No characters = no identity to verify = 1 candidate
    if not characters:
        return 1

    # Hero shots: face-critical, need maximum candidate diversity
    if shot_type in HERO_SHOT_TYPES:
        return 3

    # Dialogue shots get hero treatment regardless of shot type
    if has_dialogue and len(characters) >= 1:
        return 3

    # Production shots: moderate candidate diversity
    if shot_type in PRODUCTION_SHOT_TYPES:
        return 2

    # B-roll / establishing: no identity concern
    if shot_type in BROLL_SHOT_TYPES:
        return 1

    # Default: if characters present, at least 2
    if characters:
        return 2

    return 1


@dataclass
class CandidateResult:
    """Result of multi-candidate selection."""
    shot_id: str
    candidates_generated: int = 1
    candidates_scored: int = 0
    winner_index: int = 0
    winner_score: float = 0.0
    all_scores: List[Dict] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "candidates_generated": self.candidates_generated,
            "candidates_scored": self.candidates_scored,
            "winner_index": self.winner_index,
            "winner_score": round(self.winner_score, 3),
            "all_scores": self.all_scores,
            "diagnostics": self.diagnostics,
        }


def select_best_candidate(
    shot_id: str,
    candidate_paths: List[str],
    shot: dict,
    cast_map: dict,
    vision_service=None,
) -> CandidateResult:
    """Score all candidate frames and select the best one.

    Args:
        shot_id: Shot identifier
        candidate_paths: List of file paths to candidate frames
        shot: Shot dict from shot_plan
        cast_map: Character appearance data
        vision_service: Optional VisionService for Florence-2 captioning

    Returns:
        CandidateResult with winner index and all scores
    """
    result = CandidateResult(
        shot_id=shot_id,
        candidates_generated=len(candidate_paths),
    )

    if not candidate_paths:
        result.diagnostics.append("No candidates to score")
        return result

    if len(candidate_paths) == 1:
        # Single candidate — no selection needed, but still score for telemetry
        result.winner_index = 0
        try:
            from tools.vision_judge import judge_frame
            v = judge_frame(shot_id, candidate_paths[0], shot, cast_map, vision_service=vision_service)
            result.winner_score = sum(v.identity_scores.values()) / max(len(v.identity_scores), 1)
            result.all_scores.append({
                "index": 0,
                "score": round(result.winner_score, 3),
                "verdict": v.verdict,
                "identity_scores": v.identity_scores,
            })
            result.candidates_scored = 1
        except Exception as e:
            result.diagnostics.append(f"Scoring failed: {e}")
        return result

    # Multiple candidates — score each and pick best
    scores = []
    for i, path in enumerate(candidate_paths):
        try:
            from tools.vision_judge import judge_frame
            v = judge_frame(shot_id, path, shot, cast_map, vision_service=vision_service)
            avg_identity = sum(v.identity_scores.values()) / max(len(v.identity_scores), 1)

            # Composite score: identity (70%) + face_count_ok (30%)
            face_bonus = 0.3 if v.face_count_ok else 0.0
            composite = (avg_identity * 0.7) + face_bonus

            entry = {
                "index": i,
                "score": round(composite, 3),
                "identity_avg": round(avg_identity, 3),
                "verdict": v.verdict,
                "identity_scores": v.identity_scores,
                "face_count_ok": v.face_count_ok,
                "caption_preview": v.caption[:100],
            }
            scores.append(entry)
            result.candidates_scored += 1
            logger.info(
                f"[SELECTOR] {shot_id} candidate {i}: "
                f"composite={composite:.3f} identity={avg_identity:.3f} "
                f"faces={'OK' if v.face_count_ok else 'MISMATCH'}"
            )
        except Exception as e:
            scores.append({"index": i, "score": 0.0, "error": str(e)})
            result.diagnostics.append(f"Candidate {i} scoring failed: {e}")

    result.all_scores = scores

    if scores:
        best = max(scores, key=lambda s: s.get("score", 0))
        result.winner_index = best["index"]
        result.winner_score = best.get("score", 0)
        result.diagnostics.append(
            f"Selected candidate {best['index']} with score {best.get('score', 0):.3f}"
        )
    else:
        result.diagnostics.append("No candidates could be scored — using first")

    return result


# ═══ SELF-TEST ═══

if __name__ == "__main__":
    print("=== Multi-Candidate Selector Self-Test ===\n")

    # Test candidate count determination
    test_shots = [
        ({"shot_type": "close_up", "characters": ["THOMAS"], "dialogue_text": "Hello"}, 3),
        ({"shot_type": "medium_close", "characters": ["ELEANOR"]}, 3),
        ({"shot_type": "ots", "characters": ["THOMAS", "ELEANOR"], "dialogue_text": "Yes"}, 3),
        ({"shot_type": "medium", "characters": ["NADIA"]}, 2),
        ({"shot_type": "two_shot", "characters": ["THOMAS", "ELEANOR"]}, 2),
        ({"shot_type": "establishing", "characters": []}, 1),
        ({"shot_type": "b_roll"}, 1),
        ({"shot_type": "wide", "characters": ["THOMAS"], "dialogue_text": "Speak"}, 3),  # dialogue boost
    ]

    all_pass = True
    for shot, expected in test_shots:
        actual = get_candidate_count(shot)
        status = "PASS" if actual == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {shot.get('shot_type', '?'):20s} chars={len(shot.get('characters', []))} "
              f"dial={'Y' if shot.get('dialogue_text') else 'N'} → {actual} (expected {expected})")

    print(f"\n{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
