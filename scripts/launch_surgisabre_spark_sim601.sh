#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly SIM_SOURCE_ROOT="${ISAAC_SIM_SOURCE_ROOT:-${DATA_ROOT}/upstream/IsaacSim}"
readonly SIM_ROOT="${ISAAC_SIM_ROOT:-${SIM_SOURCE_ROOT}/_build/linux-aarch64/release}"
readonly SIM_REVISION="987015050efebfd0cd5d3736ae47fffe5adee308"
readonly LAB_ROOT="${DATA_ROOT}/upstream/IsaacLab"
readonly LAB_REVISION="ab419fec0ddae768952e6d56f9a317e1461d2d71"
readonly CLOUDXR_ROOT="${DATA_ROOT}/runtime/cloudxr-6.2.0-arm64"
readonly CLOUDXR_ENV="${SURGISABRE_CLOUDXR_ENV:-${REPO_ROOT}/config/cloudxr.env}"
readonly OPENXR_LOADER="${ISAAC_TELEOP_OPENXR_LOADER:?Set ISAAC_TELEOP_OPENXR_LOADER}"
readonly CUSPARSELT_ROOT="${DATA_ROOT}/runtime/cusparselt-cu13-0.8.0"
readonly EXPERIENCE="${SURGISABRE_XR_EXPERIENCE:-${REPO_ROOT}/apps/surgisabre.spark.arm64.kit}"
readonly SESSION_ID="${SURGISABRE_SESSION_ID:-$(date --utc '+%Y%m%dT%H%M%SZ')-gb10}"
readonly SESSION_DIR="${SURGISABRE_SESSION_DIR:-${DATA_ROOT}/evidence/${SESSION_ID}}"
readonly RUNTIME_ROOT="${DATA_ROOT}/runtime/isaacsim-6.0.1-surgisabre"

if [[ "${ACCEPT_OMNIVERSE_EULA:-}" != "Y" ]]; then
  printf '%s\n' "Set ACCEPT_OMNIVERSE_EULA=Y after accepting NVIDIA's terms." >&2
  exit 2
fi
if [[ "${ACCEPT_CLOUDXR_EULA:-}" != "Y" ]]; then
  printf '%s\n' "Set ACCEPT_CLOUDXR_EULA=Y after accepting NVIDIA's CloudXR licence." >&2
  exit 2
