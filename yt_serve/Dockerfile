# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Backend with Python
FROM python:3.11-slim AS runner
WORKDIR /app/backend

# Install ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy compiled frontend static assets to backend/static
COPY --from=frontend-builder /app/frontend/dist ./static

# Create downloads and persistent data directory
RUN mkdir -p /downloads /app/data

# Expose unified port
EXPOSE 8000

# Default environment variables
ENV BASE_DOWNLOAD_PATH=/downloads \
    DATABASE_PATH=/app/data/yt_manager.db \
    PYTHONUNBUFFERED=1

CMD ["python", "run.py"]

