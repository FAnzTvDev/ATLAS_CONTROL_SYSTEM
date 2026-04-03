#!/usr/bin/env python3
"""
lyria_score_generator.py — ATLAS V36.5 Scene Undertone Generator

Generates continuous UNDERTONE tracks timed to story bible dialogue beats.

These are NOT standalone soundscapes per shot.
They are subtle musical underbeds — low-level continuous tonal layers —
composed to flow under the scene's dialogue as the authoritative bible beats
prescribe. The bible's dialogue timing drives the music; shots are only used
to compute beat offsets.

Architecture:
  1. Read story bible beats (dialogue, atmosphere, character_action)
  2. Compute beat timecodes from shot durations grouped by _beat_ref
  3. Build a Lyria undertone prompt describing the continuous arc across all beats
  4. Generate ONE continuous undertone per scene
  5. Output: soundscapes/{scene_id}_undertone.wav  (bible-timed music bed)
             soundscapes/{scene_id}_undertone_manifest.json  (beat timecodes)

The manifest is consumed by scene_audio_mixer.py which ducks the undertone
under dialogue and removes it from silence gaps.

Authority: ADVISORY — non-blocking. Failure never blocks generation.
"""

from __future__ import annotations

import json
import os
import hashlib
import time
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── API CONSTANTS ───────────────────────────────────────────────────────────
_GEMINI_MODEL   = "gemini-2.0-flash"
_MAX_DURATION   = 90    # seconds — cap for a single undertone track
_UNDERBED_LUFS  = -22   # target loudness for undertone (sits under dialogue)

# ── CHARACTER STYLE PROFILES ────────────────────────────────────────────────
CHARACTER_STYLES = {
    "ELEANOR VOSS": {
        "timbre":   "solo cello, sparse piano, distant church organ, string harmonics",
        "mood_tag": "grief, obsession, Victorian elegance, suppressed rage",
        "key_pref": "D minor / E minor",
    },
    "THOMAS BLACKWOOD": {
        "timbre":   "double bass, baritone strings, slow brass, sub-bass drone",
        "mood_tag": "authority, menace, controlled power, old money",
        "key_pref": "B minor / G minor",
    },
    "NADIA COLE": {
        "timbre":   "granular synthesis, reverse piano, tape delay, glitchy sparse percussion",
        "mood_tag": "curiosity, discovery, outsider clarity, analytical tension",
        "key_pref": "A minor modal / chromatic",
    },
    "HARRIET HARGROVE": {
        "timbre":   "acoustic guitar with vinyl crackle, parlour piano, soft violin",
        "mood_tag": "nostalgia, secrets, faded grandeur, frailty",
        "key_pref": "C major / F major, bittersweet",
    },
    "RAYMOND CROSS": {
        "timbre":   "low brass, dissonant strings, cold synth pad",
        "mood_tag": "threat, deception, predatory patience",
        "key_pref": "tritone, unresolved dissonance",
    },
}

_CHARACTER_ALIASES = {
    "ELEANOR": "ELEANOR VOSS",
    "THOMAS":  "THOMAS BLACKWOOD",
    "NADIA":   "NADIA COLE",
    "HARRIET": "HARRIET HARGROVE",
    "RAYMOND": "RAYMOND CROSS",
}

