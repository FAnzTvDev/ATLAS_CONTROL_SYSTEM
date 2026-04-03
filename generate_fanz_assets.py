#!/usr/bin/env python3
"""
FANZ TV Platform Asset Generator
Generates portraits, headshots, show art, and banners for all 6 networks.
Budget: $20 HARD CAP
"""

import os, json, time, requests, boto3, hashlib
from pathlib import Path
from botocore.config import Config

# ── CREDENTIALS ────────────────────────────────────────────────────────────────
os.environ["FAL_KEY"] = "os.environ.get('FAL_KEY', '')"
import fal_client

R2_ACCOUNT_ID  = "026089839555deec85ae1cfc77648038"
R2_ACCESS_KEY  = "9bd9b3551878dba7a09990d86d2c2af0"
R2_SECRET      = "2869cc5136454a0cfad511df69a5c08f96b01490510a82a4276f8417215891c6"
R2_BUCKET      = "rumble-fanz"
R2_ENDPOINT    = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
CDN_BASE       = "https://media.rumbletv.com"

BUDGET_HARD_CAP = 20.00
# Flux/dev pricing: ~$0.025/image at 1024px
# Flux/schnell pricing: ~$0.003/image at 1024px
# Using flux/dev for quality portraits; schnell for bulk show cards
COST_DEV       = 0.025   # per image
COST_SCHNELL   = 0.003   # per image

total_cost = 0.0
generated  = []
failed     = []

# ── OUTPUT FOLDERS ─────────────────────────────────────────────────────────────
BASE_OUT = Path("platform_assets")
FOLDERS  = {
    "vybe":       BASE_OUT / "vybe" / "artists",
    "fighters":   BASE_OUT / "rumble" / "fighters",
    "drama":      BASE_OUT / "characters",
    "podcast":    BASE_OUT / "characters" / "hosts",
    "athletes":   BASE_OUT / "characters" / "athletes",
    "network":    BASE_OUT / "characters" / "network",
    "shows_fm":   BASE_OUT / "shows" / "fanz_main",
    "shows_rl":   BASE_OUT / "shows" / "rumble_league",
    "shows_as":   BASE_OUT / "shows" / "ai_sports",
    "shows_vm":   BASE_OUT / "shows" / "vybe_music",
    "shows_jb":   BASE_OUT / "shows" / "jokebox_tv",
    "shows_do":   BASE_OUT / "shows" / "drama_originals",
    "banners":    BASE_OUT / "banners",
    "aifl":       BASE_OUT / "aifl" / "teams",
}
for f in FOLDERS.values():
    f.mkdir(parents=True, exist_ok=True)

# ── R2 CLIENT ──────────────────────────────────────────────────────────────────
r2 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

def upload_to_r2(local_path: Path, r2_key: str) -> str:
    """Upload file to R2 and return CDN URL."""
    try:
        with open(local_path, "rb") as f:
            r2.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=f,
                ContentType="image/jpeg",
                CacheControl="public, max-age=31536000",
            )
        cdn_url = f"{CDN_BASE}/{r2_key}"
        print(f"    ✅ R2: {cdn_url}")
        return cdn_url
    except Exception as e:
        print(f"    ⚠️  R2 upload failed: {e}")
        return ""

def check_budget(cost_per_image: float) -> bool:
    global total_cost
    if total_cost + cost_per_image > BUDGET_HARD_CAP:
        print(f"\n🛑 BUDGET CAP REACHED: ${total_cost:.2f} / ${BUDGET_HARD_CAP:.2f}. STOPPING.")
        return False
    return True

def generate_image(
    prompt: str,
    local_path: Path,
    r2_key: str,
    model: str = "fal-ai/flux/dev",
    size: str = "square_hd",
    label: str = "",
) -> dict | None:
    global total_cost

    cost = COST_DEV if "dev" in model or "pro" in model else COST_SCHNELL
    if not check_budget(cost):
        return None

    print(f"\n🎨 Generating: {label or local_path.name}")
    print(f"   Prompt: {prompt[:100]}...")
    try:
        result = fal_client.run(
            model,
            arguments={
                "prompt": prompt,
                "image_size": size,
                "num_inference_steps": 28 if "dev" in model else 4,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
                "output_format": "jpeg",
            },
        )
        img_url = result["images"][0]["url"]
        # Download
        resp = requests.get(img_url, timeout=60)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        total_cost += cost
        cdn_url = upload_to_r2(local_path, r2_key)
        entry = {"label": label, "local": str(local_path), "cdn_url": cdn_url, "cost": cost}
        generated.append(entry)
        print(f"   💰 Cost: ${cost:.3f} | Running total: ${total_cost:.2f} / ${BUDGET_HARD_CAP:.2f}")
        return entry
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        failed.append({"label": label, "error": str(e)})
        return None

# ──────────────────────────────────────────────────────────────────────────────
# ASSET DEFINITIONS
# ──────────────────────────────────────────────────────────────────────────────

