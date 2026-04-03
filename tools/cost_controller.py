"""
ATLAS V37 — Cost Controller (Observe-Only)
Tracks generation spend and projects overruns. Phase 1: observe and report only.
Authority: OBSERVE_ONLY — never blocks renders or modifies generation behavior.
"""
import json, os
from pathlib import Path
from datetime import datetime, timezone

_REPO = Path(__file__).resolve().parent.parent
_COST_LEDGER = _REPO / "pipeline_outputs" / "cost_ledger.json"

# Cost estimates per API call (USD)
COST_TABLE = {
    "fal_nano_banana_pro": 0.04,      # first frame generation
    "fal_kling_v3_pro_5s": 0.12,      # 5-second video
    "fal_kling_v3_pro_10s": 0.20,     # 10-second video
    "gemini_vision_score": 0.002,     # vision analysis call
    "gemini_filmmakers_eye": 0.005,   # filmmaker's eye audit
}

DEFAULT_EPISODE_BUDGET = 25.00  # USD

def _load_ledger():
    if _COST_LEDGER.exists():
        return json.loads(_COST_LEDGER.read_text())
    return {"version": "v37.0", "entries": [], "created": datetime.now(timezone.utc).isoformat()}

def _save_ledger(ledger):
    _COST_LEDGER.write_text(json.dumps(ledger, indent=2, default=str))

def log_cost(episode_id, scene_id, shot_id, api_call_type, actual_cost=None):
    """Log a generation cost event. Uses COST_TABLE estimate if actual_cost not provided."""
    ledger = _load_ledger()
    cost = actual_cost if actual_cost is not None else COST_TABLE.get(api_call_type, 0.0)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "episode_id": episode_id,
        "scene_id": scene_id,
        "shot_id": shot_id,
        "api_call_type": api_call_type,
        "cost_usd": cost
    }
    ledger["entries"].append(entry)
    _save_ledger(ledger)
    return cost

def get_episode_spend(episode_id):
    """Get total spend for an episode."""
    ledger = _load_ledger()
    entries = [e for e in ledger["entries"] if e.get("episode_id") == episode_id]
    total = sum(e.get("cost_usd", 0) for e in entries)
    return {
        "episode_id": episode_id,
        "total_spend_usd": round(total, 2),
        "call_count": len(entries),
        "budget_cap": DEFAULT_EPISODE_BUDGET,
        "budget_remaining": round(DEFAULT_EPISODE_BUDGET - total, 2),
        "status": "WITHIN_BUDGET" if total <= DEFAULT_EPISODE_BUDGET else "OVER_BUDGET",
        "by_type": {}
    }

def get_episode_projection(episode_id, total_shots, completed_shots):
    """Project final episode cost based on current burn rate."""
    spend = get_episode_spend(episode_id)
    if completed_shots == 0:
        return {**spend, "projected_final": 0, "projection_status": "NO_DATA"}

    per_shot = spend["total_spend_usd"] / completed_shots
    projected = per_shot * total_shots

    return {
        **spend,
        "completed_shots": completed_shots,
        "total_shots": total_shots,
        "cost_per_shot": round(per_shot, 3),
        "projected_final_usd": round(projected, 2),
        "projection_status": "OVER_TREND" if projected > DEFAULT_EPISODE_BUDGET else "ON_TRACK"
    }

def get_network_spend(network_id=None):
    """Get total spend across all episodes, optionally filtered by network."""
    ledger = _load_ledger()
    entries = ledger["entries"]
    total = sum(e.get("cost_usd", 0) for e in entries)
    episodes = set(e.get("episode_id", "") for e in entries)
    return {
        "total_spend_usd": round(total, 2),
        "episode_count": len(episodes),
        "entry_count": len(entries)
    }

if __name__ == "__main__":
    stats = get_network_spend()
    print(f"Cost Controller: ${stats['total_spend_usd']} across {stats['episode_count']} episodes ({stats['entry_count']} API calls)")
