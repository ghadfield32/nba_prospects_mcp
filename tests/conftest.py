"""
Pytest configuration and shared fixtures for REST API and MCP server tests.

This module provides reusable fixtures that:
1. Set up test environments
2. Provide sample data
3. Handle server lifecycle
4. Clean up resources

Usage:
    Fixtures are automatically discovered by pytest. Simply add them as
    function parameters to your test functions:

    def test_something(api_client, sample_filters):
        response = api_client.get("/datasets")
        assert response.status_code == 200
"""

import pytest
import requests
from typing import Dict, Any, List
from datetime import datetime, timedelta


# ============================================================================
# REST API Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Base URL for REST API server.

    Returns:
        str: API base URL (default: http://localhost:8000)

    Note:
        Override with environment variable: CBB_API_URL
    """
    import os
    return os.getenv("CBB_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def api_client(api_base_url):
    """
    Requests session configured for API testing.

    Provides a persistent session with:
    - Connection pooling
    - Automatic retries
    - Timeout configuration

    Returns:
        requests.Session: Configured session

    Example:
        def test_health(api_client):
            response = api_client.get("/health")
            assert response.status_code == 200
    """
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Configure retries
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    yield session

    # Cleanup
    session.close()


@pytest.fixture
def sample_filters() -> Dict[str, Any]:
    """
    Sample filter configurations for testing datasets.

    Returns:
        Dict with common filter combinations

    Example:
        def test_query(api_client, sample_filters):
            filters = sample_filters["ncaa_mbb_schedule"]
            response = api_client.post("/datasets/schedule", json=filters)
    """
    return {
        "ncaa_mbb_schedule": {
            "filters": {
                "league": "NCAA-MBB",
                "season": "2024"
            },
            "limit": 5
        },
        "ncaa_wbb_schedule": {
            "filters": {
                "league": "NCAA-WBB",
                "season": "2024"
            },
            "limit": 5
        },
        "euroleague_schedule": {
            "filters": {
                "league": "EuroLeague",
                "season": "2024"
            },
            "limit": 5
        },
        "player_season_totals": {
            "filters": {
                "league": "NCAA-MBB",
                "season": "2024",
                "per_mode": "Totals"
            },
            "limit": 10
        },
        "player_season_pergame": {
            "filters": {
                "league": "NCAA-MBB",
                "season": "2024",
                "per_mode": "PerGame"
            },
            "limit": 10
        },
        "recent_games": {
            "filters": {
                "league": "NCAA-MBB"
            },
            "days": 2
        }
    }


@pytest.fixture
def all_leagues() -> List[str]:
    """
    List of all supported leagues for parametrized testing.

    Returns:
        List[str]: All league identifiers

    Example:
        @pytest.mark.parametrize("league", all_leagues())
        def test_all_leagues(league):
            # Test runs once for each league
            pass
    """
    return ["NCAA-MBB", "NCAA-WBB", "EuroLeague"]


@pytest.fixture
def all_datasets() -> List[str]:
    """
    List of all available datasets for parametrized testing.

    Returns:
        List[str]: All dataset identifiers

    Example:
        @pytest.mark.parametrize("dataset_id", all_datasets())
        def test_all_datasets(dataset_id):
            # Test runs once for each dataset
            pass
    """
    return [
        "schedule",
        "player_game",
        "team_game",
        "pbp",  # Fixed: was "play_by_play" but dataset is registered as "pbp"
        "shots",
        "player_season",
        "team_season",
        "player_team_season"
    ]


@pytest.fixture
def per_modes() -> List[str]:
    """
    List of all per_mode aggregation options.

    Returns:
        List[str]: All per_mode values

    Example:
        @pytest.mark.parametrize("per_mode", per_modes())
        def test_aggregations(per_mode):
            # Test each aggregation mode
            pass
    """
    return ["Totals", "PerGame", "Per40"]


# ============================================================================
# MCP Server Fixtures
# ============================================================================

@pytest.fixture
def mcp_tools():
    """
    Provide all MCP tool definitions for testing.

    Returns:
        List[Dict]: List of MCP tool specifications

    Each tool has:
        - name: Tool identifier
        - description: What the tool does
        - inputSchema: JSON Schema for parameters
        - handler: Function to execute

    Example:
        def test_tool(mcp_tools):
            tool_names = [tool["name"] for tool in mcp_tools]
            assert "get_schedule" in tool_names
    """
    from cbb_data.servers.mcp import tools
    return tools.TOOLS


@pytest.fixture
def mcp_resources():
    """
    Provide all MCP resource definitions for testing.

    Returns:
        List[Dict]: List of MCP resource specifications

    Each resource has:
        - uri: Resource URI (e.g., cbb://leagues)
        - name: Human-readable name
        - description: What the resource contains
        - mimeType: Content type
        - handler: Function to fetch content

    Example:
        def test_resource(mcp_resources):
            resource_uris = [r["uri"] for r in mcp_resources]
            assert "cbb://leagues" in resource_uris
    """
    from cbb_data.servers.mcp import resources
    return resources.RESOURCES


@pytest.fixture
def mcp_prompts():
    """
    Provide all MCP prompt definitions for testing.

    Returns:
        List[Dict]: List of MCP prompt templates

    Each prompt has:
        - name: Prompt identifier
        - description: What the prompt does
        - arguments: List of argument definitions
        - template: Prompt text template

    Example:
        def test_prompts(mcp_prompts):
            prompt_names = [p["name"] for p in mcp_prompts]
            assert "top-scorers" in prompt_names
    """
    from cbb_data.servers.mcp import prompts
    return prompts.PROMPTS


@pytest.fixture
def sample_tool_params() -> Dict[str, Dict]:
    """
    Sample parameters for testing MCP tools.

    Returns:
        Dict mapping tool names to parameter sets

    Example:
        def test_tools(mcp_tools, sample_tool_params):
            params = sample_tool_params["get_schedule"]
            result = mcp_tools.tool_get_schedule(**params)
    """
    return {
        "get_schedule": {
            "league": "NCAA-MBB",
            "season": "2024",
            "limit": 5
        },
        "get_player_season_stats": {
            "league": "NCAA-MBB",
            "season": "2024",
            "per_mode": "PerGame",
            "limit": 5
        },
        "get_team_season_stats": {
            "league": "NCAA-MBB",
            "season": "2024",
            "limit": 5
        },
        "get_recent_games": {
            "league": "NCAA-MBB",
            "days": 2
        }
    }


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def sample_dates():
    """
    Sample date ranges for testing date filters.

    Returns:
        Dict with date range configurations

    Example:
        def test_dates(sample_dates):
            date_range = sample_dates["last_week"]
            # Use in filters
    """
    today = datetime.now().date()
    return {
        "today": {
            "start": today,
            "end": today
        },
        "last_week": {
            "start": today - timedelta(days=7),
            "end": today
        },
        "last_month": {
            "start": today - timedelta(days=30),
            "end": today
        }
    }


@pytest.fixture
def expected_columns():
    """
    Expected column names for each dataset.

    Returns:
        Dict mapping dataset IDs to expected columns

    Example:
        def test_columns(expected_columns):
            cols = expected_columns["schedule"]
            assert "GAME_DATE" in cols
    """
    return {
        "schedule": [
            "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM",
            "HOME_SCORE", "AWAY_SCORE", "SEASON"
        ],
        "player_game": [
            "PLAYER_NAME", "TEAM", "GAME_DATE", "PTS", "REB", "AST",
            "MIN", "FG_PCT", "FT_PCT"
        ],
        "player_season": [
            "PLAYER_NAME", "TEAM", "SEASON", "GP", "PTS", "REB", "AST",
            "MIN", "FG_PCT"
        ]
    }


# ============================================================================
# Markers
# ============================================================================

def pytest_configure(config):
    """
    Register custom pytest markers.

    Markers:
        slow: Mark test as slow running (>10s)
        integration: Mark test as integration test
        api: Mark test as REST API test
        mcp: Mark test as MCP server test
        smoke: Mark test as smoke test (quick validation)

    Usage:
        @pytest.mark.slow
        def test_large_dataset():
            pass

        Run only fast tests:
        pytest -m "not slow"

        Run only API tests:
        pytest -m api
    """
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (>10 seconds)"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "api: mark test as REST API test"
    )
    config.addinivalue_line(
        "markers",
        "mcp: mark test as MCP server test"
    )
    config.addinivalue_line(
        "markers",
        "smoke: mark test as smoke test (quick validation)"
    )
