"""
Test script to verify the launcher can find all required files
"""
from pathlib import Path
import os

def test_file_structure():
    print("Testing file structure for launcher...")
    print("="*50)
    
    # Get current directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Check for yt_serve directory
    yt_serve_dir = current_dir / "yt_serve"
    print(f"yt_serve directory: {yt_serve_dir}")
    print(f"  Exists: {yt_serve_dir.exists()}")
    
    if yt_serve_dir.exists():
        # Check backend directory
        backend_dir = yt_serve_dir / "backend"
        print(f"backend directory: {backend_dir}")
        print(f"  Exists: {backend_dir.exists()}")
        
        if backend_dir.exists():
            # Check required files
            required_files = [
                backend_dir / "requirements.txt",
                backend_dir / "run.py",
                backend_dir / ".env.example",
                backend_dir / "app" / "main_with_static.py",
                backend_dir / "static" / "index.html",
            ]
            
            print("\nRequired files:")
            for file_path in required_files:
                exists = file_path.exists()
                status = "✓" if exists else "✗"
                print(f"  {status} {file_path}")
                
                if not exists and file_path.name == "index.html":
                    # Check if static directory exists at all
                    static_dir = backend_dir / "static"
                    if static_dir.exists():
                        static_files = list(static_dir.iterdir())
                        print(f"    Static directory has {len(static_files)} files")
                        for f in static_files[:3]:  # Show first 3
                            print(f"      - {f.name}")
                    else:
                        print("    Static directory doesn't exist")
    
    print("\n" + "="*50)
    print("File structure test complete")

if __name__ == "__main__":
    test_file_structure()