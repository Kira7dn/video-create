"""
Module xử lý transcript và tạo text overlay với timing chính xác.

Module này cung cấp các chức năng để xử lý transcript từ âm thanh, đồng bộ hóa văn bản
với âm thanh sử dụng Gentle forced aligner, và tạo các đoạn văn bản hiển thị đúng thời điểm.
"""

# Standard library imports
import json
import logging
import os
import tempfile
import time
from typing import Dict, List

# Third-party imports
import requests

# Local application imports
from app.config.settings import settings
from app.core.exceptions import ProcessingError, AudioProcessingError, AlignmentError
from app.services.processors.core.base_processor import AsyncProcessor, ProcessingStage
from utils.alignment_utils import find_exact_match, find_flexible_match
from utils.gentle_utils import align_audio_with_transcript, filter_successful_words
from utils.text_utils import split_transcript, create_text_over_item, normalize_text

logger = logging.getLogger(__name__)


class TranscriptProcessor(AsyncProcessor):
    """
    Xử lý transcript và tạo text overlay với timing chính xác.

    Sử dụng Gentle forced aligner để đồng bộ hóa văn bản với âm thanh,
    tạo ra các đoạn văn bản hiển thị đúng thời điểm trong video.
    """

    def __init__(self, *args, **kwargs):
        """Khởi tạo TranscriptProcessor với cấu hình mặc định."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.DEBUG)

    def _find_word_groups(
        self,
        word_items: List[Dict],
        transcript_lines: List[str],
        alignment_issues: List[Dict],
    ) -> List[Dict]:
        """
        Create word groups from word_items with robust checks.

        Args:
            word_items: List of words from Gentle aligner, each word is a dict containing:
                - word: Word content
                - start: Start time (seconds)
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
            "Start finding word groups for %d lines", len(transcript_lines)
        )

        for line_idx, line in enumerate(transcript_lines, 1):
            if not line.strip():
                self.logger.debug("Skip empty line at position %d", line_idx)
                continue

            line_normalized = normalize_text(line)
            if not line_normalized:
                self.logger.warning("Cannot normalize line: %s", line)
                continue

            self.logger.debug("Processing line %d: %s", line_idx, line)

            # Tìm kiếm chính xác trước
            group = self._find_exact_match(line_normalized, success_words, word_index)

            if group and len(group) == len(line_normalized):
                text_over_item = create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    for item in reversed(group):
                        if item in success_words:
                            word_index = success_words.index(item) + 1
                            break
                    continue

            group = self._find_flexible_match(
                line_normalized,
                success_words[word_index:],
                alignment_issues,
                max_lookahead=20,
            )

            if group and len(group) == len(line_normalized):
                text_over_item = create_text_over_item(line, group)
                if text_over_item:
                    text_over.append(text_over_item)
                    for item in reversed(group):
                        if item in success_words:
                            word_index = success_words.index(item) + 1
                            break
                    continue
                self.logger.debug(
                    "Cannot find exact match, flexible matched for line %d",
                    line_idx,
                )
            else:
                self.logger.warning(
                    "Cannot find enough words for line %d: %s (only found %d/%d words)",
                    line_idx,
                    line,
                    len(group) if group else 0,
                    len(line_normalized),
                )

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
        """
        Find exact match for a sequence of words in word_items.

        Args:
            words: List of words to find
            word_items: List of words from Gentle aligner
            start_idx: Start index for search

        Returns:
            Danh sách các từ tìm thấy
        """
        return find_exact_match(words, word_items, start_idx)

    def _find_flexible_match(
        self,
        words: List[str],
        word_items: List[Dict],
        alignment_issues: List[Dict],
        max_lookahead: int = 20,
    ) -> List[Dict]:
        """
        Find flexible match for a sequence of words in word_items.

        Args:
            words: List of words to find
            word_items: List of words from Gentle aligner
            alignment_issues: List of alignment issues
            max_lookahead: Number of words to look ahead

        Returns:
            List[Dict]: List of words found
        """
        return find_flexible_match(words, word_items, alignment_issues, max_lookahead)

    async def process(self, input_data: List[Dict], **kwargs) -> List[Dict]:
        """
        Xử lý transcript và tạo text overlay với timing chính xác.

        Args:
            input_data: Danh sách các segment cần xử lý, mỗi segment phải chứa:
                - id: Định danh duy nhất của segment
                - voice_over (tùy chọn): Chứa thông tin audio và transcript:
                    - local_path: Đường dẫn đến file audio
                    - content: Nội dung transcript
            **kwargs: Các tham số bổ sung:
                - context: Chứa thông tin ngữ cảnh bổ sung

        Returns:
            List[Dict]: Danh sách các segment đã được xử lý với trường 'text_over' bổ sung

        Raises:
            ProcessingError: Nếu có lỗi nghiêm trọng trong quá trình xử lý

        Note:
            - Mỗi segment được xử lý độc lập, lỗi ở một segment không ảnh hưởng đến các segment khác
        """
        if not input_data:
            self.logger.warning("Không có dữ liệu đầu vào để xử lý")
            return []

        self.logger.info("Bắt đầu xử lý %d segment(s)", len(input_data))
        start_time = time.time()
        metric = self._start_processing(ProcessingStage.TEXT_OVERLAY)
        processed_count = 0

        try:
            # Lấy temp_dir từ context
            context = kwargs.get("context")
            if context is None:
                self.logger.warning("Không tìm thấy context")
                return []

            temp_dir = context.temp_dir
            if temp_dir is None:
                self.logger.warning("Không tìm thấy temp_dir trong context")
                return []

            for idx, segment in enumerate(input_data, 1):
                segment_id = segment.get("id", f"unknown_{idx}")

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
                voice_path = voice_over.get("local_path")

                # Kiểm tra nội dung transcript
                transcript_content = voice_over.get("content", "").strip()
                if not transcript_content:
                    self.logger.warning(
                        "Segment %s: Bỏ qua do thiếu nội dung transcript",
                        segment_id,
                    )
                    continue
                self.logger.debug(
                    "Segment %s: Đang phân đoạn transcript...", segment_id
                )
                try:
                    transcript_lines = await split_transcript(transcript_content)
                    try:
                        transcript_lines_file = os.path.join(
                            temp_dir, f"{segment_id}_transcript_lines.json"
                        )
                        with open(transcript_lines_file, "w", encoding="utf-8") as f:
                            json.dump(transcript_lines, f, ensure_ascii=False)
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

                    # Handle gentle
                    gentle_url = settings.gentle_url
                    gentle_timeout = settings.gentle_timeout

                    self.logger.info("Sử dụng Gentle URL: %s", gentle_url)

                    try:
                        result, verification = align_audio_with_transcript(
                            audio_path=voice_path,
                            transcript_path=transcript_path,
                            gentle_url=gentle_url,
                            timeout=gentle_timeout,
                            min_success_ratio=0.8,
                        )
                        if not verification.get("is_verified"):
                            self.logger.warning(
                                "Aligned segment %s: Failed alignment - %s",
                                segment_id,
                                str(verification.get("success_ratio")),
                            )
                            continue
                        try:
                            # Tạo tên file đầu ra dựa trên segment_id
                            words_output_file = os.path.join(
                                temp_dir, f"{segment_id}_words.json"
                            )

                            # Ghi dữ liệu vào file
                            with open(words_output_file, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)

                            self.logger.debug(
                                "Aligned segment %s: Saved words to file: %s",
                                segment_id,
                                words_output_file,
                            )
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
                            "Aligned segment %s: %d/%d",
                            segment_id,
                            verification.get("success_count"),
                            verification.get("total_words"),
                        )
                        if len(verification.get("alignment_issues")) > 0:
                            self.logger.warning(
                                "Aligned segment %s: %d issues:\n%s",
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
                        try:
                            text_over_result = self._find_word_groups(
                                word_items,
                                transcript_lines,
                                verification.get("alignment_issues"),
                            )
                            segment["text_over"] = text_over_result

                            try:
                                text_over_output_file = os.path.join(
                                    temp_dir, f"{segment_id}_text_over.json"
                                )

                                with open(
                                    text_over_output_file, "w", encoding="utf-8"
                                ) as f:
                                    json.dump(
                                        text_over_result,
                                        f,
                                        ensure_ascii=False,
                                        indent=2,
                                    )

                                self.logger.debug(
                                    "Aligned segment %s: Saved text_over to file: %s",
                                    segment_id,
                                    text_over_output_file,
                                )
                            except (
                                IOError,
                                OSError,
                                TypeError,
                                ValueError,
                            ) as save_error:
                                self.logger.warning(
                                    "Aligned segment %s: Failed to save text_over: %s",
                                    segment_id,
                                    str(save_error),
                                )

                            self.logger.info(
                                "Aligned segment %s: Created %d text_over items",
                                segment_id,
                                len(text_over_result),
                            )
                            processed_count += 1

                        except (RuntimeError, ValueError, TypeError) as e:
                            self.logger.error(
                                "Aligned segment %s: Failed to create text_over - %s",
                                segment_id,
                                str(e),
                                exc_info=True,
                            )
                            raise RuntimeError(
                                f"Aligned segment {segment_id}: Failed to create text_over"
                            ) from e

                    except (
                        ValueError,
                        json.JSONDecodeError,
                        KeyError,
                        AttributeError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.info(
                            "Aligned segment %s: Aligning with Gentle (timeout: %s giây)...",
                            segment_id,
                            gentle_timeout,
                        )
                        self.logger.error(
                            "Aligned segment %s: Failed to align with Gentle - %s",
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
                        "Aligned segment %s: Failed to create temporary file - %s",
                        segment_id,
                        str(e),
                        exc_info=True,
                    )
                    raise AudioProcessingError(
                        f"Aligned segment {segment_id}: Failed to process temporary file",
                        file_path=voice_path,
                    ) from e

                self.logger.debug("Aligned segment %s: Completed", segment_id)

            total_time = time.time() - start_time
            avg_time = total_time / len(input_data) if input_data else 0

            self.logger.info(
                "Aligned %d/%d segments in %.2f seconds (average %.2f seconds/segment)",
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
