#!/usr/bin/env python3
"""
ATLAS V16.0 - Temporal Client
==============================
Client functions for interacting with Temporal workflows from the orchestrator.

Usage:
    from temporal.client import (
        start_episode_generation,
        get_workflow_progress,
        send_human_approval,
        cancel_workflow,
    )

    # Start a workflow
    run_id = await start_episode_generation("kord", auto_approve=False)

    # Check progress
    progress = await get_workflow_progress(run_id)

    # Approve a human gate
    await send_human_approval(run_id, approved=True)
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import timedelta

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.service import TLSConfig

# Temporal Cloud Configuration
# ==============================================================================
# Production: us-east4.gcp.api.temporal.io:7233
# Namespace: quickstart-fanztv.ojuv1
# ==============================================================================
TEMPORAL_CLOUD_ADDRESS = "us-east4.gcp.api.temporal.io:7233"
TEMPORAL_CLOUD_NAMESPACE = "quickstart-fanztv.ojuv1"

# API Key - can be overridden via environment variable
_DEFAULT_API_KEY = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6Ild2dHdhQSJ9."
    "eyJhY2NvdW50X2lkIjoib2p1djEiLCJhdWQiOlsidGVtcG9yYWwuaW8iXSwiZXhwIjoxODMzMTEzNjg1LCJ"
    "pc3MiOiJ0ZW1wb3JhbC5pbyIsImp0aSI6IkxNb0JpYjZOd2hDR0VycTM4SUFHWm0xUXBJQ2hLT21IIiwia2"
    "V5X2lkIjoiTE1vQmliNk53aENHRXJxMzhJQUdabTFRcElDaEtPbUgiLCJzdWIiOiJjY2E3Mjg4MjRiZDM0"
    "NzE3YjI2ZDBiOTcwNDZmNjNlOCJ9."
    "J6w6NsE0kRWRkkuKXA7XdVCGq5hPUy-WGr2kuZHcidgKfCsrCGomtKzVNRNzB9CIz7z_8RYxdVNPFmSa_xnZ8g"
)
TEMPORAL_API_KEY = os.environ.get("TEMPORAL_API_KEY", _DEFAULT_API_KEY)

# Use cloud by default since we have API key configured
USE_TEMPORAL_CLOUD = True

from temporal.workflows import (
    EpisodeGenerationWorkflow,
    EpisodeGenerationInput,
    ShotRenderWorkflow,
    ShotRenderInput,
    ValidationGateWorkflow,
)

logger = logging.getLogger("atlas.temporal.client")

# Singleton client instance
_client: Optional[Client] = None
_client_lock = asyncio.Lock()


async def get_client(
    address: str = None,
    namespace: str = None,
    use_cloud: bool = None,
) -> Client:
    """
    Get or create the Temporal client singleton.

    Connects to Temporal Cloud if TEMPORAL_API_KEY env var is set,
    otherwise connects to local Temporal server.

    Args:
        address: Override the default address
        namespace: Override the default namespace
        use_cloud: Force cloud/local mode (default: auto-detect from API key)
    """
    global _client

    async with _client_lock:
        if _client is None:
            # Determine if using cloud
            cloud_mode = use_cloud if use_cloud is not None else USE_TEMPORAL_CLOUD

            if cloud_mode and TEMPORAL_API_KEY:
                # Temporal Cloud connection with TLS and API key
                target_address = address or TEMPORAL_CLOUD_ADDRESS
                target_namespace = namespace or TEMPORAL_CLOUD_NAMESPACE

                logger.info(f"Connecting to Temporal Cloud at {target_address}")
                logger.info(f"Namespace: {target_namespace}")

                _client = await Client.connect(
                    target_address,
                    namespace=target_namespace,
                    tls=True,
                    rpc_metadata={"temporal-namespace": target_namespace},
                    api_key=TEMPORAL_API_KEY,
                )
                logger.info("Temporal Cloud client connected (TLS + API Key)")
            else:
                # Local Temporal server connection
                target_address = address or "localhost:7233"
                target_namespace = namespace or "default"

                logger.info(f"Connecting to local Temporal at {target_address}")
                _client = await Client.connect(target_address, namespace=target_namespace)
                logger.info("Temporal local client connected")

        return _client


# =============================================================================
# WORKFLOW STARTERS
# =============================================================================

async def start_episode_generation(
    project_name: str,
    episode_id: Optional[str] = None,
    target_runtime_minutes: int = 45,
    auto_approve: bool = False,
    task_queue: str = "atlas-production",
) -> Dict[str, Any]:
    """
    Start an episode generation workflow.

    Args:
        project_name: Name of the project (e.g., "kord")
        episode_id: Optional episode identifier
        target_runtime_minutes: Target runtime in minutes
        auto_approve: If True, skip human approval gates
        task_queue: Temporal task queue name

    Returns:
        {
            "workflow_id": str,
            "run_id": str,
            "status": "started",
        }
    """
    client = await get_client()

    workflow_id = f"episode-{project_name}-{episode_id or 'main'}"

    logger.info(f"Starting EpisodeGenerationWorkflow: {workflow_id}")

    handle = await client.start_workflow(
        EpisodeGenerationWorkflow.run,
        EpisodeGenerationInput(
            project_name=project_name,
            episode_id=episode_id,
            target_runtime_minutes=target_runtime_minutes,
            auto_approve=auto_approve,
        ),
        id=workflow_id,
        task_queue=task_queue,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )

    return {
        "workflow_id": workflow_id,
        "run_id": handle.result_run_id,
        "status": "started",
        "project": project_name,
    }


async def start_shot_render(
    project_name: str,
    shot_id: str,
    shot_data: Dict[str, Any],
    render_type: str = "image",
    task_queue: str = "atlas-production",
) -> Dict[str, Any]:
    """
    Start a single shot render workflow.

    Args:
        project_name: Name of the project
        shot_id: Shot identifier
        shot_data: Shot data dictionary
        render_type: "image" or "video"
        task_queue: Temporal task queue name

    Returns:
        Workflow handle info
    """
    client = await get_client()

    workflow_id = f"shot-{project_name}-{shot_id}-{render_type}"

    handle = await client.start_workflow(
        ShotRenderWorkflow.run,
        ShotRenderInput(
            project_name=project_name,
            shot_id=shot_id,
            shot_data=shot_data,
            render_type=render_type,
        ),
        id=workflow_id,
        task_queue=task_queue,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )

    return {
        "workflow_id": workflow_id,
        "run_id": handle.result_run_id,
        "status": "started",
        "shot_id": shot_id,
        "render_type": render_type,
    }


async def start_validation(
    project_name: str,
    task_queue: str = "atlas-production",
) -> Dict[str, Any]:
    """
    Start a validation gate workflow.

    Returns validation results without starting full render.
    """
    client = await get_client()

    workflow_id = f"validate-{project_name}"

    handle = await client.start_workflow(
        ValidationGateWorkflow.run,
        project_name,
        id=workflow_id,
        task_queue=task_queue,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )

    # Wait for validation to complete (it's fast)
    result = await handle.result()

    return {
        "workflow_id": workflow_id,
        "passed": result.passed,
        "grade": result.grade,
        "blocking_issues": result.blocking_issues,
        "warnings": result.warnings,
    }


# =============================================================================
# WORKFLOW QUERIES
# =============================================================================

async def get_workflow_progress(workflow_id: str) -> Dict[str, Any]:
    """
    Query the progress of a running workflow.

    Returns:
        Progress information from the workflow
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        progress = await handle.query(EpisodeGenerationWorkflow.query_progress)
        return {
            "workflow_id": workflow_id,
            "status": "running",
            **progress,
        }
    except Exception as e:
        logger.error(f"Failed to query workflow {workflow_id}: {e}")
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


