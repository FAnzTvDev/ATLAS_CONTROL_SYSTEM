#!/usr/bin/env python3
"""
ATLAS V27.1.1 — OTS Dialogue Enforcer
======================================
Root cause from probe 001_005B: FAL doesn't understand character NAMES.
It sees image_urls and a text prompt. If the prompt says "THOMAS faces camera"
but Eleanor's ref is more visually prominent, the model renders Eleanor facing camera.

This module enforces 3 things:

1. SPEAKER-FIRST REF ORDERING
   image_urls[0] = speaker's ref (face the model should render facing camera)
   image_urls[1] = listener's ref (back-to-camera/shoulder)
   image_urls[2+] = location

2. APPEARANCE-BASED PROMPTING
   Replace "THOMAS BLACKWOOD faces camera" with:
   "The man with silver hair, 62, wearing a navy suit faces camera and speaks"
   FAL models respond to DESCRIPTIONS, not NAMES.

3. POST-GEN VISION GATE
   After generation: ArcFace score the visible face against SPEAKER ref.
   If speaker_similarity < threshold: REJECT and flag for regen.

Usage:
    from tools.ots_enforcer import OTSEnforcer
    enforcer = OTSEnforcer(cast_map)

    # Pre-gen: reorder refs + rewrite prompt
    shot = enforcer.prepare_ots_shot(shot)

    # Post-gen: verify correct person faces camera
    result = enforcer.verify_ots_frame(frame_path, shot)
"""

