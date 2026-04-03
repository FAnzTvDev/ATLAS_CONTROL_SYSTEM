"""
FANZ TV Network Video Promo Generator — V2.0 (2026-03-30)
Kling v2 Master Image-to-Video via FAL API
Hard Budget Cap: $10.00
D1-D20 Vision Doctrine Scoring via Gemini for all generated clips.
"""

import os, sys, json, time, requests, tempfile
from pathlib import Path
from datetime import datetime

# Load env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

FAL_KEY = os.environ.get('FAL_KEY', '1c446616-b1de-4964-8979-1b6fbc6e41b0:3ff7a80d36b901d586e6b9732a62acd9')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
os.environ['FAL_KEY'] = FAL_KEY
os.environ['GOOGLE_API_KEY'] = GOOGLE_API_KEY

import fal_client

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BASE = Path('/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM')
ASSETS = BASE / 'platform_assets'
OUTPUT_BASE = ASSETS / 'video_promos'
MANIFEST_PATH = ASSETS / 'generation_manifest_video.json'
DOCTRINE_LOG_PATH = ASSETS / 'video_doctrine_baseline.json'

BUDGET_CAP = 10.00
COST_PER_5S_CLIP = 0.25   # Kling v2 master, 5s image-to-video (confirmed FAL pricing)

# Step 1: Nano generates the start frame (image)
# Step 2: Kling v3/pro animates it into video — using start_image_url from Nano
ENDPOINT_NANO_EDIT = 'fal-ai/nano-banana-pro/edit'            # Step 1: I2I frame gen
ENDPOINT_KLING     = 'fal-ai/kling-video/v3/pro/image-to-video'  # Step 2: video from frame

