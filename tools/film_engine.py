"""
ATLAS Film Engine — Dual-Model Router + Camera Token Translator + Model-Specific Synthesis
============================================================================================
V24.0 — Built from Kling 3.0 / LTX-2.3 / Higgsfield research analysis (March 2026)

This module sits BETWEEN the LITE Synthesizer and the generation endpoints.
It takes model-agnostic LITE output and transforms it into model-specific payloads.

Key insights from research:
  1. Camera brand names (ARRI, Cooke, RED) don't produce consistent results on either model
     → Replace with focal length + aperture + film stock descriptors
  2. Kling 3.0 accepts natural-language emotion ("controlled composure")
     → LTX-2.3 requires physical descriptions ("jaw tight, eyes narrowing")
  3. Kling Elements 3.0 handles single-character identity natively
     → LTX still needs NB frame anchor + face-lock negatives
  4. Kling optimal: 30-100 words, 6-zone structure, ++element++ emphasis
     → LTX optimal: 4-8 sentences, flowing paragraph, concrete nouns/verbs
  5. Kling: multi-shot prompts with character tags, up to 2500 chars
     → LTX: single paragraph under 200 words, max ~800 chars effective

Design:
  - film_engine.route_shot(shot, context) → decides Kling vs LTX
  - film_engine.translate_camera_tokens(prompt) → strips brands, injects physics
  - film_engine.compile_for_model(nano, ltx, context, model) → model-specific output
  - film_engine.build_generation_payload(shot, context, model) → ready-to-send API payload

Integration: Called from orchestrator_server.py AFTER LITE synthesis, BEFORE FAL API call.
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ─────────────────────────────────────────────
# MODEL ROUTING LOGIC
# ─────────────────────────────────────────────

@dataclass
class RoutingDecision:
    """Result of the model router's analysis."""
    model: str              # "kling" or "ltx"
    reason: str             # Human-readable routing rationale
    confidence: float       # 0-1 confidence in this routing
    mode: str               # "identity" | "i2v" | "atmo" | "dialogue"
    cost_estimate: float    # Estimated $ per shot
    identity_critical: bool # Whether character identity is the primary concern


# Shot characteristics that push toward Kling (identity-critical)
KLING_INDICATORS = {
    "shot_types": {"close", "medium_close", "close_up", "mcu", "cu", "extreme_close", "ots"},
    "has_dialogue": True,
    "coverage_roles": {"C_EMOTION"},
    "multi_character": True,  # 2+ characters in frame
}

# Shot characteristics that push toward LTX (cost-effective, environment-heavy)
LTX_INDICATORS = {
    "shot_types": {"wide", "establishing", "master", "extreme_wide", "aerial"},
    "is_broll": True,
    "is_landscape": True,  # No characters
    "coverage_roles": {"A_GEOGRAPHY"},
}

# Cost per shot (approximate, from FAL pricing)
COST_MAP = {
    "kling_identity": 0.56,    # Kling v3 pro with elements
    "kling_dialogue": 0.56,    # Kling v3 pro (lip sync)
    "ltx_i2v": 0.16,           # LTX-2.3 image-to-video fast
    "ltx_atmo": 0.12,          # LTX-2.3 atmosphere/landscape
}


def route_shot(shot: dict, context: dict = None, force_model: str = None) -> RoutingDecision:
    """
    Decide whether a shot should be rendered with Kling 3.0 or LTX-2.3.

    Routing logic (priority order):
    1. Force override (from UI selector or API param)
    2. Close-up + character → Kling (identity critical)
    3. Dialogue shot → Kling (lip sync)
    4. Multi-character close → Kling (feature bleed prevention)
    5. B-roll / no characters → LTX (cost-effective)
    6. Wide/establishing → LTX (environment, not identity)
    7. Default: LTX (cheaper, good enough for medium shots with NB anchor)
    """
    if force_model:
        return RoutingDecision(
            model=force_model,
            reason=f"forced to {force_model} by user/API",
            confidence=1.0,
            mode="identity" if force_model == "kling" else "i2v",
            cost_estimate=COST_MAP.get(f"{force_model}_identity", 0.16),
            identity_critical=force_model == "kling",
        )

    shot_type = shot.get("shot_type", "medium").lower().replace(" ", "_")
    characters = shot.get("characters", [])
    has_chars = len(characters) > 0
    has_dialogue = bool((shot.get("dialogue_text") or "").strip())
    is_broll = shot.get("_broll", False)
    coverage = shot.get("coverage_role", "")

    # Rule 1: B-roll / no characters → always LTX
    if is_broll or not has_chars:
        return RoutingDecision(
            model="ltx", reason="no characters / b-roll → LTX (cost-effective)",
            confidence=0.95, mode="atmo",
            cost_estimate=COST_MAP["ltx_atmo"],
            identity_critical=False,
        )

    # Rule 2: Close-up with character → Kling (identity critical)
    if shot_type in KLING_INDICATORS["shot_types"] and has_chars:
        mode = "dialogue" if has_dialogue else "identity"
        return RoutingDecision(
            model="kling",
            reason=f"close-up + character → Kling ({mode})",
            confidence=0.90,
            mode=mode,
            cost_estimate=COST_MAP[f"kling_{mode}"],
            identity_critical=True,
        )

    # Rule 3: Dialogue on any shot type → Kling (lip sync quality)
    if has_dialogue and has_chars:
        return RoutingDecision(
            model="kling",
            reason="dialogue shot → Kling (lip sync)",
            confidence=0.85,
            mode="dialogue",
            cost_estimate=COST_MAP["kling_dialogue"],
            identity_critical=True,
        )

    # Rule 4: Multi-character medium → Kling (feature bleed prevention)
    if len(characters) >= 2 and shot_type in {"medium", "two_shot", "group"}:
        return RoutingDecision(
            model="kling",
            reason="multi-character medium → Kling (bleed prevention)",
            confidence=0.80,
            mode="identity",
            cost_estimate=COST_MAP["kling_identity"],
            identity_critical=True,
        )

    # Rule 5: C_EMOTION coverage → Kling (emotional close-ups)
    if coverage == "C_EMOTION" and has_chars:
        return RoutingDecision(
            model="kling",
            reason="C_EMOTION coverage → Kling (expression fidelity)",
            confidence=0.85,
            mode="identity",
            cost_estimate=COST_MAP["kling_identity"],
            identity_critical=True,
        )

    # Rule 6: Wide/establishing → LTX (environment shots)
    if shot_type in LTX_INDICATORS["shot_types"]:
        return RoutingDecision(
            model="ltx",
            reason=f"{shot_type} → LTX (environment, cost-effective)",
            confidence=0.90,
            mode="i2v" if has_chars else "atmo",
            cost_estimate=COST_MAP["ltx_i2v"] if has_chars else COST_MAP["ltx_atmo"],
            identity_critical=False,
        )

    # Rule 7: A_GEOGRAPHY coverage → LTX
    if coverage == "A_GEOGRAPHY":
        return RoutingDecision(
            model="ltx",
            reason="A_GEOGRAPHY coverage → LTX (wide framing)",
            confidence=0.80,
            mode="i2v" if has_chars else "atmo",
            cost_estimate=COST_MAP["ltx_i2v"],
            identity_critical=False,
        )

    # Default: LTX (cheaper, NB frame anchor handles identity for mediums)
    return RoutingDecision(
        model="ltx",
        reason="default → LTX (NB anchor sufficient for medium shots)",
        confidence=0.70,
        mode="i2v",
        cost_estimate=COST_MAP["ltx_i2v"],
        identity_critical=False,
    )


