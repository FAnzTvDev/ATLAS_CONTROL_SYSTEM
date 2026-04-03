"""
ATLAS V24 — PROJECT TRUTH (System Memory / Hippocampus)
========================================================
Single source of truth document per project that persists across runs.
Contains: act outline, character arcs, pacing profile, reward history,
visual anchors, and condensed global context for the LITE synthesizer.

Usage:
  from tools.project_truth import ProjectTruth, generate_project_truth
  truth = ProjectTruth.load(project_path)
  lite_data = truth.get_lite_data_object(shot)
"""

import json
import os
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ActBeat:
    """A major story beat within an act."""
    scene_range: str          # "000-003"
    description: str          # "Establish world, introduce Eleanor"
    emotional_peak: float     # 0.0-1.0 intensity
    pacing: str               # "allegro" / "andante" / "adagio" / "moderato"

@dataclass
class ActOutline:
    """Macro-structure of the film."""
    act_number: int           # 1, 2, 3
    act_name: str             # "Setup", "Rising Action", "Climax"
    scene_range: str          # "000-003"
    tone: str                 # "curiosity tinged with unease"
    beats: List[ActBeat] = field(default_factory=list)

@dataclass
class CharacterArc:
    """Per-character journey across the film."""
    character_name: str
    arc_type: str             # "transformation", "fall", "revelation", "growth"
    arc_positions: Dict[str, str] = field(default_factory=dict)
    # scene_id -> position description: "001": "hopeful arrival", "005": "growing suspicion"
    known_strengths: List[str] = field(default_factory=list)
    # Prompt patterns that score well for this character
    known_weaknesses: List[str] = field(default_factory=list)
    # Prompt patterns that score poorly

@dataclass
class PacingProfile:
    """Genre-derived timing and rhythm targets."""
    genre: str
    default_tempo: str        # "andante"
    scene_tempos: Dict[str, str] = field(default_factory=dict)
    # scene_id -> tempo tag: "000": "adagio", "005": "allegro"
    cut_frequency_targets: Dict[str, float] = field(default_factory=dict)
    # scene_id -> avg seconds per cut
    rhythm_signature: str = ""
    # "slow-burn with sudden bursts", "escalating tension", "steady crescendo"

@dataclass
class RewardEntry:
    """A single reward memory entry."""
    shot_id: str
    prompt_hash: str
    composite_score: float
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    # identity, blocking, rhythm, emotion, environment, fidelity
    model_used: str = ""
    timestamp: str = ""
    is_winning_pattern: bool = False

# ============================================================================
# PROJECT TRUTH DOCUMENT
# ============================================================================

