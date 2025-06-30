# 📚 Video Creation API - API Documentation

## 🌟 Overview

Video Creation API cung cấp RESTful endpoints để tạo video từ hình ảnh và âm thanh. API hỗ trợ batch processing, nhiều định dạng media, và tích hợp dễ dàng.

## 🔗 Base URLs

```bash
# Development
http://localhost:8000

# Production
https://api.yourdomain.com

# API Documentation
https://api.yourdomain.com/docs
```

## 🛡️ Authentication

Hiện tại API không yêu cầu authentication, nhưng có rate limiting:

```
- General API: 10 requests/second
- Upload endpoints: 1 request/second
```

## 📋 API Endpoints

### 1. Health Check

Kiểm tra trạng thái service

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-06-30T10:00:00Z",
  "version": "1.0.0",
  "uptime": 3600,
  "memory_usage": "512MB",
  "disk_usage": "2GB"
}
```

**Status Codes:**
- `200`: Service healthy
- `503`: Service unhealthy

---

### 2. Create Video

Tạo video từ segments input

```http
POST /api/v1/video/create
Content-Type: application/json
```

#### Request Body Schema

```json
{
  "segments": [
    {
      "id": "string",                    // Unique identifier
      "images": ["string"],              // Array of image URLs/paths
      "voice_over": "string",            // Audio URL/path (optional)
      "background_music": "string",      // Background music URL/path (optional)
      "duration": 5.0,                   // Duration in seconds (optional)
      "transition": {                    // Transition effect (optional)
        "type": "fade|fadeblack|slide",
        "duration": 1.0
      }
    }
  ],
  "output_settings": {
    "format": "mp4",                     // Output format
    "quality": "high|medium|low",        // Video quality
    "fps": 24,                          // Frames per second
    "resolution": {                     // Video resolution
      "width": 1280,
      "height": 720
    }
  }
}
```

#### Example Request

```json
{
  "segments": [
    {
      "id": "intro",
      "images": [
        "https://example.com/intro1.jpg",
        "https://example.com/intro2.jpg"
      ],
      "voice_over": "https://example.com/intro-voice.mp3",
      "background_music": "https://example.com/bg-music.mp3",
      "duration": 8.0,
      "transition": {
        "type": "fade",
        "duration": 1.0
      }
    },
    {
      "id": "main",
      "images": [
        "https://example.com/main1.jpg",
        "https://example.com/main2.jpg",
        "https://example.com/main3.jpg"
      ],
      "voice_over": "https://example.com/main-voice.mp3",
      "duration": 12.0
    },
    {
      "id": "outro",
      "images": [
        "https://example.com/outro.jpg"
      ],
      "background_music": "https://example.com/outro-music.mp3",
      "duration": 5.0,
      "transition": {
        "type": "fadeblack",
        "duration": 2.0
      }
    }
  ],
  "output_settings": {
    "format": "mp4",
    "quality": "high",
    "fps": 30,
    "resolution": {
      "width": 1920,
      "height": 1080
    }
  }
}
```

#### Response

**Success (200):**
```json
{
  "success": true,
  "video_id": "video_123456789",
  "video_url": "https://api.yourdomain.com/output/video_123456789.mp4",
  "thumbnail_url": "https://api.yourdomain.com/output/video_123456789_thumb.jpg",
  "duration": 25.0,
  "file_size": 15728640,
  "processing_time": 45.2,
  "segments_processed": 3,
  "metadata": {
    "resolution": "1920x1080",
    "fps": 30,
    "format": "mp4",
    "codec": "h264"
  }
}
```

**Error (400):**
```json
{
  "success": false,
  "error": "Invalid input format",
  "details": {
    "field": "segments[0].images",
    "message": "At least one image is required per segment"
  }
}
```

**Error (422):**
```json
{
  "success": false,
  "error": "Processing failed",
  "details": {
    "segment_id": "intro",
    "message": "Failed to download image: https://example.com/missing.jpg"
  }
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (invalid input)
- `422`: Processing error
- `429`: Rate limit exceeded
- `500`: Internal server error

---

### 3. Get Video Status

Kiểm tra trạng thái video processing

```http
GET /api/v1/video/{video_id}/status
```

**Response:**
```json
{
  "video_id": "video_123456789",
  "status": "processing|completed|failed",
  "progress": 75,
  "estimated_time_remaining": 15,
  "created_at": "2025-06-30T10:00:00Z",
  "completed_at": "2025-06-30T10:01:30Z"
}
```

---

### 4. Download Video

Download video đã tạo

```http
GET /api/v1/video/{video_id}/download
```

**Response:**
- `200`: Video file (binary)
- `404`: Video not found
- `410`: Video expired/deleted

---

### 5. List Videos

Lấy danh sách videos đã tạo

```http
GET /api/v1/videos
```

**Query Parameters:**
- `limit`: Number of results (default: 10, max: 100)
- `offset`: Pagination offset (default: 0)
- `status`: Filter by status (processing|completed|failed)

**Response:**
```json
{
  "videos": [
    {
      "video_id": "video_123456789",
      "status": "completed",
      "duration": 25.0,
      "file_size": 15728640,
      "created_at": "2025-06-30T10:00:00Z",
      "video_url": "https://api.yourdomain.com/output/video_123456789.mp4"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

### 6. Delete Video

Xóa video

```http
DELETE /api/v1/video/{video_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Video deleted successfully"
}
```

---

## 🎛️ Input Formats

### Supported Image Formats
- **JPEG/JPG**: High quality photos
- **PNG**: Images with transparency
- **WebP**: Modern format with good compression
- **GIF**: Animated images (first frame used)

### Supported Audio Formats
- **MP3**: Most common format
- **WAV**: Uncompressed audio
- **AAC**: Modern audio codec
- **OGG**: Open source format

### Input Sources
- **URLs**: HTTP/HTTPS links to media files
- **Local files**: File paths (for server-side usage)
- **Base64**: Encoded media data (for small files)

---

## ⚙️ Configuration Options

### Video Quality Settings

```json
{
  "quality": "low",      // 480p, 1 Mbps
  "quality": "medium",   // 720p, 3 Mbps  
  "quality": "high",     // 1080p, 8 Mbps
  "quality": "ultra"     // 4K, 20 Mbps
}
```

### Transition Effects

```json
{
  "transition": {
    "type": "fade",        // Fade in/out
    "type": "fadeblack",   // Fade to black
    "type": "slide",       // Slide transition
    "type": "zoom",        // Zoom in/out
    "type": "dissolve",    // Cross dissolve
    "duration": 1.0        // Transition duration in seconds
  }
}
```

### Audio Settings

```json
{
  "audio_settings": {
    "voice_over_volume": 1.0,      // 0.0 to 2.0
    "background_music_volume": 0.3, // 0.0 to 2.0
    "fade_in": 1.0,                // Fade in duration
    "fade_out": 1.0                // Fade out duration
  }
}
```

---

## 🚨 Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "Error category",
  "message": "Human readable error message",
  "details": {
    "field": "Specific field that caused error",
    "code": "ERROR_CODE",
    "timestamp": "2025-06-30T10:00:00Z"
  }
}
```

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `INVALID_INPUT` | Invalid request format | Check request schema |
| `MISSING_MEDIA` | Media file not found | Verify URLs/paths |
| `PROCESSING_FAILED` | Video processing error | Check media formats |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait before retry |
| `INSUFFICIENT_STORAGE` | Not enough disk space | Contact administrator |
| `TIMEOUT` | Processing timeout | Reduce video complexity |

---

## 📊 Rate Limits

### Current Limits

| Endpoint | Rate Limit | Burst |
|----------|------------|--------|
| `/health` | No limit | - |
| `/api/v1/video/create` | 1/second | 5 requests |
| `/api/v1/video/{id}/*` | 10/second | 20 requests |
| `/api/v1/videos` | 10/second | 20 requests |

### Rate Limit Headers

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1625097600
```

---

## 🔍 Monitoring & Analytics

### Request Logging

All API requests are logged with:
- Request ID
- Client IP
- Endpoint
- Response time
- Status code
- Error details

### Metrics Available

- **Request rate**: Requests per second
- **Error rate**: Failed requests percentage
- **Processing time**: Average video creation time
- **Resource usage**: CPU, memory, disk usage

Access metrics at: `http://localhost:9090` (Prometheus)

---

## 🧪 Testing

### Health Check Test

```bash
curl -X GET https://api.yourdomain.com/health
```

### Simple Video Creation Test

```bash
curl -X POST https://api.yourdomain.com/api/v1/video/create \
  -H "Content-Type: application/json" \
  -d '{
    "segments": [
      {
        "id": "test",
        "images": ["https://picsum.photos/1280/720"],
        "duration": 3.0
      }
    ]
  }'
```

### Load Testing

```bash
# Using Apache Bench
ab -n 100 -c 10 https://api.yourdomain.com/health

# Using curl in loop
for i in {1..10}; do
  curl -X GET https://api.yourdomain.com/health &
done
wait
```

---

## 🔧 SDK Examples

### JavaScript SDK

```javascript
class VideoAPI {
  constructor(baseURL, options = {}) {
    this.baseURL = baseURL;
    this.timeout = options.timeout || 300000; // 5 minutes
  }

  async createVideo(segments, outputSettings = {}) {
    const payload = {
      segments,
      output_settings: outputSettings
    };

    const response = await fetch(`${this.baseURL}/api/v1/video/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`API Error: ${error.message}`);
    }

    return await response.json();
  }

  async getVideoStatus(videoId) {
    const response = await fetch(`${this.baseURL}/api/v1/video/${videoId}/status`);
    return await response.json();
  }

  async downloadVideo(videoId) {
    const response = await fetch(`${this.baseURL}/api/v1/video/${videoId}/download`);
    return response.blob();
  }
}

