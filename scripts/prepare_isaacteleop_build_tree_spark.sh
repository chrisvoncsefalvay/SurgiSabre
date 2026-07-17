#!/usr/bin/env bash
set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly SOURCE_ROOT="${DATA_ROOT}/upstream/IsaacTeleop"
readonly REVISION="790d6cb4e948de377975c76ed1e9cbf5098e10fc"
readonly BUILD_SOURCE="${DATA_ROOT}/build-sources/IsaacTeleop-${REVISION}-cloudxr-6.2.0-arm64"
readonly VERSION_PATCH="${REPO_ROOT}/patches/isaacteleop-790d6cb-cloudxr-version-override.patch"
readonly OOB_PATCH="${REPO_ROOT}/patches/isaacteleop-790d6cb-oob-hub-only.patch"
readonly PROVENANCE_PATCH="${REPO_ROOT}/patches/isaacteleop-790d6cb-build-provenance.patch"
readonly VERSION_FILE="src/core/cloudxr/python/CMakeLists.txt"
readonly OOB_FILE="src/core/cloudxr/python/wss.py"
readonly PROVENANCE_FILE="src/core/python/isaacteleop_init.py"

[[ "$(uname -m)" == "aarch64" ]]
[[ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" == "${REVISION}" ]]
[[ -z "$(git -C "${SOURCE_ROOT}" status --porcelain)" ]]

mkdir -p "$(dirname "${BUILD_SOURCE}")"
if [[ ! -e "${BUILD_SOURCE}/.git" ]]; then
  git -C "${SOURCE_ROOT}" worktree add --quiet --detach "${BUILD_SOURCE}" "${REVISION}"
fi
[[ "$(git -C "${BUILD_SOURCE}" rev-parse HEAD)" == "${REVISION}" ]]

if ! grep -Fq "CXR_RUNTIME_SDK_VERSION_OVERRIDE" "${BUILD_SOURCE}/${VERSION_FILE}"; then
  [[ -z "$(git -C "${BUILD_SOURCE}" status --porcelain)" ]]
  git -C "${BUILD_SOURCE}" apply "${VERSION_PATCH}"
fi
if ! grep -Fq "TELEOP_OOB_ADB_AUTOMATION" "${BUILD_SOURCE}/${OOB_FILE}"; then
  git -C "${BUILD_SOURCE}" apply "${OOB_PATCH}"
fi
if ! grep -Fq "__integration_commit__" "${BUILD_SOURCE}/${PROVENANCE_FILE}"; then
  git -C "${BUILD_SOURCE}" apply "${PROVENANCE_PATCH}"
fi

expected_changed_files="${VERSION_FILE}"$'\n'"${OOB_FILE}"$'\n'"${PROVENANCE_FILE}"
[[ "$(git -C "${BUILD_SOURCE}" diff --name-only)" == "${expected_changed_files}" ]]
printf '%s  %s\n' \
  "988f6b82c245a6a54172dbf3ae45d61b3bffc7381fca56f57aa08020a40df7bc" \
  "${BUILD_SOURCE}/${VERSION_FILE}" | sha256sum --check >/dev/null
printf '%s  %s\n' \
  "d03300628d8836c163395e8ed99240b513fc1cacabcfd147484dac638aa012ad" \
  "${BUILD_SOURCE}/${OOB_FILE}" | sha256sum --check >/dev/null
printf '%s  %s\n' \
  "f24d10038402cebbbcdc6c458c76b7afdc4cca6fc0418be2f6ced78463716586" \
  "${BUILD_SOURCE}/${PROVENANCE_FILE}" | sha256sum --check >/dev/null

untracked_files="$(git -C "${BUILD_SOURCE}" ls-files --others --exclude-standard)"
allowed_archive="deps/cloudxr/CloudXR-6.2.0-Linux-arm64-sdk.tar.gz"
if [[ -n "${untracked_files}" ]]; then
  [[ "${untracked_files}" == "${allowed_archive}" ]]
  printf '%s  %s\n' \
    "3aa25e7c052aab4c2e6b1cb188272ae6d691335c586e1667e95e73c492584e88" \
    "${BUILD_SOURCE}/${allowed_archive}" | sha256sum --check >/dev/null
fi

printf '%s\n' "${BUILD_SOURCE}"