# ── LOCATION ACOUSTIC COLOURS ───────────────────────────────────────────────
LOCATION_ACOUSTICS = {
    "kitchen":       "warm intimate, short reverb, muffled wood",
    "library":       "hushed, dry, restrained — sounds absorbed by books",
    "foyer":         "marble reverb, high ceiling, cold air, long decay",
    "drawing_room":  "mid diffusion, velvet absorption, dust-muffled",
    "garden":        "open sky, no walls, wind, long natural decay",
    "bedroom":       "intimate, low-frequency, isolated, personal",
    "staircase":     "vertical space, echo between floors",
    "exterior":      "exposed, ambient bleed, no containment",
    "cemetery":      "cold stone, minimal decay, heavy silence",
}


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def generate_scene_undertone(
    project_dir: str | Path,
    scene_id: str,
    shot_plan_path: str | Path | None = None,
    story_bible_path: str | Path | None = None,
    force_regen: bool = False,
) -> dict:
    """
    Generate a continuous bible-timed undertone track for one scene.

    Returns manifest dict:
    {
        "scene_id":      "001",
        "audio_path":    "…/soundscapes/001_undertone.wav",  # None if failed
        "duration_s":    60.0,
        "beat_timecodes": [
            {"beat_index": 0, "beat_ref": "beat_1", "offset_s": 0.0,
             "dialogue": "She would have hated this…", "atmosphere": "…"},
            …
        ],
        "characters":    ["ELEANOR VOSS", "THOMAS BLACKWOOD"],
        "location":      "GRAND FOYER",
        "prompt_used":   "…",
        "source":        "lyria" | "cached" | "failed",
        "error":         null | "reason",
    }
    """
    project_dir   = Path(project_dir)
    soundscape_dir = project_dir / "soundscapes"
    soundscape_dir.mkdir(parents=True, exist_ok=True)

    out_wav       = soundscape_dir / f"{scene_id}_undertone.wav"
    manifest_path = soundscape_dir / f"{scene_id}_undertone_manifest.json"

    if not force_regen and manifest_path.exists() and out_wav.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            pass

    # ── Resolve file paths ──────────────────────────────────────────────────
    if shot_plan_path is None:
        shot_plan_path   = project_dir / "shot_plan.json"
    if story_bible_path is None:
        story_bible_path = project_dir / "story_bible.json"

    # ── Build context from bible beats + shot timings ──────────────────────
    bible_scene  = _load_bible_scene(story_bible_path, scene_id)
    scene_shots  = _load_shots_for_scene(shot_plan_path, scene_id)
    ctx          = _build_undertone_context(scene_id, bible_scene, scene_shots)

    # ── Build Lyria undertone prompt ────────────────────────────────────────
    prompt       = _build_undertone_prompt(ctx)
    prompt_hash  = hashlib.sha256(prompt.encode()).hexdigest()[:16]

    # ── Content-addressed cache ─────────────────────────────────────────────
    cache_wav = soundscape_dir / f"_cache_{prompt_hash}.wav"
    if not force_regen and cache_wav.exists():
        import shutil
        shutil.copy2(cache_wav, out_wav)
        manifest = _build_manifest(ctx, prompt, str(out_wav), "cached")
        manifest_path.write_text(json.dumps(manifest, indent=2))
        log.info(f"[Lyria] Scene {scene_id}: cache hit ({prompt_hash})")
        return manifest

    # ── Call Lyria ──────────────────────────────────────────────────────────
    audio_bytes, error = _call_lyria(prompt)

    if audio_bytes:
        out_wav.write_bytes(audio_bytes)
        cache_wav.write_bytes(audio_bytes)
        source = "lyria"
        log.info(f"[Lyria] Scene {scene_id}: undertone generated {len(audio_bytes):,} bytes")
    else:
        source = "failed"
        log.warning(f"[Lyria] Scene {scene_id}: failed — {error}")

    manifest = _build_manifest(ctx, prompt,
                                str(out_wav) if audio_bytes else None,
                                source, error=error)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def generate_episode_undertones(
    project_dir: str | Path,
    scene_ids: list[str] | None = None,
    shot_plan_path: str | Path | None = None,
    story_bible_path: str | Path | None = None,
) -> list[dict]:
    """
    Generate undertones for all scenes (or a subset).
    Non-blocking — failures included in results with source='failed'.
    """
    project_dir = Path(project_dir)
    if shot_plan_path is None:
        shot_plan_path = project_dir / "shot_plan.json"
    if story_bible_path is None:
        story_bible_path = project_dir / "story_bible.json"

    if scene_ids is None:
        scene_ids = _discover_scene_ids(shot_plan_path)

    results = []
    for sid in scene_ids:
        try:
            m = generate_scene_undertone(project_dir, sid,
                                          shot_plan_path, story_bible_path)
        except Exception as exc:
            m = {"scene_id": sid, "audio_path": None,
                 "source": "failed", "error": str(exc)}
        results.append(m)
        if m.get("source") == "lyria":
            time.sleep(1.5)   # courtesy delay between API calls

    return results


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER — bible beats are the authority
# ═══════════════════════════════════════════════════════════════════════════

