# Multi-stage Dockerfile for optimized Video Creation API
FROM python:3.12-slim as builder

# Set work directory
WORKDIR /app

# Install system dependencies for building (with better cache management)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    git \
    pkg-config \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install with optimizations
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --compile -r requirements.txt

# Production stage
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Install runtime dependencies with specific versions for stability
RUN apt-get update && apt-get install -y \
    ffmpeg=7:5.1.4-0+deb12u1 \
    curl=7.88.1-10+deb12u8 \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code (with .dockerignore optimization)
COPY . .

# Create directories with proper permissions for video processing
RUN mkdir -p /app/tmp /app/logs /app/cache \
    && chmod 755 /app/tmp /app/logs /app/cache

# Create non-root user for security with specific UID/GID
RUN groupadd -r -g 1000 appgroup && \
    useradd -r -u 1000 -g appgroup -d /app -s /bin/bash app && \
    chown -R app:appgroup /app && \
    chmod -R 755 /app

# Switch to non-root user
USER app

# Set environment variables for optimal performance
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MOVIEPY_TEMP_DIR=/app/tmp \
    IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg

# Expose FastAPI port
EXPOSE 8000

# Enhanced health check with proper timeout
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with optimized uvicorn settings for video processing workloads
CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--log-level", "info", \
    "--workers", "1", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--max-requests", "100", \
    "--max-requests-jitter", "10", \
    "--timeout-keep-alive", "5"]
