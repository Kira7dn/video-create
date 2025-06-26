import argparse
import os
import json
import asyncio
import aiohttp
import aiofiles
import uuid
from typing import Optional
from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
    ColorClip,
    TextClip,
    CompositeAudioClip,
)
from pydub import AudioSegment
from gtts import gTTS
import shutil
from urllib.parse import urlparse
import logging

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
    concatenate_videos_with_sequence,
)
from exceptions import VideoCreationError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _download_file(session: aiohttp.ClientSession, url: str, dest_path: str):
    """Asynchronously downloads a file from a URL."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(await response.read())
        logger.info(f"Successfully downloaded {url} to {dest_path}")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to download {url}: {e}")
        raise VideoCreationError(f"Failed to download resource: {url}") from e


async def _generate_tts(text: str, lang: str, dest_path: str):
    """Asynchronously generates TTS audio and saves it."""
    try:
        # gTTS is not async, so we run it in a thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: gTTS(text=text, lang=lang).save(dest_path)
        )
        logger.info(f"Successfully generated TTS for '{text[:20]}...'")
    except Exception as e:
        logger.error(f"Failed to generate TTS: {e}")
        raise VideoCreationError("Failed to generate TTS audio") from e


async def _process_segment(
    session: aiohttp.ClientSession, segment: dict, temp_dir: str
) -> dict:
    """Processes a single video segment, downloading assets in parallel."""
    tasks = []
    download_map = {}

    # Collect download tasks for background images/videos
    if bg_image_url := segment.get("background_image"):
        ext = os.path.splitext(urlparse(bg_image_url).path)[1]
        img_path = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}{ext}")
        tasks.append(_download_file(session, bg_image_url, img_path))
        download_map["background_image"] = img_path

    # Collect download tasks for background music
    if bg_music_url := segment.get("background_music"):
        ext = os.path.splitext(urlparse(bg_music_url).path)[1]
        music_path = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}{ext}")
        tasks.append(_download_file(session, bg_music_url, music_path))
        download_map["background_music"] = music_path

    # Collect TTS generation tasks
    if tts_data := segment.get("tts"):
        tts_text = tts_data.get("text")
        tts_lang = tts_data.get("lang", "en")
        if tts_text:
            tts_path = os.path.join(temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
            tasks.append(_generate_tts(tts_text, tts_lang, tts_path))
            download_map["tts"] = tts_path

    # Run all download/TTS tasks concurrently
    await asyncio.gather(*tasks)

    # Update segment with local paths
    processed_segment = segment.copy()
    if "background_image" in download_map:
        processed_segment["background_image_path"] = download_map["background_image"]
    if "background_music" in download_map:
        processed_segment["background_music_path"] = download_map["background_music"]
    if "tts" in download_map:
        processed_segment["tts_path"] = download_map["tts"]

    return processed_segment


def _create_clip_from_segment(segment: dict, temp_dir: str) -> VideoFileClip:
    """Creates a video clip from a processed segment dictionary."""
    segment_type = segment.get("type")
    duration = segment.get("duration", 5)
    bg_image_path = segment.get("background_image_path")

    if not bg_image_path or not os.path.exists(bg_image_path):
        raise VideoCreationError(f"Background image not found for segment.")

    # Create base clip (image or video)
    clip = ImageClip(bg_image_path, duration=duration)

    # Add texts if any
    texts = segment.get("texts", [])
    text_clips = []
    if texts:
        for text_info in texts:
            txt_clip = (
                TextClip(
                    text_info["text"],
                    fontsize=text_info.get("fontsize", 24),
                    color=text_info.get("color", "white"),
                    font=text_info.get("font", "Arial"),
                )
                .with_position(text_info.get("position", ("center", "center")))
                .with_duration(duration)
            )
            text_clips.append(txt_clip)

    # Combine base clip with text clips
    final_clip = CompositeVideoClip([clip] + text_clips, size=clip.size)

    # Handle audio
    audio_clips = []
    if bg_music_path := segment.get("background_music_path"):
        audio_clips.append(AudioFileClip(bg_music_path))
    if tts_path := segment.get("tts_path"):
        audio_clips.append(AudioFileClip(tts_path))

    if audio_clips:
        # Combine audio clips and set to video
        composite_audio = CompositeAudioClip(audio_clips)
        final_clip = final_clip.with_audio(composite_audio.with_duration(duration))

    # Set FPS for consistency
    final_clip = final_clip.with_fps(24)

    # Write to a temporary file to stabilize it before concatenation
    segment_output_path = os.path.join(temp_dir, f"temp_segment_{segment_type}.mp4")
    export_final_video_clip(final_clip, segment_output_path)

    # Return a clip loaded from the stable file
    return VideoFileClip(segment_output_path)


async def create_video_from_json(
    json_data: list, transitions_override: Optional[str] = None
) -> str:
    """
    Main async function to create a video from a JSON structure.
    Manages temp directories, parallel downloads, and video processing.
    """
    video_id = uuid.uuid4().hex
    temp_dir = os.path.join("tmp_create_" + video_id)
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Phase 1: Download all assets concurrently
        async with aiohttp.ClientSession() as session:
            processing_tasks = [
                _process_segment(session, seg, temp_dir) for seg in json_data
            ]
            processed_segments = await asyncio.gather(*processing_tasks)

        # Phase 2: Create individual video clips from downloaded assets
        # This part is CPU-bound and should be run in an executor in a real-world scenario
        # For simplicity here, we run it sequentially after downloads.
        segment_clips = [
            _create_clip_from_segment(seg, temp_dir) for seg in processed_segments
        ]

        segment_paths = [clip.filename for clip in segment_clips]

        # Phase 3: Concatenate clips with transitions
        transitions_config = None
        if transitions_override:
            transitions_config = [{"type": transitions_override, "duration": 1.0}] * (
                len(segment_paths) - 1
            )

        final_video = concatenate_videos_with_sequence(
            segment_paths, transitions=transitions_config
        )

        # Phase 4: Export final video
        output_path = os.path.join(temp_dir, f"final_video_{video_id}.mp4")
        export_final_video_clip(final_video, output_path)

        # Close all file handles held by clips
        for clip in segment_clips:
            clip.close()
        if final_video:
            final_video.close()

        return output_path

    except Exception as e:
        logger.error(f"Video creation failed: {e}", exc_info=True)
        # Clean up on failure
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise VideoCreationError(f"Video creation failed: {e}") from e


def process_single_cut(data, tmp_dir, cut_id=None):
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    import uuid

    cut_id = cut_id or data.get("id") or str(uuid.uuid4())
    temp_files = []
    logger.info(f"[CUT {cut_id}] Start processing")
    try:
        # 1. Process images
        image_paths = [img["path"] for img in data["images"]]
        padded_images = process_images_with_padding(
            image_paths, target_size=(1280, 720), pad_color=(0, 0, 0)
        )
        # 2. Process audio
        voice_seg = load_audio_file(data["voice_over"])
        bgm_seg = load_audio_file(data["background_music"])
        bgm_seg = manage_audio_duration(bgm_seg, len(voice_seg))
        mixed_seg = mix_audio(voice_seg, bgm_seg, bgm_gain_when_voice=-15)
        temp_mixed_path = os.path.join(tmp_dir, f"temp_mixed_audio_{cut_id}.mp3")
        mixed_seg.export(temp_mixed_path, format="mp3")
        temp_files.append(temp_mixed_path)
        mixed_audio = AudioFileClip(temp_mixed_path)
        total_audio_duration_sec = mixed_audio.duration
        fps = 24
        # 3. Create video from images
        video_clip = create_raw_video_clip_from_images(
            padded_images, total_audio_duration_sec, fps
        )
        # 4. Merge audio and video
        merged_clip = merge_audio_with_video_clip(video_clip, mixed_audio)
        # 5. Export to temp video file
        temp_video_path = os.path.join(tmp_dir, f"temp_cut_{cut_id}.mp4")
        export_final_video_clip(
            merged_clip, temp_video_path, fps=fps, codec="libx264", audio_codec="aac"
        )
        logger.info(f"[CUT {cut_id}] Finished: {temp_video_path}")
        # Cleanup
        merged_clip.close()
        mixed_audio.close()
        video_clip.close()
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        return temp_video_path
    except Exception as e:
        logger.error(f"[CUT {cut_id}] Error: {e}")
        # Attempt cleanup on error
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Video creation pipeline supporting batch JSON array input."
    )
    parser.add_argument(
        "--input", required=True, help="Path to input JSON file (array of objects)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output MP4 video file (final concatenated video)",
    )
    parser.add_argument(
        "--transitions",
        default=None,
        help="Optional: JSON file or string specifying transitions between cuts",
    )
    parser.add_argument(
        "--tmp-dir",
        default="tmp_pipeline",
        help="Temp dir for downloads and intermediate files",
    )
    args = parser.parse_args()

    # Read and validate input JSON array
    logger.info("Reading and validating input JSON array...")
    with open(args.input, "r", encoding="utf-8") as f:
        try:
            data_array = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to parse input JSON: {e}")
    if not isinstance(data_array, list):
        raise ValueError("Input JSON must be an array of objects (batch mode)")
    if len(data_array) == 0:
        raise ValueError("Input JSON array is empty")
    logger.info(f"Loaded {len(data_array)} input objects.")

    # --- Download & replace URLs with local paths ---
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
        # Gather all URLs to download
        url_list = []
        for data in data_array:
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
        # Replace URLs with local paths
        data_array = [
            replace_url_with_local_path(data, url_to_local) for data in data_array
        ]
        # Process each cut
        logger.info("Processing each cut...")
        temp_video_paths = []
        cut_results = []
        per_cut_temp_files = []
        for idx, data in enumerate(data_array):
            cut_id = data.get("id") or f"cut{idx+1}"
            try:
                temp_video_path = process_single_cut(data, tmp_dir, cut_id)
                temp_video_paths.append(temp_video_path)
                per_cut_temp_files.append(temp_video_path)
                cut_results.append(
                    {
                        "id": cut_id,
                        "status": "success",
                        "video_path": temp_video_path,
                        "error": None,
                    }
                )
            except Exception as e:
                cut_results.append(
                    {
                        "id": cut_id,
                        "status": "error",
                        "video_path": None,
                        "error": str(e),
                    }
                )
        # Summary
        logger.info("Batch processing summary:")
        for res in cut_results:
            if res["status"] == "success":
                logger.info(f"  [CUT {res['id']}] OK")
            else:
                logger.error(f"  [CUT {res['id']}] ERROR: {res['error']}")
        # --- Concatenate video cuts ---
        logger.info("Concatenating video cuts...")
        valid_video_paths = [
            res["video_path"]
            for res in cut_results
            if res["status"] == "success" and res["video_path"]
        ]
        if not valid_video_paths:
            logger.error("No valid video cuts to concatenate. Exiting.")
            return
        transitions = None
        if args.transitions:
            if os.path.isfile(args.transitions):
                with open(args.transitions, "r", encoding="utf-8") as tf:
                    transitions = json.load(tf)
            else:
                try:
                    transitions = json.loads(args.transitions)
                except Exception:
                    transitions = args.transitions
        else:
            transitions = [
                obj.get("transition") for obj in data_array if "transition" in obj
            ]
        try:
            final_clip = concatenate_videos_with_sequence(
                valid_video_paths,
                transitions=transitions,
            )
            final_clip.write_videofile(
                args.output, codec="libx264", audio_codec="aac", logger=None
            )
            final_clip.close()
            logger.info(f"SUCCESS: Final video created at {args.output}")
        except Exception as e:
            logger.error(f"Failed to concatenate videos: {e}")
        # Cleanup temp video cuts
        for f in per_cut_temp_files:
            if os.path.exists(f):
                os.remove(f)
    finally:
        # Cleanup temp files
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        # Remove temp dir if empty
        if os.path.exists(tmp_dir) and not os.listdir(tmp_dir):
            os.rmdir(tmp_dir)
    logger.info("Batch pipeline finished.")


if __name__ == "__main__":
    main()
