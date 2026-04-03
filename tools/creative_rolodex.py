"""
ATLAS Creative Rolodex — V1.0
The Visual Brain's Reference Library

Maps scene types → shot grammar → camera choices → pacing
Based on real film data and cinematography research.

This module is imported by the shot expansion pipeline to make
MOTIVATED creative decisions instead of generic templates.

Usage:
    from tools.creative_rolodex import get_scene_grammar, get_shot_recipe

    grammar = get_scene_grammar("discovery", genre="mystery_thriller")
    recipe = get_shot_recipe("dialogue_reaction", emotion_level=7)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ═══════════════════════════════════════════════════════════════
# SCENE TYPE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

SCENE_TYPES = {
    "cold_open": "First scene of episode — must hook in 8 seconds",
    "confrontation": "Two characters with opposing agendas",
    "discovery": "Character finds evidence / information",
    "confession": "Character reveals emotional truth",
    "investigation": "Character searches / examines / gathers clues",
    "transition": "Moving between locations or time periods",
    "atmosphere": "Establishing mood without dialogue",
    "climax": "Scene of highest tension / stakes",
    "resolution": "After climax — new equilibrium",
    "introduction": "First appearance of major character",
}

# ═══════════════════════════════════════════════════════════════
# GENRE PACING DATA (from real film studies)
# ═══════════════════════════════════════════════════════════════

@dataclass
class GenrePacing:
    """Pacing profile based on measured Average Shot Length data."""
    genre: str
    avg_shot_length: float  # seconds
    cuts_per_minute: Tuple[int, int]  # range
    dialogue_asl: float  # dialogue-specific ASL
    action_asl: float  # action beat ASL
    held_shot_max: float  # longest acceptable held shot
    description: str = ""

GENRE_PACING = {
    "mystery_thriller": GenrePacing(
        genre="mystery_thriller",
        avg_shot_length=6.0,
        cuts_per_minute=(8, 12),
        dialogue_asl=5.0,
        action_asl=4.0,
        held_shot_max=15.0,
        description="Tense, building, methodical. Rhythm accelerates at reveals."
    ),
    "horror": GenrePacing(
        genre="horror",
        avg_shot_length=12.0,
        cuts_per_minute=(4, 6),
        dialogue_asl=8.0,
        action_asl=3.0,  # kill scenes are fast
        held_shot_max=20.0,
        description="Sustained dread. Long holds build anxiety. Violence is fast."
    ),
    "drama": GenrePacing(
        genre="drama",
        avg_shot_length=8.0,
        cuts_per_minute=(6, 10),
        dialogue_asl=7.0,
        action_asl=5.0,
        held_shot_max=15.0,
        description="Considered, emotional, character-driven pacing."
    ),
    "action": GenrePacing(
        genre="action",
        avg_shot_length=2.5,
        cuts_per_minute=(20, 30),
        dialogue_asl=4.0,
        action_asl=2.0,
        held_shot_max=8.0,
        description="Fast, chaotic, kinetic energy."
    ),
    "period_drama": GenrePacing(
        genre="period_drama",
        avg_shot_length=9.0,
        cuts_per_minute=(5, 8),
        dialogue_asl=8.0,
        action_asl=6.0,
        held_shot_max=18.0,
        description="Elegant, measured. Favors wide compositions and held moments."
    ),
    "noir": GenrePacing(
        genre="noir",
        avg_shot_length=7.0,
        cuts_per_minute=(7, 10),
        dialogue_asl=6.0,
        action_asl=4.0,
        held_shot_max=15.0,
        description="Moody, shadow-heavy, conversation-driven tension."
    ),
}

# ═══════════════════════════════════════════════════════════════
# SHOT RECIPES — Specific camera choices for specific moments
# ═══════════════════════════════════════════════════════════════

@dataclass
class ShotRecipe:
    """A specific, motivated shot selection for a narrative moment."""
    shot_type: str
    focal_length: str  # e.g. "85mm"
    aperture: str  # e.g. "f/2.0"
    movement: str  # e.g. "slow push in"
    duration_range: Tuple[float, float]  # seconds
    motivation: str  # WHY this choice
    ltx_motion_hint: str  # what to put in LTX prompt
    reference: str  # real film reference
    ai_quality_note: str  # how AI handles this shot type

SHOT_RECIPES = {
    # === DIALOGUE SHOTS ===
    "dialogue_speaker": ShotRecipe(
        shot_type="medium_close",
        focal_length="50-85mm",
        aperture="f/2.8",
        movement="static or gentle drift",
        duration_range=(5, 8),
        motivation="Conversational distance — face + gesture readable",
        ltx_motion_hint="character speaks with natural gestures, subtle weight shifts",
        reference="Succession: every boardroom scene — MCU on speaker",
        ai_quality_note="Sweet spot for AI — enough face for identity, enough body for gesture"
    ),
    "dialogue_reaction": ShotRecipe(
        shot_type="close_up",
        focal_length="85mm",
        aperture="f/2.0",
        movement="static, locked",
        duration_range=(3, 5),
        motivation="Reaction reveals more than speech — audience reads the listener",
        ltx_motion_hint="character listens intently, subtle facial shift, eyes processing",
        reference="Succession: reaction shots during Logan's monologues",
        ai_quality_note="HIGH quality — face fills frame, max identity fidelity"
    ),
    "dialogue_two_shot": ShotRecipe(
        shot_type="medium",
        focal_length="35-50mm",
        aperture="f/4.0",
        movement="static or slow lateral drift",
        duration_range=(6, 10),
        motivation="Shows spatial relationship between speakers — power dynamics",
        ltx_motion_hint="two characters face each other, natural conversation movement",
        reference="The Bear: kitchen conversations — both bodies visible",
        ai_quality_note="MEDIUM quality — faces smaller, but body language readable"
    ),
    "dialogue_over_shoulder": ShotRecipe(
        shot_type="over_the_shoulder",
        focal_length="65-85mm",
        aperture="f/2.8",
        movement="static",
        duration_range=(4, 7),
        motivation="Connects speaker to listener — we see WHO they're talking TO",
        ltx_motion_hint="over shoulder framing, foreground character soft, background sharp",
        reference="Standard coverage in every prestige drama",
        ai_quality_note="CHALLENGING for AI — needs clear depth separation"
    ),

    # === DISCOVERY / INVESTIGATION ===
    "discovery_hands": ShotRecipe(
        shot_type="extreme_close_up",
        focal_length="100mm",
        aperture="f/2.0",
        movement="slow push in",
        duration_range=(3, 5),
        motivation="Hands reveal intention — touching, opening, reaching",
        ltx_motion_hint="slow push toward hands interacting with object, deliberate movement",
        reference="Zodiac: hands on documents, slow reveal of evidence",
        ai_quality_note="HIGH quality — detail shots render well in AI"
    ),
    "discovery_face_reaction": ShotRecipe(
        shot_type="close_up",
        focal_length="85mm",
        aperture="f/2.0",
        movement="static, hold",
        duration_range=(3, 5),
        motivation="Face transforms as information lands — the audience reads the discovery through the character",
        ltx_motion_hint="character's expression shifts from curiosity to shock, eyes widening",
        reference="Severance: every time an Innie discovers a truth about their Outie",
        ai_quality_note="HIGH quality — emotional micro-expressions render well close up"
    ),
    "discovery_object_insert": ShotRecipe(
        shot_type="extreme_close_up",
        focal_length="100-135mm",
        aperture="f/2.0",
        movement="static or slow tilt",
        duration_range=(2, 4),
        motivation="The THING itself — letter, journal, ring, evidence",
        ltx_motion_hint="static close detail of object, shallow depth, soft background",
        reference="Breaking Bad: the blue meth, always in ECU",
        ai_quality_note="HIGHEST quality — objects render perfectly in AI, no identity issues"
    ),

    # === EMOTIONAL / CONFESSION ===
    "confession_opening_wide": ShotRecipe(
        shot_type="medium",
        focal_length="35mm",
        aperture="f/2.8",
        movement="static",
        duration_range=(6, 10),
        motivation="Show isolation — the character alone in space before they speak",
        ltx_motion_hint="character stands alone in room, breathing, weight of decision visible",
        reference="Succession: Tom alone before his confession to Shiv",
        ai_quality_note="MEDIUM quality — establishes space before tightening"
    ),
    "confession_push_in": ShotRecipe(
        shot_type="medium_close",
        focal_length="50-85mm",
        aperture="f/2.0",
        movement="slow push in throughout shot",
        duration_range=(8, 15),
        motivation="Camera moves WITH the emotional build — we get closer as they open up",
        ltx_motion_hint="slow steady push toward character as they speak with growing emotion",
        reference="Every great monologue in prestige TV — camera tightens as emotion deepens",
        ai_quality_note="MEDIUM-HIGH — push-in renders well in LTX-2.3, motivated movement"
    ),
    "confession_held_ecu": ShotRecipe(
        shot_type="extreme_close_up",
        focal_length="100mm",
        aperture="f/2.0",
        movement="static, locked, DO NOT CUT",
        duration_range=(5, 10),
        motivation="The confession lands. Hold it. Let silence work. This is the payoff.",
        ltx_motion_hint="extreme close on face, eyes wet, lips trembling, breathing visible",
        reference="Succession: Logan's eyes when power shifts. Breaking Bad: Walt's face decisions.",
        ai_quality_note="HIGHEST quality — face fills frame, every pixel is emotion"
    ),

    # === ESTABLISHING / ATMOSPHERE ===
    "scene_opener_detail": ShotRecipe(
        shot_type="extreme_close_up",
        focal_length="100mm",
        aperture="f/2.0",
        movement="slow reveal",
        duration_range=(3, 5),
        motivation="Don't open with the room — open with one DETAIL that contains the room",
        ltx_motion_hint="close detail of significant object, dust particles in light beam",
        reference="Breaking Bad: pants in sky. Succession: hands in darkness.",
        ai_quality_note="HIGH — detail shots are AI's strength"
    ),
    "scene_opener_reveal": ShotRecipe(
        shot_type="establishing",
        focal_length="24-35mm",
        aperture="f/4.0",
        movement="slow pull back or pan to reveal",
        duration_range=(5, 8),
        motivation="After the detail, REVEAL the space — context follows mystery",
        ltx_motion_hint="slow pull back revealing full room, natural light, architectural detail",
        reference="Severance: hallway reveals — tight to wide, claustrophobic to spacious",
        ai_quality_note="MEDIUM — keep wide shots SHORT, establish and move on"
    ),
    "atmosphere_empty_space": ShotRecipe(
        shot_type="establishing",
        focal_length="24mm",
        aperture="f/5.6",
        movement="slow lateral drift",
        duration_range=(4, 8),
        motivation="The space WITHOUT people — shows what's left when humans aren't there",
        ltx_motion_hint="slow drift through empty room, dust motes in light, objects undisturbed",
        reference="Severance: empty Lumon hallways. Breaking Bad: empty desert.",
        ai_quality_note="HIGH for AI — no identity tracking needed, pure atmosphere"
    ),

    # === CLOSING / TRANSITION ===
    "scene_exit_wide": ShotRecipe(
        shot_type="medium",
        focal_length="35mm",
        aperture="f/4.0",
        movement="slow pull back or static",
        duration_range=(4, 6),
        motivation="Breathe. Let the scene land. Create space for transition.",
        ltx_motion_hint="character recedes or room settles, moment of stillness",
        reference="Every scene end in Succession — the camera stays after the person leaves",
        ai_quality_note="MEDIUM — transition shots, keep short"
    ),
    "closing_image": ShotRecipe(
        shot_type="establishing",
        focal_length="24mm",
        aperture="f/4.0",
        movement="static or very slow drift",
        duration_range=(5, 10),
        motivation="The thesis restated visually — what does this mean?",
        ltx_motion_hint="held wide composition, symbolic framing, fading light",
        reference="Breaking Bad: every episode-ending desert shot. Succession: final shot of city.",
        ai_quality_note="HIGH for AI — scenic, atmospheric, no faces needed"
    ),
}

# ═══════════════════════════════════════════════════════════════
# SCENE GRAMMAR — Full shot sequence patterns per scene type
# ═══════════════════════════════════════════════════════════════

@dataclass
class SceneGrammar:
    """Complete shot grammar for a scene type."""
    scene_type: str
    description: str
    shot_sequence: List[str]  # ordered list of ShotRecipe keys
    rhythm_pattern: str  # SLOW/BUILD/FAST/BREATHE pattern
    target_duration: Tuple[int, int]  # seconds range
    target_shot_count: Tuple[int, int]  # shot count range
    pacing_note: str
    reference_scenes: List[str]

SCENE_GRAMMARS = {
    "cold_open": SceneGrammar(
        scene_type="cold_open",
        description="First scene — hook the audience in 8 seconds",
        shot_sequence=[
            "scene_opener_detail",      # 1. Thesis image — one detail
            "scene_opener_reveal",       # 2. Pull back — where are we?
            "dialogue_speaker",          # 3. First character — in action
            "dialogue_reaction",         # 4. Second character — reaction
            "dialogue_speaker",          # 5. Dialogue exchange
            "dialogue_reaction",         # 6. Reaction (tension building)
            "discovery_face_reaction",   # 7. Something unspoken — the question
        ],
        rhythm_pattern="TIGHT → REVEAL → BUILD → QUESTION",
        target_duration=(45, 75),
        target_shot_count=(7, 12),
        pacing_note="Start tight and specific. Widen to context. Build to question. ASL 5-7s.",
        reference_scenes=[
            "Succession S1E1: Logan in dark bedroom",
            "Breaking Bad S1E1: pants in sky → RV chaos",
            "Severance S1E1: Helly wakes on table",
        ]
    ),
    "confrontation": SceneGrammar(
        scene_type="confrontation",
        description="Two characters with opposing agendas — power dynamics",
        shot_sequence=[
            "scene_opener_reveal",       # 1. Establish geography — who has power position?
            "dialogue_speaker",          # 2. Aggressor speaks
            "dialogue_reaction",         # 3. Target reacts
            "dialogue_speaker",          # 4. Target responds
            "dialogue_over_shoulder",    # 5. OTS — connecting them in conflict
            "dialogue_speaker",          # 6. Escalation
            "dialogue_reaction",         # 7. Breaking point — ECU-level
            "discovery_face_reaction",   # 8. The turn — something shifts
            "scene_exit_wide",           # 9. Aftermath — new power balance
        ],
        rhythm_pattern="ESTABLISH → BUILD → TIGHTEN → TURN → BREATHE",
        target_duration=(60, 90),
        target_shot_count=(9, 15),
        pacing_note="Start at distance, TIGHTEN as tension rises. Separate frames = opposition.",
        reference_scenes=[
            "Succession: every Kendall vs Logan scene",
            "Breaking Bad: Walt vs Tuco in the junkyard",
        ]
    ),
    "discovery": SceneGrammar(
        scene_type="discovery",
        description="Character finds evidence / information that changes everything",
        shot_sequence=[
            "scene_opener_detail",       # 1. The space — one telling detail
            "dialogue_speaker",          # 2. Character in space — searching
            "discovery_object_insert",   # 3. The THING — first glimpse
            "discovery_hands",           # 4. Hands reach for it
            "discovery_face_reaction",   # 5. Face changes as they read/see
            "discovery_object_insert",   # 6. The detail that matters — ECU
            "discovery_face_reaction",   # 7. Full impact hits — held
        ],
        rhythm_pattern="QUIET → NOTICE → REACH → DISCOVER → IMPACT",
        target_duration=(45, 75),
        target_shot_count=(7, 10),
        pacing_note="Intercut face/object/face/object — each cycle faster. Rhythm = heartbeat.",
        reference_scenes=[
            "Zodiac: discovering handwriting match",
            "Severance: finding the file numbers",
        ]
    ),
    "confession": SceneGrammar(
        scene_type="confession",
        description="Character reveals emotional truth — vulnerability",
        shot_sequence=[
            "confession_opening_wide",   # 1. Isolation — alone in space
            "dialogue_speaker",          # 2. They begin — tentative
            "dialogue_reaction",         # 3. Listener reacts
            "confession_push_in",        # 4. Camera tightens as emotion builds
            "confession_held_ecu",       # 5. The confession — HOLD IT
            "dialogue_reaction",         # 6. Listener's face — the payoff
            "scene_exit_wide",           # 7. Aftermath — breathe
        ],
        rhythm_pattern="WIDE → SPEAK → TIGHTEN → HOLD → REACT → BREATHE",
        target_duration=(60, 120),
        target_shot_count=(6, 10),
        pacing_note="Slowly tighten. The confession shot is HELD — do NOT cut during it. ASL 8-12s.",
        reference_scenes=[
            "Succession: Tom's confession to Shiv",
            "Breaking Bad: Walt's 'I am the danger' speech",
        ]
    ),
    "investigation": SceneGrammar(
        scene_type="investigation",
        description="Character searches, examines, gathers clues",
        shot_sequence=[
            "scene_opener_reveal",       # 1. The space to search
            "dialogue_speaker",          # 2. Character moves through space
            "discovery_object_insert",   # 3. First find — detail
            "discovery_hands",           # 4. Handling evidence
            "discovery_face_reaction",   # 5. Processing
            "discovery_object_insert",   # 6. Second find — escalation
            "discovery_face_reaction",   # 7. Realization building
            "dialogue_speaker",          # 8. Decision made — action
        ],
        rhythm_pattern="SEARCH → FIND → PROCESS → FIND → REALIZE → ACT",
        target_duration=(50, 80),
        target_shot_count=(8, 12),
        pacing_note="Methodical opening, accelerating as discoveries compound. ASL 5-7s.",
        reference_scenes=[
            "Zodiac: examining evidence",
            "Severance: exploring the testing floor",
        ]
    ),
    "atmosphere": SceneGrammar(
        scene_type="atmosphere",
        description="Establishing mood — minimal or no dialogue",
        shot_sequence=[
            "scene_opener_detail",       # 1. Detail — texture of the place
            "atmosphere_empty_space",    # 2. The space itself — breathing
            "scene_opener_reveal",       # 3. Wider context
            "closing_image",             # 4. The mood image — held
        ],
        rhythm_pattern="DETAIL → BREATHE → CONTEXT → HOLD",
        target_duration=(15, 30),
        target_shot_count=(3, 5),
        pacing_note="Slow, contemplative. Every shot earns its time. ASL 8-12s. Silence is the score.",
        reference_scenes=[
            "Severance: Lumon hallways",
            "Breaking Bad: desert landscapes",
        ]
    ),
    "transition": SceneGrammar(
        scene_type="transition",
        description="Moving between locations or time — bridging scenes",
        shot_sequence=[
            "atmosphere_empty_space",    # 1. Where we're going
            "scene_opener_detail",       # 2. One detail of new space
        ],
        rhythm_pattern="MOVE → ARRIVE",
        target_duration=(8, 15),
        target_shot_count=(2, 3),
        pacing_note="Quick. Functional. Don't overindulge. ASL 4-6s.",
        reference_scenes=[
            "Succession: quick New York establishing between scenes",
        ]
    ),
}


# ═══════════════════════════════════════════════════════════════
# PUBLIC API — What the pipeline calls
# ═══════════════════════════════════════════════════════════════

def classify_scene_type(beat_description: str, characters: list,
                        has_dialogue: bool, scene_position: str = "middle") -> str:
    """Classify a scene beat into a scene type for grammar lookup.

    Args:
        beat_description: text description of what happens
        characters: list of character names in scene
        has_dialogue: whether scene has dialogue
        scene_position: "opening", "middle", "climax", "closing"

    Returns:
        Scene type string matching SCENE_TYPES keys
    """
    desc_lower = (beat_description or "").lower()

    # Position-based overrides
    if scene_position == "opening":
        return "cold_open"
    if scene_position == "closing":
        return "atmosphere" if not has_dialogue else "resolution"

    # Content-based classification
    discovery_words = ["find", "discover", "read", "open", "letter",
                       "journal", "evidence", "document", "photograph",
                       "notice", "spot", "see", "reveal"]
    confession_words = ["confess", "admit", "truth", "love", "secret",
                        "tell you", "never told", "should have",
                        "forgive", "coward", "regret"]
    confrontation_words = ["threaten", "confront", "argue", "demand",
                           "refuse", "stop", "authority", "mistake",
                           "warn", "dangerous", "challenge"]
    investigation_words = ["search", "examine", "investigate", "look for",
                           "photograph", "document", "transcribe", "catalog"]

    # Score each type — highest wins (prevents discovery-bias from common words)
    discovery_score = sum(1 for w in discovery_words if w in desc_lower)
    confession_score = sum(1 for w in confession_words if w in desc_lower)
    confrontation_score = sum(1 for w in confrontation_words if w in desc_lower)
    investigation_score = sum(1 for w in investigation_words if w in desc_lower)

    # 2+ characters with dialogue is a confrontation signal
    if has_dialogue and len(characters) >= 2:
        confrontation_score += 2

    scores = {
        "confrontation": confrontation_score,
        "confession": confession_score,
        "discovery": discovery_score,
        "investigation": investigation_score,
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    if not has_dialogue and len(characters) <= 1:
        return "atmosphere"
    if has_dialogue and len(characters) >= 2:
        return "confrontation"

    return "atmosphere"


def get_scene_grammar(scene_type: str, genre: str = "mystery_thriller") -> dict:
    """Get the full shot grammar for a scene type.

    Returns dict with:
        - shot_sequence: list of ShotRecipe keys
        - pacing: GenrePacing data
        - rhythm_pattern: string
        - target_duration: (min, max) seconds
        - target_shot_count: (min, max)
    """
    grammar = SCENE_GRAMMARS.get(scene_type, SCENE_GRAMMARS["atmosphere"])
    pacing = GENRE_PACING.get(genre, GENRE_PACING["mystery_thriller"])

    return {
        "scene_type": grammar.scene_type,
        "shot_sequence": grammar.shot_sequence,
        "rhythm_pattern": grammar.rhythm_pattern,
        "target_duration": grammar.target_duration,
        "target_shot_count": grammar.target_shot_count,
        "pacing_note": grammar.pacing_note,
        "reference_scenes": grammar.reference_scenes,
        "genre_asl": pacing.avg_shot_length,
        "genre_cuts_per_minute": pacing.cuts_per_minute,
        "genre_dialogue_asl": pacing.dialogue_asl,
    }


def get_shot_recipe(recipe_key: str, emotion_level: int = 5) -> dict:
    """Get a specific shot recipe with emotion-adjusted parameters.

    Args:
        recipe_key: key from SHOT_RECIPES
        emotion_level: 1-10 emotional intensity (affects focal length, duration)

    Returns dict with all shot parameters for nano_prompt and ltx_motion.
    """
    recipe = SHOT_RECIPES.get(recipe_key)
    if not recipe:
        recipe = SHOT_RECIPES["dialogue_speaker"]  # safe default

    # Emotion adjustments
    duration_min, duration_max = recipe.duration_range
    if emotion_level >= 8:
        # High emotion: tighter shots, slightly longer holds
        duration_min = min(duration_min + 1, duration_max)
    elif emotion_level <= 3:
        # Low emotion: standard or slightly shorter
        duration_max = max(duration_max - 1, duration_min)

    return {
        "shot_type": recipe.shot_type,
        "focal_length": recipe.focal_length,
        "aperture": recipe.aperture,
        "movement": recipe.movement,
        "duration_range": (duration_min, duration_max),
        "motivation": recipe.motivation,
        "ltx_motion_hint": recipe.ltx_motion_hint,
        "reference": recipe.reference,
        "ai_quality_note": recipe.ai_quality_note,
        "emotion_level": emotion_level,
    }


def build_shot_plan_from_grammar(scene_type: str, beats: list,
                                  characters: list,
                                  genre: str = "mystery_thriller") -> list:
    """Build a complete shot plan for a scene using creative grammar.

    Args:
        scene_type: classified scene type
        beats: list of story bible beats for the scene
        characters: list of character names in scene
        genre: genre for pacing data

    Returns:
        List of shot dicts ready for the pipeline
    """
    grammar = get_scene_grammar(scene_type, genre)
    sequence = grammar["shot_sequence"]
    shots = []

    for i, recipe_key in enumerate(sequence):
        recipe = get_shot_recipe(recipe_key, emotion_level=5)

        # Map beat if available
        beat_idx = min(i, len(beats) - 1) if beats else 0
        beat = beats[beat_idx] if beats else {}

        # Calculate duration from genre pacing
        dur_min, dur_max = recipe["duration_range"]
        # Use genre ASL as center point
        genre_asl = grammar["genre_asl"]
        duration = max(dur_min, min(dur_max, genre_asl))

        shot = {
            "shot_type": recipe["shot_type"],
            "focal_length": recipe["focal_length"],
            "aperture": recipe["aperture"],
            "camera_movement": recipe["movement"],
            "duration_seconds": round(duration, 1),
            "ltx_motion_hint": recipe["ltx_motion_hint"],
            "creative_motivation": recipe["motivation"],
            "reference": recipe["reference"],
            "characters": characters if "dialogue" in recipe_key or "confession" in recipe_key else [],
            "beat_description": beat.get("description", ""),
            "rhythm_position": grammar["rhythm_pattern"].split(" → ")[min(i, len(grammar["rhythm_pattern"].split(" → ")) - 1)] if " → " in grammar["rhythm_pattern"] else "",
        }
        shots.append(shot)

    return shots


# ═══════════════════════════════════════════════════════════════
# EMOTION → CAMERA MAPPING (from psychology research)
# ═══════════════════════════════════════════════════════════════

EMOTION_TO_CAMERA = {
    # Emotion: (preferred_focal, preferred_movement, duration_modifier)
    "dread": ("50-85mm", "slow push in", 1.3),
    "tension": ("65-85mm", "static, locked", 1.1),
    "grief": ("85-100mm", "slow pull back", 1.4),
    "shock": ("100-135mm", "static, hold", 0.8),
    "anger": ("50-65mm", "handheld subtle", 0.9),
    "intimacy": ("85mm", "slow push in", 1.2),
    "power": ("24-35mm", "low angle, static", 1.0),
    "vulnerability": ("85-135mm", "static, level", 1.2),
    "curiosity": ("50mm", "slow lateral drift", 1.0),
    "revelation": ("85mm", "push in accelerating", 0.9),
    "hope": ("35-50mm", "slow tilt up", 1.1),
    "isolation": ("24mm", "slow pull back", 1.3),
}


def get_emotion_camera(emotion: str) -> dict:
    """Get camera parameters driven by emotion.

    Returns focal, movement, and duration modifier.
    """
    mapping = EMOTION_TO_CAMERA.get(emotion, ("50mm", "static", 1.0))
    return {
        "focal_length": mapping[0],
        "movement": mapping[1],
        "duration_modifier": mapping[2],
    }
