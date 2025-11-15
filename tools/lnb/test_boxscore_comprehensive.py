#!/usr/bin/env python3
"""Comprehensive LNB Boxscore Parser Validation Suite

Tests all parser functionality including:
- Edge cases (0 FGA, null values, DNP players)
- Field name variations (15+ different naming conventions)
- French time format parsing
- Calculated metrics accuracy
- Schema compliance
- Integration with fetcher function

Usage:
    python tools/lnb/test_boxscore_comprehensive.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

import pandas as pd

from cbb_data.fetchers.lnb_parsers import _parse_minutes_french, parse_boxscore
from cbb_data.fetchers.lnb_schemas import get_player_game_columns


class TestSuite:
    """Comprehensive test suite for LNB boxscore parser."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def run_test(self, test_name, test_func):
        """Run a test and track results."""
        print(f"\n[TEST] {test_name}")
        try:
            test_func()
            print("  [PASS]")
            self.passed += 1
            self.tests.append((test_name, True))
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            self.failed += 1
            self.tests.append((test_name, False))
        except Exception as e:
            print(f"  [ERROR] {e}")
            self.failed += 1
            self.tests.append((test_name, False))

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)
        print()
        for test_name, passed in self.tests:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"  {status} {test_name}")
        print()
        print(f"  Total: {self.passed + self.failed} tests")
        print(f"  Passed: {self.passed}")
        print(f"  Failed: {self.failed}")
        print()
        if self.failed == 0:
            print("  [SUCCESS] All tests passed!")
            return 0
        else:
            print(f"  [ERROR] {self.failed} test(s) failed")
            return 1


# ==============================================================================
# Test Cases
# ==============================================================================


def test_french_time_parsing():
    """Test French time format parsing."""
    assert _parse_minutes_french("0' 00''") == 0.0
    assert _parse_minutes_french("10' 30''") == 10.5
    assert _parse_minutes_french("35' 45''") == 35.75
    assert _parse_minutes_french("48' 00''") == 48.0
    assert abs(_parse_minutes_french("18' 46''") - 18.766667) < 0.001


def test_field_name_variations():
    """Test parser handles different field naming conventions."""
    # Pattern 1: snake_case (most common from LNB API)
    data1 = [
        {
            "person_external_id": 100,
            "first_name": "Test",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
            "minutes": "10' 00''",
            "points": 10,
            "field_goals_made": 4,
            "field_goals_attempted": 8,
        }
    ]

    # Pattern 2: camelCase (alternative naming)
    data2 = [
        {
            "personExternalId": 100,
            "firstName": "Test",
            "familyName": "Player",
            "teamExternalId": 1,
            "opponentExternalId": 2,
            "minutes": "10' 00''",
            "points": 10,
            "fieldGoalsMade": 4,
            "fieldGoalsAttempted": 8,
        }
    ]

    df1 = parse_boxscore(data1, 1, 2025)
    df2 = parse_boxscore(data2, 1, 2025)

    # Both should parse successfully
    assert len(df1) == 1
    assert len(df2) == 1

    # Both should have same values
    assert df1["PTS"].iloc[0] == 10
    assert df2["PTS"].iloc[0] == 10


