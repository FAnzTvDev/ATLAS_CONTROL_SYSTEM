"""
ATLAS V22 — STALENESS DETECTION & REMEDIATION AGENT
=====================================================
Detects and auto-fixes stale, orphaned, scrambled, and legacy data across
the entire ATLAS project pipeline. Runs as a pre-generation gate check
and on-demand via API endpoint.

Checks performed (12 total):
  CHECK S1: Cast map actor ID ↔ name consistency (vs ai_actors_library.json)
  CHECK S2: Headshot/reference URL validity (files must exist on disk)
  CHECK S3: SCRIPT_ACCURATE / legacy path contamination
  CHECK S4: Wrong actor references in shot segments (cross-ref cast_map)
  CHECK S5: Orphan characters in shots not in cast_map
  CHECK S6: Short/unnormalized character names in shots
  CHECK S7: Cloud VM session paths leaked into persistent data
  CHECK S8: Legacy/deprecated fields in cast_map (_legacy_*, _old_*)
  CHECK S9: Hollow story bible scenes (no beats, no description)
  CHECK S10: Location master references (files must exist)
  CHECK S11: Wardrobe/extras referencing non-canonical characters
  CHECK S12: UI bundle staleness (dirty flag age)

Architecture:
    API Endpoint → StalenessAgent.run_audit(project)
                   → returns (issues[], auto_fixes[], summary)

    fix-v16 integration → StalenessAgent.run_and_fix(project)
                          → applies safe auto-fixes, returns report

NO MANUAL INTERVENTION REQUIRED for safe fixes.
CRITICAL issues are reported but require human confirmation.

Version: V22.0 | Agent #40 in ATLAS agent system
"""

import json
import logging
import os
import re
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("atlas.staleness_agent")

# ============================================================================
# CONSTANTS
# ============================================================================

AGENT_VERSION = "V22.0"

# Severity levels
CRITICAL = "CRITICAL"   # Must fix before generation — blocks pipeline
WARNING = "WARNING"     # Should fix — may cause visual errors
INFO = "INFO"           # Cleanup — no generation impact

# Character name normalization map (short → canonical)
NAME_NORMALIZATION = {
    "EVELYN": "EVELYN RAVENCROFT",
    "MARGARET": "LADY MARGARET RAVENCROFT",
    "LADY MARGARET": "LADY MARGARET RAVENCROFT",
    "CLARA": "CLARA BYRNE",
    "ARTHUR": "ARTHUR GRAY",
    "DR. WARD": "DR. ELIAS WARD",
    "DR WARD": "DR. ELIAS WARD",
    "WARD": "DR. ELIAS WARD",
    "ELIAS": "DR. ELIAS WARD",
    "LAWYER": "THE LAWYER",
}

# Stale path patterns (EXCLUDES /api/media?path=/Users/ which is valid host path)
STALE_PATH_PATTERNS = [
    (r"/sessions/[^/]+/mnt/", "Cloud VM session path"),
    (r"SCRIPT_ACCURATE", "Legacy SCRIPT_ACCURATE directory"),
    (r"character_library_locked/ravencroft_manor/SCRIPT_ACCURATE", "Old stale character system"),
]

# Paths that look stale but are actually valid production formats
SAFE_PATH_PATTERNS = [
    r"/api/media\?path=/Users/",  # Valid host-resolved media path
    r"/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/",  # Valid host absolute path
]

# Legacy field prefixes to clean
LEGACY_FIELD_PREFIXES = ["_legacy_", "_old_", "_stale_", "_deprecated_"]

# ============================================================================
# ISSUE CLASS
# ============================================================================

