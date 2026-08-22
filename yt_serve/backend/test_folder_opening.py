#!/usr/bin/env python3
"""
Test script for the refactored folder opening functionality
"""
import os
import sys
import tempfile

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.system import open_folder_in_explorer, get_system_info


def test_folder_opening():
    """Test the folder opening functionality"""
    print("=== System Info ===")
    system_info = get_system_info()
    for key, value in system_info.items():
        print(f"{key}: {value}")
    
    print("\n=== Testing Folder Opening ===")
    
    # Create a temporary test folder
    with tempfile.TemporaryDirectory() as temp_dir:
        test_folder = os.path.join(temp_dir, "test_playlist_folder")
        os.makedirs(test_folder, exist_ok=True)
        
        print(f"Test folder: {test_folder}")
        
        try:
            result = open_folder_in_explorer(test_folder)
            print(f"✓ Success: {result}")
            return True
        except Exception as e:
            print(f"✗ Error: {e}")
            return False


def test_nonexistent_folder():
    """Test error handling for nonexistent folder"""
    print("\n=== Testing Error Handling ===")
    
    nonexistent = "/path/that/does/not/exist"
    try:
        result = open_folder_in_explorer(nonexistent)
        print(f"✗ Unexpected success: {result}")
        return False
    except FileNotFoundError as e:
        print(f"✓ Correctly caught FileNotFoundError: {e}")
        return True
    except Exception as e:
        print(f"✗ Unexpected error type: {e}")
        return False


if __name__ == "__main__":
    print("Testing refactored folder opening functionality...\n")
    
    success1 = test_folder_opening()
    success2 = test_nonexistent_folder()
    
    overall_success = success1 and success2
    print(f"\n=== Overall Result: {'SUCCESS' if overall_success else 'FAILED'} ===")