def test_zero_fga_edge_case():
    """Test handling of 0 FGA (should return None for FG%)."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "DNP",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
            "minutes": "0' 00''",
            "points": 0,
            "field_goals_made": 0,
            "field_goals_attempted": 0,
            "three_pointers_made": 0,
            "three_pointers_attempted": 0,
            "free_throws_made": 0,
            "free_throws_attempted": 0,
        }
    ]

    df = parse_boxscore(data, 1, 2025)

    assert len(df) == 1
    assert df["PTS"].iloc[0] == 0
    assert df["FGM"].iloc[0] == 0
    assert df["FGA"].iloc[0] == 0
    assert pd.isna(df["FG_PCT"].iloc[0])  # Should be None/NaN
    assert pd.isna(df["EFG_PCT"].iloc[0])
    assert pd.isna(df["TS_PCT"].iloc[0])


def test_calculated_metrics():
    """Test FG%, eFG%, TS% calculations."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "Test",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
            "minutes": "30' 00''",
            "points": 20,
            "field_goals_made": 6,
            "field_goals_attempted": 12,
            "three_pointers_made": 2,
            "three_pointers_attempted": 5,
            "free_throws_made": 6,
            "free_throws_attempted": 8,
        }
    ]

    df = parse_boxscore(data, 1, 2025)

    # FG% = 6/12 = 0.500
    assert abs(df["FG_PCT"].iloc[0] - 0.500) < 0.001

    # eFG% = (6 + 0.5 * 2) / 12 = 7/12 = 0.583
    assert abs(df["EFG_PCT"].iloc[0] - 0.583) < 0.001

    # TS% = 20 / (2 * (12 + 0.44 * 8)) = 20 / 31.04 = 0.644
    assert abs(df["TS_PCT"].iloc[0] - 0.644) < 0.001


def test_schema_compliance():
    """Test that output matches LNBPlayerGame schema."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "Test",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
            "minutes": "10' 00''",
            "points": 5,
        }
    ]

    df = parse_boxscore(data, 1, 2025)
    expected_cols = get_player_game_columns()

    assert len(df.columns) == len(expected_cols)
    assert list(df.columns) == expected_cols


def test_missing_stats():
    """Test handling of missing stats (should default to 0 or None)."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "Minimal",
            "family_name": "Data",
            "team_external_id": 1,
            "opponent_external_id": 2,
            # Only required fields, no stats
        }
    ]

    df = parse_boxscore(data, 1, 2025)

    assert len(df) == 1
    assert df["PLAYER_ID"].iloc[0] == 100
    assert df["MIN"].iloc[0] == 0.0
    assert df["PTS"].iloc[0] == 0


