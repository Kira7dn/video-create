# Video Creation API - Docker Guide

This document provides comprehensive Docker setup and deployment instructions for the Video Creation API.

## 🐳 Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available for Docker
- 10GB+ disk space

### Development Setup

1. **Clone and setup:**
```bash
git clone <your-repo>
cd video-create
make setup  # or run setup-directories.bat on Windows
```

2. **Configure environment:**
```bash
cp .env.template .env
# Edit .env file with your settings
```

3. **Start development environment:**
```bash
make dev
# or
docker-compose up
```

4. **Access the API:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## 🏗️ Docker Architecture

### Multi-stage Dockerfile Benefits
- **Builder stage**: Installs build dependencies and Python packages
- **Production stage**: Only includes runtime dependencies
- **Smaller final image**: ~800MB vs ~1.2GB
- **Better security**: No build tools in production image

### Container Optimizations
- Non-root user for security
- Optimized Python settings
- Memory and CPU limits
- Health checks with proper timeouts
- Proper FFmpeg integration for video processing

## 🚀 Deployment Options

### Development Environment
```bash
# With hot reload and debug features
make dev

# Manual command
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

Features:
- Hot code reload
- Debug logging
- Development tools
- Lower resource limits

### Production Environment
```bash
# Optimized for production
make prod

# Manual command
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Features:
- Nginx reverse proxy
- Prometheus monitoring
- Production logging
- Higher resource limits
- SSL/TLS support

## 📊 Resource Management

### Memory Allocation
- **Development**: 1GB limit, 256MB reserved
- **Production**: 4GB limit, 1GB reserved
- **Video processing needs**: 500MB-2GB per concurrent job

### CPU Allocation
- **Development**: 0.5 CPU limit
- **Production**: 2.0 CPU limit
- **Single worker**: Recommended for video processing

### Storage
- **Temp files**: Docker volume with cleanup
- **Logs**: Persistent volume with rotation
- **Cache**: In-memory with volume backup

## 🔧 Configuration

### Environment Variables
Key variables in `.env`:

```bash
# Core settings
DEBUG=false
LOG_LEVEL=INFO
MAX_WORKERS=1           # Keep at 1 for video processing

# Resource limits
MEMORY_LIMIT=2G
MOVIEPY_TEMP_DIR=/app/tmp

# Ngrok (for external access)
NGROK_AUTHTOKEN=your_token_here
NGROK_URL=your_domain

# Video processing
DEFAULT_VIDEO_FPS=24
DEFAULT_VIDEO_CODEC=libx264
```

### Volume Mounts
- `video_temp:/app/tmp` - Temporary video processing files
- `video_logs:/app/logs` - Application logs
- `video_cache:/app/cache` - Processing cache

## 🔍 Monitoring & Debugging

### Health Checks
```bash
# Check service health
make health
curl http://localhost:8000/health

# Container status
make info
docker-compose ps
```

### Logs
```bash
# Follow logs
make logs
docker-compose logs -f video

# Specific service logs
docker-compose logs ngrok
```

### Resource Usage
```bash
# Real-time stats
make stats
docker stats cont_video

# Container details
docker inspect cont_video
```

## 🛠️ Maintenance

### Regular Tasks
```bash
# Restart services
make restart

# Clean up old containers/images
make clean

# Backup logs and data
make backup

# Update images
docker-compose pull
make build
```

### Troubleshooting

#### Common Issues

1. **Out of Memory**
```bash
# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # Increase this
```

2. **Permission Issues**
```bash
# Fix permissions
docker-compose exec video chown -R app:app /app/tmp
```

3. **FFmpeg Not Found**
```bash
# Verify FFmpeg installation
docker-compose exec video which ffmpeg
docker-compose exec video ffmpeg -version
```

4. **Temp Files Not Cleaning**
```bash
# Manual cleanup
docker-compose exec video rm -rf /app/tmp/*
docker volume rm video-create_video_temp
```

### Performance Tuning

#### For High-Load Production
```yaml
services:
  video:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4.0'
    environment:
      - MAX_REQUESTS=500
      - WORKERS=2  # Still keep low for video processing
```

#### For Development
```yaml
services:
  video:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
```

## 📋 Available Commands

### Make Commands
```bash
make help      # Show all available commands
make setup     # Initial setup
make build     # Build images
make up        # Start development
make down      # Stop all services
make dev       # Development with hot reload
make prod      # Production deployment
make logs      # Show logs
make clean     # Cleanup everything
make test      # Run tests
make shell     # Open container shell
make health    # Health check
make stats     # Resource usage
make backup    # Backup data
make info      # Container information
```

### Docker Compose Commands
```bash
# Basic operations
docker-compose up -d                    # Start in background
docker-compose down                     # Stop all services
docker-compose restart video           # Restart specific service

# Development
docker-compose -f docker-compose.yml -f docker-compose.override.yml up

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Maintenance
docker-compose exec video /bin/bash     # Shell access
docker-compose logs -f video           # Follow logs
docker-compose ps                      # Service status
```

## 🔐 Security Considerations

### Production Security
- Non-root user in container
- Resource limits to prevent DoS
- No sensitive data in environment variables
- Regular image updates
- Network isolation

### Development Security
- Use `.env` file for secrets
- Don't commit sensitive data
- Use proper volume permissions
- Regular dependency updates

## 📈 Scaling Considerations

### Horizontal Scaling
For multiple replicas, consider:
- Shared storage for temp files
- Load balancer configuration
- Session management
- Database for coordination

### Vertical Scaling
- Increase memory for larger videos
- More CPU cores for parallel processing
- SSD storage for temp files
- Network bandwidth for downloads

## 🆘 Support

### Getting Help
1. Check logs: `make logs`
2. Verify health: `make health`
3. Check resources: `make stats`
4. Review configuration: `make info`

### Common Solutions
- Restart services: `make restart`
- Clean rebuild: `make clean && make build && make up`
- Reset volumes: `docker-compose down -v && make up`
