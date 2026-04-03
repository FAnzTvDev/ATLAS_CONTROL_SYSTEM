"""
v24_prompt_compiler.py — FIXED
==============================
Drop-in replacement for tools/v24_prompt_compiler.py

ROOT CAUSE of the transcript bug:
  Environment shot GUARD tokens ("locked camera, zero movement, NO human figures,
  environment only") were compiled into a shared _base_constraints block that
  got appended to ALL shots regardless of type. Result: every character shot
  looked like an environment shot.

FIX: Hard zone isolation. Each zone ONLY writes into its own string.
  Environment guards → ONLY written when shot has zero characters.
  Character/emotion language → ONLY written when shot has characters.
  NO shared constraint block that gets globally appended.

Higgsfield insight applied:
  Prompt compiler IS the moat. Not a gear selector. Not a brand injector.
  Every cinematic input (lens, move, emotion, light) translates to a
  specific text modifier that conditions the model. That translation
  IS the product.

Dual-model awareness:
  KLING: 50–100 words, @Element1 reference, dialogue with <<<voice_1>>>
  LTX:   70–120 words, image_url anchor, extend-chain compatible

Source hierarchy (read-only inputs — never old prompts):
  Level 1: story_bible beats
  Level 2: cast_map appearance entries  
  Level 3: scene_manifest location/atmosphere
  Level 4: shot metadata (type, chars, action, dialogue)
  Level 5: continuity memory (previous shot state — self-contained, no import)
"""

import json, os, re
from pathlib import Path
from typing  import Optional

# ─── CINEMATIC TOKEN LIBRARY ─────────────────────────────────────────────────
# Source of truth for cinematic language.
# These are the ONLY prompt modifiers the compiler is allowed to use.
# Never add hardware brands. Never add film stocks. Never add bio language.

LENS_TOKENS = {
    "WS":     "28mm wide perspective, full environment context, slight barrel",
    "MS":     "50mm natural perspective, eye-level intimacy",
    "MCU":    "85mm f/2.0 mild compression, face in environment",
    "CU":     "85mm f/1.4 shallow depth, subject isolation, background separation",
    "ECU":    "100mm f/1.4 extreme subject fill, razor depth plane",
    "OTS":    "50mm over-shoulder, spatial relationship between subjects",
    "POV":    "35mm handheld feel, first-person spatial authenticity",
    "INSERT": "100mm macro proximity, texture detail, object intimacy",
    "TWO":    "50mm two-shot, balanced framing, equal subject weight",
    "ESTAB":  "24mm anamorphic feel, grand establishing, location authority",
}

MOVE_TOKENS = {
    "static":    "locked-off, absolute stillness, composed frame",
    "dolly_in":  "slow forward dolly, focal compression, encroaching intimacy",
    "dolly_out": "retreating dolly, expanding context, subject diminished in space",
    "tracking":  "lateral track, parallel motion, subject held in frame",
    "handheld":  "organic handheld drift, subtle 2-pixel shake, documentary truth",
    "push_in":   "creeping push-in, dread accumulation, slow approach",
    "crane_up":  "ascending crane, ground to sky, revealing scale",
    "tilt_up":   "slow tilt upward, revealing height, vertical revelation",
}

EMOTION_TOKENS = {
    "dread":       "microexpression of controlled fear, jaw tight, pupils searching exits",
    "grief":       "suppressed grief at jaw line, breath shallow, eyes bright with held tears",
    "rage":        "stillness before eruption, lips pressed, contained fury behind calm",
    "wonder":      "pupils dilated, slight lip part, head tilts 5 degrees, breath held",
    "resolve":     "jaw set, eyes level, breath steady, hands still at sides",
    "deceit":      "carefully neutral expression masking calculation, brief tell at brow",
    "fear":        "dilated pupils, heightened breathing, hands close to body",
    "curiosity":   "head inclines, eyes narrow with focus, body leans forward 10 degrees",
    "suspicion":   "eyes narrow, jaw shifts, weight redistributes to back foot",
    "relief":      "exhale visible, shoulders drop, jaw unclenches",
    "shock":       "eyes widen, jaw drops fractionally, stillness before reaction",
    "determination":"eyes forward, breath controlled, jaw forward, body aligned",
}

