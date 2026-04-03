#!/usr/bin/env python3
"""
PROMPT AUTHORITY GATE — V21.4 (UNIVERSAL + ALL ENDPOINTS)
======================================================
The LAST function to run before any prompt reaches nano-banana.
Strips ALL conflicting injections from 7 enrichment layers.
Enforces single-authority character descriptions, color grades,
performance directions, location descriptions, and prompt size.

V21.3 ADDITIONS (was V21):
- Processes BOTH nano_prompt AND ltx_motion_prompt (was nano only)
- Deduplicates "performance:" directives (keeps first, strips rest)
- Deduplicates "Setting:" blocks (keeps first)
- Deduplicates "composition:" blocks (keeps first)
- Deduplicates "Location:" blocks (keeps first)
- Deduplicates "emotion blend:" blocks (keeps first)
- Deduplicates "ACTING" blocks (keeps first)
- Deduplicates "DIALOGUE PERFORMANCE" blocks (keeps first)
- Strips scene-inappropriate atmosphere ("the house is watching" from non-001 scenes)
- Strips duplicate "face stable NO morphing" (keeps first)
- Caps nano_prompt at ~3000 chars, ltx_motion_prompt at ~1500 chars
- 92.5% of shots had contamination — now stripped

WHY THIS EXISTS:
The chain pipeline has 7 enrichment layers that each APPEND text without
checking what's already there. The result is prompts with:
- 3-8 conflicting descriptions of the same character
- 2-5 conflicting color grades
- 5-7 duplicate "performance:" directives per shot
- 5-6 duplicate location description blocks per shot
- "the house is watching" in 258 of 279 shots (including apartment scenes)
- AI actor descriptions that don't match the actual character
- nano_prompt tripled from ~2,500 chars (V9) to ~7,200 chars (V21)

This gate runs AFTER all enrichment and BEFORE generation.
It is the FINAL authority on what nano sees.

V21.4 ADDITIONS:
- NOW WIRED INTO ALL 4 ENDPOINTS (was only chain + turbo):
  1. Chain pipeline (line ~6793) — enforce_prompt_authority() on all scene shots
  2. Turbo endpoint (line ~19177) — enforce_prompt_authority() on all shots
  3. generate-first-frames (line ~18572) — _process_prompt() per-shot inline (NEW)
  4. render-videos (line ~27376) — _process_prompt() per-shot LTX inline (NEW)
- UNIVERSAL: Loads project-specific config from prompt_authority_config.json
  when present, falls back to hardcoded Ravencroft defaults
- load_project_authority_config() sets _PROJECT_CHARACTERS, _PROJECT_COLOR_GRADES

WIRING: Called from orchestrator_server.py at 4 integration points

Usage:
    from tools.prompt_authority_gate import enforce_prompt_authority
    enforce_prompt_authority(scene_shots, project_path, cast_map)
"""

import json
import re
import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger("atlas.prompt_authority_gate")

# Import project config system
try:
    from core.project_config import get_project_config, ProjectConfig
    HAS_PROJECT_CONFIG = True
except ImportError:
    HAS_PROJECT_CONFIG = False
    ProjectConfig = None

# ============================================================
# ACTIVE PROJECT CONFIGURATION (module-level mutable state)
# ============================================================
_active_config: Optional[ProjectConfig] = None

# ============================================================
# DEFAULT CANONICAL CHARACTER REGISTRY (Ravencroft)
# Used as fallback if project_config not loaded.
# Single source of truth per character. NO EXCEPTIONS.
# ============================================================

# These override EVERYTHING: AI actor descriptions, wardrobe agent,
# cinematic enricher, face-lock text, story bible, etc.

_DEFAULT_CANONICAL_CHARACTERS = {
    "LADY MARGARET RAVENCROFT": {
        "appearance": "regal woman in her 50s, commanding aristocratic presence, severe look on her face, elegant beauty with authority, silver-white hair pulled back tightly",
        "wardrobe_by_scene": {
            "001": "wearing elegant white robe, silver crescent pendant on thin chain, bare feet on cold stone, surrounded by shadowy robed figures in half-masks holding blood-red candles"
        },
        "negative": "NO modern clothing, NO casual wear, NO smiling, NO Italian description, NO operatic, NO dark hair",
        "strip_patterns": [
            r"ISABELLA\s+MORETTI[^.]*[.,]?\s*",
            r"Italian woman[^.]*[.,]?\s*",
            r"dark hair with silver streaks[^.]*[.,]?\s*",
            r"elegant updos?[^.,]*[.,]?\s*",
            r"silver severe bun[^.]*[.,]?\s*",
            r"Victorian mourning[^.]*[.,]?\s*",
            r"designer clothing[^.]*[.,]?\s*",
            r"operatic intensity[^.]*[.,]?\s*",
            r"perfect posture[^.,]*[.,]?\s*",
            r"deep brown expressive eyes[^.,]*[.,]?\s*",
            r"regal commanding presence[^.,]*[.,]?\s*",
            r"timeless elegance[^.,]*[.,]?\s*",
            r"age 55[^.,]*[.,]?\s*",
        ]
    },
    "EVELYN RAVENCROFT": {
        "appearance": "fairly attractive woman early 30s, on the thin side, looks a little tired around the edges, slender build, dark brown hair",
        "wardrobe_by_scene": {
            "002": "wearing oversized grey cardigan over white t-shirt, faded pyjama bottoms, bare feet, dark brown hair messily pulled back in loose bun",
            "003": "wearing dark navy peacoat over cream jumper, fitted jeans, brown leather boots, dark brown hair loosely tied back"
        },
        "negative": "NO hair color changes, NO hair style changes between shots in same scene, NO outfit changes between shots in same scene, NO blonde hair, NO red hair, NO short hair, NO auburn hair, NO English description, NO pre-Raphaelite",
        "strip_patterns": [
            r"CHARLOTTE\s+BEAUMONT[^.]*[.,]?\s*",
            r"English woman[^.]*[.,]?\s*",
            r"delicate ethereal[^.]*[.,]?\s*",
            r"pre-Raphaelite[^.]*[.,]?\s*",
            r"auburn waves[^.]*[.,]?\s*",
            r"grey-green haunted[^.]*[.,]?\s*",
            r"haunted melancholy eyes[^.]*[.,]?\s*",
            r"pale complexion[^.]*[.,]?\s*",
            r"Victorian-inspired[^.]*[.,]?\s*",
            r"dark romantic dress[^.]*[.,]?\s*",
            r"age 27[^.,]*[.,]?\s*",
            r"ethereal pre-Raphaelite build[^.,]*[.,]?\s*",
            r"flowing auburn[^.,]*[.,]?\s*",
        ]
    },
    "LAWYER": {
        "appearance": "man in his 50s, distinguished silver-grey hair neatly parted, wire-rimmed glasses, clean-shaven, square jaw, professional bearing",
        "wardrobe_by_scene": {
            "002": "wearing charcoal three-piece suit, white shirt, dark tie, gold cufflinks"
        },
        "negative": "NO French description, NO turtleneck, NO intellectual, NO professor",
        "strip_patterns": [
            r"ANTOINE\s+DUBOIS[^.]*[.,]?\s*",
            r"French man[^.]*[.,]?\s*",
            r"intellectual slim build[^.]*[.,]?\s*",
            r"Gauloise gesture[^.]*[.,]?\s*",
            r"grey distinguished hair unkempt[^.]*[.,]?\s*",
            r"unkempt professor[^.]*[.,]?\s*",
            r"dark thoughtful philosophical eyes[^.]*[.,]?\s*",
            r"thoughtful philosophical[^.]*[.,]?\s*",
            r"black turtleneck[^.]*[.,]?\s*",
            r"intellectual French[^.]*[.,]?\s*",
            r"age 52[^.,]*[.,]?\s*",
        ]
    },
    "ARTHUR GRAY": {
        "appearance": "man in his 70s, immaculately suited, posture like a soldier at ease, silver-haired, distinguished, prominent nose above a pencil-thin mustache, thin lips",
        "wardrobe_by_scene": {},
        "negative": "NO French description, NO chef, NO kitchen, NO passionate",
        "strip_patterns": [
            r"PIERRE\s+LAURENT[^.]*[.,]?\s*",
            r"French man[^.]*[.,]?\s*",
            r"chef sturdy build[^.]*[.,]?\s*",
            r"kitchen-hardened[^.]*[.,]?\s*",
            r"dark greying hair chef style[^.]*[.,]?\s*",
            r"chef style[^.]*[.,]?\s*",
            r"passionate brown fiery eyes[^.]*[.,]?\s*",
            r"fiery eyes[^.]*[.,]?\s*",
            r"chef bearing[^.]*[.,]?\s*",
            r"chef whites[^.]*[.,]?\s*",
            r"casual French style[^.]*[.,]?\s*",
            r"age 45[^.,]*[.,]?\s*",
        ]
    },
    "CLARA": {
        "appearance": "woman late 20s, bartender with lived-in charm, friendly face, working clothes, sturdy and practical",
        "wardrobe_by_scene": {},
        "negative": "NO French description, NO Vietnamese, NO academic, NO literary",
        "strip_patterns": [
            r"MIRANDA\s+CROSS[^.]*[.,]?\s*",
            r"French[-\s]Vietnamese[^.]*[.,]?\s*",
            r"Vietnamese[^.]*[.,]?\s*",
            r"academic literary[^.]*[.,]?\s*",
            r"quiet intensity[^.,]*bookish[^.]*[.,]?\s*",
            r"dark bob[^.]*[.,]?\s*",
            r"almond-shaped[^.]*[.,]?\s*",
            r"observant eyes[^.]*[.,]?\s*",
            r"reading glasses[^.]*[.,]?\s*",
            r"earth tones[^.,]*[.,]?\s*",
            r"age 24[^.,]*[.,]?\s*",
        ]
    },
    "DR. ELIAS WARD": {
        "appearance": "man in his 50s, rumpled academic, chubby, kind face, scholarly, glasses, tweed jacket, neat beard",
        "wardrobe_by_scene": {},
        "negative": "NO military description, NO rigid, NO buzz cut, NO combat boots",
        "strip_patterns": [
            r"JACKSON\s+WRIGHT[^.]*[.,]?\s*",
            r"military bearing[^.]*[.,]?\s*",
            r"rigid posture[^.]*[.,]?\s*",
            r"close-cropped[^.]*[.,]?\s*",
            r"buzz cut[^.]*[.,]?\s*",
            r"sharp jaw[^.]*[.,]?\s*",
            r"steel(?:-|\s)?grey[^.]*[.,]?\s*",
            r"combat boots[^.]*[.,]?\s*",
            r"military precision[^.]*[.,]?\s*",
            r"age 38[^.,]*[.,]?\s*",
        ]
    },
}

