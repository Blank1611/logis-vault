#!/usr/bin/env python3
"""
Production start script for the backend with embedded frontend
"""
import uvicorn

if __name__ == "__main__":
    print("="*60)
    print("Playlist Manager - Production Server")
    print("="*60)
    print("\nStarting server with embedded frontend...")
    print("Web Interface: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*60)
    print()
    
    uvicorn.run(
        "app.main_with_static:app",  # Use the static-enabled version
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload for production
        log_level="info"
    )
