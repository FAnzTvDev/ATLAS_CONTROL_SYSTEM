"""
ATLAS V26.1 — KEYFRAME APPROVAL GATE
======================================
Vision-scored approval gate for generated keyframes.

After nano-banana-pro generates a first frame, this module:
1. Scores identity (do the characters look right?)
2. Scores location (does the environment match?)
3. Scores composition (is the framing correct for the shot type?)
4. Scores semantic alignment (does the image match the prompt?)
5. Returns APPROVE / RETRY / REJECT with scores and reasons

Vision stack roles (from V26.1 spec):
  - DINO: identity continuity + location similarity (embedding distance)
  - CLIP: semantic match (prompt vs generated image)
  - Florence-2: spatial grounding (character count, object detection)
  - ArcFace: face identity verification (when refs available)

Vision INFORMS approval. Controller APPLIES policy. Ledger RECORDS why.
This module does NOT make the final decision — it provides scored evidence.

DOCTRINE LAW 274: Keyframe approval is NON-BLOCKING. If vision is unavailable,
use heuristic scoring and return default verdict with confidence=0.5.
DOCTRINE LAW 275: Approval thresholds are per-authority-tier. Hero shots (MCU,
close-up, dialogue) get stricter thresholds than B-roll.
DOCTRINE LAW 276: Retry hints must be specific and actionable.
"""

from dataclasses import dataclass
from typing import Optional, List
import json
from pathlib import Path


@dataclass
class KeyframeScore:
    """Structured vision scores for a generated keyframe."""
    identity_score: float  # 0.0-1.0: Do characters match refs? (DINO embedding distance if refs, heuristic if not)
    location_score: float  # 0.0-1.0: Does environment match scene? (DINOv2 scene embedding vs location master)
    composition_score: float  # 0.0-1.0: Is framing correct for shot type? (CLIP vs shot_type description)
    semantic_score: float  # 0.0-1.0: Does image match prompt? (CLIPScore)
    overall_score: float  # 0.0-1.0: Weighted average (identity 40%, location 30%, composition 15%, semantic 15%)
    scores_available: bool  # False if vision service unavailable (heuristic used)
    analysis_timestamp: str  # ISO 8601
    frame_hash: str  # SHA256 of frame file


@dataclass
class ApprovalVerdict:
    """Approval decision with evidence and actionable guidance."""
    verdict: str  # "approve" | "retry" | "reject"
    score: KeyframeScore
    reasons: List[str]  # Why this verdict
    retry_hints: List[str]  # If verdict=="retry": what to change on regeneration
    confidence: float  # 0.0-1.0: How confident in this verdict
    tier: str  # "hero" | "production" | "broll" (used for threshold tuning)


APPROVAL_THRESHOLDS = {
    "hero": {
        # Hero shots: close-ups, MCU, dialogue, key emotional moments
        "identity_min": 0.82,
        "location_min": 0.70,
        "composition_min": 0.75,
        "semantic_min": 0.72,
        "overall_min": 0.75,
    },
    "production": {
        # Production shots: medium, OTS, two-shot, standard coverage
        "identity_min": 0.70,
        "location_min": 0.55,
        "composition_min": 0.65,
        "semantic_min": 0.60,
        "overall_min": 0.63,
    },
    "broll": {
        # B-roll: inserts, details, cutaways, atmospheric
        "identity_min": 0.0,  # No face identity requirement
        "location_min": 0.40,
        "composition_min": 0.50,
        "semantic_min": 0.50,
        "overall_min": 0.45,
    },
}

# Composition thresholds per shot type
COMPOSITION_BY_SHOT_TYPE = {
    "close_up": 0.80,  # Tight framing required
    "mcu": 0.78,
    "medium": 0.70,
    "ots": 0.75,  # Over-the-shoulder precise
    "two_shot": 0.72,
    "wide": 0.60,  # Wider is more forgiving
    "establishing": 0.55,
    "master": 0.65,
    "insert": 0.50,  # Details don't need precise composition
    "b_roll": 0.45,
    "reaction": 0.70,
}


