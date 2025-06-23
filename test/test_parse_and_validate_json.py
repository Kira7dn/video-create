import os
import tempfile
import json
import pytest
from utils.audio_utils import parse_and_validate_json


# Helper to create a temp file with content and return its path
def make_temp_file(content=b"test", suffix=".tmp"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def make_json_file(data):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def test_valid_json():
    img1 = make_temp_file()
    img2 = make_temp_file()
    voice = make_temp_file()
    music = make_temp_file()
    data = {
        "images": [{"path": img1}, {"path": img2}],
        "voice_over": voice,
        "background_music": music,
    }
    json_path = make_json_file(data)
    result = parse_and_validate_json(json_path)
    assert result["images"][0]["path"] == img1
    assert result["voice_over"] == voice
    assert result["background_music"] == music
    os.remove(img1)
    os.remove(img2)
    os.remove(voice)
    os.remove(music)
    os.remove(json_path)


def test_missing_key():
    data = {"images": [], "voice_over": "a.mp3"}  # missing background_music
    json_path = make_json_file(data)
    try:
        parse_and_validate_json(json_path)
        assert False, "Should raise ValueError for missing key"
    except ValueError as e:
        assert "background_music" in str(e)
    os.remove(json_path)


def test_wrong_type():
    data = {"images": "notalist", "voice_over": "a.mp3", "background_music": "b.wav"}
    json_path = make_json_file(data)
    try:
        parse_and_validate_json(json_path)
        assert False, "Should raise ValueError for images not a list"
    except ValueError as e:
        assert "'images' must be a list" in str(e)
    os.remove(json_path)


def test_nonexistent_file():
    data = {
        "images": [{"path": "notfound.jpg"}],
        "voice_over": "notfound.mp3",
        "background_music": "notfound.wav",
    }
    json_path = make_json_file(data)
    try:
        parse_and_validate_json(json_path)
        assert False, "Should raise FileNotFoundError for missing files"
    except FileNotFoundError as e:
        assert "does not exist" in str(e)
    os.remove(json_path)