# ─────────────────────────────────────────────
# CAMERA TOKEN TRANSLATION
# ─────────────────────────────────────────────
# Research finding: Camera brand names don't produce consistent results.
# Replace with focal length + aperture + film stock descriptors.

CAMERA_BRAND_PATTERNS = [
    # Camera bodies
    (r'\bARRI\s+Alexa\s+\d*\s*(Mini|LF|35)?', ''),
    (r'\bRED\s+(V-?Raptor|Komodo|DSMC\d?|Monstro|Helium)', ''),
    (r'\bSony\s+Venice\s*\d*', ''),
    (r'\bPanavision\s+\w+', ''),
    (r'\bBlackmagic\s+\w+', ''),
    (r'\bCanon\s+(C\d+|EOS\s*R\d*)', ''),
    # Lens brands
    (r'\bCooke\s+S\d+/?i?\s*Prime', ''),
    (r'\bZeiss\s+(Master|Supreme|Standard)\s*\w*', ''),
    (r'\bPanavision\s+(C-Series|Primo|Ultra\s*Speed)', ''),
    (r'\bLeica\s+Summicron\s*\w*', ''),
    (r'\bAngenieux\s+\w+', ''),
    # Generic brand patterns
    (r'\bShot\s+on\s+[A-Z][a-z]+\s+[A-Z][\w\s]*?,', ''),
    (r'\bfilmed\s+on\s+[A-Z][a-z]+\s+[A-Z][\w\s]*?,', ''),
    # Remnant patterns from partial stripping (e.g. "shot on 8K VV" leftover)
    (r',?\s*shot on \d+K\s*(?:VV)?\s*,?', ''),
    (r'\b\d+K\s+VV\b', ''),
]

# Translation: focal length → cinematic descriptor
FOCAL_LENGTH_DESCRIPTORS = {
    "14mm": "14mm ultra-wide, expansive geometric distortion, deep depth of field",
    "18mm": "18mm wide, slight barrel perspective, deep focus",
    "24mm": "24mm wide, slight barrel distortion, expansive field of view",
    "28mm": "28mm moderate wide, natural spatial relationship",
    "35mm": "35mm standard wide, natural perspective, eye-level intimacy",
    "40mm": "40mm standard, naturalistic perspective, minimal distortion",
    "50mm": "50mm normal lens, natural perspective, eye-level intimacy",
    "65mm": "65mm portrait, slight background separation, intimate framing",
    "85mm": "85mm portrait, f/1.8 shallow focus, subject isolation, creamy bokeh",
    "100mm": "100mm telephoto, compressed perspective, background collapse",
    "135mm": "135mm telephoto, strong compression, extreme background collapse, tight framing",
    "200mm": "200mm long telephoto, severe compression, voyeuristic distance",
}

# Camera movement → cinematic verbs (confirmed effective on both models)
CAMERA_MOVEMENT_TOKENS = {
    "static": "locked-off tripod, absolute stillness",
    "locked_tripod": "locked-off tripod, absolute stillness",
    "handheld": "organic handheld drift, documentary truth, subtle breathing",
    "slow_crane": "ascending crane lift, deliberate overhead arc",
    "dolly": "smooth forward dolly, focal compression, encroaching intimacy",
    "dolly_in": "slow forward dolly, focal compression, encroaching intimacy",
    "dolly_out": "pulling dolly retreat, widening perspective, releasing tension",
    "tracking": "lateral tracking shot, parallel motion, constant distance",
    "push_in": "creeping push-in, dread accumulation, closing distance",
    "pull_back": "slow pull-back revealing context, expanding frame",
    "orbit": "slow orbital arc around subject, shifting perspective",
    "steadicam": "Steadicam glide, floating stability, following movement",
    "whip_pan": "whip pan, motion blur transition, disorienting speed",
}

