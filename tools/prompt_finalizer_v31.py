#!/usr/bin/env python3
"""
ATLAS Prompt Finalizer V31.0
Adds soundscape/voice signatures and upgrades all nano_prompts with full V31.0 consciousness.
"""

import json
import sys
import os
from pathlib import Path

SHOT_PLAN_PATH = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/shot_plan.json")

# ─── SOUNDSCAPE SIGNATURES (MUSICAL/TONAL DIRECTION — NOT AMBIENT SFX) ──────
# These are scene-level TONAL SIGNATURES for music composition.
# They define the emotional arc, tension level, and harmonic mood that MUST
# persist across all shots in the scene — because once you cut to the next shot,
# ambient sounds change but the musical tone must remain consistent.
# Think: "what note is this scene playing?" — not "what do we hear?"

SOUNDSCAPE_MAP = {
    # Scene 001 — GRAND FOYER: Professional intrusion meets grief
    "GRAND FOYER":     "low sustained string tension, minor key, slow tempo — professional coldness meeting unresolved grief. Rising dread under the surface. No resolution.",
    # Scene 002 — LIBRARY: Solitary discovery
    "LIBRARY":         "sparse piano motif, warm then cold — wonder curdling into tension as the letter is found. Quiet urgency. One instrument. No safety.",
    # Scene 003 — DRAWING ROOM: Threat made explicit
    "DRAWING ROOM":    "staccato low brass, compressed harmonic tension — intimidation rhythm. No melody. Threat made visible in tempo. Cut short.",
    # Scene 004 — GARDEN: Quiet confession / breathing space
    "GARDEN":          "open string intervals, grey and unresolved — space between notes as important as the notes. Grief breathing freely for the first time.",
    # Scene 005 — MASTER BEDROOM: Private revelation
    "MASTER BEDROOM":  "solo cello, deliberate and mournful — thirty years of secret carried in a single melodic line. Tempo like a heartbeat resisting belief.",
    # Scene 006 — KITCHEN: Working-class warmth / conspiracy
    "KITCHEN":         "low warmth, major undertone — the only major key in the estate. Brief. Conspiratorial whisper under a warm hum. Trust forming.",
    # Scene 007 — MASTER BEDROOM 2: Truth confronted
    "MASTER BEDROOM":  "returning cello motif, now fractured — the secret pulled into the open. Same theme, broken. Rising.",
    # Scene 008 — GRAND STAIRCASE: Rising stakes
    "GRAND STAIRCASE": "escalating string ostinato — the architecture itself as tension. Upward motion in the score mirrors upward movement. Tempo accelerating.",
    # Scene 009 — FRONT DRIVE: Escape attempt / confrontation
    "FRONT DRIVE":     "brass punctuation over sustained string bed — imminent threat, time running out. Harmonic collision of two forces at the door.",
    # Scene 010 — DRAWING ROOM 2: Alliance formed
    "DRAWING ROOM":    "returning theme now shared between two instruments — Eleanor and Nadia's motifs align for the first time. Resolution approaching.",
    # Scene 011 — LIBRARY 2: The journal read aloud
    "LIBRARY":         "Harriet's theme introduced — fragile, period-specific, harpsichord colour. Her voice in the music. Past reaching through into present.",
    # Scene 012 — GRAND FOYER 2: Climax and reckoning
    "GRAND FOYER":     "full orchestral tension, all motifs colliding — sustained dissonance then release. The house holds its breath. One final note.",
    # Scene 013 — EXTERIOR WIDE: Final image
    "EXTERIOR WIDE":   "single sustained string note fading to silence — the estate after truth. No resolution chord. Open ended. The house remains.",
}

def get_soundscape(location: str) -> str:
    loc_upper = location.upper()
    for key, sig in SOUNDSCAPE_MAP.items():
        if key in loc_upper:
            return sig
    return "sustained tonal ambiguity, minor key, no resolution — the estate's fundamental harmonic state"

# ─── VOICE SIGNATURES ────────────────────────────────────────────────────────