NETWORK_STYLES = {
    "VYBE":     "Apple Music premium artist photography, sleek studio, purple gradient lighting, ultra-sharp, editorial fashion magazine quality",
    "RUMBLE":   "ESPN UFC fight night photography, dramatic rim lighting, intense expression, arena atmosphere, bold cinematic",
    "DRAMA":    "prestige TV character portrait, cinematic moody lighting, AMC HBO aesthetic, shallow depth of field",
    "FANZ":     "professional sports media broadcaster portrait, ESPN SportsCenter studio lighting, polished commercial photography",
    "AI_SPORTS":"futuristic sports photography, cyan accent lighting, Apple TV+ precision, clean white studio",
    "JOKEBOX":  "warm comedy club spotlight lighting, Comedy Central promo aesthetic, genuine expression, golden key light",
    "HORROR":   "atmospheric horror lighting, high contrast, AMC Shudder aesthetic, ominous dark background",
    "SCI_FI":   "clean futuristic lighting, Apple TV+ sci-fi aesthetic, cool blue-white tones, precision",
    "CRIME":    "gritty crime drama portrait, practical lighting, HBO cinematic, atmospheric shadows",
    "BANNER":   "wide cinematic platform key art, broadcast quality, professional graphic design, 16:9 composition",
}

# ── PRIORITY 1: VYBE ARTISTS (12) ─────────────────────────────────────────────
VYBE_ARTISTS = [
    {"id":"vybe_001","name":"JXTREME","visual_description":"24-year-old Black man, diamond grill, designer logos but street energy, Atlanta born","genre":"Hip-Hop / Trap"},
    {"id":"vybe_002","name":"NOVA X","visual_description":"27-year-old mixed-race Haitian-French woman, LED-embedded stage outfit, confident performer","genre":"EDM / Future Bass"},
    {"id":"vybe_003","name":"AMELIA CROSS","visual_description":"29-year-old Black woman, natural hair, vintage aesthetic, Chicago born","genre":"R&B / Neo-Soul"},
    {"id":"vybe_004","name":"RYKER STONE","visual_description":"31-year-old Polish-American man, tattoo sleeves, tight black jeans, rock musician","genre":"Alternative Rock"},
    {"id":"vybe_005","name":"CASSIE RAE","visual_description":"25-year-old Black woman, cowboy hat, denim jacket, Nashville country artist","genre":"Country-Pop"},
    {"id":"vybe_006","name":"EL MAESTRO","visual_description":"28-year-old Puerto Rican man, gold chains, Miami style, confident reggaeton artist","genre":"Reggaeton / Latin Trap"},
    {"id":"vybe_007","name":"YARA","visual_description":"26-year-old Nigerian-British woman, colorful ankara-print outfit, Lagos pipeline, vibrant","genre":"Afrobeats"},
    {"id":"vybe_008","name":"PHANTOM WAVE","visual_description":"22-year-old Black man, hooded silhouette, minimal lighting, mysterious hip-hop artist","genre":"Cloud Rap"},
    {"id":"vybe_009","name":"DIAMOND DAVIS","visual_description":"23-year-old Black woman, meticulous glamour styling, Atlanta R&B pop star energy","genre":"Pop / R&B"},
    {"id":"vybe_010","name":"STEEL THREAD","visual_description":"4-piece hip-hop jazz band, Black MC, Asian-American bassist, drummer, Latina guitarist, NYC loft","genre":"Hip-Hop Jazz Fusion"},
    {"id":"vybe_011","name":"LUNA AZUL","visual_description":"30-year-old Colombian-American woman, understated elegant style, LA indie artist","genre":"Latin Pop / Indie"},
    {"id":"vybe_012","name":"FREQUENCY","visual_description":"35-year-old Black man, Chicago-born DJ, behind DJ booth with decks visible, focused","genre":"Electronic / House"},
]

# ── PRIORITY 1: RUMBLE FIGHTERS (10) ──────────────────────────────────────────
RUMBLE_FIGHTERS = [
    {"id":"rl_001","name":"DANTE 'IRON CROWN' WASHINGTON","visual_description":"6'4\" Black man, 245lbs, shaved head, gold-taped boxing gloves, heavyweight champion aura","weight_class":"Heavyweight"},
    {"id":"rl_002","name":"SOFIA 'LA TORMENTA' REYNA","visual_description":"5'5\" Mexican-American woman, long dark braid, Aztec eagle shoulder tattoo, intense fighter","weight_class":"Featherweight"},
    {"id":"rl_003","name":"KENJI 'THE BLADE' NAKAMURA","visual_description":"5'11\" Japanese man, lean angular face, black and white trunks, kickboxer stance","weight_class":"Middleweight"},
    {"id":"rl_004","name":"MARCUS 'BIG MAC' COLEMAN","visual_description":"6'2\" Black man, 205lbs, wide genuine smile, Philadelphia flag boxing shorts","weight_class":"Light Heavyweight"},
    {"id":"rl_005","name":"ZARA 'QUEEN Z' OKONKWO","visual_description":"5'4\" Nigerian-American woman, natural hair crown, Nigerian flag wrist wraps, fierce bantamweight","weight_class":"Bantamweight"},
    {"id":"rl_006","name":"DONTAE 'GHOST' RIVERS","visual_description":"5'10\" Black man, 170lbs, face covered in fight story tattoos, veteran welterweight","weight_class":"Welterweight"},
    {"id":"rl_007","name":"HENRIK 'THE VIKING' BERG","visual_description":"6'6\" Norwegian man, blond beard, Viking rune forearm tattoos, imposing heavyweight","weight_class":"Heavyweight"},
    {"id":"rl_008","name":"AALIYAH 'AX' PRICE","visual_description":"5'2\" Black woman, cornrow braids, explosive strawweight fighter energy, Miami","weight_class":"Strawweight"},
    {"id":"rl_009","name":"CARLOS 'EL MARTILLO' VEGA","visual_description":"5'8\" Mexican man, Guadalajara pride chest tattoo, Mexican boxing style","weight_class":"Super Lightweight"},
    {"id":"rl_010","name":"JADE 'JADE DRAGON' CHEN","visual_description":"5'7\" Chinese-American woman, dragon tattoo up right arm, martial arts stance","weight_class":"Women's Lightweight"},
]

