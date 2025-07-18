"""
Interfaces for video processing components.
"""

from typing import (
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Any,
    Union,
    BinaryIO,
)
from pathlib import Path


@runtime_checkable
class IVideoProcessor(Protocol):
    """Interface for video processing operations.

    This protocol defines the contract that any video processor implementation
    must follow to be compatible with the VideoCreationService.
    """

    async def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        """Create a video clip from a single segment.

        Args:
            segment: Dictionary containing segment information
            temp_dir: Temporary directory for intermediate files

        Returns:
            Path to the created video clip
            
        Raises:
            VideoCreationError: If there's an error creating the segment clip
        """

    def concatenate_clips(
        self,
        video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        transitions: Optional[list] = None,
        background_music: Optional[dict] = None,
        default_transition_type: str = "fade",
        default_transition_duration: float = 1.0,
    ) -> str:
        """Concatenate multiple video clips into a single video.

        Args:
            video_segments: List of video segment information
            output_path: Path to save the output video
            temp_dir: Temporary directory for intermediate files
            transitions: List of transition configurations
            background_music: Background music configuration
            default_transition_type: Default transition type
            default_transition_duration: Default transition duration in seconds

        Returns:
            Path to the concatenated video file
        """


@runtime_checkable
class IDownloader(Protocol):
    """Interface for downloading resources from various sources"""

    async def download(self, url: str, destination: Union[str, Path], **kwargs) -> str:
        """Download a resource from URL to destination

        Args:
            url: Source URL to download from
            destination: Local path or directory to save the downloaded file
            **kwargs: Additional download options

        Returns:
            Path to the downloaded file
        """

    async def batch_download(
        self, resources: List[Dict[str, Any]], destination_dir: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Download multiple resources in batch

        Args:
            resources: List of resource dictionaries containing at least 'url' key
            destination_dir: Directory to save downloaded files

        Returns:
            List of download results with status and file paths
        """


@runtime_checkable
class IUploader(Protocol):
    """Interface for uploading files to various destinations"""

    async def upload(
        self, file_path: Union[str, Path], destination: str, **kwargs
    ) -> Dict[str, Any]:
        """Upload a file to destination

        Args:
            file_path: Path to the local file to upload
            destination: Target destination (e.g., S3 path, remote URL)
            **kwargs: Additional upload options

        Returns:
            Upload result metadata
        """

    async def upload_stream(
        self, file_obj: BinaryIO, destination: str, **kwargs
    ) -> Dict[str, Any]:
        """Upload a file-like object directly

        Args:
            file_obj: File-like object to upload
            destination: Target destination
            **kwargs: Additional upload options

        Returns:
            Upload result metadata
        """


@runtime_checkable
class IValidator(Protocol):
    """Interface for data validation"""

    def validate(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate data against a schema

        Args:
            data: Data to validate
            schema: Validation schema

        Returns:
            True if validation passes, False otherwise
        """

    def get_validation_errors(self) -> List[Dict[str, Any]]:
        """Get validation errors from the last validation

        Returns:
            List of error dictionaries with details
        """


@runtime_checkable
class IMetricsCollector(Protocol):
    """Interface for collecting and reporting metrics"""

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric value

        Args:
            name: Metric name
            value: Numeric value
            tags: Optional key-value tags for categorization
        """

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric

        Args:
            name: Counter name
            value: Value to increment by (default: 1)
            tags: Optional key-value tags
        """

    def record_execution_time(
        self, name: str, time_ms: float, tags: Optional[Dict[str, str]] = None
    ):
        """Record execution time in milliseconds

        Args:
            name: Metric name
            time_ms: Execution time in milliseconds
            tags: Optional key-value tags
        """