class ProjectTruth:
    """
    The system's hippocampus. Persists across all runs.
    Contains everything the LITE synthesizer needs for Global Perception.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.truth_path = os.path.join(project_path, "ATLAS_PROJECT_TRUTH.json")

        # Core identity
        self.series_title: str = ""
        self.episode_title: str = ""
        self.genre: str = ""
        self.tone: str = ""
        self.visual_style: str = ""
        self.target_audience: str = ""

        # Macro structure
        self.act_outlines: List[ActOutline] = []
        self.total_scenes: int = 0
        self.total_runtime_seconds: int = 0

        # Character journeys
        self.character_arcs: Dict[str, CharacterArc] = {}

        # Pacing
        self.pacing_profile: Optional[PacingProfile] = None

        # Reward memory
        self.reward_history: List[RewardEntry] = []

        # Visual anchors
        self.color_grade_by_scene: Dict[str, str] = {}
        self.location_anchors: Dict[str, str] = {}

        # Meta
        self.version: str = "1.0"
        self.created_at: str = ""
        self.updated_at: str = ""
        self.generation_count: int = 0

    # ── Persistence ──

    def save(self):
        """Save to ATLAS_PROJECT_TRUTH.json (atomic write)."""
        self.updated_at = datetime.utcnow().isoformat()
        data = self._to_dict()
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(self.truth_path))
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.truth_path)

    @classmethod
    def load(cls, project_path: str) -> "ProjectTruth":
        """Load from existing file or create empty."""
        truth = cls(project_path)
        if os.path.exists(truth.truth_path):
            with open(truth.truth_path) as f:
                data = json.load(f)
            truth._from_dict(data)
        return truth

    # ── Global Perception: LITE Data Object ──

    def get_lite_data_object(self, shot: dict) -> dict:
        """
        Build the condensed global context for a single shot.
        This is what gives the LITE synthesizer Global Perception.
        Small enough to fit in any LLM context window.
        """
        scene_id = shot.get("scene_id", "")

        # Act position
        act_position = self._get_act_position(scene_id)

        # Emotional trajectory (previous, current, next scene)
        emotional_trajectory = self._get_emotional_trajectory(scene_id)

        # Scene cards context (prev + next summaries)
        scene_cards = self._get_surrounding_scene_cards(scene_id)

        # Character arc positions for characters in this shot
        char_arcs = {}
        for char_name in shot.get("characters", []):
            arc = self.character_arcs.get(char_name)
            if arc:
                char_arcs[char_name] = {
                    "arc_type": arc.arc_type,
                    "current_position": arc.arc_positions.get(scene_id, "unknown"),
                }

        # Pacing target
        pacing_target = "moderato"
        if self.pacing_profile:
            pacing_target = self.pacing_profile.scene_tempos.get(
                scene_id, self.pacing_profile.default_tempo
            )

        # Scene color grade
        color_grade = self.color_grade_by_scene.get(scene_id, "")

        return {
            "episode_overview": {
                "series": self.series_title,
                "episode": self.episode_title,
                "genre": self.genre,
                "tone": self.tone,
                "visual_style": self.visual_style,
            },
            "act_position": act_position,
            "emotional_trajectory": emotional_trajectory,
            "scene_cards_context": scene_cards,
            "character_arc_positions": char_arcs,
            "pacing_target": pacing_target,
            "color_grade": color_grade,
            "film_progress_pct": self._get_film_progress(scene_id),
        }

    # ── Act Outline Helpers ──

    def _get_act_position(self, scene_id: str) -> dict:
        """Where in the film structure is this scene?"""
        for act in self.act_outlines:
            start, end = self._parse_range(act.scene_range)
            scene_num = int(scene_id) if scene_id.isdigit() else -1
            if start <= scene_num <= end:
                position_in_act = (scene_num - start) / max(1, end - start)
                return {
                    "act": act.act_number,
                    "act_name": act.act_name,
                    "tone": act.tone,
                    "position_in_act": round(position_in_act, 2),
                    "description": f"Act {act.act_number} ({act.act_name}), {int(position_in_act*100)}% through",
                }
        return {"act": 0, "act_name": "unknown", "tone": "", "position_in_act": 0, "description": "unknown position"}

    def _get_emotional_trajectory(self, scene_id: str) -> dict:
        """Previous, current, and next scene emotional intensity."""
        scene_num = int(scene_id) if scene_id.isdigit() else 0
        trajectory = {"previous": 0.5, "current": 0.5, "next": 0.5}

        for act in self.act_outlines:
            for beat in act.beats:
                start, end = self._parse_range(beat.scene_range)
                if start <= scene_num <= end:
                    trajectory["current"] = beat.emotional_peak
                if start <= (scene_num - 1) <= end:
                    trajectory["previous"] = beat.emotional_peak
                if start <= (scene_num + 1) <= end:
                    trajectory["next"] = beat.emotional_peak

        return trajectory

    def _get_surrounding_scene_cards(self, scene_id: str) -> dict:
        """Get summaries of previous and next scenes for context."""
        scene_num = int(scene_id) if scene_id.isdigit() else 0
        cards = {"previous": "", "current": "", "next": ""}

        for act in self.act_outlines:
            for beat in act.beats:
                start, end = self._parse_range(beat.scene_range)
                if start <= scene_num <= end:
                    cards["current"] = beat.description
                if start <= (scene_num - 1) <= end:
                    cards["previous"] = beat.description
                if start <= (scene_num + 1) <= end:
                    cards["next"] = beat.description

        return cards

    def _get_film_progress(self, scene_id: str) -> float:
        """What percentage through the film is this scene?"""
        if self.total_scenes <= 0:
            return 0.0
        scene_num = int(scene_id) if scene_id.isdigit() else 0
        return round(scene_num / max(1, self.total_scenes - 1), 2)

    @staticmethod
    def _parse_range(range_str: str) -> tuple:
        """Parse '000-003' into (0, 3)."""
        parts = range_str.split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        elif len(parts) == 1:
            n = int(parts[0])
            return n, n
        return 0, 0

    # ── Reward Memory ──

    def record_reward(self, shot_id: str, prompt_hash: str, composite_score: float,
                      dimension_scores: dict, model_used: str = ""):
        """Record a generation result for learning."""
        entry = RewardEntry(
            shot_id=shot_id,
            prompt_hash=prompt_hash,
            composite_score=composite_score,
            dimension_scores=dimension_scores,
            model_used=model_used,
            timestamp=datetime.utcnow().isoformat(),
            is_winning_pattern=composite_score >= 0.85,
        )
        self.reward_history.append(entry)

        # Also write to reward_log.jsonl (append-only)
        log_path = os.path.join(self.project_path, "reports", "reward_log.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def get_winning_patterns(self, character_name: str = "") -> List[RewardEntry]:
        """Get all winning prompt patterns, optionally filtered by character."""
        winners = [r for r in self.reward_history if r.is_winning_pattern]
        # TODO: filter by character from prompt hash lookup
        return winners

    def get_failure_patterns(self, threshold: float = 0.50) -> List[RewardEntry]:
        """Get all failing prompt patterns for avoidance."""
        return [r for r in self.reward_history if r.composite_score < threshold]

    # ── Serialization ──

    def _to_dict(self) -> dict:
        return {
            "version": self.version,
            "series_title": self.series_title,
            "episode_title": self.episode_title,
            "genre": self.genre,
            "tone": self.tone,
            "visual_style": self.visual_style,
            "target_audience": self.target_audience,
            "total_scenes": self.total_scenes,
            "total_runtime_seconds": self.total_runtime_seconds,
            "act_outlines": [
                {
                    "act_number": a.act_number,
                    "act_name": a.act_name,
                    "scene_range": a.scene_range,
                    "tone": a.tone,
                    "beats": [asdict(b) for b in a.beats],
                }
                for a in self.act_outlines
            ],
            "character_arcs": {
                name: asdict(arc) for name, arc in self.character_arcs.items()
            },
            "pacing_profile": asdict(self.pacing_profile) if self.pacing_profile else None,
            "color_grade_by_scene": self.color_grade_by_scene,
            "location_anchors": self.location_anchors,
            "reward_history_count": len(self.reward_history),
            "generation_count": self.generation_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def _from_dict(self, data: dict):
        self.version = data.get("version", "1.0")
        self.series_title = data.get("series_title", "")
        self.episode_title = data.get("episode_title", "")
        self.genre = data.get("genre", "")
        self.tone = data.get("tone", "")
        self.visual_style = data.get("visual_style", "")
        self.target_audience = data.get("target_audience", "")
        self.total_scenes = data.get("total_scenes", 0)
        self.total_runtime_seconds = data.get("total_runtime_seconds", 0)
        self.color_grade_by_scene = data.get("color_grade_by_scene", {})
        self.location_anchors = data.get("location_anchors", {})
        self.generation_count = data.get("generation_count", 0)
        self.created_at = data.get("created_at", "")
        self.updated_at = data.get("updated_at", "")

        for ao in data.get("act_outlines", []):
            beats = [ActBeat(**b) for b in ao.get("beats", [])]
            self.act_outlines.append(ActOutline(
                act_number=ao["act_number"],
                act_name=ao["act_name"],
                scene_range=ao["scene_range"],
                tone=ao["tone"],
                beats=beats,
            ))

        for name, arc_data in data.get("character_arcs", {}).items():
            self.character_arcs[name] = CharacterArc(**arc_data)

        pp = data.get("pacing_profile")
        if pp:
            self.pacing_profile = PacingProfile(**pp)


# ============================================================================
# GENERATOR: Auto-create PROJECT_TRUTH from existing project data
# ============================================================================

def generate_project_truth(project_path: str) -> ProjectTruth:
    """
    Auto-generate ATLAS_PROJECT_TRUTH.json from existing project data.
    Uses story_bible, shot_plan, and cast_map to populate the truth document.
    """
    truth = ProjectTruth(project_path)
    truth.created_at = datetime.utcnow().isoformat()

    # Load project data
    bible_path = os.path.join(project_path, "story_bible.json")
    shot_plan_path = os.path.join(project_path, "shot_plan.json")
    cast_map_path = os.path.join(project_path, "cast_map.json")

    bible = {}
    if os.path.exists(bible_path):
        with open(bible_path) as f:
            bible = json.load(f)

    shots = []
    if os.path.exists(shot_plan_path):
        with open(shot_plan_path) as f:
            data = json.load(f)
        shots = data.get("shots", data) if isinstance(data, dict) else data

    cast_map = {}
    if os.path.exists(cast_map_path):
        with open(cast_map_path) as f:
            cast_map = json.load(f)

    # ── Episode overview ──
    truth.series_title = bible.get("series_title", bible.get("title", Path(project_path).name))
    truth.episode_title = bible.get("episode_title", "Episode 1")
    truth.genre = bible.get("genre", "gothic_horror, psychological thriller")
    truth.tone = bible.get("tone", "dark, suspenseful, atmospheric")
    truth.visual_style = bible.get("visual_style", "cinematic, 35mm film grain, period lighting")
    truth.target_audience = bible.get("target_audience", "adult drama viewers")

    # ── Scene count + runtime ──
    scene_ids = sorted(set(s.get("scene_id", "") for s in shots))
    truth.total_scenes = len(scene_ids)
    truth.total_runtime_seconds = sum(s.get("duration", 0) for s in shots)

    # ── Auto-generate act outlines ──
    n_scenes = len(scene_ids)
    if n_scenes > 0:
        # Split into 3 acts: ~25% / ~50% / ~25%
        act1_end = max(1, n_scenes // 4)
        act3_start = n_scenes - max(1, n_scenes // 4)

        act_configs = [
            (1, "Setup", scene_ids[0], scene_ids[min(act1_end, n_scenes-1)],
             "Establish world, introduce characters, set the tone", 0.3, "andante"),
            (2, "Confrontation", scene_ids[min(act1_end+1, n_scenes-1)], scene_ids[min(act3_start-1, n_scenes-1)],
             "Rising tension, complications, midpoint reversal", 0.7, "moderato"),
            (3, "Resolution", scene_ids[min(act3_start, n_scenes-1)], scene_ids[-1],
             "Climax, confrontation, resolution", 0.9, "allegro"),
        ]

        for act_num, act_name, start_scene, end_scene, desc, peak, tempo in act_configs:
            act = ActOutline(
                act_number=act_num,
                act_name=act_name,
                scene_range=f"{start_scene}-{end_scene}",
                tone=truth.tone,
                beats=[ActBeat(
                    scene_range=f"{start_scene}-{end_scene}",
                    description=desc,
                    emotional_peak=peak,
                    pacing=tempo,
                )],
            )
            truth.act_outlines.append(act)

    # ── Character arcs ──
    for char_name, cast_entry in cast_map.items():
        if isinstance(cast_entry, dict) and not cast_entry.get("_is_alias_of"):
            # Find which scenes this character appears in
            char_scenes = sorted(set(
                s.get("scene_id", "") for s in shots
                if char_name in (s.get("characters", []) if isinstance(s.get("characters"), list) else [])
            ))

            arc = CharacterArc(
                character_name=char_name,
                arc_type="transformation",
                arc_positions={sc: f"scene {sc} appearance" for sc in char_scenes},
            )
            truth.character_arcs[char_name] = arc

    # ── Pacing profile ──
    scene_tempos = {}
    for i, sid in enumerate(scene_ids):
        progress = i / max(1, n_scenes - 1)
        if progress < 0.25:
            scene_tempos[sid] = "andante"
        elif progress < 0.5:
            scene_tempos[sid] = "moderato"
        elif progress < 0.75:
            scene_tempos[sid] = "allegro"
        else:
            scene_tempos[sid] = "allegro"

    truth.pacing_profile = PacingProfile(
        genre=truth.genre,
        default_tempo="moderato",
        scene_tempos=scene_tempos,
        cut_frequency_targets={sid: 8.0 for sid in scene_ids},
        rhythm_signature="slow-burn with sudden bursts of intensity",
    )

    # ── Color grades by scene ──
    from tools.atlas_lite_synthesizer import GENRE_COLOR_GRADE, EMOTION_COLOR_GRADE
    genre_key = truth.genre.lower().replace(" ", "_").split(",")[0].strip()
    default_grade = GENRE_COLOR_GRADE.get(genre_key, "balanced natural light")
    for sid in scene_ids:
        truth.color_grade_by_scene[sid] = default_grade

    # Save
    truth.save()
    print(f"[PROJECT TRUTH] Generated for {Path(project_path).name}")
    print(f"  Scenes: {truth.total_scenes}, Runtime: {truth.total_runtime_seconds}s")
    print(f"  Characters: {len(truth.character_arcs)}")
    print(f"  Acts: {len(truth.act_outlines)}")
    print(f"  Saved: {truth.truth_path}")

    return truth


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_path = os.path.join(base, "pipeline_outputs", project)
    truth = generate_project_truth(project_path)
