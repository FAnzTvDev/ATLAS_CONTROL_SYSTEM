"""
ATLAS PROMPT COMPILER v1.0
===========================
Model-aware prompt engine for ATLAS V23.
Replaces the 7-layer enrichment stack entirely.

ARCHITECTURE:
  Shot Data + LITE Data Object → Compiler → Model-Specific Payload

MODELS SUPPORTED:
  - Kling O3 Pro Reference-to-Video  (fal-ai/kling-video/o3/pro/reference-to-video)
  - LTX-2.3 Fast Image-to-Video      (fal-ai/ltx-2.3/image-to-video/fast)

ROUTING LOGIC (no LoRA tiers yet):
  Kling  → CU/MCU shots, dialogue, emotional peaks, multi-character, scene anchors
  LTX    → Medium/wide, establishing, atmosphere, B-roll, single-char reaction

DEAD SPACE (model handles natively — do NOT inject):
  Kling  → Anti-CGI anchors, ArcFace identity, photorealism guards, IP-Adapter
  LTX    → Basic prompt reformatting (4x larger text connector handles it)
  Both   → FACS muscle mapping (physical descriptions now sufficient)

PROMPT FORMAT (validated from Higgsfield + model research):
  Kling  → Zone order: Camera → Subject → Environment → Lighting → Texture → Emotion
            30-100 words. @Element1 replaces ALL character description text.
            Natural language emotion works. +++emphasis+++ for critical elements.
  LTX    → 4-8 sentences, single paragraph, present tense imperative.
            Zone order: Action → Movement → Appearance → Environment → Camera → Lighting
            NO emotion labels — physical descriptions ONLY.
            Concrete nouns/verbs weighted more heavily than vague descriptors.

Juice's law: "Make every change happen at the beginning of the pipeline.
              The end should be what you see."
"""

import json
import hashlib
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING RULES
# No LoRA tiers yet. Route by shot characteristics only.
# ═══════════════════════════════════════════════════════════════════════════════

KLING_SHOT_SIZES  = {"CU", "ECU", "MCU"}           # identity-critical sizes
LTX_SHOT_SIZES    = {"WS", "EWS", "MS", "MWS", "LS", "WIDE", "ESTABLISHING"}

KLING_SHOT_TYPES  = {"dialogue", "confrontation", "revelation", "emotional_peak",
                     "close_up", "reaction_kling", "scene_open", "scene_close"}
LTX_SHOT_TYPES    = {"establishing", "atmosphere", "transition", "b_roll",
                     "insert", "wide", "reaction", "single_char_action"}


def route_model(shot: dict) -> str:
    """
    Returns 'kling' or 'ltx' for a given shot.
    Kling for anything identity-critical or dialogue.
    LTX for everything else.
    """
    shot_size  = shot.get("shot_size", "").upper()
    shot_type  = shot.get("shot_type", "").lower()
    has_dialogue   = bool(shot.get("dialogue_text") or shot.get("has_dialogue"))
    char_count     = len(shot.get("characters_present", []))
    emotion_intensity = float(shot.get("emotion_intensity", 0.5))
    is_scene_anchor   = shot.get("is_scene_anchor", False)  # first/last shot of scene

    # Hard Kling rules
    if has_dialogue:              return "kling"
    if is_scene_anchor:           return "kling"
    if shot_size in KLING_SHOT_SIZES: return "kling"
    if shot_type in KLING_SHOT_TYPES: return "kling"
    if char_count >= 2:           return "kling"   # multi-char: bleed prevention
    if emotion_intensity >= 0.8:  return "kling"   # emotional peaks

    # Default to LTX
    return "ltx"


# ═══════════════════════════════════════════════════════════════════════════════
# KLING PROMPT COMPILER
# Zone order: Camera → Subject → Environment → Lighting → Texture → Emotion
# 30-100 words. Character identity via @Element tags ONLY — no text description.
# ═══════════════════════════════════════════════════════════════════════════════

