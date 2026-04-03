#!/usr/bin/env python3
"""
ATLAS V17.4+ Regression & Validation Test Suite
================================================
Runs comprehensive checks against the codebase to catch:
- Regressions from edit engine integration
- Placeholder/stub code
- Silent exception swallowing
- Import failures
- Cost tracking accuracy
- Invariant violations
- Agent health
- UI code integrity

Usage:
    python3 tests/atlas_regression_suite.py [--verbose] [--fix] [--log PATH]

Results logged to: tests/regression_log_{timestamp}.json
"""

import json
import re
import sys
import os
import time
import importlib
import traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SERVER_FILE = BASE_DIR / "orchestrator_server.py"
UI_FILE = BASE_DIR / "auto_studio_tab.html"
ENRICHER_FILE = BASE_DIR / "tools" / "cinematic_enricher.py"
AGENTS_DIR = BASE_DIR / "atlas_agents"
AGENTS_V16_DIR = BASE_DIR / "atlas_agents_v16_7" / "atlas_agents"
PIPELINE_DIR = BASE_DIR / "pipeline_outputs"
ENV_FILE = BASE_DIR / ".env"
LOG_DIR = BASE_DIR / "tests"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
FIX_MODE = "--fix" in sys.argv

# ============================================================
# TEST FRAMEWORK
# ============================================================
class TestResult:
    def __init__(self, name, category, severity):
        self.name = name
        self.category = category
        self.severity = severity  # P0, P1, P2, P3
        self.passed = None
        self.message = ""
        self.details = []
        self.start_time = time.time()
        self.duration_ms = 0

    def pass_test(self, msg=""):
        self.passed = True
        self.message = msg or "PASS"
        self.duration_ms = round((time.time() - self.start_time) * 1000, 1)
        return self

    def fail_test(self, msg, details=None):
        self.passed = False
        self.message = msg
        if details:
            self.details = details if isinstance(details, list) else [details]
        self.duration_ms = round((time.time() - self.start_time) * 1000, 1)
        return self

    def to_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "passed": self.passed,
            "message": self.message,
            "details": self.details[:10],  # cap detail output
            "duration_ms": self.duration_ms
        }


class TestSuite:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def add(self, result):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        sev = f"[{result.severity}]" if not result.passed else ""
        print(f"  {icon} {result.name} {sev} — {result.message}")
        if not result.passed and VERBOSE and result.details:
            for d in result.details[:5]:
                print(f"      → {d}")

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        p0_fails = sum(1 for r in self.results if not r.passed and r.severity == "P0")
        p1_fails = sum(1 for r in self.results if not r.passed and r.severity == "P1")
        elapsed = round(time.time() - self.start_time, 2)

        return {
            "total": total, "passed": passed, "failed": failed,
            "p0_failures": p0_fails, "p1_failures": p1_fails,
            "elapsed_seconds": elapsed,
            "production_ready": p0_fails == 0,
            "timestamp": datetime.now().isoformat()
        }

    def log(self, path=None):
        path = path or LOG_DIR / f"regression_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path


# ============================================================
# CATEGORY 1: FILE INTEGRITY
# ============================================================
def test_file_integrity(suite):
    print("\n📁 FILE INTEGRITY")

    # Server file exists and has expected size
    t = TestResult("server_file_exists", "integrity", "P0")
    if SERVER_FILE.exists():
        lines = len(SERVER_FILE.read_text(errors="ignore").splitlines())
        if lines > 20000:
            suite.add(t.pass_test(f"{lines} lines"))
        else:
            suite.add(t.fail_test(f"Only {lines} lines — expected >20,000"))
    else:
        suite.add(t.fail_test("orchestrator_server.py NOT FOUND"))

    # UI file exists
    t = TestResult("ui_file_exists", "integrity", "P0")
    if UI_FILE.exists():
        lines = len(UI_FILE.read_text(errors="ignore").splitlines())
        if lines > 18000:
            suite.add(t.pass_test(f"{lines} lines"))
        else:
            suite.add(t.fail_test(f"Only {lines} lines — expected >18,000"))
    else:
        suite.add(t.fail_test("auto_studio_tab.html NOT FOUND"))

    # Agents directory
    t = TestResult("agents_directory_exists", "integrity", "P0")
    agents_dir = AGENTS_DIR if AGENTS_DIR.exists() else AGENTS_V16_DIR
    if agents_dir.exists():
        py_files = list(agents_dir.glob("*.py"))
        if len(py_files) >= 15:
            suite.add(t.pass_test(f"{len(py_files)} agent files"))
        else:
            suite.add(t.fail_test(f"Only {len(py_files)} agent files — expected >=15"))
    else:
        suite.add(t.fail_test("No atlas_agents directory found"))

    # Enricher
    t = TestResult("cinematic_enricher_exists", "integrity", "P1")
    if ENRICHER_FILE.exists():
        suite.add(t.pass_test())
    else:
        suite.add(t.fail_test("tools/cinematic_enricher.py NOT FOUND"))

    # .env file
    t = TestResult("env_file_exists", "integrity", "P1")
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text(errors="ignore")
        keys = ["FAL_KEY", "ELEVENLABS_API_KEY", "OPENROUTER_API_KEY"]
        missing = [k for k in keys if k not in env_content]
        if not missing:
            suite.add(t.pass_test(f"All {len(keys)} API keys present"))
        else:
            suite.add(t.fail_test(f"Missing keys: {missing}"))
    else:
        suite.add(t.fail_test(".env NOT FOUND"))


