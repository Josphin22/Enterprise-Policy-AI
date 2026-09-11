# Production Dockerfile for Enterprise Policy AI Backend
# Multi-stage optimized build with non-root security and healthcheck
FROM python:3.11-slim as base

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies needed for PyMuPDF, psycopg2, curl, and PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root dedicated user and group for container runtime security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10000 -g appgroup -s /bin/bash -m appuser

# Copy application source code
COPY . /app

# Ensure writable directories exist with correct permissions for non-root user
RUN mkdir -p /app/documents /app/vectorstore /app/logs && \
    chown -R appuser:appgroup /app && \
    chmod +x /app/entrypoint.sh || true

# Switch to non-root user
USER appuser

# Expose backend port
EXPOSE 8000

# Container healthcheck targeting the enterprise health probe
HEALTHCHECK --interval=20s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production ASGI server execution using entrypoint script
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
