"""
ATLAS Training Pipeline — V1.0
Three-Lane Architecture: Production Serves → Training Learns → Promotion Decides

Lane A: Live Production (frozen champion, no self-modification)
Lane B: Learning Pipeline (capture → quarantine → approve → train → benchmark → shadow → promote)
Lane C: Memory Without Weight Changes (prompt patterns, preferences, archetypes)

Principle: The live system is self-RECORDING and self-EVALUATING, not self-UPDATING.
"""

import json
import time
import os
import hashlib
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timedelta

# ── PATHS ──────────────────────────────────────────────────────

TRAINING_ROOT = Path(os.environ.get("ATLAS_TRAINING_ROOT", "training"))
LANE_A = TRAINING_ROOT / "lane_a_production"
LANE_B = TRAINING_ROOT / "lane_b_learning"
LANE_C = TRAINING_ROOT / "lane_c_memory"

# Lane B subdirs
RAW_CAPTURES = LANE_B / "raw_captures"
QUARANTINE = LANE_B / "quarantine"
APPROVED_DATASET = LANE_B / "approved_dataset"
CANDIDATES = LANE_B / "candidates"
GOLDEN_BENCHMARKS = LANE_B / "golden_benchmarks"
SHADOW_RESULTS = LANE_B / "shadow_results"

# Lane C subdirs
WINNING_PROMPTS = LANE_C / "winning_prompts"
FAILED_PATTERNS = LANE_C / "failed_patterns"
SCENE_ARCHETYPES = LANE_C / "scene_archetypes"
PREFERENCE_LOG = LANE_C / "preference_log"

# Ensure dirs exist
for d in [LANE_A, RAW_CAPTURES, QUARANTINE, APPROVED_DATASET, CANDIDATES,
          GOLDEN_BENCHMARKS, SHADOW_RESULTS, WINNING_PROMPTS, FAILED_PATTERNS,
          SCENE_ARCHETYPES, PREFERENCE_LOG]:
    d.mkdir(parents=True, exist_ok=True)


# ── DATA STRUCTURES ────────────────────────────────────────────

@dataclass
class TrainingCapture:
    """Single training example captured from a production run."""
    capture_id: str
    timestamp: str
    project: str
    scene_id: str
    shot_id: str

    # Inputs
    script_beat: str = ""
    scene_contract: Dict = field(default_factory=dict)
    compiled_prompt: str = ""
    character_refs: List[str] = field(default_factory=list)
    location_refs: List[str] = field(default_factory=list)

    # Outputs
    first_frame_url: str = ""
    video_url: str = ""
    identity_score: float = 0.0
    vision_score: float = 0.0
    continuity_score: float = 0.0
    reward_score: float = 0.0

    # Human feedback
    human_approved: Optional[bool] = None
    human_override: str = ""        # What the human changed
    final_accepted: bool = False    # Was this the final version used?

    # Quality gates passed
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)


@dataclass
class GoldenBenchmark:
    """Locked reference scene for regression testing."""
    benchmark_id: str
    category: str       # dialogue, action, continuity, blocking, prop, closeup
    project: str
    scene_id: str
    shot_ids: List[str]

    # Reference scores (champion must match or beat)
    reference_scores: Dict[str, float] = field(default_factory=dict)
    # identity, vision, continuity, human_preference

    created_at: str = ""
    locked: bool = True


@dataclass
class CandidateModel:
    """A challenger model being evaluated for promotion."""
    candidate_id: str
    model_name: str
    training_data_version: str
    trained_at: str

    # Benchmark results
    benchmark_scores: Dict[str, Dict] = field(default_factory=dict)
    # benchmark_id → {score, champion_score, delta}

    # Shadow test results
    shadow_scores: Dict[str, float] = field(default_factory=dict)
    shadow_human_preference: float = 0.0  # % times human chose candidate over champion

    # Promotion decision
    promoted: Optional[bool] = None
    promotion_reason: str = ""
    promoted_at: Optional[str] = None


# ── LANE A: PRODUCTION CAPTURE ─────────────────────────────────

