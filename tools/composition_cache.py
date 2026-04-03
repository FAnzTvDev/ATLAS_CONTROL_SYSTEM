"""
COMPOSITION CACHE — V21.10 Production Module
Identifies shots with identical framing and enables plate reuse
Only generates new LTX motion, not new first frames for matching compositions

ATLAS V21.10 — AAA Production Factory
Sentry DSN: configured | Temporal.io: enabled | Composition Reuse: active

Author: ATLAS Engineering
Created: 2026-03-04
"""

import json
import logging
import os
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, FrozenSet, Tuple
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger = logging.getLogger("atlas.composition_cache")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[COMP_CACHE] %(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ============================================================================
# COMPOSITION KEY DATA STRUCTURE
# ============================================================================

@dataclass(frozen=True)
class CompositionKey:
    """
    Immutable hashable key identifying a unique framing/composition.
    
    Two shots match if ALL fields are identical.
    """
    scene_id: str
    shot_type: str  # establishing, wide, medium, close, mcu, overs, two_shot, pov, etc.
    lens_class: str  # wide (≤35mm), normal (36-65mm), tele (66mm+)
    characters_present: FrozenSet[str]  # sorted, immutable set of character names
    camera_angle: str  # eye_level, low, high
    location: str  # normalized scene location
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "scene_id": self.scene_id,
            "shot_type": self.shot_type,
            "lens_class": self.lens_class,
            "characters_present": sorted(self.characters_present),
            "camera_angle": self.camera_angle,
            "location": self.location,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CompositionKey":
        """Reconstruct from JSON dict."""
        # V30.5: Guard against None data (json.loads("null") → None)
        if data is None:
            data = {}
        return cls(
            scene_id=data.get("scene_id", ""),
            shot_type=data.get("shot_type", ""),
            lens_class=data.get("lens_class", "normal"),
            characters_present=frozenset(data.get("characters_present") or []),
            camera_angle=data.get("camera_angle", "eye_level"),
            location=data.get("location", ""),
        )


# ============================================================================
# CACHE ENTRY DATA STRUCTURE
# ============================================================================

@dataclass
class CacheEntry:
    """
    Metadata for a cached composition frame.
    """
    shot_id: str  # First shot to generate this composition
    frame_path: str  # Local file path
    frame_url: str  # Serving URL
    timestamp: str  # ISO 8601 creation time
    usage_count: int = 0  # How many shots have reused this frame
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Reconstruct from JSON dict."""
        # V30.5: Guard against None data
        if data is None:
            data = {"shot_id": "", "frame_path": "", "frame_url": "",
                    "timestamp": "", "usage_count": 0}
        return cls(**data)


# ============================================================================
# COMPOSITION CACHE — MAIN CLASS
# ============================================================================

class CompositionCache:
    """
    Production-grade composition cache for ATLAS V21.10.
    
    Stores first frames by composition key, enables frame reuse across
    identical framings. Only anchor shots (first in composition group)
    generate new nano-banana frames; others reuse + generate new LTX motion.
    """
    
    def __init__(self, project: str, pipeline_outputs_dir: str = None):
        """
        Initialize composition cache.
        
        Args:
            project: Project name
            pipeline_outputs_dir: Path to pipeline_outputs/ root (optional)
        """
        self.project = project
        self.pipeline_outputs_dir = pipeline_outputs_dir or os.path.expanduser(
            f"~/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs"
        )
        self._cache: Dict[CompositionKey, CacheEntry] = {}
        self._reuse_plan: Dict[str, Optional[str]] = {}  # shot_id → source shot_id (or None)
        self._all_compositions: Dict[CompositionKey, None] = {}  # Track all seen compositions
        
        logger.info(f"Initialized CompositionCache for project '{project}'")
    
    @staticmethod
    def classify_lens(focal_length_mm: Optional[float]) -> str:
        """
        Classify focal length into lens class.
        
        Args:
            focal_length_mm: Focal length in millimeters
            
        Returns:
            "wide" (≤35mm), "normal" (36-65mm), or "tele" (66mm+)
        """
        if focal_length_mm is None:
            return "normal"  # Default to normal
        
        if focal_length_mm <= 35:
            return "wide"
        elif focal_length_mm <= 65:
            return "normal"
        else:
            return "tele"
    
    @staticmethod
    def extract_camera_angle(shot: dict) -> str:
        """
        Extract camera angle from shot data.
        
        Looks for: camera_angle, blocking_role, or infers from shot_type.
        
        Args:
            shot: Shot plan entry
            
        Returns:
            "eye_level", "low", "high"
        """
        # Explicit angle field — V30.5: guard against None value
        if "camera_angle" in shot and shot["camera_angle"] is not None:
            angle = shot["camera_angle"].lower()
            if angle in ("eye_level", "low", "high"):
                return angle
        
        # Infer from shot type
        shot_type = (shot.get("shot_type") or "").lower()
        if "pov" in shot_type or "high" in shot_type:
            return "high"
        if "low" in shot_type or "crane" in shot_type:
            return "low"
        
        return "eye_level"
    
    @staticmethod
    def extract_characters(shot: dict) -> FrozenSet[str]:
        """
        Extract and normalize character list from shot.
        
        Args:
            shot: Shot plan entry
            
        Returns:
            Frozen set of sorted canonical character names
        """
        chars = set()
        
        # From characters array
        if "characters" in shot and isinstance(shot["characters"], list):
            for char in shot["characters"]:
                if char and not char.startswith("_"):
                    chars.add(char)
        
        # From dialogue_text (speaker markers)
        dialogue_text = shot.get("dialogue_text", "") or ""
        # Simple heuristic: "CHARACTER\n" at line starts
        for line in dialogue_text.split("\n"):
            line = line.strip()
            if line and line[0].isupper() and len(line) < 50 and not line.startswith("#"):
                # Looks like a character name
                name = line.rstrip(":")
                if name and not name.startswith(("INT.", "EXT.", "CUT", "ACTION")):
                    chars.add(name)
        
        return frozenset(sorted(chars))
    
    def compute_key(self, shot: dict) -> CompositionKey:
        """
        Compute composition key for a shot.
        
        Args:
            shot: Shot plan entry with scene_id, shot_type, camera_body, lens_specs, etc.
            
        Returns:
            CompositionKey uniquely identifying this framing
        """
        scene_id = shot.get("scene_id", "")
        shot_type = (shot.get("shot_type") or "").lower()
        camera_angle = self.extract_camera_angle(shot)
        location = (shot.get("location") or "").strip()
        characters = self.extract_characters(shot)
        
        # Extract focal length from lens_specs
        focal_length = None
        lens_specs = shot.get("lens_specs") or ""
        if isinstance(lens_specs, str):
            # Try to parse "24mm", "85-135mm", etc.
            try:
                parts = lens_specs.lower().split("-")
                focal_length = float(parts[0].replace("mm", "").strip())
            except (ValueError, IndexError, AttributeError):
                pass
        
        lens_class = self.classify_lens(focal_length)
        
        return CompositionKey(
            scene_id=scene_id,
            shot_type=shot_type,
            lens_class=lens_class,
            characters_present=characters,
            camera_angle=camera_angle,
            location=location,
        )
    
    def lookup(self, shot: dict) -> Optional[CacheEntry]:
        """
        Look up cached frame for shot's composition.
        
        Args:
            shot: Shot plan entry
            
        Returns:
            CacheEntry if matching composition found, else None
        """
        key = self.compute_key(shot)
        entry = self._cache.get(key)
        
        if entry:
            logger.debug(
                f"Cache HIT for shot {shot.get('shot_id')}: "
                f"reusing frame from {entry.shot_id}"
            )
            return entry
        
        logger.debug(
            f"Cache MISS for shot {shot.get('shot_id')}: "
            f"no matching composition in cache"
        )
        return None
    
    def register(self, shot: dict, frame_path: str, frame_url: str) -> None:
        """
        Register a generated frame in cache.
        
        Args:
            shot: Shot plan entry
            frame_path: Local file system path to frame
            frame_url: Serving URL for frame
        """
        key = self.compute_key(shot)
        shot_id = shot.get("shot_id", "unknown")
        
        entry = CacheEntry(
            shot_id=shot_id,
            frame_path=frame_path,
            frame_url=frame_url,
            timestamp=datetime.utcnow().isoformat() + "Z",
            usage_count=0,
        )
        
        self._cache[key] = entry
        logger.info(
            f"Cache REGISTER: {shot_id} composition "
            f"[{key.scene_id}|{key.shot_type}|{key.lens_class}|{key.camera_angle}] "
            f"→ {frame_path}"
        )
    
    def get_reuse_plan(self, shots: List[dict]) -> Dict[str, Optional[str]]:
        """
        Pre-compute which shots can reuse which frames.
        
        Strategy:
        - Group shots by CompositionKey
        - First shot in each group is "anchor" (generates fresh frame)
        - Subsequent shots in same group reuse anchor's frame
        - Idempotent: can be called multiple times safely
        
        Args:
            shots: List of shot plan entries
            
        Returns:
            Dict mapping shot_id → source shot_id (None = generate fresh)
        """
        # Group shots by composition
        groups: Dict[CompositionKey, List[dict]] = defaultdict(list)
        for shot in shots:
            key = self.compute_key(shot)
            groups[key].append(shot)
            self._all_compositions[key] = None  # Track all seen compositions
        
        # Build reuse plan
        plan: Dict[str, Optional[str]] = {}
        
        for key, group in groups.items():
            anchor_shot = group[0]
            anchor_id = anchor_shot.get("shot_id")
            
            logger.info(
                f"Composition group [scene={key.scene_id}|type={key.shot_type}|"
                f"lens={key.lens_class}|angle={key.camera_angle}]: "
                f"{len(group)} shots, anchor={anchor_id}"
            )
            
            for shot in group:
                shot_id = shot.get("shot_id")
                
                if shot is anchor_shot:
                    # Anchor generates fresh
                    plan[shot_id] = None
                    logger.debug(f"  {shot_id}: ANCHOR (generate fresh)")
                else:
                    # Reuser
                    plan[shot_id] = anchor_id
                    logger.debug(f"  {shot_id}: REUSE from {anchor_id}")
        
        self._reuse_plan = plan
        return plan
    
    def apply_reuse_to_shot_plan(
        self,
        shots: List[dict],
        cache_only: bool = False
    ) -> List[dict]:
        """
        Modify shot plan to mark reusable shots.
        
        For each shot where cache has matching composition:
        - Sets `_reuse_frame_from`: source shot_id
        - Sets `_reuse_frame_path`: cached frame path
        - Sets `_skip_nano_generation`: True
        
        Anchor shots (first in composition group) always generate fresh.
        
        Args:
            shots: List of shot plan entries (modified in-place)
            cache_only: If True, only use entries already in self._cache
                       If False, auto-generate reuse plan for ungrouped shots
            
        Returns:
            Modified shots list
        """
        if not cache_only and not self._reuse_plan:
            # Auto-generate reuse plan
            self.get_reuse_plan(shots)
        
        modified_count = 0
        
        for shot in shots:
            shot_id = shot.get("shot_id")
            
            # Check reuse plan
            source_shot_id = self._reuse_plan.get(shot_id)
            
            if source_shot_id is None:
                # Anchor shot — generate fresh
                shot.pop("_reuse_frame_from", None)
                shot.pop("_reuse_frame_path", None)
                shot.pop("_skip_nano_generation", None)
                logger.debug(f"{shot_id}: ANCHOR — generate fresh nano frame")
                continue
            
            # Check if we have cached entry for source
            key = self.compute_key(shot)
            cache_entry = self._cache.get(key)
            
            if cache_entry:
                shot["_reuse_frame_from"] = source_shot_id
                shot["_reuse_frame_path"] = cache_entry.frame_path
                shot["_skip_nano_generation"] = True
                cache_entry.usage_count += 1
                modified_count += 1
                
                logger.info(
                    f"{shot_id}: REUSE frame from {source_shot_id} "
                    f"(usage count: {cache_entry.usage_count})"
                )
            else:
                # No cached entry yet — will generate fresh, populate cache
                logger.debug(
                    f"{shot_id}: Reuse candidate but no cached entry yet "
                    f"(will generate when {source_shot_id} renders)"
                )
        
        logger.info(f"Applied reuse markings to {modified_count} shots")
        return shots
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Persist cache to JSON.
        
        Args:
            path: Output file path (default: pipeline_outputs/{project}/composition_cache.json)
            
        Returns:
            Path where cache was saved
        """
        if path is None:
            path = os.path.join(
                self.pipeline_outputs_dir,
                self.project,
                "composition_cache.json"
            )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Serialize cache
        cache_data = {
            "project": self.project,
            "version": "21.10",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entries": {
                json.dumps(key.to_dict(), sort_keys=True): entry.to_dict()
                for key, entry in self._cache.items()
            },
            "reuse_plan": self._reuse_plan,
        }
        
        # Write atomically
        temp_path = path + ".tmp"
        try:
            with open(temp_path, "w") as f:
                json.dump(cache_data, f, indent=2)
            os.replace(temp_path, path)
            logger.info(f"Saved composition cache to {path} ({len(self._cache)} entries)")
            return path
        except Exception as e:
            logger.error(f"Failed to save composition cache: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def load(self, path: Optional[str] = None) -> None:
        """
        Load cache from JSON.
        
        Args:
            path: Input file path (default: pipeline_outputs/{project}/composition_cache.json)
        """
        if path is None:
            path = os.path.join(
                self.pipeline_outputs_dir,
                self.project,
                "composition_cache.json"
            )
        
        if not os.path.exists(path):
            logger.info(f"No existing cache at {path}")
            return
        
        try:
            with open(path, "r") as f:
                cache_data = json.load(f)
            
            # Deserialize cache entries
            for key_json, entry_data in cache_data.get("entries", {}).items():
                key_dict = json.loads(key_json)
                key = CompositionKey.from_dict(key_dict)
                entry = CacheEntry.from_dict(entry_data)
                self._cache[key] = entry
                self._all_compositions[key] = None
            
            # Restore reuse plan
            self._reuse_plan = cache_data.get("reuse_plan", {})
            
            logger.info(
                f"Loaded composition cache from {path} ({len(self._cache)} entries)"
            )
        except Exception as e:
            logger.error(f"Failed to load composition cache: {e}")
            raise
    
    def stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with:
            - total_shots: number of shots in reuse plan
            - unique_compositions: number of unique framings (cached + planned)
            - reusable_shots: number of shots marked for reuse
            - total_reuses: sum of usage_counts
            - savings_pct: estimated nano-banana savings percentage
            - entries: per-entry breakdown
        """
        total_shots = len(self._reuse_plan)
        # Count both cached and planned compositions
        unique_compositions = len(self._all_compositions) or len(self._cache)
        reusable_shots = sum(1 for v in self._reuse_plan.values() if v is not None)
        total_reuses = sum(entry.usage_count for entry in self._cache.values())
        
        savings_pct = 0.0
        if total_shots > 0:
            savings_pct = (reusable_shots / total_shots) * 100
        
        # Per-entry breakdown
        entries_breakdown = []
        for key, entry in sorted(
            self._cache.items(),
            key=lambda x: x[1].usage_count,
            reverse=True
        ):
            entries_breakdown.append({
                "shot_id": entry.shot_id,
                "composition": key.to_dict(),
                "usage_count": entry.usage_count,
                "timestamp": entry.timestamp,
            })
        
        return {
            "total_shots": total_shots,
            "unique_compositions": unique_compositions,
            "reusable_shots": reusable_shots,
            "total_reuses": total_reuses,
            "savings_pct": round(savings_pct, 1),
            "entries": entries_breakdown,
        }
    
    def invalidate_for_wardrobe_change(
        self,
        character: str,
        scene_id: Optional[str] = None
    ) -> int:
        """
        Flush cache entries when wardrobe changes for a character.
        
        Args:
            character: Character name
            scene_id: If provided, only invalidate entries for this scene
            
        Returns:
            Number of entries invalidated
        """
        to_remove = []
        
        for key in self._cache.keys():
            # Check if character is in this composition
            if character not in key.characters_present:
                continue
            
            # Check scene if specified
            if scene_id and key.scene_id != scene_id:
                continue
            
            to_remove.append(key)
        
        for key in to_remove:
            entry = self._cache.pop(key)
            logger.info(
                f"Invalidated composition entry: {entry.shot_id} "
                f"(wardrobe change: {character})"
            )
        
        return len(to_remove)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def should_reuse(shot: dict) -> bool:
    """
    Check if shot should reuse a cached frame.
    
    Args:
        shot: Shot plan entry
        
    Returns:
        True if shot has _reuse_frame_from marker
    """
    return "_reuse_frame_from" in shot


def get_reuse_source(shot: dict) -> Optional[str]:
    """
    Get the source shot ID for frame reuse.
    
    Args:
        shot: Shot plan entry
        
    Returns:
        Source shot ID, or None if not marked for reuse
    """
    return shot.get("_reuse_frame_from")


def analyze_reuse_opportunities(shots: List[dict]) -> dict:
    """
    Analyze composition grouping to identify reuse opportunities.
    
    Groups shots by CompositionKey, identifies groups with >1 shot.
    
    Args:
        shots: List of shot plan entries
        
    Returns:
        Structured report with:
        - total_shots: number of input shots
        - unique_compositions: number of unique framings
        - groups: array of composition groups
        - savings_estimate: estimated nano-banana calls saved
    """
    groups: Dict[CompositionKey, List[dict]] = defaultdict(list)
    
    for shot in shots:
        key = CompositionKey(
            scene_id=shot.get("scene_id", ""),
            shot_type=(shot.get("shot_type") or "").lower(),
            lens_class=CompositionCache.classify_lens(
                _extract_focal_length(shot)
            ),
            characters_present=CompositionCache.extract_characters(shot),
            camera_angle=CompositionCache.extract_camera_angle(shot),
            location=(shot.get("location") or "").strip(),
        )
        groups[key].append(shot)
    
    # Build report
    reuse_groups = []
    total_reusable = 0
    
    for key, group in sorted(
        groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    ):
        if len(group) > 1:
            # V25.9 DOCTRINE: DRAMATIC EQUIVALENCE BEFORE REUSE
            # Two shots are only reusable when they share the same dramatic intent.
            # Scene/framing/characters alone are insufficient — prompt content,
            # dialogue, and action must also match. Without this check, shots with
            # different dialogue/action get identical frames (classifier drift bug).
            anchor = group[0]
            anchor_prompt = (anchor.get("nano_prompt_final") or anchor.get("nano_prompt", ""))[:200]
            anchor_dialogue = (anchor.get("dialogue_text") or "")[:100]
            truly_reusable = []
            for candidate in group[1:]:
                cand_prompt = (candidate.get("nano_prompt_final") or candidate.get("nano_prompt", ""))[:200]
                cand_dialogue = (candidate.get("dialogue_text") or "")[:100]
                if cand_prompt == anchor_prompt and cand_dialogue == anchor_dialogue:
                    truly_reusable.append(candidate.get("shot_id"))
                else:
                    logger.info(f"[DRAMATIC_EQ] Rejected reuse: {candidate.get('shot_id')} differs from {anchor.get('shot_id')} in prompt/dialogue")
            if truly_reusable:
                reuse_groups.append({
                    "composition": key.to_dict(),
                    "anchor_shot": anchor.get("shot_id"),
                    "reuse_candidates": truly_reusable,
                    "group_size": 1 + len(truly_reusable),
                    "savings": len(truly_reusable),
                })
                total_reusable += len(truly_reusable)
    
    return {
        "total_shots": len(shots),
        "unique_compositions": len(groups),
        "reuse_groups": reuse_groups,
        "total_reusable_shots": total_reusable,
        "estimated_savings": f"{total_reusable} nano-banana calls out of {len(shots)}",
        "savings_pct": round((total_reusable / len(shots) * 100), 1) if shots else 0,
    }


def _extract_focal_length(shot: dict) -> Optional[float]:
    """Extract focal length in mm from shot data."""
    lens_specs = shot.get("lens_specs") or ""
    if isinstance(lens_specs, str):
        try:
            parts = lens_specs.lower().split("-")
            return float(parts[0].replace("mm", "").strip())
        except (ValueError, IndexError, AttributeError):
            pass
    return None


# ============================================================================
# VERSION & METADATA
# ============================================================================

__version__ = "21.10"
__author__ = "ATLAS Engineering"
__created__ = "2026-03-04"
__description__ = (
    "Production-grade composition cache for ATLAS V21.10. "
    "Identifies shots with identical framing and enables plate reuse."
)

if __name__ == "__main__":
    # Demo usage
    print(f"COMPOSITION CACHE — ATLAS V{__version__}")
    print(f"Created: {__created__} | Author: {__author__}")
    print(__description__)
