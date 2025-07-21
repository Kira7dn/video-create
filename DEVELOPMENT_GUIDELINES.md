---
trigger: always_on
---

## 📝 Coding Standards

### Python

* Follow PEP 8 style guide
* Use type hints for all function signatures
* Maximum line length: 100 characters
* Use f-strings for regular string formatting (except in logging)
* Use `pathlib` for file paths and directory operations
* One class per file, one responsibility per class/function
* Use `black` for auto-formatting code

### Import Rules

* ALWAYS order imports as: standard library → third-party → local imports
* Use absolute imports (avoid relative imports like `from .module import X`)
* Sort imports using `isort`
* Avoid unused imports
* Group imports with line breaks between categories

### Naming Conventions

* Variables and functions: `snake_case`
* Classes: `PascalCase`
* Constants: `UPPER_SNAKE_CASE`
* Private members: `_leading_underscore`
* Avoid shadowing built-in names like `id`, `list`, `file`
* Be descriptive but concise

### Docstring Rules

* All public modules, classes, and functions MUST have docstrings
* Use Google-style or NumPy-style docstrings consistently
* Private functions should have at least a one-line docstring
* Include usage examples where helpful
* Document arguments, return types, raised exceptions

## 🚨 ERROR HANDLING & LOGGING

### ⚠️ CRITICAL RULES

* ❌ NEVER use bare `except` clauses
* ❌ NEVER silently swallow exceptions
* ✅ ALWAYS use specific exception types from `app.core.exceptions`
* ✅ ALWAYS include context in error messages
* ✅ Use appropriate exception hierarchy for different error types

### Exception Hierarchy

The project uses a well-defined exception hierarchy in `app/core/exceptions.py`:

```python
# Base exceptions
VideoProcessingError          # Base for all video processing errors
├── VideoCreationError        # Video creation specific errors
├── ProcessingError          # General processing failures
├── UploadError             # S3 upload failures
├── ValidationError         # Input validation failures
├── PipelineError           # Pipeline execution failures
├── ConcatenationError      # Video concatenation failures
├── BatchProcessingError    # Batch processing failures
├── ResourceError           # Resource management failures
├── ConfigurationError      # Configuration issues
├── AssetError             # Asset handling failures
└── FileValidationError    # File validation errors
```

### Using Exceptions Correctly

```python
# ✅ Good - Specific exception with context
from app.core.exceptions import ProcessingError, UploadError

try:
    result = process_video(input_data)
except FileNotFoundError as e:
    raise ProcessingError(f"Input file not found: {input_data['path']}") from e
except Exception as e:
    raise ProcessingError(f"Failed to process video: {str(e)}") from e

# ✅ Good - Exception with additional context
try:
    upload_to_s3(video_path, bucket, key)
except ClientError as e:
    raise UploadError(
        f"Failed to upload to S3: {str(e)}",
        video_id=video_metadata.get('id')
    ) from e

# ❌ Bad - Bare except
try:
    process_data()
except:  # Never do this!
    pass

# ❌ Bad - Generic exception without context
try:
    process_data()
except Exception:
    raise Exception("Something went wrong")  # Too generic!
```

### Logging Standards

* ✅ Use lazy `%` formatting for all logging calls to avoid unnecessary computation:

  ```python
  logger.debug("Processing file %s", filename)  # ✅ Correct
  ```
* ❌ NEVER use f-strings or `%` operators inside logging statements:

  ```python
  logger.debug(f"Processing file {filename}")    # ❌ Don't
  logger.debug("File is %s" % filename)          # ❌ Don't
  ```
* ✅ Use appropriate logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
* ✅ Include relevant context in log messages
* ✅ Use structured logging if possible (e.g., `extra`, JSON logs)

### Best Practices

1. **Exception Handling**

   * Use custom exception types from `app.core.exceptions` for business logic
   * Preserve stack traces when re-raising with `from e`
   * Always clean up resources in `finally` blocks or with context managers
   * Include relevant context (file paths, IDs, parameters) in error messages
   * Use appropriate exception type for the specific failure scenario

