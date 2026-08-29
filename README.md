# YouTube Playlist Manager

Download and manage YouTube playlists with automatic audio extraction, metadata syncing, and archive tracking.

---

## 📦 Projects in this Repository

This repository contains two independent, standalone implementations:

### 1. 🌐 Web Version (Modern Full-Stack)
* **Location:** [`yt_serve/`](file:///yt_serve/)
* **Tech Stack:** React (TypeScript + Vite + Tailwind CSS) + FastAPI + SQLAlchemy + WebSockets + Docker
* **Documentation:** [`yt_serve/DOCS/`](file:///yt_serve/DOCS/)
* **Quickstart:**
  ```powershell
  cd yt_serve
  # See yt_serve/README.md for backend and frontend launch instructions
  ```

### 2. 🖥️ Desktop Tkinter Version (Lightweight Classic)
* **Location:** [`tkinter_gui/`](file:///tkinter_gui/)
* **Tech Stack:** Python standard `tkinter` + `yt-dlp`
* **Documentation:** [`tkinter_gui/docs/`](file:///tkinter_gui/docs/)
* **Quickstart:**
  ```powershell
  cd tkinter_gui
  pip install -r requirements.txt
  python yt_playlist_manager_gui_final.py
  ```

---

## ⚖️ Comparison

| Feature | 🌐 Web Version (`yt_serve`) | 🖥️ Desktop Version (`tkinter_gui`) |
| :--- | :--- | :--- |
| **Interface** | Responsive Web Application | Native Tkinter Desktop Window |
| **Architecture** | Client/Server (FastAPI + React) | Standalone Python Process |
| **Database** | SQLite + SQLAlchemy ORM | JSON config & filesystem metadata |
| **Monitoring** | Prometheus / Grafana / Metrics API | Local log rotation & buffer |
| **Dependencies** | FastAPI, Uvicorn, React, Node.js 18+ | `yt-dlp` only |
| **Docker Support** | ✅ Full Compose & Dockerfile | N/A |

---

## 📄 License

MIT License - see [LICENSE](file:///LICENSE) for details.

