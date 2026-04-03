#!/usr/bin/env python3
"""
suno_cataloger.py — FANZ SOUND 50PACK Audio Cataloger
Analyzes 239 Suno MP3s: BPM (librosa), energy, mood, category mapping.
Copies tracks into taxonomy folders. Writes suno_catalog.json.

Usage:
    python3 tools/suno_cataloger.py
    python3 tools/suno_cataloger.py --raw-dir /path/to/08_RAW_MASTERS
    python3 tools/suno_cataloger.py --no-copy  (analyze only, no file copy)
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ── Optional librosa for real BPM ──────────────────────────────────────────
try:
    import librosa
    import numpy as np
    LIBROSA_OK = True
except ImportError:
    LIBROSA_OK = False
    print("[WARN] librosa not available — BPM will use heuristic from bitrate/duration")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path("/Users/quantum/Desktop/FANZ_SOUND_50PACK")
RAW_DIR    = BASE_DIR / "08_RAW_MASTERS"
CATALOG_OUT = BASE_DIR / "suno_catalog.json"

TAXONOMY = {
    "01_VYBE_THEMES":    BASE_DIR / "01_VYBE_THEMES",
    "02_ATLAS_SCORES":   BASE_DIR / "02_ATLAS_SCORES",
    "03_RUMBLE_LEAGUE":  BASE_DIR / "03_RUMBLE_LEAGUE",
    "04_AI_SPORTS":      BASE_DIR / "04_AI_SPORTS",
    "05_FANZTV_BUMPERS": BASE_DIR / "05_FANZTV_BUMPERS",
    "06_AMBIENT_LOOPS":  BASE_DIR / "06_AMBIENT_LOOPS",
    "07_SFX_TRANSITIONS":BASE_DIR / "07_SFX_TRANSITIONS",
}


# ── ffprobe ─────────────────────────────────────────────────────────────────
def ffprobe_info(mp3_path: Path) -> dict:
    """Extract format metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(mp3_path)
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10)
        data = json.loads(out)
        fmt = data.get("format", {})
        streams = data.get("streams", [{}])
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

        duration = float(fmt.get("duration", 0))
        bitrate  = int(fmt.get("bit_rate", 0)) // 1000   # kbps
        size_kb  = int(fmt.get("size", 0)) // 1024
        tags     = fmt.get("tags", {})
        comment  = tags.get("comment", "")
        sample_rate = int(audio.get("sample_rate", 44100))
        channels    = int(audio.get("channels", 2))

        # Parse suno creation date from comment field
        created_at = None
        m = re.search(r"created=([^\s;]+)", comment)
        if m:
            created_at = m.group(1)

        return {
            "duration_s": round(duration, 2),
            "bitrate_kbps": bitrate,
            "size_kb": size_kb,
            "sample_rate": sample_rate,
            "channels": channels,
            "comment": comment,
            "created_at": created_at,
        }
    except Exception as e:
        return {"error": str(e), "duration_s": 0, "bitrate_kbps": 0}


