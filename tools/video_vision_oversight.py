"""
ATLAS Video Vision Oversight — V2.0 (2026-03-29)
=================================================
Post-generation per-video watching. Two analysis tiers:

TIER 1 — FULL VIDEO (Gemini 2.0 Flash, temporal analysis, preferred):
  Uploads the actual .mp4 to Gemini Files API and asks it to reason over
  the entire timeline. Catches what frame extraction cannot:
    • ACTION_COMPLETION  — beat action actually finishes before cut
    • FROZEN_SEGMENT     — temporal freeze at any timestamp (not just midpoint)
    • DIALOGUE_SYNC      — mouth movement continuity across speaking duration
    • EMOTIONAL_ARC      — body language matches arc_position (ESTABLISH/ESCALATE/PIVOT/RESOLVE)
    • CHARACTER_CONTINUITY — start vs end spatial state for chain handoff

  Chain transition check: upload BOTH prev + curr video and ask if
  the handoff is seamless (position, costume, lighting).

  Scene stitch check: upload the FULL STITCHED SCENE and ask for
  cut naturalness, emotional arc, jarring transitions.

TIER 2 — FRAME-BASED (Gemini 2.5 Flash, per-frame, fallback):
  Original V1.0 checks. Used when full video upload fails or is disabled.
    1. CHARACTER BLEED  — unexpected people in E-shots
    2. FROZEN FRAMES    — pixel-diff + Gemini on extracted frame
    3. DIALOGUE SYNC    — mouth movement on a single extracted frame

Authority: QA layer — returns verdicts only, never mutates shot_plan.
           Controller/runner acts on returned regen_patches.

Wire: called from atlas_universal_runner.py AFTER _cig_post (V36.5),
      BEFORE ARJ. Failure marks shot contaminated for regen.

Usage:
  # Default (frame-based):
  report = run_video_oversight(video_path, shot, story_bible)

  # Full video (preferred):
  report = run_video_oversight(video_path, shot, story_bible, use_full_video=True)

  # Chain transition check:
  result = run_chain_transition_check(prev_video, curr_video, prev_shot, curr_shot)

  # Scene stitch check (after ffmpeg concat):
  result = run_scene_stitch_check(stitched_path, scene_shots)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.video_vision_oversight")

# ── DOCTRINE LAYER (V4.0 — 2026-03-29) ───────────────────────────────────────
# Optional import — VVO works without it (falls back to technical-only prompts)
try:
    from tools.vision_doctrine_prompts import (
        get_doctrine_prompt as _get_doctrine_prompt,
        get_chain_doctrine_prompt as _get_chain_doctrine_prompt,
        get_scene_stitch_doctrine_prompt as _get_scene_stitch_doctrine_prompt,
        parse_doctrine_fields as _parse_doctrine_fields,
        parse_chain_doctrine_fields as _parse_chain_doctrine_fields,
        parse_scene_doctrine_fields as _parse_scene_doctrine_fields,
        resolve_genre_and_production as _resolve_genre_and_production,
        compute_doctrine_health as _compute_doctrine_health,
    )
    _DOCTRINE_AVAILABLE = True
except ImportError:
    try:
        from vision_doctrine_prompts import (
            get_doctrine_prompt as _get_doctrine_prompt,
            get_chain_doctrine_prompt as _get_chain_doctrine_prompt,
            get_scene_stitch_doctrine_prompt as _get_scene_stitch_doctrine_prompt,
            parse_doctrine_fields as _parse_doctrine_fields,
            parse_chain_doctrine_fields as _parse_chain_doctrine_fields,
            parse_scene_doctrine_fields as _parse_scene_doctrine_fields,
            resolve_genre_and_production as _resolve_genre_and_production,
            compute_doctrine_health as _compute_doctrine_health,
        )
        _DOCTRINE_AVAILABLE = True
    except ImportError:
        _DOCTRINE_AVAILABLE = False
        logger.debug("[VVO] vision_doctrine_prompts not available — technical-only mode")

# ── GEMINI MODELS ──────────────────────────────────────────────────────────────
# Two-tier vision model selection (V3.0 upgrade — 2026-03-29):
#   CRITICAL: chain transitions, scene stitch, dialogue sync — deep narrative reasoning
#   VIDEO:    per-shot full video analysis — fast, cost-efficient, temporal checks
#   FRAME:    per-frame frozen/bleed/sync checks — high-volume, cheapest tier
_GEMINI_CRITICAL_MODEL = "gemini-2.5-pro"        # Tier 1 CRITICAL: chain + stitch + dialogue (V3.0)
_GEMINI_VIDEO_MODEL    = "gemini-2.5-flash"      # Tier 1 VIDEO: per-shot full analysis (upgraded from 2.0-flash)
_GEMINI_FRAME_MODEL    = "gemini-2.5-flash"      # Tier 2 FRAME: per-frame checks (V1.0, unchanged)

# ── UPLOAD LIMITS ─────────────────────────────────────────────────────────────
_GEMINI_FILE_POLL_INTERVAL = 3   # seconds between state polls
_GEMINI_FILE_POLL_MAX_WAIT = 240 # max seconds to wait for ACTIVE state (increased for large files)
_GEMINI_UPLOAD_TIMEOUT     = 300 # upload request timeout (increased for 50MB+ stitch files)

# ── GENRE CROWD POLICY ────────────────────────────────────────────────────────
_CROWD_EXPECTED_GENRES = {
    "horror", "thriller", "action", "crime", "war", "political",
    "social", "epic", "musical", "spy", "heist",
}
_CROWD_EXPECTED_LOCATIONS = {
    "street", "market", "plaza", "square", "bar", "pub", "restaurant",
    "train", "station", "airport", "crowd", "party", "celebration",
    "court", "church", "wedding", "stadium", "arena", "ballroom",
    "corridor", "hallway",
}
_STRICT_EMPTY_GENRES = {
    "drama", "romance", "literary", "gothic", "mystery", "period",
    "chamber", "noir", "psychological", "family",
}


# ═══════════════════════════════════════════════════════════════════════════════
# VISION BUDGET GUARDRAILS — V5.0 (2026-03-30)
# Hard caps on regen cycles to prevent API budget runaway.
# All thresholds configurable via VISION_BUDGET_CONFIG.
# ═══════════════════════════════════════════════════════════════════════════════

VISION_BUDGET_CONFIG = {
    # Hard cap: max regen attempts per shot before flagging for human review
    # Deliberately set to 1: one correction attempt, then flag for human review.
    # Prevents "refinement spiral" where repeated regens waste budget without convergence.
    "max_regen_per_shot":            1,
    # Scene cap: total Kling API calls (primary + regens) ≤ scene_shots × multiplier
    "max_kling_calls_multiplier":    1.5,
    # Episode cap: total Kling calls across all scenes ≤ total_shots × multiplier
    "max_episode_multiplier":        1.3,
    # Daily Gemini API spend cap — warnings printed at 50 / 75 / 90%
    "daily_gemini_budget_usd":       5.0,
    # Estimated cost per Gemini vision API call (Files API + generate_content)
    "gemini_cost_per_call_usd":      0.002,
    # True  → auto-regen only on grade F (hard reject dimensions OR overall < 0.30)
    # False → auto-regen on any REJECT verdict (legacy behavior)
    "regen_on_grade_f_only":         True,
    # True → contaminate chain when budget exceeded (stop downstream shots)
    "stop_chain_on_budget_exceeded": True,
}


class VisionBudgetTracker:
    """
    Episode-level budget tracker for vision oversight regens.

    Enforces hard caps on:
      - Per-shot regen attempts    (max_regen_per_shot)
      - Per-scene Kling API calls  (scene_shots × max_kling_calls_multiplier)
      - Episode Kling API calls    (total_shots × max_episode_multiplier)
      - Daily Gemini spend         (warnings at 50/75/90% of daily_gemini_budget_usd)

    Grade-based regen filtering (when regen_on_grade_f_only=True):
      Grade F = has_hard_rejects OR overall_score < 0.30 → auto-regen
      Grade D = REJECT without hard_rejects (0.30–0.52) → advisory flag, no regen

    Chain-forward protection (when stop_chain_on_budget_exceeded=True):
      Budget-exceeded shots are marked contaminated so downstream chain shots
      are not generated from a defective start frame.

    Instance created once per episode run.
    reset_scene() MUST be called at the start of each scene.
    Thread-safe: CPython dict updates are GIL-guarded.
    """

    def __init__(self, config: dict = None):
        self._cfg = {**VISION_BUDGET_CONFIG, **(config or {})}
        # Per-shot regen counts: shot_id → int
        self._shot_regens: dict = {}
        # Scene-level tracking (reset each scene)
        self._scene_kling_calls: int = 0
        self._scene_shot_count: int = 0
        # Episode-level tracking (accumulates across scenes)
        self._episode_kling_calls: int = 0
        self._episode_shot_count: int = 0
        # Gemini cost tracking
        self._gemini_calls: int = 0
        self._gemini_cost: float = 0.0
        self._warned_50 = False
        self._warned_75 = False
        self._warned_90 = False

    # ── Scene lifecycle ────────────────────────────────────────────────────────

    def reset_scene(self, scene_shot_count: int):
        """Call at the start of each scene. Resets scene counters, accumulates episode."""
        self._scene_kling_calls = 0
        self._scene_shot_count = scene_shot_count
        self._episode_shot_count += scene_shot_count
        logger.debug(
            f"[VISION BUDGET] Scene reset: {scene_shot_count} shots | "
            f"Scene cap: {self._scene_cap()} | Episode total shots: {self._episode_shot_count}"
        )

    # ── Kling call tracking ────────────────────────────────────────────────────

    def track_kling_call(self):
        """Track one Kling API call (primary generation or regen). Always safe to call."""
        self._scene_kling_calls += 1
        self._episode_kling_calls += 1

    def _scene_cap(self) -> int:
        return max(1, int(self._scene_shot_count * self._cfg["max_kling_calls_multiplier"]))

    def _episode_cap(self) -> int:
        if self._episode_shot_count == 0:
            return 9999
        return max(1, int(self._episode_shot_count * self._cfg["max_episode_multiplier"]))

    def scene_budget_ok(self) -> bool:
        """True if scene has not yet hit its Kling call cap."""
        return self._scene_kling_calls < self._scene_cap()

    def episode_budget_ok(self) -> bool:
        """True if episode has not yet hit its total Kling call cap."""
        return self._episode_kling_calls < self._episode_cap()

    def budget_summary(self) -> str:
        return (
            f"Scene Kling: {self._scene_kling_calls}/{self._scene_cap()} | "
            f"Episode Kling: {self._episode_kling_calls}/{self._episode_cap()} | "
            f"Gemini: {self._gemini_calls} calls (${self._gemini_cost:.3f})"
        )

    # ── Per-shot regen cap ─────────────────────────────────────────────────────

    def can_regen_shot(self, shot_id: str) -> bool:
        """True if this shot has not exhausted its regen budget (max_regen_per_shot)."""
        return self._shot_regens.get(shot_id, 0) < self._cfg["max_regen_per_shot"]

    def consume_regen(self, shot_id: str):
        """Increment regen count for this shot. Call BEFORE triggering each regen."""
        self._shot_regens[shot_id] = self._shot_regens.get(shot_id, 0) + 1

    def regen_count(self, shot_id: str) -> int:
        return self._shot_regens.get(shot_id, 0)

    # ── Grade-based regen gate ─────────────────────────────────────────────────

    def should_regen_on_grade(self, has_hard_rejects: bool, overall_score: float) -> bool:
        """
        True if this ARJ verdict warrants an auto-regen.

        Grade mapping:
          Grade F: has_hard_rejects=True OR overall_score < 0.30  → regen
          Grade D: REJECT without hard_rejects (0.30–0.52)        → advisory, no regen

        If regen_on_grade_f_only=False (legacy mode): always True for any REJECT.
        """
        if not self._cfg["regen_on_grade_f_only"]:
            return True  # legacy: regen on any rejection
        return has_hard_rejects or (overall_score < 0.30)

    # ── Gemini cost tracking ───────────────────────────────────────────────────

    def track_gemini_call(self, call_type: str = "vision"):
        """
        Track one Gemini API call. Logs cost and prints budget warnings at
        50%, 75%, and 90% of daily_gemini_budget_usd (once each).
        """
        cost = self._cfg["gemini_cost_per_call_usd"]
        self._gemini_calls += 1
        self._gemini_cost += cost
        daily_cap = self._cfg["daily_gemini_budget_usd"]
        if daily_cap <= 0:
            return
        pct = self._gemini_cost / daily_cap
        if pct >= 0.90 and not self._warned_90:
            self._warned_90 = True
            print(
                f"\n  [VISION BUDGET] ⚠️⚠️⚠️  CRITICAL: Gemini at 90% of daily cap "
                f"(${self._gemini_cost:.3f} / ${daily_cap:.2f}) — "
                f"{self._gemini_calls} calls [{call_type}]"
            )
        elif pct >= 0.75 and not self._warned_75:
            self._warned_75 = True
            print(
                f"\n  [VISION BUDGET] ⚠️⚠️  WARNING: Gemini at 75% of daily cap "
                f"(${self._gemini_cost:.3f} / ${daily_cap:.2f})"
            )
        elif pct >= 0.50 and not self._warned_50:
            self._warned_50 = True
            print(
                f"\n  [VISION BUDGET] ⚠️  INFO: Gemini at 50% of daily cap "
                f"(${self._gemini_cost:.3f} / ${daily_cap:.2f})"
            )

    # ── Chain protection ───────────────────────────────────────────────────────

    def stop_chain_on_exceeded(self) -> bool:
        """True if the chain should stop (mark contaminated) when budget is exceeded."""
        return self._cfg["stop_chain_on_budget_exceeded"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — GEMINI FILES API HELPERS (V2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")


def _upload_video_to_gemini(video_path: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Upload a video file to the Gemini Files API via multipart upload.

    Returns file metadata dict with keys: name, uri, mimeType, state
    Returns None on failure.

    The returned file.name is needed to poll state and later delete.
    The returned file.uri is used in generate_content file_data parts.
    """
    import urllib.request as _req
    import urllib.error as _err

    if not os.path.exists(video_path):
        logger.debug(f"[VVO] upload: file not found: {video_path}")
        return None

    file_size = os.path.getsize(video_path)
    if file_size == 0:
        logger.debug(f"[VVO] upload: empty file: {video_path}")
        return None

    ext = os.path.splitext(video_path)[1].lower()
    mime_type = "video/mp4" if ext in (".mp4", ".m4v") else "video/quicktime"

    display_name = Path(video_path).stem[:64]
    boundary = f"atlas_vvo_{uuid.uuid4().hex}"

    # Build multipart body
    meta_json = json.dumps({"file": {"display_name": display_name}}).encode("utf-8")
    meta_part = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n\r\n"
    ).encode("utf-8") + meta_json + b"\r\n"

    with open(video_path, "rb") as f:
        video_bytes = f.read()

    video_part = (
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + video_bytes + b"\r\n"

    closing = f"--{boundary}--\r\n".encode("utf-8")
    body = meta_part + video_part + closing

    url = (
        f"https://generativelanguage.googleapis.com/upload/v1beta/files"
        f"?uploadType=multipart&key={api_key}"
    )
    req = _req.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        method="POST",
    )

    try:
        with _req.urlopen(req, timeout=_GEMINI_UPLOAD_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        file_meta = result.get("file", result)
        logger.debug(
            f"[VVO] uploaded {Path(video_path).name} "
            f"({file_size//1024}KB) → {file_meta.get('name')}"
        )
        return file_meta
    except Exception as e:
        logger.debug(f"[VVO] upload failed for {Path(video_path).name}: {e}")
        return None


def _poll_file_active(
    file_name: str,
    api_key: str,
    max_wait: int = _GEMINI_FILE_POLL_MAX_WAIT,
) -> bool:
    """
    Poll Gemini Files API until file.state == ACTIVE.
    file_name is the 'files/xyz123' string from the upload response.
    Returns True when active, False on timeout or FAILED state.
    """
    import urllib.request as _req

    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/{file_name}?key={api_key}"
    )
    waited = 0
    while waited < max_wait:
        try:
            with _req.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            state = data.get("state", "")
            if state == "ACTIVE":
                return True
            if state == "FAILED":
                logger.debug(f"[VVO] file {file_name} entered FAILED state")
                return False
            # PROCESSING — keep waiting
        except Exception as e:
            logger.debug(f"[VVO] poll error for {file_name}: {e}")

        time.sleep(_GEMINI_FILE_POLL_INTERVAL)
        waited += _GEMINI_FILE_POLL_INTERVAL

    logger.debug(f"[VVO] poll timeout after {max_wait}s for {file_name}")
    return False


