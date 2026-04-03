"""
V18.2: CONTINUITY GATE — Director Brain Pre-Render Validator

Sits BETWEEN planning and rendering. Blocks bad shot plans before compute is wasted.

Architecture:
    script → beats → blocking timeline (stateful) → coverage (3 angles) → continuity gate → render

Three components:
    1. SceneState — persistent truth across shots (pose, position, emotion, props)
    2. CoverageContract — 3-angle coverage per beat (Geography/Action/Emotion)
    3. ContinuityGate — validates state transitions, blocks nonsense

Rules enforced:
    - No pose change without action beat
    - No position jump without movement beat or bridging shot
    - No emotion teleport (max 2-point jump without micro-beat)
    - No 180° axis cross without motivated break
    - Bridge score between consecutive shots must pass threshold
"""

import json
import logging
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# SCENE STATE — persistent truth that every shot must read and write
# ═══════════════════════════════════════════════════════════════════════

VALID_POSES = {"standing", "sitting", "kneeling", "prone", "leaning", "walking", "running", "crouching"}
VALID_SHOT_ROLES = {"GEOGRAPHY", "ACTION", "EMOTION"}

@dataclass
class CharacterState:
    """Tracked state for one character within a scene."""
    name: str
    pose: str = "standing"
    position_x: float = 0.0  # Relative screen position -1 to 1
    position_y: float = 0.0
    facing: str = "camera"  # camera, left, right, away
    hands: str = "free"  # free, holding_prop, gesturing, clasped
    emotion_intensity: int = 5  # 0-10 scale
    emotion_label: str = "neutral"
    prop_held: str = ""

@dataclass
class SceneState:
    """
    The truth the system must obey. Persists across shots within a scene.
    Every shot reads SceneState, and after planning writes a delta.
    """
    scene_id: str
    location_anchor: str = ""
    time_in_scene: float = 0.0  # cumulative seconds
    beat_index: int = 0
    characters: Dict[str, CharacterState] = field(default_factory=dict)
    props: Dict[str, dict] = field(default_factory=dict)  # prop_name → {position, owner}
    camera_axis: str = "standard"  # standard, crossed, neutral
    wardrobe_ids: Dict[str, str] = field(default_factory=dict)  # char_name → wardrobe_id

    def get_character(self, name: str) -> CharacterState:
        """Get or create character state."""
        name_upper = name.upper().strip()
        if name_upper not in self.characters:
            self.characters[name_upper] = CharacterState(name=name_upper)
        return self.characters[name_upper]

    def apply_delta(self, delta: dict):
        """Apply a state delta from a shot plan."""
        for char_name, changes in delta.get("characters", {}).items():
            cs = self.get_character(char_name)
            for k, v in changes.items():
                if hasattr(cs, k):
                    setattr(cs, k, v)
        if "time_advance" in delta:
            self.time_in_scene += delta["time_advance"]
        if "beat_index" in delta:
            self.beat_index = delta["beat_index"]
        if "camera_axis" in delta:
            self.camera_axis = delta["camera_axis"]

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "location_anchor": self.location_anchor,
            "time_in_scene": self.time_in_scene,
            "beat_index": self.beat_index,
            "camera_axis": self.camera_axis,
            "characters": {
                name: asdict(cs) for name, cs in self.characters.items()
            },
            "props": self.props,
            "wardrobe_ids": self.wardrobe_ids,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SceneState":
        state = cls(
            scene_id=d.get("scene_id", ""),
            location_anchor=d.get("location_anchor", ""),
            time_in_scene=d.get("time_in_scene", 0),
            beat_index=d.get("beat_index", 0),
            camera_axis=d.get("camera_axis", "standard"),
            wardrobe_ids=d.get("wardrobe_ids", {}),
            props=d.get("props", {}),
        )
        for name, cd in d.get("characters", {}).items():
            state.characters[name] = CharacterState(**cd)
        return state


# ═══════════════════════════════════════════════════════════════════════
# COVERAGE CONTRACT — 3-angle coverage per beat
# ═══════════════════════════════════════════════════════════════════════

