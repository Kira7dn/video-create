---
trigger: always_on
---

# 📜 Video Creation Service - Development Guidelines

> **Note**: This document outlines the architecture standards and development practices for the Video Creation Service.

## 📋 Table of Contents
- [🔧 Critical Rules](#-critical-rules)
- [🏗️ Architecture Principles](#-architecture-principles)
- [⚙️ Configuration Management](#-configuration-management)
- [🧪 Testing Guidelines](#-testing-guidelines)
- [🔧 Development Workflows](#-development-workflows)
- [📁 Project Structure](#-project-structure)

## 🔧 Critical Rules

### 🚫 Never Violate
1. **Single Configuration File**  
   - Use only `app/config/settings.py` for all configurations
   - Never create additional config files

2. **Separation of Concerns**  
   - Keep business logic separate from infrastructure code
   - Each processor should handle exactly one responsibility

3. **Error Handling**  
   - Always use specific exception types
   - Include meaningful error messages and context
   - Log all errors with stack traces

## 🏗️ Architecture Principles

### 1. Processor Design
- Each processor must inherit from `BaseProcessor`
- Follow the Single Responsibility Principle (SRP)
- Use dependency injection for testability

### 2. Pipeline Pattern
- Implement all complex workflows using `VideoPipeline`
- Each stage should be independently testable
- Support conditional execution and parallel processing

### 3. Resource Management
- Use async context managers for resources
- Implement proper cleanup in `__exit__` or `__aexit__`
- Monitor memory usage in long-running processes

```python
# Example: Basic Processor Implementation
class MyProcessor(BaseProcessor):
    async def process(self, input_data: Any, **kwargs) -> Any:
        """Process input data and return results."""
        try:
            # Processing logic here
            return processed_data
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise ProcessingError(f"Failed to process data: {e}")
```

## ⚙️ Configuration Management

### Settings Structure
```python
# settings.py
class Settings(BaseSettings):
    # Feature Flags
    feature_enabled: bool = True
    
    # Performance Settings
    max_concurrent_tasks: int = 5
    
    # API Settings
    api_timeout: int = 30
    
    # Add new settings here following the same pattern
```

### Environment Variables
```bash
# .env
FEATURE_ENABLED=true
MAX_CONCURRENT_TASKS=5
API_TIMEOUT=30
```

## 🧪 Testing Guidelines

### Unit Tests
- Test one component in isolation
- Mock external dependencies
- Follow the Arrange-Act-Assert pattern

### Integration Tests
- Test component interactions
- Use test containers for external services
- Clean up test data after execution

### Example Test
```python
@pytest.mark.asyncio
async def test_processor_happy_path():
    # Arrange
    processor = MyProcessor()
    test_data = {...}
    
    # Act
    result = await processor.process(test_data)
    
    # Assert
    assert result.expected_field == expected_value
```

## 🔧 Development Workflows

### Running Tests
```bash
# Run all tests
pytest test/

# Run specific test file
pytest test/test_my_processor.py

# Run with coverage
pytest --cov=app test/
```

### Code Quality
```bash
# Run linter
flake8 .

# Run type checking
mypy .

# Run formatter
black .
```

## 📁 Project Structure

```
app/
├── config/
│   └── settings.py      # All configuration
├── services/
│   ├── processors/      # Business logic processors
│   ├── pipelines/       # Workflow definitions
│   └── utils/           # Shared utilities
test/
├── unit/               # Unit tests
└── integration/        # Integration tests
```

## 🚀 Best Practices

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Document public APIs with docstrings

### Error Handling
- Use specific exception types
- Include context in error messages
- Log errors before raising

### Performance
- Use async/await for I/O operations
- Implement proper resource cleanup
- Monitor memory usage

### Security
- Never hardcode secrets
- Validate all inputs
- Use environment variables for sensitive data
