"""
ATLAS V25.8 — RENDER STRATEGY MAP (Behavioral Decision Layer)
==============================================================
This module is the BEHAVIORAL BRAIN for rendering decisions. It answers:
  1. Does this shot CHAIN to the previous shot's end frame?
  2. Can this shot render in PARALLEL with other scenes?
  3. Does this shot need EXTENSION beyond 20s?
  4. What ANGLE does coverage role dictate?
  5. What is the OPTIMAL rendering path for each shot?

The strategy map reads shot_plan + coverage roles + blocking points and
produces a RenderStrategy per shot that the pipeline follows blindly.

Brain mapping:
  - Basal ganglia: action selection (chain vs independent vs extend)
  - Motor cortex: execution path (which API call, which params)
  - Cerebellum: timing (parallel groups, sequential dependencies)

INTEGRATION POINTS:
  - master_shot_chain_agent.py reads strategies before rendering
  - extended_video_stitch_agent.py reads extension plans
  - orchestrator_server.py chain pipeline checks can_parallel
  - continuity_memory.py dependency graph aligns with strategy groups

Usage:
  from tools.render_strategy_map import build_render_strategies, RenderStrategy
  strategies = build_render_strategies(shots, scene_manifest)
  for shot_id, strategy in strategies.items():
      if strategy.needs_extension:
          # Use LTX extend-video
      elif strategy.chains_to:
          # Wait for previous shot's end frame
      else:
          # Render independently (can parallel)
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# RENDER PATH TYPES
# ============================================================================

class RenderPath(str, Enum):
    """How a shot gets rendered."""
    ANCHOR = "anchor"           # First shot in scene — generates from text/refs
    CHAIN = "chain"             # Chained to previous — uses end-frame as source
    INDEPENDENT = "independent" # No dependency — can render any time
    EXTEND = "extend"           # Needs extension beyond 20s (LTX extend-video)
    SKIP = "skip"               # Editorial: reuse frame, hold, or overlay


class ParallelGroup(str, Enum):
    """What parallel bucket a shot belongs to."""
    SCENE_CHAIN = "scene_chain"       # Sequential within scene (blocking deps)
    SCENE_BROLL = "scene_broll"       # Parallel B-roll within scene
    SCENE_INDEPENDENT = "scene_indep" # Parallel inserts/cutaways within scene
    CROSS_SCENE = "cross_scene"       # Can parallel with other scenes entirely


# ============================================================================
# COVERAGE → ANGLE MAPPING (from V25.7)
# ============================================================================

COVERAGE_TO_ANGLE = {
    "A_GEOGRAPHY": {
        "name": "wide_geography",
        "focal": 24,
        "framing": "ultra-wide establishing — full environment visible, characters in context",
        "ltx_prefix": "Wide shot, full environment visible,",
    },
    "B_ACTION": {
        "name": "medium_action",
        "focal": 50,
        "framing": "medium standard — character action framed waist-up, environment contextual",
        "ltx_prefix": "Medium shot, character action visible,",
    },
    "C_EMOTION": {
        "name": "close_emotion",
        "focal": 100,
        "framing": "telephoto close-up — face fills frame, emotion reads clearly",
        "ltx_prefix": "Close-up, face fills frame, emotion visible,",
    },
}

# ============================================================================
# MODEL CAPABILITIES — Kling and LTX operate DIFFERENTLY
# ============================================================================

@dataclass
class ModelCapabilities:
    """What each video model can and cannot do."""
    name: str
    fal_model_id: str
    max_single_duration: float      # max seconds per generation
    min_duration: float             # minimum seconds
    duration_options: List[float]   # available duration choices
    has_extend_api: bool            # can extend existing video
    has_camera_control: bool        # can control camera via prompt
    has_native_audio: bool          # generates audio with video
    cost_per_second: float          # $ per second of output
    extend_model_id: str = ""       # fal model for extending
    extend_max_per_call: float = 0  # max seconds per extend call
    extend_cost_per_second: float = 0.0
    max_fps: int = 25
    max_resolution: str = "1080p"
    notes: str = ""


LTX_MODEL = ModelCapabilities(
    name="LTX-2.3",
    fal_model_id="fal-ai/ltx-2.3/image-to-video/fast",
    max_single_duration=20,
    min_duration=6,
    duration_options=[6, 8, 10, 12, 14, 16, 18, 20],
    has_extend_api=True,
    extend_model_id="fal-ai/ltx-2.3/extend-video",
    extend_max_per_call=20,
    has_camera_control=False,       # camera is in the PROMPT only
    has_native_audio=True,
    cost_per_second=0.04,           # $0.04/s at 1080p
    extend_cost_per_second=0.10,    # $0.10/s for extensions
    max_fps=25,
    max_resolution="1080p",         # >10s locked to 1080p/25fps
    notes="Durations >10s locked to 25fps+1080p. Extend-video reads context frames for seamless continuation.",
)

KLING_MODEL = ModelCapabilities(
    name="Kling 3.0",
    fal_model_id="fal-ai/kling-video/v3/standard/image-to-video",
    max_single_duration=15,         # Kling 3.0 standard: 3-15s
    min_duration=3,
    duration_options=[3, 5, 8, 10, 15],
    has_extend_api=False,           # No extend endpoint on FAL
    extend_model_id="",
    extend_max_per_call=0,
    has_camera_control=True,        # Prompt-based camera control (pan, orbit, dolly)
    has_native_audio=True,
    cost_per_second=0.084,          # $0.084/s without audio
    extend_cost_per_second=0.0,
    max_fps=30,
    max_resolution="1080p",
    notes="Camera control via natural language in prompt. No extend API on FAL — long shots need segment approach.",
)

KLING_PRO_MODEL = ModelCapabilities(
    name="Kling 2.6 Pro",
    fal_model_id="fal-ai/kling-video/v2.6/pro/image-to-video",
    max_single_duration=10,         # Kling 2.6 Pro: 5 or 10s
    min_duration=5,
    duration_options=[5, 10],
    has_extend_api=False,
    extend_model_id="",
    extend_max_per_call=0,
    has_camera_control=False,       # No explicit camera params in 2.6 Pro
    has_native_audio=True,
    cost_per_second=0.07,           # $0.07/s without audio
    extend_cost_per_second=0.0,
    max_fps=30,
    max_resolution="1080p",
    notes="Higher quality per frame than 3.0 standard but shorter max duration.",
)

# Registry
MODEL_REGISTRY: Dict[str, ModelCapabilities] = {
    "ltx": LTX_MODEL,
    "kling": KLING_MODEL,
    "kling_pro": KLING_PRO_MODEL,
}

def get_model(model_key: str = "ltx") -> ModelCapabilities:
    """Get model capabilities by key. Defaults to LTX."""
    return MODEL_REGISTRY.get(model_key, LTX_MODEL)


# Shot types that NEVER chain (independent visual contexts)
NO_CHAIN_TYPES = frozenset([
    "insert", "b-roll", "b_roll", "broll", "cutaway",
    "detail", "atmosphere", "montage", "title", "transition",
])

# Transition keywords that break chains
CHAIN_BREAK_TRANSITIONS = frozenset([
    "cut to", "smash cut", "fade", "dissolve", "wipe",
])

# V.O./cross-location keywords that break chains
CROSS_LOCATION_KEYWORDS = frozenset([
    "v.o.", "vo", "voice over", "phone", "intercut", "cross-cutting",
])


# ============================================================================
# RENDER STRATEGY (per-shot decision)
# ============================================================================

@dataclass
class RenderStrategy:
    """Complete rendering decision for a single shot."""
    shot_id: str
    scene_id: str

    # Core decisions
    render_path: str = "independent"        # RenderPath value
    parallel_group: str = "cross_scene"     # ParallelGroup value
    chains_to: Optional[str] = None         # shot_id this depends on (end-frame source)
    chain_position: int = 0                 # 0=independent, 1+=position in chain

    # Coverage-driven angle
    coverage_role: str = ""                 # A_GEOGRAPHY, B_ACTION, C_EMOTION
    target_focal: int = 50                  # mm equivalent from coverage
    target_framing: str = ""                # human-readable framing direction
    ltx_framing_prefix: str = ""            # injected into LTX prompt

    # Extension decision
    needs_extension: bool = False           # True if duration exceeds model max
    total_duration: float = 0.0             # target total duration
    base_duration: float = 0.0             # first render duration (≤ model max)
    extension_steps: int = 0                # number of extend-video calls needed
    extension_method: str = ""              # "ltx_extend" or "ffmpeg_concat" or ""
    extension_cost: float = 0.0             # estimated $ for extensions

    # Model assignment
    video_model: str = "ltx"                # which model renders this shot
    model_max_duration: float = 20.0        # model's max single render
    model_cost_per_sec: float = 0.04        # model's cost

    # Flags
    is_anchor: bool = False                 # first shot in scene
    is_broll: bool = False                  # B-roll or insert
    is_intercut: bool = False               # cross-location intercut
    has_characters: bool = False            # character shot (needs face lock)
    has_dialogue: bool = False              # dialogue shot (needs lip sync)
    can_parallel: bool = True               # can render alongside other groups

    # Editorial hints (Phase 2 integration)
    editorial_skip: bool = False            # editorial says skip gen (frame reuse)
    editorial_hold: bool = False            # editorial says extend via hold
    reuse_frame_from: Optional[str] = None  # shot_id to reuse frame from

    # Reasoning (for logs/debug)
    reasoning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# STRATEGY BUILDER — THE DECISION ENGINE
# ============================================================================

def build_render_strategies(
    shots: List[dict],
    scene_manifest: Optional[dict] = None,
    video_model: str = "ltx",
) -> Dict[str, RenderStrategy]:
    """
    Build a RenderStrategy for every shot in the plan.

    This is the behavioral decision layer. It reads:
    - shot.coverage_role → angle/framing
    - shot.duration → extension plan (MODEL-AWARE)
    - shot._broll, _no_chain, _intercut → chain/parallel decisions
    - shot.characters, dialogue → face lock and lip sync needs
    - shot.shot_type → independent vs chain classification

    Model differences:
    - LTX: max 20s per render, HAS extend-video API for seamless continuation
    - Kling 3.0: max 15s per render, NO extend API — must use FFmpeg concat
    - Kling Pro: max 10s per render, NO extend API — must use FFmpeg concat

    Returns dict of shot_id → RenderStrategy.
    """
    from collections import defaultdict

    model = get_model(video_model)
    strategies: Dict[str, RenderStrategy] = {}

    # Group shots by scene
    scenes = defaultdict(list)
    for s in shots:
        scenes[s.get("scene_id", "?")].append(s)

    for scene_id in sorted(scenes.keys()):
        scene_shots = scenes[scene_id]
        last_chained_id = None
        chain_pos = 0

        for i, shot in enumerate(scene_shots):
            sid = shot.get("shot_id", "?")
            strat = RenderStrategy(shot_id=sid, scene_id=scene_id)

            # Model assignment
            strat.video_model = video_model
            strat.model_max_duration = model.max_single_duration
            strat.model_cost_per_sec = model.cost_per_second

            # === BASIC SHOT PROPERTIES ===
            strat.total_duration = shot.get("duration", shot.get("duration_seconds", 10))
            strat.has_characters = bool(shot.get("characters") or [])
            strat.has_dialogue = bool(
                (shot.get("dialogue_text") or shot.get("dialogue") or "").strip()
            )
            strat.is_intercut = bool(shot.get("_intercut"))
            strat.is_broll = bool(
                shot.get("_broll", False) or shot.get("_no_chain", False)
            )  # V26 DOCTRINE: suffixes are editorial, not runtime

            # === COVERAGE ROLE → ANGLE ===
            cr = shot.get("coverage_role", "")
            if cr in COVERAGE_TO_ANGLE:
                angle = COVERAGE_TO_ANGLE[cr]
                strat.coverage_role = cr
                strat.target_focal = angle["focal"]
                strat.target_framing = angle["framing"]
                strat.ltx_framing_prefix = angle["ltx_prefix"]

            # === EXTENSION DECISION (MODEL-AWARE) ===
            if strat.total_duration > model.max_single_duration and not strat.is_broll:
                strat.needs_extension = True
                strat.base_duration = min(strat.total_duration, model.max_single_duration)
                remaining = strat.total_duration - strat.base_duration

                if model.has_extend_api:
                    # LTX: use extend-video API (seamless, model reads context)
                    strat.extension_method = "ltx_extend"
                    max_per_ext = model.extend_max_per_call
                    strat.extension_steps = min(
                        3,  # max 3 extensions (quality cap)
                        int((remaining + max_per_ext - 1) // max_per_ext)
                    )
                    actual_ext_secs = min(remaining, max_per_ext * 3)
                    strat.extension_cost = actual_ext_secs * model.extend_cost_per_second
                else:
                    # Kling: no extend API — must use FFmpeg segment concat
                    strat.extension_method = "ffmpeg_concat"
                    max_seg = model.max_single_duration
                    strat.extension_steps = int((remaining + max_seg - 1) // max_seg)
                    # Segments cost the same as rendering (no extend premium)
                    strat.extension_cost = remaining * model.cost_per_second
            else:
                strat.base_duration = strat.total_duration

            # === CHAIN / PARALLEL / INDEPENDENT DECISION ===
            shot_type = (shot.get("shot_type") or "").lower()

            # Decision 1: Is this the scene anchor (first shot)?
            if i == 0:
                strat.is_anchor = True
                strat.render_path = RenderPath.ANCHOR.value
                strat.parallel_group = ParallelGroup.CROSS_SCENE.value
                strat.can_parallel = True
                strat.chain_position = 0
                chain_pos = 1
                last_chained_id = sid
                strat.reasoning = "Scene anchor — renders from text/refs, can parallel with other scenes"

            # Decision 2: B-roll = always independent
            elif strat.is_broll or shot.get("_no_chain"):
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_BROLL.value
                strat.can_parallel = True
                strat.chain_position = 0
                strat.reasoning = "B-roll/no-chain — independent visual context"

            # Decision 3: Intercut = never chain (cross-location)
            elif strat.is_intercut:
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                strat.chain_position = 0
                strat.reasoning = "Intercut — cross-location, cannot chain"

            # Decision 4: Insert/cutaway/detail = independent
            elif any(t in shot_type for t in NO_CHAIN_TYPES):
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                strat.chain_position = 0
                strat.reasoning = f"Shot type '{shot_type}' — independent insert"

            # Decision 5: Establishing without characters = independent
            elif ("establishing" in shot_type or "master" in shot_type):
                if not strat.has_characters or not strat.has_dialogue:
                    strat.render_path = RenderPath.INDEPENDENT.value
                    strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                    strat.can_parallel = True
                    strat.reasoning = "Establishing/master without characters — new visual context"
                # else: establishing WITH characters falls through to chain logic

            # Decision 6: No characters = no blocking to chain
            elif not strat.has_characters:
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                strat.reasoning = "No characters — no blocking continuity needed"

            # Decision 7: Location change = chain break
            elif _locations_differ(shot, scene_shots[i - 1] if i > 0 else {}):
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                strat.reasoning = "Location change from previous shot — chain breaks"

            # Decision 8: V.O./phone keywords = chain break
            elif _has_cross_location_keywords(shot):
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                strat.reasoning = "V.O./phone/intercut keywords — cross-location"

            # Decision 9: Transition keyword = chain break
            elif _has_transition_break(shot):
                strat.render_path = RenderPath.INDEPENDENT.value
                strat.parallel_group = ParallelGroup.SCENE_INDEPENDENT.value
                strat.can_parallel = True
                last_chained_id = None
                chain_pos = 0
                strat.reasoning = "Transition keyword breaks chain"

            # Decision 10: Character shot in same location = CHAIN
            else:
                if last_chained_id:
                    strat.render_path = RenderPath.CHAIN.value
                    strat.parallel_group = ParallelGroup.SCENE_CHAIN.value
                    strat.chains_to = last_chained_id
                    strat.chain_position = chain_pos
                    strat.can_parallel = False
                    chain_pos += 1
                    last_chained_id = sid
                    strat.reasoning = (
                        f"Character shot chains to {strat.chains_to} "
                        f"(blocking continuity, position #{strat.chain_position})"
                    )
                else:
                    # No previous chain anchor — start new chain
                    strat.render_path = RenderPath.ANCHOR.value
                    strat.parallel_group = ParallelGroup.SCENE_CHAIN.value
                    strat.can_parallel = True
                    chain_pos = 1
                    last_chained_id = sid
                    strat.reasoning = "New chain anchor (no previous chain source)"

            # Override: extension flag
            if strat.needs_extension:
                strat.render_path = RenderPath.EXTEND.value
                strat.reasoning += f" + EXTENDS to {strat.total_duration}s ({strat.extension_steps} steps)"

            # Editorial hints (read but don't override — Phase 2)
            if shot.get("_editorial_skip_gen"):
                strat.editorial_skip = True
            if shot.get("_reuse_frame_from"):
                strat.reuse_frame_from = shot["_reuse_frame_from"]
            if shot.get("_hold_extension"):
                strat.editorial_hold = True

            strategies[sid] = strat

    return strategies


# ============================================================================
# ANALYSIS / REPORTING
# ============================================================================

def analyze_render_plan(strategies: Dict[str, RenderStrategy]) -> dict:
    """
    Produce a summary of the rendering plan.
    Useful for pre-run review and cost estimation.
    """
    total = len(strategies)
    anchors = sum(1 for s in strategies.values() if s.is_anchor)
    chained = sum(1 for s in strategies.values() if s.render_path == "chain")
    independent = sum(1 for s in strategies.values() if s.render_path == "independent")
    extending = sum(1 for s in strategies.values() if s.needs_extension)
    parallel_ok = sum(1 for s in strategies.values() if s.can_parallel)
    sequential = total - parallel_ok

    ext_cost = sum(s.extension_cost for s in strategies.values())
    ext_duration = sum(s.total_duration - s.base_duration for s in strategies.values() if s.needs_extension)

    # Group by scene
    scenes = {}
    for s in strategies.values():
        if s.scene_id not in scenes:
            scenes[s.scene_id] = {"chain": 0, "independent": 0, "broll": 0, "extend": 0}
        if s.render_path == "chain":
            scenes[s.scene_id]["chain"] += 1
        elif s.is_broll:
            scenes[s.scene_id]["broll"] += 1
        elif s.needs_extension:
            scenes[s.scene_id]["extend"] += 1
        else:
            scenes[s.scene_id]["independent"] += 1

    return {
        "total_shots": total,
        "anchors": anchors,
        "chained": chained,
        "independent": independent,
        "extending": extending,
        "can_parallel": parallel_ok,
        "must_sequential": sequential,
        "extension_cost_estimate": round(ext_cost, 2),
        "extension_seconds": round(ext_duration, 1),
        "per_scene": scenes,
    }


def print_render_plan(strategies: Dict[str, RenderStrategy]) -> str:
    """Format render plan as readable text for logging/review."""
    lines = ["═══ ATLAS RENDER STRATEGY MAP ═══", ""]
    analysis = analyze_render_plan(strategies)

    lines.append(f"Total shots: {analysis['total_shots']}")
    lines.append(f"  Anchors: {analysis['anchors']}")
    lines.append(f"  Chained: {analysis['chained']} (sequential — blocking deps)")
    lines.append(f"  Independent: {analysis['independent']} (can parallel)")
    lines.append(f"  Need extension: {analysis['extending']} (LTX extend-video)")
    lines.append(f"  Extension cost: ${analysis['extension_cost_estimate']:.2f}")
    lines.append(f"  Extension seconds: {analysis['extension_seconds']:.0f}s")
    lines.append("")

    # Per-scene breakdown
    for scene_id in sorted(analysis["per_scene"].keys()):
        sc = analysis["per_scene"][scene_id]
        lines.append(f"  Scene {scene_id}: chain={sc['chain']} indep={sc['independent']} broll={sc['broll']} extend={sc['extend']}")

    lines.append("")
    lines.append("Per-shot decisions:")
    for sid in sorted(strategies.keys()):
        s = strategies[sid]
        chain_info = f" → chains to {s.chains_to}" if s.chains_to else ""
        ext_info = f" [+{s.extension_steps} extends]" if s.needs_extension else ""
        coverage = f" [{s.coverage_role} {s.target_focal}mm]" if s.coverage_role else ""
        lines.append(f"  {sid}: {s.render_path}{chain_info}{ext_info}{coverage}")

    return "\n".join(lines)


# ============================================================================
# HELPERS
# ============================================================================

def _norm_location(loc: str) -> str:
    """Normalize location string for comparison."""
    loc = (loc or "").lower().strip()
    loc = re.sub(r'^(int\.|ext\.|int/ext\.)\s*', '', loc)
    loc = loc.replace('–', '-').replace('—', '-')
    loc = re.sub(r'\s*-\s*(night|day|dawn|dusk|evening|morning|continuous|same|later)\s*$', '', loc)
    return re.sub(r'\s+', ' ', loc).strip()


def _locations_differ(shot_a: dict, shot_b: dict) -> bool:
    """Check if two shots are in different locations."""
    loc_a = _norm_location(shot_a.get("location", ""))
    loc_b = _norm_location(shot_b.get("location", ""))
    if not loc_a or not loc_b:
        return False
    if loc_a == loc_b:
        return False
    # Fuzzy: if one contains the other, treat as same
    if loc_a in loc_b or loc_b in loc_a:
        return False
    return True


def _has_cross_location_keywords(shot: dict) -> bool:
    """Check if shot has V.O./phone/intercut keywords."""
    dialogue = (shot.get("dialogue") or shot.get("dialogue_text") or "").lower()
    notes = (shot.get("notes") or shot.get("beat_text") or "").lower()
    combined = dialogue + " " + notes
    return any(kw in combined for kw in CROSS_LOCATION_KEYWORDS)


def _has_transition_break(shot: dict) -> bool:
    """Check if shot has a chain-breaking transition."""
    transition = (shot.get("transition") or "").lower()
    return any(t in transition for t in CHAIN_BREAK_TRANSITIONS)


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path

    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
    repo = Path(__file__).parent.parent
    plan_path = repo / "pipeline_outputs" / project / "shot_plan.json"

    if not plan_path.exists():
        print(f"No shot_plan.json found for {project}")
        sys.exit(1)

    with open(plan_path) as f:
        data = json.load(f)

    shots = data.get("shots", [])
    strategies = build_render_strategies(shots)
    print(print_render_plan(strategies))
    print()
    analysis = analyze_render_plan(strategies)
    print(json.dumps(analysis, indent=2))
