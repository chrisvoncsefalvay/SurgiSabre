# Deployment

This guide describes the reference deployment on an ARM64 NVIDIA GB10 host
with a physical Meta Quest. It is a source build and private-network workflow.
It is not a recipe for exposing CloudXR directly to the open Internet.

## Evidence boundary

The original system was manually exercised with a physical Quest, bilateral
tracked controllers, streamed rendering and haptic requests. That result is
specific to its host, headset software and network path. Private certificates,
tailnet configuration, session logs, video and controller traces are not
bundled with this repository.

A new deployment remains unverified until an operator completes the physical
acceptance checklist at the end of this guide. Unit tests, open ports and a
successful package import are necessary checks, but they are not end-to-end
evidence.

## Reference stack

| Component | Required reference identity |
| --- | --- |
| Host operating system | Ubuntu 24.04 ARM64 |
| GPU | NVIDIA GB10 with unified CPU and GPU memory |
| Isaac Sim source | `987015050efebfd0cd5d3736ae47fffe5adee308` |
| Isaac Sim build | `6.0.1-rc.7+develop.0.98701505.local` |
| Isaac Sim Python | `3.12.13` |
| Isaac Lab | `0.54.5` at `ab419fec0ddae768952e6d56f9a317e1461d2d71` |
| IsaacTeleop source | `ca175df7afc8198cbba0592cd1b447b11a4f3165` |
| IsaacTeleop integration | `790d6cb4e948de377975c76ed1e9cbf5098e10fc` |
| CloudXR runtime and web client | `6.2.0` |
| i4h PSM asset | catalogue `v0.6.0`, content revision `c189487` |

Preserve these pins for the reference profile. Treat a version change as a new
compatibility lane with separate validation.

## Distribution boundary

SurgiSabre does not include third-party runtime binaries or the i4h USD payload.
Before continuing, obtain:

1. NVIDIA Isaac Sim source and every additional component required by its build
   under the applicable NVIDIA terms.
2. NVIDIA CloudXR Runtime SDK 6.2.0 for Linux ARM64 and the matching CloudXR.js
   package after accepting the CloudXR agreement.
3. Network access to the pinned public i4h PSM asset.

Do not copy a prebuilt runtime, generated wheel or SDK archive from another
organisation unless its licence explicitly permits that distribution.

The expected ARM64 CloudXR 6.2.0 archive SHA-256 is:

```text
3aa25e7c052aab4c2e6b1cb188272ae6d691335c586e1667e95e73c492584e88
```

Verify the archive before extraction:

```bash
sha256sum /path/to/CloudXR-6.2.0-Linux-arm64-sdk.tar.gz
```

The result must match exactly. A different archive is not the reference build.

## Host preparation

Use project-scoped directories outside the repository for downloads, builds,
runtimes, logs and evidence. A typical layout is:

```text
/srv/surgisabre/
  archives/
  build/
  runtime/
  upstream/
  logs/
  evidence/
```

On a single-user development host, an equivalent directory under the user's
home is acceptable. Do not use a shared repository directory for private keys
or generated SDK content.

The GB10 uses unified memory. Before every large download, build and launch,
check host memory, swap, disk capacity and GPU activity:

```bash
free -h
swapon --show
df -h /srv/surgisabre
nvidia-smi
```

Avoid concurrent Isaac Sim, IsaacTeleop and CloudXR builds. If available memory
approaches an unsafe level, stop the project-owned process cleanly before the
host is forced to recover it.

## Configuration

Copy the public environment template, edit it and export its values into the
current shell. Keep the local file untracked:

```bash
cp .env.example .env
set -a
source .env
set +a
scripts/render_cloudxr_config.sh
```

Set or confirm these deployment-specific values:

- project data root
- Isaac Sim source and release roots
- CloudXR archive and runtime roots
- host bind address and advertised address
- public or private-overlay DNS hostname
- TLS certificate and private-key paths
- OpenXR loader path
- X display and Xauthority path
- CloudXR web client base URL

Never place a private key, token or machine-specific address in a tracked file.
The launchers must fail closed when a required value is absent.

## Build order

Place the separately obtained CloudXR archive at
`$SURGISABRE_DATA_ROOT/archives/cloudxr-6.2.0/CloudXR-6.2.0-Linux-arm64-sdk.tar.gz`.
Use one heavyweight operation at a time, in this order:

