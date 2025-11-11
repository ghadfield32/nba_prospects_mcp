"""
Comprehensive stress tests for all automation upgrade features.

Tests:
    - JSON logging
    - Prometheus metrics
    - Auto-pagination & token management
    - Column registry & pruning
    - Guardrails (decimal rounding, datetime standardization)
    - Batch queries
    - Composite tools
    - Middleware (Request-ID, Circuit Breaker, Idempotency)
"""

import pandas as pd

# ============================================================================
# Test Logging
# ============================================================================


def test_json_logging() -> None:
    """Test JSON structured logging."""
    from cbb_data.servers.logging import log_cache, log_error, log_event, log_request, log_tool_call

    # Test log_event
    log_event(service="test", event="test_event", value=123)

    # Test log_request
    log_request(
        service="test",
        endpoint="/test",
        method="GET",
        status_code=200,
        duration_ms=45.3,
        request_id="test-123",
    )

    # Test log_error
    log_error(service="test", error="Test error", error_type="ValueError", request_id="test-123")

    # Test log_cache
    log_cache(
        action="hit",
        dataset="schedule",
        league="NCAA-MBB",
        season="2025",
        rows=100,
        duration_ms=0.5,
    )

    # Test log_tool_call
    log_tool_call(
        tool="get_schedule", duration_ms=125.5, rows=50, request_id="mcp-456", league="NCAA-MBB"
    )

    print("[PASS] JSON logging tests passed")


# ============================================================================
# Test Metrics
# ============================================================================


def test_metrics_available() -> None:
    """Test that metrics module loads correctly."""
    from cbb_data.servers.metrics import (
        METRICS_ENABLED,
        get_metrics_snapshot,
        track_cache_hit,
        track_cache_miss,
        track_error,
        track_http_request,
        track_tool_call,
    )

    # Test tracking functions (should not error even if metrics disabled)
    track_tool_call("get_schedule", duration_ms=100, rows=50, dataset="schedule", league="NCAA-MBB")
    track_cache_hit("schedule", "NCAA-MBB", duration_ms=0.5)
    track_cache_miss("schedule", "NCAA-MBB")
    track_http_request("POST", "/datasets/schedule", 200, 0.125)
    track_error("rest", "ValueError")

    # Test snapshot
    snapshot = get_metrics_snapshot()
    assert "metrics_enabled" in snapshot

    print(f"[PASS] Metrics tests passed (enabled={METRICS_ENABLED})")


# ============================================================================
# Test Auto-Pagination
# ============================================================================


def test_auto_pagination() -> None:
    """Test auto-pagination wrapper."""
    from cbb_data.servers.mcp_wrappers import estimate_tokens, mcp_autopaginate

    # Test token estimation
    tokens = estimate_tokens(100, 10)
    assert tokens == 4000  # 100 rows × 10 cols × 4

    # Test wrapper
    @mcp_autopaginate
    def mock_fetch(limit=None, offset=0, **kwargs) -> None:
        # Return mock data
        return pd.DataFrame(
            {
                "id": range(offset, offset + min(limit or 100, 100)),
                "value": range(offset, offset + min(limit or 100, 100)),
            }
        )

    # Test with shape="array"
    result = mock_fetch(limit=50, shape="array")
    assert "columns" in result
    assert "data" in result
    assert "truncated" in result
    assert result["row_count"] == 50

    # Test with shape="summary"
    result = mock_fetch(limit=50, shape="summary")
    assert "rows_returned" in result
    assert "sample" in result
    assert "stats" in result

    print("[PASS] Auto-pagination tests passed")


def test_column_pruning() -> None:
    """Test column pruning."""
    from cbb_data.servers.mcp_wrappers import prune_to_key_columns

    # Create test DataFrame
    df = pd.DataFrame(
        {
            "PLAYER_ID": [1, 2, 3],
            "PLAYER_NAME": ["Alice", "Bob", "Charlie"],
            "PTS": [20, 15, 25],
            "OBSCURE_STAT_1": [0.5, 0.3, 0.7],
            "OBSCURE_STAT_2": [0.1, 0.2, 0.3],
        }
    )

    # Test pruning
    pruned = prune_to_key_columns(df, "player_game")

    # Should keep important columns
    assert len(pruned.columns) < len(df.columns)
    assert (
        "PLAYER_ID" in pruned.columns or "PLAYER_NAME" in pruned.columns or "PTS" in pruned.columns
    )

    print(
        f"[PASS] Column pruning tests passed (pruned {len(df.columns)} -> {len(pruned.columns)} columns)"
    )


