import argparse
import os
from utils.audio_utils import (
    load_audio_file,
    mix_audio,
    manage_audio_duration,
)
from utils.validation_utils import parse_and_validate_json
from utils.image_utils import process_images_with_padding
from utils.video_utils import (
    create_raw_video_clip_from_images,
    merge_audio_with_video_clip,
    export_final_video_clip,
)
from moviepy.audio.io.AudioFileClip import AudioFileClip
import cv2


def main():
    parser = argparse.ArgumentParser(
        description="Video creation pipeline from JSON input."
    )
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--output", required=True, help="Path to output MP4 video file")
    parser.add_argument(
        "--tmp-dir", default="tmp_pipeline", help="Temp dir for downloads"
    )
    args = parser.parse_args()

    print("[1] Đọc và validate JSON...")
    data = parse_and_validate_json(args.input)

    # --- Bổ sung: Download & replace URL bằng local path ---
    from utils.validation_utils import (
        is_url,
        batch_download_urls,
        replace_url_with_local_path,
        batch_validate_files,
    )
    import tempfile

    tmp_dir = args.tmp_dir
    os.makedirs(tmp_dir, exist_ok=True)
    temp_files = []
    url_to_local = {}
    try:
        # Gom tất cả URL cần download
        url_list = []
        for img in data["images"]:
            if img.get("is_url"):
                url_list.append(img["path"])
        for key in ["voice_over", "background_music"]:
            if data.get(f"{key}_is_url"):
                url_list.append(data[key])
        # Download
        if url_list:
            local_paths, download_errors = batch_download_urls(url_list, tmp_dir)
            for url, local in zip(url_list, local_paths):
                if local:
                    url_to_local[url] = local
                    temp_files.append(local)
            if download_errors:
                raise RuntimeError(f"Download errors: {download_errors}")
        # Replace URL bằng local path
        data = replace_url_with_local_path(data, url_to_local)
        # Validate file type/size nếu muốn (ví dụ: batch_validate_files)
        # ...
        # Tiếp tục pipeline như cũ
        print("[2] Xử lý ảnh...")
        image_paths = [img["path"] for img in data["images"]]
        padded_images = process_images_with_padding(
            image_paths, target_size=(1280, 720), pad_color=(0, 0, 0)
        )
        for idx, img in enumerate(padded_images):
            assert (
                img.shape[0] == 720 and img.shape[1] == 1280
            ), f"Image {idx} has wrong size: {img.shape}"

        print("[3] Xử lý audio (mix voice + bgm)...")
        voice_seg = load_audio_file(data["voice_over"])
        bgm_seg = load_audio_file(data["background_music"])
        bgm_seg = manage_audio_duration(bgm_seg, len(voice_seg))
        mixed_seg = mix_audio(voice_seg, bgm_seg, bgm_gain_when_voice=-15)
        temp_mixed_path = os.path.join(tmp_dir, "temp_mixed_audio.mp3")
        mixed_seg.export(temp_mixed_path, format="mp3")
        temp_files.append(temp_mixed_path)
        mixed_audio = AudioFileClip(temp_mixed_path)
        total_audio_duration_sec = mixed_audio.duration
        fps = 24

        print("[4] Tạo video từ ảnh...")
        video_clip = create_raw_video_clip_from_images(
            padded_images, total_audio_duration_sec, fps
        )

        print("[5] Merge audio vào video...")
        merged_clip = merge_audio_with_video_clip(video_clip, mixed_audio)

        print(f"[6] Export video ra file: {args.output}")
        export_final_video_clip(
            merged_clip, args.output, fps=fps, codec="libx264", audio_codec="aac"
        )

        print("[7] Hoàn tất! Video đã được tạo.")
        merged_clip.close()
        mixed_audio.close()
        video_clip.close()
    finally:
        # Cleanup file tạm
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        # Cleanup thư mục tạm nếu rỗng
        if os.path.exists(tmp_dir) and not os.listdir(tmp_dir):
            os.rmdir(tmp_dir)


if __name__ == "__main__":
    main()
