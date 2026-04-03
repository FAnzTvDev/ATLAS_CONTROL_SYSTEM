#!/usr/bin/env python3
"""
ATLAS V28 — SHOT TRUTH CONTRACT
=================================
The canonical object that turns Claude's intelligence into locked runtime directives.

ARCHITECTURE:
  Intelligence Layer (Claude reasoning)
       ↓ compiles into
  Truth Layer (this module — structured, locked, machine-readable)
       ↓ consumed by
  Execution Layer (controller, prompt compiler, FAL calls)

THE PRINCIPLE:
  "Claude should not be the intelligence talking around the system.
   Claude should be the intelligence compiled INTO the system."

  LLM insight is advisory → LLM insight becomes doctrine → doctrine becomes runtime contract.

THREE OBJECTS:
  1. SceneTruthContract  — scene-level locked truth (scene_contract.json)
  2. ShotTruthContract   — per-shot locked truth (fields on shot_plan.json)
  3. TruthGate           — refuses render if truth is missing or corrupted

FIELD OWNERSHIP:
  Truth fields are OWNED by this module. No other system may:
  - Delete them (fix-v16, sanitizer, enricher)
  - Overwrite them without explicit re-authoring
  - Ignore them at render time

  Protected field prefixes: _truth_, _beat_, _eye_line_, _body_, _cut_
  Protected fields: _scene_contract_version, _truth_locked, _truth_hash

WHEN TO RUN:
  After story bible + fix-v16 + beat_enrichment, BEFORE any generation.
  Part of the Production Workflow as the MANDATORY truth compilation step.
  The V26 controller MUST call TruthGate.validate_shot() before FAL.
"""

import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# PROTECTED FIELDS — These cannot be stripped by downstream systems
# ═══════════════════════════════════════════════════════════════════

TRUTH_OWNED_FIELDS = {
    # Beat enrichment (from beat_enrichment.py)
    "_beat_ref",
    "_beat_index",
    "_beat_description",
    "_beat_action",
    "_beat_dialogue",
    "_beat_atmosphere",
    "_beat_enriched",
    # Cinematographic truth (from this module)
    "_eye_line_target",
    "_body_direction",
    "_cut_motivation",
    "_movement_state",
    "_emotional_state",
    "_prop_focus",
    "_story_purpose",
    "_blocking_direction",
    "_frame_reason",
    # Contract metadata
    "_truth_locked",
    "_truth_hash",
    "_truth_version",
    "_scene_contract_version",
    "_truth_authored_at",
}

# Fields that must be present for a shot to be render-ready
REQUIRED_TRUTH_FIELDS = {
    "_beat_ref",          # Which story beat this shot serves
    "_eye_line_target",   # Where the character is looking
    "_body_direction",    # What the body is doing
    "_cut_motivation",    # WHY the camera cuts here
}

# Fields that SHOULD be present (WARN if missing, don't block)
RECOMMENDED_TRUTH_FIELDS = {
    "_movement_state",    # static / walking / transitioning
    "_emotional_state",   # from beat atmosphere
    "_story_purpose",     # what this shot accomplishes narratively
}


