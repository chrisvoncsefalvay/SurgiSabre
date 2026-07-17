#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly REVISION="790d6cb4e948de377975c76ed1e9cbf5098e10fc"
readonly SOURCE_REVISION="ca175df7afc8198cbba0592cd1b447b11a4f3165"
readonly JOBS="${ISAACTELEOP_BUILD_JOBS:-8}"
readonly PATCHELF_PACKAGE_VERSION="0.17.2.4"
readonly PYTHON_VERSION="${ISAACTELEOP_PYTHON_VERSION:-3.11}"
case "${PYTHON_VERSION}" in
  3.11) readonly PYTHON_TAG="cp311" ;;
  3.12) readonly PYTHON_TAG="cp312" ;;
  *)
    printf '%s\n' "ISAACTELEOP_PYTHON_VERSION must be 3.11 or 3.12." >&2
    exit 2
    ;;
esac
readonly ARCHIVE="${DATA_ROOT}/archives/cloudxr-6.2.0/CloudXR-6.2.0-Linux-arm64-sdk.tar.gz"
readonly ARCHIVE_SHA256="3aa25e7c052aab4c2e6b1cb188272ae6d691335c586e1667e95e73c492584e88"
readonly BUILD_ROOT="${DATA_ROOT}/build/IsaacTeleop-${REVISION}-cloudxr-6.2.0-arm64-${PYTHON_TAG}-patchelf-${PATCHELF_PACKAGE_VERSION}"
readonly INSTALL_ROOT="${DATA_ROOT}/wheels/IsaacTeleop-${REVISION}-cloudxr-6.2.0-arm64-${PYTHON_TAG}-patchelf-${PATCHELF_PACKAGE_VERSION}"
readonly BUILD_MARKER="${BUILD_ROOT}/.surgisabre-build-inputs.env"
readonly PROVENANCE="${INSTALL_ROOT}/build-provenance.env"
readonly PATCHELF_ROOT="${DATA_ROOT}/runtime/build-tools/patchelf-${PATCHELF_PACKAGE_VERSION}"
readonly PATCHELF_PYTHON="${PATCHELF_ROOT}/bin/python"
readonly PATCHELF_EXECUTABLE="${PATCHELF_ROOT}/bin/patchelf"

if [[ "${ACCEPT_CLOUDXR_EULA:-}" != "Y" ]]; then
  printf '%s\n' "CloudXR licence acceptance is required before the bundled build." >&2
  exit 2
fi
if [[ ! "${JOBS}" =~ ^[1-9][0-9]*$ ]] || (( JOBS > 16 )); then
  printf '%s\n' "ISAACTELEOP_BUILD_JOBS must be between 1 and 16." >&2
  exit 2
fi
for command_name in cmake ctest file git python3 sha256sum uv; do
  command -v "${command_name}" >/dev/null
done
[[ "$(uname -m)" == "aarch64" ]]
printf '%s  %s\n' "${ARCHIVE_SHA256}" "${ARCHIVE}" | sha256sum --check

readonly BUILD_SOURCE="$(${REPO_ROOT}/scripts/prepare_isaacteleop_build_tree_spark.sh)"
readonly BUNDLE_ARCHIVE="${BUILD_SOURCE}/deps/cloudxr/CloudXR-6.2.0-Linux-arm64-sdk.tar.gz"

if [[ -s "${PROVENANCE}" ]]; then
  mapfile -t retained_wheels < <(find "${INSTALL_ROOT}/wheels" -maxdepth 1 -type f -name 'isaacteleop-*.whl' -print)
  [[ "${#retained_wheels[@]}" -eq 1 ]]
  retained_sha256="$(sha256sum "${retained_wheels[0]}" | awk '{ print $1 }')"
  grep -Fxq "ISAACTELEOP_INTEGRATION_REVISION=${REVISION}" "${PROVENANCE}"
  grep -Fxq "CLOUDXR_RUNTIME_SHA256=${ARCHIVE_SHA256}" "${PROVENANCE}"
  grep -Fxq "PATCHELF_PACKAGE_VERSION=${PATCHELF_PACKAGE_VERSION}" "${PROVENANCE}"
  grep -Fxq "PYTHON_VERSION=${PYTHON_VERSION}" "${PROVENANCE}"
  grep -Fxq "WHEEL_SHA256=${retained_sha256}" "${PROVENANCE}"
  printf 'Validated existing generated wheel: %s\n' "${retained_wheels[0]}"
  exit 0
