import argparse
import os
from utils.video_utils import concatenate_videos, concatenate_videos_with_sequence


def main():
    parser = argparse.ArgumentParser(
        description="Ghép các video .mp4 trong thư mục chỉ định với các tuỳ chọn chuyển cảnh."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=".",
        help="Thư mục chứa các file .mp4 để ghép (default: thư mục hiện tại)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_project_concat.mp4",
        help="Tên file video output",
    )
    parser.add_argument(
        "--transition",
        type=str,
        default=None,
        choices=[None, "crossfade", "fade", "fadeblack", "slideleft", "slideright"],
        help="Loại hiệu ứng chuyển cảnh áp dụng cho tất cả (nếu không dùng sequence)",
    )
    parser.add_argument(
        "--transition-duration",
        type=float,
        default=1.0,
        help="Thời lượng hiệu ứng chuyển cảnh (giây)",
    )
    parser.add_argument(
        "--sequence",
        type=str,
        default=None,
        help='Chuỗi hiệu ứng chuyển cảnh dạng JSON, ví dụ: \'[{"type": "crossfade", "duration": 1.0}, {"type": "slideleft", "duration": 1.0}]\'',
    )
    args = parser.parse_args()

    video_files = [
        os.path.join(args.input_dir, f)
        for f in sorted(os.listdir(args.input_dir))
        if f.endswith(".mp4") and os.path.isfile(os.path.join(args.input_dir, f))
    ]
    if len(video_files) < 2:
        print("Cần ít nhất 2 file video .mp4 để ghép!")
        return
    print(
        f"Ghép {len(video_files)} video trong {args.input_dir} thành {args.output}..."
    )
    if args.sequence:
        import json

        transitions = json.loads(args.sequence)
        concat_clip = concatenate_videos_with_sequence(video_files, transitions)
    elif args.transition:
        concat_clip = concatenate_videos(
            video_files,
            transition_type=args.transition,
            transition_duration=args.transition_duration,
        )
    else:
        concat_clip = concatenate_videos(video_files)
    concat_clip.write_videofile(args.output, fps=24, codec="libx264", audio_codec="aac")
    print(f"Đã xuất file: {args.output}")


if __name__ == "__main__":
    main()
