#!/usr/bin/env python3
"""
ATLAS V30.4 DEPLOY SCRIPT
==========================
Applies 3 surgical patches to atlas_universal_runner.py in-place.
Run from: ~/Desktop/ATLAS_CONTROL_SYSTEM/
Usage:    python3 DEPLOY_V30.4.py

PATCHES:
  1. OTSEnforcer import block (Wire D — screen position lock for CLI runs)
  2. Location master ALWAYS included in gen_frame (fixes room drift on 2-char shots)
  3. Wire D initialization in run_scene() (establish_screen_positions on full shot list)
"""

import sys
import shutil
from pathlib import Path

TARGET = Path(__file__).parent / "atlas_universal_runner.py"
BACKUP = Path(__file__).parent / "atlas_universal_runner.py.backup_v30.3_pre_v30.4"

print("ATLAS V30.4 DEPLOY")
print("=" * 50)

# ── Confirm backup exists ──────────────────────────────────────────────────
if not BACKUP.exists():
    print(f"  ERROR: Backup not found at {BACKUP.name}")
    print("  Expected pre-V30.4 backup. Cannot proceed safely.")
    sys.exit(1)
print(f"  Backup confirmed: {BACKUP.name}")

# ── Read current file ──────────────────────────────────────────────────────
if not TARGET.exists():
    print(f"  ERROR: Target not found: {TARGET}")
    sys.exit(1)

content = TARGET.read_text(encoding="utf-8")
original_len = len(content)
print(f"  File loaded: {original_len} chars, {content.count(chr(10))} lines")

# Skip if already patched
if "Wire D (2026-03-23)" in content:
    print("\n  Already patched to V30.4. Nothing to do.")
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════════════
# PATCH 1: OTSEnforcer import block
# Insert after kling_prompt_compiler import line
# ══════════════════════════════════════════════════════════════════════════
OLD_IMPORT = "from kling_prompt_compiler import compile_video_for_kling, compile_for_kling"
NEW_IMPORT = """from kling_prompt_compiler import compile_video_for_kling, compile_for_kling

# ── SCREEN POSITION LOCK — Wire D (V30.4) ──────────────────────────────────
# OTSEnforcer wired here so CLI runs enforce the 180° rule + character blocking.
# Previously only wired in orchestrator_server.py (UI path) and atlas_v26_controller.py.
# CLI generation was blind to blocking → characters drifted between shots.
# NON-BLOCKING: degrades gracefully if ots_enforcer.py is missing.
try:
    from ots_enforcer import OTSEnforcer as _OTSEnforcer
    _OTS_AVAILABLE = True
except ImportError:
    _OTSEnforcer = None
    _OTS_AVAILABLE = False"""

if OLD_IMPORT not in content:
    print("  ERROR: Patch 1 anchor not found. File may have changed.")
    sys.exit(1)

content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
print("  Patch 1 applied: OTSEnforcer import block")

# ══════════════════════════════════════════════════════════════════════════
# PATCH 2: Location master ALWAYS included — remove broken < 2 guard
# ══════════════════════════════════════════════════════════════════════════
OLD_LOC = """    _has_loc_ref = False
    if len(image_urls) < 2:
        loc = get_location_ref(locs, location_text)
        if loc:
            url = upload(loc)
            if url:
                image_urls.append(url)
                _has_loc_ref = True"""

NEW_LOC = """    # V30.4 FIX: Location master ALWAYS included — remove the broken `< 2` guard.
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
    loc = get_location_ref(locs, location_text)
    if loc:
        url = upload(loc)
        if url:
            image_urls.append(url)
            _has_loc_ref = True"""

if OLD_LOC not in content:
    print("  ERROR: Patch 2 anchor not found. File may have changed.")
    sys.exit(1)

content = content.replace(OLD_LOC, NEW_LOC, 1)
print("  Patch 2 applied: Location master always included in gen_frame")

# ══════════════════════════════════════════════════════════════════════════
# PATCH 3: Wire D initialization in run_scene()
# Insert after the tone injection block, before "# Step 3: Generation gate"
# ══════════════════════════════════════════════════════════════════════════
OLD_GATE = """    # Step 3: Generation gate
    from generation_gate import run_gate, print_gate_report"""

NEW_GATE = """    # ── WIRE D: SCREEN POSITION LOCK (V30.4 — T2-FE-20) ────────────────────────
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

    # Step 3: Generation gate
    from generation_gate import run_gate, print_gate_report"""

if "from generation_gate import run_gate, print_gate_report" not in content:
    print("  ERROR: Patch 3 anchor not found. File may have changed.")
    sys.exit(1)

content = content.replace(OLD_GATE, NEW_GATE, 1)
print("  Patch 3 applied: Wire D OTSEnforcer initialization in run_scene()")

# ══════════════════════════════════════════════════════════════════════════
# Update version header
# ══════════════════════════════════════════════════════════════════════════
content = content.replace(
    "ATLAS UNIVERSAL RUNNER V30.1 — Strategic Sequential Test Build",
    "ATLAS UNIVERSAL RUNNER V30.4 — Wire D: Screen Position Lock + Location Master Fix",
    1
)
content = content.replace(
    "Wire C (2026-03-21): AUTO-REGEN FROZEN VIDEO — motion-boosted Seedance retry in _analyze_video",
    "Wire C (2026-03-21): AUTO-REGEN FROZEN VIDEO — motion-boosted Seedance retry in _analyze_video\nWire D (2026-03-23): SCREEN POSITION LOCK — OTSEnforcer wired into CLI runner (was UI-only)",
    1
)

# ── Verify patches are present ─────────────────────────────────────────────
checks = [
    ("OTS import block",     "from ots_enforcer import OTSEnforcer as _OTSEnforcer"),
    ("Location master fix",  "V30.4 FIX: Location master ALWAYS included"),
    ("Wire D init block",    "WIRE D: SCREEN POSITION LOCK"),
    ("establish_screen call","establish_screen_positions(mshots)"),
]
bad_guard = "    if len(image_urls) < 2:\n        loc = get_location_ref" in content

print("\nVERIFICATION:")
all_ok = True
for name, pat in checks:
    ok = pat in content
    print(f"  {'OK' if ok else 'FAIL'}: {name}")
    if not ok:
        all_ok = False
print(f"  {'OK' if not bad_guard else 'FAIL'}: Old broken guard removed")
if bad_guard:
    all_ok = False

if not all_ok:
    print("\n  ABORT: Verification failed — file not written")
    sys.exit(1)

# ── Write ──────────────────────────────────────────────────────────────────
TARGET.write_text(content, encoding="utf-8")
new_len = len(content)
print(f"\n  Written: {new_len} chars ({new_len - original_len:+d}), {content.count(chr(10))} lines")
print(f"  Target:  {TARGET}")
print(f"  Backup:  {BACKUP.name}")

# ── Syntax check ───────────────────────────────────────────────────────────
import ast
try:
    ast.parse(content)
    print("\n  SYNTAX: OK")
except SyntaxError as e:
    print(f"\n  SYNTAX ERROR: {e}")
    print("  ROLLING BACK to backup...")
    shutil.copy(BACKUP, TARGET)
    print("  Rollback complete.")
    sys.exit(1)

print("\n" + "=" * 50)
print("  DEPLOY SUCCESS — V30.4 active")
print("=" * 50)
print("\nNext steps:")
print("  1. python3 tools/session_enforcer.py")
print("  2. python3 atlas_universal_runner.py victorian_shadows_ep1 002 --mode lite --frames-only")
print("  3. Verify [WIRE-D] and location master in console output")
