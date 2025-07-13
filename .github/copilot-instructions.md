## OTHER_RULES

When calling check_ai_script_hallucinations with a path starting with "C:\Workspace\", convert the path to the "/workspace/" format instead. Example: "C:\Workspace\video-create\app\main.py" becomes "/workspace/video-create/app/main.py".
# Video Creation Service - Architecture & Development Guidelines

## 🤖 **AI AGENT DEVELOPMENT RULES - MANDATORY COMPLIANCE**

### ⚠️ **CRITICAL RULES - NEVER VIOLATE**

1. **NEVER create new configuration files** - Only use `app/config/settings.py`
2. **NEVER mix business logic with infrastructure code** - Keep processors separate
3. **NEVER create monolithic classes** - Follow SRP strictly
4. **NEVER bypass the pipeline pattern** - Use `VideoPipeline` for complex workflows
5. **NEVER hardcode file paths** - Use settings and temporary directories
6. **NEVER ignore error handling** - Use specific exceptions and proper logging

### 🎯 **ENHANCED ARCHITECTURE PRINCIPLES - ENFORCE STRICTLY**

1. **Single Responsibility Principle (SRP) - ENHANCED**
   - Each processor handles **ONE** specific concern only
   - Clear separation between downloading, processing, and orchestration
   - **NO** mixing of business logic and infrastructure code
   - If a class has multiple responsibilities, **MUST** split it into separate processors
   - **FOLLOW EXISTING PATTERNS**: Use `BaseProcessor`, `Validator`, `BatchProcessor`

2. **Pipeline Pattern Implementation - MANDATORY**
   - **ALL** video processing **MUST** follow the pipeline approach
   - Each stage has clear inputs/outputs and can be tested independently
   - Stages can be skipped, run conditionally, or in parallel
   - **ALWAYS** use `VideoPipeline` class for orchestrating complex workflows
   - **USE EXISTING COMPONENTS**: `PipelineContext`, `ProcessingStage`, `MetricsCollector`

3. **Configuration Management - ZERO TOLERANCE FOR VIOLATIONS**
   - **ALWAYS** use unified `app.config.settings` - **NEVER** create separate config files
   - **ALL** settings **MUST** support `.env` file overrides
   - **MUST** use Pydantic Settings for type safety and validation
   - Add new settings **ONLY** to `Settings` class in `app/config/settings.py`
   - **EXISTING SETTINGS STRUCTURE**: Follow grouping patterns (video_, audio_, text_, performance_)

4. **Error Handling - MANDATORY PATTERNS**
   - **MUST** use specific exception types: `DownloadError`, `ProcessingError`, `VideoCreationError`
   - **ALWAYS** log errors with context and stack traces
   - **MUST** provide meaningful error messages for debugging
   - **ALWAYS** use try-catch blocks with proper exception chaining
   - **USE EXISTING PATTERNS**: Follow error handling in existing processors

5. **Resource Management - CRITICAL COMPLIANCE**
   - **MUST** use async context managers for temporary directories
   - **MUST** implement proper cleanup for ALL resources
   - **MUST** monitor memory usage and implement garbage collection
   - **ALWAYS** use `managed_resources()` and `managed_temp_directory()`
   - **FOLLOW EXISTING PATTERNS**: Check `video_service.py` for resource management examples

## 🏗️ **EXISTING ARCHITECTURE COMPONENTS - DO NOT MODIFY STRUCTURE**

### **Core Services Structure - RESPECT EXISTING HIERARCHY**
```
app/services/
├── video_service.py          # Main orchestrator service (REFACTORED)
├── video_processing_service.py  # Processing coordinator (MINIMAL LOGIC)
├── download_service.py          # Asset downloading (ASYNC)
├── resource_manager.py          # Resource management (CONTEXT MANAGERS)
├── performance_utils.py         # Performance monitoring utilities
└── processors/                  # Specialized processors (NEW ARCHITECTURE)
    ├── base_processor.py        # Abstract base classes (METRICS + SRP)
    ├── validation_processor.py  # Input validation (COMPREHENSIVE)
    ├── audio_processor.py       # Audio composition (STATIC METHODS)
    ├── text_overlay_processor.py # Text overlays (FADE EFFECTS)
    ├── transition_processor.py  # Video transitions (EFFECTS)
    ├── segment_processor.py     # Segment creation (IMAGE/VIDEO)
    ├── concatenation_processor.py # Video concatenation (FFMPEG)
    ├── batch_processor.py       # Batch operations (CONCURRENCY)
    ├── image_auto_processor.py  # AI-powered image validation & replacement (PYDANTIC-AI)
    ├── pydantic_ai_validator.py # PydanticAI validation components
    └── pipeline.py              # Pipeline pattern (ASYNC STAGES)
```

