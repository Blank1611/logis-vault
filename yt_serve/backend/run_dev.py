#!/usr/bin/env python3
"""
Quick start script for the backend
"""
import uvicorn

if __name__ == "__main__":
    print("="*60)
    print("YouTube Playlist Manager - Backend Server")
    print("="*60)
    print("\nStarting server...")
    print("API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    print("="*60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
