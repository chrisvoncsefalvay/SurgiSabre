#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly SIM_SOURCE_ROOT="${ISAAC_SIM_SOURCE_ROOT:-${DATA_ROOT}/upstream/IsaacSim}"
readonly SIM_REVISION="987015050efebfd0cd5d3736ae47fffe5adee308"

[[ "$(uname -m)" == "aarch64" ]]
[[ "$(git -C "${SIM_SOURCE_ROOT}" rev-parse HEAD)" == "${SIM_REVISION}" ]]
[[ -z "$(git -C "${SIM_SOURCE_ROOT}" status --porcelain)" ]]

"${REPO_ROOT}/scripts/check_capacity_spark.sh" --build
mkdir -p "${DATA_ROOT}/logs/resources"
monitor_log="${DATA_ROOT}/logs/resources/build-isaacsim-$(date --utc '+%Y%m%dT%H%M%SZ').log"
"${REPO_ROOT}/scripts/resource_monitor_spark.sh" "${monitor_log}" "$$" &
monitor_pid=$!
cleanup() {
  set +e
  kill "${monitor_pid}" 2>/dev/null
  wait "${monitor_pid}" 2>/dev/null
}
trap cleanup EXIT INT TERM HUP

(cd "${SIM_SOURCE_ROOT}" && ./build.sh)

cleanup
trap - EXIT INT TERM HUP
printf 'Isaac Sim build: %s\n' "${SIM_SOURCE_ROOT}/_build/linux-aarch64/release"
printf 'Resource monitor: %s\n' "${monitor_log}"
