#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly UPSTREAM_ROOT="${DATA_ROOT}/upstream"

readonly ISAAC_SIM_REPOSITORY="https://github.com/isaac-sim/IsaacSim.git"
readonly ISAAC_SIM_REVISION="987015050efebfd0cd5d3736ae47fffe5adee308"
readonly ISAAC_LAB_REPOSITORY="https://github.com/isaac-sim/IsaacLab.git"
readonly ISAAC_LAB_REVISION="ab419fec0ddae768952e6d56f9a317e1461d2d71"
readonly ISAAC_TELEOP_REPOSITORY="https://github.com/NVIDIA/IsaacTeleop.git"
readonly ISAAC_TELEOP_SOURCE_REVISION="ca175df7afc8198cbba0592cd1b447b11a4f3165"
readonly ISAAC_TELEOP_INTEGRATION_REVISION="790d6cb4e948de377975c76ed1e9cbf5098e10fc"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_repository() {
  local directory="$1"
  local repository="$2"
  mkdir -p "${directory}"
  if [[ ! -d "${directory}/.git" ]]; then
    git -C "${directory}" init --quiet
  fi
  if git -C "${directory}" remote get-url origin >/dev/null 2>&1; then
    git -C "${directory}" remote set-url origin "${repository}"
  else
    git -C "${directory}" remote add origin "${repository}"
  fi
}

checkout_revision() {
  local directory="$1"
  local repository="$2"
  local revision="$3"
  ensure_repository "${directory}" "${repository}"
  if [[ -n "$(git -C "${directory}" status --porcelain)" ]]; then
    fail "refusing to replace a modified checkout: ${directory}"
  fi
  git -C "${directory}" fetch --quiet --no-tags --filter=blob:none origin "${revision}"
  git -C "${directory}" checkout --quiet --detach "${revision}"
  [[ "$(git -C "${directory}" rev-parse HEAD)" == "${revision}" ]] || \
    fail "checkout mismatch in ${directory}"
}

for command_name in git; do
  command -v "${command_name}" >/dev/null || fail "missing command: ${command_name}"
done
[[ "$(uname -m)" == "aarch64" ]] || fail "the reference bootstrap requires aarch64"

mkdir -p "${UPSTREAM_ROOT}"
checkout_revision \
  "${UPSTREAM_ROOT}/IsaacSim" "${ISAAC_SIM_REPOSITORY}" "${ISAAC_SIM_REVISION}"
checkout_revision \
  "${UPSTREAM_ROOT}/IsaacLab" "${ISAAC_LAB_REPOSITORY}" "${ISAAC_LAB_REVISION}"
checkout_revision \
  "${UPSTREAM_ROOT}/IsaacTeleop" "${ISAAC_TELEOP_REPOSITORY}" \
  "${ISAAC_TELEOP_INTEGRATION_REVISION}"

# The tested integration commit is based on the PR source revision. Retain both
# identities so provenance can distinguish the upstream source from the local
# integration commit.
git -C "${UPSTREAM_ROOT}/IsaacTeleop" merge-base --is-ancestor \
  "${ISAAC_TELEOP_SOURCE_REVISION}" "${ISAAC_TELEOP_INTEGRATION_REVISION}" || \
  fail "IsaacTeleop integration does not contain the pinned source revision"

printf 'Isaac Sim: %s\n' "$(git -C "${UPSTREAM_ROOT}/IsaacSim" rev-parse HEAD)"
printf 'Isaac Lab: %s\n' "$(git -C "${UPSTREAM_ROOT}/IsaacLab" rev-parse HEAD)"
printf 'IsaacTeleop source: %s\n' "${ISAAC_TELEOP_SOURCE_REVISION}"
printf 'IsaacTeleop integration: %s\n' \
  "$(git -C "${UPSTREAM_ROOT}/IsaacTeleop" rev-parse HEAD)"
