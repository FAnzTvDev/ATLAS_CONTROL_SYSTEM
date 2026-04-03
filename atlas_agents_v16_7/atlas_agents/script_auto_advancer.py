#!/usr/bin/env python3
"""
V20.4 Script Auto-Advancement Engine — Parse Script, Fill Pipeline Gaps

THE PROBLEM:
The V6 full-import pipeline extracts STRUCTURE (scenes, shot slots, character names)
but often MISSES the CONTENT (character descriptions, beat actions, dialogue, scene
atmosphere, prop lists, wardrobe cues). This happens because:
  1. Regex-based extraction catches headings but not paragraph descriptions
  2. Dialogue attribution fails on non-standard screenplay formatting
  3. Beat descriptions collapse into single-line summaries
  4. Character descriptions in "## 4) Characters" sections are ignored after names

THE SOLUTION:
This engine reads the imported_script.txt (or uploaded PDFs), parses EVERY section
thoroughly, and FILLS the empty fields in story_bible.json and shot_plan.json.

It handles ALL content types — from 52-page screenplays to 1-paragraph concepts.

UNIVERSAL PIPELINE RULE:
Every piece of content that enters ATLAS goes through:
  Script Upload → Auto-Advance (this) → Compliance Check → V20.0-V20.2 → Render

This module is the BRIDGE between raw script and pipeline-ready data.

DESIGN PRINCIPLE: Extract → Compare → Fill → Report
  1. EXTRACT everything from the raw script text
  2. COMPARE what's extracted vs what's already in story_bible + shot_plan
  3. FILL every empty field with extracted or generated content
  4. REPORT what was filled so the user/system can verify
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SECTION PARSERS — Extract structured data from raw script text
# ═══════════════════════════════════════════════════════════════════

# Standard screenplay character line: ALL CAPS name (possibly with age/parenthetical)
CHARACTER_LINE_RE = re.compile(
    r'^([A-Z][A-Z\s\-\'\.]+?)(?:\s*\(([^)]+)\))?\s*$'
)
# Dialogue: indented text after character name
DIALOGUE_RE = re.compile(
    r'^([A-Z][A-Z\s\-\'\.]{1,40})\s*(?:\(([^)]+)\))?\s*\n((?:[ \t]+.+\n?)+)',
    re.MULTILINE
)
# Scene heading: INT./EXT. LOCATION - TIME
SCENE_HEADING_RE = re.compile(
    r'^((?:INT|EXT|INT/EXT|EXT/INT)\.?\s+.+?)\s*$',
    re.MULTILINE | re.IGNORECASE
)
# Character description block: **NAME** - description
CHAR_DESC_RE = re.compile(
    r'\*\*([A-Z][A-Z\s\-\'\.]+?)\*\*\s*[-–—]\s*(.+?)(?=\n\*\*[A-Z]|\n###|\n##|\Z)',
    re.DOTALL
)
# Scene card: **Scene N - LOCATION**
SCENE_CARD_RE = re.compile(
    r'\*\*Scene\s+(\d+)\s*[-–—]\s*(.+?)\*\*\s*\n((?:.*?\n)*?)(?=\*\*Scene|\Z)',
    re.DOTALL
)
# Alias line: NAME = ALIAS = ALIAS2
ALIAS_RE = re.compile(
    r'^([A-Z][A-Z\s\-\'\.]+?)\s*=\s*(.+)$',
    re.MULTILINE
)
# Beat bullet: - LOCATION: description
BEAT_RE = re.compile(
    r'^[-•]\s*(?:([A-Z][A-Z\s\-\'\/]+?):\s*)?(.+)$',
    re.MULTILINE
)
# Casting stopwords
CASTING_STOPWORDS = {
    'NIGHT', 'MORNING', 'EVENING', 'DAY', 'CONTINUOUS', 'O.S.', 'V.O.',
    'PRE-LAP', 'INTO VIEW', 'ESTABLISHING', 'CUT TO', 'FADE TO', 'MONTAGE',
    'END OF ACT', 'ACT ONE', 'ACT TWO', 'ACT THREE', 'ACT FOUR', 'LATER',
    'MOMENTS LATER', 'CONTINUED', 'CONT', 'ANGLE ON', 'CLOSE ON', 'BACK TO',
    'TITLE CARD', 'SUPER', 'INTERCUT', 'FLASHBACK', 'SMASH CUT', 'DISSOLVE TO',
}


@dataclass
class ExtractedCharacter:
    """Character parsed from script."""
    name: str
    description: str = ""
    age: str = ""
    gender: str = ""
    race: str = ""  # human/elf/dwarf/etc for fantasy
    physical: str = ""
    wardrobe: str = ""
    props: str = ""
    aliases: List[str] = field(default_factory=list)
    scenes_present: List[str] = field(default_factory=list)


@dataclass
class ExtractedDialogue:
    """Dialogue line from screenplay."""
    character: str
    line: str
    parenthetical: str = ""
    scene_number: str = ""


@dataclass
class ExtractedBeat:
    """Action beat from screenplay."""
    description: str
    characters: List[str] = field(default_factory=list)
    location: str = ""
    scene_number: str = ""
    is_action: bool = False
    dialogue_lines: List[ExtractedDialogue] = field(default_factory=list)


@dataclass
class ExtractedScene:
    """Full scene parsed from screenplay."""
    scene_number: str
    location: str
    time_of_day: str = ""
    int_ext: str = ""
    purpose: str = ""
    characters: List[str] = field(default_factory=list)
    beats: List[ExtractedBeat] = field(default_factory=list)
    dialogue: List[ExtractedDialogue] = field(default_factory=list)
    action_text: str = ""
    atmosphere: str = ""


@dataclass
class AdvancementReport:
    """What was filled by the auto-advancer."""
    characters_filled: int = 0
    characters_created: int = 0
    beats_filled: int = 0
    dialogue_recovered: int = 0
    scenes_enriched: int = 0
    aliases_mapped: int = 0
    props_extracted: int = 0
    wardrobe_cues: int = 0
    atmosphere_added: int = 0
    total_changes: int = 0
    details: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# SCRIPT PARSER — Universal parser for any script format
# ═══════════════════════════════════════════════════════════════════

class ScriptParser:
    """
    Parses imported_script.txt (ATLAS V6 format) or raw screenplay text.

    Handles:
      - V6 format: ## sections (Story Bible, Beat Summary, Scene Cards, Characters, Screenplay)
      - Standard screenplay: INT./EXT. headings, ALL CAPS characters, indented dialogue
      - Hybrid: Markdown-wrapped screenplays
      - Minimal: Single paragraph concepts
    """

    def __init__(self, script_text: str):
        self.raw = script_text
        self.sections = {}
        self.characters: Dict[str, ExtractedCharacter] = {}
        self.scenes: Dict[str, ExtractedScene] = {}
        self.aliases: Dict[str, str] = {}  # alias → canonical name
        self.dialogue: List[ExtractedDialogue] = []
        self.beats_by_act: Dict[str, List[ExtractedBeat]] = {}
        self.metadata: Dict[str, str] = {}

        self._split_sections()
        self._parse_metadata()
        self._parse_characters()
        self._parse_aliases()
        self._parse_scene_cards()
        self._parse_beat_summary()
        self._parse_screenplay()

    def _split_sections(self):
        """Split V6-format script into named sections."""
        # Find ## headers
        parts = re.split(r'^(## \d+\).+)$', self.raw, flags=re.MULTILINE)
        current_header = "_preamble"
        for part in parts:
            if re.match(r'^## \d+\)', part):
                current_header = part.strip()
            else:
                self.sections[current_header] = part

        # Also find the screenplay section (after ---SCREENPLAY---)
        sp_idx = self.raw.find('---SCREENPLAY---')
        if sp_idx >= 0:
            self.sections['_screenplay'] = self.raw[sp_idx:]
        else:
            # Try to find first INT./EXT. heading as screenplay start
            m = SCENE_HEADING_RE.search(self.raw)
            if m:
                self.sections['_screenplay'] = self.raw[m.start():]

    def _parse_metadata(self):
        """Extract series title, genre, logline, etc."""
        preamble = self.sections.get('_preamble', '')
        for key_section in [preamble] + list(self.sections.values()):
            for pattern, field_name in [
                (r'\*\*Series Title:\*\*\s*(.+)', 'series_title'),
                (r'\*\*Episode:\*\*\s*(.+)', 'episode'),
                (r'\*\*Genre:\*\*\s*(.+)', 'genre'),
                (r'\*\*Logline:\*\*\s*(.+)', 'logline'),
                (r'\*\*Tone:\*\*\s*(.+)', 'tone'),
                (r'\*\*Written By:\*\*\s*(.+)', 'writer'),
                (r'\*\*Runtime.*?:\*\*\s*(.+)', 'runtime'),
                (r'\*\*Setting:\*\*\s*(.+)', 'setting'),
            ]:
                m = re.search(pattern, key_section)
                if m and field_name not in self.metadata:
                    self.metadata[field_name] = m.group(1).strip()

    def _parse_characters(self):
        """Extract character descriptions from ## 4) Characters or similar."""
        # Try V6 format first
        char_section = ""
        for header, content in self.sections.items():
            if 'Character' in header:
                char_section = content
                break

        if not char_section:
            # Try to find character descriptions in any section
            char_section = self.raw

        # Parse **NAME** - description blocks
        current_race = ""
        race_headers = re.finditer(r'###\s*(HUMANS?|ELVES?|DWARVES?|ENEMIES|CREATURES|MONSTERS|ORCS?|VILLAINS?|SUPPORTING)\b.*', char_section)
        race_ranges = []
        for m in race_headers:
            race_ranges.append((m.start(), m.group().strip()))

        for match in CHAR_DESC_RE.finditer(char_section):
            name = match.group(1).strip()
            desc = match.group(2).strip()

            # Skip stopwords
            if any(sw in name for sw in CASTING_STOPWORDS):
                continue

            # Determine race from section header
            race = ""
            pos = match.start()
            for rstart, rheader in race_ranges:
                if rstart < pos:
                    raw_race = rheader.split('(')[0].strip()
                    # Clean: remove ### prefix, trailing S, normalize
                    raw_race = re.sub(r'^#+\s*', '', raw_race).strip().lower()
                    # Normalize plural/variants
                    raw_race = raw_race.rstrip('s')  # HUMANS→HUMAN, ELVES→ELVE
                    RACE_NORM = {
                        'human': 'human', 'elve': 'elf', 'elf': 'elf',
                        'dwarve': 'dwarf', 'dwarf': 'dwarf',
                        'enemie': 'creature', 'enemy': 'creature',
                        'creature': 'creature', 'monster': 'creature',
                    }
                    race = RACE_NORM.get(raw_race, raw_race)

            # Extract structured fields from description
            age = ""
            gender = ""
            physical = ""
            wardrobe = ""
            props = ""

            # Age extraction
            age_m = re.search(r'(\d+)-year-old', desc)
            if age_m:
                age = age_m.group(1)

            # Gender extraction
            if re.search(r'\b(male|man|boy|he)\b', desc[:80], re.I):
                gender = "male"
            elif re.search(r'\b(female|woman|girl|she)\b', desc[:80], re.I):
                gender = "female"

            # Physical details (after age/gender, before first period)
            sentences = [s.strip() for s in desc.split('.') if s.strip()]
            physical_parts = []
            wardrobe_parts = []
            prop_parts = []

            wardrobe_words = {'wears', 'wearing', 'dressed', 'costume', 'armor', 'robe',
                            'leather', 'hide', 'tunic', 'cloak', 'collar', 'necklace',
                            'paint', 'braids', 'beard', 'hair'}
            prop_words = {'carries', 'carry', 'armed', 'weapon', 'staff', 'axe', 'sword',
                         'sickle', 'pick', 'horn', 'sack', 'bag', 'atlatl', 'hammer'}

            for sentence in sentences[1:]:  # Skip first sentence (usually age/role)
                sl = sentence.lower()
                if any(w in sl for w in prop_words):
                    prop_parts.append(sentence)
                elif any(w in sl for w in wardrobe_words):
                    wardrobe_parts.append(sentence)
                else:
                    physical_parts.append(sentence)

            # Clean multiline description
            desc_clean = re.sub(r'\s+', ' ', desc).strip()

            char = ExtractedCharacter(
                name=name,
                description=desc_clean,
                age=age,
                gender=gender,
                race=race,
                physical='. '.join(physical_parts),
                wardrobe='. '.join(wardrobe_parts),
                props='. '.join(prop_parts),
            )
            self.characters[name] = char

    def _parse_aliases(self):
        """Parse alias mappings (NAME = ALIAS = ALIAS2)."""
        # Look for Aliases section
        alias_section = ""
        alias_idx = self.raw.find('## Aliases')
        if alias_idx < 0:
            alias_idx = self.raw.find('Aliases\n')
        if alias_idx >= 0:
            end = self.raw.find('##', alias_idx + 5)
            if end < 0:
                end = self.raw.find('---', alias_idx + 5)
            alias_section = self.raw[alias_idx:end] if end > 0 else self.raw[alias_idx:alias_idx+2000]

        for match in ALIAS_RE.finditer(alias_section):
            canonical = match.group(1).strip()
            aliases_str = match.group(2).strip()
            for alias in re.split(r'\s*=\s*', aliases_str):
                alias = alias.strip()
                if alias and alias != canonical:
                    self.aliases[alias] = canonical
                    # Also add to character if exists
                    if canonical in self.characters:
                        self.characters[canonical].aliases.append(alias)

    def _parse_scene_cards(self):
        """Parse scene cards with purpose, characters, beats."""
        card_section = ""
        for header, content in self.sections.items():
            if 'Scene Card' in header:
                card_section = content
                break

        if not card_section:
            return

        for match in SCENE_CARD_RE.finditer(card_section):
            num = match.group(1).zfill(3)
            location = match.group(2).strip()
            body = match.group(3).strip()

            scene = ExtractedScene(
                scene_number=num,
                location=location,
            )

            # Parse INT/EXT from location
            loc_upper = location.upper()
            if loc_upper.startswith('INT'):
                scene.int_ext = 'INT'
            elif loc_upper.startswith('EXT'):
                scene.int_ext = 'EXT'

            # Parse time of day
            for tod in ['DAY', 'NIGHT', 'EVENING', 'MORNING', 'DUSK', 'DAWN']:
                if tod in loc_upper:
                    scene.time_of_day = tod
                    break

            # Parse purpose and characters from body
            for line in body.split('\n'):
                line = line.strip()
                if line.startswith('Purpose:'):
                    scene.purpose = line.replace('Purpose:', '').strip()
                elif line.startswith('Characters:'):
                    char_str = line.replace('Characters:', '').strip()
                    scene.characters = [c.strip() for c in char_str.split(',') if c.strip()]

            self.scenes[num] = scene

    def _parse_beat_summary(self):
        """Parse act outline / beat summary."""
        beat_section = ""
        for header, content in self.sections.items():
            if 'Act Outline' in header or 'Beat Summary' in header:
                beat_section = content
                break

        if not beat_section:
            return

        current_act = ""
        for line in beat_section.split('\n'):
            line = line.strip()
            act_m = re.match(r'\*\*ACT\s+(\w+)', line)
            if act_m:
                current_act = act_m.group(1)
                self.beats_by_act[current_act] = []
                continue

            beat_m = BEAT_RE.match(line)
            if beat_m and current_act:
                location = beat_m.group(1) or ""
                description = beat_m.group(2).strip()

                # Extract character names from description
                chars = []
                for name in self.characters:
                    if name.upper() in description.upper():
                        chars.append(name)

                beat = ExtractedBeat(
                    description=description,
                    location=location,
                    characters=chars,
                )
                self.beats_by_act[current_act].append(beat)

    def _parse_screenplay(self):
        """Parse the actual screenplay text for dialogue and action."""
        screenplay = self.sections.get('_screenplay', '')
        if not screenplay:
            return

        # Split into scenes by INT./EXT. headings
        scene_splits = list(SCENE_HEADING_RE.finditer(screenplay))

        for i, heading_match in enumerate(scene_splits):
            heading = heading_match.group(1).strip()
            start = heading_match.end()
            end = scene_splits[i + 1].start() if i + 1 < len(scene_splits) else len(screenplay)
            scene_text = screenplay[start:end].strip()

            # Determine scene number from sequential order
            scene_num = str(i + 1).zfill(3)

            # Get or create scene
            if scene_num not in self.scenes:
                self.scenes[scene_num] = ExtractedScene(
                    scene_number=scene_num,
                    location=heading,
                )
            scene = self.scenes[scene_num]
            scene.action_text = scene_text[:500]  # First 500 chars as atmosphere

            # Parse INT/EXT
            heading_upper = heading.upper()
            if heading_upper.startswith('INT'):
                scene.int_ext = 'INT'
            elif heading_upper.startswith('EXT'):
                scene.int_ext = 'EXT'

            # Extract dialogue from scene text
            self._extract_scene_dialogue(scene_num, scene_text)

            # Extract action beats
            self._extract_scene_beats(scene_num, scene_text)

            # Build atmosphere from first action paragraph
            first_para = scene_text.split('\n\n')[0] if scene_text else ""
            if first_para and not first_para.isupper():
                scene.atmosphere = re.sub(r'\s+', ' ', first_para).strip()[:300]

    def _extract_scene_dialogue(self, scene_num: str, text: str):
        """Extract dialogue lines from scene text."""
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check if this is a character name (ALL CAPS, possibly with parenthetical)
            if line and line.isupper() and len(line) < 50:
                # Clean character name
                char_name = re.sub(r'\s*\(.*?\)\s*', '', line).strip()

                # Skip stopwords
                if any(sw in char_name for sw in CASTING_STOPWORDS):
                    i += 1
                    continue

                # Resolve alias
                char_name = self.aliases.get(char_name, char_name)

                # Check for parenthetical on next line
                parenthetical = ""
                dialogue_text = ""
                j = i + 1

                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    if next_line.startswith('(') and next_line.endswith(')'):
                        parenthetical = next_line[1:-1]
                    elif not next_line.isupper():
                        dialogue_text += (" " if dialogue_text else "") + next_line
                    else:
                        break
                    j += 1

                if dialogue_text:
                    dlg = ExtractedDialogue(
                        character=char_name,
                        line=dialogue_text.strip(),
                        parenthetical=parenthetical,
                        scene_number=scene_num,
                    )
                    self.dialogue.append(dlg)

                    # Add to scene
                    if scene_num in self.scenes:
                        self.scenes[scene_num].dialogue.append(dlg)

                    i = j
                    continue
            i += 1

    def _extract_scene_beats(self, scene_num: str, text: str):
        """Extract action beats from scene text (non-dialogue paragraphs)."""
        paragraphs = text.split('\n\n')
        scene = self.scenes.get(scene_num)
        if not scene:
            return

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Skip if it's a character name + dialogue block
            first_line = para.split('\n')[0].strip()
            if first_line.isupper() and len(first_line) < 50:
                # This is likely a dialogue block
                continue

            # Skip very short lines (transitions, etc.)
            if len(para) < 20:
                continue

            # This is an action paragraph
            # Extract characters mentioned
            chars = []
            for name in list(self.characters.keys()) + list(self.aliases.keys()):
                if re.search(r'\b' + re.escape(name) + r'\b', para, re.I):
                    canonical = self.aliases.get(name, name)
                    if canonical not in chars:
                        chars.append(canonical)

            beat = ExtractedBeat(
                description=re.sub(r'\s+', ' ', para).strip()[:300],
                characters=chars,
                location=scene.location,
                scene_number=scene_num,
                is_action=True,
            )
            scene.beats.append(beat)

    def get_summary(self) -> Dict:
        """Get extraction summary."""
        total_dialogue = len(self.dialogue)
        total_beats = sum(len(s.beats) for s in self.scenes.values())
        total_chars = len(self.characters)
        chars_with_desc = sum(1 for c in self.characters.values() if len(c.description) > 10)

        return {
            "characters_found": total_chars,
            "characters_with_descriptions": chars_with_desc,
            "scenes_found": len(self.scenes),
            "total_dialogue_lines": total_dialogue,
            "total_action_beats": total_beats,
            "aliases_found": len(self.aliases),
            "beats_by_act": {act: len(beats) for act, beats in self.beats_by_act.items()},
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════════
# AUTO-ADVANCEMENT ENGINE — Fill Pipeline Gaps
# ═══════════════════════════════════════════════════════════════════

class ScriptAutoAdvancer:
    """
    Compares extracted script data against pipeline state (story_bible + shot_plan)
    and fills every empty field.

    Universal — works on ANY content type:
      - Full screenplays: fills characters, beats, dialogue, atmosphere
      - Concepts: creates outline structure, suggests scenes
      - Promos: maps talent to shots, fills wardrobe/look cues
      - Social: creates hook/body/CTA structure
    """

    def __init__(self, project_path: Path, parsed: ScriptParser):
        self.project_path = Path(project_path)
        self.parsed = parsed
        self.report = AdvancementReport()

        # Load current pipeline state
        self.story_bible = self._load_json('story_bible.json')
        self.shot_plan = self._load_json('shot_plan.json')
        self.cast_map = self._load_json('cast_map.json')

    def _load_json(self, filename: str) -> Dict:
        fp = self.project_path / filename
        if fp.exists():
            try:
                return json.load(open(fp))
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        return {}

    def _save_json(self, filename: str, data: Dict):
        fp = self.project_path / filename
        with open(fp, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def advance(self, dry_run: bool = False) -> Dict:
        """
        Run full auto-advancement pipeline.
        Returns report of all changes made.
        """
        self._fill_characters()
        self._fill_scene_data()
        self._fill_shot_beats()
        self._fill_dialogue()
        self._fill_atmosphere()
        self._fill_aliases()
        self._fill_wardrobe_cues()
        self._fill_prop_cues()

        self.report.total_changes = (
            self.report.characters_filled +
            self.report.characters_created +
            self.report.beats_filled +
            self.report.dialogue_recovered +
            self.report.scenes_enriched +
            self.report.aliases_mapped +
            self.report.props_extracted +
            self.report.wardrobe_cues +
            self.report.atmosphere_added
        )

        if not dry_run and self.report.total_changes > 0:
            self._save_json('story_bible.json', self.story_bible)
            self._save_json('shot_plan.json', self.shot_plan)

            # Invalidate UI cache
            cache_dir = self.project_path / 'ui_cache'
            if cache_dir.exists():
                dirty = cache_dir / '.dirty'
                dirty.write_text('auto-advanced')

            self.report.details.append(f"Saved story_bible.json and shot_plan.json")

        return {
            "success": True,
            "dry_run": dry_run,
            "report": {
                "characters_filled": self.report.characters_filled,
                "characters_created": self.report.characters_created,
                "beats_filled": self.report.beats_filled,
                "dialogue_recovered": self.report.dialogue_recovered,
                "scenes_enriched": self.report.scenes_enriched,
                "aliases_mapped": self.report.aliases_mapped,
                "props_extracted": self.report.props_extracted,
                "wardrobe_cues": self.report.wardrobe_cues,
                "atmosphere_added": self.report.atmosphere_added,
                "total_changes": self.report.total_changes,
                "details": self.report.details,
            },
            "extraction_summary": self.parsed.get_summary(),
        }

    # ── CHARACTER FILLING ──────────────────────────────────────────

    def _fill_characters(self):
        """Fill empty character descriptions from parsed script."""
        sb_chars = self.story_bible.get('characters', [])

        # Handle both list and dict formats
        if isinstance(sb_chars, dict):
            sb_chars_list = []
            for name, data in sb_chars.items():
                if isinstance(data, dict):
                    data['name'] = name
                    sb_chars_list.append(data)
            sb_chars = sb_chars_list

        # Build lookup by name (case-insensitive)
        sb_lookup = {}
        for char in sb_chars:
            if isinstance(char, dict):
                name = char.get('name', '').upper()
                sb_lookup[name] = char

        # Fill existing characters with empty descriptions
        for parsed_name, parsed_char in self.parsed.characters.items():
            name_upper = parsed_name.upper()

            if name_upper in sb_lookup:
                sb_char = sb_lookup[name_upper]
                existing_desc = sb_char.get('description', '')

                if not existing_desc or len(existing_desc) < 10:
                    sb_char['description'] = parsed_char.description
                    if parsed_char.age:
                        sb_char['age'] = parsed_char.age
                    if parsed_char.gender:
                        sb_char['gender'] = parsed_char.gender
                    if parsed_char.race:
                        sb_char['race'] = parsed_char.race
                    if parsed_char.physical:
                        sb_char['physical_description'] = parsed_char.physical
                    if parsed_char.wardrobe:
                        sb_char['wardrobe_description'] = parsed_char.wardrobe
                    if parsed_char.props:
                        sb_char['props'] = parsed_char.props
                    if parsed_char.aliases:
                        sb_char['aliases'] = parsed_char.aliases

                    self.report.characters_filled += 1
                    self.report.details.append(
                        f"FILLED character {parsed_name}: {parsed_char.description[:60]}..."
                    )
            else:
                # Character in script but not in pipeline — create it
                new_char = {
                    'name': parsed_name,
                    'description': parsed_char.description,
                    'age': parsed_char.age,
                    'gender': parsed_char.gender,
                    'race': parsed_char.race,
                    'physical_description': parsed_char.physical,
                    'wardrobe_description': parsed_char.wardrobe,
                    'props': parsed_char.props,
                    'aliases': parsed_char.aliases,
                }
                sb_chars.append(new_char)
                self.report.characters_created += 1
                self.report.details.append(
                    f"CREATED character {parsed_name}: {parsed_char.description[:60]}..."
                )

        # Write back as list
        self.story_bible['characters'] = sb_chars

    # ── SCENE DATA FILLING ─────────────────────────────────────────

    def _fill_scene_data(self):
        """Enrich scene entries with purpose, characters, atmosphere."""
        sb_scenes = self.story_bible.get('scenes', [])

        if isinstance(sb_scenes, dict):
            sb_scenes_list = []
            for sid, data in sb_scenes.items():
                if isinstance(data, dict):
                    data['scene_id'] = sid
                    sb_scenes_list.append(data)
            sb_scenes = sb_scenes_list

        sb_lookup = {}
        for scene in sb_scenes:
            if isinstance(scene, dict):
                sid = scene.get('scene_id', scene.get('id', ''))
                sb_lookup[sid] = scene

        for parsed_num, parsed_scene in self.parsed.scenes.items():
            if parsed_num in sb_lookup:
                sb_scene = sb_lookup[parsed_num]
                changed = False

                # Fill purpose
                if not sb_scene.get('purpose') and parsed_scene.purpose:
                    sb_scene['purpose'] = parsed_scene.purpose
                    changed = True

                # Fill characters list
                if (not sb_scene.get('characters') or len(sb_scene.get('characters', [])) == 0) and parsed_scene.characters:
                    sb_scene['characters'] = parsed_scene.characters
                    changed = True

                # Fill atmosphere
                if not sb_scene.get('atmosphere') and parsed_scene.atmosphere:
                    sb_scene['atmosphere'] = parsed_scene.atmosphere
                    changed = True

                # Fill int/ext
                if not sb_scene.get('int_ext') and parsed_scene.int_ext:
                    sb_scene['int_ext'] = parsed_scene.int_ext
                    changed = True

                # Fill time_of_day
                if not sb_scene.get('time_of_day') and parsed_scene.time_of_day:
                    sb_scene['time_of_day'] = parsed_scene.time_of_day
                    changed = True

                # Fill beats from screenplay parsing
                existing_beats = sb_scene.get('beats', [])
                if len(existing_beats) <= 1 and len(parsed_scene.beats) > 1:
                    # Current scene has only the default establishing beat
                    # Add real beats from screenplay
                    new_beats = []
                    for beat in parsed_scene.beats:
                        new_beats.append({
                            'description': beat.description,
                            'characters': beat.characters,
                            'is_action': beat.is_action,
                        })
                    # Keep existing beats and add new ones
                    sb_scene['beats'] = existing_beats + new_beats
                    self.report.beats_filled += len(new_beats)
                    changed = True
                    self.report.details.append(
                        f"FILLED scene {parsed_num}: +{len(new_beats)} beats from screenplay"
                    )

                # Fill dialogue count
                if parsed_scene.dialogue:
                    sb_scene['dialogue_count'] = len(parsed_scene.dialogue)
                    sb_scene['dialogue_characters'] = list(set(
                        d.character for d in parsed_scene.dialogue
                    ))

                if changed:
                    self.report.scenes_enriched += 1

        self.story_bible['scenes'] = sb_scenes

    # ── SHOT BEAT FILLING ──────────────────────────────────────────

    def _fill_shot_beats(self):
        """Fill empty shot descriptions with proportionally-mapped beats."""
        shots = self.shot_plan.get('shots', [])
        if not shots:
            return

        # Group shots by scene
        scene_shots = {}
        for i, shot in enumerate(shots):
            sid = shot.get('shot_id', '')[:3]
            if sid not in scene_shots:
                scene_shots[sid] = []
            scene_shots[sid].append((i, shot))

        for scene_id, shot_list in scene_shots.items():
            parsed_scene = self.parsed.scenes.get(scene_id)
            if not parsed_scene:
                continue

            # Combine all beats from this scene
            all_beats = parsed_scene.beats
            if not all_beats:
                continue

            n_shots = len(shot_list)
            n_beats = len(all_beats)

            for shot_idx, (global_idx, shot) in enumerate(shot_list):
                desc = shot.get('description', '')

                # Only fill if description is empty or very short
                if desc and len(desc) > 20:
                    continue

                # Proportional mapping
                beat_idx = int(shot_idx * n_beats / n_shots) if n_shots > 0 else 0
                beat_idx = min(beat_idx, n_beats - 1)
                beat = all_beats[beat_idx]

                # Fill description
                shot['description'] = beat.description

                # Fill characters from beat if shot has none
                if not shot.get('characters') and beat.characters:
                    shot['characters'] = beat.characters

                self.report.beats_filled += 1

        self.shot_plan['shots'] = shots

    # ── DIALOGUE FILLING ───────────────────────────────────────────

    def _fill_dialogue(self):
        """Fill dialogue_text fields from parsed screenplay dialogue."""
        shots = self.shot_plan.get('shots', [])
        if not shots:
            return

        # Group dialogue by scene
        dialogue_by_scene = {}
        for dlg in self.parsed.dialogue:
            sn = dlg.scene_number
            if sn not in dialogue_by_scene:
                dialogue_by_scene[sn] = []
            dialogue_by_scene[sn].append(dlg)

        # Group shots by scene
        scene_shots = {}
        for i, shot in enumerate(shots):
            sid = shot.get('shot_id', '')[:3]
            if sid not in scene_shots:
                scene_shots[sid] = []
            scene_shots[sid].append((i, shot))

        for scene_id, shot_list in scene_shots.items():
            scene_dialogue = dialogue_by_scene.get(scene_id, [])
            if not scene_dialogue:
                continue

            n_shots = len(shot_list)
            n_dlg = len(scene_dialogue)

            # Distribute dialogue proportionally to shots that don't have any
            for shot_idx, (global_idx, shot) in enumerate(shot_list):
                if shot.get('dialogue_text') or shot.get('dialogue'):
                    continue

                # Skip b-roll and insert shots
                shot_type = shot.get('shot_type', shot.get('type', ''))
                if shot_type in ('b-roll', 'insert', 'establishing', 'detail'):
                    continue

                # Map to dialogue lines
                dlg_start = int(shot_idx * n_dlg / n_shots)
                dlg_end = int((shot_idx + 1) * n_dlg / n_shots)
                dlg_end = max(dlg_end, dlg_start + 1)

                assigned_dialogue = scene_dialogue[dlg_start:dlg_end]
                if assigned_dialogue:
                    # Format as character attribution
                    dlg_parts = []
                    for d in assigned_dialogue[:3]:  # Max 3 lines per shot
                        text = d.line[:200]  # Truncate long dialogue
                        dlg_parts.append(f"{d.character}: \"{text}\"")

                    shot['dialogue_text'] = '; '.join(dlg_parts)

                    # Also update characters if missing
                    if not shot.get('characters'):
                        shot['characters'] = list(set(d.character for d in assigned_dialogue))

                    self.report.dialogue_recovered += 1

        self.shot_plan['shots'] = shots

    # ── ATMOSPHERE FILLING ─────────────────────────────────────────

    def _fill_atmosphere(self):
        """Fill scene atmosphere from screenplay opening paragraphs."""
        sb_scenes = self.story_bible.get('scenes', [])
        if isinstance(sb_scenes, list):
            for scene in sb_scenes:
                if isinstance(scene, dict):
                    sid = scene.get('scene_id', scene.get('id', ''))
                    parsed = self.parsed.scenes.get(sid)
                    if parsed and parsed.atmosphere and not scene.get('atmosphere'):
                        scene['atmosphere'] = parsed.atmosphere
                        self.report.atmosphere_added += 1
                        self.report.details.append(
                            f"ATMOSPHERE scene {sid}: {parsed.atmosphere[:60]}..."
                        )
        self.story_bible['scenes'] = sb_scenes

    # ── ALIAS FILLING ──────────────────────────────────────────────

    def _fill_aliases(self):
        """Add alias mappings to story bible."""
        if self.parsed.aliases:
            existing_aliases = self.story_bible.get('aliases', {})
            for alias, canonical in self.parsed.aliases.items():
                if alias not in existing_aliases:
                    existing_aliases[alias] = canonical
                    self.report.aliases_mapped += 1
            self.story_bible['aliases'] = existing_aliases

    # ── WARDROBE CUE FILLING ──────────────────────────────────────

    def _fill_wardrobe_cues(self):
        """Extract wardrobe cues from character descriptions."""
        sb_chars = self.story_bible.get('characters', [])
        if isinstance(sb_chars, list):
            for char in sb_chars:
                if isinstance(char, dict):
                    name = char.get('name', '').upper()
                    parsed = self.parsed.characters.get(name)
                    if parsed and parsed.wardrobe and not char.get('wardrobe_description'):
                        char['wardrobe_description'] = parsed.wardrobe
                        self.report.wardrobe_cues += 1
        self.story_bible['characters'] = sb_chars

    # ── PROP CUE FILLING ──────────────────────────────────────────

    def _fill_prop_cues(self):
        """Extract prop lists from character descriptions."""
        sb_chars = self.story_bible.get('characters', [])
        if isinstance(sb_chars, list):
            for char in sb_chars:
                if isinstance(char, dict):
                    name = char.get('name', '').upper()
                    parsed = self.parsed.characters.get(name)
                    if parsed and parsed.props and not char.get('props'):
                        char['props'] = parsed.props
                        self.report.props_extracted += 1
        self.story_bible['characters'] = sb_chars


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API — Called by orchestrator_server.py
# ═══════════════════════════════════════════════════════════════════

def auto_advance_script(
    project_path,
    script_text: str = None,
    dry_run: bool = False,
) -> Dict:
    """
    Auto-advance a script by parsing it and filling pipeline gaps.

    Args:
        project_path: Path to pipeline_outputs/{project}/
        script_text: Optional override script text. If None, reads imported_script.txt
        dry_run: If True, report changes without writing files

    Returns:
        Dict with success, report, extraction_summary
    """
    project_path = Path(project_path)

    # Load script text
    if not script_text:
        script_file = project_path / 'imported_script.txt'
        if script_file.exists():
            script_text = script_file.read_text()
        else:
            return {
                "success": False,
                "error": "No imported_script.txt found and no script_text provided",
            }

    if len(script_text.strip()) < 50:
        return {
            "success": False,
            "error": f"Script too short ({len(script_text)} chars) — need at least 50 chars",
        }

    # Parse
    parsed = ScriptParser(script_text)

    # Advance
    advancer = ScriptAutoAdvancer(project_path, parsed)
    result = advancer.advance(dry_run=dry_run)

    return result


def parse_script_only(script_text: str) -> Dict:
    """
    Parse a script without touching pipeline files.
    Useful for preview/validation before advancing.
    """
    parsed = ScriptParser(script_text)
    return {
        "success": True,
        "summary": parsed.get_summary(),
        "characters": {
            name: {
                "description": c.description[:200],
                "age": c.age,
                "gender": c.gender,
                "race": c.race,
                "aliases": c.aliases,
            }
            for name, c in parsed.characters.items()
        },
        "scenes": {
            num: {
                "location": s.location,
                "purpose": s.purpose,
                "characters": s.characters,
                "beat_count": len(s.beats),
                "dialogue_count": len(s.dialogue),
                "atmosphere": s.atmosphere[:100] if s.atmosphere else "",
            }
            for num, s in parsed.scenes.items()
        },
    }
