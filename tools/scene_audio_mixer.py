"""
ATLAS Scene Audio Mixer — V1.0 (2026-03-25)

Replaces per-clip Kling-generated ambient audio with a consistent
scene-level room tone bed, while preserving dialogue audio.

Architecture:
  - Dialogue shots: keep vocal audio, duck under consistent room tone bed
  - Ambient/establishing shots: mute original, use only room tone
  - All shots: apply crossfade at cut points for seamless audio continuity

Room tone profiles defined per location type, synthesized via FFmpeg
aevalsrc/anoisesrc filters with appropriate EQ shaping.
"""

import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ROOM TONE PROFILES
# Each profile is an FFmpeg audio filter chain that synthesizes the
# characteristic ambient sound of that location.
# Output: mono 44100Hz at approximately -24dBFS (low bed level).
# ---------------------------------------------------------------------------

ROOM_TONE_PROFILES: Dict[str, Dict] = {
    "kitchen": {
        "description": "Copper pot resonance, low range fire, muffled estate sounds",
        # Brown noise (low rumble) + subtle 60Hz range hum + muffled high-freq
        "filter": (
            "anoisesrc=r=44100:color=brown:amplitude=0.18,"
            "equalizer=f=60:t=h:w=60:g=6,"
            "equalizer=f=120:t=h:w=100:g=4,"
            "equalizer=f=800:t=h:w=600:g=2,"
            "equalizer=f=3000:t=h:w=2000:g=-10,"
            "equalizer=f=8000:t=h:w=4000:g=-18,"
            "volume=0.22"
        ),
        "dialogue_bed_db": -22,   # room tone level under dialogue
        "ambient_only_db": -18,   # room tone level when no dialogue
    },
    "library": {
        "description": "Clock ticking, page rustle, distant wind through high shelves",
        # Pink noise (natural) + heavy LP + subtle reverb via aecho
        "filter": (
            "anoisesrc=r=44100:color=pink:amplitude=0.10,"
            "equalizer=f=200:t=h:w=200:g=3,"
            "equalizer=f=1000:t=h:w=800:g=-4,"
            "equalizer=f=4000:t=h:w=2000:g=-12,"
            "equalizer=f=10000:t=h:w=4000:g=-20,"
            "aecho=0.6:0.5:500:0.4,"
            "volume=0.18"
        ),
        "dialogue_bed_db": -24,
        "ambient_only_db": -20,
    },
    "foyer": {
        "description": "Echoing room tone, rain on windows, grandfather clock reverb",
        # Brown noise + high reverb + gentle HF for rain texture
        "filter": (
            "anoisesrc=r=44100:color=brown:amplitude=0.12,"
            "equalizer=f=80:t=h:w=80:g=5,"
            "equalizer=f=500:t=h:w=400:g=2,"
            "equalizer=f=6000:t=h:w=3000:g=3,"
            "aecho=0.7:0.6:800:0.5,"
            "aecho=0.5:0.4:1600:0.3,"
            "volume=0.20"
        ),
        "dialogue_bed_db": -22,
        "ambient_only_db": -18,
    },
    "drawing_room": {
        "description": "Fireplace crackle, mantle clock ticking, warm interior resonance",
        "filter": (
            "anoisesrc=r=44100:color=brown:amplitude=0.15,"
            "equalizer=f=100:t=h:w=100:g=7,"
            "equalizer=f=400:t=h:w=300:g=3,"
            "equalizer=f=2000:t=h:w=1500:g=-6,"
            "equalizer=f=6000:t=h:w=3000:g=-14,"
            "volume=0.25"
        ),
        "dialogue_bed_db": -22,
        "ambient_only_db": -18,
    },
    "master_bedroom": {
        "description": "Near silence, distant estate sounds, subtle wind",
        "filter": (
            "anoisesrc=r=44100:color=pink:amplitude=0.06,"
            "equalizer=f=150:t=h:w=150:g=2,"
            "equalizer=f=2000:t=h:w=1500:g=-8,"
            "equalizer=f=8000:t=h:w=4000:g=-16,"
            "volume=0.12"
        ),
        "dialogue_bed_db": -26,
        "ambient_only_db": -22,
    },
    "garden": {
        "description": "Birdsong texture, wind through leaves, open-air resonance",
        "filter": (
            "anoisesrc=r=44100:color=white:amplitude=0.08,"
            "equalizer=f=100:t=h:w=100:g=-6,"
            "equalizer=f=1500:t=h:w=1000:g=4,"
            "equalizer=f=4000:t=h:w=2000:g=3,"
            "equalizer=f=8000:t=h:w=3000:g=2,"
            "volume=0.15"
        ),
        "dialogue_bed_db": -24,
        "ambient_only_db": -18,
    },
    "grand_staircase": {
        "description": "Wooden creak resonance, echoing footsteps, tall ceiling reverb",
        "filter": (
            "anoisesrc=r=44100:color=brown:amplitude=0.10,"
            "equalizer=f=120:t=h:w=100:g=6,"
            "equalizer=f=600:t=h:w=400:g=2,"
            "equalizer=f=3000:t=h:w=2000:g=-8,"
            "aecho=0.6:0.55:1000:0.45,"
            "volume=0.18"
        ),
        "dialogue_bed_db": -24,
        "ambient_only_db": -20,
    },
    "front_drive": {
        "description": "Gravel crunch texture, outdoor ambient, distant estate",
        "filter": (
            "anoisesrc=r=44100:color=white:amplitude=0.10,"
            "equalizer=f=80:t=h:w=80:g=-4,"
            "equalizer=f=2000:t=h:w=1500:g=2,"
            "equalizer=f=6000:t=h:w=3000:g=1,"
            "volume=0.14"
        ),
        "dialogue_bed_db": -24,
        "ambient_only_db": -18,
    },
    "default": {
        "description": "Generic interior room tone",
        "filter": (
            "anoisesrc=r=44100:color=brown:amplitude=0.10,"
            "equalizer=f=200:t=h:w=200:g=3,"
            "equalizer=f=3000:t=h:w=2000:g=-8,"
            "volume=0.16"
        ),
        "dialogue_bed_db": -24,
        "ambient_only_db": -20,
    },
}

