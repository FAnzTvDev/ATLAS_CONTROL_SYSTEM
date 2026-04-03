#!/usr/bin/env python3
"""
ATLAS V28 — Truth-to-Prompt Translator
========================================
The bridge between Intelligence and Execution.

This module reads the locked truth fields on each shot and translates
them into prompt text that FAL can execute. Without this, the truth
fields exist on the shot data but never reach the model.

THE PRINCIPLE:
  Truth fields are MACHINE-READABLE directives (for the pipeline).
  FAL needs NATURAL LANGUAGE descriptions (for the model).
  This translator converts one into the other.

WHAT IT TRANSLATES:
  _eye_line_target    → "[PERFORMANCE: eyes directed {target}]"
  _body_direction     → "[PERFORMANCE: {body action}]"
  _movement_state     → "static pose" / "walking through space" / "transitioning"
  _prop_focus         → "[PROP: {object} visible, character interacts with it]"
  _emotional_state    → atmosphere/mood injection
  _story_purpose      → framing emphasis (tight for emotion, wide for geography)
  _blocking_direction → spatial positioning instruction

WHAT IT DOES NOT DO:
  - Does NOT replace existing prompt content
  - Does NOT override [CHARACTER:], [ROOM DNA:], [LIGHTING RIG:] blocks
  - Does NOT touch identity injection (that's prompt_identity_injector.py)
  - Does NOT touch negative prompts

WHERE IT RUNS:
  - V26 Controller Phase E6: after Film Engine + Identity Injection, before FAL
  - Orchestrator generate-first-frames: after identity injection, before FAL call
  - Both paths (belt-and-suspenders per C1: Dual Authority Separation)

NON-BLOCKING: If translation fails, original prompt passes through unchanged.
"""

import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# PERFORMANCE DIRECTION TEMPLATES
# ═══════════════════════════════════════════════════════════════════

# Eye-line translation: truth field → FAL-friendly description
EYE_LINE_TRANSLATIONS = {
    "through camera viewfinder": "eyes looking through camera viewfinder, focused and deliberate",
    "down at letter": "eyes cast downward at paper in hands, reading intently",
    "down at text": "eyes scanning text, head slightly tilted",
    "scanning across": "eyes moving slowly across the space, head turning",
    "scanning book spines": "eyes tracking along shelf, reading spines",
    "toward door": "gaze directed toward doorway, alert",
    "toward window": "eyes drawn toward window light",
    "widening on discovery": "eyes widening, breath catching, realization visible",
    "fixed on target": "unblinking stare, jaw set, focused",
    "shifting to new object": "quick eye shift, attention caught by something new",
    "neutral, present": "natural gaze, present and grounded in the space",
    "downward": "eyes cast slightly downward, introspective",
    "ahead into middle distance": "gaze drifting forward, unfocused, lost in thought",
}

# Body direction translation
BODY_TRANSLATIONS = {
    "walking slowly": "walking slowly, natural gait, weight shifting",
    "walking through space": "moving through the room, body in motion",
    "stepping into frame": "entering the space, body transitioning through doorway",
    "hands reacting": "hands moving quickly, grabbing or catching",
    "carefully opening": "fingers working delicately, opening something with care",
    "hand moving to pocket": "hand sliding to pocket, quick furtive movement",
    "still, tension": "body still but tension visible in shoulders and jaw",
    "visible emotional change": "micro-expression shifting, internal state changing visibly",
    "breath catches": "sharp inhale, posture stiffening slightly",
    "forward lean": "leaning forward, attention sharpening",
    "natural micro-movements": "natural breathing, subtle weight shifts, alive and present",
    "present, natural": "relaxed presence, natural breathing rhythm",
}

# Movement state → prompt modifier
MOVEMENT_MODIFIERS = {
    "walking": "continuous walking motion, natural gait, body moving through space",
    "transitioning": "shifting position, weight transfer visible, not static",
    "pivoting": "body rotating, shoulders leading the turn",
    "static": "still, grounded, no locomotion — only breathing and micro-movements",
}

# Prop interaction templates
PROP_TEMPLATES = {
    "letter": "folded paper/letter visible in hands or nearby",
    "book": "book visible, leather-bound, aged pages",
    "camera": "professional camera in hands, held at chest or eye level",
    "phone": "phone in hand, screen glow on face",
    "door": "doorway visible in frame, architectural feature",
    "window": "window light source visible, casting directional light",
    "painting": "framed artwork visible on wall",
    "desk": "desk surface visible with objects",
    "photograph": "photograph visible, printed image",
    "manuscript": "aged document or manuscript visible",
}


