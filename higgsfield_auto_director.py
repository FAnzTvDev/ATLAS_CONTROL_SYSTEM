#!/usr/bin/env python3
"""
HIGGSFIELD AUTO DIRECTOR — Victorian Shadows EP1
================================================
Autonomous movie generation pipeline for Higgsfield AI.
Reads your ATLAS production bible (cast_map + story_bible + shot_plan),
builds optimized prompts, and fires 24-concurrent generations.

USAGE:
  python3 higgsfield_auto_director.py --api-key YOUR_KEY --mode text-to-video
  python3 higgsfield_auto_director.py --api-key YOUR_KEY --mode image-to-video --scene 001
  python3 higgsfield_auto_director.py --mode prompts-only   # just generate prompt bible
  python3 higgsfield_auto_director.py --mode browser-paste  # print prompts for manual paste
"""

import asyncio
import json
import os
import sys
import time
import argparse
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── PATHS ────────────────────────────────────────────────────────────────────
ATLAS_ROOT   = Path(__file__).parent
PROJECT_DIR  = ATLAS_ROOT / "pipeline_outputs" / "victorian_shadows_ep1"
CAST_MAP     = PROJECT_DIR / "cast_map.json"
STORY_BIBLE  = PROJECT_DIR / "story_bible.json"
SHOT_PLAN    = PROJECT_DIR / "shot_plan.json"
OUTPUT_DIR   = PROJECT_DIR / "higgsfield_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── HIGGSFIELD API CONFIG ────────────────────────────────────────────────────
HF_BASE_URL      = "https://platform.higgsfield.ai"
HF_CLOUD_URL     = "https://cloud.higgsfield.ai"

# Application identifiers (Higgsfield SDK endpoint names)
APP_TEXT_TO_VIDEO   = "higgsfield/film"           # Cinema Studio text-to-video
APP_IMAGE_TO_VIDEO  = "higgsfield/film/i2v"       # Image-to-video
APP_TEXT_TO_IMAGE   = "higgsfield/image"          # Text-to-image still
APP_IMAGE_EXTEND    = "higgsfield/film/extend"    # Extend video

MAX_CONCURRENCY = 24    # Your plan's concurrent slots

# ─── VICTORIAN SHADOWS PRODUCTION BIBLE ──────────────────────────────────────
# Compiled from cast_map.json + story_bible.json

