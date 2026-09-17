"""Check a running deployment: python scripts/check_server.py http://localhost:8501"""
import asyncio
import json
import sys
import urllib.request
from urllib.parse import urlsplit, urlunsplit

import websockets

async def check(base):
    with urllib.request.urlopen(base+'/health/ready',timeout=15) as response:
        assert json.load(response)['state']=='ready'
    parts=urlsplit(base)
    endpoint=urlunsplit(('wss' if parts.scheme=='https' else 'ws',parts.netloc,'/ws','',''))
    async with websockets.connect(endpoint,max_size=10_000_000,open_timeout=30) as ws:
        first=json.loads(await asyncio.wait_for(ws.recv(),30))
        for _ in range(80):
            state=json.loads(await asyncio.wait_for(ws.recv(),15))
            if state['body']['physics_time']>first['body']['physics_time']:
                assert state['body']['position']!=first['body']['position']
                assert state['error'] is None
                await ws.send(json.dumps({'action':'pause'}))
                print(json.dumps({'ready':True,'websocket':True,'physics_advances':True,'steering_gain':state['steering_gain']}))
                return
        raise RuntimeError('Physical clock did not advance')

if __name__=='__main__':
    asyncio.run(check((sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8501').rstrip('/')))
