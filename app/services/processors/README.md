# Video Processors

This directory contains the core processing components for the video creation service.

## Core Components

### Base Classes
- `base_processor.py`: Defines the base processor interfaces and common functionality
  - `BaseProcessor`: Abstract base class for all processors
  - `BatchProcessor`: Base class for batch operations
  - `Validator`: Base class for validation logic

### Concrete Implementations
- `segment_processor.py`: Processes individual video segments
- `concatenation_processor.py`: Combines video segments
- `image_auto_processor.py`: Handles image processing
- `transcript_processor.py`: Processes video transcripts
- `s3_upload_processor.py`: Handles S3 uploads

### Pipeline
- `pipeline.py`: Defines the video processing pipeline
- `interfaces.py`: Protocol definitions for processor interfaces

## Usage Examples

### Creating a Simple Processor

```python
from typing import Any, Dict
from app.services.processors.base_processor import BaseProcessor

class MyProcessor(BaseProcessor):
    async def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        self.logger.info("Processing data")
        # Process input_data
        return {"result": "success"}
```

### Using the Pipeline

```python
from app.services.processors.pipeline import VideoPipeline, PipelineStage

class MyStage(PipelineStage):
    async def process(self, context):
        # Process context
        return context

pipeline = VideoPipeline([
    MyStage("stage1"),
    MyStage("stage2"),
])

result = await pipeline.run(initial_context)
```

## Testing

Run tests with:
```bash
pytest tests/processors/
```

## Documentation

For detailed architecture and guidelines, see:
[Processor Architecture](../../docs/processors/PROCESSOR_ARCHITECTURE.md)
