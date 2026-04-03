#!/usr/bin/env python3
"""Fix Scene 001 nano prompts — inject unique dialogue/action per shot to prevent duplicate frames."""
import json, shutil, time, re

project = 'victorian_shadows_ep1'
sp_path = f'/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{project}/shot_plan.json'

backup_path = f'{sp_path}.backup_nano_fix_{int(time.time())}'
shutil.copy2(sp_path, backup_path)
print(f'Backup: {backup_path}')

with open(sp_path) as f:
    sp = json.load(f)

# Scene 001 shot-specific action direction (from screenplay beats)
SHOT_ACTIONS = {
    "001_001A": "vast foyer, morning light streams through stained glass, dust sheets cover furniture, dark chandelier looms above",
    "001_002B": "Eleanor pushes open heavy oak doors, morning sunlight floods in behind her, she pauses scanning the decayed grandeur",
    "001_003B": "Eleanor steps cautiously across marble floor, her heels echo, she touches a dust sheet revealing ornate furniture beneath",
    "001_004B": "Thomas stands at the top of the staircase, hand trailing the banister, looking down at Eleanor with guarded expression",
    "001_005B": "Eleanor looks up at Thomas on the stairs, extends her hand formally, professional smile, briefcase in other hand",
    "001_006B": "Eleanor opens her briefcase on a console table, pulls out documents, gestures at the papers with urgency",
    "001_007B": "Thomas descends the staircase slowly, one hand on banister, other hand gestures dismissively at the house around them",
    "001_008B": "Eleanor follows Thomas through the foyer, notepad in hand, writing as she walks, glancing at items on the walls",
    "001_009B": "Thomas stops abruptly, turns to face Eleanor, one hand raised palm-up, other hand touches the wall beside him",
    "001_010B": "Eleanor plants her feet firmly, chin up, meeting Thomas's gaze directly, documents held against her chest",
    "001_011C": "Thomas turns away, face half in shadow, looks toward a hallway leading deeper into the house, voice drops to a whisper",
    "001_012A": "Thomas crosses to a large painting on the wall, reaches out as if to touch it, then pulls his hand back, jaw set",
}

fixes = 0
for shot in sp.get('shots', []):
    if shot.get('scene_id') != '001':
        continue
    sid = shot['shot_id']
    if sid not in SHOT_ACTIONS:
        continue

    action = SHOT_ACTIONS[sid]
    nano = shot.get('nano_prompt', '') or ''

    # Replace generic "Character action: Character experiences..." with specific action
    old_action_match = re.search(r'Character action:\s*Character experiences[^.]*\.?', nano)
    if old_action_match:
        nano = nano.replace(old_action_match.group(0), f'Character action: {action}.')
        fixes += 1
        print(f'[NANO] {sid}: replaced generic action with: {action[:80]}')
    elif 'Character action:' not in nano:
        # No action at all — inject before the first colon-separated section
        # Find the shot type description and append after it
        nano = nano.rstrip() + f' Character action: {action}.'
        fixes += 1
        print(f'[NANO] {sid}: injected action: {action[:80]}')
    else:
        print(f'[NANO] {sid}: already has specific action, skipping')

    shot['nano_prompt'] = nano
    # Also update nano_prompt_final if it exists
    if shot.get('nano_prompt_final'):
        nf = shot['nano_prompt_final']
        old_nf_match = re.search(r'Character action:\s*Character experiences[^.]*\.?', nf)
        if old_nf_match:
            shot['nano_prompt_final'] = nf.replace(old_nf_match.group(0), f'Character action: {action}.')

with open(sp_path, 'w') as f:
    json.dump(sp, f, indent=2)

print(f'\nDone: {fixes} nano prompt fixes applied')
print(f'Each shot now has unique action direction — no more duplicate frames')
