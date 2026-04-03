"""
V27.1.5 SCENE VISUAL DNA — Architectural Consistency Token

THE PROBLEM:
Each shot's prompt describes the room independently. FAL generates a different
room every time — the staircase changes material, color, proximity, and design
between shots. The audience sees 4 different staircases in the same scene.

THE FIX:
Extract a LOCKED architectural description from the story bible location +
atmosphere, then APPEND it to every shot's nano_prompt in that scene.
This forces FAL to generate the SAME room features across all shots.

ARCHITECTURE DNA = immutable physical features that MUST NOT change between shots:
  - Staircase material, design, color
  - Wall material, paneling, color
  - Floor material, pattern
  - Ceiling features (chandelier, molding, dome)
  - Light source type, color temperature, direction
  - Key furniture (console table, mirror, coat rack)

WHAT DNA IS NOT:
  - Character positions (those change)
  - Camera angle (changes per shot)
  - Emotional atmosphere (changes per beat)
  - Framing/lens (changes per shot type)

DNA is appended to nano_prompt as: "[ROOM DNA: ...]"
This ensures the model sees the same room description regardless of shot type.

ROOM DNA TEMPLATES:
  Each room type has a default DNA that can be OVERRIDDEN by story bible details.
  The story bible's atmosphere + beat descriptions enrich the template.
"""

import re
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# ROOM DNA TEMPLATES — default architectural fingerprints
# ═══════════════════════════════════════════════════════════════