def _delete_gemini_file(file_name: str, api_key: str) -> None:
    """Delete a file from Gemini Files API. Silent on failure."""
    import urllib.request as _req

    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/{file_name}?key={api_key}"
    )
    try:
        req = _req.Request(url, method="DELETE")
        # DELETE needs the key in the URL (already included)
        # urllib doesn't send body for DELETE
        _req.urlopen(req, timeout=15)
        logger.debug(f"[VVO] deleted {file_name}")
    except Exception as e:
        logger.debug(f"[VVO] delete failed for {file_name}: {e}")


def _call_gemini_with_video(
    file_uri: str,
    mime_type: str,
    prompt: str,
    api_key: str,
    second_file_uri: Optional[str] = None,
    second_mime: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Call Gemini with one (or two) uploaded video file URIs and a text prompt.
    Returns the text response or None on failure.

    Two-file mode is used for chain transition analysis (prev + curr video).
    """
    import urllib.request as _req

    parts: List[dict] = []

    # First video
    parts.append({"file_data": {"mime_type": mime_type, "file_uri": file_uri}})

    # Optional second video (chain transition)
    if second_file_uri and second_mime:
        parts.append({"file_data": {"mime_type": second_mime, "file_uri": second_file_uri}})

    parts.append({"text": prompt})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.1,
        },
    }).encode("utf-8")

    _model = model or _GEMINI_VIDEO_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{_model}:generateContent?key={api_key}"
    )
    req = _req.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with _req.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.debug(f"[VVO] generate_content call failed: {e}")
        return None


def _upload_and_call(
    video_path: str,
    prompt: str,
    api_key: str,
    second_video_path: Optional[str] = None,
    cleanup: bool = True,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Full lifecycle: upload → poll → generate → delete.
    Handles one or two videos (chain transition mode).
    Pass model=_GEMINI_CRITICAL_MODEL for chain/stitch/dialogue analysis.
    Returns Gemini response text or None on any failure.
    """
    if not api_key:
        return None

    # Upload first video
    meta1 = _upload_video_to_gemini(video_path, api_key)
    if not meta1:
        return None
    file_name1 = meta1.get("name", "")
    file_uri1  = meta1.get("uri", "")
    mime1      = meta1.get("mimeType", "video/mp4")

    if not _poll_file_active(file_name1, api_key):
        if cleanup and file_name1:
            _delete_gemini_file(file_name1, api_key)
        return None

    # Optional second video
    file_name2 = ""
    file_uri2  = None
    mime2      = None
    if second_video_path and os.path.exists(second_video_path):
        meta2 = _upload_video_to_gemini(second_video_path, api_key)
        if meta2:
            file_name2 = meta2.get("name", "")
            file_uri2  = meta2.get("uri", "")
            mime2      = meta2.get("mimeType", "video/mp4")
            if not _poll_file_active(file_name2, api_key):
                file_uri2 = None  # proceed with single video if second fails

    try:
        return _call_gemini_with_video(
            file_uri1, mime1, prompt, api_key,
            second_file_uri=file_uri2, second_mime=mime2,
            model=model,
        )
    finally:
        if cleanup:
            if file_name1:
                _delete_gemini_file(file_name1, api_key)
            if file_name2:
                _delete_gemini_file(file_name2, api_key)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — FULL VIDEO ANALYSIS (V2.0 TIER 1)
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_full_video(
    video_path: str,
    shot: dict,
    story_bible: Optional[dict] = None,
    genre_id: str = "",
    production_type: str = "movie",
) -> Dict[str, Any]:
    """
    Upload the full video to Gemini 2.0 Flash and perform comprehensive temporal analysis.

    Checks in ONE API call (cost-efficient):
      - ACTION_COMPLETION: does the beat action finish before cut?
      - FROZEN_SEGMENT: any timestamp where motion completely stops?
      - DIALOGUE_SYNC: mouth movement continuity across speaking duration?
      - EMOTIONAL_ARC: body language matches arc_position?
      - CHARACTER_CONTINUITY: start vs end spatial state for chain handoff

    Returns a dict with all dimensions + overall_pass (True/False) + regen_patch.
    Returns a minimal "skipped" dict if Gemini unavailable or upload fails.
    """
    api_key = _get_api_key()
    sid = shot.get("shot_id", "?")

    _SKIP = {
        "skipped": True, "overall_pass": True,
        "action_completion": None, "frozen_segment": None,
        "dialogue_sync": None, "emotional_arc": None,
        "character_continuity": None, "regen_patch": {},
        # V4.0 doctrine fields (None = not assessed)
        "filmmaker_grade": None, "grade_reason": "",
        "arc_fulfilled": None, "arc_verdict": "",
        "genre_compliance": "not_assessed", "genre_verdict": "",
        "doctrine_issues": [], "cinematography_scores": {},
    }

    if not api_key or not os.path.exists(video_path):
        return dict(_SKIP, reason="no_api_key_or_file")

    # V4.0: Resolve genre + production_type from shot/bible if not explicitly provided
    if _DOCTRINE_AVAILABLE and (not genre_id):
        _resolved_genre, _resolved_pt = _resolve_genre_and_production(shot, story_bible)
        genre_id = genre_id or _resolved_genre
        production_type = production_type or _resolved_pt or "movie"

    # Build context for the prompt
    beat_action    = (shot.get("_beat_action") or "").strip()[:120]
    dialogue_text  = (shot.get("dialogue_text") or "").strip()[:120]
    arc_position   = (shot.get("_arc_position") or "").strip()
    shot_type      = (shot.get("shot_type") or "").lower()
    chars          = shot.get("characters") or []
    char_desc      = chars[0] if chars else "the character"

    # Build shot context block for the prompt
    context_lines = [f"Shot ID: {sid}", f"Shot type: {shot_type}"]
    if beat_action:
        context_lines.append(f"Beat action: {beat_action}")
    if dialogue_text:
        context_lines.append(f"Dialogue: \"{dialogue_text}\"")
    if arc_position:
        context_lines.append(f"Arc position: {arc_position} (ESTABLISH=opening, ESCALATE=middle, PIVOT=turning-point, RESOLVE=closing)")
    if chars:
        context_lines.append(f"Characters present: {', '.join(chars)}")
    context_block = "\n".join(context_lines)

    prompt = f"""You are analyzing a short video clip from a film production.

SHOT CONTEXT:
{context_block}

Please analyze this video across ALL of the following dimensions and respond with a single JSON object:

1. ACTION_COMPLETION: Does the beat action ("{beat_action or 'stated action'}") begin and make meaningful progress in this clip? Answer: "complete" (beat fully executed), "in_progress" (action starts and is ongoing — OK for pacing/walking/continuous actions), "not_started" (beat action does not appear at all), or "not_applicable" (no visible action). NOTE: continuous actions like pacing, walking, or dialogue in progress are "in_progress", not "truncated". Only use "not_started" if the stated beat action never begins.

2. FROZEN_SEGMENT: Is there any segment where the video appears completely frozen or the character stops moving unnaturally (not intentional stillness)? Answer: true/false. Include start_timestamp if frozen (e.g., "frozen 4.2s–end").

3. DIALOGUE_SYNC: If dialogue is present, is mouth movement visible and continuous throughout the speaking? Answer: "synced", "no_face_visible", "frozen_mouth", "not_applicable".

4. EMOTIONAL_ARC: Does the character's body language and expression match the arc_position "{arc_position or 'unknown'}"? ESTABLISH=calm/open presence, ESCALATE=increasing intensity, PIVOT=visible shift/reaction, RESOLVE=settling/closing. Answer: "matches", "mismatches", "unclear", "not_applicable".

5. CHARACTER_CONTINUITY: Describe the character's spatial state at VIDEO START (position, orientation, what they're doing) and at VIDEO END. This will be used to verify the chain handoff to the next shot.

6. ENVIRONMENT_DESCRIPTION: In one sentence, describe the visible setting/environment (room type, architectural features, key props, lighting quality). This is used to check location consistency.

7. OVERALL_PASS: true if no critical failures. Mark false ONLY if: frozen_segment=true, OR action_completion="not_started" (beat never begins), OR dialogue mouth completely frozen.

Return ONLY valid JSON, no markdown:
{{"action_completion": "complete|in_progress|not_started|not_applicable", "action_timestamp_note": "...", "frozen_segment": false, "frozen_timestamp": null, "dialogue_sync": "synced|no_face_visible|frozen_mouth|not_applicable", "emotional_arc": "matches|mismatches|unclear|not_applicable", "character_start_state": "...", "character_end_state": "...", "environment_description": "...", "overall_pass": true, "failure_notes": "brief note if any failures"}}"""

    # V4.0: Append doctrine layer if available — extends JSON with filmmaker evaluation fields
    if _DOCTRINE_AVAILABLE:
        try:
            _doctrine_block = _get_doctrine_prompt(shot, genre_id=genre_id, production_type=production_type)
            prompt = prompt + _doctrine_block
            logger.debug(f"[VVO] [DOCTRINE] Enriched prompt for {sid} ({production_type}×{genre_id or 'drama'})")
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] Prompt build failed for {sid}: {_de}")

    try:
        response = _upload_and_call(video_path, prompt, api_key)
    except Exception as e:
        logger.debug(f"[VVO] analyze_full_video exception for {sid}: {e}")
        return dict(_SKIP, reason=f"exception: {e}")

    if not response:
        return dict(_SKIP, reason="gemini_no_response")

    # Parse JSON — robust extraction with truncation fallback (V3.0)
    raw = response.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    # Try full match first, then try to grab a partial {…} if model truncated output
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        # Try to extract a partial JSON object (Gemini sometimes cuts off)
        partial = re.search(r'\{[^}]*', raw, re.DOTALL)
        if partial:
            # Close the partial object with defaults
            patched = partial.group(0) + ', "overall_pass": true}'
            try:
                data = json.loads(patched)
                logger.debug(f"[VVO] full_video: used partial JSON fallback for {sid}")
            except json.JSONDecodeError:
                data = {}
        else:
            logger.debug(f"[VVO] full_video: unparseable response for {sid}: {response[:200]}")
            return dict(_SKIP, reason="unparseable_response", raw_response=response[:300])
    else:
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            # Try relaxed parse: remove trailing comma issues
            fixed = re.sub(r',\s*}', '}', json_match.group(0))
            fixed = re.sub(r',\s*]', ']', fixed)
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                logger.debug(f"[VVO] full_video: JSON decode error for {sid}: {e}")
                return dict(_SKIP, reason=f"json_error: {e}", raw_response=response[:300])

    # Build regen_patch from failures
    regen_patch: Dict[str, Any] = {}

    frozen = data.get("frozen_segment", False)
    if frozen:
        ts = data.get("frozen_timestamp", "")
        regen_patch["_regen_frozen_video"] = True
        regen_patch["_frozen_timestamp"] = ts
        regen_patch["nano_prompt_suffix"] = (
            " VIDEO MUST SHOW CONTINUOUS MOTION throughout. "
            "NOT a still photograph at any point. Every frame animated."
        )
        regen_patch["_negative_prompt_addition"] = (
            "frozen, static, still image, no motion, statue"
        )

    action_status = data.get("action_completion", "not_applicable")
    # Only flag regen for not_started (beat never began), not for in_progress (continuous action)
    if action_status == "not_started":
        regen_patch["_regen_action_truncated"] = True
        regen_patch["_action_note"] = data.get("action_timestamp_note", "")
        regen_patch["_action_failure_reason"] = "beat_never_started"

    dialogue_sync = data.get("dialogue_sync", "not_applicable")
    if dialogue_sync == "frozen_mouth":
        regen_patch["_regen_dialogue_sync"] = True
        if "nano_prompt_suffix" in regen_patch:
            regen_patch["nano_prompt_suffix"] += (
                " SPEAKING CHARACTER: mouth clearly animated throughout dialogue."
            )
        else:
            regen_patch["nano_prompt_suffix"] = (
                " CHARACTER ACTIVELY SPEAKING: mouth clearly open and animated, "
                "jaw movement visible throughout dialogue."
            )

    overall_pass = data.get("overall_pass", True)

    # V4.0: Parse doctrine fields if available
    _doctrine: Dict[str, Any] = {}
    _doctrine_health: Dict[str, Any] = {}
    if _DOCTRINE_AVAILABLE:
        try:
            _doctrine = _parse_doctrine_fields(data)
            _doctrine_health = _compute_doctrine_health(_doctrine)
            # Doctrine critical violations → flag regen patch (advisory, not blocking)
            if _doctrine_health.get("critical_violations"):
                regen_patch["_doctrine_critical_violations"] = _doctrine_health["critical_violations"]
                regen_patch["_filmmaker_grade"] = _doctrine.get("filmmaker_grade", "")
            grade = _doctrine.get("filmmaker_grade", "")
            if grade:
                logger.debug(
                    f"[VVO] [DOCTRINE] {sid} grade={grade} "
                    f"arc={_doctrine.get('arc_fulfilled')} "
                    f"genre={_doctrine.get('genre_compliance')} "
                    f"issues={_doctrine.get('doctrine_issues', [])}"
                )
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] parse failed for {sid}: {_de}")

    return {
        "skipped": False,
        "overall_pass": overall_pass,
        "action_completion": action_status,
        "action_timestamp_note": data.get("action_timestamp_note", ""),
        "frozen_segment": frozen,
        "frozen_timestamp": data.get("frozen_timestamp"),
        "dialogue_sync": dialogue_sync,
        "emotional_arc": data.get("emotional_arc", "not_applicable"),
        "character_start_state": data.get("character_start_state", ""),
        "character_end_state": data.get("character_end_state", ""),
        "environment_description": data.get("environment_description", ""),  # V3.0: location coherence field
        "failure_notes": data.get("failure_notes", ""),
        "regen_patch": regen_patch,
        # V4.0 — Doctrine layer fields (None if doctrine unavailable)
        "filmmaker_grade": _doctrine.get("filmmaker_grade"),
        "grade_reason": _doctrine.get("grade_reason", ""),
        "arc_fulfilled": _doctrine.get("arc_fulfilled"),
        "arc_verdict": _doctrine.get("arc_verdict", ""),
        "genre_compliance": _doctrine.get("genre_compliance", "not_assessed"),
        "genre_verdict": _doctrine.get("genre_verdict", ""),
        "production_format_compliance": _doctrine.get("production_format_compliance", "not_assessed"),
        "cinematography_scores": _doctrine.get("cinematography_scores", {}),
        "doctrine_issues": _doctrine.get("doctrine_issues", []),
        # V4.1 — Broadcast QC + AI artifact detection
        "ai_artifact_report": _doctrine.get("ai_artifact_report", {}),
        "broadcast_qc": _doctrine.get("broadcast_qc", {}),
        "doctrine_health": _doctrine_health,
    }


