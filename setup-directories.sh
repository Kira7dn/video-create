#!/bin/bash

# Script to create necessary directories for Docker volumes
# Run this before docker-compose up

echo "Creating necessary directories for video-create application..."

# Create data directories
mkdir -p data/temp
mkdir -p data/logs
mkdir -p data/cache

# Create nginx configuration directory (for production)
mkdir -p nginx

# Create monitoring directory (for production)
mkdir -p monitoring

# Set proper permissions
chmod 755 data
chmod 755 data/temp
chmod 755 data/logs
chmod 755 data/cache

echo "Directories created successfully!"
echo ""
echo "Directory structure:"
echo "├── data/"
echo "│   ├── temp/     # Temporary files for video processing"
echo "│   ├── logs/     # Application logs"
echo "│   └── cache/    # Application cache"
echo "├── nginx/        # Nginx configuration (production)"
echo "└── monitoring/   # Monitoring configuration (production)"
echo ""
echo "You can now run:"
echo "  Development: docker-compose up"
echo "  Production:  docker-compose -f docker-compose.yml -f docker-compose.prod.yml up"
