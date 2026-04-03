import os, json, base64, subprocess, urllib.request

os.environ['FAL_KEY'] = 'os.environ.get('FAL_KEY', '')'
import fal_client

PROJECT = '/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1'
SHOTS = [('001_010B', 10), ('001_011C', 10), ('001_012A', 18)]
POOL_KEYS = [
    '12cd8bf8-1599-4d40-80d5-bdd16d09edbf:e1308c1a518cfdf1b95c6cc7e8ca529a',
    'ef03d641-1122-422a-9d27-27158cc88ae6:43f285f4e5984b775a950eb0deaebc05',
    '8d1ca2fc-9064-4ba9-bd22-6f84ded1e6db:edd366cdb950b14a522da2268be6d423',
    'c7830c0c-4635-43c3-b2ee-23525cc5cc17:eeef1b4f196f366253931b41e78a19fe',
    '582c0d2b-b266-45ab-ba8b-b5e89f03acac:119a80ff6e56e84ccd74acd1350c26b7',
    '7e489f09-3797-4113-a5d4-386a2841eebc:be9498651dfc76373cc26b5a7d1f4daa',
    'aaa9e8a3-af55-4aca-8687-ffd1411deea7:71b92029c9bc960abe468fcc12501016',
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
