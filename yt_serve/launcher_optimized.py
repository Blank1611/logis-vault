
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
        print("\nShutting down...")
        backend_process.terminate()

if __name__ == '__main__':
    main()
