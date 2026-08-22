"""
Diagnostic script to check build environment and prerequisites
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python():
    """Check Python installation"""
    print("🐍 Python Environment:")
    print(f"   Version: {sys.version}")
    print(f"   Executable: {sys.executable}")
    print(f"   Platform: {sys.platform}")
    return True

def check_nodejs():
    """Check Node.js and npm installation"""
    print("\n📦 Node.js Environment:")
    
    # Check Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print(f"   Node.js: {result.stdout.strip()}")
        else:
            print("   Node.js: ❌ Not working")
            return False
    except FileNotFoundError:
        print("   Node.js: ❌ Not found")
        return False
    
    # Check npm
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print(f"   npm: {result.stdout.strip()}")
        else:
            print("   npm: ❌ Not working")
            return False
    except FileNotFoundError:
        print("   npm: ❌ Not found")
        return False
    
    return True

def check_project_structure():
    """Check project file structure"""
    print("\n📁 Project Structure:")
    
    required_files = [
        "frontend/package.json",
        "frontend/src/App.tsx",
        "backend/app/main.py",
        "backend/app/main_with_static.py",
        "backend/requirements.txt",
    ]
    
    optional_files = [
        "frontend/dist/index.html",
        "frontend/node_modules",
        "backend/venv",
    ]
    
    all_good = True
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            all_good = False
    
    print("\n   Optional files:")
    for file_path in optional_files:
        path = Path(file_path)
        if path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ⚠️  {file_path} - Not found (will be created)")
    
    return all_good

def check_frontend_build():
    """Check if frontend is already built"""
    print("\n🏗️  Frontend Build Status:")
    
    dist_dir = Path("frontend/dist")
    if not dist_dir.exists():
        print("   ❌ frontend/dist not found - needs building")
        return False
    
    index_html = dist_dir / "index.html"
    if not index_html.exists():
        print("   ❌ frontend/dist/index.html not found - build incomplete")
        return False
    
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        js_files = list(assets_dir.glob("*.js"))
        css_files = list(assets_dir.glob("*.css"))
        print(f"   ✅ Build found: {len(js_files)} JS, {len(css_files)} CSS files")
    else:
        print("   ⚠️  No assets directory found")
    
    return True

def check_build_tools():
    """Check build tools availability"""
    print("\n🔧 Build Tools:")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"   ✅ PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("   ⚠️  PyInstaller: Not installed (will be installed automatically)")
    
    # Check if Inno Setup is available (for installer)
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    
    inno_found = False
    for path in inno_paths:
        if os.path.exists(path):
            print(f"   ✅ Inno Setup: {path}")
            inno_found = True
            break
    
    if not inno_found:
        print("   ⚠️  Inno Setup: Not found (needed for Windows installer)")
    
    return True

def provide_recommendations():
    """Provide recommendations based on findings"""
    print("\n💡 Recommendations:")
    
    # Check what's missing and provide specific advice
    has_nodejs = False
    has_frontend_build = False
    
    try:
        subprocess.run(['npm', '--version'], capture_output=True, check=True)
        has_nodejs = True
    except:
        pass
    
    has_frontend_build = Path("frontend/dist/index.html").exists()
    
    if not has_nodejs and not has_frontend_build:
        print("   🔴 CRITICAL: No Node.js and no frontend build")
        print("      Option 1: Install Node.js and run build_optimized.py")
        print("      Option 2: Get frontend/dist/ files from another machine")
        print("      Option 3: Use a different build approach")
    
    elif not has_nodejs and has_frontend_build:
        print("   🟡 Node.js missing but frontend already built")
        print("      ✅ You can use: python build_optimized_simple.py")
        print("      This will work without Node.js!")
    
    elif has_nodejs and not has_frontend_build:
        print("   🟡 Node.js available but frontend not built")
        print("      ✅ You can use: python build_optimized.py")
        print("      This will build frontend and create executable")
    
    else:
        print("   🟢 Everything looks good!")
        print("      ✅ You can use: python build_optimized.py")
        print("      ✅ Or use: python build_optimized_simple.py")

def main():
    print("="*60)
    print("BUILD ENVIRONMENT DIAGNOSTIC")
    print("="*60)
    print()
    print("Checking your environment for build prerequisites...")
    print()
    
    # Run all checks
    check_python()
    nodejs_ok = check_nodejs()
    structure_ok = check_project_structure()
    frontend_built = check_frontend_build()
    check_build_tools()
    
    provide_recommendations()
    
    print("\n" + "="*60)
    print("DIAGNOSTIC COMPLETE")
    print("="*60)
    
    if not structure_ok:
        print("❌ Critical files missing - check project structure")
        return 1
    
    if not nodejs_ok and not frontend_built:
        print("❌ Cannot build - need Node.js or existing frontend build")
        return 1
    
    print("✅ Environment ready for building")
    return 0

if __name__ == "__main__":
    sys.exit(main())