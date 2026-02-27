# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Install system dependencies
# ffmpeg  → audio extraction (MP3)
# curl    → health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── App stage ─────────────────────────────────────────────────────────────────
WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create temp directory
RUN mkdir -p /tmp/tiktok_bot

# Non-root user for security
RUN useradd -m botuser && chown -R botuser /app /tmp/tiktok_bot
USER botuser

# Health check (keeps the container alive on platforms that need it)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8443}/health || exit 1

# Default to polling mode (no WEBHOOK_URL)
CMD ["python", "bot.py"]
