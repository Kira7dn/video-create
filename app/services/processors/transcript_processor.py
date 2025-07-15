import requests
from typing import List, Dict, Optional, Any
import logging
import time
from datetime import datetime

from app.services.processors.base_processor import BaseProcessor, ProcessingStage
from app.core.exceptions import ProcessingError
from app.config.settings import settings
import tempfile
import json
import re
import os
from pydantic import BaseModel, field_validator

# Khởi tạo logger
logger = logging.getLogger(__name__)

class TranscriptSegments(BaseModel):
    """Pydantic model cho validated transcript segments"""
    segments: List[str]
    
    @field_validator('segments')
    @classmethod
    def validate_segments(cls, v):
        """Validate và auto-fix segments theo YouTube constraints"""
        validated = []
        for segment in v:
            # Kiểm tra constraints: 2-7 từ, max 35 chars
            words = segment.split()
            char_count = len(segment)
            
            if 2 <= len(words) <= 7 and char_count <= 35:
                validated.append(segment)
            else:
                # Auto-fix: chia segment quá dài
                while words:
                    chunk = []
                    chunk_chars = 0
                    
                    while words and len(chunk) < 7:
                        next_word = words[0]
                        new_chars = chunk_chars + len(next_word) + (1 if chunk else 0)
                        
                        if new_chars <= 35:
                            chunk.append(words.pop(0))
                            chunk_chars = new_chars
                        else:
                            break
                    
                    # Đảm bảo chunk có ít nhất 2 từ để tự nhiên
                    if len(chunk) >= 2:
                        validated.append(' '.join(chunk))
                    elif len(chunk) == 1 and not words:
                        # Từ cuối cùng đơn lẻ
                        validated.append(chunk[0])
                    elif len(chunk) == 1 and words:
                        # Gộp với từ tiếp theo nếu có thể
                        if len(chunk[0]) + len(words[0]) + 1 <= 35:
                            chunk.append(words.pop(0))
                            validated.append(' '.join(chunk))
                        else:
                            validated.append(chunk[0])
        
        return validated

class WordGroupMapping(BaseModel):
    """Model cho mapping segments với word ranges"""
    mappings: List[Dict[str, int]]  # [{"segment_index": 0, "start_word": 0, "end_word": 2}, ...]

class TranscriptProcessor(BaseProcessor):
    """Xử lý transcript và tạo text overlay với timing chính xác"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def _split_transcript_by_llm(self, content: str) -> List[str]:
        """
        Sử dụng OpenAI qua PydanticAI với structured output để phân đoạn transcript.
        Args:
            content: str - transcript gốc
        Returns:
            List[str] - danh sách câu đã phân đoạn và validated
        """
        self.logger.info("Bắt đầu phân đoạn transcript bằng LLM")
        start_time = time.time()
        
        # Tạo prompt cho LLM
        prompt = f"""
        Phân đoạn transcript sau thành các câu ngắn tự nhiên (2-7 từ, tối đa 35 ký tự):
        
        {content}
        
        Yêu cầu:
        - Mỗi câu phải là một đơn vị ngữ nghĩa hoàn chỉnh
        - Giữ nguyên dấu câu
        - Không được cắt ngang từ
        - Mỗi câu tối đa 35 ký tự
        - Mỗi câu nên có từ 2-7 từ
        - Trả về dạng JSON với key 'segments' là list các câu
        """
        
        try:
            from pydantic_ai import Agent
            
            self.logger.debug("Khởi tạo Agent với model: %s", settings.ai_pydantic_model)
            agent = Agent(
                model=settings.ai_pydantic_model,
                output_type=TranscriptSegments,
                system_prompt="""Bạn là một chuyên gia xử lý ngôn ngữ tự nhiên.
                Nhiệm vụ của bạn là phân đoạn transcript thành các câu ngắn tự nhiên.
                Mỗi câu phải là một đơn vị ngữ nghĩa hoàn chỉnh, dễ đọc và tự nhiên khi đọc to."""
            )
            
            prompt = f"""
Split this transcript into natural speech segments that feel organic and readable:

"{content}"

Natural Speech Requirements:
- Each segment: 3-7 words (natural phrase boundaries)
- Maximum 35 characters per segment
- Break at natural breath pauses and thought boundaries
- Keep compound words/phrases together
- Maintain natural speech rhythm
- Each segment should feel complete
- Perfect for natural reading pace (2-4 seconds)

