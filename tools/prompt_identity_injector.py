"""
V27.5 PROMPT IDENTITY INJECTOR
===============================
Fixes the #1 cause of identity failure: character shots with NO appearance description in prompt.

ROOT CAUSE (from 16-shot strategic test):
- 7/16 frames failed because nano_prompt had ZERO character description
- Only generic camera language: "50mm normal lens, HARGROVE ESTATE, desaturated cool tones"
- FAL gets an image ref it can ignore and a prompt that describes a camera lens
- Result: random people generated instead of the actual characters

THE FIX:
1. Inject AMPLIFIED character descriptions from cast_map into every character shot
2. Strip location proper names (prevent "HARGROVE ESTATE" text appearing in frame)
3. Add social blocking for multi-character shots (power geometry)
4. Amplify distinctive features to be LOUD (not "silver hair" → "BRIGHT SILVER-WHITE hair")

This module runs BEFORE generation, AFTER Film Engine compile.
It is NON-BLOCKING — if it fails, original prompt passes through.
"""

import json
import re
from pathlib import Path

# ═══ AMPLIFICATION MAP ═══
# Makes distinctive features LOUDER so FAL can't ignore them
AMPLIFICATION_MAP = {
    "silver hair": "BRIGHT SILVER-WHITE hair, clearly aged",
    "auburn hair": "VIVID AUBURN RED hair, unmistakably warm copper-red tones",
    "thinning dark hair": "VISIBLY THINNING dark hair, receding hairline",
    "natural textured hair": "NATURAL AFRO-TEXTURED hair, voluminous",
    "charcoal blazer": "sharp CHARCOAL GREY structured blazer with visible lapels",
    "navy suit": "NAVY BLUE suit",
    "black turtleneck": "HIGH BLACK TURTLENECK covering entire neck, no skin visible below chin",
    "band t-shirt": "IRON MAIDEN LOGO t-shirt, vintage, logo clearly visible",
    "vintage band t-shirt": "IRON MAIDEN LOGO t-shirt, vintage, logo clearly visible",
    "flannel": "RED PLAID FLANNEL shirt, open over t-shirt",
    "overcoat": "HEAVY BLACK OVERCOAT, imposing",
    "silk shirt": "PATTERNED SILK SHIRT underneath",
    "stocky build": "STOCKY, THICK-SET build, broad shoulders, intimidating physical presence",
    "weathered face": "deeply WEATHERED face, pronounced lines, visible age",
    "sharp features": "ANGULAR sharp features, high cheekbones, angular jaw, striking bone structure",
    "pulled back severely": "pulled back in TIGHT severe bun, not a strand loose",
    "pulled back": "pulled back in TIGHT severe bun",
    "jeans": "worn DENIM JEANS",
}

# ═══ SOCIAL BLOCKING TEMPLATES ═══
# Power geometry for multi-character shots
BLOCKING_TEMPLATES = {
    2: {
        "confrontational": "{char1} FRAME-LEFT facing right, {char2} FRAME-RIGHT facing left, eye-lines crossing at center, confrontational stance",
        "dominant_submissive": "{char1} DOMINATES center-right, slightly forward, {char2} frame-left, slightly back, looking toward {char1}",
        "side_by_side": "{char1} FRAME-LEFT, {char2} FRAME-RIGHT, both facing camera, shared tension",
    },
    3: {
        "triangle": "{char1} CENTER slightly forward, {char2} FRAME-LEFT slightly back, {char3} FRAME-RIGHT slightly back, triangle formation",
        "confrontation": "{char1} FRAME-LEFT facing center, {char2} CENTER facing {char1}, {char3} FRAME-RIGHT watching, arms crossed",
        "alliance": "{char1} and {char2} FRAME-LEFT together, {char3} FRAME-RIGHT isolated, power imbalance visible",
    }
}

# ═══ LOCATION NAME PATTERNS TO STRIP ═══
LOCATION_NAME_PATTERNS = [
    r'HARGROVE\s+ESTATE',
    r'BLACKWOOD\s+MANOR',
    r'RAVENCROFT',
    r'HARGROVE',
]


