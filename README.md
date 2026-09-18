# Brain-Controlled Digital Fly

> **🖥️ Live Demo**: <https://naturals-extremely-operation-grill.trycloudflare.com>

**To deploy to a web server, see [DEPLOY.md](DEPLOY.md). Docker / Compose / Nginx configs are included.**

Public human EEG → CSP + LDA → neural activity propagation over the measured MANC connectome → motor-neuron readout → NeuroMechFly / MuJoCo physical behavior.

This is a runnable, interactive engineering demo — not a complete fly brain and not a biologically validated digital twin. It uses decoded predictions by default and does not hide erroneous trials.

## Getting started

Use **Python 3.12** and a WebGL-capable browser. From this directory:

```bash
pip install -r requirements.txt
python app.py
```

The browser opens http://localhost:8501 automatically. On Windows, double-click `start.bat`; on macOS / Linux, run `sh start.sh` (the actual validation platform was Windows). `--no-browser` and `--port 8502` are supported. The first install needs network access and enough time to install the scientific-computing and physics-engine dependencies.

The distribution includes prepared real EEG and the full threshold-filtered MANC matrix, so the demo runs offline after dependencies are installed. If prepared data is missing, it is downloaded and built automatically from public sources; failures surface the real error instead of falling back to synthetic data.

## Usage

- **Decoded EEG** (default): real CSP + LDA predictions drive DNa02.
- **Ground Truth**: public labels drive the same neural-and-physics pipeline, for comparison.
- **Manual**: choose a left/right input signal to drive DNa02 directly, for interactive control.
- **Cut synapses**: disconnect propagation and remove the EEG's influence on motion; the baseline CPG keeps walking. **Restore** reconnects.
- Pause / Resume, Next trial, Reset, and 0.5× / 1× / 2× speed. Both the brain network and the body can be dragged to rotate and scrolled to zoom.
- **Session details** shows the data, algorithms, verification criteria, and modeling assumptions.
- The UI is **bilingual**: use the **中文 / EN** toggle in the top-right corner.

The left panel draws 8 channel waveforms (decoding uses all 22 channels). The middle panel shows 1,800 neurons and 20,000 connections at their real coordinates; node brightness follows model activity and edge brightness is derived from the activity of its endpoint nodes — no schematic flow particles. The right panel shows the actual physical pose, trajectory, reference target, contact count, and heading. All 144 held-out test trials loop in their original order.

## Data & fidelity

### EEG

BNCI2014_001 / BCI Competition IV 2a, A01T for training and A01E for testing, left/right hand only, 144 trials per session. 250 Hz, a 0–4 s signal after the cue; predictions use only the first 2 s. Causal 8–30 Hz Butterworth → 4-component CSP → shrinkage LDA. Held-out accuracy is **74.3056%**; the confusion matrix (true rows L/R, predicted columns L/R) is `[[69,3],[34,38]]`. Confidence is an uncalibrated LDA posterior. Predictions are precomputed offline for smooth animation — this is not live EEG acquisition.

Source: https://lampx.tugraz.at/~bci/database/001-2014/

### Measured connectome

**MANC v1.0 is a male fly ventral nerve cord, not a whole brain.** It uses 23,188 traced neurons; from 5,243,574 released directed connections, 1,360,021 connections with at least 5 synapses are retained, totaling 23,999,382 synapses. No edges are generated or synthesized. Neuron IDs, connections, and synapse counts come from EM reconstruction; the source files pass the publisher's MD5 verification and their SHA256 is recorded.

EEG LEFT / RIGHT stimulate the real DNa02 #10126 / #10118, respectively. Leg motor neurons use the eLife 96084 Supplement 6 annotation; 247 of 264 annotations match this traced release, and the 17 missing entries are explicitly excluded. The display subset does not limit the computation: all retained nodes and edges participate in the sparse-matrix dynamics.

Source: https://www.janelia.org/project-team/flyem/manc-connectome

Motor annotation: https://doi.org/10.7554/eLife.96084

### Modeling assumptions & physical body

- Neural dynamics are a delayed rectified-rate model: 5 ms neural step, 25 ms time constant, 10 ms propagation delay, 0.92 recurrent gain. It is normalized by input synapse count, with predicted ACh positive, GABA/Glut negative, and unknown treated as positive. These are not per-neuron fitted physiological parameters.
- Mean activity of the MANC left/right motor populations is normalized by a shared calibration scale. An engineering adapter `clip(1 - 0.65 * gain * motor / scale, 0.25, 1)` (default gain = 2, options 1 / 1.5 / 2) modulates the ipsilateral CPG stride; the body code never receives EEG labels or left/right classes.
- The body is the micro-CT-derived female fly model from FlyGym 2.1.0 / NeuroMechFly, a different specimen from the male MANC. MuJoCo 3.9 computes gravity, joints, and contacts: 42 leg position actuators and 6 adhesion actuators; physics step 0.1 ms, control step 1 ms.
- Baseline walking comes from a published hybrid CPG + reflex controller. **MANC modulates turning; it does not independently generate the baseline gait.** There is no scripted body translation, rotation, wall bouncing, or between-trial teleportation.
- Human EEG → DNa02 and motor populations → CPG are engineering interfaces, not a validated human–fly biological mapping.

