"""
tools/series_orchestrator.py — ATLAS Series Orchestrator

CONTROLLER-CLASS MODULE (V36 Section 0 compliant).
Authority: Series Orchestrator is a CONTROLLER — it sequences episodes and writes
manifests. QA gates (prep_engine, generation_gate) still validate each episode
independently. Heatmap observes only. This module never bypasses any QA gate.

Hierarchy:
  Network Manifest → Channel → Season → Series Manifest → Episode
  → Story Bible → Shot Plan → atlas_universal_runner.py

Usage:
    from tools.series_orchestrator import load_manifest, run_series
    manifest = load_manifest("series_manifests/victorian_shadows.json")
    run_series(manifest)

    # Or from CLI:
    python3 tools/series_orchestrator.py series_manifests/victorian_shadows.json

V36.0 — 2026-03-27
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Path resolution — works when called from repo root or tools/ ──────────────
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tools"))

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

VALID_EPISODE_STATUSES = {
    "not_started",       # No story bible, no shot plan
    "bible_ready",       # story_bible_path exists, no shot plan yet
    "shot_plan_ready",   # shot_plan_path exists, not yet generated
    "in_production",     # Actively generating frames/videos
    "frames_complete",   # All frames generated, awaiting video approval
    "videos_complete",   # All videos generated, awaiting stitch
    "stitched",          # Episode MP4 exists
    "qc_passed",         # Director QC approved
    "aired",             # Broadcast schedule complete
}

SERIES_MANIFEST_SCHEMA_VERSION = "1.0"

EPISODE_STUB_TEMPLATE = {
    "episode_number": None,
    "title": "TBD",
    "story_bible_path": None,
    "shot_plan_path": None,
    "status": "not_started",
    "scene_count": None,
    "shot_count": None,
    "target_duration_minutes": 10,
    "stitched_video_path": None,
    "genre_dna_override": None,   # If null, inherits from series
    "_created_at": None,
    "_last_updated": None,
}

# ─────────────────────────────────────────────────────────────────────────────
# MANIFEST LOAD + VALIDATE
# ─────────────────────────────────────────────────────────────────────────────

def load_manifest(manifest_path: str) -> dict:
    """
    Load and validate a series_manifest.json.

    Validation checks:
      - Required top-level fields present
      - All episodes have required fields
      - Episode statuses are valid
      - episode_id is unique across all episodes

    Returns the manifest dict on success.
    Raises ValueError with actionable diagnostics on validation failure.
    """
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Series manifest not found: {manifest_path}")

    manifest = json.load(open(path))

    # ── Required top-level fields ──────────────────────────────────────────
    required_top = ["series_id", "channel", "genre_dna", "season", "episodes"]
    missing = [f for f in required_top if f not in manifest]
    if missing:
        raise ValueError(f"Series manifest missing required fields: {missing}")

    # ── Episode validation ─────────────────────────────────────────────────
    seen_ids = set()
    errors = []
    for i, ep in enumerate(manifest.get("episodes", [])):
        ep_id = ep.get("episode_id", f"<episode {i}>")

        # Uniqueness
        if ep_id in seen_ids:
            errors.append(f"Duplicate episode_id: {ep_id}")
        seen_ids.add(ep_id)

        # Required per-episode fields
        for field in ["episode_id", "episode_number", "status"]:
            if field not in ep:
                errors.append(f"{ep_id}: missing required field '{field}'")

        # Status validity
        status = ep.get("status")
        if status and status not in VALID_EPISODE_STATUSES:
            errors.append(
                f"{ep_id}: unknown status '{status}'. "
                f"Valid: {sorted(VALID_EPISODE_STATUSES)}"
            )

    if errors:
        raise ValueError(
            f"Series manifest validation failed ({len(errors)} errors):\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    print(
        f"[SERIES] Loaded: {manifest['series_id']} "
        f"(season {manifest['season']}, {len(manifest['episodes'])} episodes)"
    )
    return manifest


def save_manifest(manifest: dict, manifest_path: str) -> None:
    """Write manifest to disk with updated _last_updated timestamp."""
    manifest["_last_updated"] = datetime.utcnow().isoformat()
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[SERIES] Saved manifest → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# EPISODE STATUS QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def get_episode_status(manifest: dict, episode_id: str) -> dict:
    """
    Return the full status record for a specific episode.

    Enriches the stored status with live filesystem checks:
      - story_bible_exists: checks story_bible_path on disk
      - shot_plan_exists: checks shot_plan_path on disk
      - frames_on_disk: count of JPG files in first_frames/
      - videos_on_disk: count of MP4 files in videos_kling_lite/

    Returns a dict with 'episode_id', 'status', and all live fields.
    Raises KeyError if episode_id not found in manifest.
    """
    episodes = {ep["episode_id"]: ep for ep in manifest.get("episodes", [])}
    if episode_id not in episodes:
        raise KeyError(
            f"Episode '{episode_id}' not found in series '{manifest['series_id']}'. "
            f"Available: {sorted(episodes.keys())}"
        )

    ep = dict(episodes[episode_id])  # copy, don't mutate

    # Live filesystem checks
    ep["story_bible_exists"] = False
    ep["shot_plan_exists"] = False
    ep["frames_on_disk"] = 0
    ep["videos_on_disk"] = 0

    if ep.get("story_bible_path"):
        ep["story_bible_exists"] = Path(ep["story_bible_path"]).exists()

    if ep.get("shot_plan_path"):
        sp_path = Path(ep["shot_plan_path"])
        ep["shot_plan_exists"] = sp_path.exists()

        if sp_path.exists():
            proj_dir = sp_path.parent
            frames_dir = proj_dir / "first_frames"
            videos_dir = proj_dir / "videos_kling_lite"
            ep["frames_on_disk"] = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0
            ep["videos_on_disk"] = len(list(videos_dir.glob("*.mp4"))) if videos_dir.exists() else 0

    return ep


def get_next_episode(manifest: dict) -> Optional[dict]:
    """
    Return the next episode that needs production work.

    Priority order (lowest status = most urgent):
      1. in_production  (already running, resume it)
      2. shot_plan_ready (ready to generate)
      3. bible_ready    (needs shot plan expansion first)
      4. not_started    (needs story bible first)

    Episodes with status 'stitched', 'qc_passed', or 'aired' are skipped.

    Returns the episode dict, or None if all episodes are complete.
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

    candidates = [
        ep for ep in manifest.get("episodes", [])
        if PRIORITY.get(ep.get("status", "not_started"), 99) < 99
    ]

    if not candidates:
        return None

    candidates.sort(key=lambda ep: (
        PRIORITY.get(ep.get("status", "not_started"), 99),
        ep.get("episode_number", 999)
    ))

    return candidates[0]


