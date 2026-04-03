#!/usr/bin/env python3
"""
FANZ TV Asset Generator — Batch 3
City Market Cards, Fighter Action Shots, Artist Promo Shots
Budget remaining: ~$14.91
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

PREV_SPEND    = 5.09
BUDGET_HARD_CAP = 20.00
COST_DEV      = 0.025

total_cost = 0.0
generated  = []
failed     = []

r2 = boto3.client(
    "s3", endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY, aws_secret_access_key=R2_SECRET,
    config=Config(signature_version="s3v4"), region_name="auto",
)

BASE_OUT = Path("platform_assets")

def upload_to_r2(local_path, r2_key):
    try:
        with open(local_path, "rb") as f:
            r2.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=f,
                          ContentType="image/jpeg",
                          CacheControl="public, max-age=31536000")
        cdn_url = f"{CDN_BASE}/{r2_key}"
        print(f"    ✅ R2: {cdn_url}")
        return cdn_url
    except Exception as e:
        print(f"    ⚠️  R2 failed: {e}")
        return ""

def check_budget(cost):
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
        print(f"   💰 Batch3: ${total_cost:.2f} | All-in: ${PREV_SPEND + total_cost:.2f} / ${BUDGET_HARD_CAP:.2f}")
        entry = {"label": label, "local": str(local_path), "cdn_url": cdn_url, "cost": COST_DEV}
        generated.append(entry)
        return entry
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        failed.append({"label": label, "error": str(e)})
        return None

def slugify(s):
    return s.lower().replace(" ", "_").replace("'", "").replace("/", "_").replace(":", "").replace(",", "")[:40]

# ── Load data ──────────────────────────────────────────────────────────────────
with open("ecosystem/fanz_unified_asset_pack.json") as f:
    pack = json.load(f)

CITY_MARKETS = pack["city_markets"]

print("\n" + "="*60)
print("FANZ TV ASSET GENERATOR — BATCH 3")
print(f"Budget: $20.00 | Previously spent: ${PREV_SPEND:.2f}")
print(f"Remaining: ${BUDGET_HARD_CAP - PREV_SPEND:.2f}")
print("="*60)

# ── BATCH A: CITY MARKET CARDS (32) ───────────────────────────────────────────
print("\n\n🏙️ BATCH A: CITY MARKET CARDS (32)")
print("-"*40)
city_folder = BASE_OUT / "cities"
city_folder.mkdir(parents=True, exist_ok=True)

# City visual profiles
CITY_VISUALS = {
    "Atlanta":       "Atlanta Georgia skyline at golden hour, Peachtree Street, hip-hop culture energy, urban Southern city",
    "New York":      "New York City Manhattan skyline at night, Times Square glow, iconic bridges, world capital energy",
    "Los Angeles":   "Los Angeles Hollywood Hills at sunset, palm trees, freeway grid, West Coast city glamour",
    "Chicago":       "Chicago iconic cloud gate bean reflection, Lake Michigan waterfront, architecture skyline, Midwest power city",
    "Miami":         "Miami South Beach Art Deco at night, ocean drive neon lights, turquoise ocean, Latin tropical energy",
    "Dallas":        "Dallas downtown Texas skyline at dusk, cowboy culture meets modern city, Reunion Tower, bold Southwest energy",
    "Philadelphia":  "Philadelphia Liberty Bell and skyscrapers, Independence Hall neighborhood, Rocky steps energy, East Coast grit",
    "Houston":       "Houston Texas downtown at night, Space Center NASA nearby, Energy Corridor, diverse Southern metropolis",
    "Phoenix":       "Phoenix Arizona desert city, Camelback Mountain backdrop, sunset desert colors, modern Southwest oasis",
    "San Francisco": "San Francisco Golden Gate Bridge in fog, Bay Area hills, tech innovation meets Victorian architecture",
    "Seattle":       "Seattle Space Needle at twilight, Puget Sound view, Pike Place Market, Pacific Northwest rain and tech culture",
    "Denver":        "Denver Colorado Rocky Mountain backdrop, Mile High city skyline, outdoor adventure and urban culture",
    "Minneapolis":   "Minneapolis Minneapolis skyline with Minnesota winter aurora, Twin Cities bridges, North Star energy",
    "Nashville":     "Nashville Broadway honky-tonk neon at night, country music capital, modern skyline meets Music Row",
    "New Orleans":   "New Orleans French Quarter at night, jazz on Bourbon Street, Mardi Gras color, Mississippi River mystery",
    "Washington DC": "Washington DC National Mall at golden hour, Capitol Building, diverse power city on the Potomac",
    "Baltimore":     "Baltimore Inner Harbor waterfront, historic port city atmosphere, Maryland crabs and waterfront culture",
    "Pittsburgh":    "Pittsburgh three rivers confluence aerial view, steel bridges, Heinz Field, industrial renaissance city",
    "Cleveland":     "Cleveland Ohio city skyline with Lake Erie, Rock and Roll Hall of Fame, industrial Midwest revitalization",
    "Cincinnati":    "Cincinnati Ohio river city downtown, arts district, baseball stadium, historic Over-the-Rhine neighborhood",
    "Detroit":       "Detroit Michigan city skyline, industrial heritage, Renaissance Center, Motor City music legacy",
    "Green Bay":     "Green Bay Wisconsin Lambeau Field area, frozen tundra winter, small city giant football legacy",
    "Indianapolis":  "Indianapolis Indiana downtown, racing culture, Monument Circle, Colts and Pacers city energy",
    "Jacksonville":  "Jacksonville Florida riverside city, St. Johns River skyline, coastal Florida with Southern roots",
    "Kansas City":   "Kansas City Missouri Union Station, barbecue smoke, art deco buildings, crossroads city energy",
    "Las Vegas":     "Las Vegas Nevada Strip at night, neon casino lights, entertainment capital, desert mountain backdrop",
    "Tampa":         "Tampa Bay Florida waterfront, Riverwalk, palm trees, Gasparilla pirate festival city energy",
    "Buffalo":       "Buffalo New York Niagara Falls nearby, lake effect snow city, working class pride, blue collar heart",
    "Charlotte":     "Charlotte North Carolina banking capital, NASCAR energy, Uptown skyline, New South growth city",
    "Memphis":       "Memphis Tennessee Mississippi River view, Beale Street blues neon, soul music capital, BBQ smoke",
    "Tennessee":     "Nashville Tennessee Music Row studios, Broadway entertainment strip, Country Music Hall of Fame",
    "San Diego":     "San Diego California beach city, perfect weather, naval base, Balboa Park, Mexico border culture",
}

for market in CITY_MARKETS:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    city = market["name"]
    slug = slugify(city)
    city_vibe = market.get("city_vibe", "vibrant American city")
    visual = CITY_VISUALS.get(city, f"{city} city skyline, American metropolitan area, urban landscape")
    prompt = (
        f"Cinematic city photography of {visual}. "
        f"Aerial or street-level cinematic perspective. "
        f"Professional travel photography, golden hour or dramatic lighting, "
        f"vibrant authentic city energy, FANZ network visual style, "
        f"no text overlays, no people in foreground, architectural and landscape focus"
    )
    generate_image(
        prompt=prompt,
        local_path=city_folder / f"{slug}.jpg",
        r2_key=f"assets/cities/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"CITY | {city}",
    )
    time.sleep(0.3)

# ── BATCH B: FIGHTER ACTION/PROMO SHOTS ───────────────────────────────────────
print("\n\n🥊 BATCH B: FIGHTER PROMO SHOTS (10)")
print("-"*40)
fighter_promo_folder = BASE_OUT / "rumble" / "promos"
fighter_promo_folder.mkdir(parents=True, exist_ok=True)

FIGHTER_PROMOS = [
    {"name":"DANTE 'IRON CROWN' WASHINGTON",
     "prompt":"6'4\" Black heavyweight boxer, shaved head, in fighting stance with gold-taped gloves raised, arena spotlights, smoke and dramatic backlighting, ESPN fight night photography, championship belt behind him, intense expression"},
    {"name":"SOFIA 'LA TORMENTA' REYNA",
     "prompt":"5'5\" Mexican-American MMA fighter woman, long dark braid, Aztec shoulder tattoo, fighting stance in octagon, storm energy lighting, La Tormenta featherweight champion, dramatic fight card photography"},
    {"name":"KENJI 'THE BLADE' NAKAMURA",
     "prompt":"5'11\" Japanese kickboxer man, lean angular face, black and white shorts, high kick demonstration mid-air, dynamic motion photography, K-1 arena energy, The Blade in action"},
    {"name":"MARCUS 'BIG MAC' COLEMAN",
     "prompt":"6'2\" Black light heavyweight boxer, wide genuine smile between rounds, Philly flag shorts, corner of boxing ring, Philadelphia fight night, fan favorite energy, Big Mac Coleman"},
    {"name":"ZARA 'QUEEN Z' OKONKWO",
     "prompt":"5'4\" Nigerian-American Muay Thai fighter woman, natural hair before fight, Nigerian flag wrist wraps, fighting stance, Queen Z undefeated bantamweight, regal power pose, dramatic arena lighting"},
    {"name":"DONTAE 'GHOST' RIVERS",
     "prompt":"5'10\" Black welterweight brawler, face full of fight tattoos telling his life story, 38-1 veteran, intense pre-fight stare, Ghost Rivers pressure fighter, battle-worn champion"},
    {"name":"HENRIK 'THE VIKING' BERG",
     "prompt":"6'6\" Norwegian heavyweight, massive blond beard, Viking rune tattoos on forearms, imposing stance, The Viking Berg pre-fight walk-out energy, Norse warrior meets modern fighter"},
    {"name":"AALIYAH 'AX' PRICE",
     "prompt":"5'2\" Black strawweight kickboxer woman, cornrow braids, spinning heel kick mid-air demonstration, explosive speed, Ax Price fastest fighter, Miami arena energy, strawweight champion"},
    {"name":"CARLOS 'EL MARTILLO' VEGA",
     "prompt":"5'8\" Mexican super lightweight boxer, Guadalajara pride chest tattoo, trademark body shot stance, El Martillo Mexican boxing heritage, dramatic golden spotlights, 29-1 contender presence"},
    {"name":"JADE 'JADE DRAGON' CHEN",
     "prompt":"5'7\" Chinese-American fighter woman, dragon tattoo up right arm, wushu martial arts pose, Dragon Sweep submission setup, Jade Dragon undefeated challenger, red and gold arena energy"},
]

for fp in FIGHTER_PROMOS:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(fp["name"]) + "_promo"
    prompt = (
        f"Dynamic professional combat sports photography: {fp['prompt']}. "
        f"No text overlays, photorealistic, ESPN UFC fight card quality"
    )
    generate_image(
        prompt=prompt,
        local_path=fighter_promo_folder / f"{slug}.jpg",
        r2_key=f"assets/rumble/promos/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="portrait_4_3",
        label=f"FIGHTER PROMO | {fp['name']}",
    )
    time.sleep(0.3)

# ── BATCH C: ARTIST PERFORMANCE SHOTS (12) ────────────────────────────────────
print("\n\n🎵 BATCH C: ARTIST PERFORMANCE SHOTS (12)")
print("-"*40)
perf_folder = BASE_OUT / "vybe" / "performances"
perf_folder.mkdir(parents=True, exist_ok=True)

ARTIST_PERFS = [
    {"name":"JXTREME",
     "prompt":"24-year-old Black rapper on stage, diamond grill glinting, crowd of thousands behind him, trap music concert, Atlanta rapper, 808 bass energy, designer outfit lit by stage lights"},
    {"name":"NOVA X",
     "prompt":"27-year-old Haitian-French woman DJ/producer, LED-embedded outfit glowing, massive EDM festival stage, hands on controller, Future Bass emotional drop moment, 50,000 crowd"},
    {"name":"AMELIA CROSS",
     "prompt":"29-year-old Black R&B singer, natural hair, vintage aesthetic, intimate soul concert, jazz musicians behind her, raw live performance, Chicago neo-soul venue"},
    {"name":"RYKER STONE",
     "prompt":"31-year-old tattooed rock musician, tight black jeans, playing electric guitar, distortion sound waves visible, alternative rock concert, Dallas venue, stage dive energy"},
    {"name":"CASSIE RAE",
     "prompt":"25-year-old Black country artist woman, cowboy hat and denim, acoustic guitar on stage, Nashville country concert, breaking genre barriers, triumphant performance moment"},
    {"name":"EL MAESTRO",
     "prompt":"28-year-old Puerto Rican reggaeton artist, gold chains gleaming, Miami concert stage, bilingual crowd singing along, dembow rhythm concert energy, Latin trap performance"},
    {"name":"YARA",
     "prompt":"26-year-old Nigerian-British afrobeats singer, colorful ankara outfit, Lagos to Atlanta world tour stage, talking drum musicians behind her, joyful call-and-response concert"},
    {"name":"PHANTOM WAVE",
     "prompt":"22-year-old Black cloud rapper, hooded figure barely lit on stage, reverb-drenched atmospheric concert, New Orleans moody dark stage, mysterious silhouette performance"},
    {"name":"DIAMOND DAVIS",
     "prompt":"23-year-old Black pop R&B singer, meticulous glamour styling, arena tour show, massive stage with choreographers, Atlanta pop star big moment, stadium-scale performance"},
    {"name":"STEEL THREAD",
     "prompt":"4-piece hip-hop jazz band on stage, Black male MC, Asian-American female bassist, drummer, Latina guitarist, NYC live jazz fusion concert, improvisational energy"},
    {"name":"LUNA AZUL",
     "prompt":"30-year-old Colombian-American indie singer, nylon guitar, intimate LA concert venue, understated elegant performance, Spanish and English flowing, candlelit atmosphere"},
    {"name":"FREQUENCY",
     "prompt":"35-year-old Black Chicago DJ, behind massive DJ booth at house music event, Chicago house meets Detroit techno performance, crowd in ecstasy, melodic dance music"},
]

for ap in ARTIST_PERFS:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(ap["name"]) + "_performance"
    prompt = (
        f"Professional concert photography: {ap['prompt']}. "
        f"VYBE Music Network performance aesthetic, Apple Music quality, "
        f"no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=perf_folder / f"{slug}.jpg",
        r2_key=f"assets/vybe/performances/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"ARTIST PERF | {ap['name']}",
    )
    time.sleep(0.3)

# ── BATCH D: FANZ MONEY LEGACY PLAY (missed show) + JOKEBOX extras ────────────
print("\n\n📺 BATCH D: ADDITIONAL SHOW ART")
print("-"*40)
extra_shows = [
    {"title":"FANZ MONEY: LEGACY PLAY","platform":"fm",
     "prompt":"FANZ MONEY LEGACY PLAY ownership legacy show key art, Black businessman at conference table, generational wealth imagery, Howard University energy, legacy and ownership culture"},
    {"title":"JOKEBOX: VERSUS","platform":"jb",
     "prompt":"JOKEBOX VERSUS comedy versus show key art, two comedians facing off on split screen stage, battle of wits, JokeBox golden palette, competitive comedy energy"},
    {"title":"FANZ: HISTORY OF THE GAME","platform":"fm",
     "prompt":"FANZ HISTORY OF THE GAME sports history show key art, vintage sports photography montage, timeline of greatness, ESPN 30 for 30 documentary style quality"},
    {"title":"RUMBLE: UNDISPUTED","platform":"rl",
     "prompt":"RUMBLE UNDISPUTED championship unification show key art, multiple championship belts being held up, undisputed champion moment, dramatic arena flood lighting"},
    {"title":"AI SPORTS: ROOKIE WATCH","platform":"as",
     "prompt":"AI SPORTS ROOKIE WATCH new player scouting show key art, young athlete first game nervous excitement, bright future energy, fresh debut in arena lighting"},
    {"title":"VYBE: UNDERGROUND","platform":"vm",
     "prompt":"VYBE UNDERGROUND underground music scene show key art, basement venue, emerging artists in raw setting, authentic music scene, pre-fame intimate performance"},
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

for show in extra_shows:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(show["title"])
    pf = show["platform"]
    folder = folder_map[pf]
    folder.mkdir(parents=True, exist_ok=True)
    generate_image(
        prompt=show["prompt"] + ", professional broadcast television key art, cinematic, no text overlays",
        local_path=folder / f"{slug}.jpg",
        r2_key=f"assets/shows/{r2_net_map[pf]}/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"SHOW | {show['title']}",
    )
    time.sleep(0.3)

# ── BATCH E: NETWORK IDENTITY CARDS (4 additional platforms detail) ────────────
print("\n\n🌐 BATCH E: PLATFORM IDENTITY ART")
print("-"*40)
identity_art = [
    {"name":"rumble_fight_card","r2":"assets/rumble/fight_card_template.jpg","size":"landscape_16_9",
     "prompt":"RUMBLE LEAGUE empty fight card template background design, orange and dark red dramatic gradient, arena crowd silhouettes, championship atmosphere, octagon/ring visible, cinematic fight poster background with dramatic lighting"},
    {"name":"vybe_stage_backdrop","r2":"assets/vybe/stage_backdrop.jpg","size":"landscape_16_9",
     "prompt":"VYBE Music Network concert stage backdrop design, purple gradient lighting, LED wall, empty stage ready for performance, premium music channel aesthetic, Apple Music stage quality"},
    {"name":"aifl_championship_field","r2":"assets/aifl/championship_field.jpg","size":"landscape_16_9",
     "prompt":"AIFL football championship field aerial view at night, center field logo, stadium lights blazing, confetti ready, championship game atmosphere, NFL-quality production"},
    {"name":"drama_title_card","r2":"assets/drama/originals_backdrop.jpg","size":"landscape_16_9",
     "prompt":"DRAMA ORIGINALS prestige television backdrop, dark atmospheric deep noir, Victorian and modern cinematic blend, premium network title card quality, AMC HBO Netflix aesthetic"},
    {"name":"fanz_studio_set","r2":"assets/fanz/studio_set.jpg","size":"landscape_16_9",
     "prompt":"FANZ Sports television studio set empty, ESPN-quality broadcast studio, giant screens showing sports, anchor desk, professional broadcast lighting, sports media environment"},
    {"name":"jokebox_comedy_stage","r2":"assets/jokebox/comedy_stage.jpg","size":"landscape_16_9",
     "prompt":"JokeBox TV comedy stage empty, yellow and gold spotlight, comedy club meets TV studio hybrid, microphone stand center stage, warm inviting atmosphere, Comedy Central quality"},
]

identity_folder = BASE_OUT / "network_identity"
identity_folder.mkdir(parents=True, exist_ok=True)

for art in identity_art:
    if PREV_SPEND + total_cost >= BUDGET_HARD_CAP:
        break
    generate_image(
        prompt=art["prompt"] + ", no text overlays, professional broadcast quality, cinematic background",
        local_path=identity_folder / f"{art['name']}.jpg",
        r2_key=art["r2"],
        model="fal-ai/flux/dev",
        size=art["size"],
        label=f"NETWORK ID | {art['name']}",
    )
    time.sleep(0.3)

# ── FINAL REPORT ───────────────────────────────────────────────────────────────
all_in = PREV_SPEND + total_cost
print("\n" + "="*60)
print("BATCH 3 COMPLETE")
print("="*60)
print(f"✅ Batch 3 Generated: {len(generated)} images")
print(f"❌ Batch 3 Failed:    {len(failed)} images")
print(f"💰 Batch 3 Cost: ${total_cost:.2f}")
print(f"💰 ALL-IN TOTAL: ${all_in:.2f} / ${BUDGET_HARD_CAP:.2f}")
print(f"💵 Remaining Budget: ${BUDGET_HARD_CAP - all_in:.2f}")

# Update manifest
manifest_path = BASE_OUT / "generation_manifest.json"
try:
    existing = json.loads(manifest_path.read_text())
except:
    existing = {"assets": [], "failures": []}

existing["batch3_cost"] = round(total_cost, 3)
existing["total_all_in_cost"] = round(all_in, 3)
existing["budget_remaining"] = round(BUDGET_HARD_CAP - all_in, 3)
existing["assets"].extend(generated)
existing["failures"].extend(failed)
existing["total_images"] = len(existing["assets"])
manifest_path.write_text(json.dumps(existing, indent=2))
print(f"\n📋 Manifest updated: {manifest_path}")

print(f"\n🎉 GRAND TOTAL: {len(existing['assets'])} platform assets")
print(f"\n📂 ASSET DIRECTORY STRUCTURE:")
for folder in sorted(BASE_OUT.rglob("*.jpg")):
    pass  # count only

all_files = list(BASE_OUT.rglob("*.jpg"))
print(f"   Total JPG files on disk: {len(all_files)}")
print(f"\n🌐 All assets live at: https://media.rumbletv.com/assets/")
print(f"\n💰 FINAL BUDGET SUMMARY:")
print(f"   Batch 1 (portraits, characters, shows): $2.87")
print(f"   Batch 2 (AIFL logos, stadiums, shows):  $2.22")
print(f"   Batch 3 (cities, promos, identity):     ${total_cost:.2f}")
print(f"   TOTAL SPENT: ${all_in:.2f} / ${BUDGET_HARD_CAP:.2f}")
print(f"   REMAINING:   ${BUDGET_HARD_CAP - all_in:.2f}")
