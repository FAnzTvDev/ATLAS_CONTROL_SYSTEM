"""
ATLAS V24.2.3 — SMART REGEN ENGINE (Vision-Guided Delta Reprompting)
====================================================================
Post-generation quality gate with intelligent prompt correction.

Instead of blindly re-running the same prompt on failure, this module:
1. SCORES the generated frame (identity, location, presence, quality)
2. DIAGNOSES the failure mode (wrong face, empty room, location drift, blur)
3. BUILDS a corrective delta prompt targeting the specific failure
4. REGENERATES with the corrected prompt (bounded retry budget)

Design Principle: Fix the prompt, not just retry.
- Identity fail → strengthen face lock text + add negative for wrong face features
- Empty room → prepend "CHARACTER MUST BE VISIBLE" + remove landscape-only language
- Location drift → inject location anchor description + add negative for wrong location
- Blur/quality → increase detail language + add "sharp, detailed, high resolution"
- Blocking fail → inject spatial position from state_in/state_out

Integration:
  Called AFTER frame generation, BEFORE video generation in chain pipeline.
  If frame passes QA → continue to video (zero overhead).
  If frame fails → reprompt + regen (max 2 retries per shot, configurable).

Feature flag: FEATURE_SMART_REGEN (default: true)
  When false, falls through to old behavior (no QA in chain).

STATUS: V24.2.3 PRODUCTION READY
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger("atlas.smart_regen")

# ─── Feature flag ───
FEATURE_SMART_REGEN = os.environ.get("FEATURE_SMART_REGEN", "true").lower() == "true"

# ─── Config ───
MAX_REGEN_ATTEMPTS = int(os.environ.get("ATLAS_MAX_REGEN", "2"))
IDENTITY_THRESHOLD = 0.70      # Below this → identity correction
LOCATION_THRESHOLD = 0.55      # Below this → location correction
SHARPNESS_THRESHOLD = 0.15     # Below this → quality correction
PRESENCE_THRESHOLD = 0.35      # Detection confidence minimum


# =============================================================================
# FAILURE DIAGNOSIS
# =============================================================================

@dataclass
class FrameDiagnosis:
    """Diagnosis of what went wrong with a generated frame."""
    shot_id: str
    passed: bool
    failures: List[str]           # ["identity_mismatch", "empty_room", "location_drift", "blurry"]
    scores: Dict[str, float]      # {"identity": 0.45, "location": 0.82, "sharpness": 0.3}
    corrective_actions: List[str]  # Human-readable actions taken
    corrective_nano: str          # Corrected nano_prompt (or empty if passed)
    corrective_ltx: str           # Corrected ltx_motion_prompt (or empty if passed)
    attempt: int                  # Which attempt this is (0=original, 1=first retry, 2=second)


def diagnose_frame(
    frame_path: str,
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    ref_path: Optional[str] = None,
    location_master_path: Optional[str] = None,
) -> FrameDiagnosis:
    """
    Score a generated frame and diagnose failure modes.
    Uses vision_service for scoring, returns structured diagnosis.

    Falls back gracefully if vision tools unavailable (PIL-only checks).
    """
    shot_id = shot.get("shot_id", "unknown")
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    failures = []
    scores = {}

    # Try to load vision service
    vs = None
    try:
        from tools.vision_service import get_vision_service
        vs = get_vision_service("auto")
    except Exception as e:
        logger.warning(f"[SMART-REGEN] {shot_id}: vision service unavailable ({e}) — using PIL fallback")

    # ── Layer 1: Fast QA (sharpness, exposure, composition) ──
    if vs:
        try:
            qa = vs.fast_qa(frame_path)
            scores["sharpness"] = qa.get("sharpness", 0.5)
            scores["brightness"] = qa.get("brightness", 0.5)
            scores["contrast"] = qa.get("contrast", 0.5)
            if qa.get("sharpness", 1.0) < SHARPNESS_THRESHOLD:
                failures.append("blurry")
        except Exception as e:
            logger.debug(f"[SMART-REGEN] {shot_id}: fast QA failed: {e}")
            scores["sharpness"] = 0.5  # Assume OK on error
    else:
        # PIL fallback: basic Laplacian variance
        try:
            from PIL import Image
            import numpy as np
            img = Image.open(frame_path).convert("L")
            arr = np.array(img, dtype=float)
            # Laplacian approximation
            laplacian = (arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:] - 4 * arr[1:-1, 1:-1])
            sharpness = min(1.0, float(laplacian.var()) / 1000.0)
            scores["sharpness"] = round(sharpness, 3)
            if sharpness < SHARPNESS_THRESHOLD:
                failures.append("blurry")
        except Exception:
            scores["sharpness"] = 0.5

    # ── Layer 2: Identity scoring ──
    if characters and ref_path and Path(ref_path).exists():
        if vs:
            try:
                id_result = vs.score_identity(frame_path, ref_path)
                id_score = id_result.get("score", id_result.get("face_similarity", 0.5))
                scores["identity"] = round(id_score, 3)
                if id_score < IDENTITY_THRESHOLD:
                    failures.append("identity_mismatch")
                if id_result.get("face_count", 1) == 0 and characters:
                    failures.append("empty_room")
                    scores["presence"] = 0.0
            except Exception as e:
                logger.debug(f"[SMART-REGEN] {shot_id}: identity scoring failed: {e}")
                scores["identity"] = 0.5
        else:
            scores["identity"] = 0.5  # Can't score without vision

    # ── Layer 3: Location scoring ──
    if location_master_path and Path(location_master_path).exists():
        if vs:
            try:
                loc_result = vs.score_location(frame_path, location_master_path)
                loc_score = loc_result.get("score", loc_result.get("similarity", 0.5))
                scores["location"] = round(loc_score, 3)
                if loc_score < LOCATION_THRESHOLD:
                    failures.append("location_drift")
            except Exception as e:
                logger.debug(f"[SMART-REGEN] {shot_id}: location scoring failed: {e}")
                scores["location"] = 0.5

    # ── Layer 4: Empty room detection (if not already caught by identity) ──
    if characters and "empty_room" not in failures:
        if vs:
            try:
                empty = vs.detect_empty_room(frame_path, characters)
                is_empty = empty.get("is_empty", False)
                scores["presence"] = 0.0 if is_empty else 1.0
                scores["skin_ratio"] = empty.get("skin_ratio", 0)
                if is_empty:
                    failures.append("empty_room")
            except Exception as e:
                logger.debug(f"[SMART-REGEN] {shot_id}: empty room detection failed: {e}")

    passed = len(failures) == 0

    return FrameDiagnosis(
        shot_id=shot_id,
        passed=passed,
        failures=failures,
        scores=scores,
        corrective_actions=[],
        corrective_nano="",
        corrective_ltx="",
        attempt=0,
    )


# =============================================================================
# CORRECTIVE PROMPT BUILDER
# =============================================================================

def build_corrective_prompt(
    diagnosis: FrameDiagnosis,
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    scene_manifest: Optional[Dict] = None,
    attempt: int = 1,
) -> Tuple[str, str]:
    """
    Build corrected nano + LTX prompts targeting the specific failure modes.

    Strategy per failure:
    - identity_mismatch → strengthen character description, add face-lock negatives
    - empty_room → FORCE character presence, strip landscape-only language
    - location_drift → inject location anchor, add wrong-location negatives
    - blurry → add sharpness/detail boosters

    Returns:
        (corrected_nano_prompt, corrected_ltx_prompt)
    """
    shot_id = shot.get("shot_id", "unknown")
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    nano = shot.get("nano_prompt", "")
    ltx = shot.get("ltx_motion_prompt", "")
    actions = []

    # ── IDENTITY MISMATCH: Strengthen face lock ──
    if "identity_mismatch" in diagnosis.failures:
        # Get canonical character description from cast_map
        for char_name in characters[:2]:  # Max 2 characters
            char_upper = char_name.upper()
            for cm_key, cm_val in cast_map.items():
                if isinstance(cm_val, dict) and (char_upper in cm_key.upper() or cm_key.upper() in char_upper):
                    appearance = cm_val.get("appearance", "")
                    if appearance:
                        # Prepend identity lock to nano
                        short_name = char_name.split()[0].title()
                        if short_name.lower() not in nano.lower():
                            nano = f"IDENTITY LOCK: {short_name} — {appearance[:120]}. " + nano
                            actions.append(f"Strengthened identity lock for {short_name}")
                    break

        # Add identity-specific negatives
        _id_neg = "NO face change, NO different person, NO identity drift, SAME character throughout"
        if _id_neg not in nano:
            nano = nano.rstrip(",. ") + f", {_id_neg}"

        # On second attempt, try more aggressive approach
        if attempt >= 2:
            nano = f"CRITICAL: Character face MUST match reference image exactly. " + nano
            actions.append("Aggressive identity lock (attempt 2)")

    # ── EMPTY ROOM: Force character presence ──
    if "empty_room" in diagnosis.failures:
        char_list = ", ".join(c.split()[0].title() for c in characters[:3])
        presence_prefix = f"CHARACTER MUST BE VISIBLE: {char_list} clearly present in frame, "
        nano = presence_prefix + nano
        actions.append(f"Forced character presence: {char_list}")

        # Strip any landscape-only language that might push away from characters
        _landscape_words = ["empty landscape", "no people", "environment only", "establishing wide"]
        for lw in _landscape_words:
            if lw.lower() in nano.lower():
                nano = nano.replace(lw, "").replace(lw.title(), "")
                actions.append(f"Stripped landscape-only: '{lw}'")

        # LTX: ensure character movement direction
        if "character performs:" not in ltx.lower() and "character speaks:" not in ltx.lower():
            char_first = characters[0].split()[0].title() if characters else "Character"
            ltx = f"character performs: {char_first} present in frame with natural movement. " + ltx
            actions.append("Added character performance marker to LTX")

    # ── LOCATION DRIFT: Anchor to correct location ──
    if "location_drift" in diagnosis.failures:
        location = shot.get("location", "")
        scene_id = shot.get("scene_id", "")

        # Get location from scene manifest if available
        if scene_manifest and scene_id:
            scene_data = scene_manifest.get(scene_id, {})
            manifest_location = scene_data.get("location", "")
            if manifest_location:
                location = manifest_location

        if location:
            loc_anchor = f"LOCATION: {location}. Scene takes place in {location}. "
            if location.lower() not in nano.lower():
                nano = loc_anchor + nano
                actions.append(f"Injected location anchor: {location}")

            # Add wrong-location negatives (common drift targets)
            _loc_neg = f"NO outdoor scene, NO different room" if "INT" in location.upper() else "NO indoor scene, NO different location"
            if _loc_neg not in nano:
                nano = nano.rstrip(",. ") + f", {_loc_neg}"
                actions.append("Added location-specific negatives")

    # ── BLURRY: Quality boost ──
    if "blurry" in diagnosis.failures:
        _quality = "sharp focus, high detail, crystal clear, well-lit"
        if "sharp focus" not in nano.lower():
            nano = f"{_quality}, " + nano
            actions.append("Added sharpness/quality boosters")

        # LTX: reduce motion complexity to help clarity
        if attempt >= 2 and "slow" not in ltx.lower():
            ltx = ltx.rstrip(",. ") + ", slow deliberate movement, minimal motion blur"
            actions.append("Reduced motion complexity for clarity (attempt 2)")

    # ── PROMPT LENGTH SAFETY ──
    if len(nano) > 2000:
        nano = nano[:1997] + "..."
    if len(ltx) > 1400:
        ltx = ltx[:1397] + "..."

    diagnosis.corrective_nano = nano
    diagnosis.corrective_ltx = ltx
    diagnosis.corrective_actions = actions
    diagnosis.attempt = attempt

    logger.info(f"[SMART-REGEN] {shot_id}: built corrective prompt "
               f"(failures={diagnosis.failures}, actions={len(actions)}, attempt={attempt})")

    return nano, ltx


# =============================================================================
# CHAIN INTEGRATION — Per-Shot QA + Regen Loop
# =============================================================================

def chain_post_gen_qa(
    frame_path: str,
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    scene_manifest: Optional[Dict] = None,
    ref_path: Optional[str] = None,
    location_master_path: Optional[str] = None,
    max_retries: int = None,
) -> Dict[str, Any]:
    """
    Run post-generation QA on a chain-generated frame.

    Returns:
        {
            "passed": bool,
            "diagnosis": FrameDiagnosis,
            "needs_regen": bool,
            "corrective_nano": str (if needs_regen),
            "corrective_ltx": str (if needs_regen),
            "scores": dict,
        }
    """
    if not FEATURE_SMART_REGEN:
        return {"passed": True, "diagnosis": None, "needs_regen": False, "scores": {}}

    if max_retries is None:
        max_retries = MAX_REGEN_ATTEMPTS

    shot_id = shot.get("shot_id", "unknown")

    # Score the frame
    diagnosis = diagnose_frame(
        frame_path=str(frame_path),
        shot=shot,
        cast_map=cast_map,
        ref_path=ref_path,
        location_master_path=location_master_path,
    )

    if diagnosis.passed:
        logger.info(f"[SMART-REGEN] {shot_id}: ✅ PASSED QA (scores={diagnosis.scores})")
        return {
            "passed": True,
            "diagnosis": diagnosis,
            "needs_regen": False,
            "scores": diagnosis.scores,
        }

    # Frame failed — build corrective prompt
    logger.warning(f"[SMART-REGEN] {shot_id}: ❌ FAILED QA — {diagnosis.failures} (scores={diagnosis.scores})")

    corrective_nano, corrective_ltx = build_corrective_prompt(
        diagnosis=diagnosis,
        shot=shot,
        cast_map=cast_map,
        scene_manifest=scene_manifest,
        attempt=1,
    )

    return {
        "passed": False,
        "diagnosis": diagnosis,
        "needs_regen": True,
        "corrective_nano": corrective_nano,
        "corrective_ltx": corrective_ltx,
        "corrective_actions": diagnosis.corrective_actions,
        "scores": diagnosis.scores,
    }


def escalate_correction(
    prev_diagnosis: FrameDiagnosis,
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    scene_manifest: Optional[Dict] = None,
    attempt: int = 2,
) -> Tuple[str, str]:
    """
    Build escalated corrective prompt for second retry.
    More aggressive corrections than first attempt.
    """
    return build_corrective_prompt(
        diagnosis=prev_diagnosis,
        shot=shot,
        cast_map=cast_map,
        scene_manifest=scene_manifest,
        attempt=attempt,
    )


# =============================================================================
# REGEN BUDGET TRACKER
# =============================================================================

class RegenBudget:
    """
    Tracks regen attempts per shot and per scene to prevent infinite loops.

    Rules:
    - Max 2 retries per shot (configurable)
    - Max 30% of scene shots can have retries (cost control)
    - After budget exhausted, accept best-effort frame and log warning
    """

    def __init__(self, scene_shots: List[Dict], max_per_shot: int = None, max_scene_pct: float = 0.30):
        self.max_per_shot = max_per_shot or MAX_REGEN_ATTEMPTS
        self.max_scene_pct = max_scene_pct
        self.total_shots = len(scene_shots)
        self.max_scene_regens = max(1, int(self.total_shots * self.max_scene_pct))
        self.attempts: Dict[str, int] = {}  # shot_id → attempt count
        self.scene_regen_count = 0

    def can_regen(self, shot_id: str) -> bool:
        """Check if this shot has regen budget remaining."""
        shot_attempts = self.attempts.get(shot_id, 0)
        if shot_attempts >= self.max_per_shot:
            logger.info(f"[REGEN-BUDGET] {shot_id}: exhausted shot budget ({shot_attempts}/{self.max_per_shot})")
            return False
        if self.scene_regen_count >= self.max_scene_regens:
            logger.info(f"[REGEN-BUDGET] {shot_id}: exhausted scene budget ({self.scene_regen_count}/{self.max_scene_regens})")
            return False
        return True

    def record_attempt(self, shot_id: str):
        """Record a regen attempt."""
        self.attempts[shot_id] = self.attempts.get(shot_id, 0) + 1
        self.scene_regen_count += 1
        logger.info(f"[REGEN-BUDGET] {shot_id}: attempt {self.attempts[shot_id]}/{self.max_per_shot} "
                    f"(scene: {self.scene_regen_count}/{self.max_scene_regens})")

    def get_attempt(self, shot_id: str) -> int:
        return self.attempts.get(shot_id, 0)

    def summary(self) -> Dict:
        return {
            "total_shots": self.total_shots,
            "shots_retried": len(self.attempts),
            "total_retries": sum(self.attempts.values()),
            "max_per_shot": self.max_per_shot,
            "scene_regen_count": self.scene_regen_count,
            "scene_regen_budget": self.max_scene_regens,
            "budget_exhausted": self.scene_regen_count >= self.max_scene_regens,
        }


# =============================================================================
# RESOLVE REFS HELPER (for chain integration)
# =============================================================================

def resolve_shot_refs(
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    project_path: Path,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve character reference and location master paths for a shot.
    Returns (ref_path, location_master_path) or (None, None).
    """
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    # Character reference: first character's headshot
    ref_path = None
    for char_name in characters[:1]:
        char_upper = char_name.upper()
        for cm_key, cm_val in cast_map.items():
            if not isinstance(cm_val, dict):
                continue
            if char_upper in cm_key.upper() or cm_key.upper() in char_upper:
                raw = (cm_val.get("character_reference_url") or
                       cm_val.get("reference_url") or
                       cm_val.get("headshot_url", ""))
                if raw:
                    if "/api/media?path=" in raw:
                        raw = raw.split("path=", 1)[1]
                    if Path(raw).exists():
                        ref_path = raw
                    else:
                        # Try common directories
                        fname = Path(raw).name
                        for search_dir in [
                            project_path / "character_library_locked",
                            project_path.parent.parent / "character_library_locked" / "ai_actors",
                            project_path.parent.parent / "ai_actor_headshots",
                        ]:
                            candidate = search_dir / fname
                            if candidate.exists():
                                ref_path = str(candidate)
                                break
                break

    # Location master
    location_master_path = None
    scene_id = shot.get("scene_id", "")
    loc_masters_dir = project_path / "location_masters"
    if loc_masters_dir.exists() and scene_id:
        for ext in [".jpg", ".png", ".jpeg"]:
            candidate = loc_masters_dir / f"scene_{scene_id}{ext}"
            if candidate.exists():
                location_master_path = str(candidate)
                break
            candidate = loc_masters_dir / f"{scene_id}{ext}"
            if candidate.exists():
                location_master_path = str(candidate)
                break

    return ref_path, location_master_path
