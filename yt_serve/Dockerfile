# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Backend with Python
FROM python:3.14-slim AS runner
WORKDIR /app/backend

# Install ffmpeg and git for metadata versioning
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy compiled frontend static assets to backend/static
COPY --from=frontend-builder /app/frontend/dist ./static

# Create non-root appuser (UID 1000 / GID 1000) and state directories
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -d /app -s /bin/sh appuser && \
    mkdir -p /downloads /downloads-temp /app/data && \
    chown -R appuser:appuser /app /downloads /downloads-temp && \
    chmod 777 /downloads /downloads-temp /app/data && \
    chmod -R 775 /app

# Expose unified port
EXPOSE 8000

# Default environment variables
ENV PYTHONUNBUFFERED=1

# Run container as unprivileged appuser (supports custom UID/GID or group_add override)
USER appuser

# Cloud-native entrypoint and default argument list
ENTRYPOINT ["python", "run.py"]
CMD [ \
    "--config.file=/app/data/config.env", \
    "--storage.db.path=/app/data/yt_manager.db", \
    "--storage.downloads.path=/downloads", \
    "--web.listen-address=0.0.0.0:8000" \
]
