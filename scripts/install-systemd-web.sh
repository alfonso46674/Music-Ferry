#!/usr/bin/env bash
# Install Music Ferry Web UI as a systemd user service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="music-ferry-web.service"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "=== Music Ferry Web UI Service Installer ==="
echo

# Check if running as root (we want user services)
if [[ $EUID -eq 0 ]]; then
    echo "Error: This script should NOT be run as root."
    echo "It installs a user-level systemd service."
    exit 1
fi

# Create systemd user directory if needed
mkdir -p "$SYSTEMD_USER_DIR"

# Check if venv exists
VENV_DIR="${HOME}/.music-ferry/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Install/upgrade music-ferry
echo "Installing music-ferry..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install "$REPO_DIR"

# Copy service file
echo "Installing systemd service..."
cp "$REPO_DIR/systemd/$SERVICE_NAME" "$SYSTEMD_USER_DIR/$SERVICE_NAME"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl --user daemon-reload

# Enable and start service
echo "Enabling and starting service..."
systemctl --user enable --now "$SERVICE_NAME"

echo
echo "=== Installation complete! ==="
echo
echo "Service status:"
systemctl --user status "$SERVICE_NAME" --no-pager || true
echo
echo "Useful commands:"
echo "  View logs:    journalctl --user -u $SERVICE_NAME -f"
echo "  Restart:      systemctl --user restart $SERVICE_NAME"
echo "  Stop:         systemctl --user stop $SERVICE_NAME"
echo "  Disable:      systemctl --user disable $SERVICE_NAME"
echo
echo "Web UI available at: http://127.0.0.1:4444"
echo
echo "For reverse proxy setup, see the documentation."
