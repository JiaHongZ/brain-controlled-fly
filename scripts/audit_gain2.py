from pathlib import Path
import sys,json,math,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.manc_network import MANCNetwork
from backend.eeg_decoder import prepare
from backend.real_simulation import RealSimulation
g=MANCNetwork();data,_=prepare();results={}
for mode in ['decoded','truth']:
 s=RealSimulation(g,data);s.mode=mode;events=[];minimum=1.;delta=0
 for i in range(14400):
  if s.tick==40:delta=0
  before=s.body_state['heading'];tick=s.tick;trial=s.index;prediction=int(data['predictions' if mode=='decoded' else 'labels'][trial]);s.step()
  assert not s.error,s.error;minimum=min(minimum,s.body_state['upright'])
  if tick>=40:delta+=math.degrees(math.atan2(math.sin(s.body_state['heading']-before),math.cos(s.body_state['heading']-before)))
  if tick==99:events.append(dict(trial=trial+1,drive=prediction,turn_deg=delta,match=delta>0 if prediction==0 else delta<0))
  if i%3600==3599:print(mode,'trials',s.sequence,flush=True)
 results[mode]=dict(gain=s.body.steering_gain,trials=len(events),minimum_upright=minimum,matches=sum(e['match'] for e in events),events=events)
(Path(__file__).resolve().parents[1]/'data/validation/gain2-full-replay.json').write_text(json.dumps(results,indent=2))
print({m:{k:v for k,v in x.items() if k!='events'} for m,x in results.items()},flush=True)
