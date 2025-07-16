import requests
from typing import List, Dict, Optional, Any
import logging
import time
from datetime import datetime
from pathlib import Path

class TranscriptProcessorError(Exception):
    """Base error for transcript processor"""
    pass

class AudioProcessingError(TranscriptProcessorError):
    """Error when processing audio file"""
    pass

class AlignmentError(TranscriptProcessorError):
    """Error during alignment process"""
    pass

class ValidationError(TranscriptProcessorError):
    """Error during validation"""
    pass

# Standard library imports
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
from pydantic import BaseModel, field_validator

# Local application imports
from app.config import settings
from app.core.exceptions import ProcessingError
from app.services.processors.base_processor import BaseProcessor, ProcessingStage
from utils.gentle_utils import align_audio_with_transcript

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
    """
    Xử lý transcript và tạo text overlay với timing chính xác.
    
    Sử dụng Gentle forced aligner để đồng bộ hóa văn bản với âm thanh,
    tạo ra các đoạn văn bản hiển thị đúng thời điểm trong video.
    """
    
    # Định dạng file audio được hỗ trợ
    SUPPORTED_AUDIO_FORMATS = ('.wav', '.mp3', '.m4a')
    
    # Kích thước file tối đa (100MB)
    MAX_AUDIO_SIZE_MB = 100
    
    def __init__(self, *args, **kwargs):
        """Khởi tạo TranscriptProcessor với cấu hình mặc định."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.DEBUG)

    def validate_audio_file(self, audio_path: str) -> None:
        """
        Kiểm tra và xác thực file audio trước khi xử lý.
        
        Args:
            audio_path: Đường dẫn đến file audio cần kiểm tra
            
        Raises:
            ValidationError: Nếu file không đáp ứng các yêu cầu
            
        Note:
            - Kiểm tra sự tồn tại của file
            - Kiểm tra kích thước file
            - Kiểm tra định dạng file
        """
        try:
            if not audio_path:
                raise ValidationError("Đường dẫn audio không được để trống")
                
            path = Path(audio_path)
            
            # Kiểm tra sự tồn tại
            if not path.exists():
                raise ValidationError(f"Không tìm thấy file audio: {audio_path}")
                
            if not path.is_file():
                raise ValidationError(f"Đường dẫn không phải là file: {audio_path}")
            
            # Kiểm tra kích thước file
            file_size_mb = path.stat().st_size / (1024 * 1024)  # Chuyển sang MB
            if file_size_mb > self.MAX_AUDIO_SIZE_MB:
                raise ValidationError(
                    f"Kích thước file quá lớn: {file_size_mb:.2f}MB "
                    f"(tối đa {self.MAX_AUDIO_SIZE_MB}MB)"
                )
            
            # Kiểm tra định dạng file
            if path.suffix.lower() not in self.SUPPORTED_AUDIO_FORMATS:
                raise ValidationError(
                    f"Định dạng file không được hỗ trợ: {path.suffix}. "
                    f"Định dạng được hỗ trợ: {', '.join(self.SUPPORTED_AUDIO_FORMATS)}"
                )
                
        except ValidationError as ve:
            self.logger.error("Lỗi xác thực audio: %s", str(ve))
            raise
        except Exception as e:
            self.logger.error("Lỗi không xác định khi xác thực audio: %s", str(e), exc_info=True)
            raise ValidationError(f"Lỗi khi xác thực file audio: {str(e)}") from e
    
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
        """Chuẩn hóa văn bản để phù hợp với tokenization của Gentle"""
        import re
        # Tách từ và loại bỏ dấu câu
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
            self.logger.error(
                "Lỗi khi tìm word groups: %s.", 
                str(e), 
                exc_info=True
            )
    
    def _find_word_groups_fallback(self, word_items: List[Dict], transcript_lines: List[str]) -> List[Dict]:
        """
        Tạo word groups từ word_items với các kiểm tra robust hơn.
        
        Args:
            word_items: Danh sách các từ từ Gentle aligner, mỗi từ là một dict chứa:
                - word: Nội dung từ
                - start: Thời gian bắt đầu (giây)
                - end: Thời gian kết thúc (giây)
                - case: Trạng thái align ('success' nếu thành công)
            transcript_lines: Danh sách các dòng transcript cần tìm timing
                
        Returns:
            List[Dict]: Danh sách các text_over item, mỗi item chứa:
                - text: Nội dung hiển thị
                - start_time: Thời gian bắt đầu (giây)
                - duration: Thời lượng hiển thị (giây)
                
        Note:
            - Phương thức này cố gắng tìm kiếm mềm dẻo các từ trong transcript
            - Tự động xử lý các trường hợp overlap giữa các từ
            - Có cơ chế dự phòng khi không tìm thấy từ chính xác
        """
        if not word_items or not transcript_lines:
            self.logger.warning("Dữ liệu đầu vào rỗng")
            return []
            
        text_over = []
        word_index = 0
        
        # Lọc chỉ lấy từ được align thành công
        success_words = [w for w in word_items if w.get("case") == "success"]
        
        if not success_words:
            self.logger.warning("Không có từ nào được align thành công")
            return []
            
        self.logger.debug("Bắt đầu tìm word groups cho %d dòng transcript", len(transcript_lines))
        
        for line_idx, line in enumerate(transcript_lines, 1):
            if not line.strip():
                self.logger.debug("Bỏ qua dòng trống tại vị trí %d", line_idx)
                continue
                
            line_normalized = self._normalize_text(line)
            if not line_normalized:
                self.logger.warning("Không thể chuẩn hóa dòng: %s", line)
                continue
                
            self.logger.debug("Xử lý dòng %d: %s", line_idx, line)
            
            # Tìm kiếm chính xác trước
            group = self._find_exact_match(
                line_normalized, 
                success_words, 
                word_index
            )
            
            if group and len(group) == len(line_normalized):
                # Tìm thấy khớp chính xác
                self.logger.debug("Tìm thấy khớp chính xác cho dòng %d", line_idx)
                text_over_item = self._create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    word_index = success_words.index(group[-1]) + 1
                continue
                
            # Nếu không tìm thấy khớp chính xác, thử tìm kiếm mềm dẻo
            self.logger.debug("Không tìm thấy khớp chính xác, thử tìm kiếm mềm dẻo cho dòng %d", line_idx)
            
            # Tìm kiếm không phân biệt thứ tự
            group = self._find_flexible_match(
                line_normalized,
                success_words[word_index:],
                max_lookahead=20  # Giới hạn số từ xem xét để tăng hiệu suất
            )
            
            if group and len(group) == len(line_normalized):
                # Tìm thấy khớp mềm dẻo
                text_over_item = self._create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    word_index = success_words.index(group[-1]) + 1
            else:
                self.logger.warning(
                    "Không thể tìm thấy đủ từ cho dòng %d: %s (chỉ tìm thấy %d/%d từ)",
                    line_idx, line, len(group) if group else 0, len(line_normalized)
                )
                
                # Thêm dòng này với timing 0 nếu không tìm thấy từ nào
                if not group and text_over:
                    last_end = text_over[-1]['start_time'] + text_over[-1]['duration']
                    text_over.append({
                        'text': line,
                        'start_time': last_end,
                        'duration': 1.0  # Mặc định 1 giây
                    })
        
        self.logger.info("Đã tạo được %d text_over items từ %d dòng", len(text_over), len(transcript_lines))
        return text_over
        
    def _find_exact_match(self, words: List[str], word_items: List[Dict], start_idx: int) -> List[Dict]:
        """Tìm kiếm chính xác dãy từ trong word_items."""
        if not words or start_idx >= len(word_items):
            return []
            
        # Tìm vị trí bắt đầu khả thi
        for i in range(start_idx, len(word_items) - len(words) + 1):
            match = True
            for j, word in enumerate(words):
                if word_items[i + j]['word'].lower() != word:
                    match = False
                    break
                    
            if match:
                return word_items[i:i+len(words)]
                
        return []
        
    def _find_flexible_match(self, words: List[str], word_items: List[Dict], max_lookahead: int = 20) -> List[Dict]:
        """Tìm kiếm mềm dẻo các từ không theo thứ tự."""
        if not words or not word_items:
            return []
            
        # Giới hạn số lượng từ xem xét để tăng hiệu suất
        search_items = word_items[:min(len(word_items), max_lookahead)]
        
        # Tạo dict để tra cứu nhanh
        word_to_items = {}
        for item in search_items:
            word = item['word'].lower()
            if word not in word_to_items:
                word_to_items[word] = []
            word_to_items[word].append(item)
        
        # Tìm các từ khớp
        found_items = []
        remaining_words = set(words)
        
        for word in words:
            if word in word_to_items and word_to_items[word]:
                found_items.append(word_to_items[word].pop(0))
                remaining_words.discard(word)
                
        # Nếu tìm thấy ít nhất một nửa số từ, sắp xếp lại theo thời gian
        if len(found_items) >= max(1, len(words) // 2):
            found_items.sort(key=lambda x: x['start'])
            return found_items
            
        return []
        
    def _create_text_over_item(self, text: str, word_items: List[Dict]) -> Optional[Dict]:
        """Tạo text_over item từ danh sách từ và xử lý overlap."""
        if not word_items:
            return None
            
        # Sắp xếp lại theo thời gian để chắc chắn
        word_items = sorted(word_items, key=lambda x: x['start'])
        
        # Kiểm tra và sửa overlap
        for i in range(1, len(word_items)):
            if word_items[i-1]['end'] > word_items[i]['start']:
                # Điều chỉnh thời gian kết thúc của từ trước
                word_items[i-1]['end'] = word_items[i]['start']
                self.logger.debug(
                    "Đã điều chỉnh overlap giữa '%s' (%.2fs-%.2fs) và '%s' (%.2fs-%.2fs)",
                    word_items[i-1]['word'], word_items[i-1]['start'], word_items[i-1]['end'],
                    word_items[i]['word'], word_items[i]['start'], word_items[i].get('end', 0)
                )
        
        # Tính toán thời gian bắt đầu và kết thúc
        start_time = word_items[0]['start']
        end_time = word_items[-1]['end']
        
        # Đảm bảo thời lượng tối thiểu là 0.1 giây
        duration = max(0.1, end_time - start_time)
        
        return {
            'text': text,
            'start_time': start_time,
            'duration': duration
        }

    async def _find_word_groups(self, word_items: List[Dict], transcript_lines: List[str]) -> List[Dict]:
        """Tìm groups từ cho từng câu transcript - sử dụng fallback method"""
        self.logger.info("Bắt đầu tìm word groups cho %d segments", len(transcript_lines))
        start_time = time.time()
        
        # Kiểm tra xem có nên dùng LLM không
        try:
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
                "Lỗi khi tìm word groups: %s.", 
                str(e), 
                exc_info=True
            )
    
    async def process(self, input_data: List[Dict], **kwargs) -> List[Dict]:
        """
        Xử lý transcript và tạo text overlay với timing chính xác.
        
        Args:
            input_data: Danh sách các segment cần xử lý, mỗi segment phải chứa:
                - id: Định danh duy nhất của segment
                - voice_over: Chứa thông tin audio và transcript:
                    - local_path: Đường dẫn đến file audio
                    - content: Nội dung transcript
                    - transcript_lines: (tùy chọn) Các dòng transcript đã được phân đoạn
            **kwargs: Các tham số bổ sung:
                - context: Chứa thông tin ngữ cảnh bổ sung
                - temp_dir: Thư mục tạm để lưu file transcript (nếu không dùng thư mục tạm hệ thống)
                
        Returns:
            List[Dict]: Danh sách các segment đã được xử lý với trường 'text_over' bổ sung
            
        Raises:
            ProcessingError: Nếu có lỗi nghiêm trọng trong quá trình xử lý
            
        Note:
            - Mỗi segment được xử lý độc lập, lỗi ở một segment không ảnh hưởng đến các segment khác
            - File tạm sẽ được tự động dọn dẹp sau khi xử lý xong
        """
        if not input_data:
            self.logger.warning("Không có dữ liệu đầu vào để xử lý")
            return []
            
        self.logger.info("Bắt đầu xử lý %d segment(s)", len(input_data))
        start_time = time.time()
        metric = self._start_processing(ProcessingStage.TEXT_OVERLAY)
        processed_count = 0
        
        try:
            context = kwargs.get("context", {})
            temp_dir = context.get("temp_dir")
            
            for idx, segment in enumerate(input_data, 1):
                segment_id = segment.get('id', f'unknown_{idx}')
                segment_start_time = time.time()
                
                self.logger.info("[%d/%d] Đang xử lý segment %s", 
                              idx, len(input_data), segment_id)
                
                try:
                    # Kiểm tra voice_over
                    voice_over = segment.get('voice_over')
                    if not voice_over:
                        self.logger.warning("Segment %s: Bỏ qua do thiếu voice_over", segment_id)
                        continue
                        
                    # Kiểm tra và xác thực file audio
                    audio_path = voice_over.get('local_path')
                    try:
                        self.validate_audio_file(audio_path)
                        self.logger.debug("Segment %s: File audio hợp lệ", segment_id)
                    except ValidationError as ve:
                        self.logger.warning("Segment %s: Lỗi xác thực audio - %s", segment_id, str(ve))
                        continue
                        
                    # Kiểm tra nội dung transcript
                    transcript_content = voice_over.get('content', '').strip()
                    if not transcript_content:
                        self.logger.warning("Segment %s: Bỏ qua do thiếu nội dung transcript", segment_id)
                        continue
                    # Lưu nội dung transcript vào file
                    try:
                        output_file = os.path.join(temp_dir, f"{segment_id}_transcript.json")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(transcript_content, f, ensure_ascii=False, indent=2)
                        self.logger.debug("Đã lưu transcript vào file: %s", output_file)
                    except Exception as e:
                        self.logger.warning("Không thể lưu transcript: %s", str(e))

                    # Log thông tin cơ bản
                    audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                    self.logger.debug(
                        "Segment %s: Audio=%s (%.2f MB), Transcript length=%d ký tự", 
                        segment_id, 
                        os.path.basename(audio_path),
                        audio_size_mb,
                        len(transcript_content)
                    )
                    
                    # Xử lý transcript
                    transcript_lines = voice_over.get('transcript_lines')
                    if not transcript_lines:
                        self.logger.debug("Segment %s: Đang phân đoạn transcript...", segment_id)
                        try:
                            transcript_lines = await self._split_transcript_by_llm(transcript_content)
                            self.logger.debug(
                                "Segment %s: Đã phân đoạn thành %d dòng", 
                                segment_id, len(transcript_lines)
                            )
                            # Lưu transcript_lines vào file JSON
                            try:
                                transcript_lines_file = os.path.join(temp_dir, f"{segment_id}_transcript_lines.json")
                                with open(transcript_lines_file, 'w', encoding='utf-8') as f:
                                    json.dump(transcript_lines, f, ensure_ascii=False, indent=2)
                                self.logger.debug("Đã lưu transcript_lines vào file: %s", transcript_lines_file)
                            except Exception as e:
                                self.logger.warning("Không thể lưu transcript_lines: %s", str(e))
                                                
                        except Exception as e:
                            self.logger.error(
                                "Segment %s: Lỗi khi phân đoạn transcript - %s", 
                                segment_id, str(e), exc_info=True
                            )
                            continue
                    
                    try:
                        with tempfile.NamedTemporaryFile(
                            mode='w', 
                            suffix='.txt', 
                            delete=False,
                            dir=temp_dir,
                            encoding='utf-8'
                        ) as f:
                            f.write(transcript_content)
                            transcript_path = f.name
                            
                        self.logger.debug("Segment %s: Đã tạo file transcript tạm: %s", 
                                       segment_id, transcript_path)
                        
                        # Xử lý audio và transcript với Gentle
                        gentle_start = time.time()
                        try:
                            result, verification = await align_audio_with_transcript(
                                audio_path=audio_path,
                                transcript_path=transcript_path,
                                gentle_url=settings.gentle_url if hasattr(settings, 'gentle_url') 
                                         else "http://localhost:8765/transcriptions",
                                timeout=getattr(settings, 'gentle_timeout', 300),
                                verify_quality=True,
                                min_success_ratio=0.8,
                                logger=self.logger
                            )
                            
                            gentle_time = time.time() - gentle_start
                            success_ratio = verification.get("success_ratio", 0) * 100
                            
                            self.logger.info(
                                "Segment %s: Xử lý Gentle hoàn thành sau %.2f giây (tỷ lệ thành công: %.1f%%)",
                                segment_id, gentle_time, success_ratio
                            )
                            
                            # Thống kê kết quả align
                            words = result.get("words", [])
                            success_words = [w for w in words if w.get("case") == "success"]
                            total_words = len(words)
                            
                            self.logger.debug(
                                "Segment %s: Kết quả align - %d/%d từ được nhận diện (%.1f%%)",
                                segment_id, len(success_words), total_words,
                                (len(success_words) / total_words * 100) if total_words > 0 else 0
                            )
                            
                            # Tạo text_over từ kết quả align
                            try:
                                 # Tạo kết quả text_over
                                text_over_result = self._find_word_groups_fallback(
                                    words, 
                                    transcript_lines
                                )
                                segment["text_over"] = text_over_result
                                
                                # Lưu kết quả vào file JSON trong thư mục tạm
                                try:
                                    # Tạo tên file đầu ra dựa trên segment_id
                                    output_file = os.path.join(temp_dir, f"{segment_id}_text_over.json")
                                    
                                    # Ghi dữ liệu vào file
                                    with open(output_file, 'w', encoding='utf-8') as f:
                                        json.dump(text_over_result, f, ensure_ascii=False, indent=2)
                                        
                                    self.logger.debug(
                                        "Đã lưu text_over vào file: %s", 
                                        output_file
                                    )
                                except Exception as save_error:
                                    self.logger.warning(
                                        "Không thể lưu text_over: %s", 
                                        str(save_error)
                                    )
                                
                                self.logger.info(
                                    "Segment %s: Đã tạo %d text_over items",
                                    segment_id, len(text_over_result)
                                )
                                processed_count += 1
                                
                            except Exception as e:
                                self.logger.error(
                                    "Segment %s: Lỗi khi tạo text_over - %s", 
                                    segment_id, str(e), exc_info=True
                                )
                                
                        except Exception as e:
                            self.logger.error(
                                "Segment %s: Lỗi khi xử lý với Gentle - %s", 
                                segment_id, str(e), exc_info=True
                            )
                            
                    except Exception as e:
                        self.logger.error(
                            "Segment %s: Lỗi khi tạo file tạm - %s", 
                            segment_id, str(e), exc_info=True
                        )
                    
                except Exception as e:
                    self.logger.error(
                        "Lỗi không xác định khi xử lý segment %s: %s", 
                        segment_id, str(e), exc_info=True
                    )
                
                # Log thời gian xử lý cho segment hiện tại
                segment_time = time.time() - segment_start_time
                self.logger.debug(
                    "Hoàn thành segment %s sau %.2f giây", 
                    segment_id, segment_time
                )
            
            # Kết thúc quá trình xử lý
            total_time = time.time() - start_time
            avg_time = total_time / len(input_data) if input_data else 0
            
            self.logger.info(
                "Đã xử lý xong %d/%d segment(s) trong %.2f giây (trung bình %.2f giây/segment)",
                processed_count, len(input_data), total_time, avg_time
            )
            
            self._end_processing(
                metric, 
                success=processed_count > 0,
                items_processed=processed_count
            )
            
            return input_data
            
        except Exception as e:
            error_msg = f"Lỗi nghiêm trọng khi xử lý: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(
                metric, 
                success=False, 
                error_message=error_msg,
                items_processed=processed_count
            )
            raise ProcessingError(error_msg) from e
