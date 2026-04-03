"""
ATLAS V17.3 — Cinematic Quality Enricher

Restores V14/V15-level cinematic quality to V17 prompts by injecting:
1. Film Stock & Sensor vocabulary (focal length + color science, NO brand names)
2. Humanization layer (blinks, breathing, micro-expressions)
3. Smart Continuity directives (per-character chaining)
4. Timed Motion cues for LTX video generation
5. Director Vision layer (camera philosophy, movement vocabulary, lighting
   signature, lens preferences, shot braintree overrides from directors_library.json)
6. Performance Notes layer (emotion-driven acting direction, writer silence_usage,
   monologue_tendency from writers_library.json)
7. Subtext Layer (body-language-contradicts-dialogue direction when writer
   subtext_density >= 0.7, scaled intensity at 0.9+)

This module is the BRIDGE between V17's casting system and V14's prompt quality.
The casting system provides character/location locks — this module adds the
cinematic VOCABULARY that makes AI-generated frames look like real film.

Director profiles (directors_library.json) inject:
  - visual_signature.camera_philosophy → guiding note in every prompt
  - visual_signature.movement_vocabulary → per-emotion camera motion overrides
  - visual_signature.lighting_signature → philosophy, palette, ratio, instruments
  - visual_signature.lens_preferences → per-shot-type lens choices
  - visual_signature.color_grade → override film profile grade (primary, shadow_tone, skin)
  - visual_signature.composition_style → framing philosophy
  - shot_braintree_overrides → per-shot-type duration/motion/lighting overrides
  - sample_direction → director tone quotes
  - creative_philosophy.signature_technique → unique directorial technique

Writer profiles (writers_library.json) inject:
  - voice_characteristics.dialogue_style.subtext_density → subtext layer activation
  - voice_characteristics.silence_usage → pacing direction
  - voice_characteristics.monologue_tendency → performance pacing

Injection points:
  - After scene_anchor_system.enhance_prompt() for nano_prompt
  - Before FAL API call for ltx_motion_prompt

Created: 2026-02-12
Updated: 2026-02-14 — V17.3 Director Vision + Performance Notes + Subtext layers
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("atlas.cinematic_enricher")


# ============================================================
# FILM STOCK & SENSOR PROFILES
# ============================================================

# V25 CURE 5: FILM_PROFILES upgraded — camera brand names REMOVED.
# Research proof: "50mm, f/2.8, warm halation, Kodak 2383 print look" outperforms
# "shot on ARRI Alexa with Cooke S4 lenses" on BOTH Kling 3.0 and LTX-2.3.
# Brand tokens are prompt noise — LTX pattern-matches focal length + aperture + film stock.
# DOCTRINE LAW 235: NO camera brand names in ANY prompt path.
FILM_PROFILES = {
    "default": {
        "sensor": "cinematic Super 35mm sensor, natural color science, high dynamic range",
        "stock": "Kodak 5219 print look, naturalistic earth tones, soft grain texture",
        "grade": "professional color grade, subtle film grain, gentle contrast",
        "lut": "filmic highlight rolloff, no digital clipping",
    },
    "period": {
        "sensor": "large format sensor, warm color science, period texture",
        "stock": "warm Kodak Vision3 look, amber candlelight warmth, period grain texture",
        "grade": "period-accurate warm grade, golden hour bias",
        "lut": "rich shadows, lifted blacks, amber midtones",
    },
    "horror": {
        "sensor": "high-resolution sensor, clinical precision, cold color science",
        "stock": "desaturated cold stock look, muted palette, heavy grain",
        "grade": "cold desaturated grade, teal shadows",
        "lut": "crushed blacks, sickly green highlights, grain",
    },
    "noir": {
        "sensor": "Super 35mm sensor, vintage lens character, soft halation on highlights",
        "stock": "monochrome silver halide look, deep black and white contrast",
        "grade": "high contrast noir grade, deep shadows",
        "lut": "harsh falloff, venetian blind light patterns",
    },
    "fantasy": {
        "sensor": "large format sensor, ethereal softness, golden halation on highlights",
        "stock": "clean saturated stock look, jewel tones, luminous highlights",
        "grade": "vibrant saturated grade, jewel-tone palette",
        "lut": "rich color depth, luminous highlights, clean shadows",
    },
    "scifi": {
        "sensor": "high-resolution digital sensor, clinical sharpness, cool color science",
        "stock": "digital LogC look with subtle grain overlay, blue-steel precision",
        "grade": "cool clinical grade, neon accent colors",
        "lut": "sharp detail, blue-white highlights, tech aesthetic",
    },
}

# Genre → film profile mapping
GENRE_TO_PROFILE = {
    "drama": "default",
    "thriller": "default",
    "action": "default",
    "horror": "horror",
    "gothic_horror": "horror",
    "dark_fantasy": "horror",
    "psychological": "horror",
    "supernatural": "horror",
    "noir": "noir",
    "crime": "noir",
    "crime_drama": "noir",
    "detective": "noir",
    "nordic_noir": "noir",
    "period": "period",
    "historical": "period",
    "historical_drama": "period",
    "period_drama": "period",
    "romance": "period",
    "fantasy": "fantasy",
    "epic": "fantasy",
    "adventure": "fantasy",
    "sci-fi": "scifi",
    "sci_fi": "scifi",
    "science_fiction": "scifi",
    "scifi_thriller": "scifi",
    "cyberpunk": "scifi",
    "afrofuturism": "scifi",
    "comedy": "default",
    "romantic_comedy": "default",
    "sitcom": "default",
    "political": "default",
    "legal_drama": "default",
    "biopic": "default",
    "art_house": "default",
    "experimental": "default",
    "martial_arts": "default",
    "spy": "noir",
}


# ============================================================
# HUMANIZATION LAYER
# ============================================================

# V25 LAW 239: Physical verbs, NOT generic descriptors.
# "subtle breathing chest rise" produces frozen video. Physical actions produce motion.
HUMANIZATION_BASE = (
    "weight shifts between feet, "
    "fingers adjust grip on nearest object, "
    "jaw tightens then releases, "
    "shoulders settle with slow exhale"
)

# Emotional context → specific humanization cues
HUMANIZATION_BY_EMOTION = {
    "tension": "held breath, micro-tension in jaw, alert stillness, narrowed gaze",
    "dread": "held breath, micro-tension in jaw, alert stillness, shallow rapid breathing",
    "fear": "widened eyes, arrested breath, involuntary micro-flinch, tremor in hands",
    "grief": "weighted shoulders, slow deliberate blinks, internal stillness, downward gaze",
    "sadness": "weighted shoulders, slow deliberate blinks, internal stillness, heavy exhale",
    "loss": "weighted shoulders, slow deliberate blinks, hollow gaze, stillness",
    "hope": "subtle brightening in eyes, lifted gaze, gentle exhale, open posture",
    "revelation": "subtle brightening, widened eyes, intake of breath, stillness before motion",
    "joy": "natural smile reaching eyes, relaxed shoulders, free breathing, animated gestures",
    "anger": "clenched jaw, controlled breathing, intense locked gaze, tensed forearms",
    "rage": "flared nostrils, rapid shallow breathing, trembling hands, locked predator gaze",
    "love": "soft gaze, gentle breathing, relaxed face, unconscious lean toward subject",
    "horror": "frozen stillness, widened eyes, arrested breath, involuntary recoil",
    "shock": "frozen stillness, widened eyes, arrested breath, slack jaw",
    "contemplation": "distant gaze, slow measured breathing, subtle head tilt, stillness",
    "determination": "set jaw, steady breathing, focused gaze, squared shoulders",
    "neutral": "natural breathing, lifelike micro-movements, ambient body language",
}


# ============================================================
# SMART CONTINUITY DIRECTIVES
# ============================================================

CONTINUITY_RULES = {
    "face_lock": "SAME FACE throughout, no morphing between frames, identity-locked",
    "wardrobe_lock": "consistent wardrobe unchanged from scene start",
    "lighting_lock": "consistent lighting direction and color temperature",
    "spatial_lock": "maintain spatial relationships between characters",
    "temporal_lock": "temporal coherence with previous shot in sequence",
}

# Text poison terms to strip from prompts before enrichment
TEXT_POISON_PATTERNS = [
    r"IDENTITY[\s_]*LOCKED",
    r"DO NOT CHANGE",
    r"MUST MATCH",
    r"EXACTLY SAME",
    r"COPY EXACTLY",
    r"REFERENCE LOCKED",
    r"SAME AS BEFORE",
]


# ============================================================
# TIMED MOTION CUES (for LTX video)
# ============================================================

def generate_timed_motion(duration: float, shot_type: str = "medium",
                          characters: List = None, emotion: str = "neutral",
                          dialogue_text: str = "") -> str:
    """
    Generate timed motion cues for LTX video prompts.
    Creates specific timing markers: "at 0s...", "at 2s...", etc.
    V21.6: No-character shots get environmental camera motion instead of "subject face" cues.
    V25 CURE 1: Dialogue-aware — dialogue shots get performance-driven motion from frame 1.
    """
    cues = []
    chars = characters or []
    has_dialogue = bool(dialogue_text and dialogue_text.strip())

    # V21.6: No-character shots get ENVIRONMENTAL timed motion — no "subject" references
    if not chars:
        return _generate_environmental_timed_motion(duration, shot_type, emotion)

    # Character name extraction
    if isinstance(chars[0], str):
        char_name = chars[0]
    elif isinstance(chars[0], dict):
        char_name = chars[0].get("name", "subject")
    else:
        char_name = "subject"

    # V25: Determine dialogue energy from emotion + word count
    dialogue_energy = "neutral"
    if has_dialogue:
        word_count = len(dialogue_text.split())
        if emotion in ("tension", "anger", "rage"):
            dialogue_energy = "intense"
        elif emotion in ("grief", "sadness", "loss"):
            dialogue_energy = "grief"
        elif emotion in ("revelation", "hope", "surprise"):
            dialogue_energy = "revelation"
        elif emotion in ("fear", "dread"):
            dialogue_energy = "quiet"
        elif word_count > 20:
            dialogue_energy = "intense"

    if duration <= 8:
        # Short shot: 2 timing cues
        cues.append(f"at 0s: {_motion_opener(shot_type, char_name, emotion, has_dialogue, dialogue_energy)}")
        mid = int(duration * 0.6)
        cues.append(f"at {mid}s: {_motion_development(shot_type, char_name, emotion)}")
    elif duration <= 20:
        # Standard shot: 3-4 timing cues
        cues.append(f"at 0s: {_motion_opener(shot_type, char_name, emotion, has_dialogue, dialogue_energy)}")
        cues.append(f"at {int(duration * 0.3)}s: {_motion_development(shot_type, char_name, emotion)}")
        cues.append(f"at {int(duration * 0.7)}s: {_motion_climax(shot_type, char_name, emotion)}")
    else:
        # Extended shot: 4+ timing cues
        cues.append(f"at 0s: {_motion_opener(shot_type, char_name, emotion, has_dialogue, dialogue_energy)}")
        cues.append(f"at {int(duration * 0.2)}s: {_motion_development(shot_type, char_name, emotion)}")
        cues.append(f"at {int(duration * 0.5)}s: {_motion_climax(shot_type, char_name, emotion)}")
        cues.append(f"at {int(duration * 0.8)}s: {_motion_resolution(shot_type, char_name, emotion)}")

    return ", ".join(cues)


def _generate_environmental_timed_motion(duration: float, shot_type: str, emotion: str) -> str:
    """V21.6: Timed motion for landscape/B-roll/establishing shots — pure camera + environment."""
    cues = []

    # Environmental openers by shot type
    env_openers = {
        "wide": "camera slowly reveals the full landscape, natural light shifts",
        "establishing": "wide establishing view, camera drifts revealing depth and scale",
        "medium": "environmental detail visible, ambient movement in foliage or atmosphere",
        "close-up": "tight on environmental detail, texture and surface visible",
        "extreme_close_up": "extreme detail on surface texture, macro-level clarity",
        "tracking": "camera glides through environment, parallax reveals depth",
        "dolly": "slow dolly reveals environment layers, foreground to background",
        "aerial": "overhead perspective drifts, landscape unfolds below",
    }

    # Environmental development by emotion
    env_dev = {
        "tension": "shadows lengthen, light source narrows, atmosphere tightens",
        "dread": "darkness encroaches from edges, light dims, environment contracts",
        "fear": "environment grows restless, light flickers, shadows shift",
        "grief": "light fades to grey, stillness deepens, weight settles",
        "hope": "golden light strengthens, warmth enters the frame, atmosphere lifts",
        "horror": "sickly light crawls across surfaces, shadows move independently",
        "neutral": "natural ambient shifts, clouds drift, gentle environmental motion",
    }

    opener = env_openers.get(shot_type, "environment visible, natural atmospheric movement")
    development = env_dev.get(emotion, env_dev["neutral"])

    if duration <= 8:
        cues.append(f"at 0s: {opener}")
        cues.append(f"at {int(duration * 0.6)}s: {development}")
    elif duration <= 20:
        cues.append(f"at 0s: {opener}")
        cues.append(f"at {int(duration * 0.3)}s: {development}")
        cues.append(f"at {int(duration * 0.7)}s: light and atmosphere settle into final mood")
    else:
        cues.append(f"at 0s: {opener}")
        cues.append(f"at {int(duration * 0.2)}s: {development}")
        cues.append(f"at {int(duration * 0.5)}s: environment reaches atmospheric peak")
        cues.append(f"at {int(duration * 0.8)}s: light and atmosphere resolve toward stillness")

    return ", ".join(cues)


def _motion_opener(shot_type: str, char: str, emotion: str,
                    has_dialogue: bool = False, dialogue_energy: str = "neutral") -> str:
    """
    V25 CURE 1: Dialogue-aware motion opener.
    DOCTRINE LAW 231: If has_dialogue=True, character performs speech from frame 1.
    NEVER "enters frame" or "natural movement begins" on dialogue shots — those freeze the first second.
    """
    # DIALOGUE SHOTS: Character is already speaking, no settle, no enter-frame
    if has_dialogue:
        energy_map = {
            "intense":     f"{char} speaks with conviction, jaw set, direct eye contact",
            "grief":       f"{char} voice catches, eyes glisten, breath unsteady",
            "revelation":  f"{char} leans forward, urgency in every word",
            "anger":       f"{char} voice controlled but hard, tension in shoulders",
            "quiet":       f"{char} speaks low, camera holds tight on truth in the face",
            "neutral":     f"{char} speaks naturally, genuine presence from first frame",
        }
        return energy_map.get(dialogue_energy, energy_map["neutral"])

    # NON-DIALOGUE SHOTS: V25.1 — emotion-driven physical openers, NEVER generic filler
    # Import CPC for physical direction if available
    try:
        from tools.creative_prompt_compiler import get_physical_direction
        _phys = get_physical_direction(emotion, "default", char, "")
    except ImportError:
        _phys = None

    # Emotion-aware openers by shot type — each tells a PHYSICAL story
    if emotion in ("grief", "sadness", "loss"):
        openers = {
            "wide": f"camera finds {char} small in the space, shoulders curved under weight",
            "establishing": f"wide view, {char} isolated in the frame, stillness speaks",
            "medium": f"{char} body heavy, hands still, gaze lowered",
            "close_up": f"tight on {char}, grief pooling in the eyes, jaw clenched",
            "extreme_close_up": f"extreme detail, {char} eyes bright with unshed tears",
            "over_the_shoulder": f"OTS past {char}, world blurred beyond the grief",
            "tracking": f"camera follows {char} slow deliberate movement",
            "dolly": f"slow push toward {char}, weight of loss visible in posture",
        }
    elif emotion in ("tension", "dread", "fear"):
        openers = {
            "wide": f"camera holds wide, {char} rigid in the space, scanning",
            "establishing": f"wide establishing, oppressive atmosphere, {char} braced",
            "medium": f"{char} body coiled, hands gripping, breathing shallow",
            "close_up": f"tight on {char}, pupils dilated, jaw locked",
            "extreme_close_up": f"extreme detail, sweat on {char} brow, pulse visible in neck",
            "over_the_shoulder": f"OTS framing, {char} watching something approach",
            "tracking": f"camera stalks {char}, matching cautious pace",
            "dolly": f"slow creep toward {char}, dread building in the frame",
        }
    elif emotion in ("anger", "rage", "confrontation"):
        openers = {
            "wide": f"camera holds ground as {char} dominates the space, posture squared",
            "establishing": f"wide view, {char} stance aggressive, energy radiating",
            "medium": f"{char} fists clenched, shoulders squared, chin up",
            "close_up": f"tight on {char}, controlled fury in the eyes, veins visible",
            "extreme_close_up": f"extreme detail, {char} teeth set, nostrils flared",
            "over_the_shoulder": f"OTS past {char}, confronting what's ahead",
            "tracking": f"camera moves with {char} aggressive stride",
            "dolly": f"push toward {char}, intensity building with proximity",
        }
    elif emotion in ("revelation", "shock", "discovery"):
        openers = {
            "wide": f"camera catches {char} frozen mid-step, realization hitting",
            "establishing": f"wide view, {char} stops dead, world reshaping",
            "medium": f"{char} body goes still, hands pause, eyes widen",
            "close_up": f"tight on {char}, moment of recognition dawning across the face",
            "extreme_close_up": f"extreme detail, {char} pupils shift, understanding arrives",
            "over_the_shoulder": f"OTS past {char}, staring at what changes everything",
            "tracking": f"camera catches {char} mid-movement as realization freezes them",
            "dolly": f"push in on {char} as truth lands, face transforming",
        }
    else:
        # Neutral/default — still PHYSICAL, never generic
        openers = {
            "wide": f"camera establishes scene, {char} grounded in the space",
            "establishing": f"wide establishing view, depth and scale revealed",
            "medium": f"{char} centered in frame, body relaxed but alert",
            "close_up": f"tight on {char}, face telling the story before words",
            "extreme_close_up": f"extreme detail on {char}, every thought readable",
            "over_the_shoulder": f"OTS framing locked, {char} focused ahead",
            "tracking": f"camera tracks with {char}, matching natural rhythm",
            "dolly": f"slow push toward {char}, drawing audience into the moment",
        }

    result = openers.get(shot_type, openers.get("medium", f"{char} body grounded, present in the space"))
    # If CPC gave us a better physical direction, blend it
    if _phys and _phys not in result and char in result:
        result = result.split(",")[0] + f", {_phys}"
    return result


def _motion_development(shot_type: str, char: str, emotion: str) -> str:
    if emotion in ("tension", "dread", "fear"):
        return f"{char} tension builds, breathing becomes shallow, environment feels closing in"
    elif emotion in ("grief", "sadness", "loss"):
        return f"{char} weight settles deeper, gaze drops, movement slows"
    elif emotion in ("anger", "rage"):
        return f"{char} energy intensifies, posture squares, movement becomes deliberate"
    elif emotion in ("joy", "hope", "revelation"):
        return f"{char} expression opens, posture lifts, energy brightens"
    return f"{char} body shifts with intention, weight transfers, hands find purpose"


def _motion_climax(shot_type: str, char: str, emotion: str) -> str:
    if emotion in ("tension", "dread", "fear", "horror"):
        return f"peak tension moment, {char} stillness or sudden movement, camera responds"
    elif emotion in ("grief", "loss"):
        return f"emotional peak, {char} breaks composure, vulnerable moment"
    elif emotion in ("revelation", "shock"):
        return f"revelation hits, {char} reacts with full body, camera holds"
    return f"{char} reaches the turning point, body commits to the decision"


def _motion_resolution(shot_type: str, char: str, emotion: str) -> str:
    return f"{char} body finds its new position, weight settles, the beat is complete"


# ============================================================
# MAIN ENRICHER CLASS
# ============================================================

class CinematicEnricher:
    """
    Enriches V17 prompts with cinematic quality layers.

    Usage:
        enricher = CinematicEnricher(genre="dark_fantasy")
        enriched_nano = enricher.enrich_nano_prompt(nano_prompt, shot)
        enriched_ltx = enricher.enrich_ltx_prompt(ltx_prompt, shot)
    """

    def __init__(self, genre: str = "drama", director_profile: Dict = None,
                 story_bible: Dict = None, writer_profile: Dict = None):
        self.genre = (genre or "drama").lower().replace(" ", "_").replace("-", "_")
        self.director_profile = director_profile or {}
        self.story_bible = story_bible or {}
        self.writer_profile = writer_profile or {}

        # Select film profile (make a copy so we don't mutate the global)
        profile_key = GENRE_TO_PROFILE.get(self.genre, "default")
        self.film_profile = dict(FILM_PROFILES.get(profile_key, FILM_PROFILES["default"]))

        # --- Extract director visual_signature (the ACTUAL schema) ---
        vis_sig = self.director_profile.get("visual_signature", {})

        # Camera philosophy: e.g. "The camera is a character. It breathes, hesitates, reveals."
        self.camera_philosophy = vis_sig.get("camera_philosophy", "")

        # Composition style: e.g. "Negative space dominates, subjects isolated in architecture"
        self.composition_style = vis_sig.get("composition_style", "")

        # Movement vocabulary: dict of mood -> motion description
        self.movement_vocabulary = vis_sig.get("movement_vocabulary", {})

        # Lighting signature: can be dict with philosophy/palette/ratio/instruments or string
        self.lighting_signature = vis_sig.get("lighting_signature", {})
        if isinstance(self.lighting_signature, str):
            self.lighting_signature = {"philosophy": self.lighting_signature}

        # Lens preferences: dict of shot_type -> lens description
        self.lens_preferences = vis_sig.get("lens_preferences", {})

        # Color grade override from director (structured dict with primary, shadow_tone, etc.)
        director_grade = vis_sig.get("color_grade", {})
        if isinstance(director_grade, dict) and director_grade:
            grade_parts = []
            if director_grade.get("primary"):
                grade_parts.append(director_grade["primary"])
            if director_grade.get("shadow_tone"):
                grade_parts.append(f"shadows: {director_grade['shadow_tone']}")
            if director_grade.get("skin_treatment"):
                grade_parts.append(f"skin: {director_grade['skin_treatment']}")
            if grade_parts:
                self.film_profile["grade"] = ", ".join(grade_parts)
        elif isinstance(director_grade, str) and director_grade:
            self.film_profile["grade"] = director_grade

        # Shot braintree overrides: per shot type duration/motion/lighting overrides
        self.shot_braintree = self.director_profile.get("shot_braintree_overrides", {})

        # Sample direction quotes for tone injection
        self.sample_direction = self.director_profile.get("sample_direction", [])

        # Creative philosophy signature technique
        creative_phil = self.director_profile.get("creative_philosophy", {})
        self.signature_technique = creative_phil.get("signature_technique", "")

        # Default camera motion from director profile
        self.director_default_motion = self.director_profile.get("default_camera_motion", "")

        # --- Legacy flat-key overrides (backward compat) ---
        if self.director_profile.get("film_stock"):
            self.film_profile["stock"] = self.director_profile["film_stock"]
        if self.director_profile.get("sensor"):
            self.film_profile["sensor"] = self.director_profile["sensor"]
        if self.director_profile.get("color_grade") and isinstance(self.director_profile["color_grade"], str):
            self.film_profile["grade"] = self.director_profile["color_grade"]

        # --- Extract writer voice characteristics ---
        voice_chars = self.writer_profile.get("voice_characteristics", {})
        dialogue_style = voice_chars.get("dialogue_style", {})
        self.subtext_density = dialogue_style.get("subtext_density", 0.0)
        self.silence_usage = voice_chars.get("silence_usage", "")
        self.monologue_tendency = voice_chars.get("monologue_tendency", "")

        logger.info(f"[ENRICHER] Initialized with genre={self.genre}, "
                    f"profile={profile_key}, film_stock={self.film_profile['stock'][:30]}..., "
                    f"director={'YES' if self.camera_philosophy else 'none'}, "
                    f"writer={'YES (subtext={self.subtext_density})' if self.writer_profile else 'none'}")

    def _strip_text_poison(self, prompt: str) -> str:
        """Remove instruction-like text that degrades visual quality."""
        cleaned = prompt
        for pattern in TEXT_POISON_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        # Clean up double spaces/commas
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r",\s*,", ",", cleaned)
        return cleaned.strip()

    def _detect_emotion(self, shot: Dict) -> str:
        """Detect the emotional context of a shot from multiple sources."""
        # Check explicit emotion field
        emotion = shot.get("emotion", shot.get("emotional_tone", ""))
        if emotion:
            return emotion.lower().strip()

        # Check scene emotional context
        tone = shot.get("tone", shot.get("scene_tone", ""))
        if tone:
            return tone.lower().strip()

        # Infer from shot description/dialogue
        description = (shot.get("description", "") + " " +
                       shot.get("nano_prompt", "") + " " +
                       shot.get("dialogue", "")).lower()

        emotion_keywords = {
            "tension": ["tension", "tense", "suspense", "watching", "waiting"],
            "fear": ["fear", "afraid", "terrif", "scream", "flee"],
            "grief": ["grief", "mourn", "death", "loss", "funeral", "crying"],
            "anger": ["anger", "furious", "rage", "yell", "confront"],
            "joy": ["joy", "happy", "laugh", "celebrat", "smile", "delight"],
            "hope": ["hope", "dawn", "light", "promise", "future"],
            "horror": ["horror", "dark", "monster", "blood", "scream"],
            "love": ["love", "tender", "embrace", "kiss", "heart"],
            "shock": ["shock", "reveal", "surprise", "gasp", "twist"],
            "contemplation": ["think", "ponder", "stare", "silence", "alone"],
            "determination": ["determin", "resolve", "decide", "stand", "fight"],
        }

        for emo, keywords in emotion_keywords.items():
            if any(kw in description for kw in keywords):
                return emo

        return "neutral"

    def _detect_shot_type_key(self, shot: Dict) -> str:
        """Normalize shot type to a key usable for braintree/lens lookups."""
        raw = (shot.get("type", "") or shot.get("shot_type", "") or
               shot.get("framing", "") or "medium").lower().strip()
        # Map common shot types to braintree keys
        mapping = {
            "establishing": "establishing",
            "wide": "establishing",
            "medium": "dialogue",
            "close-up": "dialogue",
            "close_up": "dialogue",
            "closeup": "dialogue",
            "extreme_close_up": "intimate",
            "extreme_close": "intimate",
            "over_the_shoulder": "dialogue",
            "ots": "dialogue",
            "two_shot": "dialogue",
            "tracking": "action",
            "action": "action",
            "aerial": "establishing",
            "dolly": "dialogue",
            "insert": "intimate",
        }
        return mapping.get(raw, "dialogue")

    def _build_director_vision_layer(self, shot: Dict, emotion: str) -> str:
        """
        Build a Director Vision enrichment string from the full director profile.
        Injects camera philosophy, motivated movement, lighting signature, lens
        preferences, and composition style into the prompt.
        """
        if not self.camera_philosophy and not self.lighting_signature:
            return ""

        parts = []
        shot_type_key = self._detect_shot_type_key(shot)

        # 1. Camera philosophy as a guiding note
        if self.camera_philosophy:
            parts.append(f"Director vision: {self.camera_philosophy}")

        # 2. Composition style
        if self.composition_style:
            parts.append(f"composition: {self.composition_style}")

        # 3. Motivated movement from movement_vocabulary based on emotion
        if self.movement_vocabulary:
            # Try emotion-specific movement first, then 'default'
            motion_desc = self.movement_vocabulary.get(emotion, "")
            if not motion_desc:
                # Try broader emotion categories
                emotion_to_mood = {
                    "tension": "tension", "dread": "tension", "fear": "horror",
                    "horror": "horror", "grief": "emotion", "sadness": "emotion",
                    "loss": "emotion", "anger": "tension", "rage": "tension",
                    "hope": "emotion", "joy": "emotion", "revelation": "revelation",
                    "shock": "revelation", "love": "emotion", "contemplation": "default",
                    "determination": "tension", "neutral": "default",
                }
                mapped_mood = emotion_to_mood.get(emotion, "default")
                motion_desc = self.movement_vocabulary.get(mapped_mood,
                              self.movement_vocabulary.get("default", ""))
            if motion_desc:
                parts.append(f"camera movement: {motion_desc}")

        # 4. Lighting signature
        if self.lighting_signature:
            light_phil = self.lighting_signature.get("philosophy", "")
            light_palette = self.lighting_signature.get("palette", "")
            light_ratio = self.lighting_signature.get("ratio", "")
            light_parts = [p for p in [light_phil, light_palette, light_ratio] if p]
            if light_parts:
                parts.append(f"lighting: {', '.join(light_parts)}")

        # 5. Lens preferences per shot type
        if self.lens_preferences:
            lens = self.lens_preferences.get(shot_type_key, "")
            if not lens:
                # Try the raw shot type as key
                raw_type = (shot.get("type", "") or shot.get("shot_type", "")).lower()
                lens = self.lens_preferences.get(raw_type, "")
            if lens:
                parts.append(f"lens: {lens}")

        # 6. Shot braintree override (specific director instructions per shot type)
        if self.shot_braintree:
            braintree = self.shot_braintree.get(shot_type_key, {})
            if not braintree:
                # Also check emotion-based keys like "horror_beat"
                emotion_keys = {
                    "horror": "horror_beat", "dread": "horror_beat",
                    "fear": "horror_beat", "revelation": "revelation",
                    "shock": "revelation",
                }
                alt_key = emotion_keys.get(emotion, "")
                if alt_key:
                    braintree = self.shot_braintree.get(alt_key, {})
            if isinstance(braintree, dict):
                bt_desc = braintree.get("default", "")
                bt_motion = braintree.get("motion", "")
                bt_lighting = braintree.get("lighting", "")
                bt_shadow = braintree.get("shadow_treatment", "")
                bt_parts = [p for p in [bt_desc, bt_motion, bt_lighting, bt_shadow] if p]
                if bt_parts:
                    parts.append(f"director note: {', '.join(bt_parts)}")

        if not parts:
            return ""

        return ". ".join(parts)

    def _build_performance_notes_layer(self, shot: Dict, emotion: str) -> str:
        """
        Build performance direction notes from:
        - Shot's emotional tone
        - Writer's silence_usage and monologue_tendency
        - Character-specific acting direction (via actor ltx_motion_default)
        """
        parts = []

        # Emotion-driven performance cue
        emotion_perf = {
            "tension": "held stillness, coiled energy beneath restraint, breath control",
            "dread": "involuntary micro-movements betray composure, eyes scanning",
            "fear": "fight-or-flight visible in body, controlled panic",
            "grief": "weight of loss in every gesture, gravity in movement",
            "sadness": "internal collapse visible in posture, slow deliberate motion",
            "anger": "controlled fury channeled through physicality, precision in rage",
            "rage": "explosive energy barely contained, trembling restraint",
            "hope": "gradual opening of posture, light returning to eyes",
            "joy": "unguarded natural expression, relaxed authentic movement",
            "revelation": "moment of understanding crosses the face, stillness then reaction",
            "shock": "body processes before mind, involuntary physical response",
            "horror": "primal response visible, civilized mask slipping",
            "love": "unconscious gravitational pull, softening of all edges",
            "contemplation": "internal world visible through external stillness",
            "determination": "resolution settles into the body, weight becomes purpose",
        }
        if emotion in emotion_perf:
            parts.append(f"performance: {emotion_perf[emotion]}")

        # Writer's silence_usage influences pacing direction
        if self.silence_usage:
            silence_map = {
                "frequent_and_meaningful": "hold pauses, silence carries weight between lines",
                "power_move": "silence as dominance, let the void speak",
                "tension_before_action": "breath-held silence before release",
                "before_the_verdict": "charged silence, anticipation in stillness",
                "comedic_beat": "timing pause, let the moment land",
                "nordic_standard": "contained silence, emotion internalized",
                "the_work_itself": "silence is the performance, stillness is the art",
                "before_the_kiss": "anticipatory silence, space between touches",
                "space_is_vast": "cosmic silence, smallness of being",
                "loyalty_test": "silence as test, watching for the tell",
            }
            silence_dir = silence_map.get(self.silence_usage, "")
            if silence_dir:
                parts.append(f"pacing: {silence_dir}")

        if not parts:
            return ""

        return ". ".join(parts)

    def _build_environmental_pacing(self, shot: Dict, emotion: str) -> str:
        """
        V21.6: Environmental atmosphere direction for no-character shots.
        Replaces performance notes/subtext (which are human-body-language) with
        environmental mood cues that give FAL atmosphere direction WITHOUT
        generating people.
        """
        env_cues = {
            "tension": "atmospheric pressure builds, shadows deepen, wind stills before the storm",
            "dread": "environment feels oppressive, darkness encroaches on light, air thickens",
            "fear": "environment contracts, light sources flicker, shadows grow restless",
            "grief": "muted landscape, overcast weight pressing down, stillness of aftermath",
            "sadness": "grey light, rain-washed surfaces, heavy atmosphere, muted palette",
            "anger": "sky bruises dark, wind whips vegetation, turbulent energy in elements",
            "rage": "storm light, violent wind, dramatic cloud movement, elemental fury",
            "hope": "light breaks through clouds, golden hour warmth emerging, atmosphere lifts",
            "joy": "bright natural light, gentle breeze through environment, warmth in the air",
            "revelation": "light shifts dramatically, environment transforms, atmosphere pivots",
            "shock": "sudden light change, environment freezes in stillness, charged air",
            "horror": "deep shadows swallow edges, sickly light, environment feels alive and hostile",
            "love": "soft golden light, gentle atmosphere, warmth permeating the environment",
            "contemplation": "still air, diffused light, meditative calm in the landscape",
            "determination": "strengthening light, clearing atmosphere, landscape sharpens in focus",
            "neutral": "natural ambient atmosphere, gentle environmental movement, steady light",
        }
        cue = env_cues.get(emotion, env_cues["neutral"])
        return f"environment mood: {cue}"

    def _build_subtext_layer(self, shot: Dict, emotion: str) -> str:
        """
        When writer subtext_density is high (>= 0.7), inject subtext acting direction:
        - Body language contradicting dialogue
        - Micro-expressions revealing internal state
        - Layered performance cues
        """
        if self.subtext_density < 0.7:
            return ""

        # Scale subtext intensity by density
        parts = []

        if self.subtext_density >= 0.9:
            # Very high subtext: explicit contradiction direction
            subtext_cues = {
                "tension": "says calm words but body betrays coiled readiness, eyes contradict smile",
                "dread": "projects composure but hands give away terror, forced steadiness in voice",
                "fear": "maintains brave facade, micro-tremors visible in close-up",
                "grief": "speaks of moving on while body language clings to the past",
                "anger": "pleasant words delivered with jaw tension, controlled venom",
                "love": "casual demeanor hiding desperate need, involuntary lean toward subject",
                "hope": "guarded optimism, protecting self from disappointment visible in posture",
                "revelation": "mind racing behind still exterior, processing visible only in eyes",
                "contemplation": "simple words masking philosophical depth, weight beneath simplicity",
                "determination": "soft speech masking iron will, gentleness as strength",
            }
            cue = subtext_cues.get(emotion, "internal conflict visible in micro-expressions, body tells a different story than words")
            parts.append(f"subtext: {cue}")
        elif self.subtext_density >= 0.7:
            # Moderate-high subtext: suggest internal complexity
            parts.append("subtext visible in performance: what is unsaid matters more than dialogue, "
                         "internal world bleeds through controlled exterior")

        return ". ".join(parts) if parts else ""

    def enrich_nano_prompt(self, nano_prompt: str, shot: Dict) -> str:
        """
        Enrich a nano_prompt (first frame) with cinematic quality layers.

        Adds:
        1. Film stock & sensor vocabulary
        2. Humanization markers
        3. Smart continuity directives
        4. Quality anchors

        Input:  "Medium shot of FELAN in the valley at dawn"
        Output: "Medium shot of FELAN in the valley at dawn. cinematic Super 35mm sensor,
                 natural color science, Kodak 5219 print look, professional color grade,
                 subtle film grain. natural human micro-movements, subtle breathing chest rise.
                 face stable, identity-locked, consistent wardrobe unchanged from scene start.
                 filmic highlight rolloff, no digital clipping"
        """
        if not nano_prompt:
            return nano_prompt

        # Step 1: Clean text poison
        prompt = self._strip_text_poison(nano_prompt)

        # Step 2: Detect emotional context
        emotion = self._detect_emotion(shot)

        # Step 3: Build enrichment layers
        layers = []

        # Layer 1: Film Stock & Sensor (only if not already present)
        # V25: Guard checks for "sensor" or "color science" — no more brand name checks
        if "sensor" not in prompt.lower() and "color science" not in prompt.lower():
            film_desc = f"{self.film_profile['sensor']}, {self.film_profile['stock']}"
            layers.append(film_desc)

        # Layer 2: Color Grade
        if "grade" not in prompt.lower() and "color" not in prompt.lower():
            layers.append(self.film_profile["grade"])

        # Layer 3: Humanization (for shots with characters)
        # V26.1: Dedup + cap — humanization was repeating micro-expressions 2-3x across
        # base + emotion layers, bloating prompts to 2000+ chars and drowning dialogue direction.
        # Now: pick emotion-specific ONLY (more targeted), skip base if emotion covers it.
        # Cap total humanization to 30 words to leave room for dialogue/action direction.
        characters = shot.get("characters", [])
        if characters:
            emo_human = HUMANIZATION_BY_EMOTION.get(emotion, HUMANIZATION_BY_EMOTION["neutral"])
            # V26.1: Use emotion-specific humanization INSTEAD of base when available
            # Base has generic "jaw tightens, shoulders settle" — emotion-specific is always better
            if emo_human:
                # Cap to 30 words to prevent prompt bloat
                _human_words = emo_human.split()
                if len(_human_words) > 30:
                    emo_human = " ".join(_human_words[:30])
                layers.append(emo_human)
            else:
                # Fallback to base only if no emotion mapping exists
                layers.append(HUMANIZATION_BASE)

        # Layer 4: Smart Continuity — only face_lock if characters present
        # V21.6: "SAME FACE" in a landscape prompt causes FAL to generate faces
        if characters:
            layers.append(CONTINUITY_RULES["face_lock"])
        else:
            layers.append(CONTINUITY_RULES["lighting_lock"])  # Landscapes: lock lighting, not faces

        # Layer 5: Filmic quality anchor
        layers.append(self.film_profile["lut"])

        # Assemble base enrichment
        enriched = prompt + ". " + ", ".join(layers)

        # Layer 6: Director Vision (from full director profile)
        director_vision = self._build_director_vision_layer(shot, emotion)
        if director_vision:
            enriched = enriched + ". " + director_vision

        # Layer 7: Performance Notes (from emotion + writer voice)
        # V21.6: ONLY inject human performance into shots WITH characters
        # Landscape/B-roll/establishing shots get environmental pacing instead
        if characters:
            perf_notes = self._build_performance_notes_layer(shot, emotion)
            if perf_notes:
                enriched = enriched + ". " + perf_notes
        else:
            # Environmental pacing for no-character shots
            env_pacing = self._build_environmental_pacing(shot, emotion)
            if env_pacing:
                enriched = enriched + ". " + env_pacing

        # Layer 8: Subtext Layer (from writer subtext_density)
        # V21.6: Subtext is about human body language — skip for no-character shots
        if characters:
            subtext = self._build_subtext_layer(shot, emotion)
            if subtext:
                enriched = enriched + ". " + subtext

        # Log enrichment stats
        orig_len = len(nano_prompt)
        new_len = len(enriched)
        logger.info(f"[ENRICHER] nano_prompt enriched: {orig_len} → {new_len} chars "
                    f"(+{new_len - orig_len}), emotion={emotion}, "
                    f"director={'yes' if director_vision else 'no'}, "
                    f"chars={'yes' if characters else 'NO-landscape'}")

        return enriched

    def enrich_ltx_prompt(self, ltx_prompt: str, shot: Dict) -> str:
        """
        Enrich an LTX motion prompt with timed motion cues and humanization.

        Adds:
        1. Timed motion cues ("at 0s...", "at 2s...")
        2. Humanization movement markers
        3. Camera motion physics
        """
        if not ltx_prompt:
            return ltx_prompt

        prompt = self._strip_text_poison(ltx_prompt)
        emotion = self._detect_emotion(shot)
        duration = shot.get("duration", shot.get("duration_seconds", 8))
        shot_type = shot.get("type", shot.get("shot_type", "medium"))
        characters = shot.get("characters", [])

        layers = []

        # Layer 1: Timed motion cues (only if not already present)
        if "at 0s" not in prompt and "at 2s" not in prompt:
            timed = generate_timed_motion(
                duration=duration,
                shot_type=shot_type,
                characters=characters,
                emotion=emotion
            )
            if timed:
                layers.append(timed)

        # Layer 2: Humanization for video
        if characters:
            emo_human = HUMANIZATION_BY_EMOTION.get(emotion, HUMANIZATION_BY_EMOTION["neutral"])
            if emo_human and emo_human not in prompt:
                layers.append(emo_human)

        # Layer 3: Camera physics
        camera = shot.get("camera", shot.get("camera_motion", ""))
        if camera and camera != "static":
            physics = _camera_physics(camera, duration)
            if physics and physics not in prompt:
                layers.append(physics)

        # Assemble base enrichment
        if not layers:
            enriched = prompt
        else:
            enriched = prompt + ". " + ", ".join(layers)

        # Layer 4: Director Vision — motion vocabulary override for LTX
        if self.movement_vocabulary or self.shot_braintree:
            shot_type_key = self._detect_shot_type_key(shot)
            director_motion_parts = []

            # Movement vocabulary for this emotion/mood
            if self.movement_vocabulary:
                emotion_to_mood = {
                    "tension": "tension", "dread": "tension", "fear": "horror",
                    "horror": "horror", "grief": "emotion", "sadness": "emotion",
                    "loss": "emotion", "anger": "tension", "rage": "tension",
                    "hope": "emotion", "joy": "emotion", "revelation": "revelation",
                    "shock": "revelation", "love": "emotion", "contemplation": "default",
                    "determination": "tension", "neutral": "default",
                }
                mapped_mood = emotion_to_mood.get(emotion, "default")
                motion = (self.movement_vocabulary.get(emotion, "") or
                          self.movement_vocabulary.get(mapped_mood, "") or
                          self.movement_vocabulary.get("default", ""))
                # V22.3: Check for FULL prefix to prevent stacking across multiple enricher passes
                if motion and motion not in enriched and "director camera:" not in enriched:
                    director_motion_parts.append(f"director camera: {motion}")

            # Shot braintree motion override
            if self.shot_braintree:
                braintree = self.shot_braintree.get(shot_type_key, {})
                if not braintree:
                    emotion_keys = {
                        "horror": "horror_beat", "dread": "horror_beat",
                        "fear": "horror_beat", "revelation": "revelation",
                        "shock": "revelation",
                    }
                    alt_key = emotion_keys.get(emotion, "")
                    if alt_key:
                        braintree = self.shot_braintree.get(alt_key, {})
                if isinstance(braintree, dict):
                    bt_motion = braintree.get("motion", "")
                    # V22.3: Check for FULL prefix to prevent stacking across multiple enricher passes
                if bt_motion and bt_motion not in enriched and "motivated movement:" not in enriched:
                        director_motion_parts.append(f"motivated movement: {bt_motion}")

            if director_motion_parts:
                enriched = enriched + ". " + ". ".join(director_motion_parts)

        # Layer 5: Performance Notes for motion context
        # V21.6: ONLY inject human performance into shots WITH characters
        if characters:
            perf_notes = self._build_performance_notes_layer(shot, emotion)
            if perf_notes:
                enriched = enriched + ". " + perf_notes
        else:
            env_pacing = self._build_environmental_pacing(shot, emotion)
            if env_pacing:
                enriched = enriched + ". " + env_pacing

        # Layer 6: Subtext for character animation direction
        # V21.6: Subtext is human body language — skip for no-character shots
        if characters:
            subtext = self._build_subtext_layer(shot, emotion)
            if subtext:
                enriched = enriched + ". " + subtext

        logger.info(f"[ENRICHER] ltx_prompt enriched: {len(ltx_prompt)} → {len(enriched)} chars, "
                    f"emotion={emotion}, duration={duration}s")

        return enriched


    def inject_cast_traits(self, prompt: str, shot: Dict,
                           cast_map: Dict = None, actor_library: Dict = None) -> str:
        """
        V21.10: FIXED — Now uses CANONICAL_CHARACTERS registry instead of AI actor library.

        Previous version pulled from ai_actors_library.json which injected WRONG
        nationalities and physical descriptions (Italian, French, auburn, chef, etc.)
        causing massive character drift across all 279 shots.

        Now uses the same canonical registry as the Authority Gate — single source
        of truth for character appearance, matching the actual screenplay characters.
        """
        characters = shot.get("characters", [])
        if not characters:
            return prompt

        try:
            from tools.prompt_authority_gate import CANONICAL_CHARACTERS
        except ImportError:
            logger.warning("[ENRICHER] Could not import CANONICAL_CHARACTERS — skipping trait injection")
            return prompt

        cast_additions = []
        for char in characters:
            char_name = char if isinstance(char, str) else char.get("name", "")
            char_upper = char_name.upper().strip()

            # Find canonical entry
            canon = None
            for canon_name, canon_data in CANONICAL_CHARACTERS.items():
                if char_upper in canon_name.upper() or canon_name.upper() in char_upper:
                    canon = canon_data
                    break

            if not canon:
                continue

            # Only inject if character name not already described in prompt
            if char_name.upper() not in prompt.upper():
                appearance = canon.get("appearance", "")
                if appearance:
                    cast_additions.append(f"{char_name}: {appearance[:200]}")

        if cast_additions:
            prompt = prompt + ". " + ". ".join(cast_additions)
            logger.info(f"[ENRICHER] Injected CANONICAL traits for {len(cast_additions)} character(s)")

        return prompt


def _camera_physics(camera_type: str, duration: float) -> str:
    """Generate realistic camera movement physics."""
    camera_lower = camera_type.lower()
    if "dolly" in camera_lower:
        return f"smooth dolly movement over {duration}s, steady acceleration and deceleration"
    elif "pan" in camera_lower:
        return f"controlled pan at constant angular velocity, {duration}s duration"
    elif "tracking" in camera_lower or "follow" in camera_lower:
        return f"camera tracking subject movement, stabilized follow over {duration}s"
    elif "crane" in camera_lower or "jib" in camera_lower:
        return f"fluid crane movement, vertical parallax over {duration}s"
    elif "zoom" in camera_lower:
        return f"subtle optical zoom, focal length shift over {duration}s"
    elif "drift" in camera_lower or "subtle" in camera_lower:
        return f"barely perceptible camera drift, breathing steadicam feel"
    return ""


# ============================================================
# MODULE-LEVEL CONVENIENCE
# ============================================================

_enricher_instance = None

def get_enricher(genre: str = "drama", director_profile: Dict = None,
                 story_bible: Dict = None, writer_profile: Dict = None,
                 force_new: bool = False) -> CinematicEnricher:
    """Get or create the singleton enricher instance."""
    global _enricher_instance
    if _enricher_instance is None or force_new:
        _enricher_instance = CinematicEnricher(
            genre=genre,
            director_profile=director_profile,
            story_bible=story_bible,
            writer_profile=writer_profile
        )
    return _enricher_instance