2. **Logging**

   * Log context-rich messages
   * Avoid logging excessive data or secrets
   * Use `logging` module — not `print()`

3. **Resource Management**

   * Use `with` statements for file/resource management
   * Clean up temp files
   * Handle temporary files properly using `tempfile` or context managers

## 🧩 Interface Guidelines

* Define interfaces using `Protocol` from `typing` or abstract base classes (ABC) from `abc`
* Interfaces must be defined in `app/interfaces/`
* Use `@runtime_checkable` when runtime type validation is needed (e.g., with `isinstance()`)
* Always type services and dependencies by their interface, not their implementation:

  ```python
  def __init__(self, processor: IVideoProcessor):
      self.processor = processor
  ```
* Interface names must start with an `I`, e.g. `IVideoProcessor`, `IUploader`
* Prefer thin interfaces with a small set of methods focused on one responsibility
* All interfaces must be documented with expected behavior, not implementation
* Use mocks or stubs of interfaces for unit testing — never test against real implementations

## 🚀 Pipeline System Architecture

The pipeline system provides a flexible and extensible way to define and execute multi-step workflows. It's designed to be:

- **Modular**: Each stage is independent and can be developed/tested in isolation
- **Composable**: Stages can be combined in various ways to create complex workflows
- **Observable**: Built-in metrics and logging for monitoring and debugging
- **Type-safe**: Full type hints and interface definitions
- **Testable**: Designed with testability in mind

### Core Components

#### 1. Pipeline Context (`IPipelineContext`)

The context is a container that holds data and state that flows through the pipeline. It provides:

- **Data Storage**: Key-value store for passing data between stages
- **Metadata**: For storing execution metadata
- **Temporary Directory**: For file operations during pipeline execution

```python
# Example: Working with pipeline context
from app.services.pipelines.context.default import PipelineContext

# Create a new context with a temporary directory
context = PipelineContext(temp_dir=Path("/tmp/pipeline"))

# Store data in context
context.set("input_data", "some_value")

# Retrieve data from context
value = context.get("input_data")

# Access metadata
context.metadata["execution_id"] = "12345"
```

#### 2. Pipeline Stages

Stages are the building blocks of a pipeline, located in `app/services/pipelines/stages/`:

1. **Base Stage** (`base.py`)
   - Abstract base class for all stages
   - Handles common functionality like status tracking and input validation

2. **Processor Stage** (`processor.py`)
   - Wraps a processor (synchronous or asynchronous)
   - Handles input/output mapping between context and processor

3. **Function Stage** (`function.py`)
   - Wraps a simple function (sync or async)
   - Ideal for lightweight operations

4. **Conditional Stage** (`conditional.py`)
   - Executes one of two stages based on a condition

5. **Parallel Stage** (`parallel.py`)
   - Executes multiple stages in parallel

#### 3. Video Pipeline (`video_pipeline.py`)

The main pipeline implementation that orchestrates stage execution:

- Manages stage lifecycle
- Handles error propagation
- Collects metrics and execution statistics
- Supports both sync and async stages

### Creating a Custom Stage

```python
from pathlib import Path
from typing import Dict, Any
from app.services.pipelines.stages.base import PipelineStage
from app.interfaces.pipeline import IPipelineContext

class MyCustomStage(PipelineStage):
    """A custom pipeline stage that demonstrates basic functionality.
    
    Args:
        name: Unique name for this stage
        some_param: Example parameter for demonstration
    """
    def __init__(self, name: str, some_param: str):
        super().__init__(name, required_inputs=["input_data"])
        self.some_param = some_param
    
    async def _execute_impl(self, context: IPipelineContext) -> IPipelineContext:
        # Get input from context
        input_data = context.get("input_data")
        
        # Process data
        result = f"Processed {input_data} with {self.some_param}"
        
        # Store result in context
        context.set("output_data", result)
        
        # Update metadata
        context.metadata["processed"] = True
        
        return context
        
        return context
```

### Example: Building a Pipeline

