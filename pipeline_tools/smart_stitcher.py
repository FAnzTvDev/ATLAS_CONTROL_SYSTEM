#!/usr/bin/env python3
"""
Scene-aware smart stitching utility.

Packages the latest renders into two curated edits:
  1. master – full continuity run (door → chart → Chen look → entry → interior)
  2. highlight – ~1 minute recap with low-volume prep shots and full-volume dialogue beats

Usage:
    python3 pipeline_tools/smart_stitcher.py --scene 004 --mode master
    python3 pipeline_tools/smart_stitcher.py --scene 004 --mode highlight
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Iterable

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = "ffmpeg"
_FINGERPRINT_CACHE: Dict[Path, str] = {}
TARGET_UNDERSCORE_RATIO = 0.6
RATIO_TOLERANCE = 0.08


def run_ffmpeg(args: List[str]) -> None:
    proc = subprocess.run(
        [FFMPEG, *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({' '.join(args)}):\n{proc.stderr}")


def volume_adjust(src: Path, dst: Path, gain: float) -> None:
    if src == dst:
        temp = dst.with_name(dst.stem + '_tmp' + dst.suffix)
        run_ffmpeg(['-y', '-i', str(src), '-c:v', 'copy', '-af', f'volume={gain}', str(temp)])
        temp.replace(dst)
    else:
        run_ffmpeg(['-y', '-i', str(src), '-c:v', 'copy', '-af', f'volume={gain}', str(dst)])


def ensure_audio(src: Path, dst: Path) -> None:
    probe = subprocess.run(
        [FFMPEG, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    if probe.returncode == 0 and probe.stdout.strip():
        dst.write_bytes(src.read_bytes())
        return
    run_ffmpeg([
        "-y",
        "-i", str(src),
        "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=24000",
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac",
        str(dst),
    ])


def concat(clips: List[Path], output: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as concat_file:
        for clip in clips:
            concat_file.write(f"file '{clip}'\n")
    run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", concat_file.name, "-c", "copy", str(output)])


def mix_underscore(video: Path, underscore: Path, output: Path, dialog_gain: float, underscore_gain: float) -> None:
    ratio = validate_mix_ratio(video, underscore, dialog_gain, underscore_gain)
    if ratio is not None:
        print(f"🎧 Target underscore/dialogue ratio ~{TARGET_UNDERSCORE_RATIO:.2f}; measured {ratio:.2f}")

    run_ffmpeg([
        "-y",
        "-i", str(video),
        "-i", str(underscore),
        "-filter_complex",
        f"[0:a]volume={dialog_gain}[a1];"
        f"[1:a]volume={underscore_gain},aresample=24000,apad[a2];"
        f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output),
    ])


def measure_rms_db(path: Path) -> Optional[float]:
    """Measure overall RMS level in decibels for the given media asset."""
    result = subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "astats=metadata=1:reset=1",
            "-f",
            "null",
            "-",
        ],
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        check=True,
    )

    rms_db = None
    for line in result.stderr.splitlines():
        if "Overall RMS level dB" in line:
            try:
                rms_db = float(line.split(":")[-1].strip())
            except ValueError:
                rms_db = None
            break
        if "RMS level dB" in line and "Overall" not in line:
            try:
                rms_db = float(line.split(":")[-1].strip())
            except ValueError:
                rms_db = None
            break

    return rms_db


def check_mix_levels(path: Path, min_db: float = -36.0, max_db: float = -12.0) -> None:
    """Run astats to keep the underscore/dialogue mix within expected bounds."""
    rms_db = measure_rms_db(path)
    if rms_db is None:
        print(f"⚠️  Unable to parse RMS level for {path.name}")
        return

    if rms_db < min_db or rms_db > max_db:
        print(f"⚠️  Mix RMS {rms_db:.1f} dB outside target range ({min_db} .. {max_db}) for {path.name}")
    else:
        print(f"✅ Mix RMS {rms_db:.1f} dB for {path.name}")


def validate_mix_ratio(video: Path, underscore: Path, dialog_gain: float, underscore_gain: float) -> Optional[float]:
    """Validate the effective loudness ratio between dialogue (video) and underscore stems."""
    dialog_rms_db = measure_rms_db(video)
    underscore_rms_db = measure_rms_db(underscore)

    if dialog_rms_db is None or underscore_rms_db is None:
        print("⚠️  Unable to measure RMS for one of the stems; ratio check skipped.")
        return None

    dialog_linear = 10 ** (dialog_rms_db / 20.0)
    underscore_linear = 10 ** (underscore_rms_db / 20.0)

    adjusted_ratio = (underscore_linear * underscore_gain) / max(dialog_linear * dialog_gain, 1e-6)

    if abs(adjusted_ratio - TARGET_UNDERSCORE_RATIO) > RATIO_TOLERANCE:
        print(
            f"⚠️  Underscore/dialogue ratio {adjusted_ratio:.2f} outside tolerance "
            f"(target {TARGET_UNDERSCORE_RATIO:.2f} ± {RATIO_TOLERANCE:.2f})"
        )
    else:
        print(
            f"✅ Underscore/dialogue ratio {adjusted_ratio:.2f} within tolerance "
            f"(target {TARGET_UNDERSCORE_RATIO:.2f})"
        )

    return adjusted_ratio


def cut_segment(src: Path, start: float, end: Optional[float], dst: Path) -> None:
    args = ["-y", "-i", str(src)]
    if start:
        args.extend(["-ss", str(start)])
    if end is not None:
        args.extend(["-to", str(end)])
    args.extend(["-c", "copy", str(dst)])
    run_ffmpeg(args)


def load_shot_status(scene_id: str) -> Dict[str, Dict]:
    registry_path = ROOT / "REALRUNNER" / f"scene_{scene_id}_shot_status.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"Shot status registry missing: {registry_path}")
    return json.loads(registry_path.read_text()).get("shot_status", {})


def get_shot_path(status: Dict[str, Dict], shot_id: str) -> Path:
    entry = status.get(shot_id, {})
    candidate = entry.get("latest_video")
    if candidate and Path(candidate).exists():
        return Path(candidate)
    return ROOT / "atlas_output" / "nano_banana" / f"{shot_id}.mp4"


def build_segments(stitched: Path, seg1: Path, seg2: Path, seg3: Path) -> None:
    if not seg1.exists():
        cut_segment(stitched, 0, 14, seg1)
    if not seg3.exists():
        cut_segment(stitched, 33, None, seg3)
    if not seg2.exists():
        cut_segment(stitched, 14, 33, seg2)


def ensure_unique_shots(shot_ids: Iterable[str], context: str) -> None:
    seen = set()
    duplicates = set()
    for sid in shot_ids:
        if sid in seen:
            duplicates.add(sid)
        else:
            seen.add(sid)
    if duplicates:
        dup_list = ", ".join(sorted(duplicates))
        raise RuntimeError(f"Duplicate shots detected in {context}: {dup_list}")


def file_fingerprint(path: Path) -> str:
    actual = path.resolve()
    cached = _FINGERPRINT_CACHE.get(actual)
    if cached:
        return cached

    hasher = hashlib.sha256()
    with actual.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    _FINGERPRINT_CACHE[actual] = digest
    return digest


def remove_adjacent_duplicate_clips(clips: List[Path], context: str) -> List[Path]:
    cleaned: List[Path] = []
    last_fingerprint: Optional[str] = None

    for clip in clips:
        if not clip.exists():
            raise FileNotFoundError(f"Clip missing for duplicate check: {clip}")
        fingerprint = file_fingerprint(clip)
        if fingerprint == last_fingerprint:
            print(f"⚠️  Duplicate beat detected in {context}: {clip.name} – skipping second occurrence.")
            continue
        cleaned.append(clip)
        last_fingerprint = fingerprint

    return cleaned


def master_edit(
    scene_id: str,
    underscore: Path,
    dialog_gain: float,
    underscore_gain: float,
) -> Path:
    shot_status = load_shot_status(scene_id)

    title = ROOT / "title_card_latest.mp4"
    prelude_ids = [
        "004_door_mechanism",
        "004_clipboard_detail",
        "004_chen_closeup",
        "004_chen_enters",
    ]
    ensure_unique_shots(prelude_ids, "master prelude")
    prelude_shots = [get_shot_path(shot_status, shot_id) for shot_id in prelude_ids]
    prelude_shots = remove_adjacent_duplicate_clips(prelude_shots, "master prelude")

    stitched = ROOT / "stitched_scenes" / "scene_004_STITCHED.mp4"
    interior = ROOT / "REALRUNNER" / "scene_004_interiors_reordered.mp4"
    if not interior.exists():
        seg_dir = Path(tempfile.mkdtemp())
        seg1 = seg_dir / "seg1.mp4"
        seg2 = seg_dir / "seg2.mp4"
        seg3 = seg_dir / "seg3.mp4"
        build_segments(stitched, seg1, seg2, seg3)
        concat([seg1, seg3, seg2], interior)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        prepared: List[Path] = []

        title_prepped = temp_root / "title_low.mp4"
        ensure_audio(title, title_prepped)
        volume_adjust(title_prepped, title_prepped, 0.6)
        prepared.append(title_prepped)

        for src in prelude_shots:
            prepped = temp_root / f"{src.stem}_low.mp4"
            ensure_audio(src, prepped)
            volume_adjust(prepped, prepped, 0.6)
            prepared.append(prepped)

        concat(prepared + [interior], temp_root / "master_no_score.mp4")
        master_no_score = temp_root / "master_no_score.mp4"

        output = ROOT / "stitched_scenes" / f"scene_{scene_id}_SEQUENCE_MASTER_EDIT.mp4"
        if output.exists() or output.is_symlink():
            output.unlink()
        mix_underscore(
            master_no_score,
            underscore,
            output,
            dialog_gain=dialog_gain,
            underscore_gain=underscore_gain,
        )
        check_mix_levels(output)

        timestamped = output.with_name(output.stem + "_latest.mp4")
        if timestamped.exists():
            timestamped.unlink()
        output.replace(timestamped)
        if output.exists() or output.is_symlink():
            output.unlink()
        output.symlink_to(timestamped.name)

        return timestamped


def highlight_edit(
    scene_id: str,
    underscore: Path,
    dialog_gain: float,
    underscore_gain: float,
) -> Path:
    highlight = ROOT / "stitched_scenes" / f"scene_{scene_id}_SMART_MINUTE.mp4"
    shot_status = load_shot_status(scene_id)

    stitched = ROOT / "stitched_scenes" / "scene_004_STITCHED.mp4"
    seg1 = ROOT / "REALRUNNER" / "tmp_scene004_seg1.mp4"
    seg2 = ROOT / "REALRUNNER" / "tmp_scene004_seg2.mp4"
    seg3_full = ROOT / "REALRUNNER" / "tmp_scene004_seg3.mp4"
    build_segments(stitched, seg1, seg2, seg3_full)
    seg3_20 = ROOT / "REALRUNNER" / "tmp_scene004_seg3_20s.mp4"
    if not seg3_20.exists():
        cut_segment(seg3_full, 0, 20, seg3_20)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        highlight_ids = [
            "004_door_mechanism",
            "004_clipboard_detail",
            "004_chen_closeup",
            "004_chen_enters",
        ]
        ensure_unique_shots(highlight_ids, "highlight prelude")

        prepared: List[Path] = []
        title_prepped = temp_root / "title_low.mp4"
        ensure_audio(ROOT / "title_card_latest.mp4", title_prepped)
        volume_adjust(title_prepped, title_prepped, 0.6)
        prepared.append(title_prepped)

        for shot_id in highlight_ids:
            src = get_shot_path(shot_status, shot_id)
            prepped = temp_root / f"{src.stem}_low.mp4"
            ensure_audio(src, prepped)
            volume_adjust(prepped, prepped, 0.6)
            prepared.append(prepped)

        prepared = remove_adjacent_duplicate_clips(prepared, "highlight prelude")

        concat(prepared + [seg1, seg3_20], temp_root / "highlight_no_score.mp4")
        if highlight.exists() or highlight.is_symlink():
            highlight.unlink()
        mix_underscore(
            temp_root / "highlight_no_score.mp4",
            underscore,
            highlight,
            dialog_gain=dialog_gain,
            underscore_gain=underscore_gain,
        )
        check_mix_levels(highlight)

    return highlight


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart stitching for scene outputs")
    parser.add_argument("--scene", default="004", help="Scene identifier (default: 004)")
    parser.add_argument("--mode", choices=["master", "highlight"], default="master")
    parser.add_argument(
        "--underscore",
        type=str,
        default=str(ROOT / "REALRUNNER" / "horror_underscore_trimmed.mp3"),
        help="Path to underscore audio (default: REALRUNNER/horror_underscore_trimmed.mp3)",
    )
    parser.add_argument(
        "--dialog-gain",
        type=float,
        default=0.95,
        help="Gain multiplier for dialogue track (default: 0.95)",
    )
    parser.add_argument(
        "--underscore-gain",
        type=float,
        default=0.35,
        help="Gain multiplier for underscore track (default: 0.35)",
    )
    args = parser.parse_args()

    underscore_path = Path(args.underscore).expanduser()
    if not underscore_path.exists():
        raise FileNotFoundError(f"Underscore track not found: {underscore_path}")

    if args.mode == "master":
        output = master_edit(
            args.scene,
            underscore_path,
            dialog_gain=args.dialog_gain,
            underscore_gain=args.underscore_gain,
        )
        print(f"✅ Master edit ready: {output}")
    else:
        output = highlight_edit(
            args.scene,
            underscore_path,
            dialog_gain=args.dialog_gain,
            underscore_gain=args.underscore_gain,
        )
        print(f"✅ Highlight edit ready: {output}")


if __name__ == "__main__":
    main()
