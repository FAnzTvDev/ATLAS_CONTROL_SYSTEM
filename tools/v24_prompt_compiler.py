"""
V24.2 PROMPT COMPILER — LTX-2.3 RESEARCH-ALIGNED + PIPELINE PROTECTED
======================================================================
BUILT ON RESEARCH: Kling 3.0 / LTX-2.3 capability analysis (March 2026)
FIXES ALL REGRESSIONS + PROTECTS AGAINST SERVER RE-ENRICHMENT

Key research findings applied:
  - Colon-separated zones > period-separated sentences for LTX-2.3
  - Focal length + aperture + film stock > camera brand tokens (ARRI, Cooke = unreliable)
  - Physical descriptions > emotional labels ("clenches jaw" not "angry")
  - Concrete nouns/verbs weighted more heavily than vague descriptors
  - 4-8 sentences, under 200 words optimal for LTX-2.3
  - Official LTX-2.3 negative prompts: worst quality, inconsistent motion, blurry, jittery
  - Multi-character: focus on PRIMARY character per shot (feature bleed risk)
  - Identity memory: LTX has NONE natively — I2V first-frame conditioning is the mechanism

Pipeline protection:
  - Sets _unified_builder_applied = True on every shot
  - Sets nano_prompt_final = compiled prompt (server fast-path key)
  - Server's generate-first-frames checks these and SKIPS all enrichment layers
  - Zero risk of downstream re-contamination

Source data (ONLY these — nothing else):
  - story_bible.json → beat actions, dialogue, atmosphere
  - cast_map.json → canonical character appearances
  - scene_manifest → location truth per scene
  - shot metadata → coverage_role, shot_type, lens, camera_style, state_in/out
"""

import json, re, sys
from typing import Dict, List, Optional

# ─────────────────────────────────────────────
# CONSTANTS — RESEARCH-ALIGNED
# ─────────────────────────────────────────────

# Color science: Research confirms "Kodak 2383" and film stock refs work on LTX-2.3
COLOR_SCIENCE = {
    "gothic_horror": "Kodak 2383 print look: desaturated cool tones, teal shadows, amber practicals, 35mm grain",
    "noir": "high contrast: deep blacks, silver halide texture, single-source hard light",
    "period_drama": "warm amber base: candlelight practicals, Rembrandt lighting, rich earth tones",
}

# Research: "texture-based positive prompts (grain, skin pores, fabric weave) improve output"
# Research: "named light sources outperform generic descriptors like 'dramatic lighting'"
QUALITY_ULTRA = (
    "photographic realism, 8K resolution, natural skin texture with pores and imperfections, "
    "volumetric atmospheric lighting, accurate shadow falloff, physically-based material rendering, "
    "cinematic depth of field with optical bokeh, real-world color response"
)

# Research: "LTX-2.3 base model has NO built-in identity memory"
# Identity is held by I2V first-frame conditioning — text is a REINFORCEMENT signal only
# Research: "concrete nouns and verbs weighted more heavily than vague descriptors"
IDENTITY_LOCK = (
    "preserve exact facial bone structure, eye color, skin tone, "
    "hair color and texture, jawline shape, nose bridge, ear shape. "
    "NO age drift, NO feature blending between characters"
)

# Research: "focal length specifications (24mm, 35mm, 50mm, 85mm) work reliably"
# Research: "aperture values (f/1.2, f/2.8) work reliably"
# Research: "camera body names (ARRI Alexa, RED) are NOT confirmed to produce distinct results"
FOCAL_MAP = {
    "14mm": "14mm ultra-wide, f/2.8, deep perspective, environmental dominance",
    "24mm": "24mm wide, f/2.0, spatial context, environmental storytelling",
    "35mm": "35mm, f/1.8, natural perspective, balanced framing",
    "50mm": "50mm, f/1.4, normal lens, natural perspective, shallow depth of field",
    "85mm": "85mm, f/1.2, compressed background, face isolation, heavy bokeh",
    "100mm": "100mm, f/2.0, telephoto, isolated subject, heavy bokeh",
    "135mm": "135mm, f/2.0, extreme close, voyeuristic compression",
}

