# Future Plan & Walkthrough: Server 24/7 Deployment with Local PC SSD Mirroring

This document details the architectural walkthrough and setup guide for deploying YouTube Playlist Manager on an always-on 24/7 Linux server using an external hard drive, while automatically mirroring media libraries to a primary PC SATA SSD using Syncthing / FreeFileSync.

---

## 1. Architecture Overview

```
                        +-------------------------------------------------------------+
                        |                      24/7 Linux Server                      |
                        |                                                             |
                        |   [ Docker: YouTube Playlist Manager ]                      |
                        |         │                             │                     |
                        |    Daily 4:00 AM Scan             Downloads                 |
                        |         │                             │                     |
                        |         ▼                             ▼                     |
                        |   [ GitHub Remote ]       [ External Hard Drive ]           |
                        |   (Git Metadata Repo)     (/mnt/external_hdd/youtube)       |
                        +---------------------------------------┬---------------------+
                                                                │
                                    Automated LAN Sync          │  (Syncthing / FreeFileSync)
                                    (When PC is Powered ON)     ▼
                        +-------------------------------------------------------------+
                        |                        Your Main PC                         |
                        |                                                             |
                        |   [ Internal SATA SSD ]                                     |
                        |   (High-Speed Offline Playback & Master Media Backup)       |
                        +-------------------------------------------------------------+
```

---

## 2. Server Deployment Walkthrough

### Step 1: Mount the External HDD Persistently on Linux
Find the UUID of your external HDD:
```bash
sudo blkid
```

Add an entry to `/etc/fstab` (with `nofail` so the server boots cleanly even if unplugged):
```fstab
UUID=YOUR-HDD-UUID-HERE  /mnt/external_hdd  ext4  defaults,nofail,x-systemd.device-timeout=10  0  2
```

Create the directory and mount it:
```bash
sudo mkdir -p /mnt/external_hdd/youtube
sudo chown -R $USER:$USER /mnt/external_hdd/youtube
sudo mount -a
```

### Step 2: Configure `docker-compose.yml`
Deploy the application with the external HDD mapped to `/downloads`:

```yaml
version: '3.8'

services:
  yt-playlist-manager:
    image: yt-playlist-manager:latest
    build:
      context: ./yt_serve
      dockerfile: Dockerfile
    container_name: yt-playlist-manager
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      # Map the external HDD as the primary download target
      - /mnt/external_hdd/youtube:/downloads
      # Persistent app data (database, settings)
      - ./data:/app/data
    environment:
      - BASE_DOWNLOAD_PATH=/downloads
      - DAILY_REFRESH_TIME=04:00
      - DAILY_REFRESH_TIMEZONE=Asia/Kolkata
      - ENABLE_DAILY_AUTO_REFRESH=true
      - ENABLE_GIT_METADATA_SYNC=true
      - GIT_REMOTE_URL=git@github.com:YOUR_USERNAME/yt-playlists-metadata.git
```

---

## 3. Automated PC SSD Mirroring Setup

### Option A: Syncthing (Recommended — Fully Automated Real-time LAN Sync)
1. **On Server**:
   - Install Syncthing (`sudo apt install syncthing` or run as a lightweight Docker container).
   - Add folder `/mnt/external_hdd/youtube` as a shared folder.
   - Set Folder Type to **"Send Only"**.
