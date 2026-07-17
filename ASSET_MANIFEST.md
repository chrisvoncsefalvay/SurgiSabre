# Asset manifest

SurgiSabre does not vendor third-party USD, mesh, texture, font or logo assets.
The reference task resolves the following revisioned asset through the pinned
Isaac Lab configuration.

| Asset | Source | SHA-256 | Licence |
| --- | --- | --- | --- |
| dVRK PSM | `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/Healthcare/0.6.0/c189487/Robots/dVRK/PSM/psm.usd` | `5730339c3b806f17a5228c69b97464d0b3469888002f62fb23d9621f746347c8` | Apache-2.0 through the i4h v0.6.0 catalogue |

Run `python3 scripts/verify_i4h_asset.py` before the first launch. The script
stores the verified root USD under the untracked project data root. Referenced
payloads remain subject to their upstream catalogue entries.

The course is needleless and has no suture pad. The table is project-authored
primitive geometry with a plain white material. No HCLTech artwork or font is
part of the public scene.
