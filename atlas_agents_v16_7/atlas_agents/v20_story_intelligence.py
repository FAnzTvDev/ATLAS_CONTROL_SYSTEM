#!/usr/bin/env python3
"""
V20.1 Story Intelligence Layer — Director + Writer + Actor + Emotion Driven

THE PROBLEM WITH V20.0:
V20.0 enricher picks shot types by keyword matching ("pub" → dialogue_two_person).
That's MECHANICAL. It doesn't know:
  - WHY you picked OTS in V9 (power dynamic between characters)
  - WHY V9 held a wide shot (to show isolation, not just "geography")
  - WHY V9 used insert cutaways (to give the actor space, show props that matter)
  - WHAT the director's signature style would demand
  - WHAT the writer's subtext density means for shot pacing
  - HOW the actor's specialty affects which shots work best for them

V9 worked because YOU (the filmmaker) made MOTIVATED choices based on:
  1. Emotional arc of the scene (tension → release → escalation)
  2. Character power dynamics (who dominates, who submits, who surprises)
  3. Story beats (the WHAT matters more than the WHERE)
  4. Your director instinct (hold on faces when subtext is high, go wide when isolated)

THIS MODULE adds the layers V20.0 is missing:
  - Director profile → shot preferences, holding style, movement vocabulary
  - Writer profile → subtext density (high = more close-ups), silence usage (= hold longer)
  - Actor specialty → some actors shine in close-ups, some in physical wide shots
  - Emotional arc → escalate shot tightness as emotion intensifies
  - Character dynamics → power shifts drive OTS and reverse choices
  - Wardrobe intelligence → outfit changes at scene boundaries, specificity in tags

DESIGN PRINCIPLE: This is NOT a replacement for V20.0. It's a POST-PROCESSOR
that takes V20.0's mechanical types and adds filmmaker motivation.
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DIRECTOR SHOT PHILOSOPHY — How directors think about shot selection
# ═══════════════════════════════════════════════════════════════════

# Director shot_braintree_overrides apply PER SHOT TYPE
# Example: Helena Blackwood's establishing = "wide drone fog approach"
# Example: Helena Blackwood's dialogue = "OTS with reaction holds"
# Example: Helena Blackwood's horror_beat = "static wide, subject small in frame"
# Example: Helena Blackwood's revelation = "slow push to CU, rack focus"

def load_director_shot_philosophy(director_name: str, directors_library: List[Dict]) -> Dict:
    """
    Extract a director's shot-selection philosophy from directors_library.json.
    Returns a dict mapping shot contexts → director preferences.
    """
    if not directors_library:
        return {}

    # Find the director
    director = None
    for d in directors_library:
        if isinstance(d, dict) and d.get("name", "").lower() == director_name.lower():
            director = d
            break

    if not director:
        return {}

    philosophy = {}

    # Visual signature
    vs = director.get("visual_signature", {})
    philosophy["camera_philosophy"] = vs.get("camera_philosophy", "")
    philosophy["composition_style"] = vs.get("composition_style", "")

    # Movement vocabulary — tells us WHEN to use which camera movement
    mv = vs.get("movement_vocabulary", {})
    if isinstance(mv, dict):
        philosophy["movement_by_emotion"] = mv
    elif isinstance(mv, str):
        philosophy["movement_default"] = mv

    # Lens preferences — tells us WHICH lens for which shot type
    lp = vs.get("lens_preferences", {})
    if isinstance(lp, dict):
        philosophy["lens_by_type"] = lp

    # Shot braintree overrides — the gold: director's ACTUAL shot-type preferences
    sbo = director.get("shot_braintree_overrides", {})
    philosophy["shot_overrides"] = sbo

    # Signature technique — e.g. "The Blackwood Hold - never cut before the actor breaks"
    cp = director.get("creative_philosophy", {})
    philosophy["signature_technique"] = cp.get("signature_technique", "")
    philosophy["core_belief"] = cp.get("core_belief", "")

    return philosophy


# ═══════════════════════════════════════════════════════════════════
# WRITER PACING INFLUENCE — How the writer's style affects shot rhythm
# ═══════════════════════════════════════════════════════════════════

def load_writer_pacing(writer_name: str, writers_library: List[Dict]) -> Dict:
    """
    Extract writer pacing preferences that affect shot selection.
    High subtext → more close-ups (reading faces matters)
    Frequent silences → more reaction shots (silence IS the story)
    Monologue tendency → longer medium holds
    """
    if not writers_library:
        return {}

    writer = None
    for w in writers_library:
        if isinstance(w, dict) and w.get("name", "").lower() == writer_name.lower():
            writer = w
            break

    if not writer:
        return {}

    vc = writer.get("voice_characteristics", {})
    ds = vc.get("dialogue_style", {}) if isinstance(vc, dict) else {}

    return {
        "subtext_density": ds.get("subtext_density", 0.5) if isinstance(ds, dict) else 0.5,
        "silence_usage": vc.get("silence_usage", "normal") if isinstance(vc, dict) else "normal",
        "monologue_tendency": vc.get("monologue_tendency", "normal") if isinstance(vc, dict) else "normal",
        "interruption_frequency": ds.get("interruption_frequency", "normal") if isinstance(ds, dict) else "normal",
    }


# ═══════════════════════════════════════════════════════════════════
# ACTOR SPECIALTY INFLUENCE — How cast profiles affect shot selection
# ═══════════════════════════════════════════════════════════════════

def get_actor_shot_affinity(cast_entry: Dict, actor_library: List[Dict] = None) -> Dict:
    """
    Determine which shot types work best for this actor's specialty.

    Example:
      - Actor with specialty=["Action"] → tracking shots, wide shots showcase them
      - Actor with specialty=["Drama"] → close-ups, reaction shots showcase them
      - Actor with ltx_motion_default="intense stillness" → CU holds work well
      - Actor with ltx_motion_default="controlled martial arts" → wide shots showcase
    """
    affinity = {"prefers_close": False, "prefers_wide": False, "prefers_movement": False}

    # From cast_map entry
    appearance = cast_entry.get("appearance", "")
    if isinstance(appearance, dict):
        appearance = appearance.get("distinguishing", "")

    # From actor library entry
    actor_name = cast_entry.get("actor_name", "")
    actor_data = {}
    if actor_library:
        for a in actor_library:
            if isinstance(a, dict) and a.get("name", "") == actor_name:
                actor_data = a
                break

    specialties = actor_data.get("specialty", [])
    ltx_default = actor_data.get("ltx_motion_default", "")

    # Actors who shine in close-ups (drama, stillness, method)
    close_keywords = ["drama", "stillness", "method", "intense", "subtle", "measured"]
    if any(kw in str(specialties).lower() or kw in ltx_default.lower() for kw in close_keywords):
        affinity["prefers_close"] = True

    # Actors who shine in wide/tracking (action, movement, physical)
    wide_keywords = ["action", "martial", "physical", "tracking", "movement", "stunt"]
    if any(kw in str(specialties).lower() or kw in ltx_default.lower() for kw in wide_keywords):
        affinity["prefers_wide"] = True
        affinity["prefers_movement"] = True

    return affinity


# ═══════════════════════════════════════════════════════════════════
# EMOTIONAL ARC ENGINE — Escalate shot tightness with emotion
# ═══════════════════════════════════════════════════════════════════

# Emotion keywords → intensity level (0-10)
# Uses prefix matching — "apprehens" catches "apprehension", "apprehensive"
EMOTION_INTENSITY = {
    # Low intensity (wide/medium) — scene-setting, neutral
    "neutral": 2, "calm": 2, "observation": 2, "mundane": 1,
    "quiet": 2, "still": 2, "peaceful": 2, "serene": 2,
    # Mild engagement (3)
    "curious": 3, "cautious": 3, "uncertain": 3, "wary": 3,
    "contempl": 3, "ponder": 3, "thoughtful": 3, "reflect": 3,
    "hesita": 3, "reluct": 3, "comfort": 3, "warm": 3,
    # Moderate engagement (4)
    "concern": 4, "suspicion": 4, "interest": 4, "isol": 4,
    "alone": 4, "lonely": 4, "uneasy": 4, "relief": 4, "hope": 4,
    "nostalgic": 4, "melanchol": 4, "wistful": 4,
    # Rising tension (5)
    "determin": 5, "resolut": 5, "defian": 5, "brave": 5,
    "tension": 5, "tense": 5, "anxiety": 5, "anxious": 5,
    "urgency": 5, "urgent": 5, "conflict": 5, "nervous": 5,
    "suspici": 5, "eerie": 5, "uneas": 5, "troubl": 5,
    "apprehens": 5, "forebod": 5, "ominous": 5,
    # Significant emotion (6)
    "confront": 6, "accus": 6, "demand": 6, "sinister": 6,
    "menac": 6, "haunt": 6, "supernatural": 6, "ghostly": 6,
    "discover": 6, "escap": 6, "abandon": 6, "betray": 6,
    "disturb": 6, "distress": 6, "anguish": 6,
    # High intensity (7)
    "fear": 7, "dread": 7, "anger": 7, "threat": 7, "danger": 7,
    "flee": 7, "mourn": 7, "realiz": 7, "sorrow": 7,
    "panick": 7, "scream": 7, "cry": 7, "weep": 7,
    # Peak emotion (8)
    "grief": 8, "horror": 8, "shock": 8, "revelation": 8,
    "panick": 8, "violent": 8, "attack": 8,
    # Extreme (9-10)
    "despair": 9, "rage": 9, "terror": 10, "death": 9,
    # Resolution (pulls back)
    "acceptance": 3, "resolution": 3, "peace": 2,
}

def get_emotion_intensity(shot: Dict) -> int:
    """Extract emotional intensity from ALL text fields on the shot."""
    texts = []
    texts.append((shot.get("description", "") or "").lower())
    texts.append((shot.get("beat_description", "") or "").lower())
    texts.append((shot.get("dialogue_text", "") or "").lower())
    texts.append((shot.get("dialogue", "") or "").lower())
    texts.append((shot.get("emotion", "") or "").lower())
    # Also scan nano_prompt — it has the richest text after enrichment
    texts.append((shot.get("nano_prompt", "") or "").lower())
    combined = " ".join(texts)

    best_intensity = 2  # default neutral
    for keyword, intensity in EMOTION_INTENSITY.items():
        if keyword in combined:
            best_intensity = max(best_intensity, intensity)

    return best_intensity


def emotion_to_shot_bias(intensity: int) -> str:
    """
    Convert emotion intensity to a shot-type bias.
    This is the FILMMAKER INSTINCT: as emotion rises, camera gets closer.
    """
    if intensity <= 2:
        return "wide"       # Neutral → show the space
    elif intensity <= 4:
        return "medium"     # Engaged → see the person
    elif intensity <= 6:
        return "medium_close"  # Tense → read the face
    elif intensity <= 8:
        return "close"      # Peak → emotion fills the frame
    else:
        return "close"      # Extreme → nothing but the face


# ═══════════════════════════════════════════════════════════════════
# CHARACTER POWER DYNAMICS — Who dominates drives OTS/reverse choices
# ═══════════════════════════════════════════════════════════════════

POWER_KEYWORDS = {
    "dominant": ["demands", "orders", "commands", "towers", "grabs", "controls",
                 "threatens", "accuses", "confronts", "glares", "slams"],
    "submissive": ["shrinks", "retreats", "stammers", "flinches", "apologizes",
                   "pleads", "whispers", "cowers", "backs away", "trembles"],
    "equal": ["debate", "discuss", "agree", "both", "together", "face to face",
              "stand off", "neither", "match"],
}

def detect_power_dynamic(shot: Dict, scene_shots: List[Dict]) -> str:
    """Detect character power dynamic in this shot. Returns 'dominant', 'submissive', 'equal', or 'neutral'."""
    text = (
        (shot.get("description", "") or "") + " " +
        (shot.get("dialogue_text", "") or "") + " " +
        (shot.get("beat_description", "") or "")
    ).lower()

    scores = {k: sum(1 for kw in kws if kw in text) for k, kws in POWER_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"


# ═══════════════════════════════════════════════════════════════════
# WARDROBE INTELLIGENCE — Smart outfit descriptions, not "dark dark"
# ═══════════════════════════════════════════════════════════════════

def enrich_wardrobe_tag(character: str, scene_id: str, story_bible: Dict,
                        cast_map: Dict, wardrobe: Dict) -> str:
    """
    Build a SPECIFIC wardrobe tag from all available sources.
    V9 had: "long dark charcoal coat, cream envelope, wire-frame glasses"
    V18 has: "dark dark"

    This function combines: story bible description + cast appearance + actor image_prompt
    to build something V9-quality but automatic.
    """
    parts = []

    # 1. From cast_map appearance
    cast_entry = cast_map.get(character, {})
    if isinstance(cast_entry, dict):
        app = cast_entry.get("appearance", "")
        if isinstance(app, dict):
            app = app.get("distinguishing", "") or app.get("build", "")
        if app and len(app) > 5:
            # Extract clothing-specific words
            clothing_words = extract_clothing_from_text(app)
            if clothing_words:
                parts.append(clothing_words)

    # 2. From story bible character description
    for char_data in story_bible.get("characters", []):
        if isinstance(char_data, dict):
            if char_data.get("name", "").upper() == character.upper():
                desc = char_data.get("description", "") or ""
                app = char_data.get("appearance", "") or ""
                clothing = extract_clothing_from_text(f"{desc} {app}")
                if clothing:
                    parts.append(clothing)
                break

    # 3. From existing wardrobe.json (only if it's specific enough)
    look_key = f"{character}::{scene_id}"
    existing = wardrobe.get("looks", {}).get(look_key, {})
    existing_tag = existing.get("wardrobe_tag", "")
    existing_desc = existing.get("description", "")

    # If existing tag is too vague (like "dark dark"), rebuild it
    if existing_tag and len(existing_tag) > 15 and not _is_vague_tag(existing_tag):
        return existing_tag

    # 4. From wardrobe description — pull full clothing context
    if existing_desc and len(existing_desc) > 10:
        desc_clothing = extract_clothing_from_text(existing_desc)
        if desc_clothing and len(desc_clothing) > 5:
            parts.append(desc_clothing)

    if not parts:
        # Last resort: use the description with age/face removed
        if existing_desc:
            # Strip age/appearance prefixes, keep clothing
            stripped = re.sub(
                r'^(?:late|early|mid)\s+\d+s?,?\s*', '', existing_desc, flags=re.IGNORECASE
            ).strip()
            stripped = re.sub(
                r'^(?:dark hair|blonde|redhead|stocky|slim|tall|short),?\s*',
                '', stripped, flags=re.IGNORECASE
            ).strip()
            if stripped and len(stripped) > 10:
                return stripped[:120]
        return ""

    # Deduplicate and combine
    combined = ", ".join(dict.fromkeys(parts))
    return combined[:120]


CLOTHING_NOUNS = (
    r'coat|jacket|dress|suit|shirt|blouse|trousers|pants|skirt|gown|robe|'
    r'cloak|cape|vest|sweater|hoodie|uniform|armor|tie|scarf|hat|cap|'
    r'glasses|boots|shoes|heels|sandals|gloves|ring|necklace|bracelet|'
    r'watch|bag|purse|briefcase|envelope|attire|clothing|outfit|garment|'
    r'tweed|leather|silk|cotton|wool|denim|linen|velvet|satin|robes|'
    r'waistcoat|overcoat|cardigan|jewelry'
)

# Match adjective(s) + clothing noun for richer phrases
# e.g., "long dark charcoal coat", "formal black suit", "dark practical clothing"
CLOTHING_PHRASE_PATTERN = re.compile(
    r'(?:(?:long|short|dark|light|black|white|grey|gray|brown|navy|'
    r'red|blue|green|cream|charcoal|burgundy|crimson|emerald|golden|'
    r'silver|old|new|worn|pristine|elegant|shabby|formal|casual|'
    r'practical|ornate|ritualistic|heavy|thin|thick|tailored|loose|'
    r'fitted|flowing|weathered|vintage|antique|modern|traditional|'
    r'expensive|cheap|modest|fancy|plain|simple|luxurious|'
    r'wire-frame|horn-rimmed|reading|round|square)\s+)*'
    r'(?:' + CLOTHING_NOUNS + r')',
    re.IGNORECASE
)

CLOTHING_SIMPLE = re.compile(r'\b(' + CLOTHING_NOUNS + r')\b', re.IGNORECASE)


def extract_clothing_from_text(text: str) -> str:
    """Extract clothing-specific phrases from a description, preserving adjectives."""
    if not text:
        return ""
    # First try phrase extraction (adjective + clothing noun)
    phrases = CLOTHING_PHRASE_PATTERN.findall(text)
    if phrases:
        # Clean up matches — findall on groups can be messy
        clean = []
        for p in phrases:
            p = p.strip()
            if p and len(p) > 2:
                clean.append(p.lower())
        if clean:
            return ", ".join(dict.fromkeys(clean))

    # Fallback: try extracting full clause that contains clothing word
    # e.g., "often in dark practical clothing" → "dark practical clothing"
    for match in CLOTHING_SIMPLE.finditer(text):
        start = max(0, match.start() - 40)
        clause = text[start:match.end()].strip()
        # Find the start of the phrase (after comma, period, or beginning)
        for sep in [',', '.', ';', ':', '\n']:
            if sep in clause:
                clause = clause.split(sep)[-1].strip()
        # Remove leading "in", "wearing", "dressed in"
        clause = re.sub(r'^(?:often\s+)?(?:in|wearing|dressed\s+in)\s+', '', clause, flags=re.IGNORECASE)
        if clause and len(clause) > 3:
            return clause.lower()

    return ""


def _is_vague_tag(tag: str) -> bool:
    """Check if a wardrobe tag is too vague to be useful for V9-quality prompts.
    V9 had: 'long dark charcoal coat, cream envelope, wire-frame glasses'
    Vague means: 'dark dark', 'practical clothing', 'formal suit tie'
    """
    vague_patterns = [
        "dark dark", "light light", "casual casual", "formal formal",
        "dark clothing", "practical clothing", "formal suit",
        "formal suit tie", "dark practical", "white dark",
    ]
    tag_lower = tag.lower().strip()
    if len(tag_lower) < 20:
        return True
    if tag_lower in vague_patterns:
        return True
    words = tag_lower.split()
    if len(words) == 2 and words[0] == words[1]:
        return True
    # Tags with fewer than 3 descriptive words are vague
    if len(words) < 3:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════
# V20.1 STORY INTELLIGENCE ENRICHER — Main Entry Point
# ═══════════════════════════════════════════════════════════════════

class StoryIntelligenceEnricher:
    """
    Post-processes V20.0 enriched shots with filmmaker intelligence.
    Reads director/writer/actor profiles and applies motivated shot adjustments.
    """

    def __init__(self, project_path: Path, story_bible: Dict = None,
                 cast_map: Dict = None, director_name: str = None,
                 writer_name: str = None):
        self.project_path = Path(project_path)
        self.story_bible = story_bible or {}
        self.cast_map = cast_map or {}
        self.director_name = director_name
        self.writer_name = writer_name

        # Load libraries
        base = self.project_path.parent.parent  # Back to ATLAS_CONTROL_SYSTEM
        if not base.exists():
            base = Path(".")

        self.directors = []
        self.writers = []
        self.actors = []

        dl_path = base / "directors_library.json"
        if dl_path.exists():
            with open(dl_path) as f:
                data = json.load(f)
                self.directors = data.get("directors", data) if isinstance(data, dict) else data

        wl_path = base / "writers_library.json"
        if wl_path.exists():
            with open(wl_path) as f:
                data = json.load(f)
                self.writers = data.get("writers", data) if isinstance(data, dict) else data

        al_path = base / "ai_actors_library.json"
        if al_path.exists():
            with open(al_path) as f:
                data = json.load(f)
                self.actors = data.get("actors", data) if isinstance(data, dict) else data

        # Genre-based auto-detection of director + writer
        # If no director/writer specified, use genre_to_X_mapping from libraries
        genre = self.story_bible.get("genre", "").lower().strip()
        self._director_genre_map = {}
        self._writer_genre_map = {}

        if dl_path.exists():
            with open(dl_path) as f:
                dl_full = json.load(f)
            if isinstance(dl_full, dict):
                self._director_genre_map = dl_full.get("genre_to_director_mapping", {})

        if wl_path.exists():
            with open(wl_path) as f:
                wl_full = json.load(f)
            if isinstance(wl_full, dict):
                self._writer_genre_map = wl_full.get("genre_to_writer_mapping", {})

        if not self.director_name and genre and genre in self._director_genre_map:
            director_id = self._director_genre_map[genre]
            for d in self.directors:
                if isinstance(d, dict) and d.get("id", "") == director_id:
                    self.director_name = d["name"]
                    logger.info(f"[V20.1] Auto-detected director: {self.director_name} (genre={genre})")
                    break

        if not self.writer_name and genre and genre in self._writer_genre_map:
            writer_id = self._writer_genre_map[genre]
            for w in self.writers:
                if isinstance(w, dict) and w.get("id", "") == writer_id:
                    self.writer_name = w["name"]
                    logger.info(f"[V20.1] Auto-detected writer: {self.writer_name} (genre={genre})")
                    break

        # Load wardrobe
        self.wardrobe = {}
        wd_path = self.project_path / "wardrobe.json"
        if wd_path.exists():
            with open(wd_path) as f:
                self.wardrobe = json.load(f)

        # Load director/writer philosophies
        self.director_philosophy = {}
        if self.director_name:
            self.director_philosophy = load_director_shot_philosophy(
                self.director_name, self.directors
            )

        self.writer_pacing = {}
        if self.writer_name:
            self.writer_pacing = load_writer_pacing(self.writer_name, self.writers)

    def enrich(self, dry_run: bool = False) -> Dict:
        """
        Apply story intelligence to shot_plan.json.
        This runs AFTER v20_shot_type_enricher.py — it refines, not replaces.
        """
        sp_path = self.project_path / "shot_plan.json"
        if not sp_path.exists():
            return {"error": "shot_plan.json not found"}

        with open(sp_path) as f:
            shot_plan = json.load(f)

        shots = shot_plan if isinstance(shot_plan, list) else shot_plan.get("shots", [])

        # Group by scene
        scenes = {}
        for s in shots:
            sid = s.get("scene_id", "?")
            scenes.setdefault(sid, []).append(s)

        total_changes = 0
        wardrobe_fixes = 0
        emotion_adjustments = 0
        director_overrides = 0

        for scene_id, scene_shots in scenes.items():
            for i, shot in enumerate(scene_shots):
                changes = self._apply_intelligence(shot, i, scene_shots, scene_id)
                total_changes += changes["type_changed"]
                wardrobe_fixes += changes["wardrobe_fixed"]
                emotion_adjustments += changes["emotion_adjusted"]
                director_overrides += changes["director_override"]

        if not dry_run and total_changes + wardrobe_fixes > 0:
            with open(sp_path, "w") as f:
                json.dump(shot_plan, f, indent=2, default=str)
            logger.info(f"[V20.1] Applied {total_changes} type changes, {wardrobe_fixes} wardrobe fixes")

            # Also write back enriched wardrobe
            if wardrobe_fixes > 0:
                wd_path = self.project_path / "wardrobe.json"
                with open(wd_path, "w") as f:
                    json.dump(self.wardrobe, f, indent=2, default=str)

        return {
            "status": "dry_run" if dry_run else "applied",
            "total_shots": len(shots),
            "type_changes": total_changes,
            "wardrobe_fixes": wardrobe_fixes,
            "emotion_adjustments": emotion_adjustments,
            "director_overrides": director_overrides,
            "director": self.director_name or "(none)",
            "writer": self.writer_name or "(none)",
        }

    def _apply_intelligence(self, shot: Dict, idx: int,
                            scene_shots: List[Dict], scene_id: str) -> Dict:
        """Apply all intelligence layers to a single shot."""
        result = {"type_changed": 0, "wardrobe_fixed": 0,
                  "emotion_adjusted": 0, "director_override": 0}

        current_type = shot.get("shot_type", shot.get("type", "medium"))
        new_type = current_type

        # ─── LAYER 1: Emotional Arc ───
        intensity = get_emotion_intensity(shot)
        emotion_bias = emotion_to_shot_bias(intensity)

        # If emotion is HIGH but shot type is WIDE, that's wrong
        # (unless it's intentional isolation — director can override)
        if intensity >= 7 and current_type in ("wide", "establishing"):
            # Check if director's signature_technique suggests holding wide
            sig = self.director_philosophy.get("signature_technique", "").lower()
            if "small in frame" in sig or "isolation" in sig or "vast space" in sig:
                pass  # Director wants wide for horror effect
            else:
                new_type = "close"
                result["emotion_adjusted"] = 1

        # If emotion is LOW but shot is tight close-up, that's wasted
        if intensity <= 3 and current_type == "close" and idx > 0:
            # Don't change reaction shots or insert shots
            if current_type not in ("reaction", "insert", "detail"):
                new_type = "medium"
                result["emotion_adjusted"] = 1

        # ─── LAYER 2: Writer Subtext Density ───
        subtext = self.writer_pacing.get("subtext_density", 0.5)
        if subtext >= 0.8:
            # High subtext writer → more close-ups during dialogue
            has_dialogue = bool((shot.get("dialogue_text", "") or "").strip())
            if has_dialogue and current_type == "medium":
                # Upgrade some dialogue mediums to close (not all — every 3rd)
                if idx % 3 == 0:
                    new_type = "close"
                    result["emotion_adjusted"] = 1

        # Writer silence_usage affects reaction shots
        silence = self.writer_pacing.get("silence_usage", "normal")
        if silence in ("frequent_and_meaningful", "power_move"):
            # More reaction shots where there's no dialogue
            has_no_dialogue = not bool((shot.get("dialogue_text", "") or "").strip())
            if has_no_dialogue and current_type == "medium" and idx > 1:
                prev = scene_shots[idx - 1]
                if bool((prev.get("dialogue_text", "") or "").strip()):
                    # Previous shot had dialogue, this one doesn't → reaction
                    new_type = "reaction"
                    result["emotion_adjusted"] = 1

        # ─── LAYER 3: Director Shot Overrides ───
        # Director overrides are FLAVOR — they don't convert every shot.
        # Each director has 4-6 override contexts (dialogue, establishing,
        # tension, confrontation, revelation, etc.) that map to their signature style.
        overrides = self.director_philosophy.get("shot_overrides", {})
        if overrides:
            has_dialogue = bool((shot.get("dialogue_text", "") or "").strip())
            desc_lower = (shot.get("description", "") or "").lower()
            nano_lower = (shot.get("nano_prompt", "") or "").lower()
            combined_text = f"{desc_lower} {nano_lower}"
            chars = shot.get("characters", [])
            if isinstance(chars, str):
                chars = [c.strip() for c in chars.split(",")]
            has_multi_chars = len(chars) >= 2

            # Detect shot CONTEXT from content (not just type)
            context = self._detect_shot_context(shot, intensity, has_dialogue, combined_text)

            # Apply director's override for detected context
            if context in overrides:
                directive = overrides[context].get("default", "")
                dur_hint = overrides[context].get("duration")
                hold_hint = overrides[context].get("hold")

                # Duration and hold hints always apply
                if dur_hint:
                    shot["_director_duration_hint"] = dur_hint
                if hold_hint:
                    shot["_director_hold_hint"] = hold_hint

                # Type changes are selective — ~30% of applicable shots, not all
                # This creates editorial rhythm, not monotony
                if idx % 3 == 2 or intensity >= 7:
                    type_from_directive = self._directive_to_type(directive, current_type, has_multi_chars)
                    if type_from_directive and type_from_directive != current_type:
                        new_type = type_from_directive
                        result["director_override"] = 1

            # Establishing shots always get director duration hints
            elif current_type == "establishing" and "establishing" in overrides:
                dur_override = overrides["establishing"].get("duration")
                if dur_override:
                    shot["_director_duration_hint"] = dur_override

        # ─── LAYER 4: Character Power Dynamics ───
        power = detect_power_dynamic(shot, scene_shots)
        chars = shot.get("characters", [])
        if isinstance(chars, str):
            chars = [c.strip() for c in chars.split(",")]

        if power == "dominant" and len(chars) >= 2 and current_type == "medium":
            # Dominant character → OTS from submissive POV, but only if
            # director hasn't already changed this shot (avoid double override)
            if result["director_override"] == 0 and intensity >= 5:
                new_type = "over_the_shoulder"
                result["type_changed"] = 1

        # ─── LAYER 5: Actor Specialty ───
        if chars:
            primary_char = chars[0] if isinstance(chars[0], str) else chars[0].get("name", "")
            cast_entry = self.cast_map.get(primary_char, {})
            affinity = get_actor_shot_affinity(cast_entry, self.actors)

            # If actor prefers close and we're on a generic medium, consider close
            if affinity.get("prefers_close") and current_type == "medium" and intensity >= 5:
                new_type = "medium_close"
                result["type_changed"] = 1

        # ─── LAYER 6: Wardrobe Specificity ───
        if chars:
            for char_name in chars:
                if isinstance(char_name, dict):
                    char_name = char_name.get("name", "")
                if not char_name:
                    continue

                new_tag = enrich_wardrobe_tag(
                    char_name, scene_id, self.story_bible,
                    self.cast_map, self.wardrobe
                )
                if new_tag:
                    look_key = f"{char_name.upper()}::{scene_id}"
                    if look_key in self.wardrobe.get("looks", {}):
                        old_tag = self.wardrobe["looks"][look_key].get("wardrobe_tag", "")
                        if _is_vague_tag(old_tag) and len(new_tag) > len(old_tag):
                            self.wardrobe["looks"][look_key]["wardrobe_tag"] = new_tag
                            result["wardrobe_fixed"] = 1

        # Apply type change (write to BOTH fields for consistency)
        if new_type != current_type:
            shot["type"] = new_type
            shot["shot_type"] = new_type
            shot["_v20_1_original"] = current_type
            shot["_v20_1_reason"] = self._explain_change(
                current_type, new_type, intensity, power
            )
            result["type_changed"] = 1

        # Store emotion intensity for downstream use
        shot["_emotion_intensity"] = intensity

        return result

    def _detect_shot_context(self, shot: Dict, intensity: int,
                              has_dialogue: bool, combined_text: str) -> str:
        """Map shot content to director override context.
        Each director has different context names (dialogue, interrogation,
        action_beat, confrontation, etc.) — this detects which one applies.
        """
        # High-emotion keywords that map to specific director contexts
        TENSION_WORDS = {"confront", "argue", "demand", "threaten", "challenge",
                         "tension", "standoff", "face off", "clash"}
        REVEAL_WORDS = {"reveal", "discover", "realize", "uncover", "truth",
                        "secret", "learn", "shock", "understand", "revelation"}
        ACTION_WORDS = {"fight", "chase", "run", "attack", "strike", "punch",
                        "kick", "combat", "battle", "struggle", "escape"}
        INVESTIGATE_WORDS = {"investigate", "examine", "evidence", "clue",
                            "search", "inspect", "forensic", "crime scene"}
        EMOTIONAL_WORDS = {"cry", "weep", "grief", "loss", "mourn", "embrace",
                          "comfort", "heartbreak", "farewell", "goodbye"}

        # Check for specific contexts based on content
        words_in_text = set(combined_text.split())

        if words_in_text & ACTION_WORDS:
            return "action_beat"
        if words_in_text & INVESTIGATE_WORDS:
            return "investigation"
        if intensity >= 8 and (words_in_text & TENSION_WORDS):
            return "confrontation"
        if words_in_text & REVEAL_WORDS:
            return "revelation"
        if words_in_text & EMOTIONAL_WORDS:
            return "emotional"
        if intensity >= 7 and has_dialogue:
            return "tension"
        if has_dialogue:
            return "dialogue"
        if shot.get("shot_type", "") == "establishing":
            return "establishing"
        return ""

    def _directive_to_type(self, directive: str, current_type: str,
                           has_multi_chars: bool) -> str:
        """Convert a director's textual directive into a shot type.
        e.g., 'OTS with reaction holds' → 'over_the_shoulder'
        e.g., 'tight two-shot' → 'two_shot'
        e.g., 'extreme close-up' → 'close'
        """
        d = directive.upper()
        if "OTS" in d and has_multi_chars:
            return "over_the_shoulder"
        if "EXTREME" in d and ("CLOSE" in d or "CU" in d):
            return "close"
        if "CU" in d or "CLOSE-UP" in d or "CLOSE UP" in d:
            return "close"
        if "TWO-SHOT" in d or "TWO SHOT" in d:
            return "two_shot"
        if "WIDE" in d and current_type not in ("wide", "establishing"):
            return "wide"
        if "TRACKING" in d:
            return "tracking"
        if "MEDIUM" in d and "CLOSE" in d:
            return "medium_close"
        if "REACTION" in d:
            return "reaction"
        if "INSERT" in d:
            return "insert"
        # Don't change if we can't parse the directive
        return ""

    def _explain_change(self, old: str, new: str, intensity: int, power: str) -> str:
        """Human-readable explanation of why the shot type was changed."""
        reasons = []
        if intensity >= 7:
            reasons.append(f"high emotion ({intensity}/10)")
        if power in ("dominant", "submissive"):
            reasons.append(f"power dynamic ({power})")
        if self.director_name:
            reasons.append(f"director: {self.director_name}")
        return f"{old}→{new}: " + ", ".join(reasons) if reasons else f"{old}→{new}"


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def apply_story_intelligence(project_path: Path, story_bible: Dict = None,
                              cast_map: Dict = None, director_name: str = None,
                              writer_name: str = None, dry_run: bool = False) -> Dict:
    """
    Apply story intelligence layer to a project's shot types.
    Call this AFTER v20_shot_type_enricher and BEFORE generation.

    Args:
        project_path: Path to pipeline_outputs/{project}
        story_bible: Story bible data (loaded from story_bible.json)
        cast_map: Cast map data (loaded from cast_map.json)
        director_name: Name matching directors_library.json entry
        writer_name: Name matching writers_library.json entry
        dry_run: If True, don't write changes
    """
    enricher = StoryIntelligenceEnricher(
        project_path, story_bible, cast_map, director_name, writer_name
    )
    return enricher.enrich(dry_run=dry_run)
