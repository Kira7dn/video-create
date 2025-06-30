# 🎬 Video Creation API - Hướng dẫn sử dụng

## 📖 Tổng quan

Video Creation API là một hệ thống tạo video từ hình ảnh và âm thanh, hỗ trợ batch processing và tích hợp dễ dàng với các ứng dụng khác.

## 🚀 Bắt đầu nhanh

### 1. Chuẩn bị môi trường

```bash
# Clone repository
git clone <your-repository-url>
cd video-create

# Cài đặt Docker và Docker Compose
# Windows: Download từ https://docker.com/get-started
# Linux: sudo apt install docker.io docker-compose
# macOS: brew install docker docker-compose
```

### 2. Thiết lập ban đầu

```bash
# Tạo thư mục cần thiết
# Windows:
setup-directories.bat

# Linux/macOS:
chmod +x setup-directories.sh
./setup-directories.sh

# Tạo file cấu hình
cp .env.template .env
```

### 3. Chỉnh sửa cấu hình

Mở file `.env` và chỉnh sửa:

```bash
# Cho Development
DEBUG=true
LOG_LEVEL=DEBUG
DOMAIN=localhost
SSL_ENABLED=false

# Cho Production
DEBUG=false
LOG_LEVEL=INFO
DOMAIN=api.yourdomain.com
SSL_ENABLED=true
```

### 4. Khởi chạy

```bash
# Development (khuyên dùng)
make dev

# Hoặc Production
make prod
```

## 🛠️ Các môi trường triển khai

### 🔧 Development Environment

**Dành cho:** Phát triển, debug, testing

```bash
# Khởi chạy
make dev

# Hoặc command đầy đủ
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

**Features:**
- ✅ Hot reload (code thay đổi tự động restart)
- ✅ Debug logs chi tiết
- ✅ Redis cache server
- ✅ MinIO object storage
- ✅ Tài nguyên thấp (1GB RAM)

**Truy cập:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Redis: localhost:6379
- MinIO Console: http://localhost:9001

### 🏭 Production Environment

**Dành cho:** Triển khai thực tế, production

```bash
# Khởi chạy
make prod

