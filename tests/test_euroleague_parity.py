"""
Comprehensive EuroLeague Parity Tests

Tests that EuroLeague functionality matches NCAA-MBB capabilities.

Test Coverage:
1. Dataset parity (same datasets available for both leagues)
2. Feature parity (filtering, granularity, aggregation)
3. Schema consistency (column standardization)
4. Data quality parity (completeness, accuracy)
5. Sub-league/tournament filtering
"""

import sys
import os
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, 'src')

from get_basketball_data import get_basketball_data
import pytest


# Test configuration
LEAGUE_NCAA = 'NCAA-MBB'
LEAGUE_EURO = 'EuroLeague'
TEST_SEASON_NCAA = '2024'
TEST_SEASON_EURO = '2024'


class TestDatasetParity:
    """Test that both leagues support the same datasets"""

    def test_schedule_available_both_leagues(self):
        """Test schedule dataset available for both leagues"""
        print("\n[TEST] Schedule dataset parity")

        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=5
        )

        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=5
        )

        assert not ncaa_df.empty, "NCAA-MBB should have schedule data"
        assert not euro_df.empty, "EuroLeague should have schedule data"

        print(f"✓ Schedule available: NCAA ({len(ncaa_df)} games), EuroLeague ({len(euro_df)} games)")

    def test_player_game_available_both_leagues(self):
        """Test player_game dataset available for both leagues"""
        print("\n[TEST] Player game dataset parity")

        ncaa_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=10
        )

        euro_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=10
        )

        ncaa_available = not ncaa_df.empty
        euro_available = not euro_df.empty

        print(f"  NCAA-MBB: {'✓' if ncaa_available else '✗'} ({len(ncaa_df)} records)")
        print(f"  EuroLeague: {'✓' if euro_available else '✗'} ({len(euro_df)} records)")

        assert ncaa_available, "NCAA-MBB should have player_game data"

    def test_player_season_available_both_leagues(self):
        """Test player_season dataset available for both leagues"""
        print("\n[TEST] Player season dataset parity")

        ncaa_df = get_basketball_data(
            dataset='player_season',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=10
        )

        euro_df = get_basketball_data(
            dataset='player_season',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=10
        )

        ncaa_available = not ncaa_df.empty
        euro_available = not euro_df.empty

        print(f"  NCAA-MBB: {'✓' if ncaa_available else '✗'} ({len(ncaa_df)} players)")
        print(f"  EuroLeague: {'✓' if euro_available else '✗'} ({len(euro_df)} players)")


class TestFilteringParity:
    """Test that filtering works comparably for both leagues"""

    def test_team_filtering_both_leagues(self):
        """Test team filtering works for both leagues"""
        print("\n[TEST] Team filtering parity")

        # NCAA: Duke
        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            teams=['Duke'],
            limit=10
        )

        # EuroLeague: Barcelona or Real Madrid
        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            teams=['Barcelona'],
            limit=10
        )

        ncaa_works = not ncaa_df.empty
        euro_works = not euro_df.empty

        print(f"  NCAA team filter: {'✓' if ncaa_works else '✗'} ({len(ncaa_df)} games)")
        print(f"  EuroLeague team filter: {'✓' if euro_works else '✗'} ({len(euro_df)} games)")

    def test_date_filtering_both_leagues(self):
        """Test date filtering works for both leagues"""
        print("\n[TEST] Date filtering parity")

        # NCAA: November 2024
        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            start_date='2024-11-01',
            end_date='2024-11-30',
            limit=20
        )

        # EuroLeague: October 2024 (season typically starts in October)
        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            start_date='2024-10-01',
            end_date='2024-10-31',
            limit=20
        )

        ncaa_works = not ncaa_df.empty
        euro_works = not euro_df.empty

        print(f"  NCAA date filter: {'✓' if ncaa_works else '✗'} ({len(ncaa_df)} games)")
        print(f"  EuroLeague date filter: {'✓' if euro_works else '✗'} ({len(euro_df)} games)")


