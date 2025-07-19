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
* ✅ ALWAYS use specific exception types
* ✅ ALWAYS include context in error messages

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

   * Use custom exception types for business logic
   * Preserve stack traces when re-raising
   * Always clean up resources in `finally` blocks or with context managers

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
│   │   └── settings.py       # Single config file
│   │
│   ├── interfaces/           # Protocols / Abstract Base Interfaces
│   │   ├── video.py          # IVideoProcessor, IDownloader, etc.
│   │   ├── audio.py          # IAudioProcessor
│   │   ├── storage.py        # IUploader, IStorage
│   │   ├── validation.py     # IValidator
│   │   └── metrics.py        # IMetricsCollector
│   │
│   ├── services/             # Business logic coordination layer
│   │   ├── video_service.py              # High-level orchestration logic
│   │   ├── video_processing_service.py   # Implementation of processors
│   │   │
│   │   ├── processors/       # Processing components
│   │   │   ├── core/         # Core abstractions and base classes
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_processor.py    # BaseProcessor, BaseSyncProcessor
│   │   │   │   └── metrics.py           # MetricsCollector, ProcessingMetrics
│   │   │   │
│   │   │   ├── media/        # Media processing
│   │   │   │   ├── audio/    # Audio processing
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── processor.py     # AudioProcessor
│   │   │   │   │
│   │   │   │   ├── video/    # Video processing
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── processor.py     # Video processing
│   │   │   │   │   └── transitions.py   # TransitionProcessor
│   │   │   │   │
│   │   │   │   └── image/    # Image processing
│   │   │   │       ├── __init__.py
│   │   │   │       └── processor.py     # ImageAutoProcessor
│   │   │   │
│   │   │   ├── workflow/     # Workflow orchestration
│   │   │   │   ├── __init__.py
│   │   │   │   ├── segment.py          # SegmentProcessor
│   │   │   │   └── composer.py         # ConcatenationProcessor
│   │   │   │
│   │   │   ├── io/           # Input/Output operations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── download.py        # DownloadProcessor
│   │   │   │   └── s3_upload.py       # S3UploadProcessor
│   │   │   │
│   │   │   ├── text/         # Text processing
│   │   │   │   ├── __init__.py
│   │   │   │   ├── overlay.py         # TextOverlayProcessor
│   │   │   │   └── transcript.py      # TranscriptProcessor
│   │   │   │
│   │   │   └── validation/   # Data validation
│   │   │       ├── __init__.py
│   │   │       ├── validator.py      # ValidationProcessor
│   │   │       └── ai_validator.py   # PydanticAIValidator
│   │   │
│   │   └── pipelines/        # Workflow definitions (optional)
│   │
│   ├── api/                  # FastAPI routers and endpoints
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   └── video.py  # API endpoint for video creation
│   │       └── router.py     # API router for version v1
│   │
│   └── models/               # Pydantic models
│       ├── requests.py      # Request schemas
│       └── responses.py     # Response schemas
│
├── utils/                    # Shared utilities
│   ├── gentle_utils.py      # Gentle API utilities
│   ├── ffmpeg_utils.py      # FFmpeg utilities
│   ├── resource_manager.py  # File/directory cleanup
│   └── ...
│
└── test/                    # Tests
    ├── unit/               # Unit tests
    └── integration/        # Integration tests
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

   * ✅ Use only `app/config/settings.py` for all configurations
   * ❌ NEVER create additional config files or hardcode configuration values
   * 🔐 NEVER commit secrets or sensitive data

2. **Code Organization**

   * ✅ Keep business logic in `/app/services/processors/`
   * ✅ Place shared utilities in `/utils/`
   * ❌ NEVER mix business logic with infrastructure code
   * 🧩 Each processor must follow SRP (Single Responsibility Principle)

3. **Pipeline Pattern**

   * ✅ Use `VideoPipeline` or equivalent for complex workflows
   * ✅ Keep pipeline stages independent and testable
   * ❌ NEVER bypass the pipeline pattern for complex operations

## 🧪 Testing

### Critical Rules

* ❌ NEVER skip tests for "simple" code
* ✅ ALWAYS write tests for error conditions
* ✅ Test coverage MUST be > 80%

### Testing Strategy

#### Unit Tests

* Test one component in isolation
* Mock external dependencies
* Follow Arrange-Act-Assert pattern
* Aim for high coverage

#### Integration Tests

* Test component interactions
* Use test containers for external services
* Clean up test data after tests

#### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_module.py

# Run with coverage
pytest --cov=app --cov=utils
```

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

* ✅ All tests pass
* ✅ Code formatted with `black`
* ✅ Imports sorted with `isort`
* ✅ Type checking passes with `mypy`
* ✅ No secrets or sensitive data committed

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



✅ When calling check_ai_script_hallucinations with a path starting with "C:\Workspace", convert the path to the "/workspace/" format instead. Example: "C:\Workspace\video-create\app\main.py" becomes "/workspace/video-create/app/main.py".