# Color science descriptors — V26.1 FIX: Stripped ALL film stock brand names per Law 235
# "Kodak 2383 print look" caused literal film-damage textures on FAL.
# These are now PURE color/tone descriptors that both Kling 3.0 and LTX-2.3 interpret correctly.
COLOR_SCIENCE_TOKENS = {
    "gothic_horror": "desaturated cool tones, teal shadows, amber practicals, fine organic grain",
    "noir": "high contrast monochrome, silver halide grain, deep shadow pools, hard light",
    "period": "warm amber candlelight tones, gentle filmic warmth, period grain texture",
    "thriller": "desaturated cold blue undertones, harsh shadow edges, clinical precision",
    "drama": "naturalistic muted earth tones, soft grain, gentle contrast, warm diffusion",
    "fantasy": "rich saturated warmth, golden hour diffusion, ethereal halation on highlights",
    "horror": "crushed blacks, sickly green shifted, high ISO grain, underexposed shadow pools",
    "sci_fi": "cool blue clinical steel, neon accent spill, clean digital precision",
}


def translate_camera_tokens(prompt: str, genre: str = "gothic_horror") -> str:
    """
    Strip camera brand names and replace with effective cinematic descriptors.

    Research finding: "50mm, f/2.8, warm halation on highlights, Kodak 2383 print look"
    consistently produces more reliable results than "shot on ARRI Alexa with Cooke S4 lenses."
    """
    result = prompt

    # Strip all camera brand patterns
    for pattern, replacement in CAMERA_BRAND_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Clean up artifacts from stripping
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r'\.\s*\.', '.', result)
    result = re.sub(r'\s{2,}', ' ', result)

    return result.strip()


def build_camera_zone(
    lens_specs: str,
    camera_style: str,
    shot_type: str,
    coverage_role: str = "",
) -> str:
    """
    Build the CAMERA zone using effective tokens instead of brand names.
    Returns a compact camera descriptor string.
    """
    parts = []

    # Focal length descriptor
    focal = FOCAL_LENGTH_DESCRIPTORS.get(lens_specs, f"{lens_specs} lens")
    parts.append(focal)

    # Camera movement
    movement = CAMERA_MOVEMENT_TOKENS.get(camera_style, f"{camera_style} movement")
    parts.append(movement)

    # Shot type
    if coverage_role:
        parts.append(f"{shot_type}, {coverage_role}")
    else:
        parts.append(shot_type)

    return ". ".join(parts)


# ─────────────────────────────────────────────
# EMOTION TRANSLATION (LTX REQUIRES PHYSICAL)
# ─────────────────────────────────────────────
# Research: Kling interprets natural-language performance direction.
# LTX requires physical descriptions — "jaw tight, eyes narrowing" not "angry".

EMOTION_TO_PHYSICAL = {
    # Emotion label → physical description for LTX
    "dread": "jaw clenched, pupils dilated searching the space, breath shallow and held, shoulders drawn inward",
    "fear": "eyes wide scanning rapidly, nostrils flared, body pulled back, hands trembling slightly",
    "grief": "suppressed emotion visible at jaw line, breath shallow, eyes glistening with unshed tears, head slightly bowed",
    "sadness": "downcast gaze, slight tremor in lower lip, shoulders curved inward, slow deliberate breathing",
    "anger": "stillness before eruption, lips pressed white, contained fury in clenched fists, narrowed eyes",
    "rage": "veins visible at temple, teeth bared, explosive stance, hands gripping nearest object",
    "tension": "micro-stillness, controlled breathing, eyes tracking without head movement, jaw muscles flexing",
    "suspense": "body frozen mid-motion, breath held, pupils fixed on single point, fingers spread rigid",
    "hope": "chin lifting slightly, eyes widening with light, breath deepening, shoulders dropping tension",
    "wonder": "pupils dilated, slight lip part, head tilts upward, breath held in reverence",
    "resolve": "jaw set firmly, eyes level and direct, breath steady through nose, hands still at sides",
    "love": "soft focus in eyes, slight smile at lip corners, body leaning toward subject, relaxed hands",
    "deceit": "carefully neutral expression masking calculation, brief micro-tell at eye corner, controlled smile",
    "defiance": "chin raised, direct unflinching gaze, squared shoulders, weight shifted forward on feet",
    "exhaustion": "heavy eyelids fighting to stay open, shoulders sagging, breath coming in shallow bursts",
    "revelation": "eyes snapping wide, mouth opening slightly, body freezing then straightening, sharp inhale",
    "neutral": "relaxed natural expression, even breathing, balanced posture",
    "composure": "controlled composure, measured breathing, hands deliberately still, face revealing nothing",
}

# Kling-specific emotion tokens (natural language works)
EMOTION_FOR_KLING = {
    "dread": "controlled fear, attempting composure while sensing something wrong",
    "fear": "genuine visceral fear, fight-or-flight visible in every muscle",
    "grief": "deep quiet grief, barely contained emotional weight",
    "anger": "explosive anger barely contained, seconds from eruption",
    "tension": "coiled tension, hyper-aware of surroundings, ready to move",
    "hope": "cautious hope emerging through pain, trying to believe",
    "resolve": "steely resolve, decision made, no turning back",
    "deceit": "masterful deception, warm exterior concealing cold calculation",
}


