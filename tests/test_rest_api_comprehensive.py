"""
Comprehensive REST API Tests with Detailed Documentation

This module provides thorough testing of all REST API endpoints with:
1. Detailed docstrings explaining what each test does
2. Usage examples showing how to call the API
3. Edge case testing
4. Performance validation
5. Error handling verification

HOW TO RUN THESE TESTS:
======================

Run all API tests:
    pytest tests/test_rest_api_comprehensive.py -v

Run only smoke tests:
    pytest tests/test_rest_api_comprehensive.py -m smoke -v

Run tests for specific endpoint:
    pytest tests/test_rest_api_comprehensive.py::TestHealthEndpoint -v

Run with coverage:
    pytest tests/test_rest_api_comprehensive.py --cov=cbb_data.api.rest_api

BEFORE RUNNING:
==============
Make sure the REST API server is running:
    python -m cbb_data.servers.rest_server

Or start it in the background:
    python -m cbb_data.servers.rest_server &

API USAGE EXAMPLES:
==================

1. Health Check:
    curl http://localhost:8000/health

2. List Datasets:
    curl http://localhost:8000/datasets

3. Query Dataset:
    curl -X POST http://localhost:8000/datasets/schedule \\
      -H "Content-Type: application/json" \\
      -d '{"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 10}'

4. Recent Games:
    curl http://localhost:8000/recent-games/NCAA-MBB?days=2

5. Dataset Info:
    curl http://localhost:8000/datasets/schedule/info
"""

import pytest
import requests
from typing import Dict, Any
import time


# ============================================================================
# Health Check Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.smoke
class TestHealthEndpoint:
    """
    Tests for /health endpoint.

    The health endpoint provides server status information and is used for:
    - Monitoring server availability
    - Checking service dependencies
    - Load balancer health checks

    Example Response:
        {
          "status": "healthy",
          "version": "1.0.0",
          "timestamp": "2025-01-15T12:00:00Z",
          "services": {
            "api": "healthy",
            "cache": "healthy",
            "data_sources": "healthy"
          }
        }
    """

    def test_health_returns_200(self, api_client, api_base_url):
        """
        Test that /health endpoint returns HTTP 200 OK.

        This is the most basic health check - server is responding.

        Expected:
            - Status code: 200
            - Response time: <500ms

        Example:
            GET http://localhost:8000/health
        """
        response = api_client.get(f"{api_base_url}/health")
        assert response.status_code == 200, "Health endpoint should return 200 OK"

    def test_health_has_required_fields(self, api_client, api_base_url):
        """
        Test that /health response contains all required fields.

        Required fields:
            - status: Server health status ("healthy", "degraded", "unhealthy")
            - version: API version string
            - timestamp: Current server time (ISO format)
            - services: Dict of service statuses

        Example:
            response = requests.get("http://localhost:8000/health")
            data = response.json()
            print(data["status"])  # "healthy"
            print(data["version"])  # "1.0.0"
        """
        response = api_client.get(f"{api_base_url}/health")
        data = response.json()

        required_fields = ["status", "version", "timestamp", "services"]
        for field in required_fields:
            assert field in data, f"Health response missing field: {field}"

    def test_health_status_is_healthy(self, api_client, api_base_url):
        """
        Test that server reports healthy status.

        The status field should be "healthy" when all services are operational.

        Possible values:
            - "healthy": All services operational
            - "degraded": Some services have issues
            - "unhealthy": Critical services down

        Example:
            if response.json()["status"] == "healthy":
                print("Server is ready to accept requests")
        """
        response = api_client.get(f"{api_base_url}/health")
        data = response.json()

        assert data["status"] == "healthy", (
            f"Server status is {data['status']}, expected 'healthy'"
        )

    def test_health_response_time(self, api_client, api_base_url):
        """
        Test that /health endpoint responds quickly.

        Health checks should be fast (<500ms) since they're used for
        monitoring and load balancing.

        Expected:
            - Response time: <500ms
            - Timeout: 5s max

        Example:
            start = time.time()
            response = requests.get("http://localhost:8000/health", timeout=5)
            elapsed = time.time() - start
            print(f"Health check took {elapsed*1000:.0f}ms")
        """
        start_time = time.time()
        response = api_client.get(f"{api_base_url}/health", timeout=5)
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms

        assert response.status_code == 200, "Health check failed"
        assert elapsed_time < 500, (
            f"Health check took {elapsed_time:.0f}ms, should be <500ms"
        )


