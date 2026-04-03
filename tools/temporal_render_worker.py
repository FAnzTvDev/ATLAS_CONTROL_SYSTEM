#!/usr/bin/env python3
"""
ATLAS V27.3 — Temporal.io Parallel Render Orchestration
========================================================
Replaces sequential shot-by-shot rendering with Temporal workflows
that fire ALL independent shots in parallel.

Architecture:
  - RenderSceneWorkflow: Top-level workflow per scene
  - render_shot_activity: Individual shot generation (FAL call)
  - Chain-aware: sequential within chains, parallel across chains
  - Non-chain shots fire simultaneously

Performance:
  Sequential (current):  12 shots × 4min = 48min (Kling)
  Parallel (Temporal):   Wave 0 parallel + chain waves = ~8-12min

Usage:
  # Start worker
  python3 tools/temporal_render_worker.py

  # Trigger from controller
  from tools.temporal_render_worker import submit_parallel_render
  result = await submit_parallel_render(project, scene_id, shots, model="kling")
"""

import asyncio
import json
import os
import sys
import logging
import time
from datetime import timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger("temporal_render")

# ============================================================================
# DATA CONTRACTS
# ============================================================================

@dataclass
class ShotRenderInput:
    """Input for a single shot render activity."""
    project: str
    shot_id: str
    scene_id: str
    nano_prompt: str
    ltx_prompt: str
    ref_urls: List[str]
    video_model: str  # "ltx" or "kling"
    duration: float
    first_frame_path: str
    output_dir: str
    fal_params: Dict[str, Any] = None

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "shot_id": self.shot_id,
            "scene_id": self.scene_id,
            "nano_prompt": self.nano_prompt,
            "ltx_prompt": self.ltx_prompt,
            "ref_urls": self.ref_urls,
            "video_model": self.video_model,
            "duration": self.duration,
            "first_frame_path": self.first_frame_path,
            "output_dir": self.output_dir,
            "fal_params": self.fal_params or {},
        }

    @staticmethod
    def from_dict(d: dict) -> "ShotRenderInput":
        return ShotRenderInput(**{k: d[k] for k in ShotRenderInput.__dataclass_fields__ if k in d})


@dataclass
class ShotRenderResult:
    """Result from a single shot render activity."""
    shot_id: str
    success: bool
    video_path: str = ""
    duration_actual: float = 0
    elapsed_ms: int = 0
    error: str = ""
    model_used: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class SceneRenderInput:
    """Input for a full scene parallel render."""
    project: str
    scene_id: str
    shots: List[Dict[str, Any]]
    video_model: str
    chain_groups: List[List[str]]  # [[shot1, shot2], [shot3]] — sequential within group
    force: bool = False


# ============================================================================
# ACTIVITIES — Individual shot render (runs in Temporal worker)
# ============================================================================

try:
    from temporalio import activity, workflow
    from temporalio.client import Client
    from temporalio.worker import Worker
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    logger.warning("[TEMPORAL] temporalio not installed — parallel render unavailable")


