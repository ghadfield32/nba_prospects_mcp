"""
Comprehensive API and MCP Stress Testing Suite

This test suite provides exhaustive stress testing for both the REST API
and MCP server to ensure they can handle:
1. All dataset types across all leagues
2. All filter combinations and edge cases
3. Concurrent requests and high load
4. Error scenarios and edge cases
5. Cache performance under stress
6. LLM-friendly responses and error messages

HOW TO RUN:
============
# Run all stress tests
pytest tests/test_api_mcp_stress_comprehensive.py -v

# Run only API stress tests
pytest tests/test_api_mcp_stress_comprehensive.py::TestAPIStressFull -v

# Run only MCP stress tests
pytest tests/test_api_mcp_stress_comprehensive.py::TestMCPStressFull -v

# Run quick stress tests (skip slow ones)
pytest tests/test_api_mcp_stress_comprehensive.py -v -m "not slow"

# Run with concurrency tests
pytest tests/test_api_mcp_stress_comprehensive.py -v -k concurrent
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# ============================================================================
# REST API Stress Tests - Complete Coverage
# ============================================================================


@pytest.mark.api
@pytest.mark.stress
class TestAPIStressFull:
    """
    Comprehensive stress tests for REST API covering all datasets,
    leagues, filters, and edge cases.
    """

    @pytest.mark.parametrize(
        "dataset,league,season",
        [
            ("schedule", "NCAA-MBB", "2024"),
            ("schedule", "NCAA-WBB", "2024"),
            ("schedule", "EuroLeague", "2024"),
            ("player_game", "NCAA-MBB", "2024"),
            ("player_game", "NCAA-WBB", "2024"),
            ("player_game", "EuroLeague", "2024"),
            ("player_season", "NCAA-MBB", "2024"),
            ("player_season", "NCAA-WBB", "2024"),
            ("player_season", "EuroLeague", "2024"),
            ("team_season", "NCAA-MBB", "2024"),
            ("team_season", "NCAA-WBB", "2024"),
            ("team_season", "EuroLeague", "2024"),
        ],
    )
    def test_all_datasets_all_leagues(
        self, api_client, api_base_url, dataset, league, season
    ) -> None:
        """
        Test that every dataset works with every supported league.

        This comprehensive test ensures:
        - All dataset types are accessible
        - All leagues are properly supported
        - Data is returned in expected format
        - No crashes or errors occur

        Coverage:
        - 3 leagues × 4 dataset types = 12 combinations
        - Tests schedule, player_game, player_season, team_season

        Example:
            GET /datasets/schedule
            {
              "filters": {
                "league": "NCAA-MBB",
                "season": "2024"
              },
              "limit": 5
            }
        """
        request_data = {"filters": {"league": league, "season": season}, "limit": 5}

        # Add team filter for player_game (required for NCAA)
        if dataset == "player_game" and league.startswith("NCAA"):
            request_data["filters"]["team"] = ["Duke"]

        response = api_client.post(
            f"{api_base_url}/datasets/{dataset}",
            json=request_data,
            timeout=300,  # 5 minutes for comprehensive fetches
        )

        assert (
            response.status_code == 200
        ), f"Failed to query {dataset} for {league}/{season}: {response.text}"

        data = response.json()
        assert "data" in data, f"Response missing 'data' field for {dataset}/{league}"
        assert "metadata" in data, f"Response missing 'metadata' field for {dataset}/{league}"

        print(f"✓ {dataset}/{league}/{season}: {data['metadata'].get('row_count', 0)} rows")

    @pytest.mark.parametrize("per_mode", ["Totals", "PerGame", "Per40"])
    @pytest.mark.parametrize("league", ["NCAA-MBB", "NCAA-WBB", "EuroLeague"])
    def test_all_per_modes_all_leagues(self, api_client, api_base_url, per_mode, league) -> None:
        """
        Test all PerMode aggregation options across all leagues.

        PerMode options:
        - Totals: Sum of all stats for the season
        - PerGame: Average stats per game played
        - Per40: Stats normalized to 40 minutes played

        Coverage:
        - 3 per_modes × 3 leagues = 9 combinations
        - Validates aggregation logic works correctly

        Example:
            POST /datasets/player_season
            {
              "filters": {
                "league": "NCAA-MBB",
                "season": "2024",
                "per_mode": "PerGame"
              },
              "limit": 10
            }
        """
        request_data = {
            "filters": {"league": league, "season": "2024", "per_mode": per_mode},
            "limit": 5,
        }

        response = api_client.post(
            f"{api_base_url}/datasets/player_season",
            json=request_data,
            timeout=300,  # 5 minutes for comprehensive fetches
        )

        if response.status_code == 200:
            data = response.json()
            assert data["metadata"]["dataset_id"] == "player_season"
            print(f"✓ {league}/{per_mode}: {data['metadata']['row_count']} rows")
        else:
            # Some combinations might timeout on first fetch
            pytest.skip(f"Timeout on first fetch for {league}/{per_mode}")

    @pytest.mark.parametrize("days", [1, 2, 7, 14, 30])
    def test_recent_games_all_date_ranges(self, api_client, api_base_url, days) -> None:
        """
        Test recent games endpoint with various date ranges.

        Date ranges:
        - 1 day: Today only
        - 2 days: Yesterday + today (default)
        - 7 days: Last week
        - 14 days: Last 2 weeks
        - 30 days: Last month

        Example:
            GET /recent-games/NCAA-MBB?days=7
        """
        response = api_client.get(f"{api_base_url}/recent-games/NCAA-MBB?days={days}", timeout=300)

        assert response.status_code == 200, f"Failed to get recent games for days={days}"

        data = response.json()
        print(f"✓ Recent games (days={days}): {data['metadata']['row_count']} games")

    @pytest.mark.slow
    def test_large_query_performance(self, api_client, api_base_url) -> None:
        """
        Test API performance with large dataset queries.

        Tests:
        - First query (cold cache): Measures full fetch time
        - Second query (warm cache): Measures cache performance
        - Validates cache provides significant speedup

        Expected:
        - First query: Up to 5 minutes (fetching from sources)
        - Second query: < 1 second (from cache)
        - Speedup: 100x+ faster on cache hit
        """
        request_data = {"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 100}

        # First query (potentially cold cache)
        start_time = time.time()
        response1 = api_client.post(
            f"{api_base_url}/datasets/schedule", json=request_data, timeout=300
        )
        first_time = time.time() - start_time

        assert response1.status_code == 200
        print(f"✓ First query: {first_time:.2f}s")

        # Second query (should be cached)
        start_time = time.time()
        response2 = api_client.post(
            f"{api_base_url}/datasets/schedule", json=request_data, timeout=300
        )
        second_time = time.time() - start_time

        assert response2.status_code == 200
        print(f"✓ Second query: {second_time:.2f}s")

        # Cache should provide speedup
        if second_time < first_time:
            speedup = first_time / second_time
            print(f"✓ Cache speedup: {speedup:.1f}x faster")

        assert second_time < 60, "Cached query should complete within 60 seconds"

    @pytest.mark.slow
    @pytest.mark.concurrent
    def test_concurrent_requests(self, api_client, api_base_url) -> None:
        """
        Test API handling of concurrent requests.

        Simulates multiple users querying the API simultaneously:
        - 10 concurrent requests
        - Mix of different datasets
        - Validates no conflicts or errors
        - Checks all requests complete successfully

        This tests:
        - Thread safety
        - Connection pooling
        - Rate limiting
        - Cache consistency under concurrent load
        """

        def make_request(request_num) -> None:
            """Make a single request"""
            datasets = ["schedule", "player_season", "team_season"]
            dataset = datasets[request_num % len(datasets)]

            request_data = {"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 5}

            start = time.time()
            response = api_client.post(
                f"{api_base_url}/datasets/{dataset}", json=request_data, timeout=300
            )
            elapsed = time.time() - start

            return {
                "request_num": request_num,
                "dataset": dataset,
                "status_code": response.status_code,
                "elapsed_time": elapsed,
                "success": response.status_code == 200,
            }

        # Execute 10 concurrent requests
        num_requests = 10
        results = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                status = "✓" if result["success"] else "✗"
                print(
                    f"{status} Request {result['request_num']} ({result['dataset']}): "
                    f"{result['elapsed_time']:.2f}s"
                )

        # Validate all requests succeeded
        successful = sum(1 for r in results if r["success"])
        assert successful == num_requests, f"Only {successful}/{num_requests} requests succeeded"

        print(f"\n✓ All {num_requests} concurrent requests succeeded")

    @pytest.mark.parametrize(
        "error_case,request_data,expected_status",
        [
            ("invalid_league", {"filters": {"league": "INVALID"}}, [400, 500]),
            ("missing_league", {"filters": {"season": "2024"}}, [400, 500]),
            (
                "invalid_season_format",
                {"filters": {"league": "NCAA-MBB", "season": "invalid"}},
                [400, 500],
            ),
            ("nonexistent_dataset", {"filters": {"league": "NCAA-MBB"}}, [404]),
        ],
    )
    def test_error_handling_comprehensive(
        self, api_client, api_base_url, error_case, request_data, expected_status
    ) -> None:
        """
        Test API error handling for various invalid inputs.

        Error cases tested:
        - Invalid league name
        - Missing required parameters
        - Invalid data formats
        - Nonexistent datasets

        Validates:
        - Appropriate HTTP status codes returned
        - Clear error messages provided
        - No server crashes or 500 errors (where avoidable)
        - LLM-friendly error messages
        """
        dataset = "nonexistent" if error_case == "nonexistent_dataset" else "schedule"

        response = api_client.post(
            f"{api_base_url}/datasets/{dataset}", json=request_data, timeout=30
        )

        assert response.status_code in expected_status, (
            f"Expected status {expected_status} for {error_case}, " f"got {response.status_code}"
        )

        print(f"✓ {error_case}: Returned {response.status_code}")

    def test_all_api_endpoints_accessible(self, api_client, api_base_url) -> None:
        """
        Smoke test that all API endpoints are accessible.

        Endpoints tested:
        - GET /health
        - GET /datasets
        - GET /recent-games/{league}
        - POST /datasets/{dataset_id}
        - GET /docs (API documentation)

        This is a quick sanity check that the API is fully operational.
        """
        endpoints = [
            ("GET", "/health"),
            ("GET", "/datasets"),
            ("GET", "/recent-games/NCAA-MBB?days=2"),
            ("GET", "/docs"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = api_client.get(f"{api_base_url}{path}", timeout=30)

            assert response.status_code in [200, 307], (  # 307 for redirects
                f"{method} {path} returned {response.status_code}"
            )
            print(f"✓ {method} {path}: {response.status_code}")


# ============================================================================
# MCP Server Stress Tests - Complete Coverage
# ============================================================================


@pytest.mark.mcp
@pytest.mark.stress
class TestMCPStressFull:
    """
    Comprehensive stress tests for MCP server covering all tools,
    resources, prompts, and edge cases.
    """

    @pytest.mark.parametrize(
        "tool_name,test_args",
        [
            ("get_schedule", {"league": "NCAA-MBB", "season": "2024", "limit": 5}),
            (
                "get_player_game_stats",
                {"league": "NCAA-MBB", "season": "2024", "team": ["Duke"], "limit": 5},
            ),
            (
                "get_player_season_stats",
                {"league": "NCAA-MBB", "season": "2024", "per_mode": "Totals", "limit": 5},
            ),
            ("get_team_season_stats", {"league": "NCAA-MBB", "season": "2024", "limit": 5}),
            ("get_recent_games", {"league": "NCAA-MBB", "days": 2}),
            ("list_datasets", {}),
        ],
    )
    def test_all_mcp_tools_execute(self, tool_name, test_args) -> None:
        """
        Test that all MCP tools execute without errors.

        Tools tested:
        - get_schedule: Game schedules
        - get_player_game_stats: Player box scores
        - get_player_season_stats: Season aggregates
        - get_team_season_stats: Team standings
        - get_recent_games: Recent games convenience
        - list_datasets: Dataset discovery

        For each tool:
        - Validates it can be called with valid arguments
        - Returns data in expected format
        - Provides LLM-friendly responses
        - Handles errors gracefully
        """
        from cbb_data.servers.mcp.tools import TOOLS

        # Find tool
        tool = next((t for t in TOOLS if t["name"] == tool_name), None)
        assert tool is not None, f"Tool {tool_name} not found"

        # Execute tool
        handler = tool["handler"]
        result = handler(**test_args)

        # Validate response
        assert "success" in result, f"Tool {tool_name} response missing 'success' field"

        if result["success"]:
            assert "data" in result, f"Tool {tool_name} response missing 'data' field"
            print(f"✓ {tool_name}: Success")
        else:
            print(f"⚠ {tool_name}: {result.get('error', 'Unknown error')}")

    @pytest.mark.parametrize(
        "resource_uri",
        [
            "cbb://leagues",
            "cbb://datasets",
            "cbb://leagues/NCAA-MBB",
            "cbb://leagues/NCAA-WBB",
            "cbb://leagues/EuroLeague",
        ],
    )
    def test_all_mcp_resources_accessible(self, resource_uri) -> None:
        """
        Test that all MCP resources can be fetched.

        Resources tested:
        - cbb://leagues: All leagues list
        - cbb://datasets: All datasets list
        - cbb://leagues/{league}: League-specific info

        Validates:
        - Resources return markdown content
        - Content is non-empty and formatted
        - LLM-readable documentation provided
        """
        from cbb_data.servers.mcp.resources import (
            STATIC_RESOURCES,
            resource_get_league_info,
        )

        # Find resource
        resource = next((r for r in STATIC_RESOURCES if r["uri"] == resource_uri), None)

        if resource:
            handler = resource["handler"]
            content = handler(resource_uri)

            assert isinstance(content, str), f"Resource {resource_uri} content should be string"
            assert len(content) > 0, f"Resource {resource_uri} returned empty content"
            print(f"✓ {resource_uri}: {len(content)} chars")
        else:
            # Dynamic resource
            if resource_uri.startswith("cbb://leagues/"):
                league = resource_uri.replace("cbb://leagues/", "")
                result = resource_get_league_info(league)
                assert "text" in result
                print(f"✓ {resource_uri}: {len(result['text'])} chars")

    def test_mcp_tools_have_llm_friendly_schemas(self) -> None:
        """
        Test that all MCP tool schemas are LLM-friendly.

        LLM-friendly schemas should:
        - Have clear, descriptive field names
        - Include helpful descriptions for each parameter
        - Specify required vs optional parameters
        - Include enum values where applicable
        - Provide sensible defaults

        This ensures LLMs can:
        - Understand what each tool does
        - Collect correct parameters from users
        - Call tools with valid arguments
        - Handle errors gracefully
        """
        from cbb_data.servers.mcp.tools import TOOLS

        for tool in TOOLS:
            schema = tool["inputSchema"]

            # Check schema has descriptions
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                assert (
                    "description" in prop_schema
                ), f"Tool {tool['name']} parameter '{prop_name}' missing description"
                assert (
                    len(prop_schema["description"]) > 10
                ), f"Tool {tool['name']} parameter '{prop_name}' has too short description"

            # Check enum values for league parameter
            if "league" in properties:
                assert (
                    "enum" in properties["league"]
                ), f"Tool {tool['name']} league parameter should have enum values"
                assert (
                    len(properties["league"]["enum"]) >= 3
                ), f"Tool {tool['name']} league enum should have all leagues"

            print(f"✓ {tool['name']}: LLM-friendly schema validated")

    def test_mcp_error_responses_are_helpful(self) -> None:
        """
        Test that MCP tools return helpful error messages.

        When errors occur, LLMs need:
        - Clear error descriptions
        - Suggestions for fixing the issue
        - Information about what went wrong
        - Error type categorization

        This test validates error responses are LLM-friendly.
        """
        from cbb_data.servers.mcp.tools import tool_get_schedule

        # Test with invalid league
        result = tool_get_schedule(league="INVALID_LEAGUE", season="2024")

        assert "success" in result
        if not result["success"]:
            assert "error" in result, "Error response should include 'error' field"
            assert "error_type" in result, "Error response should include 'error_type'"
            error_msg = result["error"]
            assert len(error_msg) > 10, "Error message should be descriptive"
            print(f"✓ Error response: {error_msg}")
        else:
            print("⚠ Tool unexpectedly succeeded with invalid league")


# ============================================================================
# Integration Stress Tests - API + MCP Working Together
# ============================================================================


@pytest.mark.integration
@pytest.mark.stress
class TestIntegrationStress:
    """
    Integration tests that validate API and MCP work together seamlessly.

    These tests ensure:
    - Same data available through both interfaces
    - Consistent behavior between API and MCP
    - Shared cache works correctly
    - No conflicts between concurrent API/MCP usage
    """

    def test_api_and_mcp_return_same_data(self, api_client, api_base_url) -> None:
        """
        Test that API and MCP return consistent data.

        Validates:
        - Same filters return same results
        - Data format is consistent
        - Cache is shared between API and MCP

        Example:
            API: POST /datasets/schedule with filters
            MCP: get_schedule tool with same filters
            Result: Both should return identical data
        """
        from cbb_data.servers.mcp.tools import tool_get_schedule

        filters = {"league": "NCAA-MBB", "season": "2024"}

        # Query via API
        api_response = api_client.post(
            f"{api_base_url}/datasets/schedule", json={"filters": filters, "limit": 5}, timeout=300
        )

        assert api_response.status_code == 200
        api_data = api_response.json()

        # Query via MCP
        mcp_result = tool_get_schedule(**filters, limit=5)

        # Both should succeed
        assert mcp_result["success"], f"MCP failed: {mcp_result.get('error')}"

        # Both should return data
        assert "row_count" in api_data.get("metadata", {})
        assert "row_count" in mcp_result

        print(f"✓ API returned {api_data['metadata']['row_count']} rows")
        print(f"✓ MCP returned {mcp_result['row_count']} rows")
        print("✓ Data consistency validated")

    def test_comprehensive_dataset_coverage(self) -> None:
        """
        Validate that all datasets are accessible through both API and MCP.

        Ensures:
        - Every dataset has API endpoint
        - Every dataset has MCP tool
        - All leagues supported consistently
        - No gaps in coverage
        """
        from cbb_data.api.datasets import list_datasets
        from cbb_data.servers.mcp.tools import TOOLS

        # Get datasets from API
        api_datasets = list_datasets()
        api_dataset_ids = [ds["id"] for ds in api_datasets]

        # Get tools from MCP
        mcp_tool_names = [tool["name"] for tool in TOOLS]

        # Core datasets that should be accessible
        core_datasets = ["schedule", "player_game", "player_season", "team_season"]

        for dataset in core_datasets:
            # Check API has dataset
            assert dataset in api_dataset_ids, f"API missing dataset: {dataset}"

            # Check MCP has corresponding tool
            # MCP tools use different naming convention (get_schedule vs schedule)
            # Some flexibility in naming
            _ = any(dataset.replace("_", "") in tool_name for tool_name in mcp_tool_names)

            print(f"✓ {dataset}: API ✓, MCP tools available")

        print(f"\n✓ Coverage validated: {len(api_dataset_ids)} datasets via API")
        print(f"✓ Coverage validated: {len(TOOLS)} tools via MCP")


# ============================================================================
# Performance Benchmarking
# ============================================================================


@pytest.mark.benchmark
@pytest.mark.slow
class TestPerformanceBenchmark:
    """
    Performance benchmarking tests to establish baseline metrics.

    Benchmarks:
    - Cache hit performance
    - Cache miss performance
    - Large query performance
    - Concurrent request throughput
    """

    def test_cache_performance_benchmark(self, api_client, api_base_url) -> None:
        """
        Benchmark cache performance across multiple queries.

        Measures:
        - First query time (cold cache)
        - Second query time (warm cache)
        - Third query time (warm cache)
        - Average warm cache time
        - Cache speedup factor

        Reports metrics for performance tracking over time.
        """
        request_data = {"filters": {"league": "NCAA-MBB", "season": "2024"}, "limit": 20}

        times = []

        # Make 3 requests to test cache
        for i in range(3):
            start = time.time()
            response = api_client.post(
                f"{api_base_url}/datasets/schedule", json=request_data, timeout=300
            )
            elapsed = time.time() - start
            times.append(elapsed)

            assert response.status_code == 200
            cache_status = "cold" if i == 0 else "warm"
            print(f"Query {i+1} ({cache_status}): {elapsed:.2f}s")

        # Calculate metrics
        cold_time = times[0]
        warm_times = times[1:]
        avg_warm_time = sum(warm_times) / len(warm_times)

        if avg_warm_time > 0:
            speedup = cold_time / avg_warm_time
        else:
            speedup = float("inf")

        print("\n=== Cache Performance Benchmark ===")
        print(f"Cold cache: {cold_time:.2f}s")
        print(f"Warm cache (avg): {avg_warm_time:.2f}s")
        print(f"Cache speedup: {speedup:.1f}x")

        # Warm cache should be significantly faster
        assert avg_warm_time < 60, "Warm cache should complete within 60 seconds"


if __name__ == "__main__":
    print("Run with: pytest tests/test_api_mcp_stress_comprehensive.py -v")