# ============================================================
# AI ACTOR UNIVERSAL STRIP — catches ANY residual actor contamination
# regardless of which character it leaked into.
# Runs AFTER per-character strips as a safety net.
# ============================================================
AI_ACTOR_UNIVERSAL_STRIP = [
    # Actor names (any position)
    r"ISABELLA\s+MORETTI", r"CHARLOTTE\s+BEAUMONT", r"PIERRE\s+LAURENT",
    r"ANTOINE\s+DUBOIS", r"MIRANDA\s+CROSS", r"JACKSON\s+WRIGHT",
    r"Isabella\s+Moretti", r"Charlotte\s+Beaumont", r"Pierre\s+Laurent",
    r"Antoine\s+Dubois", r"Miranda\s+Cross", r"Jackson\s+Wright",
    # Nationality descriptors from AI actors (these NEVER belong in prompts)
    r"Italian woman age \d+",
    r"English woman age \d+",
    r"French man age \d+",
    r"French[-\s]Vietnamese woman age \d+",
    # AI actor profession contamination
    r"chef sturdy build kitchen-hardened",
    r"chef whites casual French style",
    r"Gauloise gesture",
    r"operatic intensity",
    r"pre-Raphaelite",
]

# ============================================================
# DEFAULT SCENE COLOR GRADES (Ravencroft)
# Used as fallback if project_config not loaded.
# One grade per scene. Strips all conflicting color language.
# ============================================================

_DEFAULT_SCENE_COLOR_GRADES = {
    # === ACT 1: PROLOGUE + INHERITANCE ===
    "000": {  # Show Open — mixed exteriors + titles
        "grade": "crushed blacks, desaturated cool tones, high contrast, cinematic grain, stormy overcast",
        "negative": "NO warm tones, NO bright colors, NO flat lighting",
        "strip": ["warm amber", "bright", "saturated"]
    },
    "001": {  # Ritual Room — candlelit stone chamber
        "grade": "crushed blacks, warm amber candlelight 2200K, deep shadows, desaturated cold stone, gothic horror grain",
        "negative": "NO teal, NO blue shift, NO green tones, NO bright highlights, NO modern lighting",
        "strip": ["teal", "blue-silver", "warm green", "cold blue", "cold-shifted"]
    },
    "002": {  # Evelyn's Apartment — modern urban morning
        "grade": "cold blue morning light, desaturated urban tones, muted greys and whites, soft window light, melancholic naturalism",
        "negative": "NO warm amber, NO saturated colors, NO dramatic candlelight",
        "strip": ["amber", "candlelight", "gothic", "warm candlelight", "amber 1800K", "teal", "neon", "sickly green", "green highlights"]
    },
    "003": {  # Bus / Coastal Road — overcast travel
        "grade": "overcast natural daylight, muted coastal greens and greys, soft diffused light, gentle desaturation, contemplative atmosphere",
        "negative": "NO indoor lighting, NO warm amber, NO dramatic shadows, NO night look",
        "strip": ["amber", "candlelight", "gothic", "teal", "neon", "sickly green", "green highlights"]
    },
    # === ACT 2: VILLAGE + ARRIVAL ===
    "004": {  # Village Pub — warm interior, worn wood
        "grade": "warm tungsten pub interior 3200K, amber wood tones, soft practicals, slight haze, cozy but worn, naturalistic",
        "negative": "NO cold blue, NO daylight balance, NO gothic darkness",
        "strip": ["cold blue", "teal", "gothic", "sickly green", "green highlights"]
    },
    "005": {  # Arrival at Manor — stormy gothic exterior
        "grade": "overcast grey sky, desaturated greens and stone, cold diffused daylight, looming shadows, gothic naturalism",
        "negative": "NO warm tones, NO bright sunlight, NO saturated colors",
        "strip": ["warm amber", "bright sunlight", "saturated"]
    },
    "006": {  # Manor Tour / East Wing — dim interior corridors
        "grade": "dim interior practicals, dusty warm shafts, cold shadow fill, faded grandeur, desaturated heritage tones",
        "negative": "NO modern lighting, NO bright highlights, NO clean white",
        "strip": ["modern", "bright", "clean white"]
    },
    "007": {  # Will Terms Discussion — study lamplight
        "grade": "warm desk lamp 3400K, deep wood tones, amber highlights on faces, dark background fall-off, legal formality",
        "negative": "NO cold blue, NO daylight, NO flat lighting",
        "strip": ["cold blue", "daylight", "flat", "sickly green", "green highlights"]
    },
    # === ACT 2: HAUNTING + INVESTIGATION ===
    "008": {  # First Night Haunting — dark bedroom storm
        "grade": "near darkness, cold moonlight through rain-streaked windows, deep blacks, isolated warm bedside glow, horror intimacy",
        "negative": "NO bright lighting, NO warm overall, NO daylight",
        "strip": ["bright", "warm overall", "daylight"]
    },
    "009": {  # Cliff Walk with Arthur — overcast coastal
        "grade": "grey overcast coastal daylight, muted greens and slate, wind-blown desaturation, cold natural fill, isolated landscape",
        "negative": "NO warm tones, NO indoor lighting, NO gothic darkness",
        "strip": ["warm amber", "indoor", "gothic darkness", "sickly green", "green highlights"]
    },
    "010": {  # Library Discovery — dusty interior daylight
        "grade": "dusty warm window shafts, aged leather tones, soft diffused interior daylight, floating particles, scholarly warmth",
        "negative": "NO cold blue, NO night look, NO modern lighting",
        "strip": ["cold blue", "night", "modern", "sickly green", "green highlights"]
    },
    "011": {  # Village Records Research — cramped office fluorescent
        "grade": "overhead fluorescent mixed with window daylight, slightly green office cast, paper-white highlights, documentary naturalism",
        "negative": "NO warm amber, NO gothic, NO dramatic shadows",
        "strip": ["warm amber", "gothic", "dramatic candlelight"]
    },
    "012": {  # East Wing Exploration — forbidden dark corridor
        "grade": "near darkness, cold blue-grey fill, isolated torch or lamp warmth, deep blacks, deteriorating surfaces, dread atmosphere",
        "negative": "NO bright lighting, NO daylight, NO warm overall",
        "strip": ["bright", "daylight", "warm overall"]
    },
    # === ACT 3: DEEPER DISCOVERY ===
    "013": {  # Manor Library (Evelyn's Discovery) — lamplight + dust
        "grade": "warm lamplight through dust motes, aged paper tones, golden shafts from tall windows, soft contrast, intimate discovery",
        "negative": "NO cold blue, NO modern lighting, NO flat exposure",
        "strip": ["cold blue", "modern", "flat", "sickly green", "green highlights"]
    },
    "014": {  # Village Records & Cafe — mixed daylight/fluorescent
        "grade": "mixed daylight and fluorescent, cool office tones shifting to warm cafe amber, documentary to intimate transition",
        "negative": "NO gothic darkness, NO candlelight, NO horror grain",
        "strip": ["gothic", "candlelight", "horror grain", "sickly green", "green highlights"]
    },
    "015": {  # Guest Bedroom — intimate warm evening
        "grade": "warm firelight and bedside lamp, intimate amber 2800K, soft shadows, personal warmth against cold manor, vulnerable intimacy",
        "negative": "NO cold blue, NO harsh lighting, NO daylight",
        "strip": ["cold blue", "harsh", "daylight", "sickly green", "green highlights"]
    },
    "016": {  # East Wing Corridor — haunted echoes
        "grade": "near darkness, flickering unstable light source, cold grey-blue shadows, deteriorating surfaces, supernatural unease",
        "negative": "NO warm tones, NO stable lighting, NO bright",
        "strip": ["warm tones", "stable lighting", "bright"]
    },
    "017": {  # Study Confrontation — firelight tension
        "grade": "fireplace warm flicker, deep amber on faces, dark wood surrounds, tension-high contrast, warm key with cold fill",
        "negative": "NO flat lighting, NO daylight, NO cold overall",
        "strip": ["flat lighting", "daylight", "cold overall", "sickly green", "green highlights"]
    },
    "018": {  # Study Commitment — solo firelight resolve
        "grade": "dying firelight, warm embers, intimate low-key, single lamp on desk, solitude warmth against vast dark manor",
        "negative": "NO bright lighting, NO daylight, NO cold blue",
        "strip": ["bright", "daylight", "cold blue", "sickly green", "green highlights"]
    },
}

# ============================================================
# DEFAULT SCENE ATMOSPHERE (Ravencroft)
# Used as fallback if project_config not loaded.
# Phrases that belong ONLY in specific scenes.
# Stripped from all other scenes.
# ============================================================

_DEFAULT_SCENE_LOCKED_ATMOSPHERE = {
    # Phrases that ONLY belong in Scene 001 (ritual chamber)
    "001_ONLY": [
        r"the house is watching[^.]*[.,]?\s*",
        r"find the dread in the stillness[^.]*[.,]?\s*",
        r"ritual\s+chamber[^.]*[.,]?\s*",
        r"blood[- ]?red candles?[^.]*[.,]?\s*",
        r"masked figures?[^.]*[.,]?\s*",
        r"robed figures?[^.]*[.,]?\s*",
        r"cold stone\s+(?:floor|walls?)[^.]*[.,]?\s*",
        r"altar[^.]*[.,]?\s*",
    ],
    # Phrases that ONLY belong in Scene 002 (apartment)
    "002_ONLY": [
        r"overdue bills[^.]*[.,]?\s*",
        r"cramped\s+(?:apartment|flat|space)[^.]*[.,]?\s*",
    ],
    # Phrases that ONLY belong in Scene 003 (bus/coastal)
    "003_ONLY": [
        r"coastal[^.]*[.,]?\s*",
        r"bus\s+(?:window|seat|journey)[^.]*[.,]?\s*",
    ],
}

