# video-create

A Python batch video creation pipeline supporting image/audio input (local or URL), batch processing, and robust temp file management.

## Features

- Batch processing: Accepts a JSON array of input objects, each describing a video cut.
- Supports local files and remote URLs for images and audio (auto-downloads URLs).
- Concatenates all cuts into a single final video, with optional transitions.
- Robust temp file management and cleanup.
- Detailed logging and error handling.

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the batch pipeline:

```bash
python create_video.py --input input_sample.json --output final_output.mp4 --tmp-dir tmp_pipeline
```

**Arguments:**

- `--input`: Path to input JSON file (array of objects, see below)
- `--output`: Path to output MP4 video file (final concatenated video)
- `--transitions`: (Optional) JSON file or string specifying transitions between cuts
- `--tmp-dir`: (Optional) Temp dir for downloads and intermediate files (default: `tmp_pipeline`)

## Input JSON Format (Simplified)

The input file must be a JSON array, where each object describes a video cut. Example:

```json
[
  {
    "id": "intro",
    "images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg"
    ],
    "voice_over": "https://example.com/voice.mp3",
    "background_music": "https://example.com/background.mp3",
    "transition": {
      "type": "fadeblack", 
      "duration": 1.0
    }
  }
]
```

**Key features:**
- **images**: Array of URL strings (auto-downloaded)
- **voice_over**: Direct URL string to audio file  
- **background_music**: Direct URL string to audio file
- **transition**: Optional transition configuration

For complete format documentation, see [SIMPLIFIED_FORMAT.md](SIMPLIFIED_FORMAT.md).
    "voice_over_is_url": true,
    "background_music": "https://example.com/music.mp3",
    "background_music_is_url": true
  }
  // ... more cuts ...
]
```

- For each image/audio, set `is_url` or `<key>_is_url` to `true` if the value is a remote URL.
- Local file paths are also supported (set `is_url: false` or omit the flag).

See `input_sample.json` for a full example.

## Output

- The script creates a single MP4 file containing all cuts, concatenated in order.
- Temp files and downloads are cleaned up automatically after processing.
- Logs are printed to the console for each step and error.

## Testing

Run the automated batch pipeline test:

```bash
pytest -v test/test_batch_pipeline.py
```

## Notes

- All remote files are downloaded to the temp directory before processing.
- If any cut fails, the error is logged and processing continues for other cuts.
- The script requires Python 3.8+ and ffmpeg (for MoviePy).

## Example

```bash
python create_video.py --input input_sample.json --output final_output.mp4
```

This will process all cuts in `input_sample.json` and produce `final_output.mp4`.