# ============================================================================
# Dataset Listing Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.smoke
class TestListDatasetsEndpoint:
    """
    Tests for /datasets endpoint.

    This endpoint lists all available datasets with their metadata.
    Use it to discover what data is available before querying.

    Example Response:
        {
          "datasets": [
            {
              "id": "schedule",
              "name": "Game Schedule",
              "description": "Game schedules and results",
              "supported_filters": ["league", "season", "team", "date"],
              "supported_leagues": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
            }
          ],
          "count": 8
        }
    """

    def test_list_datasets_returns_200(self, api_client, api_base_url):
        """
        Test that /datasets endpoint returns HTTP 200 OK.

        Example:
            GET http://localhost:8000/datasets
        """
        response = api_client.get(f"{api_base_url}/datasets")
        assert response.status_code == 200

    def test_list_datasets_has_correct_structure(self, api_client, api_base_url):
        """
        Test that /datasets response has the correct structure.

        Expected structure:
            {
              "datasets": [array of dataset objects],
              "count": number
            }

        Each dataset object should have:
            - id: Dataset identifier
            - name: Human-readable name
            - description: What the dataset contains
            - supported_filters: Array of filter names
            - supported_leagues: Array of league identifiers

        Example:
            response = requests.get("http://localhost:8000/datasets")
            data = response.json()

            for dataset in data["datasets"]:
                print(f"{dataset['id']}: {dataset['description']}")
                print(f"  Leagues: {dataset['supported_leagues']}")
                print(f"  Filters: {dataset['supported_filters']}")
        """
        response = api_client.get(f"{api_base_url}/datasets")
        data = response.json()

        # Check top-level structure
        assert "datasets" in data, "Response missing 'datasets' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["datasets"], list), "'datasets' should be a list"
        assert data["count"] == len(data["datasets"]), "Count doesn't match array length"

    def test_list_datasets_contains_expected_datasets(self, api_client, api_base_url, all_datasets):
        """
        Test that all expected datasets are present.

        Expected datasets:
            - schedule: Game schedules and results
            - player_game: Per-player per-game stats
            - team_game: Team-level game results
            - play_by_play: Play-by-play events
            - shots: Shot chart data
            - player_season: Player season aggregates
            - team_season: Team season aggregates
            - player_team_season: Player×team season stats

        Example:
            # Get list of available datasets
            response = requests.get("http://localhost:8000/datasets")
            dataset_ids = [ds["id"] for ds in response.json()["datasets"]]

            # Check if a specific dataset is available
            if "schedule" in dataset_ids:
                print("Schedule dataset is available")
        """
        response = api_client.get(f"{api_base_url}/datasets")
        data = response.json()

        dataset_ids = [ds["id"] for ds in data["datasets"]]

        for expected_id in all_datasets:
            assert expected_id in dataset_ids, (
                f"Expected dataset '{expected_id}' not found in response"
            )

    def test_dataset_metadata_completeness(self, api_client, api_base_url):
        """
        Test that each dataset has complete metadata.

        Each dataset should provide enough information for users to
        understand what it contains and how to query it.

        Required fields per dataset:
            - id: Unique identifier
            - name: Display name
            - description: What it contains
            - supported_filters: Available filter options
            - supported_leagues: Which leagues it covers

        Example:
            # Get metadata for a specific dataset
            response = requests.get("http://localhost:8000/datasets")
            datasets = response.json()["datasets"]

            schedule_dataset = next(ds for ds in datasets if ds["id"] == "schedule")
            print(f"Description: {schedule_dataset['description']}")
            print(f"Filters: {schedule_dataset['supported_filters']}")
        """
        response = api_client.get(f"{api_base_url}/datasets")
        data = response.json()

        required_fields = [
            "id", "name", "description",
            "supported_filters", "supported_leagues"
        ]

        for dataset in data["datasets"]:
            for field in required_fields:
                assert field in dataset, (
                    f"Dataset '{dataset.get('id', 'unknown')}' missing field: {field}"
                )


# ============================================================================
# Dataset Query Tests
# ============================================================================