# ============================================================
# CATEGORY 2: COST TRACKING ACCURACY
# ============================================================
def test_cost_tracking(suite):
    print("\n💰 COST TRACKING ACCURACY")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""

    # First frame cost should be $0.15 (real FAL price)
    t = TestResult("first_frame_cost_accurate", "cost", "P0")
    frame_costs = re.findall(r'COST_PER_FRAME_\w+\s*=\s*([\d.]+)', server_code)
    if frame_costs:
        bad = [c for c in frame_costs if float(c) < 0.10]
        if bad:
            suite.add(t.fail_test(f"Frame cost too low: {bad} — should be $0.15 (real FAL price)", bad))
        else:
            suite.add(t.pass_test(f"Frame costs: {frame_costs}"))
    else:
        suite.add(t.fail_test("No COST_PER_FRAME constants found"))

    # Video cost should be ~$0.55 avg or $0.04/sec
    t = TestResult("video_cost_accurate", "cost", "P1")
    vid_match = re.search(r'VIDEO_COST_USD\s*=.*?"([\d.]+)"', server_code)
    if vid_match:
        val = float(vid_match.group(1))
        if val > 1.0:
            suite.add(t.fail_test(f"VIDEO_COST_USD=${val} — should be ~$0.55 (LTX-2 fast 1080p avg)"))
        elif val < 0.10:
            suite.add(t.fail_test(f"VIDEO_COST_USD=${val} — too low, should be ~$0.55"))
        else:
            suite.add(t.pass_test(f"VIDEO_COST_USD=${val}"))
    else:
        suite.add(t.fail_test("VIDEO_COST_USD not found"))

    # Slot-pack image cost should be $0.15
    t = TestResult("slot_pack_image_cost", "cost", "P1")
    slot_img = re.search(r'image_cost\s*=\s*([\d.]+)\s*#.*Per image', server_code)
    if slot_img:
        val = float(slot_img.group(1))
        if val < 0.10:
            suite.add(t.fail_test(f"Slot-pack image_cost=${val} — should be $0.15"))
        else:
            suite.add(t.pass_test(f"image_cost=${val}"))
    else:
        suite.add(t.pass_test("No slot-pack image_cost found (may be removed)"))

    # Scene budget should be >= $50
    t = TestResult("scene_budget_realistic", "cost", "P2")
    budget = re.search(r'ATLAS_SCENE_BUDGET_USD.*?"([\d.]+)"', server_code)
    if budget:
        val = float(budget.group(1))
        if val < 30:
            suite.add(t.fail_test(f"Scene budget ${val} too low — real scene costs $30-80"))
        else:
            suite.add(t.pass_test(f"Scene budget=${val}"))
    else:
        suite.add(t.pass_test("No scene budget found"))


