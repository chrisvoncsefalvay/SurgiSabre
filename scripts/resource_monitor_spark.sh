#!/usr/bin/env bash
set -euo pipefail

readonly OUTPUT="${1:?output path is required}"
readonly PARENT_PID="${2:?parent PID is required}"
readonly CONTAINER_NAME="${3:-}"
readonly SYSTEMD_UNIT="${4:-}"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly INTERVAL_SECONDS="${RESOURCE_MONITOR_INTERVAL_SECONDS:-15}"
readonly STOP_MIN_AVAILABLE_KIB="${RESOURCE_STOP_MIN_AVAILABLE_KIB:-25165824}"

if [[ ! "${INTERVAL_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  printf '%s\n' "RESOURCE_MONITOR_INTERVAL_SECONDS must be a positive integer." >&2
  exit 2
fi
if [[ ! "${STOP_MIN_AVAILABLE_KIB}" =~ ^[1-9][0-9]*$ ]]; then
  printf '%s\n' "RESOURCE_STOP_MIN_AVAILABLE_KIB must be a positive integer." >&2
  exit 2
fi
if [[ -n "${CONTAINER_NAME}" && ! "${CONTAINER_NAME}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
  printf '%s\n' "Container name contains unsupported characters." >&2
  exit 2
fi
if [[ -n "${SYSTEMD_UNIT}" && ! "${SYSTEMD_UNIT}" =~ ^surgisabre-[a-zA-Z0-9_.-]+\.service$ ]]; then
  printf '%s\n' "Systemd unit must be a surgisabre project service." >&2
  exit 2
fi

mkdir -p "$(dirname "${OUTPUT}")"
while kill -0 "${PARENT_PID}" 2>/dev/null; do
  available_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
  {
    date --utc '+%Y-%m-%dT%H:%M:%SZ'
    awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ { print }' /proc/meminfo
    nvidia-smi --query-gpu=name,temperature.gpu,power.draw,utilization.gpu,utilization.encoder \
      --format=csv,noheader,nounits
    df -h "${DATA_ROOT}"
  } >>"${OUTPUT}"
  if (( available_kib < STOP_MIN_AVAILABLE_KIB )); then
    printf 'Memory safety threshold crossed: available=%s KiB threshold=%s KiB.\n' \
      "${available_kib}" "${STOP_MIN_AVAILABLE_KIB}" >>"${OUTPUT}"
    if [[ -n "${CONTAINER_NAME}" ]] && \
      [[ "$(docker inspect --format '{{ index .Config.Labels "org.surgisabre.owner" }}' "${CONTAINER_NAME}" 2>/dev/null || true)" == "gb10-arm64" ]]; then
      printf 'Stopping owned container %s before host OOM.\n' "${CONTAINER_NAME}" >>"${OUTPUT}"
      docker stop --time 30 "${CONTAINER_NAME}" >>"${OUTPUT}" 2>&1 || true
    fi
    if [[ -n "${SYSTEMD_UNIT}" ]] && systemctl --user is-active --quiet "${SYSTEMD_UNIT}"; then
      printf 'Stopping owned systemd unit %s before host OOM.\n' "${SYSTEMD_UNIT}" >>"${OUTPUT}"
      systemctl --user stop --no-block "${SYSTEMD_UNIT}" >>"${OUTPUT}" 2>&1 || true
    else
      printf 'Stopping project-owned parent PID %s before host OOM.\n' \
        "${PARENT_PID}" >>"${OUTPUT}"
      kill -TERM "${PARENT_PID}" 2>/dev/null || true
    fi
    exit 75
  fi
  sleep "${INTERVAL_SECONDS}"
done
