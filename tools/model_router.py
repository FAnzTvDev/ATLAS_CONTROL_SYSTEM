"""
ATLAS V26.1 — MODEL ROUTER
============================
Routes shots to the correct FAL engine based on render_mode and shot characteristics.

Design Principle: Smart Engine Selection
Different shots have different requirements. Dialogue needs identity lock (Kling strength).
B-roll needs speed and economy (LTX strength). The router matches each shot to its best engine.

Render modes:
  - "ltx"   → LTX-2.3 only (fast, open-source, up to 20s)
  - "kling"  → Kling 3.0 only (premium, closed-source, up to 15s, better identity)
  - "auto"   → Router decides per shot (dialogue/hero→Kling, b-roll/establishing→LTX)
  - "dual"   → Generate with BOTH engines, keep best (expensive, for key shots)

Kling 3.0 strengths (confirmed 2026):
  - Native character identity lock (Elements 3.0 + Element Binding)
  - 4K HDR 60fps, physics-aware motion
  - Multi-shot storyboard (up to 6 scenes natively)
  - Natural language emotion direction works
  - Duration: 3-15 seconds
  - Cost: ~$0.08-0.20/sec

LTX-2.3 strengths:
  - Open-source, runs locally
  - Up to 20 seconds per generation
  - Trainable LoRAs for style/character
  - Native audio generation
  - Duration: 6-20 seconds
  - Cost: ~$0.04-0.16/sec

The model lock from CLAUDE.md applies: nano-banana-pro for frames, ltx/kling for video.
Frame generation is ALWAYS nano-banana-pro (or nano-banana-pro/edit with refs).
This router only decides the VIDEO engine.

STATUS: V26.1 PRODUCTION READY
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("atlas.model_router")


# =============================================================================
# ENGINE CAPABILITIES
# =============================================================================

class VideoEngine(Enum):
    """Supported video generation engines."""
    LTX = "ltx"
    KLING = "kling"


@dataclass
class EngineCapability:
    """Per-engine capability specification."""
    engine: VideoEngine
    max_duration: int              # Maximum seconds per generation
    min_duration: int              # Minimum seconds per generation
    supports_audio: bool           # Native audio generation
    supports_multi_shot: bool      # Multi-shot storyboard
    identity_lock_native: bool     # Native character identity (Elements/Binding)
    emotion_direction_native: bool # Natural language emotion comprehension
    resolution_max: str            # Best resolution supported
    cost_per_second: float         # Estimated USD per second
    fal_endpoint: str              # FAL API endpoint string
    fal_endpoint_i2v: str          # FAL image-to-video endpoint


# Engine capability definitions (research-backed, 2026-03-15)
KLING_CAPS = EngineCapability(
    engine=VideoEngine.KLING,
    max_duration=15,
    min_duration=3,
    supports_audio=True,
    supports_multi_shot=True,
    identity_lock_native=True,
    emotion_direction_native=True,
    resolution_max="2160p",
    cost_per_second=0.12,
    fal_endpoint="fal-ai/kling-video/v2/master",
    fal_endpoint_i2v="fal-ai/kling-video/v2/master/image-to-video",
)

LTX_CAPS = EngineCapability(
    engine=VideoEngine.LTX,
    max_duration=20,
    min_duration=6,
    supports_audio=True,
    supports_multi_shot=False,
    identity_lock_native=False,
    emotion_direction_native=False,
    resolution_max="2160p",
    cost_per_second=0.08,
    fal_endpoint="fal-ai/ltx-2/image-to-video/fast",
    fal_endpoint_i2v="fal-ai/ltx-2/image-to-video/fast",
)


# =============================================================================
# ROUTING DECISION
# =============================================================================

@dataclass
class RoutingDecision:
    """Output of the routing decision for a single shot."""
    shot_id: str
    engine: VideoEngine              # Primary engine selection
    reason: str                       # Why this engine was selected
    fallback_engine: Optional[VideoEngine]  # Alternate if primary fails
    dual_mode: bool                   # Generate with both engines
    estimated_cost: float             # Estimated cost in USD
    confidence: float                 # 0-1 routing confidence
    warnings: List[str] = None        # Routing warnings/notes


# =============================================================================
# ROUTING ENGINE
# =============================================================================

def route_shot(
    shot_state: Dict[str, Any],
    render_mode: str = "auto",
    explicit_engine: Optional[VideoEngine] = None,
) -> RoutingDecision:
    """
    Route a single shot to the optimal generation engine.

    Args:
        shot_state: Shot metadata dict with keys:
            - shot_id (str): unique identifier
            - shot_type (str): wide, medium, close_up, MCU, OTS, etc.
            - has_dialogue (bool): whether shot has dialogue
            - characters (list[str]): character list
            - duration (int): seconds
            - is_broll (bool): whether B-roll/insert/cutaway
            - emotion_intensity (float): 0-1 emotion magnitude
            - coverage_role (str): "A_GEOGRAPHY", "B_ACTION", "C_EMOTION"
            - render_mode (str, optional): override global render_mode
        render_mode: "ltx" | "kling" | "auto" | "dual"
        explicit_engine: Force selection to this engine (bypass routing logic)

    Returns:
        RoutingDecision with selected engine, reason, cost, confidence
    """
    warnings = []
    shot_id = shot_state.get("shot_id", "unknown")
    shot_type = (shot_state.get("shot_type") or shot_state.get("type") or "medium").lower()
    has_dialogue = shot_state.get("has_dialogue", False)
    is_broll = shot_state.get("is_broll", False)
    duration = shot_state.get("duration", 10)
    characters = shot_state.get("characters", [])
    emotion_intensity = shot_state.get("emotion_intensity", 0.5)
    coverage_role = shot_state.get("coverage_role", "B_ACTION")

    # Explicit engine override
    if explicit_engine:
        return RoutingDecision(
            shot_id=shot_id,
            engine=explicit_engine,
            reason="explicit_override",
            fallback_engine=None,
            dual_mode=False,
            estimated_cost=_estimate_cost(explicit_engine, duration),
            confidence=1.0,
            warnings=warnings,
        )

    # Render mode override
    if render_mode == "ltx":
        engine = VideoEngine.LTX
        fallback = VideoEngine.KLING
        dual = False
        reason = "render_mode_ltx_only"
    elif render_mode == "kling":
        engine = VideoEngine.KLING
        fallback = VideoEngine.LTX
        dual = False
        reason = "render_mode_kling_only"
    elif render_mode == "dual":
        engine = VideoEngine.KLING
        fallback = VideoEngine.LTX
        dual = True
        reason = "dual_mode_both_engines"
    else:
        # AUTO routing logic
        engine, fallback, dual, reason = _route_auto(
            shot_id, shot_type, has_dialogue, is_broll, duration,
            characters, emotion_intensity, coverage_role, warnings
        )

    confidence = _compute_routing_confidence(engine, shot_state)
    cost = _estimate_cost(engine, duration)
    if dual:
        cost += _estimate_cost(fallback, duration)

    return RoutingDecision(
        shot_id=shot_id,
        engine=engine,
        reason=reason,
        fallback_engine=fallback,
        dual_mode=dual,
        estimated_cost=round(cost, 3),
        confidence=round(confidence, 2),
        warnings=warnings,
    )


def _route_auto(
    shot_id: str,
    shot_type: str,
    has_dialogue: bool,
    is_broll: bool,
    duration: int,
    characters: List[str],
    emotion_intensity: float,
    coverage_role: str,
    warnings: List[str],
) -> tuple:
    """
    Auto-routing logic. Returns (engine, fallback, dual_mode, reason).

    Decision tree (highest priority first):
    1. B-roll/insert/cutaway → LTX (no character lock needed, cheaper)
    2. Dialogue + 1 character → Kling (native lip-sync + identity lock)
    3. Multi-character (2+) → Kling (better identity separation)
    4. Duration > 15s → LTX (Kling max is 15s)
    5. Hero shots (close_up, MCU, ECU) with dialogue → Kling
    6. Reaction/OTS with high emotion (>0.7) → Kling
    7. Default → LTX (cheaper, faster)
    """
    hero_types = ("close_up", "MCU", "ECU", "extreme_close_up")
    dialogue_types = ("medium", "OTS", "two_shot", "MCU")

    # Rule 1: B-roll → LTX
    if is_broll or shot_type in ("broll", "insert", "cutaway", "detail"):
        return VideoEngine.LTX, VideoEngine.KLING, False, "broll_economics"

    # Rule 2: Dialogue + 1 character → Kling (native lip-sync)
    if has_dialogue and len(characters) == 1:
        return VideoEngine.KLING, VideoEngine.LTX, False, "dialogue_single_char"

    # Rule 3: Multi-character (2+) → Kling (identity separation)
    if len(characters) >= 2:
        warnings.append(f"multi_character_{len(characters)}: Kling better for identity separation")
        return VideoEngine.KLING, VideoEngine.LTX, False, "multi_character"

    # Rule 4: Duration > 15s → LTX (Kling max is 15s)
    if duration > 15:
        warnings.append(f"duration_{duration}s: Exceeds Kling max, using LTX")
        return VideoEngine.LTX, VideoEngine.KLING, False, "duration_constraint"

    # Rule 5: Hero dialogue shots → Kling
    if shot_type in hero_types and has_dialogue and characters:
        return VideoEngine.KLING, VideoEngine.LTX, False, "hero_dialogue"

    # Rule 6: High-emotion reaction/OTS → Kling (emotion direction works better)
    if shot_type in ("reaction", "OTS") and emotion_intensity > 0.7 and has_dialogue:
        return VideoEngine.KLING, VideoEngine.LTX, False, "high_emotion_dialogue"

    # Rule 7: Default → LTX (cheaper, faster)
    return VideoEngine.LTX, VideoEngine.KLING, False, "default_economics"


def _compute_routing_confidence(engine: VideoEngine, shot_state: Dict[str, Any]) -> float:
    """
    Compute 0-1 confidence score for the routing decision.
    Factors: character count, dialogue, emotion intensity, duration, refs available.
    """
    confidence = 0.5  # baseline
    has_dialogue = shot_state.get("has_dialogue", False)
    characters = shot_state.get("characters", [])
    has_refs = shot_state.get("has_refs", False)
    emotion_intensity = shot_state.get("emotion_intensity", 0.5)
    duration = shot_state.get("duration", 10)

    if engine == VideoEngine.KLING:
        # Kling confidence boosts
        if has_dialogue and has_refs:
            confidence += 0.25
        if len(characters) > 0:
            confidence += 0.15
        if emotion_intensity > 0.6:
            confidence += 0.1
    else:  # LTX
        # LTX confidence boosts
        if duration <= 15:
            confidence += 0.15
        if not has_dialogue:
            confidence += 0.2
        if len(characters) == 0:
            confidence += 0.1

    return min(1.0, confidence)


def _estimate_cost(engine: VideoEngine, duration: int) -> float:
    """Estimate generation cost in USD for a single shot."""
    if engine == VideoEngine.KLING:
        return KLING_CAPS.cost_per_second * duration
    else:  # LTX
        return LTX_CAPS.cost_per_second * duration


# =============================================================================
# SCENE ROUTING
# =============================================================================

def route_scene(
    shots: List[Dict[str, Any]],
    render_mode: str = "auto",
) -> List[RoutingDecision]:
    """
    Route all shots in a scene.

    Args:
        shots: List of shot state dicts
        render_mode: "ltx" | "kling" | "auto" | "dual"

    Returns:
        List of RoutingDecision objects (one per shot, preserving order)
    """
    decisions = []
    for shot in shots:
        decision = route_shot(shot, render_mode=render_mode)
        decisions.append(decision)
    return decisions


def estimate_scene_cost(decisions: List[RoutingDecision]) -> Dict[str, Any]:
    """
    Compute total cost and breakdown by engine for a scene.

    Args:
        decisions: List of RoutingDecision objects

    Returns:
        Dict with total cost, per-engine breakdown, shot counts
    """
    kling_cost = 0.0
    ltx_cost = 0.0
    kling_shots = 0
    ltx_shots = 0
    dual_shots = 0

    for decision in decisions:
        if decision.dual_mode:
            kling_cost += decision.estimated_cost / 2  # Split cost
            ltx_cost += decision.estimated_cost / 2
            dual_shots += 1
        elif decision.engine == VideoEngine.KLING:
            kling_cost += decision.estimated_cost
            kling_shots += 1
        else:  # LTX
            ltx_cost += decision.estimated_cost
            ltx_shots += 1

    total_cost = kling_cost + ltx_cost

    return {
        "total_cost": round(total_cost, 2),
        "kling_cost": round(kling_cost, 2),
        "ltx_cost": round(ltx_cost, 2),
        "kling_shots": kling_shots,
        "ltx_shots": ltx_shots,
        "dual_shots": dual_shots,
        "total_shots": len(decisions),
        "avg_cost_per_shot": round(total_cost / len(decisions) if decisions else 0, 2),
    }


# =============================================================================
# FAL ENDPOINTS AND UTILITIES
# =============================================================================

def get_fal_endpoint(engine: VideoEngine, mode: str = "i2v") -> str:
    """
    Get the FAL API endpoint string for a given engine.

    Args:
        engine: VideoEngine.LTX or VideoEngine.KLING
        mode: "text_to_video" or "image_to_video"

    Returns:
        FAL endpoint string (fal-ai/...)
    """
    if engine == VideoEngine.KLING:
        if mode == "i2v":
            return KLING_CAPS.fal_endpoint_i2v
        return KLING_CAPS.fal_endpoint
    else:  # LTX
        if mode == "i2v":
            return LTX_CAPS.fal_endpoint_i2v
        return LTX_CAPS.fal_endpoint


def clamp_duration(engine: VideoEngine, duration: int) -> int:
    """
    Clamp duration to engine's supported range.

    Args:
        engine: VideoEngine.LTX or VideoEngine.KLING
        duration: Requested duration in seconds

    Returns:
        Clamped duration (min_duration ≤ result ≤ max_duration)
    """
    caps = KLING_CAPS if engine == VideoEngine.KLING else LTX_CAPS
    return max(caps.min_duration, min(caps.max_duration, duration))


def get_engine_capabilities(engine: VideoEngine) -> EngineCapability:
    """Get full capability specification for an engine."""
    return KLING_CAPS if engine == VideoEngine.KLING else LTX_CAPS


# =============================================================================
# VALIDATION AND DIAGNOSTICS
# =============================================================================

def validate_routing_decision(decision: RoutingDecision, shot_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a routing decision against shot constraints.

    Returns:
        Dict with keys: valid (bool), violations (list[str]), warnings (list[str])
    """
    violations = []
    warnings = list(decision.warnings) if decision.warnings else []
    caps = get_engine_capabilities(decision.engine)
    duration = shot_state.get("duration", 10)
    has_dialogue = shot_state.get("has_dialogue", False)
    characters = shot_state.get("characters", [])

    # Duration must fit engine
    clamped = clamp_duration(decision.engine, duration)
    if clamped != duration:
        warnings.append(f"duration_clamped: {duration}s → {clamped}s (engine limit)")

    # Dialogue without native support
    if has_dialogue and decision.engine == VideoEngine.LTX:
        warnings.append("ltx_dialogue: LTX does not have native lip-sync; may need manual sync pass")

    # Multi-character without native identity lock
    if len(characters) > 1 and decision.engine == VideoEngine.LTX:
        warnings.append(f"ltx_multi_char_{len(characters)}: LTX lacks native identity separation; consider Kling")

    # Very high emotion without native emotion direction
    if shot_state.get("emotion_intensity", 0.5) > 0.8 and decision.engine == VideoEngine.LTX:
        warnings.append("ltx_high_emotion: LTX may not respond well to emotion language; Kling recommended")

    valid = len(violations) == 0

    return {
        "valid": valid,
        "violations": violations,
        "warnings": warnings,
        "duration_clamped": clamp_duration(decision.engine, duration),
        "engine_cap_check": {
            "duration_range": f"{caps.min_duration}-{caps.max_duration}s",
            "supports_audio": caps.supports_audio,
            "supports_multi_shot": caps.supports_multi_shot,
            "identity_lock_native": caps.identity_lock_native,
        }
    }