fi
if [[ -e "${INSTALL_ROOT}" ]]; then
  printf 'Refusing unmarked generated install root: %s\n' "${INSTALL_ROOT}" >&2
  exit 1
fi
if [[ -e "${BUILD_ROOT}" && ! -s "${BUILD_MARKER}" ]]; then
  printf 'Refusing unmarked generated build root: %s\n' "${BUILD_ROOT}" >&2
  exit 1
fi

mkdir -p "${BUILD_ROOT}" "${DATA_ROOT}/logs/resources"
if [[ ! -s "${BUILD_MARKER}" ]]; then
  {
    printf 'ISAACTELEOP_INTEGRATION_REVISION=%s\n' "${REVISION}"
    printf 'CLOUDXR_RUNTIME_VERSION=6.2.0\n'
    printf 'CLOUDXR_RUNTIME_SHA256=%s\n' "${ARCHIVE_SHA256}"
    printf 'PATCHELF_PACKAGE_VERSION=%s\n' "${PATCHELF_PACKAGE_VERSION}"
    printf 'PYTHON_VERSION=%s\n' "${PYTHON_VERSION}"
    printf 'ARCHITECTURE=aarch64\n'
  } >"${BUILD_MARKER}"
fi
grep -Fxq "ISAACTELEOP_INTEGRATION_REVISION=${REVISION}" "${BUILD_MARKER}"
grep -Fxq "CLOUDXR_RUNTIME_SHA256=${ARCHIVE_SHA256}" "${BUILD_MARKER}"
grep -Fxq "PATCHELF_PACKAGE_VERSION=${PATCHELF_PACKAGE_VERSION}" "${BUILD_MARKER}"
grep -Fxq "PYTHON_VERSION=${PYTHON_VERSION}" "${BUILD_MARKER}"

if [[ -e "${BUNDLE_ARCHIVE}" ]]; then
  printf '%s  %s\n' "${ARCHIVE_SHA256}" "${BUNDLE_ARCHIVE}" | sha256sum --check
else
  install -m 0644 "${ARCHIVE}" "${BUNDLE_ARCHIVE}"
fi

"${REPO_ROOT}/scripts/check_capacity_spark.sh" --build
monitor_log="${DATA_ROOT}/logs/resources/build-isaacteleop-$(date --utc '+%Y%m%dT%H%M%SZ').log"
"${REPO_ROOT}/scripts/resource_monitor_spark.sh" "${monitor_log}" "$$" &
monitor_pid=$!
cleanup_monitor() {
  set +e
  kill "${monitor_pid}" 2>/dev/null
  wait "${monitor_pid}" 2>/dev/null
  return 0
}
trap cleanup_monitor EXIT

export UV_PYTHON_INSTALL_DIR="${DATA_ROOT}/runtime/python/uv-python"
export UV_CACHE_DIR="${DATA_ROOT}/cache/uv"
export UV_TOOL_DIR="${DATA_ROOT}/runtime/python/uv-tools"
export UV_TOOL_BIN_DIR="${DATA_ROOT}/runtime/python/uv-tool-bin"

if [[ ! -x "${PATCHELF_EXECUTABLE}" ]]; then
  uv venv --python 3.11 "${PATCHELF_ROOT}"
  uv pip install --python "${PATCHELF_PYTHON}" "patchelf==${PATCHELF_PACKAGE_VERSION}"
fi
[[ "$(${PATCHELF_EXECUTABLE} --version)" == "patchelf 0.17.2" ]]
patchelf_sha256="$(sha256sum "${PATCHELF_EXECUTABLE}" | awk '{ print $1 }')"
export PATH="${PATCHELF_ROOT}/bin:${PATH}"

