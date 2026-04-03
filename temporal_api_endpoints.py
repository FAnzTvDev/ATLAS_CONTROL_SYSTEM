"""
FastAPI endpoints for Temporal.io workflow orchestration in ATLAS V17.

These endpoints provide:
- Health checks for the Temporal system
- Workflow status queries per project
- Stalled workflow detection and remediation recommendations
- Integration points for the pipeline orchestration

To integrate into orchestrator_server.py:
1. Import this module: from temporal_api_endpoints import register_temporal_endpoints
2. After app = FastAPI(...), call: register_temporal_endpoints(app, tracker_instance)
3. The tracker instance should come from: from temporal_workflow_tracker import init_temporal_tracker
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from temporal_workflow_tracker import (
    get_temporal_tracker,
    WorkflowState,
    ActivityState,
)


logger = logging.getLogger(__name__)


# Pydantic models for request/response validation


class ActivityStatus(BaseModel):
    """Status of a single activity"""
    name: str
    state: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    progress: Optional[Dict[str, Any]] = None


class WorkflowStatus(BaseModel):
    """Status of a workflow execution"""
    workflow_id: str
    project: str
    workflow_type: str
    state: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    activities: Dict[str, ActivityStatus]


class HealthSummary(BaseModel):
    """Overall Temporal system health"""
    total_workflows: int
    completed: int = 0
    failed: int = 0
    running: int = 0
    timed_out: int = 0
    pending: int = 0
    success_rate: float = 0.0
    avg_duration_ms: Optional[int] = None
    timestamp: str


class StalledWorkflow(BaseModel):
    """Info about a stalled workflow"""
    workflow_id: str
    project: str
    activity: str
    stalled_seconds: int
    last_heartbeat: str
    recommendation: str


class CheckStalledRequest(BaseModel):
    """Request to check for stalled workflows"""
    stale_threshold_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Consider stalled if no heartbeat for this many seconds (60-3600)"
    )


class CheckStalledResponse(BaseModel):
    """Response from stalled workflow check"""
    stalled_count: int
    stalled_workflows: List[StalledWorkflow]
    timestamp: str
    recommendation: str


def _activity_record_to_status(activity_record) -> ActivityStatus:
    """Convert internal ActivityRecord to Pydantic ActivityStatus"""
    return ActivityStatus(
        name=activity_record.name,
        state=activity_record.state.value,
        started_at=activity_record.started_at,
        completed_at=activity_record.completed_at,
        last_heartbeat=activity_record.last_heartbeat,
        retry_count=activity_record.retry_count,
        error=activity_record.error,
        duration_ms=activity_record.duration_ms,
        progress=activity_record.progress,
    )


def _workflow_execution_to_status(workflow) -> WorkflowStatus:
    """Convert internal WorkflowExecution to Pydantic WorkflowStatus"""
    return WorkflowStatus(
        workflow_id=workflow.workflow_id,
        project=workflow.project,
        workflow_type=workflow.workflow_type,
        state=workflow.state.value,
        created_at=workflow.created_at,
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
        duration_ms=workflow.duration_ms,
        error=workflow.error,
        activities={
            name: _activity_record_to_status(record)
            for name, record in workflow.activities.items()
        }
    )


async def temporal_health_check() -> HealthSummary:
    """
    GET /api/v17/temporal/health

    Overall Temporal system health check.

    Returns metrics about workflow execution:
    - total_workflows: Total workflows tracked
    - completed: Successfully completed workflows
    - failed: Permanently failed workflows
    - running: Currently executing workflows
    - timed_out: Workflows that exceeded timeout
    - pending: Not yet started workflows
    - success_rate: Percentage of completed vs failed
    - avg_duration_ms: Average execution time

    Example:
        GET /api/v17/temporal/health

    Response:
        {
            "total_workflows": 45,
            "completed": 42,
            "failed": 2,
            "running": 1,
            "timed_out": 0,
            "pending": 0,
            "success_rate": 95.45,
            "avg_duration_ms": 3847,
            "timestamp": "2026-02-12T14:30:22.123456"
        }
    """
    try:
        tracker = get_temporal_tracker()
        health = tracker.get_health_summary()

        return HealthSummary(
            total_workflows=health['total_workflows'],
            completed=health['completed'],
            failed=health['failed'],
            running=health['running'],
            timed_out=health['timed_out'],
            pending=health['pending'],
            success_rate=health['success_rate'],
            avg_duration_ms=health['avg_duration_ms'],
            timestamp=health['timestamp'],
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


async def get_project_workflows(
    project: str,
    limit: int = 50,
    state: Optional[str] = None
) -> Dict[str, Any]:
    """
    GET /api/v17/temporal/workflows/{project}

    Get all workflow runs for a specific project.

    Query parameters:
    - limit: Maximum workflows to return (default 50, max 500)
    - state: Filter by state (PENDING, RUNNING, COMPLETED, FAILED, TIMED_OUT)

    Returns all workflows for the project with their activity states.

    Example:
        GET /api/v17/temporal/workflows/my_project?limit=20&state=COMPLETED

    Response:
        {
            "project": "my_project",
            "total": 20,
            "workflows": [
                {
                    "workflow_id": "wf-my_project-20260212T143022-a1b2c3d4",
                    "workflow_type": "full_pipeline",
                    "state": "COMPLETED",
                    "created_at": "2026-02-12T14:30:22",
                    "started_at": "2026-02-12T14:30:25",
                    "completed_at": "2026-02-12T14:35:12",
                    "duration_ms": 287000,
                    "activities": {
                        "parse_script": {
                            "name": "parse_script",
                            "state": "COMPLETED",
                            "started_at": "2026-02-12T14:30:25",
                            "completed_at": "2026-02-12T14:30:35",
                            "duration_ms": 10000
                        },
                        ...
                    }
                },
                ...
            ]
        }
    """
    try:
        # Validate limit
        limit = min(int(limit) if limit else 50, 500)

        # Parse state filter
        state_filter = None
        if state:
            try:
                state_filter = WorkflowState(state.upper())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid state: {state}. Must be one of: "
                           f"PENDING, RUNNING, COMPLETED, FAILED, TIMED_OUT"
                )

        tracker = get_temporal_tracker()
        workflows = tracker.get_project_workflows(project, limit, state_filter)

        return {
            "project": project,
            "total": len(workflows),
            "workflows": [_workflow_execution_to_status(w) for w in workflows],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflows for {project}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflows: {str(e)}")


async def check_stalled_workflows(
    request: CheckStalledRequest = Body(
        default=CheckStalledRequest(),
        description="Stalled workflow detection parameters"
    )
) -> CheckStalledResponse:
    """
    POST /api/v17/temporal/check-stalled

    Detect workflows that have stalled (no heartbeat in >N seconds).

    Request body:
        {
            "stale_threshold_seconds": 300  // (60-3600, default 300 = 5 minutes)
        }

    Stalled workflows are typically:
    - Generation processes that hung without error
    - Network timeouts that left state dirty
    - Crashed processes that didn't report failure

    Returns detection results and remediation recommendations.

    Example request:
        POST /api/v17/temporal/check-stalled
        {
            "stale_threshold_seconds": 600
        }

    Example response:
        {
            "stalled_count": 2,
            "stalled_workflows": [
                {
                    "workflow_id": "wf-kord-20260212T143022-a1b2c3d4",
                    "project": "kord",
                    "activity": "render_videos",
                    "stalled_seconds": 892,
                    "last_heartbeat": "2026-02-12T14:42:10",
                    "recommendation": "Activity render_videos has no heartbeat for 892s. "
                                     "Consider terminating workflow wf-kord-20260212T143022-a1b2c3d4 and retrying."
                }
            ],
            "timestamp": "2026-02-12T14:51:22.123456",
            "recommendation": "2 workflows stalled. Manual intervention may be needed. "
                             "Review logs and either cancel workflows or diagnose hanging processes."
        }
    """
    try:
        tracker = get_temporal_tracker()
        stalled = tracker.check_stalled_workflows(request.stale_threshold_seconds)

        # Generate recommendation message
        if not stalled:
            recommendation = "All workflows are healthy. No stalled workflows detected."
        elif len(stalled) == 1:
            recommendation = (
                f"1 workflow stalled (threshold: {request.stale_threshold_seconds}s). "
                f"Review the activity logs and consider canceling and retrying the workflow."
            )
        else:
            recommendation = (
                f"{len(stalled)} workflows stalled (threshold: {request.stale_threshold_seconds}s). "
                f"Manual intervention may be needed. Review logs and either cancel workflows or diagnose hanging processes."
            )

        return CheckStalledResponse(
            stalled_count=len(stalled),
            stalled_workflows=[
                StalledWorkflow(
                    workflow_id=item['workflow_id'],
                    project=item['project'],
                    activity=item['activity'],
                    stalled_seconds=item['stalled_seconds'],
                    last_heartbeat=item['last_heartbeat'],
                    recommendation=item['recommendation'],
                )
                for item in stalled
            ],
            timestamp=datetime.now(timezone.utc).isoformat(),  # V17.3: Fixed — was assigning Pydantic FieldInfo
            recommendation=recommendation,
        )
    except Exception as e:
        logger.error(f"Stalled workflow check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


async def get_workflow_detail(workflow_id: str) -> WorkflowStatus:
    """
    GET /api/v17/temporal/workflow/{workflow_id}

    Get detailed status of a specific workflow.

    Returns complete workflow execution state including all activities.

    Example:
        GET /api/v17/temporal/workflow/wf-my_project-20260212T143022-a1b2c3d4

    Response:
        {
            "workflow_id": "wf-my_project-20260212T143022-a1b2c3d4",
            "project": "my_project",
            "workflow_type": "full_pipeline",
            "state": "RUNNING",
            "created_at": "2026-02-12T14:30:22",
            "started_at": "2026-02-12T14:30:25",
            "activities": {
                "parse_script": {"state": "COMPLETED", ...},
                "generate_story_bible": {"state": "COMPLETED", ...},
                "fix_v16_setup": {"state": "COMPLETED", ...},
                "auto_cast": {"state": "RUNNING", "progress": {"progress": 0.65, ...}, ...},
                "generate_first_frames": {"state": "PENDING", ...},
                ...
            }
        }
    """
    try:
        tracker = get_temporal_tracker()
        workflow = tracker.get_workflow(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        return _workflow_execution_to_status(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow: {str(e)}")


def register_temporal_endpoints(app) -> None:
    """
    Register all Temporal endpoints with a FastAPI app.

    Usage in orchestrator_server.py:
        from temporal_api_endpoints import register_temporal_endpoints
        from temporal_workflow_tracker import init_temporal_tracker

        # After app = FastAPI(...)
        tracker = init_temporal_tracker(str(PIPELINE_OUTPUTS_ROOT))
        register_temporal_endpoints(app)

    This registers the following endpoints:
    - GET /api/v17/temporal/health
    - GET /api/v17/temporal/workflows/{project}
    - GET /api/v17/temporal/workflow/{workflow_id}
    - POST /api/v17/temporal/check-stalled
    """
    router = APIRouter(
        prefix="/api/v17/temporal",
        tags=["temporal"],
        responses={
            500: {"description": "Internal server error"},
            404: {"description": "Not found"},
        }
    )

    # Health check endpoint
    @router.get(
        "/health",
        response_model=HealthSummary,
        summary="Temporal system health",
        description="Get overall health metrics for the Temporal workflow orchestration system"
    )
    async def health():
        return await temporal_health_check()

    # Project workflows endpoint
    @router.get(
        "/workflows/{project}",
        response_model=Dict[str, Any],
        summary="Project workflows",
        description="Get all workflow runs for a specific project"
    )
    async def workflows(
        project: str,
        limit: int = 50,
        state: Optional[str] = None
    ):
        return await get_project_workflows(project, limit, state)

    # Specific workflow detail endpoint
    @router.get(
        "/workflow/{workflow_id}",
        response_model=WorkflowStatus,
        summary="Workflow detail",
        description="Get detailed status of a specific workflow execution"
    )
    async def workflow_detail(workflow_id: str):
        return await get_workflow_detail(workflow_id)

    # Stalled workflow detection endpoint
    @router.post(
        "/check-stalled",
        response_model=CheckStalledResponse,
        summary="Check for stalled workflows",
        description="Detect workflows that have not updated for >N seconds"
    )
    async def check_stalled(request: CheckStalledRequest = Body(...)):
        return await check_stalled_workflows(request)

    app.include_router(router)
    logger.info("Registered Temporal workflow orchestration endpoints")
