"""
CREATION PACK RECAST RUNNER — V27.1
====================================
Executes the recast manifest: generates character refs and location refs
via FAL nano-banana-pro from canonical appearance descriptions.

Usage:
  python3 tools/run_recast.py pipeline_outputs/victorian_shadows_ep1 [--chars-only] [--locs-only] [--force-all]
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# Load FAL key from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import fal_client

from creation_pack_validator import (
    validate_project,
    build_recast_manifest,
    CreationPackReport,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recast")


def generate_ref(job: dict, project_path: str, dry_run: bool = False) -> dict:
    """
    Execute a single FAL generation job from the recast manifest.

    Returns dict with:
      - success: bool
      - output_path: str (local file path)
      - candidates: List[str] (if num_candidates > 1)
      - selected: str (best candidate path)
      - prompt: str (the prompt used)
      - elapsed_ms: float
    """
    pp = Path(project_path)
    output_rel = job["output_path"]
    output_path = pp / output_rel
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prompt = job["prompt"]
    num_candidates = job.get("num_candidates", 1)
    resolution = job.get("resolution", "1K")
    aspect_ratio = job.get("aspect_ratio", "1:1")
    model = job.get("model", "fal-ai/nano-banana-pro")

    logger.info(f"Generating: {job['name']} → {job['ref_type']} ({num_candidates} candidates)")
    logger.info(f"  Prompt: {prompt[:120]}...")

    if dry_run:
        return {"success": False, "dry_run": True, "prompt": prompt}

    start = time.time()

    try:
        # V27.1: Determine generation mode
        # - source_image present → IMAGE-TO-IMAGE reframe (nano-banana-pro/edit)
        #   Same person/room, different camera angle. Source image = identity anchor.
        # - source_image absent → TEXT-TO-IMAGE (nano-banana-pro)
        #   Master generation from text description.
        source_image = job.get("source_image")

        if source_image and model == "fal-ai/nano-banana-pro/edit":
            # IMAGE-TO-IMAGE REFRAME
            # Upload source image to get FAL URL
            source_path = Path(source_image)
            if not source_path.is_absolute():
                source_path = Path(project_path) / source_image
            if not source_path.exists():
                # Try character_library_locked
                source_path = Path(project_path) / "character_library_locked" / Path(source_image).name
            if not source_path.exists():
                logger.error(f"  Source image not found: {source_image}")
                return {"success": False, "error": f"Source image not found: {source_image}"}

            logger.info(f"  IMAGE-TO-IMAGE reframe from: {source_path.name}")
            # Upload source to FAL
            source_url = fal_client.upload_file(str(source_path))
            logger.info(f"  Source uploaded: {source_url[:80]}...")

            result = fal_client.run(
                model,
                arguments={
                    "prompt": prompt,
                    "image_urls": [source_url],
                    "num_images": num_candidates,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "jpeg",
                    "safety_tolerance": "6",
                },
            )
        else:
            # TEXT-TO-IMAGE master generation
            result = fal_client.run(
                model,
                arguments={
                    "prompt": prompt,
                    "num_images": num_candidates,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "jpeg",
                    "safety_tolerance": "6",
                },
            )

        elapsed = (time.time() - start) * 1000

        images = result.get("images", [])
        if not images:
            logger.error(f"  No images returned for {job['name']} {job['ref_type']}")
            return {"success": False, "error": "no images returned", "elapsed_ms": elapsed}

        # Save all candidates
        candidate_paths = []
        for i, img in enumerate(images):
            url = img.get("url", "")
            if url:
                import urllib.request
                suffix = f"_candidate_{i}" if len(images) > 1 else ""
                cand_name = output_path.stem + suffix + output_path.suffix
                cand_path = output_path.parent / cand_name
                urllib.request.urlretrieve(url, str(cand_path))
                candidate_paths.append(str(cand_path))
                logger.info(f"  Saved candidate {i}: {cand_path.name} ({url[:60]}...)")

        # For now, select first candidate as primary (operator reviews later)
        # In production: use vision scoring to pick best
        if candidate_paths:
            selected = candidate_paths[0]
            # Copy selected as the canonical ref
            if len(candidate_paths) > 1:
                import shutil
                shutil.copy2(selected, str(output_path))
                logger.info(f"  Selected candidate 0 as canonical: {output_path.name}")
            # If only 1 candidate, it's already at the right path

        return {
            "success": True,
            "output_path": str(output_path),
            "candidates": candidate_paths,
            "selected": str(output_path),
            "prompt": prompt,
            "elapsed_ms": elapsed,
        }

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"  FAL error for {job['name']} {job['ref_type']}: {e}")
        return {"success": False, "error": str(e), "elapsed_ms": elapsed}


def update_cast_map_provenance(
    cast_map_path: str,
    char_name: str,
    ref_type: str,
    prompt: str,
    output_path: str,
):
    """Update cast_map.json with generation provenance for a character ref."""
    with open(cast_map_path) as f:
        cast_map = json.load(f)

    if char_name in cast_map and isinstance(cast_map[char_name], dict):
        now = datetime.utcnow().isoformat()

        if ref_type == "headshot":
            cast_map[char_name]["_reference_generation_prompt"] = prompt
            cast_map[char_name]["_reference_validated"] = True
            cast_map[char_name]["_reference_validated_at"] = now
            cast_map[char_name]["_reference_generated_at"] = now
            # Update paths to point to new ref
            cast_map[char_name]["character_reference_url"] = output_path
            cast_map[char_name]["character_reference_path"] = output_path
            cast_map[char_name]["reference_url"] = output_path
            cast_map[char_name]["headshot_url"] = output_path

        # Track multi-image pack refs
        pack_key = f"_ref_pack_{ref_type}"
        cast_map[char_name][pack_key] = {
            "path": output_path,
            "prompt": prompt,
            "generated_at": now,
        }

    with open(cast_map_path, "w") as f:
        json.dump(cast_map, f, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/run_recast.py <project_path> [--chars-only] [--locs-only] [--force-all] [--dry-run]")
        sys.exit(1)

    project_path = sys.argv[1]
    chars_only = "--chars-only" in sys.argv
    locs_only = "--locs-only" in sys.argv
    force_all = "--force-all" in sys.argv
    dry_run = "--dry-run" in sys.argv

    pp = Path(project_path)
    cast_map_path = pp / "cast_map.json"

    # Run creation pack validation
    logger.info(f"Validating creation pack for {project_path}...")
    report = validate_project(project_path)

    logger.info(f"Characters: {len(report.characters)}, Locations: {len(report.locations)}")
    logger.info(f"Blocking: {len(report.blocking_issues)}, Warnings: {len(report.warnings)}")

    # Load cast_map and story_bible for recast
    with open(cast_map_path) as f:
        cast_map = json.load(f)

    story_bible = None
    sb_path = pp / "story_bible.json"
    if sb_path.exists():
        with open(sb_path) as f:
            story_bible = json.load(f)

    # Build recast manifest
    jobs = build_recast_manifest(report, cast_map, story_bible, force_all=force_all)
    logger.info(f"Total recast jobs: {len(jobs)}")

    # Filter by type if requested
    if chars_only:
        jobs = [j for j in jobs if j["job_type"] == "character_ref"]
        logger.info(f"Chars-only: {len(jobs)} character jobs")
    elif locs_only:
        jobs = [j for j in jobs if j["job_type"] == "location_ref"]
        logger.info(f"Locs-only: {len(jobs)} location jobs")

    # Execute jobs
    results = []
    total_start = time.time()

    for i, job in enumerate(jobs):
        logger.info(f"\n[{i+1}/{len(jobs)}] {job['job_type']}: {job['name']} → {job['ref_type']}")
        result = generate_ref(job, project_path, dry_run=dry_run)
        results.append({"job": job, "result": result})

        # Update cast_map provenance for successful character refs
        if result.get("success") and job["job_type"] == "character_ref":
            update_cast_map_provenance(
                str(cast_map_path),
                job["name"],
                job["ref_type"],
                job["prompt"],
                result["output_path"],
            )
            logger.info(f"  Updated cast_map provenance for {job['name']}")

        # Brief pause between FAL calls
        if not dry_run and i < len(jobs) - 1:
            time.sleep(0.5)

    total_elapsed = time.time() - total_start

    # Summary
    successful = sum(1 for r in results if r["result"].get("success"))
    failed = sum(1 for r in results if not r["result"].get("success") and not r["result"].get("dry_run"))

    logger.info(f"\n{'='*60}")
    logger.info(f"RECAST COMPLETE")
    logger.info(f"Total: {len(jobs)} jobs | Success: {successful} | Failed: {failed}")
    logger.info(f"Elapsed: {total_elapsed:.1f}s")
    logger.info(f"{'='*60}")

    # Save results report
    report_path = pp / "reports" / "recast_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "total_jobs": len(jobs),
            "successful": successful,
            "failed": failed,
            "elapsed_seconds": total_elapsed,
            "results": [
                {
                    "name": r["job"]["name"],
                    "ref_type": r["job"]["ref_type"],
                    "job_type": r["job"]["job_type"],
                    "success": r["result"].get("success", False),
                    "output": r["result"].get("output_path", ""),
                    "error": r["result"].get("error", ""),
                }
                for r in results
            ],
        }, f, indent=2)
    logger.info(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
