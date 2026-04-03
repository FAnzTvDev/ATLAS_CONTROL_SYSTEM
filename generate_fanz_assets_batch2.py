#!/usr/bin/env python3
"""
FANZ TV Asset Generator — Batch 2
AIFL Team Logos, Stadium Shots, Remaining Show Art
Budget remaining: ~$17.13
"""

import os, json, time, requests, boto3
from pathlib import Path
from botocore.config import Config

os.environ["FAL_KEY"] = "1c446616-b1de-4964-8979-1b6fbc6e41b0:3ff7a80d36b901d586e6b9732a62acd9"
import fal_client

R2_ACCOUNT_ID = "026089839555deec85ae1cfc77648038"
R2_ACCESS_KEY = "9bd9b3551878dba7a09990d86d2c2af0"
R2_SECRET     = "2869cc5136454a0cfad511df69a5c08f96b01490510a82a4276f8417215891c6"
R2_BUCKET     = "rumble-fanz"
R2_ENDPOINT   = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
CDN_BASE      = "https://media.rumbletv.com"

# Batch 1 already spent $2.87
PREV_SPEND    = 2.87
BUDGET_HARD_CAP = 20.00
COST_DEV      = 0.025

total_cost = 0.0
generated  = []
failed     = []

r2 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

BASE_OUT = Path("platform_assets")

def upload_to_r2(local_path: Path, r2_key: str) -> str:
    try:
        with open(local_path, "rb") as f:
            r2.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=f,
                          ContentType="image/jpeg",
                          CacheControl="public, max-age=31536000")
        cdn_url = f"{CDN_BASE}/{r2_key}"
        print(f"    ✅ R2: {cdn_url}")
        return cdn_url
    except Exception as e:
        print(f"    ⚠️  R2 upload failed: {e}")
        return ""

def check_budget(cost: float) -> bool:
    global total_cost
    if PREV_SPEND + total_cost + cost > BUDGET_HARD_CAP:
        print(f"\n🛑 BUDGET CAP. Total: ${PREV_SPEND + total_cost:.2f} / ${BUDGET_HARD_CAP:.2f}")
        return False
    return True

def generate_image(prompt, local_path, r2_key, model="fal-ai/flux/dev",
                   size="square_hd", label=""):
    global total_cost
    if not check_budget(COST_DEV):
        return None
    print(f"\n🎨 {label}")
    print(f"   {prompt[:90]}...")
    try:
        result = fal_client.run(
            model,
            arguments={
                "prompt": prompt,
                "image_size": size,
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
                "output_format": "jpeg",
            },
        )
        img_url = result["images"][0]["url"]
        resp = requests.get(img_url, timeout=60)
        resp.raise_for_status()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(resp.content)
        total_cost += COST_DEV
        cdn_url = upload_to_r2(local_path, r2_key)
        total_with_prev = PREV_SPEND + total_cost
        print(f"   💰 Batch2: ${total_cost:.2f} | All-in: ${total_with_prev:.2f} / ${BUDGET_HARD_CAP:.2f}")
        entry = {"label": label, "local": str(local_path), "cdn_url": cdn_url, "cost": COST_DEV}
        generated.append(entry)
        return entry
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        failed.append({"label": label, "error": str(e)})
        return None

def slugify(s):
    return s.lower().replace(" ", "_").replace("'", "").replace("/", "_").replace(":", "")[:40]

# ── Load AIFL teams from asset pack ───────────────────────────────────────────
with open("ecosystem/fanz_unified_asset_pack.json") as f:
    pack = json.load(f)

AIFL_TEAMS = pack["aifl_teams"]

print("\n" + "="*60)
print("FANZ TV ASSET GENERATOR — BATCH 2")
print(f"Budget: $20.00 | Previously spent: ${PREV_SPEND:.2f}")
print(f"Remaining: ${BUDGET_HARD_CAP - PREV_SPEND:.2f}")
print("="*60)

# ── BATCH A: AIFL TEAM LOGOS (32) ─────────────────────────────────────────────
print("\n\n🏈 BATCH A: AIFL TEAM LOGOS (32)")
print("-"*40)
logo_folder = BASE_OUT / "aifl" / "logos"
logo_folder.mkdir(parents=True, exist_ok=True)

for team in AIFL_TEAMS:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(team["team"])
    logo_prompt = (
        f"{team['logo_prompt']}, "
        f"clean vector logo design, transparent background white, "
        f"primary color {team['primary_color']}, secondary color {team['secondary_color']}, "
        f"modern sports team logo, NFL-quality branding, no text, centered composition"
    )
    generate_image(
        prompt=logo_prompt,
        local_path=logo_folder / f"{slug}_logo.jpg",
        r2_key=f"assets/aifl/logos/{slug}_logo.jpg",
        model="fal-ai/flux/dev",
        size="square_hd",
        label=f"AIFL LOGO | {team['team']} ({team['city']})",
    )
    time.sleep(0.3)

