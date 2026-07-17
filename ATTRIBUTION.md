# Attribution

SurgiSabre combines original application code with pinned open source projects,
externally obtained NVIDIA components and a remotely referenced healthcare
simulation asset. This file records what each component contributes. The full
licence texts and required notices are in `LICENSE`, `THIRD_PARTY_NOTICES.md`
and `LICENSES/`.

## SurgiSabre

Original SurgiSabre source is released under Apache License 2.0. This licence
does not grant rights to separately obtained third-party software, SDKs, assets
or trademarks.

## NVIDIA Isaac Sim

- Project: [NVIDIA Isaac Sim](https://github.com/isaac-sim/IsaacSim)
- Source revision: `987015050efebfd0cd5d3736ae47fffe5adee308`
- Tested build identity: `6.0.1-rc.7+develop.0.98701505.local`
- Role: simulation application, rendering and PhysX runtime
- Source licence: Apache License 2.0

The source repository and the complete Isaac Sim distribution have different
licence boundaries. Kit, models, textures and other additional components may
be governed by NVIDIA's separate terms. SurgiSabre does not redistribute an
Isaac Sim build or those additional materials.

## Isaac Lab

- Project: [Isaac Lab](https://github.com/isaac-sim/IsaacLab)
- Version: `0.54.5`
- Revision: `ab419fec0ddae768952e6d56f9a317e1461d2d71`
- Upstream context: pull request 6527
- Role: task framework, articulated assets, contact sensors and OpenXR device
  integration points
- Licence: BSD 3-Clause
- Copyright: The Isaac Lab Project Developers

Files or patches derived from Isaac Lab retain their upstream copyright,
licence and modification notices. The Isaac Lab name and contributor names are
not used to imply endorsement.

## NVIDIA IsaacTeleop

- Project: [NVIDIA IsaacTeleop](https://github.com/NVIDIA/IsaacTeleop)
- Source revision: `ca175df7afc8198cbba0592cd1b447b11a4f3165`
- Tested integration revision: `790d6cb4e948de377975c76ed1e9cbf5098e10fc`
- Tested package identity: `1.4+local`
- Upstream context: pull request 769
- Role: XR device abstraction, CloudXR/OpenXR integration, haptic output and
  dVRK retargeting foundation
- Licence: Apache License 2.0
- Copyright: NVIDIA Corporation and affiliates

Published patches identify their modified upstream files and retain the
applicable NVIDIA copyright and SPDX notices.

## Isaac for Healthcare assets

- Project: [Isaac for Healthcare i4h asset catalog](https://github.com/isaac-for-healthcare/i4h-asset-catalog)
- Release: `v0.6.0`
- Tag commit: `bee7e9314bb8f1c78f7e178a7840d708eda9ffb1`
- Content revision: `c189487`
- Licence for the pinned dVRK PSM catalogue entry: Apache License 2.0
- Role: simulated dVRK Patient Side Manipulator

The current SurgiSabre course references this asset:

| Asset | Pinned path | SHA-256 |
| --- | --- | --- |
| dVRK PSM | `Assets/Isaac/Healthcare/0.6.0/c189487/Robots/dVRK/PSM/psm.usd` | `5730339c3b806f17a5228c69b97464d0b3469888002f62fb23d9621f746347c8` |

The asset is fetched from the official revisioned content location and verified
before use. No i4h USD or mesh payload is stored in this repository. The
needleless SurgiSabre course does not instantiate the i4h suture needle or
suture pad.

Some other i4h catalogue entries have additional terms. Do not assume that the
licence recorded for the PSM applies to unrelated catalogue content.

## NVIDIA CloudXR

- Product: NVIDIA CloudXR Runtime and CloudXR.js
- Version: `6.2.0`
- Role: WebXR signalling, streamed immersive media, tracked controller input
  and haptic transport
- Licence: separate NVIDIA CloudXR agreement

CloudXR runtime archives, shared libraries, npm packages and generated bundles
are not included. Each deployer must obtain CloudXR from NVIDIA, accept its
terms and determine whether a planned distribution is permitted.

## OpenXR and device platforms

OpenXR is an open standard maintained by the Khronos Group. Meta Quest is an
external device platform with its own software and terms. Neither is bundled
with SurgiSabre.

## Trademarks and non-endorsement

NVIDIA, Isaac, Isaac Sim, Isaac Lab, IsaacTeleop, CloudXR, Meta, Quest, dVRK,
da Vinci and other names may be trademarks of their respective owners. Their
use here identifies compatible projects, interfaces and assets. No sponsorship,
affiliation or endorsement is implied.

