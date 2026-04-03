#!/usr/bin/env python3
"""
ATLAS V17 Production Smoke Test
================================
Validates end-to-end pipeline health before ship.
Run: python3 tools/smoke_test_v17.py [project_name]

Exit codes:
  0 = All checks passed
  1 = Critical failure (blocks ship)
  2 = Warning (can ship with known limitations)
"""

import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# V17: Set up paths before imports
_tools_dir = Path(__file__).parent
_repo_root = _tools_dir.parent
sys.path.insert(0, str(_tools_dir))
sys.path.insert(0, str(_repo_root / "atlas_agents_v16_7"))

# V17: Import auto-heal gate for unified validation
try:
    from auto_heal_gate import run_preflight_gate, run_pre_stitch_gate
    AUTO_HEAL_AVAILABLE = True
except ImportError as e:
    print(f"[DEBUG] auto_heal_gate import failed: {e}")
    AUTO_HEAL_AVAILABLE = False

# V17: Import semantic invariants
try:
    from atlas_agents.semantic_invariants import check_all_invariants
    INVARIANTS_AVAILABLE = True
except ImportError as e:
    print(f"[DEBUG] semantic_invariants import failed: {e}")
    INVARIANTS_AVAILABLE = False

BASE_URL = "http://localhost:9999"
DEFAULT_PROJECT = "kord_v17"

# Golden log markers for grep
MARKERS = {
    "health": "[SMOKE:HEALTH]",
    "r2": "[SMOKE:R2]",
    "bundle": "[SMOKE:BUNDLE]",
    "cast": "[SMOKE:AUTO_CAST]",
    "frame": "[SMOKE:FIRST_FRAME]",
    "video": "[SMOKE:VIDEO_RENDER]",
    "stitch": "[SMOKE:STITCH]",
    "qa": "[SMOKE:QA]",
    "autoheal": "[SMOKE:AUTO_HEAL]",
}

