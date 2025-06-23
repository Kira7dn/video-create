import os
import glob
import cv2
import numpy as np
from moviepy.audio.io.AudioFileClip import AudioFileClip
from utils.video_utils import (
    create_raw_video_clip_from_images,
    merge_audio_with_video_clip,
    export_final_video_clip,
)
from utils.image_utils import process_images_with_padding
from utils.audio_utils import load_audio_file, mix_audio, manage_audio_duration
from moviepy.audio.io.AudioFileClip import AudioFileClip


def test_merge_audio_with_video_clip():
    # 1. Đọc ảnh gốc
    image_path = "test/source/image/sample.jpg"
    assert os.path.exists(image_path), f"Missing sample image: {image_path}"
    # 2. Sinh ra nhiều ảnh với các size khác nhau từ ảnh gốc
    sizes = [(1280, 720), (800, 600), (600, 600), (405, 720), (450, 600)]
    varied_image_paths = []
    os.makedirs("output", exist_ok=True)
    img = cv2.imread(image_path)
    for idx, size in enumerate(sizes):
        resized = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        path = f"output/varied_{idx}.jpg"
        cv2.imwrite(path, resized)
        varied_image_paths.append(path)

    # 3. Dùng process_images_with_padding để chuẩn hóa về 1280x720 (có padding, không méo)
    padded_images = process_images_with_padding(
        varied_image_paths, target_size=(1280, 720), pad_color=(0, 0, 0)
    )
    for idx, img in enumerate(padded_images):
        assert (
            img.shape[0] == 720 and img.shape[1] == 1280
        ), f"Padded image {idx} has wrong size: {img.shape}"
        cv2.imwrite(f"output/padded_{idx}.jpg", img)

    # 4. Lấy file audio mẫu
    audio_path = "test/source/voice/voice2.mp3"
    assert os.path.exists(audio_path), f"Audio file not found: {audio_path}"
    bgm_path = "test/source/bgm/bg1.mp3"
    assert os.path.exists(bgm_path), f"BGM file not found: {bgm_path}"
    # Dùng pipeline chuẩn hóa: load bằng pydub, mix, xuất file tạm, load lại bằng MoviePy
    voice_seg = load_audio_file(audio_path)
    bgm_seg = load_audio_file(bgm_path)
    # Lặp bgm cho đủ độ dài voice
    bgm_seg = manage_audio_duration(bgm_seg, len(voice_seg))
    # Mix voice + bgm (giảm volume bgm)
    mixed_seg = mix_audio(voice_seg, bgm_seg, bgm_gain_when_voice=-15)
    # Xuất ra file tạm
    temp_mixed_path = "test/temp_mixed_audio.mp3"
    mixed_seg.export(temp_mixed_path, format="mp3")
    # Load lại bằng MoviePy
    mixed_audio = AudioFileClip(temp_mixed_path)
    total_audio_duration_sec = mixed_audio.duration
    fps = 24
    # 5. Tạo video clip từ padded images
    video_clip = create_raw_video_clip_from_images(
        padded_images, total_audio_duration_sec, fps
    )
    # Merge audio đã mix vào video
    merged_clip = merge_audio_with_video_clip(video_clip, mixed_audio)
    # Kiểm tra thuộc tính audio
    assert (
        hasattr(merged_clip, "audio") and merged_clip.audio is not None
    ), "Merged clip does not have audio"
    # Kiểm tra duration
    assert (
        abs(merged_clip.duration - mixed_audio.duration) < 0.05
    ), f"Duration mismatch: {merged_clip.duration} vs {mixed_audio.duration}"
    # Xuất thử file video
    output_path = "test/test_output_merge_audio_video.mp4"
    export_final_video_clip(
        merged_clip, output_path, fps=fps, codec="libx264", audio_codec="aac"
    )
    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Output video file not created or empty"
    print(f"Test passed: Merged video with audio created at {output_path}")
    # Đóng clip để giải phóng tài nguyên
    merged_clip.close()
    mixed_audio.close()
    video_clip.close()
    # Xóa file tạm
    if os.path.exists(temp_mixed_path):
        os.remove(temp_mixed_path)


if __name__ == "__main__":
    test_merge_audio_with_video_clip()