# =============================================================================
# MAIN ENTRY POINT FOR CONTROLLER
# =============================================================================

def route_for_generation(
    shot_or_shots: Any,
    render_mode: str = "auto",
    explicit_engine: Optional[VideoEngine] = None,
) -> Any:
    """
    Top-level entry point for routing decisions.

    Accepts both single shot dict or list of shot dicts.
    Non-blocking: if routing fails, defaults to LTX with warning.

    Args:
        shot_or_shots: Dict or List[Dict] of shot state
        render_mode: "ltx" | "kling" | "auto" | "dual"
        explicit_engine: Force selection (VideoEngine.LTX or VideoEngine.KLING)

    Returns:
        RoutingDecision or List[RoutingDecision], never raises exception
    """
    try:
        if isinstance(shot_or_shots, list):
            return route_scene(shot_or_shots, render_mode=render_mode)
        else:
            return route_shot(shot_or_shots, render_mode=render_mode, explicit_engine=explicit_engine)
    except Exception as e:
        logger.exception(f"Model router failed: {e}, defaulting to LTX")
        # Fallback: return safe default routing
        shot_id = shot_or_shots.get("shot_id", "unknown") if isinstance(shot_or_shots, dict) else "batch"
        return RoutingDecision(
            shot_id=shot_id,
            engine=VideoEngine.LTX,
            reason="fallback_on_error",
            fallback_engine=None,
            dual_mode=False,
            estimated_cost=0.1,
            confidence=0.3,
            warnings=[f"Routing error: {str(e)}", "Defaulted to LTX engine"],
        )
