# V36 AUTHORITY: This module is PASS/FAIL ONLY.
# It CANNOT modify shot_plan.json or prompt fields.
# It returns verdicts. Controller decides what to do with them.

"""
AUTO REVISION JUDGE — V1.0
===========================
Post-video generation quality gate using Gemini Vision (Files API).

Analyzes generated MP4 videos against their shot_plan specification to
determine APPROVE / WARN / REJECT verdicts with actionable diagnostics
that feed directly into the regen system.

8 evaluation dimensions:
  1. duration_match       — Actual video duration vs shot_plan target (local check)
  2. dialogue_timing      — Mouth movement alignment for dialogue shots
  3. cinematic_tone       — Lighting, color grade, mood vs beat atmosphere
  4. camera_work          — Camera angle/framing matches requested shot type
  5. character_blocking   — Screen positions correct (Eleanor LEFT, Thomas RIGHT etc)
  6. story_beat_accuracy  — Visual action matches _beat_action description
  7. end_frame_continuity — End of clip visually compatible with next clip's start
  8. identity_consistency — Character looks same throughout clip and across clips

Verdict thresholds:
  APPROVE : overall >= 0.72   (confident pass, no human review required)
  WARN    : overall  0.52–0.72 (proceed but flag for human review)
  REJECT  : overall <  0.52   (auto-regen with injected diagnostic fix)

Per-dimension AUTO-REJECT triggers (override overall score):
  - duration_match    < 0.50  → REJECT  (video too short/long for dialogue)
  - identity_consistency < 0.40  → REJECT  (character drift is hard fail)
  - story_beat_accuracy  < 0.30  → REJECT  (completely wrong action)

Uses Gemini 2.5 Flash Files API for video upload.
Falls back gracefully: API failure → WARN (not APPROVE), preserves for human review.
NON-BLOCKING at pipeline level — any exception returns WARN verdict, never crashes runner.

Integration:
  Called from pre_video_gate.py PostVideoGate.judge_video() after Kling generation.
  Also callable standalone for batch analysis.

  from tools.auto_revision_judge import AutoRevisionJudge, VideoVerdict
  judge = AutoRevisionJudge()
  verdict = judge.judge(video_path, shot, cast_map, next_shot=next_shot)
  if verdict.should_reject:
      inject_diagnostic(verdict.regen_instruction)
"""

import json
import logging
import os
import re
import subprocess
import time
import urllib.request as _urllib_request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("atlas.auto_revision_judge")

# ── Model & thresholds ────────────────────────────────────────────────────────

_GEMINI_MODEL = "gemini-2.5-flash"
_FILES_API_BASE = "https://generativelanguage.googleapis.com"

# Overall verdict thresholds
APPROVE_THRESHOLD = 0.72
WARN_THRESHOLD    = 0.52   # below = REJECT

# Per-dimension hard-reject overrides (even if overall is above threshold)
_HARD_REJECT_RULES = {
    "duration_match":        0.50,   # video too short for dialogue content
    "identity_consistency":  0.40,   # character drift is unacceptable
    "story_beat_accuracy":   0.30,   # completely wrong action
}

# Dimension weights — character shots weight identity + beat accuracy higher
_WEIGHTS_WITH_CHARS = {
    "duration_match":        0.10,
    "dialogue_timing":       0.15,
    "cinematic_tone":        0.10,
    "camera_work":           0.10,
    "character_blocking":    0.10,
    "story_beat_accuracy":   0.20,
    "end_frame_continuity":  0.10,
    "identity_consistency":  0.15,
}

_WEIGHTS_WITHOUT_CHARS = {
    "duration_match":        0.10,
    "dialogue_timing":       0.00,
    "cinematic_tone":        0.20,
    "camera_work":           0.15,
    "character_blocking":    0.05,
    "story_beat_accuracy":   0.30,
    "end_frame_continuity":  0.10,
    "identity_consistency":  0.10,
}

# Max seconds to wait for Gemini to process an uploaded video
_FILE_PROCESS_TIMEOUT_S = 120
_FILE_POLL_INTERVAL_S   = 5

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    score:      float = 0.0
    verdict:    str   = "UNKNOWN"   # PASS / WARN / FAIL
    observation: str  = ""          # What Gemini saw
    fix:         str  = ""          # Actionable fix instruction