# Research: "camera movement verbs (dolly push, crane drop, Steadicam glide) translate to distinct operations"
MOTION_MAP = {
    "static": "locked camera, zero movement",
    "slow_crane": "slow crane ascending, gradual reveal",
    "slow_push": "gentle dolly push in, imperceptible drift",
    "handheld": "organic handheld, subtle breathing movement",
    "tracking": "smooth tracking shot, following subject",
    "dolly": "dolly forward, controlled approach",
    "pan": "slow pan, lateral sweep",
    "steadicam": "steadicam glide, weightless movement",
}

COVERAGE_FRAMING = {
    "A_GEOGRAPHY": "wide establishing: full environment visible, characters small in frame",
    "B_ACTION": "medium shot: waist-up, action-readable",
    "C_EMOTION": "close-up: face fills frame, emotional detail, eyes sharp",
}

# Research: "LTX-2.3 official code includes default negative prompts"
LTX_NEGATIVE_PROMPT = (
    "worst quality, inconsistent motion, blurry, jittery, distorted, "
    "NO morphing, NO grid, NO collage, NO split screen, NO watermarks, NO text overlays"
)

# Rule 143: Human-body language patterns forbidden in environment/no-character shots
HUMAN_LANGUAGE_PATTERNS = re.compile(
    r'\b(?:lip|lips|jaw|gaze|gaz(?:ing|ed)|blink|blinks|blinking|'
    r'breathing|breath|exhale|inhale|chest\s+rise|micro[- ]?expression|'
    r'eyebrow|eyelid|nostril|cheek|forehead|chin|pupil|iris|'
    r'shoulder|arm|hand|finger|wrist|elbow|knee|ankle|'
    r'posture|gesture|slouch|lean|crouch|kneel|sit(?:s|ting)?|stand(?:s|ing)?|'
    r'whisper|murmur|nod|shake|shrug|frown|smile|smirk|grimace|'
    r'perform|speaks|reacts|listens|watches|stares)\b',
    re.IGNORECASE
)


def strip_human_language_from_delta(delta: str) -> str:
    """Strip human-body references from continuity delta for environment shots."""
    if not delta:
        return ""
    lines = delta.split('\n')
    clean_lines = []
    for line in lines:
        if any(kw in line.lower() for kw in [
            'character', 'person', 'figure', 'performer',
            'face', 'body', 'emotional', 'emotion_intensity',
            'gaze_direction', 'body_angle', 'posture',
            'screen_position', 'depth_plane',
        ]):
            continue
        cleaned = HUMAN_LANGUAGE_PATTERNS.sub('', line)
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        cleaned = re.sub(r',\s*,', ',', cleaned)
        cleaned = re.sub(r':\s*[,.]', ':', cleaned)
        cleaned = cleaned.strip(' ,.')
        if cleaned and len(cleaned) > 5:
            clean_lines.append(cleaned)
    result = '\n'.join(clean_lines).strip()
    return result if len(result) > 10 else ""


def get_beat_for_shot(shot_index: int, n_shots: int, beats: list, scene_data: dict,
                      shot: dict = None) -> dict:
    """
    PROPORTIONAL beat mapping — the ONLY correct method.
    Rule 80: beat_idx = int(shot_index * n_beats / n_shots)
    """
    if not beats:
        shot_desc = ''
        shot_dlg = None
        if shot:
            shot_desc = shot.get('description', '') or ''
            shot_dlg = shot.get('dialogue_text', '') or shot.get('dialogue', '') or None
        return {
            'description': shot_desc or scene_data.get('description', ''),
            'character_action': shot_desc,
            'dialogue': shot_dlg,
            'atmosphere': scene_data.get('atmosphere', ''),
        }
    n_beats = len(beats)
    beat_idx = int(shot_index * n_beats / n_shots)
    beat_idx = min(beat_idx, n_beats - 1)
    beat = dict(beats[beat_idx])
    if not beat.get('atmosphere'):
        beat['atmosphere'] = scene_data.get('atmosphere', '')
    return beat


