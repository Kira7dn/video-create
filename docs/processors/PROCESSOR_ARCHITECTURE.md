# Video Processing Pipeline Architecture

## Overview

This document outlines the architecture of the video processing pipeline, including the key components, their responsibilities, and how they interact with each other.

## Core Components

### 1. Base Classes

#### `BaseProcessor`
- **Purpose**: Abstract base class for all processors
- **Key Methods**:
  - `async process(input_data: Any, **kwargs) -> Any`: Main processing method to be implemented by subclasses
  - `_start_processing(stage: ProcessingStage)`: Start metrics collection
  - `_end_processing(metric, success, error_message, items_processed)`: End metrics collection

#### `BatchProcessor`
- **Purpose**: Base class for batch processing operations
- **Extends**: `BaseProcessor`
- **Key Methods**:
  - `async process_batch(items: List[Any], **kwargs) -> List[Any]`: Process a batch of items
  - Implements `process` by delegating to `process_batch`

#### `Validator`
- **Purpose**: Base class for validation operations
- **Extends**: `BaseProcessor`
- **Key Methods**:
  - `validate(data: Any) -> ValidationResult`: Validate input data
  - Implements `process` by delegating to `validate`

### 2. Key Interfaces (Protocols)

#### `ISegmentProcessor`
- **Purpose**: Interface for processing individual video segments
- **Key Methods**:
  - `async process_segment(segment: Dict, temp_dir: str, **kwargs) -> Dict`

#### `IBatchProcessor`
- **Purpose**: Interface for batch processing operations
- **Key Methods**:
  - `async process_batch(items: List[Any], **kwargs) -> List[Any]`

### 3. Processing Pipeline

#### `VideoPipeline`
- **Purpose**: Orchestrates the execution of processing stages
- **Key Features**:
  - Sequential stage execution
  - Context passing between stages
  - Error handling and recovery
  - Progress tracking

## Implementation Guidelines

### Creating a New Processor

1. **Choose the Right Base Class**:
   - Use `BaseProcessor` for simple processors
   - Use `BatchProcessor` for batch operations
   - Use `Validator` for validation logic

2. **Implement Required Methods**:
   ```python
   class MyProcessor(BaseProcessor):
       async def process(self, input_data: Any, **kwargs) -> Any:
           # Implementation here
           pass
   ```

3. **Handle Errors**:
   - Raise appropriate exceptions (e.g., `ProcessingError`)
   - Use `_start_processing` and `_end_processing` for metrics

4. **Logging**:
   - Use the built-in logger: `self.logger`
   - Include relevant context in log messages

## Testing Guidelines

### Unit Tests
- Test each processor in isolation
- Mock dependencies
- Test both success and error cases

### Integration Tests
- Test processor interactions
- Test with real data when possible
- Verify output formats and side effects

## Performance Considerations

- Use batch processing for large datasets
- Implement proper resource cleanup
- Monitor memory usage for large files
- Consider async I/O for better concurrency

## Common Patterns

### Dependency Injection
```python
def create_processor():
    metrics = MetricsCollector()
    validator = MyValidator(metrics)
    return MyProcessor(validator=validator, metrics=metrics)
```

### Error Handling
```python
try:
    result = await processor.process(data)
except ProcessingError as e:
    self.logger.error(f"Processing failed: {e}")
    raise
```

## Best Practices

1. **Single Responsibility**: Each processor should do one thing well
2. **Stateless**: Processors should be stateless when possible
3. **Idempotency**: Processing the same input multiple times should be safe
4. **Logging**: Include sufficient debug information
5. **Documentation**: Document expected inputs, outputs, and side effects
