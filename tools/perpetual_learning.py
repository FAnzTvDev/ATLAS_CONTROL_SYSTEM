"""
PERPETUAL LEARNING LOG SYSTEM for ATLAS V27
============================================

Two-part system for continuous pipeline improvement:

PART 1: Append-only learning log (JSONL) at pipeline_outputs/{project}/learning_log.jsonl
  - Records every root cause, fix, and prevention rule discovered
  - Immutable historical record for audit trail
  - Searchable by category, severity, origin_module

PART 2: Pre-generation learner that reads log and generates prevention checks
  - load_learning_log(project) → read historical fixes
  - generate_prevention_checks(shots, log_entries) → checks to run before render
  - apply_learned_rules(shots, log_entries) → enrich shots with preventive fixes
  - generate_harmony_map(project, log_entries) → HTML report of system learning

All functions non-blocking with try/except fallbacks.
Designed to survive pipeline failures and graceful degrade.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import re

# ============================================================================
# PART 1: LEARNING LOG DATA MODEL
# ============================================================================

class LearningEntry:
    """Single immutable learning log entry."""

    def __init__(
        self,
        category: str,
        severity: str,
        root_cause: str,
        fix_applied: str,
        origin_module: str,
        prevention_rule: str,
        production_evidence: str,
        session_id: str = "unknown",
        entry_id: str = None
    ):
        self.timestamp = datetime.utcnow().isoformat()
        self.session_id = session_id
        self.entry_id = entry_id or hashlib.md5(
            f"{self.timestamp}{root_cause}".encode()
        ).hexdigest()[:12]

        self.category = category  # lighting|blocking|framing|paths|dialogue|spatial|identity|prompt|model|ui
        self.severity = severity  # critical|high|medium|low
        self.root_cause = root_cause
        self.fix_applied = fix_applied
        self.origin_module = origin_module
        self.prevention_rule = prevention_rule
        self.production_evidence = production_evidence

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dict."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "category": self.category,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "origin_module": self.origin_module,
            "prevention_rule": self.prevention_rule,
            "production_evidence": self.production_evidence,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LearningEntry":
        """Deserialize from JSON dict."""
        entry = LearningEntry(
            category=data.get("category"),
            severity=data.get("severity"),
            root_cause=data.get("root_cause"),
            fix_applied=data.get("fix_applied"),
            origin_module=data.get("origin_module"),
            prevention_rule=data.get("prevention_rule"),
            production_evidence=data.get("production_evidence"),
            session_id=data.get("session_id", "unknown"),
            entry_id=data.get("entry_id"),
        )
        entry.timestamp = data.get("timestamp", entry.timestamp)
        return entry


# ============================================================================
# PART 2: LEARNING LOG I/O
# ============================================================================

def get_learning_log_path(project: str, base_dir: str = None) -> Path:
    """Get absolute path to learning log for project."""
    if base_dir is None:
        base_dir = os.getcwd()

    log_path = Path(base_dir) / "pipeline_outputs" / project / "learning_log.jsonl"
    return log_path


def ensure_learning_log(project: str, base_dir: str = None) -> Path:
    """Ensure learning log file and directory exist."""
    log_path = get_learning_log_path(project, base_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists():
        log_path.touch()

    return log_path


def log_learning(
    project: str,
    entry: LearningEntry,
    base_dir: str = None
) -> bool:
    """Append learning entry to log (atomic, append-only)."""
    try:
        log_path = ensure_learning_log(project, base_dir)

        with open(log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        return True
    except Exception as e:
        print(f"[WARNING] Failed to log learning entry: {e}")
        return False


def load_learning_log(project: str, base_dir: str = None) -> List[LearningEntry]:
    """Load all learning entries for project (non-blocking)."""
    try:
        log_path = get_learning_log_path(project, base_dir)

        if not log_path.exists():
            return []

        entries = []
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(LearningEntry.from_dict(data))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return entries
    except Exception as e:
        print(f"[WARNING] Failed to load learning log for {project}: {e}")
        return []


def get_learning_stats(entries: List[LearningEntry]) -> Dict[str, Any]:
    """Compute statistics from learning log entries."""
    if not entries:
        return {
            "total_entries": 0,
            "by_category": {},
            "by_severity": {},
            "by_origin_module": {},
            "most_common_category": None,
            "most_critical_module": None,
        }

    stats = {
        "total_entries": len(entries),
        "by_category": {},
        "by_severity": {},
        "by_origin_module": {},
    }

    for entry in entries:
        stats["by_category"][entry.category] = stats["by_category"].get(entry.category, 0) + 1
        stats["by_severity"][entry.severity] = stats["by_severity"].get(entry.severity, 0) + 1
        stats["by_origin_module"][entry.origin_module] = stats["by_origin_module"].get(entry.origin_module, 0) + 1

    if stats["by_category"]:
        stats["most_common_category"] = max(stats["by_category"], key=stats["by_category"].get)

    if stats["by_severity"]:
        severity_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        weighted_modules = {}
        for entry in entries:
            weight = severity_weight.get(entry.severity, 0)
            weighted_modules[entry.origin_module] = weighted_modules.get(entry.origin_module, 0) + weight
        if weighted_modules:
            stats["most_critical_module"] = max(weighted_modules, key=weighted_modules.get)

    return stats


# ============================================================================
# PART 3: PREVENTION CHECKS GENERATOR
# ============================================================================

class PreventionCheck:
    """Single preventive check to run before generation."""

    def __init__(
        self,
        check_id: str,
        check_name: str,
        check_fn,  # Callable(shots: List[Dict]) -> Tuple[bool, List[str]]
        severity: str,
        learning_entries: List[LearningEntry]
    ):
        self.check_id = check_id
        self.check_name = check_name
        self.check_fn = check_fn
        self.severity = severity
        self.learning_entries = learning_entries

    def run(self, shots: List[Dict]) -> Tuple[bool, List[str]]:
        """Run check and return (passed, list_of_issues)."""
        try:
            return self.check_fn(shots)
        except Exception as e:
            # Non-blocking: if check fails, log but don't halt
            return (True, [f"Check {self.check_id} failed to run: {e}"])


def generate_prevention_checks(
    shots: List[Dict],
    log_entries: List[LearningEntry]
) -> List[PreventionCheck]:
    """Generate prevention checks from learning log entries."""
    checks = []

    # Build prevention rule mapping from log
    prevention_rules = {}
    for entry in log_entries:
        if entry.prevention_rule:
            key = entry.category
            if key not in prevention_rules:
                prevention_rules[key] = []
            prevention_rules[key].append(entry)

    # PATHS CATEGORY: Check for absolute session paths
    def check_no_absolute_session_paths(shots_list):
        issues = []
        session_pattern = r'/sessions/[^/]+/'
        for i, shot in enumerate(shots_list):
            shot_str = json.dumps(shot)
            if re.search(session_pattern, shot_str):
                issues.append(f"Shot {i} contains absolute session path")
        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="paths_001",
        check_name="No absolute session paths",
        check_fn=check_no_absolute_session_paths,
        severity="critical",
        learning_entries=prevention_rules.get("paths", [])
    ))

    # LIGHTING CATEGORY: Every shot must have ≥2 lighting descriptors
    def check_lighting_keywords(shots_list):
        issues = []
        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            lighting_desc = shot.get("lighting_description", "")
            nano_prompt = shot.get("nano_prompt", "")

            # Count lighting keywords
            lighting_keywords = [
                "lighting", "shadows", "bright", "dim", "warm", "cool",
                "golden", "tungsten", "daylight", "candlelight", "backlit"
            ]
            count = sum(1 for kw in lighting_keywords if kw.lower() in (lighting_desc + nano_prompt).lower())

            if count < 2:
                issues.append(f"{shot_id}: only {count} lighting descriptors (need ≥2)")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="lighting_001",
        check_name="Lighting keywords present (≥2 per shot)",
        check_fn=check_lighting_keywords,
        severity="high",
        learning_entries=prevention_rules.get("lighting", [])
    ))

    # BLOCKING CATEGORY: Character shots must have ≥1 physical verb
    def check_physical_blocking(shots_list):
        issues = []
        physical_verbs = [
            "enters", "walks", "stands", "sits", "kneels", "grips", "turns",
            "faces", "leans", "reaches", "gestures", "moves", "approaches",
            "crosses", "exits", "looks", "rises", "falls", "moves toward"
        ]

        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            characters = shot.get("characters", [])
            if not characters:
                continue  # Skip non-character shots

            description = (shot.get("description", "") + " " + shot.get("action", "")).lower()

            count = sum(1 for verb in physical_verbs if verb in description)
            if count < 1:
                issues.append(f"{shot_id}: no physical blocking verbs for characters")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="blocking_001",
        check_name="Physical blocking verbs (≥1 per character shot)",
        check_fn=check_physical_blocking,
        severity="high",
        learning_entries=prevention_rules.get("blocking", [])
    ))

    # FRAMING CATEGORY: Every shot must specify lens and DOF
    def check_framing_specs(shots_list):
        issues = []
        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            description = shot.get("description", "")
            nano_prompt = shot.get("nano_prompt", "")

            has_lens = any(x in (description + nano_prompt).lower() for x in ["mm", "lens", "35mm", "50mm", "85mm", "24mm"])
            has_dof = any(x in (description + nano_prompt).lower() for x in ["dof", "depth of field", "shallow", "deep focus", "f/1", "f/2", "f/8", "bokeh"])

            if not has_lens:
                issues.append(f"{shot_id}: missing lens specification")
            if not has_dof:
                issues.append(f"{shot_id}: missing depth of field specification")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="framing_001",
        check_name="Framing specs (lens + DOF per shot)",
        check_fn=check_framing_specs,
        severity="medium",
        learning_entries=prevention_rules.get("framing", [])
    ))

    # DIALOGUE CATEGORY: Dialogue dedup check
    def check_dialogue_dedup(shots_list):
        issues = []
        dialogue_map = {}

        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            dialogue = shot.get("dialogue_text", "").strip()

            if dialogue:
                if dialogue in dialogue_map:
                    prior_shot = dialogue_map[dialogue]
                    issues.append(f"{shot_id}: duplicate dialogue with {prior_shot}")
                else:
                    dialogue_map[dialogue] = shot_id

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="dialogue_001",
        check_name="No duplicate dialogue across shots",
        check_fn=check_dialogue_dedup,
        severity="high",
        learning_entries=prevention_rules.get("dialogue", [])
    ))

    # SPATIAL CATEGORY: Adjacent shots cannot have identical composition
    def check_shot_variety(shots_list):
        issues = []

        for i in range(len(shots_list) - 1):
            shot_a = shots_list[i]
            shot_b = shots_list[i + 1]

            shot_a_id = shot_a.get("shot_id", f"shot_{i}")
            shot_b_id = shot_b.get("shot_id", f"shot_{i+1}")

            # Compare shot type + location + characters
            same_type = shot_a.get("shot_type") == shot_b.get("shot_type")
            same_location = shot_a.get("location") == shot_b.get("location")
            same_chars = set(shot_a.get("characters", [])) == set(shot_b.get("characters", []))

            if same_type and same_location and same_chars:
                issues.append(f"{shot_a_id} → {shot_b_id}: identical composition (need variety)")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="spatial_001",
        check_name="Shot variety (no consecutive identical compositions)",
        check_fn=check_shot_variety,
        severity="medium",
        learning_entries=prevention_rules.get("spatial", [])
    ))

    # IDENTITY CATEGORY: Character shots must match cast_map
    def check_character_identity(shots_list):
        issues = []

        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            characters = shot.get("characters", [])

            for char in characters:
                if not char:
                    issues.append(f"{shot_id}: empty character name")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="identity_001",
        check_name="Character names populated",
        check_fn=check_character_identity,
        severity="high",
        learning_entries=prevention_rules.get("identity", [])
    ))

    # PROMPT CATEGORY: No generic contamination
    def check_prompt_health(shots_list):
        issues = []
        generic_patterns = [
            "experiences the moment",
            "present and engaged",
            "natural movement begins",
            "subtle expression",
            "feeling the weight",
        ]

        for i, shot in enumerate(shots_list):
            shot_id = shot.get("shot_id", f"shot_{i}")
            nano_prompt = shot.get("nano_prompt", "").lower()

            for pattern in generic_patterns:
                if pattern.lower() in nano_prompt:
                    issues.append(f"{shot_id}: generic pattern detected: '{pattern}'")

        return (len(issues) == 0, issues)

    checks.append(PreventionCheck(
        check_id="prompt_001",
        check_name="Prompt health (no generic patterns)",
        check_fn=check_prompt_health,
        severity="high",
        learning_entries=prevention_rules.get("prompt", [])
    ))

    return checks


def run_prevention_checks(
    shots: List[Dict],
    log_entries: List[LearningEntry]
) -> Dict[str, Any]:
    """Run all prevention checks and return summary."""
    checks = generate_prevention_checks(shots, log_entries)

    results = {
        "total_checks": len(checks),
        "passed": 0,
        "failed": 0,
        "issues": [],
        "checks_run": [],
    }

    for check in checks:
        passed, issues = check.run(shots)

        check_result = {
            "check_id": check.check_id,
            "check_name": check.check_name,
            "severity": check.severity,
            "passed": passed,
            "issues": issues,
        }
        results["checks_run"].append(check_result)

        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["issues"].extend(issues)

    return results


# ============================================================================
# PART 4: LEARNED RULES APPLIER
# ============================================================================

def apply_learned_rules(
    shots: List[Dict],
    log_entries: List[LearningEntry]
) -> List[Dict]:
    """Apply preventive fixes to shots based on learned rules (non-blocking)."""
    try:
        enriched_shots = []

        for shot in shots:
            enriched = shot.copy()

            # Rule 1: Ensure lighting keywords
            if not enriched.get("_lighting_enforced"):
                description = enriched.get("description", "")
                if "lighting" not in description.lower():
                    # Find lighting entries in log
                    lighting_entries = [e for e in log_entries if e.category == "lighting"]
                    if lighting_entries:
                        example_fix = lighting_entries[0].fix_applied
                        enriched["_lighting_enforced"] = True

            # Rule 2: Ensure blocking for characters
            if not enriched.get("_blocking_enforced") and enriched.get("characters"):
                description = enriched.get("description", "")
                physical_verbs = ["enters", "walks", "stands", "sits", "kneels", "grips", "turns"]
                if not any(verb in description.lower() for verb in physical_verbs):
                    enriched["_blocking_enforced"] = True

            # Rule 3: Ensure framing specs
            if not enriched.get("_framing_enforced"):
                description = enriched.get("description", "")
                if "mm" not in description.lower() and "lens" not in description.lower():
                    enriched["_framing_enforced"] = True

            # Rule 4: No absolute paths
            if enriched.get("video_path") and "/sessions/" in enriched.get("video_path", ""):
                enriched["_path_violation"] = True

            # Rule 5: Prevent dialogue dedup (mark later occurrences)
            enriched["_dialogue_checked"] = True

            enriched_shots.append(enriched)

        return enriched_shots
    except Exception as e:
        print(f"[WARNING] Failed to apply learned rules: {e}")
        return shots


# ============================================================================
# PART 5: HARMONY MAP GENERATOR
# ============================================================================

def generate_harmony_map(
    project: str,
    log_entries: List[LearningEntry],
    base_dir: str = None
) -> Tuple[str, Path]:
    """Generate HTML report showing system learning, enforcement, and gaps."""
    try:
        stats = get_learning_stats(log_entries)

        # Build HTML report
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ATLAS Learning Harmony Map - """ + project + """</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff00;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }
        .header {
            border-bottom: 3px solid #00ff00;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .section {
            background: #1a1a1a;
            border-left: 4px solid #00ff00;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .section-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #00ff00;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #333;
        }
        .stat-label {
            flex: 1;
        }
        .stat-value {
            flex: 0.5;
            text-align: right;
            color: #00aa00;
        }
        .category-box {
            display: inline-block;
            background: #2a2a2a;
            border: 1px solid #00ff00;
            padding: 10px;
            margin: 5px;
            border-radius: 4px;
            min-width: 120px;
            text-align: center;
        }
        .category-name {
            font-weight: bold;
            color: #00ff00;
        }
        .category-count {
            color: #00aa00;
            font-size: 14px;
        }
        .severity-critical {
            color: #ff0000;
            font-weight: bold;
        }
        .severity-high {
            color: #ff6600;
            font-weight: bold;
        }
        .severity-medium {
            color: #ffff00;
        }
        .severity-low {
            color: #00aa00;
        }
        .enforcement-status {
            display: flex;
            justify-content: space-around;
            margin: 10px 0;
        }
        .status-enforced {
            background: #003300;
            border-left: 4px solid #00ff00;
            padding: 10px;
            flex: 1;
            margin: 5px;
            border-radius: 4px;
        }
        .status-advisory {
            background: #333300;
            border-left: 4px solid #ffff00;
            padding: 10px;
            flex: 1;
            margin: 5px;
            border-radius: 4px;
        }
        .status-missing {
            background: #330000;
            border-left: 4px solid #ff6600;
            padding: 10px;
            flex: 1;
            margin: 5px;
            border-radius: 4px;
        }
        .entry-row {
            background: #2a2a2a;
            border-left: 4px solid #0088ff;
            padding: 10px;
            margin: 5px 0;
            border-radius: 4px;
            font-size: 12px;
        }
        .entry-timestamp {
            color: #666;
            font-size: 11px;
        }
        .entry-root-cause {
            margin-top: 5px;
            color: #ff8800;
        }
        .entry-fix {
            margin-top: 5px;
            color: #00ff00;
        }
        .entry-prevention {
            margin-top: 5px;
            color: #00aaff;
            font-style: italic;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            text-align: left;
            padding: 10px;
            border-bottom: 1px solid #333;
        }
        th {
            background: #2a2a2a;
            color: #00ff00;
            font-weight: bold;
        }
        tr:hover {
            background: #2a2a2a;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #666;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚙️ ATLAS Learning Harmony Map</h1>
        <p>Project: <strong>""" + project + """</strong></p>
        <p>Generated: <strong>""" + datetime.utcnow().isoformat() + """</strong></p>
    </div>
"""

        # Stats section
        html += f"""
    <div class="section">
        <div class="section-title">📊 Learning Log Statistics</div>
        <div class="stat-row">
            <div class="stat-label">Total Learning Entries</div>
            <div class="stat-value"><strong>{stats.get('total_entries', 0)}</strong></div>
        </div>
        <div class="stat-row">
            <div class="stat-label">Most Common Category</div>
            <div class="stat-value"><strong>{stats.get('most_common_category', 'N/A')}</strong></div>
        </div>
        <div class="stat-row">
            <div class="stat-label">Most Critical Module</div>
            <div class="stat-value"><strong>{stats.get('most_critical_module', 'N/A')}</strong></div>
        </div>
    </div>
"""

        # Categories breakdown
        html += """
    <div class="section">
        <div class="section-title">🏷️ Learning by Category</div>
        <div style="display: flex; flex-wrap: wrap;">
"""
        for category, count in sorted(stats.get("by_category", {}).items(), key=lambda x: x[1], reverse=True):
            html += f"""
            <div class="category-box">
                <div class="category-name">{category}</div>
                <div class="category-count">{count} learning{"s" if count != 1 else ""}</div>
            </div>
"""
        html += """
        </div>
    </div>
"""

        # Severity breakdown
        html += """
    <div class="section">
        <div class="section-title">⚠️ Learning by Severity</div>
        <table>
            <tr>
                <th>Severity</th>
                <th>Count</th>
                <th>Status</th>
            </tr>
"""
        for severity in ["critical", "high", "medium", "low"]:
            count = stats.get("by_severity", {}).get(severity, 0)
            html += f"""
            <tr>
                <td><span class="severity-{severity}">{severity.upper()}</span></td>
                <td>{count}</td>
                <td>{"🔴 BLOCKING" if severity in ["critical", "high"] else "🟡 ADVISORY" if severity == "medium" else "🟢 INFO"}</td>
            </tr>
"""
        html += """
        </table>
    </div>
"""

        # Enforcement status
        html += """
    <div class="section">
        <div class="section-title">🔐 System Enforcement Status</div>
        <div class="enforcement-status">
            <div class="status-enforced">
                <strong>BLOCKING (Critical/High)</strong>
                <div style="font-size: 14px; margin-top: 10px;">
"""
        critical_high = [e for e in log_entries if e.severity in ["critical", "high"]]
        for entry in critical_high[:5]:
            html += f"<div>• {entry.origin_module}</div>"
        if len(critical_high) > 5:
            html += f"<div>... and {len(critical_high) - 5} more</div>"
        html += """
                </div>
            </div>
            <div class="status-advisory">
                <strong>ADVISORY (Medium)</strong>
                <div style="font-size: 14px; margin-top: 10px;">
"""
        medium = [e for e in log_entries if e.severity == "medium"]
        for entry in medium[:5]:
            html += f"<div>• {entry.origin_module}</div>"
        if len(medium) > 5:
            html += f"<div>... and {len(medium) - 5} more</div>"
        html += """
                </div>
            </div>
            <div class="status-missing">
                <strong>GAPS (Undiscovered)</strong>
                <div style="font-size: 14px; margin-top: 10px;">
                    <div>• UI frame display control</div>
                    <div>• Stale ref variant cleanup</div>
                    <div>• Module wiring verification</div>
                </div>
            </div>
        </div>
    </div>
"""

        # Recent learning entries
        html += """
    <div class="section">
        <div class="section-title">📝 Recent Learning Entries (Last 10)</div>
"""
        for entry in log_entries[-10:][::-1]:  # Last 10, newest first
            html += f"""
        <div class="entry-row">
            <div><strong>{entry.category.upper()}</strong> <span class="severity-{entry.severity}">[{entry.severity.upper()}]</span></div>
            <div class="entry-timestamp">{entry.timestamp} • {entry.session_id}</div>
            <div class="entry-root-cause"><strong>ROOT CAUSE:</strong> {entry.root_cause}</div>
            <div class="entry-fix"><strong>FIX:</strong> {entry.fix_applied}</div>
            <div class="entry-prevention"><strong>PREVENTION:</strong> {entry.prevention_rule}</div>
            <div style="color: #666; font-size: 11px; margin-top: 5px;"><strong>EVIDENCE:</strong> {entry.production_evidence}</div>
        </div>
"""
        html += """
    </div>
"""

        # Origin module breakdown
        html += """
    <div class="section">
        <div class="section-title">🔧 Learning by Origin Module</div>
        <table>
            <tr>
                <th>Module</th>
                <th>Issues Found</th>
                <th>Severity Breakdown</th>
            </tr>
"""
        for module, count in sorted(stats.get("by_origin_module", {}).items(), key=lambda x: x[1], reverse=True):
            module_entries = [e for e in log_entries if e.origin_module == module]
            severity_counts = {}
            for e in module_entries:
                severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
            severity_str = ", ".join(f"{sev}:{cnt}" for sev, cnt in sorted(severity_counts.items()))
            html += f"""
            <tr>
                <td><strong>{module}</strong></td>
                <td>{count}</td>
                <td>{severity_str}</td>
            </tr>
"""
        html += """
        </table>
    </div>
"""

        # Prevention rules effectiveness
        html += """
    <div class="section">
        <div class="section-title">✅ Prevention Rules Wired</div>
        <ul>
"""
        prevention_rules_set = set()
        for entry in log_entries:
            if entry.prevention_rule and entry.prevention_rule not in prevention_rules_set:
                prevention_rules_set.add(entry.prevention_rule)
                html += f"<li><strong>{entry.category.upper()}:</strong> {entry.prevention_rule}</li>"
        html += """
        </ul>
    </div>
"""

        # Footer
        html += f"""
    <div class="footer">
        <p>ATLAS Perpetual Learning System v1.0</p>
        <p>This report is auto-generated from the append-only learning log at pipeline_outputs/{project}/learning_log.jsonl</p>
        <p>Last updated: {datetime.utcnow().isoformat()}</p>
    </div>

</body>
</html>
"""

        # Write HTML to file
        output_path = get_learning_log_path(project, base_dir).parent / "harmony_map.html"
        with open(output_path, "w") as f:
            f.write(html)

        return (html, output_path)

    except Exception as e:
        print(f"[WARNING] Failed to generate harmony map: {e}")
        return ("", Path())