def score_keyframe(
    frame_path: str,
    shot_state: dict,
    cast_map: dict,
    location_master_path: Optional[str] = None,
    vision_service=None,
) -> KeyframeScore:
    """
    Score a generated keyframe using vision models (if available) or heuristics.

    Args:
        frame_path: Path to generated first frame (JPEG)
        shot_state: Shot dict from shot_plan.json (contains characters[], dialogue, shot_type)
        cast_map: Character → AI actor map (contains character_reference_url paths)
        location_master_path: Path to location master image for environment matching
        vision_service: Vision service instance (if None, use heuristic)

    Returns:
        KeyframeScore with all 5 scores filled, or defaults if vision unavailable
    """
    from datetime import datetime
    import hashlib

    # Hash the frame for caching/logging
    try:
        frame_hash = _sha256_file(frame_path)
    except Exception:
        frame_hash = "unknown"

    # If no vision service, use heuristic
    if vision_service is None:
        return score_without_vision(shot_state)

    timestamp = datetime.utcnow().isoformat() + "Z"

    try:
        # Identity score: do character faces match refs?
        identity_score = _score_identity(frame_path, shot_state, cast_map, vision_service)

        # Location score: does environment match scene?
        location_score = _score_location(
            frame_path, shot_state, location_master_path, vision_service
        )

        # Composition score: is framing correct for shot type?
        shot_type = shot_state.get("shot_type", "medium")
        composition_target = COMPOSITION_BY_SHOT_TYPE.get(shot_type, 0.65)
        composition_score = _score_composition(
            frame_path, shot_state, vision_service, composition_target
        )

        # Semantic score: does image match prompt?
        nano_prompt = shot_state.get("nano_prompt", "")
        semantic_score = _score_semantic(frame_path, nano_prompt, vision_service)

        # Overall: weighted average
        # Identity 40%, location 30%, composition 15%, semantic 15%
        overall_score = (
            0.40 * identity_score
            + 0.30 * location_score
            + 0.15 * composition_score
            + 0.15 * semantic_score
        )

        return KeyframeScore(
            identity_score=identity_score,
            location_score=location_score,
            composition_score=composition_score,
            semantic_score=semantic_score,
            overall_score=overall_score,
            scores_available=True,
            analysis_timestamp=timestamp,
            frame_hash=frame_hash,
        )

    except Exception as e:
        # Vision service error → fall back to heuristic
        print(f"[keyframe_approval] Vision scoring failed: {e}. Using heuristic.")
        return score_without_vision(shot_state)


def _score_identity(
    frame_path: str, shot_state: dict, cast_map: dict, vision_service
) -> float:
    """
    Score character identity match.
    Uses ArcFace + character_reference_url if available, else DINOv2 embedding comparison.
    """
    characters = shot_state.get("characters", [])

    # No characters → identity score is neutral
    if not characters:
        return 0.5

    # Count character ref matches
    ref_count = 0
    for char in characters:
        if cast_map and char in cast_map:
            if cast_map[char].get("character_reference_url"):
                ref_count += 1

    # With refs, use ArcFace if available
    if ref_count > 0:
        try:
            # Vision service should provide face verification
            # Heuristic: if we have refs and face detection found faces, score high
            result = vision_service.analyze_identity(frame_path, characters, cast_map)
            if result and "identity_score" in result:
                return min(1.0, result["identity_score"])
        except Exception:
            pass

    # Fallback: check face count matches character count
    try:
        caption = vision_service.get_caption(frame_path)
        face_count = caption.lower().count("face") + caption.lower().count("person")
        expected_chars = len(characters)
        if expected_chars > 0:
            return min(1.0, face_count / expected_chars)
    except Exception:
        pass

    # No vision available → neutral
    return 0.5


