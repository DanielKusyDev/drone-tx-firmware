# Testing Guide

Comprehensive guide for running tests in the Python telemetry bridge project.

## Quick Start

```bash
# Install dev dependencies
pip install -e ".[dev]"
# or with uv
uv pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html
```

## Test Organization

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── test_parser.py       # Parser unit tests (comprehensive)
└── __init__.py
```

### Test Classes in `test_parser.py`

- **TestBasicParsing** - Basic packet parsing functionality
- **TestErrorHandling** - Error cases (CRC errors, garbage data, etc.)
- **TestStatistics** - Parser statistics tracking
- **TestParametrized** - Parametrized tests with various inputs
- **TestIntegration** - Integration scenarios
- **TestPerformance** - Performance tests (marked as `@pytest.mark.slow`)
- **TestCRCUtility** - CRC calculation tests

## Running Specific Tests

### By Test Class

```bash
# Run only basic parsing tests
pytest tests/test_parser.py::TestBasicParsing -v

# Run only error handling tests
pytest tests/test_parser.py::TestErrorHandling -v

# Run only parametrized tests
pytest tests/test_parser.py::TestParametrized -v
```

### By Test Function

```bash
# Run specific test function
pytest tests/test_parser.py::TestBasicParsing::test_single_attitude_packet -v

# Run tests matching pattern
pytest -k "attitude" -v

# Run tests matching multiple patterns
pytest -k "attitude or motors" -v
```

### By Markers

```bash
# Run only unit tests (excludes integration, slow)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only parser tests
pytest -m parser

# Run slow performance tests
pytest -m slow

# Exclude slow tests (default recommended)
pytest -m "not slow"

# Run unit tests excluding slow ones
pytest -m "unit and not slow"
```

## Coverage Reports

### Generate HTML Coverage Report

```bash
# Run tests with coverage and generate HTML report
pytest --cov=app --cov-report=html

# Open coverage report in browser
# Linux/WSL
xdg-open htmlcov/index.html

# macOS
open htmlcov/index.html

# Windows
start htmlcov/index.html
```

### Generate Terminal Coverage Report

```bash
# Show coverage summary in terminal
pytest --cov=app --cov-report=term

# Show missing lines
pytest --cov=app --cov-report=term-missing
```

### Coverage by Module

```bash
# Coverage for parser only
pytest --cov=app.services.telemetry_parser

# Coverage for entire services package
pytest --cov=app.services

# Coverage for specific test file
pytest tests/test_parser.py --cov=app.services.telemetry_parser
```

## Output Options

### Verbose Output

```bash
# Detailed test output
pytest -v

# Very verbose (show print statements)
pytest -vv

# Show local variables on failure
pytest -l
```

### Show Print Statements

```bash
# Show print statements from tests
pytest -s

# Show print statements with verbose
pytest -sv
```

### Quiet Mode

```bash
# Minimal output
pytest -q

# Only show failures
pytest --tb=short
```

## Debugging Tests

### Run and Stop on First Failure

```bash
# Stop after first failure
pytest -x

# Stop after N failures
pytest --maxfail=3
```

### Drop into Debugger on Failure

```bash
# Use pdb on failure
pytest --pdb

# Use pdb on error
pytest --pdb-trace
```

### Run Last Failed Tests

```bash
# Run only tests that failed last time
pytest --lf

# Run failed tests first, then rest
pytest --ff
```

## Performance Testing

```bash
# Run only performance tests
pytest -m slow -v

# Skip performance tests (recommended for quick iteration)
pytest -m "not slow"
```

## Continuous Integration

### Recommended CI Command

```bash
# Full test suite with coverage
pytest --cov=app --cov-report=xml --cov-report=term -v
```

### GitHub Actions Example

```yaml
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=app --cov-report=xml --cov-report=term -v

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Writing New Tests

### Test File Structure

```python
"""
Module docstring explaining what's tested.
"""

import pytest
from app.services.your_module import YourClass


@pytest.fixture
def your_fixture():
    """Create test fixture."""
    return YourClass()


class TestYourFeature:
    """Test suite for your feature."""

    def test_basic_functionality(self, your_fixture):
        """Test basic functionality."""
        result = your_fixture.do_something()
        assert result == expected_value

    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (2, 4),
    ])
    def test_with_parameters(self, your_fixture, input, expected):
        """Test with multiple parameter sets."""
        assert your_fixture.process(input) == expected
```

### Async Tests

```python
import pytest


class TestAsyncFeature:
    """Test async functionality."""

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function."""
        result = await async_function()
        assert result == expected
```

### Using Markers

```python
@pytest.mark.slow
def test_performance():
    """Slow performance test."""
    pass

@pytest.mark.integration
async def test_integration_scenario():
    """Integration test."""
    pass
```

## Troubleshooting

### Import Errors

If you get import errors:

```bash
# Install package in editable mode
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### Asyncio Warnings

If you see asyncio warnings:

```bash
# Make sure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini has: asyncio_mode = auto
```

### Coverage Not Working

```bash
# Make sure pytest-cov is installed
pip install pytest-cov

# Run with explicit coverage source
pytest --cov=app tests/
```

## Best Practices

1. **Run tests frequently** during development
2. **Use `-x` flag** to stop on first failure for quick iteration
3. **Use markers** to organize tests by category
4. **Aim for >80% coverage** on critical modules
5. **Keep tests fast** - mark slow tests with `@pytest.mark.slow`
6. **Use parametrize** to test multiple scenarios efficiently
7. **Use fixtures** to avoid code duplication
8. **Write descriptive test names** that explain what's being tested

## Test Statistics

Current test coverage (as of 2025-12-14):

- **Parser**: ~90% coverage (excellent)
- **Serial Reader**: 0% coverage (needs tests)
- **Bridge**: 0% coverage (needs tests)
- **API**: 0% coverage (needs tests)

**Overall**: ~20% → Target: 80%+

## Next Steps

To improve test coverage:

1. Add serial reader tests (mock serial port)
2. Add bridge tests (mock serial reader)
3. Add API endpoint tests (use FastAPI TestClient)
4. Add WebSocket tests

See `CODE_QUALITY_ASSESSMENT.md` for detailed recommendations.
