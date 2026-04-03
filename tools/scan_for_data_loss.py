#!/usr/bin/env python3
"""
SCAN FOR DATA LOSS PATTERNS - V17 Factory Guard

Scans the codebase for patterns that silently strip data:
- beat_count = len(beats) without preserving beats
- beats = [] overwrites
- dialogue = "" defaults that strip existing dialogue
- scenes without beats array

Usage:
    python3 tools/scan_for_data_loss.py

Exit codes:
    0 = No data loss patterns found
    1 = Data loss patterns detected (blocks commit)
"""

import re
import sys
from pathlib import Path

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

# Files to scan (Python files in main directory)
SCAN_PATTERNS = [
    # Pattern: Only storing beat_count without beats array
    (r'"beat_count":\s*len\([^)]+\.get\(["\']beats["\']\s*,\s*\[\]\)\)', "beat_count without beats preservation"),

    # Pattern: Overwriting beats with empty array
    (r'["\'"]beats["\'"]\s*:\s*\[\](?!\s*if)', "beats set to empty array"),

    # Pattern: Dropping dialogue
    (r's\.get\(["\']dialogue["\'],\s*["\']["\']', "dialogue defaulting to empty without check"),

    # Pattern: Scenes without beats key
    (r'\{[^}]*"scene_id"[^}]*\}(?![^}]*"beats")', "scene dict without beats key"),
]

# Files to exclude from scanning
EXCLUDE_FILES = [
    "scan_for_data_loss.py",  # This file
    "__pycache__",
    ".git",
    "venv",
    "node_modules",
    "V16.7_FREEZE_ARCHIVE",  # Legacy archive
]

# Allowed patterns (exceptions)
ALLOWED_EXCEPTIONS = [
    "canonical_ingestion.py",  # The canonical path preserves data
    "ui_consistency_enforcer.py",  # The enforcer fixes data
    "test_",  # Test files
]


def should_scan_file(path: Path) -> bool:
    """Check if file should be scanned."""
    path_str = str(path)

    # Skip excluded patterns
    for exclude in EXCLUDE_FILES:
        if exclude in path_str:
            return False

    # Only scan Python files
    if not path.suffix == ".py":
        return False

    return True


def is_allowed_exception(path: Path, pattern_desc: str) -> bool:
    """Check if this pattern is allowed in this file."""
    path_str = str(path)

    for allowed in ALLOWED_EXCEPTIONS:
        if allowed in path_str:
            return True

    return False


def scan_file(path: Path) -> list:
    """Scan a file for data loss patterns."""
    issues = []

    try:
        content = path.read_text()
        lines = content.split('\n')

        for pattern, description in SCAN_PATTERNS:
            for match in re.finditer(pattern, content):
                # Find line number
                start = match.start()
                line_num = content[:start].count('\n') + 1

                # Check if this is an allowed exception
                if is_allowed_exception(path, description):
                    continue

                # Check context - is it actually problematic?
                # Get surrounding lines
                context_start = max(0, line_num - 3)
                context_end = min(len(lines), line_num + 2)
                context = '\n'.join(lines[context_start:context_end])

                # Skip if beats is preserved elsewhere in same block
                if "beat_count" in description and '"beats":' in context and '[]' not in context:
                    continue

                issues.append({
                    "file": str(path.relative_to(BASE_DIR)),
                    "line": line_num,
                    "pattern": description,
                    "match": match.group()[:80]
                })

    except Exception as e:
        pass  # Skip files that can't be read

    return issues


def main():
    print("=" * 60)
    print("ATLAS V17 DATA LOSS PATTERN SCANNER")
    print("=" * 60)

    all_issues = []

    # Scan main directory Python files
    for path in BASE_DIR.glob("*.py"):
        if should_scan_file(path):
            issues = scan_file(path)
            all_issues.extend(issues)

    # Scan atlas_agents directory
    agents_dir = BASE_DIR / "atlas_agents_v16_7" / "atlas_agents"
    if agents_dir.exists():
        for path in agents_dir.glob("*.py"):
            if should_scan_file(path):
                issues = scan_file(path)
                all_issues.extend(issues)

    # Scan tools directory
    tools_dir = BASE_DIR / "tools"
    if tools_dir.exists():
        for path in tools_dir.glob("*.py"):
            if should_scan_file(path):
                issues = scan_file(path)
                all_issues.extend(issues)

    if all_issues:
        print(f"\n❌ FOUND {len(all_issues)} DATA LOSS PATTERNS:\n")
        for issue in all_issues:
            print(f"  {issue['file']}:{issue['line']}")
            print(f"    Pattern: {issue['pattern']}")
            print(f"    Match: {issue['match'][:60]}...")
            print()

        print("=" * 60)
        print("COMMIT BLOCKED - Fix data loss patterns before proceeding")
        print("=" * 60)
        sys.exit(1)
    else:
        print("\n✓ No data loss patterns detected")
        print("  Safe to proceed")
        sys.exit(0)


if __name__ == "__main__":
    main()
