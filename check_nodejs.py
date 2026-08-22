#!/usr/bin/env python3
"""
Check if Node.js is properly installed for yt-dlp JavaScript execution
"""
import subprocess
import sys
import os

def check_nodejs():
    """Check if Node.js is available"""
    try:
        result = subprocess.run("node --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ Node.js found: {version}")
            
            # Check if it's a recent enough version
            version_num = version.lstrip('v').split('.')[0]
            if int(version_num) >= 14:
                print("✓ Node.js version is compatible")
                return True
            else:
                print("⚠ Node.js version might be too old (need v14+)")
                return False
        else:
            print("✗ Node.js not found in PATH")
            return False
    except Exception as e:
        print(f"✗ Error checking Node.js: {e}")
        return False

def test_ytdlp_with_nodejs():
    """Test yt-dlp with Node.js runtime"""
    print("\nTesting yt-dlp with Node.js runtime...")
    
    try:
        # Test with a simple video
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:js_runtimes=node",
            "--no-download",
            "--print", "title",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✓ yt-dlp with Node.js works: {result.stdout.strip()}")
            return True
        else:
            print(f"✗ yt-dlp with Node.js failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ yt-dlp test timed out")
        return False
    except Exception as e:
        print(f"✗ Error testing yt-dlp: {e}")
        return False

def main():
    print("Node.js Installation Check for yt-dlp")
    print("="*40)
    
    # Check Node.js
    nodejs_ok = check_nodejs()
    
    if not nodejs_ok:
        print("\n" + "="*40)
        print("INSTALL NODE.JS")
        print("="*40)
        print("1. Go to: https://nodejs.org/")
        print("2. Download and install the LTS version")
        print("3. Restart your terminal/command prompt")
        print("4. Run this script again to verify")
        return False
    
    # Test yt-dlp with Node.js
    ytdlp_ok = test_ytdlp_with_nodejs()
    
    print("\n" + "="*40)
    print("SUMMARY")
    print("="*40)
    print(f"Node.js: {'✓ OK' if nodejs_ok else '✗ MISSING'}")
    print(f"yt-dlp + Node.js: {'✓ OK' if ytdlp_ok else '✗ FAILED'}")
    
    if nodejs_ok and ytdlp_ok:
        print("\n✓ Everything is ready!")
        print("Your application should now work with YouTube's new requirements.")
    else:
        print("\n✗ Setup incomplete")
        if not nodejs_ok:
            print("- Install Node.js")
        if nodejs_ok and not ytdlp_ok:
            print("- Update yt-dlp: pip install -U 'yt-dlp[default]'")
    
    return nodejs_ok and ytdlp_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)