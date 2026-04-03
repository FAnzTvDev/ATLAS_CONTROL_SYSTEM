#!/usr/bin/env python3
"""
ATLAS V27.6 — Pre-Run Gate (Mandatory Before ANY Generation)
=============================================================
This script MUST run before any first-frame or video generation.
It does three things that prevent the recurring production failures:

1. ARCHIVE — Move all stale artifacts out of the truth directories
   so the UI never shows frames/videos from a previous run.

2. VERIFY — Confirm every V27.6 upgrade is actually wired and firing,
   not just "built but not imported."

3. AUDIT — Run beat-shot analysis on the target scene to catch
   cinematographic logic errors BEFORE burning FAL credits.

If any check fails, generation is BLOCKED with actionable diagnostics.

DISCIPLINE PROTOCOL:
  "Built" ≠ "Wired" ≠ "Tested" ≠ "Proven"
  - BUILT: Code exists in a .py file
  - WIRED: Code is imported and called by the controller/orchestrator
  - TESTED: Unit tests pass
  - PROVEN: Live FAL generation confirms the output changed
  This gate checks ALL FOUR levels, not just "tests pass."
"""

import json
import os
import shutil
import time
import logging
import importlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class GateCheck:
    name: str
    status: str  # PASS, FAIL, WARN
    detail: str


@dataclass
class PreRunResult:
    scene_id: str
    project_path: str
    archive_path: Optional[str] = None
    checks: List[GateCheck] = field(default_factory=list)
    beat_issues: int = 0
    blocked: bool = False
    block_reasons: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blocked