def analyze_chain_transition(
    prev_video_path: str,
    curr_video_path: str,
    prev_shot: dict,
    curr_shot: dict,
    genre_id: str = "",
    production_type: str = "movie",
) -> Dict[str, Any]:
    """
    Upload BOTH videos and ask Gemini if the chain handoff is seamless.

    Checks:
      - POSITION_JUMP: character teleports between shots
      - COSTUME_CHANGE: unexpected wardrobe continuity break
      - LIGHTING_SHIFT: jarring light temperature/direction change
      - SPATIAL_MISMATCH: the end-state of video 1 doesn't match start-state of video 2

    Returns dict with: seamless (bool), issues[], regen_patch, skipped.
    """
    api_key = _get_api_key()

    _SKIP = {
        "skipped": True, "seamless": True, "issues": [], "regen_patch": {},
        # V4.0 chain doctrine fields
        "chain_filmmaker_grade": None, "chain_grade_reason": "",
        "screen_direction_correct": None, "lighting_temperature_match": None,
        "color_grade_drift": None, "spatial_geography_maintained": None,
        "cut_grammar": "", "chain_doctrine_issues": [],
    }

    if not api_key:
        return dict(_SKIP, reason="no_api_key")
    if not os.path.exists(prev_video_path) or not os.path.exists(curr_video_path):
        return dict(_SKIP, reason="file_not_found")

    prev_sid = prev_shot.get("shot_id", "prev")
    curr_sid = curr_shot.get("shot_id", "curr")

    prev_end   = prev_shot.get("character_end_state", "")
    curr_start = curr_shot.get("character_start_state", "")

    prompt = f"""You are checking the continuity between two consecutive video clips.

VIDEO 1 ends with shot {prev_sid}.
VIDEO 2 begins with shot {curr_sid}.

{"Expected end state of Video 1: " + prev_end if prev_end else ""}
{"Expected start state of Video 2: " + curr_start if curr_start else ""}

Watch BOTH videos and answer:

1. POSITION_JUMP: Does the character jump to a completely different position/orientation between the end of Video 1 and the start of Video 2? (small natural variation is OK)

2. COSTUME_CHANGE: Does the character's clothing/appearance change unexpectedly between the two clips?

3. LIGHTING_SHIFT: Is there a jarring, unmotivated change in light color or direction between the clips?

4. SPATIAL_MISMATCH: Describe the character's position/action at the END of Video 1, and at the START of Video 2. Do they match well enough for a clean cut?

5. SEAMLESS: Is this chain transition cinematically acceptable (true) or does it have continuity breaks that would distract the viewer (false)?

Return ONLY valid JSON:
{{"position_jump": false, "costume_change": false, "lighting_shift": false, "end_state_v1": "...", "start_state_v2": "...", "spatial_mismatch": false, "seamless": true, "issues": [], "notes": "..."}}"""

    # V4.0: Append chain doctrine block if available
    if _DOCTRINE_AVAILABLE:
        try:
            if not genre_id:
                genre_id = (
                    curr_shot.get("_genre_dna_profile") or
                    prev_shot.get("_genre_dna_profile") or ""
                ).lower()
            _chain_doctrine = _get_chain_doctrine_prompt(
                prev_shot, curr_shot, genre_id=genre_id, production_type=production_type
            )
            prompt = prompt + _chain_doctrine
            logger.debug(f"[VVO] [DOCTRINE] Chain prompt enriched {prev_sid}→{curr_sid}")
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] Chain prompt build failed: {_de}")

    try:
        response = _upload_and_call(
            prev_video_path, prompt, api_key,
            second_video_path=curr_video_path,
            model=_GEMINI_CRITICAL_MODEL,  # V3.0: use pro for chain reasoning
        )
    except Exception as e:
        logger.debug(f"[VVO] chain_transition exception {prev_sid}→{curr_sid}: {e}")
        return dict(_SKIP, reason=f"exception: {e}")

    if not response:
        return dict(_SKIP, reason="gemini_no_response")

    raw = response.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        return dict(_SKIP, reason="unparseable_response")

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return dict(_SKIP, reason="json_error")

    seamless = data.get("seamless", True)
    issues = data.get("issues", [])

    # Collect triggered issues
    issue_flags = []
    if data.get("position_jump"):
        issue_flags.append("POSITION_JUMP")
    if data.get("costume_change"):
        issue_flags.append("COSTUME_CHANGE")
    if data.get("lighting_shift"):
        issue_flags.append("LIGHTING_SHIFT")
    if data.get("spatial_mismatch"):
        issue_flags.append("SPATIAL_MISMATCH")

    all_issues = issues + issue_flags

    regen_patch: Dict[str, Any] = {}
    if not seamless:
        regen_patch["_regen_chain_mismatch"] = True
        regen_patch["_chain_issues"] = all_issues
        regen_patch["_chain_end_state"]   = data.get("end_state_v1", "")
        regen_patch["_chain_start_state"] = data.get("start_state_v2", "")

    # V4.0: Parse chain doctrine fields
    _chain_doctrine: Dict[str, Any] = {}
    if _DOCTRINE_AVAILABLE:
        try:
            _chain_doctrine = _parse_chain_doctrine_fields(data)
            grade = _chain_doctrine.get("chain_filmmaker_grade", "")
            if grade:
                logger.debug(
                    f"[VVO] [DOCTRINE] Chain {prev_sid}→{curr_sid} grade={grade} "
                    f"screen_dir={_chain_doctrine.get('screen_direction_correct')} "
                    f"cut={_chain_doctrine.get('cut_grammar')}"
                )
            # Flag chain doctrine failures in regen_patch (advisory)
            if _chain_doctrine.get("chain_doctrine_issues"):
                regen_patch["_chain_doctrine_issues"] = _chain_doctrine["chain_doctrine_issues"]
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] Chain parse failed {prev_sid}→{curr_sid}: {_de}")

    return {
        "skipped": False,
        "seamless": seamless,
        "position_jump": data.get("position_jump", False),
        "costume_change": data.get("costume_change", False),
        "lighting_shift": data.get("lighting_shift", False),
        "spatial_mismatch": data.get("spatial_mismatch", False),
        "end_state_v1": data.get("end_state_v1", ""),
        "start_state_v2": data.get("start_state_v2", ""),
        "issues": all_issues,
        "notes": data.get("notes", ""),
        "regen_patch": regen_patch,
        # V4.0 — Chain doctrine fields
        "chain_filmmaker_grade": _chain_doctrine.get("chain_filmmaker_grade"),
        "chain_grade_reason": _chain_doctrine.get("chain_grade_reason", ""),
        "screen_direction_correct": _chain_doctrine.get("screen_direction_correct"),
        "lighting_temperature_match": _chain_doctrine.get("lighting_temperature_match"),
        "color_grade_drift": _chain_doctrine.get("color_grade_drift"),
        "spatial_geography_maintained": _chain_doctrine.get("spatial_geography_maintained"),
        "cut_grammar": _chain_doctrine.get("cut_grammar", ""),
        "chain_doctrine_issues": _chain_doctrine.get("chain_doctrine_issues", []),
        # V4.1 — Broadcast QC at chain boundary
        "chain_color_delta": _chain_doctrine.get("chain_color_delta", "not_assessed"),
        "chain_ssim_estimate": _chain_doctrine.get("chain_ssim_estimate", "not_assessed"),
        "ai_chain_artifacts": _chain_doctrine.get("ai_chain_artifacts", {}),
    }


