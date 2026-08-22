#!/usr/bin/env python3
"""
Test script for folder opening functionality with pywinauto
"""
import os
import subprocess
import platform
import time

def test_folder_opening():
    """Test the folder opening functionality"""
    # Create a test folder
    test_folder = os.path.join(os.getcwd(), "test_folder")
    os.makedirs(test_folder, exist_ok=True)
    
    print(f"Testing folder opening for: {test_folder}")
    
    system = platform.system()
    
    if system == "Windows":
        # Try pywinauto approach for foreground opening
        try:
            import pywinauto
            print("✓ pywinauto is available")
            
            abs_path = os.path.abspath(test_folder)
            print(f"Opening folder: {abs_path}")
            
            # Method 1: Open folder and then find the window
            os.startfile(abs_path)
            print("✓ os.startfile() executed")
            
            # Give explorer a moment to open the window
            time.sleep(1.5)
            print("✓ Waited for Explorer to open")
            
            # Try to find and activate the Explorer window
            try:
                # Connect to all Explorer windows
                app = pywinauto.Application(backend="uia").connect(class_name="CabinetWClass")
                print("✓ Connected to Explorer windows")
                
                # Look for window with matching folder name in title
                folder_name = os.path.basename(abs_path)
                windows = app.windows()
                print(f"✓ Found {len(windows)} Explorer windows")
                
                target_window = None
                for i, window in enumerate(windows):
                    try:
                        window_text = window.window_text()
                        print(f"  Window {i+1}: '{window_text}'")
                        # Check if folder name is in window title
                        if folder_name.lower() in window_text.lower():
                            target_window = window
                            print(f"  ^ MATCH found for folder: {folder_name}")
                            break
                    except Exception as e:
                        print(f"  Window {i+1}: Error getting text - {e}")
                        continue
                
                if target_window:
                    # Bring window to foreground
                    target_window.set_focus()
                    target_window.restore()  # In case it's minimized
                    print(f"✓ Successfully brought Explorer window to foreground: {target_window.window_text()}")
                    return True
                else:
                    print(f"✗ Could not find Explorer window for folder: {folder_name}")
                    return False
                    
            except Exception as e:
                print(f"✗ Could not bring window to foreground using pywinauto: {e}")
                return False
            
        except ImportError:
            print("✗ pywinauto not available")
            return False
    else:
        print(f"✗ Not running on Windows (system: {system})")
        return False

if __name__ == "__main__":
    success = test_folder_opening()
    print(f"\nTest result: {'SUCCESS' if success else 'FAILED'}")