#!/bin/bash
# scripts/install.sh
# Install Spotify Swimmer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$HOME/.spotify-swimmer"

echo "Installing Spotify Swimmer..."

# Detect if we're in a virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Detected virtual environment: $VIRTUAL_ENV"
    echo "Installing into venv..."
    pip install "$PROJECT_DIR"
    INSTALL_METHOD="venv"
elif command -v pipx &> /dev/null; then
    echo "Installing with pipx..."
    pipx install "$PROJECT_DIR" || pipx install --force "$PROJECT_DIR"
    INSTALL_METHOD="pipx"
elif command -v pip &> /dev/null; then
    echo "Installing with pip (--user)..."
    pip install --user "$PROJECT_DIR"
    INSTALL_METHOD="pip"
else
    echo "Error: Neither pipx nor pip found. Please install Python first."
    exit 1
fi

# Verify installation
if ! command -v spotify-swimmer &> /dev/null; then
    echo ""
    echo "Warning: spotify-swimmer not found in PATH"
    if [ "$INSTALL_METHOD" = "pip" ]; then
        echo "You may need to add ~/.local/bin to your PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

# Create data directories
echo "Creating data directories..."
mkdir -p "$DATA_DIR/spotify/music"
mkdir -p "$DATA_DIR/youtube/music"
mkdir -p "$DATA_DIR/cookies"

# Create sample config if not exists
if [ ! -f "$DATA_DIR/config.yaml" ]; then
    cat > "$DATA_DIR/config.yaml" << 'EOF'
spotify:
  enabled: true
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"
  playlists:
    - name: "Discover Weekly"
      url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

youtube:
  enabled: false
  playlists:
    - name: "Coding Music"
      url: "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"

audio:
  bitrate: 192
  format: "mp3"

paths:
  music_dir: "~/.spotify-swimmer"
  headphones_mount: "/media/YOUR_USERNAME/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  trim_silence: true
EOF
    echo "Created sample config at $DATA_DIR/config.yaml"
fi

# Save install method for uninstall
echo "$INSTALL_METHOD" > "$DATA_DIR/.install-method"

echo ""
echo "Installation complete! (method: $INSTALL_METHOD)"
echo ""
echo "Next steps:"
echo "1. Edit config: $DATA_DIR/config.yaml"
echo "2. Install Playwright: playwright install chromium"
echo "3. (Optional) Install systemd timer: $SCRIPT_DIR/install-systemd.sh"
echo ""
echo "Usage:"
echo "  spotify-swimmer sync              # Download new tracks"
echo "  spotify-swimmer sync --youtube    # YouTube only"
echo "  spotify-swimmer transfer          # Transfer to headphones"
