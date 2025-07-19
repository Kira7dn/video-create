"""
Module chứa logic xây dựng và quản lý video creation pipeline.
"""

import importlib
from typing import Any, Dict, Optional

from app.services.processors.base_processor import MetricsCollector

from .pipeline import VideoPipeline
from .pipeline_config import get_video_creation_stages


def _import_class(class_path: str) -> type:
    """
    Import một class từ đường dẫn đầy đủ.

    Args:
        class_path: Đường dẫn đầy đủ đến class (vd: 'module.submodule.ClassName')

    Returns:
        type: Class được import

    Raises:
        ImportError: Nếu không thể import class
    """
    module_path, class_name = class_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import class {class_path}: {e}") from e


def create_video_creation_pipeline(
    metrics_collector: Optional[MetricsCollector] = None,
    custom_stages: Optional[list] = None,
) -> VideoPipeline:
    """
    Tạo và cấu hình video creation pipeline.

    Args:
        metrics_collector: Đối tượng thu thập metrics (nếu có)
        custom_stages: Danh sách các stages tùy chỉnh để ghi đè cấu hình mặc định

    Returns:
        VideoPipeline: Đối tượng pipeline đã được cấu hình
    """
    # Sử dụng metrics_collector nếu được cung cấp, nếu không tạo mới
    if metrics_collector is None:
        metrics_collector = MetricsCollector()

    # Tạo pipeline mới
    pipeline = VideoPipeline(metrics_collector)

    # Lấy danh sách stages (mặc định hoặc tùy chỉnh)
    stages = custom_stages if custom_stages is not None else get_video_creation_stages()

    # Thêm từng stage vào pipeline
    for stage_config in stages:
        _add_stage_to_pipeline(pipeline, stage_config)

    return pipeline


def _add_stage_to_pipeline(
    pipeline: VideoPipeline, stage_config: Dict[str, Any]
) -> None:
    """
    Thêm một stage vào pipeline dựa trên cấu hình.

    Args:
        pipeline: Đối tượng pipeline cần thêm stage
        stage_config: Cấu hình của stage

    Raises:
        ValueError: Nếu cấu hình stage không hợp lệ
    """
    stage_type = stage_config.get("type")
    stage_name = stage_config.get("name")

    if not stage_type or not stage_name:
        raise ValueError("Stage config must include 'type' and 'name'")

    if stage_type == "processor":
        _add_processor_stage(pipeline, stage_config)
    elif stage_type == "function":
        _add_function_stage(pipeline, stage_config)
    else:
        raise ValueError(f"Unknown stage type: {stage_type}")


def _add_processor_stage(pipeline: VideoPipeline, config: Dict[str, Any]) -> None:
    """
    Thêm processor stage vào pipeline.

    Args:
        pipeline: Đối tượng pipeline
        config: Cấu hình của processor stage
    """
    processor_class = _import_class(config["processor_class"])
    processor = processor_class()

    pipeline.add_processor_stage(
        name=config["name"],
        processor=processor,
        input_key=config.get("input_key"),
        output_key=config.get("output_key"),
        required_inputs=config.get("required_inputs", []),
    )


def _add_function_stage(pipeline: VideoPipeline, config: Dict[str, Any]) -> None:
    """
    Thêm function stage vào pipeline.

    Args:
        pipeline: Đối tượng pipeline
        config: Cấu hình của function stage
    """
    # Function sẽ được bind vào sau từ VideoCreationService
    pipeline.add_function_stage(
        name=config["name"],
        func_name=config["function_name"],  # Sẽ được resolve thành method thực tế
        output_key=config.get("output_key"),
        required_inputs=config.get("required_inputs", []),
    )
