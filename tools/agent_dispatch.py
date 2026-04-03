"""
ATLAS Agent Dispatch — V1.0
Tiered Agent Stack: Director (Gemma 12B) → Builder (DeepSeek R1) → QA (Gemma 4B)

Single entry point: POST /atlas/dispatch
Mobile-ready, persistent, autonomous.

Architecture:
  - Executive Tier: Claude/external API (analysis only, no code generation)
  - Director Tier: Gemma 12B — intent parsing, scene contracts, cinematic direction
  - Builder Tier: DeepSeek R1 7B — code generation, prompt compilation, implementation
  - QA Tier: Gemma 4B — fast validation, gate checks, regression detection

Sequential Protocol:
  1. DISPATCH receives intent (natural language or structured)
  2. DIRECTOR interprets intent → produces structured task spec
  3. BUILDER executes task spec → produces code/prompts/config changes
  4. QA validates output against doctrine gates
  5. If QA passes → apply changes. If QA fails → loop back to BUILDER with feedback (max 2 retries)
"""

import json
import time
import hashlib
import os
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# ── CONFIGURATION ──────────────────────────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

AGENT_MODELS = {
    "director": os.environ.get("ATLAS_DIRECTOR_MODEL", "gemma4:e4b"),
    "builder":  os.environ.get("ATLAS_BUILDER_MODEL", "deepseek-r1:7b"),
    "qa":       os.environ.get("ATLAS_QA_MODEL", "gemma4:e4b"),
}

MAX_BUILDER_RETRIES = 2
DISPATCH_LOG_DIR = Path("dispatch_logs")
DISPATCH_LOG_DIR.mkdir(exist_ok=True)


# ── DATA STRUCTURES ────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    DIRECTOR_PHASE = "director_phase"
    BUILDER_PHASE = "builder_phase"
    QA_PHASE = "qa_phase"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    SCENE_REFINE = "scene_refine"           # Refine a scene's prompts/shots
    CODE_FIX = "code_fix"                   # Fix a bug or implement a feature
    PIPELINE_RUN = "pipeline_run"           # Run generation pipeline
    PROMPT_COMPILE = "prompt_compile"       # Compile/enhance prompts
    DOCTRINE_CHECK = "doctrine_check"       # Run doctrine validation
    CUSTOM = "custom"                       # Freeform task


@dataclass
class AgentMessage:
    role: str           # director, builder, qa, system
    content: str
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


@dataclass
class DispatchTask:
    task_id: str
    intent: str                             # Natural language from user
    task_type: TaskType = TaskType.CUSTOM
    status: TaskStatus = TaskStatus.PENDING
    project: str = ""
    scene_id: str = ""

    # Agent outputs
    director_spec: Dict = field(default_factory=dict)
    builder_output: Dict = field(default_factory=dict)
    qa_verdict: Dict = field(default_factory=dict)

    # Execution log
    messages: List[AgentMessage] = field(default_factory=list)
    retries: int = 0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # Results
    changes_applied: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ── OLLAMA CLIENT ──────────────────────────────────────────────

def _ollama_generate(model: str, prompt: str, system: str = "", temperature: float = 0.3) -> Dict:
    """Call Ollama API, return response dict with content + metadata."""
    t0 = time.time()
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 4096}
        }
        if system:
            payload["system"] = system

        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "content": data.get("response", ""),
            "model": model,
            "tokens_used": data.get("eval_count", 0),
            "duration_ms": int((time.time() - t0) * 1000),
            "success": True
        }
    except Exception as e:
        return {
            "content": f"ERROR: {str(e)}",
            "model": model,
            "tokens_used": 0,
            "duration_ms": int((time.time() - t0) * 1000),
            "success": False
        }


# ── DIRECTOR AGENT ─────────────────────────────────────────────

