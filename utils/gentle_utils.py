"""
Utils for working with Gentle forced alignment service.
Provides functionality to call Gentle API and verify alignment quality.
"""
import logging
import os
import time
from typing import Dict, List, Tuple, Optional, Any
import requests

# Type alias for logger
LoggerType = logging.Logger

class GentleAlignmentError(Exception):
    """Base exception for Gentle alignment errors."""
    pass

class GentleAlignmentVerificationError(GentleAlignmentError):
    """Raised when alignment verification fails."""
    pass

def verify_alignment_quality(word_items: List[Dict[str, Any]], 
                           min_success_ratio: float = 0.5,
                           logger: Optional[LoggerType] = None) -> Dict[str, Any]:
    """
    Verify the quality of Gentle alignment results.
    
    Args:
        word_items: List of word items from Gentle API response
        min_success_ratio: Minimum ratio of successfully aligned words (0-1)
        min_confidence: Minimum average confidence score (0-1)
        
    Returns:
        Dict containing verification results and statistics
        
    Raises:
        GentleAlignmentVerificationError: If alignment quality is below thresholds
    """
    if not word_items:
        raise GentleAlignmentVerificationError("No word items provided for verification")
    
    total_words = len(word_items)
    success_words = [w for w in word_items if w.get("case") == "success"]
    success_count = len(success_words)
    success_ratio = success_count / total_words if total_words > 0 else 0
    
    # Calculate confidence metrics (Gentle default build often lacks meaningful confidence values)
    valid_confidences = [
        w.get("confidence", 0)
        for w in success_words
        if w.get("confidence") is not None and w.get("confidence") > 0
    ]

    confidence_available = bool(valid_confidences)

    if confidence_available:
        avg_confidence = sum(valid_confidences) / len(valid_confidences)
    else:
        # No non-zero confidences – treat as unavailable (set 0 but skip threshold check later)
        avg_confidence = 0.0
    
    # Check for alignment issues
    alignment_issues = []
    for word in word_items:
        if word.get("case") != "success":
            alignment_issues.append({
                "word": word.get("word"),
                "case": word.get("case"),
                "start": word.get("start"),
                "end": word.get("end")
            })
    
    # Verify quality thresholds
    #   • Always check success_ratio
    # Confidence is not used for verification in default Gentle builds
    is_verified = success_ratio >= min_success_ratio
    
    result = {
        "is_verified": is_verified,
        "total_words": total_words,
        "success_count": success_count,
        "success_ratio": success_ratio,
        "alignment_issues": alignment_issues,
        "issues_count": len(alignment_issues),
        "verification_passed": is_verified,
        "verification_feedback": ""
    }
    
    if not is_verified:
        feedback = []
        if success_ratio < min_success_ratio:
            feedback.append(
                f"Success ratio ({success_ratio:.2f}) is below minimum ({min_success_ratio})"
            )

        result["verification_feedback"] = "; ".join(feedback)
    
    return result