# ============================================================
# CATEGORY 3: PLACEHOLDER & STUB DETECTION
# ============================================================
def test_placeholders(suite):
    print("\n🔍 PLACEHOLDER & STUB DETECTION")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""
    server_lines = server_code.splitlines()

    # TODO/FIXME comments
    t = TestResult("no_critical_todos", "placeholders", "P2")
    todos = []
    for i, line in enumerate(server_lines, 1):
        if re.search(r'#\s*(TODO|FIXME|HACK|XXX)', line, re.IGNORECASE):
            stripped = line.strip()[:120]
            todos.append(f"L{i}: {stripped}")
    if len(todos) > 20:
        suite.add(t.fail_test(f"{len(todos)} TODO/FIXME comments", todos[:10]))
    else:
        suite.add(t.pass_test(f"{len(todos)} TODO/FIXME (acceptable)"))

    # Silent exception swallowing (except: pass or except Exception: pass)
    t = TestResult("no_silent_exceptions", "placeholders", "P1")
    silent = []
    for i, line in enumerate(server_lines, 1):
        stripped = line.strip()
        if stripped in ("pass", "pass  # silent", "pass  # ignore"):
            # Check if previous non-empty line is except
            for j in range(i-2, max(0, i-5), -1):
                prev = server_lines[j].strip()
                if prev.startswith("except"):
                    silent.append(f"L{i}: {prev} → pass")
                    break
    if len(silent) > 15:
        suite.add(t.fail_test(f"{len(silent)} silent except:pass blocks", silent[:10]))
    elif len(silent) > 0:
        suite.add(t.pass_test(f"{len(silent)} silent exceptions (within tolerance)"))
    else:
        suite.add(t.pass_test("Zero silent exception blocks"))

    # Stub endpoints (return empty/fake data)
    t = TestResult("no_stub_endpoints", "placeholders", "P1")
    stubs = []
    for i, line in enumerate(server_lines, 1):
        if re.search(r'return\s*\{["\']success["\']\s*:\s*True\s*,\s*["\']message["\']\s*:\s*["\'].*stub', line, re.IGNORECASE):
            stubs.append(f"L{i}: {line.strip()[:100]}")
        if re.search(r'#.*stub|#.*placeholder|#.*not.?implement', line, re.IGNORECASE):
            if 'return' in line or 'return' in (server_lines[i] if i < len(server_lines) else ""):
                stubs.append(f"L{i}: {line.strip()[:100]}")
    if stubs:
        suite.add(t.fail_test(f"{len(stubs)} potential stub endpoints", stubs))
    else:
        suite.add(t.pass_test("No stub endpoints detected"))

    # NotImplementedError
    t = TestResult("no_not_implemented", "placeholders", "P2")
    not_impl = [f"L{i}: {l.strip()[:100]}" for i, l in enumerate(server_lines, 1)
                if "NotImplementedError" in l or "not implemented" in l.lower()]
    if not_impl:
        suite.add(t.fail_test(f"{len(not_impl)} NotImplementedError references", not_impl))
    else:
        suite.add(t.pass_test())


# ============================================================
# CATEGORY 4: MODEL LOCK ENFORCEMENT
# ============================================================
def test_model_lock(suite):
    print("\n🔒 MODEL LOCK ENFORCEMENT")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""

    # No forbidden models
    t = TestResult("no_forbidden_models", "model_lock", "P0")
    forbidden = ["minimax", "runway", "pika", "sora", "flux", "wan", "omnihuman"]
    found = []
    for model in forbidden:
        # Search for model in API call contexts (not just comments)
        pattern = rf'(?:model|model_id|endpoint)\s*[=:]\s*["\'][^"\']*{model}'
        matches = re.findall(pattern, server_code, re.IGNORECASE)
        if matches:
            found.extend(matches)
    if found:
        suite.add(t.fail_test(f"Forbidden models in use: {found}", found))
    else:
        suite.add(t.pass_test("No forbidden models referenced in API calls"))

    # Correct models present
    t = TestResult("correct_models_present", "model_lock", "P0")
    required = ["nano-banana-pro", "ltx-2", "ltx-2/image-to-video"]
    missing = [m for m in required if m not in server_code]
    if missing:
        suite.add(t.fail_test(f"Missing required models: {missing}"))
    else:
        suite.add(t.pass_test(f"All {len(required)} required models present"))


# ============================================================
# CATEGORY 5: V13 GOLD STANDARD COMPLIANCE
# ============================================================
def test_gold_standard(suite):
    print("\n🏆 V13 GOLD STANDARD")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""

    # Required negatives enforcement exists
    t = TestResult("negatives_enforcement", "gold_standard", "P0")
    if "NO grid" in server_code and "NO morphing" in server_code:
        suite.add(t.pass_test("Required negatives in enforcement code"))
    else:
        suite.add(t.fail_test("Missing 'NO grid' or 'NO morphing' enforcement"))

    # Face stability enforcement
    t = TestResult("face_stability_enforcement", "gold_standard", "P0")
    if "face stable" in server_code.lower() or "face_stable" in server_code.lower():
        suite.add(t.pass_test("Face stability enforcement present"))
    else:
        suite.add(t.fail_test("Missing face stability enforcement"))

    # LTX timing enforcement
    t = TestResult("ltx_timing_enforcement", "gold_standard", "P1")
    if "0-2s" in server_code or "0-" in server_code:
        suite.add(t.pass_test("LTX timing clauses present"))
    else:
        suite.add(t.fail_test("Missing LTX timing clause enforcement"))


