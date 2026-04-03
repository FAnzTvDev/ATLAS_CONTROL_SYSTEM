"""
ATLAS ElevenLabs TTS — V1.0 (2026-03-29)
==========================================
Dialogue audio generation via ElevenLabs REST API.

Architecture:
  - generate_dialogue_audio(text, voice_id, output_path) → per-shot .mp3
  - resolve_voice_id(character_name, cast_map) → voice_id string
  - generate_scene_dialogue_audio(scene_id, shots, project_dir, cast_map)
      → Dict[shot_id → audio_path]  (batch for a whole scene)

No SDK dependency — pure urllib REST.
Cache: skips API call if output_path already exists and is valid (>1KB).
Non-blocking: generate_dialogue_audio() returns {"success": False} on failure,
never raises. generate_scene_dialogue_audio() silently skips failed shots.

Voice IDs (from CLAUDE.md default assignments + cast_map override):
  Deep/authoritative lead:   21m00Tcm4TlvDq8ikWAM
  Clinical/precise:          EXAVITQu4vr4xnSDxMaL
  Robotic/system:            onwK4e9ZLuTAKqWW03F9

Character name → voice mapping is loaded first from cast_map["voice_id"],
then from _CHAR_VOICE_HINTS keyword matching, then falls back to default.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request as _req
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("atlas.elevenlabs_tts")

# ── DEFAULT VOICE IDs ─────────────────────────────────────────────────────────
_DEFAULT_VOICES: Dict[str, str] = {
    "default_male":    "21m00Tcm4TlvDq8ikWAM",   # deep, authoritative
    "default_female":  "EXAVITQu4vr4xnSDxMaL",   # clinical, clear
    "system":          "onwK4e9ZLuTAKqWW03F9",    # robotic / system
    "default":         "21m00Tcm4TlvDq8ikWAM",    # fallback
}

# Character name keyword → voice_id (overridden by cast_map if voice_id set there)
_CHAR_VOICE_HINTS: Dict[str, str] = {
    "marcus":     "21m00Tcm4TlvDq8ikWAM",
    "chen":       "EXAVITQu4vr4xnSDxMaL",
    "system":     "onwK4e9ZLuTAKqWW03F9",
    "thomas":     "21m00Tcm4TlvDq8ikWAM",
    "raymond":    "21m00Tcm4TlvDq8ikWAM",
    "eleanor":    "EXAVITQu4vr4xnSDxMaL",
    "nadia":      "EXAVITQu4vr4xnSDxMaL",
    "harriet":    "EXAVITQu4vr4xnSDxMaL",
}

# ElevenLabs API
_API_BASE       = "https://api.elevenlabs.io/v1"
_OUTPUT_FORMAT  = "mp3_44100_128"         # 128kbps MP3 — quality + small file size
_MODEL_ID       = "eleven_multilingual_v2"


# ── VOICE RESOLUTION ──────────────────────────────────────────────────────────

def resolve_voice_id(
    character_name: str,
    cast_map: Optional[Dict] = None,
) -> str:
    """
    Resolve the ElevenLabs voice_id for a character.

    Priority order:
      1. cast_map[character_name]["voice_id"]   (explicit override in project)
      2. _CHAR_VOICE_HINTS keyword match        (common ATLAS show characters)
      3. _DEFAULT_VOICES["default"]             (guaranteed fallback)
    """
    if cast_map:
        # Try exact match first
        if character_name in cast_map:
            vid = (cast_map[character_name] or {}).get("voice_id", "")
            if vid:
                return str(vid)
        # Try case-insensitive key match
        name_upper = character_name.upper()
        for k, v in cast_map.items():
            if k.upper() == name_upper and isinstance(v, dict) and v.get("voice_id"):
                return str(v["voice_id"])

    name_lower = character_name.lower()
    for hint_key, voice_id in _CHAR_VOICE_HINTS.items():
        if hint_key in name_lower:
            return voice_id

    return _DEFAULT_VOICES["default"]


# ── SINGLE-SHOT TTS ───────────────────────────────────────────────────────────

def generate_dialogue_audio(
    text: str,
    voice_id: str,
    output_path: str,
    api_key: Optional[str] = None,
    stability: float = 0.50,
    similarity_boost: float = 0.75,
    style: float = 0.00,          # 0 = natural speech, no exaggeration
    use_cache: bool = True,
) -> Dict:
    """
    Generate TTS audio for dialogue text via ElevenLabs REST API.

    Args:
        text:             Dialogue text to synthesize (will be stripped)
        voice_id:         ElevenLabs voice ID
        output_path:      Destination .mp3 file path
        api_key:          API key — falls back to ELEVENLABS_API_KEY env var
        stability:        Voice consistency 0–1 (0.5 = balanced)
        similarity_boost: Adherence to reference voice 0–1 (0.75 = close)
        style:            Style exaggeration 0–1 (0.0 = off for natural speech)
        use_cache:        Return cached file if output_path already exists and valid

    Returns:
        {"success": True,  "path": output_path, "source": "api"|"cache", "size_kb": N}
        {"success": False, "error": "description"}

    Never raises. All exceptions are caught and returned as error dicts.
    """
    text = (text or "").strip()
    if not text:
        return {"success": False, "error": "Empty dialogue text"}

    # Cache check
    if use_cache and os.path.exists(output_path):
        if os.path.getsize(output_path) > 1000:
            logger.debug(f"[TTS] Cache hit: {output_path}")
            return {"success": True, "path": output_path, "source": "cache"}

    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return {"success": False, "error": "ELEVENLABS_API_KEY not set in environment"}

    url = f"{_API_BASE}/text-to-speech/{voice_id}?output_format={_OUTPUT_FORMAT}"
    payload = json.dumps({
        "text": text,
        "model_id": _MODEL_ID,
        "voice_settings": {
            "stability":         stability,
            "similarity_boost":  similarity_boost,
            "style":             style,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    try:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        request = _req.Request(
            url,
            data=payload,
            headers={
                "Accept":         "audio/mpeg",
                "Content-Type":   "application/json",
                "xi-api-key":     api_key,
            },
            method="POST",
        )
        with _req.urlopen(request, timeout=60) as resp:
            audio_bytes = resp.read()

        if len(audio_bytes) < 1000:
            return {
                "success": False,
                "error": (
                    f"ElevenLabs returned {len(audio_bytes)} bytes — "
                    f"too small to be valid audio"
                ),
            }

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        size_kb = len(audio_bytes) / 1024
        logger.info(f"[TTS] {size_kb:.0f}KB → {output_path}")
        return {"success": True, "path": output_path, "source": "api", "size_kb": size_kb}

    except Exception as e:
        logger.warning(f"[TTS] API call failed for voice={voice_id}: {e}")
        return {"success": False, "error": str(e)}


# ── SCENE-LEVEL BATCH TTS ─────────────────────────────────────────────────────

def generate_scene_dialogue_audio(
    scene_id: str,
    shots: list,
    project_dir: Path,
    cast_map: Optional[Dict] = None,
    api_key: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate ElevenLabs TTS for every dialogue shot in a scene.

    Writes audio to: project_dir/dialogue_audio/{shot_id}_dialogue.mp3
    Skips shots with no dialogue_text or where generation failed.

    Args:
        scene_id:    e.g. "006"
        shots:       All shots from shot_plan.json (filtered to scene_id internally)
        project_dir: Project root directory (Path)
        cast_map:    Character → {voice_id, appearance, ...} map
        api_key:     ElevenLabs API key (falls back to env var)

    Returns:
        Dict[shot_id → audio_file_path] — only includes successfully generated shots.
    """
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    dialogue_dir = Path(project_dir) / "dialogue_audio"
    dialogue_dir.mkdir(exist_ok=True)

    shot_audio_map: Dict[str, str] = {}
    total = 0
    success = 0

    for shot in shots:
        sid = shot.get("shot_id", "")
        if not sid.startswith(scene_id + "_"):
            continue

        dialogue = (shot.get("dialogue_text") or "").strip()
        if not dialogue:
            continue

        total += 1
        chars    = shot.get("characters") or []
        primary  = chars[0] if chars else ""
        voice_id = resolve_voice_id(primary, cast_map)
        out_path = str(dialogue_dir / f"{sid}_dialogue.mp3")

        result = generate_dialogue_audio(
            text=dialogue,
            voice_id=voice_id,
            output_path=out_path,
            api_key=api_key,
        )

        if result.get("success"):
            shot_audio_map[sid] = out_path
            success += 1
            src = result.get("source", "api")
            size = result.get("size_kb", 0)
            icon = "⚡" if src == "cache" else "✅"
            print(
                f"  [TTS] {sid} ({primary or 'unknown'}): "
                f"{icon} {src} {size:.0f}KB → {os.path.basename(out_path)}"
            )
        else:
            print(f"  [TTS] {sid}: ⚠️  {result.get('error', 'unknown error')}")

    if total > 0:
        print(f"  [TTS] Scene {scene_id}: {success}/{total} dialogue shots synthesised")

    return shot_audio_map