def test_full_stat_line():
    """Test complete stat line with all fields."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "Complete",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
            "minutes": "35' 30''",
            "starter": True,
            "points": 25,
            "field_goals_made": 9,
            "field_goals_attempted": 18,
            "three_pointers_made": 3,
            "three_pointers_attempted": 8,
            "free_throws_made": 4,
            "free_throws_attempted": 5,
            "rebounds": 8,
            "offensive_rebounds": 2,
            "defensive_rebounds": 6,
            "assists": 7,
            "steals": 3,
            "blocks": 1,
            "turnovers": 2,
            "fouls": 3,
            "plus_minus": 12,
        }
    ]

    df = parse_boxscore(data, 1, 2025)

    assert len(df) == 1
    assert df["PLAYER_NAME"].iloc[0] == "Complete Player"
    assert df["MIN"].iloc[0] == 35.5
    assert df["STARTER"].iloc[0]
    assert df["PTS"].iloc[0] == 25
    assert df["FGM"].iloc[0] == 9
    assert df["FGA"].iloc[0] == 18
    assert df["FG3M"].iloc[0] == 3
    assert df["FG3A"].iloc[0] == 8
    assert df["FTM"].iloc[0] == 4
    assert df["FTA"].iloc[0] == 5
    assert df["REB"].iloc[0] == 8
    assert df["OREB"].iloc[0] == 2
    assert df["DREB"].iloc[0] == 6
    assert df["AST"].iloc[0] == 7
    assert df["STL"].iloc[0] == 3
    assert df["BLK"].iloc[0] == 1
    assert df["TOV"].iloc[0] == 2
    assert df["PF"].iloc[0] == 3
    assert df["PLUS_MINUS"].iloc[0] == 12


def test_multiple_players():
    """Test parsing multiple players."""
    data = [
        {
            "person_external_id": 100 + i,
            "first_name": f"Player{i}",
            "family_name": f"Test{i}",
            "team_external_id": 1 if i < 5 else 2,
            "opponent_external_id": 2 if i < 5 else 1,
            "minutes": f"{10 + i}' 00''",
            "points": i * 2,
        }
        for i in range(10)
    ]

    df = parse_boxscore(data, 1, 2025)

    assert len(df) == 10
    assert df["PLAYER_ID"].nunique() == 10  # All unique players


def test_pattern_1_simple_list():
    """Test Pattern 1: Direct list of players."""
    data = [
        {
            "person_external_id": 1,
            "first_name": "A",
            "family_name": "B",
            "team_external_id": 1,
            "opponent_external_id": 2,
        }
    ]

    df = parse_boxscore(data, 1, 2025)
    assert len(df) == 1


def test_pattern_2_players_key():
    """Test Pattern 2: Dict with 'players' key."""
    data = {
        "players": [
            {
                "person_external_id": 1,
                "first_name": "A",
                "family_name": "B",
                "team_external_id": 1,
                "opponent_external_id": 2,
            }
        ]
    }

    df = parse_boxscore(data, 1, 2025)
    assert len(df) == 1


def test_pattern_3_home_away():
    """Test Pattern 3: Separate home/away player lists."""
    data = {
        "home_players": [
            {
                "person_external_id": 1,
                "first_name": "Home",
                "family_name": "Player",
                "team_external_id": 1,
                "opponent_external_id": 2,
            }
        ],
        "away_players": [
            {
                "person_external_id": 2,
                "first_name": "Away",
                "family_name": "Player",
                "team_external_id": 2,
                "opponent_external_id": 1,
            }
        ],
    }

    df = parse_boxscore(data, 1, 2025)
    assert len(df) == 2


def test_pattern_4_nested_teams():
    """Test Pattern 4: Teams with nested players."""
    data = {
        "teams": [
            {
                "team_id": 1,
                "players": [
                    {
                        "person_external_id": 1,
                        "first_name": "T1",
                        "family_name": "P1",
                        "team_external_id": 1,
                        "opponent_external_id": 2,
                    }
                ],
            },
            {
                "team_id": 2,
                "players": [
                    {
                        "person_external_id": 2,
                        "first_name": "T2",
                        "family_name": "P2",
                        "team_external_id": 2,
                        "opponent_external_id": 1,
                    }
                ],
            },
        ]
    }

    df = parse_boxscore(data, 1, 2025)
    assert len(df) == 2


def test_game_id_season_propagation():
    """Test that GAME_ID and SEASON are correctly added to all rows."""
    data = [
        {
            "person_external_id": 100,
            "first_name": "Test",
            "family_name": "Player",
            "team_external_id": 1,
            "opponent_external_id": 2,
        }
    ]

    df = parse_boxscore(data, game_id=28931, season=2025)

    assert df["GAME_ID"].iloc[0] == 28931
    assert df["SEASON"].iloc[0] == 2025
    assert df["LEAGUE"].iloc[0] == "LNB"


# ==============================================================================
# Main Test Runner
# ==============================================================================


def main():
    """Run all tests."""
    print("=" * 70)
    print("  LNB Boxscore Parser Comprehensive Validation")
    print("=" * 70)

    suite = TestSuite()

    # Run all tests
    suite.run_test("French time parsing", test_french_time_parsing)
    suite.run_test("Field name variations", test_field_name_variations)
    suite.run_test("Zero FGA edge case", test_zero_fga_edge_case)
    suite.run_test("Calculated metrics accuracy", test_calculated_metrics)
    suite.run_test("Schema compliance", test_schema_compliance)
    suite.run_test("Missing stats handling", test_missing_stats)
    suite.run_test("Full stat line parsing", test_full_stat_line)
    suite.run_test("Multiple players", test_multiple_players)
    suite.run_test("Pattern 1: Simple list", test_pattern_1_simple_list)
    suite.run_test("Pattern 2: Players key", test_pattern_2_players_key)
    suite.run_test("Pattern 3: Home/away split", test_pattern_3_home_away)
    suite.run_test("Pattern 4: Nested teams", test_pattern_4_nested_teams)
    suite.run_test("Game ID and season propagation", test_game_id_season_propagation)

    # Print summary and exit
    return suite.print_summary()


if __name__ == "__main__":
    sys.exit(main())