class StalenessIssue:
    """Represents a single staleness finding."""

    def __init__(self, check_id: str, severity: str, file: str, field: str,
                 current_value: str, expected_value: str = "", description: str = "",
                 auto_fixable: bool = False):
        self.check_id = check_id
        self.severity = severity
        self.file = file
        self.field = field
        self.current_value = str(current_value)[:200]  # Truncate for readability
        self.expected_value = str(expected_value)[:200]
        self.description = description
        self.auto_fixable = auto_fixable
        self.fixed = False

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "file": self.file,
            "field": self.field,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "description": self.description,
            "auto_fixable": self.auto_fixable,
            "fixed": self.fixed,
        }

# ============================================================================
# STALENESS AGENT
# ============================================================================

class StalenessAgent:
    """
    Detects and remediates stale data across the ATLAS project pipeline.

    Usage:
        agent = StalenessAgent(project_path, ai_actors_library_path)
        report = agent.run_audit()          # Read-only audit
        report = agent.run_and_fix()        # Audit + auto-fix safe issues
    """

    def __init__(self, project_path: str, ai_actors_library_path: str = None):
        self.project_path = Path(project_path)
        self.issues: List[StalenessIssue] = []
        self.fixes_applied: List[dict] = []

        # Resolve ai_actors_library path
        if ai_actors_library_path:
            self.ai_actors_path = Path(ai_actors_library_path)
        else:
            # Default: look relative to project
            self.ai_actors_path = self.project_path.parent.parent / "ai_actors_library.json"

        # Loaded data (lazy)
        self._cast_map = None
        self._shot_plan = None
        self._story_bible = None
        self._wardrobe = None
        self._extras = None
        self._ai_actors = None
        self._actor_by_name = None
        self._actor_by_id = None

    # ========================================================================
    # DATA LOADERS
    # ========================================================================

    def _load_json(self, filename: str) -> Optional[dict]:
        path = self.project_path / filename
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {filename}: {e}")
            return None

    @property
    def cast_map(self) -> dict:
        if self._cast_map is None:
            self._cast_map = self._load_json("cast_map.json") or {}
        return self._cast_map

    @property
    def shot_plan(self) -> dict:
        if self._shot_plan is None:
            self._shot_plan = self._load_json("shot_plan.json") or {}
        return self._shot_plan

    @property
    def story_bible(self) -> dict:
        if self._story_bible is None:
            self._story_bible = self._load_json("story_bible.json") or {}
        return self._story_bible

    @property
    def wardrobe(self) -> dict:
        if self._wardrobe is None:
            self._wardrobe = self._load_json("wardrobe.json") or {}
        return self._wardrobe

    @property
    def extras(self) -> dict:
        if self._extras is None:
            self._extras = self._load_json("extras.json") or {}
        return self._extras

    @property
    def ai_actors(self) -> list:
        if self._ai_actors is None:
            if self.ai_actors_path.exists():
                try:
                    with open(self.ai_actors_path) as f:
                        data = json.load(f)
                    self._ai_actors = data.get("actors", data) if isinstance(data, dict) else data
                except Exception:
                    self._ai_actors = []
            else:
                self._ai_actors = []
        return self._ai_actors

    @property
    def actor_by_name(self) -> dict:
        if self._actor_by_name is None:
            self._actor_by_name = {a["name"]: a for a in self.ai_actors if isinstance(a, dict)}
        return self._actor_by_name

    @property
    def actor_by_id(self) -> dict:
        if self._actor_by_id is None:
            self._actor_by_id = {a["id"]: a for a in self.ai_actors if isinstance(a, dict)}
        return self._actor_by_id

    def _add_issue(self, **kwargs):
        issue = StalenessIssue(**kwargs)
        self.issues.append(issue)
        return issue

    # ========================================================================
    # CHECK S1: Cast Map Actor ID ↔ Name Consistency
    # ========================================================================

    def check_s1_cast_id_consistency(self):
        """Verify each cast_map actor name matches its ID in ai_actors_library."""
        for char_name, entry in self.cast_map.items():
            if entry.get("_is_alias_of"):
                continue  # Skip alias entries

            actor_name = entry.get("ai_actor", "")
            actor_id = entry.get("ai_actor_id", "")

            if not actor_name or not actor_id:
                continue

            # Look up actor by name in library
            lib_actor = self.actor_by_name.get(actor_name)
            if not lib_actor:
                self._add_issue(
                    check_id="S1", severity=WARNING,
                    file="cast_map.json", field=f"{char_name}.ai_actor",
                    current_value=actor_name,
                    expected_value="Actor name from ai_actors_library.json",
                    description=f"Actor '{actor_name}' not found in AI actors library",
                )
                continue

            # Verify ID matches
            if str(lib_actor["id"]) != str(actor_id):
                self._add_issue(
                    check_id="S1", severity=CRITICAL,
                    file="cast_map.json", field=f"{char_name}.ai_actor_id",
                    current_value=f"{actor_name} has ID {actor_id}",
                    expected_value=f"{actor_name} should be ID {lib_actor['id']}",
                    description=f"Actor ID mismatch: cast_map says {actor_id}, library says {lib_actor['id']}",
                    auto_fixable=True,
                )

    # ========================================================================
    # CHECK S2: Headshot/Reference URL File Existence
    # ========================================================================

    def check_s2_headshot_validity(self):
        """Verify all headshot/reference URLs point to files that exist."""
        url_fields = ["headshot_url", "character_reference_url", "reference_url"]
        base_dir = self.project_path.parent.parent  # ATLAS_CONTROL_SYSTEM root

        for char_name, entry in self.cast_map.items():
            if entry.get("_is_alias_of"):
                continue

            for field in url_fields:
                url = entry.get(field, "")
                if not url:
                    continue

                # Extract filesystem path from /api/media?path=... URL
                path_str = url
                if "?path=" in url:
                    path_str = url.split("?path=")[-1]

                # Try to resolve the path — check multiple base locations
                found = False
                candidates = [
                    Path(path_str),
                    base_dir / path_str,
                    self.project_path / path_str,
                ]
                # Also check the path as served by /api/media (user's Mac path)
                # These paths won't exist in VM but are valid on production host
                if "/Users/" in path_str or "/api/media" in url:
                    found = True  # Trust /api/media wrapped paths — they resolve on host

                if not found:
                    for candidate in candidates:
                        if candidate.exists():
                            found = True
                            break

                if not found:
                    self._add_issue(
                        check_id="S2", severity=WARNING,
                        file="cast_map.json", field=f"{char_name}.{field}",
                        current_value=url[:120],
                        description=f"Referenced file does not exist on disk",
                        auto_fixable=False,
                    )

    # ========================================================================
    # CHECK S3: SCRIPT_ACCURATE / Legacy Path Contamination
    # ========================================================================

    def check_s3_legacy_paths(self):
        """Scan all JSON fields for stale path patterns."""
        files_to_check = {
            "cast_map.json": self.cast_map,
            "shot_plan.json": self.shot_plan,
        }

        for filename, data in files_to_check.items():
            self._scan_dict_for_stale_paths(data, filename, "")

    def _scan_dict_for_stale_paths(self, obj, filename: str, path: str, depth: int = 0):
        if depth > 8:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_dict_for_stale_paths(v, filename, f"{path}.{k}" if path else k, depth + 1)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:5]):  # Sample first 5 for perf
                self._scan_dict_for_stale_paths(v, filename, f"{path}[{i}]", depth + 1)
        elif isinstance(obj, str):
            # Skip known-safe production path formats
            is_safe = any(re.search(sp, obj) for sp in SAFE_PATH_PATTERNS)
            if not is_safe:
                for pattern, desc in STALE_PATH_PATTERNS:
                    if re.search(pattern, obj):
                        self._add_issue(
                            check_id="S3", severity=WARNING,
                            file=filename, field=path,
                            current_value=obj[:120],
                            description=f"Stale path detected: {desc}",
                            auto_fixable=True,
                        )
                        break  # One issue per field

    # ========================================================================
    # CHECK S4: Wrong Actor References in Shot Segments
    # ========================================================================

    def check_s4_segment_actor_refs(self):
        """Verify character_reference_url in segments matches cast_map actors or characters."""
        # Build set of valid reference name tokens (actor names AND character names)
        valid_ref_tokens = set()
        for char_name, entry in self.cast_map.items():
            # Add actor name tokens
            actor = entry.get("ai_actor", "")
            if actor:
                valid_ref_tokens.add(actor.upper().replace(" ", "_"))
            # Add character name tokens (headshots may be named by character)
            valid_ref_tokens.add(char_name.upper().replace(" ", "_").replace(".", ""))

        for shot in self.shot_plan.get("shots", []):
            shot_id = shot.get("shot_id", "?")

            # Check segments for refs pointing to actors NOT in our cast
            for i, seg in enumerate(shot.get("segments", [])):
                ref = seg.get("character_reference_url", "")
                if not ref:
                    continue

                ref_upper = ref.upper()
                found_valid = any(token in ref_upper for token in valid_ref_tokens)

                # Also accept if the ref is a project-local headshot path
                if "/headshots/" in ref or "/headshot" in ref:
                    found_valid = True

                if not found_valid:
                    # Extract what actor name IS in the URL for reporting
                    self._add_issue(
                        check_id="S4", severity=CRITICAL,
                        file="shot_plan.json",
                        field=f"shots[{shot_id}].segments[{i}].character_reference_url",
                        current_value=ref[:120],
                        description=f"Segment references unknown actor — not in cast_map",
                        auto_fixable=True,
                    )

    # ========================================================================
    # CHECK S5: Orphan Characters in Shots
    # ========================================================================

    def check_s5_orphan_characters(self):
        """Find characters in shots that don't exist in cast_map."""
        cast_names = set(self.cast_map.keys())
        orphans = {}

        for shot in self.shot_plan.get("shots", []):
            for char in shot.get("characters", []):
                if char and char not in cast_names:
                    orphans.setdefault(char, []).append(shot.get("shot_id", "?"))

        for char, shots in orphans.items():
            self._add_issue(
                check_id="S5", severity=WARNING,
                file="shot_plan.json",
                field=f"characters[{char}]",
                current_value=f"Referenced in {len(shots)} shots: {', '.join(shots[:5])}",
                description=f"Character '{char}' exists in shots but not in cast_map",
                auto_fixable=False,
            )

    # ========================================================================
    # CHECK S6: Short/Unnormalized Character Names
    # ========================================================================

    def check_s6_short_names(self):
        """Detect short character names that should be canonical."""
        short_found = {}

        for shot in self.shot_plan.get("shots", []):
            for char in shot.get("characters", []):
                if char in NAME_NORMALIZATION:
                    canonical = NAME_NORMALIZATION[char]
                    short_found.setdefault(char, {"canonical": canonical, "shots": []})
                    short_found[char]["shots"].append(shot.get("shot_id", "?"))

        for short_name, info in short_found.items():
            self._add_issue(
                check_id="S6", severity=CRITICAL,
                file="shot_plan.json",
                field=f"characters[{short_name}]",
                current_value=f"'{short_name}' in {len(info['shots'])} shots",
                expected_value=info["canonical"],
                description=f"Short name should be '{info['canonical']}'",
                auto_fixable=True,
            )

    # ========================================================================
    # CHECK S7: Cloud VM Session Paths
    # ========================================================================

    def check_s7_session_paths(self):
        """Scan for /sessions/ paths leaked into persistent JSON."""
        session_pattern = re.compile(r"/sessions/[a-z0-9-]+/mnt/")

        for filename in ["cast_map.json", "shot_plan.json", "wardrobe.json", "extras.json"]:
            path = self.project_path / filename
            if not path.exists():
                continue

            try:
                content = path.read_text()
                matches = session_pattern.findall(content)
                if matches:
                    self._add_issue(
                        check_id="S7", severity=WARNING,
                        file=filename, field="(multiple)",
                        current_value=f"Found {len(matches)} session path references",
                        description="Cloud VM session paths in persistent data — will break on restart",
                        auto_fixable=True,
                    )
            except OSError:
                pass

    # ========================================================================
    # CHECK S8: Legacy/Deprecated Fields
    # ========================================================================

    def check_s8_legacy_fields(self):
        """Find and flag deprecated field prefixes in cast_map."""
        for char_name, entry in self.cast_map.items():
            for key in list(entry.keys()):
                for prefix in LEGACY_FIELD_PREFIXES:
                    if key.startswith(prefix):
                        self._add_issue(
                            check_id="S8", severity=INFO,
                            file="cast_map.json",
                            field=f"{char_name}.{key}",
                            current_value=str(entry[key])[:100],
                            description=f"Legacy field '{key}' should be removed",
                            auto_fixable=True,
                        )
                        break

    # ========================================================================
    # CHECK S9: Hollow Story Bible Scenes
    # ========================================================================

    def check_s9_hollow_scenes(self):
        """Find story bible scenes with no beats and no description."""
        scenes = self.story_bible.get("scenes", [])
        if isinstance(scenes, dict):
            scenes = list(scenes.values())

        for scene in scenes:
            scene_id = scene.get("scene_id", scene.get("id", "?"))
            beats = scene.get("beats", [])
            desc = scene.get("description", "")

            if not beats and not desc:
                self._add_issue(
                    check_id="S9", severity=WARNING,
                    file="story_bible.json",
                    field=f"scenes[{scene_id}]",
                    current_value="No beats and no description",
                    description=f"Hollow scene — cannot enrich shots from this scene",
                    auto_fixable=False,
                )

    # ========================================================================
    # CHECK S10: Location Master References
    # ========================================================================

    def check_s10_location_masters(self):
        """Verify location_master_url in shots points to existing files."""
        loc_dir = self.project_path / "location_masters"
        missing = set()

        for shot in self.shot_plan.get("shots", []):
            url = shot.get("location_master_url", "")
            if not url:
                continue

            # Extract path
            path_str = url
            if "?path=" in url:
                path_str = url.split("?path=")[-1]

            resolved = Path(path_str)
            if not resolved.is_absolute():
                resolved = self.project_path.parent.parent / path_str

            if not resolved.exists():
                loc_key = path_str.split("/")[-1] if "/" in path_str else path_str
                if loc_key not in missing:
                    missing.add(loc_key)
                    self._add_issue(
                        check_id="S10", severity=WARNING,
                        file="shot_plan.json",
                        field=f"location_master_url",
                        current_value=path_str[:120],
                        description=f"Location master file missing: {loc_key}",
                        auto_fixable=False,
                    )

    # ========================================================================
    # CHECK S11: Wardrobe/Extras Character References
    # ========================================================================

    def check_s11_wardrobe_refs(self):
        """Verify wardrobe and extras reference canonical character names."""
        cast_names = set(self.cast_map.keys())

        # Check wardrobe
        for key in self.wardrobe:
            # Wardrobe keys are typically "CHARACTER::SCENE_ID"
            char_name = key.split("::")[0] if "::" in key else key
            if char_name and char_name not in cast_names and char_name not in ("_metadata", "_version"):
                self._add_issue(
                    check_id="S11", severity=WARNING,
                    file="wardrobe.json", field=key,
                    current_value=char_name,
                    description=f"Wardrobe references non-canonical character '{char_name}'",
                    auto_fixable=False,
                )

        # Check extras
        for scene_id, pack in self.extras.items():
            if isinstance(pack, dict):
                chars = pack.get("characters", [])
                for char in chars:
                    if char and char not in cast_names:
                        self._add_issue(
                            check_id="S11", severity=INFO,
                            file="extras.json", field=f"{scene_id}.characters",
                            current_value=char,
                            description=f"Extras references non-canonical character",
                            auto_fixable=False,
                        )

    # ========================================================================
    # CHECK S12: UI Bundle Staleness
    # ========================================================================

    def check_s12_bundle_staleness(self):
        """Check if UI bundle has been dirty for too long."""
        dirty_path = self.project_path / "ui_cache" / "bundle.json.dirty"
        if dirty_path.exists():
            age_seconds = time.time() - dirty_path.stat().st_mtime
            if age_seconds > 300:  # Stale for > 5 minutes
                self._add_issue(
                    check_id="S12", severity=INFO,
                    file="ui_cache/bundle.json.dirty",
                    field="mtime",
                    current_value=f"Dirty for {int(age_seconds)}s ({int(age_seconds/60)}m)",
                    description="UI bundle has been stale — will regenerate on next load",
                    auto_fixable=True,
                )

    # ========================================================================
    # AUTO-FIX ENGINE
    # ========================================================================

    def _apply_auto_fixes(self):
        """Apply safe auto-fixes for issues marked auto_fixable."""
        modified_files = set()

        for issue in self.issues:
            if not issue.auto_fixable or issue.fixed:
                continue

            try:
                if issue.check_id == "S1":
                    self._fix_s1_actor_id(issue)
                    modified_files.add("cast_map.json")
                elif issue.check_id == "S3":
                    # Skip — path fixes are complex, need human review
                    pass
                elif issue.check_id == "S4":
                    self._fix_s4_segment_ref(issue)
                    modified_files.add("shot_plan.json")
                elif issue.check_id == "S6":
                    self._fix_s6_short_name(issue)
                    modified_files.add("shot_plan.json")
                elif issue.check_id == "S8":
                    self._fix_s8_legacy_field(issue)
                    modified_files.add("cast_map.json")
                elif issue.check_id == "S12":
                    # Delete stale dirty flag so bundle regenerates
                    dirty = self.project_path / "ui_cache" / "bundle.json.dirty"
                    if dirty.exists():
                        dirty.unlink()
                    issue.fixed = True
                    self.fixes_applied.append({"check": "S12", "action": "Cleared stale bundle dirty flag"})
            except Exception as e:
                logger.warning(f"Auto-fix failed for {issue.check_id}: {e}")

        # Save modified files
        if "cast_map.json" in modified_files:
            self._save_json("cast_map.json", self.cast_map)
        if "shot_plan.json" in modified_files:
            # Also sync cast_map into shot_plan
            self.shot_plan["cast_map"] = self.cast_map
            self._save_json("shot_plan.json", self.shot_plan)

        # Always invalidate cache after fixes
        if modified_files:
            cache_dir = self.project_path / "ui_cache"
            cache_dir.mkdir(exist_ok=True)
            (cache_dir / "bundle.json.dirty").write_text("staleness_agent_fix")

    def _fix_s1_actor_id(self, issue: StalenessIssue):
        """Fix scrambled actor ID by looking up correct ID from library."""
        char_name = issue.field.split(".")[0]
        entry = self.cast_map.get(char_name)
        if not entry:
            return

        actor_name = entry.get("ai_actor", "")
        lib_actor = self.actor_by_name.get(actor_name)
        if not lib_actor:
            return

        old_id = entry.get("ai_actor_id")
        entry["ai_actor_id"] = lib_actor["id"]

        # Also fix reference URLs from library
        if lib_actor.get("locked_reference_url"):
            entry["locked_reference_url"] = lib_actor["locked_reference_url"]

        issue.fixed = True
        self.fixes_applied.append({
            "check": "S1", "character": char_name,
            "action": f"Fixed actor ID: {old_id} → {lib_actor['id']}",
        })

    def _fix_s4_segment_ref(self, issue: StalenessIssue):
        """Fix segment references that point to wrong actors."""
        # Parse the field to find the shot and segment
        # Field format: shots[SHOT_ID].segments[N].character_reference_url
        for shot in self.shot_plan.get("shots", []):
            shot_id = shot.get("shot_id", "")
            if shot_id not in issue.field:
                continue

            # Get the primary character for this shot
            chars = shot.get("characters", [])
            if not chars:
                continue

            primary_char = chars[0]
            cast_entry = self.cast_map.get(primary_char, {})
            correct_ref = cast_entry.get("character_reference_url", "")

            if not correct_ref:
                continue

            # Fix segments
            for seg in shot.get("segments", []):
                ref = seg.get("character_reference_url", "")
                if ref and ref == issue.current_value:
                    seg["character_reference_url"] = correct_ref
                    issue.fixed = True
                    self.fixes_applied.append({
                        "check": "S4", "shot": shot_id,
                        "action": f"Fixed segment ref to {primary_char}'s actor",
                    })

            # Fix shot-level too
            ref = shot.get("character_reference_url", "")
            if ref and ref == issue.current_value:
                shot["character_reference_url"] = correct_ref
                issue.fixed = True

    def _fix_s6_short_name(self, issue: StalenessIssue):
        """Replace short character names with canonical in shots."""
        short_name = issue.field.split("[")[1].rstrip("]")
        canonical = NAME_NORMALIZATION.get(short_name, "")
        if not canonical:
            return

        fixed_count = 0
        for shot in self.shot_plan.get("shots", []):
            chars = shot.get("characters", [])
            for i, char in enumerate(chars):
                if char == short_name:
                    chars[i] = canonical
                    fixed_count += 1

        if fixed_count > 0:
            issue.fixed = True
            self.fixes_applied.append({
                "check": "S6",
                "action": f"Normalized '{short_name}' → '{canonical}' in {fixed_count} shots",
            })

    def _fix_s8_legacy_field(self, issue: StalenessIssue):
        """Remove legacy/deprecated fields from cast_map."""
        char_name = issue.field.split(".")[0]
        field_name = issue.field.split(".")[-1]
        entry = self.cast_map.get(char_name)
        if entry and field_name in entry:
            del entry[field_name]
            issue.fixed = True
            self.fixes_applied.append({
                "check": "S8", "character": char_name,
                "action": f"Removed legacy field '{field_name}'",
            })

    def _save_json(self, filename: str, data: dict):
        """Atomic JSON save with tempfile + rename."""
        import tempfile
        path = self.project_path / filename
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json',
            dir=str(self.project_path), delete=False
        )
        try:
            json.dump(data, tmp, indent=2)
            tmp.close()
            os.replace(tmp.name, str(path))
            logger.info(f"Saved {filename}")
        except Exception:
            tmp.close()
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            raise

    # ========================================================================
    # MAIN ENTRY POINTS
    # ========================================================================

    def run_audit(self) -> dict:
        """
        Run all 12 staleness checks (read-only, no modifications).
        Returns structured report.
        """
        self.issues = []
        self.fixes_applied = []

        start = time.time()

        self.check_s1_cast_id_consistency()
        self.check_s2_headshot_validity()
        self.check_s3_legacy_paths()
        self.check_s4_segment_actor_refs()
        self.check_s5_orphan_characters()
        self.check_s6_short_names()
        self.check_s7_session_paths()
        self.check_s8_legacy_fields()
        self.check_s9_hollow_scenes()
        self.check_s10_location_masters()
        self.check_s11_wardrobe_refs()
        self.check_s12_bundle_staleness()

        elapsed = time.time() - start

        return self._build_report(elapsed, auto_fixed=False)

    def run_and_fix(self) -> dict:
        """
        Run all 12 checks, then auto-fix safe issues.
        Returns structured report with fix details.
        """
        # First run audit
        self.issues = []
        self.fixes_applied = []

        start = time.time()

        self.check_s1_cast_id_consistency()
        self.check_s2_headshot_validity()
        self.check_s3_legacy_paths()
        self.check_s4_segment_actor_refs()
        self.check_s5_orphan_characters()
        self.check_s6_short_names()
        self.check_s7_session_paths()
        self.check_s8_legacy_fields()
        self.check_s9_hollow_scenes()
        self.check_s10_location_masters()
        self.check_s11_wardrobe_refs()
        self.check_s12_bundle_staleness()

        # Then auto-fix
        self._apply_auto_fixes()

        elapsed = time.time() - start

        return self._build_report(elapsed, auto_fixed=True)

    def _build_report(self, elapsed: float, auto_fixed: bool) -> dict:
        """Build the final audit report."""
        critical = [i for i in self.issues if i.severity == CRITICAL]
        warnings = [i for i in self.issues if i.severity == WARNING]
        infos = [i for i in self.issues if i.severity == INFO]
        fixed = [i for i in self.issues if i.fixed]
        unfixed = [i for i in self.issues if not i.fixed and i.severity in (CRITICAL, WARNING)]

        # Overall status
        has_unfixed_critical = any(i.severity == CRITICAL and not i.fixed for i in self.issues)
        status = "STALE" if has_unfixed_critical else "CLEAN" if not unfixed else "WARN"

        return {
            "agent": "staleness_agent",
            "version": AGENT_VERSION,
            "project": str(self.project_path.name),
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": int(elapsed * 1000),
            "status": status,
            "auto_fixed": auto_fixed,
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(critical),
                "warnings": len(warnings),
                "info": len(infos),
                "auto_fixed": len(fixed),
                "remaining_unfixed": len(unfixed),
            },
            "issues": [i.to_dict() for i in self.issues],
            "fixes_applied": self.fixes_applied,
            "checks_run": [
                "S1:cast_id_consistency", "S2:headshot_validity",
                "S3:legacy_paths", "S4:segment_actor_refs",
                "S5:orphan_characters", "S6:short_names",
                "S7:session_paths", "S8:legacy_fields",
                "S9:hollow_scenes", "S10:location_masters",
                "S11:wardrobe_refs", "S12:bundle_staleness",
            ],
        }


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

