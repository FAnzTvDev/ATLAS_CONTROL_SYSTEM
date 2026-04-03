"""
V6 HEADER PARSER — STORY BIBLE INGEST ENGINE
=============================================
V21.10: Parses V6 script format headers into structured story_bible.json data.

The V6 format has rich metadata ABOVE the ---SCREENPLAY--- marker:
  1) Story Bible — title, genre, logline, tone, runtime, setting
  2) Act Outline / Beat Summary — per-act beat breakdowns
  3) Scene Cards — per-scene purpose + characters
  4) Characters — detailed descriptions grouped by faction/race
  5) Aliases — character name mappings
  6) Casting Stopwords — words to ignore during character detection

This parser extracts ALL of this into structured JSON that becomes
story_bible.json — INSTEAD of having an LLM reinvent it from scratch.

The key insight: if the V6 header exists, INGEST it. If not, GENERATE.

Usage:
    from tools.v6_header_parser import parse_v6_header, has_v6_header

    if has_v6_header(script_text):
        header_data = parse_v6_header(script_text)
        # header_data contains: metadata, characters, scene_cards, aliases,
        # stopwords, act_outline, screenplay_text
    else:
        # Fall back to LLM generation
        ...
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

logger = logging.getLogger("atlas.v6_header_parser")

# ============================================================================
# V6 HEADER DETECTION
# ============================================================================

V6_SEPARATOR = "---SCREENPLAY---"

def has_v6_header(script_text: str) -> bool:
    """Check if script text contains a V6 format header."""
    return V6_SEPARATOR in script_text


def split_header_and_screenplay(script_text: str) -> Tuple[str, str]:
    """Split V6 script into header and screenplay sections."""
    if V6_SEPARATOR in script_text:
        parts = script_text.split(V6_SEPARATOR, 1)
        return parts[0].strip(), parts[1].strip()
    return "", script_text.strip()


# ============================================================================
# SECTION PARSERS
# ============================================================================

def _extract_metadata(header: str) -> Dict[str, Any]:
    """Extract top-level metadata: title, genre, logline, tone, runtime, setting."""
    metadata = {}

    # Series Title (check first, as it's the canonical title)
    m = re.search(r'\*{0,2}Series Title:\*{0,2}\s*(.+)', header)
    if m:
        metadata["series_title"] = m.group(1).strip()
        metadata["title"] = m.group(1).strip()
    else:
        # Title: first non-empty line
        lines = header.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('=') and not line.startswith('V6'):
                metadata["title"] = re.sub(r'\*+', '', line).strip()
                break

    # Episode
    m = re.search(r'\*{0,2}Episode:\*{0,2}\s*(.+)', header)
    if m:
        metadata["episode"] = m.group(1).strip()
        # Try to extract season/episode numbers — supports "Season 1 Episode 1" and "S01E01"
        ep_match = re.search(r'Season\s+(\d+).*Episode\s+(\d+)', m.group(1))
        if not ep_match:
            ep_match = re.search(r'S(\d+)E(\d+)', m.group(1))
        if ep_match:
            metadata["season_number"] = int(ep_match.group(1))
            metadata["episode_number"] = int(ep_match.group(2))

    # Written By
    m = re.search(r'\*{0,2}Written By:\*{0,2}\s*(.+)', header)
    if m:
        metadata["written_by"] = m.group(1).strip()

    # Genre
    m = re.search(r'\*{0,2}Genre:\*{0,2}\s*(.+)', header)
    if m:
        metadata["genre"] = m.group(1).strip()

    # Logline
    m = re.search(r'\*{0,2}Logline:\*{0,2}\s*(.+)', header, re.DOTALL)
    if m:
        # Logline can be multi-line — grab until next "- **" or blank line
        logline_text = m.group(1).strip()
        # Truncate at next field marker
        logline_text = re.split(r'\n\s*-\s*\*\*', logline_text)[0].strip()
        metadata["logline"] = logline_text

    # Tone
    m = re.search(r'\*{0,2}Tone:\*{0,2}\s*(.+)', header, re.DOTALL)
    if m:
        tone_text = m.group(1).strip()
        tone_text = re.split(r'\n\s*-\s*\*\*', tone_text)[0].strip()
        metadata["tone"] = tone_text

    # Runtime Target — supports "Runtime Target: 45 minutes", "Target Runtime: 45 min", etc.
    m = re.search(r'\*{0,2}(?:Runtime Target|Target Runtime):\*{0,2}\s*(\d+)\s*min', header, re.IGNORECASE)
    if m:
        metadata["runtime_minutes"] = int(m.group(1))
    else:
        # Try alternate patterns
        m = re.search(r'(\d+)\s*minutes?\s*\(', header)
        if m:
            metadata["runtime_minutes"] = int(m.group(1))

    # Setting
    m = re.search(r'\*{0,2}Setting:\*{0,2}\s*(.+)', header, re.DOTALL)
    if m:
        setting_text = m.group(1).strip()
        setting_text = re.split(r'\n\s*-\s*\*\*', setting_text)[0].strip()
        metadata["setting"] = setting_text

    return metadata


def _extract_act_outline(header: str) -> List[Dict[str, Any]]:
    """Extract act outline / beat summary."""
    acts = []

    # Find act outline section — supports both markdown (## Act Outline) and plain text (ACT OUTLINE:)
    act_section = re.search(
        r'(?:##\s*\d*\)?\s*Act Outline|##\s*\d*\)?\s*Beat Summary|ACT\s+OUTLINE\s*:|BEAT\s+SUMMARY\s*:)(.*?)(?=SCENE\s+CARDS\s*:|##\s|CHARACTERS\s*:|\Z)',
        header, re.DOTALL | re.IGNORECASE
    )
    if not act_section:
        return acts

    text = act_section.group(1)

    # Parse each act — supports "ACT ONE", "ACT I", "ACT 1", with optional title and scene range
    act_blocks = re.split(
        r'\*{0,2}(ACT\s+(?:ONE|TWO|THREE|FOUR|FIVE|I{1,3}|IV|V|1|2|3|4|5))\s*(?:[-–—]\s*[^\n]*)?\*{0,2}',
        text
    )

    for i in range(1, len(act_blocks), 2):
        act_name = act_blocks[i].strip()
        act_content = act_blocks[i + 1] if i + 1 < len(act_blocks) else ""

        beats = []
        for line in act_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Match bullet points (- or •) OR numbered beats (1. or 1:)
            beat_text = None
            if line.startswith('-') or line.startswith('•'):
                beat_text = re.sub(r'^[-•]\s*', '', line)
            elif re.match(r'^\d+[\.\)]\s+', line):
                beat_text = re.sub(r'^\d+[\.\)]\s+', '', line)

            if beat_text:
                # Extract location if present (LOCATION: description) — but skip very short "labels"
                loc_match = re.match(r'([A-Z][A-Z\s/]+?):\s*(.+)', beat_text)
                if loc_match and len(loc_match.group(1)) > 3:
                    beats.append({
                        "location": loc_match.group(1).strip(),
                        "description": loc_match.group(2).strip()
                    })
                else:
                    beats.append({"description": beat_text})

        acts.append({
            "act": act_name,
            "beats": beats
        })

    return acts


def _extract_scene_cards(header: str) -> List[Dict[str, Any]]:
    """Extract scene cards with purpose and characters."""
    cards = []

    # Find scene cards section — supports both markdown (## Scene Cards) and plain text (SCENE CARDS:)
    # IMPORTANT: Terminator must match CHARACTERS: as a standalone section header (start of line, all caps)
    # NOT the "Characters:" field inside individual scene cards
    scene_section = re.search(
        r'(?:##\s*\d*\)?\s*Scene Cards|##\s*\d*\)?\s*Scene Breakdown|SCENE\s+CARDS\s*:|SCENE\s+BREAKDOWN\s*:)(.*?)(?=\nCHARACTERS\s*:\s*\n|##\s*\d*\)?\s*Characters|\Z)',
        header, re.DOTALL
    )
    if not scene_section:
        return cards

    text = scene_section.group(1)

    # Parse each scene card
    # Pattern: **Scene N - LOCATION** (markdown) OR Scene 001 — INT. LOCATION - TIME (plain text)
    scene_blocks = re.split(
        r'\*{0,2}Scene\s+(\d+)\s*[-–—]\s*(.*?)\*{0,2}\s*\n',
        text,
        flags=re.IGNORECASE
    )

    for i in range(1, len(scene_blocks), 3):
        scene_num = int(scene_blocks[i])
        scene_header = scene_blocks[i + 1].strip() if i + 1 < len(scene_blocks) else ""
        scene_body = scene_blocks[i + 2] if i + 2 < len(scene_blocks) else ""

        card = {
            "scene_number": scene_num,
            "scene_id": f"{scene_num:03d}",
            "header": scene_header
        }

        # Extract Purpose
        m = re.search(r'Purpose:\s*(.+)', scene_body)
        if m:
            card["purpose"] = m.group(1).strip()

        # Extract Characters
        m = re.search(r'Characters?:\s*(.+)', scene_body)
        if m:
            chars_text = m.group(1).strip()
            card["characters"] = [c.strip() for c in re.split(r',\s*', chars_text) if c.strip()]

        cards.append(card)

    return cards


def _extract_characters(header: str) -> List[Dict[str, Any]]:
    """
    Extract character descriptions grouped by faction/race.
    Handles the V6 format:
        ### GROUP NAME (physical description)
        **NAME** - description
    """
    characters = []
    current_group = None
    current_group_traits = ""

    # Find characters section — supports both markdown (## Characters) and plain text (CHARACTERS:)
    char_section = re.search(
        r'(?:##\s*\d*\)?\s*Characters|CHARACTERS\s*:)(.*?)(?=ALIASES\s*:|CASTING\s+STOPWORDS\s*:|##\s*(?:\d*\)?\s*)?(?:Aliases|Casting)|---SCREENPLAY|\Z)',
        header, re.DOTALL | re.IGNORECASE
    )
    if not char_section:
        return characters

    text = char_section.group(1)

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Check for group header: ### GROUP NAME (traits)
        group_match = re.match(r'#{1,3}\s*(.+?)(?:\s*\((.+?)\))?\s*$', line)
        if group_match and not line.startswith('**'):
            current_group = re.sub(r'\*+', '', group_match.group(1)).strip()
            current_group_traits = group_match.group(2) or ""
            continue

        # Check for italic group note: *Body paint: white = adolescent...*
        if line.startswith('*') and not line.startswith('**'):
            if current_group:
                current_group_traits += " " + line.strip('* ')
            continue

        # Check for character entry: **NAME** - description  OR  NAME — description (plain text)
        # V21.10: Allow dots (DR.), parens (V.O.), and other punctuation in names
        char_match = re.match(r'\*{0,2}([A-Z][A-Z\s\'\-\.\(\)]+?)\*{0,2}\s*[-–—]+\s*(.+)', line)
        if char_match:
            name = char_match.group(1).strip()
            description = char_match.group(2).strip()

            char_data = {
                "name": name,
                "description": description,
                "source": "v6_header"
            }

            if current_group:
                char_data["group"] = current_group
                char_data["group_traits"] = current_group_traits.strip()

            # Try to extract age
            age_match = re.search(r'(\d+)-year-old', description)
            if age_match:
                char_data["age"] = int(age_match.group(1))

            # Try to extract gender
            if re.search(r'\b(female|woman|girl|she)\b', description, re.I):
                char_data["gender"] = "female"
            elif re.search(r'\b(male|man|boy|he)\b', description, re.I):
                char_data["gender"] = "male"

            # Try to extract role/title
            role_match = re.search(r'\b(apprentice|warrior|sage|priest|king|leader|hunter|scout|healer|cook|miner|smith|farmer|warden|beastmaster)\b', description, re.I)
            if role_match:
                char_data["role"] = role_match.group(1).capitalize()

            # Build visual_prompt from description + group traits
            visual_parts = [description]
            if current_group_traits:
                visual_parts.append(current_group_traits)
            char_data["visual_prompt"] = ". ".join(visual_parts)

            characters.append(char_data)

    return characters


def _extract_aliases(header: str) -> Dict[str, List[str]]:
    """Extract character aliases mapping."""
    aliases = {}

    # Find aliases section — supports both markdown (## Aliases) and plain text (ALIASES:)
    alias_section = re.search(
        r'(?:##\s*\d*\)?\s*Aliases|ALIASES\s*:)(.*?)(?=CASTING\s+STOPWORDS\s*:|##\s*\d*\)?\s*Casting|---SCREENPLAY|\Z)',
        header, re.DOTALL | re.IGNORECASE
    )
    if not alias_section:
        return aliases

    text = alias_section.group(1)

    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Pattern: NAME = ALIAS1 = ALIAS2
        parts = [p.strip() for p in re.split(r'\s*=\s*', line) if p.strip()]
        if len(parts) >= 2:
            primary = parts[0].upper()
            aliases[primary] = [p.upper() for p in parts[1:]]

    return aliases


def _extract_casting_stopwords(header: str) -> List[str]:
    """Extract casting stopwords."""
    stopwords = []

    # Find stopwords section — supports both markdown (## Casting Stopwords) and plain text (CASTING STOPWORDS:)
    stop_section = re.search(
        r'(?:##\s*\d*\)?\s*Casting Stopwords|CASTING\s+STOPWORDS\s*:)(.*?)(?=##\s|---SCREENPLAY|\Z)',
        header, re.DOTALL | re.IGNORECASE
    )
    if not stop_section:
        return stopwords

    text = stop_section.group(1).strip()

    # Split by commas
    for word in re.split(r',\s*', text):
        word = word.strip()
        if word:
            stopwords.append(word)

    return stopwords


# ============================================================================
# MAIN PARSER
# ============================================================================

def parse_v6_header(script_text: str) -> Dict[str, Any]:
    """
    Parse V6 script format header into structured data.

    Returns dict with:
        - metadata: title, genre, logline, tone, runtime, setting, etc.
        - characters: list of character dicts with descriptions + visual prompts
        - scene_cards: list of scene card dicts with purpose + characters
        - aliases: dict mapping primary name -> list of aliases
        - stopwords: list of casting stopwords
        - act_outline: list of act dicts with beat breakdowns
        - screenplay_text: the raw screenplay (everything after ---SCREENPLAY---)
        - has_v6_header: True
    """
    header, screenplay = split_header_and_screenplay(script_text)

    if not header:
        return {
            "has_v6_header": False,
            "screenplay_text": screenplay,
            "metadata": {},
            "characters": [],
            "scene_cards": [],
            "aliases": {},
            "stopwords": [],
            "act_outline": []
        }

    metadata = _extract_metadata(header)
    characters = _extract_characters(header)
    scene_cards = _extract_scene_cards(header)
    aliases = _extract_aliases(header)
    stopwords = _extract_casting_stopwords(header)
    act_outline = _extract_act_outline(header)

    result = {
        "has_v6_header": True,
        "screenplay_text": screenplay,
        "metadata": metadata,
        "characters": characters,
        "scene_cards": scene_cards,
        "aliases": aliases,
        "stopwords": stopwords,
        "act_outline": act_outline,
        "_parser_version": "V21.10",
        "_parsed_at": datetime.now().isoformat()
    }

    logger.info(
        f"[V6-PARSER] Parsed header: {len(characters)} characters, "
        f"{len(scene_cards)} scene cards, {len(aliases)} aliases, "
        f"{len(stopwords)} stopwords, {len(act_outline)} acts"
    )

    return result


# ============================================================================
# STORY BIBLE BUILDER (from V6 header data)
# ============================================================================

def build_story_bible_from_v6(parsed_header: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a story_bible.json from parsed V6 header data.

    This is the INGEST path — uses the author's actual data instead of
    having an LLM reinvent it from scratch.

    The LLM generate path should ONLY be used when has_v6_header is False.
    """
    meta = parsed_header.get("metadata", {})
    characters = parsed_header.get("characters", [])
    scene_cards = parsed_header.get("scene_cards", [])
    act_outline = parsed_header.get("act_outline", [])
    aliases = parsed_header.get("aliases", {})

    # Build characters array for story bible
    bible_characters = []
    for char in characters:
        bible_char = {
            "name": char["name"],
            "description": char.get("description", ""),
            "visual_prompt": char.get("visual_prompt", char.get("description", "")),
            "role": char.get("role", "supporting"),
            "source": "v6_header_ingest"
        }

        # Add optional fields
        if "age" in char:
            bible_char["age"] = char["age"]
        if "gender" in char:
            bible_char["gender"] = char["gender"]
        if "group" in char:
            bible_char["group"] = char["group"]
            bible_char["group_traits"] = char.get("group_traits", "")

        bible_characters.append(bible_char)

    # Build locations array from scene cards
    locations = []
    seen_locations = set()
    for card in scene_cards:
        header = card.get("header", "")
        # Parse INT./EXT. from header
        loc_match = re.match(r'(INT\.|EXT\.|INT/EXT\.)\s*(.+?)(?:\s*[-–—]\s*(.+))?$', header)
        if loc_match:
            loc_name = loc_match.group(2).strip()
            time_of_day = loc_match.group(3).strip() if loc_match.group(3) else "DAY"
        else:
            loc_name = header
            time_of_day = "DAY"

        if loc_name and loc_name.upper() not in seen_locations:
            seen_locations.add(loc_name.upper())
            locations.append({
                "name": loc_name,
                "time_of_day": time_of_day,
                "source": "v6_header_ingest"
            })

    # Build scenes array from scene cards + act outline
    scenes = []
    for card in scene_cards:
        scene = {
            "scene_id": card.get("scene_id", f"{card.get('scene_number', 0):03d}"),
            "header": card.get("header", ""),
            "purpose": card.get("purpose", ""),
            "characters": card.get("characters", []),
            "source": "v6_header_ingest"
        }

        # Parse location from header
        loc_match = re.match(r'(INT\.|EXT\.|INT/EXT\.)\s*(.+?)(?:\s*[-–—]\s*(.+))?$', card.get("header", ""))
        if loc_match:
            scene["int_ext"] = loc_match.group(1).replace('.', '').strip()
            scene["location"] = loc_match.group(2).strip()
            scene["time_of_day"] = loc_match.group(3).strip() if loc_match.group(3) else "DAY"

        scenes.append(scene)

    story_bible = {
        "title": meta.get("title", "Untitled"),
        "series_title": meta.get("series_title", meta.get("title", "Untitled")),
        "episode": meta.get("episode", ""),
        "episode_number": meta.get("episode_number", 1),
        "season_number": meta.get("season_number", 1),
        "written_by": meta.get("written_by", ""),
        "genre": meta.get("genre", "drama"),
        "logline": meta.get("logline", ""),
        "tone": meta.get("tone", "cinematic"),
        "setting": meta.get("setting", ""),
        "runtime_target_minutes": meta.get("runtime_minutes", 45),
        "runtime_target_seconds": meta.get("runtime_minutes", 45) * 60,

        "characters": bible_characters,
        "locations": locations,
        "scenes": scenes,
        "act_outline": act_outline,

        # Aliases are critical for character normalization in the pipeline
        "aliases": aliases,
        "casting_stopwords": parsed_header.get("stopwords", []),

        # Visual style (defaults — LLM can enrich later)
        "visual_style": {
            "aspect_ratio": "16:9",
            "color_palette": "cinematic",
            "lighting_style": "atmospheric"
        },

        # Metadata
        "_generated_by": "V6_HEADER_INGEST_V21.10",
        "_ingested": True,
        "_pipeline_imported": True,
        "_v6_header_parsed": True,
        "_timestamp": datetime.now().isoformat(),
        "_character_count": len(bible_characters),
        "_scene_card_count": len(scene_cards),
        "_alias_count": len(aliases),
        "_stopword_count": len(parsed_header.get("stopwords", []))
    }

    logger.info(
        f"[V6-INGEST] Built story bible: {len(bible_characters)} characters, "
        f"{len(locations)} locations, {len(scenes)} scenes, "
        f"{len(aliases)} alias mappings"
    )

    return story_bible