class SmokeTest:
    def __init__(self, project: str):
        self.project = project
        self.results = []
        self.start_time = datetime.now()

    def log(self, marker: str, msg: str, success: bool = True):
        status = "PASS" if success else "FAIL"
        line = f"{MARKERS.get(marker, '[SMOKE]')} [{status}] {msg}"
        print(line)
        self.results.append({"marker": marker, "msg": msg, "success": success})

    def check(self, name: str, condition: bool, msg: str) -> bool:
        self.log(name, msg, condition)
        return condition

    def run_all(self) -> int:
        """Run all smoke tests. Returns exit code."""
        print("=" * 60)
        print(f"ATLAS V17 SMOKE TEST - {self.project}")
        print(f"Started: {self.start_time.isoformat()}")
        print("=" * 60)

        failures = 0
        warnings = 0

        # 1. Health Check
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=5)
            data = r.json()
            if not self.check("health", data.get("status") == "ok", f"Server health: {data}"):
                return 1  # Critical - server down
        except Exception as e:
            self.log("health", f"Server unreachable: {e}", False)
            return 1

        # 2. R2 Status (warning only — V18.3: GCS removed, Cloudflare R2 is sole cloud storage)
        try:
            r = requests.get(f"{BASE_URL}/api/v18/r2/status", timeout=5)
            if r.status_code == 200:
                data = r.json()
                r2_enabled = data.get("configured", False)
                self.log("r2", f"R2 configured={r2_enabled}, bucket={data.get('bucket', 'n/a')}", True)
            else:
                self.log("r2", "R2 endpoint not available (using local mode)", True)
        except:
            self.log("r2", "R2 check skipped (endpoint unavailable)", True)

        # 2b. V17 AUTO-HEAL GATE (Preflight Validation)
        if AUTO_HEAL_AVAILABLE:
            try:
                preflight = run_preflight_gate(self.project, repair=False)

                # Report secrets scan
                secrets = preflight.get("secrets", {})
                if secrets.get("exposed", []):
                    self.log("autoheal", f"CRITICAL: {len(secrets['exposed'])} exposed secrets found!", False)
                    failures += 1
                else:
                    self.log("autoheal", "Secrets scan: CLEAN", True)

                # Report Sentry status
                sentry = preflight.get("sentry", {})
                if sentry.get("required") and not sentry.get("active"):
                    self.log("autoheal", "CRITICAL: LOCKED mode requires Sentry but it's not active", False)
                    failures += 1
                elif sentry.get("active"):
                    self.log("autoheal", "Sentry: ACTIVE", True)
                else:
                    self.log("autoheal", "Sentry: INACTIVE (warning in dev mode)", True)

                # Report model lock
                model_lock = preflight.get("model_lock", {})
                if model_lock.get("violations"):
                    self.log("autoheal", f"CRITICAL: {len(model_lock['violations'])} forbidden model references", False)
                    failures += 1
                else:
                    self.log("autoheal", "Model lock: CLEAN", True)

                # Report segment status
                segments = preflight.get("segments", {})
                if segments.get("issues"):
                    self.log("autoheal", f"Segments: {len(segments['issues'])} issues (repairable)", False)
                    warnings += 1
                else:
                    self.log("autoheal", f"Segments: {segments.get('checked', 0)} extended shots validated", True)

                # Report cast propagation
                cast = preflight.get("cast", {})
                if cast.get("orphans"):
                    self.log("autoheal", f"Cast: {len(cast['orphans'])} shots missing character mapping", False)
                    warnings += 1
                else:
                    self.log("autoheal", f"Cast propagation: {cast.get('checked', 0)} shots validated", True)

                # Report aspect ratio
                aspect = preflight.get("aspect", {})
                if aspect.get("issues"):
                    self.log("autoheal", f"Aspect: {len(aspect['issues'])} first frames wrong ratio", False)
                    warnings += 1
                else:
                    self.log("autoheal", f"Aspect ratio: {aspect.get('checked', 0)} frames validated", True)

            except Exception as e:
                self.log("autoheal", f"Auto-heal gate error: {e}", False)
                warnings += 1
        else:
            self.log("autoheal", "Auto-heal gate not available (import failed)", False)
            warnings += 1

        # 2c. V17 SEMANTIC INVARIANTS
        if INVARIANTS_AVAILABLE:
            try:
                result = check_all_invariants(
                    project=self.project,
                    repo_root=Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
                )

                blocking = result.get("blocking_violations", [])
                warning_list = result.get("warnings", [])
                all_violations = result.get("all_violations", [])
                passed = result.get("passed", False)

                if blocking:
                    for v in blocking[:3]:  # Show first 3
                        msg = f"{v.invariant}: {v.message}" if hasattr(v, 'invariant') else str(v)
                        self.log("autoheal", f"BLOCKING: {msg}", False)
                    failures += len(blocking)
                if warning_list:
                    for v in warning_list[:2]:  # Show first 2
                        msg = f"{v.invariant}: {v.message}" if hasattr(v, 'invariant') else str(v)
                        self.log("autoheal", f"WARNING: {msg}", False)
                    warnings += len(warning_list)
                if passed and not blocking and not warning_list:
                    self.log("autoheal", "Semantic invariants: ALL PASS (9 checks)", True)

            except Exception as e:
                self.log("autoheal", f"Invariants check error: {e}", False)
                warnings += 1
        else:
            self.log("autoheal", "Semantic invariants not available", False)
            warnings += 1

        # 3. Bundle Check
        try:
            r = requests.get(f"{BASE_URL}/api/v16/ui/bundle/{self.project}", timeout=30)
            data = r.json()
            if not data.get("success"):
                self.log("bundle", f"Bundle failed: {data.get('error')}", False)
                failures += 1
            else:
                shots = data.get("shot_plan_summary", {}).get("total_shots", 0)
                cast = len(data.get("cast_map", {}))
                self.log("bundle", f"Bundle OK: {shots} shots, {cast} cast members", True)

                # Check for empty URLs where files exist
                gallery = data.get("shot_gallery_rows", [])
                empty_urls = sum(1 for s in gallery if not s.get("first_frame_url") and s.get("has_first_frame"))
                if empty_urls > 0:
                    self.log("bundle", f"WARNING: {empty_urls} shots have frames but no URL", False)
                    warnings += 1
        except Exception as e:
            self.log("bundle", f"Bundle check failed: {e}", False)
            failures += 1

        # 3b. SEMANTIC INTEGRITY CHECKS (V17.1 Data Loss Detection)
        try:
            project_path = Path(f"/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{self.project}")
            story_bible_path = project_path / "story_bible.json"
            shot_plan_path = project_path / "shot_plan.json"

            if story_bible_path.exists():
                with open(story_bible_path) as f:
                    sb = json.load(f)

                # Check beats not stripped
                scenes = sb.get("scenes", [])
                scenes_with_beats = [s for s in scenes if s.get("beats")]
                if scenes and len(scenes_with_beats) == 0:
                    self.log("bundle", "CRITICAL: Beats stripped from story_bible (dialogue may be lost!)", False)
                    failures += 1
                else:
                    self.log("bundle", f"Semantic OK: {len(scenes_with_beats)}/{len(scenes)} scenes have beats", True)

                # Check locations exist
                locations = sb.get("locations", []) or sb.get("setting", {}).get("locations", [])
                if not locations:
                    self.log("bundle", "WARNING: No locations array in story_bible", False)
                    warnings += 1

            if shot_plan_path.exists():
                with open(shot_plan_path) as f:
                    sp = json.load(f)
                shots_data = sp.get("shots", [])

                # Check for dialogue preservation
                shots_with_dialogue = [s for s in shots_data if s.get("dialogue")]
                self.log("bundle", f"Dialogue: {len(shots_with_dialogue)}/{len(shots_data)} shots have dialogue", True)

                # Check LTX prompt diversity
                ltx_prompts = [s.get("ltx_motion_prompt", "") for s in shots_data if s.get("ltx_motion_prompt")]
                if ltx_prompts:
                    unique_ltx = len(set(ltx_prompts))
                    diversity_pct = unique_ltx / len(ltx_prompts) * 100
                    if diversity_pct < 30:
                        self.log("bundle", f"WARNING: LTX prompts repetitive ({diversity_pct:.0f}% unique)", False)
                        warnings += 1
                    else:
                        self.log("bundle", f"LTX diversity OK: {diversity_pct:.0f}% unique", True)

                # Check for extended shots (if runtime > 10 min)
                total_dur = sum(s.get("duration", 20) for s in shots_data)
                extended = [s for s in shots_data if s.get("duration", 20) > 20]
                if total_dur > 600 and not extended:
                    self.log("bundle", f"WARNING: Runtime {total_dur}s but no extended shots", False)
                    warnings += 1

        except Exception as e:
            self.log("bundle", f"Semantic check error: {e}", False)
            warnings += 1

        # 4. Auto-Cast
        try:
            r = requests.post(f"{BASE_URL}/api/v6/casting/auto-cast",
                            json={"project": self.project}, timeout=30)
            data = r.json()
            if r.status_code == 200 and data.get("success") != False:
                cast_count = data.get("cast_count", data.get("total_cast", 0))
                self.log("cast", f"Auto-cast OK: {cast_count} characters mapped", True)
            else:
                self.log("cast", f"Auto-cast issue: {data.get('error', 'unknown')}", False)
                warnings += 1
        except Exception as e:
            self.log("cast", f"Auto-cast failed: {e}", False)
            failures += 1

        # 5. First Frame Generation (1 shot only)
        try:
            r = requests.post(f"{BASE_URL}/api/auto/generate-first-frames",
                            json={"project": self.project, "limit": 1, "dry_run": True}, timeout=30)
            data = r.json()
            if r.status_code == 200:
                plan = data.get("generation_plan", [])
                self.log("frame", f"Frame gen ready: {len(plan)} shots in plan", True)
            else:
                self.log("frame", f"Frame gen issue: {data.get('error', r.status_code)}", False)
                warnings += 1
        except Exception as e:
            self.log("frame", f"Frame gen check failed: {e}", False)
            warnings += 1

        # 6. Video Generation (1 shot only)
        try:
            r = requests.post(f"{BASE_URL}/api/auto/render-videos",
                            json={"project": self.project, "limit": 1, "dry_run": True}, timeout=30)
            data = r.json()
            if r.status_code == 200:
                plan = data.get("generation_plan", [])
                self.log("video", f"Video gen ready: {len(plan)} shots in plan", True)
            else:
                self.log("video", f"Video gen issue: {data.get('error', r.status_code)}", False)
                warnings += 1
        except Exception as e:
            self.log("video", f"Video gen check failed: {e}", False)
            warnings += 1

        # 7. Stitch Dry-Run (with pre-stitch gate)
        try:
            # V17: Run pre-stitch gate first
            if AUTO_HEAL_AVAILABLE:
                pre_stitch = run_pre_stitch_gate(self.project)
                if not pre_stitch.get("stitch_ready"):
                    blockers = pre_stitch.get("blockers", [])
                    for b in blockers[:3]:
                        self.log("stitch", f"PRE-STITCH BLOCKER: {b}", False)
                    failures += len(blockers)
                else:
                    hash_ok = pre_stitch.get("hash_validation", {}).get("valid", 0)
                    self.log("stitch", f"Pre-stitch gate: PASS ({hash_ok} hashes validated)", True)

            r = requests.post(f"{BASE_URL}/api/v16/stitch/dry-run",
                            json={"project": self.project}, timeout=30)
            data = r.json()
            if r.status_code == 200 and data.get("success"):
                ready = data.get("ready_count", 0)
                total = data.get("total_count", 0)
                # V17: Check for segment issues from server
                segment_issues = data.get("segment_issues", [])
                if segment_issues:
                    self.log("stitch", f"WARNING: {len(segment_issues)} segment integrity issues", False)
                    warnings += 1
                self.log("stitch", f"Stitch dry-run: {ready}/{total} ready", True)
            else:
                self.log("stitch", f"Stitch issue: {data.get('error', 'unknown')}", False)
                warnings += 1
        except Exception as e:
            self.log("stitch", f"Stitch check failed: {e}", False)
            warnings += 1

        # 8. QA Analyze (if shots exist)
        try:
            # Get first shot ID from bundle
            r = requests.get(f"{BASE_URL}/api/v16/ui/bundle/{self.project}", timeout=10)
            bundle = r.json()
            shots = bundle.get("shot_gallery_rows", [])
            if shots:
                shot_id = shots[0].get("shot_id")
                r = requests.post(f"{BASE_URL}/api/v16/qa/analyze",
                                json={"project": self.project, "shot_id": shot_id}, timeout=30)
                if r.status_code == 200:
                    self.log("qa", f"QA analyze OK for {shot_id}", True)
                else:
                    self.log("qa", f"QA analyze issue: {r.status_code}", False)
                    warnings += 1
            else:
                self.log("qa", "No shots to analyze (skipped)", True)
        except Exception as e:
            self.log("qa", f"QA check failed: {e}", False)
            warnings += 1

        # Summary
        print("=" * 60)
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"SMOKE TEST COMPLETE in {elapsed:.1f}s")
        print(f"Failures: {failures}, Warnings: {warnings}")

        if failures > 0:
            print("STATUS: BLOCKED - Critical failures prevent ship")
            return 1
        elif warnings > 0:
            print("STATUS: SHIP WITH CAUTION - Warnings present")
            return 2
        else:
            print("STATUS: SHIP READY - All checks passed")
            return 0


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT
    test = SmokeTest(project)
    sys.exit(test.run_all())


if __name__ == "__main__":
    main()
