# Quick Reference: Interrupted Jobs UI Migration

## What Changed?

The Step 1 interrupted jobs handling in `run.py` startup event has been completely refactored from command-line interactive prompts to a frontend UI dialog.

## Architecture

### Before (❌ Command-Line Interactive)
```
Server Startup
    ↓
main.py startup_event()
    ↓
[BLOCKS] Waits for user input via input()
    ↓
Prompts for action (Resume/Cancel/Individual)
    ↓
Executes based on user choice
```

### After (✅ Non-Blocking, UI-Based)
```
Server Startup
    ↓
main.py startup_event()
    ↓
[SILENT] Detects interrupted jobs, logs info
    ↓
Server Ready (no blocking)
    ↓
Frontend Loads
    ↓
API: GET /api/downloads/interrupted-jobs
    ↓
Show Dialog if jobs found
    ↓
User selects action in Dialog
    ↓
API: POST /api/downloads/handle-interrupted-jobs
    ↓
Backend executes, updates database
```

## Files Modified

### Backend
1. `yt_serve/backend/app/main.py`
   - Removed all `input()` prompts
   - Simplified startup to detect-only (no action)

2. `yt_serve/backend/app/api/downloads.py`
   - Added `GET /api/downloads/interrupted-jobs`
   - Added `POST /api/downloads/handle-interrupted-jobs`
   - Added 3 new Pydantic models: `InterruptedJobInfo`, `InterruptedJobsResponse`, `JobRecoveryRequest`, `JobRecoveryResponse`

### Frontend
1. `yt_serve/frontend/src/services/api.ts`
   - Added `jobsApi.getInterrupted()`
   - Added `jobsApi.handleInterrupted(action, jobDecisions)`

2. `yt_serve/frontend/src/components/InterruptedJobsDialog.tsx` (NEW)
   - Complete dialog component with 3 modes
   - Handles all user interactions for interrupted jobs

3. `yt_serve/frontend/src/App.tsx`
   - Imported `InterruptedJobsDialog`
   - Added state: `interruptedJobs`, `showInterruptedDialog`, `interruptedJobsHandled`
   - Added effect hook to check interrupted jobs on init
   - Added mutation: `handleInterruptedJobs`
   - Added dialog rendering with handlers

## API Endpoints

### GET /api/downloads/interrupted-jobs
**Purpose**: Fetch all interrupted jobs on app initialization

**Response**:
```json
{
  "jobs": [
    {
      "id": 1,
      "job_type": "download",
      "playlist_id": 5,
      "playlist_title": "My Playlist",
      "created_at": "2024-01-25T10:30:00"
    }
  ],
  "count": 1
}
```

### POST /api/downloads/handle-interrupted-jobs
**Purpose**: Execute user's decision about interrupted jobs

**Request (Resume All)**:
```json
{
  "action": "resume_all"
}
```

**Request (Cancel All)**:
```json
{
  "action": "cancel_all"
}
```

**Request (Individual)**:
```json
{
  "action": "individual",
  "job_decisions": {
    "1": "resume",
    "2": "cancel",
    "3": "resume"
  }
}
```

**Response**:
```json
{
  "message": "Successfully handled 3 interrupted job(s)",
  "processed": 3,
  "resumed": 2,
  "cancelled": 1
}
```

## Dialog Modes

### Mode 1: Initial Selection
- Shows list of interrupted jobs
- Three clear action buttons
- Click to choose action

### Mode 2: Individual Selection
- One job per card
- Resume/Cancel buttons for each
- Submit when all decided

### Mode 3: Processing
- Loading spinner
- Disables all inputs
- Shows progress text

## Key Features

✨ **Features**:
- Non-blocking startup
- Dark mode support
- Responsive design
- Clear visual hierarchy
- Smooth transitions
- Real-time feedback
- Error handling

## Testing

To test the migration:

1. **Create interrupted jobs**:
   ```bash
   # Start a download/extract job
   # Stop server while job is running
   ```

2. **Restart server**:
   ```bash
   # Server should start without prompts
   python run.py
   ```

3. **Check frontend**:
   - Open `http://localhost:8000`
   - Dialog should appear automatically
   - Select action and submit

4. **Verify**:
   - Check database for updated job statuses
   - Verify playlists refreshed if jobs resumed

## Rollback (if needed)

If you need to revert to the old command-line approach:
1. Restore `main.py` with `input()` prompts
2. Remove the two API endpoints from `downloads.py`
3. Remove dialog component and App.tsx integration

But the new UI approach is much better! 🎉

## Notes

- No migration needed for existing interrupted jobs (they're in database)
- Dialog only shows on first load when interrupted jobs exist
- User must decide before app proceeds with normal operation
- Backend accepts decision via REST API (can be called from anywhere)
- All state is synchronized between backend and frontend
