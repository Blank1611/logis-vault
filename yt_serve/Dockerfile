# ==============================================================================
# Stage 1: Build Frontend Assets (React + Vite)
# ==============================================================================
FROM node:18-alpine AS frontend-builder
LABEL project="yt_serve"
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Shared Backend Base (Python 3.14 + Static FFmpeg + Git + Dependencies)
# ==============================================================================
FROM python:3.14-slim AS backend-base
WORKDIR /app/backend

# Copy static precompiled FFmpeg and FFprobe binaries (reduces image by ~500 MB)
COPY --from=mwader/static-ffmpeg:6.1 /ffmpeg /ffprobe /usr/local/bin/

# Install git for metadata versioning & clean up apt caches in same layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/*

# Install python dependencies (layer cached unless requirements.txt changes)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

# Informative project and OCI container metadata
LABEL org.opencontainers.image.source="https://github.com/Blank1611/yt_playlist_dnlder" \
      org.opencontainers.image.title="yt_serve" \
      org.opencontainers.image.description="Containerized YouTube Playlist Downloader" \
      project="yt_serve"

# ==============================================================================
# Stage 3: Test Target (Fast Backend Unit, Integration & Recovery Tests)
# ==============================================================================
FROM backend-base AS backend-test
# Copy backend source code & tests (skips Node/frontend compilation entirely!)
COPY backend/ ./

# Test entrypoint: runs automated test suite
ENTRYPOINT ["python", "-m", "unittest", "discover", "tests"]

# ==============================================================================
# Stage 4: Production Runner (Full-Stack Container with Compiled Static Assets)
# ==============================================================================
FROM backend-base AS runner

# Copy backend source code
COPY backend/ ./

# Copy compiled frontend static assets from frontend-builder stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Create non-root appuser (UID 1000 / GID 1000) and state directories
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -d /app -s /bin/sh appuser && \
    mkdir -p /downloads /downloads-temp /app/data && \
    chown -R appuser:appuser /app /downloads /downloads-temp && \
    chmod 777 /downloads /downloads-temp /app/data && \
    chmod -R 775 /app

# Expose unified web application port
EXPOSE 8000

# Run container as unprivileged appuser
USER appuser

# Cloud-native entrypoint and default argument list
ENTRYPOINT ["python", "run.py"]
CMD [ \
    "--config.file=/app/data/config.env", \
    "--storage.db.path=/app/data/yt_manager.db", \
    "--storage.downloads.path=/downloads", \
    "--web.listen-address=0.0.0.0:8000" \
]
