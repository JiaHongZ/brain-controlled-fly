"""Official BNCI2014_001 MATLAB archive (same source used by MOABB).

Training = A01T; held-out evaluation = A01E. No synthesized EEG fallback.
"""
from pathlib import Path
import hashlib
import json
import time
import urllib.request
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ['Fz','FC3','FC1','FCz','FC2','FC4','C5','C3','C1','Cz','C2','C4','C6','CP3','CP1','CPz','CP2','CP4','P1','Pz','P2','POz']
BASES = ['https://lampx.tugraz.at/~bci/database/001-2014/', 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/']

def download_file(name, destination, progress=print):
    if destination.exists():
        try:
            loadmat(destination,variable_names=['data'])['data']
            return
        except Exception:
            progress(f'Invalid cached {name}; downloading a fresh official copy…')
    errors = []
    for base in BASES:
        temp = destination.with_suffix('.part')
        try:
            progress(f'Downloading {name} from public BNCI archive…')
            from .download import download_ranges
            if download_ranges(base+name,temp,progress):
                loadmat(temp,variable_names=['data'])['data']
                temp.replace(destination)
                return
            req = urllib.request.Request(base+name,headers={'User-Agent':'BrainControlledFly/1.0 (research demo)'})
            with urllib.request.urlopen(req,timeout=45) as r, temp.open('wb') as f:
                total = int(r.headers.get('Content-Length',0)); downloaded=0; last=0
                while chunk := r.read(1024*256):
                    f.write(chunk); downloaded += len(chunk)
                    if time.monotonic()-last>1:
                        progress(f'Downloading {name}: {downloaded/1e6:.1f} MB'+(f' / {total/1e6:.1f} MB' if total else ''))
                        last=time.monotonic()
            # Reject HTTP error pages before committing the cache.
            loadmat(temp,variable_names=['data'])['data']
            temp.replace(destination)
            return
        except Exception as exc:
            errors.append(f'{base}: {exc}')
            temp.unlink(missing_ok=True)
    raise RuntimeError('Public EEG download failed. Retry, or place A01T.mat and A01E.mat in data/eeg/raw. '+ '; '.join(errors))

def load_session(path):
    data = loadmat(path,simplify_cells=True)['data']
    trials, labels, artifacts = [],[],[]
    for run in np.asarray(data,dtype=object).ravel():
        if not isinstance(run,dict) or not len(np.atleast_1d(run.get('trial',[]))):
            continue
        fs = int(run['fs'])
        if fs != 250:
            raise ValueError(f'Expected 250 Hz, got {fs}')
        starts = np.atleast_1d(run['trial']).astype(int)-1
        ys = np.atleast_1d(run['y']).astype(int)
        flags = np.atleast_1d(run.get('artifacts',np.zeros(len(ys)))).astype(int)
        for start,label,flag in zip(starts,ys,flags):
            if label not in (1,2):
                continue
            # In this dataset trial onset precedes MI cue by 2 seconds.
            epoch = np.asarray(run['X'][start+2*fs:start+6*fs,:22],float).T * 1e-6
            if epoch.shape != (22,1000) or not np.isfinite(epoch).all():
                raise ValueError('Malformed or truncated EEG trial')
            trials.append(epoch); labels.append(label-1); artifacts.append(int(flag))
    if not trials:
        raise ValueError('No left/right trials in archive')
    return np.stack(trials),np.array(labels),np.array(artifacts)

def load_public_data(folder=ROOT/'data/eeg',progress=print):
    raw = Path(folder)/'raw'
    raw.mkdir(parents=True,exist_ok=True)
    for name in ['A01T.mat','A01E.mat']:
        download_file(name,raw/name,progress)
    progress('Reading real A01 training and evaluation sessions…')
    provenance = dict(dataset='BNCI2014_001 / BCI Competition IV 2a', subject='A01',
                      source=BASES[0], training='A01T',evaluation='A01E',
                      sampling_rate=250, epoch='2–6 s after trial onset (0–4 s after MI cue)',
                      files={name:hashlib.sha256((raw/name).read_bytes()).hexdigest() for name in ['A01T.mat','A01E.mat']})
    (Path(folder)/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    return load_session(raw/'A01T.mat'),load_session(raw/'A01E.mat'),provenance
