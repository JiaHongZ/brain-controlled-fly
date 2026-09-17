from pathlib import Path
import sys,time,json,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.biomechanics import BiomechanicalFly
from backend.manc_network import MANCNetwork,MeasuredDynamics
g=MANCNetwork();body=BiomechanicalFly();results={}
for side,lesion in [(None,False),('L',False),('R',False),('L',True),('R',True)]:
    body.reset();net=MeasuredDynamics(g);net.lesion=lesion;start=time.monotonic()
    for i in range(200):
        m=net.step(side)
        body.advance({s:m[s]/g.motor_scale for s in ['L','R']},.005)
    state=body.state();key=str(side)+('-lesion' if lesion else '')
    results[key]=dict(position=state['position'],heading_deg=math.degrees(state['heading']),upright=state['upright'],motors=net.motor_activity(),signals=state['signals'])
    print(key,json.dumps(results[key]),'wall',time.monotonic()-start,flush=True)
(Path(__file__).resolve().parents[1]/'data/validation/real-chain-probe.json').write_text(json.dumps(results,indent=2))