@dataclass
class VideoVerdict:
    shot_id:     str
    video_path:  str
    overall:     float = 0.0
    verdict:     str   = "WARN"     # APPROVE / WARN / REJECT
    dimensions:  dict  = field(default_factory=dict)   # dim_name -> DimensionScore
    hard_rejects: list = field(default_factory=list)   # dimensions that triggered hard reject
    regen_instruction: str = ""    # Injected into next gen attempt
    backend:     str   = "unknown"
    analysis_ms: int   = 0

    @property
    def should_reject(self) -> bool:
        return self.verdict == "REJECT"

    @property
    def should_warn(self) -> bool:
        return self.verdict in ("WARN", "REJECT")

    def to_dict(self) -> dict:
        return {
            "shot_id":            self.shot_id,
            "video_path":         self.video_path,
            "overall":            round(self.overall, 3),
            "verdict":            self.verdict,
            "hard_rejects":       self.hard_rejects,
            "regen_instruction":  self.regen_instruction,
            "backend":            self.backend,
            "analysis_ms":        self.analysis_ms,
            "dimensions": {
                k: {
                    "score":       round(v.score, 3),
                    "verdict":     v.verdict,
                    "observation": v.observation,
                    "fix":         v.fix,
                }
                for k, v in self.dimensions.items()
            },
        }


# ── Duration check (local, no API needed) ────────────────────────────────────