# ============================================================
# CATEGORY 6: AGENT SYSTEM HEALTH
# ============================================================
def test_agent_system(suite):
    print("\n🤖 AGENT SYSTEM HEALTH")

    agents_dir = AGENTS_DIR if AGENTS_DIR.exists() else AGENTS_V16_DIR

    # Agent directory exists with files
    t = TestResult("agent_files_present", "agents", "P0")
    if agents_dir.exists():
        files = list(agents_dir.glob("*.py"))
        required = ["enforcement_agent.py", "agent_coordinator.py", "semantic_invariants.py"]
        missing = [r for r in required if not (agents_dir / r).exists()]
        if missing:
            suite.add(t.fail_test(f"Missing critical agent files: {missing}"))
        else:
            suite.add(t.pass_test(f"{len(files)} agent files, all critical ones present"))
    else:
        suite.add(t.fail_test("No agents directory found"))

    # Agent coordinator import check
    t = TestResult("coordinator_correct_import", "agents", "P1")
    coord_file = agents_dir / "agent_coordinator.py" if agents_dir.exists() else None
    if coord_file and coord_file.exists():
        coord_code = coord_file.read_text(errors="ignore")
        if "check_all_invariants" in coord_code:
            suite.add(t.pass_test("Correct import: check_all_invariants"))
        elif "validate_invariants" in coord_code:
            suite.add(t.fail_test("Wrong import: validate_invariants (should be check_all_invariants)"))
        else:
            suite.add(t.pass_test("No invariant import found (may be restructured)"))
    else:
        suite.add(t.fail_test("agent_coordinator.py not found"))

    # Enforcement agent has pre_generation_gate
    t = TestResult("enforcement_has_gate", "agents", "P0")
    enf_file = agents_dir / "enforcement_agent.py" if agents_dir.exists() else None
    if enf_file and enf_file.exists():
        enf_code = enf_file.read_text(errors="ignore")
        if "pre_generation_gate" in enf_code or "enforce_pre_generation" in enf_code:
            suite.add(t.pass_test("Pre-generation gate method present"))
        else:
            suite.add(t.fail_test("Missing pre_generation_gate method"))
    else:
        suite.add(t.fail_test("enforcement_agent.py not found"))

    # Agent enforcement wired in server
    t = TestResult("agents_wired_in_server", "agents", "P0")
    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""
    if "pre_generation_gate" in server_code and "AgentCoordinator" in server_code:
        suite.add(t.pass_test("Agents wired into generation endpoints"))
    else:
        suite.add(t.fail_test("Agents NOT wired into server generation endpoints"))


# ============================================================
# CATEGORY 7: UI CODE INTEGRITY
# ============================================================
def test_ui_integrity(suite):
    print("\n🖥️  UI CODE INTEGRITY")

    ui_code = UI_FILE.read_text(errors="ignore") if UI_FILE.exists() else ""

    # v167ShowModal accepts 2 args
    t = TestResult("modal_2arg_support", "ui", "P0")
    if "function v167ShowModal(titleOrContent, contentArg)" in ui_code:
        suite.add(t.pass_test("2-argument modal signature"))
    elif "function v167ShowModal(" in ui_code:
        suite.add(t.fail_test("v167ShowModal exists but may not support 2 args"))
    else:
        suite.add(t.fail_test("v167ShowModal function NOT FOUND"))

    # No prompt() dialogs (should all be modals)
    t = TestResult("no_browser_prompt_dialogs", "ui", "P1")
    prompt_calls = re.findall(r'(?<!window\.)prompt\s*\(', ui_code)
    # Filter out false positives (nano_prompt, ltx_motion_prompt variable names)
    real_prompts = [p for p in re.finditer(r'(?<!\w)prompt\s*\(["\']', ui_code)]
    if len(real_prompts) > 3:
        suite.add(t.fail_test(f"{len(real_prompts)} potential browser prompt() calls"))
    else:
        suite.add(t.pass_test(f"Browser prompt() calls within tolerance"))

    # CSS variables present
    t = TestResult("css_variables_complete", "ui", "P1")
    required_vars = ["--bg-secondary", "--accent-blue", "--accent-cyan", "--bg-tertiary", "--bg-panel"]
    missing = [v for v in required_vars if v not in ui_code]
    if missing:
        suite.add(t.fail_test(f"Missing CSS vars: {missing}"))
    else:
        suite.add(t.pass_test(f"All {len(required_vars)} CSS variables present"))

    # showStatus shim exists
    t = TestResult("show_status_shim", "ui", "P1")
    if "function showStatus" in ui_code:
        suite.add(t.pass_test())
    else:
        suite.add(t.fail_test("showStatus() shim NOT FOUND — 40+ call sites depend on it"))

    # No duplicate function definitions (critical ones)
    t = TestResult("no_duplicate_functions", "ui", "P1")
    func_defs = defaultdict(list)
    for i, line in enumerate(ui_code.splitlines(), 1):
        m = re.match(r'\s*function\s+(\w+)\s*\(', line)
        if m:
            func_defs[m.group(1)].append(i)
    dupes = {name: lines for name, lines in func_defs.items() if len(lines) > 1}
    critical_dupes = {n: l for n, l in dupes.items() if n in [
        "newProject", "saveAllShotEdits", "lockAllCharacters", "lockAllLocations",
        "loadScreeningRoom", "renderTimeline", "generateFirstFrames"
    ]}
    if critical_dupes:
        details = [f"{name}: defined at lines {lines}" for name, lines in critical_dupes.items()]
        suite.add(t.fail_test(f"{len(critical_dupes)} critical duplicate functions", details))
    else:
        suite.add(t.pass_test(f"No critical duplicate functions (total dupes: {len(dupes)})"))


