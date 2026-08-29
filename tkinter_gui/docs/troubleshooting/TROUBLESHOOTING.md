# Troubleshooting Guide

## Dark Mode Not Switching

### Symptoms
- Click dark mode toggle button
- UI doesn't change
- Moon icon not visible

### Solutions

#### 1. Hard Refresh Browser
```
Windows: Ctrl + Shift + R
Mac: Cmd + Shift + R
```

#### 2. Clear Browser Cache
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

#### 3. Check Console
1. Open DevTools (F12)
2. Go to Console tab
3. Click dark mode toggle
4. Look for "Dark mode: true" or "Dark mode: false"
5. If you don't see this, the JavaScript isn't loading

#### 4. Verify localStorage
1. Open DevTools (F12)
2. Go to Application tab
3. Click "Local Storage" → "http://localhost:5173"
4. Look for "darkMode" key
5. Delete it and try again

#### 5. Check HTML Element
1. Open DevTools (F12)
2. Go to Elements tab
3. Find `<html>` tag
4. When in dark mode, it should have `class="dark"`
5. If not, the toggle isn't working

### Debug Steps

**Test the toggle:**
```javascript
// Open browser console (F12)
// Type this and press Enter:
document.documentElement.classList.toggle('dark')

// If UI changes, the CSS is working
// If not, Tailwind isn't configured properly
```

**Check if Tailwind is loaded:**
```javascript
// In console:
getComputedStyle(document.body).backgroundColor

// Should return different values in light/dark mode
```

## Cancel Button Not Working

### Expected Behavior
- Click "Cancel" button
- Confirmation dialog appears
- Current video finishes downloading
- Job stops before next video
- Status changes to "cancelled"

### Why It's Not Immediate
The download service can't interrupt a video mid-download. It waits for the current video to complete, then stops.

### Workaround for Immediate Stop
1. Stop backend server (Ctrl+C)
2. Restart backend
3. Job will be marked as failed

### Check If Cancel Worked
1. Watch backend terminal logs
2. Look for "Job cancelled by user" message
3. Check job status in UI (should change to "cancelled")
4. Check log file: `{BASE_DOWNLOAD_PATH}/logs/job_{id}.log`

## Frontend Not Loading

### Check Backend
```bash
curl http://localhost:8000/api/playlists
```

Should return JSON with playlists.

### Check Frontend Dev Server
```bash
cd yt_serve/frontend
npm run dev
```

Should show:
```
VITE v5.0.11  ready in XXX ms
➜  Local:   http://localhost:5173/
```

### Check Browser Console
1. Open http://localhost:5173
2. Press F12
3. Look for errors in Console tab
4. Common errors:
   - "Failed to fetch" → Backend not running
   - "Module not found" → Run `npm install`
   - "Unexpected token" → Syntax error in code

## API Errors

### 404 Not Found
- Backend not running
- Wrong URL
- Check: http://localhost:8000/docs

### 500 Internal Server Error
- Check backend terminal for Python errors
- Check backend logs
- Restart backend

### CORS Errors
- Should not happen (proxy configured)
- If it does, check `vite.config.ts`

## Jobs Not Starting

### Check Backend Logs
Look for errors in terminal where backend is running.

### Check Job Status
```bash
curl http://localhost:8000/api/downloads/jobs
```

### Common Issues
1. **Playlist not found** → Re-add playlist
2. **Job already running** → Wait for it to complete
3. **Download path not accessible** → Check `.env` file

## Performance Issues

### Frontend Slow
- Too many playlists? (>50)
- Reduce polling interval in `App.tsx`:
  ```typescript
  refetchInterval: 5000, // Change from 2000 to 5000
  ```

### Backend Slow
- Check disk space
- Check network speed
- Reduce concurrent extractions in `.env`:
  ```
  MAX_CONCURRENT_EXTRACTIONS=2
  ```

## Database Issues

### Playlists Not Showing
```bash
# Verify database
python verify_migration.py

# Re-run migration
python migrate_playlists.py
```

### Database Locked
1. Stop backend
2. Close any database viewers
3. Restart backend

## Still Having Issues?

### Collect Debug Info
1. Backend terminal output
2. Frontend console errors (F12)
3. Network tab in DevTools
4. Job log files
5. Steps to reproduce

### Check Documentation
- [GETTING_STARTED.md](GETTING_STARTED.md)
- [FRONTEND_COMPLETE.md](FRONTEND_COMPLETE.md)
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