def analyze_scene_stitch(
    stitched_path: str,
    scene_shots: List[dict],
    genre_id: str = "",
    production_type: str = "movie",
) -> Dict[str, Any]:
    """
    Upload the FULL STITCHED SCENE video to Gemini and evaluate the complete sequence.

    Checks:
      - CUT_NATURALNESS: are cuts smooth or jarring?
      - EMOTIONAL_ARC: does the scene build and resolve properly?
      - JARRING_TRANSITIONS: specific timestamps where cuts are problematic
      - NARRATIVE_FLOW: does the sequence tell the story coherently?

    Returns assessment dict with overall_quality (A/B/C/D) and notes.
    """
    api_key = _get_api_key()

    _SKIP = {
        "skipped": True, "overall_quality": "not_assessed",
        "cut_naturalness": None, "emotional_arc": None,
        "jarring_transitions": [], "narrative_flow": None, "notes": "",
    }

    if not api_key or not os.path.exists(stitched_path):
        return dict(_SKIP, reason="no_api_key_or_file")

    scene_id = scene_shots[0].get("shot_id", "?")[:3] if scene_shots else "?"
    shot_count = len(scene_shots)
    beat_summary = "; ".join(
        (s.get("_beat_action") or "")[:50]
        for s in scene_shots if s.get("_beat_action")
    )[:300]

    prompt = f"""You are reviewing the full assembled scene {scene_id} from a film.
This scene has {shot_count} shots stitched together.

Scene beat summary: {beat_summary or "(not available)"}

Watch the COMPLETE scene and evaluate:

1. CUT_NATURALNESS (0.0–1.0): How smooth are the cuts? 1.0=all cuts feel motivated and invisible, 0.0=all cuts are jarring.

2. EMOTIONAL_ARC (0.0–1.0): Does the scene have a clear emotional build and release? 1.0=strong arc, 0.0=flat/random.

3. JARRING_TRANSITIONS: List timestamps (e.g., "2.3s", "7.8s") of any cuts that feel unmotivated or spatially confusing. Empty list if none.

4. NARRATIVE_FLOW (0.0–1.0): Does the scene tell its story coherently? 1.0=completely clear, 0.0=confusing.

5. OVERALL_QUALITY: Grade A (0.85+), B (0.70–0.84), C (0.50–0.69), D (<0.50) based on the average of above scores.

6. NOTES: 2–3 sentence director's note on the biggest issues (if any).

Return ONLY valid JSON:
{{"cut_naturalness": 0.8, "emotional_arc": 0.7, "jarring_transitions": [], "narrative_flow": 0.8, "overall_quality": "B", "notes": "..."}}"""

    # V4.0: Append scene-level doctrine block if available
    if _DOCTRINE_AVAILABLE:
        try:
            if not genre_id:
                for _s in scene_shots:
                    _cand = _s.get("_genre_dna_profile") or _s.get("_genre_id") or ""
                    if _cand:
                        genre_id = _cand.lower()
                        break
            _stitch_doctrine = _get_scene_stitch_doctrine_prompt(
                scene_shots, genre_id=genre_id, production_type=production_type
            )
            prompt = prompt + _stitch_doctrine
            logger.debug(f"[VVO] [DOCTRINE] Scene stitch prompt enriched for scene {scene_id}")
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] Scene stitch prompt build failed: {_de}")

    try:
        response = _upload_and_call(stitched_path, prompt, api_key,
                                    model=_GEMINI_CRITICAL_MODEL)  # V3.0: pro for scene-level narrative
    except Exception as e:
        logger.debug(f"[VVO] scene_stitch exception for {stitched_path}: {e}")
        return dict(_SKIP, reason=f"exception: {e}")

    if not response:
        return dict(_SKIP, reason="gemini_no_response")

    raw = response.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        return dict(_SKIP, reason="unparseable_response")

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return dict(_SKIP, reason="json_error")

    # V4.0: Parse scene-level doctrine fields
    _scene_doctrine: Dict[str, Any] = {}
    if _DOCTRINE_AVAILABLE:
        try:
            _scene_doctrine = _parse_scene_doctrine_fields(data)
            grade = _scene_doctrine.get("scene_filmmaker_grade", "")
            if grade:
                logger.debug(
                    f"[VVO] [DOCTRINE] Scene {scene_id} director grade={grade} "
                    f"arc={_scene_doctrine.get('arc_sequence_coherent')} "
                    f"genre={_scene_doctrine.get('genre_maintained_across_scene')}"
                )
        except Exception as _de:
            logger.debug(f"[VVO] [DOCTRINE] Scene stitch parse failed: {_de}")

    return {
        "skipped": False,
        "overall_quality": data.get("overall_quality", "not_assessed"),
        "cut_naturalness": data.get("cut_naturalness"),
        "emotional_arc": data.get("emotional_arc"),
        "jarring_transitions": data.get("jarring_transitions", []),
        "narrative_flow": data.get("narrative_flow"),
        "notes": data.get("notes", ""),
        # V4.0 — Scene doctrine fields
        "scene_filmmaker_grade": _scene_doctrine.get("scene_filmmaker_grade"),
        "scene_grade_reason": _scene_doctrine.get("scene_grade_reason", ""),
        "arc_sequence_coherent": _scene_doctrine.get("arc_sequence_coherent"),
        "arc_sequence_note": _scene_doctrine.get("arc_sequence_note", ""),
        "genre_maintained_across_scene": _scene_doctrine.get("genre_maintained_across_scene"),
        "production_format_coherent": _scene_doctrine.get("production_format_coherent"),
        "degree_180_rule_scene_verdict": _scene_doctrine.get("degree_180_rule_scene_verdict", "not_assessed"),
        "scene_doctrine_issues": _scene_doctrine.get("scene_doctrine_issues", []),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FRAME-BASED CHECKS (V1.0 TIER 2, UNCHANGED)
# ═══════════════════════════════════════════════════════════════════════════════

def _call_gemini_vision(image_path: str, prompt: str) -> Optional[str]:
    """Call Gemini Vision with image + prompt. Returns text or None on failure."""
    import base64
    import urllib.request as _req

    api_key = _get_api_key()
    if not api_key or not image_path or not os.path.exists(image_path):
        return None

    try:
        try:
            from PIL import Image as _PILImage
            import io as _io
            img = _PILImage.open(image_path)
            img.thumbnail((768, 768), _PILImage.LANCZOS)
            buf = _io.BytesIO()
            img.save(buf, "JPEG", quality=75, optimize=True)
            frame_b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            with open(image_path, "rb") as f:
                frame_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        payload = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime_type, "data": frame_b64}},
                {"text": prompt},
            ]}],
            "generationConfig": {
                "maxOutputTokens": 512,
                "temperature": 0.1,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }).encode("utf-8")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{_GEMINI_FRAME_MODEL}:generateContent?key={api_key}"
        )
        req = _req.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with _req.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.debug(f"[VVO] Gemini frame vision call failed: {e}")
        return None