class KlingPromptCompiler:
    """
    Compiles Kling O3 Reference-to-Video payloads.
    Identity comes from elements[] array — never from prompt text.
    Prompt = Camera + Action + Environment + Emotion only.
    """

    # What Kling handles natively — do NOT re-inject these
    NATIVE_CAPABILITIES = {
        "photorealism",      # dual-reward RL baked in
        "anti_cgi",          # native quality mode
        "character_identity", # Elements 3.0
        "lip_sync",          # native with voice_ids
        "physics",           # gravity/inertia/cloth native
    }

    # Camera grammar validated for Kling (focal + aperture + film stock)
    CAMERA_GRAMMAR = {
        "ECU":  "90mm, f/1.4",
        "CU":   "85mm, f/1.8",
        "MCU":  "50mm, f/2.0",
        "MS":   "35mm, f/2.8",
        "MWS":  "28mm, f/3.5",
        "WS":   "24mm, f/4.0",
        "EWS":  "18mm, f/5.6",
    }

    # Film stock by genre/tone — replaces hardware brand tokens
    FILM_STOCK = {
        "mystery_thriller":  "Kodak 2383 print look, teal shadows, warm amber practicals",
        "gothic_horror":     "desaturated cool tones, deep shadows, silver halide grain",
        "drama":             "Kodak Vision3 500T, warm naturalistic, slight softness",
        "action":            "high contrast, punchy saturation, sharp edges",
        "default":           "35mm film grain, natural color science, motivated lighting",
    }

    # Pacing tags → camera movement intensity
    TEMPO_MOVEMENT = {
        "allegro":  "handheld urgency, restless reframing",
        "andante":  "slow deliberate push, controlled movement",
        "adagio":   "locked static frame, stillness as pressure",
        "moderato": "smooth dolly, measured pace",
    }

    def compile_prompt(self, shot: dict, lite_data: dict,
                       canonical_chars: dict) -> str:
        """
        Builds the Kling text prompt.
        Character description is EXCLUDED — identity is in elements[].
        Returns a clean 30-100 word prompt string.
        """
        parts = []

        # ── ZONE 1: CAMERA ─────────────────────────────────────────────────────
        shot_size   = shot.get("shot_size", "MS").upper()
        cam_base    = self.CAMERA_GRAMMAR.get(shot_size, "35mm, f/2.8")
        cam_move    = shot.get("camera_movement", "")
        pacing      = lite_data.get("pacing_target", "moderato")
        tempo_feel  = self.TEMPO_MOVEMENT.get(pacing, "controlled movement")

        if cam_move:
            parts.append(f"{cam_move}, {cam_base}")
        else:
            parts.append(f"{cam_base}, {tempo_feel}")

        # ── ZONE 2: SUBJECT / ACTION (character refs by @Element only) ─────────
        chars = shot.get("characters_present", [])
        action = shot.get("action_description") or shot.get("beat_action", "")

        if chars and action:
            # Reference characters by @Element tag — NEVER describe appearance
            element_refs = " and ".join(
                f"@Element{self._get_element_index(c, canonical_chars)}"
                for c in chars
            )
            parts.append(f"{element_refs}: {action}")
        elif action:
            parts.append(action)

        # ── ZONE 3: DIALOGUE MARKER ─────────────────────────────────────────────
        dialogue = shot.get("dialogue_text", "")
        if dialogue:
            speaker = chars[0] if chars else "character"
            voice_idx = self._get_element_index(speaker, canonical_chars)
            # Kling voice syntax: <<<voice_N>>> in prompt
            parts.append(f"<<<voice_{voice_idx}>>> speaks: \"{dialogue[:80]}\"")

        # ── ZONE 4: ENVIRONMENT ─────────────────────────────────────────────────
        location = shot.get("location_description") or shot.get("location", "")
        time_of_day = shot.get("time_of_day", "")
        scene_atmo  = lite_data.get("scene_cards_context", {}).get(
            "current_atmosphere", ""
        )
        if location:
            env_parts = [p for p in [location, time_of_day, scene_atmo] if p]
            parts.append(", ".join(env_parts))

        # ── ZONE 5: LIGHTING ────────────────────────────────────────────────────
        lighting = shot.get("lighting_direction", "")
        if not lighting:
            # Derive from act position and tone
            act_tone = lite_data.get("act_position", {}).get("tone", "")
            lighting = self._derive_lighting(act_tone, time_of_day)
        parts.append(lighting)

        # ── ZONE 6: TEXTURE / FILM STOCK ────────────────────────────────────────
        genre = lite_data.get("episode_overview", {}).get("genre", "default")
        film  = self.FILM_STOCK.get(genre, self.FILM_STOCK["default"])
        # Color anchor from project truth — locks grade across all shots
        color_anchor = lite_data.get("color_anchor", "")
        parts.append(color_anchor if color_anchor else film)

        # ── ZONE 7: EMOTION (Kling reads natural language — no FACS needed) ────
        emotion_label = shot.get("emotion_primary", "")
        subtext       = shot.get("emotion_subtext", "")
        intensity     = float(shot.get("emotion_intensity", 0.5))
        if emotion_label:
            if intensity >= 0.8:
                parts.append(f"+++{emotion_label}+++ {subtext}".strip())
            else:
                parts.append(f"{emotion_label}{', ' + subtext if subtext else ''}")

        prompt = ", ".join(p.strip() for p in parts if p.strip())

        # Word count guard: Kling optimal 30-100 words
        words = prompt.split()
        if len(words) > 100:
            prompt = " ".join(words[:100])

        return prompt

    def build_elements_array(self, shot: dict,
                              canonical_chars: dict) -> list:
        """
        Builds the elements[] array for the Kling API payload.
        Pre-uploaded character URLs from CANONICAL_CHARACTERS registry.
        Max 4 elements total.
        """
        chars = shot.get("characters_present", [])[:4]
        elements = []
        for char_name in chars:
            char = canonical_chars.get(char_name, {})
            frontal  = char.get("frontal_image_url")
            refs     = char.get("reference_image_urls", [])
            if frontal:
                elements.append({
                    "frontal_image_url":    frontal,
                    "reference_image_urls": refs[:3],  # max 3 reference angles
                })
        return elements

    def build_payload(self, shot: dict, lite_data: dict,
                      canonical_chars: dict,
                      scene_manifest: dict) -> dict:
        """
        Full Kling API payload ready for fal.subscribe().
        """
        prompt   = self.compile_prompt(shot, lite_data, canonical_chars)
        elements = self.build_elements_array(shot, canonical_chars)

        # Voice IDs for dialogue shots
        voice_ids = []
        if shot.get("dialogue_text"):
            chars = shot.get("characters_present", [])
            for c in chars[:2]:  # Kling max 2 voices per call
                vid = canonical_chars.get(c, {}).get("voice_id")
                if vid:
                    voice_ids.append(vid)

        # Keyframe bookends from Nano Banana pre-production
        start_frame = shot.get("nb_start_frame_url") or \
                      scene_manifest.get("location_reference_url")
        end_frame   = shot.get("nb_end_frame_url")

        payload = {
            "prompt":          prompt,
            "elements":        elements,
            "duration":        _clamp_kling_duration(shot.get("duration_seconds", 5)),
            "shot_type":       "customize",
            "generate_audio":  bool(shot.get("dialogue_text")),
        }

        if start_frame:
            payload["start_image_url"] = start_frame
        if end_frame:
            payload["end_image_url"] = end_frame
        if voice_ids:
            payload["voice_ids"] = voice_ids

        # Location reference as @Image1 for environment consistency
        loc_ref = scene_manifest.get("location_master_url")
        if loc_ref:
            payload["image_urls"] = [loc_ref]

        return {
            "endpoint": "fal-ai/kling-video/o3/pro/reference-to-video",
            "payload":  payload,
            "shot_id":  shot.get("shot_id"),
            "model":    "kling",
            "prompt_hash": _hash_prompt(prompt),
        }

    def _get_element_index(self, char_name: str,
                           canonical_chars: dict) -> int:
        keys = list(canonical_chars.keys())
        try:
            return keys.index(char_name) + 1
        except ValueError:
            return 1

    def _derive_lighting(self, act_tone: str, time_of_day: str) -> str:
        mapping = {
            "curiosity tinged with unease": "cool motivated practicals, deep fill shadows",
            "mounting dread":               "harsh underlighting, loss of fill",
            "paranoia":                     "flickering source, unstable shadows",
            "catharsis":                    "warm window light, expanding exposure",
        }
        base = mapping.get(act_tone, "motivated practical lighting, natural shadow falloff")
        if "night" in (time_of_day or "").lower():
            base += ", minimal ambient, strong motivated source"
        return base