# ═══════════════════════════════════════════════════════════════════
# SCENE TRUTH CONTRACT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SceneTruthContract:
    """
    Scene-level truth authored by intelligence, consumed by runtime.
    Stored as scene_contracts/{scene_id}_contract.json.
    """
    scene_id: str
    version: int = 1
    authored_at: str = ""

    # Story truth
    scene_objective: str = ""           # What this scene accomplishes in the story
    emotional_arc: str = ""             # Start emotion → end emotion
    location_truth: str = ""            # The actual room/space (canonical)
    time_of_day: str = ""
    present_characters: List[str] = field(default_factory=list)
    is_solo_scene: bool = False

    # Beat breakdown
    beats: List[Dict] = field(default_factory=list)     # [{beat_index, description, action, objects}]
    beat_count: int = 0

    # Coverage logic
    required_coverage: List[str] = field(default_factory=list)  # ["establishing", "OTS_pair", "close_up_hero"]
    forbidden_mistakes: List[str] = field(default_factory=list) # ["off-camera partner on solo scene", ...]

    # Visual DNA
    room_type: str = ""                 # foyer, library, study, exterior, etc.
    lighting_anchor: str = ""           # "warm lamplight" / "cold overcast" / etc.
    continuity_anchors: List[str] = field(default_factory=list)  # Props/features that must persist

    # Integrity
    contract_hash: str = ""

    def compute_hash(self) -> str:
        """SHA256 of the contract content (excluding hash field itself)."""
        d = asdict(self)
        d.pop("contract_hash", None)
        d.pop("authored_at", None)
        payload = json.dumps(d, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def lock(self):
        """Finalize and lock the contract."""
        self.authored_at = datetime.now().isoformat()
        self.contract_hash = self.compute_hash()

    def save(self, project_path: str):
        """Save to scene_contracts/{scene_id}_contract.json."""
        out_dir = Path(project_path) / "scene_contracts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self.scene_id}_contract.json"
        self.lock()
        with open(out_path, "w") as f:
            json.dump(asdict(self), f, indent=2)
        return str(out_path)


# ═══════════════════════════════════════════════════════════════════
# SHOT TRUTH FIELDS — Written onto each shot in shot_plan.json
# ═══════════════════════════════════════════════════════════════════

def compute_shot_truth_hash(shot: Dict) -> str:
    """Hash the truth fields on a shot for integrity verification."""
    truth_data = {}
    for key in sorted(TRUTH_OWNED_FIELDS):
        if key in shot and key not in ("_truth_hash", "_truth_locked", "_truth_authored_at"):
            truth_data[key] = shot[key]
    payload = json.dumps(truth_data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def stamp_shot_truth(shot: Dict, version: int = 1) -> Dict:
    """Lock truth fields on a shot with hash + version + timestamp."""
    shot["_truth_version"] = version
    shot["_truth_authored_at"] = datetime.now().isoformat()
    shot["_truth_hash"] = compute_shot_truth_hash(shot)
    shot["_truth_locked"] = True
    return shot


def verify_shot_truth_integrity(shot: Dict) -> Tuple[bool, str]:
    """Check if truth fields have been tampered with since locking."""
    if not shot.get("_truth_locked"):
        return True, "not_locked"  # Can't verify unlocked shot
    stored_hash = shot.get("_truth_hash", "")
    current_hash = compute_shot_truth_hash(shot)
    if stored_hash != current_hash:
        return False, f"TAMPERED: stored={stored_hash}, current={current_hash}"
    return True, "intact"


# ═══════════════════════════════════════════════════════════════════
# SCENE CONTRACT GENERATOR
# ═══════════════════════════════════════════════════════════════════

# Room type detection from location text
ROOM_KEYWORDS = {
    "foyer": ["foyer", "entrance", "hall", "entry"],
    "library": ["library", "book", "study", "reading"],
    "drawing_room": ["drawing", "sitting", "parlor", "salon"],
    "bedroom": ["bedroom", "chamber", "boudoir"],
    "kitchen": ["kitchen", "pantry", "scullery"],
    "staircase": ["staircase", "stairs", "landing"],
    "exterior": ["exterior", "garden", "grounds", "yard", "street", "outside"],
    "cemetery": ["cemetery", "grave", "churchyard"],
    "office": ["office", "workspace", "desk"],
}


def detect_room_type(location_text: str) -> str:
    """Detect room type from location text."""
    loc_lower = location_text.lower()
    for room_type, keywords in ROOM_KEYWORDS.items():
        if any(kw in loc_lower for kw in keywords):
            return room_type
    return "interior"  # generic fallback


def generate_scene_contract(
    scene_id: str,
    story_bible_scene: Dict,
    shots: List[Dict],
    cast_map: Dict = None,
) -> SceneTruthContract:
    """
    Generate a SceneTruthContract from story bible + shot plan data.

    This is the Intelligence Layer compiling truth for the Execution Layer.
    """
    contract = SceneTruthContract(scene_id=scene_id)

    # ── Extract from story bible ──
    contract.scene_objective = story_bible_scene.get("scene_summary",
                                story_bible_scene.get("description", ""))
    contract.location_truth = story_bible_scene.get("location", "")
    contract.time_of_day = story_bible_scene.get("time_of_day", "")

    # Characters
    sb_chars = story_bible_scene.get("characters", [])
    for c in sb_chars:
        name = c.get("name", c) if isinstance(c, dict) else str(c)
        if name:
            contract.present_characters.append(name.strip().upper())
    contract.is_solo_scene = len(contract.present_characters) <= 1

    # Emotional arc
    beats_raw = story_bible_scene.get("beats", [])
    contract.beat_count = len(beats_raw)
    if beats_raw:
        first_atmo = ""
        last_atmo = ""
        for b in beats_raw:
            if isinstance(b, dict):
                atmo = b.get("atmosphere", "")
                if atmo and not first_atmo:
                    first_atmo = atmo
                if atmo:
                    last_atmo = atmo
        if first_atmo and last_atmo:
            contract.emotional_arc = f"{first_atmo} → {last_atmo}"

    # Beats breakdown
    for i, b in enumerate(beats_raw):
        if isinstance(b, dict):
            beat_entry = {
                "beat_index": i,
                "description": b.get("description", b.get("beat", "")),
                "character_action": b.get("character_action", ""),
                "dialogue": b.get("dialogue", ""),
                "atmosphere": b.get("atmosphere", ""),
            }
            # Extract objects mentioned
            text = (beat_entry["description"] + " " + beat_entry["character_action"]).lower()
            objects = re.findall(
                r'\b(letter|book|camera|phone|door|window|painting|desk|shelf|photograph|manuscript|note)\b',
                text
            )
            beat_entry["objects"] = list(set(objects))
            contract.beats.append(beat_entry)

    # Room type
    contract.room_type = detect_room_type(contract.location_truth)
    contract.lighting_anchor = _derive_lighting(contract.room_type, contract.time_of_day,
                                                 beats_raw)

    # Coverage logic
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
    shot_types = [s.get("shot_type", "") for s in scene_shots]
    contract.required_coverage = _derive_required_coverage(
        shot_types, contract.is_solo_scene, contract.beat_count
    )

    # Forbidden mistakes
    contract.forbidden_mistakes = _derive_forbidden_mistakes(contract)

    # Continuity anchors (objects/props that must persist)
    all_objects = set()
    for b in contract.beats:
        all_objects.update(b.get("objects", []))
    contract.continuity_anchors = sorted(all_objects)

    contract.lock()
    return contract


def _derive_lighting(room_type: str, time_of_day: str, beats: List) -> str:
    """Derive lighting anchor from room + time + atmosphere."""
    tod = (time_of_day or "").lower()
    if "night" in tod or "evening" in tod:
        if room_type in ("library", "study", "drawing_room"):
            return "warm lamplight, pools of amber on dark wood, deep shadows"
        elif room_type == "exterior":
            return "moonlight, cold blue tones, deep shadows"
        return "warm interior lamplight, amber highlights, dark shadows"
    elif "morning" in tod or "dawn" in tod:
        return "soft morning light, cool tones warming, diffused through curtains"
    elif room_type == "exterior":
        return "natural daylight, overcast diffusion, cool grey-green tones"
    return "warm ambient light, practical lamp sources, natural shadow gradient"


def _derive_required_coverage(shot_types: List[str], is_solo: bool, beat_count: int) -> List[str]:
    """What coverage this scene needs."""
    coverage = ["establishing"]
    if not is_solo:
        coverage.extend(["OTS_pair", "two_shot"])
    if beat_count >= 2:
        coverage.append("close_up_hero")
    if any("b-roll" in t or "insert" in t for t in shot_types):
        coverage.append("narrative_insert")
    return coverage


def _derive_forbidden_mistakes(contract: SceneTruthContract) -> List[str]:
    """Scene-specific things that MUST NOT happen."""
    mistakes = []
    if contract.is_solo_scene:
        mistakes.append("NO off-camera partner direction — character is alone")
        mistakes.append("NO OTS framing — no one to shoot over-the-shoulder of")
    if contract.room_type:
        mistakes.append(f"NO room teleportation — stay in {contract.room_type}")
    if contract.present_characters:
        mistakes.append(f"NO phantom characters — only {', '.join(contract.present_characters)} visible")
    mistakes.append("NO camera-aware eye-lines — character never looks at lens")
    mistakes.append("NO unmotivated cuts — every cut has physical reason")
    return mistakes


# ═══════════════════════════════════════════════════════════════════
# TRUTH COMPILER — Enriches shots with full truth from scene contract
# ═══════════════════════════════════════════════════════════════════

# Movement state vocabulary
MOVEMENT_STATES = {
    "enters": "walking",
    "walks": "walking",
    "crosses": "walking",
    "follows": "walking",
    "steps": "transitioning",
    "moves": "transitioning",
    "approaches": "transitioning",
    "turns": "pivoting",
    "stands": "static",
    "sits": "static",
    "reads": "static",
    "examines": "static",
    "stares": "static",
    "holds": "static",
}

# Story purpose vocabulary
SHOT_PURPOSE_MAP = {
    "establishing": "establish spatial geography and atmosphere",
    "wide": "show full scene context and character positions",
    "medium": "balanced view of character in environment",
    "medium_close": "intimate character focus with environment context",
    "close_up": "emotional intensity, character's inner state visible",
    "reaction": "capture unspoken response to stimulus",
    "insert": "draw attention to narratively significant object",
    "b-roll": "atmospheric texture supporting the scene's mood",
    "over_the_shoulder": "place viewer in conversation, show listener perspective",
    "two_shot": "show relationship dynamic between characters",
    "closing": "resolve scene's visual narrative, transition out",
}


def compile_shot_truth(
    shot: Dict,
    scene_contract: SceneTruthContract,
    scene_shots: List[Dict],
    shot_index_in_scene: int,
) -> Dict:
    """
    Compile full truth onto a shot using the scene contract.

    This runs AFTER beat_enrichment (which provides _beat_ref, _eye_line_target, etc.)
    and ADDS the fields that beat_enrichment doesn't cover:
    - _movement_state
    - _emotional_state
    - _story_purpose
    - _frame_reason
    - _scene_contract_version
    - _blocking_direction
    - _prop_focus

    If beat enrichment fields already exist (_beat_enriched=True), those are PRESERVED.
    This compiler only ADDS, never overwrites beat fields.
    """
    shot_id = shot.get("shot_id", "")
    shot_type = (shot.get("shot_type") or "").lower()

    # ── Movement state ──
    if not shot.get("_movement_state"):
        beat_action = (shot.get("_beat_action") or "").lower()
        movement = "static"  # default
        for keyword, state in MOVEMENT_STATES.items():
            if keyword in beat_action:
                movement = state
                break
        shot["_movement_state"] = movement

    # ── Emotional state ──
    if not shot.get("_emotional_state"):
        atmo = shot.get("_beat_atmosphere") or ""
        if not atmo and scene_contract.beats:
            # Use scene-level emotional context
            beat_idx = shot.get("_beat_index", 0)
            if 0 <= beat_idx < len(scene_contract.beats):
                atmo = scene_contract.beats[beat_idx].get("atmosphere", "")
        shot["_emotional_state"] = atmo if atmo else "neutral"

    # ── Story purpose ──
    if not shot.get("_story_purpose"):
        base_purpose = SHOT_PURPOSE_MAP.get(shot_type, "advance scene narrative")
        # Enrich with beat context
        beat_desc = shot.get("_beat_description", "")
        if beat_desc:
            purpose = f"{base_purpose} — {beat_desc[:80]}"
        else:
            purpose = base_purpose
        shot["_story_purpose"] = purpose

    # ── Prop focus ──
    if not shot.get("_prop_focus"):
        beat_idx = shot.get("_beat_index")
        if beat_idx is not None and 0 <= beat_idx < len(scene_contract.beats):
            objects = scene_contract.beats[beat_idx].get("objects", [])
            if objects:
                shot["_prop_focus"] = ", ".join(objects)

    # ── Blocking direction (for multi-char) ──
    if not shot.get("_blocking_direction"):
        chars = shot.get("characters") or []
        if len(chars) >= 2:
            shot["_blocking_direction"] = "confrontational"  # default for 2-char
        elif len(chars) == 1 and scene_contract.is_solo_scene:
            shot["_blocking_direction"] = "solo_performance"
        elif len(chars) == 0:
            shot["_blocking_direction"] = "empty_environment"

    # ── Frame reason (WHY this frame exists in the edit) ──
    if not shot.get("_frame_reason"):
        cut_motiv = shot.get("_cut_motivation", "")
        story_purpose = shot.get("_story_purpose", "")
        if cut_motiv and story_purpose:
            shot["_frame_reason"] = f"{cut_motiv} | {story_purpose[:60]}"
        elif cut_motiv:
            shot["_frame_reason"] = cut_motiv
        else:
            shot["_frame_reason"] = story_purpose

    # ── Scene contract reference ──
    shot["_scene_contract_version"] = scene_contract.contract_hash

    # ── Fallback: ensure required fields exist even if beat enrichment didn't run ──
    if not shot.get("_beat_ref"):
        # Proportional beat assignment
        num_shots = max(len(scene_shots), 1)
        num_beats = max(scene_contract.beat_count, 1)
        proportion = shot_index_in_scene / max(num_shots - 1, 1)
        beat_idx = min(int(proportion * num_beats), num_beats - 1)
        shot["_beat_ref"] = f"beat_{beat_idx + 1}"
        shot["_beat_index"] = beat_idx

    if not shot.get("_eye_line_target"):
        shot["_eye_line_target"] = "neutral, present in scene"

    if not shot.get("_body_direction"):
        shot["_body_direction"] = "natural micro-movements, breathing"

    if not shot.get("_cut_motivation"):
        if shot_index_in_scene == 0:
            shot["_cut_motivation"] = "SCENE OPEN — establishing geography"
        else:
            shot["_cut_motivation"] = "CONTINUITY — sustaining dramatic beat"

    # ── Lock truth ──
    stamp_shot_truth(shot)

    return shot


# ═══════════════════════════════════════════════════════════════════
# TRUTH GATE — Refuses render if truth is missing or corrupt
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TruthGateResult:
    """Result of truth validation for a single shot."""
    shot_id: str
    passed: bool
    missing_required: List[str] = field(default_factory=list)
    missing_recommended: List[str] = field(default_factory=list)
    integrity_ok: bool = True
    integrity_detail: str = ""

    @property
    def can_render(self) -> bool:
        """True if no REQUIRED fields missing and integrity intact."""
        return self.passed and self.integrity_ok


@dataclass
class SceneTruthGateResult:
    """Result of truth validation for an entire scene."""
    scene_id: str
    shot_results: List[TruthGateResult] = field(default_factory=list)
    has_contract: bool = False
    contract_version: str = ""

    @property
    def can_render(self) -> bool:
        return self.has_contract and all(r.can_render for r in self.shot_results)

    @property
    def blocking_count(self) -> int:
        return sum(1 for r in self.shot_results if not r.can_render)

    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.shot_results if r.missing_recommended)


class TruthGate:
    """
    Validates that shots have required truth fields before rendering.
    Called by the V26 controller BEFORE any FAL call.
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def validate_shot(self, shot: Dict) -> TruthGateResult:
        """Validate a single shot's truth contract."""
        shot_id = shot.get("shot_id", "?")
        result = TruthGateResult(shot_id=shot_id, passed=True)

        # Check required fields
        for field_name in REQUIRED_TRUTH_FIELDS:
            val = shot.get(field_name)
            if val is None or val == "":
                result.missing_required.append(field_name)
                result.passed = False

        # Check recommended fields
        for field_name in RECOMMENDED_TRUTH_FIELDS:
            val = shot.get(field_name)
            if val is None or val == "":
                result.missing_recommended.append(field_name)

        # Check integrity if locked
        if shot.get("_truth_locked"):
            intact, detail = verify_shot_truth_integrity(shot)
            result.integrity_ok = intact
            result.integrity_detail = detail

        return result

    def validate_scene(self, scene_id: str,
                       shots: List[Dict]) -> SceneTruthGateResult:
        """Validate all shots in a scene."""
        result = SceneTruthGateResult(scene_id=scene_id)

        # Check for scene contract
        contract_path = self.project_path / "scene_contracts" / f"{scene_id}_contract.json"
        if contract_path.exists():
            result.has_contract = True
            with open(contract_path) as f:
                contract_data = json.load(f)
            result.contract_version = contract_data.get("contract_hash", "")
        else:
            result.has_contract = False

        # Validate each shot
        scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
        for shot in scene_shots:
            shot_result = self.validate_shot(shot)
            result.shot_results.append(shot_result)

        return result

    def print_report(self, result: SceneTruthGateResult):
        """Print human-readable truth gate report."""
        print(f"\n{'='*70}")
        print(f"  TRUTH GATE — Scene {result.scene_id}")
        print(f"  Contract: {'PRESENT (v' + result.contract_version[:8] + ')' if result.has_contract else 'MISSING'}")
        print(f"  Shots: {len(result.shot_results)} | "
              f"Blocking: {result.blocking_count} | "
              f"Warnings: {result.warn_count}")
        print(f"{'='*70}")

        for sr in result.shot_results:
            status = "PASS" if sr.can_render else "BLOCK"
            warn = f" ({len(sr.missing_recommended)} recommended missing)" if sr.missing_recommended else ""
            print(f"  {'[OK]' if sr.can_render else '[!!]'} {sr.shot_id}: {status}{warn}")
            if sr.missing_required:
                print(f"       MISSING: {', '.join(sr.missing_required)}")
            if not sr.integrity_ok:
                print(f"       INTEGRITY: {sr.integrity_detail}")

        if result.can_render:
            print(f"\n  RESULT: CLEARED for render")
        else:
            reasons = []
            if not result.has_contract:
                reasons.append("No scene contract")
            if result.blocking_count > 0:
                reasons.append(f"{result.blocking_count} shots missing required truth")
            print(f"\n  RESULT: BLOCKED — {'; '.join(reasons)}")
            print(f"  FIX: Run truth compilation: python3 tools/shot_truth_contract.py compile {self.project_path} {result.scene_id}")

        print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════
# FIELD PROTECTION — API for downstream systems
# ═══════════════════════════════════════════════════════════════════

def is_truth_field(field_name: str) -> bool:
    """Check if a field is owned by the truth system."""
    if field_name in TRUTH_OWNED_FIELDS:
        return True
    # Also protect any field starting with _beat_ or _truth_
    if field_name.startswith(("_beat_", "_truth_", "_eye_line_", "_body_", "_cut_")):
        return True
    return False


def protect_truth_fields(shot_before: Dict, shot_after: Dict) -> Dict:
    """
    Restore truth fields if they were stripped by a downstream process.
    Call this AFTER any mutation (fix-v16, sanitizer, enrichment).
    Returns the shot_after with truth fields restored from shot_before.
    """
    if not shot_before.get("_truth_locked") and not shot_before.get("_beat_enriched"):
        return shot_after  # Nothing to protect

    restored_count = 0
    for key, val in shot_before.items():
        if is_truth_field(key) and key not in shot_after:
            shot_after[key] = val
            restored_count += 1

    if restored_count > 0:
        logger.info(f"[TRUTH PROTECT] Restored {restored_count} truth fields on "
                    f"{shot_after.get('shot_id', '?')}")

    return shot_after


def protect_shots_batch(shots_before: List[Dict], shots_after: List[Dict]) -> List[Dict]:
    """Batch protection: restore truth fields across all shots."""
    before_map = {s.get("shot_id", ""): s for s in shots_before}
    for shot in shots_after:
        sid = shot.get("shot_id", "")
        if sid in before_map:
            protect_truth_fields(before_map[sid], shot)
    return shots_after


# ═══════════════════════════════════════════════════════════════════
# COMPILE COMMAND — Full truth compilation for a scene
# ═══════════════════════════════════════════════════════════════════

def compile_scene_truth(project_path: str, scene_id: str) -> Dict:
    """
    Full truth compilation pipeline:
    1. Generate scene contract from story bible
    2. Compile truth onto every shot (preserving existing beat enrichment)
    3. Lock all truth fields with integrity hashes
    4. Save scene contract to disk
    5. Save enriched shot plan back to disk
    """
    project = Path(project_path)

    # Load data
    with open(project / "shot_plan.json") as f:
        sp = json.load(f)
    is_list = isinstance(sp, list)
    shots = sp if is_list else sp.get("shots", [])

    with open(project / "story_bible.json") as f:
        sb = json.load(f)

    cast_map = {}
    cast_path = project / "cast_map.json"
    if cast_path.exists():
        with open(cast_path) as f:
            cast_map = json.load(f)

    # Find story bible scene
    sb_scene = next((s for s in sb.get("scenes", [])
                    if s.get("scene_id") == scene_id), None)
    if not sb_scene:
        return {"status": "FAIL", "reason": f"Scene {scene_id} not in story bible"}

    # Step 1: Generate scene contract
    contract = generate_scene_contract(scene_id, sb_scene, shots, cast_map)
    contract_path = contract.save(project_path)

    # Step 2: Compile truth onto shots
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
    compiled = 0
    for i, shot in enumerate(scene_shots):
        compile_shot_truth(shot, contract, scene_shots, i)
        compiled += 1

    # Step 3: Save shot plan (backup first)
    import shutil
    backup_path = project / f"shot_plan.json.backup_truth_compile_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(project / "shot_plan.json", backup_path)

    if is_list:
        with open(project / "shot_plan.json", "w") as f:
            json.dump(shots, f, indent=2)
    else:
        sp["shots"] = shots
        with open(project / "shot_plan.json", "w") as f:
            json.dump(sp, f, indent=2)

    # Step 4: Validate
    gate = TruthGate(project_path)
    gate_result = gate.validate_scene(scene_id, shots)
    gate.print_report(gate_result)

    print(f"\n  Scene contract saved: {contract_path}")
    print(f"  Shots compiled: {compiled}")
    print(f"  Backup: {backup_path}")
    print(f"  Can render: {'YES' if gate_result.can_render else 'NO'}")

    return {
        "status": "OK" if gate_result.can_render else "BLOCKED",
        "contract_path": contract_path,
        "contract_hash": contract.contract_hash,
        "shots_compiled": compiled,
        "can_render": gate_result.can_render,
        "blocking_shots": gate_result.blocking_count,
        "warning_shots": gate_result.warn_count,
    }


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tools/shot_truth_contract.py compile <project_path> <scene_id>")
        print("  python3 tools/shot_truth_contract.py validate <project_path> <scene_id>")
        print("  python3 tools/shot_truth_contract.py protect <project_path>")
        sys.exit(1)

    command = sys.argv[1]
    project_path = sys.argv[2] if len(sys.argv) > 2 else "pipeline_outputs/victorian_shadows_ep1"

    if command == "compile":
        scene_id = sys.argv[3] if len(sys.argv) > 3 else "002"
        result = compile_scene_truth(project_path, scene_id)
        sys.exit(0 if result.get("can_render") else 1)

    elif command == "validate":
        scene_id = sys.argv[3] if len(sys.argv) > 3 else "002"
        with open(f"{project_path}/shot_plan.json") as f:
            sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])
        gate = TruthGate(project_path)
        result = gate.validate_scene(scene_id, shots)
        gate.print_report(result)
        sys.exit(0 if result.can_render else 1)

    elif command == "protect":
        # Verify all truth fields survived on all shots
        with open(f"{project_path}/shot_plan.json") as f:
            sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])
        locked_count = sum(1 for s in shots if s.get("_truth_locked"))
        enriched_count = sum(1 for s in shots if s.get("_beat_enriched"))
        intact = 0
        tampered = 0
        for s in shots:
            if s.get("_truth_locked"):
                ok, detail = verify_shot_truth_integrity(s)
                if ok:
                    intact += 1
                else:
                    tampered += 1
                    print(f"  TAMPERED: {s.get('shot_id')} — {detail}")
        print(f"\n  Truth protection report:")
        print(f"    Locked shots: {locked_count}")
        print(f"    Beat-enriched: {enriched_count}")
        print(f"    Integrity intact: {intact}")
        print(f"    Tampered: {tampered}")
        sys.exit(0 if tampered == 0 else 1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
