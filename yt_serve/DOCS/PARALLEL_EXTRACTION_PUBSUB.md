# Parallel Extraction Pub-Sub System

## Overview

The parallel extraction system uses a queue-based pub-sub architecture to extract audio from videos as soon as they're downloaded, enabling true parallel operation.

## Architecture

### Components

1. **Publisher (Download Phase)**
   - Downloads videos one by one
   - After each successful download, publishes the video file path to the extraction queue
   - Sends `None` as a sentinel value when download is complete

2. **Subscriber (Extraction Phase)**
   - Consumes video paths from the queue
   - Uses a ThreadPoolExecutor to extract audio in parallel
   - Tracks progress and updates the database

3. **Queue**
   - `asyncio.Queue` for each job
   - Thread-safe communication between download and extraction phases
   - Stored in `JobManager.extraction_queues[job_id]`

### Flow

```
Download Phase                    Queue                    Extraction Phase
--------------                    -----                    ----------------
Download video 1 ──────────────> [video1.mp4] ──────────> Extract audio (thread 1)
Download video 2 ──────────────> [video2.mp4] ──────────> Extract audio (thread 2)
Download video 3 ──────────────> [video3.mp4] ──────────> Extract audio (thread 3)
...                               ...                      ...
Download complete ─────────────> [None] ─────────────────> Wait for remaining tasks
```

## Implementation Details

### Global Callbacks

In `yt_playlist_audio_tools.py`:
- `GLOBAL_DOWNLOAD_PROGRESS_CALLBACK` - Download progress updates
- `GLOBAL_EXTRACT_PROGRESS_CALLBACK` - Extraction progress updates
- `GLOBAL_VIDEO_DOWNLOADED_CALLBACK` - Called when a video is successfully downloaded

### Download Phase

1. Creates `video_downloaded_callback` that publishes to the queue
2. Passes callback to `download_service.download_playlist()`
3. After download completes, sends `None` sentinel to signal completion

### Extraction Phase

1. Creates extraction queue for the job
2. Starts ThreadPoolExecutor with `MAX_EXTRACTION_WORKERS` threads
3. Continuously polls the queue for new videos
4. Submits extraction tasks to the thread pool
5. Tracks completed tasks and updates progress
6. Waits for all remaining tasks after receiving `None` sentinel
7. Cleans up queue and thread pool

### Thread Pool

- Max workers: `min(MAX_EXTRACTION_WORKERS, 4)`
- Each worker extracts one video at a time
- Tasks are submitted as videos become available
- Parallel extraction improves overall throughput

## Benefits

1. **Immediate Processing**: Videos are extracted as soon as they're downloaded
2. **Parallel Execution**: Multiple videos can be extracted simultaneously
3. **Efficient Resource Usage**: No polling overhead, event-driven architecture
4. **Progress Tracking**: Separate progress bars for download and extraction
5. **Scalability**: Thread pool size can be configured

## Configuration

Set in `.env`:
```
MAX_CONCURRENT_EXTRACTIONS=4  # Number of parallel extraction threads
```

## Progress Updates

- **Download Progress**: Updated after each video download
- **Extraction Progress**: Updated after each audio extraction completes
- Both progress bars update independently in the UI

## Error Handling

- Failed extractions are tracked separately
- Extraction phase continues even if individual videos fail
- All errors are logged and reported to the UI