def list_episode_statuses(manifest: dict) -> list:
    """Return a sorted list of (episode_id, episode_number, status) tuples."""
    return sorted(
        [
            (ep["episode_id"], ep.get("episode_number", "?"), ep.get("status", "unknown"))
            for ep in manifest.get("episodes", [])
        ],
        key=lambda x: x[1]
    )


# ─────────────────────────────────────────────────────────────────────────────
# EPISODE PRODUCTION — BIBLE TO SHOT PLAN
# ─────────────────────────────────────────────────────────────────────────────

def generate_episode_shot_plan(
    manifest: dict,
    episode_id: str,
    story_bible: dict,
    orchestrator_url: str = "http://localhost:9999",
    dry_run: bool = False,
) -> dict:
    """
    Convert a story bible into a fully-enriched shot plan for one episode.

    This is the bible-to-shot-plan conversion point. It calls the ATLAS
    orchestrator server (which must be running) via its standard REST pipeline:

      1. POST /api/v6/script/full-import        (from story bible, skip if shot_plan exists)
      2. POST /api/auto/generate-story-bible     (if bible not already expanded)
      3. POST /api/shot-plan/fix-v16             (duration, coverage, CHECK 7A-7F)
      4. POST /api/v6/casting/auto-cast          (character → AI actor mapping)

    This module does NOT call the runner directly — it prepares the episode
    so the runner can be called by run_series() or the operator.

    Args:
        manifest:         The loaded series manifest (from load_manifest())
        episode_id:       Which episode to prepare
        story_bible:      The story bible dict (pre-loaded by caller)
        orchestrator_url: Base URL of the running ATLAS orchestrator
        dry_run:          If True, print what would happen but make no API calls

    Returns:
        dict with keys: episode_id, status, shot_plan_path, scene_count, shot_count
    """
    import urllib.request

    ep_rec = next((ep for ep in manifest["episodes"] if ep["episode_id"] == episode_id), None)
    if ep_rec is None:
        raise KeyError(f"Episode '{episode_id}' not found in manifest")

    project = episode_id
    print(f"\n[SERIES] Preparing episode: {episode_id}")
    print(f"  Story bible: {story_bible.get('title', 'Untitled')}")
    print(f"  Scenes: {story_bible.get('_canonical_scene_count', '?')}")

    result = {
        "episode_id": episode_id,
        "status": ep_rec.get("status"),
        "shot_plan_path": ep_rec.get("shot_plan_path"),
        "scene_count": None,
        "shot_count": None,
    }

    if dry_run:
        print(f"  [DRY RUN] Would call orchestrator at {orchestrator_url}")
        print(f"  [DRY RUN] Steps: fix-v16 → auto-cast → ready for runner")
        return result

    def _post(endpoint: str, payload: dict) -> dict:
        """Simple POST helper — no external dependencies."""
        url = f"{orchestrator_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  [SERIES] WARNING: {endpoint} failed: {e}")
            return {"error": str(e)}

    # Step 1: fix-v16 enrichment
    print(f"  → POST /api/shot-plan/fix-v16 ...")
    r1 = _post("/api/shot-plan/fix-v16", {"project": project})
    if "error" not in r1:
        print(f"  ✓ fix-v16 complete")

    # Step 2: auto-cast
    print(f"  → POST /api/v6/casting/auto-cast ...")
    r2 = _post("/api/v6/casting/auto-cast", {"project": project})
    if "error" not in r2:
        print(f"  ✓ auto-cast complete")

    # Verify shot plan exists and count shots/scenes
    shot_plan_path = Path("pipeline_outputs") / project / "shot_plan.json"
    if shot_plan_path.exists():
        sp = json.load(open(shot_plan_path))
        shots = sp if isinstance(sp, list) else sp.get("shots", [])
        scene_ids = set(s.get("scene_id", "") for s in shots)
        result["shot_plan_path"] = str(shot_plan_path)
        result["shot_count"] = len(shots)
        result["scene_count"] = len(scene_ids)
        result["status"] = "shot_plan_ready"
        print(f"  ✓ Shot plan: {len(shots)} shots across {len(scene_ids)} scenes")
    else:
        print(f"  ⚠ Shot plan not found at {shot_plan_path}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# SERIES RUNNER — SEQUENCES EPISODES THROUGH THE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_series(
    manifest_path: str,
    mode: str = "lite",
    frames_only: bool = False,
    videos_only: bool = False,
    dry_run: bool = False,
    stop_on_failure: bool = True,
) -> dict:
    """
    Sequence through all production-ready episodes in the series,
    calling atlas_universal_runner.py for each episode's scenes.

    This is the top-level orchestration loop. It:
      1. Loads the manifest
      2. Finds episodes with status 'shot_plan_ready' or 'in_production'
      3. For each episode, iterates all scenes in the shot plan
      4. Calls the runner for each scene (subprocess call — preserves runner's
         own QA gates, Wire A/B/C, spatial gate, generation gate)
      5. Updates episode status in the manifest after each episode completes

    Authority note: This module is a CONTROLLER. All QA decisions (approve/reject
    frames, Wire A regen, heatmap) remain in the runner and orchestrator. This
    module only sequences and reports.

    Args:
        manifest_path:   Path to series_manifest.json
        mode:            "lite" or "full" (passed to runner --mode)
        frames_only:     Pass --frames-only to runner (stage 1 validation run)
        videos_only:     Pass --videos-only to runner (stage 2, after frame review)
        dry_run:         Print commands but do not execute
        stop_on_failure: Halt series if any episode scene fails (default True)

    Returns:
        dict with summary: episodes_attempted, episodes_succeeded, episodes_failed
    """
    manifest = load_manifest(manifest_path)
    runner = str(_REPO_ROOT / "atlas_universal_runner.py")

    summary = {
        "series_id": manifest["series_id"],
        "episodes_attempted": 0,
        "episodes_succeeded": 0,
        "episodes_failed": 0,
        "episode_results": [],
    }

    RUNNABLE_STATUSES = {"shot_plan_ready", "in_production", "frames_complete"}

    for ep in manifest.get("episodes", []):
        ep_id = ep["episode_id"]
        status = ep.get("status", "not_started")

        if status not in RUNNABLE_STATUSES:
            print(f"\n[SERIES] Skipping {ep_id} (status: {status})")
            continue

        print(f"\n{'='*60}")
        print(f"  EPISODE: {ep_id} | Status: {status}")
        print(f"{'='*60}")

        shot_plan_path = ep.get("shot_plan_path")
        if not shot_plan_path or not Path(shot_plan_path).exists():
            print(f"  [SERIES] ERROR: shot_plan not found for {ep_id}: {shot_plan_path}")
            summary["episodes_failed"] += 1
            if stop_on_failure:
                break
            continue

        # Load shot plan to get scene list
        sp = json.load(open(shot_plan_path))
        shots = sp if isinstance(sp, list) else sp.get("shots", [])
        scene_ids = sorted(set(s.get("scene_id", "") for s in shots if s.get("scene_id")))
        print(f"  Scenes to run: {scene_ids}")

        summary["episodes_attempted"] += 1
        ep_result = {"episode_id": ep_id, "scenes": {}, "success": True}

        for scene_id in scene_ids:
            cmd = [
                sys.executable, runner,
                ep_id,
                scene_id,
                "--mode", mode,
            ]
            if frames_only:
                cmd.append("--frames-only")
            if videos_only:
                cmd.append("--videos-only")

            print(f"\n  [RUNNER] {' '.join(cmd)}")

            if dry_run:
                print(f"  [DRY RUN] Would run: {' '.join(cmd)}")
                ep_result["scenes"][scene_id] = "dry_run"
                continue

            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(_REPO_ROOT),
                    capture_output=False,  # Let runner output flow to console
                    timeout=3600,          # 1-hour timeout per scene
                )
                success = result.returncode == 0
                ep_result["scenes"][scene_id] = "success" if success else "failed"
                if not success:
                    ep_result["success"] = False
                    print(f"  [SERIES] Scene {scene_id} FAILED (exit {result.returncode})")
                    if stop_on_failure:
                        break
            except subprocess.TimeoutExpired:
                ep_result["scenes"][scene_id] = "timeout"
                ep_result["success"] = False
                print(f"  [SERIES] Scene {scene_id} TIMED OUT after 3600s")
                if stop_on_failure:
                    break
            except Exception as e:
                ep_result["scenes"][scene_id] = f"error: {e}"
                ep_result["success"] = False
                print(f"  [SERIES] Scene {scene_id} ERROR: {e}")
                if stop_on_failure:
                    break

        # Update episode status in manifest
        if ep_result["success"]:
            _update_episode_status(
                manifest,
                ep_id,
                "frames_complete" if frames_only else ("videos_complete" if videos_only else "in_production")
            )
            summary["episodes_succeeded"] += 1
        else:
            _update_episode_status(manifest, ep_id, "in_production")
            summary["episodes_failed"] += 1

        summary["episode_results"].append(ep_result)

        if not ep_result["success"] and stop_on_failure:
            print(f"\n[SERIES] Stopping series run after failure in {ep_id}")
            break

    # Save updated manifest
    if not dry_run:
        save_manifest(manifest, manifest_path)

    print(f"\n{'='*60}")
    print(f"  SERIES COMPLETE: {manifest['series_id']}")
    print(f"  Attempted: {summary['episodes_attempted']}")
    print(f"  Succeeded: {summary['episodes_succeeded']}")
    print(f"  Failed:    {summary['episodes_failed']}")
    print(f"{'='*60}")

    return summary