VOICE_SIGNATURES = {
    "ELEANOR VOSS":    "measured alto, clipped Victorian legal cadence, controlled emotion underneath",
    "THOMAS BLACKWOOD":"deep baritone, slow deliberate pacing, aristocratic warmth edged with grief",
    "NADIA COLE":      "bright mezzo-soprano, quick speech pattern, nervous curiosity beneath composure",
    "RAYMOND CROSS":   "smooth baritone, controlled menace, silk-over-steel delivery",
    "HARRIET HARGROVE":"(portrait only — no voice)",
}

def get_voice_signature(speaker: str) -> str:
    for name, sig in VOICE_SIGNATURES.items():
        if name in (speaker or "").upper():
            return sig
    return ""

# ─── ROOM DNA TEMPLATES ──────────────────────────────────────────────────────

ROOM_DNA = {
    "GRAND FOYER": (
        "Victorian grand foyer, double-height ceiling with ornate plasterwork crown molding. "
        "Single curved cream marble staircase with white carved balustrades, brass handrail, rising center-background. "
        "Dark mahogany wood-paneled walls with wainscoting. Persian carpet runner over dark marble floor. "
        "Crystal chandelier (unlit) overhead. Tall arched stained-glass windows frame-left admitting colored morning light. "
        "White dust-sheeted furniture. Oil portrait of stern Victorian woman above staircase landing."
    ),
    "LIBRARY": (
        "Victorian private library, floor-to-ceiling mahogany bookshelves packed with leather-bound volumes on all four walls. "
        "Rolling brass library ladder on upper rail. Central reading table of dark mahogany. "
        "Two leather wingback chairs angled toward fireplace. Tall arched windows admitting warm amber lamplight. "
        "Standing globe beside reading table. Dust on every horizontal surface. "
        "Warm lamp glow pooling on leather spines. Deep shadows in alcoves."
    ),
    "DRAWING ROOM": (
        "Victorian drawing room, ghostly white dust-sheeted furniture creating sculptural shapes. "
        "Grand Steinway piano frame-left under fitted sheet. Silver candelabras on mantelpiece. "
        "Crystal display cases along far wall. Marble fireplace surround, cold ash. "
        "Sage green wallpaper visible above the dust sheets. Dim grey light from curtained windows. "
        "Tarnished silver frames on the walls. A room preserved in amber, waiting."
    ),
    "GARDEN": (
        "Overgrown Victorian kitchen garden, dead roses on rusted iron trellises. "
        "Dry cracked stone fountain, basin empty. Weathered teak bench. "
        "Grey cloudy sky above rolling Yorkshire countryside. "
        "Gravel paths overtaken by moss and grass. Stone estate wall beyond. "
        "Copper beeches in the distance."
    ),
    "MASTER BEDROOM": (
        "Victorian master bedroom, burgundy silk wallpaper faded at seams. "
        "Carved mahogany four-poster bed with dusty canopy. "
        "Marble-topped washstand with porcelain basin. "
        "Vanity table with tarnished mirror, scattered silver toiletry set. "
        "Persian rug, deep colors muted under dust. "
        "Heavy velvet curtains half-drawn over tall windows. Morning light through the gap."
    ),
    "KITCHEN": (
        "Victorian estate kitchen, whitewashed brick walls, low-beamed ceiling with hanging copper pots. "
        "Flagstone floor, worn smooth at the range and sink. "
        "Cast-iron range, still faintly warm. Pine work table, scarred from decades of use. "
        "Stone sink, cold tap. Bundles of dried herbs hanging above. "
        "Warm orange light from range firebox, practical lantern overhead. "
        "The only working room in the estate."
    ),
    "GRAND STAIRCASE": (
        "Victorian grand staircase hall, domed skylight admitting cold grey light from above. "
        "Single curved marble staircase rising in a graceful sweep, brass rod carpet fasteners. "
        "Oil portraits of Hargrove ancestors in heavy gilt frames lining the walls. "
        "Crystal chandelier suspended from dome, unlit. "
        "Dark mahogany balustrade with carved newel post. "
        "The house's spine — everything flows through here."
    ),
    "FRONT DRIVE": (
        "Hargrove Estate front drive, Victorian limestone facade, ivy-covered wings. "
        "Gravel forecourt, raked but overgrown at edges. "
        "Iron gates at drive entrance, rusted but standing. "
        "Lead-paned windows reflecting grey sky. "
        "Copper beeches lining the carriage drive. Morning mist on the lawns."
    ),
    "EXTERIOR WIDE": (
        "Hargrove Estate exterior, grey limestone Victorian mansion. "
        "Ivy and wisteria claiming the east wing. "
        "Rolling grounds beyond iron perimeter fence. "
        "Morning mist on the lawns. Grey-blue Yorkshire sky."
    ),
}