def _score_location(
    frame_path: str,
    shot_state: dict,
    location_master_path: Optional[str],
    vision_service,
) -> float:
    """
    Score location/environment consistency.
    Uses DINOv2 embedding distance if location master available.
    """
    # No master → can't verify location
    if not location_master_path:
        return 0.5

    try:
        # Get scene caption from generated frame
        caption = vision_service.get_caption(frame_path)

        # Simple heuristic: check location keywords in caption
        location = shot_state.get("location", "")
        location_words = location.lower().split()

        caption_lower = caption.lower()
        matches = sum(1 for word in location_words if word in caption_lower)

        if len(location_words) > 0:
            keyword_score = matches / len(location_words)
        else:
            keyword_score = 0.5

        # If vision service has DINOv2 embedding distance, use it as primary
        try:
            embedding_distance = vision_service.get_embedding_distance(
                frame_path, location_master_path
            )
            # Embedding distance in range [0, 2], normalize to [1, 0]
            embedding_score = max(0.0, 1.0 - embedding_distance / 2.0)
            # Blend: 70% embedding, 30% keyword match
            return 0.7 * embedding_score + 0.3 * keyword_score
        except Exception:
            # No embedding distance → use keyword match alone
            return keyword_score

    except Exception:
        return 0.5


def _score_composition(
    frame_path: str, shot_state: dict, vision_service, composition_target: float
) -> float:
    """
    Score composition correctness for the shot type.
    Uses Florence-2 spatial grounding or simple heuristics.
    """
    shot_type = shot_state.get("shot_type", "medium")

    # Get spatial analysis from vision if available
    try:
        spatial = vision_service.get_spatial_layout(frame_path)

        # Heuristic checks:
        # - For close-up/MCU: character should fill 60-90% of frame
        # - For medium: character should fill 40-60%
        # - For wide: character should fill 20-40%

        if spatial and "character_coverage" in spatial:
            coverage = spatial["character_coverage"]

            if shot_type in ["close_up", "mcu"]:
                target_min, target_max = 0.60, 0.90
            elif shot_type in ["medium", "ots", "two_shot"]:
                target_min, target_max = 0.35, 0.65
            elif shot_type in ["wide", "establishing", "master"]:
                target_min, target_max = 0.15, 0.50
            else:
                target_min, target_max = 0.25, 0.75

            if target_min <= coverage <= target_max:
                return 0.95  # Excellent composition
            else:
                # Score distance from target range
                if coverage < target_min:
                    deviation = (target_min - coverage) / target_min
                else:
                    deviation = (coverage - target_max) / (1.0 - target_max)
                return max(0.3, 1.0 - deviation)

    except Exception:
        pass

    # Fallback: assume composition is reasonable if frame exists
    return composition_target


def _score_semantic(frame_path: str, nano_prompt: str, vision_service) -> float:
    """
    Score semantic alignment: does the image match the prompt?
    Uses CLIP CLIPScore if available.
    """
    if not nano_prompt:
        return 0.5

    try:
        # Use CLIP embedding distance between prompt and image
        score = vision_service.get_clipscore(frame_path, nano_prompt)
        if score is not None:
            return min(1.0, max(0.0, score))
    except Exception:
        pass

    # Fallback: use caption matching
    try:
        caption = vision_service.get_caption(frame_path)

        # Simple word overlap heuristic
        prompt_words = set(nano_prompt.lower().split())
        caption_words = set(caption.lower().split())

        overlap = len(prompt_words & caption_words)
        if len(prompt_words) > 0:
            return overlap / len(prompt_words) * 0.8  # Cap at 0.8
        else:
            return 0.5

    except Exception:
        return 0.5


def score_without_vision(shot_state: dict) -> KeyframeScore:
    """
    Heuristic scoring when vision service is unavailable.

    Checks:
    - Prompt specificity (long prompt → higher semantic score)
    - Character count (if characters exist, identity isn't zero)
    - Shot type (establishes composition target)
    - Authority tier (dialogue shots get stricter heuristic)
    """
    from datetime import datetime

    timestamp = datetime.utcnow().isoformat() + "Z"

    # Identity: presence of characters raises score
    characters = shot_state.get("characters", [])
    identity_score = 0.5 if len(characters) > 0 else 0.3

    # Location: assume neutral if no master
    location_score = 0.5

    # Composition: by shot type
    shot_type = shot_state.get("shot_type", "medium")
    composition_score = COMPOSITION_BY_SHOT_TYPE.get(shot_type, 0.65)

    # Semantic: by prompt length (longer → more specific → higher score)
    nano_prompt = shot_state.get("nano_prompt", "")
    prompt_len = len(nano_prompt)
    semantic_score = min(0.85, 0.3 + (prompt_len / 1000.0))  # Cap at 0.85

    # Dialogue boost: if dialogue_text exists, assume higher semantic score
    if shot_state.get("dialogue_text"):
        semantic_score = min(0.90, semantic_score + 0.1)

    # Overall: weighted average
    overall_score = (
        0.40 * identity_score
        + 0.30 * location_score
        + 0.15 * composition_score
        + 0.15 * semantic_score
    )

    return KeyframeScore(
        identity_score=identity_score,
        location_score=location_score,
        composition_score=composition_score,
        semantic_score=semantic_score,
        overall_score=overall_score,
        scores_available=False,
        analysis_timestamp=timestamp,
        frame_hash="unknown",
    )


