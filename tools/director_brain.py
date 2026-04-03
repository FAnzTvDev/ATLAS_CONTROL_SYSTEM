"""
ATLAS Director Brain — V1.0
============================
Pre-production LLM meta-controller that sits ABOVE the runner.
Reads the whole film arc and provides editorial corrections mid-production.

This is Layer 2 of the three intelligence layers:
  Layer 1: Production Intelligence Graph  (production_intelligence.py)
  Layer 2: Director Brain                 (THIS FILE)
  Layer 3: Doctrine Evolution             (doctrine_tracker.py)

WHAT IT DOES:
  1. PRE-PRODUCTION CALL (before any shot is generated for a scene):
     - Reads story_bible scene + previous scene outcomes
     - Reads arc position (which act are we in?)
     - Reads production intelligence for this character/location combo
     - Makes a Claude API call (or falls back to heuristic)
     - Returns structured EditorialGuidance injected into beat context

  2. MID-PRODUCTION ARC ADJUSTMENT:
     - After frame generation, if I-scores are trending low, signals adjustment
     - The ArcAdjustmentSignal is an injectable correction the runner can apply
       to the NEXT shot's prompt compilation

  3. SCENE-CLOSE EVALUATION:
     - After all shots in a scene complete, evaluates the arc health
     - Writes director notes to pipeline_outputs/{project}/director_notes/{scene_id}.json

ARCHITECTURE:
  DirectorBrain.pre_scene_brief(scene_id, bible_scene, history)
    → EditorialGuidance  (injected into shot beat context)

  DirectorBrain.arc_adjustment_signal(shots_so_far, scores_so_far)
    → ArcAdjustmentSignal  (fed into next shot's _arc_carry_directive)

  DirectorBrain.scene_close_evaluation(scene_id, reward_ledger)
    → SceneEvaluation  (written to director_notes/)

USAGE:
    from tools.director_brain import DirectorBrain

    brain = DirectorBrain(project_dir=Path("pipeline_outputs/victorian_shadows_ep1"))

    # Before generating a scene:
    guidance = brain.pre_scene_brief(
        scene_id="003",
        bible_scene=story_bible["scenes"][2],
        prev_scene_summary={"avg_R": 0.82, "avg_I": 0.90, "pacing": "fast"}
    )
    # guidance.shot_recommendations, guidance.tension_level, guidance.camera_guidance

    # After each shot, check if arc needs adjustment:
    signal = brain.arc_adjustment_signal(shots_so_far, scores_so_far)
    if signal.apply:
        shot["_arc_carry_directive"] += " " + signal.directive

Non-blocking: all Claude calls wrapped in try/except with heuristic fallback.
Falls back gracefully if ANTHROPIC_API_KEY not set.
"""

import json
import os
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Anthropic client (optional — falls back to heuristic if unavailable) ──
_CLAUDE_AVAILABLE = False
_anthropic_client = None
try:
    import anthropic
    _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if _api_key:
        _anthropic_client = anthropic.Anthropic(api_key=_api_key)
        _CLAUDE_AVAILABLE = True
except Exception as _claude_import_err:
    logger.info(f"[DB] Claude API unavailable: {_claude_import_err} — heuristic mode active")

