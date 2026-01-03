# Audio Extraction Performance Optimization

## Issue
Audio extraction was slow and lagging behind downloads despite multi-threading, with both operations showing the same thread pool name (`ThreadPoolExecutor-784_0`).

## Root Causes

### 1. Shared Thread Pool
- Both download and extraction were using the default thread pool executor
- This caused resource contention and confusion in logs
- No clear separation between download and extraction threads

### 2. Inefficient Queue Processing
- Extraction queue used `asyncio.wait_for()` with 0.5s timeout
- Every empty queue check added 0.5s delay
- Complex task management with unnecessary waiting

### 3. Blocking Queue Operations
- Used `await asyncio.wait_for(queue.get(), timeout=0.5)` repeatedly
- This added cumulative delays when queue was empty
- Extraction couldn't keep up with download pace

## Optimizations Made

### 1. Separate Thread Pools
**Before**:
```python
# Both used default executor
await loop.run_in_executor(None, download_function)
await loop.run_in_executor(None, extract_function)
```

**After**:
```python
# Dedicated download thread pool
download_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="DownloadThread"
)

# Dedicated extraction thread pool  
extract_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="ExtractionThread"
)
```

### 2. Non-Blocking Queue Processing
**Before**:
```python
# Always waited with timeout
video_path = await asyncio.wait_for(
    queue.get(), timeout=0.5
)
```

**After**:
```python
# Non-blocking check first
try:
    video_path = queue.get_nowait()
except asyncio.QueueEmpty:
    # Only wait if no active tasks
    if active_tasks:
        await asyncio.wait(active_tasks, return_when=FIRST_COMPLETED)
    else:
        await asyncio.sleep(0.1)
```

### 3. Efficient Task Management
**Before**:
- Complex timeout-based loop
- Checked completed tasks every 0.5s
- Mixed queue processing with task completion

**After**:
- Process completed tasks immediately
- Non-blocking queue checks
- Wait for task completion only when needed
- Clear separation of concerns

## Performance Improvements

### Thread Pool Separation
- **Download threads**: `DownloadThread-1` (1 worker, downloads are sequential)
- **Extraction threads**: `ExtractionThread-1`, `ExtractionThread-2`, etc. (4 workers)
- No more resource contention between operations

### Queue Processing Speed
- **Before**: 0.5s delay per empty queue check
- **After**: Immediate processing with minimal delays
- **Result**: Extraction keeps pace with downloads

### Task Completion
- **Before**: Checked every 0.5s regardless of activity
- **After**: Processes completions immediately as they happen
- **Result**: Real-time progress updates

## Expected Results

### Log Output Changes
**Before**:
```
[ThreadPoolExecutor-784_0] Downloading video...
[ThreadPoolExecutor-784_0] Extracting audio...  # Same pool!
```

**After**:
```
[DownloadThread-1] Downloading video...
[ExtractionThread-1] Extracting audio...  # Separate pools!
[ExtractionThread-2] Extracting audio...
```

### Performance Metrics
- **Extraction lag**: Reduced from 2+ videos behind to near real-time
- **Queue processing**: No more 0.5s delays
- **Resource utilization**: Better CPU usage with dedicated pools
- **Throughput**: Extraction should match or exceed download speed

### User Experience
- Progress bars update in real-time
- Audio extraction completes shortly after downloads
- Clear separation in logs between download and extraction phases
- Better resource utilization on multi-core systems

## Monitoring

To verify the improvements:

1. **Check thread names in logs**:
   - Look for `DownloadThread-1` for downloads
   - Look for `ExtractionThread-1`, `ExtractionThread-2`, etc. for extractions

2. **Monitor extraction lag**:
   - Should be 0-1 videos behind instead of 2+
   - Extraction should complete quickly after downloads finish

3. **Watch progress updates**:
   - Should be more responsive and real-time
   - Less delay between download completion and extraction start

## Future Improvements

- Add extraction thread pool size to settings (currently fixed at 4)
- Implement extraction priority queue for larger files first
- Add extraction time metrics to logs
- Consider SSD vs HDD optimization for extraction speed