CHARACTERS = {
    "ELEANOR VOSS": {
        "age": 34, "role": "lead",
        "appearance": "woman, mid-30s, sharp angular features, auburn hair pulled back in severe bun, piercing grey-green eyes, pale complexion, tailored charcoal blazer over black turtleneck",
        "identity_lock": "[CHARACTER: SHARP-FEATURED woman, AUBURN hair in tight bun, piercing grey-green eyes, PALE skin, tailored CHARCOAL blazer, BLACK turtleneck. NO blonde hair, NO casual clothing.]",
        "negative": "NO blonde hair, NO casual clothing, NO warm smile, NO relaxed posture",
        "ref_path": str(PROJECT_DIR / "character_library_locked" / "ELEANOR_VOSS_CHAR_REFERENCE.jpg"),
        "ref_3q": str(PROJECT_DIR / "character_library_locked" / "ELEANOR_VOSS_three_quarter.jpg"),
        "soul_id_tag": "@Eleanor_Voss",
    },
    "THOMAS BLACKWOOD": {
        "age": 62, "role": "supporting_lead",
        "appearance": "man, early 60s, BRIGHT SILVER-WHITE hair, deep weathered lines on face, weary dark eyes, rumpled navy suit, slightly stooped posture",
        "identity_lock": "[CHARACTER: SILVER-WHITE haired man, 62, weathered grief-lined face, dark weary eyes, RUMPLED NAVY SUIT. NO young face, NO bright clothing.]",
        "negative": "NO young face, NO bright clothing, NO energetic movement",
        "ref_path": str(PROJECT_DIR / "character_library_locked" / "THOMAS_BLACKWOOD_CHAR_REFERENCE.jpg"),
        "ref_3q": str(PROJECT_DIR / "character_library_locked" / "THOMAS_BLACKWOOD_three_quarter.jpg"),
        "soul_id_tag": "@Thomas_Blackwood",
    },
    "NADIA COLE": {
        "age": 28, "role": "supporting_lead",
        "appearance": "young woman, 28, dark brown skin, intelligent brown eyes, natural textured afro hair, jeans, vintage Iron Maiden band t-shirt, open flannel shirt",
        "identity_lock": "[CHARACTER: young woman, DARK BROWN SKIN, natural TEXTURED AFRO hair, intelligent brown eyes, VINTAGE BAND T-SHIRT under open flannel. NO straight hair, NO formal clothing.]",
        "negative": "NO formal clothing, NO straight hair, NO disrespectful handling of objects",
        "ref_path": str(PROJECT_DIR / "character_library_locked" / "NADIA_COLE_CHAR_REFERENCE.jpg"),
        "ref_3q": str(PROJECT_DIR / "character_library_locked" / "NADIA_COLE_three_quarter.jpg"),
        "soul_id_tag": "@Nadia_Cole",
    },
    "RAYMOND CROSS": {
        "age": 45, "role": "antagonist",
        "appearance": "stocky man, 45, THINNING dark hair slicked back, sharp suspicious eyes, expensive black overcoat over burgundy silk shirt, broad threatening shoulders",
        "identity_lock": "[CHARACTER: STOCKY THICK-SET man, thinning dark hair, sharp suspicious eyes, EXPENSIVE BLACK OVERCOAT, burgundy silk shirt. NO friendly smile, NO casual dress.]",
        "negative": "NO friendly smile, NO casual dress, NO sympathetic expression",
        "ref_path": str(PROJECT_DIR / "character_library_locked" / "RAYMOND_CROSS_CHAR_REFERENCE.jpg"),
        "ref_3q": str(PROJECT_DIR / "character_library_locked" / "RAYMOND_CROSS_three_quarter.jpg"),
        "soul_id_tag": "@Raymond_Cross",
    },
    "HARRIET HARGROVE": {
        "age": "60s", "role": "presence",
        "appearance": "stern elderly Victorian woman, aristocratic bearing, iron-grey hair, cold appraising eyes, high-collared Victorian dress, oil painting portrait quality",
        "identity_lock": "[CHARACTER: STERN VICTORIAN woman, iron-grey hair, cold appraising eyes, HIGH-COLLARED Victorian dress, imperious bearing.]",
        "negative": "NO living character, NO modern clothing, NO warm expression",
        "ref_path": str(PROJECT_DIR / "character_library_locked" / "HARRIET_HARGROVE_CHAR_REFERENCE.jpg"),
        "ref_3q": str(PROJECT_DIR / "character_library_locked" / "HARRIET_HARGROVE_three_quarter.jpg"),
        "soul_id_tag": "@Harriet_Hargrove",
    },
}