def _update_episode_status(manifest: dict, episode_id: str, new_status: str) -> None:
    """Mutate episode status in the manifest dict (in-place). Caller saves manifest."""
    for ep in manifest.get("episodes", []):
        if ep["episode_id"] == episode_id:
            ep["status"] = new_status
            ep["_last_updated"] = datetime.utcnow().isoformat()
            print(f"  [SERIES] {episode_id} status → {new_status}")
            return
    print(f"  [SERIES] WARNING: episode '{episode_id}' not found — status not updated")


# ─────────────────────────────────────────────────────────────────────────────
# CONTINUITY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_series_continuity(manifest: dict) -> dict:
    """
    Cross-episode continuity validation.

    Checks that character appearances, props, costumes, and story threads
    are consistent across episodes. This is purely advisory — it reports
    violations but does not block generation.

    Validation domains:
      1. Recurring characters — appearance descriptions match across episodes
      2. Wardrobe continuity — same character, same look_id in same scene context
      3. Story threads — thread status correctly propagates (introduced → developed → resolved)
      4. Visual continuity — color_palette and lighting_rig match series arc settings

    Returns:
        dict with keys:
          - 'passed': bool
          - 'violations': list of dicts {episode_id, domain, description, severity}
          - 'warnings': list of strings
          - 'summary': human-readable string
    """
    violations = []
    warnings = []

    series_arc = manifest.get("series_arc", {})
    recurring_chars = {
        c["name"]: c
        for c in series_arc.get("recurring_characters", [])
    }

    episodes_with_plans = [
        ep for ep in manifest.get("episodes", [])
        if ep.get("shot_plan_path") and Path(ep["shot_plan_path"]).exists()
    ]

    if not episodes_with_plans:
        return {
            "passed": True,
            "violations": [],
            "warnings": ["No episodes with shot plans found — nothing to validate"],
            "summary": "Skipped: no shot plans available",
        }

    # ── Domain 1: Character appearance consistency ─────────────────────────
    char_appearances_by_ep = {}
    for ep in episodes_with_plans:
        ep_id = ep["episode_id"]
        cast_path = Path(ep["shot_plan_path"]).parent / "cast_map.json"
        if not cast_path.exists():
            warnings.append(f"{ep_id}: no cast_map.json — skipping character check")
            continue

        cast_map = json.load(open(cast_path))
        char_appearances_by_ep[ep_id] = {
            name.upper(): data.get("appearance", "")
            for name, data in (cast_map.items() if isinstance(cast_map, dict) else {}.items())
        }

    # Compare recurring characters across episodes
    for char_name, char_spec in recurring_chars.items():
        canonical_appearance = char_spec.get("canonical_appearance", "")
        appearances_found = []

        for ep_id, appearances in char_appearances_by_ep.items():
            ep_appearance = appearances.get(char_name.upper(), "")
            if ep_appearance:
                appearances_found.append((ep_id, ep_appearance))

        # Check for inconsistency: any two episodes describe the character differently
        if len(appearances_found) >= 2:
            first_ep, first_app = appearances_found[0]
            for other_ep, other_app in appearances_found[1:]:
                # Simple keyword drift check — look for contradictory descriptors
                contradictions = _find_appearance_contradictions(first_app, other_app)
                if contradictions:
                    violations.append({
                        "episode_id": other_ep,
                        "domain": "character_appearance",
                        "character": char_name,
                        "description": (
                            f"Appearance drift for {char_name}: "
                            f"'{first_ep}' says '{first_app[:80]}' "
                            f"but '{other_ep}' says '{other_app[:80]}'"
                        ),
                        "severity": "warning",
                        "contradictions": contradictions,
                    })

    # ── Domain 2: Story thread continuity ────────────────────────────────
    story_threads = series_arc.get("story_threads", [])
    for thread in story_threads:
        thread_id = thread.get("id", "unknown")
        introduced_ep = thread.get("introduced_in")
        resolved_ep = thread.get("resolved_in")

        if introduced_ep and resolved_ep:
            # Verify resolution episode comes after introduction episode
            ep_numbers = {
                ep["episode_id"]: ep.get("episode_number", 0)
                for ep in manifest.get("episodes", [])
            }
            intro_num = ep_numbers.get(introduced_ep, 0)
            resolve_num = ep_numbers.get(resolved_ep, 0)

            if resolve_num > 0 and intro_num > 0 and resolve_num <= intro_num:
                violations.append({
                    "episode_id": resolved_ep,
                    "domain": "story_thread",
                    "thread_id": thread_id,
                    "description": (
                        f"Thread '{thread_id}' resolves in ep{resolve_num} "
                        f"but is introduced in ep{intro_num} — resolution before introduction"
                    ),
                    "severity": "error",
                })

    # ── Domain 3: Visual continuity metadata ────────────────────────────
    visual_continuity = series_arc.get("visual_continuity", {})
    series_palette = visual_continuity.get("color_palette", "")

    for ep in episodes_with_plans:
        ep_id = ep["episode_id"]
        bible_path = ep.get("story_bible_path")
        if not bible_path or not Path(bible_path).exists():
            continue

        bible = json.load(open(bible_path))
        ep_palette = bible.get("color_palette", "")

        if series_palette and ep_palette and series_palette != ep_palette:
            # Advisory only — genre DNA injection handles the actual enforcement
            warnings.append(
                f"{ep_id}: color_palette in story bible ('{ep_palette[:60]}') "
                f"differs from series arc ('{series_palette[:60]}'). "
                f"Genre DNA injection will override at render time."
            )

    # ── Summary ──────────────────────────────────────────────────────────
    errors = [v for v in violations if v.get("severity") == "error"]
    warns = [v for v in violations if v.get("severity") == "warning"]

    passed = len(errors) == 0
    summary = (
        f"{'PASS' if passed else 'FAIL'}: "
        f"{len(errors)} errors, {len(warns)} warnings, {len(warnings)} advisories"
    )

    print(f"\n[SERIES] Continuity validation: {summary}")
    for v in violations:
        prefix = "  ✗" if v.get("severity") == "error" else "  ⚠"
        print(f"{prefix} [{v['domain']}] {v['description'][:100]}")
    for w in warnings:
        print(f"  · {w[:100]}")

    return {
        "passed": passed,
        "violations": violations,
        "warnings": warnings,
        "summary": summary,
    }