def get_scene_location(scene_id: str, scene_manifest, story_bible: dict) -> str:
    """Get location from scene_manifest (truth) or story_bible (fallback)."""
    if isinstance(scene_manifest, list):
        for sm in scene_manifest:
            if isinstance(sm, dict) and sm.get('scene_id') == scene_id:
                loc = sm.get('location', '')
                tod = sm.get('time_of_day', '')
                if loc:
                    return f"{loc} - {tod}" if tod else loc
    elif isinstance(scene_manifest, dict):
        sm = scene_manifest.get(scene_id, {})
        if isinstance(sm, dict) and sm.get('location'):
            return sm['location']
    for s in story_bible.get('scenes', []):
        if s.get('scene_id') == scene_id:
            return s.get('location', '')
    return ''


def get_character_appearance(name: str, cast_map: dict) -> str:
    """Get CANONICAL appearance from cast_map — NEVER from AI actor library."""
    data = cast_map.get(name, {})
    if isinstance(data, dict):
        return data.get('appearance', '')
    return ''


def compile_nano_prompt(shot: dict, beat: dict, cast_map: dict,
                        scene_location: str, genre: str = "gothic_horror") -> str:
    """
    Build nano_prompt (text-to-image) from source data.

    Research: nano-banana-pro is text-to-image — gets full scene description.
    Uses colon-separated zones for structured parsing.
    Research: "more than 7 distinct elements creates confusion" — keep focused.

    NANO PROMPT = what the FIRST FRAME looks like (static image).

    Zone structure:
      Camera : Subject : Environment : Action : Quality : Constraints
    """
    zones = []

    # Zone 1: Camera (lens physics — research confirmed these work)
    lens = shot.get('lens_specs', '50mm')
    coverage = shot.get('coverage_role', '')
    cam_zone = FOCAL_MAP.get(lens, f"{lens} lens")
    if coverage in COVERAGE_FRAMING:
        cam_zone += ": " + COVERAGE_FRAMING[coverage]
    zones.append(cam_zone)

    # Zone 2: Environment (scene-level truth — prevents cross-contamination)
    atmosphere = beat.get('atmosphere', '')
    if scene_location:
        env_zone = scene_location
        if atmosphere:
            env_zone += f", {atmosphere}"
        zones.append(env_zone)

    # Zone 3: Subject — PRIMARY character only (research: "focus on one character
    # at a time" to avoid feature bleed on LTX-2.3)
    characters = shot.get('characters') or []
    if characters:
        # Primary character gets full appearance
        primary = characters[0]
        appearance = get_character_appearance(primary, cast_map)
        if appearance:
            zones.append(f"{primary}: {appearance}")
        # Secondary characters get name-only mention (reduces feature bleed risk)
        if len(characters) > 1:
            others = ", ".join(characters[1:])
            zones.append(f"also present: {others}")

    # Zone 4: Action — what happens (concrete verbs, imperative phrasing)
    # Research: "concrete nouns and verbs weighted more heavily than vague descriptors"
    action = beat.get('character_action', '') or beat.get('description', '')
    if action:
        zones.append(action)

    # Zone 5: Dialogue direction (if present)
    dialogue = shot.get('dialogue_text', '') or shot.get('dialogue', '')
    if not dialogue:
        dialogue = beat.get('dialogue', '') or ''
    if dialogue and characters:
        zones.append(f"{characters[0]} speaks: {dialogue[:120]}")

    # Zone 6: Quality + color science
    # Research: "texture-based positive prompts improve output"
    zones.append(QUALITY_ULTRA)
    zones.append(COLOR_SCIENCE.get(genre, COLOR_SCIENCE["gothic_horror"]))

    # Zone 7: Identity + constraints
    if characters:
        zones.append(IDENTITY_LOCK)

    # Negative zone (always last)
    if characters:
        zones.append("NO morphing, NO grid, NO identity drift, NO extra people")
    else:
        zones.append("NO morphing, NO face generation, NO human figures, environment only")

    # Join with ". " — nano-banana-pro is text-to-image, less sensitive to zone format
    return ". ".join(z.strip().rstrip('.') for z in zones if z and z.strip())