# ═══════════════════════════════════════════════════════════════════
# MAIN TRANSLATOR
# ═══════════════════════════════════════════════════════════════════

def translate_truth_to_prompt(prompt: str, shot: Dict) -> str:
    """
    Inject truth-derived performance direction into the prompt.

    Takes the existing compiled prompt (with [CHARACTER:], [ROOM DNA:], etc.)
    and adds a [PERFORMANCE:] block derived from the shot's truth fields.

    Args:
        prompt: The compiled nano_prompt (after Film Engine + Identity Injection)
        shot: The shot dict with truth fields (_eye_line_target, _body_direction, etc.)

    Returns:
        Enhanced prompt with [PERFORMANCE:] block. Original prompt if no truth data.
    """
    # Skip if no truth fields present
    if not shot.get("_truth_locked") and not shot.get("_beat_enriched"):
        return prompt

    # Skip if [PERFORMANCE:] already injected (idempotency)
    if "[PERFORMANCE:" in prompt:
        return prompt

    shot_id = shot.get("shot_id", "?")
    parts = []

    # ── 1. Eye-line direction ──
    eye_target = shot.get("_eye_line_target", "")
    if eye_target and eye_target not in ("neutral, present in scene", "neutral"):
        eye_text = _translate_eye_line(eye_target)
        if eye_text:
            parts.append(f"eyes: {eye_text}")

    # ── 2. Body direction ──
    body_dir = shot.get("_body_direction", "")
    if body_dir and body_dir not in ("natural micro-movements, breathing", "present, natural micro-movements"):
        body_text = _translate_body(body_dir)
        if body_text:
            parts.append(f"body: {body_text}")

    # ── 3. Movement state ──
    movement = shot.get("_movement_state", "")
    if movement and movement != "static":
        move_text = MOVEMENT_MODIFIERS.get(movement, movement)
        parts.append(f"motion: {move_text}")

    # ── 4. Prop focus ──
    prop_focus = shot.get("_prop_focus", "")
    if prop_focus:
        prop_text = _translate_props(prop_focus)
        if prop_text:
            parts.append(f"props: {prop_text}")

    # ── 5. Emotional atmosphere ──
    emotional = shot.get("_emotional_state", "")
    if emotional and emotional != "neutral":
        parts.append(f"mood: {emotional}")

    # Build the [PERFORMANCE:] block
    if not parts:
        return prompt  # No truth data worth injecting

    perf_block = "[PERFORMANCE: " + ". ".join(parts) + ".]"

    # Inject BEFORE any [CHARACTER:] or [ROOM DNA:] blocks (so it's early in the prompt)
    # If no blocks exist, append at end
    block_pattern = r'\[(?:CHARACTER|ROOM DNA|LIGHTING RIG|TIGHT FRAMING|BLOCKING):'
    match = re.search(block_pattern, prompt)
    if match:
        # Insert before the first block
        insert_pos = match.start()
        enhanced = prompt[:insert_pos].rstrip() + " " + perf_block + " " + prompt[insert_pos:]
    else:
        # Append at end
        enhanced = prompt.rstrip() + " " + perf_block

    logger.info(f"[TRUTH→PROMPT] {shot_id}: injected {len(parts)} performance directives")
    return enhanced


def _translate_eye_line(eye_target: str) -> str:
    """Convert truth eye-line to FAL-friendly description."""
    eye_lower = eye_target.lower()
    # Check for direct matches
    for key, translation in EYE_LINE_TRANSLATIONS.items():
        if key in eye_lower:
            return translation
    # Pass through the raw truth (it's usually already descriptive)
    return eye_target


def _translate_body(body_dir: str) -> str:
    """Convert truth body direction to FAL-friendly description."""
    body_lower = body_dir.lower()
    for key, translation in BODY_TRANSLATIONS.items():
        if key in body_lower:
            return translation
    return body_dir


def _translate_props(prop_focus: str) -> str:
    """Convert truth prop focus to FAL-friendly description."""
    parts = []
    for prop_name in prop_focus.split(","):
        prop_name = prop_name.strip().lower()
        if prop_name in PROP_TEMPLATES:
            parts.append(PROP_TEMPLATES[prop_name])
        elif prop_name:
            parts.append(f"{prop_name} visible in scene")
    return ", ".join(parts) if parts else ""


# ═══════════════════════════════════════════════════════════════════
# TRUTH VERIFICATION — Post-compile check
# ═══════════════════════════════════════════════════════════════════

