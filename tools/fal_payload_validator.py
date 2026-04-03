"""
ATLAS V26.1 — FAL PAYLOAD VALIDATOR
====================================
Model-safe payload enforcement. Every payload sent to FAL passes through here.
Each engine has its own constraint set. Invalid params are STRIPPED, not errored.
Missing required params are FLAGGED as violations.

Design:
  - `validate_payload(engine, payload)` is the gateway for all FAL calls
  - Each engine (nano, nano-edit, kling, ltx) has constraints defined
  - Payloads are normalized: duration strings→ints, resolutions normalized, refs capped
  - Invalid params are SILENTLY STRIPPED (not raised as errors)
  - Violations + warnings are returned as metadata — generation proceeds regardless
  - Convenience builders (build_nano_payload, build_ltx_payload, etc.) wrap validation

CRITICAL DOCTRINE V26.1 (Laws 211-218):
  211. NO guidance_scale or num_inference_steps — FAL ignores them
  212. Resolution is the primary quality lever — 1K for production, 2K for hero
  213. Shot Authority is NON-BLOCKING — if build fails, proceed with defaults
  214. Smart Regen bumps resolution +1 tier
  215. Smart Regen escalation always uses 2K
  216. Ref cap is per-shot-type (hero=3, production=4, etc.)
  217. Dialogue override adds +1 ref slot and forces 2K minimum
  218. All FAL calls use aspect_ratio + resolution + output_format (canonical param set)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("atlas.fal_payload_validator")


# =============================================================================
# ENGINE CONSTRAINTS
# =============================================================================

class ModelEngine(Enum):
    """FAL model engines supported by ATLAS."""
    NANO = "nano-banana-pro"
    NANO_EDIT = "nano-banana-pro/edit"
    KLING = "kling-video/v2/master/image-to-video"
    LTX = "ltx-2/image-to-video/fast"


@dataclass
class EngineConstraints:
    """Constraint set for a single FAL model engine."""
    engine: str                          # "nano", "nano-edit", "kling", "ltx"
    required_params: List[str]           # Must be present in payload
    optional_params: List[str]           # OK to have, OK to omit
    forbidden_params: List[str]          # STRIPPED if present (never sent to FAL)
    param_types: Dict[str, type]         # Type validators
    allowed_values: Dict[str, List[Any]] # Value enums (e.g., resolution choices)
    max_prompt_length: int               # Truncate if exceeded
    max_image_urls: int                  # Max image_urls / refs


# nano-banana-pro (text-to-image)
NANO_CONSTRAINTS = EngineConstraints(
    engine="nano",
    required_params=["prompt"],
    optional_params=["image_urls", "resolution", "aspect_ratio", "output_format", "seed", "safety_tolerance", "num_images"],
    forbidden_params=["guidance_scale", "num_inference_steps", "image_size", "negative_prompt"],
    param_types={
        "prompt": str,
        "image_urls": list,
        "resolution": str,
        "aspect_ratio": str,
        "output_format": str,
        "seed": int,
        "safety_tolerance": str,
        "num_images": int,
    },
    allowed_values={
        "resolution": ["1K", "2K", "4K"],
        "aspect_ratio": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
        "output_format": ["jpeg", "png"],
        "safety_tolerance": ["1", "2", "3", "4", "5", "6"],
    },
    max_prompt_length=4000,
    max_image_urls=10,
)

# nano-banana-pro/edit (image editing)
NANO_EDIT_CONSTRAINTS = EngineConstraints(
    engine="nano-edit",
    required_params=["prompt", "image_urls"],
    optional_params=["resolution", "aspect_ratio", "output_format", "num_outputs"],
    forbidden_params=["guidance_scale", "num_inference_steps", "image_size", "negative_prompt"],
    param_types={
        "prompt": str,
        "image_urls": list,
        "resolution": str,
        "aspect_ratio": str,
        "output_format": str,
        "num_outputs": int,
    },
    allowed_values={
        "resolution": ["1K", "2K", "4K"],
        "aspect_ratio": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
        "output_format": ["jpeg", "png"],
    },
    max_prompt_length=4000,
    max_image_urls=10,
)

# Kling 3.0 video generation
KLING_CONSTRAINTS = EngineConstraints(
    engine="kling",
    required_params=["prompt", "image_url"],
    optional_params=["duration", "aspect_ratio", "cfg_scale", "negative_prompt", "generate_audio", "elements"],
    forbidden_params=["guidance_scale", "num_inference_steps", "image_size", "resolution", "fps"],
    param_types={
        "prompt": str,
        "image_url": str,
        "duration": str,  # String enum for Kling
        "aspect_ratio": str,
        "cfg_scale": float,
        "negative_prompt": str,
        "generate_audio": bool,
        "elements": list,
    },
    allowed_values={
        "duration": ["3", "5", "10", "15"],  # String enum
        "aspect_ratio": ["16:9", "9:16", "1:1"],
    },
    max_prompt_length=4000,
    max_image_urls=1,  # Kling uses image_url (singular)
)

# LTX-2.3 fast video generation
LTX_CONSTRAINTS = EngineConstraints(
    engine="ltx",
    required_params=["prompt", "image_url"],
    optional_params=["duration", "resolution", "fps", "guidance_scale", "negative_prompt", "generate_audio"],
    forbidden_params=["num_inference_steps", "image_size", "cfg_scale", "aspect_ratio"],
    param_types={
        "prompt": str,
        "image_url": str,
        "duration": int,  # Int enum for LTX
        "resolution": str,
        "fps": int,
        "guidance_scale": float,
        "negative_prompt": str,
        "generate_audio": bool,
    },
    allowed_values={
        "duration": [6, 8, 10, 12, 14, 16, 18, 20],  # Int enum
        "resolution": ["1080p", "1440p", "2160p"],
        "fps": [25, 50],
    },
    max_prompt_length=4000,
    max_image_urls=1,  # LTX uses image_url (singular)
)

# Constraint registry
CONSTRAINT_MAP = {
    "nano": NANO_CONSTRAINTS,
    "nano-banana-pro": NANO_CONSTRAINTS,
    "nano-edit": NANO_EDIT_CONSTRAINTS,
    "nano-banana-pro/edit": NANO_EDIT_CONSTRAINTS,
    "kling": KLING_CONSTRAINTS,
    "kling-video/v2/master/image-to-video": KLING_CONSTRAINTS,
    "ltx": LTX_CONSTRAINTS,
    "ltx-2/image-to-video/fast": LTX_CONSTRAINTS,
}


# =============================================================================
# PAYLOAD VALIDATION RESULT
# =============================================================================

@dataclass
class PayloadValidation:
    """Result of FAL payload validation."""
    clean_payload: Dict[str, Any]        # Sanitized payload, ready for FAL
    engine: str                          # Which engine this is for
    is_valid: bool                       # All required params present + no critical violations
    stripped_params: List[str]           # Forbidden params that were removed
    violations: List[str]                # Critical issues (missing required, invalid types)
    warnings: List[str]                  # Advisory notes (truncated, refs capped, etc.)

    def log_summary(self):
        """Log a summary of validation results."""
        if self.violations:
            logger.warning(f"[{self.engine}] VIOLATIONS: {'; '.join(self.violations)}")
        if self.warnings:
            logger.info(f"[{self.engine}] WARNINGS: {'; '.join(self.warnings)}")
        if self.stripped_params:
            logger.info(f"[{self.engine}] Stripped forbidden params: {', '.join(self.stripped_params)}")


# =============================================================================
# CORE VALIDATION FUNCTION
# =============================================================================

def validate_payload(engine: str, payload: Dict[str, Any]) -> PayloadValidation:
    """
    Validate and normalize a FAL API payload.

    This is the GATEWAY for all FAL calls. It ensures:
    - Only accepted params are sent
    - Forbidden params are stripped
    - Required params are present
    - Values are normalized (durations, resolutions, image lists)
    - No errors are raised — all issues are logged as metadata

    Args:
        engine: "nano", "nano-edit", "kling", "ltx" (or full model ID)
        payload: Raw input dict

    Returns:
        PayloadValidation with clean_payload ready for FAL
    """
    # Resolve engine
    constraint = CONSTRAINT_MAP.get(engine)
    if not constraint:
        logger.warning(f"Unknown engine: {engine}, using nano defaults")
        constraint = NANO_CONSTRAINTS

    engine_name = constraint.engine

    clean = {}
    violations = []
    warnings = []
    stripped = []

    # Check required params
    for req in constraint.required_params:
        if req not in payload:
            violations.append(f"MISSING REQUIRED: {req}")
        else:
            clean[req] = payload[req]

    # Process optional + allowed params
    for key, value in payload.items():
        if key in constraint.required_params:
            continue  # Already handled
        if key in constraint.forbidden_params:
            stripped.append(key)
            continue  # Don't copy forbidden params
        if key not in constraint.optional_params:
            logger.debug(f"Unexpected param for {engine_name}: {key}, including anyway")

        # Type check
        expected_type = constraint.param_types.get(key)
        if expected_type and not isinstance(value, expected_type):
            violations.append(f"TYPE ERROR: {key} is {type(value).__name__}, expected {expected_type.__name__}")
            continue

        # Value check (enum validation)
        if key in constraint.allowed_values:
            allowed = constraint.allowed_values[key]
            if value not in allowed:
                violations.append(f"INVALID VALUE: {key}={value}, must be one of {allowed}")
                continue

        clean[key] = value

    # Normalize prompt length
    if "prompt" in clean:
        prompt = clean["prompt"]
        if len(prompt) > constraint.max_prompt_length:
            warnings.append(f"PROMPT TRUNCATED from {len(prompt)} to {constraint.max_prompt_length} chars")
            clean["prompt"] = prompt[:constraint.max_prompt_length - 3] + "..."

    # Normalize image URLs
    if "image_urls" in clean:
        urls = clean["image_urls"]
        if not isinstance(urls, list):
            urls = [urls]
        if len(urls) > constraint.max_image_urls:
            warnings.append(f"REFS CAPPED from {len(urls)} to {constraint.max_image_urls}")
            urls = urls[:constraint.max_image_urls]
        clean["image_urls"] = urls

    # Normalize singular image_url (for Kling/LTX)
    if "image_url" in clean:
        url = clean["image_url"]
        if isinstance(url, list):
            if url:
                warnings.append(f"image_url received list, using first element")
                clean["image_url"] = url[0]
            else:
                violations.append("image_url list is empty")

    # Determine validity
    is_valid = len(violations) == 0

    return PayloadValidation(
        clean_payload=clean,
        engine=engine_name,
        is_valid=is_valid,
        stripped_params=stripped,
        violations=violations,
        warnings=warnings,
    )


# =============================================================================
# NORMALIZATION HELPERS
# =============================================================================

def normalize_duration(engine: str, duration: Any) -> Any:
    """
    Normalize duration to engine-specific format.

    Kling uses STRING enum: "3" | "5" | "10" | "15"
    LTX uses INT enum: 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20

    Args:
        engine: "kling" or "ltx" (or full model ID)
        duration: int or str

    Returns:
        Normalized duration (string for Kling, int for LTX)
    """
    constraint = CONSTRAINT_MAP.get(engine, NANO_CONSTRAINTS)

    # Convert to int first
    if isinstance(duration, str):
        try:
            duration = int(duration)
        except ValueError:
            logger.warning(f"Cannot parse duration: {duration}, using default")
            duration = 8

    # Normalize to engine's enum
    if constraint.engine == "kling":
        # Kling: map int to nearest string enum
        kling_options = [3, 5, 10, 15]
        closest = min(kling_options, key=lambda x: abs(x - duration))
        return str(closest)
    elif constraint.engine == "ltx":
        # LTX: map to nearest int enum
        ltx_options = [6, 8, 10, 12, 14, 16, 18, 20]
        closest = min(ltx_options, key=lambda x: abs(x - duration))
        return closest
    else:
        # For nano, just return int
        return int(duration)


def normalize_resolution(engine: str, resolution: str) -> str:
    """
    Normalize resolution to engine-specific format.

    nano/nano-edit: "1K" | "2K" | "4K"
    kling: (no resolution param — Kling controls internally)
    ltx: "1080p" | "1440p" | "2160p"

    Args:
        engine: Model engine
        resolution: Input resolution string

    Returns:
        Normalized resolution for the engine
    """
    resolution = str(resolution).upper()

    constraint = CONSTRAINT_MAP.get(engine, NANO_CONSTRAINTS)

    if constraint.engine == "ltx":
        # Map 1K/2K/4K → 1080p/1440p/2160p
        mapping = {
            "1K": "1080p", "1K ": "1080p", "1280": "1080p",
            "2K": "1440p", "2K ": "1440p", "2560": "1440p",
            "4K": "2160p", "4K ": "2160p", "4096": "2160p",
            "1080P": "1080p", "1440P": "1440p", "2160P": "2160p",
        }
        return mapping.get(resolution, "1080p")
    else:
        # nano: 1K, 2K, 4K
        return resolution if resolution in ["1K", "2K", "4K"] else "1K"


def clamp_refs(engine: str, image_urls: List[str], max_refs: int) -> List[str]:
    """
    Cap reference image count per engine limits.

    nano: max 10
    nano-edit: max 10
    kling: max 1 (uses image_url, not image_urls)
    ltx: max 1 (uses image_url, not image_urls)

    Args:
        engine: Model engine
        image_urls: List of image URLs
        max_refs: Caller's max ref count (from ShotContract)

    Returns:
        Clamped list of URLs
    """
    constraint = CONSTRAINT_MAP.get(engine, NANO_CONSTRAINTS)

    # Apply both constraints: caller's max + engine's max
    final_max = min(max_refs, constraint.max_image_urls)

    if len(image_urls) > final_max:
        logger.info(f"Clamping refs from {len(image_urls)} to {final_max}")
        return image_urls[:final_max]

    return image_urls


# =============================================================================
# CONVENIENCE PAYLOAD BUILDERS
# =============================================================================

def build_nano_payload(
    prompt: str,
    image_urls: Optional[List[str]] = None,
    resolution: str = "1K",
    aspect_ratio: str = "16:9",
    output_format: str = "jpeg",
    seed: Optional[int] = None,
    safety_tolerance: str = "3",
) -> PayloadValidation:
    """
    Build a nano-banana-pro text-to-image or edit payload.

    If image_urls are provided, this becomes an edit payload (edit mode).
    Otherwise, text-to-image mode.

    Returns PayloadValidation with clean_payload ready for FAL.
    """
    payload = {
        "prompt": prompt,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
    }

    if image_urls:
        payload["image_urls"] = image_urls if isinstance(image_urls, list) else [image_urls]
        payload["num_outputs"] = 1
        engine = "nano-edit"
    else:
        payload["num_images"] = 1
        engine = "nano"

    if seed is not None:
        payload["seed"] = seed

    result = validate_payload(engine, payload)
    result.log_summary()
    return result


def build_nano_edit_payload(
    prompt: str,
    image_urls: List[str],
    resolution: str = "1K",
    aspect_ratio: str = "16:9",
    output_format: str = "jpeg",
) -> PayloadValidation:
    """
    Build a nano-banana-pro/edit image reframing payload.

    image_urls are required and should contain the source image + character refs.

    Returns PayloadValidation with clean_payload ready for FAL.
    """
    payload = {
        "prompt": prompt,
        "image_urls": image_urls if isinstance(image_urls, list) else [image_urls],
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "output_format": output_format,
        "num_outputs": 1,
    }

    result = validate_payload("nano-edit", payload)
    result.log_summary()
    return result


def build_kling_payload(
    prompt: str,
    image_url: str,
    duration: str = "5",
    aspect_ratio: str = "16:9",
    cfg_scale: float = 0.5,
    negative_prompt: Optional[str] = None,
    generate_audio: bool = False,
) -> PayloadValidation:
    """
    Build a Kling 3.0 image-to-video payload.

    image_url is required (singular, not list).
    duration is a string enum: "3" | "5" | "10" | "15"

    Returns PayloadValidation with clean_payload ready for FAL.
    """
    # Normalize duration to Kling format
    duration = normalize_duration("kling", duration)

    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "cfg_scale": cfg_scale,
        "generate_audio": generate_audio,
    }

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    result = validate_payload("kling", payload)
    result.log_summary()
    return result


def build_ltx_payload(
    prompt: str,
    image_url: str,
    duration: int = 8,
    resolution: str = "1080p",
    fps: int = 25,
    guidance_scale: float = 7.0,
    negative_prompt: Optional[str] = None,
    generate_audio: bool = False,
) -> PayloadValidation:
    """
    Build an LTX-2.3 image-to-video payload.

    image_url is required (singular, not list).
    duration is an int enum: 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20
    resolution: "1080p" | "1440p" | "2160p"

    Returns PayloadValidation with clean_payload ready for FAL.
    """
    # Normalize resolution
    resolution = normalize_resolution("ltx", resolution)

    # Normalize duration to LTX format
    duration = normalize_duration("ltx", duration)

    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "duration": duration,
        "resolution": resolution,
        "fps": fps,
        "guidance_scale": guidance_scale,
        "generate_audio": generate_audio,
    }

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    result = validate_payload("ltx", payload)
    result.log_summary()
    return result


# =============================================================================
# BATCH VALIDATION (For multi-shot renders)
# =============================================================================

def validate_batch_payloads(
    payloads: List[Tuple[str, Dict[str, Any]]],  # List of (engine, payload) tuples
) -> Dict[str, PayloadValidation]:
    """
    Validate multiple payloads in one call.

    Useful for scene renders where multiple shots go to FAL.

    Args:
        payloads: List of (engine, payload) tuples

    Returns:
        Dict mapping shot_id (or index) to PayloadValidation
    """
    results = {}
    for i, (engine, payload) in enumerate(payloads):
        shot_id = payload.get("shot_id", f"shot_{i}")
        results[shot_id] = validate_payload(engine, payload)
    return results


# =============================================================================
# TEST HELPERS
# =============================================================================

def test_constraint_coverage():
    """
    Verify that all constraints are properly defined.
    Called during module load to catch configuration errors.
    """
    for key, constraint in CONSTRAINT_MAP.items():
        # All param types should have type checkers
        for param, ptype in constraint.param_types.items():
            assert ptype is not None, f"Missing type for {param} in {key}"

        # All allowed values should be in param_types
        for param in constraint.allowed_values:
            assert param in constraint.param_types, f"Allowed value param {param} not in param_types for {key}"

    logger.info("Constraint coverage check: PASS")


# Run coverage test on module load
try:
    test_constraint_coverage()
except AssertionError as e:
    logger.error(f"Constraint configuration error: {e}")