# ── PRIORITY 2: PODCAST/BROADCAST HOSTS (15 + 5 network) ─────────────────────
HOSTS = [
    {"id":"pod_001","name":"REGGIE 'THE COMMISSIONER' BANKS","visual":"52-year-old Black man, silver temples, tailored suit, ESPN broadcaster confidence","style":"FANZ"},
    {"id":"pod_002","name":"TASHA 'FACTS ONLY' MONROE","visual":"34-year-old Black woman, natural hair, glasses, data analyst energy, confident","style":"FANZ"},
    {"id":"pod_003","name":"MARCO 'LOUD MARCO' ESPINOZA","visual":"29-year-old Mexican-American man, streetwear outfit, bold personality, TikTok energy","style":"FANZ"},
    {"id":"pod_004","name":"DJ PROPHET","visual":"38-year-old Black man, fitted cap cocked, turntables visible behind him, hip-hop energy","style":"VYBE"},
    {"id":"pod_005","name":"KEZIA 'K-LUX' HENRY","visual":"31-year-old Black woman, natural hair with gold accents, intellectual music critic presence","style":"VYBE"},
    {"id":"pod_006","name":"SAINT COLE","visual":"26-year-old Black man, all-white outfit, Rolex watch, effortlessly wealthy lifestyle","style":"VYBE"},
    {"id":"pod_007","name":"WENDELL 'WEND' PRICE JR.","visual":"44-year-old Black man, cardigan over graphic tee, Atlanta comedian, relaxed warmth","style":"JOKEBOX"},
    {"id":"pod_008","name":"IZZY CHEN-DAVIS","visual":"27-year-old Asian-Black woman, curly hair, thrift store aesthetic, Twitch personality energy","style":"JOKEBOX"},
    {"id":"pod_009","name":"VICTOR 'VIC GOLD' GOLDSMITH","visual":"39-year-old Jewish man, slim suit, deadpan expression, roast comedian energy","style":"JOKEBOX"},
    {"id":"pod_010","name":"DET. LYDIA CROSS (RET.)","visual":"58-year-old white woman, retired detective, grey bob, hard-won authority","style":"FANZ"},
    {"id":"pod_011","name":"OMAR HASSAN","visual":"36-year-old Somali-American man, sharp-dressed, investigative journalist intensity","style":"FANZ"},
    {"id":"pod_012","name":"PHOENIX BLAKE","visual":"31-year-old Black non-binary person, natural hair, quiet commanding authority","style":"FANZ"},
    {"id":"pod_013","name":"DAMON 'MOGUL' HAYES","visual":"47-year-old Black man, former NFL player turned businessman, Wharton MBA confidence","style":"FANZ"},
    {"id":"pod_014","name":"YUKI TANAKA-ROSS","visual":"33-year-old Japanese-American woman, Stanford MBA, casual tech aesthetic","style":"FANZ"},
    {"id":"pod_015","name":"CORNELIUS 'NEIL' WASHINGTON III","visual":"61-year-old Black man, Howard graduate, old money earned energy, dignified","style":"FANZ"},
    # Network personalities
    {"id":"net_001","name":"CARTER JAMES","visual":"55-year-old Black man, silver hair immaculate, expensive suit, network president gravitas","style":"FANZ"},
    {"id":"net_002","name":"NINA RASHAD","visual":"38-year-old Lebanese-American woman, earpiece in, news anchor polish and urgency","style":"FANZ"},
    {"id":"net_003","name":"JAMES 'THE VOICE' STERLING","visual":"62-year-old white man, stadium announcer presence, broadcasting legend confidence","style":"FANZ"},
    {"id":"net_004","name":"BRITTANY 'B-SHARP' SHARPE","visual":"26-year-old Black woman, natural hair, microphone in hand, sideline reporter energy","style":"FANZ"},
    {"id":"net_005","name":"PROFESSOR DR. KOFI ANSAH","visual":"51-year-old Ghanaian-American man, Georgetown professor, Ankara tie on suit jacket","style":"FANZ"},
]