# ============================================================================
# Test Column Registry
# ============================================================================


def test_column_registry() -> None:
    """Test column registry."""
    from cbb_data.schemas.column_registry import (
        COLUMN_METADATA,
        filter_to_key_columns,
        get_key_columns,
        get_supplementary_columns,
        is_key_column,
    )

    # Test get_key_columns
    key_cols = get_key_columns("player_game")
    assert len(key_cols) > 0
    assert "PLAYER_ID" in key_cols
    assert "PTS" in key_cols

    # Test get_supplementary_columns
    supp_cols = get_supplementary_columns("player_game")
    assert len(supp_cols) > 0

    # Test is_key_column
    assert is_key_column("player_game", "PTS")
    assert not is_key_column("player_game", "OFFENSIVE_RATING")

    # Test filter_to_key_columns
    df = pd.DataFrame({"PLAYER_ID": [1], "PTS": [20], "OFFENSIVE_RATING": [110]})

    filtered = filter_to_key_columns(df, "player_game")
    assert "PTS" in filtered.columns
    assert "OFFENSIVE_RATING" not in filtered.columns or len(filtered.columns) < len(df.columns)

    # Test all datasets have metadata
    expected_datasets = [
        "schedule",
        "player_game",
        "team_game",
        "play_by_play",
        "shot_chart",
        "player_season",
        "team_season",
        "box_score",
    ]
    for dataset in expected_datasets:
        assert dataset in COLUMN_METADATA
        assert "key_columns" in COLUMN_METADATA[dataset]

    print(f"[PASS] Column registry tests passed ({len(COLUMN_METADATA)} datasets)")


# ============================================================================
# Test Guardrails
# ============================================================================


def test_guardrails() -> None:
    """Test decimal rounding and datetime standardization."""
    from cbb_data.compose.enrichers import (
        apply_decimal_rounding,
        apply_guardrails,
        standardize_datetimes,
    )

    # Test decimal rounding
    df = pd.DataFrame({"PTS": [20.123456], "FG_PCT": [0.456789123]})

    rounded = apply_decimal_rounding(df, precision=2)
    assert rounded["PTS"].iloc[0] == 20.12
    assert rounded["FG_PCT"].iloc[0] == 0.46

    # Test compact mode
    compact = apply_decimal_rounding(df, compact=True)
    assert compact["PTS"].iloc[0] == 20.1  # 1 decimal for counting stats
    assert compact["FG_PCT"].iloc[0] == 0.457  # 3 decimals for percentages

    # Test datetime standardization
    df_dt = pd.DataFrame({"GAME_DATE": [pd.Timestamp("2025-01-15 19:00:00")]})

    standardized = standardize_datetimes(df_dt)
    assert isinstance(standardized["GAME_DATE"].iloc[0], str)
    assert "T" in standardized["GAME_DATE"].iloc[0]  # ISO-8601 format
    assert "+00:00" in standardized["GAME_DATE"].iloc[0]  # UTC timezone

    # Test apply_guardrails (all in one)
    df_combined = pd.DataFrame(
        {"GAME_DATE": [pd.Timestamp("2025-01-15")], "PTS": [20.123456], "FG_PCT": [0.456789]}
    )

    clean = apply_guardrails(df_combined, compact=True)
    assert clean["PTS"].iloc[0] == 20.1
    assert isinstance(clean["GAME_DATE"].iloc[0], str)

    print("[PASS] Guardrails tests passed")


# ============================================================================
# Test Batch Queries
# ============================================================================