```python
from app.services.pipelines import VideoPipeline
from app.services.pipelines.stages import ProcessorPipelineStage, FunctionPipelineStage
from app.services.processors.media.video import VideoProcessor
from pathlib import Path

# Create a pipeline
pipeline = VideoPipeline()

# Add a processor stage
video_processor = VideoProcessor()
pipeline.add_processor_stage(
    name="process_video",
    processor=video_processor,
    input_key="video_path",
    output_key="processed_video"
)

# Add a function stage
def analyze_video(context: IPipelineContext) -> None:
    video_data = context.get("processed_video")
    # Perform analysis
    context.set("analysis_result", {"duration": video_data.duration})

pipeline.add_function_stage(
    name="analyze_video",
    func=analyze_video,
    required_inputs=["processed_video"]
)

# Execute the pipeline
context = MyContext(temp_dir=Path("/tmp"))
context.set("video_path", "/path/to/video.mp4")

result = await pipeline.execute(context)
print(f"Pipeline completed in {result['duration']:.2f} seconds")
```

### Error Handling

The pipeline system provides robust error handling:

- Each stage's execution is wrapped in a try-catch block
- Errors are wrapped in `ProcessingError` with context
- Failed stages can be retried or skipped based on configuration
- Detailed error information is available in the execution result

```python
try:
    result = await pipeline.execute(context)
    if not result["success"]:
        for stage in result["stages"]:
            if stage["status"] == "failed":
                print(f"Stage {stage['name']} failed: {stage['error']}")
        
        # Handle specific error types
        if "validation_error" in result:
            handle_validation_error(result["validation_error"])
            
except ProcessingError as e:
    logger.error(f"Pipeline failed: {e}")
    # Handle pipeline failure
```

### Metrics and Monitoring

The pipeline automatically collects metrics:

- Execution time for each stage and the entire pipeline
- Success/failure rates
- Input/output data sizes
- Custom metrics via the metrics collector

```python
# Accessing metrics
metrics = pipeline.metrics_collector.get_metrics()
for stage_name, stage_metrics in metrics.items():
    print(f"{stage_name}: {stage_metrics}")
```

### Testing Pipeline Components

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_my_custom_stage():
    # Setup
    context = MagicMock()
    context.get.return_value = "test_input"
    context.metadata = {}
    
    # Execute
    stage = MyCustomStage("test_stage", "test_param")
    result = await stage.execute(context)
    
    # Verify
    context.set.assert_called_with("output_data", "Processed test_input with test_param")
    assert context.metadata["processed"] is True
