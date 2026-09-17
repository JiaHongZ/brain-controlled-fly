# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-17

### Added

- Real-data "Brain-Controlled Digital Fly" web server (FastAPI + WebSocket).
- Human EEG decoding pipeline: causal 8–30 Hz Butterworth → 4-component CSP →
  shrinkage LDA (22-channel inference, 8-channel display).
- Measured MANC v1.0 connectome dynamics (23,188 traced neurons, 1,360,021
  synapses after ≥5-synapse thresholding) as a sparse neural network.
- NeuroMechFly / MuJoCo 3.9 physical body with hybrid CPG + reflex walking
  controller, where MANC motor readout modulates steering.
- Three.js local frontend: EEG waveform, connectome activity, and physics
  panels with orbit controls, pause/resume, speed controls, cut/restore
  synapses, ground-truth vs decoded modes, and session details.
- Prepared EEG replay cache and MANC network data included in the package
  (no startup re-download required).
- Dockerfile + Compose configuration and host Nginx sample (see `DEPLOY.md`).
- Readiness endpoint (`/health/ready`), HTTP/WebSocket smoke checks, and
  offline validation artifacts (`data/validation/`).
- Reproduction scripts (`scripts/`) for EEG/MANC download and network build,
  plus a unit-test suite (`tests/`).

### Notes

- The package is a reproducible engineering demo, not a biologically validated
  digital twin. Model assumptions are documented in `README.md`.