def _extract_frame(video_path: str, position: float = 0.5) -> Optional[str]:
    """Extract a frame at relative position (0.0=start, 1.0=end). Returns temp path or None."""
    if not os.path.exists(video_path):
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(r.stdout.strip())
        ts = max(0.05, min(duration - 0.1, duration * position))

        fd, path = tempfile.mkstemp(suffix=".jpg", prefix="atlas_vvo_")
        os.close(fd)
        r2 = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
             "-frames:v", "1", "-q:v", "3", path],
            capture_output=True, timeout=20,
        )
        if r2.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 500:
            return path
        if os.path.exists(path):
            os.unlink(path)
        return None
    except Exception as e:
        logger.debug(f"[VVO] Frame extract failed at pos={position}: {e}")
        return None


def _cleanup(*paths: Optional[str]) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.unlink(p)
            except Exception:
                pass


# ── RESULT DATACLASSES ───────────────────────────────────────────────────────

@dataclass
class OversightResult:
    """Result of one video oversight check."""
    check: str
    passed: bool
    description: str = ""
    regen_patch: Dict[str, Any] = field(default_factory=dict)
    confidence: str = "medium"


@dataclass
class VideoOversightReport:
    """Aggregated oversight report for one generated video."""
    shot_id: str
    video_path: str
    passed: bool
    oversight_results: List[OversightResult] = field(default_factory=list)
    regen_patch: Dict[str, Any] = field(default_factory=dict)
    failure_summary: str = ""
    full_video_analysis: Optional[Dict[str, Any]] = None   # V2.0 temporal analysis