def get_room_dna(location: str) -> str:
    loc_upper = location.upper()
    for key, dna in ROOM_DNA.items():
        if key in loc_upper:
            return dna
    return "Victorian estate interior, period architecture, practical lighting, dust and atmosphere."

# ─── CHARACTER AMPLIFICATION ─────────────────────────────────────────────────

CHARACTER_DESCRIPTIONS = {
    "ELEANOR VOSS": (
        "ELEANOR VOSS — woman in her mid-30s, sharp angular features, AUBURN hair pulled back in severe bun, "
        "piercing grey-green eyes, pale complexion, tailored CHARCOAL BLAZER over black turtleneck, dark trousers. "
        "Controlled, upright posture. Carries a leather briefcase."
    ),
    "THOMAS BLACKWOOD": (
        "THOMAS BLACKWOOD — man in his early 60s, BRIGHT SILVER-WHITE hair, deep weathered lines on face, "
        "dark weary eyes, RUMPLED NAVY SUIT, white shirt open at collar, no tie. "
        "Slightly stooped, as if carrying invisible weight."
    ),
    "NADIA COLE": (
        "NADIA COLE — young woman, 28, DARK BROWN skin, intelligent brown eyes, NATURAL TEXTURED AFRO hair, "
        "JEANS, VINTAGE IRON MAIDEN band t-shirt under OPEN FLANNEL SHIRT, professional camera hanging at chest."
    ),
    "RAYMOND CROSS": (
        "RAYMOND CROSS — STOCKY man, 45, THINNING DARK HAIR, sharp suspicious eyes, "
        "EXPENSIVE BLACK OVERCOAT over BURGUNDY SILK SHIRT, dark trousers, polished shoes. "
        "Moves through the estate as if he already owns it."
    ),
}

def get_char_desc(name: str) -> str:
    for key, desc in CHARACTER_DESCRIPTIONS.items():
        if key in name.upper():
            return desc
    return ""

# ─── FOCAL LENGTH ENFORCEMENT ─────────────────────────────────────────────────

FOCAL_FRAMING = {
    "establishing":  "[FRAMING: full room geography visible, deep depth of field, all architectural features sharp, wide establishing view]",
    "insert":        "[FRAMING: extreme close detail, lens compressed flat, object fills 60% of frame, background abstracted]",
    "medium":        "[FRAMING: waist-up figures, room context visible in background, mid-range depth of field]",
    "medium_close":  "[FRAMING: head and shoulders fill frame, background soft with vague shapes, 85mm f/2.0 compression]",
    "close_up":      "[FRAMING: face fills 80% of frame, background compressed flat and completely blurred, 85mm f/1.4 bokeh]",
    "two_shot":      "[FRAMING: both figures visible waist-up, confrontational composition, room context secondary]",
    "ots_a":         "[FRAMING: OTS A-angle — listener shoulder FRAME-LEFT foreground out of focus, SPEAKER FRAME-RIGHT facing camera]",
    "ots_b":         "[FRAMING: OTS B-angle — listener shoulder FRAME-RIGHT foreground out of focus, SPEAKER FRAME-LEFT facing camera]",
    "closing":       "[FRAMING: wide master, figures dwarfed by architecture, full room geography, deep field]",
    "reaction":      "[FRAMING: close reaction shot, 85mm f/1.4, face fills frame, pure bokeh background]",
}

def get_focal_framing(shot_type: str) -> str:
    return FOCAL_FRAMING.get(shot_type, "[FRAMING: standard composition, medium depth of field]")