async def get_critic_report(workflow_id: str) -> Dict[str, Any]:
    """
    Query the latest critic report from a running workflow.
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        report = await handle.query(EpisodeGenerationWorkflow.query_critic_report)
        return {
            "workflow_id": workflow_id,
            **report,
        }
    except Exception as e:
        logger.error(f"Failed to query critic report: {e}")
        return {"error": str(e)}


async def get_workflow_result(
    workflow_id: str,
    timeout_seconds: float = 300,
) -> Dict[str, Any]:
    """
    Wait for and return the workflow result.

    Args:
        workflow_id: The workflow ID to wait for
        timeout_seconds: Maximum time to wait

    Returns:
        The workflow result
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        result = await asyncio.wait_for(
            handle.result(),
            timeout=timeout_seconds,
        )
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "result": result,
        }
    except asyncio.TimeoutError:
        return {
            "workflow_id": workflow_id,
            "status": "timeout",
            "error": f"Workflow did not complete within {timeout_seconds}s",
        }
    except Exception as e:
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


# =============================================================================
# WORKFLOW SIGNALS
# =============================================================================

async def send_human_approval(
    workflow_id: str,
    approved: bool,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Send a human approval signal to a workflow.

    Args:
        workflow_id: The workflow to signal
        approved: True to approve, False to reject
        notes: Optional notes about the decision

    Returns:
        Signal confirmation
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        await handle.signal(
            EpisodeGenerationWorkflow.signal_human_approval,
            approved,
            notes,
        )
        return {
            "workflow_id": workflow_id,
            "signal": "human_approval",
            "approved": approved,
            "notes": notes,
            "status": "sent",
        }
    except Exception as e:
        logger.error(f"Failed to send approval signal: {e}")
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


async def signal_skip_to_shot(
    workflow_id: str,
    shot_index: int,
) -> Dict[str, Any]:
    """
    Signal a workflow to skip to a specific shot.
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        await handle.signal(
            EpisodeGenerationWorkflow.signal_skip_to_shot,
            shot_index,
        )
        return {
            "workflow_id": workflow_id,
            "signal": "skip_to_shot",
            "shot_index": shot_index,
            "status": "sent",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def signal_pause(workflow_id: str) -> Dict[str, Any]:
    """
    Signal a workflow to pause after the current shot.
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        await handle.signal(EpisodeGenerationWorkflow.signal_pause)
        return {
            "workflow_id": workflow_id,
            "signal": "pause",
            "status": "sent",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =============================================================================
# WORKFLOW CONTROL
# =============================================================================

async def cancel_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Cancel a running workflow.
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        await handle.cancel()
        return {
            "workflow_id": workflow_id,
            "status": "cancelled",
        }
    except Exception as e:
        logger.error(f"Failed to cancel workflow: {e}")
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


async def terminate_workflow(
    workflow_id: str,
    reason: str = "Terminated by user",
) -> Dict[str, Any]:
    """
    Forcefully terminate a workflow.
    """
    client = await get_client()

    handle = client.get_workflow_handle(workflow_id)

    try:
        await handle.terminate(reason)
        return {
            "workflow_id": workflow_id,
            "status": "terminated",
            "reason": reason,
        }
    except Exception as e:
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


async def list_workflows(
    project_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List all workflows, optionally filtered by project.
    """
    client = await get_client()

    query = ""
    if project_name:
        query = f'WorkflowId STARTS_WITH "episode-{project_name}"'

    workflows = []
    async for workflow in client.list_workflows(query=query):
        workflows.append({
            "workflow_id": workflow.id,
            "run_id": workflow.run_id,
            "status": str(workflow.status),
            "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
        })

    return {
        "workflows": workflows,
        "count": len(workflows),
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def check_temporal_health() -> Dict[str, Any]:
    """
    Check if Temporal is available and healthy.
    """
    try:
        client = await get_client()

        # Try to list system workflows (quick operation)
        count = 0
        async for _ in client.list_workflows(query="", page_size=1):
            count += 1
            break

        return {
            "status": "healthy",
            "connected": True,
            "address": "localhost:7233",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }
