#!/usr/bin/env python3
"""
ATLAS V16.0 - Temporal Worker
==============================
Runs the Temporal worker that executes workflows and activities.

Usage:
    # First, start Temporal server
    temporal server start-dev

    # Then start this worker
    python -m temporal.worker

    # Or with custom task queue
    python -m temporal.worker --task-queue atlas-renders
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from temporalio.client import Client
from temporalio.worker import Worker

# Temporal Cloud Configuration (shared with client.py)
TEMPORAL_CLOUD_ADDRESS = "us-east4.gcp.api.temporal.io:7233"
TEMPORAL_CLOUD_NAMESPACE = "quickstart-fanztv.ojuv1"
_DEFAULT_API_KEY = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6Ild2dHdhQSJ9."
    "eyJhY2NvdW50X2lkIjoib2p1djEiLCJhdWQiOlsidGVtcG9yYWwuaW8iXSwiZXhwIjoxODMzMTEzNjg1LCJ"
    "pc3MiOiJ0ZW1wb3JhbC5pbyIsImp0aSI6IkxNb0JpYjZOd2hDR0VycTM4SUFHWm0xUXBJQ2hLT21IIiwia2"
    "V5X2lkIjoiTE1vQmliNk53aENHRXJxMzhJQUdabTFRcElDaEtPbUgiLCJzdWIiOiJjY2E3Mjg4MjRiZDM0"
    "NzE3YjI2ZDBiOTcwNDZmNjNlOCJ9."
    "J6w6NsE0kRWRkkuKXA7XdVCGq5hPUy-WGr2kuZHcidgKfCsrCGomtKzVNRNzB9CIz7z_8RYxdVNPFmSa_xnZ8g"
)
TEMPORAL_API_KEY = os.environ.get("TEMPORAL_API_KEY", _DEFAULT_API_KEY)

# Import workflows and activities
from temporal.workflows import (
    EpisodeGenerationWorkflow,
    ShotRenderWorkflow,
    ValidationGateWorkflow,
)
from temporal.activities import (
    validate_prerequisites,
    load_project_state,
    save_project_state,
    run_cinematographer_agent,
    run_director_critic,
    render_shot_image,
    render_shot_video,
    run_preflight_check,
    update_shot_in_db,
    notify_human_required,
    # V16.3: Extension activities for shots > 20 seconds
    render_extended_video,
    extract_last_frame,
    stitch_video_segments,
    save_render_checkpoint,
    load_render_checkpoint,
    clear_render_checkpoint,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("atlas.temporal.worker")


async def run_worker(
    temporal_address: str = None,
    task_queue: str = "atlas-production",
    namespace: str = None,
    use_cloud: bool = True,
):
    """
    Run the Temporal worker.

    Args:
        temporal_address: Temporal server address (auto-detected if not specified)
        task_queue: Task queue name for this worker
        namespace: Temporal namespace (auto-detected if not specified)
        use_cloud: Use Temporal Cloud (default: True if API key available)
    """
    if use_cloud and TEMPORAL_API_KEY:
        # Connect to Temporal Cloud with TLS and API key
        target_address = temporal_address or TEMPORAL_CLOUD_ADDRESS
        target_namespace = namespace or TEMPORAL_CLOUD_NAMESPACE

        logger.info(f"Connecting to Temporal Cloud at {target_address}")
        logger.info(f"Namespace: {target_namespace}")

        client = await Client.connect(
            target_address,
            namespace=target_namespace,
            tls=True,
            rpc_metadata={"temporal-namespace": target_namespace},
            api_key=TEMPORAL_API_KEY,
        )
        logger.info("Connected to Temporal Cloud (TLS + API Key)")
    else:
        # Connect to local Temporal server
        target_address = temporal_address or "localhost:7233"
        target_namespace = namespace or "default"

        logger.info(f"Connecting to local Temporal at {target_address}")
        client = await Client.connect(target_address, namespace=target_namespace)
        logger.info("Connected to local Temporal")

    logger.info(f"Starting worker on task queue: {task_queue}")

    # Create and run worker
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[
            EpisodeGenerationWorkflow,
            ShotRenderWorkflow,
            ValidationGateWorkflow,
        ],
        activities=[
            validate_prerequisites,
            load_project_state,
            save_project_state,
            run_cinematographer_agent,
            run_director_critic,
            render_shot_image,
            render_shot_video,
            run_preflight_check,
            update_shot_in_db,
            notify_human_required,
            # V16.3: Extension activities
            render_extended_video,
            extract_last_frame,
            stitch_video_segments,
            save_render_checkpoint,
            load_render_checkpoint,
            clear_render_checkpoint,
        ],
    )

    logger.info("=" * 60)
    logger.info("ATLAS V16.0 Temporal Worker Started")
    logger.info("=" * 60)
    logger.info(f"  Temporal: {target_address}")
    logger.info(f"  Task Queue: {task_queue}")
    logger.info(f"  Namespace: {target_namespace}")
    logger.info(f"  Cloud Mode: {use_cloud and bool(TEMPORAL_API_KEY)}")
    logger.info("=" * 60)
    logger.info("Workflows:")
    logger.info("  - EpisodeGenerationWorkflow")
    logger.info("  - ShotRenderWorkflow")
    logger.info("  - ValidationGateWorkflow")
    logger.info("Activities:")
    logger.info("  - validate_prerequisites")
    logger.info("  - load_project_state / save_project_state")
    logger.info("  - run_cinematographer_agent / run_director_critic")
    logger.info("  - render_shot_image / render_shot_video")
    logger.info("  - run_preflight_check")
    logger.info("  - notify_human_required")
    logger.info("  V16.3 Extension Activities:")
    logger.info("  - render_extended_video (shots > 20s)")
    logger.info("  - extract_last_frame / stitch_video_segments")
    logger.info("  - save/load/clear_render_checkpoint")
    logger.info("=" * 60)
    logger.info("Ready to process workflows. Press Ctrl+C to stop.")

    await worker.run()


def main():
    parser = argparse.ArgumentParser(description="ATLAS Temporal Worker")
    parser.add_argument(
        "--address",
        default=None,
        help="Temporal server address (auto-detected based on mode)",
    )
    parser.add_argument(
        "--task-queue",
        default="atlas-production",
        help="Task queue name (default: atlas-production)",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Temporal namespace (auto-detected based on mode)",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        default=True,
        help="Use Temporal Cloud (default: True)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local Temporal server instead of cloud",
    )

    args = parser.parse_args()

    # --local flag overrides --cloud
    use_cloud = not args.local

    try:
        asyncio.run(
            run_worker(
                temporal_address=args.address,
                task_queue=args.task_queue,
                namespace=args.namespace,
                use_cloud=use_cloud,
            )
        )
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise


if __name__ == "__main__":
    main()