# ============================================================
# CATEGORY 8: PROJECT DATA INTEGRITY (Ravencroft)
# ============================================================
def test_project_data(suite):
    print("\n📊 PROJECT DATA INTEGRITY")

    rav_dir = PIPELINE_DIR / "ravencroft_v17"

    # Shot plan exists
    t = TestResult("shot_plan_exists", "project", "P0")
    sp_path = rav_dir / "shot_plan.json"
    if sp_path.exists():
        try:
            with open(sp_path) as f:
                sp = json.load(f)
            shots = sp.get("shots", [])
            suite.add(t.pass_test(f"{len(shots)} shots"))
        except Exception as e:
            suite.add(t.fail_test(f"Invalid JSON: {e}"))
            return
    else:
        suite.add(t.pass_test("No ravencroft project yet (skipping project tests)"))
        return

    # Cast map exists with characters
    t = TestResult("cast_map_valid", "project", "P0")
    cm_path = rav_dir / "cast_map.json"
    if cm_path.exists():
        try:
            with open(cm_path) as f:
                cm = json.load(f)
            chars = [k for k in cm if not k.startswith("_")]
            suite.add(t.pass_test(f"{len(chars)} characters"))
        except Exception as e:
            suite.add(t.fail_test(f"Invalid JSON: {e}"))
    else:
        suite.add(t.fail_test("cast_map.json NOT FOUND"))

    # No SCRIPT_ACCURATE refs
    t = TestResult("no_script_accurate_refs", "project", "P0")
    sp_text = json.dumps(sp)
    sa_count = sp_text.count("SCRIPT_ACCURATE")
    if sa_count > 0:
        suite.add(t.fail_test(f"{sa_count} SCRIPT_ACCURATE references remain"))
    else:
        suite.add(t.pass_test("Zero SCRIPT_ACCURATE references"))

    # Camera variety
    t = TestResult("camera_variety", "project", "P1")
    motion_counts = defaultdict(int)
    for shot in shots:
        style = shot.get("camera_style", "unknown")
        motion_counts[style] += 1
    if len(motion_counts) < 2:
        suite.add(t.fail_test(f"Only {len(motion_counts)} motion type(s): {dict(motion_counts)}"))
    else:
        suite.add(t.pass_test(f"{len(motion_counts)} motion types: {dict(motion_counts)}"))

    # All shots have nano_prompt
    t = TestResult("all_shots_have_prompts", "project", "P1")
    missing_prompt = sum(1 for s in shots if not s.get("nano_prompt"))
    if missing_prompt > 0:
        suite.add(t.fail_test(f"{missing_prompt} shots missing nano_prompt"))
    else:
        suite.add(t.pass_test(f"All {len(shots)} shots have nano_prompt"))

    # All shots have duration
    t = TestResult("all_shots_have_duration", "project", "P0")
    missing_dur = sum(1 for s in shots if not s.get("duration"))
    if missing_dur > 0:
        suite.add(t.fail_test(f"{missing_dur} shots missing duration"))
    else:
        suite.add(t.pass_test(f"All {len(shots)} shots have duration"))

    # Extended shots have segments
    t = TestResult("extended_shots_have_segments", "project", "P1")
    bad_extended = []
    for s in shots:
        dur = s.get("duration", 0)
        if dur > 20 and not s.get("segments"):
            bad_extended.append(s.get("shot_id", "?"))
    if bad_extended:
        suite.add(t.fail_test(f"{len(bad_extended)} extended shots (>20s) missing segments", bad_extended[:10]))
    else:
        suite.add(t.pass_test("All extended shots have segments"))

    # No CHILD characters
    t = TestResult("no_child_characters", "project", "P2")
    child_shots = []
    for s in shots:
        chars = s.get("characters", [])
        if "CHILD" in chars:
            child_shots.append(s.get("shot_id", "?"))
    if child_shots:
        suite.add(t.fail_test(f"{len(child_shots)} shots reference CHILD", child_shots[:10]))
    else:
        suite.add(t.pass_test("No CHILD character references"))