# ═══════════════════════════════════════════════════════════════════════════════
# LTX PROMPT COMPILER
# 4-8 sentences. Single flowing paragraph. Present tense imperative.
# Zone order: Action → Movement → Appearance → Environment → Camera → Lighting
# NO emotion labels. Physical descriptions ONLY.
# Anti-CGI negatives still needed (LTX doesn't have Kling's native quality mode)
# ═══════════════════════════════════════════════════════════════════════════════

class LTXPromptCompiler:
    """
    Compiles LTX-2.3 Fast Image-to-Video payloads.
    Identity anchored via image_url (Nano Banana frame) — no LoRAs yet.
    Prompt = physical actions only, no emotion labels, present tense.
    Negative prompts required and always included.
    """

    # LTX still benefits from quality guards (no dual-reward RL like Kling)
    NEGATIVE_PROMPT = (
        "worst quality, inconsistent motion, blurry, jittery, distorted, "
        "plastic skin, CGI rendering, video game aesthetic, over-sharpened, "
        "HDR glow, uncanny valley, artificial lighting, smooth skin, "
        "perfect symmetry, digital noise pattern, wax figure"
    )

    # Emotion label → physical translation table (required for LTX)
    EMOTION_TO_PHYSICAL = {
        "rage":              "clenches jaw, veins visible at temple, hands grip tightly, "
                             "eyes lock without blinking",
        "grief":             "shoulders cave inward, chin drops, slow exhale through parted lips",
        "fear":              "pupils dilate, breathing becomes shallow and rapid, "
                             "body weight shifts back",
        "controlled_composure": "jaw set, measured breath, hands still at sides, "
                                 "gaze fixed and level",
        "suspicion":         "eyes narrow, head tilts fractionally, nostrils flare slightly",
        "shock":             "mouth opens slightly, a single rapid inhale, body goes still",
        "determination":     "chin lifts, spine straightens, gaze locks forward",
        "sadness":           "brow draws together, lower lip tightens, eyes glisten",
        "relief":            "shoulders drop, a long slow exhale, eyes close briefly",
        "betrayal":          "expression freezes, color drains from face, jaw tightens",
    }

    # Camera descriptions — physical, not brand names
    CAMERA_GRAMMAR = {
        "ECU":  "extreme close-up at 90mm, f/1.4, sharp on eyes, background dissolved",
        "CU":   "close-up at 85mm, f/1.8, face fills frame",
        "MCU":  "medium close-up at 50mm, f/2.0, chest to crown",
        "MS":   "medium shot at 35mm, f/2.8, waist to crown",
        "MWS":  "medium wide at 28mm, f/3.5, full body with environment context",
        "WS":   "wide shot at 24mm, f/4.0, character small against space",
        "EWS":  "extreme wide at 18mm, f/5.6, establishing scale",
        "ESTABLISHING": "wide establishing at 18mm, environment dominant",
    }

    # Pacing → camera movement in physical terms LTX understands
    TEMPO_MOVEMENT = {
        "allegro":  "camera drifts forward with slight handheld instability",
        "andante":  "camera makes a slow deliberate push toward subject",
        "adagio":   "camera holds completely still, locked frame, stillness as weight",
        "moderato": "smooth gentle dolly right at measured pace",
    }

    def compile_prompt(self, shot: dict, lite_data: dict,
                       canonical_chars: dict) -> str:
        """
        Builds the LTX text prompt as a single paragraph.
        Physical descriptions only. No emotion labels.
        Returns 4-8 sentences.
        """
        sentences = []

        # ── SENTENCE 1: MAIN ACTION ─────────────────────────────────────────────
        chars  = shot.get("characters_present", [])
        action = shot.get("action_description") or shot.get("beat_action", "")
        if chars and action:
            char_name = chars[0].split("_")[0].title()  # "ELEANOR_VOSS" → "Eleanor"
            sentences.append(f"{char_name} {action}.")
        elif action:
            sentences.append(f"{action}.")

        # ── SENTENCE 2: PHYSICAL MOVEMENT / GESTURE ─────────────────────────────
        # Include wardrobe if it affects movement (coat, skirt, etc.)
        wardrobe_note = ""
        if chars:
            scene_id = shot.get("scene_id", "")
            char_data = canonical_chars.get(chars[0], {})
            wardrobe  = char_data.get("wardrobe_by_scene", {}).get(
                scene_id, char_data.get("default_wardrobe", {})
            )
            if wardrobe:
                fabric = wardrobe.get("fabric_note", "")
                wardrobe_note = f"  {fabric}" if fabric else ""

        blocking = shot.get("blocking_direction", "")
        if blocking:
            sentences.append(f"{blocking}.{wardrobe_note}")

        # ── SENTENCE 3: PHYSICAL EMOTION (translate labels → body) ──────────────
        emotion_label = shot.get("emotion_primary", "").lower().replace(" ", "_")
        subtext       = shot.get("emotion_subtext", "")
        physical_emotion = self.EMOTION_TO_PHYSICAL.get(emotion_label, "")

        if not physical_emotion and emotion_label:
            # Fallback: use subtext directly if no translation exists
            physical_emotion = subtext

        if physical_emotion:
            sentences.append(f"{physical_emotion.rstrip('.')}.")

        # ── SENTENCE 4: ENVIRONMENT ─────────────────────────────────────────────
        location    = shot.get("location_description") or shot.get("location", "")
        time_of_day = shot.get("time_of_day", "")
        atmosphere  = lite_data.get("scene_cards_context", {}).get(
            "current_atmosphere", ""
        )
        env_parts   = [p for p in [location, time_of_day, atmosphere] if p]
        if env_parts:
            sentences.append(f"{', '.join(env_parts)}.")

        # ── SENTENCE 5: CAMERA (physical description, no brand names) ───────────
        shot_size  = shot.get("shot_size", "MS").upper()
        cam_desc   = self.CAMERA_GRAMMAR.get(shot_size, "medium shot at 35mm, f/2.8")
        cam_move   = shot.get("camera_movement", "")
        pacing     = lite_data.get("pacing_target", "moderato")
        tempo_move = self.TEMPO_MOVEMENT.get(pacing, "")

        if cam_move:
            sentences.append(f"{cam_desc}, {cam_move}.")
        else:
            sentences.append(f"{cam_desc}, {tempo_move}.")

        # ── SENTENCE 6: LIGHTING (physical, motivated source) ───────────────────
        lighting = shot.get("lighting_direction", "")
        if not lighting:
            act_tone = lite_data.get("act_position", {}).get("tone", "")
            lighting = self._derive_lighting_ltx(act_tone, time_of_day)
        sentences.append(f"{lighting}.")

        # ── SENTENCE 7: COLOR / FILM TEXTURE ────────────────────────────────────
        # Color anchor locks grade across all shots (from project truth)
        color_anchor = lite_data.get("color_anchor", "")
        if color_anchor:
            sentences.append(f"{color_anchor}.")
        else:
            sentences.append("35mm film grain, shallow depth of field, natural color science.")

        # Join as single paragraph. LTX reads this better than comma zones.
        prompt = "  ".join(s.strip() for s in sentences if s.strip())

        # LTX optimal: 4-8 sentences, under 200 words
        words = prompt.split()
        if len(words) > 200:
            prompt = " ".join(words[:200])

        return prompt

    def build_payload(self, shot: dict, lite_data: dict,
                      canonical_chars: dict,
                      scene_manifest: dict,
                      extend_from: Optional[dict] = None) -> dict:
        """
        Full LTX API payload.
        extend_from: previous clip result dict — triggers ExtendVideo mode
                     for sequential shots of same character/location.
        """
        prompt = self.compile_prompt(shot, lite_data, canonical_chars)

        # Identity anchor: scene-wardrobe-specific Nano Banana frame
        chars    = shot.get("characters_present", [])
        scene_id = shot.get("scene_id", "")
        image_url = None
        if chars:
            char_data = canonical_chars.get(chars[0], {})
            # Prefer scene-specific wardrobe frame, fall back to default NB frame
            image_url = (
                char_data.get("wardrobe_by_scene", {})
                         .get(scene_id, {})
                         .get("nb_frame_url")
                or char_data.get("nb_frame_url")
            )
        # Atmosphere shots: use location reference
        if not image_url:
            image_url = scene_manifest.get("location_reference_url")

        duration    = _clamp_ltx_duration(shot.get("duration_seconds", 6))
        is_slow_mo  = shot.get("slow_motion", False)
        is_atmo     = not chars or shot.get("shot_type", "").lower() == "atmosphere"

        # ExtendVideo mode: same character, continuous action, no location jump
        if extend_from and self._can_extend(extend_from, shot):
            endpoint = "fal-ai/ltx-2.3/image-to-video/fast/extend"
            payload  = {
                "video_url": extend_from["video"]["url"],
                "prompt":    prompt,
                "duration":  duration,
                "mode":      "end",
                "context":   min(4.0, float(extend_from["video"].get("duration", 4))),
            }
        else:
            endpoint = "fal-ai/ltx-2.3/image-to-video/fast"
            payload  = {
                "image_url":      image_url,
                "end_image_url":  shot.get("nb_end_frame_url"),
                "prompt":         prompt,
                "negative_prompt": self.NEGATIVE_PROMPT,
                "duration":       duration,
                "resolution":     "1440p" if is_atmo else "1080p",
                "fps":            48 if is_slow_mo else 25,
                "aspect_ratio":   "16:9",
                "generate_audio": is_atmo,  # LTX ambient audio for atmosphere only
            }
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}

        return {
            "endpoint":    endpoint,
            "payload":     payload,
            "shot_id":     shot.get("shot_id"),
            "model":       "ltx",
            "extend_mode": extend_from is not None and self._can_extend(extend_from, shot),
            "prompt_hash": _hash_prompt(prompt),
        }

    def _can_extend(self, prev_clip: dict, next_shot: dict) -> bool:
        """
        Extend only when same character + same location + under 20s total.
        This is where temporal continuity is handled for free.
        """
        if not prev_clip or not prev_clip.get("video"):
            return False
        if prev_clip.get("shot_data", {}).get("location") != next_shot.get("location"):
            return False
        if prev_clip.get("shot_data", {}).get("characters_present") != \
           next_shot.get("characters_present"):
            return False
        if float(prev_clip["video"].get("duration", 0)) >= 20:
            return False
        return True

    def _derive_lighting_ltx(self, act_tone: str, time_of_day: str) -> str:
        mapping = {
            "curiosity tinged with unease":
                "practical candle light casts warm pools, cold ambient bleeds in from windows",
            "mounting dread":
                "single overhead source, shadow falls heavy below eyeline, fill removed",
            "paranoia":
                "flickering practical source, light shifts unpredictably across faces",
            "catharsis":
                "warm diffused window light expands across frame, shadows soften",
        }
        base = mapping.get(
            act_tone,
            "motivated light from visible source, natural shadow falloff, soft fill"
        )
        if "night" in (time_of_day or "").lower():
            base = "near darkness, single motivated source creates isolated pool of light"
        return base


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER COMPILER — Entry point for the entire system
# This is what orchestrator_server.py calls instead of the 7-layer stack
# ═══════════════════════════════════════════════════════════════════════════════