# ─── MAIN PROMPT BUILDER ──────────────────────────────────────────────────────

REALISM_ANCHOR = "photorealistic film frame, 35mm Kodak 5219, practical lighting, no digital artifacts, film grain, natural skin texture"
ANTI_CGI = "NO CGI render, NO video game graphics, NO illustration, NO painterly effects, tactile period surfaces"

def build_v31_prompt(shot: dict) -> str:
    shot_type = shot.get("shot_type", "medium")
    location = shot.get("location", "")
    characters = shot.get("characters", [])
    beat_action = shot.get("_beat_action", "") or shot.get("description", "")
    beat_dialogue = shot.get("_beat_dialogue") or shot.get("dialogue_text") or ""
    beat_atmosphere = shot.get("_beat_atmosphere", "")
    # Soundscape = MUSICAL/TONAL DIRECTION (scene-level), not ambient SFX
    # Keyed by scene_id first for precision, falls back to location
    scene_soundscapes = {
        "001": "low sustained string tension, minor key, slow tempo — professional coldness meeting unresolved grief. Rising dread under the surface. No resolution.",
        "002": "sparse piano motif, warm then cold — wonder curdling into tension as the letter is found. Quiet urgency. One instrument. No safety.",
        "003": "staccato low brass, compressed harmonic tension — intimidation rhythm. No melody. Threat made visible in tempo. Cut short.",
        "004": "open string intervals, grey and unresolved — space between notes as important as the notes. Grief breathing freely for the first time.",
        "005": "solo cello, deliberate and mournful — thirty years of secret carried in a single melodic line. Tempo like a heartbeat resisting belief.",
        "006": "low warmth, brief major undertone — the only major key in the estate. Conspiratorial whisper under a warm hum. Trust forming.",
        "007": "returning cello motif, now fractured — the secret pulled into the open. Same theme, broken. Rising.",
        "008": "escalating string ostinato — architecture as tension. Upward motion in score mirrors upward movement on the staircase. Tempo accelerating.",
        "009": "brass punctuation over sustained string bed — imminent threat, time running out. Harmonic collision of two forces at the door.",
        "010": "returning theme now shared between two instruments — Eleanor and Nadia's motifs align. Resolution approaching.",
        "011": "Harriet's theme introduced — fragile, period-specific harpsichord colour. Her voice in the music. Past reaching into present.",
        "012": "full orchestral tension, all motifs colliding — sustained dissonance then sudden release. The house holds its breath. One final note.",
        "013": "single sustained string note fading to silence — the estate after truth. No resolution chord. Open ended. The house remains.",
    }
    scene_id = shot.get("scene_id", "")
    soundscape = scene_soundscapes.get(scene_id, get_soundscape(location))

    parts = []

    # 1. REALISM ANCHOR
    parts.append(realism_anchor(shot_type))

    # 2. CHARACTER DESCRIPTIONS (weaved into action)
    if characters:
        char_descs = []
        for c in characters:
            desc = get_char_desc(c)
            if desc:
                char_descs.append(desc)
        if char_descs:
            parts.append("\n".join(char_descs))

    # 3. ROOM DNA
    dna = get_room_dna(location)
    parts.append(f"[ROOM DNA: {dna}]")

    # 4. SCENE ACTION (beat-driven)
    action_text = beat_action.strip()
    if action_text and not action_text.startswith("INT.") and not action_text.startswith("EXT."):
        parts.append(f"ACTION: {action_text}")
    elif action_text:
        parts.append(action_text)

    # 5. DIALOGUE EMBEDDING
    if beat_dialogue and beat_dialogue.strip():
        dialogue_clean = beat_dialogue.strip().strip('"')
        speaker = shot.get("_dialogue_speaker", "")
        voice = get_voice_signature(speaker)
        if voice:
            parts.append(f"DIALOGUE: \"{dialogue_clean}\" [{voice}] — speaking posture, lips forming words, jaw and throat engaged")
        else:
            parts.append(f"DIALOGUE: \"{dialogue_clean}\" — speaking posture, natural mouth movement")

    # 6. 4 CINEMATIC CHANNELS
    # Camera
    camera_tag = get_camera_tag(shot_type)
    parts.append(camera_tag)

    # Palette
    palette = get_palette(beat_atmosphere, location)
    parts.append(f"[PALETTE: {palette}]")

    # Physics
    parts.append("[PHYSICS: practical period lighting, natural shadows directional, dust motes in light shafts, no fill-card artifice]")

    # Aesthetic
    parts.append(f"[AESTHETIC: Victorian period realism, {ANTI_CGI}]")

    # 7. FOCAL LENGTH ENFORCEMENT
    parts.append(get_focal_framing(shot_type))

    # 8. SOUNDSCAPE REFERENCE
    parts.append(f"[SOUNDSCAPE: {soundscape}]")

    # 9. TONE SHOTS: empty room negative constraint
    if not characters:
        parts.append("No people visible in frame, no figures, empty space only.")

    return "\n".join(p for p in parts if p.strip())