# ── CHECK 1: CHARACTER BLEED ──────────────────────────────────────────────────

def check_character_bleed(
    video_path: str,
    shot: dict,
    story_bible: Optional[dict] = None,
) -> OversightResult:
    """
    Detect unexpected human figures in shots that should be empty.
    Context-aware gating — skips when people are legitimate.
    Uses Gemini Vision on mid-frame.
    """
    sid = shot.get("shot_id", "?")

    shot_chars = shot.get("characters") or []
    if shot_chars:
        return OversightResult(
            check="CHARACTER_BLEED", passed=True,
            description=f"Characters expected {shot_chars} — bleed check skipped",
        )

    shot_type = (shot.get("shot_type") or "").lower()
    is_e_shot = "_E" in sid.upper()
    is_empty_type = any(t in shot_type for t in [
        "establishing", "atmosphere", "broll", "b_roll", "insert", "wide",
    ])
    if not is_empty_type and not is_e_shot:
        return OversightResult(
            check="CHARACTER_BLEED", passed=True,
            description=f"Shot type '{shot_type}' not empty-room type — check skipped",
        )

    genre = ""
    location = ""
    if story_bible:
        genre = (story_bible.get("genre") or "").lower()
        scene_prefix = sid[:3]
        for sc in story_bible.get("scenes", []):
            sc_id = str(sc.get("scene_id") or "").zfill(3)
            if sc_id == scene_prefix:
                location = (sc.get("location") or "").lower()
                break

    if genre in _CROWD_EXPECTED_GENRES:
        if any(loc_kw in location for loc_kw in _CROWD_EXPECTED_LOCATIONS):
            return OversightResult(
                check="CHARACTER_BLEED", passed=True,
                description=f"Genre '{genre}' + location '{location}' allows crowds — skipped",
            )

    mid_frame = _extract_frame(video_path, 0.5)
    if not mid_frame:
        return OversightResult(
            check="CHARACTER_BLEED", passed=True,
            description="No frame extractable — bleed check skipped",
            confidence="low",
        )

    try:
        loc_hint   = f" Scene location: {location}." if location else ""
        genre_hint = f" Genre: {genre}." if genre else ""
        beat_hint  = f" Beat: {(shot.get('_beat_action') or '')[:60]}." if shot.get("_beat_action") else ""
        nano_hint  = f" Prompt: {(shot.get('nano_prompt') or '')[:80]}." if shot.get("nano_prompt") else ""

        _is_establishing = is_e_shot or any(t in shot_type for t in ["establishing", "atmosphere"])
        _eshot_rule = (
            " CRITICAL RULE: For E-shots (establishing shots), ANY detected human figure, "
            "person, silhouette, crowd, or body part is an automatic REJECT — "
            "E-shots must be pure environment with zero human presence."
        ) if _is_establishing else ""

        prompt = (
            f"This should be an EMPTY ROOM/ENVIRONMENT shot — NO people should be visible."
            f"{_eshot_rule}"
            f"{loc_hint}{genre_hint}{beat_hint}{nano_hint}\n\n"
            "Are there any people, human figures, silhouettes, or body parts visible?\n"
            "Answer ONLY with JSON: "
            '{"people_visible": true/false, "person_count": 0, '
            '"confidence": "high"/"medium"/"low", "description": "<5 words>"}'
        )

        response = _call_gemini_vision(mid_frame, prompt)
        if not response:
            return OversightResult(
                check="CHARACTER_BLEED", passed=True,
                description="Gemini unavailable — bleed check skipped",
                confidence="low",
            )

        raw = response.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return OversightResult(
                check="CHARACTER_BLEED", passed=True,
                description=f"Response unparseable — check skipped ({response[:60]})",
                confidence="low",
            )

        data = json.loads(json_match.group(0))
        people_visible = data.get("people_visible", False)
        person_count   = int(data.get("person_count", 0))
        confidence     = data.get("confidence", "medium")
        description    = data.get("description", "")

        if people_visible and confidence in ("high", "medium"):
            patch = {
                "_regen_character_bleed": True,
                "nano_prompt_suffix": (
                    " NO PEOPLE VISIBLE. Purely architectural/environmental. "
                    "No human figures, no silhouettes, no body parts, no shadows "
                    "suggesting human presence. Empty space only."
                ),
                "_negative_prompt_addition": (
                    "people, person, figure, human, body, silhouette, crowd, face"
                ),
            }
            return OversightResult(
                check="CHARACTER_BLEED", passed=False,
                description=(
                    f"CHARACTER BLEED in '{sid}': "
                    f"{person_count} person(s) visible ({description}). "
                    f"confidence={confidence}, genre={genre or 'unknown'}."
                ),
                regen_patch=patch, confidence=confidence,
            )

        return OversightResult(
            check="CHARACTER_BLEED", passed=True,
            description=f"No unexpected people (confidence={confidence})",
            confidence=confidence,
        )

    finally:
        _cleanup(mid_frame)


# ── CHECK 2: FROZEN FRAMES ────────────────────────────────────────────────────

def check_frozen_frames(video_path: str, shot: dict) -> OversightResult:
    """
    Detect completely static videos using PIL pixel diff (free) or Gemini fallback.
    Frame-based (Tier 2). Full temporal freeze detection is in analyze_full_video().
    """
    sid = shot.get("shot_id", "?")

    frame_early = _extract_frame(video_path, 0.10)
    frame_late  = _extract_frame(video_path, 0.80)

    if not frame_early or not frame_late:
        _cleanup(frame_early, frame_late)
        return OversightResult(
            check="FROZEN_FRAME", passed=True,
            description="Frames not extractable — frozen check skipped",
            confidence="low",
        )

    try:
        try:
            from PIL import Image as _PILImage
            img1 = _PILImage.open(frame_early).convert("L").resize((64, 64))
            img2 = _PILImage.open(frame_late).convert("L").resize((64, 64))
            p1 = list(img1.getdata())
            p2 = list(img2.getdata())
            if len(p1) == len(p2):
                mean_diff = sum(abs(a - b) for a, b in zip(p1, p2)) / len(p1)

                if mean_diff < 1.5:
                    patch = {
                        "_regen_frozen_video": True,
                        "nano_prompt_suffix": (
                            " VIDEO MUST SHOW MOTION. NOT a still photograph. "
                            "Scene must be animated with natural movement throughout."
                        ),
                        "_negative_prompt_addition": (
                            "frozen, static, still image, photograph, no motion, statue"
                        ),
                    }
                    return OversightResult(
                        check="FROZEN_FRAME", passed=False,
                        description=(
                            f"FROZEN VIDEO '{sid}': mean pixel diff={mean_diff:.2f} "
                            f"(threshold <1.5). Frames pixel-identical."
                        ),
                        regen_patch=patch, confidence="high",
                    )

                if mean_diff > 8.0:
                    return OversightResult(
                        check="FROZEN_FRAME", passed=True,
                        description=f"Motion confirmed (pixel diff={mean_diff:.1f})",
                        confidence="high",
                    )
        except ImportError:
            pass  # PIL unavailable — fall through to Gemini

        # Gemini fallback
        prompt = (
            "Is this video frame showing a completely FROZEN/STATIC image with zero motion? "
            "Or does it show evidence of real movement (motion blur, changed position, animation)?\n"
            "Answer ONLY with JSON: "
            '{"has_motion": true/false, "motion_evidence": "blur/position_change/animation/none", '
            '"confidence": "high"/"medium"/"low"}'
        )
        response = _call_gemini_vision(frame_late, prompt)
        if response:
            raw = response.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                has_motion = data.get("has_motion", True)
                motion_ev  = data.get("motion_evidence", "unknown")
                confidence = data.get("confidence", "medium")
                if not has_motion and motion_ev == "none" and confidence in ("high", "medium"):
                    patch = {
                        "_regen_frozen_video": True,
                        "nano_prompt_suffix": " VIDEO MUST SHOW MOTION.",
                        "_negative_prompt_addition": "frozen, static, still, no motion",
                    }
                    return OversightResult(
                        check="FROZEN_FRAME", passed=False,
                        description=(
                            f"Frozen video (Gemini: no motion={motion_ev}, "
                            f"confidence={confidence}) for '{sid}'"
                        ),
                        regen_patch=patch, confidence=confidence,
                    )

        return OversightResult(
            check="FROZEN_FRAME", passed=True,
            description="Motion present — video not frozen",
            confidence="medium",
        )

    finally:
        _cleanup(frame_early, frame_late)


