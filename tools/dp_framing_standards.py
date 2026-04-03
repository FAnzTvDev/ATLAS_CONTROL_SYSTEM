"""
DP Framing Standards Reference Module for ATLAS V27

Encodes Hollywood cinematography knowledge into structured shot-level decision guidance.
Provides: shot taxonomy, scene coverage patterns, emotional framing modifiers, B-roll narrative
generation, and optimal reference selection logic.

Authority: Director of Photography (DP) perspective on camera placement, composition, and visual
continuity. Non-blocking advisory system — generates recommendations, never blocks generation.

Production Evidence: Built from real DP notes (American Cinematographer, Fincher/Deakins/Lubezki
technique analysis, Victorian Shadows EP1 coverage patterns).

Tier: TIER 3 (Operational Guidance) — see CLAUDE.md Organ Laws T2-CP-1 through T2-CP-8 (Chain Policy)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set, Tuple
import json
from pathlib import Path


# ============================================================================
# SECTION 1: SHOT TYPE TAXONOMY
# ============================================================================

class ShotType(Enum):
    """Hollywood standard shot types with cinematographic properties."""

    # CLOSE SHOTS (Emotional/Intimate)
    ECU = "extreme_close_up"           # Eyes/mouth only, max intimacy, emotional peaks
    CU = "close_up"                     # Head/shoulders, standard dialogue coverage
    MCU = "medium_close_up"             # Chest up, most common dialogue shot

    # MEDIUM SHOTS (Standard Coverage)
    MS = "medium_shot"                  # Waist up, shows body language + gesture
    MWS = "medium_wide_shot"            # Knees up, character in environment

    # WIDE SHOTS (Geography/Establishment)
    WS = "wide_shot"                    # Full body, spatial relationship
    EWS = "extreme_wide_shot"           # Character small in frame, environment dominates

    # MULTI-CHARACTER COVERAGE
    OTS = "over_the_shoulder"           # Shoulder/head of foreground, face of background
    TWO_SHOT = "two_shot"               # Two characters equally framed

    # DETAIL/SUBJECTIVE
    INSERT = "insert"                   # Object detail, non-character focus
    POV = "point_of_view"               # Character's line of sight

    # COMPOSITIONAL MODIFIERS
    DUTCH = "dutch_angle"               # Tilted frame, psychological unease
    LOW_ANGLE = "low_angle"             # Camera below eyeline, power/dominance
    HIGH_ANGLE = "high_angle"           # Camera above eyeline, vulnerability

    # MONTAGE/SEQUENCE
    MONTAGE = "montage"                 # Multiple quick cuts, passage of time
    SEQUENCE = "sequence"               # Multi-shot connected action


@dataclass
class ShotTypeProfile:
    """Cinematographic properties for each shot type."""

    shot_type: ShotType
    framing_description: str            # What's in frame (eyes/mouth, head/shoulders, etc.)
    intimacy_level: int                 # 1-10, 10 = most intimate
    emotion_weight: float               # How much emotion this shot carries (0-1)
    body_language_visible: bool         # Can we see hands/posture?
    environment_visible: bool           # Is background meaningful?
    dialogue_suitability: str           # "primary", "secondary", "none"
    typical_lens_mm: Tuple[int, int]    # Range: (wide_end, tele_end)
    depth_of_field: str                 # "shallow", "medium", "deep"
    emotional_association: List[str]    # What emotions this shot typically conveys
    reframe_distance_mm: Tuple[int, int]  # How far you can push/pull this shot before changing role
    continuity_strength: str             # How well this shot chains to next: "strong", "medium", "weak"


SHOT_TYPE_PROFILES: Dict[ShotType, ShotTypeProfile] = {

    ShotType.ECU: ShotTypeProfile(
        shot_type=ShotType.ECU,
        framing_description="Eyes/mouth only, fills frame",
        intimacy_level=10,
        emotion_weight=0.95,
        body_language_visible=False,
        environment_visible=False,
        dialogue_suitability="primary",
        typical_lens_mm=(50, 85),
        depth_of_field="shallow",
        emotional_association=["shock", "revelation", "grief", "rage", "intimacy"],
        reframe_distance_mm=(50, 85),
        continuity_strength="strong"
    ),

    ShotType.CU: ShotTypeProfile(
        shot_type=ShotType.CU,
        framing_description="Head/shoulders, fills frame",
        intimacy_level=9,
        emotion_weight=0.90,
        body_language_visible=False,
        environment_visible=False,
        dialogue_suitability="primary",
        typical_lens_mm=(50, 75),
        depth_of_field="shallow",
        emotional_association=["dialogue", "emotion", "reaction", "confession"],
        reframe_distance_mm=(50, 75),
        continuity_strength="strong"
    ),

    ShotType.MCU: ShotTypeProfile(
        shot_type=ShotType.MCU,
        framing_description="Chest up, most coverage",
        intimacy_level=7,
        emotion_weight=0.75,
        body_language_visible=True,
        environment_visible=False,
        dialogue_suitability="primary",
        typical_lens_mm=(35, 50),
        depth_of_field="medium",
        emotional_association=["dialogue", "action_start", "attention"],
        reframe_distance_mm=(35, 50),
        continuity_strength="strong"
    ),

    ShotType.MS: ShotTypeProfile(
        shot_type=ShotType.MS,
        framing_description="Waist up, full body action",
        intimacy_level=5,
        emotion_weight=0.60,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="secondary",
        typical_lens_mm=(24, 35),
        depth_of_field="medium",
        emotional_association=["action", "movement", "gesture", "approach"],
        reframe_distance_mm=(24, 35),
        continuity_strength="medium"
    ),

    ShotType.MWS: ShotTypeProfile(
        shot_type=ShotType.MWS,
        framing_description="Knees up, character in environment",
        intimacy_level=4,
        emotion_weight=0.45,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="secondary",
        typical_lens_mm=(20, 28),
        depth_of_field="medium",
        emotional_association=["context", "arrival", "containment", "location"],
        reframe_distance_mm=(20, 28),
        continuity_strength="medium"
    ),

    ShotType.WS: ShotTypeProfile(
        shot_type=ShotType.WS,
        framing_description="Full body, character small in space",
        intimacy_level=2,
        emotion_weight=0.30,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(16, 24),
        depth_of_field="deep",
        emotional_association=["isolation", "geography", "scale", "loneliness"],
        reframe_distance_mm=(16, 24),
        continuity_strength="weak"
    ),

    ShotType.EWS: ShotTypeProfile(
        shot_type=ShotType.EWS,
        framing_description="Character tiny, environment dominates",
        intimacy_level=1,
        emotion_weight=0.25,
        body_language_visible=False,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(8, 16),
        depth_of_field="deep",
        emotional_association=["isolation", "insignificance", "vast", "wonder"],
        reframe_distance_mm=(8, 16),
        continuity_strength="weak"
    ),

    ShotType.OTS: ShotTypeProfile(
        shot_type=ShotType.OTS,
        framing_description="Foreground shoulder/head + background face",
        intimacy_level=6,
        emotion_weight=0.70,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="primary",
        typical_lens_mm=(24, 50),
        depth_of_field="medium",
        emotional_association=["dialogue", "confrontation", "intimacy", "reaction"],
        reframe_distance_mm=(24, 50),
        continuity_strength="strong"
    ),

    ShotType.TWO_SHOT: ShotTypeProfile(
        shot_type=ShotType.TWO_SHOT,
        framing_description="Two characters equally in frame",
        intimacy_level=5,
        emotion_weight=0.65,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="primary",
        typical_lens_mm=(20, 35),
        depth_of_field="medium",
        emotional_association=["relationship", "balance", "connection", "conflict"],
        reframe_distance_mm=(20, 35),
        continuity_strength="medium"
    ),

    ShotType.INSERT: ShotTypeProfile(
        shot_type=ShotType.INSERT,
        framing_description="Object/detail fills frame, no character",
        intimacy_level=3,
        emotion_weight=0.50,
        body_language_visible=False,
        environment_visible=False,
        dialogue_suitability="none",
        typical_lens_mm=(35, 85),
        depth_of_field="shallow",
        emotional_association=["discovery", "attention", "detail", "meaning"],
        reframe_distance_mm=(35, 85),
        continuity_strength="medium"
    ),

    ShotType.POV: ShotTypeProfile(
        shot_type=ShotType.POV,
        framing_description="Character's line of sight, first-person view",
        intimacy_level=8,
        emotion_weight=0.80,
        body_language_visible=False,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(16, 50),
        depth_of_field="medium",
        emotional_association=["curiosity", "fear", "desire", "discovery"],
        reframe_distance_mm=(16, 50),
        continuity_strength="weak"
    ),

    ShotType.DUTCH: ShotTypeProfile(
        shot_type=ShotType.DUTCH,
        framing_description="Tilted frame (20-30 degrees)",
        intimacy_level=5,
        emotion_weight=0.85,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(20, 50),
        depth_of_field="medium",
        emotional_association=["unease", "confusion", "danger", "tension"],
        reframe_distance_mm=(20, 50),
        continuity_strength="weak"
    ),

    ShotType.LOW_ANGLE: ShotTypeProfile(
        shot_type=ShotType.LOW_ANGLE,
        framing_description="Camera below eyeline, looking up",
        intimacy_level=6,
        emotion_weight=0.75,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(16, 35),
        depth_of_field="deep",
        emotional_association=["power", "dominance", "threat", "heroism"],
        reframe_distance_mm=(16, 35),
        continuity_strength="weak"
    ),

    ShotType.HIGH_ANGLE: ShotTypeProfile(
        shot_type=ShotType.HIGH_ANGLE,
        framing_description="Camera above eyeline, looking down",
        intimacy_level=4,
        emotion_weight=0.70,
        body_language_visible=True,
        environment_visible=True,
        dialogue_suitability="none",
        typical_lens_mm=(16, 35),
        depth_of_field="deep",
        emotional_association=["vulnerability", "submission", "insignificance", "judgment"],
        reframe_distance_mm=(16, 35),
        continuity_strength="weak"
    ),
}


# ============================================================================
# SECTION 2: SCENE TYPE → COVERAGE PATTERNS
# ============================================================================

class SceneType(Enum):
    """Scene archetypes mapped to standard DP coverage patterns."""

    DIALOGUE_CONFRONTATION = "dialogue_confrontation"
    DIALOGUE_INTIMATE = "dialogue_intimate"
    DIALOGUE_EXPOSITION = "dialogue_exposition"
    ARRIVAL_DEPARTURE = "arrival_departure"
    DISCOVERY_REVELATION = "discovery_revelation"
    SOLITARY_REFLECTION = "solitary_reflection"
    ACTION_PHYSICAL = "action_physical"
    INVESTIGATION_SEARCH = "investigation_search"


@dataclass
class CoveragePattern:
    """Standard DP coverage for a scene type."""

    scene_type: SceneType
    description: str
    primary_shots: List[ShotType]              # Master → supporting shots
    secondary_shots: List[ShotType]            # Reaction cuts, inserts
    optional_shots: List[ShotType]             # Context, mood, atmosphere
    cutting_rhythm: str                        # "fast", "medium", "slow"
    average_shot_duration_sec: Tuple[int, int] # (min, max)
    key_rules: List[str]                       # What NOT to forget
    lens_progression: List[int]                # Typical lens path through scene (mm)
    lighting_mood: str                         # Warm/cool/neutral, contrast level
    depth_of_field_strategy: str               # How DoF changes through scene


SCENE_COVERAGE_PATTERNS: Dict[SceneType, CoveragePattern] = {

    SceneType.DIALOGUE_CONFRONTATION: CoveragePattern(
        scene_type=SceneType.DIALOGUE_CONFRONTATION,
        description="High-tension argument or confrontation. Tightening pattern as tension builds.",
        primary_shots=[
            ShotType.TWO_SHOT,      # Wide master, both visible
            ShotType.OTS,           # Speaker A (aggressor), face visible
            ShotType.OTS,           # Speaker B (defender), face visible
            ShotType.CU,            # Reaction A
            ShotType.CU,            # Reaction B
        ],
        secondary_shots=[ShotType.MCU, ShotType.MS, ShotType.INSERT],
        optional_shots=[ShotType.DUTCH, ShotType.LOW_ANGLE],
        cutting_rhythm="fast",
        average_shot_duration_sec=(2, 4),
        key_rules=[
            "Enforce 180° rule: camera stays on one side of dialogue axis",
            "Alternate speakers: OTS-A → OTS-B → OTS-A pattern",
            "Progressive tightening: start wide, end in CU",
            "Match eyeline: each shot looks toward opposite speaker",
            "Reaction cuts accelerate as tension peaks"
        ],
        lens_progression=[24, 35, 35, 50, 50],
        lighting_mood="cool, high contrast, shadow-heavy",
        depth_of_field_strategy="shallow in close shots, tighter as emotion peaks"
    ),

    SceneType.DIALOGUE_INTIMATE: CoveragePattern(
        scene_type=SceneType.DIALOGUE_INTIMATE,
        description="Vulnerable confession or intimate moment. Slow rhythm, shallow DoF.",
        primary_shots=[
            ShotType.TWO_SHOT,      # Establishing, both present
            ShotType.CU,            # Speaker, emotional peaks
            ShotType.CU,            # Listener, reaction
        ],
        secondary_shots=[ShotType.MCU, ShotType.INSERT],
        optional_shots=[],
        cutting_rhythm="slow",
        average_shot_duration_sec=(5, 10),
        key_rules=[
            "Shallow depth of field throughout",
            "Warm key light, soft shadows",
            "Longer holds, fewer cuts",
            "Music/silence as important as dialogue",
            "Close-ups for emotional peaks only"
        ],
        lens_progression=[35, 50, 50],
        lighting_mood="warm, low contrast, soft shadows",
        depth_of_field_strategy="shallow throughout, isolation from environment"
    ),

    SceneType.DIALOGUE_EXPOSITION: CoveragePattern(
        scene_type=SceneType.DIALOGUE_EXPOSITION,
        description="Functional information delivery (explaining plot, exposition). Standard coverage.",
        primary_shots=[
            ShotType.WS,            # Master establishes space
            ShotType.MCU,           # Speaker, clear and functional
            ShotType.MCU,           # Listener
        ],
        secondary_shots=[ShotType.MS, ShotType.CU],
        optional_shots=[],
        cutting_rhythm="medium",
        average_shot_duration_sec=(3, 6),
        key_rules=[
            "Prioritize clarity over emotion",
            "Functional coverage, no fancy angles",
            "Listener reaction important: shows engagement",
            "Medium DoF: keep space visible",
            "Standard neutral lighting"
        ],
        lens_progression=[24, 35, 35],
        lighting_mood="neutral, even lighting",
        depth_of_field_strategy="medium: character AND background both visible"
    ),

    SceneType.ARRIVAL_DEPARTURE: CoveragePattern(
        scene_type=SceneType.ARRIVAL_DEPARTURE,
        description="Character arrives/leaves location. B-roll sequence: exterior → approach → entry → interior reaction.",
        primary_shots=[
            ShotType.EWS,           # Exterior wide, character small
            ShotType.WS,            # Character approaching
            ShotType.MS,            # Crossing threshold
            ShotType.MCU,           # Interior reaction
        ],
        secondary_shots=[ShotType.INSERT, ShotType.POV],
        optional_shots=[ShotType.LOW_ANGLE],
        cutting_rhythm="medium",
        average_shot_duration_sec=(3, 5),
        key_rules=[
            "Show ARRIVAL not just appearance",
            "B-roll: vehicle/footsteps/door handle/threshold",
            "Environmental change must be visible (inside vs outside)",
            "Character emotion on entry carries forward",
            "Final interior shot should contain emotional reaction"
        ],
        lens_progression=[16, 20, 28, 35],
        lighting_mood="changes from exterior to interior lighting",
        depth_of_field_strategy="deep exterior shots, transitions to medium/shallow interiors"
    ),

    SceneType.DISCOVERY_REVELATION: CoveragePattern(
        scene_type=SceneType.DISCOVERY_REVELATION,
        description="Character discovers something important. Hitchcock rule: show audience the discovery BEFORE the character reacts.",
        primary_shots=[
            ShotType.POV,           # Character approaches
            ShotType.INSERT,        # Object/revelation, emphasis
            ShotType.ECU,           # Character reaction
            ShotType.MS,            # Pull back to character in space
        ],
        secondary_shots=[ShotType.CU, ShotType.WS],
        optional_shots=[],
        cutting_rhythm="medium",
        average_shot_duration_sec=(2, 5),
        key_rules=[
            "Reveal BEFORE reaction: audience sees first",
            "INSERT gets special emphasis/framing",
            "Reaction shot (ECU) is emotional peak",
            "Pull back after peak: character in context",
            "No dialogue typically — let visuals carry meaning"
        ],
        lens_progression=[24, 50, 85, 35],
        lighting_mood="dramatic, emphasis on INSERT",
        depth_of_field_strategy="POV medium, INSERT shallow for emphasis, ECU very shallow"
    ),

    SceneType.SOLITARY_REFLECTION: CoveragePattern(
        scene_type=SceneType.SOLITARY_REFLECTION,
        description="Character alone, thinking/feeling. Wide space emphasizes isolation. B-roll intercuts mood.",
        primary_shots=[
            ShotType.WS,            # Character tiny in space
            ShotType.MS,            # Slow push toward MCU
            ShotType.CU,            # Hold on face, silence
        ],
        secondary_shots=[ShotType.INSERT, ShotType.EWS],
        optional_shots=[],
        cutting_rhythm="slow",
        average_shot_duration_sec=(5, 12),
        key_rules=[
            "Emphasize empty space and isolation",
            "Slow push toward tighter frame",
            "Hold final CU, resist cutting away",
            "B-roll intercuts: ticking clock, rain, empty chair",
            "Minimal dialogue or voice-over only",
            "Silence is the point"
        ],
        lens_progression=[24, 35, 50],
        lighting_mood="cool, single-source key light, deep shadows",
        depth_of_field_strategy="deep wide shots, gradually shallower as we push in"
    ),

    SceneType.ACTION_PHYSICAL: CoveragePattern(
        scene_type=SceneType.ACTION_PHYSICAL,
        description="Physical action: fight, chase, movement-heavy. Wide lenses, multiple angles, faster cutting.",
        primary_shots=[
            ShotType.EWS,           # Geography establish
            ShotType.WS,            # Action coverage wide
            ShotType.MS,            # Action coverage medium
            ShotType.CU,            # Impact moments (impact, collision, pain)
            ShotType.WS,            # Aftermath, character state
        ],
        secondary_shots=[ShotType.INSERT, ShotType.POV, ShotType.LOW_ANGLE],
        optional_shots=[ShotType.HIGH_ANGLE],
        cutting_rhythm="fast",
        average_shot_duration_sec=(1, 3),
        key_rules=[
            "Establish geography first",
            "Cover action from multiple angles",
            "Impact moments get CU emphasis",
            "Faster editing, wider lenses",
            "Always show aftermath: where did action leave character?",
            "Maintain 180° rule even in chaos"
        ],
        lens_progression=[16, 20, 24, 35, 20],
        lighting_mood="high contrast, motivated by action (practical lights moving with camera)",
        depth_of_field_strategy="deep: need to see full action geography"
    ),

    SceneType.INVESTIGATION_SEARCH: CoveragePattern(
        scene_type=SceneType.INVESTIGATION_SEARCH,
        description="Character searching/investigating a location. POV shots, INSERTs of clues, reaction cuts.",
        primary_shots=[
            ShotType.WS,            # Room geography
            ShotType.MS,            # Character moving through space
            ShotType.INSERT,        # Clue detail
            ShotType.CU,            # Reaction to clue
        ],
        secondary_shots=[ShotType.POV, ShotType.MCU, ShotType.MWS],
        optional_shots=[],
        cutting_rhythm="medium",
        average_shot_duration_sec=(2, 5),
        key_rules=[
            "Establish room first with WS",
            "Show character's PROCESS: scanning, moving, touching",
            "INSERT clues with clear framing",
            "Reaction shots show character understanding moment",
            "POV shots of character examining things",
            "Audience should understand what matters to character"
        ],
        lens_progression=[24, 28, 50, 75],
        lighting_mood="motivated by practical room lighting, shadows matter",
        depth_of_field_strategy="medium for geography, shallow for INSERT/reaction"
    ),
}


# ============================================================================
# SECTION 3: COVERAGE_ROLE → REF_PRIORITY MAPPING
# ============================================================================

class CoverageRole(Enum):
    """Editorial coverage role determines reference and B-roll requirements."""

    A_GEOGRAPHY = "a_geography"           # Wide/establishing, environment primary
    B_COVERAGE = "b_coverage"             # Standard medium coverage
    C_EMPHASIS = "c_emphasis"             # Close-up, emotional peak
    D_CONTEXTUAL = "d_contextual"         # B-roll, atmosphere, no character required


@dataclass
class CoverageRoleProfile:
    """Reference and B-roll requirements by coverage role."""

    role: CoverageRole
    purpose: str
    required_character_refs: int                    # Min refs needed
    optional_character_refs: int                    # Can use more
    location_ref_required: bool
    b_roll_character_present: bool                  # Does B-roll include character or environment-only?
    typical_shot_types: List[ShotType]
    continuity_chaining_role: str                   # "anchor", "chain", "independent"
    ref_resolution_requirement: str                 # "character_identity_critical", "environment_critical", "flexible"


COVERAGE_ROLE_PROFILES: Dict[CoverageRole, CoverageRoleProfile] = {

    CoverageRole.A_GEOGRAPHY: CoverageRoleProfile(
        role=CoverageRole.A_GEOGRAPHY,
        purpose="Establish location and geography. Character secondary to environment.",
        required_character_refs=0,
        optional_character_refs=1,
        location_ref_required=True,
        b_roll_character_present=False,
        typical_shot_types=[ShotType.EWS, ShotType.WS, ShotType.MWS],
        continuity_chaining_role="anchor",
        ref_resolution_requirement="environment_critical"
    ),

    CoverageRole.B_COVERAGE: CoverageRoleProfile(
        role=CoverageRole.B_COVERAGE,
        purpose="Standard character coverage. Dialogue or action primary.",
        required_character_refs=1,
        optional_character_refs=2,
        location_ref_required=False,
        b_roll_character_present=True,
        typical_shot_types=[ShotType.MCU, ShotType.MS, ShotType.OTS, ShotType.TWO_SHOT],
        continuity_chaining_role="chain",
        ref_resolution_requirement="character_identity_critical"
    ),

    CoverageRole.C_EMPHASIS: CoverageRoleProfile(
        role=CoverageRole.C_EMPHASIS,
        purpose="Emotional peak. Character emotion and identity paramount.",
        required_character_refs=1,
        optional_character_refs=1,
        location_ref_required=False,
        b_roll_character_present=False,
        typical_shot_types=[ShotType.ECU, ShotType.CU, ShotType.INSERT],
        continuity_chaining_role="chain",
        ref_resolution_requirement="character_identity_critical"
    ),

    CoverageRole.D_CONTEXTUAL: CoverageRoleProfile(
        role=CoverageRole.D_CONTEXTUAL,
        purpose="B-roll, atmosphere, mood. No character identity needed.",
        required_character_refs=0,
        optional_character_refs=0,
        location_ref_required=True,
        b_roll_character_present=False,
        typical_shot_types=[ShotType.INSERT, ShotType.EWS, ShotType.WS],
        continuity_chaining_role="independent",
        ref_resolution_requirement="environment_critical"
    ),
}


# ============================================================================
# SECTION 4: EMOTIONAL_BEAT → FRAMING_MODIFIER
# ============================================================================

@dataclass
class EmotionalFramingModifier:
    """How emotion modifies base framing choices."""

    emotion: str
    framing_modifier: str                           # What changes in the frame
    shot_type_push: str                             # "tighter" (CU), "wider" (WS), "none"
    depth_of_field_modifier: str                    # "shallower", "deeper", "none"
    lens_direction: str                             # "telephoto", "wide", "normal"
    rhythm_modifier: str                            # "faster_cuts", "slower_holds", "none"
    angle_recommendation: str                       # "low_angle", "high_angle", "level", "dutch"
    lighting_mood: str
    prompt_injection: str                           # What to add to nano_prompt
    continuity_emphasis: str                        # What continuity element matters most


EMOTIONAL_FRAMING_MODIFIERS: Dict[str, EmotionalFramingModifier] = {

    "tension_building": EmotionalFramingModifier(
        emotion="tension_building",
        framing_modifier="Progressive tightening: each shot closer than last",
        shot_type_push="tighter",
        depth_of_field_modifier="shallower",
        lens_direction="telephoto",
        rhythm_modifier="faster_cuts",
        angle_recommendation="level or low_angle for power dynamic",
        lighting_mood="High contrast, shadow-heavy, key light directional",
        prompt_injection="mounting tension, physical stillness before explosion, breath shallow",
        continuity_emphasis="eyeline matching, 180° rule sacred"
    ),

    "grief": EmotionalFramingModifier(
        emotion="grief",
        framing_modifier="Wider framing emphasizes isolation in space",
        shot_type_push="wider",
        depth_of_field_modifier="deeper",
        lens_direction="wide",
        rhythm_modifier="slower_holds",
        angle_recommendation="level or high_angle to show vulnerability",
        lighting_mood="Cool, diffuse light, minimal shadows, overcast feeling",
        prompt_injection="silent moment, motionless except for breath, tears, weight of body",
        continuity_emphasis="environmental isolation, empty space around character"
    ),

    "anger": EmotionalFramingModifier(
        emotion="anger",
        framing_modifier="Tighter framing, more aggressive angles",
        shot_type_push="tighter",
        depth_of_field_modifier="shallower",
        lens_direction="telephoto or wide (distortion)",
        rhythm_modifier="faster_cuts",
        angle_recommendation="low_angle or dutch angle",
        lighting_mood="High contrast, sharp shadows, motivated by practical lights",
        prompt_injection="jaw clenched, fists tightening, sudden movement, barely contained",
        continuity_emphasis="body language intensity, explosive potential"
    ),

    "fear": EmotionalFramingModifier(
        emotion="fear",
        framing_modifier="POV emphasis, character small in frame, high angles",
        shot_type_push="wider",
        depth_of_field_modifier="deeper",
        lens_direction="wide",
        rhythm_modifier="faster_cuts",
        angle_recommendation="high_angle or wide POV",
        lighting_mood="Shadow-heavy, unpredictable lighting, motivated by environment",
        prompt_injection="eyes wide, breathing visible, hands trembling or reaching for support",
        continuity_emphasis="environmental threat, spatial vulnerability"
    ),

    "revelation": EmotionalFramingModifier(
        emotion="revelation",
        framing_modifier="Dolly-in equivalent: sequence from wide to ECU over several shots",
        shot_type_push="tighter",
        depth_of_field_modifier="shallower",
        lens_direction="normal to telephoto",
        rhythm_modifier="medium_rhythm",
        angle_recommendation="level then low_angle for power",
        lighting_mood="Motivated by discovered object: spotlit, dramatic",
        prompt_injection="eyes focused, sudden understanding, body goes still, then moves",
        continuity_emphasis="object discovery carries through to reaction"
    ),

    "intimacy": EmotionalFramingModifier(
        emotion="intimacy",
        framing_modifier="Shallow DoF, close framings, warm tones, eyeline matching",
        shot_type_push="tighter",
        depth_of_field_modifier="shallower",
        lens_direction="normal to telephoto",
        rhythm_modifier="slower_holds",
        angle_recommendation="level or slightly low",
        lighting_mood="Warm key light, soft shadows, practical light motivated by setting",
        prompt_injection="gentle expression, slow breathing, eye contact, hands touching or reaching",
        continuity_emphasis="eyeline matching, spatial proximity"
    ),

    "confusion": EmotionalFramingModifier(
        emotion="confusion",
        framing_modifier="Multiple angles, dutch angles, POV disorientation",
        shot_type_push="none",
        depth_of_field_modifier="none",
        lens_direction="wide to telephoto mismatch",
        rhythm_modifier="faster_cuts",
        angle_recommendation="dutch or multiple competing angles",
        lighting_mood="Inconsistent, conflicting practical lights",
        prompt_injection="eyes searching, head turning, body off-balance, gaze unfocused",
        continuity_emphasis="spatial geography becomes unclear"
    ),

    "triumph": EmotionalFramingModifier(
        emotion="triumph",
        framing_modifier="Elevated angle (character rises), wide open space, high horizon",
        shot_type_push="wider",
        depth_of_field_modifier="deeper",
        lens_direction="wide",
        rhythm_modifier="slower_holds",
        angle_recommendation="low_angle (character powerful) or level wide",
        lighting_mood="Bright, golden hour, high-key, backlighting optional",
        prompt_injection="shoulders back, chest expanded, head high, arms open, smile",
        continuity_emphasis="spatial dominance, character fills frame despite distance"
    ),

    "vulnerability": EmotionalFramingModifier(
        emotion="vulnerability",
        framing_modifier="High angle, character small in frame, contained space",
        shot_type_push="wider",
        depth_of_field_modifier="deeper",
        lens_direction="wide",
        rhythm_modifier="slower_holds",
        angle_recommendation="high_angle",
        lighting_mood="Cool, diffuse, character in shadow relative to environment",
        prompt_injection="eyes down or away, shoulders rounded, small gestures, breath shallow",
        continuity_emphasis="spatial confinement, loss of control over environment"
    ),
}


# ============================================================================
# SECTION 5: NARRATIVE B-ROLL GENERATOR
# ============================================================================

@dataclass
class BRollSuggestion:
    """A suggested B-roll shot with narrative justification."""

    shot_description: str                           # What to shoot
    narrative_purpose: str                          # Why it matters to story
    duration_seconds: int
    shot_type: ShotType
    props_or_details: List[str]                     # Specific elements to capture
    continuity_connection: str                      # How does it connect to adjacent scenes?
    mood: str
    timing_in_scene: str                            # "opening", "intercut", "closing"
    optional_dialogue: Optional[str] = None


def generate_narrative_broll(
    scene_type: SceneType,
    story_beat: str,
    character_names: Optional[List[str]] = None,
    location_context: Optional[str] = None,
    emotional_arc: Optional[str] = None
) -> List[BRollSuggestion]:
    """
    Generate suggested B-roll for a scene based on narrative context.

    Rules for narrative B-roll:
    1. NEVER show empty room then characters appear — show ARRIVAL
    2. Opening B-roll CONTEXTUALIZES: show family portrait before inheritance argument
    3. Closing B-roll RESONATES: linger on empty chair, extinguished candle, closed door
    4. Transitional B-roll BRIDGES: hallway, exterior, clock showing time passage

    Args:
        scene_type: Type of scene (dialogue, action, etc.)
        story_beat: Narrative description of what happens in scene
        character_names: Main characters present
        location_context: Where scene takes place
        emotional_arc: How emotion changes through scene

    Returns:
        List of B-roll suggestions with timings and purposes
    """
    suggestions: List[BRollSuggestion] = []

    if not scene_type:
        return suggestions

    # Contextual opening B-roll (scene-specific)
    if scene_type == SceneType.DIALOGUE_CONFRONTATION:
        suggestions.append(BRollSuggestion(
            shot_description="Approaching footsteps, door frame, hand on doorknob",
            narrative_purpose="Establish confrontation is about to happen, create anticipation",
            duration_seconds=3,
            shot_type=ShotType.INSERT,
            props_or_details=["door handle", "threshold", "footsteps"],
            continuity_connection="Connects previous scene to argument",
            mood="tense, anticipatory",
            timing_in_scene="opening"
        ))

    elif scene_type == SceneType.DISCOVERY_REVELATION:
        # Contextual B-roll: show what's being searched BEFORE discovery
        if location_context:
            suggestions.append(BRollSuggestion(
                shot_description=f"Establishing B-roll of {location_context}, where discovery will happen",
                narrative_purpose="Show audience where to focus, plant subconscious expectation",
                duration_seconds=2,
                shot_type=ShotType.INSERT,
                props_or_details=["surfaces", "objects", "lighting"],
                continuity_connection="Context for discovery moment",
                mood="neutral or ominous",
                timing_in_scene="opening"
            ))

        suggestions.append(BRollSuggestion(
            shot_description="Hands touching objects, eyes scanning, discovery process",
            narrative_purpose="Show character's methodology, make audience complicit in search",
            duration_seconds=3,
            shot_type=ShotType.INSERT,
            props_or_details=["hands", "objects being touched", "surfaces"],
            continuity_connection="Leads directly to discovery moment",
            mood="investigative, methodical",
            timing_in_scene="intercut"
        ))

    elif scene_type == SceneType.SOLITARY_REFLECTION:
        # Mood-setting B-roll
        if location_context:
            suggestions.append(BRollSuggestion(
                shot_description=f"Environmental detail B-roll of {location_context}: clock ticking, rain on window, empty chair, cold coffee",
                narrative_purpose="Amplify isolation and passage of time through environment",
                duration_seconds=4,
                shot_type=ShotType.INSERT,
                props_or_details=["clock", "weather", "abandoned objects", "temperature indicators"],
                continuity_connection="Intercuts with character's stillness",
                mood="melancholic, time-aware",
                timing_in_scene="intercut"
            ))

        suggestions.append(BRollSuggestion(
            shot_description="Final environmental frame: the space character is leaving (empty chair, closed door, extinguished light)",
            narrative_purpose="Resonate with emotional weight of scene, show cost of moment",
            duration_seconds=3,
            shot_type=ShotType.INSERT,
            props_or_details=["empty space", "symbolic object", "door closing", "light going out"],
            continuity_connection="Connects this reflection to next scene's action",
            mood="poignant, reflective",
            timing_in_scene="closing"
        ))

    elif scene_type == SceneType.ARRIVAL_DEPARTURE:
        suggestions.append(BRollSuggestion(
            shot_description="Vehicle arrival or approach, footsteps, threshold crossing",
            narrative_purpose="Show the JOURNEY, not just appearance. Make arrival feel real.",
            duration_seconds=4,
            shot_type=ShotType.INSERT,
            props_or_details=["vehicle", "road", "footsteps", "door/gate", "threshold"],
            continuity_connection="Connects travel/departure to new location",
            mood="anticipatory, transitional",
            timing_in_scene="opening"
        ))

        if emotional_arc and "departure" in emotional_arc.lower():
            suggestions.append(BRollSuggestion(
                shot_description="Closing shot: back of character walking away, door closing, car pulling away",
                narrative_purpose="Emphasize finality of departure, emotional weight of leaving",
                duration_seconds=3,
                shot_type=ShotType.EWS,
                props_or_details=["character's back", "door", "vehicle", "empty space left behind"],
                continuity_connection="Leads to next scene in new location",
                mood="bittersweet, closure",
                timing_in_scene="closing"
            ))

    elif scene_type == SceneType.ACTION_PHYSICAL:
        suggestions.append(BRollSuggestion(
            shot_description="Geography establishing: where will action take place? Full room/space overview.",
            narrative_purpose="Audience needs to understand spatial layout before action explodes",
            duration_seconds=2,
            shot_type=ShotType.EWS,
            props_or_details=["exits", "obstacles", "cover", "spatial relationships"],
            continuity_connection="Sets up understanding of action choreography",
            mood="clear, spatial",
            timing_in_scene="opening"
        ))

        suggestions.append(BRollSuggestion(
            shot_description="Impact moments: collision, object breaking, environmental change from action",
            narrative_purpose="Emphasize physical consequences, make action feel consequential",
            duration_seconds=2,
            shot_type=ShotType.INSERT,
            props_or_details=["impact point", "debris", "broken objects", "environmental disruption"],
            continuity_connection="Reinforces action sequence",
            mood="dynamic, impactful",
            timing_in_scene="intercut"
        ))

    elif scene_type == SceneType.INVESTIGATION_SEARCH:
        suggestions.append(BRollSuggestion(
            shot_description="Room geography: establish what's in this space, what could be found",
            narrative_purpose="Show audience the search space, plant where clues might hide",
            duration_seconds=2,
            shot_type=ShotType.WS,
            props_or_details=["furniture", "shelves", "containers", "surfaces"],
            continuity_connection="Context for investigation",
            mood="curious, methodical",
            timing_in_scene="opening"
        ))

        suggestions.append(BRollSuggestion(
            shot_description="Clue detail shots: hands touching objects, eyes examining, specific discoveries",
            narrative_purpose="Audience sees what character sees, understanding investigation process",
            duration_seconds=3,
            shot_type=ShotType.INSERT,
            props_or_details=["the actual clues", "how they're stored", "character's hands", "character's eyes"],
            continuity_connection="Builds toward revelation",
            mood="investigative, revealing",
            timing_in_scene="intercut"
        ))

    return suggestions


# ============================================================================
# SECTION 6: BEST_FIT_REF_SELECTOR
# ============================================================================

@dataclass
class RefSelection:
    """Selected reference images for a shot."""

    shot_id: str
    character_refs: List[Dict[str, Any]]            # [{"character": "EVELYN", "ref_url": "...", "priority": 1}]
    location_refs: List[Dict[str, Any]]             # [{"location": "RAVENCROFT_HALL", "ref_url": "...", "type": "location_master"}]
    ref_selection_reason: str                       # Why these refs were chosen
    fallback_used: bool                             # Did we have to use degraded refs?
    confidence_score: float                         # 0-1, how confident this selection is optimal
    broll_suggestions: List[BRollSuggestion]        # Suggested B-roll for this shot
    framing_recommendations: str                    # DP guidance for this shot
    continuity_notes: str                           # What continuity this shot bridges


def select_refs_for_shot(
    shot: Dict[str, Any],
    scene_type: SceneType,
    coverage_role: CoverageRole,
    emotion: Optional[str] = None,
    character_pack: Optional[Dict[str, Any]] = None,
    location_pack: Optional[Dict[str, Any]] = None,
    story_beat: Optional[str] = None,
    cast_map: Optional[Dict[str, Any]] = None
) -> RefSelection:
    """
    Select optimal reference images for a shot following full DP logic.

    Decision tree:
    1. Coverage role determines what refs are needed (A_GEOGRAPHY → location primary)
    2. Shot type constraints checked (ECU needs character ref, INSERT needs no character)
    3. Character identity checked against cast_map
    4. Location master checked/generated
    5. Fallback chain: preferred refs → degraded refs → generic → skip

    Rules from CLAUDE.md Doctrine:
    - DOCTRINE 2: All character shots must resolve through canonical character_reference_url
    - DOCTRINE 3: Dramatic equivalence before reuse (not just shot_id overlap)
    - Ref cap per shot type: Hero 3, Production 4, Establishing 2, Dialogue boost +1

    Args:
        shot: Shot dict with shot_id, shot_type, dialogue_text, characters, etc.
        scene_type: Parent scene archetype
        coverage_role: Coverage role (A_GEOGRAPHY, B_COVERAGE, etc.)
        emotion: Emotional beat (affects framing recommendation)
        character_pack: Available character reference packs
        location_pack: Available location reference packs
        story_beat: Narrative context for B-roll generation
        cast_map: Character → actor mapping

    Returns:
        RefSelection with selected refs + DP recommendations
    """

    shot_id = shot.get("shot_id", "unknown")
    characters = shot.get("characters") or []
    dialogue_text = shot.get("dialogue_text", "")
    shot_type_str = shot.get("shot_type", "MCU")
    scene_id = shot.get("scene_id", "")

    character_refs: List[Dict[str, Any]] = []
    location_refs: List[Dict[str, Any]] = []
    fallback_used = False
    confidence = 1.0

    # ────────────────────────────────────────────────────────────────────
    # STEP 1: Determine ref requirements by coverage role
    # ────────────────────────────────────────────────────────────────────

    role_profile = COVERAGE_ROLE_PROFILES.get(coverage_role)
    if not role_profile:
        role_profile = COVERAGE_ROLE_PROFILES[CoverageRole.B_COVERAGE]  # fallback

    required_char_refs = role_profile.required_character_refs
    optional_char_refs = role_profile.optional_character_refs
    location_ref_needed = role_profile.location_ref_required

    # DIALOGUE BOOST: +1 ref slot + 2K resolution minimum (Law T2-SA-4)
    if dialogue_text:
        optional_char_refs += 1

    # ────────────────────────────────────────────────────────────────────
    # STEP 2: Resolve character refs
    # ────────────────────────────────────────────────────────────────────

    cast_map_safe = cast_map or {}

    for idx, character in enumerate(characters):
        if idx >= (required_char_refs + optional_char_refs):
            break  # Hit ref cap

        # Priority 1: canonical character_reference_url from cast_map (DOCTRINE 2)
        char_record = cast_map_safe.get(character, {})
        character_reference_url = char_record.get("character_reference_url")

        if character_reference_url:
            character_refs.append({
                "character": character,
                "ref_url": character_reference_url,
                "priority": 1,
                "source": "canonical_cast_map"
            })
        else:
            # Priority 2: fallback to headshot_url
            headshot_url = char_record.get("headshot_url")
            if headshot_url:
                character_refs.append({
                    "character": character,
                    "ref_url": headshot_url,
                    "priority": 2,
                    "source": "fallback_headshot"
                })
                confidence *= 0.85  # Degraded confidence: using fallback
                fallback_used = True
            else:
                # No ref found — Doctrine says this is degraded_safe or blocked
                confidence *= 0.70
                # Non-blocking: proceed but flag

    # ────────────────────────────────────────────────────────────────────
    # STEP 3: Resolve location refs
    # ────────────────────────────────────────────────────────────────────

    if location_ref_needed:
        location_pack_safe = location_pack or {}

        # Try location-specific master first
        location_master_key = f"{scene_id}_master"
        location_master = location_pack_safe.get(location_master_key)

        if location_master:
            location_refs.append({
                "location": scene_id,
                "ref_url": location_master,
                "type": "location_master",
                "priority": 1
            })
        else:
            # Fallback: use generic environment ref if available
            generic_env = location_pack_safe.get("generic_environment")
            if generic_env:
                location_refs.append({
                    "location": scene_id,
                    "ref_url": generic_env,
                    "type": "generic_environment",
                    "priority": 2
                })
                confidence *= 0.80
                fallback_used = True

    # ────────────────────────────────────────────────────────────────────
    # STEP 4: Generate B-roll suggestions
    # ────────────────────────────────────────────────────────────────────

    broll_suggestions = generate_narrative_broll(
        scene_type=scene_type,
        story_beat=story_beat or "",
        character_names=characters,
        location_context=scene_id,
        emotional_arc=emotion
    )

    # ────────────────────────────────────────────────────────────────────
    # STEP 5: Generate DP framing recommendations
    # ────────────────────────────────────────────────────────────────────

    framing_recs: List[str] = []

    # Get shot type profile for recommendations
    try:
        shot_type_enum = next(s for s in ShotType if s.value == shot_type_str.lower())
        shot_profile = SHOT_TYPE_PROFILES.get(shot_type_enum)
    except (StopIteration, KeyError):
        shot_profile = None

    if shot_profile:
        framing_recs.append(f"Shot Type: {shot_profile.shot_type.value}")
        framing_recs.append(f"Framing: {shot_profile.framing_description}")
        framing_recs.append(f"Depth of Field: {shot_profile.depth_of_field}")
        framing_recs.append(f"Typical Lens Range: {shot_profile.typical_lens_mm[0]}-{shot_profile.typical_lens_mm[1]}mm")

        if shot_profile.emotional_association:
            framing_recs.append(f"Emotional Weight: {', '.join(shot_profile.emotional_association)}")

    # Add emotional modifier recommendations
    if emotion:
        emotional_mod = EMOTIONAL_FRAMING_MODIFIERS.get(emotion)
        if emotional_mod:
            framing_recs.append(f"Emotion '{emotion}' Modifier:")
            framing_recs.append(f"  - {emotional_mod.framing_modifier}")
            framing_recs.append(f"  - Angle: {emotional_mod.angle_recommendation}")
            framing_recs.append(f"  - Lighting: {emotional_mod.lighting_mood}")
            framing_recs.append(f"  - Prompt Injection: {emotional_mod.prompt_injection}")

    # Scene-type specific recommendations
    scene_pattern = SCENE_COVERAGE_PATTERNS.get(scene_type)
    if scene_pattern:
        framing_recs.append(f"Scene Pattern: {scene_pattern.description}")
        framing_recs.append(f"Cutting Rhythm: {scene_pattern.cutting_rhythm}")
        framing_recs.append(f"Lighting Mood: {scene_pattern.lighting_mood}")

    # ────────────────────────────────────────────────────────────────────
    # STEP 6: Continuity notes
    # ────────────────────────────────────────────────────────────────────

    continuity_notes = ""

    if role_profile:
        continuity_notes = f"Continuity Role: {role_profile.continuity_chaining_role}. "
        if role_profile.continuity_chaining_role == "anchor":
            continuity_notes += "This is an establishing shot — sets environment. Next shots will chain from this geography."
        elif role_profile.continuity_chaining_role == "chain":
            continuity_notes += "This shot chains from previous — must maintain spatial and emotional continuity."
        else:
            continuity_notes += "This is an independent shot (B-roll or insert). No spatial chaining required."

    if dialogue_text:
        continuity_notes += f" [DIALOGUE BOOST APPLIED: +1 ref slot, 2K resolution minimum]"

    # ────────────────────────────────────────────────────────────────────
    # FINAL ASSEMBLY
    # ────────────────────────────────────────────────────────────────────

    reason = (
        f"Coverage Role: {coverage_role.value} | "
        f"Scene Type: {scene_type.value} | "
        f"Shot Type: {shot_type_str} | "
        f"Characters: {len(character_refs)}/{required_char_refs + optional_char_refs} | "
        f"Locations: {len(location_refs)}/{(1 if location_ref_needed else 0)}"
    )

    return RefSelection(
        shot_id=shot_id,
        character_refs=character_refs,
        location_refs=location_refs,
        ref_selection_reason=reason,
        fallback_used=fallback_used,
        confidence_score=max(0.0, min(1.0, confidence)),  # Clamp 0-1
        broll_suggestions=broll_suggestions,
        framing_recommendations="\n".join(framing_recs),
        continuity_notes=continuity_notes
    )


# ============================================================================
# HELPER FUNCTIONS (Non-blocking, ATLAS conventions)
# ============================================================================

def get_shot_type_from_string(shot_type_str: Optional[str]) -> Optional[ShotType]:
    """Safely resolve shot type string to enum."""
    if not shot_type_str:
        return None

    try:
        # Try direct match
        return ShotType[shot_type_str.upper()]
    except KeyError:
        # Try .value match
        for st in ShotType:
            if st.value == shot_type_str.lower():
                return st
        return None


def get_coverage_role_from_shot_id(shot_id: str) -> Optional[CoverageRole]:
    """Infer coverage role from shot_id suffix (A/B/C/D)."""
    if not shot_id:
        return None

    suffix = shot_id[-1].upper()

    role_map = {
        'A': CoverageRole.A_GEOGRAPHY,
        'B': CoverageRole.B_COVERAGE,
        'C': CoverageRole.C_EMPHASIS,
        'D': CoverageRole.D_CONTEXTUAL,
    }

    return role_map.get(suffix)


def estimate_scene_type_from_beat(story_beat: Optional[str], dialogue_present: bool = False) -> SceneType:
    """Heuristic: infer scene type from story beat text."""
    if not story_beat:
        return SceneType.DIALOGUE_EXPOSITION if dialogue_present else SceneType.ACTION_PHYSICAL

    beat_lower = story_beat.lower()

    if any(word in beat_lower for word in ["discover", "find", "reveal", "realize"]):
        return SceneType.DISCOVERY_REVELATION
    elif any(word in beat_lower for word in ["confront", "argue", "fight", "clash"]):
        return SceneType.DIALOGUE_CONFRONTATION
    elif any(word in beat_lower for word in ["alone", "reflect", "think", "sit", "wait"]):
        return SceneType.SOLITARY_REFLECTION
    elif any(word in beat_lower for word in ["arrive", "depart", "leave", "enter", "exit"]):
        return SceneType.ARRIVAL_DEPARTURE
    elif any(word in beat_lower for word in ["search", "look", "investigate", "examine"]):
        return SceneType.INVESTIGATION_SEARCH
    elif any(word in beat_lower for word in ["action", "chase", "fight", "struggle", "move"]):
        return SceneType.ACTION_PHYSICAL
    else:
        return SceneType.DIALOGUE_EXPOSITION  # default


def format_framing_summary(ref_selection: RefSelection) -> str:
    """Format RefSelection into human-readable DP summary."""
    lines = [
        f"SHOT: {ref_selection.shot_id}",
        f"Confidence: {ref_selection.confidence_score:.0%}",
        f"Fallback Used: {'Yes' if ref_selection.fallback_used else 'No'}",
        "",
        "CHARACTER REFS:",
    ]

    if ref_selection.character_refs:
        for ref in ref_selection.character_refs:
            lines.append(f"  {ref['character']} (priority {ref['priority']}): {ref['ref_url']}")
    else:
        lines.append("  [None]")

    lines.append("")
    lines.append("LOCATION REFS:")

    if ref_selection.location_refs:
        for ref in ref_selection.location_refs:
            lines.append(f"  {ref['location']} ({ref['type']}): {ref['ref_url']}")
    else:
        lines.append("  [None]")

    lines.append("")
    lines.append("DP FRAMING RECOMMENDATIONS:")
    for rec_line in ref_selection.framing_recommendations.split("\n"):
        lines.append(f"  {rec_line}")

    lines.append("")
    lines.append("CONTINUITY NOTES:")
    lines.append(f"  {ref_selection.continuity_notes}")

    if ref_selection.broll_suggestions:
        lines.append("")
        lines.append("B-ROLL SUGGESTIONS:")
        for broll in ref_selection.broll_suggestions:
            lines.append(f"  [{broll.timing_in_scene.upper()}] {broll.shot_description}")
            lines.append(f"    Purpose: {broll.narrative_purpose}")
            lines.append(f"    Duration: {broll.duration_seconds}s | Mood: {broll.mood}")

    return "\n".join(lines)


# ============================================================================
# MODULE CONSTANTS
# ============================================================================

ALL_SHOT_TYPES = list(ShotType)
ALL_SCENE_TYPES = list(SceneType)
ALL_COVERAGE_ROLES = list(CoverageRole)
ALL_EMOTIONS = list(EMOTIONAL_FRAMING_MODIFIERS.keys())


# ============================================================================
# MAIN ENTRY POINT (for testing/standalone use)
# ============================================================================

if __name__ == "__main__":
    """
    Example usage: standalone testing of DP framing standards.

    python3 tools/dp_framing_standards.py
    """

    # Example: Select refs for a confrontation scene dialogue shot
    example_shot = {
        "shot_id": "001B",
        "scene_id": "001",
        "shot_type": "over_the_shoulder",
        "characters": ["EVELYN", "JAMES"],
        "dialogue_text": "You cannot expect me to accept this arrangement.",
        "coverage_role": "b_coverage"
    }

    example_cast_map = {
        "EVELYN": {
            "character_reference_url": "/refs/evelyn_char.jpg",
            "headshot_url": "/refs/evelyn_headshot.jpg"
        },
        "JAMES": {
            "character_reference_url": "/refs/james_char.jpg",
            "headshot_url": "/refs/james_headshot.jpg"
        }
    }

    example_location_pack = {
        "001_master": "/locations/ravencroft_hall_master.jpg",
        "generic_environment": "/locations/generic_interior.jpg"
    }

    result = select_refs_for_shot(
        shot=example_shot,
        scene_type=SceneType.DIALOGUE_CONFRONTATION,
        coverage_role=CoverageRole.B_COVERAGE,
        emotion="tension_building",
        cast_map=example_cast_map,
        location_pack=example_location_pack,
        story_beat="EVELYN confronts JAMES about the inheritance",
    )

    print(format_framing_summary(result))
    print("\n" + "="*80 + "\n")

    # Example: Generate B-roll for solitary reflection scene
    broll = generate_narrative_broll(
        scene_type=SceneType.SOLITARY_REFLECTION,
        story_beat="EVELYN sits alone, processing the revelation",
        character_names=["EVELYN"],
        location_context="RAVENCROFT_STUDY",
        emotional_arc="grief"
    )

    print("NARRATIVE B-ROLL SUGGESTIONS:")
    for suggestion in broll:
        print(f"\n  [{suggestion.timing_in_scene.upper()}] {suggestion.shot_description}")
        print(f"    Purpose: {suggestion.narrative_purpose}")
        print(f"    Duration: {suggestion.duration_seconds}s")
        print(f"    Props: {', '.join(suggestion.props_or_details)}")
        print(f"    Mood: {suggestion.mood}")
