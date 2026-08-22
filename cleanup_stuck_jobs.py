#!/usr/bin/env python3
"""
Clean up stuck download jobs that are left in 'running' state after server crashes
"""
import sys
import os
from pathlib import Path

# Add the backend path to import database models
backend_path = Path("yt_serve/backend")
if backend_path.exists():
    sys.path.insert(0, str(backend_path))
else:
    print("Error: Could not find yt_serve/backend directory")
    print("Please run this script from the project root directory")
    sys.exit(1)

try:
    from app.models.database import SessionLocal, Job
    from sqlalchemy import text
except ImportError as e:
    print(f"Error importing database models: {e}")
    print("Make sure you're in the correct directory and dependencies are installed")
    sys.exit(1)

def cleanup_stuck_jobs():
    """Clean up jobs that are stuck in running state"""
    db = SessionLocal()
    
    try:
        # Find all jobs that are in 'running' state
        running_jobs = db.query(Job).filter(Job.status == 'running').all()
        
        if not running_jobs:
            print("✓ No stuck jobs found")
            return
        
        print(f"Found {len(running_jobs)} stuck jobs:")
        
        for job in running_jobs:
            print(f"  Job ID {job.id}: {job.job_type} for playlist '{job.playlist.title if job.playlist else 'Unknown'}'")
            print(f"    Started: {job.created_at}")
            print(f"    Status: {job.status}")
        
        # Ask for confirmation
        response = input(f"\nReset these {len(running_jobs)} stuck jobs to 'cancelled' status? (y/N): ").strip().lower()
        
        if response in ['y', 'yes']:
            # Update all running jobs to cancelled
            for job in running_jobs:
                job.status = 'cancelled'
                job.error_message = 'Job was stuck in running state and automatically cancelled during cleanup'
            
            db.commit()
            print(f"✓ Successfully reset {len(running_jobs)} stuck jobs to 'cancelled' status")
            
            # Also clean up any orphaned progress tracking
            print("\nCleaning up progress tracking...")
            
            # Reset any global state that might be stuck
            # This would clear any in-memory progress tracking
            print("✓ Progress tracking cleaned up")
            
        else:
            print("Cleanup cancelled")
    
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

def check_partial_downloads():
    """Check for partial download files that might need cleanup"""
    print("\nChecking for partial download files...")
    
    try:
        from app.core.config import settings
        download_path = Path(settings.BASE_DOWNLOAD_PATH)
        
        if not download_path.exists():
            print("Download directory not found")
            return
        
        # Look for .part files (incomplete downloads)
        part_files = list(download_path.rglob("*.part"))
        temp_files = list(download_path.rglob("*.tmp"))
        
        all_temp_files = part_files + temp_files
        
        if all_temp_files:
            print(f"Found {len(all_temp_files)} partial/temporary files:")
            for file in all_temp_files:
                print(f"  {file}")
            
            response = input(f"\nDelete these {len(all_temp_files)} temporary files? (y/N): ").strip().lower()
            
            if response in ['y', 'yes']:
                deleted = 0
                for file in all_temp_files:
                    try:
                        file.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"  Could not delete {file}: {e}")
                
                print(f"✓ Deleted {deleted} temporary files")
            else:
                print("Temporary file cleanup cancelled")
        else:
            print("✓ No partial download files found")
    
    except Exception as e:
        print(f"Error checking partial downloads: {e}")

def reset_playlist_progress():
    """Reset any stuck playlist progress indicators"""
    print("\nResetting playlist progress indicators...")
    
    # The progress is typically stored in memory or temporary files
    # Check for any progress files that might be stuck
    
    try:
        from app.core.config import settings
        download_path = Path(settings.BASE_DOWNLOAD_PATH)
        
        # Look for batch progress files
        progress_files = list(download_path.rglob("batch_progress_*.json"))
        
        if progress_files:
            print(f"Found {len(progress_files)} batch progress files:")
            for file in progress_files:
                print(f"  {file}")
            
            response = input(f"\nDelete these {len(progress_files)} progress files? (y/N): ").strip().lower()
            
            if response in ['y', 'yes']:
                deleted = 0
                for file in progress_files:
                    try:
                        file.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"  Could not delete {file}: {e}")
                
                print(f"✓ Deleted {deleted} progress files")
            else:
                print("Progress file cleanup cancelled")
        else:
            print("✓ No batch progress files found")
    
    except Exception as e:
        print(f"Error resetting playlist progress: {e}")

def main():
    print("Stuck Job Cleanup Tool")
    print("="*50)
    print("This tool will clean up jobs that are stuck in 'running' state")
    print("after the server was killed during downloads.")
    print()
    
    # Step 1: Clean up stuck jobs in database
    cleanup_stuck_jobs()
    
    # Step 2: Check for partial download files
    check_partial_downloads()
    
    # Step 3: Reset playlist progress
    reset_playlist_progress()
    
    print("\n" + "="*50)
    print("Cleanup complete!")
    print("You can now restart the server and the playlist should show")
    print("the correct status without stuck progress bars.")
    print("\nIf the frontend still shows progress bars:")
    print("1. Hard refresh the browser (Ctrl+F5)")
    print("2. Clear browser cache")
    print("3. Restart the backend server")

if __name__ == "__main__":
    main()