def realism_anchor(shot_type: str) -> str:
    if shot_type in ("establishing", "insert"):
        return f"{REALISM_ANCHOR}, environmental photography"
    elif shot_type in ("close_up", "medium_close", "reaction"):
        return f"{REALISM_ANCHOR}, cinematic portraiture"
    else:
        return f"{REALISM_ANCHOR}, dramatic narrative cinema"


def get_camera_tag(shot_type: str) -> str:
    camera_map = {
        "establishing":  "[CAMERA: 24mm ultra-wide, f/8, slow dolly reveal, deep field]",
        "insert":        "[CAMERA: 100mm macro, f/2.8, static, object-centric close]",
        "medium":        "[CAMERA: 35mm, f/4, static or gentle push, eye-level]",
        "medium_close":  "[CAMERA: 85mm, f/2.0, static, slight tilt down]",
        "close_up":      "[CAMERA: 85mm, f/1.4, static, shallow DOF, face-centric]",
        "two_shot":      "[CAMERA: 35mm, f/4, static or slight settle, confrontational angle]",
        "ots_a":         "[CAMERA: 50mm, f/2.8, over-shoulder A-angle, listener in foreground soft]",
        "ots_b":         "[CAMERA: 50mm, f/2.8, over-shoulder B-angle, listener in foreground soft]",
        "closing":       "[CAMERA: 28mm wide, f/5.6, slow pull-back or static, full room visible]",
        "reaction":      "[CAMERA: 85mm, f/1.4, reaction close-up, micro-expression visible]",
    }
    return camera_map.get(shot_type, "[CAMERA: 50mm, f/2.8, standard lens, natural perspective]")


def get_palette(atmosphere: str, location: str) -> str:
    atm_lower = (atmosphere or "").lower()
    loc_upper = location.upper()

    if any(w in atm_lower for w in ["dread", "threat", "danger", "menac"]):
        return "high contrast, deep cold shadows, desaturated blues and charcoal, muted flesh tones"
    elif any(w in atm_lower for w in ["grief", "melan", "elegy"]):
        return "desaturated cool tones, soft diffused shadows, muted earth palette, restrained contrast"
    elif any(w in atm_lower for w in ["discovery", "reveal", "wonder"]):
        return "warm amber highlights, cool shadow fill, amber-to-teal split, high clarity on focal point"
    elif any(w in atm_lower for w in ["confron", "tension", "defian", "steel"]):
        return "high contrast neutral tones, hard practical shadows, desaturated with deliberate push"
    elif any(w in atm_lower for w in ["warm", "tender", "trust"]):
        return "warm amber and soft gold, low contrast, gentle fill light, period warmth"
    elif "KITCHEN" in loc_upper:
        return "warm orange fire-glow, cool stone walls, practical lamp amber, working-class warmth"
    elif "GARDEN" in loc_upper or "EXTERIOR" in loc_upper:
        return "grey overcast sky, cool greens and greys, desaturated Victorian landscape"
    else:
        return "muted period palette, desaturated earth tones, warm amber highlights in shadow"


