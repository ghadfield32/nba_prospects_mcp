# Testing Guide

Complete guide to testing the College Basketball Data API and MCP Server.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing New Tests](#writing-new-tests)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

This project includes comprehensive test suites for:

1. **REST API** - HTTP endpoints for data access
2. **MCP Server** - Model Context Protocol for LLM integration
3. **Core Library** - Underlying data functions

### Test Statistics

- **Total Test Files**: 6
- **REST API Tests**: 30+ tests covering all endpoints
- **MCP Server Tests**: 35+ tests covering tools, resources, and prompts
- **Coverage Target**: >80% code coverage

---

## Test Structure

```
tests/
├── README_TESTS.md                      # This file
├── conftest.py                          # Pytest fixtures and configuration
│
├── test_rest_api_comprehensive.py       # Complete REST API tests
├── test_mcp_server_comprehensive.py     # Complete MCP server tests
│
├── test_rest_api.py                     # Basic REST API smoke tests
└── test_mcp_server.py                   # Basic MCP server smoke tests
```

### Test Files Explained

**conftest.py**
- Shared pytest fixtures
- Custom markers (smoke, integration, slow, api, mcp)
- Test configuration
- Sample data for tests

**test_rest_api_comprehensive.py**
- All REST API endpoint tests
- Performance tests
- Error handling tests
- Caching validation
- Detailed usage examples

**test_mcp_server_comprehensive.py**
- All MCP tool tests
- Resource handler tests
- Prompt template tests
- Integration tests
- Performance validation

---

## Running Tests

### Prerequisites

1. **Install Test Dependencies**:
   ```bash
   # Install all dependencies including test tools
   uv pip install -e ".[dev]"

   # Or with pip
   pip install -e ".[dev]"
   ```

2. **Start REST API Server** (for API tests only):
   ```bash
   python -m cbb_data.servers.rest_server
   ```
   Leave running in separate terminal for API tests.

### Basic Test Commands

**Run all tests**:
```bash
pytest tests/ -v
```

**Run specific test file**:
```bash
pytest tests/test_rest_api_comprehensive.py -v
pytest tests/test_mcp_server_comprehensive.py -v
```

**Run specific test class**:
```bash
pytest tests/test_rest_api_comprehensive.py::TestHealthEndpoint -v
pytest tests/test_mcp_server_comprehensive.py::TestMCPTools -v
```

**Run specific test**:
```bash
pytest tests/test_rest_api_comprehensive.py::TestHealthEndpoint::test_health_returns_200 -v
```

### Test Categories

**Run only smoke tests** (quick validation):
```bash
pytest tests/ -m smoke -v
```

**Run only integration tests**:
```bash
pytest tests/ -m integration -v
```

**Run only API tests**:
```bash
pytest tests/ -m api -v
```

**Run only MCP tests**:
```bash
pytest tests/ -m mcp -v
```

**Skip slow tests**:
```bash
pytest tests/ -m "not slow" -v
```

### Verbose Output

**Show print statements**:
```bash
pytest tests/ -v -s
```

**Show full diff on failures**:
```bash
pytest tests/ -v --tb=long
```

**Show test execution time**:
```bash
pytest tests/ -v --durations=10
```

### Coverage Reports

**Run with coverage**:
```bash
pytest tests/ --cov=cbb_data --cov-report=html
```

**View coverage report**:
```bash
# Open htmlcov/index.html in browser
```

**Coverage by module**:
```bash
pytest tests/ --cov=cbb_data --cov-report=term-missing
```

---

## Test Categories

### Smoke Tests (@pytest.mark.smoke)

**Purpose**: Quick validation that basic functionality works

**When to run**:
- Before committing code
- After dependency updates
- Quick sanity check

**Examples**:
- Health check returns 200
- Server can be imported
- Basic endpoints respond

**Run command**:
```bash
pytest tests/ -m smoke -v
# Should complete in <30 seconds
```

### Integration Tests (@pytest.mark.integration)

**Purpose**: Test components working together

**When to run**:
- Before releasing
- After major changes
- Full system validation

**Examples**:
- End-to-end data flows
- Cache integration
- Multiple components interacting

**Run command**:
```bash
pytest tests/ -m integration -v
```

### Performance Tests (@pytest.mark.slow)

**Purpose**: Validate performance characteristics

**When to run**:
- Before releasing
- Performance regression testing
- Benchmarking

**Examples**:
- Cache speedup validation
- Query execution time
- Resource lookup speed

**Run command**:
```bash
pytest tests/ -m slow -v
# May take several minutes
```

### API Tests (@pytest.mark.api)

**Purpose**: Test REST API endpoints

**Requirements**: REST API server must be running

**Examples**:
- GET /health
- POST /datasets/{id}
- GET /recent-games/{league}

**Run command**:
```bash
# Start server first
python -m cbb_data.servers.rest_server &

# Run API tests
pytest tests/ -m api -v
```

### MCP Tests (@pytest.mark.mcp)

**Purpose**: Test MCP server components

**Requirements**: None (tests run in-process)

**Examples**:
- Tool registration
- Resource handlers
- Prompt templates

**Run command**:
```bash
pytest tests/ -m mcp -v
```

---

## Writing New Tests

### Test File Structure

```python
"""
Test Module Documentation

Describe what this module tests and how to use it.
"""

import pytest
from typing import Any


@pytest.mark.api  # Add appropriate marker
class TestFeatureName:
    """
    Test class for specific feature.

    Explain what this class tests and why it's important.
    """

    def test_specific_behavior(self, fixture_name):
        """
        Test that specific behavior works correctly.

        Detailed explanation of:
        - What this test validates
        - Why it's important
        - How to interpret results

        Example usage:
            # Show relevant code example
            response = api_client.get("/endpoint")
            assert response.status_code == 200
        """
        # Arrange
        test_data = {"key": "value"}

        # Act
        result = function_under_test(test_data)

        # Assert
        assert result is not None, "Result should not be None"
```

### Using Fixtures

**Available fixtures** (from conftest.py):

- `api_base_url` - REST API base URL
- `api_client` - Configured requests session
- `sample_filters` - Common filter combinations
- `all_leagues` - List of all leagues
- `all_datasets` - List of all datasets
- `per_modes` - List of per-modes
- `mcp_tools` - MCP tool registry
- `mcp_resources` - MCP resource registry
- `mcp_prompts` - MCP prompt registry

**Example**:
```python
def test_query_all_leagues(self, api_client, api_base_url, all_leagues):
    """Test querying data for all leagues."""
    for league in all_leagues:
        response = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json={"filters": {"league": league, "season": "2024"}}
        )
        assert response.status_code == 200
```

### Parametrized Tests

**Test same behavior with different inputs**:

```python
@pytest.mark.parametrize("league", ["NCAA-MBB", "NCAA-WBB", "EuroLeague"])
def test_schedule_for_league(self, api_client, api_base_url, league):
    """Test that schedule works for each league."""
    response = api_client.post(
        f"{api_base_url}/datasets/schedule",
        json={"filters": {"league": league, "season": "2024"}}
    )
    assert response.status_code == 200
```

### Adding Markers

**Mark tests appropriately**:

```python
@pytest.mark.smoke  # Quick smoke test
@pytest.mark.api    # Requires API server
def test_health_check(self):
    """Quick health check test."""
    pass

@pytest.mark.slow         # Takes >5 seconds
@pytest.mark.integration  # Tests multiple components
def test_full_data_pipeline(self):
    """Test complete data flow."""
    pass
```

### Documentation Standards

**Every test must have**:

1. **Docstring** explaining:
   - What it tests
   - Why it's important
   - How to interpret results

2. **Usage example** showing:
   - How to call the functionality
   - What parameters are used
   - What the expected result is

3. **Clear assertions** with:
   - Descriptive failure messages
   - Specific expected values
   - Context for debugging

**Example**:
```python
def test_player_season_stats(self, api_client, api_base_url):
    """
    Test querying player season statistics.

    This test validates that:
    - Player season endpoint accepts valid filters
    - Returns data in expected format
    - Includes required columns

    Example API call:
        POST /datasets/player_season
        {
          "filters": {
            "league": "NCAA-MBB",
            "season": "2024",
            "per_mode": "PerGame"
          },
          "limit": 10
        }

    Expected result:
        - 200 OK status
        - JSON response with data and metadata
        - At least PTS, REB, AST columns
    """
    request_data = {
        "filters": {
            "league": "NCAA-MBB",
            "season": "2024",
            "per_mode": "PerGame"
        },
        "limit": 10
    }

    response = api_client.post(
        f"{api_base_url}/datasets/player_season",
        json=request_data
    )

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    data = response.json()
    assert "data" in data, "Response missing 'data' field"
    assert "columns" in data, "Response missing 'columns' field"

    # Verify key stat columns present
    columns = data["columns"]
    required_cols = ["PTS", "REB", "AST"]
    for col in required_cols:
        assert col in columns, f"Missing required column: {col}"
```

---

## Continuous Integration

### GitHub Actions

**Recommended workflow** (.github/workflows/test.yml):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"

    - name: Run smoke tests
      run: |
        pytest tests/ -m smoke -v

    - name: Run all tests
      run: |
        pytest tests/ -v --cov=cbb_data --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

**Run smoke tests before committing**:

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/ -m smoke -q
if [ $? -ne 0 ]; then
    echo "Smoke tests failed! Commit aborted."
    exit 1
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Common Issues

**1. "Connection refused" errors in API tests**

**Problem**: REST API server not running

**Solution**:
```bash
# Start server in separate terminal
python -m cbb_data.servers.rest_server

# Or run only MCP tests
pytest tests/ -m "mcp and not api" -v
```

**2. "ModuleNotFoundError: No module named 'pytest'"**

**Problem**: Test dependencies not installed

**Solution**:
```bash
uv pip install -e ".[dev]"
```

**3. "Timeout" errors on first test run**

**Problem**: First data fetch takes longer (populating cache)

**Solution**:
- This is expected behavior
- Subsequent runs will be much faster
- Tests handle timeouts gracefully

**4. "PermissionError" on Windows**

**Problem**: File system permissions

**Solution**:
```bash
# Run as administrator or adjust permissions
pytest tests/ -v --basetemp=c:/temp/pytest
```

**5. Tests passing locally but failing in CI**

**Problem**: Environment differences

**Solution**:
- Check Python version matches
- Verify all dependencies installed
- Check environment variables
- Review CI logs for specific errors

### Debug Mode

**Run tests with debugging**:

```bash
# Drop into debugger on failure
pytest tests/ -v --pdb

# Show local variables on failure
pytest tests/ -v -l

# Very verbose output
pytest tests/ -v -vv --tb=long
```

### Test Isolation

**Run tests in isolation**:

```bash
# Run each test in separate process
pytest tests/ -v --forked

# Randomize test order
pytest tests/ -v --random-order
```

---

## Best Practices

### 1. Test Independence

**Each test should**:
- Run independently
- Not depend on other tests
- Clean up after itself
- Use fixtures for setup/teardown

### 2. Clear Assertions

**Good assertion**:
```python
assert response.status_code == 200, (
    f"Expected 200 OK, got {response.status_code}. "
    f"Response: {response.text[:200]}"
)
```

**Bad assertion**:
```python
assert response.status_code == 200
```

### 3. Test Data

**Use fixtures for test data**:
```python
@pytest.fixture
def sample_game_data():
    return {
        "league": "NCAA-MBB",
        "season": "2024",
        "team": ["Duke"]
    }

def test_schedule(self, sample_game_data):
    # Use fixture
    response = query_schedule(sample_game_data)
    assert response is not None
```

### 4. Performance

**Keep tests fast**:
- Use small data samples (limit=5)
- Mock external services when possible
- Mark slow tests with @pytest.mark.slow
- Cache expensive setup in session fixtures

### 5. Documentation

**Document everything**:
- Why test exists
- What it validates
- How to interpret failures
- Example usage

---

## Additional Resources

- **pytest Documentation**: https://docs.pytest.org/
- **REST API Guide**: [../API_GUIDE.md](../API_GUIDE.md)
- **MCP Guide**: [../MCP_GUIDE.md](../MCP_GUIDE.md)
- **Project README**: [../README.md](../README.md)

---

## Support

**Issues or questions?**
- GitHub Issues: https://github.com/ghadfield32/nba_prospects_mcp/issues
- Check existing tests for examples
- Review conftest.py for available fixtures
