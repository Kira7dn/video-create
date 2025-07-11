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
   - **FOLLOW EXISTING PATTERNS**: Check `video_service_v2.py` for resource management examples

## 🏗️ **EXISTING ARCHITECTURE COMPONENTS - DO NOT MODIFY STRUCTURE**

### **Core Services Structure - RESPECT EXISTING HIERARCHY**
```
app/services/
├── video_service_v2.py          # Main orchestrator service (REFACTORED)
├── video_processing_service.py  # Processing coordinator (MINIMAL LOGIC)
├── download_service.py          # Asset downloading (ASYNC)
├── resource_manager.py          # Resource management (CONTEXT MANAGERS)
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
    service = VideoCreationServiceV2()
    
    # Mock external dependencies - FOLLOW EXISTING PATTERNS
    with patch('app.services.download_service.DownloadService'):
        result = await service.create_video_from_json(test_data)
        assert os.path.exists(result)
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

## 🛠️ **MANDATORY CODE PATTERNS - ENFORCE STRICTLY**

### **Error Handling Pattern**
```python
# REQUIRED: Always use specific exception types with context
from app.core.exceptions import ProcessingError, DownloadError, VideoCreationError

try:
    result = some_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise ProcessingError(f"Processing failed: {e}") from e
```

### **Resource Management Pattern**
```python
# REQUIRED: Always use async context managers
from app.services.resource_manager import managed_temp_directory

async def some_function():
    async with managed_temp_directory() as temp_dir:
        # Your processing logic here
        result = await process_data(temp_dir)
        return result
    # Cleanup happens automatically
```

### **Settings Usage Pattern**
```python
# REQUIRED: Always import and use unified settings
from app.config.settings import settings

# Use settings with proper grouping
timeout = settings.download_timeout
quality = settings.video_quality
max_concurrent = settings.performance_max_concurrent_segments
```

### **Processor Implementation Pattern**
```python
# REQUIRED: Always inherit from BaseProcessor
from app.services.processors.base_processor import BaseProcessor, ProcessingStage

class MyProcessor(BaseProcessor):
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
    
    async def process(self, input_data: Any, **kwargs) -> Any:
        metric = self._start_processing(ProcessingStage.MY_STAGE)
        try:
            result = await self._do_processing(input_data)
            self._end_processing(metric, success=True, items_processed=1)
            return result
        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise ProcessingError(f"Processing failed: {e}") from e
```

### **Pipeline Usage Pattern**
```python
# REQUIRED: Use VideoPipeline for complex workflows
from app.services.processors.pipeline import VideoPipeline, PipelineContext

async def build_processing_pipeline(self) -> VideoPipeline:
    pipeline = VideoPipeline(self.metrics_collector)
    
    pipeline.add_processor_stage(
        name="validation",
        processor=self.validation_processor,
        input_key="raw_data",
        output_key="validated_data"
    )
    
    pipeline.add_function_stage(
        name="processing",
        func=self._process_data,
        output_key="processed_data",
        required_inputs=["validated_data"]
    )
    
    return pipeline
```

## 🎯 **EXISTING FEATURES TO RESPECT**

### **Current Capabilities - DO NOT BREAK**
- ✅ Text overlay with fade-in/fade-out effects
- ✅ Multiple transition types (fade, slide, zoom, dissolve)
- ✅ Audio composition with background music
- ✅ Image smart padding and processing
- ✅ Batch segment processing with concurrency
- ✅ Pipeline-based video creation workflow
- ✅ Comprehensive input validation
- ✅ Resource management and cleanup
- ✅ Performance metrics and monitoring
- ✅ Async download service
- ✅ Unified configuration system
- ✅ **PydanticAI-powered keyword extraction** (ImageAutoProcessor)
- ✅ **AI-enhanced image search** with structured outputs
- ✅ **Type-safe AI integrations** with automatic validation

### **Test Coverage - MAINTAIN STANDARDS**
- ✅ **13/13 refactored architecture tests passing** - Core pipeline and processor tests
- ✅ **35/42 total tests passing** - Unit and logic tests all pass
- ✅ Integration tests for video creation API (require running server)
- ✅ Text overlay validation and processing
- ✅ Error handling and edge cases
- ✅ Pipeline execution and stage management
- ✅ Processor unit tests and mocking
- ⚠️ **Integration tests fail without running server** - Expected behavior

---

## 🤖 **PYDANTICAI INTEGRATION GUIDELINES (UPDATED - PREFERRED APPROACH)**

### **When to Use PydanticAI**
- **PRIMARY CHOICE** for all AI integrations: keyword extraction, schema validation, content analysis
- Use PydanticAI instead of direct OpenAI API calls for type safety and structured outputs
- Ideal for any AI task requiring structured data validation and response parsing
- **REPLACE** direct OpenAI API usage with PydanticAI Agents for better maintainability

### **How to Integrate PydanticAI (MANDATORY PATTERN)**
1. **Define Pydantic Models** for structured AI responses:
```python
from pydantic import BaseModel
from typing import List

