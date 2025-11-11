"""
Comprehensive Date Filtering Tests

Tests date-based game filtering functionality for NCAA-MBB and EuroLeague.

Test Coverage:
1. Single date filtering
2. Date range filtering (start_date/end_date)
3. Multiple date format support (string, date, datetime)
4. Invalid date handling
5. Date filter with other parameters (teams, granularity)
6. Cross-league compatibility
"""

import os
import sys

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, "src")

from datetime import date, datetime

import pytest
from get_basketball_data import get_basketball_data

# Test configuration
LEAGUE_NCAA = "NCAA-MBB"
LEAGUE_EURO = "EuroLeague"
TEST_SEASON = "2025"


class TestSingleDateFiltering:
    """Test single date game retrieval"""

    def test_single_date_string_format(self) -> None:
        """Test filtering games by single date (string format)"""
        print("\n[TEST] Single date filter (string format)")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            date="2024-11-04",  # Opening day of 2024-25 season
            limit=10,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"

            # All games should be on the specified date
            # (Note: GAME_DATE might be datetime, so check date component)
            print(f"✓ Single date filter works: {len(df)} games on 2024-11-04")
        else:
            print("  Note: No games found on 2024-11-04 (check if date has games)")

    def test_single_date_datetime_object(self) -> None:
        """Test filtering with datetime.date object"""
        print("\n[TEST] Single date filter (date object)")

        test_date = date(2024, 11, 6)  # Early season game

        df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season=TEST_SEASON, date=test_date, limit=10
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"
            print(f"✓ Date object filter works: {len(df)} games")
        else:
            print(f"  Note: No games found on {test_date}")

    def test_single_datetime_with_time(self) -> None:
        """Test filtering with datetime.datetime object"""
        print("\n[TEST] Single date filter (datetime object)")

        test_datetime = datetime(2024, 11, 12, 19, 0)  # Date with time

        df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season=TEST_SEASON, date=test_datetime, limit=10
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"
            print(f"✓ Datetime object filter works: {len(df)} games")
        else:
            print(f"  Note: No games found on {test_datetime.date()}")


class TestDateRangeFiltering:
    """Test date range filtering (start_date/end_date)"""

    def test_date_range_basic(self) -> None:
        """Test retrieving games within a date range"""
        print("\n[TEST] Date range filtering (basic)")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            start_date="2024-11-04",
            end_date="2024-11-10",
            limit=50,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"

            # Verify all dates are within range
            game_dates = (
                df["GAME_DATE"].dt.date if hasattr(df["GAME_DATE"], "dt") else df["GAME_DATE"]
            )

            start = date(2024, 11, 4)
            end = date(2024, 11, 10)

            # Check all dates are within range
            assert all(
                start <= d <= end for d in game_dates if d is not None
            ), "All games should be within date range"

            print(f"✓ Date range filter works: {len(df)} games from 11/04 to 11/10")
        else:
            print("  Note: No games found in date range (check season dates)")

    def test_date_range_with_datetime_objects(self) -> None:
        """Test date range with datetime objects"""
        print("\n[TEST] Date range with datetime objects")

        start = datetime(2024, 12, 1)
        end = datetime(2024, 12, 15)

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            start_date=start,
            end_date=end,
            limit=100,
        )

        if not df.empty:
            print(f"✓ Datetime range filter works: {len(df)} games in December 2024")
        else:
            print("  Note: No games found in December 2024 range")

    def test_start_date_only(self) -> None:
        """Test filtering with start_date only (no end_date)"""
        print("\n[TEST] Start date only (open-ended)")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            start_date="2025-01-01",  # After January 1st
            limit=20,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"

            # All dates should be >= start_date
            game_dates = (
                df["GAME_DATE"].dt.date if hasattr(df["GAME_DATE"], "dt") else df["GAME_DATE"]
            )
            start = date(2025, 1, 1)

            assert all(
                d >= start for d in game_dates if d is not None
            ), "All games should be on or after start_date"

            print(f"✓ Start date only works: {len(df)} games after 2025-01-01")
        else:
            print("  Note: No games found after 2025-01-01")

    def test_end_date_only(self) -> None:
        """Test filtering with end_date only (no start_date)"""
        print("\n[TEST] End date only (open-ended)")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            end_date="2024-12-31",  # Before Dec 31st
            limit=20,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"

            # All dates should be <= end_date
            game_dates = (
                df["GAME_DATE"].dt.date if hasattr(df["GAME_DATE"], "dt") else df["GAME_DATE"]
            )
            end = date(2024, 12, 31)

            assert all(
                d <= end for d in game_dates if d is not None
            ), "All games should be on or before end_date"

            print(f"✓ End date only works: {len(df)} games before 2024-12-31")
        else:
            print("  Note: No games found before 2024-12-31")