LIGHT_TOKENS = {
    "candle":       "warm 2200K practical candles, guttering shadows, golden pool radius",
    "moonlight":    "cool 5500K through tall windows, silver edge rim, deep shadow wells",
    "fireplace":    "amber 2700K flicker, dynamic shadow dance on walls, near-warmth",
    "overcast":     "diffused 4300K exterior, flat even fill, no hard shadow, grey weight",
    "storm_flash":  "strobed 6500K burst through storm, shadow-recovery frames, disoriented light",
    "magic_hour":   "golden 3000K oblique rake, 30-degree side angle, extended warm shadows",
    "daylight_int": "natural 5600K window light, soft fill from bounce, motivated direction",
    "practical_lamp":"warm 2800K bedside/desk practical, tight pool, deep room fall-off",
}

# Project color anchor — every shot, every model, no exception
RAVENCROFT_GRADE = (
    "desaturated cool tones, teal in deep shadows, warm amber in practical sources, "
    "Kodak 2383 print look, 35mm grain, controlled vignette"
)

# ─── SHOT CLASSIFIER ─────────────────────────────────────────────────────────

def classify_shot(shot: dict) -> dict:
    """
    Classify shot into routing and zone flags.
    Returns classification dict — no side effects.
    """
    chars      = shot.get("characters", []) or shot.get("cast", []) or []
    shot_type  = shot.get("shot_type","MS").upper().replace("-","_").replace("/","_")
    has_dlg    = bool(shot.get("dialogue") or shot.get("speaks"))
    is_env     = len(chars) == 0
    is_cu      = shot_type in ("CU","ECU","MCU")
    is_insert  = shot_type == "INSERT"

    # Model routing — no LoRAs yet, NB frame IS the identity anchor for LTX
    if is_env or is_insert:
        model, mode = "LTX", "atmosphere"
    elif is_cu or has_dlg:
        model, mode = "KLING", "identity"
    else:
        model, mode = "LTX", "i2v"

    return {
        "chars":     chars,
        "shot_type": shot_type,
        "has_dlg":   has_dlg,
        "is_env":    is_env,
        "is_insert": is_insert,
        "model":     model,
        "mode":      mode,
    }


# ─── ZONE COMPILERS ──────────────────────────────────────────────────────────
# Each function writes ONLY its own zone.
# They do NOT read from other zones.
# They do NOT conditionally append environment guards if has_chars is True.

def zone_subject(shot: dict, beat: dict, cl: dict) -> str:
    """Z1: WHO does WHAT in WHERE. Character shots only."""
    if cl["is_env"]:
        return ""  # environment shots get no subject zone — see zone_environment

    chars   = cl["chars"]
    action  = (beat.get("character_action") or shot.get("action") or
               shot.get("description", "")).strip()
    loc     = (shot.get("location") or shot.get("set", "")).strip()

    subject = chars[0] if chars else "UNKNOWN"
    if len(chars) == 2:
        subject = f"{chars[0]} and {chars[1]}"

    parts = [f"{subject} — {action}"] if action else [subject]
    if loc:
        parts.append(f"in {loc}")

    return ". ".join(parts)


def zone_environment(shot: dict, beat: dict, scene_manifest: dict, cl: dict) -> str:
    """Z2-ENV: For atmosphere/B-roll shots ONLY. Never runs on character shots."""
    if not cl["is_env"] and not cl["is_insert"]:
        return ""  # ← THIS is the fix. Guard tokens never reach character shots.

    loc       = (shot.get("location") or scene_manifest.get("location","the location")).strip()
    atmosphere = (beat.get("atmosphere") or scene_manifest.get("atmosphere","")).strip()
    action    = (shot.get("action") or beat.get("atmosphere_action","")).strip()

    parts = [loc]
    if atmosphere: parts.append(atmosphere)
    if action:     parts.append(action)
    parts.append("environment and atmosphere, no human figures")

    return ". ".join(parts)


def zone_lens(shot: dict, cl: dict) -> str:
    """Z3: Lens character from shot type. No brand names ever."""
    return LENS_TOKENS.get(cl["shot_type"], LENS_TOKENS["MS"])