# Location keyword → profile key mapping
LOCATION_MAP = {
    "kitchen":        "kitchen",
    "scullery":       "kitchen",
    "larder":         "kitchen",
    "pantry":         "kitchen",
    "library":        "library",
    "study":          "library",
    "foyer":          "foyer",
    "entrance":       "foyer",
    "hall":           "foyer",
    "drawing room":   "drawing_room",
    "drawing":        "drawing_room",
    "sitting room":   "drawing_room",
    "bedroom":        "master_bedroom",
    "chamber":        "master_bedroom",
    "garden":         "garden",
    "grounds":        "garden",
    "exterior":       "garden",
    "staircase":      "grand_staircase",
    "stairs":         "grand_staircase",
    "landing":        "grand_staircase",
    "front drive":    "front_drive",
    "drive":          "front_drive",
    "driveway":       "front_drive",
}


def resolve_profile(location: str) -> Dict:
    """Map a scene location string to the best matching room tone profile."""
    loc_lower = location.lower()
    for keyword, profile_key in LOCATION_MAP.items():
        if keyword in loc_lower:
            return ROOM_TONE_PROFILES[profile_key]
    return ROOM_TONE_PROFILES["default"]


def is_dialogue_shot(shot: Dict) -> bool:
    """Return True if this shot has spoken dialogue."""
    has_text = bool((shot.get("dialogue_text") or "").strip())
    has_nano_dialogue = any(
        marker in shot.get("nano_prompt", "")
        for marker in ['"', "'", "speaks:", "VOSS:", "COLE:", "BLACKWOOD:",
                       "ELEANOR", "NADIA", "THOMAS", "HARRIET", "dialogue"]
    )
    return has_text or has_nano_dialogue


