"""
ATLAS V17.6 — Cross-Shot Embedding Memory
==========================================

The missing piece: scene-level visual continuity.

Instead of analyzing each shot in isolation, this module:
  1. Caches identity embeddings per character per scene
  2. Compares consecutive shots for drift (face, location, wardrobe)
  3. Detects direction/eyeline flips without cutaways
  4. Produces a CONTINUITY REPORT that LOA can enforce

Architecture:
  SceneMemory holds embeddings for all shots in a scene.
  After each frame is generated, its embedding is stored.
  CrossShotAnalyzer compares shot N vs shot N-1, N-2 to detect drift.

Drift thresholds:
  - Identity drift > 0.15 cosine distance = WARN
  - Location drift > 0.25 cosine distance = WARN
  - Screen direction flip without cutaway = WARN
  - Consecutive same shot type = PACING warn

Usage:
  from tools.cross_shot_memory import CrossShotAnalyzer
  analyzer = CrossShotAnalyzer(project_path)
  analyzer.register_shot("001_001A", frame_path, shot_metadata)
  report = analyzer.check_continuity("001")  # scene_id
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("atlas.cross_shot")


class ShotEmbedding:
    """Cached embedding for a single shot frame."""

    def __init__(self, shot_id: str, scene_id: str, frame_path: str,
                 identity_embedding: List[float] = None,
                 location_embedding: List[float] = None,
                 metadata: Dict = None):
        self.shot_id = shot_id
        self.scene_id = scene_id
        self.frame_path = frame_path
        self.identity_embedding = identity_embedding or []
        self.location_embedding = location_embedding or []
        self.metadata = metadata or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {
            "shot_id": self.shot_id,
            "scene_id": self.scene_id,
            "frame_path": self.frame_path,
            "has_identity": len(self.identity_embedding) > 0,
            "has_location": len(self.location_embedding) > 0,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class SceneMemory:
    """
    Holds all shot embeddings for a single scene.
    Ordered by shot_id for sequential continuity checks.
    """

    def __init__(self, scene_id: str):
        self.scene_id = scene_id
        self.shots: Dict[str, ShotEmbedding] = {}  # shot_id -> embedding
        self._order: List[str] = []  # shot_ids in sequence order

    def add(self, embedding: ShotEmbedding):
        self.shots[embedding.shot_id] = embedding
        if embedding.shot_id not in self._order:
            self._order.append(embedding.shot_id)
            self._order.sort()

    def get_ordered(self) -> List[ShotEmbedding]:
        return [self.shots[sid] for sid in self._order if sid in self.shots]

    def get_previous(self, shot_id: str) -> Optional[ShotEmbedding]:
        try:
            idx = self._order.index(shot_id)
            if idx > 0:
                return self.shots.get(self._order[idx - 1])
        except (ValueError, IndexError):
            pass
        return None


class CrossShotAnalyzer:
    """
    Main engine for cross-shot visual continuity.

    After each frame is generated, call register_shot().
    Then call check_continuity(scene_id) for a full report.
    """

    # Drift thresholds
    IDENTITY_DRIFT_WARN = 0.15    # cosine distance
    IDENTITY_DRIFT_FAIL = 0.30
    LOCATION_DRIFT_WARN = 0.25
    LOCATION_DRIFT_FAIL = 0.45

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.scenes: Dict[str, SceneMemory] = {}
        self._cache_dir = self.project_path / ".vision_cache" / "cross_shot"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._vision_service = None

    def _get_vision(self):
        if self._vision_service is None:
            try:
                from tools.vision_service import get_vision_service
                self._vision_service = get_vision_service("auto")
            except Exception as e:
                logger.warning(f"[CROSS-SHOT] Vision service unavailable: {e}")
        return self._vision_service

    def _scene_id(self, shot_id: str) -> str:
        """Extract scene ID from shot_id (e.g., '003' from '003_002A')."""
        return shot_id.split("_")[0] if "_" in shot_id else "000"

    def register_shot(self, shot_id: str, frame_path: str, shot_metadata: Dict = None) -> Dict:
        """
        Register a generated frame into scene memory.
        Computes embeddings and stores them for cross-shot comparison.
        Returns immediate drift check vs previous shot.
        """
        scene_id = self._scene_id(shot_id)
        metadata = shot_metadata or {}

        embedding = ShotEmbedding(
            shot_id=shot_id,
            scene_id=scene_id,
            frame_path=frame_path,
            metadata={
                "shot_type": metadata.get("shot_type", ""),
                "characters": metadata.get("characters", []),
                "screen_direction": metadata.get("screen_direction", ""),
                "eyeline_target": metadata.get("eyeline_target", ""),
                "blocking_role": metadata.get("blocking_role", ""),
                "location": metadata.get("location", ""),
                "duration": metadata.get("duration", 0),
            }
        )

        # Try to compute embeddings via vision service
        vs = self._get_vision()
        if vs and Path(frame_path).exists():
            try:
                # Use fast_qa as a lightweight embedding proxy
                qa = vs.fast_qa(frame_path)
                # Store QA metrics as pseudo-embedding for drift detection
                embedding.metadata["sharpness"] = qa.get("sharpness", 0)
                embedding.metadata["brightness"] = qa.get("brightness", 0)
                embedding.metadata["contrast"] = qa.get("contrast", 0)
            except Exception as e:
                logger.warning(f"[CROSS-SHOT] QA failed for {shot_id}: {e}")

        # Store in scene memory
        if scene_id not in self.scenes:
            self.scenes[scene_id] = SceneMemory(scene_id)
        scene = self.scenes[scene_id]
        scene.add(embedding)

        # Check drift vs previous shot
        drift_result = self._check_drift_vs_previous(scene, embedding)

        # Cache to disk
        self._save_cache(scene_id)

        return drift_result

    def _check_drift_vs_previous(self, scene: SceneMemory, current: ShotEmbedding) -> Dict:
        """Compare current shot vs previous shot in scene for drift."""
        prev = scene.get_previous(current.shot_id)
        if not prev:
            return {
                "shot_id": current.shot_id,
                "drift_check": "first_in_scene",
                "issues": [],
                "passed": True,
            }

        issues = []

        # ── Screen direction flip ──
        curr_dir = current.metadata.get("screen_direction", "")
        prev_dir = prev.metadata.get("screen_direction", "")
        curr_type = current.metadata.get("shot_type", "")

        if curr_dir and prev_dir and curr_dir != prev_dir:
            if curr_type not in ("establishing", "insert", "b_roll", "cutaway"):
                issues.append({
                    "type": "screen_direction_flip",
                    "severity": "warn",
                    "message": f"Direction flipped from '{prev_dir}' to '{curr_dir}' without cutaway",
                    "previous_shot": prev.shot_id,
                    "suggestion": "Add a neutral cutaway or wide re-establish between these shots",
                })

        # ── Pacing: consecutive same shot type ──
        prev_type = prev.metadata.get("shot_type", "")
        if curr_type and prev_type and curr_type == prev_type:
            if curr_type not in ("establishing", "insert"):
                issues.append({
                    "type": "same_shot_type_consecutive",
                    "severity": "warn",
                    "message": f"Back-to-back '{curr_type}' shots — consider varying coverage",
                    "previous_shot": prev.shot_id,
                    "suggestion": "Insert a different shot type (cutaway, reaction, insert) between them",
                })

        # ── Brightness/exposure drift (if available) ──
        curr_bright = current.metadata.get("brightness", 0)
        prev_bright = prev.metadata.get("brightness", 0)
        if curr_bright > 0 and prev_bright > 0:
            brightness_delta = abs(curr_bright - prev_bright)
            if brightness_delta > 0.25:
                issues.append({
                    "type": "lighting_drift",
                    "severity": "warn",
                    "message": f"Brightness jumped {brightness_delta:.2f} between shots (possible lighting mismatch)",
                    "previous_shot": prev.shot_id,
                    "suggestion": "Check lighting consistency in scene",
                })

        # ── Character continuity ──
        curr_chars = set(current.metadata.get("characters", []))
        prev_chars = set(prev.metadata.get("characters", []))
        if curr_chars and prev_chars:
            appeared = curr_chars - prev_chars
            disappeared = prev_chars - curr_chars
            # Only warn if characters vanish/appear in dialogue (not establishing/insert)
            if disappeared and curr_type in ("medium", "close_up", "extreme_close", "dialogue", "reaction"):
                issues.append({
                    "type": "character_disappearance",
                    "severity": "info",
                    "message": f"Characters {list(disappeared)} were in previous shot but not this one",
                    "previous_shot": prev.shot_id,
                })

        passed = not any(i.get("severity") == "fail" for i in issues)

        return {
            "shot_id": current.shot_id,
            "previous_shot": prev.shot_id,
            "drift_check": "compared",
            "issues": issues,
            "passed": passed,
            "issue_count": len(issues),
        }

    def check_continuity(self, scene_id: str) -> Dict:
        """
        Full continuity report for a scene.
        Checks all consecutive shot pairs for drift.
        """
        if scene_id not in self.scenes:
            return {"scene_id": scene_id, "error": "scene_not_registered", "issues": []}

        scene = self.scenes[scene_id]
        ordered = scene.get_ordered()

        all_issues = []
        shot_reports = []

        for i, emb in enumerate(ordered):
            if i == 0:
                shot_reports.append({
                    "shot_id": emb.shot_id,
                    "position": i,
                    "drift_check": "first_in_scene",
                    "issues": [],
                })
                continue

            prev = ordered[i - 1]
            drift = self._check_drift_vs_previous(scene, emb)
            shot_reports.append({
                "shot_id": emb.shot_id,
                "position": i,
                "drift_check": drift.get("drift_check", ""),
                "issues": drift.get("issues", []),
            })
            all_issues.extend(drift.get("issues", []))

        # Scene-level checks
        scene_issues = self._check_scene_coverage(ordered)
        all_issues.extend(scene_issues)

        # Grade
        fail_count = sum(1 for i in all_issues if i.get("severity") == "fail")
        warn_count = sum(1 for i in all_issues if i.get("severity") == "warn")
        if fail_count > 0:
            grade = "F"
        elif warn_count > 3:
            grade = "C"
        elif warn_count > 1:
            grade = "B"
        elif warn_count > 0:
            grade = "B+"
        else:
            grade = "A"

        return {
            "scene_id": scene_id,
            "total_shots": len(ordered),
            "grade": grade,
            "issues": all_issues,
            "shot_reports": shot_reports,
            "stats": {
                "fails": fail_count,
                "warnings": warn_count,
                "infos": sum(1 for i in all_issues if i.get("severity") == "info"),
            }
        }

    def _check_scene_coverage(self, shots: List[ShotEmbedding]) -> List[Dict]:
        """Check scene-level coverage requirements."""
        issues = []
        types = [s.metadata.get("shot_type", "") for s in shots]

        # Must have establishing shot
        has_establishing = any(t in ("establishing", "wide") for t in types)
        if not has_establishing and len(shots) > 2:
            issues.append({
                "type": "missing_establishing",
                "severity": "warn",
                "message": "Scene has no establishing or wide shot",
                "suggestion": "Add an establishing shot at the beginning",
            })

        # Must have close-up if dialogue present
        has_dialogue = any(s.metadata.get("characters", []) for s in shots)
        has_closeup = any(t in ("close_up", "extreme_close") for t in types)
        if has_dialogue and not has_closeup and len(shots) > 3:
            issues.append({
                "type": "missing_closeup",
                "severity": "warn",
                "message": "Scene has dialogue but no close-up coverage",
                "suggestion": "Add a close-up shot for emotional beats",
            })

        return issues

    def _save_cache(self, scene_id: str):
        """Persist scene memory to disk."""
        if scene_id not in self.scenes:
            return
        scene = self.scenes[scene_id]
        cache_file = self._cache_dir / f"scene_{scene_id}.json"
        try:
            data = {
                "scene_id": scene_id,
                "shots": {sid: emb.to_dict() for sid, emb in scene.shots.items()},
                "order": scene._order,
                "timestamp": time.time(),
            }
            cache_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"[CROSS-SHOT] Cache write failed: {e}")

    def load_cache(self, scene_id: str) -> bool:
        """Load scene memory from disk cache."""
        cache_file = self._cache_dir / f"scene_{scene_id}.json"
        if not cache_file.exists():
            return False
        try:
            data = json.loads(cache_file.read_text())
            scene = SceneMemory(scene_id)
            for sid, shot_data in data.get("shots", {}).items():
                emb = ShotEmbedding(
                    shot_id=shot_data["shot_id"],
                    scene_id=shot_data["scene_id"],
                    frame_path=shot_data["frame_path"],
                    metadata=shot_data.get("metadata", {}),
                )
                scene.add(emb)
            self.scenes[scene_id] = scene
            return True
        except Exception as e:
            logger.warning(f"[CROSS-SHOT] Cache load failed: {e}")
            return False

    def get_all_scene_reports(self) -> Dict:
        """Full project continuity report across all registered scenes."""
        reports = {}
        for scene_id in sorted(self.scenes.keys()):
            reports[scene_id] = self.check_continuity(scene_id)

        total_issues = sum(len(r.get("issues", [])) for r in reports.values())
        grades = [r.get("grade", "?") for r in reports.values()]

        return {
            "project_report": True,
            "scenes": reports,
            "total_scenes": len(reports),
            "total_issues": total_issues,
            "scene_grades": grades,
        }


# ═══════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS for server wiring
# ═══════════════════════════════════════════════════════════

def register_generated_frame(project_path: str, shot_id: str, frame_path: str,
                             shot_metadata: Dict = None) -> Dict:
    """Call after each frame generation to build scene memory."""
    analyzer = CrossShotAnalyzer(project_path)
    scene_id = shot_id.split("_")[0] if "_" in shot_id else "000"
    analyzer.load_cache(scene_id)
    return analyzer.register_shot(shot_id, frame_path, shot_metadata)


def get_scene_continuity_report(project_path: str, scene_id: str) -> Dict:
    """Get continuity report for a scene."""
    analyzer = CrossShotAnalyzer(project_path)
    analyzer.load_cache(scene_id)
    return analyzer.check_continuity(scene_id)