# ─── PROMO PLAN (12 clips across 6 networks) ──────────────────────────────────
PROMOS = [

    # ── DRAMA ORIGINALS ────────────────────────────────────────────────────────
    {
        "network": "drama_originals",
        "promo_id": "drama_01_victorian_shadows",
        "genre_id": "whodunnit_drama",
        "production_type": "bumper",
        "image": str(BASE / 'pipeline_outputs/victorian_shadows_ep1/first_frames/001_E02.jpg'),
        "fallback_image": str(ASSETS / 'shows/drama_originals/victorian_shadows.jpg'),
        "prompt": "Cinematic slow camera push into ornate Victorian grand foyer. Candlelight flickers. Shadows shift along dark mahogany walls. Dust motes drift in dim light. Ominous atmosphere builds. Mystery drama promo. Victorian estate reveals itself. Eerie and atmospheric.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'drama_originals/victorian_shadows_promo.mp4'),
    },
    {
        "network": "drama_originals",
        "promo_id": "drama_02_crown_heights",
        "genre_id": "drama",
        "production_type": "bumper",
        "image": str(ASSETS / 'shows/drama_originals/crown_heights.jpg'),
        "prompt": "Dramatic cinematic reveal. Show title card glows intensely. Camera slowly zooms in on bold title text. Atmospheric urban drama energy. Tension builds. High contrast lighting. Bold colors. Network promo reveal energy.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'drama_originals/crown_heights_promo.mp4'),
    },

    # ── RUMBLE LEAGUE ──────────────────────────────────────────────────────────
    {
        "network": "rumble_league",
        "promo_id": "rumble_01_dante_iron_crown",
        "genre_id": "action",
        "production_type": "fight_broadcast",
        "image": str(ASSETS / 'rumble/promos/dante_iron_crown_washington_promo.jpg'),
        "prompt": "Fighter intro promo. Powerful male athlete steps forward into dramatic arena spotlight. Crowd erupts. Smoke and spotlights sweep. Fighter raises fists confidently. Intense championship energy. Slow motion power walk toward camera. Combat sports broadcast.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'rumble_league/dante_iron_crown_intro.mp4'),
    },
    {
        "network": "rumble_league",
        "promo_id": "rumble_02_zara_queen_z",
        "genre_id": "action",
        "production_type": "fight_broadcast",
        "image": str(ASSETS / 'rumble/promos/zara_queen_z_okonkwo_promo.jpg'),
        "prompt": "Female champion fighter stands in spotlight. Arena packed with cheering crowd. Championship belt catches the light. Fighter faces camera with fierce intensity. Fight night energy electrifies the air. Dramatic broadcast reveal.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'rumble_league/zara_queen_z_intro.mp4'),
    },

    # ── VYBE MUSIC NETWORK ─────────────────────────────────────────────────────
    {
        "network": "vybe_music",
        "promo_id": "vybe_01_nova_x_performance",
        "genre_id": "music_video",
        "production_type": "music_video",
        "image": str(ASSETS / 'vybe/performances/nova_x_performance.jpg'),
        "prompt": "Music video drop promo. Artist performs under explosive stage lighting. Camera glides dynamically. Beats pulse visually through the frame. Crowd energy surges. Colorful light beams sweep. Bold movement. VYBE Network music culture broadcast.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'vybe_music/nova_x_drop.mp4'),
    },
    {
        "network": "vybe_music",
        "promo_id": "vybe_02_stage_backdrop",
        "genre_id": "music_video",
        "production_type": "bumper",
        "image": str(ASSETS / 'network_identity/vybe_stage_backdrop.jpg'),
        "prompt": "VYBE Music Network sizzle reel. Massive concert stage. Lasers sweep dramatically. LED walls pulse with music visualizers. Crowd raises hands in unison. Camera cranes up to reveal full epic arena scale. Premium music broadcast energy.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'vybe_music/network_sizzle.mp4'),
    },

    # ── FANZ SPORTS & CULTURE ──────────────────────────────────────────────────
    {
        "network": "fanz_tv",
        "promo_id": "fanz_01_studio_set",
        "genre_id": "drama",
        "production_type": "podcast",
        "image": str(ASSETS / 'network_identity/fanz_studio_set.jpg'),
        "prompt": "Sports talk broadcast goes live. Camera pushes into modern studio. LED screens light up with stats and highlights. Dynamic camera reveal across the set. Sports culture broadcast style. High energy network opening. All screens animate simultaneously.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'fanz_tv/studio_broadcast_opener.mp4'),
    },
    {
        "network": "fanz_tv",
        "promo_id": "fanz_02_banner",
        "genre_id": "drama",
        "production_type": "bumper",
        "image": str(ASSETS / 'banners/fanz_sports_&_culture.jpg'),
        "prompt": "FANZ Sports and Culture network banner comes alive. Bold logo text glows. Camera pushes into the brand identity. Sports culture energy radiates. Dramatic reveal with dynamic lighting. Network promo energy builds to climax.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'fanz_tv/network_banner_promo.mp4'),
    },

    # ── AI SPORTS / AIFL ───────────────────────────────────────────────────────
    {
        "network": "ai_sports",
        "promo_id": "aifl_01_championship_field",
        "genre_id": "action",
        "production_type": "sports_game",
        "image": str(ASSETS / 'network_identity/aifl_championship_field.jpg'),
        "prompt": "AIFL Game Day teaser. Championship football field under blazing stadium lights. Camera glides across the field toward end zone. Crowd roars in packed stadium. Game day atmosphere electrifies. Epic sports broadcast reveal. Season is here.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'ai_sports/aifl_gameday_teaser.mp4'),
    },
    {
        "network": "ai_sports",
        "promo_id": "aifl_02_las_vegas_stadium",
        "genre_id": "action",
        "production_type": "sports_game",
        "image": str(ASSETS / 'aifl/stadiums/las_vegas_phantoms_stadium.jpg'),
        "prompt": "Las Vegas Phantoms stadium promo. Spectacular AI football stadium glows under Vegas night sky. Camera sweeps to reveal epic scale. Crowd fills every seat. Scoreboard lights pulse with excitement. AIFL championship season opener.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'ai_sports/las_vegas_stadium_promo.mp4'),
    },

    # ── JOKEBOX TV ─────────────────────────────────────────────────────────────
    {
        "network": "jokebox_tv",
        "promo_id": "jokebox_01_comedy_stage",
        "genre_id": "comedy",
        "production_type": "comedy_special",
        "image": str(ASSETS / 'network_identity/jokebox_comedy_stage.jpg'),
        "prompt": "Comedy show bumper. Spotlight hits center stage. Audience erupts in laughter. Camera swoops to center stage with fun energy. Comedian vibe radiates. Colorful lights pop with joy. Fun and irreverent broadcast tone. JokeBox TV network moment.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'jokebox_tv/comedy_stage_bumper.mp4'),
    },
    {
        "network": "jokebox_tv",
        "promo_id": "jokebox_02_roast_season",
        "genre_id": "comedy",
        "production_type": "bumper",
        "image": str(ASSETS / 'shows/jokebox_tv/jokebox_roast_season.jpg'),
        "prompt": "Roast Season show promo reveal. Show card dramatically illuminates with vibrant energy. Camera zooms in with comedy confidence. Bold colors burst outward. Crowd reaction of laughter. Savage comedy is coming. JokeBox broadcast excitement builds.",
        "duration": "5",
        "output": str(OUTPUT_BASE / 'jokebox_tv/roast_season_promo.mp4'),
    },
]