if TEMPORAL_AVAILABLE:

    @activity.defn
    async def render_shot_activity(input_dict: dict) -> dict:
        """
        Render a single shot via FAL API.
        This is the atomic unit of work — one FAL call per shot.
        Runs as a Temporal activity with retry policy.
        """
        inp = ShotRenderInput.from_dict(input_dict)
        start = time.time()
        result = ShotRenderResult(shot_id=inp.shot_id, success=False, model_used=inp.video_model)

        try:
            import httpx

            # Build FAL payload based on model
            if inp.video_model == "kling":
                fal_endpoint = "https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video"
                payload = {
                    "prompt": inp.ltx_prompt[:2000],
                    "image_url": inp.first_frame_path,
                    "duration": str(min(int(inp.duration), 10)),
                    "aspect_ratio": "16:9",
                }
            else:  # ltx
                fal_endpoint = "https://queue.fal.run/fal-ai/ltx-2.3/image-to-video/fast"
                payload = {
                    "prompt": inp.ltx_prompt[:2000],
                    "image_url": inp.first_frame_path,
                    "num_frames": max(65, min(int(inp.duration * 24), 257)),
                    "resolution": "720p",
                }

            fal_key = os.environ.get("FAL_KEY", "")
            headers = {
                "Authorization": f"Key {fal_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=300) as client:
                # Submit to queue
                resp = await client.post(fal_endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                queue_data = resp.json()

                # Poll for completion
                request_id = queue_data.get("request_id", "")
                status_url = queue_data.get("status_url", f"{fal_endpoint}/requests/{request_id}/status")
                result_url = queue_data.get("response_url", f"{fal_endpoint}/requests/{request_id}")

                for _ in range(120):  # 10 min max wait
                    await asyncio.sleep(5)
                    status_resp = await client.get(status_url, headers=headers)
                    status = status_resp.json()
                    if status.get("status") == "COMPLETED":
                        break
                    if status.get("status") in ("FAILED", "CANCELLED"):
                        result.error = f"FAL status: {status.get('status')}"
                        return result.to_dict()

                # Get result
                result_resp = await client.get(result_url, headers=headers)
                result_data = result_resp.json()

                video_url = ""
                if "video" in result_data:
                    video_url = result_data["video"].get("url", "")
                elif "output" in result_data:
                    video_url = result_data["output"].get("video", {}).get("url", "")

                if video_url:
                    # Download video
                    video_resp = await client.get(video_url)
                    output_path = os.path.join(inp.output_dir, f"{inp.shot_id}.mp4")
                    os.makedirs(inp.output_dir, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(video_resp.content)
                    result.success = True
                    result.video_path = output_path
                    result.duration_actual = inp.duration
                else:
                    result.error = "No video URL in FAL response"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[TEMPORAL] Shot {inp.shot_id} failed: {e}")

        result.elapsed_ms = int((time.time() - start) * 1000)
        activity.logger.info(f"[TEMPORAL] {inp.shot_id}: {'OK' if result.success else 'FAIL'} "
                            f"in {result.elapsed_ms}ms ({inp.video_model})")
        return result.to_dict()


    @workflow.defn
    class RenderSceneWorkflow:
        """
        Temporal workflow that renders a full scene with chain-aware parallelism.

        Execution strategy:
          Wave 0: All non-chained shots fire in PARALLEL
          Chain waves: Sequential within each chain group, parallel across groups
        """

        @workflow.run
        async def run(self, input_dict: dict) -> dict:
            scene_id = input_dict["scene_id"]
            shots = input_dict["shots"]
            video_model = input_dict["video_model"]
            chain_groups = input_dict.get("chain_groups", [])
            project = input_dict["project"]

            results = {}
            all_chained = set()
            for group in chain_groups:
                for sid in group:
                    all_chained.add(sid)

            # Build shot lookup
            shot_map = {s.get("shot_id", ""): s for s in shots}

            # WAVE 0: All non-chained shots in parallel
            wave0_tasks = []
            for shot in shots:
                sid = shot.get("shot_id", "")
                if sid not in all_chained:
                    inp = self._build_shot_input(shot, project, video_model)
                    wave0_tasks.append(
                        workflow.execute_activity(
                            render_shot_activity,
                            arg=inp,
                            start_to_close_timeout=timedelta(minutes=15),
                            retry_policy=workflow.RetryPolicy(
                                maximum_attempts=2,
                                initial_interval=timedelta(seconds=10),
                            ),
                        )
                    )

            # Fire wave 0
            if wave0_tasks:
                wave0_results = await asyncio.gather(*wave0_tasks, return_exceptions=True)
                for r in wave0_results:
                    if isinstance(r, dict):
                        results[r["shot_id"]] = r
                    elif isinstance(r, Exception):
                        workflow.logger.error(f"Wave 0 error: {r}")

            # CHAIN WAVES: Sequential within group, parallel across groups
            chain_tasks = []
            for group in chain_groups:
                chain_tasks.append(self._run_chain_group(group, shot_map, project, video_model))

            if chain_tasks:
                chain_results = await asyncio.gather(*chain_tasks, return_exceptions=True)
                for group_result in chain_results:
                    if isinstance(group_result, dict):
                        results.update(group_result)

            return {
                "scene_id": scene_id,
                "total_shots": len(shots),
                "successful": sum(1 for r in results.values() if r.get("success")),
                "failed": sum(1 for r in results.values() if not r.get("success")),
                "results": results,
            }

        async def _run_chain_group(self, group: List[str], shot_map: dict,
                                    project: str, video_model: str) -> dict:
            """Run a chain group sequentially."""
            results = {}
            for sid in group:
                shot = shot_map.get(sid)
                if not shot:
                    continue
                inp = self._build_shot_input(shot, project, video_model)
                r = await workflow.execute_activity(
                    render_shot_activity,
                    arg=inp,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=workflow.RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=10),
                    ),
                )
                results[sid] = r
            return results

        def _build_shot_input(self, shot: dict, project: str, video_model: str) -> dict:
            """Build ShotRenderInput from shot dict."""
            sid = shot.get("shot_id", "")
            scene_id = shot.get("scene_id", sid[:3])
            base_dir = f"pipeline_outputs/{project}"
            ff_path = f"{base_dir}/first_frames/{sid}.jpg"

            model_dir = "videos_kling" if video_model == "kling" else "videos"
            return ShotRenderInput(
                project=project,
                shot_id=sid,
                scene_id=scene_id,
                nano_prompt=shot.get("nano_prompt", ""),
                ltx_prompt=shot.get("ltx_motion_prompt", ""),
                ref_urls=shot.get("_fal_image_urls_resolved", []),
                video_model=video_model,
                duration=float(shot.get("duration", 5)),
                first_frame_path=ff_path,
                output_dir=f"{base_dir}/{model_dir}",
                fal_params=shot.get("_fal_params", {}),
            ).to_dict()


# ============================================================================
# SUBMISSION API — Called from controller or orchestrator
# ============================================================================

async def submit_parallel_render(
    project: str,
    scene_id: str,
    shots: List[dict],
    video_model: str = "ltx",
    chain_groups: Optional[List[List[str]]] = None,
    temporal_address: str = "localhost:7233",
) -> dict:
    """
    Submit a scene render to Temporal for parallel execution.

    Args:
        project: Project name
        scene_id: Scene to render
        shots: List of shot dicts (must have first frames generated)
        video_model: "ltx" or "kling"
        chain_groups: Optional chain groups for sequential ordering
        temporal_address: Temporal server address

    Returns:
        Workflow result dict with per-shot results
    """
    if not TEMPORAL_AVAILABLE:
        return {"error": "temporalio not installed", "fallback": "sequential"}

    client = await Client.connect(temporal_address)

    workflow_input = {
        "project": project,
        "scene_id": scene_id,
        "shots": shots,
        "video_model": video_model,
        "chain_groups": chain_groups or [],
    }

    result = await client.execute_workflow(
        RenderSceneWorkflow.run,
        workflow_input,
        id=f"render-{project}-{scene_id}-{video_model}-{int(time.time())}",
        task_queue="atlas-render-queue",
        execution_timeout=timedelta(minutes=60),
    )

    return result


async def start_render_worker(temporal_address: str = "localhost:7233"):
    """Start a Temporal worker that processes render activities."""
    if not TEMPORAL_AVAILABLE:
        logger.error("[TEMPORAL] Cannot start worker — temporalio not installed")
        return

    client = await Client.connect(temporal_address)
    worker = Worker(
        client,
        task_queue="atlas-render-queue",
        workflows=[RenderSceneWorkflow],
        activities=[render_shot_activity],
    )
    logger.info("[TEMPORAL] Render worker started on atlas-render-queue")
    await worker.run()


# ============================================================================
# FALLBACK — In-process parallel render (no Temporal server needed)
# ============================================================================

async def parallel_render_in_process(
    project: str,
    scene_id: str,
    shots: List[dict],
    video_model: str = "ltx",
    chain_groups: Optional[List[List[str]]] = None,
    render_fn=None,
) -> dict:
    """
    Parallel render WITHOUT Temporal — uses asyncio.gather directly.
    This is the immediate-value path: no Temporal server needed.

    Args:
        render_fn: async function(shot_dict, video_model) -> result_dict
                   If None, uses the built-in FAL caller.
    """
    if render_fn is None:
        if TEMPORAL_AVAILABLE:
            render_fn = lambda inp: render_shot_activity(inp)
        else:
            raise ValueError("No render function provided and temporal not available")

    all_chained = set()
    for group in (chain_groups or []):
        for sid in group:
            all_chained.add(sid)

    shot_map = {s.get("shot_id", ""): s for s in shots}
    results = {}
    base_dir = f"pipeline_outputs/{project}"
    model_dir = "videos_kling" if video_model == "kling" else "videos"

    def build_input(shot):
        sid = shot.get("shot_id", "")
        return ShotRenderInput(
            project=project,
            shot_id=sid,
            scene_id=shot.get("scene_id", sid[:3]),
            nano_prompt=shot.get("nano_prompt", ""),
            ltx_prompt=shot.get("ltx_motion_prompt", ""),
            ref_urls=shot.get("_fal_image_urls_resolved", []),
            video_model=video_model,
            duration=float(shot.get("duration", 5)),
            first_frame_path=f"{base_dir}/first_frames/{sid}.jpg",
            output_dir=f"{base_dir}/{model_dir}",
        ).to_dict()

    # Wave 0: parallel non-chained shots
    wave0_inputs = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        if sid not in all_chained:
            wave0_inputs.append(build_input(shot))

    if wave0_inputs:
        logger.info(f"[PARALLEL] Wave 0: {len(wave0_inputs)} shots firing in parallel")
        wave0_tasks = [render_fn(inp) for inp in wave0_inputs]
        wave0_results = await asyncio.gather(*wave0_tasks, return_exceptions=True)
        for r in wave0_results:
            if isinstance(r, dict):
                results[r.get("shot_id", "")] = r

    # Chain waves: sequential within, parallel across
    async def run_chain(group):
        group_results = {}
        for sid in group:
            shot = shot_map.get(sid)
            if shot:
                r = await render_fn(build_input(shot))
                if isinstance(r, dict):
                    group_results[sid] = r
        return group_results

    if chain_groups:
        chain_tasks = [run_chain(g) for g in chain_groups]
        chain_results = await asyncio.gather(*chain_tasks, return_exceptions=True)
        for gr in chain_results:
            if isinstance(gr, dict):
                results.update(gr)

    successful = sum(1 for r in results.values() if r.get("success"))
    return {
        "scene_id": scene_id,
        "total_shots": len(shots),
        "successful": successful,
        "failed": len(shots) - successful,
        "results": results,
        "execution_mode": "in_process_parallel",
    }


# ============================================================================
# CLI — Start worker or run test
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ATLAS Temporal Render Worker")
    parser.add_argument("--address", default="localhost:7233", help="Temporal server address")
    parser.add_argument("--test", action="store_true", help="Run test render")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.test:
        print("[TEMPORAL] Test mode — verifying imports and data contracts")
        inp = ShotRenderInput(
            project="test", shot_id="001_001A", scene_id="001",
            nano_prompt="test prompt", ltx_prompt="test ltx",
            ref_urls=[], video_model="ltx", duration=5.0,
            first_frame_path="test.jpg", output_dir="/tmp/test",
        )
        print(f"  ShotRenderInput: {inp.to_dict()['shot_id']} OK")
        result = ShotRenderResult(shot_id="001_001A", success=True, elapsed_ms=100)
        print(f"  ShotRenderResult: {result.to_dict()['shot_id']} OK")
        print(f"  TEMPORAL_AVAILABLE: {TEMPORAL_AVAILABLE}")
        print("[TEMPORAL] All contracts valid")
    else:
        asyncio.run(start_render_worker(args.address))