# ── PRIORITY 2: DRAMA CHARACTERS (24) ─────────────────────────────────────────
DRAMA_CHARS = [
    {"id":"char_001","name":"ELEANOR VOSS","show":"Victorian Shadows","visual":"Late 30s white woman, sharp angular features, dark auburn hair pulled back, Victorian brown wool coat, wire-rimmed spectacles, worn leather briefcase","style":"DRAMA"},
    {"id":"char_002","name":"THOMAS BLACKWOOD","show":"Victorian Shadows","visual":"Early 40s white man, tall lean build, dark wavy hair, Victorian overcoat, weathered face, keen eyes","style":"DRAMA"},
    {"id":"char_003","name":"NADIA COLE","show":"Victorian Shadows","visual":"Late 20s Black woman, natural hair, intelligent eyes, simple dark Victorian dress, camera in hand","style":"DRAMA"},
    {"id":"char_004","name":"RAYMOND CROSS","show":"Victorian Shadows","visual":"Mid 50s white man, stocky powerful build, silver-streaked hair slicked back, formal Victorian attire, gold cross chain","style":"DRAMA"},
    {"id":"char_005","name":"HARRIET HARGROVE","show":"Victorian Shadows","visual":"60s white woman, gaunt ethereal presence, white hair, black mourning Victorian dress","style":"HORROR"},
    {"id":"char_006","name":"DETECTIVE ELENA REYES","show":"Crown Heights","visual":"Mid 30s Latina woman, athletic build, dark curly hair, leather jacket, detective badge on belt","style":"CRIME"},
    {"id":"char_007","name":"MARCUS REID","show":"Crown Heights","visual":"Late 20s Black man, athletic fit build, fade haircut, Jordan 1 sneakers, Brooklyn native energy","style":"CRIME"},
    {"id":"char_008","name":"BISHOP TATE","show":"Crown Heights","visual":"Late 40s Black man, heavy powerful build, designer clothes, gold cross necklace, intimidating","style":"CRIME"},
    {"id":"char_009","name":"YOLANDA MORALES","show":"Crown Heights","visual":"Early 40s Latina woman, nurse scrubs, tired but hopeful eyes, community anchor presence","style":"CRIME"},
    {"id":"char_010","name":"GEMMA ARNOLD","show":"Red Key","visual":"Late 20s white woman, red-dyed hair, spy thriller chameleon energy, calculating eyes","style":"CRIME"},
    {"id":"char_011","name":"REN TAKEDA","show":"Red Key","visual":"Early 30s Japanese-American man, slight build, oversized tech hoodie, hacker energy","style":"SCI_FI"},
    {"id":"char_012","name":"LIAM WALLACE","show":"Red Key","visual":"Late 40s white man, MI6 handler build gone soft, expensive watch, spy agency weight","style":"CRIME"},
    {"id":"char_013","name":"NAOMI LAWSON","show":"Red Key","visual":"Mid 30s Black woman, immaculate presentation, sharper instincts than everyone in the room","style":"CRIME"},
    {"id":"char_014","name":"MR. OSCAR","show":"Red Key","visual":"Older European man, age unknown, linen suit, no expression, truly dangerous antagonist","style":"CRIME"},
    {"id":"orig_001","name":"COMMANDER ZARA PULSE","show":"Signal Break","visual":"Mid 30s Black woman, battle-worn command uniform, prosthetic right arm with integrated tech, sci-fi","style":"SCI_FI"},
    {"id":"orig_002","name":"DR. FELIX CRANE","show":"Signal Break","visual":"Late 40s white man, sterile lab coat, cold clinical expression, scientific antagonist","style":"SCI_FI"},
    {"id":"orig_003","name":"JUNE HOLLIS","show":"Harrow House","visual":"Late 20s white woman, journalist with camera, fear replacing confidence, horror protagonist","style":"HORROR"},
    {"id":"orig_004","name":"PASTOR ELIAS MORROW","show":"Harrow House","visual":"60s Black man, reverend collar, grips Bible tightly, faith tested by horror","style":"HORROR"},
    {"id":"orig_005","name":"DETECTIVE SAM FORD","show":"Ford's Line","visual":"40s white man, three days stubble, coffee cup in hand, burned out detective","style":"CRIME"},
    {"id":"orig_006","name":"LUNA ESPINOZA-FORD","show":"Ford's Line","visual":"Late 20s Latina woman, detective badge three months old, sharper instincts than her partner","style":"CRIME"},
    {"id":"orig_007","name":"ALEX 'AXIOM' CHEN","show":"Axiom","visual":"25-year-old Chinese-American non-binary person, laptop stickers everywhere, ethical hacker energy","style":"SCI_FI"},
    {"id":"orig_008","name":"DIRECTOR HAYES MORLEY","show":"Axiom","visual":"58-year-old white man, government agency suit, patriot who lost the moral plot","style":"SCI_FI"},
    {"id":"orig_009","name":"GRANDMOTHER STONE","show":"The Delta","visual":"75-year-old Black woman, Mississippi Delta presence, front porch dignity, 60 years of secrets","style":"DRAMA"},
    {"id":"orig_010","name":"MILES STONE","show":"The Delta","visual":"Late 30s Black man, left the South at 18 and made it, returned for funeral, caught between worlds","style":"DRAMA"},
]