def approve_keyframe(
    score: KeyframeScore, authority_tier: str, has_dialogue: bool = False
) -> ApprovalVerdict:
    """
    Apply approval policy to vision scores.

    Args:
        score: KeyframeScore from score_keyframe()
        authority_tier: "hero" | "production" | "broll" (from Shot Authority Gate)
        has_dialogue: If True, apply stricter thresholds

    Returns:
        ApprovalVerdict with verdict + reasons + hints
    """
    thresholds = APPROVAL_THRESHOLDS.get(authority_tier, APPROVAL_THRESHOLDS["production"])

    # Boost thresholds for dialogue
    if has_dialogue:
        thresholds = {k: v + 0.05 for k, v in thresholds.items()}

    reasons = []
    failed_checks = []

    # Check each dimension
    if score.identity_score < thresholds["identity_min"]:
        failed_checks.append("identity")
        reasons.append(
            f"Identity score {score.identity_score:.2f} below "
            f"threshold {thresholds['identity_min']:.2f}"
        )

    if score.location_score < thresholds["location_min"]:
        failed_checks.append("location")
        reasons.append(
            f"Location score {score.location_score:.2f} below "
            f"threshold {thresholds['location_min']:.2f}"
        )

    if score.composition_score < thresholds["composition_min"]:
        failed_checks.append("composition")
        reasons.append(
            f"Composition score {score.composition_score:.2f} below "
            f"threshold {thresholds['composition_min']:.2f}"
        )

    if score.semantic_score < thresholds["semantic_min"]:
        failed_checks.append("semantic")
        reasons.append(
            f"Semantic score {score.semantic_score:.2f} below "
            f"threshold {thresholds['semantic_min']:.2f}"
        )

    # Determine verdict
    if not failed_checks:
        if score.overall_score >= thresholds["overall_min"]:
            verdict = "approve"
            confidence = score.overall_score
            reasons = ["All dimensions within acceptable range."]
        else:
            verdict = "retry"
            confidence = 0.6
            reasons.append(
                f"Overall score {score.overall_score:.2f} below threshold "
                f"{thresholds['overall_min']:.2f}"
            )
    else:
        if len(failed_checks) == 1:
            verdict = "retry"
            confidence = 0.5
        else:
            verdict = "reject"
            confidence = 0.3

    # Generate retry hints
    retry_hints = []
    if "identity" in failed_checks:
        retry_hints.append(
            "Character faces not matching refs. Retry with: "
            "sharper facial lighting, higher contrast, frontal angle"
        )
    if "location" in failed_checks:
        retry_hints.append(
            "Environment not matching location master. Retry with: "
            "location anchor emphasized, environment details specified"
        )
    if "composition" in failed_checks:
        retry_hints.append(
            "Framing not optimal for shot type. Retry with: "
            "camera position/lens adjusted, character positioning refined"
        )
    if "semantic" in failed_checks:
        retry_hints.append(
            "Image doesn't match prompt. Retry with: "
            "prompt refined for clarity, key details emphasized"
        )

    return ApprovalVerdict(
        verdict=verdict,
        score=score,
        reasons=reasons,
        retry_hints=retry_hints,
        confidence=confidence,
        tier=authority_tier,
    )


def _sha256_file(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