### **Configuration System - SINGLE SOURCE OF TRUTH**
```
app/config/
└── settings.py                  # Unified Pydantic Settings (150+ SETTINGS)
```

### **Exception Handling - EXISTING STRUCTURE**
```
app/core/
└── exceptions.py                # Custom exception classes (ENHANCED)
```

## 🔧 **PROCESSOR DEVELOPMENT - FOLLOW EXISTING PATTERNS**

### **Creating New Processors - USE EXISTING TEMPLATES**

1. **MUST Inherit from Base Classes - EXISTING PATTERN**
```python
from app.services.processors.base_processor import BaseProcessor, ProcessingStage

class MyProcessor(BaseProcessor):
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
    
    def process(self, input_data: Any, **kwargs) -> Any:
        metric = self._start_processing(ProcessingStage.MY_STAGE)
        try:
            # Your processing logic here
            result = self._do_processing(input_data)
            self._end_processing(metric, success=True, items_processed=1)
            return result
        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise ProcessingError(f"Processing failed: {e}") from e
```

2. **MUST Implement Validation - EXISTING PATTERN**
```python
from app.services.processors.base_processor import Validator, ValidationResult

class MyValidator(Validator):
    def validate(self, data: Any) -> ValidationResult:
        result = ValidationResult()
        
        if not self._is_valid(data):
            result.add_error("Invalid data format")
        
        return result
```

3. **MUST Use Batch Processing - EXISTING IMPLEMENTATION**
```python
from app.services.processors.batch_processor import SegmentBatchProcessor

batch_processor = SegmentBatchProcessor(
    processor_func=MyProcessor.process_item,
    max_concurrent=settings.performance_max_concurrent_segments,
    metrics_collector=self.metrics_collector
)

results = batch_processor.process_batch(items, temp_dir=temp_dir)
```

### **Pipeline Integration - FOLLOW EXISTING ARCHITECTURE**

1. **Add Stages to Pipeline - EXISTING PATTERN**
```python
from app.services.processors.pipeline import VideoPipeline

def build_my_pipeline(self) -> VideoPipeline:
    pipeline = VideoPipeline(self.metrics_collector)
    
    # Function stage - FOLLOW EXISTING PATTERN
    pipeline.add_function_stage(
        name="my_stage",
        func=self._my_processing_function,
        output_key="my_result",
        required_inputs=["input_data"]
    )
    
    # Processor stage - FOLLOW EXISTING PATTERN
    pipeline.add_processor_stage(
        name="validation",
        processor=self.validator,
        input_key="raw_data",
        output_key="validated_data"
    )
    
    return pipeline
```

2. **Execute Pipeline - STANDARD IMPLEMENTATION**
```python
context = PipelineContext(
    data={"input_data": input_data},
    temp_dir=temp_dir,
    video_id=video_id,
    metadata={}
)

result_context = await pipeline.execute(context)
final_result = result_context.get("final_output")
```

## 📝 **CONFIGURATION GUIDELINES - FOLLOW EXISTING STRUCTURE**

### **Adding New Settings - EXTEND EXISTING PATTERNS**

1. **Add to Settings Class - FOLLOW GROUPING PATTERNS**
```python
# app/config/settings.py
class Settings(BaseSettings):
    # ...existing 150+ settings...
    
    # NEW FEATURE SETTINGS - FOLLOW NAMING CONVENTION
    my_feature_enabled: bool = True
    my_feature_timeout: int = 30
    my_feature_max_items: int = 100
    
    # GROUP WITH PREFIX - FOLLOW EXISTING PATTERNS
    audio_new_feature_volume: float = 0.5
    video_new_feature_quality: str = "high"
    performance_new_feature_max_concurrent: int = 5
```

2. **Add to .env Documentation - MAINTAIN CONSISTENCY**
```bash
# .env
# New Feature Settings - FOLLOW EXISTING COMMENTS
MY_FEATURE_ENABLED=true
MY_FEATURE_TIMEOUT=30
AUDIO_NEW_FEATURE_VOLUME=0.5
```

3. **Use in Code - FOLLOW EXISTING IMPORT PATTERN**
```python
from app.config.settings import settings

# Access settings - FOLLOW EXISTING USAGE
if settings.my_feature_enabled:
    timeout = settings.my_feature_timeout
    volume = settings.audio_new_feature_volume
```

## 🧪 **TESTING GUIDELINES - FOLLOW EXISTING TEST STRUCTURE**

