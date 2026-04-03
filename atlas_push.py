import os, json, urllib.request, datetime

GALLERY_URL = os.getenv('ATLAS_GALLERY_URL', 'https://atlas-gallery.rumbletv64.workers.dev')
PUSH_SECRET = os.getenv('ATLAS_PUSH_SECRET', 'atlas-v30')

def push_render(name, url='', prompt='', type='RENDER', thumb='', local_path='', source='kling'):
    try:
        # If local_path provided and no url, upload to R2 first
        if local_path and not url:
            url = f'/api/media?path={local_path}'

        payload = json.dumps({
            'name': name,
            'url': url,
            'prompt': prompt[:200] if prompt else '',
            'type': type,
            'thumb': thumb,
            'source': source,  # 'kling' | 'higgsfield' | 'seedance' etc.
            'ts': datetime.datetime.now().isoformat()
        }).encode()
        
        req = urllib.request.Request(
            f'{GALLERY_URL}/push',
            data=payload,
            headers={'Content-Type': 'application/json', 'X-Push-Secret': PUSH_SECRET}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception as e:
        print(f'[GALLERY-PUSH] {name}: {e}')
        return False