_DIRECTOR_MODEL = "claude-opus-4-6"  # Highest capability for editorial judgment


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EditorialGuidance:
    """
    Pre-production editorial guidance output from the Director Brain.
    Injected into beat enrichment context before shot generation.
    """
    scene_id: str
    timestamp: str = ""

    # Narrative direction
    tension_level: str = "moderate"           # low / moderate / high / extreme
    pacing_target: str = "andante"            # allegro / andante / moderato / largo
    emotional_arc: str = ""                   # one sentence describing scene arc
    key_moment: str = ""                      # the most important beat in this scene

    # Shot-level recommendations (list of {shot_index, recommendation} dicts)
    shot_recommendations: List[Dict] = field(default_factory=list)

    # Camera guidance
    camera_guidance: str = ""                 # e.g. "lean on close-ups for tension"
    preferred_shot_types: List[str] = field(default_factory=list)
    avoid_shot_types: List[str] = field(default_factory=list)

    # Identity reinforcement flags
    identity_risk_chars: List[str] = field(default_factory=list)  # characters needing extra refs
    use_multi_ref: bool = False

    # Lighting/mood
    mood_note: str = ""                       # e.g. "high contrast, cold shadows"

    # Arc position context
    act_position: str = ""                    # "opening / middle / late / climax"
    arc_momentum: str = "building"            # building / sustaining / releasing / pivoting

    # Source tracking
    source: str = "heuristic"                 # "claude" or "heuristic"
    confidence: float = 0.5

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ArcAdjustmentSignal:
    """
    Mid-production correction signal. Applied to the NEXT shot's arc_carry_directive.
    Triggered when consecutive shots are trending below quality threshold.
    """
    apply: bool = False
    trigger_reason: str = ""             # why adjustment was triggered
    directive: str = ""                  # text to append to _arc_carry_directive
    identity_boost: bool = False         # bump identity reinforcement for next shot
    resolution_bump: str = ""            # "2K" or "" — upgrade next shot's resolution
    tension_injection: str = ""          # text to inject into mood/atmosphere
    confidence: float = 0.5
    source: str = "heuristic"


@dataclass
class SceneEvaluation:
    """Director's post-scene evaluation after all shots complete."""
    scene_id: str
    timestamp: str = ""
    overall_grade: str = "B"             # A / B / C / D / F
    avg_R: float = 0.0
    avg_I: float = 0.0
    arc_health: str = "HEALTHY"          # HEALTHY / SAGGING / BROKEN
    pacing_verdict: str = "ON_TARGET"    # FAST / ON_TARGET / SLOW
    notes: List[str] = field(default_factory=list)
    next_scene_recommendations: List[str] = field(default_factory=list)
    source: str = "heuristic"


# ═══════════════════════════════════════════════════════════════════════════
# DIRECTOR BRAIN
# ═══════════════════════════════════════════════════════════════════════════

