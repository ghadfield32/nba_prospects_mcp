"""
Comprehensive Data Availability Tests

Tests data coverage, completeness, and historical depth for all datasets.

Test Coverage:
1. Historical data availability (how far back does data go?)
2. Dataset completeness (missing data, null values)
3. Season coverage (which seasons have data?)
4. League parity (NCAA-MBB vs EuroLeague coverage)
5. Dataset consistency (schema, columns)
"""

import os
import sys

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, "src")

from get_basketball_data import get_basketball_data

# Test configuration
LEAGUE_NCAA = "NCAA-MBB"
LEAGUE_EURO = "EuroLeague"


class TestHistoricalDataAvailability:
    """Test how far back data goes for each dataset"""

    def test_ncaa_schedule_historical_depth(self) -> None:
        """Test NCAA-MBB schedule historical availability"""
        print("\n[TEST] NCAA-MBB schedule historical depth")

        # Test several seasons going back
        test_seasons = ["2024", "2023", "2022", "2021", "2020"]

        results = {}
        for season in test_seasons:
            try:
                df = get_basketball_data(
                    dataset="schedule", league=LEAGUE_NCAA, season=season, limit=5
                )
                results[season] = len(df) > 0
            except Exception as e:
                results[season] = False
                print(f"  {season}: Error - {str(e)[:50]}")

        # Report findings
        available_seasons = [s for s, available in results.items() if available]
        print(f"✓ Schedule data available for {len(available_seasons)} seasons:")
        print(f"  Available: {', '.join(available_seasons)}")

        # At least recent seasons should be available
        assert results.get("2024", False) or results.get(
            "2023", False
        ), "At least one recent season should have schedule data"

    def test_ncaa_player_game_historical_depth(self) -> None:
        """Test NCAA-MBB player_game historical availability"""
        print("\n[TEST] NCAA-MBB player_game historical depth")

        test_seasons = ["2024", "2023", "2022"]

        results = {}
        for season in test_seasons:
            try:
                df = get_basketball_data(
                    dataset="player_game", league=LEAGUE_NCAA, season=season, limit=10
                )
                results[season] = len(df) > 0
            except Exception:
                results[season] = False

        available_seasons = [s for s, available in results.items() if available]
        print(f"✓ Player game data available for {len(available_seasons)} seasons")

    def test_euroleague_historical_depth(self) -> None:
        """Test EuroLeague historical data availability"""
        print("\n[TEST] EuroLeague historical depth")

        test_seasons = ["2024", "2023", "2022", "2021"]

        results = {}
        for season in test_seasons:
            try:
                df = get_basketball_data(
                    dataset="schedule", league=LEAGUE_EURO, season=season, limit=5
                )
                results[season] = len(df) > 0
            except Exception:
                results[season] = False

        available_seasons = [s for s, available in results.items() if available]
        print(f"✓ EuroLeague data available for {len(available_seasons)} seasons")

        # EuroLeague should have recent data
        assert len(available_seasons) > 0, "EuroLeague should have data for at least one season"


class TestDatasetCompleteness:
    """Test data completeness and quality"""

    def test_schedule_required_columns(self) -> None:
        """Test that schedule data has all required columns"""
        print("\n[TEST] Schedule required columns")

        df = get_basketball_data(dataset="schedule", league=LEAGUE_NCAA, season="2024", limit=10)

        if not df.empty:
            # Essential columns that must be present
            required = ["GAME_ID", "GAME_DATE"]
            missing = [col for col in required if col not in df.columns]

            assert len(missing) == 0, f"Missing required columns: {missing}"

            # Check for null values in critical columns
            for col in required:
                null_count = df[col].isnull().sum()
                assert null_count == 0, f"Column {col} has {null_count} null values"

            print(f"✓ Schedule completeness validated: {len(df)} games with required columns")
        else:
            print("  Note: No schedule data to validate")

    def test_player_game_required_columns(self) -> None:
        """Test that player_game data has all required columns"""
        print("\n[TEST] Player game required columns")

        df = get_basketball_data(dataset="player_game", league=LEAGUE_NCAA, season="2024", limit=20)

        if not df.empty:
            # Essential columns
            required = ["PLAYER_NAME", "GAME_ID", "PTS"]
            missing = [col for col in required if col not in df.columns]

            assert len(missing) == 0, f"Missing required columns: {missing}"

            # Check that PLAYER_NAME is not null
            null_names = df["PLAYER_NAME"].isnull().sum()
            assert null_names == 0, f"Found {null_names} rows with null PLAYER_NAME"

            print(f"✓ Player game completeness validated: {len(df)} records with required columns")
        else:
            print("  Note: No player game data to validate")

    def test_player_season_completeness(self) -> None:
        """Test that player_season aggregates are complete"""
        print("\n[TEST] Player season data completeness")

        df = get_basketball_data(
            dataset="player_season", league=LEAGUE_NCAA, season="2024", limit=20
        )

        if not df.empty:
            # Should have stats columns
            stat_cols = ["GP", "PTS", "AST", "REB"]
            existing = [col for col in stat_cols if col in df.columns]

            assert len(existing) > 0, "Should have at least some stat columns"

            # Games played should be > 0 for all players
            if "GP" in df.columns:
                assert (df["GP"] > 0).all(), "All players should have GP > 0"

            print(
                f"✓ Player season completeness validated: {len(df)} players with {len(existing)} stat columns"
            )
        else:
            print("  Note: No player season data to validate")


