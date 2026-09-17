import json
import numpy as np
import mne
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix
from .eeg_loader import load_public_data, CHANNELS, ROOT

VERSION = 2

def filter_eeg(X):
    # Causal filtering: the decision at 2 s never accesses later samples.
    return mne.filter.filter_data(X.copy(),250,8,30,method='iir',phase='forward',
                                 iir_params=dict(order=4,ftype='butter'),verbose=False)

def prepare(folder=ROOT/'data/eeg',progress=print,force=False):
    folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'replay.npz'; report_path=folder/'metrics.json'
    if cache.exists() and report_path.exists() and not force:
        report=json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('version')==VERSION:
            with np.load(cache,allow_pickle=False) as a:
                return {k:a[k] for k in a.files},report
    (train,ytrain,atrain),(test,ytest,atest),provenance=load_public_data(folder,progress)
    progress('MNE: causal 8–30 Hz filtering; fitting CSP + LDA on A01T only…')
    # Features use exactly the first 2 seconds after cue, for both sessions.
    train_f=filter_eeg(train[:,:,:500]); test_f=filter_eeg(test)
    model=make_pipeline(CSP(n_components=4,reg='ledoit_wolf',log=True,norm_trace=False),
                        LinearDiscriminantAnalysis(solver='lsqr',shrinkage='auto'))
    with mne.utils.use_log_level('ERROR'):
        model.fit(train_f,ytrain)
        probabilities=model.predict_proba(test_f[:,:,:500])
    predictions=model.classes_[np.argmax(probabilities,axis=1)]
    report=dict(version=VERSION,provenance=provenance,training_trials=len(ytrain),evaluation_trials=len(ytest),
                accuracy=float(accuracy_score(ytest,predictions)),
                balanced_accuracy=float(balanced_accuracy_score(ytest,predictions)),
                confusion_matrix=confusion_matrix(ytest,predictions,labels=[0,1]).tolist(),
                labels=['LEFT','RIGHT'],channels=CHANNELS,sample_rate=250,
                decoder='Causal 8–30 Hz · CSP (4) · shrinkage LDA',decision_window_seconds=2,
                split='A01T train → A01E held-out evaluation; no test-set fitting or tuning',
                artifact_policy='All left/right trials retained, including dataset-flagged artifacts',
                training_artifacts=int(atrain.sum()),evaluation_artifacts=int(atest.sum()),
                confidence_note='LDA posterior, not independently calibrated; this is not clinical confidence')
    arrays=dict(signals=(test_f*1e6).astype(np.float32),labels=ytest,predictions=predictions,
                confidence=probabilities.max(axis=1),artifacts=atest)
    np.savez_compressed(cache,**arrays)
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    progress(f'EEG ready: {len(ytest)} held-out trials, accuracy {report["accuracy"]:.1%}')
    return arrays,report