### **Processor Testing - USE EXISTING TEST PATTERNS**
```python
import pytest
from app.services.processors.my_processor import MyProcessor

class TestMyProcessor:
    def test_process_valid_input(self):
        processor = MyProcessor()
        result = processor.process(valid_input)
        assert result is not None
    
    def test_process_invalid_input(self):
        processor = MyProcessor()
        with pytest.raises(ProcessingError):
            processor.process(invalid_input)
```

### **Pipeline Testing - FOLLOW ASYNC PATTERNS**
```python
@pytest.mark.asyncio
async def test_pipeline_execution():
    pipeline = build_test_pipeline()
    context = PipelineContext(
        data={"test_data": test_input},
        temp_dir="/tmp/test",
        video_id="test",
        metadata={}
    )
    
    result = await pipeline.execute(context)
    assert result.get("final_output") is not None
```

### **Integration Testing - USE EXISTING MOCK PATTERNS**
```python
@pytest.mark.asyncio
async def test_full_video_creation():
    service = VideoCreationService()
    
    # Mock external dependencies - FOLLOW EXISTING PATTERNS
    with patch('app.services.download_service.DownloadService'):
        result = await service.create_video_from_json(test_data)
        assert os.path.exists(result)
```

## 🧪 **DEVELOPMENT WORKFLOWS - ESSENTIAL COMMANDS**

### **Testing Workflow - FOLLOW THESE PATTERNS**
```powershell
# Run all tests (68 tests total)
python -m pytest test/ -v

# Run specific test categories
python -m pytest test/test_refactored_architecture.py -v    # Architecture tests
python -m pytest test/test_ai_keyword_extraction.py -v     # AI integration tests
python -m pytest test/test_text_overlay.py -v              # Text overlay tests
python -m pytest test/test_transition_*.py -v              # Transition effect tests

# Run integration tests (requires running server)
python -m pytest test/test_integration.py -v               # API integration tests

# Test collection only (see test structure)
python -m pytest test/ --collect-only
```

### **Development Setup - REQUIRED STEPS**
```powershell
# 1. Install dependencies
pip install -r requirements.dev.txt

# 2. Run development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Docker development
docker-compose up --build    # Full stack with ngrok tunnel
docker build -t video-create .    # Build production image

# 4. Test AI features (requires OpenAI API key)
python demo_ai_keywords.py    # Demo PydanticAI keyword extraction
```

### **Environment Configuration - MANDATORY**
```bash
# .env file required for AI features
OPENAI_API_KEY=your-api-key-here
AI_KEYWORD_EXTRACTION_ENABLED=true
AI_PYDANTIC_MODEL=gpt-3.5-turbo
AI_MAX_KEYWORDS_PER_PROMPT=5

# Performance settings
PERFORMANCE_MAX_CONCURRENT_SEGMENTS=3
PERFORMANCE_MAX_MEMORY_MB=2048
DOWNLOAD_MAX_CONCURRENT=5
```

### **Key Development Files - UNDERSTAND THESE**
```
test/input_sample.json           # Sample video creation request format
demo_ai_keywords.py             # PydanticAI keyword extraction demo
utils/image_utils.py            # Image processing utilities (smart padding)
pytest.ini                      # Test configuration (pythonpath, maxfail)
requirements.prod.txt           # Production dependencies (includes pydantic-ai)
```

## 🚀 **PERFORMANCE GUIDELINES - RESPECT EXISTING LIMITS**

### **Memory Management - USE EXISTING INFRASTRUCTURE**
- **MUST** use `managed_resources()` context manager for resource cleanup
- **MUST** implement garbage collection at strategic points
- **MUST** monitor memory usage in batch operations
- **MUST** use streaming for large file operations
- **FOLLOW EXISTING**: Check `performance_max_memory_mb` setting

### **Concurrency - RESPECT EXISTING LIMITS**
- **MUST** respect `performance_max_concurrent_segments` setting
- **MUST** use semaphores for rate limiting
- **MUST** implement proper async/await patterns
- **NEVER** block operations in async contexts
- **FOLLOW EXISTING**: Check `download_max_concurrent` for download operations

### **Monitoring - USE EXISTING METRICS SYSTEM**
- **ALWAYS** use `MetricsCollector` for performance tracking
- **MUST** log processing durations and item counts
- **MUST** monitor error rates and failure patterns
- **MUST** implement health checks for external dependencies
- **FOLLOW EXISTING**: Check `metrics_collector.get_summary()` usage

## ✅ **CODE QUALITY STANDARDS - ENFORCE STRICTLY**

