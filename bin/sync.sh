#!/bin/bash
# bin/sync.sh
# Entry point for systemd service

set -e

INSTALL_DIR="$HOME/.spotify-swimmer"

# Start Xvfb for headless browser (needed for Spotify)
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
export DISPLAY=:99

# Give Xvfb time to start
sleep 1

# Run the installed CLI
"$INSTALL_DIR/.venv/bin/spotify-swimmer" "$@"
EXIT_CODE=$?

# Cleanup
kill $XVFB_PID 2>/dev/null || true

exit $EXIT_CODE