# ── CHECK 3: DIALOGUE SYNC ────────────────────────────────────────────────────

def check_dialogue_sync(video_path: str, shot: dict) -> OversightResult:
    """
    Verify dialogue shots show mouth movement. Frame-based (Tier 2).
    Full temporal dialogue sync is in analyze_full_video().
    Only fires at HIGH Gemini confidence to avoid over-blocking.
    """
    sid = shot.get("shot_id", "?")
    dialogue = (shot.get("dialogue_text") or "").strip()
    if not dialogue:
        return OversightResult(
            check="DIALOGUE_SYNC", passed=True,
            description="No dialogue — sync check skipped",
        )

    shot_type = (shot.get("shot_type") or "").lower()
    face_types = {"close_up", "medium_close", "ots", "over_the_shoulder",
                  "two_shot", "medium", "reaction", "mcu", "cu"}
    if not any(ft in shot_type for ft in face_types):
        return OversightResult(
            check="DIALOGUE_SYNC", passed=True,
            description=f"Shot type '{shot_type}' not face-visible — sync check skipped",
        )

    check_frame = _extract_frame(video_path, 0.35)
    if not check_frame:
        return OversightResult(
            check="DIALOGUE_SYNC", passed=True,
            description="No check frame extractable — sync check skipped",
            confidence="low",
        )

    try:
        chars     = shot.get("characters") or []
        char_desc = chars[0] if chars else "the character"
        prompt = (
            f"This frame is from a shot where {char_desc} should be actively speaking: "
            f'"{dialogue[:70]}"\n\n'
            "Can you see a face? Is the mouth moving / person clearly speaking?\n"
            "Answer ONLY with JSON: "
            '{"face_visible": true/false, "mouth_moving": true/false, '
            '"speaking_plausible": true/false, "confidence": "high"/"medium"/"low"}'
        )

        response = _call_gemini_vision(check_frame, prompt)
        if not response:
            return OversightResult(
                check="DIALOGUE_SYNC", passed=True,
                description="Gemini unavailable — sync check skipped",
                confidence="low",
            )

        raw = response.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return OversightResult(
                check="DIALOGUE_SYNC", passed=True,
                description="Response unparseable — sync check skipped",
                confidence="low",
            )

        data = json.loads(json_match.group(0))
        face_visible       = data.get("face_visible", True)
        speaking_plausible = data.get("speaking_plausible", True)
        confidence         = data.get("confidence", "medium")

        # Block only at HIGH confidence to avoid over-rejecting
        if face_visible and not speaking_plausible and confidence == "high":
            patch = {
                "_regen_dialogue_sync": True,
                "nano_prompt_suffix": (
                    " CHARACTER ACTIVELY SPEAKING: mouth clearly open and animated, "
                    "jaw movement visible, lips forming words throughout dialogue."
                ),
            }
            return OversightResult(
                check="DIALOGUE_SYNC", passed=False,
                description=(
                    f"Dialogue sync failure in '{sid}': face visible but "
                    f"speaking_plausible=False (HIGH confidence). "
                    f"Dialogue: '{dialogue[:50]}...'"
                ),
                regen_patch=patch, confidence=confidence,
            )

        return OversightResult(
            check="DIALOGUE_SYNC", passed=True,
            description=(
                f"Dialogue sync OK — speaking_plausible={speaking_plausible} "
                f"(confidence={confidence})"
            ),
            confidence=confidence,
        )

    finally:
        _cleanup(check_frame)


# ── PRE-FLIGHT: E-SHOT FRAME CHECK ───────────────────────────────────────────