ROOM_DNA_TEMPLATES = {
    "foyer": {
        "architecture": "Victorian grand foyer, double-height ceiling with ornate crown molding",
        "staircase": "single curved cream marble staircase with white balustrades, brass handrail, NO dark wood, NO brown, NO mahogany",
        "walls": "dark wood-paneled walls with wainscoting, faded floral wallpaper above, oil portraits in gilded frames",
        "floor": "warm cream marble floor with subtle veining, large Persian rug in center, NO checkered tile, NO black and white pattern",
        "ceiling": "crystal chandelier (unlit, dusty), coffered ceiling with dark beams",
        "fixtures": "heavy oak front doors with brass hardware, coat rack, umbrella stand, console table with mirror above",
        "light": "morning light through stained glass transom, dust particles visible in light shafts",
        # ── CAMERA POSITIONS: each describes what the camera SEES from that vantage point ──
        "camera_positions": {
            "wide_master": (
                "Camera at foyer entrance doorway looking INWARD. Full room depth visible: "
                "cream marble floor receding to staircase base, curved mahogany banister sweeping "
                "upward left, chandelier hanging center-frame overhead, front door frame at "
                "periphery, portrait wall receding right, depth of field deep, all architecture sharp"
            ),
            "interior_atmosphere": (
                "Camera inside the foyer looking toward the staircase. Staircase fills center frame, "
                "banister curves away upward, portrait wall on left ascending with stairs, "
                "chandelier above and slightly behind camera, warm lamplight pooling on marble floor, "
                "upper landing visible in shadow at top, sense of vertical height"
            ),
            "reverse_angle": (
                "Camera at far staircase base looking BACK toward the front entrance door. "
                "Heavy oak front doors visible at far end of frame, dusty light shaft from transom above, "
                "coat rack and umbrella stand flanking doorway, marble floor stretching between camera and door, "
                "wood-paneled walls receding toward entrance, reverse spatial geography"
            ),
            "insert_detail": (
                "Extreme close-up. Tarnished brass door hardware or carved banister newel post. "
                "Worn metal or wood surface, patina of age and use, shallow depth of field, "
                "background blurred to warm amber and shadow shapes, architectural detail sharp"
            ),
        },
    },
    "library": {
        "architecture": "Victorian library, floor-to-ceiling built-in mahogany bookshelves on three walls",
        "walls": "dark mahogany bookshelves packed with leather-bound volumes, rolling ladder on brass rail",
        "floor": "dark hardwood with large faded oriental rug, reading table in center",
        "ceiling": "pressed tin ceiling with gas-to-electric brass fixture, warm pool of light below",
        "fixtures": "leather wingback chairs, standing globe, drinks cabinet, typewriter on side desk",
        "light": "warm amber lamplight, deep shadows between shelving bays, green banker's lamp glow",
        "camera_positions": {
            "wide_master": (
                "Camera at library doorway looking INWARD. Full room depth: floor-to-ceiling mahogany "
                "bookshelves receding on both sides into shadow, central reading table mid-frame with "
                "scattered papers and open books, brass chandelier overhead, Persian rug on dark hardwood, "
                "window alcove visible at far end, warm amber lamp pools, deep depth of field"
            ),
            "interior_atmosphere": (
                "Camera inside the library beside the fireplace looking ACROSS the room. "
                "Warm amber hearth glow in foreground, leather wingback chair near fire, "
                "bookshelves filling the opposite wall, rolling ladder on brass rail, "
                "dancing firelight catching leather spines, green banker's lamp on reading table, "
                "room's depth compressed by warm interior light"
            ),
            "reverse_angle": (
                "Camera at far window alcove looking BACK toward the library doorway. "
                "Door frame visible at far end, bookshelves flanking both sides converging toward entrance, "
                "reading table in middle ground between camera and door, warm lamplight silhouetting "
                "shelved volumes, cool daylight from window behind camera lighting the reverse view"
            ),
            "insert_detail": (
                "Extreme close-up. Leather-bound book spine, gold-embossed title lettering, "
                "aged dark leather with worn patina, dust motes visible in shaft of amber candlelight, "
                "adjacent spines soft-blurred behind, shallow depth of field, warm amber bokeh background"
            ),
        },
    },
    "drawing_room": {
        "architecture": "Victorian drawing room, high ceilings with ornate plasterwork",
        "walls": "sage green wallpaper with damask pattern, gilt-framed landscapes, heavy velvet drapes",
        "floor": "polished dark wood with Aubusson rug, fireplace hearth in grey marble",
        "ceiling": "elaborate plaster rose ceiling medallion, gas chandelier converted to electric",
        "fixtures": "chaise longue, settee, marble-topped side tables, piano in corner, fire screen",
        "light": "soft diffused light through lace curtains, fire glow from hearth, wall sconces amber",
        "camera_positions": {
            "wide_master": (
                "Camera at drawing room doorway looking INWARD. Full room depth: Aubusson rug on "
                "polished wood floor stretching to far wall fireplace, chaise longue and settee "
                "arranged center-frame, piano in far corner, tall sash windows with velvet drapes "
                "on left wall, ornate marble fireplace dominating far wall, chandelier overhead"
            ),
            "interior_atmosphere": (
                "Camera beside the marble fireplace looking ACROSS the room. Fire glow in close "
                "foreground, fire screen detail visible, settee and chaise arranged toward warmth, "
                "damask wallpaper and gilt landscapes on opposite wall, piano in far corner, "
                "wall sconces amber, lace curtains at windows filtering pale daylight"
            ),
            "reverse_angle": (
                "Camera at far bay window looking BACK toward the drawing room door. "
                "Door frame visible at far end framed by the room, fireplace to one side in middle "
                "ground, furniture arranged between camera and entrance, diffused window backlight "
                "casting the room in pale, cool reverse illumination"
            ),
            "insert_detail": (
                "Extreme close-up. Ornate brass fireplace poker or tarnished silver picture frame. "
                "Decorative Victorian metalwork or carved wood surface, aged patina, "
                "cool grey or warm amber light catching surface texture, background blurred to "
                "warm hearth shapes, shallow depth of field"
            ),
        },
    },
    "bedroom": {
        "architecture": "Victorian master bedroom, high ceiling with crown molding",
        "walls": "deep burgundy wallpaper, heavy oak wardrobe, vanity table with triple mirror",
        "floor": "dark wood with thick Persian carpet, bed on raised platform",
        "ceiling": "plaster medallion with small chandelier, crown molding with acanthus leaf",
        "fixtures": "four-poster bed with canopy, writing desk, upholstered chair by window, fireplace",
        "light": "muted light through heavy curtains, bedside lamp warm glow, dust in air",
        "camera_positions": {
            "wide_master": (
                "Camera at bedroom doorway looking INWARD. Four-poster bed dominates center-right, "
                "heavy brocade canopy above, Persian carpet on dark wood floor, "
                "heavy oak wardrobe against far wall, vanity table with triple mirror to one side, "
                "curtains half-drawn over tall windows, muted filtered light, intimate domestic scale"
            ),
            "interior_atmosphere": (
                "Camera beside the writing desk looking ACROSS the room toward the window. "
                "Desk in close foreground with personal objects, upholstered chair between desk and window, "
                "pale diffused light filtering through heavy curtains, four-poster bed to one side, "
                "warm bedside lamp pool, burgundy wallpaper, sense of private intimate space"
            ),
            "reverse_angle": (
                "Camera at the window looking BACK toward the bedroom door. "
                "Cool pale window backlight illuminating the scene in reverse, "
                "four-poster bed center-frame silhouetted against window glow, "
                "wardrobe and vanity flanking both sides, doorway visible at far end, "
                "personal objects on surfaces in middle ground"
            ),
            "insert_detail": (
                "Extreme close-up. Silver-backed hairbrush, jewellery box clasp, or folded letter on "
                "dresser surface. Tarnished silver or aged fabric, warm lamplight catching surface, "
                "dust on edges, intimate personal object, shallow depth of field, "
                "dresser surface soft-blurred behind"
            ),
        },
    },
    "kitchen": {
        "architecture": "Victorian service kitchen, lower ceiling, utilitarian",
        "walls": "whitewashed brick walls with open shelving, copper pots hanging from ceiling rack",
        "floor": "flagstone floor, heavy pine work table in center, cast iron range against wall",
        "ceiling": "exposed beams with drying herb bundles, single pendant gas light",
        "fixtures": "butler's pantry doorway, Welsh dresser with china, deep Belfast sink, meat safe",
        "light": "harsh morning light through small high windows, warm range glow, practical overhead",
        "camera_positions": {
            "wide_master": (
                "Camera at kitchen service entrance looking INWARD. Full kitchen depth: "
                "flagstone floor receding to cast iron range at far wall, central pine work table "
                "mid-frame, copper pots hanging overhead from ceiling rack, whitewashed brick walls "
                "on both sides with open shelving, small high windows on side wall admitting sharp light"
            ),
            "interior_atmosphere": (
                "Camera beside the cast iron range looking ACROSS the kitchen. "
                "Range in close foreground, heavy iron surface and warming door detail, "
                "copper pots on hooks overhead, central work table with food preparation, "
                "whitewashed brick far wall, Welsh dresser with china stacked, "
                "warm range glow mixing with harsh window light"
            ),
            "reverse_angle": (
                "Camera at the range looking BACK toward the service entrance door. "
                "Heavy wooden service door at far end, worn stone threshold, "
                "pine work table in middle ground between camera and door, "
                "shelving and hanging utensils on side walls, cool exterior light from doorway gap"
            ),
            "insert_detail": (
                "Extreme close-up. Hammered copper cooking pot surface or cast iron range door handle. "
                "Heavy patina of age and use, riveted seams, worn surface, "
                "warm amber light catching copper or cool grey on cast iron, "
                "background blurred to warm kitchen shapes, shallow depth of field"
            ),
        },
    },
    "staircase": {
        "architecture": "Victorian grand staircase, sweeping curve from foyer to upper landing",
        "walls": "stairwell lined with oil portraits in gilded frames, dark wood paneling below",
        "floor": "worn carpet runner on dark wood treads, brass stair rods, scuffed landing",
        "ceiling": "domed skylight at top (dirty, filtered light), plaster molding spiraling up",
        "fixtures": "carved newel post with gas lamp (unlit), landing window seat, hall table",
        "light": "filtered skylight from above, portrait frames catching light, deep shadows below",
        "camera_positions": {
            "wide_master": (
                "Camera at staircase foot looking UPWARD. Sweeping curve of dark mahogany banister "
                "rising from newel post at camera level up and away, worn carpet runner on treads, "
                "brass stair rods on each step, portrait frames ascending the wall on the right, "
                "domed skylight at top filtering pale light down into the well, deep shadow in bends"
            ),
            "interior_atmosphere": (
                "Camera at mid-landing looking along the staircase. Banister rail fills foreground "
                "horizontally, treads ascending above and descending below the landing, portrait frames "
                "at eye level on the wall, filtered skylight from above, shadows pooling in the lower "
                "well, scale and height of the staircase visible in both directions"
            ),
            "reverse_angle": (
                "Camera at upper landing looking DOWN the staircase. Staircase descends away into "
                "the foyer below, banister railing perspective lines converging downward, "
                "portraits descending the wall on the left, foyer marble floor visible at the bottom, "
                "chandelier of the foyer visible below, sense of height and descent"
            ),
            "insert_detail": (
                "Extreme close-up. Dark mahogany banister rail or carved newel post cap. "
                "Wood grain and surface polish worn in grip area, warm light catching the curve, "
                "shallow depth of field, staircase soft-blurred behind, "
                "rich dark wood texture, age and use visible in the surface"
            ),
        },
    },
    "exterior": {
        "architecture": "Victorian Gothic estate exterior, grey stone, peaked gables, climbing ivy",
        "walls": "weathered grey limestone facade, leaded glass windows, iron railings",
        "floor": "gravel drive, stone front steps with iron boot scraper, mossy flagstone path",
        "ceiling": "open sky, slate roof tiles, decorative chimney pots, copper guttering (green patina)",
        "fixtures": "wrought-iron gate, stone pillars with urns, gas lamp post (unlit), front porch columns",
        "light": "overcast sky, grey diffused light, morning mist on grounds, damp stone surfaces",
        "camera_positions": {
            "wide_master": (
                "Camera at iron front gates looking TOWARD the house. Long gravel drive receding to "
                "stone mansion facade, overgrown grounds on both sides, ivy-draped peaked gables "
                "against pale sky, one upper window with amber glow, mist on the grounds, "
                "gate ironwork in close foreground, full estate depth visible"
            ),
            "interior_atmosphere": (
                "Camera on gravel forecourt looking at the front facade. Stone facade filling frame, "
                "front door at center with steps and boot scraper, leaded glass windows on both floors, "
                "gas lamp post flanking entrance, ivy colonising the stonework, overcast sky above, "
                "damp stone texture and moss on steps, closer and more imposing than the gate view"
            ),
            "reverse_angle": (
                "Camera at the front door looking BACK toward the iron gates and the road. "
                "Long gravel drive receding toward distant gates, overgrown grounds spreading wide, "
                "stone pillars with urns flanking the drive near the house, trees at boundary, "
                "the world outside visible from the threshold, cool exterior light"
            ),
            "insert_detail": (
                "Extreme close-up. Iron gate hinge, stone step surface with moss, or estate wall texture. "
                "Weathered grey limestone or rusted iron, lichen and age, cool diffused exterior light, "
                "shallow depth of field, background blurred to grey-green garden shapes"
            ),
        },
    },
    "cemetery": {
        "architecture": "Victorian cemetery, stone wall boundary, gothic iron gate",
        "walls": "moss-covered stone wall, mature yew trees, ivy-covered angel statuary",
        "floor": "uneven grass between weathered headstones, gravel path, fallen leaves",
        "ceiling": "open sky through bare branches, crows circling, grey overcast",
        "fixtures": "granite headstones with worn inscriptions, iron grave railings, stone bench",
        "light": "flat grey light, fog at ground level, damp surfaces reflecting pale sky",
        "camera_positions": {
            "wide_master": (
                "Camera at cemetery entrance gate looking INWARD. Gothic iron gate in close foreground, "
                "gravel path receding between headstones into depth, yew trees on both sides, "
                "angel statuary visible mid-ground, fog at ground level among graves, "
                "grey overcast sky above, full cemetery depth, all in deep focus"
            ),
            "interior_atmosphere": (
                "Camera among the headstones looking across the cemetery. Granite headstones in "
                "middle ground, worn inscriptions, iron grave railings between plots, "
                "moss and lichen on stone surfaces, yew branches framing above, "
                "fog curling at ground level, flat grey light, still and airless atmosphere"
            ),
            "reverse_angle": (
                "Camera at the far end of the cemetery looking BACK toward the entrance gate. "
                "Iron entrance gate visible at far distance, gravel path leading away, "
                "headstones receding toward gate, stone boundary wall on left, "
                "the outside world glimpsed through the far gate, enclosed and isolated view"
            ),
            "insert_detail": (
                "Extreme close-up. Granite headstone surface, worn inscription letters, moss filling "
                "carved letters, lichen on stone surface, rainwater in carved grooves, "
                "flat grey light, no warmth, cold stone texture, shallow depth of field"
            ),
        },
    },
}