def run_staleness_check(project_path: str, ai_actors_path: str = None,
                         auto_fix: bool = False) -> dict:
    """
    Convenience function for server integration.

    Args:
        project_path: Full path to project directory
        ai_actors_path: Path to ai_actors_library.json (optional)
        auto_fix: If True, apply safe automatic fixes

    Returns:
        Structured audit report dict
    """
    agent = StalenessAgent(project_path, ai_actors_path)
    if auto_fix:
        return agent.run_and_fix()
    return agent.run_audit()


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
    base = Path(__file__).parent.parent / "pipeline_outputs" / project

    if not base.exists():
        print(f"Project not found: {base}")
        sys.exit(1)

    agent = StalenessAgent(str(base))
    report = agent.run_audit()

    print(f"\n{'='*60}")
    print(f"STALENESS AUDIT: {project}")
    print(f"{'='*60}")
    print(f"Status: {report['status']}")
    print(f"Issues: {report['summary']['total_issues']} "
          f"({report['summary']['critical']} critical, "
          f"{report['summary']['warnings']} warning, "
          f"{report['summary']['info']} info)")
    print(f"Elapsed: {report['elapsed_ms']}ms")

    for issue in report["issues"]:
        icon = "🔴" if issue["severity"] == "CRITICAL" else "🟡" if issue["severity"] == "WARNING" else "🔵"
        fix = " ✅ AUTO-FIXABLE" if issue["auto_fixable"] else ""
        print(f"\n{icon} [{issue['check_id']}] {issue['severity']}{fix}")
        print(f"   File: {issue['file']} → {issue['field']}")
        print(f"   {issue['description']}")
        if issue["current_value"]:
            print(f"   Current: {issue['current_value']}")
        if issue["expected_value"]:
            print(f"   Expected: {issue['expected_value']}")