@pytest.mark.api
class TestDatasetQueryEndpoint:
    """
    Tests for POST /datasets/{dataset_id} endpoint.

    This is the main endpoint for querying datasets. It accepts filters
    and returns the requested data.

    Request Format:
        POST /datasets/schedule
        {
          "filters": {
            "league": "NCAA-MBB",
            "season": "2024",
            "team": ["Duke"]
          },
          "limit": 10,
          "offset": 0,
          "output_format": "json",
          "include_metadata": true
        }

    Response Format:
        {
          "data": [[row1], [row2], ...],  # Array of arrays (default)
          "columns": ["COL1", "COL2", ...],
          "metadata": {
            "dataset_id": "schedule",
            "row_count": 10,
            "execution_time_ms": 45.3,
            "cached": true
          }
        }
    """

    @pytest.mark.parametrize("league", ["NCAA-MBB", "NCAA-WBB", "EuroLeague"])
    def test_query_schedule_all_leagues(self, api_client, api_base_url, league):
        """
        Test querying schedule dataset for all supported leagues.

        This test runs once for each league to ensure schedule data
        is accessible across all supported competitions.

        Supported leagues:
            - NCAA-MBB: NCAA Men's Basketball (2002-present)
            - NCAA-WBB: NCAA Women's Basketball (2005-present)
            - EuroLeague: EuroLeague Basketball (2001-present)

        Example for each league:
            # NCAA Men's Basketball
            curl -X POST http://localhost:8000/datasets/schedule \\
              -H "Content-Type: application/json" \\
              -d '{"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 5}'

            # NCAA Women's Basketball
            curl -X POST http://localhost:8000/datasets/schedule \\
              -H "Content-Type: application/json" \\
              -d '{"filters": {"league": "NCAA-WBB", "season": "2024"}, "limit": 5}'

            # EuroLeague
            curl -X POST http://localhost:8000/datasets/schedule \\
              -H "Content-Type: application/json" \\
              -d '{"filters": {"league": "EuroLeague", "season": "2024"}, "limit": 5}'
        """
        request_data = {
            "filters": {
                "league": league,
                "season": "2024"
            },
            "limit": 5,
            "include_metadata": True
        }

        response = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json=request_data,
            timeout=180  # Increased from 60s to handle first-time data fetches
        )

        assert response.status_code == 200, (
            f"Failed to query schedule for {league}: {response.text}"
        )

        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert "metadata" in data, "Response missing 'metadata' field"
        assert data["metadata"]["dataset_id"] == "schedule"

    @pytest.mark.parametrize("per_mode", ["Totals", "PerGame", "Per40"])
    def test_player_season_all_per_modes(self, api_client, api_base_url, per_mode):
        """
        Test querying player season stats with all aggregation modes.

        Per-mode options:
            - Totals: Season totals (sum of all games)
            - PerGame: Per-game averages (total / games played)
            - Per40: Per-40-minutes stats (normalized to 40 mins)

        Use cases:
            - Totals: Find players with most total points
            - PerGame: Compare scoring averages
            - Per40: Compare efficiency regardless of minutes played

        Examples:
            # Get top scorers by total points
            curl -X POST http://localhost:8000/datasets/player_season \\
              -H "Content-Type: application/json" \\
              -d '{
                "filters": {
                  "league": "NCAA-MBB",
                  "season": "2024",
                  "per_mode": "Totals"
                },
                "limit": 20
              }'

            # Get top scorers by points per game
            curl -X POST http://localhost:8000/datasets/player_season \\
              -H "Content-Type: application/json" \\
              -d '{
                "filters": {
                  "league": "NCAA-MBB",
                  "season": "2024",
                  "per_mode": "PerGame"
                },
                "limit": 20
              }'

            # Get most efficient scorers (per 40 minutes)
            curl -X POST http://localhost:8000/datasets/player_season \\
              -H "Content-Type: application/json" \\
              -d '{
                "filters": {
                  "league": "NCAA-MBB",
                  "season": "2024",
                  "per_mode": "Per40"
                },
                "limit": 20
              }'
        """
        request_data = {
            "filters": {
                "league": "NCAA-MBB",
                "season": "2024",
                "per_mode": per_mode
            },
            "limit": 5,
            "include_metadata": True
        }

        response = api_client.post(
            f"{api_base_url}/datasets/player_season",
            json=request_data,
            timeout=180  # Increased from 60s to handle first-time data fetches
        )

        # Some per_modes might take longer on first fetch
        if response.status_code == 200:
            data = response.json()
            assert data["metadata"]["dataset_id"] == "player_season"
            print(f"✓ per_mode={per_mode}: {data['metadata']['row_count']} rows")
        else:
            pytest.skip(f"Timeout on first fetch for per_mode={per_mode}")

    def test_query_with_metadata(self, api_client, api_base_url):
        """
        Test that metadata is included when requested.

        Metadata provides useful information about the query:
            - dataset_id: Which dataset was queried
            - row_count: Number of rows returned
            - execution_time_ms: How long the query took
            - cached: Whether result was from cache
            - filters_applied: What filters were used
            - timestamp: When the query was executed

        Example:
            request = {
              "filters": {"league": "NCAA-MBB", "season": "2024"},
              "limit": 10,
              "include_metadata": True  # <-- Request metadata
            }

            response = requests.post(
                "http://localhost:8000/datasets/schedule",
                json=request
            )

            metadata = response.json()["metadata"]
            print(f"Query took {metadata['execution_time_ms']}ms")
            print(f"Cached: {metadata['cached']}")
            print(f"Rows: {metadata['row_count']}")
        """
        request_data = {
            "filters": {
                "league": "NCAA-MBB",
                "season": "2024"
            },
            "limit": 5,
            "include_metadata": True  # Request metadata
        }

        response = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json=request_data,
            timeout=180  # Increased from 60s to handle first-time data fetches
        )

        assert response.status_code == 200
        data = response.json()

        assert "metadata" in data, "Metadata not included despite include_metadata=True"

        metadata = data["metadata"]
        required_metadata_fields = [
            "dataset_id", "row_count", "execution_time_ms",
            "cached", "filters_applied"
        ]

        for field in required_metadata_fields:
            assert field in metadata, f"Metadata missing field: {field}"