# ═══════════════════════════════════════════════════════════════
# CAMERA POSITION CONSTANTS — used to look up per-position DNA
# ═══════════════════════════════════════════════════════════════

# Maps shot suffixes and shot types to canonical camera_positions keys
_SHOT_TO_CAMERA_POS = {
    # E-shot suffixes
    "_E01": "wide_master",
    "_E02": "interior_atmosphere",
    "_E03": "insert_detail",
    # shot_type values
    "establishing": "wide_master",
    "wide": "wide_master",
    "exterior": "wide_master",
    "interior_atmosphere": "interior_atmosphere",
    "medium": "interior_atmosphere",
    "two_shot": "interior_atmosphere",
    "over_the_shoulder": "interior_atmosphere",
    "ots": "interior_atmosphere",
    "ots_a": "interior_atmosphere",
    "ots_b": "reverse_angle",
    "close_up": "insert_detail",
    "ecu": "insert_detail",
    "insert": "insert_detail",
    "detail": "insert_detail",
    "reaction": "insert_detail",
}


def get_shot_camera_position(shot: Dict) -> str:
    """
    Determine the canonical camera position (wide_master / interior_atmosphere /
    reverse_angle / insert_detail) for a shot based on its shot_id suffix and
    shot_type field.

    Returns one of: "wide_master", "interior_atmosphere", "reverse_angle",
                    "insert_detail", or "" (unknown — use generic DNA).
    """
    sid = shot.get("shot_id", "")
    shot_type = (shot.get("shot_type") or "").lower()

    # E-shot suffix takes priority
    for suffix, pos in _SHOT_TO_CAMERA_POS.items():
        if suffix.startswith("_E") and sid.endswith(suffix):
            return pos

    # Reverse angle: shot marked with _is_reverse_angle or "reverse" in shot_type/description
    desc = (shot.get("description") or "").lower()
    if "_is_reverse_angle" in shot or "reverse" in shot_type or "reverse angle" in desc:
        return "reverse_angle"

    # shot_type lookup
    for st_key, pos in _SHOT_TO_CAMERA_POS.items():
        if not st_key.startswith("_E") and (st_key in shot_type or shot_type.startswith(st_key)):
            return pos

    return ""


