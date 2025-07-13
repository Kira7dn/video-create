import requests
from typing import List, Dict
from app.services.processors.base_processor import BaseProcessor, ProcessingStage
from app.core.exceptions import ProcessingError
import tempfile, json
import re
import os

class TranscriptProcessor(BaseProcessor):
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
    
    def _find_word_groups(self, word_items: List[Dict], transcript_lines: List[str]) -> List[Dict]:
        """Tìm groups từ cho từng câu transcript bằng word matching"""
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

    def process(self, input_data: List[Dict], **kwargs) -> List[Dict]:
        metric = self._start_processing(ProcessingStage.TEXT_OVERLAY)
        context = kwargs.get("context")
        try:
            for segment in input_data:
                voice_over = segment.get('voice_over')
                if not voice_over:
                    continue
                audio_path = voice_over.get('local_path')
                transcript_content = voice_over.get('content', '')
                transcript_lines = voice_over.get('transcript_lines')
                if not transcript_lines:
                    transcript_lines = re.split(r'(?<=[.!?])\s+', transcript_content.strip())
                joined_transcript = " ".join(transcript_lines)
                # Nếu cần, lấy temp_dir từ context
                temp_dir = None
                if context:
                    temp_dir = context.get('temp_dir') if isinstance(context, dict) else getattr(context, 'temp_dir', None)
                # Tạo file tạm trong temp_dir nếu có
                if temp_dir:
                    transcript_path = os.path.join(temp_dir, f"transcript_{segment.get('id', '')}.txt")
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(joined_transcript)
                else:
                    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
                        f.write(joined_transcript)
                        transcript_path = f.name
                with open(audio_path, "rb") as a_file, open(transcript_path, "rb") as t_file:
                    files = {"audio": a_file, "transcript": t_file}
                    response = requests.post(
                        "http://localhost:8765/transcriptions?async=false",
                        files=files
                    )
                result = response.json()
                word_items = [w for w in result["words"] if w.get("case") == "success"]
                segment["text_over"] = self._find_word_groups(word_items, transcript_lines)
            self._end_processing(metric, success=True, items_processed=len(input_data))
            return input_data
        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise ProcessingError(f"Gentle alignment failed: {e}") from e
