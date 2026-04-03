#!/usr/bin/env python3
"""
test_gates.py - V15.3 Verification Gate Testing Script

Tests all V15.3 gate-related endpoints to ensure proper operation:
1. /health/gates - Basic gate health check
2. /health/gates?project=<slug> - Project-specific gate status
3. /api/v15/dev/shot-angles - Multi-angle preset generator
4. /api/v153/hardening/status - Production readiness check

Usage:
    python3 tools/test_gates.py
    python3 tools/test_gates.py --project ravencroft_new
    python3 tools/test_gates.py --verbose
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip3 install requests")
    sys.exit(1)

ATLAS_URL = "http://localhost:9999"


class TestResult:
    """Simple test result container."""
    def __init__(self, name: str, passed: bool, message: str = "", details: dict = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}


def test_server_health() -> TestResult:
    """Test basic server health."""
    try:
        resp = requests.get(f"{ATLAS_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "healthy":
                return TestResult("Server Health", True, "Server is healthy")
        return TestResult("Server Health", False, f"Unexpected response: {resp.status_code}")
    except Exception as e:
        return TestResult("Server Health", False, f"Connection failed: {e}")


def test_gates_health() -> TestResult:
    """Test /health/gates endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/health/gates", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "healthy":
                gates = data.get("gates", {})
                available = sum(1 for g in gates.values() if g.get("available"))
                return TestResult(
                    "Gates Health",
                    True,
                    f"{available}/{len(gates)} gates available",
                    {"gates": gates}
                )
            return TestResult("Gates Health", False, f"Status: {data.get('status')}", data)
        return TestResult("Gates Health", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("Gates Health", False, str(e))


def test_gates_with_project(project: str) -> TestResult:
    """Test /health/gates?project=<slug> endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/health/gates", params={"project": project}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            paused_at = data.get("paused_at")
            next_action = data.get("next_action")
            verification = data.get("verification_state", {})

            if paused_at:
                return TestResult(
                    f"Project Gates ({project})",
                    True,
                    f"Paused at {paused_at.upper()} - {next_action}",
                    {
                        "paused_at": paused_at,
                        "next_action": next_action,
                        "verification_state": verification
                    }
                )
            else:
                # All gates passed
                return TestResult(
                    f"Project Gates ({project})",
                    True,
                    "All gates passed",
                    {"verification_state": verification}
                )
        return TestResult(f"Project Gates ({project})", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult(f"Project Gates ({project})", False, str(e))


def test_shot_angles_presets() -> TestResult:
    """Test /api/v15/dev/shot-angles endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/api/v15/dev/shot-angles", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("available"):
                presets = data.get("presets", {})
                return TestResult(
                    "Shot Angles Presets",
                    True,
                    f"{len(presets)} presets available",
                    {"presets": list(presets.keys())}
                )
            return TestResult("Shot Angles Presets", False, "Module not available", data)
        return TestResult("Shot Angles Presets", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("Shot Angles Presets", False, str(e))


def test_shot_angles_generate() -> TestResult:
    """Test /api/v15/dev/shot-angles/generate endpoint."""
    try:
        payload = {
            "shot_id": "TEST_001",
            "base_prompt": "Lady Margaret at the ritual altar, candlelight flicker, gothic manor",
            "preset": "dramatic_dialogue",
            "characters": ["LADY MARGARET", "EVELYN"],
            "location": "ritual chamber"
        }
        resp = requests.post(
            f"{ATLAS_URL}/api/v15/dev/shot-angles/generate",
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                angles = data.get("angles", {})
                if "A" in angles and "B" in angles and "C" in angles:
                    return TestResult(
                        "Shot Angles Generate",
                        True,
                        f"Generated A/B/C angles, total duration: {data.get('total_duration')}s",
                        {"angles": {k: v.get("coverage_role") for k, v in angles.items()}}
                    )
            return TestResult("Shot Angles Generate", False, data.get("error", "Unknown error"), data)
        return TestResult("Shot Angles Generate", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("Shot Angles Generate", False, str(e))


def test_hardening_status() -> TestResult:
    """Test /api/v153/hardening/status endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/api/v153/hardening/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            production_ready = data.get("production_ready", False)
            systems = data.get("systems", {})

            status_items = []
            for sys_name, sys_status in systems.items():
                available = sys_status.get("available", sys_status.get("mandatory", False))
                status_items.append(f"{sys_name}:{'✓' if available else '✗'}")

            return TestResult(
                "V15.3 Hardening Status",
                production_ready,
                f"Production ready: {production_ready} | {' '.join(status_items)}",
                {"systems": systems}
            )
        return TestResult("V15.3 Hardening Status", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("V15.3 Hardening Status", False, str(e))


def test_critic_status() -> TestResult:
    """Test /api/v153/critic/status endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/api/v153/critic/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            available = data.get("available", False)
            return TestResult(
                "Critic Agent Status",
                True,  # Endpoint works even if critic not available
                f"Critic Agent: {'available' if available else 'not loaded (rule-based fallback)'}",
                data
            )
        return TestResult("Critic Agent Status", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("Critic Agent Status", False, str(e))


def test_physics_status() -> TestResult:
    """Test /api/v153/physics/status endpoint."""
    try:
        resp = requests.get(f"{ATLAS_URL}/api/v153/physics/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            available = data.get("available", False)
            return TestResult(
                "Physics Gate Status",
                True,  # Endpoint works even if physics gate not available
                f"Physics Gate: {'available' if available else 'not loaded'}",
                data
            )
        return TestResult("Physics Gate Status", False, f"HTTP {resp.status_code}")
    except Exception as e:
        return TestResult("Physics Gate Status", False, str(e))


def run_all_tests(project: str = None, verbose: bool = False):
    """Run all gate tests."""
    print("=" * 60)
    print("V15.3 GATE VERIFICATION TESTS")
    print("=" * 60)
    print()

    tests = [
        test_server_health,
        test_gates_health,
        test_shot_angles_presets,
        test_shot_angles_generate,
        test_hardening_status,
        test_critic_status,
        test_physics_status,
    ]

    results = []

    for test_func in tests:
        result = test_func()
        results.append(result)

        icon = "✅" if result.passed else "❌"
        print(f"{icon} {result.name}")
        print(f"   {result.message}")
        if verbose and result.details:
            print(f"   Details: {json.dumps(result.details, indent=6)[:200]}...")
        print()

    # Test project-specific gates if provided
    if project:
        result = test_gates_with_project(project)
        results.append(result)

        icon = "✅" if result.passed else "❌"
        print(f"{icon} {result.name}")
        print(f"   {result.message}")
        if verbose and result.details:
            # Show verification state badges
            verification = result.details.get("verification_state", {})
            badges = []
            if verification.get("characters_approved"):
                badges.append("✓ Characters")
            else:
                badges.append("○ Characters")
            if verification.get("casting_approved"):
                badges.append("✓ Casting")
            else:
                badges.append("○ Casting")
            if verification.get("locations_approved"):
                badges.append("✓ Locations")
            else:
                badges.append("○ Locations")
            if verification.get("first_frames_approved"):
                badges.append("✓ First Frames")
            else:
                badges.append("○ First Frames")
            print(f"   Verification: {' | '.join(badges)}")
        print()

    # Summary
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        failed = [r.name for r in results if not r.passed]
        print(f"   Failed: {', '.join(failed)}")

    print("=" * 60)

    return passed == total


def main():
    global ATLAS_URL

    parser = argparse.ArgumentParser(
        description="Test V15.3 verification gate endpoints"
    )
    parser.add_argument(
        "--project", "-p",
        help="Test project-specific gates for this project slug"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed response data"
    )
    parser.add_argument(
        "--server",
        default=ATLAS_URL,
        help=f"ATLAS server URL (default: {ATLAS_URL})"
    )

    args = parser.parse_args()
    ATLAS_URL = args.server

    success = run_all_tests(args.project, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
