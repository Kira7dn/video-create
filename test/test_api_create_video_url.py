import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_api_create_video_with_url_input(tmp_path):
    # Copy input_sample.json vào tmp_path
    sample_json_path = os.path.join(
        os.path.dirname(__file__), "..", "input_sample.json"
    )
    assert os.path.exists(sample_json_path), "input_sample.json không tồn tại!"
    # Đọc transitions từ từng object trong input_sample.json
    with open(sample_json_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    transitions_list = [obj["transition"] for obj in input_data if "transition" in obj]
    transitions_str = json.dumps(transitions_list)
    files = {
        "input_json": (
            "input_sample.json",
            open(sample_json_path, "rb"),
            "application/json",
        )
    }
    data = {
        "tmp_dir_param": str(tmp_path / "api_tmp_dir"),
        "transitions_str": transitions_str,
    }
    response = client.post("/api/create-video", files=files, data=data)
    assert response.status_code == 200, f"API lỗi: {response.text}"
    # Lưu file kết quả ra test/result để kiểm tra thủ công
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, "api_create_result.mp4")
    with open(out_path, "wb") as fout:
        fout.write(response.content)
    assert (
        os.path.exists(out_path) and os.path.getsize(out_path) > 0
    ), "Không tạo được file output từ API!"
    print(f"[Test] Video output đã lưu tại: {out_path}")
    # Có thể kiểm tra thêm: duration, định dạng, ... nếu cần


def test_api_create_video_with_url_input_transitions_str(tmp_path):
    # Test truyền transitions_str qua API
    sample_json_path = os.path.join(
        os.path.dirname(__file__), "..", "input_sample.json"
    )
    assert os.path.exists(sample_json_path), "input_sample.json không tồn tại!"
    with open(sample_json_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    transitions_list = [obj["transition"] for obj in input_data if "transition" in obj]
    transitions_str = json.dumps(transitions_list)
    files = {
        "input_json": (
            "input_sample.json",
            open(sample_json_path, "rb"),
            "application/json",
        )
    }
    data = {
        "tmp_dir_param": str(tmp_path / "api_tmp_dir_str"),
        "transitions_str": transitions_str,
    }
    response = client.post("/api/create-video", files=files, data=data)
    assert response.status_code == 200, f"API lỗi: {response.text}"
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, "api_create_result_str.mp4")
    with open(out_path, "wb") as fout:
        fout.write(response.content)
    assert (
        os.path.exists(out_path) and os.path.getsize(out_path) > 0
    ), "Không tạo được file output từ API!"
    print(f"[Test] Video output (transitions_str) đã lưu tại: {out_path}")


def test_api_create_video_with_url_input_auto_transition(tmp_path):
    # Test KHÔNG truyền transitions_str, pipeline tự lấy từ input JSON
    sample_json_path = os.path.join(
        os.path.dirname(__file__), "..", "input_sample.json"
    )
    assert os.path.exists(sample_json_path), "input_sample.json không tồn tại!"
    files = {
        "input_json": (
            "input_sample.json",
            open(sample_json_path, "rb"),
            "application/json",
        )
    }
    data = {
        "tmp_dir_param": str(tmp_path / "api_tmp_dir_auto"),
        # Không truyền transitions_str
    }
    response = client.post("/api/create-video", files=files, data=data)
    assert response.status_code == 200, f"API lỗi: {response.text}"
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, "api_create_result_auto.mp4")
    with open(out_path, "wb") as fout:
        fout.write(response.content)
    assert (
        os.path.exists(out_path) and os.path.getsize(out_path) > 0
    ), "Không tạo được file output từ API!"
    print(f"[Test] Video output (auto transitions) đã lưu tại: {out_path}")
