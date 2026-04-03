#!/usr/bin/env python3
"""
r2_music_uploader.py — Upload FANZ SOUND catalog to Cloudflare R2
Reads suno_catalog.json, uploads each track to rumble-fanz R2 bucket,
writes r2_music_manifest.json with public URLs.

Usage:
    python3 tools/r2_music_uploader.py
    python3 tools/r2_music_uploader.py --catalog /path/to/suno_catalog.json
    python3 tools/r2_music_uploader.py --dry-run       (show what would upload)
    python3 tools/r2_music_uploader.py --category 03_RUMBLE_LEAGUE  (one category)
    python3 tools/r2_music_uploader.py --resume        (skip already-uploaded tracks)

Requires:
    wrangler CLI installed and authenticated (wrangler r2 object put)
    OR CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID env vars for direct API upload
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
BUCKET_NAME   = "rumble-fanz"
R2_PREFIX     = "music"
R2_CDN_BASE   = f"https://pub-rumble-fanz.r2.dev/{R2_PREFIX}"  # update with your public URL

CATALOG_PATH  = Path("/Users/quantum/Desktop/FANZ_SOUND_50PACK/suno_catalog.json")
MANIFEST_PATH = Path("/Users/quantum/Desktop/FANZ_SOUND_50PACK/r2_music_manifest.json")

# ── Wrangler R2 upload ────────────────────────────────────────────────────────
def upload_via_wrangler(local_path: Path, r2_key: str, dry_run: bool = False) -> dict:
    """
    Upload a single file using wrangler r2 object put.
    Returns {"success": True/False, "url": ..., "error": ...}
    """
    cmd = [
        "wrangler", "r2", "object", "put",
        f"{BUCKET_NAME}/{r2_key}",
        "--file", str(local_path),
        "--content-type", "audio/mpeg",
    ]

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "r2_key": r2_key,
            "url": f"{R2_CDN_BASE}/{r2_key}",
        }

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {
                "success": True,
                "r2_key": r2_key,
                "url": f"{R2_CDN_BASE}/{r2_key}",
                "wrangler_stdout": result.stdout.strip()[:200],
            }
        else:
            return {
                "success": False,
                "r2_key": r2_key,
                "error": result.stderr.strip()[:300],
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "r2_key": r2_key, "error": "timeout after 120s"}
    except FileNotFoundError:
        return {"success": False, "r2_key": r2_key, "error": "wrangler not found in PATH"}
    except Exception as e:
        return {"success": False, "r2_key": r2_key, "error": str(e)}


def upload_via_cf_api(local_path: Path, r2_key: str, account_id: str,
                      api_token: str, dry_run: bool = False) -> dict:
    """
    Upload via Cloudflare Workers R2 API (requires requests library).
    Fallback when wrangler is not available.
    """
    if dry_run:
        return {
            "success": True, "dry_run": True,
            "r2_key": r2_key,
            "url": f"{R2_CDN_BASE}/{r2_key}",
        }
    try:
        import requests
    except ImportError:
        return {"success": False, "r2_key": r2_key, "error": "requests library not installed"}

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets/{BUCKET_NAME}/objects/{r2_key}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "audio/mpeg",
    }
    try:
        with open(local_path, "rb") as f:
            resp = requests.put(url, headers=headers, data=f, timeout=120)
        if resp.status_code in (200, 201):
            return {"success": True, "r2_key": r2_key, "url": f"{R2_CDN_BASE}/{r2_key}"}
        else:
            return {"success": False, "r2_key": r2_key, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "r2_key": r2_key, "error": str(e)}


def check_wrangler() -> bool:
    try:
        r = subprocess.run(["wrangler", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


# ── Manifest helpers ──────────────────────────────────────────────────────────
def load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            pass
    return {"uploads": {}, "generated_at": None}


def save_manifest(manifest: dict, manifest_path: Path):
    manifest["last_updated"] = datetime.utcnow().isoformat() + "Z"
    manifest_path.write_text(json.dumps(manifest, indent=2))


# ── Main upload loop ──────────────────────────────────────────────────────────
def run_upload(catalog_path: Path, manifest_path: Path,
               category_filter: str | None,
               dry_run: bool, resume: bool) -> dict:

    # Load catalog
    if not catalog_path.exists():
        print(f"[ERROR] Catalog not found: {catalog_path}")
        print("  Run: python3 tools/suno_cataloger.py  first")
        sys.exit(1)

    raw_catalog = json.loads(catalog_path.read_text())
    tracks = raw_catalog.get("tracks", [])
    print(f"[UPLOADER] Loaded {len(tracks)} tracks from catalog")

    # Filter by category
    if category_filter:
        tracks = [t for t in tracks if t["suggested_category"] == category_filter]
        print(f"[UPLOADER] Filtered to {len(tracks)} tracks in {category_filter}")

    # Load existing manifest for resume
    manifest = load_manifest(manifest_path)
    already_uploaded = set(manifest["uploads"].keys()) if resume else set()
    if resume and already_uploaded:
        print(f"[UPLOADER] Resume mode: {len(already_uploaded)} already uploaded, skipping")

    # Detect upload method
    use_wrangler = check_wrangler()
    cf_api_token  = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    use_api = bool(cf_api_token and cf_account_id)

    if not use_wrangler and not use_api and not dry_run:
        print("[WARN] Neither wrangler nor CLOUDFLARE_API_TOKEN found.")
        print("       Running in dry-run mode. Set CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID")
        print("       or install wrangler (npm i -g wrangler) for real uploads.")
        dry_run = True

    print(f"[UPLOADER] Method  : {'wrangler' if use_wrangler else 'CF API' if use_api else 'DRY RUN'}")
    print(f"[UPLOADER] Bucket  : {BUCKET_NAME}")
    print(f"[UPLOADER] Dry run : {dry_run}")

    results = {"success": [], "failed": [], "skipped": []}
    total = len(tracks)

    for i, track in enumerate(tracks, 1):
        track_id = track["id"]
        r2_key   = track.get("r2_key", f"{R2_PREFIX}/{track['suggested_category']}/{track['filename']}")
        # Use catalog_path (taxonomy folder copy) if available, else raw
        local_path = Path(track.get("catalog_path", track["raw_path"]))
        if not local_path.exists():
            local_path = Path(track["raw_path"])

        print(f"  [{i:3d}/{total}] {track_id[:16]}...  {r2_key}", end="  ")

        # Skip if resume and already done
        if track_id in already_uploaded:
            print("SKIP (already uploaded)")
            results["skipped"].append(track_id)
            continue

        if not local_path.exists():
            print(f"MISSING FILE: {local_path}")
            results["failed"].append({"id": track_id, "error": f"file not found: {local_path}"})
            continue

        # Upload
        if use_wrangler:
            res = upload_via_wrangler(local_path, r2_key, dry_run=dry_run)
        elif use_api:
            res = upload_via_cf_api(local_path, r2_key, cf_account_id, cf_api_token, dry_run=dry_run)
        else:
            res = upload_via_wrangler(local_path, r2_key, dry_run=True)

        if res.get("success"):
            print(f"OK {'(dry)' if dry_run else ''}")
            manifest["uploads"][track_id] = {
                "r2_key":   r2_key,
                "url":      res.get("url", ""),
                "category": track["suggested_category"],
                "filename": track["filename"],
                "bpm":      track.get("bpm_estimate", 0),
                "energy":   track.get("energy", "mid"),
                "duration": track.get("duration_s", 0),
                "mood_tags": track.get("mood_tags", []),
                "uploaded_at": datetime.utcnow().isoformat() + "Z",
            }
            results["success"].append(track_id)
        else:
            print(f"FAIL: {res.get('error', '?')[:60]}")
            results["failed"].append({"id": track_id, "error": res.get("error", "unknown")})

        # Save manifest periodically
        if i % 20 == 0:
            save_manifest(manifest, manifest_path)

        # Small delay to avoid rate limits on real uploads
        if not dry_run and i % 5 == 0:
            time.sleep(0.5)

    save_manifest(manifest, manifest_path)

    print(f"\n[UPLOAD COMPLETE]")
    print(f"  Success : {len(results['success'])}")
    print(f"  Failed  : {len(results['failed'])}")
    print(f"  Skipped : {len(results['skipped'])}")
    print(f"  Manifest: {manifest_path}")

    if results["failed"]:
        print("\n  Failed tracks:")
        for f in results["failed"][:10]:
            print(f"    {f['id'][:20]}: {f['error'][:60]}")

    return results


def print_manifest_summary(manifest_path: Path):
    """Print a human-readable summary of the manifest."""
    if not manifest_path.exists():
        print("[MANIFEST] Not found")
        return
    data = json.loads(manifest_path.read_text())
    uploads = data.get("uploads", {})
    by_category: dict[str, list] = {}
    for tid, info in uploads.items():
        cat = info.get("category", "unknown")
        by_category.setdefault(cat, []).append(info)

    print(f"\n[MANIFEST SUMMARY] {len(uploads)} tracks uploaded")
    print(f"  Last updated: {data.get('last_updated', 'unknown')}")
    for cat, items in sorted(by_category.items()):
        print(f"    {cat:25s}  {len(items):3d} tracks")

    # Show sample R2 URLs
    sample = list(uploads.values())[:3]
    if sample:
        print("\n  Sample R2 URLs:")
        for s in sample:
            print(f"    {s.get('url', '?')}")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Upload FANZ SOUND catalog to R2")
    parser.add_argument("--catalog",   default=str(CATALOG_PATH))
    parser.add_argument("--manifest",  default=str(MANIFEST_PATH))
    parser.add_argument("--category",  default=None, help="Upload only this category")
    parser.add_argument("--dry-run",   action="store_true", help="Show what would upload")
    parser.add_argument("--resume",    action="store_true", help="Skip already-uploaded tracks")
    parser.add_argument("--summary",   action="store_true", help="Print manifest summary and exit")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)

    if args.summary:
        print_manifest_summary(manifest_path)
        return

    run_upload(
        catalog_path=Path(args.catalog),
        manifest_path=manifest_path,
        category_filter=args.category,
        dry_run=args.dry_run,
        resume=args.resume,
    )
    print_manifest_summary(manifest_path)


if __name__ == "__main__":
    main()