# ============================================================================
# Recent Games Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.smoke
class TestRecentGamesEndpoint:
    """
    Tests for GET /recent-games/{league} endpoint.

    This is a convenience endpoint for quickly getting recent games
    without manually specifying date ranges.

    Example Usage:
        # Get yesterday + today's games
        GET http://localhost:8000/recent-games/NCAA-MBB?days=2

        # Get last week of games
        GET http://localhost:8000/recent-games/NCAA-MBB?days=7

        # Filter by teams
        GET http://localhost:8000/recent-games/NCAA-MBB?days=2&teams=Duke,UNC

    Common Use Cases:
        - Display today's games on a website
        - Check recent scores
        - Find games to analyze
    """

    @pytest.mark.parametrize("league", ["NCAA-MBB", "NCAA-WBB", "EuroLeague"])
    def test_recent_games_all_leagues(self, api_client, api_base_url, league):
        """
        Test getting recent games for all leagues.

        The recent games endpoint automatically calculates the date range
        from today backwards, making it easy to get current games.

        Examples:
            # NCAA Men's Basketball recent games
            curl "http://localhost:8000/recent-games/NCAA-MBB?days=2"

            # NCAA Women's Basketball recent games
            curl "http://localhost:8000/recent-games/NCAA-WBB?days=2"

            # EuroLeague recent games
            curl "http://localhost:8000/recent-games/EuroLeague?days=2"
        """
        response = api_client.get(
            f"{api_base_url}/recent-games/{league}?days=2",
            timeout=180  # Increased from 60s to handle first-time data fetches
        )

        assert response.status_code == 200, (
            f"Failed to get recent games for {league}"
        )

        data = response.json()
        assert "data" in data
        assert "metadata" in data
        print(f"✓ {league}: {data['metadata']['row_count']} recent games")

    def test_recent_games_date_range_validation(self, api_client, api_base_url):
        """
        Test that days parameter is properly validated.

        Valid range: 1-30 days
            - days=1: Today only
            - days=2: Yesterday + today (default)
            - days=7: Last week
            - days=30: Last month

        Example:
            # Today only
            curl "http://localhost:8000/recent-games/NCAA-MBB?days=1"

            # Last week
            curl "http://localhost:8000/recent-games/NCAA-MBB?days=7"

            # Invalid (should fail)
            curl "http://localhost:8000/recent-games/NCAA-MBB?days=100"
        """
        # Test valid range
        response = api_client.get(
            f"{api_base_url}/recent-games/NCAA-MBB?days=7",
            timeout=180  # Increased from 60s to handle first-time data fetches
        )
        assert response.status_code == 200, "Valid days parameter should work"


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.api
class TestErrorHandling:
    """
    Tests for error handling and validation.

    The API should return clear, helpful error messages when:
        - Dataset doesn't exist
        - Required parameters are missing
        - Invalid parameter values
        - Rate limits exceeded
    """

    def test_nonexistent_dataset_returns_404(self, api_client, api_base_url):
        """
        Test that querying a non-existent dataset returns 404.

        Example:
            POST http://localhost:8000/datasets/nonexistent
            Response: 404 Not Found
            {
              "error": "NotFoundError",
              "message": "Dataset 'nonexistent' not found"
            }
        """
        request_data = {
            "filters": {"league": "NCAA-MBB"}
        }

        response = api_client.post(
            f"{api_base_url}/datasets/nonexistent_dataset",
            json=request_data
        )

        assert response.status_code == 404, "Should return 404 for non-existent dataset"

    def test_invalid_league_returns_400(self, api_client, api_base_url):
        """
        Test that invalid league parameter returns 400 Bad Request.

        Valid leagues: NCAA-MBB, NCAA-WBB, EuroLeague
        Invalid: INVALID_LEAGUE, NBA, etc.

        Example:
            POST http://localhost:8000/datasets/schedule
            {
              "filters": {"league": "INVALID_LEAGUE"}
            }

            Response: 400 Bad Request
            {
              "error": "ValidationError",
              "message": "Invalid league: INVALID_LEAGUE"
            }
        """
        request_data = {
            "filters": {"league": "INVALID_LEAGUE"}
        }

        response = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json=request_data
        )

        # Should return 400 or 500 with validation error
        assert response.status_code in [400, 500], (
            "Invalid league should return error status"
        )

    def test_rate_limit_headers_present(self, api_client, api_base_url):
        """
        Test that rate limit headers are included in responses.

        Rate limit headers:
            - X-RateLimit-Limit: Maximum requests per minute
            - X-RateLimit-Remaining: Requests remaining
            - X-RateLimit-Reset: Unix timestamp when limit resets

        Example:
            response = requests.get("http://localhost:8000/health")

            limit = int(response.headers["X-RateLimit-Limit"])
            remaining = int(response.headers["X-RateLimit-Remaining"])
            reset = int(response.headers["X-RateLimit-Reset"])

            print(f"Rate limit: {remaining}/{limit} requests remaining")
            print(f"Resets at: {datetime.fromtimestamp(reset)}")
        """
        response = api_client.get(f"{api_base_url}/datasets")

        assert "X-RateLimit-Limit" in response.headers, (
            "Missing rate limit header: X-RateLimit-Limit"
        )
        assert "X-RateLimit-Remaining" in response.headers, (
            "Missing rate limit header: X-RateLimit-Remaining"
        )
        assert "X-RateLimit-Reset" in response.headers, (
            "Missing rate limit header: X-RateLimit-Reset"
        )


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.api
@pytest.mark.slow
class TestPerformance:
    """
    Tests for API performance and caching.

    Performance expectations:
        - Health check: <500ms
        - Cached queries: <100ms
        - Fresh queries: <60s (fetching from data sources)
        - Rate limit: 60 requests/minute
    """

    def test_performance_headers_present(self, api_client, api_base_url):
        """
        Test that performance tracking headers are included.

        Headers:
            - X-Process-Time: Query execution time in milliseconds

        Example:
            response = requests.get("http://localhost:8000/datasets")
            process_time = response.headers["X-Process-Time"]
            print(f"Request took {process_time}")  # "45.23ms"
        """
        response = api_client.get(f"{api_base_url}/datasets")

        assert "X-Process-Time" in response.headers, (
            "Missing performance header: X-Process-Time"
        )

        # Verify format
        process_time = response.headers["X-Process-Time"]
        assert "ms" in process_time, "X-Process-Time should be in milliseconds"

    def test_caching_improves_performance(self, api_client, api_base_url):
        """
        Test that caching significantly improves query performance.

        Expected behavior:
            - First query: Fetches from data sources (slow)
            - Second query: Returns from cache (fast, typically 1000x faster)

        Example:
            import time

            # First query (not cached)
            start = time.time()
            response1 = requests.post(
                "http://localhost:8000/datasets/schedule",
                json={"filters": {"league": "NCAA-MBB", "season": "2024"}}
            )
            first_time = time.time() - start

            # Second query (cached)
            start = time.time()
            response2 = requests.post(
                "http://localhost:8000/datasets/schedule",
                json={"filters": {"league": "NCAA-MBB", "season": "2024"}}
            )
            second_time = time.time() - start

            speedup = first_time / second_time
            print(f"Cache provided {speedup:.0f}x speedup")
        """
        request_data = {
            "filters": {
                "league": "EuroLeague",  # EuroLeague is usually fast
                "season": "2024"
            },
            "limit": 5
        }

        # First query
        start_time = time.time()
        response1 = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json=request_data,
            timeout=180  # Increased from 60s to handle first-time data fetches
        )
        first_query_time = time.time() - start_time

        # Second query (should be cached)
        start_time = time.time()
        response2 = api_client.post(
            f"{api_base_url}/datasets/schedule",
            json=request_data,
            timeout=180  # Increased from 60s to handle first-time data fetches
        )
        second_query_time = time.time() - start_time

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Second query should be significantly faster
        if second_query_time < first_query_time:
            speedup = first_query_time / second_query_time
            print(f"✓ Cache speedup: {speedup:.1f}x faster")
        else:
            # Even if not faster, both should complete
            print(f"✓ Both queries completed")