# ============================================================
# PROJECT CONFIG LOADER + HELPERS
# Loads project-specific config from core.project_config
# Falls back to _DEFAULT_* if not available
# ============================================================

def load_project_authority_config(project_name_or_path) -> bool:
    """
    Load project-specific configuration and set _active_config.
    Called from orchestrator_server.py before prompt authority enforcement.

    Args:
        project_name_or_path: Name of the project (e.g., "ravencroft_v22")
                              OR full path to project directory

    Returns:
        True if loaded successfully, False if using fallback defaults
    """
    global _active_config

    if not HAS_PROJECT_CONFIG:
        logger.debug(f"[ProjectConfig] core.project_config not available, using fallback defaults")
        return False

    # V23 FIX: Extract project name from path if a full path was passed
    project_name = project_name_or_path
    if project_name_or_path:
        from pathlib import Path
        path_obj = Path(project_name_or_path)
        # If it looks like a path (contains pipeline_outputs or has multiple parts)
        if 'pipeline_outputs' in str(path_obj) or path_obj.is_dir():
            project_name = path_obj.name
        elif '/' in str(project_name_or_path) or '\\' in str(project_name_or_path):
            project_name = path_obj.name

    if not project_name:
        logger.warning(f"[ProjectConfig] No project name could be extracted from '{project_name_or_path}'")
        return False

    try:
        _active_config = get_project_config(project_name)
        logger.info(f"[ProjectConfig] Loaded project config for '{project_name}'")
        return True
    except Exception as e:
        logger.warning(f"[ProjectConfig] Failed to load config for '{project_name}': {e}")
        _active_config = None
        return False


def _get_canonical_characters() -> Dict[str, Dict]:
    """Get canonical characters from active config or fallback."""
    if _active_config and _active_config.canonical_characters:
        return _active_config.canonical_characters
    return _DEFAULT_CANONICAL_CHARACTERS


def _get_scene_color_grades() -> Dict[str, Dict]:
    """Get scene color grades from active config or fallback."""
    if _active_config and _active_config.scene_color_grades:
        return _active_config.scene_color_grades
    return _DEFAULT_SCENE_COLOR_GRADES


def _get_scene_locked_atmosphere() -> Dict[str, List[str]]:
    """Get scene-locked atmosphere patterns from active config or fallback."""
    if _active_config and _active_config.scene_locked_atmosphere:
        return _active_config.scene_locked_atmosphere
    return _DEFAULT_SCENE_LOCKED_ATMOSPHERE


def _get_character_strip_patterns(char_name: str) -> List[str]:
    """
    Get AI actor contamination strip patterns for a character.
    Returns patterns from active config or fallback.

    Args:
        char_name: Character name (e.g., "EVELYN RAVENCROFT")

    Returns:
        List of regex patterns to strip for this character
    """
    if _active_config:
        patterns = _active_config.get_strip_patterns_for_character(char_name)
        if patterns:
            return patterns

    # Fallback: look in _DEFAULT_CANONICAL_CHARACTERS
    char_upper = char_name.upper().strip()
    if char_upper in _DEFAULT_CANONICAL_CHARACTERS:
        return _DEFAULT_CANONICAL_CHARACTERS[char_upper].get("strip_patterns", [])

    return []


def _build_dynamic_ai_actor_strip() -> List[str]:
    """
    Build AI_ACTOR_UNIVERSAL_STRIP dynamically from active config.
    If config loaded, extract all AI actor names from character_strip_patterns.
    Falls back to hardcoded universal list.
    """
    patterns = AI_ACTOR_UNIVERSAL_STRIP.copy()  # Start with hardcoded list

    if _active_config and _active_config.character_strip_patterns:
        # Extract unique AI actor names from all character patterns
        for char_name, char_patterns in _active_config.character_strip_patterns.items():
            for pattern in char_patterns:
                # Heuristic: first pattern in each character often has the AI actor name
                # Extract sequences like "FIRSTNAME LASTNAME"
                match = re.search(r'([A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)*)', pattern)
                if match:
                    name_pattern = match.group(0)
                    if name_pattern not in patterns:
                        patterns.append(name_pattern)

    return patterns

# ============================================================
# GENERIC STRIP PATTERNS
# Enrichment-layer artifacts that always get stripped
# ============================================================

ALWAYS_STRIP = [
    r"#[0-9A-Fa-f]{6}",                    # Hex color codes from wardrobe agent
    r"Color grade:[^.]*[.]?\s*",            # ALL "Color grade:" blocks — canonical one re-injected later
    r"Eterna 500 desaturated stock[^.,]*[.,]?\s*", # Film stock from enricher
    r"cold-shifted teal color grade[^.,]*[.,]?\s*", # Enricher teal injection
    r"Fuji Eterna \d+T[^.,]*[.,]?\s*",    # Film stock injection
    # V21.9.1: Fixed — patterns now accept comma OR period terminator
    # Was: [^.]*\. — only matched period-terminated phrases
    # Now: [^.,]*[.,]?\s* — matches both "...stock." and "...stock, next"
    # BROADEST FIRST: catch the full "shot on X sensor, Y stock" phrase in one pass
    r"shot on (?:RED|ARRI|Sony|Canon|Panavision)[^.]*(?:stock|grain|texture)[^.,]*[.,]?\s*",  # Full sensor+stock phrase
    r"shot on RED Monstro[^.,]*[.,]?\s*",  # Camera from enricher (nano)
    r"shot on ARRI Alexa[^.,]*[.,]?\s*",   # Camera sensor from enricher
    r"Kodak Vision3[^.,]*[.,]?\s*",        # Film stock from enricher
    r"Fujifilm Eterna[^.,]*[.,]?\s*",      # Film stock from enricher (horror profile)
    r"Fujifilm\s+\w+",                     # V21.9.1: Catch any orphaned "Fujifilm X" after partial strip
]

# V21.9.1: LTX-specific strips — film stock/sensor/LUT have ZERO effect on LTX-2
# These waste ~200 chars of the 1500 budget and contribute to truncation
LTX_ALWAYS_STRIP = [
    r"shot on (?:RED|ARRI|Sony|Canon|Panavision)[^.]*\.",  # Camera sensor
    r"(?:Kodak|Fujifilm|Fuji)\s+(?:Vision|Eterna)\s*\d*T?[^.]*\.",  # Film stock
    r"crushed blacks,?\s*sickly green highlights,?\s*grain[.,]?\s*",  # Horror LUT (conflicts with scene grades)
    r"crushed blacks,?\s*deep shadow detail[^.]*\.",  # LUT from enricher
    r"grain[.,]\s*(?=\w)",                             # Orphaned "grain," from LUT strip
]

# Scene 003 contamination guard
SCENE_003_STRIP = [
    r"lawyer'?s?\s+letter",                 # Lawyer reference in bus scene
    r"office\s*(?:wear|worker)[^.]*",       # Office extras in bus scene
]

# ============================================================
# DEDUPLICATION PATTERNS — V21.3
# Blocks that appear multiple times due to enrichment stacking.
# Keep FIRST occurrence, strip all subsequent.
# ============================================================

# These are prefix patterns — we find all blocks starting with these,
# keep the first, remove duplicates.
DEDUP_BLOCK_PREFIXES = [
    "performance:",
    "Setting:",
    "Location:",
    "composition:",
    "emotion blend:",
    "ACTING",
    "DIALOGUE PERFORMANCE",
    "atmosphere:",
    "lighting:",
    # V22.3: Added from Victorian Shadows stacking analysis
    "director camera:",
    "motivated movement:",
    "environment mood:",
    "AUDIO:",
    "subtext:",
]

# Exact phrase dedup — if same phrase appears multiple times, keep first
DEDUP_EXACT_PHRASES = [
    "face stable NO morphing",
    "face stable",
    "character consistent",
    "character speaks:",
    "natural speech movement, lips moving",
    "let the silence work",
    "find the dread in the stillness",
    "the house is watching",
    "static dread",
    "measured deliberate tempo",
    "natural breathing, lifelike micro-movements",
    "eyes convey deep emotion",
    "subtle micro-expressions",
    "emotional intensity in gaze",
    # V22.3: Added camera motion dedup from Victorian Shadows stacking
    "camera slowly pushes in",
    "static camera",
    "slow dolly",
    "elegant dolly",
    "controlled movement",
    "establishing atmosphere",
    "golden ratio composition",
]

# ============================================================
# V21.9.2: DIALOGUE MARKER CONSOLIDATION
# ============================================================
# Root cause: 7+ injection points in orchestrator_server.py each add dialogue
# using DIFFERENT marker prefixes. Result: same dialogue text 3x in every LTX.
# Fix: consolidate ALL dialogue markers into ONE clean "character speaks:" block.