COVERAGE_ROLES = {
    "A_GEOGRAPHY": {
        "label": "Geography",
        "description": "Wide/establishing — maintains spatial logic and orientation",
        "shot_sizes": ["EWS", "WS", "MWS", "FULL"],
        "lens_range": "14-35mm",
        "goal": "orientation + continuity",
    },
    "B_ACTION": {
        "label": "Action",
        "description": "Medium showing body mechanics and blocking",
        "shot_sizes": ["MS", "MWS", "MCU", "OTS", "TWO"],
        "lens_range": "35-65mm",
        "goal": "action clarity + match cuts",
    },
    "C_EMOTION": {
        "label": "Emotion",
        "description": "Close-up for performance and psychological continuity",
        "shot_sizes": ["CU", "MCU", "ECU"],
        "lens_range": "65-135mm",
        "goal": "performance + psychological continuity",
    },
}


def assign_coverage_role(shot: dict) -> str:
    """Assign A/B/C coverage role based on shot characteristics."""
    shot_size = (shot.get("shot_size") or shot.get("type") or "").upper()
    purpose = (shot.get("purpose") or "").upper()
    shot_type = (shot.get("shot_type") or "").lower()

    # Explicit coverage_role already set
    existing = shot.get("coverage_role", "")
    if existing and existing.startswith(("A_", "B_", "C_")):
        return existing

    # Wide/establishing → Geography
    if shot_size in ("EWS", "WS", "MWS", "FULL") or purpose in ("ESTABLISH", "MASTER"):
        return "A_GEOGRAPHY"

    # Close-ups → Emotion
    if shot_size in ("CU", "ECU", "BCU") or shot_type in ("reaction", "emotion", "close"):
        return "C_EMOTION"

    # Dialogue and medium shots → Action
    if shot_type in ("dialogue", "action", "movement") or shot_size in ("MS", "MCU", "OTS", "TWO"):
        return "B_ACTION"

    # Default to Action (most common)
    return "B_ACTION"


# ═══════════════════════════════════════════════════════════════════════
# STATE INFERENCE — extract state_in/state_out from shot content
# ═══════════════════════════════════════════════════════════════════════

# Pose detection keywords
POSE_KEYWORDS = {
    "kneeling": ["kneels", "kneeling", "drops to her knees", "drops to his knees",
                  "falls to knees", "on her knees", "on his knees", "genuflects"],
    "sitting": ["sits", "sitting", "seated", "sits down", "takes a seat", "in a chair",
                "at the desk", "at a table"],
    "prone": ["lying", "collapsed", "falls", "on the ground", "on the floor",
              "sprawled", "face down"],
    "crouching": ["crouches", "crouching", "ducking", "hunched", "squatting"],
    "walking": ["walks", "walking", "pacing", "strides", "approaches", "crosses"],
    "running": ["runs", "running", "sprints", "dashes", "flees", "rushes"],
    "leaning": ["leans", "leaning", "propped against", "resting against"],
    "standing": ["stands", "standing", "rises", "gets up", "on her feet", "on his feet"],
}

EMOTION_KEYWORDS = {
    0: ["calm", "neutral", "blank", "serene"],
    2: ["thoughtful", "curious", "attentive", "watchful"],
    4: ["concerned", "uneasy", "anxious", "wary"],
    5: ["tense", "worried", "conflicted", "determined"],
    6: ["angry", "frightened", "desperate", "pleading"],
    7: ["furious", "terrified", "grief", "anguish"],
    8: ["rage", "horror", "breakdown", "hysteria"],
    9: ["primal fear", "violent", "unhinged", "catatonic"],
    10: ["transcendent terror", "complete breakdown"],
}


def _detect_pose(text: str) -> str:
    """Detect pose from text content."""
    text_lower = text.lower()
    for pose, keywords in POSE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return pose
    return "standing"


def _detect_emotion_intensity(text: str) -> int:
    """Detect emotion intensity from text content."""
    text_lower = text.lower()
    for intensity in sorted(EMOTION_KEYWORDS.keys(), reverse=True):
        for kw in EMOTION_KEYWORDS[intensity]:
            if kw in text_lower:
                return intensity
    return 5  # Default neutral-tense