// Usage
const api = new VideoAPI('https://api.yourdomain.com');

const segments = [
  {
    id: 'intro',
    images: ['https://example.com/image.jpg'],
    voice_over: 'https://example.com/voice.mp3',
    duration: 5.0
  }
];

api.createVideo(segments)
  .then(result => console.log('Video created:', result))
  .catch(error => console.error('Error:', error));
```

### Python SDK

```python
import requests
import time
from typing import List, Dict, Optional

class VideoAPI:
    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def create_video(self, segments: List[Dict], output_settings: Optional[Dict] = None) -> Dict:
        """Create video from segments"""
        payload = {
            'segments': segments,
            'output_settings': output_settings or {}
        }
        
        response = self.session.post(
            f'{self.base_url}/api/v1/video/create',
            json=payload,
            timeout=self.timeout
        )
        
        if not response.ok:
            error_data = response.json()
            raise Exception(f"API Error: {error_data.get('message', 'Unknown error')}")
        
        return response.json()

    def get_video_status(self, video_id: str) -> Dict:
        """Get video processing status"""
        response = self.session.get(f'{self.base_url}/api/v1/video/{video_id}/status')
        return response.json()

    def download_video(self, video_id: str, output_path: str) -> None:
        """Download video to local file"""
        response = self.session.get(f'{self.base_url}/api/v1/video/{video_id}/download')
        
        with open(output_path, 'wb') as f:
            f.write(response.content)

    def wait_for_completion(self, video_id: str, poll_interval: int = 5) -> Dict:
        """Wait for video processing to complete"""
        while True:
            status = self.get_video_status(video_id)
            
            if status['status'] == 'completed':
                return status
            elif status['status'] == 'failed':
                raise Exception(f"Video processing failed: {status}")
            
            time.sleep(poll_interval)