DIRECTOR_SYSTEM = """You are the ATLAS Director Agent — a cinematic AI director.
Your job: interpret the user's intent and produce a STRUCTURED TASK SPECIFICATION.

You understand film grammar: shot types, OTS coverage, 180° rule, emotional arcs,
beat structure (Save the Cat 21-point), identity continuity, room DNA.

OUTPUT FORMAT (always respond with valid JSON):
{
    "task_type": "scene_refine|code_fix|pipeline_run|prompt_compile|doctrine_check|custom",
    "objective": "One sentence: what must be achieved",
    "constraints": ["List of hard constraints from doctrine"],
    "steps": [
        {"step": 1, "action": "description", "target": "file or component"},
        {"step": 2, "action": "description", "target": "file or component"}
    ],
    "validation_criteria": ["How QA should verify success"],
    "risk_assessment": "low|medium|high",
    "estimated_complexity": "trivial|moderate|complex"
}

Be precise. Be cinematic. Think like a director, not a programmer."""


def run_director(task: DispatchTask) -> Dict:
    """Director interprets intent → structured task spec."""

    context = f"Project: {task.project or 'unknown'}\n"
    if task.scene_id:
        context += f"Scene: {task.scene_id}\n"

    prompt = f"""{context}
User Intent: {task.intent}

Analyze this intent and produce a structured task specification.
Consider ATLAS doctrine: identity continuity, room DNA, 180° rule, beat enrichment.
Output ONLY valid JSON."""

    result = _ollama_generate(
        model=AGENT_MODELS["director"],
        prompt=prompt,
        system=DIRECTOR_SYSTEM,
        temperature=0.2
    )

    task.messages.append(AgentMessage(
        role="director",
        content=result["content"],
        model=result["model"],
        tokens_used=result["tokens_used"],
        duration_ms=result["duration_ms"]
    ))

    # Parse JSON from response
    try:
        # Try to extract JSON from response
        content = result["content"]
        # Find JSON block
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            spec = json.loads(content[json_start:json_end])
            task.director_spec = spec
            task.task_type = TaskType(spec.get("task_type", "custom"))
            return {"success": True, "spec": spec}
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: treat raw text as spec
    task.director_spec = {
        "task_type": "custom",
        "objective": task.intent,
        "steps": [{"step": 1, "action": result["content"][:500], "target": "manual"}],
        "validation_criteria": ["Manual review required"],
        "risk_assessment": "medium",
        "estimated_complexity": "moderate"
    }
    return {"success": True, "spec": task.director_spec}


# ── BUILDER AGENT ──────────────────────────────────────────────

BUILDER_SYSTEM = """You are the ATLAS Builder Agent — a precision code and prompt engineer.
You receive a structured task specification from the Director and EXECUTE it.

Rules:
1. Output ONLY the requested changes — no commentary unless asked
2. For code changes: output the exact file path and the code to write
3. For prompt changes: output the exact shot_id and the new prompt text
4. For config changes: output the exact JSON path and new value
5. NEVER modify files outside the task scope
6. NEVER introduce new dependencies without noting them
7. Follow ATLAS doctrine: no hardcoded secrets, no identity drift, no room teleportation

OUTPUT FORMAT (always respond with valid JSON):
{
    "changes": [
        {
            "type": "code|prompt|config|command",
            "target": "file path or shot_id",
            "action": "create|modify|delete|execute",
            "content": "the actual change content",
            "reason": "why this change"
        }
    ],
    "notes": "Any important context for QA"
}"""


