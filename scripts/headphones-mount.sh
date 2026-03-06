#!/usr/bin/env bash
# Mount (and optionally unlock) a removable headphones storage device on the host.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  headphones-mount.sh --device /dev/sdXN
  headphones-mount.sh --uuid <UUID>
  headphones-mount.sh --unlock-device /dev/sdXN
  headphones-mount.sh --unlock-uuid <UUID>

Examples:
  ./scripts/headphones-mount.sh --device /dev/sdb1
  ./scripts/headphones-mount.sh --unlock-device /dev/sdb2
  ./scripts/headphones-mount.sh --uuid 1234-ABCD

Notes:
  - This script runs on the host (not inside Docker).
  - Unlock mode is for encrypted volumes (LUKS); it mounts the mapped device.
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

parse_mount_target() {
    local device="$1"
    findmnt -nr -S "$device" -o TARGET 2>/dev/null | head -n 1
}

parse_unlock_mapper() {
    local output="$1"
    printf '%s\n' "$output" | sed -nE 's/.* as ([^ ]+)\.?/\1/p' | head -n 1
}

device=""
uuid=""
unlock_device=""
unlock_uuid=""

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
        --unlock-device)
            unlock_device="${2:-}"
            shift 2
            ;;
        --unlock-uuid)
            unlock_uuid="${2:-}"
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
need_cmd findmnt
need_cmd readlink

if [[ -n "$uuid" ]]; then
    device="$(resolve_uuid "$uuid")"
fi

if [[ -n "$unlock_uuid" ]]; then
    unlock_device="$(resolve_uuid "$unlock_uuid")"
fi

if [[ -n "$device" && -n "$unlock_device" ]]; then
    echo "Error: use either mount mode (--device/--uuid) or unlock mode (--unlock-device/--unlock-uuid)." >&2
    exit 1
fi

mount_device=""

if [[ -n "$unlock_device" ]]; then
    echo "Unlocking $unlock_device ..."
    unlock_output="$(udisksctl unlock -b "$unlock_device")"
    mapper_device="$(parse_unlock_mapper "$unlock_output")"
    if [[ -z "$mapper_device" ]]; then
        echo "Error: unable to parse mapped device from unlock output:" >&2
        echo "$unlock_output" >&2
        exit 1
    fi
    mount_device="$mapper_device"
elif [[ -n "$device" ]]; then
    mount_device="$device"
else
    echo "Error: no device provided." >&2
    usage
    exit 1
fi

existing_target="$(parse_mount_target "$mount_device" || true)"
if [[ -n "$existing_target" ]]; then
    echo "Already mounted: $mount_device -> $existing_target"
    exit 0
fi

echo "Mounting $mount_device ..."
udisksctl mount -b "$mount_device" >/dev/null
mounted_target="$(parse_mount_target "$mount_device" || true)"

if [[ -z "$mounted_target" ]]; then
    echo "Warning: mount command succeeded but mountpoint could not be determined." >&2
    exit 0
fi

echo "Mounted: $mount_device -> $mounted_target"
echo "If needed, set paths.headphones_mount to: $mounted_target"
