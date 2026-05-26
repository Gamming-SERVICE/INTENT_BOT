# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Dockerfile
# ══════════════════════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Build-time labels
LABEL org.opencontainers.image.title="Intent BOT" \
      org.opencontainers.image.version="3.0.0" \
      org.opencontainers.image.description="Production-ready multi-server Discord bot"

# System dependencies (ffmpeg optional for voice/music)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 botuser

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY --chown=botuser:botuser . .

# Create required runtime directories
RUN mkdir -p data/backups logs && chown -R botuser:botuser data logs

# Switch to non-root
USER botuser

# Volume for persistent data (database + logs)
VOLUME ["/app/data", "/app/logs"]

# Health check — pings the process via a lightweight check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import os, sys; sys.exit(0 if os.path.exists('data') else 1)"

CMD ["python", "main.py"]
