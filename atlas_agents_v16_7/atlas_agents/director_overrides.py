"""
Director Overrides System for ATLAS V18.3

The director_overrides.json file is the single source of truth for:
- Shot-level edits (duration, lens, angle, camera, prompts)
- Cast locks (approved casting decisions)
- Approved shots (ready for render)

Director overrides ALWAYS WIN over auto-repair and auto-cast.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class DirectorOverrides:
    """
    Manages director-level overrides for a project.

    Usage:
        director = DirectorOverrides("ravencroft_v17")
        director.override_shot("001_001A", nano_prompt="New prompt...")
        director.lock_cast("EVELYN", actor="Charlotte Beaumont")
        director.approve_shot("001_001A")
        director.save()
    """

    def __init__(self, project: str, repo_root: Path = None):
        self.project = project
        # Better repo_root detection
        if repo_root:
            self.repo_root = Path(repo_root)
        else:
            # Look for FACTORY_SIGNATURE.json to find root
            current = Path(__file__).parent
            while current != current.parent:
                if (current / "FACTORY_SIGNATURE.json").exists():
                    self.repo_root = current
                    break
                current = current.parent
            else:
                # Fallback to cwd
                self.repo_root = Path.cwd()

        self.project_path = self.repo_root / "pipeline_outputs" / project
        self.overrides_path = self.project_path / "director_overrides.json"

        # Load or create
        if self.overrides_path.exists():
            with open(self.overrides_path) as f:
                self.data = json.load(f)
        else:
            self.data = self._create_empty()

    def _create_empty(self) -> Dict:
        return {
            "_meta": {
                "created_at": datetime.now().isoformat(),
                "version": "17.0",
                "project": self.project
            },
            "shot_overrides": {},  # shot_id -> override dict
            "cast_locks": {},  # character_name -> cast decision
            "approved_shots": [],  # list of shot_ids
            "rejected_shots": [],  # shots marked for redo
            "notes": {}  # per-shot notes from director
        }

    def save(self):
        """Save overrides to disk."""
        self.data["_meta"]["updated_at"] = datetime.now().isoformat()
        with open(self.overrides_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    # =========================================================================
    # SHOT OVERRIDES
    # =========================================================================

    def override_shot(self, shot_id: str, **kwargs) -> Dict:
        """
        Override shot parameters. Allowed fields:
        - duration: int (seconds)
        - nano_prompt: str
        - ltx_motion_prompt: str
        - camera_motion: str (static, slow_dolly, etc.)
        - shot_type: str (wide, medium, close-up, etc.)
        - lens: str (24mm, 35mm, 50mm, etc.)
        - emotional_tone: str
        - blocking_notes: str
        """
        if shot_id not in self.data["shot_overrides"]:
            self.data["shot_overrides"][shot_id] = {
                "created_at": datetime.now().isoformat(),
                "history": []
            }

        override = self.data["shot_overrides"][shot_id]

        # Log previous values to history
        for key, value in kwargs.items():
            if key in override and override[key] != value:
                override["history"].append({
                    "field": key,
                    "old_value": override[key],
                    "new_value": value,
                    "timestamp": datetime.now().isoformat()
                })
            override[key] = value

        override["updated_at"] = datetime.now().isoformat()
        return override

    def get_shot_override(self, shot_id: str) -> Optional[Dict]:
        """Get override for a specific shot."""
        return self.data["shot_overrides"].get(shot_id)

    def apply_overrides_to_shot(self, shot: Dict) -> Dict:
        """
        Apply director overrides to a shot dict.
        Director values ALWAYS win over original.
        """
        shot_id = shot.get("shot_id")
        override = self.get_shot_override(shot_id)

        if not override:
            return shot

        # Create a copy with overrides applied
        result = shot.copy()
        for key in ["duration", "nano_prompt", "ltx_motion_prompt", "camera_motion",
                    "shot_type", "lens", "emotional_tone", "blocking_notes"]:
            if key in override:
                result[key] = override[key]
                result[f"_{key}_override"] = True  # Mark as overridden

        return result

    # =========================================================================
    # CAST LOCKS
    # =========================================================================

    def lock_cast(self, character: str, actor: str, actor_id: str = None,
                  reason: str = None) -> Dict:
        """
        Lock a casting decision. Locked casts are not changed by auto-cast.
        """
        self.data["cast_locks"][character.upper()] = {
            "ai_actor": actor,
            "ai_actor_id": actor_id,
            "locked_at": datetime.now().isoformat(),
            "locked_by": "director",
            "reason": reason or "Director approval"
        }
        return self.data["cast_locks"][character.upper()]

    def get_cast_lock(self, character: str) -> Optional[Dict]:
        """Get locked cast for a character."""
        return self.data["cast_locks"].get(character.upper())

    def get_all_cast_locks(self) -> Dict:
        """Get all locked casting decisions."""
        return self.data["cast_locks"]

    def is_cast_locked(self, character: str) -> bool:
        """Check if a character's casting is locked."""
        return character.upper() in self.data["cast_locks"]

    # =========================================================================
    # SHOT APPROVAL
    # =========================================================================

    def approve_shot(self, shot_id: str) -> bool:
        """Mark a shot as approved (ready for video generation)."""
        if shot_id not in self.data["approved_shots"]:
            self.data["approved_shots"].append(shot_id)
        if shot_id in self.data["rejected_shots"]:
            self.data["rejected_shots"].remove(shot_id)
        return True

    def reject_shot(self, shot_id: str, reason: str = None) -> bool:
        """Mark a shot for regeneration."""
        if shot_id not in self.data["rejected_shots"]:
            self.data["rejected_shots"].append(shot_id)
        if shot_id in self.data["approved_shots"]:
            self.data["approved_shots"].remove(shot_id)
        if reason:
            self.add_note(shot_id, f"REJECTED: {reason}")
        return True

    def is_approved(self, shot_id: str) -> bool:
        """Check if a shot is approved."""
        return shot_id in self.data["approved_shots"]

    def get_approved_shots(self) -> List[str]:
        """Get all approved shot IDs."""
        return self.data["approved_shots"]

    def get_rejected_shots(self) -> List[str]:
        """Get all rejected shot IDs."""
        return self.data["rejected_shots"]

    # =========================================================================
    # NOTES
    # =========================================================================

    def add_note(self, shot_id: str, note: str):
        """Add a director note to a shot."""
        if shot_id not in self.data["notes"]:
            self.data["notes"][shot_id] = []
        self.data["notes"][shot_id].append({
            "note": note,
            "timestamp": datetime.now().isoformat()
        })

    def get_notes(self, shot_id: str) -> List[Dict]:
        """Get all notes for a shot."""
        return self.data["notes"].get(shot_id, [])

    # =========================================================================
    # SUMMARY
    # =========================================================================

    def get_summary(self) -> Dict:
        """Get summary of all overrides."""
        return {
            "project": self.project,
            "shot_overrides_count": len(self.data["shot_overrides"]),
            "cast_locks_count": len(self.data["cast_locks"]),
            "approved_shots_count": len(self.data["approved_shots"]),
            "rejected_shots_count": len(self.data["rejected_shots"]),
            "notes_count": sum(len(n) for n in self.data["notes"].values())
        }


# Convenience function for quick access
def load_director_overrides(project: str) -> DirectorOverrides:
    """Load director overrides for a project."""
    return DirectorOverrides(project)
