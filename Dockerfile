# Music Ferry Docker Image
# Supports: Web UI, YouTube sync
# Note: Spotify sync requires audio passthrough (see docker-compose.yml)

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    # For Playwright/Chromium (needed for Spotify)
    xvfb \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ferry
USER ferry
WORKDIR /home/ferry

# Install the application
COPY --chown=ferry:ferry . /app
RUN pip install --user --no-cache-dir /app

# Install Playwright browsers
RUN /home/ferry/.local/bin/playwright install chromium

# Environment
ENV PATH="/home/ferry/.local/bin:$PATH"
ENV HOME="/home/ferry"

# Data directory (mount as volume)
VOLUME ["/home/ferry/.music-ferry"]

# Web UI port
EXPOSE 4444

# Default: run web UI
CMD ["music-ferry", "serve", "--host", "0.0.0.0", "--port", "4444"]
