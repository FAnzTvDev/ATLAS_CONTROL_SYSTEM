"""
ATLAS LITE Synthesizer — 3-Stage Prompt Pipeline (V24.0 Upgraded)
==================================================================
Replaces the V22 9-layer string-concatenation enrichment stack with:
  Stage 1: Context Object (structured JSON, no string manipulation)
  Stage 2: LLM Synthesizer (single LLM call replaces 7 enrichment layers)
  Stage 3: Native Visual Anchoring (trust LTX-2's image lock for chains)
  Stage 4: Film Engine (dual-model compilation — Kling 3.0 vs LTX-2.3)

V24 Additions:
  - LITE Data Object integration (Global Perception from project_truth.py)
  - Hard Zone Separation (5 zones with character budgets)
  - Photorealistic Quality Anchors (anti-CGI markers)
  - Scene Tempo Tags (allegro/andante/adagio/moderato)
  - Basal Ganglia scoring integration point
  - Actor Intent Layer injection

V24.0 Additions (Film Engine Integration):
  - Dual-model routing: auto-select Kling vs LTX per shot
  - Camera token translation: strip brands, inject focal + aperture + film stock
  - Model-specific prompt compilation (Kling: tags + natural emotion, LTX: physical + flowing)
  - Cost estimation per scene/project with smart routing savings

Usage:
  from tools.atlas_lite_synthesizer import synthesize_shot, synthesize_scene

Design principle: NO string concatenation. NO regex cleanup. NO 40-agent pipeline.
The LLM sees structured data and produces clean, non-contradictory prompts in one pass.
The Film Engine then adapts output for the optimal model per shot.
"""

import json
import os
import re
import httpx
import asyncio
import hashlib
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Fast + cheap model for synthesis (not creative writing — structured output)
SYNTH_MODEL = "google/gemini-2.0-flash-001"  # ~$0.10/M tokens, <1s latency
SYNTH_MODEL_FALLBACK = "anthropic/claude-3-5-haiku-20241022"  # backup

# Gold standard negatives — these NEVER change
GOLD_NEGATIVES = (
    "NO grid, NO collage, NO split screen, NO extra people, "
    "NO morphing faces, NO watermarks, NO text overlays, NO babies, "
    "NO children unless script specifies"
)

GOLD_LTX_CHARACTER = (
    "face stable NO morphing, identity consistent, no expression morphing, "
    "maintain exact character appearance"
)

GOLD_LTX_LANDSCAPE = "NO morphing, NO face generation, environment only"

# ─────────────────────────────────────────────
# V24: HARD ZONE SEPARATION
# ─────────────────────────────────────────────
# 5 strict zones — each has a character budget. Content NEVER leaks across zones.

ZONE_BUDGETS = {
    "CAMERA": {
        "max_chars": 120,
        "includes": ["lens_specs", "camera_body", "camera_style", "shot_type", "coverage_role"],
        "never_includes": ["character names", "emotions", "actions", "colors"],
    },
    "CHARACTER": {
        "max_chars": 300,
        "includes": ["appearance", "wardrobe", "stature", "age"],
        "never_includes": ["camera", "lens", "color grade", "environment"],
    },
    "PERFORMANCE": {
        "max_chars": 250,
        "includes": ["action", "emotion", "dialogue", "micro_action", "eyeline", "tempo"],
        "never_includes": ["camera", "appearance", "environment"],
    },
    "ENVIRONMENT": {
        "max_chars": 200,
        "includes": ["location", "lighting", "atmosphere", "color_grade", "time_of_day"],
        "never_includes": ["character names", "dialogue", "camera"],
    },
    "CONSTRAINTS": {
        "max_chars": 250,
        "includes": ["gold_negatives", "face_stability", "anti_morph"],
        "never_includes": [],
    },
}

# ─────────────────────────────────────────────
# V24: PHOTOREALISTIC QUALITY ANCHORS
# ─────────────────────────────────────────────
# Anti-CGI markers injected to push toward photorealistic output

PHOTOREALISTIC_ANCHORS = {
    "skin": "natural skin texture with pores and imperfections, subsurface scattering",
    "eyes": "wet reflective eyes with visible catch light, natural iris detail",
    "hair": "individual hair strands, natural hair movement, not plastic or clumped",
    "lighting": "motivated lighting from visible source, natural shadow falloff",
    "fabric": "real fabric texture with weight and drape, visible weave pattern",
}

ANTI_CGI_NEGATIVES = (
    "NO plastic skin, NO CGI look, NO airbrushed, NO video game render, "
    "NO 3D render, NO uncanny valley, NO wax figure, NO symmetrical face, "
    "NO floating objects, NO impossible physics"
)

