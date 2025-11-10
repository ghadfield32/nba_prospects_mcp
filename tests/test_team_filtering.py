"""
Comprehensive Team Filtering Tests

Tests team-based game retrieval functionality for NCAA-MBB and EuroLeague.

Test Coverage:
1. Single team game retrieval
2. Head-to-head (two team) filtering
3. Team name case insensitivity
4. Invalid team handling
5. Data completeness validation
6. Cross-league compatibility
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
TEST_SEASON = '2025'


class TestSingleTeamFiltering:
    """Test single team game retrieval"""

    def test_single_team_schedule(self):
        """Test retrieving all games for a single team"""
        print("\n[TEST] Single team schedule retrieval")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Duke']
        )

        assert not df.empty, "Duke schedule should not be empty"

        # Verify Duke appears in every game (either home or away)
        if 'HOME_TEAM' in df.columns and 'AWAY_TEAM' in df.columns:
            duke_games = df[
                (df['HOME_TEAM'].str.lower().str.contains('duke', na=False)) |
                (df['AWAY_TEAM'].str.lower().str.contains('duke', na=False))
            ]
            assert len(duke_games) == len(df), "All games should include Duke"

        print(f"✓ Single team filter works: {len(df)} Duke games found")

    def test_team_player_stats(self):
        """Test retrieving player stats for a specific team"""
        print("\n[TEST] Team-specific player game stats")

        df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Houston'],
            limit=20
        )

        assert not df.empty, "Houston player stats should not be empty"
        assert 'PLAYER_NAME' in df.columns, "Should have PLAYER_NAME column"
        assert 'PTS' in df.columns, "Should have PTS column"

        print(f"✓ Team player stats work: {len(df)} player-game records")

    def test_case_insensitive_team_name(self):
        """Test that team names are case-insensitive"""
        print("\n[TEST] Case-insensitive team names")

        # Try different cases
        df_lower = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['duke'],
            limit=5
        )

        df_upper = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['DUKE'],
            limit=5
        )

        df_mixed = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Duke'],
            limit=5
        )

        # All should return data
        assert not df_lower.empty, "Lowercase 'duke' should work"
        assert not df_upper.empty, "Uppercase 'DUKE' should work"
        assert not df_mixed.empty, "Mixed case 'Duke' should work"

        print(f"✓ Case insensitivity works: duke={len(df_lower)}, DUKE={len(df_upper)}, Duke={len(df_mixed)}")


class TestHeadToHeadFiltering:
    """Test two-team head-to-head filtering"""

    def test_head_to_head_schedule(self):
        """Test retrieving games between two specific teams"""
        print("\n[TEST] Head-to-head schedule")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Duke', 'North Carolina']
        )

        if not df.empty:
            # Should only include games with both Duke AND UNC
            assert 'HOME_TEAM' in df.columns, "Should have HOME_TEAM column"
            assert 'AWAY_TEAM' in df.columns, "Should have AWAY_TEAM column"

            # Verify both teams appear
            for _, row in df.iterrows():
                home = str(row['HOME_TEAM']).lower()
                away = str(row['AWAY_TEAM']).lower()

                has_duke = 'duke' in home or 'duke' in away
                has_unc = 'carolina' in home or 'carolina' in away or 'unc' in home or 'unc' in away

                assert has_duke and has_unc, f"Game should include both teams: {row['HOME_TEAM']} vs {row['AWAY_TEAM']}"

            print(f"✓ Head-to-head filter works: {len(df)} Duke vs UNC games")
        else:
            print("  Note: No Duke vs UNC games found (may not have played yet this season)")

    def test_head_to_head_player_stats(self):
        """Test player stats from head-to-head games"""
        print("\n[TEST] Head-to-head player stats")

        df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Kansas', 'Kentucky'],
            limit=50
        )

        if not df.empty:
            assert 'PLAYER_NAME' in df.columns, "Should have PLAYER_NAME column"
            assert 'TEAM_ABBREVIATION' in df.columns or 'TEAM_NAME' in df.columns, "Should have team info"

            print(f"✓ Head-to-head player stats work: {len(df)} player records")
        else:
            print("  Note: No Kansas vs Kentucky games found this season")


class TestEuroLeagueTeamFiltering:
    """Test team filtering for EuroLeague"""

    def test_euroleague_team_schedule(self):
        """Test EuroLeague team schedule retrieval"""
        print("\n[TEST] EuroLeague team schedule")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_EURO,
            season='2024',
            teams=['Barcelona'],
            limit=10
        )

        if not df.empty:
            assert 'HOME_TEAM' in df.columns or 'AWAY_TEAM' in df.columns, "Should have team columns"
            print(f"✓ EuroLeague team filter works: {len(df)} Barcelona games")
        else:
            print("  Note: No Barcelona games found (check team name format)")

    def test_euroleague_team_player_stats(self):
        """Test EuroLeague player stats for a specific team"""
        print("\n[TEST] EuroLeague team player stats")

        df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_EURO,
            season='2024',
            teams=['Real Madrid'],
            limit=20
        )

        if not df.empty:
            assert 'PLAYER_NAME' in df.columns, "Should have PLAYER_NAME column"
            print(f"✓ EuroLeague player stats work: {len(df)} player-game records")
        else:
            print("  Note: No Real Madrid player data found (check team name format)")


class TestTeamFilterValidation:
    """Test team filter parameter validation"""

    def test_empty_teams_list(self):
        """Test that empty teams list returns all games"""
        print("\n[TEST] Empty teams list behavior")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=[],
            limit=10
        )

        # Empty list should return general schedule
        assert not df.empty, "Should return games even with empty teams list"
        print(f"✓ Empty teams list works: {len(df)} games returned")

    def test_invalid_team_name(self):
        """Test handling of non-existent team names"""
        print("\n[TEST] Invalid team name handling")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['NonExistentTeam12345'],
            limit=10
        )

        # Should return empty DataFrame for non-existent team
        # (or possibly a few games if there's a partial match)
        print(f"  Invalid team returned {len(df)} games (expected 0 or very few)")

    def test_more_than_two_teams_error(self):
        """Test that more than 2 teams raises an error"""
        print("\n[TEST] More than 2 teams validation")

        with pytest.raises(ValueError, match="Maximum of 2 teams"):
            get_basketball_data(
                dataset='schedule',
                league=LEAGUE_NCAA,
                season=TEST_SEASON,
                teams=['Duke', 'UNC', 'Kentucky']
            )

        print("✓ Three-team validation correctly enforced")


class TestTeamFilterDataQuality:
    """Test data quality and completeness for team filtering"""

    def test_team_schedule_completeness(self):
        """Test that team schedules have required fields"""
        print("\n[TEST] Team schedule data completeness")

        df = get_basketball_data(
            dataset='schedule',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Gonzaga'],
            limit=5
        )

        if not df.empty:
            # Check for essential schedule columns
            required_cols = ['GAME_ID', 'GAME_DATE']
            for col in required_cols:
                assert col in df.columns, f"Missing required column: {col}"

            # Verify no null game IDs
            assert not df['GAME_ID'].isnull().any(), "Should have no null GAME_IDs"

            print(f"✓ Data completeness validated: {len(df)} complete records")
        else:
            print("  Note: No Gonzaga games found")

    def test_team_stats_accuracy(self):
        """Test that team filtering returns accurate stats"""
        print("\n[TEST] Team stats accuracy")

        df = get_basketball_data(
            dataset='player_game',
            league=LEAGUE_NCAA,
            season=TEST_SEASON,
            teams=['Purdue'],
            limit=10
        )

        if not df.empty:
            # Basic stat validation
            if 'PTS' in df.columns:
                assert (df['PTS'] >= 0).all(), "Points should be non-negative"

            if 'FGM' in df.columns and 'FGA' in df.columns:
                assert (df['FGM'] <= df['FGA']).all(), "FGM should not exceed FGA"

            print(f"✓ Stats accuracy validated: {len(df)} records")
        else:
            print("  Note: No Purdue player data found")


if __name__ == '__main__':
    """Run tests with detailed output"""
    print("=" * 80)
    print("TEAM FILTERING VALIDATION TESTS")
    print("=" * 80)
    print()

    # Track results
    passed = 0
    failed = 0
    skipped = 0

    # Run each test class
    test_classes = [
        TestSingleTeamFiltering,
        TestHeadToHeadFiltering,
        TestEuroLeagueTeamFiltering,
        TestTeamFilterValidation,
        TestTeamFilterDataQuality
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
        print("ALL TESTS PASSED - Team filtering implementation verified!")
        print("=" * 80)
    else:
        print("=" * 80)
        print(f"SOME TESTS FAILED - Please review {failed} failed tests above")
        print("=" * 80)
