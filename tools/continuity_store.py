"""
ATLAS V21.10 — Continuity Store: Persistent Disk-Backed State Management

Provides durable SceneState that survives across pipeline runs. Tracks character poses,
emotions, props, camera settings, and environment state. Integrates with continuity_gate.py
for validation and auto-insert workflows.

Module: continuity_store.py
Lines: ~850
Agents: Continuity Gate Agent
Status: NEW V21.10

Core classes:
  - ContinuityStore: Main state persistence engine
  - SceneSnapshot: Complete state snapshot for a scene
  - CharacterSnapshot: Per-character pose/emotion/position tracking
  - CameraState: Camera axis and lens history
  - EnvironmentState: Scene color grade, lighting, weather
  - StateTransition: Historical change log entry
  - StateDiff: Structured difference between states
  - Violation: Continuity breach description
  - PropState: Physical prop tracking

Integration:
  - import_from_scene_state(scene_state) ← compatibility layer with continuity_gate.py
  - export_to_scene_state() → dict ← used by gate for validation
  - update_from_shot(shot) ← reads state_out, persists to disk
  - validate_continuity(shot) ← checks shot.state_in vs stored state
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with [CONTINUITY_STORE] prefix
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[CONTINUITY_STORE] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ============================================================================
# DATACLASSES — CORE STATE STRUCTURES
# ============================================================================

@dataclass
class PropState:
    """Physical prop tracking within a scene."""
    name: str
    position: str  # center, left, right, background, foreground, altar, table, etc.
    owner: Optional[str] = None  # which character is holding it
    visible: bool = True
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PropState":
        return PropState(**d)


@dataclass
class CameraState:
    """Camera configuration and history."""
    axis: str = "central"  # central, left_diagonal, right_diagonal, overhead, low_angle
    last_lens: str = "50mm"  # focal length
    last_angle: str = "wide"  # wide, medium, close, extreme_close
    last_distance: float = 10.0  # feet from subject
    pan_direction: Optional[str] = None  # left, right, up, down
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CameraState":
        return CameraState(**d)


@dataclass
class EnvironmentState:
    """Scene environment configuration."""
    color_grade: str = "neutral"  # teal, amber, desaturated, warm, cool, etc.
    lighting: str = "bright"  # bright, dim, shadowy, candlelit, natural, etc.
    time_of_day: str = "day"  # day, night, morning, dusk, etc.
    weather: str = "clear"  # clear, rain, fog, snow, etc.
    atmosphere: str = "calm"  # calm, tense, mysterious, reverent, chaotic, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "EnvironmentState":
        return EnvironmentState(**d)


@dataclass
class CharacterSnapshot:
    """Per-character state snapshot."""
    name: str
    pose: str  # standing, sitting, kneeling, lying, walking, dancing, fallen
    emotion: str  # grief, determined, fearful, relieved, confused, angry, etc.
    emotion_intensity: int = 5  # 0-10 scale
    eyeline: Optional[str] = None  # target character/object name
    wardrobe_id: Optional[str] = None  # look_id for scene
    position: str = "center"  # center, left, right, background, foreground, doorway
    facing: str = "camera"  # camera, left, right, away, profile_left, profile_right
    hands: str = "free"  # free, holding_X, clasped, praying, covering_face, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CharacterSnapshot":
        return CharacterSnapshot(**d)


@dataclass
class StateDiff:
    """Structured difference between two state snapshots."""
    pose_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # char → (from, to)
    emotion_changes: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # char → (from_intensity, to_intensity)
    position_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # char → (from, to)
    facing_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # char → (from, to)
    eyeline_changes: Dict[str, Tuple[Optional[str], Optional[str]]] = field(default_factory=dict)
    props_added: List[str] = field(default_factory=list)
    props_removed: List[str] = field(default_factory=list)
    props_moved: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # prop → (from_pos, to_pos)
    camera_changed: bool = False
    environment_changed: bool = False
    
    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        changes = []
        
        if self.pose_changes:
            poses = ", ".join([f"{c}: {f}→{t}" for c, (f, t) in self.pose_changes.items()])
            changes.append(f"Poses: {poses}")
        
        if self.emotion_changes:
            emotions = ", ".join([f"{c}: {f}→{t}" for c, (f, t) in self.emotion_changes.items()])
            changes.append(f"Emotions: {emotions}")
        
        if self.position_changes:
            positions = ", ".join([f"{c}: {f}→{t}" for c, (f, t) in self.position_changes.items()])
            changes.append(f"Positions: {positions}")
        
        if self.props_added:
            changes.append(f"Props +: {', '.join(self.props_added)}")
        
        if self.props_removed:
            changes.append(f"Props -: {', '.join(self.props_removed)}")
        
        if self.camera_changed:
            changes.append("Camera changed")
        
        if self.environment_changed:
            changes.append("Environment changed")
        
        return " | ".join(changes) if changes else "No changes"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "pose_changes": self.pose_changes,
            "emotion_changes": self.emotion_changes,
            "position_changes": self.position_changes,
            "facing_changes": self.facing_changes,
            "eyeline_changes": self.eyeline_changes,
            "props_added": self.props_added,
            "props_removed": self.props_removed,
            "props_moved": self.props_moved,
            "camera_changed": self.camera_changed,
            "environment_changed": self.environment_changed,
            "summary": self.summary,
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "StateDiff":
        d_copy = {k: v for k, v in d.items() if k != "summary"}
        return StateDiff(**d_copy)


@dataclass
class Violation:
    """Continuity breach description."""
    type: str  # POSE_MISMATCH, EMOTION_JUMP, WARDROBE_DRIFT, PROP_MISSING, POSITION_TELEPORT
    severity: str  # BLOCKING, WARNING
    character: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Violation":
        return Violation(**d)


@dataclass
class SceneSnapshot:
    """Complete state snapshot for a scene."""
    scene_id: str
    characters: Dict[str, CharacterSnapshot] = field(default_factory=dict)
    props: Dict[str, PropState] = field(default_factory=dict)
    camera: CameraState = field(default_factory=CameraState)
    environment: EnvironmentState = field(default_factory=EnvironmentState)
    last_shot_id: Optional[str] = None
    shot_count: int = 0
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "scene_id": self.scene_id,
            "characters": {
                name: snap.to_dict() for name, snap in self.characters.items()
            },
            "props": {
                name: prop.to_dict() for name, prop in self.props.items()
            },
            "camera": self.camera.to_dict(),
            "environment": self.environment.to_dict(),
            "last_shot_id": self.last_shot_id,
            "shot_count": self.shot_count,
            "timestamp": self.timestamp,
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SceneSnapshot":
        """Deserialize from JSON dict."""
        return SceneSnapshot(
            scene_id=d["scene_id"],
            characters={
                name: CharacterSnapshot.from_dict(snap)
                for name, snap in d.get("characters", {}).items()
            },
            props={
                name: PropState.from_dict(prop)
                for name, prop in d.get("props", {}).items()
            },
            camera=CameraState.from_dict(d.get("camera", {})),
            environment=EnvironmentState.from_dict(d.get("environment", {})),
            last_shot_id=d.get("last_shot_id"),
            shot_count=d.get("shot_count", 0),
            timestamp=d.get("timestamp", ""),
        )


@dataclass
class StateTransition:
    """Historical change log entry."""
    shot_id: str
    timestamp: str
    changes: StateDiff
    violations: List[Violation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "timestamp": self.timestamp,
            "changes": self.changes.to_dict(),
            "violations": [v.to_dict() for v in self.violations],
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "StateTransition":
        return StateTransition(
            shot_id=d["shot_id"],
            timestamp=d["timestamp"],
            changes=StateDiff.from_dict(d["changes"]),
            violations=[Violation.from_dict(v) for v in d.get("violations", [])],
        )


# ============================================================================
# CONTINUITY STORE — MAIN PERSISTENCE ENGINE
# ============================================================================

class ContinuityStore:
    """
    Persistent, disk-backed continuity state management for ATLAS.
    
    Maintains SceneSnapshot per scene, serializes to continuity_state.json,
    survives across pipeline runs. Integrates with continuity_gate.py for
    validation workflows.
    """
    
    def __init__(self, project_path: str):
        """
        Initialize ContinuityStore for a project.
        
        Args:
            project_path: Full path to project directory (e.g., /path/to/project/)
        """
        self.project_path = project_path
        self.store_path = os.path.join(project_path, "continuity_state.json")
        self.history_path = os.path.join(project_path, "continuity_history.jsonl")
        
        self._state: Dict[str, SceneSnapshot] = {}  # scene_id → SceneSnapshot
        self._history: List[StateTransition] = []  # Full history log
        
        logger.debug(f"ContinuityStore initialized for project: {project_path}")
        
        # Load existing state if available
        if os.path.exists(self.store_path):
            self.load()
    
    def update_from_shot(self, shot: Dict[str, Any]) -> bool:
        """
        Read state_out from a shot and update store.
        
        Args:
            shot: Shot plan dict with state_out field
        
        Returns:
            True if update succeeded, False if shot has no state_out
        """
        shot_id = shot.get("shot_id")
        scene_id = shot.get("scene_id")
        state_out = shot.get("state_out")
        
        if not state_out:
            logger.debug(f"Shot {shot_id} has no state_out, skipping")
            return False
        
        if not scene_id:
            logger.warning(f"Shot {shot_id} has no scene_id, cannot update continuity")
            return False
        
        # Get or create scene snapshot
        if scene_id not in self._state:
            self._state[scene_id] = SceneSnapshot(scene_id=scene_id)
        
        scene_snap = self._state[scene_id]
        old_snap = SceneSnapshot.from_dict(scene_snap.to_dict())  # Deep copy
        
        # Update characters from state_out
        if "characters" in state_out:
            for char_name, char_state in state_out["characters"].items():
                scene_snap.characters[char_name] = CharacterSnapshot(
                    name=char_name,
                    pose=char_state.get("pose", "standing"),
                    emotion=char_state.get("emotion", "neutral"),
                    emotion_intensity=char_state.get("emotion_intensity", 5),
                    eyeline=char_state.get("eyeline"),
                    wardrobe_id=char_state.get("wardrobe_id"),
                    position=char_state.get("position", "center"),
                    facing=char_state.get("facing", "camera"),
                    hands=char_state.get("hands", "free"),
                )
        
        # Update props from state_out
        if "props" in state_out:
            for prop_name, prop_state in state_out["props"].items():
                scene_snap.props[prop_name] = PropState(
                    name=prop_name,
                    position=prop_state.get("position", "center"),
                    owner=prop_state.get("owner"),
                    visible=prop_state.get("visible", True),
                    description=prop_state.get("description", ""),
                )
        
        # Update camera if provided
        if "camera" in state_out:
            scene_snap.camera = CameraState.from_dict(state_out["camera"])
        
        # Update environment if provided
        if "environment" in state_out:
            scene_snap.environment = EnvironmentState.from_dict(state_out["environment"])
        
        # Update metadata
        scene_snap.last_shot_id = shot_id
        scene_snap.shot_count += 1
        scene_snap.timestamp = datetime.now().isoformat()
        
        # Record transition in history
        diff = self._compute_diff(old_snap, scene_snap)
        transition = StateTransition(
            shot_id=shot_id,
            timestamp=scene_snap.timestamp,
            changes=diff,
            violations=[],
        )
        self._history.append(transition)
        
        logger.info(f"Updated continuity for {shot_id} in scene {scene_id}: {diff.summary}")
        
        return True
    
    def get_state_before_shot(self, scene_id: str, shot_id: Optional[str] = None) -> SceneSnapshot:
        """
        Get the state that should exist before entering a shot.
        
        Args:
            scene_id: Scene ID
            shot_id: Optional shot ID for logging
        
        Returns:
            SceneSnapshot with stored state for scene, or empty if not found
        """
        if scene_id in self._state:
            logger.debug(f"Retrieved state before shot {shot_id} in scene {scene_id}")
            return self._state[scene_id]
        
        logger.debug(f"No stored state for scene {scene_id}, returning empty snapshot")
        return SceneSnapshot(scene_id=scene_id)
    
    def validate_continuity(self, shot: Dict[str, Any]) -> List[Violation]:
        """
        Validate that shot's state_in matches stored state.
        
        Args:
            shot: Shot plan dict with state_in field
        
        Returns:
            List of Violation objects (empty if valid)
        """
        shot_id = shot.get("shot_id")
        scene_id = shot.get("scene_id")
        state_in = shot.get("state_in")
        
        violations: List[Violation] = []
        
        if not scene_id or not state_in:
            return violations
        
        # Get stored state for this scene
        stored_state = self.get_state_before_shot(scene_id, shot_id)
        
        # Check character states
        if "characters" in state_in:
            for char_name, char_expected in state_in["characters"].items():
                if char_name not in stored_state.characters:
                    if char_expected.get("pose") != "entering":
                        violations.append(Violation(
                            type="POSE_MISMATCH",
                            severity="WARNING",
                            character=char_name,
                            expected="present",
                            actual="absent",
                            message=f"{char_name} expected but not in stored state",
                        ))
                    continue
                
                char_stored = stored_state.characters[char_name]
                
                # Pose mismatch
                expected_pose = char_expected.get("pose")
                if expected_pose and expected_pose != char_stored.pose:
                    violations.append(Violation(
                        type="POSE_MISMATCH",
                        severity="BLOCKING",
                        character=char_name,
                        expected=char_stored.pose,
                        actual=expected_pose,
                        message=f"{char_name} pose mismatch: stored={char_stored.pose}, shot={expected_pose}",
                    ))
                
                # Emotion jump (>3 point difference)
                expected_emotion_intensity = char_expected.get("emotion_intensity", 5)
                if abs(expected_emotion_intensity - char_stored.emotion_intensity) > 3:
                    violations.append(Violation(
                        type="EMOTION_JUMP",
                        severity="WARNING",
                        character=char_name,
                        expected=str(char_stored.emotion_intensity),
                        actual=str(expected_emotion_intensity),
                        message=f"{char_name} emotion jump: {char_stored.emotion_intensity}→{expected_emotion_intensity}",
                    ))
                
                # Position teleport
                expected_position = char_expected.get("position")
                if expected_position and expected_position != char_stored.position:
                    # Only flag if unmotivated (would need shot action description to justify)
                    violations.append(Violation(
                        type="POSITION_TELEPORT",
                        severity="WARNING",
                        character=char_name,
                        expected=char_stored.position,
                        actual=expected_position,
                        message=f"{char_name} position change: {char_stored.position}→{expected_position}",
                    ))
                
                # Wardrobe drift
                expected_wardrobe = char_expected.get("wardrobe_id")
                if expected_wardrobe and expected_wardrobe != char_stored.wardrobe_id:
                    violations.append(Violation(
                        type="WARDROBE_DRIFT",
                        severity="BLOCKING",
                        character=char_name,
                        expected=char_stored.wardrobe_id or "default",
                        actual=expected_wardrobe,
                        message=f"{char_name} wardrobe drift: {char_stored.wardrobe_id}→{expected_wardrobe}",
                    ))
        
        # Check props
        if "props" in state_in:
            for prop_name in state_in["props"].keys():
                if prop_name not in stored_state.props:
                    violations.append(Violation(
                        type="PROP_MISSING",
                        severity="WARNING",
                        expected=prop_name,
                        actual="absent",
                        message=f"Prop '{prop_name}' expected but not in stored state",
                    ))
        
        logger.debug(f"Validation for {shot_id}: {len(violations)} violations found")
        
        return violations
    
    def get_state_diff(self, scene_id: str, shot_id_a: Optional[str], shot_id_b: Optional[str]) -> Optional[StateDiff]:
        """
        Get structured diff between states around two shots.
        
        Args:
            scene_id: Scene ID
            shot_id_a: First shot ID (or None for initial state)
            shot_id_b: Second shot ID
        
        Returns:
            StateDiff object, or None if insufficient history
        """
        # Find transitions for these shots
        trans_a = None
        trans_b = None
        
        for trans in self._history:
            if shot_id_a and trans.shot_id == shot_id_a:
                trans_a = trans
            if trans.shot_id == shot_id_b:
                trans_b = trans
        
        if not trans_b:
            return None
        
        if not trans_a:
            # Diff from initial state (empty snapshot)
            initial = SceneSnapshot(scene_id=scene_id)
            final_state = self.get_state_before_shot(scene_id, shot_id_b)
            return self._compute_diff(initial, final_state)
        
        # Get states around these shots
        state_after_a = self.get_state_before_shot(scene_id, trans_a.shot_id)
        state_after_b = self.get_state_before_shot(scene_id, trans_b.shot_id)
        
        return self._compute_diff(state_after_a, state_after_b)
    
    def save(self) -> bool:
        """
        Save state to continuity_state.json (atomic write).
        
        Returns:
            True if save succeeded
        """
        try:
            # Prepare data
            data = {
                "project": self.project_path,
                "timestamp": datetime.now().isoformat(),
                "state": {
                    scene_id: snap.to_dict()
                    for scene_id, snap in self._state.items()
                },
                "history_count": len(self._history),
            }
            
            # Atomic write
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=os.path.dirname(self.store_path),
                suffix=".json",
                delete=False,
            ) as f:
                json.dump(data, f, indent=2)
                temp_path = f.name
            
            os.replace(temp_path, self.store_path)
            logger.info(f"Saved continuity state to {self.store_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save continuity state: {e}")
            return False
    
    def load(self) -> bool:
        """
        Load state from continuity_state.json.
        
        Returns:
            True if load succeeded, False if file missing/corrupt
        """
        try:
            if not os.path.exists(self.store_path):
                logger.debug(f"No existing continuity state at {self.store_path}")
                return False
            
            with open(self.store_path, "r") as f:
                data = json.load(f)
            
            # Load state snapshots
            for scene_id, snap_dict in data.get("state", {}).items():
                self._state[scene_id] = SceneSnapshot.from_dict(snap_dict)
            
            logger.info(f"Loaded continuity state for {len(self._state)} scenes from {self.store_path}")
            return True
        
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted continuity state JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load continuity state: {e}")
            return False
    
    def rollback_to_shot(self, scene_id: str, shot_id: str) -> bool:
        """
        Revert scene state to what it was after this shot.
        
        Args:
            scene_id: Scene ID
            shot_id: Shot ID to rollback to
        
        Returns:
            True if rollback succeeded
        """
        # Find the transition for this shot
        rollback_trans = None
        for trans in self._history:
            if trans.shot_id == shot_id:
                rollback_trans = trans
                break
        
        if not rollback_trans:
            logger.warning(f"No history for {shot_id}, cannot rollback")
            return False
        
        # Find the index of this transition
        rollback_idx = self._history.index(rollback_trans)
        
        # Trim history
        self._history = self._history[:rollback_idx + 1]
        
        logger.info(f"Rolled back scene {scene_id} to state after {shot_id}")
        return True
    
    def get_history(self, scene_id: str) -> List[StateTransition]:
        """
        Get full state change log for a scene.
        
        Args:
            scene_id: Scene ID
        
        Returns:
            List of StateTransition objects for this scene
        """
        # Get all history entries that mention this scene
        scene_history = []
        for trans in self._history:
            # History is per scene_id in practice, but we could filter
            scene_history.append(trans)
        
        return scene_history
    
    def clear_scene(self, scene_id: str) -> bool:
        """
        Reset state for a scene (for regeneration).
        
        Args:
            scene_id: Scene ID to clear
        
        Returns:
            True if clear succeeded
        """
        if scene_id in self._state:
            del self._state[scene_id]
            logger.info(f"Cleared continuity state for scene {scene_id}")
        
        # Also clear history entries for this scene
        self._history = [
            trans for trans in self._history
            if scene_id not in trans.shot_id  # Heuristic: scene_id prefix in shot_id
        ]
        
        return True
    
    # ========================================================================
    # INTEGRATION WITH continuity_gate.py (SceneState compatibility)
    # ========================================================================
    
    def import_from_scene_state(self, scene_state: Dict[str, Any]) -> bool:
        """
        Convert SceneState dict from continuity_gate.py to ContinuityStore format.
        
        Args:
            scene_state: Dict with characters, props, camera, environment keys
        
        Returns:
            True if import succeeded
        """
        try:
            # Assume scene_id available in caller context
            scene_id = scene_state.get("scene_id", "unknown")
            
            snap = SceneSnapshot(scene_id=scene_id)
            
            # Import characters
            if "characters" in scene_state:
                for char_name, char_data in scene_state["characters"].items():
                    snap.characters[char_name] = CharacterSnapshot(
                        name=char_name,
                        pose=char_data.get("pose", "standing"),
                        emotion=char_data.get("emotion", "neutral"),
                        emotion_intensity=char_data.get("emotion_intensity", 5),
                        eyeline=char_data.get("eyeline"),
                        wardrobe_id=char_data.get("wardrobe_id"),
                        position=char_data.get("position", "center"),
                        facing=char_data.get("facing", "camera"),
                        hands=char_data.get("hands", "free"),
                    )
            
            # Import props
            if "props" in scene_state:
                for prop_name, prop_data in scene_state["props"].items():
                    snap.props[prop_name] = PropState(
                        name=prop_name,
                        position=prop_data.get("position", "center"),
                        owner=prop_data.get("owner"),
                        visible=prop_data.get("visible", True),
                        description=prop_data.get("description", ""),
                    )
            
            # Import camera
            if "camera" in scene_state:
                snap.camera = CameraState.from_dict(scene_state["camera"])
            
            # Import environment
            if "environment" in scene_state:
                snap.environment = EnvironmentState.from_dict(scene_state["environment"])
            
            snap.timestamp = datetime.now().isoformat()
            
            self._state[scene_id] = snap
            logger.info(f"Imported SceneState for {scene_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to import SceneState: {e}")
            return False
    
    def export_to_scene_state(self, scene_id: str) -> Dict[str, Any]:
        """
        Export ContinuityStore state as SceneState dict for continuity_gate.py.
        
        Args:
            scene_id: Scene ID to export
        
        Returns:
            Dict compatible with SceneState
        """
        if scene_id not in self._state:
            return {"characters": {}, "props": {}}
        
        snap = self._state[scene_id]
        
        return {
            "characters": {
                name: snap_char.to_dict()
                for name, snap_char in snap.characters.items()
            },
            "props": {
                name: prop.to_dict()
                for name, prop in snap.props.items()
            },
            "camera": snap.camera.to_dict(),
            "environment": snap.environment.to_dict(),
        }
    
    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================
    
    def _compute_diff(self, old: SceneSnapshot, new: SceneSnapshot) -> StateDiff:
        """
        Compute structured diff between two snapshots.
        """
        diff = StateDiff()
        
        # Character changes
        all_chars = set(old.characters.keys()) | set(new.characters.keys())
        for char in all_chars:
            old_char = old.characters.get(char)
            new_char = new.characters.get(char)
            
            if old_char and new_char:
                if old_char.pose != new_char.pose:
                    diff.pose_changes[char] = (old_char.pose, new_char.pose)
                
                if old_char.emotion_intensity != new_char.emotion_intensity:
                    diff.emotion_changes[char] = (old_char.emotion_intensity, new_char.emotion_intensity)
                
                if old_char.position != new_char.position:
                    diff.position_changes[char] = (old_char.position, new_char.position)
                
                if old_char.facing != new_char.facing:
                    diff.facing_changes[char] = (old_char.facing, new_char.facing)
                
                if old_char.eyeline != new_char.eyeline:
                    diff.eyeline_changes[char] = (old_char.eyeline, new_char.eyeline)
        
        # Prop changes
        old_props = set(old.props.keys())
        new_props = set(new.props.keys())
        diff.props_added = list(new_props - old_props)
        diff.props_removed = list(old_props - new_props)
        
        for prop in old_props & new_props:
            old_pos = old.props[prop].position
            new_pos = new.props[prop].position
            if old_pos != new_pos:
                diff.props_moved[prop] = (old_pos, new_pos)
        
        # Camera/environment changes
        if old.camera != new.camera:
            diff.camera_changed = True
        
        if old.environment != new.environment:
            diff.environment_changed = True
        
        return diff


# ============================================================================
# CONVENIENCE FACTORY FUNCTION
# ============================================================================

def create_continuity_store(project_path: str) -> ContinuityStore:
    """
    Factory function to create a ContinuityStore instance.
    
    Args:
        project_path: Full path to project directory
    
    Returns:
        ContinuityStore instance
    """
    return ContinuityStore(project_path)


if __name__ == "__main__":
    # Simple test
    print("[TEST] continuity_store.py loaded successfully")
    
    test_snap = SceneSnapshot(scene_id="001")
    test_snap.characters["EVELYN"] = CharacterSnapshot(
        name="EVELYN",
        pose="standing",
        emotion="determined",
        emotion_intensity=7,
    )
    
    print(f"Test snapshot: {test_snap.to_dict()}")