# ─── COMPUTE PROMPT STATUS ────────────────────────────────────────────────────

def assess_prompt(shot: dict) -> dict:
    """Return a readiness assessment dict."""
    nano = shot.get("nano_prompt") or ""
    issues = []

    if not nano or len(nano) < 20:
        issues.append("EMPTY or trivially short prompt")

    if shot.get("_has_dialogue") and not shot.get("_beat_dialogue") and not shot.get("dialogue_text"):
        issues.append("MISSING dialogue text for dialogue shot")

    if shot.get("characters") and "35mm" not in nano and "photorealistic" not in nano and "CAMERA" not in nano:
        issues.append("MISSING cinematic channels (camera/palette/physics)")

    if not shot.get("_soundscape_signature"):
        issues.append("MISSING soundscape signature")

    # Check for actor_intent bleed (choreography text in nano_prompt)
    if "Speaking:" in nano or "0-5s:" in nano or "5-10s:" in nano:
        issues.append("CONTAMINATED with choreography/actor_intent text")

    if shot.get("characters") and "[ROOM DNA" not in nano and "floor-to-ceiling" not in nano and "marble staircase" not in nano:
        issues.append("MISSING room DNA")

    return {
        "shot_id": shot["shot_id"],
        "issues": issues,
        "ready": len(issues) == 0,
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("ATLAS Prompt Finalizer V31.0")
    print("=" * 60)

    with open(SHOT_PLAN_PATH) as f:
        data = json.load(f)

    if isinstance(data, list):
        shots = data
        is_bare_list = True
    else:
        shots = data["shots"]
        is_bare_list = False

    print(f"Loaded {len(shots)} shots across {len(set(s.get('scene_id','?') for s in shots))} scenes")

    # Build pre-audit report
    pre_audit = [assess_prompt(s) for s in shots]
    pre_issues = sum(1 for a in pre_audit if not a["ready"])
    print(f"\nPre-finalization: {pre_issues}/{len(shots)} shots have issues")

    # Update each shot
    updated = 0
    for shot in shots:
        location = shot.get("location", "")
        scene_id_for_sound = shot.get("scene_id", "")
        scene_sound_map = {
            "001": "low sustained string tension, minor key, slow tempo — professional coldness meeting unresolved grief. Rising dread under the surface. No resolution.",
            "002": "sparse piano motif, warm then cold — wonder curdling into tension as the letter is found. Quiet urgency. One instrument. No safety.",
            "003": "staccato low brass, compressed harmonic tension — intimidation rhythm. No melody. Threat made visible in tempo. Cut short.",
            "004": "open string intervals, grey and unresolved — space between notes as important as the notes. Grief breathing freely for the first time.",
            "005": "solo cello, deliberate and mournful — thirty years of secret carried in a single melodic line. Tempo like a heartbeat resisting belief.",
            "006": "low warmth, brief major undertone — the only major key in the estate. Conspiratorial whisper under a warm hum. Trust forming.",
            "007": "returning cello motif, now fractured — the secret pulled into the open. Same theme, broken. Rising.",
            "008": "escalating string ostinato — architecture as tension. Upward motion in score mirrors upward movement on the staircase. Tempo accelerating.",
            "009": "brass punctuation over sustained string bed — imminent threat, time running out. Harmonic collision of two forces at the door.",
            "010": "returning theme now shared between two instruments — Eleanor and Nadia's motifs align. Resolution approaching.",
            "011": "Harriet's theme introduced — fragile, period-specific harpsichord colour. Her voice in the music. Past reaching into present.",
            "012": "full orchestral tension, all motifs colliding — sustained dissonance then sudden release. The house holds its breath. One final note.",
            "013": "single sustained string note fading to silence — the estate after truth. No resolution chord. Open ended. The house remains.",
        }
        soundscape = scene_sound_map.get(scene_id_for_sound, get_soundscape(location))
        shot["_soundscape_signature"] = soundscape

        # Voice signature for dialogue shots
        speaker = shot.get("_dialogue_speaker", "")
        if speaker and speaker.strip():
            shot["_voice_signature"] = get_voice_signature(speaker)
        elif shot.get("characters"):
            # Multi-char: build combined voice signatures
            voices = []
            for c in shot.get("characters", []):
                v = get_voice_signature(c)
                if v:
                    voices.append(f"{c}: {v}")
            if voices:
                shot["_voice_signature"] = " | ".join(voices)

        # Build upgraded nano_prompt
        new_prompt = build_v31_prompt(shot)

        # Only update if current prompt is weak or missing key elements
        current = shot.get("nano_prompt") or ""
        needs_upgrade = (
            len(current) < 50 or
            "photorealistic" not in current or
            "[ROOM DNA" not in current or
            "Speaking:" in current or
            "0-5s:" in current or
            (shot.get("characters") and "CAMERA" not in current)
        )

        if needs_upgrade:
            shot["_nano_prompt_v30"] = current  # archive old prompt
            shot["nano_prompt"] = new_prompt
            updated += 1

    # Post-audit
    post_audit = [assess_prompt(s) for s in shots]
    post_issues = sum(1 for a in post_audit if not a["ready"])
    print(f"Post-finalization: {post_issues}/{len(shots)} shots still have issues")
    print(f"Updated {updated} prompts")

    # Save
    backup_path = SHOT_PLAN_PATH.with_suffix(".json.pre_v31_backup")
    with open(backup_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nBackup saved: {backup_path.name}")

    with open(SHOT_PLAN_PATH, "w") as f:
        if is_bare_list:
            json.dump(shots, f, indent=2)
        else:
            json.dump(data, f, indent=2)
    print(f"Shot plan saved: {SHOT_PLAN_PATH.name}")

    # Generate report data
    report_data = {
        "total_shots": len(shots),
        "prompts_updated": updated,
        "pre_issues": pre_issues,
        "post_issues": post_issues,
        "pre_audit": pre_audit,
        "post_audit": post_audit,
        "scenes": {}
    }

    for shot in shots:
        sid = shot.get("scene_id", "?")
        if sid not in report_data["scenes"]:
            report_data["scenes"][sid] = {
                "location": shot.get("location", "?"),
                "shots": [],
                "soundscape": shot.get("_soundscape_signature", ""),
            }

        post = next((a for a in post_audit if a["shot_id"] == shot["shot_id"]), {})
        report_data["scenes"][sid]["shots"].append({
            "shot_id": shot["shot_id"],
            "shot_type": shot.get("shot_type"),
            "characters": shot.get("characters", []),
            "has_frames": bool(shot.get("first_frame_path")),
            "has_video": bool(shot.get("video_path")),
            "identity_score": shot.get("_frame_identity_score") or shot.get("_identity_score"),
            "approval_status": shot.get("_approval_status"),
            "issues": post.get("issues", []),
            "ready": post.get("ready", False),
        })

    return report_data


if __name__ == "__main__":
    result = main()

    # Print scene-by-scene summary
    print("\n" + "=" * 60)
    print("SCENE-BY-SCENE SUMMARY")
    print("=" * 60)

    generation_order = []

    for scene_id, scene_data in sorted(result["scenes"].items()):
        shots = scene_data["shots"]
        ready_count = sum(1 for s in shots if s["ready"])
        issues_count = sum(len(s["issues"]) for s in shots)
        has_frames_count = sum(1 for s in shots if s["has_frames"])
        has_video_count = sum(1 for s in shots if s["has_video"])

        status = "READY" if issues_count == 0 else f"{issues_count} issue(s)"
        print(f"\nScene {scene_id} — {scene_data['location']}")
        print(f"  Shots: {len(shots)} | Frames: {has_frames_count} | Videos: {has_video_count} | Status: {status}")
        print(f"  Soundscape: {scene_data['soundscape'][:60]}...")

        if issues_count == 0 and has_frames_count == 0:
            generation_order.append(scene_id)

    print(f"\n\nRECOMMENDED GENERATION ORDER (scenes without frames, ready prompts):")
    if generation_order:
        print("  " + " → ".join(generation_order))
    else:
        print("  All scenes already have frames or have issues to resolve first")
