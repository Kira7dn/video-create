"""
ImageAutoProcessor: Kiểm tra và tự động thay thế ảnh cho segment nếu ảnh không hợp lệ.
- Sử dụng PydanticAI để trích xuất keywords thông minh từ segment text với type safety.
- Nếu ảnh không phù hợp, tự động tìm kiếm ảnh mới (Pixabay API với AI-enhanced keywords).
"""
from typing import List, Dict, Any, Optional
from app.services.processors.base_processor import BaseProcessor, ProcessingStage
from app.core.exceptions import ProcessingError
from app.config.settings import settings
from utils.image_utils import is_image_size_valid, search_pixabay_image
import logging
import os
import requests
import shutil
from uuid import uuid4
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

logger = logging.getLogger(__name__)


class KeywordExtractionResult(BaseModel):
    """Structured result for AI keyword extraction"""
    keywords: List[str]
    primary_keyword: str
    search_strategy: str = "progressive"  # progressive, fallback, or specific

class ImageAutoProcessor(BaseProcessor):
    """
    AI-powered image validation and replacement processor using PydanticAI.
    """
    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
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
                    system_prompt="""You are an expert image search specialist. 
Extract 3-5 best English keywords to find suitable stock photos for the given content.
Focus on visual, concrete terms rather than abstract concepts.
Return keywords optimized for Pixabay search.

Guidelines:
- Use short, specific keywords (1-2 words each)
- Prioritize visual elements over concepts
- Include relevant objects, settings, emotions, styles
- Make primary_keyword the most important/specific term
- Examples: "business meeting" → keywords: ["business", "meeting", "office", "professional", "teamwork"], primary: "business"
"""
                )
                logger.info("🤖 PydanticAI Agent initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize PydanticAI Agent: {e}")
                self.keyword_agent = None
        else:
            self.keyword_agent = None

    async def _ai_extract_keywords(self, segment_text: str) -> List[str]:
        """
        Dùng PydanticAI để trích xuất từ khóa tìm kiếm thông minh từ segment text.
        Trả về list keywords theo độ ưu tiên cao → thấp.
        """
        # Kiểm tra setting có enable AI keyword extraction không
        if not settings.ai_keyword_extraction_enabled or not self.keyword_agent:
            # Fallback: trích xuất từ khóa đơn giản
            return [segment_text.strip() or "nature"]
        
        try:
            # Sử dụng PydanticAI Agent để extract keywords với structured output
            result = await self.keyword_agent.run(
                user_prompt=f"Extract image search keywords for: {segment_text}",
                message_history=[]
            )
            
            # Get structured result
            keyword_result: KeywordExtractionResult = result.data
            
            # Giới hạn số keywords theo setting
            final_keywords = keyword_result.keywords[:settings.ai_max_keywords_per_prompt]
            
            logger.info(f"🤖 PydanticAI extracted keywords: {final_keywords} (primary: {keyword_result.primary_keyword}) from: '{segment_text}'")
            
            return final_keywords
            
        except Exception as e:
            logger.warning(f"PydanticAI keyword extraction failed: {e}")
            # Fallback về trích xuất đơn giản
            return [segment_text.strip() or "nature"]

    async def _ai_search_image(self, prompt: str, min_width: Optional[int] = None, min_height: Optional[int] = None) -> Optional[str]:
        """
        AI-enhanced image search: dùng PydanticAI trích xuất keywords, thử nhiều keywords với Pixabay.
        """
        pixabay_key = settings.pixabay_api_key
        min_width = min_width or settings.video_min_image_width
        min_height = min_height or settings.video_min_image_height
        
        # AI trích xuất keywords thông minh với PydanticAI
        keywords_list = await self._ai_extract_keywords(prompt)
        
        # Thử từng keyword cho đến khi tìm được ảnh phù hợp
        for keywords in keywords_list:
            url = search_pixabay_image(keywords, pixabay_key, min_width, min_height)
            if url:
                logger.info(f"✅ Found image with keywords: '{keywords}' for prompt: '{prompt}'")
                return url
        
        # Nếu không tìm được gì, thử keyword fallback cuối cùng
        fallback_url = search_pixabay_image("abstract background", pixabay_key, min_width, min_height)
        if fallback_url:
            logger.warning(f"⚠️ Using fallback image for prompt: '{prompt}'")
        
        return fallback_url

    async def process(self, input_data: Any, **kwargs) -> Any:
        """
        input_data: download_results (tuple: (segment_results, background_music_result))
        context: truyền qua kwargs['context'], lấy segments từ context
        """
        metric = self._start_processing(ProcessingStage.DOWNLOAD)
        try:
            download_results = input_data
            context = kwargs.get('context')
            if not context:
                raise ProcessingError("Context is required for ImageAutoProcessor")
            segments = context.get("segments")
            if not segments:
                raise ProcessingError("Segments not found in context")
            if not download_results or len(download_results) != 2:
                raise ProcessingError("Invalid download results format")
            segment_results, background_music_result = download_results
            if len(segments) != len(segment_results):
                raise ProcessingError(
                    f"Segment count mismatch: {len(segments)} vs {len(segment_results)}"
                )
            min_width = settings.video_min_image_width
            min_height = settings.video_min_image_height
            pixabay_key = settings.pixabay_api_key
            temp_dir = context.get('temp_dir') if isinstance(context, dict) else context.temp_dir
            if not temp_dir:
                raise ProcessingError("temp_dir is required in context")
            new_segment_results = []
            for segment, asset_dict in zip(segments, segment_results):
                image_obj = asset_dict.get("image", {})
                image_path = image_obj.get("local_path")
                prompt = segment.get("text") or segment.get("title") or ""
                merged_asset = asset_dict.copy()
                valid = False
                if image_path:
                    valid = is_image_size_valid(image_path, min_width, min_height)
                if not valid:
                    # Tìm ảnh mới từ self._ai_search_image
                    new_url = await self._ai_search_image(prompt, min_width, min_height)
                    if not new_url:
                        raise ProcessingError(f"Không tìm được ảnh phù hợp cho segment: {prompt}")
                    # Download ảnh mới về temp_dir
                    ext = os.path.splitext(new_url)[1] or ".jpg"
                    new_filename = f"auto_image_{uuid4().hex}{ext}"
                    new_path = os.path.join(temp_dir, new_filename)
                    try:
                        with requests.get(new_url, stream=True, timeout=10) as r:
                            r.raise_for_status()
                            with open(new_path, 'wb') as f:
                                shutil.copyfileobj(r.raw, f)
                        merged_asset["image"] = {
                            "url": new_url,
                            "local_path": new_path
                        }
                    except Exception as e:
                        raise ProcessingError(f"Download replacement image failed: {e}")
                new_segment_results.append(merged_asset)
            self._end_processing(metric, success=True, items_processed=len(new_segment_results))
            return (new_segment_results, background_music_result)
        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise ProcessingError(f"Image validation/search failed: {e}") from e
