#!/usr/bin/env python3
"""
Quick yt-dlp status check
"""
import sys
import subprocess

def run_command(cmd):
    """Run a command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def main():
    print("yt-dlp Status Check")
    print("="*50)
    
    # Check yt-dlp version
    print("1. Checking yt-dlp version...")
    success, stdout, stderr = run_command("yt-dlp --version")
    if success:
        print(f"   ✓ yt-dlp version: {stdout}")
    else:
        print(f"   ✗ yt-dlp not found or error: {stderr}")
        return
    
    # Check if yt-dlp can access YouTube at all
    print("\n2. Testing basic YouTube access...")
    test_cmd = 'yt-dlp --no-download --quiet "https://www.youtube.com/watch?v=dQw4w9WgXcQ"'
    success, stdout, stderr = run_command(test_cmd)
    if success:
        print("   ✓ Basic YouTube access works")
    else:
        print(f"   ✗ YouTube access failed: {stderr}")
    
    # Check available extractors
    print("\n3. Checking YouTube extractor...")
    success, stdout, stderr = run_command("yt-dlp --list-extractors | grep -i youtube")
    if success and "youtube" in stdout.lower():
        print("   ✓ YouTube extractor available")
    else:
        print("   ⚠ YouTube extractor check inconclusive")
    
    # Test with the problematic video
    video_id = input("\n4. Enter problematic video ID (or press Enter to skip): ").strip()
    if video_id:
        print(f"   Testing video: {video_id}")
        test_cmd = f'yt-dlp --no-download --print title "https://www.youtube.com/watch?v={video_id}"'
        success, stdout, stderr = run_command(test_cmd)
        if success:
            print(f"   ✓ Video accessible: {stdout}")
        else:
            print(f"   ✗ Video failed: {stderr}")
            
            # Try with verbose output
            print("   Trying with verbose output...")
            test_cmd = f'yt-dlp --no-download --verbose --print title "https://www.youtube.com/watch?v={video_id}"'
            success, stdout, stderr = run_command(test_cmd)
            if not success:
                print(f"   Verbose error: {stderr}")
    
    print(f"\n{'='*50}")
    print("If basic access works but downloads fail with 403:")
    print("1. Run the debug script: python debug_ytdlp_403.py")
    print("2. Try using browser cookies")
    print("3. Reduce concurrent downloads")
    print("4. Add delays between requests")

if __name__ == "__main__":
    main()