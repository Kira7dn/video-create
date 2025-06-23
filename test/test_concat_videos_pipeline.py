import os
import subprocess
import pytest


def test_concat_videos_pipeline(tmp_path):
    # Tạo thư mục tạm và copy 3 file video mẫu vào đó
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    # Giả định test/source/video có ít nhất 3 file .mp4
    src_dir = os.path.join(os.path.dirname(__file__), "source", "video")
    video_files = [f for f in os.listdir(src_dir) if f.endswith(".mp4")]
    assert len(video_files) >= 3, "Cần ít nhất 3 file video mẫu để test pipeline!"
    for f in video_files[:3]:
        src = os.path.join(src_dir, f)
        dst = sample_dir / f
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            fout.write(fin.read())
    # Chạy pipeline với crossfade
    output_path = tmp_path / "output_pipeline.mp4"
    cmd = [
        "python",
        "concat_videos.py",
        "--input-dir",
        str(sample_dir),
        "--output",
        str(output_path),
        "--transition",
        "crossfade",
        "--transition-duration",
        "1.0",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Pipeline lỗi: {result.stderr}"
    assert (
        output_path.exists() and output_path.stat().st_size > 0
    ), "Không tạo được file output pipeline!"
    # Kiểm tra duration
    from moviepy.video.io.VideoFileClip import VideoFileClip

    input_total_duration = 0
    for f in video_files[:3]:
        with VideoFileClip(os.path.join(src_dir, f)) as clip:
            input_total_duration += clip.duration
    with VideoFileClip(str(output_path)) as out_clip:
        expected_duration = input_total_duration - 2 * 1.0
        assert (
            abs(out_clip.duration - expected_duration) < 0.1
        ), f"Duration output không đúng, expected {expected_duration}, got {out_clip.duration}"