LOCATIONS = {
    "GRAND FOYER": {
        "dna": "[ROOM DNA: single curved dark mahogany staircase with carved balusters, stone walls with tapestries, massive unlit crystal chandelier above, dust-covered marble floor, Persian carpet, oil portrait of stern Victorian woman above staircase]",
        "lighting": "[LIGHTING RIG: morning light through stained glass windows, fractured colored beams on dusty floor, deep shadows in corners, warm amber and cool blue contrast]",
        "atmosphere": "abandoned Victorian grandeur, dust motes in colored light, eerie stillness",
        "ref_path": str(PROJECT_DIR / "location_masters" / "001_master.jpg"),
        "color": "muted golds, cool slate grey, fractured stained glass colors",
    },
    "LIBRARY": {
        "dna": "[ROOM DNA: floor-to-ceiling mahogany bookshelves, rolling brass ladder on rail, leather-bound volumes, large mahogany desk with scattered papers, tall windows, Persian rug]",
        "lighting": "[LIGHTING RIG: golden afternoon light streaming through tall windows, warm amber pool on desk, deep shadow between shelves, dust motes floating in light beams]",
        "atmosphere": "scholarly sanctuary, accumulated knowledge, afternoon warmth, hidden secrets",
        "ref_path": str(PROJECT_DIR / "location_masters" / "002_master.jpg"),
        "color": "warm golden amber, deep mahogany browns, cream paper",
    },
    "DRAWING ROOM": {
        "dna": "[ROOM DNA: furniture hidden under white dust sheets creating ghostly shapes, Steinway piano in corner, silver candelabras, crystal display cases, marble fireplace unlit, dim light]",
        "lighting": "[LIGHTING RIG: grey overcast light through heavy curtains, dramatic shadows under dust sheets, cold blue-grey atmosphere, fireplace dark]",
        "atmosphere": "ghostly silence, hidden shapes, frozen time, menacing stillness",
        "ref_path": str(PROJECT_DIR / "location_masters" / "003_master.jpg"),
        "color": "cold grey-blue, ghostly white, deep shadow",
    },
    "GARDEN": {
        "dna": "[ROOM DNA: overgrown Victorian garden, dead roses on rusted iron trellises, dry cracked stone fountain, weathered stone bench, overgrown hedgerows, rolling countryside beyond iron gates]",
        "lighting": "[LIGHTING RIG: grey overcast sky, flat cold light, no shadows, dull natural light, dead vegetation texture]",
        "atmosphere": "decay and abandonment, nature reclaiming order, cold outdoor air",
        "ref_path": str(PROJECT_DIR / "location_masters" / "004_master.jpg"),
        "color": "dead browns, grey sky, rust orange, cold green",
    },
    "MASTER BEDROOM": {
        "dna": "[ROOM DNA: heavy velvet curtains drawn, ornate four-poster bed with silk coverings, antique vanity with framed photographs, nightstand with leather journal monogrammed H.H., frozen in time]",
        "lighting": "[LIGHTING RIG: moonlight through velvet curtain gap, single warm lamp on nightstand, deep shadows, intimate and still]",
        "atmosphere": "intimate preserved memory, frozen in the moment of death, personal relics",
        "ref_path": str(PROJECT_DIR / "location_masters" / "005_master.jpg"),
        "color": "deep burgundy velvet, moonlight silver, warm lamp amber",
    },
    "KITCHEN": {
        "dna": "[ROOM DNA: vast Victorian kitchen, copper pots hanging from ceiling racks, large farmhouse table as command post, documents spread across table, stone floors, window overlooking dead garden]",
        "lighting": "[LIGHTING RIG: cold daylight from garden window, practical overhead, documents lit from below by laptop screen glow, utilitarian and investigative]",
        "atmosphere": "investigative command center, practical urgency, cold stone and warm paper",
        "ref_path": str(PROJECT_DIR / "location_masters" / "006_master.jpg"),
        "color": "copper orange, cold stone grey, paper cream, laptop blue",
    },
}

# Scene assignments: which characters appear in which locations
SCENES = [
    {"id": "001", "location": "GRAND FOYER",    "chars": ["ELEANOR VOSS", "THOMAS BLACKWOOD"], "time": "MORNING",   "mood": "tense professional arrival"},
    {"id": "002", "location": "LIBRARY",        "chars": ["NADIA COLE", "THOMAS BLACKWOOD"],  "time": "AFTERNOON", "mood": "discovery and revelation"},
    {"id": "003", "location": "DRAWING ROOM",   "chars": ["ELEANOR VOSS", "RAYMOND CROSS"],   "time": "AFTERNOON", "mood": "confrontational threat"},
    {"id": "004", "location": "GARDEN",         "chars": ["NADIA COLE", "ELEANOR VOSS"],      "time": "OVERCAST",  "mood": "investigative alliance"},
    {"id": "005", "location": "LIBRARY",        "chars": ["ELEANOR VOSS", "THOMAS BLACKWOOD"],"time": "AFTERNOON", "mood": "confession and truth"},
    {"id": "006", "location": "GRAND FOYER",    "chars": ["ELEANOR VOSS", "RAYMOND CROSS"],   "time": "EVENING",   "mood": "final confrontation"},
]

