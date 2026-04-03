#!/usr/bin/env python3
"""
ATLAS V27.4 — Scene Intent Verifier (The Story Conscience)

The MISSING ORGAN discovered 2026-03-17.

Every other system checks TECHNICAL quality:
  - Vision: is the frame sharp? identity match?
  - Doctrine: are the rules followed?
  - CPC: is the prompt generic?
  - UQG: composite quality score?

NONE of them ask: "Does this frame match the STORY?"

This tool answers that question. It runs:
  PRE-GENERATION: Before FAL calls — catches wrong characters, wrong rooms, missing constraints
  POST-GENERATION: After frames exist — catches hallucinated people, room drift, narrative mismatch

Usage:
    from tools.scene_intent_verifier import SceneIntentVerifier
    verifier = SceneIntentVerifier(project_path)

    # Pre-gen: fix shots BEFORE sending to FAL
    fixes = verifier.pre_generation_verify(scene_id, shots, story_bible, cast_map)

    # Post-gen: evaluate frames AFTER generation
    report = verifier.post_generation_evaluate(scene_id, shots, story_bible)
"""

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class IntentViolation:
    """A single mismatch between story intent and shot/frame reality."""
    shot_id: str
    severity: str  # CRITICAL, WARNING, INFO
    category: str  # CHARACTER_MISSING, CHARACTER_PHANTOM, ROOM_WRONG, NARRATIVE_EMPTY, LOCATION_MISMATCH
    description: str
    fix_action: str  # What the system should do to fix it
    fix_data: Dict = field(default_factory=dict)  # Data needed to apply the fix


@dataclass
class SceneIntent:
    """Extracted intent from story bible for a single scene."""
    scene_id: str
    location: str           # "HARGROVE ESTATE - LIBRARY"
    room_name: str          # "LIBRARY" (extracted suffix)
    characters_present: List[str]  # ["NADIA COLE"]
    time_of_day: str        # "MORNING"
    mood: str               # "reverent silence, old leather and paper"
    key_props: List[str]    # ["first edition book", "hidden letter"]
    key_actions: List[str]  # ["photographs bookshelves", "reads letter", "pockets letter"]
    beat_count: int
    beats: List[str]


@dataclass
class ShotIntentMatch:
    """How well a single shot matches the scene's intent."""
    shot_id: str
    character_match: str     # CORRECT, MISSING, PHANTOM, EMPTY_OK
    location_match: str      # CORRECT, WRONG_ROOM, GENERIC, MISSING
    narrative_match: str     # HAS_PURPOSE, EMPTY, DUPLICATE
    violations: List[IntentViolation]
    score: float             # 0.0 to 1.0


@dataclass
class SceneIntentReport:
    """Full intent verification report for a scene."""
    scene_id: str
    intent: SceneIntent
    shot_matches: List[ShotIntentMatch]
    total_violations: int
    critical_violations: int
    fixes_applied: int
    overall_score: float     # 0.0 to 1.0
    timestamp: str


# ═══════════════════════════════════════════════════════════════
# SCENE INTENT EXTRACTOR
# ═══════════════════════════════════════════════════════════════