def _dedup_dialogue_markers(text):
    """V21.9.2: Consolidate duplicate dialogue injections into ONE clean block.

    Root cause: The pipeline has 7+ dialogue injection points that each use
    different markers:
      - "dialogue context: CHAR: text"     (from CHECK 5B)
      - "character speaking: \"text\""       (from director motion injection)
      - "character speaks: \"CHAR: text\""   (from fidelity injection)
      - "character speaks: CHAR delivers dialogue, on speaker" (from gold standard)

    All carry the SAME dialogue text. This:
    1. Wastes ~200-400 chars of LTX's 1500 budget
    2. Confuses the model with 3 conflicting speech directions
    3. Causes "on speaker, on speaker, on speaker" stutter artifacts

    Fix: Extract dialogue text, keep ONE clean "character speaks:" block,
    strip the other two markers entirely.
    """
    if not text:
        return text

    result = text

    # --- Phase 1: Strip "on speaker" stutter ---
    # Pattern: "on speaker, on speaker, on speaker" from concatenation bugs
    result = re.sub(r'(?:,?\s*on speaker){2,}', '', result, flags=re.IGNORECASE)

    # --- Phase 2: Extract dialogue text from all 3+ markers ---
    # We want to keep the best (most complete) dialogue text
    dialogue_texts = []

    # Pattern A: "dialogue context: CHAR: text | CHAR: text"
    # This can be long with pipe-delimited multi-speaker dialogue
    dlg_ctx_match = re.search(
        r'dialogue context:\s*((?:[A-Z][A-Z\s]*:\s*[^|,]+\s*\|\s*)*[A-Z][A-Z\s]*:\s*[^,]+)',
        result, re.IGNORECASE)
    if not dlg_ctx_match:
        # Fallback: simpler match for shorter dialogue
        dlg_ctx_match = re.search(r'dialogue context:\s*([^,]{5,}?)(?=,\s*character|\s*$)', result, re.IGNORECASE)
    if dlg_ctx_match:
        dialogue_texts.append(dlg_ctx_match.group(1).strip().strip('"'))

    # Pattern B: 'character speaking: "text"' (quoted)
    speaking_match = re.search(r'character speaking:\s*"([^"]*)"', result, re.IGNORECASE)
    if speaking_match:
        dialogue_texts.append(speaking_match.group(1).strip())

    # Pattern C: 'character speaks: "CHAR: text"' (quoted)
    speaks_quoted = re.search(r'character speaks:\s*"([^"]*)"', result, re.IGNORECASE)
    if speaks_quoted:
        dialogue_texts.append(speaks_quoted.group(1).strip())

    # Pattern D: 'character speaks: CHAR delivers dialogue' (unquoted gold standard)
    speaks_unquoted = re.search(
        r'character speaks:\s*([A-Z][A-Z\s]+ (?:delivers dialogue|speaks)[^,]*)',
        result)
    if speaks_unquoted:
        dialogue_texts.append(speaks_unquoted.group(1).strip())

    # Count ALL dialogue-related markers (including empty/corrupted ones)
    all_markers = re.findall(r'character speak(?:s|ing)?:|dialogue context:', result, re.IGNORECASE)
    # If fewer than 2 markers total AND fewer than 2 extracted texts, nothing to consolidate
    if len(dialogue_texts) < 2 and len(all_markers) < 2:
        return result

    # Pick the LONGEST dialogue text that contains actual character dialogue (has ":" in it)
    # Prefer text with "CHAR: words" pattern over "delivers dialogue"
    actual_dialogue = [t for t in dialogue_texts if re.search(r'[A-Z]+\s*:', t)]
    if actual_dialogue:
        best_dialogue = max(actual_dialogue, key=len)
    elif dialogue_texts:
        best_dialogue = max(dialogue_texts, key=len)
    else:
        best_dialogue = ""

    # --- Phase 3: Strip ALL dialogue markers (we'll re-inject one clean one) ---

    # Strip "dialogue context:" — entire section up to next major marker
    # This can contain pipe-delimited multi-speaker dialogue, so match aggressively
    result = re.sub(
        r',?\s*dialogue context:\s*[^|]*?(?:\|[^|]*?)*?(?=,\s*character speak|,\s*restrained|,\s*performance|,\s*show me|,\s*atmosphere|,\s*lighting|,\s*Empty|\s*$)',
        '', result, flags=re.IGNORECASE)
    # Fallback: catch any remaining "dialogue context:" fragments
    result = re.sub(r',?\s*dialogue context:[^,]*', '', result, flags=re.IGNORECASE)

    # Strip ALL "character speaking:" — single aggressive pass
    # Must handle: quoted, unquoted, corrupted (orphaned quote), and empty variants
    # Strategy: find all occurrences and remove them with surrounding template text
    while re.search(r'character speaking:', result, re.IGNORECASE):
        before = result
        # Try 1: match through "maintain exact character appearance" anchor
        result = re.sub(
            r',?\s*character speaking:\s*.*?maintain exact character appearance',
            '', result, flags=re.IGNORECASE)
        if result != before:
            continue
        # Try 2: match quoted content with trailing template
        result = re.sub(
            r',?\s*character speaking:\s*"[^"]*"[^,]*(?:,\s*restrained[^,]*)?(?:,\s*slow[^,]*)?(?:,\s*measured[^,]*)?',
            '', result, flags=re.IGNORECASE)
        if result != before:
            continue
        # Try 3: nuclear — strip from marker to end, preserve final timing
        final_time = re.search(r',?\s*(\d+s)\s*$', result)
        result = re.sub(r',?\s*character speaking:.*$', '', result, flags=re.IGNORECASE)
        if final_time:
            result = result.rstrip(', ') + ', ' + final_time.group(1)
        break  # Prevent infinite loop

    # Strip 'character speaks: "..."' with optional trailing template
    result = re.sub(
        r',?\s*character speaks:\s*"[^"]*"(?:,\s*lips moving naturally)?(?:,\s*subtle expression shifts)?(?:,\s*no face morphing)?(?:,\s*maintain exact character appearance)?',
        '', result, flags=re.IGNORECASE)

    # Strip 'character speaks: CHAR delivers dialogue, on speaker' (unquoted gold standard)
    result = re.sub(
        r',?\s*character speaks:\s*[A-Z][A-Z\s]+(?:delivers dialogue|speaks)[^,]*(?:,\s*on speaker)?',
        '', result)

    # --- Phase 4: Re-inject ONE clean dialogue block ---
    if best_dialogue:
        # Truncate dialogue to 200 chars max to prevent LTX bloat
        if len(best_dialogue) > 200:
            best_dialogue = best_dialogue[:200].rsplit(' |', 1)[0] if ' |' in best_dialogue[:200] else best_dialogue[:200].rsplit(' ', 1)[0]
        clean_block = f', character speaks: "{best_dialogue}", lips moving naturally'
        # Find good injection point — before "atmosphere:" or "lighting:" or at end
        atmo_match = re.search(r',?\s*atmosphere:', result, re.IGNORECASE)
        if atmo_match:
            result = result[:atmo_match.start()] + clean_block + result[atmo_match.start():]
        else:
            time_match = re.search(r',?\s*\d+s\s*$', result)
            if time_match:
                result = result[:time_match.start()] + clean_block + result[time_match.start():]
            else:
                result += clean_block

    # --- Phase 5: Clean up artifacts ---
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r'\s{2,}', ' ', result)

    return result.strip()


def _strip_ltx_acting_metrics(text):
    """V21.9.2: Strip emotional metric blocks that LTX-2 cannot interpret.

    Root cause: The ACTING (bio-real) block contains numeric emotion blends,
    microleak scores, brow asymmetry metrics — designed for human actors,
    not video generation models. These waste 200-300 chars and confuse LTX.

    Example being stripped:
    'ACTING (bio-real): emotion blend: curiosity (0.6) under caution,
    high control microleak: 0. surprise flash at 3. then composure returns
    brows: inner lift slight, asymmetry body: leaning forward...'

    Replacement: Simple emotional direction LTX CAN use.
    """
    if not text:
        return text

    result = text

    # Strip the full ACTING block — from "ACTING (bio-real):" to next major marker
    acting_match = re.search(
        r'ACTING\s*\(bio-real\):\s*emotion blend:[^.]*(?:\.\s*[a-z][^.]*)*\.',
        result, re.IGNORECASE
    )
    if acting_match:
        # Extract the emotion name for a simple replacement
        emotion_match = re.search(r'emotion blend:\s*(\w+)', acting_match.group())
        simple_emotion = emotion_match.group(1) if emotion_match else ''
        replacement = f'subtle {simple_emotion} performance, ' if simple_emotion else ''
        result = result[:acting_match.start()] + replacement + result[acting_match.end():]

    # Also strip standalone metric fragments that survive partial stripping
    result = re.sub(r'high control microleak:\s*\d+\.?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'microleak:\s*\d+\.?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'brows:\s*inner lift[^.,]*[.,]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'asymmetry body:\s*[^.,]*[.,]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'breath catch at line end[^.,]*[.,]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'no blink on final words[^.,]*[.,]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'delivery:\s*low restrained[^.,]*[.,]?\s*', '', result, flags=re.IGNORECASE)

    # V21.9.3: Strip GARBLED acting metrics from OLD v16_7 emotion_layer_agent.
    # Root cause: OLD version used "\n".join() → newlines collapsed to spaces →
    # numbered list artifacts like "7) under resignation, resolve set at 3."
    # These patterns survive even after the full ACTING block strip above.
    # Strip numbered emotion items: "7) under dread", "2) under watchfulness"
    result = re.sub(r',?\s*\d+\)\s+under\s+\w+[^,]*(?:,\s*(?:resolve|dread|fear|grief|hope|tension|resignation|watchfulness|caution|defiance|reverence|desperation|control)[^,]*)*', '', result, flags=re.IGNORECASE)
    # Strip "resolve set at N" fragments
    result = re.sub(r',?\s*resolve set at\s*\d+[^,]*', '', result, flags=re.IGNORECASE)
    # Strip "then composure returns" fragments
    result = re.sub(r',?\s*then composure returns[^,]*', '', result, flags=re.IGNORECASE)
    # Strip orphaned "brows:" metric lines (not in context of "eye brows")
    result = re.sub(r',?\s*brows:\s*(?:brow draw|inner lift|slight furrow|asymmetry)[^,]*', '', result, flags=re.IGNORECASE)
    # Strip "eyes:" metric lines from emotion layer
    result = re.sub(r',?\s*eyes:\s*(?:lower lid|narrowed|wide|squint|lid tension)[^,]*', '', result, flags=re.IGNORECASE)
    # Strip "dread freeze at N" / "surprise flash at N"
    result = re.sub(r',?\s*(?:dread freeze|surprise flash|fear flash|grief wave|tension spike)\s+at\s+\d+[^,]*', '', result, flags=re.IGNORECASE)
    # Strip "high control" orphans
    result = re.sub(r',?\s*high control\s*(?:,|$)', ',', result, flags=re.IGNORECASE)
    # Strip "emotion blend:" if it survived without the ACTING header
    result = re.sub(r',?\s*emotion blend:\s*\w+\s*\([^)]*\)[^,]*', '', result, flags=re.IGNORECASE)

    return result