```

## 🔄 Code Quality & Maintainability

* Maintain cyclomatic complexity per function < 10
* Avoid deep nesting (prefer early returns)
* Keep function length < 40 lines where possible
* Limit number of arguments per function to 5 or fewer
* Use enums or constants instead of magic strings/numbers

## 🏗️ Project Structure

```
video-create/
├── app/                      # Application code
│   ├── config/               # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py       # Pydantic settings with environment variables
│   │   └── schema.json       # JSON schema for validation
│   │
│   ├── core/                 # Core application components
│   │   ├── __init__.py
│   │   ├── exceptions.py     # Custom exception classes (VideoProcessingError, etc.)
│   │   └── dependencies.py   # FastAPI dependencies
│   │
│   ├── interfaces/           # Protocols / Abstract Base Interfaces
│   │   ├── __init__.py
│   │   ├── audio.py          # IAudioProcessor
│   │   ├── metrics.py        # IMetricsCollector
│   │   ├── storage.py        # IUploader, IStorage
│   │   ├── validation.py     # IValidator
│   │   ├── video.py          # IVideoProcessor, IDownloader, etc.
│   │   └── pipeline/         # Pipeline interfaces
│   │       ├── __init__.py
│   │       ├── context.py    # IPipelineContext
│   │       ├── stage.py      # IPipelineStage
│   │       └── pipeline.py   # IPipeline
│   │
│   ├── models/               # Pydantic models
│   │   ├── __init__.py
│   │   ├── requests.py       # Request schemas
│   │   └── responses.py      # Response schemas
│   │
│   ├── api/                  # FastAPI routers and endpoints
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app configuration
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py     # API router for version v1
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── video.py  # Video creation endpoints
│   │
│   ├── services/             # Business logic coordination layer
│   │   ├── __init__.py
│   │   ├── video_service.py  # High-level orchestration logic
│   │   ├── download_service.py # Asset download service
│   │   │
│   │   ├── processors/       # Processing components
│   │   │   ├── __init__.py   # Exports all processors
│   │   │   │
│   │   │   ├── core/         # Base classes and metrics
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_processor.py  # ProcessorBase, SyncProcessor, AsyncProcessor
│   │   │   │   └── metrics.py         # MetricsCollector, ProcessingMetrics
│   │   │   │
│   │   │   ├── media/        # Audio/video/image processing
│   │   │   │   ├── __init__.py
│   │   │   │   ├── audio/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── processor.py   # AudioProcessor
│   │   │   │   ├── video/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── processor.py   # VideoProcessor
│   │   │   │   └── image/
│   │   │   │       ├── __init__.py
│   │   │   │       └── processor.py   # ImageProcessor
│   │   │   │
│   │   │   ├── workflow/     # Segment and composition logic
│   │   │   │   ├── __init__.py
│   │   │   │   ├── segment_processor.py  # SegmentProcessor
│   │   │   │   └── composer.py           # ConcatenationProcessor
│   │   │   │
│   │   │   ├── io/           # File operations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── download.py        # DownloadProcessor
│   │   │   │   └── upload.py          # S3UploadProcessor
│   │   │   │
│   │   │   ├── text/         # Text processing
│   │   │   │   ├── __init__.py
│   │   │   │   ├── overlay.py         # TextOverlayProcessor
│   │   │   │   └── transcript.py      # TranscriptProcessor
│   │   │   │
│   │   │   └── validation/   # Data validation
│   │   │       ├── __init__.py
│   │   │       └── processor.py       # ValidationProcessor
│   │   │
│   │   └── pipelines/        # Pipeline orchestration framework
│   │       ├── __init__.py            # Core pipeline exports
│   │       ├── pipeline_config.py     # Pipeline configuration
│   │       ├── video_pipeline.py      # VideoPipeline implementation
│   │       ├── video_creation_pipeline.py  # Video creation workflow factory
│   │       │
│   │       ├── context/      # Pipeline context implementations
│   │       │   ├── __init__.py
│   │       │   └── default.py         # DefaultPipelineContext
│   │       │
│   │       └── stages/       # Pipeline stage implementations
│   │           ├── __init__.py
│   │           ├── base.py            # BasePipelineStage
│   │           ├── function.py        # FunctionPipelineStage
│   │           └── processor.py       # ProcessorPipelineStage
│   │
│   └── main.py               # Application entry point
│
├── utils/                    # Shared utilities
│   ├── __init__.py
│   ├── gentle_utils.py       # Gentle API utilities
│   ├── ffmpeg_utils.py       # FFmpeg utilities
│   ├── subprocess_utils.py   # Safe subprocess execution
│   ├── image_utils.py        # Image processing utilities
│   └── resource_manager.py   # File/directory cleanup utilities
│
├── test/                     # Tests
│   ├── conftest.py           # Test configuration and fixtures
│   ├── input_sample.json     # Sample input data for tests
│   ├── test_transcript.txt   # Sample transcript for tests
│   │
│   ├── unit/                 # Unit tests
│   │   ├── test_*.py         # Standard unit test files
│   │   └── _test_*.py        # Legacy test files (to be renamed)
│   │
│   ├── integration/          # Integration tests
│   │   ├── test_*.py         # Standard integration test files
│   │   └── _test_*.py        # Legacy test files (to be renamed)
│   │
│   ├── e2e/                  # End-to-end tests
│   │   └── test_*.py         # E2E test files
│   │
│   ├── temp/                 # Temporary files during testing
│   └── test_output/          # Test output files and logs
│       └── logs/             # Test execution logs
│
├── fonts/                    # Font files for text overlay
├── data/                     # Data files
├── .env                      # Environment variables
├── .env.example              # Environment variables template
├── requirements.prod.txt     # Production dependencies
├── requirements.dev.txt      # Development dependencies
├── pytest.ini               # Pytest configuration
├── .pylintrc                 # Pylint configuration
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose configuration
└── DEVELOPMENT_GUIDELINES.md # This file
```

### Processors Organization

1. **Core** (`core/`): Base classes and shared components
   - `base_processor.py`: Abstract base classes for all processors
   - `metrics.py`: Metrics collection and tracking

2. **Media Processing** (`media/`): Media-specific processors
   - Audio, video, and image processing components
   - Organized by media type for better separation of concerns

3. **Workflow** (`workflow/`): Workflow orchestration
   - High-level processors that coordinate other processors
   - Handles segment processing and composition

4. **I/O** (`io/`): Input/Output operations
   - File downloads, uploads, and storage operations
   - Abstracted for easy replacement of storage backends

5. **Text Processing** (`text/`): Text-related operations
   - Text overlays, transcript processing, etc.

6. **Validation** (`validation/`): Data validation
   - Input validation and data integrity checks
   - AI-assisted validation when needed

## 🏆 Best Practices for Processors

### 1. Interface Implementation
- Always implement the corresponding interface for each processor
- Depend on interfaces, not concrete implementations
- Use dependency injection for better testability

### 2. Error Handling
- Handle errors at the appropriate level
- Include meaningful error messages
- Clean up resources in case of failures

### 3. Performance
- Use async/await for I/O-bound operations
- Batch operations when possible
- Monitor resource usage

### 4. Testing
- Write unit tests for each processor
- Test error conditions and edge cases
- Use mocks for external dependencies

## ⚠️ Critical Development Rules

1. **Configuration**

   * ✅ Use only `app/config/settings.py` for all configurations (Pydantic Settings)
   * ✅ Use environment variables for configuration values
   * ✅ Provide sensible defaults in the Settings class
   * ❌ NEVER create additional config files or hardcode configuration values
   * 🔐 NEVER commit secrets or sensitive data to `.env` files
   * 🔐 Use `.env.example` as template for required environment variables

### Configuration Pattern

```python
# app/config/settings.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Settings
    api_title: str = "Video Creation API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # File Upload Settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = [".json"]
    
    # AWS Settings (from environment)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    
    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()