# ── PRIORITY 3: AI SPORTS ATHLETES (20) ───────────────────────────────────────
ATHLETES = [
    {"id":"aifl_001","name":"JAVON 'LIGHTNING' BROOKS","visual":"6'3\" Black man, 230lbs, QB stance, #1 jersey, laser-focus eyes, mobile quarterback","sport":"Football QB"},
    {"id":"aifl_002","name":"TREMAINE 'HAMMER' JACKSON","visual":"5'11\" Black man, thick neck, power running back build, #32 jersey, Chicago Storm","sport":"Football RB"},
    {"id":"aifl_003","name":"DEONTAE 'D-FLASH' WILLIAMS","visual":"6'1\" Black man, 195lbs, #84 jersey, gold cleats, wide receiver speed","sport":"Football WR"},
    {"id":"aifl_004","name":"RICO 'BRICK WALL' SANTOS","visual":"6'5\" Afro-Latino man, 275lbs, #91 jersey, defensive end intensity","sport":"Football DE"},
    {"id":"aibl_001","name":"ZION 'Z-MONEY' PARISH","visual":"6'2\" Black man, 195lbs, #3 jersey, cornrows, point guard court vision","sport":"Basketball PG"},
    {"id":"aibl_002","name":"MISHA 'THE MACHINE' VOLKOV","visual":"7'1\" Russian man, 265lbs, #12 jersey, cold expression, dominant center","sport":"Basketball C"},
    {"id":"aibl_003","name":"LONDON 'FLASH' HAYES","visual":"6'5\" Black man, 215lbs, #23 jersey, shooting guard precision","sport":"Basketball SG"},
    {"id":"aibl_004","name":"AMARA 'QUEEN AMARA' OSEI","visual":"6'1\" Ghanaian-American woman, #24 jersey, gold headband, small forward power","sport":"Basketball SF"},
    {"id":"aimlb_001","name":"PEDRO 'EL TORO' DIAZ","visual":"6'4\" Dominican man, pitcher on mound, deliberate ritual, #21 jersey","sport":"Baseball SP"},
    {"id":"aimlb_002","name":"KYLE 'K-BOMB' MORRISON","visual":"6'6\" white man, massive power hitter build, #44 jersey, home run stance","sport":"Baseball 1B"},
    {"id":"aimlb_003","name":"AKIRA YAMAMOTO","visual":"5'10\" Japanese man, shortstop athleticism, #7 jersey, Gold Glove precision","sport":"Baseball SS"},
    {"id":"aimlb_004","name":"DESTINY 'D-ROC' ROCHELLE","visual":"5'8\" Black woman, catcher gear, calls pitches with authority, #2 jersey","sport":"Baseball C"},
    {"id":"ainhl_001","name":"IVAN 'THE CZAR' PETROV","visual":"6'2\" Russian man, hockey center ice, #91 jersey, MVP presence","sport":"Hockey C"},
    {"id":"ainhl_002","name":"TYLER 'T-BONE' MCALLISTER","visual":"6'4\" white man, three missing teeth proud, enforcer energy, #14 jersey","sport":"Hockey RW"},
    {"id":"ainhl_003","name":"EMMA 'ICE QUEEN' LINDQVIST","visual":"5'11\" Swedish woman, all-white goalie mask with crown design, ice goalie stance","sport":"Hockey G"},
    {"id":"ainhl_004","name":"SEBASTIEN 'SEBBO' LAFLEUR","visual":"6'3\" Quebecois man, French-Canadian swagger, defenseman blue line stance, #5 jersey","sport":"Hockey D"},
    {"id":"aimls_001","name":"GABRIEL 'GABI' SANTOS FERREIRA","visual":"5'9\" Brazilian man, dreadlocks, #10 jersey, attacking midfielder flair","sport":"Soccer AM"},
    {"id":"aimls_002","name":"FATIMAH AL-RASHID","visual":"5'7\" Jordanian-American woman, hijab in team colors, #9 jersey, striker with Golden Boot energy","sport":"Soccer ST"},
    {"id":"aimls_003","name":"KWAME 'THE GENERAL' ASANTE","visual":"6'0\" Ghanaian man, #8 jersey, commanding midfielder reads three passes ahead","sport":"Soccer CM"},
    {"id":"aimls_004","name":"DIEGO 'EL FENOMENO' RESTREPO","visual":"6'4\" Colombian man, wild orange goalkeeper gloves, sweeper-keeper athleticism","sport":"Soccer GK"},
]