def compile_ltx_prompt(shot: dict, beat: dict, cast_map: dict,
                       continuity_delta: str = "",
                       scene_location: str = "",
                       genre: str = "gothic_horror") -> str:
    """
    Build ltx_motion_prompt (image-to-video) from source data.

    Research: LTX-2.3 works best with:
      - "4-8 descriptive sentences under 200 words"
      - "zone-separated clauses render more consistently"
      - "main action → movement/gestures → character appearance → environment → camera"
      - "imperative phrasing outperforms narrative language"
      - Physical descriptions required, not emotion labels
      - Official negatives: "worst quality, inconsistent motion, blurry, jittery, distorted"

    LTX PROMPT = how the VIDEO moves (from the first frame).
    The first frame already shows the scene — LTX needs MOTION direction.

    Zone structure (colon-separated for LTX parsing):
      Camera motion : Scene context : Action/performance : Timing : Constraints
    """
    parts = []
    characters = shot.get('characters') or []

    # 1. Camera motion + lens physics (research: "dolly push, crane drop = distinct operations")
    # Include focal length so server V22.3 camera embedding detects it and is a NO-OP
    style = shot.get('camera_style', 'static')
    lens = shot.get('lens_specs', '50mm')
    lens_num = re.search(r'(\d+)', str(lens))
    focal_tag = f"{lens_num.group(1)}mm" if lens_num else "50mm"
    parts.append(f"{MOTION_MAP.get(style, MOTION_MAP['static'])}: {focal_tag} lens")

    # 2. Scene context (gives LTX environmental grounding for the video)
    atmosphere = beat.get('atmosphere', '')
    if scene_location:
        if atmosphere:
            parts.append(f"{scene_location}: {atmosphere}")
        else:
            parts.append(scene_location)
    elif atmosphere:
        parts.append(atmosphere)

    # 3. Action/performance — PHYSICAL descriptions, not emotion labels
    # Research: "Avoid emotional labels like 'sad' without describing visual cues"
    # Research: "Use posture, gesture, and facial expression instead"
    action = beat.get('character_action', '') or beat.get('description', '')
    dialogue = shot.get('dialogue_text', '') or shot.get('dialogue', '') or beat.get('dialogue', '') or ''

    if characters and dialogue:
        # Dialogue shot — physical speech description
        speaker = characters[0]
        parts.append(f"{speaker} speaks: {dialogue[:100]}: lips moving naturally, jaw articulating words")
    elif characters and action:
        # Action shot — imperative physical description
        parts.append(f"{characters[0]} performs: {action}")
    elif characters:
        # Reaction shot — physical reaction description
        parts.append(f"{characters[0]} reacts: eyes shifting, slight head movement, listening intently")
    else:
        # Environment shot — Rule 143: strip human language from action text
        if action:
            clean_action = HUMAN_LANGUAGE_PATTERNS.sub('', action)
            clean_action = re.sub(r'\s{2,}', ' ', clean_action).strip(' ,.')
            if clean_action and len(clean_action) > 10:
                parts.append(f"environment: {clean_action}")
            else:
                parts.append("environment: atmospheric detail, ambient light shifts, subtle movement")
        else:
            parts.append("environment: atmospheric detail, ambient light shifts, subtle movement")
        # V.O. / narration — env shots CAN have dialogue (newscast, voiceover)
        if dialogue and not characters:
            parts.append(f"voiceover narration: {dialogue[:120]}")

    # 4. Physical state transitions (NOT emotion labels — physical descriptions)
    state_in = shot.get('state_in') or {}
    state_out = shot.get('state_out') or {}
    for char_name in characters[:1]:
        si = state_in.get(char_name, {})
        so = state_out.get(char_name, {})
        pose_in = si.get('pose', '')
        pose_out = so.get('pose', '')
        if pose_in and pose_out and pose_in != pose_out:
            parts.append(f"{char_name} physically transitions from {pose_in} to {pose_out}")

    # 5. Color science (research: film stock references work on LTX-2.3)
    parts.append(COLOR_SCIENCE.get(genre, COLOR_SCIENCE["gothic_horror"]))

    # 6. Face/identity constraints
    if characters:
        if dialogue:
            parts.append("face stable: same bone structure, skin tone, eye color throughout: natural speech movement")
        else:
            parts.append("face stable: same bone structure, skin tone, eye color throughout: NO morphing")
    else:
        parts.append("NO morphing: NO face generation: NO human figures: environment only")

    # 7. Timing + continuity
    parts.append("single continuous shot")

    # Build with colon-separated zones (research: "zone-separated clauses render more consistently")
    prompt = ": ".join(p.strip().rstrip(':').rstrip('.') for p in parts if p and p.strip())

    # Continuity delta (appended as structured block, not inline)
    if continuity_delta:
        if characters:
            prompt += "\n\n" + continuity_delta
        else:
            clean_delta = strip_human_language_from_delta(continuity_delta)
            if clean_delta:
                prompt += "\n\n" + clean_delta

    return prompt


