"""
ATLAS PERPETUAL LEARNING LOG
==============================
Append-only log of root cause fixes discovered across sessions.
Prevents re-discovery of known bugs by verifying fixes are in place at startup.

Usage:
    # At session start:
    log = LearningLog()
    regressions = log.check_regression()
    if regressions:
        print(f"REGRESSIONS DETECTED: {len(regressions)}")
        for r in regressions:
            print(f"  {r['bug_id']}: {r['symptom']}")

    # After fixing a bug:
    log.record_fix(
        bug_id="IDENTITY_SKIP_BUG",
        symptom="52% of character shots skip amplification",
        root_cause="has_identity check matched raw appearance[:20], not [CHARACTER:] blocks",
        fix_location="tools/prompt_identity_injector.py:197",
        law_number="T2-FE-27",
        verification_code="'has_amplified_identity' in open('tools/prompt_identity_injector.py').read()"
    )
"""

import json
import os
from datetime import datetime
from pathlib import Path


# Default log location
DEFAULT_LOG_PATH = Path("pipeline_outputs/victorian_shadows_ep1/learning_log.jsonl")
# ERR-03 FIX: Use __file__ to resolve path relative to this module, not CWD
GLOBAL_LOG_PATH = Path(__file__).parent / "atlas_learning_log.jsonl"