# ── PRIORITY 3: NETWORK PLATFORM BANNERS (6) ──────────────────────────────────
BANNERS = [
    {"id":"banner_fanz","platform":"FANZ Sports & Culture","prompt":"FANZ Sports and Culture network hero banner, bold red and white color palette, diverse athletes and hosts in dynamic action, 'WHERE THE GAME LIVES' energy, ESPN-level production quality, cinematic wide shot, broadcast TV key art"},
    {"id":"banner_rumble","platform":"RUMBLE League","prompt":"RUMBLE LEAGUE fight network hero banner, intense orange and dark red palette, champion fighters in dramatic fight-night lighting, 'THE ONLY FIGHT CARD THAT MATTERS', UFC ESPN arena energy, cinematic dramatic lighting"},
    {"id":"banner_ai_sports","platform":"AI Sports Network","prompt":"AI Sports Network hero banner, futuristic cyan and dark blue palette, diverse athletes across football basketball baseball hockey soccer, holographic data overlays, 'THE FUTURE OF ATHLETIC EXCELLENCE', Apple TV+ precision aesthetic"},
    {"id":"banner_vybe","platform":"VYBE Music Network","prompt":"VYBE Music Network hero banner, premium purple gradient palette, diverse musical artists in Apple Music editorial style, 'THE CULTURE'S SOUNDTRACK', sleek premium music platform key art, ultra-modern"},
    {"id":"banner_jokebox","platform":"JokeBox TV","prompt":"JokeBox TV comedy network hero banner, warm golden yellow palette, diverse comedians mid-performance in spotlight, 'NO FILTER. ALL LAUGHS.', Comedy Central energy, warm stage lighting, joyful"},
    {"id":"banner_drama","platform":"DRAMA Originals","prompt":"DRAMA Originals premium network hero banner, deep cinematic dark palette, multiple character portraits from Victorian Shadows Crown Heights Signal Break, prestige TV key art, HBO AMC quality, atmospheric moody lighting"},
]

# ── PRIORITY 4: SHOW KEY ART (select 24 highest priority) ────────────────────
SHOW_ART = [
    # RUMBLE shows
    {"id":"show_rl_01","title":"RUMBLE MAIN EVENT","platform":"rl","prompt":"RUMBLE MAIN EVENT live fight coverage TV show key art, arena crowd, two fighters facing off, ring lights, championship title belt, bold orange typography, fight night energy"},
    {"id":"show_rl_02","title":"RUMBLE: ROAD TO THE CROWN","platform":"rl","prompt":"RUMBLE ROAD TO THE CROWN docuseries key art, fighter training in gym, determination and sweat, behind-the-scenes documentary style, gritty cinematic"},
    {"id":"show_rl_08","title":"RUMBLE: IRON CROWN SPECIALS","platform":"rl","prompt":"RUMBLE IRON CROWN SPECIALS heavyweight championship mega event key art, Dante Washington silhouette with crown, arena explosion, gold and black color palette, epic scale"},
    # VYBE shows
    {"id":"show_vm_01","title":"VYBE: THE CULTURE SHIFT","platform":"vm","prompt":"VYBE THE CULTURE SHIFT hip-hop culture talk show key art, DJ booth, vinyl records, neon purple lights, premium music studio, cool underground energy"},
    {"id":"show_vm_04","title":"VYBE: LIVE SESSION","platform":"vm","prompt":"VYBE LIVE SESSION in-studio performance show key art, musician on stage with band, intimate studio lighting, live music energy, premium music television"},
    {"id":"show_vm_08","title":"VYBE: THE CYPHER","platform":"vm","prompt":"VYBE THE CYPHER freestyle rap battle show key art, circle of rappers in studio, microphone center frame, raw hip-hop energy, urban night lighting"},
    # FANZ MAIN shows
    {"id":"show_fm_01","title":"FANZ LIVE: THE TAKE","platform":"fm","prompt":"FANZ LIVE THE TAKE sports debate show key art, studio debate set, ESPN-style lighting, multiple hosts at desk, sports broadcast premium production"},
    {"id":"show_fm_04","title":"FANZ CRIME: COLD FILES","platform":"fm","prompt":"FANZ CRIME COLD FILES true crime show key art, cold case file folders, evidence photographs, retired detective atmosphere, AMC true crime documentary aesthetic"},
    {"id":"show_fm_07","title":"FANZ MONEY: THE MOGUL ROOM","platform":"fm","prompt":"FANZ MONEY THE MOGUL ROOM business show key art, boardroom setting, athlete turned mogul energy, financial district skyline, wealth and ambition"},
    # AI SPORTS shows
    {"id":"show_as_01","title":"AIFL GAME NIGHT","platform":"as","prompt":"AIFL GAME NIGHT live football coverage show key art, stadium aerial view, night game lights, crowd energy, futuristic AI sports data overlays"},
    {"id":"show_as_02","title":"AIFL: LIGHTNING STRIKES","platform":"as","prompt":"AIFL LIGHTNING STRIKES quarterback docuseries key art, star QB throwing spiral, motion blur speed, lightning effects, #1 jersey, dramatic stadium lighting"},
    {"id":"show_as_06","title":"AI SPORTS: WOMEN'S LEAGUE","platform":"as","prompt":"AI SPORTS WOMEN'S LEAGUE show key art, diverse female athletes across multiple sports, empowering imagery, championship moments, inclusive athletic excellence"},
    # JOKEBOX shows
    {"id":"show_jb_01","title":"JOKEBOX: THE WEND SHOW","platform":"jb","prompt":"JOKEBOX THE WEND SHOW stand-up comedy talk show key art, comedian on stage, spotlight, audience laughing, warm golden lighting, Atlanta comedy"},
    {"id":"show_jb_02","title":"JOKEBOX: PANEL DAMAGE","platform":"jb","prompt":"JOKEBOX PANEL DAMAGE chaotic panel comedy show key art, multiple comedians on colorful set, controlled chaos energy, internet culture humor"},
    {"id":"show_jb_03","title":"JOKEBOX: ROAST SEASON","platform":"jb","prompt":"JOKEBOX ROAST SEASON celebrity roast show key art, roast podium setup, comedian with microphone, roast victim in chair, golden lighting humor"},
    # DRAMA ORIGINALS shows
    {"id":"show_vs","title":"Victorian Shadows","platform":"do","prompt":"Victorian Shadows prestige TV show key art, Victorian London fog, Eleanor and Thomas silhouettes on cobblestone street, gas lamp lighting, gothic mystery atmosphere, HBO prestige aesthetic"},
    {"id":"show_ch","title":"Crown Heights","platform":"do","prompt":"Crown Heights urban crime drama show key art, Brooklyn street at night, detective badge and street life collision, gritty cinematic, AMC prestige"},
    {"id":"show_rk","title":"Red Key","platform":"do","prompt":"Red Key spy thriller show key art, international espionage aesthetic, red-haired woman in shadows, encrypted data visuals, Apple TV+ spy drama quality"},
    {"id":"show_sb","title":"Signal Break","platform":"do","prompt":"Signal Break sci-fi drama show key art, space station exterior, Commander Zara prosthetic arm detail, deep space backdrop, clean Apple TV+ sci-fi aesthetic"},
    {"id":"show_hh","title":"Harrow House","platform":"do","prompt":"Harrow House horror show key art, dark Victorian manor in fog, atmospheric dread, Shudder horror aesthetic, gothic supernatural"},
    {"id":"show_fl","title":"Ford's Line","platform":"do","prompt":"Ford's Line crime drama show key art, detective with coffee cup in rain-soaked city, partner dynamic, gritty urban noir"},
    {"id":"show_ax","title":"Axiom","platform":"do","prompt":"Axiom cyber thriller show key art, hacker at multiple screens, encrypted code, government surveillance aesthetic, modern tech thriller"},
    {"id":"show_dl","title":"The Delta","platform":"do","prompt":"The Delta southern gothic drama show key art, Mississippi Delta landscape, front porch of weathered home, generational secrets, HBO southern gothic"},
]

