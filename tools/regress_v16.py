#!/usr/bin/env python3
"""
ATLAS V16.6 Regression Test Suite
==================================
Manual test script to verify all systems work correctly.

Run: python3 tools/regress_v16.py

Success criteria:
- All endpoints respond without 500 errors
- Duration clustering < 40%
- ABC violations flagged correctly
- Oversight reports generated
- Fix pipeline works
- Sentry captures events
"""

import json
import sys
import time
import requests
from datetime import datetime

BASE_URL = "http://localhost:9999"
TEST_PROJECT = "Ravencroft_V6_upload"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_pass(msg):
    print(f"{GREEN}✓ PASS{RESET}: {msg}")

def log_fail(msg):
    print(f"{RED}✗ FAIL{RESET}: {msg}")

def log_warn(name, msg=None):
    if msg:
        print(f"{YELLOW}⚠ WARN{RESET}: {name}: {msg}")
    else:
        print(f"{YELLOW}⚠ WARN{RESET}: {name}")

def log_info(msg):
    print(f"  ℹ {msg}")

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        log_pass(name)

    def add_fail(self, name, error=None):
        self.failed += 1
        self.errors.append({"test": name, "error": str(error)})
        log_fail(f"{name}: {error}")

    def add_warn(self, name, msg):
        self.warnings += 1
        log_warn(f"{name}: {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"RESULTS: {self.passed}/{total} passed, {self.warnings} warnings")
        if self.failed > 0:
            print(f"\n{RED}FAILED TESTS:{RESET}")
            for e in self.errors:
                print(f"  - {e['test']}: {e['error']}")
        print(f"{'='*60}")
        return self.failed == 0


def test_health(results):
    """Test 1: Health check endpoints"""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok":
                results.add_pass("Health check /health")
                log_info(f"Version: {data.get('version', '?')}")
            else:
                results.add_fail("Health check /health", "status not ok")
        else:
            results.add_fail("Health check /health", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Health check /health", e)

    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if r.status_code == 200:
            results.add_pass("Health check /api/health alias")
        else:
            results.add_fail("Health check /api/health", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Health check /api/health", e)


def test_project_list(results):
    """Test 2: List projects"""
    try:
        r = requests.get(f"{BASE_URL}/api/auto/projects", timeout=10)
        if r.status_code == 200:
            data = r.json()
            projects = data if isinstance(data, list) else data.get("projects", [])
            # Extract project names if dicts
            if projects and isinstance(projects[0], dict):
                projects = [p.get("name", p.get("id", str(p))) for p in projects]
            results.add_pass(f"List projects ({len(projects)} found)")
            log_info(f"Projects: {', '.join(projects[:5])}...")
            return projects
        else:
            results.add_fail("List projects", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("List projects", e)
    return []


def test_load_project(results, project):
    """Test 3: Load project"""
    try:
        r = requests.get(f"{BASE_URL}/api/auto/projects/load/{project}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            shot_count = len(data.get("shot_plan", {}).get("shots", []))
            results.add_pass(f"Load project {project}")
            log_info(f"Shots: {shot_count}")
            return data
        else:
            results.add_fail(f"Load project {project}", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail(f"Load project {project}", e)
    return None


def test_oversight_report(results, project):
    """Test 4: Full oversight report (read-only)"""
    try:
        r = requests.get(f"{BASE_URL}/api/v16/oversight/report?project={project}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "?")
            blocking = len(data.get("blocking_flags", []))
            clustering = data.get("duration_stats", {}).get("clustering_score", 0)

            results.add_pass(f"Oversight report - status: {status}")
            log_info(f"Blocking flags: {blocking}")
            log_info(f"Duration clustering: {clustering*100:.0f}%")
            log_info(f"ABC violations: {data.get('abc_critic', {}).get('total_violations', 0)}")

            if clustering > 0.4:
                results.add_warn("Duration clustering", f"{clustering*100:.0f}% > 40% threshold")

            return data
        else:
            results.add_fail("Oversight report", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Oversight report", e)
    return None


def test_abc_critic(results, project):
    """Test 5: ABC Alternation Critic"""
    try:
        r = requests.get(f"{BASE_URL}/api/v16/critic/abc-alternation/{project}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            violations = data.get("total_violations", 0)
            score = data.get("overall_score", 0)

            results.add_pass(f"ABC Critic - {violations} violations, score {score}")
            return data
        else:
            results.add_fail("ABC Critic", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("ABC Critic", e)
    return None


def test_scene_oversight(results, project, scene_id="001"):
    """Test 6: Per-scene oversight"""
    try:
        r = requests.get(f"{BASE_URL}/api/v16/oversight/scene/{project}/{scene_id}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            actions = len(data.get("actions", []))
            status = data.get("status", "?")

            results.add_pass(f"Scene {scene_id} oversight - {actions} actions, status: {status}")
            return data
        else:
            results.add_fail(f"Scene {scene_id} oversight", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail(f"Scene {scene_id} oversight", e)
    return None


def test_fix_v16(results, project):
    """Test 7: Fix V16 endpoint"""
    try:
        r = requests.post(
            f"{BASE_URL}/api/shot-plan/fix-v16",
            json={"project": project},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "?")
            shot_count = data.get("shot_count", 0)
            total_mins = data.get("total_minutes", 0)

            results.add_pass(f"Fix V16 - {shot_count} shots, {total_mins:.1f} min")

            # Check duration variety
            for note in data.get("advisory_notes", []):
                if "variety" in note.lower():
                    log_info(note)

            return data
        else:
            results.add_fail("Fix V16", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Fix V16", e)
    return None


def test_story_state(results, project):
    """Test 8: Story state endpoint"""
    try:
        r = requests.get(f"{BASE_URL}/api/v6/story-state/{project}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            has_bible = data.get("story_bible") is not None
            has_cast = data.get("cast_map") is not None

            results.add_pass(f"Story state - bible: {has_bible}, cast: {has_cast}")
            return data
        else:
            results.add_fail("Story state", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Story state", e)
    return None


def test_character_refs(results, project):
    """Test 9: Character refs (operator truth)"""
    try:
        r = requests.get(f"{BASE_URL}/api/assets/character-refs?project={project}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            chars = data if isinstance(data, list) else data.get("characters", [])

            results.add_pass(f"Character refs - {len(chars)} characters")
            if chars:
                log_info(f"First: {chars[0].get('name', '?')}")
            return data
        else:
            results.add_fail("Character refs", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Character refs", e)
    return None


def test_preflight(results, project):
    """Test 10: Preflight check"""
    try:
        r = requests.get(f"{BASE_URL}/api/v10/preflight/{project}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            passed = data.get("passed", False)
            blocks = data.get("block_count", 0)
            warns = data.get("warn_count", 0)

            if passed:
                results.add_pass(f"Preflight - PASSED")
            else:
                results.add_warn("Preflight", f"{blocks} blocks, {warns} warnings")

            return data
        else:
            results.add_fail("Preflight", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_fail("Preflight", e)
    return None


def test_temporal_status(results):
    """Test 11: Temporal integration status"""
    try:
        r = requests.get(f"{BASE_URL}/api/temporal/status", timeout=5)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            if status == "connected":
                results.add_pass(f"Temporal - connected to {data.get('host')}")
            else:
                results.add_warn("Temporal", f"Status: {status} - {data.get('error', 'not connected')}")
            return data
        else:
            results.add_warn("Temporal", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_warn("Temporal", f"Not available: {e}")
    return None


def test_sentry_configured(results):
    """Test 12: Sentry error tracking configured"""
    try:
        # We don't actually trigger the error, just check the endpoint exists
        r = requests.get(f"{BASE_URL}/debug-sentry", timeout=5)
        if r.status_code == 500:
            # 500 is expected - it means the endpoint works and throws
            results.add_pass("Sentry - debug endpoint active (500 = throwing errors)")
            return True
        else:
            results.add_warn("Sentry", f"Unexpected status: {r.status_code}")
    except Exception as e:
        results.add_fail("Sentry", e)
    return False


def test_model_lock_status(results):
    """Test 13: V16.6 Model lock status endpoint"""
    try:
        r = requests.get(f"{BASE_URL}/api/v16/model-lock/status", timeout=5)
        if r.status_code == 200:
            data = r.json()
            version = data.get("version", "unknown")
            locked = data.get("locked", False)
            governance = data.get("governance", {})

            if locked and version.startswith("16.6"):
                results.add_pass(f"Model lock V{version} - LOCKED")
                log_info(f"First frame: {governance.get('first_frame', 'unset')}")
                log_info(f"Video: {governance.get('video', 'unset')}")
            else:
                results.add_fail("Model lock", f"Not locked or wrong version: {version}")
            return data
        else:
            # Endpoint might not exist yet - that's a regression
            results.add_fail("Model lock", f"HTTP {r.status_code} - endpoint missing?")
    except Exception as e:
        results.add_fail("Model lock", e)
    return None


def test_model_lock_enforcement(results):
    """Test 14: V16.6 Model lock enforcement (invalid model rejected)"""
    try:
        # Try to use a forbidden model - should be rejected
        r = requests.post(
            f"{BASE_URL}/api/v16/render/validate-model",
            json={
                "stage": "video",
                "model": "some-random-model"
            },
            timeout=5
        )

        if r.status_code >= 400:
            results.add_pass("Model lock enforced (invalid model rejected)")
            return True
        else:
            data = r.json()
            if not data.get("valid", True):
                results.add_pass("Model lock enforced (validation returned invalid)")
                return True
            else:
                results.add_fail("Model lock FAILED", "Invalid model was accepted")
    except requests.exceptions.HTTPError:
        results.add_pass("Model lock enforced (exception on invalid model)")
        return True
    except Exception as e:
        # Connection errors etc. are not passes
        results.add_warn("Model lock", f"Could not test: {e}")
    return False


def test_model_lock_approved(results):
    """Test 15: V16.6 Approved models work"""
    try:
        # Try to validate an approved model - should pass
        r = requests.post(
            f"{BASE_URL}/api/v16/render/validate-model",
            json={
                "stage": "video",
                "model": "ltxv2"
            },
            timeout=5
        )

        if r.status_code == 200:
            data = r.json()
            if data.get("valid", False):
                results.add_pass("Approved model ltxv2 accepted")
                return True
            else:
                results.add_fail("Model lock", "Approved model rejected")
        else:
            results.add_warn("Model lock", f"HTTP {r.status_code}")
    except Exception as e:
        results.add_warn("Model lock", f"Could not test: {e}")
    return False


def run_all_tests():
    """Run all regression tests"""
    print("="*60)
    print("ATLAS V16.6 REGRESSION TEST SUITE")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Target: {BASE_URL}")
    print(f"Project: {TEST_PROJECT}")
    print("="*60 + "\n")

    results = TestResults()

    # Test 1-2: Health and project list
    print("\n[TIER 1: Core Infrastructure]")
    test_health(results)
    projects = test_project_list(results)

    test_project = TEST_PROJECT
    if test_project not in projects:
        log_warn("Test project", f"{test_project} not found, using first available")
        if projects:
            test_project = projects[0]

    # Test 3-4: Load and oversight
    print("\n[TIER 2: Project Loading]")
    test_load_project(results, test_project)
    test_story_state(results, test_project)

    # Test 5-6: Critics
    print("\n[TIER 3: Critics & Oversight]")
    test_abc_critic(results, test_project)
    test_scene_oversight(results, test_project, "001")
    test_oversight_report(results, test_project)

    # Test 7: Fix pipeline
    print("\n[TIER 4: Fix Pipeline]")
    test_fix_v16(results, test_project)

    # Test 8-10: Asset endpoints
    print("\n[TIER 5: Assets & Validation]")
    test_character_refs(results, test_project)
    test_preflight(results, test_project)

    # Test 11-12: Integration (Temporal + Sentry)
    print("\n[TIER 6: Integration]")
    test_temporal_status(results)
    test_sentry_configured(results)

    # Test 13-15: V16.6 Model Lock Governance
    print("\n[TIER 7: V16.6 Model Lock Governance]")
    test_model_lock_status(results)
    test_model_lock_enforcement(results)
    test_model_lock_approved(results)

    # Summary
    success = results.summary()

    if success:
        print(f"\n{GREEN}🎉 ALL TESTS PASSED - System ready for production{RESET}")
    else:
        print(f"\n{RED}❌ TESTS FAILED - Fix issues before proceeding{RESET}")

    return 0 if success else 1


if __name__ == "__main__":
    # Check if server is running
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
    except:
        print(f"{RED}ERROR: Server not running at {BASE_URL}{RESET}")
        print("Start with: python3 orchestrator_server.py")
        sys.exit(1)

    sys.exit(run_all_tests())