def _build_undertone_context(scene_id: str,
                              bible_scene: dict,
                              scene_shots: list[dict]) -> dict:
    """
    Derive undertone context from bible beats.
    Shots are used ONLY to compute beat offsets from their durations.
    The bible's dialogue and atmosphere are the authoritative content.
    """
    bible_beats = bible_scene.get("beats", [])

    # ── Map shot durations to beats ─────────────────────────────────────────
    # shots carry _beat_index (0-based) or _beat_ref ("beat_1", "beat_2"…)
    # Accumulate duration per beat index, then compute cumulative offsets.
    beat_duration: dict[int, float] = {}
    for shot in scene_shots:
        idx = shot.get("_beat_index")
        if idx is None:
            # Fall back to parsing _beat_ref: "beat_1" → 0
            ref = shot.get("_beat_ref", "")
            try:
                idx = int(ref.split("_")[-1]) - 1
            except (ValueError, IndexError):
                idx = 0
        idx = int(idx)
        dur = float(shot.get("duration") or 10)
        beat_duration[idx] = beat_duration.get(idx, 0.0) + dur

    # Build ordered beat timecodes from bible beats
    cumulative = 0.0
    beat_timecodes = []
    for i, beat in enumerate(bible_beats):
        dur = beat_duration.get(i, 10.0)   # default 10s if no shots mapped
        beat_timecodes.append({
            "beat_index":     i,
            "beat_ref":       f"beat_{i+1}",
            "offset_s":       round(cumulative, 2),
            "duration_s":     round(dur, 2),
            "dialogue":       beat.get("dialogue") or "",
            "character_action": beat.get("character_action") or "",
            "atmosphere":     beat.get("atmosphere") or "",
            "description":    beat.get("description") or "",
        })
        cumulative += dur

    total_duration = min(round(cumulative), _MAX_DURATION)
    if total_duration < 15:
        total_duration = 30

    # ── Characters ─────────────────────────────────────────────────────────
    chars_present = bible_scene.get("characters_present", [])
    if not chars_present:
        char_set = set()
        for shot in scene_shots:
            for c in (shot.get("characters") or []):
                if c:
                    char_set.add(c.upper().strip())
        chars_present = sorted(char_set)

    # ── Location ────────────────────────────────────────────────────────────
    location = (bible_scene.get("location") or "").upper()

    return {
        "scene_id":       scene_id,
        "beat_timecodes": beat_timecodes,
        "characters":     [c.upper().strip() for c in chars_present],
        "location":       location,
        "duration_s":     total_duration,
        "scene_description": bible_scene.get("description") or "",
        "scene_atmosphere":  bible_scene.get("atmosphere") or "",
        "int_ext":           bible_scene.get("int_ext", "INT").upper(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# UNDERTONE PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _build_undertone_prompt(ctx: dict) -> str:
    """
    Build a Lyria prompt for a continuous dialogue undertone.

    The prompt describes:
    1. What an undertone IS (subtle underbed, not foreground)
    2. The scene's tonal identity from the characters present
    3. The location's acoustic character
    4. Each bible beat in temporal order — what's happening and what dialogue is spoken
    5. Mix instructions (LUFS, no competition with dialogue)
    """
    chars    = ctx["characters"]
    location = ctx["location"]
    duration = ctx["duration_s"]
    beats    = ctx["beat_timecodes"]
    desc     = ctx["scene_description"]
    atm      = ctx["scene_atmosphere"]

    # ── Character tonal blend ───────────────────────────────────────────────
    style_lines = []
    for c in chars:
        key = _resolve_char_key(c)
        if key in CHARACTER_STYLES:
            s = CHARACTER_STYLES[key]
            style_lines.append(f"  {key}: {s['timbre']}  [{s['mood_tag']}]  key: {s['key_pref']}")
    if not style_lines:
        style_lines = ["  gothic atmospheric chamber: solo cello, sparse piano, minor key"]

    # ── Location acoustics ──────────────────────────────────────────────────
    loc_key     = _resolve_location_key(location)
    loc_acoustic = LOCATION_ACOUSTICS.get(loc_key, "interior, contained")

    # ── Beat-by-beat description ────────────────────────────────────────────
    beat_lines = []
    for bt in beats:
        t_str  = f"{bt['offset_s']:.1f}s"
        dlg    = bt["dialogue"]
        action = bt["character_action"]
        atm_bt = bt["atmosphere"]

        line = f"  [{t_str}]  {action}"
        if dlg:
            line += f'\n           DIALOGUE: "{dlg}"'
        if atm_bt:
            line += f"\n           ATMOSPHERE: {atm_bt}"
        beat_lines.append(line)

    beat_block = "\n".join(beat_lines)

    # ── Assemble ────────────────────────────────────────────────────────────
    lines = [
        f"Compose {duration} seconds of continuous cinematic UNDERTONE music.",
        f"",
        f"DEFINITION: An undertone is a subtle musical underbed — NOT foreground music.",
        f"It sits beneath dialogue at low volume ({_UNDERBED_LUFS} LUFS), providing",
        f"tonal support and emotional colour without competing with the spoken voice.",
        f"It does not swell or draw attention. It breathes with the scene.",
        f"",
        f"SCENE: {desc}",
        f"LOCATION ACOUSTIC: {loc_acoustic}",
        f"OVERALL ATMOSPHERE: {atm}",
        f"",
        f"CHARACTER TONAL PALETTE (blend these voices into a single underbed):",
        "\n".join(style_lines),
        f"",
        f"BIBLE BEAT SEQUENCE — compose THE UNDERTONE TO SUPPORT EACH BEAT IN ORDER:",
        beat_block,
        f"",
        f"COMPOSITION RULES:",
        f"- One continuous piece — no hard breaks or restarts between beats",
        f"- Subtle tonal shifts at beat transitions, never jarring cuts",
        f"- During spoken dialogue: drop to near-silence (underbed only), let voice lead",
        f"- During action/atmosphere beats (no dialogue): slight swell, then recede",
        f"- No melody that would compete with a speaking voice",
        f"- No drums, no rhythm section, no percussion",
        f"- No vocals, no choral elements, no lyrics",
        f"- Prefer sustained tones, slow bowed strings, soft piano clusters, pad textures",
        f"- Final {min(8, duration//6):.0f} seconds: fade or open suspension — do not resolve",
        f"- Target mix level: {_UNDERBED_LUFS} LUFS integrated, peaks no higher than -16 dBFS",
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# LYRIA API CALL
# ═══════════════════════════════════════════════════════════════════════════

def _call_lyria(prompt: str) -> tuple[bytes | None, str | None]:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return None, "GOOGLE_API_KEY not set"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except ImportError:
        return None, "google-generativeai not installed"
    except Exception as e:
        return None, f"Lyria init: {e}"

    try:
        model    = genai.GenerativeModel(_GEMINI_MODEL)
        response = model.generate_content(
            prompt,
            generation_config={"response_modalities": ["AUDIO", "TEXT"]},
        )

        # Primary parts path
        for part in getattr(response, "parts", []):
            if hasattr(part, "inline_data") and \
               part.inline_data.mime_type.startswith("audio/"):
                return part.inline_data.data, None

        # Alternate candidates path
        for candidate in getattr(response, "candidates", []):
            for part in getattr(candidate.content, "parts", []):
                if hasattr(part, "inline_data") and \
                   part.inline_data.mime_type.startswith("audio/"):
                    return part.inline_data.data, None

        return None, "No audio data in Lyria response"

    except Exception as e:
        return None, f"Lyria generation error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# MANIFEST
# ═══════════════════════════════════════════════════════════════════════════

def _build_manifest(ctx: dict, prompt: str,
                    audio_path: str | None,
                    source: str,
                    error: str | None = None) -> dict:
    from datetime import datetime
    return {
        "scene_id":       ctx["scene_id"],
        "audio_path":     audio_path,
        "duration_s":     ctx["duration_s"],
        "beat_timecodes": ctx["beat_timecodes"],
        "characters":     ctx["characters"],
        "location":       ctx["location"],
        "prompt_used":    prompt,
        "source":         source,
        "error":          error,
        "generated_at":   datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# FILE LOADERS
# ═══════════════════════════════════════════════════════════════════════════

def _load_bible_scene(path: Path | str, scene_id: str) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data   = json.loads(path.read_text())
        scenes = data.get("scenes", [])
        for sc in scenes:
            sid = str(sc.get("scene_id", sc.get("id", "")))
            if sid == scene_id or sid.lstrip("0") == scene_id.lstrip("0"):
                return sc
    except Exception as e:
        log.warning(f"[Lyria] story_bible load error: {e}")
    return {}


def _load_shots_for_scene(path: Path | str, scene_id: str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        data   = json.loads(path.read_text())
        shots  = data if isinstance(data, list) else data.get("shots", [])
        prefix = f"{scene_id}_"
        return [s for s in shots if str(s.get("shot_id", "")).startswith(prefix)]
    except Exception as e:
        log.warning(f"[Lyria] shot_plan load error: {e}")
        return []


def _discover_scene_ids(path: Path | str) -> list[str]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        data  = json.loads(path.read_text())
        shots = data if isinstance(data, list) else data.get("shots", [])
        seen  = []
        for s in shots:
            sid   = str(s.get("shot_id", ""))
            scene = sid.split("_")[0] if "_" in sid else sid[:3]
            if scene and scene not in seen:
                seen.append(scene)
        return seen
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_char_key(name: str) -> str:
    u = name.upper().strip()
    if u in CHARACTER_STYLES:
        return u
    for alias, canon in _CHARACTER_ALIASES.items():
        if alias in u:
            return canon
    return u


def _resolve_location_key(location: str) -> str:
    l = location.lower()
    for key in LOCATION_ACOUSTICS:
        if key in l:
            return key
    if "kitchen" in l:            return "kitchen"
    if any(w in l for w in ("library", "study", "book")):  return "library"
    if any(w in l for w in ("foyer", "entrance", "hall")): return "foyer"
    if any(w in l for w in ("drawing", "sitting", "parlour")): return "drawing_room"
    if any(w in l for w in ("garden", "outside", "ext")):  return "garden"
    if any(w in l for w in ("bedroom", "master")):         return "bedroom"
    if "stair" in l:              return "staircase"
    if any(w in l for w in ("cemetery", "grave")):         return "cemetery"
    return "foyer"


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Generate Lyria undertone tracks from story bible timecodes"
    )
    parser.add_argument("project_dir")
    parser.add_argument("scene_ids", nargs="*",
                        help="Scene IDs (e.g. 001 002). Default: all scenes.")
    parser.add_argument("--force",   action="store_true",
                        help="Force regeneration ignoring cache")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompts, do not call Lyria API")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.exists():
        print(f"ERROR: {project_dir} not found", file=sys.stderr)
        sys.exit(1)

    shot_plan   = project_dir / "shot_plan.json"
    story_bible = project_dir / "story_bible.json"

    scene_ids = args.scene_ids or _discover_scene_ids(shot_plan)
    if not scene_ids:
        print("ERROR: no scene IDs found", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("\n=== DRY RUN — LYRIA UNDERTONE PROMPTS ===\n")
        for sid in scene_ids:
            shots    = _load_shots_for_scene(shot_plan, sid)
            bible_sc = _load_bible_scene(story_bible, sid)
            ctx      = _build_undertone_context(sid, bible_sc, shots)
            prompt   = _build_undertone_prompt(ctx)
            beats    = ctx["beat_timecodes"]
            print(f"── SCENE {sid}  ({ctx['duration_s']}s  "
                  f"{len(beats)} beats  chars: {ctx['characters']}) ──")
            print(prompt)
            print()
        sys.exit(0)

    print(f"\n🎼 Lyria Undertone Generator — {len(scene_ids)} scene(s)\n")
    results = generate_episode_undertones(project_dir, scene_ids,
                                           shot_plan, story_bible)
    ok  = [r for r in results if r.get("source") in ("lyria", "cached")]
    err = [r for r in results if r.get("source") == "failed"]
    print(f"\n✅ {len(ok)} generated   ❌ {len(err)} failed")
    for r in ok:
        print(f"   {r['scene_id']} → {r.get('audio_path')}  [{r['source']}]")
    for r in err:
        print(f"   {r['scene_id']} FAILED: {r.get('error')}")