def get_positional_dna(room_type: str, camera_position: str) -> str:
    """
    Return the camera-position-specific DNA description for a given room type and
    camera position.

    Args:
        room_type:       One of the ROOM_DNA_TEMPLATES keys (e.g. "library", "foyer")
        camera_position: One of "wide_master", "interior_atmosphere",
                         "reverse_angle", "insert_detail"

    Returns:
        A natural-language description of what the camera SEES from that position,
        suitable for injection as [ROOM DNA: ...] into a nano_prompt.
        Falls back to the flat "architecture" field if no per-position entry exists.
    """
    template = ROOM_DNA_TEMPLATES.get(room_type, ROOM_DNA_TEMPLATES["foyer"])
    positions = template.get("camera_positions", {})
    if camera_position and camera_position in positions:
        return positions[camera_position]
    # Graceful fallback: build from flat fields as before
    parts = [template.get("architecture", "")]
    if room_type == "foyer":
        parts.append(template.get("staircase", ""))
    parts.append(template.get("walls", ""))
    return ". ".join(p for p in parts if p)


def detect_room_type(location: str) -> str:
    """Detect room type from story bible location string."""
    loc = location.lower()
    if any(kw in loc for kw in ["cemetery", "burial", "graveyard"]):
        return "cemetery"
    if any(kw in loc for kw in ["library", "bookshelf"]):
        return "library"
    if any(kw in loc for kw in ["study", "office"]):
        return "library"  # study uses library template
    if any(kw in loc for kw in ["bedroom", "bed", "chamber"]):
        return "bedroom"
    if any(kw in loc for kw in ["kitchen", "pantry", "scullery"]):
        return "kitchen"
    if any(kw in loc for kw in ["drawing room", "sitting room", "parlor", "parlour"]):
        return "drawing_room"
    if any(kw in loc for kw in ["garden", "exterior", "outside", "driveway", "front drive"]):
        return "exterior"
    if any(kw in loc for kw in ["staircase", "landing"]):
        return "staircase"
    if any(kw in loc for kw in ["foyer", "entrance", "grand hall", "vestibule", "hallway", "estate"]):
        return "foyer"
    return "foyer"  # default