def run_builder(task: DispatchTask, qa_feedback: str = "") -> Dict:
    """Builder executes the Director's spec."""

    spec_str = json.dumps(task.director_spec, indent=2)

    prompt = f"""TASK SPECIFICATION FROM DIRECTOR:
{spec_str}

Project: {task.project or 'unknown'}
Scene: {task.scene_id or 'n/a'}
"""
    if qa_feedback:
        prompt += f"\nQA FEEDBACK (fix these issues):\n{qa_feedback}\n"

    prompt += "\nExecute this specification. Output ONLY valid JSON with your changes."

    result = _ollama_generate(
        model=AGENT_MODELS["builder"],
        prompt=prompt,
        system=BUILDER_SYSTEM,
        temperature=0.1  # Low temp for precise code gen
    )

    task.messages.append(AgentMessage(
        role="builder",
        content=result["content"],
        model=result["model"],
        tokens_used=result["tokens_used"],
        duration_ms=result["duration_ms"]
    ))

    # Parse builder output
    try:
        content = result["content"]
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            output = json.loads(content[json_start:json_end])
            task.builder_output = output
            return {"success": True, "output": output}
    except (json.JSONDecodeError, ValueError):
        pass

    task.builder_output = {
        "changes": [],
        "notes": f"Raw output (parse failed): {result['content'][:500]}"
    }
    return {"success": True, "output": task.builder_output}


# ── QA AGENT ───────────────────────────────────────────────────

QA_SYSTEM = """You are the ATLAS QA Agent — a strict quality gate.
You validate Builder output against the Director's specification and ATLAS doctrine.

Check for:
1. Does the output match the Director's objective?
2. Are all steps from the spec addressed?
3. Any doctrine violations? (identity drift, room teleportation, secret leaks, model lock violations)
4. Are validation criteria from the spec satisfied?
5. Any regressions? (breaking existing functionality)

OUTPUT FORMAT (always respond with valid JSON):
{
    "verdict": "PASS|FAIL|WARN",
    "score": 0.0 to 1.0,
    "issues": [
        {"severity": "blocking|warning|info", "description": "what's wrong", "fix_hint": "how to fix"}
    ],
    "approved_changes": [0, 1, 2],
    "rejected_changes": [],
    "summary": "One sentence verdict"
}

Be strict. Better to catch a bug now than in production."""


def run_qa(task: DispatchTask) -> Dict:
    """QA validates Builder output against Director spec."""

    prompt = f"""DIRECTOR SPECIFICATION:
{json.dumps(task.director_spec, indent=2)}

BUILDER OUTPUT:
{json.dumps(task.builder_output, indent=2)}

Validate the Builder's output against the Director's specification.
Check for doctrine compliance, completeness, and regressions.
Output ONLY valid JSON."""

    result = _ollama_generate(
        model=AGENT_MODELS["qa"],
        prompt=prompt,
        system=QA_SYSTEM,
        temperature=0.1
    )

    task.messages.append(AgentMessage(
        role="qa",
        content=result["content"],
        model=result["model"],
        tokens_used=result["tokens_used"],
        duration_ms=result["duration_ms"]
    ))

    # Parse QA verdict
    try:
        content = result["content"]
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            verdict = json.loads(content[json_start:json_end])
            task.qa_verdict = verdict
            return {"success": True, "verdict": verdict}
    except (json.JSONDecodeError, ValueError):
        pass

    # Default: WARN if we can't parse
    task.qa_verdict = {
        "verdict": "WARN",
        "score": 0.5,
        "issues": [{"severity": "warning", "description": "QA output unparseable", "fix_hint": "Manual review"}],
        "summary": "QA output could not be parsed — manual review required"
    }
    return {"success": True, "verdict": task.qa_verdict}


# ── DISPATCH ORCHESTRATOR ──────────────────────────────────────

