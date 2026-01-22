#!/bin/bash
# scripts/install-systemd.sh
# Install systemd user units for automatic scheduling

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Verify spotify-swimmer is installed
if ! command -v spotify-swimmer &> /dev/null; then
    echo "Error: spotify-swimmer not found in PATH"
    echo "Please run install.sh first, or add ~/.local/bin to your PATH"
    exit 1
fi

echo "Installing systemd units..."

# Create systemd directory
mkdir -p "$SYSTEMD_DIR"

# Install service unit
cat > "$SYSTEMD_DIR/spotify-swimmer.service" << 'EOF'
[Unit]
Description=Spotify Swimmer - Download playlists for offline swimming
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
# Start Xvfb for headless browser, then run sync
ExecStart=/bin/bash -c 'Xvfb :99 -screen 0 1920x1080x24 & XVFB_PID=$!; sleep 1; DISPLAY=:99 spotify-swimmer sync; kill $XVFB_PID 2>/dev/null || true'
TimeoutStartSec=3600

[Install]
WantedBy=default.target
EOF

# Install timer unit
cat > "$SYSTEMD_DIR/spotify-swimmer.timer" << 'EOF'
[Unit]
Description=Run Spotify Swimmer daily

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
echo "  Enable timer:    systemctl --user enable --now spotify-swimmer.timer"
echo "  Run manually:    systemctl --user start spotify-swimmer.service"
echo "  View logs:       journalctl --user -u spotify-swimmer.service -f"
echo "  Check timer:     systemctl --user list-timers spotify-swimmer.timer"
echo "  Disable timer:   systemctl --user disable spotify-swimmer.timer"
