"""
Temporal.io Pattern Implementation for ATLAS V17 Workflow Orchestration

This module implements Temporal-style durable execution tracking without the SDK.
It provides workflow state management, activity tracking, heartbeat monitoring,
and health checks suitable for upgrading to actual Temporal.io in production.

Key concepts:
- Workflow IDs: Unique identifier per pipeline run (wf-{project}-{timestamp})
- Activities: Individual pipeline steps (parse, story_bible, fix_v16, etc.)
- State Machine: PENDING → RUNNING → COMPLETED/FAILED/TIMED_OUT
- Heartbeats: Periodic status updates during long operations
- History: JSON-based event log (ready for Temporal event store migration)
"""

import json
import threading
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


logger = logging.getLogger(__name__)


class ActivityState(str, Enum):
    """Activity execution states (Temporal-aligned)"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    RETRYING = "RETRYING"


class WorkflowState(str, Enum):
    """Workflow execution states (Temporal-aligned)"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


@dataclass
class ActivityRecord:
    """Single activity execution record"""
    name: str
    state: ActivityState = ActivityState.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['state'] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActivityRecord':
        """Reconstruct from dictionary"""
        data['state'] = ActivityState(data['state'])
        return cls(**data)


@dataclass
class WorkflowExecution:
    """Complete workflow execution record (Temporal-style)"""
    workflow_id: str
    project: str
    workflow_type: str  # e.g., "full_pipeline", "generation_only"
    state: WorkflowState = WorkflowState.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    activities: Dict[str, ActivityRecord] = field(default_factory=dict)
    error: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 3600  # 1 hour default
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'workflow_id': self.workflow_id,
            'project': self.project,
            'workflow_type': self.workflow_type,
            'state': self.state.value,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'activities': {k: v.to_dict() for k, v in self.activities.items()},
            'error': self.error,
            'retry_policy': self.retry_policy,
            'timeout_seconds': self.timeout_seconds,
            'duration_ms': self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowExecution':
        """Reconstruct from dictionary"""
        data['state'] = WorkflowState(data['state'])
        data['activities'] = {
            k: ActivityRecord.from_dict(v)
            for k, v in data.get('activities', {}).items()
        }
        return cls(**data)


