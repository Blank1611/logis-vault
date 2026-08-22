#!/usr/bin/env python3
"""
Debug script for yt-dlp 403 errors
This script tests different configurations to isolate the cause of 403 errors
"""
import os
import sys
import json
import time
from pathlib import Path

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import ExtractorError
except ImportError:
    print("ERROR: yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

def test_video_url(video_id, test_name, ydl_opts):
    """Test downloading a single video with given options"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"Video ID: {video_id}")
    print(f"Options: {json.dumps(ydl_opts, indent=2)}")
    print(f"{'='*60}")
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # First try to extract info only
            print("Step 1: Extracting video info...")
            info = ydl.extract_info(video_url, download=False)
            print(f"✓ Info extracted successfully")
            print(f"  Title: {info.get('title', 'Unknown')}")
            print(f"  Duration: {info.get('duration', 'Unknown')} seconds")
            print(f"  Uploader: {info.get('uploader', 'Unknown')}")
            
            # Check available formats
            formats = info.get('formats', [])
            print(f"  Available formats: {len(formats)}")
            
            # Try to download
            print("\nStep 2: Attempting download...")
            result = ydl.download([video_url])
            print(f"✓ Download completed successfully")
            return True
            
    except ExtractorError as e:
        print(f"✗ ExtractorError: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def main():
    print("yt-dlp 403 Error Debug Script")
    print("="*60)
    
    # Get a video ID that's currently failing
    video_id = input("Enter a video ID that's getting 403 errors (e.g., ZeJrWimKSSY): ").strip()
    if not video_id:
        video_id = "ZeJrWimKSSY"  # Default from your error
    
    # Create test directory
    test_dir = Path("debug_downloads")
    test_dir.mkdir(exist_ok=True)
    os.chdir(test_dir)
    
    print(f"Testing with video ID: {video_id}")
    print(f"Download directory: {test_dir.absolute()}")
    
    # Test configurations
    tests = [
        {
            "name": "1. Minimal Configuration",
            "opts": {
                "format": "best",
                "outtmpl": "%(title)s.%(ext)s",
            }
        },
        {
            "name": "2. With User Agent",
            "opts": {
                "format": "best",
                "outtmpl": "%(title)s.%(ext)s",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
        },
        {
            "name": "3. Conservative Settings (Low Concurrency)",
            "opts": {
                "format": "best",
                "outtmpl": "%(title)s.%(ext)s",
                "concurrent_fragment_downloads": 1,
                "retries": 10,
                "fragment_retries": 10,
                "sleep_interval": 2,
            }
        },
        {
            "name": "4. With Browser Cookies (Chrome)",
            "opts": {
                "format": "best",
                "outtmpl": "%(title)s.%(ext)s",
                "cookies_from_browser": ("chrome",),
                "concurrent_fragment_downloads": 1,
            }
        },
        {
            "name": "5. Audio Only (Less Likely to Hit Rate Limits)",
            "opts": {
                "format": "bestaudio",
                "outtmpl": "%(title)s.%(ext)s",
                "concurrent_fragment_downloads": 1,
            }
        },
        {
            "name": "6. Different Format Selection",
            "opts": {
                "format": "worst",  # Try lowest quality
                "outtmpl": "%(title)s.%(ext)s",
            }
        }
    ]
    
    # Check if cookies file exists
    cookies_file = None
    possible_cookies = [
        "../cookies.txt",
        "cookies.txt",
        "../yt_serve/backend/cookies.txt"
    ]
    
    for cookie_path in possible_cookies:
        if os.path.exists(cookie_path):
            cookies_file = cookie_path
            break
    
    if cookies_file:
        print(f"Found cookies file: {cookies_file}")
        tests.append({
            "name": "7. With Cookies File",
            "opts": {
                "format": "best",
                "outtmpl": "%(title)s.%(ext)s",
                "cookiefile": cookies_file,
                "concurrent_fragment_downloads": 1,
            }
        })
    else:
        print("No cookies file found")
    
    # Run tests
    results = []
    for i, test in enumerate(tests):
        try:
            success = test_video_url(video_id, test["name"], test["opts"])
            results.append((test["name"], success))
            
            if success:
                print(f"✓ {test['name']} - SUCCESS")
                break  # Stop on first success
            else:
                print(f"✗ {test['name']} - FAILED")
            
            # Wait between tests to avoid rate limiting
            if i < len(tests) - 1:
                print("Waiting 5 seconds before next test...")
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
            break
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for name, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status} - {name}")
    
    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    successful_tests = [name for name, success in results if success]
    
    if successful_tests:
        print(f"✓ Working configuration found: {successful_tests[0]}")
        print("Apply this configuration to your main application")
    else:
        print("✗ All tests failed. This suggests:")
        print("  1. YouTube is blocking your IP temporarily")
        print("  2. The specific video has restrictions")
        print("  3. Your network/ISP is blocking YouTube API access")
        print("\nTry:")
        print("  - Wait 30-60 minutes and try again")
        print("  - Use a VPN")
        print("  - Try a different video ID")
        print("  - Update yt-dlp: pip install --upgrade yt-dlp")
    
    print(f"\nTest files saved in: {test_dir.absolute()}")

if __name__ == "__main__":
    main()