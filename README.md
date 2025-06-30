# 🎬 Video Creation API

> Professional video creation service với batch processing, built với FastAPI và Docker

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.13-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## ✨ Features

- 🎥 **Batch Video Processing**: Tạo video từ nhiều segments
- 🖼️ **Multi-format Support**: Images (JPG, PNG, WebP) và Audio (MP3, WAV, AAC)
- 🌐 **URL & Local Files**: Hỗ trợ cả remote URLs và local files
- 🎭 **Transition Effects**: Fade, slide, zoom transitions giữa segments
- 🚀 **Production Ready**: Docker, nginx, SSL, monitoring
- 📊 **Real-time Monitoring**: Prometheus metrics và health checks
- 🔒 **Security**: Rate limiting, non-root containers, SSL support
- 🎛️ **Flexible Configuration**: Environment-based settings

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available for Docker

### 1. Clone và Setup

```bash
git clone <repository-url>
cd video-create

# Windows
setup-directories.bat

# Linux/macOS
chmod +x setup-directories.sh && ./setup-directories.sh
```

### 2. Configuration

```bash
# Tạo environment file
cp .env.template .env

# Chỉnh sửa cấu hình
# Development:
DEBUG=true
DOMAIN=localhost
SSL_ENABLED=false

# Production:
DEBUG=false  
DOMAIN=api.yourdomain.com
SSL_ENABLED=true
```

### 3. Start Services

```bash
# Development (with hot reload)
make dev

# Production
make prod

# Hoặc sử dụng docker-compose trực tiếp
docker-compose up -d
```

### 4. Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

## 📋 Quick API Example

### Create Video

```bash
curl -X POST http://localhost:8000/api/v1/video/create \
  -H "Content-Type: application/json" \
  -d '{
    "segments": [
      {
        "id": "intro",
        "images": ["https://picsum.photos/1280/720"],
        "voice_over": "https://example.com/voice.mp3",
        "duration": 5.0,
        "transition": {
          "type": "fade",
          "duration": 1.0
        }
      }
    ]
  }'
```

### JavaScript Client

```javascript
const response = await fetch('http://localhost:8000/api/v1/video/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    segments: [
      {
        id: 'intro',
        images: ['https://picsum.photos/1280/720'],
        duration: 5.0
      }
    ]
  })
});

const result = await response.json();
console.log('Video URL:', result.video_url);
```

## 🏗️ Architecture

### Multi-stage Docker Build
- **Builder stage**: Compile dependencies (gcc, g++, build tools)
- **Production stage**: Runtime-only environment (800MB vs 1.5GB)
- **Security**: Non-root user, minimal attack surface

### Services
- **video**: Main FastAPI application
- **nginx**: Reverse proxy, SSL termination, rate limiting
- **prometheus**: Monitoring và metrics
- **ngrok**: External access (development)

### Environments
- **Development**: Hot reload, debug logs, Redis, MinIO
- **Production**: Nginx proxy, SSL, monitoring, optimized resources

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [**USAGE_GUIDE.md**](USAGE_GUIDE.md) | 📖 Complete usage guide |
| [**API_DOCUMENTATION.md**](API_DOCUMENTATION.md) | 📡 API endpoints và examples |
| [**DOCKER_README.md**](DOCKER_README.md) | 🐳 Docker deployment guide |
| [**REFACTORING_GUIDE.md**](REFACTORING_GUIDE.md) | 🔧 Architecture overview |

## 🛠️ Management Commands

```bash
# Setup và development
make setup          # Initial setup
make dev            # Start development environment  
make build          # Build Docker images

# Production
make prod           # Start production
make deploy-prod    # Full production deployment

# Monitoring
make health         # Check service health
make logs           # View logs
make stats          # Resource usage

# Maintenance  
make restart        # Restart services
make clean          # Cleanup containers/images
make backup         # Backup data
```

## 🌐 Production Deployment

### 1. Server Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repository
git clone <repository-url>
cd video-create
```

### 2. Domain Configuration

```bash
# Configure DNS A record
# api.yourdomain.com -> YOUR_SERVER_IP
```

### 3. Deploy

```bash
# Automated deployment
make deploy-prod

# Manual deployment
export DOMAIN=api.yourdomain.com
export SSL_ENABLED=true
make prod-env
```

### 4. Access

- **API**: https://api.yourdomain.com
- **Docs**: https://api.yourdomain.com/docs
- **Health**: https://api.yourdomain.com/health
- **Monitoring**: http://localhost:9090

## 📊 API Overview

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/api/v1/video/create` | Create video from segments |
| `GET` | `/api/v1/video/{id}/status` | Get processing status |
| `GET` | `/api/v1/video/{id}/download` | Download video |
| `GET` | `/api/v1/videos` | List videos |
| `DELETE` | `/api/v1/video/{id}` | Delete video |

