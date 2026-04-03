# V36 AUTHORITY: This module is PASS/FAIL ONLY.
# It CANNOT modify shot_plan.json or prompt fields.
# It returns verdicts. Controller decides what to do with them.

"""
PRE-VIDEO QUALITY GATE — V31.1
=================================
Scores generated first frames against canonical shot expectations BEFORE
Kling video generation. Catches bad frames before they waste $3-12 per call.

Architecture (where this sits):
    gen_frame() → judge_frame() [identity-only, Wire A]
                → PRE_VIDEO_GATE [holistic canonical match]  ← THIS FILE
                → gen_scene_multishot() [Kling video, $3-12]

The gate compares the actual frame against the FULL canonical specification:
    1. nano_prompt  — what was explicitly requested
    2. Room DNA     — what architecture/location was specified
    3. beat_action  — what should be happening
    4. characters   — who should appear (appearance from cast_map)

4 scored dimensions (Gemini Vision):
    location_match    — Is the right location/architecture shown?
    character_identity — Are the right characters present and correct?
    blocking_accuracy  — Is the shot framed correctly for its type?
    mood_lighting      — Does the lighting/atmosphere match the beat?

If overall score < CANONICAL_REGEN_THRESHOLD:
    → Build diagnostic string from failed dimensions
    → Inject into shot._pvg_diagnostic
    → gen_frame() reads this and prepends it as a CORRECTION directive
    → Re-score. If still failing after MAX_GATE_REGENS: FLAG and proceed
      (Wire B will block truly broken shots from the stitch)

Called from atlas_universal_runner.py run_scene(), between Phase 1 and Phase 2.
Skipped in --videos-only mode (frames already human-approved).
NON-BLOCKING at pipeline level: any exception → frame passes through unchanged.
"""

import os
import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
CANONICAL_PASS_THRESHOLD = 0.65     # Overall: above this → PASS to Kling
CANONICAL_FLAG_THRESHOLD = 0.45     # Between flag/regen: borderline, proceed with annotation
CANONICAL_REGEN_THRESHOLD = 0.45    # Below this → auto-regen with diagnostic
DIMENSION_WARN_THRESHOLD  = 0.50    # Per-dimension: below this → included in diagnostic
MAX_GATE_REGENS           = 2       # Max regens per shot (separate budget from Wire A)

# Weight profile — character shots weight identity higher; empty shots weight location/mood
_WEIGHTS_WITH_CHARS    = {"location": 0.25, "identity": 0.40, "blocking": 0.20, "mood": 0.15}
_WEIGHTS_WITHOUT_CHARS = {"location": 0.40, "identity": 0.00, "blocking": 0.30, "mood": 0.30}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CanonicalScore:
    location_match:     float = 0.0
    character_identity: float = 0.0
    blocking_accuracy:  float = 0.0
    mood_lighting:      float = 0.0
    overall:            float = 0.0
    verdict:            str   = "UNKNOWN"   # PASS / FLAG / REGEN
    diagnostics:        list  = field(default_factory=list)
    regen_hint:         str   = ""
    backend_used:       str   = "unknown"


@dataclass
class GateResult:
    shot_id:                str
    attempt:                int
    score:                  CanonicalScore
    frame_path:             str
    passed:                 bool
    regen_prompt_injection: str = ""   # Prepended to next gen_frame() attempt


# ── Helper: strip FAL-confusing location proper nouns ─────────────────────────