def capture_run(project: str, scene_id: str, shot_id: str,
                prompt: str, refs: Dict, scores: Dict,
                human_approved: bool = None, human_override: str = "") -> str:
    """
    Capture a production run as training material.
    Called after every shot generation in the runner.

    Returns: capture_id
    """
    capture_id = hashlib.sha256(
        f"{project}{scene_id}{shot_id}{time.time()}".encode()
    ).hexdigest()[:12]

    capture = TrainingCapture(
        capture_id=capture_id,
        timestamp=datetime.utcnow().isoformat(),
        project=project,
        scene_id=scene_id,
        shot_id=shot_id,
        compiled_prompt=prompt,
        character_refs=refs.get("character_refs", []),
        location_refs=refs.get("location_refs", []),
        identity_score=scores.get("identity", 0.0),
        vision_score=scores.get("vision", 0.0),
        continuity_score=scores.get("continuity", 0.0),
        reward_score=scores.get("reward", 0.0),
        first_frame_url=scores.get("first_frame_url", ""),
        video_url=scores.get("video_url", ""),
        human_approved=human_approved,
        human_override=human_override,
        gates_passed=scores.get("gates_passed", []),
        gates_failed=scores.get("gates_failed", [])
    )

    # Save to raw captures
    path = RAW_CAPTURES / f"{capture_id}.json"
    with open(path, "w") as f:
        json.dump(asdict(capture), f, indent=2)

    print(f"[TRAINING] Captured {shot_id} → {capture_id} (I:{capture.identity_score:.2f} V:{capture.vision_score:.2f})")
    return capture_id


# ── LANE B: QUARANTINE + APPROVAL ──────────────────────────────

def quarantine_captures(min_reward: float = 0.5) -> Dict:
    """
    Move raw captures through quarantine.
    Only captures passing quality gates get promoted to approved dataset.

    Run daily.
    """
    stats = {"processed": 0, "approved": 0, "rejected": 0, "quarantined": 0}

    for capture_path in RAW_CAPTURES.glob("*.json"):
        with open(capture_path) as f:
            capture = json.load(f)

        stats["processed"] += 1

        # Gate 1: Minimum reward score
        if capture.get("reward_score", 0) < min_reward:
            # Move to quarantine for review
            dest = QUARANTINE / capture_path.name
            shutil.move(str(capture_path), str(dest))
            stats["quarantined"] += 1
            continue

        # Gate 2: No failed critical gates
        critical_fails = [g for g in capture.get("gates_failed", [])
                         if g in ("identity", "model_lock", "generation_gate")]
        if critical_fails:
            dest = QUARANTINE / capture_path.name
            shutil.move(str(capture_path), str(dest))
            stats["quarantined"] += 1
            continue

        # Gate 3: Human approval (if available)
        if capture.get("human_approved") is False:
            # Explicitly rejected — save as negative example
            capture["_training_label"] = "negative"
            dest = APPROVED_DATASET / f"neg_{capture_path.name}"
            with open(dest, "w") as f:
                json.dump(capture, f, indent=2)
            capture_path.unlink()
            stats["rejected"] += 1
            continue

        # Passed all gates — approve
        capture["_training_label"] = "positive"
        dest = APPROVED_DATASET / capture_path.name
        with open(dest, "w") as f:
            json.dump(capture, f, indent=2)
        capture_path.unlink()
        stats["approved"] += 1

    print(f"[TRAINING] Quarantine: {stats}")
    return stats


def build_weekly_dataset() -> Dict:
    """
    Build a training dataset from approved captures.
    Includes: fresh approved + older high-value + failure counterexamples + canonical style.

    Run weekly.
    """
    dataset = {
        "version": datetime.utcnow().strftime("%Y%m%d"),
        "created_at": datetime.utcnow().isoformat(),
        "examples": [],
        "stats": {"positive": 0, "negative": 0, "canonical": 0}
    }

    # Fresh approved examples
    for p in sorted(APPROVED_DATASET.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:100]:
        with open(p) as f:
            ex = json.load(f)
        dataset["examples"].append(ex)
        label = ex.get("_training_label", "positive")
        if label == "positive":
            dataset["stats"]["positive"] += 1
        else:
            dataset["stats"]["negative"] += 1

    # Golden benchmark examples (replay to prevent forgetting)
    for p in GOLDEN_BENCHMARKS.glob("*.json"):
        with open(p) as f:
            bench = json.load(f)
        bench["_training_label"] = "canonical"
        dataset["examples"].append(bench)
        dataset["stats"]["canonical"] += 1

    # Save dataset snapshot
    ds_path = LANE_B / f"dataset_{dataset['version']}.json"
    with open(ds_path, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"[TRAINING] Weekly dataset: {dataset['stats']}, saved to {ds_path.name}")
    return dataset["stats"]


# ── LANE B: GOLDEN BENCHMARKS ─────────────────────────────────

def register_golden_benchmark(category: str, project: str, scene_id: str,
                               shot_ids: List[str], reference_scores: Dict) -> str:
    """
    Register a locked golden benchmark scene.
    Every candidate model must match or beat these.
    """
    bench_id = f"golden_{category}_{scene_id}"
    benchmark = GoldenBenchmark(
        benchmark_id=bench_id,
        category=category,
        project=project,
        scene_id=scene_id,
        shot_ids=shot_ids,
        reference_scores=reference_scores,
        created_at=datetime.utcnow().isoformat()
    )

    path = GOLDEN_BENCHMARKS / f"{bench_id}.json"
    with open(path, "w") as f:
        json.dump(asdict(benchmark), f, indent=2)

    print(f"[TRAINING] Golden benchmark registered: {bench_id}")
    return bench_id


