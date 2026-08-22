@echo off
echo Starting Playlist Manager...
echo.

cd /d "%~dp0"

REM Try to deactivate any active virtual environment
if defined VIRTUAL_ENV (
    echo Deactivating virtual environment...
    call deactivate 2>nul
)

REM Run the executable
echo Running application...
dist\PlaylistManager_Optimized.exe

pause