"""
Default implementation of IPipelineContext.

This module provides a concrete implementation of the IPipelineContext interface.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from app.interfaces.pipeline.context import IPipelineContext


@dataclass
class DefaultPipelineContext(IPipelineContext):
    """
    Default implementation of IPipelineContext.
    
    This class provides a thread-safe implementation of the pipeline context
    that can be used to pass data between pipeline stages.
    """

    _data: Dict[str, Any] = field(default_factory=dict)
    _temp_dir: Optional[Path] = None
    _video_id: Optional[str] = None
    _metadata: Dict[str, Any] = field(default_factory=dict)

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
    def temp_dir(self, value: Optional[Path]) -> None:
        """Set the temporary directory path."""
        self._temp_dir = Path(value) if value else None

    @property
    def video_id(self) -> Optional[str]:
        """Get the video ID."""
        return self._video_id

    @video_id.setter
    def video_id(self, value: Optional[str]) -> None:
        """Set the video ID."""
        self._video_id = value

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get the metadata dictionary."""
        return self._metadata

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Set the metadata dictionary."""
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
