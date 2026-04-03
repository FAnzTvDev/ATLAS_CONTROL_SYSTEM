"""
ATLAS V18.3 — Continuity State Enricher Agent
==============================================
Enriches shot_plan with persistent state tracking across shots.

Part of the Director Brain system (V18.2+):
- SceneState: Character pose, position, emotion_intensity across shots
- ShotRole: GEOGRAPHY (wide), ACTION (medium), EMOTION (close)
- CoverageRole: A_GEOGRAPHY, B_ACTION, C_EMOTION for coverage contracts
- state_in / state_out: Character state deltas per shot

Key responsibilities:
1. Infer character poses from shot descriptions + beat actions
2. Track emotion intensity changes per beat
3. Assign coverage roles based on focal length + character count
4. Detect state changes between consecutive shots
5. Flag continuity gaps for the gate to validate

Returns per-shot enrichment:
{
  "shot_role": "GEOGRAPHY|ACTION|EMOTION",
  "coverage_role": "A_GEOGRAPHY|B_ACTION|C_EMOTION",
  "state_in": {"CHARACTER": {"pose": "standing", "emotion_intensity": 5, "position": "center"}},
  "state_out": {"CHARACTER": {"pose": "kneeling", "emotion_intensity": 8, "position": "altar"}},
  "state_changes": [{"character": "EVELYN", "from_pose": "standing", "to_pose": "kneeling", "triggered_by": "beat_action"}],
  "continuity_gaps": []
}
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger("atlas.continuity_state_enricher")

# ─── Pose Keywords ───
POSE_KEYWORDS = {
    "standing": ["stand", "stands", "standing", "rises", "get up", "gets up", "risen"],
    "sitting": ["sit", "sits", "sitting", "seated", "slumps", "settles"],
    "kneeling": ["kneel", "kneels", "kneeling", "knelt"],
    "lying": ["lies", "lying", "lay", "lays", "reclines"],
    "falling": ["falls", "falling", "fell", "collapse", "collapses"],
    "reaching": ["reaches", "reaching", "reach", "stretches", "extending"],
    "walking": ["walks", "walking", "walk", "enters", "exits", "approaches", "strides", "paces"],
    "running": ["runs", "running", "run", "rushes", "dashing"],
    "kneeling_over": ["bends over", "leans over", "hunches", "stoops"],
}

# ─── Emotion Keywords ───
EMOTION_KEYWORDS = {
    "dread": ["dread", "horror", "terror", "terrified", "afraid"],
    "tension": ["tension", "tense", "anxious", "nervous", "worried"],
    "grief": ["grief", "grieves", "mourning", "tears", "weeping", "sobbing"],
    "joy": ["joy", "happy", "happiness", "delighted", "elated"],
    "anger": ["anger", "angry", "rage", "furious", "enraged"],
    "surprise": ["surprise", "surprised", "shocked", "startled", "gasps"],
    "fear": ["fear", "afraid", "frightened", "scared", "terrified"],
    "hope": ["hope", "hopeful", "optimistic", "uplifting"],
    "sorrow": ["sorrow", "sad", "sadness", "melancholy", "despair"],
    "calm": ["calm", "peaceful", "serene", "tranquil", "composed"],
    "confusion": ["confused", "confused", "bewildered", "disoriented", "uncertain"],
    "determination": ["determined", "resolute", "steadfast", "unwavering"],
}

# ─── Shot Role Detection (based on focal length + character count) ───
# Lower focal length (wider) = GEOGRAPHY, Higher focal length (tighter) = EMOTION
def infer_shot_role(focal_length: Optional[float], character_count: int, 
                   shot_type: Optional[str]) -> str:
    """
    Infer shot role from focal length and character count.
    A_GEOGRAPHY: 14-35mm, 2+ characters, establishes space
    B_ACTION: 35-65mm, 1-2 characters, action-focused
    C_EMOTION: 65-135mm, 1 character, intimate close-up
    """
    shot_type_lower = (shot_type or "").lower()
    
    # Shot type shortcuts
    if any(x in shot_type_lower for x in ["wide", "master", "establishing", "ext", "LS", "VW"]):
        return "GEOGRAPHY"
    elif any(x in shot_type_lower for x in ["close", "mcu", "cu", "extreme", "detail"]):
        return "EMOTION"
    elif any(x in shot_type_lower for x in ["medium", "ms", "two-shot", "ots"]):
        return "ACTION"
    
    # Focal length heuristic
    if focal_length:
        if focal_length < 35:
            return "GEOGRAPHY"
        elif focal_length < 65:
            return "ACTION"
        else:
            return "EMOTION"
    
    # Character count fallback
    if character_count >= 2:
        return "GEOGRAPHY"
    elif character_count == 1:
        return "EMOTION"
    else:
        return "ACTION"


def infer_coverage_role(shot_role: str) -> str:
    """Map shot_role to coverage contract role."""
    role_map = {
        "GEOGRAPHY": "A_GEOGRAPHY",
        "ACTION": "B_ACTION",
        "EMOTION": "C_EMOTION",
    }
    return role_map.get(shot_role, "B_ACTION")


# ─── Pose Extraction ───
def extract_pose_from_text(text: str, previous_pose: Optional[str] = None) -> Optional[str]:
    """
    Extract character pose from beat description or shot type.
    Returns most recent pose mentioned, or previous_pose if no change detected.
    """
    if not text:
        return previous_pose or "standing"
    
    text_lower = text.lower()
    
    # Check for explicit pose keywords (order matters: more specific first)
    for pose, keywords in POSE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return pose
    
    return previous_pose or "standing"


# ─── Emotion Intensity Extraction ───
def extract_emotion_intensity(beat_description: str, dialogue: str = "", 
                             previous_intensity: int = 5) -> int:
    """
    Extract emotion intensity (0-10 scale) from beat + dialogue.
    0-2: calm, composed, neutral
    3-4: mild concern, slight worry
    5: neutral/balanced
    6-7: strong emotion, visible impact
    8-9: extreme emotion, breaking composure
    10: maximum intensity (rage, terror, etc.)
    """
    text = (beat_description + " " + dialogue).lower()
    
    # Extreme keywords → intensity 9-10
    extreme_words = ["terror", "terror", "horrified", "devastated", "ecstatic", "enraged"]
    if any(w in text for w in extreme_words):
        return 10
    
    # Strong keywords → intensity 7-8
    strong_words = ["tears", "trembles", "shakes", "gasps", "rage", "fury", "despair", "grief"]
    if any(w in text for w in strong_words):
        return 8
    
    # Medium keywords → intensity 6-7
    medium_words = ["sad", "angry", "worried", "afraid", "hope", "joy", "surprised", "shocked"]
    if any(w in text for w in medium_words):
        return 6
    
    # Mild keywords → intensity 3-4
    mild_words = ["concerned", "unsure", "hesitant", "nervous", "slight", "faint"]
    if any(w in text for w in mild_words):
        return 4
    
    # Calm keywords → intensity 0-2
    calm_words = ["calm", "peaceful", "serene", "composed", "tranquil", "quiet"]
    if any(w in text for w in calm_words):
        return 1
    
    return previous_intensity


# ─── Position Extraction ───
def extract_position_from_text(text: str, previous_position: str = "center") -> str:
    """
    Extract character position (spatial location in frame).
    Returns: "center", "left", "right", "foreground", "background", "altar", "window", etc.
    """
    if not text:
        return previous_position
    
    text_lower = text.lower()
    
    # Specific location keywords
    position_keywords = {
        "center": ["center", "middle", "foreground"],
        "left": ["left", "stage left"],
        "right": ["right", "stage right"],
        "background": ["background", "back", "behind"],
        "altar": ["altar", "at the altar"],
        "window": ["window", "at the window", "looking out"],
        "door": ["door", "doorway", "at the door"],
        "bed": ["bed", "on the bed"],
        "floor": ["floor", "on the floor"],
        "chair": ["chair", "seated"],
    }
    
    for position, keywords in position_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return position
    
    return previous_position


@dataclass
class CharacterState:
    """State of a single character at a point in time."""
    pose: str = "standing"
    position: str = "center"
    emotion_intensity: int = 5
    props_in_hand: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ShotEnrichment:
    """Complete state enrichment for a single shot."""
    shot_id: str
    shot_role: str
    coverage_role: str
    state_in: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    state_out: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    state_changes: List[Dict[str, Any]] = field(default_factory=list)
    continuity_gaps: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContinuityStateEnricher:
    """Enriches shot_plan with persistent state tracking."""
    
    def __init__(self, story_bible: Dict, shot_plan: Dict):
        self.story_bible = story_bible or {}
        self.shot_plan = shot_plan or {}
        self.scenes = self.story_bible.get("scenes", [])
        self.shots = self.shot_plan.get("shots", [])
        self.character_states: Dict[str, CharacterState] = {}  # Per-scene state tracking
    
    def enrich_all_shots(self) -> Dict[str, Any]:
        """
        Enrich all shots in shot_plan with state_in/state_out/shot_role/coverage_role.
        Returns: {enriched_shots, report}
        """
        enriched = []
        scene_states = {}  # Reset per scene
        
        for shot_idx, shot in enumerate(self.shots):
            shot_id = shot.get("shot_id", f"shot_{shot_idx}")
            scene_id = shot.get("scene_id", "001")
            
            # Reset scene state when entering new scene
            if scene_id not in scene_states:
                scene_states[scene_id] = {}
                self.character_states = {}
            
            # Get beat data for this shot
            beat = self._get_beat_for_shot(shot_id, scene_id)
            characters = self._get_characters_for_shot(shot_id, scene_id)
            
            # Calculate focal length from lens_specs if available
            focal_length = self._extract_focal_length(shot.get("lens_specs", ""))
            
            # Infer shot role from focal length + character count
            shot_role = infer_shot_role(focal_length, len(characters), shot.get("shot_type"))
            coverage_role = infer_coverage_role(shot_role)
            
            # Build state_in (from previous shot or scene default)
            state_in = self._build_state_in(characters, scene_states[scene_id])
            
            # Build state_out (from beat + shot description)
            state_out, changes = self._build_state_out(
                characters, state_in, beat, shot, scene_states[scene_id]
            )
            
            # Update scene state for next shot
            scene_states[scene_id] = state_out
            
            # Detect continuity gaps
            gaps = self._detect_gaps(state_in, state_out, beat, shot)
            
            # Build enrichment
            enrichment = ShotEnrichment(
                shot_id=shot_id,
                shot_role=shot_role,
                coverage_role=coverage_role,
                state_in=state_in,
                state_out=state_out,
                state_changes=changes,
                continuity_gaps=gaps,
            )
            
            # Merge back into shot
            enriched_shot = {**shot}
            enriched_shot.update(enrichment.to_dict())
            enriched.append(enriched_shot)
        
        return {
            "enriched_shots": enriched,
            "report": {
                "total_shots": len(enriched),
                "shots_with_state": len([s for s in enriched if s.get("state_in")]),
                "scenes_processed": len(scene_states),
            }
        }
    
    def _get_beat_for_shot(self, shot_id: str, scene_id: str) -> Optional[Dict]:
        """Look up beat data from story_bible for a given shot."""
        for scene in self.scenes:
            if scene.get("scene_id") == scene_id:
                beats = scene.get("beats", [])
                for beat in beats:
                    if beat.get("beat_id") == shot_id or beat.get("shot_id") == shot_id:
                        return beat
        return None
    
    def _get_characters_for_shot(self, shot_id: str, scene_id: str) -> List[str]:
        """Extract character list from shot description."""
        shot = next((s for s in self.shots if s.get("shot_id") == shot_id), None)
        if not shot:
            return []
        
        # Try multiple sources
        chars = shot.get("characters", [])
        if chars:
            return chars if isinstance(chars, list) else [chars]
        
        # Extract from description
        desc = (shot.get("shot_description", "") + " " + shot.get("nano_prompt", "")).upper()
        cast = self.story_bible.get("cast", [])
        found = []
        for actor in cast:
            name = actor.get("name", "").upper()
            if name and name in desc:
                found.append(name)
        return found or []
    
    def _extract_focal_length(self, lens_specs: str) -> Optional[float]:
        """Extract focal length (mm) from lens spec string."""
        if not lens_specs:
            return None
        
        # Try to extract number from specs like "24mm", "85mm", "135mm"
        match = re.search(r'(\d+)(?:mm)?', str(lens_specs))
        if match:
            return float(match.group(1))
        return None
    
    def _build_state_in(self, characters: List[str], previous_scene_state: Dict) -> Dict[str, Dict]:
        """
        Build state_in from previous shot or scene default.
        """
        state = {}
        for char in characters:
            if char in previous_scene_state:
                state[char] = dict(previous_scene_state[char])
            else:
                state[char] = CharacterState().to_dict()
        return state
    
    def _build_state_out(self, characters: List[str], state_in: Dict[str, Dict],
                        beat: Optional[Dict], shot: Dict, 
                        scene_state: Dict) -> Tuple[Dict[str, Dict], List[Dict]]:
        """
        Build state_out from beat + shot description.
        Returns: (state_out, state_changes)
        """
        state_out = {}
        changes = []
        
        beat_desc = beat.get("action", "") if beat else ""
        shot_desc = shot.get("shot_description", "")
        dialogue = beat.get("dialogue", "") if beat else ""
        full_text = f"{beat_desc} {shot_desc} {dialogue}"
        
        for char in characters:
            char_state_in = state_in.get(char, CharacterState().to_dict())
            
            # Extract new pose
            new_pose = extract_pose_from_text(full_text, char_state_in.get("pose", "standing"))
            
            # Extract new emotion intensity
            new_emotion = extract_emotion_intensity(beat_desc, dialogue, 
                                                    char_state_in.get("emotion_intensity", 5))
            
            # Extract new position
            new_position = extract_position_from_text(full_text, char_state_in.get("position", "center"))
            
            # Build new state
            char_state_out = {
                "pose": new_pose,
                "emotion_intensity": new_emotion,
                "position": new_position,
                "props_in_hand": char_state_in.get("props_in_hand", []),
            }
            
            state_out[char] = char_state_out
            
            # Track changes
            if new_pose != char_state_in.get("pose"):
                changes.append({
                    "character": char,
                    "type": "pose_change",
                    "from_pose": char_state_in.get("pose"),
                    "to_pose": new_pose,
                    "triggered_by": "beat_action" if beat else "shot_description",
                })
            
            if new_emotion != char_state_in.get("emotion_intensity"):
                changes.append({
                    "character": char,
                    "type": "emotion_change",
                    "from_intensity": char_state_in.get("emotion_intensity"),
                    "to_intensity": new_emotion,
                    "delta": new_emotion - char_state_in.get("emotion_intensity", 5),
                })
        
        return state_out, changes
    
    def _detect_gaps(self, state_in: Dict, state_out: Dict, beat: Optional[Dict],
                    shot: Dict) -> List[str]:
        """
        Detect continuity gaps (e.g., unmotivated pose changes).
        Returns list of gap descriptions for gate to validate.
        """
        gaps = []
        
        beat_desc = beat.get("action", "") if beat else ""
        shot_desc = shot.get("shot_description", "")
        
        for char, state_out_char in state_out.items():
            state_in_char = state_in.get(char, {})
            
            # Gap: pose change without beat action
            if state_out_char.get("pose") != state_in_char.get("pose"):
                if not beat_desc and not shot_desc:
                    gaps.append(
                        f"{char}: unmotivated pose change ({state_in_char.get('pose')} → {state_out_char.get('pose')})"
                    )
            
            # Gap: large emotion jump
            emotion_delta = state_out_char.get("emotion_intensity", 5) - state_in_char.get("emotion_intensity", 5)
            if abs(emotion_delta) > 3:
                if not beat_desc:
                    gaps.append(
                        f"{char}: unexplained emotion jump ({emotion_delta:+d})"
                    )
        
        return gaps


def enrich_shot_plan_with_state(story_bible: Dict, shot_plan: Dict) -> Dict[str, Any]:
    """
    Main entry point for state enrichment.
    
    Args:
        story_bible: Story bible dict with scenes, beats, cast
        shot_plan: Shot plan dict with shots array
    
    Returns:
        Enriched shot_plan with state_in/state_out/shot_role/coverage_role per shot
    """
    enricher = ContinuityStateEnricher(story_bible, shot_plan)
    result = enricher.enrich_all_shots()
    
    # Replace shots array with enriched version
    enriched_plan = {**shot_plan}
    enriched_plan["shots"] = result["enriched_shots"]
    
    logger.info(f"State enrichment complete: {result['report']}")
    
    return {
        "enriched_shot_plan": enriched_plan,
        "report": result["report"],
    }
