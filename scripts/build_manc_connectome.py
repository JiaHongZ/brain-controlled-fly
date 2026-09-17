"""Prepare a measured MANC network. No generated neurons or synthetic edges."""
from pathlib import Path
import sys,json,hashlib,urllib.request
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix,save_npz
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROOT=Path(__file__).resolve().parents[1]
DN_IDS={'L':10126,'R':10118}  # MANC v1.0 DNa02, checked against type and rootSide
MOTOR_URL='https://cdn.elifesciences.org/articles/96084/elife-96084-supp6-v1.csv'

def build(progress=print):
    raw=ROOT/'data/manc/raw';out=ROOT/'data/manc';out.mkdir(parents=True,exist_ok=True)
    if not (raw/'traced-connections.csv').exists():
        from scripts.download_manc import download
        download(progress)
    motor_path=raw/'leg-motor-neurons.csv'
    if not motor_path.exists():
        with urllib.request.urlopen(MOTOR_URL,timeout=60) as response:motor_path.write_bytes(response.read())
    progress('Reading measured MANC neurons, synapses, and published leg motor annotations…')
    traced=pd.read_csv(raw/'traced-neurons.csv')
    props=pd.read_feather(raw/'neuron-properties.feather').set_index('bodyId')
    E=pd.read_csv(raw/'traced-connections.csv')
    leg=pd.read_csv(motor_path).set_index('bodyid')
    ids=traced.bodyId.to_numpy(dtype=np.int64)
    idx={int(n):i for i,n in enumerate(ids)}
    P=props.loc[ids]
    for side,body in DN_IDS.items():
        row=P.loc[body]
        assert row['type']=='DNa02' and row.rootSide==('LHS' if side=='L' else 'RHS')
    excluded_motor_ids=sorted(int(b) for b in leg.index if int(b) not in idx)
    annotation_count=len(leg)
    # The publication table also includes cells absent from this traced adjacency
    # release. Do not invent their connections or silently remap their body IDs.
    leg=leg.loc[leg.index.isin(idx)]
    # Use ALL traced neurons for simulation, not just the displayed subgraph.
    # The standard >=5 synapse cutoff removes only weak measured edges.
    original_edges=len(E);E=E[E.weight>=5]
    sources=E.bodyId_pre.map(idx).to_numpy(dtype=np.int32)
    targets=E.bodyId_post.map(idx).to_numpy(dtype=np.int32)
    counts=E.weight.to_numpy(dtype=np.float64)
    nt=P.predictedNt.fillna('unknown').to_numpy()
    signs=np.where(np.isin(nt,['gaba','glutamate']),-1.,1.)
    incoming=np.bincount(targets,weights=counts,minlength=len(ids))
    W=csr_matrix((counts*signs[sources]/np.maximum(incoming[targets],1),(targets,sources)),shape=(len(ids),len(ids)))
    save_npz(out/'measured_network.npz',W)
    np.savez_compressed(out/'measured_edges.npz',source=sources,target=targets,synapse_count=counts.astype(np.int32))
    meta=[]
    for i,body in enumerate(ids):
        n=P.loc[body]
        side={'LHS':'L','RHS':'R'}.get(n.rootSide) or {'LHS':'L','RHS':'R'}.get(n.somaSide,'U')
        position=None;coordinate_field=None
        for field in ('position','somaLocation','rootPosition','avgLocation'):
            p=n[field]
            if isinstance(p,(list,np.ndarray)) and len(p)==3 and np.isfinite(p).all():
                position=[float(v) for v in p];coordinate_field=field;break
        is_motor=int(body) in leg.index
        if is_motor:
            m=leg.loc[int(body)];side={'LHS':'L','RHS':'R'}[m.soma_side]
            motor_leg=side+{'fl':'F','ml':'M','hl':'H'}[m.subclass]
        else:motor_leg=None
        meta.append(dict(node_id=str(body),index=i,cell_type=str(n.type or ''),cell_class=str(n['class'] or ''),
                         region='motor' if is_motor else 'descending' if n['class']=='descending neuron' else 'sensory' if 'sensory' in str(n['class']) else 'VNC',
                         side=side,predicted_nt=str(nt[i]),nt_probability=float(n.predictedNtProb) if pd.notna(n.predictedNtProb) else None,
                         raw_position=position,coordinate_field=coordinate_field,
                         motor_leg=motor_leg,muscle_target=str(leg.loc[int(body)].target) if is_motor else None))
    (out/'all_neurons.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
    configuration=dict(dataset='MANC v1.0',neuron_count=len(ids),original_edge_count=original_edges,
                       edge_count=len(E),synapse_count=int(counts.sum()),min_synapse_count=5,
                       input_body_ids=DN_IDS,input_indices={s:idx[b] for s,b in DN_IDS.items()},
                       motor_indices={s:[idx[int(b)] for b in leg.index if leg.loc[b].soma_side==('LHS' if s=='L' else 'RHS')] for s in ['L','R']},
                       leg_motor_indices={s+part:[n['index'] for n in meta if n['motor_leg']==s+part] for s in ['L','R'] for part in ['F','M','H']},
                       motor_annotation=dict(url=MOTOR_URL,sha256=hashlib.sha256(motor_path.read_bytes()).hexdigest(),count=len(leg),
                                             table_count=annotation_count,excluded_absent_from_traced_release=excluded_motor_ids),
                       dynamics_assumptions=dict(model='delayed rectified rate network',tau_seconds=.025,delay_seconds=.010,
                       step_seconds=.005,recurrent_gain=.92,normalization='absolute incoming retained synapse count',
                       transmitter_sign='predicted ACh +; GABA/Glut -; unknown + (assumed, not measured functional sign)'),
                       eeg_mapping='Engineered: LEFT/RIGHT MI drives left/right identified DNa02. Not a measured cross-species mapping.')
    (out/'network_config.json').write_text(json.dumps(configuration,indent=2),encoding='utf-8')
    progress(f'MANC ready: {len(ids):,} real neurons, {len(E):,} measured edges; {len(leg)} published leg MNs')
    return configuration

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    build()