# V21.9: CONFLICT RESOLUTION — strip contradictory directives
def resolve_ltx_conflicts(ltx: str, shot: dict) -> str:
    """V21.9 DIRECTOR AUDIT GATE — resolve ALL contradictions in LTX AFTER all enrichment.

    This is the LAST line of defense before prompts reach FAL.
    Every issue a director would catch on a shot sheet should be caught here.
    """
    dialogue_text = (shot.get("dialogue_text") or shot.get("dialogue") or "").strip()
    has_dialogue = bool(dialogue_text)
    shot_type = (shot.get("shot_type") or "").lower()
    has_chars = bool(shot.get("characters"))
    is_establishing = shot_type in ("establishing", "detail", "cutaway")
    is_demoted = bool(shot.get("_original_dialogue_demoted") or shot.get("_stage_direction_demoted"))

    # ── Rule 1: Dialogue shots — remove "NO morphing" (conflicts with lip sync) ──
    if has_dialogue and has_chars:
        ltx = ltx.replace("NO morphing", "").replace("no morphing", "")
        ltx = ltx.replace("Face morphing ENABLED:", "").replace("face morphing ENABLED:", "")

    # ── Rule 2: SILENT + character speaks — remove SILENT if dialogue exists ──
    if has_dialogue and "AUDIO: silent" in ltx:
        ltx = re.sub(r"AUDIO:\s*silent[^.]*\.", "", ltx)

    # ── Rule 3: Characterless shots — strip ALL human performance language ──
    if not has_chars:
        ltx = re.sub(r',?\s*character performs:[^,]*(?:,|$)', '', ltx)
        ltx = re.sub(r',?\s*character speaks:[^,]*(?:,|$)', '', ltx)
        ltx = re.sub(r',?\s*character reacts:[^,]*(?:,|$)', '', ltx)
        ltx = re.sub(r',?\s*key motion:[^,]*(?:,|$)', '', ltx)
        ltx = re.sub(r'face stable[^,]*,?', '', ltx)
        ltx = re.sub(r'lips moving[^,]*,?', '', ltx)
        ltx = re.sub(r'natural speech movement[^,]*,?', '', ltx)
        ltx = re.sub(r'micro-expression[^,]*,?', '', ltx, flags=re.I)
        ltx = re.sub(r'breathing[^,]*,?', '', ltx, flags=re.I)
        ltx = re.sub(r'chest rise[^,]*,?', '', ltx, flags=re.I)
        ltx = re.sub(r'blinks[^,]*,?', '', ltx, flags=re.I)
        ltx = re.sub(r'subtle eye movement[^,]*,?', '', ltx, flags=re.I)
        ltx = re.sub(r'DIALOGUE PERFORMANCE MANDATORY:[^.]*\.?', '', ltx)

    # ── Rule 4: Demoted dialogue — strip stale character speaks from LTX ──
    if is_demoted and not has_dialogue:
        ltx = re.sub(r',?\s*character speaks:[^,]*(?:,|$)', '', ltx)
        ltx = re.sub(r'DIALOGUE PERFORMANCE MANDATORY:[^.]*\.?', '', ltx)

    # ── Rule 5: V.O. dialogue — on-screen character should REACT not speak ──
    if has_dialogue and "V.O." in dialogue_text and has_chars:
        # Check if V.O. speaker is different from on-screen characters
        vo_match = re.search(r'(\w[\w\s]*?)\s*\(V\.O\.\)', dialogue_text)
        if vo_match:
            vo_speaker = vo_match.group(1).strip().upper()
            on_screen_names = [c.upper() for c in shot.get("characters", [])]
            if vo_speaker not in " ".join(on_screen_names):
                # V.O. speaker is off-screen — on-screen char should react
                on_screen = shot.get("characters", ["Character"])[0]
                ltx = re.sub(r'character speaks:[^,]*',
                    f'character reacts: {on_screen} listening to voice, subtle facial shifts', ltx)

    # ── Rule 6: Stage directions as dialogue — strip from LTX ──
    stage_dir_patterns = [
        r'^Listening intently', r'^Detail shot', r'^Processing the',
        r'^Watching .* as', r'^Absorbing', r'^Looking .* at'
    ]
    if has_dialogue:
        for pat in stage_dir_patterns:
            if re.match(pat, dialogue_text, re.I):
                ltx = re.sub(r',?\s*character speaks:[^,]*(?:,|$)', '', ltx)
                break

    # ── Rule 7: "None experiences/explains" generic actions — strip ──
    ltx = re.sub(r'character performs:\s*None\s+(?:experiences|explains)[^,]*(?:,|$)', '', ltx)
    ltx = re.sub(r',?\s*key motion:\s*(?:experiences|explains)\s*(?:,|$)', '', ltx)

    # ── Clean up ──
    ltx = re.sub(r',\s*,', ',', ltx)
    ltx = re.sub(r'\s{2,}', ' ', ltx)
    return ltx.strip(' ,.')

# ============================================================
# PROMPT SIZE LIMITS — V21.3
# Restore prompts to V9-quality density (~2,500 chars)
# ============================================================

NANO_PROMPT_MAX_CHARS = 3000      # V9 averaged 2,500 — allow some headroom
LTX_MOTION_MAX_CHARS = 1500       # V9 averaged 900 — allow headroom


# ============================================================
# PROJECT-SPECIFIC OVERRIDES — UNIVERSAL SUPPORT
# Load from {project_path}/prompt_authority_config.json when present.
# Falls back to hardcoded Ravencroft defaults above.
# ============================================================

# Legacy wrapper — extracts project name from path and calls ProjectConfig loader
_CONFIG_LOAD_CACHE = {}  # Cache to avoid reloading same project


def _extract_project_name(project_path) -> Optional[str]:
    """Extract project name from path or return as-is if already a name."""
    if not project_path:
        return None
    path_str = str(project_path).strip()
    if "/" in path_str or "\\" in path_str:
        # It's a path — extract directory name
        return os.path.basename(path_str)
    # It's already a project name
    return path_str


# Override the load function to integrate with ProjectConfig
_original_load_project_authority_config = load_project_authority_config


def load_project_authority_config(project_path):
    """
    Load project configuration from path (legacy compatibility API).

    Extracts project name from path and loads via ProjectConfig.
    Falls back to hardcoded defaults if ProjectConfig unavailable.

    Args:
        project_path: Directory path like /path/pipeline_outputs/ravencroft_v22
                     or project name like "ravencroft_v22"

    Returns:
        True if loaded, False if using fallback defaults
    """
    if not project_path:
        return False

    # Cache check
    project_name = _extract_project_name(project_path)
    if not project_name:
        return False

    if project_name in _CONFIG_LOAD_CACHE:
        return _CONFIG_LOAD_CACHE[project_name]

    # Try new ProjectConfig system first
    success = _original_load_project_authority_config(project_name)
    _CONFIG_LOAD_CACHE[project_name] = success
    return success


def get_characters():
    """Get active character registry (project-specific or default)."""
    return _get_canonical_characters()


def get_color_grades():
    """Get active color grade registry (project-specific or default)."""
    return _get_scene_color_grades()


def get_atmosphere():
    """Get active atmosphere registry (project-specific or default)."""
    return _get_scene_locked_atmosphere()


def _strip_patterns(text, patterns):
    """Strip regex patterns from text."""
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    return result


def _strip_color_conflicts(text, scene_id):
    """Strip color language that conflicts with scene authority."""
    sid = scene_id[:3] if scene_id else ""
    grade_info = get_color_grades().get(sid)
    if not grade_info:
        return text

    result = text
    for bad_word in grade_info.get("strip", []):
        escaped = re.escape(bad_word)

        def _should_strip(match):
            """Check if this match is inside a NO-constraint — if so, keep it."""
            start = match.start()
            lookback = result[max(0, start - 20):start].lower()
            if re.search(r'\bno\s+\w*\s*$', lookback):
                return match.group()  # Keep it — it's inside "NO ..."
            return ''  # Strip it

        pattern = rf'{escaped}[^.,]*[.,]?\s*'
        result = re.sub(pattern, _should_strip, result, flags=re.IGNORECASE)

    # Also strip Scene 003 contamination
    if sid == "003":
        for pattern in SCENE_003_STRIP:
            result = re.sub(pattern, 'letter', result, count=1, flags=re.IGNORECASE)

    return result


def _strip_scene_atmosphere(text, scene_id):
    """Strip atmosphere phrases that belong to OTHER scenes.

    V21.3: "the house is watching" in apartment scenes, "ritual chamber" in bus scenes, etc.
    """
    sid = scene_id[:3] if scene_id else ""
    if not sid:
        return text

    result = text
    for scene_key, patterns in get_atmosphere().items():
        owner_scene = scene_key[:3]  # e.g., "001" from "001_ONLY"
        if sid == owner_scene:
            continue  # These phrases BELONG here — don't strip

        # Strip these phrases from this (non-owner) scene
        for pattern in patterns:
            # Don't strip if inside a "NO ..." block
            def _should_strip_atmo(match):
                start = match.start()
                lookback = result[max(0, start - 10):start].lower()
                if 'no ' in lookback:
                    return match.group()
                return ''
            result = re.sub(pattern, _should_strip_atmo, result, flags=re.IGNORECASE)

    return result


def _strip_duplicate_character_blocks(text, char_name):
    """Remove duplicate character description blocks, keep first occurrence.
    V21.9.1: Also strips parenthetical cast_map descriptions that evade
    the standard pattern, e.g. 'EVELYN RAVENCROFT (fairly attractive woman...)'
    """
    name_upper = char_name.upper().replace(" ", r"\s+")

    # Pattern 1: Standard character descriptions with trigger words
    pattern = rf'{name_upper}[\s:,(][^.]*(?:woman|man|age|hair|eyes|face|skin|build|Italian|regal|attractive|thin|gaunt|piercing)[^.]*\.?'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if len(matches) <= 1:
        # Pattern 2: Parenthetical descriptions — "CHARNAME (any description here)"
        # These come from cast_map AI actor descriptions and don't always contain trigger words
        paren_pattern = rf'{name_upper}\s*\([^)]+\)'
        matches = list(re.finditer(paren_pattern, text, re.IGNORECASE))

    if len(matches) <= 1:
        return text

    # Keep first, remove rest
    result = text
    for match in reversed(matches[1:]):
        result = result[:match.start()] + result[match.end():]

    return result