def translate_emotion_for_model(
    emotion: str,
    model: str,
    character_name: str = "",
) -> str:
    """
    Translate emotion labels into model-appropriate performance direction.

    Kling: natural language works ("controlled composure, quiet grief")
    LTX: must be physical ("jaw clenched, breath shallow, eyes glistening")
    """
    emotion_key = emotion.lower().strip()

    if model == "kling":
        desc = EMOTION_FOR_KLING.get(emotion_key, emotion)
        if character_name:
            return f"{character_name}: {desc}"
        return desc

    # LTX: physical descriptions required
    physical = EMOTION_TO_PHYSICAL.get(emotion_key)
    if not physical:
        # V26.1 FIX: Generic fallback violated Law 245. Use CPC emotion×posture map
        # if available, otherwise produce concrete physical description
        try:
            from tools.creative_prompt_compiler import get_physical_direction
            physical = get_physical_direction(emotion_key, "standing")
        except (ImportError, Exception):
            # Fallback: concrete physical description, NOT generic "visible in posture"
            physical = (
                f"body still, {emotion} visible in tightened jaw, "
                f"measured breathing, hands pressed against surface"
            )

    if character_name:
        return f"{character_name} — {physical}"
    return physical


# ─────────────────────────────────────────────
# MODEL-SPECIFIC PROMPT COMPILATION
# ─────────────────────────────────────────────

def compile_for_kling(
    nano_prompt: str,
    ltx_prompt: str,
    context: dict,
    routing: RoutingDecision,
) -> Dict[str, str]:
    """
    Transform LITE prompts into Kling 3.0 optimized format.

    V27.2 REWRITE based on Kling 3.0 API research (FAL prompting guide, March 2026):
    - Up to 2500 chars (NOT 250 — that was wrong)
    - Directorial language: Scene → Characters → Action → Camera → Dialogue
    - Character tags: [Character A: Role, appearance]
    - Dialogue format: [Character, tone]: "dialogue text"
    - Natural-language emotion works — Kling's strength
    - Camera behavior over time, not static descriptions
    - Trust Kling's native physics for body motion
    - NO dense LTX-style per-frame choreography

    Uses NEW context fields from V27.1.6:
    - _room_dna, _lighting_rig, _focal_enforcement
    - _timed_choreography, _beat_action, _dialogue_text
    - _split_anti_morph
    """
    sd = context.get("shot_details", {})
    characters = context.get("characters", {})
    narr = context.get("narrative", {})
    va = context.get("visual_anchor", {})
    wardrobe = context.get("wardrobe", {})
    intent = context.get("actor_intent", {})

    # V27.2: NEW context fields
    room_dna = context.get("_room_dna", "")
    lighting_rig = context.get("_lighting_rig", "")
    dialogue_text = context.get("_dialogue_text", "")
    beat_action = context.get("_beat_action", "")

    # Strip camera brands from nano
    clean_nano = translate_camera_tokens(nano_prompt, va.get("genre", "gothic_horror"))

    kling_parts = []

    # Zone 1: Camera direction (cinematic intent, not specs)
    shot_type = sd.get("shot_type", "medium")
    cam = build_camera_zone(
        va.get("lens_specs", "50mm"),
        va.get("camera_style", "handheld"),
        shot_type,
        sd.get("coverage_role", ""),
    )
    kling_parts.append(cam)

    # Zone 2: Characters (Kling character tag format with appearance)
    if characters:
        for i, (name, data) in enumerate(characters.items()):
            char_tag = f"[Character {'ABCDEF'[i]}: {name}"
            if data.get("appearance"):
                char_tag += f", {data['appearance'][:120]}"
            if wardrobe.get(name):
                char_tag += f", wearing {wardrobe[name]}"
            char_tag += "]"
            kling_parts.append(char_tag)

    # Zone 3: Emotion + Performance (Kling's native strength)
    if intent:
        emotion = intent.get("emotion", "")
        if emotion:
            kling_parts.append(translate_emotion_for_model(emotion, "kling"))
        if beat_action:
            kling_parts.append(beat_action[:100])

    # Zone 4: Dialogue (Kling supports native audio/dialogue)
    if dialogue_text and characters:
        # Format: [Character, tone]: "dialogue"
        speaker = list(characters.keys())[0] if characters else ""
        emotion = intent.get("emotion", "measured")
        dlg_short = dialogue_text[:250]
        kling_parts.append(f'[{speaker}, {emotion} voice]: "{dlg_short}"')

    # Zone 5: Room DNA (condensed for Kling — key architecture, not full spec)
    if room_dna:
        kling_parts.append(room_dna[:200])
    elif va.get("location"):
        kling_parts.append(va["location"][:100])

    # Zone 6: Lighting + Atmosphere
    if lighting_rig:
        kling_parts.append(lighting_rig[:100])
    elif narr.get("atmosphere"):
        kling_parts.append(narr["atmosphere"][:80])

    # Color science (no film stock brands)
    genre = va.get("genre", "gothic_horror")
    color_sci = COLOR_SCIENCE_TOKENS.get(genre, COLOR_SCIENCE_TOKENS["gothic_horror"])
    kling_parts.append(color_sci)

    # Identity emphasis
    if routing.identity_critical and characters:
        first_char = list(characters.keys())[0]
        kling_parts.append(f"++{first_char} identity consistent++")

    kling_nano = ". ".join(p.strip().rstrip(".") for p in kling_parts if p.strip())

    # V26.1: Translate camera tokens on FINAL output
    kling_nano = translate_camera_tokens(kling_nano, genre)

    # Structural negatives only (Kling has native photorealism)
    kling_nano += ". NO grid, NO collage, NO split screen"

    # Enforce 2500 char limit (Kling's actual max, not 250)
    if len(kling_nano) > 2500:
        kling_nano = kling_nano[:2497] + "..."

    # V27.2: Build Kling-specific VIDEO prompt (directorial, not LTX-style dense)
    # Kling video prompt: camera behavior + dialogue + emotion direction
    # Trust native physics — don't over-choreograph body movement
    kling_motion_parts = []
    kling_motion_parts.append(cam)

    # Character performance (natural language — Kling understands this)
    if characters and intent:
        emotion = intent.get("emotion", "")
        if emotion:
            kling_motion_parts.append(f"{emotion}, subtle physical shift")
        if beat_action:
            kling_motion_parts.append(beat_action[:120])

    # Dialogue for video (lip sync + speech)
    if dialogue_text and characters:
        speaker = list(characters.keys())[0]
        dlg_short = dialogue_text[:300]
        kling_motion_parts.append(
            f'[{speaker}, {intent.get("emotion", "measured")} voice]: "{dlg_short}". '
            f"Mouth moves forming words, natural speech rhythm"
        )

    # Split anti-morph for Kling
    if context.get("_split_anti_morph") and characters:
        kling_motion_parts.append(
            "Facial features stay consistent. Natural breathing and gestures continue"
        )

    kling_motion = ". ".join(p.strip().rstrip(".") for p in kling_motion_parts if p.strip())
    if len(kling_motion) > 2500:
        kling_motion = kling_motion[:2497] + "..."

    return {
        "nano_prompt": kling_nano,
        "ltx_motion_prompt": kling_motion,
        "model": "kling",
        "mode": routing.mode,
        "cost_estimate": routing.cost_estimate,
    }


