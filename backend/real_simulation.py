"""EEG replay -> measured MANC rate model -> physical NeuroMechFly locomotion."""
import math
import numpy as np
from .manc_network import MeasuredDynamics
from .biomechanics import BiomechanicalFly

class RealSimulation:
    DT=.05                 # EEG replay seconds per dashboard update
    BODY_DT=.005           # 10x slow-motion neural/body clock, explicitly shown
    TRIAL_SECONDS=5.
    def __init__(self,graph,data):
        self.graph=graph;self.data=data;self.net=MeasuredDynamics(graph)
        self.body=BiomechanicalFly();self.mode='decoded';self.running=True;self.speed=1.
        self.reset(reset_body=False)

    def reset(self,reset_body=True):
        self.index=0;self.tick=0;self.sequence=0;self.elapsed=0.
        self.events=[];self.command='WAIT';self.hits=0;self.error=None;self.lesion=False
        self.target=dict(x=12.,y=6.,z=0.)
        self.net.reset()
        if reset_body:self.body.reset()
        self.body_state=self.body.state();self.target_reached=False
        self.response_path=[];self.response_turn=0.
        self.cut_turn=0.;self.cut_time=0.

    def next_trial(self):
        self.index=(self.index+1)%len(self.data['labels']);self.sequence+=1
        self.tick=0;self.command='WAIT';self.net.reset();self.net.lesion=self.lesion
        self.response_path=[];self.response_turn=0.

    def control(self,message):
        action=message.get('action')
        if action=='pause':self.running=False
        elif action=='play' and self.error is None:self.running=True
        elif action=='reset':self.reset()
        elif action=='next':self.next_trial()
        elif action=='mode' and message.get('value') in ('truth','decoded'):
            self.mode=message['value'];self.tick=0;self.command='WAIT';self.net.reset();self.net.lesion=self.lesion
            self.response_path=[];self.response_turn=0.
        elif action=='speed' and message.get('value') in (.5,1,2):self.speed=float(message['value'])
        elif action=='steering_gain' and message.get('value') in (1,1.5,2):self.body.steering_gain=float(message['value'])
        elif action=='lesion' and isinstance(message.get('value'),bool):
            self.lesion=message['value'];self.net.reset();self.net.lesion=self.lesion
            self.command='HOLD';self.response_path=[];self.response_turn=0.
            self.cut_turn=0.;self.cut_time=self.body_state['physics_time']

    def step(self):
        if not self.running:return
        t=self.tick*self.DT
        cls=int(self.data['labels' if self.mode=='truth' else 'predictions'][self.index])
        side=('L','R')[cls] if 2<=t<3.8 else None
        motor=self.net.step(side)
        normalized={s:motor[s]/self.graph.motor_scale for s in ('L','R')}
        # This is the ONLY input into the body. No class/label/side is passed.
        previous_heading=self.body_state['heading']
        if self.tick==40:self.response_path=[self.body_state['position']];self.response_turn=0.
        self.body_state=self.body.advance(normalized,self.BODY_DT)
        if self.lesion:
            drift=self.body_state['heading']-previous_heading
            self.cut_turn+=math.degrees(math.atan2(math.sin(drift),math.cos(drift)))
        if self.tick>=40:
            delta=self.body_state['heading']-previous_heading
            self.response_turn+=math.degrees(math.atan2(math.sin(delta),math.cos(delta)))
            self.response_path.append(self.body_state['position'])
        diff=motor['L']-motor['R']
        self.command='WAIT' if t<2 else 'HOLD' if abs(diff)<self.graph.motor_scale*.01 else 'LEFT' if diff>0 else 'RIGHT'
        if self.tick==80:
            self.events.insert(0,dict(trial=self.index+1,command=self.command,time=round(self.elapsed,1),
                left=motor['L'],right=motor['R'],heading_deg=math.degrees(self.body_state['heading']),turn_deg=self.response_turn,lesion=self.lesion))
            self.events=self.events[:8]
        p=self.body_state['position']
        if not self.target_reached and math.hypot(p[0]-self.target['x'],p[1]-self.target['y'])<.8:
            self.hits+=1;self.target_reached=True
        if self.body_state['upright']<.5:
            self.error='Physical fly lost upright posture. Reset to restart; no automatic teleportation.'
            self.running=False
        self.tick+=1;self.elapsed+=self.DT
        if self.tick>=100:self.next_trial()

    def payload(self):
        t=self.tick*self.DT;motor=self.net.motor_activity()
        normalized={s:float(motor[s]/self.graph.motor_scale) for s in ('L','R')}
        return dict(trial=self.index,sequence=self.sequence,time=round(t,3),elapsed=round(self.elapsed,2),
                    phase='ACQUIRE' if t<2 else 'INPUT' if t<2.6 else 'PROPAGATE' if t<3.4 else 'MOTOR' if t<4 else 'MOVE',
                    label=int(self.data['labels'][self.index]),prediction=int(self.data['predictions'][self.index]) if t>=2 else None,
                    confidence=float(self.data['confidence'][self.index]) if t>=2 else None,
                    activity=np.round(self.net.display_activity(),3).tolist(),motors=motor,motors_normalized=normalized,
                    leg_motors=self.net.leg_activity(),body=self.body_state,
                    fly=dict(x=self.body_state['position'][0],y=self.body_state['position'][1],heading=self.body_state['heading']),
                    path=self.body_state['path'],target=self.target,events=self.events,command=self.command,hits=self.hits,
                    response_path=self.response_path,response_turn_deg=self.response_turn,
                    steering_gain=self.body.steering_gain,
                    cut_turn_deg=self.cut_turn,cut_elapsed=self.body_state['physics_time']-self.cut_time if self.lesion else 0.,
                    distance=self.body_state['distance'],mode=self.mode,running=self.running,speed=self.speed,
                    lesion=self.lesion,error=self.error,body_time_scale=self.BODY_DT/self.DT,
                    input_body_id=self.graph.config['input_body_ids'][('L','R')[int(self.data['labels' if self.mode=='truth' else 'predictions'][self.index])]] if t>=2 else None)
