#!/bin/bash
# scripts/uninstall.sh
# Uninstall Music Ferry

set -e

DATA_DIR="$HOME/.music-ferry"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Uninstalling Music Ferry..."

# Stop and disable systemd units if they exist
if [ -f "$SYSTEMD_DIR/music-ferry.timer" ]; then
    echo "Stopping systemd timer..."
    systemctl --user stop music-ferry.timer 2>/dev/null || true
    systemctl --user disable music-ferry.timer 2>/dev/null || true
fi

if [ -f "$SYSTEMD_DIR/music-ferry.service" ]; then
    echo "Removing systemd units..."
    rm -f "$SYSTEMD_DIR/music-ferry.service"
    rm -f "$SYSTEMD_DIR/music-ferry.timer"
    systemctl --user daemon-reload
fi

# Determine install method and uninstall package
if [ -f "$DATA_DIR/.install-method" ]; then
    INSTALL_METHOD=$(cat "$DATA_DIR/.install-method")
else
    # Try to detect
    if pipx list 2>/dev/null | grep -q music-ferry; then
        INSTALL_METHOD="pipx"
    else
        INSTALL_METHOD="pip"
    fi
fi

echo "Uninstalling package (installed via $INSTALL_METHOD)..."
if [ "$INSTALL_METHOD" = "pipx" ]; then
    pipx uninstall music-ferry 2>/dev/null || true
else
    pip uninstall -y music-ferry 2>/dev/null || true
fi

# Ask about data directory
echo ""
echo "Package uninstalled."
echo ""
echo "Data directory: $DATA_DIR"
echo "Contains: config, cookies, downloaded music, library databases"
echo ""
read -p "Delete data directory? This will remove all downloaded music! [y/N]: " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing data directory..."
    rm -rf "$DATA_DIR"
    echo "Data directory removed."
else
    echo "Data directory preserved at $DATA_DIR"
fi

echo ""
echo "Uninstall complete!"
