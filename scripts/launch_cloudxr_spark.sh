#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly PYTHON="${DATA_ROOT}/runtime/cloudxr-venv-cp311/bin/python"
readonly INSTALL_ROOT="${DATA_ROOT}/runtime/cloudxr-6.2.0-arm64"
readonly STATIC_ROOT="${INSTALL_ROOT}/static-client"
readonly PROVENANCE="${INSTALL_ROOT}/runtime-provenance.env"
readonly ENV_CONFIG="${SURGISABRE_CLOUDXR_ENV:-${REPO_ROOT}/config/cloudxr.env}"
readonly PUBLIC_HOST="${SURGISABRE_PUBLIC_HOSTNAME:-${SURGISABRE_HOST_ADDRESS:?Set SURGISABRE_HOST_ADDRESS}}"
readonly MEDIA_PORT=47998

if [[ "${ACCEPT_CLOUDXR_EULA:-}" != "Y" ]]; then
  printf '%s\n' "Set ACCEPT_CLOUDXR_EULA=Y after accepting NVIDIA's CloudXR licence." >&2
  exit 2
fi
[[ -x "${PYTHON}" ]]
[[ -s "${PROVENANCE}" ]]
[[ -s "${ENV_CONFIG}" ]]
grep -Fxq \
  'ISAACTELEOP_INTEGRATION_REVISION=790d6cb4e948de377975c76ed1e9cbf5098e10fc' \
  "${PROVENANCE}"
grep -Fxq 'CLOUDXR_RUNTIME_VERSION=6.2.0' "${PROVENANCE}"
grep -Fxq "NV_CXR_ENDPOINT_IP=${SURGISABRE_HOST_ADDRESS}" "${ENV_CONFIG}"
grep -Fxq "NV_CXR_MEDIA_PORT=${MEDIA_PORT}" "${ENV_CONFIG}"
grep -Fxq 'NV_CXR_STREAMSDK_ENABLE_ICE=0' "${ENV_CONFIG}"

for asset in index.html bundle.js; do
  [[ -s "${STATIC_ROOT}/${asset}" ]]
done
for port in 48322 49100; do
  if ss -H -lnt "sport = :${port}" | grep -q .; then
    printf 'Required CloudXR TCP port is already in use: %s\n' "${port}" >&2
    exit 1
  fi
done
if ss -H -lnu "sport = :${MEDIA_PORT}" | grep -q .; then
  printf 'Required CloudXR UDP port is already in use: %s\n' "${MEDIA_PORT}" >&2
  exit 1
fi

"${REPO_ROOT}/scripts/check_capacity_spark.sh" --runtime
mkdir -p "${DATA_ROOT}/logs/resources"
monitor_log="${DATA_ROOT}/logs/resources/cloudxr-$(date --utc '+%Y%m%dT%H%M%SZ').log"
"${REPO_ROOT}/scripts/resource_monitor_spark.sh" "${monitor_log}" "$$" &

export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=ascii:backslashreplace
export PYTHONUNBUFFERED=1
export TELEOP_WEB_CLIENT_STATIC_DIR="${STATIC_ROOT}"
export SURGISABRE_RUNTIME_PROFILE=gb10_arm64

printf 'CloudXR resource log: %s\n' "${monitor_log}"
printf 'Quest client: https://%s:48322/client/?immersiveMode=vr\n' "${PUBLIC_HOST}"
exec "${PYTHON}" -m isaacteleop.cloudxr \
  --cloudxr-install-dir "${INSTALL_ROOT}" \
  --cloudxr-env-config "${ENV_CONFIG}" \
  --accept-eula \
  --host-client