# ─── VISION DOCTRINE SCORING (D1-D20 via Gemini) ──────────────────────────────
def score_with_doctrine(video_path: str, promo: dict, genre_id: str, production_type: str) -> dict:
    """Score a video clip using Gemini + vision doctrine prompts. Returns D1-D20 dict."""
    if not GOOGLE_API_KEY:
        return {"skipped": True, "reason": "no_google_api_key"}
    if not Path(video_path).exists():
        return {"skipped": True, "reason": "video_file_missing"}

    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
    except ImportError:
        return {"skipped": True, "reason": "google_generativeai_not_installed"}

    # Build the doctrine prompt using vision_doctrine_prompts
    sys.path.insert(0, str(BASE))
    sys.path.insert(0, str(BASE / 'tools'))
    try:
        from tools.vision_doctrine_prompts import get_doctrine_prompt, parse_doctrine_fields, BROADCAST_THRESHOLDS_PROMPT_BLOCK
        doctrine_available = True
    except ImportError:
        try:
            from vision_doctrine_prompts import get_doctrine_prompt, parse_doctrine_fields, BROADCAST_THRESHOLDS_PROMPT_BLOCK
            doctrine_available = True
        except ImportError:
            doctrine_available = False

    # Build a minimal shot dict for promo
    shot = {
        "shot_id": promo['promo_id'],
        "shot_type": "establishing",
        "_arc_position": "ESTABLISH",
        "_beat_action": promo['prompt'][:80],
        "characters": [],
        "dialogue_text": "",
        "_genre_id": genre_id,
        "_production_type": production_type,
    }

    # Base technical prompt
    base_prompt = f"""You are a professional cinematographer and broadcast QC engineer analyzing a short promo video clip.

CLIP CONTEXT:
- Network: {promo['network'].upper().replace('_', ' ')}
- Promo ID: {promo['promo_id']}
- Genre: {genre_id}
- Production type: {production_type}
- Brief: {promo['prompt'][:120]}

Analyze this video clip across ALL dimensions below. Return a SINGLE JSON object (no markdown).

D1. "action_completion": "complete" | "in_progress" | "not_started" | "not_applicable"
D2. "frozen_segment": true | false
D3. "dialogue_sync": "synced" | "no_face_visible" | "frozen_mouth" | "not_applicable"
D4. "emotional_arc": "matches" | "mismatches" | "unclear" | "not_applicable"
D5. "character_start_state": one sentence on spatial state at video START
D6. "environment_description": one sentence describing the visible setting
D7. "overall_pass": true if no critical failures

"""

    # Add doctrine block if available
    if doctrine_available:
        try:
            doctrine_block = get_doctrine_prompt(shot, genre_id=genre_id, production_type=production_type)
            base_prompt = base_prompt + doctrine_block
        except Exception as e:
            print(f"  ⚠️  Doctrine prompt build failed: {e}")

    else:
        # Manual D8-D20 block as fallback
        base_prompt += f"""
{BROADCAST_THRESHOLDS_PROMPT_BLOCK if doctrine_available else ''}

D8. "arc_fulfilled": true | false
D9. "arc_verdict": one sentence
D10. "genre_compliance": "matches" | "partial" | "violated"
D11. "genre_verdict": one sentence
D12. "production_format_compliance": "correct" | "minor_deviation" | "wrong_format"
D13. "cinematography_scores": {{"composition": 0.0-1.0, "lighting": 0.0-1.0, "movement": 0.0-1.0, "color_grade": 0.0-1.0, "framing": 0.0-1.0}}
D14. "filmmaker_grade": "A" | "B" | "C" | "D" | "F"
D15. "grade_reason": one sentence
D16. "doctrine_issues": []
D17. "ai_artifact_report": {{"identity_morphing": false, "temporal_flicker": false, "texture_hallucination": false, "physics_violation": false, "temporal_freeze": false, "artifact_verdict": "clean"}}
D18. "broadcast_qc": {{"vmaf_estimate": 0-100, "color_consistency": "consistent" | "minor_shift" | "inconsistent", "overall_qc": "pass" | "warn" | "fail"}}
D19. "atmosphere_alignment": "aligned" | "partial_mismatch" | "contradicts_intent"
D20. "atmosphere_verdict": one sentence
"""

    # Upload video to Gemini Files API
    try:
        import google.generativeai as genai
        model = genai.GenerativeModel('gemini-2.5-flash')

        print(f"  📤 Uploading video to Gemini ({Path(video_path).stat().st_size//1024}KB)...")
        video_file = genai.upload_file(video_path, mime_type='video/mp4')

        # Wait for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            return {"skipped": True, "reason": "gemini_upload_failed"}

        print(f"  🔍 Scoring with Gemini ({genre_id} × {production_type})...")
        t = time.time()
        response = model.generate_content([video_file, base_prompt])
        elapsed = time.time() - t
        print(f"  ✅ Scored in {elapsed:.0f}s")

        # Parse JSON response
        raw = response.text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        scores = json.loads(raw)

        # Cleanup
        try:
            genai.delete_file(video_file.name)
        except:
            pass

        return scores

    except json.JSONDecodeError as e:
        return {"skipped": True, "reason": f"json_parse_error: {e}", "raw_response": response.text[:500] if 'response' in locals() else ""}
    except Exception as e:
        return {"skipped": True, "reason": str(e)[:200]}