Example of natural segmentation:
{{"segments": ["Hello everyone", "welcome back to", "our channel", "today we're going to", "explore machine learning", "and its applications"]}}

Focus on natural speech patterns, not just word counts!
Return as JSON object with segments array.
"""
            
            # Sử dụng async run với structured output
            result = await agent.run(user_prompt=prompt)
            
            # result.data là TranscriptSegments object với auto-validation
            transcript_segments = result.data
            
            # Pydantic đã validate và auto-fix, trả về segments
            return transcript_segments.segments
            
        except Exception as e:
            # Fallback về regex split nếu LLM fail
            lines = re.split(r'(?<=[.!?])\s+|(?<=,)\s+|\s+(?=and|or|but|so|because|when|if|while|although)\s+', content.strip())
            validated_lines = []
            for line in lines:
                words = line.split()
                while words:
                    chunk = []
                    char_count = 0
                    while words and len(chunk) < 7:
                        if char_count + len(words[0]) + 1 <= 35:
                            chunk.append(words.pop(0))
                            char_count += len(chunk[-1]) + (1 if len(chunk) > 1 else 0)
                        else:
                            break
                    
                    # Đảm bảo tính tự nhiên
                    if len(chunk) >= 2:
                        validated_lines.append(' '.join(chunk))
                    elif len(chunk) == 1 and not words:
                        validated_lines.append(chunk[0])
                    elif len(chunk) == 1 and words:
                        if char_count + len(words[0]) + 1 <= 35:
                            chunk.append(words.pop(0))
                            validated_lines.append(' '.join(chunk))
                        else:
                            validated_lines.append(chunk[0])
            return validated_lines
    """
    Processor dùng Gentle để align transcript với audio, xuất text_over cho pipeline.
    Args:
        input_data: List[Dict] processed_segments (mỗi segment có voice_over)
    Returns:
        List[Dict]: Danh sách text_over với text, start_time, duration.
    """
    
    def _normalize_text(self, text: str) -> List[str]:
        """Normalize text để match với Gentle tokenization"""
        # Remove punctuation và split, tương tự như Gentle
        words = re.findall(r'\b\w+\b', text.lower())
        return words
    
    async def _find_word_groups_with_llm(self, word_items: List[Dict], transcript_segments: List[str]) -> List[Dict]:
        """
        Sử dụng LLM để match transcript segments với Gentle word items một cách thông minh.
        Args:
            word_items: List từ Gentle với timing info
            transcript_segments: List segments đã được LLM chia nhỏ
        Returns:
            List[Dict]: text_over với timing chính xác
        """
        try:
            from app.config.settings import settings
            from pydantic_ai.agent import Agent
            
            # Tạo context cho LLM
            gentle_words = [w['word'] for w in word_items]
            
            agent = Agent(
                model=settings.ai_pydantic_model,
                output_type=WordGroupMapping,
                system_prompt="""You are an expert at aligning transcript segments with audio transcription words.
Your task is to map each transcript segment to the corresponding word range in the Gentle transcription.

Rules:
1. Each segment maps to a contiguous range of words
2. Words should not overlap between segments
3. Handle mismatches intelligently (missing words, extra words, variations)
4. Preserve semantic meaning when possible
5. Return mappings as: [{"segment_index": 0, "start_word": 0, "end_word": 2}, ...]
6. segment_index is 0-based, start_word and end_word are inclusive indices"""
            )
            
            prompt = f"""
Map these transcript segments to word ranges in the Gentle transcription:

Transcript Segments (to be mapped):
{[f"{i}: {seg}" for i, seg in enumerate(transcript_segments)]}

Gentle Words (with indices):
{[f"{i}: {word}" for i, word in enumerate(gentle_words)]}

Create precise mappings considering:
- Semantic similarity between segments and word sequences
- Natural word boundaries
- Handle variations in transcription (missing/extra words)
- Maintain chronological order