def _find_appearance_contradictions(app_a: str, app_b: str) -> list:
    """
    Simple heuristic: find word-pairs that are likely contradictory descriptors.
    Examples: 'blonde' vs 'brunette', 'tall' vs 'short', 'young' vs 'elderly'.
    Returns a list of contradiction pairs found.
    """
    CONTRADICTIONS = [
        {"blonde", "brunette"}, {"blonde", "black hair"}, {"brunette", "silver hair"},
        {"tall", "short"}, {"young", "elderly"}, {"young", "aged"},
        {"slim", "heavy-set"}, {"slim", "stocky"}, {"clean-shaven", "bearded"},
        {"pale", "dark skin"}, {"light-skinned", "dark-skinned"},
    ]
    a_lower = app_a.lower()
    b_lower = app_b.lower()
    found = []
    for pair in CONTRADICTIONS:
        pair_list = list(pair)
        if pair_list[0] in a_lower and pair_list[1] in b_lower:
            found.append(f"'{pair_list[0]}' vs '{pair_list[1]}'")
        elif pair_list[1] in a_lower and pair_list[0] in b_lower:
            found.append(f"'{pair_list[1]}' vs '{pair_list[0]}'")
    return found


# ─────────────────────────────────────────────────────────────────────────────
# STUB GENERATION — Create episode stubs for a new series
# ─────────────────────────────────────────────────────────────────────────────