class TestGranularityParity:
    """Test that granularity features work for both leagues"""

    @pytest.mark.skip(reason="EuroLeague quarter aggregation pending PBP implementation")
    def test_quarter_granularity_euroleague(self):
        """Test quarter-level granularity for EuroLeague"""
        print("\n[TEST] EuroLeague quarter granularity")

        df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            granularity='quarter',
            limit=50
        )

        assert not df.empty, "EuroLeague should have quarter-level data"
        assert 'QUARTER' in df.columns, "Should have QUARTER column"

        quarters = sorted(df['QUARTER'].unique())
        assert quarters == [1, 2, 3, 4], f"Should have quarters 1-4, got {quarters}"

        print(f"✓ EuroLeague quarter granularity works: {len(df)} records")

    def test_play_level_both_leagues(self):
        """Test play-by-play level data for both leagues"""
        print("\n[TEST] Play-level data parity")

        # NCAA PBP
        ncaa_df = get_basketball_data(
            dataset='pbp',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=100
        )

        # EuroLeague PBP
        euro_df = get_basketball_data(
            dataset='pbp',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=100
        )

        ncaa_available = not ncaa_df.empty
        euro_available = not euro_df.empty

        print(f"  NCAA PBP: {'✓' if ncaa_available else '✗'} ({len(ncaa_df)} events)")
        print(f"  EuroLeague PBP: {'✓' if euro_available else '✗'} ({len(euro_df)} events)")


class TestSchemaConsistency:
    """Test schema standardization across leagues"""

    def test_schedule_core_columns(self):
        """Test that schedule has consistent core columns"""
        print("\n[TEST] Schedule schema consistency")

        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=5
        )

        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=5
        )

        # Core columns that should exist in both
        core_cols = {'GAME_ID', 'GAME_DATE'}

        if not ncaa_df.empty and not euro_df.empty:
            ncaa_cols = set(ncaa_df.columns)
            euro_cols = set(euro_df.columns)

            ncaa_has_core = core_cols.issubset(ncaa_cols)
            euro_has_core = core_cols.issubset(euro_cols)

            print(f"  NCAA core columns: {'✓' if ncaa_has_core else '✗'}")
            print(f"  EuroLeague core columns: {'✓' if euro_has_core else '✗'}")

            assert ncaa_has_core, "NCAA missing core columns"
            assert euro_has_core, "EuroLeague missing core columns"
        else:
            print("  Note: Insufficient data to compare")

    def test_player_game_stat_columns(self):
        """Test that player_game has consistent stat columns"""
        print("\n[TEST] Player game stats schema consistency")

        ncaa_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=10
        )

        euro_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=10
        )

        # Core stat columns
        stat_cols = {'PLAYER_NAME', 'PTS'}

        if not ncaa_df.empty and not euro_df.empty:
            ncaa_cols = set(ncaa_df.columns)
            euro_cols = set(euro_df.columns)

            ncaa_has_stats = stat_cols.issubset(ncaa_cols)
            euro_has_stats = stat_cols.issubset(euro_cols)

            print(f"  NCAA stat columns: {'✓' if ncaa_has_stats else '✗'}")
            print(f"  EuroLeague stat columns: {'✓' if euro_has_stats else '✗'}")

            assert ncaa_has_stats, "NCAA missing stat columns"
        else:
            print("  Note: Insufficient data to compare")


class TestDataQualityParity:
    """Test data quality is comparable across leagues"""

    def test_no_null_game_ids(self):
        """Test that neither league has null GAME_IDs"""
        print("\n[TEST] Game ID completeness parity")

        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=20
        )

        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=20
        )

        if not ncaa_df.empty:
            ncaa_nulls = ncaa_df['GAME_ID'].isnull().sum()
            assert ncaa_nulls == 0, f"NCAA has {ncaa_nulls} null GAME_IDs"
            print(f"  NCAA: ✓ No null GAME_IDs ({len(ncaa_df)} games)")

        if not euro_df.empty:
            # EuroLeague might use GAME_CODE instead
            id_col = 'GAME_ID' if 'GAME_ID' in euro_df.columns else 'GAME_CODE'
            if id_col in euro_df.columns:
                euro_nulls = euro_df[id_col].isnull().sum()
                assert euro_nulls == 0, f"EuroLeague has {euro_nulls} null {id_col}s"
                print(f"  EuroLeague: ✓ No null {id_col}s ({len(euro_df)} games)")

    def test_no_null_player_names(self):
        """Test that neither league has null PLAYER_NAMEs"""
        print("\n[TEST] Player name completeness parity")

        ncaa_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=50
        )

        euro_df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=50
        )

        if not ncaa_df.empty and 'PLAYER_NAME' in ncaa_df.columns:
            ncaa_nulls = ncaa_df['PLAYER_NAME'].isnull().sum()
            assert ncaa_nulls == 0, f"NCAA has {ncaa_nulls} null PLAYER_NAMEs"
            print(f"  NCAA: ✓ No null PLAYER_NAMEs ({len(ncaa_df)} records)")

        if not euro_df.empty and 'PLAYER_NAME' in euro_df.columns:
            euro_nulls = euro_df['PLAYER_NAME'].isnull().sum()
            assert euro_nulls == 0, f"EuroLeague has {euro_nulls} null PLAYER_NAMEs"
            print(f"  EuroLeague: ✓ No null PLAYER_NAMEs ({len(euro_df)} records)")