# ============================================================================
# SUPPLEMENTAL: SERIES BIBLE MERGER
# ============================================================================

def merge_series_bible(story_bible: Dict, series_bible_text: str) -> Dict:
    """
    Merge external series bible content into an existing story bible.

    For scripts like Kord that come with a full Series Bible PDF,
    this enriches the V6-ingested story bible with:
    - Extended character backgrounds
    - Multi-season arc context
    - Cultural/world-building details
    - Episode outlines

    Args:
        story_bible: Existing story bible (from V6 header ingest)
        series_bible_text: Raw text from series bible PDF

    Returns:
        Enriched story bible with series_bible_supplement field
    """
    story_bible["series_bible_supplement"] = {
        "raw_text": series_bible_text[:20000],  # Cap at 20K chars
        "source": "external_series_bible",
        "_merged_at": datetime.now().isoformat()
    }

    # Try to extract character profiles from series bible
    # These are richer than V6 header descriptions
    char_profiles = []
    # Pattern: character name followed by description paragraphs
    profile_blocks = re.split(r'\n(?=[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*[-–—:])', series_bible_text)
    for block in profile_blocks:
        if len(block) > 50:  # Skip short fragments
            first_line = block.split('\n')[0].strip()
            name_match = re.match(r'([A-Za-z\s]+?)[\s]*[-–—:](.+)', first_line)
            if name_match:
                char_profiles.append({
                    "name": name_match.group(1).strip().upper(),
                    "extended_profile": block.strip()[:2000]
                })

    if char_profiles:
        story_bible["series_bible_supplement"]["character_profiles"] = char_profiles

        # Cross-reference with existing characters and enrich
        existing_chars = {c["name"]: c for c in story_bible.get("characters", [])}
        for profile in char_profiles:
            if profile["name"] in existing_chars:
                existing_chars[profile["name"]]["extended_profile"] = profile["extended_profile"]
                existing_chars[profile["name"]]["_enriched_from_series_bible"] = True

    logger.info(
        f"[V6-MERGE] Merged series bible: {len(char_profiles)} character profiles found"
    )

    return story_bible


