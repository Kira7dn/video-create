import os
import json
import re
import requests
import uuid


def is_url(path):
    """Check if a string is an HTTP/HTTPS URL."""
    return isinstance(path, str) and re.match(r"^https?://", path)


def parse_and_validate_json(json_path):
    """
    Load and validate the input JSON file for video creation.
    Raises ValueError or FileNotFoundError on invalid input.
    Returns the parsed dict if valid.
    Adds 'is_url' field to each image/audio if detected as URL.
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            raise ValueError(f"Invalid JSON format: {e}")

    # Required keys
    required_keys = ["images", "voice_over", "background_music"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key: {key}")

    # images must be a list of dicts with 'path' as string
    images = data["images"]
    if not isinstance(images, list):
        raise ValueError("'images' must be a list")
    for idx, img in enumerate(images):
        if (
            not isinstance(img, dict)
            or "path" not in img
            or not isinstance(img["path"], str)
        ):
            raise ValueError(
                f"Each image must be an object with a string 'path' (error at index {idx})"
            )
        img["is_url"] = is_url(img["path"])
        if not img["is_url"] and not os.path.exists(img["path"]):
            raise FileNotFoundError(f"Image file does not exist: {img['path']}")

    # Check voice_over and background_music
    for audio_key in ["voice_over", "background_music"]:
        if not isinstance(data[audio_key], str):
            raise ValueError(f"'{audio_key}' must be a string (file path)")
        data[f"{audio_key}_is_url"] = is_url(data[audio_key])
        if not data[f"{audio_key}_is_url"] and not os.path.exists(data[audio_key]):
            raise FileNotFoundError(
                f"{audio_key} file does not exist: {data[audio_key]}"
            )

    return data


def download_file_from_url(url, dest_dir, timeout=20):
    """
    Download a file from a URL to dest_dir. Returns the local file path.
    Raises exception on failure.
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1] or ""
    filename = f"download_{uuid.uuid4().hex}{ext}"
    local_path = os.path.join(dest_dir, filename)
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(f"Failed to download {url}: {e}")
    return local_path


def batch_download_urls(url_list, dest_dir, timeout=20):
    """
    Download multiple URLs. Returns a tuple: (list of local file paths or None if failed, list of error dicts).
    Each error dict: {"url": ..., "error": ...}
    The local_paths list preserves order: if a download fails, the corresponding entry is None.
    """
    local_paths = []
    errors = []
    for url in url_list:
        try:
            local_path = download_file_from_url(url, dest_dir, timeout=timeout)
            local_paths.append(local_path)
        except Exception as e:
            local_paths.append(None)
            errors.append({"url": url, "error": str(e)})
    return local_paths, errors


def replace_url_with_local_path(input_data, url_to_local):
    """
    Thay thế các path là URL trong input_data bằng path local đã download.
    input_data: dict (đã parse và validate)
    url_to_local: dict {url: local_path}
    Returns: input_data đã cập nhật
    """
    # Replace in images
    for img in input_data.get("images", []):
        if img.get("is_url") and img["path"] in url_to_local:
            img["path"] = url_to_local[img["path"]]
            img["is_url"] = False
    # Replace in audio
    for key in ["voice_over", "background_music"]:
        url_key = f"{key}_is_url"
        if input_data.get(url_key) and input_data[key] in url_to_local:
            input_data[key] = url_to_local[input_data[key]]
            input_data[url_key] = False
    return input_data


def validate_file_type_and_size(file_path, allowed_types=None, max_size_mb=50):
    """
    Kiểm tra file đã download có đúng định dạng và không vượt quá kích thước cho phép.
    allowed_types: list phần mở rộng (ví dụ: ['.jpg', '.png', '.mp3', '.mp4']) hoặc None (bỏ qua)
    max_size_mb: dung lượng tối đa (MB)
    Raises: ValueError nếu không hợp lệ
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File does not exist: {file_path}")
    # Check size
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"File {file_path} exceeds max size {max_size_mb} MB (actual: {size_mb:.2f} MB)"
        )
    # Check extension/type
    if allowed_types:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in allowed_types:
            raise ValueError(
                f"File {file_path} has invalid type: {ext}. Allowed: {allowed_types}"
            )
    return True


def batch_validate_files(file_paths, allowed_types=None, max_size_mb=50):
    """
    Validate multiple files, collect errors, and return a list of error dicts (do not raise immediately).
    Args:
        file_paths: list of file paths to validate
        allowed_types: list of allowed file extensions (e.g., ['.jpg', '.mp3'])
        max_size_mb: maximum allowed file size in MB
    Returns:
        List of error dicts: [{"file": ..., "error": ...}, ...]. Empty if all valid.
    """
    errors = []
    for file_path in file_paths:
        try:
            validate_file_type_and_size(file_path, allowed_types, max_size_mb)
        except Exception as e:
            errors.append({"file": file_path, "error": str(e)})
    return errors