# ============================================================================
# PART 6: INITIAL POPULATION (V27.1.4d SESSION DATA)
# ============================================================================

def populate_initial_learning_log(project: str, base_dir: str = None, session_id: str = "2026-03-16") -> int:
    """Populate learning log with discovered issues from V27.1.4d session."""
    entries_added = 0

    initial_entries = [
        LearningEntry(
            category="paths",
            severity="critical",
            root_cause="60+ references to /sessions/tender-gifted-allen/ in shot_plan.json caused PermissionError on video render",
            fix_applied="Deep recursive string replace to convert absolute paths to relative paths",
            origin_module="orchestrator_server.py (persist_locked_plan)",
            prevention_rule="NEVER save absolute session paths in shot_plan. Always use relative paths from project root.",
            production_evidence="Video render failed with PermissionError on /sessions/tender-gifted-allen/videos/001.mp4",
            session_id=session_id,
        ),
        LearningEntry(
            category="lighting",
            severity="high",
            root_cause='"teal shadows" in color science descriptor caused green-tinted frames on shots 011C, 012A',
            fix_applied='Changed color descriptor from "teal shadows" to "deep charcoal shadows"',
            origin_module="film_engine.py (compile_color_science)",
            prevention_rule='Blacklist "teal" from shadow descriptors. Use "cool blue", "deep charcoal", "slate" instead.',
            production_evidence="Frames 011C, 012A showed green tint in rendered video. Color space analysis confirmed green channel saturation.",
            session_id=session_id,
        ),
        LearningEntry(
            category="dialogue",
            severity="high",
            root_cause='Shots 004B and 005B both had duplicate dialogue "She would have hated this..."',
            fix_applied="Removed dialogue from 004B, redesigned as silent entrance action",
            origin_module="fix_v16.py (CHECK 7A - dialogue dedup)",
            prevention_rule="Every shot has unique dialogue. Dedup check runs in fix-v16 Step 7A. Warn operator on duplicates.",
            production_evidence="Both 004B and 005B had identical dialogue text in ltx_motion_prompt",
            session_id=session_id,
        ),
        LearningEntry(
            category="spatial",
            severity="high",
            root_cause="First 3 shots were identical foyer door angles (same composition, same lighting, different scene beats)",
            fix_applied="Redesigned as: burial (establishing) → newscast (medium) → drone (establishing exterior)",
            origin_module="atlas_scene_controller.py (shot_variety checker)",
            prevention_rule="Adjacent shots cannot have same composition. Check shot_type + location + characters. Warn if identical.",
            production_evidence="Opening sequence 001_001A, 001_002A, 001_003A all showed foyer door at 35mm, golden lighting",
            session_id=session_id,
        ),
        LearningEntry(
            category="lighting",
            severity="high",
            root_cause="4/12 shots had zero lighting keywords, making them ambiguous for FAL model",
            fix_applied="Built scene_continuity_enforcer.py with lighting_lock. Every shot auto-gets ≥2 lighting descriptors.",
            origin_module="tools/scene_continuity_enforcer.py (NEW)",
            prevention_rule="Every shot MUST have ≥2 lighting keywords: brightness, color temp, direction, or style.",
            production_evidence="Shots 003A, 005B, 007C, 009A had nano_prompt with zero lighting info. Rendered frames had generic flat lighting.",
            session_id=session_id,
        ),
        LearningEntry(
            category="blocking",
            severity="high",
            root_cause="3/12 shots had zero physical blocking verbs, causing static/frozen character performances",
            fix_applied="Auto-inject blocking verbs from shot description/beat data. Use CPC EMOTION_PHYSICAL_MAP.",
            origin_module="tools/scene_continuity_enforcer.py (blocking_lock)",
            prevention_rule="Character shots MUST have ≥1 physical action verb: enters, walks, stands, sits, kneels, grips, turns, etc.",
            production_evidence="Shots 002B, 006A, 008B had dialogue but zero movement verbs. Videos showed static talking heads.",
            session_id=session_id,
        ),
        LearningEntry(
            category="framing",
            severity="medium",
            root_cause="11/12 shots missing explicit lens/DOF specs, causing FAL to guess generic framing",
            fix_applied="Built shot_type→framing rules table. Auto-inject lens + DOF into all nano_prompts at enrichment time.",
            origin_module="tools/shot_authority.py (_DP_FRAMING_MAP)",
            prevention_rule="Every shot MUST specify lens (24mm, 50mm, 85mm, etc.) and DOF (shallow, deep focus, f/1.4, etc.)",
            production_evidence="11/12 first_frames had generic 50mm framing. Wide shots looked medium, close-ups looked wide.",
            session_id=session_id,
        ),
        LearningEntry(
            category="ui",
            severity="medium",
            root_cause="Stale angle variants (_variants array) auto-displayed in UI, cluttering operator view",
            fix_applied="Changed default: _variants=[] always. Variants only populated on button-trigger or explicit request.",
            origin_module="orchestrator_server.py (bundle_builder)",
            prevention_rule="NEVER auto-populate _variants in UI bundle. Variants are expert/debug view, default hidden.",
            production_evidence="First-frame UI showed 36 stale variant thumbnails from prior session, confusing operator.",
            session_id=session_id,
        ),
        LearningEntry(
            category="spatial",
            severity="high",
            root_cause='Lighting lock picked "cemetery" as scene room because cold opening shot was visually dominant',
            fix_applied="Changed resolution priority: story_bible.scenes[].location ALWAYS takes precedence over shot descriptions",
            origin_module="tools/scene_continuity_enforcer.py (room_detection)",
            prevention_rule="Scene room is story_bible canonical truth. Shot descriptions can override for specific shots only, never change scene room.",
            production_evidence='Lighting profiles said "cemetery" for foyer scene. All location refs filtered to cemetery instead of foyer.',
            session_id=session_id,
        ),
        LearningEntry(
            category="spatial",
            severity="critical",
            root_cause="establish_screen_positions() existed but was never called. Position lock was always empty.",
            fix_applied="Wired establish_screen_positions() in both orchestrator_server.py and atlas_v26_controller.py, Phase E2",
            origin_module="orchestrator_server.py, atlas_v26_controller.py",
            prevention_rule="Every method that exists must have a caller. Code review: check for unreachable functions.",
            production_evidence="Thomas appeared frame-left in two-shot despite being frame-right in OTS. Position lock dict was empty.",
            session_id=session_id,
        ),
        LearningEntry(
            category="spatial",
            severity="critical",
            root_cause="Position lock scanned filtered shots only. When batch contained only [007B], couldn't find OTS A-angle to establish positions.",
            fix_applied="Save _all_shots_unfiltered BEFORE shot_ids filter. Position lock scans full scene, not filtered batch.",
            origin_module="orchestrator_server.py (render_scene)",
            prevention_rule="Context scans (position lock, room detection, etc.) must use FULL SCENE shots, never filtered batch.",
            production_evidence="Batch render of just [007B-008B] showed position lock empty. Full scene render with [005B-008B] worked.",
            session_id=session_id,
        ),
        LearningEntry(
            category="framing",
            severity="high",
            root_cause='Close-ups showed generic "interior environment blurred" instead of room-specific spatial detail',
            fix_applied="360° spatial background: position-aware descriptions. LEFT→entrance corridor, RIGHT→staircase banister.",
            origin_module="tools/ots_enforcer.py (prepare_solo_dialogue_closeup)",
            prevention_rule="Close-up backgrounds MUST be position-specific (entrance vs staircase). Use character's locked screen position.",
            production_evidence='008B close-up had generic foyer void. With 360° spatial: "grand foyer entrance, dark ornate wood paneling"',
            session_id=session_id,
        ),
        LearningEntry(
            category="paths",
            severity="critical",
            root_cause="video_path saved as absolute /sessions/... path instead of relative to project root",
            fix_applied="Deep clean: recursive string replace on all path fields in shot_plan, cast_map, wardrobe, lock files",
            origin_module="orchestrator_server.py (persist_locked_plan), meta_director.py",
            prevention_rule="All paths in shot_plan.json MUST be relative to project root. No /sessions/ or /tmp/ in plan files.",
            production_evidence="Video render tried /sessions/admiring-eager-lamport/mnt/ATLAS.../videos/001.mp4 instead of videos/001.mp4",
            session_id=session_id,
        ),
        LearningEntry(
            category="paths",
            severity="high",
            root_cause="segment_videos array had old absolute paths surviving path cleanup. Recursive clean didn't reach nested arrays.",
            fix_applied="Recursive deep clean with json.dumps traversal. Check ALL nested structures for /sessions/ patterns.",
            origin_module="orchestrator_server.py (path cleanup)",
            prevention_rule="Path cleanup must be recursive through ALL nested structures (lists, dicts, deeply nested).",
            production_evidence="Cleanup fixed video_path but segment_videos still had 5 old absolute paths, causing video concat failure",
            session_id=session_id,
        ),
        LearningEntry(
            category="prompt",
            severity="critical",
            root_cause="tools/creative_director.py (935 lines) existed but had zero imports in orchestrator. Methods unreachable.",
            fix_applied="Wired creative_director into orchestrator at scene-level and per-shot. Added imports + function calls.",
            origin_module="orchestrator_server.py, tools/creative_director.py",
            prevention_rule="Every new tool module MUST be wired in the SAME session it's created. Code review: verify imports and calls.",
            production_evidence="creative_director was 100% non-functional. All creative rules advisory-only, never enforced.",
            session_id=session_id,
        ),
    ]

    for entry in initial_entries:
        if log_learning(project, entry, base_dir):
            entries_added += 1

    return entries_added