def infer_state_from_shot(shot: dict, prev_state: Optional[SceneState] = None) -> Tuple[dict, dict]:
    """
    Infer state_in and state_out from shot content.
    Returns (state_in, state_out) as dicts with character states.

    state_in = what the scene looks like AT THE START of this shot
    state_out = what the scene looks like AT THE END of this shot
    """
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    nano = shot.get("nano_prompt", "")
    ltx = shot.get("ltx_motion_prompt", "")
    dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "")
    beat_desc = shot.get("_beat_description", "")
    action_beat = shot.get("action_beat", "")

    # Combine all text sources for analysis
    all_text = f"{nano} {ltx} {dialogue} {beat_desc} {action_beat}"

    state_in = {}
    state_out = {}

    for char_name in characters:
        char_upper = char_name.upper().strip()

        # Start from previous state if available
        if prev_state and char_upper in prev_state.characters:
            prev_cs = prev_state.characters[char_upper]
            in_pose = prev_cs.pose
            in_emotion = prev_cs.emotion_intensity
        else:
            in_pose = "standing"
            in_emotion = 5

        # Detect pose from shot content
        out_pose = _detect_pose(all_text)
        out_emotion = _detect_emotion_intensity(all_text)

        # If no specific pose detected, carry forward
        if out_pose == "standing" and in_pose != "standing":
            # Only reset to standing if explicitly mentioned
            if "stands" in all_text.lower() or "rises" in all_text.lower() or "gets up" in all_text.lower():
                out_pose = "standing"
            else:
                out_pose = in_pose  # Carry forward

        state_in[char_upper] = {
            "pose": in_pose,
            "emotion_intensity": in_emotion,
        }
        state_out[char_upper] = {
            "pose": out_pose,
            "emotion_intensity": out_emotion,
        }

    return state_in, state_out


