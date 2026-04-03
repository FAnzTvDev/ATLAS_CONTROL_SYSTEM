#!/usr/bin/env python3
"""
ATLAS UNIVERSAL RUNNER V31.0 — Kling v3 Pro PRIMARY, End-Frame Chain Fix
==========================================================================
ALL 10 consciousness systems active. All 17 harmony systems wired.
Wire 1 (2026-03-19): gen_frame returns (path, judge_score) — real Florence-2 I_score in R
Wire 2 (2026-03-19): RenderLearningAgent.post_render_review() called after every scene
Wire A (2026-03-21): AUTO-REGEN ON REGEN VERDICT — single retry with identity boost in gen_frame
Wire B (2026-03-20): QUALITY GATE — FAIL/FROZEN shots blocked from stitch (pre-existing)
Wire C (2026-03-21): AUTO-REGEN FROZEN VIDEO — motion-boosted Seedance retry in _analyze_video
Wire D (2026-03-23): SCREEN POSITION LOCK — OTSEnforcer wired into CLI runner (was UI-only)
TEST SEQUENCE: Scene 1 → review → Scene 2 → review → multi-scene parallel
V29.9 (2026-03-19): 1 beat per Kling call — script-conscious timing. Frame type header in prompt.
  Beat position marker (Opening/Mid/Closing) gives Kling pacing context per shot.
  No more 3-beat grouping — each story moment is a focused, standalone cinematic unit.
V29.10 (2026-03-19): CONTENT-AWARE CHOREOGRAPHER — shot type driven by beat content, not position.
  RULE: OTS only when beat is STATIONARY DIALOGUE EXCHANGE. Never OTS on movement/entry beats.
  Scene 001 fix: Beat 1 (Thomas trails banister) = MEDIUM, not OTS.
  OTS coverage only after geography is established AND characters are stationary in dialogue.
  New arc for Scene 001: medium → medium (movement+dlg) → ots_b (Eleanor presents) → ots_a (Thomas refuses) → closing.

Pipeline per scene (ALL PARALLEL within each phase):
  P1. First frames:    ALL shots parallel → nano/edit (3 candidates) → Florence-2 judge → best kept
  P2. Videos:          ALL shots parallel → Kling v3/pro PRIMARY (fal-ai) | Seedance RETIRED V31.0
  P2b. Chain re-link:  post-pass only, zero blocking → M01 last frame stored for ref
  P2c. Vision QA:      ALL videos parallel → frozen detect + identity score on video first frame
  P2d. Reward signal:  R = max(frame_I, video_I)×0.35 + D×0.30 + V×0.15 + C×0.15 + E×0.05
  P3.  Stitch:         FFmpeg concat → scene{id}_{mode}.mp4
  P4.  Learning:       RenderLearningAgent → reward_ledger.jsonl + atlas_learning_log

Parallelism architecture:
  Across scenes: ThreadPoolExecutor(max_workers=N_scenes) — scenes 001+002 fire together
  P1 within scene: ThreadPoolExecutor(max_workers=4) — all shots generate frames together
  P2 within scene: ThreadPoolExecutor(max_workers=4) — all shots render videos together
  P2c within scene: ThreadPoolExecutor(max_workers=4) — all videos analyzed together
  P2b/P3: sequential (ffmpeg concat, zero API cost)

Model routing (V29.16):
  All shots PRIMARY → Kling v3/pro via fal-ai (start_image + multi_prompt + @Element identity)
  RETIRED: Seedance v2.0 via muapi.ai (retired V31.0 — do NOT set ATLAS_VIDEO_MODEL=seedance)
  RETIRED: LTX-2.3 (removed V29.3), nano-banana-pro T2I for character shots (removed V29.0)
  NEVER route to LTX — it is retired and produces frozen statues (Constitutional Law C3)

Usage:
  python3 atlas_universal_runner.py victorian_shadows_ep1 002 --mode lite
  python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 --mode lite
"""

import os, sys, json, time, subprocess, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

# Add tools path FIRST so all imports resolve correctly
sys.path.insert(0, str(Path(__file__).parent / "tools"))

# Shot choreographer — timed action sequences for Kling
from shot_choreographer import choreograph_scene, choreograph_beat
from scene_visual_dna import (build_scene_dna, build_scene_lighting_rig,
                              get_focal_length_enforcement, get_positional_dna,
                              get_shot_camera_position, inject_scene_dna)
from prompt_identity_injector import inject_identity_into_prompt, amplify_appearance, strip_location_names, build_social_blocking
from truth_prompt_translator import translate_truth_to_prompt
from beat_enrichment import enrich_project, extract_eye_line, extract_body_direction
from chain_arc_intelligence import enrich_shots_with_arc, get_chain_modifier, should_release_room_dna
from shot_truth_contract import compile_scene_truth
from kling_prompt_compiler import compile_video_for_kling, compile_for_kling

# V36.5: Chain Intelligence Gate — pre/post-gen quality enforcement (NON-BLOCKING import)
_CHAIN_GATE_AVAILABLE = False
try:
    from chain_intelligence_gate import (
        validate_pre_generation as _cig_pre,
        validate_post_generation as _cig_post,
        extract_chain_contract as _cig_contract,
        run_full_validation as _cig_full_validation,
    )
    _CHAIN_GATE_AVAILABLE = True
except Exception as _cig_import_err:
    print(f"  [CHAIN_GATE] Import warning: {_cig_import_err} — gate disabled")

# V37: CPC decontamination — strip generic patterns from prompts before every FAL call.
# Character names can leak into prompts via beat_action/choreography; decontaminate_prompt
# replaces generic patterns ("experiences the moment", "present and engaged", etc.) with
# motivated physical direction so FAL receives specific, actionable prompts.
try:
    from creative_prompt_compiler import decontaminate_prompt as _cpc_decontaminate
    _CPC_DECONTAM_AVAILABLE = True
except Exception as _cpc_import_err:
    print(f"  [CPC] Decontamination import warning: {_cpc_import_err} — using passthrough")
    def _cpc_decontaminate(text, **kw): return text or ""  # type: ignore[misc]
    _CPC_DECONTAM_AVAILABLE = False

# V37 Run Lock — only verified 7/7 systems may activate (NON-BLOCKING import)
try:
    from run_lock import is_system_allowed, get_run_lock_report, reset_run_lock
    _RUN_LOCK_AVAILABLE = True
except Exception as _rl_err:
    print(f"  [RUN_LOCK] Import warning: {_rl_err} — lock disabled")
    def is_system_allowed(name: str) -> bool: return True   # type: ignore[misc]
    def get_run_lock_report() -> dict: return {"lock_active": False, "verified_count": 0, "blocked_attempts": [], "status": "UNAVAILABLE"}  # type: ignore[misc]
    def reset_run_lock(): pass  # type: ignore[misc]
    _RUN_LOCK_AVAILABLE = False

# V32.0: Spatial comparison gate — NON-BLOCKING import
# V31.1: Gate disabled — Gemini TCP RST causes urllib to hang indefinitely even with
# ThreadPoolExecutor timeout. Gate returns UNKNOWN on all pairs regardless (Gemini unavail).
# Re-enable once urlopen hang is root-caused on this host.
_SPATIAL_GATE_AVAILABLE = False
try:
    from spatial_comparison_gate import run_spatial_gate, save_gate_result as _save_spatial_gate
except Exception as _sge:
    pass  # gate disabled above — import failure is expected/ignored

# ── LIVE GENERATION PUSH — V30.5 ────────────────────────────────────────────
# Push per-shot status to the server's LIVE_GEN_TRACKER so the UI can show
# per-shot loading spinners and live thumbnail injection without polling.
# NON-BLOCKING: if server is unreachable, push silently fails.
_ATLAS_SERVER_PORT = int(os.environ.get("ATLAS_PORT", "9999"))

def _push_live_gen(shot_id, status, asset_type="first_frame", url=None, project=None):
    """POST to /api/live-generations/push — NON-BLOCKING, fire-and-forget."""
    try:
        import urllib.request as _ur, json as _json
        payload = _json.dumps({"shot_id": shot_id, "status": status,
                               "asset_type": asset_type, "project": project or "",
                               "url": url or ""}).encode()
        req = _ur.Request(f"http://127.0.0.1:{_ATLAS_SERVER_PORT}/api/live-generations/push",
                          data=payload, headers={"Content-Type": "application/json"})
        _ur.urlopen(req, timeout=2)
    except Exception:
        pass  # server may not be running (CLI-only mode) — silently skip

# ── SCREEN POSITION LOCK — Wire D (V30.4) ──────────────────────────────────
# OTSEnforcer wired here so CLI runs enforce the 180° rule + character blocking.
# Previously only wired in orchestrator_server.py (UI path) and atlas_v26_controller.py.
# CLI generation was blind to blocking → characters drifted between shots.
# NON-BLOCKING: degrades gracefully if ots_enforcer.py is missing.
try:
    from tools.ots_enforcer import OTSEnforcer as _OTSEnforcer
    _OTS_AVAILABLE = True
except ImportError:
    _OTSEnforcer = None
    _OTS_AVAILABLE = False

# V30.5: Wire the hippocampus — spatial prediction + continuity + zone tracking
try:
    from tools.continuity_memory import ContinuityMemory, extract_spatial_state_from_metadata, compile_continuity_delta
    _CONTINUITY_AVAILABLE = True
except ImportError:
    _CONTINUITY_AVAILABLE = False

try:
    from tools.spatial_timecode import build_scene_timecode, detect_zone_from_text, get_timecode_angle_for_shot
    _SPATIAL_AVAILABLE = True
except ImportError:
    _SPATIAL_AVAILABLE = False

# Stage 5 — Prefrontal Cortex: narrative validation + 8-dimension visual scoring (V35.0)
# story_judge.py (670 lines): global narrative arc, beat coverage, pacing, tone consistency
# vision_analyst.py (911 lines): 8-dimensional visual scoring across the full cut
# Both are ADVISORY — they log and suggest, never block generation.
try:
    from tools.story_judge import StoryJudge
    _STORY_JUDGE_AVAILABLE = True
except ImportError:
    StoryJudge = None
    _STORY_JUDGE_AVAILABLE = False

try:
    from tools.vision_analyst import VisionAnalyst
    _VISION_ANALYST_AVAILABLE = True
except ImportError:
    VisionAnalyst = None
    _VISION_ANALYST_AVAILABLE = False

# Phase 2.3 FIX: FAL_KEY MUST be set BEFORE any vision import
# vision_service.py reads FAL_KEY at module INIT time — if we set it after vision_judge import,
# VISION_JUDGE_AVAILABLE is True but FAL calls inside it fail silently → I-score always 0.75 heuristic
os.environ.setdefault("FAL_KEY", "1c446616-b1de-4964-8979-1b6fbc6e41b0:3ff7a80d36b901d586e6b9732a62acd9")

# R46 FIX: OPENROUTER_API_KEY must also be set BEFORE vision_judge import.
# VLM router in vision_judge checks _backend_available("openrouter") at import time.
# Without this, VLM router always falls to Florence-2 heuristic → I-score flat/unreliable.
# Key sourced from .env — setting here guarantees it's available regardless of load order.
os.environ.setdefault("OPENROUTER_API_KEY", "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")

# FIX: GOOGLE_API_KEY must be set BEFORE vision_judge import — same pattern as FAL_KEY/OPENROUTER.
# vision_judge._GEMINI_IS_EXCLUSIVE=True means _backend_available("gemini_vision") is checked at
# route_vision_scoring() call time. But _is_cpc_via_embedding() also needs it at first CPC call.
# Loading from .env ensures both command-line runs AND server runs share the same key source.
_dotenv_path = Path(__file__).parent / ".env"
if _dotenv_path.exists():
    for _line in _dotenv_path.read_text().splitlines():
        _line = _line.strip()
        if _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())
# Hardcoded fallback only if .env is absent or key missing (mirrors FAL_KEY pattern above)
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

# Vision judge — NON-BLOCKING import (T2-CPC-7 pattern) — import AFTER FAL_KEY is set
try:
    from vision_judge import (
        judge_frame, extract_identity_markers, score_caption_against_markers,
        _embed_text, _cosine_sim, _embed_cache,
    )
    VISION_JUDGE_AVAILABLE = True
except ImportError:
    VISION_JUDGE_AVAILABLE = False

# Pre-video quality gate — NON-BLOCKING import (V31.1)
# Holistic frame scoring (location + identity + blocking + mood) BEFORE Kling video gen.
try:
    from pre_video_gate import PreVideoGate
    PRE_VIDEO_GATE_AVAILABLE = True
except ImportError:
    PRE_VIDEO_GATE_AVAILABLE = False
    class PreVideoGate:  # type: ignore[misc]
        def reset_scene(self, *a): pass
        def gate(self, *a, **kw):
            from dataclasses import dataclass, field as _f
            @dataclass
            class _R:
                shot_id=""; attempt=1; score=None; frame_path=""; passed=True; regen_prompt_injection=""
            return _R()
    # Stubs so _is_cpc_via_embedding can degrade gracefully
    def _embed_text(text, api_key): return None  # type: ignore[misc]
    def _cosine_sim(a, b): return 0.0            # type: ignore[misc]
    _embed_cache = {}                             # type: ignore[misc]

# Auto-revision judge — NON-BLOCKING import (V31.1)
# Post-video 8-dimension quality gate (dialogue, tone, camera, blocking, identity …)
try:
    from auto_revision_judge import AutoRevisionJudge
    _ARJ_AVAILABLE = True
    _arj_instance  = None   # lazy init inside run_scene (one per scene)
except ImportError:
    _ARJ_AVAILABLE = False
    AutoRevisionJudge = None   # type: ignore[assignment,misc]

# ═══ CPC CONTAMINATION DETECTION (Priority-2 embedding filter) ═══
# Catches paraphrased generic choreography that the keyword blacklist misses.
# Pattern embeddings are computed lazily on first call and cached for the session.

# Canonical CPC phrases — the same conceptual space as _CPC_PATTERNS in _build_prompt.
# Each phrase represents a class of generic, non-kinetic non-specific choreography text.
_CPC_SEED_PHRASES = [
    "the character begins to speak",
    "body language shifting with intention",
    "natural rhythm of conversation",
    "the moment lands",
    "experiences the moment",
    "present and engaged",
    "natural movement begins",
    "subtle expression of emotion",
    "gestures accompany the words",
    "the scene breathes and settles",
    "inhabits the emotional space",
    "connects with the environment",
]
_CPC_EMBED_CACHE: dict = {}   # phrase → embedding vector; populated lazily on first call

_CPC_SIM_THRESHOLD = 0.82     # cosine similarity above which text is flagged as generic


def _is_cpc_via_embedding(text: str) -> bool:
    """Return True if *text* is semantically similar to a known CPC generic phrase
    (cosine > _CPC_SIM_THRESHOLD). Uses Gemini embedding API; degrades silently to
    False (= allow through) when the API key is absent or the call fails.

    CPC pattern vectors are computed once per session and cached in _CPC_EMBED_CACHE.
    """
    google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not google_key or not text:
        return False

    # Embed candidate text
    candidate_vec = _embed_text(text[:500], google_key)
    if candidate_vec is None:
        return False

    # Lazily populate CPC seed embeddings (only runs once per session per phrase)
    for phrase in _CPC_SEED_PHRASES:
        if phrase not in _CPC_EMBED_CACHE:
            vec = _embed_text(phrase, google_key)
            if vec is not None:
                _CPC_EMBED_CACHE[phrase] = vec

    # Check cosine similarity against every cached pattern
    for phrase, pattern_vec in _CPC_EMBED_CACHE.items():
        sim = _cosine_sim(candidate_vec, pattern_vec)
        if sim > _CPC_SIM_THRESHOLD:
            return True
    return False

# FAL Vision Service — Florence-2 + DINOv2 + ArcFace
try:
    from vision_service import FALVisionService
    _vision_svc = FALVisionService()
    VISION_SERVICE_AVAILABLE = True
except:
    _vision_svc = None
    VISION_SERVICE_AVAILABLE = False

# ═══ V37 GOVERNANCE HOOKS — observe-only, non-blocking ═════════════════════
try:
    from asset_registry import register_asset as _v37_register_asset
    from cost_controller import log_cost as _v37_log_cost
    _V37_GOVERNANCE = True
except Exception:
    _V37_GOVERNANCE = False
    def _v37_register_asset(*a, **k): pass
    def _v37_log_cost(*a, **k): pass

# ═══ LYRIA SOUNDSCAPE HOOK — advisory, non-blocking ════════════════════════
try:
    from tools.lyria_score_generator import generate_scene_undertone as _lyria_generate_undertone
    _LYRIA_SOUNDSCAPE = True
except Exception:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent / "tools"))
        from lyria_score_generator import generate_scene_undertone as _lyria_generate_undertone
        _LYRIA_SOUNDSCAPE = True
    except Exception:
        _LYRIA_SOUNDSCAPE = False
        def _lyria_generate_undertone(*a, **k): return {"source": "disabled"}

# ═══ SMART STITCHER — Layer 5 scene concat (audio-safe) + curated edits ═════
# pipeline_tools/smart_stitcher.py — concat() + ensure_audio() + master_edit() + highlight_edit()
# Used in PHASE 3 stitch in place of bare subprocess ffmpeg calls.
# Also provides curated edits (master, highlight) for final scene packaging.
# Non-blocking: if import fails, PHASE 3 falls back to direct subprocess and skips curated edits.
try:
    from pipeline_tools.smart_stitcher import (
        concat as _smart_concat,
        ensure_audio as _smart_ensure_audio,
        master_edit as _smart_master_edit,
        highlight_edit as _smart_highlight_edit
    )
    _SMART_STITCHER = True
except Exception:
    try:
        import sys as _sys_ss
        _sys_ss.path.insert(0, str(Path(__file__).parent / "pipeline_tools"))
        from smart_stitcher import (
            concat as _smart_concat,
            ensure_audio as _smart_ensure_audio,
            master_edit as _smart_master_edit,
            highlight_edit as _smart_highlight_edit
        )
        _SMART_STITCHER = True
    except Exception:
        _SMART_STITCHER = False
        def _smart_concat(clips, output): pass                    # stub
        def _smart_ensure_audio(src, dst): pass                  # stub
        def _smart_master_edit(scene_id, *args, **kwargs): None  # stub
        def _smart_highlight_edit(scene_id, *args, **kwargs): None  # stub

# ═══ VIDEO VISION OVERSIGHT — post-gen per-video quality checks ═════════════
# Detects: character bleed in E-shots, all-frozen videos, dialogue sync fails.
# Complements chain_intelligence_gate (which handles frozen dialogue + arc checks).
try:
    from tools.video_vision_oversight import (
        run_video_oversight as _vvo_run,
        preflight_e_shot_frame_check as _vvo_preflight_e_shot,
        run_chain_transition_check as _vvo_chain_check,
        run_scene_stitch_check as _vvo_scene_stitch_check,
        VisionBudgetTracker as _VisionBudgetTracker,
    )
    _VVO_AVAILABLE = True
except Exception:
    try:
        from video_vision_oversight import (
            run_video_oversight as _vvo_run,
            preflight_e_shot_frame_check as _vvo_preflight_e_shot,
            run_chain_transition_check as _vvo_chain_check,
            run_scene_stitch_check as _vvo_scene_stitch_check,
            VisionBudgetTracker as _VisionBudgetTracker,
        )
        _VVO_AVAILABLE = True
    except Exception:
        _VVO_AVAILABLE = False
        def _vvo_run(*a, **k):
            return type("_VVOStub", (), {"passed": True, "failure_summary": "", "regen_patch": {}})()
        def _vvo_preflight_e_shot(*a, **k):
            return type("_VVOStub", (), {"passed": True, "description": "vvo unavailable"})()
        def _vvo_chain_check(*a, **k):
            return {"skipped": True}
        def _vvo_scene_stitch_check(*a, **k):
            return {"skipped": True, "overall_quality": "not_assessed"}

        class _VisionBudgetTracker:  # stub — VVO unavailable, all gates pass-through
            def __init__(self, **k): pass
            def reset_scene(self, n): pass
            def track_kling_call(self): pass
            def track_gemini_call(self, t=""): pass
            def can_regen_shot(self, sid): return True
            def consume_regen(self, sid): pass
            def regen_count(self, sid): return 0
            def scene_budget_ok(self): return True
            def episode_budget_ok(self): return True
            def should_regen_on_grade(self, h, s): return True
            def stop_chain_on_exceeded(self): return False
            def budget_summary(self): return "budget tracking unavailable"

# ═══ THREE INTELLIGENCE LAYERS — non-blocking imports ═══════════════════════
# Layer 1: Production Intelligence Graph — SQLite store for cross-run learning
# Layer 2: Director Brain — pre-production LLM guidance + arc adjustment
# Layer 3: Doctrine Tracker — rule firing analytics + evolution suggestions

_PI_AVAILABLE = False
try:
    from production_intelligence import (
        ProductionIntelligence as _PI,
        write_shot_outcome as _pi_write_shot,
        get_pre_generation_intel as _pi_pre_gen_intel,
    )
    _PI_AVAILABLE = True
except Exception as _pi_err:
    print(f"  [INTEL] ProductionIntelligence import warning: {_pi_err}")
    def _pi_write_shot(*a, **k): pass
    def _pi_pre_gen_intel(*a, **k): return {"risk_level": "UNKNOWN"}

_DB_AVAILABLE = False
try:
    from director_brain import (
        DirectorBrain as _DirectorBrain,
        pre_scene_brief as _db_pre_scene_brief,
        arc_adjustment_signal as _db_arc_signal,
        scene_close_evaluation as _db_scene_close,
    )
    _DB_AVAILABLE = True
except Exception as _db_err:
    print(f"  [INTEL] DirectorBrain import warning: {_db_err}")
    def _db_pre_scene_brief(*a, **k): return type("_DBStub", (), {"tension_level":"moderate","camera_guidance":"","source":"unavailable"})()
    def _db_arc_signal(*a, **k): return type("_DBStub", (), {"apply":False})()
    def _db_scene_close(*a, **k): return type("_DBStub", (), {"overall_grade":"?","arc_health":"UNKNOWN"})()

_DT_AVAILABLE = False
try:
    from doctrine_tracker import (
        DoctrineTracker as _DoctrineTracker,
        extract_firings_from_gate_result as _dt_extract_gate,
        finalize_session as _dt_finalize,
        log_rule as _dt_log_rule,
    )
    _DT_AVAILABLE = True
except Exception as _dt_err:
    print(f"  [INTEL] DoctrineTracker import warning: {_dt_err}")
    def _dt_extract_gate(*a, **k): pass
    def _dt_finalize(*a, **k): pass
    def _dt_log_rule(*a, **k): pass

# ═══ AUDIO PIPELINE — ElevenLabs TTS + scene_audio_mixer ════════════════════
# IMPORTANT: ElevenLabs TTS is used ONLY for soundscape/ambient audio generation.
# Dialogue audio is handled by Kling's native audio output in the video renderer.
# ElevenLabs generates room tone, atmosphere, and background soundscapes only.
# Mixer: room tone + Lyria undertone (NOT dialogue — Kling handles that).
# Both are non-blocking — failure never affects the silent video stitch.
# NOTE: Future migration to Google Cloud TTS for soundscapes is planned.
try:
    from tools.elevenlabs_tts import generate_scene_dialogue_audio as _tts_generate
    from tools.scene_audio_mixer import mix_scene as _audio_mix_scene
    _AUDIO_PIPELINE = True
except Exception:
    try:
        from elevenlabs_tts import generate_scene_dialogue_audio as _tts_generate
        from scene_audio_mixer import mix_scene as _audio_mix_scene
        _AUDIO_PIPELINE = True
    except Exception:
        _AUDIO_PIPELINE = False
        def _tts_generate(*a, **k): return {}
        def _audio_mix_scene(*a, **k): return {"success": False, "error": "audio pipeline disabled"}

# ═══ FIX-ERR-06: DYNAMIC CHARACTER LISTS — universal for any project ═══
# run_scene() populates these from cast_map.json before generation starts.
# All functions that previously used hardcoded Victorian Shadows names now read these.
# New show = new cast_map = these lists automatically reflect the new characters.
_ACTIVE_CHAR_NAMES: list = []     # e.g. ["NADIA COLE", "THOMAS BLACKWOOD", ...]
_ACTIVE_CHAR_PREFIXES: list = []  # e.g. ["NADIA COLE:", "THOMAS BLACKWOOD:", ...]

# ═══ COST TRACKER — resets per scene, never accumulates across scenes ═══
_cost_tracker = {"nano_calls": 0, "kling_calls": 0, "ltx_calls": 0,
                 "seedance_calls": 0,  # ERR-05 FIX: track Seedance separately
                 "florence_calls": 0, "nano_cost": 0.0, "kling_cost": 0.0,
                 "ltx_cost": 0.0, "seedance_cost": 0.0,  # ERR-05: Seedance cost ~$0.90/call (10s), $1.20/call (15s)
                 "florence_cost": 0.0, "total": 0.0}

def _reset_cost_tracker():
    """FIX: Reset per scene — prevents false accumulation across parallel scenes."""
    for k in _cost_tracker:
        _cost_tracker[k] = 0.0 if k.endswith("cost") or k == "total" else 0

def _track_cost(model_type, count=1, duration=10, generate_audio=False):
    # ERR-05 FIX: Seedance rate is duration-dependent (~$0.09/second at ~15M quota/15s clip)
    # V37: Kling v3/pro corrected FAL rates (source: fal.ai pricing page):
    #   Audio OFF: $0.112/sec  |  Audio ON: $0.168/sec
    #   Previous $0.035/sec was ~3x underreported — guardrails were firing too late
    # generate_audio=False by default (controls Kling pricing tier; see orchestrator default line ~6855)
    _kling_rate = 0.168 if generate_audio else 0.112
    rates = {"nano": 0.03, "kling": _kling_rate * max(duration, 5), "ltx": 0.30, "florence": 0.001,
             "seedance": 0.09 * max(duration, 5)}  # seedance retired but rate kept for ledger
    key = model_type
    if key.startswith("seedance"):
        key = "seedance"
    cost = rates.get(key, 0) * count
    call_key = f"{key}_calls"
    cost_key = f"{key}_cost"
    if call_key not in _cost_tracker:
        _cost_tracker[call_key] = 0
    if cost_key not in _cost_tracker:
        _cost_tracker[cost_key] = 0.0
    _cost_tracker[call_key] += count
    _cost_tracker[cost_key] += cost
    _cost_tracker["total"] += cost

def _print_cost():
    """Cost is for AWARENESS only — never gates quality.
    Florence-2, vision judge, identity scoring = always run.
    Budget affects RERUNS and REVISIONS, not the quality pipeline."""
    c = _cost_tracker
    print(f"\n  COST REPORT: ${c['total']:.2f} total (awareness only — quality systems always run)")
    print(f"     Generation: Nano {c['nano_calls']} (${c['nano_cost']:.2f}) | Kling {c['kling_calls']} (${c['kling_cost']:.2f}) | LTX {c['ltx_calls']} (${c['ltx_cost']:.2f}) | Seedance {c['seedance_calls']} (${c['seedance_cost']:.2f})")
    print(f"     Quality: Florence {c['florence_calls']} (${c['florence_cost']:.2f}) — NEVER skipped")

# ═══ WIRE A BUDGET CAP — per-scene regen limiter ═══
# If 3+ shots in the same scene all trigger Wire A regen, it's a systemic issue (vision
# model is unreliable / prompts are broken / refs are wrong) — not individual bad frames.
# Spending on 3+ regens per scene wastes money without fixing the root cause.
# Counter resets at the start of each scene. Thread-safe: CPython dict updates are GIL-guarded.
_WIRE_A_MAX_REGENS_PER_SCENE = 2
_wire_a_regen_counts: dict = {}  # scene_prefix (e.g. "001") → int count for this run

def _wire_a_can_regen(scene_prefix: str) -> bool:
    """Return True if Wire A regen budget is not yet exhausted for this scene."""
    return _wire_a_regen_counts.get(scene_prefix, 0) < _WIRE_A_MAX_REGENS_PER_SCENE

def _wire_a_consume(scene_prefix: str):
    """Record one Wire A regen for this scene."""
    _wire_a_regen_counts[scene_prefix] = _wire_a_regen_counts.get(scene_prefix, 0) + 1

def _wire_a_reset(scene_prefix: str):
    """Reset the Wire A regen counter for a scene (call at scene start)."""
    _wire_a_regen_counts[scene_prefix] = 0

# ═══ VISION BUDGET TRACKER — episode-level regen budget enforcement ═══
# Single instance per process run. reset_scene() is called at each scene boundary.
# Guards against runaway regen cycles burning Kling + Gemini API budget.
# All decisions (ARJ grade gate, per-shot cap, scene cap, episode cap) flow through here.
_vbt_instance = None  # VisionBudgetTracker, lazily created on first access


def _get_vbt():
    """Return the episode-level VisionBudgetTracker, creating it once if needed."""
    global _vbt_instance
    if _vbt_instance is None:
        try:
            _vbt_instance = _VisionBudgetTracker()
        except Exception:
            _vbt_instance = None
    return _vbt_instance


import fal_client  # FAL_KEY already set above before vision_service import

# ═══ MODEL LOCK ═══
KLING = "fal-ai/kling-video/v3/pro/image-to-video"      # Character video (identity elements)
# C3: LTX is RETIRED. This guard raises RuntimeError if anything ever tries to USE this constant.
# route_shot() is confirmed LTX-free (all 4 branches → seedance), but this makes accidental
# regression immediately loud rather than silently routing to the frozen-statue model.
class _LTXRetiredGuard:
    _val = "fal-ai/ltx-2/image-to-video/fast"  # readable for logging, not callable
    def __eq__(self, other):   raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Kling v3/pro.")
    def __hash__(self):        raise RuntimeError("C3 VIOLATION: LTX is retired. HALT.")
    def __str__(self):         return "[LTX-RETIRED-C3-GUARD]"
    def __repr__(self):        return "[LTX-RETIRED-C3-GUARD]"
    def __getattr__(self, _):  raise RuntimeError("C3 VIOLATION: LTX is retired. HALT. Use Kling v3/pro.")
LTX_FAST = _LTXRetiredGuard()  # RETIRED — C3 law. Any use raises RuntimeError immediately.
NANO_EDIT = "fal-ai/nano-banana-pro/edit"                 # First frame WITH refs (image-to-image)
NANO_T2I = "fal-ai/nano-banana-pro"                       # First frame NO refs (text-to-image)
NEG = "blurry, distorted, deformed, extra limbs, text overlay, watermark, logo, static, frozen, CGI, 3D render, animated, cartoon, doll face, plastic skin, airbrushed, smooth skin, digital art, video game, Unreal Engine, porcelain, wax figure, mannequin, HDR, overprocessed, oversaturated, studio lighting, flat lighting, ring light, beauty filter, face filter, Snapchat filter, dead stare, symmetrical AI eyes, shocked expression, wide-eyed surprise, uncanny valley, perfectly symmetrical face, glazed eyes, blank stare, robotic expression, soulless eyes"  # V36.3: AI-eye anti-uncanny-valley. V36.3b: sound tokens REMOVED (Kling is video-only, audio tokens waste prompt space)
MAX_PARALLEL = 4

# ═══ SEEDANCE V2.0 (ByteDance via muapi.ai) ═══
# V29.8: Added as alternative video model to Kling.
# Poll:     GET  https://api.muapi.ai/api/v1/predictions/{id}/result
# Params:   prompt, images_list (up to 9 URLs), aspect_ratio, duration (5-10s), quality (basic|pro), remove_watermark
# Cost:     $0.60/video (basic) — comparable to Kling
# Duration: Supports 5s and 10s (V29.8: match V29.7 word-count-aware pacing)
# Key:      Set MUAPI_KEY env var OR hardcoded fallback below
# Strengths: camera control, native audio-video sync, up to 9 reference images per call
SEEDANCE_MODEL_REGISTRY = {
    "seedance": {
        "endpoint": "https://api.muapi.ai/api/v1/seedance-v2.0-i2v",
        "label": "Seedance v2.0 I2V",
    },
    "seedance_omni": {
        "endpoint": "https://api.muapi.ai/api/v1/seedance-2.0-omni-reference",
        "label": "Seedance 2.0 Omni Reference",
    },
}
SEEDANCE_POLL = "https://api.muapi.ai/api/v1/predictions/{request_id}/result"
MUAPI_KEY = os.environ.get("MUAPI_KEY", "60bfee969e78c66be0841742fac03df68ca15ffd2075b5e26248220e8f4c4ac2")  # muapi.ai — Seedance v2.0

# Active video model — controlled by --model flag or UI selector
# V31.0: Kling v3 Pro is PRIMARY. Seedance branch preserved for emergency fallback but never fires by default.
# Default is "kling". To use Seedance: export ATLAS_VIDEO_MODEL=seedance
ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")

# V36.5: Chain Intelligence Gate bypass flag — set True via --skip-gates CLI arg or ATLAS_SKIP_GATES=1
# Emergency-only: disables pre/post-gen quality enforcement. Never use in normal production.
_SKIP_CHAIN_GATES = os.environ.get("ATLAS_SKIP_GATES", "0") == "1"

def _seedance_primary_model() -> str:
    primary = os.environ.get("ATLAS_SEEDANCE_PRIMARY", "seedance").strip().lower()
    if primary not in SEEDANCE_MODEL_REGISTRY:
        primary = "seedance"
    return primary

def _seedance_models_for_run() -> List[str]:
    primary = _seedance_primary_model()
    raw = os.environ.get("ATLAS_SEEDANCE_MODELS", "")
    requested = [m.strip().lower() for m in raw.split(",") if m.strip()] if raw else []
    models: List[str] = []
    if primary not in requested:
        models.append(primary)
    for key in requested:
        if key in SEEDANCE_MODEL_REGISTRY and key not in models:
            models.append(key)
        elif key and key not in SEEDANCE_MODEL_REGISTRY:
            print(f"  [SEEDANCE] WARNING: Unknown model '{key}' — skipping.")
    if not models:
        models.append(primary)
    return models

def _seedance_endpoint_for(model_key: str) -> Tuple[str, str]:
    key = (model_key or "seedance").strip().lower()
    if key not in SEEDANCE_MODEL_REGISTRY:
        print(f"  [SEEDANCE] WARNING: Unknown model '{model_key}' — using Seedance default.")
        key = "seedance"
    info = SEEDANCE_MODEL_REGISTRY[key]
    return info["endpoint"], info.get("label", key)

def _seedance_variant_outdir(base_dir: str, model_key: str, tag_suffix: str) -> str:
    base_path = Path(base_dir)
    parent = base_path.parent
    suffix = tag_suffix or base_path.name.replace("videos_seedance_", "")
    name = f"videos_{model_key}_{suffix}" if suffix else f"videos_{model_key}"
    target = parent / name
    target.mkdir(parents=True, exist_ok=True)
    return str(target)

def _stitch_seedance_variant_scenes(pdir: Path, scene_id: str, tag: str,
                                    variant_ctx: Dict[str, Dict[str, object]],
                                    blocked_sids: set, ordered_shots: List[str]):
    per_model = variant_ctx.get("models") if isinstance(variant_ctx, dict) else {}
    sequence = ordered_shots or variant_ctx.get("shot_sequence", [])
    if not per_model:
        return
    for model_key, data in per_model.items():
        per_shot = data.get("per_shot") if isinstance(data, dict) else {}
        if not per_shot:
            continue
        ordered_files = []
        for sid in sequence:
            if sid in blocked_sids:
                continue
            vpath = per_shot.get(sid)
            if vpath and os.path.exists(vpath):
                ordered_files.append(vpath)
        if not ordered_files:
            continue
        listfile = f"/tmp/stitch_{scene_id}_{tag}_{model_key}.txt"
        with open(listfile, "w") as f:
            for v in ordered_files:
                f.write(f"file '{os.path.abspath(v)}'\n")
        outname = f"scene{scene_id}_{tag}_{model_key}.mp4"
        outpath = pdir / outname
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", listfile, "-c:v", "copy", "-an", str(outpath)], capture_output=True)  # V31.1: -an strips audio
        if outpath.exists():
            print(f"  [STITCH:{model_key}] {outname}: {os.path.getsize(outpath)/(1024*1024):.1f}MB")

# ═══════════════════════════════════════════════════════════════
# SEEDANCE V2.0 — muapi.ai client (async poll pattern)
# ═══════════════════════════════════════════════════════════════
def gen_seedance_video(prompt, image_urls, duration=5, quality="basic", aspect_ratio="16:9", model_key="seedance"):
    """
    V29.8: Generate video via Seedance v2.0 (ByteDance / muapi.ai).
    Uses async submit → poll pattern (unlike fal_client.subscribe which blocks internally).

    Args:
        prompt: Motion/action description (no character names — FAL-style plain text)
        image_urls: List of image URLs (up to 9, first = start frame)
        duration: Video duration in seconds (default 5)
        quality: "basic" ($0.60) or "pro" ($1.20)
        aspect_ratio: "16:9" default
    Returns:
        Local video file path or None on failure
    """
    import requests, time, tempfile

    api_key = MUAPI_KEY
    if not api_key:
        print(f"  [SEEDANCE:{model_key}] FAIL: MUAPI_KEY not set. Add to env or .env file.")
        return None

    # V29.16: Semantic prompt builder for Seedance v2.0
    # Phase 2.2 FIX: Updated slot assignments to match new images_list order:
    # NEW ORDER: @image1=start_frame, @image2=char1, @image3=char2, @image4=location
    # Seedance weights early slots more heavily — characters now at priority positions 2+3
    n_imgs = len(image_urls[:9])
    # Build role suffix based on how many images are provided
    # 1 img: just animate; 2: char at @image2; 3: chars at @image2+@image3; 4: + room at @image4
    # R63 FIX: Add explicit character locking constraint to every role_suffix.
    # Seedance 2.0 best practice: "Same face, same clothing, no identity drift" is the
    # most reliable way to prevent character consistency breaks across frames.
    # Proven by ByteDance's own documentation and 500+ curated prompt community data.
    _LOCK = " Same face, same clothing, no identity drift."
    _role_suffix = ""
    if n_imgs == 2:
        _role_suffix = f"{_LOCK} Match @image2 for character identity."
    elif n_imgs == 3:
        _role_suffix = f"{_LOCK} @image2 and @image3 define character faces and clothing."
    elif n_imgs >= 4:
        _role_suffix = f"{_LOCK} @image2 and @image3 define faces and clothing. @image4 shows room architecture."
    # Compose: "Animate @image1. [content] [role assignments]"
    max_chars = 900
    content_budget = max_chars - len("Animate @image1. ") - len(_role_suffix)
    if content_budget < 0:
        content_budget = 0
    prompt_body = prompt if content_budget == 0 or len(prompt) <= content_budget else prompt[:content_budget]
    prompt_with_refs = f"Animate @image1. {prompt_body}{_role_suffix}"

    # Quality: API accepts "high" or "basic" (V29.10 fix: "pro" was wrong)
    quality_mapped = "high" if quality in ("pro", "high", "full") else "basic"

    # Duration: API enum [5, 10, 15] — round to nearest valid value
    dur_int = int(duration)
    valid_durs = [5, 10, 15]
    dur_valid = min(valid_durs, key=lambda x: abs(x - dur_int))

    endpoint, endpoint_label = _seedance_endpoint_for(model_key)
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    payload = {
        "prompt": prompt_with_refs[:900],
        "images_list": image_urls[:9],
        "aspect_ratio": aspect_ratio,
        "duration": dur_valid,
        "quality": quality_mapped,
        "remove_watermark": True,  # V29.12: Remove ByteDance/Seedance watermark from output
    }

    # Step 1: Submit
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [SEEDANCE:{model_key}] Submit FAIL: {e}")
        return None

    request_id = data.get("request_id") or data.get("id")
    if not request_id:
        print(f"  [SEEDANCE:{model_key}] No request_id in response: {data}")
        return None

    print(f"  [SEEDANCE:{model_key}] Submitted to {endpoint_label} → request_id={request_id}")

    # Step 2: Poll (max 15 min, 5s intervals)
    poll_url = SEEDANCE_POLL.format(request_id=request_id)
    max_wait = 900
    interval = 5
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            r = requests.get(poll_url, headers=headers, timeout=15)
            # ERR-POLL-FIX: Capture response body BEFORE raise_for_status to expose MUAPI error message
            if not r.ok:
                try:
                    err_body = r.json()
                    err_msg = err_body.get("message") or err_body.get("error") or err_body.get("detail") or str(err_body)
                except Exception:
                    err_msg = r.text[:200]
                print(f"  [SEEDANCE:{model_key}] Poll {r.status_code} at {elapsed}s: {err_msg}")
                # 404 = job expired/unknown, 400 = bad request → bail early (no point polling)
                if r.status_code in (400, 404):
                    print(f"  [SEEDANCE:{model_key}] Unrecoverable poll error — stopping poll loop")
                    return None
                continue
            result = r.json()
        except Exception as e:
            print(f"  [SEEDANCE:{model_key}] Poll error at {elapsed}s: {e}")
            continue

        status = result.get("status", "")
        if status in ("succeeded", "completed", "done") or result.get("video_url") or result.get("output") or result.get("outputs"):
            # V29.11 FIX: MUAPI returns video URL in outputs[0] (list), not video_url/output field
            # Confirmed from API test: {"outputs": ["https://cdn.muapi.ai/outputs/...mp4"], "status": "completed"}
            _outputs = result.get("outputs") or []
            video_url = (
                (_outputs[0] if _outputs and isinstance(_outputs[0], str) else None) or
                result.get("video_url") or
                result.get("output", {}).get("video_url") or
                result.get("output", {}).get("url") or
                (result.get("output") if isinstance(result.get("output"), str) else None))
            if video_url:
                # Download video to temp file
                try:
                    vresp = requests.get(video_url, timeout=60, stream=True)
                    vresp.raise_for_status()
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    for chunk in vresp.iter_content(chunk_size=8192):
                        tmp.write(chunk)
                    tmp.close()
                    print(f"  [SEEDANCE:{model_key}] ✓ Downloaded {os.path.getsize(tmp.name)//1024}KB in {elapsed}s")
                    return tmp.name
                except Exception as e:
                    print(f"  [SEEDANCE:{model_key}] Download FAIL: {e}")
                    return None
            else:
                print(f"  [SEEDANCE:{model_key}] Completed but no video URL in response: {list(result.keys())}")
                return None
        elif status in ("failed", "error", "cancelled"):
            print(f"  [SEEDANCE:{model_key}] FAILED: {result.get('error', result)}")
            return None
        elif elapsed % 30 == 0:
            print(f"  [SEEDANCE:{model_key}] Waiting... {elapsed}s (status={status})")

    print(f"  [SEEDANCE:{model_key}] TIMEOUT after {max_wait}s")
    return None


# ═══ SEEDANCE V2.0 EXTEND (video continuation) ═══════════════════════════════
# Endpoint: POST https://api.muapi.ai/api/v1/seedance-v2.0-extend
# Purpose:  Take an EXISTING video and generate a seamless continuation.
#           Unlike I2V (image → video), Extend feeds the FULL video clip
#           so Seedance can infer velocity, character momentum, and spatial
#           state from the motion already in the clip — not just from a static frame.
# Use case: Shots that end mid-action, dialogue scenes needing more room to breathe,
#           connecting scenes where the cut doesn't feel clean, or any shot flagged
#           with _extend_shot=True or _extend_duration_extra in the shot plan.
# Params:   video_url (public URL or R2 URL of the source video)
#           prompt (what should happen NEXT — continuation action description)
#           duration (5 or 10s of extension, default 5)
#           aspect_ratio ("16:9")
# Cost:     ~$0.60/extend call (same as I2V)
# Doc:      https://muapi.ai/playground/seedance-v2.0-extend
# ════════════════════════════════════════════════════════════════════════════════

SEEDANCE_EXTEND_ENDPOINT = "https://api.muapi.ai/api/v1/seedance-v2.0-extend"


def gen_seedance_extend(
    source_video_path: str,
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    quality: str = "basic",
) -> str | None:
    """
    V30.0 — SEEDANCE EXTEND: Continue an existing video clip.

    Uploads the source video to R2 (or uses its existing public URL), then
    submits to the Seedance V2.0 Extend endpoint with the continuation prompt.
    Uses the same async poll pattern as gen_seedance_video().

    Args:
        source_video_path: Local path to the MP4 to extend
        prompt: What should happen NEXT in the scene (continuation action)
        duration: Seconds to add (5 or 10, default 5)
        aspect_ratio: "16:9" or "9:16"
        quality: "basic" or "pro"

    Returns:
        Local path to the concatenated video (source + extension), or None if failed.
    """
    import requests as _req

    if not source_video_path or not os.path.exists(source_video_path):
        print(f"  [EXTEND] Source video not found: {source_video_path}")
        return None

    api_key = MUAPI_KEY
    if not api_key:
        print(f"  [EXTEND] FAIL: MUAPI_KEY not set")
        return None

    # Upload source video to R2 for a stable public URL
    # Uses upload_public() — the canonical R2 uploader (boto3 → fal fallback)
    print(f"  [EXTEND] Uploading source video to R2 (via upload_public)...")
    video_public_url = upload_public(source_video_path)
    if not video_public_url:
        print(f"  [EXTEND] R2 upload failed — aborting extend")
        return None

    dur_valid = 10 if duration >= 10 else 5
    payload = {
        "video_url": video_public_url,
        "prompt": prompt[:900],
        "duration": dur_valid,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "remove_watermark": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print(f"  [EXTEND] Submitting {dur_valid}s extension — prompt: {prompt[:80]}...")
    try:
        resp = _req.post(SEEDANCE_EXTEND_ENDPOINT, json=payload, headers=headers, timeout=30)
        body = resp.text
        if not resp.ok:
            print(f"  [EXTEND] Submit FAILED {resp.status_code}: {body[:300]}")
            return None
        data = resp.json()
    except Exception as e:
        print(f"  [EXTEND] Submit exception: {e}")
        return None

    request_id = data.get("request_id") or data.get("id") or data.get("prediction_id")
    if not request_id:
        print(f"  [EXTEND] No request_id in response: {data}")
        return None

    print(f"  [EXTEND] Submitted → request_id={request_id}, polling...")

    # Poll (same pattern as gen_seedance_video)
    poll_url = SEEDANCE_POLL.format(request_id=request_id)
    max_wait, elapsed = 600, 0
    while elapsed < max_wait:
        time.sleep(8)
        elapsed += 8
        try:
            r = _req.get(poll_url, headers=headers, timeout=15)
            if not r.ok:
                if r.status_code in (404, 400):
                    print(f"  [EXTEND] Poll fatal {r.status_code}: {r.text[:200]}")
                    return None
                continue
            result = r.json()
        except Exception:
            continue

        status = (result.get("status") or "").lower()
        if status in ("succeeded", "completed", "done") or result.get("video_url") or result.get("outputs"):
            ext_url = (
                result.get("outputs", [None])[0] if result.get("outputs") else None
            ) or result.get("video_url") or result.get("output", {}).get("video_url")

            if not ext_url:
                print(f"  [EXTEND] Completed but no video URL in response: {result}")
                return None

            # Download extension clip
            ext_tmp = source_video_path.replace(".mp4", "_ext_segment.mp4")
            try:
                er = _req.get(ext_url, timeout=120, stream=True)
                er.raise_for_status()
                with open(ext_tmp, "wb") as ef:
                    for chunk in er.iter_content(65536):
                        ef.write(chunk)
                print(f"  [EXTEND] Extension downloaded → {ext_tmp} ({os.path.getsize(ext_tmp)//1024}KB)")
            except Exception as e:
                print(f"  [EXTEND] Download failed: {e}")
                return None

            # Concatenate source + extension using ffmpeg concat demuxer
            concat_path = source_video_path.replace(".mp4", "_extended.mp4")
            concat_list = source_video_path.replace(".mp4", "_concat_list.txt")
            try:
                with open(concat_list, "w") as cl:
                    cl.write(f"file '{os.path.abspath(source_video_path)}'\n")
                    cl.write(f"file '{os.path.abspath(ext_tmp)}'\n")
                concat_result = subprocess.run(
                    [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", concat_list,
                        "-c", "copy",
                        concat_path,
                    ],
                    capture_output=True, text=True
                )
                if concat_result.returncode != 0 or not os.path.exists(concat_path):
                    print(f"  [EXTEND] FFmpeg concat failed: {concat_result.stderr[-300:]}")
                    return None
                # Clean up temp files
                os.remove(ext_tmp)
                os.remove(concat_list)
                ext_size = os.path.getsize(concat_path) // (1024 * 1024)
                print(f"  [EXTEND] ✓ Extended video → {concat_path} ({ext_size}MB)")
                _track_cost("seedance", duration=dur_valid)
                return concat_path
            except Exception as e:
                print(f"  [EXTEND] Concat error: {e}")
                return None

        elif status in ("failed", "error", "cancelled"):
            print(f"  [EXTEND] FAILED: {result.get('error', result)}")
            return None
        elif elapsed % 30 == 0:
            print(f"  [EXTEND] Waiting... {elapsed}s (status={status})")

    print(f"  [EXTEND] TIMEOUT after {max_wait}s")
    return None


def gen_scene_seedance(mshots, cast, first_frame_path, mode, outdir, scene_id=None, locs=None, location_text="", all_frames=None):
    """
    V29.15: CONTINUITY-FIRST Seedance — end-frame chaining + location spatial anchor.

    THREE ROOT-CAUSE FIXES for spatial drift / cut drifting:

    FIX 1 — CHARACTER-FIRST images_list ORDERING (V29.16 Phase 2.2 corrected):
      images_list = [start_frame, char_ref_1, char_ref_2, location_master]
      CHARACTER refs at slots @image2 + @image3 (highest Seedance attention weight).
      LOCATION master at slot @image4 (lower priority — room context, not identity).
      Role assignments injected into prompt: "@image2 and @image3 define character
      faces and clothing. @image4 shows the room architecture."
      ⚠ STALE ORDERING WAS: [start_frame, location_master, char1, char2] — location
        at slot [1] competed with characters for primary attention → identity drift.
      V29.16 NEW-K FIX: this comment updated to reflect Phase 2.2 correct order.

    FIX 2 — SEQUENTIAL END-FRAME CHAINING:
      Shot N's last frame → images_list[0] for Shot N+1.
      This is the Kling continuity principle applied to Seedance:
        Shot 1: images_list = [first_frame_M01, char1, char2, loc_master]
        Shot 2: images_list = [last_frame_shot1, char1, char2, loc_master]
        Shot 3: images_list = [last_frame_shot2, char1, char2, loc_master]
      Characters don't "jump" between shots — they continue from where they were.
      Trade-off: sequential (not parallel) = ~7min/scene vs ~2min, but NO DRIFT.

    FIX 3 — 15s FOR EMOTIONAL BEATS:
      authored 12s → round-up to 15s (not nearest which gives 10s).
      Round-up logic: if base_dur > 10 → use 15s. Otherwise use authored.
      Closing beats (5-10s) stay short.
    """
    import shutil as _shutil
    import re as _re
    _reset_cost_tracker()  # FIX-ERR-08: reset per-scene so multi-scene cost tracking is accurate
    seedance_models = _seedance_models_for_run()
    primary_model = seedance_models[0]
    variant_models = seedance_models[1:]
    outdir_path = Path(outdir)
    os.makedirs(outdir, exist_ok=True)
    tag_suffix = outdir_path.name[len("videos_seedance_"):] if outdir_path.name.startswith("videos_seedance_") else outdir_path.name
    variant_dirs: Dict[str, str] = {primary_model: str(outdir_path)}
    variant_manifest: Dict[str, Dict[str, object]] = {}
    for model_key in variant_models:
        variant_dir = _seedance_variant_outdir(str(outdir_path), model_key, tag_suffix)
        variant_dirs[model_key] = variant_dir
        variant_manifest[model_key] = {"per_shot": {}, "outdir": variant_dir}
    seedance_sequence: List[str] = [s.get("shot_id") for s in mshots if s.get("shot_id")]
    results = {}

    def _render_variant_versions(shot_dict, prompt_text, image_urls, duration, quality_level, prefix, group_index):
        if not variant_models:
            return
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        for model_key in variant_models:
            try:
                temp_video = gen_seedance_video(prompt_text, list(image_urls), duration=duration, quality=quality_level, model_key=model_key)
                if not temp_video:
                    print(f"  [VARIANT:{model_key}] {shot_dict['shot_id']}: FAILED")
                    continue
                oname = f"{prefix}{model_key}_group_{group_index+1:02d}.mp4"
                dest_dir = variant_dirs[model_key]
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, oname)
                _shutil.copy2(temp_video, dest_path)
                os.remove(temp_video)
                manifest_entry = variant_manifest.get(model_key)
                if manifest_entry is not None:
                    manifest_entry.setdefault("per_shot", {})[shot_dict["shot_id"]] = dest_path
                shot_variants = shot_dict.setdefault("_seedance_variants", {})
                shot_variants[model_key] = {"video_path": dest_path, "generated_at": timestamp, "model": model_key}
                print(f"  [VARIANT:{model_key}] {shot_dict['shot_id']}: OK — {os.path.getsize(dest_path)//1024}KB")
            except Exception as _variant_err:
                print(f"  [VARIANT:{model_key}] {shot_dict['shot_id']}: ERROR ({_variant_err})")

    if not mshots:
        return results

    # ── Pre-upload scene-level assets (reused across all shots) ──────────────
    # Location master: scene spatial anchor — keeps the room consistent
    loc_master_url = None
    if locs and location_text:
        loc_path = get_location_ref(locs, location_text)
        if loc_path:
            loc_master_url = upload_public(loc_path)
            print(f"  [SEEDANCE] Location anchor: {os.path.basename(loc_path)}")

    # Character references: identity anchors (shared across all shots in scene)
    all_chars = sorted(set(c for s in mshots for c in (s.get("characters") or [])))
    char_ref_urls = []
    for c in all_chars[:2]:  # max 2 char refs (leave slots for start_frame + loc_master)
        ref = get_char_ref(cast, c)
        if ref:
            ref_url = upload_public(ref)
            if ref_url:
                char_ref_urls.append(ref_url)
                print(f"  [SEEDANCE] Char ref: {c.split()[0]}")

    # ── Duration logic: prefer 15s for emotional beats ───────────────────────
    _TIMESTAMP_PAT = _re.compile(r'\d+[\-–]\d+s:\s*')
    _CHAR_PREFIXES = (_ACTIVE_CHAR_PREFIXES or ["NADIA COLE:", "THOMAS BLACKWOOD:", "ELEANOR VOSS:", "RAYMOND CROSS:", "HARRIET HARGROVE:"])
    valid_durs = [5, 10, 15]

    def _resolve_duration(s):
        """V29.15: round-up to 15s for beats authored >10s."""
        dlg_text = s.get("dialogue_text", "") or ""
        base_dur = int(str(s.get("duration", "10")).strip())
        if dlg_text:
            words = len(dlg_text.split())
            min_dlg = int(words / 2.3 + 1.5)
            base_dur = max(base_dur, min_dlg)
        # Round-up: any beat authored >10s gets 15s (emotional beats deserve full duration)
        if base_dur > 10:
            return 15
        return min(valid_durs, key=lambda x: abs(x - base_dur))

    # ── CAMERA DIRECTIVE MAP (V30.1 — Prompt Vision Analysis P1.1) ─────────────
    # Maps beat type → specific Seedance camera movement language.
    # "Continuous motion." was the worst possible instruction — FAL-specific generic.
    # These are the 5 camera terms that produce cinematic output per Seedance 2.0 guide.
    _BEAT_CAMERA_MAP = {
        "arrival":       "slow push-in dolly following entry",
        "confrontation": "static locked, camera anchored, no drift",
        "revelation":    "slow push-in from wide to close",
        "emotional_break": "subtle handheld, slight instability",
        "departure":     "slow pull back as character recedes",
        "dialogue":      "static locked, subtle eye-level drift only",
        "discovery":     "slow push-in from wide, hesitant approach",
        "reaction":      "static locked, tight on face",
        "movement":      "tracking shot following motion through space",
        "establishing":  "slow pull back, reveal room geography",
    }

    def _get_camera_directive(s):
        """Derive camera movement from beat type, shot type, and emotional arc."""
        shot_type = s.get("shot_type", "medium")
        beat_action = (s.get("_beat_action") or "").lower()
        # Match beat keywords → camera directive
        for keyword, directive in _BEAT_CAMERA_MAP.items():
            if keyword in beat_action:
                return directive
        # Shot-type fallbacks
        if shot_type in ("establishing", "wide"):
            return "slow pull back, reveal room geography"
        if shot_type in ("close_up", "mcu", "reaction"):
            return "static locked, tight on face, no camera drift"
        if "dialogue" in beat_action or s.get("dialogue_text"):
            return "static locked, subtle eye-level drift only"
        return "static locked"  # Default: stable frame beats generic "Continuous motion"

    def _build_temporal_arc(s, dur):
        """V30.1 P1.2: Time-indexed action sequence for shots >= 8s.
        Seedance excels at multi-action sequences — flat 'Continuous motion' wastes this.
        """
        dur = int(dur)
        if dur < 8:
            return ""
        dialogue = (s.get("_beat_dialogue") or s.get("dialogue_text") or "").strip()
        action = (s.get("_beat_action") or s.get("description", ""))[:60]
        if dialogue:
            word_count = len(dialogue.split())
            speak_start = 2
            speak_end = min(dur - 2, speak_start + (word_count / 2.3))
            return f"0-{speak_start}s: character settles. {speak_start:.0f}-{speak_end:.0f}s: delivers dialogue. {speak_end:.0f}-{dur}s: holds, reaction settles."
        else:
            return f"0-3s: {action}. 3-{dur-2}s: action develops with physical weight. {dur-2}-{dur}s: action resolves. HOLD final pose."

    # V30.6: Seedance v2.0 quality/stability suffix — published best practice.
    # Anchors face+clothing consistency and suppresses flickering/blur artifacts.
    # 90 chars. Appended as final token on every Seedance prompt (cannot be overridden
    # by content budget — budget check uses _SEEDANCE_CAP_CONTENT, suffix added after).
    # Source: ByteDance Seedance v2.0 prompting guide + community validation.
    _SEEDANCE_QUALITY_SUFFIX = (
        " Maintain face and clothing consistency, no distortion."
        " No blur, no flickering, stable picture."
    )
    _SEEDANCE_CAP_CONTENT = 660   # content budget: 750 total − 90 suffix chars
    _SEEDANCE_CAP_TOTAL   = 750   # hard cap sent to MUAPI

    def _build_prompt(s, next_shot=None):
        """V30.6 INTELLIGENCE-DRIVEN + CINEMATIC + QUALITY ANCHORED.

        Builds Seedance v2.0 video prompts from all available truth fields.
        V30.6 adds: quality/stability suffix (face+clothing lock, no flicker/blur)
                    raised ceiling 490 → 750 chars total (660 content + 90 suffix)

        REMOTE BRAIN QUESTIONS ANSWERED:
        - What is happening? (_beat_action — physical kinetic action)
        - What is the emotional atmosphere? (_beat_atmosphere — tone, mood)
        - What is the body doing? (_body_direction — T2-TL-5 field)
        - What is said? (_beat_dialogue — actual dialogue text)
        - What camera movement? (_get_camera_directive — from BEAT_CAMERA_MAP)
        - What temporal sequence? (_build_temporal_arc — time-indexed for shots >= 8s)

        Priority: manual _seedance_prompt > full truth field assembly > bare fallback
        """
        seedance_p = s.get("_seedance_prompt", "").strip()
        if seedance_p:
            # Manual override: still get the suffix if not already present
            base_p = seedance_p[:_SEEDANCE_CAP_CONTENT]
            if _SEEDANCE_QUALITY_SUFFIX.strip() not in base_p:
                return (base_p + _SEEDANCE_QUALITY_SUFFIX)[:_SEEDANCE_CAP_TOTAL]
            return base_p[:_SEEDANCE_CAP_TOTAL]

        # FULL TRUTH FIELD ASSEMBLY: query all available intelligence from story bible
        # PRIORITY: _beat_action (specific kinetic verb) > choreography (if not CPC-contaminated)
        action = s.get("_beat_action") or s.get("description", "")
        body = s.get("_body_direction", "")  # T2-TL-5: body movement state
        atm = s.get("_beat_atmosphere", "")

        # Choreography: ONLY use if it's NOT CPC-contaminated generic text
        # CPC blacklist patterns that indicate generic choreography (T2-CPC-3)
        _CPC_PATTERNS = [
            "the character begins to speak", "body language shifting with intention",
            "natural rhythm of conversation", "the moment lands", "the scene breathes",
            "experiences the moment", "present and engaged", "natural movement begins",
            "subtle expression", "gestures accompany the words",
        ]
        choreo_raw = (s.get("_choreography") or "").lower()
        choreo_is_generic = any(p in choreo_raw for p in _CPC_PATTERNS)
        # Use beat_action (clean, specific) always; supplement with choreography only if not generic
        base = action
        if not base:
            clean_choreo = _TIMESTAMP_PAT.sub("", s.get("_choreography", "")).replace("Then,", "").strip()
            if choreo_is_generic:
                base = s.get("description", "")
            elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
                # Embedding detected paraphrased generic choreography the keyword list missed
                import logging as _log
                _log.getLogger("atlas.runner").warning(
                    f"CPC-EMBED: shot {s.get('shot_id','?')} choreography is semantically "
                    f"generic (cosine > {_CPC_SIM_THRESHOLD}) — falling back to description"
                )
                base = s.get("description", "")
            else:
                base = clean_choreo

        # Dialogue: prefer _beat_dialogue; extract from choreography as fallback (has "Speaking:" marker)
        dlg = (s.get("_beat_dialogue") or "").strip()
        if not dlg and "Speaking:" in (s.get("_choreography") or ""):
            import re as _re2
            dlg_match = _re2.search(r'Speaking:\s*"([^"]*)"', s.get("_choreography", ""))
            if dlg_match:
                dlg = dlg_match.group(1).strip()
        if not dlg:
            dlg = (s.get("dialogue_text") or "").strip()
        for pfx in _CHAR_PREFIXES:
            dlg = dlg.replace(pfx, "").replace(pfx.upper(), "")
        dlg = dlg.replace("|", " ").strip()

        # Assemble: kinetic action → body direction → atmosphere → dialogue
        # V30.1: + camera directive (replaces "Continuous motion.") + temporal arc
        shot_dur = int(s.get("duration", 10))
        cam = _get_camera_directive(s)
        arc = _build_temporal_arc(s, shot_dur)

        part = base[:200]
        if body and body not in ("present, natural micro-movements", "neutral, present in scene"):
            part += f". {body[:60]}"
        if atm:
            part += f". {atm[:80]}"
        if dlg:
            part += f'. "{dlg[:80]}"'
        # Camera directive replaces generic "Continuous motion." (Prompt Vision Analysis P1.1)
        part += f". {cam}."
        # Temporal arc for long shots >= 8s (P1.2) — appended only if content budget allows
        if arc:
            remaining = _SEEDANCE_CAP_CONTENT - len(part.strip())
            if remaining > len(arc) + 2:
                part += f" {arc}"
        # V30.5: Premeditated end-frame staging
        # Read next shot's opening description to stage current shot's ending pose.
        # This encodes the landing intent into the prompt itself, removing dependency on
        # runtime end-frame chaining for spatial continuity between shots.
        if next_shot:
            _next_desc = (next_shot.get("_frame_description") or next_shot.get("description") or "").strip()
            if _next_desc:
                _landing = f"Final 2s: settle into position. {_next_desc[:100]}. HOLD final pose."
                _rem = _SEEDANCE_CAP_CONTENT - len(part.strip())
                if _rem > len(_landing) + 2:
                    part += f" {_landing}"
        # V30.6: Quality/stability suffix — always appended as final token (T2-FE-38)
        # Anchors face+clothing consistency and suppresses flicker/blur artifacts.
        content = part.strip()[:_SEEDANCE_CAP_CONTENT]
        return (content + _SEEDANCE_QUALITY_SUFFIX)[:_SEEDANCE_CAP_TOTAL]

    # V30.5: Parallel flag — premeditated end-frame staging in _build_prompt() means each shot
    # encodes its own landing pose, so shots no longer need to chain at runtime.
    # Set False to fall back to the original sequential end-frame chaining path.
    _USE_PARALLEL_VIDEO = True

    # ── V30.5: PARALLEL VIDEO GENERATION ─────────────────────────────────────
    if _USE_PARALLEL_VIDEO:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _par_quality = "high"  # V30.5: always high quality for Seedance
        print(f"\n  [PARALLEL VIDEO] {len(mshots)} shots | max_workers=4 | quality={_par_quality}")

        def _gen_one_video(shot_idx_data):
            _gi, _s = shot_idx_data
            _sid = _s["shot_id"]
            _next_s = mshots[_gi + 1] if _gi + 1 < len(mshots) else None
            # Per-shot first frame: use all_frames dict if provided, else fall back to scene first frame
            _sfp = (all_frames or {}).get(_sid) or first_frame_path
            _start_url = upload_public(_sfp)
            if not _start_url:
                print(f"  [PAR] {_sid}: SKIP — could not upload first frame")
                return _sid, None
            # Build call_images with the same hero-shot vs multi-char logic as sequential path
            _shot_type = _s.get("shot_type", "medium")
            _hero_types = ("close_up", "mcu", "medium_close", "reaction", "ecm")
            _cimgs = [_start_url]
            if _shot_type in _hero_types and len(_s.get("characters") or []) == 1:
                _sc = (_s.get("characters") or [None])[0]
                _cd = cast.get(_sc or "", {}) if isinstance(cast.get(_sc or "", {}), dict) else {}
                _hp = _cd.get("character_reference_url") or get_char_ref(cast, _sc or "")
                _tqp = _cd.get("three_quarter_url") or _cd.get("three_quarter_reference_url")
                if _hp:
                    _hu = upload_public(_hp)
                    if _hu:
                        _cimgs.append(_hu)
                if _tqp:
                    _tqu = upload_public(_tqp)
                    if _tqu:
                        _cimgs.append(_tqu)
                elif len(char_ref_urls) >= 1 and len(_cimgs) < 3:
                    _cimgs.append(char_ref_urls[0])
            elif (_s.get("characters") or []) and not _s.get("_no_char_ref"):
                # E-shot guard: shots with characters=[] or _no_char_ref=True NEVER get character refs
                _cimgs.extend(char_ref_urls)
            elif not (_s.get("characters") or []):
                print(f"  [E-SHOT GUARD] {_sid}: no char refs — pure environment shot")
            if loc_master_url:
                _cimgs.append(loc_master_url)
            # Build prompt with premeditated end-frame staging (next_shot encodes landing)
            _prompt = _build_prompt(_s, next_shot=_next_s)
            _cont = (_s.get("_continuity_delta") or "").strip()
            if _cont:
                _prompt = (_prompt.rstrip(".") + f" [CONTINUITY: {_cont[:80]}]")[:600]
            _zone = (_s.get("_spatial_zone") or "").strip()
            if _zone:
                _prompt = (_prompt.rstrip(".") + f" [ZONE: {_zone[:60]}]")[:600]
            _dur = int(_resolve_duration(_s))
            print(f"  [PAR {_gi+1}/{len(mshots)}] {_sid} | {_dur}s | {len(_cimgs)} imgs | {len(_prompt)}c")
            print(f"    Prompt: {_prompt[:90]}...")
            _push_live_gen(_sid, "running", "video")
            _vpath = gen_seedance_video(_prompt, _cimgs, duration=_dur, quality=_par_quality, model_key=primary_model)
            if _vpath:
                _pfx2 = f"{scene_id}_" if scene_id else ""
                _oname = f"{_pfx2}seedance_group_{_gi+1:02d}.mp4"
                _opath = os.path.join(outdir, _oname)
                import shutil as _shutil_par
                _shutil_par.copy2(_vpath, _opath)
                os.remove(_vpath)
                _track_cost(primary_model, duration=_dur)
                # Mutate shot dict in-place (same as sequential — filmstrip sync reads this)
                _s["_seedance_prompt"] = _prompt
                _s["_seedance_duration"] = _dur
                _s["_seedance_quality"] = _par_quality
                _s["video_url"] = _opath
                _s["video_path"] = _opath
                _s["_video_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                _s["_approval_status"] = _s.get("_approval_status") or "AUTO_APPROVED"
                _push_live_gen(_sid, "completed", "video", url=f"/api/media?path={_opath}")
                print(f"  [PAR] {_sid}: OK — {os.path.getsize(_opath)//1024}KB")
                _render_variant_versions(_s, _prompt, _cimgs, _dur, _par_quality, _pfx2, _gi)
                return _sid, _opath
            else:
                print(f"  [PAR] {_sid}: FAILED")
                _push_live_gen(_sid, "error", "video")
                return _sid, None

        with ThreadPoolExecutor(max_workers=4) as _pool:
            _futs = {_pool.submit(_gen_one_video, (gi, s)): s["shot_id"]
                     for gi, s in enumerate(mshots)}
            for _f in as_completed(_futs):
                _fsid = _futs[_f]
                try:
                    _rsid, _rpath = _f.result()
                    if _rpath:
                        results[_rsid] = _rpath
                except Exception as _fe:
                    print(f"  [PAR] {_fsid}: ERROR ({_fe})")

    if not _USE_PARALLEL_VIDEO:
        # ── SEQUENTIAL EXECUTION WITH END-FRAME CHAINING (legacy) ────────────────
        # Shot N completes → extract last frame → becomes images_list[0] for Shot N+1
        # This is the cinematic continuity contract: each shot begins where the last ended.
        current_start_frame_url = upload_public(first_frame_path)
        if not current_start_frame_url:
            print(f"  [SEEDANCE] FAIL: Could not upload first frame")
            return results

        for gi, s in enumerate(mshots):
            sid = s["shot_id"]
            shot_dur = _resolve_duration(s)
            prompt = _build_prompt(s, next_shot=mshots[gi + 1] if gi + 1 < len(mshots) else None)

            # V30.5: Inject continuity delta + spatial zone into Seedance prompt
            # NOTE: caps at 600 (not 490) — Seedance accepts longer prompts than nano
            _cont = (s.get("_continuity_delta") or "").strip()
            if _cont:
                prompt = (prompt.rstrip(".") + f" [CONTINUITY: {_cont[:80]}]")[:600]
            _zone = (s.get("_spatial_zone") or "").strip()
            if _zone:
                prompt = (prompt.rstrip(".") + f" [ZONE: {_zone[:60]}]")[:600]

            # Phase 2.2 FIX + V30.1 P3.3: images_list ordering — char refs BEFORE location master
            # Seedance weights early slots more heavily. Character identity is the #1 failure mode.
            # HERO SHOT EXPANSION (V30.1 P3.3 — Prompt Vision Analysis):
            #   For close_up / MCU / reaction: use headshot (@image2) + three_quarter ref (@image3)
            #   These serve DIFFERENT purposes (face identity vs body/clothing) per Seedance 2.0 guide.
            #   For multi-char / medium shots: use char1 + char2 as before.
            shot_type_here = s.get("shot_type", "medium")
            _hero_types = ("close_up", "mcu", "medium_close", "reaction", "ecm")
            call_images = [current_start_frame_url]
            if shot_type_here in _hero_types and len(s.get("characters") or []) == 1:
                # Single-character hero shot: headshot for face, three_quarter for body
                _solo_char = (s.get("characters") or [None])[0]
                _cdata = cast.get(_solo_char or "", {}) if isinstance(cast.get(_solo_char or "", {}), dict) else {}
                _headshot_path = _cdata.get("character_reference_url") or get_char_ref(cast, _solo_char or "")
                _tq_path = _cdata.get("three_quarter_url") or _cdata.get("three_quarter_reference_url")
                if _headshot_path:
                    _head_url = upload_public(_headshot_path)
                    if _head_url:
                        call_images.append(_head_url)  # @image2 = face identity
                        print(f"  [HERO-REF] {sid}: headshot at @image2")
                if _tq_path:
                    _tq_url = upload_public(_tq_path)
                    if _tq_url:
                        call_images.append(_tq_url)    # @image3 = body/clothing
                        print(f"  [HERO-REF] {sid}: three_quarter at @image3")
                elif len(char_ref_urls) >= 1 and len(call_images) < 3:
                    call_images.append(char_ref_urls[0])  # fallback: same headshot at @image3
            elif (s.get("characters") or []) and not s.get("_no_char_ref"):
                # Multi-char or non-hero: standard [char1, char2] pack
                # E-shot guard: shots with characters=[] or _no_char_ref=True NEVER get character refs
                # (E01/E02/E03 are pure environment — injecting char refs forces AI to invent people)
                call_images.extend(char_ref_urls)  # @image2, @image3 = character identity (priority)
            elif not (s.get("characters") or []):
                print(f"  [E-SHOT GUARD] {sid}: no char refs — pure environment shot")
            if loc_master_url:
                call_images.append(loc_master_url)  # @image4 = room architecture (lower priority)

            print(f"  [SEEDANCE {gi+1}/{len(mshots)}] {sid} | {shot_dur}s | {len(call_images)} imgs | {len(prompt)}c")
            _chain_src = "M01 first_frame" if gi == 0 else ("last_frame_" + mshots[gi-1]["shot_id"])
            print(f"    Chain: {_chain_src}")
            print(f"    Prompt: {prompt[:90]}...")

            _push_live_gen(sid, "running", "video")
            quality = "high"  # V30.5: always high quality for Seedance
            video_path = gen_seedance_video(prompt, call_images, duration=shot_dur, quality=quality, model_key=primary_model)

            if video_path:
                _pfx = f"{scene_id}_" if scene_id else ""
                out_name = f"{_pfx}seedance_group_{gi+1:02d}.mp4"
                out_path = os.path.join(outdir, out_name)
                _shutil.copy2(video_path, out_path)
                os.remove(video_path)
                results[sid] = out_path
                _track_cost(primary_model, duration=shot_dur)  # ERR-05 FIX: track Seedance cost
                print(f"    → {out_path}")
                _push_live_gen(sid, "completed", "video", url=f"/api/media?path={out_path}")

                # ── FILMSTRIP CONSCIOUSNESS (V30.0) ─────────────────────────────────
                s["_seedance_prompt"] = prompt
                s["_seedance_duration"] = shot_dur
                s["_seedance_quality"] = quality
                s["video_url"] = out_path
                s["video_path"] = out_path
                s["_video_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                s["_approval_status"] = s.get("_approval_status") or "AUTO_APPROVED"
                # ────────────────────────────────────────────────────────────────────
                _render_variant_versions(s, prompt, call_images, shot_dur, quality, _pfx, gi)

                # ── VISION JUDGE ──────────────────────────────────────────────────
                _vid_judge_score = 0.75
                chars_in_shot = s.get("characters") or []
                if chars_in_shot and VISION_JUDGE_AVAILABLE:
                    try:
                        _tmp_first = os.path.join(outdir, f"{sid}_vjudge_first.jpg")
                        _ffmpeg_extract = subprocess.run(
                            ["ffmpeg", "-y", "-i", out_path, "-vframes", "1",
                             "-q:v", "2", _tmp_first],
                            capture_output=True, text=True
                        )
                        if os.path.exists(_tmp_first):
                            _shot_dict = s
                            _verdict = judge_frame(sid, _tmp_first, _shot_dict, cast)
                            if _verdict and _verdict.identity_scores:
                                _vid_judge_score = sum(_verdict.identity_scores.values()) / len(_verdict.identity_scores)
                            _track_cost("florence")
                            os.remove(_tmp_first)
                            print(f"    [VID-JUDGE] {sid}: I={_vid_judge_score:.2f} ({getattr(_verdict,'verdict','?')})")
                    except Exception as _je:
                        print(f"    [VID-JUDGE] {sid}: judge skipped ({_je})")

                # ── SEEDANCE EXTEND (V30.0) ──────────────────────────────────────
                _wants_extend = s.get("_extend_shot") or s.get("_extend_duration_extra", 0) > 0
                if _wants_extend:
                    _ext_dur = int(s.get("_extend_duration_extra") or 5)
                    _ext_dur = 10 if _ext_dur >= 10 else 5
                    _ext_prompt = s.get("_extend_prompt") or s.get("_beat_action") or "Continue scene naturally, same characters same room"
                    print(f"    [EXTEND] Shot flagged for extension → +{_ext_dur}s | {_ext_prompt[:60]}...")
                    _extended_path = gen_seedance_extend(
                        source_video_path=out_path,
                        prompt=_ext_prompt,
                        duration=_ext_dur,
                        quality=quality,
                    )
                    if _extended_path and os.path.exists(_extended_path):
                        _shutil.copy2(_extended_path, out_path)
                        os.remove(_extended_path)
                        results[sid] = out_path
                        print(f"    [EXTEND] ✓ Extended video written to {out_path}")
                    else:
                        print(f"    [EXTEND] ✗ Extension failed — keeping base video unchanged")

                # END-FRAME CHAIN: extract last frame → start frame for next shot
                chain_frame_path = os.path.join(outdir, f"{_pfx}chain_{gi+1:02d}_lastframe.jpg")
                extract_last_frame(out_path, chain_frame_path)
                if os.path.exists(chain_frame_path):
                    chain_url = upload_public(chain_frame_path)
                    if chain_url:
                        current_start_frame_url = chain_url
                        print(f"    ⛓ Chain: last_frame → next shot start")
                    else:
                        print(f"    ⚠ Chain upload failed — reusing previous start")
                else:
                    print(f"    ⚠ Chain extract failed — reusing previous start")
            else:
                print(f"  [SEEDANCE {gi+1}] {sid}: FAILED — skipping chain update")
                _push_live_gen(sid, "error", "video")

    # ── FILMSTRIP SYNC: persist all prompt/video updates to shot_plan (V30.0) ──
    # The mshots list is a reference to the in-memory shot dicts — but the UI reads
    # from shot_plan.json. Write all _seedance_prompt / video_url fields back now
    # so the filmstrip reflects exactly what ran, with no delay.
    try:
        _sp_sync_path = Path(outdir).parent / "shot_plan.json"
        if _sp_sync_path.exists():
            _sp_raw_sync = json.load(open(_sp_sync_path))
            _is_list_sync = isinstance(_sp_raw_sync, list)
            _sp_shots_sync = _sp_raw_sync if _is_list_sync else _sp_raw_sync.get("shots", [])
            _shot_map_sync = {s.get("shot_id"): s for s in _sp_shots_sync}
            for _ms in mshots:
                _msid = _ms.get("shot_id")
                if _msid in _shot_map_sync:
                    # Push filmstrip-relevant fields from in-memory dict back to plan
                    for _fkey in ["_seedance_prompt", "_seedance_duration", "_seedance_quality",
                                  "video_url", "video_path", "_video_generated_at",
                                  "_approval_status", "_seedance_variants",
                                  "_extend_status", "_extend_duration_extra",
                                  "_extend_prompt", "_extended_at", "_extended_total_duration"]:
                        if _fkey in _ms:
                            _shot_map_sync[_msid][_fkey] = _ms[_fkey]
            import shutil as _shutil_sync
            _shutil_sync.copy(_sp_sync_path, str(_sp_sync_path) + ".backup_seedance_sync")
            with open(_sp_sync_path, "w") as _sf:
                json.dump(_sp_raw_sync, _sf, indent=2)
            # Invalidate UI cache so filmstrip refreshes
            _ui_cache = _sp_sync_path.parent / "ui_cache"
            _ui_cache.mkdir(exist_ok=True)
            (_ui_cache / "bundle.dirty").touch()
            print(f"\n  [FILMSTRIP] Shot plan synced — {len([m for m in mshots if m.get('video_url')])} videos written to plan. UI refreshed.")
        else:
            print(f"  [FILMSTRIP] WARNING: shot_plan.json not found at {_sp_sync_path} — UI not synced")
    except Exception as _sync_err:
        print(f"  [FILMSTRIP] WARNING: shot_plan sync failed ({_sync_err}) — run will still produce videos")

    return results, {"models": variant_manifest, "shot_sequence": seedance_sequence}


# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════
def load_project(project):
    pdir = Path("pipeline_outputs") / project
    sp = json.load(open(pdir / "shot_plan.json"))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    sb = json.load(open(pdir / "story_bible.json"))
    cm_raw = json.load(open(pdir / "cast_map.json"))
    cast = {k: v for k, v in cm_raw.items() if isinstance(v, dict) and v.get("appearance")}
    locs = {}
    loc_dir = pdir / "location_masters"
    if loc_dir.exists():
        for f in loc_dir.glob("*.jpg"):
            locs[f.stem] = str(f)
    return shots, sb, cast, locs

def get_sb_scene(sb, sid):
    return next((s for s in sb.get("scenes", []) if s.get("scene_id") == sid), {})

def get_char_ref(cast, name):
    for k, v in cast.items():
        if name.upper() in k.upper():
            return v.get("character_reference_url") or v.get("reference_url") or v.get("headshot_url")
    return None

def get_location_ref(locs, location_text):
    loc_key = location_text.upper().replace(" ", "_").replace("-", "_")
    for part in ["LIBRARY", "FOYER", "DRAWING_ROOM", "BEDROOM", "KITCHEN",
                 "STAIRCASE", "GARDEN", "FRONT_DRIVE", "EXTERIOR"]:
        if part in loc_key:
            for stem, path in locs.items():
                if part in stem.upper() and "medium" not in stem.lower() and "reverse" not in stem.lower():
                    return path
    return None

def upload(fp):
    if not fp or not os.path.exists(fp): return None
    return fal_client.upload_file(fp)

def upload_public(fp):
    """
    V29.12: Upload image to Cloudflare R2 for MUAPI/Seedance use.
    FAL CDN is blocked when balance=0, so Seedance runs use R2 (atlas.fanztv.com bucket).
    R2 provides permanent public URLs at https://media.rumbletv.com/atlas/seedance/{filename}
    """
    import hashlib
    if not fp or not os.path.exists(fp):
        return None

    fname = os.path.basename(fp)

    # 1. Try Cloudflare R2 (fastest, permanent, no per-upload cost)
    try:
        import boto3 as _boto3
        from dotenv import load_dotenv as _lde
        _lde(".env")
        _r2_acct = os.environ.get("ATLAS_R2_ACCOUNT_ID", "")
        _r2_key = os.environ.get("ATLAS_R2_ACCESS_KEY_ID", "")
        _r2_sec = os.environ.get("ATLAS_R2_SECRET_KEY", "")
        _r2_buck = os.environ.get("ATLAS_R2_BUCKET", "rumble-fanz")
        _r2_pub = os.environ.get("ATLAS_R2_PUBLIC_URL", "https://media.rumbletv.com")
        if _r2_acct and _r2_key and _r2_sec:
            _s3 = _boto3.client(
                's3',
                endpoint_url=f"https://{_r2_acct}.r2.cloudflarestorage.com",
                aws_access_key_id=_r2_key,
                aws_secret_access_key=_r2_sec,
                region_name='auto'
            )
            # Deduplicate by content hash so same frame isn't re-uploaded
            with open(fp, 'rb') as _f:
                _h = hashlib.md5(_f.read()).hexdigest()[:8]
            _ext = os.path.splitext(fname)[1] or '.jpg'
            _key = f"atlas/seedance/{_h}_{fname}"
            _s3.upload_file(fp, _r2_buck, _key, ExtraArgs={'ContentType': 'image/jpeg'})
            _url = f"{_r2_pub}/{_key}"
            print(f"  [UPLOAD] R2 → {_url}")
            return _url
        else:
            print(f"  [UPLOAD] R2 creds missing")
    except Exception as e:
        print(f"  [UPLOAD] R2 error: {e}")

    # 2. Fallback to FAL upload (may fail if balance=0 but worth trying)
    try:
        url = fal_client.upload_file(fp)
        if url:
            print(f"  [UPLOAD] FAL CDN → {url[:60]}")
            return url
    except Exception as e:
        print(f"  [UPLOAD] FAL CDN also failed: {e}")
    return None

# ═══════════════════════════════════════════════════════════════
# MODEL ROUTING — Seedance primary, Kling character fallback (LTX RETIRED C3)
# ═══════════════════════════════════════════════════════════════
def route_shot(shot):
    """Route to Kling (PRIMARY — all shots) or flag for direct nano (pure env, no elements).
    V31.0: KLING IS THE PRIMARY VIDEO MODEL. Seedance RETIRED.
    Character shots → Kling multi-prompt with @Element identity blocks.
    Environment/B-roll (no chars, no dialogue) → Kling without elements.
    Returns ('kling', reason) for all shot types."""
    chars = shot.get("characters") or []
    stype = (shot.get("shot_type") or "").lower()
    has_dlg = bool(shot.get("dialogue_text"))

    if chars or has_dlg:
        return "kling", f"Character shot ({len(chars)} chars, {stype}) — @Element identity"
    elif stype in ("establishing", "closing", "wide"):
        return "kling", f"Establishing/closing ({stype}) — no elements, Kling motion"
    elif stype in ("b-roll", "insert"):
        return "kling", f"B-roll/insert ({stype}) — no elements"
    else:
        return "kling", f"Default Kling ({stype})"

# ═══════════════════════════════════════════════════════════════
# AUTO-CONSOLIDATE — Beats → CHOREOGRAPHED shots with establishing + closing
# ═══════════════════════════════════════════════════════════════
def auto_consolidate(sb_scene, contract, shots, scene_id, cast=None):
    beats = contract.get("beats", []) if contract else []
    if not beats:
        raw = sb_scene.get("beats", [])
        beats = [{"description": b, "character_action": b} if isinstance(b, str) else b for b in raw]

    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
    all_chars = sorted(set(c for s in scene_shots for c in (s.get("characters") or [])))
    is_solo = len(all_chars) <= 1
    location_text = sb_scene.get("location", "")

    scene_dialogue = {}
    # Also build speaker attribution map: beat_index → speaker name
    # This preserves THOMAS vs ELEANOR for the Kling compiler (T2-FE-13)
    scene_dialogue_speaker = {}
    # V29.3 FIX: Content-match map for scenes where _beat_index is None
    # Many shots have _beat_index: None → all map to beat 0, losing attribution for beats 1,2,3...
    # Solution: normalize dialogue text and map directly to speaker
    _dlg_to_speaker = {}   # normalized_text[:50] → speaker_name
    _dlg_to_full = {}      # normalized_text[:50] → full dialogue string (with prefix)

    _KNOWN_PREFIXES_UPPER = (_ACTIVE_CHAR_PREFIXES or ["NADIA COLE:", "THOMAS BLACKWOOD:", "ELEANOR VOSS:", "RAYMOND CROSS:", "HARRIET HARGROVE:"])

    def _normalize_dlg(text):
        """Strip speaker prefix and whitespace, lowercase, first 50 chars for matching."""
        t = (text or "").strip()
        for pfx in _KNOWN_PREFIXES_UPPER:
            t = t.replace(pfx, "")
        return t.replace("|", " ").strip().lower()[:50]

    for s in scene_shots:
        dlg = s.get("dialogue_text") or ""
        if dlg:
            bi = s.get("_beat_index", 0)
            if bi is None: bi = 0
            if bi not in scene_dialogue or len(dlg) > len(scene_dialogue.get(bi, "")):
                scene_dialogue[bi] = dlg
                # Detect speaker: explicit field, or single-character shot attribution
                spk = (s.get("_ots_speaker") or s.get("speaker") or s.get("dialogue_speaker") or "")
                if not spk:
                    chars_s = s.get("characters") or []
                    if len(chars_s) == 1:
                        spk = chars_s[0]
                # Also try extracting from dialogue prefix
                if not spk:
                    for kc in (_ACTIVE_CHAR_NAMES or ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS", "RAYMOND CROSS", "HARRIET HARGROVE"]):
                        if dlg.upper().startswith(kc + ":"):
                            spk = kc.title(); break
                if spk:
                    scene_dialogue_speaker[bi] = spk
            # Build content-match map from ALL shots regardless of beat_index
            spk2 = (s.get("_ots_speaker") or s.get("speaker") or s.get("dialogue_speaker") or "")
            if not spk2:
                chars_s = s.get("characters") or []
                if len(chars_s) == 1:
                    spk2 = chars_s[0]
            if not spk2:
                for kc in (_ACTIVE_CHAR_NAMES or ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS", "RAYMOND CROSS", "HARRIET HARGROVE"]):
                    if dlg.upper().startswith(kc + ":"):
                        spk2 = kc.title(); break
            # Process each pipe-segment separately for multi-line dialogue
            for seg in dlg.split("|"):
                seg = seg.strip()
                if not seg: continue
                seg_spk = spk2
                for kc in (_ACTIVE_CHAR_NAMES or ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS", "RAYMOND CROSS", "HARRIET HARGROVE"]):
                    if seg.upper().startswith(kc + ":"):
                        seg_spk = kc.title(); break
                norm = _normalize_dlg(seg)
                if norm and seg_spk:
                    if norm not in _dlg_to_speaker:
                        _dlg_to_speaker[norm] = seg_spk
                        _dlg_to_full[norm] = seg
                    # Also store all 5-char n-grams for fuzzy lookup
                    for n in range(0, len(norm)-10, 5):
                        ngram = norm[n:n+20]
                        if ngram not in _dlg_to_speaker:
                            _dlg_to_speaker[ngram] = seg_spk

    # ── SPEAKER EXTRACTION from dialogue prefix (most reliable source) ──
    # Works for ALL scenes: if dialogue = "THOMAS BLACKWOOD: text" → speaker = THOMAS BLACKWOOD
    # This is more reliable than _ots_speaker (only set on OTS shots) or single-char detection
    _KNOWN_CHARS = (_ACTIVE_CHAR_NAMES or ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS", "RAYMOND CROSS", "HARRIET HARGROVE"])

    def _extract_speaker_from_dlg_text(dlg_text, chars_in_scene, _cast=None):
        """Parse 'CHAR_NAME: text' prefix to find the first speaker. Returns char name or ''."""
        if not dlg_text: return ""
        dlg_upper = dlg_text.strip().upper()
        # Try known chars first (exact match before ':')
        for kc in _KNOWN_CHARS:
            if dlg_upper.startswith(kc + ":"):
                for c in chars_in_scene:
                    if c.upper() == kc:
                        return c
                return kc.title()
        # Also try any character name from cast that appears as prefix
        if _cast:
            for cname in _cast:
                if dlg_upper.startswith(cname.upper() + ":"):
                    return cname
        return ""

    # Inject dialogue from story bible beats into beats list
    # V29.2 FIX: ALWAYS override beat dialogue with raw shot_plan version
    # V29.3 FIX: Content-match fallback — when _beat_index is None on raw shots, use normalized text matching
    for i, beat in enumerate(beats):
        if isinstance(beat, dict):
            raw_dlg = scene_dialogue.get(i, "")
            raw_spk = _extract_speaker_from_dlg_text(raw_dlg, all_chars, cast) or scene_dialogue_speaker.get(i, "")

            if raw_dlg:
                # We have a beat-index match — use it
                if raw_spk and not raw_dlg.upper().startswith(raw_spk.upper().split()[0]):
                    beat["dialogue"] = f"{raw_spk}: {raw_dlg}"
                else:
                    beat["dialogue"] = raw_dlg
                beat["_dialogue_speaker"] = raw_spk
            else:
                # V29.3: No beat-index match — try content-match on existing beat dialogue
                # Many shots have _beat_index=None so their dialogue mapped to beat 0 only
                existing_dlg = beat.get("dialogue", "")
                if existing_dlg:
                    norm = _normalize_dlg(existing_dlg)
                    matched_spk = _dlg_to_speaker.get(norm, "")
                    if not matched_spk:
                        # Substring match: check if any known key is a substring of our beat text (or vice versa)
                        # Handles: story bible beats that paraphrase or shorten dialogue
                        norm_words = norm.replace("'","").replace('"','')
                        for k, v in _dlg_to_speaker.items():
                            k_words = k.replace("'","").replace('"','')
                            # At least 15 chars in common, either direction
                            if (len(k_words) >= 15 and k_words in norm_words) or \
                               (len(norm_words) >= 15 and norm_words[:25] in k_words):
                                matched_spk = v; break
                    if matched_spk:
                        beat["_dialogue_speaker"] = matched_spk
                        # Also ensure dialogue has speaker prefix for the Kling compiler
                        if not any(existing_dlg.upper().startswith(kc + ":") for kc in
                                   (_ACTIVE_CHAR_NAMES or ["NADIA COLE", "THOMAS BLACKWOOD", "ELEANOR VOSS", "RAYMOND CROSS", "HARRIET HARGROVE"])):
                            beat["dialogue"] = f"{matched_spk}: {existing_dlg}"

    # ── CHOREOGRAPHER: build establishing + action shots + closing ──
    # choreograph_scene adds establishing + closing beats automatically
    choreo_shots = choreograph_scene(beats, all_chars, location_text, is_solo)

    consolidated = []
    shot_counter = 1
    for choreo in choreo_shots:
        shot_type = choreo.get("type", "medium")
        is_establishing = choreo.get("is_establishing", False)
        is_closing = choreo.get("is_closing", False)

        # V29.3 FIX: Skip empty establishing shots — they trigger LTX which isn't the proven format.
        # The first beat shot already carries the entry/establishing context in its action description.
        # User confirmed: Kling ONLY. No separate LTX establishing shot.
        if is_establishing:
            continue

        frame_desc = choreo.get("frame_desc", "")
        choreography = choreo.get("choreography", "")
        dialogue = choreo.get("dialogue", "")
        mood = choreo.get("mood", "")
        dur = choreo.get("duration", "10")
        action = choreo.get("action", "")

        # Characters: closing = all chars, beat = all_chars
        if is_closing:
            shot_chars = all_chars[:2] if not is_solo else all_chars[:1]
            final_shot_type = "closing"
        else:
            shot_chars = all_chars[:2] if not is_solo else all_chars[:1]
            final_shot_type = shot_type

        # Smart duration override for dialogue shots
        if dialogue and not is_establishing and not is_closing:
            words = len(dialogue.split())
            dur = str(min(15, max(10, int(words / 2.3 + 1.5))))

        shot = {
            "shot_id": f"{scene_id}_M{shot_counter:02d}",
            "shot_type": final_shot_type,
            "duration": dur,
            "characters": shot_chars,
            "dialogue_text": dialogue,
            "_dialogue_speaker": choreo.get("_dialogue_speaker", ""),
            "description": action or frame_desc,
            "_frame_description": frame_desc,   # ENTRY STATE — where Kling starts
            "_choreography": choreography,       # TIMED ACTION — what Kling does
            "_beat_action": action,
            "_beat_atmosphere": mood,
            "_beat_enriched": True,
            "_is_establishing": is_establishing,
            "_is_closing": is_closing,
            "_eye_line_target": extract_eye_line(action, dialogue, mood),
            "_body_direction": extract_body_direction(action, mood),
            "location": location_text,
        }
        consolidated.append(shot)
        shot_counter += 1

    return consolidated

# ═══════════════════════════════════════════════════════════════
# PROMPT COMPILERS
# ═══════════════════════════════════════════════════════════════
def compile_nano(shot, sb_scene, cast, contract, mode):
    """First frame prompt — blocking/spatial FIRST so FAL reads composition intent
    before character identity blocks. T2-FE-17: screen direction in every dialogue shot.
    V29.1 FIX: front-load blocking before [CHARACTER:] blocks."""
    import re as _re
    # nano_prompt feeds the description channel but does NOT bypass 4-channel treatment.
    # Strip any baked-in directive blocks so they don't duplicate the channels built below.
    _existing_np = (shot.get("nano_prompt") or "").strip()
    if _existing_np:
        _stripped = _re.sub(r'\[CAMERA:[^\]]*\]', '', _existing_np)
        _stripped = _re.sub(r'\[PALETTE:[^\]]*\]', '', _stripped)
        _stripped = _re.sub(r'\[PHYSICS:[^\]]*\]', '', _stripped)
        _stripped = _re.sub(r'\[AESTHETIC:[^\]]*\]', '', _stripped)
        _stripped = _re.sub(r'\[ROOM DNA:[^\]]*\]', '', _stripped)
        _stripped = _re.sub(r'\[LIGHTING RIG:[^\]]*\]', '', _stripped)
        desc = _stripped.strip()
        print(f"[PROMPT] {shot.get('shot_id','?')}: nano_prompt → desc ({len(desc)} chars) + full 4-channel treatment")
    else:
        # AUTO-BUILD fallback: weave character INTO scene when nano_prompt is absent.
        # Raw description alone produces flat/pasted results because FAL sees character
        # and room as separate signals. This fallback builds the same character-in-room
        # prose that a hand-authored nano_prompt would provide.
        _raw_desc = (shot.get("_frame_description") or shot.get("description") or "").strip()
        _auto_chars = shot.get("characters") or []
        _auto_beat = (shot.get("_beat_action") or shot.get("_body_direction") or "").strip()[:120]
        _auto_loc = strip_location_names(
            (sb_scene.get("location") or "") if isinstance(sb_scene, dict) else ""
        ) or "the space"
        _auto_parts = []
        if _auto_chars and isinstance(cast, dict):
            _auto_cn = _auto_chars[0]
            _auto_cdata = cast.get(_auto_cn) or {}
            if isinstance(_auto_cdata, dict):
                _auto_app = (_auto_cdata.get("amplified_appearance")
                             or _auto_cdata.get("appearance") or "")[:180]
                _auto_verb = strip_location_names(_auto_beat) if _auto_beat else "stands in the space"
                if _auto_app:
                    _auto_parts.append(
                        f"{_auto_cn} {_auto_verb}. {_auto_app}. Set in {_auto_loc}."
                    )
        if _raw_desc:
            _auto_parts.append(strip_location_names(_raw_desc))
        desc = " ".join(_auto_parts).strip() or _raw_desc
        _sid_log = shot.get("shot_id", "?")
        print(f"[PROMPT] {_sid_log}: auto-generated nano_prompt from shot fields (no preset nano_prompt) — {len(desc)} chars")
    shot_type = (shot.get("shot_type") or "medium").lower()
    # E-shot guard: if shot is flagged as B-roll / no-char, force chars=[] regardless of what
    # might have leaked into the shot dict. This is the last line of defence in compile_nano.
    _is_e_shot = (
        shot.get("_no_char_ref") or
        shot.get("_is_broll") or
        shot.get("_nano_mode") == "text2img" and not (shot.get("characters") or [])
    )
    chars = [] if _is_e_shot else (shot.get("characters") or [])
    dialogue = (shot.get("dialogue_text") or shot.get("_beat_dialogue") or "").strip()

    clean_desc = strip_location_names(desc)

    # ── STEP 0.5: V36.5.1 BLOCKING CARRY — inject spatial arrangement from previous shot
    # so the first frame knows WHERE characters are, not just WHO they are.
    # Without this, each first frame invents new character positions from scratch,
    # causing spatial jumps between shots (e.g. character appears to leave then teleport back).
    _blocking_carry = (shot.get("_blocking_carry") or "").strip()
    _blocking_prefix = ""
    if _blocking_carry and chars:
        _blocking_prefix = f"[SPATIAL CARRY: {_blocking_carry[:100]}] "

    # ── STEP 1: Blocking/spatial FIRST — FAL reads the first ~200 chars hardest ──
    # V29.6 FIX: Use the choreographer's _frame_description as the spatial header.
    # The choreographer already wrote the CORRECT composition per shot type:
    #   OTS-A: "OVER-THE-SHOULDER SHOT. CharB back fills left foreground, OUT OF FOCUS..."
    #   OTS-B: "OVER-THE-SHOULDER SHOT. CharA back fills right foreground, OUT OF FOCUS..."
    #   TWO-SHOT: "TIGHT TWO-SHOT. CharA frame-left facing right, CharB frame-right..."
    #   MEDIUM: "MEDIUM TWO-SHOT. CharA frame-left, CharB frame-right..."
    # V29.5 bug: this was overridden with "CINEMATIC TWO-SHOT. confrontational..." for ALL
    # shot types, making every multi-char shot a bilateral face-off regardless of arc position.
    # The fix: use _frame_description as the spatial header. build_social_blocking is only a
    # fallback when _frame_description is absent (e.g. manually authored shots).
    spatial_header = ""
    if len(chars) >= 2:
        frame_desc_from_choreo = shot.get("_frame_description", "").strip()
        if frame_desc_from_choreo:
            # Choreographer built the correct OTS/two-shot/medium composition — use it directly
            spatial_header = strip_location_names(frame_desc_from_choreo)
        else:
            # Fallback for manually authored shots without _frame_description
            blocking = build_social_blocking(chars, cast, shot_type, dialogue)
            if blocking:
                raw = blocking.replace("[BLOCKING: ", "").rstrip("]")
                # Use shot_type-aware label, not hardcoded "CINEMATIC TWO-SHOT"
                if shot_type in ("ots_a", "ots_b", "ots", "over_the_shoulder"):
                    spatial_header = f"OVER-THE-SHOULDER SHOT. {raw}."
                elif shot_type in ("two_shot", "tight_two_shot"):
                    spatial_header = f"TIGHT TWO-SHOT. {raw}."
                else:
                    spatial_header = f"MEDIUM TWO-SHOT. {raw}."
    elif len(chars) == 1:
        # Solo shot — V30.1 P1.4: use _body_direction + _eye_line_target for specific micro-movement
        # Old: "MEDIUM SOLO SHOT. Character occupies frame." — gave FAL nothing to animate from
        # New: derives from truth fields already populated by beat enrichment (T2-TL-7)
        eye = shot.get("_eye_line_target", "")
        body = shot.get("_body_direction", "").strip()
        _shot_label_map = {
            "close_up": "CLOSE-UP SHOT", "mcu": "MEDIUM CLOSE SHOT",
            "medium_close": "MEDIUM CLOSE SHOT", "medium": "MEDIUM SOLO SHOT",
            "wide": "WIDE SOLO SHOT", "reaction": "REACTION CLOSE-UP",
        }
        shot_label = _shot_label_map.get(shot_type, "MEDIUM SOLO SHOT")
        if body and body not in ("present, natural micro-movements", "neutral, present in scene", ""):
            # Specific choreography from truth layer — best case
            spatial_header = f"{shot_label}. {body}." + (f" Looking {eye}." if eye else "")
        else:
            # Fallback: at least add eye-line
            spatial_header = f"{shot_label}. Character fills frame." + (f" Looking {eye}." if eye else "")

    # ── STEP 2: Identity prompt (character blocks — blocking ALREADY injected above) ──
    # Pass empty dialogue to inject_identity so it doesn't re-add blocking at end
    identity_prompt = inject_identity_into_prompt(clean_desc, chars, cast, shot_type, "")
    # Remove any [BLOCKING:] block that inject_identity may have added (we have it at top)
    import re as _re
    identity_clean = _re.sub(r'\[BLOCKING:[^\]]*\]', '', identity_prompt).strip()

    # ── STEP 3: Room DNA + focal enforcement ──
    # V37: If sb_scene is None (story bible missing for this scene), fall back to the
    # shot's own _room_dna field which may have been pre-populated by the context dict
    # in run_scene. Without this fallback, missing story bible → empty dna → room drift.
    dna = build_scene_dna(sb_scene)
    if not dna:
        _fallback_dna = (shot.get("_room_dna") or "").strip()
        if _fallback_dna:
            dna = _fallback_dna
    focal = get_focal_length_enforcement(shot_type)
    focal_block = f"[{focal}]" if focal else ""

    solo = ""
    # TRUTH: derive solo from the SHOT's actual character count — NOT the contract field
    # (scene contracts have shown is_solo_scene=True incorrectly for multi-char scenes)
    if len(chars) == 0:
        solo = "No people visible, empty space only."
    elif len(chars) == 1 and contract.get("is_solo_scene"):
        # Only flag as solo if BOTH the shot AND contract agree
        solo = "Character alone. No other people visible."
    # For len(chars) >= 2: never inject solo constraint — two characters share the frame

    # ── STEP 4: 4 MISSING CHANNELS — camera, palette, physics, aesthetic ──────
    # Sourced from story bible. These directly upgrade frame quality toward the
    # structured JSON prompt standard (camera/lens spec, hex palette, physics layer,
    # aesthetic movement label). Each is a separate conditioning signal to nano.

    # CHANNEL 1: CAMERA/LENS SPEC — lens character shapes the entire image feel
    # Pull from story bible cinematography or default to Victorian Gothic standard
    sb_cinema = (sb_scene.get("cinematography") or {}) if isinstance(sb_scene, dict) else {}
    if not sb_cinema:
        sb_cinema = {}  # story bible top-level cinematography injected via sb_scene passthrough
    # Get project-level cinematography if scene-level is empty
    _cine_style = sb_cinema.get("style", "") or ""
    # Derive lens spec from shot type — describes VISUAL EFFECT not just mm number
    _lens_map = {
        "close_up": "85mm prime, f/1.4 — camera holds intimately on face, background melts to pure bokeh, every skin texture visible",
        "mcu": "85mm prime, f/1.4 — camera holds intimately on face, background melts to pure bokeh, every skin texture visible",
        "reaction": "85mm prime, f/1.6 — camera close on reacting face, background dissolved, micro-expression reads clearly",
        "medium_close": "50mm prime, f/2.0 — camera at conversation distance, shoulders up, background softly present",
        "medium": "35mm lens, f/2.8 — camera at natural standing distance, room context visible, character grounded in space",
        "establishing": "24mm wide, f/8 — camera pulls back to reveal full geography, deep focus, architecture dominates",
        "wide": "24mm wide, f/8 — camera distant, full room visible, character diminished by environment",
        "closing": "24mm wide, f/8 — camera withdrawing slowly, character receding into the space",
        "ots_a": "50mm f/2.0 — over listener's shoulder, foreground shoulder SOFT and OUT OF FOCUS, speaker's face SHARP, background architecture SOFT BOKEH. Only the speaker's face is in focus",
        "ots_b": "50mm f/2.0 — REVERSED angle, over speaker's shoulder (foreground SOFT OUT OF FOCUS), listener's face SHARP in background, architecture SOFT BOKEH. Only the listener's face is in focus",
        "two_shot": "35mm f/2.8 — both characters in frame, confrontational axis, equal visual weight, background architecture SOFT at f/2.8, characters sharp",
        "insert": "100mm macro — camera extremely close on object detail, everything else dissolved",
    }
    _camera_block = _lens_map.get(shot_type, "35mm-equivalent prime, natural depth of field")
    camera_block = f"[CAMERA: {_camera_block}. Period cinema — slight vintage optical character, natural film grain, no digital sharpness.]"

    # CHANNEL 2: COLOR PALETTE — pull from story bible, scene atmosphere, time of day
    # Story bible has: primary (muted golds), secondary (cool slate), danger (burgundy), discovery (golden)
    _time = (sb_scene.get("time_of_day") or "").upper() if isinstance(sb_scene, dict) else ""
    _atm = (sb_scene.get("atmosphere") or "") if isinstance(sb_scene, dict) else ""
    _loc = (sb_scene.get("location") or "") if isinstance(sb_scene, dict) else ""
    # Map time-of-day + location to palette
    if "MORNING" in _time:
        _palette = "desaturated cool greys warming toward gold, dust-filtered light, muted earth tones"
    elif "EVENING" in _time or "TWILIGHT" in _time:
        _palette = "deep amber and shadow, warm candlelight golds, dark vignette edges, burgundy undertones"
    elif "NIGHT" in _time:
        _palette = "deep indigo blacks, warm lamplight pools, high contrast, cool shadow fill"
    elif "AFTERNOON" in _time:
        _palette = "warm amber midtones, golden hour quality, muted saturation, soft earth tones"
    else:
        _palette = "muted warm neutrals, desaturated earth tones, period-accurate Victorian palette"
    palette_block = f"[PALETTE: {_palette}. No modern color grading — muted, desaturated, period-correct.]"

    # CHANNEL 3: PHYSICS LAYER — tactile atmosphere details that make the frame breathe
    # Key physics for Victorian Gothic: dust, candlelight, cold stone, texture
    _phys_map = {
        "library":     "visible dust motes in lamplight beams, warm ambient glow on leather spines, aged paper texture",
        "foyer":       "dust in shaft of morning light, cold stone floor texture, shadow pools at edges",
        "exterior":    "natural light variation, breath potentially visible, grass or stone texture, sky detail",
        "study":       "candleflicker on walls, aged wood grain, paper texture, ink on desk surface",
        "bedroom":     "soft diffused light, fabric texture on bedding, gentle window light fall",
        "staircase":   "dust motes in light shafts, wood creak implication, deep shadow on upper landing",
        "kitchen":     "steam or warmth haze, stone worktop texture, firelight flicker",
    }
    _loc_key = next((k for k in _phys_map if k in _loc.lower()), None)
    _physics_detail = _phys_map.get(_loc_key, "visible atmospheric depth, tactile surface textures, natural light imperfections")
    physics_block = f"[PHYSICS: {_physics_detail}. Practical lighting only — no studio flatness.]"

    # CHANNEL 4: AESTHETIC MOVEMENT LABEL — the cinematic language reference
    # R63: Derives from story bible genre/style if present → project-agnostic.
    # Fallback: Victorian Gothic (current project). New projects get their own aesthetic label.
    _genre_from_bible = ""
    if isinstance(sb_scene, dict):
        _genre_from_bible = (sb_scene.get("genre") or sb_scene.get("cinematic_style")
                             or sb_scene.get("style") or sb_scene.get("aesthetic") or "")
    if _genre_from_bible:
        _genre_label = f"{_genre_from_bible} — practical lighting, period-accurate palette, tactile realism, no digital flatness"
    else:
        # Victorian Gothic default (current project)
        _genre_label = "Victorian Gothic period realism — Robert Eggers tactile approach, practical lighting, desaturated natural palette, no modern color science"
    aesthetic_block = (
        f"[AESTHETIC: {_genre_label}."
        " NO CGI, NO 3D render, NO airbrushed skin, NO plastic skin, NO doll face,"
        " NO digital art, NO beauty filter, NO smooth skin."
        " Realistic skin texture with pores and imperfections.]"
    )
    # V36 Genre DNA override — shot-level fields written by apply_genre_dna()
    # Bible authority gate: only inject genre lighting/palette if bible didn't
    # specify atmosphere for this shot. Bible atmosphere = bible owns the aesthetic.
    _g_lighting = shot.get("_genre_lighting_rig", "")
    _g_palette = shot.get("_genre_color_palette", "")
    _has_bible_aesthetic = bool(shot.get("_beat_atmosphere"))
    if (_g_lighting or _g_palette) and not _has_bible_aesthetic:
        _genre_override = ""
        if _g_lighting:
            _genre_override += f" Lighting: {_g_lighting}."
        if _g_palette:
            _genre_override += f" Color palette: {_g_palette}."
        aesthetic_block = aesthetic_block.replace("[AESTHETIC: ", f"[AESTHETIC:{_genre_override} ", 1)

    # ── STEP 4b: Weave character into room — anti "pasted-on" fix (V30.2) ──
    # The "pasted-on" look comes from treating [CHARACTER:] and [ROOM DNA:] as separate
    # conditioning blocks — FAL sees them as independent layers and composites the face
    # onto the background. Fix: describe character AS PART OF the room in a single sentence.
    # "THOMAS stands in the grand foyer. Silver-white hair, navy suit. Steps forward."
    # This forces the model to render them as one integrated scene, not two stacked images.
    # The [CAMERA:], [PALETTE:], [PHYSICS:], [AESTHETIC:] directive blocks are unchanged.
    _room_dna_prose = dna.replace("[ROOM DNA: ", "").rstrip("]") if dna else ""
    _room_location = strip_location_names(_loc) or "the room"
    _beat_phrase = strip_location_names(
        (shot.get("_beat_action") or shot.get("_body_direction") or "")[:120]
    ).strip()
    _weave_sentences = []
    if chars:
        for _ci, _cn in enumerate(chars[:2]):
            _cdata = cast.get(_cn) if isinstance(cast.get(_cn), dict) else {}
            _raw_app = _cdata.get("amplified_appearance") or _cdata.get("appearance") or ""
            # Strip any [CHARACTER:] block markers that injection may have already added
            _app_prose = _re.sub(r'\[CHARACTER:[^\]]*\]', '', _raw_app).strip()[:200]
            if _app_prose:
                # V30.3: Use beat action as the character verb, not generic "stands in"
                # "NADIA COLE moves through the library" not "NADIA COLE stands in the library"
                if _ci == 0 and _beat_phrase:
                    _bp = _beat_phrase
                    _fn = _cn.split()[0] if _cn else ""
                    if _fn and _bp.lower().startswith(_fn.lower()):
                        _bp = _bp[len(_fn):].lstrip(", ")
                    _sent = f"{_cn} {_bp}. {_app_prose}. Set in {_room_location}."
                else:
                    _sent = f"{_cn} in {_room_location}. {_app_prose}."
                _weave_sentences.append(_sent)
    weaved_intro = " ".join(_weave_sentences)
    # When weaved_intro is built, it replaces separate identity_clean + dna blocks.
    # Room DNA architecture is still included (separately) to lock room geometry.
    _use_weaved = bool(weaved_intro)

    # V36.5.1: Prepend blocking carry to spatial header so FAL sees spatial arrangement FIRST
    if _blocking_prefix:
        spatial_header = _blocking_prefix + spatial_header

    # ── STEP 5: Assemble — spatial header FIRST, then weaved/identity, then directives ──
    # V30.4: Realism anchor — highest attention weight position.
    # Nano-banana-pro is a "thinking" model. Natural language at the top sets the entire generation intent.
    _story_atm = ""
    if isinstance(sb_scene, dict):
        _story_atm = (sb_scene.get("atmosphere") or "")[:100]
    # V36.3: Eye realism directive for character shots — prevents uncanny AI gaze
    _eye_realism = " Natural asymmetric gaze with catch light reflections in eyes, slight iris variation, no dead stare." if chars else ""
    realism_anchor = f"A photorealistic film frame shot on 35mm Kodak 5219 stock. Realistic skin texture with visible pores, natural imperfections, subsurface scattering.{_eye_realism} {_story_atm}."

    if mode == "full":
        rig = build_scene_lighting_rig(sb_scene)
        truth = translate_truth_to_prompt(identity_clean, shot)
        if _use_weaved:
            # Weaved: character-in-room prose + performance truth + directives (no separate DNA block)
            parts = [p for p in [realism_anchor, spatial_header, weaved_intro, truth, solo, focal_block,
                                  camera_block, palette_block, physics_block, aesthetic_block] if p]
        else:
            parts = [p for p in [realism_anchor, spatial_header, truth, solo, dna, rig, focal_block,
                                  camera_block, palette_block, physics_block, aesthetic_block] if p]
    else:
        if _use_weaved:
            # Weaved: character-in-room prose + directives (no separate CHARACTER/DNA blocks)
            parts = [p for p in [realism_anchor, spatial_header, weaved_intro, solo, focal_block,
                                  camera_block, palette_block, physics_block, aesthetic_block] if p]
        else:
            parts = [p for p in [realism_anchor, spatial_header, identity_clean, solo, dna, focal_block,
                                  camera_block, palette_block, physics_block, aesthetic_block] if p]

    # V30.5: Inject continuity delta and spatial zone from pre-computed mshots fields
    _cont_delta = shot.get("_continuity_delta", "")
    _zone = shot.get("_spatial_zone", "")
    if _cont_delta:
        parts.append(f"[CONTINUITY: {_cont_delta}]")
    if _zone:
        parts.append(f"[ZONE: {_zone} area of the room]")

    # V36.1 SCENE TRANSITION MANAGER — opener prefix + cross-scene entry context
    # _opener_prefix: pre-designated scene opening strategy (COLD_OPEN / ACTION / DIALOGUE etc.)
    # _scene_entry_context: emotional/spatial state carried in from previous scene's exit
    # Both injected by scene_transition_manager.inject_scene_entry() before frame generation.
    _opener_prefix = (shot.get("_opener_prefix") or "").strip()
    _entry_context = (shot.get("_scene_entry_context") or "").strip()
    if _opener_prefix:
        # Prepend to realism_anchor so it's in the highest-attention position
        parts[0] = f"{_opener_prefix} {parts[0]}" if parts else _opener_prefix
        print(f"  [OPENER→FRAME] {shot.get('shot_id','?')}: {_opener_prefix[:60]}")
    if _entry_context:
        parts.append(f"[ENTRY: {_entry_context}]")
        print(f"  [ENTRY→FRAME]  {shot.get('shot_id','?')}: {_entry_context[:60]}")

    return " ".join(parts)[:2000]


def _build_temporal_arc(action: str, duration: float) -> str:
    """R63: Convert flat action description into Seedance 2.0 timestamp segments.
    Seedance 2.0 natively supports [0-Xs]/[X-Ys] pacing control in prompts.
    Temporal segmentation prevents the model from front-loading all motion
    into the first second — it distributes action across the full duration.
    Only applied when duration >= 5s and action has multiple logical beats."""
    duration = max(5, int(duration))
    parts = [p.strip() for p in action.split(". ") if p.strip()]
    if len(parts) >= 3 and duration >= 10:
        mid = duration // 2
        third = (2 * duration) // 3
        return f"[0-{mid}s] {parts[0]}. [{mid}-{third}s] {'. '.join(parts[1:-1])}. [{third}-{duration}s] {parts[-1]}."
    elif len(parts) >= 2 and duration >= 5:
        mid = duration // 2
        return f"[0-{mid}s] {parts[0]}. [{mid}-{duration}s] {'. '.join(parts[1:])}."
    return action  # Single-beat action — no segmentation needed


def compile_video_prompt(shot, cast, contract, mode, context=None):
    """Video prompt — TIMED CHOREOGRAPHY injected first, then Kling Compiler, then fallback.
    The choreography is the KEY difference: it tells Kling WHAT HAPPENS across the duration
    instead of describing a static pose.
    R63: Fallback path now motion-first (atmosphere dropped — already in start frame).
    R63: Temporal arc [0-Xs] segmentation added for Seedance 2.0 pacing control.
    V36.2: Opener intelligence — story bible opener type drives motion energy and entry feel."""
    chars = shot.get("characters") or []
    choreography = shot.get("_choreography", "")  # timed action sequence from choreographer
    is_establishing = shot.get("_is_establishing", False)
    is_closing = shot.get("_is_closing", False)

    # ── V36.2 OPENER INTELLIGENCE → VIDEO PROMPT ──────────────────────────────
    # Story bible opener type determines the MOTION ENERGY of M01's video.
    # This closes the consciousness gap: story bible → opener → frame → VIDEO → chain.
    _opener_type = shot.get("_scene_opener_type") or shot.get("_opener_type") or ""
    _opener_prefix = (shot.get("_opener_prefix") or "").strip()
    _opener_energy = (shot.get("_opener_energy") or "").strip()
    _entry_context = (shot.get("_scene_entry_context") or "").strip()

    # Map opener type → video motion directive (what Kling SEES at frame 0)
    _OPENER_VIDEO_DIRECTIVES = {
        "DIALOGUE_OPENER":    "Scene starts MID-CONVERSATION. Immediate speech motion — lips moving, "
                              "gestures active, no slow build. Characters already engaged in dialogue.",
        "COLD_OPEN":          "Scene starts IN PROGRESS. No establishing pause — action already underway "
                              "from frame 1. Energy carries from a moment already begun.",
        "ACTION_OPENER":      "Scene starts with KINETIC MOTION. Character already moving — body committed "
                              "to physical action from first frame. No stillness.",
        "REVELATION_OPENER":  "Scene starts with TENSION. Slow, deliberate movement — character approaching "
                              "discovery. Eyes scanning, hands reaching. Building toward the reveal.",
        "ATMOSPHERE_OPENER":  "Scene starts with STILLNESS. Slow ambient drift — natural breathing, "
                              "subtle weight shifts. Character absorbing the space before acting.",
        "BROLL_OPENER":       "Scene starts with ENVIRONMENT. Slow camera movement through empty space. "
                              "Dust, light, atmosphere. No character motion yet.",
    }
    _video_opener_directive = _OPENER_VIDEO_DIRECTIVES.get(_opener_type, "")
    if _video_opener_directive:
        print(f"    [V36.2 OPENER→VIDEO] {shot.get('shot_id','?')}: {_opener_type} → {_video_opener_directive[:60]}...")

    # B-roll / establishing / closing — no identity needed, just environment action
    if is_establishing:
        action = shot.get("_beat_action") or shot.get("description") or ""
        choreo = choreography or "Slow camera drift through the empty space. Dust motes. Natural light."
        return f"{strip_location_names(choreo)} No people. Empty environment."

    if is_closing:
        choreo = choreography or "Wide pull-back. Characters distant. Scene settles. Atmosphere closes."
        return f"{strip_location_names(choreo)}"

    if chars:
        # INJECT CHOREOGRAPHY + USE KLING PROMPT COMPILER
        # Choreography gives Kling the timed action sequence — the critical missing piece
        try:
            # Add choreography to shot context so compiler can embed it
            enriched_shot = dict(shot)
            if choreography:
                # Prepend choreography to description so compiler picks it up
                enriched_shot["description"] = choreography + " " + (shot.get("description") or "")
                enriched_shot["_beat_action"] = choreography
            # V36.2: Inject opener directive into enriched shot so compiler can see it
            if _video_opener_directive:
                enriched_shot["_video_opener_directive"] = _video_opener_directive
            prompt = compile_video_for_kling(enriched_shot, cast, context or {})
            if prompt and len(prompt) > 20:
                # Also inject raw choreography at front if not already present
                if choreography and choreography[:30] not in prompt:
                    prompt = choreography[:400] + " " + prompt
                # V36.2: Prepend opener directive at highest-attention position
                if _video_opener_directive and _video_opener_directive[:30] not in prompt:
                    prompt = _video_opener_directive + " " + prompt
                return prompt[:2500]
        except Exception as e:
            print(f"    [KLING COMPILER] fallback: {e}")
        # Direct fallback: MOTION-FIRST — atmosphere dropped (already in start frame).
        # R63: Seedance 2.0 doc: "focus on what should MOVE, not static elements in the image."
        if choreography:
            action = choreography
        else:
            action = shot.get("_beat_action") or shot.get("description") or ""
        dlg = shot.get("dialogue_text") or ""
        dur = shot.get("duration", 10)
        # Apply temporal arc segmentation for Seedance pacing control
        timed_action = _build_temporal_arc(strip_location_names(action), dur)
        parts = []
        # V36.2: Opener directive first — tells Kling the entry energy
        if _video_opener_directive:
            parts.append(_video_opener_directive)
        parts.append(timed_action)
        if dlg: parts.append(f'Speaking: "{dlg[:100]}"')
        # Character locking note at end — reinforces role_suffix (belt-and-suspenders)
        if chars: parts.append("Same face, same clothing, no identity drift.")
        return " ".join(parts)[:900]

    # No chars — B-roll with choreography
    action = choreography or shot.get("_beat_action") or shot.get("description") or ""
    mood = shot.get("_beat_atmosphere") or ""
    parts = [strip_location_names(action) + "."]
    if mood: parts.append(mood + ".")  # Atmosphere OK for B-roll — there's no start-frame identity to protect
    parts.append("No people. Empty environment.")
    return " ".join(parts)[:900]


# ═══════════════════════════════════════════════════════════════
# GENERATION
# ═══════════════════════════════════════════════════════════════
def gen_frame(shot, cast, locs, sb_scene, contract, mode, outdir, location_text, dry_run=False):
    """Generate first frame with CORRECT model selection + multi-candidate."""
    sid = shot["shot_id"]
    chars = shot.get("characters") or []
    prompt = compile_nano(shot, sb_scene, cast, contract, mode)

    # V31.1: Pre-video gate diagnostic injection.
    # If a previous attempt failed the holistic gate, _pvg_diagnostic contains a
    # CORRECTION directive built from the failed dimensions (location/blocking/mood/identity).
    # Prepend it to the compiled prompt so FAL reads the correction in its highest-attention
    # zone (~first 200 chars). This is the "bridge" between the gate's diagnosis and the
    # next generation attempt.
    _pvg_diag = (shot.get("_pvg_diagnostic") or "").strip()
    if _pvg_diag:
        prompt = f"[CORRECTION — PREVIOUS FRAME REJECTED]: {_pvg_diag} [/CORRECTION] {prompt}"
        print(f"  [PVG-INJECT] {sid}: correction prepended ({len(_pvg_diag)} chars)")

    # Guard: prompt must never be empty after compile_nano (prep_engine + compile_nano
    # fallbacks should prevent this, but catch it here as last resort).
    if not (prompt or "").strip():
        _emergency = (shot.get("description") or shot.get("_beat_action") or sid).strip()
        print(f"[ERROR] {sid}: compile_nano returned empty prompt — using emergency fallback")
        prompt = (
            f"{_emergency} "
            "[CAMERA: 35mm, f/4] "
            "[PALETTE: desaturated period tones, practical lighting] "
            "[PHYSICS: natural textures, atmospheric depth] "
            "[AESTHETIC: period realism, tactile surfaces, realistic skin texture with pores."
            " NO CGI, NO 3D render, NO airbrushed skin, NO plastic skin, NO doll face,"
            " NO digital art, NO beauty filter, NO studio lighting, NO smooth skin]"
        )

    image_urls = []
    for c in chars[:2]:
        ref = get_char_ref(cast, c)
        if ref:
            url = upload(ref)
            if url: image_urls.append(url)

    # V30.4 FIX: Location master ALWAYS included — remove the broken `< 2` guard.
    # ROOT CAUSE: Old guard `if len(image_urls) < 2` meant that for ANY 2-character shot
    # (Eleanor + Thomas), image_urls already had 2 entries → condition FALSE → location
    # master NEVER passed to FAL → model invented the room from text alone → location
    # inconsistency between shots. Seedance video runs ALWAYS included location master
    # (gen_scene_seedance appends it unconditionally) — that's why Seedance had better
    # rooms than first frames. This fix makes both paths consistent.
    # COST: nano-banana-pro accepts up to 4 refs. Adding location = 3rd ref slot.
    # Character refs stay at @image1/@image2 (highest attention). Location at @image3.
    # No cost increase — same single FAL call.
    _has_loc_ref = False
    # V30.5: Shot-type aware location master — OTS-B gets reverse angle
    _shot_type_for_loc = (shot.get('shot_type') or '').lower()
    if _shot_type_for_loc in ('ots_b',) and locs:
        # Try reverse angle first for OTS-B
        _loc_key = location_text.upper().replace(' ', '_').replace('-', '_')
        _reverse_loc = None
        for _lsn, _lsp in locs.items():
            if 'reverse' in _lsn.lower() and any(p in _lsn.upper() for p in _loc_key.split('_') if len(p) > 3):
                _reverse_loc = _lsp
                break
        loc = _reverse_loc or get_location_ref(locs, location_text)
        if _reverse_loc:
            print(f'  [LOC-REF] {sid}: OTS-B → reverse_angle location master')
    else:
        loc = get_location_ref(locs, location_text)
    if loc:
        url = upload(loc)
        if url:
            image_urls.append(url)
            _has_loc_ref = True

    # V30.5: EXT shots force T2I — interior location masters confuse exterior renders.
    # An interior room master (grand foyer, library) passed to FAL for an EXTERIOR shot
    # bleeds interior architecture into the exterior frame. Pure T2I gets cleaner results.
    # Condition: shot description starts with "EXT." AND no characters in shot.
    _shot_desc_upper = (shot.get("description") or "").strip().upper()
    if shot.get("_force_t2i") or (_shot_desc_upper.startswith("EXT.") and not chars):
        image_urls = []   # Drop any location master refs picked up above
        print(f"  [FRAME] {sid}: EXT shot → T2I (interior refs cleared)")

    # VCU-style: explicit reference role declarations prepended to prompt text.
    # FAL reads the first ~200 chars hardest — declaring ref roles here prevents
    # the model from treating character refs as set dressing and vice versa.
    _role_parts = []
    if chars and image_urls:
        _role_parts.append("Character reference — strictly preserve facial structure, proportions, and clothing from reference.")
    if _has_loc_ref:
        _role_parts.append("Location reference — use solely for environment, architecture, and lighting atmosphere.")
    if _role_parts:
        prompt = " ".join(_role_parts) + " " + prompt

    # V37: CPC decontamination — strip generic patterns AFTER full prompt assembly,
    # BEFORE FAL call. Preserves role declarations and identity blocks; only removes
    # generic contamination phrases that cause FAL to produce frozen/static frames.
    prompt = _cpc_decontaminate(
        prompt,
        character=chars[0] if chars else "",
        emotion=shot.get("_emotional_state", "neutral"),
        beat_desc=shot.get("_beat_action", ""),
    )

    # V29.16 VALIDATION FIX: 1 candidate only. 3-candidate lottery wastes $0.06/shot
    # and the Vision Judge pick wasn't meaningfully better than single best-effort.
    # User now validates first frames manually before video generation (--frames-only mode).
    # That manual review IS the quality gate — multi-candidate is redundant.
    num_imgs = 1

    # R63: Resolution routing — hero face shots get 4K for identity fidelity.
    # 4K (~$0.30/call) vs 2K (~$0.15/call) — 2x cost justified for face-fill shots
    # where identity markers (hair, eyes, skin, clothing) must read clearly for VLM scoring.
    # T2-SA-2: "Hero shots (close-ups, ECU, MCU): 4K resolution."
    _HERO_SHOT_TYPES = {"close_up", "mcu", "medium_close", "reaction", "ecu"}
    _shot_type_for_res = (shot.get("shot_type") or "medium").lower()
    _resolution = "4K" if _shot_type_for_res in _HERO_SHOT_TYPES and image_urls else "2K"

    # MODEL SELECTION: /edit for refs, /base for no refs
    if image_urls:
        model = NANO_EDIT
        args = {"prompt": prompt, "image_urls": image_urls,
                "aspect_ratio": "16:9", "output_format": "jpeg",
                "resolution": _resolution,   # R63: 4K for hero face shots, 2K for production
                "num_images": num_imgs, "safety_tolerance": 6}
    else:
        model = NANO_T2I
        args = {"prompt": prompt, "aspect_ratio": "16:9", "output_format": "jpeg",
                "resolution": "2K",          # T2I has no refs — 2K is correct
                "num_images": num_imgs, "safety_tolerance": 6}

    tag = "EDIT" if image_urls else "T2I"
    print(f"  [FRAME] {sid}: {tag}, {num_imgs}x, {len(image_urls)} refs, {len(prompt)} chars")
    _push_live_gen(sid, "running", "first_frame")

    # ── FAL QUEUE-RESILIENT DISPATCH (V30.3) ──────────────────────────────────
    # Root cause of 408 failures: FAL queue saturation exhausts all 10 internal
    # retries when multiple shots fire simultaneously. Three fixes:
    #   1. start_timeout=120 — tell FAL to hold the request 2min in queue before
    #      rejecting (vs ~30s default). Survives cold starts and brief saturation.
    #   2. Per-shot jitter (0-3s) before submission — desynchronizes concurrent
    #      ThreadPoolExecutor workers so they don't all hit the queue at once.
    #   3. Outer retry loop (max 3 attempts, 15s backoff) — if FAL still rejects
    #      after start_timeout, wait and retry rather than returning None.
    # V30.5: Dry-run mode — print prompt details without making any FAL call
    if dry_run:
        print(f"  [DRY-RUN] {sid}: {tag}, {len(image_urls)} refs, {len(prompt)} chars")
        print(f"  [DRY-RUN] Prompt: {prompt[:400]}...")
        if shot.get("_continuity_delta"):
            print(f"  [DRY-RUN] Continuity: {shot['_continuity_delta']}")
        if shot.get("_spatial_zone"):
            print(f"  [DRY-RUN] Zone: {shot['_spatial_zone']}")
        return None

    import random
    _jitter = random.uniform(0, 3)
    if _jitter > 0.5:
        time.sleep(_jitter)

    _MAX_OUTER = 3
    result = None
    for _attempt in range(1, _MAX_OUTER + 1):
        try:
            t0 = time.time()
            result = fal_client.subscribe(model, arguments=args, start_timeout=120)
            elapsed = time.time() - t0
            break  # success
        except Exception as _fal_err:
            elapsed = time.time() - t0
            if _attempt < _MAX_OUTER:
                _wait = 15 * _attempt
                print(f"  [FRAME] {sid}: FAL error attempt {_attempt}/{_MAX_OUTER} ({_fal_err.__class__.__name__}) — retry in {_wait}s")
                time.sleep(_wait)
            else:
                print(f"  [FRAME] {sid}: FAL failed after {_MAX_OUTER} attempts — {_fal_err}")
                return None
    if result is None:
        return None
    # ─────────────────────────────────────────────────────────────────────────
    _track_cost("nano", num_imgs)  # Track cost per candidate

    images = result.get("images", [])
    if not images:
        print(f"  [FRAME] {sid}: FAIL"); return None

    import urllib.request
    candidate_paths = []
    for i, img in enumerate(images):
        url = img.get("url")
        if not url: continue
        path = os.path.join(outdir, f"{sid}.jpg" if i == 0 else f"{sid}_c{i+1}.jpg")
        urllib.request.urlretrieve(url, path)
        candidate_paths.append(path)

    # VISION JUDGE — pick best candidate (if available and character shot)
    # WIRE 1: Returns (path, judge_score) so real Florence-2 score flows into reward signal
    best = candidate_paths[0] if candidate_paths else None
    judge_score = 0.75  # default identity score
    if chars and len(candidate_paths) > 1 and VISION_JUDGE_AVAILABLE:
        try:
            best, judge_score = _pick_best_candidate(candidate_paths, chars, cast, sid)
        except Exception as e:
            print(f"    [JUDGE] fallback to first: {e}")
            best = candidate_paths[0]
    elif candidate_paths and VISION_JUDGE_AVAILABLE:
        # Single candidate — still score it for I_score accuracy
        try:
            shot_dict = {"shot_id": sid, "characters": chars}
            verdict = judge_frame(sid, best, shot_dict, cast)
            if verdict.identity_scores:
                judge_score = sum(verdict.identity_scores.values()) / len(verdict.identity_scores)

            # ── WIRE A V36.3: AUTONOMOUS AUTO-FIX (upgraded from V30.2 annotate-only) ──
            # V36.3: Instead of just annotating REGEN_SUGGESTED, actually AUTO-REGEN
            # with identity boost. The user should never see the bad frame.
            # Budget: 2 auto-regens per scene (same cap). If exhausted, annotate for review.
            _scene_prefix = sid[:3]
            _eye_ck = (shot.get("_eye_line_target") or "").lower()
            _body_ck = (shot.get("_body_direction") or "").lower()
            _is_back_to_camera = (
                "away from camera" in _eye_ck or "back to camera" in _body_ck
                or "turned away" in _body_ck or "back partially" in _body_ck
            )
            if _is_back_to_camera:
                print(f"    [WIRE-A] {sid}: skip identity check — back-to-camera (narrative intent)")
            elif getattr(verdict, 'verdict', None) == 'REGEN' and chars:
                if not _wire_a_can_regen(_scene_prefix):
                    _wa_used = _wire_a_regen_counts.get(_scene_prefix, 0)
                    print(f"    [WIRE-A] Scene {_scene_prefix}: regen budget exhausted ({_wa_used}/{_WIRE_A_MAX_REGENS_PER_SCENE}) — flagging {sid}")
                    shot["_approval_status"] = "REGEN_SUGGESTED"
                    shot["_wire_a_reason"] = f"identity_score_{judge_score:.2f}_budget_exhausted"
                else:
                    _wire_a_consume(_scene_prefix)
                    print(f"    [WIRE-A] {sid}: AUTO-REGEN (I={judge_score:.2f}) — boosting identity")
                    # Inject identity correction and regenerate
                    _id_boost = "[IDENTITY CORRECTION: Previous frame had wrong face/appearance. "
                    _id_boost += "STRICTLY match character reference image. "
                    for _ch in chars:
                        _cm = cast.get(_ch, {})
                        _app = _cm.get("appearance", "")[:120]
                        if _app:
                            _id_boost += f"{_ch}: {_app}. "
                    _id_boost += "]"
                    shot["_pvg_diagnostic"] = _id_boost
                    try:
                        _regen_best, _regen_score = gen_frame(shot, cast, locs, sb_scene, contract, mode, outdir, location_text, dry_run)
                        if _regen_best and _regen_score > judge_score:
                            best = _regen_best
                            judge_score = _regen_score
                            print(f"    [WIRE-A] {sid}: AUTO-FIX SUCCESS (I={_regen_score:.2f} > {judge_score:.2f})")
                            shot["_approval_status"] = "AUTO_APPROVED"
                            shot.pop("_pvg_diagnostic", None)
                        else:
                            print(f"    [WIRE-A] {sid}: regen did not improve (I={_regen_score:.2f}) — keeping original")
                            shot.pop("_pvg_diagnostic", None)
                    except Exception as _wa_err:
                        print(f"    [WIRE-A] {sid}: auto-regen failed ({_wa_err}) — keeping original")
                        shot.pop("_pvg_diagnostic", None)

            # ── WIRE A-2 V36.3: CANON VALIDATION (universal intake protocol) ──────
            # Check frame against story_state_canon for wardrobe/prop violations.
            # This makes the quality gate universal — reads from canon to know what to enforce.
            # V36.3: Also checks cross-scene wardrobe bleed (wardrobe from wrong scene).
            try:
                import sys as _sys
                if "tools" not in _sys.path: _sys.path.insert(0, "tools")
                from story_state_canon import get_canon_state, validate_against_canon, validate_cross_scene_wardrobe
                _canon = get_canon_state(_scene_prefix)
                if _canon:
                    _violations = validate_against_canon(shot, _canon)
                    # V36.3: Cross-scene wardrobe bleed check
                    _xscene_violations = validate_cross_scene_wardrobe(shot, _scene_prefix)
                    _violations.extend(_xscene_violations)
                    if _violations:
                        print(f"    [CANON] {sid}: {len(_violations)} violation(s): {_violations[:2]}")
                        shot["_canon_violations"] = _violations[:5]
                        if _xscene_violations:
                            print(f"    [WARDROBE-BLEED] {sid}: {len(_xscene_violations)} cross-scene wardrobe bleed(s)")
                    else:
                        print(f"    [CANON] {sid}: PASS")
            except Exception:
                pass  # Canon validation is advisory — never blocks
            # ─────────────────────────────────────────────────────────────────────
        except Exception:
            pass

    if best:
        print(f"  [FRAME] {sid}: OK — {os.path.getsize(best)/1024:.0f}KB — {elapsed:.1f}s — {len(candidate_paths)} cands — I={judge_score:.2f}")

        # ── VVO CHECKPOINT A (V36.5+): POST-FRAME QUALITY GATE ───────────────────────────
        # Fires at EVERY checkpoint — runs AFTER frame is written, BEFORE it becomes start_url.
        # E-shots: check no unexpected human figures crept in (reuses preflight logic).
        # Character shots: check frame is not blank/corrupted (size gate, non-API).
        # NON-BLOCKING: flags shot for review, never aborts generation.
        try:
            _gfa_chars = shot.get("characters") or []
            if _VVO_AVAILABLE and not _gfa_chars and not shot.get("_no_char_ref") and not shot.get("_is_broll"):
                # E-shot: use VVO preflight to detect unexpected human figures in first frame
                _gfa_sb = sb_scene  # story bible scene context
                _gfa_result = _vvo_preflight_e_shot(best, shot, _gfa_sb)
                if not _gfa_result.passed:
                    print(f"  [VVO-A] ❌ {sid}: E-shot first frame has unexpected content — {_gfa_result.description[:100]}")
                    shot["_vvo_frame_rejected"] = True
                    if shot.get("_approval_status") not in ("APPROVED", "AUTO_APPROVED"):
                        shot["_approval_status"] = "REGEN_SUGGESTED"
                else:
                    print(f"  [VVO-A] ✓ {sid}: E-shot frame clean — {_gfa_result.description[:80]}")
            elif _gfa_chars:
                # Character shot: verify frame file is not suspiciously small (< 5KB = corrupted)
                _gfa_size = os.path.getsize(best)
                if _gfa_size < 5000:
                    print(f"  [VVO-A] ⚠️  {sid}: first frame suspiciously small ({_gfa_size}B) — flagging for review")
                    shot["_vvo_frame_size_warn"] = True
                    if shot.get("_approval_status") not in ("APPROVED", "AUTO_APPROVED"):
                        shot["_approval_status"] = "REGEN_SUGGESTED"
                else:
                    print(f"  [VVO-A] ✓ {sid}: character frame size OK ({_gfa_size//1024}KB)")
        except Exception as _gfa_err:
            print(f"  [VVO-A] exception (non-blocking): {_gfa_err}")
        # ─────────────────────────────────────────────────────────────────────────────────

        _push_live_gen(sid, "completed", "first_frame",
                       url=f"/api/media?path={best}")
    else:
        _push_live_gen(sid, "error", "first_frame")
    return best, judge_score  # WIRE 1: tuple (path, real_florence2_score)


def _pick_best_candidate(paths, chars, cast, sid):
    """Vision Judge: score candidates against char ref using Florence-2 captioning.
    Falls back to file size if Florence-2 unavailable."""
    best_path = paths[0]
    best_score = -1

    if VISION_JUDGE_AVAILABLE:
        try:
            # Build a minimal shot dict for the judge
            shot_dict = {"shot_id": sid, "characters": chars}
            for path in paths:
                verdict = judge_frame(sid, path, shot_dict, cast)
                # Use average identity score across characters
                if verdict.identity_scores:
                    avg = sum(verdict.identity_scores.values()) / len(verdict.identity_scores)
                else:
                    avg = 0
                tag = "PASS" if verdict.verdict == "PASS" else verdict.verdict
                print(f"    [JUDGE] {os.path.basename(path)}: {avg:.2f} ({tag})")
                if avg > best_score:
                    best_score = avg
                    best_path = path

            if best_path != paths[0]:
                primary = os.path.join(os.path.dirname(best_path), f"{sid}.jpg")
                if best_path != primary:
                    shutil.copy2(best_path, primary)
                    best_path = primary
                print(f"    [JUDGE] Best: {os.path.basename(best_path)} (score={best_score:.2f})")
            return best_path, best_score  # WIRE 1: tuple
        except Exception as e:
            print(f"    [JUDGE] Florence-2 failed ({e}), falling back to file size")

    # Fallback: file size proxy (larger = richer detail = usually better)
    for path in paths:
        score = os.path.getsize(path) / 1024
        if score > best_score:
            best_score = score
            best_path = path

    if best_path != paths[0]:
        primary = os.path.join(os.path.dirname(best_path), f"{sid}.jpg")
        if best_path != primary:
            shutil.copy2(best_path, primary)
            best_path = primary
        print(f"    [JUDGE] Selected by size: {os.path.basename(best_path)} ({best_score:.0f}KB)")

    # Normalize score: file size proxy → 0.0-1.0 scale (cap at 500KB = 1.0)
    normalized = min(best_score / 500.0, 1.0)
    return best_path, normalized  # WIRE 1: tuple


def gen_video(shot, cast, contract, frame_path, mode, outdir, context=None):
    """Generate video — routes to Kling (character) or LTX (B-roll)."""
    sid = shot["shot_id"]
    chars = shot.get("characters") or []
    dur = shot.get("duration", "10")
    model_choice, reason = route_shot(shot)

    prompt = compile_video_prompt(shot, cast, contract, mode, context)
    prompt = _cpc_decontaminate(
        prompt,
        character=chars[0] if chars else "",
        emotion=shot.get("_emotional_state", "neutral"),
        beat_desc=shot.get("_beat_action", ""),
    )

    start_url = upload(frame_path)
    if not start_url:
        print(f"  [VIDEO] {sid}: FAIL upload"); return None

    if model_choice == "kling":
        # Kling with identity elements
        elements = []
        for c in chars[:2]:
            ref = get_char_ref(cast, c)
            if ref:
                ref_url = upload(ref)
                if ref_url:
                    elements.append({"frontal_image_url": ref_url, "reference_image_urls": [ref_url]})

        for i in range(len(elements)):
            tag = f"@Element{i+1}"
            if tag not in prompt: prompt = f"{tag} " + prompt

        args = {"prompt": prompt[:2500], "start_image_url": start_url,
                "duration": dur, "aspect_ratio": "16:9",
                "negative_prompt": NEG, "cfg_scale": 0.5}
        if elements: args["elements"] = elements

        print(f"  [VIDEO] {sid}: KLING {dur}s, {len(elements)} IDs, {len(prompt)} chars — {reason}")
        model_endpoint = KLING

    else:
        # C3 MODEL LOCK: LTX RETIRED. NEW-R FIX (2026-03-21).
        # route_shot() returns "seedance" in normal ops — this branch is only reached
        # when gen_scene_multishot() is explicitly triggered (ATLAS_VIDEO_MODEL=kling).
        # In that mode, all shots use Kling — never LTX (retired per C3).
        args = {"prompt": prompt[:2500], "start_image_url": start_url,
                "duration": int(str(dur).strip()), "aspect_ratio": "16:9",
                "negative_prompt": NEG, "cfg_scale": 0.5}

        print(f"  [VIDEO] {sid}: KLING-FALLBACK {dur}s, {len(prompt)} chars — C3 safe (LTX retired)")
        model_endpoint = KLING

    t0 = time.time()
    result = fal_client.subscribe(model_endpoint, arguments=args)
    elapsed = time.time() - t0
    _track_cost("kling")

    vid_url = result.get("video", {}).get("url")
    if not vid_url:
        print(f"  [VIDEO] {sid}: FAIL"); return None

    import urllib.request
    out = os.path.join(outdir, f"{sid}.mp4")
    urllib.request.urlretrieve(vid_url, out)
    mb = os.path.getsize(out) / (1024*1024)

    # POST-VIDEO QUALITY CHECK: frozen statue detection
    is_frozen = _check_frozen(out)
    frozen_tag = " ⚠FROZEN" if is_frozen else ""

    print(f"  [VIDEO] {sid}: OK — {mb:.1f}MB — {elapsed:.1f}s{frozen_tag}")
    if is_frozen:
        print(f"    [QUALITY] WARNING: Video may be frozen/static — low frame difference detected")

    return out


def gen_scene_multishot(mshots, cast, contract, first_frame_path, mode, outdir, context=None, gen_mode="chain", all_frames=None):
    """
    KLING MULTI-SHOT: ONE call per scene. Character persists across all shots.
    Matches the user's proven working format:
      start_image_url + multi_prompt[{prompt, duration}...] + elements + negative + cfg=0.5

    For scenes ≤ 15s total: ONE call with all shots.
    For scenes > 15s: Split into groups of ≤15s, each group = one call.

    V29.3 FIX: ALL shots go through Kling. No LTX branch. Establishing shots are
    skipped in auto_consolidate so they never reach this function. Kling only.
    """
    # V29.3: ALL shots go through Kling (no LTX path).
    # Establishing shots are skipped in auto_consolidate.
    # Pure environment scenes (chars=[]) still use Kling — just no @Element identity blocks.
    _reset_cost_tracker()  # FIX-ERR-08: reset per-scene so multi-scene cost tracking is accurate
    kling_shots = list(mshots)  # All shots → Kling

    results = {}  # sid -> video_path

    # V31.1 post-video gate helpers — set before group loop
    cast_map_for_arj = cast if isinstance(cast, dict) else {}
    _arj_regens_used: dict = {}   # gi → int regen count (capped by VisionBudgetTracker)

    # ── VISION BUDGET: reset scene-level counters ─────────────────────────────
    _vbt = _get_vbt()
    if _vbt:
        _vbt.reset_scene(len(kling_shots))
        print(f"  [VISION BUDGET] Scene budget initialised: {_vbt.budget_summary()}")

    # Group Kling shots into ≤15s chunks for multi_prompt
    if not kling_shots:
        print(f"  [MULTISHOT] No character shots to render — skipping")
        return results

    # Collect all unique characters for identity elements
    # V31.1: Sort by speaking frequency (most-speaking chars get the 2 identity element slots)
    # Fixes 3-char climax scenes where alphabetical sort dropped the primary speaker
    from collections import Counter as _Counter
    _spk_counts = _Counter(s.get("_dialogue_speaker","") for s in kling_shots if s.get("_dialogue_speaker",""))
    all_chars = sorted(
        set(c for s in kling_shots for c in (s.get("characters") or [])),
        key=lambda c: -_spk_counts.get(c, 0)  # most-speaking first; ties → alphabetical as before
    )

    # Upload identity elements ONCE (reused across all multi_prompt calls)
    elements = []
    for c in all_chars[:2]:
        ref = get_char_ref(cast, c)
        if ref:
            ref_url = upload(ref)
            if ref_url:
                elements.append({"frontal_image_url": ref_url, "reference_image_urls": [ref_url]})

    # Upload start image (first frame of the scene)
    start_url = upload(first_frame_path)
    if not start_url:
        print(f"  [MULTISHOT] FAIL: could not upload start frame")
        return results

    # V29.9: 1 beat per Kling call — SCRIPT-CONSCIOUS TIMING
    # "slow it down, conscious of script timing and framing, don't add too much to one shot"
    # Each beat gets its OWN focused Kling call. No grouping. 1 shot = 1 video = 1 moment.
    # V29.7 pacing formula still applies: dialogue shots = word_count/2.3 + 1.5s (max 10s)
    # Cost: same per shot. Quality: Kling can fully commit to ONE action / ONE dialogue beat.
    groups = []
    for s in kling_shots:
        # V29.7 FIX: Dialogue-aware duration — word count sets minimum, cap at 10s
        base_dur = int(s.get("duration", "5"))
        dlg_text = (s.get("dialogue_text") or s.get("_beat_dialogue") or "").strip()
        if dlg_text:
            words = len(dlg_text.split())
            min_dlg_dur = int(words / 2.3 + 1.5)
            shot_dur = min(max(base_dur, min_dlg_dur), 15)  # dialogue: respect word count, max 10s
        else:
            shot_dur = min(base_dur, 15)  # V30.6: non-dialogue up to 10s for full action beats
        # V30.6 → V37: Kling API accepts 5, 10, or 15 — snap to nearest valid value
        shot_dur = 15 if shot_dur >= 15 else (10 if shot_dur > 5 else 5)
        # V29.9: ALWAYS 1 shot per group — each beat stands alone
        groups.append([(s, shot_dur)])

    # ── V36.1 Hybrid Chain/Parallel Intelligence ────────────────────────────────
    # Per-shot generation strategy based on story bible role:
    #   INDEPENDENT  = B-roll / E-shots (_is_broll or _no_char_ref) — own first frame, no chain dep
    #   CHAIN_ANCHOR = first character/dialogue group — own first frame, starts the chain
    #   CHAIN        = subsequent character groups — receives end-frame from previous shot
    #
    # Processing order: independent groups first (fast, no deps), then chain sequence.
    # This fixes the V36 bug where parallel_shots were removed from groups but never rendered.
    if gen_mode == "chain":
        _independent_groups = []
        _chain_groups = []
        _chain_anchor_set = False

        for g in groups:
            is_independent = all(s.get("_is_broll") or s.get("_no_char_ref") for s, _dur in g)
            if is_independent:
                for s, _dur in g:
                    _ps_sid = s.get("shot_id", "")
                    _ps_fp = (all_frames or {}).get(_ps_sid) or first_frame_path
                    _ps_url = upload(_ps_fp) if _ps_fp else None
                    if _ps_url:
                        s["_independent_start_url"] = _ps_url
                    s["_gen_strategy"] = "INDEPENDENT"
                _independent_groups.append(g)
            else:
                if not _chain_anchor_set:
                    # First character group is the anchor — uses its own approved first frame
                    for s, _dur in g:
                        s["_gen_strategy"] = "CHAIN_ANCHOR"
                    _chain_anchor_set = True
                else:
                    for s, _dur in g:
                        s["_gen_strategy"] = "CHAIN"
                _chain_groups.append(g)

        n_indep = sum(len(g) for g in _independent_groups)
        n_chain = sum(len(g) for g in _chain_groups)
        if _independent_groups:
            print(f"  [HYBRID] {n_indep} shot(s) → INDEPENDENT (own first frames, no chain dep)")
            print(f"  [HYBRID] {n_chain} shot(s) → CHAIN (visual continuity sequence)")
            print(f"  [HYBRID] Order: independent groups first → then chain sequence")

        # Log the full scene generation plan
        all_groups_ordered = _independent_groups + _chain_groups
        for gi, g in enumerate(all_groups_ordered):
            strategies = {s.get("_gen_strategy", "UNKNOWN") for s, _ in g}
            shot_ids = [s.get("shot_id", "?") for s, _ in g]
            print(f"  [PLAN] Group {gi+1}: {shot_ids} → {strategies}")

        # Independent groups processed first, chain groups follow in order
        groups = _independent_groups + _chain_groups
    # ─────────────────────────────────────────────────────────────────────────────

    # V37: Write final chain_group index to every shot in-memory NOW, before the pre-gen
    # gate fires. chain_intelligence_gate._check_chain_group() requires chain_group on all
    # M-shots — without it the gate reports an error and blocks every group.
    # This is the ONLY place where the final execution order is known (independent groups
    # first, chain groups after). Writing here ensures gate sees correct chain_group values.
    for _cg_gi, _cg_group in enumerate(groups):
        for _cg_s, _ in _cg_group:
            _cg_s["chain_group"] = _cg_gi
            _cg_s["_chain_group"] = _cg_gi

    # V36.1: REFRAME FLIP — outgoing hint appended to shot N's prompt (not prepended to N+1).
    # These soft hints bake the transition into the END of shot N's clip so the chain frame
    # already contains the transition motion. Shot N+1 starts from a frame already heading
    # in the right direction — no fighting the chain frame with an incoming directive.
    _REFRAME_MAP = {
        # Opening shots — hint camera will drift inward
        ("establishing", "medium"):       "The camera drifts gently closer as the shot ends.",
        ("establishing", "ots_a"):        "The framing begins moving closer, settling over a shoulder.",
        ("establishing", "two_shot"):     "The camera eases forward toward the pair.",
        ("establishing", "close_up"):     "The camera begins a slow drift inward toward the face.",
        # Medium → tighter coverage
        ("medium", "ots_a"):              "The framing subtly shifts closer, angling over a shoulder.",
        ("medium", "ots_b"):              "The camera begins a gentle turn toward the other side.",
        ("medium", "two_shot"):           "The framing holds as the characters settle into focus.",
        ("medium", "close_up"):           "The camera drifts closer, background beginning to blur.",
        ("medium", "medium_close"):       "The camera eases in slightly, tightening the frame.",
        ("medium", "closing"):            "The camera begins a slow, natural pull outward.",
        # OTS pair — soft hint of cross-axis shift
        ("ots_a", "ots_b"):               "The framing begins its shift across the conversation axis.",
        ("ots_b", "ots_a"):               "The camera begins returning across the axis toward the speaker.",
        ("ots_a", "two_shot"):            "The framing naturally opens as both figures come into view.",
        ("ots_b", "two_shot"):            "The framing naturally opens as both figures come into view.",
        ("ots_a", "close_up"):            "The camera drifts closer toward the speaker's face.",
        ("ots_b", "close_up"):            "The camera drifts closer toward the speaker's face.",
        ("ots_a", "closing"):             "The camera begins a slow, measured pull away.",
        ("ots_b", "closing"):             "The camera begins a slow, measured pull away.",
        # Two-shot → coverage
        ("two_shot", "close_up"):         "The camera drifts gently closer, face filling the frame.",
        ("two_shot", "medium_close"):     "The framing tightens slightly as the shot concludes.",
        ("two_shot", "ots_a"):            "The camera eases forward and settles over a shoulder.",
        ("two_shot", "ots_b"):            "The framing shifts to favor the other side of the axis.",
        ("two_shot", "closing"):          "The camera begins a slow, deliberate pull outward.",
        # Close-up / medium_close → wider
        ("close_up", "medium"):           "The framing naturally opens outward as the shot ends.",
        ("close_up", "two_shot"):         "The camera pulls back gently, revealing both figures.",
        ("close_up", "ots_a"):            "The framing eases back into an over-shoulder composition.",
        ("close_up", "ots_b"):            "The framing eases back to the other side of the conversation.",
        ("close_up", "closing"):          "The camera begins a wide, sweeping pull back.",
        ("medium_close", "medium"):       "The framing naturally opens outward.",
        ("medium_close", "close_up"):     "The camera drifts closer as the emotion intensifies.",
        ("medium_close", "two_shot"):     "The framing pulls back to include both characters.",
        ("medium_close", "closing"):      "The camera begins a slow, unhurried pull away.",
        # Closing / insert
        ("closing", "medium"):            "The camera drifts inward as the next moment begins.",
        ("insert", "medium"):             "The framing opens to reveal the characters beyond.",
        ("insert", "medium_close"):       "The framing eases back into medium-close territory.",
        ("insert", "close_up"):           "The camera moves closer toward the subject.",
        ("insert", "ots_a"):              "The framing eases back into an over-shoulder view.",
        ("insert", "two_shot"):           "The camera pulls back to include both characters.",
        # medium_close → ots
        ("medium_close", "ots_a"):        "The framing eases forward into an over-shoulder angle.",
        ("medium_close", "ots_b"):        "The framing shifts to favor the other side.",
        ("medium_close", "closing"):      "The camera begins a slow pull away.",
    }
    # V36.1: Transitions that cross the axis or jump focal extremes — soften further
    # to prevent the outgoing hint from fighting the chain frame.
    _AGGRESSIVE_TRANSITIONS = {
        ("ots_a", "ots_b"),
        ("ots_b", "ots_a"),
        ("establishing", "close_up"),
        ("close_up", "establishing"),
    }


    # V36.1: REFRAME FLIP — flat shot list for cross-group lookahead
    # Outgoing hint on the last shot of group N must see first shot of group N+1.
    _all_shots_flat = []
    for _g in groups:
        for _s, _d in _g:
            _all_shots_flat.append(_s)
    _shot_idx_map = {_s.get("shot_id", ""): _i for _i, _s in enumerate(_all_shots_flat)}

    # V36.3: Contamination tracker — if ARJ rejects a group AND regen fails,
    # that group's end-frame is CONTAMINATED and must NOT chain to next shot.
    _arj_contaminated = {}  # {group_index: True} for contaminated groups

    # V37.1: Chain break tracker — if Kling fails or end-frame extraction fails,
    # we halt the scene and set HUMAN_ESCALATION on all downstream chain shots.
    # NO fallback frame generation. The human must fix and re-run deliberately.
    _chain_break_group = None   # group index where chain broke (None = no break)

    # V36.5: Chain Intelligence Gate state
    _cig_audit_entries = []      # collected pre/post gate verdicts → written to gate_audit.json
    _cig_prev_contract = None    # ChainContract from last group's final frame (position handoff)
    _cig_scene_shots   = mshots  # full scene shot list for cross-shot validators

    # Generate each group as ONE multi_prompt call
    for gi, group in enumerate(groups):
        multi_prompt = []
        group_sids = []

        # ── PARALLEL MODE: each shot uses its own first frame as start_url ──────
        # In parallel mode we bypass all chaining — each shot is independent.
        # The start_url is resolved from all_frames[shot_id] (its approved first frame).
        if gen_mode == "parallel" and all_frames:
            _par_sid = group[0][0].get("shot_id", "")
            _par_fp = all_frames.get(_par_sid) or first_frame_path
            _par_url = upload(_par_fp)
            if _par_url:
                start_url = _par_url
                print(f"  [PARALLEL] Group {gi+1} ({_par_sid}): own first frame → start_url ✓")
            else:
                print(f"  [PARALLEL] Group {gi+1} ({_par_sid}): upload failed — falling back to scene start frame")
        # V36.1 Hybrid: INDEPENDENT shots use their own first frame (no chain dependency)
        # CHAIN_ANCHOR shots also use their own first frame (they start the chain)
        # CHAIN shots inherit start_url from the previous group's end-frame (no override here)
        elif group and group[0][0].get("_independent_start_url"):
            start_url = group[0][0]["_independent_start_url"]
            strategy = group[0][0].get("_gen_strategy", "INDEPENDENT")
            print(f"  [HYBRID] Group {gi+1}: {strategy} — using own first frame as start_url")
        elif group and group[0][0].get("_gen_strategy") == "CHAIN_ANCHOR":
            # Chain anchor: resolve its own approved first frame
            _anchor_sid = group[0][0].get("shot_id", "")
            _anchor_fp = (all_frames or {}).get(_anchor_sid) or first_frame_path
            _anchor_url = upload(_anchor_fp) if _anchor_fp else None
            if _anchor_url:
                start_url = _anchor_url
                print(f"  [HYBRID] Group {gi+1}: CHAIN_ANCHOR ({_anchor_sid}) — own first frame starts chain")
            else:
                print(f"  [HYBRID] Group {gi+1}: CHAIN_ANCHOR upload failed — using scene start frame")
        # Legacy fallback: old _parallel_start_url field
        elif group and group[0][0].get("_parallel_start_url"):
            start_url = group[0][0]["_parallel_start_url"]
            print(f"  [HYBRID] Group {gi+1}: legacy parallel start frame")
        # ─────────────────────────────────────────────────────────────────────────
        for _gi_shot, (s, dur) in enumerate(group):
            choreo = s.get("_choreography", "")
            dlg = s.get("dialogue_text", "") or ""
            action = s.get("_beat_action") or s.get("description", "")
            chars = s.get("characters") or []
            spk_name = s.get("_dialogue_speaker", "")

            # Build speaker label from cast_map appearance (FAL reads appearance, not names)
            def _gender_label(char_name, cast_map):
                if not char_name or not cast_map: return ""
                entry = cast_map.get(char_name, {})
                app = entry.get("appearance", "") if isinstance(entry, dict) else ""
                app_l = app.lower()
                if "woman" in app_l or "female" in app_l or "her " in app_l: return "woman"
                if "man" in app_l or "male" in app_l or "his " in app_l: return "man"
                return ""

            # V29.2 FIX: Multi-speaker dialogue attribution — don't merge both speakers into one line
            # Parse pipe-separated dialogue and attribute to correct speaker
            # "THOMAS BLACKWOOD: text | ELEANOR VOSS: text" → Element1/Element2 labels
            CHAR_PREFIXES = (_ACTIVE_CHAR_PREFIXES or ["NADIA COLE:", "THOMAS BLACKWOOD:", "ELEANOR VOSS:", "RAYMOND CROSS:", "HARRIET HARGROVE:"])

            def parse_dialogue_segments(dlg_raw, chars, cast):
                """Return list of (speaker_char_name_or_empty, text) tuples"""
                if not dlg_raw: return []
                segs = []
                for seg in dlg_raw.split("|"):
                    seg = seg.strip()
                    if not seg: continue
                    found_spk = ""
                    clean = seg
                    for pfx in CHAR_PREFIXES:
                        if seg.upper().startswith(pfx):
                            found_spk = pfx.replace(":", "").strip().title()
                            for c in chars:
                                if c.upper() == pfx.replace(":","").strip():
                                    found_spk = c
                                    break
                            clean = seg[len(pfx):].strip()
                            break
                    segs.append((found_spk, clean))
                return segs

            dlg_segs = parse_dialogue_segments(dlg, chars, cast)

            # V29.9: SCRIPT-CONSCIOUS TIMING — 1 beat per call, framing-aware prompt
            # Frame type header (OTS-A/B, two_shot, medium, closing) sets spatial context FIRST.
            # Beat action follows — SPECIFIC to this story moment, not generic rewrite.
            # Kling reads framing + action + dialogue as a single intentional cinematic unit.
            parts = []

            # V36.2: OPENER DIRECTIVE — inject motion energy directive for M01 (first shot in scene)
            # This is the highest-attention position: Kling reads the first ~100 chars most strongly.
            # DIALOGUE_OPENER → "MID-CONVERSATION" energy. ACTION_OPENER → kinetic. etc.
            _opener_type_v = s.get("_scene_opener_type") or s.get("_opener_type") or ""
            if _opener_type_v and gi == 0 and _gi_shot == 0:  # first shot in entire scene's video sequence
                _OPENER_SHORT = {
                    "DIALOGUE_OPENER":   "MID-CONVERSATION — lips moving, gestures active from frame 1.",
                    "COLD_OPEN":         "IN PROGRESS — action already underway, no pause.",
                    "ACTION_OPENER":     "KINETIC START — body already in motion from frame 1.",
                    "REVELATION_OPENER": "TENSION — slow deliberate movement, building toward reveal.",
                    "ATMOSPHERE_OPENER": "STILLNESS — slow ambient drift, natural breathing.",
                    "BROLL_OPENER":      "ENVIRONMENT — slow camera through empty space.",
                }
                _od = _OPENER_SHORT.get(_opener_type_v, "")
                if _od:
                    parts.append(_od)
                    print(f"    [V36.2 OPENER→KLING] {s.get('shot_id','?')}: {_opener_type_v} → {_od[:50]}")

            # V36.1: shot type tracked for outgoing reframe (appended at end of parts)
            _cur_shot_type = (s.get("shot_type") or "").lower()

            # V29.10: Lead with shot TYPE LABEL only (not full spatial description)
            # _frame_description is the nano first-frame prompt (250+ chars of spatial blocking).
            # For Kling VIDEO, we only need the type label — Kling already HAS the first frame.
            # Extract the leading type label (everything before the first period or first char
            # count threshold). Examples:
            #   "MEDIUM TWO-SHOT. Eleanor frame-left..." → "MEDIUM TWO-SHOT"
            #   "OVER-THE-SHOULDER SHOT. Thomas back..." → "OVER-THE-SHOULDER"
            #   "CLOSE-UP. Nadia face fills frame..." → "CLOSE-UP"
            frame_desc = s.get("_frame_description", "") or ""
            shot_type_label = ""
            if frame_desc:
                # Take everything before the first period OR first 30 chars (whichever is shorter)
                label_raw = frame_desc.split(".")[0].strip()
                if len(label_raw) <= 30:
                    shot_type_label = label_raw
                # else: skip label — it's a sentence, not a type label

            beat_idx = s.get("_beat_index") or 0
            beat_total = len(kling_shots)
            # Beat position context for Kling pacing: "Opening beat." / "Mid scene." / "Closing beat."
            if beat_total > 1:
                if beat_idx == 0:
                    beat_pos = "Opening beat."
                elif beat_idx >= beat_total - 1:
                    beat_pos = "Closing beat."
                else:
                    beat_pos = "Mid scene."
            else:
                beat_pos = ""

            # Lead with: SHOT TYPE LABEL + beat position (both compact, total ≤45 chars)
            if shot_type_label:
                parts.append(f"{shot_type_label}. {beat_pos}".strip().rstrip(".") + ".")
            elif beat_pos:
                parts.append(beat_pos)

            action_clean = strip_location_names(action) if action else ""
            if action_clean:
                a = action_clean.rstrip(".").rstrip()
                parts.append(f"{a}.")
            # V30.6: Add body_direction for physical specificity (was stripped in V29.7, Kling v3 handles it)
            _body = s.get("_body_direction", "").strip()
            if _body and _body not in ("present, natural micro-movements", "neutral, present in scene"):
                parts.append(f"{_body[:50]}.")
            # V30.6: Compact atmosphere from story bible
            _atm = s.get("_beat_atmosphere", "").strip()
            if _atm:
                parts.append(f"{_atm[:40]}.")
            # V30.6: Compact camera directive — Kling v3 reads these natively
            _cam_map = {"close_up": "tight on face", "ots_a": "over shoulder", "ots_b": "reverse over shoulder",
                        "two_shot": "two shot locked", "wide": "wide pull back", "closing": "slow pull back",
                        "establishing": "establishing wide", "medium": "medium shot"}
            _cam = _cam_map.get((s.get("shot_type") or "").lower(), "")
            if _cam:
                parts.append(f"{_cam}.")

            # V36.4: ROOM ANCHOR for chain groups 2+ — compact location text so Kling
            # doesn't drift the environment when start_image is a reframed chain frame.
            # Only fires for groups after the first (gi > 0) where the start image is a
            # chain frame rather than the original first-frame (which already has full DNA).
            if gi > 0 and context and isinstance(context, dict):
                _rf_dna = (context.get("_room_dna") or "").strip()
                if _rf_dna:
                    # Extract just the room description, strip [ROOM DNA: ...] wrapper
                    _rf_dna_inner = _rf_dna.replace("[ROOM DNA: ", "").rstrip("]").strip()
                    # Compact to ~60 chars — enough for Kling to anchor the room
                    _rf_dna_short = _rf_dna_inner[:60].rsplit(",", 1)[0] if len(_rf_dna_inner) > 60 else _rf_dna_inner
                    parts.append(f"Setting: {_rf_dna_short}.")

            # V36.5: ARC POSITION MODIFIER — emotional escalation per beat position
            # Opening doesn't need modifier (it sets tone). Middle/Pivot/Resolve get
            # compact emotional direction that sequences beats correctly.
            _arc_pos = s.get("_arc_position", "")
            if _arc_pos:
                _arc_mod = get_chain_modifier(_arc_pos, gi)
                _arc_suffix = _arc_mod.get("prompt_suffix", "")
                if _arc_suffix:
                    parts.append(_arc_suffix)

            # V29.3: Dialogue format — "Speaking:" for solo, "@Element{N} [gender speaks]:" for multi-char
            # Proven working format: solo = Speaking: "full text", multi = @Element per speaker
            is_solo_scene = (len(all_chars) <= 1)
            if dlg_segs:
                if is_solo_scene:
                    # SOLO: merge ALL pipe segments into one clean Speaking: block
                    all_text = " ".join(t for _, t in dlg_segs if t)
                    if all_text:
                        parts.append(f'Speaking: "{all_text[:120]}"')
                else:
                    # MULTI-CHAR: @Element{N} [gender speaks]: "text" per speaker
                    # V29.3: Merge consecutive same-speaker segments into one line
                    merged = []  # list of (el_idx, gender, combined_text)
                    _max_el = max(len(elements), 1)  # V31.1: cap at actual uploaded element count
                    for spk, text in dlg_segs:
                        if not text: continue
                        if spk and spk in chars:
                            el_idx = min(chars.index(spk) + 1, _max_el)  # V31.1: clamp to available elements
                            gender = _gender_label(spk, cast)
                        elif spk_name and spk_name in chars:
                            el_idx = min(chars.index(spk_name) + 1, _max_el)
                            gender = _gender_label(spk_name, cast)
                        else:
                            el_idx = 1
                            gender = _gender_label(chars[0] if chars else "", cast)
                        # Merge if same speaker as last entry
                        if merged and merged[-1][0] == el_idx:
                            prev_el, prev_gen, prev_text = merged[-1]
                            merged[-1] = (prev_el, prev_gen, f"{prev_text} {text}")
                        else:
                            merged.append((el_idx, gender, text))
                    dlg_parts = [f'@Element{ei} [{g or "character"} speaks]: "{t[:120]}"'
                                 for ei, g, t in merged]
                    if dlg_parts:
                        parts.append(" | ".join(dlg_parts))
            elif dlg:
                # Fallback: strip prefix, clean text
                clean_dlg = dlg
                for pfx in CHAR_PREFIXES:
                    clean_dlg = clean_dlg.replace(pfx, "")
                clean_dlg = clean_dlg.replace("|", " ").strip()[:120]
                if is_solo_scene:
                    parts.append(f'Speaking: "{clean_dlg}"')
                else:
                    _max_el2 = max(len(elements), 1)  # V31.1: clamp to available elements
                    el_idx = 1
                    gender = _gender_label(spk_name or (chars[0] if chars else ""), cast)
                    if spk_name and spk_name in chars:
                        el_idx = min(chars.index(spk_name) + 1, _max_el2)
                    parts.append(f'@Element{el_idx} [{gender or "character"} speaks]: "{clean_dlg}"')
            if not dlg_segs and not dlg:
                # V30.6: _beat_dialogue as final fallback — catches shots where dialogue_text
                # is empty but story bible beat has spoken content (prep pipeline gap)
                _bd = (s.get("_beat_dialogue") or "").strip()
                if _bd:
                    parts.append(f'Speaking: "{_bd[:120]}"')

            # V29.7: Mood/atmosphere stripped from Kling prompt — it belongs in the first-frame
            # (nano), not in Kling's motion instruction. Mood stacking made prompts too dense
            # and caused Kling to rush through actions trying to hit every descriptor.

            # Presence indicator
            if len(all_chars) <= 1:
                parts.append("Alone.")
            if chars:
                parts.append("Face locked, body moves naturally. Natural asymmetric gaze with catch light in eyes, subtle micro-expressions.")

            # V36.1: OUTGOING REFRAME — appended to THIS shot so it ends toward the next angle.
            # Lookahead: flat list spans all groups — cross-group transitions included.
            # Appending (not prepending) means Kling receives the outgoing hint AFTER the beat
            # action — it shapes the end of the shot without fighting the chain start frame.
            if gen_mode == "chain":
                _cur_sid = s.get("shot_id", "")
                _cur_flat_idx = _shot_idx_map.get(_cur_sid, -1)
                if _cur_flat_idx >= 0 and _cur_flat_idx + 1 < len(_all_shots_flat):
                    _next_shot_type = (_all_shots_flat[_cur_flat_idx + 1].get("shot_type") or "").lower()
                else:
                    _next_shot_type = ""
                _reframe = _REFRAME_MAP.get((_cur_shot_type, _next_shot_type), "")
                if _reframe:
                    if (_cur_shot_type, _next_shot_type) in _AGGRESSIVE_TRANSITIONS:
                        _reframe = "[GENTLE] " + _reframe
                    parts.append(_reframe)
                    print(f"    [REFRAME→] {_cur_shot_type} → {_next_shot_type}: {_reframe}")

            prompt_text = " ".join(parts)[:460]  # 460 hard cap leaves room for @ElementN prepend

            # V37: CPC decontamination on Kling video prompt — same generic patterns that
            # produce frozen first frames also cause Kling to generate frozen/statue video.
            # Run AFTER joining parts but BEFORE @ElementN prepend so the 460-char budget
            # is not inflated by replacement text that then gets truncated.
            _kling_chars_k = s.get("characters") or []
            prompt_text = _cpc_decontaminate(
                prompt_text,
                character=_kling_chars_k[0] if _kling_chars_k else "",
                emotion=s.get("_emotional_state", "neutral"),
                beat_desc=s.get("_beat_action", ""),
            )
            if len(prompt_text) > 460:
                prompt_text = prompt_text[:460]

            # Ensure all elements are referenced (for chars without dialogue too)
            # E-shot guard: shots with characters=[] or _no_char_ref=True MUST NOT reference @ElementN
            # Prepending @Element1 to an empty-room B-roll prompt forces Kling to render characters.
            _shot_has_chars = bool(s.get("characters") or []) and not s.get("_no_char_ref")
            if _shot_has_chars:
                for j in range(len(elements)):
                    tag = f"@Element{j+1}"
                    if tag not in prompt_text:
                        prompt_text = f"{tag} " + prompt_text

            # V29.10: Hard enforce 512-char API limit after @ElementN prepend
            if len(prompt_text) > 512:
                prompt_text = prompt_text[:512]

            multi_prompt.append({"prompt": prompt_text, "duration": str(dur)})
            group_sids.append(s["shot_id"])

        total_dur = sum(int(mp["duration"]) for mp in multi_prompt)
        print(f"  [MULTISHOT] Group {gi+1}: {len(multi_prompt)} shots, {total_dur}s, {len(elements)} elements")
        for mp in multi_prompt:
            print(f"    {mp['duration']}s: {mp['prompt'][:80]}...")

        kling_args = {
            "start_image_url": start_url,
            "multi_prompt": multi_prompt,
            "aspect_ratio": "16:9",
            "negative_prompt": NEG,
            "cfg_scale": 0.5,
        }
        # E-shot guard: only add elements if at least one shot in this group has characters.
        # A group of pure E-shots (characters=[]) must run as environment-only Kling calls.
        # Passing elements to an E-shot group forces Kling to render character faces in B-roll.
        _group_has_chars = any(
            bool(s2.get("characters") or []) and not s2.get("_no_char_ref")
            for s2 in ([t[0] if isinstance(t, (list, tuple)) else t for t in group]
                       if isinstance(group, list) else [s for s in kling_shots
                        if s["shot_id"] in group_sids])
        )
        if elements and _group_has_chars:
            kling_args["elements"] = elements
        elif elements and not _group_has_chars:
            print(f"  [E-SHOT GUARD] Group {gi+1} {group_sids}: pure environment — elements withheld")

        # ── VVO PRE-FLIGHT: REJECT HUMAN FIGURES IN E-SHOTS ─────────────────────────────────
        # For pure environment groups (no characters), check the first frame BEFORE calling
        # Kling. If Gemini Vision detects any human figure in an E-shot's first frame →
        # REJECT: block Kling generation and mark the group contaminated for re-frame first.
        # NON-BLOCKING: any exception proceeds cleanly.
        _vvo_preflight_blocked = False
        if _VVO_AVAILABLE and not _group_has_chars:
            try:
                _vvo_sb = context.get("_story_bible") if context else None
                for _pf_s, _ in group:
                    _pf_sid  = _pf_s.get("shot_id", "?")
                    _pf_fp   = (all_frames or {}).get(_pf_sid) or first_frame_path
                    if _pf_fp and os.path.exists(_pf_fp):
                        _pf_result = _vvo_preflight_e_shot(_pf_fp, _pf_s, _vvo_sb)
                        if not _pf_result.passed:
                            print(
                                f"  [VVO PREFLIGHT] ❌ E-shot '{_pf_sid}' BLOCKED — "
                                f"human figures in first frame: {_pf_result.description[:120]}"
                            )
                            print(
                                f"  [VVO PREFLIGHT] Regen the first frame without people, "
                                f"then re-run --videos-only."
                            )
                            _pf_s["_vvo_preflight_rejected"] = True
                            _pf_s.update(_pf_result.regen_patch)
                            _arj_contaminated[gi] = True
                            _vvo_preflight_blocked = True
                        else:
                            print(f"  [VVO PREFLIGHT] ✓ {_pf_sid}: {_pf_result.description[:80]}")
            except Exception as _pf_err:
                print(f"  [VVO PREFLIGHT] exception (non-blocking): {_pf_err}")
        if _vvo_preflight_blocked:
            continue  # skip Kling call for this E-shot group
        # ─────────────────────────────────────────────────────────────────────────────────────

        # ── V36.5 PRE-GEN GATE — chain_intelligence_gate.validate_pre_generation ──────────
        # Validates each shot in this group before spending on Kling API.
        # On gate failure: logs error, marks group contaminated, skips generation unless --skip-gates.
        # NON-BLOCKING: any gate exception skips the check cleanly.
        _cig_pre_blocked = False
        if _CHAIN_GATE_AVAILABLE and not _SKIP_CHAIN_GATES:
            try:
                _cig_pre_errors_all = []
                for _cig_s, _ in group:
                    _pre_result = _cig_pre(_cig_s, _cig_scene_shots, context.get("_story_bible") if context else None)
                    if not _pre_result.passed:
                        _cig_pre_errors_all.extend(_pre_result.errors)
                        _cig_s["_gate_pre_errors"] = _pre_result.errors
                    if _pre_result.warnings:
                        for _w in _pre_result.warnings:
                            print(f"  [CHAIN_GATE][PRE][WARN] {_w[:120]}")
                    _cig_audit_entries.append({
                        "phase": "pre_gen",
                        "group": gi + 1,
                        "shot_id": _cig_s.get("shot_id", "?"),
                        "passed": _pre_result.passed,
                        "errors": _pre_result.errors,
                        "warnings": _pre_result.warnings,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    })
                if _cig_pre_errors_all:
                    for _cig_err in _cig_pre_errors_all:
                        print(f"  [CHAIN_GATE][PRE][BLOCK] {_cig_err[:150]}")
                    print(f"  [CHAIN_GATE] Group {gi+1} PRE-GEN BLOCKED ({len(_cig_pre_errors_all)} error(s)) — skipping Kling call")
                    _arj_contaminated[gi] = True
                    _cig_pre_blocked = True
            except Exception as _cig_pre_err:
                print(f"  [CHAIN_GATE] PRE-GEN gate exception (non-blocking): {_cig_pre_err}")
        if _cig_pre_blocked:
            continue  # skip this group's Kling call
        # ─────────────────────────────────────────────────────────────────────────────────────

        t0 = time.time()
        try:
            result = fal_client.subscribe(KLING, arguments=kling_args)
            elapsed = time.time() - t0
            _track_cost("kling")
            if _vbt:
                _vbt.track_kling_call()  # track primary Kling call in episode budget

            vid_url = result.get("video", {}).get("url")
            if vid_url:
                import urllib.request
                # Name by first shot in group
                outname = f"multishot_g{gi+1}_{group_sids[0]}.mp4"
                outpath = os.path.join(outdir, outname)
                try:
                    urllib.request.urlretrieve(vid_url, outpath)
                except Exception as dl_err:
                    print(f"  [MULTISHOT] Group {gi+1}: DOWNLOAD FAILED — {dl_err}")
                    print(f"  ⛔ Cannot proceed — video URL unreachable. Fix and re-run.")
                    break
                # Validate download is a real video (< 5000 bytes = truncated/error page)
                dl_size = os.path.getsize(outpath) if os.path.exists(outpath) else 0
                if dl_size < 5000:
                    print(f"  [MULTISHOT] Group {gi+1}: INVALID DOWNLOAD — {dl_size} bytes (expected >5KB). URL may be expired.")
                    print(f"  ⛔ Aborting chain — do not proceed with corrupt video.")
                    break
                mb = os.path.getsize(outpath) / (1024*1024)
                print(f"  [MULTISHOT] Group {gi+1}: OK — {mb:.1f}MB — {elapsed:.1f}s")
                # Map all sids in this group to the same video
                for sid in group_sids:
                    results[sid] = outpath

                # ── V36.5 POST-GEN GATE — chain_intelligence_gate.validate_post_generation ──
                # Runs AFTER download, BEFORE ARJ. Checks: duration, frozen dialogue, arc quality,
                # action truncation, chain contract handoff.
                # On failure: marks group contaminated (blocks end-frame chain propagation).
                # Extracts ChainContract from last frame → passed as prev_contract to NEXT group.
                # NON-BLOCKING: any exception proceeds cleanly.
                if _CHAIN_GATE_AVAILABLE and not _SKIP_CHAIN_GATES:
                    try:
                        _cig_repr_shot = group[0][0] if isinstance(group[0], (list, tuple)) else group[0]
                        _post_result = _cig_post(
                            shot=_cig_repr_shot,
                            video_path=outpath,
                            prev_contract=_cig_prev_contract,
                        )
                        _cig_audit_entries.append({
                            "phase": "post_gen",
                            "group": gi + 1,
                            "shot_id": _cig_repr_shot.get("shot_id", "?"),
                            "passed": _post_result.passed,
                            "errors": _post_result.errors,
                            "warnings": _post_result.warnings,
                            "regen_suggestion": _post_result.regen_suggestion,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        })
                        if _post_result.warnings:
                            for _w in _post_result.warnings:
                                print(f"  [CHAIN_GATE][POST][WARN] {_w[:120]}")
                        if not _post_result.passed:
                            for _e in _post_result.errors:
                                print(f"  [CHAIN_GATE][POST][FAIL] {_e[:150]}")
                            if _post_result.regen_suggestion:
                                print(f"  [CHAIN_GATE][POST] Suggestion: {_post_result.regen_suggestion}")
                            # Mark contaminated — ARJ contamination gate will block end-frame chain
                            _arj_contaminated[gi] = True
                            print(f"  [CHAIN_GATE] Group {gi+1} POST-GEN FAILED — end-frame chain blocked")
                        else:
                            print(f"  [CHAIN_GATE][POST] ✓ Group {gi+1} passed")
                        # Extract chain contract for next group's position handoff
                        _cig_prev_contract = _cig_contract(outpath, _cig_repr_shot)
                    except Exception as _cig_post_err:
                        print(f"  [CHAIN_GATE] POST-GEN gate exception (non-blocking): {_cig_post_err}")
                # ─────────────────────────────────────────────────────────────────────────────

                # ── VIDEO VISION OVERSIGHT (VVO) — character bleed + frozen + dialogue sync ─
                # Runs AFTER chain_gate, BEFORE ARJ. Three context-aware checks:
                #   CHARACTER_BLEED: unexpected people in E-shots (genre/location aware)
                #   FROZEN_FRAME:    pixel-diff + Gemini — all-static video detected
                #   DIALOGUE_SYNC:   mouth movement verification on speaking shots
                # On any FAIL → marks group contaminated (blocks end-frame chain propagation).
                # NON-BLOCKING: any exception proceeds cleanly.
                if _VVO_AVAILABLE:
                    try:
                        _vvo_sb = context.get("_story_bible") if context else None
                        _vvo_shot = group[0][0] if isinstance(group[0], (list, tuple)) else group[0]
                        _vvo_report = _vvo_run(outpath, _vvo_shot, _vvo_sb)
                        if _vbt:
                            _vbt.track_gemini_call("vvo_frame_check")
                        if not _vvo_report.passed:
                            _sid_vvo = _vvo_shot.get("shot_id", "?")
                            print(f"  [VVO] ⚠️  Group {gi+1} ({_sid_vvo}): "
                                  f"{_vvo_report.failure_summary[:120]}")
                            for _vvo_r in _vvo_report.oversight_results:
                                if not _vvo_r.passed:
                                    print(f"      [{_vvo_r.check}] {_vvo_r.description[:100]}")
                            # ── VVO REGEN PATH (V37) — budget-gated, max 1 retry per shot ──────────
                            # Grade F only: VVO fail = hard reject, always warrants regen attempt.
                            # Mirrors ARJ budget guard pattern: per-shot cap → scene cap → regen.
                            # If any gate blocks: mark contaminated (same as before this fix).
                            _vvo_regen_ok = False
                            if _vbt and _vbt.can_regen_shot(_sid_vvo) and _vbt.scene_budget_ok():
                                _vvo_regen_ok = True
                            elif not _vbt and not _arj_regens_used.get(gi, False):
                                _vvo_regen_ok = True
                            if _vvo_regen_ok:
                                _arj_regens_used[gi] = _arj_regens_used.get(gi, 0) + 1
                                if _vbt:
                                    _vbt.consume_regen(_sid_vvo)
                                _vvo_rn = _vbt.regen_count(_sid_vvo) if _vbt else _arj_regens_used[gi]
                                _vvo_rm = _vbt._cfg["max_regen_per_shot"] if _vbt else 1
                                _vvo_patch = getattr(_vvo_report, "regen_patch", {}) or {}
                                print(f"  [VVO] Regen {_vvo_rn}/{_vvo_rm} for {_sid_vvo}: "
                                      f"{_vvo_report.failure_summary[:80]}")
                                # Rebuild shots with VVO regen patch applied
                                _vvo_regen_shots = []
                                for _vvo_si in group:
                                    _vvo_s = _vvo_si[0] if isinstance(_vvo_si, (list, tuple)) else _vvo_si
                                    _vvo_sm = dict(_vvo_s)
                                    _vvo_sm.update(_vvo_patch)
                                    _vvo_sm["_vvo_regen"] = True
                                    _vvo_regen_shots.append(_vvo_sm)
                                _vvo_mp_regen = []
                                for _vvo_s in _vvo_regen_shots:
                                    try:
                                        from kling_prompt_compiler import compile_video_for_kling as _ckvk_vvo  # type: ignore
                                        _vvo_pt = _ckvk_vvo(_vvo_s, mode="lite")
                                    except Exception:
                                        _vvo_pt = (
                                            _vvo_s.get("_beat_action") or
                                            _vvo_s.get("description") or
                                            _vvo_s.get("shot_id", "")
                                        )[:512]
                                    _vvo_dur = max(5, min(int(str(_vvo_s.get("duration", 5)).strip()), 10))
                                    _vvo_mp_regen.append({"prompt": _vvo_pt[:512], "duration": str(_vvo_dur)})
                                _vvo_regen_args = {
                                    "start_image_url": start_url,
                                    "multi_prompt":    _vvo_mp_regen,
                                    "aspect_ratio":    "16:9",
                                    "negative_prompt": NEG,
                                    "cfg_scale":       0.5,
                                }
                                if elements and _group_has_chars:
                                    _vvo_regen_args["elements"] = elements
                                try:
                                    _vvo_regen_result = fal_client.subscribe(KLING, arguments=_vvo_regen_args)
                                    _vvo_regen_url = _vvo_regen_result.get("video", {}).get("url")
                                    if _vvo_regen_url:
                                        _vvo_regen_path = outpath.replace(".mp4", "_vvo_regen.mp4")
                                        import urllib.request as _ureq_vvo
                                        _ureq_vvo.urlretrieve(_vvo_regen_url, _vvo_regen_path)
                                        if os.path.exists(_vvo_regen_path) and os.path.getsize(_vvo_regen_path) > 5000:
                                            os.replace(_vvo_regen_path, outpath)
                                            _track_cost("kling")
                                            if _vbt:
                                                _vbt.track_kling_call()
                                            print(f"  [VVO] ✓ Regen success — group {gi+1} video replaced")
                                        else:
                                            print(f"  [VVO] ✗ Regen download invalid — keeping original")
                                            _arj_contaminated[gi] = True
                                            print(f"  [VVO] Group {gi+1} OVERSIGHT FAILED — end-frame chain blocked")
                                    else:
                                        print(f"  [VVO] ✗ Regen: no URL in response — keeping original")
                                        _arj_contaminated[gi] = True
                                        print(f"  [VVO] Group {gi+1} OVERSIGHT FAILED — end-frame chain blocked")
                                except Exception as _vvo_regen_err:
                                    print(f"  [VVO] ✗ Regen FAILED: {_vvo_regen_err} — keeping original")
                                    _arj_contaminated[gi] = True
                                    print(f"  [VVO] Group {gi+1} OVERSIGHT FAILED — end-frame chain blocked")
                            else:
                                _arj_contaminated[gi] = True
                                print(f"  [VVO] Group {gi+1} OVERSIGHT FAILED — end-frame chain blocked")
                        else:
                            _sid_vvo = _vvo_shot.get("shot_id", "?")
                            checks_run = [r.check for r in _vvo_report.oversight_results]
                            print(f"  [VVO] ✓ {_sid_vvo} passed ({', '.join(checks_run)})")
                    except Exception as _vvo_err:
                        print(f"  [VVO] oversight exception (non-blocking): {_vvo_err}")
                # ─────────────────────────────────────────────────────────────────────────────

                # ── POST-VIDEO QUALITY GATE (V36.3) — per-group ARJ + contamination gate ─
                # AutoRevisionJudge: 8-dimension video quality check AFTER Kling download.
                # If REJECT → one regen of this group with diagnostic injection.
                # V36.3: If REJECT persists after regen → _arj_contaminated[gi] = True
                #        → chain gate blocks this end-frame from propagating to next shot.
                # Budget: 1 regen per group (conservative — Kling videos cost ~$0.35/10s).
                # NON-BLOCKING: any exception → video passes through unchanged.
                if _ARJ_AVAILABLE and cast_map_for_arj:
                    try:
                        _arj_judge = AutoRevisionJudge()
                        # group is a list of tuples (shot_dict, ...) — unpack [0] to get the dict
                        _arj_repr_shot = (group[0][0] if isinstance(group[0], (list, tuple)) else group[0]) if group else {}
                        _arj_next_raw  = group[1] if len(group) > 1 else None
                        _arj_next      = (_arj_next_raw[0] if isinstance(_arj_next_raw, (list, tuple)) else _arj_next_raw)
                        _arj_verdict   = _arj_judge.judge(
                            outpath, _arj_repr_shot, cast_map_for_arj,
                            next_shot=_arj_next,
                        )
                        _arj_icon = {"APPROVE": "✅", "WARN": "⚠️", "REJECT": "❌"}.get(
                            _arj_verdict.verdict, "?"
                        )
                        # V36.3: Log semantic observations to shots for post-run analysis
                        # V36.3 FIX: VideoVerdict uses .overall (not .overall_score)
                        # and .dimensions dict (not .dim_observations / .worst_failure)
                        _arj_overall_val = getattr(_arj_verdict, 'overall', 0.0)
                        _arj_obs = {}
                        _arj_worst = ""
                        _dims = getattr(_arj_verdict, 'dimensions', {}) or {}
                        if _dims:
                            for _dk, _dv in _dims.items():
                                _obs_text = getattr(_dv, 'observation', '') if hasattr(_dv, 'observation') else str(_dv)
                                if _obs_text:
                                    _arj_obs[_dk] = _obs_text
                        _hard_rej = getattr(_arj_verdict, 'hard_rejects', []) or []
                        if _hard_rej:
                            _arj_worst = ", ".join(str(h) for h in _hard_rej[:3])
                        if _arj_obs or _arj_overall_val > 0:
                            for _arj_si in group:
                                _arj_s = _arj_si[0] if isinstance(_arj_si, (list, tuple)) else _arj_si
                                _arj_s["_arj_observations"] = {k: v[:200] for k, v in _arj_obs.items() if v}
                                _arj_s["_arj_worst_failure"] = str(_arj_worst)[:200]
                                _arj_s["_arj_overall"] = round(_arj_overall_val, 3)
                                _arj_s["_arj_verdict"] = _arj_verdict.verdict
                        print(
                            f"  [POST-VIDEO-GATE] {_arj_icon} Group {gi+1} "
                            f"overall={_arj_overall_val:.2f} "
                            f"verdict={_arj_verdict.verdict}"
                        )
                        if _arj_obs:
                            for _dim, _obs_txt in _arj_obs.items():
                                if _obs_txt:
                                    print(f"    [{_dim}] {_obs_txt[:100]}")
                        if _arj_verdict.should_reject:
                            # ── VISION BUDGET GUARDRAILS (V5.0) ─────────────────────
                            # All gates must pass before a regen Kling call is issued.
                            # On any block: shot is flagged for human review, chain
                            # is stopped if stop_chain_on_budget_exceeded=True.
                            _arj_shot_id_key = _arj_repr_shot.get("shot_id", str(gi))
                            _arj_has_hard_rejects = bool(getattr(_arj_verdict, 'hard_rejects', []) or [])

                            # GATE 1 — Grade-based filter
                            # Grade F: hard_rejects present OR overall < 0.30 → regen
                            # Grade D: overall 0.30–0.52 with no hard rejects → advisory only
                            _arj_grade_is_f = (
                                _vbt.should_regen_on_grade(_arj_has_hard_rejects, _arj_overall_val)
                                if _vbt else True
                            )
                            if not _arj_grade_is_f:
                                print(
                                    f"  [POST-VIDEO-GATE] 📋 Grade D "
                                    f"(overall={_arj_overall_val:.2f}, no hard rejects) — "
                                    f"advisory flag only, regen skipped (budget preserved)"
                                )
                            # GATE 2 — Per-shot regen cap (max_regen_per_shot)
                            elif _vbt and not _vbt.can_regen_shot(_arj_shot_id_key):
                                print(
                                    f"  [VISION BUDGET] 🛑 {_arj_shot_id_key}: regen cap reached "
                                    f"({_vbt.regen_count(_arj_shot_id_key)}/"
                                    f"{_vbt._cfg['max_regen_per_shot']} max) — "
                                    f"flagged for human review, no further regen"
                                )
                                _arj_contaminated[gi] = True
                                if _vbt.stop_chain_on_exceeded():
                                    print(f"  [VISION BUDGET] ⛓️  Chain stopped at group {gi+1} — per-shot cap")
                            # GATE 3 — Scene-level Kling budget
                            elif _vbt and not _vbt.scene_budget_ok():
                                print(
                                    f"  [VISION BUDGET] 🛑 Scene Kling cap exceeded "
                                    f"({_vbt.budget_summary()}) — "
                                    f"regen blocked, flagging group {gi+1}"
                                )
                                _arj_contaminated[gi] = True
                                if _vbt.stop_chain_on_exceeded():
                                    print(f"  [VISION BUDGET] ⛓️  Chain stopped at group {gi+1} — scene cap")
                            # GATE 4 — Episode-level Kling budget
                            elif _vbt and not _vbt.episode_budget_ok():
                                print(
                                    f"  [VISION BUDGET] 🛑 Episode Kling cap exceeded "
                                    f"({_vbt.budget_summary()}) — "
                                    f"halting all regens for remainder of episode"
                                )
                                _arj_contaminated[gi] = True
                                if _vbt.stop_chain_on_exceeded():
                                    print(f"  [VISION BUDGET] ⛓️  Chain stopped at group {gi+1} — episode cap")
                            # LEGACY fallback: no tracker available, honour once-only boolean
                            elif not _vbt and _arj_regens_used.get(gi, False):
                                _arj_contaminated[gi] = True
                                print(
                                    f"  [CONTAMINATION-GATE] ⚠️ Group {gi+1} CONTAMINATED "
                                    f"(budget exhausted) — end-frame will NOT chain"
                                )
                            else:
                                # ── ALL GATES PASSED — REGEN APPROVED ────────────────
                                _arj_regens_used[gi] = _arj_regens_used.get(gi, 0) + 1
                                if _vbt:
                                    _vbt.consume_regen(_arj_shot_id_key)
                                _arj_regen_n = _vbt.regen_count(_arj_shot_id_key) if _vbt else _arj_regens_used[gi]
                                _arj_regen_max = _vbt._cfg["max_regen_per_shot"] if _vbt else 1
                                _arj_instr = _arj_verdict.regen_instruction or ""
                                print(
                                    f"  [POST-VIDEO-GATE] REJECT → regen group {gi+1} "
                                    f"(attempt {_arj_regen_n}/{_arj_regen_max}): "
                                    f"{_arj_instr[:120]}..."
                                )
                                # Inject diagnostic into each shot in the group
                                _arj_fixed_shots = []
                                for _arj_si in group:
                                    _arj_s = _arj_si[0] if isinstance(_arj_si, (list, tuple)) else _arj_si
                                    _arj_sm = dict(_arj_s)
                                    _arj_sm["_pvg_diagnostic"] = (
                                        f"[POST-VIDEO-REGEN] {_arj_instr}"
                                    )
                                    _arj_fixed_shots.append(_arj_sm)
                                # Rebuild multi_prompt with injected diagnostics and regen
                                _arj_mp2  = []
                                for _arj_s in _arj_fixed_shots:
                                    try:
                                        from kling_prompt_compiler import compile_video_for_kling as _ckvk  # type: ignore
                                        _arj_pt = _ckvk(_arj_s, mode="lite")
                                    except Exception:
                                        _arj_pt = (
                                            _arj_s.get("_beat_action") or
                                            _arj_s.get("description") or
                                            _arj_s.get("shot_id", "")
                                        )[:512]
                                    _arj_dur = max(5, min(int(str(_arj_s.get("duration", 5)).strip()), 10))
                                    _arj_mp2.append({"prompt": _arj_pt[:512], "duration": str(_arj_dur)})
                                _arj_args2 = {
                                    "start_image_url": start_url,
                                    "multi_prompt":   _arj_mp2,
                                    "aspect_ratio":   "16:9",
                                    "negative_prompt": NEG,
                                    "cfg_scale":      0.5,
                                }
                                if elements:
                                    _arj_args2["elements"] = elements
                                try:
                                    _arj_result2 = fal_client.subscribe(KLING, arguments=_arj_args2)
                                    _arj_url2 = _arj_result2.get("video", {}).get("url")
                                    if _arj_url2:
                                        _arj_outpath2 = outpath.replace(".mp4", "_arj_regen.mp4")
                                        import urllib.request as _ureq2
                                        _ureq2.urlretrieve(_arj_url2, _arj_outpath2)
                                        if os.path.exists(_arj_outpath2) and os.path.getsize(_arj_outpath2) > 5000:
                                            os.replace(_arj_outpath2, outpath)
                                            _track_cost("kling")
                                            if _vbt:
                                                _vbt.track_kling_call()  # track regen Kling call
                                            print(
                                                f"  [POST-VIDEO-GATE] ✓ regen success "
                                                f"— group {gi+1} video replaced"
                                            )
                                        else:
                                            print(f"  [POST-VIDEO-GATE] ✗ regen download invalid — keeping original")
                                            _arj_contaminated[gi] = True
                                            print(f"  [CONTAMINATION-GATE] ⚠️ Group {gi+1} CONTAMINATED — end-frame will NOT chain")
                                except Exception as _arj_regen_err:
                                    print(f"  [POST-VIDEO-GATE] ✗ regen FAILED: {_arj_regen_err} — keeping original")
                                    _arj_contaminated[gi] = True
                                    print(f"  [CONTAMINATION-GATE] ⚠️ Group {gi+1} CONTAMINATED — end-frame will NOT chain")
                    except Exception as _arj_err:
                        print(f"  [POST-VIDEO-GATE] Gate error ({_arj_err}) — skipping")
                # ────────────────────────────────────────────────────────────────────

                # V31.1 END-FRAME CHAIN WITH REFRAME:
                # Extract last frame → reframe to next shot's angle via nano → upload → next group starts here
                #
                # WHY: Raw end-frame chaining without reframe = Kling starts from the SAME
                # camera angle and just continues with different emotion. The "cut" never
                # happens visually — it's the same OTS shoulder with a mood change, not an
                # editorial cut. By reframing the end-frame to the NEXT shot's composition
                # BEFORE feeding it as start_url, Kling receives a frame that already
                # establishes the correct angle, so it generates from the right visual POV.
                #
                # PARALLEL MODE: skip entirely — each shot resolves its own start_url at the
                # top of the loop from all_frames. No chaining, no reframing. Independent shots.
                if gen_mode == "chain" and gi < len(groups) - 1:  # only chain if more groups follow
                    # V36.3 CONTAMINATION GATE: if ARJ rejected this group and regen failed,
                    # do NOT chain this end-frame — it carries the defect forward.
                    # Instead, next group will use its own first_frame from all_frames (fallback).
                    if _arj_contaminated.get(gi, False):
                        print(f"  [CONTAMINATION-GATE] 🛑 Group {gi+1}: CHAIN BLOCKED — next shot uses its own first frame")
                        # Find next group's lead shot and resolve its first frame as start_url
                        _contam_next_sid = groups[gi + 1][0][0].get("shot_id", "") if groups[gi + 1] else ""
                        _contam_fallback = all_frames.get(_contam_next_sid, "")
                        if _contam_fallback and os.path.exists(_contam_fallback):
                            _contam_url = upload(_contam_fallback)
                            if _contam_url:
                                start_url = _contam_url
                                print(f"  [CONTAMINATION-GATE] ✓ Fallback to {_contam_next_sid} first frame — chain resumes clean")
                            else:
                                print(f"  [CONTAMINATION-GATE] ⚠️ Upload failed — chain continues with last known good start_url")
                        else:
                            print(f"  [CONTAMINATION-GATE] ⚠️ No first frame for {_contam_next_sid} — chain continues with last known good start_url")
                        continue  # skip end-frame extraction + reframe for this contaminated group
                    chain_local = outpath.replace(".mp4", "_lastframe.jpg")
                    chained = extract_last_frame(outpath, chain_local)

                    # ── VVO CHECKPOINT B (V36.5+): END-FRAME CHAIN QUALITY GATE ──────────────
                    # Fires at EVERY checkpoint — validates the extracted end-frame BEFORE it
                    # becomes the next shot's start_url. A corrupted/blank chain frame silently
                    # poisons every downstream shot in the scene.
                    # Check 1: File size > 2KB (< 2KB = ffmpeg extraction failed or blank)
                    # Check 2: VVO chain transition check (Gemini Vision, if available + budget)
                    # On failure: blocks this chain frame from becoming start_url → falls back
                    # to next shot's own first frame (same path as ARJ contamination fallback).
                    # NON-BLOCKING: any exception proceeds cleanly.
                    _chain_b_valid = True
                    if chained and os.path.exists(chain_local):
                        _chain_b_size = os.path.getsize(chain_local)
                        if _chain_b_size < 2000:
                            print(f"  [VVO-B] ⚠️  Group {gi+1}: end-frame too small ({_chain_b_size}B) — chain propagation blocked")
                            _chain_b_valid = False
                            chained = False  # treat as extraction failure → fallback path below
                        else:
                            print(f"  [VVO-B] ✓ Group {gi+1}: end-frame valid ({_chain_b_size//1024}KB) — chain OK")
                            # Optional: VVO chain transition check (Gemini, budget-gated)
                            if _VVO_AVAILABLE and _vbt:
                                try:
                                    _prev_vid = outpath
                                    _next_shot_for_vvo = groups[gi + 1][0][0] if gi + 1 < len(groups) else None
                                    if _next_shot_for_vvo:
                                        _chain_result = _vvo_chain_check(_prev_vid, chain_local, _next_shot_for_vvo)
                                        if _chain_result.get("jarring"):
                                            print(f"  [VVO-B] ⚠️  Group {gi+1}: jarring chain transition detected — {_chain_result.get('notes', '')[:100]}")
                                except Exception as _vvo_b_chain_err:
                                    pass  # budget check or Gemini unavailable — non-blocking
                    elif chained and not os.path.exists(chain_local):
                        print(f"  [VVO-B] ⚠️  Group {gi+1}: end-frame path does not exist after extraction")
                        _chain_b_valid = False
                        chained = False
                    # If chain invalidated by VVO-B, fall back to next shot's first frame (same as contamination gate)
                    if not _chain_b_valid and gi + 1 < len(groups):
                        _vvob_next_sid = groups[gi + 1][0][0].get("shot_id", "") if groups[gi + 1] else ""
                        _vvob_fallback = (all_frames or {}).get(_vvob_next_sid, "")
                        if _vvob_fallback and os.path.exists(_vvob_fallback):
                            _vvob_url = upload(_vvob_fallback)
                            if _vvob_url:
                                start_url = _vvob_url
                                print(f"  [VVO-B] ✓ Chain fallback: using {_vvob_next_sid} first frame as start_url")
                        continue  # skip reframe for this group
                    # ─────────────────────────────────────────────────────────────────────────

                    if chained:
                        # Determine if a reframe is needed (angle category change between shots)
                        _curr_shot = group[0][0]
                        _next_shot = groups[gi + 1][0][0]
                        _curr_type = (_curr_shot.get("shot_type") or "").lower()
                        _next_type = (_next_shot.get("shot_type") or "").lower()

                        def _angle_cat(st):
                            if st in ("close_up", "reaction", "medium_close", "mcu", "ecu"): return "CLOSE"
                            if st in ("ots_a", "ots_b", "ots"): return "OTS"
                            if st in ("establishing", "wide", "closing"): return "WIDE"
                            return "MEDIUM"  # medium, two_shot, insert, default

                        _curr_cat = _angle_cat(_curr_type)
                        _next_cat = _angle_cat(_next_type)
                        _needs_reframe = (_curr_cat != _next_cat) or (_curr_type != _next_type)

                        _reframe_success = False
                        if _needs_reframe and cast_map_for_arj:
                            # Build reframe prompt for next shot's composition
                            _focal_map = {
                                "close_up":     "face fills 80% of frame, background fully blurred bokeh, extreme tight 85mm f/1.4",
                                "medium_close": "head and shoulders fill frame, soft background, 50mm f/2.0",
                                "ots_a":        "over-the-shoulder, listener shoulder FRAME-LEFT foreground, speaker FRAME-RIGHT facing camera, 50mm",
                                "ots_b":        "over-the-shoulder reversed, listener shoulder FRAME-RIGHT foreground, speaker FRAME-LEFT facing camera, 50mm",
                                "two_shot":     "two-shot, confrontational blocking, both figures in frame, speaker LEFT facing right, listener RIGHT facing left, 35mm",
                                "medium":       "medium shot waist-up, room context visible behind characters, 35mm",
                                "wide":         "wide shot full room geography visible, deep depth of field, 24mm",
                                "closing":      "closing wide pull-back, characters small in environment, deep DOF, 24mm",
                                "reaction":     "tight reaction close-up, eyes and brow visible, natural breathing, 85mm",
                            }
                            _framing = _focal_map.get(_next_type, "medium shot, 35mm")

                            # Character appearance block for identity continuity
                            _next_chars = _next_shot.get("characters") or []
                            _char_blocks = []
                            for _nc in _next_chars[:2]:
                                _nc_entry = cast_map_for_arj.get(_nc, {}) if isinstance(cast_map_for_arj, dict) else {}
                                _nc_app = _nc_entry.get("appearance", "") if isinstance(_nc_entry, dict) else ""
                                if _nc_app:
                                    _char_blocks.append(f"[CHARACTER: {_nc_app[:80]}]")

                            _atm = (_next_shot.get("_beat_atmosphere") or "").strip()
                            # V36.4 FIX: Inject Room DNA into reframe prompt to prevent
                            # environment drift across chain. Without this, each reframe
                            # dilutes the room until it becomes a blank white void.
                            _rf_room_dna = ""
                            if context and isinstance(context, dict):
                                _rf_room_dna = (context.get("_room_dna") or "").strip()

                            # V36.5: Arc-aware reframe — carry directive tells the reframe
                            # what the chain expects at this position in the emotional arc
                            _next_arc = _next_shot.get("_arc_position", "ESCALATE")
                            _next_carry = _next_shot.get("_arc_carry_directive", "")
                            _arc_reframe_hint = ""
                            if _next_arc == "RESOLVE":
                                _arc_reframe_hint = "Scene closing — maintain room fully, allow wider framing. "
                            elif _next_arc == "PIVOT":
                                _arc_reframe_hint = "Emotional turning point — room holds, intensity shifts. "
                            elif _next_arc == "ESCALATE":
                                _arc_reframe_hint = "Carry the room exactly from opening. "

                            # V36.5.1: BLOCKING CARRY — inject spatial arrangement from previous shot
                            # so the reframe knows WHERE characters are, not just WHO they are
                            _blocking_carry = (_next_shot.get("_blocking_carry") or "").strip()
                            _blocking_hint = f"[BLOCKING: {_blocking_carry[:80]}] " if _blocking_carry else ""

                            _reframe_prompt = (
                                f"REFRAME TO: {_framing}. "
                                + (" ".join(_char_blocks) + " " if _char_blocks else "")
                                + (_blocking_hint)
                                + (f"{_rf_room_dna} " if _rf_room_dna else "")
                                + (f"[ATMOSPHERE: {_atm[:50]}] " if _atm else "")
                                + (_arc_reframe_hint if _arc_reframe_hint else "")
                                + "Same lighting, same room architecture, same people, new camera angle. "
                                + "FACE IDENTITY LOCK: facial features unchanged. "
                                + "ROOM LOCK: maintain all architectural elements from source frame."
                            )[:900]

                            # Upload char ref for identity lock during reframe
                            _rf_image_urls = [chain_local]  # base = last frame
                            _rf_char_ref = get_char_ref(cast_map_for_arj, _next_chars[0]) if _next_chars else None
                            _rf_ref_url = None
                            if _rf_char_ref:
                                _rf_ref_url = upload(_rf_char_ref)
                                if _rf_ref_url:
                                    _rf_image_urls = [chain_local, _rf_ref_url]

                            # V36.4: Upload location master as visual room anchor
                            # Slot order: [last_frame, char_ref, loc_master]
                            # Slot 3 = lower attention than char ref but still anchors architecture
                            _rf_loc_url = None
                            if context and isinstance(context, dict):
                                _rf_loc_path = context.get("_location_master_path")
                                if _rf_loc_path and os.path.exists(_rf_loc_path):
                                    _rf_loc_url = upload(_rf_loc_path)
                                    if _rf_loc_url:
                                        print(f"  [CHAIN-REFRAME] Location master anchored: {os.path.basename(_rf_loc_path)}")

                            try:
                                # Upload the raw last frame first for nano input
                                _rf_last_uploaded = upload(chain_local)
                                if _rf_last_uploaded:
                                    _rf_urls_final = [_rf_last_uploaded]
                                    if _rf_ref_url:
                                        _rf_urls_final.append(_rf_ref_url)
                                    if _rf_loc_url:
                                        _rf_urls_final.append(_rf_loc_url)  # V36.4: room anchor at slot 3
                                    _rf_result = fal_client.subscribe(
                                        NANO_EDIT,
                                        arguments={
                                            "prompt": _reframe_prompt,
                                            "image_urls": _rf_urls_final,
                                            "aspect_ratio": "16:9",
                                            "resolution": "1K",
                                            "num_images": 1,
                                            "safety_tolerance": "5",
                                            "output_format": "jpeg",
                                        }
                                    )
                                    _rf_imgs = _rf_result.get("images", [])
                                    if _rf_imgs:
                                        _rf_url = _rf_imgs[0].get("url", "")
                                        _rf_local = chain_local.replace("_lastframe.jpg", "_reframed.jpg")
                                        import urllib.request as _ureqrf
                                        _ureqrf.urlretrieve(_rf_url, _rf_local)
                                        if os.path.exists(_rf_local) and os.path.getsize(_rf_local) > 1000:
                                            _track_cost("nano")
                                            chained = _rf_local
                                            _reframe_success = True
                                            print(f"  [CHAIN-REFRAME] {_curr_cat}({_curr_type}) → {_next_cat}({_next_type}): reframed ✓")
                                        else:
                                            print(f"  [CHAIN-REFRAME] Download tiny — using raw last frame")
                                    else:
                                        print(f"  [CHAIN-REFRAME] No image returned — using raw last frame")
                            except Exception as _rf_err:
                                print(f"  [CHAIN-REFRAME] Reframe failed ({_rf_err}) — using raw last frame")

                        if not _needs_reframe:
                            print(f"  [CHAIN] Same angle ({_curr_type}→{_next_type}) — chaining raw last frame ✓")

                        # Upload the (reframed or raw) chain frame as next group's start
                        chained_url = upload(chained)
                        if chained_url:
                            start_url = chained_url
                            _chain_label = "reframed" if _reframe_success else "raw"
                            print(f"  [CHAIN] Group {gi+1} → {_chain_label} chain frame → group {gi+2} start locked ✓")
                        else:
                            print(f"  ⛔ CHAIN BROKEN at Group {gi+1}: chain-frame upload failed — halting to prevent drift")
                            _chain_break_group = gi
                            break
                    else:
                        print(f"  ⛔ CHAIN BROKEN at Group {gi+1}: last-frame extract failed — halting to prevent drift")
                        _chain_break_group = gi
                        break
            else:
                # V37.1: No video URL = Kling call failed for this group.
                # If downstream groups are chain-dependent, they cannot proceed.
                # Halt and escalate — do NOT silently continue with unchained frames.
                _group_strategy = group[0][0].get("_gen_strategy", "") if group else ""
                _has_chain_deps = any(
                    groups[_gi2][0][0].get("_gen_strategy") == "CHAIN"
                    for _gi2 in range(gi + 1, len(groups))
                    if groups[_gi2]
                ) if gi + 1 < len(groups) else False
                print(f"  [MULTISHOT] Group {gi+1}: FAIL — no video URL")
                if gen_mode == "chain" and _has_chain_deps:
                    print(f"  ⛔ CHAIN BROKEN at Group {gi+1}: video generation failed — downstream shots need this end-frame")
                    _chain_break_group = gi
                    break
        except Exception as e:
            print(f"  [MULTISHOT] Group {gi+1}: FAILED — {e}")
            print(f"  ⛔ NO FALLBACK. Fix the issue and re-run. Do not generate wrong output.")
            # NO FALLBACK. Stop. Report. Fix. Re-run.
            if gen_mode == "chain":
                _chain_break_group = gi
                break

    # V37.1: HUMAN_ESCALATION — if chain broke, mark all downstream chain shots.
    # These shots did NOT get videos because their start_image was never available.
    # Setting _approval_status=HUMAN_ESCALATION surfaces them in the UI as needing
    # deliberate human intervention. No automatic fallback frame is generated.
    if _chain_break_group is not None:
        _escalated = 0
        for _gi2 in range(_chain_break_group + 1, len(groups)):
            for _esc_shot, _ in groups[_gi2]:
                _esc_strategy = _esc_shot.get("_gen_strategy", "")
                if _esc_strategy == "CHAIN":
                    _esc_sid = _esc_shot.get("shot_id", "?")
                    _esc_shot["_approval_status"] = "HUMAN_ESCALATION"
                    _esc_shot["_chain_break_reason"] = (
                        f"Chain broke at group {_chain_break_group + 1} — "
                        f"end-frame unavailable. Re-run after fixing group {_chain_break_group + 1}."
                    )
                    print(f"  [ESCALATION] {_esc_sid}: HUMAN_ESCALATION — chain broke at group {_chain_break_group + 1}")
                    _escalated += 1
        if _escalated:
            print(f"  ⚠️  {_escalated} chain-dependent shot(s) flagged HUMAN_ESCALATION — fix group {_chain_break_group + 1} and re-run --videos-only")

    # V36.5: Write gate_audit.json — all pre/post gate verdicts for this scene run
    if _cig_audit_entries:
        try:
            _audit_path = os.path.join(outdir, "gate_audit.json")
            _audit_existing = []
            if os.path.exists(_audit_path):
                with open(_audit_path) as _af:
                    _audit_existing = json.load(_af)
            _audit_existing.extend(_cig_audit_entries)
            with open(_audit_path, "w") as _af:
                json.dump(_audit_existing, _af, indent=2)
            _pre_fails  = sum(1 for e in _cig_audit_entries if e["phase"] == "pre_gen"  and not e["passed"])
            _post_fails = sum(1 for e in _cig_audit_entries if e["phase"] == "post_gen" and not e["passed"])
            print(f"  [CHAIN_GATE] Audit written → {_audit_path} ({len(_cig_audit_entries)} entries, {_pre_fails} pre-fail, {_post_fails} post-fail)")
        except Exception as _audit_err:
            print(f"  [CHAIN_GATE] Audit write failed (non-blocking): {_audit_err}")

    return results


def _check_frozen(video_path, threshold_kb=3):
    """Post-video frozen statue detection — KLING CALIBRATED.
    Kling renders subtle performance (expressions, slight movement) not sweeping action.
    File size diff of just 3KB+ = real motion for Kling.
    Old 50KB threshold was calibrated for LTX's obvious motion and falsely flagged all Kling shots.
    FIX: threshold_kb=3 (was 50)."""
    try:
        first = video_path + "_check_first.jpg"
        last = video_path + "_check_last.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", first],
                      capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path, "-vframes", "1", "-q:v", "2", last],
                      capture_output=True)
        if os.path.exists(first) and os.path.exists(last):
            s1 = os.path.getsize(first)
            s2 = os.path.getsize(last)
            diff = abs(s1 - s2) / 1024  # KB difference
            # Clean up
            os.remove(first)
            os.remove(last)
            # Frozen: very similar frames = very small size difference
            return diff < threshold_kb
        return False
    except:
        return False


# ═══════════════════════════════════════════════════════════════
# END-FRAME CHAINING — extract last frame, use as next start
# ═══════════════════════════════════════════════════════════════
def extract_last_frame(video_path, outpath):
    """Extract the TRUE last frame of a video for chaining.

    V36.2 FIX: Previous -sseof -0.1 grabbed a frame ~3 frames before end, causing
    jitter at chain boundaries. New approach: seek to final 0.04s (≤1 frame at 25fps)
    and grab the last decoded frame. This ensures video N's end and video N+1's start
    are pixel-identical, eliminating the micro-jump.
    """
    # V36.3 FIX: -sseof -0.04 was too aggressive for Kling videos (produced empty output
    # despite rc=0). Changed to -sseof -1 (last 1 second), which was confirmed working
    # in manual testing. Also trigger fallback on small output, not just non-zero rc.
    cmd = ["ffmpeg", "-y", "-sseof", "-1", "-i", video_path,
           "-vframes", "1", "-q:v", "1", outpath]
    r = subprocess.run(cmd, capture_output=True)
    # Check BOTH return code AND output size — ffmpeg can return 0 but produce empty file
    _ef_ok = r.returncode == 0 and os.path.exists(outpath) and os.path.getsize(outpath) > 1000
    if not _ef_ok:
        # Fallback: some containers don't support -sseof well — try extracting all frames, take last
        tmp_pattern = outpath.replace(".jpg", "_tmp_%04d.jpg")
        cmd2 = ["ffmpeg", "-y", "-i", video_path, "-q:v", "1", tmp_pattern]
        r2 = subprocess.run(cmd2, capture_output=True)
        if r2.returncode == 0:
            import glob
            all_tmp = sorted(glob.glob(outpath.replace(".jpg", "_tmp_*.jpg")))
            if all_tmp:
                shutil.copy2(all_tmp[-1], outpath)  # last frame
                for f in all_tmp:
                    os.remove(f)
                if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
                    print(f"  [CHAIN] extract_last_frame: fallback succeeded — {len(all_tmp)} frames, took last")
                    return outpath
        err = r.stderr.decode("utf-8", errors="replace").strip()[-400:]
        print(f"  [CHAIN] extract_last_frame FAILED (rc={r.returncode}) — {video_path}")
        print(f"  [CHAIN] ffmpeg stderr: {err}")
        return None
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        return outpath
    print(f"  [CHAIN] extract_last_frame: output missing or too small — {outpath}")
    return None


# ═══════════════════════════════════════════════════════════════
# TONE INJECTION — Pre-character establishing shots (TASK 1)
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SPATIAL_MAP — canonical E01/E02/E03 content per room type  (V31.1 2026-03-25)
#
# Each entry maps a room type to:
#   "keywords"  : list of strings to match against room_short.lower()
#   "e01_desc"  : human-readable description of what E01 SHOULD show
#   "e01_nano"  : nano_prompt template (use {tod}, {room_short}, {loc_short}, {atm})
#   "e01_beat"  : beat_action for E01
#   "e02_desc"  : what E02 SHOULD show (empty room interior)
#   "e02_nano"  : nano_prompt template for E02
#   "e02_beat"  : beat_action for E02
#   "e03_desc"  : what E03 SHOULD show (threshold detail insert)
#   "e03_nano"  : nano_prompt template for E03
#   "e03_beat"  : beat_action for E03
#
# The UI Prompt Review panel reads this map to display "expected" content
# alongside actual prompts so operators can catch spatial mismatches.
#
# Resolution order: exact keyword match → is_estate fallback → "default"
# ═══════════════════════════════════════════════════════════════════════════════

SPATIAL_MAP = {
    "grand_foyer": {
        "keywords": ["foyer", "entrance hall", "grand hall", "reception hall"],
        "e01_desc": "EXT iron front gates. Victorian mansion through morning mist. One upper window glows.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion viewed from iron front gates. "
            "{tod_title} mist rolls across overgrown grounds. Stone facade draped in ivy. "
            "One upper-floor window glows with interior light against pale sky. "
            "Heavy iron gate in foreground, rust and age. No people visible. "
            "[CAMERA: 24mm ultra-wide, f/8, deep focus, eye-level] "
            "[PALETTE: desaturated cool {tod} tones, muted grey-green, pale amber window glow] "
            "[AESTHETIC: period realism, photographic, atmospheric gothic, NO CGI, NO digital art]"
        ),
        "e01_beat": "The house watches. {tod_title} fog. Crumbling grandeur.",
        "e02_desc": "INT foyer empty. Checkerboard marble floor. Grandfather clock. Dust motes in light shafts. Staircase ascending into shadow.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Grand Victorian foyer, completely empty. No people. "
            "Checkerboard marble floor. Dust sheets draped over dark furniture. "
            "Tall arched windows casting {tod} shafts of light with floating dust motes. "
            "Dark mahogany staircase rising into upper shadow. Crystal chandelier unlit above. "
            "Grandfather clock standing silent. {atm}. Faded grandeur. Absolute silence. "
            "[CAMERA: 35mm, f/5.6, wide angle, slight elevation] "
            "[PALETTE: desaturated warm amber and deep shadow, dust-filtered {tod} light] "
            "[AESTHETIC: period realism, photographic atmosphere, NO people, NO CGI]"
        ),
        "e02_beat": "The foyer breathes. Dust. Silence. Light.",
        "e03_desc": "ECU tarnished brass front door handle. Hand reaching into frame from outside. Cold {tod} light on metal.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Tarnished Victorian brass door handle, heavy patina of age. "
            "Worn surface from decades of use. A single human hand entering from frame edge, "
            "fingers about to close around the handle. Cold {tod} light on metal. "
            "Stone door frame edge visible at periphery. Texture: aged metal, weathered stone. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, hand sharp, background soft] "
            "[PALETTE: cool grey-gold, muted tones, high texture emphasis] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "A hand reaches for the door handle. The threshold.",
    },
    "library": {
        "keywords": ["library", "reading room", "study"],
        "e01_desc": "EXT library wing of Victorian mansion. Warm amber lamplight from tall arched windows against {tod} sky. Stone facade, ivy.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion angled to show library wing. "
            "{tod_title}. Warm amber lamplight glowing from two tall arched library windows "
            "against pale {tod} sky. Stone facade draped in ivy, overgrown grounds. "
            "No people visible outside. "
            "[CAMERA: 24mm ultra-wide, f/8, deep focus, slight low angle] "
            "[PALETTE: cool {tod} exterior, warm amber window glow, muted grey-green stone] "
            "[AESTHETIC: period realism, photographic, atmospheric gothic, NO CGI, NO digital art]"
        ),
        "e01_beat": "The library wing. Warm light inside. The answers wait.",
        "e02_desc": "INT library empty. Floor-to-ceiling bookshelves. {tod} light on leather spines. Dust on every surface. Reading table with scattered papers.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Victorian library, completely empty. No people. "
            "Floor-to-ceiling bookshelves packed with leather-bound volumes filling every wall. "
            "Warm {tod} light slanting through high windows, catching dust motes. "
            "Central reading table with scattered papers and an open book. {atm}. "
            "[CAMERA: 35mm, f/5.6, wide angle] "
            "[PALETTE: warm amber, aged leather tones, deep shadow between shelves] "
            "[AESTHETIC: period realism, NO people, NO CGI]"
        ),
        "e02_beat": "The library waits. Books and silence. The past on every shelf.",
        "e03_desc": "ECU leather-bound book spine with gold-embossed letters. Folded letter tucked between volumes, yellowed edges protruding.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Victorian leather-bound book spine, gold-embossed title "
            "letters catching warm {tod} lamplight. A folded letter partially visible between "
            "two adjacent volumes, yellowed edges protruding. Rich dark leather texture. "
            "Warm amber light on paper and binding. Dust on spines. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, book sharp, background warm bokeh] "
            "[PALETTE: warm amber, aged paper cream, deep burgundy and forest leather] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "A letter hidden between books. The secret waits.",
    },
    "drawing_room": {
        "keywords": ["drawing room", "sitting room", "parlour", "parlor", "morning room", "reception room"],
        "e01_desc": "EXT Victorian mansion side elevation showing drawing room bay window. Warm firelight visible through glass. Overgrown grounds.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion side elevation, drawing room "
            "bay window prominent. {tod_title}. Warm firelight or lamp glow visible through the "
            "large bay window. Stone facade, overgrown garden visible. No people outside. "
            "[CAMERA: 28mm wide, f/8, deep focus, slight low angle from lawn level] "
            "[PALETTE: cool {tod} exterior, warm amber window glow, muted grey stone and green ivy] "
            "[AESTHETIC: period realism, photographic, NO CGI, NO digital art]"
        ),
        "e01_beat": "The drawing room window glows. Warmth inside. The world outside is cold.",
        "e02_desc": "INT drawing room empty. Ornate fireplace, dust-sheeted furniture, tall windows with heavy drapes. Victorian opulence abandoned.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Victorian drawing room, completely empty. No people. "
            "Ornate carved marble fireplace dominating one wall, cold grate. "
            "Furniture covered in dust sheets — silhouettes of sofas and occasional tables. "
            "Heavy velvet drapes half-drawn over tall sash windows, {tod} light filtering through. "
            "Faded wallpaper, portrait frames on walls. {atm}. "
            "[CAMERA: 35mm, f/5.6, wide angle, slight elevation] "
            "[PALETTE: muted burgundy, dusty cream, warm amber fireplace, cool window light] "
            "[AESTHETIC: period realism, NO people, NO CGI]"
        ),
        "e02_beat": "The drawing room holds its breath. Dust and memory.",
        "e03_desc": "ECU ornate fireplace poker or mantelpiece detail. Tarnished brass. Cold ash in the grate.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Victorian ornate brass fireplace poker, tarnished with age. "
            "Decorative handle catching cold {tod} light. Cold ash visible in grate behind, soft focus. "
            "Textured stone mantelpiece edge at frame periphery. "
            "Stillness. The fire has not been lit. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, poker sharp, grate softly blurred] "
            "[PALETTE: tarnished gold, grey ash, cold stone, muted tones] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "The fireplace cold. The household suspended. Someone is about to arrive.",
    },
    "master_bedroom": {
        "keywords": ["bedroom", "master bedroom", "chamber", "master chamber", "guest room", "guest chamber"],
        "e01_desc": "EXT Victorian mansion upper floor. Bedroom window visible, curtains drawn or slightly open. Dawn or daylight light.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion upper floor elevation. "
            "{tod_title}. Master bedroom windows visible — heavy curtains drawn, thin gap of light. "
            "Stone facade, climbing ivy. Overgrown garden below, perhaps morning dew on grass. "
            "No people visible. "
            "[CAMERA: 24mm wide, f/8, deep focus, slightly low angle from garden] "
            "[PALETTE: cool {tod} exterior light, warm hint behind curtains, grey stone, deep green ivy] "
            "[AESTHETIC: period realism, photographic, intimate and quiet, NO CGI, NO digital art]"
        ),
        "e01_beat": "The upper windows. Behind one of them, something waits to be found.",
        "e02_desc": "INT master bedroom empty. Four-poster bed, heavy drapes, dresser with tarnished mirror. Personal objects suggesting the absent occupant.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Victorian master bedroom, completely empty. No people. "
            "Four-poster bed with heavy brocade canopy and curtains, unmade or neatly made. "
            "Heavy mahogany dresser with large tarnished mirror. Personal items on surfaces — "
            "hairbrush, jewellery box, perfume bottles. {tod_title} light through heavy drapes. {atm}. "
            "The room holds the character of its absent occupant. "
            "[CAMERA: 35mm, f/5.6, wide angle, eye level] "
            "[PALETTE: warm amber, deep burgundy, dark mahogany, pale morning light] "
            "[AESTHETIC: period realism, NO people, intimate domestic, NO CGI]"
        ),
        "e02_beat": "The bedroom holds its owner's shape. Someone lived — or died — here.",
        "e03_desc": "ECU personal object on dresser — hairbrush, jewellery, letter. Intimate detail of the absent person.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Victorian personal object on bedroom dresser — "
            "silver-backed hairbrush, or ornate jewellery box slightly ajar, or folded letter. "
            "Warm {tod} light catching the surface. Dust on edges. "
            "The object as a portrait of its absent owner. Tarnished silver, aged fabric, worn surfaces. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, object sharp, dresser surface soft] "
            "[PALETTE: warm amber, tarnished silver, aged fabric, intimate and quiet] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "An object left behind. The person was real. They are gone.",
    },
    "kitchen": {
        "keywords": ["kitchen", "scullery", "larder", "pantry", "servants", "below stairs", "service entrance"],
        "e01_desc": "EXT Victorian mansion service/rear entrance. Worn stone steps down to heavy wooden door slightly ajar. Faint chimney smoke above.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian mansion service entrance — side or rear facade. "
            "{tod_title}. Worn stone steps leading down to heavy wooden service door, slightly ajar. "
            "Chimney stack with faint smoke above. Cobblestone yard, utility outbuildings. "
            "No people visible. "
            "[CAMERA: 28mm wide, f/8, deep focus, slight low angle from yard level] "
            "[PALETTE: cool {tod} exterior, muted grey stone, warm interior light spilling from door gap] "
            "[AESTHETIC: period realism, photographic, working-class Victorian utility, NO CGI, NO digital art]"
        ),
        "e01_beat": "The service entrance. Stone steps. The working world of the house.",
        "e02_desc": "INT Victorian kitchen empty. Copper pots hanging from ceiling rack. Cast iron range. Flagstone floor. Small window. Working-class functional.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Victorian kitchen, completely empty. No people. "
            "Copper pots and pans hanging from ceiling rack above central preparation table. "
            "Massive cast iron range along one wall, cold. Flagstone floor, thick stone walls. "
            "Small high window casting {tod} light across the copper cookware. "
            "Wooden shelving with ceramic crocks and provisions. {atm}. "
            "[CAMERA: 35mm, f/5.6, wide angle, eye level] "
            "[PALETTE: warm copper-amber, cool grey stone, muted {tod} light] "
            "[AESTHETIC: period realism, photographic atmosphere, working Victorian kitchen, NO people, NO CGI]"
        ),
        "e02_beat": "The kitchen waits. Copper and iron. The working heart of the house.",
        "e03_desc": "ECU large copper cooking pot. Worn hammered surface, aged patina. Warm light catching metal. No people.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Victorian copper cooking pot, large, heavy patina of age and use. "
            "Worn hammered copper surface, riveted seams, curved handle. "
            "Warm {tod} light from small window catching the metal surface, amber and gold reflections. "
            "Hanging from rack or resting on stone, slightly out-of-focus cast iron visible behind. "
            "No people. Texture: hammered metal, aged surface, utilitarian beauty. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, copper sharp, background warm blur] "
            "[PALETTE: warm amber copper-gold, dark background, high texture contrast] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "A copper pot. The kitchen's history in its surface. Work is about to begin.",
    },
    "grand_staircase": {
        "keywords": ["staircase", "grand staircase", "stairs", "landing", "upper landing", "stair hall"],
        "e01_desc": "EXT Victorian mansion main elevation showing the stair tower / upper floor height. Imposing vertical mass.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion main elevation. "
            "{tod_title}. Imposing stone facade, tall central bay suggesting the grand staircase within. "
            "Upper floor windows. Overgrown grounds, ivy on stone. No people visible. "
            "[CAMERA: 24mm ultra-wide, f/8, low angle, deep focus] "
            "[PALETTE: cool {tod} sky, grey stone, amber interior light hinting through upper windows] "
            "[AESTHETIC: period realism, photographic, imposing scale, NO CGI, NO digital art]"
        ),
        "e01_beat": "The house rises. Floor upon floor. The staircase connects everything.",
        "e02_desc": "INT grand staircase empty. Dark mahogany banister curving upward. Light from above. Shadow and height. No people.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. Victorian grand staircase, completely empty. No people. "
            "Dark mahogany banister with carved balusters curving upward from marble floor below. "
            "Natural {tod} light descending from upper landing windows. "
            "Deep shadow in the turns. Height and silence. Persian runner carpet on treads. "
            "Portrait frames on the wall ascending with the stairs. {atm}. "
            "[CAMERA: 28mm wide, f/5.6, looking upward, deep focus] "
            "[PALETTE: dark mahogany, cool ambient light from above, warm amber portrait frames] "
            "[AESTHETIC: period realism, dramatic vertical composition, NO people, NO CGI]"
        ),
        "e02_beat": "The staircase ascends. Above and below. The house reveals its vertical truth.",
        "e03_desc": "ECU mahogany banister top post or carved newel cap. Hand gripping wood. The staircase threshold.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Victorian dark mahogany newel post or banister rail top. "
            "Carved wood, warm {tod} light catching the grain and depth. "
            "A single hand entering frame, gripping the newel post from below. "
            "First step of the ascent. Rich wood texture, polish worn in the grip area. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, wood grain sharp, staircase soft behind] "
            "[PALETTE: warm amber, deep mahogany, cool peripheral shadow] "
            "[AESTHETIC: period realism, photographic detail, tactile close-up, NO CGI]"
        ),
        "e03_beat": "A hand on the banister. The threshold of the upper house.",
    },
    "front_drive": {
        "keywords": ["front drive", "driveway", "drive", "forecourt", "courtyard", "approach", "entrance gate"],
        "e01_desc": "EXT iron front gates of Victorian estate. Long gravel drive leading to house. {tod} light. No people.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic estate viewed from beyond iron front gates. "
            "{tod_title}. Long gravel drive stretching from closed gates toward the distant stone mansion. "
            "Overgrown grounds on either side, mature trees. {atm}. No people visible. "
            "[CAMERA: 24mm ultra-wide, f/11, deep focus, eye level from driveway] "
            "[PALETTE: cool {tod} sky, pale gravel, dark stone mansion at distance, deep green trees] "
            "[AESTHETIC: period realism, wide open space, NO CGI, NO digital art]"
        ),
        "e01_beat": "The gates. The long drive. The house waits at the end.",
        "e02_desc": "Gravel forecourt / front drive surface. Tyre tracks or footprints in gravel. Scale of approach. No people.",
        "e02_nano": (
            "WIDE SHOT. Victorian estate gravel forecourt, completely empty. No people. "
            "Raked gravel surface, pale stone chippings. Tyre tracks or footprints suggesting "
            "recent arrival. The stone mansion facade in background, full frontal elevation. "
            "Formal gardens to sides, clipped hedges, stone urns. {tod_title} light. {atm}. "
            "[CAMERA: 35mm, f/8, deep focus, low angle showing gravel texture] "
            "[PALETTE: cool grey gravel, pale stone facade, deep green hedges, overcast or bright sky] "
            "[AESTHETIC: period realism, formal estate approach, NO people, NO CGI]"
        ),
        "e02_beat": "The forecourt. The scale of the estate. Someone has just arrived.",
        "e03_desc": "ECU gravel close-up. Footstep or heel print in gravel. Arrival. The surface of the estate.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Pale gravel of Victorian estate forecourt. "
            "A shoe or heel pressing into gravel, crushing stone beneath foot — mid-step or just-landed. "
            "High texture close-up of pale stone chips, dust, and compression beneath sole. "
            "The physical act of arrival. {tod} light casting short shadow from heel. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, gravel and foot sharp, ground soft] "
            "[PALETTE: pale grey gravel, warm skin/leather tone, cold ground shadow] "
            "[AESTHETIC: period realism, photographic detail, NO CGI]"
        ),
        "e03_beat": "A foot on the gravel. The estate registers the arrival.",
    },
    "garden": {
        "keywords": ["garden", "grounds", "terrace", "lawn", "greenhouse", "walled garden", "orchard"],
        "e01_desc": "EXT Victorian estate from garden side. House facade seen through overgrown grounds. Nature reclaiming the formal garden.",
        "e01_nano": (
            "EXTERIOR WIDE SHOT. Victorian Gothic mansion viewed from the garden, {tod_title}. "
            "Overgrown formal garden in foreground — untended hedges, wild grass, moss-covered stone urns. "
            "The full garden elevation of the stone mansion behind. {atm}. No people. "
            "[CAMERA: 24mm ultra-wide, f/8, deep focus, eye level from overgrown lawn] "
            "[PALETTE: deep green overgrown garden, grey stone, pale sky, {tod} natural light] "
            "[AESTHETIC: period realism, nature reclaiming formal space, NO CGI, NO digital art]"
        ),
        "e01_beat": "The garden gone wild. The house looms through the overgrowth.",
        "e02_desc": "INT/EXT garden space empty. Overgrown paths, abandoned garden furniture, nature encroaching. {tod} light on it all.",
        "e02_nano": (
            "WIDE SHOT. Victorian estate garden, completely empty. No people. "
            "Overgrown gravel path between untended flowerbeds, weeds pushing through stone. "
            "Rusted iron garden bench, moss-covered. Topiary half-grown into shapelessness. "
            "{tod_title} natural light, outdoor atmosphere. {atm}. "
            "[CAMERA: 35mm, f/5.6, deep focus, eye level from path] "
            "[PALETTE: deep green, grey stone, rust, pale sky, natural {tod} light] "
            "[AESTHETIC: period realism, melancholy beauty, NO people, NO CGI]"
        ),
        "e02_beat": "The garden holds what the house forgot. Nature and neglect.",
        "e03_desc": "ECU overgrown garden detail — moss on stone, rusted iron, thorned rose cane. Nature asserting itself.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Detail of Victorian estate garden — stone urn or wall surface "
            "heavily colonised by moss, pale green and grey textures. Or rusted iron gate hinge. "
            "Or a wild rose cane growing across a path, thorns sharp. {tod} natural light. "
            "No people. The garden's slow reclamation. "
            "[CAMERA: 85mm macro, f/2.8, very shallow DOF, detail sharp, garden soft behind] "
            "[PALETTE: deep green moss, grey stone, rust, natural {tod} light] "
            "[AESTHETIC: period realism, nature close-up, NO CGI]"
        ),
        "e03_beat": "Moss on stone. The garden claims everything eventually.",
    },
    "estate_default": {
        # Fallback for any estate/manor location not matched above
        "keywords": [],  # matched by is_estate flag, not keywords
        "e01_desc": "EXT Victorian Gothic mansion from iron front gates. {tod} mist. One upper window glows.",
        "e01_nano": (
            "EXTERIOR ESTABLISHING SHOT. Victorian Gothic mansion viewed from iron front gates. "
            "{tod_title} mist rolls across overgrown grounds. Stone facade draped in ivy. "
            "One upper-floor window glows with interior light against pale sky. "
            "Heavy iron gate in foreground, rust and age. No people visible. "
            "[CAMERA: 24mm ultra-wide, f/8, deep focus, eye-level] "
            "[PALETTE: desaturated cool {tod} tones, muted grey-green, pale amber window glow] "
            "[AESTHETIC: period realism, photographic, atmospheric gothic, NO CGI, NO digital art]"
        ),
        "e01_beat": "The house watches. {tod_title} fog. Crumbling grandeur.",
        "e02_desc": "INT room empty. {atm}. Period furniture, dust, {tod} light. No people.",
        "e02_nano": (
            "INTERIOR WIDE SHOT. {room_short}, completely empty. No people. "
            "Victorian period furniture, dust on every surface. {tod_title} light from tall windows. "
            "{atm}. Faded grandeur. "
            "[CAMERA: 35mm, f/5.6] [PALETTE: desaturated period tones, warm amber and deep shadow] "
            "[AESTHETIC: period realism, NO people, NO CGI]"
        ),
        "e02_beat": "The room breathes. {atm}.",
        "e03_desc": "ECU threshold detail — door handle, knocker, or entry object. First human contact.",
        "e03_nano": (
            "EXTREME CLOSE-UP INSERT. Tarnished Victorian brass door handle or entry detail. "
            "Worn surface, patina of age. {tod} light on metal. No people. Threshold moment. "
            "[CAMERA: 85mm macro, f/2.8] [AESTHETIC: period realism, NO CGI]"
        ),
        "e03_beat": "The threshold. First contact with the space.",
    },
}


def resolve_spatial_profile(room_short: str, location: str) -> dict:
    """
    Return the SPATIAL_MAP entry that best matches the given room/location string.
    Checks room keywords first, then falls back to estate_default if is_estate.
    Returns SPATIAL_MAP["estate_default"] if nothing matches.
    """
    room_lower = room_short.lower()
    loc_lower  = location.lower()
    for key, profile in SPATIAL_MAP.items():
        if key == "estate_default":
            continue
        for kw in profile.get("keywords", []):
            if kw in room_lower or kw in loc_lower:
                return profile
    # Estate fallback
    if any(w in loc_lower for w in ("estate", "manor", "house", "hall", "castle")):
        return SPATIAL_MAP["estate_default"]
    return SPATIAL_MAP["estate_default"]


def _build_spatial_nano(template: str, ctx: dict) -> str:
    """Apply context dict to a SPATIAL_MAP nano template. Safe — unknown keys left as-is."""
    try:
        return template.format(**ctx)
    except KeyError:
        return template  # return template unchanged if a key is missing


def inject_tone_shots(pdir, scene_id, sb_scene, story_bible):
    """
    TASK 1: Pre-character tone shot injection. Universal — works for any scene/project.

    Checks whether the scene already has E-prefix atmosphere shots before the first
    character appears. If not, generates up to 3 shots from story bible data:
      E01 — EXTERIOR ESTABLISHING: the building/location from outside
      E02 — INTERIOR ATMOSPHERE: empty room before characters arrive
      E03 — THRESHOLD INSERT: close detail of the entry point (door handle, gate, etc.)

    Uses SPATIAL_MAP for location-specific content so every room type gets the right
    exterior, interior, and threshold detail — not a generic estate shot.

    Conditions for each shot:
    - E01 injected when scene is interior (int_ext=="INT") or location has estate/manor/house
    - E02 injected when story bible has atmosphere text
    - E03 injected when the first character shot exists (someone is about to enter)

    Writes the new shots into shot_plan.json (before first M-shot) and returns the
    shot objects so run_scene() can prepend them to mshots before generation.

    Logs: "[TONE] Scene 001: injected 3 pre-character shots: ['001_E01', '001_E02', '001_E03']"
    """
    sp_path = Path(pdir) / "shot_plan.json"
    sp_raw = json.load(open(sp_path))
    is_list = isinstance(sp_raw, list)
    all_shots = sp_raw if is_list else sp_raw.get("shots", [])

    # ── V36.2 COLD OPEN CHECK — story bible drives E-shot decision ─────────
    # If the scene's first beat contains dialogue or the story bible signals a cold open,
    # E-shots (establishing preamble) should NOT be injected. The opener type classification
    # happens downstream, but we can detect cold-open signals HERE from the story bible:
    #   - First beat has dialogue → conversation already in progress → DIALOGUE_OPENER
    #   - Scene description contains "cold open" / "mid-conversation" → explicit cold open
    #   - Shot plan already has _opener_type on any shot → respect it
    _sb_beats = sb_scene.get("beats", []) if isinstance(sb_scene, dict) else []
    _first_beat_has_dialogue = bool(_sb_beats and _sb_beats[0].get("dialogue"))
    _scene_desc_cold = any(kw in (sb_scene.get("description", "") + " " + sb_scene.get("synopsis", "")).lower()
                          for kw in ("cold open", "mid-conversation", "already talking", "in progress"))
    _existing_opener = ""
    for _s in all_shots:
        if _s.get("shot_id", "").startswith(f"{scene_id}_") and (_s.get("_scene_opener_type") or _s.get("_opener_type")):
            _existing_opener = _s.get("_scene_opener_type") or _s["_opener_type"]
            break
    _cold_open_types = {"DIALOGUE_OPENER", "COLD_OPEN", "REVELATION_OPENER"}

    # EXISTING E-SHOTS ALWAYS WIN — check before cold-open guard.
    # Cold-open guard should only block NEW injection, never discard already-authored E-shots.
    # Solo discovery scenes (BROLL_OPENER + self-directed dialogue) need their E-shots.
    existing_e = [s for s in all_shots if s.get("shot_id", "").startswith(f"{scene_id}_E")]
    if existing_e:
        print(f"  [TONE] Scene {scene_id}: {len(existing_e)} tone shots already in plan — reusing")
        return existing_e

    if _existing_opener in _cold_open_types or _first_beat_has_dialogue or _scene_desc_cold:
        _reason = (_existing_opener if _existing_opener in _cold_open_types
                   else "first_beat_has_dialogue" if _first_beat_has_dialogue
                   else "scene_desc_cold_open")
        print(f"  [TONE] Scene {scene_id}: COLD OPEN detected ({_reason}) — skipping E-shot injection")
        return []
    # ─────────────────────────────────────────────────────────────────────────

    location      = sb_scene.get("location", "")
    atmosphere    = sb_scene.get("atmosphere", "")
    int_ext       = sb_scene.get("int_ext", "INT")
    time_of_day   = sb_scene.get("time_of_day", "MORNING")
    tod           = time_of_day.lower() if time_of_day else "morning"

    scene_shots   = [s for s in all_shots if s.get("shot_id", "").startswith(f"{scene_id}_")]
    first_m_has_chars = bool(scene_shots and scene_shots[0].get("characters"))

    # Global tone from story bible
    themes    = story_bible.get("themes", [])
    theme_str = themes[3] if len(themes) > 3 else (themes[0] if themes else "")

    loc_parts  = location.split(" - ")
    loc_short  = loc_parts[0].strip()                          # "HARGROVE ESTATE"
    room_short = loc_parts[1].strip() if len(loc_parts) > 1 else loc_short  # "GRAND FOYER"
    is_estate  = any(w in location.lower() for w in ("estate", "manor", "house", "hall", "castle"))
    is_foyer   = "foyer" in room_short.lower()
    is_library = "library" in room_short.lower()
    is_kitchen = any(w in room_short.lower() for w in ("kitchen", "scullery", "larder", "pantry"))
    is_service = any(w in room_short.lower() for w in ("service", "servant", "below stairs", "basement"))

    injected = []

    # ── Resolve spatial profile once for all three E-shots  (V31.1 SPATIAL_MAP)
    sp       = resolve_spatial_profile(room_short, location)
    sp_key   = next((k for k, v in SPATIAL_MAP.items() if v is sp), "estate_default")
    ctx = {
        "tod":        tod,
        "tod_title":  tod.title(),
        "room_short": room_short,
        "loc_short":  loc_short,
        "atm":        atmosphere or "",
    }

    # ── E01: EXTERIOR ESTABLISHING ─────────────────────────────────────────────
    if int_ext == "INT" or is_estate:
        nano        = _build_spatial_nano(sp["e01_nano"], ctx)
        beat_action = _build_spatial_nano(sp["e01_beat"], ctx)
        ext_desc    = _build_spatial_nano(sp["e01_desc"], ctx)
        injected.append({
            "shot_id": f"{scene_id}_E01", "shot_type": "establishing",
            "duration": 8, "characters": [], "dialogue_text": None, "_dialogue_speaker": "",
            "description": ext_desc, "_frame_description": ext_desc, "_choreography": "",
            "_beat_action": beat_action, "_beat_atmosphere": atmosphere,
            "_beat_enriched": True, "_is_establishing": True, "_is_closing": False,
            "_eye_line_target": "", "_body_direction": "",
            "_cut_motivation": "TONE — exterior establishing before characters appear",
            "location": location, "scene_id": scene_id,
            "_beat_ref": "tone_e01", "_beat_index": None,
            "nano_prompt": nano, "_nano_mode": "text2img",
            "_approval_status": "AWAITING_APPROVAL", "_tone_injected": True,
            "_spatial_profile": sp_key,
        })

    # ── E02: INTERIOR ATMOSPHERE (empty room) ──────────────────────────────────
    if atmosphere:
        nano        = _build_spatial_nano(sp["e02_nano"], ctx)
        beat_action = _build_spatial_nano(sp["e02_beat"], ctx)
        atm_desc    = _build_spatial_nano(sp["e02_desc"], ctx)
        injected.append({
            "shot_id": f"{scene_id}_E02", "shot_type": "insert",
            "duration": 6, "characters": [], "dialogue_text": None, "_dialogue_speaker": "",
            "description": atm_desc, "_frame_description": atm_desc, "_choreography": "",
            "_beat_action": beat_action, "_beat_atmosphere": atmosphere,
            "_beat_enriched": True, "_is_establishing": False, "_is_closing": False,
            "_eye_line_target": "", "_body_direction": "",
            "_cut_motivation": "TONE — empty room atmosphere before characters arrive",
            "location": location, "scene_id": scene_id,
            "_beat_ref": "tone_e02", "_beat_index": None,
            "nano_prompt": nano, "_nano_mode": "text2img",
            "_approval_status": "AWAITING_APPROVAL", "_tone_injected": True,
            "_spatial_profile": sp_key,
        })

    # ── E03: THRESHOLD INSERT ──────────────────────────────────────────────────
    if first_m_has_chars:
        nano        = _build_spatial_nano(sp["e03_nano"], ctx)
        beat_action = _build_spatial_nano(sp["e03_beat"], ctx)
        thr_desc    = _build_spatial_nano(sp["e03_desc"], ctx)
        injected.append({
            "shot_id": f"{scene_id}_E03", "shot_type": "insert",
            "duration": 5, "characters": [], "dialogue_text": None, "_dialogue_speaker": "",
            "description": thr_desc, "_frame_description": thr_desc, "_choreography": "",
            "_beat_action": beat_action,
            "_beat_atmosphere": "anticipation, threshold, first contact",
            "_beat_enriched": True, "_is_establishing": False, "_is_closing": False,
            "_eye_line_target": "", "_body_direction": "",
            "_cut_motivation": "TONE — threshold insert before characters enter",
            "location": location, "scene_id": scene_id,
            "_beat_ref": "tone_e03", "_beat_index": None,
            "nano_prompt": nano, "_nano_mode": "text2img",
            "_approval_status": "AWAITING_APPROVAL", "_tone_injected": True,
            "_spatial_profile": sp_key,
        })

    if not injected:
        print(f"  [TONE] Scene {scene_id}: no tone injection conditions met")
        return []

    # Insert before first M-shot of this scene
    insert_idx = next(
        (i for i, s in enumerate(all_shots) if s.get("shot_id", "").startswith(f"{scene_id}_M")),
        len(all_shots)
    )
    for i, shot in enumerate(injected):
        all_shots.insert(insert_idx + i, shot)

    # Backup and save
    import shutil as _shutil
    _shutil.copy(str(sp_path), str(sp_path) + f".backup_tone_inject_{int(time.time())}")
    with open(sp_path, "w") as _f:
        json.dump(sp_raw, _f, indent=2)

    ids = [s["shot_id"] for s in injected]
    print(f"  [TONE] Scene {scene_id}: injected {len(injected)} pre-character shots: {ids}")
    return injected


# ═══════════════════════════════════════════════════════════════
# MAIN — Universal entry point
# ═══════════════════════════════════════════════════════════════
def run_scene(project, scene_id, mode="lite", reuse_frames=False,
              frames_only=False, videos_only=False, dry_run=False, gen_mode="chain"):
    pdir = Path("pipeline_outputs") / project
    shots, sb, cast, locs = load_project(project)
    sb_scene = get_sb_scene(sb, scene_id)
    if not sb_scene:
        print(f"Scene {scene_id} not found in story bible"); return

    # Step 1-2: Prep (skip if already done)
    cp = pdir / "scene_contracts" / f"{scene_id}_contract.json"
    if not cp.exists():
        print(f"\n[PREP] Beat enrichment + truth compilation for scene {scene_id}...")
        try: enrich_project(str(pdir), [scene_id])
        except Exception as e: print(f"  enrich: {e}")
        try: compile_scene_truth(str(pdir), scene_id)
        except Exception as e: print(f"  truth: {e}")
    else:
        print(f"\n[PREP] Scene {scene_id} already prepared")

    contract = {}
    if cp.exists(): contract = json.load(open(cp))

    # ═══ LAYER 2: DIRECTOR BRAIN PRE-SCENE BRIEF ════════════════════════════
    # Runs BEFORE any shot is generated. Reads story bible + production history.
    # Returns EditorialGuidance injected into consciousness_state for beat context.
    _director_guidance = None
    if _DB_AVAILABLE and sb_scene:
        try:
            _director_guidance = _db_pre_scene_brief(
                scene_id=scene_id,
                bible_scene=sb_scene,
                project_dir=pdir,
            )
            _tension  = getattr(_director_guidance, "tension_level", "moderate")
            _cam_note = getattr(_director_guidance, "camera_guidance", "")
            _source   = getattr(_director_guidance, "source", "heuristic")
            print(f"\n  [DIRECTOR BRAIN] Scene {scene_id} brief: tension={_tension} "
                  f"| {_cam_note[:60] if _cam_note else 'no camera note'} [{_source}]")
        except Exception as _dbe:
            print(f"  [DIRECTOR BRAIN] Pre-scene brief failed (non-blocking): {_dbe}")

    shots = json.load(open(pdir / "shot_plan.json"))
    if not isinstance(shots, list): shots = shots.get("shots", [])
    mshots = auto_consolidate(sb_scene, contract, shots, scene_id, cast=cast)
    location_text = sb_scene.get("location", "")

    # V36.5 FIX: auto_consolidate creates fresh M-shot dicts from beats — key plan fields
    # like _chain_group, nano_prompt, _arc_position are lost. Merge them back from originals
    # by shot_id so chain_intelligence_gate validators receive complete shot state.
    _PRESERVE_FIELDS = ("_chain_group", "chain_group", "nano_prompt", "_arc_position",
                        "_arc_carry_directive", "_arc_release", "_beat_ref",
                        "_truth_locked", "_truth_hash", "_approval_status",
                        "first_frame_url", "video_url")
    _orig_by_id = {s.get("shot_id"): s for s in shots if s.get("shot_id")}
    for _ms in mshots:
        _orig = _orig_by_id.get(_ms.get("shot_id"))
        if _orig:
            for _fld in _PRESERVE_FIELDS:
                if _fld not in _ms or _ms[_fld] is None:
                    _v = _orig.get(_fld)
                    if _v is not None:
                        _ms[_fld] = _v

    # ── V36 Genre DNA injection ──────────────────────────────────
    _genre_id = os.environ.get("ATLAS_GENRE_DNA", "")
    if _genre_id:
        try:
            from tools.network_intake import apply_genre_dna
            apply_genre_dna(mshots, _genre_id)
            print(f"  [GENRE DNA] Applied '{_genre_id}' to {len(mshots)} shots")
        except Exception as e:
            print(f"  [GENRE DNA] Warning: could not apply — {e}")

    # Wire A budget cap reset — fresh counter for each scene so a bad prior scene doesn't
    # block regens in the current scene.
    _wire_a_reset(scene_id)

    # FIX-ERR-06: Dynamic character names loaded from cast_map — universal for any project.
    # Updates module-level _ACTIVE_CHAR_NAMES / _ACTIVE_CHAR_PREFIXES so that helper functions
    # (gen_scene_seedance, gen_scene_multishot, _build_prompt) that parse dialogue attribution
    # automatically use the correct character names for this show — not hardcoded Victorian names.
    global _ACTIVE_CHAR_NAMES, _ACTIVE_CHAR_PREFIXES
    _cast_path_dyn = pdir / "cast_map.json"
    _cast_dyn = json.load(open(_cast_path_dyn)) if _cast_path_dyn.exists() else cast
    _dyn_names    = [c.upper() for c in (_cast_dyn.keys() if isinstance(_cast_dyn, dict) else [])]
    _dyn_prefixes = [f"{c}:" for c in _dyn_names]
    if _dyn_names:
        _ACTIVE_CHAR_NAMES[:]    = _dyn_names
        _ACTIVE_CHAR_PREFIXES[:] = _dyn_prefixes
        print(f"  [CAST] Dynamic character list: {_dyn_names}")

    # FIX-ERR-11: Single-shot regen mode via ATLAS_REGEN_SHOT_ID env var.
    # Set: ATLAS_REGEN_SHOT_ID=001_M02 python3 atlas_universal_runner.py victorian_shadows_ep1 001
    # Filters mshots to only the specified shot so only that one regenerates.
    _regen_target = os.environ.get("ATLAS_REGEN_SHOT_ID", "").strip()
    _regen_is_e_series = _regen_target and "_E" in _regen_target
    if _regen_target and not _regen_is_e_series:
        _regen_match = [s for s in mshots if s["shot_id"] == _regen_target]
        if not _regen_match:
            print(f"  [REGEN] Shot '{_regen_target}' not in scene {scene_id}.")
            print(f"  [REGEN] Available: {[s['shot_id'] for s in mshots]}")
            return
        mshots = _regen_match
        print(f"  [REGEN] Single-shot mode: regenerating {_regen_target} only")

    # TASK 1: Tone shot injection — prepend pre-character establishing/atmosphere shots
    # Skipped on single-shot regen to avoid regenerating tone shots unnecessarily.
    if not _regen_target or _regen_target.split("_")[1].startswith("E"):
        try:
            _tone_shots = inject_tone_shots(pdir, scene_id, sb_scene, sb)
            if _tone_shots:
                mshots = _tone_shots + mshots
                print(f"  [TONE] {len(_tone_shots)} tone shots prepended → {len(mshots)} total shots for scene {scene_id}")
        except Exception as _te:
            print(f"  [TONE] WARNING: inject_tone_shots failed ({_te}) — proceeding without tone shots")
    # V30.5: E-series regen filter — runs AFTER tone injection so E shots are in mshots
    if _regen_is_e_series:
        _regen_match = [s for s in mshots if s["shot_id"] == _regen_target]
        if not _regen_match:
            print(f"  [REGEN] E-shot '{_regen_target}' not found after tone injection.")
            print(f"  [REGEN] Available: {[s['shot_id'] for s in mshots]}")
            return
        mshots = _regen_match
        print(f"  [REGEN] E-series single-shot mode: regenerating {_regen_target} only")

    # ── V36.1 SCENE TRANSITION MANAGER — opener type + cross-scene entry context ──
    # Classifies scene opener (COLD_OPEN / ACTION / DIALOGUE / BROLL / REVELATION / ATMOSPHERE)
    # from story bible intelligence and injects _opener_prefix onto E01/E02/E03/M01.
    # Also extracts previous scene's exit emotional state and writes _scene_entry_context
    # onto M01 (CHAIN_ANCHOR) so the chain's first frame carries the cross-scene weight.
    # compile_nano() reads both fields in STEP 5 — highest attention position.
    try:
        from tools.scene_transition_manager import inject_scene_entry, get_prev_sb_scene
        _prev_sb_sc = get_prev_sb_scene(sb, scene_id)
        mshots = inject_scene_entry(mshots, scene_id, sb_scene, _prev_sb_sc, verbose=True)
    except Exception as _stm_err:
        print(f"  [OPENER] WARNING: scene_transition_manager failed ({_stm_err}) — proceeding without entry context")

    # ── V36.2 COLD OPEN E-SHOT STRIP ─────────────────────────────────────────
    # If opener type is DIALOGUE_OPENER, the scene cuts straight into conversation.
    # E-shots (establishing/atmosphere/insert) contradict "MID-CONVERSATION — no preamble."
    # Strip them from mshots so only M-shots render. For M-shots in --frames-only mode,
    # only M01 (CHAIN_ANCHOR) needs a first frame — M02+ get their start from the chain.
    _cold_open_types = {"DIALOGUE_OPENER", "COLD_OPEN", "REVELATION_OPENER"}
    _scene_opener_type = ""
    for _s in mshots:
        _sot = _s.get("_scene_opener_type") or _s.get("_opener_type") or ""
        if _sot:
            _scene_opener_type = _sot
            break
    if _scene_opener_type in _cold_open_types:
        _e_shots = [s for s in mshots if s.get("shot_id", "").startswith(f"{scene_id}_E")]
        _m_shots = [s for s in mshots if not s.get("shot_id", "").startswith(f"{scene_id}_E")]
        if _e_shots:
            print(f"  [COLD-OPEN] {_scene_opener_type}: stripping {len(_e_shots)} E-shots — cold open has no preamble")
            print(f"  [COLD-OPEN] Stripped: {[s['shot_id'] for s in _e_shots]}")
            print(f"  [COLD-OPEN] Remaining: {[s['shot_id'] for s in _m_shots]}")
            mshots = _m_shots
        # Mark M02+ to skip independent first-frame generation in --frames-only mode.
        # They'll get their start_image from end-frame chain during --videos-only.
        _m_anchor_set = False
        for _s in mshots:
            _sid = _s.get("shot_id", "")
            if _sid.startswith(f"{scene_id}_M"):
                if not _m_anchor_set:
                    _m_anchor_set = True
                    print(f"  [COLD-OPEN] {_sid} = CHAIN_ANCHOR (first frame generated)")
                else:
                    _s["_cold_open_chain_only"] = True
                    print(f"  [COLD-OPEN] {_sid} = CHAIN_ONLY (first frame from chain, skipped in --frames-only)")
    # ───────────────────────────────────────────────────────────────────────────

    # ── UNIVERSAL CHAIN FRAME SKIP (V37.1) ──────────────────────────────────────
    # For ALL regular scenes (non-DIALOGUE_OPENER/COLD_OPEN/REVELATION_OPENER):
    # M02+ non-independent M-shots will receive their start_image from the previous
    # Kling group's end-frame during --videos-only. They must NOT get standalone Nano
    # frames in --frames-only — those frames would be discarded anyway and waste money.
    #
    # Mirrors gen_scene_multishot() chain group assignment logic:
    #   E-shots (shot_id contains _E)  → always get standalone frames (room atmosphere)
    #   _is_broll / _no_char_ref       → INDEPENDENT — get their own frames
    #   First non-independent M-shot   → CHAIN_ANCHOR — gets Nano I2I frame
    #   All subsequent non-independent M-shots → _chain_inherits_start=True — skip
    #
    # DIALOGUE_OPENER scenes are already handled above via _cold_open_chain_only.
    if _scene_opener_type not in _cold_open_types:
        _chain_anchor_marked = False
        for _s in mshots:
            _sid = _s.get("shot_id", "")
            if not _sid.startswith(f"{scene_id}_M"):
                continue  # E-shots always get their own frames — never skip
            if _s.get("_is_broll") or _s.get("_no_char_ref"):
                continue  # Independent shots (B-roll, env-only) get their own frames
            if not _chain_anchor_marked:
                _chain_anchor_marked = True
                print(f"  [CHAIN-FRAME] {_sid} = CHAIN_ANCHOR (Nano I2I frame will be generated)")
            else:
                _s["_chain_inherits_start"] = True
                print(f"  [CHAIN-FRAME] {_sid} = CHAIN_ONLY (start_image from Kling end-frame — no Nano)")
    # ─────────────────────────────────────────────────────────────────────────────

    # ── WIRE D: SCREEN POSITION LOCK (V30.4 — T2-FE-20) ────────────────────────
    # Establish which character is on which side of frame from the first OTS A-angle.
    # Lock those positions for ALL subsequent shot types in this scene.
    # CRITICAL: must use the FULL mshots list (not a filtered batch) so OTS shots
    # are always found even when only a subset is being generated.
    # NON-BLOCKING: if OTSEnforcer unavailable, generation proceeds without position lock.
    _scene_ots_enforcer = None
    if _OTS_AVAILABLE and _OTSEnforcer is not None:
        try:
            _scene_ots_enforcer = _OTSEnforcer(cast)
            _scene_ots_enforcer.set_scene_context(
                scene_shots=mshots,          # FULL list — not filtered
                story_bible_scene=sb_scene,  # For solo-scene detection
            )
            _scene_ots_enforcer.establish_screen_positions(mshots)  # scans for OTS A-angle
            _pos = getattr(_scene_ots_enforcer, '_screen_positions', {})
            if _pos:
                print(f"  [WIRE-D] Screen positions locked: {_pos}")
            else:
                print(f"  [WIRE-D] No OTS A-angle found yet — positions establish on first OTS shot")
        except Exception as _ots_err:
            print(f"  [WIRE-D] OTSEnforcer init skipped ({_ots_err}) — proceeding without position lock")
            _scene_ots_enforcer = None
    # ───────────────────────────────────────────────────────────────────────────

    # V36 Genre DNA injection — applies channel identity to all shot prompts
    _genre_id = os.environ.get("ATLAS_GENRE_DNA", "")
    if _genre_id:
        try:
            from tools.network_intake import apply_genre_dna
            apply_genre_dna(mshots, _genre_id)
            print(f"  [GENRE DNA] Applied '{_genre_id}' profile to {len(mshots)} shots")
        except Exception as _gdna_err:
            print(f"  [GENRE DNA] WARNING: apply_genre_dna failed ({_gdna_err}) — proceeding without genre DNA")

    # Step 3: Generation gate
    from generation_gate import run_gate, print_gate_report
    gate_result = run_gate(str(pdir), scene_id, mshots, cast, contract, locs, location_text, mode)
    print_gate_report(gate_result)
    if not gate_result["can_generate"]:
        print(f"\n  BLOCKED"); return

    # Step 3b: V36.2 Consciousness Validator — full intelligence chain audit before spending money
    try:
        from tools.consciousness_validator import validate_scene_consciousness
        _cv_sb_scene = sb_scene if isinstance(sb_scene, dict) else {}
        _cv_result = validate_scene_consciousness(scene_id, mshots, _cv_sb_scene, cast, verbose=True)
        if not _cv_result["pass"]:
            _cv_blocks = [i for i in _cv_result["issues"] if i["severity"] == "BLOCK"]
            print(f"\n  [CONSCIOUSNESS] ⚠️ {len(_cv_blocks)} BLOCKING issues detected — proceeding with warnings.")
            print(f"  [CONSCIOUSNESS] Advisory mode (V36.2): generation continues. V37+ will enforce blocks.")
        else:
            print(f"  [CONSCIOUSNESS] ✅ All 6 layers validated — consciousness chain intact.")
    except Exception as _cv_err:
        print(f"  [CONSCIOUSNESS] Validator unavailable ({_cv_err}) — proceeding without consciousness check.")

    tag = "lite" if mode == "lite" else "full"
    frame_dir = str(pdir / "first_frames")  # V30.3: Always write to first_frames/ — UI reads from here

    # V29.8: Model-aware video dir — controlled by ATLAS_VIDEO_MODEL env var (set by UI selector)
    # "kling" = proven Kling v3/pro multi-shot | "seedance"/"seeddance" = Seedance v2.0 (ByteDance)
    _vid_model = ACTIVE_VIDEO_MODEL
    if _vid_model in ("seedance", "seeddance"):
        video_dir = str(pdir / f"videos_seedance_{tag}")
    else:
        video_dir = str(pdir / f"videos_kling_{tag}")
    os.makedirs(frame_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)

    # Build context for Kling compiler
    # V36.4: Include location master path so chain reframe can use it as visual anchor
    _ctx_loc_path = get_location_ref(locs, location_text) if locs and location_text else None
    context = {
        "_room_dna": build_scene_dna(sb_scene),
        "_lighting_rig": build_scene_lighting_rig(sb_scene),
        "_location_master_path": _ctx_loc_path,  # V36.4: visual room anchor for chain reframes
    }

    # V36.5: CHAIN ARC INTELLIGENCE — enrich shots with arc positions
    # Opening declares → Middle carries → Ending releases
    try:
        _sb_full = None
        _sb_path = str(pdir / "story_bible.json")
        if os.path.exists(_sb_path):
            with open(_sb_path) as _sbf:
                _sb_full = json.load(_sbf)
        mshots = enrich_shots_with_arc(mshots, _sb_full, scene_id)
        _arc_summary = " → ".join(f"{s.get('shot_id','?')}[{s.get('_arc_position','?')}]" for s in mshots)
        print(f"  [ARC] {_arc_summary}")
        # V36.5+: make story_bible available to gen_scene_multishot for VVO checks
        context["_story_bible"] = _sb_full
    except Exception as _arc_err:
        print(f"  [ARC] Warning: arc enrichment failed ({_arc_err}) — proceeding without")

    # Route shots
    routing = {}
    for s in mshots:
        model, reason = route_shot(s)
        routing[s["shot_id"]] = (model, reason)

    kling_count = sum(1 for m, _ in routing.values() if m == "kling")
    ltx_count = sum(1 for m, _ in routing.values() if m == "ltx")

    print(f"\n{'='*70}")
    print(f"  SCENE {scene_id} — {mode.upper()} | V3 FULL HARMONY")
    print(f"  {len(mshots)} shots: {kling_count} Kling (Kling-only, no LTX)")
    print(f"  Location: {location_text}")
    print(f"  Systems: beat✓ truth✓ DNA✓ identity✓ judge✓ chain✓ kling-compiler✓")
    print(f"  Models: nano/edit → Kling v3/pro ONLY (V29.3: LTX removed)")
    print(f"{'='*70}")

    # Phase 1: First frames (parallel, multi-candidate, vision judge)
    # V29.10: --reuse-frames skips Phase 1 if frames already exist on disk (for model comparison runs)
    # V29.16 FIX-ERR-02: --videos-only MUST skip Phase 1 entirely. Without this guard,
    # Phase 1 runs unconditionally, regenerates all frames, and overwrites human-approved
    # _approval_status=AWAITING_APPROVAL with AUTO_APPROVED — killing the 2-stage review gate.
    all_frames = {}
    judge_scores = {}  # WIRE 1: sid -> real Florence-2 identity score

    if videos_only:
        print(f"\n  [VIDEOS-ONLY] Skipping Phase 1 — loading approved frames from disk")
        for s in mshots:
            sid = s["shot_id"]
            fp = Path(frame_dir) / f"{sid}.jpg"
            if fp.exists():
                all_frames[sid] = str(fp)
                judge_scores[sid] = s.get("_frame_identity_score", 0.75)
        if not all_frames:
            print(f"  FAIL — no frames found in {frame_dir}. Run --frames-only first.")
            return
        print(f"  Loaded {len(all_frames)}/{len(mshots)} approved frames — proceeding to Phase 2 (video)")
    else:
        print(f"\nPHASE 1: FIRST FRAMES (parallel, multi-candidate, vision judge + Florence-2 scoring)")

        # V30.5: Initialize continuity memory — accumulate spatial states per shot
        _cont_mem = None
        if _CONTINUITY_AVAILABLE:
            try:
                _cont_mem = ContinuityMemory(str(pdir))
                for _cs in mshots:
                    _spatial = extract_spatial_state_from_metadata(_cs, cast)
                    _cont_mem.store_shot_state(_cs["shot_id"], _spatial)
                    # Propagate _continuity_delta if already set (e.g., from story bible beats)
                    if _cs.get("_continuity_delta"):
                        print(f"  [CONTINUITY] {_cs['shot_id']}: {_cs['_continuity_delta'][:80]}")
                print(f"  [CONTINUITY] {len(mshots)} spatial states initialised")
            except Exception as _cm_err:
                print(f"  [CONTINUITY] Init failed ({_cm_err}) — proceeding without")

        # V30.5: Assign spatial zones to all shots
        if _SPATIAL_AVAILABLE:
            try:
                _sb_beats = sb_scene.get("beats", []) if isinstance(sb_scene, dict) else []
                _timecode = build_scene_timecode(mshots, _sb_beats, scene_id)
                for _tc in _timecode:
                    _tc_sid = _tc.get("shot_id")
                    _tc_zone = _tc.get("zone", "center")
                    for _s in mshots:
                        if _s.get("shot_id") == _tc_sid:
                            _s["_spatial_zone"] = _tc_zone
                            break
                if _timecode:
                    print(f"  [ZONES] Assigned: {', '.join(t.get('shot_id','?') + '=' + t.get('zone','?') for t in _timecode)}")
                else:
                    print(f"  [ZONES] No timecode entries — beats may be empty")
            except Exception as _tz_err:
                print(f"  [ZONES] Failed ({_tz_err}) — proceeding without")

        # Check if we can reuse existing frames (e.g., Seedance comparison run after Kling Phase 1)
        if reuse_frames:
            existing = {}
            for s in mshots:
                sid = s["shot_id"]
                fp = Path(frame_dir) / f"{sid}.jpg"
                if fp.exists():
                    existing[sid] = str(fp)
            if len(existing) == len(mshots):
                print(f"  [REUSE] All {len(existing)} frames exist — skipping Phase 1 generation")
                all_frames = existing
                judge_scores = {sid: 0.75 for sid in existing}
            else:
                missing = [s["shot_id"] for s in mshots if s["shot_id"] not in existing]
                print(f"  [REUSE] {len(existing)}/{len(mshots)} frames exist, {len(missing)} missing: {missing}")
                print(f"  [REUSE] Generating missing frames only...")
                mshots_missing = [s for s in mshots if s["shot_id"] in missing]
                # Reuse existing, generate missing
                all_frames.update(existing)
                judge_scores.update({sid: 0.75 for sid in existing})
                with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
                    futs = {pool.submit(gen_frame, s, cast, locs, sb_scene, contract, mode,
                                       frame_dir, location_text, dry_run): s["shot_id"] for s in mshots_missing}
                    for f in as_completed(futs):
                        sid = futs[f]
                        try:
                            result = f.result()
                            if result:
                                p, score = (result if isinstance(result, tuple) else (result, 0.75))
                                if p:
                                    all_frames[sid] = p
                                    judge_scores[sid] = score
                        except Exception as e:
                            print(f"  [FRAME] {sid}: ERROR — {e}")
        else:
            # V36.2/V37.1: Chain-only shots skip first-frame generation in --frames-only.
            # _cold_open_chain_only: M02+ on DIALOGUE_OPENER/COLD_OPEN scenes (set above).
            # _chain_inherits_start: M02+ on ALL other scenes (set by universal block above).
            # Both mean the same thing: this shot gets its start_image from the Kling
            # end-frame chain — generating a standalone Nano frame would be wasted work.
            def _is_chain_only(s):
                return s.get("_cold_open_chain_only") or s.get("_chain_inherits_start")
            _gen_shots = [s for s in mshots if not _is_chain_only(s)]
            _skipped_chain = [s for s in mshots if _is_chain_only(s)]
            if _skipped_chain:
                print(f"  [CHAIN-FRAME] Skipping Nano for {len(_skipped_chain)} chain-only shots: "
                      f"{[s['shot_id'] for s in _skipped_chain]}")
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
                futs = {pool.submit(gen_frame, s, cast, locs, sb_scene, contract, mode,
                                   frame_dir, location_text, dry_run): s["shot_id"] for s in _gen_shots}
                for f in as_completed(futs):
                    sid = futs[f]
                    try:
                        result = f.result()
                        if result:
                            # WIRE 1: handle both old path-only and new (path, score) tuple
                            if isinstance(result, tuple):
                                p, score = result
                            else:
                                p, score = result, 0.75
                            if p:
                                all_frames[sid] = p
                                judge_scores[sid] = score
                    except Exception as e:
                        print(f"  [FRAME] {sid}: ERROR — {e}")
        print(f"\n  Frames: {len(all_frames)}/{len(mshots)} | Avg I-score: {sum(judge_scores.values())/max(len(judge_scores),1):.2f}")

        if not all_frames:
            print("  FAIL — no frames"); return

        # ── PRE-VIDEO QUALITY GATE (V31.1) ───────────────────────────────────
        # Holistic canonical-match scoring: location + identity + blocking + mood.
        # Runs AFTER Wire A (identity-only), BEFORE Kling video generation.
        # Catches frames where the location is wrong, blocking is wrong, or mood is
        # wrong — things Wire A never checks. Auto-regens with diagnostic injection.
        # NON-BLOCKING: any exception → all frames pass through unchanged.
        # Skipped in --videos-only (frames already human-approved).
        # Skipped in --frames-only: the gate still runs (improves filmstrip quality),
        # but we don't gate on it for the AWAITING_APPROVAL write below.
        if PRE_VIDEO_GATE_AVAILABLE:
            try:
                from pre_video_gate import MAX_GATE_REGENS as _PVG_MAX_REGENS
            except ImportError:
                _PVG_MAX_REGENS = 2
            try:
                _pvg = PreVideoGate()
                _pvg.reset_scene(scene_id)
                _pvg_improved = 0
                _pvg_flagged  = 0
                print(f"\n  [PRE-VIDEO-GATE] V31.1 holistic scoring {len(all_frames)} frames "
                      f"(loc + identity + blocking + mood) — max {_PVG_MAX_REGENS} retries/shot...")
                for _pvg_shot in mshots:
                    _pvg_sid   = _pvg_shot["shot_id"]
                    _pvg_frame = all_frames.get(_pvg_sid)
                    if not _pvg_frame:
                        continue

                    # V31.1: Enrich shot with SPATIAL_MAP room DNA so the location
                    # diagnostic says "copper pots, cast iron range" not just "wrong room".
                    _pvg_shot_work = dict(_pvg_shot)
                    _pvg_sp_key = _pvg_shot_work.get("_spatial_profile")
                    if _pvg_sp_key and not _pvg_shot_work.get("_room_dna"):
                        _pvg_sp_data = SPATIAL_MAP.get(_pvg_sp_key, {})
                        # Use e02_desc as the canonical interior description for location failures
                        _pvg_room_dna = _pvg_sp_data.get("e02_desc", "")[:160]
                        if _pvg_room_dna:
                            _pvg_shot_work["_room_dna"] = _pvg_room_dna

                    # V31.1: Proper 2-retry loop (was 1 regen + 1 re-check without regen)
                    _pvg_current_frame = _pvg_frame
                    for _pvg_attempt in range(_PVG_MAX_REGENS + 1):
                        _pvg_result = _pvg.gate(_pvg_current_frame, _pvg_shot_work, cast)

                        # PASS or FLAG-only (no regen needed) → stop loop
                        if not _pvg_result.regen_prompt_injection:
                            if _pvg_result.score and _pvg_result.score.verdict == "FLAG":
                                _pvg_flagged += 1
                            break

                        # Budget exhausted → flag and stop
                        if _pvg_attempt >= _PVG_MAX_REGENS:
                            _pvg_shot["_pvg_status"] = f"GATE_FAIL_AFTER_{_PVG_MAX_REGENS}_REGENS"
                            _pvg_flagged += 1
                            print(f"    [PRE-VIDEO-GATE] {_pvg_sid}: budget exhausted "
                                  f"({_PVG_MAX_REGENS}/{_PVG_MAX_REGENS}) — flagged for review")
                            break

                        # Inject diagnostic and regen
                        _pvg_shot_work["_pvg_diagnostic"] = _pvg_result.regen_prompt_injection
                        print(f"    [PRE-VIDEO-GATE] {_pvg_sid}: attempt {_pvg_attempt+1} → REGEN")
                        _pvg_new = gen_frame(
                            _pvg_shot_work, cast, locs, sb_scene, contract,
                            mode, frame_dir, location_text, dry_run
                        )
                        if _pvg_new:
                            _pvg_path, _pvg_score = (
                                _pvg_new if isinstance(_pvg_new, tuple) else (_pvg_new, 0.75)
                            )
                            if _pvg_path:
                                _pvg_current_frame         = _pvg_path
                                all_frames[_pvg_sid]       = _pvg_path
                                judge_scores[_pvg_sid]     = _pvg_score
                                _pvg_improved             += 1
                        else:
                            break  # gen_frame failed — stop retrying this shot

                print(
                    f"  [PRE-VIDEO-GATE] Done — "
                    f"{_pvg_improved} regen'd, {_pvg_flagged} flagged for review, "
                    f"{len(all_frames) - _pvg_improved - _pvg_flagged} clean"
                )
            except Exception as _pvg_err:
                print(f"  [PRE-VIDEO-GATE] Gate exception ({_pvg_err}) — proceeding without")
        # ─────────────────────────────────────────────────────────────────────

    if not videos_only:  # FIX-ERR-02: don't overwrite approval status when using existing frames
        # ═══ V29.16 VALIDATION GATE ═══
        # Write first frame paths + AWAITING_APPROVAL status back to shot_plan so the UI
        # shows the filmstrip immediately. User reviews blocking/composition in the UI,
        # then runs --videos-only to continue. This replaces the 3-candidate lottery.
        try:
            _sp_path = pdir / "shot_plan.json"
            _sp_raw = json.load(open(_sp_path))
            _is_list_sp = isinstance(_sp_raw, list)
            _sp_shots = _sp_raw if _is_list_sp else _sp_raw.get("shots", [])
            for _shot in _sp_shots:
                _sid = _shot.get("shot_id", "")
                if _sid in all_frames:
                    _shot["first_frame_url"] = all_frames[_sid]
                    _shot["first_frame_path"] = all_frames[_sid]
                    _shot["_frame_identity_score"] = round(judge_scores.get(_sid, 0.75), 3)
                    _shot["_frame_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    if frames_only:
                        _shot["_approval_status"] = "AWAITING_APPROVAL"
                    elif not _shot.get("_approval_status"):
                        _shot["_approval_status"] = "AUTO_APPROVED"
            import shutil as _shutil
            _shutil.copy(_sp_path, str(_sp_path) + f".backup_framewrite_{int(time.time())}")
            with open(_sp_path, "w") as _f:
                json.dump(_sp_raw, _f, indent=2)
            # Invalidate UI cache so filmstrip shows frames immediately
            (_pdir_cache := pdir / "ui_cache").mkdir(exist_ok=True)
            (_pdir_cache / "bundle.dirty").touch()
            _status_word = "AWAITING_APPROVAL" if frames_only else "AUTO_APPROVED"
            print(f"  [UI] {len(all_frames)} first frames written to shot_plan → filmstrip shows frames ({_status_word})")
            # ── V37: register each frame + log cost (non-blocking) ──
            if _V37_GOVERNANCE:
                try:
                    for _v37_sid, _v37_fpath in all_frames.items():
                        _v37_shot = next((s for s in _sp_shots if s.get("shot_id") == _v37_sid), {})
                        _v37_register_asset(_v37_fpath, "first_frame", {
                            "episode_id": project, "scene_id": scene_id, "shot_id": _v37_sid,
                            "characters": _v37_shot.get("characters", []),
                            "model_used": "fal-ai/nano-banana-pro",
                            "qc_score": judge_scores.get(_v37_sid),
                            "approval_status": _v37_shot.get("_approval_status", "PENDING"),
                        })
                        _v37_log_cost(project, scene_id, _v37_sid, "fal_nano_banana_pro")
                except Exception as _v37_e:
                    print(f"  [V37] WARNING: governance hook failed (non-blocking): {_v37_e}")
        except Exception as _e:
            print(f"  [UI] WARNING: Could not write frames to shot_plan ({_e})")

    # ─── V32.0 SPATIAL COMPARISON GATE ────────────────────────────────────────
    # After frames are generated, compare E01/E02/E03 (and first M-shot) to verify
    # each shot shows a DISTINCT camera position. If any pair looks identical, flags
    # it with a specific reprompt suggestion before the operator reviews.
    # NON-BLOCKING: unavailable Gemini key → logs warning and skips.
    if _SPATIAL_GATE_AVAILABLE and all_frames:
        try:
            _spatial_result = run_spatial_gate(str(pdir), scene_id)
            _save_spatial_gate(str(pdir), scene_id, _spatial_result)
            if not _spatial_result.get("all_distinct", True):
                print(f"\n  [SPATIAL-GATE] ⚠️  Spatial distinctiveness issues detected for scene {scene_id}.")
                print(f"  Review reprompt suggestions in: pipeline_outputs/{project}/spatial_gate_results/{scene_id}_spatial_gate.json")
        except Exception as _sge:
            print(f"  [SPATIAL-GATE] WARNING: gate failed ({_sge}) — proceeding")

    # --frames-only: STOP HERE. User reviews filmstrip in UI, then runs --videos-only
    if frames_only:
        print(f"\n{'='*60}")
        print(f"  FRAMES ONLY MODE — {len(all_frames)}/{len(mshots)} frames generated")
        print(f"  Review the filmstrip in ATLAS Auto Studio UI.")
        print(f"  When satisfied, run:")
        print(f"    python3 atlas_universal_runner.py {project} {scene_id} --mode {mode} --videos-only")
        print(f"{'='*60}")
        return

    # --videos-only: Phase 1 skipped by guard at top of scene function (FIX-ERR-02)
    # approved frames already loaded into all_frames from disk

    # ─── UI APPROVAL GATE (V30.0) ──────────────────────────────────────────────
    # Read _approval_status from shot_plan (set by UI thumbs-up/thumbs-down).
    # REGEN_REQUESTED  → frame was thumbs-downed; regen before video generation
    # AWAITING_APPROVAL → not yet reviewed; skip video gen for this shot (warn)
    # APPROVED / AUTO_APPROVED → proceed normally
    # ────────────────────────────────────────────────────────────────────────────
    try:
        _sp_approval_path = pdir / "shot_plan.json"
        _sp_approval_raw = json.load(open(_sp_approval_path))
        _sp_approval_shots = (
            _sp_approval_raw if isinstance(_sp_approval_raw, list)
            else _sp_approval_raw.get("shots", [])
        )
        _approval_map = {
            s.get("shot_id"): s.get("_approval_status", "AUTO_APPROVED")
            for s in _sp_approval_shots
        }
    except Exception as _ae:
        print(f"  [APPROVAL-GATE] WARNING: Could not read approval statuses ({_ae}) — proceeding")
        _approval_map = {}

    # — Handle REGEN_REQUESTED shots (thumbs-down) —
    _regen_requested = [
        sid for sid, status in _approval_map.items()
        if status == "REGEN_REQUESTED" and sid in all_frames
    ]
    if _regen_requested:
        print(f"\n  [APPROVAL-GATE] {len(_regen_requested)} shot(s) marked REGEN_REQUESTED (thumbs-down):")
        for _rsid in _regen_requested:
            print(f"    → {_rsid}: re-generating first frame (new seed + resolution bump)")
        # Re-run frame gen for just these shots using the same gen_frame path
        _regen_shots = [s for s in mshots if s["shot_id"] in _regen_requested]
        try:
            for _rs in _regen_shots:
                _rsid = _rs["shot_id"]
                # Archive old frame before regen
                _old_frame = Path(all_frames.get(_rsid, ""))
                if _old_frame.exists():
                    _archive_dir = pdir / "_archived_runs" / f"thumbsdown_{int(time.time())}"
                    _archive_dir.mkdir(parents=True, exist_ok=True)
                    import shutil as _shutil_regen
                    _shutil_regen.copy(str(_old_frame), str(_archive_dir / _old_frame.name))
                    print(f"    [ARCHIVE] {_rsid}: old frame archived to {_archive_dir.name}/")
                # Generate new frame — ONE revision with amplified identity prompt
                # T2-FE-27 + build_regen_plan: strengthen prompt before the single retry
                _rs_refs = _rs.get("_fal_image_urls_resolved") or []
                _rs_frame_path = Path(frame_dir) / f"{_rsid}.jpg"
                _rs = dict(_rs)  # don't mutate original shot
                # ── Apply regen plan escalations ──────────────────────────────
                # 1. Amplify identity: prepend [IDENTITY BOOST] block from cast_map
                _regen_chars = _rs.get("characters") or []
                _boost_lines = []
                for _rgen_cn in _regen_chars:
                    _rgen_cdata = (cast.get(_rgen_cn) or cast.get(_rgen_cn.upper()) or {})
                    _rgen_app = (_rgen_cdata.get("amplified_appearance")
                                 or _rgen_cdata.get("appearance") or _rgen_cn)
                    _boost_lines.append(
                        f"[IDENTITY BOOST — {_rgen_cn.upper()}] {_rgen_app}. "
                        f"THIS PERSON MUST BE CLEARLY VISIBLE AND RECOGNIZABLE."
                    )
                if _boost_lines:
                    _orig_np = _rs.get("nano_prompt") or _rs.get("prompt") or ""
                    _rs["nano_prompt"] = "\n".join(_boost_lines) + "\n" + _orig_np
                    print(f"    [REGEN-PLAN] {_rsid}: identity_boost applied ({len(_regen_chars)} chars amplified)")
                # 2. Force 2K resolution for retry (T2-SA-5: Smart Regen escalates resolution)
                _rs["_resolution"] = "2K"
                _rs["_identity_boost"] = True
                print(f"    [REGEN-PLAN] {_rsid}: resolution → 2K, new seed, amplified prompt ready")
                # ─────────────────────────────────────────────────────────────
                _regen_result = gen_frame(
                    _rs, cast, _rs_frame_path, refs=_rs_refs,
                    seed=int(time.time()) % 999999,  # fresh seed — 1 attempt max
                )
                if _regen_result and Path(_regen_result).exists():
                    all_frames[_rsid] = _regen_result
                    print(f"    [REGEN] {_rsid}: ✓ new frame generated → {_regen_result}")
                    # Run vision judge on new frame
                    if VISION_JUDGE_AVAILABLE:
                        try:
                            _rj = judge_frame(_rsid, _regen_result, _rs, cast)
                            judge_scores[_rsid] = (
                                sum(_rj.identity_scores.values()) / len(_rj.identity_scores)
                                if _rj.identity_scores else 0.75
                            )
                            print(f"    [VID-JUDGE] {_rsid}: I={judge_scores[_rsid]:.2f} ({_rj.verdict})")
                        except Exception as _rje:
                            print(f"    [VID-JUDGE] {_rsid}: skipped ({_rje})")
                    # Reset status to AWAITING_APPROVAL so user reviews again
                    _approval_map[_rsid] = "AWAITING_APPROVAL"
                else:
                    print(f"    [REGEN] {_rsid}: ✗ regen failed — keeping old frame")
        except Exception as _regen_err:
            print(f"  [APPROVAL-GATE] REGEN error: {_regen_err} — continuing with existing frames")

        # Write regen results back to shot_plan + invalidate UI cache
        try:
            for _rs_shot in _sp_approval_shots:
                _rsid = _rs_shot.get("shot_id", "")
                if _rsid in all_frames:
                    _rs_shot["first_frame_url"] = all_frames[_rsid]
                    _rs_shot["first_frame_path"] = all_frames[_rsid]
                    _rs_shot["_frame_identity_score"] = round(judge_scores.get(_rsid, 0.75), 3)
                if _rsid in _regen_requested:
                    _rs_shot["_approval_status"] = "AWAITING_APPROVAL"
                    _rs_shot["_regen_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(_sp_approval_path, "w") as _f:
                json.dump(_sp_approval_raw, _f, indent=2)
            (_pdir_cache := pdir / "ui_cache").mkdir(exist_ok=True)
            (_pdir_cache / "bundle.dirty").touch()
            print(f"  [APPROVAL-GATE] Regen results written to shot_plan. UI refreshed.")
            # If all regen shots are back to AWAITING_APPROVAL, warn before proceeding to video
            _still_pending = [sid for sid in _regen_requested if _approval_map.get(sid) == "AWAITING_APPROVAL"]
            if _still_pending:
                # ALWAYS stop after regen — in both frames_only AND videos_only mode.
                # User must review the revised frames before videos are generated.
                print(f"\n  ⛔ [REVISION GATE] {len(_still_pending)} shot(s) revised — AWAITING YOUR REVIEW:")
                for _sp_sid in _still_pending:
                    _score = judge_scores.get(_sp_sid, 0.0)
                    print(f"     → {_sp_sid}: new frame ready, I={_score:.2f} — review in UI")
                print(f"\n  Review revised frames in ATLAS Auto Studio → thumbs-up to approve.")
                print(f"  Then run --videos-only to generate videos for approved shots.")
                return
        except Exception as _save_err:
            print(f"  [APPROVAL-GATE] WARNING: Could not persist regen results ({_save_err})")

    # — Skip AWAITING_APPROVAL shots in video generation —
    # V30.6 FIX: Only block on shots in THIS scene (all_frames), not the entire shot_plan.
    # Tone shots from other scenes (003_E*, 005_E*, etc.) were blocking Scene 002 video gen.
    _pending_review = {
        sid for sid, status in _approval_map.items()
        if status == "AWAITING_APPROVAL" and sid in all_frames
    }
    if _pending_review:
        # HARD STOP — never generate videos for unreviewed frames.
        # "i rather fail then to run wrong" — partial scenes are worse than no scene.
        print(f"\n  ⛔ [APPROVAL GATE — HARD STOP] {len(_pending_review)} shot(s) not yet reviewed:")
        for _psid in sorted(_pending_review):
            _score = judge_scores.get(_psid, 0.0)
            print(f"     → {_psid}: AWAITING_APPROVAL (I={_score:.2f})")
        print(f"\n  ALL shots must be reviewed before video generation.")
        print(f"  Open ATLAS Auto Studio → review each frame → thumbs-up to approve, thumbs-down to revise.")
        print(f"  When all shots show APPROVED status → run --videos-only to generate videos.")
        print(f"  Reason: partial scene renders waste money and produce unusable cuts.")
        return  # Hard abort — no partial video generation
    else:
        mshots_for_video = mshots

    # Phase 2: Videos — routed by ATLAS_VIDEO_MODEL
    # V29.8: Kling (proven multi-prompt @Element) OR Seedance (ByteDance, images_list)
    # V30.0: Uses mshots_for_video (only APPROVED/AUTO_APPROVED shots from approval gate)
    first_frame = list(all_frames.values())[0]
    seedance_variant_ctx = {"models": {}, "shot_sequence": []}
    if _vid_model in ("seedance", "seeddance"):
        print(f"\nPHASE 2: SEEDANCE V2.0 (ByteDance — video-edit, images_list, {mode} quality)")
        print(f"  Shots: {len(mshots_for_video)}/{len(mshots)} (filtered by approval gate)")
        all_videos, seedance_variant_ctx = gen_scene_seedance(
            mshots_for_video, cast, first_frame, mode, video_dir,
            scene_id=scene_id, locs=locs, location_text=location_text, all_frames=all_frames)
    else:
        print(f"\nPHASE 2: KLING v3/pro MULTI-SHOT (proven format — beat actions, @Element identity) [{gen_mode.upper()} mode]")
        print(f"  Shots: {len(mshots_for_video)}/{len(mshots)} (filtered by approval gate)")
        all_videos = gen_scene_multishot(mshots_for_video, cast, contract, first_frame, mode, video_dir, context,
                                         gen_mode=gen_mode, all_frames=all_frames)

    # Collect videos in scene order for stitch
    videos = []
    ordered_shot_ids: List[str] = []
    seen_paths = set()
    for s in mshots_for_video:
        sid = s["shot_id"]
        if sid in all_videos:
            path = all_videos[sid]
            if path not in seen_paths:  # multi_prompt groups share one video file
                videos.append(path)
                seen_paths.add(path)
                ordered_shot_ids.append(sid)

    # Phase 2b: Extract last frames for chaining reference
    print(f"\nPHASE 2b: CHAIN FRAMES ({len(videos)} videos)")
    for vpath in videos:
        chain_frame = os.path.join(frame_dir, os.path.basename(vpath).replace('.mp4', '_lastframe.jpg'))
        extract_last_frame(vpath, chain_frame)

    print(f"  Videos: {len(videos)} | Multi-shot groups: {len(set(all_videos.values()))}")

    # Phase 2c: PARALLEL POST-VIDEO VISION ANALYSIS
    # Runs on all completed videos simultaneously: frozen detection + identity check on first/last frame
    print(f"\nPHASE 2c: POST-VIDEO VISION ANALYSIS (parallel — {len(videos)} videos)")
    video_vision = {}  # sid -> {"frozen": bool, "identity_score": float, "V_score": float}

    def _analyze_video(s):
        sid = s["shot_id"]
        # ERR-01 FIX: Seedance saves as {scene_id}_seedance_group_NN.mp4, not {sid}.mp4
        # Use the actual path from all_videos dict; fallback to legacy name for Kling
        vpath = all_videos.get(sid, os.path.join(video_dir, f"{sid}.mp4"))
        chars = s.get("characters") or []
        result = {"frozen": False, "identity_score": 0.75, "V_score": 0.8}
        if not os.path.exists(vpath):
            result["V_score"] = 0.0
            return sid, result

        # 1. Frozen detection (ffmpeg first/last frame diff)
        frozen = _check_frozen(vpath)
        result["frozen"] = frozen
        result["V_score"] = 0.3 if frozen else 0.85
        if frozen:
            print(f"  [VISION] {sid}: ⚠ FROZEN DETECTED")
            # ── WIRE C: AUTO-REGEN FROZEN VIDEO (V30.0) ───────────────────────────
            # Seedance occasionally renders static frames instead of motion.
            # One retry with an explicit "CONTINUOUS MOTION REQUIRED" prompt fix.
            # Only retries for Seedance (not Kling — Kling frozen threshold is 3KB).
            _s_data = next((ss for ss in mshots if ss.get('shot_id') == sid), None)
            if _s_data and _vid_model in ('seedance', 'seeddance') and MUAPI_KEY:
                print(f"  [WIRE-C] {sid}: Attempting frozen video regen — motion-boosted prompt")
                try:
                    _fc_prompt = (_s_data.get('_seedance_prompt') or
                                  _s_data.get('_beat_action') or
                                  _s_data.get('description') or 'Character moves naturally in scene')
                    _fc_prompt = _fc_prompt[:400] + " CONTINUOUS MOTION REQUIRED. Do not freeze. Fluid natural movement throughout."
                    _fc_start = _s_data.get('first_frame_url') or _s_data.get('first_frame_path') or ''
                    _fc_start_url = upload_public(_fc_start) if _fc_start and os.path.exists(_fc_start) else None
                    if _fc_start_url:
                        _fc_dur = int(str(_s_data.get('duration', '5')).strip())
                        _fc_dur = max(5, min(_fc_dur, 15))
                        _fc_video = gen_seedance_video(_fc_prompt, [_fc_start_url], duration=_fc_dur, quality='basic')
                        if _fc_video and os.path.exists(_fc_video):
                            _fc_frozen2 = _check_frozen(_fc_video)
                            if not _fc_frozen2:
                                shutil.copy2(_fc_video, vpath)
                                os.remove(_fc_video)
                                result['frozen'] = False
                                result['V_score'] = 0.85
                                _track_cost('seedance', duration=_fc_dur)
                                print(f"  [WIRE-C] {sid}: ✓ frozen regen SUCCESS — V_score restored to 0.85")
                            else:
                                print(f"  [WIRE-C] {sid}: ✗ regen still frozen — flagging for manual review")
                                os.remove(_fc_video)
                        else:
                            print(f"  [WIRE-C] {sid}: regen call failed — keeping frozen flag")
                    else:
                        print(f"  [WIRE-C] {sid}: no start frame URL — skipping auto-regen")
                except Exception as _wc_err:
                    print(f"  [WIRE-C] {sid}: regen exception ({_wc_err}) — keeping frozen flag")
            # ────────────────────────────────────────────────────────────────────────

        # 2. Identity check on video's first frame (char shots only)
        if chars and VISION_JUDGE_AVAILABLE:
            try:
                first_frame_check = vpath + "_vcheck.jpg"
                subprocess.run(["ffmpeg", "-y", "-i", vpath, "-vframes", "1",
                               "-q:v", "2", first_frame_check], capture_output=True)
                if os.path.exists(first_frame_check):
                    shot_dict = {"shot_id": sid, "characters": chars}
                    verdict = judge_frame(sid, first_frame_check, shot_dict, cast)
                    if verdict.identity_scores:
                        id_score = sum(verdict.identity_scores.values()) / len(verdict.identity_scores)
                        result["identity_score"] = id_score
                        tag = "PASS" if verdict.verdict == "PASS" else verdict.verdict
                        print(f"  [VISION] {sid}: video I={id_score:.2f} ({tag}) frozen={frozen}")
                    os.remove(first_frame_check)
            except Exception as e:
                print(f"  [VISION] {sid}: analysis error — {e}")
        else:
            print(f"  [VISION] {sid}: frozen={frozen}")

        # Push video analysis result to live tracker
        _push_live_gen(sid, "analysed", "video", url=f"/api/media?path={vpath}")
        return sid, result

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        vfuts = {pool.submit(_analyze_video, s): s["shot_id"] for s in mshots if s["shot_id"] in all_videos}
        for f in as_completed(vfuts):
            sid = vfuts[f]
            try:
                sid_result, analysis = f.result()
                video_vision[sid_result] = analysis
            except Exception as e:
                print(f"  [VISION] {sid}: ERROR — {e}")

    frozen_count = sum(1 for v in video_vision.values() if v["frozen"])
    avg_vid_id = sum(v["identity_score"] for v in video_vision.values()) / max(len(video_vision), 1)
    print(f"  Vision complete: {len(video_vision)}/{len(videos)} | frozen={frozen_count} | avg video_I={avg_vid_id:.2f}")

    # ═══ CONSCIOUSNESS GAP 3: DOPAMINE LOOP — Reward Signal per shot ═══
    print(f"\nPHASE 2d: REWARD SIGNAL (real scores from all vision passes)")
    reward_ledger = []
    for i, s in enumerate(mshots):
        sid = s["shot_id"]
        vid_path = os.path.join(video_dir, f"{sid}.mp4")
        vision_data = video_vision.get(sid, {})
        chars = s.get("characters") or []

        # I = BEST identity score: video vision pass (most accurate) OR Phase 1 frame score
        frame_I = judge_scores.get(sid, 0.75)
        video_I = vision_data.get("identity_score", frame_I)
        I_score = max(frame_I, video_I)

        # D = doctrine compliance
        D_score = len(gate_result["passed"]) / max(gate_result["total_checks"], 1)

        # V = real video quality from Phase 2c (frozen detection)
        V_score = vision_data.get("V_score", 0.5)

        # C = chain frames present
        # ERR-NEW-20 FIX: Seedance chain frames named from actual video basename, not sid
        # Phase 2b saves: {video_basename}_lastframe.jpg — look up from all_videos dict
        _actual_vid = all_videos.get(sid, "")
        if _actual_vid:
            chain_path = os.path.join(frame_dir, os.path.basename(_actual_vid).replace('.mp4', '_lastframe.jpg'))
        else:
            chain_path = os.path.join(frame_dir, f"{sid}_lastframe.jpg")
        C_score = 0.85 if os.path.exists(chain_path) else 0.70

        # E = efficiency (first pass = 1.0)
        E_score = 1.0

        # R = weighted composite
        R = (I_score * 0.35) + (D_score * 0.30) + (V_score * 0.15) + (C_score * 0.15) + (E_score * 0.05)

        entry = {
            "shot_id": sid, "R": round(R, 3),
            "I": round(I_score, 2), "D": round(D_score, 2),
            "V": round(V_score, 2), "C": round(C_score, 2), "E": round(E_score, 2),
            "verdict": "PASS" if R >= 0.70 else "REVIEW" if R >= 0.50 else "FAIL",
        }
        reward_ledger.append(entry)
        verdict_icon = "✓" if R >= 0.70 else "⚠" if R >= 0.50 else "✗"
        print(f"  {verdict_icon} {sid}: R={R:.3f} (I={I_score:.2f} D={D_score:.2f} V={V_score:.2f} C={C_score:.2f} E={E_score:.2f}) → {entry['verdict']}")

    # Write reward ledger
    ledger_path = str(pdir / "reward_ledger.jsonl")
    with open(ledger_path, "a") as f:
        for entry in reward_ledger:
            entry["scene_id"] = scene_id
            entry["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            f.write(json.dumps(entry) + "\n")
    avg_R = sum(e["R"] for e in reward_ledger) / max(len(reward_ledger), 1)
    print(f"\n  Avg R: {avg_R:.3f} | Written to {os.path.basename(ledger_path)}")

    # ═══ UI WRITEBACK — Sync video paths to shot_plan.json so ATLAS UI shows videos ═══
    # ROOT CAUSE FIX: Universal runner saves to videos_seedance_full/ but never updates
    # shot_plan.json. UI reads shot_plan → sees video_url=None → shows nothing.
    # Fix: after generation, write all_videos paths back to each shot in shot_plan.json
    # and invalidate the UI bundle cache so the orchestrator serves fresh data.
    try:
        _sp_path = pdir / "shot_plan.json"
        _sp_raw = json.load(open(_sp_path))
        _is_list = isinstance(_sp_raw, list)
        _all_shots = _sp_raw if _is_list else _sp_raw.get("shots", [])
        _updated = 0
        for _shot in _all_shots:
            _sid = _shot.get("shot_id", "")
            if _sid in all_videos and all_videos[_sid]:
                _vpath = all_videos[_sid]
                _shot["video_url"] = _vpath
                _shot["video_path"] = _vpath
                _shot["_seedance_video"] = _vpath
                _shot["_video_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                # V37: Persist chain_group + arc positions so chain_intelligence_gate
                # can validate chain continuity in the NEXT session without re-running
                # enrich_shots_with_arc. These fields are computed fresh each run but
                # persisting them makes the gate diagnostic reports accurate off-disk.
                _mshot_match = next(
                    (ms for ms in mshots if ms.get("shot_id") == _sid), None
                )
                if _mshot_match:
                    for _persist_field in (
                        "chain_group", "_chain_group",
                        "_arc_position", "_arc_carry_directive",
                        "_arc_release", "_gen_strategy",
                    ):
                        _pval = _mshot_match.get(_persist_field)
                        if _pval is not None:
                            _shot[_persist_field] = _pval
                _updated += 1
        # Write back preserving format (list or dict)
        import shutil
        shutil.copy(_sp_path, str(_sp_path) + f".backup_vidwrite_{int(time.time())}")
        with open(_sp_path, "w") as _f:
            json.dump(_sp_raw, _f, indent=2)
        # Invalidate UI cache — orchestrator watches for 'bundle.dirty' flag
        # T2-OR-1: UI reads ONLY from /api/v16/ui/bundle/{project}; cache invalidated after every mutation
        _cache_dir = pdir / "ui_cache"
        _cache_dir.mkdir(exist_ok=True)
        _dirty_path = _cache_dir / "bundle.dirty"
        _dirty_path.touch()
        print(f"  [UI] bundle.dirty flag set → orchestrator will rebuild bundle on next request")
        print(f"  [UI] Wrote video_url to {_updated} shots in shot_plan.json → UI will now show videos")
        # ── V37: register each video + log cost (non-blocking) ──
        if _V37_GOVERNANCE:
            try:
                for _v37_sid, _v37_vpath in all_videos.items():
                    if not _v37_vpath: continue
                    _v37_shot = next((s for s in _all_shots if s.get("shot_id") == _v37_sid), {})
                    _v37_dur = _v37_shot.get("duration", 10)
                    _v37_call_type = "fal_kling_v3_pro_5s" if _v37_dur <= 5 else "fal_kling_v3_pro_10s"
                    _v37_register_asset(_v37_vpath, "video_clip", {
                        "episode_id": project, "scene_id": scene_id, "shot_id": _v37_sid,
                        "characters": _v37_shot.get("characters", []),
                        "model_used": "fal-ai/kling-video/v3/pro/image-to-video",
                        "generation_strategy": _v37_shot.get("_gen_strategy", ""),
                        "approval_status": _v37_shot.get("_approval_status", "PENDING"),
                    })
                    _v37_log_cost(project, scene_id, _v37_sid, _v37_call_type)
            except Exception as _v37_e:
                print(f"  [V37] WARNING: governance hook failed (non-blocking): {_v37_e}")
    except Exception as _e:
        print(f"  [UI] WARNING: Could not write video paths back to shot_plan ({_e}) — UI may not reflect videos")

    # ═══ CONSCIOUSNESS GAP 2: PROPRIOCEPTION — State awareness ═══
    # Phase 1.4 FIX: Add run_flags/video_model/run_mode so every run is identifiable in history
    consciousness_state = {
        "scene_id": scene_id,
        "project": project,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": mode,
        "video_model": ACTIVE_VIDEO_MODEL,  # V29.16 NEW-J FIX: use actual runtime var, not re-read env
        "run_mode": ("reuse_frames" if reuse_frames     # FIX-ERR-07: distinguish all modes for audit trail
                     else "frames_only" if frames_only
                     else "videos_only" if videos_only
                     else "full_gen"),
        "run_flags": {                                                      # full argv for auditability
            "reuse_frames": reuse_frames,
            "frames_only": frames_only,
            "videos_only": videos_only,
            "scenes": [scene_id],
            "mode": mode,
        },
        "shots_total": len(mshots),
        "shots_generated": len(videos),
        "frames_generated": len(all_frames),
        "avg_reward": round(avg_R, 3),
        "doctrine_compliance": round(D_score, 3),
        "identity_hold_rate": round(sum(1 for e in reward_ledger if e["I"] >= 0.7) / max(len(reward_ledger), 1), 3),
        "first_pass_rate": round(sum(1 for e in reward_ledger if e["E"] >= 1.0) / max(len(reward_ledger), 1), 3),
        "frozen_count": sum(1 for e in reward_ledger if e["V"] <= 0.3),
        "cost": dict(_cost_tracker),
        "gate_result": {"blocking": len(gate_result["blocking"]), "warnings": len(gate_result["warnings"]), "passed": len(gate_result["passed"])},
        "model_routing": {sid: {"model": m, "reason": r} for sid, (m, r) in routing.items()},
    }
    state_path = str(pdir / "consciousness_state.json")
    # Read existing states and append
    existing_states = []
    if os.path.exists(state_path):
        try: existing_states = json.load(open(state_path))
        except: existing_states = []
    if not isinstance(existing_states, list): existing_states = [existing_states]
    existing_states.append(consciousness_state)
    with open(state_path, "w") as f:
        json.dump(existing_states, f, indent=2)

    # ═══ QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH ════════════════
    # "i rather fail then to run wrong" — never stitch broken shots into a cut.
    # FAIL = R < 0.50 in reward ledger. FROZEN = video_vision detected static video.
    _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
    _frozen_sids = {sid for sid, v in video_vision.items() if v.get("frozen")}
    _blocked_sids = _fail_sids | _frozen_sids
    if _blocked_sids:
        print(f"\n  ⛔ [QUALITY GATE] {len(_blocked_sids)} shot(s) BLOCKED from stitch:")
        for _bsid in sorted(_blocked_sids):
            _why = []
            if _bsid in _frozen_sids: _why.append("FROZEN — no motion detected")
            if _bsid in _fail_sids:   _why.append("FAIL — reward R < 0.50")
            print(f"     → {_bsid}: {' + '.join(_why)}")
        # Remove blocked shots from videos list
        videos = [v for v in videos
                  if not any(_bsid in os.path.basename(v) for _bsid in _blocked_sids)]
        if not videos:
            print(f"\n  ⛔ ALL shots failed quality gate — scene ABORTED. No stitch produced.")
            print(f"  Fix blocked shots (regen from UI), then re-run --videos-only.")
            return  # Hard abort — nothing to stitch
        print(f"  Stitch will proceed with {len(videos)} passing shot(s).")
    # ═════════════════════════════════════════════════════════════════════════

    if seedance_variant_ctx.get("models"):
        _stitch_seedance_variant_scenes(pdir, scene_id, tag, seedance_variant_ctx, _blocked_sids, ordered_shot_ids)

    # Phase 3: Stitch — drop duplicate first frame from chained clips
    # V36.2: End-frame chaining means video N+1's first frame IS video N's last frame.
    # They are pixel-identical. Just trim 1 frame (0.04s @25fps) from the HEAD of
    # each subsequent clip, then concat. No crossfade needed — clean cut.
    if videos:
        print(f"\nPHASE 3: STITCH (V36.2 drop-duplicate)")
        sorted_videos = sorted(videos)
        outname = f"scene{scene_id}_{tag}.mp4"
        outpath = str(pdir / outname)

        if len(sorted_videos) == 1:
            shutil.copy2(sorted_videos[0], outpath)
        elif len(sorted_videos) >= 2:
            # V36.6 FIX: Normalize ALL clips to 1920x1080 before concat.
            # Kling sometimes returns 1928x1072 or 1924x1076 — mixed resolutions
            # fed into the concat demuxer cause the encoder to use clip-1's resolution
            # as output format and stutter/freeze at the first resolution boundary.
            # Fix: re-encode clip 1 too (not "untouched"), scale all to 1920x1080.
            trimmed = []
            for i, v in enumerate(sorted_videos):
                trimmed_path = f"/tmp/stitch_{scene_id}_{tag}_trim{i}.mp4"
                cmd = ["ffmpeg", "-y"]
                if i > 0:
                    cmd += ["-ss", "0.04"]  # trim duplicate first frame from clips 2+
                cmd += [
                    "-i", v,
                    "-vf", "scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an", trimmed_path
                ]
                subprocess.run(cmd, capture_output=True)
                if os.path.exists(trimmed_path) and os.path.getsize(trimmed_path) > 1000:
                    trimmed.append(trimmed_path)
                else:
                    trimmed.append(v)  # fallback to original (may still mismatch)

            # Layer 5: concat via smart_stitcher (audio-safe, no -an)
            if _SMART_STITCHER:
                from pathlib import Path as _Path
                _smart_concat([_Path(t) for t in trimmed], _Path(outpath))
                print(f"  [Layer 5 / SMART STITCH] {len(trimmed)} clips concatenated")
            else:
                listfile = f"/tmp/stitch_{scene_id}_{tag}.txt"
                with open(listfile, "w") as f:
                    for v in trimmed:
                        f.write(f"file '{os.path.abspath(v)}'\n")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c", "copy", outpath
                ], capture_output=True)

            # Cleanup trimmed temps
            for t in trimmed:
                if "/tmp/" in t and os.path.exists(t):
                    try: os.remove(t)
                    except: pass

        if os.path.exists(outpath):
            mb = os.path.getsize(outpath) / (1024*1024)
            print(f"  [STITCH] {outname}: {mb:.1f}MB (duplicate frames dropped)")
            shutil.copy2(outpath, outname)
            print(f"  Output: {outname}")
        else:
            # Fallback: raw concat (Layer 5 smart_stitcher if available)
            print(f"  [STITCH] Trim failed — raw concat fallback")
            if _SMART_STITCHER:
                from pathlib import Path as _Path
                _smart_concat([_Path(os.path.abspath(v)) for v in sorted_videos], _Path(outpath))
            else:
                listfile = f"/tmp/stitch_{scene_id}_{tag}_raw.txt"
                with open(listfile, "w") as f:
                    for v in sorted_videos:
                        f.write(f"file '{os.path.abspath(v)}'\n")
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                               "-i", listfile, "-c:v", "copy", outpath], capture_output=True)
            if os.path.exists(outpath):
                mb = os.path.getsize(outpath) / (1024*1024)
                print(f"  [STITCH] {outname}: {mb:.1f}MB (raw concat)")
                shutil.copy2(outpath, outname)
                print(f"  Output: {outname}")

        # V36.3b: Copy stitch to final/ directory with UI-expected name format
        # UI checks: final/scene_{scene_id}.mp4 (e.g. final/scene_001.mp4)
        if os.path.exists(outpath):
            final_dir = pdir / "final"
            final_dir.mkdir(exist_ok=True)
            ui_name = f"scene_{scene_id}.mp4"
            final_path = final_dir / ui_name
            shutil.copy2(outpath, str(final_path))
            print(f"  [UI-SYNC] Copied to final/{ui_name} — now visible in gallery")

            # ── VVO CHECKPOINT C (V36.5+): POST-SCENE COHERENCE CHECK ────────────────────
            # Fires at EVERY checkpoint — runs AFTER scene stitch, ADVISORY only.
            # Two checks (both non-blocking):
            #   1. VVO scene stitch check: jarring transitions, overall quality assessment
            #   2. StoryJudge narrative check: beat coverage, pacing, emotional arc
            # Results written to chain_reports/ for operator review.
            # NEVER blocks the run — purely advisory.
            try:
                _sc_shots_all = all_shots_in_scene if 'all_shots_in_scene' in dir() else []
                if not _sc_shots_all and 'mshots' in dir():
                    _sc_shots_all = mshots
                # 1. VVO scene stitch check
                if _VVO_AVAILABLE and os.path.exists(outpath):
                    _sc_stitch_result = _vvo_scene_stitch_check(outpath, _sc_shots_all)
                    _sc_quality = _sc_stitch_result.get("overall_quality", "not_assessed")
                    _sc_jarring = _sc_stitch_result.get("jarring_transitions", [])
                    if _sc_jarring:
                        print(f"  [VVO-C] ⚠️  Scene {scene_id}: {len(_sc_jarring)} jarring transition(s) at {_sc_jarring}")
                    elif not _sc_stitch_result.get("skipped"):
                        print(f"  [VVO-C] ✓ Scene {scene_id} stitch quality: {_sc_quality}")
                    # Persist to chain_reports/ for UI display
                    try:
                        _cr_dir = pdir / "chain_reports"
                        _cr_dir.mkdir(exist_ok=True)
                        import json as _sc_json
                        _cr_path = _cr_dir / f"{scene_id}_vvo_scene_check.json"
                        _sc_stitch_result["scene_id"] = scene_id
                        _sc_stitch_result["checked_at"] = __import__('time').strftime("%Y-%m-%dT%H:%M:%S")
                        _cr_path.write_text(_sc_json.dumps(_sc_stitch_result, indent=2))
                    except Exception:
                        pass
                # 2. StoryJudge narrative coherence check
                if StoryJudge is not None and _sc_shots_all:
                    try:
                        _sj = StoryJudge(str(pdir))
                        _sv = _sj.evaluate_scene(scene_id)
                        if hasattr(_sv, 'overall_score'):
                            print(f"  [VVO-C/StoryJudge] Scene {scene_id}: narrative score {_sv.overall_score:.2f}")
                            if hasattr(_sv, 'issues') and _sv.issues:
                                for _si in _sv.issues[:3]:
                                    print(f"    [NARRATIVE] {str(_si)[:120]}")
                        elif hasattr(_sv, 'verdict'):
                            print(f"  [VVO-C/StoryJudge] Scene {scene_id}: {_sv.verdict}")
                    except Exception as _sj_err:
                        print(f"  [VVO-C/StoryJudge] advisory check skipped: {_sj_err}")
            except Exception as _sc_err:
                print(f"  [VVO-C] post-scene check exception (non-blocking): {_sc_err}")
            # ─────────────────────────────────────────────────────────────────────────────

    # ═══ LAYER 6: LYRIA UNDERTONE — between stitch and audio delivery ══════════
    # Generates a continuous bible-timed music underbed AFTER the scene is stitched.
    # The undertone file is consumed by the audio pipeline immediately below.
    # Authority: ADVISORY — failure never blocks generation or audio mixing.
    if _LYRIA_SOUNDSCAPE and not frames_only:
        try:
            print(f"\n  [Lyria] Generating scene {scene_id} undertone (Layer 6, post-stitch)...")
            _lyria_manifest = _lyria_generate_undertone(
                project_dir=pdir,
                scene_id=scene_id,
            )
            _lyria_src   = _lyria_manifest.get("source", "unknown")
            _lyria_beats = len(_lyria_manifest.get("beat_timecodes", []))
            if _lyria_src == "lyria":
                print(f"  [Lyria] ✅ Undertone generated  {_lyria_beats} beats timed  "
                      f"→ {_lyria_manifest.get('audio_path')}")
            elif _lyria_src == "cached":
                print(f"  [Lyria] ⚡ Cache hit  {_lyria_beats} beats")
            elif _lyria_src == "failed":
                print(f"  [Lyria] ⚠️  Undertone failed (non-blocking): "
                      f"{_lyria_manifest.get('error')}")
            else:
                print(f"  [Lyria] ℹ  Source={_lyria_src}")
        except Exception as _lyria_e:
            print(f"  [Lyria] WARNING: undertone hook error (non-blocking): {_lyria_e}")

    # ═══ AUDIO PIPELINE — ElevenLabs TTS + room tone + Lyria undertone ═══════
    # Three-source audio architecture (see scene_audio_mixer.py for full spec):
    #   SOURCE A — Kling audio (demusic'd: AI music stripped, SFX/foley kept)
    #   SOURCE B — Room tone bed (FFmpeg synthesis, location-matched)
    #   SOURCE C — ElevenLabs TTS (primary voice for dialogue shots)
    #   SOURCE D — Lyria undertone (continuous scene-level music underbed)
    #
    # Output: final/scene_{scene_id}_audio.mp4 (alongside silent _video_ stitch)
    # Non-blocking: failure at any stage produces a warning, never halts runner.
    # Only runs on videos_only or full-gen runs (not frames_only).
    if _AUDIO_PIPELINE and not frames_only and all_videos:
        try:
            print(f"\n  [AUDIO] Starting audio pipeline for scene {scene_id}...")

            # Collect (clip_path, shot_dict) pairs for passing shots only
            _audio_clips = []
            for _a_shot in mshots:
                _a_sid = _a_shot.get("shot_id", "")
                _a_vpath = all_videos.get(_a_sid)
                if _a_vpath and os.path.exists(_a_vpath) and _a_sid not in _blocked_sids:
                    _audio_clips.append((_a_vpath, _a_shot))

            if not _audio_clips:
                print(f"  [AUDIO] No passing clips to mix — audio pipeline skipped")
            else:
                # Generate ElevenLabs TTS for soundscape/ambient audio ONLY
                # NOTE: This is for room tone and background ambience, NOT dialogue
                # Dialogue comes from Kling's native audio output during video rendering
                _tts_map: dict = {}
                if os.environ.get("ELEVENLABS_API_KEY"):
                    print(f"  [AUDIO] Generating ElevenLabs soundscape audio...")
                    try:
                        _tts_map = _tts_generate(
                            scene_id=scene_id,
                            shots=mshots,
                            project_dir=pdir,
                            cast_map=cast,
                        )
                    except Exception as _tts_err:
                        print(f"  [AUDIO] TTS generation error (non-blocking): {_tts_err}")
                else:
                    print(f"  [AUDIO] ELEVENLABS_API_KEY not set — TTS skipped, room tone only")

                # Resolve scene location for room tone profile
                _audio_location = location_text or f"SCENE {scene_id}"

                # Resolve Lyria undertone path
                _lyria_undertone_wav = str(pdir / "soundscapes" / f"{scene_id}_undertone.wav")
                if not os.path.exists(_lyria_undertone_wav):
                    _lyria_undertone_wav = None

                # Run scene audio mix
                _audio_out = str(pdir / f"scene{scene_id}_{tag}_audio.mp4")
                print(
                    f"  [AUDIO] Mixing {len(_audio_clips)} clips | "
                    f"TTS={len(_tts_map)} shots | "
                    f"Lyria={'yes' if _lyria_undertone_wav else 'no'}"
                )
                _mix_result = _audio_mix_scene(
                    scene_id=scene_id,
                    video_clips=_audio_clips,
                    location=_audio_location,
                    output_path=_audio_out,
                    tts_audio_map=_tts_map,
                    lyria_undertone_path=_lyria_undertone_wav,
                )

                if _mix_result.get("success"):
                    _audio_mb = os.path.getsize(_audio_out) / (1024 * 1024)
                    print(
                        f"  [AUDIO] ✅ Mixed scene: {_audio_mb:.1f}MB "
                        f"({_mix_result.get('dialogue_shots',0)} dialogue + "
                        f"{_mix_result.get('ambient_shots',0)} ambient | "
                        f"TTS injected={_mix_result.get('tts_injected',0)} | "
                        f"Lyria={_mix_result.get('lyria_layered',False)} | "
                        f"profile: {_mix_result.get('profile_used','?')[:40]})"
                    )
                    # Copy to final/ for UI visibility
                    _audio_final_dir = pdir / "final"
                    _audio_final_dir.mkdir(exist_ok=True)
                    _audio_ui_name = f"scene_{scene_id}_audio.mp4"
                    shutil.copy2(_audio_out, str(_audio_final_dir / _audio_ui_name))
                    print(f"  [AUDIO] Copied to final/{_audio_ui_name}")
                else:
                    print(f"  [AUDIO] ⚠️  Mix failed: {_mix_result.get('error', 'unknown error')}")

        except Exception as _audio_pipeline_err:
            print(f"  [AUDIO] Pipeline exception (non-blocking): {_audio_pipeline_err}")
    # ═════════════════════════════════════════════════════════════════════════

    # ═══ WIRE 2: RENDER LEARNING AGENT — long-term memory after every scene ═══
    # Records reward scores, compliance rates, identity hold into permanent learning log
    try:
        from perpetual_learning import RenderLearningAgent
        rla = RenderLearningAgent()
        rla.post_render_review(project, scene_id, reward_ledger, consciousness_state)
        print(f"\n  [LEARNING] RenderLearningAgent: {len(reward_ledger)} shots reviewed — memory updated")
    except AttributeError:
        # RenderLearningAgent exists but may not have post_render_review yet
        # Log reward data manually to atlas_learning_log.jsonl
        try:
            from perpetual_learning import LearningEntry, log_learning
            import os as _os
            base_dir = str(Path(__file__).parent)
            for entry_data in reward_ledger:
                le = LearningEntry(
                    category="reward",
                    severity="low" if entry_data["R"] >= 0.70 else "medium",
                    root_cause=f"Shot {entry_data['shot_id']} scored R={entry_data['R']:.3f}",
                    fix_applied=f"I={entry_data['I']:.2f} D={entry_data['D']:.2f} V={entry_data['V']:.2f} C={entry_data['C']:.2f} E={entry_data['E']:.2f}",
                    origin_module="atlas_universal_runner.reward_signal",
                    prevention_rule=f"Verdict: {entry_data['verdict']}",
                    production_evidence=f"Scene {scene_id}, mode={mode}, project={project}",
                    session_id=time.strftime("%Y-%m-%dT%H:%M:%S")
                )
                log_learning(project, le, base_dir=_os.path.join(base_dir, "pipeline_outputs"))
            print(f"  [LEARNING] {len(reward_ledger)} reward entries logged to atlas_learning_log")
        except Exception as e2:
            print(f"  [LEARNING] Logging fallback failed: {e2}")
    except Exception as e:
        print(f"  [LEARNING] RenderLearningAgent unavailable: {e}")

    # ═══ THREE INTELLIGENCE LAYERS — post-scene write hooks (non-blocking) ═══

    # LAYER 1: Production Intelligence Graph — persist shot outcomes to SQLite
    if _PI_AVAILABLE and reward_ledger:
        try:
            _pi_inst = _PI(project_dir=pdir)
            for _entry in reward_ledger:
                # Find the shot dict for this entry
                _shot_dict = next((s for s in mshots if s.get("shot_id") == _entry.get("shot_id")), {})
                _pi_write_shot(
                    project=project,
                    scene_id=scene_id,
                    shot=_shot_dict,
                    scores={"R": _entry.get("R", 0), "I": _entry.get("I", 0),
                            "D": _entry.get("D", 0), "V": _entry.get("V", 0),
                            "C": _entry.get("C", 0), "E": _entry.get("E", 0)},
                    retries=_entry.get("retries", 0),
                    verdict=_entry.get("verdict", "PASS"),
                    model_used="kling_v3_pro",
                    project_dir=pdir,
                )
            _pi_inst.write_scene_outcome(project=project, scene_id=scene_id,
                                          reward_ledger=reward_ledger)
            _pi_inst.close()
            print(f"  [INTEL Layer 1] {len(reward_ledger)} shot outcomes written to Production Intelligence DB")
        except Exception as _pi_e:
            print(f"  [INTEL Layer 1] ProductionIntelligence write failed (non-blocking): {_pi_e}")

    # LAYER 2: Director Brain — scene close evaluation + arc health
    if _DB_AVAILABLE and reward_ledger:
        try:
            _eval = _db_scene_close(
                scene_id=scene_id,
                reward_ledger=reward_ledger,
                project_dir=pdir,
            )
            _grade     = getattr(_eval, "overall_grade", "?")
            _arc_hlth  = getattr(_eval, "arc_health", "UNKNOWN")
            _eval_notes = getattr(_eval, "notes", [])
            print(f"  [INTEL Layer 2] Director Brain scene {scene_id}: grade={_grade} arc={_arc_hlth}")
            for _note in _eval_notes[:2]:
                print(f"    → {_note}")
        except Exception as _dbe:
            print(f"  [INTEL Layer 2] DirectorBrain scene close failed (non-blocking): {_dbe}")

    # LAYER 3: Doctrine Tracker — correlate gate firings to reward scores, write analytics
    if _DT_AVAILABLE and reward_ledger:
        try:
            # Extract rule firings from generation gate result that was computed earlier
            if gate_result and isinstance(gate_result, dict):
                for _entry in reward_ledger:
                    _sid = _entry.get("shot_id", "")
                    _scores = {"R": _entry.get("R", 0), "I": _entry.get("I", 0)}
                    _dt_extract_gate(gate_result, shot_id=_sid, scores=_scores)
            # Correlate and write analytics
            _analytics_path = _dt_finalize(
                reward_ledger=reward_ledger,
                project_dir=pdir,
            )
            if _analytics_path:
                print(f"  [INTEL Layer 3] Doctrine analytics written → {_analytics_path.name}")
        except Exception as _dte:
            print(f"  [INTEL Layer 3] DoctrineTracker finalize failed (non-blocking): {_dte}")
    # ═════════════════════════════════════════════════════════════════════════

    # Phase 3.5: Smart stitcher — curated edits (master + highlight)
    # Non-blocking: if smart_stitcher fails, scene stitch still completes
    if _SMART_STITCHER and videos and scene_id == "004":  # Currently configured for scene 004
        try:
            from pathlib import Path as _ss_Path
            _underscore_path = pdir / "REALRUNNER" / "horror_underscore_trimmed.mp3"
            if _underscore_path.exists():
                print(f"\n  [SMART STITCHER] Building curated edits for scene {scene_id}...")
                try:
                    _master_out = _smart_master_edit(
                        scene_id=scene_id,
                        underscore=_underscore_path,
                        dialog_gain=0.95,
                        underscore_gain=0.35,
                    )
                    print(f"  [SMART STITCHER] Master edit ready: {_master_out}")
                except Exception as _ss_master_err:
                    print(f"  [SMART STITCHER] Master edit failed (non-blocking): {_ss_master_err}")

                try:
                    _highlight_out = _smart_highlight_edit(
                        scene_id=scene_id,
                        underscore=_underscore_path,
                        dialog_gain=0.95,
                        underscore_gain=0.35,
                    )
                    print(f"  [SMART STITCHER] Highlight edit ready: {_highlight_out}")
                except Exception as _ss_highlight_err:
                    print(f"  [SMART STITCHER] Highlight edit failed (non-blocking): {_ss_highlight_err}")
            else:
                print(f"  [SMART STITCHER] Underscore track not found, skipping curated edits")
        except Exception as _ss_err:
            print(f"  [SMART STITCHER] Curated edit generation failed (non-blocking): {_ss_err}")

    # Phase 4: Cost report
    _print_cost()

    print(f"\n{'='*70}")
    print(f"  SCENE {scene_id} {'DONE' if videos else 'FAILED'} — {len(videos)}/{len(mshots)} | {mode.upper()} V3")
    print(f"  Consciousness: R={avg_R:.3f} | Identity={consciousness_state['identity_hold_rate']:.0%} | Compliance={D_score:.0%}")
    i_str = ' '.join(f"{k.split('_M')[-1]}={v:.2f}" for k,v in judge_scores.items())
    print(f"  I-scores: {i_str}")
    print(f"{'='*70}")


def run_single_shot(project, scene_id, shot_index, mode="lite"):
    """
    Run ONE shot (frame + video) — no scene chaining, no multi_prompt dependency.
    Called from UI 'Fire Shot' button. Standalone. Clean.
    shot_index: 0-based index into auto_consolidate output for this scene.
    """
    pdir = Path("pipeline_outputs") / project
    shots_raw, sb, cast, locs = load_project(project)
    sb_scene = get_sb_scene(sb, scene_id)
    if not sb_scene:
        print(f"Scene {scene_id} not found"); return None

    cp = pdir / "scene_contracts" / f"{scene_id}_contract.json"
    if not cp.exists():
        try: enrich_project(str(pdir), [scene_id])
        except Exception as e: print(f"  enrich: {e}")
        try: compile_scene_truth(str(pdir), scene_id)
        except Exception as e: print(f"  truth: {e}")

    contract = json.load(open(cp)) if cp.exists() else {}
    shots_raw = json.load(open(pdir / "shot_plan.json"))
    if not isinstance(shots_raw, list): shots_raw = shots_raw.get("shots", [])
    mshots = auto_consolidate(sb_scene, contract, shots_raw, scene_id, cast=cast)

    if shot_index >= len(mshots):
        print(f"Shot index {shot_index} out of range ({len(mshots)} total)"); return None

    shot = mshots[shot_index]
    sid = shot["shot_id"]
    location_text = sb_scene.get("location", "")

    tag = "lite" if mode == "lite" else "full"
    frame_dir = str(pdir / "first_frames")  # V30.3: Always write to first_frames/ — UI reads from here
    video_dir = str(pdir / f"videos_kling_{tag}")
    os.makedirs(frame_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)

    _ctx_loc_path2 = get_location_ref(locs, location_text) if locs and location_text else None
    context = {
        "_room_dna": build_scene_dna(sb_scene),
        "_lighting_rig": build_scene_lighting_rig(sb_scene),
        "_location_master_path": _ctx_loc_path2,  # V36.4: visual room anchor for chain reframes
    }

    model_choice, reason = route_shot(shot)
    print(f"\n{'='*60}")
    print(f"  SINGLE SHOT: {sid} | {model_choice.upper()} | {reason}")
    print(f"  Scene {scene_id} shot {shot_index+1}/{len(mshots)} | {mode.upper()}")
    print(f"  Standalone — no chain dependency")
    print(f"{'='*60}")

    # Phase 1: First frame
    print(f"\n[FRAME] {sid}...")
    result = gen_frame(shot, cast, locs, sb_scene, contract, mode, frame_dir, location_text)
    if not result:
        print(f"  FAIL — no frame"); return None
    frame_path, judge_score = result if isinstance(result, tuple) else (result, 0.75)

    # Phase 2: Individual video — NO chaining, NO multi_prompt group dependency
    print(f"\n[VIDEO] {sid}...")
    vid = gen_video(shot, cast, contract, frame_path, mode, video_dir, context)

    if vid:
        frozen = _check_frozen(vid)
        mb = os.path.getsize(vid) / (1024*1024)
        print(f"\n  SHOT {sid}: {'FROZEN ⚠' if frozen else 'DONE ✓'} | {mb:.1f}MB | I={judge_score:.2f}")
        return {"shot_id": sid, "frame": frame_path, "video": vid,
                "identity_score": judge_score, "frozen": frozen, "mb": round(mb, 2)}
    print(f"  FAIL — no video"); return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 atlas_universal_runner.py <project> <scene_id> [scene_id...] [--mode lite|full]")
        print("")
        print("VALIDATION WORKFLOW (recommended):")
        print("  Step 1 — Frames:  python3 atlas_universal_runner.py <project> <scene> --mode lite --frames-only")
        print("           → Generates first frames, writes to UI filmstrip, STOPS for review")
        print("  Step 2 — Videos:  python3 atlas_universal_runner.py <project> <scene> --mode lite --videos-only")
        print("           → Uses approved frames, generates videos, stitches scene")
        print("")
        print("FULL AUTO (skips validation gate):")
        print("  python3 atlas_universal_runner.py <project> <scene> --mode lite")
        print("")
        print("GEN MODE (video generation strategy):")
        print("  --gen-mode chain     (default) End-frame of shot N → start of shot N+1. Temporal continuity.")
        print("  --gen-mode parallel  Each shot generates from its own first frame. Independent composition.")
        sys.exit(1)

    project = sys.argv[1]
    mode = "lite"
    scene_ids = []
    reuse_frames = False
    frames_only = False    # --frames-only: stop after first frames, write AWAITING_APPROVAL
    videos_only = False    # --videos-only: skip frame gen, use existing frames, go straight to video
    dry_run = False
    gen_mode = "chain"     # --gen-mode chain|parallel (V31.2: parallel = independent shots)
    episode_id = None      # --episode-id: series orchestrator tracking ID
    locked = True          # V37: --locked default on; --unlocked disables regression guard
    _next_is_gen_mode = False
    _next_is_episode_id = False
    for arg in sys.argv[2:]:
        if _next_is_gen_mode:
            if arg in ("chain", "parallel"):
                gen_mode = arg
            else:
                print(f"  [WARN] Unknown --gen-mode value '{arg}' — defaulting to 'chain'")
            _next_is_gen_mode = False
            continue
        if _next_is_episode_id:
            episode_id = arg
            _next_is_episode_id = False
            continue
        if arg == "--mode": continue
        elif arg == "--gen-mode": _next_is_gen_mode = True
        elif arg == "--episode-id": _next_is_episode_id = True
        elif arg in ("lite", "full"): mode = arg
        elif arg == "--reuse-frames": reuse_frames = True
        elif arg == "--frames-only": frames_only = True    # V29.16: manual validation gate
        elif arg == "--videos-only": videos_only = True
        elif arg == "--dry-run": dry_run = True         # V30.5: simulate without FAL    # V29.16: continue from approved frames
        elif arg == "--skip-gates":                      # V36.5: bypass chain intelligence gate (emergency)
            import atlas_universal_runner as _self
            _self._SKIP_CHAIN_GATES = True
            print("  [CHAIN_GATE] ⚠️  --skip-gates active — pre/post-gen quality enforcement DISABLED")
        elif arg == "--locked": locked = True           # V37: enforce run lock (default on)
        elif arg == "--unlocked":                       # V37: development override — disables regression guard
            locked = False
            print("  [RUN_LOCK] ⚠️  --unlocked active — V37 regression guard DISABLED (dev only)")
        elif arg.startswith("--"): continue
        else: scene_ids.append(arg)

    if episode_id:
        print(f"  [SERIES] Episode ID: {episode_id}")

    if not scene_ids:
        print("No scene IDs"); sys.exit(1)

    # V37 Run Lock preflight — reset singleton and announce status
    if locked and _RUN_LOCK_AVAILABLE:
        reset_run_lock()
        _rl = get_run_lock_report()
        print(f"\n🔒 V37 Run Lock Active — only verified systems will fire")
        print(f"🔒 Verified systems: {_rl['verified_count']}/7")
    elif not locked:
        print("\n⚠️  V37 Run Lock DISABLED — unlocked mode, all systems may fire")

    if len(scene_ids) == 1:
        run_scene(project, scene_ids[0], mode, reuse_frames=reuse_frames,
                  frames_only=frames_only, videos_only=videos_only, dry_run=dry_run,
                  gen_mode=gen_mode)
    else:
        # Prep all scenes sequentially first (avoid race condition)
        pdir = Path("pipeline_outputs") / project
        print(f"\n[PREP] Enriching all scenes sequentially...")
        try:
            enrich_project(str(pdir), scene_ids)
            for sid in scene_ids:
                cp = pdir / "scene_contracts" / f"{sid}_contract.json"
                if not cp.exists():
                    compile_scene_truth(str(pdir), sid)
        except Exception as e:
            print(f"  Prep error: {e}")

        print(f"\n{'='*70}")
        print(f"  PARALLEL — {len(scene_ids)} scenes, {mode.upper()} [{gen_mode.upper()} gen mode]")
        print(f"{'='*70}")
        with ThreadPoolExecutor(max_workers=len(scene_ids)) as pool:
            futs = {pool.submit(run_scene, project, sid, mode, reuse_frames,
                                frames_only, videos_only, dry_run, gen_mode): sid for sid in scene_ids}
            for f in as_completed(futs):
                sid = futs[f]
                try: f.result(); print(f"\n  Scene {sid}: DONE")
                except Exception as e: print(f"\n  Scene {sid}: ERROR — {e}")

    # V37 Run Lock final report
    if locked and _RUN_LOCK_AVAILABLE:
        _rl_final = get_run_lock_report()
        print(f"\n🔒 Run Lock Report: {_rl_final['status']}")
        if _rl_final["blocked_attempts"]:
            for _ba in _rl_final["blocked_attempts"]:
                print(f"   ⛔ Blocked: {_ba}")
