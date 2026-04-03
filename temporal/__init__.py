"""
ATLAS V16.0 Temporal Integration
=================================
Durable execution for movie generation workflows.

Usage:
    # Start the Temporal server (in terminal)
    temporal server start-dev

    # Start the worker (in another terminal)
    python -m temporal.worker

    # Trigger workflow from orchestrator
    from temporal.client import start_episode_generation
    await start_episode_generation("kord")
"""

from .workflows import (
    EpisodeGenerationWorkflow,
    ShotRenderWorkflow,
    ValidationGateWorkflow,
    EpisodeGenerationInput,
    ShotRenderInput,
)

from .activities import (
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
)

__all__ = [
    # Workflows
    "EpisodeGenerationWorkflow",
    "ShotRenderWorkflow",
    "ValidationGateWorkflow",
    "EpisodeGenerationInput",
    "ShotRenderInput",
    # Activities
    "validate_prerequisites",
    "load_project_state",
    "save_project_state",
    "run_cinematographer_agent",
    "run_director_critic",
    "render_shot_image",
    "render_shot_video",
    "run_preflight_check",
    "update_shot_in_db",
    "notify_human_required",
]