def zone_motion(shot: dict) -> str:
    """Z4: Camera movement. Defaults to static if not specified."""
    move = shot.get("camera_move", shot.get("movement", "static")).lower().replace(" ","_")
    return MOVE_TOKENS.get(move, MOVE_TOKENS["static"])


def zone_performance(shot: dict, beat: dict, cl: dict) -> str:
    """Z5: Emotion + performance direction. Character shots only."""
    if cl["is_env"]:
        return ""

    emotion = (shot.get("emotion") or shot.get("emotion_choice") or
               beat.get("emotion") or "").lower()
    token   = EMOTION_TOKENS.get(emotion, "")

    dialogue = (shot.get("dialogue") or shot.get("speaks") or
                beat.get("dialogue","")).strip()
    dlg_part = f'speaks: "{dialogue}"' if dialogue and cl["has_dlg"] else ""

    parts = [p for p in [token, dlg_part] if p]
    return ". ".join(parts)


def zone_light(shot: dict, beat: dict) -> str:
    """Z6: Lighting. One source, one quality."""
    light = (shot.get("light") or shot.get("lighting") or
             beat.get("lighting","candle")).lower().replace(" ","_")
    return LIGHT_TOKENS.get(light, LIGHT_TOKENS["candle"])


def zone_grade() -> str:
    """Z7: Project color anchor. Always appended. Never varies."""
    return RAVENCROFT_GRADE


def zone_quality(cl: dict) -> str:
    """Z8: Photorealism + identity lock. Varies by shot type."""
    if cl["is_env"]:
        # Environment: NO face generation language
        return (
            "photorealistic render, no CGI artifacts, "
            "physically-based lighting, atmospheric depth, film grain present"
        )
    else:
        # Character: identity lock language
        chars = cl["chars"]
        char_str = " and ".join(chars) if chars else "subject"
        return (
            f"photorealistic, STRICT IDENTITY LOCK on {char_str}: "
            "preserve exact facial bone structure, eye color, skin tone, "
            "hair color and style, jawline, nose shape throughout. "
            "face stable, identity held, no morphing, film grain present"
        )


# ─── CONTINUITY DELTA (self-contained, no external import) ───────────────────

def build_continuity_delta(previous_shot: Optional[dict], current_shot: dict, cl: dict) -> str:
    """
    Generate continuity memory delta.
    Rules:
    - First shot in scene: no delta (it IS the anchor)
    - Environment shots: no delta (they don't chain)
    - Character shots only: spatial position + screen direction
    """
    if cl["is_env"] or not previous_shot:
        return ""

    prev_chars = previous_shot.get("characters", [])
    curr_chars = cl["chars"]

    # Don't inject continuity if characters changed
    if set(prev_chars) != set(curr_chars):
        return ""

    prev_state_out = previous_shot.get("state_out", {})
    if not prev_state_out:
        return ""

    position = prev_state_out.get("position", "")
    screen_dir = prev_state_out.get("screen_direction", "")

    parts = ["Previous shot establishes:"]
    if position:  parts.append(position)
    if screen_dir: parts.append(f"screen direction {screen_dir}")

    return " ".join(parts) if len(parts) > 1 else ""


# ─── MASTER COMPILER ─────────────────────────────────────────────────────────