def run_golden_benchmarks(candidate_model: str) -> Dict:
    """
    Run all golden benchmarks against a candidate model.
    Returns: {benchmark_id: {passed: bool, score: float, reference: float}}
    """
    results = {}
    for p in GOLDEN_BENCHMARKS.glob("*.json"):
        with open(p) as f:
            bench = json.load(f)

        bench_id = bench["benchmark_id"]
        ref_scores = bench.get("reference_scores", {})

        # TODO: Actually run the candidate model on the benchmark scenes
        # For now, placeholder scoring
        results[bench_id] = {
            "reference_scores": ref_scores,
            "candidate_scores": {},  # Fill after actual run
            "passed": False,
            "category": bench["category"]
        }

    return results


# ── LANE B: SHADOW TESTING + PROMOTION ─────────────────────────

def shadow_test(candidate_id: str, champion_results: Dict, candidate_results: Dict) -> Dict:
    """
    Compare candidate vs champion on the same scenes.
    Returns promotion recommendation.
    """
    comparisons = []
    candidate_wins = 0
    total = 0

    for scene_key in champion_results:
        if scene_key not in candidate_results:
            continue

        champ = champion_results[scene_key]
        cand = candidate_results[scene_key]
        total += 1

        # Compare on key metrics
        champ_score = (champ.get("identity", 0) * 0.35 +
                      champ.get("vision", 0) * 0.40 +
                      champ.get("continuity", 0) * 0.25)

        cand_score = (cand.get("identity", 0) * 0.35 +
                     cand.get("vision", 0) * 0.40 +
                     cand.get("continuity", 0) * 0.25)

        if cand_score >= champ_score:
            candidate_wins += 1

        comparisons.append({
            "scene": scene_key,
            "champion_score": round(champ_score, 3),
            "candidate_score": round(cand_score, 3),
            "winner": "candidate" if cand_score >= champ_score else "champion"
        })

    win_rate = candidate_wins / max(total, 1)

    result = {
        "candidate_id": candidate_id,
        "total_scenes": total,
        "candidate_wins": candidate_wins,
        "win_rate": round(win_rate, 3),
        "promote": win_rate >= 0.6,  # Candidate must win 60%+ to promote
        "comparisons": comparisons,
        "tested_at": datetime.utcnow().isoformat()
    }

    # Save shadow result
    path = SHADOW_RESULTS / f"shadow_{candidate_id}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[TRAINING] Shadow test: {candidate_id} win rate={win_rate:.1%} → {'PROMOTE' if result['promote'] else 'REJECT'}")
    return result


# ── LANE C: MEMORY WITHOUT WEIGHT CHANGES ─────────────────────

def record_winning_prompt(shot_id: str, prompt: str, scores: Dict):
    """Record a prompt that scored well for future reference."""
    entry = {
        "shot_id": shot_id,
        "prompt": prompt,
        "scores": scores,
        "recorded_at": datetime.utcnow().isoformat()
    }
    path = WINNING_PROMPTS / f"{shot_id}_{int(time.time())}.json"
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)


def record_failed_pattern(shot_id: str, prompt: str, failure_type: str, details: str):
    """Record a prompt pattern that failed for avoidance."""
    entry = {
        "shot_id": shot_id,
        "prompt_snippet": prompt[:500],
        "failure_type": failure_type,
        "details": details,
        "recorded_at": datetime.utcnow().isoformat()
    }
    path = FAILED_PATTERNS / f"fail_{failure_type}_{int(time.time())}.json"
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)


def record_preference(shot_id: str, option_a: str, option_b: str,
                       human_choice: str, reason: str = ""):
    """Record a human preference between two options."""
    entry = {
        "shot_id": shot_id,
        "option_a": option_a,
        "option_b": option_b,
        "human_choice": human_choice,  # "a" or "b"
        "reason": reason,
        "recorded_at": datetime.utcnow().isoformat()
    }
    path = PREFERENCE_LOG / f"pref_{shot_id}_{int(time.time())}.json"
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)