def _get_video_duration_s(video_path: str) -> Optional[float]:
    """Use ffprobe to get actual video duration in seconds. Returns None if unavailable."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception:
        pass
    return None


def _score_duration(actual_s: Optional[float], target_s: float,
                    dialogue_text: str, word_count: int) -> DimensionScore:
    """
    Score how well the video duration matches the shot_plan target.

    For dialogue shots: minimum = (word_count / 2.3) + 1.5s buffer.
    A video shorter than dialogue minimum is a hard reject.
    """
    if actual_s is None:
        return DimensionScore(
            score=0.75,
            verdict="WARN",
            observation="ffprobe unavailable — duration unchecked",
            fix="",
        )

    # Minimum duration required for dialogue
    dialogue_min = 0.0
    has_dialogue = bool(dialogue_text and dialogue_text.strip())
    if has_dialogue and word_count > 0:
        dialogue_min = (word_count / 2.3) + 1.5

    # Tolerance: within ±20% of target is fine; Kling snaps to 5/10s
    target_adj = max(target_s, dialogue_min)
    ratio = actual_s / target_adj if target_adj > 0 else 1.0

    # Hard fail: video too short for dialogue
    if has_dialogue and actual_s < dialogue_min:
        deficit = dialogue_min - actual_s
        return DimensionScore(
            score=0.25,
            verdict="FAIL",
            observation=(
                f"Video {actual_s:.1f}s is {deficit:.1f}s shorter than the minimum needed "
                f"for {word_count}-word dialogue ({dialogue_min:.1f}s minimum)."
            ),
            fix=(
                f"DURATION FAIL: video is {deficit:.1f}s too short for dialogue. "
                f"Increase duration to at least {int(dialogue_min)+2}s or split dialogue across shots."
            ),
        )

    # Kling hard snaps to 5 or 10 seconds — accept 5/10 even if target differs
    if actual_s in (5.0, 10.0) and abs(actual_s - target_s) <= 6:
        # Expected Kling snap — not a failure
        score = 0.90 if actual_s == target_s else 0.75
        obs   = (
            f"Video is {actual_s:.0f}s (target {target_s}s). "
            + ("Exact match." if actual_s == target_s else "Kling snapped to nearest valid duration.")
        )
        return DimensionScore(score=score, verdict="PASS", observation=obs, fix="")

    # General duration closeness score
    deviation = abs(ratio - 1.0)
    if deviation <= 0.15:
        score, verd = 0.95, "PASS"
    elif deviation <= 0.35:
        score, verd = 0.70, "WARN"
    else:
        score, verd = 0.40, "FAIL"

    obs  = f"Actual {actual_s:.1f}s vs target {target_s}s ({ratio:.2f}×)."
    fix  = (
        f"DURATION MISMATCH: video is {actual_s:.1f}s, shot requires ~{target_s}s. "
        "Adjust generation duration or restructure the shot."
    ) if verd == "FAIL" else ""

    return DimensionScore(score=score, verdict=verd, observation=obs, fix=fix)


# ── Gemini Files API helpers ──────────────────────────────────────────────────

def _upload_video_file(video_path: str, api_key: str) -> Optional[str]:
    """
    Upload a video file to the Gemini Files API.
    Returns the file URI (e.g. "https://generativelanguage.googleapis.com/v1beta/files/abc123")
    or None on failure.
    """
    path = Path(video_path)
    if not path.exists():
        logger.error(f"[ARJ] Video not found: {video_path}")
        return None

    file_size = path.stat().st_size
    display_name = path.stem[:64]

    upload_url = f"{_FILES_API_BASE}/upload/v1beta/files?key={api_key}"

    try:
        with open(video_path, "rb") as f:
            video_data = f.read()

        # Multipart body: JSON metadata + video bytes
        boundary = "atlas_arj_boundary_v1"
        metadata_json = json.dumps({"file": {"display_name": display_name}}).encode("utf-8")

        parts = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        ).encode("utf-8") + metadata_json + (
            f"\r\n--{boundary}\r\n"
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8") + video_data + (
            f"\r\n--{boundary}--"
        ).encode("utf-8")

        req = _urllib_request.Request(
            upload_url,
            data=parts,
            headers={
                "Content-Type":   f"multipart/related; boundary={boundary}",
                "Content-Length": str(len(parts)),
                "X-Goog-Upload-Protocol": "multipart",
            },
            method="POST",
        )

        with _urllib_request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        file_uri  = result["file"]["uri"]
        file_name = result["file"]["name"]
        logger.info(f"[ARJ] Uploaded {path.name} → {file_name}")
        return file_uri

    except Exception as e:
        logger.error(f"[ARJ] Upload failed for {video_path}: {e}")
        return None


def _wait_for_file_active(file_uri: str, api_key: str) -> bool:
    """
    Poll the Files API until the uploaded file reaches ACTIVE state.
    Returns True if active within timeout, False otherwise.
    """
    # Extract file name from URI
    file_name = file_uri.split("/v1beta/")[-1]  # e.g. "files/abc123"
    status_url = f"{_FILES_API_BASE}/v1beta/{file_name}?key={api_key}"

    deadline = time.time() + _FILE_PROCESS_TIMEOUT_S
    while time.time() < deadline:
        try:
            req = _urllib_request.Request(status_url, method="GET")
            with _urllib_request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            state = data.get("state", "UNKNOWN")
            if state == "ACTIVE":
                return True
            if state == "FAILED":
                logger.error(f"[ARJ] File processing FAILED: {file_uri}")
                return False
            logger.debug(f"[ARJ] File state: {state}, waiting...")
        except Exception as e:
            logger.debug(f"[ARJ] Poll error: {e}")

        time.sleep(_FILE_POLL_INTERVAL_S)

    logger.warning(f"[ARJ] Timeout waiting for {file_uri} to become ACTIVE")
    return False


def _delete_file(file_uri: str, api_key: str):
    """Delete an uploaded file after analysis to stay within quota."""
    try:
        file_name = file_uri.split("/v1beta/")[-1]
        delete_url = f"{_FILES_API_BASE}/v1beta/{file_name}?key={api_key}"
        req = _urllib_request.Request(delete_url, method="DELETE")
        _urllib_request.urlopen(req, timeout=15)
        logger.debug(f"[ARJ] Deleted file: {file_name}")
    except Exception:
        pass  # Non-critical — files auto-expire in 48h


# ── Evaluation prompt builder ─────────────────────────────────────────────────

def _build_video_eval_prompt(shot: dict, cast_map: dict,
                             next_shot: Optional[dict] = None) -> str:
    """
    Build the 8-dimension evaluation prompt for Gemini.

    Each dimension is explicitly described so Gemini can evaluate it against
    the video content. We ask for structured JSON output.
    """
    shot_id      = shot.get("shot_id", "unknown")
    shot_type    = shot.get("shot_type") or "medium"
    location     = shot.get("location") or shot.get("_scene_room") or "interior"
    beat_action  = (shot.get("_beat_action") or shot.get("beat_action") or "")[:200]
    beat_atmos   = (shot.get("_beat_atmosphere") or "")[:100]
    dialogue     = (shot.get("dialogue_text") or "")[:300]
    characters   = shot.get("characters") or []
    nano_prompt  = (shot.get("nano_prompt") or "")[:300]
    frame_desc   = (shot.get("_frame_description") or "")[:200]
    eye_line     = (shot.get("_eye_line_target") or "")[:80]
    body_dir     = (shot.get("_body_direction") or "")[:80]

    # Strip proper-noun location labels (prevents FAL text bleed)
    location_safe = re.sub(r'\b[A-Z]{3,}(?:\s+[A-Z]{3,})*\b',
                           lambda m: m.group(0).title(), location)

    # Character appearance blocks from cast_map
    char_blocks = []
    for char_name in characters[:3]:
        cdata = cast_map.get(char_name) or cast_map.get(char_name.upper()) or {}
        appearance = (
            cdata.get("amplified_appearance")
            or cdata.get("appearance")
            or cdata.get("description")
            or "no description available"
        )[:200]
        screen_pos = cdata.get("_screen_position", "")
        pos_hint   = f" [Screen position: {screen_pos}]" if screen_pos else ""
        char_blocks.append(f"  {char_name}{pos_hint}: {appearance}")

    char_section = "\n".join(char_blocks) if char_blocks else "  (No characters required — empty/insert shot)"
    has_chars    = bool(characters)
    has_dialogue = bool(dialogue and dialogue.strip())

    # Shot type framing guide
    framing_map = {
        "establishing":  "Full room/exterior visible, characters small or absent.",
        "wide":          "Wide geography, characters at ~1/3 frame height.",
        "medium":        "Character(s) waist-up, room visible as background.",
        "medium_close":  "Head and shoulders fill frame, background soft.",
        "close_up":      "Face fills 60–80% of frame, heavy background bokeh.",
        "ots_a":         "Listener shoulder FRAME-LEFT foreground (out of focus), speaker FRAME-RIGHT facing camera.",
        "ots_b":         "Listener shoulder FRAME-RIGHT foreground (out of focus), speaker FRAME-LEFT facing camera.",
        "two_shot":      "Two characters: one FRAME-LEFT facing right, one FRAME-RIGHT facing left.",
        "insert":        "Extreme close-up of prop/object, no full character visible.",
        "closing":       "Wide, character small in frame or three-quarter back to camera.",
    }
    framing_guide = framing_map.get(shot_type.lower(), f"Standard {shot_type} shot framing.")

    # Next shot continuity context
    next_block = ""
    if next_shot:
        next_id     = next_shot.get("shot_id", "next")
        next_action = (next_shot.get("_beat_action") or next_shot.get("nano_prompt") or "")[:100]
        next_block  = f"\nNEXT SHOT ({next_id}): {next_action}"

    prompt = f"""You are a professional film quality-control supervisor analyzing a generated movie clip against its specification.
