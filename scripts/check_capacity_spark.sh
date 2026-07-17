#!/usr/bin/env bash
set -euo pipefail

readonly MODE="${1:---runtime}"
readonly DATA_ROOT="${SURGISABRE_DATA_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/surgisabre}"
readonly MIN_LOCAL_DISK_KIB="${MIN_LOCAL_DISK_KIB:-83886080}"

case "${MODE}" in
  --build)
    readonly MIN_RAM_KIB="${MIN_BUILD_RAM_KIB:-50331648}"
    ;;
  --runtime)
    readonly MIN_RAM_KIB="${MIN_RUNTIME_RAM_KIB:-50331648}"
    ;;
  *)
    printf 'Usage: %s [--build|--runtime]\n' "$0" >&2
    exit 2
    ;;
esac

available_ram_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
swap_total_kib="$(awk '/^SwapTotal:/ { print $2 }' /proc/meminfo)"
swap_free_kib="$(awk '/^SwapFree:/ { print $2 }' /proc/meminfo)"
mkdir -p "${DATA_ROOT}"
local_disk_kib="$(df --output=avail -k "${DATA_ROOT}" | tail -n 1 | tr -d ' ')"
gpu_utilisation="$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -n 1 | tr -d ' ')"

printf 'Capacity: RAM available=%s KiB, swap=%s/%s KiB free, local disk=%s KiB, GPU utilisation=%s percent\n' \
  "${available_ram_kib}" "${swap_free_kib}" "${swap_total_kib}" \
  "${local_disk_kib}" "${gpu_utilisation}"

if (( available_ram_kib < MIN_RAM_KIB )); then
  printf 'Insufficient available unified memory: need at least %s KiB for %s.\n' \
    "${MIN_RAM_KIB}" "${MODE}" >&2
  exit 1
fi
if (( local_disk_kib < MIN_LOCAL_DISK_KIB )); then
  printf 'Insufficient local disk: need at least %s KiB for %s.\n' \
    "${MIN_LOCAL_DISK_KIB}" "${MODE}" >&2
  exit 1
fi
if (( gpu_utilisation > 90 )); then
  printf 'GPU utilisation is already %s percent; refusing a concurrent heavy operation.\n' \
    "${gpu_utilisation}" >&2
  exit 1
fi