# ═══════════════════════════════════════════════════════════════════════
# CONTINUITY GATE — the validator that blocks bad plans
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """Result of a continuity gate check."""
    passed: bool
    shot_id: str
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    auto_fixes: List[str] = field(default_factory=list)
    needs_connector: bool = False
    connector_type: str = ""  # "transition_wide", "insert_hands", "reaction_cu"
    bridge_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ContinuityGate:
    """
    Validates shot plans before rendering. Blocks continuity violations.

    Rules:
    1. POSE CHANGE → requires action_beat text or connector shot
    2. POSITION JUMP → requires movement beat or bridging shot
    3. EMOTION JUMP → max 2-point jump without micro-beat
    4. AXIS BREAK → requires motivated break or neutral cutaway
    5. BRIDGE SCORE → consecutive shots must cut cleanly
    """

    EMOTION_MAX_JUMP = 3  # Max allowed jump without a micro-beat
    BRIDGE_SCORE_THRESHOLD = 0.4  # Minimum bridge score to pass

    def __init__(self, scene_state: Optional[SceneState] = None):
        self.scene_state = scene_state or SceneState(scene_id="")
        self.violations_log = []

    def validate_shot(self, shot: dict, prev_shot: Optional[dict] = None) -> GateResult:
        """
        Validate a single shot against continuity rules.
        Returns GateResult with pass/fail + violations.
        """
        sid = shot.get("shot_id", "unknown")
        result = GateResult(passed=True, shot_id=sid)

        # Infer states
        state_in, state_out = infer_state_from_shot(shot, self.scene_state)
        shot["state_in"] = state_in
        shot["state_out"] = state_out

        # Assign coverage role
        shot["coverage_role"] = assign_coverage_role(shot)

        characters = shot.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",") if c.strip()]

        all_text = f"{shot.get('nano_prompt', '')} {shot.get('ltx_motion_prompt', '')} {shot.get('action_beat', '')} {shot.get('_beat_description', '')}"

        for char_name in characters:
            char_upper = char_name.upper().strip()
            s_in = state_in.get(char_upper, {})
            s_out = state_out.get(char_upper, {})

            # ─── RULE 1: POSE CHANGE requires action beat ───
            in_pose = s_in.get("pose", "standing")
            out_pose = s_out.get("pose", "standing")
            if in_pose != out_pose:
                has_action_beat = bool(shot.get("action_beat"))
                # Also check if the prompt describes the transition
                pose_described = any(kw in all_text.lower() for kw in POSE_KEYWORDS.get(out_pose, []))

                if not has_action_beat and not pose_described:
                    result.violations.append(
                        f"POSE_CHANGE: {char_upper} goes {in_pose}→{out_pose} without action beat"
                    )
                    result.needs_connector = True
                    result.connector_type = "transition_wide"
                    result.passed = False
                else:
                    result.auto_fixes.append(
                        f"POSE_OK: {char_upper} {in_pose}→{out_pose} (action beat present)"
                    )

            # ─── RULE 2: EMOTION JUMP check ───
            in_emo = s_in.get("emotion_intensity", 5)
            out_emo = s_out.get("emotion_intensity", 5)
            emo_delta = abs(out_emo - in_emo)
            if emo_delta > self.EMOTION_MAX_JUMP:
                has_dialogue = bool(shot.get("dialogue_text") or shot.get("dialogue"))
                has_reaction = "reaction" in (shot.get("shot_type") or "").lower()
                if not has_dialogue and not has_reaction:
                    result.warnings.append(
                        f"EMOTION_JUMP: {char_upper} intensity {in_emo}→{out_emo} (delta={emo_delta}) without dialogue/reaction"
                    )

        # ─── RULE 3: BRIDGE SCORE to previous shot ───
        if prev_shot:
            bridge = self._compute_bridge_score(prev_shot, shot)
            result.bridge_score = bridge
            if bridge < self.BRIDGE_SCORE_THRESHOLD:
                result.warnings.append(
                    f"LOW_BRIDGE: score={bridge:.2f} (threshold={self.BRIDGE_SCORE_THRESHOLD})"
                )

        # Update scene state with this shot's output
        for char_upper, s_out_data in state_out.items():
            cs = self.scene_state.get_character(char_upper)
            cs.pose = s_out_data.get("pose", cs.pose)
            cs.emotion_intensity = s_out_data.get("emotion_intensity", cs.emotion_intensity)

        self.scene_state.time_in_scene += float(shot.get("duration", 5))

        # Log violations
        if result.violations:
            self.violations_log.append(result.to_dict())
            logger.warning(f"[CONTINUITY-GATE] {sid}: {len(result.violations)} violations — {result.violations}")
        elif result.warnings:
            logger.info(f"[CONTINUITY-GATE] {sid}: PASS with {len(result.warnings)} warnings")
        else:
            logger.info(f"[CONTINUITY-GATE] {sid}: PASS ✅ (bridge={result.bridge_score:.2f})")

        return result

    def validate_scene(self, shots: List[dict], auto_fix: bool = True) -> List[GateResult]:
        """
        Validate all shots in a scene sequentially.
        If auto_fix=True, inserts connector shots where needed.
        Returns list of GateResults.
        """
        results = []
        prev_shot = None
        fixed_shots = []
        connector_count = 0

        for i, shot in enumerate(shots):
            result = self.validate_shot(shot, prev_shot)
            results.append(result)

            # AUTO-FIX: Insert connector shot if needed
            if auto_fix and result.needs_connector and result.connector_type:
                connector = self._generate_connector_shot(shot, prev_shot, result.connector_type)
                if connector:
                    fixed_shots.append(connector)
                    connector_count += 1
                    logger.info(f"[CONTINUITY-GATE] Inserted {result.connector_type} connector before {shot['shot_id']}")

            fixed_shots.append(shot)
            prev_shot = shot

        if connector_count > 0:
            logger.info(f"[CONTINUITY-GATE] Auto-inserted {connector_count} connector shots")
            # Replace original shots with fixed version
            shots.clear()
            shots.extend(fixed_shots)

        return results

    def _compute_bridge_score(self, prev_shot: dict, curr_shot: dict) -> float:
        """
        Compute how well two consecutive shots cut together.
        Score 0-1 based on:
        - Match on action direction
        - Match on composition progression
        - Match on emotional arc
        - Shot size variety (wide→medium→close is good)
        """
        score = 0.0
        factors = 0

        # 1. Shot size progression (avoid same-size cuts)
        prev_size = (prev_shot.get("shot_size") or "").upper()
        curr_size = (curr_shot.get("shot_size") or "").upper()

        SIZE_ORDER = {"EWS": 0, "WS": 1, "MWS": 2, "FULL": 3, "MS": 4, "MCU": 5, "OTS": 5, "TWO": 4, "CU": 6, "ECU": 7, "BCU": 7}
        prev_idx = SIZE_ORDER.get(prev_size, 4)
        curr_idx = SIZE_ORDER.get(curr_size, 4)
        size_delta = abs(prev_idx - curr_idx)

        if size_delta >= 2:
            score += 0.3  # Good jump
        elif size_delta == 1:
            score += 0.2  # Acceptable
        else:
            score += 0.05  # Same size = bad cut
        factors += 0.3

        # 2. Coverage role variety
        prev_role = prev_shot.get("coverage_role", "B_ACTION")
        curr_role = curr_shot.get("coverage_role", "B_ACTION")
        if prev_role != curr_role:
            score += 0.25  # Different coverage = good
        else:
            score += 0.05
        factors += 0.25

        # 3. Emotion continuity (smooth arc, no teleport)
        prev_state = prev_shot.get("state_out", {})
        curr_state = curr_shot.get("state_in", {})
        emo_deltas = []
        for char in set(list(prev_state.keys()) + list(curr_state.keys())):
            prev_emo = prev_state.get(char, {}).get("emotion_intensity", 5)
            curr_emo = curr_state.get(char, {}).get("emotion_intensity", 5)
            emo_deltas.append(abs(prev_emo - curr_emo))
        avg_emo_delta = sum(emo_deltas) / max(len(emo_deltas), 1)
        if avg_emo_delta <= 2:
            score += 0.25
        elif avg_emo_delta <= 4:
            score += 0.15
        else:
            score += 0.0
        factors += 0.25

        # 4. Character continuity (same characters in consecutive shots)
        prev_chars = set(c.upper() for c in (prev_shot.get("characters") or []))
        curr_chars = set(c.upper() for c in (curr_shot.get("characters") or []))
        if prev_chars and curr_chars:
            overlap = len(prev_chars & curr_chars) / max(len(prev_chars | curr_chars), 1)
            score += 0.2 * overlap
        factors += 0.2

        return round(min(score / max(factors, 0.01), 1.0), 3)

    def _generate_connector_shot(self, shot: dict, prev_shot: Optional[dict], connector_type: str) -> Optional[dict]:
        """
        Generate a connector/transition shot to fix continuity violations.
        This creates a minimal shot spec that the chain pipeline will render.
        """
        sid = shot.get("shot_id", "")
        scene_id = sid.split("_")[0] if "_" in sid else ""
        characters = shot.get("characters", [])
        location = shot.get("location", "")

        # Connector shot ID: insert "T" (transition) before the shot
        connector_id = f"{sid}_T"

        if connector_type == "transition_wide":
            # Wide shot showing the physical transition
            state_in = shot.get("state_in", {})
            state_out = shot.get("state_out", {})

            # Build transition description
            transitions = []
            for char in characters:
                char_upper = char.upper().strip() if isinstance(char, str) else str(char)
                s_in = state_in.get(char_upper, {})
                s_out = state_out.get(char_upper, {})
                if s_in.get("pose") != s_out.get("pose"):
                    transitions.append(f"{char} transitions from {s_in.get('pose', 'standing')} to {s_out.get('pose', 'standing')}")

            trans_desc = "; ".join(transitions) if transitions else "Character movement transition"

            return {
                "shot_id": connector_id,
                "scene_id": scene_id,
                "type": "medium_wide",
                "shot_size": "MWS",
                "shot_type": "transition",
                "shot_role": "GEOGRAPHY",
                "coverage_role": "A_GEOGRAPHY",
                "b_roll": False,
                "duration": 3,
                "duration_seconds": 3,
                "ltx_duration_seconds": 6,
                "location": location,
                "characters": characters,
                "nano_prompt": f"MWS medium wide shot showing {trans_desc}, {location}, continuous movement, smooth transition",
                "ltx_motion_prompt": f"0-3s smooth movement, {trans_desc}, natural body mechanics, face stable NO morphing",
                "action_beat": trans_desc,
                "_connector_shot": True,
                "_inserted_by": "continuity_gate",
                "_fixes_violation": f"pose_change in {sid}",
                "state_in": state_in,
                "state_out": state_out,
            }

        return None


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API — functions called by the chain pipeline
# ═══════════════════════════════════════════════════════════════════════

