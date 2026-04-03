import os, json, base64, subprocess, urllib.request

os.environ['FAL_KEY'] = '6c394797-d2ed-4238-a303-7b1179a0aaf5:ccce2ccede50e31794c205aad4439ccc'
import fal_client

PROJECT = '/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1'
SHOTS = [('001_010B', 10), ('001_011C', 10), ('001_012A', 18)]
POOL_KEYS = [
    '6c394797-d2ed-4238-a303-7b1179a0aaf5:ccce2ccede50e31794c205aad4439ccc',
    '5fe81578-ca41-418e-aa1a-1d62ada97f0e:4894e489d4230008f1c2ad482882a29f',
    'd6d674e6-a090-403e-b6e8-24334394290f:d4e68a53c7881707e3815eb75bb76dc2',
]
key_idx = 0

with open(f'{PROJECT}/shot_plan.json') as f:
    sp = json.load(f)
shot_map = {s['shot_id']: s for s in sp['shots']}

for shot_id, target_dur in SHOTS:
    shot = shot_map[shot_id]
    frame_path = f'{PROJECT}/first_frames/{shot_id}.jpg'
    out_path = f'{PROJECT}/videos/{shot_id}.mp4'
    with open(frame_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    img_url = 'data:image/jpeg;base64,' + b64
    ltx = shot.get('ltx_motion_prompt', '')[:1800]
    neg = shot.get('negative_prompt', 'blurry, distorted face, morphing')
    VALID = [6, 8, 10, 12, 14, 16, 18, 20]
    api_dur = min((d for d in VALID if d >= target_dur), default=20)
    print(f'{shot_id}: generating {api_dur}s...')
    for attempt in range(len(POOL_KEYS)):
        os.environ['FAL_KEY'] = POOL_KEYS[(key_idx + attempt) % len(POOL_KEYS)]
        try:
            result = fal_client.run('fal-ai/ltx-2.3/image-to-video/fast', arguments={
                'image_url': img_url, 'prompt': ltx, 'negative_prompt': neg,
                'duration': api_dur, 'aspect_ratio': '16:9'
            })
            vid_url = result.get('video', {}).get('url', '')
            if vid_url:
                urllib.request.urlretrieve(vid_url, out_path)
                sz = os.path.getsize(out_path)
                dur_out = subprocess.check_output(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',out_path], text=True).strip()
                print(f'  OK: {dur_out}s, {sz} bytes')
                key_idx = (key_idx + attempt) % len(POOL_KEYS)
                break
        except Exception as e:
            err = str(e)
            if '403' in err or 'balance' in err.lower() or 'locked' in err.lower():
                print(f'  Key {attempt} exhausted, rotating...')
                continue
            print(f'  ERROR: {err[:150]}')
            break
