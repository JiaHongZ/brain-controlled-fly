"""Launch: python app.py → http://localhost:8501. All UI assets are local."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import threading
import time
import webbrowser
import sys
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

ROOT=Path(__file__).resolve().parent
status={'state':'loading','message':'Preparing public EEG…'}
resources={}
worker_lock=threading.Lock()

def prepare():
    if not worker_lock.acquire(blocking=False): return
    try:
        status.update(state='loading',message='Loading connectome…')
        from backend.manc_network import MANCNetwork
        from backend.biomechanics import BiomechanicalFly
        from backend.eeg_decoder import prepare as prepare_eeg
        if not (ROOT/'data/manc/network_config.json').exists():
            from scripts.download_manc import download
            from scripts.build_manc_connectome import build
            download(lambda message:status.update(message=message))
            build(lambda message:status.update(message=message))
        status.update(message='Loading 23,188 measured MANC neurons and synapses…')
        resources['graph']=MANCNetwork()
        data,report=prepare_eeg(progress=lambda message: status.update(message=message))
        resources.update(data=data,report=report)
        status.update(message='Compiling micro-CT NeuroMechFly body in MuJoCo…')
        resources['body_geometry']=BiomechanicalFly().geometry()
        status.update(state='ready',message='Real EEG + measured MANC + MuJoCo body ready')
    except Exception as exc:
        import traceback
        traceback.print_exc()
        status.update(state='error',message=str(exc))
    finally:
        worker_lock.release()

@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=prepare,daemon=True).start()
    yield

app=FastAPI(title='Brain-Controlled Digital Fly',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')

@app.get('/')
def home(): return FileResponse(ROOT/'frontend/index.html')

@app.get('/api/status')
def get_status(): return status

@app.get('/health/ready')
def readiness():
    return JSONResponse(status_code=200 if status['state']=='ready' else 503,content=status)

@app.post('/api/retry')
def retry():
    if status['state']=='error': threading.Thread(target=prepare,daemon=True).start()
    return status

def ready():
    if status['state']!='ready': raise HTTPException(503,status['message'])

@app.get('/api/bootstrap')
def bootstrap():
    ready()
    return dict(graph=resources['graph'].payload(),metrics=resources['report'],body_geometry=resources['body_geometry'])

@app.get('/api/trials/{index}')
def trial(index:int):
    ready()
    data=resources['data']
    if not 0<=index<len(data['labels']): raise HTTPException(404,'Unknown trial')
    # Eight display channels; inference uses all 22 EEG channels.
    ids=[0,2,7,9,11,14,16,19]
    return dict(index=index,signals=data['signals'][index,ids,::2].round(3).tolist(),
                channels=[resources['report']['channels'][i] for i in ids],sample_rate=125,
                artifact=bool(data['artifacts'][index]))

@app.websocket('/ws')
async def websocket(ws:WebSocket):
    await ws.accept()
    if status['state']!='ready':
        await ws.close(code=1013); return
    from backend.real_simulation import RealSimulation
    sim=await asyncio.to_thread(RealSimulation,resources['graph'],resources['data'])
    queue=asyncio.Queue(maxsize=100)
    async def receive():
        while True:
            msg=await ws.receive_json()
            if isinstance(msg,dict): await queue.put(msg)
    listener=asyncio.create_task(receive())
    accumulator=0; last=time.monotonic()
    try:
        while not listener.done():
            while not queue.empty(): sim.control(queue.get_nowait())
            now=time.monotonic()
            accumulator+=min(now-last,.2)*sim.speed; last=now
            while accumulator>=sim.DT:
                await asyncio.to_thread(sim.step); accumulator-=sim.DT
            await ws.send_json(sim.payload())
            await asyncio.sleep(.05)
    except (WebSocketDisconnect,RuntimeError,ConnectionError): pass
    finally:
        listener.cancel()
        try: await listener
        except (asyncio.CancelledError,WebSocketDisconnect,RuntimeError): pass

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default=os.getenv('HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.getenv('PORT','8501')))
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if sys.platform=='win32':
        # Selector loop avoids noisy Proactor socket-shutdown errors when a tab closes.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if not args.no_browser:
        timer=threading.Timer(1.5,lambda:webbrowser.open(f'http://localhost:{args.port}'))
        timer.daemon=True; timer.start()
    uvicorn.run(app,host=args.host,port=args.port,log_level='info')