cmake -S "${BUILD_SOURCE}" -B "${BUILD_ROOT}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${INSTALL_ROOT}" \
  -DISAAC_TELEOP_PYTHON_VERSION="${PYTHON_VERSION}" \
  -DBUILD_EXAMPLES=OFF \
  -DBUILD_PLUGINS=OFF \
  -DBUILD_VIZ=OFF \
  -DBUILD_TESTING=ON \
  -DENABLE_CLANG_FORMAT_CHECK=OFF \
  -DENABLE_CLOUDXR_BUNDLE_CHECK=ON \
  -DCXR_RUNTIME_SDK_VERSION_OVERRIDE=6.2.0

cmake --build "${BUILD_ROOT}" --target python_wheel --parallel "${JOBS}"
ctest --test-dir "${BUILD_ROOT}" -R '^retargeting_test_dvrk_psm_retargeters$' --output-on-failure
ctest --test-dir "${BUILD_ROOT}" -R '^cloudxr_test_' --output-on-failure
cmake --install "${BUILD_ROOT}"

mapfile -t wheels < <(find "${INSTALL_ROOT}/wheels" -maxdepth 1 -type f -name 'isaacteleop-*.whl' -print)
if [[ "${#wheels[@]}" -ne 1 ]]; then
  printf 'Expected exactly one generated wheel, found %d.\n' "${#wheels[@]}" >&2
  exit 1
fi
readonly wheel="${wheels[0]}"
[[ "$(basename "${wheel}")" == *-${PYTHON_TAG}-${PYTHON_TAG}-linux_aarch64.whl ]]
wheel_sha256="$(sha256sum "${wheel}" | awk '{ print $1 }')"

python3 - "${wheel}" "${PATCHELF_EXECUTABLE}" <<'PY'
import os
import struct
import subprocess
import sys
import tempfile
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    names = [name for name in archive.namelist() if name.endswith("/cloudxr/native/libcloudxr.so")]
    assert len(names) == 1, names
    binary = archive.read(names[0])
    assert binary[:4] == b"\x7fELF"
    assert struct.unpack("<H", binary[18:20])[0] == 183
    with tempfile.NamedTemporaryFile() as extracted:
        extracted.write(binary)
        extracted.flush()
        os.chmod(extracted.name, 0o755)
        needed = subprocess.check_output(
            [sys.argv[2], "--print-needed", extracted.name], text=True
        ).splitlines()
        assert "libssl.so.3" not in needed, needed
PY

temporary_provenance="${PROVENANCE}.tmp.$$"
mkdir -p "$(dirname "${PROVENANCE}")"
{
  printf 'ISAACTELEOP_INTEGRATION_REVISION=%s\n' "${REVISION}"
  printf 'ISAACTELEOP_PROVENANCE_REVISION=%s\n' "${SOURCE_REVISION}"
  printf 'CLOUDXR_RUNTIME_VERSION=6.2.0\n'
  printf 'CLOUDXR_RUNTIME_SHA256=%s\n' "${ARCHIVE_SHA256}"
  printf 'PATCHELF_PACKAGE_VERSION=%s\n' "${PATCHELF_PACKAGE_VERSION}"
  printf 'PATCHELF_SHA256=%s\n' "${patchelf_sha256}"
  printf 'PYTHON_VERSION=%s\n' "${PYTHON_VERSION}"
  printf 'ARCHITECTURE=aarch64\n'
  printf 'WHEEL_FILE=%s\n' "$(basename "${wheel}")"
  printf 'WHEEL_SHA256=%s\n' "${wheel_sha256}"
  printf 'BUILT_AT=%s\n' "$(date --utc '+%Y-%m-%dT%H:%M:%SZ')"
} >"${temporary_provenance}"
mv "${temporary_provenance}" "${PROVENANCE}"

cleanup_monitor
trap - EXIT
printf '%s  %s\n' "${wheel_sha256}" "${wheel}"
printf 'Resource monitor: %s\n' "${monitor_log}"