# Shot types with Higgsfield-optimized prompting
SHOT_TYPES = {
    "establishing": {"camera": "WIDE ESTABLISHING SHOT, deep focus, full architecture visible", "duration": 5,  "chars": False},
    "medium":       {"camera": "MEDIUM SHOT, waist-up, room context visible, 50mm lens",        "duration": 8,  "chars": True},
    "close_up":     {"camera": "CLOSE-UP, face fills 80% frame, 85mm, heavy bokeh background",  "duration": 6,  "chars": True},
    "two_shot":     {"camera": "TWO-SHOT, both characters, medium framing, confrontational",     "duration": 10, "chars": True},
    "ots_a":        {"camera": "OVER-THE-SHOULDER, speaker FRAME-RIGHT faces camera, listener shoulder FRAME-LEFT foreground", "duration": 8, "chars": True},
    "ots_b":        {"camera": "OVER-THE-SHOULDER, speaker FRAME-LEFT faces camera, listener shoulder FRAME-RIGHT foreground", "duration": 8, "chars": True},
    "insert":       {"camera": "EXTREME CLOSE-UP insert, detail shot, no characters",            "duration": 4,  "chars": False},
    "reaction":     {"camera": "REACTION SHOT, medium-close, face visible, eyes shift subtly",   "duration": 5,  "chars": True},
}

# Motion styles for Higgsfield Cinema Studio
MOTION_STYLES = {
    "dramatic":    "slow dolly in, deliberate movement",
    "discovery":   "gentle pan right revealing detail",
    "tense":       "locked off, micro-tremor, holding breath",
    "emotional":   "slow push in, face fills frame progressively",
    "establishing":"slow pull back revealing room scale",
    "reaction":    "static, only character motion visible",
}

# ─── PROMPT BUILDER ───────────────────────────────────────────────────────────

def build_higgsfield_prompt(
    shot_type: str,
    location_name: str,
    characters: list[str],
    beat_action: str = "",
    dialogue: str = "",
    mood: str = "",
    motion: str = "dramatic"
) -> dict:
    """Build an optimized Higgsfield prompt from Victorian Shadows production bible."""

    loc   = LOCATIONS.get(location_name, LOCATIONS["GRAND FOYER"])
    stype = SHOT_TYPES.get(shot_type, SHOT_TYPES["medium"])
    chars = [CHARACTERS[c] for c in characters if c in CHARACTERS]

    # ── Camera & Room Foundation
    prompt_parts = [
        stype["camera"] + ".",
        loc["dna"],
        loc["lighting"],
    ]

    # ── Character Identity Blocks (STRONGEST signal to AI)
    for char in chars:
        prompt_parts.append(char["identity_lock"])

    # ── Action / Beat
    if beat_action:
        prompt_parts.append(f"ACTION: {beat_action}.")

    # ── Dialogue marker (V27.1.4d — prevents frozen faces)
    if dialogue:
        if chars:
            char_desc = chars[0]["appearance"].split(",")[0]
            prompt_parts.append(f"[DIALOGUE: {char_desc} speaks: '{dialogue[:80]}'. Mouth moving, jaw motion, natural breath.]")

    # ── Mood & atmosphere
    if mood:
        prompt_parts.append(f"Mood: {mood}.")
    prompt_parts.append(f"Atmosphere: {loc['atmosphere']}.")

    # ── Split anti-morph (V27.1.5 — face lock + body free)
    if chars:
        prompt_parts.append("FACE IDENTITY LOCK: facial structure UNCHANGED, NO face morphing. BODY PERFORMANCE FREE: natural breathing, weight shifts, gestures continue.")

    # ── Empty room guard (V27.5)
    if not chars:
        prompt_parts.append("No people visible, no figures, empty atmospheric space only.")

    # ── Motion
    motion_desc = MOTION_STYLES.get(motion, MOTION_STYLES["dramatic"])
    prompt_parts.append(f"Camera motion: {motion_desc}.")

    # ── Color grade
    prompt_parts.append(f"Color: {loc['color']}. Cinematic, desaturated warmth, film grain.")

    full_prompt = " ".join(prompt_parts)

    # Soul ID tags for web UI (for browser-paste mode)
    soul_tags = " ".join([CHARACTERS[c]["soul_id_tag"] for c in characters if c in CHARACTERS])

    return {
        "prompt": full_prompt,
        "soul_id_tags": soul_tags,
        "negative_prompt": "blurry, distorted, deformed, extra limbs, text overlay, watermark, logo, static, frozen statue, identity drift, face morphing, teleporting characters",
        "duration": stype["duration"],
        "characters": characters,
        "location": location_name,
        "shot_type": shot_type,
    }


