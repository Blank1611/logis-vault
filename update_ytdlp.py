#!/usr/bin/env python3
"""
Update yt-dlp to the version with full JavaScript support
"""
import subprocess
import sys

def run_command(cmd):
    """Run a command and return success status"""
    try:
        print(f"Running: {cmd}")
        result = subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return False

def main():
    print("Updating yt-dlp with JavaScript support...")
    print("="*50)
    
    # Update yt-dlp with all optional dependencies
    success = run_command('pip install -U "yt-dlp[default]"')
    
    if success:
        print("\n✓ yt-dlp updated successfully!")
        
        # Check if Node.js is available
        print("\nChecking Node.js availability...")
        try:
            result = subprocess.run("node --version", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ Node.js found: {result.stdout.strip()}")
            else:
                print("✗ Node.js not found")
                print("Please install Node.js from: https://nodejs.org/")
                print("This is required for YouTube's JavaScript execution")
        except Exception as e:
            print(f"✗ Could not check Node.js: {e}")
            print("Please install Node.js from: https://nodejs.org/")
        
        # Test the new configuration
        print("\nTesting yt-dlp with JavaScript runtime...")
        test_cmd = 'yt-dlp --extractor-args "youtube:js_runtimes=node" --no-download --print title "https://www.youtube.com/watch?v=dQw4w9WgXcQ"'
        test_success = run_command(test_cmd)
        
        if test_success:
            print("✓ JavaScript runtime test successful!")
        else:
            print("✗ JavaScript runtime test failed")
            print("Make sure Node.js is installed and in your PATH")
    
    else:
        print("✗ Failed to update yt-dlp")
        return False
    
    print("\n" + "="*50)
    print("Update complete!")
    print("Your application should now work with the new YouTube requirements.")

if __name__ == "__main__":
    main()