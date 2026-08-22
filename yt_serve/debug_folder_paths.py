#!/usr/bin/env python3
"""
Debug script to check playlist folder paths and existence.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.config import settings
from app.core import yt_playlist_audio_tools as tools
from app.models.database import SessionLocal, Playlist

def debug_playlist_folders():
    """Debug all playlist folder paths."""
    
    print("=" * 60)
    print("PLAYLIST FOLDER DEBUG")
    print("=" * 60)
    
    print(f"Base download path: {settings.BASE_DOWNLOAD_PATH}")
    print(f"Base path exists: {os.path.exists(settings.BASE_DOWNLOAD_PATH)}")
    print()
    
    # Get all playlists from database
    db = SessionLocal()
    try:
        playlists = db.query(Playlist).all()
        print(f"Found {len(playlists)} playlists in database:")
        print()
        
        for playlist in playlists:
            print(f"Playlist ID: {playlist.id}")
            print(f"Title: {playlist.title}")
            print(f"URL: {playlist.url}")
            
            # Calculate folder path
            safe_title = tools._sanitize_title(playlist.title)
            playlist_folder = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_title)
            
            print(f"Sanitized title: '{safe_title}'")
            print(f"Expected folder: {playlist_folder}")
            print(f"Folder exists: {os.path.exists(playlist_folder)}")
            
            # List actual folders in base path
            if os.path.exists(settings.BASE_DOWNLOAD_PATH):
                actual_folders = [
                    f for f in os.listdir(settings.BASE_DOWNLOAD_PATH) 
                    if os.path.isdir(os.path.join(settings.BASE_DOWNLOAD_PATH, f))
                ]
                print(f"Actual folders in base path: {actual_folders}")
                
                # Check for similar folder names
                similar = [f for f in actual_folders if safe_title.lower() in f.lower() or f.lower() in safe_title.lower()]
                if similar:
                    print(f"Similar folder names found: {similar}")
            
            print("-" * 40)
            
    finally:
        db.close()

if __name__ == "__main__":
    debug_playlist_folders()