# ─────────────────────────────────────────────
# V24: SCENE TEMPO TAGS
# ─────────────────────────────────────────────
SCENE_TEMPO_MAP = {
    "allegro": {"camera": "quick cuts, tracking movement", "action_pace": "rapid, urgent"},
    "andante": {"camera": "steady movement, deliberate pacing", "action_pace": "measured, walking pace"},
    "adagio": {"camera": "slow push, lingering holds", "action_pace": "slow, contemplative, weighted"},
    "moderato": {"camera": "balanced movement", "action_pace": "natural, conversational"},
}

# Genre color grades (from scene_anchor_system.py)
GENRE_COLOR_GRADE = {
    "gothic_horror": "cold desaturated grade, teal shadows, period grain, NO warm green tones",
    "horror": "crushed blacks, sickly green undertones, desaturated",
    "noir": "high contrast black and white, deep shadows, silver tones",
    "period": "warm amber, candlelight warmth, film grain, aged look",
    "fantasy": "rich saturated colors, golden hour warmth, ethereal glow",
    "sci_fi": "cool blue steel, neon accents, clinical white",
    "drama": "naturalistic, muted earth tones, soft contrast",
    "thriller": "desaturated, cold blue undertones, harsh shadows",
}

# Emotion color grades (fallback if no genre match)
EMOTION_COLOR_GRADE = {
    "dread": "cold desaturated grade, teal-blue shadows, crushed blacks, no warm tones",
    "tension": "high contrast, deep blacks, sharp shadows, no soft light",
    "grief": "muted desaturated, blue-grey, soft shadows, no bright colors",
    "hope": "warm golden hour, amber tones, soft light",
    "revelation": "stark white light, high key, blown highlights",
    "fear": "dark, underexposed, deep shadows, cold tones",
    "anger": "red-shifted, high contrast, harsh light",
    "love": "warm soft focus, golden, romantic light",
    "suspense": "teal-orange split, deep shadows",
    "horror": "green-shifted, crushed blacks, sickly undertones",
    "mystery": "blue-shifted, fog, soft edges",
    "neutral": "balanced natural light, neutral tones",
}

# Dialogue duration clamps
DIALOGUE_DURATION_CLAMP = {
    "close": (5, 10), "medium": (5, 10), "medium_close": (5, 10),
    "title_card": (5, 10), "reaction": (5, 10), "insert": (5, 10),
    "wide": (8, 15), "establishing": (10, 20), "master": (10, 20),
}

# Even-second durations only (LTX-2 constraint)
VALID_LTX_DURATIONS = [4, 6, 8, 10, 12, 14, 16, 18, 20]


# ─────────────────────────────────────────────
# STAGE 1: CONTEXT OBJECT BUILDER
# ─────────────────────────────────────────────

