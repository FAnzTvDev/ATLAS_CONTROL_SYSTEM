#!/usr/bin/env python3
"""
B-ROLL & INSERT SHOT GENERATOR — V21
======================================
Generates scene-matched B-roll shots that inherit the scene's aesthetic
(color grade, lighting, atmosphere) without fighting the camera system.

Design principle: B-roll is INDEPENDENT — it never chains. It gets its
own nano-banana generation with scene-matched color grade and atmosphere
keywords, but NO character refs (it's environmental/detail footage).

Usage:
    from tools.broll_generator import generate_broll, BROLL_PRESETS

    # Generate a cityscape B-roll for Scene 003
    shot = generate_broll("003", "cityscape", project_path, cast_map={})

    # Get all presets matching a scene
    presets = get_scene_broll_presets("001")
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("atlas.broll_generator")


# ============================================================
# B-ROLL PRESETS — Categorized by visual type
# Each preset has a base prompt, suggested duration, and
# compatible scene types (interior/exterior/any)
# ============================================================

BROLL_PRESETS = {
    # ── CITYSCAPES & EXTERIORS ──
    "cityscape_dawn": {
        "name": "Cityscape at Dawn",
        "base_prompt": "Cinematic establishing wide shot, city skyline at dawn, first light breaking over buildings, muted warm tones, atmospheric haze, slow dolly forward",
        "duration": 4,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "slow dolly forward, subtle parallax between foreground and background buildings",
        "tags": ["city", "dawn", "establishing", "skyline"],
    },
    "cityscape_night": {
        "name": "City at Night",
        "base_prompt": "Cinematic wide shot, city lights at night, reflections on wet streets, moody urban atmosphere, shallow depth of field on foreground lights",
        "duration": 4,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "slow pan across city lights, gentle camera drift",
        "tags": ["city", "night", "urban", "moody"],
    },
    "coastal_road": {
        "name": "Coastal Road",
        "base_prompt": "Cinematic aerial tracking shot, winding coastal road along cliffs, overcast sky, muted greens and greys, crashing waves below, vehicle moving along road",
        "duration": 5,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "tracking forward along road, gentle camera tilt following the curve",
        "tags": ["coast", "road", "journey", "travel"],
    },
    "rain_window": {
        "name": "Rain on Window",
        "base_prompt": "Extreme close-up, raindrops sliding down glass window, blurred city lights behind, melancholic atmosphere, shallow depth of field",
        "duration": 3,
        "shot_type": "detail",
        "context": "any",
        "motion": "static camera, raindrops moving naturally down glass",
        "tags": ["rain", "window", "melancholy", "detail"],
    },

    # ── INTERIOR DETAILS ──
    "candles_flickering": {
        "name": "Flickering Candles",
        "base_prompt": "Close-up detail shot, candle flames flickering in darkness, warm amber light casting dancing shadows on stone walls, gothic atmosphere",
        "duration": 3,
        "shot_type": "detail",
        "context": "interior",
        "motion": "static camera, flames flicker naturally, shadows dance on walls",
        "tags": ["candles", "gothic", "ritual", "darkness"],
    },
    "old_documents": {
        "name": "Old Documents",
        "base_prompt": "Close-up insert shot, aged parchment documents spread on dark wooden desk, handwritten text visible, wax seal, warm lamplight",
        "duration": 3,
        "shot_type": "insert",
        "context": "interior",
        "motion": "slow dolly in toward documents, focus shifts from seal to text",
        "tags": ["documents", "letter", "desk", "legal"],
    },
    "clock_ticking": {
        "name": "Clock Detail",
        "base_prompt": "Extreme close-up, antique clock face, second hand moving, tarnished brass, ticking audible, time passing motif",
        "duration": 3,
        "shot_type": "detail",
        "context": "interior",
        "motion": "static close-up, second hand ticking forward",
        "tags": ["clock", "time", "suspense", "detail"],
    },
    "empty_hallway": {
        "name": "Empty Hallway",
        "base_prompt": "Wide shot, long empty hallway in old manor, dim lighting, shadows along walls, dust motes in light beam, eerie stillness",
        "duration": 4,
        "shot_type": "establishing",
        "context": "interior",
        "motion": "slow dolly forward through hallway, steady movement into depth",
        "tags": ["manor", "hallway", "gothic", "empty"],
    },

    # ── NATURE & ATMOSPHERE ──
    "fog_rolling": {
        "name": "Rolling Fog",
        "base_prompt": "Wide atmospheric shot, thick fog rolling across moor landscape, low grey sky, bare trees silhouetted, haunting isolation",
        "duration": 5,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "static wide shot, fog drifts slowly across frame left to right",
        "tags": ["fog", "moor", "gothic", "nature", "isolation"],
    },
    "waves_crashing": {
        "name": "Waves Crashing",
        "base_prompt": "Medium shot, waves crashing against rocky coastline, overcast sky, spray and mist, raw power of sea, contemplative mood",
        "duration": 4,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "static camera on tripod, waves crash naturally, spray rises",
        "tags": ["waves", "coast", "sea", "power", "nature"],
    },
    "sunset_silhouette": {
        "name": "Sunset Silhouette",
        "base_prompt": "Wide cinematic shot, figure silhouetted against sunset horizon, warm golden-orange sky, long shadows, contemplative solitude",
        "duration": 4,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "slow zoom out revealing more landscape, figure stays small in frame",
        "tags": ["sunset", "silhouette", "golden", "solitude"],
    },

    # ── TRANSITIONAL ──
    "bus_journey": {
        "name": "Bus Journey",
        "base_prompt": "Medium shot through bus window, passing countryside landscape, rain streaks on glass, blurred greenery rushing past, contemplative travel",
        "duration": 4,
        "shot_type": "establishing",
        "context": "interior",
        "motion": "landscape scrolls past window, gentle bus vibration, rain streaks on glass",
        "tags": ["bus", "journey", "travel", "window", "countryside"],
    },
    "driving_pov": {
        "name": "Driving POV",
        "base_prompt": "POV through car windshield, winding country road ahead, overcast sky, hedgerows and stone walls passing, steady forward movement",
        "duration": 4,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "steady forward movement, road curves gently, landscape unfolds",
        "tags": ["driving", "road", "pov", "journey"],
    },
    "train_passing": {
        "name": "Train Passing",
        "base_prompt": "Wide shot, train passing through countryside, long exposure motion blur, overcast sky, fields of green, industrial journey",
        "duration": 3,
        "shot_type": "establishing",
        "context": "exterior",
        "motion": "train moves across frame left to right, slight camera pan to follow",
        "tags": ["train", "journey", "passing", "landscape"],
    },

    # ── MOOD/TEXTURE ──
    "dust_motes": {
        "name": "Dust Motes in Light",
        "base_prompt": "Detail shot, dust motes floating in single beam of light through window, dark room beyond, particles catch light, ethereal atmosphere",
        "duration": 3,
        "shot_type": "detail",
        "context": "interior",
        "motion": "static camera, dust particles drift and swirl naturally in light beam",
        "tags": ["dust", "light", "atmospheric", "ethereal"],
    },
    "hands_detail": {
        "name": "Hands Close-up",
        "base_prompt": "Extreme close-up, aged hands resting on fabric, visible texture of skin and veins, soft side lighting, intimate human detail",
        "duration": 3,
        "shot_type": "insert",
        "context": "any",
        "motion": "static close-up, subtle finger movement, breathing rhythm visible",
        "tags": ["hands", "detail", "human", "intimate"],
    },

    # ── LOCATION-SPECIFIC INSERTS ──
    "office_desk": {
        "name": "Office Desk Detail",
        "base_prompt": "Extreme close-up, polished mahogany desk surface, legal documents and folders neatly stacked, fountain pen, brass desk lamp casting warm pool of light, professional atmosphere",
        "duration": 3,
        "shot_type": "insert",
        "context": "interior",
        "motion": "slow dolly along desk surface, focus shifts between pen and documents",
        "tags": ["office", "desk", "legal", "professional", "detail"],
        "use_location_ref": True,
    },
    "computer_screen": {
        "name": "Computer Screen",
        "base_prompt": "Close-up, computer monitor screen glowing in dim room, reflections on face, text visible on screen, modern workplace atmosphere",
        "duration": 3,
        "shot_type": "insert",
        "context": "interior",
        "motion": "static close-up, subtle screen glow flickers, mouse cursor moves",
        "tags": ["computer", "screen", "modern", "office", "detail"],
        "use_location_ref": True,
    },
    "takeaway_food": {
        "name": "Takeaway Food Detail",
        "base_prompt": "Extreme close-up, Chinese takeaway containers on kitchen counter, chopsticks resting on edge, steam rising from food, warm overhead kitchen light, casual domestic atmosphere",
        "duration": 3,
        "shot_type": "insert",
        "context": "interior",
        "motion": "slow dolly in, steam rises naturally, warm light catches moisture",
        "tags": ["food", "apartment", "domestic", "detail", "chinese"],
        "use_location_ref": True,
    },
    "coffee_mug": {
        "name": "Coffee Mug Detail",
        "base_prompt": "Extreme close-up, coffee mug on worn table surface, steam rising, morning light catching liquid surface, stained ring on table, domestic melancholy",
        "duration": 3,
        "shot_type": "insert",
        "context": "interior",
        "motion": "static, steam rises gently, subtle light shift",
        "tags": ["coffee", "morning", "domestic", "melancholy", "detail"],
        "use_location_ref": True,
    },
    "phone_ringing": {
        "name": "Phone Ringing",
        "base_prompt": "Close-up, mobile phone vibrating on table surface, screen lighting up with incoming call, reflections on screen, tension building",
        "duration": 3,
        "shot_type": "insert",
        "context": "any",
        "motion": "static close-up, phone vibrates and screen pulses with light",
        "tags": ["phone", "call", "tension", "communication"],
        "use_location_ref": True,
    },
    "letter_envelope": {
        "name": "Letter/Envelope Detail",
        "base_prompt": "Extreme close-up, wax-sealed envelope on dark surface, ornate writing, aged paper texture, dramatic side lighting casting long shadows",
        "duration": 3,
        "shot_type": "insert",
        "context": "any",
        "motion": "slow push-in toward wax seal, focus shifts from text to seal",
        "tags": ["letter", "envelope", "mysterious", "seal", "detail"],
        "use_location_ref": True,
    },
    "window_exterior": {
        "name": "View Through Window",
        "base_prompt": "Medium shot from inside looking out window, blurred interior frame edges, exterior scene visible through glass, contemplative composition",
        "duration": 4,
        "shot_type": "establishing",
        "context": "interior",
        "motion": "slow push-in toward window, exterior comes into sharper focus",
        "tags": ["window", "view", "interior", "contemplative"],
        "use_location_ref": True,
    },
    "keys_door": {
        "name": "Keys in Door",
        "base_prompt": "Close-up, hand turning key in old lock, heavy wooden door, metal mechanism clicking, dramatic lighting from behind door",
        "duration": 3,
        "shot_type": "insert",
        "context": "any",
        "motion": "static close-up, key turns, lock clicks, door begins to open slightly",
        "tags": ["keys", "door", "entry", "suspense", "detail"],
    },
    "bookshelf": {
        "name": "Bookshelf Detail",
        "base_prompt": "Slow pan across old bookshelf, leather-bound volumes, dust on spines, warm side lighting catching gold lettering, academic atmosphere",
        "duration": 4,
        "shot_type": "detail",
        "context": "interior",
        "motion": "slow pan left to right across book spines, rack focus between shelves",
        "tags": ["books", "library", "academic", "detail"],
        "use_location_ref": True,
    },
}


# ============================================================
# SCENE-MATCHED AESTHETIC SYSTEM
# Maps scene IDs to their color grade, atmosphere, and
# compatible B-roll presets
# ============================================================

SCENE_AESTHETICS = {
    "001": {
        "color_grade": "crushed blacks, warm amber candlelight 2200K, deep shadows, desaturated cold stone, gothic horror grain",
        "color_negative": "NO teal, NO blue shift, NO green tones, NO bright highlights, NO modern lighting",
        "atmosphere": "gothic ritual chamber, candlelight, stone walls, ancient darkness",
        "compatible_broll": ["candles_flickering", "empty_hallway", "dust_motes", "fog_rolling", "clock_ticking"],
    },
    "002": {
        "color_grade": "cold blue morning light, desaturated urban tones, muted greys and whites, soft window light, melancholic naturalism",
        "color_negative": "NO warm amber, NO saturated colors, NO dramatic candlelight",
        "atmosphere": "modern city apartment, morning light, urban isolation, legal papers",
        "compatible_broll": [
            "cityscape_dawn", "rain_window", "old_documents", "clock_ticking", "hands_detail",
            "takeaway_food", "coffee_mug", "phone_ringing", "letter_envelope", "window_exterior",
            "office_desk", "computer_screen",
        ],
    },
    "003": {
        "color_grade": "overcast natural daylight, muted coastal greens and greys, soft diffused light, gentle desaturation, contemplative atmosphere",
        "color_negative": "NO indoor lighting, NO warm amber, NO dramatic shadows, NO night look",
        "atmosphere": "bus journey, coastal road, countryside, passing landscape, contemplative travel",
        "compatible_broll": [
            "bus_journey", "coastal_road", "waves_crashing", "rain_window", "driving_pov", "fog_rolling",
            "letter_envelope", "phone_ringing", "window_exterior",
        ],
    },
}


def get_scene_broll_presets(scene_id: str) -> List[Dict]:
    """
    Get B-roll presets compatible with a scene's aesthetic.

    Returns list of preset dicts with scene-matched color grade injected.
    """
    sid = scene_id[:3] if scene_id else ""
    aesthetic = SCENE_AESTHETICS.get(sid)

    if not aesthetic:
        # Return all presets for unknown scenes
        return [{"id": k, **v} for k, v in BROLL_PRESETS.items()]

    compatible_ids = aesthetic.get("compatible_broll", [])
    result = []
    for preset_id in compatible_ids:
        preset = BROLL_PRESETS.get(preset_id)
        if preset:
            # Clone and inject scene aesthetic
            p = {"id": preset_id, **preset}
            p["scene_color_grade"] = aesthetic["color_grade"]
            p["scene_color_negative"] = aesthetic["color_negative"]
            p["scene_atmosphere"] = aesthetic["atmosphere"]
            result.append(p)

    return result


def generate_broll_prompt(
    scene_id: str,
    preset_id: str,
    custom_prompt: str = "",
) -> Dict[str, str]:
    """
    Generate a complete B-roll shot prompt that matches the scene aesthetic.

    Returns:
        {
            "nano_prompt": "...",
            "ltx_motion_prompt": "...",
            "shot_type": "...",
            "duration": N,
        }
    """
    sid = scene_id[:3] if scene_id else ""
    preset = BROLL_PRESETS.get(preset_id, {})
    aesthetic = SCENE_AESTHETICS.get(sid, {})

    base = custom_prompt if custom_prompt else preset.get("base_prompt", "Cinematic B-roll shot")
    motion = preset.get("motion", "subtle camera movement")
    color_grade = aesthetic.get("color_grade", "")
    color_neg = aesthetic.get("color_negative", "")

    # Build nano_prompt with scene-matched aesthetic
    nano = f"{base}."
    if color_grade:
        nano += f" Color grade: {color_grade}."
    if color_neg:
        nano += f" {color_neg}."
    nano += " NO grid, NO morphing, NO collage, NO split screen."
    nano += " NO people, NO figures, NO human silhouettes, NO faces, empty scene only."

    # Build LTX motion prompt
    ltx = f"{motion}. Smooth cinematic movement, NO jitter, NO sudden motion."
    ltx += " face stable NO morphing. subtle micro motion."

    return {
        "nano_prompt": nano,
        "ltx_motion_prompt": ltx,
        "shot_type": preset.get("shot_type", "detail"),
        "duration": preset.get("duration", 3),
        "shot_id_suffix": "B",  # B-roll always gets B suffix
        "_broll": True,
        "_broll_preset": preset_id,
        "_no_chain": True,  # B-roll never chains
    }


def generate_broll_shot(
    scene_id: str,
    preset_id: str,
    insert_after_shot_id: str = "",
    custom_prompt: str = "",
    location_ref_path: str = "",
    project_path: str = "",
) -> Dict[str, Any]:
    """
    Generate a complete B-roll shot dict ready to insert into the shot plan.

    Args:
        scene_id: Scene to match aesthetic to
        preset_id: Preset from BROLL_PRESETS
        insert_after_shot_id: Shot to insert after (for ordering)
        custom_prompt: Override base prompt (optional)
        location_ref_path: Path to location reference image (for visual matching)
        project_path: Project path for location master lookup

    Returns:
        Complete shot dict with all required fields
    """
    sid = scene_id[:3] if scene_id else ""
    prompts = generate_broll_prompt(sid, preset_id, custom_prompt)

    # Generate shot ID
    if insert_after_shot_id:
        base_num = insert_after_shot_id.split("_")[-1] if "_" in insert_after_shot_id else "000"
        # Extract number and add B suffix
        try:
            num = int(base_num.replace("A", "").replace("B", "").replace("R", ""))
            shot_id = f"{sid}_{num:03d}B"
        except ValueError:
            shot_id = f"{sid}_099B"
    else:
        shot_id = f"{sid}_099B"

    preset = BROLL_PRESETS.get(preset_id, {})

    # V21: Resolve location reference for presets that benefit from it
    _loc_ref = location_ref_path
    if not _loc_ref and preset.get("use_location_ref") and project_path:
        # Auto-find location master for this scene
        try:
            import os
            loc_dir = os.path.join(project_path, "location_masters")
            if os.path.isdir(loc_dir):
                # Match by scene aesthetic keywords
                aesthetic = SCENE_AESTHETICS.get(sid, {})
                atmos = aesthetic.get("atmosphere", "").lower()
                for loc_file in os.listdir(loc_dir):
                    if loc_file.endswith((".jpg", ".png", ".jpeg")):
                        loc_name = loc_file.rsplit(".", 1)[0].lower().replace("_", " ")
                        # Simple keyword matching
                        if any(kw in loc_name for kw in atmos.split(", ")[:3]):
                            _loc_ref = os.path.join(loc_dir, loc_file)
                            logger.info(f"[BROLL] Auto-matched location ref: {loc_file}")
                            break
        except Exception:
            pass

    shot = {
        "shot_id": shot_id,
        "scene_id": sid,
        "shot_type": prompts["shot_type"],
        "type": prompts["shot_type"],
        "nano_prompt": prompts["nano_prompt"],
        "ltx_motion_prompt": prompts["ltx_motion_prompt"],
        "duration": prompts["duration"],
        "duration_seconds": prompts["duration"],
        "ltx_duration_seconds": prompts["duration"],
        "characters": [],  # B-roll has no characters
        "dialogue_text": "",
        "dialogue": "",
        "location": "",  # Inherit from scene context
        "_broll": True,
        "_broll_preset": preset_id,
        "_broll_name": preset.get("name", preset_id),
        "_no_chain": True,
        "_authority_gate": True,  # Pre-validated
        "_insert_after": insert_after_shot_id,
    }

    # V21: Add location reference for visual consistency
    if _loc_ref:
        shot["location_master_url"] = f"/api/media?path={_loc_ref}"
        shot["_broll_location_ref"] = _loc_ref

    logger.info(
        f"[BROLL] Generated {preset.get('name', preset_id)} for scene {sid}: "
        f"{shot_id} ({prompts['duration']}s, {prompts['shot_type']})"
    )

    return shot


def list_all_presets() -> List[Dict]:
    """Return all B-roll presets for UI display."""
    return [
        {
            "id": k,
            "name": v["name"],
            "duration": v["duration"],
            "shot_type": v["shot_type"],
            "context": v["context"],
            "tags": v["tags"],
            "preview": v["base_prompt"][:100] + "...",
        }
        for k, v in BROLL_PRESETS.items()
    ]


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    import sys

    scene = sys.argv[1] if len(sys.argv) > 1 else "003"
    print(f"\nB-ROLL PRESETS FOR SCENE {scene}")
    print("=" * 60)

    presets = get_scene_broll_presets(scene)
    for p in presets:
        print(f"\n  {p['id']}: {p['name']}")
        print(f"    Duration: {p['duration']}s | Type: {p['shot_type']}")
        print(f"    Tags: {', '.join(p['tags'])}")

    print(f"\n\nSAMPLE GENERATED B-ROLL SHOT:")
    print("=" * 60)
    if presets:
        shot = generate_broll_shot(scene, presets[0]["id"], "003_005")
        print(f"  Shot ID: {shot['shot_id']}")
        print(f"  Type: {shot['shot_type']} | Duration: {shot['duration']}s")
        print(f"  Nano ({len(shot['nano_prompt'])} chars):")
        print(f"    {shot['nano_prompt'][:200]}...")
        print(f"  LTX ({len(shot['ltx_motion_prompt'])} chars):")
        print(f"    {shot['ltx_motion_prompt']}")
