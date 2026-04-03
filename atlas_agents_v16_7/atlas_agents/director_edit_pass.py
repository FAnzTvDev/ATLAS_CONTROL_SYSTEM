"""
ATLAS V19 Director Edit Pass Agent
===================================

Runs between fix-v16 and chain render to inject editorial intelligence:
1. Edit Rhythm Validator — enforces film grammar and shot sequencing
2. Story Beat Injector — detects narrative moments requiring specific shots
3. Prop-Driven B-Roll Converter — upgrades generic B-roll with detail
4. Character Micro-Expression Builder — behavioral direction per actor

Non-blocking, advisory layer. All operations are reversible.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger("atlas.director_edit_pass")


# ============================================================================
# EDIT GRAMMAR & RHYTHM VALIDATION
# ============================================================================

EDIT_GRAMMAR = {
    "ESTABLISHING": ["GEOGRAPHY", "ACTION", "INSERT", "MASTER"],
    "GEOGRAPHY": ["ACTION", "EMOTION", "B-ROLL", "DIALOGUE"],
    "ACTION": ["EMOTION", "DETAIL", "B-ROLL", "OTS"],
    "EMOTION": ["ACTION", "REACTION", "OTS", "DIALOGUE"],
    "DIALOGUE": ["ACTION", "EMOTION", "OTS", "REACTION"],
    "OTS": ["ACTION", "EMOTION", "CLOSE", "DIALOGUE"],
    "CLOSE": ["EMOTION", "ACTION", "OTS", "INSERT"],
    "DETAIL": ["ACTION", "DIALOGUE", "GEOGRAPHY", "B-ROLL"],
    "REACTION": ["DIALOGUE", "ACTION", "EMOTION", "OTS"],
    "INSERT": ["ACTION", "DIALOGUE", "GEOGRAPHY", "B-ROLL"],
    "B-ROLL": ["GEOGRAPHY", "ACTION", "DIALOGUE", "ESTABLISHING"],
    "MASTER": ["GEOGRAPHY", "ACTION", "EMOTION"],
}

FORBIDDEN_CONSECUTIVE = [
    ("ESTABLISHING", "ESTABLISHING"),
    ("GEOGRAPHY", "GEOGRAPHY"),
    ("CLOSE", "CLOSE"),  # Avoid cutting same framing twice
    ("INSERT", "INSERT"),
]

# V19: Type normalization — maps ATLAS shot_plan types to EDIT_GRAMMAR categories
# Shot plans use lowercase specific types; grammar uses uppercase abstract roles.
# Multiple plan types can map to the same grammar category.
SHOT_TYPE_TO_GRAMMAR = {
    # Direct mappings
    "establishing": "ESTABLISHING",
    "master": "MASTER",
    "close": "CLOSE",
    "close_up": "CLOSE",
    "close-up": "CLOSE",
    "extreme_close_up": "CLOSE",
    "medium_close_up": "CLOSE",
    "insert": "INSERT",
    "detail": "DETAIL",
    "reaction": "REACTION",
    # Wide shots → GEOGRAPHY (scene-setting / spatial context)
    "wide": "GEOGRAPHY",
    "wide_shot": "GEOGRAPHY",
    "medium_wide": "GEOGRAPHY",
    "full_shot": "GEOGRAPHY",
    # Medium shots → ACTION (character action / dialogue framing)
    "medium": "ACTION",
    "medium_shot": "ACTION",
    "two_shot": "ACTION",
    "group": "ACTION",
    # OTS and conversation framing
    "over_the_shoulder": "OTS",
    "ots": "OTS",
    # B-roll and atmosphere
    "b-roll": "B-ROLL",
    "b_roll": "B-ROLL",
    "cutaway": "B-ROLL",
    # Coverage role mappings (from continuity gate)
    "a_geography": "GEOGRAPHY",
    "b_action": "ACTION",
    "c_emotion": "EMOTION",
    "geography": "GEOGRAPHY",
    "action": "ACTION",
    "emotion": "EMOTION",
}


def normalize_shot_type(raw_type: str) -> str:
    """Convert ATLAS shot_plan type to EDIT_GRAMMAR category."""
    if not raw_type:
        return "ACTION"  # Safe default — most permissive transitions
    key = raw_type.strip().lower().replace(" ", "_")
    return SHOT_TYPE_TO_GRAMMAR.get(key, "ACTION")


EDIT_SEVERITY = {
    "grammar_violation": "warning",
    "forbidden_consecutive": "warning",
    "missing_reaction": "advisory",
}


# ============================================================================
# STORY MOMENT DETECTION & INJECTION
# ============================================================================

MOMENT_PATTERNS = {
    "ARRIVAL": {
        "triggers": r"\b(arrives?|enters?|comes? through|steps? into|appears?)\b",
        "required_shots": ["ESTABLISHING", "GEOGRAPHY", "ACTION"],
        "template": "Arrival moment — character enters new location",
    },
    "REVEAL": {
        "triggers": r"\b(reveals?|discovers?|finds?|uncovers?|sees?)\b",
        "required_shots": ["CLOSE", "REACTION", "DETAIL"],
        "template": "Reveal moment — character discovers something",
    },
    "CONFRONTATION": {
        "triggers": r"\b(confronts?|accuses?|demands?|threatens?|attacks?)\b",
        "required_shots": ["OTS", "CLOSE", "REACTION"],
        "template": "Confrontation moment — tension between characters",
    },
    "SLEEP_WAKE": {
        "triggers": r"\b(sleeps?|wakes?|dreams?|awakens?)\b",
        "required_shots": ["CLOSE", "ACTION", "DETAIL"],
        "template": "Sleep/wake moment — character transitions consciousness",
    },
    "READING_LETTER": {
        "triggers": r"\b(reads?|opens? letter|receives? letter|letter reveals?)\b",
        "required_shots": ["CLOSE", "INSERT", "REACTION"],
        "template": "Letter moment — character reads message",
    },
    "SUPERNATURAL": {
        "triggers": r"\b(appears?|vanishes?|haunts?|spirit|ghost|supernatural|curse)\b",
        "required_shots": ["ESTABLISHING", "CLOSE", "REACTION"],
        "template": "Supernatural moment — otherworldly occurrence",
    },
    "DEPARTURE": {
        "triggers": r"\b(leaves?|departs?|exits?|walks? away|disappears?)\b",
        "required_shots": ["GEOGRAPHY", "ACTION", "ESTABLISHING"],
        "template": "Departure moment — character leaves location",
    },
}


# ============================================================================
# PROP-DRIVEN B-ROLL TEMPLATES
# ============================================================================

PROP_PATTERNS = {
    "letter": r"\b(letter|envelope|correspondence|note|missive)\b",
    "candle": r"\b(candle|candles?|flame|wax|wick)\b",
    "book": r"\b(book|books?|tome|volume|manuscript|pages?)\b",
    "key": r"\b(key|keys?|unlock|lock|opening)\b",
    "portrait": r"\b(portrait|painting|picture|frame|photo)\b",
    "window": r"\b(window|windows?|pane|glass|view)\b",
    "door": r"\b(door|doors?|entrance|exit|threshold)\b",
    "drink": r"\b(glass|wine|drink|cup|teacup|beverage)\b",
    "weapon": r"\b(sword|dagger|gun|knife|pistol|rifle)\b",
    "ring": r"\b(ring|rings?|signet|jewelry|band)\b",
}

PROP_BROLL_TEMPLATES = {
    "letter": {
        "lens": "100mm macro",
        "framing": "extreme close-up",
        "prompt": "Macro shot of letter: creased paper, wax seal, handwritten script, soft candlelight catching text edges",
    },
    "candle": {
        "lens": "135mm macro",
        "framing": "extreme close detail",
        "prompt": "Candle detail: flame flickers, wax drips, light refracts through glass holder, shadows dance",
    },
    "book": {
        "lens": "85mm macro",
        "framing": "tight detail",
        "prompt": "Book pages: aged leather binding, gilt edges, hand turning pages, text visible but soft focus",
    },
    "key": {
        "lens": "100mm macro",
        "framing": "close-up detail",
        "prompt": "Antique key: ornate handle, intricate etchings, light glints off metal, casting fine shadows",
    },
    "portrait": {
        "lens": "50mm",
        "framing": "medium detail",
        "prompt": "Portrait in frame: subject's eyes visible, oil paint texture, dust particles in light, ornate frame edges",
    },
    "window": {
        "lens": "35mm",
        "framing": "wide interior detail",
        "prompt": "Window view: rain on glass, light streams in, curtain billows, landscape faint beyond",
    },
    "door": {
        "lens": "24mm",
        "framing": "wide establishing detail",
        "prompt": "Door detail: wood grain, heavy hinges, threshold shadow, doorway light spills across floor",
    },
    "drink": {
        "lens": "85mm macro",
        "framing": "close-up detail",
        "prompt": "Glass detail: liquid catches light, condensation on rim, hand reaching for handle",
    },
    "weapon": {
        "lens": "85mm macro",
        "framing": "close detail",
        "prompt": "Weapon detail: blade edge sharp, handle worn from use, light glints off metal, shadow suggests danger",
    },
    "ring": {
        "lens": "100mm macro",
        "framing": "extreme close-up",
        "prompt": "Ring detail: gem facets sparkle, metal catches light, worn patina, hand holding close",
    },
}


# ============================================================================
# EDIT RHYTHM VALIDATOR
# ============================================================================

class EditRhythmValidator:
    """Enforces film grammar and shot sequencing rules."""

    def __init__(self):
        self.violations = []

    def validate_edit_rhythm(self, shots: List[Dict]) -> List[Dict]:
        """
        Check for grammar violations and forbidden consecutive pairs.

        Args:
            shots: List of shot dicts with 'shot_type' field

        Returns:
            List of violation dicts {index, shot_type, violation, severity}
        """
        self.violations = []

        if len(shots) < 2:
            return self.violations

        for i in range(len(shots) - 1):
            current = shots[i]
            next_shot = shots[i + 1]

            # V19: Normalize plan types to grammar categories
            raw_current = current.get("type", current.get("shot_type", ""))
            raw_next = next_shot.get("type", next_shot.get("shot_type", ""))
            current_type = normalize_shot_type(raw_current)
            next_type = normalize_shot_type(raw_next)

            # Check grammar violation
            allowed = EDIT_GRAMMAR.get(current_type, [])
            if next_type not in allowed and next_type != "UNKNOWN":
                self.violations.append(
                    {
                        "index": i,
                        "shot_type": current_type,
                        "next_type": next_type,
                        "violation": f"{current_type} → {next_type} breaks grammar",
                        "severity": "warning",
                    }
                )

            # Check forbidden consecutive
            if (current_type, next_type) in FORBIDDEN_CONSECUTIVE:
                self.violations.append(
                    {
                        "index": i,
                        "shot_type": current_type,
                        "next_type": next_type,
                        "violation": f"Forbidden consecutive: {current_type} + {next_type}",
                        "severity": "warning",
                    }
                )

        return self.violations

    def apply_rhythm_fixes(self, shots: List[Dict]) -> Tuple[List[Dict], int]:
        """
        Reorder shots to minimize violations (never delete).

        Args:
            shots: List of shot dicts

        Returns:
            (reordered_shots, reorder_count)
        """
        reordered = shots.copy()
        reorder_count = 0

        violations = self.validate_edit_rhythm(reordered)
        while violations and reorder_count < 10:  # Max 10 iterations
            violation = violations[0]
            idx = violation["index"]

            # Try swapping with next shot
            if idx + 1 < len(reordered):
                reordered[idx], reordered[idx + 1] = (
                    reordered[idx + 1],
                    reordered[idx],
                )
                reorder_count += 1

            violations = self.validate_edit_rhythm(reordered)

        return reordered, reorder_count


# ============================================================================
# STORY BEAT INJECTOR
# ============================================================================

class StoryBeatInjector:
    """Detects narrative moments and ensures coverage."""

    def detect_story_moments(self, beat_descriptions: List[str]) -> List[Dict]:
        """
        Scan beat descriptions for moment triggers.

        Args:
            beat_descriptions: List of beat text strings

        Returns:
            List of detected moments {type, description, beat_idx}
        """
        detected = []

        for beat_idx, beat in enumerate(beat_descriptions):
            for moment_type, pattern_info in MOMENT_PATTERNS.items():
                if re.search(pattern_info["triggers"], beat, re.IGNORECASE):
                    detected.append(
                        {
                            "type": moment_type,
                            "description": beat[:100],
                            "beat_idx": beat_idx,
                            "required_shots": pattern_info["required_shots"],
                            "template": pattern_info["template"],
                        }
                    )
                    break  # Only first match per beat

        return detected

    def check_coverage(
        self, detected_moments: List[Dict], shots: List[Dict]
    ) -> List[Dict]:
        """
        Check if moments have required shot types.

        Args:
            detected_moments: Moments from detect_story_moments()
            shots: Current shot list

        Returns:
            List of uncovered moments
        """
        uncovered = []
        existing_types = [s.get("shot_type") for s in shots]

        for moment in detected_moments:
            required = set(moment["required_shots"])
            existing = set(existing_types)

            if not required.issubset(existing):
                uncovered.append(
                    {
                        "moment_type": moment["type"],
                        "description": moment["description"],
                        "missing_shot_types": list(required - existing),
                    }
                )

        return uncovered

    def insert_moment_shots(
        self,
        beat_descriptions: List[str],
        story_bible: Dict,
        ai_actors_lib: Dict,
    ) -> List[Dict]:
        """
        Generate shot stubs for detected moments.

        Args:
            beat_descriptions: Beat text
            story_bible: Story bible data
            ai_actors_lib: AI actors library

        Returns:
            List of new shot stubs
        """
        new_shots = []
        moments = self.detect_story_moments(beat_descriptions)

        for moment in moments:
            for shot_type in moment["required_shots"]:
                nano_prompt = self._build_moment_prompt(
                    shot_type, moment, story_bible, ai_actors_lib
                )

                stub = {
                    "shot_id": f"moment_{moment['beat_idx']}_{shot_type.lower()}",
                    "shot_type": shot_type,
                    "duration": 3.0,
                    "nano_prompt": nano_prompt,
                    "ltx_motion_prompt": f"subtle micro-expression, {moment['template'].lower()}",
                    "_inserted_by": "director_edit_pass",
                    "_moment_type": moment["type"],
                }
                new_shots.append(stub)

        return new_shots

    def _build_moment_prompt(
        self,
        shot_type: str,
        moment: Dict,
        story_bible: Dict,
        ai_actors_lib: Dict,
    ) -> str:
        """Build V9-quality nano prompt for moment shot."""
        setting = story_bible.get("setting", {})
        location = setting.get("primary_location", "unknown location")

        templates = {
            "ESTABLISHING": f"Establishing shot of {location}, {moment['template'].lower()}",
            "GEOGRAPHY": f"Wide shot showing character position in {location}",
            "ACTION": f"Character performs action: {moment['description'][:50]}",
            "CLOSE": f"Close-up of character's face, subtle emotion, {moment['type'].lower()} moment",
            "REACTION": f"Character reacts with controlled emotion, microexpression visible",
            "INSERT": f"Detail shot related to {moment['type'].lower()}, sharp focus",
        }

        return templates.get(shot_type, f"Shot for {moment['type']} moment")


# ============================================================================
# PROP-DRIVEN B-ROLL CONVERTER
# ============================================================================

class PropDrivenBrollConverter:
    """Upgrades generic B-roll with prop-specific detail."""

    def detect_props_in_beat(self, beat_text: str) -> List[Tuple[str, str]]:
        """
        Scan beat for prop mentions.

        Returns:
            List of (prop_type, matched_text) tuples
        """
        props = []

        for prop_type, pattern in PROP_PATTERNS.items():
            matches = re.findall(pattern, beat_text, re.IGNORECASE)
            if matches:
                props.append((prop_type, matches[0]))

        return props

    def is_generic_prompt(self, prompt: str) -> bool:
        """Check if prompt is weak/generic (< 3 specific nouns)."""
        generic_words = {
            "shot",
            "scene",
            "detail",
            "atmospheric",
            "ambient",
            "background",
        }
        words = prompt.lower().split()
        specific_nouns = [w for w in words if w not in generic_words and len(w) > 3]

        return len(specific_nouns) < 3

    def upgrade_broll_prompts(
        self, shots: List[Dict], beat_descriptions: List[str]
    ) -> Tuple[List[Dict], int]:
        """
        Replace generic B-roll prompts with prop-specific ones.

        Args:
            shots: Shot list
            beat_descriptions: Beat text

        Returns:
            (upgraded_shots, upgrade_count)
        """
        upgraded = shots.copy()
        upgrade_count = 0

        for i, shot in enumerate(upgraded):
            if shot.get("shot_type") == "B-ROLL" or shot.get("shot_id", "").endswith(
                "B"
            ):
                beat_idx = min(i, len(beat_descriptions) - 1)
                beat = beat_descriptions[beat_idx] if beat_idx >= 0 else ""

                props = self.detect_props_in_beat(beat)
                if props and self.is_generic_prompt(shot.get("nano_prompt", "")):
                    prop_type, _ = props[0]
                    template = PROP_BROLL_TEMPLATES.get(prop_type)

                    if template:
                        shot["nano_prompt"] = template["prompt"]
                        shot["lens_specs"] = template["lens"]
                        shot["_upgraded_by"] = "director_edit_pass"
                        upgrade_count += 1

        return upgraded, upgrade_count


# ============================================================================
# CHARACTER MICRO-EXPRESSION BUILDER
# ============================================================================

class CharacterMicroExpressionBuilder:
    """Builds V9-style behavioral direction per character."""

    # V19: Expanded keyword set — covers story_bible descriptions, personality
    # traits, emotional states, and character archetypes common in gothic/drama scripts.
    # Multiple keywords can match the same character to build richer direction.
    BEHAVIOR_KEYWORDS = {
        # Core emotional states
        "stern": "controlled posture, minimal facial movement, steady gaze",
        "haunted": "cautious eye movements, weight shifts, subtle tension",
        "grief": "downward focus, slow breath, trembling jaw, quiet sorrow",
        "defiant": "rigid stance, clenched jaw, direct eye contact, sharp breathing",
        "loving": "soft eyes, gentle smile, relaxed shoulders, steady gaze",
        "fearful": "rapid eye movement, tension in shoulders, shallow breath",
        "scheming": "narrowed eyes, calculating pause, slight head tilt",
        "resigned": "slumped posture, distant gaze, slow movements",
        "determined": "forward lean, clenched fists, intense focus",
        "curious": "head tilt, raised eyebrows, forward gaze",
        # Personality / archetype descriptors
        "aristocrat": "elevated chin, measured movements, composed expression, restrained power",
        "matriarch": "commanding posture, deliberate gestures, piercing gaze, controlled authority",
        "mysterious": "guarded expression, deliberate stillness, eyes that reveal nothing",
        "vulnerable": "soft shoulders, unsteady breath, eyes searching for safety",
        "brooding": "furrowed brow, jaw tension, heavy gaze, slow deliberate movements",
        "charming": "easy smile, relaxed stance, warm eye contact, fluid gestures",
        "weary": "heavy eyelids, slowed movements, weight on one side, deep exhales",
        "sinister": "stillness before movement, eyes tracking prey, thin smile, controlled menace",
        "protective": "body angled toward ward, hands ready, alert scanning, jaw set",
        "tormented": "eyes wincing at memory, hand to temple, breath catching, tension in neck",
        # Gothic / period drama specifics
        "occult": "measured ritual gestures, intense focus, lips moving silently, trance-like stillness",
        "regal": "spine straight, chin lifted, slow deliberate turns, commanding presence",
        "anxious": "fidgeting fingers, darting eyes, swallowing, weight shifting foot to foot",
        "cold": "minimal expression, flat affect, precise movements, emotionally walled off",
        "passionate": "intense eye contact, leaning forward, expressive hands, breath quickening",
        "gentle": "soft touch, careful movements, warm half-smile, unhurried pace",
        "ruthless": "unflinching gaze, economical movement, no wasted gesture, predatory stillness",
        "scholarly": "adjusting glasses, thoughtful pause, finger tracing text, absorbed focus",
        # Broader trait matching (catches more story_bible descriptions)
        "dark": "shadowed expression, guarded stance, eyes that hold secrets",
        "proud": "squared shoulders, lifted chin, controlled expression, refuses to look away",
        "bitter": "tight lips, averted gaze, tension in hands, sharp exhales",
        "noble": "dignified bearing, measured speech cadence, composed under pressure",
        "secretive": "eyes darting to exits, lowered voice posture, guarded hand positions",
        "powerful": "grounded stance, deliberate gestures, unblinking authority",
        "fragile": "trembling hands, shallow breathing, eyes brimming, delicate movements",
        "loyal": "steadfast gaze, body oriented toward leader, ready posture, unwavering focus",
        "manipulat": "slight smile that doesn't reach eyes, calculated pauses, measuring gaze",
        "obsess": "unblinking focus, repetitive gesture, leaning too close, intense fixation",
    }

    def build_character_microexpressions(
        self, story_bible: Dict, cast_map: Dict, ai_actors_lib: Dict
    ) -> Dict[str, str]:
        """
        Generate behavioral direction for each character.

        Args:
            story_bible: Story bible with character descriptions
            cast_map: Character to actor mapping
            ai_actors_lib: AI actors library

        Returns:
            Dict of {character_name: behavioral_direction}
        """
        microexpressions = {}

        chars = story_bible.get("characters", {})
        # Handle both dict and list formats
        if isinstance(chars, list):
            chars = {c.get("name", f"char_{i}"): c for i, c in enumerate(chars) if isinstance(c, dict)}
        elif not isinstance(chars, dict):
            chars = {}
        for char_name, char_data in chars.items():
            if not isinstance(char_data, dict):
                char_data = {"description": str(char_data)}
            # V19: Search personality, description, AND appearance for keyword matches
            personality = char_data.get("personality", "")
            description = char_data.get("description", "")
            appearance = char_data.get("appearance", "")
            if isinstance(appearance, dict):
                appearance = " ".join(str(v) for v in appearance.values())
            search_text = f"{personality} {description} {appearance}".lower()

            # Find ALL matching behavior keywords, combine top 2 for richer direction
            matched_behaviors = []
            for keyword, desc in self.BEHAVIOR_KEYWORDS.items():
                if keyword in search_text:
                    matched_behaviors.append(desc)
            if matched_behaviors:
                # Take up to 2 unique behavior descriptions
                unique = list(dict.fromkeys(matched_behaviors))[:2]
                behavior_desc = ", ".join(unique)
            else:
                behavior_desc = "subtle, natural micro-expression"

            # Add actor's default LTX motion if available
            if char_name in cast_map:
                actor_id = cast_map[char_name].get("actor_id")
                if actor_id and actor_id in ai_actors_lib:
                    actor_motion = ai_actors_lib[actor_id].get(
                        "ltx_motion_default", ""
                    )
                    if actor_motion:
                        behavior_desc = f"{behavior_desc}, {actor_motion}"

            microexpressions[char_name] = behavior_desc

        return microexpressions


# ============================================================================
# MAIN DIRECTOR EDIT PASS CLASS
# ============================================================================

class DirectorEditPass:
    """
    Main entry point for editorial intelligence injection.

    Runs between fix-v16 and chain render, adding:
    - Edit rhythm validation & fixes
    - Story moment detection & coverage
    - Prop-driven B-roll upgrade
    - Character micro-expression direction
    """

    def __init__(
        self,
        project_path: Path,
        story_bible: Dict,
        cast_map: Dict,
        ai_actors_lib: Dict,
    ):
        self.project_path = Path(project_path)
        self.story_bible = story_bible
        self.cast_map = cast_map
        self.ai_actors_lib = ai_actors_lib

        self.rhythm_validator = EditRhythmValidator()
        self.beat_injector = StoryBeatInjector()
        self.broll_converter = PropDrivenBrollConverter()
        self.expression_builder = CharacterMicroExpressionBuilder()

        logger.info(f"DirectorEditPass initialized for {project_path}")

    def run(self, scene_id: Optional[str] = None, auto_fix: bool = False) -> Dict:
        """
        Run complete editorial pass.

        Args:
            scene_id: Specific scene to process (None = all)
            auto_fix: Apply automatic rhythm fixes

        Returns:
            Dict with stats: rhythm_violations, missing_moments, broll_upgrades, etc.
        """
        try:
            result = {
                "status": "success",
                "rhythm_violations": [],
                "reorders": 0,
                "missing_moments": [],
                "broll_upgrades": 0,
                "microexpressions": {},
                "warnings": [],
            }

            # Load shot plan
            shot_plan_path = self.project_path / "shot_plan.json"
            if not shot_plan_path.exists():
                logger.warning(f"No shot_plan.json found at {shot_plan_path}")
                return {**result, "status": "no_shot_plan"}

            with open(shot_plan_path) as f:
                shot_plan = json.load(f)

            shots = shot_plan.get("shots", [])
            if not shots:
                logger.warning("No shots in shot_plan")
                return {**result, "status": "no_shots"}

            # Filter by scene if specified
            if scene_id:
                shots = [s for s in shots if s.get("scene_id") == scene_id]

            # 1. Edit rhythm validation
            violations = self.rhythm_validator.validate_edit_rhythm(shots)
            result["rhythm_violations"] = violations
            logger.info(f"Found {len(violations)} rhythm violations")

            # 2. Apply fixes if requested
            if auto_fix:
                shots, reorder_count = self.rhythm_validator.apply_rhythm_fixes(shots)
                result["reorders"] = reorder_count
                logger.info(f"Applied {reorder_count} reorders")

            # 3. Story moment detection
            beat_descriptions = [
                b.get("description", "")
                for b in self.story_bible.get("beats", [])
            ]
            detected_moments = self.beat_injector.detect_story_moments(
                beat_descriptions
            )
            uncovered = self.beat_injector.check_coverage(detected_moments, shots)
            result["missing_moments"] = uncovered
            logger.info(f"Found {len(uncovered)} uncovered story moments")

            # 4. B-roll upgrade
            upgraded_shots, broll_upgrades = self.broll_converter.upgrade_broll_prompts(
                shots, beat_descriptions
            )
            result["broll_upgrades"] = broll_upgrades
            logger.info(f"Upgraded {broll_upgrades} B-roll prompts")

            # 5. Character micro-expressions
            microexpressions = (
                self.expression_builder.build_character_microexpressions(
                    self.story_bible, self.cast_map, self.ai_actors_lib
                )
            )
            result["microexpressions"] = microexpressions
            logger.info(f"Generated direction for {len(microexpressions)} characters")

            # Persist if changes made
            if auto_fix or broll_upgrades > 0:
                shot_plan["shots"] = upgraded_shots if broll_upgrades > 0 else shots
                try:
                    with open(shot_plan_path, "w") as f:
                        json.dump(shot_plan, f, indent=2)
                    logger.info(f"Updated shot_plan.json")
                except Exception as e:
                    result["warnings"].append(f"Failed to persist changes: {str(e)}")
                    logger.warning(f"Persist failed: {e}")

            return result

        except Exception as e:
            logger.error(f"DirectorEditPass.run() failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "rhythm_violations": [],
                "missing_moments": [],
                "broll_upgrades": 0,
            }

    def get_character_direction(self, character_name: str) -> str:
        """
        Get micro-expression direction for a specific character.

        Args:
            character_name: Name of character

        Returns:
            Behavioral direction string
        """
        microexpressions = self.expression_builder.build_character_microexpressions(
            self.story_bible, self.cast_map, self.ai_actors_lib
        )
        return microexpressions.get(
            character_name, "subtle, natural micro-expression"
        )


# ============================================================================
# PUBLIC API
# ============================================================================


def run_director_edit_pass(
    project_path: Path,
    story_bible: Dict,
    cast_map: Dict,
    ai_actors_lib: Dict,
    scene_id: Optional[str] = None,
    auto_fix: bool = False,
) -> Dict:
    """
    Convenience function to run editor pass.

    Args:
        project_path: Path to project
        story_bible: Story bible data
        cast_map: Character to actor mapping
        ai_actors_lib: AI actors library
        scene_id: Optional specific scene
        auto_fix: Apply automatic fixes

    Returns:
        Result dict with stats
    """
    agent = DirectorEditPass(project_path, story_bible, cast_map, ai_actors_lib)
    return agent.run(scene_id=scene_id, auto_fix=auto_fix)
