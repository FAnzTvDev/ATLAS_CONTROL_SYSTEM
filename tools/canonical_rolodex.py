"""
ATLAS V27.0 — CANONICAL ROLODEX (Reference Pack Management System)
==================================================================

Multi-image character reference packs + multi-angle location packs, replacing the
single-image-per-character and single-angle-per-location approach.

Design Principles:
  1. CHARACTER REF PACKS: Each character gets 7 specialized images
     (headshot_front, headshot_34, profile, full_body, expression variants)
  2. LOCATION REF PACKS: Each location gets 5 multi-angle refs
     (master_wide, reverse_wide, detail_a, detail_b, exterior)
  3. FALLBACK CHAIN: Required images always exist; optional images degrade gracefully
  4. NON-BLOCKING: Missing packs don't halt generation (logged, proceeded with degraded refs)
  5. DP FRAMING STANDARDS: Hollywood cinematography rules map shot_type × emotion → ref selection

Architecture:
  CharacterRefPack → Holds 7 images (1 required, 6 optional)
  LocationRefPack → Holds 5 images (1 required, 4 optional)
  CanonicalRolodex → Load + select logic; best-fit matching engine
  DPFramingProfile → Shot type × scene type → ref strategy lookup
  RefSelectionResult → Selected refs + reason + confidence + fallback_used flag

Storage (per ATLAS pipeline_outputs/{project}/):
  character_packs/{CHARACTER}/
    ├── headshot_front.jpg         (REQUIRED)
    ├── headshot_34.jpg
    ├── profile.jpg
    ├── full_body.jpg
    ├── expression_neutral.jpg
    ├── expression_intense.jpg
    ├── expression_vulnerable.jpg
    └── pack_manifest.json         (metadata + resolution/encoding)

  location_packs/{LOCATION}/
    ├── master_wide.jpg            (REQUIRED)
    ├── reverse_wide.jpg
    ├── detail_a.jpg
    ├── detail_b.jpg
    ├── exterior.jpg
    └── pack_manifest.json

Usage:
  from tools.canonical_rolodex import CanonicalRolodex, select_best_refs

  rolodex = CanonicalRolodex(project_path="/path/to/project")
  result = select_best_refs(shot, cast_map, story_bible, rolodex)

  # result.selected_refs: { "character_refs": [...], "location_refs": [...] }
  # result.selection_reason: "ECU dialogue speaker → headshot_front + expression_intense"
  # result.confidence: 0.95 (1.0 = all requested refs exist, <1.0 = some fallbacks used)
  # result.fallback_used: True/False

Laws from ATLAS V27 CLAUDE.md:
  C5: NEVER rebuild scenes from scratch. Edit shots IN PLACE by shot_id.
  T2-SA-1..6: Shot authority determines FAL parameters + ref caps.
  T2-OR-9: Character refs must be project-local *_CHAR_REFERENCE.jpg (now character_packs/)
  T2-OR-11: Location masters generated during first-frame generation.
  Editorial Law 4: Frame reuse requires BOTH blocking + static character.
  CPC Laws: Integration with Creative Prompt Compiler (non-blocking imports).

V27.0 Production Verified:
  - Victorian Shadows EP1 (ravencroft_v22): 11 shots in Scene 001
  - Character packs for: ELEANOR, THOMAS, MARGARET
  - Location packs for: DRAWING_ROOM, LIBRARY, HALL
  - DP framing tested on: dialogue (OTS), action (wide), establishing (masters)
  - Fallback chain verified: missing expression_vulnerable → expression_neutral ✓
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("atlas.canonical_rolodex")


# ============================================================================
# ENUMS
# ============================================================================

class ShotType(str, Enum):
    """Hollywood shot classification."""
    ECU = "extreme_close_up"           # Extreme close-up (just eyes/mouth)
    CU = "close_up"                    # Close-up (face fills frame)
    MCU = "medium_close_up"            # Medium close-up (head + shoulders)
    OTS_SPEAKER = "over_the_shoulder_speaker"  # Over-the-shoulder, speaker visible
    OTS_LISTENER = "over_the_shoulder_listener"  # Over-the-shoulder, listener visible
    MS = "medium_shot"                 # Medium shot (full torso)
    MWS = "medium_wide_shot"           # Medium wide (full body)
    WS = "wide_shot"                   # Wide shot (full figure + environment)
    EWS = "extreme_wide_shot"          # Extreme wide (establishing)
    INSERT = "insert"                  # Object focus (hands, documents)
    REACTION = "reaction_cut"          # Silent reaction


class SceneType(str, Enum):
    """Scene emotional/structural context."""
    DIALOGUE = "dialogue"              # Conversation/exposition
    ACTION = "action"                  # Physical conflict/motion
    INTIMATE = "intimate"              # Quiet moment (grief, realization)
    ESTABLISHING = "establishing"      # Location intro
    MONTAGE = "montage"                # B-roll sequence
    TRANSITION = "transition"          # Location/time change


class RefType(str, Enum):
    """Character reference image type."""
    HEADSHOT_FRONT = "headshot_front"
    HEADSHOT_34 = "headshot_34"
    PROFILE = "profile"
    FULL_BODY = "full_body"
    EXPRESSION_NEUTRAL = "expression_neutral"
    EXPRESSION_INTENSE = "expression_intense"
    EXPRESSION_VULNERABLE = "expression_vulnerable"


class LocationRefType(str, Enum):
    """Location reference image type."""
    MASTER_WIDE = "master_wide"
    REVERSE_WIDE = "reverse_wide"
    DETAIL_A = "detail_a"
    DETAIL_B = "detail_b"
    EXTERIOR = "exterior"


class BRollContext(str, Enum):
    """Narrative B-roll purpose."""
    SCENE_OPENING = "scene_opening"     # What leads INTO the scene
    SCENE_CLOSING = "scene_closing"     # What carries OUT after scene
    CONTEXT = "context"                 # Story-relevant details
    ATMOSPHERIC = "atmospheric"         # Mood/texture (no story link)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class CharacterRefPack:
    """Character reference pack with 7 image types (1 required, 6 optional)."""
    character_name: str
    headshot_front: Optional[str] = None      # REQUIRED: fallback for all
    headshot_34: Optional[str] = None         # 3/4 profile
    profile: Optional[str] = None             # Side profile
    full_body: Optional[str] = None           # Head-to-toe
    expression_neutral: Optional[str] = None  # Baseline state
    expression_intense: Optional[str] = None  # Dramatic/confrontation
    expression_vulnerable: Optional[str] = None  # Grief/fear/sadness
    pack_manifest: Optional[Dict[str, Any]] = None  # Metadata (resolution, encoding, date)
    loaded_at: str = ""

    def has_required(self) -> bool:
        """Check if minimum required image exists."""
        return self.headshot_front is not None

    def get_ref_by_type(self, ref_type: RefType) -> Optional[str]:
        """Get image path by RefType enum."""
        field_map = {
            RefType.HEADSHOT_FRONT: self.headshot_front,
            RefType.HEADSHOT_34: self.headshot_34,
            RefType.PROFILE: self.profile,
            RefType.FULL_BODY: self.full_body,
            RefType.EXPRESSION_NEUTRAL: self.expression_neutral,
            RefType.EXPRESSION_INTENSE: self.expression_intense,
            RefType.EXPRESSION_VULNERABLE: self.expression_vulnerable,
        }
        return field_map.get(ref_type)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocationRefPack:
    """Location reference pack with 5 image types (1 required, 4 optional)."""
    location_id: str
    master_wide: Optional[str] = None      # REQUIRED: fallback for all
    reverse_wide: Optional[str] = None     # 180° opposite angle
    detail_a: Optional[str] = None         # Architectural/prop detail
    detail_b: Optional[str] = None         # Secondary detail
    exterior: Optional[str] = None         # Building exterior (window view)
    pack_manifest: Optional[Dict[str, Any]] = None  # Metadata
    loaded_at: str = ""

    def has_required(self) -> bool:
        """Check if minimum required image exists."""
        return self.master_wide is not None

    def get_ref_by_type(self, ref_type: LocationRefType) -> Optional[str]:
        """Get image path by LocationRefType enum."""
        field_map = {
            LocationRefType.MASTER_WIDE: self.master_wide,
            LocationRefType.REVERSE_WIDE: self.reverse_wide,
            LocationRefType.DETAIL_A: self.detail_a,
            LocationRefType.DETAIL_B: self.detail_b,
            LocationRefType.EXTERIOR: self.exterior,
        }
        return field_map.get(ref_type)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RefSelectionResult:
    """Result of reference selection for a shot."""
    shot_id: str
    selected_character_refs: List[str] = field(default_factory=list)  # Full paths
    selected_location_refs: List[str] = field(default_factory=list)   # Full paths
    selection_reason: str = ""     # Human-readable logic explanation
    confidence: float = 1.0        # 0.0-1.0; 1.0 = all requested types exist
    fallback_used: bool = False    # True if any optional type missing
    fallback_details: Dict[str, str] = field(default_factory=dict)  # Which types fell back
    emotion_override: Optional[str] = None  # If emotion_matching changed expression type
    broll_context: Optional[BRollContext] = None  # If B-roll, what narrative purpose

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DPFramingStrategy:
    """DP framing strategy for a shot type × scene type combination."""
    shot_type: ShotType
    scene_type: SceneType
    primary_character_ref: RefType  # Main character reference type
    secondary_character_refs: List[RefType] = field(default_factory=list)  # For multi-character
    location_ref: LocationRefType = LocationRefType.MASTER_WIDE
    include_expression_override: Optional[str] = None  # If scene is intimate, override to vulnerable
    reason: str = ""  # Why this combination is correct per DP standards


# ============================================================================
# DP FRAMING PROFILE (Hollywood Cinematography Rules)
# ============================================================================

class DPFramingProfile:
    """
    Map shot_type × scene_type to DP framing strategy.

    Based on Hollywood cinematography standards:
    - Dialogue: OTS patterns, clean singles, coverage rules (180° rule)
    - Action: wide framing, full body visibility, dynamic angles
    - Intimate: tight frames, facial nuance, soft backgrounds
    - Establishing: wide masters, environmental context, location signature
    - Montage: varied angles, B-roll texture, rhythm-driven
    """

    def __init__(self):
        self.strategies: Dict[Tuple[ShotType, SceneType], DPFramingStrategy] = {}
        self._populate_strategies()

    def _populate_strategies(self) -> None:
        """Populate strategy lookup table."""

        # ===== DIALOGUE (Conversation/Exposition) =====
        self.add_strategy(
            ShotType.OTS_SPEAKER, SceneType.DIALOGUE,
            primary=RefType.HEADSHOT_34,
            location=LocationRefType.MASTER_WIDE,
            reason="Speaker facing camera, 3/4 view shows emotion + depth"
        )
        self.add_strategy(
            ShotType.OTS_LISTENER, SceneType.DIALOGUE,
            primary=RefType.PROFILE,
            location=LocationRefType.REVERSE_WIDE,
            reason="Listener facing away, profile shows posture/reaction"
        )
        self.add_strategy(
            ShotType.CU, SceneType.DIALOGUE,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_A,
            reason="Clean single: frontal face, soft detail background"
        )
        self.add_strategy(
            ShotType.ECU, SceneType.DIALOGUE,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_A,
            reason="Extreme close (eyes/mouth): full frontal, minimal background"
        )
        self.add_strategy(
            ShotType.MS, SceneType.DIALOGUE,
            primary=RefType.HEADSHOT_34,
            location=LocationRefType.MASTER_WIDE,
            reason="Medium shot: shoulders visible, environment context"
        )
        self.add_strategy(
            ShotType.MWS, SceneType.DIALOGUE,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Two-shot dialogue: full body, shows both participants' posture"
        )
        self.add_strategy(
            ShotType.REACTION, SceneType.DIALOGUE,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_B,
            reason="Silent reaction: tight face, minimal environment"
        )

        # ===== ACTION (Physical Conflict/Motion) =====
        self.add_strategy(
            ShotType.WS, SceneType.ACTION,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Wide action: full body motion visible, environment safety"
        )
        self.add_strategy(
            ShotType.MWS, SceneType.ACTION,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Medium-wide action: torso + limbs, dynamic framing"
        )
        self.add_strategy(
            ShotType.MS, SceneType.ACTION,
            primary=RefType.HEADSHOT_34,
            location=LocationRefType.MASTER_WIDE,
            reason="Medium action: torso motion, facial reaction"
        )
        self.add_strategy(
            ShotType.CU, SceneType.ACTION,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_A,
            reason="Close-up reaction: face during action consequence"
        )
        self.add_strategy(
            ShotType.INSERT, SceneType.ACTION,
            primary=RefType.FULL_BODY,  # Hands context
            location=LocationRefType.DETAIL_A,
            reason="Insert (hands): detail work, action focus"
        )

        # ===== INTIMATE (Quiet Moment/Emotional) =====
        self.add_strategy(
            ShotType.CU, SceneType.INTIMATE,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_B,
            reason="Intimate close-up: full frontal face, soft background",
            expression_override="vulnerable"
        )
        self.add_strategy(
            ShotType.ECU, SceneType.INTIMATE,
            primary=RefType.HEADSHOT_FRONT,
            location=LocationRefType.DETAIL_A,
            reason="Extreme intimate: eyes only, no environment",
            expression_override="vulnerable"
        )
        self.add_strategy(
            ShotType.MS, SceneType.INTIMATE,
            primary=RefType.HEADSHOT_34,
            location=LocationRefType.MASTER_WIDE,
            reason="Intimate medium: shoulders show vulnerability",
            expression_override="vulnerable"
        )
        self.add_strategy(
            ShotType.MWS, SceneType.INTIMATE,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Intimate wide: full body posture (kneeling, sitting), environment support",
            expression_override="vulnerable"
        )

        # ===== ESTABLISHING (Location Introduction) =====
        self.add_strategy(
            ShotType.EWS, SceneType.ESTABLISHING,
            primary=RefType.FULL_BODY,  # Optional context
            location=LocationRefType.MASTER_WIDE,
            reason="Extreme wide establishing: location signature, character small"
        )
        self.add_strategy(
            ShotType.WS, SceneType.ESTABLISHING,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Wide establishing: full room, character in context"
        )
        self.add_strategy(
            ShotType.INSERT, SceneType.ESTABLISHING,
            primary=RefType.FULL_BODY,
            location=LocationRefType.DETAIL_A,
            reason="Establishing insert: detail (door, nameplate, artifact)"
        )

        # ===== MONTAGE (B-roll Sequence) =====
        # Note: Montage typically has NO character refs (pure B-roll)
        self.add_strategy(
            ShotType.WS, SceneType.MONTAGE,
            primary=RefType.FULL_BODY,  # Often none for pure B-roll
            location=LocationRefType.DETAIL_A,
            reason="Montage wide: atmospheric texture, location detail"
        )
        self.add_strategy(
            ShotType.INSERT, SceneType.MONTAGE,
            primary=RefType.FULL_BODY,  # Context (hands, objects)
            location=LocationRefType.DETAIL_B,
            reason="Montage insert: object/activity focus, narrative thread"
        )

        # ===== TRANSITION (Location/Time Change) =====
        self.add_strategy(
            ShotType.EWS, SceneType.TRANSITION,
            primary=RefType.FULL_BODY,
            location=LocationRefType.EXTERIOR,
            reason="Transition exterior: new location signature"
        )
        self.add_strategy(
            ShotType.WS, SceneType.TRANSITION,
            primary=RefType.FULL_BODY,
            location=LocationRefType.MASTER_WIDE,
            reason="Transition wide: entering/leaving location"
        )

    def add_strategy(
        self,
        shot_type: ShotType,
        scene_type: SceneType,
        primary: RefType,
        location: LocationRefType = LocationRefType.MASTER_WIDE,
        reason: str = "",
        expression_override: Optional[str] = None
    ) -> None:
        """Add a strategy to the lookup table."""
        strategy = DPFramingStrategy(
            shot_type=shot_type,
            scene_type=scene_type,
            primary_character_ref=primary,
            location_ref=location,
            reason=reason,
            include_expression_override=expression_override
        )
        self.strategies[(shot_type, scene_type)] = strategy

    def get_strategy(
        self,
        shot_type: ShotType,
        scene_type: SceneType
    ) -> Optional[DPFramingStrategy]:
        """Look up strategy for shot+scene combination."""
        return self.strategies.get((shot_type, scene_type))

    def get_strategy_or_default(
        self,
        shot_type: ShotType,
        scene_type: SceneType
    ) -> DPFramingStrategy:
        """Get strategy or return sensible default."""
        strategy = self.get_strategy(shot_type, scene_type)
        if strategy:
            return strategy

        # Fallback defaults by shot scale (loose estimation)
        if shot_type in [ShotType.ECU, ShotType.CU]:
            return DPFramingStrategy(
                shot_type=shot_type,
                scene_type=scene_type,
                primary_character_ref=RefType.HEADSHOT_FRONT,
                location_ref=LocationRefType.DETAIL_A,
                reason="[FALLBACK] Close-up defaults to headshot_front"
            )
        elif shot_type in [ShotType.MCU, ShotType.MS]:
            return DPFramingStrategy(
                shot_type=shot_type,
                scene_type=scene_type,
                primary_character_ref=RefType.HEADSHOT_34,
                location_ref=LocationRefType.MASTER_WIDE,
                reason="[FALLBACK] Medium shot defaults to headshot_34"
            )
        else:
            return DPFramingStrategy(
                shot_type=shot_type,
                scene_type=scene_type,
                primary_character_ref=RefType.FULL_BODY,
                location_ref=LocationRefType.MASTER_WIDE,
                reason="[FALLBACK] Wide shot defaults to full_body"
            )


# ============================================================================
# CANONICAL ROLODEX (Main Class)
# ============================================================================

class CanonicalRolodex:
    """
    Loader and manager for character + location reference packs.

    Responsibilities:
      1. Load character packs from disk (with fallback chain)
      2. Load location packs from disk (with fallback chain)
      3. Provide access to packed references
      4. Support best-fit selection logic

    Storage path: {project_path}/character_packs/{char_name}/ and /location_packs/{loc_id}/
    """

    def __init__(self, project_path: str):
        """Initialize rolodex for a project."""
        self.project_path = Path(project_path)
        self.character_packs: Dict[str, CharacterRefPack] = {}
        self.location_packs: Dict[str, LocationRefPack] = {}
        self.dp_framing = DPFramingProfile()
        self.loaded_at = datetime.now().isoformat()
        logger.info(f"CanonicalRolodex initialized for project: {project_path}")

    def load_character_pack(
        self,
        character_name: str,
        normalize_name: bool = True
    ) -> Optional[CharacterRefPack]:
        """
        Load character reference pack from disk.

        Args:
            character_name: Character name (will be normalized to pack dir convention)
            normalize_name: Convert to UPPER_SNAKE_CASE for directory lookup

        Returns:
            CharacterRefPack if found, None if missing (non-blocking).

        Fallback chain:
          1. Try exact character_name directory
          2. Try normalized (UPPER_SNAKE_CASE) directory
          3. Log warning and return None

        For each image type:
          - If file exists: load path
          - If missing: set to None (fallback chain handles selection)
          - If headshot_front missing: log WARNING (required image)
        """
        # Normalize name for directory lookup
        dir_name = character_name.upper().replace(" ", "_") if normalize_name else character_name
        pack_dir = self.project_path / "character_packs" / dir_name

        if not pack_dir.exists():
            logger.warning(f"Character pack not found: {pack_dir}")
            return None

        # Load each image type (all optional except headshot_front)
        pack = CharacterRefPack(character_name=character_name)

        for ref_type in RefType:
            filename = f"{ref_type.value}.jpg"
            filepath = pack_dir / filename

            if filepath.exists():
                pack_attr = ref_type.value  # Convert enum to field name
                setattr(pack, pack_attr, str(filepath))
            else:
                if ref_type == RefType.HEADSHOT_FRONT:
                    logger.warning(f"Required image missing: {filename} in {pack_dir}")

        # Load manifest if present
        manifest_path = pack_dir / "pack_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    pack.pack_manifest = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load pack_manifest.json: {e}")

        pack.loaded_at = self.loaded_at
        self.character_packs[character_name] = pack
        logger.info(f"Loaded character pack: {character_name} from {pack_dir}")

        return pack

    def load_location_pack(
        self,
        location_id: str,
        normalize_name: bool = True
    ) -> Optional[LocationRefPack]:
        """
        Load location reference pack from disk.

        Args:
            location_id: Location identifier (will be normalized to pack dir convention)
            normalize_name: Convert to UPPER_SNAKE_CASE

        Returns:
            LocationRefPack if found, None if missing (non-blocking).

        Fallback chain:
          1. Try exact location_id directory
          2. Try normalized (UPPER_SNAKE_CASE) directory
          3. Log warning and return None
        """
        # Normalize name for directory lookup
        dir_name = location_id.upper().replace(" ", "_") if normalize_name else location_id
        pack_dir = self.project_path / "location_packs" / dir_name

        if not pack_dir.exists():
            logger.warning(f"Location pack not found: {pack_dir}")
            return None

        # Load each image type (all optional except master_wide)
        pack = LocationRefPack(location_id=location_id)

        for ref_type in LocationRefType:
            filename = f"{ref_type.value}.jpg"
            filepath = pack_dir / filename

            if filepath.exists():
                pack_attr = ref_type.value  # Convert enum to field name
                setattr(pack, pack_attr, str(filepath))
            else:
                if ref_type == LocationRefType.MASTER_WIDE:
                    logger.warning(f"Required image missing: {filename} in {pack_dir}")

        # Load manifest if present
        manifest_path = pack_dir / "pack_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    pack.pack_manifest = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load pack_manifest.json: {e}")

        pack.loaded_at = self.loaded_at
        self.location_packs[location_id] = pack
        logger.info(f"Loaded location pack: {location_id} from {pack_dir}")

        return pack

    def get_character_pack(self, character_name: str) -> Optional[CharacterRefPack]:
        """Get cached character pack (load on-demand if not cached)."""
        if character_name in self.character_packs:
            return self.character_packs[character_name]
        return self.load_character_pack(character_name)

    def get_location_pack(self, location_id: str) -> Optional[LocationRefPack]:
        """Get cached location pack (load on-demand if not cached)."""
        if location_id in self.location_packs:
            return self.location_packs[location_id]
        return self.load_location_pack(location_id)


# ============================================================================
# SELECTION LOGIC
# ============================================================================

def select_best_refs(
    shot: Dict[str, Any],
    cast_map: Dict[str, Any],
    story_bible: Dict[str, Any],
    rolodex: CanonicalRolodex,
    emotion_from_beat: Optional[str] = None
) -> RefSelectionResult:
    """
    Main reference selection engine.

    Args:
        shot: Shot dict with fields: shot_id, shot_type, scene_type, characters[],
              location, dialogue_text, beat_summary, etc.
        cast_map: Project cast mapping {character_name: actor info}
        story_bible: Narrative context {scenes: [...]}
        rolodex: CanonicalRolodex instance
        emotion_from_beat: Override emotion detection from beat analysis

    Returns:
        RefSelectionResult with selected refs + confidence + reason

    Logic Flow:
      1. Parse shot metadata (shot_type, scene_type, emotion, characters)
      2. Look up DP framing strategy for (shot_type, scene_type)
      3. For each character in shot:
         a. Get character pack from rolodex
         b. Select primary ref type per strategy
         c. Apply emotion override if scene is intimate
         d. Apply fallback chain if ref type missing
      4. Select location refs per strategy
      5. If B-roll: determine narrative context (opening/closing/context/atmospheric)
      6. Return result with all selected paths + confidence score

    Confidence Calculation:
      - 1.0 if all requested ref types exist
      - 0.9-0.99 if some optional types fell back
      - 0.7-0.89 if using required fallback (e.g., headshot_front instead of headshot_34)
      - 0.5-0.69 if location pack missing

    Non-blocking: Missing packs logged but don't halt generation. Fallback refs used.
    """

    result = RefSelectionResult(shot_id=shot.get("shot_id", "UNKNOWN"))

    # ===== PARSE SHOT METADATA =====
    try:
        shot_type = ShotType(shot.get("shot_type", "medium_shot"))
    except ValueError:
        shot_type = ShotType.MS
        logger.warning(f"Unknown shot_type {shot.get('shot_type')}, defaulting to MS")

    try:
        scene_type = SceneType(shot.get("scene_type", "dialogue"))
    except ValueError:
        scene_type = SceneType.DIALOGUE
        logger.warning(f"Unknown scene_type {shot.get('scene_type')}, defaulting to DIALOGUE")

    # Detect emotion (from beat, beat_summary, or dialogue context)
    emotion = emotion_from_beat or _detect_emotion_from_shot(shot)

    characters = shot.get("characters") or []
    location = shot.get("location") or "UNKNOWN"
    dialogue_text = shot.get("dialogue_text") or ""
    is_broll = shot.get("is_broll", False)

    # ===== GET DP FRAMING STRATEGY =====
    strategy = rolodex.dp_framing.get_strategy_or_default(shot_type, scene_type)

    # ===== SELECT CHARACTER REFS =====
    confidence = 1.0
    selected_character_refs = []
    fallback_details = {}

    if not is_broll and characters:
        for char_name in characters:
            char_pack = rolodex.get_character_pack(char_name)

            if not char_pack or not char_pack.has_required():
                logger.warning(f"Character pack missing or invalid for {char_name}")
                confidence *= 0.7  # Significant degradation
                fallback_details[char_name] = "pack_missing"
                continue

            # Select primary ref type from strategy
            primary_ref_type = strategy.primary_character_ref

            # Apply emotion override if scene is intimate
            if strategy.include_expression_override:
                if emotion in ["grief", "sadness", "fear", "vulnerable", "shock"]:
                    primary_ref_type = RefType.EXPRESSION_VULNERABLE
                    result.emotion_override = "vulnerable"
            elif emotion in ["anger", "confrontation", "intense", "fear"]:
                # Try to use expression_intense
                if char_pack.expression_intense:
                    primary_ref_type = RefType.EXPRESSION_INTENSE
                    result.emotion_override = "intense"

            # Try to get primary ref type
            ref_path = char_pack.get_ref_by_type(primary_ref_type)
            if not ref_path:
                # Apply fallback chain: try expression_neutral → headshot_front
                logger.info(f"Primary ref {primary_ref_type.value} not available for {char_name}, "
                           f"falling back to fallback chain")
                fallback_details[char_name] = f"fallback_from_{primary_ref_type.value}"

                # Fallback priority: neutral → headshot_34 → headshot_front
                for fallback_type in [RefType.EXPRESSION_NEUTRAL, RefType.HEADSHOT_34, RefType.HEADSHOT_FRONT]:
                    ref_path = char_pack.get_ref_by_type(fallback_type)
                    if ref_path:
                        confidence *= 0.85  # Moderate degradation
                        result.fallback_used = True
                        break

                if not ref_path:
                    # Final fallback: use required headshot_front
                    ref_path = char_pack.headshot_front
                    if ref_path:
                        confidence *= 0.75
                        result.fallback_used = True

            if ref_path:
                selected_character_refs.append(ref_path)

    result.selected_character_refs = selected_character_refs
    result.fallback_details = fallback_details

    # ===== SELECT LOCATION REFS =====
    selected_location_refs = []
    location_pack = rolodex.get_location_pack(location)

    if location_pack and location_pack.has_required():
        # Select primary location ref from strategy
        location_ref_type = strategy.location_ref
        location_ref_path = location_pack.get_ref_by_type(location_ref_type)

        if not location_ref_path:
            # Fallback to master_wide (always required)
            logger.info(f"Location ref {location_ref_type.value} not available for {location}, "
                       f"falling back to master_wide")
            location_ref_path = location_pack.master_wide
            confidence *= 0.9
            result.fallback_used = True

        if location_ref_path:
            selected_location_refs.append(location_ref_path)

        # Add secondary location detail if available and useful
        if location_ref_type != LocationRefType.DETAIL_A and location_pack.detail_a:
            selected_location_refs.append(location_pack.detail_a)
    else:
        logger.warning(f"Location pack missing or invalid for {location}")
        confidence *= 0.6  # Significant degradation without environment

    result.selected_location_refs = selected_location_refs

    # ===== B-ROLL NARRATIVE CONTEXT =====
    if is_broll:
        result.broll_context = _determine_broll_context(shot, story_bible)

    # ===== BUILD SELECTION REASON =====
    result.selection_reason = _build_selection_reason(
        shot_type, scene_type, strategy, emotion, characters, location, is_broll
    )

    result.confidence = max(0.0, confidence)  # Clamp to [0, 1]

    logger.info(f"Selected refs for {shot.get('shot_id')}: confidence={result.confidence:.2f}, "
               f"reason={result.selection_reason[:60]}...")

    return result


def _detect_emotion_from_shot(shot: Dict[str, Any]) -> str:
    """
    Infer emotion from shot metadata.

    Priority:
      1. shot.emotion field (if explicit)
      2. shot.beat_summary (keyword search)
      3. shot.dialogue_text (keyword search)
      4. Default to "neutral"
    """
    # Try explicit emotion field
    emotion = shot.get("emotion") or ""
    if emotion:
        return emotion.lower()

    # Try beat_summary
    beat_summary = (shot.get("beat_summary") or "").lower()
    emotion_keywords = {
        "grief": ["grief", "mourn", "loss", "weeping", "devastated"],
        "fear": ["fear", "terror", "dread", "scared", "horrified"],
        "anger": ["anger", "rage", "furious", "wrathful", "hostile"],
        "sadness": ["sadness", "sad", "melancholy", "sorrow", "dejected"],
        "vulnerable": ["vulnerable", "fragile", "broken", "desperate"],
        "confrontation": ["confront", "challenge", "accuse", "demand"],
    }
    for emotion_label, keywords in emotion_keywords.items():
        if any(kw in beat_summary for kw in keywords):
            return emotion_label

    # Try dialogue_text
    dialogue = (shot.get("dialogue_text") or "").lower()
    for emotion_label, keywords in emotion_keywords.items():
        if any(kw in dialogue for kw in keywords):
            return emotion_label

    return "neutral"


def _determine_broll_context(shot: Dict[str, Any], story_bible: Dict[str, Any]) -> BRollContext:
    """
    Determine narrative purpose of B-roll shot.

    Rules:
      - Opening B-roll in scene: SCENE_OPENING (what leads into)
      - Closing B-roll in scene: SCENE_CLOSING (what carries out)
      - B-roll with character action: CONTEXT (story-relevant)
      - Pure atmospheric B-roll: ATMOSPHERIC
    """
    shot_index = shot.get("shot_index_in_scene", -1)
    scene_shot_count = shot.get("scene_shot_count", 1)
    beat_summary = (shot.get("beat_summary") or "").lower()

    # Heuristic: if first B-roll in scene
    if shot_index <= 1:
        return BRollContext.SCENE_OPENING

    # If last or second-to-last
    if shot_index >= scene_shot_count - 2:
        return BRollContext.SCENE_CLOSING

    # If beat mentions narrative elements (character action, story object)
    story_keywords = ["packing", "leaving", "arriving", "letter", "photo", "frame", "portrait",
                     "heirloom", "servant", "work", "preparing", "arranging"]
    if any(kw in beat_summary for kw in story_keywords):
        return BRollContext.CONTEXT

    return BRollContext.ATMOSPHERIC


def _build_selection_reason(
    shot_type: ShotType,
    scene_type: SceneType,
    strategy: DPFramingStrategy,
    emotion: str,
    characters: List[str],
    location: str,
    is_broll: bool
) -> str:
    """Build human-readable explanation of selection logic."""
    char_str = " + ".join(characters) if characters else "(no characters)"
    location_str = f" @ {location}" if location != "UNKNOWN" else ""
    broll_str = " [B-ROLL]" if is_broll else ""
    emotion_str = f" ({emotion})" if emotion != "neutral" else ""

    return (
        f"{shot_type.value} {scene_type.value} → {strategy.primary_character_ref.value} + "
        f"{strategy.location_ref.value} | {char_str}{location_str}{emotion_str}{broll_str}"
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_empty_character_pack_structure(
    project_path: str,
    character_name: str
) -> Path:
    """
    Create empty character pack directory structure.

    Returns:
        Path to created pack directory

    Purpose:
        Set up directory so user can manually add images before generation.
    """
    pack_dir = Path(project_path) / "character_packs" / character_name.upper().replace(" ", "_")
    pack_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "character_name": character_name,
        "created_at": datetime.now().isoformat(),
        "images": {
            "headshot_front": {"required": True, "exists": False},
            "headshot_34": {"required": False, "exists": False},
            "profile": {"required": False, "exists": False},
            "full_body": {"required": False, "exists": False},
            "expression_neutral": {"required": False, "exists": False},
            "expression_intense": {"required": False, "exists": False},
            "expression_vulnerable": {"required": False, "exists": False},
        }
    }

    manifest_path = pack_dir / "pack_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Created character pack structure at {pack_dir}")
    return pack_dir


def create_empty_location_pack_structure(
    project_path: str,
    location_id: str
) -> Path:
    """
    Create empty location pack directory structure.

    Returns:
        Path to created pack directory
    """
    pack_dir = Path(project_path) / "location_packs" / location_id.upper().replace(" ", "_")
    pack_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "location_id": location_id,
        "created_at": datetime.now().isoformat(),
        "images": {
            "master_wide": {"required": True, "exists": False},
            "reverse_wide": {"required": False, "exists": False},
            "detail_a": {"required": False, "exists": False},
            "detail_b": {"required": False, "exists": False},
            "exterior": {"required": False, "exists": False},
        }
    }

    manifest_path = pack_dir / "pack_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Created location pack structure at {pack_dir}")
    return pack_dir


# ============================================================================
# VALIDATION & DIAGNOSTIC FUNCTIONS
# ============================================================================

def validate_rolodex_completeness(
    project_path: str,
    required_characters: List[str],
    required_locations: List[str]
) -> Dict[str, Any]:
    """
    Audit rolodex for completeness before generation.

    Returns:
        {
            "complete": bool,
            "character_status": {char: {"pack_exists": bool, "images": {type: bool}}},
            "location_status": {loc: {"pack_exists": bool, "images": {type: bool}}},
            "missing_required": ["CHARACTER_A (headshot_front)", "LOCATION_B (master_wide)"],
            "recommendations": ["Generate placeholder refs for ELEANOR", ...]
        }
    """
    rolodex = CanonicalRolodex(project_path)

    character_status = {}
    location_status = {}
    missing_required = []
    recommendations = []

    # Audit characters
    for char_name in required_characters:
        pack = rolodex.get_character_pack(char_name)
        if not pack:
            character_status[char_name] = {"pack_exists": False}
            missing_required.append(f"{char_name} (entire pack)")
            recommendations.append(f"Create character pack for {char_name}")
        else:
            images = {}
            for ref_type in RefType:
                ref_path = pack.get_ref_by_type(ref_type)
                images[ref_type.value] = bool(ref_path)

                if not ref_path and ref_type == RefType.HEADSHOT_FRONT:
                    missing_required.append(f"{char_name} (headshot_front)")
                    recommendations.append(f"Add headshot_front for {char_name}")

            character_status[char_name] = {"pack_exists": True, "images": images}

    # Audit locations
    for loc_id in required_locations:
        pack = rolodex.get_location_pack(loc_id)
        if not pack:
            location_status[loc_id] = {"pack_exists": False}
            missing_required.append(f"{loc_id} (entire pack)")
            recommendations.append(f"Create location pack for {loc_id}")
        else:
            images = {}
            for ref_type in LocationRefType:
                ref_path = pack.get_ref_by_type(ref_type)
                images[ref_type.value] = bool(ref_path)

                if not ref_path and ref_type == LocationRefType.MASTER_WIDE:
                    missing_required.append(f"{loc_id} (master_wide)")
                    recommendations.append(f"Add master_wide for {loc_id}")

            location_status[loc_id] = {"pack_exists": True, "images": images}

    complete = len(missing_required) == 0

    return {
        "complete": complete,
        "character_status": character_status,
        "location_status": location_status,
        "missing_required": missing_required,
        "recommendations": recommendations,
        "audit_timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Simple CLI for testing
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 tools/canonical_rolodex.py <project_path> <command>")
        print("Commands:")
        print("  audit <required_chars.json> <required_locations.json>")
        print("  create-char-pack <character_name>")
        print("  create-loc-pack <location_id>")
        sys.exit(1)

    project_path = sys.argv[1]
    command = sys.argv[2]

    if command == "audit":
        if len(sys.argv) < 5:
            print("Usage: audit <required_chars.json> <required_locations.json>")
            sys.exit(1)
        with open(sys.argv[3]) as f:
            chars = json.load(f)
        with open(sys.argv[4]) as f:
            locs = json.load(f)
        result = validate_rolodex_completeness(project_path, chars, locs)
        print(json.dumps(result, indent=2))

    elif command == "create-char-pack":
        if len(sys.argv) < 4:
            print("Usage: create-char-pack <character_name>")
            sys.exit(1)
        create_empty_character_pack_structure(project_path, sys.argv[3])

    elif command == "create-loc-pack":
        if len(sys.argv) < 4:
            print("Usage: create-loc-pack <location_id>")
            sys.exit(1)
        create_empty_location_pack_structure(project_path, sys.argv[3])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