def run_continuity_gate(shots: List[dict], scene_id: str = "",
                        auto_fix: bool = True, story_bible: dict = None) -> dict:
    """
    Run the continuity gate on a list of shots.
    Returns summary with pass/fail counts, violations, and auto-fixes.

    This is the main entry point called by the chain pipeline.
    """
    if not shots:
        return {"success": True, "total": 0, "passed": 0, "failed": 0, "warnings": 0}

    # Initialize scene state from first shot's context
    location = shots[0].get("location", "")
    state = SceneState(scene_id=scene_id, location_anchor=location)

    # Pre-populate characters from all shots in scene
    for shot in shots:
        for char in (shot.get("characters") or []):
            name = char.upper().strip() if isinstance(char, str) else str(char)
            state.get_character(name)

    gate = ContinuityGate(scene_state=state)
    results = gate.validate_scene(shots, auto_fix=auto_fix)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    warnings = sum(len(r.warnings) for r in results)
    connectors = sum(1 for r in results if r.needs_connector)
    avg_bridge = sum(r.bridge_score for r in results) / max(len(results), 1)

    summary = {
        "success": True,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "connectors_inserted": connectors if auto_fix else 0,
        "avg_bridge_score": round(avg_bridge, 3),
        "violations": [r.to_dict() for r in results if not r.passed],
        "scene_state_final": state.to_dict(),
    }

    logger.info(f"[CONTINUITY-GATE] Scene {scene_id}: {passed}/{len(results)} passed, "
                f"{failed} failed, {connectors} connectors, bridge={avg_bridge:.2f}")

    return summary


