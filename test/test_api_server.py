import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
import pytest
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)


def test_api_concat_videos(tmp_path):
    # Chuẩn bị 2 file video mẫu
    src_dir = os.path.join(os.path.dirname(__file__), "source", "video")
    video_files = [f for f in os.listdir(src_dir) if f.endswith(".mp4")]
    assert len(video_files) >= 2, "Cần ít nhất 2 file video mẫu để test API!"
    files = [
        (
            "videos",
            (
                video_files[0],
                open(os.path.join(src_dir, video_files[0]), "rb"),
                "video/mp4",
            ),
        ),
        (
            "videos",
            (
                video_files[1],
                open(os.path.join(src_dir, video_files[1]), "rb"),
                "video/mp4",
            ),
        ),
    ]
    data = {"transition": "crossfade", "transition_duration": "1.0"}
    response = client.post("/api/concat-videos", files=files, data=data)
    for _, (_, f, _) in files:
        f.close()
    assert response.status_code == 200, f"API lỗi: {response.text}"
    # Lưu file kết quả ra tmp_path để kiểm tra
    out_path = tmp_path / "api_concat_result.mp4"
    with open(out_path, "wb") as fout:
        fout.write(response.content)
    assert (
        out_path.exists() and out_path.stat().st_size > 0
    ), "Không tạo được file output từ API!"
    # Kiểm tra duration
    from moviepy.video.io.VideoFileClip import VideoFileClip

    input_total_duration = 0
    for f in video_files[:2]:
        with VideoFileClip(os.path.join(src_dir, f)) as clip:
            input_total_duration += clip.duration
    with VideoFileClip(str(out_path)) as out_clip:
        expected_duration = input_total_duration - 1.0
        assert (
            abs(out_clip.duration - expected_duration) < 0.1
        ), f"Duration output không đúng, expected {expected_duration}, got {out_clip.duration}"
