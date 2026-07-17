# SurgiSabre

**A lighthearted target game for serious surgical teleoperation familiarisation.**

SurgiSabre is an immersive teleoperation simulation in which Meta Quest
controllers drive two simulated dVRK Patient Side Manipulators (PSMs). Players
intercept approaching targets using clutchable remote-centre instrument control
with contact haptics, scoring and reactive lighting.

The presentation is playful, but the control problem is real. A physical
controller pose must be translated into a bounded simulated instrument pose
while preserving the remote centre, shaft direction, insertion limits and
clutch reference frame. Quest controllers do not reproduce the kinematics or
ergonomics of surgical Master Tool Manipulators (MTMs). For surgeons and
operators accustomed to MTMs, direct spatial controller mapping may therefore
be unfamiliar.

SurgiSabre provides a repeatable low-stakes environment for learning that
translation. Its purpose is to help users build intuition for orientation,
insertion, clutching and workspace limits before undertaking more structured
teleoperation tasks. It does not claim to measure surgical skill or clinical
competence.

> Beat the targets. Learn the mapping. Respect the remote centre.

## What the operator practises

- Left and right controllers command the corresponding left and right PSMs.
- Each instrument pivots around its fixed remote centre.
- Controller orientation determines instrument direction within a clutch
  interval.
- Controller movement along the instrument axis advances or retracts the tool.
- Squeeze acts as a clutch. Re-engagement registers a new controller reference
  without intentionally moving the held tool.
- The index trigger commands jaw opening and closing. Jaw contact and gripping
  physics are disabled in the current needleless course.
- A valid instrument contact releases a target into gravity, applies an
  impulse-like kick and requests haptic feedback on the corresponding
  controller.

Targets vary in height, length, colour and speed. A table-mounted score records
successful contacts and missed targets. Side lighting changes on accepted hits.
The arena uses a plain white table without a branding decal.

## System path

```text
Meta Quest browser
  -> CloudXR.js 6.2 web client
  -> CloudXR 6.2 signalling and direct media
  -> CloudXR OpenXR runtime
  -> IsaacTeleop XR device and dVRK retargeting
  -> Isaac Lab task and contact sensors
  -> Isaac Sim 6.0.1 and PhysX on NVIDIA GB10
```

SurgiSabre adds the application-specific retargeting contract, target course,
score, haptics, scene presentation and telemetry. It does not modify global
Isaac defaults.

## Validated reference configuration

The first working path was exercised on one ARM64 NVIDIA GB10 host and a
physical Quest with tracked controllers. These are compatibility pins, not
floating minimum versions.

| Component | Tested identity |
| --- | --- |
| Host | Ubuntu 24.04, ARM64, NVIDIA GB10 |
| Isaac Sim source | `987015050efebfd0cd5d3736ae47fffe5adee308` |
| Isaac Sim build identity | `6.0.1-rc.7+develop.0.98701505.local` |
| Isaac Sim Python | `3.12.13` |
| Isaac Lab | `0.54.5` at `ab419fec0ddae768952e6d56f9a317e1461d2d71` |
| IsaacTeleop source | `ca175df7afc8198cbba0592cd1b447b11a4f3165` |
| IsaacTeleop integration | `790d6cb4e948de377975c76ed1e9cbf5098e10fc` |
| IsaacTeleop package | `1.4+local` |
| CloudXR runtime and web client | `6.2.0` |
| i4h asset catalogue | `v0.6.0`, tag commit `bee7e9314bb8f1c78f7e178a7840d708eda9ffb1` |
| i4h content revision | `c189487` |

Other hosts, GPUs, headset versions and network layouts are unverified until
they pass the same runtime and physical acceptance checks.

## Source-only distribution

This repository does not redistribute Isaac Sim binaries, CloudXR SDK or
runtime files, the CloudXR npm package, generated IsaacTeleop wheels or i4h USD
payloads. It provides source, patches, dependency identities and digest checks.
Users must obtain third-party components from their official distributors and
accept the applicable terms.

The dVRK PSM asset is fetched from the pinned i4h catalogue location and
checked against SHA-256
`5730339c3b806f17a5228c69b97464d0b3469888002f62fb23d9621f746347c8`.

See [ATTRIBUTION.md](ATTRIBUTION.md), `THIRD_PARTY_NOTICES.md` and
`ASSET_MANIFEST.md` before building or redistributing a derived package.

## Getting started

1. Read [the deployment guide](docs/deployment.md).
2. Obtain and build the pinned Isaac Sim source revision.
3. Obtain CloudXR 6.2.0 directly from NVIDIA after accepting its licence.
4. Copy `.env.example` to `.env`, provide local paths, hostname and display
   settings, then source it into the launch shell.
5. Run the capacity check before each build or launch.
6. Build the pinned IsaacTeleop integration and OpenXR compatibility component.
7. Start CloudXR, then start the SurgiSabre Isaac application.
8. Use the exact immersive-VR client URL printed by the launcher.
9. Complete the physical acceptance checklist in the deployment guide.

The original hardware session, certificates, private network configuration and
Quest evidence are intentionally not bundled. Passing the Python tests does not
prove that a new headset, network or runtime can complete the end-to-end path.

## Development checks

Run the smallest checks relevant to a change, then run the complete source test
suite before proposing it for release:

```bash
python3 -m ruff check src tests
python3 -m pytest -q
bash -n scripts/*.sh
```

Runtime changes also require a fresh Isaac launch. Changes to mapping, clutch,
haptics, streaming or presentation require a physical Quest check and an
explicit record of the tested hardware.

## Deployment boundary

The validated configuration uses a direct route or private network overlay.
Its current CloudXR path does not provide a repository-level authentication
layer and does not establish a general ICE or TURN path. Do not expose it as an
open Internet service. Restrict ingress to the operator network and read
[docs/deployment.md](docs/deployment.md) before opening any port.

## Known limitations

- The simulation does not model tissue or an operative procedure.
- Contact response, haptics, latency and controller mapping are simplified.
- The course is a familiarisation exercise, not a validated training protocol.
- Score is a game metric, not a proficiency or credentialling metric.
- The current physical evidence covers a limited hardware and network
  configuration.
- No transfer-of-training or clinical-outcome claim has been established.

## Safety and non-clinical use

SurgiSabre is research and demonstration software. It is not a medical device
and is not intended for clinical use, procedure planning, patient care,
credentialling or operation of a physical surgical robot. Its kinematics,
dynamics, latency, collision response and haptics have not been validated
against clinical hardware. Do not interpret a game score as evidence of
surgical competence.

Use the headset only in a clear safe area and follow the headset manufacturer's
safety guidance. Do not connect this software to a patient-facing system or a
physical surgical robot.

## Credits

SurgiSabre is built on NVIDIA Isaac Sim and Isaac Lab. XR device integration
and retargeting build on NVIDIA IsaacTeleop. The simulated dVRK PSM asset comes
from the NVIDIA Isaac for Healthcare (i4h) Sim-Ready Asset Catalog.

No affiliation with or endorsement by NVIDIA, Meta, Intuitive Surgical or the
dVRK project is implied. See [ATTRIBUTION.md](ATTRIBUTION.md) for exact pins and
licence boundaries.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before sending a change. Report security
issues through the private process described in [SECURITY.md](SECURITY.md).
