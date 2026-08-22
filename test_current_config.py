#!/usr/bin/env python3
"""
Test your current yt-dlp configuration vs a minimal working one
"""
import os
import sys
import json
from pathlib import Path

# Add the backend path to import your current configuration
sys.path.insert(0, 'yt_serve/backend')

try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("ERROR: yt-dlp not installed")
    sys.exit(1)

def test_with_current_config():
    """Test with your current application configuration"""
    try:
        # Import your current settings
        from app.core.yt_playlist_audio_tools import _base_speed_opts
        from app.core.config import settings
        
        print("Current application configuration:")
        base_opts = _base_speed_opts()
        print(json.dumps(base_opts, indent=2))
        
        # Build full config like your app does
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "%(title)s [%(id)s].%(ext)s",
            "writeinfojson": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": False,
        }
        ydl_opts.update(base_opts)
        
        # Add cookies if configured
        if hasattr(settings, 'USE_BROWSER_COOKIES') and settings.USE_BROWSER_COOKIES:
            if hasattr(settings, 'BROWSER_NAME'):
                ydl_opts["cookies_from_browser"] = (settings.BROWSER_NAME,)
                print(f"Using browser cookies: {settings.BROWSER_NAME}")
        elif hasattr(settings, 'COOKIES_FILE') and settings.COOKIES_FILE:
            if os.path.exists(settings.COOKIES_FILE):
                ydl_opts["cookiefile"] = settings.COOKIES_FILE
                print(f"Using cookies file: {settings.COOKIES_FILE}")
        
        return ydl_opts
        
    except Exception as e:
        print(f"Could not load current config: {e}")
        return None

def test_minimal_config():
    """Test with minimal working configuration"""
    return {
        "format": "best",
        "outtmpl": "minimal_%(title)s.%(ext)s",
        "concurrent_fragment_downloads": 1,
        "retries": 3,
        "fragment_retries": 3,
    }

def test_download(video_id, config_name, ydl_opts):
    """Test downloading with given configuration"""
    print(f"\n{'='*50}")
    print(f"Testing: {config_name}")
    print(f"Video ID: {video_id}")
    print(f"{'='*50}")
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            print("Extracting info...")
            info = ydl.extract_info(video_url, download=False)
            print(f"✓ Title: {info.get('title', 'Unknown')}")
            
            print("Attempting download...")
            result = ydl.download([video_url])
            print("✓ Download successful!")
            return True
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        
        # Check if it's a 403 error specifically
        error_str = str(e).lower()
        if "403" in error_str or "forbidden" in error_str:
            print("  → This is a 403 Forbidden error")
            print("  → YouTube is blocking the request")
        elif "fragment" in error_str:
            print("  → This is a fragment download error")
            print("  → Try reducing concurrent_fragment_downloads")
        
        return False

def main():
    print("Testing Current vs Minimal yt-dlp Configuration")
    print("="*60)
    
    # Get video ID
    video_id = input("Enter video ID that's failing (e.g., ZeJrWimKSSY): ").strip()
    if not video_id:
        print("No video ID provided, exiting")
        return
    
    # Create test directory
    test_dir = Path("config_test")
    test_dir.mkdir(exist_ok=True)
    os.chdir(test_dir)
    
    # Test minimal config first
    print("\n1. Testing MINIMAL configuration...")
    minimal_config = test_minimal_config()
    minimal_success = test_download(video_id, "Minimal Config", minimal_config)
    
    # Test current config
    print("\n2. Testing YOUR CURRENT configuration...")
    current_config = test_with_current_config()
    if current_config:
        current_success = test_download(video_id, "Current App Config", current_config)
    else:
        current_success = False
        print("Could not load current configuration")
    
    # Results
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Minimal config: {'✓ SUCCESS' if minimal_success else '✗ FAILED'}")
    print(f"Current config: {'✓ SUCCESS' if current_success else '✗ FAILED'}")
    
    if minimal_success and not current_success:
        print("\n🔍 DIAGNOSIS:")
        print("Minimal config works but your current config fails.")
        print("This suggests your current settings are too aggressive.")
        print("\nRECOMMENDATIONS:")
        print("1. Reduce concurrent_fragment_downloads to 1")
        print("2. Increase retry delays")
        print("3. Add sleep intervals between downloads")
        
    elif not minimal_success and not current_success:
        print("\n🔍 DIAGNOSIS:")
        print("Both configs failed - this suggests:")
        print("1. YouTube is blocking your IP")
        print("2. The video has restrictions")
        print("3. Network/ISP issues")
        print("\nRECOMMENDATIONS:")
        print("1. Wait 30-60 minutes")
        print("2. Try a different video")
        print("3. Use VPN")
        print("4. Check if video is available in your region")
        
    elif minimal_success and current_success:
        print("\n✓ Both configs work - the issue might be intermittent")
        
    print(f"\nTest files in: {test_dir.absolute()}")

if __name__ == "__main__":
    main()