def dispatch(intent: str, project: str = "", scene_id: str = "") -> DispatchTask:
    """
    Main entry point. Runs the full Director → Builder → QA pipeline.

    Usage:
        task = dispatch("Refine scene 001 mood to be more ominous", project="victorian_shadows_ep1", scene_id="001")
        print(task.status, task.qa_verdict)
    """

    # Create task
    task_id = hashlib.sha256(f"{intent}{time.time()}".encode()).hexdigest()[:12]
    task = DispatchTask(
        task_id=task_id,
        intent=intent,
        project=project,
        scene_id=scene_id
    )

    print(f"\n{'='*60}")
    print(f"[DISPATCH] Task {task_id}: {intent[:80]}")
    print(f"{'='*60}")

    # Phase 1: Director
    task.status = TaskStatus.DIRECTOR_PHASE
    print(f"\n[DIRECTOR] Analyzing intent with {AGENT_MODELS['director']}...")
    dir_result = run_director(task)
    if not dir_result["success"]:
        task.status = TaskStatus.FAILED
        task.error = "Director phase failed"
        _save_task_log(task)
        return task

    print(f"[DIRECTOR] Spec: {task.director_spec.get('objective', 'n/a')}")
    print(f"[DIRECTOR] Steps: {len(task.director_spec.get('steps', []))}")
    print(f"[DIRECTOR] Risk: {task.director_spec.get('risk_assessment', 'unknown')}")

    # Phase 2: Builder (with retry loop)
    qa_feedback = ""
    for attempt in range(1 + MAX_BUILDER_RETRIES):
        task.status = TaskStatus.BUILDER_PHASE
        print(f"\n[BUILDER] Executing spec with {AGENT_MODELS['builder']} (attempt {attempt + 1})...")
        build_result = run_builder(task, qa_feedback=qa_feedback)

        changes = task.builder_output.get("changes", [])
        print(f"[BUILDER] Changes: {len(changes)}")

        # Phase 3: QA
        task.status = TaskStatus.QA_PHASE
        print(f"\n[QA] Validating with {AGENT_MODELS['qa']}...")
        qa_result = run_qa(task)

        verdict = task.qa_verdict.get("verdict", "WARN")
        score = task.qa_verdict.get("score", 0)
        print(f"[QA] Verdict: {verdict} (score: {score})")

        if verdict == "PASS" or verdict == "WARN":
            # Accept with warnings
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()

            issues = task.qa_verdict.get("issues", [])
            blocking = [i for i in issues if i.get("severity") == "blocking"]

            if not blocking:
                print(f"\n[DISPATCH] ✅ Task COMPLETED — {verdict}")
                if issues:
                    print(f"[DISPATCH] ⚠️  {len(issues)} warning(s) — review recommended")
                break
            else:
                # Has blocking issues despite PASS/WARN verdict — retry
                qa_feedback = json.dumps(blocking)
                task.retries += 1
                print(f"[DISPATCH] Blocking issues found — retrying ({task.retries}/{MAX_BUILDER_RETRIES})")
                continue

        elif verdict == "FAIL":
            issues = task.qa_verdict.get("issues", [])
            qa_feedback = json.dumps(issues)
            task.retries += 1

            if attempt < MAX_BUILDER_RETRIES:
                print(f"[DISPATCH] ❌ QA FAIL — retrying with feedback ({task.retries}/{MAX_BUILDER_RETRIES})")
            else:
                task.status = TaskStatus.FAILED
                task.error = f"QA failed after {MAX_BUILDER_RETRIES} retries: {task.qa_verdict.get('summary', 'unknown')}"
                print(f"\n[DISPATCH] ❌ Task FAILED after {MAX_BUILDER_RETRIES} retries")

    _save_task_log(task)
    return task


def _save_task_log(task: DispatchTask):
    """Save task execution log to disk."""
    log_path = DISPATCH_LOG_DIR / f"{task.task_id}.json"
    log_data = {
        "task_id": task.task_id,
        "intent": task.intent,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "project": task.project,
        "scene_id": task.scene_id,
        "director_spec": task.director_spec,
        "builder_output": task.builder_output,
        "qa_verdict": task.qa_verdict,
        "retries": task.retries,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
        "error": task.error,
        "messages": [
            {
                "role": m.role,
                "content": m.content[:2000],  # Truncate for storage
                "model": m.model,
                "tokens_used": m.tokens_used,
                "duration_ms": m.duration_ms,
                "timestamp": m.timestamp
            }
            for m in task.messages
        ],
        "total_tokens": sum(m.tokens_used for m in task.messages),
        "total_duration_ms": sum(m.duration_ms for m in task.messages)
    }
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)


