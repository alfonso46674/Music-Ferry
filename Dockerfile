# Music Ferry Docker Image
# Default target: Web UI + YouTube sync
# Optional Spotify support can be enabled with INSTALL_PLAYWRIGHT=true

FROM python:3.12-slim

# Install core runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Optional Spotify/Playwright dependencies
ARG INSTALL_PLAYWRIGHT=false
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
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
        && rm -rf /var/lib/apt/lists/*; \
    fi

# Create non-root user
RUN useradd -m -u 1000 ferry
USER ferry
WORKDIR /home/ferry

# Install the application
COPY --chown=ferry:ferry . /app
RUN pip install --user --no-cache-dir /app

# Install Playwright browser only when Spotify support is enabled
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
        /home/ferry/.local/bin/playwright install chromium; \
    fi

# Environment
ENV PATH="/home/ferry/.local/bin:$PATH"
ENV HOME="/home/ferry"

# Data directory (mount as volume)
VOLUME ["/home/ferry/.music-ferry"]

# Web UI port
EXPOSE 4444

# Default: run web UI
CMD ["music-ferry", "serve", "--host", "0.0.0.0", "--port", "4444"]
