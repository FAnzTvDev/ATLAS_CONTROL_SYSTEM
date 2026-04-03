#!/usr/bin/env python3
"""
ATLAS V28 — Video Generation Doctrine (Multi-Model)
=====================================================
Locked API landscape for ALL video generation models.
This file is the SINGLE SOURCE OF TRUTH for video gen parameters.

Every video generation path MUST import from here.
No ad-hoc parameter guessing. No trial-and-error API discovery.

MODELS COVERED:
  1. LTX-2 /fast  — Budget tier. Fixed 6.12s clips. $0.30/video.
  2. LTX-2 (full) — Custom duration (6|8|10 ONLY). $0.04-0.16/sec.
  3. Kling 3.0     — Frontier tier. Up to 15s native. Best for humans.

ROUTING LOGIC:
  - B-roll, establishing, inserts → LTX-2 /fast (cheap, 6s is fine)
  - Dialogue shots needing >6s     → LTX-2 full (custom duration)
  - Hero close-ups, complex acting  → Kling 3.0 (best quality)
  - Multi-character complex scenes  → Kling 3.0 (identity preservation)

DISCOVERED 2026-03-18 from live API testing + research:
  - LTX-2 /fast: 153 frames at 25fps = 6.12s FIXED
  - LTX-2 full: supports `duration` param (6|8|10 ONLY — NOT 12-20 despite docs)
  - Kling 3.0: up to 15s native, 4K HDR 60fps, lip-sync
  - Cost model is per-VIDEO for /fast, per-SECOND for full/Kling

PROMPT RULES (from frontier model research):
  LTX-2.3:
    - 4-8 sentences, single flowing paragraph, present tense
    - Physical descriptions REQUIRED for emotion (not labels)
    - "Avoid emotional labels like 'sad' without describing visual cues"
    - Concrete nouns + verbs > vague descriptors
    - Negative prompts still recommended
    - Camera brand names DO NOT WORK — use focal length + aperture + film stock
    - Zone-separated clauses render more consistently than narrative paragraphs
  Kling 3.0:
    - Up to 2500 chars, optimal 30-100 words
    - Six-zone: Camera → Subject → Environment → Lighting → Texture → Emotion
    - Natural language emotion direction works (controlled composure, explosive anger)
    - ++element++ emphasis markers for critical features
    - Max 7 distinct elements or 3 sequential actions per prompt
    - Multi-shot prompts with character tags supported natively
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════
# MODEL REGISTRY — All approved video generation models
# ═══════════════════════════════════════════════════════════════════

class VideoModels:
    """Locked model identifiers. C3: MODEL LOCK IS ABSOLUTE."""
    LTX2_FAST = "fal-ai/ltx-2/image-to-video/fast"
    LTX2_FULL = "fal-ai/ltx-2/image-to-video"
    KLING_3 = "fal-ai/kling-video/v2/master/image-to-video"  # Kling 3.0 via FAL
    NANO_BANANA = "fal-ai/nano-banana-pro"                    # First frames only
    NANO_BANANA_EDIT = "fal-ai/nano-banana-pro/edit"          # First frames with refs


# ═══════════════════════════════════════════════════════════════════
# LTX-2 /FAST — Budget tier, fixed duration
# ═══════════════════════════════════════════════════════════════════

LTX2_FAST_PARAMS = {
    "accepted": {
        "prompt": "str, required, max ~900 chars",
        "image_url": "str, required, base64 or hosted URL",
        "resolution": "str, required: '1080p' | '1440p' | '2160p'",
        "seed": "int, optional, for reproducibility",
    },
    "rejected": [
        "duration", "num_frames", "aspect_ratio", "num_outputs",
        "guidance_scale", "output_format", "safety_tolerance",
    ],
    "output": {
        "duration_seconds": 6.12,
        "frame_count": 153,
        "fps": 25,
        "codec": "h264",
        "pixel_format": "yuv420p",
    },
    "cost_per_video": 0.30,
    "latency_range": "42-103s",
}


# ═══════════════════════════════════════════════════════════════════
# LTX-2 FULL — Custom duration tier
# ═══════════════════════════════════════════════════════════════════

LTX2_FULL_PARAMS = {
    "accepted": {
        "prompt": "str, required, max ~900 chars",
        "image_url": "str, required, base64 or hosted URL",
        "resolution": "str, required: '1080p' | '1440p' | '2160p'",
        "duration": "int, optional: 6|8|10 ONLY (FAL rejects 12+)",
        "seed": "int, optional",
    },
    "rejected": [
        "num_frames", "aspect_ratio", "num_outputs",
        "guidance_scale", "output_format",
    ],
    "cost_per_second": 0.10,  # ~$0.04-0.16/sec range, using mid estimate
    "latency_range": "60-180s",
    "max_duration": 10,  # CORRECTED: FAL API rejects 12+ with literal_error
    "min_duration": 6,
    "duration_step": 2,  # Must be even numbers
    "valid_durations": [6, 8, 10],  # EXHAUSTIVE — no other values accepted
}


# ═══════════════════════════════════════════════════════════════════
# KLING 3.0 — Frontier tier (via FAL)
# ═══════════════════════════════════════════════════════════════════

KLING_3_PARAMS = {
    "accepted": {
        "prompt": "str, required, max 2500 chars, optimal 30-100 words",
        "image_url": "str, required",
        "duration": "str: '5' | '10' (seconds)",
        "aspect_ratio": "str: '16:9' | '9:16' | '1:1'",
    },
    "features": [
        "Native 4K HDR at 60fps",
        "Lip-sync in 5+ languages",
        "Physics-aware motion (gravity, inertia, cloth)",
        "Natural language emotion direction",
        "Element Binding for character identity",
    ],
    "cost_per_second": 0.50,  # Kling is expensive
    "latency_range": "90-300s",
    "max_duration": 15,
}

# Kling prompt structure (six-zone)
KLING_PROMPT_ZONES = [
    "Camera",       # Focal length, movement, angle
    "Subject",      # Character appearance, action, expression
    "Environment",  # Setting, props, spatial layout
    "Lighting",     # Light source, color temperature, direction
    "Texture",      # Film grain, skin detail, fabric weave
    "Emotion",      # Performance direction, mood
]


# ═══════════════════════════════════════════════════════════════════
# PROMPT RULES — What works vs what doesn't
# ═══════════════════════════════════════════════════════════════════

# Camera tokens that WORK on both models
EFFECTIVE_CAMERA_TOKENS = [
    "focal length (24mm, 35mm, 50mm, 85mm)",
    "aperture values (f/1.2, f/2.8, f/8)",
    "film stock references (Kodak Vision3 500T, shot on 35mm film)",
    "aspect ratios (2.39:1 anamorphic)",
    "camera movement verbs (dolly push, crane drop, Steadicam glide, rack focus)",
]

# Camera tokens that DO NOT WORK reliably
INEFFECTIVE_CAMERA_TOKENS = [
    "Camera body names (ARRI Alexa, RED Komodo, Sony Venice)",
    "Lens brand names (Cooke, Zeiss, Panavision)",
    "These trigger aesthetic associations, not optical simulation",
]

# LTX-2 requires physical descriptions for emotion
LTX_EMOTION_RULE = """
LTX-2.3 REQUIRES physical descriptions, not emotion labels.
BAD:  'sad expression, melancholy mood'
GOOD: 'eyes glistening, jaw clenched, shoulders slightly hunched,
       slow exhale visible, hands trembling slightly'