def build_context_object(
    shot: dict,
    cast_map: dict,
    story_bible: dict,
    genre: str = "gothic_horror",
    scene_emotion: str = "dread",
) -> dict:
    """
    Stage 1: Build a pure JSON context object from shot + project data.
    NO string concatenation. NO prompt building. Just structured data.
    """
    shot_id = shot.get("shot_id", "")
    scene_id = shot.get("scene_id", "")
    characters = shot.get("characters", [])
    has_characters = len(characters) > 0
    has_dialogue = bool(shot.get("dialogue_text", "").strip())

    # ── Shot details ──
    shot_details = {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "shot_type": shot.get("shot_type", "medium"),
        "coverage_role": shot.get("coverage_role", ""),
        "duration": _snap_to_even(shot.get("duration", 6)),
        "has_characters": has_characters,
        "has_dialogue": has_dialogue,
        "is_broll": shot.get("_broll", False),
        "is_chained": shot.get("_should_chain", False) and not shot.get("_no_chain", False),
        "is_chain_anchor": shot.get("_is_chain_first", False),
        "chain_position": shot.get("_chain_position", 0),
    }

    # ── Narrative (from beat/description) ──
    narrative = {
        "description": shot.get("description", ""),
        "action": "",
        "dialogue": "",
        "atmosphere": "",
    }

    # Extract beat action if available
    if shot.get("_beat_action"):
        narrative["action"] = shot["_beat_action"]
    elif shot.get("description"):
        narrative["action"] = shot["description"]

    if has_dialogue:
        narrative["dialogue"] = shot.get("dialogue_text", "")

    # Scene atmosphere from story bible
    scenes = story_bible.get("scenes", [])
    for sc in scenes:
        if sc.get("scene_id") == scene_id:
            narrative["atmosphere"] = sc.get("atmosphere", "")
            break

    # ── Visual anchor (color grade + camera) ──
    color_grade = _resolve_color_grade(genre, scene_emotion)
    visual_anchor = {
        "color_grade": color_grade,
        "genre": genre,
        "camera_body": shot.get("camera_body", "ARRI Alexa 35"),
        "camera_style": shot.get("camera_style", "handheld"),
        "lens_specs": shot.get("lens_specs", "50mm"),
        "lens_type": shot.get("lens_type", "Cooke S7/i Prime"),
        "location": shot.get("location", ""),
        "int_ext": "INT" if shot.get("location", "").startswith("INT") else "EXT",
    }

    # ── Character data (from cast_map, NOT AI actor descriptions) ──
    character_data = {}
    if has_characters:
        for char_name in characters:
            cast_entry = cast_map.get(char_name, {})
            if cast_entry.get("_is_alias_of"):
                continue
            character_data[char_name] = {
                "appearance": cast_entry.get("appearance", ""),
                "has_reference_image": bool(cast_entry.get("character_reference_url")),
            }

    # ── Actor intent (if available) ──
    actor_intent = {}
    if shot.get("actor_intent"):
        actor_intent = shot["actor_intent"]

    # ── Wardrobe (if available) ──
    wardrobe = {}
    if shot.get("_wardrobe_tag"):
        for char_name in characters:
            wardrobe[char_name] = shot.get("_wardrobe_tag", "")

    # ── Chain context (for chained shots) ──
    chain_context = {}
    if shot_details["is_chained"]:
        chain_context = {
            "has_end_frame_image": bool(shot.get("_chain_first_frame_url")),
            "environment_locked_by_image": True,
            "prompt_should_contain": "action_and_emotion_only",
            "prompt_should_NOT_contain": "environment_description",
        }

    # ── V24: LITE Data Object (Global Perception) ──
    lite_data = {}
    try:
        from tools.project_truth import ProjectTruth
        truth_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                   "pipeline_outputs",
                                   story_bible.get("project_id", ""))
        if os.path.exists(os.path.join(truth_path, "ATLAS_PROJECT_TRUTH.json")):
            truth = ProjectTruth.load(truth_path)
            lite_data = truth.get_lite_data_object(shot)
    except Exception:
        pass  # LITE data is enhancement, not requirement

    # ── V24: Scene tempo (from LITE data or default) ──
    scene_tempo = lite_data.get("pacing_target", "moderato") if lite_data else "moderato"
    tempo_config = SCENE_TEMPO_MAP.get(scene_tempo, SCENE_TEMPO_MAP["moderato"])

    # ── V24: Photorealistic anchors (character shots only) ──
    photo_anchors = {}
    if has_characters:
        photo_anchors = PHOTOREALISTIC_ANCHORS.copy()

    return {
        "shot_details": shot_details,
        "narrative": narrative,
        "visual_anchor": visual_anchor,
        "characters": character_data,
        "actor_intent": actor_intent,
        "wardrobe": wardrobe,
        "chain_context": chain_context,
        "gold_negatives": GOLD_NEGATIVES,
        # V24 additions
        "lite_data": lite_data,
        "scene_tempo": scene_tempo,
        "tempo_config": tempo_config,
        "photo_anchors": photo_anchors,
        "anti_cgi": ANTI_CGI_NEGATIVES if has_characters else "",
        "zone_budgets": ZONE_BUDGETS,
    }


# ─────────────────────────────────────────────
# STAGE 2: LLM SYNTHESIZER
# ─────────────────────────────────────────────

SYNTH_SYSTEM_PROMPT = """You are the ATLAS LITE Prompt Synthesizer V24. Your job is to read a JSON shot context object and produce exactly TWO clean prompt strings for AI image/video generation.

RULES (STRICT):
1. Output ONLY valid JSON with exactly two keys: "nano_prompt" and "ltx_prompt"
2. nano_prompt = what the STILL IMAGE should look like (for fal-ai/nano-banana-pro)
3. ltx_prompt = how the VIDEO should MOVE (for fal-ai/ltx-2 image-to-video)
4. NEVER use AI actor names (no "Isabella Moretti", "Charlotte Beaumont", etc.)
5. NEVER duplicate information — say each thing ONCE
6. NEVER put camera/lens instructions in ltx_prompt (that's for nano only)
7. NEVER put motion/timing instructions in nano_prompt (that's for ltx only)
8. If has_characters is false: NO people, NO faces, NO human figures in either prompt
9. If is_chained is true: nano_prompt is EMPTY (image comes from previous video's end frame). ltx_prompt describes ONLY motion/action/emotion — NO environment description (environment locked by image)
10. If has_dialogue: ltx_prompt MUST include "character speaks: [dialogue]" and "lips moving naturally"
11. nano_prompt max length: 1500 characters
12. ltx_prompt max length: 400 characters
13. ltx_prompt MUST start with duration: "[N]s, " and end with the appropriate suffix:
    - Character shots: "face stable NO morphing, identity consistent"
    - No-character shots: "NO morphing, NO face generation, environment only"
14. Color grade from visual_anchor.color_grade MUST appear in nano_prompt
15. Gold negatives MUST appear at END of nano_prompt

HARD ZONE SEPARATION (V24 — content NEVER leaks between zones):
Zone 1 CAMERA: lens, body, style, shot type (max 120 chars)
Zone 2 CHARACTER: appearance, wardrobe, stature (max 300 chars)
Zone 3 PERFORMANCE: action, emotion, dialogue, micro_action (max 250 chars)
Zone 4 ENVIRONMENT: location, lighting, atmosphere, color grade (max 200 chars)
Zone 5 CONSTRAINTS: gold negatives, face stability, anti-CGI (max 250 chars)

PHOTOREALISTIC QUALITY (V24 — for character shots):
- Describe natural skin with pores, not plastic
- Eyes should have catch light and iris detail
- Hair should be individual strands, not clumped
- Fabric should have visible weave and weight
- Lighting should be motivated from visible source

SCENE TEMPO (V24 — if tempo_config provided):
- Use the camera movement style from tempo_config
- Match action pacing to tempo_config.action_pace

GLOBAL CONTEXT (V24 — if lite_data provided):
- Use act_position to calibrate emotional weight
- Use emotional_trajectory to inform character expression
- scene_cards_context shows what came before/after — maintain narrative flow

NANO_PROMPT STRUCTURE (in this order):
[CAMERA: shot_type, coverage, lens, body] [CHARACTER: appearance, wardrobe] [PERFORMANCE: action, emotion, micro_action] [ENVIRONMENT: location, color grade, atmosphere] [CONSTRAINTS: gold negatives, anti-CGI, face stability]

LTX_PROMPT STRUCTURE:
[duration]s, [tempo-appropriate motion]. [character action if any]. [dialogue if any]. [timing]. [gold suffix]"""