# ============================================================================
# CONVENIENCE: ONE-SHOT INGEST
# ============================================================================

def ingest_v6_script(
    script_text: str,
    series_bible_text: Optional[str] = None
) -> Tuple[Dict[str, Any], str]:
    """
    One-shot V6 script ingestion.

    Returns:
        (story_bible, screenplay_text) — story_bible is ready to save,
        screenplay_text is the raw screenplay for full-import parsing.
    """
    parsed = parse_v6_header(script_text)

    if not parsed["has_v6_header"]:
        return {}, script_text

    story_bible = build_story_bible_from_v6(parsed)

    if series_bible_text:
        story_bible = merge_series_bible(story_bible, series_bible_text)

    return story_bible, parsed["screenplay_text"]


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python v6_header_parser.py <script_file.txt>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        text = f.read()

    if has_v6_header(text):
        parsed = parse_v6_header(text)
        bible = build_story_bible_from_v6(parsed)

        print(f"\n{'='*60}")
        print(f"V6 HEADER PARSE RESULTS")
        print(f"{'='*60}")
        print(f"Title:      {bible.get('title', 'N/A')}")
        print(f"Genre:      {bible.get('genre', 'N/A')}")
        print(f"Runtime:    {bible.get('runtime_target_minutes', 'N/A')} min")
        print(f"Characters: {len(bible.get('characters', []))}")
        print(f"Locations:  {len(bible.get('locations', []))}")
        print(f"Scenes:     {len(bible.get('scenes', []))}")
        print(f"Aliases:    {len(bible.get('aliases', {}))}")
        print(f"Stopwords:  {len(bible.get('casting_stopwords', []))}")
        print(f"\nCharacters:")
        for c in bible.get("characters", []):
            group = f" [{c.get('group', '')}]" if c.get('group') else ""
            print(f"  - {c['name']}{group}: {c.get('description', '')[:80]}...")
        print(f"\nAliases:")
        for primary, alt_names in bible.get("aliases", {}).items():
            print(f"  {primary} = {', '.join(alt_names)}")
    else:
        print("No V6 header found in script.")
