"""
Quick script to rebuild the executable with the fixed launcher
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("Rebuilding executable with improved launcher...")
    print("="*50)
    
    # Check if the fixed launcher exists
    launcher_file = Path("launcher_optimized_fixed.py")
    if not launcher_file.exists():
        print("ERROR: launcher_optimized_fixed.py not found!")
        return
    
    print("✓ Fixed launcher found")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller found: {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installed")
    
    # Clean up old build files
    import shutil
    for cleanup_dir in ["build", "dist"]:
        if Path(cleanup_dir).exists():
            shutil.rmtree(cleanup_dir)
            print(f"✓ Cleaned up {cleanup_dir} directory")
    
    # Build with PyInstaller
    print("\nBuilding executable...")
    cmd = [
        'pyinstaller',
        '--onefile',
        '--name=PlaylistManager_Fixed',
        '--icon=NONE',
        '--console',
        '--clean',  # Clean build
        'launcher_optimized_fixed.py'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Executable built successfully!")
        print("New executable: dist/PlaylistManager_Fixed.exe")
        print("\nTo test:")
        print("  dist\\PlaylistManager_Fixed.exe")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)

if __name__ == "__main__":
    main()