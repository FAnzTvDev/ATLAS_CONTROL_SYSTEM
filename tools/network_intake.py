"""
tools/network_intake.py — ATLAS Network Programming Module

This module manages the full broadcast network: 5 channels × 26 seasons × 7 episodes
= 910 episodes per year. It handles channel scheduling, production queuing, and
critically the apply_genre_dna() function that injects channel-specific visual
identity into shot plans at render time.

WIRE POSITION IN V36 HIERARCHY:
  Network Manifest → Channel → Season → Series Manifest → Episode → Shot Plan
                                                                       ↑
                                                    apply_genre_dna() injects HERE
                                                    (modifies nano_prompt compile inputs
                                                     before atlas_universal_runner.py
                                                     calls gen_frame())

AUTHORITY:
  - This module is a CONTROLLER for network-level state (writes network manifests,
    series manifests, genre DNA into shot plans)
  - apply_genre_dna() modifies shot nano_prompt fields — this is permitted because
    it operates BEFORE the generation gate, not after
  - QA gates (generation_gate, prep_engine) still validate after injection
  - Heatmap observes outputs but does not trigger from this module

Usage:
    from tools.network_intake import load_network, apply_genre_dna, get_production_queue

    network = load_network("network_manifest.json")
    queue = get_production_queue(network)
    for ep in queue[:5]:
        apply_genre_dna(shot_plan, network["genre_dna_profiles"][ep["genre_dna"]])

V36.0 — 2026-03-27
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tools"))

# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN GENRE DNA PROFILES
# These are the canonical profiles. Override by putting "genre_dna_profiles"
# in your network_manifest.json — load_network() merges manifest profiles
# on top of these defaults.
# ─────────────────────────────────────────────────────────────────────────────

BUILTIN_GENRE_DNA = {
    "horror": {
        "genre_id": "horror",
        "display_name": "Horror",
        "lighting": "low-key, practical sources only, deep shadows, motivated single-source light",
        "camera_grammar": "dutch angles for dread, slow push-ins on faces, static wide holds for isolation",
        "avg_shot_length_seconds": 6,
        "color_palette": "desaturated cold, deep blue shadows, amber practical sources, no warm fill",
        "pacing": "slow burn with sharp cuts at scare beats, hold on reaction",
        "axis_break_policy": "allowed at scare moments for disorientation",
        "negative_prompt_additions": "bright cheerful lighting, warm color grade, shallow depth of field except extreme close-ups",
        "nano_prompt_prefix": "HORROR ATMOSPHERE. Low-key lighting, deep shadows, practical sources. Cold desaturated color.",
        "kling_mood_suffix": "tense slow movement, suspenseful hold",
        "sound_design_notes": "silence punctuated by sudden audio, low-frequency dread tone",
        "avg_scene_count_per_episode": 8,
        "typical_shot_types": ["establishing", "medium", "close_up", "reaction", "insert"],
    },
    "sci_fi": {
        "genre_id": "sci_fi",
        "display_name": "Science Fiction",
        "lighting": "high-tech practical: LED strips, holographic sources, hard directional light",
        "camera_grammar": "clean geometry, motivated dolly moves, eye-level for authority, low-angle for machines",
        "avg_shot_length_seconds": 4,
        "color_palette": "cool blues and teals, occasional warm amber accents, high contrast",
        "pacing": "brisk cuts in action, deliberate holds on technology reveals",
        "axis_break_policy": "strict 180 degree rule — this world has order",
        "negative_prompt_additions": "warm candlelight, organic textures, period costumes",
        "nano_prompt_prefix": "SCI-FI ENVIRONMENT. Clean geometric architecture, cool LED lighting, high-tech surfaces.",
        "kling_mood_suffix": "controlled precise movement, technological world",
        "sound_design_notes": "ambient hum, digital beeps, processed voices",
        "avg_scene_count_per_episode": 10,
        "typical_shot_types": ["establishing", "wide", "medium", "ots", "insert"],
    },
    "whodunnit_drama": {
        "genre_id": "whodunnit_drama",
        "display_name": "Whodunnit Drama",
        "lighting": "motivated naturalistic: window light, fireplace, practical lamps, soft fill only",
        "camera_grammar": "slow deliberate moves, favors OTS dialogue pairs, close-ups on hands and objects",
        "avg_shot_length_seconds": 8,
        "color_palette": "warm amber interiors, cool exterior, desaturated shadows, rich jewel tones",
        "pacing": "patient — let scenes breathe, hold on reaction shots",
        "axis_break_policy": "strict 180 degree rule — spatial clarity is the mystery",
        "negative_prompt_additions": "artificial neon lighting, fast paced editing, sci-fi elements",
        "nano_prompt_prefix": "PERIOD DRAMA. Naturalistic lighting, warm interiors, rich textiles and wood.",
        "kling_mood_suffix": "deliberate controlled movement, period-appropriate gesture",
        "sound_design_notes": "ambient room tone, clock ticks, distant rain, fireplace crackle",
        "avg_scene_count_per_episode": 13,
        "typical_shot_types": ["establishing", "medium", "ots", "close_up", "reaction", "insert"],
    },
    "action": {
        "genre_id": "action",
        "display_name": "Action / Rumble",
        "lighting": "high-key when possible, but dynamic: explosions, muzzle flash, dust-filtered sunlight",
        "camera_grammar": "handheld in fights, motivated crash zooms, low angle on heroes, aerial establishing",
        "avg_shot_length_seconds": 2.5,
        "color_palette": "high contrast, crushed blacks, golden hour orange, adrenaline teal",
        "pacing": "rapid intercutting in action, brief holds after impact",
        "axis_break_policy": "break axis intentionally during fight choreography for chaos",
        "negative_prompt_additions": "static talking-head compositions, soft diffused light, leisurely pacing",
        "nano_prompt_prefix": "ACTION SEQUENCE. Dynamic lighting, high-contrast, kinetic energy.",
        "kling_mood_suffix": "fast decisive movement, physical tension",
        "sound_design_notes": "impact punches, whooshes, hyper-edited score",
        "avg_scene_count_per_episode": 12,
        "typical_shot_types": ["establishing", "wide", "medium", "close_up", "reaction"],
    },
    "comedy": {
        "genre_id": "comedy",
        "display_name": "Comedy / Jokebox",
        "lighting": "bright even fill, three-point lighting, no harsh shadows, warm friendly tone",
        "camera_grammar": "wide singles for reaction, two-shots for rapport, occasional crash-zoom for gag",
        "avg_shot_length_seconds": 5,
        "color_palette": "warm saturated, bright primaries, clean backgrounds, no darkness",
        "pacing": "tight — no hanging on a joke. Cut on the laugh or just before",
        "axis_break_policy": "180 degree rule observed except for joke axis breaks",
        "negative_prompt_additions": "dark shadows, horror atmosphere, desaturated grade, dutch angles",
        "nano_prompt_prefix": "BRIGHT COMEDY SETTING. Warm even lighting, clean saturated colors, friendly space.",
        "kling_mood_suffix": "expressive physical performance, energetic movement",
        "sound_design_notes": "bright score, room tone, live-audience feel",
        "avg_scene_count_per_episode": 10,
        "typical_shot_types": ["wide", "medium", "close_up", "reaction", "two_shot"],
    },

    # ── V37.0 FANZ UNIVERSE ADDITIONS ────────────────────────────────
    # New genre DNA profiles for Rumble League, AI Sports League,
    # Comedy Specials, and Podcast content. Added alongside existing
    # profiles — no existing profiles modified.

    "fight_broadcast": {
        "genre_id": "fight_broadcast",
        "display_name": "Rumble League Fight Broadcast",
        "lighting": "arena overhead rigs, high-key center ring, deep crowd shadows, corner spotlights",
        "camera_grammar": "ringside low-angle for power, handheld for exchanges, aerial wide for arena scale, crash-zoom on knockdown",
        "avg_shot_length_seconds": 2.5,
        "color_palette": "high contrast, punchy saturation, ring canvas white, corner colour accents, crowd darkness",
        "pacing": "rapid intercutting during exchanges, hold on knockdown reaction, slow-motion replay at key beats",
        "axis_break_policy": "break axis during fight chaos — confusion is authentic. Strict 180 in corner interview segments.",
        "negative_prompt_additions": "soft diffused light, pastel colours, static compositions, letterbox bars",
        "nano_prompt_prefix": "FIGHT ARENA. High-contrast ring lighting, crowd atmosphere, kinetic combat energy.",
        "kling_mood_suffix": "explosive physical movement, athletic precision, crowd energy",
        "sound_design_notes": "crowd roar, corner corner bell, punch impacts, commentary, ring mat sounds",
        "avg_scene_count_per_episode": 8,
        "typical_shot_types": ["establishing", "wide", "medium", "close_up", "reaction", "insert"],
        "broadcast_format": "live",
        "arc_genre_id": "fight_broadcast",
        "_notes": "Rumble League Mon-Fri 8pm broadcast. Arc: FIGHTER_INTRO→ROUND_ACTION→MOMENTUM_SHIFT→AFTERMATH",
    },

    "sports_game": {
        "genre_id": "sports_game",
        "display_name": "AI Sports League Broadcast",
        "lighting": "stadium floods, natural daylight for outdoor, consistent flat fill for fairness, score graphic overlay friendly",
        "camera_grammar": "wide establishing stadium, tight follow-cam on ball/puck, cutaway to bench reaction, aerial on set pieces",
        "avg_shot_length_seconds": 3.5,
        "color_palette": "team colours dominant, pitch/court green or hardwood brown, sky or arena ceiling establishing depth",
        "pacing": "game pace varies by sport — football slow build, basketball rapid, hockey frenetic. Always cut to reaction after scoring.",
        "axis_break_policy": "strict — audience must always know which team attacks left-to-right. Never flip direction mid-game.",
        "negative_prompt_additions": "wrong team colours, empty stadium mid-game, score graphic missing during key play",
        "nano_prompt_prefix": "SPORTS BROADCAST. Stadium atmosphere, team colours, live game energy.",
        "kling_mood_suffix": "athletic movement, team play, competitive intensity",
        "sound_design_notes": "crowd noise, PA announcements, ref whistle, sport-specific action sounds, broadcast commentary",
        "avg_scene_count_per_episode": 12,
        "typical_shot_types": ["establishing", "wide", "medium", "close_up", "reaction"],
        "broadcast_format": "live",
        "arc_genre_id": "sports_game",
        "_notes": "AI Sports League — 160 teams, 5 sports. Arc: PREGAME→GAME_ACTION→KEY_PLAY→POSTGAME",
    },

    "comedy_special": {
        "genre_id": "comedy_special",
        "display_name": "Comedy Special / Stand-Up",
        "lighting": "stage spot on performer, warm fill, audience in silhouette, optional follow-spot for movement",
        "camera_grammar": "wide single for reaction beats, medium for performance, crash-zoom for emphasis, two-shot for rapport",
        "avg_shot_length_seconds": 5,
        "color_palette": "warm stage amber, deep red curtain or brick wall background, performer lit bright against dark audience",
        "pacing": "tight setup/punchline — cut ON the laugh, never after. Hold on awkward silence for effect.",
        "axis_break_policy": "180 rule observed. Axis breaks only for intentional comedic disorientation.",
        "negative_prompt_additions": "horror atmosphere, deep shadows on performer, cold blue lighting, dutch angles",
        "nano_prompt_prefix": "COMEDY STAGE. Warm spot lighting, performer energy, intimate audience atmosphere.",
        "kling_mood_suffix": "expressive delivery, comedic timing, physical performance",
        "sound_design_notes": "audience laughter track, performer mic, minimal music, silence as comedic beat",
        "avg_scene_count_per_episode": 8,
        "typical_shot_types": ["wide", "medium", "close_up", "reaction", "two_shot"],
        "broadcast_format": "recorded",
        "arc_genre_id": "comedy_special",
        "_notes": "Stand-up and sketch comedy specials. Arc: SETUP→BUILD→SUBVERSION→PUNCHLINE",
    },

    "podcast": {
        "genre_id": "podcast",
        "display_name": "Podcast / Interview Format",
        "lighting": "soft even fill, motivated desk lamp or window source, intimate studio feel, no harsh shadows",
        "camera_grammar": "three-camera setup — wide two-shot, host close-up, guest close-up. Cut on emphasis not on sentence.",
        "avg_shot_length_seconds": 8,
        "color_palette": "neutral warm tones, microphone and headphone visible, branded background elements, bookshelf or neutral wall",
        "pacing": "patient — let thoughts complete. Cut only when speaker energy shifts or listener reaction is gold.",
        "axis_break_policy": "strict 180 — host always same side, guest always opposite. Never cross the conversation axis.",
        "negative_prompt_additions": "dark moody lighting, dutch angles, horror atmosphere, action elements, crowds",
        "nano_prompt_prefix": "PODCAST STUDIO. Warm intimate lighting, conversational framing, microphone setup visible.",
        "kling_mood_suffix": "natural conversational movement, thoughtful expression, engaged listening",
        "sound_design_notes": "room tone, subtle music bed, microphone presence, natural breath pauses",
        "avg_scene_count_per_episode": 6,
        "typical_shot_types": ["wide", "medium", "close_up", "reaction", "two_shot"],
        "broadcast_format": "recorded",
        "arc_genre_id": "podcast",
        "_notes": "Podcast and interview content. Arc: TOPIC_INTRO→DISCUSSION→KEY_INSIGHT→OUTRO",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# NETWORK MANIFEST SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

NETWORK_MANIFEST_SCHEMA_VERSION = "1.0"

CHANNEL_TEMPLATE = {
    "channel_id": None,
    "channel_name": None,
    "genre_dna": None,
    "seasons_per_year": 26,
    "series_per_season": 1,
    "episodes_per_series": 7,
    "airings_per_episode_48h": 4,
    "time_block_hours": 12,
    "series": [],           # List of series_manifest paths (populated as seasons air)
    "_notes": "",
}

ATLAS_NETWORK_CHANNELS = [
    {
        "channel_id": "horror",
        "channel_name": "Horror Channel",
        "genre_dna": "horror",
        "seasons_per_year": 26,
        "series_per_season": 1,
        "episodes_per_series": 7,
        "airings_per_episode_48h": 4,
        "time_block_hours": 12,
        "series": [],
        "_notes": "Slow-burn horror anthology. Each 7-episode series is a standalone story.",
    },
    {
        "channel_id": "sci_fi",
        "channel_name": "Sci-Fi Channel",
        "genre_dna": "sci_fi",
        "seasons_per_year": 26,
        "series_per_season": 1,
        "episodes_per_series": 7,
        "airings_per_episode_48h": 4,
        "time_block_hours": 12,
        "series": [],
        "_notes": "Near-future science fiction. Hard sci-fi aesthetics.",
    },
    {
        "channel_id": "whodunnit",
        "channel_name": "Whodunnit Channel",
        "genre_dna": "whodunnit_drama",
        "seasons_per_year": 26,
        "series_per_season": 1,
        "episodes_per_series": 7,
        "airings_per_episode_48h": 4,
        "time_block_hours": 12,
        "series": [],
        "_notes": "Victorian and modern mystery. ATLAS's first production: Victorian Shadows.",
    },
    {
        "channel_id": "rumble",
        "channel_name": "Rumble Action Channel",
        "genre_dna": "action",
        "seasons_per_year": 26,
        "series_per_season": 1,
        "episodes_per_series": 7,
        "airings_per_episode_48h": 4,
        "time_block_hours": 12,
        "series": [],
        "_notes": "Action, fights, heists. Dynamic camera grammar.",
    },
    {
        "channel_id": "jokebox",
        "channel_name": "Jokebox Comedy Channel",
        "genre_dna": "comedy",
        "seasons_per_year": 26,
        "series_per_season": 1,
        "episodes_per_series": 7,
        "airings_per_episode_48h": 4,
        "time_block_hours": 12,
        "series": [],
        "_notes": "Sitcoms, sketch comedy, stand-up narratives.",
    },
]


def build_default_network_manifest() -> dict:
    """
    Return the canonical ATLAS Network manifest with all 5 channels.

    Annual stats (26 seasons × 5 channels × 7 episodes = 910 total):
      - 910 unique episodes/year
      - 9,100 minutes of unique content
      - 3,640 airings (4 airings per episode across 48h window)
      - ~129.6 FAL calls/episode (8 shots/scene × ~13 scenes + regen overhead)
      - Estimated cost: $17-25/episode → $15,470-22,750/year

    FAL call breakdown per episode:
      - First frames: 100 shots × 1.0 call avg = 100 calls
      - Wire A regens: ~15% of character shots = 12 calls
      - Kling video: 10 scenes × 1.75 Kling calls/scene = 17.5 calls avg
      - Total: ~129.5 calls/episode
    """
    channels = list(ATLAS_NETWORK_CHANNELS)  # deep copy not needed — populated later

    return {
        "_schema_version": NETWORK_MANIFEST_SCHEMA_VERSION,
        "network_id": "atlas_network",
        "network_name": "ATLAS AI Broadcast Network",
        "programming_cycle_year": datetime.utcnow().year,
        "channels": channels,
        "genre_dna_profiles": BUILTIN_GENRE_DNA,
        "production_stats": {
            "channels": 5,
            "seasons_per_channel_per_year": 26,
            "episodes_per_season": 7,
            "total_episodes_per_year": 910,
            "avg_runtime_minutes_per_episode": 10,
            "total_unique_content_minutes": 9100,
            "airings_per_episode_48h": 4,
            "total_airings_per_year": 3640,
            "avg_fal_calls_per_episode": 130,
            "estimated_fal_calls_per_year": 118300,
            "estimated_cost_per_episode_usd_low": 17,
            "estimated_cost_per_episode_usd_high": 25,
            "estimated_annual_cost_usd_low": 15470,
            "estimated_annual_cost_usd_high": 22750,
            "_cost_note": (
                "Estimate based on: $0.03/nano frame × 100 shots, "
                "$0.81/Kling scene × 10 scenes/ep, "
                "15% Wire A regen overhead. "
                "Excludes ElevenLabs audio and GCS storage."
            ),
        },
        "_created_at": datetime.utcnow().isoformat(),
        "_last_updated": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK LOAD + VALIDATE
# ─────────────────────────────────────────────────────────────────────────────

def load_network(network_path: str) -> dict:
    """
    Load and validate a network_manifest.json.

    Merges manifest genre_dna_profiles with BUILTIN_GENRE_DNA (manifest wins).
    Validates all channels reference valid genre_dna keys.

    Returns the merged, validated network dict.
    """
    path = Path(network_path)
    if not path.exists():
        raise FileNotFoundError(f"Network manifest not found: {network_path}")

    network = json.load(open(path))

    # Merge genre DNA: built-in defaults + manifest overrides
    merged_profiles = dict(BUILTIN_GENRE_DNA)
    for k, v in network.get("genre_dna_profiles", {}).items():
        merged_profiles[k] = v
    network["genre_dna_profiles"] = merged_profiles

    # Validate channels
    errors = []
    for ch in network.get("channels", []):
        ch_id = ch.get("channel_id", "<unknown>")
        genre = ch.get("genre_dna")
        if genre not in merged_profiles:
            errors.append(
                f"Channel '{ch_id}' references unknown genre_dna '{genre}'. "
                f"Available: {sorted(merged_profiles.keys())}"
            )

    if errors:
        raise ValueError(
            f"Network manifest validation failed:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    n_channels = len(network.get("channels", []))
    print(f"[NETWORK] Loaded: {network.get('network_id')} — {n_channels} channels")
    return network


def save_network(network: dict, network_path: str) -> None:
    """Write network manifest to disk with updated timestamp."""
    network["_last_updated"] = datetime.utcnow().isoformat()
    path = Path(network_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(network, f, indent=2)
    print(f"[NETWORK] Saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULE + QUEUE
# ─────────────────────────────────────────────────────────────────────────────

def get_channel_schedule(network: dict, channel_id: str) -> dict:
    """
    Return the 26-season schedule for a channel.

    For each season, returns:
      - season_number: 1-26
      - series_manifest_path: path to the series_manifest.json (if created)
      - episode_ids: list of expected episode IDs
      - status: 'scheduled' | 'in_production' | 'complete' | 'not_scheduled'

    Args:
        network:    Loaded network manifest (from load_network())
        channel_id: e.g. "whodunnit"

    Returns:
        dict with channel metadata + list of season records
    """
    channel = next(
        (ch for ch in network.get("channels", []) if ch["channel_id"] == channel_id),
        None
    )
    if channel is None:
        raise KeyError(
            f"Channel '{channel_id}' not found. "
            f"Available: {[ch['channel_id'] for ch in network.get('channels', [])]}"
        )

    seasons_per_year = channel.get("seasons_per_year", 26)
    eps_per_series = channel.get("episodes_per_series", 7)
    series_paths = {s.get("season"): s for s in channel.get("series", [])}

    schedule = []
    for season_num in range(1, seasons_per_year + 1):
        series_record = series_paths.get(season_num, {})
        manifest_path = series_record.get("manifest_path")

        # Build expected episode IDs
        series_id = f"{channel_id}_s{season_num:02d}"
        episode_ids = [f"{series_id}_ep{i}" for i in range(1, eps_per_series + 1)]

        # Determine status from manifest if available
        status = "not_scheduled"
        if manifest_path and Path(manifest_path).exists():
            try:
                m = json.load(open(manifest_path))
                all_aired = all(
                    ep.get("status") == "aired"
                    for ep in m.get("episodes", [])
                )
                any_in_prod = any(
                    ep.get("status") in {"in_production", "frames_complete", "videos_complete"}
                    for ep in m.get("episodes", [])
                )
                status = "complete" if all_aired else ("in_production" if any_in_prod else "scheduled")
            except Exception:
                status = "scheduled"
        elif manifest_path:
            status = "scheduled"

        schedule.append({
            "season_number": season_num,
            "series_id": series_id,
            "series_manifest_path": manifest_path,
            "episode_ids": episode_ids,
            "status": status,
        })

    return {
        "channel_id": channel_id,
        "channel_name": channel.get("channel_name"),
        "genre_dna": channel.get("genre_dna"),
        "seasons_total": seasons_per_year,
        "episodes_per_season": eps_per_series,
        "schedule": schedule,
    }


def get_production_queue(network: dict) -> list:
    """
    Return all episodes across all channels ordered by production priority.

    Priority rules:
      1. Episodes already in_production (don't drop them)
      2. Episodes with shot_plan_ready (ready to generate)
      3. Episodes with bible_ready (need shot plan expansion)
      4. Episodes not_started with the lowest season number first

    Episodes with status stitched/qc_passed/aired are excluded.

    Returns:
        List of dicts, each with:
          - episode_id, channel_id, genre_dna, status, manifest_path
          - priority_score (lower = higher priority)
    """
    PRIORITY = {
        "in_production": 0,
        "frames_complete": 1,
        "videos_complete": 2,
        "shot_plan_ready": 3,
        "bible_ready": 4,
        "not_started": 5,
        "stitched": 99,
        "qc_passed": 99,
        "aired": 99,
    }

    queue = []

    for channel in network.get("channels", []):
        ch_id = channel["channel_id"]
        genre_dna = channel.get("genre_dna", "")

        for series_record in channel.get("series", []):
            manifest_path = series_record.get("manifest_path")
            if not manifest_path or not Path(manifest_path).exists():
                continue

            try:
                manifest = json.load(open(manifest_path))
            except Exception as e:
                print(f"  [NETWORK] WARNING: Could not load {manifest_path}: {e}")
                continue

            for ep in manifest.get("episodes", []):
                status = ep.get("status", "not_started")
                priority = PRIORITY.get(status, 99)

                if priority >= 99:
                    continue  # Skip completed episodes

                queue.append({
                    "episode_id": ep["episode_id"],
                    "episode_number": ep.get("episode_number", 0),
                    "channel_id": ch_id,
                    "genre_dna": genre_dna,
                    "status": status,
                    "manifest_path": manifest_path,
                    "shot_plan_path": ep.get("shot_plan_path"),
                    "story_bible_path": ep.get("story_bible_path"),
                    "priority_score": priority * 1000 + ep.get("episode_number", 0),
                })

    queue.sort(key=lambda x: x["priority_score"])
    return queue


# ─────────────────────────────────────────────────────────────────────────────
# GENRE DNA INJECTION — THE CRITICAL FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def apply_genre_dna(
    shot_plan: list,
    genre_profile: dict,
    overwrite_existing: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Inject genre-specific visual identity into a shot plan's nano_prompt fields.

    This is WHERE channel identity enters the generation pipeline. Called by
    atlas_universal_runner.py BEFORE gen_frame() sends the prompt to FAL.

    What it injects (per shot):
      1. nano_prompt_prefix: Genre-specific visual statement prepended to nano_prompt
         (e.g. "HORROR ATMOSPHERE. Low-key lighting, deep shadows, practical sources.")
      2. _genre_lighting_rig: Lighting override written to shot (used by scene_visual_dna.py)
      3. _genre_color_palette: Color palette override written to shot
      4. _genre_camera_grammar: Camera movement/framing preference notes
      5. _genre_negative_additions: Extra negative terms added to _negative_prompt

    Wire position: This function mutates shot dicts IN PLACE. It writes these fields:
      - nano_prompt (prepend prefix if not already present)
      - _genre_lighting_rig
      - _genre_color_palette
      - _genre_camera_grammar
      - _genre_negative_additions
      - _genre_dna_applied (True — deduplication guard)
      - _genre_dna_profile (profile id — for traceability)

    Authority note: This modifies nano_prompt BEFORE generation_gate and gen_frame().
    The generation_gate still validates the modified prompt. This is correct —
    genre DNA is an input to the pipeline, not a bypass of it.

    Args:
        shot_plan:         List of shot dicts (the shots array from shot_plan.json)
        genre_profile:     Genre DNA dict (from network["genre_dna_profiles"][key])
        overwrite_existing: If False (default), skip shots that already have
                           _genre_dna_applied=True (idempotent)
        dry_run:           If True, return stats without modifying shots

    Returns:
        dict with: shots_modified, shots_skipped, genre_id, prefix_added
    """
    if not isinstance(shot_plan, list):
        raise TypeError(f"shot_plan must be a list, got {type(shot_plan)}")

    genre_id = genre_profile.get("genre_id", "unknown")
    prefix = genre_profile.get("nano_prompt_prefix", "")
    lighting = genre_profile.get("lighting", "")
    palette = genre_profile.get("color_palette", "")
    camera = genre_profile.get("camera_grammar", "")
    neg_additions = genre_profile.get("negative_prompt_additions", "")

    modified = 0
    skipped = 0

    for shot in shot_plan:
        # Deduplication guard
        if shot.get("_genre_dna_applied") and not overwrite_existing:
            skipped += 1
            continue

        if dry_run:
            modified += 1
            continue

        # ── 1. nano_prompt prefix injection ───────────────────────────────
        # Bible authority gate: if story bible specified atmosphere for this shot,
        # the bible wins — genre prefix would override narrative intent.
        # Genre DNA only fills gaps (shots with no bible atmosphere).
        existing = shot.get("nano_prompt", "")
        _has_bible_atmosphere = bool(shot.get("_beat_atmosphere"))
        if prefix and prefix not in existing and not _has_bible_atmosphere:
            shot["nano_prompt"] = f"{prefix} {existing}".strip()

        # ── 2. Lighting rig override ───────────────────────────────────────
        # scene_visual_dna.py reads _genre_lighting_rig to supplement its output
        if lighting:
            shot["_genre_lighting_rig"] = lighting

        # ── 3. Color palette override ─────────────────────────────────────
        if palette:
            shot["_genre_color_palette"] = palette

        # ── 4. Camera grammar notes ───────────────────────────────────────
        # Advisory to the Film Engine / Kling prompt compiler
        if camera:
            shot["_genre_camera_grammar"] = camera

        # ── 5. Negative prompt additions ─────────────────────────────────
        # These append to whatever negative_prompt the shot already has
        if neg_additions:
            existing_neg = shot.get("_negative_prompt", "")
            if neg_additions not in existing_neg:
                shot["_negative_prompt"] = (
                    f"{existing_neg}, {neg_additions}".strip(", ")
                    if existing_neg else neg_additions
                )

        # ── 6. Traceability fields ────────────────────────────────────────
        shot["_genre_dna_applied"] = True
        shot["_genre_dna_profile"] = genre_id
        shot["_genre_dna_applied_at"] = datetime.utcnow().isoformat()

        modified += 1

    result = {
        "genre_id": genre_id,
        "shots_modified": modified,
        "shots_skipped": skipped,
        "shots_total": len(shot_plan),
        "prefix_added": prefix,
        "dry_run": dry_run,
    }

    if not dry_run:
        print(
            f"[GENRE DNA] Applied '{genre_id}' to {modified}/{len(shot_plan)} shots "
            f"({skipped} already tagged)"
        )

    return result


def strip_genre_dna(shot_plan: list) -> int:
    """
    Remove all genre DNA injections from a shot plan.

    Useful when: switching a series from one channel to another, or
    re-applying a different genre profile after a channel reassignment.

    Does NOT restore the original nano_prompt (the prefix is prepended,
    not the full original text). Caller should reload from disk if
    original prompts are needed.

    Returns the number of shots that had genre DNA stripped.
    """
    stripped = 0
    genre_fields = [
        "_genre_dna_applied", "_genre_dna_profile", "_genre_dna_applied_at",
        "_genre_lighting_rig", "_genre_color_palette", "_genre_camera_grammar",
        "_genre_negative_additions",
    ]
    for shot in shot_plan:
        if shot.get("_genre_dna_applied"):
            for field in genre_fields:
                shot.pop(field, None)
            stripped += 1
    return stripped


# ─────────────────────────────────────────────────────────────────────────────
# SEASON MANIFEST GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_season_manifest(
    network: dict,
    channel_id: str,
    season_number: int,
    series_title: Optional[str] = None,
    episode_titles: Optional[list] = None,
    recurring_characters: Optional[list] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Create a series_manifest.json for one season of one channel.

    This is the bridge between network-level programming and episode-level
    production. It calls series_orchestrator.create_series_manifest() with
    the channel's genre DNA and episode count.

    Args:
        network:        Loaded network manifest
        channel_id:     e.g. "whodunnit"
        season_number:  1-26
        series_title:   Optional human title (e.g. "Victorian Shadows")
        episode_titles: Optional list of 7 episode titles
        recurring_characters: Optional character continuity list
        output_dir:     Where to write the series_manifest.json
                       (defaults to series_manifests/)

    Returns:
        The created series manifest dict
    """
    try:
        from tools.series_orchestrator import create_series_manifest
    except ImportError:
        # Fallback import when called from repo root
        sys.path.insert(0, str(_REPO_ROOT / "tools"))
        from series_orchestrator import create_series_manifest

    channel = next(
        (ch for ch in network.get("channels", []) if ch["channel_id"] == channel_id),
        None
    )
    if channel is None:
        raise KeyError(f"Channel '{channel_id}' not found in network manifest")

    eps_per_series = channel.get("episodes_per_series", 7)
    genre_dna = channel.get("genre_dna", "")
    time_block = channel.get("time_block_hours", 12)
    airings = channel.get("airings_per_episode_48h", 4)

    series_id = f"{channel_id}_s{season_number:02d}"
    if series_title:
        # Create a slug: "Victorian Shadows" → "victorian_shadows"
        slug = series_title.lower().replace(" ", "_").replace("'", "").replace("-", "_")
        series_id = slug

    manifest = create_series_manifest(
        series_id=series_id,
        channel=channel_id,
        genre_dna=genre_dna,
        season=season_number,
        episode_count=eps_per_series,
        target_duration_minutes=10,
        recurring_characters=recurring_characters or [],
        airing_schedule={
            "time_block_hours": time_block,
            "airings_per_48h": airings,
            "premiere_slot": None,
        },
    )

    # Apply custom titles if provided
    if episode_titles:
        for i, ep in enumerate(manifest["episodes"]):
            if i < len(episode_titles):
                ep["title"] = episode_titles[i]

    # Save if output_dir provided
    if output_dir:
        out_path = Path(output_dir) / f"{series_id}_series_manifest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[NETWORK] Season manifest written → {out_path}")

    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK STATS
# ─────────────────────────────────────────────────────────────────────────────

def calculate_network_stats(network: dict) -> dict:
    """
    Compute live totals from the actual manifests referenced in the network.

    Unlike the 'production_stats' field (which is a projection), this
    function reads actual series manifests to report real state:
      - episodes_created: how many episodes have shot plans on disk
      - episodes_in_production: currently generating
      - episodes_complete: stitched, qc_passed, or aired
      - total_shots: across all shot plans found
      - total_scenes: across all shot plans found

    Returns a stats dict with both projected and live figures.
    """
    projected = network.get("production_stats", {})
    live = {
        "episodes_found": 0,
        "episodes_not_started": 0,
        "episodes_in_production": 0,
        "episodes_complete": 0,
        "total_shots_on_disk": 0,
        "total_scenes_on_disk": 0,
        "channels_with_series": 0,
    }

    COMPLETE_STATUSES = {"stitched", "qc_passed", "aired"}
    IN_PRODUCTION_STATUSES = {"shot_plan_ready", "in_production", "frames_complete", "videos_complete"}

    for channel in network.get("channels", []):
        has_series = False
        for series_record in channel.get("series", []):
            manifest_path = series_record.get("manifest_path")
            if not manifest_path or not Path(manifest_path).exists():
                continue
            has_series = True

            try:
                manifest = json.load(open(manifest_path))
            except Exception:
                continue

            for ep in manifest.get("episodes", []):
                live["episodes_found"] += 1
                status = ep.get("status", "not_started")

                if status == "not_started":
                    live["episodes_not_started"] += 1
                elif status in IN_PRODUCTION_STATUSES:
                    live["episodes_in_production"] += 1
                elif status in COMPLETE_STATUSES:
                    live["episodes_complete"] += 1

                sp_path = ep.get("shot_plan_path")
                if sp_path and Path(sp_path).exists():
                    try:
                        sp = json.load(open(sp_path))
                        shots = sp if isinstance(sp, list) else sp.get("shots", [])
                        live["total_shots_on_disk"] += len(shots)
                        live["total_scenes_on_disk"] += len(set(
                            s.get("scene_id", "") for s in shots
                        ))
                    except Exception:
                        pass

        if has_series:
            live["channels_with_series"] += 1

    return {
        "projected": projected,
        "live": live,
        "_computed_at": datetime.utcnow().isoformat(),
    }


def print_network_summary(network: dict) -> None:
    """Print a human-readable summary of the network to stdout."""
    stats = calculate_network_stats(network)
    proj = stats["projected"]
    live = stats["live"]

    print(f"\n{'═'*60}")
    print(f"  ATLAS NETWORK: {network.get('network_name', network.get('network_id'))}")
    print(f"  Year: {network.get('programming_cycle_year')}")
    print(f"{'═'*60}")
    print(f"\nPROJECTED (full year):")
    print(f"  Channels:          {proj.get('channels', 5)}")
    print(f"  Episodes/year:     {proj.get('total_episodes_per_year', 910)}")
    print(f"  Content minutes:   {proj.get('total_unique_content_minutes', 9100)}")
    print(f"  Total airings:     {proj.get('total_airings_per_year', 3640)}")
    print(f"  FAL calls/year:    ~{proj.get('estimated_fal_calls_per_year', 118300):,}")
    lo = proj.get('estimated_annual_cost_usd_low', 15470)
    hi = proj.get('estimated_annual_cost_usd_high', 22750)
    print(f"  Est. annual cost:  ${lo:,} – ${hi:,}")

    print(f"\nLIVE STATE (manifests on disk):")
    print(f"  Episodes found:    {live['episodes_found']}")
    print(f"  Not started:       {live['episodes_not_started']}")
    print(f"  In production:     {live['episodes_in_production']}")
    print(f"  Complete:          {live['episodes_complete']}")
    print(f"  Shots on disk:     {live['total_shots_on_disk']}")
    print(f"  Scenes on disk:    {live['total_scenes_on_disk']}")

    print(f"\nCHANNELS:")
    for ch in network.get("channels", []):
        n_series = len(ch.get("series", []))
        print(f"  {ch['channel_id']:<12} ({ch['genre_dna']:<18}) {n_series} series registered")
    print(f"{'═'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ATLAS Network Intake — manage the 5-channel broadcast network"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # init — create a new network manifest
    init_p = subparsers.add_parser("init", help="Create a new network_manifest.json")
    init_p.add_argument("output", help="Output path for network_manifest.json")

    # status — show network summary
    status_p = subparsers.add_parser("status", help="Show network status")
    status_p.add_argument("manifest", help="Path to network_manifest.json")

    # queue — show production queue
    queue_p = subparsers.add_parser("queue", help="Show production queue")
    queue_p.add_argument("manifest", help="Path to network_manifest.json")
    queue_p.add_argument("--limit", type=int, default=20)

    # apply-dna — inject genre DNA into a shot plan
    dna_p = subparsers.add_parser("apply-dna", help="Apply genre DNA to a shot plan")
    dna_p.add_argument("manifest", help="Path to network_manifest.json")
    dna_p.add_argument("channel_id", help="Channel ID (e.g. whodunnit)")
    dna_p.add_argument("shot_plan", help="Path to shot_plan.json to modify")
    dna_p.add_argument("--dry-run", action="store_true")
    dna_p.add_argument("--overwrite", action="store_true")

    # new-season — generate a season manifest
    season_p = subparsers.add_parser("new-season", help="Generate a season manifest")
    season_p.add_argument("manifest", help="Path to network_manifest.json")
    season_p.add_argument("channel_id", help="Channel ID")
    season_p.add_argument("season_number", type=int)
    season_p.add_argument("--title", help="Series title")
    season_p.add_argument("--output-dir", default="series_manifests")

    args = parser.parse_args()

    if args.command == "init":
        net = build_default_network_manifest()
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(net, f, indent=2)
        print(f"[NETWORK] Created network manifest → {path}")

    elif args.command == "status":
        net = load_network(args.manifest)
        print_network_summary(net)

    elif args.command == "queue":
        net = load_network(args.manifest)
        queue = get_production_queue(net)[:args.limit]
        print(f"\nProduction Queue (top {args.limit}):")
        print(f"{'Episode':<40} {'Channel':<12} {'Status':<20} {'Priority'}")
        print("-" * 90)
        for item in queue:
            print(
                f"  {item['episode_id']:<38} "
                f"{item['channel_id']:<12} "
                f"{item['status']:<20} "
                f"{item['priority_score']}"
            )

    elif args.command == "apply-dna":
        net = load_network(args.manifest)
        channel = next(
            (ch for ch in net["channels"] if ch["channel_id"] == args.channel_id), None
        )
        if not channel:
            print(f"ERROR: Channel '{args.channel_id}' not found"); sys.exit(1)

        genre_key = channel["genre_dna"]
        profile = net["genre_dna_profiles"].get(genre_key)
        if not profile:
            print(f"ERROR: Genre profile '{genre_key}' not found"); sys.exit(1)

        sp = json.load(open(args.shot_plan))
        shots = sp if isinstance(sp, list) else sp.get("shots", sp)

        result = apply_genre_dna(shots, profile, overwrite_existing=args.overwrite, dry_run=args.dry_run)
        print(f"[GENRE DNA] Result: {result}")

        if not args.dry_run:
            with open(args.shot_plan, "w") as f:
                json.dump(shots if isinstance(sp, list) else {**sp, "shots": shots}, f, indent=2)
            print(f"[GENRE DNA] Shot plan updated: {args.shot_plan}")

    elif args.command == "new-season":
        net = load_network(args.manifest)
        manifest = generate_season_manifest(
            net, args.channel_id, args.season_number,
            series_title=args.title,
            output_dir=args.output_dir,
        )
        print(f"[NETWORK] Season manifest created: {manifest['series_id']}")

    else:
        parser.print_help()