def get_winning_patterns(n: int = 20) -> List[Dict]:
    """Retrieve top N winning prompt patterns for controller bias."""
    winners = []
    for p in sorted(WINNING_PROMPTS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
        with open(p) as f:
            winners.append(json.load(f))
    return winners


def get_failed_patterns(n: int = 20) -> List[Dict]:
    """Retrieve recent failed patterns for avoidance."""
    failures = []
    for p in sorted(FAILED_PATTERNS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
        with open(p) as f:
            failures.append(json.load(f))
    return failures


# ── SCHEDULED PIPELINE ─────────────────────────────────────────

def daily_pipeline():
    """Run the daily training pipeline tasks."""
    print(f"\n{'='*60}")
    print(f"[TRAINING] Daily pipeline — {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")

    # 1. Process raw captures through quarantine
    stats = quarantine_captures()

    # 2. Report status
    raw_count = len(list(RAW_CAPTURES.glob("*.json")))
    quarantine_count = len(list(QUARANTINE.glob("*.json")))
    approved_count = len(list(APPROVED_DATASET.glob("*.json")))
    benchmark_count = len(list(GOLDEN_BENCHMARKS.glob("*.json")))

    print(f"\n[TRAINING] Status:")
    print(f"  Raw captures: {raw_count}")
    print(f"  In quarantine: {quarantine_count}")
    print(f"  Approved dataset: {approved_count}")
    print(f"  Golden benchmarks: {benchmark_count}")

    return {
        "raw": raw_count,
        "quarantine": quarantine_count,
        "approved": approved_count,
        "benchmarks": benchmark_count,
        "daily_stats": stats
    }


def weekly_pipeline():
    """Run the weekly training pipeline tasks."""
    print(f"\n{'='*60}")
    print(f"[TRAINING] Weekly pipeline — {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")

    # 1. Run daily first
    daily_stats = daily_pipeline()

    # 2. Build weekly dataset
    dataset_stats = build_weekly_dataset()

    # 3. Report
    print(f"\n[TRAINING] Weekly complete. Dataset: {dataset_stats}")
    return {"daily": daily_stats, "dataset": dataset_stats}


# ── FASTAPI ENDPOINTS ──────────────────────────────────────────

def register_training_routes(app):
    """Register training API routes on the FastAPI app."""
    from fastapi import Body

    @app.post("/atlas/training/capture")
    async def api_capture(request: Dict = Body(...)):
        capture_id = capture_run(
            project=request.get("project", ""),
            scene_id=request.get("scene_id", ""),
            shot_id=request.get("shot_id", ""),
            prompt=request.get("prompt", ""),
            refs=request.get("refs", {}),
            scores=request.get("scores", {}),
            human_approved=request.get("human_approved"),
            human_override=request.get("human_override", "")
        )
        return {"capture_id": capture_id}

    @app.post("/atlas/training/daily")
    async def api_daily():
        return daily_pipeline()

    @app.post("/atlas/training/weekly")
    async def api_weekly():
        return weekly_pipeline()

    @app.get("/atlas/training/status")
    async def api_training_status():
        return {
            "raw_captures": len(list(RAW_CAPTURES.glob("*.json"))),
            "quarantine": len(list(QUARANTINE.glob("*.json"))),
            "approved_dataset": len(list(APPROVED_DATASET.glob("*.json"))),
            "golden_benchmarks": len(list(GOLDEN_BENCHMARKS.glob("*.json"))),
            "winning_prompts": len(list(WINNING_PROMPTS.glob("*.json"))),
            "failed_patterns": len(list(FAILED_PATTERNS.glob("*.json"))),
            "preference_log": len(list(PREFERENCE_LOG.glob("*.json")))
        }

    @app.get("/atlas/training/winners")
    async def api_winners():
        return {"patterns": get_winning_patterns()}

    @app.get("/atlas/training/failures")
    async def api_failures():
        return {"patterns": get_failed_patterns()}

    @app.post("/atlas/training/benchmark/register")
    async def api_register_benchmark(request: Dict = Body(...)):
        bench_id = register_golden_benchmark(
            category=request.get("category", "custom"),
            project=request.get("project", ""),
            scene_id=request.get("scene_id", ""),
            shot_ids=request.get("shot_ids", []),
            reference_scores=request.get("reference_scores", {})
        )
        return {"benchmark_id": bench_id}

    print("[TRAINING] Training pipeline routes registered: /atlas/training/*")


# ── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "daily":
        daily_pipeline()
    elif cmd == "weekly":
        weekly_pipeline()
    elif cmd == "status":
        print(f"Raw captures: {len(list(RAW_CAPTURES.glob('*.json')))}")
        print(f"Quarantine: {len(list(QUARANTINE.glob('*.json')))}")
        print(f"Approved: {len(list(APPROVED_DATASET.glob('*.json')))}")
        print(f"Benchmarks: {len(list(GOLDEN_BENCHMARKS.glob('*.json')))}")
        print(f"Winning prompts: {len(list(WINNING_PROMPTS.glob('*.json')))}")
        print(f"Failed patterns: {len(list(FAILED_PATTERNS.glob('*.json')))}")
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: daily, weekly, status")
