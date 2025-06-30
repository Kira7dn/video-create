# Ví dụ minh họa Multi-stage Build
# File: examples/single-vs-multi-stage.md

## Scenario: Bạn cần build một Python app với numpy + opencv

### ❌ Approach 1: Single-stage
```dockerfile
FROM python:3.12-slim

# Cài đặt TẤT CẢ dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ git pkg-config libffi-dev \  # Build tools
    ffmpeg curl libgomp1 \               # Runtime tools
    && pip install numpy opencv-python

COPY . .
CMD ["python", "app.py"]
```

**Kết quả:**
- Image size: 1.5GB
- Chứa gcc, g++, git trong production
- Có thể bị exploit qua build tools
- Upload/download chậm

---

### ✅ Approach 2: Multi-stage  
```dockerfile
# Stage 1: Build environment
FROM python:3.12-slim as builder
RUN apt-get update && apt-get install -y gcc g++ git pkg-config libffi-dev
RUN pip install numpy opencv-python

# Stage 2: Production environment  
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg curl libgomp1

# Chỉ copy compiled packages, KHÔNG copy build tools
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .
CMD ["python", "app.py"]
```

**Kết quả:**
- Image size: 800MB
- KHÔNG chứa gcc, g++, git
- An toàn hơn (ít attack vectors)
- Deploy nhanh hơn

---

## 🎯 Tại sao đặc biệt quan trọng với Video Processing?

### 1. **Packages nặng cần compile:**
```
numpy: ~50MB (cần gcc để compile C extensions)
opencv-python: ~200MB (cần g++ để compile C++ code)
moviepy: depends on numpy, imageio (cần build tools)
```

### 2. **Build vs Runtime requirements:**
```
Build time cần:     Runtime chỉ cần:
├── gcc            ├── ffmpeg
├── g++            ├── libgomp1  
├── git            ├── OpenGL libs
├── pkg-config     └── curl
└── libffi-dev     
```

### 3. **Production considerations:**
- **Security**: Build tools = potential security holes
- **Performance**: Nhỏ hơn = deploy nhanh hơn
- **Cost**: Bandwidth + storage costs
- **Compliance**: Nhiều companies yêu cầu minimal production images

## 🚀 Kết luận

Multi-stage build **không phải là over-engineering** - nó là **best practice** cho:

1. **Size optimization**: 50% nhỏ hơn
2. **Security**: Loại bỏ unnecessary tools  
3. **Performance**: Deploy và scale nhanh hơn
4. **Cost**: Tiết kiệm bandwidth và storage
5. **Maintainability**: Tách biệt build vs runtime concerns

Đặc biệt quan trọng với video processing vì cần nhiều heavy packages nhưng chỉ cần minimal runtime dependencies.
