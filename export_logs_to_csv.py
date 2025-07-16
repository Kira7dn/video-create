#!/usr/bin/env python3
"""
Script để trích xuất dữ liệu từ file test_run.log ra các file CSV
"""
import re
import json
import csv
import os
from pathlib import Path
from datetime import datetime

def extract_transcript_lines(log_content):
    """Trích xuất các dòng transcript từ log"""
    pattern = r'\[.*?\]\s+INFO\s+\[.*?\]\s+Content:\s+(.+)'
    return re.findall(pattern, log_content)

def extract_word_items(log_content):
    """Trích xuất các word items từ log"""
    word_items = []
    
    # Tìm tất cả các khối word items
    word_blocks = re.findall(r'Word items:\s+(\[.*?\])\s*\n', log_content, re.DOTALL)
    
    for block in word_blocks:
        try:
            # Thử parse JSON trực tiếp
            items = json.loads(block)
            if isinstance(items, list):
                word_items.extend(items)
        except json.JSONDecodeError:
            try:
                # Thử sửa lỗi JSON nếu có
                fixed_json = block.replace("'", '"')
                items = json.loads(fixed_json)
                if isinstance(items, list):
                    word_items.extend(items)
            except:
                # Nếu vẫn lỗi, bỏ qua block này
                print(f"Không thể parse word items từ block: {block[:100]}...")
    
    return word_items

def extract_text_over(log_content):
    """
    Trích xuất thông tin text over từ log
    
    Trả về:
        List[dict]: Danh sách các text over items, mỗi item là một dictionary
                   chứa thông tin về text, vị trí, thời gian, style, v.v.
                   Trả về None nếu không tìm thấy thông tin text over
    """
    # Thử tìm dưới dạng JSON
    json_patterns = [
        r'Text over items:\s*(\[.*?\])\s*$',  # Format mới
        r'TextOver\s*:\s*(\[.*?\])\s*$',     # Format cũ hơn
        r'text_over\s*=\s*(\[.*?\])\s*$'      # Format khác
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, log_content, re.DOTALL | re.MULTILINE)
        if matches:
            try:
                # Lấy dữ liệu JSON và parse
                json_str = matches[0].strip()
                # Thay thế các ký tự đặc biệt có thể gây lỗi JSON
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r',\s*}', '}', json_str)  # Sửa lỗi dấu phẩy thừa
                
                data = json.loads(json_str)
                if isinstance(data, list):
                    print(f"Đã tìm thấy {len(data)} text over items")
                    return data
            except json.JSONDecodeError as e:
                print(f"Lỗi khi parse JSON text over: {e}")
                print(f"Nội dung lỗi: {json_str[:200]}...")
                continue
    
    print("Không tìm thấy thông tin text over trong log")
    return []

def save_to_csv(data, filename, fieldnames=None):
    """Lưu dữ liệu ra file CSV"""
    if not data:
        print(f"Không có dữ liệu để lưu vào {filename}")
        return
    
    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        if isinstance(data[0], dict):
            if not fieldnames:
                fieldnames = data[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        else:
            writer = csv.writer(f)
            writer.writerow(['text'])
            for item in data:
                writer.writerow([item])
    
    print(f"Đã lưu {len(data)} mục vào {filename}")

def main():
    # Đường dẫn đến file log và thư mục output
    log_file = 'test_output/logs/test_run.log'
    output_dir = 'test_output/temp'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Đọc nội dung file log
        print(f"Đang đọc file log: {os.path.abspath(log_file)}")
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # Tạo thư mục output nếu chưa tồn tại
        os.makedirs(output_dir, exist_ok=True)
        print(f"Thư mục output: {os.path.abspath(output_dir)}")
        
        # 1. Trích xuất transcript lines
        print("\n1. Đang trích xuất transcript lines...")
        transcript_lines = extract_transcript_lines(log_content)
        if transcript_lines:
            transcript_file = os.path.join(output_dir, f'transcript_lines_{timestamp}.csv')
            save_to_csv(
                [{'line': line} for line in transcript_lines],
                transcript_file,
                ['line']
            )
            print(f"  - Đã lưu {len(transcript_lines)} dòng transcript vào: {transcript_file}")
        else:
            print("  - Không tìm thấy thông tin transcript lines trong log")
        
        # 2. Trích xuất word items
        print("\n2. Đang trích xuất word items...")
        word_items = extract_word_items(log_content)
        if word_items and isinstance(word_items, list) and len(word_items) > 0:
            # Lấy tất cả các trường có thể có
            all_keys = set()
            for item in word_items:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            # Lọc các trường hợp lệ
            valid_fieldnames = [k for k in all_keys if isinstance(k, str) and not k.startswith('_')]
            
            word_items_file = os.path.join(output_dir, f'word_items_{timestamp}.csv')
            save_to_csv(
                word_items,
                word_items_file,
                valid_fieldnames
            )
            print(f"  - Đã lưu {len(word_items)} word items vào: {word_items_file}")
            
            # In thông tin thống kê
            print(f"  - Số lượng từ: {len(word_items)}")
            if word_items and 'word' in word_items[0]:
                print(f"  - 5 từ đầu tiên: {', '.join([w.get('word', '') for w in word_items[:5] if 'word' in w])}...")
        else:
            print("  - Không tìm thấy thông tin word items trong log")
        
        # 3. Trích xuất text over items
        print("\n3. Đang tìm kiếm text over items...")
        text_over = extract_text_over(log_content)
        if text_over and isinstance(text_over, list) and len(text_over) > 0:
            # Lấy tất cả các trường có thể có
            all_keys = set()
            for item in text_over:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            # Lọc các trường hợp lệ
            valid_fieldnames = [k for k in all_keys if isinstance(k, str) and not k.startswith('_')]
            
            text_over_file = os.path.join(output_dir, f'text_over_{timestamp}.csv')
            save_to_csv(
                text_over,
                text_over_file,
                valid_fieldnames
            )
            print(f"  - Đã lưu {len(text_over)} text over items vào: {text_over_file}")
        else:
            print("  - Không tìm thấy thông tin text over trong log")
            print("  - Lưu ý: Có thể thông tin text over không được ghi lại trong log hoặc có định dạng khác")
        
        print("\n✅ Hoàn thành trích xuất dữ liệu!")
        print(f"Các file đã được lưu tại thư mục: {os.path.abspath(output_dir)}")
        
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy file log tại {os.path.abspath(log_file)}")
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi khi parse dữ liệu JSON: {str(e)}")
        print("Vui lòng kiểm tra lại định dạng dữ liệu trong file log.")
    except Exception as e:
        print(f"❌ Đã xảy ra lỗi không mong muốn: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