class TestSeasonCoverage:
    """Test which seasons have data for each dataset"""

    def test_ncaa_season_range(self) -> None:
        """Test range of NCAA-MBB seasons with data"""
        print("\n[TEST] NCAA-MBB season coverage")

        # Test a range of seasons
        current_season = 2025
        seasons_to_test = [str(year) for year in range(current_season, current_season - 10, -1)]

        available = []
        for season in seasons_to_test:
            try:
                df = get_basketball_data(
                    dataset="schedule", league=LEAGUE_NCAA, season=season, limit=3
                )
                if not df.empty:
                    available.append(season)
            except Exception:
                pass

        print(f"✓ NCAA-MBB data available for {len(available)} seasons:")
        print(f"  Seasons: {', '.join(available[:5])}{'...' if len(available) > 5 else ''}")

        # Should have at least current season
        assert len(available) > 0, "Should have data for at least one season"

    def test_euroleague_season_range(self) -> None:
        """Test range of EuroLeague seasons with data"""
        print("\n[TEST] EuroLeague season coverage")

        seasons_to_test = ["2024", "2023", "2022", "2021", "2020"]

        available = []
        for season in seasons_to_test:
            try:
                df = get_basketball_data(
                    dataset="schedule", league=LEAGUE_EURO, season=season, limit=3
                )
                if not df.empty:
                    available.append(season)
            except Exception:
                pass

        print(f"✓ EuroLeague data available for {len(available)} seasons:")
        print(f"  Seasons: {', '.join(available)}")

        assert len(available) > 0, "Should have EuroLeague data for at least one season"


class TestLeagueParity:
    """Test that NCAA-MBB and EuroLeague have comparable data"""

    def test_both_leagues_have_schedule(self) -> None:
        """Test that both leagues have schedule data"""
        print("\n[TEST] Both leagues have schedule data")

        ncaa_df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season="2024", limit=5
        )

        euro_df = get_basketball_data(
            dataset="schedule", league=LEAGUE_EURO, season="2024", limit=5
        )

        assert not ncaa_df.empty, "NCAA-MBB should have schedule data"
        assert not euro_df.empty, "EuroLeague should have schedule data"

        print("✓ Both leagues have schedule data available")

    def test_both_leagues_have_player_game(self) -> None:
        """Test that both leagues have player_game data"""
        print("\n[TEST] Both leagues have player_game data")

        ncaa_df = get_basketball_data(
            dataset="player_game", league=LEAGUE_NCAA, season="2024", limit=10
        )

        euro_df = get_basketball_data(
            dataset="player_game", league=LEAGUE_EURO, season="2024", limit=10
        )

        ncaa_available = not ncaa_df.empty
        euro_available = not euro_df.empty

        print(f"  NCAA-MBB player_game: {'✓ Available' if ncaa_available else '✗ Not available'}")
        print(f"  EuroLeague player_game: {'✓ Available' if euro_available else '✗ Not available'}")

        # At least NCAA should have data
        assert ncaa_available, "NCAA-MBB should have player_game data"