The truth translator already does this conversion via
EYE_LINE_TRANSLATIONS and BODY_TRANSLATIONS dictionaries.
"""

# LTX-2 recommended negative prompts
LTX_NEGATIVE_PROMPTS = [
    "worst quality",
    "inconsistent motion",
    "blurry",
    "jittery",
    "distorted",
    "CGI",
    "artificial",
    "oily shine",
]


# ═══════════════════════════════════════════════════════════════════
# ROUTING LOGIC — Which model for which shot
# ═══════════════════════════════════════════════════════════════════

def select_video_model(shot: Dict, budget_remaining: float = 30.0) -> str:
    """
    Select the optimal video model for a shot based on requirements.

    Routing rules:
      1. Multi-character dialogue → Kling (if budget allows)
      2. Dialogue needing >6s → LTX-2 full
      3. Hero close-ups with acting → LTX-2 full (longer = better)
      4. B-roll, establishing, inserts → LTX-2 /fast (cheap)
      5. Budget fallback → always LTX-2 /fast
    """
    shot_type = shot.get("shot_type", "")
    has_dialogue = bool(shot.get("dialogue_text", ""))
    chars = shot.get("characters") or []
    char_count = len(chars)
    duration = shot.get("duration", 4)

    # Calculate minimum duration for dialogue
    min_dur = 0
    if has_dialogue:
        word_count = len(shot.get("dialogue_text", "").split())
        min_dur = (word_count / 2.3) + 1.5

    # Rule 1: Multi-character dialogue → Kling (best quality)
    if char_count >= 2 and has_dialogue and budget_remaining > 5.0:
        return VideoModels.KLING_3

    # Rule 2: Dialogue needing >6s → LTX-2 full
    if min_dur > 6.0:
        needed_dur = _round_to_ltx_duration(min_dur)
        cost = needed_dur * LTX2_FULL_PARAMS["cost_per_second"]
        if budget_remaining > cost:
            return VideoModels.LTX2_FULL
        # Budget fallback
        return VideoModels.LTX2_FAST

    # Rule 3: Hero shots with performance → LTX-2 full for 8s
    if shot_type in ("close_up", "medium_close", "reaction") and has_dialogue:
        return VideoModels.LTX2_FULL

    # Rule 4: Everything else → LTX-2 /fast (budget tier)
    return VideoModels.LTX2_FAST


def _round_to_ltx_duration(seconds: float) -> int:
    """Round to nearest valid LTX-2 full duration. ONLY 6, 8, or 10 accepted by FAL API."""
    VALID = [6, 8, 10]
    d = max(6, min(10, int(seconds)))
    if d % 2 != 0:
        d += 1
    d = min(d, 10)  # HARD CAP — FAL rejects anything above 10
    return d if d in VALID else 10


# ═══════════════════════════════════════════════════════════════════
# BUILD FAL ARGUMENTS — The only way to build video gen params
# ═══════════════════════════════════════════════════════════════════

def build_video_arguments(
    model: str,
    prompt: str,
    image_url: str,
    shot: Optional[Dict] = None,
    resolution: str = "1080p",
    seed: Optional[int] = None,
) -> Dict:
    """
    Build validated FAL arguments for ANY video model.

    This is the ONLY function that should build video params.
    Raises ValueError on invalid configuration.
    """
    if model == VideoModels.LTX2_FAST:
        return _build_ltx2_fast(prompt, image_url, resolution, seed)
    elif model == VideoModels.LTX2_FULL:
        duration = _get_required_duration(shot) if shot else 8
        return _build_ltx2_full(prompt, image_url, resolution, duration, seed)
    elif model == VideoModels.KLING_3:
        duration = "10" if shot and shot.get("dialogue_text") else "5"
        return _build_kling3(prompt, image_url, duration)
    else:
        raise ValueError(f"Unknown model: {model}. Use VideoModels constants.")


def _build_ltx2_fast(prompt, image_url, resolution, seed):
    if resolution not in ("1080p", "1440p", "2160p"):
        raise ValueError(f"LTX-2 /fast resolution must be 1080p/1440p/2160p, got {resolution}")
    if len(prompt) > 900:
        prompt = prompt[:897] + "..."
    args = {"prompt": prompt, "image_url": image_url, "resolution": resolution}
    if seed is not None:
        args["seed"] = seed
    return args


def _build_ltx2_full(prompt, image_url, resolution, duration, seed):
    if resolution not in ("1080p", "1440p", "2160p"):
        raise ValueError(f"LTX-2 resolution must be 1080p/1440p/2160p, got {resolution}")
    duration = _round_to_ltx_duration(duration)
    if len(prompt) > 900:
        prompt = prompt[:897] + "..."
    args = {"prompt": prompt, "image_url": image_url, "resolution": resolution, "duration": duration}
    if seed is not None:
        args["seed"] = seed
    return args


def _build_kling3(prompt, image_url, duration):
    if len(prompt) > 2500:
        prompt = prompt[:2497] + "..."
    return {
        "prompt": prompt,
        "image_url": image_url,
        "duration": duration,
        "aspect_ratio": "16:9",
    }


def _get_required_duration(shot: Dict) -> int:
    """Calculate required video duration from shot data."""
    base_dur = shot.get("duration", 6)
    dialogue = shot.get("dialogue_text", "")
    if dialogue:
        word_count = len(dialogue.split())
        min_dur = (word_count / 2.3) + 1.5
        base_dur = max(base_dur, min_dur)
    return _round_to_ltx_duration(base_dur)


# ═══════════════════════════════════════════════════════════════════
# COST MODEL
# ═══════════════════════════════════════════════════════════════════

COST_PER_FIRST_FRAME = 0.04  # nano-banana-pro

def estimate_video_cost(model: str, duration_seconds: float = 6.12) -> float:
    """Estimate cost for a single video generation."""
    if model == VideoModels.LTX2_FAST:
        return 0.30
    elif model == VideoModels.LTX2_FULL:
        return duration_seconds * LTX2_FULL_PARAMS["cost_per_second"]
    elif model == VideoModels.KLING_3:
        return duration_seconds * KLING_3_PARAMS["cost_per_second"]
    return 0.30  # default


def estimate_scene_cost(shots: List[Dict], budget_cap: float = 30.0) -> Dict:
    """Full scene cost estimate with model routing."""
    frame_cost = len(shots) * COST_PER_FIRST_FRAME
    video_cost = 0
    model_breakdown = {}
    for shot in shots:
        model = select_video_model(shot, budget_cap - frame_cost - video_cost)
        dur = _get_required_duration(shot) if shot.get("dialogue_text") else 6.12
        cost = estimate_video_cost(model, dur)
        video_cost += cost
        model_breakdown[model] = model_breakdown.get(model, 0) + 1

    retry_cost = len(shots) * 0.30  # 1 retry per shot at /fast rate
    total = frame_cost + video_cost + retry_cost
    return {
        "first_frames": frame_cost,
        "videos": video_cost,
        "retries_estimate": retry_cost,
        "total": total,
        "within_budget": total <= budget_cap,
        "model_routing": model_breakdown,
    }


# ═══════════════════════════════════════════════════════════════════
# PRE-RUN VALIDATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class VideoDoctrineCheck:
    """Result of video doctrine validation."""
    model_locked: bool
    params_valid: bool
    cost_within_budget: bool
    estimated_cost: float
    budget_remaining: float
    model_routing: Dict = field(default_factory=dict)
    dialogue_duration_issues: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return self.model_locked and self.params_valid and self.cost_within_budget


def validate_video_readiness(
    shots: List[Dict],
    budget_remaining: float,
) -> VideoDoctrineCheck:
    """
    Pre-run validation for video generation.
    Checks model routing, duration compliance, and budget.
    """
    issues = []
    dur_issues = []
    model_routing = {}
    total_cost = 0

    for shot in shots:
        sid = shot.get("shot_id", "?")
        model = select_video_model(shot, budget_remaining - total_cost)
        model_routing[model] = model_routing.get(model, 0) + 1

        dur = _get_required_duration(shot) if shot.get("dialogue_text") else 6.12
        cost = estimate_video_cost(model, dur)
        total_cost += cost

        # Check dialogue duration compliance
        dialogue = shot.get("dialogue_text", "")
        if dialogue:
            word_count = len(dialogue.split())
            min_dur = (word_count / 2.3) + 1.5
            if model == VideoModels.LTX2_FAST and min_dur > 6.12:
                dur_issues.append(
                    f"{sid}: dialogue needs {min_dur:.1f}s but /fast only gives 6.1s — will route to full"
                )

    total_with_retries = total_cost + len(shots) * 0.30
    cost_ok = total_with_retries <= budget_remaining
    if not cost_ok:
        issues.append(f"Estimated ${total_with_retries:.2f} exceeds budget ${budget_remaining:.2f}")

    return VideoDoctrineCheck(
        model_locked=True,
        params_valid=True,
        cost_within_budget=cost_ok,
        estimated_cost=total_with_retries,
        budget_remaining=budget_remaining - total_with_retries,
        model_routing=model_routing,
        dialogue_duration_issues=dur_issues,
        issues=issues,
    )


# ═══════════════════════════════════════════════════════════════════
# CLI — Print full doctrine status
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  ATLAS V28 — VIDEO GENERATION DOCTRINE (Multi-Model)")
    print("=" * 70)

    print(f"\n  MODELS:")
    print(f"    LTX-2 /fast: {VideoModels.LTX2_FAST}")
    print(f"      Duration: FIXED 6.12s | Cost: $0.30/video | Latency: 42-103s")
    print(f"      Use for: B-roll, establishing, inserts, non-dialogue")
    print(f"    LTX-2 full:  {VideoModels.LTX2_FULL}")
    print(f"      Duration: 6|8|10s ONLY | Cost: ~$0.10/sec | Latency: 60-180s")
    print(f"      Use for: Dialogue >6s, hero close-ups, acting performance")
    print(f"    Kling 3.0:   {VideoModels.KLING_3}")
    print(f"      Duration: 5-15s | Cost: ~$0.50/sec | Latency: 90-300s")
    print(f"      Use for: Multi-character, complex acting, lip-sync")

    print(f"\n  PROMPT RULES:")
    print(f"    LTX-2: Physical descriptions REQUIRED for emotion (not labels)")
    print(f"    LTX-2: Max 900 chars, zone-separated, present tense")
    print(f"    Kling: Max 2500 chars, 30-100 words optimal")
    print(f"    BOTH: Camera brands DON'T WORK — use focal length + aperture + film stock")

    print(f"\n  EFFECTIVE CAMERA TOKENS:")
    for t in EFFECTIVE_CAMERA_TOKENS:
        print(f"    ✓ {t}")
    print(f"\n  INEFFECTIVE (DO NOT USE):")
    for t in INEFFECTIVE_CAMERA_TOKENS:
        print(f"    ✗ {t}")

    print(f"\n  COST MODEL:")
    print(f"    First frame: $0.04/shot (nano-banana-pro)")
    print(f"    Video /fast: $0.30/video (6s fixed)")
    print(f"    Video full:  ~$0.10/sec (8s = $0.80)")
    print(f"    Video Kling: ~$0.50/sec (10s = $5.00)")

    print(f"\n  8-SHOT SCENE ESTIMATES:")
    for scenario, desc in [
        ("all_fast", "All /fast (B-roll heavy)"),
        ("mixed", "Mixed routing (typical scene)"),
        ("all_kling", "All Kling (premium)"),
    ]:
        if scenario == "all_fast":
            cost = 8 * 0.04 + 8 * 0.30 + 8 * 0.30
            print(f"    {desc}: ${cost:.2f}")
        elif scenario == "mixed":
            cost = 8 * 0.04 + 5 * 0.30 + 3 * 0.80 + 8 * 0.30
            print(f"    {desc}: ${cost:.2f}")
        else:
            cost = 8 * 0.04 + 8 * 5.0 + 8 * 0.30
            print(f"    {desc}: ${cost:.2f}")

    print(f"\n{'='*70}")