```

### Using Configuration

```python
# ✅ Good - Import and use settings
from app.config.settings import settings

def upload_to_s3(file_path: str):
    bucket = settings.s3_bucket
    region = settings.aws_region
    # Use configuration values...

# ❌ Bad - Hardcoded values
def upload_to_s3(file_path: str):
    bucket = "my-hardcoded-bucket"  # Never do this!
```

2. **Code Organization**

   * ✅ Keep business logic in `/app/services/processors/` organized by domain
   * ✅ Place shared utilities in `/utils/`
   * ✅ Use interfaces in `/app/interfaces/` for dependency injection
   * ✅ Keep pipeline orchestration in `/app/services/pipelines/`
   * ❌ NEVER mix business logic with infrastructure code
   * 🧩 Each processor must follow SRP (Single Responsibility Principle)
   * 🧩 One class per file, one responsibility per class

3. **Pipeline Pattern**

   * ✅ Use `VideoPipeline` or equivalent for complex workflows
   * ✅ Keep pipeline stages independent and testable
   * ❌ NEVER bypass the pipeline pattern for complex operations

## 🧪 Testing

### Critical Rules

* ❌ NEVER skip tests for "simple" code
* ✅ ALWAYS write tests for error conditions
* ✅ Test coverage MUST be > 80%
* ✅ Use proper test file naming: `test_*.py` (not `_test_*.py`)
* ✅ Place tests in correct directories: `test/unit/`, `test/integration/`, `test/e2e/`
* ✅ Mock interfaces, not implementations
* ✅ Use `pytest` with `pytest-asyncio` for async tests

### Test Structure and Organization

```
test/
├── conftest.py              # Test configuration and fixtures
├── input_sample.json        # Sample test data
├── test_transcript.txt      # Sample transcript data
│
├── unit/                    # Unit tests (isolated components)
│   ├── test_*.py            # Standard unit test files
│   └── _test_*.py           # Legacy files (rename to test_*.py)
│
├── integration/             # Integration tests (component interactions)
│   ├── test_*.py            # Standard integration test files
│   └── _test_*.py           # Legacy files (rename to test_*.py)
│
├── e2e/                     # End-to-end tests (full workflows)
│   └── test_*.py            # E2E test files
│
├── temp/                    # Temporary files during testing
└── test_output/             # Test output files and logs
    └── logs/                # Test execution logs
