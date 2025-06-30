@echo off
REM Script to create necessary directories for Docker volumes
REM Run this before docker-compose up

echo Creating necessary directories for video-create application...

REM Create data directories
if not exist "data" mkdir data
if not exist "data\temp" mkdir data\temp
if not exist "data\logs" mkdir data\logs
if not exist "data\cache" mkdir data\cache

REM Create nginx configuration directory (for production)
if not exist "nginx" mkdir nginx

REM Create monitoring directory (for production)
if not exist "monitoring" mkdir monitoring

echo Directories created successfully!
echo.
echo Directory structure:
echo ├── data/
echo │   ├── temp/     # Temporary files for video processing
echo │   ├── logs/     # Application logs
echo │   └── cache/    # Application cache
echo ├── nginx/        # Nginx configuration (production)
echo └── monitoring/   # Monitoring configuration (production)
echo.
echo You can now run:
echo   Development: docker-compose up
echo   Production:  docker-compose -f docker-compose.yml -f docker-compose.prod.yml up

pause
