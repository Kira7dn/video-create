"""
Shared subprocess utilities for video processing
"""

import subprocess
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class SubprocessError(Exception):
    """Custom exception for subprocess errors"""
    pass


def safe_subprocess_run(cmd, operation_name="FFmpeg operation", custom_logger: Optional[Any] = None):
    """
    Safely run subprocess with proper error handling
    
    Args:
        cmd: Command to run as list of strings
        operation_name: Descriptive name for the operation (for logging)
        custom_logger: Optional logger to use instead of default
        
    Returns:
        subprocess.CompletedProcess result
        
    Raises:
        SubprocessError: If subprocess fails or FFmpeg not found
    """
    active_logger = custom_logger or logger
    
    try:
        if active_logger:
            active_logger.debug(f"Running {operation_name}: {' '.join(str(x) for x in cmd)}")
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"{operation_name} failed with return code {e.returncode}"
        if e.stderr:
            error_msg += f"\nFFmpeg stderr: {e.stderr}"
        if e.stdout:
            error_msg += f"\nFFmpeg stdout: {e.stdout}"
        if active_logger:
            active_logger.error(error_msg)
        raise SubprocessError(error_msg) from e
    except FileNotFoundError as e:
        error_msg = f"{operation_name} failed: FFmpeg not found. Please ensure FFmpeg is installed and in PATH."
        if active_logger:
            active_logger.error(error_msg)
        raise SubprocessError(error_msg) from e
