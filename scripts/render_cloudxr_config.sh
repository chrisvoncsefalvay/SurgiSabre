#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OUTPUT="${SURGISABRE_CLOUDXR_ENV:-${REPO_ROOT}/config/cloudxr.env}"
readonly HOST_ADDRESS="${SURGISABRE_HOST_ADDRESS:?Set SURGISABRE_HOST_ADDRESS}"
readonly PUBLIC_HOST="${SURGISABRE_PUBLIC_HOSTNAME:?Set SURGISABRE_PUBLIC_HOSTNAME}"

if [[ ! "${HOST_ADDRESS}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  printf '%s\n' "SURGISABRE_HOST_ADDRESS must be an IPv4 address." >&2
  exit 2
fi
if [[ ! "${PUBLIC_HOST}" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]]; then
  printf '%s\n' "SURGISABRE_PUBLIC_HOSTNAME contains unsupported characters." >&2
  exit 2
fi
if [[ -e "${OUTPUT}" ]]; then
  printf 'Refusing to overwrite existing configuration: %s\n' "${OUTPUT}" >&2
  exit 2
fi

umask 077
temporary="${OUTPUT}.tmp.$$"
trap 'rm -f "${temporary}"' EXIT INT TERM HUP
{
  printf 'NV_CXR_ENDPOINT_IP=%s\n' "${HOST_ADDRESS}"
  printf 'NV_CXR_MEDIA_PORT=47998\n'
  printf 'NV_CXR_STREAMSDK_ENABLE_ICE=0\n'
  printf 'NV_DEVICE_PROFILE=auto-webrtc\n'
  printf 'PROXY_PORT=48322\n'
  printf 'BACKEND_PORT=49100\n'
  printf 'TELEOP_STREAM_SERVER_IP=%s\n' "${HOST_ADDRESS}"
  printf 'TELEOP_STREAM_PORT=48322\n'
  printf 'TELEOP_WEB_CLIENT_BASE=https://%s:48322/client/\n' "${PUBLIC_HOST}"
} >"${temporary}"
mv "${temporary}" "${OUTPUT}"
trap - EXIT INT TERM HUP
printf 'CloudXR configuration: %s\n' "${OUTPUT}"
