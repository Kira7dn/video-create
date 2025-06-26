import os
import glob
import cv2
from utils.video_utils import create_raw_video_clip_from_images


def test_raw_video_creation():
    # Lấy danh sách ảnh sample đã xử lý (padded)
    image_dir = "source/image/samples/"
    image_paths = sorted(glob.glob(f"{image_dir}/*_padded.jpg"))
    assert image_paths, f"No padded images found in {image_dir}"
    images = [cv2.imread(p) for p in image_paths]
    for idx, img in enumerate(images):
        assert img is not None, f"Image at {image_paths[idx]} could not be read"
    # Tổng thời lượng audio giả lập (giây)
    total_audio_duration_sec = 6
    fps = 24
    # Tạo video clip
    clip = create_raw_video_clip_from_images(images, total_audio_duration_sec, fps)
    # Kiểm tra duration
    assert (
        abs(clip.duration - total_audio_duration_sec) < 0.05
    ), f"Clip duration {clip.duration} != {total_audio_duration_sec}"
    # Kiểm tra số frame (concatenate_videoclips có thể làm tròn, nên cho phép lệch 1 frame)
    expected_frames = int(total_audio_duration_sec * fps)
    actual_frames = int(clip.duration * fps)
    assert (
        abs(actual_frames - expected_frames) <= 1
    ), f"Frame count {actual_frames} != {expected_frames}"
    # Xuất thử file video
    output_path = "test_output_raw_video.mp4"
    clip.write_videofile(output_path, fps=fps, codec="libx264")
    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Output video file not created or empty"
    print(f"Test passed: Raw video created at {output_path}")


if __name__ == "__main__":
    test_raw_video_creation()
