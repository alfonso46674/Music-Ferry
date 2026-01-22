#!/bin/bash
# scripts/install-systemd.sh
# Install systemd user units for Spotify Swimmer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="$HOME/.spotify-swimmer"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Installing Spotify Swimmer..."

# Create installation directory
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/music"
mkdir -p "$INSTALL_DIR/cookies"
mkdir -p "$INSTALL_DIR/logs"

# Copy project files
cp -r "$PROJECT_DIR/spotify_swimmer" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/.venv" "$INSTALL_DIR/"
cp "$PROJECT_DIR/bin/sync.sh" "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/bin/sync.sh"

# Create sample config if not exists
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    cat > "$INSTALL_DIR/config.yaml" << 'EOF'
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
    echo "Created sample config at $INSTALL_DIR/config.yaml"
    echo "Please edit it with your Spotify credentials and settings."
fi

# Install systemd units
mkdir -p "$SYSTEMD_DIR"
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/spotify-swimmer.service" > "$SYSTEMD_DIR/spotify-swimmer.service"
cp "$PROJECT_DIR/systemd/spotify-swimmer.timer" "$SYSTEMD_DIR/"

# Reload systemd
systemctl --user daemon-reload

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config: $INSTALL_DIR/config.yaml"
echo "2. Install Playwright browsers: $INSTALL_DIR/.venv/bin/playwright install chromium"
echo "3. Login to Spotify manually once to save cookies"
echo "4. Enable timer: systemctl --user enable --now spotify-swimmer.timer"
echo ""
echo "Commands:"
echo "  Run manually:    systemctl --user start spotify-swimmer.service"
echo "  View logs:       journalctl --user -u spotify-swimmer.service -f"
echo "  Check timer:     systemctl --user list-timers spotify-swimmer.timer"
