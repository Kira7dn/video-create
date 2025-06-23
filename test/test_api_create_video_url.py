import os
import pytest
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)


def test_api_create_video_with_url_input(tmp_path):
    # Copy input_sample.json vào tmp_path
    sample_json_path = os.path.join(
        os.path.dirname(__file__), "..", "input_sample.json"
    )
    assert os.path.exists(sample_json_path), "input_sample.json không tồn tại!"
    with open(sample_json_path, "rb") as f:
        files = {"input_json": ("input_sample.json", f, "application/json")}
        response = client.post("/api/create-video", files=files)
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
