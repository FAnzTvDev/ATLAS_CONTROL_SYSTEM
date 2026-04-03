"""
ATLAS V24 — META-DIRECTOR (Prefrontal Cortex / Orchestration Layer)
====================================================================
The autonomous orchestrator that coordinates all V24 systems:
  - ProjectTruth (hippocampus/memory)
  - BasalGangliaEngine (action selection)
  - VisionAnalyst (post-render evaluation)
  - LITE Synthesizer (prompt pipeline)
  - ActorIntentLayer (character psychology)

The Meta-Director is the "consciousness" layer. It:
1. Loads project truth and global context before any render
2. Feeds LITE data to the synthesizer for every shot
3. Evaluates renders via Vision Analyst
4. Records rewards via Basal Ganglia
5. Detects regressions and triggers re-renders
6. Produces a scene-level director's report

Brain mapping:
  - Prefrontal cortex: Planning, sequencing, decision authority
  - Executive function: Coordinates all subsystems
  - Working memory: Holds scene context during render pass

Usage:
  from tools.meta_director import MetaDirector
  director = MetaDirector(project_path)
  report = director.direct_scene(scene_id, shots)
  report = director.direct_full_project()
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# DIRECTOR DECISIONS
# ============================================================================

@dataclass
class DirectorDecision:
    """A decision made by the Meta-Director for a shot or scene."""
    decision_type: str   # "approve", "flag", "regen", "adjust", "skip"
    target: str          # shot_id or scene_id
    reason: str
    confidence: float    # 0.0-1.0
    action: str          # what to do: "proceed", "regenerate", "adjust_prompt", "manual_review"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneDirectorReport:
    """Director's report after evaluating/directing a scene."""
    scene_id: str
    timestamp: str = ""
    status: str = "pending"  # pending, directed, needs_review, approved
    decisions: List[Dict] = field(default_factory=list)
    health_score: float = 0.0
    pacing_target: str = "moderato"
    act_position: str = ""
    shots_approved: int = 0
    shots_flagged: int = 0
    shots_for_regen: int = 0
    narrative_notes: List[str] = field(default_factory=list)
    technical_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectDirectorReport:
    """Full project director's report."""
    project_name: str
    timestamp: str = ""
    total_scenes: int = 0
    scenes_approved: int = 0
    scenes_needs_review: int = 0
    overall_health: float = 0.0
    scene_reports: Dict[str, Dict] = field(default_factory=dict)
    global_notes: List[str] = field(default_factory=list)
    reward_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# META-DIRECTOR ENGINE
# ============================================================================

