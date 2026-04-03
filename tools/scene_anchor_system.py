#!/usr/bin/env python3
"""
SCENE ANCHOR SYSTEM - V17 Consistency Layer
============================================
Re-implements the consistency logic that was lost since Marcus Chen era.

This system ensures:
1. WARDROBE LOCK: Same costume across all shots of a character in a scene
2. LOCATION ANCHOR: Same room description across all shots in a scene
3. LIGHTING CONTINUITY: Same lighting style across all shots in a scene
4. HARD NEGATIVES: Genre-specific banned elements

Usage:
    from tools.scene_anchor_system import SceneAnchorSystem
    anchor = SceneAnchorSystem(project_path)
    enhanced_prompt = anchor.enhance_prompt(shot, scene_id)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from core.project_config import get_project_config
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False


class SceneAnchorSystem:
    """
    Manages visual consistency anchors at the scene level.
    Each scene gets a fixed:
    - Location description (same room)
    - Lighting style (same mood)
    - Per-character wardrobe (same costume)
    """

    # Hard negatives that apply to ALL shots (from V13 Gold Standard)
    HARD_NEGATIVES = (
        ", NO grid, NO collage, NO split screen, NO extra people, "
        "NO morphing faces, NO watermarks, NO text overlays, "
        "NO babies, NO children unless script specifies"
    )

    # Genre-specific additional negatives
    GENRE_NEGATIVES = {
        "gothic_horror": ", NO modern technology, NO bright colors, NO contemporary clothing",
        "fantasy": ", NO modern technology, NO cars, NO phones, NO contemporary clothing",
        "sci_fi": ", NO fantasy magic, NO medieval props, NO horses",
        "thriller": ", NO fantasy elements, NO supernatural, NO bright cheerful colors",
        "drama": ", NO fantasy elements, NO supernatural, NO period anachronisms",
    }

    # Default wardrobe by character archetype (fallback when story_bible lacks detail)
    DEFAULT_WARDROBE = {
        "lead_female": "elegant flowing gown, period-appropriate formal wear",
        "lead_male": "fitted formal attire, dark tailored clothing",
        "servant": "simple plain garments, muted colors, practical attire",
        "noble": "rich fabrics, ornate details, jeweled accessories",
        "priest": "religious robes, ceremonial vestments, modest attire",
        "warrior": "battle-worn armor, practical leather gear, weapon belt",
        "default": "period-appropriate attire, practical clothing",
    }

    # V22 WARDROBE LOCKS - Project-specific (loaded from project config at runtime)
    # Empty fallback dict — dynamically populated from project config in __init__
    _DEFAULT_WARDROBE_LOCKS = {}

    # Lighting by emotional tone
    LIGHTING_BY_TONE = {
        "dread": "high contrast, deep shadows, cold blue undertones, rim lighting",
        "tension": "harsh directional lighting, strong shadows, contrasty",
        "grief": "soft diffused light, muted colors, low saturation",
        "hope": "warm golden hour light, soft fill, gentle rim",
        "revelation": "dramatic spotlight, stark contrast, single source",
        "fear": "low key lighting, shadows dominate, cold tones",
        "anger": "harsh red-tinted lighting, strong contrast, aggressive",
        "love": "soft romantic lighting, warm tones, gentle fill",
        "suspense": "low key lighting, shadows, motivated practicals only",
        "horror": "under-lighting, green/blue tint, unnatural shadows",
        "mystery": "dappled shadows, partial illumination, chiaroscuro",
        "neutral": "balanced three-point lighting, natural color temperature",
    }

    # V17.8: COLOR GRADE ANCHORS by emotional tone
    # Ensures ALL shots in a scene share the SAME color grade — prevents green/warm drift
    COLOR_GRADE_BY_TONE = {
        "dread": "cold desaturated grade, teal-blue shadows, crushed blacks, no warm tones",
        "tension": "high contrast grade, neutral midtones, sharp shadows, controlled saturation",
        "grief": "muted desaturated grade, low saturation, soft contrast, gray-blue undertones",
        "hope": "warm golden grade, amber highlights, lifted shadows, gentle saturation",
        "revelation": "stark neutral grade, high contrast, crisp whites, deep blacks",
        "fear": "cold blue-green grade, desaturated skin tones, deep shadow crush",
        "anger": "high contrast warm-red grade, saturated reds, hot highlights",
        "love": "warm rosy grade, soft pink highlights, gentle skin tones, low contrast",
        "suspense": "underexposed neutral grade, muted colors, practical light warmth only",
        "horror": "sickly green-teal grade, desaturated except green channel, crushed blacks",
        "mystery": "amber-teal split grade, warm highlights cold shadows, filmic contrast",
        "neutral": "DaVinci Resolve neutral grade, balanced color temperature, subtle film grain",
    }

    # V17.8: GENRE COLOR GRADE OVERRIDE — scene-level grade matching film profile
    GENRE_COLOR_GRADE = {
        "gothic_horror": "cold desaturated grade, teal shadows, period grain, NO warm green tones",
        "horror": "cold desaturated grade, teal shadows, crushed blacks, sickly undertone",
        "noir": "high contrast monochrome grade, deep blacks, silver highlights",
        "period": "period-accurate warm grade, golden hour bias, amber midtones",
        "fantasy": "vibrant saturated grade, jewel-tone palette, rich color depth",
        "sci_fi": "cool clinical grade, neon accents, blue-white highlights",
        "drama": "DaVinci Resolve neutral grade, balanced temperature, subtle film grain",
        "thriller": "neutral-cool grade, controlled saturation, sharp contrast",
    }

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.shot_plan = self._load_json("shot_plan.json")
        self.story_bible = self._load_json("story_bible.json")
        self.cast_map = self._load_json("cast_map.json")

        # Load wardrobe locks from project config (V22 dynamic loading)
        self.wardrobe_locks: Dict[str, str] = {}
        if _HAS_CONFIG:
            try:
                project_name = self.project_path.name
                config = get_project_config(project_name)
                self.wardrobe_locks = config.wardrobe_locks
            except Exception:
                # Config loading failed — fall back to empty dict
                # Story bible lookup will be used in _get_character_wardrobe()
                pass

        # Build scene anchors
        self.scene_anchors: Dict[str, Dict[str, Any]] = {}
        self._build_scene_anchors()

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file from project path."""
        path = self.project_path / filename
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _build_scene_anchors(self):
        """Build per-scene consistency anchors from story bible and shot plan."""
        shots = self.shot_plan.get("shots", [])

        # Group shots by scene
        shots_by_scene: Dict[str, List[Dict]] = {}
        for shot in shots:
            scene_id = shot.get("scene_id", "001")
            if scene_id not in shots_by_scene:
                shots_by_scene[scene_id] = []
            shots_by_scene[scene_id].append(shot)

        # Get scene metadata from story bible
        scenes_meta = {}
        for scene in self.story_bible.get("scenes", []):
            sid = scene.get("scene_id", scene.get("id", ""))
            scenes_meta[sid] = scene

        # Build anchors for each scene
        for scene_id, scene_shots in shots_by_scene.items():
            scene_meta = scenes_meta.get(scene_id, {})

            # LOCATION ANCHOR - Same room for all shots in scene
            location = (
                scene_meta.get("location")
                or scene_meta.get("setting")
                or scene_shots[0].get("location", "")
                or "interior location"
            )
            location_desc = self._expand_location(location, scene_meta)

            # LIGHTING ANCHOR - Based on emotional tone
            emotional_tone = (
                scene_meta.get("emotional_tone")
                or scene_meta.get("emotion")
                or scene_shots[0].get("emotional_tone", "neutral")
            )
            lighting = self.LIGHTING_BY_TONE.get(
                emotional_tone.lower() if emotional_tone else "neutral",
                self.LIGHTING_BY_TONE["neutral"]
            )

            # TIME OF DAY - Affects lighting
            time_of_day = scene_meta.get("time_of_day", "")
            if time_of_day:
                if "night" in time_of_day.lower():
                    lighting += ", nighttime practical lighting, candles or moonlight"
                elif "dawn" in time_of_day.lower() or "dusk" in time_of_day.lower():
                    lighting += ", golden hour, warm directional sunlight"
                elif "day" in time_of_day.lower():
                    lighting += ", natural daylight, soft fill"

            # V17.8: COLOR GRADE ANCHOR — Same grade for ALL shots in scene
            # Priority: genre override → tone-based → neutral
            genre = (self.story_bible.get("genre") or "drama")
            if isinstance(genre, list):
                genre = genre[0] if genre else "drama"
            genre_key = genre.lower().replace(" ", "_").replace("-", "_")

            color_grade = self.GENRE_COLOR_GRADE.get(genre_key, "")
            if not color_grade:
                tone_key = emotional_tone.lower() if emotional_tone else "neutral"
                color_grade = self.COLOR_GRADE_BY_TONE.get(tone_key, self.COLOR_GRADE_BY_TONE["neutral"])

            # CHARACTER WARDROBES - Per character in scene
            characters_in_scene = set()
            for shot in scene_shots:
                for char in shot.get("characters", []):
                    char_name = char if isinstance(char, str) else char.get("name", "")
                    characters_in_scene.add(char_name.upper())

            character_wardrobes = {}
            for char_name in characters_in_scene:
                wardrobe = self._get_character_wardrobe(char_name)
                if wardrobe:
                    character_wardrobes[char_name] = wardrobe

            # Store anchor
            self.scene_anchors[scene_id] = {
                "location": location,
                "location_description": location_desc,
                "lighting": lighting,
                "color_grade": color_grade,
                "emotional_tone": emotional_tone,
                "time_of_day": time_of_day,
                "character_wardrobes": character_wardrobes,
                "shot_count": len(scene_shots),
            }

    def _expand_location(self, location: str, scene_meta: Dict) -> str:
        """Expand location name into detailed visual description."""
        # Check story bible locations
        locations_data = self.story_bible.get("locations", [])
        if isinstance(locations_data, list):
            for loc in locations_data:
                loc_name = loc.get("name", "")
                if loc_name.upper() in location.upper() or location.upper() in loc_name.upper():
                    desc = loc.get("description", "")
                    visual = loc.get("visual_details", "")
                    atmosphere = loc.get("atmosphere", "")
                    return f"{desc} {visual} {atmosphere}".strip()

        # Check setting.locations (V17 format)
        setting = self.story_bible.get("setting", {})
        if not isinstance(setting, dict):
            setting = {}
        setting_locs = setting.get("locations", [])
        if isinstance(setting_locs, list):
            for loc in setting_locs:
                loc_name = loc.get("name", "")
                if loc_name.upper() in location.upper() or location.upper() in loc_name.upper():
                    desc = loc.get("description", loc.get("visual", ""))
                    return desc if desc else loc_name

        # Fallback: use scene metadata
        setting_desc = scene_meta.get("setting_description", "")
        if setting_desc:
            return f"{location}, {setting_desc}"

        return location

    def _get_character_wardrobe(self, character_name: str) -> str:
        """Get wardrobe description for a character from project config, story bible, or defaults."""
        char_upper = character_name.upper().strip()

        # PRIORITY 1: Check project-specific wardrobe locks (loaded from config)
        for locked_name, wardrobe in self.wardrobe_locks.items():
            if locked_name in char_upper or char_upper in locked_name:
                return wardrobe

        # PRIORITY 2: Check story bible characters
        for char in self.story_bible.get("characters", []):
            name = (char.get("name") or "").upper()
            if name == char_upper or char_upper in name or name in char_upper:
                # Try various wardrobe fields
                wardrobe = (
                    char.get("costume")
                    or char.get("wardrobe")
                    or char.get("attire")
                    or char.get("clothing")
                    or char.get("appearance", {}).get("costume")
                    or char.get("visual_details", {}).get("wardrobe")
                )
                if wardrobe:
                    return wardrobe

                # Fall back to archetype-based default
                role = (char.get("role") or char.get("archetype") or "default").lower()
                return self.DEFAULT_WARDROBE.get(role, self.DEFAULT_WARDROBE["default"])

        return ""

    def enhance_prompt(self, shot: Dict, scene_id: Optional[str] = None) -> str:
        """
        Enhance a shot's nano_prompt with scene-locked consistency anchors.

        V18.4 ACTION-FIRST REORDER: Nano models (like nano-banana-pro) weight
        the FIRST ~120 tokens most heavily.  We now guarantee the prompt opens
        with [LENS / COMPOSITION] → [CHARACTER ACTION + PROPS] → [WARDROBE]
        before any location / atmosphere / technical layers.  This is the
        single biggest lever for hitting 70-80% first-render fidelity.

        Prompt assembly order (V18.4):
          1. LENS + COMPOSITION  (from original prompt head)
          2. CHARACTER ACTION    (extracted "Character action:" clause)
          3. CHARACTER EXPRESSION / BLOCKING (extracted expression clauses)
          4. WARDROBE            (scene anchor + cast-level)
          5. LOCATION / SETTING  (anchor location description)
          6. LIGHTING + COLOR GRADE
          7. ATMOSPHERE + TECHNICAL  (remaining original prompt body)
          8. FACE STABILITY + NEGATIVES
        """
        import re as _re

        scene_id = scene_id or shot.get("scene_id", "001")
        anchor = self.scene_anchors.get(scene_id, {})

        nano_prompt = shot.get("nano_prompt", shot.get("description", ""))
        if not nano_prompt:
            return ""

        # ── STEP 0: EXTRACT priority clauses from raw nano_prompt ──────
        # Split into sentences for classification
        _sentences = [s.strip() for s in nano_prompt.split(". ") if s.strip()]

        # Buckets
        lens_composition = []     # Camera / lens / framing (always first)
        action_clauses = []       # "Character action:" + character blocking
        expression_clauses = []   # Expression / emotion markers
        negative_clauses = []     # "NO grid" etc — always last
        atmosphere_tech = []      # Everything else (location, film stock, etc.)

        # Classification patterns
        _LENS_PAT = _re.compile(
            r"^\d+mm\b|^(?:WS|MS|MCU|CU|ECU|OTS|EWS|MWS|MLS)\b|"
            r"^(?:Wide|Medium|Close|Extreme|Establishing)\b|"
            r"^composition:|^Cinematic shot\b|^(?:macro|telephoto|anamorphic)\b",
            _re.IGNORECASE
        )
        _ACTION_PAT = _re.compile(
            r"Character action:|character performs:|character speaks:|"
            r"^(?:EVELYN|LADY|LORD|MRS|MR|DR|FATHER|MOTHER|SIR)\b.*?(?:sits|stands|walks|kneels|opens|reads|picks|holds|reaches|turns|looks|grabs|places|sets|pours|trembl|clutch|grasp|lift|push|pull)",
            _re.IGNORECASE
        )
        _EXPR_PAT = _re.compile(
            r"expression:|emotion:|visible \w+|partially restrained|"
            r"performance:|motion style:",
            _re.IGNORECASE
        )
        _NEG_PAT = _re.compile(r"^NO grid|^NO collage|^NO split|^NO morphing|^NO extra|^NO text|^NO warm|^NO babies|^NEVER", _re.IGNORECASE)

        for sent in _sentences:
            if _NEG_PAT.search(sent):
                negative_clauses.append(sent)
            elif _ACTION_PAT.search(sent):
                action_clauses.append(sent)
            elif _LENS_PAT.match(sent):
                lens_composition.append(sent)
            elif _EXPR_PAT.search(sent):
                expression_clauses.append(sent)
            else:
                atmosphere_tech.append(sent)

        # ── STEP 1: LENS / COMPOSITION (always opens the prompt) ───────
        parts = []
        if lens_composition:
            parts.extend(lens_composition)

        # ── STEP 2: CHARACTER ACTION + PROPS (highest priority content) ─
        if action_clauses:
            parts.extend(action_clauses)

        # ── STEP 3: EXPRESSION / BLOCKING ──────────────────────────────
        if expression_clauses:
            parts.extend(expression_clauses)

        # ── STEP 4: WARDROBE (scene anchor) ────────────────────────────
        characters = shot.get("characters", [])
        wardrobes_added = []
        for char in characters:
            char_name = char if isinstance(char, str) else char.get("name", "")
            char_upper = char_name.upper().strip()
            wardrobe = anchor.get("character_wardrobes", {}).get(char_upper)
            if wardrobe and wardrobe.lower() not in nano_prompt.lower():
                wardrobes_added.append(f"{char_name} wearing {wardrobe}")
        if wardrobes_added:
            parts.append(", ".join(wardrobes_added))

        # ── STEP 5: LOCATION / SETTING (anchor) ───────────────────────
        location_desc = anchor.get("location_description", "")
        if location_desc and location_desc.lower() not in nano_prompt.lower():
            parts.append(f"Location: {location_desc}")

        # ── STEP 6: LIGHTING + COLOR GRADE ─────────────────────────────
        lighting = anchor.get("lighting", "")
        if lighting and lighting.lower() not in nano_prompt.lower():
            parts.append(f"Lighting: {lighting}")

        color_grade = anchor.get("color_grade", "")
        if color_grade and color_grade.lower() not in nano_prompt.lower():
            parts.append(f"Color grade: {color_grade}")

        # ── STEP 7: ATMOSPHERE + TECHNICAL (remaining original clauses) ─
        if atmosphere_tech:
            parts.extend(atmosphere_tech)

        # ── STEP 8: FACE STABILITY + NEGATIVES ────────────────────────
        if characters:
            parts.append("face stable NO morphing, character consistent, temporal coherence")

        # Genre-appropriate hard negatives
        genre = (self.story_bible.get("genre") or "drama")
        if isinstance(genre, list):
            genre = genre[0] if genre else "drama"
        genre_key = genre.lower().replace(" ", "_").replace("-", "_")

        negatives = self.HARD_NEGATIVES
        genre_specific = self.GENRE_NEGATIVES.get(genre_key, "")
        if genre_specific:
            negatives += genre_specific

        # Re-add any extracted negative clauses (avoid duplication)
        for neg in negative_clauses:
            if neg.lower() not in negatives.lower():
                negatives += f", {neg}"

        # Build final prompt
        enhanced = ". ".join(parts) + negatives

        return enhanced

    def get_scene_anchor(self, scene_id: str) -> Dict:
        """Get the full anchor data for a scene."""
        return self.scene_anchors.get(scene_id, {})

    def apply_to_shot_plan(self, save: bool = True) -> Dict:
        """
        Apply scene anchors to all shots in the shot plan.
        Updates nano_prompt with consistency anchors.
        """
        shots = self.shot_plan.get("shots", [])
        enhanced_count = 0

        for shot in shots:
            scene_id = shot.get("scene_id", "001")
            original_prompt = shot.get("nano_prompt", "")
            enhanced_prompt = self.enhance_prompt(shot, scene_id)

            if enhanced_prompt != original_prompt:
                shot["nano_prompt"] = enhanced_prompt
                shot["_scene_anchor_applied"] = True
                enhanced_count += 1

        if save and enhanced_count > 0:
            # Backup first
            from datetime import datetime
            import shutil
            shot_plan_path = self.project_path / "shot_plan.json"
            backup_path = shot_plan_path.with_suffix(
                f".backup_scene_anchor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy(shot_plan_path, backup_path)

            # Save updated shot plan
            with open(shot_plan_path, 'w') as f:
                json.dump(self.shot_plan, f, indent=2)

        return {
            "success": True,
            "total_shots": len(shots),
            "enhanced_shots": enhanced_count,
            "scenes_anchored": len(self.scene_anchors),
        }


def main():
    """CLI for applying scene anchors to a project."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 scene_anchor_system.py <project_name> [--apply]")
        print()
        print("Analyzes and optionally applies scene consistency anchors.")
        sys.exit(1)

    project_name = sys.argv[1]
    apply_mode = "--apply" in sys.argv

    project_path = Path(f"/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{project_name}")
    if not project_path.exists():
        print(f"Error: Project '{project_name}' not found")
        sys.exit(1)

    anchor_system = SceneAnchorSystem(project_path)

    # Print analysis
    print("=" * 70)
    print("  SCENE ANCHOR SYSTEM - CONSISTENCY ANALYSIS")
    print("=" * 70)
    print(f"\nProject: {project_name}")
    print(f"Total Scenes: {len(anchor_system.scene_anchors)}")
    print()

    print("-" * 70)
    print("SCENE ANCHORS")
    print("-" * 70)

    for scene_id, anchor in sorted(anchor_system.scene_anchors.items()):
        print(f"\n{scene_id}:")
        print(f"  Location: {anchor.get('location', 'unknown')[:50]}...")
        print(f"  Lighting: {anchor.get('lighting', 'unknown')[:50]}...")
        print(f"  Tone: {anchor.get('emotional_tone', 'neutral')}")
        print(f"  Characters: {len(anchor.get('character_wardrobes', {}))}")
        for char, wardrobe in anchor.get("character_wardrobes", {}).items():
            print(f"    - {char}: {wardrobe[:40]}...")

    if apply_mode:
        print()
        print("=" * 70)
        print("  APPLYING SCENE ANCHORS")
        print("=" * 70)

        result = anchor_system.apply_to_shot_plan(save=True)
        print(f"\nShots enhanced: {result['enhanced_shots']}/{result['total_shots']}")
        print("Shot plan updated with consistency anchors.")
    else:
        print()
        print("Run with --apply to update shot plan with consistency anchors.")


if __name__ == "__main__":
    main()