class TemporalWorkflowTracker:
    """
    Temporal.io-style workflow execution tracker without SDK dependency.

    Thread-safe, JSON-persisted state management suitable for upgrading to
    actual Temporal.io. Tracks workflow state, activity execution, heartbeats,
    retries, and timing.
    """

    PIPELINE_ACTIVITIES = [
        'parse_script',
        'generate_story_bible',
        'fix_v16_setup',
        'auto_cast',
        'generate_first_frames',
        'render_videos',
        'stitch_final',
    ]

    def __init__(self, pipeline_outputs_root: str):
        """
        Initialize tracker.

        Args:
            pipeline_outputs_root: Root directory for pipeline_outputs/{project}/
        """
        self.pipeline_outputs_root = Path(pipeline_outputs_root)
        self._workflows: Dict[str, WorkflowExecution] = {}
        self._lock = threading.RLock()
        self._heartbeat_threads: Dict[str, threading.Thread] = {}

    def _get_project_history_path(self, project: str) -> Path:
        """Get path to workflow_history.json for project"""
        project_dir = self.pipeline_outputs_root / project
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / "workflow_history.json"

    def _load_project_history(self, project: str) -> List[WorkflowExecution]:
        """Load workflow history from disk for a project"""
        history_path = self._get_project_history_path(project)
        if not history_path.exists():
            return []

        try:
            with open(history_path, 'r') as f:
                data = json.load(f)
                return [WorkflowExecution.from_dict(wf) for wf in data]
        except Exception as e:
            logger.warning(f"Failed to load workflow history for {project}: {e}")
            return []

    def _save_project_history(self, project: str, histories: List[WorkflowExecution]) -> None:
        """Save workflow history to disk (keeps last 100)"""
        history_path = self._get_project_history_path(project)

        try:
            with self._lock:
                # Keep only last 100 entries
                histories = histories[-100:]
                with open(history_path, 'w') as f:
                    json.dump(
                        [wf.to_dict() for wf in histories],
                        f,
                        indent=2
                    )
        except Exception as e:
            logger.error(f"Failed to save workflow history for {project}: {e}")

    def start_workflow(
        self,
        project: str,
        workflow_type: str = "full_pipeline",
        timeout_seconds: int = 3600
    ) -> str:
        """
        Start a new workflow execution.

        Args:
            project: Project name
            workflow_type: Type of workflow (e.g., "full_pipeline", "generation_only")
            timeout_seconds: Workflow timeout in seconds (default 1 hour)

        Returns:
            Workflow ID (e.g., "wf-my_project-20260212T143022-a1b2c3d4")
        """
        with self._lock:
            workflow_id = f"wf-{project}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}-{str(uuid.uuid4())[:8]}"

            workflow = WorkflowExecution(
                workflow_id=workflow_id,
                project=project,
                workflow_type=workflow_type,
                state=WorkflowState.PENDING,
                timeout_seconds=timeout_seconds,
            )

            # Initialize all standard activities as PENDING
            for activity_name in self.PIPELINE_ACTIVITIES:
                workflow.activities[activity_name] = ActivityRecord(name=activity_name)

            self._workflows[workflow_id] = workflow
            logger.info(f"Started workflow {workflow_id} for project {project}")
            return workflow_id

    def run_activity(self, workflow_id: str, activity: str) -> None:
        """
        Mark activity as RUNNING and update workflow state.

        Args:
            workflow_id: Workflow ID from start_workflow()
            activity: Activity name (e.g., "generate_first_frames")
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                logger.warning(f"Workflow {workflow_id} not found")
                return

            # Transition workflow to RUNNING if PENDING
            if workflow.state == WorkflowState.PENDING:
                workflow.state = WorkflowState.RUNNING
                workflow.started_at = datetime.utcnow().isoformat()

            # Mark activity as RUNNING
            if activity in workflow.activities:
                activity_record = workflow.activities[activity]
                activity_record.state = ActivityState.RUNNING
                activity_record.started_at = datetime.utcnow().isoformat()
                activity_record.last_heartbeat = activity_record.started_at

    def heartbeat(
        self,
        workflow_id: str,
        activity: str,
        progress: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record heartbeat during activity execution (no-op safe).

        Used during long-running operations (generation, video rendering).
        Call periodically to indicate activity is still alive.

        Args:
            workflow_id: Workflow ID
            activity: Activity name
            progress: Optional progress data (e.g., {"frames_generated": 12, "total_frames": 20})
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow or activity not in workflow.activities:
                return

            activity_record = workflow.activities[activity]
            activity_record.last_heartbeat = datetime.utcnow().isoformat()
            if progress:
                activity_record.progress = progress

    def complete_activity(
        self,
        workflow_id: str,
        activity: str,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark activity as COMPLETED.

        Args:
            workflow_id: Workflow ID
            activity: Activity name
            result: Optional result data to store
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow or activity not in workflow.activities:
                return

            activity_record = workflow.activities[activity]
            activity_record.state = ActivityState.COMPLETED
            activity_record.completed_at = datetime.utcnow().isoformat()
            activity_record.result = result

            # Calculate duration
            if activity_record.started_at:
                started = datetime.fromisoformat(activity_record.started_at)
                completed = datetime.fromisoformat(activity_record.completed_at)
                activity_record.duration_ms = int((completed - started).total_seconds() * 1000)

            logger.info(f"Completed activity {activity} in workflow {workflow_id}")

    def fail_activity(
        self,
        workflow_id: str,
        activity: str,
        error: str,
        should_retry: bool = True
    ) -> bool:
        """
        Mark activity as FAILED and potentially retry.

        Args:
            workflow_id: Workflow ID
            activity: Activity name
            error: Error message
            should_retry: Whether to retry this activity

        Returns:
            True if activity will be retried, False otherwise
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow or activity not in workflow.activities:
                return False

            activity_record = workflow.activities[activity]
            activity_record.error = error
            activity_record.completed_at = datetime.utcnow().isoformat()

            # Calculate duration
            if activity_record.started_at:
                started = datetime.fromisoformat(activity_record.started_at)
                completed = datetime.fromisoformat(activity_record.completed_at)
                activity_record.duration_ms = int((completed - started).total_seconds() * 1000)

            # Check retry policy
            if should_retry and activity_record.retry_count < activity_record.max_retries:
                activity_record.retry_count += 1
                activity_record.state = ActivityState.RETRYING
                logger.warning(
                    f"Activity {activity} failed (attempt {activity_record.retry_count}/"
                    f"{activity_record.max_retries}): {error}"
                )
                return True
            else:
                activity_record.state = ActivityState.FAILED
                workflow.state = WorkflowState.FAILED
                workflow.error = f"Activity {activity} failed: {error}"
                logger.error(f"Activity {activity} failed permanently: {error}")
                return False

    def complete_workflow(
        self,
        workflow_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark workflow as COMPLETED.

        Args:
            workflow_id: Workflow ID
            result: Optional final result
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return

            workflow.state = WorkflowState.COMPLETED
            workflow.completed_at = datetime.utcnow().isoformat()

            # Calculate total duration
            if workflow.started_at:
                started = datetime.fromisoformat(workflow.started_at)
                completed = datetime.fromisoformat(workflow.completed_at)
                workflow.duration_ms = int((completed - started).total_seconds() * 1000)

            # Persist to history
            histories = self._load_project_history(workflow.project)
            histories.append(workflow)
            self._save_project_history(workflow.project, histories)

            logger.info(f"Completed workflow {workflow_id} in {workflow.duration_ms}ms")

    def timeout_workflow(self, workflow_id: str) -> None:
        """
        Mark workflow as TIMED_OUT.

        Args:
            workflow_id: Workflow ID
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return

            workflow.state = WorkflowState.TIMED_OUT
            workflow.completed_at = datetime.utcnow().isoformat()
            workflow.error = f"Workflow exceeded timeout of {workflow.timeout_seconds}s"

            # Mark running activities as timed out
            for activity_record in workflow.activities.values():
                if activity_record.state == ActivityState.RUNNING:
                    activity_record.state = ActivityState.TIMED_OUT
                    activity_record.completed_at = datetime.utcnow().isoformat()

            logger.error(f"Workflow {workflow_id} timed out")

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowExecution]:
        """
        Get workflow execution details.

        Args:
            workflow_id: Workflow ID

        Returns:
            WorkflowExecution or None
        """
        with self._lock:
            return self._workflows.get(workflow_id)

    def get_project_workflows(
        self,
        project: str,
        limit: int = 50,
        state_filter: Optional[WorkflowState] = None
    ) -> List[WorkflowExecution]:
        """
        Get all workflows for a project.

        Args:
            project: Project name
            limit: Maximum number of workflows to return
            state_filter: Optional state to filter by

        Returns:
            List of WorkflowExecution objects (newest first)
        """
        with self._lock:
            histories = self._load_project_history(project)

            # Add in-memory workflows
            for workflow in self._workflows.values():
                if workflow.project == project:
                    histories.append(workflow)

            # Filter by state
            if state_filter:
                histories = [w for w in histories if w.state == state_filter]

            # Sort by created_at descending
            histories.sort(key=lambda w: w.created_at, reverse=True)

            return histories[:limit]

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get overall Temporal system health.

        Returns:
            Dict with health metrics
        """
        with self._lock:
            all_workflows = list(self._workflows.values())

            completed = sum(1 for w in all_workflows if w.state == WorkflowState.COMPLETED)
            failed = sum(1 for w in all_workflows if w.state == WorkflowState.FAILED)
            running = sum(1 for w in all_workflows if w.state == WorkflowState.RUNNING)
            timed_out = sum(1 for w in all_workflows if w.state == WorkflowState.TIMED_OUT)

            avg_duration_ms = None
            if completed > 0:
                total_duration = sum(w.duration_ms or 0 for w in all_workflows if w.state == WorkflowState.COMPLETED)
                avg_duration_ms = total_duration // completed

            return {
                'total_workflows': len(all_workflows),
                'completed': completed,
                'failed': failed,
                'running': running,
                'timed_out': timed_out,
                'pending': sum(1 for w in all_workflows if w.state == WorkflowState.PENDING),
                'success_rate': (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0,
                'avg_duration_ms': avg_duration_ms,
                'timestamp': datetime.utcnow().isoformat(),
            }

    def check_stalled_workflows(self, stale_threshold_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Detect workflows that have no heartbeat for >N seconds.

        Args:
            stale_threshold_seconds: Consider stalled if no heartbeat for this long (default 5 min)

        Returns:
            List of stalled workflow info dicts
        """
        with self._lock:
            stalled = []
            now = datetime.utcnow()

            for workflow in self._workflows.values():
                if workflow.state not in [WorkflowState.RUNNING]:
                    continue

                for activity_name, activity_record in workflow.activities.items():
                    if activity_record.state != ActivityState.RUNNING:
                        continue

                    if not activity_record.last_heartbeat:
                        continue

                    last_heartbeat = datetime.fromisoformat(activity_record.last_heartbeat)
                    elapsed_seconds = (now - last_heartbeat).total_seconds()

                    if elapsed_seconds > stale_threshold_seconds:
                        stalled.append({
                            'workflow_id': workflow.workflow_id,
                            'project': workflow.project,
                            'activity': activity_name,
                            'stalled_seconds': int(elapsed_seconds),
                            'last_heartbeat': activity_record.last_heartbeat,
                            'recommendation': (
                                f"Activity {activity_name} has no heartbeat for {int(elapsed_seconds)}s. "
                                f"Consider terminating workflow {workflow.workflow_id} and retrying."
                            )
                        })

            return stalled

    def persist_all_workflows(self) -> None:
        """Persist all in-memory workflows to their project histories."""
        with self._lock:
            by_project = {}
            for workflow in self._workflows.values():
                if workflow.project not in by_project:
                    by_project[workflow.project] = []
                by_project[workflow.project].append(workflow)

            for project, workflows in by_project.items():
                histories = self._load_project_history(project)
                for workflow in workflows:
                    # Avoid duplicates
                    histories = [w for w in histories if w.workflow_id != workflow.workflow_id]
                    histories.append(workflow)
                self._save_project_history(project, histories)


# Module-level singleton instance
_tracker_instance: Optional[TemporalWorkflowTracker] = None


def init_temporal_tracker(pipeline_outputs_root: str) -> TemporalWorkflowTracker:
    """
    Initialize the module-level tracker instance.

    Args:
        pipeline_outputs_root: Root directory for pipeline_outputs/

    Returns:
        Tracker instance
    """
    global _tracker_instance
    _tracker_instance = TemporalWorkflowTracker(pipeline_outputs_root)
    return _tracker_instance


def get_temporal_tracker() -> TemporalWorkflowTracker:
    """
    Get the module-level tracker instance.

    Returns:
        Tracker instance (initializes if needed)
    """
    global _tracker_instance
    if _tracker_instance is None:
        # Default initialization
        _tracker_instance = TemporalWorkflowTracker("/tmp/atlas_pipeline_outputs")
    return _tracker_instance


# High-level convenience functions


def temporal_start_workflow(project: str, workflow_type: str = "full_pipeline") -> str:
    """
    Start a new workflow. Call at the beginning of any pipeline operation.

    Args:
        project: Project name
        workflow_type: Type of workflow

    Returns:
        Workflow ID to pass to other temporal_* functions
    """
    tracker = get_temporal_tracker()
    return tracker.start_workflow(project, workflow_type)


def temporal_run_activity(workflow_id: str, activity: str) -> None:
    """
    Mark activity as RUNNING. Call when activity starts.

    Args:
        workflow_id: Workflow ID from temporal_start_workflow()
        activity: Activity name
    """
    tracker = get_temporal_tracker()
    tracker.run_activity(workflow_id, activity)


def temporal_heartbeat(
    workflow_id: str,
    activity: str,
    progress: Optional[Dict[str, Any]] = None
) -> None:
    """
    Record heartbeat during long operation. Safe to call frequently.

    Args:
        workflow_id: Workflow ID
        activity: Activity name
        progress: Optional progress data
    """
    if not workflow_id:  # Graceful degradation
        return
    tracker = get_temporal_tracker()
    tracker.heartbeat(workflow_id, activity, progress)


def temporal_complete_activity(
    workflow_id: str,
    activity: str,
    result: Optional[Dict[str, Any]] = None
) -> None:
    """
    Mark activity as COMPLETED. Call when activity finishes successfully.

    Args:
        workflow_id: Workflow ID
        activity: Activity name
        result: Optional result data
    """
    if not workflow_id:  # Graceful degradation
        return
    tracker = get_temporal_tracker()
    tracker.complete_activity(workflow_id, activity, result)


def temporal_fail_activity(
    workflow_id: str,
    activity: str,
    error: str,
    should_retry: bool = True
) -> bool:
    """
    Mark activity as FAILED. Call when activity fails.

    Args:
        workflow_id: Workflow ID
        activity: Activity name
        error: Error message
        should_retry: Whether to retry

    Returns:
        True if activity will be retried, False if permanently failed
    """
    if not workflow_id:  # Graceful degradation
        return False
    tracker = get_temporal_tracker()
    return tracker.fail_activity(workflow_id, activity, error, should_retry)


def temporal_complete_workflow(
    workflow_id: str,
    result: Optional[Dict[str, Any]] = None
) -> None:
    """
    Mark workflow as COMPLETED. Call at end of pipeline.

    Args:
        workflow_id: Workflow ID
        result: Optional final result
    """
    if not workflow_id:  # Graceful degradation
        return
    tracker = get_temporal_tracker()
    tracker.complete_workflow(workflow_id, result)


def temporal_sentry_bridge(
    workflow_id: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Report workflow failures to Sentry with full workflow context.

    Integrates with existing Sentry instrumentation in orchestrator_server.py.
    This is a no-op if Sentry is not configured.

    Args:
        workflow_id: Workflow ID
        error: Exception that occurred
        context: Optional additional context
    """
    try:
        import sentry_sdk

        tracker = get_temporal_tracker()
        workflow = tracker.get_workflow(workflow_id)

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("workflow_id", workflow_id)
            if workflow:
                scope.set_context("workflow", {
                    'project': workflow.project,
                    'workflow_type': workflow.workflow_type,
                    'state': workflow.state.value,
                    'duration_ms': workflow.duration_ms,
                })

                # Add activity status
                for activity_name, activity_record in workflow.activities.items():
                    scope.set_context(f"activity_{activity_name}", {
                        'state': activity_record.state.value,
                        'retry_count': activity_record.retry_count,
                        'duration_ms': activity_record.duration_ms,
                    })

            if context:
                scope.set_context("workflow_error_context", context)

            sentry_sdk.capture_exception(error)
    except ImportError:
        # Sentry not installed, graceful degradation
        logger.debug(f"Sentry not available for workflow {workflow_id} error reporting")
    except Exception as e:
        # Any error in Sentry bridge should not break the pipeline
        logger.warning(f"Failed to report workflow error to Sentry: {e}")