def build_scene_dna(
    scene: Dict,
    max_chars: int = 400
) -> str:
    """
    Build a locked architectural DNA string for a scene.

    Args:
        scene: Story bible scene dict with location, atmosphere, beats
        max_chars: Maximum character length for the DNA string

    Returns:
        A string like "[ROOM DNA: dark mahogany staircase with carved balusters, ...]"
        that should be appended to every shot's nano_prompt in this scene.
    """
    location = scene.get("location", "")
    atmosphere = scene.get("atmosphere", "")
    room_type = detect_room_type(location)
    template = ROOM_DNA_TEMPLATES.get(room_type, ROOM_DNA_TEMPLATES["foyer"])

    # Extract the most visually distinctive elements — ALL key features
    # More detail = more consistency. FAL needs explicit material/color/design.
    dna_parts = []

    dna_parts.append(template["architecture"])
    if room_type == "foyer" and "staircase" in template:
        dna_parts.append(template["staircase"])
    dna_parts.append(template["walls"])
    if "floor" in template:
        dna_parts.append(template["floor"])
    if "ceiling" in template:
        dna_parts.append(template["ceiling"])
    if "fixtures" in template:
        dna_parts.append(template["fixtures"])

    # Add atmosphere-derived lighting
    if atmosphere:
        # Extract light-related words from atmosphere
        atmo_light = []
        for word in ["dust", "morning", "stained glass", "golden", "amber",
                      "warm", "cold", "harsh", "soft", "filtered", "dim",
                      "candlelight", "firelight", "lamplight", "overcast"]:
            if word in atmosphere.lower():
                atmo_light.append(word)
        if atmo_light:
            dna_parts.append(f"lighting: {', '.join(atmo_light[:3])}")
    else:
        dna_parts.append(template.get("light", ""))

    # Combine and trim to max_chars
    dna_raw = ". ".join(dna_parts)
    if len(dna_raw) > max_chars:
        # Trim to last complete sentence/phrase within limit
        dna_raw = dna_raw[:max_chars].rsplit(", ", 1)[0]

    return f"[ROOM DNA: {dna_raw}]"