# ── BATCH B: AIFL STADIUM SHOTS (32) ──────────────────────────────────────────
print("\n\n🏟️ BATCH B: AIFL STADIUM SHOTS (32)")
print("-"*40)
stadium_folder = BASE_OUT / "aifl" / "stadiums"
stadium_folder.mkdir(parents=True, exist_ok=True)

for team in AIFL_TEAMS:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(team["team"])
    stadium_prompt = (
        f"{team['stadium_image_prompt']}, "
        f"NFL-quality stadium photography, dramatic game day lighting, "
        f"crowd visible, {team['weather_flavor']}, "
        f"cinematic wide angle, photorealistic, no text overlays"
    )
    generate_image(
        prompt=stadium_prompt,
        local_path=stadium_folder / f"{slug}_stadium.jpg",
        r2_key=f"assets/aifl/stadiums/{slug}_stadium.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"AIFL STADIUM | {team['stadium_name']} ({team['city']})",
    )
    time.sleep(0.3)

# ── BATCH C: REMAINING SHOW ART (VYBE/FANZ shows not in batch 1) ──────────────
print("\n\n📺 BATCH C: REMAINING SHOW ART")
print("-"*40)
remaining_shows = [
    # FANZ MAIN (remaining 5)
    {"title":"FANZ DATA ROOM","platform":"fm","prompt":"FANZ DATA ROOM sports analytics show key art, data visualization, MIT graduate analyst at screens, ESPN analytics aesthetic, clean modern data studio"},
    {"title":"FANZ: TAKE IT OR LEAVE IT","platform":"fm","prompt":"FANZ TAKE IT OR LEAVE IT hot takes show key art, young Mexican-American host in streetwear, bold graphic design, TikTok energy, sports debate culture"},
    {"title":"FANZ CRIME: THE HUNT","platform":"fm","prompt":"FANZ CRIME THE HUNT investigative journalism show key art, journalist following thread of evidence, urban night investigation, true crime documentary"},
    {"title":"FANZ CRIME: VOICES","platform":"fm","prompt":"FANZ CRIME VOICES victim advocacy show key art, microphone close-up, human rights atmosphere, warm yet sobering lighting, documentary style"},
    {"title":"FANZ MONEY: THE ALGORITHM","platform":"fm","prompt":"FANZ MONEY THE ALGORITHM sports tech show key art, Japanese-American woman with data visuals, Silicon Valley meets sports, clean tech aesthetic"},
    # RUMBLE (remaining 5)
    {"title":"RUMBLE: THE WEIGHT OF IT","platform":"rl","prompt":"RUMBLE THE WEIGHT OF IT long-form fighter profile show key art, intimate portrait of fighter, gym solitude, documentary boxing photography"},
    {"title":"RUMBLE: CITY WARS","platform":"rl","prompt":"RUMBLE CITY WARS regional fight show key art, city skyline behind boxing ring, local fighter pride, urban arena energy"},
    {"title":"RUMBLE: WOMEN'S CIRCUIT","platform":"rl","prompt":"RUMBLE WOMEN'S CIRCUIT female fighting show key art, champion women fighters in dramatic lighting, powerful representation, fight night energy"},
    {"title":"RUMBLE: BRACKET","platform":"rl","prompt":"RUMBLE BRACKET tournament show key art, bracket tournament graphic integrated with arena, quarterly championship energy, competitive elimination format"},
    {"title":"RUMBLE: POST-FIGHT BREAKDOWN","platform":"rl","prompt":"RUMBLE POST-FIGHT BREAKDOWN analysis show key art, analyst at tactical screen with fight footage, coaching breakdown, ESPN analysis style"},
    # VYBE (remaining 5)
    {"title":"VYBE: NEW DROP FRIDAY","platform":"vm","prompt":"VYBE NEW DROP FRIDAY new music premiere show key art, Friday night energy, headphones and new tracks, streaming platform aesthetic, purple glow"},
    {"title":"VYBE: CITY SOUNDS","platform":"vm","prompt":"VYBE CITY SOUNDS city music profile show key art, city skyline at night with music waveforms, local music scene energy, premium music television"},
    {"title":"VYBE: STADIUM TOUR","platform":"vm","prompt":"VYBE STADIUM TOUR concert coverage show key art, arena concert aerial view, performer on massive stage, 50,000 fans, spectacular concert photography"},
    {"title":"VYBE: SAINT'S TABLE","platform":"vm","prompt":"VYBE SAINT'S TABLE long-form interview show key art, intimate interview setting, elegant minimal studio, two chairs facing each other, luxury lifestyle"},
    {"title":"VYBE: THE VERDICT","platform":"vm","prompt":"VYBE THE VERDICT album review show key art, vinyl record and headphones, music critic intellectual energy, Cambridge meets hip-hop culture"},
    # AI SPORTS (remaining 5)
    {"title":"AI SPORTS: STAT LINE","platform":"as","prompt":"AI SPORTS STAT LINE daily analytics show key art, holographic stat displays, multiple sport data streams, futuristic sports analytics command center"},
    {"title":"AIFL: CHAMPIONSHIP SEASON","platform":"as","prompt":"AIFL CHAMPIONSHIP SEASON playoff show key art, Lombardi Trophy-style championship trophy, confetti explosion, champions celebrating, cinematic"},
    {"title":"AI SPORTS: THE COMBINE","platform":"as","prompt":"AI SPORTS THE COMBINE draft scouting show key art, athlete running combine tests, AI measurement overlays, draft evaluation technology"},
    {"title":"AI SPORTS: CITY RIVALRY","platform":"as","prompt":"AI SPORTS CITY RIVALRY cross-city matchup show key art, two rival city skylines facing each other, sports collision energy, urban rivalry drama"},
    {"title":"AIBL COURTSIDE","platform":"as","prompt":"AIBL COURTSIDE live basketball show key art, NBA arena courtside view, basketball action from ground level, dramatic hardwood lighting"},
    # JOKEBOX (remaining 5)
    {"title":"JOKEBOX: BEST OF THE WEEK","platform":"jb","prompt":"JOKEBOX BEST OF THE WEEK comedy highlight show key art, best comedy moments compilation energy, multiple laughing faces, golden spotlight montage"},
    {"title":"JOKEBOX: OPEN MIC WARS","platform":"jb","prompt":"JOKEBOX OPEN MIC WARS amateur stand-up competition show key art, open mic night, comedian on small stage, competitive humor energy"},
    {"title":"JOKEBOX: THE BEEF","platform":"jb","prompt":"JOKEBOX THE BEEF comedy beef show key art, two comedians in comedic standoff, exaggerated conflict energy, JokeBox yellow palette"},
    {"title":"JOKEBOX: COMEDY BRACKET","platform":"jb","prompt":"JOKEBOX COMEDY BRACKET tournament comedy show key art, comedian tournament bracket, elimination format, competition show energy"},
    {"title":"JOKEBOX: AFTER DARK","platform":"jb","prompt":"JOKEBOX AFTER DARK late night comedy show key art, late night energy, comedian in spotlight after dark, premium adult comedy atmosphere"},
]

