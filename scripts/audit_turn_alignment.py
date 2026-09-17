import sys,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.manc_network import MANCNetwork
from backend.eeg_decoder import prepare
from backend.real_simulation import RealSimulation
s=RealSimulation(MANCNetwork(),prepare()[0]);results=[];delta=0
for i in range(14400):
 if s.tick==40:delta=0
 previous=s.body_state['heading'];tick=s.tick;trial=s.index;pred=int(s.data['predictions'][trial])
 s.step();d=math.atan2(math.sin(s.body_state['heading']-previous),math.cos(s.body_state['heading']-previous))
 if tick>=40:delta+=math.degrees(d)
 if tick==99:results.append({'trial':trial+1,'prediction':pred,'turn_deg':round(delta,2),'match':delta>0 if pred==0 else delta<0})
print(json.dumps(results));(Path(__file__).resolve().parents[1]/'data/validation/decoded-turn-alignment.json').write_text(json.dumps(results,indent=2))

