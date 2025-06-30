#!/usr/bin/env python3
"""
Manual cleanup script for existing temp directories
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from app.services.video_service import VideoCreationService

if __name__ == "__main__":
    service = VideoCreationService()

    # Force cleanup of all existing temp directories (regardless of age)
    print("🧹 Cleaning up all existing temp directories...")
    service.cleanup_old_temp_directories(max_age_hours=0.1)  # Very short age threshold
    print("✅ Cleanup completed!")