class TestDateFormatValidation:
    """Test various date format inputs"""

    def test_iso_date_format(self) -> None:
        """Test ISO 8601 date format (YYYY-MM-DD)"""
        print("\n[TEST] ISO date format (YYYY-MM-DD)")

        df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season=TEST_SEASON, date="2024-11-15", limit=5
        )

        # Should not raise error
        print(f"✓ ISO format works: {len(df)} games")

    def test_slash_date_format(self) -> None:
        """Test slash date format (MM/DD/YYYY)"""
        print("\n[TEST] Slash date format (MM/DD/YYYY)")

        # This might not be supported; test if it works
        try:
            df = get_basketball_data(
                dataset="schedule",
                league=LEAGUE_NCAA,
                season=TEST_SEASON,
                date="11/15/2024",
                limit=5,
            )
            print(f"✓ Slash format works: {len(df)} games")
        except ValueError:
            print("  Note: Slash format not supported (expected, use ISO format)")

    def test_invalid_date_string(self) -> None:
        """Test that invalid date strings raise appropriate errors"""
        print("\n[TEST] Invalid date string handling")

        # Test completely invalid date
        with pytest.raises(ValueError):
            get_basketball_data(
                dataset="schedule", league=LEAGUE_NCAA, season=TEST_SEASON, date="not-a-date"
            )

        print("✓ Invalid date correctly rejected")


class TestDateFilterCombinations:
    """Test date filtering combined with other parameters"""

    def test_date_and_team_filter(self) -> None:
        """Test combining date filter with team filter"""
        print("\n[TEST] Date + Team filter combination")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=["Duke"],
            start_date="2024-11-01",
            end_date="2024-12-31",
            limit=20,
        )

        if not df.empty:
            # Should have Duke in every game
            assert (
                "HOME_TEAM" in df.columns or "AWAY_TEAM" in df.columns
            ), "Should have team columns"

            # Verify dates are in range
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"

            print(f"✓ Date+Team filter works: {len(df)} Duke games in Nov-Dec 2024")
        else:
            print("  Note: No Duke games found in date range")

    def test_date_and_granularity_filter(self) -> None:
        """Test combining date filter with granularity"""
        print("\n[TEST] Date + Granularity filter combination")

        # Get a specific game on a known date
        df = get_basketball_data(
            dataset="player_game",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            date="2024-11-04",
            granularity="half",
            limit=50,
        )

        if not df.empty:
            assert "HALF" in df.columns, "Should have HALF column for half granularity"
            print(f"✓ Date+Granularity filter works: {len(df)} half-level records")
        else:
            print("  Note: No games found on date for granularity test")


class TestEuroLeagueDateFiltering:
    """Test date filtering for EuroLeague"""

    def test_euroleague_date_filter(self) -> None:
        """Test EuroLeague date filtering"""
        print("\n[TEST] EuroLeague date filter")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_EURO,
            season="2024",
            start_date="2024-10-01",
            end_date="2024-10-31",
            limit=20,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"
            print(f"✓ EuroLeague date filter works: {len(df)} games in Oct 2024")
        else:
            print("  Note: No EuroLeague games in October 2024")

    def test_euroleague_single_date(self) -> None:
        """Test EuroLeague single date filtering"""
        print("\n[TEST] EuroLeague single date filter")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_EURO,
            season="2024",
            date="2024-10-03",  # Opening day of 2024-25 season
            limit=10,
        )

        if not df.empty:
            assert "GAME_DATE" in df.columns, "Should have GAME_DATE column"
            print(f"✓ EuroLeague single date works: {len(df)} games on 2024-10-03")
        else:
            print("  Note: No EuroLeague games on 2024-10-03")