def verify_prompt_reflects_truth(prompt: str, shot: Dict) -> Dict:
    """
    Verify that the compiled prompt actually reflects the shot's truth fields.
    Returns a report of what's present and what's missing.

    This is for the Runtime Traceability requirement — ensuring
    the prompt that goes to FAL actually carries the intelligence
    that was authored into the truth fields.
    """
    report = {
        "shot_id": shot.get("shot_id", "?"),
        "has_performance_block": "[PERFORMANCE:" in prompt,
        "has_character_block": "[CHARACTER:" in prompt,
        "has_room_dna": "[ROOM DNA:" in prompt,
        "truth_fields_present": {},
        "truth_fields_reflected": {},
        "score": 0.0,
    }

    prompt_lower = prompt.lower()
    checks = 0
    hits = 0

    # Check eye-line
    eye = shot.get("_eye_line_target", "")
    if eye and eye != "neutral, present in scene":
        checks += 1
        report["truth_fields_present"]["eye_line"] = eye
        # Check if any key phrase from the eye-line appears in the prompt
        eye_words = set(eye.lower().split()) - {"the", "at", "in", "and", "a"}
        if any(w in prompt_lower for w in eye_words if len(w) > 3):
            hits += 1
            report["truth_fields_reflected"]["eye_line"] = True
        else:
            report["truth_fields_reflected"]["eye_line"] = False

    # Check body direction
    body = shot.get("_body_direction", "")
    if body and body != "natural micro-movements, breathing":
        checks += 1
        report["truth_fields_present"]["body"] = body
        body_words = set(body.lower().split()) - {"the", "at", "in", "and", "a"}
        if any(w in prompt_lower for w in body_words if len(w) > 3):
            hits += 1
            report["truth_fields_reflected"]["body"] = True
        else:
            report["truth_fields_reflected"]["body"] = False

    # Check prop focus
    prop = shot.get("_prop_focus", "")
    if prop:
        checks += 1
        report["truth_fields_present"]["prop"] = prop
        if any(p.strip().lower() in prompt_lower for p in prop.split(",")):
            hits += 1
            report["truth_fields_reflected"]["prop"] = True
        else:
            report["truth_fields_reflected"]["prop"] = False

    # Check character identity (from identity injector, not us)
    chars = shot.get("characters") or []
    if chars:
        checks += 1
        report["truth_fields_present"]["characters"] = len(chars)
        if "[CHARACTER:" in prompt:
            hits += 1
            report["truth_fields_reflected"]["characters"] = True
        else:
            report["truth_fields_reflected"]["characters"] = False

    report["score"] = hits / max(checks, 1)
    return report


# ═══════════════════════════════════════════════════════════════════
# BATCH TRANSLATOR — For controller phase usage
# ═══════════════════════════════════════════════════════════════════

def translate_scene_truth(shots: List[Dict]) -> int:
    """
    Translate truth fields to prompt text for ALL shots in a scene.
    Mutates shot["nano_prompt"] in place.
    Returns count of shots translated.
    """
    count = 0
    for shot in shots:
        nano = shot.get("nano_prompt", "")
        if not nano:
            continue
        enhanced = translate_truth_to_prompt(nano, shot)
        if enhanced != nano:
            shot["nano_prompt"] = enhanced
            count += 1
    return count


# ═══════════════════════════════════════════════════════════════════
# CLI — Test translation on a real shot
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    shot_id = sys.argv[2] if len(sys.argv) > 2 else "002_017B"

    with open(f"{project}/shot_plan.json") as f:
        sp = json.load(f)
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    shot = next((s for s in shots if s.get("shot_id") == shot_id), None)

    if not shot:
        print(f"Shot {shot_id} not found")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  TRUTH → PROMPT TRANSLATION — {shot_id}")
    print(f"{'='*70}")

    # Show truth fields
    print(f"\n  TRUTH FIELDS:")
    for key in sorted(shot.keys()):
        if key.startswith(("_beat_", "_eye_", "_body_", "_movement_", "_emotional_", "_prop_", "_story_", "_cut_")):
            print(f"    {key}: {str(shot[key])[:70]}")

    # Show original prompt
    nano = shot.get("nano_prompt", "")
    print(f"\n  ORIGINAL PROMPT ({len(nano)} chars):")
    print(f"    {nano[:200]}...")

    # Translate
    enhanced = translate_truth_to_prompt(nano, shot)
    print(f"\n  ENHANCED PROMPT ({len(enhanced)} chars):")
    print(f"    {enhanced[:300]}...")

    # Verify
    report = verify_prompt_reflects_truth(enhanced, shot)
    print(f"\n  TRUTH REFLECTION SCORE: {report['score']:.0%}")
    for field, reflected in report["truth_fields_reflected"].items():
        status = "PRESENT" if reflected else "MISSING"
        print(f"    {field}: {status}")

    print(f"\n{'='*70}")