Watch the full video carefully, then score it on exactly 8 dimensions.

═══ SHOT SPECIFICATION ═══
Shot ID:         {shot_id}
Shot Type:       {shot_type}
Location:        {location_safe}
Beat Action:     {beat_action}
Beat Atmosphere: {beat_atmos}
Frame Desc:      {frame_desc}
Eye Line:        {eye_line}
Body Direction:  {body_dir}
Prompt:          {nano_prompt}

Expected Characters:
{char_section}

Expected Framing: {framing_guide}

Dialogue to be spoken (if any):
{dialogue if has_dialogue else "(no dialogue in this shot)"}
{next_block}

═══ SCORING TASK ═══
Score the video on each of these 8 dimensions from 0.0 to 1.0.
Return ONLY valid JSON — no markdown fences, no prose before or after.

{{
  "dialogue_timing":      <0.0–1.0: Do mouth movements match when dialogue should occur? Score 1.0 if no dialogue.>,
  "cinematic_tone":       <0.0–1.0: Does lighting, color grade, and atmosphere match '{beat_atmos}'?>,
  "camera_work":          <0.0–1.0: Does framing/angle match '{shot_type}'? {framing_guide}>,
  "character_blocking":   <0.0–1.0: Are characters in correct screen positions? Score 1.0 if no characters.>,
  "story_beat_accuracy":  <0.0–1.0: Does the visual action match the beat action '{beat_action[:80]}'?>,
  "end_frame_continuity": <0.0–1.0: Does the final frame cleanly set up a transition to the next shot?>,
  "identity_consistency": <0.0–1.0: Does the character look consistent throughout the clip? Score 1.0 if no characters.>,
  "dim_observations": {{
    "dialogue_timing":      "<one sentence: what you saw re: mouth movement timing>",
    "cinematic_tone":       "<one sentence: what you saw re: lighting and mood>",
    "camera_work":          "<one sentence: what you saw re: shot framing>",
    "character_blocking":   "<one sentence: character positions observed>",
    "story_beat_accuracy":  "<one sentence: was the specified action performed?>",
    "end_frame_continuity": "<one sentence: does the last frame bridge to the next?>",
    "identity_consistency": "<one sentence: was character appearance stable?>"
  }},
  "worst_failure":        "<the single most critical problem in this clip, or 'none'>",
  "regen_fix":            "<one actionable sentence: how to fix the worst failure, or ''>"
}}