```

### Testing Strategy

#### Unit Tests

* Test one component in isolation
* Mock external dependencies using `unittest.mock`
* Follow Arrange-Act-Assert pattern
* Use `@pytest.mark.asyncio` for async tests
* Mock interfaces, not concrete implementations

```python
# Example unit test
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.processors.workflow.segment_processor import SegmentProcessor

@pytest.mark.asyncio
async def test_segment_processor_success():
    # Arrange
    processor = SegmentProcessor()
    processor.audio_processor = AsyncMock()
    processor.text_processor = MagicMock()
    
    input_data = {"segment_id": "test_123", "image": {"url": "test.jpg"}}
    
    # Act
    result = await processor.process(input_data)
    
    # Assert
    assert "segment_path" in result
    processor.audio_processor.create_audio_composition.assert_called_once()
```

#### Integration Tests

* Test component interactions within the pipeline
* Use real implementations where possible
* Mock external services (S3, APIs)
* Clean up test data after tests

```python
# Example integration test
import pytest
from app.services.pipelines.video_pipeline import VideoPipeline
from app.services.processors.workflow.segment_processor import SegmentProcessor

@pytest.mark.asyncio
async def test_pipeline_with_segment_processor():
    # Arrange
    pipeline = VideoPipeline()
    pipeline.add_processor_stage(
        name="segment_processing",
        processor=SegmentProcessor(),
        input_key="segments",
        output_key="processed_segments"
    )
    
    context = {"segments": [{"id": "1", "image": {"url": "test.jpg"}}]}
    
    # Act
    result = await pipeline.execute(context)
    
    # Assert
    assert "processed_segments" in result
    assert len(result["processed_segments"]) == 1
```

#### End-to-End Tests

* Test complete workflows from API to final output
* Use real data and minimal mocking
* Test actual file operations and external integrations

### Test Configuration (`conftest.py`)

The project uses a comprehensive test configuration:

```python
# Key fixtures available in all tests
@pytest.fixture
def valid_video_data():
    """Provides valid video data from input_sample.json"""
    
@pytest.fixture
def test_segments(input_data):
    """Provides test segment data"""
    
@pytest.fixture
def schema_file():
    """Returns path to schema.json for validation tests"""
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test directory
pytest test/unit/
pytest test/integration/

# Run specific test file
pytest test/unit/test_segment_processor.py

# Run with coverage
pytest --cov=app --cov=utils --cov-report=html

# Run async tests
pytest -v test/unit/test_async_processor.py

