#!/usr/bin/env python3
"""
Run DINO-v3 continuity analysis over a manifest's latest renders.

Usage:
    python3 pipeline_tools/dino_continuity_report.py \
        --manifest blackwood_parallel_test.json \
        --media-root /Users/quantum/Desktop/atlas_output/nano_banana
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase_7_8_parallel_qc_director import DINOv3QualityAnalyzer

DEFAULT_MEDIA_ROOT = Path("/Users/quantum/Desktop/atlas_output/nano_banana")
REFERENCE_PREFIX = "CHAR_REF_"
FFMPEG = "ffmpeg"


def resolve_reference_image(name: str, media_root: Path) -> Optional[Path]:
    """Locate the cached reference portrait for the given character."""
    slug = name.strip().replace(" ", "_")
    candidates = [
        media_root / f"{REFERENCE_PREFIX}{slug}.jpg",
        media_root / f"{REFERENCE_PREFIX}{slug}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text())


def extract_frame(video: Path, timestamp: float, temp_dir: Path) -> Optional[Path]:
    """Grab a single frame from the video via ffmpeg."""
    frame_path = temp_dir / f"{video.stem}_{int(timestamp * 1000)}.jpg"
    cmd = [
        FFMPEG,
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{timestamp:.2f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 or not frame_path.exists():
        return None
    return frame_path


def analyze_manifest(manifest_path: Path,
                     media_root: Path,
                     output_dir: Path) -> Path:
    manifest = load_manifest(manifest_path)
    analyzer = DINOv3QualityAnalyzer()

    report: List[Dict] = []
    prev_image: Optional[Path] = None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        for scene in manifest.get("scenes", []):
            for shot in scene.get("shots", []):
                shot_id = shot["shot_id"]
                image_path = media_root / f"{shot_id}.jpg"
                video_path = media_root / f"{shot_id}.mp4"
                if not image_path.exists():
                    image_path = media_root / f"{shot_id}.png"
                if not image_path.exists():
                    report.append({
                        "shot_id": shot_id,
                        "scene_id": scene.get("scene_id"),
                        "error": f"Missing render for {shot_id}"
                    })
                    continue

                ref_scores = []
                references = []
                ref_field = shot.get("reference_needed")
                if isinstance(ref_field, str):
                    references = [name.strip() for name in ref_field.split(",") if name.strip()]

                for ref_name in references:
                    ref_image = resolve_reference_image(ref_name, media_root)
                    if not ref_image:
                        ref_scores.append({
                            "reference": ref_name,
                            "score": None,
                            "note": "reference image missing"
                        })
                        continue
                    score = analyzer.score_similarity(str(image_path), str(ref_image))
                    ref_scores.append({
                        "reference": ref_name,
                        "score": round(score, 3)
                    })

                prev_score = None
                if prev_image and prev_image.exists():
                    prev_score = analyzer.score_similarity(str(image_path), str(prev_image))

                frame_scores: List[Dict] = []
                if video_path.exists():
                    duration = shot.get("duration") or 6
                    timestamps = [max(0.05, duration * frac) for frac in (0.25, 0.5, 0.75)]
                    for ts in timestamps:
                        frame = extract_frame(video_path, ts, tmp_dir)
                        if not frame:
                            continue
                        ref_image = None
                        if references:
                            ref_image = resolve_reference_image(references[0], media_root)
                        if ref_image and ref_image.exists():
                            frame_score = analyzer.score_similarity(str(frame), str(ref_image))
                        elif prev_image and prev_image.exists():
                            frame_score = analyzer.score_similarity(str(frame), str(prev_image))
                        else:
                            frame_score = None
                        frame_scores.append({
                            "timestamp": round(ts, 2),
                            "score": None if frame_score is None else round(frame_score, 3)
                        })

                report.append({
                    "shot_id": shot_id,
                    "scene_id": scene.get("scene_id"),
                    "reference_scores": ref_scores,
                    "prev_frame_score": None if prev_score is None else round(prev_score, 3),
                    "frame_scores": frame_scores
                })

                prev_image = image_path

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"dino_report_{manifest_path.stem}_{timestamp}.json"
    out_path.write_text(json.dumps(report, indent=2))
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DINO continuity analysis")
    parser.add_argument("--manifest", required=True,
                        help="Path to the episode manifest JSON.")
    parser.add_argument("--media-root", default=str(DEFAULT_MEDIA_ROOT),
                        help="Directory containing the rendered JPG/PNG files.")
    parser.add_argument("--output-dir",
                        default="/Users/quantum/Desktop/atlas_output/dino_reports",
                        help="Directory to write the JSON report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    media_root = Path(args.media_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    report_path = analyze_manifest(manifest_path, media_root, output_dir)
    print(f"✅ DINO continuity report written to {report_path}")


if __name__ == "__main__":
    main()
