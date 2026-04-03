"""
ATLAS V24 — Integration Layer
==============================
Clean integration point for wiring V24 subsystems into orchestrator_server.py.
Import this module to get access to all V24 capabilities:

  from tools.v23_integration import V24Pipeline

Usage in orchestrator_server.py:
  v23 = V24Pipeline(project_path)

  # Pre-render: prepare context
  scene_ctx = v23.prepare_scene(scene_id)

  # Per-shot: check readiness + get LITE data
  readiness = v23.check_shot(shot)
  lite_data = v23.get_lite_data(shot)

  # Post-render: evaluate
  health = v23.evaluate_scene(scene_id, shots)

  # Variant selection: use Basal Ganglia
  winner = v23.select_variant(candidates, shot, prev_shot)

  # Full project: director's report
  report = v23.full_evaluation()
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class V24Pipeline:
    """
    Single entry point for all V24 subsystems.
    Lazy-loads everything so importing is cheap.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self._meta_director = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy init — only loads when first used."""
        if self._initialized:
            return
        try:
            from tools.meta_director import MetaDirector
            self._meta_director = MetaDirector(self.project_path)
            self._initialized = True
            logger.info(f"[V24] Pipeline initialized for {os.path.basename(self.project_path)}")
        except Exception as e:
            logger.warning(f"[V24] Failed to initialize: {e}")
            self._initialized = True  # Don't retry

    # ────────────────────────────────────────────
    # PRE-RENDER
    # ────────────────────────────────────────────

    def prepare_scene(self, scene_id: str) -> Dict[str, Any]:
        """Prepare full scene context before rendering."""
        self._ensure_initialized()
        if self._meta_director:
            return self._meta_director.prepare_scene_context(scene_id)
        return {"scene_id": scene_id}

    def check_shot(self, shot: dict, scene_context: Optional[Dict] = None) -> Dict:
        """Check single shot readiness. Returns decision dict."""
        self._ensure_initialized()
        if self._meta_director:
            ctx = scene_context or {}
            from dataclasses import asdict
            decision = self._meta_director.check_shot_readiness(shot, ctx)
            return asdict(decision)
        return {"decision_type": "approve", "reason": "V24 not loaded"}

    def get_lite_data(self, shot: dict) -> Dict:
        """Get LITE data object for a shot (Global Perception context)."""
        self._ensure_initialized()
        if self._meta_director and self._meta_director.truth:
            return self._meta_director.truth.get_lite_data_object(shot)
        return {}

    # ────────────────────────────────────────────
    # POST-RENDER
    # ────────────────────────────────────────────

    def evaluate_scene(self, scene_id: str, shots: List[dict]) -> Dict:
        """Evaluate rendered scene. Returns director report dict."""
        self._ensure_initialized()
        if self._meta_director:
            report = self._meta_director.evaluate_scene_render(scene_id, shots)
            return report.to_dict()
        return {"scene_id": scene_id, "status": "skipped"}

    def evaluate_project(self) -> Dict:
        """Full project evaluation."""
        self._ensure_initialized()
        if self._meta_director:
            report = self._meta_director.direct_full_project()
            return report.to_dict()
        return {"status": "skipped"}

    # ────────────────────────────────────────────
    # VARIANT SELECTION
    # ────────────────────────────────────────────

    def select_variant(
        self,
        candidates: List[dict],
        shot: dict,
        previous_shot: Optional[dict] = None,
    ) -> Tuple[dict, Dict]:
        """Select best variant using Basal Ganglia scoring."""
        self._ensure_initialized()
        if self._meta_director:
            return self._meta_director.select_best_variant(candidates, shot, previous_shot)
        return (candidates[0] if candidates else {}, {})

    # ────────────────────────────────────────────
    # STATUS
    # ────────────────────────────────────────────

    def get_status(self) -> Dict:
        """V24 subsystem status."""
        self._ensure_initialized()
        if self._meta_director:
            return self._meta_director.get_status()
        return {"status": "not_initialized"}

    # ────────────────────────────────────────────
    # ACTOR INTENT
    # ────────────────────────────────────────────

    def extract_actor_intent(self, shot: dict, story_bible: dict) -> Dict:
        """Extract actor intent for a shot using ActorIntentLayer."""
        try:
            from tools.actor_intent_layer import extract_character_intents
            intents = extract_character_intents(shot, story_bible)
            return intents
        except Exception as e:
            logger.warning(f"[V24] Actor intent extraction failed: {e}")
            return {}

    # ────────────────────────────────────────────
    # REWARD MEMORY
    # ────────────────────────────────────────────

    def get_reward_summary(self) -> Dict:
        """Get reward memory summary from Basal Ganglia."""
        self._ensure_initialized()
        if self._meta_director and self._meta_director.basal_ganglia:
            return self._meta_director.basal_ganglia.get_reward_summary()
        return {}

    def record_render_reward(
        self,
        shot_id: str,
        composite_score: float,
        dimension_scores: Optional[Dict[str, float]] = None,
    ):
        """Record a reward for a rendered shot."""
        self._ensure_initialized()
        if self._meta_director and self._meta_director.basal_ganglia:
            try:
                self._meta_director.basal_ganglia._record_reward(
                    shot_id=shot_id,
                    prompt_hash="post_render",
                    result=None,
                    composite=composite_score,
                )
            except Exception as e:
                logger.warning(f"[V24] Failed to record reward: {e}")


# ────────────────────────────────────────────
# ENDPOINT HANDLERS (for wiring into orchestrator_server.py)
# ────────────────────────────────────────────

def register_v23_endpoints(app, get_project_path_fn):
    """
    Register V24 API endpoints on a FastAPI app.

    Usage in orchestrator_server.py:
        from tools.v23_integration import register_v23_endpoints
        register_v23_endpoints(app, lambda project: f"pipeline_outputs/{project}")
    """
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    @app.get("/api/v23/status/{project}")
    async def v23_status(project: str):
        """V24 subsystem status."""
        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)
        return JSONResponse(content=pipeline.get_status())

    @app.post("/api/v23/evaluate-scene")
    async def v23_evaluate_scene(body: dict):
        """Evaluate a rendered scene via V24 Vision Analyst + Meta-Director."""
        project = body.get("project", "")
        scene_id = body.get("scene_id", "")
        if not project or not scene_id:
            raise HTTPException(status_code=400, detail="project and scene_id required")

        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)

        # Load shots for this scene
        shot_plan_path = os.path.join(project_path, "shot_plan.json")
        if not os.path.exists(shot_plan_path):
            raise HTTPException(status_code=404, detail="shot_plan.json not found")

        with open(shot_plan_path) as f:
            data = json.load(f)
        shots = data.get("shots", data) if isinstance(data, dict) else data
        scene_shots = [s for s in shots if s.get("scene_id") == scene_id]

        result = pipeline.evaluate_scene(scene_id, scene_shots)
        return JSONResponse(content=result)

    @app.post("/api/v23/evaluate-project")
    async def v23_evaluate_project(body: dict):
        """Full project evaluation via V24."""
        project = body.get("project", "")
        if not project:
            raise HTTPException(status_code=400, detail="project required")

        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)
        result = pipeline.evaluate_project()
        return JSONResponse(content=result)

    @app.post("/api/v23/generate-truth")
    async def v23_generate_truth(body: dict):
        """Generate ATLAS_PROJECT_TRUTH.json for a project."""
        project = body.get("project", "")
        if not project:
            raise HTTPException(status_code=400, detail="project required")

        project_path = get_project_path_fn(project)
        try:
            from tools.project_truth import generate_project_truth
            truth = generate_project_truth(project_path)
            return JSONResponse(content={
                "success": True,
                "project": project,
                "scenes": len(truth.act_outline.acts) if truth.act_outline else 0,
                "characters": len(truth.character_arcs),
                "path": os.path.join(project_path, "ATLAS_PROJECT_TRUTH.json"),
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v23/reward-summary/{project}")
    async def v23_reward_summary(project: str):
        """Get reward memory summary."""
        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)
        return JSONResponse(content=pipeline.get_reward_summary())

    @app.post("/api/v23/select-variant")
    async def v23_select_variant(body: dict):
        """Use Basal Ganglia to select best variant."""
        project = body.get("project", "")
        candidates = body.get("candidates", [])
        shot = body.get("shot", {})
        previous_shot = body.get("previous_shot")

        if not project or not candidates:
            raise HTTPException(status_code=400, detail="project and candidates required")

        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)
        winner, details = pipeline.select_variant(candidates, shot, previous_shot)
        return JSONResponse(content={"winner": winner, "scoring": details})

    @app.post("/api/v23/shot-readiness")
    async def v23_shot_readiness(body: dict):
        """Check shot readiness via Meta-Director."""
        project = body.get("project", "")
        shot = body.get("shot", {})

        if not project or not shot:
            raise HTTPException(status_code=400, detail="project and shot required")

        project_path = get_project_path_fn(project)
        pipeline = V24Pipeline(project_path)
        decision = pipeline.check_shot(shot)
        return JSONResponse(content=decision)

    logger.info("[V24] 7 endpoints registered: status, evaluate-scene, evaluate-project, generate-truth, reward-summary, select-variant, shot-readiness")