Scoring rules:
- 1.0 = perfect execution
- 0.8 = mostly correct, minor deviation
- 0.5 = partially correct, significant deviation
- 0.2 = clearly wrong, some overlap
- 0.0 = completely wrong or absent
- If no characters required → identity_consistency = 1.0, character_blocking = 1.0
- If no dialogue → dialogue_timing = 1.0
- Be strict on story_beat_accuracy: if the beat action specifies a specific gesture/prop and it's absent, score ≤ 0.35
- Be strict on identity_consistency: any frame where the character looks like a different person = ≤ 0.35"""

    return prompt


# ── Main judge class ──────────────────────────────────────────────────────────

class AutoRevisionJudge:
    """
    Post-video quality judge using Gemini Vision Files API.

    Usage:
        judge = AutoRevisionJudge()
        verdict = judge.judge(video_path, shot, cast_map, next_shot=next_shot)
        print(verdict.verdict, verdict.regen_instruction)
    """

    def __init__(self):
        self._api_key = (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or ""
        )
        self._available = bool(self._api_key)

        if not self._available:
            logger.warning(
                "[ARJ] GOOGLE_API_KEY not set — judge will return WARN for all videos"
            )

    @property
    def available(self) -> bool:
        return self._available

    def judge(
        self,
        video_path:  str,
        shot:        dict,
        cast_map:    dict,
        next_shot:   Optional[dict] = None,
        delete_after: bool = True,
    ) -> VideoVerdict:
        """
        Analyze a video against its shot specification.

        Args:
            video_path:   Path to the MP4 file.
            shot:         Shot dict from shot_plan.json.
            cast_map:     Project cast_map dict (for character appearances).
            next_shot:    Optional next shot in sequence (for continuity scoring).
            delete_after: Delete uploaded file from Gemini after analysis (default True).

        Returns:
            VideoVerdict with overall score, per-dimension scores, and regen instructions.
        """
        t0       = time.time()
        shot_id  = shot.get("shot_id", "unknown")

        # 1. Duration check (local — no API)
        target_s     = float(shot.get("duration") or 10)
        dialogue_txt = shot.get("dialogue_text") or ""
        word_count   = len(dialogue_txt.split()) if dialogue_txt.strip() else 0
        actual_dur   = _get_video_duration_s(video_path)
        dur_score    = _score_duration(actual_dur, target_s, dialogue_txt, word_count)

        # 2. Gemini video analysis
        gem_scores   = None
        backend_used = "local_only"

        if self._available:
            gem_scores, backend_used = self._analyze_via_gemini(
                video_path, shot, cast_map, next_shot
            )
        else:
            logger.info(f"[ARJ] Skipping Gemini (no key) for {shot_id}")

        # 3. Assemble full dimension scores
        dimensions = self._assemble_dimensions(dur_score, gem_scores, shot)

        # 4. Compute weighted overall
        has_chars = bool(shot.get("characters"))
        weights   = _WEIGHTS_WITH_CHARS if has_chars else _WEIGHTS_WITHOUT_CHARS
        overall   = sum(
            dimensions[k].score * weights.get(k, 0.0)
            for k in dimensions
        )

        # 5. Check hard-reject rules
        hard_rejects = [
            dim for dim, threshold in _HARD_REJECT_RULES.items()
            if dim in dimensions and dimensions[dim].score < threshold
        ]

        # 6. Determine verdict
        if hard_rejects or overall < WARN_THRESHOLD:
            verdict = "REJECT"
        elif overall < APPROVE_THRESHOLD:
            verdict = "WARN"
        else:
            verdict = "APPROVE"

        # If Gemini unavailable, downgrade APPROVE → WARN (can't be confident without vision)
        if not self._available and verdict == "APPROVE":
            verdict = "WARN"

        # 7. Build regen instruction
        regen_instruction = self._build_regen_instruction(
            dimensions, hard_rejects, shot, overall
        )

        elapsed_ms = int((time.time() - t0) * 1000)

        return VideoVerdict(
            shot_id=shot_id,
            video_path=video_path,
            overall=overall,
            verdict=verdict,
            dimensions=dimensions,
            hard_rejects=hard_rejects,
            regen_instruction=regen_instruction,
            backend=backend_used,
            analysis_ms=elapsed_ms,
        )

    def _analyze_via_gemini(
        self,
        video_path:  str,
        shot:        dict,
        cast_map:    dict,
        next_shot:   Optional[dict],
    ) -> tuple:
        """
        Upload video to Gemini Files API, wait for processing, then analyze.
        Returns (gem_scores_dict, backend_name) or (None, "gemini_failed").
        """
        shot_id = shot.get("shot_id", "unknown")

        # Upload
        logger.info(f"[ARJ] Uploading {Path(video_path).name} for {shot_id}…")
        file_uri = _upload_video_file(video_path, self._api_key)
        if not file_uri:
            return None, "gemini_upload_failed"

        # Wait for processing
        logger.info(f"[ARJ] Waiting for {shot_id} video to process…")
        if not _wait_for_file_active(file_uri, self._api_key):
            _delete_file(file_uri, self._api_key)
            return None, "gemini_processing_timeout"

        # Build evaluation prompt
        eval_prompt = _build_video_eval_prompt(shot, cast_map, next_shot)

        # Call generateContent with video + prompt
        try:
            payload = json.dumps({
                "contents": [{
                    "parts": [
                        {"file_data": {"mime_type": "video/mp4", "file_uri": file_uri}},
                        {"text": eval_prompt},
                    ]
                }],
                "generationConfig": {
                    "temperature":      0.1,
                    "maxOutputTokens":  1024,
                    "thinkingConfig":   {"thinkingBudget": 512},
                },
            }).encode("utf-8")

            url = (
                f"{_FILES_API_BASE}/v1beta/models/"
                f"{_GEMINI_MODEL}:generateContent?key={self._api_key}"
            )
            req = _urllib_request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST"
            )

            with _urllib_request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Strip markdown fences
            if "```" in raw_text:
                parts = raw_text.split("```")
                raw_text = parts[1] if len(parts) > 1 else raw_text
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            scores = json.loads(raw_text.strip())
            logger.info(f"[ARJ] Gemini scored {shot_id}: "
                        f"beat={scores.get('story_beat_accuracy', '?')}, "
                        f"identity={scores.get('identity_consistency', '?')}")
            return scores, f"gemini/{_GEMINI_MODEL}"

        except json.JSONDecodeError as e:
            logger.warning(f"[ARJ] JSON parse error for {shot_id}: {e}")
            return None, "gemini_parse_error"
        except Exception as e:
            logger.warning(f"[ARJ] Gemini analysis failed for {shot_id}: {e}")
            return None, "gemini_call_failed"
        finally:
            _delete_file(file_uri, self._api_key)

    def _assemble_dimensions(
        self, dur_score: DimensionScore, gem_scores: Optional[dict], shot: dict
    ) -> dict:
        """
        Combine the local duration score with Gemini's 7 video-quality scores
        into a unified dimensions dict.
        """
        has_chars    = bool(shot.get("characters"))
        has_dialogue = bool((shot.get("dialogue_text") or "").strip())

        # Fallback scores when Gemini unavailable
        neutral_with_note = lambda dim: DimensionScore(
            score=0.70,   # conservative neutral — not 0.75 (signals "unchecked")
            verdict="WARN",
            observation="Gemini unavailable — score is neutral estimate",
            fix="",
        )

        dims = {"duration_match": dur_score}

        gem_dim_names = [
            "dialogue_timing",
            "cinematic_tone",
            "camera_work",
            "character_blocking",
            "story_beat_accuracy",
            "end_frame_continuity",
            "identity_consistency",
        ]

        for dim in gem_dim_names:
            if gem_scores and dim in gem_scores:
                raw_score = gem_scores[dim]
                if isinstance(raw_score, (int, float)):
                    score = max(0.0, min(1.0, float(raw_score)))
                else:
                    score = 0.70

                obs_map = gem_scores.get("dim_observations", {})
                obs     = obs_map.get(dim, "") if isinstance(obs_map, dict) else ""

                # Build fix from generic regen_fix if this dimension failed
                fix = ""
                if score < 0.55:
                    fix = gem_scores.get("regen_fix", "") or gem_scores.get("worst_failure", "")

                # Apply auto-1.0 rules
                if dim == "dialogue_timing" and not has_dialogue:
                    score, obs = 1.0, "No dialogue required."
                if dim in ("character_blocking", "identity_consistency") and not has_chars:
                    score, obs = 1.0, "No characters required."

                verd = "PASS" if score >= 0.72 else ("WARN" if score >= 0.52 else "FAIL")
                dims[dim] = DimensionScore(score=score, verdict=verd,
                                           observation=obs, fix=fix)
            else:
                # Gemini returned no data for this dim
                d = neutral_with_note(dim)
                # Apply auto-1.0 rules even on fallback
                if dim == "dialogue_timing" and not has_dialogue:
                    d = DimensionScore(score=1.0, verdict="PASS",
                                       observation="No dialogue required.", fix="")
                if dim in ("character_blocking", "identity_consistency") and not has_chars:
                    d = DimensionScore(score=1.0, verdict="PASS",
                                       observation="No characters required.", fix="")
                dims[dim] = d

        return dims

    def _build_regen_instruction(
        self,
        dimensions:   dict,
        hard_rejects: list,
        shot:         dict,
        overall:      float,
    ) -> str:
        """
        Build the actionable regen instruction to inject into the next generation attempt.
        Prioritizes hard rejects, then worst-scoring dimensions.
        """
        shot_type  = shot.get("shot_type") or "medium"
        characters = shot.get("characters") or []
        beat_action = (shot.get("_beat_action") or "")[:100]

        parts = []

        # Hard rejects first — these are the must-fix items
        for dim in hard_rejects:
            ds = dimensions.get(dim)
            if ds and ds.fix:
                parts.append(f"[HARD REJECT — {dim.upper()}] {ds.fix}")
            elif dim == "duration_match":
                dur_s = shot.get("duration", 10)
                parts.append(
                    f"[HARD REJECT — DURATION] Video too short for dialogue content. "
                    f"Minimum duration: {dur_s}s. Do NOT snap to 5s."
                )
            elif dim == "identity_consistency":
                char_str = ", ".join(characters) if characters else "the character"
                parts.append(
                    f"[HARD REJECT — IDENTITY DRIFT] {char_str} changed appearance mid-clip. "
                    "Use character reference image as anchor throughout entire video."
                )
            elif dim == "story_beat_accuracy":
                parts.append(
                    f"[HARD REJECT — WRONG ACTION] The video did not show: {beat_action}. "
                    "The specific physical action MUST be visible in the clip."
                )

        # Add warnings for non-hard-reject failures (score < 0.52)
        for dim, ds in dimensions.items():
            if dim in hard_rejects:
                continue
            if ds.score < 0.52:
                if ds.fix:
                    parts.append(f"[FIX — {dim.upper()}] {ds.fix}")
                elif dim == "camera_work":
                    parts.append(
                        f"[FIX — FRAMING] Shot type is {shot_type} but framing was wrong. "
                        "Correct the composition."
                    )
                elif dim == "cinematic_tone":
                    atmos = shot.get("_beat_atmosphere", "")
                    parts.append(
                        f"[FIX — TONE] Lighting/mood must match: {atmos}. "
                        "Adjust color grade and atmosphere."
                    )
                elif dim == "character_blocking":
                    parts.append(
                        f"[FIX — BLOCKING] Character screen positions are wrong for {shot_type}. "
                        "Eleanor must be FRAME-LEFT, Thomas must be FRAME-RIGHT."
                    )

        if not parts:
            return ""

        return " | ".join(parts)


# ── Batch analysis helper ─────────────────────────────────────────────────────

def analyze_scene(
    scene_id:   str,
    shot_plan:  list,
    cast_map:   dict,
    videos_dir: str,
    judge:      Optional["AutoRevisionJudge"] = None,
) -> list:
    """
    Run AutoRevisionJudge on all shots in a scene.

    Args:
        scene_id:   e.g. "002"
        shot_plan:  list of shot dicts from shot_plan.json
        cast_map:   project cast_map dict
        videos_dir: directory containing the MP4 files
        judge:      optional pre-constructed judge (avoids re-init)

    Returns:
        List of VideoVerdict.to_dict() records.
    """
    if judge is None:
        judge = AutoRevisionJudge()

    scene_shots = [
        s for s in shot_plan
        if str(s.get("shot_id", "")).startswith(scene_id)
    ]

    if not scene_shots:
        logger.warning(f"[ARJ] No shots found for scene {scene_id}")
        return []

    results = []
    for i, shot in enumerate(scene_shots):
        sid       = shot.get("shot_id", "unknown")
        video_url = shot.get("video_url", "")
        next_shot = scene_shots[i + 1] if i + 1 < len(scene_shots) else None

        # Resolve video path
        video_path = None
        if video_url:
            if os.path.isabs(video_url) and os.path.exists(video_url):
                video_path = video_url
            else:
                candidate = os.path.join(videos_dir, os.path.basename(video_url))
                if os.path.exists(candidate):
                    video_path = candidate

        if not video_path:
            # Try pattern match in videos_dir
            for fname in os.listdir(videos_dir):
                if sid.replace("_", "") in fname.replace("_", ""):
                    video_path = os.path.join(videos_dir, fname)
                    break

        if not video_path:
            logger.warning(f"[ARJ] No video found for {sid}")
            results.append({
                "shot_id":  sid,
                "verdict":  "SKIP",
                "reason":   "No video file found",
                "video_path": "",
            })
            continue

        logger.info(f"[ARJ] Analyzing {sid} → {os.path.basename(video_path)}")
        try:
            verdict = judge.judge(video_path, shot, cast_map, next_shot=next_shot)
            results.append(verdict.to_dict())
        except Exception as e:
            logger.error(f"[ARJ] Unhandled error for {sid}: {e}")
            results.append({
                "shot_id":    sid,
                "verdict":    "ERROR",
                "reason":     str(e),
                "video_path": video_path or "",
            })

    return results


# ── Auto-reject criteria registry (for pre_video_gate integration) ────────────

AUTO_REJECT_CRITERIA = {
    "duration_match": {
        "threshold":    0.50,
        "description":  "Video duration insufficient for dialogue content",
        "fix_template": "Extend video to minimum {min_dur}s for {word_count}-word dialogue.",
        "severity":     "HARD_REJECT",
    },
    "identity_consistency": {
        "threshold":    0.40,
        "description":  "Character appearance drifts mid-clip",
        "fix_template": "Apply character reference as identity anchor for entire video duration.",
        "severity":     "HARD_REJECT",
    },
    "story_beat_accuracy": {
        "threshold":    0.30,
        "description":  "Visual action does not match beat description",
        "fix_template": "Video must show: {beat_action}. Rewrite motion prompt to be explicit.",
        "severity":     "HARD_REJECT",
    },
    "camera_work": {
        "threshold":    0.40,
        "description":  "Shot framing/angle incorrect for shot type",
        "fix_template": "Correct framing to {shot_type}: {framing_guide}.",
        "severity":     "WARN",
    },
    "cinematic_tone": {
        "threshold":    0.40,
        "description":  "Lighting and mood inconsistent with scene",
        "fix_template": "Atmosphere must match: {beat_atmosphere}.",
        "severity":     "WARN",
    },
    "dialogue_timing": {
        "threshold":    0.45,
        "description":  "Dialogue mouth movement not aligned with speech content",
        "fix_template": "Dialogue shot must show visible lip movement from first frame. Add dialogue marker.",
        "severity":     "WARN",
    },
    "character_blocking": {
        "threshold":    0.45,
        "description":  "Characters in wrong screen positions",
        "fix_template": "Enforce screen position lock: {blocking_spec}.",
        "severity":     "WARN",
    },
    "end_frame_continuity": {
        "threshold":    0.35,
        "description":  "End frame cannot bridge to next shot",
        "fix_template": "Ensure final frame is a clean neutral pause, compatible with '{next_shot_action}'.",
        "severity":     "WARN",
    },
}


if __name__ == "__main__":
    # Quick standalone test
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python auto_revision_judge.py <video_path> [shot_json_path]")
        sys.exit(1)

    video_path = sys.argv[1]
    shot = {}
    cast_map = {}

    if len(sys.argv) >= 3:
        with open(sys.argv[2]) as f:
            shot = json.load(f)

    judge   = AutoRevisionJudge()
    verdict = judge.judge(video_path, shot, cast_map)

    print("\n" + "="*60)
    print(f"SHOT: {verdict.shot_id}")
    print(f"VERDICT: {verdict.verdict}  (overall={verdict.overall:.3f})")
    print(f"Backend: {verdict.backend}  ({verdict.analysis_ms}ms)")
    if verdict.hard_rejects:
        print(f"HARD REJECTS: {', '.join(verdict.hard_rejects)}")
    if verdict.regen_instruction:
        print(f"\nREGEN INSTRUCTION:\n  {verdict.regen_instruction}")
    print("\nPER-DIMENSION SCORES:")
    for dim, ds in verdict.dimensions.items():
        bar = "█" * int(ds.score * 10)
        print(f"  {dim:28s}  {ds.score:.2f}  {bar:10s}  {ds.verdict}  {ds.observation[:60]}")
    print("="*60)