class DirectorBrain:
    """
    Pre-production LLM meta-controller. Sits ABOVE the runner.
    Reads the whole film arc and provides editorial guidance before and
    during production. Falls back to heuristic if Claude unavailable.
    """

    def __init__(self, project_dir: Optional[Path] = None, project: str = ""):
        self._project_dir = Path(project_dir) if project_dir else None
        self._project = project
        self._notes_dir: Optional[Path] = None
        if self._project_dir:
            self._notes_dir = self._project_dir / "director_notes"
            self._notes_dir.mkdir(parents=True, exist_ok=True)
        self._scene_history: Dict[str, Dict] = {}  # scene_id → summary of outcomes

    # ── Public API ──────────────────────────────────────────────────────────

    def pre_scene_brief(
        self,
        scene_id: str,
        bible_scene: Dict,
        prev_scene_summary: Optional[Dict] = None,
        production_intel: Optional[Dict] = None,
    ) -> EditorialGuidance:
        """
        Generate pre-production editorial guidance for a scene.
        Called BEFORE any shot is generated.

        Args:
            scene_id: e.g. "003"
            bible_scene: story_bible["scenes"][n] dict
            prev_scene_summary: {"avg_R": 0.82, "avg_I": 0.90, "frozen_count": 0}
            production_intel: from ProductionIntelligence.get_production_summary()

        Returns:
            EditorialGuidance — injected into beat context
        """
        try:
            if _CLAUDE_AVAILABLE:
                guidance = self._call_claude_pre_scene(scene_id, bible_scene,
                                                        prev_scene_summary,
                                                        production_intel)
            else:
                guidance = self._heuristic_pre_scene(scene_id, bible_scene,
                                                      prev_scene_summary)
            self._save_guidance(scene_id, guidance)
            return guidance
        except Exception as e:
            logger.warning(f"[DB] pre_scene_brief failed: {e}")
            return self._heuristic_pre_scene(scene_id, bible_scene, prev_scene_summary)

    def arc_adjustment_signal(
        self,
        shots_so_far: List[Dict],
        scores_so_far: List[Dict],
        threshold: float = 0.60,
    ) -> ArcAdjustmentSignal:
        """
        Mid-production arc check. Called after each shot completes.
        If last N shots are trending below threshold, returns adjustment signal.

        Args:
            shots_so_far: list of shot dicts generated so far
            scores_so_far: list of reward ledger entries so far
            threshold: R-score below which to trigger adjustment

        Returns:
            ArcAdjustmentSignal — applied to next shot if signal.apply is True
        """
        try:
            return self._compute_arc_adjustment(shots_so_far, scores_so_far, threshold)
        except Exception as e:
            logger.warning(f"[DB] arc_adjustment_signal failed: {e}")
            return ArcAdjustmentSignal(apply=False)

    def scene_close_evaluation(
        self,
        scene_id: str,
        reward_ledger: List[Dict],
        bible_scene: Optional[Dict] = None,
    ) -> SceneEvaluation:
        """
        Post-scene director evaluation. Called after all shots in a scene complete.
        Writes evaluation to director_notes/{scene_id}.json.

        Args:
            scene_id: e.g. "003"
            reward_ledger: list of reward entries from runner
            bible_scene: optional story bible scene for context

        Returns:
            SceneEvaluation
        """
        try:
            eval_ = self._evaluate_scene(scene_id, reward_ledger, bible_scene)
            self._save_evaluation(scene_id, eval_)
            # Store for cross-scene arc tracking
            self._scene_history[scene_id] = {
                "avg_R": eval_.avg_R,
                "avg_I": eval_.avg_I,
                "arc_health": eval_.arc_health,
                "grade": eval_.overall_grade,
            }
            return eval_
        except Exception as e:
            logger.warning(f"[DB] scene_close_evaluation failed: {e}")
            return SceneEvaluation(scene_id=scene_id,
                                   timestamp=datetime.utcnow().isoformat())

    def get_arc_health_summary(self) -> Dict:
        """Return arc health across all scenes seen so far."""
        if not self._scene_history:
            return {"status": "NO_DATA", "scenes_evaluated": 0}
        grades = [s["grade"] for s in self._scene_history.values()]
        avg_R = sum(s["avg_R"] for s in self._scene_history.values()) / len(self._scene_history)
        healthy = sum(1 for s in self._scene_history.values() if s["arc_health"] == "HEALTHY")
        return {
            "scenes_evaluated": len(self._scene_history),
            "avg_R_across_scenes": round(avg_R, 3),
            "healthy_scenes": healthy,
            "arc_health": "HEALTHY" if healthy == len(self._scene_history) else
                          "PARTIAL" if healthy > len(self._scene_history) * 0.6 else "BROKEN",
            "grade_distribution": {g: grades.count(g) for g in "ABCDF"},
        }

    # ── Claude API Call ─────────────────────────────────────────────────────

    def _call_claude_pre_scene(
        self,
        scene_id: str,
        bible_scene: Dict,
        prev_scene_summary: Optional[Dict],
        production_intel: Optional[Dict],
    ) -> EditorialGuidance:
        """Call Claude API to generate pre-production editorial guidance."""

        # Build a compact bible scene summary (avoid token waste)
        location  = bible_scene.get("location", "Unknown location")
        characters = bible_scene.get("characters", [])
        beats_raw  = bible_scene.get("beats", [])
        beats_text = "\n".join(f"  Beat {i+1}: {b}" for i, b in enumerate(beats_raw[:6]))
        atmosphere = bible_scene.get("atmosphere", "")
        objective  = bible_scene.get("scene_objective", bible_scene.get("description", ""))

        prev_text = ""
        if prev_scene_summary:
            avg_R = prev_scene_summary.get("avg_R", 0)
            avg_I = prev_scene_summary.get("avg_I", 0)
            prev_text = f"""
PREVIOUS SCENE PERFORMANCE:
  Average reward score (R): {avg_R:.2f}
  Average identity score (I): {avg_I:.2f}
  Frozen videos: {prev_scene_summary.get('frozen_count', 0)}
  Notes: {prev_scene_summary.get('notes', 'none')}
"""

        intel_text = ""
        if production_intel:
            intel_text = f"""
PRODUCTION INTELLIGENCE:
  Total shots generated this production: {production_intel.get('total_shots', 0)}
  Overall pass rate: {production_intel.get('pass_rate', 0):.0%}
  Characters with high drift: {[r['character_name'] for r in production_intel.get('character_drift', []) if r.get('drifts', 0) > 0]}
"""

        prompt = f"""You are the Director Brain for ATLAS, an AI film production system.
Your job: provide concise, actionable pre-production editorial guidance for Scene {scene_id}.

SCENE DATA:
  Location: {location}
  Characters: {', '.join(characters)}
  Scene objective: {objective}
  Atmosphere: {atmosphere}
  Beats:
{beats_text}
{prev_text}{intel_text}
ATLAS generates shots using Kling v3/pro video AI. Each shot is ~10 seconds.
Shot types available: wide, medium, close_up, ots_a, ots_b, two_shot, establishing, insert.
Arc positions: ESTABLISH (opening), ESCALATE (middle), PIVOT (turning), RESOLVE (close).

OUTPUT FORMAT (JSON only, no markdown):
{{
  "tension_level": "low|moderate|high|extreme",
  "pacing_target": "allegro|andante|moderato|largo",
  "emotional_arc": "<one sentence describing arc from first to last beat>",
  "key_moment": "<which beat is the scene's turning point>",
  "camera_guidance": "<concise camera/lens recommendation>",
  "preferred_shot_types": ["<shot_type1>", "<shot_type2>"],
  "avoid_shot_types": ["<shot_type>"],
  "mood_note": "<lighting/color temperature suggestion>",
  "arc_position": "<opening|middle|late|climax>",
  "arc_momentum": "<building|sustaining|releasing|pivoting>",
  "identity_risk_chars": ["<char_name if needs extra ref reinforcement>"],
  "shot_recommendations": [
    {{"beat_index": 0, "recommendation": "<specific shot guidance for beat 0>"}},
    {{"beat_index": 1, "recommendation": "<specific shot guidance for beat 1>"}}
  ],
  "confidence": 0.85
}}

Be brief and specific. No explanations outside the JSON."""

        response = _anthropic_client.messages.create(
            model=_DIRECTOR_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Parse JSON response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response if wrapped in text
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}

        return EditorialGuidance(
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            tension_level=data.get("tension_level", "moderate"),
            pacing_target=data.get("pacing_target", "andante"),
            emotional_arc=data.get("emotional_arc", ""),
            key_moment=data.get("key_moment", ""),
            shot_recommendations=data.get("shot_recommendations", []),
            camera_guidance=data.get("camera_guidance", ""),
            preferred_shot_types=data.get("preferred_shot_types", []),
            avoid_shot_types=data.get("avoid_shot_types", []),
            identity_risk_chars=data.get("identity_risk_chars", []),
            use_multi_ref=bool(data.get("identity_risk_chars")),
            mood_note=data.get("mood_note", ""),
            act_position=data.get("arc_position", ""),
            arc_momentum=data.get("arc_momentum", "building"),
            source="claude",
            confidence=float(data.get("confidence", 0.8)),
        )

    # ── Heuristic Fallback ──────────────────────────────────────────────────

    def _heuristic_pre_scene(
        self,
        scene_id: str,
        bible_scene: Dict,
        prev_scene_summary: Optional[Dict],
    ) -> EditorialGuidance:
        """
        Heuristic pre-production guidance when Claude is unavailable.
        Derived from story bible atmosphere and character count.
        """
        chars     = bible_scene.get("characters", [])
        atmosphere = (bible_scene.get("atmosphere", "") or "").lower()
        beats_raw  = bible_scene.get("beats", [])
        scene_num  = int(scene_id) if scene_id.isdigit() else 1

        # Tension from atmosphere keywords
        if any(w in atmosphere for w in ["dread", "fear", "horror", "confrontation", "rage"]):
            tension = "high"
            mood = "High contrast, deep shadows, desaturated cool tones"
        elif any(w in atmosphere for w in ["tension", "conflict", "uneasy", "suspicious"]):
            tension = "moderate"
            mood = "Dutch angles, tight framing"
        elif any(w in atmosphere for w in ["grief", "loss", "sorrow", "melancholy"]):
            tension = "low"
            mood = "Soft focus, muted colors, wide isolation shots"
        else:
            tension = "moderate"
            mood = "Warm lighting, balanced framing"

        # Camera guidance from character count
        if len(chars) >= 2:
            camera = "Use OTS pairs for dialogue. Vary between wide two-shot and close-ups."
            preferred = ["ots_a", "ots_b", "two_shot", "close_up"]
        elif len(chars) == 1:
            camera = "Solo scene: emphasize isolation with wide + close-up contrast."
            preferred = ["wide", "medium", "close_up"]
        else:
            camera = "Environment scene: layer depth with wide + insert shots."
            preferred = ["wide", "establishing", "insert"]

        # Arc position heuristic from scene number
        total_scenes = 6  # default assumption
        position_ratio = scene_num / max(total_scenes, 1)
        if position_ratio <= 0.25:
            act_pos, momentum = "opening", "building"
        elif position_ratio <= 0.6:
            act_pos, momentum = "middle", "sustaining"
        elif position_ratio <= 0.85:
            act_pos, momentum = "late", "escalating"
        else:
            act_pos, momentum = "climax", "releasing"

        # Prev scene feedback
        identity_risk = []
        if prev_scene_summary and prev_scene_summary.get("avg_I", 1.0) < 0.70:
            identity_risk = chars  # all chars get extra refs if prev scene had drift

        shot_recs = []
        for i, beat in enumerate(beats_raw[:4]):
            beat_str = str(beat) if not isinstance(beat, str) else beat
            if "dialogue" in beat_str.lower() or "says" in beat_str.lower():
                shot_recs.append({"beat_index": i, "recommendation": "Use OTS pair, alternate A/B angles"})
            elif "enters" in beat_str.lower() or "walks" in beat_str.lower():
                shot_recs.append({"beat_index": i, "recommendation": "Wide establishing shot, then cut to medium"})
            elif "looks" in beat_str.lower() or "sees" in beat_str.lower():
                shot_recs.append({"beat_index": i, "recommendation": "Close-up reaction, eye-line match to object"})

        return EditorialGuidance(
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            tension_level=tension,
            pacing_target="moderato" if tension == "moderate" else "andante" if tension == "low" else "allegro",
            emotional_arc=f"Scene builds from {tension} tension, {atmosphere[:50] if atmosphere else 'neutral atmosphere'}",
            key_moment=f"Beat {len(beats_raw) // 2 + 1} of {len(beats_raw)}" if beats_raw else "Midpoint",
            shot_recommendations=shot_recs,
            camera_guidance=camera,
            preferred_shot_types=preferred,
            avoid_shot_types=[],
            identity_risk_chars=identity_risk,
            use_multi_ref=bool(identity_risk),
            mood_note=mood,
            act_position=act_pos,
            arc_momentum=momentum,
            source="heuristic",
            confidence=0.4,
        )

    # ── Arc Adjustment Signal ───────────────────────────────────────────────

    def _compute_arc_adjustment(
        self,
        shots_so_far: List[Dict],
        scores_so_far: List[Dict],
        threshold: float,
    ) -> ArcAdjustmentSignal:
        """
        Compute mid-production arc adjustment signal.
        Triggers if last 2+ shots are below threshold OR I-scores are dropping.
        """
        if len(scores_so_far) < 2:
            return ArcAdjustmentSignal(apply=False)

        recent = scores_so_far[-3:]  # last 3 shots
        avg_R = sum(e.get("R", 0) for e in recent) / len(recent)
        avg_I = sum(e.get("I", 0) for e in recent) / len(recent)

        # Check for frozen videos (V_score very low)
        frozen = sum(1 for e in recent if e.get("V", 1.0) <= 0.3)

        directives = []
        identity_boost = False
        res_bump = ""
        reason_parts = []

        if avg_R < threshold:
            reason_parts.append(f"avg_R={avg_R:.2f} below threshold={threshold:.2f}")

        if avg_I < 0.65:
            directives.append("IDENTITY ANCHOR: Reference character's exact appearance explicitly. Face lock priority.")
            identity_boost = True
            res_bump = "2K"
            reason_parts.append(f"identity drift detected (avg_I={avg_I:.2f})")

        if frozen >= 2:
            directives.append("MOTION INJECTION: Character must have explicit physical action — gestures, breathing, weight shift.")
            reason_parts.append(f"{frozen}/3 recent shots frozen")

        # Check if R is declining (not just low)
        if len(scores_so_far) >= 3:
            r_values = [e.get("R", 0) for e in scores_so_far[-3:]]
            if r_values[0] > r_values[1] > r_values[2]:  # declining trend
                directives.append("ARC RECOVERY: Add emotional specificity — character reaction must be physically visible.")
                reason_parts.append("R-score declining trend")

        if not reason_parts:
            return ArcAdjustmentSignal(apply=False)

        return ArcAdjustmentSignal(
            apply=True,
            trigger_reason=" | ".join(reason_parts),
            directive=" ".join(directives),
            identity_boost=identity_boost,
            resolution_bump=res_bump,
            tension_injection="Heighten physical performance — posture, gaze, grip tension visible.",
            confidence=0.7,
            source="heuristic",
        )

    # ── Scene Evaluation ───────────────────────────────────────────────────

    def _evaluate_scene(
        self,
        scene_id: str,
        reward_ledger: List[Dict],
        bible_scene: Optional[Dict],
    ) -> SceneEvaluation:
        """Evaluate completed scene based on reward ledger."""
        if not reward_ledger:
            return SceneEvaluation(scene_id=scene_id,
                                   timestamp=datetime.utcnow().isoformat(),
                                   overall_grade="?",
                                   notes=["No reward ledger data"])

        avg_R    = sum(e.get("R", 0) for e in reward_ledger) / len(reward_ledger)
        avg_I    = sum(e.get("I", 0) for e in reward_ledger) / len(reward_ledger)
        pass_rate = sum(1 for e in reward_ledger if e.get("verdict") == "PASS") / len(reward_ledger)
        frozen   = sum(1 for e in reward_ledger if e.get("V", 1) <= 0.3)

        # Grade
        if avg_R >= 0.85 and pass_rate >= 0.90:
            grade = "A"
        elif avg_R >= 0.75 and pass_rate >= 0.75:
            grade = "B"
        elif avg_R >= 0.60 and pass_rate >= 0.50:
            grade = "C"
        elif avg_R >= 0.45:
            grade = "D"
        else:
            grade = "F"

        # Arc health
        r_values = [e.get("R", 0) for e in reward_ledger]
        declining = len(r_values) >= 3 and r_values[-1] < r_values[0] - 0.2
        arc_health = "BROKEN" if frozen >= len(reward_ledger) * 0.4 else \
                     "SAGGING" if declining or avg_R < 0.55 else "HEALTHY"

        # Pacing (from V-scores and shot durations)
        avg_V = sum(e.get("V", 0) for e in reward_ledger) / len(reward_ledger)
        pacing = "FAST" if avg_V >= 0.80 else "SLOW" if avg_V <= 0.30 else "ON_TARGET"

        notes = []
        next_recs = []

        if avg_I < 0.70:
            notes.append(f"Identity drift in this scene (avg_I={avg_I:.2f}). Increase ref injection for next scene.")
            next_recs.append("Boost identity reinforcement: use [CHARACTER:] blocks on 100% of shots")
        if frozen > 0:
            notes.append(f"{frozen} frozen video(s) detected. Check motion choreography directives.")
            next_recs.append("Add explicit physical motion verbs to all Kling prompts")
        if pass_rate < 0.70:
            notes.append(f"Pass rate {pass_rate:.0%} — below 70%. Consider slower pacing with longer takes.")
        if arc_health == "SAGGING":
            notes.append("Arc is sagging mid-scene. Next scene should open with stronger establishing energy.")
            next_recs.append("Open next scene with wide establishing + immediate tension injection")

        # Cross-scene arc intelligence
        prev_scenes = list(self._scene_history.values())
        if prev_scenes:
            prev_avg_R = sum(s["avg_R"] for s in prev_scenes) / len(prev_scenes)
            if avg_R > prev_avg_R + 0.1:
                notes.append(f"Quality improving: this scene R={avg_R:.2f} vs series avg {prev_avg_R:.2f}")
            elif avg_R < prev_avg_R - 0.15:
                notes.append(f"Quality drop: this scene R={avg_R:.2f} vs series avg {prev_avg_R:.2f}. Diagnose.")

        return SceneEvaluation(
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            overall_grade=grade,
            avg_R=round(avg_R, 3),
            avg_I=round(avg_I, 3),
            arc_health=arc_health,
            pacing_verdict=pacing,
            notes=notes,
            next_scene_recommendations=next_recs,
            source="heuristic",
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def _save_guidance(self, scene_id: str, guidance: EditorialGuidance):
        if not self._notes_dir:
            return
        try:
            path = self._notes_dir / f"{scene_id}_pre_brief.json"
            path.write_text(json.dumps(guidance.to_dict(), indent=2))
        except Exception as e:
            logger.warning(f"[DB] Failed to save guidance: {e}")

    def _save_evaluation(self, scene_id: str, eval_: SceneEvaluation):
        if not self._notes_dir:
            return
        try:
            path = self._notes_dir / f"{scene_id}_evaluation.json"
            path.write_text(json.dumps(asdict(eval_), indent=2))
            print(f"  [DIRECTOR BRAIN] Scene {scene_id} evaluation: {eval_.overall_grade} "
                  f"(R={eval_.avg_R:.2f} I={eval_.avg_I:.2f} arc={eval_.arc_health})")
        except Exception as e:
            logger.warning(f"[DB] Failed to save evaluation: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════

_GLOBAL_BRAIN: Optional[DirectorBrain] = None

def get_director_brain(project_dir: Optional[Path] = None,
                        project: str = "") -> DirectorBrain:
    """Get or create the global DirectorBrain instance."""
    global _GLOBAL_BRAIN
    if _GLOBAL_BRAIN is None:
        _GLOBAL_BRAIN = DirectorBrain(project_dir=project_dir, project=project)
    return _GLOBAL_BRAIN


def pre_scene_brief(scene_id: str, bible_scene: Dict,
                     prev_scene_summary: Optional[Dict] = None,
                     project_dir: Optional[Path] = None) -> EditorialGuidance:
    """Module-level convenience — non-blocking."""
    try:
        brain = get_director_brain(project_dir)
        return brain.pre_scene_brief(scene_id, bible_scene, prev_scene_summary)
    except Exception as e:
        logger.warning(f"[DB] pre_scene_brief wrapper: {e}")
        return EditorialGuidance(scene_id=scene_id,
                                  timestamp=datetime.utcnow().isoformat(),
                                  source="fallback")


def arc_adjustment_signal(shots_so_far: List[Dict],
                           scores_so_far: List[Dict]) -> ArcAdjustmentSignal:
    """Module-level convenience — non-blocking."""
    try:
        return get_director_brain().arc_adjustment_signal(shots_so_far, scores_so_far)
    except Exception:
        return ArcAdjustmentSignal(apply=False)


def scene_close_evaluation(scene_id: str,
                             reward_ledger: List[Dict],
                             project_dir: Optional[Path] = None) -> SceneEvaluation:
    """Module-level convenience — non-blocking."""
    try:
        brain = get_director_brain(project_dir)
        return brain.scene_close_evaluation(scene_id, reward_ledger)
    except Exception as e:
        logger.warning(f"[DB] scene_close_evaluation wrapper: {e}")
        return SceneEvaluation(scene_id=scene_id,
                                timestamp=datetime.utcnow().isoformat())


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    print(f"Director Brain — Claude available: {_CLAUDE_AVAILABLE}")
    print(f"Model: {_DIRECTOR_MODEL}")

    if len(sys.argv) >= 3:
        project_path = Path(sys.argv[1])
        scene_id = sys.argv[2]
        # Try to load story bible
        bible_path = project_path / "story_bible.json"
        if bible_path.exists():
            bible = json.loads(bible_path.read_text())
            scenes = bible.get("scenes", [])
            scene_num = int(scene_id) - 1
            if 0 <= scene_num < len(scenes):
                brain = DirectorBrain(project_dir=project_path)
                guidance = brain.pre_scene_brief(scene_id, scenes[scene_num])
                print(json.dumps(guidance.to_dict(), indent=2))
            else:
                print(f"Scene {scene_id} not found in bible ({len(scenes)} scenes)")
        else:
            print(f"No story bible at {bible_path}")
    else:
        print("Usage: python3 director_brain.py <project_dir> <scene_id>")
        print("       python3 director_brain.py pipeline_outputs/victorian_shadows_ep1 003")
