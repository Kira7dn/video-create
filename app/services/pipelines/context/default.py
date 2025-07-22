"""
Default implementation of IPipelineContext.

This module provides a concrete implementation of the IPipelineContext interface.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.interfaces.pipeline.context import IPipelineContext


class PipelineContext(IPipelineContext):
    """
    Default implementation of IPipelineContext.

    This class provides a thread-safe implementation of the pipeline context
    that can be used to pass data between pipeline stages.

    Args:
        data: Dictionary containing context data
        temp_dir: Path to temporary directory (str or Path)
        video_id: Optional video identifier
        metadata: Additional metadata dictionary
    """
    
    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        temp_dir: Optional[Union[str, Path]] = None,
        video_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize the pipeline context."""
        # Initialize private attributes with default values
        self._data: Dict[str, Any] = {}
        self._temp_dir: Optional[Path] = None
        self._video_id: Optional[str] = None
        self._metadata: Dict[str, Any] = {}
        
        # Use property setters to ensure validation
        if data is not None:
            self.data = data
        if temp_dir is not None:
            self.temp_dir = temp_dir
        if video_id is not None:
            self.video_id = video_id
        if metadata is not None:
            self.metadata = metadata

    @property
    def data(self) -> Dict[str, Any]:
        """Get the context data dictionary."""
        return self._data

    @data.setter
    def data(self, value: Dict[str, Any]) -> None:
        """Set the context data dictionary."""
        self._data = value or {}

    @property
    def temp_dir(self) -> Optional[Path]:
        """Get the temporary directory path."""
        return self._temp_dir

    @temp_dir.setter
    def temp_dir(self, value: Optional[Union[str, Path]]) -> None:
        """Set the temporary directory path.
        
        Args:
            value: Path to directory (str or Path). If None, temp_dir will be set to None.
        """
        self._temp_dir = Path(value) if value else None
        
        # Create directory if it doesn't exist
        if self._temp_dir and not self._temp_dir.exists():
            self._temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def video_id(self) -> Optional[str]:
        """Get the video ID.
        
        Returns:
            Optional[str]: The video identifier or None if not set
        """
        return self._video_id

    @video_id.setter
    def video_id(self, value: Optional[str]) -> None:
        """Set the video ID.
        
        Args:
            value: The video identifier string or None
        """
        self._video_id = str(value) if value is not None else None

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get the metadata dictionary.
        
        Returns:
            Dict[str, Any]: A dictionary containing metadata
        """
        return self._metadata

    @metadata.setter
    def metadata(self, value: Optional[Dict[str, Any]]) -> None:
        """Set the metadata dictionary.
        
        Args:
            value: Dictionary containing metadata. If None, an empty dict will be used.
        """
        self._metadata = value or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context data.

        Args:
            key: The key to look up
            default: Default value if key is not found

        Returns:
            The value associated with the key, or default if key doesn't exist
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the context data.

        Args:
            key: The key to set
            value: The value to store
        """
        self._data[key] = value

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple values in the context data.

        Args:
            data: Dictionary of updates to apply
        """
        self._data.update(data)
