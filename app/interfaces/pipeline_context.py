"""
Interface for pipeline context
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class IPipelineContext(ABC):
    """Interface for pipeline context that carries data between stages"""

    # Properties
    data: Dict[str, Any] = field(default_factory=dict)
    temp_dir: Optional[Path] = None
    video_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def temp_dir(self) -> Optional[Path]:
        """Get the temporary directory path"""
        return self._temp_dir

    @temp_dir.setter
    def temp_dir(self, value: Optional[Path]) -> None:
        self._temp_dir = value

    @property
    def video_id(self) -> Optional[str]:
        """Get the video ID"""
        return self._video_id

    @video_id.setter
    def video_id(self, value: Optional[str]) -> None:
        self._video_id = value

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get the metadata dictionary"""
        return self._metadata

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        self._metadata = value

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context by key

        Args:
            key: Key to get the value for
            default: Default value if key is not found

        Returns:
            The value for the key or default if not found
        """

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the context

        Args:
            key: Key to set
            value: Value to set
        """

    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple values in the context

        Args:
            data: Dictionary of key-value pairs to update
        """
