#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly SIM_SOURCE_ROOT="${ISAAC_SIM_SOURCE_ROOT:-${DATA_ROOT}/upstream/IsaacSim}"
readonly SIM_ROOT="${ISAAC_SIM_ROOT:-${SIM_SOURCE_ROOT}/_build/linux-aarch64/release}"
readonly SIM_REVISION="987015050efebfd0cd5d3736ae47fffe5adee308"
readonly LAB_ROOT="${DATA_ROOT}/upstream/IsaacLab"
readonly LAB_REVISION="ab419fec0ddae768952e6d56f9a317e1461d2d71"
readonly CUSPARSELT_SOURCE="${CUSPARSELT_SOURCE:?Set CUSPARSELT_SOURCE to libcusparseLt.so.0 from nvidia-cusparselt-cu13 0.8.0}"
readonly CUSPARSELT_SHA256="20de6b36cbbf5753b26826eec753a2005608e14cbc3bfdd4681138098be86941"
readonly CUSPARSELT_ROOT="${DATA_ROOT}/runtime/cusparselt-cu13-0.8.0"

[[ "$(uname -m)" == "aarch64" ]]
[[ "$(git -C "${SIM_SOURCE_ROOT}" rev-parse HEAD)" == "${SIM_REVISION}" ]]
[[ "$(git -C "${LAB_ROOT}" rev-parse HEAD)" == "${LAB_REVISION}" ]]
[[ -x "${SIM_ROOT}/python.sh" ]]

mapfile -t provenance_files < <(
  find "${DATA_ROOT}/wheels" -mindepth 2 -maxdepth 2 -type f \
    -path '*cp312*/build-provenance.env' -print
)
if [[ "${#provenance_files[@]}" -ne 1 ]]; then
  printf 'Expected one CPython 3.12 IsaacTeleop build, found %d.\n' \
    "${#provenance_files[@]}" >&2
  exit 1
fi
readonly WHEEL_PROVENANCE="${provenance_files[0]}"
readonly WHEEL_ROOT="$(dirname "${WHEEL_PROVENANCE}")"
readonly WHEEL_NAME="$(sed -n 's/^WHEEL_FILE=//p' "${WHEEL_PROVENANCE}")"
readonly WHEEL_SHA256="$(sed -n 's/^WHEEL_SHA256=//p' "${WHEEL_PROVENANCE}")"
readonly WHEEL="${WHEEL_ROOT}/wheels/${WHEEL_NAME}"
[[ "${WHEEL_NAME}" == *-cp312-cp312-linux_aarch64.whl ]]
[[ "${WHEEL_SHA256}" =~ ^[0-9a-f]{64}$ ]]
grep -Fxq \
  'ISAACTELEOP_INTEGRATION_REVISION=790d6cb4e948de377975c76ed1e9cbf5098e10fc' \
  "${WHEEL_PROVENANCE}"
printf '%s  %s\n' "${WHEEL_SHA256}" "${WHEEL}" | sha256sum --check
printf '%s  %s\n' "${CUSPARSELT_SHA256}" "${CUSPARSELT_SOURCE}" | sha256sum --check

readonly OVERLAY_ROOT="${DATA_ROOT}/runtime/isaacsim-6.0.1-overlay-cp312-${WHEEL_SHA256:0:8}"
readonly PROVENANCE="${OVERLAY_ROOT}/.surgisabre-overlay.env"

if [[ -e "${CUSPARSELT_ROOT}" && ! -s "${CUSPARSELT_ROOT}/provenance.env" ]]; then
  printf 'Refusing unmarked cuSPARSELt root: %s\n' "${CUSPARSELT_ROOT}" >&2
  exit 1
fi
if [[ ! -s "${CUSPARSELT_ROOT}/provenance.env" ]]; then
  partial_cusparselt="${CUSPARSELT_ROOT}.partial.$$"
  trap 'rm -rf "${partial_cusparselt}"' EXIT INT TERM HUP
  mkdir -p "${partial_cusparselt}/lib"
  install -m 0755 "${CUSPARSELT_SOURCE}" \
    "${partial_cusparselt}/lib/libcusparseLt.so.0"
  printf '%s  %s\n' "${CUSPARSELT_SHA256}" \
    "${partial_cusparselt}/lib/libcusparseLt.so.0" | sha256sum --check
  {
    printf 'PACKAGE=nvidia-cusparselt-cu13\n'
    printf 'VERSION=0.8.0\n'
    printf 'BINARY_SHA256=%s\n' "${CUSPARSELT_SHA256}"
  } >"${partial_cusparselt}/provenance.env"
  mv "${partial_cusparselt}" "${CUSPARSELT_ROOT}"
  trap - EXIT INT TERM HUP
fi

if [[ -s "${PROVENANCE}" ]]; then
  grep -Fxq "ISAAC_SIM_REVISION=${SIM_REVISION}" "${PROVENANCE}"
  grep -Fxq "ISAAC_LAB_REVISION=${LAB_REVISION}" "${PROVENANCE}"
  grep -Fxq "ISAACTELEOP_WHEEL_SHA256=${WHEEL_SHA256}" "${PROVENANCE}"
  printf 'Validated existing overlay: %s\n' "${OVERLAY_ROOT}"
  exit 0
fi
if [[ -e "${OVERLAY_ROOT}" ]]; then
  printf 'Refusing unmarked overlay root: %s\n' "${OVERLAY_ROOT}" >&2
  exit 1
fi

partial_root="${OVERLAY_ROOT}.partial.$$"
trap 'rm -rf "${partial_root}"' EXIT INT TERM HUP
mkdir -p "${partial_root}"
"${SIM_ROOT}/python.sh" -m pip install \
  --disable-pip-version-check \
  --no-deps \
  --target "${partial_root}" \
  "${LAB_ROOT}/source/isaaclab" \
  "${WHEEL}" \
  'websockets==14.0'
cp -a "${LAB_ROOT}/source/isaaclab/config" "${partial_root}/config"

PYTHONPATH="${partial_root}:${LAB_ROOT}/source/isaaclab" \
  "${SIM_ROOT}/python.sh" -c \
  'from importlib.metadata import version; import isaaclab, isaacteleop; from isaacteleop.cloudxr.runtime import runtime_version; assert isaaclab.__version__ == "0.54.5"; assert version("websockets") == "14.0"; assert isaacteleop.__provenance_commit__ == "ca175df7afc8198cbba0592cd1b447b11a4f3165"; assert isaacteleop.__integration_commit__ == "790d6cb4e948de377975c76ed1e9cbf5098e10fc"; assert runtime_version() == "6.2.0"'

{
  printf 'ISAAC_SIM_REVISION=%s\n' "${SIM_REVISION}"
  printf 'ISAAC_LAB_REVISION=%s\n' "${LAB_REVISION}"
  printf 'ISAACTELEOP_WHEEL_SHA256=%s\n' "${WHEEL_SHA256}"
  printf 'PYTHON_VERSION=3.12\n'
  printf 'ISAAC_LAB_VERSION=0.54.5\n'
  printf 'WEBSOCKETS_VERSION=14.0\n'
  printf 'ARCHITECTURE=aarch64\n'
} >"${partial_root}/.surgisabre-overlay.env"
mv "${partial_root}" "${OVERLAY_ROOT}"
trap - EXIT INT TERM HUP
printf 'Isaac Sim overlay: %s\n' "${OVERLAY_ROOT}"
