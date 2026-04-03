"""
APPROVAL GATE SYSTEM - V17 Factory

Per-scene approval gates for mass workflow automation.
Projects run autonomously until human judgment is required.

Gates:
1. INGEST - Script parsed correctly
2. CAST - Characters mapped to actors
3. FRAMES - First frames generated (PER-SCENE approval)
4. VIDEOS - Videos generated (PER-SCENE approval)
5. STITCH - Final output ready

Usage:
    from atlas_agents.approval_gate import ApprovalGate

    gate = ApprovalGate("kord_v17")
    gate.check_and_update()  # Returns current status
    gate.approve_scene("001", "FRAMES")  # Approve specific scene
    gate.approve_stage("FRAMES")  # Approve all pending
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NOT_READY = "NOT_READY"


class ApprovalStage(Enum):
    INGEST = "INGEST"
    CAST = "CAST"
    FRAMES = "FRAMES"
    VIDEOS = "VIDEOS"
    STITCH = "STITCH"
    COMPLETE = "COMPLETE"


class ApprovalGate:
    """Manages approval state for a project."""

    def __init__(self, project: str, repo_root: Path = None):
        if repo_root is None:
            repo_root = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

        self.project = project
        self.repo_root = Path(repo_root)
        self.project_path = self.repo_root / "pipeline_outputs" / project
        self.state_path = self.project_path / "approval_state.json"

        # Load or create state
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load approval state from file or create default."""
        if self.state_path.exists():
            with open(self.state_path) as f:
                return json.load(f)

        # Default state
        return {
            "project": self.project,
            "version": "v17",
            "status": ApprovalStatus.NOT_READY.value,
            "current_stage": ApprovalStage.INGEST.value,
            "required_by": "SYSTEM",
            "reasons": [],
            "human_tasks": [],

            # Per-scene approval tracking
            "scene_approvals": {},  # scene_id -> {stage: status}

            # Global stage approvals
            "stage_approvals": {
                ApprovalStage.INGEST.value: ApprovalStatus.NOT_READY.value,
                ApprovalStage.CAST.value: ApprovalStatus.NOT_READY.value,
                ApprovalStage.FRAMES.value: ApprovalStatus.NOT_READY.value,
                ApprovalStage.VIDEOS.value: ApprovalStatus.NOT_READY.value,
                ApprovalStage.STITCH.value: ApprovalStatus.NOT_READY.value,
            },

            "timestamps": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }

    def _save_state(self) -> None:
        """Save approval state to file."""
        self.state["timestamps"]["updated_at"] = datetime.now().isoformat()
        self.project_path.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_status(self) -> Dict:
        """Get current approval status."""
        return {
            "project": self.project,
            "status": self.state["status"],
            "current_stage": self.state["current_stage"],
            "stage_approvals": self.state["stage_approvals"],
            "scene_approvals": self.state.get("scene_approvals", {}),
            "human_tasks": self.state.get("human_tasks", []),
            "reasons": self.state.get("reasons", [])
        }

    def get_scene_ids(self) -> List[str]:
        """Get list of scene IDs from shot_plan."""
        shot_plan_path = self.project_path / "shot_plan.json"
        if not shot_plan_path.exists():
            return []

        with open(shot_plan_path) as f:
            shot_plan = json.load(f)

        scene_ids = set()
        for shot in shot_plan.get("shots", []):
            scene_id = shot.get("scene_id", "")
            if scene_id:
                scene_ids.add(scene_id)

        return sorted(list(scene_ids))

    def check_and_update(self) -> Dict:
        """
        Check project state and update approval status.
        Returns current status with any pending human tasks.
        """
        scene_ids = self.get_scene_ids()

        # Initialize scene approvals if needed
        if not self.state.get("scene_approvals"):
            self.state["scene_approvals"] = {}

        for scene_id in scene_ids:
            if scene_id not in self.state["scene_approvals"]:
                self.state["scene_approvals"][scene_id] = {
                    ApprovalStage.FRAMES.value: ApprovalStatus.NOT_READY.value,
                    ApprovalStage.VIDEOS.value: ApprovalStatus.NOT_READY.value
                }

        # Check each stage
        self._check_ingest_stage()
        self._check_cast_stage()
        self._check_frames_stage()
        self._check_videos_stage()
        self._check_stitch_stage()

        # Determine overall status
        self._update_overall_status()

        self._save_state()
        return self.get_status()

    def _check_ingest_stage(self) -> None:
        """Check if script ingestion is complete."""
        story_bible_path = self.project_path / "story_bible.json"
        shot_plan_path = self.project_path / "shot_plan.json"

        if story_bible_path.exists() and shot_plan_path.exists():
            # Check for beats preservation
            with open(story_bible_path) as f:
                sb = json.load(f)

            scenes = sb.get("scenes", [])
            scenes_with_beats = [s for s in scenes if s.get("beats")]

            if scenes and len(scenes_with_beats) == 0:
                self.state["stage_approvals"][ApprovalStage.INGEST.value] = ApprovalStatus.REJECTED.value
                self.state["reasons"].append("Beats stripped during ingestion")
            else:
                self.state["stage_approvals"][ApprovalStage.INGEST.value] = ApprovalStatus.APPROVED.value
        else:
            self.state["stage_approvals"][ApprovalStage.INGEST.value] = ApprovalStatus.NOT_READY.value

    def _check_cast_stage(self) -> None:
        """Check if casting is complete."""
        cast_map_path = self.project_path / "cast_map.json"

        if not cast_map_path.exists():
            self.state["stage_approvals"][ApprovalStage.CAST.value] = ApprovalStatus.NOT_READY.value
            return

        with open(cast_map_path) as f:
            cast_map = json.load(f)

        # Check for reference URLs
        entries = [k for k in cast_map.keys() if not k.startswith("_")]
        entries_with_refs = [
            k for k, v in cast_map.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("reference_url")
        ]

        if len(entries_with_refs) == len(entries):
            self.state["stage_approvals"][ApprovalStage.CAST.value] = ApprovalStatus.APPROVED.value
        elif entries:
            self.state["stage_approvals"][ApprovalStage.CAST.value] = ApprovalStatus.PENDING.value
            self.state["human_tasks"].append(f"Cast missing refs: {len(entries) - len(entries_with_refs)}")
        else:
            self.state["stage_approvals"][ApprovalStage.CAST.value] = ApprovalStatus.NOT_READY.value

    def _check_frames_stage(self) -> None:
        """Check first frames status per scene."""
        first_frames_dir = self.project_path / "first_frames"
        shot_plan_path = self.project_path / "shot_plan.json"

        if not first_frames_dir.exists() or not shot_plan_path.exists():
            self.state["stage_approvals"][ApprovalStage.FRAMES.value] = ApprovalStatus.NOT_READY.value
            return

        with open(shot_plan_path) as f:
            shot_plan = json.load(f)

        # Group shots by scene
        scene_shots = {}
        for shot in shot_plan.get("shots", []):
            scene_id = shot.get("scene_id", "")
            if scene_id:
                if scene_id not in scene_shots:
                    scene_shots[scene_id] = []
                scene_shots[scene_id].append(shot.get("shot_id"))

        # Check each scene
        pending_scenes = []
        for scene_id, shot_ids in scene_shots.items():
            frames_exist = sum(
                1 for shot_id in shot_ids
                if (first_frames_dir / f"{shot_id}.jpg").exists()
            )

            if frames_exist == 0:
                self.state["scene_approvals"][scene_id][ApprovalStage.FRAMES.value] = ApprovalStatus.NOT_READY.value
            elif frames_exist == len(shot_ids):
                # All frames exist - check if approved
                current = self.state["scene_approvals"].get(scene_id, {}).get(ApprovalStage.FRAMES.value)
                if current not in [ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value]:
                    self.state["scene_approvals"][scene_id][ApprovalStage.FRAMES.value] = ApprovalStatus.PENDING.value
                    pending_scenes.append(scene_id)
            else:
                self.state["scene_approvals"][scene_id][ApprovalStage.FRAMES.value] = ApprovalStatus.PENDING.value
                pending_scenes.append(scene_id)

        # Update global stage status
        scene_statuses = [
            self.state["scene_approvals"].get(sid, {}).get(ApprovalStage.FRAMES.value)
            for sid in scene_shots.keys()
        ]

        if all(s == ApprovalStatus.APPROVED.value for s in scene_statuses):
            self.state["stage_approvals"][ApprovalStage.FRAMES.value] = ApprovalStatus.APPROVED.value
        elif any(s == ApprovalStatus.PENDING.value for s in scene_statuses):
            self.state["stage_approvals"][ApprovalStage.FRAMES.value] = ApprovalStatus.PENDING.value
            self.state["human_tasks"] = [t for t in self.state.get("human_tasks", []) if "frames" not in t.lower()]
            self.state["human_tasks"].append(f"Review frames for {len(pending_scenes)} scene(s)")
        elif all(s == ApprovalStatus.NOT_READY.value for s in scene_statuses):
            self.state["stage_approvals"][ApprovalStage.FRAMES.value] = ApprovalStatus.NOT_READY.value

    def _check_videos_stage(self) -> None:
        """Check video status per scene."""
        videos_dir = self.project_path / "videos"
        shot_plan_path = self.project_path / "shot_plan.json"

        if not videos_dir.exists() or not shot_plan_path.exists():
            self.state["stage_approvals"][ApprovalStage.VIDEOS.value] = ApprovalStatus.NOT_READY.value
            return

        with open(shot_plan_path) as f:
            shot_plan = json.load(f)

        # Group shots by scene
        scene_shots = {}
        for shot in shot_plan.get("shots", []):
            scene_id = shot.get("scene_id", "")
            if scene_id:
                if scene_id not in scene_shots:
                    scene_shots[scene_id] = []
                scene_shots[scene_id].append(shot.get("shot_id"))

        # Check each scene
        pending_scenes = []
        for scene_id, shot_ids in scene_shots.items():
            videos_exist = sum(
                1 for shot_id in shot_ids
                if (videos_dir / f"{shot_id}.mp4").exists()
            )

            if videos_exist == 0:
                self.state["scene_approvals"][scene_id][ApprovalStage.VIDEOS.value] = ApprovalStatus.NOT_READY.value
            elif videos_exist == len(shot_ids):
                current = self.state["scene_approvals"].get(scene_id, {}).get(ApprovalStage.VIDEOS.value)
                if current not in [ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value]:
                    self.state["scene_approvals"][scene_id][ApprovalStage.VIDEOS.value] = ApprovalStatus.PENDING.value
                    pending_scenes.append(scene_id)
            else:
                self.state["scene_approvals"][scene_id][ApprovalStage.VIDEOS.value] = ApprovalStatus.PENDING.value
                pending_scenes.append(scene_id)

        # Update global stage status
        scene_statuses = [
            self.state["scene_approvals"].get(sid, {}).get(ApprovalStage.VIDEOS.value)
            for sid in scene_shots.keys()
        ]

        if all(s == ApprovalStatus.APPROVED.value for s in scene_statuses):
            self.state["stage_approvals"][ApprovalStage.VIDEOS.value] = ApprovalStatus.APPROVED.value
        elif any(s == ApprovalStatus.PENDING.value for s in scene_statuses):
            self.state["stage_approvals"][ApprovalStage.VIDEOS.value] = ApprovalStatus.PENDING.value

    def _check_stitch_stage(self) -> None:
        """Check if stitching is complete."""
        # Stitch stage requires all videos approved first
        if self.state["stage_approvals"][ApprovalStage.VIDEOS.value] != ApprovalStatus.APPROVED.value:
            self.state["stage_approvals"][ApprovalStage.STITCH.value] = ApprovalStatus.NOT_READY.value
            return

        # Check for final output
        # TODO: Check for actual stitched output file
        self.state["stage_approvals"][ApprovalStage.STITCH.value] = ApprovalStatus.PENDING.value

    def _update_overall_status(self) -> None:
        """Update overall project status based on stage approvals."""
        stages = self.state["stage_approvals"]

        # Check if blocked
        if any(s == ApprovalStatus.REJECTED.value for s in stages.values()):
            self.state["status"] = ApprovalStatus.REJECTED.value
            return

        # Check if pending human review
        if any(s == ApprovalStatus.PENDING.value for s in stages.values()):
            self.state["status"] = ApprovalStatus.PENDING.value
            # Find first pending stage
            for stage in ApprovalStage:
                if stages.get(stage.value) == ApprovalStatus.PENDING.value:
                    self.state["current_stage"] = stage.value
                    break
            return

        # Check if all approved
        if all(s == ApprovalStatus.APPROVED.value for s in stages.values()):
            self.state["status"] = ApprovalStatus.APPROVED.value
            self.state["current_stage"] = ApprovalStage.COMPLETE.value
            return

        # Otherwise not ready
        self.state["status"] = ApprovalStatus.NOT_READY.value
        for stage in ApprovalStage:
            if stages.get(stage.value) == ApprovalStatus.NOT_READY.value:
                self.state["current_stage"] = stage.value
                break

    def approve_scene(self, scene_id: str, stage: str, notes: str = "") -> Dict:
        """
        Approve a specific scene at a specific stage.

        Args:
            scene_id: Scene ID to approve
            stage: Stage to approve (FRAMES or VIDEOS)
            notes: Optional approval notes

        Returns:
            Updated status
        """
        if scene_id not in self.state["scene_approvals"]:
            self.state["scene_approvals"][scene_id] = {}

        self.state["scene_approvals"][scene_id][stage] = ApprovalStatus.APPROVED.value

        if notes:
            if "approval_notes" not in self.state:
                self.state["approval_notes"] = []
            self.state["approval_notes"].append({
                "scene_id": scene_id,
                "stage": stage,
                "notes": notes,
                "timestamp": datetime.now().isoformat()
            })

        # Re-check stage status
        self.check_and_update()
        return self.get_status()

    def reject_scene(self, scene_id: str, stage: str, reason: str) -> Dict:
        """
        Reject a specific scene at a specific stage.

        Args:
            scene_id: Scene ID to reject
            stage: Stage to reject
            reason: Rejection reason

        Returns:
            Updated status
        """
        if scene_id not in self.state["scene_approvals"]:
            self.state["scene_approvals"][scene_id] = {}

        self.state["scene_approvals"][scene_id][stage] = ApprovalStatus.REJECTED.value

        if "rejections" not in self.state:
            self.state["rejections"] = []
        self.state["rejections"].append({
            "scene_id": scene_id,
            "stage": stage,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })

        self._save_state()
        return self.get_status()

    def approve_stage(self, stage: str) -> Dict:
        """
        Approve all pending scenes for a stage.

        Args:
            stage: Stage to approve all pending

        Returns:
            Updated status
        """
        for scene_id in self.state["scene_approvals"]:
            if self.state["scene_approvals"][scene_id].get(stage) == ApprovalStatus.PENDING.value:
                self.state["scene_approvals"][scene_id][stage] = ApprovalStatus.APPROVED.value

        self.check_and_update()
        return self.get_status()

    def can_proceed(self) -> bool:
        """Check if project can proceed without human intervention."""
        return self.state["status"] not in [
            ApprovalStatus.PENDING.value,
            ApprovalStatus.REJECTED.value
        ]

    def get_pending_scenes(self, stage: str) -> List[str]:
        """Get list of scenes pending approval for a stage."""
        pending = []
        for scene_id, approvals in self.state["scene_approvals"].items():
            if approvals.get(stage) == ApprovalStatus.PENDING.value:
                pending.append(scene_id)
        return pending


def get_approval_status(project: str) -> Dict:
    """Get approval status for a project."""
    gate = ApprovalGate(project)
    return gate.check_and_update()


def approve_project_scene(project: str, scene_id: str, stage: str, notes: str = "") -> Dict:
    """Approve a scene for a project."""
    gate = ApprovalGate(project)
    return gate.approve_scene(scene_id, stage, notes)


def approve_project_stage(project: str, stage: str) -> Dict:
    """Approve all pending scenes for a stage."""
    gate = ApprovalGate(project)
    return gate.approve_stage(stage)
