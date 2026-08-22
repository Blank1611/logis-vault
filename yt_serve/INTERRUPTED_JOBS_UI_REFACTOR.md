# Interrupted Jobs Handling - UI Dialog Implementation

## Overview
The interrupted jobs handling has been moved from the command-line interactive backend startup to a user-friendly UI dialog that appears when the frontend loads.

## Changes Made

### Backend Changes

#### 1. **`yt_serve/backend/app/main.py`** - Startup Event Cleanup
- **Removed**: All interactive `input()` prompts from the startup event
- **Changed**: Startup event now only detects interrupted jobs and logs them without prompting
- **Benefit**: Server startup is non-blocking and doesn't wait for user input

**Key Changes:**
```python
# Before: Interactive prompts (input(), while loops, etc.)
# After: Silent detection only
print("Checking for interrupted jobs...")
interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
# ... logs info but no prompts
```

#### 2. **`yt_serve/backend/app/api/downloads.py`** - New API Endpoints
Added three new endpoints to handle interrupted jobs via the frontend:

##### `GET /api/downloads/interrupted-jobs`
- Returns all jobs with 'running' status
- Response includes: job ID, type, playlist info, and creation time
- Called on app initialization to populate dialog

##### `POST /api/downloads/handle-interrupted-jobs`
- Accepts action: `resume_all`, `cancel_all`, or `individual`
- For `individual` action: accepts a map of job decisions (resume/cancel)
- Executes user's decisions and updates job statuses
- Returns summary: processed count, resumed count, cancelled count

**New Request Schema:**
```json
{
  "action": "resume_all" | "cancel_all" | "individual",
  "job_decisions": { "job_id": "resume" | "cancel" }  // Only for 'individual'
}
```

### Frontend Changes

#### 1. **`yt_serve/frontend/src/services/api.ts`** - API Methods
Added two new methods to `jobsApi`:
- `getInterrupted()` - Fetches interrupted jobs on app load
- `handleInterrupted(action, jobDecisions)` - Sends user decisions to backend

#### 2. **`yt_serve/frontend/src/components/InterruptedJobsDialog.tsx`** - New Component
A comprehensive modal dialog with three interaction modes:

**Mode 1: Initial Choice Screen**
- Displays all interrupted jobs with details
- Three action buttons:
  - ✓ Resume all - Resume all interrupted jobs
  - ? Decide individually - Choose action per job
  - ✕ Cancel all - Cancel all interrupted jobs

**Mode 2: Individual Job Selection**
- Shows each job with Resume/Cancel buttons
- User selects action for each job
- Submit button applies all decisions

**Mode 3: Processing Screen**
- Shows loading indicator while request is in flight
- Prevents user from making multiple requests

**Features:**
- Dark mode support
- Responsive design
- Smooth transitions between modes
- Real-time feedback on processing status

#### 3. **`yt_serve/frontend/src/App.tsx`** - Integration
Added interrupted jobs handling to main App component:

**State Management:**
```typescript
const [interruptedJobs, setInterruptedJobs] = useState<any[]>([])
const [showInterruptedDialog, setShowInterruptedDialog] = useState(false)
const [interruptedJobsHandled, setInterruptedJobsHandled] = useState(false)
```

**Initialization Hook:**
```typescript
useEffect(() => {
  const checkInterruptedJobs = async () => {
    if (interruptedJobsHandled) return
    
    try {
      const res = await jobsApi.getInterrupted()
      if (res.data.count > 0) {
        setInterruptedJobs(res.data.jobs)
        setShowInterruptedDialog(true)
      } else {
        setInterruptedJobsHandled(true)
      }
    } catch (error) {
      console.error('Error checking interrupted jobs:', error)
      setInterruptedJobsHandled(true)
    }
  }

  checkInterruptedJobs()
}, [interruptedJobsHandled])
```

**Dialog Handlers:**
```typescript
const handleInterruptedJobs = useMutation({
  mutationFn: ({ action, jobDecisions }) => 
    jobsApi.handleInterrupted(action, jobDecisions),
  onSuccess: () => {
    setShowInterruptedDialog(false)
    setInterruptedJobsHandled(true)
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
    queryClient.invalidateQueries({ queryKey: ['playlists'] })
  },
})
```

**Dialog Rendering:**
- Dialog appears after initialization if interrupted jobs exist
- Blocked modal (darkens background, prevents interaction elsewhere)
- Auto-refetches jobs and playlists after user decision

## User Flow

```
1. Server starts → detects interrupted jobs silently
2. Frontend loads → checks for interrupted jobs via API
3. If interrupted jobs found:
   a. Dialog appears with job details
   b. User chooses action (resume all / cancel all / individual)
   c. Dialog submits decision to backend
   d. Backend executes and updates job statuses
   e. Frontend updates and closes dialog
4. App proceeds with normal operation
```

## Benefits

✅ **Non-blocking server startup** - No waiting for user input during startup
✅ **Better UX** - Professional dialog instead of CLI prompts
✅ **Responsive** - Frontend handles interaction, not backend
✅ **Clear options** - Three distinct action choices
✅ **Flexible** - Individual job decisions when needed
✅ **Dark mode support** - Consistent with app theme
✅ **Real-time feedback** - User sees processing status
✅ **Error handling** - Graceful fallback if no interrupted jobs

## Error Handling

- If API call fails during initialization, dialog is skipped
- If backend error occurs during job handling, state is properly reset
- Jobs that fail to resume are marked as failed with error message
- User can retry by refreshing the page

## Testing Checklist

- [ ] Stop server with running job
- [ ] Restart server
- [ ] Verify server starts without prompts
- [ ] Frontend loads and shows dialog
- [ ] Test "Resume all" action
- [ ] Test "Cancel all" action
- [ ] Test "Decide individually" with mixed decisions
- [ ] Verify jobs are updated correctly in database
- [ ] Check that playlists stats refresh after dialog closes
- [ ] Test with multiple interrupted jobs
- [ ] Test dark mode styling of dialog