def _safe_location_text(text: str) -> str:
    """
    Replace proper-noun location names with generic descriptors so Gemini
    doesn't conflate the room label with the visual question being asked.
    E.g. 'HARGROVE ESTATE' → 'the estate interior'.
    """
    import re
    text = re.sub(r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b', lambda m: m.group(0).title(), text)
    return text


# ── Main gate class ───────────────────────────────────────────────────────────

class PreVideoGate:
    """
    Holistic frame validator.
    Call gate() after gen_frame() / judge_frame(), before gen_scene_multishot().

    Usage in run_scene():
        _pvg = PreVideoGate()
        _pvg.reset_scene(scene_id)
        for shot in mshots:
            frame = all_frames.get(shot["shot_id"])
            if not frame: continue
            result = _pvg.gate(frame, shot, cast)
            if result.regen_prompt_injection:
                shot["_pvg_diagnostic"] = result.regen_prompt_injection
                new_frame, new_score = gen_frame(shot, ...)
                if new_frame:
                    all_frames[shot["shot_id"]] = new_frame
    """

    def __init__(self):
        self._google_api_key = os.environ.get("GOOGLE_API_KEY", "")
        self._available      = bool(self._google_api_key)
        self._regen_counts: dict[str, int] = {}

        if not self._available:
            logger.info(
                "[PRE-VIDEO-GATE] GOOGLE_API_KEY not set — gate passes all frames "
                "(set key to enable holistic scoring)"
            )

    # ── Budget management ─────────────────────────────────────────────────────

    def reset_scene(self, scene_id: str):
        """Clear regen budgets for a scene. Call once at the start of run_scene()."""
        prefix = str(scene_id)[:3]
        for k in list(self._regen_counts.keys()):
            if k.startswith(prefix):
                del self._regen_counts[k]

    def _budget_ok(self, shot_id: str) -> bool:
        return self._regen_counts.get(shot_id, 0) < MAX_GATE_REGENS

    def _consume_budget(self, shot_id: str):
        self._regen_counts[shot_id] = self._regen_counts.get(shot_id, 0) + 1

    # ── Image encoding ────────────────────────────────────────────────────────

    def _encode_image(self, image_path: str) -> Optional[str]:
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"[PRE-VIDEO-GATE] Cannot encode {image_path}: {e}")
            return None

    # ── Evaluation prompt builder ─────────────────────────────────────────────

    def _build_evaluation_prompt(self, shot: dict, cast_map: dict) -> str:
        """
        Build the Gemini evaluation prompt from the canonical shot specification.
        This is the 'ground truth' description of what the frame SHOULD show.
        """
        sid         = shot.get("shot_id", "unknown")
        nano        = (shot.get("nano_prompt") or "")[:350]
        beat_action = (shot.get("_beat_action") or shot.get("beat_action") or "")[:120]
        room_dna    = (shot.get("_room_dna") or "")[:200]
        lighting    = (shot.get("_lighting_rig") or "")[:100]
        characters  = shot.get("characters") or []
        shot_type   = shot.get("shot_type") or "medium"
        location    = _safe_location_text(
            shot.get("location") or shot.get("_scene_room") or "interior"
        )
        frame_desc  = (shot.get("_frame_description") or "")[:150]

        # Build character appearance descriptions from cast_map
        char_blocks = []
        for char_name in characters[:3]:
            cdata      = cast_map.get(char_name) or cast_map.get(char_name.upper()) or {}
            appearance = (
                cdata.get("amplified_appearance")
                or cdata.get("appearance")
                or cdata.get("description")
                or ""
            )[:180]
            if appearance:
                char_blocks.append(f"  - {char_name}: {appearance}")

        char_section = (
            "\n".join(char_blocks)
            if char_blocks
            else "  (No specific characters required in this shot)"
        )

        # Framing expectation derived from shot type
        framing_guide = {
            "establishing":  "Full room geography visible, empty or characters small in frame.",
            "wide":          "Wide geography, characters at roughly 1/3 frame height.",
            "medium":        "Character(s) waist-up, room context visible as background.",
            "medium_close":  "Head and shoulders fill frame, background soft/secondary.",
            "close_up":      "Face fills 60-80% of frame, background heavily blurred.",
            "ots_a":         "Listener shoulder FRAME-LEFT foreground out-of-focus, speaker FRAME-RIGHT facing camera.",
            "ots_b":         "Listener shoulder FRAME-RIGHT foreground out-of-focus, speaker FRAME-LEFT facing camera.",
            "two_shot":      "Two characters facing each other, one left one right of frame center.",
            "insert":        "Extreme close-up of object/prop, no full character visible.",
        }.get(shot_type.lower(), "Standard cinematic framing for this shot type.")

        prompt = f"""You are a film quality-control supervisor evaluating whether a generated movie frame matches its canonical shot specification.

═══ CANONICAL SHOT SPECIFICATION ═══
Shot ID:    {sid}
Shot Type:  {shot_type}
Location:   {location}
Beat Action: {beat_action}
Frame Description: {frame_desc}
Room Architecture: {room_dna}
Lighting: {lighting}
Full Prompt (what was requested): {nano}

Expected Characters:
{char_section}

Expected Framing: {framing_guide}

═══ YOUR TASK ═══
Look at the attached frame and score it on exactly these 4 dimensions.
Return ONLY valid JSON — no markdown, no prose before or after.

{{
  "location_match":     <0.0–1.0: Does the frame show the correct location type and architecture?>,
  "character_identity": <0.0–1.0: Are the correct characters present with correct appearance? Score 1.0 if no characters required.>,
  "blocking_accuracy":  <0.0–1.0: Is the shot framed correctly for the shot type? Are characters in the right positions?>,
  "mood_lighting":      <0.0–1.0: Does the lighting, colour, and atmosphere match the beat mood?>,
  "worst_failure":      "<one sentence: the single most wrong thing in this frame, or 'none' if all good>",
  "regen_hint":         "<one actionable sentence to fix the worst failure, or '' if all good>"
}}

Scoring rules:
- 1.0 = perfect match to specification
- 0.8 = mostly correct with minor deviation
- 0.5 = partially correct but significant deviation
- 0.2 = clearly wrong but some overlap
- 0.0 = completely wrong
- For character_identity: if no characters are listed above, always score 1.0
- For blocking_accuracy: score based on correct framing for the shot type listed above
- Be strict on location_match — wrong room architecture is a hard failure"""

        return prompt

    # ── Gemini Vision scoring ─────────────────────────────────────────────────

    def _score_via_gemini(
        self, frame_path: str, shot: dict, cast_map: dict
    ) -> Optional[CanonicalScore]:
        """Score frame vs canonical spec via Gemini 2.0 Flash vision."""
        import requests

        img_b64 = self._encode_image(frame_path)
        if not img_b64:
            return None

        eval_prompt = self._build_evaluation_prompt(shot, cast_map)

        payload = {
            "contents": [{
                "parts": [
                    {"text": eval_prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 300,
                "responseMimeType": "application/json",
            },
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={self._google_api_key}"
        )

        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Strip any accidental markdown fences
            if "```" in raw_text:
                parts = raw_text.split("```")
                raw_text = parts[1] if len(parts) > 1 else raw_text
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            scores = json.loads(raw_text.strip())

            loc   = float(scores.get("location_match",     0.5))
            iden  = float(scores.get("character_identity", 1.0))
            block = float(scores.get("blocking_accuracy",  0.5))
            mood  = float(scores.get("mood_lighting",      0.5))

            has_chars = bool(shot.get("characters"))
            w = _WEIGHTS_WITH_CHARS if has_chars else _WEIGHTS_WITHOUT_CHARS
            overall = (
                loc   * w["location"]  +
                iden  * w["identity"]  +
                block * w["blocking"]  +
                mood  * w["mood"]
            )

            worst   = scores.get("worst_failure", "")
            hint    = scores.get("regen_hint", "")

            diagnostics = []
            if loc   < DIMENSION_WARN_THRESHOLD: diagnostics.append(f"LOCATION {loc:.2f}  — wrong architecture/room")
            if iden  < DIMENSION_WARN_THRESHOLD: diagnostics.append(f"IDENTITY {iden:.2f} — character appearance wrong")
            if block < DIMENSION_WARN_THRESHOLD: diagnostics.append(f"BLOCKING {block:.2f} — wrong framing for {shot.get('shot_type','?')}")
            if mood  < DIMENSION_WARN_THRESHOLD: diagnostics.append(f"MOOD     {mood:.2f} — wrong lighting/atmosphere")

            if overall >= CANONICAL_PASS_THRESHOLD:
                verdict = "PASS"
            elif overall >= CANONICAL_FLAG_THRESHOLD:
                verdict = "FLAG"
            else:
                verdict = "REGEN"

            return CanonicalScore(
                location_match=loc,
                character_identity=iden,
                blocking_accuracy=block,
                mood_lighting=mood,
                overall=overall,
                verdict=verdict,
                diagnostics=diagnostics,
                regen_hint=hint or worst,
                backend_used="gemini-2.5-flash",
            )

        except Exception as e:
            logger.warning(f"[PRE-VIDEO-GATE] Gemini call failed: {e}")
            return None

    # ── Heuristic fallback ────────────────────────────────────────────────────

    def _heuristic_pass(self) -> CanonicalScore:
        """
        Used when Gemini is unavailable.
        Conservative PASS — don't block without actual vision scoring.
        Annotated so the user knows visual inspection was skipped.
        """
        return CanonicalScore(
            location_match=0.75, character_identity=0.75,
            blocking_accuracy=0.75, mood_lighting=0.75,
            overall=0.75, verdict="PASS",
            diagnostics=["[HEURISTIC] Gemini unavailable — passed without visual inspection"],
            regen_hint="", backend_used="heuristic",
        )

    # ── Regen injection builder ───────────────────────────────────────────────

    def _build_regen_injection(self, score: CanonicalScore, shot: dict) -> str:
        """
        Build the diagnostic string that gets injected into the next gen_frame() call.
        gen_frame() will prepend this as a [CORRECTION REQUIRED] block so FAL reads
        it in the highest-attention zone (first ~200 chars).
        """
        parts = []

        if score.location_match < DIMENSION_WARN_THRESHOLD:
            room_dna = (shot.get("_room_dna") or "")[:120]
            location = shot.get("location") or shot.get("_scene_room") or "the correct location"
            parts.append(
                f"LOCATION WRONG in previous attempt. MUST show: {_safe_location_text(location)}. "
                + (f"Architecture: {room_dna}." if room_dna else "")
            )

        if score.character_identity < DIMENSION_WARN_THRESHOLD:
            chars = shot.get("characters") or []
            parts.append(
                f"CHARACTER APPEARANCE WRONG. Focus: {', '.join(chars)}. "
                "Match the character reference image exactly — face, build, clothing."
            )

        if score.blocking_accuracy < DIMENSION_WARN_THRESHOLD:
            shot_type = shot.get("shot_type") or "medium"
            parts.append(
                f"FRAMING WRONG for {shot_type}. "
                f"{score.regen_hint or 'Correct the shot composition for this shot type.'}"
            )

        if score.mood_lighting < DIMENSION_WARN_THRESHOLD:
            beat_action = (shot.get("_beat_action") or "")[:80]
            parts.append(
                f"LIGHTING/MOOD WRONG. "
                + (f"Beat atmosphere: {beat_action}. " if beat_action else "")
                + (f"{score.regen_hint}" if score.regen_hint else "Match the scene's lighting rig.")
            )

        # If no specific dimension failed but overall is low, use the general hint
        if not parts and score.regen_hint:
            parts.append(f"QUALITY ISSUE: {score.regen_hint}")

        return " | ".join(parts)

    # ── Public gate interface ─────────────────────────────────────────────────

    def gate(self, frame_path: str, shot: dict, cast_map: dict) -> GateResult:
        """
        Score a generated first frame against its canonical specification.

        Args:
            frame_path: Path to the generated .jpg frame on disk
            shot:       Shot dict from shot_plan (must have shot_id, nano_prompt, etc.)
            cast_map:   Character appearance data (name → {appearance, ...})

        Returns:
            GateResult where:
              .passed = True if frame can proceed to Kling video generation
              .regen_prompt_injection = non-empty string if caller should regen the frame
                (inject this into shot["_pvg_diagnostic"] before calling gen_frame again)
        """
        sid     = shot.get("shot_id", "unknown")
        attempt = self._regen_counts.get(sid, 0) + 1

        # Skip gate for B-roll / establishing shots with no characters and no complex spec
        # These are low-risk and don't justify the Gemini cost per frame
        shot_type   = (shot.get("shot_type") or "").lower()
        has_chars   = bool(shot.get("characters"))
        is_broll    = shot.get("is_broll") or shot.get("_broll") or (shot_type == "insert")
        if is_broll and not has_chars:
            return GateResult(
                shot_id=sid, attempt=attempt,
                score=CanonicalScore(overall=0.80, verdict="PASS",
                                     backend_used="skipped-broll"),
                frame_path=frame_path, passed=True,
            )

        # Score the frame
        score: CanonicalScore
        if self._available and frame_path and Path(frame_path).exists():
            result = self._score_via_gemini(frame_path, shot, cast_map)
            score  = result if result is not None else self._heuristic_pass()
        else:
            score = self._heuristic_pass()

        # Emit concise log line
        v_icon = {"PASS": "✅", "FLAG": "⚠️", "REGEN": "❌"}.get(score.verdict, "?")
        print(
            f"  [PRE-VIDEO-GATE] {v_icon} {sid} "
            f"overall={score.overall:.2f} "
            f"loc={score.location_match:.2f} "
            f"id={score.character_identity:.2f} "
            f"block={score.blocking_accuracy:.2f} "
            f"mood={score.mood_lighting:.2f} "
            f"[{score.backend_used}]"
        )
        for d in score.diagnostics:
            print(f"    [PRE-VIDEO-GATE]   {d}")

        # Determine whether to regen
        needs_regen = (score.verdict == "REGEN") and self._budget_ok(sid)

        if needs_regen:
            self._consume_budget(sid)
            regen_injection = self._build_regen_injection(score, shot)
            used = self._regen_counts[sid]
            print(
                f"    [PRE-VIDEO-GATE] → REGEN #{used}/{MAX_GATE_REGENS}: "
                f"{regen_injection[:120]}{'...' if len(regen_injection) > 120 else ''}"
            )
        elif score.verdict == "REGEN" and not self._budget_ok(sid):
            # Budget exhausted — flag but don't regen
            used = self._regen_counts.get(sid, MAX_GATE_REGENS)
            print(
                f"    [PRE-VIDEO-GATE] → budget exhausted ({used}/{MAX_GATE_REGENS}) "
                f"— flagging {sid} for review, proceeding to video"
            )
            shot["_pvg_status"]     = "GATE_FAIL_BUDGET_EXHAUSTED"
            shot["_pvg_score"]      = round(score.overall, 3)
            shot["_approval_status"] = "REGEN_SUGGESTED"
            regen_injection = ""
        else:
            regen_injection = ""

        # Annotate shot with gate result (persisted to shot_plan on next UI write)
        shot["_pvg_score"]   = round(score.overall, 3)
        shot["_pvg_verdict"] = score.verdict
        shot["_pvg_dims"]    = {
            "loc":   round(score.location_match,     3),
            "id":    round(score.character_identity, 3),
            "block": round(score.blocking_accuracy,  3),
            "mood":  round(score.mood_lighting,      3),
        }

        # FLAG: borderline — proceed to video but mark for operator review
        if score.verdict == "FLAG":
            shot["_pvg_status"]     = "GATE_FLAG_BORDERLINE"
            shot["_approval_status"] = "REGEN_SUGGESTED"

        passed = score.verdict in ("PASS", "FLAG") and not needs_regen

        return GateResult(
            shot_id=sid,
            attempt=attempt,
            score=score,
            frame_path=frame_path,
            passed=passed or not needs_regen,   # non-regen always proceeds
            regen_prompt_injection=regen_injection,
        )


# ── POST-VIDEO GATE ────────────────────────────────────────────────────────────
# Runs AFTER Kling video generation (AutoRevisionJudge).
# Complements the pre-video frame gate — this catches problems that only
# manifest in the video: wrong action, camera drift, identity inconsistency.
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class VideoGateResult:
    shot_id:     str
    video_path:  str
    verdict:     str   = "WARN"     # APPROVE / WARN / REJECT
    overall:     float = 0.0
    regen_instruction: str = ""
    hard_rejects: list = field(default_factory=list)
    dimensions:   dict = field(default_factory=dict)
    backend:      str  = "unknown"
    analysis_ms:  int  = 0


class PostVideoGate:
    """
    Video quality gate — runs AFTER Kling generation.

    Uses AutoRevisionJudge (Gemini Files API) to analyze the generated video
    against the shot_plan specification on 8 cinematic dimensions.

    Called from atlas_universal_runner.py gen_scene_multishot(), after each
    video is downloaded and BEFORE it is written to shot_plan video_url.

    Derived from Scene 002 analysis (2026-03-25):
      - story_beat_accuracy avg = 0.171  ← #1 failure dimension
      - camera_work avg         = 0.257  ← #2 failure dimension
      - identity_consistency    = 0.943  ← strength to preserve
      - cinematic_tone          = 0.857  ← strength to preserve

    Usage in gen_scene_multishot():
        _pvg_post = PostVideoGate()
        for shot in scene_shots:
            video_path = download_video(shot["video_url"])
            result = _pvg_post.judge(video_path, shot, cast_map, next_shot)
            if result.verdict == "REJECT":
                shot["_approval_status"] = "REGEN_REQUESTED"
                shot["_video_regen_instruction"] = result.regen_instruction
                # Trigger diagnostic regen or flag for human review
            shot["_pvg_video_verdict"] = result.verdict
            shot["_pvg_video_score"]   = result.overall
    """

    # Scene 002-derived thresholds (2026-03-25)
    APPROVE_THRESHOLD = 0.72
    WARN_THRESHOLD    = 0.52
    MAX_REGENS        = 2

    def __init__(self):
        self._judge = None
        self._regen_counts: dict = {}
        try:
            from tools.auto_revision_judge import AutoRevisionJudge
            self._judge = AutoRevisionJudge()
            self._available = self._judge.available
        except ImportError:
            try:
                # Try relative import (when tools/ is on sys.path)
                from auto_revision_judge import AutoRevisionJudge
                self._judge = AutoRevisionJudge()
                self._available = self._judge.available
            except ImportError:
                self._available = False
                logger.warning(
                    "[POST-VIDEO-GATE] auto_revision_judge not importable — "
                    "video quality gating disabled"
                )

    @property
    def available(self) -> bool:
        return self._available and self._judge is not None

    def reset_scene(self, scene_id: str):
        """Clear regen budgets for a scene."""
        prefix = str(scene_id)[:3]
        for k in list(self._regen_counts.keys()):
            if k.startswith(prefix):
                del self._regen_counts[k]

    def _budget_ok(self, shot_id: str) -> bool:
        return self._regen_counts.get(shot_id, 0) < self.MAX_REGENS

    def _consume_budget(self, shot_id: str):
        self._regen_counts[shot_id] = self._regen_counts.get(shot_id, 0) + 1

    def judge(
        self,
        video_path: str,
        shot:       dict,
        cast_map:   dict,
        next_shot:  Optional[dict] = None,
    ) -> VideoGateResult:
        """
        Analyze a generated video and return a verdict.

        Args:
            video_path: Local path to the downloaded MP4.
            shot:       Shot dict from shot_plan.json.
            cast_map:   Project cast_map (character appearances).
            next_shot:  Next shot in sequence (for continuity scoring).

        Returns:
            VideoGateResult. On REJECT, .regen_instruction contains the fix.

        NON-BLOCKING: any exception returns a neutral WARN verdict.
        """
        sid = shot.get("shot_id", "unknown")

        if not self.available:
            return VideoGateResult(
                shot_id=sid,
                video_path=video_path,
                verdict="WARN",
                overall=0.70,
                regen_instruction="",
                backend="unavailable",
            )

        try:
            v = self._judge.judge(video_path, shot, cast_map,
                                  next_shot=next_shot, delete_after=True)

            icon = {"APPROVE": "✅", "WARN": "⚠️", "REJECT": "❌"}.get(v.verdict, "?")
            print(
                f"  [POST-VIDEO-GATE] {icon} {sid} "
                f"overall={v.overall:.2f}  "
                f"beat={v.dimensions.get('story_beat_accuracy', type('', (), {'score': 0})()).score:.2f}  "
                f"cam={v.dimensions.get('camera_work', type('', (), {'score': 0})()).score:.2f}  "
                f"id={v.dimensions.get('identity_consistency', type('', (), {'score': 0})()).score:.2f}  "
                f"[{v.backend}]  {v.analysis_ms}ms"
            )
            if v.hard_rejects:
                print(f"    [POST-VIDEO-GATE] ⛔ Hard rejects: {', '.join(v.hard_rejects)}")
            if v.regen_instruction:
                print(
                    f"    [POST-VIDEO-GATE] Fix: "
                    f"{v.regen_instruction[:140]}{'…' if len(v.regen_instruction) > 140 else ''}"
                )

            return VideoGateResult(
                shot_id=sid,
                video_path=video_path,
                verdict=v.verdict,
                overall=v.overall,
                regen_instruction=v.regen_instruction,
                hard_rejects=v.hard_rejects,
                dimensions={
                    k: {"score": ds.score, "verdict": ds.verdict, "observation": ds.observation}
                    for k, ds in v.dimensions.items()
                },
                backend=v.backend,
                analysis_ms=v.analysis_ms,
            )

        except Exception as e:
            logger.warning(f"[POST-VIDEO-GATE] Error for {sid}: {e}")
            return VideoGateResult(
                shot_id=sid,
                video_path=video_path,
                verdict="WARN",
                overall=0.70,
                regen_instruction="",
                backend="exception",
            )