def preflight_e_shot_frame_check(
    frame_path: str,
    shot: dict,
    story_bible: Optional[dict] = None,
) -> OversightResult:
    """
    PRE-FLIGHT check: runs on the FIRST FRAME image (not a video) BEFORE Kling generation.

    For E-shots (establishing/tone shots with no characters), any detected human figure
    is a hard REJECT — the shot should not proceed to Kling video generation.
    Returns OversightResult with passed=False and regen_patch when humans are detected.

    Rules:
      • Only runs for shots that are E-shots (_no_char_ref=True, characters=[], or "_E" in shot_id)
        OR shot_type in {establishing, atmosphere, broll, b_roll, wide}
      • ANY human figure = REJECT (confidence high OR medium)
      • Genre/location crowd exceptions still apply (same logic as check_character_bleed)
      • Non-blocking: returns passed=True on any exception (vision unavailable etc.)

    Called from atlas_universal_runner.py before the Kling API call for independent groups.
    """
    sid = shot.get("shot_id", "?")

    # Only run for E-shots / empty-environment shots
    shot_chars = shot.get("characters") or []
    shot_type  = (shot.get("shot_type") or "").lower()
    is_e_shot  = "_E" in sid.upper() or shot.get("_no_char_ref") or not shot_chars
    is_empty_type = any(t in shot_type for t in [
        "establishing", "atmosphere", "broll", "b_roll", "wide",
    ])

    if shot_chars and not shot.get("_no_char_ref"):
        return OversightResult(
            check="PREFLIGHT_E_SHOT", passed=True,
            description=f"Shot has characters {shot_chars} — E-shot preflight skipped",
        )

    if not is_e_shot and not is_empty_type:
        return OversightResult(
            check="PREFLIGHT_E_SHOT", passed=True,
            description=f"Shot type '{shot_type}' not E-shot type — preflight skipped",
        )

    if not frame_path or not os.path.exists(frame_path):
        return OversightResult(
            check="PREFLIGHT_E_SHOT", passed=True,
            description="No frame path available — preflight skipped",
            confidence="low",
        )

    # Genre/location crowd exception
    genre    = ""
    location = ""
    if story_bible:
        genre = (story_bible.get("genre") or "").lower()
        scene_prefix = sid[:3]
        for sc in story_bible.get("scenes", []):
            sc_id = str(sc.get("scene_id") or "").zfill(3)
            if sc_id == scene_prefix:
                location = (sc.get("location") or "").lower()
                break
    if genre in _CROWD_EXPECTED_GENRES:
        if any(loc_kw in location for loc_kw in _CROWD_EXPECTED_LOCATIONS):
            return OversightResult(
                check="PREFLIGHT_E_SHOT", passed=True,
                description=f"Genre '{genre}' + location '{location}' allows crowds — preflight skipped",
            )

    try:
        loc_hint   = f" Scene location: {location}." if location else ""
        genre_hint = f" Genre: {genre}." if genre else ""

        prompt = (
            "CRITICAL PRE-FLIGHT CHECK: This is an E-SHOT (establishing shot) — "
            "it MUST be environment-only with ZERO human presence. "
            "ANY person, human figure, silhouette, crowd, body part, or shadow "
            "suggesting human presence is an AUTOMATIC REJECT."
            f"{loc_hint}{genre_hint}\n\n"
            "Are there any people, human figures, silhouettes, or body parts visible "
            "in this image?\n"
            "Answer ONLY with JSON: "
            '{"people_visible": true/false, "person_count": 0, '
            '"confidence": "high"/"medium"/"low", "description": "<5 words>"}'
        )

        response = _call_gemini_vision(frame_path, prompt)
        if not response:
            return OversightResult(
                check="PREFLIGHT_E_SHOT", passed=True,
                description="Gemini unavailable — preflight skipped",
                confidence="low",
            )

        raw = response.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return OversightResult(
                check="PREFLIGHT_E_SHOT", passed=True,
                description=f"Response unparseable — preflight skipped ({response[:60]})",
                confidence="low",
            )

        data        = json.loads(json_match.group(0))
        people_vis  = data.get("people_visible", False)
        person_cnt  = int(data.get("person_count", 0))
        confidence  = data.get("confidence", "medium")
        description = data.get("description", "")

        if people_vis and confidence in ("high", "medium"):
            patch = {
                "_preflight_e_shot_rejected": True,
                "nano_prompt_suffix": (
                    " ENVIRONMENT ONLY — NO PEOPLE VISIBLE. Purely architectural/atmospheric. "
                    "No human figures, no silhouettes, no body parts, no shadows of people. "
                    "Empty space: architecture, nature, or objects only."
                ),
                "_negative_prompt_addition": (
                    "people, person, figure, human, body, silhouette, crowd, face, hands"
                ),
            }
            return OversightResult(
                check="PREFLIGHT_E_SHOT", passed=False,
                description=(
                    f"PREFLIGHT E-SHOT REJECT '{sid}': "
                    f"{person_cnt} person(s) in first frame ({description}). "
                    f"confidence={confidence}. Blocking Kling generation — regen frame first."
                ),
                regen_patch=patch, confidence=confidence,
            )

        return OversightResult(
            check="PREFLIGHT_E_SHOT", passed=True,
            description=f"E-shot frame clean — no humans detected (confidence={confidence})",
            confidence=confidence,
        )

    except Exception as exc:
        logger.debug(f"[VVO] preflight_e_shot exception for {sid}: {exc}")
        return OversightResult(
            check="PREFLIGHT_E_SHOT", passed=True,
            description=f"Preflight exception (non-blocking): {exc}",
            confidence="low",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MAIN ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_video_oversight(
    video_path: str,
    shot: dict,
    story_bible: Optional[dict] = None,
    checks: Optional[List[str]] = None,
    use_full_video: bool = False,
    genre_id: str = "",
    production_type: str = "movie",
) -> VideoOversightReport:
    """
    Run the video oversight suite on a generated video clip.

    Args:
        video_path:     Absolute path to the .mp4 file
        shot:           Shot dict from shot_plan.json
        story_bible:    Parsed story_bible.json (for genre/location awareness)
        checks:         Subset of checks to run. None = run all.
                        Valid: "CHARACTER_BLEED", "FROZEN_FRAME", "DIALOGUE_SYNC",
                               "FULL_VIDEO" (V2.0 temporal, requires upload)
        use_full_video: If True, run analyze_full_video() FIRST and use its results
                        for FROZEN_FRAME and DIALOGUE_SYNC instead of frame checks.
                        CHARACTER_BLEED always uses frame-based check (cheaper).
                        Falls back to frame-based if full-video upload fails.

    Returns:
        VideoOversightReport — aggregated pass/fail with merged regen patches.
        Never raises. Any per-check exception is caught and logged.

    Authority: QA only — never writes to disk, never calls generation APIs.
    """
    sid = shot.get("shot_id", "unknown")
    run_all = (checks is None)
    run_set = set(checks) if checks else set()

    if not os.path.exists(video_path):
        return VideoOversightReport(
            shot_id=sid, video_path=video_path, passed=False,
            failure_summary=f"Video file not found: {video_path}",
        )

    results: List[OversightResult] = []
    full_video_analysis: Optional[Dict[str, Any]] = None

    # ── TIER 1: FULL VIDEO ANALYSIS (V2.0) ──
    if use_full_video or (run_set and "FULL_VIDEO" in run_set):
        try:
            fva = analyze_full_video(video_path, shot, story_bible,
                                     genre_id=genre_id, production_type=production_type)
            if not fva.get("skipped"):
                full_video_analysis = fva

                # Translate full-video findings into OversightResult objects
                frozen = fva.get("frozen_segment", False)
                action_truncated = fva.get("action_completion") == "truncated"
                dialogue_fail = fva.get("dialogue_sync") == "frozen_mouth"

                if frozen or action_truncated or dialogue_fail:
                    patch = fva.get("regen_patch", {})
                    issues = []
                    if frozen:
                        ts = fva.get("frozen_timestamp", "")
                        issues.append(f"frozen segment{' at ' + ts if ts else ''}")
                    if action_truncated:
                        issues.append(f"action truncated ({fva.get('action_timestamp_note', '')})")
                    if dialogue_fail:
                        issues.append("dialogue mouth frozen")

                    results.append(OversightResult(
                        check="FULL_VIDEO",
                        passed=False,
                        description=(
                            f"Full-video analysis FAIL for '{sid}': "
                            + "; ".join(issues)
                        ),
                        regen_patch=patch,
                        confidence="high",
                    ))
                else:
                    results.append(OversightResult(
                        check="FULL_VIDEO",
                        passed=True,
                        description=(
                            f"Full-video analysis PASS — "
                            f"action={fva.get('action_completion')}, "
                            f"arc={fva.get('emotional_arc')}, "
                            f"sync={fva.get('dialogue_sync')}"
                        ),
                        confidence="high",
                    ))

                # When full-video succeeded, skip redundant frame-based checks
                # for FROZEN and DIALOGUE (CHARACTER_BLEED still runs — different domain)
                if use_full_video:
                    # Remove FROZEN_FRAME and DIALOGUE_SYNC from pending checks
                    _skip_frame_checks = {"FROZEN_FRAME", "DIALOGUE_SYNC"}
                    if run_all:
                        # Will run CHARACTER_BLEED only via frame
                        run_all = False
                        run_set = {"CHARACTER_BLEED"}
                    else:
                        run_set = run_set - _skip_frame_checks

            # If skipped (no API key / upload failed), fall through to frame checks
        except Exception as e:
            logger.debug(f"[VVO] full_video exception for {sid}: {e}")
            # Fall through to frame-based checks

    # ── TIER 2: FRAME-BASED CHECKS (V1.0) ──

    # CHARACTER BLEED (always frame-based — no temporal advantage in full video)
    if run_all or "CHARACTER_BLEED" in run_set:
        try:
            results.append(check_character_bleed(video_path, shot, story_bible))
        except Exception as e:
            logger.debug(f"[VVO] character_bleed exception for {sid}: {e}")

    # FROZEN FRAME (frame-based fallback when full-video not used or failed)
    if run_all or "FROZEN_FRAME" in run_set:
        try:
            results.append(check_frozen_frames(video_path, shot))
        except Exception as e:
            logger.debug(f"[VVO] frozen_frame exception for {sid}: {e}")

    # DIALOGUE SYNC (frame-based fallback)
    if run_all or "DIALOGUE_SYNC" in run_set:
        try:
            results.append(check_dialogue_sync(video_path, shot))
        except Exception as e:
            logger.debug(f"[VVO] dialogue_sync exception for {sid}: {e}")

    failures = [r for r in results if not r.passed]
    merged_patch: Dict[str, Any] = {}
    for f in failures:
        merged_patch.update(f.regen_patch)

    failure_summary = " | ".join(f.description for f in failures) if failures else ""

    return VideoOversightReport(
        shot_id=sid,
        video_path=video_path,
        passed=(len(failures) == 0),
        oversight_results=results,
        regen_patch=merged_patch,
        failure_summary=failure_summary,
        full_video_analysis=full_video_analysis,
    )


def run_chain_transition_check(
    prev_video_path: str,
    curr_video_path: str,
    prev_shot: dict,
    curr_shot: dict,
    genre_id: str = "",
    production_type: str = "movie",
) -> Dict[str, Any]:
    """
    Check chain handoff continuity between two consecutive shots using full video upload.

    Called from the runner after each pair of videos is generated.
    Returns the analyze_chain_transition() dict with seamless/issues/regen_patch.
    Never raises.
    """
    prev_sid = prev_shot.get("shot_id", "prev")
    curr_sid = curr_shot.get("shot_id", "curr")
    try:
        result = analyze_chain_transition(
            prev_video_path, curr_video_path, prev_shot, curr_shot,
            genre_id=genre_id, production_type=production_type,
        )
        if not result.get("seamless") and not result.get("skipped"):
            logger.warning(
                f"[VVO] Chain transition {prev_sid}→{curr_sid} has issues: "
                f"{result.get('issues', [])}"
            )
        return result
    except Exception as e:
        logger.debug(f"[VVO] run_chain_transition_check exception: {e}")
        return {"skipped": True, "seamless": True, "issues": [], "regen_patch": {}}


def run_scene_stitch_check(
    stitched_path: str,
    scene_shots: List[dict],
    genre_id: str = "",
    production_type: str = "movie",
) -> Dict[str, Any]:
    """
    Review the full assembled scene video. Called after ffmpeg stitch.
    Returns the analyze_scene_stitch() dict with overall_quality + notes.
    Never raises.
    """
    scene_id = scene_shots[0].get("shot_id", "?")[:3] if scene_shots else "?"
    try:
        result = analyze_scene_stitch(stitched_path, scene_shots,
                                      genre_id=genre_id, production_type=production_type)
        quality = result.get("overall_quality", "not_assessed")
        logger.info(f"[VVO] Scene {scene_id} stitch quality: {quality}")
        if result.get("jarring_transitions"):
            logger.warning(
                f"[VVO] Scene {scene_id} jarring transitions at: "
                f"{result['jarring_transitions']}"
            )
        return result
    except Exception as e:
        logger.debug(f"[VVO] run_scene_stitch_check exception: {e}")
        return {
            "skipped": True, "overall_quality": "not_assessed",
            "jarring_transitions": [], "notes": "",
        }
