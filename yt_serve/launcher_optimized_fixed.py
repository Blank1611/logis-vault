import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def find_python():
    """Find Python executable - try multiple locations"""
    python_candidates = [
        'python',           # System PATH
        'python3',          # Linux/Mac style
        'py',              # Python Launcher (Windows)
        sys.executable,     # Current Python (if available)
    ]
    
    # Also try common installation paths
    common_paths = [
        r"C:\Python39\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Users\{}\AppData\Local\Programs\Python\Python39\python.exe".format(os.getenv('USERNAME', '')),
        r"C:\Users\{}\AppData\Local\Programs\Python\Python310\python.exe".format(os.getenv('USERNAME', '')),
        r"C:\Users\{}\AppData\Local\Programs\Python\Python311\python.exe".format(os.getenv('USERNAME', '')),
        r"C:\Users\{}\AppData\Local\Programs\Python\Python312\python.exe".format(os.getenv('USERNAME', '')),
    ]
    
    # Try candidates first
    for candidate in python_candidates:
        try:
            result = subprocess.run([candidate, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"Found Python: {candidate} ({result.stdout.strip()})")
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    # Try common paths
    for path in common_paths:
        if os.path.exists(path):
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"Found Python: {path} ({result.stdout.strip()})")
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
    
    return None

def main():
    print("Playlist Manager - Optimized Launcher")
    print("="*50)
    print()
    
    # Get the directory where the exe is located
    if getattr(sys, 'frozen', False):
        # When running as exe, get the directory containing the exe
        app_dir = Path(sys.executable).parent
        print(f"Running as executable from: {app_dir}")
    else:
        # When running as script, get the script directory
        app_dir = Path(__file__).parent
        print(f"Running as script from: {app_dir}")
    
    # The yt_serve folder should be in the same directory as the exe
    yt_serve_dir = app_dir / "yt_serve"
    if not yt_serve_dir.exists():
        print(f"ERROR: yt_serve directory not found at {yt_serve_dir}")
        print("Make sure the executable is in the same directory as the yt_serve folder")
        input("Press Enter to exit...")
        return
    
    # Change to the yt_serve directory for relative paths to work
    os.chdir(yt_serve_dir)
    print(f"Changed working directory to: {yt_serve_dir}")
    
    # Check Python
    print("[1/3] Checking Python...")
    python_exe = find_python()
    if not python_exe:
        print("ERROR: Python not found!")
        print()
        print("Please install Python from: https://www.python.org/downloads/")
        print("Make sure to check 'Add Python to PATH' during installation.")
        print()
        print("If Python is already installed, try:")
        print("  1. Restart your command prompt")
        print("  2. Run 'python --version' to test")
        print("  3. If in a virtual environment, try 'deactivate' first")
        print()
        input("Press Enter to exit...")
        return
    
    # Setup backend (no frontend setup needed!)
    backend_dir = yt_serve_dir / "backend"
    venv_dir = backend_dir / "venv"
    
    if not backend_dir.exists():
        print(f"ERROR: Backend directory not found at {backend_dir}")
        input("Press Enter to exit...")
        return
    
    print("[2/3] Setting up backend...")
    if not venv_dir.exists():
        print("  Creating virtual environment...")
        try:
            subprocess.run([python_exe, '-m', 'venv', str(venv_dir)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: Failed to create virtual environment: {e}")
            print("  Make sure Python venv module is available")
            input("Press Enter to exit...")
            return
        
        print("  Installing dependencies...")
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        requirements = backend_dir / "requirements.txt"
        
        if not requirements.exists():
            print(f"  ERROR: requirements.txt not found at {requirements}")
            input("Press Enter to exit...")
            return
        
        try:
            subprocess.run([str(pip_exe), 'install', '-r', str(requirements)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: Failed to install dependencies: {e}")
            input("Press Enter to exit...")
            return
        
        # Copy .env.example to .env if not exists
        env_file = backend_dir / ".env"
        env_example = backend_dir / ".env.example"
        if not env_file.exists() and env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            print("  Created .env file - please configure it!")
    else:
        print("  Virtual environment already exists")
    
    print("OK Backend ready")
    
    # Check if main_with_static.py exists
    main_with_static = backend_dir / "app" / "main_with_static.py"
    if not main_with_static.exists():
        print(f"ERROR: main_with_static.py not found at {main_with_static}")
        print("Please ensure the file exists before running this application.")
        input("Press Enter to exit...")
        return
    
    # Check if static files exist
    static_dir = backend_dir / "static"
    if not static_dir.exists():
        print(f"ERROR: Static files not found at {static_dir}")
        print("Please run the build script to create static files.")
        input("Press Enter to exit...")
        return
    
    # Start single server (serves both API and frontend)
    print("[3/3] Starting application...")
    
    python_venv_exe = venv_dir / "Scripts" / "python.exe"
    run_py = backend_dir / "run.py"
    
    if not python_venv_exe.exists():
        print(f"ERROR: Virtual environment Python not found at {python_venv_exe}")
        input("Press Enter to exit...")
        return
    
    if not run_py.exists():
        print(f"ERROR: run.py not found at {run_py}")
        input("Press Enter to exit...")
        return
    
    print()
    print("="*50)
    print("Starting Playlist Manager...")
    print("="*50)
    print()
    print("Server: http://localhost:8000")
    print()
    print("Opening browser...")
    
    # Start backend (which now serves frontend too)
    try:
        backend_process = subprocess.Popen(
            [str(python_venv_exe), str(run_py)],
            cwd=str(backend_dir)
        )
    except Exception as e:
        print(f"ERROR: Failed to start backend: {e}")
        input("Press Enter to exit...")
        return
    
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
        try:
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_process.kill()

if __name__ == '__main__':
    main()