def compile_for_ltx(
    nano_prompt: str,
    ltx_prompt: str,
    context: dict,
    routing: RoutingDecision,
) -> Dict[str, str]:
    """
    Transform LITE prompts into LTX-2.3 optimized format.

    LTX specifics:
    - Optimal: 4-8 sentences, under 200 words, flowing paragraph
    - Concrete nouns and verbs weighted heavily (not vague descriptors)
    - Imperative phrasing outperforms narrative language
    - Zone-separated clauses with colons render more consistently
    - Negative prompts STILL recommended: "worst quality, inconsistent motion, blurry"
    - Emotions MUST be physical descriptions, not labels
    - Film stock references work well ("Kodak Vision3 500T")
    - Focal length + aperture reduce edge shimmer by ~18%
    """
    sd = context.get("shot_details", {})
    characters = context.get("characters", {})
    narr = context.get("narrative", {})
    va = context.get("visual_anchor", {})
    wardrobe = context.get("wardrobe", {})
    intent = context.get("actor_intent", {})
    photo_anchors = context.get("photo_anchors", {})
    anti_cgi = context.get("anti_cgi", "")
    gold = context.get("gold_negatives", "")

    # Strip camera brands
    clean_nano = translate_camera_tokens(nano_prompt, va.get("genre", "gothic_horror"))

    # Build LTX-optimized nano as flowing paragraph with clause separators
    ltx_parts = []

    # Camera clause (focal + aperture + film stock)
    lens = va.get("lens_specs", "50mm")
    focal_desc = FOCAL_LENGTH_DESCRIPTORS.get(lens, f"{lens} lens")
    genre = va.get("genre", "gothic_horror")
    color_sci = COLOR_SCIENCE_TOKENS.get(genre, COLOR_SCIENCE_TOKENS["gothic_horror"])
    ltx_parts.append(f"{focal_desc}: {color_sci}")

    # Subject clause (concrete physical descriptions)
    if characters:
        for name, data in characters.items():
            desc_parts = [name]
            if data.get("appearance"):
                desc_parts.append(data["appearance"][:100])
            if wardrobe.get(name):
                desc_parts.append(f"wearing {wardrobe[name]}")
            ltx_parts.append(", ".join(desc_parts))

    # Action clause (concrete verbs, imperative phrasing)
    if narr.get("action"):
        ltx_parts.append(narr["action"])

    # Emotion clause (PHYSICAL descriptions for LTX, never labels)
    if characters and intent:
        emotion = intent.get("emotion", "")
        if emotion:
            physical = translate_emotion_for_model(emotion, "ltx")
            ltx_parts.append(physical)

    # Environment clause
    if va.get("location"):
        ltx_parts.append(va["location"])

    # Color grade
    cg = va.get("color_grade", "")
    if cg:
        ltx_parts.append(f"Color grade: {cg}")

    # Photorealistic anchors (LTX needs these, Kling doesn't)
    if photo_anchors:
        anchor_text = ", ".join(f"{v}" for v in photo_anchors.values())
        ltx_parts.append(anchor_text)

    # ── NEGATIVE VOCABULARY GOES TO negative_prompt ONLY — NEVER in positive prompt ──
    # V26.1 FIX: These were being appended to the POSITIVE prompt, causing FAL to
    # literally generate "worst quality, blurry" images. nano-banana-pro has no
    # separate negative field, but LTX payload builder has negative_prompt.
    # Gold standard + anti-CGI are structural negatives for the NEGATIVE field.
    negative_parts = []
    if gold:
        negative_parts.append(gold)
    if anti_cgi:
        negative_parts.append(anti_cgi)
    negative_parts.append("worst quality, inconsistent motion, blurry, jittery, distorted")

    ltx_nano = ". ".join(p.strip().rstrip(".") for p in ltx_parts if p.strip())

    # V26.1 FIX: Run translate_camera_tokens on FINAL compiled output (not just input)
    # Camera brands can enter via context fields, not just the raw nano_prompt
    ltx_nano = translate_camera_tokens(ltx_nano, genre)

    # NO concatenation of negatives into positive prompt — they go to result["_negative_prompt"]

    # Trim to effective range (under 200 words, ~1500 chars)
    words = ltx_nano.split()
    if len(words) > 200:
        ltx_nano = " ".join(words[:200])
    ltx_nano = ltx_nano[:1500]

    # LTX motion prompt: flowing paragraph, concrete verbs
    # Already well-formatted from LITE — just ensure physical emotion
    ltx_motion = ltx_prompt
    if intent and isinstance(intent, dict) and intent.get("emotion"):
        emotion = intent["emotion"]
        if emotion.lower() in EMOTION_TO_PHYSICAL:
            # Replace emotion labels with physical descriptions in LTX motion
            ltx_motion = re.sub(
                rf'\b{re.escape(emotion)}\b',
                EMOTION_TO_PHYSICAL[emotion.lower()][:60],
                ltx_motion,
                flags=re.IGNORECASE,
                count=1,
            )

    return {
        "nano_prompt": ltx_nano,
        "ltx_motion_prompt": ltx_motion,
        "_negative_prompt": ". ".join(negative_parts),  # V26.1: negative vocab separated from positive
        "model": "ltx",
        "mode": routing.mode,
        "cost_estimate": routing.cost_estimate,
    }