async def align_audio_with_transcript(
    audio_path: str,
    transcript_path: str,
    gentle_url: str = "http://localhost:8765/transcriptions",
    timeout: int = 600,  # Tăng timeout lên 10 phút
    verify_quality: bool = True,
    min_success_ratio: float = 0.8,
    logger: Optional[LoggerType] = None,
    max_retries: int = 3,  # Số lần thử lại tối đa
    retry_delay: int = 10  # Thời gian chờ giữa các lần thử (giây)
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Align audio with transcript using Gentle API and optionally verify alignment quality.
    
    Args:
        audio_path: Path to audio file
        transcript_path: Path to transcript text file
        gentle_url: Gentle API endpoint URL
        timeout: Request timeout in seconds
        verify_quality: Whether to verify alignment quality
        min_success_ratio: Minimum ratio of successfully aligned words (0-1)
        logger: Optional logger instance for logging
        
    Returns:
        Tuple of (Gentle API response, verification result)
        
    Raises:
        GentleAlignmentError: If alignment fails
        GentleAlignmentVerificationError: If verification is enabled and fails
    """
    start_time = time.time()
    
    active_logger = logger or logging.getLogger(__name__)
    last_error = None
    
    # Log file info
    active_logger.debug(f"Preparing to send files to Gentle API:")
    active_logger.debug(f"- Audio: {audio_path} (exists: {os.path.exists(audio_path)}, size: {os.path.getsize(audio_path) / 1024:.2f} KB)")
    active_logger.debug(f"- Transcript: {transcript_path} (exists: {os.path.exists(transcript_path)})")
    
    # Prepare files for upload
    audio_file = None
    transcript_file = None
    
    try:
        audio_file = open(audio_path, 'rb')
        transcript_file = open(transcript_path, 'r', encoding='utf-8')
        
        # Read first 100 bytes for verification
        first_bytes = audio_file.read(100)
        audio_file.seek(0)  # Reset file pointer after reading
        
        files = {
            'audio': (os.path.basename(audio_path), audio_file, 'audio/mp3'),
            'transcript': (os.path.basename(transcript_path), transcript_file)
        }
        
        active_logger.debug(f"Files prepared for upload. Audio first 100 bytes: {first_bytes}")
        
        for attempt in range(1, max_retries + 1):
            try:
                # Log start of alignment
                active_logger.info(
                    "[Attempt %d/%d] Starting Gentle alignment for audio: %s, transcript: %s",
                    attempt, max_retries, audio_path, transcript_path
                )
                
                # Log request details
                active_logger.debug(f"Sending POST request to {gentle_url}?async=false")
                
                # Send request with progress tracking
                start_time = time.time()
                with requests.Session() as session:
                    # Add custom headers
                    session.headers.update({
                        'User-Agent': 'Video-Create/1.0',
                        'Accept': 'application/json'
                    })
                    
                    active_logger.debug(f"Request headers: {dict(session.headers)}")
                    
                    # Send the request
                    response = session.post(
                        f"{gentle_url}?async=false",
                        files=files,
                        timeout=timeout
                    )
                
                # Log response info
                duration = time.time() - start_time
                active_logger.info(f"Received response in {duration:.2f}s. Status code: {response.status_code}")
                active_logger.debug(f"Response headers: {dict(response.headers)}")
                
                response.raise_for_status()
                result = response.json()
                
                # Verify alignment quality if required
                if verify_quality:
                    word_items = result.get("words", [])
                    active_logger.debug(f"Verifying alignment quality for {len(word_items)} word items")
                    verification_result = verify_alignment_quality(
                        word_items,
                        min_success_ratio=min_success_ratio,
                        logger=active_logger
                    )
                    active_logger.info("Alignment verification passed")
                
                # Log successful alignment
                active_logger.info(
                    "Gentle alignment completed in %.2f seconds. Successfully aligned %d/%d words (%.1f%%)",
                    duration,
                    len([w for w in result.get("words", []) if w.get("case") == "success"]),
                    len(result.get("words", [])),
                    (len([w for w in result.get("words", []) if w.get("case") == "success"]) / 
                     max(1, len(result.get("words", [])))) * 100
                )
                
                # Print alignment results
                active_logger.info("\n=== Alignment Results ===")
                active_logger.info(f"Total words: {len(result.get('words', []))}")
                
                # Calculate statistics
                success_words = [w for w in result.get("words", []) if w.get("case") == "success"]
                success_ratio = len(success_words) / max(1, len(result.get("words", [])))
                
                
                active_logger.debug(
                    "Alignment statistics - Success: %d/%d (%.1f%%)",
                    len(success_words),
                    len(result.get("words", [])),
                    success_ratio * 100,
                )
                
                active_logger.info("Successfully aligned: %d/%d (%.1f%%)", 
                                 len(success_words), 
                                 len(result.get("words", [])), 
                                 success_ratio * 100)

                
                # Print first few aligned words
                if success_words:
                    active_logger.info("\nFirst 5 aligned words:")
                    for i, word in enumerate(success_words[:5], 1):
                        active_logger.info(
                            "%d. %s: %.2fs - %.2fs",
                            i,
                            word.get("word", ""),
                            float(word.get("start", 0)),
                            float(word.get("end", 0))
                        )
                
                return result, {
                    "success_ratio": success_ratio,
                    "aligned_words": len(success_words),
                    "total_words": len(result.get("words", []))
                }
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    active_logger.warning(
                        "Attempt %d/%d failed: %s. Retrying in %d seconds...",
                        attempt, max_retries, str(e), wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    active_logger.error("All %d attempts failed. Last error: %s", max_retries, str(e))
                    raise GentleAlignmentError(f"Failed to call Gentle API after {max_retries} attempts: {str(e)}")
    finally:
        # Ensure files are properly closed
        if audio_file:
            audio_file.close()
        if transcript_file:
            transcript_file.close()


def filter_successful_words(word_items: List[Dict[str, Any]], 
                          logger: Optional[LoggerType] = None) -> List[Dict[str, Any]]:
    """Filter and return only successfully aligned words.
    
    Args:
        word_items: List of word items from Gentle API response
        logger: Optional logger instance for logging
        
    Returns:
        List of successfully aligned word items
    """
    return [w for w in word_items if w.get("case") == "success"]

def get_alignment_statistics(word_items: List[Dict[str, Any]], 
                          logger: Optional[LoggerType] = None) -> Dict[str, Any]:
    """Get statistics about alignment results.
    
    Args:
        word_items: List of word items from Gentle API response
        logger: Optional logger instance for logging
        
    Returns:
        Dict containing alignment statistics
    """
    active_logger = logger or logging.getLogger(__name__)
    
    if not word_items:
        active_logger.debug("No word items provided for statistics")
        return {}
        
    try:
        success_words = [w for w in word_items if w.get("case") == "success"]
        total_words = len(word_items)
        
        stats = {
            "total_words": total_words,
            "success_count": len(success_words),
            "success_ratio": len(success_words) / max(1, total_words),
        }
        
        active_logger.debug(
            "Alignment statistics - Success: %d/%d (%.1f%%)",
            stats["success_count"], stats["total_words"], stats["success_ratio"] * 100
        )
        
        return stats
        
    except Exception as e:
        active_logger.error("Error calculating alignment statistics: %s", str(e), exc_info=True)
        return {}