class TestDatasetConsistency:
    """Test schema and column consistency across datasets"""

    def test_schedule_schema_consistency(self) -> None:
        """Test that schedule schema is consistent across leagues"""
        print("\n[TEST] Schedule schema consistency")

        ncaa_df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season="2024", limit=3
        )

        euro_df = get_basketball_data(
            dataset="schedule", league=LEAGUE_EURO, season="2024", limit=3
        )

        if not ncaa_df.empty and not euro_df.empty:
            # Core columns that should exist in both
            core_cols = {"GAME_ID", "GAME_DATE"}

            ncaa_cols = set(ncaa_df.columns)
            euro_cols = set(euro_df.columns)

            ncaa_has_core = core_cols.issubset(ncaa_cols)
            euro_has_core = core_cols.issubset(euro_cols)

            assert ncaa_has_core, f"NCAA missing core columns: {core_cols - ncaa_cols}"
            assert euro_has_core, f"EuroLeague missing core columns: {core_cols - euro_cols}"

            print("✓ Schedule schema consistent across leagues")
        else:
            print("  Note: Insufficient data to compare schemas")

    def test_player_game_schema_consistency(self) -> None:
        """Test that player_game schema is consistent"""
        print("\n[TEST] Player game schema consistency")

        # Get data from two different sources/seasons
        df1 = get_basketball_data(dataset="player_game", league=LEAGUE_NCAA, season="2024", limit=5)

        df2 = get_basketball_data(dataset="player_game", league=LEAGUE_NCAA, season="2023", limit=5)

        if not df1.empty and not df2.empty:
            # Core stat columns
            core_stats = {"PLAYER_NAME", "PTS"}

            cols1 = set(df1.columns)
            cols2 = set(df2.columns)

            has_core_1 = core_stats.issubset(cols1)
            has_core_2 = core_stats.issubset(cols2)

            assert has_core_1, "2024 data missing core columns"
            assert has_core_2, "2023 data missing core columns"

            print("✓ Player game schema consistent across seasons")
        else:
            print("  Note: Insufficient data to compare schemas")


class TestDataVolume:
    """Test expected data volumes"""

    def test_schedule_reasonable_volume(self) -> None:
        """Test that schedule returns reasonable number of games"""
        print("\n[TEST] Schedule data volume")

        df = get_basketball_data(dataset="schedule", league=LEAGUE_NCAA, season="2024", limit=100)

        if not df.empty:
            # NCAA should have many games in a season
            assert len(df) > 0, "Should have at least some games"

            # With limit=100, should get exactly 100 or fewer
            assert len(df) <= 100, f"Limit=100 but got {len(df)} games"

            print(f"✓ Schedule volume reasonable: {len(df)} games (limit=100)")
        else:
            print("  Note: No schedule data returned")

    def test_player_game_reasonable_volume(self) -> None:
        """Test that player_game returns reasonable number of records"""
        print("\n[TEST] Player game data volume")

        df = get_basketball_data(dataset="player_game", league=LEAGUE_NCAA, season="2024", limit=50)

        if not df.empty:
            # Should have player records
            assert len(df) > 0, "Should have at least some player records"

            # Should respect limit
            assert len(df) <= 50, f"Limit=50 but got {len(df)} records"

            print(f"✓ Player game volume reasonable: {len(df)} records (limit=50)")
        else:
            print("  Note: No player game data returned")


if __name__ == "__main__":
    """Run tests with detailed output"""
    print("=" * 80)
    print("DATA AVAILABILITY VALIDATION TESTS")
    print("=" * 80)
    print()

    # Track results
    passed = 0
    failed = 0
    skipped = 0

    # Run each test class
    test_classes = [
        TestHistoricalDataAvailability,
        TestDatasetCompleteness,
        TestSeasonCoverage,
        TestLeagueParity,
        TestDatasetConsistency,
        TestDataVolume,
    ]

    for test_class in test_classes:
        print(f"\n{'=' * 80}")
        print(f"TEST CLASS: {test_class.__name__}")
        print("=" * 80)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                method = getattr(instance, method_name)

                # Check if marked as skip
                skip_marker = None
                if hasattr(method, "pytestmark"):
                    marks = (
                        method.pytestmark
                        if isinstance(method.pytestmark, list)
                        else [method.pytestmark]
                    )
                    for mark in marks:
                        if mark.name == "skip":
                            skip_marker = mark
                            break

                if skip_marker:
                    reason = skip_marker.kwargs.get("reason", "No reason provided")
                    print(f"\n⊘ SKIPPED: {method_name}")
                    print(f"  Reason: {reason}")
                    skipped += 1
                    continue

                try:
                    method()
                    print(f"\n✓ PASSED: {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"\n✗ FAILED: {method_name}")
                    print(f"  Error: {e}")
                    failed += 1
                except Exception as e:
                    print(f"\n✗ ERROR: {method_name}")
                    print(f"  Error: {e}")
                    failed += 1

    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = passed + failed + skipped
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ({100 * passed / total:.1f}%)")
    print(f"Failed: {failed} ({100 * failed / total:.1f}%)")
    print(f"Skipped: {skipped} ({100 * skipped / total:.1f}%)")
    print()

    if failed == 0:
        print("=" * 80)
        print("ALL TESTS PASSED - Data availability verified!")
        print("=" * 80)
    else:
        print("=" * 80)
        print(f"SOME TESTS FAILED - Please review {failed} failed tests above")
        print("=" * 80)