# ─────────────────────────────────────────────
# GENERATION PAYLOAD BUILDERS
# ─────────────────────────────────────────────

def build_kling_payload(
    frame_url: str,
    prompt: str,
    duration: int = 6,
    negative_prompt: str = "",
    elements: list = None,
) -> dict:
    """
    Build a FAL-compatible Kling v3 Pro i2v payload.

    V27.1: Fixed to match actual FAL API at fal-ai/kling-video/v3/pro/image-to-video.
    Production-verified params from orchestrator_server.py line 6368 + line 32648.

    FAL Kling v3 API params:
      - prompt: str (motion/action description)
      - start_image_url: str (base64 or URL — Kling uses start_image_url, NOT image_url)
      - duration: str ("3" | "5" | "8" | "10" | "12" | "15") — string, not int
      - aspect_ratio: str ("16:9")
      - negative_prompt: str (optional)

    NOT valid for Kling: model_name, mode, num_frames, width, height, seed, image_url
    Cost: ~$0.56/shot
    """
    # Snap to valid Kling durations
    KLING_VALID_DURATIONS = [3, 5, 8, 10, 12, 15]
    snapped = min(KLING_VALID_DURATIONS, key=lambda x: abs(x - min(duration, 15)))

    payload = {
        "start_image_url": frame_url,  # Kling uses start_image_url (NOT image_url)
        "prompt": prompt,
        "duration": str(snapped),  # Kling takes string, not int
        "aspect_ratio": "16:9",
    }

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    # Kling Elements 3.0 — inject character reference images for identity lock
    if elements:
        payload["elements"] = elements

    return payload


def build_ltx_payload(
    frame_url: str,
    prompt: str,
    duration: int = 6,
    negative_prompt: str = "",
) -> dict:
    """
    Build a FAL-compatible LTX-2.3 i2v payload.

    V27.1: Matched to actual FAL API at fal-ai/ltx-2.3/image-to-video/fast.
    Production-verified params from orchestrator_server.py line 32648.

    FAL LTX-2.3 Fast API params:
      - prompt: str
      - image_url: str (base64 or URL — LTX uses image_url, NOT start_image_url)
      - duration: int (6, 8, 10, 12, 14, 16, 18, 20) — int, not string
      - negative_prompt: str
      - aspect_ratio: str ("16:9")

    Cost: ~$0.16/shot
    """
    # Snap to valid LTX durations (even seconds, 6-20)
    LTX_VALID_DURATIONS = [6, 8, 10, 12, 14, 16, 18, 20]
    snapped = min(LTX_VALID_DURATIONS, key=lambda x: abs(x - min(duration, 20)))

    payload = {
        "image_url": frame_url,  # LTX uses image_url (NOT start_image_url)
        "prompt": prompt,
        "negative_prompt": negative_prompt or "worst quality, inconsistent motion, blurry, jittery, distorted",
        "duration": snapped,  # LTX takes int
        "aspect_ratio": "16:9",
    }

    return payload


# Model strings for FAL API calls
FAL_MODELS = {
    "kling": "fal-ai/kling-video/v3/pro/image-to-video",
    "ltx": "fal-ai/ltx-2.3/image-to-video/fast",
    "seeddance": "fal-ai/bytedance/seedance/v2/image-to-video",
    "nano": "fal-ai/nano-banana-pro",
    "nano_edit": "fal-ai/nano-banana-pro/edit",
}


def get_fal_model_string(model_key: str) -> str:
    """Return the correct FAL API model string for a model key."""
    return FAL_MODELS.get(model_key, FAL_MODELS["ltx"])


# ─────────────────────────────────────────────
# MAIN API: COMPILE SHOT FOR MODEL
# ─────────────────────────────────────────────

