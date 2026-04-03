"""
ATLAS V24.2.4 — SHOT AUTHORITY CONTRACT (CORRECTED)
=====================================================
The AAA Pre-Generation Authority System.

Design Principle: DICTATE, don't react.
A real film production doesn't shoot first and check later.
The DP, director, script supervisor, and costume designer
all sign off BEFORE the camera rolls. This module enforces that.

WHAT CONTROLS AAA OUTPUT (in order of authority):
1. REFERENCE IMAGES — face lock, location lock, wardrobe lock (STRONGEST)
2. NEGATIVE CONSTRAINTS — what NOT to generate (second strongest)
3. COMPOSITION RULES — shot type → camera params → framing guide
4. TEXT PROMPT — scene action, emotion, blocking (weakest signal)

V24.2.4 CORRECTION — ACTUAL FAL API PARAMETERS:
The nano-banana-pro and LTX-2.3 APIs do NOT accept guidance_scale
or num_inference_steps. These were silently ignored. The actual
control levers available in 2026:

  nano-banana-pro (text-to-image):
    - prompt (str): The generation prompt
    - image_urls (list[str]): Reference images for edit mode (STRONGEST LEVER)
    - resolution (str): "1K" | "2K" | "4K" — quality/cost tradeoff
    - aspect_ratio (str): "16:9" etc
    - output_format (str): "jpeg" | "png"
    - seed (int): Reproducibility control
    - safety_tolerance (str): "1"-"6"

  LTX-2.3 image-to-video (fast):
    - prompt (str): Animation direction
    - image_url (str): Source frame
    - duration (int): 6|8|10|12|14|16|18|20 seconds
    - resolution (str): "1080p" | "1440p" | "2160p"
    - fps (int): 25 | 50
    - generate_audio (bool): Native audio generation

REAL AUTHORITY LEVERS (what actually changes output quality):
  1. REFERENCE IMAGE COUNT + ORDER — more refs = tighter identity lock
  2. RESOLUTION — 2K for hero shots, 1K for production, 1K for preview
  3. PROMPT SPECIFICITY — director-style framing, not keyword stuffing
  4. COMPOSITION PREFIX — shot-type-specific framing language
  5. NEGATIVE SUFFIX — shot-type-specific exclusions
  6. REF ORDERING — character refs FIRST (position 1+), location refs LAST
  7. SEED — lock seed for variant consistency when needed

STATUS: V24.2.4 PRODUCTION READY — CORRECTED TO ACTUAL API
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("atlas.shot_authority")


# =============================================================================
# SHOT TYPE AUTHORITY PROFILES
# =============================================================================

@dataclass
class AuthorityProfile:
    """Generation parameters dictated by shot type.

    V24.2.4: Parameters corrected to what FAL API actually accepts.
    guidance_scale and num_inference_steps REMOVED — API ignores them.
    Real levers: resolution, ref count, prompt specificity, composition.
    """
    resolution: str              # "1K" | "2K" | "4K" for nano, "1080p" | "1440p" for LTX
    ref_requirement: str         # "mandatory" | "required" | "optional" | "none"
    max_refs: int                # Maximum reference images to send (API limit: varies)
    max_prompt_length: int       # Prompt truncation per shot type
    composition_prefix: str      # Prepended to prompt — framing direction
    negative_suffix: str         # Appended to prompt — exclusions
    quality_tier: str            # "preview" | "production" | "hero"
    ltx_resolution: str          # "1080p" | "1440p" | "2160p" for video gen
    ltx_duration_override: Optional[int]  # Override LTX duration for this shot type (None = use plan duration)
    num_candidates: int = 1      # V26.2: How many FAL outputs to generate for selection (hero=3, production=1)


# Authority profiles indexed by shot type
AUTHORITY_PROFILES: Dict[str, AuthorityProfile] = {
    # Hero shots — maximum quality, strict ref adherence, 2K resolution
    "close_up": AuthorityProfile(
        resolution="2K", ref_requirement="mandatory", max_refs=3,
        max_prompt_length=800,
        composition_prefix="Extreme close-up, face filling frame, shallow depth of field, ",
        negative_suffix="NO wide angle, NO full body, NO background focus",
        quality_tier="hero",
        ltx_resolution="1080p", ltx_duration_override=None,
        num_candidates=3,  # V26.2: Hero shots generate 3 candidates for selection
    ),
    "MCU": AuthorityProfile(
        resolution="2K", ref_requirement="mandatory", max_refs=3,
        max_prompt_length=800,
        composition_prefix="Medium close-up, head and shoulders, intimate framing, ",
        negative_suffix="NO wide angle, NO full body",
        quality_tier="hero",
        ltx_resolution="1080p", ltx_duration_override=None,
        num_candidates=3,  # V26.2: Hero shots generate 3 candidates for selection
    ),
    "ECU": AuthorityProfile(
        resolution="2K", ref_requirement="mandatory", max_refs=2,
        max_prompt_length=600,
        composition_prefix="Extreme close-up, single feature detail, macro composition, ",
        negative_suffix="NO wide angle, NO full body, NO multiple subjects",
        quality_tier="hero",
        ltx_resolution="1080p", ltx_duration_override=None,
        num_candidates=3,  # V26.2: Hero shots generate 3 candidates for selection
    ),

    # V27: medium_close is hero — face identity is critical at this framing
    "medium_close": AuthorityProfile(
        resolution="2K", ref_requirement="mandatory", max_refs=3,
        max_prompt_length=900,
        composition_prefix="Medium close-up, head and shoulders, intimate framing, ",
        negative_suffix="NO wide angle, NO full body",
        quality_tier="hero",
        ltx_resolution="1080p", ltx_duration_override=None,
        num_candidates=3,
    ),

    # Production shots — balanced quality, 1K resolution
    "medium": AuthorityProfile(
        resolution="1K", ref_requirement="required", max_refs=4,
        max_prompt_length=1000,
        composition_prefix="Medium shot, waist-up framing, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),
    "OTS": AuthorityProfile(
        resolution="1K", ref_requirement="required", max_refs=4,
        max_prompt_length=1000,
        composition_prefix="Over-the-shoulder composition, foreground shoulder blur, focused on subject, ",
        negative_suffix="NO direct camera look from foreground character",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),
    "two_shot": AuthorityProfile(
        resolution="1K", ref_requirement="required", max_refs=5,
        max_prompt_length=1000,
        composition_prefix="Two-shot composition, both characters visible, balanced framing, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),
    "medium_wide": AuthorityProfile(
        resolution="1K", ref_requirement="required", max_refs=4,
        max_prompt_length=1200,
        composition_prefix="Medium wide shot, full body with environment context, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),

    # Establishing shots — creative freedom, fewer refs
    "wide": AuthorityProfile(
        resolution="1K", ref_requirement="optional", max_refs=2,
        max_prompt_length=1400,
        composition_prefix="Wide establishing shot, full environment visible, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),
    "establishing": AuthorityProfile(
        resolution="1K", ref_requirement="optional", max_refs=1,
        max_prompt_length=1400,
        composition_prefix="Establishing wide shot, location geography, atmospheric, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),
    "master": AuthorityProfile(
        resolution="1K", ref_requirement="optional", max_refs=2,
        max_prompt_length=1400,
        composition_prefix="Master shot, wide coverage, all blocking visible, ",
        negative_suffix="",
        quality_tier="production",
        ltx_resolution="1080p", ltx_duration_override=None,
    ),

    # B-roll — fast, no character refs, 1K is fine
    "broll": AuthorityProfile(
        resolution="1K", ref_requirement="none", max_refs=1,
        max_prompt_length=800,
        composition_prefix="Cinematic detail shot, atmospheric, ",
        negative_suffix="NO people, NO faces, NO characters",
        quality_tier="preview",
        ltx_resolution="1080p", ltx_duration_override=6,  # Short B-roll
    ),
    "insert": AuthorityProfile(
        resolution="1K", ref_requirement="none", max_refs=1,
        max_prompt_length=600,
        composition_prefix="Insert detail shot, tight framing on object, shallow DOF, ",
        negative_suffix="",
        quality_tier="preview",
        ltx_resolution="1080p", ltx_duration_override=6,
    ),
    "cutaway": AuthorityProfile(
        resolution="1K", ref_requirement="none", max_refs=1,
        max_prompt_length=600,
        composition_prefix="Cutaway shot, environmental detail, ",
        negative_suffix="",
        quality_tier="preview",
        ltx_resolution="1080p", ltx_duration_override=6,
    ),
}

# Dialogue override — applied ON TOP of base profile
DIALOGUE_AUTHORITY = {
    "resolution_boost": "2K",       # Upgrade resolution for dialogue (face quality)
    "ref_override": "mandatory",    # Characters must have refs for dialogue
    "max_refs_boost": 1,            # Add 1 extra ref slot for dialogue
}

# Fallback for unknown shot types
DEFAULT_PROFILE = AuthorityProfile(
    resolution="1K", ref_requirement="required", max_refs=4,
    max_prompt_length=1200,
    composition_prefix="", negative_suffix="",
    quality_tier="production",
    ltx_resolution="1080p", ltx_duration_override=None,
)


# =============================================================================
# SHOT AUTHORITY CONTRACT
# =============================================================================

@dataclass
class ShotContract:
    """Pre-generation contract for a single shot."""
    shot_id: str
    profile: AuthorityProfile
    has_dialogue: bool
    has_refs: bool
    has_location_master: bool
    ref_count: int
    violations: List[str]       # Things that SHOULD be fixed before generation
    warnings: List[str]         # Advisory notes
    fal_params: Dict[str, Any]  # Exact params to send to FAL
    authority_score: float       # 0-1 confidence that output will be correct


def build_shot_contract(
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    ref_urls: List[str],
    location_master_path: Optional[str] = None,
    is_chained: bool = False,
) -> ShotContract:
    """
    Build the authority contract for a shot BEFORE generation.

    V24.2.4: Corrected to use ACTUAL FAL API parameters.
    No guidance_scale, no num_inference_steps — those don't exist.
    Authority is expressed through: resolution, ref count/order,
    prompt composition, and negative constraints.
    """
    shot_id = shot.get("shot_id", "unknown")
    shot_type = (shot.get("type") or shot.get("shot_type") or "medium").lower()
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]
    has_dialogue = bool(shot.get("dialogue_text") or shot.get("dialogue"))
    is_broll = shot.get("_broll", False) or shot.get("_no_chain", False) or shot_type in ("broll", "insert", "cutaway", "detail")

    # Resolve profile
    if is_broll:
        profile = AUTHORITY_PROFILES.get("broll", DEFAULT_PROFILE)
    else:
        profile = AUTHORITY_PROFILES.get(shot_type, DEFAULT_PROFILE)

    # Dialogue override — boost resolution and refs (preserve num_candidates from original profile)
    if has_dialogue and characters:
        _orig_candidates = profile.num_candidates if hasattr(profile, 'num_candidates') else 1
        profile = AuthorityProfile(
            resolution=DIALOGUE_AUTHORITY["resolution_boost"],
            ref_requirement=DIALOGUE_AUTHORITY["ref_override"],
            max_refs=min(profile.max_refs + DIALOGUE_AUTHORITY["max_refs_boost"], 5),
            max_prompt_length=profile.max_prompt_length,
            composition_prefix=profile.composition_prefix,
            negative_suffix=profile.negative_suffix,
            quality_tier="hero" if shot_type in ("close_up", "MCU", "ECU", "medium_close") else profile.quality_tier,
            ltx_resolution=profile.ltx_resolution,
            ltx_duration_override=profile.ltx_duration_override,
            num_candidates=max(_orig_candidates, 1),  # V27: Preserve hero candidate count through dialogue override
        )

    # Validate refs against requirement
    violations = []
    warnings = []
    has_refs = len(ref_urls) > 0
    has_loc = location_master_path is not None and Path(location_master_path).exists() if location_master_path else False

    if profile.ref_requirement == "mandatory" and not has_refs:
        violations.append(f"MISSING REFS: {shot_type} requires character reference images but none resolved")
    elif profile.ref_requirement == "required" and not has_refs and characters:
        warnings.append(f"NO REFS: {shot_type} should have character refs for {', '.join(characters[:2])}")

    if characters and not has_refs:
        warnings.append(f"Characters {characters[:2]} have no face-lock refs — identity will drift")

    if has_dialogue and not has_refs:
        violations.append("DIALOGUE WITHOUT REFS: Speaking shots MUST have character refs for lip sync quality")

    # Ref count validation against profile max
    effective_refs = ref_urls[:profile.max_refs]
    if len(ref_urls) > profile.max_refs:
        warnings.append(f"REF OVERFLOW: {len(ref_urls)} refs provided, capped to {profile.max_refs} per authority")

    # Prompt authority — composition prefix
    nano_prompt = shot.get("nano_prompt_final") or shot.get("nano_prompt", "")
    if profile.composition_prefix and profile.composition_prefix.strip().rstrip(",").lower() not in nano_prompt.lower():
        nano_prompt = profile.composition_prefix + nano_prompt

    # Prompt authority — negative suffix (appended to end of prompt as constraint language)
    if profile.negative_suffix and profile.negative_suffix not in nano_prompt:
        nano_prompt = nano_prompt.rstrip(",. ") + ", " + profile.negative_suffix if profile.negative_suffix else nano_prompt

    # Truncate prompt to profile max
    if len(nano_prompt) > profile.max_prompt_length:
        nano_prompt = nano_prompt[:profile.max_prompt_length - 3] + "..."

    # Build exact FAL params — ONLY parameters the API actually accepts
    fal_params = {
        "prompt": nano_prompt,
        "aspect_ratio": "16:9",
        "resolution": profile.resolution,
        "output_format": "jpeg",
    }

    # V26.2: num_candidates from authority profile — hero=3, production/broll=1
    n_candidates = profile.num_candidates if hasattr(profile, 'num_candidates') else 1
    if effective_refs:
        fal_params["image_urls"] = effective_refs
        fal_params["num_outputs"] = n_candidates
    else:
        fal_params["num_images"] = n_candidates
    fal_params["_num_candidates"] = n_candidates  # For controller to read

    # Authority score — how confident are we the output will be correct?
    score = 1.0
    if not has_refs and characters:
        score -= 0.3  # No face lock — single biggest quality risk
    if not has_loc and not is_broll:
        score -= 0.1  # No location lock
    if len(violations) > 0:
        score -= 0.2 * len(violations)
    if is_chained:
        score += 0.15  # Image carries context — strongest authority
    if has_refs and has_dialogue:
        score += 0.05  # Best case: refs + dialogue = tight control
    if profile.resolution == "2K":
        score += 0.05  # Higher res = better face quality
    score = max(0.0, min(1.0, score))

    return ShotContract(
        shot_id=shot_id,
        profile=profile,
        has_dialogue=has_dialogue,
        has_refs=has_refs,
        has_location_master=has_loc,
        ref_count=len(effective_refs),
        violations=violations,
        warnings=warnings,
        fal_params=fal_params,
        authority_score=round(score, 2),
    )


# =============================================================================
# SCENE PRE-AUTHORIZATION
# =============================================================================

def pre_authorize_scene(
    scene_shots: List[Dict[str, Any]],
    cast_map: Dict[str, Any],
    scene_manifest: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Pre-authorize an entire scene before any generation.
    Returns a scene-level authority report.

    This is the equivalent of a pre-production meeting:
    - Every shot has a contract
    - Every character has refs or is flagged
    - Every location has a master or is flagged
    - Total cost estimated
    - Violations listed (blocking vs advisory)
    """
    contracts = []
    total_violations = 0
    total_warnings = 0
    missing_refs = set()
    hero_shots = 0
    production_shots = 0
    preview_shots = 0

    for shot in scene_shots:
        characters = shot.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",") if c.strip()]

        has_any_ref = False
        for char in characters:
            char_upper = char.upper()
            for cm_key, cm_val in cast_map.items():
                if isinstance(cm_val, dict) and (char_upper in cm_key.upper() or cm_key.upper() in char_upper):
                    ref = (cm_val.get("character_reference_url") or
                           cm_val.get("reference_url") or
                           cm_val.get("headshot_url", ""))
                    if ref:
                        has_any_ref = True
                    else:
                        missing_refs.add(char)
                    break
            else:
                missing_refs.add(char)

        ref_urls = ["placeholder"] if has_any_ref else []
        contract = build_shot_contract(shot, cast_map, ref_urls)
        contracts.append(contract)

        total_violations += len(contract.violations)
        total_warnings += len(contract.warnings)

        if contract.profile.quality_tier == "hero":
            hero_shots += 1
        elif contract.profile.quality_tier == "production":
            production_shots += 1
        else:
            preview_shots += 1

    avg_authority = sum(c.authority_score for c in contracts) / len(contracts) if contracts else 0

    # Cost estimate (rough: 2K costs ~2x more than 1K)
    est_cost = sum(
        0.015 if c.profile.resolution == "2K" else 0.01
        for c in contracts
    )

    return {
        "scene_id": scene_shots[0].get("scene_id", "unknown") if scene_shots else "unknown",
        "total_shots": len(scene_shots),
        "hero_shots": hero_shots,
        "production_shots": production_shots,
        "preview_shots": preview_shots,
        "total_violations": total_violations,
        "total_warnings": total_warnings,
        "missing_refs": list(missing_refs),
        "avg_authority_score": round(avg_authority, 2),
        "estimated_cost_factor": round(est_cost, 2),
        "ready_for_generation": total_violations == 0,
        "contracts": [
            {
                "shot_id": c.shot_id,
                "quality_tier": c.profile.quality_tier,
                "resolution": c.profile.resolution,
                "refs": c.ref_count,
                "authority": c.authority_score,
                "violations": c.violations,
                "warnings": c.warnings,
            }
            for c in contracts
        ],
    }