def create_series_manifest(
    series_id: str,
    channel: str,
    genre_dna: str,
    season: int,
    episode_count: int,
    target_duration_minutes: int = 10,
    recurring_characters: Optional[list] = None,
    story_threads: Optional[list] = None,
    airing_schedule: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """
    Generate a new series_manifest.json from scratch.

    Creates EP1 as a stub ready for production (status='not_started') and
    EP2+ as bare stubs. The operator fills in story bibles and titles.

    Args:
        series_id:    Unique identifier, e.g. "victorian_shadows"
        channel:      Channel ID, e.g. "whodunnit"
        genre_dna:    Genre profile key, e.g. "whodunnit_drama"
        season:       Season number (1-based)
        episode_count: Total episodes in the season
        target_duration_minutes: Runtime target per episode
        recurring_characters: List of character dicts (name, canonical_appearance)
        story_threads: List of thread dicts (id, description, introduced_in, resolved_in)
        airing_schedule: dict with time_block_hours, airings_per_48h, premiere_slot
        output_path:  If provided, saves manifest to this path

    Returns:
        The manifest dict (also saves to output_path if provided)
    """
    episodes = []
    for i in range(1, episode_count + 1):
        ep_id = f"{series_id}_ep{i}"
        episodes.append({
            "episode_id": ep_id,
            "episode_number": i,
            "title": f"Episode {i}",
            "story_bible_path": f"story_bibles/{ep_id}.json",
            "shot_plan_path": f"pipeline_outputs/{ep_id}/shot_plan.json",
            "status": "not_started",
            "scene_count": None,
            "shot_count": None,
            "target_duration_minutes": target_duration_minutes,
            "stitched_video_path": None,
            "genre_dna_override": None,
            "_created_at": datetime.utcnow().isoformat(),
            "_last_updated": None,
        })

    manifest = {
        "_schema_version": SERIES_MANIFEST_SCHEMA_VERSION,
        "series_id": series_id,
        "channel": channel,
        "genre_dna": genre_dna,
        "season": season,
        "episode_count": episode_count,
        "episodes": episodes,
        "series_arc": {
            "recurring_characters": recurring_characters or [],
            "story_threads": story_threads or [],
            "visual_continuity": {
                "color_palette": "",
                "lighting_rig_template": "",
                "notes": "",
            },
        },
        "airing_schedule": airing_schedule or {
            "time_block_hours": 12,
            "airings_per_48h": 4,
            "premiere_slot": None,
        },
        "_created_at": datetime.utcnow().isoformat(),
        "_last_updated": None,
    }

    if output_path:
        save_manifest(manifest, output_path)

    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ATLAS Series Orchestrator — sequence episodes through the runner"
    )
    parser.add_argument("manifest", help="Path to series_manifest.json")
    parser.add_argument("--mode", default="lite", choices=["lite", "full"])
    parser.add_argument("--frames-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-stop-on-failure", action="store_true")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run continuity validation only, no generation",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print episode status table and exit",
    )

    args = parser.parse_args()

    manifest = load_manifest(args.manifest)

    if args.status:
        print(f"\nSeries: {manifest['series_id']} — Season {manifest['season']}")
        print(f"{'Episode':<35} {'#':<4} {'Status'}")
        print("-" * 60)
        for ep_id, ep_num, status in list_episode_statuses(manifest):
            print(f"  {ep_id:<33} {str(ep_num):<4} {status}")
        sys.exit(0)

    if args.validate_only:
        result = validate_series_continuity(manifest)
        sys.exit(0 if result["passed"] else 1)

    summary = run_series(
        args.manifest,
        mode=args.mode,
        frames_only=args.frames_only,
        videos_only=args.videos_only,
        dry_run=args.dry_run,
        stop_on_failure=not args.no_stop_on_failure,
    )

    sys.exit(0 if summary["episodes_failed"] == 0 else 1)