### **Required Practices - NON-NEGOTIABLE**
1. **Type Hints**: ALL functions MUST have proper type annotations
2. **Docstrings**: ALL public methods NEED comprehensive docstrings
3. **Error Handling**: Use specific exception types with meaningful messages
4. **Logging**: Use structured logging with appropriate levels
5. **Testing**: Minimum 80% test coverage for new code
6. **Validation**: Validate ALL inputs at service boundaries

### **Forbidden Practices - IMMEDIATE REJECTION**
1. **❌ NO** hardcoded file paths - use settings
2. **❌ NO** direct file system operations without resource management
3. **❌ NO** mixing async and sync code inappropriately
4. **❌ NO** creating new configuration files - extend settings.py
5. **❌ NO** catching generic Exception without re-raising
6. **❌ NO** blocking operations in async contexts
7. **❌ NO** monolithic classes - follow SRP
8. **❌ NO** bypassing the pipeline pattern for complex workflows
9. **❌ NO** direct OpenAI API calls - use PydanticAI Agents

## 🚨 **VIOLATION CONSEQUENCES - AUTOMATED REJECTION**

- **Configuration Rule Violation**: Code will be rejected - must use settings.py
- **SRP Violation**: Immediate refactor required - split into processors
- **Pipeline Pattern Bypass**: Must implement proper pipeline stages
- **Error Handling Missing**: Code will not be accepted - add proper exceptions
- **Testing Below 80%**: Must add comprehensive tests with mocks
- **Hardcoded Values**: Must use settings system - no exceptions

## 🔍 **AUTOMATED VALIDATION CHECKLIST - AI AGENT MUST VERIFY**

### **Pre-Code Review (MANDATORY)**
1. **Import Analysis**: Check all imports use existing architecture patterns
2. **File Structure**: Verify new files follow established directory structure
3. **Configuration Usage**: Ensure all settings come from `app.config.settings`
4. **Error Handling**: Validate proper exception types are used
5. **Resource Management**: Check for context managers and cleanup

### **Code Quality Gates (AUTOMATIC FAIL)**
1. **Type Annotations**: All functions MUST have complete type hints
2. **Docstring Coverage**: All public methods need docstrings with examples
3. **Exception Specificity**: Generic `Exception` catching is forbidden
4. **Async Compliance**: No blocking operations in async contexts
5. **Memory Management**: All resources must have cleanup mechanisms

### **Architecture Compliance (ZERO TOLERANCE)**
1. **Processor Inheritance**: All processors MUST inherit from `BaseProcessor`
2. **Pipeline Integration**: Complex workflows MUST use `VideoPipeline`
3. **Settings Integration**: ALL configuration MUST use unified settings
4. **Metrics Collection**: Performance tracking is MANDATORY
5. **Testing Coverage**: Unit tests required for all new code

## 📋 **AI AGENT CHECKLIST - BEFORE ANY CODE CHANGE**

### **Architecture Compliance**
- [ ] Does this follow SRP (Single Responsibility Principle)?
- [ ] Am I using the existing configuration in `settings.py`?
- [ ] Do I need to create a new processor or extend existing one?
- [ ] Should this be part of a pipeline workflow?
- [ ] Have I added proper error handling with specific exceptions?

### **Implementation Quality**
- [ ] Am I using resource management properly?
- [ ] Have I added metrics tracking with `MetricsCollector`?
- [ ] Are there comprehensive tests with proper mocking?
- [ ] Is documentation updated and consistent?
- [ ] Does this maintain backward compatibility?

### **Performance & Monitoring**
- [ ] Have I respected concurrency limits from settings?
- [ ] Am I using async patterns correctly?
- [ ] Have I added proper logging with context?
- [ ] Are memory resources managed properly?
- [ ] Have I tested error scenarios?

## ---

## 📋 **SUMMARY FOR AI AGENTS**

- Follow strict separation of concerns and pipeline architecture.
- Use only the provided configuration, error handling, and resource management patterns.
- Reference sample input and test files for data formats and edge cases.
- Always use project-specific exceptions and logging.
- For AI features, ensure environment variables and settings are configured.

---

**Feedback Request:**
If any section is unclear, incomplete, or missing important patterns, please provide feedback or examples. This will help further refine the copilot instructions for maximum productivity and compliance.

## 🔒 **VALIDATION ENFORCEMENT RULES - ZERO TOLERANCE**

### **File Structure Violations**
- ❌ Creating files outside `app/services/processors/` for processing logic
- ❌ Adding configuration files outside `app/config/settings.py`
- ❌ Bypassing the existing directory structure
- ❌ Creating monolithic service files instead of using processors

