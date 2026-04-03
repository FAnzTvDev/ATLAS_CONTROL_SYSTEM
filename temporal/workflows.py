#!/usr/bin/env python3
"""
ATLAS V16.0 - Temporal Workflows
=================================
Durable execution for the ATLAS movie generation pipeline.
Replaces fragile while loops with crash-resilient Temporal workflows.

Key Workflows:
1. EpisodeGenerationWorkflow - Main orchestration workflow
2. ShotRenderWorkflow - Individual shot render with retry
3. ValidationGateWorkflow - Pre-render validation checks

Architecture:
- EditDuet Pattern: Editor (CinematographerAgent) + Critic (DirectorCritic)
- continue_as_new for infinite scale (seasons, episodes)
- Signals for human approval gates
- State persisted in Temporal, not JSON files
"""

from datetime import timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Import activities (will be defined in activities.py)
with workflow.unsafe.imports_passed_through():
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
    )


# =============================================================================
# WORKFLOW INPUT/OUTPUT MODELS
# =============================================================================

@dataclass
class EpisodeGenerationInput:
    """Input for episode generation workflow."""
    project_name: str
    episode_id: Optional[str] = None
    target_runtime_minutes: int = 45
    start_from_shot_index: int = 0  # For resume after crash
    auto_approve: bool = False  # Skip human gates in lab mode
    max_shots_per_run: int = 100  # For continue_as_new


@dataclass
class ShotRenderInput:
    """Input for individual shot render."""
    project_name: str
    shot_id: str
    shot_data: Dict[str, Any]
    render_type: str = "image"  # image, video, omnihuman


@dataclass
class ValidationResult:
    """Result from validation activities."""
    passed: bool
    blocking_issues: List[str]
    warnings: List[str]
    grade: str  # A, B, C, D, F


# =============================================================================
# MAIN EPISODE GENERATION WORKFLOW
# =============================================================================