def compile_shot_for_model(
    shot: dict,
    context: dict,
    force_model: str = None,
) -> dict:
    """
    Full Film Engine pipeline for a single shot.

    1. Route shot to optimal model
    2. Translate camera tokens
    3. Compile model-specific prompts
    4. Return ready-to-use prompts + metadata

    Returns dict with:
      - nano_prompt: model-optimized image prompt
      - ltx_motion_prompt: model-optimized motion prompt
      - model: "kling" or "ltx"
      - routing: full RoutingDecision
      - mode: "identity" | "i2v" | "atmo" | "dialogue"
      - cost_estimate: float
    """
    # Get LITE prompts (may already exist from synthesizer)
    nano = shot.get("nano_prompt_lite") or shot.get("nano_prompt", "")
    ltx = shot.get("ltx_prompt_lite") or shot.get("ltx_motion_prompt", "")

    # Step 1: Route
    routing = route_shot(shot, context, force_model)

    # Step 2+3: Compile for specific model
    if routing.model == "kling":
        result = compile_for_kling(nano, ltx, context, routing)
    else:
        result = compile_for_ltx(nano, ltx, context, routing)

    # ── V26.1 FIX: DIALOGUE MARKER INJECTION ──
    # Law 87/142: Every shot with dialogue MUST have "character speaks:" in ltx_motion_prompt
    # Film Engine was missing this entirely — dialogue shots got static LTX prompts
    dialogue_text = shot.get("dialogue_text") or shot.get("dialogue") or ""
    chars = shot.get("characters") or []
    if dialogue_text and chars:
        ltx_out = result.get("ltx_motion_prompt", "")
        if "character speaks:" not in ltx_out.lower():
            # V26.2 FIX: Parse ACTUAL speaker from dialogue_text instead of always chars[0]
            # dialogue_text format: "CHARACTER NAME: dialogue line..."
            speaker = None
            dlg_clean = dialogue_text.strip()
            if ":" in dlg_clean[:60]:
                potential_speaker = dlg_clean.split(":", 1)[0].strip().upper()
                # Verify the potential speaker is actually in the characters list
                for c in chars:
                    c_upper = c.upper() if isinstance(c, str) else str(c).upper()
                    # V26.2 FIX: Exact match OR first/last name match only
                    # Was: bidirectional substring ("ART" matched "ARTHUR", "APARTMENT" matched "ART")
                    # Now: exact match, or potential_speaker is a whole word within c_upper
                    if potential_speaker == c_upper:
                        speaker = c if isinstance(c, str) else str(c)
                        break
                    # Check if potential_speaker matches any whole word in character name
                    c_words = set(c_upper.split())
                    if potential_speaker in c_words and len(potential_speaker) >= 3:
                        speaker = c if isinstance(c, str) else str(c)
                        break
                dlg_clean = dlg_clean.split(":", 1)[1].strip()
            if not speaker:
                speaker = chars[0] if isinstance(chars[0], str) else str(chars[0])
            dlg_short = dlg_clean[:100]
            result["ltx_motion_prompt"] = (
                f"{speaker} character speaks: \"{dlg_short}\", mouth moves forming words, "
                f"subtle gestures while speaking. {ltx_out}"
            )

    # ── V26.2 FIX: MULTI-CHARACTER DESCRIPTION INJECTION FOR OTS/TWO-SHOTS ──
    # Root cause: context["characters"] arrives empty. shot.characters[] has names but no data.
    # For OTS and two-shot types, we MUST describe ALL characters in the prompt.
    shot_type = (shot.get("shot_type") or "").lower()
    cast_map = context.get("cast_map") or {}
    is_multi_char = shot_type in ("ots", "over_the_shoulder", "two_shot", "two-shot", "group")
    if chars and len(chars) > 1 and cast_map:
        # Build character descriptions from cast_map for ALL characters in the shot
        char_descs = []
        for char_name in chars:
            cn = char_name if isinstance(char_name, str) else str(char_name)
            # Look up in cast_map (case-insensitive)
            cm_entry = None
            for cm_key, cm_val in cast_map.items():
                if cm_key.upper() == cn.upper():
                    cm_entry = cm_val
                    break
            if cm_entry and isinstance(cm_entry, dict):
                appearance = cm_entry.get("appearance", "")
                if appearance:
                    char_descs.append(f"{cn}: {appearance[:120]}")
        if char_descs:
            # Inject multi-character descriptions into nano_prompt
            multi_desc = ". ".join(char_descs)
            nano_out = result.get("nano_prompt", "")
            # Only inject if not already present
            if char_descs and nano_out and chars[1].split()[0].upper() not in nano_out.upper():
                if is_multi_char:
                    # OTS: speaker (chars[0]) FACES camera, other char is the shoulder
                    # V26.2 FIX: Was reversed — chars[1] was facing, chars[0] was shoulder
                    # If shot has dialogue, use dialogue speaker as facing character
                    dlg = shot.get("dialogue_text") or shot.get("dialogue") or ""
                    facing_idx = 0  # default: first char faces camera
                    if dlg and ":" in dlg[:60]:
                        dlg_speaker = dlg.split(":", 1)[0].strip().upper()
                        for ci, cn in enumerate(chars):
                            cn_up = cn.upper() if isinstance(cn, str) else str(cn).upper()
                            if dlg_speaker == cn_up:
                                facing_idx = ci
                                break
                    shoulder_idx = 1 - facing_idx if len(chars) == 2 else (1 if facing_idx == 0 else 0)
                    facing = chars[facing_idx] if isinstance(chars[facing_idx], str) else str(chars[facing_idx])
                    shoulder = chars[shoulder_idx] if isinstance(chars[shoulder_idx], str) else str(chars[shoulder_idx])
                    ots_direction = f"Over-the-shoulder shot: {shoulder} (back to camera, shoulder visible), {facing} faces camera. "
                    result["nano_prompt"] = f"{ots_direction}{multi_desc}. {nano_out}"
                else:
                    result["nano_prompt"] = f"{multi_desc}. {nano_out}"
            # Also inject into LTX for motion continuity
            ltx_out = result.get("ltx_motion_prompt", "")
            if char_descs and ltx_out and chars[1].split()[0].upper() not in ltx_out.upper():
                result["ltx_motion_prompt"] = f"{multi_desc}. {ltx_out}"

    # ── V26.1 FIX: CPC DECONTAMINATION ──
    # Law 236-241: Creative Prompt Compiler strips generic patterns and replaces
    # with emotion-driven physical direction. Was never integrated into Film Engine.
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt, is_prompt_generic
        nano_out = result.get("nano_prompt", "")
        if nano_out and is_prompt_generic(nano_out):
            emotion = (context.get("actor_intent") or {}).get("emotion", "tension")
            result["nano_prompt"] = decontaminate_prompt(nano_out, emotion=emotion)
            result["_cpc_decontaminated"] = True
    except ImportError:
        pass  # CPC not available — Film Engine works standalone

    # Add routing metadata
    result["routing"] = {
        "model": routing.model,
        "reason": routing.reason,
        "confidence": routing.confidence,
        "mode": routing.mode,
        "cost_estimate": routing.cost_estimate,
        "identity_critical": routing.identity_critical,
    }

    # V24.1: Inject continuity memory delta if available
    # V26.1 FIX: Field names corrected — compile functions output "nano_prompt" and
    # "ltx_motion_prompt", NOT "nano_prompt_compiled" / "ltx_prompt_compiled"
    try:
        continuity_delta = context.get("_continuity_delta", "")
        if continuity_delta:
            compiled_nano = result.get("nano_prompt", "")
            # V26.2 FIX: Continuity delta is spatial state (character positions, camera geometry)
            # This belongs in nano_prompt (image gen) ONLY — NOT ltx_motion_prompt (video motion)
            # LTX needs action/motion direction, not spatial coordinates
            # Was: injected into BOTH nano + ltx, causing spatial noise in motion prompts
            if compiled_nano:
                result["nano_prompt"] = compiled_nano + "\n\n" + continuity_delta
            result["_continuity_injected"] = True

        # B-roll continuity injection
        broll_delta = context.get("_broll_continuity", "")
        if broll_delta:
            compiled_nano = result.get("nano_prompt", "")
            if compiled_nano:
                result["nano_prompt"] = compiled_nano + "\n\n" + broll_delta
            result["_broll_continuity_injected"] = True

    except Exception:
        pass  # Continuity memory not available — Film Engine works standalone

    # ── V26.2 FIX: DIALOGUE MARKER DEDUP SAFETY NET ──
    # fix-v16 enrichment may have already injected "character speaks:" into the
    # ltx_motion_prompt stored in shot_plan.json. Film Engine's compile_for_ltx()
    # passes through that text, then the post-compile injection at line 731 adds
    # another. This dedup catches any stacking (seen up to 9x in production).
    import re
    ltx_final = result.get("ltx_motion_prompt", "")
    if ltx_final:
        # Count occurrences of "character speaks:" pattern — handles both:
        #   "NAME character speaks:" and bare "character speaks:"
        speaks_pattern = re.compile(r'(?:\w[\w\s]*?\s+)?character speaks:', re.IGNORECASE)
        matches = list(speaks_pattern.finditer(ltx_final))
        if len(matches) > 1:
            # Keep only the FIRST occurrence block, strip all subsequent
            # Find the end of the first block (up to next period, comma-clause, or next match)
            first_match_end = matches[0].end()
            # Find extent of first block's content (to next sentence boundary or next match)
            next_match_start = matches[1].start()
            first_block = ltx_final[:next_match_start]
            # Strip ALL subsequent "character speaks:" blocks from remainder
            remainder = ltx_final[next_match_start:]
            remainder = speaks_pattern.sub('', remainder)
            # Clean up leftover punctuation/whitespace
            remainder = re.sub(r'\s*,\s*,', ',', remainder)
            remainder = re.sub(r'\s+', ' ', remainder).strip()
            result["ltx_motion_prompt"] = (first_block.rstrip(", ") + " " + remainder).strip()
            result["_dialogue_deduped"] = len(matches) - 1

    return result