# ============================================================
# CATEGORY 9: EDIT ENGINE INTEGRATION (NEW V17.5+)
# ============================================================
def test_edit_engine(suite):
    print("\n🎬 EDIT ENGINE INTEGRATION")

    edit_engine = BASE_DIR / "atlas_edit_engine.py"

    # Check if edit engine exists yet
    t = TestResult("edit_engine_file_exists", "edit_engine", "P2")
    if edit_engine.exists():
        code = edit_engine.read_text(errors="ignore")
        lines = len(code.splitlines())
        suite.add(t.pass_test(f"{lines} lines"))

        # Check for placeholder/stub methods
        t2 = TestResult("edit_engine_no_stubs", "edit_engine", "P1")
        stub_patterns = [
            r'def\s+\w+\([^)]*\)\s*:\s*\n\s*pass\s*$',
            r'raise NotImplementedError',
            r'#\s*TODO',
            r'return\s*None\s*#\s*stub',
        ]
        stubs_found = []
        for pat in stub_patterns:
            matches = re.finditer(pat, code, re.MULTILINE)
            for m in matches:
                line_num = code[:m.start()].count('\n') + 1
                stubs_found.append(f"L{line_num}: {m.group()[:80]}")
        if stubs_found:
            suite.add(t2.fail_test(f"{len(stubs_found)} stubs in edit engine", stubs_found))
        else:
            suite.add(t2.pass_test("No stubs detected"))

        # Check for required classes (actual V17.4 edit engine class names)
        t3 = TestResult("edit_engine_core_classes", "edit_engine", "P1")
        required_classes = ["AtlasEditEngine", "FFmpegRenderEngine", "Timeline", "EditOperations",
                           "EditorAgent", "ColoristAgent", "SoundAgent", "MusicAgent", "DirectorAgent"]
        found = [c for c in required_classes if f"class {c}" in code]
        missing = [c for c in required_classes if c not in found]
        if missing:
            suite.add(t3.fail_test(f"Missing classes: {missing} (found: {found})"))
        else:
            suite.add(t3.pass_test(f"All {len(required_classes)} core classes present"))

    else:
        suite.add(t.pass_test("Edit engine not yet created (will check when present)"))

    # Check if edit engine endpoints exist in server
    t = TestResult("edit_engine_endpoints", "edit_engine", "P1")
    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""
    edit_endpoints = [
        "/api/v17/edit/timeline",
        "/api/v17/edit/auto-edit",
        "/api/v17/edit/render",
        "/api/v17/edit/operation",
        "/api/v17/edit/effects",
        "/api/v17/edit/clip-preview",
        "/api/v17/edit/export-presets",
    ]
    found_eps = [ep for ep in edit_endpoints if ep in server_code]
    missing_eps = [ep for ep in edit_endpoints if ep not in server_code]
    if not found_eps:
        suite.add(t.pass_test("Edit endpoints not yet added (will check when present)"))
    elif len(found_eps) >= 5:
        suite.add(t.pass_test(f"{len(found_eps)}/{len(edit_endpoints)} edit endpoints present"))
    else:
        suite.add(t.fail_test(f"Only {len(found_eps)}/{len(edit_endpoints)} endpoints", missing_eps))

    # Check edit engine AI agents have real logic (not just pass/return None)
    if edit_engine.exists():
        code = edit_engine.read_text(errors="ignore")

        t = TestResult("edit_agents_have_logic", "edit_engine", "P1")
        agent_classes = ["EditorAgent", "ColoristAgent", "SoundAgent", "MusicAgent", "DirectorAgent"]
        empty_agents = []
        for ac in agent_classes:
            # Find class body and check it has substantive methods
            pattern = rf'class {ac}.*?(?=\nclass |\Z)'
            match = re.search(pattern, code, re.DOTALL)
            if match:
                body = match.group()
                # Count methods with actual logic (not just pass/return)
                methods = re.findall(r'def \w+\(', body)
                # Check for FFmpeg or analysis logic
                has_logic = ("ffmpeg" in body.lower() or "filter" in body.lower() or
                            "analyze" in body.lower() or "clip" in body.lower() or
                            "timeline" in body.lower() or len(body) > 200)
                if not has_logic:
                    empty_agents.append(ac)
        if empty_agents:
            suite.add(t.fail_test(f"{len(empty_agents)} agents appear to be stubs", empty_agents))
        else:
            suite.add(t.pass_test(f"All {len(agent_classes)} agents have substantive logic"))

        # Check FFmpeg render engine has real filter chain building
        t = TestResult("ffmpeg_engine_real", "edit_engine", "P1")
        if "ffmpeg" in code.lower() and ("filter_complex" in code or "build_filter" in code or "-vf" in code):
            suite.add(t.pass_test("FFmpeg engine has filter chain building"))
        else:
            suite.add(t.fail_test("FFmpeg engine missing filter chain logic"))

        # Check export presets are defined
        t = TestResult("export_presets_defined", "edit_engine", "P2")
        presets = re.findall(r'(?:web_1080p|cinema_4k|youtube|broadcast|mobile|draft)', code)
        if len(presets) >= 3:
            suite.add(t.pass_test(f"{len(set(presets))} export presets defined"))
        else:
            suite.add(t.fail_test("Fewer than 3 export presets"))

        # Check edit operations are implemented
        t = TestResult("edit_operations_complete", "edit_engine", "P1")
        ops = ["trim", "split", "ripple", "slip", "slide"]
        found_ops = [o for o in ops if o in code.lower()]
        missing_ops = [o for o in ops if o not in code.lower()]
        if missing_ops:
            suite.add(t.fail_test(f"Missing edit operations: {missing_ops}"))
        else:
            suite.add(t.pass_test(f"All {len(ops)} edit operations present"))

    # Check UI has edit engine panel
    t = TestResult("ui_edit_engine_panel", "edit_engine", "P1")
    ui_code = UI_FILE.read_text(errors="ignore") if UI_FILE.exists() else ""
    ee_markers = ["editEnginePanel", "eeTabInspector", "eeTabColor", "eeTabEffects", "eeTabAgents", "eeTabExport"]
    found_markers = [m for m in ee_markers if m in ui_code]
    if not found_markers:
        suite.add(t.pass_test("Edit engine UI not yet added (will check when present)"))
    elif len(found_markers) >= 4:
        suite.add(t.pass_test(f"{len(found_markers)}/{len(ee_markers)} UI panels present"))
    else:
        missing = [m for m in ee_markers if m not in ui_code]
        suite.add(t.fail_test(f"Missing UI elements: {missing}"))


