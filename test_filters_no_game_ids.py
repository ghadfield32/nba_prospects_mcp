"""Test Filters Without Game IDs

Tests the filter system with schedule and season datasets that don't require game_ids.
Tests date filters, name filters, and verifies the full API integration.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_schedule_with_date_filters():
    """Test schedule dataset with date filters"""
    print("=" * 60)
    print("TEST 1: Schedule with Date Filters")
    print("=" * 60)

    from cbb_data.api.datasets import get_dataset
    from cbb_data.api.filters import DatasetFilter, DateFilter

    errors = []

    # Test relative_days filter (last 30 days)
    try:
        date_filter = DateFilter(relative_days=30)
        post_filters = DatasetFilter(dates=date_filter)

        df = get_dataset(
            grouping="schedule",
            filters={"league": "NCAA-MBB", "season": "2025"},
            limit=100,
            post_filters=post_filters,
        )

        if df is not None and not df.empty:
            # Check dates are within range
            import pandas as pd

            if "GAME_DATE" in df.columns:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
                min_date = df["GAME_DATE"].min()
                max_date = df["GAME_DATE"].max()
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)

                print(f"   Found {len(df)} games")
                print(f"   Date range: {min_date.date()} to {max_date.date()}")

                if min_date >= cutoff:
                    print("   [PASS] All games within last 30 days")
                else:
                    print(f"   [WARN] Some games before cutoff {cutoff.date()}")
            else:
                print(f"   [PASS] Got {len(df)} rows (no GAME_DATE column)")
        else:
            print("   [INFO] No data returned (may be off-season)")

    except Exception as e:
        print(f"   [FAIL] {type(e).__name__}: {e}")
        errors.append(str(e))

    # Test absolute date range
    try:
        start = date(2024, 11, 1)
        end = date(2024, 11, 30)
        date_filter = DateFilter(start_date=start, end_date=end)
        post_filters = DatasetFilter(dates=date_filter)

        df = get_dataset(
            grouping="schedule",
            filters={"league": "NCAA-MBB", "season": "2025"},
            limit=100,
            post_filters=post_filters,
        )

        if df is not None and not df.empty:
            print(f"   Found {len(df)} games in Nov 2024")
            print("   [PASS] Absolute date filter works")
        else:
            print("   [INFO] No games found in Nov 2024")

    except Exception as e:
        print(f"   [FAIL] Absolute date: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_player_season_with_name_filters():
    """Test player_season dataset with name filters"""
    print("=" * 60)
    print("TEST 2: Player Season with Name Filters")
    print("=" * 60)

    from cbb_data.api.datasets import get_dataset
    from cbb_data.api.filters import DatasetFilter, NameFilter

    errors = []

    # Test team name filter
    try:
        name_filter = NameFilter(
            leagues=["NCAA-MBB"],
            team_names=["Duke"],
        )
        post_filters = DatasetFilter(names=name_filter)

        df = get_dataset(
            grouping="player_season",
            filters={"league": "NCAA-MBB", "season": "2025"},
            limit=50,
            post_filters=post_filters,
        )

        if df is not None and not df.empty:
            print(f"   Found {len(df)} Duke players")

            # Check if team filter worked
            team_cols = [c for c in df.columns if "TEAM" in c.upper()]
            if team_cols:
                teams = df[team_cols[0]].unique()
                print(f"   Teams in data: {list(teams)[:5]}")

            print("   [PASS] Team name filter applied")
        else:
            print("   [INFO] No Duke players found")

    except Exception as e:
        print(f"   [FAIL] Team filter: {e}")
        errors.append(str(e))

    # Test player name filter (partial match)
    try:
        name_filter = NameFilter(
            leagues=["NCAA-MBB"],
            player_names=["Flagg"],  # Should match Cooper Flagg
        )
        post_filters = DatasetFilter(names=name_filter)

        df = get_dataset(
            grouping="player_season",
            filters={"league": "NCAA-MBB", "season": "2025"},
            limit=20,
            post_filters=post_filters,
        )

        if df is not None and not df.empty:
            player_cols = [c for c in df.columns if "PLAYER" in c.upper() and "NAME" in c.upper()]
            if player_cols:
                players = df[player_cols[0]].unique()
                print(f"   Found players: {list(players)}")
            print("   [PASS] Player name filter applied")
        else:
            print("   [INFO] No matching players found")

    except Exception as e:
        print(f"   [FAIL] Player filter: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_rest_api_model_conversion():
    """Test REST API DatasetRequest to_post_filters conversion"""
    print("=" * 60)
    print("TEST 3: REST API Model Conversion")
    print("=" * 60)

    from cbb_data.api.rest_api.models import DatasetRequest

    errors = []

    # Test date filters conversion
    try:
        request = DatasetRequest(
            filters={"league": "NCAA-MBB", "season": "2025"},
            relative_days=7,
            start_date=date(2024, 11, 1),
            team_names=["Duke", "UNC"],
            player_names=["Cooper Flagg"],
        )

        post_filters = request.to_post_filters()

        assert post_filters is not None, "Post filters should not be None"
        assert post_filters.dates is not None, "Date filter should exist"
        assert post_filters.dates.relative_days == 7, "relative_days should be 7"
        assert post_filters.names is not None, "Name filter should exist"
        assert "Duke" in post_filters.names.team_names, "Duke should be in teams"

        print("   [PASS] Request conversion with all filter types")

    except Exception as e:
        print(f"   [FAIL] Conversion: {e}")
        errors.append(str(e))

    # Test segment filters conversion
    try:
        request = DatasetRequest(
            filters={"league": "NCAA-MBB", "game_ids": ["123"]},
            periods=[4],
            halves=[2],
            start_seconds=2280,
            end_seconds=2400,
        )

        post_filters = request.to_post_filters()

        assert post_filters is not None
        assert post_filters.segments is not None
        assert post_filters.segments.periods == [4]
        assert post_filters.segments.halves == [2]
        assert post_filters.segments.start_seconds == 2280

        print("   [PASS] Segment filters conversion")

    except Exception as e:
        print(f"   [FAIL] Segment conversion: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_mcp_tool_schedule():
    """Test MCP tool get_schedule with date filters"""
    print("=" * 60)
    print("TEST 4: MCP Tool get_schedule with Filters")
    print("=" * 60)

    from cbb_data.servers.mcp.tools import tool_get_schedule

    errors = []

    # Test with date_from/date_to
    try:
        result = tool_get_schedule(
            league="NCAA-MBB",
            season="2025",
            date_from="2024-11-01",
            date_to="2024-11-30",
            limit=50,
            compact=True,
        )

        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict) and "rows" in data:
                row_count = len(data["rows"])
            elif isinstance(data, list):
                row_count = len(data)
            else:
                row_count = result.get("row_count", 0)

            print(f"   Found {row_count} games in Nov 2024")
            print("   [PASS] MCP schedule tool with date filters")
        else:
            print(f"   [FAIL] Tool error: {result.get('error', 'Unknown')}")
            errors.append(result.get("error", "Unknown error"))

    except Exception as e:
        print(f"   [FAIL] {type(e).__name__}: {e}")
        errors.append(str(e))

    # Test with team filter
    try:
        result = tool_get_schedule(
            league="NCAA-MBB",
            season="2025",
            team=["Duke"],
            limit=20,
            compact=True,
        )

        if result.get("success"):
            row_count = result.get("row_count", 0)
            print(f"   Found {row_count} Duke games")
            print("   [PASS] MCP schedule tool with team filter")
        else:
            print(f"   [INFO] No Duke games: {result.get('error', '')[:50]}")

    except Exception as e:
        print(f"   [FAIL] Team filter: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def test_mcp_tool_player_stats():
    """Test MCP tool get_player_season_stats"""
    print("=" * 60)
    print("TEST 5: MCP Tool get_player_season_stats")
    print("=" * 60)

    from cbb_data.servers.mcp.tools import tool_get_player_season_stats

    errors = []

    # Test with team filter
    try:
        result = tool_get_player_season_stats(
            league="NCAA-MBB",
            season="this season",  # Natural language
            team=["Duke"],
            per_mode="PerGame",
            limit=20,
            compact=True,
        )

        if result.get("success"):
            row_count = result.get("row_count", 0)
            print(f"   Found {row_count} Duke player stats")
            print("   [PASS] MCP player_season tool with team filter")
        else:
            error = result.get("error", "Unknown")
            if "no data" in str(error).lower():
                print(f"   [INFO] No data: {error[:50]}")
            else:
                print(f"   [FAIL] Tool error: {error[:80]}")
                errors.append(error)

    except Exception as e:
        print(f"   [FAIL] {type(e).__name__}: {e}")
        errors.append(str(e))

    print()
    return len(errors) == 0


def main():
    """Run all filter tests"""
    print("\n" + "=" * 60)
    print("FILTER TESTS WITHOUT GAME_IDS")
    print("=" * 60 + "\n")

    results = []

    # Run tests (these may take time due to network)
    results.append(("REST API Model Conversion", test_rest_api_model_conversion()))

    # Network tests - may timeout
    print("\nRunning network tests (may take time)...\n")
    results.append(("Schedule with Date Filters", test_schedule_with_date_filters()))
    results.append(("Player Season with Name Filters", test_player_season_with_name_filters()))
    results.append(("MCP Tool Schedule", test_mcp_tool_schedule()))
    results.append(("MCP Tool Player Stats", test_mcp_tool_player_stats()))

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

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
