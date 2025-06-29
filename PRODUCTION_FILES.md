# Production Files Whitelist

## Essential Files for Production

### Core Application
- `main.py` - Main FastAPI application
- `create_video.py` - Video creation logic
- `config.py` - Configuration settings
- `exceptions.py` - Custom exception classes
- `middleware.py` - Custom middleware
- `monitoring.py` - Application monitoring
- `concat_videos.py` - Video concatenation utilities

### Dependencies & Configuration
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Multi-container setup
- `.dockerignore` - Docker ignore rules
- `.env.example` - Environment variables template

### Utilities Package
- `utils/__init__.py`
- `utils/audio_utils.py` - Audio processing functions
- `utils/image_utils.py` - Image processing functions
- `utils/video_utils.py` - Video processing functions
- `utils/validation_utils.py` - Input validation

### Documentation
- `README.md` - Project documentation
- `SIMPLIFIED_FORMAT.md` - API format documentation

## Files Excluded from Production

### Development & Testing
- `test_*.py` - All test files
- `*_test.py` - Test files
- `test/` - Test directory
- `result/` - Test output videos
- `*.mp4`, `*.mp3`, `*.wav` - Media files

### Development Tools
- `.venv/` - Virtual environment
- `__pycache__/` - Python cache files
- `.cursor/`, `.roo/` - Editor specific
- `.taskmaster/` - Task management
- `.roomodes`, `.windsurfrules` - Configuration

### Documentation & Examples
- `AUDIO_MIGRATION_PLAN.md` - Migration docs
- `MIGRATION_COMPLETE.md` - Migration docs
- `moviepy.md` - Development notes
- `moviepy_transition_example.py` - Examples
- `input_sample*.json` - Sample files

### Temporary & Build Files
- `tmp*/` - Temporary directories
- `*.pyc` - Compiled Python files
- `docker_test_output.mp4` - Test outputs

## Production Deployment

When deploying to production, only include:
1. Core application files
2. Dependencies & configuration
3. Utils package
4. Essential documentation

This ensures a clean, minimal production image without development artifacts.