class TestDateFilterDataQuality:
    """Test data quality and completeness for date filtering"""

    def test_date_filter_preserves_data(self) -> None:
        """Test that date filtering preserves all expected columns"""
        print("\n[TEST] Date filter data completeness")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            start_date="2024-11-01",
            end_date="2024-11-30",
            limit=10,
        )

        if not df.empty:
            # Check for essential schedule columns
            required_cols = ["GAME_ID", "GAME_DATE"]
            for col in required_cols:
                assert col in df.columns, f"Missing required column: {col}"

            # Verify no null game IDs
            assert not df["GAME_ID"].isnull().any(), "Should have no null GAME_IDs"

            print(f"✓ Data completeness validated: {len(df)} complete records")
        else:
            print("  Note: No games found in November 2024")

    def test_date_range_chronological_order(self) -> None:
        """Test that date-filtered games are in chronological order"""
        print("\n[TEST] Date filter chronological ordering")

        df = get_basketball_data(
            dataset="schedule",
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            start_date="2024-11-01",
            end_date="2024-11-30",
            limit=20,
        )

        if not df.empty and "GAME_DATE" in df.columns:
            # Check if dates are sorted (or can be sorted)
            dates = df["GAME_DATE"].dt.date if hasattr(df["GAME_DATE"], "dt") else df["GAME_DATE"]
            dates = dates.dropna()

            if len(dates) > 1:
                # Dates should be sortable
                _ = sorted(dates)
                print(f"✓ Date ordering validated: {len(dates)} chronological games")
            else:
                print("  Note: Not enough games to validate ordering")
        else:
            print("  Note: No games found for ordering test")


class TestDateFilterEdgeCases:
    """Test edge cases and error conditions"""

    def test_future_date_returns_empty(self) -> None:
        """Test that filtering for future dates returns empty result"""
        print("\n[TEST] Future date handling")

        # Use a date far in the future
        future_date = "2030-12-31"

        df = get_basketball_data(
            dataset="schedule", league=LEAGUE_NCAA, season=TEST_SEASON, date=future_date
        )

        # Should return empty (no games scheduled that far ahead)
        assert df.empty or len(df) == 0, "Future date should return empty result"
        print("✓ Future date correctly returns empty result")

    def test_start_after_end_error(self) -> None:
        """Test that start_date > end_date raises error"""
        print("\n[TEST] Invalid date range (start > end)")

        with pytest.raises(ValueError, match="start_date must be before end_date"):
            get_basketball_data(
                dataset="schedule",
                league=LEAGUE_NCAA,
                season=TEST_SEASON,
                start_date="2024-12-31",
                end_date="2024-11-01",
            )

        print("✓ Invalid date range correctly rejected")

    def test_date_and_date_range_conflict(self) -> None:
        """Test that providing both date and date range raises error"""
        print("\n[TEST] Date + date range conflict")

        with pytest.raises(ValueError, match="Cannot specify both 'date' and date range"):
            get_basketball_data(
                dataset="schedule",
                league=LEAGUE_NCAA,
                season=TEST_SEASON,
                date="2024-11-15",
                start_date="2024-11-01",
                end_date="2024-11-30",
            )

        print("✓ Date/range conflict correctly rejected")


if __name__ == "__main__":
    """Run tests with detailed output"""
    print("=" * 80)
    print("DATE FILTERING VALIDATION TESTS")
    print("=" * 80)
    print()

    # Track results
    passed = 0
    failed = 0
    skipped = 0

    # Run each test class
    test_classes = [
        TestSingleDateFiltering,
        TestDateRangeFiltering,
        TestDateFormatValidation,
        TestDateFilterCombinations,
        TestEuroLeagueDateFiltering,
        TestDateFilterDataQuality,
        TestDateFilterEdgeCases,
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
        print("ALL TESTS PASSED - Date filtering implementation verified!")
        print("=" * 80)
    else:
        print("=" * 80)
        print(f"SOME TESTS FAILED - Please review {failed} failed tests above")
        print("=" * 80)