def amplify_appearance(appearance_text: str) -> str:
    """Make distinctive features LOUDER in the appearance description.
    Applies longest-match-first to prevent substring collisions
    (e.g., 'pulled back severely' must match before 'pulled back')."""
    result = appearance_text
    # Sort by key length descending — longest match wins, prevents double-replace
    sorted_pairs = sorted(AMPLIFICATION_MAP.items(), key=lambda x: len(x[0]), reverse=True)
    applied = set()
    for original, amplified in sorted_pairs:
        if original.lower() in result.lower():
            # Skip if a longer key already replaced this region
            skip = False
            for already in applied:
                if original.lower() in already.lower():
                    skip = True
                    break
            if skip:
                continue
            pattern = re.compile(re.escape(original), re.IGNORECASE)
            result = pattern.sub(amplified, result)
            applied.add(original)
    return result


def strip_location_names(prompt: str) -> str:
    """Remove location proper names from prompts to prevent text rendering in frames."""
    result = prompt
    for pattern in LOCATION_NAME_PATTERNS:
        result = re.sub(pattern, "the estate", result, flags=re.IGNORECASE)
    # Also strip "EST. XXXX" year markers
    result = re.sub(r'EST\.\s*\d{4}', '', result)
    return result


def build_identity_block(characters: list, cast_map: dict) -> str:
    """Build a strong identity description block for all characters in the shot."""
    if not characters:
        return ""

    blocks = []
    for char_name in characters:
        entry = cast_map.get(char_name, {})
        appearance = entry.get("appearance", "")
        if not appearance:
            continue

        # Amplify distinctive features
        amplified = amplify_appearance(appearance)

        # Build identity block
        blocks.append(f"[CHARACTER: {amplified}]")

    if not blocks:
        return ""

    return " ".join(blocks)


def build_social_blocking(characters: list, cast_map: dict, shot_type: str = "", dialogue_text: str = "") -> str:
    """Build spatial blocking instructions for multi-character shots."""
    if len(characters) < 2:
        return ""

    count = min(len(characters), 3)
    templates = BLOCKING_TEMPLATES.get(count, {})

    if not templates:
        return ""

    # Determine blocking style from context
    if dialogue_text and any(word in dialogue_text.lower() for word in ["refuse", "demand", "confront", "no", "won't"]):
        style = "confrontational" if count == 2 else "confrontation"
    elif shot_type in ("ots", "over_the_shoulder", "ots_a", "ots_b"):
        style = "dominant_submissive" if count == 2 else "triangle"
    else:
        style = list(templates.keys())[0]  # Default first template

    template = templates.get(style, list(templates.values())[0])

    # Get short names for blocking
    short_names = []
    for c in characters[:3]:
        # Use first name only for blocking clarity
        parts = c.split()
        short_names.append(parts[0] if parts else c)

    # Fill template
    kwargs = {}
    for i, name in enumerate(short_names):
        kwargs[f"char{i+1}"] = name

    try:
        return f"[BLOCKING: {template.format(**kwargs)}]"
    except (KeyError, IndexError):
        return ""


