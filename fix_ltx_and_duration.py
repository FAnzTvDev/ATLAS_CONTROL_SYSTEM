#!/usr/bin/env python3
"""Fix Scene 001 LTX motion prompts (remove stillness stacking) and dialogue duration protection."""
import json, shutil, time, re, sys

project = 'victorian_shadows_ep1'
sp_path = f'/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{project}/shot_plan.json'

# Backup first
backup_path = f'{sp_path}.backup_ltx_fix_{int(time.time())}'
shutil.copy2(sp_path, backup_path)
print(f'Backup: {backup_path}')

with open(sp_path) as f:
    sp = json.load(f)

fixes_duration = 0
fixes_ltx = 0

for shot in sp.get('shots', []):
    if shot.get('scene_id') != '001':
        continue
    sid = shot['shot_id']

    # === FIX 1: Dialogue duration protection ===
    dialogue = shot.get('dialogue_text', '') or shot.get('dialogue', '')
    if dialogue:
        words = len(dialogue.split())
        min_needed = round(words / 2.3, 1) + 1.5
        old_dur = shot.get('duration', 0)
        if old_dur < min_needed:
            shot['duration'] = min_needed
            shot['duration_seconds'] = min_needed
            shot['ltx_duration_seconds'] = min_needed
            shot['_dialogue_protected'] = True
            fixes_duration += 1
            print(f'[DUR] {sid}: {old_dur}s -> {min_needed}s ({words} words need {min_needed}s)')

    # === FIX 2: Remove triple-stacked static/locked/zero movement from LTX ===
    ltx = shot.get('ltx_motion_prompt', '')
    original_ltx = ltx

    # Remove redundant static commands that cause freezing
    ltx = re.sub(r'static camera, no movement, detail focus\.\s*', '', ltx, count=2)
    ltx = re.sub(r'static camera, detail focus\.\s*', '', ltx)
    ltx = re.sub(r'locked camera, zero movement:\s*', '', ltx)

    # For non-dialogue shots: inject actual motion from nano_prompt
    if not dialogue and ('static hold' in ltx or ltx.strip() == '' or 'static camera' in ltx):
        nano = shot.get('nano_prompt', '') or shot.get('nano_prompt_final', '') or ''
        action_match = re.search(r'Character action:\s*(.+?)(?:\.|$)', nano)
        if action_match:
            char_action = action_match.group(1).strip()
            if char_action:
                ltx = re.sub(r'0-\d+s static hold,?\s*', f'0-2s {char_action}, ', ltx, count=1)

    # For dialogue shots: reduce static hold from 3s to 1s so performance starts faster
    if dialogue:
        ltx = re.sub(r'0-3s static hold,', '0-1s settle,', ltx)
        ltx = re.sub(r'0-2s static hold,', '0-1s settle,', ltx)

    # Strip stale Kodak/film stock refs
    ltx = re.sub(r':\s*Kod[^:]*:', ':', ltx)

    # Clean double colons/spaces
    ltx = re.sub(r':\s*:', ':', ltx)
    ltx = re.sub(r'\s{2,}', ' ', ltx)

    if ltx != original_ltx:
        shot['ltx_motion_prompt'] = ltx
        fixes_ltx += 1
        print(f'[LTX] {sid}: motion prompt cleaned ({len(original_ltx)} -> {len(ltx)} chars)')

# Save
with open(sp_path, 'w') as f:
    json.dump(sp, f, indent=2)

print(f'\nDone: {fixes_duration} duration fixes, {fixes_ltx} LTX motion fixes')
print(f'Shot plan saved to {sp_path}')
