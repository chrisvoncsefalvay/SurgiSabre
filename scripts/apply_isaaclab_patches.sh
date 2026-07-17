#!/usr/bin/env bash
set -euo pipefail

readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly LAB_ROOT="${DATA_ROOT}/upstream/IsaacLab"
readonly LAB_REVISION="ab419fec0ddae768952e6d56f9a317e1461d2d71"
readonly PATCHES=(
  "${REPO_ROOT}/patches/isaaclab-cloudxr-grip-readiness.patch"
  "${REPO_ROOT}/patches/isaaclab-sim601-rigid-material-compat.patch"
)

if [[ "$(git -C "${LAB_ROOT}" rev-parse HEAD)" != "${LAB_REVISION}" ]]; then
  printf '%s\n' "Isaac Lab is not at the pinned revision required by the project patches." >&2
  exit 1
fi

for patch_path in "${PATCHES[@]}"; do
  patch_name="$(basename "${patch_path}")"
  if [[ ! -s "${patch_path}" ]]; then
    printf 'Isaac Lab patch is missing or empty: %s\n' "${patch_path}" >&2
    exit 1
  fi

  if git -C "${LAB_ROOT}" apply --reverse --check "${patch_path}" 2>/dev/null; then
    printf 'Isaac Lab patch is already applied: %s\n' "${patch_name}"
    continue
  fi

  if ! git -C "${LAB_ROOT}" apply --check "${patch_path}"; then
    printf 'Isaac Lab patch cannot be applied cleanly: %s\n' "${patch_name}" >&2
    exit 1
  fi

  git -C "${LAB_ROOT}" apply "${patch_path}"
  printf 'Applied Isaac Lab patch: %s\n' "${patch_name}"
done