# ─── MANIFEST TRACKING ─────────────────────────────────────────────────────────
manifest = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "endpoint": ENDPOINT_KLING,
    "budget_cap": BUDGET_CAP,
    "cost_per_clip": COST_PER_5S_CLIP,
    "total_spent": 0.0,
    "total_clips": 0,
    "clips_by_network": {},
    "generations": [],
    "failures": [],
}

doctrine_log = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "purpose": "D1-D20 baseline scores across 6 content types for calibration",
    "scores_by_network": {},
    "all_clips": [],
}

def save_manifest():
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=2)
    with open(DOCTRINE_LOG_PATH, 'w') as f:
        json.dump(doctrine_log, f, indent=2)


def upload_image(path: str) -> str:
    with open(path, 'rb') as f:
        return fal_client.upload(f.read(), 'image/jpeg')


def download_video(url: str, output_path: str) -> bool:
    try:
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = Path(output_path).stat().st_size / 1_048_576
        print(f"  ✅ Saved {size_mb:.1f}MB → {Path(output_path).name}")
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def generate_promo(promo: dict, budget_remaining: float) -> dict:
    promo_id = promo['promo_id']
    network = promo['network']
    print(f"\n{'─'*60}")
    print(f"🎬 [{network.upper().replace('_',' ')}] {promo_id}")
    print(f"   Budget remaining: ${budget_remaining:.2f}")

    # Skip if already generated
    if Path(promo['output']).exists() and Path(promo['output']).stat().st_size > 10000:
        existing_size_mb = Path(promo['output']).stat().st_size / 1_048_576
        print(f"  ♻️  Already exists ({existing_size_mb:.1f}MB) — scoring only")
        # Run doctrine scoring on existing file
        doctrine_scores = {}
        if GOOGLE_API_KEY:
            doctrine_scores = score_with_doctrine(promo['output'], promo,
                genre_id=promo['genre_id'], production_type=promo['production_type'])
            if not doctrine_scores.get('skipped'):
                grade = doctrine_scores.get('filmmaker_grade', '?')
                print(f"  🎯 Grade: {grade} | {doctrine_scores.get('genre_compliance','?')} | {doctrine_scores.get('production_format_compliance','?')}")
                net = promo['network']
                if net not in doctrine_log['scores_by_network']:
                    doctrine_log['scores_by_network'][net] = []
                doctrine_log['scores_by_network'][net].append({
                    "promo_id": promo_id, "genre_id": promo['genre_id'],
                    "production_type": promo['production_type'], "d_scores": doctrine_scores,
                })
                doctrine_log['all_clips'].append({
                    "promo_id": promo_id, "network": network, "genre_id": promo['genre_id'],
                    "production_type": promo['production_type'], "d_scores": doctrine_scores,
                })
        return {"status": "success", "promo_id": promo_id, "network": network,
                "genre_id": promo['genre_id'], "production_type": promo['production_type'],
                "image_used": Path(promo['image']).name if Path(promo['image']).exists() else "unknown",
                "output_file": promo['output'], "cost": 0.0,
                "doctrine_scores": doctrine_scores, "reused": True}

    # Resolve image
    img_path = promo['image']
    if not Path(img_path).exists():
        fallback = promo.get('fallback_image')
        if fallback and Path(fallback).exists():
            img_path = fallback
            print(f"  ⚠️  Using fallback: {Path(img_path).name}")
        else:
            print(f"  ❌ Image not found: {img_path}")
            return {"status": "skipped", "reason": "image_not_found", **{k: promo[k] for k in ('promo_id', 'network')}}

    print(f"  📷 Input: {Path(img_path).name} ({Path(img_path).stat().st_size//1024}KB)")

    # Upload image
    print(f"  ⬆️  Uploading to FAL CDN...")
    try:
        image_url = upload_image(img_path)
        print(f"  ✅ CDN URL: {image_url[:70]}...")
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        return {"status": "failed", "reason": str(e), "promo_id": promo_id, "network": network}

    # ═══════════════════════════════════════════════════════════════════════
    # CORRECT ATLAS PIPELINE: Nano frame → Kling v3/pro video
    # Step 1: Nano-Banana-Pro/edit generates a fresh frame from reference image
    # Step 2: Kling v3/pro animates that Nano frame into video
    # If Kling denies: try fresh Nano frame + Kling again (1 retry)
    # If Kling denies again: keep best Nano frame, mark nano_only
    # ═══════════════════════════════════════════════════════════════════════

    def run_nano_frame(ref_url: str, attempt: int = 1) -> tuple[str, str]:
        """Generate a promo frame via Nano. Returns (fal_url, local_path)."""
        print(f"  🖼️  [STEP 1] Nano frame gen (attempt {attempt})...")
        nano_result = fal_client.run(
            ENDPOINT_NANO_EDIT,
            arguments={
                "prompt": promo['prompt'] + " Cinematic wide shot. Professional broadcast quality. 16:9 aspect ratio.",
                "image_urls": [ref_url],
                "aspect_ratio": "16:9",
                "resolution": "1K",
                "output_format": "jpeg",
                "safety_tolerance": "2",
            }
        )
        imgs = (nano_result.get('images') or []) if isinstance(nano_result, dict) else []
        nano_url = (imgs[0].get('url') if isinstance(imgs[0], dict) else imgs[0]) if imgs else None
        if not nano_url:
            raise ValueError(f"Nano returned no image: {str(nano_result)[:150]}")
        # Download frame locally
        frame_path = promo['output'].replace('.mp4', f'_nano_frame_{attempt}.jpg')
        Path(frame_path).parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(nano_url, timeout=60); r.raise_for_status()
        with open(frame_path, 'wb') as f: f.write(r.content)
        kb = Path(frame_path).stat().st_size // 1024
        print(f"     Nano frame OK: {kb}KB → {Path(frame_path).name}")
        return nano_url, frame_path

    def run_kling(start_url: str) -> str:
        """Animate a start frame with Kling v3/pro. Returns video URL."""
        print(f"  🎞️  [STEP 2] Kling v3/pro 5s animation...")
        result = fal_client.run(
            ENDPOINT_KLING,
            arguments={
                "start_image_url": start_url,
                "prompt": promo['prompt'],
                "duration": "5",
                "aspect_ratio": "16:9",
                "negative_prompt": "blurry distorted watermark text overlay low quality static frozen",
                "cfg_scale": 0.5,
            }
        )
        if isinstance(result, dict):
            v = result.get('video')
            if isinstance(v, dict): return v.get('url', '')
            if isinstance(v, str) and v.startswith('http'): return v
            return result.get('video_url') or result.get('url') or ''
        return ''

    engine_used = "nano+kling"
    video_url = None
    file_size = 0
    elapsed = 0
    kling_error = None
    best_nano_frame = None

    t_start = time.time()

    # ── ATTEMPT 1: Nano frame → Kling ────────────────────────────────────────
    try:
        nano_url_1, nano_frame_1 = run_nano_frame(image_url, attempt=1)
        best_nano_frame = nano_frame_1
        # Re-upload nano frame to get CDN URL for Kling
        with open(nano_frame_1, 'rb') as f:
            nano_cdn_1 = fal_client.upload(f.read(), 'image/jpeg')
    except Exception as e:
        print(f"  ❌ Nano step 1 failed: {e}")
        return {"status": "failed", "promo_id": promo_id, "network": network,
                "engine_used": "nano_failed", "reason": str(e)}

    try:
        video_url = run_kling(nano_cdn_1)
        if not video_url:
            raise ValueError("empty URL from Kling attempt 1")
        elapsed = time.time() - t_start
        print(f"  ✅ Kling v3/pro OK in {elapsed:.0f}s")
    except Exception as e:
        kling_error = str(e)
        print(f"  ⚡ Kling denied ({kling_error[:70]}) → fresh Nano frame + retry")

        # ── ATTEMPT 2: fresh Nano frame → Kling again ─────────────────────
        try:
            nano_url_2, nano_frame_2 = run_nano_frame(image_url, attempt=2)
            best_nano_frame = nano_frame_2
            with open(nano_frame_2, 'rb') as f:
                nano_cdn_2 = fal_client.upload(f.read(), 'image/jpeg')
            video_url = run_kling(nano_cdn_2)
            if not video_url:
                raise ValueError("empty URL from Kling attempt 2")
            elapsed = time.time() - t_start
            kling_error = f"attempt1_denied:{kling_error[:50]}"
            print(f"  ✅ Kling OK on retry in {elapsed:.0f}s")
        except Exception as e2:
            print(f"  ⚡ Kling denied again ({str(e2)[:60]}) → keeping Nano frame only")
            engine_used = "nano_only"
            elapsed = time.time() - t_start
            kling_error = f"{kling_error} | retry: {str(e2)[:50]}"
            # Use best nano frame as output
            promo = {**promo, 'output': best_nano_frame}
            video_url = nano_url_2 if 'nano_url_2' in dir() else nano_url_1

    if not video_url:
        return {"status": "failed", "promo_id": promo_id, "network": network,
                "engine_used": engine_used, "reason": "no_url_any_engine"}

    print(f"  🔗 Output URL: {video_url[:70]}...")

    # Download video (or skip if nano_only — frame already on disk)
    if engine_used == "nano_only":
        downloaded = best_nano_frame is not None and Path(best_nano_frame).exists()
        print(f"  🖼️  nano_only — frame saved: {Path(best_nano_frame).name if best_nano_frame else 'MISSING'}")
    else:
        downloaded = download_video(video_url, promo['output'])

    # D1-D20 Doctrine Scoring
    doctrine_scores = {}
    if downloaded and GOOGLE_API_KEY:
        print(f"  📊 Scoring D1-D20 ({promo['genre_id']} × {promo['production_type']})...")
        doctrine_scores = score_with_doctrine(
            promo['output'],
            promo,
            genre_id=promo['genre_id'],
            production_type=promo['production_type'],
        )
        if not doctrine_scores.get('skipped'):
            grade = doctrine_scores.get('filmmaker_grade', '?')
            print(f"  🎯 Filmmaker Grade: {grade}")
            print(f"     Genre: {doctrine_scores.get('genre_compliance','?')} | Format: {doctrine_scores.get('production_format_compliance','?')}")
            issues = doctrine_scores.get('doctrine_issues', [])
            if issues:
                print(f"     Issues: {', '.join(issues[:3])}")
            # Log to doctrine baseline
            net = promo['network']
            if net not in doctrine_log['scores_by_network']:
                doctrine_log['scores_by_network'][net] = []
            doctrine_log['scores_by_network'][net].append({
                "promo_id": promo_id,
                "genre_id": promo['genre_id'],
                "production_type": promo['production_type'],
                "d_scores": doctrine_scores,
            })
            doctrine_log['all_clips'].append({
                "promo_id": promo_id,
                "network": network,
                "genre_id": promo['genre_id'],
                "production_type": promo['production_type'],
                "d_scores": doctrine_scores,
            })
    elif not GOOGLE_API_KEY:
        print(f"  ⚠️  Skipping doctrine scoring (no GOOGLE_API_KEY)")

    # Nano frame ~$0.04; Kling v3/pro 5s ~$0.25-0.35; total per clip ~$0.29-$0.39
    nano_cost  = 0.04
    kling_cost = COST_PER_5S_CLIP if engine_used in ("nano+kling",) else 0.0
    cost = nano_cost + kling_cost if engine_used != "nano_only" else nano_cost * 2

    return {
        "status": "success" if downloaded else "generated_no_download",
        "promo_id": promo_id,
        "network": network,
        "genre_id": promo['genre_id'],
        "production_type": promo['production_type'],
        "engine_used": engine_used,
        "kling_error": kling_error,
        "image_used": Path(img_path).name,
        "video_url": video_url,
        "file_size_bytes": file_size,
        "output_file": promo['output'] if downloaded else None,
        "cost": cost,
        "elapsed_s": int(elapsed),
        "prompt": promo['prompt'],
        "doctrine_scores": doctrine_scores,
    }


# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🎬 FANZ TV VIDEO PROMO GENERATOR V2.0")
    print(f"   Budget Cap: ${BUDGET_CAP:.2f}")
    print(f"   Cost/clip: ${COST_PER_5S_CLIP:.2f} (Kling v2 master, 5s)")
    print(f"   Planned clips: {len(PROMOS)}")
    print(f"   Endpoint: {ENDPOINT_KLING}")
    print(f"   Doctrine scoring: {'✅ Gemini available' if GOOGLE_API_KEY else '❌ No GOOGLE_API_KEY'}")
    print("=" * 60)

    total_spent = 0.0
    networks_done = set()

    for i, promo in enumerate(PROMOS):
        budget_remaining = BUDGET_CAP - total_spent

        if budget_remaining < 0.10:
            print(f"\n⚠️  Budget exhausted (${total_spent:.2f} spent). Stopping.")
            break

        if budget_remaining < 1.50:
            print(f"\n⚠️  Low budget (${budget_remaining:.2f} remaining)...")

        result = generate_promo(promo, budget_remaining)

        if result.get('status') not in ('skipped',):
            total_spent += result.get('cost', COST_PER_5S_CLIP)

        manifest['generations'].append(result)
        manifest['total_spent'] = total_spent
        manifest['total_clips'] = sum(1 for g in manifest['generations'] if g.get('status') == 'success')

        net = promo['network']
        if net not in manifest['clips_by_network']:
            manifest['clips_by_network'][net] = []
        manifest['clips_by_network'][net].append({
            "promo_id": result.get('promo_id'),
            "file": result.get('output_file') or result.get('video_url', 'N/A'),
            "status": result.get('status'),
        })

        if result.get('status') == 'success':
            networks_done.add(net)

        save_manifest()
        print(f"\n  💰 Running total: ${total_spent:.2f} / ${BUDGET_CAP:.2f}")

        if i < len(PROMOS) - 1:
            time.sleep(2)

    # Final summary
    print("\n" + "=" * 60)
    print("📊 GENERATION COMPLETE")
    print(f"   Total spent: ${total_spent:.2f}")
    print(f"   Clips generated: {manifest['total_clips']}")
    print(f"   Networks covered: {len(networks_done)} / 6")
    print(f"   Manifest: {MANIFEST_PATH}")
    print(f"   Doctrine log: {DOCTRINE_LOG_PATH}")
    print("=" * 60)
    kling_clips = sum(1 for g in manifest['generations'] if g.get('engine_used') == 'kling')
    nano_clips  = sum(1 for g in manifest['generations'] if g.get('engine_used') == 'nano')
    print(f"\n   Engine breakdown: Kling={kling_clips}  Nano-fallback={nano_clips}")

    for net, clips in manifest['clips_by_network'].items():
        ok = sum(1 for c in clips if c.get('status') == 'success')
        engines = [c.get('engine_used', '?') for c in manifest['generations'] if c.get('network') == net]
        print(f"  📺 {net}: {ok}/{len(clips)} clips ✅  [{', '.join(engines)}]")

    # Print doctrine summary
    if doctrine_log['all_clips']:
        print("\n📐 DOCTRINE BASELINE (D14 Filmmaker Grades):")
        for clip in doctrine_log['all_clips']:
            g = clip['d_scores'].get('filmmaker_grade', '?')
            issues = clip['d_scores'].get('doctrine_issues', [])
            print(f"  {clip['promo_id']}: Grade {g} | {clip['genre_id']}×{clip['production_type']} | Issues: {len(issues)}")


if __name__ == '__main__':
    main()
