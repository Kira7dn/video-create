"""
Video creation service containing business logic for video processing
"""

import os
import json
import asyncio
import aiohttp
import aiofiles
import uuid
import logging
import shutil
import tempfile
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

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
import soundfile as sf
import numpy as np


from utils.audio_utils import (
    load_audio_file,
    mix_audio,
    manage_audio_duration,
    save_audio_to_file,
)
from utils.validation_utils import (
    parse_and_validate_json,
    is_url,
    batch_download_urls,
    replace_url_with_local_path,
    batch_validate_files,
)
from utils.image_utils import process_images_with_padding
from utils.video_utils import (
    create_raw_video_clip_from_images,
    merge_audio_with_video_clip,
    export_final_video_clip,
    concatenate_videos_with_sequence,
)
from app.core.exceptions import VideoCreationError

logger = logging.getLogger(__name__)


class VideoCreationService:
    """Service class for video creation operations"""

    def __init__(self):
        self.temp_files = []

    async def _download_file(
        self, session: aiohttp.ClientSession, url: str, dest_path: str
    ):
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

    async def _process_segment(
        self, session: aiohttp.ClientSession, segment: dict, temp_dir: str
    ) -> dict:
        """Processes a single video segment, downloading assets in parallel."""
        tasks = []
        download_map = {}

        # Support legacy/simplified format: if 'images' exists, use the first image as background_image
        if not segment.get("background_image") and segment.get("images"):
            images = segment["images"]
            if isinstance(images, list) and images:
                segment = segment.copy()
                segment["background_image"] = images[0]

        # Collect download tasks for background images/videos
        if bg_image_url := segment.get("background_image"):
            ext = os.path.splitext(urlparse(bg_image_url).path)[1]
            img_path = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}{ext}")
            tasks.append(self._download_file(session, bg_image_url, img_path))
            download_map["background_image"] = img_path

        # Collect download tasks for background music
        if bg_music_url := segment.get("background_music"):
            ext = os.path.splitext(urlparse(bg_music_url).path)[1]
            music_path = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}{ext}")
            tasks.append(self._download_file(session, bg_music_url, music_path))
            download_map["background_music"] = music_path

        # Collect download tasks for voice_over
        if voice_over_url := segment.get("voice_over"):
            ext = os.path.splitext(urlparse(voice_over_url).path)[1]
            voice_path = os.path.join(temp_dir, f"download_{uuid.uuid4().hex}{ext}")
            tasks.append(self._download_file(session, voice_over_url, voice_path))
            download_map["voice_over"] = voice_path

        # Run all download tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=False)

        # Update segment with local paths and determine duration
        processed_segment = segment.copy()
        if "background_image" in download_map:
            processed_segment["background_image_path"] = download_map[
                "background_image"
            ]
        if "background_music" in download_map:
            processed_segment["background_music_path"] = download_map[
                "background_music"
            ]
        if "voice_over" in download_map:
            processed_segment["voice_over_path"] = download_map["voice_over"]
            # ALWAYS get duration from voice_over - this is the primary audio content
            try:
                voice_clip = AudioFileClip(download_map["voice_over"])
                processed_segment["duration"] = voice_clip.duration
                voice_clip.close()
                logger.info(
                    f"Set segment duration from voice_over: {processed_segment['duration']:.2f}s"
                )
            except Exception as e:
                logger.warning(f"Failed to get duration from voice_over: {e}")
                processed_segment["duration"] = 5  # fallback
        else:
            # If no voice_over, use default duration
            processed_segment["duration"] = 5  # default duration
            logger.info("No voice_over found, using default segment duration: 5s")

        return processed_segment

    def _create_clip_from_segment(self, segment: dict, temp_dir: str) -> VideoFileClip:
        """Creates a video clip from a processed segment dictionary."""
        segment_type = segment.get("type")
        duration = segment["duration"]  # Duration is always set in _process_segment
        bg_image_path = segment.get("background_image_path")

        logger.info(f"Creating clip with duration: {duration:.2f}s")

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
                        font_size=text_info.get("fontsize", 24),
                        color=text_info.get("color", "white"),
                    )
                    .with_position(text_info.get("position", ("center", "center")))
                    .with_duration(duration)
                )
                text_clips.append(txt_clip)

        # Combine base clip with text clips
        final_clip = CompositeVideoClip([clip] + text_clips, size=clip.size)

        # Handle audio - trim/extend to match video duration
        audio_clips = []
        if bg_music_path := segment.get("background_music_path"):
            # Reduce background music volume using MultiplyVolume effect
            from moviepy.audio.fx.MultiplyVolume import MultiplyVolume

            bgm_clip = AudioFileClip(bg_music_path)
            # If background music is shorter than video, loop it
            if bgm_clip.duration < duration:
                bgm_clip = bgm_clip.with_duration(duration).with_fps(44100)
            else:
                # Trim to video duration
                bgm_clip = bgm_clip.with_duration(duration)

            # Reduce volume to 20%
            bgm_quiet = MultiplyVolume(factor=0.2).apply(bgm_clip)
            audio_clips.append(bgm_quiet)

        if voice_over_path := segment.get("voice_over_path"):
            voice_clip = AudioFileClip(voice_over_path)
            # Voice over determines the duration, don't trim it
            audio_clips.append(voice_clip)

        if audio_clips:
            # Combine audio clips and set to video
            composite_audio = CompositeAudioClip(audio_clips)
            final_clip = final_clip.with_audio(composite_audio)

        # Set FPS for consistency
        final_clip = final_clip.with_fps(24)

        # Use a unique identifier for the segment output filename
        segment_id = segment.get("id") or segment_type or str(uuid.uuid4())
        segment_output_path = os.path.join(temp_dir, f"temp_segment_{segment_id}.mp4")
        export_final_video_clip(final_clip, segment_output_path)

        # Return a clip loaded from the stable file
        return VideoFileClip(segment_output_path)

    async def create_video_from_json(self, json_data: list) -> str:
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
                    self._process_segment(session, seg, temp_dir) for seg in json_data
                ]
                processed_segments = await asyncio.gather(*processing_tasks)

            # Phase 2: Create individual video clips from downloaded assets
            segment_paths = []
            segment_clips = []
            segment_transitions = []
            for seg in processed_segments:
                transition = seg.get("transition")
                segment_transitions.append(transition)
                clip = self._create_clip_from_segment(seg, temp_dir)
                segment_clips.append(clip)
                segment_paths.append(
                    clip.filename if hasattr(clip, "filename") else None
                )
            segment_paths = [p for p in segment_paths if p is not None]

            # Phase 3: Concatenate clips with transitions

            final_video = concatenate_videos_with_sequence(
                segment_paths, transitions=segment_transitions
            )

            # Phase 4: Export final video
            output_path = os.path.join(temp_dir, f"final_video_{video_id}.mp4")
            export_final_video_clip(final_video, output_path)

            # Copy to final output location outside temp directory
            final_output_path = f"final_video_{video_id}.mp4"
            if os.path.exists(output_path):
                shutil.copy2(output_path, final_output_path)
                logger.info(f"✅ Copied video to final location: {final_output_path}")
            else:
                raise VideoCreationError(f"Output video not found: {output_path}")

            # Close all file handles held by clips
            for clip in segment_clips:
                clip.close()
            if final_video:
                final_video.close()

            return final_output_path

        except Exception as e:
            logger.error(f"Video creation failed: {e}", exc_info=True)
            # Clean up on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise VideoCreationError(f"Video creation failed: {e}") from e
        finally:
            # Always cleanup temp directory after processing
            # We delay cleanup a bit to ensure file handles are closed
            import time
            import gc

            # Force garbage collection to ensure all file handles are closed
            gc.collect()
            time.sleep(1.0)  # Longer delay to ensure file handles are released

            # Retry cleanup with multiple attempts
            cleanup_attempts = 3
            for attempt in range(cleanup_attempts):
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")
                        break
                    else:
                        logger.info(f"⚠️ Temp directory already removed: {temp_dir}")
                        break
                except Exception as cleanup_error:
                    if attempt < cleanup_attempts - 1:
                        logger.warning(
                            f"⚠️ Cleanup attempt {attempt + 1} failed for {temp_dir}: {cleanup_error}"
                        )
                        time.sleep(2.0)  # Wait before retry
                    else:
                        logger.warning(
                            f"❌ Final cleanup attempt failed for {temp_dir}: {cleanup_error}"
                        )

    # def process_single_cut(
    #     self, data: dict, tmp_dir: str, cut_id: Optional[str] = None
    # ) -> str:
    #     """Process a single video cut from data"""
    #     cut_id = cut_id or data.get("id") or str(uuid.uuid4())
    #     temp_files = []
    #     logger.info(f"[CUT {cut_id}] Start processing")

    #     try:
    #         # 1. Process images
    #         image_paths = [img["path"] for img in data["images"]]
    #         padded_images = process_images_with_padding(
    #             image_paths, target_size=(1280, 720), pad_color=(0, 0, 0)
    #         )

    #         # 2. Process audio
    #         voice_seg = load_audio_file(data["voice_over"])
    #         bgm_seg = load_audio_file(data["background_music"])
    #         bgm_seg = manage_audio_duration(bgm_seg, voice_seg["duration_ms"])
    #         mixed_seg = mix_audio(voice_seg, bgm_seg, bgm_gain_when_voice=-15)

    #         temp_mixed_path = os.path.join(tmp_dir, f"temp_mixed_audio_{cut_id}.mp3")
    #         save_audio_to_file(mixed_seg, temp_mixed_path, format="mp3")
    #         temp_files.append(temp_mixed_path)

    #         mixed_audio = AudioFileClip(temp_mixed_path)
    #         total_audio_duration_sec = mixed_audio.duration
    #         fps = 24

    #         # 3. Create video from images
    #         video_clip = create_raw_video_clip_from_images(
    #             padded_images, total_audio_duration_sec, fps
    #         )

    #         # 4. Merge audio and video
    #         merged_clip = merge_audio_with_video_clip(video_clip, mixed_audio)

    #         # 5. Export to temp video file
    #         temp_video_path = os.path.join(tmp_dir, f"temp_cut_{cut_id}.mp4")
    #         export_final_video_clip(
    #             merged_clip,
    #             temp_video_path,
    #             fps=fps,
    #             codec="libx264",
    #             audio_codec="aac",
    #         )
    #         logger.info(f"[CUT {cut_id}] Finished: {temp_video_path}")

    #         # Cleanup
    #         merged_clip.close()
    #         mixed_audio.close()
    #         video_clip.close()
    #         for f in temp_files:
    #             if os.path.exists(f):
    #                 os.remove(f)

    #         return temp_video_path

    #     except Exception as e:
    #         logger.error(f"[CUT {cut_id}] Error: {e}")
    #         # Attempt cleanup on error
    #         for f in temp_files:
    #             if os.path.exists(f):
    #                 os.remove(f)
    #         raise VideoCreationError(f"Failed to process cut {cut_id}: {e}") from e

    async def process_batch_video_creation(
        self,
        data_array: List[Dict[Any, Any]],
        transitions: Optional[Any] = None,
        tmp_dir: str = "tmp_pipeline",
        batch_uuid: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Process batch video creation from array of data (dùng lại logic như /create, đồng bộ uuid)"""
        os.makedirs(tmp_dir, exist_ok=True)
        cut_results = []
        segment_paths = []
        segment_clips = []
        temp_files = []
        try:
            # Phase 1: Download all assets concurrently cho từng segment
            async with aiohttp.ClientSession() as session:
                processing_tasks = [
                    self._process_segment(session, seg, tmp_dir) for seg in data_array
                ]
                processed_segments = await asyncio.gather(*processing_tasks)

            # Log temp_dir contents after segment processing
            logger.info(
                f"[BATCH] temp_dir contents after segment processing: {os.listdir(tmp_dir)}"
            )

            # Phase 2: Tạo từng video clip từ asset đã tải
            for idx, seg in enumerate(processed_segments):
                cut_id = seg.get("id") or f"cut{idx+1}"
                try:
                    clip = self._create_clip_from_segment(seg, tmp_dir)
                    segment_clips.append(clip)
                    segment_paths.append(
                        clip.filename if hasattr(clip, "filename") else None
                    )
                    cut_results.append(
                        {
                            "id": cut_id,
                            "status": "success",
                            "video_path": (
                                clip.filename if hasattr(clip, "filename") else None
                            ),
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

            segment_paths = [p for p in segment_paths if p is not None]

            # Phase 3: Concatenate clips with transitions
            transitions_config = None
            if transitions is None:
                transitions = [
                    obj.get("transition") for obj in data_array if "transition" in obj
                ]

            logger.info(f"[BATCH] segment_paths: {segment_paths}")
            logger.info(f"[BATCH] transitions: {transitions}")
            # Dùng batch_uuid cho tên file output nếu có
            if batch_uuid:
                output_filename = f"final_batch_video_{batch_uuid}.mp4"
            else:
                output_filename = f"final_batch_video_{uuid.uuid4().hex}.mp4"
            output_path = os.path.join(tmp_dir, output_filename)
            logger.info(f"[BATCH] Sẽ ghi file output: {output_path}")
            final_clip = concatenate_videos_with_sequence(
                segment_paths, transitions=transitions
            )
            logger.info(f"[BATCH] final_clip: {final_clip}")
            try:
                final_clip.write_videofile(
                    output_path, codec="libx264", audio_codec="aac", logger=None
                )
            except Exception as e:
                logger.error(f"[BATCH] Lỗi khi ghi file video: {e}")
                raise VideoCreationError(f"Failed to write batch video: {e}")
            finally:
                final_clip.close()

            # Log temp_dir contents after final video export
            logger.info(
                f"[BATCH] temp_dir contents after final video export: {os.listdir(tmp_dir)}"
            )

            logger.info(f"SUCCESS: Final video created at {output_path}")
            if not os.path.exists(output_path):
                logger.error(f"[BATCH] File output KHÔNG tồn tại: {output_path}")
                raise VideoCreationError(f"Batch output file not found: {output_path}")

            # Copy to final output location outside temp directory
            final_output_path = output_filename  # Remove tmp_dir path
            if os.path.exists(output_path):
                shutil.copy2(output_path, final_output_path)
                logger.info(
                    f"✅ Copied batch video to final location: {final_output_path}"
                )
            else:
                raise VideoCreationError(f"Batch output video not found: {output_path}")

            # Cleanup temp video cuts
            for clip in segment_clips:
                clip.close()

            return final_output_path, cut_results

        except Exception as e:
            logger.error(f"Batch video creation failed: {e}")
            raise VideoCreationError(f"Batch video creation failed: {e}") from e
        finally:
            # Cleanup temp files
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)

            # Always cleanup temp directory after processing
            import time
            import gc

            # Force garbage collection to ensure all file handles are closed
            gc.collect()
            time.sleep(1.0)  # Longer delay to ensure file handles are released

            # Retry cleanup with multiple attempts
            cleanup_attempts = 3
            for attempt in range(cleanup_attempts):
                try:
                    if os.path.exists(tmp_dir):
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                        logger.info(
                            f"✅ Cleaned up batch temporary directory: {tmp_dir}"
                        )
                        break
                    else:
                        logger.info(
                            f"⚠️ Batch temp directory already removed: {tmp_dir}"
                        )
                        break
                except Exception as cleanup_error:
                    if attempt < cleanup_attempts - 1:
                        logger.warning(
                            f"⚠️ Batch cleanup attempt {attempt + 1} failed for {tmp_dir}: {cleanup_error}"
                        )
                        time.sleep(2.0)  # Wait before retry
                    else:
                        logger.warning(
                            f"❌ Final batch cleanup attempt failed for {tmp_dir}: {cleanup_error}"
                        )

    def cleanup_temp_directory(self, temp_dir: str):
        """Clean up temporary directory with Windows-specific handling"""
        import time
        import gc
        import platform

        try:
            if not os.path.exists(temp_dir):
                logger.info(f"⚠️ Temp directory not found for cleanup: {temp_dir}")
                return

            # Force garbage collection to release file handles
            gc.collect()

            # Windows-specific handling with retries
            if platform.system() == "Windows":
                cleanup_attempts = 5
                for attempt in range(cleanup_attempts):
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")
                        return
                    except PermissionError as e:
                        if attempt < cleanup_attempts - 1:
                            logger.warning(
                                f"⚠️ Temp directory cleanup attempt {attempt + 1} failed, retrying in 3s: {e}"
                            )
                            time.sleep(3.0)
                            gc.collect()
                        else:
                            logger.warning(
                                f"❌ Failed to cleanup temp directory {temp_dir} after {cleanup_attempts} attempts: {e}"
                            )
                            # Fallback: try to remove individual files
                            try:
                                for root, dirs, files in os.walk(
                                    temp_dir, topdown=False
                                ):
                                    for file in files:
                                        try:
                                            os.remove(os.path.join(root, file))
                                        except:
                                            pass
                                    for dir_name in dirs:
                                        try:
                                            os.rmdir(os.path.join(root, dir_name))
                                        except:
                                            pass
                                os.rmdir(temp_dir)
                                logger.info(
                                    f"✅ Cleaned up temporary directory (fallback): {temp_dir}"
                                )
                            except Exception as fallback_error:
                                logger.warning(
                                    f"❌ Fallback cleanup also failed for {temp_dir}: {fallback_error}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"❌ Unexpected error during temp directory cleanup: {e}"
                        )
                        break
            else:
                # Non-Windows systems
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")

        except Exception as e:
            logger.warning(f"❌ Failed to clean up temp directory {temp_dir}: {e}")


# Global service instance
video_service = VideoCreationService()