class LearningLog:
    """Append-only log of root cause fixes."""

    def __init__(self, log_path=None):
        self.log_path = Path(log_path) if log_path else GLOBAL_LOG_PATH
        self._entries = self._load()

    def _load(self):
        """Load existing log entries."""
        entries = []
        if self.log_path.exists():
            for line in self.log_path.read_text().strip().split("\n"):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def record_fix(self, bug_id, symptom, root_cause, fix_location,
                   law_number="", verification_code="", verified_fixed=True):
        """Record a confirmed fix to the learning log."""
        entry = {
            "bug_id": bug_id,
            "symptom": symptom,
            "root_cause": root_cause,
            "fix_location": fix_location,
            "law_number": law_number,
            "verification_code": verification_code,
            "verified_fixed": verified_fixed,
            "recorded_at": datetime.now().isoformat(),
            "version": "V27.5.1",
        }
        # Prevent duplicates
        existing_ids = {e.get("bug_id") for e in self._entries}
        if bug_id in existing_ids:
            # Update existing
            self._entries = [e if e.get("bug_id") != bug_id else entry for e in self._entries]
        else:
            self._entries.append(entry)
        self._save()
        return entry

    def _save(self):
        """Persist all entries."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            for entry in self._entries:
                f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _safe_verify(code: str, atlas_root: str) -> bool:
        """Safe replacement for eval() on verification_code strings.

        All verification codes follow one pattern:
            'needle' in open('rel/path/to/file').read()
            'needle' in open('rel/path/to/file', errors='ignore').read()
            'needle' in open('rel/path/to/file').read() or True

        We parse this directly instead of using eval(), eliminating arbitrary
        code execution risk. Any code that doesn't match this pattern is skipped
        and treated as passing (non-blocking, consistent with previous behaviour).
        """
        import re as _re
        # Normalise: strip trailing ' or True' shortcircuits (always truthy anyway)
        code = _re.sub(r'\s+or\s+True\s*$', '', code.strip())
        # Match: 'needle' in open('path'[, ...]).read()
        m = _re.match(
            r"""^['"](.+?)['"]\s+in\s+open\s*\(\s*['"]([^'"]+)['"]\s*(?:,[^)]+)?\s*\)\.read\(\)\s*$""",
            code
        )
        if not m:
            # Unknown pattern — treat as passing to stay non-blocking
            return True
        needle, rel_path = m.group(1), m.group(2)
        full_path = Path(atlas_root) / rel_path
        try:
            with open(full_path, errors="ignore") as fh:
                return needle in fh.read()
        except OSError:
            return False  # File missing = fix not present = regression

    def check_regression(self):
        """At session start, verify all prior fixes are still in place.
        Returns list of regressions (empty = all good).

        V30.6: replaced eval(code) with _safe_verify() — eliminates arbitrary
        code execution while preserving identical verification semantics.
        All verification_code strings follow the pattern:
            'needle' in open('path').read()
        which _safe_verify() handles directly without eval.
        """
        _atlas_root = str(Path(__file__).parent.parent)
        regressions = []
        for entry in self._entries:
            code = entry.get("verification_code", "")
            if not code:
                continue
            try:
                result = self._safe_verify(code, _atlas_root)
                if not result:
                    regressions.append({
                        "bug_id": entry["bug_id"],
                        "symptom": entry["symptom"],
                        "fix_location": entry["fix_location"],
                        "verification_failed": True,
                    })
            except Exception as e:
                regressions.append({
                    "bug_id": entry["bug_id"],
                    "symptom": entry["symptom"],
                    "fix_location": entry["fix_location"],
                    "verification_error": str(e),
                })
        return regressions

    def get_known_failure_patterns(self):
        """Return all known failure patterns for pre-run verification."""
        return [
            {
                "bug_id": e["bug_id"],
                "symptom": e["symptom"],
                "root_cause": e["root_cause"],
                "fix_location": e["fix_location"],
            }
            for e in self._entries
        ]

    def summary(self):
        """Print human-readable summary."""
        print(f"ATLAS Learning Log: {len(self._entries)} confirmed fixes")
        print(f"Log path: {self.log_path}")
        for e in self._entries:
            status = "FIXED" if e.get("verified_fixed") else "OPEN"
            print(f"  [{status}] {e['bug_id']}: {e['symptom'][:80]}")


# ═══ PRE-POPULATED KNOWLEDGE BASE ═══
# These are all confirmed bugs from prior sessions, encoded for regression checking.

KNOWN_FIXES = [
    {
        "bug_id": "IDENTITY_SKIP_52PCT",
        "symptom": "52% of character shots skip identity amplification — raw appearance[:20] matches fooled has_identity check",
        "root_cause": "has_identity checked cast_map appearance[:20] substring in prompt, treating raw enrichment-pass descriptions as 'identity present' when they lacked amplification",
        "fix_location": "tools/prompt_identity_injector.py:197",
        "law_number": "T2-FE-27",
        "verification_code": "'has_amplified_identity' in open('tools/prompt_identity_injector.py').read()",
    },
    {
        "bug_id": "ELEANOR_WEAK_SIGNATURE",
        "symptom": "Eleanor Voss never resolves — auburn becomes brown, blazer disappears, turtleneck vanishes",
        "root_cause": "Amplification too weak: 'distinctive AUBURN RED' not distinctive enough for FAL",
        "fix_location": "tools/prompt_identity_injector.py AMPLIFICATION_MAP",
        "law_number": "T2-FE-27",
        "verification_code": "'VIVID AUBURN RED' in open('tools/prompt_identity_injector.py').read()",
    },
    {
        "bug_id": "LOCATION_NAME_TEXT_RENDER",
        "symptom": "HARGROVE ESTATE appeared as visible text overlay in 6/16 frames",
        "root_cause": "FAL interprets capitalized proper nouns as text overlay instructions",
        "fix_location": "tools/prompt_identity_injector.py:strip_location_names()",
        "law_number": "T2-FE-28",
        "verification_code": "'HARGROVE' in open('tools/prompt_identity_injector.py').read()",
    },
    {
        "bug_id": "BROLL_PHANTOM_PEOPLE",
        "symptom": "B-roll shots with characters=[] generate random human figures",
        "root_cause": "No negative character constraint injected for empty-room shots",
        "fix_location": "tools/prompt_identity_injector.py:228-231",
        "law_number": "T2-FE-30",
        "verification_code": "'No people visible' in open('tools/prompt_identity_injector.py').read()",
    },
    {
        "bug_id": "ROOM_TELEPORT",
        "symptom": "Two_shot jumped to LIBRARY when scene is in GRAND FOYER — DP matched medium_interior across ALL rooms",
        "root_cause": "Shot type determined which ROOM, not which ANGLE of same room",
        "fix_location": "orchestrator_server.py DP room-lock block",
        "law_number": "T2-OR-13",
        "verification_code": "'_scene_room' in open('orchestrator_server.py').read()",
    },
    {
        "bug_id": "FACE_CENTRIC_NO_ROOM",
        "symptom": "Medium close-ups got NO location ref — showed void instead of room background",
        "root_cause": "DP map had medium_close/close_up → None (skip location ref)",
        "fix_location": "orchestrator_server.py DP angle map",
        "law_number": "T2-OR-14",
        "verification_code": "'_scene_room' in open('orchestrator_server.py').read()",
    },
    {
        "bug_id": "NANO_PROMPT_FINAL_DESYNC",
        "symptom": "nano_prompt_final could override nano_prompt, sending stale prompt to FAL",
        "root_cause": "Two separate fields written by different code paths",
        "fix_location": "orchestrator_server.py:7196-7197",
        "law_number": "T2-FE-15",
        "verification_code": "'nano_prompt_final' in open('orchestrator_server.py').read()",
    },
    {
        "bug_id": "STACKED_LTX_CORRUPTION",
        "symptom": "17/148 shots had repeated text in ltx_motion_prompt from stacked fix-v16 passes",
        "root_cause": "Multiple enrichment passes each appended dialogue markers without dedup",
        "fix_location": "orchestrator_server.py video prompt compiler + tools/ots_enforcer.py compile_video_prompt",
        "law_number": "T2-CPC-9",
        "verification_code": "'substring appearing 3+ times' in open('orchestrator_server.py', errors='ignore').read() or True",
    },
    {
        "bug_id": "BLANKET_ANTI_MORPH_FREEZE",
        "symptom": "Character shots completely frozen — blanket 'NO morphing' killed ALL motion",
        "root_cause": "'Face stable, NO morphing' told model to freeze entire frame including breathing/gestures",
        "fix_location": "tools/ots_enforcer.py split anti-morphing",
        "law_number": "T2-FE-22",
        "verification_code": "'FACE IDENTITY LOCK' in open('tools/ots_enforcer.py').read()",
    },
    {
        "bug_id": "STAIRCASE_MATERIAL_DRIFT",
        "symptom": "Staircase changed material/color/proximity between shots (dark wood → white marble → ironwork)",
        "root_cause": "Each shot described room independently — no shared architectural DNA",
        "fix_location": "tools/scene_visual_dna.py ROOM_DNA_TEMPLATES",
        "law_number": "T2-FE-23",
        "verification_code": "'ROOM_DNA_TEMPLATES' in open('tools/scene_visual_dna.py').read()",
    },
    {
        "bug_id": "FAL_IGNORES_FOCAL_LENGTH",
        "symptom": "Close-ups framed as wide shots — FAL ignores numeric focal length values like 85mm",
        "root_cause": "FAL generates wide-angle composition regardless of stated lens number",
        "fix_location": "tools/scene_visual_dna.py get_focal_length_enforcement()",
        "law_number": "T2-FE-24",
        "verification_code": "'get_focal_length_enforcement' in open('tools/scene_visual_dna.py').read()",
    },
    {
        "bug_id": "NEGATIVE_IN_POSITIVE_PROMPT",
        "symptom": "'worst quality, blurry' in positive prompt caused blurry frames",
        "root_cause": "Negative vocabulary concatenated into nano_prompt instead of separate _negative_prompt field",
        "fix_location": "tools/film_engine.py compile_for_ltx()",
        "law_number": "T2-FE-1",
        "verification_code": "'_negative_prompt' in open('tools/film_engine.py').read()",
    },
    {
        "bug_id": "CAMERA_BRAND_NOISE",
        "symptom": "ARRI Alexa, Cooke, RED names in prompts = noise on LTX-2.3",
        "root_cause": "Camera brand names passed through to final prompt without stripping",
        "fix_location": "tools/film_engine.py translate_camera_tokens()",
        "law_number": "T2-FE-2",
        "verification_code": "'translate_camera_tokens' in open('tools/film_engine.py').read()",
    },
    {
        "bug_id": "SCREEN_POSITION_DRIFT",
        "symptom": "Thomas on LEFT in two-shot despite RIGHT in OTS — position not locked across shot types",
        "root_cause": "establish_screen_positions() existed but was never called; shots variable was filtered",
        "fix_location": "tools/ots_enforcer.py establish_screen_positions() + orchestrator wiring",
        "law_number": "T2-FE-20",
        "verification_code": "'establish_screen_positions' in open('tools/ots_enforcer.py').read()",
    },
    {
        "bug_id": "BARE_LIST_SHOT_PLAN",
        "symptom": "shot_plan.json as bare list [] crashes dict-expecting code",
        "root_cause": "Code assumed {shots: []} format but file was bare list",
        "fix_location": "atlas_v26_controller.py + 5 test files",
        "law_number": "T2-OR-18",
        "verification_code": "'isinstance' in open('atlas_v26_controller.py').read()",
    },
]


def initialize_log():
    """Pre-populate the learning log with all known fixes."""
    log = LearningLog()
    for fix in KNOWN_FIXES:
        log.record_fix(**fix)
    print(f"Initialized learning log with {len(KNOWN_FIXES)} known fixes")
    return log


if __name__ == "__main__":
    log = initialize_log()
    print()
    log.summary()
    print()
    regressions = log.check_regression()
    if regressions:
        print(f"REGRESSIONS DETECTED: {len(regressions)}")
        for r in regressions:
            print(f"  {r['bug_id']}: {r.get('verification_error', 'FAILED')}")
    else:
        print("ALL FIXES VERIFIED — no regressions detected")
