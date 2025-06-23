import os
import json
import subprocess


def test_create_video_pipeline():
    # 1. Tạo file JSON input mẫu
    input_json = {
        "images": [
            {"path": "test/source/image/sample.jpg"},
            {"path": "test/source/image/sample.jpg"},
        ],
        "voice_over": "test/source/voice/voice2.mp3",
        "background_music": "test/source/bgm/bg1.mp3",
    }
    input_path = "test/test_input_create_video.json"
    output_path = "test/test_output_create_video.mp4"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(input_json, f)
    # 2. Xóa file output cũ nếu có
    if os.path.exists(output_path):
        os.remove(output_path)
    # 3. Gọi script create_video.py
    result = subprocess.run(
        ["python", "create_video.py", "--input", input_path, "--output", output_path],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(result.stderr)
    # 4. Kiểm tra file output
    assert (
        os.path.exists(output_path) and os.path.getsize(output_path) > 0
    ), "Output video not created!"
    print("Test passed: create_video.py pipeline works and output video is created.")


if __name__ == "__main__":
    test_create_video_pipeline()
