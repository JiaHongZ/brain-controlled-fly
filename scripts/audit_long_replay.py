import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.manc_network import MANCNetwork
from backend.eeg_decoder import prepare
from backend.real_simulation import RealSimulation
data,metrics=prepare();graph=MANCNetwork();results={}
for mode in ('truth','decoded'):
    sim=RealSimulation(graph,data);sim.mode=mode;start=time.monotonic();minimum=1.;events=[]
    for i in range(14400):
        sim.step();minimum=min(minimum,sim.body_state['upright'])
        if sim.error:
            print('FAILED',mode,i,sim.error,flush=True);break
        if sim.tick==81:events.append(sim.events[0].copy())
        if i%1200==1199:print(mode,'trials',sim.sequence,'minimum upright',round(minimum,3),'wall',round(time.monotonic()-start,1),flush=True)
    results[mode]=dict(steps=i+1,sequence=sim.sequence,trial=sim.index,error=sim.error,minimum_upright=minimum,
                       final_position=sim.body_state['position'],physics_seconds=sim.body_state['physics_time'],events=events)
(Path(__file__).resolve().parents[1]/'data/validation/long-replay-results.json').write_text(json.dumps(results,indent=2))
print('FINISHED',flush=True)
