"""
Default implementation of IPipelineContext.

This module provides a concrete implementation of the IPipelineContext interface.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.interfaces.pipeline.context import IPipelineContext


@dataclass
class PipelineContext(IPipelineContext):
    """
    Default implementation of IPipelineContext.

    This class provides a thread-safe implementation of the pipeline context
    that can be used to pass data between pipeline stages.
    """

    data: Dict[str, Any] = field(default_factory=dict)
    temp_dir: Optional[Path] = None
    video_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize after dataclass sets the attributes."""
        # Ensure temp_dir is a Path object
        if self.temp_dir is not None and not isinstance(self.temp_dir, Path):
            self.temp_dir = Path(self.temp_dir)

        # Ensure video_id is a string
        if self.video_id is not None:
            self.video_id = str(self.video_id)

    @property
    def temp_dir(self) -> Optional[Path]:
        """Get the temporary directory path."""
        return self._temp_dir if hasattr(self, "_temp_dir") else None

    @temp_dir.setter
    def temp_dir(self, value: Optional[Union[str, Path]]) -> None:
        """Set the temporary directory path.

        Args:
            value: Path to directory (str or Path). If None, temp_dir will be set to None.
        """
        if value is not None:
            self._temp_dir = Path(value)
            if not self._temp_dir.exists():
                self._temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = None

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context data.

        Args:
            key: The key to look up
            default: Default value if key is not found

        Returns:
            The value associated with the key, or default if key doesn't exist
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the context data.

        Args:
            key: The key to set
            value: The value to store
        """
        self.data[key] = value

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple values in the context data.

        Args:
            data: Dictionary of updates to apply
        """
        self.data.update(data)

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
