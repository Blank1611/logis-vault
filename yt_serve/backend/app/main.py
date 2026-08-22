"""
FastAPI main application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio

from app.api import playlists, downloads, config, websocket
from app.core.config import settings

app = FastAPI(
    title="YouTube Playlist Manager API",
    description="Backend API for YouTube playlist management",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Check for interrupted jobs (queued) and refresh playlist stats on server startup"""
    print("\n" + "="*60)
    print("Playlist Manager - Server Startup")
    print("="*60)
    
    from app.models.database import SessionLocal, Playlist, Job
    from app.services.ytdlp_service import DownloadService
    
    db = SessionLocal()
    playlists_list = db.query(Playlist).all()
    playlists_map = {p.id: p for p in playlists_list}
    if not playlists_list:
        print("No playlists found")
        return
    print(f"Found {len(playlists_list)} playlists to refresh")
    try:
        # Step 1: Check for interrupted jobs - mark them as 'pending' (queued)
        # Note: User will handle recovery via UI dialog after app loads
        print("Checking for interrupted jobs...")
        interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
        
        if interrupted_jobs:
            print(f"\n⚠️  Found {len(interrupted_jobs)} interrupted job(s):")
            for job in interrupted_jobs:
                # Resolve playlist title from playlist_id using list comprehension
                playlist = playlists_map.get(job.playlist_id)
                playlist_title = playlist.title if playlist else "Unknown Playlist"
                print(f"  - Job #{job.id}: {job.job_type} for '{playlist_title}'")
                print(f"    Started: {job.created_at}")
            
            print(f"\nThese jobs were running when the server was last stopped.")
            print("User will be prompted via the UI to handle these jobs.")
            print("(No interactive prompt shown - UI dialog will handle this)\n")
        else:
            print("✓ No interrupted jobs found")
        
        # Step 2: Refresh playlist stats
        print(f"\n{'='*60}")
        print("Refreshing playlist stats...")
        print("="*60)

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
        print(f"Error during startup: {e.with_traceback}")
    finally:
        db.close()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "YouTube Playlist Manager API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
