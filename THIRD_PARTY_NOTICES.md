# Third-party notices

SurgiSabre original source is licensed under Apache License 2.0. The following
projects and externally obtained components are required or modified by the
reference deployment. Their licences continue to apply independently.

## Isaac Lab

Copyright (c) 2022-2025, The Isaac Lab Project Developers.

Isaac Lab revision `ab419fec0ddae768952e6d56f9a317e1461d2d71` is licensed
under BSD 3-Clause. SurgiSabre includes a derived Kit experience and patches
against this revision. The complete upstream notice is retained in
`LICENSES/BSD-3-Clause-IsaacLab.txt`. SurgiSabre marks its modifications in the
patch files and does not imply upstream endorsement.

## NVIDIA Isaac Sim

The Isaac Sim source at revision
`987015050efebfd0cd5d3736ae47fffe5adee308` is licensed under Apache License
2.0. Building or running it requires separately licensed NVIDIA components,
including Omniverse Kit and content. SurgiSabre does not redistribute those
components.

## NVIDIA IsaacTeleop

Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

IsaacTeleop source revision
`ca175df7afc8198cbba0592cd1b447b11a4f3165` and tested integration revision
`790d6cb4e948de377975c76ed1e9cbf5098e10fc` are licensed under Apache License
2.0. SurgiSabre includes patches against that source. The patch files are
modifications and retain the applicable NVIDIA headers and notices.

## Isaac for Healthcare assets

The remotely referenced dVRK PSM asset comes from Isaac for Healthcare
Sim-Ready Assets v0.6.0, content revision `c189487`. The catalogue and pinned
PSM entry are licensed under Apache License 2.0. The USD payload is not stored
in this repository.

## NVIDIA CloudXR

CloudXR Runtime and the CloudXR JavaScript package are governed by NVIDIA's
separate CloudXR agreement. SurgiSabre includes no CloudXR archive, binary,
npm package or compiled web bundle. Each operator must obtain version 6.2.0
from NVIDIA and accept its terms before building or running the integration.

This software contains source code provided by NVIDIA Corporation.

## Licence texts

- `LICENSES/Apache-2.0.txt`
- `LICENSES/BSD-3-Clause-IsaacLab.txt`

See `ATTRIBUTION.md` for source URLs, exact revisions and the non-endorsement
statement.