def compile_shot(
    shot:          dict,
    beat:          dict,
    scene_manifest:dict,
    previous_shot: Optional[dict] = None,
    canonical_chars: dict         = None,
) -> dict:
    """
    Compile a single shot to final prompt.
    
    Returns:
        {
            "nano_prompt":       str,   # Kling-ready (50–100w)
            "ltx_motion_prompt": str,   # LTX-ready (70–120w)
            "model":             str,   # "KLING" | "LTX"
            "mode":              str,   # "identity" | "i2v" | "atmosphere"
            "word_count":        int,
            "validation":        dict,
        }
    
    NEVER reads from shot["nano_prompt"] or shot["ltx_motion_prompt"].
    Those fields are outputs, not inputs.
    """
    cl = classify_shot(shot)
    if canonical_chars is None:
        canonical_chars = {}

    # ── Build all zones ────────────────────────────────────────────────────────
    # Each zone writes only to its own variable.
    # No zone reads from another zone.

    z_subject     = zone_subject(shot, beat, cl)
    z_environment = zone_environment(shot, beat, scene_manifest, cl)
    z_lens        = zone_lens(shot, cl)
    z_motion      = zone_motion(shot)
    z_performance = zone_performance(shot, beat, cl)
    z_light       = zone_light(shot, beat)
    z_grade       = zone_grade()
    z_quality     = zone_quality(cl)
    z_continuity  = build_continuity_delta(previous_shot, shot, cl)

    # ── Assemble — character vs environment NEVER share zones ─────────────────
    if cl["is_env"]:
        # Environment shot assembly
        # ONLY: environment + lens + motion + light + grade + quality
        # NEVER: subject, performance, emotion, identity lock, continuity
        zones = [z_environment, z_lens, z_motion, z_light, z_grade, z_quality]
    else:
        # Character shot assembly
        # ONLY: subject + lens + motion + performance + light + grade + quality + continuity
        # NEVER: environment guard language (NO human figures etc)
        zones = [z_subject, z_lens, z_motion, z_performance, z_light, z_grade, z_quality]
        if z_continuity:
            zones.append(z_continuity)

    # Filter empty zones, join
    prompt = ". ".join(z for z in zones if z.strip())

    # ── Model-specific formatting ──────────────────────────────────────────────
    if cl["model"] == "KLING":
        # Kling: 50–100 words, @Element1 reference prepended
        char = cl["chars"][0] if cl["chars"] else None
        char_canon = canonical_chars.get(char, {})
        element_ref = "@Element1 — " if char_canon.get("frontal_image_url") else ""
        nano_prompt = element_ref + prompt
        ltx_prompt  = prompt  # fallback if Kling fails
    else:
        # LTX: 70–120 words, extend-chain compatible
        nano_prompt = prompt  # Kling fallback
        ltx_prompt  = prompt

    # ── Validate ───────────────────────────────────────────────────────────────
    validation = validate_prompt(prompt, shot, cl)

    word_count = len(prompt.split())

    return {
        "nano_prompt":       nano_prompt,
        "ltx_motion_prompt": ltx_prompt,
        "model":             cl["model"],
        "mode":              cl["mode"],
        "word_count":        word_count,
        "validation":        validation,
        "_zones_debug": {       # debug only — not written to shot_plan
            "subject":     z_subject,
            "environment": z_environment,
            "lens":        z_lens,
            "motion":      z_motion,
            "performance": z_performance,
            "light":       z_light,
            "continuity":  z_continuity,
        }
    }


# ─── VALIDATION ──────────────────────────────────────────────────────────────

def validate_prompt(prompt: str, shot: dict, cl: dict) -> dict:
    """
    Hard validation. Returns errors dict.
    If any HARD error exists, do NOT write prompt to shot_plan.
    """
    errors   = {}
    warnings = {}
    prompt_l = prompt.lower()

    # HARD: environment guard in character shot
    if not cl["is_env"]:
        env_contaminants = [
            "no human figures", "environment only", "no face generation",
            "no morphing, no face", "zero movement"  # only bad if from env guard
        ]
        for c in env_contaminants:
            if c in prompt_l:
                errors[f"env_guard_bleed_{c[:20]}"] = (
                    f"Environment guard token '{c}' found in character shot — zone bleed"
                )

    # HARD: camera hardware brands
    brands = ["arri", "red dsmc", "sony venice", "panavision", "cooke", "zeiss leica",
              "kodak vision3", "fuji eterna", "35mm film stock"]
    for b in brands:
        if b in prompt_l:
            errors[f"brand_{b[:10]}"] = f"Hardware brand '{b}' must not appear in compiled prompt"

    # HARD: bio bleed (AI actor library contamination)
    bio_markers = ["italian", "nigerian", "mixed heritage", "ai actor", "fal actor"]
    for m in bio_markers:
        if m in prompt_l:
            errors[f"bio_{m}"] = f"Bio contamination: '{m}'"

    # HARD: empty prompt
    if len(prompt.strip()) < 20:
        errors["empty"] = "Prompt is too short — likely empty compile"

    # HARD: no scene-specific content
    if not cl["is_env"] and not any([
        shot.get("action"), shot.get("description"),
        shot.get("dialogue"), shot.get("location")
    ]):
        errors["no_scene_content"] = "No scene-specific content — prompt is generic boilerplate only"

    # WARN: word count
    if cl["model"] == "KLING":
        w = len(prompt.split())
        if w < 50: warnings["word_count_low"]  = f"{w}w below 50w Kling target"
        if w > 100: warnings["word_count_high"] = f"{w}w above 100w Kling target"
    else:
        w = len(prompt.split())
        if w < 70: warnings["word_count_low"]  = f"{w}w below 70w LTX target"
        if w > 120: warnings["word_count_high"] = f"{w}w above 120w LTX target"

    return {"errors": errors, "warnings": warnings, "passed": len(errors) == 0}