def build_scene_lighting_rig(scene: Dict) -> str:
    """
    V27.1.5: Build a LOCKED lighting description for the scene.
    This prevents lighting from changing between shots.

    Returns a string like "[LIGHTING RIG: morning light through stained glass, ...]"
    """
    atmosphere = scene.get("atmosphere", "")
    time_of_day = scene.get("time_of_day", "DAY").upper()
    room_type = detect_room_type(scene.get("location", ""))
    template = ROOM_DNA_TEMPLATES.get(room_type, ROOM_DNA_TEMPLATES["foyer"])

    # Base lighting from template
    base_light = template.get("light", "natural light")

    # Time-of-day modifiers
    time_mods = {
        "MORNING": "warm morning light, long shadows, golden hour warmth entering from east",
        "AFTERNOON": "bright afternoon light, shorter shadows, even illumination",
        "EVENING": "warm amber evening light, deep shadows, golden tones fading",
        "NIGHT": "artificial interior light, deep shadows, warm pools of lamplight, darkness beyond windows",
        "DAY": "daylight through windows, balanced illumination",
        "DUSK": "purple-orange dusk light, long shadows, warm tones mixing with cool",
        "DAWN": "pale blue-pink dawn light, soft shadows, cool tones warming",
    }
    time_light = time_mods.get(time_of_day, time_mods["DAY"])

    # Combine
    parts = [base_light]
    if atmosphere:
        parts.append(atmosphere)
    parts.append(time_light)

    rig = ". ".join(parts)
    if len(rig) > 150:
        rig = rig[:150].rsplit(", ", 1)[0]

    return f"[LIGHTING RIG: {rig}]"


