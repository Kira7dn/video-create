"""
Interface for pipeline context that carries data between stages.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class IPipelineContext(ABC):
    """
    Interface for pipeline context that carries data between stages.
    """

    # Properties
    data: Dict[str, Any] = field(default_factory=dict)
    temp_dir: Optional[Path] = None
    video_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    @abstractmethod
    def temp_dir(self) -> Optional[Path]:
        """Get the temporary directory path."""

    @temp_dir.setter
    @abstractmethod
    def temp_dir(self, value: Optional[Path]) -> None:
        """Set the temporary directory path."""

    @property
    @abstractmethod
    def video_id(self) -> Optional[str]:
        """Get the video ID."""

    @video_id.setter
    @abstractmethod
    def video_id(self, value: Optional[str]) -> None:
        """Set the video ID."""

    @property
    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Get the metadata dictionary."""

    @metadata.setter
    @abstractmethod
    def metadata(self, value: Dict[str, Any]) -> None:
        """Set the metadata dictionary."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context data.

        Args:
            key: The key to look up
            default: Default value if key is not found

        Returns:
            The value associated with the key, or default if key doesn't exist
        """

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the context data.

        Args:
            key: The key to set
            value: The value to store
        """

    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple values in the context data.

        Args:
            data: Dictionary of updates to apply
        """