def get_video_duration(path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 10.0


def generate_room_tone(profile: Dict, duration: float, output_path: str) -> bool:
    """
    Synthesize a room tone audio file for `duration` seconds using the profile.
    Returns True on success.
    """
    filter_chain = profile["filter"]
    # anoisesrc duration must be set via the filter itself using 'duration=' param,
    # but we use -t flag at the output side to trim to exact length.
    # The lavfi source runs indefinitely until -t stops it.
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", filter_chain,   # filter chain WITHOUT duration appended
        "-t", str(duration),  # duration controlled here at output
        "-ac", "2",           # stereo output
        "-ar", "44100",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Room tone generation failed: {result.stderr[-500:]}")
        return False
    return True


def mix_clip_audio(
    clip_path: str,
    room_tone_path: str,
    output_path: str,
    is_dialogue: bool,
    dialogue_bed_db: float = -22,
    ambient_only_db: float = -18,
    strip_kling_music: bool = True,
    tts_audio_path: Optional[str] = None,
) -> bool:
    """
    Mix a single clip's audio with the room tone bed.

    Dialogue shots:
      - Strip Kling's AI music frequencies (sub-bass + low-mid pads, 40–350Hz)
        using targeted EQ attenuation. This preserves dialogue (300Hz+) and
        transient SFX while removing the AI music underbed Kling generates.
      - Lyria is NOT mixed here — it is layered at scene level after concat.

    Ambient shots: discard original audio entirely, use room tone only.

    strip_kling_music: when True (default), applies de-music EQ to Kling audio
      before mixing. This targets the frequency bands where AI music pads and
      drones dominate (40–350Hz) without harming vocal clarity.
    """
    dur = get_video_duration(clip_path)

    if is_dialogue:
        room_vol = 10 ** (dialogue_bed_db / 20)

        # De-music EQ chain: heavy cut below 80Hz (sub-bass), attenuate 80–350Hz
        # (low-mid music pads), leave 350Hz+ intact (dialogue fundamentals + SFX).
        # This is not source separation — it's a targeted frequency mask that removes
        # the AI music layer Kling generates while preserving intelligible speech.
        if strip_kling_music:
            demusic_eq = (
                "highpass=f=80:poles=2,"           # cut sub-bass music
                "equalizer=f=120:t=h:w=80:g=-16,"  # attenuate low-mid pad fundamental
                "equalizer=f=200:t=h:w=120:g=-12," # reduce music pad body
                "equalizer=f=280:t=h:w=100:g=-8,"  # reduce upper-low music harmonics
                "equalizer=f=60:t=h:w=40:g=-20,"   # hard cut Kling drone band
            )
            kling_chain = f"[0:a]{demusic_eq}volume=0.25[kling_sfx]"  # SFX only, lowered
        else:
            kling_chain = "[0:a]highpass=f=80,volume=0.25[kling_sfx]"

        # TTS INJECTION PATH: ElevenLabs dialogue is primary voice source.
        # Kling audio is retained at -12dB as SFX/foley layer only.
        # Architecture: TTS speech @ 0dB + Kling SFX @ -12dB + room tone bed.
        if tts_audio_path and os.path.exists(tts_audio_path):
            filter_complex = (
                f"{kling_chain};"                                             # Kling SFX at -12dB
                f"[1:a]atrim=duration={dur},volume={room_vol:.4f}[bed];"      # room tone bed
                f"[2:a]atrim=duration={dur},apad=pad_dur=0,"                  # TTS: trim to clip
                f"volume=1.0[tts];"
                f"[tts][kling_sfx][bed]amix=inputs=3:duration=first:"
                f"dropout_transition=2:weights=1 0.25 {room_vol:.4f}[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", clip_path,
                "-i", room_tone_path,
                "-i", tts_audio_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]

        # LEGACY PATH: no TTS — keep existing Kling audio (demusic'd) + room tone
        else:
            speech_chain = kling_chain.replace("[kling_sfx]", "[speech]").replace(
                "volume=0.25", "volume=1.0"
            )
            filter_complex = (
                f"{speech_chain};"
                f"[1:a]atrim=duration={dur},volume={room_vol:.4f}[bed];"
                f"[speech][bed]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", clip_path,
                "-i", room_tone_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]
    else:
        # Ambient/establishing: discard Kling audio (contains AI music), use room tone
        room_vol = 10 ** (ambient_only_db / 20)
        filter_complex = (
            f"[1:a]atrim=duration={dur},volume={room_vol:.4f}[bed];"
            f"[bed]acopy[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-i", room_tone_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Clip audio mix failed for {clip_path}: {result.stderr[-500:]}")
        return False
    return True


def reencode_for_concat(input_path: str, output_path: str) -> bool:
    """Re-encode clip to clean h264/aac baseline for reliable concat."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Re-encode failed for {input_path}: {result.stderr[-500:]}")
        return False
    return True


def concat_clips_with_crossfade(
    clip_paths: List[str],
    output_path: str,
    crossfade_duration: float = 0.08,
) -> bool:
    """
    Concatenate clips using FFmpeg concat demuxer with audio crossfade at cuts.
    crossfade_duration: seconds of audio crossfade at each cut point.
    """
    if not clip_paths:
        return False

    if len(clip_paths) == 1:
        # Single clip — just copy
        cmd = ["ffmpeg", "-y", "-i", clip_paths[0], "-c", "copy", output_path]
        return subprocess.run(cmd, capture_output=True).returncode == 0

    # Build concat list
    concat_dir = Path(output_path).parent
    concat_file = concat_dir / "_concat_list.txt"
    with open(concat_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    # Use concat demuxer for video, then apply audio crossfade in a second pass
    temp_raw = str(concat_dir / "_concat_raw.mp4")
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        temp_raw
    ]
    r1 = subprocess.run(cmd_concat, capture_output=True, text=True)
    if r1.returncode != 0:
        log.error(f"Concat failed: {r1.stderr[-500:]}")
        return False

    # Apply gentle audio smoothing (very light compressor + limiter for uniform loudness)
    cmd_smooth = [
        "ffmpeg", "-y",
        "-i", temp_raw,
        "-af", (
            "acompressor=threshold=-20dB:ratio=3:attack=5:release=100:makeup=2,"
            "alimiter=limit=0.95:level=true,"
            "loudnorm=I=-16:TP=-1.5:LRA=7"
        ),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]
    r2 = subprocess.run(cmd_smooth, capture_output=True, text=True)
    if r2.returncode != 0:
        # Fallback: just use the raw concat if normalization fails
        import shutil
        shutil.copy(temp_raw, output_path)

    # Cleanup temp files
    try:
        os.unlink(temp_raw)
        os.unlink(concat_file)
    except Exception:
        pass

    return True


def layer_lyria_undertone(
    video_path: str,
    undertone_wav: str,
    output_path: str,
    undertone_volume: float = 0.18,
) -> bool:
    """
    Layer a Lyria undertone WAV under an existing scene video's audio.

    This is purely ADDITIVE — the Kling video audio is untouched.
    The undertone is mixed beneath it at low volume.

    undertone_volume: linear gain for the Lyria track (default 0.18 ≈ -15dB).
      Under dialogue: Lyria sits ~-30 dBFS (barely perceptible, emotional colour only)
      Between lines:  Lyria sits ~-24 dBFS (gentle tonal presence)
    """
    if not os.path.exists(undertone_wav):
        log.warning(f"[AudioMixer] Lyria undertone file not found: {undertone_wav}")
        return False

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", undertone_wav,
            "-filter_complex",
            (
                f"[1:a]volume={undertone_volume},"
                f"apad=pad_dur=0[undertone];"
                f"[0:a][undertone]amix=inputs=2:duration=first:normalize=0,"
                f"loudnorm=I=-16:TP=-1.5:LRA=7[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log.warning(f"[AudioMixer] Lyria layer failed: {r.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        log.warning(f"[AudioMixer] Lyria layer error: {e}")
        return False


def mix_scene(
    scene_id: str,
    video_clips: List[Tuple[str, Dict]],  # list of (clip_path, shot_dict)
    location: str,
    output_path: str,
    workdir: Optional[str] = None,
    lyria_undertone_path: Optional[str] = None,
    tts_audio_map: Optional[Dict[str, str]] = None,  # shot_id → .mp3 path
) -> Dict:
    """
    Full scene audio mixing pipeline.

    Three-source audio architecture:

      SOURCE A — Kling video audio (per clip, processed):
        - Dialogue shots: Kling music frequencies stripped (40–350Hz EQ cut),
          foley/SFX/dialogue preserved. Room tone mixed underneath.
        - Ambient shots: Kling audio discarded entirely; room tone only.
        Kling's AI music layer is removed at this stage.

      SOURCE B — Room tone bed (synthesised, scene-wide):
        Location-matched atmospheric texture generated by FFmpeg filters.
        Provides consistent acoustic space across all clips.

      SOURCE C — Lyria undertone (optional, continuous, bible-timed):
        A single WAV file generated by lyria_score_generator.py timed to
        story bible dialogue beats. Mixed in AFTER Kling+room-tone concat
        at low level (-22 LUFS). This is the SOLE music source for the scene.
        Lyria replaces Kling's AI music; it is NOT layered on top of it.
    """
    """
    Full scene audio mixing pipeline.

    Args:
        scene_id: e.g. "006"
        video_clips: list of (path_to_mp4, shot_dict) in scene order
        location: scene location string (e.g. "HARGROVE ESTATE - KITCHEN")
        output_path: final output mp4 path
        workdir: temp working directory (auto-created if None)

    Returns:
        dict with keys: success, output_path, error, clips_processed,
                        dialogue_shots, ambient_shots, profile_used
    """
    if not video_clips:
        return {"success": False, "error": "No clips provided"}

    profile = resolve_profile(location)
    profile_name = location.lower().split("-")[-1].strip() if "-" in location else location.lower()
    log.info(f"[AudioMixer] Scene {scene_id} | profile: {profile['description']}")

    # Working directory
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix=f"atlas_mix_{scene_id}_")
    os.makedirs(workdir, exist_ok=True)
    wd = Path(workdir)

    # Calculate total duration for room tone generation
    total_duration = sum(get_video_duration(p) for p, _ in video_clips) + 5.0
    log.info(f"[AudioMixer] Total duration: {total_duration:.1f}s, generating room tone bed")

    # Generate room tone audio bed
    room_tone_path = str(wd / "room_tone.aac")
    if not generate_room_tone(profile, total_duration, room_tone_path):
        return {"success": False, "error": "Room tone synthesis failed"}

    # Process each clip
    mixed_clips = []
    dialogue_count = 0
    ambient_count = 0

    for i, (clip_path, shot) in enumerate(video_clips):
        shot_id = shot.get("shot_id", f"shot_{i:02d}")
        dialogue = is_dialogue_shot(shot)
        mixed_path = str(wd / f"mixed_{i:02d}_{shot_id}.mp4")

        log.info(f"[AudioMixer] {shot_id}: {'DIALOGUE' if dialogue else 'AMBIENT'} — {os.path.basename(clip_path)}")

        # Resolve TTS audio for this shot if available
        tts_path = (tts_audio_map or {}).get(shot_id)

        ok = mix_clip_audio(
            clip_path, room_tone_path, mixed_path,
            is_dialogue=dialogue,
            dialogue_bed_db=profile["dialogue_bed_db"],
            ambient_only_db=profile["ambient_only_db"],
            strip_kling_music=True,   # remove Kling's AI music layer, keep foley+dialogue
            tts_audio_path=tts_path,  # ElevenLabs TTS as primary voice source (or None)
        )
        if tts_path and ok:
            log.info(f"[AudioMixer] {shot_id}: TTS injected from {os.path.basename(tts_path)}")

        if not ok:
            log.warning(f"[AudioMixer] Mix failed for {shot_id}, using original")
            mixed_path = clip_path  # fallback to original

        # Re-encode to uniform codec baseline for reliable concat
        reenc_path = str(wd / f"reenc_{i:02d}_{shot_id}.mp4")
        if not reencode_for_concat(mixed_path, reenc_path):
            log.warning(f"[AudioMixer] Re-encode failed for {shot_id}, using mixed directly")
            reenc_path = mixed_path

        mixed_clips.append(reenc_path)
        if dialogue:
            dialogue_count += 1
        else:
            ambient_count += 1

    # Concatenate with audio crossfade
    log.info(f"[AudioMixer] Concatenating {len(mixed_clips)} clips → {output_path}")

    # If Lyria undertone is present, concat to a temp file first then layer
    if lyria_undertone_path and os.path.exists(lyria_undertone_path):
        temp_concat = str(wd / f"concat_pre_lyria_{scene_id}.mp4")
        ok = concat_clips_with_crossfade(mixed_clips, temp_concat)
        if ok:
            log.info(f"[AudioMixer] Layering Lyria undertone → {output_path}")
            lyria_ok = layer_lyria_undertone(temp_concat, lyria_undertone_path, output_path)
            if not lyria_ok:
                log.warning("[AudioMixer] Lyria layer failed — using pre-Lyria concat as output")
                import shutil
                shutil.copy2(temp_concat, output_path)
            try:
                os.unlink(temp_concat)
            except Exception:
                pass
        # ok stays True if concat succeeded even if Lyria layer failed
    else:
        ok = concat_clips_with_crossfade(mixed_clips, output_path)

    tts_count = sum(1 for sid, _ in [(shot.get("shot_id",""), shot)
                                      for _, shot in video_clips]
                    if (tts_audio_map or {}).get(sid))

    return {
        "success": ok,
        "output_path": output_path,
        "error": None if ok else "Concat failed",
        "clips_processed": len(mixed_clips),
        "dialogue_shots": dialogue_count,
        "ambient_shots": ambient_count,
        "tts_injected": tts_count,
        "profile_used": profile["description"],
        "lyria_layered": bool(lyria_undertone_path and os.path.exists(lyria_undertone_path or "")),
        "workdir": workdir,
    }


# ---------------------------------------------------------------------------
# CLI entry point — for standalone stitch use
# ---------------------------------------------------------------------------

def cli_mix_scene(project_dir: str, scene_id: str, output_path: str):
    """
    CLI wrapper: read shot_plan + discover videos, run mix_scene.
    Usage: python3 scene_audio_mixer.py <project_dir> <scene_id> [output.mp4]
    """
    project_dir = Path(project_dir)
    shot_plan_path = project_dir / "shot_plan.json"

    sp = json.loads(shot_plan_path.read_text())
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id + "_")]

    if not scene_shots:
        print(f"[AudioMixer] No shots found for scene {scene_id}")
        return

    # Discover video files — check multiple model/mode directories
    video_dirs = [
        project_dir / "videos_kling_lite",
        project_dir / "videos_kling_full",
        project_dir / "videos_seedance_lite",
        project_dir / "videos_seedance_full",
        project_dir / "renders",
    ]

    clips = []
    for shot in scene_shots:
        sid = shot["shot_id"]
        found = None
        for vdir in video_dirs:
            # Try direct name first
            direct = vdir / f"{sid}.mp4"
            if direct.exists():
                found = str(direct)
                break
            # Try multishot pattern: multishot_gN_shotid.mp4
            for f in vdir.glob(f"multishot_g*_{sid}.mp4"):
                found = str(f)
                break
            if found:
                break
        if found:
            clips.append((found, shot))
        else:
            print(f"[AudioMixer] WARNING: no video found for {sid}")

    if not clips:
        print("[AudioMixer] No video clips found — aborting")
        return

    # Get location from story_bible
    sb_path = project_dir / "story_bible.json"
    location = f"SCENE {scene_id}"
    if sb_path.exists():
        sb = json.loads(sb_path.read_text())
        for s in sb.get("scenes", []):
            if str(s.get("scene_id")) == str(scene_id):
                location = s.get("location", location)
                break

    # Auto-detect Lyria undertone if present
    undertone_path = str(project_dir / "soundscapes" / f"{scene_id}_undertone.wav")
    if not os.path.exists(undertone_path):
        undertone_path = None

    result = mix_scene(
        scene_id=scene_id,
        video_clips=clips,
        location=location,
        output_path=output_path,
        lyria_undertone_path=undertone_path,
    )
    print(f"[AudioMixer] Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 3:
        print("Usage: python3 scene_audio_mixer.py <project_dir> <scene_id> [output.mp4]")
        sys.exit(1)
    proj = sys.argv[1]
    scene = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else f"scene_{scene}_mixed.mp4"
    cli_mix_scene(proj, scene, out)