class AIProcessingResult(BaseModel):
    result_data: List[str]
    primary_item: str
    confidence_score: float = 0.0
    processing_strategy: str = "default"
```

2. **Create PydanticAI Agents** in processor `__init__`:
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

def _init_ai_agent(self):
    if self.ai_api_key and settings.ai_feature_enabled:
        model = OpenAIModel(model_name=settings.ai_model_name)
        self.ai_agent = Agent(
            model=model,
            result_type=AIProcessingResult,
            system_prompt="Your AI task description..."
        )
```

3. **Implement Async AI Processing**:
```python
async def _ai_process_data(self, input_data: str) -> List[str]:
    if not self.ai_agent:
        return [input_data]  # Fallback
    
    try:
        result = await self.ai_agent.run(
            user_prompt=f"Process: {input_data}",
            message_history=[]
        )
        return result.data.result_data
    except Exception as e:
        logger.warning(f"AI processing failed: {e}")
        return [input_data]  # Graceful fallback
```

4. **Pipeline Integration**:
```python
# Add async AI processor stages to pipeline
pipeline.add_processor_stage(
    name="ai_processing",
    processor=self.ai_processor,
    input_key="raw_data",
    output_key="processed_data"
)
```

### **Configuration Settings (FOLLOW EXISTING PATTERNS)**
```python
# app/config/settings.py - ADD TO EXISTING GROUPS
class Settings(BaseSettings):
    # AI Integration Settings (NEW SECTION)
    openai_api_key: Optional[str] = None
    ai_keyword_extraction_enabled: bool = True
    ai_model_name: str = "gpt-3.5-turbo"
    ai_keyword_extraction_timeout: int = 10
    ai_max_keywords_per_prompt: int = 5
    
    # Feature-specific AI settings
    ai_content_analysis_enabled: bool = True
    ai_schema_validation_enabled: bool = True
```

### **Dependencies (UPDATED)**
```python
# requirements.prod.txt - REMOVE openai, USE pydantic-ai
pydantic-ai  # PREFERRED - includes OpenAI integration
# openai==1.58.1  # REMOVE - replaced by pydantic-ai
```

### **Testing PydanticAI (MANDATORY PATTERNS)**
```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

@patch('app.services.processors.my_processor.Agent')
@patch('app.services.processors.my_processor.OpenAIModel')
def test_ai_processing_success(self, mock_openai_model, mock_agent):
    # Mock PydanticAI Agent response
    mock_result = Mock()
    mock_result.data = AIProcessingResult(
        result_data=["processed1", "processed2"],
        primary_item="processed1",
        confidence_score=0.95
    )
    
    mock_agent_instance = AsyncMock()
    mock_agent_instance.run.return_value = mock_result
    mock_agent.return_value = mock_agent_instance
    
    processor = MyProcessor(ai_api_key="test-key")
    
    import asyncio
    result = asyncio.run(processor._ai_process_data("input"))
    assert result == ["processed1", "processed2"]
```

### **Architecture Benefits of PydanticAI**
✅ **Type Safety**: Compile-time validation for AI responses  
✅ **Structured Output**: No manual string parsing required  
✅ **Async Native**: Built-in async/await support  
✅ **Error Handling**: Automatic validation and graceful fallbacks  
✅ **Model Agnostic**: Easy switching between AI providers  
✅ **Pydantic Integration**: Seamless with existing validation patterns

---

## 🏆 **ARCHITECTURE BENEFITS ACHIEVED - MAINTAIN THESE**

✅ **Maintainability**: Clear separation of concerns, single responsibility
✅ **Scalability**: Pipeline pattern allows easy addition of new processing stages  
✅ **Testability**: Each component can be tested independently
✅ **Reliability**: Robust error handling and resource management
✅ **Performance**: Metrics collection and optimization opportunities
✅ **Flexibility**: Easy configuration and environment-based overrides
✅ **Observability**: Comprehensive logging and monitoring capabilities
✅ **Modularity**: Processor-based architecture with clear interfaces
✅ **Async Support**: Full async/await pattern implementation
✅ **Resource Safety**: Proper cleanup and memory management

**This architecture is production-ready and follows industry best practices! 🚀**

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