1. Run `scripts/bootstrap_sources.sh` to fetch all three pinned source trees.
2. Run `scripts/build_isaacsim_spark.sh`.
3. Run `scripts/apply_isaaclab_patches.sh`.
4. Run `ISAACTELEOP_PYTHON_VERSION=3.11 scripts/build_isaacteleop_spark.sh`.
5. Run `ISAACTELEOP_PYTHON_VERSION=3.12 scripts/build_isaacteleop_spark.sh`.
6. Run `scripts/prepare_cloudxr_runtime_spark.sh`.
7. Run `scripts/prepare_isaacsim_6_0_1_overlay_spark.sh`.
8. Run `scripts/build_openxr_compat_spark.sh`.
9. Run `python3 scripts/verify_i4h_asset.py`.
10. Run the source tests and the runtime capacity preflight.

The project scripts for the reference path are:

```text
scripts/check_capacity_spark.sh
scripts/bootstrap_sources.sh
scripts/build_isaacsim_spark.sh
scripts/prepare_isaacsim_6_0_1_overlay_spark.sh
scripts/apply_isaaclab_patches.sh
scripts/prepare_isaacteleop_build_tree_spark.sh
scripts/build_isaacteleop_spark.sh
scripts/prepare_cloudxr_runtime_spark.sh
scripts/build_openxr_compat_spark.sh
```

Supply local paths through the exported environment and untracked CloudXR
configuration rather than editing a launcher. Build the two IsaacTeleop wheels
sequentially. They share the separately downloaded archive but target different
Python runtimes.

## Network and TLS

The reference web path uses these service ports:

| Port | Protocol | Purpose |
| --- | --- | --- |
| 48322 | TCP | HTTPS client and secure WebSocket proxy |
| 49100 | TCP | CloudXR signalling |
| 47998 | UDP | direct media path |

Restrict all three to the intended operator network. Prefer a wired host and a
5 GHz or 6 GHz headset connection. Use a DNS name and certificate that the
Quest browser trusts.

The current reference path assumes direct reachability and has ICE disabled. It
does not provide TURN traversal, application authentication or a safe anonymous
Internet service. If the headset cannot reach the host directly, add a reviewed
ICE or TURN design rather than opening more ports indiscriminately.

## Launch order

1. Run `scripts/check_capacity_spark.sh`.
2. Start `scripts/launch_cloudxr_spark.sh` and wait for the HTTPS and signalling
   listeners.
3. Start `scripts/launch_surgisabre_spark_sim601.sh` and wait for the Isaac task
   identity, OpenXR initialisation and runtime report.
4. Use the exact client URL printed by the CloudXR launcher. It must request
   immersive VR so that passthrough is not the environment background.
5. Connect the Quest only after both services are ready.

Run long-lived processes under a supervisor that preserves their environment,
captures logs and stops the complete process group. A user service manager is
preferred to an unattended shell background process.

Start CloudXR before Isaac. Stop Isaac before CloudXR. Confirm that project
ports and child processes are gone before rebuilding or restarting.

## Host checks

Before putting on the headset, confirm:

- the runtime reports the exact dependency revisions
- the GPU device is `cuda:0`
- the task has one environment and two articulated PSMs
- the dark dome, table, targets, score and reactive side lights exist
- both controller sides are initially allowed to wait for tracking
- TCP 48322 and 49100 are listening on the intended interface
- UDP 47998 follows the expected direct route
- the client page returns HTTP 200 through the trusted hostname

OpenXR controller warnings before the headset connects are expected. A fatal
OpenXR error, missing CloudXR IPC socket, asset digest mismatch or source
revision mismatch is not expected.

## Physical Quest acceptance

Record the host revision, dependency report, Quest model, Quest software,
controller type, network route and test time. Then confirm all of the following:

1. The Quest connects and displays the dark SurgiSabre arena without
   passthrough.
2. The view is close behind and between the two PSMs.
3. Left and right controllers drive the corresponding instruments.
4. Controller orientation pivots each instrument around its fixed remote
   centre.
5. Collinear pull and push retract and advance the instrument.
6. Releasing squeeze holds the complete pose.
7. Re-engaging squeeze does not cause an instrument jump.
8. Tracking loss holds the last safe target and requires fresh engagement.
9. The index trigger opens and closes the jaws promptly.
10. Targets arrive at visibly varied heights, lengths, colours and speeds.
11. An accepted hit produces a controller haptic pulse.
12. A hit target receives a clear kick, enters gravity and falls.
13. The side lighting changes on accepted hits.
14. The table score changes exactly once for each hit or miss.
15. Disconnect and reconnect do not leave an instrument moving unattended.

Automated telemetry should corroborate the physical observations, but it does
not replace them. If any item fails, mark the deployment as incomplete and
retain the relevant logs without publishing private session data.

## Public service warning

Publishing the source repository does not make a running instance suitable for
public access. An Internet-facing service needs a separate security design with
authentication, origin restrictions, abuse controls, certificate management,
network isolation and reviewed media traversal. That work is outside the
validated SurgiSabre reference path.