SYNTH_USER_TEMPLATE = """Generate prompts for this shot:

```json
{context_json}
```

Respond with ONLY valid JSON:
{{"nano_prompt": "...", "ltx_prompt": "..."}}"""


async def synthesize_with_llm(
    context: dict,
    api_key: str = "",
    model: str = SYNTH_MODEL,
) -> Tuple[str, str]:
    """
    Stage 2: Send context object to LLM, get back clean nano + ltx prompts.
    One LLM call replaces 7 enrichment layers.
    """
    if not api_key:
        api_key = OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")

    if not api_key:
        raise ValueError("No OPENROUTER_API_KEY configured")

    # Compact JSON (no need to send full verbose context)
    compact_context = _compact_context(context)
    user_msg = SYNTH_USER_TEMPLATE.format(context_json=json.dumps(compact_context, indent=2))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://atlas.fanztv.com",
        "X-Title": "ATLAS LITE Synthesizer",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYNTH_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,  # Low creativity — we want consistency
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return result.get("nano_prompt", ""), result.get("ltx_prompt", "")
        except Exception as e:
            # Fallback: try backup model
            if model != SYNTH_MODEL_FALLBACK:
                print(f"[LITE] Primary model failed ({e}), trying fallback...")
                return await synthesize_with_llm(context, api_key, SYNTH_MODEL_FALLBACK)
            raise


