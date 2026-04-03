#!/usr/bin/env python3
import re, os, json
from pathlib import Path

base = Path('/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM')
runner = (base / 'atlas_universal_runner.py').read_text()
tools_dir = base / 'tools'

print("=== ERR-01: Video path lookup ===")
hits = [l.strip() for l in runner.splitlines() if 'all_videos.get' in l or 'ERR-01' in l]
for h in hits[:5]: print(h)

print("\n=== ERR-02: Florence-2 calls ===")
hits = [l.strip() for l in runner.splitlines() if 'florence_calls' in l]
for h in hits[:5]: print(h)

print("\n=== ERR-03: Learning log path ===")
log_py = tools_dir / 'atlas_learning_log.py'
if log_py.exists():
    for i, l in enumerate(log_py.read_text().splitlines()[:50]):
        if 'jsonl' in l or 'log_file' in l or '__file__' in l:
            print(f"  line {i+1}: {l.strip()}")
else:
    print("  NOT FOUND")

print("\n=== ERR-04/P4: Seedance cost tracking ===")
hits = [l.strip() for l in runner.splitlines() if 'seedance_cost' in l or 'seedance_calls' in l or '_track_cost("seedance")' in l]
for h in hits[:5]: print(h or 'NONE FOUND')

print("\n=== ERR-09: Run flags in consciousness state ===")
hits = [l.strip() for l in runner.splitlines() if 'run_flags' in l or 'video_model' in l or 'run_mode' in l]
for h in hits[:5]: print(h or 'NONE FOUND')

print("\n=== CURRENT VERSION ===")
for l in runner.splitlines()[:20]:
    if 'V29' in l or 'Version' in l or 'version' in l: print(l.strip())

print("\n=== REWARD LEDGER ANALYSIS ===")
ledger = base / 'pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl'
entries = [json.loads(l) for l in ledger.read_text().strip().splitlines()]
print(f"Total entries: {len(entries)}")
print(f"Unique I-scores: {set(round(e['I'],2) for e in entries[-10:])}")
print(f"Unique V-scores: {set(round(e['V'],2) for e in entries[-10:])}")
print(f"Unique C-scores: {set(round(e['C'],2) for e in entries[-10:])}")
print(f"Latest run verdicts: {[(e['shot_id'], e['verdict'], e['V']) for e in entries[-5:]]}")

print("\n=== VIDEO FILES PRODUCED ===")
import subprocess
vdir = base / 'pipeline_outputs/victorian_shadows_ep1/videos_kling_lite'
sdir = base / 'pipeline_outputs/victorian_shadows_ep1/videos_seedance_lite'
kv = list(vdir.glob('multishot_g*.mp4'))
sv = list(sdir.glob('*seedance*.mp4'))
print(f"Kling multishot videos: {len(kv)} — {[f.name for f in sorted(kv)]}")
print(f"Seedance videos: {len(sv)} — {[f.name for f in sorted(sv)]}")

print("\n=== FULL FILM FILES ===")
pdir = base / 'pipeline_outputs/victorian_shadows_ep1'
for f in sorted(pdir.glob('*.mp4'), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
    mb = f.stat().st_size / (1024*1024)
    print(f"  {f.name} — {mb:.1f}MB")