def style_to_key(style: str) -> str:
    return NETWORK_STYLES.get(style, NETWORK_STYLES["DRAMA"])

def slugify(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "").replace("/", "_").replace(":", "")[:40]

# ──────────────────────────────────────────────────────────────────────────────
# GENERATION RUNS
# ──────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("FANZ TV ASSET GENERATOR")
print(f"Budget: ${BUDGET_HARD_CAP:.2f} | Model: flux/dev (~$0.025/img)")
print("="*60)

# ── BATCH 1: VYBE ARTISTS (12 portraits) ──────────────────────────────────────
print("\n\n🎵 BATCH 1: VYBE ARTISTS (12)")
print("-"*40)
for artist in VYBE_ARTISTS:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(artist["name"])
    prompt = (
        f"Professional music artist portrait photograph of {artist['visual_description']}, "
        f"genre: {artist['genre']}, "
        f"{NETWORK_STYLES['VYBE']}, "
        f"looking directly at camera, clean background, "
        f"no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=FOLDERS["vybe"] / f"{slug}.jpg",
        r2_key=f"assets/vybe/artists/{slug}.jpg",
        model="fal-ai/flux/dev",
        label=f"VYBE | {artist['name']}",
    )
    time.sleep(0.5)

# ── BATCH 2: RUMBLE FIGHTERS (10 portraits) ────────────────────────────────────
print("\n\n🥊 BATCH 2: RUMBLE FIGHTERS (10)")
print("-"*40)
for fighter in RUMBLE_FIGHTERS:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(fighter["name"])
    prompt = (
        f"Professional fight sports portrait of {fighter['visual_description']}, "
        f"{fighter['weight_class']} division fighter, "
        f"{NETWORK_STYLES['RUMBLE']}, "
        f"standing pose facing camera, dark dramatic background, "
        f"no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=FOLDERS["fighters"] / f"{slug}.jpg",
        r2_key=f"assets/rumble/fighters/{slug}.jpg",
        model="fal-ai/flux/dev",
        label=f"RUMBLE | {fighter['name']}",
    )
    time.sleep(0.5)

# ── BATCH 3: PODCAST / BROADCAST HOSTS (20) ───────────────────────────────────
print("\n\n🎙️ BATCH 3: HOSTS & PERSONALITIES (20)")
print("-"*40)
for host in HOSTS:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(host["name"])
    net_style = NETWORK_STYLES.get(host["style"], NETWORK_STYLES["FANZ"])
    prompt = (
        f"Professional media personality portrait of {host['visual']}, "
        f"{net_style}, "
        f"confident pose looking at camera, broadcast studio background, "
        f"no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=FOLDERS["podcast"] / f"{slug}.jpg",
        r2_key=f"assets/characters/hosts/{slug}.jpg",
        model="fal-ai/flux/dev",
        label=f"HOST | {host['name']}",
    )
    time.sleep(0.5)