### **Code Quality Violations**
- ❌ Missing type hints on any function parameter or return value
- ❌ Missing docstrings on public methods or classes
- ❌ Using generic `Exception` instead of specific exception types
- ❌ Hardcoded paths, URLs, or configuration values
- ❌ Blocking operations in async functions
- ❌ Missing resource cleanup (no context managers)

### **Architecture Pattern Violations**
- ❌ Processing logic not inheriting from `BaseProcessor`
- ❌ Complex workflows not using `VideoPipeline`
- ❌ Missing metrics collection with `MetricsCollector`
- ❌ Configuration not using `app.config.settings`
- ❌ Missing proper error handling with exception chaining

### **Testing Violations**
- ❌ New code without corresponding unit tests
- ❌ Tests without proper mocking of dependencies
- ❌ Missing async test patterns for async code
- ❌ Tests that don't follow existing patterns
- ❌ Integration tests without proper environment setup

### **Performance Violations**
- ❌ Operations exceeding configured concurrency limits
- ❌ Memory leaks or missing garbage collection
- ❌ Missing timeout handling for external operations
- ❌ Inefficient resource usage patterns
- ❌ Missing performance monitoring and logging

## 🎯 **ENFORCEMENT PRIORITY ORDER**

1. **CRITICAL** - Configuration and file structure compliance
2. **HIGH** - Architecture pattern adherence (SRP, Pipeline, etc.)
3. **HIGH** - Error handling and resource management
4. **MEDIUM** - Code quality and documentation standards
5. **MEDIUM** - Testing coverage and patterns
6. **LOW** - Performance optimizations and monitoring

## 📞 **ESCALATION PROTOCOL**

If an AI agent encounters any pattern violations:

1. **STOP** - Do not proceed with the change
2. **IDENTIFY** - Clearly specify which rule(s) are being violated
3. **SUGGEST** - Provide specific examples of correct patterns to follow
4. **REQUIRE** - Demand compliance before any code changes
5. **VALIDATE** - Run tests to ensure compliance after changes

**Remember: The architecture is designed for maintainability, scalability, and reliability. Every violation weakens these principles! 🛡️**

---

*Last Updated: July 11, 2025*  
*Architecture Version: 2.1 - PydanticAI Integration Complete*  
*Test Status: AI Keyword Extraction Fully Tested*  
*AI Agent Compliance: Mandatory PydanticAI for all AI integrations*

## 🔗 **DATA FLOW & INTEGRATION POINTS**

- **Input Format:**
  - All video creation requests use a JSON format (see `test/input_sample.json`).
  - Segments may include images, videos, voice_over, text_over, and transitions.
  - Text overlays support advanced attributes (font, color, position, box, etc).

- **External Dependencies:**
  - **Pixabay API** for image search (see `utils/image_utils.py`, `image_auto_processor.py`).
  - **PydanticAI** for AI-powered keyword extraction and validation (requires API key).
  - ** OpenCV, Pillow** for video/image/audio processing.
  - **FastAPI** for API layer, with custom middleware and exception handling.

- **Cross-Component Communication:**
  - All processors communicate via `PipelineContext` (see `pipeline.py`).
  - Resource management is handled via async context managers (`resource_manager.py`).
  - Metrics and error handling are propagated through `MetricsCollector` and custom exceptions (`core/exceptions.py`).

- **Configuration:**
  - All settings are managed in `app/config/settings.py` (Pydantic Settings, .env overrides).
  - Never create new config files; always extend the `Settings` class.

- **Logging:**
  - Logs are written to both console and `data/app.log` (see `main.py`).
  - Use structured logging for error context and stack traces.

## 🧩 **PROJECT-SPECIFIC CONVENTIONS & PATTERNS**

- **Single Responsibility Principle (SRP):**
  - Each processor/class must handle only one concern (see `base_processor.py`).
  - Split multi-responsibility logic into separate processors.

- **Pipeline Pattern:**
  - All workflows use the pipeline approach (`pipeline.py`, `VideoPipeline`).
  - Stages are modular, testable, and can be skipped/parallelized.

- **Error Handling:**
  - Use only project-specific exceptions: `DownloadError`, `ProcessingError`, `VideoCreationError`, `FileValidationError`.
  - Always log errors with full context and stack trace.

- **Resource Management:**
  - Use async context managers for temp directories and resource cleanup (`resource_manager.py`).
  - Monitor memory usage and clean up resources after processing.

- **AI Integration:**
  - Use PydanticAI for keyword extraction and validation (see `image_auto_processor.py`).
  - Configure via `.env` and `settings.py` only.

- **Testing Patterns:**
  - Use parameterized and coroutine tests for processors and integration (see `test/test_refactored_architecture.py`, `test/test_image_auto_processor.py`).
  - Test input/output formats and error handling explicitly.