def _build_continuity_delta(prev_state: dict, current_shot: dict) -> str:
    """
    Build continuity delta from previous shot state — self-contained, no external deps.
    Only called for character shots that chain (not B-roll/env).
    """
    parts = []
    prev_chars = prev_state.get('characters', [])
    curr_chars = current_shot.get('characters') or []
    prev_coverage = prev_state.get('coverage_role', '')
    curr_coverage = current_shot.get('coverage_role', '')
    prev_out = prev_state.get('state_out', {})

    shared = [c for c in curr_chars if c in prev_chars]
    if shared:
        for char in shared:
            char_state = prev_out.get(char, {})
            if isinstance(char_state, dict):
                pose = char_state.get('pose', '')
                emotion = char_state.get('emotion_intensity', '')
                if pose:
                    parts.append(f"CONTINUITY: {char} continues from {pose}")
                if emotion:
                    parts.append(f"emotional intensity: {emotion}")

    if prev_coverage and curr_coverage and prev_coverage != curr_coverage:
        parts.append(f"REFRAME: {prev_coverage} to {curr_coverage}")

    parts.append("DO NOT flip screen direction or axis line")
    parts.append("maintain spatial relationships from previous shot")

    if not parts:
        return ""
    return "CONTINUITY MEMORY:\n" + "\n".join(f"- {p}" for p in parts)


def compile_scene(scene_id: str, shots: list, story_bible: dict,
                  cast_map: dict, scene_manifest: dict = None,
                  genre: str = "gothic_horror") -> list:
    """Compile all shots in a scene from source data with continuity tracking."""

    scene_data = {}
    for s in story_bible.get('scenes', []):
        if s.get('scene_id') == scene_id:
            scene_data = s
            break

    beats = scene_data.get('beats', [])
    scene_location = get_scene_location(scene_id, scene_manifest or {}, story_bible)

    scene_shots = sorted(
        [s for s in shots if s.get('scene_id') == scene_id],
        key=lambda x: x.get('shot_id', '')
    )
    n_shots = len(scene_shots)

    prev_shot_state = None

    results = []
    for i, shot in enumerate(scene_shots):
        beat = get_beat_for_shot(i, n_shots, beats, scene_data, shot)
        characters = shot.get('characters') or []

        continuity_delta = ""
        if prev_shot_state and i > 0 and characters:
            shot_id = shot.get('shot_id', '')
            is_broll = bool(shot.get('_broll') or shot.get('_no_chain'))  # V26 DOCTRINE: suffixes are editorial, not runtime
            if not is_broll:
                continuity_delta = _build_continuity_delta(prev_shot_state, shot)

        nano = compile_nano_prompt(shot, beat, cast_map, scene_location, genre)
        ltx = compile_ltx_prompt(shot, beat, cast_map, continuity_delta, scene_location, genre)

        if characters:
            prev_shot_state = {
                'characters': characters,
                'coverage_role': shot.get('coverage_role', ''),
                'state_out': shot.get('state_out') or {},
                'shot_type': shot.get('shot_type', ''),
                'shot_id': shot.get('shot_id', ''),
            }

        results.append({
            'shot_id': shot['shot_id'],
            'nano_prompt': nano,
            'ltx_motion_prompt': ltx,
            'beat_index': int(i * len(beats) / n_shots) if beats else -1,
            'has_continuity_delta': bool(continuity_delta),
            'characters': shot.get('characters', []),
            'has_dialogue': bool(shot.get('dialogue_text') or shot.get('dialogue') or beat.get('dialogue')),
        })

    return results


