# Job Logging Architecture

## Overview

Job logs are stored on the **file system** rather than in the database to handle large log files efficiently and match the existing workflow.

## Storage Location

```
{BASE_DOWNLOAD_PATH}/logs/job_{job_id}.log
```

Example:
```
D:/Music/YouTube Playlists/logs/job_1.log
D:/Music/YouTube Playlists/logs/job_2.log
```

## Log Format

Each log line includes a timestamp and message:

```
[2025-12-05 10:30:45] Starting download for playlist: My Playlist
[2025-12-05 10:30:46] Fetching playlist info...
[2025-12-05 10:30:50] Found 150 videos
[2025-12-05 10:30:51] Starting batch download (200 videos/day limit)
```

## API Access

### Get Job Logs

```bash
GET /api/downloads/jobs/{job_id}/logs?lines=100
```

**Parameters:**
- `lines` (optional): Number of lines to return from end of file. Default: 100. Use `null` for all lines.

**Response:**
```json
[
  {
    "message": "[2025-12-05 10:30:45] Starting download..."
  },
  {
    "message": "[2025-12-05 10:30:46] Fetching playlist info..."
  }
]
```

## Real-Time Streaming

Logs are also streamed in real-time via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/logs/1');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'log') {
    console.log(data.message);
  }
};
```

## Benefits

### 1. Scalability
- No database bloat from large logs
- Can handle thousands of log lines per job
- Fast file I/O operations

### 2. Compatibility
- Matches existing log structure in `logs/` directory
- Easy to view with text editors
- Can use standard log analysis tools

### 3. Performance
- No database queries for log retrieval
- Efficient tail reading for recent logs
- No transaction overhead

### 4. Maintenance
- Easy to archive old logs
- Simple log rotation
- Can delete logs independently of database

## Implementation

### Writing Logs

```python
# In job_manager.py
def _write_log(self, job_id: int, message: str):
    """Write log message to file"""
    log_file = self._get_log_file_path(job_id)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
```

### Reading Logs

```python
# In job_manager.py
def get_job_logs(self, job_id: int, lines: Optional[int] = None) -> list:
    """Get job logs from file"""
    log_file = self._get_log_file_path(job_id)
    
    if not os.path.exists(log_file):
        return []
    
    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    if lines is not None:
        return all_lines[-lines:]
    
    return all_lines
```

## Log Lifecycle

1. **Job Created** → Log file created on first write
2. **Job Running** → Logs appended in real-time
3. **Job Completed** → Log file remains for history
4. **Manual Cleanup** → User can delete old log files

## Future Enhancements

### Log Rotation
Could implement automatic log rotation:
- Archive logs older than X days
- Compress old logs
- Delete very old logs

### Log Search
Could add search functionality:
- Search across all job logs
- Filter by date range
- Full-text search

### Log Aggregation
Could aggregate logs for analysis:
- Error frequency
- Performance metrics
- Download statistics

## Comparison with Database Storage

| Aspect | File System | Database |
|--------|-------------|----------|
| Size Limit | Unlimited | Limited by DB size |
| Performance | Fast for large logs | Slow for large logs |
| Query Speed | Slower | Faster |
| Maintenance | Easy | Complex |
| Compatibility | High | Low |
| Real-time | Excellent | Good |

## Conclusion

File system logging provides the best balance of:
- ✅ Performance for large logs
- ✅ Compatibility with existing workflow
- ✅ Easy maintenance and cleanup
- ✅ Scalability for long-running jobs
- ✅ Simple implementation

This matches the proven approach from the existing Tkinter application.