# ── BATCH 4: DRAMA CHARACTERS (24) ────────────────────────────────────────────
print("\n\n🎭 BATCH 4: DRAMA CHARACTERS (24)")
print("-"*40)
for char in DRAMA_CHARS:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(char["name"])
    style_desc = NETWORK_STYLES.get(char["style"], NETWORK_STYLES["DRAMA"])
    prompt = (
        f"Prestige TV character portrait of {char['visual']}, "
        f"from show '{char['show']}', "
        f"{style_desc}, "
        f"character looking at camera or slightly off-camera, "
        f"cinematic composition, no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=FOLDERS["drama"] / f"{slug}.jpg",
        r2_key=f"assets/characters/drama/{slug}.jpg",
        model="fal-ai/flux/dev",
        label=f"DRAMA | {char['name']} ({char['show']})",
    )
    time.sleep(0.5)

# ── BATCH 5: AI SPORTS ATHLETES (20) ──────────────────────────────────────────
print("\n\n🏆 BATCH 5: AI SPORTS ATHLETES (20)")
print("-"*40)
for athlete in ATHLETES:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(athlete["name"])
    prompt = (
        f"Professional sports athlete portrait of {athlete['visual']}, "
        f"sport: {athlete['sport']}, "
        f"{NETWORK_STYLES['AI_SPORTS']}, "
        f"athletic pose, stadium or arena background, "
        f"no text overlays, photorealistic"
    )
    generate_image(
        prompt=prompt,
        local_path=FOLDERS["athletes"] / f"{slug}.jpg",
        r2_key=f"assets/characters/athletes/{slug}.jpg",
        model="fal-ai/flux/dev",
        label=f"ATHLETE | {athlete['name']}",
    )
    time.sleep(0.5)

# ── BATCH 6: PLATFORM BANNERS (6) ─────────────────────────────────────────────
print("\n\n🏳️ BATCH 6: PLATFORM BANNERS (6)")
print("-"*40)
for banner in BANNERS:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(banner["platform"])
    generate_image(
        prompt=banner["prompt"] + ", no text overlays, professional broadcast key art, ultra high quality",
        local_path=FOLDERS["banners"] / f"{slug}.jpg",
        r2_key=f"assets/banners/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"BANNER | {banner['platform']}",
    )
    time.sleep(0.5)

# ── BATCH 7: SHOW KEY ART (24) ────────────────────────────────────────────────
print("\n\n🎬 BATCH 7: SHOW KEY ART (24)")
print("-"*40)
platform_folder_map = {
    "rl": FOLDERS["shows_rl"],
    "vm": FOLDERS["shows_vm"],
    "fm": FOLDERS["shows_fm"],
    "as": FOLDERS["shows_as"],
    "jb": FOLDERS["shows_jb"],
    "do": FOLDERS["shows_do"],
}
platform_r2_map = {
    "rl": "rumble_league",
    "vm": "vybe_music",
    "fm": "fanz_main",
    "as": "ai_sports",
    "jb": "jokebox_tv",
    "do": "drama_originals",
}
for show in SHOW_ART:
    if total_cost >= BUDGET_HARD_CAP:
        break
    slug = slugify(show["title"])
    pf = show["platform"]
    folder = platform_folder_map.get(pf, FOLDERS["shows_do"])
    r2_net = platform_r2_map.get(pf, "drama_originals")
    generate_image(
        prompt=show["prompt"] + ", television show key art, professional broadcast quality, cinematic, no text overlays",
        local_path=folder / f"{slug}.jpg",
        r2_key=f"assets/shows/{r2_net}/{slug}.jpg",
        model="fal-ai/flux/dev",
        size="landscape_16_9",
        label=f"SHOW ART | {show['title']}",
    )
    time.sleep(0.5)

# ──────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("GENERATION COMPLETE")
print("="*60)
print(f"✅ Generated: {len(generated)} images")
print(f"❌ Failed:    {len(failed)} images")
print(f"💰 Total Cost: ${total_cost:.2f} / ${BUDGET_HARD_CAP:.2f}")
print(f"💵 Remaining Budget: ${BUDGET_HARD_CAP - total_cost:.2f}")

# Save manifest
manifest = {
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total_images": len(generated),
    "total_cost": round(total_cost, 3),
    "budget_cap": BUDGET_HARD_CAP,
    "budget_remaining": round(BUDGET_HARD_CAP - total_cost, 3),
    "assets": generated,
    "failures": failed,
}
manifest_path = BASE_OUT / "generation_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"\n📋 Manifest saved: {manifest_path}")

if failed:
    print(f"\n⚠️  Failed items:")
    for f in failed:
        print(f"   - {f['label']}: {f['error'][:80]}")

print("\n✅ All assets organized in platform_assets/")
print("✅ CDN URLs: https://media.rumbletv.com/assets/...")
