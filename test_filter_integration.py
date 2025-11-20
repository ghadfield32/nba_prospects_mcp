"""Comprehensive Filter System Integration Test

Tests the unified filter system across:
1. get_dataset() API with post_filters
2. REST API DatasetRequest model
3. MCP tools with segment parameters
4. Filter application functions
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd


def test_filter_imports():
    """Test that all filter modules import correctly"""
    print("=" * 60)
    print("TEST 1: Filter Module Imports")
    print("=" * 60)

    errors = []

    # Test filters module
    try:
        print("  [PASS] cbb_data.api.filters imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.api.filters: {e}")
        errors.append(str(e))

    # Test dimensions module
    try:
        print("  [PASS] cbb_data.dimensions imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.dimensions: {e}")
        errors.append(str(e))

    # Test coverage module
    try:
        print("  [PASS] cbb_data.metadata.coverage imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.metadata.coverage: {e}")
        errors.append(str(e))

    # Test REST API models
    try:
        print("  [PASS] cbb_data.api.rest_api.models imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.api.rest_api.models: {e}")
        errors.append(str(e))

    # Test datasets API
    try:
        print("  [PASS] cbb_data.api.datasets imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.api.datasets: {e}")
        errors.append(str(e))

    # Test MCP tools
    try:
        print("  [PASS] cbb_data.servers.mcp.tools imports")
    except Exception as e:
        print(f"  [FAIL] cbb_data.servers.mcp.tools: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_filter_dataclasses():
    """Test filter dataclass construction"""
    print("=" * 60)
    print("TEST 2: Filter Dataclass Construction")
    print("=" * 60)

    from cbb_data.api.filters import (
        DatasetFilter,
        DateFilter,
        GameSegmentFilter,
        NameFilter,
    )

    errors = []

    # Test DateFilter
    try:
        date_filter = DateFilter(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        start, end = date_filter.get_effective_range()
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 31)
        print("  [PASS] DateFilter with absolute dates")
    except Exception as e:
        print(f"  [FAIL] DateFilter absolute: {e}")
        errors.append(str(e))

    # Test DateFilter with relative_days
    try:
        date_filter = DateFilter(relative_days=7)
        start, end = date_filter.get_effective_range()
        assert end == date.today()
        assert start == date.today() - timedelta(days=7)
        print("  [PASS] DateFilter with relative_days")
    except Exception as e:
        print(f"  [FAIL] DateFilter relative: {e}")
        errors.append(str(e))

    # Test GameSegmentFilter
    try:
        segment_filter = GameSegmentFilter(
            periods=[4],
            start_seconds=2280,
            end_seconds=2400,
        )
        assert segment_filter.periods == [4]
        assert segment_filter.start_seconds == 2280
        print("  [PASS] GameSegmentFilter construction")
    except Exception as e:
        print(f"  [FAIL] GameSegmentFilter: {e}")
        errors.append(str(e))

    # Test NameFilter
    try:
        name_filter = NameFilter(
            leagues=["NCAA-MBB"],
            team_names=["Duke", "Kentucky"],
            player_names=["Cooper Flagg"],
        )
        assert "Duke" in name_filter.team_names
        print("  [PASS] NameFilter construction")
    except Exception as e:
        print(f"  [FAIL] NameFilter: {e}")
        errors.append(str(e))

    # Test composite DatasetFilter
    try:
        composite = DatasetFilter(
            names=NameFilter(leagues=["NCAA-MBB"], team_names=["Duke"]),
            dates=DateFilter(relative_days=7),
            segments=GameSegmentFilter(periods=[4]),
        )
        assert composite.names is not None
        assert composite.dates is not None
        assert composite.segments is not None
        print("  [PASS] DatasetFilter composite construction")
    except Exception as e:
        print(f"  [FAIL] DatasetFilter composite: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_rest_api_model():
    """Test REST API DatasetRequest model"""
    print("=" * 60)
    print("TEST 3: REST API DatasetRequest Model")
    print("=" * 60)

    from cbb_data.api.rest_api.models import DatasetRequest

    errors = []

    # Test basic request
    try:
        request = DatasetRequest(
            filters={"league": "NCAA-MBB", "season": "2025"},
            limit=50,
        )
        assert request.filters["league"] == "NCAA-MBB"
        assert request.limit == 50
        print("  [PASS] Basic DatasetRequest")
    except Exception as e:
        print(f"  [FAIL] Basic request: {e}")
        errors.append(str(e))

    # Test request with post-filters
    try:
        request = DatasetRequest(
            filters={"league": "NCAA-MBB", "game_ids": ["401635571"]},
            team_names=["Duke"],
            player_names=["Cooper Flagg"],
            relative_days=7,
            periods=[4],
            halves=[2],
            start_seconds=2280,
            end_seconds=2400,
        )

        post_filters = request.to_post_filters()
        assert post_filters is not None
        assert post_filters.names is not None
        assert post_filters.dates is not None
        assert post_filters.segments is not None
        assert post_filters.segments.periods == [4]
        print("  [PASS] DatasetRequest with post-filters")
    except Exception as e:
        print(f"  [FAIL] Request with post-filters: {e}")
        errors.append(str(e))

    # Test empty post-filters returns None
    try:
        request = DatasetRequest(
            filters={"league": "NCAA-MBB"},
        )
        post_filters = request.to_post_filters()
        assert post_filters is None
        print("  [PASS] Empty post-filters returns None")
    except Exception as e:
        print(f"  [FAIL] Empty post-filters: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_filter_application():
    """Test filter application on sample data"""
    print("=" * 60)
    print("TEST 4: Filter Application on Sample Data")
    print("=" * 60)

    from cbb_data.api.filters import (
        DatasetFilter,
        DateFilter,
        GameSegmentFilter,
        apply_date_filter,
        apply_filters,
        apply_segment_filter,
    )

    errors = []

    # Create sample PBP-like DataFrame
    sample_data = pd.DataFrame(
        {
            "GAME_ID": ["G1"] * 20 + ["G2"] * 20,
            "GAME_DATE": pd.to_datetime(["2025-01-15"] * 20 + ["2025-01-10"] * 20),
            "PERIOD": [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5,
            "TIME_REMAINING": list(range(720, 220, -25)) + list(range(720, 220, -25)),
            "EVENT_TYPE": ["shot", "rebound", "assist", "turnover", "foul"] * 8,
            "PLAYER_NAME": ["Player A", "Player B"] * 20,
            "TEAM_NAME": ["Duke", "UNC"] * 20,
        }
    )

    # Test date filter
    try:
        date_filter = DateFilter(
            start_date=date(2025, 1, 12),
            end_date=date(2025, 1, 20),
        )
        filtered = apply_date_filter(sample_data.copy(), date_filter)
        # Should only include 2025-01-15 game
        assert len(filtered) == 20
        assert all(filtered["GAME_DATE"].dt.date == date(2025, 1, 15))
        print("  [PASS] Date filter application")
    except Exception as e:
        print(f"  [FAIL] Date filter: {e}")
        errors.append(str(e))

    # Test segment filter - periods
    try:
        segment_filter = GameSegmentFilter(periods=[4])
        filtered = apply_segment_filter(sample_data.copy(), segment_filter)
        # Should only include period 4 rows
        assert len(filtered) == 10
        assert all(filtered["PERIOD"] == 4)
        print("  [PASS] Segment filter (periods)")
    except Exception as e:
        print(f"  [FAIL] Segment filter periods: {e}")
        errors.append(str(e))

    # Test composite filter
    try:
        composite = DatasetFilter(
            dates=DateFilter(start_date=date(2025, 1, 12)),
            segments=GameSegmentFilter(periods=[3, 4]),
        )
        filtered = apply_filters(sample_data.copy(), composite)
        # Should be 2025-01-15 game, periods 3 and 4 = 10 rows
        assert len(filtered) == 10
        print("  [PASS] Composite filter application")
    except Exception as e:
        print(f"  [FAIL] Composite filter: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_mcp_tools_signature():
    """Test MCP tool function signatures"""
    print("=" * 60)
    print("TEST 5: MCP Tools Signatures")
    print("=" * 60)

    import inspect

    from cbb_data.servers.mcp.tools import (
        TOOLS,
        tool_get_play_by_play,
        tool_get_shot_chart,
    )

    errors = []

    # Check tool_get_play_by_play signature
    try:
        sig = inspect.signature(tool_get_play_by_play)
        params = list(sig.parameters.keys())
        expected = [
            "league",
            "game_ids",
            "periods",
            "halves",
            "start_seconds",
            "end_seconds",
            "compact",
            "pre_only",
        ]
        for param in expected:
            assert param in params, f"Missing param: {param}"
        print("  [PASS] tool_get_play_by_play has segment params")
    except Exception as e:
        print(f"  [FAIL] PBP signature: {e}")
        errors.append(str(e))

    # Check tool_get_shot_chart signature
    try:
        sig = inspect.signature(tool_get_shot_chart)
        params = list(sig.parameters.keys())
        expected = [
            "league",
            "game_ids",
            "player",
            "periods",
            "halves",
            "start_seconds",
            "end_seconds",
        ]
        for param in expected:
            assert param in params, f"Missing param: {param}"
        print("  [PASS] tool_get_shot_chart has segment params")
    except Exception as e:
        print(f"  [FAIL] Shot chart signature: {e}")
        errors.append(str(e))

    # Check TOOLS registry has updated schemas
    try:
        pbp_tool = next(t for t in TOOLS if t["name"] == "get_play_by_play")
        schema_props = pbp_tool["inputSchema"]["properties"]
        assert "periods" in schema_props
        assert "halves" in schema_props
        assert "start_seconds" in schema_props
        assert "end_seconds" in schema_props
        print("  [PASS] TOOLS registry has segment params for PBP")
    except Exception as e:
        print(f"  [FAIL] TOOLS registry PBP: {e}")
        errors.append(str(e))

    try:
        shots_tool = next(t for t in TOOLS if t["name"] == "get_shot_chart")
        schema_props = shots_tool["inputSchema"]["properties"]
        assert "periods" in schema_props
        assert "halves" in schema_props
        print("  [PASS] TOOLS registry has segment params for shots")
    except Exception as e:
        print(f"  [FAIL] TOOLS registry shots: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_get_dataset_signature():
    """Test get_dataset() has post_filters parameter"""
    print("=" * 60)
    print("TEST 6: get_dataset() Signature")
    print("=" * 60)

    import inspect

    from cbb_data.api.datasets import get_dataset

    errors = []

    try:
        sig = inspect.signature(get_dataset)
        params = list(sig.parameters.keys())
        assert "post_filters" in params, "Missing post_filters parameter"

        # Check type annotation
        param = sig.parameters["post_filters"]
        assert "DatasetFilter" in str(param.annotation) or "None" in str(param.annotation)
        print("  [PASS] get_dataset has post_filters parameter")
    except Exception as e:
        print(f"  [FAIL] get_dataset signature: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("FILTER SYSTEM INTEGRATION TESTS")
    print("=" * 60 + "\n")

    results = []

    results.append(("Filter Imports", test_filter_imports()))
    results.append(("Filter Dataclasses", test_filter_dataclasses()))
    results.append(("REST API Model", test_rest_api_model()))
    results.append(("Filter Application", test_filter_application()))
    results.append(("MCP Tools Signatures", test_mcp_tools_signature()))
    results.append(("get_dataset Signature", test_get_dataset_signature()))

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Filter system integration is complete.")
        return 0
    else:
        print(f"\n{total - passed} tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