def build_scene_shot_list(scene: dict) -> list[dict]:
    """Build the complete shot list for a scene, ready to fire at Higgsfield."""

    loc_name = scene["location"]
    chars    = scene["chars"]
    mood     = scene["mood"]
    shots    = []

    # 1. Establishing (no characters)
    shots.append(build_higgsfield_prompt(
        "establishing", loc_name, [],
        beat_action=f"Empty {loc_name.lower()}, {scene['time'].lower()} light",
        mood=mood, motion="establishing"
    ))

    # 2. Medium shot — first character enters
    if chars:
        shots.append(build_higgsfield_prompt(
            "medium", loc_name, [chars[0]],
            beat_action=f"{chars[0].title()} surveys the room, alert posture",
            mood=mood, motion="dramatic"
        ))

    # 3. Medium shot — second character (if exists)
    if len(chars) > 1:
        shots.append(build_higgsfield_prompt(
            "medium", loc_name, [chars[1]],
            beat_action=f"{chars[1].title()} turns to face {chars[0].lower()}",
            mood=mood, motion="tense"
        ))

    # 4. Two-shot confrontation
    if len(chars) > 1:
        shots.append(build_higgsfield_prompt(
            "two_shot", loc_name, chars,
            beat_action=f"Both face each other, tension between them, confrontational blocking",
            mood=mood, motion="tense"
        ))

    # 5. OTS A — first char speaks
    if len(chars) > 1:
        shots.append(build_higgsfield_prompt(
            "ots_a", loc_name, chars,
            beat_action=f"{chars[0].title()} speaks directly to {chars[1].title()}, intent gaze",
            mood=mood, motion="dramatic"
        ))

    # 6. OTS B — second char responds
    if len(chars) > 1:
        shots.append(build_higgsfield_prompt(
            "ots_b", loc_name, [chars[1], chars[0]],
            beat_action=f"{chars[1].title()} responds, jaw tightens, weight shifts",
            mood=mood, motion="reaction"
        ))

    # 7. Close-up — lead character
    if chars:
        shots.append(build_higgsfield_prompt(
            "close_up", loc_name, [chars[0]],
            beat_action=f"Face fills frame, eyes reveal interior conflict, micro-expression",
            mood=mood, motion="emotional"
        ))

    # 8. Insert — key prop / detail
    shots.append(build_higgsfield_prompt(
        "insert", loc_name, [],
        beat_action=f"Detail insert: key prop or architectural detail in {loc_name.lower()}",
        mood=mood, motion="discovery"
    ))

    return shots


# ─── HIGGSFIELD SDK CLIENT ────────────────────────────────────────────────────

