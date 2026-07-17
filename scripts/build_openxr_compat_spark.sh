#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly BUILD_ROOT="${DATA_ROOT}/runtime/openxr-compat-sim601"
readonly SOURCE="${REPO_ROOT}/compat/openxr_required_extensions.c"
readonly OUTPUT="${BUILD_ROOT}/libisaac_teleop_openxr_extensions.so"
readonly PROVENANCE="${BUILD_ROOT}/provenance.env"

[[ "$(uname -m)" == "aarch64" ]]
mapfile -t include_roots < <(
  find "${DATA_ROOT}/wheels" -mindepth 2 -maxdepth 2 -type d \
    -path '*cp312*/include' -print
)
if [[ "${#include_roots[@]}" -ne 1 ]]; then
  printf 'Expected one CPython 3.12 IsaacTeleop include tree, found %d.\n' \
    "${#include_roots[@]}" >&2
  exit 1
fi
readonly INCLUDE_ROOT="${include_roots[0]}"
[[ -f "${INCLUDE_ROOT}/openxr/openxr.h" ]]
mkdir -p "${BUILD_ROOT}"

gcc -shared -fPIC -O2 -Wall -Wextra -Werror \
  -I"${INCLUDE_ROOT}" \
  -o "${OUTPUT}.partial" \
  "${SOURCE}" \
  -ldl
mv "${OUTPUT}.partial" "${OUTPUT}"

readelf -h "${OUTPUT}" | grep -Fq 'Machine:                           AArch64'
if readelf -d "${OUTPUT}" | grep -Fq 'libstdc++'; then
  printf '%s\n' "Unexpected C++ runtime dependency." >&2
  exit 1
fi

{
  printf 'SOURCE_SHA256=%s\n' "$(sha256sum "${SOURCE}" | cut -d' ' -f1)"
  printf 'BINARY_SHA256=%s\n' "$(sha256sum "${OUTPUT}" | cut -d' ' -f1)"
  printf 'OPENXR_HEADER_SHA256=%s\n' \
    "$(sha256sum "${INCLUDE_ROOT}/openxr/openxr.h" | cut -d' ' -f1)"
  printf 'ARCHITECTURE=aarch64\n'
} >"${PROVENANCE}"

printf 'OpenXR compatibility library: %s\n' "${OUTPUT}"
sha256sum "${OUTPUT}"