def synthesize_deterministic(context: dict) -> Tuple[str, str]:
    """
    Stage 2 FALLBACK: Deterministic synthesis without LLM.
    Still uses the context object pattern — just templates instead of LLM.
    This is what runs if LLM is unavailable or for dry-run testing.
    """
    sd = context["shot_details"]
    narr = context["narrative"]
    va = context["visual_anchor"]
    chars = context["characters"]
    wardrobe = context.get("wardrobe", {})
    intent = context.get("actor_intent", {})
    chain = context.get("chain_context", {})
    gold = context.get("gold_negatives", GOLD_NEGATIVES)
    lite_data = context.get("lite_data", {})
    tempo_config = context.get("tempo_config", SCENE_TEMPO_MAP["moderato"])
    photo_anchors = context.get("photo_anchors", {})
    anti_cgi = context.get("anti_cgi", "")

    duration = sd["duration"]
    has_chars = sd["has_characters"]
    has_dialogue = sd["has_dialogue"]
    is_chained = sd["is_chained"]

    # ── NANO PROMPT (V24: Hard Zone Separation) ──
    if is_chained:
        nano = ""
    else:
        # ZONE 1: CAMERA (max 120 chars) — V24.0: use translated tokens, not brand names
        try:
            from tools.film_engine import build_camera_zone
            zone_camera = build_camera_zone(
                va['lens_specs'], va.get('camera_style', 'handheld'),
                sd['shot_type'], sd.get('coverage_role', ''),
            )
        except ImportError:
            # Fallback: focal length + shot type (no brands)
            zone_camera = f"{va['lens_specs']} {sd['shot_type']}"
            if sd["coverage_role"]:
                zone_camera += f", {sd['coverage_role']}"
        zone_camera = zone_camera[:ZONE_BUDGETS["CAMERA"]["max_chars"]]

        # ZONE 2: CHARACTER (max 300 chars)
        zone_character = ""
        if has_chars:
            char_parts = []
            for name, data in chars.items():
                desc = data.get("appearance", "")
                if desc:
                    char_parts.append(f"{name}: {desc}")
                if wardrobe.get(name):
                    char_parts.append(f"{name} wearing {wardrobe[name]}")
            zone_character = ". ".join(char_parts)
            if zone_character:
                zone_character += "."
            # V24: Add photorealistic skin/eye anchors for characters
            if photo_anchors:
                zone_character += f" {photo_anchors.get('skin', '')}."
            zone_character = zone_character[:ZONE_BUDGETS["CHARACTER"]["max_chars"]]

        # ZONE 3: PERFORMANCE (max 250 chars)
        zone_performance = ""
        if has_chars:
            perf_parts = []
            if narr["action"]:
                perf_parts.append(f"Character action: {narr['action']}")
            if intent:
                if isinstance(intent, dict):
                    if intent.get("emotion"):
                        perf_parts.append(f"emotion: {intent['emotion']}")
                    if intent.get("stature"):
                        perf_parts.append(f"posture: {intent['stature']}")
                    if intent.get("micro_action"):
                        perf_parts.append(f"micro-action: {intent['micro_action']}")
                    if intent.get("eyeline_target"):
                        perf_parts.append(f"eyes on: {intent['eyeline_target']}")
            # V24: Emotional trajectory from LITE data
            if lite_data and lite_data.get("emotional_trajectory"):
                traj = lite_data["emotional_trajectory"]
                if traj.get("current_emotion"):
                    perf_parts.append(f"scene emotion: {traj['current_emotion']}")
            zone_performance = ". ".join(perf_parts)
            if zone_performance:
                zone_performance += "."
            zone_performance = zone_performance[:ZONE_BUDGETS["PERFORMANCE"]["max_chars"]]

        # ZONE 4: ENVIRONMENT (max 200 chars)
        zone_env_parts = [f"{va['location']}"]
        zone_env_parts.append(f"Color grade: {va['color_grade']}")
        if narr.get("atmosphere"):
            zone_env_parts.append(narr["atmosphere"][:60])
        zone_environment = ". ".join(zone_env_parts) + "."
        if not has_chars:
            zone_environment += " NO people, NO faces, NO human figures."
        zone_environment = zone_environment[:ZONE_BUDGETS["ENVIRONMENT"]["max_chars"]]

        # ZONE 5: CONSTRAINTS (max 250 chars)
        zone_constraints = gold
        if anti_cgi:
            zone_constraints += " " + anti_cgi
        zone_constraints = zone_constraints[:ZONE_BUDGETS["CONSTRAINTS"]["max_chars"]]

        # Assemble nano with zone separators
        nano_zones = [zone_camera]
        if zone_character:
            nano_zones.append(zone_character)
        if zone_performance:
            nano_zones.append(zone_performance)
        nano_zones.append(zone_environment)
        nano_zones.append(zone_constraints)

        nano = " ".join(z.strip() for z in nano_zones if z.strip())
        if len(nano) > 1500:
            nano = nano[:1497] + "..."

    # ── LTX PROMPT (V24: Tempo-aware) ──
    ltx_parts = [f"{duration}s"]

    # Camera motion — V24: use tempo config
    style = va.get("camera_style", "handheld")
    tempo_camera = tempo_config.get("camera", "balanced movement")
    if style == "slow_crane":
        ltx_parts.append("slow crane movement, establishing atmosphere")
    elif style == "handheld":
        ltx_parts.append(f"subtle handheld, {tempo_camera}")
    elif style in ("static", "locked_tripod"):
        ltx_parts.append("locked camera, static, minimal movement")
    elif style == "dolly":
        ltx_parts.append(f"smooth dolly push, {tempo_config.get('action_pace', 'deliberate')}")
    else:
        ltx_parts.append(f"{style} movement, {tempo_camera}")

    # Character action
    if has_chars and narr["action"]:
        action_text = narr["action"]
        # V24: Inject actor intent micro_action if available
        if intent and isinstance(intent, dict) and intent.get("micro_action"):
            action_text += f", {intent['micro_action']}"
        ltx_parts.append(f"character performs: {action_text}")

    # Dialogue
    if has_dialogue:
        dlg = narr["dialogue"][:200]
        ltx_parts.append(f"character speaks: {dlg}, lips moving naturally")

    # Timing
    ltx_parts.append(f"0-{duration}s continuous motion")

    # Gold suffix
    if has_chars:
        ltx_parts.append(GOLD_LTX_CHARACTER)
    else:
        ltx_parts.append(GOLD_LTX_LANDSCAPE)

    ltx = ", ".join(ltx_parts)
    if len(ltx) > 400:
        ltx = ltx[:397] + "..."

    return nano, ltx


# ─────────────────────────────────────────────
# STAGE 3: NATIVE VISUAL ANCHORING
# ─────────────────────────────────────────────

