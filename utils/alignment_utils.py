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
    Tìm kiếm mềm dẻo các từ không theo thứ tự với khả năng tìm từ tương tự.

    Args:
        words: Danh sách từ cần tìm
        word_items: Danh sách các từ từ Gentle aligner
        alignment_issues: Danh sách các vấn đề alignment
        max_lookahead: Số từ tối đa để xem xét phía trước

    Returns:
        List[Dict]: Danh sách các từ tìm thấy (có thể là partial match)
    """
    if not words or not word_items:
        return []

    found_items = []
    remaining_words = set(word.lower() for word in words)
    original_remaining = remaining_words.copy()

    # Giới hạn phạm vi tìm kiếm
    search_items = word_items[:max_lookahead]

    # Phase 1: Exact matching
    for item in search_items:
        item_word = item.get("word", "").lower()
        if item_word in remaining_words:
            found_items.append(item)
            remaining_words.remove(item_word)

            if not remaining_words:
                break

    # Phase 2: Fuzzy matching for remaining words
    if remaining_words and len(found_items) < len(original_remaining):
        for item in search_items:
            if item in found_items:  # Skip already matched items
                continue
                
            item_word = item.get("word", "").lower()
            
            # Try fuzzy matching
            for word in list(remaining_words):
                # Check if words are similar (contain each other or share significant portion)
                if (
                    len(word) >= 3 and len(item_word) >= 3 and
                    (word in item_word or item_word in word or
                     _calculate_similarity(word, item_word) > 0.6)
                ):
                    found_items.append(item)
                    remaining_words.remove(word)
                    alignment_logger.debug(
                        "Fuzzy match: '%s' matched with '%s'", word, item_word
                    )
                    break

            if not remaining_words:
                break

    # Phase 3: Position-based matching for very short words
    if remaining_words and len(found_items) > 0:
        # For remaining short words, try to find them near already found words
        for word in list(remaining_words):
            if len(word) <= 2:  # Very short words
                # Look for items near our found items
                for item in search_items:
                    if item not in found_items:
                        item_word = item.get("word", "").lower()
                        if len(item_word) <= 3 and word[0] == item_word[0]:  # First letter match
                            found_items.append(item)
                            remaining_words.remove(word)
                            alignment_logger.debug(
                                "Position match: '%s' matched with '%s'", word, item_word
                            )
                            break

    # Sort found items by their original position in word_items
    found_items.sort(key=lambda x: word_items.index(x) if x in word_items else 0)

    # Log missing words only if we found less than 30% of the words
    if remaining_words and len(found_items) < len(original_remaining) * 0.3:
        issue = {
            "missing_words": list(remaining_words),
            "found_words": len(found_items),
            "total_words": len(original_remaining),
            "context": f"Tìm thấy {len(found_items)}/{len(original_remaining)} từ trong {len(search_items)} từ",
        }
        alignment_issues.append(issue)
        alignment_logger.warning(
            "Chỉ tìm thấy %d/%d từ. Thiếu: %s", 
            len(found_items), len(original_remaining), ", ".join(remaining_words)
        )

    return found_items


def _calculate_similarity(word1: str, word2: str) -> float:
    """
    Tính độ tương tự giữa hai từ dựa trên số ký tự chung.
    
    Returns:
        float: Giá trị từ 0.0 đến 1.0
    """
    if not word1 or not word2:
        return 0.0
    
    # Count common characters
    common_chars = sum(1 for c in word1 if c in word2)
    max_len = max(len(word1), len(word2))
    
    return common_chars / max_len if max_len > 0 else 0.0