@workflow.defn
class EpisodeGenerationWorkflow:
    """
    Durable workflow for generating a complete episode.

    Features:
    - Crash-resilient: Resumes at exact shot index on restart
    - EditDuet loop: Cinematographer generates, Director critiques
    - Human approval gates via Temporal Signals
    - continue_as_new for infinite episode runs
    """

    def __init__(self):
        self.current_shot_index = 0
        self.shots_completed = 0
        self.shots_failed = 0
        self.human_approval_pending = False
        self.human_approval_received = False
        self.approval_notes = ""
        self.project_state: Dict[str, Any] = {}
        self.critic_report: Dict[str, Any] = {}

    # =========================================================================
    # SIGNALS - For human interaction
    # =========================================================================

    @workflow.signal
    def signal_human_approval(self, approved: bool, notes: str = ""):
        """Signal from UI when human approves/rejects a gate."""
        self.human_approval_received = True
        self.human_approval_pending = False
        self.approval_notes = notes
        if not approved:
            raise ApplicationError(
                f"Human rejected at shot {self.current_shot_index}: {notes}",
                non_retryable=True
            )

    @workflow.signal
    def signal_skip_to_shot(self, shot_index: int):
        """Signal to skip to a specific shot (for debugging)."""
        self.current_shot_index = shot_index
        workflow.logger.info(f"Skipping to shot index {shot_index}")

    @workflow.signal
    def signal_pause(self):
        """Signal to pause after current shot completes."""
        self.human_approval_pending = True

    # =========================================================================
    # QUERIES - For UI to read state
    # =========================================================================

    @workflow.query
    def query_progress(self) -> Dict[str, Any]:
        """Query current workflow progress."""
        return {
            "current_shot_index": self.current_shot_index,
            "shots_completed": self.shots_completed,
            "shots_failed": self.shots_failed,
            "human_approval_pending": self.human_approval_pending,
            "critic_grade": self.critic_report.get("grade", "N/A"),
            "total_shots": len(self.project_state.get("shots", [])),
        }

    @workflow.query
    def query_critic_report(self) -> Dict[str, Any]:
        """Query latest critic report."""
        return self.critic_report

    # =========================================================================
    # MAIN WORKFLOW RUN
    # =========================================================================

    @workflow.run
    async def run(self, input: EpisodeGenerationInput) -> Dict[str, Any]:
        """
        Main episode generation workflow.

        Flow:
        1. Validate prerequisites (API keys, libraries)
        2. Load project state from PostgreSQL
        3. Run 7 validation gates
        4. For each shot:
           a. Run Cinematographer (generate prompts)
           b. Run Director Critic (validate)
           c. If critic fails, regenerate (max 3 times)
           d. Render image
           e. Render video
           f. Update DB
        5. Human approval gate (if configured)
        6. continue_as_new if more shots remain
        """
        workflow.logger.info(f"Starting EpisodeGenerationWorkflow for {input.project_name}")

        # =====================================================================
        # PHASE 1: PREREQUISITES VALIDATION (Non-retryable on failure)
        # =====================================================================

        prereq_result = await workflow.execute_activity(
            validate_prerequisites,
            args=[input.project_name],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),  # No retry - fail fast
        )

        if not prereq_result.get("valid"):
            raise ApplicationError(
                f"Prerequisites failed: {prereq_result.get('missing')}",
                non_retryable=True  # Don't retry - human must fix
            )

        # =====================================================================
        # PHASE 2: LOAD PROJECT STATE FROM POSTGRESQL
        # =====================================================================

        self.project_state = await workflow.execute_activity(
            load_project_state,
            args=[input.project_name],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        shots = self.project_state.get("shots", [])
        if not shots:
            raise ApplicationError(
                f"No shots found for project {input.project_name}",
                non_retryable=True
            )

        workflow.logger.info(f"Loaded {len(shots)} shots from project state")

        # =====================================================================
        # PHASE 3: PREFLIGHT / 7 VALIDATION GATES
        # =====================================================================

        preflight_result = await workflow.execute_activity(
            run_preflight_check,
            args=[input.project_name, self.project_state],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        if preflight_result.get("blocking_issues"):
            raise ApplicationError(
                f"Preflight failed: {preflight_result['blocking_issues']}",
                non_retryable=True
            )

        # =====================================================================
        # PHASE 4: SHOT GENERATION LOOP (EditDuet Pattern)
        # =====================================================================

        self.current_shot_index = input.start_from_shot_index
        shots_processed_this_run = 0

        while self.current_shot_index < len(shots):
            shot = shots[self.current_shot_index]
            shot_id = shot.get("shot_id", f"shot_{self.current_shot_index}")

            workflow.logger.info(f"Processing shot {self.current_shot_index + 1}/{len(shots)}: {shot_id}")

            # -----------------------------------------------------------------
            # EditDuet Step 1: Cinematographer generates prompt
            # -----------------------------------------------------------------

            cinematographer_result = await workflow.execute_activity(
                run_cinematographer_agent,
                args=[input.project_name, shot, self.project_state],
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                ),
            )

            enhanced_shot = cinematographer_result.get("enhanced_shot", shot)

            # -----------------------------------------------------------------
            # EditDuet Step 2: Director Critic validates
            # -----------------------------------------------------------------

            critic_attempts = 0
            max_critic_attempts = 3

            while critic_attempts < max_critic_attempts:
                self.critic_report = await workflow.execute_activity(
                    run_director_critic,
                    args=[enhanced_shot, self.project_state],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                # Check if critic approves
                if self.critic_report.get("grade") in ["A", "B"]:
                    break

                # Critic found issues - regenerate
                critic_attempts += 1
                workflow.logger.warning(
                    f"Critic grade {self.critic_report.get('grade')} for {shot_id}, "
                    f"attempt {critic_attempts}/{max_critic_attempts}"
                )

                if critic_attempts < max_critic_attempts:
                    # Feed critic notes back to cinematographer for revision
                    cinematographer_result = await workflow.execute_activity(
                        run_cinematographer_agent,
                        args=[
                            input.project_name,
                            shot,
                            self.project_state,
                            self.critic_report.get("notes", [])  # Pass critic feedback
                        ],
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )
                    enhanced_shot = cinematographer_result.get("enhanced_shot", shot)

            # If critic still fails after max attempts, log but continue
            if self.critic_report.get("grade") not in ["A", "B"]:
                workflow.logger.error(
                    f"Shot {shot_id} failed critic after {max_critic_attempts} attempts, "
                    f"proceeding with grade {self.critic_report.get('grade')}"
                )

            # -----------------------------------------------------------------
            # Step 3: Render Image
            # -----------------------------------------------------------------

            image_result = await workflow.execute_activity(
                render_shot_image,
                args=[input.project_name, shot_id, enhanced_shot],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(minutes=2),
                ),
            )

            if not image_result.get("success"):
                self.shots_failed += 1
                workflow.logger.error(f"Image render failed for {shot_id}: {image_result.get('error')}")
                # Continue to next shot rather than failing entire workflow
                self.current_shot_index += 1
                continue

            # -----------------------------------------------------------------
            # Step 4: Render Video
            # -----------------------------------------------------------------

            video_result = await workflow.execute_activity(
                render_shot_video,
                args=[input.project_name, shot_id, enhanced_shot, image_result.get("image_url")],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(minutes=5),
                ),
            )

            # -----------------------------------------------------------------
            # Step 5: Update Database
            # -----------------------------------------------------------------

            await workflow.execute_activity(
                update_shot_in_db,
                args=[
                    input.project_name,
                    shot_id,
                    {
                        "image_url": image_result.get("image_url"),
                        "video_url": video_result.get("video_url"),
                        "status": "complete" if video_result.get("success") else "image_only",
                        "critic_grade": self.critic_report.get("grade"),
                        "enhanced_prompt": enhanced_shot.get("nano_prompt"),
                    }
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            self.shots_completed += 1
            self.current_shot_index += 1
            shots_processed_this_run += 1

            # -----------------------------------------------------------------
            # CRITICAL: Save state after EVERY shot for crash recovery
            # -----------------------------------------------------------------

            await workflow.execute_activity(
                save_project_state,
                args=[input.project_name, {
                    "workflow_checkpoint": {
                        "current_shot_index": self.current_shot_index,
                        "shots_completed": self.shots_completed,
                        "shots_failed": self.shots_failed,
                    },
                    "shot_updates": {
                        shot_id: {
                            "image_url": image_result.get("image_url"),
                            "video_url": video_result.get("video_url"),
                            "status": "complete" if video_result.get("success") else "image_only",
                            "critic_grade": self.critic_report.get("grade"),
                            "last_rendered_at": workflow.now().isoformat(),
                        }
                    }
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            workflow.logger.info(f"Checkpoint saved after shot {shot_id}")

            # -----------------------------------------------------------------
            # Human Approval Gate (if pending)
            # -----------------------------------------------------------------

            if self.human_approval_pending and not input.auto_approve:
                await workflow.execute_activity(
                    notify_human_required,
                    args=[input.project_name, shot_id, "Shot completed - awaiting approval"],
                    start_to_close_timeout=timedelta(seconds=10),
                )

                # Wait for human signal (will sleep with zero resource usage)
                await workflow.wait_condition(lambda: self.human_approval_received)
                self.human_approval_received = False
                self.human_approval_pending = False

            # -----------------------------------------------------------------
            # continue_as_new check (prevent history bloat)
            # -----------------------------------------------------------------

            if shots_processed_this_run >= input.max_shots_per_run:
                workflow.logger.info(
                    f"Processed {shots_processed_this_run} shots, continuing as new workflow"
                )

                # State already saved after each shot, just log
                workflow.logger.info(
                    f"Continuing as new at shot {self.current_shot_index} "
                    f"({self.shots_completed} completed, {self.shots_failed} failed)"
                )

                # Continue as new workflow with updated start index
                workflow.continue_as_new(
                    EpisodeGenerationInput(
                        project_name=input.project_name,
                        episode_id=input.episode_id,
                        target_runtime_minutes=input.target_runtime_minutes,
                        start_from_shot_index=self.current_shot_index,
                        auto_approve=input.auto_approve,
                        max_shots_per_run=input.max_shots_per_run,
                    )
                )

        # =====================================================================
        # PHASE 5: COMPLETION
        # =====================================================================

        workflow.logger.info(
            f"Episode generation complete: {self.shots_completed} completed, "
            f"{self.shots_failed} failed"
        )

        return {
            "status": "complete",
            "project": input.project_name,
            "shots_completed": self.shots_completed,
            "shots_failed": self.shots_failed,
            "total_shots": len(shots),
        }


# =============================================================================
# INDIVIDUAL SHOT RENDER WORKFLOW
# =============================================================================

@workflow.defn
class ShotRenderWorkflow:
    """
    Workflow for rendering a single shot.
    Used for parallel rendering and retries.
    """

    @workflow.run
    async def run(self, input: ShotRenderInput) -> Dict[str, Any]:
        """Render a single shot (image or video)."""

        if input.render_type == "image":
            result = await workflow.execute_activity(
                render_shot_image,
                args=[input.project_name, input.shot_id, input.shot_data],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=5),
                ),
            )
        elif input.render_type == "video":
            result = await workflow.execute_activity(
                render_shot_video,
                args=[
                    input.project_name,
                    input.shot_id,
                    input.shot_data,
                    input.shot_data.get("image_url")
                ],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=10),
                ),
            )
        else:
            raise ApplicationError(f"Unknown render type: {input.render_type}")

        return result


# =============================================================================
# VALIDATION GATE WORKFLOW
# =============================================================================

@workflow.defn
class ValidationGateWorkflow:
    """
    Workflow for running all 7 validation gates.
    Runs as a child workflow before rendering starts.
    """

    @workflow.run
    async def run(self, project_name: str) -> ValidationResult:
        """Run all 7 validation gates."""

        # Gate 1: Prerequisites (API keys, libraries)
        prereq = await workflow.execute_activity(
            validate_prerequisites,
            args=[project_name],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not prereq.get("valid"):
            return ValidationResult(
                passed=False,
                blocking_issues=prereq.get("missing", []),
                warnings=[],
                grade="F"
            )

        # Gate 2-7: Run preflight check (covers all other gates)
        project_state = await workflow.execute_activity(
            load_project_state,
            args=[project_name],
            start_to_close_timeout=timedelta(seconds=60),
        )

        preflight = await workflow.execute_activity(
            run_preflight_check,
            args=[project_name, project_state],
            start_to_close_timeout=timedelta(seconds=120),
        )

        blocking = preflight.get("blocking_issues", [])
        warnings = preflight.get("warnings", [])

        # Determine grade
        if blocking:
            grade = "F"
        elif len(warnings) > 10:
            grade = "D"
        elif len(warnings) > 5:
            grade = "C"
        elif len(warnings) > 0:
            grade = "B"
        else:
            grade = "A"

        return ValidationResult(
            passed=len(blocking) == 0,
            blocking_issues=blocking,
            warnings=warnings,
            grade=grade
        )
