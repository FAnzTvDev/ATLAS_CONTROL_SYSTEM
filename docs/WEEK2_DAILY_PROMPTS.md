# WEEK 2 - DAILY MASTER PROMPTS

**Purpose:** Hardening, determinism, regression safety, factory load testing.
**Rule:** Do NOT advance a phase until all validation passes.

---

## DAY 1 - Deterministic Replay + Execution Ledger

### MASTER PROMPT

> **ACT AS:** Principal Systems Engineer
>
> **MISSION:** Implement deterministic replay and a full execution ledger so that any project run can be replayed exactly and verified bit-for-bit.
>
> **DO NOT MODIFY:** ingestion, UI behavior, semantic invariants.
>
> **DO NOT PROCEED** unless replay is verifiably deterministic.

### TASKS

#### 1. Execution Ledger

Create: `pipeline_outputs/<project>/execution_ledger.json`

Each agent run must append:
```json
{
  "timestamp": "...",
  "agent": "cast_propagation",
  "execution_mode": "VERIFY",
  "input_hash": "sha256",
  "output_hash": "sha256",
  "duration_ms": 1283
}
```

Hash:
- input = serialized input file state
- output = serialized result state

#### 2. Deterministic Replay

Create: `python tools/replay_project.py <project> --run-id <timestamp>`

Replay must:
- Re-run agents in same order
- Produce identical output hashes
- Produce identical critic verdict

### REQUIRED VALIDATION

```bash
python tools/replay_project.py kord_v17
```

If output hashes differ → FAIL.

### STOP CONDITION

Replay produces identical ledger and identical critic verdict.

---

## DAY 2 - Regression Matrix + Cross-Project Isolation

### MASTER PROMPT

> **ACT AS:** Infrastructure Architect
>
> **MISSION:** Prevent fixes for one project from breaking another.
>
> Implement cross-project regression validation and strict project isolation.

### TASKS

#### 1. Regression Matrix

Create: `python tools/regression_matrix.py`

It must:
- Run smoke test for: kord_v17, ravencroft_v17, 2 synthetic scripts
- Compare: semantic invariants, critic verdict, extended shots, UI bundle schema

If any mismatch → FAIL.

#### 2. Project Isolation Guard

Enforce:
- No global state mutation during execution
- No shared memory caches across project runs
- ExecutionContext locked per project

### REQUIRED VALIDATION

```bash
python tools/regression_matrix.py
```

All projects must pass.

### STOP CONDITION

Fixing one project does not alter outputs of another.

---

## DAY 3 - Approval Escalation + Segment Integrity

### MASTER PROMPT

> **ACT AS:** Production Pipeline Engineer
>
> **MISSION:** Make per-scene approval enforce downstream behavior.
>
> No rejected scene may reach stitch.
> Extended segments must be mathematically verified.

### TASKS

#### 1. Scene Escalation Enforcement

If scene status = REJECTED:
- Downstream shots = BLOCKED
- Stitch endpoint refuses execution
- Critic marks project NEEDS_REPAIR

#### 2. Segment Integrity Validator

Create: `python tools/validate_segment_integrity.py <project>`

Checks:
- segment durations sum = shot.duration
- no orphan segments
- no 6s videos for 60s shots
- no final video shorter than intended duration

### REQUIRED VALIDATION

Manually reject a scene.
Attempt stitch.
System must refuse.

### STOP CONDITION

Rejected scene physically prevents final output.

---

## DAY 4 - Engine Slot Hardening + Model Swap Safety

### MASTER PROMPT

> **ACT AS:** Model Governance Engineer
>
> **MISSION:** Make model swapping safe and provable.
> Prevent breaking pipeline via engine change.

### TASKS

#### 1. Model Slot Validator

Create: `python tools/validate_model_swap.py --slot video --candidate <model_id>`

Checks:
- Accepts image_url input
- Returns valid video
- Passes critic
- Duration correct
- Output schema matches

#### 2. Slot Change Requires Critic Approval

Admin UI change:
- Cannot activate new model unless:
  - validation passes
  - critic READY

### REQUIRED VALIDATION

Swap to dummy model. System blocks.
Swap to valid model. System passes.

### STOP CONDITION

Model swap cannot silently degrade pipeline.

---

## DAY 5 - Observability + Factory Load Test

### MASTER PROMPT

> **ACT AS:** Platform Reliability Engineer
>
> **MISSION:** Prove ATLAS can scale under concurrent load without corruption.

### TASKS

#### 1. Observability Upgrade

Send to Sentry:
- critic failures
- semantic violations
- repair loops
- execution_mode transitions

#### 2. Factory Load Test

Create: `python tools/factory_load_test.py --scripts 10 --parallel 3`

Must:
- Upload 10 scripts
- Run 3 concurrently
- All end READY or NEEDS_REPAIR
- No silent fail
- No cross contamination

### REQUIRED VALIDATION

Run load test.
- Zero crashes
- Zero data loss
- Ledger stable

### STOP CONDITION

System stable under concurrent multi-project load.

---

## AFTER WEEK 2 - ATLAS BECOMES:

- Deterministic
- Replayable
- Cross-project stable
- Model-upgrade safe
- Concurrency safe
- Critic-governed
- Factory ready

---

*Generated: 2026-02-10*