# Run tests with detailed output
pytest -v -s
```

### Test Best Practices

1. **Naming Convention**
   - Test files: `test_*.py`
   - Test functions: `test_*`
   - Test classes: `Test*`

2. **Async Testing**
   - Use `@pytest.mark.asyncio` for async test functions
   - Mock async dependencies with `AsyncMock`

3. **Mocking Strategy**
   - Mock at the interface level, not implementation
   - Use `patch` for external dependencies
   - Mock file operations and network calls

4. **Test Data Management**
   - Use fixtures for reusable test data
   - Clean up temporary files after tests
   - Use `test/temp/` for temporary test files

## ⚡ Performance & Resource Management

### Critical Rules

* ❌ NEVER hardcode file paths
* ✅ ALWAYS use `pathlib` for file operations
* ✅ ALWAYS clean up temporary files

### Best Practices

1. **I/O Operations**

   * Use async/await for I/O-bound operations
   * Batch database queries
   * Use connection pooling

2. **Memory Management**

   * Use generators for large datasets
   * Avoid unnecessary object creation
   * Monitor memory usage

3. **Caching**

   * Cache expensive operations
   * Invalidate cache appropriately
   * Use appropriate cache TTL

## 📚 Documentation & Maintenance

### Critical Rules

* ✅ ALWAYS document public APIs with docstrings
* ❌ NEVER leave commented-out code in the codebase
* ✅ ALWAYS update documentation when changing behavior

### Documentation Standards

#### Code Documentation

* Document all public APIs with docstrings
* Follow Google-style docstrings
* Include examples where helpful

#### Project Documentation

* Keep `README.md` up to date
* Document setup and deployment
* Include troubleshooting and FAQ section

## 🔄 Development Workflow

### Pre-commit Checklist

* ✅ All tests pass (`pytest`)
* ✅ Test coverage > 80% (`pytest --cov=app --cov=utils`)
* ✅ Code formatted with `black`
* ✅ Imports sorted with `isort`
* ✅ Type checking passes with `mypy`
* ✅ Linting passes (`pylint`, `flake8`)
* ✅ No secrets or sensitive data committed
* ✅ All legacy `_test_*.py` files renamed to `test_*.py`

### Code Review Flow

1. Create a feature branch
2. Write tests first (TDD if possible)
3. Implement functionality
4. Run linters and all tests
5. Update documentation
6. Create a pull request (PR)
7. Address all review comments
8. Merge to main after approval

## 🛠️ Tools & Hooks

### Linting & Formatting

* `black` for formatting
* `isort` for sorting imports
* `flake8` for linting
* `pylint` for static checks
* `mypy` for type checks

### Pre-commit Hook Setup

```bash
# Install pre-commit hook system
pre-commit install
```

* Pre-commit hooks will auto-run on each commit

## 📦 Dependency Management

* Use `pip-tools` to manage dependencies
* Add new deps to `requirements.in`, then run:

```bash
pip-compile  # generates requirements.txt
```

* Always pin dependency versions
* Document any non-standard dependencies

## 🔒 Security & Monitoring

* ❌ NEVER commit secrets or access keys
* ✅ Use environment variables for sensitive data
* ✅ Keep all dependencies up to date
* ✅ Perform regular security audits

### Monitoring

* Log all errors
* Track performance metrics (e.g., latency, CPU, memory)
* Set up alerts for critical failures
* Monitor service uptime and resource usage

## ✅ Summary for Linters (PEP8, pylint)

These rules will help pass:

* `black` (code formatter)
* `isort` (import sorter)
* `pylint` (static checker)
* `flake8` (style and complexity)
* `mypy` (type checker)

Violations of these rules will cause pre-commit hook failures and CI build warnings.

✅ Keep your code clean, testable, and idiomatic to ensure collaboration and scaling.

## 🛠 Creating a New Processor for the Pipeline

### 1. Processor Base Classes

Processors should inherit from either `SyncProcessor` or `AsyncProcessor` base classes, depending on their requirements:

- **SyncProcessor**: For CPU-bound operations that don't require async I/O
- **AsyncProcessor**: For I/O-bound operations that benefit from async/await

### 2. Creating a New Processor

1. **Choose the appropriate base class** based on your needs:
   - `SyncProcessor` for CPU-bound operations (image processing, calculations, etc.)
   - `AsyncProcessor` for I/O-bound operations (API calls, file ops, DB queries)

2. **Create a new file** in the appropriate subdirectory under `app/services/processors/`:
   - `/media/` for audio/video/image processing
   - `/text/` for text processing
   - `/workflow/` for workflow logic
   - `/io/` for file operations
   - `/validation/` for data validation

3. **Implement the processor** following this template:

```python
from typing import Any, Dict, Optional
from app.services.processors.core.base_processor import AsyncProcessor, SyncProcessor
from app.services.processors.core.metrics import MetricsCollector

