#!/usr/bin/env bash
# Unmount (and optionally lock) a removable headphones storage device on the host.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  headphones-unmount.sh --device /dev/sdXN
  headphones-unmount.sh --uuid <UUID>
  headphones-unmount.sh --device /dev/mapper/<name> --lock-device /dev/sdXN
  headphones-unmount.sh --uuid <UUID> --lock-uuid <UUID>

Examples:
  ./scripts/headphones-unmount.sh --device /dev/sdb1
  ./scripts/headphones-unmount.sh --device /dev/mapper/luks-123 --lock-device /dev/sdb2

Notes:
  - This script runs on the host (not inside Docker).
  - Lock options are for encrypted containers after unmounting.
EOF
}

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: required command not found: $1" >&2
        exit 1
    fi
}

resolve_uuid() {
    local uuid="$1"
    local by_uuid="/dev/disk/by-uuid/$uuid"
    if [[ ! -e "$by_uuid" ]]; then
        echo "Error: UUID not found: $uuid" >&2
        exit 1
    fi
    readlink -f "$by_uuid"
}

device=""
uuid=""
lock_device=""
lock_uuid=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --device)
            device="${2:-}"
            shift 2
            ;;
        --uuid)
            uuid="${2:-}"
            shift 2
            ;;
        --lock-device)
            lock_device="${2:-}"
            shift 2
            ;;
        --lock-uuid)
            lock_uuid="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

need_cmd udisksctl
need_cmd readlink

if [[ -n "$uuid" ]]; then
    device="$(resolve_uuid "$uuid")"
fi

if [[ -n "$lock_uuid" ]]; then
    lock_device="$(resolve_uuid "$lock_uuid")"
fi

if [[ -z "$device" ]]; then
    echo "Error: --device or --uuid is required." >&2
    usage
    exit 1
fi

echo "Unmounting $device ..."
udisksctl unmount -b "$device" >/dev/null
echo "Unmounted: $device"

if [[ -n "$lock_device" ]]; then
    echo "Locking $lock_device ..."
    udisksctl lock -b "$lock_device" >/dev/null
    echo "Locked: $lock_device"
fi