def inject_scene_dna(
    shots: List[Dict],
    scene: Dict,
    scene_id: str
) -> List[Dict]:
    """
    Inject scene visual DNA into all shots for a given scene.

    V32.0: Uses camera-position-specific DNA per shot so wide_master, interior_atmosphere,
    reverse_angle, and insert_detail shots each get a description matching their actual
    camera vantage point — not the same generic room description for every shot.

    E01 → wide_master DNA (camera looking inward from doorway)
    E02 → interior_atmosphere DNA (camera inside looking at a feature)
    E03 → insert_detail DNA (extreme close-up of a threshold object)
    M-shots: position inferred from shot_type

    Modifies shots IN PLACE by appending DNA to nano_prompt.
    Also injects lighting rig.
    Idempotent: checks for existing [ROOM DNA:] marker before injecting.

    Returns the modified shots list.
    """
    location = scene.get("location", "")
    room_type = detect_room_type(location)
    generic_dna = build_scene_dna(scene)      # fallback for unknown positions
    lighting = build_scene_lighting_rig(scene)

    injected_count = 0
    for shot in shots:
        sid = shot.get("shot_id", "")
        if not sid.startswith(f"{scene_id}_"):
            continue

        nano = shot.get("nano_prompt", "") or ""

        # Idempotent: don't double-inject
        if "[ROOM DNA:" in nano:
            continue

        # Determine which camera position this shot represents
        cam_pos = get_shot_camera_position(shot)
        if cam_pos:
            pos_desc = get_positional_dna(room_type, cam_pos)
            dna = f"[ROOM DNA: {pos_desc}]"
        else:
            dna = generic_dna   # fallback for unrecognised shot types

        # Append positional DNA and lighting rig to nano_prompt
        shot["nano_prompt"] = f"{nano.rstrip('. ')}. {dna} {lighting}"
        shot["_scene_visual_dna"] = dna
        shot["_scene_lighting_rig"] = lighting
        shot["_camera_position"] = cam_pos or "generic"
        injected_count += 1

    return shots


def get_focal_length_enforcement(shot_type: str) -> str:
    """
    V27.1.5: Return apparent-size-at-focal-length description for the shot type.

    THE PROBLEM: Prompts say "85mm f/1.4" but FAL ignores focal length text.
    THE FIX: Describe the VISUAL EFFECT of the focal length, not the number.

    Returns a string like "tight framing: face fills 80% of frame, background compressed and blurred"
    """
    shot_type = (shot_type or "").lower()

    if "close" in shot_type or "ecu" in shot_type:
        return (
            "TIGHT FRAMING: face and upper chest FILL the entire frame, "
            "background is a smooth wash of color with zero detail visible, "
            "extremely shallow depth of field, only eyes and lips in sharp focus, "
            "background compressed flat and completely blurred"
        )
    elif "medium_close" in shot_type or "mcU" in shot_type.lower():
        return (
            "MEDIUM-TIGHT FRAMING: head and shoulders fill frame, "
            "arms partially visible, background soft with vague architectural shapes only, "
            "shallow depth of field, face in sharp focus, background 70% blurred"
        )
    elif "medium" in shot_type:
        return (
            "MEDIUM FRAMING: waist-up visible, room context visible but secondary, "
            "moderate depth of field, character sharp, background partially soft"
        )
    elif "two_shot" in shot_type:
        return (
            "TWO-SHOT FRAMING: both characters waist-up, facing each other, "
            "room visible between and behind them, moderate depth of field"
        )
    elif "over_the_shoulder" in shot_type or "ots" in shot_type:
        return (
            "OTS FRAMING: foreground shoulder/head soft focus edge of frame, "
            "background character sharp focus, room visible behind, moderate DOF"
        )
    elif "wide" in shot_type or "establishing" in shot_type:
        return (
            "WIDE FRAMING: full room geography visible, deep depth of field, "
            "all architectural features sharp and detailed, characters small in frame"
        )
    else:
        return ""