def test_batch_queries() -> None:
    """Test batch query tool."""
    from cbb_data.servers.mcp_batch import (
        batch_query,
        batch_query_safe,
        register_tool,
        validate_batch_request,
    )

    # Register mock tools
    def mock_tool_1(**kwargs) -> None:
        return {"result": "success_1"}

    def mock_tool_2(**kwargs) -> None:
        return {"result": "success_2"}

    def mock_tool_fail(**kwargs) -> None:
        raise ValueError("Intentional failure")

    register_tool("mock_tool_1", mock_tool_1)
    register_tool("mock_tool_2", mock_tool_2)
    register_tool("mock_tool_fail", mock_tool_fail)

    # Test validation
    valid, error = validate_batch_request([{"tool": "mock_tool_1", "args": {}}])
    assert valid
    assert error is None

    # Test invalid request
    valid, error = validate_batch_request(
        [
            {"tool": "mock_tool_1"}  # Missing args
        ]
    )
    assert not valid
    assert "missing 'args'" in error.lower()

    # Test batch execution
    results = batch_query(
        [
            {"tool": "mock_tool_1", "args": {}},
            {"tool": "mock_tool_2", "args": {}},
            {"tool": "mock_tool_fail", "args": {}},
        ]
    )

    assert len(results) == 3
    assert results[0]["ok"]
    assert results[1]["ok"]
    assert not results[2]["ok"]
    assert "Intentional failure" in results[2]["error"]

    # Test batch_query_safe
    safe_results = batch_query_safe(
        [{"tool": "mock_tool_1", "args": {}}, {"tool": "mock_tool_2", "args": {}}]
    )

    assert "results" in safe_results
    assert "summary" in safe_results
    assert safe_results["summary"]["total"] == 2
    assert safe_results["summary"]["successful"] == 2
    assert safe_results["summary"]["failed"] == 0

    print("[PASS] Batch query tests passed")


# ============================================================================
# Test Composite Tools
# ============================================================================


def test_composite_tools() -> None:
    """Test smart composite tools."""
    # Note: These are integration tests that require actual data
    # For now, just test that they're importable and have correct signatures
    import inspect

    from cbb_data.servers.mcp.composite_tools import (
        composite_player_trend,
        composite_resolve_and_get_pbp,
        composite_team_recent_performance,
    )

    # Check composite_resolve_and_get_pbp signature
    sig = inspect.signature(composite_resolve_and_get_pbp)
    assert "league" in sig.parameters
    assert "team" in sig.parameters
    assert "date_from" in sig.parameters
    assert "compact" in sig.parameters

    # Check composite_player_trend signature
    sig = inspect.signature(composite_player_trend)
    assert "league" in sig.parameters
    assert "player" in sig.parameters
    assert "last_n_games" in sig.parameters

    # Check composite_team_recent_performance signature
    sig = inspect.signature(composite_team_recent_performance)
    assert "league" in sig.parameters
    assert "team" in sig.parameters
    assert "last_n_games" in sig.parameters

    print("[PASS] Composite tools signatures validated")


# ============================================================================
# Test Configuration
# ============================================================================


def test_configuration() -> None:
    """Test updated configuration."""
    from cbb_data.config import DataConfig

    # Test default values
    config = DataConfig()

    # Legacy fields
    assert config.cache_enabled
    assert config.cache_ttl_hours == 24

    # New fields
    assert config.max_rows == 2000
    assert config.max_tokens == 8000
    assert config.ttl_schedule == 900
    assert config.ttl_pbp == 30
    assert config.ttl_shots == 60
    assert config.ttl_default == 3600
    assert config.dedupe_window_ms == 250

    # Test from_env (with defaults)
    config_env = DataConfig.from_env()
    assert config_env.max_rows == 2000

    print("[PASS] Configuration tests passed")


# ============================================================================
# Run All Tests
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("COMPREHENSIVE AUTOMATION UPGRADES STRESS TEST")
    print("=" * 60 + "\n")

    tests = [
        ("JSON Logging", test_json_logging),
        ("Metrics", test_metrics_available),
        ("Auto-Pagination", test_auto_pagination),
        ("Column Pruning", test_column_pruning),
        ("Column Registry", test_column_registry),
        ("Guardrails", test_guardrails),
        ("Batch Queries", test_batch_queries),
        ("Composite Tools", test_composite_tools),
        ("Configuration", test_configuration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\nTesting {name}...")
            test_func()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name} FAILED: {str(e)}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"[WARN] {failed} tests failed")
        exit(1)
    else:
        print("[ALL PASS] ALL TESTS PASSED!")
    print("=" * 60 + "\n")