def apply_chain_anchoring(
    nano_prompt: str,
    ltx_prompt: str,
    context: dict,
) -> Tuple[str, str]:
    """
    Stage 3: For chained shots, trust the image lock.
    - nano_prompt is EMPTY (image comes from end frame)
    - ltx_prompt contains ONLY action/motion/emotion
    - No environment words, no location descriptions
    """
    if not context["shot_details"]["is_chained"]:
        return nano_prompt, ltx_prompt

    # Chained shot: nano is empty (end frame IS the image)
    nano_prompt = ""

    # Strip any environment words that might have leaked through
    # (safety net — LLM should already handle this, but just in case)
    env_words = re.compile(
        r'\b(ritual|chamber|altar|candles?|stone|walls?|manor|corridor|hall|'
        r'chapel|church|tomb|crypt|dungeon|cellar|tower|balcony|staircase|'
        r'garden|courtyard|gate|bridge|forest|clearing|cave|cliff|shore|'
        r'village|tavern|inn|pub|library|study|bedroom|kitchen|parlour|throne)\b',
        re.IGNORECASE
    )
    cleaned_ltx = env_words.sub('', ltx_prompt)
    # Clean up double spaces/commas
    cleaned_ltx = re.sub(r'\s{2,}', ' ', cleaned_ltx)
    cleaned_ltx = re.sub(r',\s*,', ',', cleaned_ltx)

    # Safety: if stripped too much, use original
    if len(cleaned_ltx.strip()) < 20:
        cleaned_ltx = ltx_prompt

    return nano_prompt, cleaned_ltx


# ─────────────────────────────────────────────
# MAIN API: SYNTHESIZE A SHOT
# ─────────────────────────────────────────────

async def synthesize_shot(
    shot: dict,
    cast_map: dict,
    story_bible: dict,
    genre: str = "gothic_horror",
    scene_emotion: str = "dread",
    use_llm: bool = True,
    api_key: str = "",
    force_model: str = None,
    enable_film_engine: bool = True,
) -> dict:
    """
    Full ATLAS LITE pipeline for a single shot.
    Returns the shot dict with nano_prompt_lite, ltx_prompt_lite, and Film Engine data added.

    V24.0: Now includes Stage 4 (Film Engine) which:
      - Routes shot to optimal model (Kling vs LTX)
      - Translates camera tokens (strips brands, injects physics)
      - Compiles model-specific prompts
      - Adds cost estimate and routing rationale
    """
    # Stage 1: Build context object
    context = build_context_object(shot, cast_map, story_bible, genre, scene_emotion)

    # Stage 2: Synthesize prompts
    if use_llm:
        try:
            nano, ltx = await synthesize_with_llm(context, api_key)
        except Exception as e:
            print(f"[LITE] LLM synthesis failed for {shot.get('shot_id')}: {e}")
            print(f"[LITE] Falling back to deterministic synthesis")
            nano, ltx = synthesize_deterministic(context)
    else:
        nano, ltx = synthesize_deterministic(context)

    # Stage 3: Apply chain anchoring
    nano, ltx = apply_chain_anchoring(nano, ltx, context)

    # Write LITE prompts alongside V22 prompts (don't overwrite)
    shot["nano_prompt_lite"] = nano
    shot["ltx_prompt_lite"] = ltx
    shot["_lite_context"] = context  # Keep context for debugging
    shot["_lite_timestamp"] = datetime.utcnow().isoformat()
    shot["_lite_model"] = SYNTH_MODEL if use_llm else "deterministic"

    # Stage 4: Film Engine — dual-model compilation
    if enable_film_engine:
        try:
            from tools.film_engine import compile_shot_for_model, route_shot
            film_result = compile_shot_for_model(shot, context, force_model)
            shot["_film_engine"] = {
                "model": film_result["model"],
                "mode": film_result["mode"],
                "routing": film_result.get("routing", {}),
                "cost_estimate": film_result.get("cost_estimate", 0),
                "nano_prompt_model": film_result["nano_prompt"],
                "ltx_prompt_model": film_result["ltx_motion_prompt"],
            }
            shot["_routed_model"] = film_result["model"]
            shot["_routed_mode"] = film_result["mode"]
        except ImportError:
            pass  # Film Engine not available — non-blocking
        except Exception as e:
            print(f"[LITE] Film Engine failed for {shot.get('shot_id')}: {e}")

    return shot


async def synthesize_scene(
    shots: List[dict],
    scene_id: str,
    cast_map: dict,
    story_bible: dict,
    genre: str = "gothic_horror",
    scene_emotion: str = "dread",
    use_llm: bool = True,
    api_key: str = "",
) -> List[dict]:
    """
    Synthesize all shots in a scene through ATLAS LITE.
    Returns list of shots with LITE prompts added.
    """
    scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
    results = []

    for shot in scene_shots:
        result = await synthesize_shot(
            shot, cast_map, story_bible, genre, scene_emotion, use_llm, api_key
        )
        results.append(result)
        print(f"  [LITE] {shot['shot_id']}: nano={len(result.get('nano_prompt_lite',''))}c, ltx={len(result.get('ltx_prompt_lite',''))}c")

    return results


