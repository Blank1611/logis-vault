#!/usr/bin/env python3
"""
Quick script to reset all running jobs to cancelled status
"""
import sys
import os
from pathlib import Path

# Add the backend path
backend_path = Path("yt_serve/backend")
if backend_path.exists():
    sys.path.insert(0, str(backend_path))

try:
    from app.models.database import SessionLocal, Job
except ImportError:
    print("Could not import database models. Make sure you're in the project root.")
    sys.exit(1)

def reset_all_running_jobs():
    """Reset all running jobs to cancelled"""
    db = SessionLocal()
    
    try:
        # Update all running jobs
        updated = db.query(Job).filter(Job.status == 'running').update({
            'status': 'cancelled',
            'error_message': 'Reset due to server restart'
        })
        
        db.commit()
        print(f"✓ Reset {updated} running jobs to cancelled status")
        
        if updated > 0:
            print("The frontend should now show the correct status.")
            print("If it still shows progress bars, try:")
            print("1. Hard refresh browser (Ctrl+F5)")
            print("2. Restart the backend server")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_all_running_jobs()