"""Measured MANC structure; explicitly assumed rate dynamics and EEG interface."""
from collections import deque
from pathlib import Path
import json,csv
import numpy as np
from scipy.sparse import load_npz

ROOT=Path(__file__).resolve().parents[1]

class MANCNetwork:
    def __init__(self,folder=ROOT/'data/manc'):
        self.folder=Path(folder)
        self.config=json.loads((self.folder/'network_config.json').read_text(encoding='utf-8'))
        self.neurons=json.loads((self.folder/'all_neurons.json').read_text(encoding='utf-8'))
        self.W=load_npz(self.folder/'measured_network.npz').tocsr()
        self.inputs=self.config['input_indices']
        self.motors={s:np.array(v,dtype=int) for s,v in self.config['motor_indices'].items()}
        self.legs={s:np.array(v,dtype=int) for s,v in self.config['leg_motor_indices'].items()}
        with np.load(self.folder/'measured_edges.npz') as data:
            self.sources=data['source'];self.targets=data['target'];self.counts=data['synapse_count']
        self.calibrate_and_select_view()

    def calibrate_and_select_view(self):
        responses={};rates={};traces={}
        for side in ('L','R'):
            model=MeasuredDynamics(self);traces[side]=[]
            for step in range(100):
                model.step(side)
                traces[side].append(model.motor_activity())
            responses[side]=model.x.copy();rates[side]=model.motor_activity()
        # One global readout scale, calibrated from isolated DN stimulation;
        # no EEG test labels/predictions or behavior targets enter calibration.
        self.motor_scale=max(max(r.values()) for r in rates.values())
        if self.motor_scale<=1e-12:raise RuntimeError('Measured network has no leg motor response')
        self.calibration=dict(method='0.5 s unit DNa02 current, one side at a time; shared motor scaling',
                              raw_motor_rates=rates,global_motor_scale=self.motor_scale,
                              input_body_ids=self.config['input_body_ids'],traces=traces)
        salience=np.maximum(responses['L'],responses['R'])
        mandatory=set(self.inputs.values())|set(np.concatenate(list(self.motors.values())).tolist())
        available={i for i,n in enumerate(self.neurons) if n['raw_position'] is not None}
        selected=(mandatory&available)
        for i in np.argsort(salience)[::-1]:
            if int(i) in available:selected.add(int(i))
            if len(selected)>=1800:break
        self.view_indices=np.array(sorted(selected),dtype=int)
        # Individual display normalization exposes weak downstream activity;
        # raw activity remains available in readouts and the scientific record.
        self.view_scale=np.maximum(salience[self.view_indices],self.motor_scale*.2)
        map_index={int(i):j for j,i in enumerate(self.view_indices)}
        positions=np.array([self.neurons[i]['raw_position'] for i in self.view_indices])
        center=np.median(positions,axis=0)
        scale=max(np.ptp(positions[:,0]),np.ptp(positions[:,2]))/4.3
        self.nodes=[]
        for j,i in enumerate(self.view_indices):
            n=dict(self.neurons[i]);p=(positions[j]-center)/scale
            # Source x is lateral, z runs along VNC, y is depth. Common affine only.
            n.update(x=float(p[0]),y=float(p[2]),z=float(-p[1]),activity_display_scale=float(self.view_scale[j]))
            self.nodes.append(n)
        mask=np.isin(self.sources,self.view_indices)&np.isin(self.targets,self.view_indices)
        candidates=np.flatnonzero(mask)
        # Display only strongest 20k measured edges; full dynamics uses 1.36M.
        keep=candidates[np.argsort(self.counts[candidates],kind='stable')[-20000:]]
        self.edges=[dict(source=map_index[int(self.sources[k])],target=map_index[int(self.targets[k])],
                         source_body_id=self.neurons[int(self.sources[k])]['node_id'],
                         target_body_id=self.neurons[int(self.targets[k])]['node_id'],
                         weight=int(self.counts[k]),synapse_count=int(self.counts[k])) for k in keep]
        (self.folder/'calibration.json').write_text(json.dumps(self.calibration,indent=2),encoding='utf-8')
        self.write_display_csvs()

    def write_display_csvs(self):
        folder=self.folder.parent/'connectome';folder.mkdir(exist_ok=True)
        with (folder/'nodes.csv').open('w',newline='',encoding='utf-8') as f:
            keys=['node_id','cell_type','region','x','y','z','side','cell_class','predicted_nt','coordinate_field']
            writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(self.nodes)
        with (folder/'edges.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['source','target','weight','synapse_count']);writer.writeheader()
            writer.writerows(dict(source=e['source_body_id'],target=e['target_body_id'],weight=e['weight'],synapse_count=e['synapse_count']) for e in self.edges)
        (folder/'provenance.json').write_text(json.dumps(dict(dataset='MANC v1.0',role='visualization subset only',
            synthetic_edges=False,full_dynamics='../manc/measured_network.npz',
            display_nodes=len(self.nodes),display_edges=len(self.edges)),indent=2),encoding='utf-8')

    def payload(self):
        return dict(nodes=self.nodes,edges=self.edges,provenance=self.config,
                    view=dict(display_nodes=len(self.nodes),display_edges=len(self.edges),
                              selection='All matched leg MNs + DNa02 + strongest model responders; coordinates from MANC metadata',
                              edge_selection='Strongest measured edges within display subset; visualization only'),
                    calibration=self.calibration)

class MeasuredDynamics:
    DT=.005
    def __init__(self,graph):self.graph=graph;self.reset()
    def reset(self):
        self.x=np.zeros(self.graph.W.shape[0]);self.history=deque([self.x.copy(),self.x.copy()],maxlen=2)
        self.lesion=False
    def step(self,side=None,dose=1.):
        # Connectivity/sign conventions are fixed; no direction-specific weights.
        incoming=np.zeros_like(self.x) if self.lesion else self.graph.W@self.history[0]
        target=.92*incoming
        if side in self.graph.inputs:target[self.graph.inputs[side]]+=dose
        alpha=np.exp(-self.DT/.025)
        self.x=alpha*self.x+(1-alpha)*np.clip(target,0,1)
        self.history.append(self.x.copy())
        return self.motor_activity()
    def motor_activity(self):return {s:float(self.x[v].mean()) for s,v in self.graph.motors.items()}
    def leg_activity(self):return {s:float(self.x[v].mean()) for s,v in self.graph.legs.items()}
    def display_activity(self):return np.clip(self.x[self.graph.view_indices]/self.graph.view_scale,0,1)