def inject_focal_enforcement(shots: List[Dict], scene_id: str) -> List[Dict]:
    """
    Inject apparent-size-at-focal-length descriptions into all shots.
    Modifies nano_prompt IN PLACE. Idempotent.
    """
    for shot in shots:
        sid = shot.get("shot_id", "")
        if not sid.startswith(f"{scene_id}_"):
            continue

        nano = shot.get("nano_prompt", "") or ""
        if "[TIGHT FRAMING:" in nano or "[MEDIUM" in nano or "[WIDE FRAMING:" in nano or "[OTS FRAMING:" in nano or "[TWO-SHOT" in nano:
            continue  # Already injected

        shot_type = (shot.get("shot_type") or "").lower()
        focal = get_focal_length_enforcement(shot_type)
        if focal:
            shot["nano_prompt"] = f"{nano.rstrip('. ')}. [{focal}]"
            shot["_focal_enforcement"] = focal

    return shots


# ═══════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    import os

    project = "pipeline_outputs/victorian_shadows_ep1"
    sb_path = os.path.join(project, "story_bible.json")

    if os.path.exists(sb_path):
        sb = json.load(open(sb_path))
        print("=== SCENE VISUAL DNA FOR ALL SCENES ===\n")
        for scene in sb.get("scenes", []):
            sid = str(scene.get("scene_id", ""))
            loc = scene.get("location", "")
            room = detect_room_type(loc)
            dna = build_scene_dna(scene)
            lighting = build_scene_lighting_rig(scene)
            print(f"Scene {sid}: {loc}")
            print(f"  Room type: {room}")
            print(f"  DNA: {dna}")
            print(f"  Lighting: {lighting}")
            print()
    else:
        print("Story bible not found, running unit tests only")

    # Unit test: foyer DNA
    test_scene = {
        "location": "HARGROVE ESTATE - GRAND FOYER",
        "atmosphere": "dust-filtered morning light, faded grandeur",
        "time_of_day": "MORNING",
    }
    dna = build_scene_dna(test_scene)
    assert "[ROOM DNA:" in dna
    assert "staircase" in dna.lower() or "mahogany" in dna.lower()
    print(f"\n✅ Foyer DNA: {dna}")

    # Unit test: library DNA
    test_lib = {
        "location": "HARGROVE ESTATE - LIBRARY",
        "atmosphere": "warm amber lamplight",
        "time_of_day": "MORNING",
    }
    dna_lib = build_scene_dna(test_lib)
    assert "library" in dna_lib.lower() or "bookshel" in dna_lib.lower()
    print(f"✅ Library DNA: {dna_lib}")

    # Unit test: focal enforcement
    focal_close = get_focal_length_enforcement("close_up")
    assert "face" in focal_close.lower() and "fill" in focal_close.lower()
    print(f"✅ Close-up focal: {focal_close[:80]}...")

    focal_wide = get_focal_length_enforcement("establishing")
    assert "full room" in focal_wide.lower()
    print(f"✅ Wide focal: {focal_wide[:80]}...")

    print("\n✅ All scene visual DNA tests pass")
