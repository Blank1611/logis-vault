#!/usr/bin/env python3
"""
Test script to verify static file serving works correctly
"""
import os
import sys
import subprocess
import time
import requests
from pathlib import Path

def test_static_serving():
    """Test that the static file serving setup works"""
    print("="*60)
    print("Testing Static File Serving Setup")
    print("="*60)
    print()
    
    # Check if main_with_static.py exists
    backend_dir = Path("backend")
    main_with_static = backend_dir / "app" / "main_with_static.py"
    
    if not main_with_static.exists():
        print("❌ main_with_static.py not found!")
        print(f"   Expected at: {main_with_static}")
        return False
    
    print("✓ main_with_static.py found")
    
    # Check if static files exist
    static_dir = backend_dir / "static"
    if not static_dir.exists():
        print("❌ Static files not found!")
        print(f"   Expected at: {static_dir}")
        print("   Run 'npm run build' in frontend directory first")
        return False
    
    print("✓ Static files found")
    
    # Check if index.html exists
    index_html = static_dir / "index.html"
    if not index_html.exists():
        print("❌ index.html not found in static files!")
        return False
    
    print("✓ index.html found")
    
    # Start the server
    print("\nStarting test server...")
    
    try:
        # Change to backend directory
        original_cwd = os.getcwd()
        os.chdir(backend_dir)
        
        # Start server process
        process = subprocess.Popen([
            sys.executable, "-c",
            "import uvicorn; uvicorn.run('app.main_with_static:app', host='127.0.0.1', port=8001, log_level='error')"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        time.sleep(3)
        
        # Test endpoints
        base_url = "http://127.0.0.1:8001"
        
        print("Testing endpoints...")
        
        # Test 1: Root should serve index.html
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200 and "<!doctype html>" in response.text.lower():
                print("✓ Root endpoint serves HTML")
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
            return False
        
        # Test 2: API endpoint should work
        try:
            response = requests.get(f"{base_url}/api/health", timeout=5)
            if response.status_code == 200:
                print("✓ API endpoint works")
            else:
                print(f"❌ API endpoint failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API endpoint error: {e}")
            return False
        
        # Test 3: Static assets should be served
        try:
            # Find a CSS or JS file in assets
            assets_dir = static_dir / "assets"
            if assets_dir.exists():
                css_files = list(assets_dir.glob("*.css"))
                if css_files:
                    css_file = css_files[0]
                    asset_url = f"{base_url}/assets/{css_file.name}"
                    response = requests.get(asset_url, timeout=5)
                    if response.status_code == 200:
                        print("✓ Static assets served")
                    else:
                        print(f"❌ Static asset failed: {response.status_code}")
                        return False
                else:
                    print("⚠️  No CSS files found to test")
            else:
                print("⚠️  No assets directory found")
        except Exception as e:
            print(f"❌ Static asset error: {e}")
            return False
        
        print()
        print("="*60)
        print("✅ All tests passed!")
        print("="*60)
        print()
        print("Static file serving is working correctly.")
        print("You can now run the build_optimized.py script.")
        
        return True
        
    except Exception as e:
        print(f"❌ Server start error: {e}")
        return False
    
    finally:
        # Cleanup
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
        
        os.chdir(original_cwd)

if __name__ == "__main__":
    success = test_static_serving()
    sys.exit(0 if success else 1)