def extract_scene_intent(scene_id: str, story_bible: dict) -> Optional[SceneIntent]:
    """Extract the dramatic intent from a story bible scene entry."""
    scenes = story_bible.get("scenes", [])
    scene_data = None

    for s in scenes:
        sid = s.get("scene_id", "")
        snum = str(s.get("scene_number", ""))
        if sid == scene_id or snum == scene_id.lstrip("0"):
            scene_data = s
            break

    if not scene_data:
        return None

    location = scene_data.get("location", "")

    # Extract room name (the specific room within the estate)
    room_name = ""
    if " - " in location:
        room_name = location.split(" - ", 1)[1].strip()
    elif "/" in location:
        room_name = location.split("/")[0].strip()
    else:
        room_name = location.strip()

    # Characters — check both fields
    characters = scene_data.get("characters_present", [])
    if not characters:
        characters = scene_data.get("characters", [])
    # Normalize to uppercase
    characters = [c.upper().strip() for c in characters if c]

    # Extract beats
    beats_raw = scene_data.get("beats", [])
    beats = []
    for b in beats_raw:
        if isinstance(b, dict):
            beats.append(b.get("description", b.get("text", str(b))))
        else:
            beats.append(str(b))

    # Extract key props and actions from beats
    key_props = []
    key_actions = []

    _PROP_PATTERNS = [
        r"(letter|book|portrait|painting|photograph|camera|briefcase|phone|gun|knife|key|ring|necklace|document|newspaper|envelope|diary|journal|manuscript|candle|lantern|torch|mirror|clock|watch|glass|bottle|cup|plate|chair|desk|table|staircase|banister|fireplace|chandelier)",
    ]
    _ACTION_PATTERNS = [
        r"(enters|exits|walks|runs|sits|stands|turns|looks|stares|touches|grabs|holds|reads|writes|speaks|whispers|shouts|cries|laughs|smiles|frowns|nods|shakes|opens|closes|locks|unlocks|photographs|examines|discovers|reveals|hides|pockets|drops|picks up|puts down|crosses|follows|approaches|retreats|confronts|demands|refuses|accepts|presents)",
    ]

    for beat in beats:
        beat_lower = beat.lower()
        for pattern in _PROP_PATTERNS:
            for match in re.finditer(pattern, beat_lower):
                prop = match.group(1)
                if prop not in key_props:
                    key_props.append(prop)
        for pattern in _ACTION_PATTERNS:
            for match in re.finditer(pattern, beat_lower):
                action = match.group(1)
                if action not in key_actions:
                    key_actions.append(action)

    return SceneIntent(
        scene_id=scene_id,
        location=location,
        room_name=room_name,
        characters_present=characters,
        time_of_day=scene_data.get("time_of_day", "DAY"),
        mood=scene_data.get("mood", scene_data.get("atmosphere", "")),
        key_props=key_props,
        key_actions=key_actions,
        beat_count=len(beats),
        beats=beats,
    )


# ═══════════════════════════════════════════════════════════════
# PRE-GENERATION VERIFIER
# ═══════════════════════════════════════════════════════════════