Body model: https://github.com/NeLy-EPFL/flygym/tree/v2.1.0

Paper: https://doi.org/10.1038/s41592-024-02497-y

## Animation clock

Each trial spans 5 s of EEG time: 0–2 s acquisition, the prediction is revealed at 2 s, DNa02 is stimulated during 2–3.8 s, the motor readout is recorded at 4 s, and the trial switches at 5 s. Neural/body time advances at 0.1× the EEG time, and the interface shows the BODY time explicitly. The body integrates physics continuously and turning happens continuously — it does not force a fixed angle at 4 s. The target is only a reference, not a closed-loop navigation task.

## Reproduction & verification

```bash
python scripts/download_eeg.py --force
python scripts/download_manc.py
python scripts/build_manc_connectome.py
python -m unittest discover -s tests -v
python scripts/probe_real_chain.py
python scripts/audit_long_replay.py
```

The ZIP omits the large raw MAT / CSV / Feather files; run the download scripts to rebuild them. Per-edge auditing requires the original connection CSV, and the corresponding tests are explicitly skipped when it is missing. Data provenance is in `data/eeg/provenance.json`, `data/manc/source_manifest.json`, and `network_config.json`. The tested dependency versions are in `tested-versions.json`.

`data/connectome/nodes.csv` and `edges.csv` are a unified table interface for the **visualization subset** only; replacing them alone cannot change the full-network simulation. The full network is produced by `scripts/build_manc_connectome.py` into `data/manc/measured_network.npz`, `measured_edges.npz`, and `all_neurons.json`; changing the data source requires rebuilding these files together.

## Deliverables

- `app.py`, `backend/`, `frontend/`: the full server, dynamics, and local Three.js interface.
- `scripts/`: official data download, build, causal comparison, and full-session signal auditing.
- `tests/`: real-data, dynamics, physics, and EEG causal-filtering tests.
- `demo-preview.png` / `mobile-preview.png`: real browser screenshots.
- `VERIFICATION.md` / `data/validation/`: verification notes and raw results.

Real connectome data does not mean the model has explained biological behavior; this demo proves a reproducible engineering pipeline and its causal dependence within that model.

### Trajectory display

The body mesh, trajectory endpoints, and thorax ground-projection marker use the same physics snapshot — the body is not eased separately. The trajectory records the XY ground projection of the thorax center, not footprints; the minimap uses fixed world coordinates and marks the body heading. Heading does not have to equal the instantaneous velocity direction — the physics model allows sideslip. Node brightness is per-cell normalized model activity; edge brightness is only a visualization of endpoint activity, not measured synaptic current or action potentials.

### How decoding maps to turning

"Left/right turn" is relative to the fly's own heading, not left/right movement on screen. The first 2 s have only baseline gait; after 2 s the active path segment is highlighted and the historical path turns gray. The interface shows the actual driving class, the live motor-population bias, and the accumulated physical heading change since 2 s (unwrapped step-by-step to avoid ±180° boundary errors). Stimulation stops at 3.8 s, after which neural decay and body response continue. The Δ in the activity log is the accumulated turn at the 4 s readout. EEG classification and neural connectivity are unchanged; steering gain is an explicitly adjustable engineering parameter, and the body trajectory is produced by physics integration.

### Steering strength

The default steering gain is 2×, amplifying the left/right stride difference caused by motor-population activity, with a minimum stride signal of 0.25. The default view is top-down; a button switches to side view. The top-down view overlays a dashed line for the decoded direction and a solid line for the current direction; the large angle plot below fixes the decoded heading upward and shows the real accumulated turn without amplification. 1× gain validation data lives in `data/validation/baseline-gain1/`; the full 2× gain validation is in `gain2-full-replay.json`.

### What "Cut synapses" means

After cutting, the left/right motor-neuron outputs become zero, and the next physics update uses equal left/right stride signals [1, 1]. The CPG baseline gait and current body state keep integrating, so the fly may still rotate; cutting cannot undo previously accumulated motion, pose, and gait phase, and it is neither a brake nor a straight-line lock. After cutting, the interface uses a neutral trajectory and a "post-cut drift" reading. The mid-cut regression test starts from the same physical state and verifies that every subsequent step exactly matches the zero-neural-input branch's qpos, including across trials.