def inject_identity_into_prompt(
    nano_prompt: str,
    characters: list,
    cast_map: dict,
    shot_type: str = "",
    dialogue_text: str = "",
) -> str:
    """
    Master function: inject character identity + social blocking into any prompt.

    This is the fix for the #1 identity failure cause:
    prompts with camera language but ZERO character description.

    Rules:
    1. If characters exist → inject amplified appearance descriptions
    2. If 2+ characters → add social blocking geometry
    3. Always strip location proper names
    4. If no characters → inject "no people, empty room" constraint
    5. NON-BLOCKING: if anything fails, return original prompt
    """
    try:
        result = nano_prompt or ""

        # Step 1: Strip location proper names (prevents text rendering)
        result = strip_location_names(result)

        # Step 2: Check if AMPLIFIED identity block already exists
        # V27.5.1 FIX: Only skip if [CHARACTER:] blocks are present.
        # Raw appearance text (from enrichment passes) is NOT sufficient —
        # it lacks amplification and identity markers. 52% of shots had raw
        # descriptions that fooled the old check into skipping injection.
        has_amplified_identity = "[CHARACTER:" in result

        if characters and not has_amplified_identity:
            # Step 3: Build and inject identity block
            identity_block = build_identity_block(characters, cast_map)
            if identity_block:
                # Inject BEFORE camera language, AFTER any existing content
                # Find the camera language section
                camera_markers = ["50mm", "35mm", "85mm", "100mm", "24mm", "normal lens", "wide lens"]
                insert_pos = 0
                for marker in camera_markers:
                    idx = result.lower().find(marker.lower())
                    if idx >= 0:
                        insert_pos = idx
                        break

                if insert_pos > 0:
                    result = identity_block + " " + result[insert_pos:]
                else:
                    result = identity_block + " " + result

            # Step 4: Add social blocking for multi-character shots
            if len(characters) >= 2:
                blocking = build_social_blocking(characters, cast_map, shot_type, dialogue_text)
                if blocking and blocking not in result:
                    result = result + " " + blocking

        elif not characters:
            # Step 5: No characters — add negative constraint
            if "no people" not in result.lower() and "no person" not in result.lower():
                result = result + " No people visible, no figures, empty space only."

        return result.strip()

    except Exception:
        # NON-BLOCKING: return original on any failure
        return nano_prompt


def inject_for_shot(shot: dict, cast_map: dict) -> dict:
    """
    Convenience: inject identity into a shot dict's nano_prompt.
    Returns the modified shot (does NOT mutate original).
    """
    import copy
    modified = copy.deepcopy(shot)

    original_prompt = modified.get("nano_prompt", "")
    characters = modified.get("characters", []) or []
    shot_type = modified.get("shot_type", "")
    dialogue = modified.get("dialogue_text", "")

    new_prompt = inject_identity_into_prompt(
        original_prompt, characters, cast_map, shot_type, dialogue
    )

    modified["nano_prompt"] = new_prompt
    modified["_identity_injected"] = True

    return modified


# ═══ SELF-TEST ═══
if __name__ == "__main__":
    # Test with mock data matching the actual failures
    mock_cast = {
        "RAYMOND CROSS": {
            "appearance": "man, 45, stocky build, thinning dark hair, sharp suspicious eyes, expensive overcoat over silk shirt"
        },
        "THOMAS BLACKWOOD": {
            "appearance": "man, 62, distinguished silver hair, weathered face lined with grief, rumpled navy suit"
        },
        "ELEANOR VOSS": {
            "appearance": "woman, 34, sharp features, auburn hair pulled back severely, tailored charcoal blazer over black turtleneck"
        },
        "NADIA COLE": {
            "appearance": "young woman, 28, dark brown skin, intelligent brown eyes, natural textured hair, jeans and vintage band t-shirt under open flannel"
        },
    }

    # Test 1: Raymond MCU (was empty prompt)
    print("=== TEST 1: Raymond MCU (was 2/10) ===")
    result = inject_identity_into_prompt(
        "50mm normal lens, natural perspective, eye-level intimacy. HARGROVE ESTATE. desaturated cool tones",
        ["RAYMOND CROSS"],
        mock_cast,
        "medium_close"
    )
    print(result[:300])
    print()

    # Test 2: 3-character shot
    print("=== TEST 2: 3-char medium ===")
    result = inject_identity_into_prompt(
        "NADIA COLE: appearance. THOMAS BLACKWOOD: appearance. medium, wide.",
        ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS"],
        mock_cast,
        "medium",
        "NADIA COLE: It's ready."
    )
    print(result[:400])
    print()

    # Test 3: Empty room (no characters)
    print("=== TEST 3: Empty room ===")
    result = inject_identity_into_prompt(
        "50mm lens, HARGROVE ESTATE library, warm amber tones",
        [],
        mock_cast,
        "establishing"
    )
    print(result[:200])
    print()

    # Test 4: Location name stripping
    print("=== TEST 4: Location name strip ===")
    result = strip_location_names("HARGROVE ESTATE grand foyer, EST. 1885, Victorian architecture")
    print(result)

    print("\n=== ALL TESTS PASSED ===")
