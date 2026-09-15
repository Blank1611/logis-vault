# Logis Vault: Universal Media Sanctuary

<div align="center">

[![OCI Image](https://img.shields.io/badge/ghcr.io-logis--vault-purple?logo=docker&logoColor=white)](https://github.com/Blank1611/logis-vault/pkgs/container/logis-vault)
[![Release](https://img.shields.io/badge/version-v1.0.0-red?logo=github)](https://github.com/Blank1611/logis-vault/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/frontend-React_18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

*Automated YouTube playlist archive & synchronization engine with Git-backed metadata auditing, high-fidelity audio extraction, zero-overhead hardlink deduplication, and real-time streaming observability.*

</div>

---

## 🌟 Key Capabilities

* 🔄 **Continuous & Scheduled Synchronization**: Automatically polls playlists on a customizable schedule (`DAILY_SCAN_TIME`) or executes on-demand full-library rescans.
* 🎵 **High-Fidelity Audio Extraction**: Multi-format parallel extraction powered by `yt-dlp` and `ffmpeg` (`mp3`, `opus`, `m4a`, `flac`) with automated ID3 tag injection and cover art embedding.
* 📜 **Git-Backed Metadata Versioning**: Every playlist update (`playlist_info.json`) is tracked with commit history, providing permanent auditing for privatized, deleted, or missing videos.
* ⚡ **Zero-Overhead Hardlink Deduplication**: Intelligent cross-playlist file linking ensures songs appearing in multiple playlists consume storage only once.
* 📊 **Dual-Tier Real-Time Progress**: WebSocket streaming delivers millisecond-accurate transfer rates (MB/s), item ETA, and overall batch completion.
* 🛡️ **Resilient Background Processing**: Recovers cleanly from container restarts and network interruptions with persistent job states in SQLite.
* 📈 **Enterprise Observability**: Built-in Prometheus metrics (`/metrics`), Grafana dashboard provisioning, and real-time WebSocket/SSE log streaming.

---

## 🚀 Quick Start (Docker)

### Recommended: Docker Compose

Create a `docker-compose.yml` file:

```yaml
services:
  logis-vault:
    image: ghcr.io/blank1611/logis-vault:latest
    container_name: logis-vault
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - /mnt/storage/playlists:/downloads
      - ./data:/data
      - ./logs:/logs
      - ./config:/config
    environment:
      - PORT=8000
      - DOWNLOAD_DIR=/downloads
      - DATA_DIR=/data
      - LOG_DIR=/logs
      - CONFIG_DIR=/config
      - LOG_LEVEL=INFO
      - RATE_LIMIT_DELAY=3.0
      - DAILY_SCAN_TIME=04:00
      - ENABLE_PROMETHEUS=true
```

Start the container stack:

```bash
docker compose up -d
```

### Standalone Docker Run

```bash
docker run -d \
  --name logis-vault \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /path/to/media:/downloads \
  -v logis-vault-data:/data \
  -v logis-vault-logs:/logs \
  -v logis-vault-config:/config \
  -e PORT=8000 \
  -e LOG_LEVEL=INFO \
  ghcr.io/blank1611/logis-vault:latest
```

### Service Access

| Service | URL | Notes |
| :--- | :--- | :--- |
| **Web Dashboard** | [http://localhost:8000](http://localhost:8000) | Responsive React UI |
| **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI |
| **Prometheus Metrics** | [http://localhost:8000/metrics](http://localhost:8000/metrics) | Scrape target for Prometheus |
| **Health Check** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Container health probe |

---

## ⚙️ Configuration Reference

Configure Logis Vault via environment variables:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Integer | `8000` | Port for the HTTP server and WebSocket gateway. |
| `DOWNLOAD_DIR` | String | `/downloads` | Mount point for downloaded media and playlist folders. |
| `DATA_DIR` | String | `/data` | Path to persistent storage for SQLite database (`app.db`). |
| `LOG_DIR` | String | `/logs` | Path to rotating log files (`application.log`, `scheduler.log`). |
| `CONFIG_DIR` | String | `/config` | Path to dynamic settings and optional `cookies.txt`. |
| `LOG_LEVEL` | String | `INFO` | Minimum log severity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DAILY_SCAN_TIME` | String | `04:00` | 24-hour timestamp (`HH:MM`) when automated daily scans execute. |
| `RATE_LIMIT_DELAY` | Float | `3.0` | Politeness sleep delay (seconds) between video downloads. |
| `ENABLE_PROMETHEUS` | Boolean | `true` | Toggles standard Prometheus exposition endpoint at `/metrics`. |
| `MEDIA_PERMS` | String | `0664` | POSIX file permissions applied to downloaded audio files. |
| `DIR_PERMS` | String | `0775` | POSIX permissions applied to newly created playlist directories. |

---

## 📂 Storage Volumes & Directory Layout

Logis Vault separates mutable application state, persistent database storage, and external media mounts:

```text
Container Path       Host Purpose
├── /downloads       Physical media files (.mp3, .m4a, etc.) & playlist_info.json
├── /data            SQLite database (app.db, track indices, job records)
├── /logs            Rotating log files & historical session buffers
└── /config          Dynamic runtime settings (config.env) & YouTube cookies
```

---

## 🛠️ Container Lifecycle & Distribution CLI

The repository includes a dedicated build and distribution orchestrator located at [`yt_serve/dist_utils/build_image.py`](yt_serve/dist_utils/build_image.py). It manages multi-stage builds, clean Git-commit traceability, immutable dev-to-prod promotion, decoupled latest tagging, and multi-registry publishing.

### Common Operations

| Command | Action |
| :--- | :--- |
| `./yt_serve/dist_utils/build_image.py -l` | Inspect local images with true Git-commit timestamps and registry status. |
| `./yt_serve/dist_utils/build_image.py -e dev` | Compile a development image tagged with current short SHA (`dev-<sha>`). |
| `./yt_serve/dist_utils/build_image.py -e prod -v v1.0.1 -d` | Immutably promote current clean dev image to production release tag. |
| `./yt_serve/dist_utils/build_image.py -v v1.0.1 -p -P -R ghcr` | Idempotently point `latest` to `v1.0.1` and push both release and latest to GHCR. |
| `./yt_serve/dist_utils/build_image.py -r` | Roll back `latest` pointer to the previous stable release version (N-1). |
| `./yt_serve/dist_utils/build_image.py -k 3` | Prune untagged and dangling development images, keeping the newest 3. |

---

## 💻 Local Development (Bare Metal)

If you wish to run the stack directly on your host machine without Docker:

### Prerequisites
* Python 3.11+
* Node.js 18+ and npm
* `ffmpeg` installed and available on system `PATH`

### 1. Backend Setup
```bash
cd yt_serve/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start FastAPI development server with hot-reload
python3 run_dev.py
```

### 2. Frontend Setup
```bash
cd yt_serve/frontend
npm install

# Start Vite dev server
npm run dev
```

The frontend will run on `http://localhost:5173` and automatically proxy API calls to the backend on `http://localhost:8000`.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│               React 18 Dashboard (Vite)                │
│    (Tailwind CSS, Lucide Icons, WebSocket Client)      │
└───────────────────────────▲────────────────────────────┘
                            │ (HTTP REST + WebSockets / SSE)
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Server                      │
│      (Async Lifespan, Pydantic, Prometheus Metrics)    │
├───────────────────────────┬────────────────────────────┤
│   Background Task Pool    │     Rate Limiting Engine   │
│   (Thread-Safe Queues)    │    (Token-Bucket / Delays) │
├───────────────────────────┼────────────────────────────┤
│   yt-dlp Extraction       │     FFmpeg Audio Transcode │
│   (Archive & Probe)       │     (ID3 & Album Art Injection)│
├───────────────────────────┴────────────────────────────┤
│                  Persistence Layer                     │
│  SQLite (app.db)  │  Hardlink Deduplicator  │ Git Snapshots│
└───────────────────┴─────────────────────────┴──────────┘
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
