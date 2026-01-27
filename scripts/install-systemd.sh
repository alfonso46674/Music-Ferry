#!/bin/bash
# scripts/install-systemd.sh
# Install systemd user units for automatic scheduling

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_DIR="$HOME/.config/systemd/user"
DATA_DIR="$HOME/.music-ferry"
VENV_BIN="$DATA_DIR/venv/bin"
RUN_CMD="music-ferry"

if [ -x "$VENV_BIN/music-ferry" ]; then
    RUN_CMD="$VENV_BIN/music-ferry"
elif command -v music-ferry &> /dev/null; then
    RUN_CMD="$(command -v music-ferry)"
else
    echo "Error: music-ferry not found in PATH or $VENV_BIN"
    echo "Please run install.sh first."
    exit 1
fi

echo "Installing systemd units..."

# Create systemd directory
mkdir -p "$SYSTEMD_DIR"
mkdir -p "$DATA_DIR/logs"

# Install service unit
cat > "$SYSTEMD_DIR/music-ferry.service" << EOF
[Unit]
Description=Music Ferry - Download playlists for offline listening
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=RUN_CMD=$RUN_CMD
StandardOutput=append:%h/.music-ferry/logs/sync.log
StandardError=append:%h/.music-ferry/logs/sync.log
# Start Xvfb for headless browser, then run sync
ExecStart=/bin/bash -c 'Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 & XVFB_PID=\$!; sleep 1; DISPLAY=:99 "$RUN_CMD" sync; kill \$XVFB_PID 2>/dev/null || true'
TimeoutStartSec=3600

[Install]
WantedBy=default.target
EOF

# Install timer unit
cat > "$SYSTEMD_DIR/music-ferry.timer" << 'EOF'
[Unit]
Description=Run Music Ferry daily

[Timer]
OnCalendar=*-*-* 05:00:00
RandomizedDelaySec=3h
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Reload systemd
systemctl --user daemon-reload

echo ""
echo "Systemd units installed!"
echo ""
echo "Commands:"
echo "  Enable timer:    systemctl --user enable --now music-ferry.timer"
echo "  Run manually:    systemctl --user start music-ferry.service"
echo "  View logs:       journalctl --user -u music-ferry.service -f"
echo "  Check timer:     systemctl --user list-timers music-ferry.timer"
echo "  Disable timer:   systemctl --user disable music-ferry.timer"