2. **On Main PC (Windows)**:
   - Install [SyncTrayzor](https://github.com/canton7/SyncTrayzor) or Syncthing.
   - Accept the shared folder from the server and set the target path to your PC SATA SSD (e.g. `E:\songs\youtube`).
   - Set Folder Type to **"Receive Only"**.
3. **Behavior**:
   - Zero manual effort.
   - Whenever your PC boots up, Syncthing connects over your local gigabit Wi-Fi/LAN and instantly mirrors newly downloaded tracks from the server to your PC SSD.

### Option B: FreeFileSync (Manual / Scheduled One-Click Sync)
1. Open FreeFileSync on your PC.
2. Left path (Server SMB Share): `\\192.168.1.X\external_hdd\youtube`
3. Right path (PC SATA SSD): `E:\songs\youtube`
4. Synchronization Variant: **"Mirror ->"** (Copies new/updated tracks to SSD).
5. Save as a batch job (`sync_music.ffs_batch`) and place a shortcut on your desktop or Windows Task Scheduler.

---

## 4. Upcoming Roadmap & GitHub Issues

### Suggested Project Board Columns & Cards:

#### 📋 Column 1: Core Downloader & Automation
- [x] **[#12: Robust Cancellation Engine: Instant yt-dlp Stream Abort & Partial File Cleanup](https://github.com/Blank1611/yt_playlist_dnlder/issues/12)**: Fix `AttributeError`, eliminate zombie background worker threads, instantly abort in-flight `yt-dlp` stream transfers, terminate active FFmpeg processes, and purge `.part` files.
- [x] **[#13: Smooth Dual-Tier Progress Bar: In-Flight Byte Progress, Download Speeds (MB/s), ETA & Reconnect Recovery](https://github.com/Blank1611/yt_playlist_dnlder/issues/13)**: *(Completed)* Dual-tier progress bar (overall tracks + in-flight byte stream), 200ms throttled `yt-dlp` progress hooks, and tab reconnect state sync.
- [ ] **[#10: First-Time Auto-Discovery & Database Ingestion for Standard Libraries (v2.5)](https://github.com/Blank1611/yt_playlist_dnlder/issues/10)**: Instant zero-configuration onboarding to scan existing standard playlist folders, extract metadata, and populate SQLite database (`Playlist` and `tracks` index). *(Depends on #7)*.
- [ ] **[#7: Smart Track Index: Instant Cross-Playlist Hardlinking & Move Manager (v2.4)](https://github.com/Blank1611/yt_playlist_dnlder/issues/7)**: SQLite track index (`video_id` key) for zero-space hardlinking across multi-playlist tracks, auto-move/batch relocation for moved songs, and audit trail.
- [ ] **[#6: Ad-hoc Individual Video Download Flow (v2.3)](https://github.com/Blank1611/yt_playlist_dnlder/issues/6)**: Quick single-video downloads with format/quality probing dialog, customizable destination directory, and `adhoc_info.json` metadata tracking.
- [ ] **[#3: Automated Background Downloader for Daily Auto-Scan (v2.2)](https://github.com/Blank1611/yt_playlist_dnlder/issues/3)**: Optional feature toggle to download newly detected songs during daily scans.
- [ ] **[#4: Multi-Format Audio Quality Presets](https://github.com/Blank1611/yt_playlist_dnlder/issues/4)**: Support opus, flac, and m4a quality presets in Web UI.
- [ ] **[#5: Smart Video Replacement](https://github.com/Blank1611/yt_playlist_dnlder/issues/5)**: Automatic search and replacement suggestions for deleted/privatized videos from other YouTube uploads or sources.

#### 📊 Column 2: Logging, Observability & Frontend Architecture (High Priority)
- [x] **[#14: Frontend Modularization: Split Monolithic App.tsx & Extract Reusable UI Widgets](https://github.com/Blank1611/yt_playlist_dnlder/issues/14)**: *(Completed)* Split 2,894-line `App.tsx` into modular `pages/` (`PlaylistsPage.tsx`, `LogsPage.tsx`), `context/` (`ThemeContext.tsx`), and extract pixel-perfect reusable widgets (`Button`, `Modal`, `ProgressBar`, `StatusBadge`, `PlaylistActions`) into `src/components/ui/`.
- [ ] **[#2: Multi-Handler Logging & Observability Engine: SSE, WebSockets, Ring Buffers & Loki/Prometheus (v2.1)](https://github.com/Blank1611/yt_playlist_dnlder/issues/2)**: Rotating file logger, in-memory ring buffer, Server-Sent Events (SSE) stream, WebSocket broadcaster, and structured Loki/Prometheus JSON formatting.
- [ ] **Enhanced Metrics Dashboard**: Real-time download throughput (MB/s), error breakdown, and playlist health stats.

#### 🧹 Column 3: Housekeeping & Storage Optimization
- [ ] **[#11: Non-Standard Library Importer & Fuzzy Title Matching Renamer (v2.6)](https://github.com/Blank1611/yt_playlist_dnlder/issues/11)**: Wizard to import unformatted music folders lacking `playlist_info.json` or `[video_id]`, using ID3 tags, fuzzy playlist title matching, and auto-renaming.
- [ ] **[#8: Retroactive Library Deduplication & Hardlink Space Reclaimer (Housekeeping: GUI + CLI)](https://github.com/Blank1611/yt_playlist_dnlder/issues/8)**: On-demand housekeeping tool in Web GUI / CLI (`tools/deduplicate_library.py`) to scan and convert existing duplicate physical files across playlists into zero-space hardlinks.
- [ ] **[#9: Content-Based Duplicate Finder: SHA-256 Checksum & Acoustic Audio Fingerprinting (Housekeeping: GUI + CLI)](https://github.com/Blank1611/yt_playlist_dnlder/issues/9)**: On-demand library curation tool in Web GUI / CLI (`tools/find_content_duplicates.py`) with 3-stage fast SHA-256 hash and Chromaprint/AcoustID waveform fingerprinting to find duplicates with different filenames, bitrates, or tags.
- [ ] **Built-in Storage Quota Watchdog**: Alert in Web UI when target storage drops below threshold (e.g. <10 GB free).
- [ ] **Direct Cloud Backup Export**: WebDAV / Rclone hook to backup metadata directly to Google Drive / OneDrive.
