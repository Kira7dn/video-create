"""
Storage-related interfaces.
"""

from pathlib import Path
from typing import Dict, Any, List, Union, BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class IDownloader(Protocol):
    """Interface for downloading resources from various sources."""

    async def download(self, url: str, destination: Union[str, Path], **kwargs) -> str:
        """Download a resource from URL to destination.

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
        """Download multiple resources in batch.

        Args:
            resources: List of resource dictionaries containing at least 'url' key
            destination_dir: Directory to save downloaded files

        Returns:
            List of download results with status and file paths
        """


@runtime_checkable
class IUploader(Protocol):
    """Interface for uploading files to various destinations."""

    async def upload(
        self, file_path: Union[str, Path], destination: str, **kwargs
    ) -> Dict[str, Any]:
        """Upload a file to destination.

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
        """Upload a file-like object directly.

        Args:
            file_obj: File-like object to upload
            destination: Target destination
            **kwargs: Additional upload options

        Returns:
            Upload result metadata
        """