import re
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OTSEnforcer:
    """Enforces OTS dialogue framing: speaker faces camera, listener back-to-camera.

    V27.1.4c: Now includes SCREEN POSITION LOCK — once the first OTS establishes
    which character is on which side of frame, ALL subsequent shots in that dialogue
    sequence maintain the same positions. This is the 180° rule applied to character
    identity across the full shot sequence.
    """

    def __init__(self, cast_map: Dict):
        self.cast_map = cast_map
        # V27.1.4c: Screen position map — character → "left" or "right"
        # Established by first OTS in a dialogue sequence, consumed by all others
        self._screen_positions = {}  # {"THOMAS BLACKWOOD": "right", "ELEANOR VOSS": "left"}
        # V27.6: Scene character context — is this a solo scene?
        # Solo scenes (1 unique character) should NEVER have off-camera partner direction.
        # Dialogue in solo scenes = reading aloud, muttering, examining, narrating.
        self._scene_unique_characters = set()
        self._is_solo_scene = False

    def set_scene_context(self, scene_shots: List[Dict] = None, story_bible_scene: Dict = None):
        """
        V27.6: Set scene-level context so dialogue handlers know whether this is
        a solo scene (1 character alone) or multi-character conversation.

        CRITICAL: Without this, prepare_solo_dialogue_closeup() assumes EVERY dialogue
        shot has an off-camera partner, causing phantom OTS shoulders in solo scenes.
        Production evidence: 002_017B (Nadia alone in library reading book titles)
        generated with "speaking to someone off-camera left" → phantom shoulder in frame.

        Sources (priority order):
        1. story_bible_scene["characters"] — authoritative character list
        2. Unique characters across all scene_shots — fallback
        """
        self._scene_unique_characters = set()

        # Priority 1: story bible scene characters
        if story_bible_scene:
            sb_chars = story_bible_scene.get("characters", [])
            if isinstance(sb_chars, list):
                for c in sb_chars:
                    name = c.get("name", c) if isinstance(c, dict) else str(c)
                    if name:
                        self._scene_unique_characters.add(name.strip().upper())

        # Priority 2: scan all shots in scene for unique characters
        if not self._scene_unique_characters and scene_shots:
            for shot in scene_shots:
                for c in (shot.get("characters") or []):
                    name = c.get("name", c) if isinstance(c, dict) else str(c)
                    if name:
                        self._scene_unique_characters.add(name.strip().upper())

        self._is_solo_scene = len(self._scene_unique_characters) <= 1
        if self._is_solo_scene:
            chars_str = ", ".join(self._scene_unique_characters) or "NONE"
            logger.info(f"[V27.6 SCENE CONTEXT] SOLO SCENE detected — characters: {chars_str}. "
                       f"No off-camera partner direction will be used.")
        else:
            logger.info(f"[V27.6 SCENE CONTEXT] Multi-character scene — "
                       f"{len(self._scene_unique_characters)} characters: "
                       f"{', '.join(sorted(self._scene_unique_characters))}")

    def establish_screen_positions(self, shots: List[Dict]) -> Dict[str, str]:
        """
        V27.1.4c: Scan the shot list for the FIRST OTS shot and establish
        character screen positions. These positions are LOCKED for the entire
        dialogue sequence.

        In OTS A-angle: speaker is FRAME-RIGHT, listener is FRAME-LEFT.
        Once set, these positions propagate to two-shots, close-ups, etc.

        Returns: {"CHARACTER_NAME": "left"|"right"}
        """
        for shot in shots:
            shot_type = (shot.get("shot_type") or "").lower()
            if "over_the_shoulder" not in shot_type and "ots" not in shot_type:
                continue
            characters = shot.get("characters") or []
            if len(characters) < 2:
                continue

            speaker, listener = self.identify_speaker(shot)
            if not speaker or not listener:
                continue

            # OTS A-angle convention: speaker FRAME-RIGHT, listener FRAME-LEFT
            # This establishes the 180° line for the entire dialogue
            angle = shot.get("_ots_angle", "")
            if not angle:
                # Compute it: if speaker == characters[0] → A, else B
                speaker_upper = speaker.upper().strip()
                char0 = (characters[0] if isinstance(characters[0], str) else characters[0].get("name", "")).upper().strip()
                angle = "B" if speaker_upper != char0 else "A"

            if angle == "A":
                # A-angle: speaker right, listener left
                self._screen_positions[speaker.upper()] = "right"
                self._screen_positions[listener.upper()] = "left"
            else:
                # B-angle: speaker left, listener right (mirror)
                # BUT the underlying spatial truth is the SAME — character positions don't change
                # B-angle just shows the reverse camera. The A-angle sets the canonical positions.
                # So we skip B and keep looking for A.
                continue

            print(f"  [POSITION LOCK] Established from {shot.get('shot_id')} ({angle}): "
                  f"{speaker.upper()}=RIGHT, {listener.upper()}=LEFT", flush=True)
            logger.info(f"[POSITION LOCK] Established from {shot.get('shot_id')} ({angle}): "
                        f"{speaker}=RIGHT, {listener}=LEFT")
            break

        if not self._screen_positions:
            print(f"  [POSITION LOCK] WARNING: No OTS A-angle found in {len(shots)} shots — positions unlocked", flush=True)
        return self._screen_positions

    def get_screen_position(self, char_name: str) -> Optional[str]:
        """Get a character's locked screen position ('left' or 'right')."""
        return self._screen_positions.get(char_name.upper().strip())

    def identify_speaker(self, shot: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Identify who is SPEAKING in this shot.
        Returns (speaker_name, listener_name) or (None, None).
        """
        dialogue = shot.get("dialogue_text", "")
        characters = shot.get("characters") or []

        if not dialogue or not characters:
            return None, None

        # Find which character name appears in dialogue attribution
        speaker = None
        for char in characters:
            # Check for "CHARACTER:" or "CHARACTER says" patterns
            if char.upper() + ":" in dialogue.upper() or char.upper() + " SAYS" in dialogue.upper():
                speaker = char
                break

        if not speaker and characters:
            # Fallback: first character listed is assumed speaker
            speaker = characters[0]

        # Listener is the other character
        listener = None
        for char in characters:
            if char != speaker:
                listener = char
                break

        return speaker, listener

    def get_appearance_description(self, character_name: str) -> str:
        """Get physical appearance from cast_map for a character."""
        char_data = self.cast_map.get(character_name, {})
        if not isinstance(char_data, dict):
            return character_name

        appearance = char_data.get("appearance", "")
        if appearance:
            return appearance

        # Build from available fields
        parts = []
        age = char_data.get("age", "")
        gender = char_data.get("gender", "")
        if gender:
            parts.append(gender)
        if age:
            parts.append(str(age))

        hair = char_data.get("hair", char_data.get("hair_color", ""))
        if hair:
            parts.append(f"{hair} hair")

        build = char_data.get("build", "")
        if build:
            parts.append(build)

        return ", ".join(parts) if parts else character_name

    def reorder_refs_speaker_first(self, shot: Dict) -> Dict:
        """
        ENFORCEMENT 1: Reorder image_urls so speaker's ref is FIRST.

        FAL models give visual priority to image_urls[0].
        If the speaker's ref is first, the model is more likely to render
        that face prominently (facing camera).
        """
        fal_urls = shot.get("_fal_image_urls_resolved", [])
        if not fal_urls or len(fal_urls) < 2:
            return shot

        speaker, listener = self.identify_speaker(shot)
        if not speaker:
            return shot

        speaker_key = speaker.replace(" ", "_")
        listener_key = listener.replace(" ", "_") if listener else ""

        # Classify each URL
        speaker_urls = []
        listener_urls = []
        location_urls = []

        for url in fal_urls:
            basename = os.path.basename(url).upper()
            if speaker_key.upper() in basename:
                speaker_urls.append(url)
            elif listener_key and listener_key.upper() in basename:
                listener_urls.append(url)
            else:
                location_urls.append(url)

        # Reorder: speaker FIRST, then listener, then location
        new_order = speaker_urls + listener_urls + location_urls
        if new_order != fal_urls:
            logger.info(f"[OTS] Reordered refs for {shot.get('shot_id')}: "
                        f"speaker={speaker} first ({len(speaker_urls)} refs)")
            shot["_fal_image_urls_resolved"] = new_order
            shot["_ots_ref_reordered"] = True
            shot["_ots_speaker"] = speaker
            shot["_ots_listener"] = listener

        return shot

    def rewrite_prompt_appearance_based(self, shot: Dict) -> Dict:
        """
        ENFORCEMENT 2: Replace character NAMES with PHYSICAL DESCRIPTIONS
        in the nano_prompt for OTS shots.

        FAL doesn't know who "THOMAS BLACKWOOD" is. But it DOES understand:
        "The man with silver hair, 62, wearing a navy suit faces camera"
        """
        nano = shot.get("nano_prompt", "")
        if not nano:
            return shot

        speaker, listener = self.identify_speaker(shot)
        if not speaker:
            return shot

        speaker_desc = self.get_appearance_description(speaker)
        listener_desc = self.get_appearance_description(listener) if listener else ""

        # Build OTS-specific prompt header
        # Key insight: describe the SPATIAL RELATIONSHIP using appearance, not names
        shot_type = (shot.get("shot_type") or "").lower()
        is_ots = "over_the_shoulder" in shot_type or "ots" in shot_type

        if is_ots and speaker_desc and listener_desc:
            # Build appearance-based OTS prompt WITH cinematic directives
            # The prompt must include:
            # 1. Who faces camera (appearance, not name)
            # 2. Who is back-to-camera (appearance, not name)
            # 3. Lens/DOF (shallow bokeh is critical for OTS)
            # 4. Atmosphere from the scene (warm/cold, lighting, mood)
            # 5. Cinematic quality anchors

            # Extract atmosphere from original prompt or shot metadata
            location = shot.get("location", "")
            beat = shot.get("beat", shot.get("emotional_beat", ""))

            # Build atmosphere from location context
            atmo_parts = []
            loc_lower = location.lower()
            if any(w in loc_lower for w in ["study", "library", "parlor", "drawing"]):
                atmo_parts.append("Warm candlelight, dark wood paneling, deep amber shadows")
            elif any(w in loc_lower for w in ["foyer", "hall", "entrance", "grand"]):
                atmo_parts.append("Grand Victorian interior, warm lamplight, rich shadows")
            elif any(w in loc_lower for w in ["garden", "exterior", "grounds"]):
                atmo_parts.append("Overcast natural light, mist, muted greens")
            elif any(w in loc_lower for w in ["church", "chapel", "crypt"]):
                atmo_parts.append("Dim stone interior, filtered light through stained glass")
            elif any(w in loc_lower for w in ["bedroom", "chamber"]):
                atmo_parts.append("Intimate lamplight, deep shadows, warm fabrics")
            else:
                atmo_parts.append("Moody interior lighting, rich shadows")

            if "night" in loc_lower:
                atmo_parts.append("night scene")
            elif "evening" in loc_lower or "dusk" in loc_lower:
                atmo_parts.append("golden hour fading to dusk")

            atmosphere = ", ".join(atmo_parts)

            # V27.1.4b: Screen direction flips between A-angle and B-angle
            # This is the 180° rule — the eyeline must cross the screen
            ots_angle = shot.get("_ots_angle", "A")
            if ots_angle == "A":
                # A-ANGLE: listener shoulder FRAME-LEFT, speaker FRAME-RIGHT
                screen_dir = (
                    f"FRAME-LEFT foreground (back to camera, soft-focus shoulder and neck): {listener_desc}. "
                    f"FRAME-RIGHT (facing camera, sharp focus, the subject): {speaker_desc}. "
                    f"Lips parted, speaking with natural rhythm, eye-line directed frame-left toward listener."
                )
            else:
                # B-ANGLE: listener shoulder FRAME-RIGHT, speaker FRAME-LEFT (MIRROR of A)
                screen_dir = (
                    f"FRAME-RIGHT foreground (back to camera, soft-focus shoulder and neck): {listener_desc}. "
                    f"FRAME-LEFT (facing camera, sharp focus, the subject): {speaker_desc}. "
                    f"Lips parted, speaking with natural rhythm, eye-line directed frame-right toward listener."
                )

            # Build the full cinematic OTS prompt
            ots_header = (
                f"Cinematic over-the-shoulder shot, 75mm lens, f/2.0, shallow depth of field. "
                f"{screen_dir} "
                f"The speaker's face is the sharp focal point, background falls into creamy bokeh. "
                f"{atmosphere}. "
                f"Film grain, natural skin tones, no digital sharpening."
            )

            # Extract any useful cinematography from original prompt
            # (preserve lighting/color/mood directives, strip character names)
            cleaned = nano
            # Strip A-ANGLE / B-ANGLE lines
            cleaned = re.sub(
                r'[AB]-ANGLE:.*?(?=\.|$)', '', cleaned, flags=re.IGNORECASE
            ).strip()
            # Strip character name headers
            for char in (shot.get("characters") or []):
                cleaned = re.sub(
                    rf'{re.escape(char)}:', '', cleaned, flags=re.IGNORECASE
                ).strip()
            # Strip "Over-the-shoulder" prefix if it existed
            cleaned = re.sub(
                r'^Over[- ]the[- ]shoulder\s*(shot)?[.,:;]?\s*', '', cleaned, flags=re.IGNORECASE
            ).strip()

            # V27.1.5: RESPECT BAKED PROMPTS — don't overwrite if DNA/timed actions present
            # If the shot already has [ROOM DNA:] or beat-specific content, the baked prompt
            # is SUPERIOR to the generic OTS header. We PREPEND screen direction only.
            _has_baked_content = (
                "[ROOM DNA:" in nano or
                "TIMED CHOREOGRAPHY:" in (shot.get("ltx_motion_prompt","") or "") or
                shot.get("_quality_gate_ready")
            )

            if _has_baked_content:
                # PREPEND screen direction to existing baked prompt (don't destroy it)
                _screen_prefix = f"Cinematic OTS, 75mm f/2.0, shallow DOF. {screen_dir}"
                # Only add screen direction if not already in the prompt
                if "FRAME-LEFT" not in nano and "FRAME-RIGHT" not in nano:
                    shot["nano_prompt"] = f"{_screen_prefix} {nano}"
                shot["_ots_prompt_rewritten"] = True
                logger.info(f"[OTS] PRESERVED baked prompt for {shot.get('shot_id')}, prepended screen direction only")
            else:
                # Original behavior for non-baked prompts
                if cleaned and len(cleaned) > 20:
                    shot["nano_prompt"] = ots_header + " " + cleaned
                else:
                    shot["nano_prompt"] = ots_header
                shot["_ots_prompt_rewritten"] = True

            logger.info(f"[OTS] Rewrote prompt for {shot.get('shot_id')}: "
                        f"appearance-based, speaker={speaker}")

        return shot

    def verify_ots_frame(self, frame_path: str, shot: Dict,
                         vision_models=None) -> Dict:
        """
        ENFORCEMENT 3: Post-generation vision gate.
        Check if the SPEAKER's face is actually facing camera.

        Returns:
            {
                "passed": bool,
                "speaker": str,
                "speaker_similarity": float,
                "listener_similarity": float,
                "verdict": "CORRECT" | "SWAPPED" | "UNCERTAIN",
                "action": "proceed" | "reject_regen" | "review"
            }
        """
        import glob
        from pathlib import Path

        speaker, listener = self.identify_speaker(shot)
        if not speaker:
            return {"passed": True, "verdict": "NO_DIALOGUE", "action": "proceed"}

        # Get vision models
        if vision_models is None:
            try:
                import sys
                sys.path.insert(0, "tools")
                from vision_models import get_vision_models
                vision_models = get_vision_models()
            except ImportError:
                return {"passed": True, "verdict": "NO_VISION", "action": "proceed"}

        # Find refs
        project_dir = os.path.dirname(os.path.dirname(frame_path))
        lib_dir = os.path.join(project_dir, "character_library_locked")

        speaker_key = speaker.replace(" ", "_")
        speaker_refs = glob.glob(os.path.join(lib_dir, f"{speaker_key}*CHAR_REFERENCE*.jpg"))

        listener_key = listener.replace(" ", "_") if listener else ""
        listener_refs = glob.glob(os.path.join(lib_dir, f"{listener_key}*CHAR_REFERENCE*.jpg")) if listener_key else []

        result = {
            "speaker": speaker,
            "listener": listener,
            "speaker_similarity": 0.0,
            "listener_similarity": 0.0,
        }

        # Score speaker's face against frame
        if speaker_refs:
            sim = vision_models.face_similarity(frame_path, speaker_refs[0])
            result["speaker_similarity"] = sim.get("similarity", 0)

        # Score listener's face against frame
        if listener_refs:
            sim = vision_models.face_similarity(frame_path, listener_refs[0])
            result["listener_similarity"] = sim.get("similarity", 0)

        # Verdict
        sp_sim = result["speaker_similarity"]
        li_sim = result["listener_similarity"]

        if sp_sim > li_sim and sp_sim > 0.4:
            result["verdict"] = "CORRECT"
            result["passed"] = True
            result["action"] = "proceed"
        elif li_sim > sp_sim and li_sim > 0.4:
            result["verdict"] = "SWAPPED"
            result["passed"] = False
            result["action"] = "reject_regen"
            result["reason"] = (
                f"Wrong character facing camera. "
                f"Speaker ({speaker}) scored {sp_sim:.3f}, "
                f"Listener ({listener}) scored {li_sim:.3f}. "
                f"Listener's face is more visible — OTS angle is reversed."
            )
        else:
            result["verdict"] = "UNCERTAIN"
            result["passed"] = True  # Don't block on uncertainty
            result["action"] = "review"
            result["reason"] = f"Low confidence: speaker={sp_sim:.3f}, listener={li_sim:.3f}"

        return result


    def assign_ots_angle(self, shot: Dict) -> str:
        """
        V27.1.2: Assign A-angle or B-angle based on speaker position.

        UNIVERSAL RULE:
        - If speaker == characters[0] → A-angle (standard camera position)
        - If speaker == characters[1] → B-angle (reverse camera position)

        This ensures shot/reverse-shot pairs automatically alternate:
        - Shot where character A speaks → camera on side A → standard location ref
        - Shot where character B speaks → camera on side B → reverse_angle location ref

        The audience sees OPPOSITE backgrounds in adjacent OTS shots, which is
        the fundamental rule of dialogue coverage in cinema.
        """
        speaker = shot.get("_ots_speaker", "")
        characters = shot.get("characters") or []
        if not speaker or len(characters) < 2:
            return "A"  # Default to A-angle

        # Normalize for comparison
        speaker_upper = speaker.upper().strip()
        char0_upper = (characters[0] if isinstance(characters[0], str)
                       else characters[0].get("name", "")).upper().strip()
        char1_upper = (characters[1] if isinstance(characters[1], str)
                       else characters[1].get("name", "")).upper().strip()

        if speaker_upper == char1_upper:
            return "B"
        return "A"  # Default: speaker is char[0] or unknown → A-angle

    def resolve_angle_location_ref(self, shot: Dict, location_masters: Dict,
                                    location: str) -> Optional[str]:
        """
        V27.1.2: Select the correct location ref based on OTS angle.

        A-angle → standard/wide/medium_interior location ref (shows side A of room)
        B-angle → reverse_angle location ref (shows side B of room)

        STRATEGY: First check _dp_ref_selection for the known room. Then find
        the matching angle variant of THAT SAME ROOM. This prevents the resolver
        from jumping to a different room in the same estate.

        Args:
            shot: Shot dict with _ots_angle set
            location_masters: Dict of {normalized_name: path} from location_masters/
            location: Shot's location string

        Returns:
            Path to the correct location ref, or None
        """
        import re as _re

        angle = shot.get("_ots_angle", "A")

        # STRATEGY 1: Use _dp_ref_selection to identify the EXACT room, then find
        # the correct angle variant of that room
        dp_sel = shot.get("_dp_ref_selection", {})
        dp_loc_ref = dp_sel.get("location_ref", {})
        dp_loc_path = dp_loc_ref.get("path", "") if isinstance(dp_loc_ref, dict) else ""

        if dp_loc_path:
            # Extract the room identifier from the known path
            # e.g. "HARGROVE_ESTATE___GRAND_FOYER_reverse_angle.jpg" → "HARGROVE_ESTATE___GRAND_FOYER"
            basename = os.path.basename(dp_loc_path).replace(".jpg", "").replace(".png", "")
            room_base = re.sub(r'_(reverse_angle|medium_interior|wide_interior|wide_exterior|detail_insert)$',
                              '', basename, flags=re.IGNORECASE)

            # Now find the correct angle variant of this SAME room
            target_suffix = ""
            if angle == "B":
                target_suffix = "_reverse_angle"
            # A-angle: prefer no suffix (base) or medium_interior

            # Search location_masters for matching room + angle
            candidates = []
            for loc_name, loc_path in location_masters.items():
                path_base = os.path.basename(loc_path).replace(".jpg", "").replace(".png", "")
                path_room = re.sub(r'_(reverse_angle|medium_interior|wide_interior|wide_exterior|detail_insert)$',
                                  '', path_base, flags=re.IGNORECASE)

                # Must be the SAME room
                if path_room.upper().replace(" ", "_") != room_base.upper().replace(" ", "_"):
                    # Also try with different separators
                    pr_norm = path_room.upper().replace(" ", "").replace("_", "").replace("-", "")
                    rb_norm = room_base.upper().replace(" ", "").replace("_", "").replace("-", "")
                    if pr_norm != rb_norm:
                        continue

                # Score by angle preference
                has_reverse = "reverse_angle" in loc_path.lower()
                has_medium = "medium_interior" in loc_path.lower()
                is_base = not has_reverse and not has_medium

                score = 100  # Same room = strong base score
                if angle == "B":
                    if has_reverse:
                        score += 30
                    elif is_base:
                        score -= 20
                else:  # A-angle
                    if is_base:
                        score += 30
                    elif has_medium:
                        score += 15
                    elif has_reverse:
                        score -= 25

                candidates.append((loc_path, score))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                best = candidates[0]
                logger.info(f"[V27.1.2 OTS ANGLE] {shot.get('shot_id')}: "
                            f"angle={angle}, room={room_base} → {os.path.basename(best[0])} (score={best[1]})")
                return best[0]

        # STRATEGY 2 FALLBACK: Generic location matching with angle preference
        loc_upper = location.upper().strip()
        loc_clean = _re.sub(
            r'\s*[-–]\s*(NIGHT|DAY|EVENING|MORNING|AFTERNOON|LATE|DAWN|DUSK|LATER|CONTINUOUS).*$',
            '', loc_upper, flags=_re.IGNORECASE
        ).strip()

        best_match = None
        best_score = 0

        for loc_name, loc_path in location_masters.items():
            loc_name_upper = loc_name.replace(" MASTER", "").strip().upper()
            path_lower = loc_path.lower()

            name_score = 0
            if loc_name_upper == loc_clean:
                name_score = 100
            elif len(loc_name_upper) >= 8 and loc_name_upper in loc_clean:
                name_score = 50 + len(loc_name_upper)
            elif len(loc_clean) >= 8 and loc_clean in loc_name_upper:
                name_score = 40 + len(loc_clean)

            if name_score < 40:
                continue

            has_reverse = "reverse_angle" in path_lower
            is_base = not has_reverse and "medium_interior" not in path_lower

            if angle == "B":
                if has_reverse:
                    name_score += 20
                elif is_base:
                    name_score -= 10
            else:
                if is_base:
                    name_score += 20
                elif has_reverse:
                    name_score -= 15

            if name_score > best_score:
                best_match = loc_path
                best_score = name_score

        if best_match and best_score >= 40:
            logger.info(f"[V27.1.2 OTS ANGLE FALLBACK] {shot.get('shot_id')}: "
                        f"angle={angle} → {os.path.basename(best_match)} (score={best_score})")
            return best_match

        return None

    def compile_video_prompt(self, shot: Dict) -> str:
        """
        V27.1.2: Compile a CLEAN video prompt (ltx_motion_prompt) for OTS dialogue shots.

        Replaces the corrupted/stacked prompt with a fresh build that includes:
        1. Appearance-based character descriptions (not names)
        2. Full dialogue text with timing
        3. Performance direction (mouth movement, gestures, emotion)
        4. Camera/framing directives
        5. Anti-morphing constraints

        This runs at generation time in the orchestrator, REPLACING whatever
        ltx_motion_prompt was stored on the shot (which may be corrupted from
        multiple fix-v16 passes stacking dialogue markers).
        """
        speaker = shot.get("_ots_speaker", "")
        listener = shot.get("_ots_listener", "")
        dialogue = shot.get("dialogue_text", "")
        duration = shot.get("duration", 10)
        beat = shot.get("beat", shot.get("emotional_beat", ""))
        angle = shot.get("_ots_angle", "A")

        if not speaker or not dialogue:
            return shot.get("ltx_motion_prompt", "")

        # V27.1.5: RESPECT BAKED TIMED CHOREOGRAPHY
        # If the shot already has timed per-second actions, the baked ltx is SUPERIOR
        # to this generic compile. Only add screen direction if missing.
        existing_ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in existing_ltx and shot.get("_quality_gate_ready"):
            # Baked prompt is superior — only ensure screen direction is present
            if "frame-left" not in existing_ltx.lower() and "frame-right" not in existing_ltx.lower():
                _dir_prefix = ""
                if angle == "A":
                    _dir_prefix = f"OTS A-angle: listener shoulder frame-left, speaker frame-right facing camera. "
                else:
                    _dir_prefix = f"OTS B-angle: listener shoulder frame-right, speaker frame-left facing camera. "
                return f"{_dir_prefix}{existing_ltx}"
            logger.info(f"[V27.1.5] PRESERVED baked timed choreography for {shot.get('shot_id')}")
            return existing_ltx

        # Get appearance descriptions
        speaker_desc = self.get_appearance_description(speaker)
        listener_desc = self.get_appearance_description(listener) if listener else ""

        # Extract clean dialogue text (strip attribution markers)
        clean_dialogue = dialogue
        for char in (shot.get("characters") or []):
            # Remove "CHARACTER:" prefixes
            clean_dialogue = re.sub(
                rf'{re.escape(char)}\s*:\s*', '', clean_dialogue, flags=re.IGNORECASE
            )
        # Remove pipe continuations and extra whitespace
        clean_dialogue = clean_dialogue.replace("|", " ").strip()
        clean_dialogue = re.sub(r'\s+', ' ', clean_dialogue)
        # Cap at 200 chars for video prompt
        if len(clean_dialogue) > 200:
            clean_dialogue = clean_dialogue[:197] + "..."

        # V27.1.4e: Get physical action — prefer story bible character_action (narrative gold)
        beat_action = shot.get("_beat_character_action", "")
        emotion_action = "speaks with conviction"
        if beat_action and len(beat_action) > 10:
            # Story bible has exact stage direction — use it
            emotion_action = beat_action[:100].strip()
        elif beat:
            try:
                from tools.kling_prompt_compiler import KLING_EMOTION_ACTION
                action = KLING_EMOTION_ACTION.get(beat.lower().strip(), "")
                if action:
                    emotion_action = action
            except Exception:
                pass

        # Build the video prompt from scratch
        parts = []

        # Timing header
        parts.append(f"0-{duration}s:")

        # V27.1.4d: Anti-camera-drift — LTX-2 wanders without explicit lock
        parts.append("STATIC CAMERA. Camera does NOT move, pan, tilt, zoom, or orbit. Locked tripod shot.")

        # V27.1.4b: Camera/framing with explicit screen direction (180° rule)
        if angle == "A":
            parts.append(f"Over-the-shoulder shot. {listener_desc} shoulder frame-left foreground, back to camera, soft focus.")
            parts.append(f"{speaker_desc} frame-right, faces camera, sharp focus, speaking, eye-line directed frame-left.")
        else:
            parts.append(f"Reverse over-the-shoulder. {listener_desc} shoulder frame-right foreground, back to camera, soft focus.")
            parts.append(f"{speaker_desc} frame-left, faces camera, sharp focus, speaking, eye-line directed frame-right.")

        # Dialogue with performance
        parts.append(f'Delivers line: "{clean_dialogue}"')
        parts.append(f"Lips move naturally with speech cadence, subtle jaw motion, {emotion_action}.")

        # Emotional beat
        if beat:
            # Truncate long narrative beats to just the emotional essence
            _beat_short = beat[:80] if len(beat) > 80 else beat
            parts.append(f"Emotional tone: {_beat_short}.")

        # V27.1.4e: CINEMATIC QUALITY — organic film look, not CGI
        parts.append("Soft organic film grain, warm natural skin tones, gentle halation on highlights.")
        parts.append("Subtle imperfections: micro-expressions, natural breath rhythm.")

        # V27.1.5: SPLIT CONSTRAINT — face identity lock + body performance freedom
        # Old: "Face stable, NO morphing" killed ALL motion including body/hands/breathing
        # New: Face lock is SEPARATE from body, allowing natural performance
        parts.append("FACE IDENTITY LOCK: facial structure, skin tone, hair UNCHANGED throughout — NO face morphing, NO identity drift.")
        parts.append("BODY PERFORMANCE FREE: natural breathing, weight shifts, hand gestures, shoulder movement all CONTINUE throughout the shot.")
        parts.append("NO camera movement.")

        # Duration marker
        parts.append(f"{duration}s")

        prompt = " ".join(parts)

        # Cap at 900 chars (LTX limit)
        if len(prompt) > 900:
            prompt = prompt[:897] + "..."

        logger.info(f"[V27.1.2 VIDEO PROMPT] {shot.get('shot_id')}: "
                    f"compiled {len(prompt)} chars, dialogue={len(clean_dialogue)} chars")
        return prompt

    def compile_universal_video_prompt(self, shot: Dict) -> str:
        """
        V27.1.4d: Compile a CLEAN video prompt for ANY dialogue shot type.
        Fixes 3 issues:
          1. Camera drift → explicit "STATIC CAMERA, NO camera movement" constraint
          2. Corrupted prompts → built from scratch, not from stacked fix-v16 data
          3. AI-dry acting → specific physical verbs from CPC EMOTION_PHYSICAL_MAP
        """
        characters = shot.get("characters") or []
        dialogue = shot.get("dialogue_text", "")
        duration = shot.get("duration", 10)
        beat = shot.get("beat", shot.get("emotional_beat", ""))
        shot_type = (shot.get("shot_type") or "").lower()
        # V27.1.4e: Rich narrative data from story bible beat injection
        beat_action = shot.get("_beat_character_action", "")

        if not dialogue or not characters:
            return shot.get("ltx_motion_prompt", "")

        # Clean dialogue
        clean_dialogue = dialogue
        for char in characters:
            clean_dialogue = re.sub(rf'{re.escape(char)}\s*:\s*', '', clean_dialogue, flags=re.IGNORECASE)
        clean_dialogue = clean_dialogue.replace("|", " ").strip()
        clean_dialogue = re.sub(r'\s+', ' ', clean_dialogue)
        if len(clean_dialogue) > 180:
            clean_dialogue = clean_dialogue[:177] + "..."

        # Get physical performance verbs — NOT generic "subtle gestures"
        speaker = characters[0]
        speaker_desc = self.get_appearance_description(speaker)

        # V27.1.4e: NARRATIVE-DRIVEN physical actions — story bible character_action is GOLD
        # V27.3 FIX: Beat actions describe a ONE-TIME physical event (opens briefcase,
        # touches banister, gazes at painting). They are NOT ongoing performance direction.
        # Using "opens briefcase on dusty console table" for 4 consecutive dialogue shots
        # makes the character repeat the same action in every shot — continuity disaster.
        #
        # RULE: Beat action is ONLY used for the FIRST shot in the beat, AND only if the
        # action describes the SPEAKER (not a different character in the scene).
        # All subsequent shots in the same beat fall through to emotion-driven performance.
        #
        # Detection: if prev_shots share the same beat_id, this is NOT the first shot.
        physical_actions = []
        _current_beat_id = shot.get("beat_id", "")
        _is_first_shot_in_beat = True
        if _current_beat_id and hasattr(self, '_seen_beat_ids'):
            if _current_beat_id in self._seen_beat_ids:
                _is_first_shot_in_beat = False
            else:
                self._seen_beat_ids.add(_current_beat_id)
        elif _current_beat_id:
            self._seen_beat_ids = {_current_beat_id}

        if beat_action and len(beat_action) > 10 and _is_first_shot_in_beat:
            _ba = beat_action.strip()
            # Check if beat_action is about a DIFFERENT character
            _ba_lower = _ba.lower()
            _speaker_lower = speaker.lower().split()[-1] if speaker else ""  # Last name
            _speaker_first = speaker.lower().split()[0] if speaker else ""  # First name
            _action_matches_speaker = (
                not speaker or  # No speaker info → use it
                _speaker_lower in _ba_lower or  # "Thomas" in "Thomas gazes up..."
                _speaker_first in _ba_lower or
                not any(c.lower().split()[-1] in _ba_lower for c in characters[1:] if c != speaker)  # No OTHER character named
            )
            if _action_matches_speaker:
                # V27.3: Also strip location-specific props that don't belong in EVERY shot
                # "opens briefcase on dusty console table" → "opens briefcase, pulls out folder"
                # The TABLE is a location prop, not a character performance
                _ba = re.sub(r'\s+on\s+(dusty\s+)?console\s+table', '', _ba, flags=re.IGNORECASE)
                _ba = re.sub(r'\s+on\s+(the\s+)?(dusty\s+)?table', '', _ba, flags=re.IGNORECASE)
                if len(_ba) > 100:
                    _ba = _ba[:97] + "..."
                physical_actions.append(_ba)

        if not physical_actions:
            # Fallback: CPC emotion-driven physical actions
            try:
                from tools.creative_prompt_compiler import get_physical_direction
                pd = get_physical_direction(beat or "tension", "standing")
                if pd and "subtle" not in pd.lower() and "natural" not in pd.lower():
                    physical_actions.append(pd)
            except Exception:
                pass

        if not physical_actions:
            # V27.1.4e: Beat-informed emotion defaults — NOT random, derived from narrative context
            # Use beat description + dialogue text to extract the CORRECT emotional tone
            beat_lower = (beat or "").lower()
            dialogue_lower = clean_dialogue.lower()
            # Combine beat + dialogue for richer emotion detection
            context = beat_lower + " " + dialogue_lower
            if any(w in context for w in ["anger", "frustrat", "resent", "defi", "refuses", "hate"]):
                physical_actions = ["jaw clenches between words, shoulders tense, weight shifts forward aggressively"]
            elif any(w in context for w in ["grief", "loss", "sad", "pain", "reluctant", "touching", "miss"]):
                physical_actions = ["eyes glisten, breath catches mid-sentence, hand grips nearby surface"]
            elif any(w in context for w in ["control", "professional", "calm", "authority", "presents", "demands", "debt", "financial", "sale"]):
                physical_actions = ["posture straight and rigid, chin tilted up, hands clasped firmly in front"]
            elif any(w in context for w in ["tension", "confront", "power", "stares", "refuses", "stays", "painting"]):
                physical_actions = ["leans forward into the space, finger points, eyes narrow with each word"]
            elif any(w in context for w in ["enter", "survey", "approaches", "follows", "pushes open"]):
                physical_actions = ["steps forward with purpose, eyes scanning the room, body language cautious"]
            elif any(w in context for w in ["plead", "beg", "desperate", "need", "must", "only path"]):
                physical_actions = ["hands open in appeal, body leans in, eyes search for connection"]
            else:
                physical_actions = ["weight shifts between feet, hands gesture deliberately with each point made"]

        perf = physical_actions[0] if physical_actions else "speaks with controlled intensity"

        parts = []
        parts.append(f"0-{duration}s:")

        # ANTI-CAMERA-DRIFT: This is the #1 fix for LTX camera wander
        parts.append("STATIC CAMERA. Camera does NOT move, pan, tilt, zoom, or orbit. Locked tripod shot.")

        # Shot-type specific framing
        if "close" in shot_type or "medium_close" in shot_type:
            parts.append(f"Close-up: {speaker_desc} fills frame, face sharp focus.")
            parts.append(f"Eyes directed {shot.get('_eye_line_direction', 'frame-left')}, speaking off-camera.")
        elif "two_shot" in shot_type:
            sp_pos = self.get_screen_position(speaker) or "left"
            parts.append(f"Two-shot: two people face each other. Speaker on {sp_pos} side of frame.")
        elif "wide" in shot_type:
            parts.append(f"Wide shot: full room visible, two figures separated by distance.")
        elif "medium" in shot_type:
            parts.append(f"Medium shot: {speaker_desc} waist-up, room visible behind.")
            parts.append(f"Eyes directed {shot.get('_eye_line_direction', 'frame-left')}, speaking off-camera.")

        # Dialogue + performance
        parts.append(f'Delivers line: "{clean_dialogue}"')
        parts.append(f"Lips move naturally with speech rhythm, subtle jaw motion. {perf}.")

        # V27.1.4e: CINEMATIC QUALITY — kills CGI look, adds organic film texture
        parts.append("Soft organic film grain, warm natural skin tones, gentle halation on highlights.")
        parts.append("Subtle imperfections: micro-expressions, natural breath rhythm, weight shifting between feet.")

        # V27.1.5: SPLIT CONSTRAINT — face identity lock + body performance freedom
        parts.append("FACE IDENTITY LOCK: facial structure, skin tone, hair UNCHANGED — NO face morphing, NO identity drift.")
        parts.append("BODY PERFORMANCE FREE: natural breathing, weight shifts, hand gestures, posture changes CONTINUE. Photorealistic.")
        parts.append("NO camera movement.")
        parts.append(f"{duration}s")

        prompt = " ".join(parts)
        if len(prompt) > 900:
            prompt = prompt[:897] + "..."

        print(f"  [VIDEO-PROMPT] {shot.get('shot_id')}: {len(prompt)} chars, perf='{perf[:50]}'", flush=True)
        return prompt

    def prepare_ots_shot(self, shot: Dict) -> Dict:
        """
        Full OTS preparation: assign angle + reorder refs + rewrite prompt + compile video prompt.
        Call this BEFORE sending to FAL.
        """
        shot_type = (shot.get("shot_type") or "").lower()
        is_ots = "over_the_shoulder" in shot_type or "ots" in shot_type

        if not is_ots:
            return shot

        if not shot.get("dialogue_text"):
            return shot

        characters = shot.get("characters") or []
        if len(characters) < 2:
            return shot

        # Step 0: Identify speaker/listener (needed for all subsequent steps)
        speaker, listener = self.identify_speaker(shot)
        if speaker:
            shot["_ots_speaker"] = speaker
            shot["_ots_listener"] = listener

        # Step 1: Assign A/B angle
        shot["_ots_angle"] = self.assign_ots_angle(shot)

        # Step 2: Reorder refs
        shot = self.reorder_refs_speaker_first(shot)

        # Step 3: Rewrite nano_prompt (for first frame generation)
        shot = self.rewrite_prompt_appearance_based(shot)

        # Step 4: Compile clean video prompt (for video generation)
        shot["ltx_motion_prompt"] = self.compile_video_prompt(shot)
        shot["_video_prompt_compiled_at_origin"] = True

        return shot


    def prepare_two_shot(self, shot: Dict) -> Dict:
        """
        V27.1.4b: Cinematic two-shot dialogue framing.
        Characters FACE EACH OTHER across the frame.
        Speaker emphasized (frame-left facing right by convention).
        """
        speaker, listener = self.identify_speaker(shot)
        if not speaker:
            return shot
        shot["_ots_speaker"] = speaker
        shot["_ots_listener"] = listener

        speaker_desc = self.get_appearance_description(speaker)
        listener_desc = self.get_appearance_description(listener) if listener else ""

        if not speaker_desc or not listener_desc:
            return shot

        location = shot.get("location", "")
        atmo_parts = []
        loc_lower = location.lower()
        if any(w in loc_lower for w in ["foyer", "hall", "entrance", "grand"]):
            atmo_parts.append("Grand Victorian interior, warm lamplight, rich shadows")
        elif any(w in loc_lower for w in ["study", "library", "parlor"]):
            atmo_parts.append("Warm candlelight, dark wood paneling")
        else:
            atmo_parts.append("Moody interior lighting, rich shadows")
        atmosphere = ", ".join(atmo_parts)

        # V27.1.4c: Use LOCKED screen positions if available
        # This ensures the two-shot matches the spatial geography of the OTS pair
        speaker_pos = self.get_screen_position(speaker) or "left"
        listener_pos = "right" if speaker_pos == "left" else "left"
        print(f"  [TWO-SHOT POSITION] speaker={speaker}, locked_pos={self.get_screen_position(speaker)}, "
              f"using={speaker_pos}, positions_map={self._screen_positions}", flush=True)

        if speaker_pos == "right":
            left_desc = listener_desc
            left_action = "arms crossed defensively, body angled toward frame-right"
            right_desc = speaker_desc
            right_action = "speaking with intensity, body angled toward frame-left, pointing finger"
        else:
            left_desc = speaker_desc
            left_action = "speaking with intensity, body angled toward frame-right"
            right_desc = listener_desc
            right_action = "arms crossed defensively, body angled toward frame-left"

        # Two-shot: characters face each other, positions match OTS spatial geography
        _two_shot_nano = (
            f"Cinematic two-shot, 35mm lens, f/2.8, medium depth of field. "
            f"FRAME-LEFT (facing right): {left_desc}, {left_action}. "
            f"FRAME-RIGHT (facing left): {right_desc}, {right_action}. "
            f"Characters face each other across the frame, confrontational blocking, eye-lines cross at center. "
            f"Full room geography visible behind both characters. "
            f"{atmosphere}. "
            f"Film grain, natural skin tones, no digital sharpening."
        )
        # V27.1.5: RESPECT BAKED PROMPTS — only prepend screen direction if baked
        _existing_nano = shot.get("nano_prompt", "")
        if "[ROOM DNA:" in _existing_nano or shot.get("_quality_gate_ready"):
            _screen_dir = f"FRAME-LEFT: {left_desc}. FRAME-RIGHT: {right_desc}. Confrontational blocking."
            if "FRAME-LEFT" not in _existing_nano:
                shot["nano_prompt"] = f"Cinematic two-shot, 35mm f/2.8. {_screen_dir} {_existing_nano}"
            logger.info(f"[TWO-SHOT] PRESERVED baked prompt for {shot.get('shot_id')}")
        else:
            shot["nano_prompt"] = _two_shot_nano
        shot["_prompt_rewritten_by_ots_enforcer"] = True
        # V27.1.5: Respect baked ltx too
        _existing_ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in _existing_ltx and shot.get("_quality_gate_ready"):
            logger.info(f"[TWO-SHOT] PRESERVED baked ltx for {shot.get('shot_id')}")
        else:
            shot["ltx_motion_prompt"] = self.compile_universal_video_prompt(shot)
        logger.info(f"[V27.1.4c TWO-SHOT] {shot.get('shot_id')}: "
                    f"{speaker}={speaker_pos.upper()}, {listener}={listener_pos.upper()} (position-locked)")
        return shot

    def prepare_solo_dialogue_closeup(self, shot: Dict, prev_shots: List[Dict] = None) -> Dict:
        """
        V27.6: Solo character dialogue close-up.
        Tight framing (85mm+), heavy bokeh, character fills frame.

        CRITICAL DISTINCTION (V27.6):
        - SOLO SCENE (1 character in entire scene): Character is reading, examining,
          narrating to self. NO off-camera partner. Eyes directed DOWN at object,
          or AHEAD into middle distance. No dirty OTS framing.
        - MULTI-CHARACTER SCENE: Character looks OFF-CAMERA toward absent partner.
          Eye-line inherited from preceding OTS/two-shot.

        CINEMATIC FRAMING (V27.6):
        At 85mm f/1.4 with face filling frame, background is PURE BOKEH.
        No architectural details visible — only warm/cool color blobs and light shapes.
        This is how real lenses work. Detailed bg descriptions at this focal length
        cause FAL to show the room clearly, breaking the close-up illusion.
        """
        characters = shot.get("characters") or []
        if not characters:
            return shot

        char_name = characters[0]
        char_desc = self.get_appearance_description(char_name)
        if not char_desc:
            return shot

        # V27.6: SOLO SCENE vs MULTI-CHARACTER — determines eye direction and framing
        dialogue_text = shot.get("dialogue_text", "")

        if self._is_solo_scene:
            # ── SOLO SCENE: Character is ALONE. Dialogue is self-directed. ──
            # V27.6: Use BEAT DATA if available (richest source), else infer from dialogue

            beat_eye = shot.get("_eye_line_target", "")
            beat_body = shot.get("_body_direction", "")
            beat_action = shot.get("_beat_action", "")

            if beat_eye and beat_body:
                # Beat enrichment available — use it (most cinematographically accurate)
                eye_dir = beat_eye
                performance = f"{beat_body}, {beat_eye}"
                if beat_action:
                    performance = f"{beat_action.split(',')[0].strip()}, {beat_body}"
                logger.info(f"[V27.6 SOLO CLOSE-UP] {char_name} — BEAT-DRIVEN: eye={eye_dir[:30]}")
            else:
                # Fallback: infer from dialogue keywords
                _dial_lower = dialogue_text.lower()
                if any(w in _dial_lower for w in ["read", "title", "edition", "book", "letter", "note", "page"]):
                    performance = "eyes scanning downward, reading aloud softly, lips moving with quiet words"
                    eye_dir = "downward"
                elif any(w in _dial_lower for w in ["look", "see", "notice", "find", "discover"]):
                    performance = "eyes widening with discovery, examining something closely, quiet murmur"
                    eye_dir = "downward"
                elif any(w in _dial_lower for w in ["remember", "think", "wonder", "know"]):
                    performance = "eyes drifting into middle distance, lost in thought, speaking softly to self"
                    eye_dir = "ahead into middle distance"
                else:
                    performance = "speaking quietly to self, absorbed in the moment, natural micro-expressions"
                    eye_dir = "slightly downward"

            off_cam_dir = None  # NO off-camera partner
            logger.info(f"[V27.6 SOLO CLOSE-UP] {char_name} ALONE — eyes {eye_dir[:30]}, no off-camera partner")
            print(f"  [SOLO CLOSE-UP] {shot.get('shot_id')}: {char_name} ALONE — "
                  f"beat={'yes' if beat_eye else 'no'}, eye={eye_dir[:30]}", flush=True)
        else:
            # ── MULTI-CHARACTER SCENE: Use position lock for eye-line toward partner ──
            my_pos = self.get_screen_position(char_name)
            if my_pos == "left":
                eye_dir = "frame-right"
                off_cam_dir = "off-camera right, toward absent conversation partner"
                logger.info(f"[EYE-LINE] {char_name} position=LEFT → looks frame-right toward partner")
            elif my_pos == "right":
                eye_dir = "frame-left"
                off_cam_dir = "off-camera left, toward absent conversation partner"
                logger.info(f"[EYE-LINE] {char_name} position=RIGHT → looks frame-left toward partner")
            else:
                eye_dir = "frame-left"
                off_cam_dir = "off-camera left"
                logger.info(f"[EYE-LINE] {char_name} no position lock — defaulting to frame-left")
            performance = f"Eyes directed {eye_dir}, speaking to someone {off_cam_dir}, lips parted, speaking naturally with subtle jaw movement"
            print(f"  [CLOSE-UP 360°] {char_name} multi-char scene — looking {eye_dir}", flush=True)

        # V27.6: CINEMATIC BOKEH — at 85mm f/1.4 with face filling frame,
        # background is PURE color bokeh. No architectural details.
        # Real 85mm at f/1.4 with subject at 3-4 feet: background objects beyond 8 feet
        # are completely unresolvable — just warm/cool light blobs.
        location = shot.get("location", "")
        scene_room = shot.get("_scene_room", "")
        if not scene_room and prev_shots:
            for ps in reversed(prev_shots):
                sr = ps.get("_scene_room", ps.get("location", ""))
                if sr and len(sr) > len(location):
                    scene_room = sr
                    break
        loc_lower = (location + " " + scene_room).lower()

        # Background is COLOR AND LIGHT only — no shapes, no architecture
        if any(w in loc_lower for w in ["library", "study"]):
            bg_bokeh = "warm amber bokeh from lamplight, dark rich tones, soft golden highlights"
        elif any(w in loc_lower for w in ["foyer", "hall", "entrance", "grand", "estate"]):
            bg_bokeh = "warm amber and shadow bokeh, soft golden lamp highlights, dark rich wood tones"
        elif any(w in loc_lower for w in ["garden", "exterior", "outside"]):
            bg_bokeh = "cool natural daylight bokeh, soft green and grey tones"
        else:
            bg_bokeh = "warm moody bokeh, soft amber highlights, dark tonal shapes"

        _closeup_nano = (
            f"Cinematic extreme close-up portrait, 85mm f/1.4, razor-thin depth of field. "
            f"{char_desc}. "
            f"{performance}. "
            f"Face fills eighty percent of frame, eyes and mouth in critical focus, skin texture visible. "
            f"Background completely obliterated into smooth creamy bokeh — {bg_bokeh}. "
            f"No background detail visible, no room architecture, pure color and light shapes only. "
            f"Film grain, natural skin tones, intimate cinematography."
        )
        # V27.6: SOLO SCENES ALWAYS GET CLEAN REWRITE
        # Baked prompts from previous runs may contain "speaking to someone off-camera"
        # which causes phantom OTS shoulders. Solo scenes MUST rewrite completely.
        _existing_nano = shot.get("nano_prompt", "")
        if self._is_solo_scene:
            # ALWAYS rewrite for solo scenes — strip any old off-camera contamination
            # Preserve [CHARACTER:] and [ROOM DNA:] blocks from identity injection
            _preserved_blocks = ""
            import re as _re
            for block_match in _re.finditer(r'\[(?:CHARACTER|ROOM DNA|LIGHTING RIG|TIGHT FRAMING|BLOCKING):[^\]]*\]', _existing_nano):
                _preserved_blocks += " " + block_match.group(0)
            shot["nano_prompt"] = _closeup_nano + _preserved_blocks
            logger.info(f"[V27.6 CLOSE-UP] SOLO REWRITE for {shot.get('shot_id')} — "
                       f"preserved {len(_preserved_blocks)} chars of blocks")
        elif "[ROOM DNA:" in _existing_nano or shot.get("_quality_gate_ready"):
            _eye_prefix = f"Eyes directed {eye_dir}, speaking to someone {off_cam_dir}."
            if eye_dir not in _existing_nano:
                shot["nano_prompt"] = f"{_eye_prefix} {_existing_nano}"
            logger.info(f"[CLOSE-UP] PRESERVED baked prompt for {shot.get('shot_id')}")
        else:
            shot["nano_prompt"] = _closeup_nano
        shot["_prompt_rewritten_by_ots_enforcer"] = True
        shot["_eye_line_direction"] = eye_dir
        shot["_is_solo_scene_dialogue"] = self._is_solo_scene
        # V27.1.5: Respect baked ltx too
        _existing_ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in _existing_ltx and shot.get("_quality_gate_ready"):
            logger.info(f"[CLOSE-UP] PRESERVED baked ltx for {shot.get('shot_id')}")
        else:
            shot["ltx_motion_prompt"] = self.compile_universal_video_prompt(shot)
        logger.info(f"[V27.1.4b CLOSE-UP] {shot.get('shot_id')}: {char_name} looking {eye_dir}")
        return shot

    def prepare_solo_dialogue_medium(self, shot: Dict, prev_shots: List[Dict] = None) -> Dict:
        """
        V27.6: Solo character MEDIUM shot with dialogue.
        Wider than close-up (50mm not 85mm), shows more of the room,
        but still has position-locked eye-line and spatially-aware background.

        V27.6: Solo scene detection — same as close-up. If character is alone
        in the scene, no off-camera partner direction.
        """
        characters = shot.get("characters") or []
        if not characters:
            return shot

        char_name = characters[0]
        char_desc = self.get_appearance_description(char_name)
        if not char_desc:
            return shot

        dialogue_text = shot.get("dialogue_text", "")

        if self._is_solo_scene:
            # ── SOLO SCENE: Self-directed performance ──
            # V27.6: Use BEAT DATA if available (richest source), else infer from dialogue
            beat_eye = shot.get("_eye_line_target", "")
            beat_body = shot.get("_body_direction", "")
            beat_action = shot.get("_beat_action", "")

            if beat_eye and beat_body:
                # Beat enrichment available — use it (most cinematographically accurate)
                eye_dir = beat_eye
                performance = f"{beat_body}, {beat_eye}"
                if beat_action:
                    performance = f"{beat_action.split(',')[0].strip()}, {beat_body}"
                logger.info(f"[V27.6 SOLO MEDIUM] {char_name} — BEAT-DRIVEN: eye={eye_dir[:30]}")
            else:
                # Fallback: infer from dialogue keywords
                _dial_lower = dialogue_text.lower()
                if any(w in _dial_lower for w in ["read", "title", "edition", "book", "letter", "note", "page"]):
                    performance = "running fingers along book spines, reading titles aloud softly"
                    eye_dir = "downward at books"
                elif any(w in _dial_lower for w in ["look", "see", "notice", "find", "discover"]):
                    performance = "examining the room with curiosity, moving slowly through the space"
                    eye_dir = "scanning the room"
                elif any(w in _dial_lower for w in ["remember", "think", "wonder", "know"]):
                    performance = "eyes drifting into middle distance, lost in thought, speaking softly"
                    eye_dir = "ahead into middle distance"
                else:
                    performance = "speaking quietly to self, natural gestures, absorbed in surroundings"
                    eye_dir = "slightly downward"

            off_cam_dir = None
            my_pos = None  # No position lock needed for solo scenes
            logger.info(f"[V27.6 SOLO MEDIUM] {char_name} ALONE — self-directed")
            print(f"  [SOLO MEDIUM] {shot.get('shot_id')}: {char_name} ALONE — "
                  f"beat={'yes' if beat_eye else 'no'}, eye={eye_dir[:30]}", flush=True)
        else:
            # ── MULTI-CHARACTER: eye-line toward partner ──
            my_pos = self.get_screen_position(char_name)
            if my_pos == "left":
                eye_dir = "frame-right"
                off_cam_dir = "off-camera right, toward absent conversation partner"
            elif my_pos == "right":
                eye_dir = "frame-left"
                off_cam_dir = "off-camera left, toward absent conversation partner"
            else:
                eye_dir = "frame-left"
                off_cam_dir = "off-camera left"
            performance = f"Eyes directed {eye_dir}, speaking to someone {off_cam_dir}, delivering dialogue with controlled intensity, natural hand gestures"

        location = shot.get("location", "")
        scene_room = shot.get("_scene_room", "")
        if not scene_room and prev_shots:
            for ps in reversed(prev_shots):
                sr = ps.get("_scene_room", ps.get("location", ""))
                if sr and len(sr) > len(location):
                    scene_room = sr
                    break
        loc_lower = (location + " " + scene_room).lower()

        if any(w in loc_lower for w in ["foyer", "hall", "entrance", "grand", "estate"]):
            atmo = "Grand Victorian foyer visible behind, dark wood paneling, warm lamplight"
        elif any(w in loc_lower for w in ["study", "library"]):
            atmo = "Dark bookshelves and warm amber lamplight behind, leather-bound volumes"
        else:
            atmo = "Moody interior, warm shadows, period architecture behind"

        _med_nano = (
            f"Cinematic medium shot, 50mm lens, f/2.0, moderate depth of field. "
            f"Waist-up framing on {char_desc}. "
            f"{performance}. "
            f"{atmo}. "
            f"Film grain, natural skin tones, no digital sharpening."
        )
        # V27.6: SOLO SCENES ALWAYS GET CLEAN REWRITE (same logic as close-up)
        _existing_nano = shot.get("nano_prompt", "")
        if self._is_solo_scene:
            import re as _re
            _preserved_blocks = ""
            for block_match in _re.finditer(r'\[(?:CHARACTER|ROOM DNA|LIGHTING RIG|TIGHT FRAMING|BLOCKING):[^\]]*\]', _existing_nano):
                _preserved_blocks += " " + block_match.group(0)
            shot["nano_prompt"] = _med_nano + _preserved_blocks
            logger.info(f"[V27.6 MEDIUM] SOLO REWRITE for {shot.get('shot_id')}")
        elif "[ROOM DNA:" in _existing_nano or shot.get("_quality_gate_ready"):
            _eye_prefix = f"Eyes directed {eye_dir}, speaking to someone {off_cam_dir}."
            if eye_dir not in _existing_nano:
                shot["nano_prompt"] = f"{_eye_prefix} {_existing_nano}"
            logger.info(f"[MEDIUM-SOLO] PRESERVED baked prompt for {shot.get('shot_id')}")
        else:
            shot["nano_prompt"] = _med_nano
        shot["_prompt_rewritten_by_ots_enforcer"] = True
        shot["_eye_line_direction"] = eye_dir
        shot["_is_solo_scene_dialogue"] = self._is_solo_scene
        # V27.1.5: Respect baked ltx too
        _existing_ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in _existing_ltx and shot.get("_quality_gate_ready"):
            logger.info(f"[MEDIUM-SOLO] PRESERVED baked ltx for {shot.get('shot_id')}")
        else:
            shot["ltx_motion_prompt"] = self.compile_universal_video_prompt(shot)
        print(f"  [MEDIUM-SOLO] {shot.get('shot_id')}: {char_name} pos={my_pos if my_pos else 'solo'} eye={eye_dir}", flush=True)
        return shot

    def prepare_wide_dialogue(self, shot: Dict) -> Dict:
        """
        V27.1.4d: Wide/closing shot with 2+ characters and dialogue.
        Shows full room geography with characters positioned per lock.
        """
        speaker, listener = self.identify_speaker(shot)
        if not speaker:
            return shot

        speaker_desc = self.get_appearance_description(speaker)
        listener_desc = self.get_appearance_description(listener) if listener else ""
        if not speaker_desc:
            return shot

        speaker_pos = self.get_screen_position(speaker) or "left"
        listener_pos = "right" if speaker_pos == "left" else "left"

        if speaker_pos == "right":
            left_char, right_char = listener_desc, speaker_desc
        else:
            left_char, right_char = speaker_desc, listener_desc

        location = shot.get("location", "")
        loc_lower = location.lower()
        if any(w in loc_lower for w in ["foyer", "hall", "entrance", "grand", "estate"]):
            atmo = "Grand Victorian foyer, sweeping staircase, ornate chandelier, dark wood paneling, warm lamplight"
        elif any(w in loc_lower for w in ["study", "library"]):
            atmo = "Rich study interior, bookshelves, warm candlelight, dark wood furniture"
        else:
            atmo = "Full interior geography visible, moody period lighting, rich architectural detail"

        _wide_nano = (
            f"Cinematic wide shot, 24mm lens, f/4.0, deep depth of field. "
            f"Full room geography. "
            f"FRAME-LEFT: {left_char}. "
            f"FRAME-RIGHT: {right_char}. "
            f"Characters separated by distance, tension visible in body language. "
            f"{atmo}. "
            f"Film grain, natural skin tones, no digital sharpening."
        )
        # V27.1.5: RESPECT BAKED PROMPTS
        _existing_nano = shot.get("nano_prompt", "")
        if "[ROOM DNA:" in _existing_nano or shot.get("_quality_gate_ready"):
            _screen_dir = f"FRAME-LEFT: {left_char}. FRAME-RIGHT: {right_char}."
            if "FRAME-LEFT" not in _existing_nano:
                shot["nano_prompt"] = f"Cinematic wide, 24mm f/4.0, deep DOF. {_screen_dir} {_existing_nano}"
            logger.info(f"[WIDE-DIALOGUE] PRESERVED baked prompt for {shot.get('shot_id')}")
        else:
            shot["nano_prompt"] = _wide_nano
        shot["_prompt_rewritten_by_ots_enforcer"] = True
        # V27.1.5: Respect baked ltx too
        _existing_ltx = shot.get("ltx_motion_prompt", "")
        if "TIMED CHOREOGRAPHY:" in _existing_ltx and shot.get("_quality_gate_ready"):
            logger.info(f"[WIDE-DIALOGUE] PRESERVED baked ltx for {shot.get('shot_id')}")
        else:
            shot["ltx_motion_prompt"] = self.compile_universal_video_prompt(shot)
        print(f"  [WIDE-DIALOGUE] {shot.get('shot_id')}: {speaker}={speaker_pos.upper()}", flush=True)
        return shot

    def prepare_dialogue_shot(self, shot: Dict, prev_shots: List[Dict] = None) -> Dict:
        """
        V27.1.4b: UNIVERSAL dialogue shot preparation.
        Routes to the correct handler based on shot type.
        This is the single entry point for ALL dialogue shots.
        """
        shot_type = (shot.get("shot_type") or "").lower()
        dialogue = shot.get("dialogue_text", "")
        characters = shot.get("characters") or []

        if not dialogue:
            return shot

        # OTS: existing handler (screen direction now flips A/B)
        if "over_the_shoulder" in shot_type or "ots" in shot_type:
            return self.prepare_ots_shot(shot)

        # Two-shot with 2+ characters: confrontational blocking
        if ("two_shot" in shot_type or "two-shot" in shot_type) and len(characters) >= 2:
            return self.prepare_two_shot(shot)

        # Solo dialogue close-up: tight frame, off-camera eye-line, heavy bokeh
        if len(characters) <= 1 and any(t in shot_type for t in [
            "medium_close", "close_up", "extreme_close", "close-up", "medium close",
            "reaction", "medium_close_up"
        ]):
            return self.prepare_solo_dialogue_closeup(shot, prev_shots)

        # Solo medium with dialogue: keep medium framing, add position-locked eye-line
        if "medium" in shot_type and len(characters) == 1:
            return self.prepare_solo_dialogue_medium(shot, prev_shots)

        # Wide/closing with 2+ characters and dialogue: position-locked two-shot (wider lens)
        if len(characters) >= 2 and any(t in shot_type for t in ["wide", "closing", "establishing"]):
            return self.prepare_wide_dialogue(shot)

        return shot


def enforce_all_ots_shots(shots: list, cast_map: dict) -> dict:
    """Batch enforce all OTS shots in a shot plan."""
    enforcer = OTSEnforcer(cast_map)
    stats = {"total_ots": 0, "reordered": 0, "rewritten": 0}

    for shot in shots:
        shot_type = (shot.get("shot_type") or "").lower()
        if "over_the_shoulder" not in shot_type and "ots" not in shot_type:
            continue

        stats["total_ots"] += 1
        old_urls = list(shot.get("_fal_image_urls_resolved", []))
        old_prompt = shot.get("nano_prompt", "")

        enforcer.prepare_ots_shot(shot)

        if shot.get("_fal_image_urls_resolved") != old_urls:
            stats["reordered"] += 1
        if shot.get("nano_prompt") != old_prompt:
            stats["rewritten"] += 1

    return stats
