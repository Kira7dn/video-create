"""
Module xử lý transcript và tạo text overlay với timing chính xác.

Module này cung cấp các chức năng để xử lý transcript từ âm thanh, đồng bộ hóa văn bản
với âm thanh sử dụng Gentle forced aligner, và tạo các đoạn văn bản hiển thị đúng thời điểm.
"""

# Standard library imports
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
import asyncio
from pydantic_ai import Agent

# Third-party imports
import requests
from pydantic import BaseModel, field_validator

# Local application imports
from app.config import settings
from app.core.exceptions import ProcessingError
from app.services.processors.base_processor import BaseProcessor, ProcessingStage
from utils.gentle_utils import align_audio_with_transcript, filter_successful_words


class TranscriptProcessorError(Exception):
    """Base error for transcript processor"""

    def __init__(self, message=None):
        self.message = message
        super().__init__(self.message)


class AudioProcessingError(TranscriptProcessorError):
    """Error when processing audio file"""

    def __init__(self, message=None, file_path=None):
        self.file_path = file_path
        super().__init__(message or f"Error processing audio file: {file_path}")


class AlignmentError(TranscriptProcessorError):
    """Error during alignment process"""

    def __init__(self, message=None, alignment_data=None):
        self.alignment_data = alignment_data
        super().__init__(message or "Error during alignment process")


class ValidationError(TranscriptProcessorError):
    """Error during validation"""

    def __init__(self, message=None, field=None, value=None):
        self.field = field
        self.value = value
        super().__init__(message or f"Validation error for field '{field}': {value}")


# Khởi tạo logger
logger = logging.getLogger(__name__)


class TranscriptSegments(BaseModel):
    """Pydantic model cho validated transcript segments"""

    segments: List[str]

    @field_validator("segments")
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
                        validated.append(" ".join(chunk))
                    elif len(chunk) == 1 and not words:
                        # Từ cuối cùng đơn lẻ
                        validated.append(chunk[0])
                    elif len(chunk) == 1 and words:
                        # Gộp với từ tiếp theo nếu có thể
                        if len(chunk[0]) + len(words[0]) + 1 <= 35:
                            chunk.append(words.pop(0))
                            validated.append(" ".join(chunk))
                        else:
                            validated.append(chunk[0])
        return validated


class WordGroupMapping(BaseModel):
    """Model cho mapping segments với word ranges"""

    mappings: List[
        Dict[str, int]
    ]  # [{"segment_index": 0, "start_word": 0, "end_word": 2}, ...]