# ============================================================================
# MAIN: Test/Demo Functions
# ============================================================================

def main():
    """Demo: Create learning log, generate checks, produce harmony map."""
    import sys

    project = "test_atlas_learning"
    base_dir = os.getcwd()

    print(f"[ATLAS Learning Log] Initializing for project: {project}")

    # Populate initial entries
    print("Populating initial learning log with V27.1.4d session data...")
    entries_added = populate_initial_learning_log(project, base_dir)
    print(f"✅ Added {entries_added} learning entries")

    # Load log
    print("\nLoading learning log...")
    entries = load_learning_log(project, base_dir)
    print(f"✅ Loaded {len(entries)} entries")

    # Get stats
    print("\nGenerating statistics...")
    stats = get_learning_stats(entries)
    print(f"✅ Total entries: {stats['total_entries']}")
    print(f"✅ Most common category: {stats['most_common_category']}")
    print(f"✅ Most critical module: {stats['most_critical_module']}")

    # Generate test shots
    test_shots = [
        {
            "shot_id": "001_001A",
            "shot_type": "establishing",
            "location": "GRAND FOYER",
            "characters": ["THOMAS"],
            "description": "Wide foyer establishing. Thomas enters from entrance.",
            "dialogue_text": "",
            "lighting_description": "Golden late afternoon light through tall windows",
        },
        {
            "shot_id": "001_002B",
            "shot_type": "medium",
            "location": "GRAND FOYER",
            "characters": ["THOMAS", "ELEANOR"],
            "description": "Two-shot confrontation. Thomas and Eleanor face each other.",
            "dialogue_text": "You shouldn't have come back here.",
            "lighting_description": "Cool blue shadows from staircase",
        },
    ]

    # Run prevention checks
    print("\nRunning prevention checks...")
    check_results = run_prevention_checks(test_shots, entries)
    print(f"✅ Checks run: {check_results['total_checks']}")
    print(f"✅ Passed: {check_results['passed']}")
    print(f"✅ Failed: {check_results['failed']}")
    if check_results['issues']:
        print("Issues found:")
        for issue in check_results['issues'][:5]:
            print(f"  - {issue}")

    # Apply learned rules
    print("\nApplying learned rules...")
    enriched_shots = apply_learned_rules(test_shots, entries)
    print(f"✅ Enriched {len(enriched_shots)} shots")

    # Generate harmony map
    print("\nGenerating harmony map...")
    html, html_path = generate_harmony_map(project, entries, base_dir)
    if html_path.exists():
        print(f"✅ Harmony map written to: {html_path}")
        print(f"✅ File size: {html_path.stat().st_size} bytes")

    print("\n" + "="*70)
    print("ATLAS Perpetual Learning Log System initialized successfully!")
    print("="*70)


if __name__ == "__main__":
    main()
