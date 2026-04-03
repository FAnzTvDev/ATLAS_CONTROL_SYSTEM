"""
ATLAS V27.1 — MODEL LOCK CONFIGURATION
=======================================

Constitutional Law C3: MODEL LOCK IS ABSOLUTE
nano-banana-pro for first frames (text-to-image, reframes).
LTX-2.3 for video generation (primary).
Kling 3.0 for video generation (alternative — identity-critical shots).
No other models. Period.

V27.1 UPDATE: Kling 3.0 added as APPROVED alternative for video stage.
Film Engine route_shot() decides: Kling for identity-critical (close-up, dialogue, MCU),
LTX for everything else (wide, establishing, B-roll). Operator can override via UI dropdown.

FAL API model strings (canonical source of truth):
  nano-banana-pro:      fal-ai/nano-banana-pro
  nano-banana-pro/edit: fal-ai/nano-banana-pro/edit
  LTX-2.3 i2v fast:    fal-ai/ltx-2.3/image-to-video/fast
  Kling v3 Pro i2v:     fal-ai/kling-video/v3/pro/image-to-video
  SeedDance v2 i2v:     fal-ai/bytedance/seedance/v2/image-to-video
"""

ATLAS_MODEL_LOCK_VERSION = "V27.1"

# =============================================================================
# FORBIDDEN MODELS (NEVER use, regardless of request)
# =============================================================================

FORBIDDEN_MODELS = [
    "minimax", "runway", "pika", "sora", "flux",
    "wan", "mochi", "stable-video-diffusion", "animate-diff",
    "gen-2", "gen-3", "luma", "haiper",
]

# =============================================================================
# RENDER STAGE → APPROVED MODELS
# =============================================================================

ATLAS_RENDER_STAGES = {
    "first_frame": {
        "allowed": ["nano_banana_pro"],
        "default": "nano_banana_pro",
        "model_id": "fal-ai/nano-banana-pro",
        "notes": "Text-to-image identity master. C3 locked.",
    },
    "character_edit": {
        "allowed": ["nano_banana_pro_edit"],
        "default": "nano_banana_pro_edit",
        "model_id": "fal-ai/nano-banana-pro/edit",
        "notes": "Image-to-image reframe (angle variants from master). C3 locked.",
    },
    "video": {
        "allowed": ["ltxv2", "kling3"],
        "default": "ltxv2",
        "models": {
            "ltxv2": {
                "model_id": "fal-ai/ltx-2.3/image-to-video/fast",
                "image_key": "image_url",
                "duration_type": "int",
                "valid_durations": [6, 8, 10, 12, 14, 16, 18, 20],
                "max_duration": 20,
                "supports_negative_prompt": True,
                "cost_per_shot": 0.16,
                "best_for": ["wide", "establishing", "b-roll", "action", "environment"],
            },
            "kling3": {
                "model_id": "fal-ai/kling-video/v3/pro/image-to-video",
                "image_key": "start_image_url",
                "duration_type": "str",
                "valid_durations": [3, 5, 8, 10, 12, 15],
                "max_duration": 15,
                "supports_negative_prompt": True,
                "cost_per_shot": 0.56,
                "best_for": ["close_up", "dialogue", "MCU", "ECU", "reaction", "identity_critical"],
            },
        },
        "notes": "V27.1: Dual model. Film Engine route_shot() selects. UI dropdown override available.",
    },
    "stitch": {
        "allowed": ["ffmpeg"],
        "default": "ffmpeg",
        "model_id": "ffmpeg",
        "notes": "Deterministic concat. No AI. C3 locked.",
    },
}

# =============================================================================
# MODEL KEY → FAL API STRING (single source of truth)
# =============================================================================

FAL_MODEL_STRINGS = {
    "nano_banana_pro": "fal-ai/nano-banana-pro",
    "nano_banana_pro_edit": "fal-ai/nano-banana-pro/edit",
    "ltxv2": "fal-ai/ltx-2.3/image-to-video/fast",
    "kling3": "fal-ai/kling-video/v3/pro/image-to-video",
    "seeddance": "fal-ai/bytedance/seedance/v2/image-to-video",
}


def get_model_id(model_key: str) -> str:
    """Return the FAL API model string for a model key."""
    return FAL_MODEL_STRINGS.get(model_key, "")


def assert_model_allowed(stage: str, model_key: str) -> None:
    """
    V27.1 HARD LOCK: Assert a model is allowed for a given render stage.

    Args:
        stage: Render stage ("first_frame", "character_edit", "video", "stitch")
        model_key: Model key to validate (e.g., "ltxv2", "nano_banana_pro", "kling3")

    Raises:
        RuntimeError: If model is not allowed for the stage
    """
    stage_cfg = ATLAS_RENDER_STAGES.get(stage)
    if not stage_cfg:
        raise RuntimeError(
            f"[MODEL LOCK VIOLATION] Unknown stage: {stage}. "
            f"Valid: {list(ATLAS_RENDER_STAGES.keys())}. "
            f"ATLAS_VERSION: {ATLAS_MODEL_LOCK_VERSION}"
        )

    if model_key not in stage_cfg["allowed"]:
        raise RuntimeError(
            f"[MODEL LOCK VIOLATION] Stage: {stage}, Model: {model_key}. "
            f"Allowed: {stage_cfg['allowed']}. "
            f"ATLAS_VERSION: {ATLAS_MODEL_LOCK_VERSION}"
        )


def get_video_model_config(model_key: str) -> dict:
    """
    V27.1: Get video model-specific config (image_key, duration_type, valid_durations, cost).

    Returns empty dict if model_key not found. Used by controller to build correct payload.
    """
    video_models = ATLAS_RENDER_STAGES.get("video", {}).get("models", {})
    return video_models.get(model_key, {})


def get_lock_status() -> dict:
    """Return current model lock configuration for health check endpoints."""
    return {
        "version": ATLAS_MODEL_LOCK_VERSION,
        "stages": {
            stage: {
                "allowed": cfg["allowed"],
                "default": cfg["default"],
            }
            for stage, cfg in ATLAS_RENDER_STAGES.items()
        },
    }
