# Video Creation API - Simplified JSON Format

## Định dạng JSON được hỗ trợ (Chỉ format mới)

API chỉ hỗ trợ định dạng JSON đơn giản sau:

```json
[
  {
    "id": "unique_cut_id",
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

## Đặc điểm của định dạng mới:

### 1. **Images (Bắt buộc)**
- Là array chứa các URL string trực tiếp
- Tự động detect và download URLs
- Hỗ trợ các định dạng: JPG, PNG, WebP, GIF

### 2. **Voice Over (Tùy chọn)**
- URL string trực tiếp đến file audio
- Tự động detect và download nếu là URL
- Hỗ trợ: MP3, WAV, M4A

### 3. **Background Music (Tùy chọn)**
- URL string trực tiếp đến file audio
- Tự động detect và download nếu là URL
- Hỗ trợ: MP3, WAV, M4A

### 4. **Transition (Tùy chọn)**
- Object chứa thông tin chuyển cảnh
- `type`: loại transition (fadeblack, crossfade, etc.)
- `duration`: thời gian transition (giây)

## Ví dụ hoàn chỉnh:

```json
[
  {
    "id": "intro",
    "images": [
      "https://media.istockphoto.com/photo/nature-landscape.jpg"
    ],
    "voice_over": "https://cdn.pixabay.com/audio/voice-intro.mp3",
    "background_music": "https://cdn.pixabay.com/audio/bg-music.mp3",
    "transition": {
      "type": "fadeblack",
      "duration": 1.0
    }
  },
  {
    "id": "main_content",
    "images": [
      "https://example.com/content1.jpg",
      "https://example.com/content2.jpg"
    ],
    "voice_over": "https://example.com/main-voice.mp3",
    "background_music": "https://example.com/main-bg.mp3"
  }
]
```

## Lưu ý:

1. **URL Detection**: API tự động nhận diện và download các URL bắt đầu với `http://` hoặc `https://`
2. **Local Files**: Cũng có thể sử dụng đường dẫn local thay vì URL
3. **Backward Compatibility**: Định dạng cũ với `is_url` flags đã bị loại bỏ để đơn giản hóa
4. **Validation**: Tất cả URLs phải accessible và downloadable
5. **Cleanup**: Files tạm sẽ được tự động xóa sau khi tạo video

## API Endpoint:

```
POST /api/create-video
Content-Type: multipart/form-data

Parameters:
- input_json: File JSON với định dạng như trên
- transitions: (Optional) Override transitions config

Response: Video MP4 file
```