class TranscriptProcessor(BaseProcessor):
    """
    Xử lý transcript và tạo text overlay với timing chính xác.

    Sử dụng Gentle forced aligner để đồng bộ hóa văn bản với âm thanh,
    tạo ra các đoạn văn bản hiển thị đúng thời điểm trong video.
    """

    # Định dạng file audio được hỗ trợ
    SUPPORTED_AUDIO_FORMATS = (".wav", ".mp3", ".m4a")

    # Kích thước file tối đa (100MB)
    MAX_AUDIO_SIZE_MB = 100

    def __init__(self, *args, **kwargs):
        """Khởi tạo TranscriptProcessor với cấu hình mặc định."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.DEBUG)

    async def _process_async(self, input_data: List[Dict], **kwargs) -> List[Dict]:
        """Async implementation of transcript processing.

        Args:
            input_data: List of segments to process, each containing:
                - id: Unique identifier for the segment
                - voice_over: Dict containing audio and transcript info:
                    - local_path: Path to the audio file
                    - content: Transcript content
                    - transcript_lines: (optional) Pre-segmented transcript lines
            **kwargs: Additional parameters:
                - context: Additional context information
                - temp_dir: Temporary directory for storing intermediate files

        Returns:
            List[Dict]: Processed segments with 'text_over' field added

        Raises:
            ProcessingError: If a critical error occurs during processing
        """
        # Delegate to the existing sync process method for now
        # This maintains compatibility while allowing for future async optimization
        return self.process(input_data, **kwargs)

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
            self.logger.error(
                "Lỗi không xác định khi xác thực audio: %s", str(e), exc_info=True
            )
            raise ValidationError(f"Lỗi khi xác thực file audio: {str(e)}") from e

    async def _split_transcript_by_llm(self, content: str) -> List[str]:
        """
        Sử dụng OpenAI qua PydanticAI với structured output để phân đoạn transcript.
        Args:
            content: str - transcript gốc
        Returns:
            List[str] - danh sách câu đã phân đoạn và validated
        """
        start_time = time.time()

        try:

            async def run_async():
                self.logger.debug(
                    "Khởi tạo Agent với model: %s", settings.ai_pydantic_model
                )
                agent = Agent(
                    model=settings.ai_pydantic_model,
                    output_type=TranscriptSegments,
                    system_prompt="""Bạn là một chuyên gia xử lý ngôn ngữ tự nhiên.
                    Nhiệm vụ của bạn là phân đoạn transcript thành các câu ngắn tự nhiên.
                    Mỗi câu phải là một đơn vị ngữ nghĩa hoàn chỉnh, dễ đọc và tự nhiên.
                    """,
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
{{
    "segments": [
        "Hello everyone",
        "welcome back to",
        "our channel",
        "today we're going to",
        "explore machine learning",
        "and its applications"
    ]
}}

    Focus on natural speech patterns, not just word counts!
    Return as JSON object with segments array.
    """
                return await agent.run(user_prompt=prompt)

            # Chạy coroutine trong event loop hiện tại hoặc mới nếu cần
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                if loop.is_running():
                    # Nếu event loop đang chạy (ví dụ trong pytest hoặc notebook), chạy coroutine qua create_task và await
                    result = (
                        await run_async()
                        if asyncio.iscoroutinefunction(run_async)
                        else run_async()
                    )
                else:
                    result = loop.run_until_complete(run_async())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(run_async())

            # result.data là TranscriptSegments object với auto-validation
            transcript_segments = result.data
            duration = time.time() - start_time
            self.logger.debug(
                "Hoàn thành phân đoạn transcript trong %.2f giây, tạo được %d segments",
                duration,
                len(transcript_segments.segments),
            )
            # Pydantic đã validate và auto-fix, trả về segments
            return transcript_segments.segments

        except (json.JSONDecodeError, ValidationError) as e:
            # Ghi log chi tiết lỗi validation hoặc parse JSON
            self.logger.warning(
                "Lỗi khi xử lý kết quả từ LLM: %s. Kiểu lỗi: %s. Sử dụng fallback method.",
                str(e),
                type(e).__name__,
                exc_info=True,  # Thêm stack trace vào log
            )
            # Tách câu dựa trên dấu câu và từ nối
            sentence_enders = r"(?<=[.!?])\s+"
            comma_separators = r"(?<=,)\s+"
            conjunctions = r"\s+(?=and|or|but|so|because|when|if|while|although)\s+"

            pattern = f"{sentence_enders}|{comma_separators}|{conjunctions}"
            lines = re.split(pattern, content.strip())
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
                        validated_lines.append(" ".join(chunk))
                    elif len(chunk) == 1 and not words:
                        validated_lines.append(chunk[0])
                    elif len(chunk) == 1 and words:
                        if char_count + len(words[0]) + 1 <= 35:
                            chunk.append(words.pop(0))
                            validated_lines.append(" ".join(chunk))
                        else:
                            validated_lines.append(chunk[0])
            duration = time.time() - start_time
            self.logger.info(
                "Hoàn thành phân đoạn bằng fallback method trong %.2f giây, tạo được %d segments",
                duration,
                len(validated_lines),
            )
            return validated_lines

    def _normalize_text(self, text: str) -> List[str]:
        """Chuẩn hóa văn bản để phù hợp với tokenization của Gentle"""
        # Tách từ và loại bỏ dấu câu
        words = re.findall(r"\b\w+\b", text.lower())
        return words

    def _find_word_groups_fallback(
        self,
        word_items: List[Dict],
        transcript_lines: List[str],
        alignment_issues: List[Dict],
    ) -> List[Dict]:
        """
        Tạo word groups từ word_items với các kiểm tra robust hơn.

        Args:
            word_items: Danh sách các từ từ Gentle aligner, mỗi từ là một dict chứa:
                - word: Nội dung từ
                - start: Thời gian bắt đầu (giây)
                - end: Thời gian kết thúc (giây)
                - case: Trạng thái align ('success' nếu thành công)
            transcript_lines: Danh sách các dòng transcript cần tìm timing
            alignment_issues: Danh sách các vấn đề alignment

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
        success_words = filter_successful_words(word_items)

        if not success_words:
            self.logger.warning("Không có từ nào được align thành công")
            return []

        self.logger.debug(
            "Bắt đầu tìm word groups cho %d dòng transcript", len(transcript_lines)
        )

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
            group = self._find_exact_match(line_normalized, success_words, word_index)

            if group and len(group) == len(line_normalized):
                # Tìm thấy khớp chính xác
                self.logger.debug("Tìm thấy khớp chính xác cho dòng %d", line_idx)
                text_over_item = self._create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    # Chỉ cập nhật word_index nếu tìm thấy từ align thành công cuối cùng trong group
                    for item in reversed(group):
                        if item in success_words:
                            word_index = success_words.index(item) + 1
                            break
                    # Nếu không có từ align thành công nào trong group, giữ nguyên word_index
                    continue

            # Nếu không tìm thấy khớp chính xác, thử tìm kiếm mềm dẻo
            self.logger.debug(
                "Không tìm thấy khớp chính xác, thử tìm kiếm mềm dẻo cho dòng %d",
                line_idx,
            )

            # Tìm kiếm không phân biệt thứ tự
            group = self._find_flexible_match(
                line_normalized,
                success_words[word_index:],
                alignment_issues,
                max_lookahead=20,  # Giới hạn số từ xem xét để tăng hiệu suất
            )

            if group and len(group) == len(line_normalized):
                # Tìm thấy khớp mềm dẻo
                text_over_item = self._create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    # Chỉ cập nhật word_index nếu tìm thấy từ align thành công cuối cùng trong group
                    for item in reversed(group):
                        if item in success_words:
                            word_index = success_words.index(item) + 1
                            break
                    # Nếu không có từ align thành công nào trong group, giữ nguyên word_index
                    continue
            else:
                self.logger.warning(
                    "Không thể tìm thấy đủ từ cho dòng %d: %s (chỉ tìm thấy %d/%d từ)",
                    line_idx,
                    line,
                    len(group) if group else 0,
                    len(line_normalized),
                )

                # Thêm dòng này với timing 0 nếu không tìm thấy từ nào
                if not group and text_over:
                    last_end = text_over[-1]["start_time"] + text_over[-1]["duration"]
                    text_over.append(
                        {
                            "text": line,
                            "start_time": last_end,
                            "duration": 1.0,  # Mặc định 1 giây
                        }
                    )

        self.logger.info(
            "Đã tạo được %d text_over items từ %d dòng",
            len(text_over),
            len(transcript_lines),
        )
        return text_over

    def _find_exact_match(
        self, words: List[str], word_items: List[Dict], start_idx: int
    ) -> List[Dict]:
        """Tìm kiếm chính xác dãy từ trong word_items."""
        if not words or start_idx >= len(word_items):
            return []

        # Tìm vị trí bắt đầu khả thi
        for i in range(start_idx, len(word_items) - len(words) + 1):
            match = True
            for j, word in enumerate(words):
                if word_items[i + j]["word"].lower() != word:
                    match = False
                    break

            if match:
                return word_items[i : i + len(words)]

        return []

    def _find_flexible_match(
        self,
        words: List[str],
        word_items: List[Dict],
        alignment_issues: List[Dict],
        max_lookahead: int = 20,
    ) -> List[Dict]:
        """Tìm kiếm mềm dẻo các từ không theo thứ tự, bao gồm cả từ không có trong audio."""
        if not words:
            return []
        search_items = (
            word_items[: min(len(word_items), max_lookahead)] if word_items else []
        )
        word_to_items = {}
        for item in search_items:
            word = item["word"].lower()
            if word not in word_to_items:
                word_to_items[word] = []
            word_to_items[word].append(item)
        # Tạo dict tra cứu alignment_issues
        issue_words = {
            w["word"].lower(): w
            for w in alignment_issues
            if w.get("case") == "not-found-in-audio"
        }
        found_items = []
        for w in words:
            lw = w.lower()
            if lw in word_to_items and word_to_items[lw]:
                found_items.append(word_to_items[lw].pop(0))
            elif lw in issue_words:
                found_items.append(issue_words[lw])  # Đánh dấu là not-found-in-audio
            else:
                # Nếu không tìm thấy, bỏ qua hoặc log thêm nếu cần
                self.logger.warning(
                    "Không tìm thấy từ '%s' trong cả align thành công lẫn alignment_issues.",
                    w,
                )
        return found_items

    def _create_text_over_item(
        self, text: str, word_items: List[Dict]
    ) -> Optional[Dict]:
        """Tạo text_over item từ danh sách từ.

        Xử lý overlap và nội suy thời gian cho các từ not-found-in-audio.
        """
        if not word_items:
            return None

        # Bổ sung nội suy thời gian cho các từ not-found-in-audio
        # 1. Xác định các chỉ số từ align thành công
        success_indices = [
            i
            for i, w in enumerate(word_items)
            if w.get("case", "success") == "success" and "start" in w and "end" in w
        ]
        default_duration = 0.15
        # Nếu không có từ align thành công, gán start/end mặc định
        if not success_indices:
            start_time = 0.0
            end_time = default_duration * len(word_items)
            # Gán thời gian mặc định cho tất cả các từ
            for idx, w in enumerate(word_items):
                if "start" not in w:
                    w["start"] = start_time + idx * default_duration
                if "end" not in w:
                    w["end"] = w["start"] + default_duration
                if w.get("case") == "not-found-in-audio":
                    self.logger.warning(
                        "Nội suy timing cho từ not-found-in-audio '%s'"
                        "(không có từ align thành công xung quanh)",
                        w.get("word", "unknown"),
                    )
        else:
            # Duyệt từng từ, nếu là not-found-in-audio thì nội suy dựa vào từ lân cận
            for i, w in enumerate(word_items):
                if w.get("case") == "not-found-in-audio":
                    prev_idx = None
                    next_idx = None
                    for idx in success_indices:
                        if idx < i:
                            prev_idx = idx
                        elif idx > i:
                            next_idx = idx
                            break
                    if prev_idx is not None and next_idx is not None:
                        prev_end = word_items[prev_idx]["end"]
                        next_start = word_items[next_idx]["start"]
                        n_not_found = next_idx - prev_idx - 1
                        # Chia đều khoảng thời gian trống
                        if n_not_found > 0:
                            delta = (next_start - prev_end) / (n_not_found + 1)
                            w["start"] = prev_end + delta * (i - prev_idx)
                            w["end"] = w["start"] + delta
                        else:
                            w["start"] = prev_end
                            w["end"] = next_start
                    elif prev_idx is not None:
                        w["start"] = word_items[prev_idx]["end"]
                        w["end"] = w["start"] + default_duration
                    elif next_idx is not None:
                        w["end"] = word_items[next_idx]["start"]
                        w["start"] = w["end"] - default_duration
                    else:
                        w["start"] = i * default_duration
                        w["end"] = w["start"] + default_duration
                    self.logger.warning(
                        "Nội suy timing cho từ"
                        "not-found-in-audio '%s'"
                        "(giữa các từ align thành công)",
                        w["word"],
                    )
        # Sắp xếp lại theo thời gian để chắc chắn
        word_items = sorted(word_items, key=lambda x: x["start"])
        # Kiểm tra và sửa overlap
        for i in range(1, len(word_items)):
            if word_items[i - 1]["end"] > word_items[i]["start"]:
                # Điều chỉnh thời gian kết thúc của từ trước
                word_items[i - 1]["end"] = word_items[i]["start"]
            self.logger.debug(
                "Đã điều chỉnh overlap giữa '%s' (%.2fs-%.2fs) và '%s' (%.2fs-%.2fs)",
                word_items[i - 1]["word"],
                word_items[i - 1]["start"],
                word_items[i - 1]["end"],
                word_items[i]["word"],
                word_items[i]["start"],
                word_items[i].get("end", 0),
            )
        # Tính toán thời gian bắt đầu và kết thúc
        start_time = word_items[0]["start"]
        end_time = word_items[-1]["end"]
        # Đảm bảo thời lượng tối thiểu là 0.1 giây
        duration = max(0.1, end_time - start_time)
        return {"text": text, "start_time": start_time, "duration": duration}

    async def _find_word_groups(
        self,
        word_items: List[Dict],
        transcript_lines: List[str],
        alignment_issues: List[Dict],
    ) -> List[Dict]:
        """Tìm groups từ cho từng câu transcript - sử dụng fallback method"""
        self.logger.info(
            "Bắt đầu tìm word groups cho %d segments", len(transcript_lines)
        )
        start_time = time.time()

        try:
            self.logger.debug("Sử dụng fallback method để tìm word groups")
            result = self._find_word_groups_fallback(
                word_items, transcript_lines, alignment_issues
            )
            duration = time.time() - start_time
            self.logger.info(
                "Đã tìm thấy %d word groups (fallback) trong %.2f giây",
                len(result),
                duration,
            )
            return result
        except (KeyError, IndexError, ValueError) as e:
            self.logger.error(
                "Lỗi cấu trúc dữ liệu khi tìm word groups: %s", str(e), exc_info=True
            )
            # Trả về danh sách rỗng nếu có lỗi xử lý
            return []
        except Exception as e:
            self.logger.error(
                "Lỗi không xác định khi tìm word groups: %s", str(e), exc_info=True
            )
            raise  # Ném lại ngoại lệ để xử lý ở tầng trên

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
            # Lấy temp_dir từ context (hỗ trợ cả đối tượng và dict)
            context = kwargs.get("context")
            temp_dir = getattr(context, "temp_dir", None) if context else None
            temp_dir = temp_dir or (
                context.get("temp_dir") if isinstance(context, dict) else None
            )

            self.logger.debug(
                f"Sử dụng thư mục tạm: {temp_dir}"
                if temp_dir
                else "Không có thư mục tạm được chỉ định"
            )

            for idx, segment in enumerate(input_data, 1):
                segment_id = segment.get("id", f"unknown_{idx}")
                segment_start_time = time.time()

                self.logger.info(
                    "[%d/%d] Đang xử lý segment %s", idx, len(input_data), segment_id
                )

                # Kiểm tra voice_over
                voice_over = segment.get("voice_over")
                if not voice_over:
                    self.logger.warning(
                        "Segment %s: Bỏ qua do thiếu voice_over", segment_id
                    )
                    continue

                # Kiểm tra và xác thực file audio
                audio_path = voice_over.get("local_path")
                try:
                    self.validate_audio_file(audio_path)
                    self.logger.debug("Segment %s: File audio hợp lệ", segment_id)
                except ValidationError as ve:
                    self.logger.warning(
                        "Segment %s: Lỗi xác thực audio - %s", segment_id, str(ve)
                    )
                    continue

                # Kiểm tra nội dung transcript
                transcript_content = voice_over.get("content", "").strip()
                if not transcript_content:
                    self.logger.warning(
                        "Segment %s: Bỏ qua do thiếu nội dung transcript",
                        segment_id,
                    )
                    continue
                # Lưu nội dung transcript vào file
                try:
                    output_file = os.path.join(
                        temp_dir, f"{segment_id}_transcript.json"
                    )
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(transcript_content, f, ensure_ascii=False, indent=2)
                    self.logger.debug("Đã lưu transcript vào file: %s", output_file)
                except (IOError, OSError, TypeError, ValueError) as e:
                    self.logger.warning("Không thể lưu transcript: %s", str(e))

                # Log thông tin cơ bản
                audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                self.logger.debug(
                    "Segment %s: Audio=%s (%.2f MB), Transcript length=%d ký tự",
                    segment_id,
                    os.path.basename(audio_path),
                    audio_size_mb,
                    len(transcript_content),
                )

                # Xử lý transcript
                transcript_lines = voice_over.get("transcript_lines")
                if not transcript_lines:
                    self.logger.debug(
                        "Segment %s: Đang phân đoạn transcript...", segment_id
                    )
                    try:
                        transcript_lines = await self._split_transcript_by_llm(
                            transcript_content
                        )
                        self.logger.debug(
                            "Segment %s: Đã phân đoạn thành %d dòng",
                            segment_id,
                            len(transcript_lines),
                        )
                        # Lưu transcript_lines vào file JSON
                        try:
                            transcript_lines_file = os.path.join(
                                temp_dir, f"{segment_id}_transcript_lines.json"
                            )
                            with open(
                                transcript_lines_file, "w", encoding="utf-8"
                            ) as f:
                                json.dump(
                                    transcript_lines,
                                    f,
                                    ensure_ascii=False,
                                    indent=2,
                                )
                            self.logger.debug(
                                "Đã lưu transcript_lines vào file: %s",
                                transcript_lines_file,
                            )
                        except (IOError, OSError, TypeError, ValueError) as e:
                            self.logger.warning(
                                "Không thể lưu transcript_lines: %s", str(e)
                            )

                    except (ValueError, json.JSONDecodeError, KeyError) as e:
                        self.logger.error(
                            "Segment %s: Lỗi khi phân đoạn transcript - %s",
                            segment_id,
                            str(e),
                            exc_info=True,
                        )
                        continue

                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".txt",
                        delete=False,
                        dir=temp_dir,
                        encoding="utf-8",
                    ) as f:
                        f.write(transcript_content)
                        transcript_path = f.name

                    self.logger.debug(
                        "Segment %s: Đã tạo file transcript tạm: %s",
                        segment_id,
                        transcript_path,
                    )

                    # Xử lý audio và transcript với Gentle
                    gentle_url = (
                        settings.gentle_url
                        if hasattr(settings, "gentle_url") and settings.gentle_url
                        else "http://localhost:8765/transcriptions"
                    )
                    gentle_timeout = (
                        settings.gentle_timeout
                        if hasattr(settings, "gentle_timeout")
                        and settings.gentle_timeout
                        else 300
                    )

                    self.logger.info("Sử dụng Gentle URL: %s", gentle_url)
                    self.logger.info("Sử dụng Gentle timeout: %s giây", gentle_timeout)

                    try:
                        result, verification = align_audio_with_transcript(
                            audio_path=audio_path,
                            transcript_path=transcript_path,
                            gentle_url=gentle_url,
                            timeout=gentle_timeout,
                            min_success_ratio=0.8,
                        )
                        if not verification.get("is_verified"):
                            self.logger.warning(
                                "Segment %s: Tỷ lệ thành công thấp hơn ngưỡng - %s",
                                segment_id,
                                str(verification.get("success_ratio")),
                            )
                            continue
                        try:
                            # Tạo tên file đầu ra dựa trên segment_id
                            output_file = os.path.join(
                                temp_dir, f"{segment_id}_words.json"
                            )

                            # Ghi dữ liệu vào file
                            with open(output_file, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)

                            self.logger.debug("Đã lưu words vào file: %s", output_file)
                        except (
                            IOError,
                            OSError,
                            TypeError,
                            ValueError,
                        ) as save_error:
                            self.logger.warning(
                                "Không thể lưu words: %s", str(save_error)
                            )

                        self.logger.debug(
                            "Segment %s: Kết quả align - %d/%d từ được nhận diện (%.1f%%)",
                            segment_id,
                            verification.get("success_count"),
                            verification.get("total_words"),
                            verification.get("success_ratio") * 100,
                        )
                        if len(verification.get("alignment_issues")) > 0:
                            self.logger.warning(
                                "Segment %s: Có %d vấn đề alignment:\n%s",
                                segment_id,
                                len(verification.get("alignment_issues")),
                                "\n".join(
                                    [
                                        f"{issue['word']} ({issue['case']})"
                                        for issue in verification.get(
                                            "alignment_issues"
                                        )
                                    ]
                                ),
                            )
                        word_items = result.get("words")
                        # Tạo text_over từ kết quả align
                        try:
                            # Tạo kết quả text_over
                            text_over_result = self._find_word_groups_fallback(
                                word_items,
                                transcript_lines,
                                verification.get("alignment_issues"),
                            )
                            segment["text_over"] = text_over_result

                            # Lưu kết quả vào file JSON trong thư mục tạm
                            try:
                                # Tạo tên file đầu ra dựa trên segment_id
                                output_file = os.path.join(
                                    temp_dir, f"{segment_id}_text_over.json"
                                )

                                # Ghi dữ liệu vào file
                                with open(output_file, "w", encoding="utf-8") as f:
                                    json.dump(
                                        text_over_result,
                                        f,
                                        ensure_ascii=False,
                                        indent=2,
                                    )

                                self.logger.debug(
                                    "Đã lưu text_over vào file: %s", output_file
                                )
                            except (
                                IOError,
                                OSError,
                                TypeError,
                                ValueError,
                            ) as save_error:
                                self.logger.warning(
                                    "Không thể lưu text_over: %s", str(save_error)
                                )

                            self.logger.info(
                                "Segment %s: Đã tạo %d text_over items",
                                segment_id,
                                len(text_over_result),
                            )
                            processed_count += 1

                        except (RuntimeError, ValueError, TypeError) as e:
                            self.logger.error(
                                "Segment %s: Lỗi khi tạo text_over - %s",
                                segment_id,
                                str(e),
                                exc_info=True,
                            )
                            raise RuntimeError(
                                f"Lỗi khi tạo text_over cho segment {segment_id}"
                            ) from e

                    except (
                        ValueError,
                        json.JSONDecodeError,
                        KeyError,
                        AttributeError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.info(
                            "Segment %s: Đang xử lý với Gentle (timeout: %s giây)...",
                            segment_id,
                            gentle_timeout,
                        )
                        self.logger.error(
                            "Segment %s: Lỗi khi xử lý với Gentle - %s",
                            segment_id,
                            str(e),
                            exc_info=True,
                        )
                        raise AlignmentError(
                            f"Lỗi khi xử lý với Gentle cho segment {segment_id}",
                            alignment_data={
                                "segment_id": segment_id,
                                "error": str(e),
                            },
                        ) from e

                except (IOError, OSError) as e:
                    self.logger.error(
                        "Segment %s: Lỗi khi tạo file tạm - %s",
                        segment_id,
                        str(e),
                        exc_info=True,
                    )
                    raise AudioProcessingError(
                        f"Lỗi khi xử lý file tạm cho segment {segment_id}",
                        file_path=audio_path,
                    ) from e

                # Log thời gian xử lý cho segment hiện tại
                segment_time = time.time() - segment_start_time
                self.logger.debug(
                    "Hoàn thành segment %s sau %.2f giây", segment_id, segment_time
                )

            # Kết thúc quá trình xử lý
            total_time = time.time() - start_time
            avg_time = total_time / len(input_data) if input_data else 0

            self.logger.info(
                "Đã xử lý xong %d/%d segment(s) trong %.2f giây (trung bình %.2f giây/segment)",
                processed_count,
                len(input_data),
                total_time,
                avg_time,
            )

            self._end_processing(
                metric, success=processed_count > 0, items_processed=processed_count
            )

            return input_data

        except Exception as e:
            error_msg = f"Lỗi nghiêm trọng khi xử lý: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(
                metric,
                success=False,
                error_message=error_msg,
                items_processed=processed_count,
            )
            raise ProcessingError(error_msg) from e