# Hoặc với script deployment
make deploy-prod
```

**Features:**
- ✅ Nginx reverse proxy
- ✅ SSL/TLS support
- ✅ Prometheus monitoring
- ✅ Tài nguyên cao (4GB RAM)
- ✅ Rate limiting
- ✅ Log rotation

**Truy cập:**
- API: https://yourdomain.com
- Monitoring: http://localhost:9090

## 📡 API Usage

### 🔗 Endpoints chính

#### 1. Health Check
```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-06-30T10:00:00Z",
  "version": "1.0.0"
}
```

#### 2. Tạo Video
```bash
POST /api/v1/video/create
Content-Type: application/json
```

**Request Body:**
```json
{
  "segments": [
    {
      "id": "intro",
      "images": [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg"
      ],
      "voice_over": "https://example.com/voice.mp3",
      "background_music": "https://example.com/music.mp3",
      "transition": {
        "type": "fade",
        "duration": 1.0
      }
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "video_url": "https://yourdomain.com/output/video_123.mp4",
  "duration": 30.5,
  "processing_time": 45.2
}
```

### 🌐 Client Examples

#### JavaScript/TypeScript
```javascript
const API_BASE_URL = 'https://api.yourdomain.com';

async function createVideo(videoData) {
  const response = await fetch(`${API_BASE_URL}/api/v1/video/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(videoData)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}

// Usage
const videoData = {
  segments: [
    {
      id: "intro",
      images: ["https://example.com/image1.jpg"],
      voice_over: "https://example.com/voice.mp3"
    }
  ]
};

createVideo(videoData)
  .then(result => console.log('Video created:', result))
  .catch(error => console.error('Error:', error));
```

#### Python
```python
import requests
import json

API_BASE_URL = 'https://api.yourdomain.com'

def create_video(video_data):
    response = requests.post(
        f'{API_BASE_URL}/api/v1/video/create',
        json=video_data,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code != 200:
        raise Exception(f'HTTP error! status: {response.status_code}')
    
    return response.json()

# Usage
video_data = {
    "segments": [
        {
            "id": "intro",
            "images": ["https://example.com/image1.jpg"],
            "voice_over": "https://example.com/voice.mp3"
        }
    ]
}

try:
    result = create_video(video_data)
    print('Video created:', result)
except Exception as e:
    print('Error:', e)
```

#### cURL
```bash
curl -X POST https://api.yourdomain.com/api/v1/video/create \
  -H "Content-Type: application/json" \
  -d '{
    "segments": [
      {
        "id": "intro",
        "images": ["https://example.com/image1.jpg"],
        "voice_over": "https://example.com/voice.mp3"
      }
    ]
  }'
```

## 🔧 Configuration

### Environment Variables

#### 🌍 Domain & SSL
```bash
# Production domain
DOMAIN=api.yourdomain.com
API_BASE_URL=https://api.yourdomain.com
SSL_ENABLED=true

# Development
DOMAIN=localhost
API_BASE_URL=http://localhost:8000
SSL_ENABLED=false
```

#### 🎬 Video Processing
```bash
# Video settings
DEFAULT_VIDEO_FPS=24
DEFAULT_VIDEO_CODEC=libx264
DEFAULT_AUDIO_CODEC=aac
DEFAULT_RESOLUTION_WIDTH=1280
DEFAULT_RESOLUTION_HEIGHT=720

# Performance
MAX_WORKERS=1
MEMORY_LIMIT=2G
MOVIEPY_TEMP_DIR=/app/tmp
```

#### 🔒 Security
```bash
# File upload limits
MAX_FILE_SIZE=104857600  # 100MB
UPLOAD_TIMEOUT=300       # 5 minutes

# CORS
CORS_ORIGINS=http://localhost:3000,https://yourfrontend.com

# Request limits
REQUEST_TIMEOUT=300      # 5 minutes
```

#### 📊 Monitoring
```bash
# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
DEBUG=false

# Prometheus
PROMETHEUS_RETENTION=200h

# Nginx
NGINX_MAX_BODY_SIZE=100m
```

## 🚀 Triển khai Production

### 1. Chuẩn bị Server

```bash
# Cài đặt Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Cài đặt Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Cấu hình Domain

```bash
# Cập nhật DNS A record
# yourdomain.com -> YOUR_SERVER_IP
# api.yourdomain.com -> YOUR_SERVER_IP
```

### 3. Cấu hình Firewall

```bash
# Cho phép HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

### 4. Deploy

```bash
# Tự động deployment
make deploy-prod

# Hoặc manual
export DOMAIN=api.yourdomain.com
export SSL_ENABLED=true
make prod-env
```

### 5. SSL Certificate

```bash
# Sử dụng Let's Encrypt
sudo docker run --rm -v $(pwd)/nginx/ssl:/etc/letsencrypt \
  certbot/certbot certonly --standalone -d api.yourdomain.com

# Hoặc upload certificate của bạn vào nginx/ssl/
```

## 📊 Monitoring & Logging

### Health Monitoring

```bash
# Check service health
curl https://api.yourdomain.com/health

# Check via command
make health
```

### Logs

```bash
# View real-time logs
make logs

# View specific service
docker-compose logs -f video

# View last 100 lines
docker-compose logs --tail=100
```

### Resource Usage

```bash
# Check resource usage
make stats

# View detailed stats
docker stats cont_video cont_nginx_prod
```

### Prometheus Metrics

Access: http://localhost:9090

**Key metrics:**
- API response times
- Memory usage
- CPU usage
- Request rates
- Error rates

## 🔧 Maintenance

### Regular Tasks

```bash
# Restart services
make restart

# Update images
docker-compose pull
make build

# Backup data
make backup

# Clean up old containers/images
make clean
```

### Log Rotation

Logs automatically rotate:
- Max file size: 10MB
- Max files: 3
- Total log storage: ~30MB per service

### SSL Certificate Renewal

```bash
# Renew Let's Encrypt certificate
docker run --rm -v $(pwd)/nginx/ssl:/etc/letsencrypt \
  certbot/certbot renew

# Restart nginx
docker-compose restart nginx
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Service không start
```bash
# Check logs
make logs

# Check resource usage
make stats

# Increase memory limit
# Edit docker-compose.yml: memory: 4G
```

#### 2. API không truy cập được
```bash
# Check firewall
sudo ufw status

# Check port binding
netstat -tulpn | grep :8000

# Check DNS
nslookup api.yourdomain.com
```

#### 3. SSL certificate issues
```bash
# Check certificate validity
openssl x509 -in nginx/ssl/cert.pem -text -noout

# Regenerate self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem
```

#### 4. Out of memory
```bash
# Check memory usage
free -h
docker stats

# Increase system memory or reduce workers
# Edit .env: MAX_WORKERS=1, MEMORY_LIMIT=1G
```

#### 5. Video processing fails
```bash
# Check FFmpeg
docker-compose exec video ffmpeg -version

# Check temp directory
docker-compose exec video ls -la /app/tmp

# Clear temp files
docker-compose exec video rm -rf /app/tmp/*
```

### Debug Mode

```bash
# Enable debug logging
# Edit .env:
DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
make restart

# View debug logs
make logs
```

## 📋 Best Practices

### Security
- ✅ Use HTTPS in production
- ✅ Regular security updates
- ✅ Secure environment variables
- ✅ Firewall configuration
- ✅ Rate limiting enabled

### Performance
- ✅ Use single worker for video processing
- ✅ Monitor memory usage
- ✅ Regular cleanup of temp files
- ✅ Use appropriate resource limits

### Reliability
- ✅ Health checks configured
- ✅ Automatic restart policies
- ✅ Regular backups
- ✅ Monitoring and alerting

### Development
- ✅ Use development environment for coding
- ✅ Test in staging before production
- ✅ Version control for configurations
- ✅ Document API changes

## 🆘 Support

### Getting Help

1. **Check logs**: `make logs`
2. **Verify health**: `make health`
3. **Check resources**: `make stats`
4. **Review configuration**: `cat .env`

### Common Commands

```bash
# Quick diagnosis
make info

# Full system check
make health && make stats

# Emergency restart
make down && make up

# Complete reset
make clean && make setup && make up
```

### Resources

- **Documentation**: This file
- **API Docs**: http://localhost:8000/docs
- **Docker Compose**: https://docs.docker.com/compose/
- **FastAPI**: https://fastapi.tiangolo.com/
- **MoviePy**: https://zulko.github.io/moviepy/

---

## 🎉 Conclusion

Video Creation API cung cấp một giải pháp hoàn chỉnh cho việc tạo video tự động. Với các môi trường development và production được tối ưu, bạn có thể dễ dàng phát triển và triển khai ứng dụng của mình.

**Happy video creating!** 🎬✨
