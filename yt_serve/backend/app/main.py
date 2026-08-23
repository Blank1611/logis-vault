"""
FastAPI main application with integrated static frontend serving and SPA routing
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import os
import traceback

from app.api import playlists, downloads, config, websocket
from app.core.config import settings

app = FastAPI(
    title="YouTube Playlist Manager API",
    description="Backend API and web interface for YouTube playlist management",
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
    
    db = SessionLocal()
    try:
        playlists_list = db.query(Playlist).all()
        playlists_map = {p.id: p for p in playlists_list}
        
        # Step 1: Check for interrupted jobs
        print("Checking for interrupted jobs...")
        interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
        
        if interrupted_jobs:
            print(f"\nFound {len(interrupted_jobs)} interrupted job(s):")
            for job in interrupted_jobs:
                playlist = playlists_map.get(job.playlist_id)
                playlist_title = playlist.title if playlist else "Unknown Playlist"
                print(f"  - Job #{job.id}: {job.job_type} for '{playlist_title}' (started {job.created_at})")
            print("Interrupted jobs will be presented to the user via the UI recovery dialog.\n")
        else:
            print("No interrupted jobs found")
        
        if not playlists_list:
            print("No playlists found")
            return

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
                    playlist.excluded_ids or [],
                    source="startup"
                )
                
                playlist.local_count = local_count
                playlist.playlist_count = available_count
                playlist.unavailable_count = unavailable_count
                db.commit()
                
                status = "Caught up" if local_count >= available_count else f"{available_count - local_count} new"
                print(f"{status} ({local_count}/{available_count})")
                
            except Exception as e:
                print(f"Error: {str(e)}")
        
        print("="*60)
        print("Startup complete!")
        print("="*60 + "\n")
        
        # Start background 24/7 daily metadata scheduler
        from app.services.scheduler import start_daily_scheduler
        start_daily_scheduler()
        
    except Exception as e:
        print(f"Error during startup: {e}")
        traceback.print_exc()
    finally:
        db.close()

@app.on_event("shutdown")
async def shutdown_event():
    """Graceful container/server shutdown"""
    print("\n[Shutdown] Performing graceful shutdown...")
    from app.services.scheduler import stop_daily_scheduler
    stop_daily_scheduler()
    from app.services.job_manager import job_manager
    await job_manager.shutdown()
    print("[Shutdown] Complete.\n")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import router as api_v1_router
from app.api import metrics

# Include API routers FIRST
app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
app.include_router(metrics.router, tags=["metrics"])

@app.get("/api/health")
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/api/test")
async def test_endpoint():
    """Test endpoint"""
    return {"message": "API is working", "endpoint": "/api/test"}

# Static file serving & SPA routing
# Look for static directory in backend/static or frontend/dist
possible_static_dirs = [
    Path(__file__).parent.parent / "static",
    Path(__file__).parent.parent.parent / "frontend" / "dist",
    Path("/app/backend/static"),
    Path("/app/frontend/dist")
]

static_dir = None
for s_dir in possible_static_dirs:
    if s_dir.exists() and (s_dir / "index.html").exists():
        static_dir = s_dir
        break

if static_dir:
    print(f"Serving static frontend from: {static_dir}")
    
    if (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
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
    
    @app.get("/")
    async def serve_index():
        return FileResponse(static_dir / "index.html")

    # SPA catch-all fallback route
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Don't intercept API/WS/docs/metrics paths
        if full_path.startswith(("api/", "ws/", "docs", "redoc", "openapi.json", "metrics")):
            raise HTTPException(status_code=404, detail="Not Found")
        
        # Check if requested file exists in static directory directly
        potential_file = static_dir / full_path
        if potential_file.is_file():
            return FileResponse(potential_file)
        
        # Otherwise fallback to index.html for SPA client-side routing
        return FileResponse(static_dir / "index.html")

else:
    print("Static frontend directory not found. Serving API mode only.")
    
    @app.get("/")
    async def root():
        """Root endpoint when running in API-only mode"""
        return {
            "message": "YouTube Playlist Manager API",
            "version": "2.0.0",
            "docs": "/docs",
            "redoc": "/redoc"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )

