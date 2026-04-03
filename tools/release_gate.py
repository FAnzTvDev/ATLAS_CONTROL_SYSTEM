"""
ATLAS V37 — Release Gate (Advisory Mode)
Scores stitched episodes across multiple quality dimensions. Phase 1: advisory only.
Authority: OBSERVE_ONLY — scores and recommends, never blocks publication.
"""
import json, os
from pathlib import Path
from datetime import datetime, timezone

_REPO = Path(__file__).resolve().parent.parent
_RELEASE_LEDGER = _REPO / "pipeline_outputs" / "release_ledger.json"

# Thresholds (advisory — will become blocking in Phase 2)
THRESHOLDS = {
    "identity_score": 85.0,
    "continuity_score": 80.0,
    "pacing_score": 70.0,
    "artifact_score": 90.0,
    "story_compliance_score": 85.0,
    "overall_min": 80.0,
}

def _load_ledger():
    if _RELEASE_LEDGER.exists():
        return json.loads(_RELEASE_LEDGER.read_text())
    return {"version": "v37.0", "entries": {}, "created": datetime.now(timezone.utc).isoformat()}

def _save_ledger(ledger):
    _RELEASE_LEDGER.write_text(json.dumps(ledger, indent=2, default=str))

def score_episode(episode_id, scores):
    """
    Score a stitched episode.
    scores dict should contain: identity_score, continuity_score, pacing_score,
    artifact_score, story_compliance_score (all 0-100).
    Returns release recommendation.
    """
    overall = sum(scores.values()) / len(scores) if scores else 0

    failures = []
    for dimension, threshold in THRESHOLDS.items():
        if dimension == "overall_min":
            if overall < threshold:
                failures.append(f"overall {overall:.1f} < {threshold}")
        elif dimension in scores and scores[dimension] < threshold:
            failures.append(f"{dimension} {scores[dimension]:.1f} < {threshold}")

    if not failures:
        recommendation = "PASS"
    elif len(failures) <= 2 and overall >= THRESHOLDS["overall_min"]:
        recommendation = "HOLD"
    else:
        recommendation = "RERENDER_REQUIRED"

    entry = {
        "episode_id": episode_id,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "scores": scores,
        "overall_score": round(overall, 1),
        "recommendation": recommendation,
        "failures": failures,
        "mode": "ADVISORY",  # Phase 1 — does not block
        "thresholds_used": THRESHOLDS,
    }

    ledger = _load_ledger()
    ledger["entries"][episode_id] = entry
    _save_ledger(ledger)

    return entry

def get_release_status(episode_id):
    """Get the latest release gate result for an episode."""
    ledger = _load_ledger()
    return ledger["entries"].get(episode_id, {"status": "NOT_SCORED"})

def print_release_report(episode_id):
    """Print human-readable release gate report."""
    result = get_release_status(episode_id)
    if result.get("status") == "NOT_SCORED":
        print(f"Episode {episode_id}: NOT YET SCORED")
        return

    print(f"═══ RELEASE GATE — {episode_id} ═══")
    print(f"Overall Score: {result['overall_score']}")
    print(f"Recommendation: {result['recommendation']} ({result['mode']})")
    print()
    for dim, score in result.get("scores", {}).items():
        threshold = THRESHOLDS.get(dim, 0)
        icon = "✅" if score >= threshold else "⚠️"
        print(f"  {icon} {dim}: {score:.1f} (threshold: {threshold})")

    if result.get("failures"):
        print(f"\nFailures: {', '.join(result['failures'])}")

if __name__ == "__main__":
    # Demo
    demo = score_episode("victorian_shadows_ep1", {
        "identity_score": 91.0,
        "continuity_score": 78.0,
        "pacing_score": 72.0,
        "artifact_score": 95.0,
        "story_compliance_score": 88.0,
    })
    print_release_report("victorian_shadows_ep1")