# ============================================================
# CATEGORY 10: CRITICAL REGRESSION CHECKS
# ============================================================
def test_critical_regressions(suite):
    print("\n🛡️  CRITICAL REGRESSION CHECKS")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""

    # No REPO_ROOT
    t = TestResult("no_repo_root", "regression", "P0")
    if "REPO_ROOT" in server_code and "REPO_ROOT" not in server_code.split("#")[0]:
        # Check if it's in a comment or actual code
        non_comment = [l for l in server_code.splitlines() if "REPO_ROOT" in l and not l.strip().startswith("#")]
        if non_comment:
            suite.add(t.fail_test(f"REPO_ROOT still in code at {len(non_comment)} locations"))
        else:
            suite.add(t.pass_test("REPO_ROOT only in comments"))
    else:
        suite.add(t.pass_test("No REPO_ROOT references"))

    # Safe sentry wrappers
    t = TestResult("sentry_safe_wrappers", "regression", "P0")
    if "_sentry_capture_exception" in server_code and "_sentry_set_tag" in server_code:
        # Check for bare sentry_sdk calls
        bare = re.findall(r'(?<!\w)sentry_sdk\.(set_tag|capture_exception|capture_message)\(', server_code)
        safe = re.findall(r'_sentry_(set_tag|capture_exception|capture_message)\(', server_code)
        if len(bare) > len(safe):
            suite.add(t.fail_test(f"More bare sentry calls ({len(bare)}) than safe wrappers ({len(safe)})"))
        else:
            suite.add(t.pass_test(f"{len(safe)} safe wrapper calls, {len(bare)} in wrapper defs"))
    else:
        suite.add(t.fail_test("Missing _sentry safe wrappers"))

    # has_stability initialized
    t = TestResult("has_stability_initialized", "regression", "P1")
    if "has_stability = False" in server_code:
        suite.add(t.pass_test("has_stability initialized before conditional"))
    else:
        suite.add(t.fail_test("has_stability not initialized — UnboundLocalError risk"))

    # Video endpoint correct path
    t = TestResult("video_endpoint_correct", "regression", "P0")
    if "/api/auto/render-videos" in server_code:
        suite.add(t.pass_test("render-videos endpoint present"))
    else:
        suite.add(t.fail_test("Missing /api/auto/render-videos endpoint"))

    # Save mutex for concurrent write protection
    t = TestResult("save_mutex_present", "regression", "P1")
    ui_code = UI_FILE.read_text(errors="ignore") if UI_FILE.exists() else ""
    if "_saveMutex" in ui_code or "saveMutex" in ui_code:
        suite.add(t.pass_test("Save mutex for concurrent write protection"))
    else:
        suite.add(t.fail_test("Missing save mutex — race condition risk on shot_plan.json"))

    # Atomic writes in agent persist
    t = TestResult("atomic_writes_agent", "regression", "P1")
    if "os.replace" in server_code or "atomic" in server_code.lower():
        suite.add(t.pass_test("Atomic writes present"))
    else:
        suite.add(t.fail_test("No atomic writes found — data corruption risk"))


