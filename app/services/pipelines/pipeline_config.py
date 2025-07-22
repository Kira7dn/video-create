"""
Cấu hình các stages cho video creation pipeline.
"""

from typing import List, Dict, Any


def get_video_creation_stages() -> List[Dict[str, Any]]:
    """
    Trả về danh sách các stages cho video creation pipeline.

    Returns:
        List[Dict]: Danh sách các stage với cấu hình tương ứng
    """
    return [
        # Stage 1: Request validation
        {
            "type": "processor",
            "name": "request_validation",
            "processor_class": "app.services.processors.validation.ValidationProcessor.create_chained_validator",
            "input_key": "json_data",
            "output_key": "validated_data",
            "required_inputs": ["json_data"],
        },
        # Stage 2: Download assets
        {
            "type": "processor",
            "name": "download_assets",
            "processor_class": "app.services.processors.io.DownloadProcessor",
            "input_key": "validated_data",
            "output_key": "download_results",
            "required_inputs": ["validated_data"],
        },
        # Stage 3: Image auto processing
        {
            "type": "processor",
            "name": "image_auto",
            "processor_class": "app.services.processors.image_auto_processor.ImageAutoProcessor",
            "input_key": "download_results",
            "output_key": "processed_segments",
            "required_inputs": ["download_results"],
        },
        # Stage 4: Text overlay alignment
        {
            "type": "processor",
            "name": "text_overlay_alignment",
            "processor_class": "app.services.processors.transcript_processor.TranscriptProcessor",
            "input_key": "processed_segments",
            "output_key": "processed_segments",
            "required_inputs": ["processed_segments"],
        },
        # Stage 5: Create segment clips
        {
            "type": "processor",
            "name": "create_segment_clips",
            "processor_class": "app.services.processors.workflow.segment_processor.SegmentProcessor",
            "input_key": "processed_segments",
            "output_key": "segment_clips",
            "required_inputs": ["processed_segments"],
        },
        # Stage 6: Concatenate video segments
        {
            "type": "processor",
            "name": "concatenate_video",
            "processor_class": "app.services.processors.concatenation_processor.ConcatenationProcessor",
            "input_key": "segment_clips",
            "output_key": "final_video_path",
            "required_inputs": ["segment_clips", "transitions", "background_music"],
        },
        # Stage 7: Upload to S3
        {
            "type": "processor",
            "name": "upload",
            "processor_class": "app.services.processors.s3_upload_processor.S3UploadProcessor",
            "input_key": "final_video_path",
            "output_key": "s3_upload_result",
        },
    ]