# ─── SCENE COMPILER ───────────────────────────────────────────────────────────

def compile_scene(
    scene_shots:    list[dict],
    story_beats:    list[dict],
    scene_manifest: dict,
    canonical_chars:dict = None,
) -> list[dict]:
    """
    Compile an entire scene. Proportional beat mapping. Continuity chain.
    
    Returns list of compiled results — does NOT write to shot_plan yet.
    Call apply_compiled() to write.
    """
    if canonical_chars is None:
        canonical_chars = {}

    n_shots = len(scene_shots)
    n_beats = len(story_beats)
    results = []
    prev    = None

    for i, shot in enumerate(scene_shots):
        # Proportional beat mapping — correct formula from CLAUDE.md rule 80
        beat_idx = int(i * n_beats / n_shots)
        beat_idx = min(beat_idx, n_beats - 1)
        beat     = story_beats[beat_idx] if story_beats else {}

        result = compile_shot(shot, beat, scene_manifest, prev, canonical_chars)

        # Only chain continuity for character shots
        if not classify_shot(shot)["is_env"]:
            prev = shot

        results.append({**result, "_shot_id": shot.get("shot_id", f"shot_{i:03d}")})

    return results


# ─── APPLY TO SHOT PLAN ───────────────────────────────────────────────────────