class ATLASPromptCompiler:
    """
    Single entry point replacing all 7 enrichment layers.
    Called once per shot. Returns model-specific payload ready for FAL.

    Usage:
        compiler = ATLASPromptCompiler(project_truth_path)
        payload  = compiler.compile(shot, scene_manifest)
        result   = await fal.subscribe(payload["endpoint"], input=payload["payload"])
    """

    def __init__(self, project_truth_path: str = "ATLAS_PROJECT_TRUTH.json"):
        self.project_truth_path = project_truth_path
        self._truth    = None
        self._kling    = KlingPromptCompiler()
        self._ltx      = LTXPromptCompiler()
        self._prev_clips: dict = {}  # shot_id → last clip result for extend chaining

    def load(self):
        """Load project truth. Called once at session start."""
        with open(self.project_truth_path, "r") as f:
            self._truth = json.load(f)
        return self

    @property
    def canonical_chars(self) -> dict:
        return self._truth.get("CANONICAL_CHARACTERS", {})

    @property
    def color_anchor(self) -> str:
        return self._truth.get("color_anchor", "")

    def get_lite_data(self, shot: dict) -> dict:
        """
        Pulls the LITE Data Object from Project Truth for this shot.
        This is the condensed global context (act position, emotional
        trajectory, pacing target, color anchor).
        """
        if not self._truth:
            return {}

        scene_id = shot.get("scene_id", "")
        shot_num = shot.get("shot_number", 0)
        total    = self._truth.get("total_shots", 151)

        # Get act position
        act_outline = self._truth.get("act_outline", [])
        act_pos = {}
        for act in act_outline:
            scene_range = act.get("scene_range", [0, 999])
            scene_num   = int(scene_id.replace("scene_", "0").split("_")[0][:3]) if scene_id else 0
            if scene_range[0] <= scene_num <= scene_range[1]:
                act_pos = {
                    "act_name":  act.get("name"),
                    "tone":      act.get("tone"),
                    "act_number": act.get("act_number"),
                }
                break

        # Scene context
        scenes      = self._truth.get("scene_cards", {})
        scene_card  = scenes.get(scene_id, {})
        prev_scene  = scenes.get(f"scene_{int(scene_id[-3:])-1:03d}", {}) if scene_id else {}
        next_scene  = scenes.get(f"scene_{int(scene_id[-3:])+1:03d}", {}) if scene_id else {}

        return {
            "episode_overview":     self._truth.get("episode_overview", {}),
            "act_position":         act_pos,
            "film_progress_pct":    shot_num / max(total, 1),
            "pacing_target":        scene_card.get("tempo", "moderato"),
            "color_anchor":         self.color_anchor,
            "scene_cards_context":  {
                "previous_atmosphere": prev_scene.get("atmosphere", ""),
                "current_atmosphere":  scene_card.get("atmosphere", ""),
                "next_atmosphere":     next_scene.get("atmosphere", ""),
            },
            "emotional_trajectory": {
                "previous": prev_scene.get("emotion_intensity", 0.5),
                "current":  scene_card.get("emotion_intensity", 0.5),
                "next":     next_scene.get("emotion_intensity", 0.5),
            },
        }

    def compile(self, shot: dict, scene_manifest: dict,
                prev_clip_result: Optional[dict] = None) -> dict:
        """
        MAIN ENTRY POINT.
        Takes one shot → returns one model-ready payload.
        Replaces all 7 enrichment layers in a single call.

        Args:
            shot:             Shot dict from shot_plan.json
            scene_manifest:   Scene-level data (location masters, etc.)
            prev_clip_result: Result from previous LTX clip for extend chaining

        Returns:
            Dict with 'endpoint', 'payload', 'model', 'shot_id', 'prompt_hash'
        """
        if not self._truth:
            raise RuntimeError("Call .load() before .compile()")

        lite_data = self.get_lite_data(shot)
        model     = route_model(shot)

        if model == "kling":
            return self._kling.build_payload(
                shot, lite_data, self.canonical_chars, scene_manifest
            )
        else:
            return self._ltx.build_payload(
                shot, lite_data, self.canonical_chars, scene_manifest,
                extend_from=prev_clip_result
            )

    def compile_scene(self, shots: list, scene_manifest: dict) -> list:
        """
        Compile all shots in a scene, threading extend-chain state through
        sequential LTX shots automatically.
        Returns list of payloads in shot order.
        """
        payloads        = []
        last_ltx_result = None  # tracks previous LTX clip for extend chaining

        for shot in shots:
            payload = self.compile(shot, scene_manifest,
                                   prev_clip_result=last_ltx_result)
            payloads.append(payload)

            # Reset LTX chain on location/character change or Kling shot
            if payload["model"] == "kling":
                last_ltx_result = None
            else:
                # Placeholder until real result comes back — holds shot context
                last_ltx_result = {
                    "video": {"url": None, "duration": shot.get("duration_seconds", 6)},
                    "shot_data": shot,
                }

        return payloads


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _clamp_kling_duration(seconds) -> int:
    """Kling accepts 3-15 seconds."""
    return max(3, min(15, int(seconds or 5)))


