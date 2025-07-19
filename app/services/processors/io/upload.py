"""
S3UploadProcessor: Uploads video file to AWS S3 bucket.

- Inherits BaseProcessor
- Uses async/await
- Handles errors with ProcessingError
- Tracks metrics with MetricsCollector
- Uses settings from app.config.settings
- Structured logging
"""

from typing import Any, Optional
import logging
import os
import asyncio
import boto3
from app.services.processors.core.base_processor import (
    BaseProcessor,
    ProcessingStage,
    MetricsCollector,
)
from app.config.settings import settings
from app.core.exceptions import ProcessingError, UploadError


class S3UploadProcessor(BaseProcessor):
    """
    Processor for uploading video files to AWS S3.

    Example:
        processor = S3UploadProcessor(metrics_collector)
        s3_url = await processor.process(video_path, context=context)
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.logger = logging.getLogger(__name__)

    async def _process_async(self, input_data: Any, **kwargs) -> str:
        """Async implementation of S3 upload processing.

        Args:
            input_data: Path to the video file to upload. Could be a coroutine
            that resolves to a path.
            **kwargs: Additional parameters, must contain 'context' with video_id.

        Returns:
            str: S3 URL of the uploaded video or local path if S3 not configured.

        Raises:
            ProcessingError: If upload fails or required parameters are missing.
        """
        # If input_data is a coroutine, await it to get the actual path
        if asyncio.iscoroutine(input_data):
            input_data = await input_data

        # Ensure we have a string path
        if not isinstance(input_data, (str, bytes, os.PathLike)):
            raise ProcessingError(
                f"Expected file path, got {type(input_data).__name__}"
            )

        # Process with the actual path
        return await self.process(input_data, **kwargs)

    async def process(self, input_data: Any, **kwargs) -> str:
        """
        Uploads the video file to S3 and returns the S3 URL.

        Args:
            input_data (Any): Path to the video file.
            **kwargs: Must contain 'context' with video_id.
        Returns:
            str: S3 URL of the uploaded video or local path if S3 not configured.
        Raises:
            ProcessingError: If upload fails.
        """

        metric = self._start_processing(ProcessingStage.UPLOAD)
        video_path = input_data
        context = kwargs["context"]  # Pipeline always provides context
        video_id = context.video_id
        bucket = settings.aws_s3_bucket
        region = settings.aws_s3_region
        aws_key = settings.aws_access_key_id
        aws_secret = settings.aws_secret_access_key
        key = f"{settings.aws_s3_prefix}{video_id}.mp4"

        # Validate input
        if not video_path or not video_id:
            self._end_processing(
                metric, success=False, error_message="Missing video_path or video_id"
            )
            self.logger.error("Missing video_path or video_id for S3 upload")
            raise UploadError(
                "Missing video_path or video_id for S3 upload", video_id=video_id
            )

        # Check if S3 configuration is available
        if not bucket or not region or not aws_key or not aws_secret:
            self._end_processing(metric, success=True, items_processed=0)
            self.logger.info("S3 upload skipped - AWS configuration not provided")
            return f"local://{video_path}"  # Return local path as fallback

        try:
            # Sử dụng boto3 sync trong thread pool để đảm bảo upload thành công
            def upload_to_s3():
                s3_client = boto3.client(
                    "s3",
                    region_name=region,
                    aws_access_key_id=aws_key,
                    aws_secret_access_key=aws_secret,
                )
                with open(video_path, "rb") as f:
                    response = s3_client.upload_fileobj(
                        f, bucket, key, ExtraArgs={"ContentType": "video/mp4"}
                    )
                return response

            # Chạy upload trong thread pool
            await asyncio.get_event_loop().run_in_executor(None, upload_to_s3)

            s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
            self._end_processing(metric, success=True, items_processed=1)
            self.logger.info("Video uploaded to S3: %s", s3_url)
            return s3_url
        except Exception as e:
            error_msg = "Failed to upload video to S3: %s"
            self.logger.error(error_msg, str(e), exc_info=True)
            raise UploadError(error_msg % str(e), video_id=video_id) from e