def estimate_scene_cost(
    shots: list,
    force_model: str = None,
) -> dict:
    """
    Estimate rendering cost for a scene with smart routing.
    Returns cost breakdown by model and total.
    """
    kling_count = 0
    ltx_count = 0
    total_cost = 0.0
    decisions = []

    for shot in shots:
        routing = route_shot(shot, force_model=force_model)
        if routing.model == "kling":
            kling_count += 1
        else:
            ltx_count += 1
        total_cost += routing.cost_estimate
        decisions.append({
            "shot_id": shot.get("shot_id"),
            "model": routing.model,
            "mode": routing.mode,
            "reason": routing.reason,
            "cost": routing.cost_estimate,
        })

    return {
        "total_shots": len(shots),
        "kling_shots": kling_count,
        "ltx_shots": ltx_count,
        "kling_pct": round(kling_count / max(len(shots), 1) * 100, 1),
        "ltx_pct": round(ltx_count / max(len(shots), 1) * 100, 1),
        "estimated_cost": round(total_cost, 2),
        "kling_cost": round(kling_count * COST_MAP["kling_identity"], 2),
        "ltx_cost": round(ltx_count * COST_MAP["ltx_i2v"], 2),
        "decisions": decisions,
    }


def estimate_project_cost(
    shots: list,
    force_model: str = None,
) -> dict:
    """
    Estimate full project rendering cost with scene breakdown.
    """
    # Group by scene
    scenes = {}
    for shot in shots:
        sid = shot.get("scene_id", "unknown")
        if sid not in scenes:
            scenes[sid] = []
        scenes[sid].append(shot)

    scene_estimates = {}
    total_cost = 0.0
    total_kling = 0
    total_ltx = 0

    for scene_id, scene_shots in sorted(scenes.items()):
        est = estimate_scene_cost(scene_shots, force_model)
        scene_estimates[scene_id] = est
        total_cost += est["estimated_cost"]
        total_kling += est["kling_shots"]
        total_ltx += est["ltx_shots"]

    return {
        "total_shots": len(shots),
        "total_scenes": len(scenes),
        "total_kling": total_kling,
        "total_ltx": total_ltx,
        "estimated_total_cost": round(total_cost, 2),
        "smart_routing_savings": round(
            len(shots) * COST_MAP["kling_identity"] - total_cost, 2
        ),  # Savings vs all-Kling
        "scene_breakdown": scene_estimates,
    }
