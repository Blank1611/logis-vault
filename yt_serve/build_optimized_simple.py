"""
Simple optimized build script that uses existing built frontend files
Use this if you don't have Node.js installed or want to skip the frontend build step
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_existing_build():
    """Check if frontend is already built"""
    print("[1/4] Checking for existing frontend build...")
    
    frontend_dir = Path("frontend")
    dist_dir = frontend_dir / "dist"
    index_html = dist_dir / "index.html"
    
    if not frontend_dir.exists():
        print("ERROR: frontend directory not found")
        return False
    
    if not dist_dir.exists():
        print("ERROR: frontend/dist directory not found")
        print("   You need to build the frontend first:")
        print("   1. Install Node.js from https://nodejs.org/")
        print("   2. Run: cd frontend && npm install && npm run build")
        print("   3. Or use build_optimized.py instead")
        return False
    
    if not index_html.exists():
        print("ERROR: frontend/dist/index.html not found")
        print("   Frontend build appears incomplete")
        return False
    
    # Check for assets
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        js_files = list(assets_dir.glob("*.js"))
        css_files = list(assets_dir.glob("*.css"))
        print(f"  OK Found {len(js_files)} JS files and {len(css_files)} CSS files")
    
    print("  OK Frontend build found and appears complete")
    return True

def setup_backend_static_serving():
    """Modify backend to serve static frontend files"""
    print("[2/4] Setting up static file serving...")
    
    # Create static files directory in backend
    backend_dir = Path("backend")
    static_dir = backend_dir / "static"
    
    # Copy built frontend to backend/static
    frontend_dist = Path("frontend/dist")
    if static_dir.exists():
        shutil.rmtree(static_dir)
    
    shutil.copytree(frontend_dist, static_dir)
    print("  OK Static files copied to backend")
    
    # Ensure main_with_static.py exists
    main_with_static = backend_dir / "app" / "main_with_static.py"
    if not main_with_static.exists():
        print("  WARNING: main_with_static.py not found!")
        print(f"     Expected at: {main_with_static}")
        print("     Please ensure the file exists before running this script.")
        return False
    
    print("  OK main_with_static.py found")
    
    # Update the run.py to use the static-enabled main
    run_py = backend_dir / "run.py"
    run_content = '''#!/usr/bin/env python3
"""
Production start script for the backend with embedded frontend
"""
import uvicorn

if __name__ == "__main__":
    print("="*60)
    print("Playlist Manager - Production Server")
    print("="*60)
    print("\\nStarting server with embedded frontend...")
    print("Web Interface: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*60)
    print()
    
    uvicorn.run(
        "app.main_with_static:app",  # Use the static-enabled version
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload for production
        log_level="info"
    )
'''
    
    # Backup original run.py
    run_backup = backend_dir / "run_dev.py"
    if not run_backup.exists():
        shutil.copy(run_py, run_backup)
        print("  OK Backed up original run.py as run_dev.py")
    
    # Write production run.py
    run_py.write_text(run_content)
    print("  OK Updated run.py for production mode")
    
    return True

def create_single_launcher():
    """Create launcher that only needs Python"""
    print("[3/4] Creating optimized launcher...")
    
    launcher_script = '''
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def check_python():
    """Check if Python is available"""
    try:
        result = subprocess.run(['python', '--version'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def main():
    print("Playlist Manager - Optimized Launcher")
    print("="*50)
    print()
    
    # Get the directory where the exe is located
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    
    os.chdir(app_dir)
    
    # Check Python
    print("[1/3] Checking Python...")
    if not check_python():
        print("ERROR: Python not found!")
        print("Please install Python from: https://www.python.org/downloads/")
        input("Press Enter to exit...")
        return
    print("OK Python found")
    
    # Setup backend (no frontend setup needed!)
    backend_dir = app_dir / "yt_serve" / "backend"
    venv_dir = backend_dir / "venv"
    
    print("[2/3] Setting up backend...")
    if not venv_dir.exists():
        print("  Creating virtual environment...")
        subprocess.run(['python', '-m', 'venv', str(venv_dir)])
        
        print("  Installing dependencies...")
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        requirements = backend_dir / "requirements.txt"
        subprocess.run([str(pip_exe), 'install', '-r', str(requirements)])
        
        # Copy .env.example to .env if not exists
        env_file = backend_dir / ".env"
        env_example = backend_dir / ".env.example"
        if not env_file.exists() and env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            print("  Created .env file - please configure it!")
    print("OK Backend ready")
    
    # Start single server (serves both API and frontend)
    print("[3/3] Starting application...")
    
    python_exe = venv_dir / "Scripts" / "python.exe"
    run_py = backend_dir / "run.py"
    
    print()
    print("="*50)
    print("Starting Playlist Manager...")
    print("="*50)
    print()
    print("Server: http://localhost:8000")
    print()
    print("Opening browser...")
    
    # Start backend (which now serves frontend too)
    backend_process = subprocess.Popen(
        [str(python_exe), str(run_py)],
        cwd=str(backend_dir)
    )
    
    time.sleep(3)
    webbrowser.open('http://localhost:8000')
    
    print()
    print("Application is running!")
    print("Press Ctrl+C to stop the server.")
    print()
    
    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\\nShutting down...")
        backend_process.terminate()

if __name__ == '__main__':
    main()
'''
    
    # Write optimized launcher with UTF-8 encoding
    launcher_file = Path("launcher_optimized.py")
    launcher_file.write_text(launcher_script, encoding='utf-8')
    print("  OK Optimized launcher created")
    
    return True

def build_executable():
    """Build the final executable"""
    print("[4/4] Building executable...")
    
    # Check PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("  Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build with PyInstaller
    cmd = [
        'pyinstaller',
        '--onefile',
        '--name=PlaylistManager_Optimized',
        '--icon=NONE',
        '--console',
        'launcher_optimized.py'
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("  OK Executable built")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Executable build failed: {e}")
        return False

def main():
    print("="*60)
    print("Simple Optimized Build - Uses Existing Frontend Build")
    print("="*60)
    print()
    print("This script:")
    print("  • Uses existing frontend/dist/ files (no Node.js needed)")
    print("  • Creates optimized launcher (Python only)")
    print("  • Single server process")
    print("  • Faster startup")
    print()
    print("Prerequisites:")
    print("  • Frontend must be already built (frontend/dist/ exists)")
    print("  • main_with_static.py must exist in backend/app/")
    print()
    
    # Check prerequisites
    backend_dir = Path("backend")
    main_with_static = backend_dir / "app" / "main_with_static.py"
    
    if not main_with_static.exists():
        print("ERROR: main_with_static.py not found!")
        print(f"   Expected at: {main_with_static}")
        print()
        print("Please ensure you have the main_with_static.py file in your backend/app/ directory.")
        print()
        return
    
    try:
        if not check_existing_build():
            return
        
        if not setup_backend_static_serving():
            return
        
        if not create_single_launcher():
            return
        
        if not build_executable():
            return
        
        print()
        print("="*60)
        print("Simple Optimized Build Complete!")
        print("="*60)
        print()
        print("Executable: dist/PlaylistManager_Optimized.exe")
        print()
        print("Benefits:")
        print("  OK Only requires Python (no Node.js)")
        print("  OK Single server process")
        print("  OK Faster startup")
        print("  OK Production-optimized frontend")
        print("  OK Smaller distribution package")
        print()
        print("To test:")
        print("  python test_static_serving.py")
        print()
        print("To distribute:")
        print("  1. Copy the entire yt_serve folder")
        print("  2. Include PlaylistManager_Optimized.exe")
        print("  3. Users run the .exe - that's it!")
        print()
        
    except Exception as e:
        print(f"\\nBuild failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == '__main__':
    main()