def _dedup_blocks(text):
    """Deduplicate enrichment blocks that appear multiple times.

    V21.3: For each prefix like "performance:", "Setting:", "Location:",
    find ALL occurrences. Keep the FIRST (longest) one, strip the rest.
    """
    result = text

    for prefix in DEDUP_BLOCK_PREFIXES:
        escaped = re.escape(prefix)
        # Match: prefix + content up to next occurrence of ANOTHER prefix, period, or end
        # V21.9: Changed from greedy [^.]* to lazy non-greedy match that stops at next
        # prefix boundary (comma + space + known prefix) or period.
        pattern = rf'{escaped}\s*(?:(?!{escaped})[^.])*\.?\s*'
        matches = list(re.finditer(pattern, result, re.IGNORECASE))

        if len(matches) <= 1:
            continue

        # Keep the FIRST (or longest) occurrence, remove the rest
        # Sort by length descending to find the best one
        best_idx = 0
        best_len = len(matches[0].group())
        for i, m in enumerate(matches):
            if len(m.group()) > best_len:
                best_len = len(m.group())
                best_idx = i

        # Remove all except the best
        to_remove = []
        for i, m in enumerate(matches):
            if i != best_idx:
                to_remove.append((m.start(), m.end()))

        # Remove in reverse order to preserve indices
        for start, end in reversed(to_remove):
            result = result[:start] + result[end:]

    return result


def _dedup_exact_phrases(text):
    """Remove duplicate exact phrases, keeping first occurrence.

    V21.3: Phrases like "face stable NO morphing" and "the house is watching"
    appear 2-6 times per prompt. Keep first, strip rest.
    """
    result = text

    for phrase in DEDUP_EXACT_PHRASES:
        escaped = re.escape(phrase)
        # Find all occurrences (case-insensitive)
        matches = list(re.finditer(escaped, result, re.IGNORECASE))
        if len(matches) <= 1:
            continue

        # Remove all but the first
        for match in reversed(matches[1:]):
            # Remove the match + any trailing punctuation/space
            end = match.end()
            # Eat trailing comma, period, space
            while end < len(result) and result[end] in ' .,;':
                end += 1
            result = result[:match.start()] + result[end:]

    return result


def _enforce_single_character(text, char_name, scene_id):
    """Enforce single canonical description for a character."""
    canon = get_characters().get(char_name)
    if not canon:
        return text

    result = text

    # 1. Strip known bad patterns (AI actor descriptions, wrong wardrobe, etc.)
    result = _strip_patterns(result, canon.get("strip_patterns", []))

    # 2. Strip duplicate character blocks
    result = _strip_duplicate_character_blocks(result, char_name)

    # 3. Check if canonical appearance is already present
    sid = scene_id[:3] if scene_id else ""
    appearance = canon["appearance"]
    wardrobe = canon["wardrobe_by_scene"].get(sid, "")
    negative = canon.get("negative", "")

    # Build the canonical block
    canon_block = f"{char_name} ({appearance})"
    if wardrobe:
        canon_block += f", {wardrobe}"
    canon_block += "."
    if negative:
        canon_block += f" {negative}."

    # If canonical appearance keywords aren't present, inject
    key_phrase = appearance.split(",")[0]  # First descriptor
    if key_phrase.lower() not in result.lower():
        # Inject after first sentence
        first_period = result.find('. ')
        if 0 < first_period < 100:
            result = result[:first_period+2] + canon_block + " " + result[first_period+2:]
        else:
            result = canon_block + " " + result

    return result


def _smart_truncate(text, max_chars):
    """Intelligently truncate prompt to max_chars.

    V21.3: Instead of hard-cutting, remove lowest-priority sections first:
    1. Duplicate negative constraint blocks (already handled by dedup)
    2. Generic atmosphere filler ("natural breathing, lifelike micro-movements")
    3. Redundant camera descriptions after the first
    4. If still too long, truncate at last sentence boundary before limit
    """
    if len(text) <= max_chars:
        return text

    result = text

    # Phase 1: Strip low-value filler phrases (atmosphere padding)
    LOW_VALUE_FILLERS = [
        r"natural breathing,?\s*lifelike micro-movements[^.]*[.,]?\s*",
        r"eyes convey deep emotion[^.]*[.,]?\s*",
        r"subtle micro-expressions[^.]*[.,]?\s*",
        r"emotional intensity in gaze[^.]*[.,]?\s*",
        r"building dramatic intensity[^.]*[.,]?\s*",
        r"heightened emotional stakes[^.]*[.,]?\s*",
        r"urgent energy[^.]*[.,]?\s*",
        r"moment of clarity in expression[^.]*[.,]?\s*",
        r"deliberate tempo[^.]*[.,]?\s*",
        r"subtle environmental motion[^.]*[.,]?\s*",
        r"atmospheric particles[^.]*[.,]?\s*",
    ]
    for filler in LOW_VALUE_FILLERS:
        if len(result) <= max_chars:
            break
        result = re.sub(filler, '', result, flags=re.IGNORECASE)

    if len(result) <= max_chars:
        return re.sub(r'\s{2,}', ' ', result).strip()

    # Phase 2: Strip duplicate timing blocks (e.g., "0-10s static hold" repeated)
    timing_pattern = r'\d+-\d+s\s+(?:static\s+hold|slow\s+\w+)[^.,]*[.,]?\s*'
    timing_matches = list(re.finditer(timing_pattern, result))
    if len(timing_matches) > 1:
        for m in reversed(timing_matches[1:]):
            result = result[:m.start()] + result[m.end():]
            if len(result) <= max_chars:
                break

    if len(result) <= max_chars:
        return re.sub(r'\s{2,}', ' ', result).strip()

    # Phase 3: Hard truncate at last sentence boundary
    truncated = result[:max_chars]
    last_period = truncated.rfind('. ')
    if last_period > max_chars * 0.7:  # Don't truncate more than 30%
        truncated = truncated[:last_period + 1]

    return re.sub(r'\s{2,}', ' ', truncated).strip()


def _cleanup_text(text):
    """Standard text cleanup after all stripping/dedup operations."""
    result = text
    # V21.9.3: Fix missing concatenation spaces (ROOT CAUSE 2)
    # Root cause: enrichment layers append with bare periods, no space after.
    # Pattern "atmosphere.pushes" → "atmosphere. pushes"
    # Safe because sentences ALWAYS need space after period before lowercase.
    result = re.sub(r'\.([a-z])', r'. \1', result)
    result = re.sub(r'\s{2,}', ' ', result)        # Collapse multiple spaces
    result = re.sub(r'\.\s*\.', '.', result)        # Collapse double periods
    result = re.sub(r',\s*,', ',', result)          # Collapse double commas
    result = re.sub(r',\s*\.', '.', result)         # Comma before period
    result = re.sub(r'\.\s*,', '.', result)         # Period before comma
    result = re.sub(r'\bwarm\s+(?=[A-Z])', '', result)  # Orphaned "warm " before capital
    result = re.sub(r'^\s*[.,;]\s*', '', result)    # Leading punctuation
    result = re.sub(r'[.,;]\s*[.,;]', '.', result)  # Adjacent punctuation
    # V21.9.1: Clean orphaned "NO ." left after bio/actor description strip
    result = re.sub(r'\bNO\s*\.\s*', '', result)    # "NO ." → empty
    result = re.sub(r'\bNO\s*,\s*NO\b', 'NO', result)  # "NO , NO" → "NO"
    result = re.sub(r'\bNO\s+(?=NO\b)', '', result)     # "NO NO" → "NO"
    return result.strip()


def _dedup_negative_blocks(text):
    """Deduplicate repeated negative constraint blocks.
    V21.9.1: Also deduplicates color negative PHRASES within constraints,
    e.g. "NO cold blue" appearing 3x from 3 different enrichment layers.
    """
    # Phase 1: Dedup full "NO xxx." blocks (exact match)
    neg_blocks = re.findall(r'(?:NO\s+\w+[^.]*\.)', text)
    seen_negs = set()
    result = text
    for neg_block in neg_blocks:
        normalized = neg_block.strip().lower()
        if normalized in seen_negs:
            result = result.replace(neg_block, '', 1)
        else:
            seen_negs.add(normalized)

    # Phase 2: Dedup individual "NO xxx" phrases within comma-separated constraint lists
    # Catches: "NO cold blue, NO daylight balance, NO gothic darkness, NO cold blue, NO daylight balance"
    # These come from 3 enrichment layers each appending the same scene negative
    _neg_phrases = re.findall(r'NO\s+[^,.\n]+', result)
    seen_phrases = set()
    for phrase in _neg_phrases:
        normalized = phrase.strip().lower()
        if normalized in seen_phrases:
            # Remove duplicate phrase + trailing comma/space
            escaped = re.escape(phrase)
            result = re.sub(rf',?\s*{escaped}', '', result, count=1)
        else:
            seen_phrases.add(normalized)

    return result


def _dedup_camera_directions(text):
    """V21.9.1: Deduplicate camera direction phrases injected by multiple layers.
    Shot expansion + cinematic enricher both inject "camera holds steady",
    "slow push", "gentle dolly" etc. Keep the first, strip subsequent.
    """
    CAMERA_PHRASES = [
        "camera holds steady", "gentle slow push", "measured pace",
        "slow dolly forward", "camera slowly", "dolly forward",
        "slow zoom", "gentle push", "slow pan", "push in",
        "slow crane", "tracking shot", "steadicam follow",
    ]
    result = text
    for phrase in CAMERA_PHRASES:
        escaped = re.escape(phrase)
        matches = list(re.finditer(escaped, result, re.IGNORECASE))
        if len(matches) <= 1:
            continue
        # Remove all but first occurrence + trailing comma/space
        for match in reversed(matches[1:]):
            start = match.start()
            end = match.end()
            # Eat trailing comma/space/period
            while end < len(result) and result[end] in ' .,;':
                end += 1
            # Eat leading comma/space
            while start > 0 and result[start - 1] in ' ,':
                start -= 1
            result = result[:start] + result[end:]
    return result