Return mappings array where each object maps segment_index to start_word and end_word indices.
"""
            
            result = await agent.run(user_prompt=prompt)
            mappings = result.data.mappings
            
            # Áp dụng mappings để tạo text_over
            text_over = []
            for mapping in mappings:
                seg_idx = mapping.get("segment_index", 0)
                start_word = mapping.get("start_word", 0)
                end_word = mapping.get("end_word", 0)
                
                if (0 <= seg_idx < len(transcript_segments) and 
                    0 <= start_word <= end_word < len(word_items)):
                    
                    segment_text = transcript_segments[seg_idx]
                    start_time = word_items[start_word]['start']
                    end_time = word_items[end_word]['end']
                    
                    text_over.append({
                        "text": segment_text,
                        "start_time": start_time,
                        "duration": end_time - start_time
                    })
            
            return text_over
            
        except Exception as e:
            # Fallback về method cũ nếu LLM fail
            return self._find_word_groups_fallback(word_items, transcript_segments)
    
    def _find_word_groups_fallback(self, word_items: List[Dict], transcript_lines: List[str]) -> List[Dict]:
        """Fallback method cho word grouping khi LLM fail"""
        text_over = []
        word_index = 0
        
        for line in transcript_lines:
            line_normalized = self._normalize_text(line)
            
            # Tìm group từ matching với câu hiện tại
            group = []
            start_idx = word_index
            
            for i, expected_word in enumerate(line_normalized):
                if word_index + i < len(word_items):
                    actual_word = word_items[word_index + i]['word'].lower()
                    # Remove punctuation từ actual word
                    actual_normalized = re.sub(r'[^\w]', '', actual_word)
                    
                    if expected_word == actual_normalized:
                        group.append(word_items[word_index + i])
                    else:
                        # Mismatch - fallback to simple grouping
                        break
            
            # Nếu match thành công, sử dụng group
            if len(group) == len(line_normalized):
                word_index += len(group)
            else:
                # Fallback: dùng số từ đơn giản
                num_words = len(line.strip().split())
                group = word_items[word_index:word_index + num_words]
                word_index += num_words
            
            if group:
                start = group[0]['start']
                end = group[-1]['end']
                text_over.append({
                    "text": line,
                    "start_time": start,
                    "duration": end - start
                })
        
        return text_over
    
    async def _find_word_groups(self, word_items: List[Dict], transcript_lines: List[str]) -> List[Dict]:
        """Tìm groups từ cho từng câu transcript - sử dụng LLM hoặc fallback"""
        self.logger.info("Bắt đầu tìm word groups cho %d segments", len(transcript_lines))
        start_time = time.time()
        
        # Kiểm tra xem có nên dùng LLM không
        try:
            from app.config.settings import settings
            if hasattr(settings, 'ai_keyword_extraction_enabled') and settings.ai_keyword_extraction_enabled:
                self.logger.debug("Sử dụng LLM để tìm word groups")
                result = await self._find_word_groups_with_llm(word_items, transcript_lines)
                duration = time.time() - start_time
                self.logger.info(
                    "Đã tìm thấy %d word groups trong %.2f giây", 
                    len(result), duration
                )
                return result
            else:
                self.logger.debug("Sử dụng fallback method để tìm word groups")
                result = self._find_word_groups_fallback(word_items, transcript_lines)
                duration = time.time() - start_time
                self.logger.info(
                    "Đã tìm thấy %d word groups (fallback) trong %.2f giây", 
                    len(result), duration
                )
                return result
                
        except Exception as e:
            self.logger.error(
                "Lỗi khi tìm word groups: %s. Sử dụng fallback method.", 
                str(e), 
                exc_info=True
            )
            result = self._find_word_groups_fallback(word_items, transcript_lines)
            self.logger.warning("Đã sử dụng fallback method, tìm thấy %d word groups", len(result))
            return result
    

    async def process(self, input_data: List[Dict], **kwargs) -> List[Dict]:
        """
        Xử lý transcript và tạo text overlay với timing chính xác.
        
        Args:
            input_data: Danh sách các segment cần xử lý
            **kwargs: Các tham số bổ sung, có thể chứa context
            
        Returns:
            List[Dict]: Danh sách các segment đã được xử lý với text_over
            
        Raises:
            ProcessingError: Nếu có lỗi trong quá trình xử lý
        """
        self.logger.info("Bắt đầu xử lý %d segments", len(input_data))
        start_time = time.time()
        metric = self._start_processing(ProcessingStage.TEXT_OVERLAY)
        
        try:
            context = kwargs.get("context", {})
            self.logger.debug("Context: %s", context)
            
            for idx, segment in enumerate(input_data, 1):
                segment_id = segment.get('id', f'unknown_{idx}')
                self.logger.info("Xử lý segment %s (%d/%d)", segment_id, idx, len(input_data))
                
                voice_over = segment.get('voice_over')
                if not voice_over:
                    self.logger.warning("Segment %s không có voice_over, bỏ qua", segment_id)
                    continue
                    
                audio_path = voice_over.get('local_path')
                if not audio_path or not os.path.exists(audio_path):
                    self.logger.error("Không tìm thấy file audio: %s", audio_path)
                    continue
                    
                transcript_content = voice_over.get('content', '')
                if not transcript_content:
                    self.logger.warning("Segment %s không có nội dung transcript", segment_id)
                    continue
                
                # Log thông tin cơ bản
                self.logger.debug("Segment %s - Audio: %s (%.2f KB)", 
                               segment_id, 
                               os.path.basename(audio_path),
                               os.path.getsize(audio_path) / 1024)
                
                # Xử lý transcript
                transcript_lines = voice_over.get('transcript_lines')
                if not transcript_lines:
                    self.logger.debug("Phân đoạn transcript bằng LLM...")
                    transcript_lines = await self._split_transcript_by_llm(transcript_content)
                    self.logger.debug("Đã phân đoạn thành %d dòng", len(transcript_lines))
                
                # Tạo file tạm cho Gentle
                temp_dir = None
                if context:
                    temp_dir = context.get('temp_dir') if isinstance(context, dict) else getattr(context, 'temp_dir', None)
                
                transcript_path = None
                try:
                    if temp_dir:
                        os.makedirs(temp_dir, exist_ok=True)
                        transcript_path = os.path.join(temp_dir, f"transcript_{segment_id}.txt")
                        with open(transcript_path, "w", encoding="utf-8") as f:
                            f.write(transcript_content)
                        self.logger.debug("Đã lưu transcript tạm tại: %s", transcript_path)
                    else:
                        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
                            f.write(transcript_content)
                            transcript_path = f.name
                        self.logger.debug("Đã tạo file tạm: %s", transcript_path)
                    
                    # Gọi Gentle API
                    self.logger.info("Gọi Gentle API để align audio và transcript...")
                    gentle_start = time.time()
                    
                    with open(audio_path, "rb") as a_file, open(transcript_path, "rb") as t_file:
                        files = {"audio": a_file, "transcript": t_file}
                        response = requests.post(
                            "http://localhost:8765/transcriptions?async=false",
                            files=files,
                            timeout=settings.gentle_timeout
                        )
                        response.raise_for_status()
                    
                    gentle_time = time.time() - gentle_start
                    self.logger.info("Gentle hoàn thành trong %.2f giây", gentle_time)
                    
                    result = response.json()
                    word_items = [w for w in result["words"] if w.get("case") == "success"]
                    self.logger.debug("Đã nhận được %d từ được align thành công", len(word_items))
                    
                    # Tìm word groups
                    self.logger.debug("Bắt đầu tìm word groups...")
                    segment["text_over"] = await self._find_word_groups(word_items, transcript_lines)
                    self.logger.info("Đã tạo %d text_over items", len(segment.get("text_over", [])))
                    
                except Exception as e:
                    self.logger.error("Lỗi khi xử lý segment %s: %s", segment_id, str(e), exc_info=True)
                    raise
                    
                finally:
                    # Dọn dẹp file tạm
                    if transcript_path and os.path.exists(transcript_path):
                        try:
                            os.remove(transcript_path)
                            self.logger.debug("Đã xóa file tạm: %s", transcript_path)
                        except Exception as e:
                            self.logger.warning("Không thể xóa file tạm %s: %s", transcript_path, str(e))
            
            # Kết thúc xử lý
            total_time = time.time() - start_time
            self.logger.info("Hoàn thành xử lý %d segments trong %.2f giây", 
                           len(input_data), total_time)
            
            self._end_processing(metric, success=True, items_processed=len(input_data))
            return input_data
            
        except Exception as e:
            error_msg = f"Lỗi trong quá trình xử lý: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(metric, success=False, error_message=error_msg)
            raise ProcessingError(error_msg) from e