# Usage
api = VideoAPI('https://api.yourdomain.com')

segments = [
    {
        'id': 'intro',
        'images': ['https://example.com/image.jpg'],
        'voice_over': 'https://example.com/voice.mp3',
        'duration': 5.0
    }
]

try:
    result = api.create_video(segments)
    print(f"Video created: {result['video_id']}")
    
    # Wait for completion
    final_status = api.wait_for_completion(result['video_id'])
    print(f"Video ready: {final_status['video_url']}")
    
    # Download video
    api.download_video(result['video_id'], 'output_video.mp4')
    print("Video downloaded successfully")
    
except Exception as e:
    print(f"Error: {e}")
```

---

## 🎯 Best Practices

### 1. Efficient API Usage

```javascript
// ✅ Good: Batch multiple segments
const segments = [segment1, segment2, segment3];
api.createVideo(segments);

// ❌ Bad: Multiple API calls
api.createVideo([segment1]);
api.createVideo([segment2]);
api.createVideo([segment3]);
```

### 2. Error Handling

```javascript
// ✅ Good: Comprehensive error handling
try {
  const result = await api.createVideo(segments);
  return result;
} catch (error) {
  if (error.status === 429) {
    // Rate limit - wait and retry
    await sleep(1000);
    return api.createVideo(segments);
  } else if (error.status === 422) {
    // Processing error - check input
    console.error('Input validation failed:', error.details);
  }
  throw error;
}
```

### 3. Resource Optimization

```javascript
// ✅ Good: Optimize image sizes
const optimizedSegments = segments.map(segment => ({
  ...segment,
  images: segment.images.map(url => `${url}?w=1280&h=720&q=80`)
}));
```

### 4. Caching

```javascript
// ✅ Good: Cache video results
const cache = new Map();

async function createVideoWithCache(segments) {
  const key = JSON.stringify(segments);
  
  if (cache.has(key)) {
    return cache.get(key);
  }
  
  const result = await api.createVideo(segments);
  cache.set(key, result);
  return result;
}
```

---

## 📞 Support

### API Support
- **Documentation**: https://api.yourdomain.com/docs
- **Status Page**: https://status.yourdomain.com
- **Rate Limits**: Check response headers

### Common Issues
1. **Timeout errors**: Reduce video complexity or increase timeout
2. **Rate limiting**: Implement exponential backoff
3. **Media not found**: Verify URLs are accessible
4. **Large files**: Use chunked upload for large media

### Contact
- **Technical Support**: support@yourdomain.com
- **API Issues**: api-support@yourdomain.com
- **Status Updates**: Follow @yourdomain_api

---

*Last updated: June 30, 2025*
