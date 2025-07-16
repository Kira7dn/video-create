# Video Creation Service - Development Guidelines

> **⚠️ IMPORTANT**: This document extends and clarifies the rules in `.github/copilot-instructions.md`.
> Always refer to both documents for complete guidelines.

## 📋 Table of Contents
- [Project Structure](#-project-structure)
- [Development Rules](#-development-rules)
- [Coding Standards](#-coding-standards)
- [Error Handling](#-error-handling)
- [Testing](#-testing)
- [Performance](#-performance)
- [Documentation](#-documentation)

## 🏗️ Project Structure

```
video-create/
├── app/                  # Application code
│   ├── config/           # Configuration
│   │   └── settings.py   # Single config file
│   └── services/         # Business logic
│       ├── processors/   # Processing components
│       └── pipelines/    # Workflow definitions
├── utils/                # Shared utilities
│   ├── gentle_utils.py   # Gentle API utilities
│   └── ffmpeg_utils.py   # FFmpeg utilities
└── test/                 # Tests
    ├── unit/            # Unit tests
    └── integration/     # Integration tests
```

## ⚠️ CRITICAL RULES - NEVER VIOLATE

1. **CONFIGURATION**
   - ✅ **DO**: Use only `app/config/settings.py` for all configurations
   - ❌ **NEVER**: Create additional config files or hardcode configuration values
   - 🔐 **SECURITY**: Never commit secrets or sensitive data

2. **CODE ORGANIZATION**
   - ✅ **DO**: Keep business logic in `/app/services/processors/`
   - ✅ **DO**: Place shared utilities in `/utils/` (root level)
   - ❌ **NEVER**: Mix business logic with infrastructure code
   - 🧩 **SRP**: Each processor should handle exactly one responsibility

3. **PIPELINE PATTERN**
   - ✅ **DO**: Use `VideoPipeline` for complex workflows
   - ✅ **DO**: Keep pipeline stages independent and testable
   - ❌ **NEVER**: Bypass the pipeline pattern for complex operations

2. **Code Organization**
   - Keep business logic in `/app/services/`
   - Place shared utilities in `/utils/`
   - One class per file
   - One responsibility per class/function

3. **Dependencies**
   - Minimize external dependencies
   - Pin all dependency versions
   - Document all dependencies in requirements files

## 📝 Coding Standards

### Python
- Follow PEP 8 style guide
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Use `pathlib` for file paths

### Naming Conventions
- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`

## 🚨 ERROR HANDLING & LOGGING

### ⚠️ CRITICAL RULES
- ❌ **NEVER** use bare `except` clauses
- ❌ **NEVER** silently swallow exceptions
- ✅ **ALWAYS** use specific exception types
- ✅ **ALWAYS** include context in error messages

### Best Practices
1. **Exception Handling**
   - Use custom exception types for business errors
   - Preserve stack traces when re-raising exceptions
   - Clean up resources in `finally` blocks

2. **Logging**
   - Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
   - Include relevant context in log messages
   - Use structured logging for better analysis

1. **Exceptions**
   - Use specific exception types
   - Include descriptive error messages
   - Preserve stack traces

2. **Logging**
   - Use the `logging` module
   - Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
   - Include context in log messages

3. **Resource Management**
   - Use context managers (`with` statements)
   - Clean up resources in `finally` blocks
   - Handle temporary files properly

## 🧪 TESTING & QUALITY

### ⚠️ CRITICAL RULES
- ❌ **NEVER** skip tests for "simple" code
- ✅ **ALWAYS** write tests for error conditions
- ✅ **ALWAYS** maintain test coverage > 80%

### Testing Strategy

### Unit Tests
- Test one component in isolation
- Mock external dependencies
- Follow Arrange-Act-Assert pattern
- Aim for high code coverage

### Integration Tests
- Test component interactions
- Use test containers for external services
- Clean up test data

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_module.py

# Run with coverage
pytest --cov=app --cov=utils
```

## ⚡ PERFORMANCE & RESOURCE MANAGEMENT

### ⚠️ CRITICAL RULES
- ❌ **NEVER** hardcode file paths
- ✅ **ALWAYS** use `pathlib` for file operations
- ✅ **ALWAYS** clean up temporary files

### Best Practices

1. **I/O Operations**
   - Use async/await for I/O-bound operations
   - Batch database queries
   - Use connection pooling

2. **Memory Management**
   - Use generators for large datasets
   - Avoid unnecessary object creation
   - Monitor memory usage

3. **Caching**
   - Cache expensive operations
   - Invalidate cache appropriately
   - Use appropriate cache TTL

## 📚 DOCUMENTATION & MAINTENANCE

### ⚠️ CRITICAL RULES
- ✅ **ALWAYS** document public APIs
- ❌ **NEVER** leave commented-out code
- ✅ **ALWAYS** update documentation when changing behavior

### Documentation Standards

### Code Documentation
- Document all public APIs with docstrings
- Follow Google style docstrings
- Include examples where helpful

### Project Documentation
- Keep README.md up to date
- Document setup and deployment
- Include troubleshooting guide

## 🔄 DEVELOPMENT WORKFLOW

### Pre-commit Checks
Before committing, ensure:
1. All tests pass
2. Code is properly formatted (Black)
3. Imports are sorted (isort)
4. Type checking passes (mypy)
5. No sensitive data is committed

### Code Review
- Request reviews from at least one team member
- Address all review comments before merging
- Update documentation to reflect changes

1. Create a feature branch
2. Write tests first (TDD)
3. Implement functionality
4. Run linters and tests
5. Update documentation
6. Create pull request
7. Address review comments
8. Merge to main

## 🛠️ Tools

### Linting & Formatting
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

### Pre-commit Hooks
- Install pre-commit hooks:
  ```bash
  pre-commit install
  ```
- Hooks will run on each commit

## 📦 Dependencies

- Manage dependencies using `pip-tools`
- Update `requirements.in` for new dependencies
- Run `pip-compile` to update `requirements.txt`

## 🔒 Security

- Never commit secrets
- Use environment variables for sensitive data
- Keep dependencies updated
- Regular security audits

## 📈 Monitoring

- Log all errors
- Track performance metrics
- Set up alerts for critical issues
- Monitor resource usage