def _dedup_ltx_timing(text):
    """Deduplicate LTX timing/motion clauses that get stacked by 5 injection points.

    V21.4: The LTX prompt gets timing injected by:
    1. fix-v16 timing sync: "0-3s static hold, 3-10s slow dolly"
    2. fix-v16 director motion: "slow dolly, creep push, static dread" (from directors_library.json)
    3. fix-v16 director acting: "performance: the house is watching"
    4. Video render timing sync: ANOTHER "0-2s static hold, 2-10s slow push"
    5. Cinematic enricher: "at 0s: camera slowly establishes..." + director motion vocabulary (AGAIN)

    Result: "static hold" appears 2-3x, "slow dolly" appears 2-3x, "performance:" appears 2-3x.
    This confuses LTX-2 — it sees conflicting motion directions and defaults to static.

    Fix: Keep ONE clean numbered timing clause at the start, strip all unnumbered duplicates
    of camera motion words, and keep ONE performance note.
    """
    if not text or len(text) < 30:
        return text

    result = text

    # --- Phase 1: Find the first numbered timing clause and strip ALL subsequent timing ---
    # Pattern: "0-Ns word, M-Ns word" (the numbered timing)
    numbered_timing = re.search(r'0-\d+s\s+\w+[^.]*?(?:\d+-\d+s\s+\w+[^.]*?)*[.]', result)

    # --- Phase 2: Strip UNNUMBERED motion words that duplicate the numbered timing ---
    # These are bare "static hold, slow dolly" or "static hold, slow push" WITHOUT leading numbers
    # They come from director_motion injection (directors_library.json movement_vocabulary.default)
    # Pattern: standalone "static hold" or "slow dolly" etc NOT preceded by digits
    MOTION_WORDS = [
        "static hold", "slow dolly", "slow push", "slow crane", "slow pan",
        "creep push", "static dread", "steadicam",
    ]

    for word in MOTION_WORDS:
        escaped = re.escape(word)
        # Count occurrences
        all_matches = list(re.finditer(escaped, result, re.IGNORECASE))
        if len(all_matches) <= 1:
            continue

        # Keep the FIRST occurrence (usually inside the numbered timing clause)
        # Strip subsequent occurrences + any trailing comma/space
        for match in reversed(all_matches[1:]):
            start = match.start()
            end = match.end()
            # Eat trailing comma, space, period
            while end < len(result) and result[end] in ' .,;':
                end += 1
            # Also eat leading comma/space before this occurrence
            while start > 0 and result[start - 1] in ' ,':
                start -= 1
            result = result[:start] + result[end:]

    # --- Phase 3: Consolidate "at Ns:" timed motion cues ---
    # Enricher adds "at 0s: camera slowly establishes, at 3s: tension builds..."
    # These are GOOD if there's only one set, but enricher may add them multiple times
    at_cues = list(re.finditer(r'at \d+s:', result))
    if len(at_cues) > 4:
        # Too many — keep first 3-4, strip rest
        for match in reversed(at_cues[4:]):
            # Find end of this cue (up to next "at Ns:" or end of section)
            end = match.end()
            next_at = re.search(r'at \d+s:', result[end:])
            if next_at:
                end = end + next_at.start()
            else:
                # Find end of sentence
                period = result.find('.', end)
                if period > 0 and period - end < 150:
                    end = period + 1
            # Strip leading comma
            start = match.start()
            while start > 0 and result[start - 1] in ' ,':
                start -= 1
            result = result[:start] + result[end:]

    # --- Phase 4: Strip abstract director vocabulary that LTX can't interpret ---
    # These come from directors_library.json movement_vocabulary and are meant for
    # human directors, not video generation models. LTX needs concrete motion/timing.
    ABSTRACT_DIRECTOR_TERMS = [
        r"static dread[^.,]*[.,]?\s*",
        r"creep push[^.,]*[.,]?\s*",
        r"imperceptible zoom[^.,]*[.,]?\s*",
        r"low angle dutch[^.,]*[.,]?\s*",
        r"shadows reaching[^.,]*[.,]?\s*",
        r"hold static[^.,]*let performance carry[^.,]*[.,]?\s*",
    ]
    for pattern in ABSTRACT_DIRECTOR_TERMS:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # --- Phase 5: Strip orphaned/empty prefixes ---
    # After dedup, we can end up with "performance:" or "performance: ." with no content
    result = re.sub(r'performance:\s*[.,;]?\s*(?=performance:|$|[A-Z])', '', result)
    # Strip trailing "performance:" at end of prompt
    result = re.sub(r',?\s*performance:\s*$', '', result)

    # --- Phase 6: Strip duplicate "AUDIO:" blocks ---
    audio_matches = list(re.finditer(r'AUDIO:\s*[^.]*\.?\s*', result, re.IGNORECASE))
    if len(audio_matches) > 1:
        for m in reversed(audio_matches[1:]):
            result = result[:m.start()] + result[m.end():]

    return result


def _process_prompt(text, scene_id, characters, is_ltx=False):
    """Full dedup + strip pipeline for a single prompt field.

    V21.3: Unified pipeline for BOTH nano_prompt and ltx_motion_prompt.

    Args:
        text: The prompt text to process
        scene_id: Scene ID (e.g., "001", "002_INT")
        characters: List of character names in this shot
        is_ltx: True if this is ltx_motion_prompt (different size limit)

    Returns:
        Cleaned prompt text
    """
    if not text or len(text) < 20:
        return text

    sid = scene_id[:3] if scene_id else ""
    result = text

    # ---- STEP 0: STRIP HUMAN PERFORMANCE FROM NO-CHARACTER SHOTS ----
    # V21.6: Cinematic enricher blindly injects "micro-expressions", "moment of understanding
    # crosses the face", "mind racing behind still exterior" into LANDSCAPE shots.
    # FAL reads this and generates random people in coastline/building/empty room shots.
    # If characters list is empty, strip ALL human performance language.
    if not characters:
        _LANDSCAPE_STRIP = [
            r"Subject NOT looking directly into camera lens[.,]?\s*",
            r"eye-line \d+-\d+ degrees off-axis[.,]?\s*",
            r"subtext:\s*internal conflict[^.]*[.,]?\s*",
            r"subtext:\s*mind racing[^.]*[.,]?\s*",
            r"performance:\s*moment of understanding[^.]*[.,]?\s*",
            r"performance:\s*let the silence work[^.]*[.,]?\s*",
            r"performance:\s*stillness then reaction[^.]*[.,]?\s*",
            r"performance:\s*[^.,]{5,60}[.,]?\s*",
            r"body tells a different story[^.]*[.,]?\s*",
            r"processing visible only in eyes[^.]*[.,]?\s*",
            r"key light intensifies, warmer shift[.,]?\s*",
            r"moment of clarity in expression[.,]?\s*",
            r"moment of understanding[^.]*[.,]?\s*",
            r"micro-expression[s]?[^.]*[.,]?\s*",
            r"face stable NO morphing[.,]?\s*",
            r"character consistent[.,]?\s*",
            r"natural speech movement[.,]?\s*",
            r"lips moving[^.]*[.,]?\s*",
            r"lip sync[^.]*[.,]?\s*",
            r"jaw motion[^.]*[.,]?\s*",
            r"speaking cadence[^.]*[.,]?\s*",
            r"natural speaking[^.]*[.,]?\s*",
            r"dialogue context:[^.,]*[.,]?\s*",
            r"character speak(?:s|ing):[^.,]*[.,]?\s*",
            r"on speaker[^.,]*[.,]?\s*",
            r"delivers dialogue[^.,]*[.,]?\s*",
            r"emotion blend:\s*[^.]+[.,]?\s*",
            r"ACTING[^.]*[.,]?\s*",
        ]
        for _lp in _LANDSCAPE_STRIP:
            result = re.sub(_lp, ' ', result, flags=re.IGNORECASE)
        result = re.sub(r'\s{2,}', ' ', result).strip()

    # ---- STEP 1: STRIP GENERIC ARTIFACTS ----
    result = _strip_patterns(result, ALWAYS_STRIP)

    # ---- STEP 1.1: STRIP LTX-SPECIFIC ARTIFACTS (film stock, sensor, LUT) ----
    # V21.9.1: LTX-2 ignores camera bodies and film stock — these waste ~200 chars
    # of the 1500-char budget and directly cause extras truncation (Issue 1/4)
    if is_ltx:
        result = _strip_patterns(result, LTX_ALWAYS_STRIP)

    # ---- STEP 1.5: STRIP ALL AI ACTOR CONTAMINATION (UNIVERSAL) ----
    # V21.10: Safety net — catches ANY residual actor name/nationality/profession
    # that leaked through from ai_actors_library.json via _build_face_lock_text()
    # or inject_cast_traits(). Runs BEFORE per-character enforcement.
    # Uses dynamic patterns from active config, or hardcoded fallback.
    _universal_patterns = _build_dynamic_ai_actor_strip()
    for _ai_pat in _universal_patterns:
        result = re.sub(_ai_pat, '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s{2,}', ' ', result).strip()

    # ---- STEP 2: STRIP COLOR CONFLICTS ----
    result = _strip_color_conflicts(result, sid)

    # ---- STEP 3: STRIP SCENE-INAPPROPRIATE ATMOSPHERE ----
    result = _strip_scene_atmosphere(result, sid)

    # ---- STEP 4: ENFORCE CHARACTER AUTHORITY ----
    if not is_ltx:  # Character injection only in nano, not LTX
        for char_name in characters:
            result = _enforce_single_character(result, char_name, sid)

    # ---- STEP 4.5: LTX TIMING/MOTION DEDUP (LTX only) ----
    if is_ltx:
        result = _dedup_ltx_timing(result)

    # ---- STEP 4.6: CONSOLIDATE DIALOGUE MARKERS (LTX only) ----
    # V21.9.2: 7+ injection points each add dialogue with different markers.
    # Consolidates "dialogue context:", "character speaking:", "character speaks:"
    # into ONE clean "character speaks:" block. Saves 200-400 chars per dialogue shot.
    if is_ltx:
        result = _dedup_dialogue_markers(result)

    # ---- STEP 4.7: STRIP ACTING METRICS (LTX only) ----
    # V21.9.2: ACTING (bio-real) blocks contain numeric emotion metrics
    # (microleak scores, brow asymmetry) that LTX-2 can't interpret.
    # Replace with simple emotional direction. Saves 200-300 chars.
    if is_ltx:
        result = _strip_ltx_acting_metrics(result)

    # ---- STEP 5: DEDUPLICATE ENRICHMENT BLOCKS ----
    result = _dedup_blocks(result)

    # ---- STEP 5.5: DEDUPLICATE CAMERA DIRECTIONS ----
    # V21.9.1: Shot expansion + cinematic enricher both inject "camera holds steady" etc.
    result = _dedup_camera_directions(result)

    # ---- STEP 6: DEDUPLICATE EXACT PHRASES ----
    result = _dedup_exact_phrases(result)

    # ---- STEP 7: DEDUPLICATE NEGATIVE CONSTRAINT BLOCKS ----
    result = _dedup_negative_blocks(result)

    # ---- STEP 8: CLEANUP ----
    result = _cleanup_text(result)

    # ---- STEP 9: INJECT SCENE COLOR GRADE (nano only, if not present) ----
    if not is_ltx:
        grade_info = get_color_grades().get(sid)
        if grade_info and grade_info["grade"].split(",")[0].lower() not in result.lower():
            color_block = f" Color grade: {grade_info['grade']}. {grade_info['negative']}."
            inject_pos = result.find(". ", 100)
            if inject_pos > 0:
                result = result[:inject_pos+2] + color_block + " " + result[inject_pos+2:]
            else:
                result += color_block

    # ---- STEP 10: SMART TRUNCATE ----
    max_chars = LTX_MOTION_MAX_CHARS if is_ltx else NANO_PROMPT_MAX_CHARS
    result = _smart_truncate(result, max_chars)

    # ---- FINAL CLEANUP ----
    result = re.sub(r'\s{2,}', ' ', result).strip()

    return result


