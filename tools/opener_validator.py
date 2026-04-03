"""
opener_validator.py — V36.1 Scene Opener Story Coherence Validator

Validates that the auto-classified opener types are narratively correct
against the story bible. Returns a manifest with:
  - opener_type per scene
  - confidence score (0.0–1.0)
  - story_coherence_note (why this opener fits or doesn't)
  - entry_context (cross-scene emotional carry)
  - override suggestions if confidence is low

Also persists the manifest to opener_manifest.json so:
  1. The UI can display it for pre-generation verification
  2. run_scene() can read explicit overrides instead of re-classifying
  3. New shows ingest it automatically during story bible generation

Universal: works for any story bible, any genre, any network channel.
Non-blocking: classification always wins even if validation fails.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

# Import classifier (always available since same package)
from scene_transition_manager import (
    classify_scene_opener,
    extract_exit_state,
    build_entry_context,
    get_prev_sb_scene,
    OPENER_PROFILES,
)

# ═══ CONFIDENCE SCORING ═══════════════════════════════════════════════════════

# Signals that strongly confirm each opener type
_CONFIRM_SIGNALS = {
    "COLD_OPEN": [
        "already", "mid-", "continues", "still on", "resumes",
        "opens on", "we find", "cold open", "slam cut"
    ],
    "ACTION_OPENER": [
        "enters", "bursts", "storms", "rushes", "strides", "descends",
        "paces", "walks in", "crosses to", "moves through"
    ],
    "DIALOGUE_OPENER": [
        "on the phone", "arguing", "speaks to", "says", "mid-conversation",
        "read aloud", "reads aloud", "dialogue opens", "voice precedes"
    ],
    "BROLL_OPENER": [
        "photographs", "films", "documents", "surveys the space", "empty room",
        "no character", "environment", "establishes", "world first"
    ],
    "REVELATION_OPENER": [
        "finds", "discovers", "uncovers", "reveals", "journal", "letter",
        "secret", "realizes", "notices", "sees for the first time"
    ],
    "ATMOSPHERE_OPENER": [
        "sits", "stares", "gazes", "broods", "lingers", "contemplates",
        "waits", "surveys", "empty bench", "alone with"
    ],
}

# Signals that make an opener type suspicious
_DOUBT_SIGNALS = {
    "COLD_OPEN":      ["slowly", "enters", "approaches", "cautiously"],
    "ACTION_OPENER":  ["sits", "stares", "gazes", "alone", "empty"],
    "DIALOGUE_OPENER":["silent", "no dialogue", "no character", "exterior only"],
    "BROLL_OPENER":   ["speaks", "argues", "confronts", "on the phone"],
    "REVELATION_OPENER": ["exits", "leaves", "departs", "nothing to find"],
    "ATMOSPHERE_OPENER": ["rushes", "bursts", "storms", "phone"],
}


def score_opener_confidence(opener_type: str, sb_scene: dict) -> tuple[float, str]:
    """
    Score how confident we are the opener_type is correct for this scene.
    Returns (confidence 0.0–1.0, narrative note string).
    """
    beats = sb_scene.get("beats") or []
    first_beat = beats[0] if beats else {}

    if isinstance(first_beat, dict):
        first_text = (
            (first_beat.get("action") or "") + " " +
            (first_beat.get("dialogue") or "") + " " +
            (first_beat.get("description") or "")
        ).lower()
    else:
        first_text = str(first_beat).lower()

    atm = (sb_scene.get("atmosphere") or "").lower()
    full_text = first_text + " " + atm

    # Explicit bible override = 1.0
    if sb_scene.get("opening_type") or sb_scene.get("opener_type"):
        return 1.0, "Explicitly set in story bible — no inference needed."

    confirm_hits = sum(1 for sig in _CONFIRM_SIGNALS.get(opener_type, []) if sig in full_text)
    doubt_hits   = sum(1 for sig in _DOUBT_SIGNALS.get(opener_type, []) if sig in full_text)

    # Base confidence from confirms
    if confirm_hits >= 3:
        confidence = 0.95
    elif confirm_hits == 2:
        confidence = 0.85
    elif confirm_hits == 1:
        confidence = 0.70
    else:
        confidence = 0.50  # keyword-free classification — plausible but unconfirmed

    # Doubt signals reduce confidence
    confidence -= doubt_hits * 0.10
    confidence = max(0.30, min(1.0, confidence))

    # Build narrative note
    if confidence >= 0.85:
        note = f"{opener_type}: confirmed by {confirm_hits} keyword signal(s) in first beat."
    elif confidence >= 0.65:
        note = f"{opener_type}: likely correct ({confirm_hits} confirms, {doubt_hits} doubts). Review first beat."
    else:
        note = (
            f"{opener_type}: low confidence ({confirm_hits} confirms, {doubt_hits} doubts). "
            f"Consider overriding with `opening_type` field in story bible."
        )

    return round(confidence, 2), note


# ═══ MANIFEST BUILDER ════════════════════════════════════════════════════════

def build_opener_manifest(sb: dict, project: str = "") -> dict:
    """
    Build the full opener manifest for a project.
    Returns a dict suitable for saving to opener_manifest.json.
    """
    scenes = sb.get("scenes") or []
    scene_entries = []

    for i, sc in enumerate(scenes):
        sid = str(sc.get("scene_id") or sc.get("id") or str(i + 1))
        prev_sc = scenes[i - 1] if i > 0 else None

        opener_type = classify_scene_opener(sc, prev_sc)
        confidence, coh_note = score_opener_confidence(opener_type, sc)
        profile = OPENER_PROFILES[opener_type]

        exit_state = extract_exit_state(prev_sc) if prev_sc else None
        entry_context = build_entry_context(exit_state, opener_type) if exit_state else ""

        # Suggest override if confidence is low
        override_suggestion = ""
        if confidence < 0.60:
            # Find the opener type with most confirms
            best_type = opener_type
            best_score = 0
            beats = sc.get("beats") or []
            first_beat = beats[0] if beats else {}
            first_text = ""
            if isinstance(first_beat, dict):
                first_text = ((first_beat.get("action") or "") + " " + (first_beat.get("dialogue") or "")).lower()
            else:
                first_text = str(first_beat).lower()

            for ot, sigs in _CONFIRM_SIGNALS.items():
                hits = sum(1 for s in sigs if s in first_text)
                if hits > best_score:
                    best_score = hits
                    best_type = ot
            if best_type != opener_type:
                override_suggestion = (
                    f"Consider changing to {best_type} "
                    f"— add `\"opening_type\": \"{best_type}\"` to scene {sid} in story bible."
                )

        entry = {
            "scene_id":        sid,
            "location":        sc.get("location", ""),
            "opener_type":     opener_type,
            "confidence":      confidence,
            "coherence_note":  coh_note,
            "energy":          profile["energy"],
            "e_weight":        profile["e_weight"],
            "e01_prefix":      profile["e01_prefix"],
            "e02_prefix":      profile["e02_prefix"],
            "e03_prefix":      profile["e03_prefix"],
            "m01_prefix":      profile["m01_prefix"],
            "entry_context":   entry_context,
            "prev_exit_emotion": exit_state["emotion"] if exit_state else "",
            "prev_exit_action":  exit_state["beat_action"][:100] if exit_state else "",
            "override_suggestion": override_suggestion,
            # Operator can set opener_type_override to lock a specific type
            "opener_type_override": sc.get("opening_type") or sc.get("opener_type") or "",
        }
        scene_entries.append(entry)

    return {
        "_manifest_version":  "V36.1",
        "_project":           project,
        "_total_scenes":      len(scene_entries),
        "_classified_at":     __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "scenes":             scene_entries,
    }


def save_opener_manifest(manifest: dict, project_path: Path) -> Path:
    """Save opener_manifest.json to project directory. Returns path."""
    out = project_path / "opener_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    return out


def load_opener_manifest(project_path: Path) -> Optional[dict]:
    """Load opener_manifest.json if it exists."""
    p = project_path / "opener_manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


# ═══ VALIDATION REPORT ═══════════════════════════════════════════════════════

def validate_manifest(manifest: dict) -> dict:
    """
    Run story coherence validation on a built manifest.
    Returns {passed, warnings, errors, scene_results}.
    """
    scenes = manifest.get("scenes", [])
    warnings = []
    errors = []
    scene_results = []

    for entry in scenes:
        sid = entry["scene_id"]
        conf = entry["confidence"]
        ot   = entry["opener_type"]
        ovr  = entry["opener_type_override"]

        result = {"scene_id": sid, "status": "ok", "notes": []}

        if ovr and ovr != ot:
            result["notes"].append(f"Override active: {ovr} replaces auto-classified {ot}")
            result["status"] = "override"

        if conf < 0.50 and not ovr:
            msg = f"Scene {sid} ({ot}): low confidence {conf} — {entry['override_suggestion']}"
            warnings.append(msg)
            result["status"] = "warn"
            result["notes"].append(msg)
        elif conf < 0.65 and not ovr:
            result["notes"].append(f"Moderate confidence {conf} — verify against script.")

        # Cross-scene coherence: check for tonal whiplash
        if entry["prev_exit_emotion"] in ("revelation", "conspiracy") and ot == "ATMOSPHERE_OPENER":
            note = (
                f"Scene {sid}: previous scene exits on {entry['prev_exit_emotion']} "
                f"but opener is ATMOSPHERE (slow/quiet). "
                f"Consider ACTION_OPENER or COLD_OPEN for urgency continuity."
            )
            warnings.append(note)
            result["notes"].append(note)

        scene_results.append(result)

    low_conf_count = sum(1 for e in scenes if e["confidence"] < 0.60)
    return {
        "passed":        len(errors) == 0,
        "total_scenes":  len(scenes),
        "low_conf_count": low_conf_count,
        "warnings":      warnings,
        "errors":        errors,
        "scene_results": scene_results,
    }


# ═══ INGESTION HOOK (called after generate-story-bible) ══════════════════════

def run_ingestion_classification(project_path: Path, sb: dict) -> dict:
    """
    Called automatically during story bible generation.
    Classifies all scene openers, validates, saves manifest.
    Returns summary dict for the API response.
    """
    try:
        project = project_path.name
        manifest = build_opener_manifest(sb, project)
        out_path = save_opener_manifest(manifest, project_path)
        validation = validate_manifest(manifest)

        n = manifest["_total_scenes"]
        lc = validation["low_conf_count"]
        return {
            "opener_manifest_saved": str(out_path),
            "scenes_classified": n,
            "low_confidence_scenes": lc,
            "validation_passed": validation["passed"],
            "warnings": validation["warnings"],
        }
    except Exception as e:
        return {"opener_manifest_saved": None, "error": str(e)}


# ═══ UNIVERSAL NETWORK MAPPING ════════════════════════════════════════════════

# Genre-channel opener defaults — used by network_intake.py when a show has no
# explicit opening_type fields in its story bible. The channel sets the default
# opener_type distribution that reflects the genre's storytelling convention.
#
# Key insight: a COLD_OPEN-heavy show (prestige thriller) should have most of
# its scenes classified as ACTION/COLD by default; a slow-burn drama should
# default to ATMOSPHERE/BROLL. These defaults are OVERRIDABLE per-scene via
# `opening_type` in the story bible.
CHANNEL_OPENER_DEFAULTS = {
    "horror": {
        "preferred_openers": ["ATMOSPHERE_OPENER", "REVELATION_OPENER", "COLD_OPEN"],
        "default_energy":    "slow_then_spike",
        "cold_open_scenes":  [1],   # First scene is almost always cold open
        "note":              "Horror defaults to atmosphere/dread. Scene 1 = COLD_OPEN."
    },
    "sci_fi": {
        "preferred_openers": ["BROLL_OPENER", "ACTION_OPENER", "COLD_OPEN"],
        "default_energy":    "kinetic",
        "cold_open_scenes":  [1, 2],
        "note":              "Sci-fi world-builds first. First 2 scenes BROLL/COLD."
    },
    "whodunnit_drama": {
        "preferred_openers": ["ATMOSPHERE_OPENER", "DIALOGUE_OPENER", "REVELATION_OPENER"],
        "default_energy":    "slow",
        "cold_open_scenes":  [],
        "note":              "Mystery drama earns its reveals. Atmosphere and dialogue dominate."
    },
    "action": {
        "preferred_openers": ["COLD_OPEN", "ACTION_OPENER", "DIALOGUE_OPENER"],
        "default_energy":    "high",
        "cold_open_scenes":  [1, 3, 7],   # Action shows cold open at act breaks
        "note":              "Action opens cold and stays kinetic. Act breaks = cold open."
    },
    "comedy": {
        "preferred_openers": ["DIALOGUE_OPENER", "ACTION_OPENER", "BROLL_OPENER"],
        "default_energy":    "medium",
        "cold_open_scenes":  [1],
        "note":              "Comedy cold open for the tag, then dialogue-driven."
    },
    "drama": {
        "preferred_openers": ["ATMOSPHERE_OPENER", "DIALOGUE_OPENER", "ACTION_OPENER"],
        "default_energy":    "medium",
        "cold_open_scenes":  [],
        "note":              "Drama builds. No cold opens by default."
    },
}


def get_channel_opener_defaults(genre: str) -> dict:
    """Return channel-level opener defaults for a given genre."""
    return CHANNEL_OPENER_DEFAULTS.get(genre.lower(), CHANNEL_OPENER_DEFAULTS["drama"])


# ═══ STANDALONE DIAGNOSTIC ════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    pdir = Path("pipeline_outputs") / project
    sb_path = pdir / "story_bible.json"

    if not sb_path.exists():
        print(f"No story bible at {sb_path}"); sys.exit(1)

    sb = json.loads(sb_path.read_text())
    manifest = build_opener_manifest(sb, project)
    validation = validate_manifest(manifest)

    print(f"\n=== OPENER VALIDATION — {project} ===\n")
    print(f"  Scenes classified: {manifest['_total_scenes']}")
    print(f"  Validation passed: {validation['passed']}")
    print(f"  Low confidence:    {validation['low_conf_count']}")
    if validation["warnings"]:
        print(f"\n  WARNINGS:")
        for w in validation["warnings"]:
            print(f"    ⚠ {w}")
    print()

    for entry in manifest["scenes"]:
        conf_bar = "█" * int(entry["confidence"] * 10) + "░" * (10 - int(entry["confidence"] * 10))
        ovr_tag = f" [OVERRIDE→{entry['opener_type_override']}]" if entry["opener_type_override"] else ""
        print(f"  S{entry['scene_id']:>3}  {entry['opener_type']:<22}  [{conf_bar}] {entry['confidence']:.0%}{ovr_tag}")
        if entry["entry_context"]:
            print(f"         ↳ entry: {entry['entry_context'][:70]}")
        if entry["override_suggestion"]:
            print(f"         ⚠ {entry['override_suggestion'][:80]}")

    print()
    out = save_opener_manifest(manifest, pdir)
    print(f"  Manifest saved → {out}")
