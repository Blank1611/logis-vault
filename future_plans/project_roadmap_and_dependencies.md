# Project Roadmap & Interdependency Matrix

This document defines the complete dependency map, technical interrelationships, and phased implementation sequence for all planned features and architectural upgrades in the **YouTube Playlist Manager (`yt_serve`)** ecosystem.

---

## 1. Interdependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   FOUNDATIONAL LAYER (0 Dependencies)                           │
│                                                                                                 │
│   [#12: Cancellation Engine]     [#2: Multi-Handler Logging]     [#7: Smart Track Index Schema] │
│      (Thread/Stream Safety)         (Observability & Logs)          (SQLite `tracks` Table)     │
└────────────────┬─────────────────────────────────────────────────┬──────────────────────────────┘
                 │                                                 │
                 │                                                 ▼
┌────────────────┼─────────────────────────────────┬──────────────────────────────────────────────┐
│                ▼                                 │                                              │
│   [#6: Ad-hoc Downloads]                         ▼                                              ▼
│   (Uses robust cancel)             [#10: Standard Auto-Discovery]    [#3: Auto-Downloader]      │
│                                    (Populates #7 Track Index)        (Uses #7 Deduplication &   │
│                                                  │                    #12 Cancellation)         │
│                                                  ▼                                              │
│                                    [#11: Non-Standard Importer]                                 │
│                                    (Fuzzy Renamer & Matcher)                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Issue Dependency Matrix

| Issue ID & Title | Category | Hard Dependencies | Soft / Recommended Prerequisites | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **[#12: Robust Cancellation Engine](https://github.com/Blank1611/yt_playlist_dnlder/issues/12)** | Core Stability | **None (0)** | None | Independent fix for `AttributeError` and synchronous worker thread lifecycle. Provides cancellation foundation for all future jobs. |
| **[#13: Smooth Dual-Tier Progress Bar](https://github.com/Blank1611/yt_playlist_dnlder/issues/13)** | User Experience | **None (0)** | [#12] | In-flight byte progress, real-time download speeds (MB/s), ETA calculations, and automatic reconnect state recovery. |
| **[#2: Multi-Handler Logging (SSE & WebSockets)](https://github.com/Blank1611/yt_playlist_dnlder/issues/2)** | Observability | **None (0)** | None | Core logging infrastructure (rotating files, in-memory ring buffers, Server-Sent Events (SSE), WebSockets, and Loki/Prometheus JSON format). |
| **[#7: Smart Track Index & Move Manager](https://github.com/Blank1611/yt_playlist_dnlder/issues/7)** | Database / Sourcing | **None (0)** | None | Creates SQLite `tracks` and `moved_tracks_history` tables. Powers real-time $0.1$s local hardlink sourcing. |
| **[#10: Standard Auto-Discovery Onboarding](https://github.com/Blank1611/yt_playlist_dnlder/issues/10)** | Onboarding | **[#7]** | [#8] | Scans existing playlist folders and populates SQLite `Playlist` and `tracks` index in $<3$ seconds. |
| **[#8: Retroactive Library Deduplication](https://github.com/Blank1611/yt_playlist_dnlder/issues/8)** | Housekeeping | **None (0)** | [#7] | Converts existing duplicate physical files across playlists into zero-space hardlinks (CLI + Web GUI). |
| **[#6: Ad-hoc Single-Video Downloads](https://github.com/Blank1611/yt_playlist_dnlder/issues/6)** | Core Feature | **None (0)** | [#12] | Individual video download flow with stream quality probing, custom directories, and `adhoc_info.json` metadata tracking. |
| **[#3: Automated Background Downloader](https://github.com/Blank1611/yt_playlist_dnlder/issues/3)** | Automation | **None (0)** | [#7, #12] | Automatically downloads newly detected songs during daily scans with rate-limiting. Uses #7 to prevent duplicate downloads and #12 for safe cancellation. |
| **[#4: Multi-Format Quality Presets](https://github.com/Blank1611/yt_playlist_dnlder/issues/4)** | Audio Engine | **None (0)** | None | Quality presets (`MP3 320k`, `Opus 160k`, `FLAC Lossless`, `M4A 256k`) per playlist and globally in settings. |
| **[#5: Smart Missing Video Replacement](https://github.com/Blank1611/yt_playlist_dnlder/issues/5)** | Metadata / Recovery | **None (0)** | None | Recovers historical metadata from Git for `[Private video]` / `[Deleted video]` tracks and finds alternative YouTube uploads. |
| **[#9: Content-Based Duplicate Finder](https://github.com/Blank1611/yt_playlist_dnlder/issues/9)** | Housekeeping | **None (0)** | None | 3-stage fast SHA-256 hash and Chromaprint/AcoustID waveform fingerprinting to find duplicates with different filenames or bitrates. |
| **[#11: Non-Standard Library Importer](https://github.com/Blank1611/yt_playlist_dnlder/issues/11)** | Importer | **[#10, #7]** | None | Fuzzy title matching and renamer assistant for unformatted external music folders lacking `playlist_info.json` or `[video_id]`. |

---

## 3. Recommended Phased Implementation Sequence

Building the roadmap in this sequence eliminates architectural rework and guarantees maximum system stability:

### 🚀 Phase 1: Core Engine Stability, Observability & Frontend Modularization
> **Focus**: Ensure rock-solid background thread execution, instant stream cancellation, smooth non-freezing progress reporting, centralized logging, and high-performance modular frontend architecture.

1. **[#14: Frontend Modularization: Split Monolithic App.tsx & Extract Reusable UI Widgets](https://github.com/Blank1611/yt_playlist_dnlder/issues/14)**: ✅ *(Completed)*
   - Extracted modals, views, and pixel-perfect atomic widgets (`Button`, `Modal`, `ProgressBar`, `StatusBadge`, `PlaylistActions`) into `src/components/ui/`, `pages/`, `context/`, and `components/`.
   - Reduced `App.tsx` from 2,894 lines down to ~250 clean lines with 0 TypeScript build errors.
2. **[#12: Robust Cancellation Engine](https://github.com/Blank1611/yt_playlist_dnlder/issues/12)**: ✅ *(Completed)*
   - Fixed `AttributeError` in `job_manager.py` by implementing `cancel_current_job()`.
   - Built thread-safe `CancellationToken` in `cancellation.py` and integrated into worker loops to eliminate zombie background threads.
   - Hooked `yt-dlp` progress events with `DownloadCancelled` for instant ($<50\text{ ms}$) stream abort and automatic `.part` file cleanup and terminate active FFmpeg child processes.
3. **[#13: Smooth Dual-Tier Progress Bar Engine](https://github.com/Blank1611/yt_playlist_dnlder/issues/13)**: ✅ *(Completed)*
   - Dual-tier progress bar: Overall playlist items (`16/50`) + In-flight active track bytes (`68% @ 6.4 MB/s • ETA: 08s`).
   - Hooked `yt-dlp` progress events with a 200ms throttler.
   - Dual-protocol streaming: Global WebSocket event bus (`broadcast_event("job_progress")`) + `/api/downloads/jobs/{id}/stream` SSE stream with automatic reconnection.
   - Auto-reconnect state recovery hook to prevent frozen bars on tab switch or laptop sleep.
4. **[#2: Multi-Handler Logging & Observability Engine](https://github.com/Blank1611/yt_playlist_dnlder/issues/2)**:
   - Implement `logging_engine.py` routing simultaneously to rotating files, in-memory ring buffers, SSE (`GET /api/logs/stream`), and WebSocket broadcasts.
   - Add structured Loki/Prometheus JSON formatting and Prometheus `/metrics` endpoint.

---

### 🗄️ Phase 2: Database Track Index, Instant Onboarding & Space Reclaim
> **Focus**: Build the SQLite track indexing foundation, ingest existing libraries in $<3$ seconds, and reclaim physical hard drive space.

3. **[#7: Smart Track Index & Move Manager](https://github.com/Blank1611/yt_playlist_dnlder/issues/7)**:
   - Create SQLite `tracks` and `moved_tracks_history` database tables (`video_id` primary key).
   - Hook local cross-playlist sourcing into `ytdlp_service.py` for $0.1$s zero-space hardlinking.
   - Build auto-move and batch reorganization manager.
4. **[#10: First-Time Auto-Discovery & Database Ingestion](https://github.com/Blank1611/yt_playlist_dnlder/issues/10)**:
   - Scan standard playlist directories on first run, extract metadata from `playlist_info.json`, and populate SQLite tables.
5. **[#8: Retroactive Library Deduplication (CLI + Web GUI)](https://github.com/Blank1611/yt_playlist_dnlder/issues/8)**:
   - Scan existing library for physical duplicates and convert redundant files into zero-space NTFS / ext4 hardlinks.

---

### 🎯 Phase 3: Core Feature Expansion & User Experience
> **Focus**: Deliver major user-facing download features, format presets, and smart automation.

6. **[#6: Ad-hoc Individual Video Download Flow](https://github.com/Blank1611/yt_playlist_dnlder/issues/6)**:
   - Single-video download tab with format/resolution inspection (`4K`, `1080p`, `Audio Only`, `Both`).
   - Customizable `ADHOC_DOWNLOAD_PATH` and `adhoc_info.json` metadata tracking.
7. **[#4: Multi-Format Audio Quality Presets](https://github.com/Blank1611/yt_playlist_dnlder/issues/4)**:
   - Quality presets (`MP3 320k`, `Opus 160k`, `FLAC Lossless`, `M4A 256k`) per playlist and globally.
8. **[#3: Automated Background Downloader for Daily Auto-Scan](https://github.com/Blank1611/yt_playlist_dnlder/issues/3)**:
   - Optional toggle to automatically download newly added tracks during the 4:00 AM daily scan with rate-limiting.
9. **[#5: Smart Missing/Privatized Video Search & Replacement](https://github.com/Blank1611/yt_playlist_dnlder/issues/5)**:
   - Metadata recovery from Git for deleted/privatized videos with automated YouTube search and 1-click swap UI.

---

### 🧹 Phase 4: Advanced Housekeeping & Legacy Importers
> **Focus**: Powerful maintenance tools for advanced music collection management.

10. **[#9: Content-Based Duplicate Finder: SHA-256 & Acoustic Fingerprinting](https://github.com/Blank1611/yt_playlist_dnlder/issues/9)**:
    - 3-stage cryptographic SHA-256 hash + Chromaprint/AcoustID waveform analysis for finding duplicate songs with different names or tags.
11. **[#11: Non-Standard Library Importer & Fuzzy Title Matching Renamer](https://github.com/Blank1611/yt_playlist_dnlder/issues/11)**:
    - Resilient import wizard for unformatted external folders lacking `playlist_info.json` or `[video_id]`.