def apply_to_shot_plan(
    project_name:   str,
    scene_ids:      list[str],
    projects_dir:   str  = "/Users/quantum/atlas_automation",
    dry_run:        bool = False,
) -> dict:
    """
    Compile and write prompts to shot_plan.json.
    
    HARD RULE: validates ALL prompts BEFORE writing ANY.
    If any prompt fails validation, ZERO prompts are written.
    Returns summary dict.
    """
    plan_path = Path(projects_dir) / "projects" / project_name / "shot_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"shot_plan.json not found: {plan_path}")

    with open(plan_path) as f:
        plan = json.load(f)

    shots_list = plan.get("shots", plan)
    if isinstance(shots_list, dict):
        shots_list = list(shots_list.values())

    # Load supporting data
    bible_path = Path(projects_dir) / "projects" / project_name / "story_bible.json"
    story_bible = json.load(open(bible_path)) if bible_path.exists() else {}

    canon_path = Path(projects_dir) / "projects" / project_name / "canonical_characters.json"
    canonical_chars = json.load(open(canon_path)) if canon_path.exists() else {}

    # ── Phase 1: Compile all — collect results WITHOUT writing ────────────────
    all_compiled   = []
    all_errors     = []

    for scene_id in scene_ids:
        scene_shots = [s for s in shots_list if str(s.get("scene_id","")) == str(scene_id)]
        if not scene_shots:
            print(f"  ⚠ Scene {scene_id}: no shots found")
            continue

        beats    = story_bible.get("scenes", {}).get(scene_id, {}).get("beats", [])
        manifest = story_bible.get("scenes", {}).get(scene_id, {}).get("manifest", {})

        compiled = compile_scene(scene_shots, beats, manifest, canonical_chars)

        for r in compiled:
            if not r["validation"]["passed"]:
                all_errors.append({
                    "shot_id": r["_shot_id"],
                    "errors":  r["validation"]["errors"],
                })
            all_compiled.append(r)

    # ── Phase 2: Fail HARD if any errors ──────────────────────────────────────
    if all_errors:
        print(f"\n❌ COMPILE FAILED — {len(all_errors)} shots failed validation")
        print("   ZERO prompts written to shot_plan.json")
        for e in all_errors:
            print(f"   {e['shot_id']}: {list(e['errors'].values())}")
        return {"success": False, "errors": all_errors, "written": 0}

    if dry_run:
        print(f"\n✓ DRY RUN: {len(all_compiled)} shots would be written")
        for r in all_compiled[:3]:
            print(f"\n  [{r['_shot_id']}] {r['model']} {r['mode']} {r['word_count']}w")
            print(f"  {r['nano_prompt'][:120]}...")
        return {"success": True, "compiled": len(all_compiled), "written": 0, "dry_run": True}

    # ── Phase 3: Write all ─────────────────────────────────────────────────────
    compiled_by_id = {r["_shot_id"]: r for r in all_compiled}

    shot_index = {s.get("shot_id"): i for i, s in enumerate(shots_list)}
    for r in all_compiled:
        sid = r["_shot_id"]
        if sid in shot_index:
            i = shot_index[sid]
            # Write ONLY the final fields — no v24 shadow fields, no _pre_v24 backups
            shots_list[i]["nano_prompt"]       = r["nano_prompt"]
            shots_list[i]["ltx_motion_prompt"] = r["ltx_motion_prompt"]
            shots_list[i]["routed_model"]      = r["model"]
            shots_list[i]["routing_mode"]      = r["mode"]
            # Remove any contamination fields from old runs
            for old_key in ["nano_prompt_pre_v24","nano_prompt_v24","ltx_prompt_v24",
                            "nano_prompt_lite","ltx_prompt_lite"]:
                shots_list[i].pop(old_key, None)

    # Write back
    if isinstance(plan, dict) and "shots" in plan:
        plan["shots"] = shots_list
        out = plan
    else:
        out = shots_list

    with open(plan_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n✓ {len(all_compiled)} shots written to {plan_path}")
    print(f"  Models: {sum(1 for r in all_compiled if r['model']=='KLING')} Kling, "
          f"{sum(1 for r in all_compiled if r['model']=='LTX')} LTX")
    warnings_total = sum(len(r['validation']['warnings']) for r in all_compiled)
    if warnings_total:
        print(f"  ⚠ {warnings_total} warnings (non-blocking)")

    return {
        "success": True,
        "written": len(all_compiled),
        "kling":   sum(1 for r in all_compiled if r["model"]=="KLING"),
        "ltx":     sum(1 for r in all_compiled if r["model"]=="LTX"),
    }


# ─── CLI TEST ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test the zone isolation fix directly
    from pprint import pprint

    # Simulate a character CU shot
    char_shot = {
        "shot_id":   "S03_05",
        "shot_type": "CU",
        "characters":["Eleanor"],
        "location":  "INT - Drawing Room",
        "action":    "Eleanor reads the letter, hands trembling",
        "emotion":   "dread",
        "light":     "candle",
    }
    env_shot = {
        "shot_id":   "S03_07",
        "shot_type": "WS",
        "characters":[],
        "location":  "INT - Drawing Room",
        "action":    "Room falls silent, candle gutters",
        "light":     "candle",
    }
    beat = {"character_action":"reads letter","atmosphere":"tense silence","emotion":"dread"}
    manifest = {"location":"INT - Drawing Room","atmosphere":"heavy Victorian dread"}

    print("=== CHARACTER SHOT ===")
    r = compile_shot(char_shot, beat, manifest)
    print(f"Model: {r['model']} | Mode: {r['mode']} | Words: {r['word_count']}")
    print(f"Prompt: {r['nano_prompt']}")
    print(f"Valid: {r['validation']['passed']} | Errors: {r['validation']['errors']}")

    print("\n=== ENVIRONMENT SHOT ===")
    r2 = compile_shot(env_shot, beat, manifest)
    print(f"Model: {r2['model']} | Mode: {r2['mode']} | Words: {r2['word_count']}")
    print(f"Prompt: {r2['ltx_motion_prompt']}")
    print(f"Valid: {r2['validation']['passed']} | Errors: {r2['validation']['errors']}")

    # Confirm NO cross-contamination
    char_prompt = r["nano_prompt"].lower()
    env_prompt  = r2["ltx_motion_prompt"].lower()
    assert "no human figures" not in char_prompt, "BUG: env guard in character shot"
    assert "environment only" not in char_prompt, "BUG: env guard in character shot"
    assert "identity lock"    not in env_prompt,  "BUG: identity lock in environment shot"
    print("\n✓ Zone isolation verified — no cross-contamination")
