"""
FastAPI main application with static file serving for production builds
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
import asyncio
import os

from app.api import playlists, downloads, config, websocket
from app.core.config import settings
from app.models.database import get_db, Playlist

app = FastAPI(
    title="Playlist Manager API",
    description="Backend API for playlist management with embedded frontend",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Check for interrupted jobs and refresh playlist stats on server startup"""
    print("\n" + "="*60)
    print("Playlist Manager - Server Startup")
    print("="*60)
    
    from app.models.database import SessionLocal, Playlist, Job
    from app.services.ytdlp_service import DownloadService
    from app.services.job_manager import JobManager
    
    db = SessionLocal()
    try:
        # Step 1: Check for interrupted jobs
        print("Checking for interrupted jobs...")
        interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
        
        if interrupted_jobs:
            print(f"\n⚠️  Found {len(interrupted_jobs)} interrupted job(s):")
            for job in interrupted_jobs:
                playlist_title = job.playlist.title if job.playlist else "Unknown"
                print(f"  - Job #{job.id}: {job.job_type} for '{playlist_title}'")
                print(f"    Started: {job.created_at}")
            
            print(f"\nThese jobs were running when the server was last stopped.")
            print("What would you like to do?")
            print("1. Resume interrupted jobs")
            print("2. Cancel interrupted jobs")
            print("3. Ask for each job individually")
            
            while True:
                try:
                    choice = input("\nEnter your choice (1/2/3): ").strip()
                    if choice in ['1', '2', '3']:
                        break
                    print("Please enter 1, 2, or 3")
                except (EOFError, KeyboardInterrupt):
                    print("\nDefaulting to cancel all interrupted jobs...")
                    choice = '2'
                    break
            
            job_manager = JobManager()
            
            if choice == '1':
                # Resume all jobs
                print(f"\n🔄 Resuming {len(interrupted_jobs)} interrupted jobs...")
                for job in interrupted_jobs:
                    try:
                        # Reset job status and restart
                        job.status = 'pending'
                        job.error_message = None
                        db.commit()
                        
                        # Start the job in background
                        await job_manager.start_job(job.id)
                        print(f"  ✓ Resumed job #{job.id}")
                    except Exception as e:
                        print(f"  ✗ Failed to resume job #{job.id}: {e}")
                        job.status = 'failed'
                        job.error_message = f"Failed to resume: {str(e)}"
                        db.commit()
            
            elif choice == '2':
                # Cancel all jobs
                print(f"\n❌ Cancelling {len(interrupted_jobs)} interrupted jobs...")
                for job in interrupted_jobs:
                    job.status = 'cancelled'
                    job.error_message = 'Cancelled during server startup'
                    print(f"  ✓ Cancelled job #{job.id}")
                db.commit()
            
            elif choice == '3':
                # Ask for each job individually
                print(f"\n🤔 Asking for each job individually...")
                for job in interrupted_jobs:
                    playlist_title = job.playlist.title if job.playlist else "Unknown"
                    print(f"\nJob #{job.id}: {job.job_type} for '{playlist_title}'")
                    print(f"Started: {job.created_at}")
                    
                    while True:
                        try:
                            individual_choice = input("Resume this job? (y/n): ").strip().lower()
                            if individual_choice in ['y', 'yes']:
                                try:
                                    job.status = 'pending'
                                    job.error_message = None
                                    db.commit()
                                    await job_manager.start_job(job.id)
                                    print(f"  ✓ Resumed job #{job.id}")
                                except Exception as e:
                                    print(f"  ✗ Failed to resume job #{job.id}: {e}")
                                    job.status = 'failed'
                                    job.error_message = f"Failed to resume: {str(e)}"
                                    db.commit()
                                break
                            elif individual_choice in ['n', 'no']:
                                job.status = 'cancelled'
                                job.error_message = 'Cancelled by user during startup'
                                db.commit()
                                print(f"  ✓ Cancelled job #{job.id}")
                                break
                            else:
                                print("Please enter 'y' for yes or 'n' for no")
                        except (EOFError, KeyboardInterrupt):
                            print(f"\n  ✓ Cancelled job #{job.id} (interrupted)")
                            job.status = 'cancelled'
                            job.error_message = 'Cancelled by user during startup'
                            db.commit()
                            break
            
            print(f"\n✓ Interrupted job handling complete")
        else:
            print("✓ No interrupted jobs found")
        
        # Step 2: Refresh playlist stats
        print(f"\n{'='*60}")
        print("Refreshing playlist stats...")
        print("="*60)
        
        playlists_list = db.query(Playlist).all()
        if not playlists_list:
            print("No playlists found")
            return
        
        print(f"Found {len(playlists_list)} playlists to refresh")
        
        download_service = DownloadService(settings.BASE_DOWNLOAD_PATH, {
            "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
            "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
            "batch_size": settings.BATCH_SIZE,
            "use_browser_cookies": settings.USE_BROWSER_COOKIES,
            "browser_name": settings.BROWSER_NAME,
            "cookies_file": settings.COOKIES_FILE,
        })
        
        for playlist in playlists_list:
            try:
                print(f"  Refreshing: {playlist.title}...", end=" ")
                local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
                    playlist.title,
                    playlist.url,
                    playlist.excluded_ids or []
                )
                
                playlist.local_count = local_count
                playlist.playlist_count = available_count
                playlist.unavailable_count = unavailable_count
                db.commit()
                
                status = "✓ Caught up" if local_count >= available_count else f"⚠ {available_count - local_count} new"
                print(f"{status} ({local_count}/{available_count})")
                
            except Exception as e:
                print(f"✗ Error: {str(e)}")
        
        print("="*60)
        print("Startup complete!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"Error during startup: {e}")
    finally:
        db.close()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers FIRST - this is critical for proper routing
print("Registering API routers...")
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
print("✓ Playlists router registered at /api/playlists")
app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
print("✓ Downloads router registered at /api/downloads")
app.include_router(config.router, prefix="/api/config", tags=["config"])
print("✓ Config router registered at /api/config")
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
print("✓ WebSocket router registered at /ws")

# Static file serving - mount AFTER API routers
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    print(f"✓ Serving static files from: {static_dir}")
    
    # Mount static assets only
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="static")
    
    # Serve index.html for root
    @app.get("/")
    async def serve_frontend():
        """Serve the React app's index.html for the root route"""
        print("DEBUG: Root route (/) hit")
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        else:
            return {"message": "Frontend not built. Run 'npm run build' in frontend directory."}
    
    # Handle specific static files
    @app.get("/favicon.ico")
    async def favicon():
        favicon_file = static_dir / "favicon.ico"
        if favicon_file.exists():
            return FileResponse(favicon_file)
        raise HTTPException(status_code=404)
    
    @app.get("/vite.svg")
    async def vite_svg():
        vite_file = static_dir / "vite.svg"
        if vite_file.exists():
            return FileResponse(vite_file)
        raise HTTPException(status_code=404)
    
    # TODO: Add SPA fallback later - testing API first
    
    # TODO: SPA fallback disabled for debugging - API routes should work first
    # Will re-enable once API routing is confirmed working

else:
    print("⚠ Static directory not found. Frontend will not be served.")
    print(f"   Expected: {static_dir}")
    print("   Run the build script to create static files.")
    
    @app.get("/")
    async def root():
        """Root endpoint when no static files available"""
        return {
            "message": "Playlist Manager API",
            "version": "2.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "note": "Frontend not available. Run build script to enable web interface."
        }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/api/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"message": "API is working", "endpoint": "/api/test"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_with_static:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )