import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
import pytest
from utils.video_utils import concatenate_videos, concatenate_videos_with_sequence

TEST_VIDEO_DIR = "test/source/video"
OUTPUT_PATH = "test/test_output_concat.mp4"


def test_concatenate_videos_no_transition():
    # Lấy danh sách file video mẫu
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    # Xóa file output cũ nếu có
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    # Gọi hàm nối video
    try:
        concat_clip = concatenate_videos(video_files)
        concat_clip.write_videofile(
            OUTPUT_PATH, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video: {e}")

    # Kiểm tra file output
    assert (
        os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 0
    ), "Không tạo được file video output!"

    # Phân tích duration của video đầu ra
    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(OUTPUT_PATH) as out_clip:
        # Tổng duration mong đợi là tổng duration của các video input
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        # Cho phép sai số nhỏ do encode (0.1s)
        assert (
            abs(out_clip.duration - input_total_duration) < 0.1
        ), f"Duration output không đúng, expected {input_total_duration}, got {out_clip.duration}"


def test_concatenate_videos_crossfade():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    output_path = "test/test_output_concat_crossfade.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        concat_clip = concatenate_videos(
            video_files, transition_type="crossfade", transition_duration=1.0
        )
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với crossfade: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        expected_duration = input_total_duration - (len(video_files) - 1) * 1.0
        assert (
            abs(out_clip.duration - expected_duration) < 0.1
        ), f"Duration output không đúng, expected {expected_duration}, got {out_clip.duration}"


def test_concatenate_videos_fade():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    output_path = "test/test_output_concat_fade.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        concat_clip = concatenate_videos(
            video_files, transition_type="fade", transition_duration=1.0
        )
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với fade: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        # Fade không làm giảm duration tổng
        assert (
            abs(out_clip.duration - input_total_duration) < 0.1
        ), f"Duration output không đúng, expected {input_total_duration}, got {out_clip.duration}"


def test_concatenate_videos_fadeblack():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    output_path = "test/test_output_concat_fadeblack.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        concat_clip = concatenate_videos(
            video_files, transition_type="fadeblack", transition_duration=1.0
        )
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với fadeblack: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        expected_duration = input_total_duration + (len(video_files) - 1) * 1.0
        assert (
            abs(out_clip.duration - expected_duration) < 0.1
        ), f"Duration output không đúng, expected {expected_duration}, got {out_clip.duration}"


def test_concatenate_videos_slideleft():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    output_path = "test/test_output_concat_slideleft.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        concat_clip = concatenate_videos(
            video_files, transition_type="slideleft", transition_duration=1.0
        )
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với slideleft: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        # Slide hiệu ứng không thay đổi tổng duration
        assert (
            abs(out_clip.duration - input_total_duration) < 0.1
        ), f"Duration output không đúng, expected {input_total_duration}, got {out_clip.duration}"


def test_concatenate_videos_slideright():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in os.listdir(TEST_VIDEO_DIR)
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 2, "Cần ít nhất 2 video mẫu để test"

    output_path = "test/test_output_concat_slideright.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        concat_clip = concatenate_videos(
            video_files, transition_type="slideright", transition_duration=1.0
        )
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với slideright: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        # Slide hiệu ứng không thay đổi tổng duration
        assert (
            abs(out_clip.duration - input_total_duration) < 0.1
        ), f"Duration output không đúng, expected {input_total_duration}, got {out_clip.duration}"


def test_concatenate_videos_with_sequence():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in sorted(os.listdir(TEST_VIDEO_DIR))
        if f.endswith(".mp4")
    ]
    assert len(video_files) >= 3, "Cần ít nhất 3 video mẫu để test sequence transitions"

    output_path = "test/test_output_concat_sequence.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    # Ví dụ: 3 video, 2 transition: crossfade, slideleft
    transitions = [
        {"type": "crossfade", "duration": 1.0},
        {"type": "slideleft", "duration": 1.0},
    ]
    try:
        concat_clip = concatenate_videos_with_sequence(video_files[:3], transitions)
        concat_clip.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
    except Exception as e:
        pytest.fail(f"Lỗi khi nối video với sequence transitions: {e}")

    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Không tạo được file video output!"

    from moviepy.video.io.VideoFileClip import VideoFileClip

    with VideoFileClip(output_path) as out_clip:
        input_total_duration = 0
        for path in video_files[:3]:
            with VideoFileClip(path) as clip:
                input_total_duration += clip.duration
        # crossfade giảm 1s, slideleft giữ nguyên
        expected_duration = input_total_duration - 1.0
        assert (
            abs(out_clip.duration - expected_duration) < 0.1
        ), f"Duration output không đúng, expected {expected_duration}, got {out_clip.duration}"


def test_concatenate_videos_edge_cases():
    video_files = [
        os.path.join(TEST_VIDEO_DIR, f)
        for f in sorted(os.listdir(TEST_VIDEO_DIR))
        if f.endswith(".mp4")
    ]
    # Edge case: chỉ 2 video, crossfade
    if len(video_files) >= 2:
        output_path = "test/test_output_edge_2_crossfade.mp4"
        if os.path.exists(output_path):
            os.remove(output_path)
        from utils.video_utils import concatenate_videos

        try:
            concat_clip = concatenate_videos(
                video_files[:2], transition_type="crossfade", transition_duration=0.5
            )
            concat_clip.write_videofile(
                output_path, fps=24, codec="libx264", audio_codec="aac"
            )
        except Exception as e:
            pytest.fail(f"Lỗi edge case 2 video crossfade: {e}")
        assert os.path.exists(output_path) and os.path.getsize(output_path) > 0
        from moviepy.video.io.VideoFileClip import VideoFileClip

        with VideoFileClip(output_path) as out_clip:
            input_total_duration = 0
            for path in video_files[:2]:
                with VideoFileClip(path) as clip:
                    input_total_duration += clip.duration
            expected_duration = input_total_duration - 0.5
            assert abs(out_clip.duration - expected_duration) < 0.1
    # Edge case: truyền vào transition không hợp lệ
    if len(video_files) >= 2:
        from utils.video_utils import concatenate_videos_with_sequence

        output_path = "test/test_output_edge_invalid_transition.mp4"
        if os.path.exists(output_path):
            os.remove(output_path)
        transitions = [{"type": "notfound", "duration": 1.0}]
        try:
            concat_clip = concatenate_videos_with_sequence(video_files[:2], transitions)
            concat_clip.write_videofile(
                output_path, fps=24, codec="libx264", audio_codec="aac"
            )
        except Exception as e:
            pytest.fail(f"Lỗi edge case transition không hợp lệ: {e}")
        assert os.path.exists(output_path) and os.path.getsize(output_path) > 0
        # Duration phải đúng bằng tổng duration (nối cut)
        from moviepy.video.io.VideoFileClip import VideoFileClip

        with VideoFileClip(output_path) as out_clip:
            input_total_duration = 0
            for path in video_files[:2]:
                with VideoFileClip(path) as clip:
                    input_total_duration += clip.duration
            assert abs(out_clip.duration - input_total_duration) < 0.1
