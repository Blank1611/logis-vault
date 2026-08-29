#!/usr/bin/env python3
"""
Setup script to create config.json from template.
Run this after cloning the repository.
"""

import os
import shutil
import json

def setup_config():
    """Create config.json from template if it doesn't exist."""
    
    config_file = "config.json"
    template_file = "config.json.template"
    
    # Check if config already exists
    if os.path.exists(config_file):
        print(f"✓ {config_file} already exists")
        response = input("Do you want to overwrite it? (yes/no): ").strip().lower()
        if response != "yes":
            print("Setup cancelled. Keeping existing config.")
            return
    
    # Check if template exists
    if not os.path.exists(template_file):
        print(f"❌ Error: {template_file} not found")
        print("Please ensure the template file exists in the project directory.")
        return
    
    # Copy template to config
    try:
        shutil.copy(template_file, config_file)
        print(f"✓ Created {config_file} from template")
    except Exception as e:
        print(f"❌ Error copying template: {e}")
        return
    
    # Prompt for configuration
    print("\n" + "="*60)
    print("CONFIGURATION SETUP")
    print("="*60)
    print("\nPlease provide your settings:")
    print("(Press Enter to keep default values)\n")
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Get base download path
        default_path = config.get("base_download_path", "")
        new_path = input(f"Download path [{default_path}]: ").strip()
        if new_path:
            config["base_download_path"] = new_path
        
        # Get cookies file
        default_cookies = config.get("cookies_file", "")
        print("\nCookies file (optional, for age-restricted videos):")
        new_cookies = input(f"Cookies file path [{default_cookies or 'none'}]: ").strip()
        if new_cookies:
            config["cookies_file"] = new_cookies
        elif new_cookies == "":
            config["cookies_file"] = None
        
        # Get audio mode
        print("\nAudio extraction mode:")
        print("  1. copy - Fastest, best quality (recommended)")
        print("  2. mp3_best - MP3 VBR quality 0")
        print("  3. mp3_high - MP3 VBR quality 2")
        print("  4. opus - Opus codec")
        
        mode_choice = input(f"Choice [1-4, default: 1]: ").strip()
        mode_map = {
            "1": "copy",
            "2": "mp3_best",
            "3": "mp3_high",
            "4": "opus"
        }
        if mode_choice in mode_map:
            config["audio_extract_mode"] = mode_map[mode_choice]
        
        # Get worker count
        default_workers = config.get("max_extraction_workers", 4)
        workers_input = input(f"\nParallel extraction workers [{default_workers}]: ").strip()
        if workers_input.isdigit():
            config["max_extraction_workers"] = int(workers_input)
        
        # Save updated config
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*60)
        print("✓ Configuration saved successfully!")
        print("="*60)
        print(f"\nYour settings have been saved to: {config_file}")
        print("\nYou can edit this file manually at any time.")
        print("See CONFIG_SETUP.md for detailed documentation.")
        
    except Exception as e:
        print(f"\n❌ Error updating config: {e}")
        print("Please edit config.json manually.")


if __name__ == "__main__":
    print("YouTube Playlist Manager - Configuration Setup")
    print("="*60)
    print()
    
    setup_config()
    
    print("\nSetup complete! You can now run the application.")
    input("\nPress Enter to exit...")
