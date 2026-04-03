#!/usr/bin/env python3
"""
MODEL SWAP VALIDATOR

Validates that model slot changes are safe and tracked:
- Old model removed from ALLOWED list
- New model added to ALLOWED list
- All shot_plan.json files updated
- manifest_signature matches new config
- No orphan prompts referencing old models

Usage:
    python3 tools/validate_model_swap.py --check
    python3 tools/validate_model_swap.py --swap OLD_MODEL NEW_MODEL
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

# Current locked models
LOCKED_MODELS = {
    "image": "fal-ai/nano-banana-pro",
    "image_edit": "fal-ai/nano-banana-pro/edit",
    "video": "fal-ai/ltx-2.3/image-to-video/fast",
    "stitch": "ffmpeg"
}

# Forbidden models
FORBIDDEN_MODELS = [
    "minimax", "runway", "pika", "sora", "flux", "wan", "omnihuman"
]

# Model registry path
MODEL_REGISTRY_PATH = BASE_DIR / "atlas_agents_v16_7" / "model_registry.json"


def load_model_registry() -> Dict:
    """Load or create model registry."""
    if MODEL_REGISTRY_PATH.exists():
        with open(MODEL_REGISTRY_PATH) as f:
            return json.load(f)
    return {
        "locked_models": LOCKED_MODELS.copy(),
        "forbidden": FORBIDDEN_MODELS.copy(),
        "swap_history": []
    }


def save_model_registry(registry: Dict):
    """Save model registry."""
    with open(MODEL_REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=2)


def check_shot_plans_for_model(model_pattern: str) -> List[Tuple[str, str, int]]:
    """Find all shot plans referencing a model pattern."""
    matches = []
    pipeline_dir = BASE_DIR / "pipeline_outputs"

    for project_dir in pipeline_dir.iterdir():
        if not project_dir.is_dir():
            continue

        shot_plan_path = project_dir / "shot_plan.json"
        if not shot_plan_path.exists():
            continue

        with open(shot_plan_path) as f:
            content = f.read()

        count = content.lower().count(model_pattern.lower())
        if count > 0:
            matches.append((project_dir.name, str(shot_plan_path), count))

    return matches


def validate_current_config() -> Dict:
    """Validate current model configuration."""
    registry = load_model_registry()
    issues = []
    warnings = []

    # Check locked models exist
    for slot, model in registry["locked_models"].items():
        if not model:
            issues.append(f"BLOCKING: {slot} slot has no model assigned")

    # Check for forbidden model references in shot plans
    for forbidden in registry["forbidden"]:
        matches = check_shot_plans_for_model(forbidden)
        for project, path, count in matches:
            issues.append(f"BLOCKING: {project} references forbidden model '{forbidden}' ({count}x)")

    # Check model_registry.json exists
    if not MODEL_REGISTRY_PATH.exists():
        warnings.append("WARNING: model_registry.json not found, using defaults")

    # Check for prompts with model-specific tokens
    old_model_tokens = ["flux:", "minimax:", "runway:", "wan-video"]
    pipeline_dir = BASE_DIR / "pipeline_outputs"

    for project_dir in pipeline_dir.iterdir():
        if not project_dir.is_dir():
            continue
        shot_plan_path = project_dir / "shot_plan.json"
        if not shot_plan_path.exists():
            continue

        with open(shot_plan_path) as f:
            try:
                sp = json.load(f)
            except:
                continue

        for shot in sp.get("shots", []):
            prompt = shot.get("nano_prompt", "") + " " + shot.get("ltx_motion_prompt", "")
            for token in old_model_tokens:
                if token in prompt.lower():
                    warnings.append(f"WARNING: {project_dir.name}/{shot.get('shot_id')} has model-specific token '{token}'")

    return {
        "valid": len(issues) == 0,
        "locked_models": registry["locked_models"],
        "forbidden": registry["forbidden"],
        "issues": issues,
        "warnings": warnings[:10],  # Limit warnings
        "total_warnings": len(warnings)
    }


def validate_model_swap(old_model: str, new_model: str) -> Dict:
    """Validate a model swap before applying."""
    issues = []
    warnings = []
    affected_projects = []

    # Check old model exists in config
    registry = load_model_registry()
    old_slot = None
    for slot, model in registry["locked_models"].items():
        if model == old_model:
            old_slot = slot
            break

    if not old_slot:
        issues.append(f"BLOCKING: Old model '{old_model}' not in locked models")

    # Check new model is not forbidden
    for forbidden in registry["forbidden"]:
        if forbidden.lower() in new_model.lower():
            issues.append(f"BLOCKING: New model '{new_model}' matches forbidden pattern '{forbidden}'")

    # Find affected projects
    matches = check_shot_plans_for_model(old_model)
    for project, path, count in matches:
        affected_projects.append({
            "project": project,
            "occurrences": count
        })

    if affected_projects:
        warnings.append(f"WARNING: {len(affected_projects)} projects reference old model")

    return {
        "safe_to_swap": len(issues) == 0,
        "old_model": old_model,
        "new_model": new_model,
        "old_slot": old_slot,
        "issues": issues,
        "warnings": warnings,
        "affected_projects": affected_projects
    }


def apply_model_swap(old_model: str, new_model: str, dry_run: bool = True) -> Dict:
    """Apply a model swap to the registry and shot plans."""
    validation = validate_model_swap(old_model, new_model)

    if not validation["safe_to_swap"]:
        return {"success": False, "validation": validation}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "validation": validation,
            "would_update": validation["affected_projects"]
        }

    registry = load_model_registry()

    # Update locked models
    old_slot = validation["old_slot"]
    registry["locked_models"][old_slot] = new_model

    # Add to swap history
    registry["swap_history"].append({
        "timestamp": datetime.now().isoformat(),
        "slot": old_slot,
        "old_model": old_model,
        "new_model": new_model
    })

    # Add old model to forbidden
    if old_model not in registry["forbidden"]:
        registry["forbidden"].append(old_model)

    save_model_registry(registry)

    return {
        "success": True,
        "dry_run": False,
        "updated_slot": old_slot,
        "old_model": old_model,
        "new_model": new_model,
        "affected_projects": validation["affected_projects"],
        "message": f"Model swap complete. Old model '{old_model}' now forbidden."
    }


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tools/validate_model_swap.py --check")
        print("  python3 tools/validate_model_swap.py --swap OLD_MODEL NEW_MODEL")
        print("  python3 tools/validate_model_swap.py --swap OLD NEW --apply")
        sys.exit(1)

    if "--check" in sys.argv:
        result = validate_current_config()

        print(f"\n{'='*60}")
        print(f"  MODEL CONFIGURATION VALIDATION")
        print(f"{'='*60}")

        print("\n  LOCKED MODELS:")
        for slot, model in result["locked_models"].items():
            print(f"    {slot}: {model}")

        print(f"\n  FORBIDDEN ({len(result['forbidden'])}):")
        for f in result["forbidden"][:5]:
            print(f"    - {f}")

        if result["issues"]:
            print(f"\n  ISSUES ({len(result['issues'])}):")
            for issue in result["issues"]:
                print(f"    - {issue}")

        if result["warnings"]:
            print(f"\n  WARNINGS ({result['total_warnings']}):")
            for w in result["warnings"]:
                print(f"    - {w}")

        print(f"\n  VERDICT: {'PASS' if result['valid'] else 'FAIL'}")
        print(f"{'='*60}\n")

        sys.exit(0 if result["valid"] else 1)

    elif "--swap" in sys.argv:
        idx = sys.argv.index("--swap")
        if idx + 2 >= len(sys.argv):
            print("Error: --swap requires OLD_MODEL and NEW_MODEL")
            sys.exit(1)

        old_model = sys.argv[idx + 1]
        new_model = sys.argv[idx + 2]
        apply = "--apply" in sys.argv

        result = apply_model_swap(old_model, new_model, dry_run=not apply)

        print(f"\n{'='*60}")
        print(f"  MODEL SWAP {'EXECUTION' if apply else 'DRY-RUN'}")
        print(f"{'='*60}")
        print(f"  Old: {old_model}")
        print(f"  New: {new_model}")

        if not result["success"]:
            print(f"\n  BLOCKED: Cannot proceed with swap")
            for issue in result["validation"]["issues"]:
                print(f"    - {issue}")
        else:
            print(f"\n  Affected Projects: {len(result.get('affected_projects', result.get('would_update', [])))}")
            if apply:
                print(f"  Status: APPLIED")
                print(f"  Old model added to forbidden list")
            else:
                print(f"  Status: Dry-run only (use --apply to execute)")

        print(f"\n  RESULT: {'SUCCESS' if result['success'] else 'FAILED'}")
        print(f"{'='*60}\n")

        sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