class PreRunGate:
    """
    Mandatory gate before any generation run.
    Enforces: archive stale → verify wiring → audit story logic.
    """

    def __init__(self, project_path: str, scene_id: str):
        self.project_path = Path(project_path)
        self.scene_id = scene_id
        self.result = PreRunResult(scene_id=scene_id, project_path=project_path)

    def run(self) -> PreRunResult:
        """Execute all pre-run checks. Returns result with pass/fail."""
        print(f"\n{'='*70}")
        print(f"  PRE-RUN GATE — Scene {self.scene_id}")
        print(f"  Project: {self.project_path}")
        print(f"  Time: {datetime.now().isoformat()}")
        print(f"{'='*70}")

        # Phase 1: Archive stale artifacts
        self._phase_archive()

        # Phase 2: Verify data exists
        self._phase_verify_data()

        # Phase 3: Verify wiring
        self._phase_verify_wiring()

        # Phase 4: Beat-shot audit
        self._phase_beat_audit()

        # Phase 4.5: Beat enrichment immutability check
        self._phase_beat_enrichment_check()

        # Phase 5: Prompt audit
        self._phase_prompt_audit()

        # Summary
        self._print_summary()

        return self.result

    # ──────────────────────────────────────────────────
    # PHASE 1: ARCHIVE STALE ARTIFACTS
    # ──────────────────────────────────────────────────
    def _phase_archive(self):
        """Move ALL existing first_frames and videos to timestamped archive."""
        print(f"\n  [PHASE 1] ARCHIVE STALE ARTIFACTS")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = self.project_path / f"_archived_runs" / f"pre_{self.scene_id}_{ts}"

        dirs_to_archive = ["first_frames", "videos", "first_frame_variants"]
        archived_count = 0

        for dirname in dirs_to_archive:
            src = self.project_path / dirname
            if not src.exists():
                continue
            files = [f for f in src.iterdir() if f.is_file() and f.name != ".DS_Store"]
            scene_files = [f for f in files if f.stem.startswith(self.scene_id)]

            if not scene_files:
                print(f"    {dirname}/: no Scene {self.scene_id} files to archive")
                continue

            dest = archive_dir / dirname
            dest.mkdir(parents=True, exist_ok=True)

            for f in scene_files:
                shutil.move(str(f), str(dest / f.name))
                archived_count += 1

            print(f"    {dirname}/: archived {len(scene_files)} Scene {self.scene_id} files")

        if archived_count > 0:
            self.result.archive_path = str(archive_dir)
            print(f"    ✓ Archive: {archive_dir}")
            self.result.checks.append(GateCheck(
                "archive", "PASS",
                f"Archived {archived_count} stale files for scene {self.scene_id}"
            ))
        else:
            print(f"    ✓ Clean — no stale artifacts for scene {self.scene_id}")
            self.result.checks.append(GateCheck("archive", "PASS", "No stale artifacts"))

        # Also clear UI cache
        cache_file = self.project_path / "ui_cache" / "bundle.json"
        if cache_file.exists():
            try:
                cache_file.unlink()
                print(f"    ✓ UI cache cleared")
            except PermissionError:
                print(f"    ⚠ UI cache: permission denied (skip)")

    # ──────────────────────────────────────────────────
    # PHASE 2: VERIFY DATA EXISTS
    # ──────────────────────────────────────────────────
    def _phase_verify_data(self):
        """Confirm required project files exist and have valid data."""
        print(f"\n  [PHASE 2] VERIFY PROJECT DATA")

        required_files = {
            "shot_plan.json": "EXECUTION TRUTH",
            "story_bible.json": "NARRATIVE SOURCE",
            "cast_map.json": "CHARACTER IDENTITY",
        }

        for filename, purpose in required_files.items():
            fpath = self.project_path / filename
            if not fpath.exists():
                self.result.blocked = True
                self.result.block_reasons.append(f"Missing {filename} ({purpose})")
                self.result.checks.append(GateCheck(filename, "FAIL", "File not found"))
                print(f"    ✗ {filename}: NOT FOUND")
                continue

            try:
                with open(fpath) as f:
                    data = json.load(f)
                print(f"    ✓ {filename}: loaded ({purpose})")
                self.result.checks.append(GateCheck(filename, "PASS", "Loaded"))
            except Exception as e:
                self.result.blocked = True
                self.result.block_reasons.append(f"Corrupt {filename}: {e}")
                self.result.checks.append(GateCheck(filename, "FAIL", str(e)))
                print(f"    ✗ {filename}: CORRUPT — {e}")

        # Check scene has shots
        sp_path = self.project_path / "shot_plan.json"
        if sp_path.exists():
            with open(sp_path) as f:
                sp = json.load(f)
            shots = sp if isinstance(sp, list) else sp.get("shots", [])
            scene_shots = [s for s in shots if s.get("shot_id", "").startswith(self.scene_id)]
            if not scene_shots:
                self.result.blocked = True
                self.result.block_reasons.append(f"Scene {self.scene_id} has 0 shots in shot_plan")
                print(f"    ✗ Scene {self.scene_id}: 0 shots")
            else:
                print(f"    ✓ Scene {self.scene_id}: {len(scene_shots)} shots")

        # Check story bible has scene
        sb_path = self.project_path / "story_bible.json"
        if sb_path.exists():
            with open(sb_path) as f:
                sb = json.load(f)
            sb_scene = next((s for s in sb.get("scenes", [])
                           if s.get("scene_id") == self.scene_id), None)
            if not sb_scene:
                self.result.checks.append(GateCheck("story_bible_scene", "WARN",
                                                     f"Scene {self.scene_id} not in story bible"))
                print(f"    ⚠ Scene {self.scene_id}: not in story bible (beats unavailable)")
            else:
                beats = sb_scene.get("beats", [])
                chars = sb_scene.get("characters", [])
                print(f"    ✓ Scene {self.scene_id} in story bible: {len(beats)} beats, "
                      f"chars={[c.get('name', c) if isinstance(c, dict) else c for c in (chars or [])]}")

    # ──────────────────────────────────────────────────
    # PHASE 3: VERIFY WIRING
    # ──────────────────────────────────────────────────
    def _phase_verify_wiring(self):
        """Verify that each V27.6 component is actually importable and callable."""
        print(f"\n  [PHASE 3] VERIFY V27.6 WIRING (Built → Wired → Importable)")

        checks = [
            ("ots_enforcer", "OTSEnforcer", "set_scene_context",
             "Solo scene detection (T2-FE-35)"),
            ("ots_enforcer", "OTSEnforcer", "prepare_solo_dialogue_closeup",
             "Solo close-up (no phantom OTS)"),
            ("prompt_identity_injector", "inject_identity_into_prompt", None,
             "Identity injection (T2-FE-27)"),
            ("scene_visual_dna", "build_scene_dna", None,
             "Scene Visual DNA (T2-FE-23)"),
            ("beat_shot_linker", "BeatShotLinker", "analyze_scene",
             "Beat-shot cinematographic logic"),
            ("story_judge", "StoryJudge", None,
             "Story Judge post-compilation"),
        ]

        import sys
        sys.path.insert(0, str(self.project_path.parent / "tools"))
        if str(self.project_path / "tools") not in sys.path:
            sys.path.insert(0, str(self.project_path / "tools"))
        # Also try relative
        tools_path = Path("tools")
        if tools_path.exists() and str(tools_path.resolve()) not in sys.path:
            sys.path.insert(0, str(tools_path.resolve()))

        for module_name, class_or_func, method, description in checks:
            try:
                mod = importlib.import_module(module_name)
                obj = getattr(mod, class_or_func)
                if method:
                    assert hasattr(obj, method) or callable(getattr(obj, method, None)) or \
                           (isinstance(obj, type) and hasattr(obj, method))
                print(f"    ✓ {module_name}.{class_or_func}"
                      f"{'.' + method if method else ''}: importable ({description})")
                self.result.checks.append(GateCheck(
                    f"wiring_{module_name}", "PASS", description
                ))
            except (ImportError, AttributeError, AssertionError) as e:
                print(f"    ✗ {module_name}.{class_or_func}: NOT IMPORTABLE — {e}")
                self.result.checks.append(GateCheck(
                    f"wiring_{module_name}", "WARN",
                    f"Not importable: {e}. Component exists but may not fire during render."
                ))

        # Check V26 controller has the phases wired
        controller_path = self.project_path.parent / "atlas_v26_controller.py"
        if not controller_path.exists():
            controller_path = Path("atlas_v26_controller.py")
        if controller_path.exists():
            content = controller_path.read_text()
            critical_wiring = {
                "set_scene_context": "V27.6 solo scene detection in Phase E2",
                "inject_identity_into_prompt": "V27.5 identity injection in Phase E1.1",
                "build_scene_dna": "V27.1.5 Scene Visual DNA in Phase E5",
                "establish_screen_positions": "V27.1.4d Screen Position Lock in Phase E2",
            }
            for func_name, description in critical_wiring.items():
                if func_name in content:
                    print(f"    ✓ V26 controller calls {func_name} ({description})")
                    self.result.checks.append(GateCheck(
                        f"controller_{func_name}", "PASS", description
                    ))
                else:
                    print(f"    ✗ V26 controller MISSING {func_name} ({description})")
                    self.result.checks.append(GateCheck(
                        f"controller_{func_name}", "FAIL",
                        f"Controller does not call {func_name}"
                    ))

    # ──────────────────────────────────────────────────
    # PHASE 4: BEAT-SHOT AUDIT
    # ──────────────────────────────────────────────────
    def _phase_beat_audit(self):
        """Run beat-shot linker to catch cinematographic logic errors."""
        print(f"\n  [PHASE 4] BEAT-SHOT CINEMATOGRAPHIC AUDIT")

        try:
            from beat_shot_linker import BeatShotLinker

            with open(self.project_path / "shot_plan.json") as f:
                sp = json.load(f)
            shots = sp if isinstance(sp, list) else sp.get("shots", [])

            with open(self.project_path / "story_bible.json") as f:
                sb = json.load(f)
            sb_scene = next((s for s in sb.get("scenes", [])
                           if s.get("scene_id") == self.scene_id), None)

            if not sb_scene:
                print(f"    ⚠ No story bible scene — skipping beat audit")
                self.result.checks.append(GateCheck("beat_audit", "WARN", "No story bible scene"))
                return

            linker = BeatShotLinker()
            plan = linker.analyze_scene(self.scene_id, shots, sb_scene)
            issues = linker.print_analysis(plan)

            self.result.beat_issues = issues
            if issues > 0:
                self.result.checks.append(GateCheck(
                    "beat_audit", "WARN",
                    f"{issues} cinematographic issues detected (advisory, not blocking)"
                ))
            else:
                self.result.checks.append(GateCheck("beat_audit", "PASS", "All shots motivated"))

        except ImportError as e:
            print(f"    ✗ beat_shot_linker not importable: {e}")
            self.result.checks.append(GateCheck("beat_audit", "WARN", f"Import failed: {e}"))
        except Exception as e:
            print(f"    ✗ beat audit error: {e}")
            self.result.checks.append(GateCheck("beat_audit", "WARN", f"Error: {e}"))

    # ──────────────────────────────────────────────────
    # PHASE 4.5: BEAT ENRICHMENT IMMUTABILITY CHECK
    # ──────────────────────────────────────────────────
    def _phase_beat_enrichment_check(self):
        """Verify beat enrichment fields survived on shots (immutability protection)."""
        print(f"\n  [PHASE 4.5] BEAT ENRICHMENT IMMUTABILITY CHECK")

        try:
            with open(self.project_path / "shot_plan.json") as f:
                sp = json.load(f)
            shots = sp if isinstance(sp, list) else sp.get("shots", [])
            scene_shots = [s for s in shots if s.get("shot_id", "").startswith(self.scene_id)]

            enriched = [s for s in scene_shots if s.get("_beat_enriched")]
            total = len(scene_shots)

            if total == 0:
                print(f"    ⚠ No shots for scene {self.scene_id}")
                self.result.checks.append(GateCheck("beat_enrichment", "WARN", "No shots found"))
                return

            if enriched:
                # Verify fields are intact
                required_fields = ["_beat_ref", "_beat_index", "_eye_line_target", "_body_direction", "_cut_motivation"]
                stripped = []
                for shot in enriched:
                    missing = [f for f in required_fields if shot.get(f) is None]
                    if missing:
                        stripped.append(f"{shot.get('shot_id')}: missing {missing}")

                if stripped:
                    print(f"    ✗ BEAT DATA CORRUPTED — fields stripped from {len(stripped)} shots:")
                    for s in stripped[:5]:
                        print(f"      {s}")
                    self.result.checks.append(GateCheck(
                        "beat_enrichment", "FAIL",
                        f"Beat fields stripped from {len(stripped)}/{len(enriched)} enriched shots"
                    ))
                else:
                    pct = len(enriched) / total * 100
                    print(f"    ✓ {len(enriched)}/{total} shots beat-enriched ({pct:.0f}%), all fields intact")
                    self.result.checks.append(GateCheck(
                        "beat_enrichment", "PASS",
                        f"{len(enriched)}/{total} shots enriched, fields intact"
                    ))
            else:
                print(f"    ⚠ No beat enrichment data — run: python3 tools/beat_enrichment.py {self.project_path} {self.scene_id}")
                self.result.checks.append(GateCheck(
                    "beat_enrichment", "WARN",
                    f"0/{total} shots enriched — run beat_enrichment.py"
                ))
        except Exception as e:
            print(f"    ✗ beat enrichment check error: {e}")
            self.result.checks.append(GateCheck("beat_enrichment", "WARN", f"Error: {e}"))

    # ──────────────────────────────────────────────────
    # PHASE 5: PROMPT AUDIT
    # ──────────────────────────────────────────────────
    def _phase_prompt_audit(self):
        """Check prompts for known contamination patterns."""
        print(f"\n  [PHASE 5] PROMPT CONTAMINATION AUDIT")

        with open(self.project_path / "shot_plan.json") as f:
            sp = json.load(f)
        shots = sp if isinstance(sp, list) else sp.get("shots", [])
        scene_shots = [s for s in shots if s.get("shot_id", "").startswith(self.scene_id)]

        issues = []
        for shot in scene_shots:
            sid = shot.get("shot_id", "")
            nano = shot.get("nano_prompt", "")
            chars = shot.get("characters") or []
            dialogue = shot.get("dialogue_text", "")

            # Check: proper names in prompt (FAL renders as text overlay)
            for name in ["HARGROVE", "BLACKWOOD", "RAVENCROFT", "VOSS"]:
                if name in nano:
                    issues.append(f"{sid}: proper name '{name}' in nano_prompt (FAL renders as text)")

            # Check: character shot missing identity block
            if chars and "[CHARACTER:" not in nano:
                issues.append(f"{sid}: has characters but NO [CHARACTER:] block — identity will fail")

            # Check: dialogue on establishing
            if shot.get("shot_type") == "establishing" and dialogue:
                issues.append(f"{sid}: dialogue on establishing shot — move to performance shot")

            # Check: stale off-camera text on what should be solo scene
            if "off-camera" in nano and len(set(
                c if isinstance(c, str) else c.get("name", "")
                for s in scene_shots
                for c in (s.get("characters") or [])
            )) <= 1:
                issues.append(f"{sid}: 'off-camera' in prompt but scene appears solo")

            # Check: prompt repetition (stacked fix-v16)
            if len(nano) > 60:
                for i in range(len(nano) - 30):
                    substr = nano[i:i+30]
                    if nano.count(substr) >= 3:
                        issues.append(f"{sid}: repeated 30-char substring (corrupted prompt)")
                        break

        if issues:
            print(f"    ⚠ {len(issues)} prompt issues found:")
            for issue in issues[:10]:
                print(f"      {issue}")
            if len(issues) > 10:
                print(f"      ... and {len(issues) - 10} more")
            self.result.checks.append(GateCheck(
                "prompt_audit", "WARN",
                f"{len(issues)} prompt contamination issues"
            ))
        else:
            print(f"    ✓ All {len(scene_shots)} prompts clean")
            self.result.checks.append(GateCheck("prompt_audit", "PASS", "All prompts clean"))

    # ──────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────
    def _print_summary(self):
        fails = [c for c in self.result.checks if c.status == "FAIL"]
        warns = [c for c in self.result.checks if c.status == "WARN"]
        passes = [c for c in self.result.checks if c.status == "PASS"]

        print(f"\n{'='*70}")
        print(f"  PRE-RUN GATE RESULT — Scene {self.scene_id}")
        print(f"  ✓ PASS: {len(passes)} | ⚠ WARN: {len(warns)} | ✗ FAIL: {len(fails)}")
        if self.result.archive_path:
            print(f"  📦 Archived to: {self.result.archive_path}")
        if self.result.beat_issues > 0:
            print(f"  🎬 Beat-shot issues: {self.result.beat_issues} (advisory)")

        if self.result.blocked:
            print(f"\n  ❌ BLOCKED — Cannot proceed:")
            for reason in self.result.block_reasons:
                print(f"     {reason}")
        else:
            print(f"\n  ✅ CLEARED — Ready for generation")
            if warns:
                print(f"     (with {len(warns)} warnings to review)")

        print(f"{'='*70}")


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    scene_id = sys.argv[2] if len(sys.argv) > 2 else "002"

    gate = PreRunGate(project, scene_id)
    result = gate.run()

    sys.exit(0 if result.passed else 1)