class HiggsFieldDirector:
    """Autonomous Higgsfield generation manager with 24-slot concurrency."""

    def __init__(self, api_key: str):
        self.api_key    = api_key
        self.semaphore  = asyncio.Semaphore(MAX_CONCURRENCY)
        self.results    = []
        self.failed     = []
        self.completed  = 0
        self.total      = 0

        # Try importing SDK
        try:
            from higgsfield_client import AsyncClient, upload_image_async
            self._sdk_available = True
            self._client = AsyncClient(api_key=api_key, base_url=HF_BASE_URL)
            print("✅ Higgsfield SDK: connected")
        except Exception as e:
            self._sdk_available = False
            print(f"⚠️  SDK import issue: {e} — will use direct HTTP")

    async def upload_image(self, image_path: str) -> Optional[str]:
        """Upload a local image and return the CDN URL."""
        if not Path(image_path).exists():
            return None
        try:
            from higgsfield_client import upload_image_async
            result = await upload_image_async(image_path, api_key=self.api_key)
            return result.get("url") or result.get("cdn_url")
        except Exception as e:
            print(f"  ⚠️  Upload failed for {Path(image_path).name}: {e}")
            return None

    async def generate_one(self, job: dict, job_id: str) -> dict:
        """Fire one generation job at Higgsfield, respecting concurrency limit."""
        async with self.semaphore:
            start = time.time()
            print(f"\n🎬 [{job_id}] Generating: {job['shot_type']} — {job['location']}")
            print(f"   Characters: {', '.join(job['characters']) or 'EMPTY (no characters)'}")
            print(f"   Prompt preview: {job['prompt'][:120]}...")

            try:
                # Upload character ref images
                image_urls = []
                for char_name in job["characters"][:2]:  # Max 2 chars
                    char = CHARACTERS.get(char_name)
                    if char and Path(char["ref_path"]).exists():
                        url = await self.upload_image(char["ref_path"])
                        if url:
                            image_urls.append(url)

                # Build API payload for Cinema Studio / text-to-video
                payload = {
                    "prompt": job["prompt"],
                    "negative_prompt": job["negative_prompt"],
                    "duration": job["duration"],
                    "aspect_ratio": "16:9",
                    "motion_speed": "normal",
                }

                if image_urls:
                    payload["reference_images"] = image_urls

                # Submit job
                from higgsfield_client import AsyncClient
                client = AsyncClient(api_key=self.api_key, base_url=HF_BASE_URL)

                result = await client.subscribe(
                    APP_TEXT_TO_VIDEO,
                    payload,
                    on_enqueue=lambda req_id: print(f"   📋 Enqueued: {req_id}"),
                    on_queue_update=lambda s: print(f"   ⏳ Status: {s}"),
                )

                elapsed = time.time() - start
                output_path = OUTPUT_DIR / f"{job_id}_{job['shot_type']}.mp4"

                # Save result
                if result and result.get("video_url"):
                    video_url = result["video_url"]
                    # Download video
                    async with httpx.AsyncClient() as http:
                        resp = await http.get(video_url, timeout=120)
                        if resp.status_code == 200:
                            output_path.write_bytes(resp.content)
                            print(f"   ✅ [{job_id}] Done in {elapsed:.1f}s → {output_path.name}")

                return {
                    "job_id": job_id,
                    "status": "completed",
                    "shot_type": job["shot_type"],
                    "location": job["location"],
                    "characters": job["characters"],
                    "output_path": str(output_path),
                    "result": result,
                    "elapsed_s": elapsed,
                }

            except Exception as e:
                print(f"   ❌ [{job_id}] Failed: {e}")
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                    "shot_type": job["shot_type"],
                    "location": job["location"],
                }

    async def run_scene_batch(self, scene_id: str) -> list[dict]:
        """Run all shots for a scene in parallel (up to 24 concurrent)."""
        scene = next((s for s in SCENES if s["id"] == scene_id), None)
        if not scene:
            print(f"❌ Scene {scene_id} not found. Available: {[s['id'] for s in SCENES]}")
            return []

        shots = build_scene_shot_list(scene)
        self.total = len(shots)
        print(f"\n{'='*60}")
        print(f"🎬 SCENE {scene_id}: {scene['location']}")
        print(f"   Characters: {', '.join(scene['chars'])}")
        print(f"   Shots: {len(shots)} | Concurrency: min({len(shots)}, {MAX_CONCURRENCY})")
        print(f"{'='*60}")

        tasks = []
        for i, shot in enumerate(shots):
            job_id = f"{scene_id}_{i+1:02d}"
            tasks.append(self.generate_one(shot, job_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        clean = []
        for r in results:
            if isinstance(r, Exception):
                clean.append({"status": "exception", "error": str(r)})
            else:
                clean.append(r)

        # Save batch report
        report_path = OUTPUT_DIR / f"scene_{scene_id}_report.json"
        with open(report_path, "w") as f:
            json.dump({
                "scene_id": scene_id,
                "location": scene["location"],
                "generated_at": datetime.utcnow().isoformat(),
                "total_shots": len(shots),
                "results": clean,
            }, f, indent=2)
        print(f"\n📄 Report saved: {report_path}")

        return clean

    async def run_multi_scene(self, scene_ids: list[str]) -> None:
        """Run multiple scenes in parallel batches (3 scenes × 8 shots = 24 concurrent)."""
        print(f"\n{'='*60}")
        print(f"🎬 MULTI-SCENE RUN: Scenes {scene_ids}")
        print(f"   Total scenes: {len(scene_ids)} | Max concurrent: {MAX_CONCURRENCY}")
        print(f"{'='*60}")

        # Build all shot jobs across all scenes
        all_jobs = []
        for scene_id in scene_ids:
            scene = next((s for s in SCENES if s["id"] == scene_id), None)
            if scene:
                shots = build_scene_shot_list(scene)
                for i, shot in enumerate(shots):
                    all_jobs.append((f"{scene_id}_{i+1:02d}", shot))

        print(f"\n📊 Total jobs queued: {len(all_jobs)}")

        # Fire all with semaphore controlling concurrency
        tasks = [self.generate_one(shot, job_id) for job_id, shot in all_jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "completed")
        failed    = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "failed")

        print(f"\n{'='*60}")
        print(f"✅ COMPLETE: {completed}/{len(all_jobs)} succeeded | {failed} failed")
        print(f"{'='*60}")


# ─── BROWSER PASTE MODE ───────────────────────────────────────────────────────

def print_browser_paste_bible(scene_ids: list[str] = None):
    """Print optimized prompts for manual/browser-automated paste into Higgsfield UI."""

    target_scenes = SCENES if not scene_ids else [s for s in SCENES if s["id"] in scene_ids]

    print("\n" + "="*70)
    print("VICTORIAN SHADOWS EP1 — HIGGSFIELD PROMPT BIBLE")
    print("Generated by ATLAS Auto Director | Ready for Cinema Studio 2.5")
    print("="*70)

    for scene in target_scenes:
        shots = build_scene_shot_list(scene)

        print(f"\n{'─'*70}")
        print(f"SCENE {scene['id']}: {scene['location']}")
        print(f"Characters: {', '.join(scene['chars'])}")
        print(f"Time: {scene['time']} | Mood: {scene['mood']}")
        print(f"Total shots: {len(shots)}")
        print(f"{'─'*70}")

        for i, shot in enumerate(shots):
            soul_tags = " ".join([CHARACTERS[c]["soul_id_tag"] for c in shot["characters"] if c in CHARACTERS])

            print(f"\n[SHOT {scene['id']}_{i+1:02d}] {shot['shot_type'].upper()}")
            print(f"  Soul IDs: {soul_tags or 'NONE (establishing/insert)'}")
            print(f"  Duration: {shot['duration']}s")
            print(f"  PROMPT:")
            # Wrap at 80 chars for readability
            words = shot["prompt"].split()
            line = "    "
            for w in words:
                if len(line) + len(w) > 80:
                    print(line)
                    line = "    " + w + " "
                else:
                    line += w + " "
            print(line)
            print(f"  NEGATIVE: {shot['negative_prompt']}")


# ─── PROMPT BIBLE EXPORT ──────────────────────────────────────────────────────

def export_prompt_bible():
    """Export full structured prompt bible as JSON for the UI or external tools."""

    bible = {
        "project": "Victorian Shadows EP1",
        "generated_at": datetime.utcnow().isoformat(),
        "atlas_version": "V31.0",
        "characters": {name: {k: v for k, v in data.items() if k != "ref_path"} for name, data in CHARACTERS.items()},
        "locations": LOCATIONS,
        "scenes": [],
    }

    for scene in SCENES:
        shots = build_scene_shot_list(scene)
        bible["scenes"].append({
            "id": scene["id"],
            "location": scene["location"],
            "characters": scene["chars"],
            "time_of_day": scene["time"],
            "mood": scene["mood"],
            "shots": shots,
        })

    out_path = OUTPUT_DIR / "victorian_shadows_prompt_bible.json"
    with open(out_path, "w") as f:
        json.dump(bible, f, indent=2)

    print(f"\n✅ Prompt bible exported → {out_path}")
    print(f"   {len(SCENES)} scenes × ~8 shots = {sum(len(build_scene_shot_list(s)) for s in SCENES)} total shots")
    return out_path


# ─── CONCURRENCY TEST (no API key needed) ────────────────────────────────────

async def test_concurrency_structure():
    """Test the 24-slot concurrency pipeline structure without spending credits."""
    print("\n🧪 CONCURRENCY STRUCTURE TEST (dry run, no API calls)")
    print(f"   Max concurrent slots: {MAX_CONCURRENCY}")

    # Simulate 3 scenes × 8 shots = 24 parallel slots
    test_scenes = ["001", "002", "003"]
    all_jobs = []

    for scene_id in test_scenes:
        scene = next((s for s in SCENES if s["id"] == scene_id), None)
        if scene:
            shots = build_scene_shot_list(scene)
            for i, shot in enumerate(shots):
                all_jobs.append((f"{scene_id}_{i+1:02d}", shot))

    print(f"\n📊 Jobs that would fire in parallel:")
    for job_id, shot in all_jobs[:24]:  # First 24 fit in one wave
        chars_str = ", ".join(shot["characters"]) or "EMPTY"
        print(f"   {job_id}: {shot['shot_type']:12} | {shot['location']:15} | {chars_str}")

    if len(all_jobs) > 24:
        print(f"   ... and {len(all_jobs) - 24} more in subsequent waves")

    print(f"\n✅ Concurrency test complete — {len(all_jobs)} total jobs across {len(test_scenes)} scenes")


# ─── CLI ENTRYPOINT ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ATLAS Higgsfield Auto Director — Victorian Shadows")
    parser.add_argument("--api-key",  default=os.getenv("HIGGSFIELD_API_KEY", ""), help="Higgsfield API key")
    parser.add_argument("--mode",     default="prompts-only",
                        choices=["text-to-video", "image-to-video", "browser-paste", "prompts-only", "dry-run"],
                        help="Generation mode")
    parser.add_argument("--scene",    default=None, nargs="+", help="Scene IDs to run (e.g. 001 002 003)")
    parser.add_argument("--all-scenes", action="store_true", help="Run all 6 scenes")
    args = parser.parse_args()

    scene_ids = args.scene or (["001", "002", "003", "004", "005", "006"] if args.all_scenes else ["001", "002", "003"])

    print(f"\n{'='*70}")
    print("ATLAS AUTO DIRECTOR — Victorian Shadows EP1")
    print(f"Mode: {args.mode} | Scenes: {scene_ids} | Concurrency: {MAX_CONCURRENCY}")
    print(f"{'='*70}\n")

    if args.mode == "prompts-only":
        export_prompt_bible()
        print_browser_paste_bible(scene_ids)

    elif args.mode == "browser-paste":
        print_browser_paste_bible(scene_ids)

    elif args.mode == "dry-run":
        asyncio.run(test_concurrency_structure())
        export_prompt_bible()

    elif args.mode in ("text-to-video", "image-to-video"):
        if not args.api_key:
            print("❌ --api-key required for generation mode")
            print("   Set HIGGSFIELD_API_KEY env var or pass --api-key YOUR_KEY")
            print("\n💡 TIP: Run --mode prompts-only to generate prompt bible without API key")
            sys.exit(1)

        director = HiggsFieldDirector(args.api_key)
        asyncio.run(director.run_multi_scene(scene_ids))

    print(f"\n✅ Done. Outputs in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
