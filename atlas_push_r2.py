"""
ATLAS GALLERY PUSH — R2 Edition
Drops a render into media.rumbletv.com/gallery instantly.

Drop one line anywhere in your pipeline after a render saves:
    from atlas_push_r2 import push_render
    push_render(url="https://...", name="shot_01.mp4", prompt="Marcus in rain")

Or upload a local file:
    from atlas_push_r2 import push_file
    push_file("/path/to/shot.mp4", prompt="Marcus in rain")

Gallery lives at: https://media.rumbletv.com/gallery/index.html
"""

import os, json, time, datetime, mimetypes
import boto3
from botocore.client import Config
from pathlib import Path

# ── R2 CONFIG (from ATLAS_CONTROL_SYSTEM/.env) ────────────────────────────────
ACCOUNT_ID = os.getenv("ATLAS_R2_ACCOUNT_ID", "026089839555deec85ae1cfc77648038")
ACCESS_KEY  = os.getenv("ATLAS_R2_ACCESS_KEY_ID", "9bd9b3551878dba7a09990d86d2c2af0")
SECRET_KEY  = os.getenv("ATLAS_R2_SECRET_KEY",
              "2869cc5136454a0cfad511df69a5c08f96b01490510a82a4276f8417215891c6")
BUCKET      = os.getenv("ATLAS_R2_BUCKET", "rumble-fanz")
PUBLIC_URL  = os.getenv("ATLAS_R2_PUBLIC_URL", "https://media.rumbletv.com")
MANIFEST_KEY = "gallery/manifest.json"
MAX_ITEMS    = 100
# ──────────────────────────────────────────────────────────────────────────────


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _read_manifest(s3) -> list:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)
        return json.loads(obj["Body"].read())
    except Exception:
        return []


def _write_manifest(s3, items: list):
    s3.put_object(
        Bucket=BUCKET,
        Key=MANIFEST_KEY,
        Body=json.dumps(items).encode(),
        ContentType="application/json",
        CacheControl="no-store",
    )


def push_render(url: str, name: str = "", prompt: str = "",
                type: str = "RENDER", thumb: str = "") -> bool:
    """
    Push a render URL directly to the gallery manifest.
    Use when the file is already publicly accessible (GCS, R2, CDN, etc.)
    """
    try:
        s3 = _client()
        manifest = _read_manifest(s3)
        item = {
            "id":     f"r_{int(time.time()*1000)}",
            "name":   name or Path(url).name,
            "url":    url,
            "thumb":  thumb or url,
            "prompt": prompt,
            "type":   type.upper(),
            "ts":     datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        manifest.insert(0, item)
        _write_manifest(s3, manifest[:MAX_ITEMS])
        print(f"[ATLAS GALLERY] ✓ '{item['name']}' → {PUBLIC_URL}/gallery/index.html")
        return True
    except Exception as e:
        print(f"[ATLAS GALLERY] ✗ push_render failed: {e}")
        return False


def push_file(local_path: str, prompt: str = "",
              type: str = "RENDER", thumb_path: str = "") -> bool:
    """
    Upload a local file to R2 then push to gallery manifest.
    Works for videos (.mp4, .mov, .webm) and images (.jpg, .png, .webp).
    """
    p = Path(local_path)
    if not p.exists():
        print(f"[ATLAS GALLERY] ✗ File not found: {local_path}")
        return False
    try:
        s3  = _client()
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"renders/{ts}_{p.name}"
        ct  = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

        print(f"[ATLAS GALLERY] Uploading {p.name} …")
        s3.upload_file(
            str(p), BUCKET, key,
            ExtraArgs={"ContentType": ct, "CacheControl": "public, max-age=31536000"},
        )
        pub = f"{PUBLIC_URL}/{key}"

        # Optional thumbnail
        thumb_url = pub
        if thumb_path and Path(thumb_path).exists():
            tp = Path(thumb_path)
            tk = f"renders/thumb_{ts}_{tp.name}"
            tct = mimetypes.guess_type(str(tp))[0] or "image/jpeg"
            s3.upload_file(str(tp), BUCKET, tk, ExtraArgs={"ContentType": tct})
            thumb_url = f"{PUBLIC_URL}/{tk}"

        return push_render(url=pub, name=p.name, prompt=prompt,
                           type=type, thumb=thumb_url)
    except Exception as e:
        print(f"[ATLAS GALLERY] ✗ push_file failed: {e}")
        return False


# ── ATLAS PIPELINE HOOKS ──────────────────────────────────────────────────────
# Paste into FULL_PRODUCTION_WITH_UI.py after each shot saves:
#
#   import sys; sys.path.insert(0, '/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM')
#   from atlas_push_r2 import push_render
#   push_render(url=shot_public_url, name=filename,
#               prompt=beat.get('description',''), type='PIPELINE')
#
# Paste into AI_MARKETPLACE_ARCHITECTURE.py after generation result:
#
#   from atlas_push_r2 import push_render
#   push_render(url=result_url, name=result_name, prompt=prompt, type='QUICK')
#
# Paste into FULL_PRODUCTION_WITH_UI.py for LOCAL files before GCS upload:
#
#   from atlas_push_r2 import push_file
#   push_file(local_path=output_path, prompt=beat_desc, type='PIPELINE')
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Quick test — pushes a sample render to gallery
    print("Testing ATLAS Gallery push…")
    ok = push_render(
        url    = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        name   = "test_render.mp4",
        prompt = "Test — ATLAS gallery is live",
        type   = "TEST",
        thumb  = "",
    )
    if ok:
        print(f"\n✅ Gallery live at: {PUBLIC_URL}/gallery/index.html")
    else:
        print("\n❌ Failed — check credentials")
