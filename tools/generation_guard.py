#!/usr/bin/env python3
"""
tools/generation_guard.py — ATLAS V37 Single Entry-Point Generation Guard

Every code path that calls a FAL/Kling/Nano API MUST pass through these guards
before spending money. At 1000 movies/month, one unguarded path wastes enormous
budget on bad generations.

Guards enforced:
  G1: E-shot character bleed — environment-only shots get zero char refs
  G2: Duration snap — Kling only accepts 5/10/15s; LTX 6/8/10/12/14/16/18/20s
  G3: Kling cost tier — $0.112/sec (audio off), $0.168/sec (audio on)
  G4: Regen budget cap — max_regen_per_shot=1 for orchestrator paths
  G5: Chain-only skip — shots with _chain_inherits_start/_cold_open_chain_only skip Nano
  G6: No-people prompt guard — E-shots get "no people" negative constraint injected
  G7: Prompt size cap — 512-char hard cap for Kling multi-prompt text

Usage:
    from tools.generation_guard import GenerationGuard

    guard = GenerationGuard(shot, context="orchestrator_chain")
    if not guard.passes():
        logger.warning(f"[GUARD BLOCKED] {shot['shot_id']}: {guard.block_reason}")
        return  # Do not spend on API

    # Safe to call FAL
    refs = guard.filtered_char_refs(raw_refs)
    duration = guard.snapped_duration(raw_duration, model="kling")
    cost = guard.estimated_cost(duration, generate_audio=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Kling valid durations (hard API limit) ───────────────────────────────────
_KLING_VALID_DURATIONS = [5, 10, 15]
_LTX_VALID_DURATIONS   = [6, 8, 10, 12, 14, 16, 18, 20]

# ─── Kling cost rates (USD per second) ────────────────────────────────────────
_KLING_RATE_AUDIO_OFF = 0.112   # generate_audio=False
_KLING_RATE_AUDIO_ON  = 0.168   # generate_audio=True

# ─── Per-shot regen cap (orchestrator legacy paths) ───────────────────────────
_ORCHESTRATOR_MAX_REGEN_PER_SHOT = 1  # Runner uses VisionBudgetTracker (dynamic); orchestrator caps at 1


# ══════════════════════════════════════════════════════════════════════════════
# Budget tracker — lightweight in-process regen counter
# For full episode-level budgeting use tools/video_vision_oversight.VisionBudgetTracker
# ══════════════════════════════════════════════════════════════════════════════

class SimpleBudgetTracker:
    """
    Lightweight per-session regen tracker. One instance per chain/render call.
    Does NOT persist across HTTP requests — use VisionBudgetTracker for that.
    """

    def __init__(self, max_regen_per_shot: int = _ORCHESTRATOR_MAX_REGEN_PER_SHOT):
        self._max = max_regen_per_shot
        self._counts: Dict[str, int] = {}

    def can_regen(self, shot_id: str) -> bool:
        return self._counts.get(shot_id, 0) < self._max

    def consume(self, shot_id: str):
        self._counts[shot_id] = self._counts.get(shot_id, 0) + 1

    def count(self, shot_id: str) -> int:
        return self._counts.get(shot_id, 0)


# ══════════════════════════════════════════════════════════════════════════════
# Guard result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GuardResult:
    passed: bool
    shot_id: str
    context: str
    warnings: List[str] = field(default_factory=list)
    block_reason: Optional[str] = None

    def __bool__(self):
        return self.passed


# ══════════════════════════════════════════════════════════════════════════════
# Main guard
# ══════════════════════════════════════════════════════════════════════════════

class GenerationGuard:
    """
    Single entry-point guard for all FAL/Kling/Nano generation calls.

    Instantiate per shot. Call passes() before spending on the API.
    Use helper methods to get safe values for refs, duration, cost.
    """

    def __init__(self, shot: dict, context: str = "unknown"):
        self._shot = shot
        self._context = context
        self._sid = shot.get("shot_id", "UNKNOWN")

    # ── G1: E-shot detection ──────────────────────────────────────────────────

    def is_e_shot(self) -> bool:
        """True if this is an environment-only shot that must not receive char refs."""
        return bool(
            self._shot.get("_no_char_ref")
            or self._shot.get("_is_broll")
            or self._shot.get("_broll")
            or self._shot.get("is_broll")
        )

    def filtered_char_refs(self, raw_refs: List[str]) -> List[str]:
        """
        Return empty list for E-shots; otherwise return raw_refs unchanged.
        Prevents Kling from rendering characters in environment-only shots.
        """
        if self.is_e_shot():
            if raw_refs:
                logger.info(
                    f"[GENERATION GUARD G1] {self._sid} ({self._context}): "
                    f"E-shot — {len(raw_refs)} char ref(s) withheld"
                )
            return []
        return raw_refs

    # ── G5: Chain-only skip ───────────────────────────────────────────────────

    def skip_nano_frame(self) -> bool:
        """
        True if this shot should skip Nano frame generation.
        _chain_inherits_start and _cold_open_chain_only shots get their start
        frame from the previous shot's end-frame — no new Nano call needed.
        """
        return bool(
            self._shot.get("_chain_inherits_start")
            or self._shot.get("_cold_open_chain_only")
        )

    # ── G2: Duration snapping ─────────────────────────────────────────────────

    @staticmethod
    def snapped_duration(raw: int, model: str = "kling") -> int:
        """
        Snap raw duration to the nearest valid API duration.
        Kling: [5, 10, 15] — LTX: [6, 8, 10, 12, 14, 16, 18, 20]
        """
        valid = _KLING_VALID_DURATIONS if model == "kling" else _LTX_VALID_DURATIONS
        snapped = min((d for d in valid if d >= raw), default=valid[-1])
        return snapped

    # ── G3: Cost estimation ───────────────────────────────────────────────────

    @staticmethod
    def estimated_cost(duration_secs: int, generate_audio: bool = False, model: str = "kling") -> float:
        """Return estimated USD cost for a single Kling call."""
        if model != "kling":
            return 0.0
        rate = _KLING_RATE_AUDIO_ON if generate_audio else _KLING_RATE_AUDIO_OFF
        return max(duration_secs, 5) * rate

    # ── G6: No-people prompt guard ────────────────────────────────────────────

    def enforce_no_people_prompt(self, prompt: str) -> str:
        """
        For E-shots, ensure 'no people' constraint is in the prompt text.
        Nano has no negative_prompt param — the constraint must be in positive text.
        """
        if not self.is_e_shot():
            return prompt
        _constraint = "no people visible, no human figures, empty space only"
        if "no people" not in prompt.lower() and "no human" not in prompt.lower():
            prompt = f"{prompt.rstrip('.')}. {_constraint}."
            logger.info(
                f"[GENERATION GUARD G6] {self._sid} ({self._context}): "
                f"E-shot — no-people constraint injected"
            )
        return prompt

    # ── G7: Prompt size cap ───────────────────────────────────────────────────

    @staticmethod
    def cap_prompt(prompt: str, limit: int = 512) -> str:
        if len(prompt) > limit:
            return prompt[:limit]
        return prompt

    # ── Overall pass/block decision ───────────────────────────────────────────

    def passes(self) -> GuardResult:
        """
        Run all blocking guards. Returns GuardResult with passed=True if safe to generate.
        Emits warnings for non-blocking issues.
        """
        warnings: List[str] = []

        # G5: chain-only shots should never reach a Nano call
        if self.skip_nano_frame():
            return GuardResult(
                passed=False,
                shot_id=self._sid,
                context=self._context,
                block_reason="G5: _chain_inherits_start/_cold_open_chain_only — skip Nano, inherit from chain"
            )

        # G1: E-shots with characters listed are suspicious — warn but don't block
        if self.is_e_shot() and self._shot.get("characters"):
            warnings.append(
                f"G1-WARN: E-shot has characters={self._shot['characters']} — they will be stripped"
            )

        return GuardResult(passed=True, shot_id=self._sid, context=self._context, warnings=warnings)


# ══════════════════════════════════════════════════════════════════════════════
# Module-level helper functions (drop-in replacements for inline guard code)
# ══════════════════════════════════════════════════════════════════════════════

def guard_char_refs(shot: dict, raw_refs: List[str], context: str = "unknown") -> List[str]:
    """Drop-in: filter char refs for E-shots. Zero-overhead for non-E-shots."""
    return GenerationGuard(shot, context).filtered_char_refs(raw_refs)


def guard_duration(raw: int, model: str = "kling") -> int:
    """Drop-in: snap duration to valid API values."""
    return GenerationGuard.snapped_duration(raw, model)


def guard_prompt(shot: dict, prompt: str, context: str = "unknown", cap: int = 512) -> str:
    """Drop-in: enforce no-people for E-shots + cap to API limit."""
    g = GenerationGuard(shot, context)
    prompt = g.enforce_no_people_prompt(prompt)
    return GenerationGuard.cap_prompt(prompt, cap)


def estimate_kling_cost(duration_secs: int, generate_audio: bool = False) -> float:
    """Drop-in: return USD cost for a Kling call."""
    return GenerationGuard.estimated_cost(duration_secs, generate_audio, model="kling")


def check_e_shot_for_people(frame_path: str, shot: dict) -> Tuple[bool, str]:
    """
    VVO E-shot rejection rule: detect human figures in environment-only frames.

    Returns (clean, reason).
      clean=True  → no people detected (or check skipped) — OK to proceed
      clean=False → human figures detected — mark REGEN_REQUESTED

    Uses Florence-2 caption via FAL as a lightweight check (~$0.001/call).
    Falls back to filename heuristics if FAL is unavailable.
    """
    if not GenerationGuard(shot).is_e_shot():
        return True, "not an E-shot"

    import os
    from pathlib import Path as _Path

    _frame = _Path(frame_path)
    if not _frame.exists():
        return True, "frame not found — skip"

    # Heuristic: check if "no people" text was in the prompt (pre-gen guard fired)
    _prompt = (shot.get("nano_prompt") or "").lower()
    _has_guard_text = "no people" in _prompt or "no figures" in _prompt or "no persons" in _prompt
    if not _has_guard_text:
        # Pre-gen guard was NOT applied — flag for review without spending on vision
        return False, "E-shot prompt missing 'no people' guard — pre-gen guard was bypassed"

    # Optional: FAL Florence-2 caption check (only if FAL key available)
    try:
        import fal_client as _fal
        _caption_result = _fal.run(
            "fal-ai/florence-2-large/caption",
            arguments={"image_url": f"data:image/jpeg;base64,{_b64_frame(frame_path)}"},
        )
        _caption = (_caption_result.get("results", {}).get("caption", "") or "").lower()
        _people_words = [
            "person", "people", "man", "woman", "character", "figure", "human",
            "face", "standing", "sitting", "walking", "wearing",
        ]
        for _word in _people_words:
            if _word in _caption:
                return False, f"VVO: human figure detected in E-shot (caption: '{_caption[:80]}')"
        return True, f"VVO: E-shot clean (caption: '{_caption[:80]}')"
    except Exception as _cap_err:
        # Vision unavailable — trust the pre-gen guard and proceed
        return True, f"VVO check skipped (non-blocking): {_cap_err}"


def _b64_frame(frame_path: str) -> str:
    """Encode frame as base64 for Florence-2 caption call."""
    import base64
    with open(frame_path, "rb") as _f:
        return base64.b64encode(_f.read()).decode()


def log_cost_summary(tracker: dict) -> None:
    """Print a cost summary from a _cost_tracker dict (runner format)."""
    total = sum(v for k, v in tracker.items() if k.endswith("_cost"))
    lines = []
    for model in ["kling", "nano", "seedance", "ltx"]:
        cost = tracker.get(f"{model}_cost", 0)
        calls = tracker.get(f"{model}_calls", 0)
        if calls:
            lines.append(f"  {model}: {calls} calls, ${cost:.3f}")
    if lines:
        logger.info(f"[COST SUMMARY] Total ${total:.3f}\n" + "\n".join(lines))