fi
if [[ ! "${SESSION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  printf '%s\n' "SURGISABRE_SESSION_ID contains unsupported characters." >&2
  exit 2
fi
if [[ -e "${SESSION_DIR}" ]]; then
  printf 'Session directory already exists: %s\n' "${SESSION_DIR}" >&2
  exit 2
fi

[[ "$(uname -m)" == "aarch64" ]]
[[ "$(git -C "${SIM_SOURCE_ROOT}" rev-parse HEAD)" == "${SIM_REVISION}" ]]
[[ "$(git -C "${LAB_ROOT}" rev-parse HEAD)" == "${LAB_REVISION}" ]]
[[ -x "${SIM_ROOT}/python.sh" ]]
[[ -s "${SIM_ROOT}/VERSION" ]]
[[ -s "${EXPERIENCE}" ]]
[[ -s "${CLOUDXR_ENV}" ]]
[[ -S "${CLOUDXR_ROOT}/run/ipc_cloudxr" ]]
[[ -s "${OPENXR_LOADER}" ]]
printf '%s  %s\n' \
  '20de6b36cbbf5753b26826eec753a2005608e14cbc3bfdd4681138098be86941' \
  "${CUSPARSELT_ROOT}/lib/libcusparseLt.so.0" | sha256sum --check
if ! ss -H -lnt 'sport = :48322 or sport = :49100' | grep -q .; then
  printf '%s\n' "CloudXR TCP listeners are not ready." >&2
  exit 1
fi

mapfile -t overlay_markers < <(
  find "${DATA_ROOT}/runtime" -mindepth 2 -maxdepth 2 -type f \
    -name '.surgisabre-overlay.env' -print
)
if [[ "${#overlay_markers[@]}" -ne 1 ]]; then
  printf 'Expected one Isaac Sim overlay, found %d.\n' \
    "${#overlay_markers[@]}" >&2
  exit 1
fi
readonly OVERLAY_ROOT="$(dirname "${overlay_markers[0]}")"
grep -Fxq "ISAAC_SIM_REVISION=${SIM_REVISION}" "${overlay_markers[0]}"
grep -Fxq "ISAAC_LAB_REVISION=${LAB_REVISION}" "${overlay_markers[0]}"

for directory in \
  "${RUNTIME_ROOT}/cache" \
  "${RUNTIME_ROOT}/tmp" \
  "${RUNTIME_ROOT}/logs" \
  "${SESSION_DIR}"; do
  mkdir -p "${directory}"
done

"${REPO_ROOT}/scripts/check_capacity_spark.sh" --runtime
resource_log="${SESSION_DIR}/resources-isaac.log"
host_log="${SESSION_DIR}/isaac-host.log"
manifest="${SESSION_DIR}/runtime-manifest.txt"
{
  printf 'session_id=%s\n' "${SESSION_ID}"
  printf 'host=%s\n' "$(hostname)"
  printf 'architecture=%s\n' "$(uname -m)"
  printf 'isaac_sim_source_revision=%s\n' "${SIM_REVISION}"
  printf 'isaac_sim_version=%s\n' "$(tr -d '\n' <"${SIM_ROOT}/VERSION")"
  printf 'isaac_lab_revision=%s\n' "${LAB_REVISION}"
  printf 'isaacteleop_integration_revision=790d6cb4e948de377975c76ed1e9cbf5098e10fc\n'
  printf 'cloudxr_version=6.2.0\n'
  printf 'experience_sha256=%s\n' "$(sha256sum "${EXPERIENCE}" | cut -d' ' -f1)"
  printf 'openxr_loader_sha256=%s\n' "$(sha256sum "${OPENXR_LOADER}" | cut -d' ' -f1)"
} >"${manifest}"

"${REPO_ROOT}/scripts/resource_monitor_spark.sh" "${resource_log}" "$$" &
monitor_pid=$!
cleanup() {
  exit_code=$?
  trap - EXIT INT TERM HUP
  set +e
  kill "${monitor_pid}" 2>/dev/null
  wait "${monitor_pid}" 2>/dev/null
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM HUP

set -a
source "${CLOUDXR_ENV}"
set +a
export ACCEPT_EULA=Y
export OMNI_KIT_ACCEPT_EULA=yes
export PRIVACY_CONSENT=N
export CUDA_VISIBLE_DEVICES=0
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=ascii:backslashreplace
export PYTHONNOUSERSITE=1
export ISAACLAB_PATH="${LAB_ROOT}"
export ISAACLAB_ROOT="${LAB_ROOT}"
export ISAAC_SIM_ROOT="${SIM_ROOT}"
export ISAAC_TELEOP_OPENXR_LOADER="${OPENXR_LOADER}"
export LD_LIBRARY_PATH="${CUSPARSELT_ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export PYTHONPATH="${REPO_ROOT}/src:${LAB_ROOT}/source/isaaclab:${LAB_ROOT}/source/isaaclab_assets:${LAB_ROOT}/source/isaaclab_tasks:${LAB_ROOT}/source/isaaclab_mimic:${LAB_ROOT}/source/isaaclab_rl:${OVERLAY_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export XDG_CACHE_HOME="${RUNTIME_ROOT}/cache"
export TMPDIR="${RUNTIME_ROOT}/tmp"
export DISPLAY="${DISPLAY:?Set DISPLAY to the active X display}"
export XAUTHORITY="${XAUTHORITY:?Set XAUTHORITY to the active Xauthority file}"
export SURGISABRE_SESSION_ID="${SESSION_ID}"
export SURGISABRE_TELEMETRY_PATH="${SESSION_DIR}/isaac-telemetry.jsonl"
export SURGISABRE_RUNTIME_PROFILE=gb10_arm64
export SURGISABRE_XR_ANCHOR_POS="${SURGISABRE_XR_ANCHOR_POS:-0.0,-0.50,-1.3662}"
export SURGISABRE_XR_NEAR_PLANE_M="${SURGISABRE_XR_NEAR_PLANE_M:-0.05}"

printf 'SurgiSabre session: %s\n' "${SESSION_ID}"
printf 'Session directory: %s\n' "${SESSION_DIR}"
"${SIM_ROOT}/python.sh" "${REPO_ROOT}/scripts/run_surgisabre.py" \
  --task Isaac-NeedlePass-dVRK-IK-Abs-v0 \
  --teleop_device motion_controllers \
  --device cuda:0 \
  --xr \
  --headless \
  --experience "${EXPERIENCE}" \
  --kit_args "--ext-folder ${LAB_ROOT}/source --/xr/ui/enabled=true --/defaults/xr/profile/ar/controllers/visible=true --/persistent/xr/profile/ar/controllers/visible=true --/persistent/xr/profile/ar/render/nearPlane=0.05" \
  2>&1 | tee "${host_log}"

python_status="${PIPESTATUS[0]}"
exit "${python_status}"