def validate_compiled_prompt(shot_id: str, nano: str, ltx: str, characters: list) -> list:
    """
    Validate a single compiled prompt. Returns list of errors (empty = pass).
    """
    errors = []

    if len(nano) < 30:
        errors.append(f"{shot_id}: nano_prompt too short ({len(nano)} chars)")
    if len(ltx) < 20:
        errors.append(f"{shot_id}: ltx_prompt too short ({len(ltx)} chars)")
    if len(nano) > 3000:
        errors.append(f"{shot_id}: nano_prompt too long ({len(nano)} chars)")

    # Bio bleed — camera brands + AI actor names
    bio_pattern = re.compile(
        r'(?:Isabella\s+Moretti|Sophia\s+Chen|Marcus\s+Sterling|ARRI\s+Alexa|Cooke\s+S7|'
        r'Sony\s+Venice|Panavision|RED\s+DSMC|Kodak\s+Vision3|Fuji\s+Eterna|'
        r'anamorphic\s+lens\s+flare|subsurface\s+scattering)', re.IGNORECASE)
    if bio_pattern.search(nano):
        errors.append(f"{shot_id}: bio bleed in nano_prompt")
    if bio_pattern.search(ltx):
        errors.append(f"{shot_id}: bio bleed in ltx_prompt")

    # Old enrichment DNA
    old_dna = re.compile(r'(?:performance:|subtext:|composition:|cinematic_weight)', re.IGNORECASE)
    if old_dna.search(nano):
        errors.append(f"{shot_id}: old enrichment DNA in nano_prompt")
    if old_dna.search(ltx):
        errors.append(f"{shot_id}: old enrichment DNA in ltx_prompt")

    # Rule 142: character shots need marker
    if characters:
        if not any(m in ltx for m in ['performs:', 'speaks:', 'reacts']):
            errors.append(f"{shot_id}: Rule 142 — missing performs/speaks/reacts marker")

    # Rule 143: no human language in env shots
    if not characters:
        human_check = re.compile(r'\b(?:lip|lips|jaw|blink|breathing|micro[- ]?expression)\b', re.IGNORECASE)
        if human_check.search(ltx):
            errors.append(f"{shot_id}: Rule 143 — human language in env shot LTX")

    # Research: LTX prompts should be under ~200 words
    ltx_words = len(ltx.split())
    if ltx_words > 250:
        errors.append(f"{shot_id}: LTX prompt too verbose ({ltx_words} words, target <200)")

    return errors


