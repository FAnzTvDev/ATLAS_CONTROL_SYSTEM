"""
ATLAS V23 Universal Project Configuration

Replaces ALL hardcoded Ravencroft-specific data with project-agnostic
configuration loaded from each project's own data files.

Every project gets its own:
  - canonical_characters (from cast_map.json + story_bible)
  - scene_color_grades (computed from story_bible atmosphere)
  - location_keywords (extracted from scene_manifest)
  - name_normalization_map (built from cast_map aliases)
  - character_strip_patterns (generated from ai_actors_library match)
  - scene_locked_atmosphere (extracted from story_bible scene descriptions)
  - color_grade_contamination_map (computed from scene_manifest locations)
  - wardrobe_locks (from wardrobe.json — no hardcoded hex)
  - main_location_name (for manor-room style exemptions)
  - genre (from story_bible — no gothic_horror default)

Usage:
    config = ProjectConfig.load("ravencroft_v22")
    config.canonical_characters["EVELYN RAVENCROFT"]["appearance"]
    config.scene_color_grades["001"]
    config.name_norm_map["EVELYN"]  # -> "EVELYN RAVENCROFT"
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Base path for pipeline outputs
# ──────────────────────────────────────────────────────────────
PIPELINE_ROOT = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs")
AI_ACTORS_PATH = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/ai_actors_library.json")

# Fallback for VM / non-local environments
_FALLBACK_ROOT = Path(__file__).parent.parent / "pipeline_outputs"
_FALLBACK_ACTORS = Path(__file__).parent.parent / "ai_actors_library.json"

# ──────────────────────────────────────────────────────────────
# Genre-level defaults (project-agnostic)
# ──────────────────────────────────────────────────────────────
GENRE_COLOR_GRADE = {
    "gothic_horror": "desaturated cool tones, deep shadows, moonlit, crushed blacks",
    "thriller": "high contrast, sharp shadows, cool steel blue undertones",
    "noir": "deep blacks, low-key lighting, single hard light source, wet reflections",
    "drama": "natural light, warm neutrals, soft contrast, cinematic grain",
    "comedy": "bright warm tones, even lighting, slightly saturated",
    "sci_fi": "cold blue-green, metallic highlights, neon accent colors, sharp",
    "fantasy": "rich saturated tones, warm golden highlights, atmospheric haze",
    "period": "desaturated warm tones, amber highlights, film grain, soft focus edges",
    "horror": "desaturated greens, crushed blacks, stark contrast, sickly undertones",
    "romance": "soft warm tones, golden hour, gentle contrast, dreamy highlights",
    "action": "punchy contrast, warm highlights, sharp detail, desaturated midtones",
    "western": "amber dust tones, warm shadows, bleached highlights, wide open light",
}

GENRE_NEGATIVES = {
    "gothic_horror": ", NO modern technology, NO bright colors, NO contemporary clothing",
    "fantasy": ", NO modern technology, NO cars, NO phones, NO contemporary clothing",
    "sci_fi": ", NO fantasy magic, NO medieval props, NO horses",
    "thriller": ", NO fantasy elements, NO supernatural, NO bright cheerful colors",
    "drama": ", NO fantasy elements, NO supernatural, NO period anachronisms",
    "comedy": ", NO horror elements, NO blood, NO dark shadows",
    "noir": ", NO bright colors, NO modern technology, NO daylight",
    "horror": ", NO bright colors, NO comedy, NO cheerful expressions",
    "period": ", NO modern technology, NO contemporary clothing, NO anachronisms",
    "romance": ", NO horror elements, NO violence, NO dark shadows",
    "action": ", NO still poses, NO static cameras, NO fantasy elements",
    "western": ", NO modern technology, NO urban settings, NO contemporary clothing",
}

COLOR_GRADE_BY_TONE = {
    "dread": "cold desaturated grade, teal-blue shadows, crushed blacks, no warm tones",
    "tension": "high contrast grade, neutral midtones, sharp shadows, controlled saturation",
    "grief": "muted desaturated grade, low saturation, soft contrast, gray-blue undertones",
    "hope": "warm golden grade, lifted shadows, gentle saturation, amber highlights",
    "anger": "hot contrast grade, deep reds in shadows, sharp edges, punchy saturation",
    "mystery": "teal-blue grade, cool shadows, muted highlights, atmospheric desaturation",
    "peace": "soft warm grade, gentle contrast, pastel undertones, diffused light",
    "fear": "green-teal grade, crushed shadows, sickly undertones, low saturation",
    "love": "warm amber grade, soft focus, gentle highlights, golden skin tones",
    "power": "high contrast, deep blacks, metallic highlights, rich saturation",
    "isolation": "cold desaturated grade, blue-gray shadows, flat midtones, muted everything",
    "celebration": "warm saturated grade, golden highlights, rich colors, lifted shadows",
    "neutral": "balanced natural grade, moderate contrast, neutral shadows, clean midtones",
}

# Common adjective prefixes that indicate the same character
ADJECTIVE_PREFIXES = {"THE", "A", "AN", "YOUNG", "OLD", "ELDER", "LITTLE", "BIG", "DR.", "MR.", "MRS.", "MS.", "PROFESSOR", "CAPTAIN", "SERGEANT", "DETECTIVE", "AGENT", "FATHER", "MOTHER", "SISTER", "BROTHER", "UNCLE", "AUNT", "GRANDMA", "GRANDPA", "LORD", "LADY", "SIR", "DAME", "KING", "QUEEN", "PRINCE", "PRINCESS"}


@dataclass
class ProjectConfig:
    """Universal project configuration — all project-specific data in one object."""

    project_name: str
    genre: str = "drama"

    # Character system
    canonical_characters: Dict[str, Dict] = field(default_factory=dict)
    name_norm_map: Dict[str, str] = field(default_factory=dict)
    character_strip_patterns: Dict[str, List[str]] = field(default_factory=dict)

    # Scene system
    scene_color_grades: Dict[str, str] = field(default_factory=dict)
    scene_locked_atmosphere: Dict[str, List[str]] = field(default_factory=dict)
    location_keywords: Dict[str, List[str]] = field(default_factory=dict)
    main_location_name: str = ""
    sub_rooms: Set[str] = field(default_factory=set)
    color_grade_contamination: Dict[str, List[str]] = field(default_factory=dict)

    # Wardrobe
    wardrobe_locks: Dict[str, str] = field(default_factory=dict)

    # Raw data refs (for downstream tools)
    cast_map: Dict = field(default_factory=dict)
    story_bible: Dict = field(default_factory=dict)
    scene_manifest: Dict = field(default_factory=dict)
    ai_actors_library: List[Dict] = field(default_factory=list)

    # ──────────────────────────────────────────────────────────
    # FACTORY METHOD — builds everything from project files
    # ──────────────────────────────────────────────────────────
    @classmethod
    def load(cls, project_name: str, pipeline_root: Optional[Path] = None) -> "ProjectConfig":
        """
        Load all project-specific configuration from project data files.

        This replaces ALL hardcoded Ravencroft data with dynamic loading.
        Works for any project — Ravencroft, sci-fi, comedy, anything.
        """
        root = pipeline_root or PIPELINE_ROOT
        if not root.exists():
            root = _FALLBACK_ROOT
        project_dir = root / project_name

        config = cls(project_name=project_name)

        # ── Load raw data ──
        config.cast_map = _load_json(project_dir / "cast_map.json")
        config.story_bible = _load_json(project_dir / "story_bible.json")
        config.scene_manifest = _load_scene_manifest(project_dir)
        config.ai_actors_library = _load_ai_actors()

        wardrobe_data = _load_json(project_dir / "wardrobe.json")

        # ── Detect genre ──
        config.genre = _detect_genre(config.story_bible)
        logger.info(f"[ProjectConfig] {project_name}: genre={config.genre}")

        # ── Build character system ──
        config.canonical_characters = _build_canonical_characters(config.cast_map, config.story_bible)
        config.name_norm_map = _build_name_norm_map(config.cast_map, config.story_bible)
        config.character_strip_patterns = _build_strip_patterns(config.cast_map, config.ai_actors_library)

        # ── Build scene system ──
        config.scene_color_grades = _build_scene_color_grades(config.story_bible, config.scene_manifest, config.genre)
        config.scene_locked_atmosphere = _build_scene_atmosphere(config.story_bible, config.scene_manifest)
        config.location_keywords = _build_location_keywords(config.scene_manifest, config.story_bible)
        config.main_location_name, config.sub_rooms = _detect_main_location(config.scene_manifest)
        config.color_grade_contamination = _build_contamination_map(config.scene_manifest, config.location_keywords)

        # ── Build wardrobe locks ──
        config.wardrobe_locks = _build_wardrobe_locks(wardrobe_data, config.cast_map)

        logger.info(
            f"[ProjectConfig] {project_name} loaded: "
            f"{len(config.canonical_characters)} chars, "
            f"{len(config.scene_color_grades)} scene grades, "
            f"{len(config.location_keywords)} locations, "
            f"{len(config.name_norm_map)} name aliases"
        )
        return config

    # ──────────────────────────────────────────────────────────
    # CONVENIENCE METHODS
    # ──────────────────────────────────────────────────────────
    def get_character(self, name: str) -> Optional[Dict]:
        """Get canonical character data, trying exact match then substring."""
        name_upper = name.upper().strip()
        if name_upper in self.canonical_characters:
            return self.canonical_characters[name_upper]
        # Try normalized name
        normalized = self.name_norm_map.get(name_upper)
        if normalized and normalized in self.canonical_characters:
            return self.canonical_characters[normalized]
        # Substring fallback
        for canon_name, data in self.canonical_characters.items():
            if name_upper in canon_name or canon_name in name_upper:
                return data
        return None

    def get_color_grade(self, scene_id: str) -> str:
        """Get color grade for scene, falling back to genre default."""
        if scene_id in self.scene_color_grades:
            return self.scene_color_grades[scene_id]
        return GENRE_COLOR_GRADE.get(self.genre, GENRE_COLOR_GRADE["drama"])

    def get_genre_negative(self) -> str:
        """Get genre-specific negative constraints."""
        return GENRE_NEGATIVES.get(self.genre, "")

    def normalize_name(self, name: str) -> str:
        """Normalize a character name to canonical form."""
        name_upper = name.upper().strip()
        return self.name_norm_map.get(name_upper, name_upper)

    def is_sub_room(self, location: str) -> bool:
        """Check if a location is a sub-room of the main location."""
        loc_upper = location.upper().strip()
        for room in self.sub_rooms:
            if room in loc_upper:
                return True
        if self.main_location_name and self.main_location_name in loc_upper:
            return True
        return False

    def get_strip_patterns_for_character(self, char_name: str) -> List[str]:
        """Get AI actor contamination patterns for a character."""
        name_upper = char_name.upper().strip()
        return self.character_strip_patterns.get(name_upper, [])

    def to_dict(self) -> Dict:
        """Serialize config for API responses / debugging."""
        return {
            "project_name": self.project_name,
            "genre": self.genre,
            "character_count": len(self.canonical_characters),
            "characters": list(self.canonical_characters.keys()),
            "scene_color_grade_count": len(self.scene_color_grades),
            "location_count": len(self.location_keywords),
            "main_location": self.main_location_name,
            "sub_rooms": list(self.sub_rooms),
            "name_aliases": len(self.name_norm_map),
            "strip_pattern_chars": len(self.character_strip_patterns),
        }


# ══════════════════════════════════════════════════════════════
# BUILDER FUNCTIONS — each replaces one hardcoded section
# ══════════════════════════════════════════════════════════════

def _load_json(path: Path) -> Dict:
    """Load JSON file, return empty dict on failure."""
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    return {}


def _load_ai_actors() -> List[Dict]:
    """Load AI actors library."""
    path = AI_ACTORS_PATH if AI_ACTORS_PATH.exists() else _FALLBACK_ACTORS
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("actors", data.get("library", []))
        except Exception:
            pass
    return []


def _load_scene_manifest(project_dir: Path) -> Dict:
    """Extract scene_manifest from shot_plan.json metadata. Always returns dict keyed by scene_id."""
    shot_plan = _load_json(project_dir / "shot_plan.json")
    if isinstance(shot_plan, dict):
        manifest = shot_plan.get("scene_manifest", None)
        if manifest is None:
            meta = shot_plan.get("metadata", {})
            if isinstance(meta, dict):
                manifest = meta.get("scene_manifest", None)

        if manifest:
            return _normalize_manifest(manifest)
    return {}


def _normalize_manifest(manifest) -> Dict:
    """Convert scene_manifest to dict keyed by scene_id regardless of input format."""
    if isinstance(manifest, dict):
        # Check if it's already keyed by scene_id
        first_val = next(iter(manifest.values()), None) if manifest else None
        if isinstance(first_val, dict):
            return manifest
        return {}

    if isinstance(manifest, list):
        result = {}
        for item in manifest:
            if isinstance(item, dict):
                sid = item.get("scene_id", "")
                if sid:
                    result[sid] = item
        return result

    return {}


def _detect_genre(story_bible: Dict) -> str:
    """Detect genre from story bible — NEVER defaults to gothic_horror."""
    if not story_bible:
        return "drama"  # Universal safe default
    # Direct field
    genre = story_bible.get("genre", "")
    if isinstance(genre, list):
        genre = genre[0] if genre else ""
    if genre:
        # Handle comma-separated genres — take first
        genre = genre.split(",")[0].strip()
        return genre.lower().replace(" ", "_").replace("-", "_")
    # Nested in metadata
    meta = story_bible.get("metadata", {})
    if isinstance(meta, dict):
        genre = meta.get("genre", "")
        if isinstance(genre, list):
            genre = genre[0] if genre else ""
        if genre:
            genre = genre.split(",")[0].strip()
            return genre.lower().replace(" ", "_").replace("-", "_")
    return "drama"


def _build_canonical_characters(cast_map: Dict, story_bible: Dict) -> Dict[str, Dict]:
    """
    Build CANONICAL_CHARACTERS from cast_map + story_bible.
    Replaces the hardcoded Ravencroft character dict.

    Each character gets:
      - appearance: from cast_map.appearance or story_bible character description
      - negative: auto-generated from AI actor name + nationality
      - wardrobe_by_scene: from wardrobe.json (if available)
    """
    characters = {}

    for char_name, char_data in cast_map.items():
        # Skip alias entries
        if isinstance(char_data, dict) and char_data.get("_is_alias_of"):
            continue

        name_upper = char_name.upper().strip()

        # Extract appearance
        appearance = ""
        if isinstance(char_data, dict):
            app = char_data.get("appearance", "")
            if isinstance(app, str):
                appearance = app
            elif isinstance(app, dict):
                # Structured appearance (height, build, hair, eyes, etc.)
                parts = []
                for key in ["build", "hair", "eyes", "distinguishing"]:
                    val = app.get(key, "")
                    if val:
                        parts.append(val)
                appearance = ", ".join(parts)

        # Build negative from AI actor data
        negative_parts = []
        ai_actor_name = ""
        if isinstance(char_data, dict):
            ai_actor_name = char_data.get("ai_actor", "") or char_data.get("actor_name", "")
            if ai_actor_name:
                negative_parts.append(f"NO {ai_actor_name} description")

        # Extract additional negatives from story bible character notes
        sb_chars = _get_story_bible_characters(story_bible)
        for sb_char in sb_chars:
            sb_name = sb_char.get("name", "").upper().strip()
            if sb_name == name_upper or sb_name in name_upper or name_upper in sb_name:
                notes = sb_char.get("negative_constraints", "") or sb_char.get("notes", "")
                if notes:
                    negative_parts.append(notes)
                break

        characters[name_upper] = {
            "appearance": appearance,
            "negative": ", ".join(negative_parts) if negative_parts else "",
            "ai_actor": ai_actor_name,
        }

    logger.info(f"[ProjectConfig] Built {len(characters)} canonical characters from cast_map")
    return characters


def _get_story_bible_characters(story_bible: Dict) -> List[Dict]:
    """Extract character list from story bible (various formats)."""
    if not story_bible:
        return []
    # Direct characters array
    chars = story_bible.get("characters", [])
    if isinstance(chars, list):
        return chars
    if isinstance(chars, dict):
        return [{"name": k, **v} if isinstance(v, dict) else {"name": k, "description": v}
                for k, v in chars.items()]
    return []


def _build_name_norm_map(cast_map: Dict, story_bible: Dict) -> Dict[str, str]:
    """
    Build name normalization map from cast_map canonical names.
    Replaces hardcoded _NAME_NORM.

    For each canonical name like "EVELYN RAVENCROFT":
      - "EVELYN" -> "EVELYN RAVENCROFT"  (first name)
      - "RAVENCROFT" -> skip (too ambiguous if multiple Ravencrofts)

    Also handles:
      - "DR. ELIAS WARD" -> "ELIAS" maps, "DR. WARD" maps, "DR. ELIAS" maps
      - "THE LAWYER" -> "LAWYER" maps
    """
    norm_map = {}
    canonical_names = set()

    for char_name in cast_map:
        if isinstance(cast_map[char_name], dict) and cast_map[char_name].get("_is_alias_of"):
            continue
        canonical_names.add(char_name.upper().strip())

    # Count how many characters share each name part
    part_count = Counter()
    for name in canonical_names:
        parts = name.split()
        for part in parts:
            clean = part.strip(".,;:'\"")
            if clean and clean not in ADJECTIVE_PREFIXES and len(clean) > 1:
                part_count[clean] += 1

    for name in canonical_names:
        parts = name.split()

        # Single-word name: no aliases needed (already canonical)
        if len(parts) == 1:
            continue

        # Strip prefix (THE, DR., LADY, etc.)
        prefix_parts = []
        name_parts = []
        for p in parts:
            if p in ADJECTIVE_PREFIXES and not name_parts:
                prefix_parts.append(p)
            else:
                name_parts.append(p)

        # Map first significant name part if unique
        if name_parts and part_count[name_parts[0]] == 1:
            norm_map[name_parts[0]] = name

        # Map prefix + first name (e.g., "DR. ELIAS" -> "DR. ELIAS WARD")
        if prefix_parts and name_parts:
            short = " ".join(prefix_parts + name_parts[:1])
            norm_map[short] = name

        # Map prefix + last name (e.g., "DR. WARD" -> "DR. ELIAS WARD")
        if prefix_parts and len(name_parts) > 1:
            short = " ".join(prefix_parts + name_parts[-1:])
            norm_map[short] = name

        # Map without prefix (e.g., "LAWYER" -> "THE LAWYER")
        if prefix_parts:
            without_prefix = " ".join(name_parts)
            if without_prefix not in canonical_names:
                norm_map[without_prefix] = name

        # Map last name only if unique (e.g., "WARD" -> "DR. ELIAS WARD")
        if len(name_parts) > 1 and part_count[name_parts[-1]] == 1:
            norm_map[name_parts[-1]] = name

    # Also check story bible for aliases
    sb_chars = _get_story_bible_characters(story_bible)
    for sb_char in sb_chars:
        aliases = sb_char.get("aliases", [])
        sb_name = sb_char.get("name", "").upper().strip()
        if sb_name in canonical_names:
            for alias in aliases:
                alias_upper = alias.upper().strip()
                if alias_upper not in canonical_names:
                    norm_map[alias_upper] = sb_name

    logger.info(f"[ProjectConfig] Built {len(norm_map)} name aliases from {len(canonical_names)} canonical names")
    return norm_map


def _build_strip_patterns(cast_map: Dict, ai_actors: List[Dict]) -> Dict[str, List[str]]:
    """
    Build AI actor contamination strip patterns PER CHARACTER.
    Replaces hardcoded strip_patterns in CANONICAL_CHARACTERS.

    For each character, finds their AI actor match and generates regex patterns
    to strip the actor's name, nationality, and identifying features.
    """
    patterns = {}
    actor_index = {a.get("name", ""): a for a in ai_actors}

    for char_name, char_data in cast_map.items():
        if not isinstance(char_data, dict) or char_data.get("_is_alias_of"):
            continue

        name_upper = char_name.upper().strip()
        char_patterns = []

        # Get AI actor info
        actor_name = char_data.get("ai_actor", "") or char_data.get("actor_name", "")
        if not actor_name:
            continue

        actor_info = actor_index.get(actor_name, {})

        # Pattern 1: AI actor full name
        escaped = re.escape(actor_name)
        char_patterns.append(rf'{escaped}[^.]*[.,]?\s*')

        # Pattern 2: AI actor first name + last name separately
        name_parts = actor_name.split()
        if len(name_parts) >= 2:
            char_patterns.append(rf'\b{re.escape(name_parts[0])}\s+{re.escape(name_parts[1])}[^.]*[.,]?\s*')

        # Pattern 3: Nationality from actor's image_prompt or backstory
        image_prompt = actor_info.get("image_prompt", "")
        nationalities_found = _extract_nationalities(image_prompt)
        for nat in nationalities_found:
            # Add context guard — don't strip "Italian architecture", etc.
            context_safe = _nationality_with_context_guard(nat)
            if context_safe:
                char_patterns.append(context_safe)

        # Pattern 4: Specific descriptors from actor that DON'T match character
        actor_appearance = actor_info.get("image_prompt", "")
        if actor_appearance:
            # Extract ethnicity/nationality descriptors
            for desc in re.findall(r'([A-Z][a-z]+-[A-Z][a-z]+)', actor_appearance):
                char_patterns.append(rf'\b{re.escape(desc)}\b[^.]*[.,]?\s*')

        if char_patterns:
            patterns[name_upper] = char_patterns

    logger.info(f"[ProjectConfig] Built strip patterns for {len(patterns)} characters")
    return patterns


# Nationality extraction helpers
_KNOWN_NATIONALITIES = {
    "Italian", "French", "German", "Spanish", "Russian", "Chinese", "Japanese",
    "Korean", "Indian", "Brazilian", "Nigerian", "Mexican", "Irish", "Swedish",
    "Norwegian", "Polish", "Greek", "Turkish", "Vietnamese", "Thai", "Egyptian",
    "Moroccan", "Cuban", "Argentine", "Colombian", "Australian", "Canadian",
    "British", "Scottish", "Welsh", "American", "African", "European", "Asian"
}

_NATIONALITY_CONTEXT_GUARDS = {
    "Italian": r'\bItalian\b(?!\s+(?:architecture|villa|countryside|wine|garden|marble|stone|renaissance|Gothic|food|restaurant|opera))',
    "French": r'\bFrench\b(?!\s+(?:door|window|press|toast|quarter|cuisine|restaurant|revolution))',
    "Irish": r'\bIrish\b(?!\s+(?:whiskey|coffee|pub|sea|stew|cream))',
    "German": r'\bGerman\b(?!\s+(?:shepherd|expressionism|engineering|beer))',
    "Indian": r'\bIndian\b(?!\s+(?:ocean|summer|ink|food|spice|cuisine))',
    "Russian": r'\bRussian\b(?!\s+(?:roulette|doll|novel|literature))',
    "Chinese": r'\bChinese\b(?!\s+(?:food|restaurant|lantern|new year))',
    "Japanese": r'\bJapanese\b(?!\s+(?:garden|tea|maple|cherry))',
}


def _extract_nationalities(text: str) -> List[str]:
    """Extract nationality words from actor description text."""
    found = []
    for nat in _KNOWN_NATIONALITIES:
        if re.search(rf'\b{nat}\b', text, re.IGNORECASE):
            found.append(nat)
    # Also catch hyphenated (Asian-American, Mexican-American, etc.)
    for match in re.finditer(r'([A-Z][a-z]+-[A-Z][a-z]+)', text):
        found.append(match.group(1))
    return found


def _nationality_with_context_guard(nationality: str) -> Optional[str]:
    """Get a nationality pattern with context guard, or basic pattern."""
    if nationality in _NATIONALITY_CONTEXT_GUARDS:
        return _NATIONALITY_CONTEXT_GUARDS[nationality]
    # Basic pattern for uncommon nationalities
    return rf'\b{re.escape(nationality)}\b'


def _build_scene_color_grades(story_bible: Dict, scene_manifest: Dict, genre: str) -> Dict[str, str]:
    """
    Build per-scene color grades from story bible atmosphere data.
    Replaces hardcoded SCENE_COLOR_GRADES.

    Priority: scene-level atmosphere → genre default.
    """
    grades = {}
    scenes = story_bible.get("scenes", [])
    if isinstance(scenes, list):
        for scene in scenes:
            sid = scene.get("scene_id", "")
            if not sid:
                continue

            # Try atmosphere/mood fields
            atmosphere = scene.get("atmosphere", "") or scene.get("mood", "")
            tone = scene.get("tone", "") or scene.get("emotional_tone", "")

            # Map tone to color grade
            grade = ""
            if tone:
                tone_lower = tone.lower().strip()
                for tone_key, tone_grade in COLOR_GRADE_BY_TONE.items():
                    if tone_key in tone_lower:
                        grade = tone_grade
                        break

            # If no tone match, derive from atmosphere
            if not grade and atmosphere:
                atm_lower = atmosphere.lower()
                if any(w in atm_lower for w in ["dark", "dread", "ominous", "forboding"]):
                    grade = COLOR_GRADE_BY_TONE.get("dread", "")
                elif any(w in atm_lower for w in ["tense", "suspense", "anxiety"]):
                    grade = COLOR_GRADE_BY_TONE.get("tension", "")
                elif any(w in atm_lower for w in ["warm", "cozy", "comfort"]):
                    grade = COLOR_GRADE_BY_TONE.get("peace", "")
                elif any(w in atm_lower for w in ["sad", "grief", "mourn", "loss"]):
                    grade = COLOR_GRADE_BY_TONE.get("grief", "")
                elif any(w in atm_lower for w in ["mystery", "enigma", "unknown"]):
                    grade = COLOR_GRADE_BY_TONE.get("mystery", "")
                elif any(w in atm_lower for w in ["hope", "bright", "optimis"]):
                    grade = COLOR_GRADE_BY_TONE.get("hope", "")

            # Fallback to genre default
            if not grade:
                grade = GENRE_COLOR_GRADE.get(genre, GENRE_COLOR_GRADE.get("drama", ""))

            grades[sid] = grade

    logger.info(f"[ProjectConfig] Built {len(grades)} scene color grades")
    return grades


def _build_scene_atmosphere(story_bible: Dict, scene_manifest: Dict) -> Dict[str, List[str]]:
    """
    Build per-scene locked atmosphere phrases from story bible.
    Replaces hardcoded SCENE_LOCKED_ATMOSPHERE.

    Extracts distinctive keywords from each scene's description/beats
    that should NOT appear in other scenes' prompts.
    """
    scene_keywords = {}
    scenes = story_bible.get("scenes", [])
    if not isinstance(scenes, list):
        return {}

    for scene in scenes:
        sid = scene.get("scene_id", "")
        if not sid:
            continue

        # Collect unique phrases from this scene's description + beats
        texts = []
        desc = scene.get("description", "")
        if desc:
            texts.append(desc)
        for beat in scene.get("beats", []):
            beat_desc = beat.get("description", "")
            if beat_desc:
                texts.append(beat_desc)

        # Extract location-specific noun phrases (2-3 word combos)
        combined = " ".join(texts).lower()
        keywords = set()

        # Extract location-defining phrases
        location = (scene.get("location", "") or "").lower()
        if location:
            # Split location into significant words
            for word in re.split(r'[\s\-/]+', location):
                clean = word.strip(".,;:'\"()[]")
                if len(clean) > 3 and clean not in {"the", "and", "with", "from", "into"}:
                    keywords.add(clean)

        scene_keywords[sid] = list(keywords)

    # Now build LOCKED patterns: phrases from scene X that shouldn't be in scene Y
    locked = {}
    for sid, kws in scene_keywords.items():
        patterns = []
        for kw in kws:
            patterns.append(rf'\b{re.escape(kw)}\b[^.]*[.,]?\s*')
        if patterns:
            locked[f"{sid}_ONLY"] = patterns

    return locked


def _build_location_keywords(scene_manifest: Dict, story_bible: Dict) -> Dict[str, List[str]]:
    """
    Build location keyword index from scene manifest.
    Replaces hardcoded LOCATION_KEYWORDS.

    For each unique location, extracts DISTINCTIVE keywords that identify it.
    V23: Excludes shared prefix words to prevent false positives when all
    locations are sub-rooms of the same estate/building.
    Used by movie_lock_mode contract D (location_bleed).
    """
    location_kws = {}
    all_loc_names = []

    def _clean_location(raw_loc):
        loc_upper = raw_loc.upper().strip()
        loc_clean = re.sub(r'^(INT\.|EXT\.|INT/EXT\.?)\s*', '', loc_upper).strip()
        loc_clean = re.sub(r'\s*[-–—]\s*(DAY|NIGHT|MORNING|EVENING|DAWN|DUSK|LATER|CONTINUOUS|SAME).*$', '', loc_clean).strip()
        return loc_clean

    # Collect all location names
    for scene_id, scene_data in scene_manifest.items():
        if not isinstance(scene_data, dict):
            continue
        location = scene_data.get("location", "") or scene_data.get("name", "")
        if location:
            loc_clean = _clean_location(location)
            if loc_clean:
                all_loc_names.append(loc_clean)

    scenes = story_bible.get("scenes", [])
    if isinstance(scenes, list):
        for scene in scenes:
            location = scene.get("location", "")
            if location:
                loc_clean = _clean_location(location)
                if loc_clean:
                    all_loc_names.append(loc_clean)

    # V23: Detect shared prefix words to exclude from individual keyword sets
    # If 60%+ of locations share the same prefix, those prefix words are NOT distinctive
    shared_prefix_words = set()
    if len(set(all_loc_names)) >= 3:
        word_counts = Counter()
        unique_locs = list(set(all_loc_names))
        for loc in unique_locs:
            for word in loc.split():
                w = word.strip(".,;:'\"()[]")
                if len(w) > 3 and w.upper() not in ADJECTIVE_PREFIXES:
                    word_counts[w.lower()] += 1
        # Words appearing in 60%+ of unique locations are "shared" — not distinctive
        threshold = max(2, len(unique_locs) * 0.6)
        for word, count in word_counts.items():
            if count >= threshold:
                shared_prefix_words.add(word)
        if shared_prefix_words:
            logger.info(f"[ProjectConfig] Shared prefix words excluded from location keywords: {shared_prefix_words}")

    # Build keyword sets with shared words excluded
    for loc_clean in set(all_loc_names):
        if loc_clean in location_kws:
            continue

        keywords = []
        # Add full location as a keyword (exact match)
        keywords.append(loc_clean.lower())

        # Add individual DISTINCTIVE words only (not shared prefix words)
        for word in loc_clean.split():
            w = word.strip(".,;:'\"()[]")
            if len(w) > 3 and w.upper() not in ADJECTIVE_PREFIXES:
                if w.lower() not in shared_prefix_words:
                    keywords.append(w.lower())

        location_kws[loc_clean] = keywords

    logger.info(f"[ProjectConfig] Built {len(location_kws)} location keyword sets (excluded {len(shared_prefix_words)} shared words)")
    return location_kws


def _detect_main_location(scene_manifest: Dict) -> Tuple[str, Set[str]]:
    """
    Detect the main/recurring location and its sub-rooms.
    Replaces hardcoded MANOR_ROOMS and 'if RAVENCROFT in location'.

    The main location is the one that appears most frequently across scenes.
    Sub-rooms are locations that contain the main location's name.
    """
    location_counts = Counter()
    all_locations = {}

    for scene_id, scene_data in scene_manifest.items():
        if not isinstance(scene_data, dict):
            continue
        location = scene_data.get("location", "")
        if not location:
            continue
        loc_upper = location.upper().strip()
        loc_clean = re.sub(r'^(INT\.|EXT\.|INT/EXT\.?)\s*', '', loc_upper).strip()
        loc_clean = re.sub(r'\s*[-–—]\s*(DAY|NIGHT|MORNING|EVENING|DAWN|DUSK|LATER|CONTINUOUS|SAME).*$', '', loc_clean).strip()

        all_locations[scene_id] = loc_clean

        # Count base location words
        for word in loc_clean.split():
            w = word.strip(".,;:'\"()[]")
            if len(w) > 3 and w.upper() not in ADJECTIVE_PREFIXES:
                location_counts[w] += 1

    if not location_counts:
        return "", set()

    # Most common significant location word
    main_word = location_counts.most_common(1)[0][0]

    # V23: Detect common location prefix (e.g., "HARGROVE ESTATE" shared by all locations)
    # If most locations share a common base, use that as the main location
    unique_locs = list(set(all_locations.values()))
    common_prefix = ""
    if len(unique_locs) >= 2:
        # Find longest common prefix among all locations
        def _common_prefix(strings):
            if not strings:
                return ""
            prefix = strings[0]
            for s in strings[1:]:
                while not s.startswith(prefix):
                    # Try trimming at the last separator (space, dash)
                    for sep_idx in range(len(prefix) - 1, -1, -1):
                        if prefix[sep_idx] in (' ', '-', '–', '—'):
                            prefix = prefix[:sep_idx].strip(' -–—')
                            break
                    else:
                        prefix = ""
                        break
            return prefix.strip(' -–—')

        common_prefix = _common_prefix(unique_locs)
        # Only use if it's a meaningful base (>5 chars, at least 2 words)
        if common_prefix and len(common_prefix) > 5 and ' ' in common_prefix:
            # Check that most locations start with this prefix
            match_count = sum(1 for loc in unique_locs if loc.startswith(common_prefix))
            if match_count >= len(unique_locs) * 0.6:
                logger.info(f"[ProjectConfig] Common prefix detected: '{common_prefix}' ({match_count}/{len(unique_locs)} locations)")

    # Find the main location — prefer common prefix, otherwise longest with main_word
    main_location = ""
    if common_prefix:
        main_location = common_prefix
    else:
        for loc in all_locations.values():
            if main_word in loc:
                if not main_location or len(loc) > len(main_location):
                    main_location = loc

    # Sub-rooms: location names that are sub-locations of the main location
    # V23: If a common prefix exists, ALL locations with that prefix + a sub-part are sub-rooms
    sub_rooms = set()
    common_room_words = {"LIBRARY", "STUDY", "HALLWAY", "BEDROOM", "KITCHEN", "PARLOUR",
                         "PARLOR", "DINING", "BALLROOM", "CELLAR", "ATTIC", "TOWER",
                         "CHAPEL", "GARDEN", "COURTYARD", "ENTRANCE", "FOYER", "OFFICE",
                         "LABORATORY", "BASEMENT", "GALLERY", "THRONE", "CHAMBER",
                         "STAIRCASE", "DRIVE", "DRAWING", "MASTER", "GUEST", "GRAND"}

    for loc in set(all_locations.values()):
        if loc == main_location:
            continue
        # V23: If location starts with the main location, everything after the separator is a sub-room
        if main_location and loc.startswith(main_location):
            sub_part = loc[len(main_location):].strip(' -–—')
            if sub_part:
                # Add both the sub-part and its individual significant words
                sub_rooms.add(sub_part)
                for word in sub_part.split():
                    w = word.strip(".,;:'\"()[]")
                    if len(w) > 3:
                        sub_rooms.add(w)
        else:
            # Fallback: check for common room words
            loc_words = set(loc.split())
            for room_word in loc_words & common_room_words:
                sub_rooms.add(room_word)

    logger.info(f"[ProjectConfig] Main location: '{main_location}', sub-rooms: {sub_rooms}")
    return main_location, sub_rooms


def _build_contamination_map(scene_manifest: Dict, location_keywords: Dict) -> Dict[str, List[str]]:
    """
    Build color grade contamination map from scene manifest.
    Replaces hardcoded COLOR_GRADE_CONTAMINATION.

    For each scene, the contamination list is keywords from OTHER locations
    that should NOT appear in this scene's prompts.
    """
    contamination = {}
    scene_locations = {}

    for scene_id, scene_data in scene_manifest.items():
        if not isinstance(scene_data, dict):
            continue
        location = scene_data.get("location", "")
        if not location:
            continue
        loc_upper = location.upper().strip()
        loc_clean = re.sub(r'^(INT\.|EXT\.|INT/EXT\.?)\s*', '', loc_upper).strip()
        loc_clean = re.sub(r'\s*[-–—]\s*(DAY|NIGHT|MORNING|EVENING|DAWN|DUSK|LATER|CONTINUOUS|SAME).*$', '', loc_clean).strip()
        scene_locations[scene_id] = loc_clean

    # For each scene, forbidden keywords = keywords from OTHER locations
    for sid, my_loc in scene_locations.items():
        forbidden = []
        my_keywords = set()
        for loc_name, kws in location_keywords.items():
            if loc_name == my_loc or my_loc in loc_name or loc_name in my_loc:
                my_keywords.update(kws)

        for other_loc, other_kws in location_keywords.items():
            if other_loc == my_loc or my_loc in other_loc or other_loc in my_loc:
                continue
            for kw in other_kws:
                if kw not in my_keywords and len(kw) > 3:
                    forbidden.append(kw)

        if forbidden:
            contamination[sid] = list(set(forbidden))

    logger.info(f"[ProjectConfig] Built contamination map for {len(contamination)} scenes")
    return contamination


def _build_wardrobe_locks(wardrobe_data: Dict, cast_map: Dict) -> Dict[str, str]:
    """
    Build wardrobe locks from wardrobe.json data.
    Replaces hardcoded RAVENCROFT_WARDROBE_LOCKS.
    """
    locks = {}

    if not wardrobe_data:
        # Fall back to cast_map appearance data
        for char_name, char_data in cast_map.items():
            if isinstance(char_data, dict) and not char_data.get("_is_alias_of"):
                appearance = char_data.get("appearance", "")
                if isinstance(appearance, str) and appearance:
                    locks[char_name.upper().strip()] = appearance
        return locks

    # Extract from wardrobe.json structure
    for char_key, char_wardrobe in wardrobe_data.items():
        if isinstance(char_wardrobe, dict):
            # Get the most common/default wardrobe tag
            for scene_key, scene_look in char_wardrobe.items():
                if isinstance(scene_look, dict):
                    tag = scene_look.get("wardrobe_tag", "") or scene_look.get("description", "")
                    if tag:
                        # Use first scene's look as default
                        char_name = char_key.upper().strip()
                        if char_name not in locks:
                            locks[char_name] = tag

    return locks


# ══════════════════════════════════════════════════════════════
# MODULE-LEVEL CACHE — avoids reloading for same project
# ══════════════════════════════════════════════════════════════
_CONFIG_CACHE: Dict[str, ProjectConfig] = {}


def get_project_config(project_name: str, force_reload: bool = False) -> ProjectConfig:
    """
    Get or create ProjectConfig for a project.
    Cached — only loads once per project per server session.
    Call with force_reload=True after project data changes.
    """
    if not force_reload and project_name in _CONFIG_CACHE:
        return _CONFIG_CACHE[project_name]

    config = ProjectConfig.load(project_name)
    _CONFIG_CACHE[project_name] = config
    return config


def invalidate_config_cache(project_name: Optional[str] = None):
    """Clear config cache. Call after cast/bible/manifest changes."""
    if project_name:
        _CONFIG_CACHE.pop(project_name, None)
    else:
        _CONFIG_CACHE.clear()
