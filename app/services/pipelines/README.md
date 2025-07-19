# Video Processing Pipelines

Module này chứa các pipeline xử lý video được thiết kế theo mô hình pipeline pattern, giúp tách biệt các bước xử lý và dễ dàng mở rộng.

## Cấu trúc thư mục

```
pipelines/
├── __init__.py           # Export các thành phần chính
├── pipeline_config.py    # Cấu hình các stages của pipeline
└── video_creation_pipeline.py  # Factory và helper functions
```

## Cách sử dụng

### 1. Tạo pipeline mặc định

```python
from app.services.pipelines import create_video_creation_pipeline

# Tạo pipeline với metrics collector mặc định
pipeline = create_video_creation_pipeline()

# Hoặc với metrics collector tùy chỉnh
from app.services.processors.base_processor import MetricsCollector
metrics_collector = MetricsCollector()
pipeline = create_video_creation_pipeline(metrics_collector=metrics_collector)
```

### 2. Sử dụng pipeline với VideoCreationService

```python
from app.services.video_creation_service import VideoCreationService

# Tạo service với pipeline mặc định
service = VideoCreationService()

# Hoặc với pipeline tùy chỉnh
from app.services.pipelines import create_video_creation_pipeline
custom_pipeline = create_video_creation_pipeline()
service = VideoCreationService()
service.pipeline = custom_pipeline  # Ghi đè pipeline mặc định
```

### 3. Tùy chỉnh pipeline

Bạn có thể tạo pipeline với các stages tùy chỉnh:

```python
from app.services.pipelines import get_video_creation_stages

# Lấy danh sách stages mặc định
stages = get_video_creation_stages()

# Tùy chỉnh stages theo nhu cầu
custom_stages = [
    stage for stage in stages 
    if stage['name'] != 's3_upload'  # Bỏ qua bước upload S3
]

# Tạo pipeline với stages tùy chỉnh
pipeline = create_video_creation_pipeline(custom_stages=custom_stages)
```

## Các stages mặc định

1. **ai_schema_validation**: Kiểm tra tính hợp lệ của dữ liệu đầu vào
2. **download_assets**: Tải xuống các tài nguyên cần thiết
3. **image_auto**: Xử lý tự động hình ảnh
4. **text_overlay_alignment**: Căn chỉnh và thêm phụ đề
5. **create_segment_clips**: Tạo các clip riêng lẻ
6. **concatenate_video**: Ghép các clip thành video hoàn chỉnh
7. **s3_upload**: Tải video lên S3

## Mở rộng pipeline

Để thêm stage mới vào pipeline:

1. Thêm cấu hình stage vào `pipeline_config.py`
2. Tạo processor/function tương ứng (nếu cần)
3. Thêm stage vào danh sách stages trong `get_video_creation_stages()`

## Gỡ lỗi

Để debug pipeline, bạn có thể bật logging chi tiết:

```python
import logging

# Bật logging chi tiết
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("VideoPipeline")
logger.setLevel(logging.DEBUG)
```