def apply_to_shot_plan(project: str, scene_ids: list, genre: str = "gothic_horror"):
    """
    Apply fresh compiled prompts to shot_plan.json.

    CRITICAL: Sets _unified_builder_applied + nano_prompt_final on every shot.
    This triggers the server's FAST PATH — skipping ALL enrichment layers.
    Without these flags, the server re-runs the old 7-layer enrichment and
    overwrites V24 prompts with contaminated versions.
    """
    import shutil
    from datetime import datetime

    base = f"pipeline_outputs/{project}"
    sp_path = f"{base}/shot_plan.json"

    sp = json.load(open(sp_path))
    sb = json.load(open(f"{base}/story_bible.json"))
    cm = json.load(open(f"{base}/cast_map.json"))
    sm = sp.get('scene_manifest', {})
    shots = sp.get('shots', [])

    # Phase 1: Compile ALL prompts and validate BEFORE writing anything
    all_results = []
    all_errors = []
    for scene_id in scene_ids:
        results = compile_scene(scene_id, shots, sb, cm, sm, genre)
        for r in results:
            errs = validate_compiled_prompt(
                r['shot_id'], r['nano_prompt'], r['ltx_motion_prompt'], r['characters']
            )
            if errs:
                all_errors.extend(errs)
            all_results.append(r)

    if all_errors:
        error_msg = f"VALIDATION FAILED — {len(all_errors)} errors. ABORTING:\n"
        for e in all_errors:
            error_msg += f"  {e}\n"
        raise ValueError(error_msg)

    # Phase 2: All valid — backup then write WITH PIPELINE PROTECTION FLAGS
    backup = f"{sp_path}.backup_v24fresh_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(sp_path, backup)

    updated = 0
    before_count = len(shots)
    for r in all_results:
        shot = next((s for s in shots if s.get('shot_id') == r['shot_id']), None)
        if shot:
            shot['nano_prompt'] = r['nano_prompt']
            shot['ltx_motion_prompt'] = r['ltx_motion_prompt']

            # === PIPELINE PROTECTION FLAGS ===
            # These flags tell the server to SKIP all enrichment layers.
            # Without them, generate-first-frames re-runs:
            #   wardrobe → emotion → location → cinematic enricher →
            #   cast trait injection (AI actor library!) → face-lock → authority gate
            # which overwrites every V24 prompt with contaminated versions.
            shot['nano_prompt_final'] = r['nano_prompt']          # Server fast-path key
            shot['ltx_motion_prompt_final'] = r['ltx_motion_prompt']
            shot['_unified_builder_applied'] = True               # Server fast-path trigger
            shot['_v24_compiled'] = True
            shot['_v24_source'] = 'v24.2_research_aligned'

            # Also set negative_prompt for LTX (research: official LTX-2.3 negatives)
            shot['negative_prompt'] = LTX_NEGATIVE_PROMPT

            updated += 1

    after_count = len(shots)
    if before_count != after_count:
        raise ValueError(f"SHOT COUNT CHANGED: {before_count} → {after_count}. ABORTING.")

    with open(sp_path, 'w') as f:
        json.dump(sp, f, indent=2)

    print(f"✅ {updated}/{len(all_results)} prompts compiled, validated, and PIPELINE-PROTECTED")
    print(f"🛡️  _unified_builder_applied=True + nano_prompt_final set on all shots")
    print(f"🛡️  Server will SKIP enrichment layers (fast path active)")
    print(f"📦 Backup: {backup}")
    return updated, backup


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    scene_ids = sys.argv[2].split(',') if len(sys.argv) > 2 else ['001', '002']

    sys.path.insert(0, '.')
    base = f"pipeline_outputs/{project}"
    sp = json.load(open(f"{base}/shot_plan.json"))
    sb = json.load(open(f"{base}/story_bible.json"))
    cm = json.load(open(f"{base}/cast_map.json"))
    sm = sp.get('scene_manifest', {})

    for sid in scene_ids:
        results = compile_scene(sid, sp['shots'], sb, cm, sm)
        print(f"\nSCENE {sid}: {len(results)} shots")
        for r in results:
            chars = r['characters']
            dlg = "DIALOGUE" if r['has_dialogue'] else ""
            delta = "DELTA" if r['has_continuity_delta'] else ""
            print(f"  {r['shot_id']} beat={r['beat_index']} chars={len(chars)} {dlg} {delta}")
            print(f"    NANO: {r['nano_prompt'][:200]}...")
            print(f"    LTX:  {r['ltx_motion_prompt'][:200]}...")
