#!/usr/bin/env python3
"""
DOCTRINE CALIBRATION — Victorian Shadows EP1 Scene 001 Test Run
================================================================
Real production data from 2026-03-12 test render.
This file feeds confirmed wins and identified failures into the
Phase 4 memory system so doctrine can learn and enforce.

Run this ONCE to lock calibration. It writes to:
  - reports/doctrine_calibration.json (persistent calibration store)
  - reports/doctrine_ledger.jsonl (append-only ledger entries)

NEVER delete calibration data. It decays naturally via BeliefDecaySystem.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

PROJECT_PATH = "/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1"
REPORTS_DIR = os.path.join(PROJECT_PATH, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# ============================================================================
# CALIBRATION DATA FROM SCENE 001 TEST RUN (2026-03-12)
# ============================================================================

CALIBRATION = {
    "session_id": "calibration_ep1_s001_20260312",
    "session_number": 1,
    "timestamp": datetime.utcnow().isoformat(),
    "project": "victorian_shadows_ep1",
    "scene": "001",
    "shots_generated": 12,

    # =========================================================================
    # CONFIRMED WINS — promote to STABLE patterns (confidence 0.8+)
    # =========================================================================
    "stable_patterns": [
        {
            "pattern_id": "wardrobe_injection_working",
            "category": "wardrobe",
            "description": "Wardrobe auto-assign from story_bible + cast_map produces consistent costume across all 12 shots",
            "evidence": "User confirmed: 'wardrobe was on point! lock whatever you did'",
            "confidence": 0.95,
            "lock": True,  # NEVER regress this
            "enforcement": "Wardrobe injection MUST run before every generation. Non-blocking but MANDATORY.",
            "source_shots": ["001_001A", "001_002B", "001_003B", "001_004B", "001_005B",
                           "001_006B", "001_007B", "001_008B", "001_009B", "001_010B",
                           "001_011C", "001_012A"],
        },
        {
            "pattern_id": "dialogue_beat_injection_working",
            "category": "script_fidelity",
            "description": "CHECK 5B beat injection + PERFORMANCE MANDATORY markers produce on-point dialogue delivery",
            "evidence": "User confirmed: 'dialog and delivery!' — dialogue hits on point",
            "confidence": 0.90,
            "lock": True,
            "enforcement": "Every dialogue shot MUST have 'PERFORMANCE MANDATORY' + 'character speaks:' in LTX",
            "source_shots": ["001_005B", "001_006B", "001_007B", "001_008B", "001_009B",
                           "001_010B", "001_011C", "001_012A"],
        },
        {
            "pattern_id": "cast_map_identity_lock_working",
            "category": "identity",
            "description": "Cast map character refs + canonical names produce consistent character appearance",
            "evidence": "User confirmed: 'characters are better' — identity lock functional",
            "confidence": 0.85,
            "lock": True,
            "enforcement": "Cast map refs MUST be passed to every character shot. CANONICAL_CHARACTERS is truth.",
        },
        {
            "pattern_id": "post_fix_sanitizer_clean",
            "category": "prompt_hygiene",
            "description": "Post-fix-v16 sanitizer eliminates bio bleed, camera brands, film stock contamination",
            "evidence": "Sanitizer returned 0 fixes needed — all contaminants already clean",
            "confidence": 0.90,
            "lock": True,
            "enforcement": "Sanitizer MUST run after every fix-v16 pass. NEVER skip step 4 in pipeline.",
        },
    ],

    # =========================================================================
    # CONFIRMED FAILURES — register as TOXIC patterns (avoid/fix)
    # =========================================================================
    "toxic_patterns": [
        {
            "pattern_id": "triple_static_stacking",
            "category": "ltx_motion",
            "description": "LTX prompts with 'static camera, no movement' repeated 3x cause complete frame freeze",
            "severity": "CRITICAL",
            "evidence": "Shots 002B-004B had 3 stacked static commands — produced frozen video with zero motion",
            "fix_applied": "Stripped duplicate static/locked/zero-movement commands, kept max 1",
            "prevention": "LTX prompt builder MUST deduplicate motion commands. Max 1 static directive per prompt.",
            "affected_shots": ["001_002B", "001_003B", "001_004B"],
        },
        {
            "pattern_id": "generic_action_causes_duplicate_frames",
            "category": "nano_prompt",
            "description": "Generic 'Character action: Character experiences...' produces identical frames across shots",
            "severity": "CRITICAL",
            "evidence": "MD5 check: 006B=008B=010B (identical), 005B=009B (identical) — same frames reused",
            "fix_applied": "Injected shot-specific blocking/action per beat into each nano prompt",
            "prevention": "Every shot MUST have unique Character action derived from its specific beat. NEVER use generic template.",
            "affected_shots": ["001_005B", "001_006B", "001_007B", "001_008B", "001_009B", "001_010B"],
        },
        {
            "pattern_id": "static_hold_start_kills_performance",
            "category": "ltx_motion",
            "description": "'0-3s static hold' at start of dialogue shots creates visible pause before performance",
            "severity": "WARNING",
            "evidence": "User reported 'pausing stillness' — 3s of nothing before actors speak",
            "fix_applied": "Reduced to '0-1s settle' for dialogue shots",
            "prevention": "Dialogue shots start with '0-1s settle' max. NEVER '0-3s static hold' on dialogue.",
        },
        {
            "pattern_id": "dialogue_duration_underallocation",
            "category": "runtime",
            "description": "Duration allocation doesn't account for dialogue word count, cutting off speech",
            "severity": "WARNING",
            "evidence": "Shot 006B: 8s for 16 words (needs 8.5s), Shot 009B: 14s for 32 words (needs 15.4s)",
            "fix_applied": "Duration protection: min_duration = words/2.3 + 1.5s buffer",
            "prevention": "Runtime contract MUST protect dialogue: duration >= ceil(word_count / 2.3) + 1.5",
            "affected_shots": ["001_006B", "001_009B"],
        },
        {
            "pattern_id": "force_legacy_bypass",
            "category": "doctrine_violation",
            "description": "Using force_legacy:true bypasses master chain, defeating the entire reframe pipeline",
            "severity": "CRITICAL",
            "evidence": "Zero angle variants generated — all B-angle shots with no coverage diversity",
            "fix_applied": "NONE YET — must wire master chain through doctrine",
            "prevention": "NEVER use force_legacy:true in production. Master chain is the ONLY generation path.",
        },
        {
            "pattern_id": "doctrine_bypass_as_fix",
            "category": "doctrine_violation",
            "description": "Downgrading gate REJECTs to WARNs and making exceptions non-blocking defeats doctrine",
            "severity": "CRITICAL",
            "evidence": "3 doctrine bypasses this session — EXECUTIVE_LAW_02, phase_exception, route guard",
            "fix_applied": "NONE YET — gates must be fixed properly, not bypassed",
            "prevention": "When a doctrine gate REJECTs, FIX THE DATA not the gate. Downgrades require user approval.",
        },
    ],

    # =========================================================================
    # PARAMETER LOCKS — exact values that produced good results
    # =========================================================================
    "parameter_locks": {
        "wardrobe_schema": "17.7.5",
        "wardrobe_auto_assign": True,
        "wardrobe_carry_forward": True,
        "dialogue_pace_wps": 2.3,  # words per second for duration calc
        "dialogue_buffer_s": 1.5,   # seconds buffer after speech
        "dialogue_settle_s": 1.0,   # max settle time before dialogue starts
        "max_static_directives": 1,  # max "static" commands per LTX prompt
        "performance_mandatory": True,  # PERFORMANCE MANDATORY prefix on all dialogue LTX
        "character_speaks_marker": True,  # character speaks: in all dialogue LTX
        "cast_map_canonical_only": True,  # no alias entries in cast_map
        "post_fix_sanitizer_mandatory": True,  # always run after fix-v16
        "nano_model": "fal-ai/nano-banana-pro",
        "nano_edit_model": "fal-ai/nano-banana-pro/edit",
        "ltx_model": "fal-ai/ltx-2/image-to-video/fast",
        "resolution_hero": "2K",
        "resolution_production": "1K",
    },

    # =========================================================================
    # GENERATION PROTOCOL — the correct order (doctrine-enforced)
    # =========================================================================
    "generation_protocol": {
        "description": "Master chain is the ONLY generation path. No force_legacy.",
        "steps": [
            "1. doctrine_runner.session_open()",
            "2. doctrine_runner.scene_initialize(scene_shots, manifest, bible, cast_map)",
            "3. FOR each shot in scene:",
            "   3a. pre_result = doctrine_runner.pre_generation(shot, context)",
            "   3b. IF pre_result.can_proceed: generate via master chain (NOT force_legacy)",
            "   3c. post_result = doctrine_runner.post_generation(shot, context)",
            "   3d. IF NOT post_result.accepted: queue for regen or manual review",
            "4. doctrine_runner.scene_complete(scene_id)",
            "5. Stitch via /api/v16/stitch/run (with pre-stitch LOA gate)",
            "6. doctrine_runner.session_close()",
        ],
        "forbidden": [
            "force_legacy: true",
            "Bypassing doctrine gates by downgrading REJECT to WARN",
            "Making phase_exception non-blocking without user approval",
            "Running generate-first-frames outside of master chain",
            "Manual FFmpeg stitch without pre-stitch LOA gate",
        ],
    },
}


def write_calibration():
    """Write calibration data to persistent store and ledger."""
    cal_path = os.path.join(REPORTS_DIR, "doctrine_calibration.json")
    ledger_path = os.path.join(REPORTS_DIR, "doctrine_ledger.jsonl")

    # Load existing calibration (merge, don't overwrite)
    existing = {}
    if os.path.exists(cal_path):
        with open(cal_path) as f:
            existing = json.load(f)

    # Merge: append new patterns, don't duplicate by pattern_id
    existing_stable_ids = {p["pattern_id"] for p in existing.get("stable_patterns", [])}
    existing_toxic_ids = {p["pattern_id"] for p in existing.get("toxic_patterns", [])}

    merged = {
        "last_calibration": CALIBRATION["timestamp"],
        "session_count": existing.get("session_count", 0) + 1,
        "stable_patterns": existing.get("stable_patterns", []),
        "toxic_patterns": existing.get("toxic_patterns", []),
        "parameter_locks": {**existing.get("parameter_locks", {}), **CALIBRATION["parameter_locks"]},
        "generation_protocol": CALIBRATION["generation_protocol"],
    }

    for sp in CALIBRATION["stable_patterns"]:
        if sp["pattern_id"] not in existing_stable_ids:
            merged["stable_patterns"].append(sp)

    for tp in CALIBRATION["toxic_patterns"]:
        if tp["pattern_id"] not in existing_toxic_ids:
            merged["toxic_patterns"].append(tp)

    # Write calibration
    with open(cal_path, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"Calibration written: {cal_path}")
    print(f"  {len(merged['stable_patterns'])} stable patterns locked")
    print(f"  {len(merged['toxic_patterns'])} toxic patterns registered")
    print(f"  {len(merged['parameter_locks'])} parameter locks set")

    # Append to ledger
    ledger_entry = {
        "timestamp": CALIBRATION["timestamp"],
        "session_id": CALIBRATION["session_id"],
        "event": "CALIBRATION_WRITE",
        "stable_count": len(CALIBRATION["stable_patterns"]),
        "toxic_count": len(CALIBRATION["toxic_patterns"]),
        "parameter_locks": list(CALIBRATION["parameter_locks"].keys()),
    }
    with open(ledger_path, "a") as f:
        f.write(json.dumps(ledger_entry) + "\n")
    print(f"Ledger entry appended: {ledger_path}")


if __name__ == "__main__":
    write_calibration()