def enforce_prompt_authority(scene_shots, project_path=None, cast_map=None, story_bible=None):
    """
    FINAL AUTHORITY GATE — runs after ALL enrichment layers.
    Phase 1: Strips conflicts, deduplicates, enforces canonical descriptions.
             NOW processes BOTH nano_prompt AND ltx_motion_prompt.
    Phase 2: Injects script insight (beat actions, dialogue, atmosphere).

    Args:
        scene_shots: list of shot dicts (modified in-place)
        project_path: Path to project directory
        cast_map: Character cast mapping dict
        story_bible: Pre-loaded story bible (or loaded from project_path)

    Returns:
        dict with stats: {stripped, injected, color_fixed, ltx_fixed, total, script_insight,
                          nano_chars_before, nano_chars_after, ltx_chars_before, ltx_chars_after}
    """
    stats = {
        "stripped": 0, "injected": 0, "color_fixed": 0, "ltx_fixed": 0,
        "total": 0, "script_insight": None,
        "nano_chars_before": 0, "nano_chars_after": 0,
        "ltx_chars_before": 0, "ltx_chars_after": 0,
    }

    # V21.4: Load project-specific config if available (universal support)
    load_project_authority_config(project_path)

    for shot in scene_shots:
        shot_id = shot.get("shot_id", "")
        scene_id = shot.get("scene_id", "")
        sid = scene_id[:3] if scene_id else (shot_id.split("_")[0] if "_" in shot_id else "")
        characters = shot.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",") if c.strip()]

        # ======== PROCESS NANO_PROMPT ========
        nano = shot.get("nano_prompt", "")
        nano_before = len(nano)
        stats["nano_chars_before"] += nano_before

        nano = _process_prompt(nano, sid, characters, is_ltx=False)

        # V21.9: NANO DIRECTOR AUDIT — characterless shots should not have character language
        if not characters:
            nano = nano.replace('subjects isolated in architecture', 'negative space in composition')
            # Strip "None experiences/explains" generic actions
            nano = re.sub(r'Character action:\s*None\s+(?:experiences|explains)[^.]*\.?\s*', '', nano)

        shot["nano_prompt"] = nano
        stats["nano_chars_after"] += len(nano)

        if len(nano) < nano_before:
            stats["stripped"] += 1

        # ======== PROCESS LTX_MOTION_PROMPT ========
        ltx = shot.get("ltx_motion_prompt", "")
        ltx_before = len(ltx)
        stats["ltx_chars_before"] += ltx_before

        ltx = _process_prompt(ltx, sid, characters, is_ltx=True)

        # V21.9: CONFLICT RESOLUTION — resolve contradictions AFTER all processing
        ltx = resolve_ltx_conflicts(ltx, shot)

        shot["ltx_motion_prompt"] = ltx
        stats["ltx_chars_after"] += len(ltx)

        if len(ltx) < ltx_before:
            stats["ltx_fixed"] += 1

        # ======== MARK AS PROCESSED ========
        shot["_authority_gate"] = True
        shot["_authority_gate_version"] = "21.9"
        stats["total"] += 1

    # ================================================================
    # PHASE 2: SCRIPT INSIGHT INJECTION
    # After stripping conflicts, inject actual story content
    # ================================================================
    try:
        from tools.script_insight_engine import enrich_with_script_insight

        # Load story bible
        sb = story_bible
        sb_path = None
        if not sb and project_path:
            sb_path = os.path.join(project_path, "story_bible.json")
            if not os.path.exists(sb_path):
                sb_path = None

        insight_report = enrich_with_script_insight(
            scene_shots,
            story_bible=sb,
            story_bible_path=sb_path,
        )
        stats["script_insight"] = {
            "actions_injected": insight_report.get("actions_injected", 0),
            "dialogue_markers_added": insight_report.get("dialogue_markers_added", 0),
            "atmosphere_injected": insight_report.get("atmosphere_injected", 0),
            "avg_specificity": insight_report.get("avg_specificity", 0),
            "grade_distribution": insight_report.get("grade_distribution", {}),
        }
        logger.info(
            f"[AUTHORITY-GATE] Script insight: "
            f"actions={insight_report.get('actions_injected', 0)}, "
            f"dlg_markers={insight_report.get('dialogue_markers_added', 0)}, "
            f"atmosphere={insight_report.get('atmosphere_injected', 0)}, "
            f"avg_score={insight_report.get('avg_specificity', 0)}"
        )
    except Exception as _si_err:
        logger.warning(f"[AUTHORITY-GATE] Script insight non-blocking error: {_si_err}")

    # ================================================================
    # LOG SUMMARY
    # ================================================================
    nano_reduction = 0
    if stats["nano_chars_before"] > 0:
        nano_reduction = round(100 * (1 - stats["nano_chars_after"] / stats["nano_chars_before"]), 1)
    ltx_reduction = 0
    if stats["ltx_chars_before"] > 0:
        ltx_reduction = round(100 * (1 - stats["ltx_chars_after"] / stats["ltx_chars_before"]), 1)

    logger.info(
        f"[AUTHORITY-GATE V21.3] Processed {stats['total']} shots: "
        f"{stats['stripped']} nano stripped, {stats['ltx_fixed']} ltx stripped | "
        f"Nano: {stats['nano_chars_before']:,}→{stats['nano_chars_after']:,} chars ({nano_reduction}% reduction) | "
        f"LTX: {stats['ltx_chars_before']:,}→{stats['ltx_chars_after']:,} chars ({ltx_reduction}% reduction)"
    )
    return stats


# ============================================================
# V21.4 DO NOT RE-BREAK RULES (135-142)
# ============================================================
# 135. Narrative timing replaces numbered timing — "0-Ns static hold" is REMOVED — NEVER re-add
# 136. Dialogue shots use "natural speech movement" — NEVER add "face stable NO morphing" to dialogue
# 137. Non-dialogue shots keep "face stable NO morphing" — NEVER remove for non-speaking shots
# 138. LTX truncation is 1800 chars — NEVER lower below 1500 — dialogue gets cut
# 139. Authority Gate runs in ALL 4 endpoints — NEVER remove from any endpoint
# 140. Story bible beats have character_action field — NEVER strip during re-import
# 141. Location descriptions appear MAX ONCE in nano — NEVER allow triplication
# 142. Authority Gate errors captured by Sentry — NEVER remove _sentry_capture_exception calls


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/ravencroft_v17"

    # Simulate: load shot plan, apply gate, show results
    sp = json.load(open(os.path.join(project_dir, "shot_plan.json")))
    shots = [s for s in sp.get("shots", []) if s.get("scene_id", "")[:3] in ("001", "002", "003")]

    print(f"Testing Prompt Authority Gate V21.3 on {len(shots)} shots...")
    print(f"Before: {sum(len(s.get('nano_prompt','')) for s in shots):,} nano chars, "
          f"{sum(len(s.get('ltx_motion_prompt','')) for s in shots):,} ltx chars")

    stats = enforce_prompt_authority(shots, project_dir)

    print(f"\nResults: {json.dumps({k:v for k,v in stats.items() if k != 'script_insight'}, indent=2)}")
    print(f"Nano: {stats['nano_chars_before']:,} → {stats['nano_chars_after']:,} chars")
    print(f"LTX:  {stats['ltx_chars_before']:,} → {stats['ltx_chars_after']:,} chars")

    # Show samples
    for s in shots[:3]:
        print(f"\n--- {s['shot_id']} (nano: {len(s['nano_prompt'])} chars, ltx: {len(s.get('ltx_motion_prompt',''))} chars) ---")
        print(f"NANO: {s['nano_prompt'][:200]}...")
        print(f"LTX:  {s.get('ltx_motion_prompt','')[:200]}...")
