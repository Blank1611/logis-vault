"""
System utilities for cross-platform operations
"""
import os
import subprocess
import platform
from typing import Dict, Any


def open_folder_in_explorer(folder_path: str) -> Dict[str, Any]:
    """
    Open a folder in the system's file explorer.
    
    On Windows, attempts to bring the window to the foreground using pywinauto.
    Falls back to background opening if foreground activation fails.
    
    Args:
        folder_path: Path to the folder to open
        
    Returns:
        Dict with 'success', 'message', 'path', and optionally 'foreground' keys
        
    Raises:
        FileNotFoundError: If the folder doesn't exist
        OSError: If the folder cannot be opened
    """
    # Validate folder exists
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    
    if not os.path.isdir(folder_path):
        raise OSError(f"Path is not a directory: {folder_path}")
    
    system = platform.system()
    abs_path = os.path.abspath(folder_path)
    
    try:
        if system == "Windows":
            return _open_folder_windows(abs_path)
        elif system == "Darwin":  # macOS
            return _open_folder_macos(abs_path)
        else:  # Linux and others
            return _open_folder_linux(abs_path)
    except Exception as e:
        raise OSError(f"Could not open folder '{abs_path}': {str(e)}")


def _open_folder_windows(abs_path: str) -> Dict[str, Any]:
    """Open folder on Windows with foreground activation attempt."""
    try:
        import pywinauto
        import time
        
        # Method 1: Open folder and then find the window
        os.startfile(abs_path)
        
        # Give explorer a moment to open the window
        time.sleep(1.5)
        
        #Try to find and activate the Explorer window
        try:
            # Find all Explorer windows using Desktop
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            
            # Find all Explorer windows (CabinetWClass)
            explorer_windows = desktop.windows(class_name="CabinetWClass")
            
            folder_name = os.path.basename(abs_path)
            print(f"[DEBUG] Looking for Explorer window with folder: {folder_name}")
            print(f"[DEBUG] Found {len(explorer_windows)} Explorer windows")
            
            target_window = None
            for i, window in enumerate(explorer_windows):
                try:
                    window_text = window.window_text()
                    print(f"[DEBUG] Window {i+1}: '{window_text}'")
                    
                    # Check if folder name is in window title (case-insensitive)
                    if folder_name.lower() in window_text.lower():
                        target_window = window
                        print(f"[DEBUG] Found matching window: {window_text}")
                        break
                except Exception as e:
                    print(f"[DEBUG] Error checking window {i+1}: {e}")
                    continue
            
            if target_window:
            #     # Bring window to foreground without changing its size
                try:
                    import win32gui
                    import win32con
                    hwnd = target_window.handle
                    
            #         # Check if window is minimized and restore only if needed
                    placement = win32gui.GetWindowPlacement(hwnd)
                    current_state = placement[1]  # showCmd
                    
            #         if current_state == win32con.SW_SHOWMINIMIZED:
            #             # Only restore if minimized, otherwise leave size unchanged
            #             win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            #             print(f"[DEBUG] Restored minimized window")
                    
            #         # Bring to foreground without changing size
                    win32gui.SetForegroundWindow(hwnd)
                    print(f"[DEBUG] Used win32gui to bring window to foreground")
                    
                except ImportError:
                    print(f"[DEBUG] win32gui not available, using pywinauto only")
                    # Fallback to pywinauto - just set focus
                    target_window.set_focus()
                except Exception as e:
                    print(f"[DEBUG] win32gui activation failed: {e}")
                    # Fallback to pywinauto
                    target_window.set_focus()
                
                print(f"[DEBUG] Successfully brought Explorer window to foreground: {target_window.window_text()}")
                return {
                    "success": True,
                    "message": "Folder opened successfully (foreground)",
                    "path": abs_path,
                    "foreground": True
                }
            else:
                print(f"[DEBUG] Could not find Explorer window for folder: {folder_name}")
                print(f"[DEBUG] Available window titles:")
                for i, window in enumerate(explorer_windows):
                    try:
                        print(f"[DEBUG]   {i+1}: {window.window_text()}")
                    except:
                        print(f"[DEBUG]   {i+1}: <could not get title>")
                return {
                    "success": True,
                    "message": "Folder opened successfully (background)",
                    "path": abs_path,
                    "foreground": False
                }
                
        except Exception as e:
            print(f"[DEBUG] Could not bring window to foreground using pywinauto: {e}")
            # Window still opened, just not in foreground
            return {
                "success": True,
                "message": "Folder opened successfully (background)",
                "path": abs_path,
                "foreground": False
            }
        
    except ImportError:
        print(f"[DEBUG] pywinauto not available, falling back to os.startfile")
        # Fallback to simple method
        os.startfile(abs_path)
        return {
            "success": True,
            "message": "Folder opened successfully (background)",
            "path": abs_path,
            "foreground": False
        }


def _open_folder_macos(abs_path: str) -> Dict[str, Any]:
    """Open folder on macOS."""
    subprocess.run(["open", abs_path], check=True)
    return {
        "success": True,
        "message": "Folder opened successfully",
        "path": abs_path
    }


def _open_folder_linux(abs_path: str) -> Dict[str, Any]:
    """Open folder on Linux, handling headless/Docker environments gracefully."""
    import shutil
    if not shutil.which("xdg-open") or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return {
            "success": False,
            "message": f"File manager cannot be opened in headless/container environment. Download path: {abs_path}",
            "path": abs_path
        }
    try:
        subprocess.run(["xdg-open", abs_path], check=True)
        return {
            "success": True,
            "message": "Folder opened successfully", 
            "path": abs_path
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Could not launch file manager: {str(e)}",
            "path": abs_path
        }



def get_system_info() -> Dict[str, str]:
    """Get basic system information."""
    return {
        "system": platform.system(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }