"""
Các hàm tiện ích hỗ trợ alignment giữa văn bản và âm thanh.

Module này chứa các hàm tìm kiếm và so khớp từ giữa transcript
và kết quả align từ Gentle.
"""

import logging
from typing import Dict, List

# Khởi tạo logger
alignment_logger = logging.getLogger("alignment_utils")


def find_exact_match(
    words: List[str], word_items: List[Dict], start_idx: int
) -> List[Dict]:
    """
    Tìm kiếm chính xác dãy từ trong word_items.

    Args:
        words: Danh sách từ cần tìm
        word_items: Danh sách các từ từ Gentle aligner
        start_idx: Vị trí bắt đầu tìm kiếm

    Returns:
        List[Dict]: Danh sách các từ tìm thấy trong word_items
    """
    if not words or start_idx >= len(word_items):
        return []

    # Tìm vị trí bắt đầu khả thi
    for i in range(start_idx, len(word_items) - len(words) + 1):
        match = True
        for j, word in enumerate(words):
            if i + j >= len(word_items):
                match = False
                break

            item_word = word_items[i + j].get("word", "").lower()
            if item_word != word.lower():
                match = False
                break

        if match:
            return word_items[i : i + len(words)]

    return []


def find_flexible_match(
    words: List[str],
    word_items: List[Dict],
    alignment_issues: List[Dict],
    max_lookahead: int = 20,
) -> List[Dict]:
    """
    Tìm kiếm mềm dẻo các từ không theo thứ tự.

    Args:
        words: Danh sách từ cần tìm
        word_items: Danh sách các từ từ Gentle aligner
        alignment_issues: Danh sách các vấn đề alignment
        max_lookahead: Số từ tối đa để xem xét phía trước

    Returns:
        List[Dict]: Danh sách các từ tìm thấy
    """
    if not words or not word_items:
        return []

    found_items = []
    remaining_words = set(word.lower() for word in words)

    # Giới hạn phạm vi tìm kiếm
    search_items = word_items[:max_lookahead]

    for item in search_items:
        item_word = item.get("word", "").lower()
        if item_word in remaining_words:
            found_items.append(item)
            remaining_words.remove(item_word)

            if not remaining_words:
                break

    # Ghi nhận các từ không tìm thấy
    if remaining_words:
        issue = {
            "missing_words": list(remaining_words),
            "context": f"Không tìm thấy từ trong {len(search_items)} từ đầu tiên",
        }
        alignment_issues.append(issue)
        alignment_logger.warning(
            "Không tìm thấy các từ: %s", ", ".join(remaining_words)
        )

    return found_items