### Input Format

```json
{
  "segments": [
    {
      "id": "unique_identifier",
      "images": ["url1", "url2"],
      "voice_over": "audio_url",
      "background_music": "music_url", 
      "duration": 5.0,
      "transition": {
        "type": "fade|fadeblack|slide",
        "duration": 1.0
      }
    }
  ],
  "output_settings": {
    "format": "mp4",
    "quality": "high|medium|low",
    "resolution": {"width": 1280, "height": 720}
  }
}
```

## 🔧 Configuration

### Environment Variables

```bash
# Core settings
DOMAIN=api.yourdomain.com
API_BASE_URL=https://api.yourdomain.com
SSL_ENABLED=true
DEBUG=false
LOG_LEVEL=INFO

# Video processing
DEFAULT_VIDEO_FPS=24
DEFAULT_VIDEO_CODEC=libx264
MAX_WORKERS=1
MEMORY_LIMIT=2G

# Security
MAX_FILE_SIZE=104857600  # 100MB
UPLOAD_TIMEOUT=300
CORS_ORIGINS=https://yourfrontend.com
```

### Resource Limits

| Environment | Memory | CPU | Workers |
|-------------|---------|-----|---------|
| Development | 1GB | 0.5 | 1 |
| Production | 4GB | 2.0 | 2 |

## 🚨 Troubleshooting

### Common Issues

#### Service won't start
```bash
make logs           # Check error logs
make stats          # Check resources
make clean && make up  # Clean restart
```

#### API not accessible
```bash
# Check firewall
sudo ufw status

# Check port binding  
netstat -tulpn | grep :8000

# Verify health
curl http://localhost:8000/health
```

#### Out of memory
```bash
# Check usage
docker stats

# Increase limits in docker-compose.yml
memory: 4G
```

#### SSL certificate issues
```bash
# Check certificate
openssl x509 -in nginx/ssl/cert.pem -text -noout

# Regenerate self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem
```

### Debug Mode

```bash
# Enable debug logging
echo "DEBUG=true" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
make restart
make logs
```

## 🔒 Security

### Production Security Checklist

- ✅ HTTPS enabled với valid certificates
- ✅ Firewall configured (ports 22, 80, 443)
- ✅ Non-root containers
- ✅ Rate limiting enabled
- ✅ Environment variables secured
- ✅ Regular updates scheduled
- ✅ Monitoring và alerting configured

### Rate Limits

- General API: 10 requests/second
- Upload endpoints: 1 request/second
- Burst allowance: 20 requests

## 📈 Performance

### Benchmarks

- **Single video creation**: ~45 seconds
- **Batch processing**: 3 videos in 34 seconds  
- **Memory usage**: 512MB-2GB per job
- **Concurrent requests**: Up to 10/second

### Optimization Tips

- Use appropriate image sizes (1280x720 recommended)
- Optimize audio files (MP3 128kbps sufficient)
- Batch multiple segments vs multiple API calls
- Monitor resource usage with `make stats`

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd video-create

# Start development environment
make dev

# Make changes và test
# Code auto-reloads in development mode

# Run tests
make test
```

### Code Structure

```
app/
├── main.py              # FastAPI application
├── api/v1/              # API routes
├── core/                # Core functionality
├── models/              # Request/response models
├── services/            # Business logic
└── config/              # Configuration

utils/                   # Utility functions
test/                    # Test files
```

## 📞 Support

### Getting Help

1. **Check documentation**: [USAGE_GUIDE.md](USAGE_GUIDE.md)
2. **API reference**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)  
3. **Docker guide**: [DOCKER_README.md](DOCKER_README.md)
4. **Check logs**: `make logs`
5. **Verify health**: `make health`

### Quick Diagnostics

```bash
make info           # System overview
make health         # Health check
make stats          # Resource usage
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [MoviePy](https://zulko.github.io/moviepy/) - Video processing
- [Docker](https://docker.com/) - Containerization
- [Nginx](https://nginx.org/) - Reverse proxy
- [Prometheus](https://prometheus.io/) - Monitoring

---

**Happy video creating!** 🎬✨

*For detailed setup instructions, see [USAGE_GUIDE.md](USAGE_GUIDE.md)*
python create_video.py --input input_sample.json --output final_output.mp4
```

This will process all cuts in `input_sample.json` and produce `final_output.mp4`.


## Avaiable Transitions
- `fadeblack`: Fades to black between cuts.
- `crossfade`: Crossfades between cuts.
- `fade`: A generic fade transition.