def _clamp_ltx_duration(seconds) -> int:
    """LTX Fast accepts 6, 8, 10, 12, 14, 16, 18, 20 only."""
    valid = [6, 8, 10, 12, 14, 16, 18, 20]
    s = int(seconds or 6)
    return min(valid, key=lambda v: abs(v - s))


def _hash_prompt(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()[:8]


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK-TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Smoke test without project truth file

    TEST_CANONICAL = {
        "ELEANOR_VOSS": {
            "frontal_image_url":    "https://fal.media/files/eleanor_frontal.png",
            "reference_image_urls": [
                "https://fal.media/files/eleanor_3q.png",
                "https://fal.media/files/eleanor_profile.png",
            ],
            "voice_id":  "eleanor_voice_001",
            "nb_frame_url": "https://fal.media/files/eleanor_nb_scene001.png",
            "wardrobe_by_scene": {
                "scene_001": {
                    "nb_frame_url": "https://fal.media/files/eleanor_charcoal_coat.png",
                    "fabric_note":  "charcoal wool coat moves with weight",
                },
            },
            "default_wardrobe": {},
        },
        "THOMAS_BLACKWOOD": {
            "frontal_image_url":    "https://fal.media/files/thomas_frontal.png",
            "reference_image_urls": [],
            "voice_id":  "thomas_voice_001",
            "nb_frame_url": "https://fal.media/files/thomas_nb.png",
            "wardrobe_by_scene": {},
            "default_wardrobe": {},
        },
    }

    TEST_LITE = {
        "episode_overview":    {"genre": "gothic_horror", "title": "Victorian Shadows"},
        "act_position":        {"act_number": 2, "tone": "mounting dread"},
        "pacing_target":       "andante",
        "film_progress_pct":   0.4,
        "color_anchor":        "desaturated cool tones, teal shadows, warm amber practicals, 35mm film grain, slight vignette",
        "scene_cards_context": {"current_atmosphere": "cold candlelit parlor, storm outside"},
        "emotional_trajectory":{"previous": 0.5, "current": 0.75, "next": 0.85},
    }

    TEST_SCENE = {
        "location_master_url":  "https://fal.media/files/ravencroft_parlor_master.png",
        "location_reference_url": "https://fal.media/files/parlor_ref.png",
    }

    # ── Test KLING shot ───────────────────────────────────────────────────────
    kling_shot = {
        "shot_id":           "001_004A",
        "scene_id":          "scene_001",
        "shot_size":         "MCU",
        "shot_type":         "confrontation",
        "characters_present": ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
        "action_description": "turns to face Thomas, hand still on the mantelpiece",
        "dialogue_text":      "You knew about the will.",
        "emotion_primary":    "controlled_composure",
        "emotion_subtext":    "barely contained fury beneath surface stillness",
        "emotion_intensity":  0.85,
        "duration_seconds":   8,
        "blocking_direction": "Eleanor pivots sharply, closing distance to Thomas",
        "is_scene_anchor":    False,
    }

    kling_compiler = KlingPromptCompiler()
    kling_prompt   = kling_compiler.compile_prompt(kling_shot, TEST_LITE, TEST_CANONICAL)
    kling_payload  = kling_compiler.build_payload(kling_shot, TEST_LITE, TEST_CANONICAL, TEST_SCENE)

    print("═" * 60)
    print("KLING PROMPT (should be 30-100 words, no character description text)")
    print("═" * 60)
    print(kling_prompt)
    print(f"\nWord count: {len(kling_prompt.split())}")
    print(f"Elements:   {len(kling_payload['payload']['elements'])} character(s) locked")
    print(f"Voice IDs:  {kling_payload['payload'].get('voice_ids', [])}")

    # ── Test LTX shot ─────────────────────────────────────────────────────────
    ltx_shot = {
        "shot_id":           "001_006A",
        "scene_id":          "scene_001",
        "shot_size":         "WS",
        "shot_type":         "establishing",
        "characters_present": ["ELEANOR_VOSS"],
        "action_description": "crosses the length of the parlor toward the far window",
        "emotion_primary":    "grief",
        "emotion_intensity":  0.65,
        "duration_seconds":   9,
        "location":           "Ravencroft Manor Victorian parlor",
        "time_of_day":        "late night",
        "lighting_direction": "",
        "slow_motion":        False,
    }

    ltx_compiler = LTXPromptCompiler()
    ltx_prompt   = ltx_compiler.compile_prompt(ltx_shot, TEST_LITE, TEST_CANONICAL)
    ltx_payload  = ltx_compiler.build_payload(ltx_shot, TEST_LITE, TEST_CANONICAL, TEST_SCENE)

    print("\n" + "═" * 60)
    print("LTX PROMPT (should be 4-8 sentences, physical descriptions, no emotion labels)")
    print("═" * 60)
    print(ltx_prompt)
    print(f"\nWord count:   {len(ltx_prompt.split())}")
    print(f"Duration:     {ltx_payload['payload']['duration']}s (valid LTX value)")
    print(f"Resolution:   {ltx_payload['payload']['resolution']}")
    print(f"Extend mode:  {ltx_payload['extend_mode']}")
    print(f"Image anchor: {ltx_payload['payload'].get('image_url', 'None')[:50]}...")

    # ── Test router ───────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("ROUTING TEST")
    print("═" * 60)
    test_shots = [
        {"shot_id": "001_001A", "shot_size": "MCU", "has_dialogue": True,
         "characters_present": ["ELEANOR_VOSS"], "emotion_intensity": 0.9},
        {"shot_id": "001_002A", "shot_size": "WS", "characters_present": [],
         "shot_type": "establishing", "emotion_intensity": 0.3},
        {"shot_id": "001_003A", "shot_size": "MS",
         "characters_present": ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
         "emotion_intensity": 0.5},
        {"shot_id": "001_004A", "shot_size": "CU", "characters_present": ["ELEANOR_VOSS"],
         "emotion_intensity": 0.95},
    ]
    for s in test_shots:
        model = route_model(s)
        print(f"  {s['shot_id']:12} {s['shot_size']:4} {len(s.get('characters_present',[]))} char  "
              f"emotion {s.get('emotion_intensity',0):.1f}  →  {model.upper()}")

    print("\n✓ Compiler smoke test complete")
