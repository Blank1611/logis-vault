@echo off
echo ============================================================
echo Simple Optimized Build - No Node.js Required
echo ============================================================
echo.
echo This will use your existing frontend build and create an optimized executable.
echo.

cd /d "%~dp0"

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo.
echo Running simple build script...
python build_optimized_simple.py

echo.
echo Build complete! Check the output above for results.
pause