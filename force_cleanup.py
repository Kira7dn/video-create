#!/usr/bin/env python3
"""
Force cleanup with delayed scheduling for stubborn temp directories
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from app.services.video_service import VideoCreationService

if __name__ == "__main__":
    service = VideoCreationService()

    # Get all temp directories
    temp_dirs = [d for d in os.listdir(".") if d.startswith("tmp_create_")]

    print(f"Found {len(temp_dirs)} temp directories to clean up")

    for temp_dir in temp_dirs:
        print(f"🕒 Scheduling delayed cleanup for: {temp_dir}")
        service.schedule_delayed_cleanup(temp_dir, delay_seconds=10.0)

    if temp_dirs:
        print("⏳ Cleanup scheduled! Directories will be removed in 10 seconds...")
        import time

        time.sleep(12)  # Wait for cleanup to complete

        # Check results
        remaining_dirs = [d for d in os.listdir(".") if d.startswith("tmp_create_")]
        if remaining_dirs:
            print(f"❌ Still have {len(remaining_dirs)} directories: {remaining_dirs}")
        else:
            print("✅ All temp directories cleaned up successfully!")
    else:
        print("✅ No temp directories found!")
