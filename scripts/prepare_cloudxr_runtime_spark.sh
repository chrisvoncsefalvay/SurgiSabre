#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly VENV_ROOT="${DATA_ROOT}/runtime/cloudxr-venv-cp311"
readonly PYTHON="${VENV_ROOT}/bin/python"
readonly INSTALL_ROOT="${DATA_ROOT}/runtime/cloudxr-6.2.0-arm64"
readonly STATIC_ROOT="${INSTALL_ROOT}/static-client"
readonly CERT_ROOT="${INSTALL_ROOT}/certs"
readonly PROVENANCE="${INSTALL_ROOT}/runtime-provenance.env"

if [[ "${ACCEPT_CLOUDXR_EULA:-}" != "Y" ]]; then
  printf '%s\n' "Set ACCEPT_CLOUDXR_EULA=Y after accepting NVIDIA's CloudXR licence." >&2
  exit 2
fi
for command_name in sha256sum uv; do
  command -v "${command_name}" >/dev/null
done
[[ "$(uname -m)" == "aarch64" ]]

mapfile -t provenance_files < <(
  find "${DATA_ROOT}/wheels" -mindepth 2 -maxdepth 2 -type f \
    -path '*cp311*/build-provenance.env' -print
)
if [[ "${#provenance_files[@]}" -ne 1 ]]; then
  printf 'Expected one CPython 3.11 IsaacTeleop build, found %d.\n' \
    "${#provenance_files[@]}" >&2
  exit 1
fi
readonly WHEEL_PROVENANCE="${provenance_files[0]}"
readonly WHEEL_ROOT="$(dirname "${WHEEL_PROVENANCE}")"
readonly WHEEL_NAME="$(sed -n 's/^WHEEL_FILE=//p' "${WHEEL_PROVENANCE}")"
readonly WHEEL_SHA256="$(sed -n 's/^WHEEL_SHA256=//p' "${WHEEL_PROVENANCE}")"
readonly WHEEL="${WHEEL_ROOT}/wheels/${WHEEL_NAME}"
[[ "${WHEEL_NAME}" == *-cp311-cp311-linux_aarch64.whl ]]
[[ "${WHEEL_SHA256}" =~ ^[0-9a-f]{64}$ ]]
grep -Fxq \
  'ISAACTELEOP_INTEGRATION_REVISION=790d6cb4e948de377975c76ed1e9cbf5098e10fc' \
  "${WHEEL_PROVENANCE}"
grep -Fxq 'CLOUDXR_RUNTIME_VERSION=6.2.0' "${WHEEL_PROVENANCE}"
printf '%s  %s\n' "${WHEEL_SHA256}" "${WHEEL}" | sha256sum --check

export UV_PYTHON_INSTALL_DIR="${DATA_ROOT}/runtime/python/uv-python"
export UV_CACHE_DIR="${DATA_ROOT}/cache/uv"
if [[ ! -x "${PYTHON}" ]]; then
  uv venv --python 3.11.15 "${VENV_ROOT}"
fi
uv pip install --python "${PYTHON}" --no-deps \
  'numpy==2.4.6' \
  'websockets==14.0' \
  "${WHEEL}"

PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - <<'PY'
from importlib.metadata import version
import isaacteleop
from isaacteleop.cloudxr.runtime import runtime_version

assert version("numpy") == "2.4.6"
assert version("websockets") == "14.0"
assert isaacteleop.__version__ == "1.4+local"
assert isaacteleop.__provenance_commit__ == "ca175df7afc8198cbba0592cd1b447b11a4f3165"
assert isaacteleop.__integration_commit__ == "790d6cb4e948de377975c76ed1e9cbf5098e10fc"
assert runtime_version() == "6.2.0"
PY

mkdir -p "${STATIC_ROOT}" "${CERT_ROOT}"
TELEOP_WEB_CLIENT_STATIC_DIR="${STATIC_ROOT}" PYTHONDONTWRITEBYTECODE=1 \
  "${PYTHON}" -c \
  'from isaacteleop.cloudxr.oob_teleop_env import require_web_client_static_dir; print(require_web_client_static_dir())'

for asset in index.html bundle.js; do
  [[ -s "${STATIC_ROOT}/${asset}" ]]
done

cert_source="${SURGISABRE_TLS_CERT_PATH:-}"
key_source="${SURGISABRE_TLS_KEY_PATH:-}"
if [[ -n "${cert_source}" || -n "${key_source}" ]]; then
  if [[ ! -s "${cert_source}" || ! -s "${key_source}" ]]; then
    printf '%s\n' "Both SURGISABRE_TLS_CERT_PATH and SURGISABRE_TLS_KEY_PATH are required." >&2
    exit 2
  fi
  install -m 0644 "${cert_source}" "${CERT_ROOT}/server.crt"
  install -m 0600 "${key_source}" "${CERT_ROOT}/server.key"
fi

{
  printf 'ISAACTELEOP_INTEGRATION_REVISION=790d6cb4e948de377975c76ed1e9cbf5098e10fc\n'
  printf 'ISAACTELEOP_PROVENANCE_REVISION=ca175df7afc8198cbba0592cd1b447b11a4f3165\n'
  printf 'ISAACTELEOP_WHEEL_SHA256=%s\n' "${WHEEL_SHA256}"
  printf 'CLOUDXR_RUNTIME_VERSION=6.2.0\n'
  printf 'PYTHON_VERSION=3.11.15\n'
  printf 'ARCHITECTURE=aarch64\n'
  printf 'STATIC_INDEX_SHA256=%s\n' \
    "$(sha256sum "${STATIC_ROOT}/index.html" | cut -d' ' -f1)"
  printf 'STATIC_BUNDLE_SHA256=%s\n' \
    "$(sha256sum "${STATIC_ROOT}/bundle.js" | cut -d' ' -f1)"
} >"${PROVENANCE}"

printf 'CloudXR runtime root: %s\n' "${INSTALL_ROOT}"
printf 'Static client root: %s\n' "${STATIC_ROOT}"
if [[ ! -s "${CERT_ROOT}/server.crt" ]]; then
  printf '%s\n' "No trusted certificate was installed. The launcher will create a self-signed pair."
fi
