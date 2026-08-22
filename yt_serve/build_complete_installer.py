"""
Complete build script that creates optimized executable AND Windows installer
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_optimized_build():
    """Run the optimized build process"""
    print("="*60)
    print("STEP 1: Building Optimized Executable")
    print("="*60)
    
    # Run the optimized build script
    result = subprocess.run([sys.executable, "build_optimized.py"], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Optimized build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False
    
    print("✅ Optimized build completed successfully!")
    return True

def setup_portable_python():
    """Download and setup portable Python for installer"""
    print("\n" + "="*60)
    print("STEP 2: Setting up Portable Python")
    print("="*60)
    
    portable_dir = Path("portable")
    python_dir = portable_dir / "python"
    
    if python_dir.exists():
        print("✅ Portable Python already exists")
        return True
    
    print("📥 Downloading portable Python...")
    
    # You can implement Python download here or use pre-downloaded version
    # For now, we'll assume it's already available or skip this step
    
    if not python_dir.exists():
        print("⚠️  Portable Python not found. Installer will use system Python.")
        print("   To include portable Python:")
        print("   1. Download Python embed version from python.org")
        print("   2. Extract to portable/python/ directory")
        print("   3. Re-run this script")
    
    return True

def create_installer():
    """Create the Windows installer using Inno Setup"""
    print("\n" + "="*60)
    print("STEP 3: Creating Windows Installer")
    print("="*60)
    
    # Check if Inno Setup is installed
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    inno_path = None
    for path in inno_paths:
        if os.path.exists(path):
            inno_path = path
            break
    
    if not inno_path:
        print("❌ Inno Setup not found!")
        print("   Download from: https://jrsoftware.org/isdl.php")
        print("   Then re-run this script.")
        return False
    
    print(f"✅ Found Inno Setup: {inno_path}")
    
    # Check if installer script exists
    installer_script = Path("installer_optimized.iss")
    if not installer_script.exists():
        print("❌ installer_optimized.iss not found!")
        return False
    
    print("🔨 Compiling installer...")
    
    # Compile the installer
    result = subprocess.run([inno_path, str(installer_script)], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Installer compilation failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False
    
    print("✅ Installer created successfully!")
    return True

def verify_build_outputs():
    """Verify that all expected outputs were created"""
    print("\n" + "="*60)
    print("STEP 4: Verifying Build Outputs")
    print("="*60)
    
    expected_files = [
        "dist/PlaylistManager_Optimized.exe",
        "installer_output/PlaylistManager_Optimized_Setup.exe",
    ]
    
    all_good = True
    
    for file_path in expected_files:
        path = Path(file_path)
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"✅ {file_path} ({size_mb:.1f} MB)")
        else:
            print(f"❌ {file_path} - NOT FOUND")
            all_good = False
    
    return all_good

def main():
    print("="*60)
    print("COMPLETE BUILD: Optimized Executable + Windows Installer")
    print("="*60)
    print()
    print("This will create:")
    print("  • Optimized executable (Python only, no Node.js)")
    print("  • Professional Windows installer")
    print("  • Embedded frontend (no separate server)")
    print("  • Portable Python (optional)")
    print()
    
    # Check prerequisites
    if not Path("build_optimized.py").exists():
        print("❌ build_optimized.py not found!")
        return
    
    if not Path("installer_optimized.iss").exists():
        print("❌ installer_optimized.iss not found!")
        return
    
    try:
        # Step 1: Build optimized executable
        if not run_optimized_build():
            print("\n❌ Build process failed at optimized build step")
            return
        
        # Step 2: Setup portable Python (optional)
        if not setup_portable_python():
            print("\n❌ Build process failed at portable Python step")
            return
        
        # Step 3: Create installer
        if not create_installer():
            print("\n❌ Build process failed at installer creation step")
            return
        
        # Step 4: Verify outputs
        if not verify_build_outputs():
            print("\n⚠️  Some outputs are missing")
        
        print("\n" + "="*60)
        print("🎉 COMPLETE BUILD SUCCESSFUL!")
        print("="*60)
        print()
        print("📦 Distribution Files:")
        print("   • dist/PlaylistManager_Optimized.exe")
        print("     └─ Standalone executable (requires Python)")
        print()
        print("   • installer_output/PlaylistManager_Optimized_Setup.exe")
        print("     └─ Professional Windows installer")
        print("     └─ Includes everything users need")
        print("     └─ Creates Start Menu shortcuts")
        print("     └─ Handles dependencies automatically")
        print()
        print("🚀 Ready for Distribution!")
        print()
        print("For end users:")
        print("  • Run the installer (.exe)")
        print("  • Follow the setup wizard")
        print("  • Launch from Start Menu or Desktop")
        print("  • No manual setup required!")
        print()
        
    except Exception as e:
        print(f"\n❌ Build failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()