r2_net_map = {"fm":"fanz_main","rl":"rumble_league","vm":"vybe_music","as":"ai_sports","jb":"jokebox_tv","do":"drama_originals"}
folder_map = {
    "fm": BASE_OUT / "shows" / "fanz_main",
    "rl": BASE_OUT / "shows" / "rumble_league",
    "vm": BASE_OUT / "shows" / "vybe_music",
    "as": BASE_OUT / "shows" / "ai_sports",
    "jb": BASE_OUT / "shows" / "jokebox_tv",
    "do": BASE_OUT / "shows" / "drama_originals",
}

for show in remaining_shows:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(show["title"])
    pf = show["platform"]
    folder = folder_map[pf]
    folder.mkdir(parents=True, exist_ok=True)
    generate_image(
        prompt=show["prompt"] + ", TV show key art, professional broadcast quality, no text overlays, cinematic",
        local_path=folder / f"{slug}.jpg",
        r2_key=f"assets/shows/{r2_net_map[pf]}/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"SHOW ART | {show['title']}",
    )
    time.sleep(0.3)

# ── FINAL REPORT ───────────────────────────────────────────────────────────────
all_in = PREV_SPEND + total_cost
print("\n" + "="*60)
print("BATCH 2 COMPLETE")
print("="*60)
print(f"✅ Batch 2 Generated: {len(generated)} images")
print(f"❌ Batch 2 Failed:    {len(failed)} images")
print(f"💰 Batch 2 Cost: ${total_cost:.2f}")
print(f"💰 ALL-IN TOTAL: ${all_in:.2f} / ${BUDGET_HARD_CAP:.2f}")
print(f"💵 Remaining Budget: ${BUDGET_HARD_CAP - all_in:.2f}")

# Append to manifest
manifest_path = BASE_OUT / "generation_manifest.json"
try:
    existing = json.loads(manifest_path.read_text())
except:
    existing = {"assets": [], "failures": []}

existing["batch2_cost"] = round(total_cost, 3)
existing["total_all_in_cost"] = round(all_in, 3)
existing["budget_remaining"] = round(BUDGET_HARD_CAP - all_in, 3)
existing["assets"].extend(generated)
existing["failures"].extend(failed)
existing["total_images"] = len(existing["assets"])
manifest_path.write_text(json.dumps(existing, indent=2))
print(f"\n📋 Manifest updated: {manifest_path}")

if failed:
    print(f"\n⚠️  Failed:")
    for f in failed:
        print(f"   - {f['label']}: {f['error'][:80]}")

print(f"\n🎉 Total platform assets: {len(existing['assets'])} images")
print(f"   📁 platform_assets/vybe/artists/         — 12 artist portraits")
print(f"   📁 platform_assets/rumble/fighters/      — 10 fighter headshots")
print(f"   📁 platform_assets/characters/           — drama/athletes/hosts/network")
print(f"   📁 platform_assets/aifl/logos/           — 32 team logos")
print(f"   📁 platform_assets/aifl/stadiums/        — 32 stadium shots")
print(f"   📁 platform_assets/shows/                — show key art across all networks")
print(f"   📁 platform_assets/banners/              — 6 network banners")
print(f"   🌐 CDN: https://media.rumbletv.com/assets/")