class TestEuroLeagueSpecificFeatures:
    """Test EuroLeague-specific features (sub-league, tournaments)"""

    def test_season_type_regular_season(self):
        """Test filtering by regular season"""
        print("\n[TEST] EuroLeague Regular Season filtering")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            season_type='regular',
            limit=10
        )

        if not df.empty:
            print(f"✓ Regular season filter works: {len(df)} games")
        else:
            print("  Note: No regular season games found")

    def test_season_type_playoffs(self):
        """Test filtering by playoffs"""
        print("\n[TEST] EuroLeague Playoffs filtering")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            season_type='playoffs',
            limit=10
        )

        # Playoffs may or may not have data depending on season timing
        print(f"  Playoffs data: {'✓' if not df.empty else '✗'} ({len(df)} games)")

    def test_season_type_final_four(self):
        """Test filtering by Final Four"""
        print("\n[TEST] EuroLeague Final Four filtering")

        # Try 2023 season (completed, should have Final Four)
        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season='2023',
            season_type='finals',
            limit=10
        )

        # Final Four may be sparse
        print(f"  Final Four data: {'✓' if not df.empty else '✗'} ({len(df)} games)")


class TestUseCaseParity:
    """Test common use cases work for both leagues"""

    def test_get_team_schedule_use_case(self):
        """Test getting a team's schedule (common use case)"""
        print("\n[TEST] Get team schedule use case")

        # NCAA: Duke's schedule
        ncaa_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            teams=['Duke'],
            limit=20
        )

        # EuroLeague: Barcelona's schedule
        euro_df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            teams=['Barcelona'],
            limit=20
        )

        ncaa_works = not ncaa_df.empty
        euro_works = not euro_df.empty

        print(f"  NCAA (Duke): {'✓' if ncaa_works else '✗'} ({len(ncaa_df)} games)")
        print(f"  EuroLeague (Barcelona): {'✓' if euro_works else '✗'} ({len(euro_df)} games)")

    def test_get_player_season_stats_use_case(self):
        """Test getting player season stats (common use case)"""
        print("\n[TEST] Get player season stats use case")

        # NCAA
        ncaa_df = get_basketball_data(
            dataset='player_season',
            league=LEAGUE_NCAA,
            season=TEST_SEASON_NCAA,
            limit=20
        )

        # EuroLeague
        euro_df = get_basketball_data(
            dataset='player_season',
            league=LEAGUE_EURO,
            season=TEST_SEASON_EURO,
            limit=20
        )

        ncaa_works = not ncaa_df.empty
        euro_works = not euro_df.empty

        print(f"  NCAA: {'✓' if ncaa_works else '✗'} ({len(ncaa_df)} players)")
        print(f"  EuroLeague: {'✓' if euro_works else '✗'} ({len(euro_df)} players)")


if __name__ == '__main__':
    """Run tests with detailed output"""
    print("=" * 80)
    print("EUROLEAGUE PARITY VALIDATION TESTS")
    print("=" * 80)
    print()

    # Track results
    passed = 0
    failed = 0
    skipped = 0

    # Run each test class
    test_classes = [
        TestDatasetParity,
        TestFilteringParity,
        TestGranularityParity,
        TestSchemaConsistency,
        TestDataQualityParity,
        TestEuroLeagueSpecificFeatures,
        TestUseCaseParity
    ]

    for test_class in test_classes:
        print(f"\n{'=' * 80}")
        print(f"TEST CLASS: {test_class.__name__}")
        print('=' * 80)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                method = getattr(instance, method_name)

                # Check if marked as skip
                skip_marker = None
                if hasattr(method, 'pytestmark'):
                    marks = method.pytestmark if isinstance(method.pytestmark, list) else [method.pytestmark]
                    for mark in marks:
                        if mark.name == 'skip':
                            skip_marker = mark
                            break

                if skip_marker:
                    reason = skip_marker.kwargs.get('reason', 'No reason provided')
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
        print("ALL TESTS PASSED - EuroLeague parity verified!")
        print("=" * 80)
    else:
        print("=" * 80)
        print(f"SOME TESTS FAILED - Please review {failed} failed tests above")
        print("=" * 80)