class MetaDirector:
    """
    The autonomous orchestrator — ATLAS's prefrontal cortex.
    Coordinates all V24 subsystems for intelligent filmmaking.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.project_name = os.path.basename(project_path)
        self.reports_dir = os.path.join(project_path, "reports", "meta_director")
        os.makedirs(self.reports_dir, exist_ok=True)

        # Load project data
        self.cast_map = self._load_json("cast_map.json")
        self.story_bible = self._load_json("story_bible.json")
        self.shot_plan = self._load_json("shot_plan.json")
        self.genre = self.story_bible.get("genre", "gothic_horror")

        # Initialize subsystems (lazy — only when needed)
        self._truth = None
        self._basal_ganglia = None
        self._vision_analyst = None

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self.project_path, filename)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        return {}

    # ── Lazy subsystem initialization ──

    @property
    def truth(self):
        if self._truth is None:
            try:
                from tools.project_truth import ProjectTruth
                truth_path = os.path.join(self.project_path, "ATLAS_PROJECT_TRUTH.json")
                if os.path.exists(truth_path):
                    self._truth = ProjectTruth.load(self.project_path)
                else:
                    from tools.project_truth import generate_project_truth
                    self._truth = generate_project_truth(self.project_path)
            except Exception as e:
                logger.warning(f"ProjectTruth unavailable: {e}")
        return self._truth

    @property
    def basal_ganglia(self):
        if self._basal_ganglia is None:
            try:
                from tools.basal_ganglia_engine import BasalGangliaEngine
                self._basal_ganglia = BasalGangliaEngine(self.project_path)
            except Exception as e:
                logger.warning(f"BasalGangliaEngine unavailable: {e}")
        return self._basal_ganglia

    @property
    def vision_analyst(self):
        if self._vision_analyst is None:
            try:
                from tools.vision_analyst import VisionAnalyst
                self._vision_analyst = VisionAnalyst(self.project_path)
            except Exception as e:
                logger.warning(f"VisionAnalyst unavailable: {e}")
        return self._vision_analyst

    # ────────────────────────────────────────────
    # PRE-RENDER: Prepare scene context
    # ────────────────────────────────────────────

    def prepare_scene_context(self, scene_id: str) -> Dict[str, Any]:
        """
        Build complete scene context before rendering.
        This is the 'working memory' — everything the render pipeline needs.
        """
        context = {
            "scene_id": scene_id,
            "genre": self.genre,
            "project": self.project_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Get LITE data from ProjectTruth
        if self.truth:
            # Build a dummy shot to get scene-level LITE data
            dummy = {"scene_id": scene_id, "shot_id": f"{scene_id}_000A"}
            lite_data = self.truth.get_lite_data_object(dummy)
            context["lite_data"] = lite_data
            context["act_position"] = lite_data.get("act_position", "")
            context["pacing_target"] = lite_data.get("pacing_target", "moderato")
            context["emotional_trajectory"] = lite_data.get("emotional_trajectory", {})
        else:
            context["act_position"] = ""
            context["pacing_target"] = "moderato"

        # Scene from story bible
        scenes = self.story_bible.get("scenes", [])
        for sc in scenes:
            if sc.get("scene_id") == scene_id:
                context["scene_data"] = {
                    "location": sc.get("location", ""),
                    "atmosphere": sc.get("atmosphere", ""),
                    "characters": sc.get("characters_present", []),
                    "beats": len(sc.get("beats", [])),
                }
                break

        return context

    # ────────────────────────────────────────────
    # PRE-RENDER: Shot-level readiness check
    # ────────────────────────────────────────────

    def check_shot_readiness(self, shot: dict, scene_context: Dict) -> DirectorDecision:
        """
        Pre-render check for a single shot. Returns a director decision.
        """
        shot_id = shot.get("shot_id", "unknown")
        issues = []

        # Check nano_prompt exists
        nano = shot.get("nano_prompt_final") or shot.get("nano_prompt_lite") or shot.get("nano_prompt", "")
        if not nano and not shot.get("_should_chain"):
            issues.append("Missing nano_prompt")

        # Check ltx_prompt exists
        ltx = shot.get("ltx_motion_prompt", "")
        if not ltx:
            issues.append("Missing ltx_motion_prompt")

        # Check gold standard
        if shot.get("characters") and "NO morphing" not in ltx:
            issues.append("Missing gold standard negatives in LTX")

        # Check performance markers
        has_chars = len(shot.get("characters", [])) > 0
        if has_chars:
            has_marker = any(m in ltx for m in [
                "character performs:", "character speaks:", "character reacts:"
            ])
            if not has_marker:
                issues.append("Missing performance marker in LTX")

        # Check dialogue injection
        if shot.get("dialogue_text") and "character speaks:" not in ltx:
            issues.append("Dialogue exists but no 'character speaks:' in LTX")

        # Check duration validity
        duration = shot.get("duration", 0)
        if duration not in [4, 6, 8, 10, 12, 14, 16, 18, 20]:
            issues.append(f"Invalid LTX duration: {duration}")

        # V24: Check actor intent populated
        if has_chars and not shot.get("actor_intent"):
            issues.append("No actor intent data (V24 enhancement)")

        if not issues:
            return DirectorDecision(
                decision_type="approve",
                target=shot_id,
                reason="All checks pass",
                confidence=0.95,
                action="proceed",
            )
        elif len(issues) <= 2 and "Missing performance marker" in str(issues):
            return DirectorDecision(
                decision_type="flag",
                target=shot_id,
                reason=f"Minor issues: {'; '.join(issues)}",
                confidence=0.7,
                action="proceed",  # Non-blocking
                metadata={"issues": issues},
            )
        else:
            return DirectorDecision(
                decision_type="flag",
                target=shot_id,
                reason=f"Issues found: {'; '.join(issues)}",
                confidence=0.4,
                action="manual_review",
                metadata={"issues": issues},
            )

    # ────────────────────────────────────────────
    # POST-RENDER: Evaluate and score
    # ────────────────────────────────────────────

    def evaluate_scene_render(self, scene_id: str, shots: List[dict]) -> SceneDirectorReport:
        """
        Post-render evaluation. Uses VisionAnalyst for health scoring
        and BasalGanglia for reward recording.
        """
        scene_context = self.prepare_scene_context(scene_id)
        report = SceneDirectorReport(
            scene_id=scene_id,
            timestamp=datetime.utcnow().isoformat(),
            pacing_target=scene_context.get("pacing_target", "moderato"),
            act_position=scene_context.get("act_position", ""),
        )

        # Pre-render checks on all shots
        for shot in shots:
            decision = self.check_shot_readiness(shot, scene_context)
            report.decisions.append(asdict(decision))
            if decision.decision_type == "approve":
                report.shots_approved += 1
            elif decision.action == "regenerate":
                report.shots_for_regen += 1
            else:
                report.shots_flagged += 1

        # Vision Analyst health check
        if self.vision_analyst:
            health = self.vision_analyst.evaluate_scene(
                scene_id, shots,
                pacing_target=report.pacing_target,
                act_position=report.act_position,
            )
            report.health_score = health.composite_score
            report.technical_notes.extend(health.recommendations)

            # Record rewards via Basal Ganglia
            if self.basal_ganglia and health.composite_score > 0:
                for shot_eval in health.shot_evaluations:
                    if isinstance(shot_eval, dict) and shot_eval.get("scores"):
                        try:
                            from tools.basal_ganglia_engine import CandidateResult
                            # Record as reward memory
                            self.basal_ganglia._record_reward(
                                shot_id=shot_eval["shot_id"],
                                prompt_hash=self.basal_ganglia._hash_prompt(
                                    str(shot_eval.get("vision_data", ""))
                                ),
                                result=None,  # No candidate result for post-eval
                                composite=health.composite_score,
                            )
                        except Exception:
                            pass

        # Narrative notes based on act position
        if report.act_position == "setup":
            report.narrative_notes.append("SETUP act — establish characters and world clearly")
        elif report.act_position == "confrontation":
            report.narrative_notes.append("CONFRONTATION act — build tension and conflict")
        elif report.act_position == "resolution":
            report.narrative_notes.append("RESOLUTION act — emotional payoff and closure")

        # Set status
        if report.shots_for_regen > 0:
            report.status = "needs_review"
        elif report.shots_flagged > len(shots) * 0.3:
            report.status = "needs_review"
        elif report.health_score >= 0.7:
            report.status = "approved"
        else:
            report.status = "directed"

        # Save report
        self._save_scene_report(report)

        return report

    # ────────────────────────────────────────────
    # FULL PROJECT DIRECTION
    # ────────────────────────────────────────────

    def direct_full_project(self) -> ProjectDirectorReport:
        """
        Full project evaluation — the director reviews everything.
        """
        report = ProjectDirectorReport(
            project_name=self.project_name,
            timestamp=datetime.utcnow().isoformat(),
        )

        # Group shots by scene
        shots_data = self.shot_plan if isinstance(self.shot_plan, list) else self.shot_plan.get("shots", [])
        if not shots_data:
            report.global_notes.append("No shots found in shot_plan")
            return report

        scenes = {}
        for shot in shots_data:
            sid = shot.get("scene_id", "")
            scenes.setdefault(sid, []).append(shot)

        report.total_scenes = len(scenes)

        # Evaluate each scene
        for scene_id in sorted(scenes.keys()):
            scene_report = self.evaluate_scene_render(scene_id, scenes[scene_id])
            report.scene_reports[scene_id] = scene_report.to_dict()
            if scene_report.status == "approved":
                report.scenes_approved += 1
            else:
                report.scenes_needs_review += 1

        # Overall health
        health_scores = [
            r.get("health_score", 0)
            for r in report.scene_reports.values()
        ]
        if health_scores:
            report.overall_health = round(sum(health_scores) / len(health_scores), 4)

        # Reward summary from Basal Ganglia
        if self.basal_ganglia:
            try:
                summary = self.basal_ganglia.get_reward_summary()
                report.reward_summary = summary
            except Exception:
                pass

        # Global notes
        if report.overall_health < 0.5:
            report.global_notes.append(
                "OVERALL HEALTH BELOW 50% — significant quality issues across project"
            )
        if report.scenes_needs_review > report.total_scenes * 0.5:
            report.global_notes.append(
                f"{report.scenes_needs_review}/{report.total_scenes} scenes need review"
            )

        # Save project report
        self._save_project_report(report)

        return report

    # ────────────────────────────────────────────
    # CANDIDATE SELECTION (Basal Ganglia integration)
    # ────────────────────────────────────────────

    def select_best_variant(
        self,
        candidates: List[dict],
        shot: dict,
        previous_shot: Optional[dict] = None,
    ) -> Tuple[dict, Dict]:
        """
        Use Basal Ganglia to select best variant from candidates.
        Returns (winner_candidate, scoring_details).
        """
        if not self.basal_ganglia:
            # Fallback: return first candidate
            return candidates[0] if candidates else ({}, {}), {}

        lite_data = None
        if self.truth:
            lite_data = self.truth.get_lite_data_object(shot)

        winner, result = self.basal_ganglia.select_best_candidate(
            candidates=candidates,
            shot=shot,
            cast_map=self.cast_map,
            previous_shot=previous_shot,
            lite_data=lite_data,
        )

        return winner, asdict(result) if result else {}

    # ────────────────────────────────────────────
    # PERSISTENCE
    # ────────────────────────────────────────────

    def _save_scene_report(self, report: SceneDirectorReport):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.reports_dir, f"scene_{report.scene_id}_{ts}.json")
        try:
            import tempfile
            fd, tmp = tempfile.mkstemp(dir=self.reports_dir, suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"Failed to save scene report: {e}")

    def _save_project_report(self, report: ProjectDirectorReport):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.reports_dir, f"project_{ts}.json")
        try:
            import tempfile
            fd, tmp = tempfile.mkstemp(dir=self.reports_dir, suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"Failed to save project report: {e}")

    # ────────────────────────────────────────────
    # QUICK STATUS
    # ────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Quick status check of all V24 subsystems."""
        return {
            "project": self.project_name,
            "subsystems": {
                "project_truth": "loaded" if self._truth else "not_loaded",
                "basal_ganglia": "loaded" if self._basal_ganglia else "not_loaded",
                "vision_analyst": "loaded" if self._vision_analyst else "not_loaded",
                "cast_map": f"{len([k for k,v in self.cast_map.items() if isinstance(v,dict) and not v.get('_is_alias_of')])} characters",
                "story_bible": f"{len(self.story_bible.get('scenes',[]))} scenes",
                "shot_plan": f"{len(self.shot_plan if isinstance(self.shot_plan, list) else self.shot_plan.get('shots',[]))} shots",
            },
            "genre": self.genre,
            "timestamp": datetime.utcnow().isoformat(),
        }
