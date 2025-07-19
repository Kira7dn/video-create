"""
Metrics collection interfaces.
"""

from typing import Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class IMetricsCollector(Protocol):
    """Interface for collecting and reporting metrics."""

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Numeric value
            tags: Optional key-value tags for categorization
        """

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Counter name
            value: Value to increment by (default: 1)
            tags: Optional key-value tags
        """

    def record_execution_time(
        self, name: str, time_ms: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record execution time in milliseconds.

        Args:
            name: Metric name
            time_ms: Execution time in milliseconds
            tags: Optional key-value tags
        """
