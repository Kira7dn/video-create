# Demo script để so sánh image size
#!/bin/bash

echo "=== So sánh Image Size ==="

# Build single-stage version
cat > Dockerfile.single << 'EOF'
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ ffmpeg git pkg-config libffi-dev \
    curl libgomp1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Build multi-stage version (existing Dockerfile)
echo "Building single-stage image..."
docker build -f Dockerfile.single -t video-api:single .

echo "Building multi-stage image..."  
docker build -f Dockerfile -t video-api:multi .

echo ""
echo "=== Image Size Comparison ==="
docker images | grep video-api

echo ""
echo "=== Detailed Analysis ==="
echo "Single-stage contains:"
docker run --rm video-api:single ls -la /usr/bin | grep -E "(gcc|g\+\+|git)" || echo "Build tools present"

echo ""
echo "Multi-stage contains:"
docker run --rm video-api:multi ls -la /usr/bin | grep -E "(gcc|g\+\+|git)" || echo "Build tools NOT present"

# Cleanup
rm Dockerfile.single