async def synthesize_project(
    project_path: str,
    use_llm: bool = True,
    scene_filter: Optional[str] = None,
) -> dict:
    """
    Run ATLAS LITE on an entire project (or filtered scene).
    Writes nano_prompt_lite and ltx_prompt_lite alongside V22 prompts.
    """
    # Load project data
    shot_plan_path = os.path.join(project_path, "shot_plan.json")
    cast_map_path = os.path.join(project_path, "cast_map.json")
    bible_path = os.path.join(project_path, "story_bible.json")

    with open(shot_plan_path) as f:
        data = json.load(f)
    shots = data.get("shots", data) if isinstance(data, dict) else data

    with open(cast_map_path) as f:
        cast_map = json.load(f)

    bible = {}
    if os.path.exists(bible_path):
        with open(bible_path) as f:
            bible = json.load(f)

    genre = bible.get("genre", "gothic_horror")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    # Filter scenes if requested
    if scene_filter:
        target_shots = [s for s in shots if s.get("scene_id") == scene_filter]
    else:
        target_shots = shots

    print(f"\n[ATLAS LITE] Synthesizing {len(target_shots)} shots...")
    print(f"[ATLAS LITE] Model: {SYNTH_MODEL if use_llm else 'deterministic'}")
    print(f"[ATLAS LITE] Genre: {genre}")

    for shot in target_shots:
        scene_emotion = _get_scene_emotion(shot.get("scene_id", ""), bible)
        await synthesize_shot(shot, cast_map, bible, genre, scene_emotion, use_llm, api_key)

    # Save (atomic)
    import tempfile
    if isinstance(data, dict):
        data["shots"] = shots
        save_data = data
    else:
        save_data = shots

    fd, tmp = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(shot_plan_path))
    with os.fdopen(fd, "w") as f:
        json.dump(save_data, f, indent=2)
    os.replace(tmp, shot_plan_path)

    synthesized = len([s for s in target_shots if s.get("nano_prompt_lite") is not None])
    print(f"\n[ATLAS LITE] Done: {synthesized}/{len(target_shots)} shots synthesized")

    return {
        "success": True,
        "total": len(target_shots),
        "synthesized": synthesized,
        "model": SYNTH_MODEL if use_llm else "deterministic",
    }


# ─────────────────────────────────────────────
# A/B COMPARISON
# ─────────────────────────────────────────────

def compare_v22_vs_lite(shot: dict) -> dict:
    """
    Compare V22 prompts vs LITE prompts for a single shot.
    Returns a human-readable comparison.
    """
    return {
        "shot_id": shot.get("shot_id"),
        "characters": shot.get("characters", []),
        "v22": {
            "nano_prompt": shot.get("nano_prompt", "")[:300],
            "nano_length": len(shot.get("nano_prompt", "")),
            "ltx_prompt": shot.get("ltx_motion_prompt", "")[:300],
            "ltx_length": len(shot.get("ltx_motion_prompt", "")),
        },
        "lite": {
            "nano_prompt": shot.get("nano_prompt_lite", "")[:300],
            "nano_length": len(shot.get("nano_prompt_lite", "")),
            "ltx_prompt": shot.get("ltx_prompt_lite", "")[:300],
            "ltx_length": len(shot.get("ltx_prompt_lite", "")),
        },
        "analysis": {
            "v22_has_character_contamination": _check_contamination(
                shot.get("nano_prompt", ""), shot.get("characters", [])
            ),
            "lite_has_character_contamination": _check_contamination(
                shot.get("nano_prompt_lite", ""), shot.get("characters", [])
            ),
            "v22_nano_length_ok": len(shot.get("nano_prompt", "")) <= 2000,
            "lite_nano_length_ok": len(shot.get("nano_prompt_lite", "")) <= 1500,
        }
    }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _resolve_color_grade(genre: str, scene_emotion: str = "neutral") -> str:
    """
    Resolve color grade from genre string, handling compound genres like
    'gothic horror, psychological thriller, supernatural drama'.
    Priority: exact genre match > word-level match > emotion > neutral fallback.
    """
    if not genre:
        return EMOTION_COLOR_GRADE.get(scene_emotion, "balanced natural light, neutral tones")

    # 1. Exact match (e.g., "gothic_horror")
    genre_key = genre.lower().strip().replace(" ", "_")
    if genre_key in GENRE_COLOR_GRADE:
        return GENRE_COLOR_GRADE[genre_key]

    # 2. Word-level match for compound genres like "gothic horror, psychological thriller"
    # Split on commas, try each sub-genre
    for sub_genre in genre.lower().split(","):
        sub_key = sub_genre.strip().replace(" ", "_")
        if sub_key in GENRE_COLOR_GRADE:
            return GENRE_COLOR_GRADE[sub_key]

    # 3. Partial word match — "gothic horror" → "gothic_horror"
    genre_lower = genre.lower()
    for key in GENRE_COLOR_GRADE:
        # Check if genre key words appear in the genre string
        key_words = key.replace("_", " ")
        if key_words in genre_lower:
            return GENRE_COLOR_GRADE[key]

    # 4. Single keyword match — "gothic" in "gothic horror, psychological thriller"
    genre_words = set(re.split(r'[,\s]+', genre_lower))
    for key in GENRE_COLOR_GRADE:
        key_parts = key.split("_")
        if any(kp in genre_words for kp in key_parts):
            return GENRE_COLOR_GRADE[key]

    # 5. Emotion fallback
    return EMOTION_COLOR_GRADE.get(scene_emotion, "balanced natural light, neutral tones")


