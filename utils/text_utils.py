"""
Các hàm tiện ích để tạo và quản lý text overlay.

Module này chứa các hàm hỗ trợ tạo text overlay với timing chính xác,
xử lý duration và các thao tác liên quan đến hiển thị văn bản.

"""

from typing import Annotated, Dict, List, Optional
import asyncio
import json
import logging
import re
import time

from pydantic_ai import Agent
from pydantic import BaseModel, field_validator

from app.config import settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def create_text_overlay(
    text: str, start_time: float, duration: float, **kwargs
) -> Dict:
    """
    Tạo một text overlay item với các thông số cơ bản.

    Args:
        text: Nội dung văn bản
        start_time: Thời gian bắt đầu (giây)
        duration: Thời lượng hiển thị (giây)
        **kwargs: Các thông số bổ sung

    Returns:
        Dict: Đối tượng text overlay
    """
    return {
        "text": text,
        "start_time": max(0, start_time),  # Đảm bảo không âm
        "duration": max(0.1, duration),  # Đảm bảo duration tối thiểu 0.1s
        **kwargs,
    }


def merge_consecutive_overlays(
    overlays: List[Dict], max_gap: float = 0.5
) -> List[Dict]:
    """
    Hợp nhất các text overlay liên tiếp gần nhau.

    Args:
        overlays: Danh sách các overlay
        max_gap: Khoảng cách tối đa (giây) để coi là liên tiếp

    Returns:
        List[Dict]: Danh sách các overlay đã được hợp nhất
    """
    if not overlays:
        return []

    # Sắp xếp theo thời gian bắt đầu
    sorted_overlays = sorted(overlays, key=lambda x: x["start_time"])
    merged = [sorted_overlays[0]]

    for current in sorted_overlays[1:]:
        last = merged[-1]

        # Tính khoảng cách giữa overlay cuối và hiện tại
        gap = current["start_time"] - (last["start_time"] + last["duration"])

        # Nếu khoảng cách nhỏ hơn ngưỡng, hợp nhất
        if gap <= max_gap and last["text"].endswith((".", "!", "?")) == current[
            "text"
        ].startswith((" ", "\n")):
            last["text"] += " " + current["text"].lstrip()
            last["duration"] = (current["start_time"] + current["duration"]) - last[
                "start_time"
            ]
        else:
            merged.append(current)

    return merged


def validate_segments(v: List[str]) -> List[str]:
    """Validate và auto-fix segments theo YouTube constraints"""
    if not v:
        return []

    validated = []
    for segment in v:
        if not isinstance(segment, str):
            continue

        # Loại bỏ khoảng trắng thừa
        segment = " ".join(segment.split())

        # Bỏ qua segment rỗng
        if not segment:
            continue

        # Kiểm tra độ dài và số từ
        char_count = len(segment)
        words = segment.split()

        # Áp dụng quy tắc YouTube:
        # - Mỗi dòng 2-7 từ
        # - Tối đa 35 ký tự
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


class TranscriptSegments(BaseModel):
    """Pydantic model cho validated transcript segments"""

    segments: Annotated[
        List[str],
        field_validator("segments", mode="after")(validate_segments),
    ]


async def split_transcript(content: str) -> List[str]:
    """Split transcript into natural segments using LLM.

    Args:
        content: The transcript content to split.

    Returns:
        List of segmented transcript parts.

    Raises:
        ValidationError: If there's an error processing the LLM response.
    """
    start_time = time.time()

    try:

        async def run_async():
            logger.debug(
                "Initializing Agent with model: %s", settings.ai_pydantic_model
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

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the async operation
        try:
            if loop.is_running():
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

        # Process the result
        transcript_segments = result.data
        duration = time.time() - start_time

        logger.debug(
            "Completed transcript segmentation in %.2f seconds, created %d segments",
            duration,
            len(transcript_segments.segments),
        )

        return transcript_segments.segments

    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(
            "Error processing LLM response: %s. Error type: %s. Using fallback method.",
            str(e),
            type(e).__name__,
            exc_info=True,
        )
        # Fallback to simple punctuation-based splitting
        return _fallback_split(content)


def _fallback_split(content: str) -> List[str]:
    """Fallback method for splitting transcript when LLM fails.

    Args:
        content: The transcript content to split.

    Returns:
        List of split segments.
    """
    # Split on sentence boundaries and conjunctions
    sentence_enders = r"(?<=[.!?])\s+"
    comma_separators = r"(?<=,)\s+"
    conjunctions = r"\s+(?=and|or|but|so|because|when|if|while|although)\s+"

    pattern = f"{sentence_enders}|{comma_separators}|{conjunctions}"

    # Split and clean up whitespace
    segments = [s.strip() for s in re.split(pattern, content) if s.strip()]

    # Further split long segments
    result = []
    for segment in segments:
        words = segment.split()
        if len(words) <= 7 and len(segment) <= 35:
            result.append(segment)
        else:
            # Simple split for long segments
            for i in range(0, len(words), 5):
                chunk = words[i : i + 5]
                if chunk:
                    result.append(" ".join(chunk))

    return result


def create_text_over_item(text: str, word_items: List[Dict]) -> Optional[Dict]:
    """
    Tạo text_over item từ danh sách từ.

    Args:
        text: Nội dung văn bản
        word_items: Danh sách các từ với thông tin timing

    Returns:
        Optional[Dict]: Dictionary chứa thông tin text overlay hoặc None nếu không hợp lệ
    """
    if not word_items or not text.strip():
        return None

    # Lọc ra các từ có thông tin timing hợp lệ
    valid_words = [
        w for w in word_items if isinstance(w, dict) and "start" in w and "end" in w
    ]

    if not valid_words:
        return None

    # Tính toán thời gian bắt đầu và kết thúc
    start_time = min(w["start"] for w in valid_words)
    end_time = max(w["end"] for w in valid_words)
    duration = max(0.1, end_time - start_time)  # Đảm bảo duration > 0

    return {
        "text": text,
        "start_time": start_time,
        "duration": duration,
        "word_count": len(valid_words),
    }


def normalize_text(text: str) -> List[str]:
    """
    Chuẩn hóa văn bản để phù hợp với tokenization của Gentle.

    Args:
        text: Văn bản cần chuẩn hóa

    Returns:
        List[str]: Danh sách các từ đã được chuẩn hóa
    """
    # Tách từ và loại bỏ dấu câu
    words = re.findall(r"\b\w+\b", text.lower())
    return words
