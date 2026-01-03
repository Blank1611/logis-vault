# Dynamic Settings - No Restart Required

## Overview
Most settings in the yt_serve backend are now loaded dynamically, meaning you can change them in the `.env` file and they'll take effect immediately without restarting the backend.

## Dynamic Settings

### ✅ BATCH_SIZE
- **What it does**: Controls how many videos are downloaded in each batch
- **File**: `yt_serve/backend/.env`
- **Example**: `BATCH_SIZE=100`
- **Takes effect**: Immediately on next download start
- **No restart required** ✅

### ✅ Other Dynamic Settings (Future)
The same pattern can be applied to other settings as needed.

## Static Settings (Require Restart)

### ❌ BASE_DOWNLOAD_PATH
- **Why**: Path validation and directory creation happens at startup
- **Workaround**: Use the settings UI to change and restart

### ❌ Database Settings
- **Why**: Database connection is established at startup
- **Workaround**: Restart backend after changing database settings

### ❌ API Settings
- **Why**: FastAPI server configuration happens at startup
- **Workaround**: Restart backend after changing API settings

## How It Works

### Before (Static Loading)
```python
# At module import time (startup)
BATCH_SIZE = settings.BATCH_SIZE  # Fixed value until restart
```

### After (Dynamic Loading)
```python
def _get_batch_size() -> int:
    # Create fresh Settings instance each time
    fresh_settings = Settings()
    return fresh_settings.BATCH_SIZE  # Always current value
```

## Testing Dynamic Settings

Use the test script to verify dynamic loading:
```bash
python yt_serve/test_dynamic_batch_size.py
```

## Implementation Pattern

To make other settings dynamic:

1. **Remove static assignment**:
   ```python
   # Remove this
   SOME_SETTING = settings.SOME_SETTING
   ```

2. **Create getter function**:
   ```python
   def _get_some_setting():
       from app.core.config import Settings
       fresh_settings = Settings()
       return fresh_settings.SOME_SETTING
   ```

3. **Use getter in code**:
   ```python
   # Instead of SOME_SETTING, use:
   current_value = _get_some_setting()
   ```

## Benefits

- **Better UX**: No need to restart backend for common setting changes
- **Faster development**: Quick iteration on batch sizes and other parameters
- **Production friendly**: Change settings without downtime
- **Debugging**: Easy to test different values without restarts

## Performance Impact

- **Minimal**: Settings are only reloaded when needed (e.g., start of download)
- **Not per-request**: Settings aren't reloaded for every API call
- **Cached where appropriate**: Static settings remain static for performance

## Future Improvements

- Add settings validation before applying changes
- Add settings change notifications via WebSocket
- Add settings history/rollback functionality
- Make more settings dynamic based on user needs