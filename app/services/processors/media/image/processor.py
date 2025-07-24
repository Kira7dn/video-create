"""
ImageAutoProcessor: Kiểm tra và tự động thay thế ảnh cho segment nếu ảnh không hợp lệ.
- Sử dụng PydanticAI để trích xuất keywords thông minh từ segment text với type safety.
- Nếu ảnh không phù hợp, tự động tìm kiếm ảnh mới (Pixabay API với AI-enhanced keywords).
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, List, Optional, Tuple
from uuid import uuid4

import requests
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from app.config.settings import settings
from app.core.exceptions import ProcessingError
from app.services.processors.core.base_processor import AsyncProcessor, ProcessingStage
from utils.image_utils import is_image_size_valid, search_pixabay_image

logger = logging.getLogger(__name__)


class KeywordExtractionResult(BaseModel):
    """Structured result for AI keyword extraction"""

    keywords: List[str] = []


class ImageProcessor(AsyncProcessor):
    """
    AI-powered image validation and replacement processor using PydanticAI.
    """

    def __init__(self):
        super().__init__()
        # Luôn dùng trực tiếp settings.openai_api_key
        self.ai_api_key = settings.openai_api_key

        # Initialize PydanticAI Agent
        self._init_ai_agent()

    def _init_ai_agent(self):
        """Initialize PydanticAI Agent for keyword extraction"""
        if self.ai_api_key and settings.ai_keyword_extraction_enabled:
            try:
                # Create OpenAI model instance (PydanticAI sẽ tự động dùng OPENAI_API_KEY từ env)
                model = OpenAIModel(model_name=settings.ai_pydantic_model)

                # Create PydanticAI Agent with structured output
                self.keyword_agent = Agent(
                    model=model,
                    result_type=KeywordExtractionResult,
                    system_prompt="""You are a smart keyword-extraction assistant for image search.

                        Your task: Extract 4-8 multi-word search phrases that are optimized for Pixabay image search.

                        Requirements:
                        • Generate compound keywords (2-4 words each)
                        • Focus on visual, descriptive terms
                        • Avoid generic single words
                        • Prioritize searchable, relevant phrases
                        • Use clear, descriptive language

                        Return structured data with:
                        - keywords: List of 4-8 multi-word search phrases
                        - primary_keyword: Most important keyword
                        - search_strategy: "progressive"

                        Example:
                        Input: "AI Agents will revolutionize technology by 2025"
                        Output: keywords=["futuristic AI assistant", "autonomous technology concept", "digital agent illustration", "AI revolution 2025"]
                        """,
                )
                logger.info("🤖 PydanticAI Agent initialized successfully")
            except (ImportError, ValueError, RuntimeError) as e:
                logger.warning("Failed to initialize PydanticAI Agent: %s", str(e))
                self.keyword_agent = None
        else:
            self.keyword_agent = None

    async def _ai_extract_keywords(
        self, content: str, fields: Optional[List[str]] = None
    ) -> List[str]:
        """
        Dùng PydanticAI để trích xuất từ khóa tìm kiếm thông minh từ content và fields.
        Trả về list keywords theo độ ưu tiên cao → thấp.
        """
        # Kiểm tra setting có enable AI keyword extraction không
        if not settings.ai_keyword_extraction_enabled or not self.keyword_agent:
            # Fallback: trích xuất từ khóa đơn giản
            return fields

        # Chuẩn bị prompt cho PydanticAI Agent
        fields = fields or []
        fields_str = ", ".join(fields)
        user_prompt = (
            f"Extract image search keywords from this content: '{content}' "
            f"with these related fields: [{fields_str}]"
        )

        try:
            # Sử dụng PydanticAI Agent để extract keywords với structured output
            result = await self.keyword_agent.run(user_prompt=user_prompt)

            # Get structured result
            keyword_result: KeywordExtractionResult = result.output

            # Giới hạn số keywords theo setting
            final_keywords = keyword_result.keywords[
                : settings.ai_max_keywords_per_prompt
            ]

            logger.info(
                "🤖 PydanticAI extracted keywords: %s from content: '%s' with fields: %s",
                final_keywords,
                content,
                fields,
            )

            return final_keywords

        except (ValueError, TypeError, RuntimeError) as e:
            logger.warning("PydanticAI keyword extraction failed: %s", str(e))
            # Fallback về trích xuất đơn giản
            return fields

    async def _download_image(
        self,
        content: str,
        fields: List[str],
        temp_dir: str,
    ) -> Tuple[str, str]:
        """
        Tìm kiếm và tải ảnh mới.

        Args:
            content: Nội dung để tìm kiếm ảnh
            fields: Danh sách các trường từ khóa
            temp_dir: Thư mục tạm để lưu ảnh

        Returns:
            Tuple chứa (image_url, local_path)

        Raises:
            ProcessingError: Nếu có lỗi khi tìm kiếm hoặc tải ảnh
        """
        try:
            # Tìm kiếm ảnh mới
            new_url = await self._ai_search_image(
                content=content,
                fields=fields,
                min_width=settings.video_min_image_width,
                min_height=settings.video_min_image_height,
            )
            if not new_url:
                raise ProcessingError(
                    f"Không tìm được ảnh phù hợp cho content: '{content}' "
                    f"với fields: {fields}"
                )

            # Tạo tên file và đường dẫn mới
            ext = os.path.splitext(new_url)[1] or ".jpg"
            new_filename = f"auto_image_{uuid4().hex}{ext}"
            save_path = Path(temp_dir) / new_filename

            # Tải ảnh về local
            def download_image(url, path):
                with requests.get(url, stream=True, timeout=10) as r:
                    r.raise_for_status()
                    with open(path, "wb") as f:
                        shutil.copyfileobj(r.raw, f)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_image, new_url, str(save_path))

            return new_url, str(save_path)

        except (requests.RequestException, OSError) as e:
            raise ProcessingError(f"Download replacement image failed: {e}") from e

    async def _ai_search_image(
        self,
        content: str,
        fields: Optional[List[str]] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
    ) -> Optional[str]:
        """
        AI-enhanced image search:
        - Dùng PydanticAI trích xuất keywords
        - Thử nhiều keywords với Pixabay để tìm ảnh phù hợp
        """
        pixabay_key = settings.pixabay_api_key
        min_width = min_width or settings.video_min_image_width
        min_height = min_height or settings.video_min_image_height

        # AI trích xuất keywords thông minh với PydanticAI
        keywords_list = await self._ai_extract_keywords(content, fields)

        # Thử từng keyword cho đến khi tìm được ảnh phù hợp
        for keywords in keywords_list:
            url = search_pixabay_image(keywords, pixabay_key, min_width, min_height)
            if url:
                logger.info(
                    "✅ Found image with keywords: %s for content: '%s'",
                    keywords,
                    content,
                )
                return url

        # Nếu không tìm được gì, thử keyword fallback cuối cùng
        fallback_url = search_pixabay_image(
            "abstract background", pixabay_key, min_width, min_height
        )
        if fallback_url:
            logger.warning("⚠️ Using fallback image for content: '%s'", content)

        return fallback_url

    async def process(self, input_data: Any, **kwargs) -> Any:
        """Async implementation of image processing and validation

        Args:
            input_data: download_results (list: result_segments)
            **kwargs: Additional parameters including 'context' with segments and other metadata

        Returns:
            Processed segment results with validated/replaced images

        Raises:
            ProcessingError: If image processing or validation fails
        """
        metric = self._start_processing(ProcessingStage.DOWNLOAD)
        try:
            download_results = input_data
            context = kwargs.get("context")
            temp_dir = context.temp_dir

            if not temp_dir:
                raise ProcessingError("temp_dir is required in context")

            if not context:
                raise ProcessingError("Context is required for ImageAutoProcessor")
            if not download_results:
                raise ProcessingError("Invalid download results format")

            result_segments = download_results
            # Check segment count matches asset count
            keywords = context.get("keywords")

            min_width = settings.video_min_image_width
            min_height = settings.video_min_image_height

            new_result_segments = []
            for segment in result_segments:
                # Kiểm tra video trước, nếu có video thì valid = True luôn
                video_obj = segment.get("video")
                if video_obj:
                    valid = True
                else:
                    # Nếu không có video, kiểm tra image
                    image_obj = segment.get("image", {})
                    image_path = image_obj.get("local_path")
                    valid = False
                    if image_path:
                        valid = is_image_size_valid(image_path, min_width, min_height)

                # Tách content và fields để truyền riêng biệt
                content = segment.get("voice_over", {}).get("content", "")
                fields = keywords  # keywords từ context

                merged_asset = segment.copy()
                # Chỉ thay thế ảnh nếu không phải video và ảnh không hợp lệ
                if not valid:
                    # Tìm kiếm và tải ảnh mới
                    new_url, local_path = await self._download_image(
                        content=content, fields=fields, temp_dir=temp_dir
                    )

                    # Cập nhật thông tin asset
                    if "image" in merged_asset and isinstance(
                        merged_asset["image"], dict
                    ):
                        merged_asset["image"]["url"] = new_url
                        merged_asset["image"]["local_path"] = local_path
                    else:
                        merged_asset["image"] = {
                            "url": new_url,
                            "local_path": local_path,
                        }

                new_result_segments.append(merged_asset)

            self._end_processing(
                metric, success=True, items_processed=len(new_result_segments)
            )
            return new_result_segments

        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise ProcessingError(f"Image validation/search failed: {e}") from e
