"""
ATLAS V23 Unified Prompt Builder
Replaces 7-layer enrichment + authority gate + sanitizer with one clean function.

Design Principles:
1. Read ALL data sources ONCE at construction time
2. Build prompts in deterministic order — no conflicting text ever added
3. No stripping needed because nothing conflicting gets added
4. Each section clearly separated and controllable
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


logger = logging.getLogger(__name__)

# V23: Import universal project config — replaces ALL hardcoded character/scene data
from core.project_config import ProjectConfig, get_project_config, GENRE_COLOR_GRADE

# Camera defaults by shot type
CAMERA_DEFAULTS_BY_TYPE = {
    "master": {"lens": "24mm", "style": "static wide establishing"},
    "wide": {"lens": "24mm", "style": "static or slow push"},
    "medium": {"lens": "50mm", "style": "slow push or subtle zoom"},
    "close": {"lens": "85mm", "style": "steady or slow push in"},
    "mcu": {"lens": "85mm", "style": "steady"},
    "insert": {"lens": "135mm", "style": "macro or static detail"},
    "landscape": {"lens": "24mm", "style": "slow pan or static"},
    "broll": {"lens": "35mm", "style": "slow movement or stable"},
}

# Duration constraints by shot type (seconds)
IDEAL_DURATION_BY_TYPE = {
    "master": 4.0,
    "wide": 3.5,
    "medium": 3.0,
    "close": 2.5,
    "mcu": 2.0,
    "insert": 1.5,
    "landscape": 3.0,
    "broll": 3.0,
}

# Gold standard negatives — always applied
GOLD_STANDARD_NEGATIVES = (
    "NO grid, NO collage, NO split screen, NO extra people, "
    "NO morphing faces, NO watermarks, NO text overlays, "
    "NO CGI artifacts, NO visible editing, NO digital glitches"
)

# Environment keywords to strip from chained prompts
ENV_DRIFT_PATTERNS = re.compile(
    r"\b(ritual|chamber|altar|candles?|stone|walls?|manor|corridor|hall|"
    r"chapel|church|tomb|crypt|dungeon|cellar|tower|balcony|staircase|"
    r"garden|courtyard|gate|bridge|forest|clearing|cave|cliff|shore|"
    r"village|tavern|inn|pub|library|study|bedroom|kitchen|parlour|throne)\b",
    re.IGNORECASE
)


class PromptBuilder:
    """
    Unified prompt builder for ATLAS V23.

    Reads all data sources once, builds prompts in deterministic order.
    No conflicting text ever added, no stripping needed.
    """

    def __init__(
        self,
        project_path: Path,
        project_name: Optional[str] = None,
        cast_map: Optional[Dict] = None,
        story_bible: Optional[Dict] = None,
        wardrobe: Optional[Dict] = None,
        extras: Optional[Dict] = None,
        scene_manifest: Optional[Dict] = None,
        project_config: Optional[ProjectConfig] = None,
    ):
        """
        Initialize builder with data sources.

        Args:
            project_path: Path to project directory
            project_name: Project name for config loading (e.g., "ravencroft_v22")
            cast_map: Character data (loaded from cast_map.json if not provided)
            story_bible: Narrative data (loaded from story_bible.json if not provided)
            wardrobe: Wardrobe data (loaded from wardrobe.json if not provided)
            extras: Extras/crowd data (loaded from extras.json if not provided)
            scene_manifest: Scene manifest (loaded from shot_plan.json metadata if not provided)
            project_config: Pre-loaded ProjectConfig (auto-loaded if not provided)
        """
        self.project_path = Path(project_path)

        # V23: Load universal project config (replaces all hardcoded data)
        if project_config:
            self.config = project_config
        elif project_name:
            self.config = get_project_config(project_name)
        else:
            # Infer project name from path
            inferred = self.project_path.name
            self.config = get_project_config(inferred)

        # Use config data, with overrides from explicit params
        self.cast_map = cast_map or self.config.cast_map or self._load_json("cast_map.json")
        self.story_bible = story_bible or self.config.story_bible or self._load_json("story_bible.json")
        self.wardrobe = wardrobe or self._load_json("wardrobe.json")
        self.extras = extras or self._load_json("extras.json")
        self.scene_manifest = scene_manifest or self.config.scene_manifest or self._load_scene_manifest()

        # Build beat index for fast lookup
        self._beat_index = self._build_beat_index()

        logger.info(
            f"PromptBuilder initialized: {len(self.cast_map)} cast, "
            f"{len(self.story_bible.get('scenes', []))} scenes, "
            f"{len(self._beat_index)} beats indexed"
        )

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file from project path, return empty dict if not found."""
        path = self.project_path / "pipeline_outputs" / filename
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        return {}

    def _load_scene_manifest(self) -> Dict:
        """Load scene manifest from shot_plan.json metadata."""
        path = self.project_path / "pipeline_outputs" / "shot_plan.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    return data.get("_scene_manifest", {})
            except Exception as e:
                logger.warning(f"Failed to load scene_manifest: {e}")
        return {}

    def _build_beat_index(self) -> Dict[str, List[Dict]]:
        """
        Build index: scene_id → list of beats in order.
        Used for fast proportional beat lookup.
        """
        index = {}
        for scene in self.story_bible.get("scenes", []):
            scene_id = scene.get("scene_id", "")
            if scene_id:
                index[scene_id] = scene.get("beats", [])
        return index

    def _get_proportional_beat(
        self,
        scene_id: str,
        shot_index: int,
        n_shots_in_scene: int
    ) -> Optional[Dict]:
        """
        Get beat for shot using proportional mapping.

        Maps shots evenly across beats:
        beat_idx = int(shot_index * n_beats / n_shots)

        Args:
            scene_id: Scene identifier
            shot_index: Zero-based shot index within scene
            n_shots_in_scene: Total shots in scene

        Returns:
            Beat dict or None if not found
        """
        beats = self._beat_index.get(scene_id, [])
        if not beats or n_shots_in_scene == 0:
            return None

        beat_idx = int(shot_index * len(beats) / n_shots_in_scene)
        beat_idx = min(beat_idx, len(beats) - 1)  # Clamp to valid range

        return beats[beat_idx] if beat_idx < len(beats) else None

    def _get_character_desc(self, char_name: str) -> Optional[str]:
        """
        Look up canonical character description.

        Uses fuzzy matching: tries exact match, then uppercase, then substring.
        """
        # Exact match
        if char_name in self.config.canonical_characters:
            return self.config.canonical_characters[char_name]["appearance"]

        # Uppercase match
        upper_name = char_name.upper()
        if upper_name in self.config.canonical_characters:
            return self.config.canonical_characters[upper_name]["appearance"]

        # Substring match
        for canon_name, canon_data in self.config.canonical_characters.items():
            if char_name.lower() in canon_name.lower():
                return canon_data["appearance"]

        return None

    def _get_character_negatives(self, char_name: str) -> Optional[str]:
        """Get canonical character negative constraints."""
        # Exact match
        if char_name in self.config.canonical_characters:
            return self.config.canonical_characters[char_name].get("negative", "")

        # Uppercase match
        upper_name = char_name.upper()
        if upper_name in self.config.canonical_characters:
            return self.config.canonical_characters[upper_name].get("negative", "")

        # Substring match
        for canon_name, canon_data in self.config.canonical_characters.items():
            if char_name.lower() in canon_name.lower():
                return canon_data["negative"]

        return None

    def _get_wardrobe_tag(self, char_name: str, scene_id: str) -> Optional[str]:
        """Get wardrobe tag for character in scene."""
        if not self.wardrobe:
            return None

        look_key = f"{char_name}::{scene_id}"
        look = self.wardrobe.get(look_key, {})
        return look.get("wardrobe_tag") or look.get("tag")

    def _get_scene_location(self, scene_id: str) -> Optional[str]:
        """Get location name from scene manifest."""
        manifest = self.scene_manifest.get(scene_id, {})
        return manifest.get("location")

    def _get_color_grade(self, scene_id: str) -> str:
        """Get color grade for scene, fall back to genre default."""
        return self.config.get_color_grade(scene_id)

    def _clamp_duration(
        self,
        duration: float,
        shot_type: str,
        has_dialogue: bool
    ) -> float:
        """Clamp duration to valid range based on shot type."""
        min_dur = 0.5
        max_dur = 8.0

        # Dialogue shots minimum 2s, max 6s
        if has_dialogue:
            min_dur = 2.0
            max_dur = 6.0

        # Extended shots can be longer
        if shot_type in ("master", "establishing"):
            max_dur = 12.0

        return max(min_dur, min(duration, max_dur))

    def _strip_env_from_prompt(self, text: str) -> str:
        """
        Strip environment keywords from text (for chained shots).

        Removes 30+ location nouns that cause room drift when prompts are chained.
        Returns original text if result would be too short.
        """
        result = ENV_DRIFT_PATTERNS.sub("", text)
        result = re.sub(r'\s+', ' ', result).strip()

        # Keep original if result too short
        if len(result) < 10:
            return text

        return result

    def build_prompts(
        self,
        shot: Dict[str, Any],
        scene_id: Optional[str] = None,
        shot_index: int = 0,
        n_shots_in_scene: int = 1,
        is_chained: bool = False,
    ) -> Dict[str, str]:
        """
        Build nano_prompt and ltx_motion_prompt for a shot.

        Deterministic order: lens → characters → beat action → wardrobe → location →
        color grade → emotion → camera → gold standard → negatives.

        Args:
            shot: Shot dict with camera, characters, duration, etc.
            scene_id: Scene identifier (used for wardrobe/location lookups)
            shot_index: Zero-based index of shot within scene
            n_shots_in_scene: Total shots in scene
            is_chained: If True, strip environment words from chained video prompt

        Returns:
            Dict with keys: nano_prompt, ltx_motion_prompt, nano_prompt_final
        """
        # Extract shot data
        shot_id = shot.get("shot_id", "unknown")
        shot_type = shot.get("shot_type", "medium")
        characters = shot.get("characters", [])
        duration = self._clamp_duration(
            shot.get("duration", 3.0),
            shot_type,
            bool(shot.get("dialogue_text"))
        )
        camera_body = shot.get("camera_body", "Arri Alexa Mini LF")
        camera_style = shot.get("camera_style", "static")
        lens_specs = shot.get("lens_specs", "24mm")
        emotion_data = shot.get("emotion_data")
        dialogue_text = shot.get("dialogue_text", "")

        # Get beat for this shot (if scene_id provided)
        beat = None
        if scene_id:
            beat = self._get_proportional_beat(scene_id, shot_index, n_shots_in_scene)

        # Build nano_prompt sections (deterministic order)
        nano_sections = []

        # 1. Lens + Composition
        nano_sections.append(f"Camera: {camera_body} with {lens_specs} lens. {camera_style}.")
        nano_sections.append(f"Shot type: {shot_type}. Framing: {self._get_frame_direction(shot_type)}.")

        # 2. Character descriptions (from project config canonical_characters)
        char_descs = []
        for char in characters:
            desc = self._get_character_desc(char)
            if desc:
                char_descs.append(f"{char}: {desc}")

        if char_descs:
            nano_sections.append("Characters: " + " | ".join(char_descs))

        # 3. Beat action
        if beat:
            action = beat.get("character_action") or beat.get("action") or beat.get("description", "")
            if action:
                nano_sections.append(f"Action: {action}")

        # 4. Wardrobe
        if scene_id:
            wardrobe_tags = []
            for char in characters:
                tag = self._get_wardrobe_tag(char, scene_id)
                if tag:
                    wardrobe_tags.append(f"{char} wearing: {tag}")

            if wardrobe_tags:
                nano_sections.append(". ".join(wardrobe_tags))

        # 5. Location
        if scene_id:
            location = self._get_scene_location(scene_id)
            if location:
                # Get location description from story bible if available
                scene_data = next(
                    (s for s in self.story_bible.get("scenes", []) if s.get("scene_id") == scene_id),
                    {}
                )
                location_desc = scene_data.get("description", "")

                if location_desc:
                    nano_sections.append(f"Location: {location}. {location_desc}")
                else:
                    nano_sections.append(f"Location: {location}")

        # 6. Scene color grade
        if scene_id:
            color_grade = self._get_color_grade(scene_id)
            nano_sections.append(f"Color grade: {color_grade}")

        # 7. Emotion state
        if emotion_data:
            emotion = emotion_data.get("emotion", "")
            if emotion:
                for char in characters:
                    nano_sections.append(f"{char} emotion: {emotion}")

        # 8. Camera direction
        if camera_style:
            nano_sections.append(f"Camera movement: {camera_style}")

        # 9. Gold standard negatives (always last in main prompt)
        nano_sections.append(GOLD_STANDARD_NEGATIVES)

        # 10. Character-specific negatives
        for char in characters:
            negatives = self._get_character_negatives(char)
            if negatives:
                nano_sections.append(negatives)

        # Join with period + space for readability
        nano_prompt = ". ".join(filter(None, nano_sections))
        if not nano_prompt.endswith("."):
            nano_prompt += "."

        # Optionally strip environment for chained shots
        nano_prompt_final = (
            self._strip_env_from_prompt(nano_prompt) if is_chained else nano_prompt
        )

        # Build ltx_motion_prompt sections
        ltx_sections = []

        # 1. Timing
        ltx_sections.append(f"0-2s opening motion, 2-{duration:.1f}s main action")

        # 2. Character action (from beat)
        if beat:
            action = beat.get("character_action") or beat.get("description", "")
            if action:
                for char in characters:
                    ltx_sections.append(f"{char} performs: {action}")

        # 3. Dialogue marker
        if dialogue_text and characters:
            speaker = characters[0]  # Primary speaker
            dialogue_short = dialogue_text[:100]
            ltx_sections.append(f"{speaker} speaks: {dialogue_short}")

        # 4. Wardrobe continuity
        if scene_id and characters:
            for char in characters:
                ltx_sections.append(f"wardrobe continuity: {char} same outfit throughout")

        # 5. Face stability
        if characters:
            ltx_sections.append("face stable NO morphing, character consistent")
        else:
            # No-character guard
            ltx_sections.append("NO morphing, NO face generation, environment only")

        # 6. Atmosphere
        if scene_id:
            color_grade = self._get_color_grade(scene_id)
            ltx_sections.append(f"atmosphere: {color_grade}")
        else:
            ltx_sections.append(f"atmosphere: {self.config.get_color_grade(scene_id)}")

        ltx_motion_prompt = ". ".join(filter(None, ltx_sections))
        if not ltx_motion_prompt.endswith("."):
            ltx_motion_prompt += "."

        return {
            "nano_prompt": nano_prompt,
            "ltx_motion_prompt": ltx_motion_prompt,
            "nano_prompt_final": nano_prompt_final,
        }

    def _get_frame_direction(self, shot_type: str) -> str:
        """Get frame direction text for shot type."""
        directions = {
            "master": "wide establishing, full scene composition",
            "wide": "wide shot, see geography and blocking",
            "medium": "medium shot, see from waist up",
            "close": "close-up, see facial expression",
            "mcu": "medium close-up, see chest and face",
            "insert": "detail shot, macro on object",
            "landscape": "environmental, no characters",
            "broll": "B-roll insert, environmental detail",
            "establishing": "wide establishing shot",
        }
        return directions.get(shot_type, "medium shot")

    def enrich_all_shots(
        self,
        shots: List[Dict[str, Any]],
        scene_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run build_prompts on all shots, return enrichment statistics.

        Args:
            shots: List of shot dicts
            scene_id: Optional scene filter (if provided, only enrich this scene)

        Returns:
            Dict with enrichment results and statistics
        """
        results = {
            "shots_enriched": 0,
            "shots_skipped": 0,
            "total_nano_chars": 0,
            "total_ltx_chars": 0,
            "shots": [],
            "warnings": [],
        }

        # Group shots by scene if not filtered
        if scene_id:
            scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
            shot_groups = {scene_id: scene_shots}
        else:
            shot_groups = {}
            for shot in shots:
                sid = shot.get("scene_id", "unknown")
                if sid not in shot_groups:
                    shot_groups[sid] = []
                shot_groups[sid].append(shot)

        # Process each scene
        for sid, scene_shots in shot_groups.items():
            n_shots = len(scene_shots)

            for idx, shot in enumerate(scene_shots):
                try:
                    prompts = self.build_prompts(
                        shot,
                        scene_id=sid,
                        shot_index=idx,
                        n_shots_in_scene=n_shots,
                    )

                    # Update shot with new prompts
                    shot["nano_prompt"] = prompts["nano_prompt"]
                    shot["ltx_motion_prompt"] = prompts["ltx_motion_prompt"]
                    shot["nano_prompt_final"] = prompts["nano_prompt_final"]

                    results["shots_enriched"] += 1
                    results["total_nano_chars"] += len(prompts["nano_prompt"])
                    results["total_ltx_chars"] += len(prompts["ltx_motion_prompt"])
                    results["shots"].append(shot)

                    # Warn if prompts too long
                    if len(prompts["nano_prompt"]) > 2000:
                        results["warnings"].append(
                            f"{shot.get('shot_id')}: nano_prompt {len(prompts['nano_prompt'])} chars (>2000)"
                        )
                    if len(prompts["ltx_motion_prompt"]) > 1500:
                        results["warnings"].append(
                            f"{shot.get('shot_id')}: ltx_motion_prompt {len(prompts['ltx_motion_prompt'])} chars (>1500)"
                        )

                except Exception as e:
                    results["shots_skipped"] += 1
                    results["warnings"].append(f"Failed to enrich {shot.get('shot_id')}: {e}")
                    results["shots"].append(shot)

        results["avg_nano_chars"] = (
            results["total_nano_chars"] // results["shots_enriched"]
            if results["shots_enriched"] > 0 else 0
        )
        results["avg_ltx_chars"] = (
            results["total_ltx_chars"] // results["shots_enriched"]
            if results["shots_enriched"] > 0 else 0
        )

        logger.info(
            f"Enriched {results['shots_enriched']} shots, "
            f"skipped {results['shots_skipped']}, "
            f"avg nano {results['avg_nano_chars']} chars, "
            f"avg ltx {results['avg_ltx_chars']} chars"
        )

        if results["warnings"]:
            logger.warning(f"{len(results['warnings'])} enrichment warnings")
            for warn in results["warnings"][:5]:  # Log first 5
                logger.warning(f"  {warn}")

        return results