def _snap_to_even(duration: int) -> int:
    """Snap duration to nearest valid LTX-2 even second."""
    if duration <= 0:
        return 6
    closest = min(VALID_LTX_DURATIONS, key=lambda x: abs(x - duration))
    return closest


def _compact_context(context: dict) -> dict:
    """Strip verbose fields for LLM input (reduce token cost)."""
    compact = {
        "shot": context["shot_details"],
        "narrative": context["narrative"],
        "visual": {
            "color_grade": context["visual_anchor"]["color_grade"],
            "camera": f"{context['visual_anchor']['lens_specs']}, {context['visual_anchor']['camera_style']}",
            "location": context["visual_anchor"]["location"],
        },
        "gold_negatives": context["gold_negatives"],
    }

    if context["characters"]:
        compact["characters"] = context["characters"]
    if context["wardrobe"]:
        compact["wardrobe"] = context["wardrobe"]
    if context["actor_intent"]:
        compact["actor_intent"] = context["actor_intent"]
    if context["chain_context"]:
        compact["chain"] = context["chain_context"]

    # V24: Include LITE data for global perception
    lite_data = context.get("lite_data", {})
    if lite_data:
        compact["global_context"] = {
            "act_position": lite_data.get("act_position", ""),
            "emotional_trajectory": lite_data.get("emotional_trajectory", {}),
            "pacing_target": lite_data.get("pacing_target", "moderato"),
            "film_progress_pct": lite_data.get("film_progress_pct", 0),
        }

    # V24: Include tempo and photorealistic config
    if context.get("scene_tempo"):
        compact["scene_tempo"] = context["scene_tempo"]
    if context.get("tempo_config"):
        compact["tempo_config"] = context["tempo_config"]
    if context.get("photo_anchors"):
        compact["photorealistic_anchors"] = context["photo_anchors"]
    if context.get("anti_cgi"):
        compact["anti_cgi_negatives"] = context["anti_cgi"]

    return compact


def _get_scene_emotion(scene_id: str, story_bible: dict) -> str:
    """Get primary emotion for a scene from story bible."""
    scenes = story_bible.get("scenes", [])
    for sc in scenes:
        if sc.get("scene_id") == scene_id:
            atmo = sc.get("atmosphere", "").lower()
            for emotion in EMOTION_COLOR_GRADE:
                if emotion in atmo:
                    return emotion
            return "neutral"
    return "neutral"


def _check_contamination(prompt: str, characters: list) -> bool:
    """Check if a no-character shot has character names in its prompt."""
    if characters:
        return False  # Has characters, contamination check doesn't apply
    # Strip gold negatives before checking (they contain "children" which matches CHILD)
    import re as _re_cc
    clean = _re_cc.sub(r'NO\s+\w+', '', prompt)  # Strip "NO xxx" patterns
    clean_upper = clean.upper()
    char_names = ["EVELYN", "MARGARET", "ARTHUR", "CLARA", "ELIAS", "LAWYER", "BARTENDER"]
    # Use word boundary check to avoid false positives
    for name in char_names:
        pattern = r'\b' + name + r'\b'
        if _re_cc.search(pattern, clean_upper):
            return True
    return False


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
    scene = sys.argv[2] if len(sys.argv) > 2 else None
    use_llm = "--llm" in sys.argv
    deterministic = "--deterministic" in sys.argv or not use_llm

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_path = os.path.join(base, "pipeline_outputs", project)

    print(f"\n{'='*60}")
    print(f"ATLAS LITE SYNTHESIZER")
    print(f"{'='*60}")
    print(f"Project: {project}")
    print(f"Scene: {scene or 'ALL'}")
    print(f"Mode: {'LLM' if use_llm else 'Deterministic'}")
    print(f"{'='*60}\n")

    result = asyncio.run(synthesize_project(
        project_path,
        use_llm=use_llm,
        scene_filter=scene,
    ))

    print(f"\n{'='*60}")
    print(f"RESULT: {result}")
    print(f"{'='*60}")