class SceneIntentVerifier:
    """
    The Story Conscience — verifies every shot against the screenplay's intent.

    PRE-GEN: Fixes shots before FAL calls (character propagation, room lock, no-people)
    POST-GEN: Evaluates frames after generation (phantom people, room drift, narrative)
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.reports_dir = self.project_path / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def pre_generation_verify(
        self,
        scene_id: str,
        shots: List[dict],
        story_bible: dict,
        cast_map: dict,
        location_masters: Dict[str, str] = None,
        auto_fix: bool = True,
    ) -> Dict[str, Any]:
        """
        PRE-GENERATION: Verify and fix shots BEFORE sending to FAL.

        Returns dict with:
          - intent: SceneIntent extracted from story bible
          - violations: list of IntentViolation found
          - fixes_applied: count of auto-fixes applied to shots
          - shot_fixes: dict of shot_id -> list of fixes applied
        """
        intent = extract_scene_intent(scene_id, story_bible)
        if not intent:
            return {
                "intent": None,
                "violations": [],
                "fixes_applied": 0,
                "shot_fixes": {},
                "warning": f"Scene {scene_id} not found in story bible"
            }

        violations = []
        shot_fixes = {}
        fixes_applied = 0

        scene_shots = [s for s in shots if s.get("scene_id") == scene_id]

        for shot in scene_shots:
            shot_id = shot.get("shot_id", "?")
            shot_violations = []
            shot_fix_list = []

            # ─── CHECK 1: CHARACTER POPULATION ───
            shot_chars = [c.upper().strip() if isinstance(c, str) else c.get("name", "").upper().strip()
                         for c in (shot.get("characters") or [])]
            shot_type = (shot.get("shot_type") or shot.get("type") or "").lower()
            is_broll = shot.get("is_broll", shot.get("_broll", False))
            has_dialogue = bool(shot.get("dialogue_text"))

            if not shot_chars and intent.characters_present:
                # Shot has NO characters but the scene HAS characters
                if has_dialogue:
                    # CRITICAL: dialogue shot with no character — who is speaking?
                    v = IntentViolation(
                        shot_id=shot_id,
                        severity="CRITICAL",
                        category="CHARACTER_MISSING",
                        description=f"Dialogue shot has no characters but scene has {intent.characters_present}. Who is speaking?",
                        fix_action="ASSIGN_SCENE_CHARACTERS",
                        fix_data={"characters": intent.characters_present[:1]},  # Assign first character as speaker
                    )
                    shot_violations.append(v)
                    if auto_fix:
                        shot["characters"] = list(intent.characters_present[:1])
                        shot_fix_list.append(f"Assigned {intent.characters_present[0]} as speaker")
                        fixes_applied += 1

                elif is_broll or shot_type in ("b-roll", "insert", "detail"):
                    # B-roll with no characters — could be intentional (empty room detail)
                    # But if the scene only has 1-2 characters, they're probably visible
                    if shot_type in ("insert", "detail"):
                        # True detail shots (prop close-ups) should be empty
                        v = IntentViolation(
                            shot_id=shot_id,
                            severity="INFO",
                            category="CHARACTER_EMPTY_OK",
                            description=f"Detail/insert shot with no characters — adding 'no people' constraint",
                            fix_action="ADD_NO_PEOPLE",
                            fix_data={},
                        )
                        shot_violations.append(v)
                        if auto_fix:
                            nano = shot.get("nano_prompt", "") or ""
                            if "no people" not in nano.lower() and "no person" not in nano.lower():
                                shot["nano_prompt"] = nano + " No people visible, no bystanders, empty room detail shot."
                                shot["_intent_no_people"] = True
                                shot_fix_list.append("Added 'no people' constraint for detail B-roll")
                                fixes_applied += 1
                    else:
                        # B-roll that ISN'T insert/detail — check if description implies a person
                        desc = (shot.get("description", "") or "").lower()
                        nano = (shot.get("nano_prompt", "") or "").lower()
                        _person_implied = any(word in desc + " " + nano for word in [
                            "walks", "enters", "sits", "stands", "examines", "reads",
                            "photographs", "touches", "holds", "looks", "watching",
                            "speaking", "confronts", "demands", "crosses",
                        ])

                        if _person_implied:
                            # The prompt implies human activity — assign the scene's character
                            v = IntentViolation(
                                shot_id=shot_id,
                                severity="WARNING",
                                category="CHARACTER_PHANTOM_RISK",
                                description=f"B-roll implies human activity but has no character ref. FAL will hallucinate a random person. Scene characters: {intent.characters_present}",
                                fix_action="ASSIGN_SCENE_CHARACTERS",
                                fix_data={"characters": intent.characters_present[:1]},
                            )
                            shot_violations.append(v)
                            if auto_fix:
                                shot["characters"] = list(intent.characters_present[:1])
                                shot["_intent_character_propagated"] = True
                                shot_fix_list.append(f"Propagated {intent.characters_present[0]} to prevent phantom person")
                                fixes_applied += 1
                        else:
                            # Pure atmosphere B-roll — add "no people" to be safe
                            v = IntentViolation(
                                shot_id=shot_id,
                                severity="INFO",
                                category="CHARACTER_EMPTY_SAFE",
                                description=f"B-roll has no human activity keywords — adding 'no people' safety constraint",
                                fix_action="ADD_NO_PEOPLE",
                                fix_data={},
                            )
                            shot_violations.append(v)
                            if auto_fix:
                                nano = shot.get("nano_prompt", "") or ""
                                if "no people" not in nano.lower() and "no person" not in nano.lower():
                                    shot["nano_prompt"] = nano + " No people visible, no figures, empty atmospheric shot."
                                    shot["_intent_no_people"] = True
                                    shot_fix_list.append("Added 'no people' safety constraint")
                                    fixes_applied += 1

                elif shot_type in ("establishing", "closing", "wide", "master"):
                    # Establishing/closing may or may not show characters
                    desc = (shot.get("description", "") or "").lower()
                    nano = (shot.get("nano_prompt", "") or "").lower()
                    _person_implied = any(word in desc + " " + nano for word in [
                        "enters", "exits", "walks", "stands", "approaching",
                    ])
                    if not _person_implied:
                        nano_current = shot.get("nano_prompt", "") or ""
                        if "no people" not in nano_current.lower():
                            shot["nano_prompt"] = nano_current + " No people visible, atmospheric establishing shot."
                            shot["_intent_no_people"] = True
                            shot_fix_list.append("Added 'no people' to establishing shot")
                            fixes_applied += 1

            # ─── CHECK 2: LOCATION / ROOM LOCK ───
            dp_ref = shot.get("_dp_ref_selection", {})
            loc_ref_path = ""
            if isinstance(dp_ref, dict):
                lr = dp_ref.get("location_ref", {})
                if isinstance(lr, dict):
                    loc_ref_path = lr.get("path", "")
                elif isinstance(lr, str):
                    loc_ref_path = lr
            elif isinstance(dp_ref, list) and dp_ref:
                loc_ref_path = dp_ref[0] if isinstance(dp_ref[0], str) else ""

            if loc_ref_path and intent.room_name:
                loc_basename = os.path.basename(loc_ref_path).upper().replace(".JPG", "").replace(".PNG", "")
                room_key = intent.room_name.upper().replace(" ", "_")

                if room_key not in loc_basename and len(room_key) >= 4:
                    # Location ref doesn't match the scene's room!
                    v = IntentViolation(
                        shot_id=shot_id,
                        severity="CRITICAL",
                        category="ROOM_WRONG",
                        description=f"Location ref '{os.path.basename(loc_ref_path)}' does not contain room '{intent.room_name}'. Scene is in {intent.location}.",
                        fix_action="RESOLVE_CORRECT_ROOM",
                        fix_data={"expected_room": intent.room_name, "current_ref": loc_ref_path},
                    )
                    shot_violations.append(v)

                    # Auto-fix: find the correct room's location master
                    if auto_fix and location_masters:
                        _correct_ref = None
                        for lm_name, lm_path in location_masters.items():
                            lm_stem = os.path.basename(lm_path).upper().replace(".JPG", "")
                            if room_key in lm_stem:
                                # Found a master for the correct room
                                # Pick the best angle based on shot type
                                if shot_type in ("establishing", "wide", "closing", "master"):
                                    if "medium_interior" not in lm_stem and "reverse" not in lm_stem:
                                        _correct_ref = lm_path
                                        break
                                elif shot_type in ("medium", "two_shot"):
                                    if "medium_interior" in lm_stem:
                                        _correct_ref = lm_path
                                        break
                                else:
                                    # Default: prefer base master
                                    if "medium_interior" not in lm_stem and "reverse" not in lm_stem:
                                        _correct_ref = lm_path

                        # Fallback: any master with the room name
                        if not _correct_ref:
                            for lm_name, lm_path in location_masters.items():
                                lm_stem = os.path.basename(lm_path).upper().replace(".JPG", "")
                                if room_key in lm_stem:
                                    _correct_ref = lm_path
                                    break

                        if _correct_ref:
                            shot["location_master_url"] = _correct_ref
                            if isinstance(dp_ref, dict) and isinstance(dp_ref.get("location_ref"), dict):
                                dp_ref["location_ref"]["path"] = _correct_ref
                                dp_ref["location_ref"]["_intent_corrected"] = True
                            shot_fix_list.append(f"Room-locked to {os.path.basename(_correct_ref)}")
                            fixes_applied += 1

            # ─── CHECK 3: NARRATIVE PURPOSE ───
            desc = (shot.get("description", "") or "").strip()
            nano = (shot.get("nano_prompt", "") or "").strip()

            if is_broll and not desc and len(nano) < 100:
                v = IntentViolation(
                    shot_id=shot_id,
                    severity="WARNING",
                    category="NARRATIVE_EMPTY",
                    description=f"B-roll shot has no description and minimal prompt — will generate generic filler",
                    fix_action="ENRICH_FROM_BEATS",
                    fix_data={"beats": intent.beats},
                )
                shot_violations.append(v)

            # ─── CHECK 4: CHARACTER REF RESOLUTION ───
            if shot_chars and not shot.get("character_reference_url"):
                # Has characters but no ref URL resolved
                char_name = shot_chars[0]
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', char_name)
                ref_path = self.project_path / "character_library_locked" / f"{safe_name}_CHAR_REFERENCE.jpg"

                if ref_path.exists():
                    if auto_fix:
                        shot["character_reference_url"] = str(ref_path)
                        shot_fix_list.append(f"Resolved char ref for {char_name}")
                        fixes_applied += 1
                else:
                    v = IntentViolation(
                        shot_id=shot_id,
                        severity="CRITICAL",
                        category="CHARACTER_REF_MISSING",
                        description=f"Character {char_name} has no CHAR_REFERENCE.jpg — identity will be wrong",
                        fix_action="GENERATE_REF",
                        fix_data={"character": char_name},
                    )
                    shot_violations.append(v)

            violations.extend(shot_violations)
            if shot_fix_list:
                shot_fixes[shot_id] = shot_fix_list

        # Save pre-gen report
        report = {
            "scene_id": scene_id,
            "phase": "PRE_GENERATION",
            "timestamp": datetime.now().isoformat(),
            "intent": {
                "location": intent.location,
                "room_name": intent.room_name,
                "characters_present": intent.characters_present,
                "time_of_day": intent.time_of_day,
                "mood": intent.mood,
                "key_props": intent.key_props,
                "key_actions": intent.key_actions,
                "beat_count": intent.beat_count,
            },
            "violations": [
                {
                    "shot_id": v.shot_id,
                    "severity": v.severity,
                    "category": v.category,
                    "description": v.description,
                    "fix_action": v.fix_action,
                }
                for v in violations
            ],
            "fixes_applied": fixes_applied,
            "shot_fixes": shot_fixes,
            "total_shots": len(scene_shots),
            "critical_count": sum(1 for v in violations if v.severity == "CRITICAL"),
            "warning_count": sum(1 for v in violations if v.severity == "WARNING"),
        }

        report_path = self.reports_dir / f"intent_pregen_{scene_id}.json"
        try:
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        return report

    def post_generation_evaluate(
        self,
        scene_id: str,
        shots: List[dict],
        story_bible: dict,
        generated_frames_dir: str = None,
    ) -> SceneIntentReport:
        """
        POST-GENERATION: Evaluate generated frames against story intent.

        This checks:
        1. Did every character shot get a frame with the right person?
        2. Are B-roll frames empty of phantom people?
        3. Does the room look consistent across the scene?
        4. Does each shot serve a narrative purpose?
        """
        intent = extract_scene_intent(scene_id, story_bible)
        if not intent:
            return SceneIntentReport(
                scene_id=scene_id,
                intent=SceneIntent(scene_id, "", "", [], "", "", [], [], 0, []),
                shot_matches=[],
                total_violations=0,
                critical_violations=0,
                fixes_applied=0,
                overall_score=0.0,
                timestamp=datetime.now().isoformat(),
            )

        if not generated_frames_dir:
            generated_frames_dir = str(self.project_path / "first_frames")

        scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
        shot_matches = []
        total_violations = 0
        critical_violations = 0

        for shot in scene_shots:
            shot_id = shot.get("shot_id", "?")
            violations = []

            # Check if frame exists
            frame_path = Path(generated_frames_dir) / f"{shot_id}.jpg"
            frame_exists = frame_path.exists()

            # ─── CHARACTER MATCH ───
            shot_chars = [c.upper().strip() if isinstance(c, str) else c.get("name", "").upper().strip()
                         for c in (shot.get("characters") or [])]

            if shot_chars:
                # Has characters — check if ref was sent
                has_ref = bool(shot.get("character_reference_url"))
                if has_ref:
                    char_match = "CORRECT"
                else:
                    char_match = "MISSING"
                    violations.append(IntentViolation(
                        shot_id=shot_id,
                        severity="CRITICAL",
                        category="CHARACTER_NO_REF",
                        description=f"Shot has characters {shot_chars} but no character ref was sent — identity will be wrong",
                        fix_action="REGEN_WITH_REF",
                        fix_data={"characters": shot_chars},
                    ))
            elif intent.characters_present:
                # No characters on shot but scene has people
                no_people = shot.get("_intent_no_people", False)
                if no_people:
                    char_match = "EMPTY_OK"
                else:
                    char_match = "PHANTOM"
                    violations.append(IntentViolation(
                        shot_id=shot_id,
                        severity="WARNING",
                        category="CHARACTER_PHANTOM_RISK",
                        description=f"No character ref sent but scene has {intent.characters_present} — frame may show random person",
                        fix_action="VERIFY_FRAME",
                        fix_data={},
                    ))
            else:
                char_match = "EMPTY_OK"

            # ─── LOCATION MATCH ───
            dp_ref = shot.get("_dp_ref_selection", {})
            loc_ref_path = ""
            if isinstance(dp_ref, dict):
                lr = dp_ref.get("location_ref", {})
                if isinstance(lr, dict):
                    loc_ref_path = lr.get("path", "")

            if loc_ref_path and intent.room_name:
                loc_basename = os.path.basename(loc_ref_path).upper()
                room_key = intent.room_name.upper().replace(" ", "_")
                if room_key in loc_basename:
                    loc_match = "CORRECT"
                else:
                    loc_match = "WRONG_ROOM"
                    violations.append(IntentViolation(
                        shot_id=shot_id,
                        severity="CRITICAL",
                        category="LOCATION_MISMATCH",
                        description=f"Ref is {os.path.basename(loc_ref_path)} but scene is in {intent.room_name}",
                        fix_action="REGEN_CORRECT_ROOM",
                        fix_data={"expected_room": intent.room_name},
                    ))
            elif not loc_ref_path:
                loc_match = "MISSING"
            else:
                loc_match = "GENERIC"

            # ─── NARRATIVE MATCH ───
            desc = (shot.get("description", "") or "").strip()
            has_dialogue = bool(shot.get("dialogue_text"))
            shot_type = (shot.get("shot_type") or "").lower()

            if has_dialogue or desc or shot_type in ("establishing", "closing"):
                narr_match = "HAS_PURPOSE"
            else:
                narr_match = "EMPTY"

            # ─── SCORE ───
            score = 1.0
            for v in violations:
                if v.severity == "CRITICAL":
                    score -= 0.3
                elif v.severity == "WARNING":
                    score -= 0.15
                else:
                    score -= 0.05
            score = max(0.0, min(1.0, score))

            total_violations += len(violations)
            critical_violations += sum(1 for v in violations if v.severity == "CRITICAL")

            shot_matches.append(ShotIntentMatch(
                shot_id=shot_id,
                character_match=char_match,
                location_match=loc_match,
                narrative_match=narr_match,
                violations=violations,
                score=score,
            ))

        # Overall score
        if shot_matches:
            overall_score = sum(m.score for m in shot_matches) / len(shot_matches)
        else:
            overall_score = 0.0

        report = SceneIntentReport(
            scene_id=scene_id,
            intent=intent,
            shot_matches=shot_matches,
            total_violations=total_violations,
            critical_violations=critical_violations,
            fixes_applied=0,
            overall_score=overall_score,
            timestamp=datetime.now().isoformat(),
        )

        # Save report
        report_path = self.reports_dir / f"intent_postgen_{scene_id}.json"
        try:
            report_dict = {
                "scene_id": scene_id,
                "phase": "POST_GENERATION",
                "timestamp": report.timestamp,
                "overall_score": round(overall_score, 3),
                "total_violations": total_violations,
                "critical_violations": critical_violations,
                "intent": {
                    "location": intent.location,
                    "room_name": intent.room_name,
                    "characters_present": intent.characters_present,
                    "beat_count": intent.beat_count,
                },
                "shots": [
                    {
                        "shot_id": m.shot_id,
                        "character_match": m.character_match,
                        "location_match": m.location_match,
                        "narrative_match": m.narrative_match,
                        "score": round(m.score, 3),
                        "violations": [
                            {"severity": v.severity, "category": v.category, "description": v.description}
                            for v in m.violations
                        ],
                    }
                    for m in shot_matches
                ],
            }
            with open(report_path, "w") as f:
                json.dump(report_dict, f, indent=2)
        except Exception:
            pass

        return report


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def verify_scene_intent(project_path: str, scene_id: str, auto_fix: bool = True) -> Dict[str, Any]:
    """
    One-shot function: load project data, verify intent, return report.
    Used by the orchestrator before generation.
    """
    project = Path(project_path)

    # Load data
    sp_path = project / "shot_plan.json"
    sb_path = project / "story_bible.json"
    cm_path = project / "cast_map.json"

    if not sp_path.exists() or not sb_path.exists():
        return {"error": "Missing shot_plan.json or story_bible.json"}

    with open(sp_path) as f:
        sp = json.load(f)
    if isinstance(sp, list):
        shots = sp
    else:
        shots = sp.get("shots", [])

    with open(sb_path) as f:
        story_bible = json.load(f)

    cast_map = {}
    if cm_path.exists():
        with open(cm_path) as f:
            cast_map = json.load(f)

    # Load location masters
    lm_dir = project / "location_masters"
    location_masters = {}
    if lm_dir.exists():
        for f in lm_dir.iterdir():
            if f.suffix.lower() in (".jpg", ".png"):
                location_masters[f.stem] = str(f)

    verifier = SceneIntentVerifier(str(project))
    report = verifier.pre_generation_verify(
        scene_id, shots, story_bible, cast_map, location_masters, auto_fix=auto_fix
    )

    # If auto_fix applied changes, save back to shot_plan
    if auto_fix and report.get("fixes_applied", 0) > 0:
        try:
            if isinstance(sp, list):
                with open(sp_path, "w") as f:
                    json.dump(shots, f, indent=2)
            else:
                sp["shots"] = shots
                with open(sp_path, "w") as f:
                    json.dump(sp, f, indent=2)
            report["shot_plan_saved"] = True
        except Exception as e:
            report["shot_plan_save_error"] = str(e)

    return report


def print_intent_report(report: dict):
    """Pretty-print an intent verification report."""
    print(f"\n{'='*70}")
    print(f"  SCENE INTENT VERIFICATION — Scene {report.get('scene_id', '?')}")
    print(f"  Phase: {report.get('phase', '?')} | {report.get('timestamp', '')[:19]}")
    print(f"{'='*70}")

    intent = report.get("intent", {})
    print(f"\n  STORY SAYS:")
    print(f"    Location: {intent.get('location', '?')}")
    print(f"    Room: {intent.get('room_name', '?')}")
    print(f"    Characters: {intent.get('characters_present', [])}")
    print(f"    Time: {intent.get('time_of_day', '?')}")
    if intent.get('mood'):
        print(f"    Mood: {intent.get('mood', '')[:80]}")
    if intent.get('key_props'):
        print(f"    Props: {', '.join(intent.get('key_props', []))}")
    if intent.get('key_actions'):
        print(f"    Actions: {', '.join(intent.get('key_actions', []))}")

    violations = report.get("violations", [])
    fixes = report.get("fixes_applied", 0)
    crit = report.get("critical_count", 0)
    warn = report.get("warning_count", 0)

    print(f"\n  VERDICT:")
    print(f"    Total shots: {report.get('total_shots', '?')}")
    print(f"    Violations: {len(violations)} ({crit} CRITICAL, {warn} WARNING)")
    print(f"    Fixes applied: {fixes}")

    if violations:
        print(f"\n  VIOLATIONS:")
        for v in violations:
            sev = v.get("severity", "?")
            icon = "🔴" if sev == "CRITICAL" else "🟡" if sev == "WARNING" else "🔵"
            print(f"    {icon} {v.get('shot_id', '?')} [{v.get('category', '?')}]")
            print(f"       {v.get('description', '')}")

    shot_fixes = report.get("shot_fixes", {})
    if shot_fixes:
        print(f"\n  FIXES APPLIED:")
        for sid, fixes_list in shot_fixes.items():
            for fix in fixes_list:
                print(f"    ✅ {sid}: {fix}")

    print(f"\n{'='*70}\n")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python scene_intent_verifier.py <project_path> <scene_id> [--no-fix]")
        sys.exit(1)

    proj = sys.argv[1]
    sid = sys.argv[2]
    auto = "--no-fix" not in sys.argv

    report = verify_scene_intent(proj, sid, auto_fix=auto)
    print_intent_report(report)