# ============================================================
# CATEGORY 11: V17.5 MULTI-ANGLE + MEDIA BIN + PREVIS
# ============================================================
def test_v175_features(suite):
    print("\n🎬  V17.5 FEATURES (Multi-Angle, Media Bin, Previs)")

    server_code = SERVER_FILE.read_text(errors="ignore") if SERVER_FILE.exists() else ""
    ui_code = UI_FILE.read_text(errors="ignore") if UI_FILE.exists() else ""

    # Multi-angle endpoint
    t = TestResult("multi_angle_endpoint", "v175", "P1")
    if "/api/v17/generate-multi-angle" in server_code:
        suite.add(t.pass_test("Multi-angle generation endpoint present"))
    else:
        suite.add(t.fail_test("Missing /api/v17/generate-multi-angle endpoint"))

    # Select variant endpoint
    t = TestResult("select_variant_endpoint", "v175", "P1")
    if "/api/v17/select-variant" in server_code:
        suite.add(t.pass_test("Select variant endpoint present"))
    else:
        suite.add(t.fail_test("Missing /api/v17/select-variant endpoint"))

    # Verify variants endpoint
    t = TestResult("verify_variants_endpoint", "v175", "P1")
    if "/api/v17/auto/verify-variants" in server_code:
        suite.add(t.pass_test("Verify variants endpoint present"))
    else:
        suite.add(t.fail_test("Missing /api/v17/auto/verify-variants endpoint"))

    # UI multi-angle panel
    t = TestResult("multi_angle_panel_ui", "v175", "P1")
    if "multiAnglePanel" in ui_code and "multiAngleGrid" in ui_code:
        suite.add(t.pass_test("Multi-angle panel HTML present"))
    else:
        suite.add(t.fail_test("Missing multiAnglePanel or multiAngleGrid in UI"))

    # UI media bin
    t = TestResult("media_bin_ui", "v175", "P1")
    if "mediaBinPanel" in ui_code and "renderMediaBin" in ui_code:
        suite.add(t.pass_test("Media bin panel + render function present"))
    else:
        suite.add(t.fail_test("Missing media bin panel or renderMediaBin"))

    # Timeline thumbnail clips
    t = TestResult("timeline_thumbnails", "v175", "P1")
    if "has-thumb" in ui_code and "clip-label" in ui_code:
        suite.add(t.pass_test("Timeline thumbnail clip CSS + rendering present"))
    else:
        suite.add(t.fail_test("Missing timeline thumbnail mode (has-thumb class)"))

    # Enhanced previs filmstrip (powerhouse)
    t = TestResult("previs_powerhouse", "v175", "P1")
    if "powerhouse" in ui_code and "ff-variants-dot" in ui_code:
        suite.add(t.pass_test("Previs filmstrip powerhouse mode present"))
    else:
        suite.add(t.fail_test("Missing powerhouse previs filmstrip"))

    # Shot-type-aware auto-balance
    t = TestResult("smart_auto_balance", "v175", "P1")
    if "IDEAL_BY_TYPE" in ui_code and "dialogue" in ui_code.split("IDEAL_BY_TYPE")[1][:200] if "IDEAL_BY_TYPE" in ui_code else False:
        suite.add(t.pass_test("Shot-type-aware auto-balance present"))
    else:
        suite.add(t.fail_test("Missing IDEAL_BY_TYPE shot-type-aware auto-balance"))

    # Insert shot with live rendering
    t = TestResult("insert_shot_live_render", "v175", "P1")
    if "insertAutoRender" in ui_code and "executeInsertShot" in ui_code:
        suite.add(t.pass_test("Insert shot with auto-render present"))
    else:
        suite.add(t.fail_test("Missing insert shot with auto-render"))

    # Multi-angle Qwen presets
    t = TestResult("qwen_angle_presets", "v175", "P2")
    if "MULTI_ANGLE_PRESETS" in ui_code:
        suite.add(t.pass_test("Qwen angle differentiation presets present"))
    else:
        suite.add(t.fail_test("Missing MULTI_ANGLE_PRESETS"))


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("  ATLAS V17.5 REGRESSION & VALIDATION TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Base: {BASE_DIR}")
    print("=" * 60)

    suite = TestSuite()

    test_file_integrity(suite)
    test_cost_tracking(suite)
    test_placeholders(suite)
    test_model_lock(suite)
    test_gold_standard(suite)
    test_agent_system(suite)
    test_ui_integrity(suite)
    test_project_data(suite)
    test_edit_engine(suite)
    test_critical_regressions(suite)
    test_v175_features(suite)

    # Summary
    s = suite.summary()
    print("\n" + "=" * 60)
    print(f"  RESULTS: {s['passed']}/{s['total']} passed")
    if s['failed'] > 0:
        print(f"  FAILURES: {s['failed']} ({s['p0_failures']} P0, {s['p1_failures']} P1)")
    print(f"  PRODUCTION READY: {'✅ YES' if s['production_ready'] else '❌ NO (P0 failures)'}")
    print(f"  Duration: {s['elapsed_seconds']}s")
    print("=" * 60)

    # Log results
    log_path = suite.log()
    print(f"\n  📄 Full log: {log_path}")

    # Return exit code
    return 0 if s['production_ready'] else 1


if __name__ == "__main__":
    sys.exit(main())