class MyNewProcessor(AsyncProcessor):  # or SyncProcessor
    """Processes [describe what this processor does]."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        # Initialize any required resources here
        
    async def _process_async(self, input_data: Any, **kwargs) -> Any:
        """Async implementation of the processing logic.
        
        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters
            
        Returns:
            Processed result
            
        Raises:
            ProcessingError: If processing fails
        """
        try:
            # 1. Process the input data
            result = await self._do_processing(input_data)
            
            # 2. Return the result
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process: {str(e)}")
            raise ProcessingError(f"Failed to process: {str(e)}")
    
    async def _do_processing(self, data: Any) -> Any:
        """Internal method with the actual processing logic."""
        # Implementation details here
        pass
```

### 3. Adding the Processor to a Pipeline

```python
def create_my_pipeline() -> VideoPipeline:
    """Create and configure a video processing pipeline."""
    pipeline = VideoPipeline()
    
    # Add your processor
    pipeline.add_processor_stage(
        name="my_processor",
        processor=MyNewProcessor(),
        input_key="input_data_key",
        output_key="output_data_key",
        required_inputs=["required_input_1", "required_input_2"]
    )
    
    return pipeline
```

### 4. Testing Your Processor

1. **Unit Test** (`test/unit/test_my_processor.py`):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.processors.your_module import MyNewProcessor

@pytest.mark.asyncio
async def test_my_processor_success():
    # Setup
    processor = MyNewProcessor()
    test_input = {"key": "value"}
    
    # Mock any external dependencies
    processor._do_processing = AsyncMock(return_value={"result": "success"})
    
    # Execute
    result = await processor.process(test_input)
    
    # Verify
    assert "result" in result
    assert result["result"] == "success"
    processor._do_processing.assert_awaited_once_with(test_input)
```

2. **Integration Test** (`test/integration/test_my_processor_integration.py`):

```python
import pytest
from app.services.pipelines.video_pipeline import VideoPipeline
from app.services.processors.your_module import MyNewProcessor

@pytest.mark.asyncio
async def test_my_processor_in_pipeline():
    # Setup pipeline
    pipeline = VideoPipeline()
    pipeline.add_processor_stage(
        name="test_processor",
        processor=MyNewProcessor(),
        input_key="test_input",
        output_key="test_output"
    )
    
    # Execute
    context = {"test_input": {"key": "value"}}
    result = await pipeline.execute(context)
    
    # Verify
    assert "test_output" in result
    assert result["test_output"] is not None
```

### 5. Best Practices

- **Inheritance**: Choose between `SyncProcessor` and `AsyncProcessor` based on your needs
- **Error Handling**: Use `ProcessingError` for expected failures
- **Logging**: Use the built-in logger (`self.logger`) for important events
- **Metrics**: Utilize the metrics collector for performance tracking
- **Documentation**: Document all public methods and configuration options
- **Testing**: Cover both success and error scenarios

### 6. Example: Image Processing Processor

```python
from pathlib import Path
from PIL import Image
from app.services.processors.core.base_processor import AsyncProcessor

class ImageResizeProcessor(AsyncProcessor):
    """Resizes images to specified dimensions."""
    
    def __init__(self, width: int, height: int, metrics_collector=None):
        super().__init__(metrics_collector)
        self.width = width
        self.height = height
    
    async def _process_async(self, input_data: dict, **kwargs) -> dict:
        """Resize the input image."""
        input_path = Path(input_data["image_path"])
        output_path = input_path.parent / f"resized_{input_path.name}"
        
        with Image.open(input_path) as img:
            resized = img.resize((self.width, self.height))
            resized.save(output_path)
        
        return {
            "resized_image": str(output_path),
            "dimensions": {"width": self.width, "height": self.height}
        }
```



✅ When calling check_ai_script_hallucinations with a path starting with "C:\Workspace", convert the path to the "/workspace/" format instead. Example: "C:\Workspace\video-create\app\main.py" becomes "/workspace/video-create/app/main.py".