# ── FASTAPI ENDPOINTS (wire into orchestrator_server.py) ───────

def register_dispatch_routes(app):
    """Register dispatch API routes on the FastAPI app."""
    from fastapi import Body

    @app.post("/atlas/dispatch")
    async def api_dispatch(request: Dict = Body(...)):
        """Single entry point for all agent-dispatched tasks."""
        intent = request.get("intent", "")
        project = request.get("project", "")
        scene_id = request.get("scene_id", "")

        if not intent:
            return {"success": False, "error": "intent is required"}

        task = dispatch(intent, project=project, scene_id=scene_id)

        return {
            "success": task.status == TaskStatus.COMPLETED,
            "task_id": task.task_id,
            "status": task.status.value,
            "director_spec": task.director_spec,
            "builder_output": task.builder_output,
            "qa_verdict": task.qa_verdict,
            "retries": task.retries,
            "error": task.error,
            "total_tokens": sum(m.tokens_used for m in task.messages),
            "total_duration_ms": sum(m.duration_ms for m in task.messages)
        }

    @app.get("/atlas/dispatch/status/{task_id}")
    async def api_dispatch_status(task_id: str):
        """Get status of a dispatch task."""
        log_path = DISPATCH_LOG_DIR / f"{task_id}.json"
        if log_path.exists():
            with open(log_path) as f:
                return json.load(f)
        return {"success": False, "error": "Task not found"}

    @app.get("/atlas/dispatch/history")
    async def api_dispatch_history():
        """List recent dispatch tasks."""
        logs = sorted(DISPATCH_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        tasks = []
        for log_path in logs:
            with open(log_path) as f:
                data = json.load(f)
                tasks.append({
                    "task_id": data["task_id"],
                    "intent": data["intent"][:100],
                    "status": data["status"],
                    "task_type": data["task_type"],
                    "created_at": data["created_at"],
                    "total_tokens": data.get("total_tokens", 0),
                    "total_duration_ms": data.get("total_duration_ms", 0)
                })
        return {"tasks": tasks}

    @app.get("/atlas/agents/status")
    async def api_agents_status():
        """Check health of all agent models."""
        status = {}
        for role, model in AGENT_MODELS.items():
            try:
                r = requests.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={"model": model, "prompt": "OK", "stream": False,
                          "options": {"num_predict": 1}},
                    timeout=30
                )
                status[role] = {
                    "model": model,
                    "status": "online" if r.status_code == 200 else "error",
                    "response_ms": int(r.elapsed.total_seconds() * 1000)
                }
            except Exception as e:
                status[role] = {
                    "model": model,
                    "status": "offline",
                    "error": str(e)
                }
        return {"agents": status, "ollama_base": OLLAMA_BASE}

    print("[DISPATCH] Agent dispatch routes registered: /atlas/dispatch, /atlas/agents/status")


# ── CLI ENTRY POINT ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 tools/agent_dispatch.py 'your intent here' [project] [scene_id]")
        sys.exit(1)

    intent = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else ""
    scene_id = sys.argv[3] if len(sys.argv) > 3 else ""

    task = dispatch(intent, project=project, scene_id=scene_id)

    print(f"\n{'='*60}")
    print(f"RESULT: {task.status.value}")
    print(f"Director spec: {json.dumps(task.director_spec, indent=2)[:500]}")
    print(f"Builder output: {json.dumps(task.builder_output, indent=2)[:500]}")
    print(f"QA verdict: {json.dumps(task.qa_verdict, indent=2)[:500]}")
    print(f"Total tokens: {sum(m.tokens_used for m in task.messages)}")
    print(f"Total time: {sum(m.duration_ms for m in task.messages)}ms")