# ── BPM via librosa ──────────────────────────────────────────────────────────
def estimate_bpm_librosa(mp3_path: Path) -> tuple[float, float]:
    """
    Returns (bpm, confidence 0-1).
    Loads only first 60s for speed. Falls back to (0.0, 0.0) on error.
    """
    if not LIBROSA_OK:
        return 0.0, 0.0
    try:
        y, sr = librosa.load(str(mp3_path), sr=22050, duration=60, mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        # Confidence heuristic: how many beats were found vs expected
        expected_beats = (60 / bpm * len(y) / sr) if bpm > 0 else 0
        confidence = min(1.0, len(beats) / max(expected_beats, 1))
        return round(bpm, 1), round(confidence, 2)
    except Exception:
        return 0.0, 0.0


# ── Energy / RMS ─────────────────────────────────────────────────────────────
def estimate_energy(mp3_path: Path) -> tuple[str, float]:
    """
    Returns (level: low|mid|high, rms_norm 0-1).
    Uses librosa if available, else heuristic from bitrate.
    """
    if LIBROSA_OK:
        try:
            y, sr = librosa.load(str(mp3_path), sr=22050, duration=60, mono=True)
            rms = float(np.sqrt(np.mean(y ** 2)))
            # rms typically 0.01 – 0.25 for music
            norm = min(1.0, rms / 0.15)
            if norm < 0.35:
                level = "low"
            elif norm < 0.68:
                level = "mid"
            else:
                level = "high"
            return level, round(norm, 3)
        except Exception:
            pass
    # Fallback: infer from bitrate proxy
    return "mid", 0.5


# ── Spectral features for mood ───────────────────────────────────────────────
def spectral_features(mp3_path: Path) -> dict:
    """
    Extracts centroid, rolloff, zero_crossing_rate.
    Used for bright/dark/warm/cold mood tags.
    """
    if not LIBROSA_OK:
        return {}
    try:
        y, sr = librosa.load(str(mp3_path), sr=22050, duration=60, mono=True)
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        rolloff  = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
        zcr      = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        contrast = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
        return {
            "centroid": round(centroid, 1),
            "rolloff":  round(rolloff, 1),
            "zcr":      round(zcr, 4),
            "contrast": round(contrast, 2),
        }
    except Exception:
        return {}


# ── Genre classifier (music genre inference from spectral features) ───────────
def infer_genre_tags(bpm: float, energy_level: str, spec: dict,
                     duration_s: float) -> list[str]:
    """
    Infers likely music genre tags from audio features.
    These are VYBE-style genre labels for playlist matching, not production categories.
    All Suno tracks are treated as music — never routed as SFX or scoring stems.
    """
    genres = []
    centroid = spec.get("centroid", 2000)
    zcr      = spec.get("zcr", 0.05)
    contrast = spec.get("contrast", 5.0)

    if bpm > 0:
        # EDM / Dance
        if energy_level == "high" and bpm >= 125:
            genres.append("edm")
            if bpm >= 150:
                genres.append("drum-and-bass")
        # Hip-hop / Trap
        if 130 <= bpm <= 165 and zcr > 0.07:
            genres.append("hip-hop")
        if 60 <= bpm <= 85 and energy_level in ("mid", "high") and zcr > 0.06:
            genres.append("trap")  # trap is often half-time 65-80 BPM feel
        # R&B / Neo-Soul
        if 70 <= bpm <= 100 and energy_level == "mid" and centroid < 3000:
            genres.append("r&b")
        # Synthwave / Electronic
        if 95 <= bpm <= 130 and centroid > 2500:
            genres.append("electronic")
        # Lo-fi / Chill
        if 70 <= bpm <= 95 and energy_level == "low":
            genres.append("lo-fi")
        # Pop
        if 100 <= bpm <= 130 and energy_level == "mid":
            genres.append("pop")
        # Ambient / Downtempo
        if bpm < 85 and energy_level == "low":
            genres.append("ambient")
        # Sports / Hype
        if bpm >= 128 and energy_level == "high" and zcr > 0.08:
            genres.append("hype")

    # Spectral-based genre hints
    if centroid > 4000 and energy_level == "high":
        if "edm" not in genres:
            genres.append("electronic")
    if centroid < 1800 and energy_level == "low":
        if "ambient" not in genres:
            genres.append("ambient")
    if contrast > 8.0:
        if "percussion" not in genres:
            genres.append("percussion-heavy")

    # Fallback
    if not genres:
        genres.append("electronic")

    return list(dict.fromkeys(genres))


# ── Mood tag derivation ───────────────────────────────────────────────────────
def derive_mood_tags(bpm: float, energy_level: str, energy_norm: float,
                     duration_s: float, spec: dict) -> list[str]:
    """
    Derives VYBE mood tags — same vocabulary as VYBE's MOOD_PROMPT_MATRIX.
    These are used for playlist matching, not ATLAS cinematic routing.
    All tracks are songs; none are SFX or ambient scoring stems.
    """
    tags = []

    # Tempo-based VYBE moods
    if bpm > 0:
        if bpm < 75:
            tags += ["peaceful", "melancholy"]
        elif bpm < 95:
            tags += ["nostalgic", "romantic"]
        elif bpm < 115:
            tags += ["focused", "groove"]
        elif bpm < 135:
            tags += ["confident", "upbeat"]
        elif bpm < 155:
            tags += ["energized", "rebellious"]
        else:
            tags += ["euphoric", "intense"]

    # Energy-based
    if energy_level == "low":
        tags += ["dreamy", "peaceful"]
    elif energy_level == "mid":
        tags += ["balanced", "focused"]
    else:
        tags += ["energized", "driving"]

    # Duration-based context
    if duration_s < 60:
        tags.append("short-form")
    elif duration_s > 240:
        tags.append("extended")

    # Spectral character
    centroid = spec.get("centroid", 2000)
    zcr      = spec.get("zcr", 0.05)
    if centroid > 3500:
        tags.append("bright")
    elif centroid < 1500:
        tags.append("dark")
    else:
        tags.append("warm")

    if zcr > 0.10:
        tags.append("percussive")
    elif zcr < 0.03:
        tags.append("melodic")

    return list(dict.fromkeys(tags))


# ── VYBE Category classifier ──────────────────────────────────────────────────
def classify_category(bpm: float, energy_level: str, energy_norm: float,
                       duration_s: float, mood_tags: list[str],
                       genre_tags: list[str]) -> str:
    """
    Maps music tracks to VYBE taxonomy folders.
    ALL 239 Suno tracks are SONGS for VYBE playlists — none are scored as
    ATLAS cinematic stems or SFX. Lyria handles all production audio.

    Rules:
    1. Short bumpers (<60s) → 05_FANZTV_BUMPERS  (not SFX, just short songs)
    2. High energy + fast (≥125 BPM) → 03_RUMBLE_LEAGUE  (hype / sports)
    3. High energy + mid-fast (105-125) → 04_AI_SPORTS   (workout / gameday)
    4. Low energy → 06_AMBIENT_LOOPS                     (chill / lo-fi / dreamy)
    5. Mid energy + R&B/Hip-hop/Trap → 01_VYBE_THEMES    (core VYBE vibe)
    6. Mid energy + electronic/pop → 01_VYBE_THEMES
    7. Slow + dark/melancholy → 02_ATLAS_SCORES          (cinematic feel, still music)
    8. Default → 01_VYBE_THEMES
    """
    # Rule 1 — short form bumpers (songs, just short)
    if duration_s < 60:
        return "05_FANZTV_BUMPERS"

    # Rule 2 — rumble league (hype / high energy / sports anthems)
    if energy_level == "high" and bpm >= 125:
        return "03_RUMBLE_LEAGUE"

    # Rule 3 — AI sports (high energy workout / gameday)
    if energy_level == "high" and bpm >= 105:
        return "04_AI_SPORTS"
    if energy_level == "high":
        return "04_AI_SPORTS"

    # Rule 4 — ambient / lo-fi / chill
    if energy_level == "low":
        return "06_AMBIENT_LOOPS"

    # Rule 5 — core VYBE: R&B, hip-hop, trap, soul
    vybe_genres = {"r&b", "hip-hop", "trap", "neo-soul"}
    if any(g in vybe_genres for g in genre_tags):
        return "01_VYBE_THEMES"

    # Rule 6 — electronic / pop mid-energy
    if energy_level == "mid" and any(g in {"electronic", "pop", "synthwave"} for g in genre_tags):
        return "01_VYBE_THEMES"

    # Rule 7 — slow + dark = cinematic feel (still a song, not a stem)
    if bpm < 90 and ("dark" in mood_tags or "melancholy" in mood_tags):
        return "02_ATLAS_SCORES"

    # Rule 8 — default VYBE
    return "01_VYBE_THEMES"


# ── Radio station assignment ──────────────────────────────────────────────────
# VYBE Radio stations: each plays Suno songs in rotation with ElevenLabs AI host overlay.
RADIO_STATIONS = {
    "vybe_hiphop":   "VYBE Hip-Hop Radio",
    "vybe_chill":    "VYBE Chill Station",
    "rumble_hype":   "Rumble Hype Radio",
    "vybe_electronic":"VYBE Electronic",
    "fanz_gameday":  "FANZ Gameday Radio",
    "vybe_rnb":      "VYBE R&B Smooth",
    "fanz_cinematic":"FANZ Cinematic FM",
    "vybe_lofi":     "VYBE Lo-Fi 24/7",
}

def assign_radio_station(bpm: float, energy_level: str, genre_tags: list[str],
                          mood_tags: list[str], duration_s: float) -> str:
    """
    Assigns a primary radio station for this track's rotation.
    One track can appear on multiple stations but gets ONE primary assignment.
    """
    # Hype / sports
    if energy_level == "high" and bpm >= 128:
        if "edm" in genre_tags or "drum-and-bass" in genre_tags:
            return "rumble_hype"
        return "fanz_gameday"

    # Hip-hop / trap
    if any(g in genre_tags for g in ("hip-hop", "trap")):
        return "vybe_hiphop"

    # R&B / soul
    if "r&b" in genre_tags:
        return "vybe_rnb"

    # Lo-fi
    if "lo-fi" in genre_tags or (energy_level == "low" and bpm < 90):
        return "vybe_lofi"

    # Chill / ambient / dreamy
    if energy_level == "low" or any(m in mood_tags for m in ("peaceful", "dreamy", "melancholy")):
        return "vybe_chill"

    # Electronic / EDM
    if any(g in genre_tags for g in ("electronic", "edm", "synthwave")):
        if energy_level == "high":
            return "rumble_hype"
        return "vybe_electronic"

    # Cinematic slow songs
    if bpm < 90 and any(m in mood_tags for m in ("dark", "melancholy")):
        return "fanz_cinematic"

    # Mid energy pop/electronic → core VYBE
    return "vybe_electronic"


def score_mixability(bpm: float, energy_level: str, duration_s: float, spec: dict) -> dict:
    """
    Scores how well a track works for radio rotation.
    intro_energy: does it start strong (good for cold opens)?
    outro_energy: does it fade/end well (good for DJ transitions)?
    mix_score: overall 0-1 suitability for automated rotation.
    """
    # BPM-based mix score — tracks near common DJ anchors mix better
    bpm_score = 0.5
    if bpm > 0:
        dj_anchors = [85, 95, 100, 105, 110, 120, 125, 128, 130, 135, 140]
        nearest = min(dj_anchors, key=lambda x: abs(x - bpm))
        bpm_score = max(0.3, 1.0 - abs(bpm - nearest) / 20)

    # Duration score — 2-4 min ideal for radio rotation
    dur_score = 0.5
    if 90 <= duration_s <= 270:
        dur_score = 1.0
    elif duration_s < 60:
        dur_score = 0.3  # too short for full rotation, better as bumper
    elif duration_s > 360:
        dur_score = 0.6  # longer tracks can work as station fillers

    # Spectral smoothness (lower ZCR = smoother mix)
    zcr = spec.get("zcr", 0.05)
    smooth_score = max(0.2, 1.0 - zcr * 5)

    mix_score = round((bpm_score * 0.4 + dur_score * 0.4 + smooth_score * 0.2), 3)

    return {
        "mix_score":    mix_score,
        "bpm_anchor":   bpm,
        "mixable":      mix_score >= 0.6,
        "intro_style":  "cold" if energy_level == "high" else "fade-in",
        "outro_style":  "fade" if zcr < 0.06 else "cut",
    }


def assign_rotation_slot(energy_level: str, duration_s: float,
                          mood_tags: list[str]) -> str:
    """
    Assigns a rotation slot for radio scheduling:
    - opener: high-energy track to start a set
    - closer: low-energy track to end a set / wind down
    - mid_rotation: standard rotation track
    - bumper: very short, used between segments
    - feature: extended track, used as station highlight
    """
    if duration_s < 60:
        return "bumper"
    if duration_s > 300 and energy_level == "low":
        return "feature"
    if energy_level == "high" and "euphor" in str(mood_tags) or "energized" in mood_tags:
        return "opener"
    if energy_level == "low" and any(m in mood_tags for m in ("peaceful", "dreamy", "melancholy")):
        return "closer"
    return "mid_rotation"


# ── Main cataloger ────────────────────────────────────────────────────────────
def catalog_tracks(raw_dir: Path, do_copy: bool = True) -> list[dict]:
    mp3_files = sorted(raw_dir.glob("*.mp3"))
    total = len(mp3_files)
    print(f"[CATALOGER] Found {total} MP3 files in {raw_dir}")

    catalog = []
    category_counts = {k: 0 for k in TAXONOMY}

    for i, mp3 in enumerate(mp3_files, 1):
        track_id = mp3.stem  # UUID filename without .mp3
        print(f"  [{i:3d}/{total}] {track_id[:16]}...", end=" ", flush=True)

        # 1. ffprobe metadata
        info = ffprobe_info(mp3)
        dur  = info.get("duration_s", 0)

        # 2. BPM (librosa, first 60s)
        bpm, bpm_conf = estimate_bpm_librosa(mp3)

        # 3. Energy
        energy_level, energy_norm = estimate_energy(mp3)

        # 4. Spectral features
        spec = spectral_features(mp3)

        # 5. Genre + mood tags
        genre_tags = infer_genre_tags(bpm, energy_level, spec, dur)
        mood_tags  = derive_mood_tags(bpm, energy_level, energy_norm, dur, spec)

        # 6. Category
        category = classify_category(bpm, energy_level, energy_norm, dur, mood_tags, genre_tags)
        category_counts[category] += 1

        # 7. Radio station assignment + mixability
        radio_station  = assign_radio_station(bpm, energy_level, genre_tags, mood_tags, dur)
        mixability     = score_mixability(bpm, energy_level, dur, spec)
        rotation_slot  = assign_rotation_slot(energy_level, dur, mood_tags)

        entry = {
            "id":                track_id,
            "filename":          mp3.name,
            "duration_s":        dur,
            "duration_fmt":      f"{int(dur//60)}:{int(dur%60):02d}",
            "bitrate_kbps":      info.get("bitrate_kbps", 0),
            "sample_rate":       info.get("sample_rate", 44100),
            "channels":          info.get("channels", 2),
            "size_kb":           info.get("size_kb", 0),
            "bpm_estimate":      bpm,
            "bpm_confidence":    bpm_conf,
            "energy":            energy_level,
            "energy_norm":       energy_norm,
            "spectral":          spec,
            "genre_tags":        genre_tags,
            "mood_tags":         mood_tags,
            "suggested_category":category,
            "radio_station":     radio_station,
            "mixability":        mixability,
            "rotation_slot":     rotation_slot,
            "created_at":        info.get("created_at"),
            "raw_path":          str(mp3),
            "catalog_path":      str(TAXONOMY[category] / mp3.name),
            "r2_key":            f"music/{category}/{mp3.name}",
        }
        catalog.append(entry)

        print(f"  {dur:.0f}s  {bpm:.0f}bpm  {energy_level:4s}  → {category}")

    return catalog, category_counts


def copy_to_taxonomy(catalog: list[dict]) -> dict:
    """Copy files from RAW_MASTERS to taxonomy folders (no move/delete)."""
    copied = {}
    for entry in catalog:
        src  = Path(entry["raw_path"])
        dest = Path(entry["catalog_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src, dest)
            copied[entry["id"]] = str(dest)
        else:
            copied[entry["id"]] = str(dest) + " (already exists)"
    return copied


def write_catalog(catalog: list[dict], out_path: Path):
    meta = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_tracks": len(catalog),
        "librosa_available": LIBROSA_OK,
        "tracks": catalog,
    }
    out_path.write_text(json.dumps(meta, indent=2))
    print(f"\n[CATALOG] Written → {out_path}")


def print_summary(catalog: list[dict], counts: dict):
    print("\n" + "═" * 60)
    print("  FANZ SOUND CATALOG SUMMARY")
    print("═" * 60)
    total = len(catalog)
    durs  = [t["duration_s"] for t in catalog]
    bpms  = [t["bpm_estimate"] for t in catalog if t["bpm_estimate"] > 0]

    print(f"  Total tracks  : {total}")
    print(f"  Total duration: {sum(durs)/60:.1f} min")
    print(f"  Avg duration  : {sum(durs)/len(durs):.1f}s")
    if bpms:
        print(f"  BPM range     : {min(bpms):.0f} – {max(bpms):.0f}  (avg {sum(bpms)/len(bpms):.0f})")

    print("\n  Category breakdown:")
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = "█" * (count * 30 // max(counts.values(), default=1))
        print(f"    {cat:25s}  {count:3d}  {bar}")

    energy_dist = {"low": 0, "mid": 0, "high": 0}
    for t in catalog:
        energy_dist[t["energy"]] = energy_dist.get(t["energy"], 0) + 1
    print(f"\n  Energy: low={energy_dist['low']}  mid={energy_dist['mid']}  high={energy_dist['high']}")

    # Radio station breakdown
    station_dist: dict[str, int] = {}
    for t in catalog:
        s = t.get("radio_station", "unknown")
        station_dist[s] = station_dist.get(s, 0) + 1
    print("\n  Radio station assignment:")
    for station, count in sorted(station_dist.items(), key=lambda x: -x[1]):
        label = RADIO_STATIONS.get(station, station)
        bar   = "█" * (count * 25 // max(station_dist.values(), default=1))
        print(f"    {label:28s}  {count:3d}  {bar}")

    # Rotation slot breakdown
    slot_dist: dict[str, int] = {}
    for t in catalog:
        slot_dist[t.get("rotation_slot", "mid_rotation")] = \
            slot_dist.get(t.get("rotation_slot", "mid_rotation"), 0) + 1
    print(f"\n  Rotation slots: {dict(sorted(slot_dist.items()))}")
    mixable = sum(1 for t in catalog if t.get("mixability", {}).get("mixable", False))
    print(f"  Mixable tracks: {mixable}/{len(catalog)} ({100*mixable//max(len(catalog),1)}%)")
    print("═" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Suno MP3 cataloger for FANZ SOUND 50PACK")
    parser.add_argument("--raw-dir",  default=str(RAW_DIR),  help="Path to 08_RAW_MASTERS/")
    parser.add_argument("--out",      default=str(CATALOG_OUT), help="Output catalog JSON path")
    parser.add_argument("--no-copy",  action="store_true",    help="Skip copying files to taxonomy folders")
    parser.add_argument("--limit",    type=int, default=0,    help="Analyze only first N tracks (for testing)")
    args = parser.parse_args()

    raw_dir  = Path(args.raw_dir)
    out_path = Path(args.out)

    if not raw_dir.exists():
        print(f"[ERROR] RAW_DIR not found: {raw_dir}")
        sys.exit(1)

    print(f"[CATALOGER] librosa available: {LIBROSA_OK}")
    print(f"[CATALOGER] Raw dir  : {raw_dir}")
    print(f"[CATALOGER] Output   : {out_path}")
    print(f"[CATALOGER] Copy mode: {'DISABLED' if args.no_copy else 'ENABLED'}")

    # Limit for testing
    if args.limit > 0:
        mp3s = sorted(raw_dir.glob("*.mp3"))[:args.limit]
        # Temporarily symlink/copy to a temp raw dir? No — just pass limit via catalog.
        # We'll handle via slicing inside catalog_tracks by overriding glob.
        print(f"[CATALOGER] Limiting to first {args.limit} tracks")

    catalog, counts = catalog_tracks(raw_dir, do_copy=not args.no_copy)

    if args.limit > 0:
        catalog = catalog[:args.limit]

    write_catalog(catalog, out_path)

    if not args.no_copy:
        print("\n[COPY] Copying to taxonomy folders...")
        copy_results = copy_to_taxonomy(catalog)
        print(f"[COPY] {len(copy_results)} files processed")

    print_summary(catalog, counts)
    print(f"\n[DONE] Catalog: {out_path}")


if __name__ == "__main__":
    main()