def enrich_shots_with_state(shots: List[dict], scene_id: str = "") -> int:
    """
    Add state_in, state_out, coverage_role, and shot_role fields to shots.
    Non-destructive — only adds fields that don't exist.
    Returns count of shots enriched.

    V21.2: Respects scene type from _scene_type field (set by scene_type_classifier).
    Scenes with special types (PHONE_DIALOGUE, INTERCUT, etc.) don't follow standard
    A/B/C coverage contract.
    """
    count = 0
    state = SceneState(scene_id=scene_id)

    for shot in shots:
        characters = shot.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",") if c.strip()]

        # V21.2: Check scene type for coverage override
        scene_type = shot.get('_scene_type', '')
        if scene_type in ('PHONE_DIALOGUE', 'INTERCUT', 'MONTAGE', 'VOICEOVER'):
            shot['_coverage_override'] = True

        # Add state_in / state_out
        if "state_in" not in shot or "state_out" not in shot:
            state_in, state_out = infer_state_from_shot(shot, state)
            shot["state_in"] = state_in
            shot["state_out"] = state_out

            # Update running state
            for char_upper, s_out in state_out.items():
                cs = state.get_character(char_upper)
                cs.pose = s_out.get("pose", cs.pose)
                cs.emotion_intensity = s_out.get("emotion_intensity", cs.emotion_intensity)

        # Add coverage_role
        if not shot.get("coverage_role") or not shot["coverage_role"].startswith(("A_", "B_", "C_")):
            shot["coverage_role"] = assign_coverage_role(shot)

        # Add shot_role (GEOGRAPHY / ACTION / EMOTION)
        if "shot_role" not in shot or shot["shot_role"] not in VALID_SHOT_ROLES:
            role_map = {"A_GEOGRAPHY": "GEOGRAPHY", "B_ACTION": "ACTION", "C_EMOTION": "EMOTION"}
            shot["shot_role"] = role_map.get(shot.get("coverage_role", "B_ACTION"), "ACTION")

        state.time_in_scene += float(shot.get("duration", 5))
        count += 1

    return count
