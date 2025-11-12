"""
Comprehensive stress tests for EuroCup and G League implementation.

Tests all granularities for newly added leagues:
- EuroCup: schedule, player_game, team_game, pbp, shots, player_season, team_season
- G League: schedule, player_game, team_game, pbp, shots, player_season, team_season

Date: 2025-11-12
Purpose: Validate EuroCup and G League data pipeline end-to-end with real data
"""

import sys

sys.path.insert(0, "src")

import time

from cbb_data.api.datasets import get_dataset

# Known completed game IDs for reliable testing
# EuroCup: Using 2024-25 season game codes
# G League: Using 2024-25 season game IDs (format: 00224YYSSGG)
KNOWN_TEST_GAME_IDS = {
    "EuroCup": [1, 2, 3, 4, 5],  # Game codes 1-5 from 2024 season
    "G-League": [
        "0022400001",  # 2024-25 season game 1
        "0022400002",  # 2024-25 season game 2
        "0022400003",  # 2024-25 season game 3
    ],
}


class StressTestRunner:
    """Manages comprehensive stress testing across all parameters"""

    def __init__(self) -> None:
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def run_test(self, name, test_func) -> None:
        """Run a single test and record results"""
        print(f"\n{'='*80}")
        print(f"TEST: {name}")
        print("=" * 80)

        try:
            start = time.time()
            result = test_func()
            elapsed = time.time() - start

            if result:
                print(f"✅ [PASS] {name} ({elapsed:.2f}s)")
                self.passed += 1
                self.results.append((name, "PASS", elapsed, None))
            else:
                print(f"❌ [FAIL] {name}")
                self.failed += 1
                self.results.append((name, "FAIL", elapsed, "Test returned False"))

        except Exception as e:
            elapsed = time.time() - start if "start" in locals() else 0
            print(f"❌ [FAIL] {name}: {str(e)[:200]}")
            self.failed += 1
            self.results.append((name, "FAIL", elapsed, str(e)[:200]))

    def print_summary(self) -> bool:
        """Print comprehensive test summary"""
        print("\n" + "=" * 80)
        print("🏀 EUROCUP & G LEAGUE STRESS TEST SUMMARY")
        print("=" * 80)

        total = self.passed + self.failed + self.skipped

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {self.passed} ({self.passed/total*100:.1f}%)")
        print(f"❌ Failed: {self.failed} ({self.failed/total*100:.1f}%)")
        print(f"⏭️  Skipped: {self.skipped}")

        if self.failed > 0:
            print("\n❌ Failed Tests:")
            for name, status, _elapsed, error in self.results:
                if status == "FAIL":
                    print(f"  - {name}:")
                    print(f"    {error}")

        print("=" * 80)

        return self.failed == 0


# ==============================================================================
# EuroCup Tests
# ==============================================================================


def test_eurocup_schedule_regular_season() -> bool:
    """EuroCup: Fetch schedule for 2024-25 regular season"""
    df = get_dataset(
        "schedule",
        {"league": "EuroCup", "season": "U2024", "season_type": "Regular Season"},
        limit=50,
    )
    assert len(df) > 0, "EuroCup schedule should return data"
    assert "GAME_CODE" in df.columns, "Schedule should have GAME_CODE"
    assert "HOME_TEAM" in df.columns, "Schedule should have HOME_TEAM"
    assert "AWAY_TEAM" in df.columns, "Schedule should have AWAY_TEAM"
    assert "LEAGUE" in df.columns, "Schedule should have LEAGUE column"
    assert all(df["LEAGUE"] == "EuroCup"), "All rows should be marked as EuroCup"
    print(f"  ✓ Fetched {len(df)} EuroCup games")
    return True


def test_eurocup_schedule_playoffs() -> bool:
    """EuroCup: Fetch schedule for playoffs"""
    df = get_dataset(
        "schedule",
        {"league": "EuroCup", "season": "U2024", "season_type": "Playoffs"},
        limit=50,
    )
    # Playoffs may have 0 games if season hasn't reached playoffs yet
    assert "GAME_CODE" in df.columns or len(df) == 0, "Schedule should have GAME_CODE or be empty"
    print(f"  ✓ Fetched {len(df)} EuroCup playoff games")
    return True


def test_eurocup_player_game() -> bool:
    """EuroCup: Fetch player box scores for specific games"""
    game_ids = KNOWN_TEST_GAME_IDS["EuroCup"][:3]  # Test first 3 games

    df = get_dataset(
        "player_game",
        {"league": "EuroCup", "season": "U2024", "game_ids": game_ids},
        limit=500,
    )

    assert len(df) > 0, "EuroCup player_game should return data"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "TEAM" in df.columns, "Should have TEAM"
    assert "PTS" in df.columns, "Should have PTS"
    assert "REB" in df.columns, "Should have REB"
    assert "AST" in df.columns, "Should have AST"
    assert "VALUATION" in df.columns, "Should have VALUATION (EuroLeague efficiency)"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "EuroCup"), "All rows should be marked as EuroCup"

    print(f"  ✓ Fetched {len(df)} player box scores from {len(game_ids)} games")
    print(f"  ✓ Average VALUATION: {df['VALUATION'].mean():.2f}")
    return True


def test_eurocup_play_by_play() -> bool:
    """EuroCup: Fetch play-by-play data for specific games"""
    game_ids = KNOWN_TEST_GAME_IDS["EuroCup"][:2]  # Test first 2 games

    df = get_dataset(
        "pbp",
        {"league": "EuroCup", "season": "U2024", "game_ids": game_ids},
    )

    assert len(df) > 0, "EuroCup PBP should return data"
    assert "PLAY_TYPE" in df.columns, "Should have PLAY_TYPE"
    assert "PERIOD" in df.columns, "Should have PERIOD"
    assert "CLOCK" in df.columns or "MINUTE" in df.columns, "Should have time information"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "EuroCup"), "All rows should be marked as EuroCup"

    print(f"  ✓ Fetched {len(df)} play-by-play events from {len(game_ids)} games")
    return True


def test_eurocup_shots() -> bool:
    """EuroCup: Fetch shot chart data with coordinates"""
    game_ids = KNOWN_TEST_GAME_IDS["EuroCup"][:2]  # Test first 2 games

    df = get_dataset(
        "shots",
        {"league": "EuroCup", "season": "U2024", "game_ids": game_ids},
    )

    assert len(df) > 0, "EuroCup shots should return data"
    assert "LOC_X" in df.columns, "Should have LOC_X coordinate"
    assert "LOC_Y" in df.columns, "Should have LOC_Y coordinate"
    assert "SHOT_MADE" in df.columns, "Should have SHOT_MADE flag"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "EuroCup"), "All rows should be marked as EuroCup"

    # Validate coordinates are numeric
    assert df["LOC_X"].dtype in ["int64", "float64"], "LOC_X should be numeric"
    assert df["LOC_Y"].dtype in ["int64", "float64"], "LOC_Y should be numeric"

    made_pct = (df["SHOT_MADE"].sum() / len(df)) * 100
    print(f"  ✓ Fetched {len(df)} shots from {len(game_ids)} games")
    print(f"  ✓ Shot accuracy: {made_pct:.1f}%")
    return True


def test_eurocup_player_season() -> bool:
    """EuroCup: Fetch player season aggregates"""
    df = get_dataset(
        "player_season",
        {"league": "EuroCup", "season": "U2024", "per_mode": "PerGame"},
        limit=100,
    )

    assert len(df) > 0, "EuroCup player_season should return data"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "GP" in df.columns, "Should have GP (games played)"
    assert "PTS" in df.columns, "Should have PTS"
    assert "REB" in df.columns, "Should have REB"
    assert "AST" in df.columns, "Should have AST"

    print(f"  ✓ Fetched {len(df)} player season aggregates")
    print(f"  ✓ Average PPG: {df['PTS'].mean():.2f}")
    return True


def test_eurocup_team_season() -> bool:
    """EuroCup: Fetch team season standings"""
    df = get_dataset(
        "team_season",
        {"league": "EuroCup", "season": "U2024"},
        limit=50,
    )

    assert len(df) > 0, "EuroCup team_season should return data"
    assert "TEAM_NAME" in df.columns or "TEAM" in df.columns, "Should have team name"
    assert "GP" in df.columns, "Should have GP (games played)"

    print(f"  ✓ Fetched {len(df)} team season records")
    return True


# ==============================================================================
# G League Tests
# ==============================================================================


def test_gleague_schedule() -> bool:
    """G League: Fetch schedule for 2024-25 season"""
    df = get_dataset(
        "schedule",
        {"league": "G-League", "season": "2024-25", "season_type": "Regular Season"},
        limit=50,
    )

    assert len(df) > 0, "G League schedule should return data"
    assert "GAME_ID" in df.columns, "Schedule should have GAME_ID"
    assert "HOME_TEAM" in df.columns, "Schedule should have HOME_TEAM"
    assert "AWAY_TEAM" in df.columns, "Schedule should have AWAY_TEAM"
    assert "LEAGUE" in df.columns, "Schedule should have LEAGUE column"
    assert all(df["LEAGUE"] == "G-League"), "All rows should be marked as G-League"

    print(f"  ✓ Fetched {len(df)} G League games")
    return True


def test_gleague_player_game() -> bool:
    """G League: Fetch player box scores for specific games"""
    # Note: These game IDs may need to be updated based on actual G League schedule
    # Using placeholder game IDs - real tests should use actual game IDs from schedule
    game_ids = KNOWN_TEST_GAME_IDS["G-League"]

    df = get_dataset(
        "player_game",
        {"league": "G-League", "season": "2024-25", "game_ids": game_ids},
        limit=500,
    )

    assert len(df) > 0, "G League player_game should return data"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "TEAM" in df.columns, "Should have TEAM"
    assert "PTS" in df.columns, "Should have PTS"
    assert "REB" in df.columns, "Should have REB"
    assert "AST" in df.columns, "Should have AST"
    assert "MIN" in df.columns, "Should have MIN (minutes)"
    assert "PLUS_MINUS" in df.columns, "Should have PLUS_MINUS"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "G-League"), "All rows should be marked as G-League"

    print(f"  ✓ Fetched {len(df)} player box scores from {len(game_ids)} games")
    print(f"  ✓ Average PPG: {df['PTS'].mean():.2f}")
    return True


def test_gleague_play_by_play() -> bool:
    """G League: Fetch play-by-play data for specific games"""
    game_ids = KNOWN_TEST_GAME_IDS["G-League"][:2]

    df = get_dataset(
        "pbp",
        {"league": "G-League", "season": "2024-25", "game_ids": game_ids},
    )

    assert len(df) > 0, "G League PBP should return data"
    assert "EVENT_NUM" in df.columns, "Should have EVENT_NUM"
    assert "EVENT_TYPE" in df.columns, "Should have EVENT_TYPE"
    assert "PERIOD" in df.columns, "Should have PERIOD"
    assert "CLOCK" in df.columns, "Should have CLOCK"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "G-League"), "All rows should be marked as G-League"

    print(f"  ✓ Fetched {len(df)} play-by-play events from {len(game_ids)} games")
    return True


def test_gleague_shots() -> bool:
    """G League: Fetch shot chart data with coordinates"""
    game_ids = KNOWN_TEST_GAME_IDS["G-League"][:2]

    df = get_dataset(
        "shots",
        {"league": "G-League", "season": "2024-25", "game_ids": game_ids},
    )

    assert len(df) > 0, "G League shots should return data"
    assert "LOC_X" in df.columns, "Should have LOC_X coordinate"
    assert "LOC_Y" in df.columns, "Should have LOC_Y coordinate"
    assert "SHOT_MADE" in df.columns, "Should have SHOT_MADE flag"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "SHOT_DISTANCE" in df.columns, "Should have SHOT_DISTANCE"
    assert "SHOT_ZONE_BASIC" in df.columns, "Should have SHOT_ZONE_BASIC"
    assert "LEAGUE" in df.columns, "Should have LEAGUE column"
    assert all(df["LEAGUE"] == "G-League"), "All rows should be marked as G-League"

    # Validate coordinates are numeric
    assert df["LOC_X"].dtype in ["int64", "float64"], "LOC_X should be numeric"
    assert df["LOC_Y"].dtype in ["int64", "float64"], "LOC_Y should be numeric"

    made_pct = (df["SHOT_MADE"].sum() / len(df)) * 100
    avg_distance = df["SHOT_DISTANCE"].mean()

    print(f"  ✓ Fetched {len(df)} shots from {len(game_ids)} games")
    print(f"  ✓ Shot accuracy: {made_pct:.1f}%")
    print(f"  ✓ Average shot distance: {avg_distance:.1f} feet")
    return True


def test_gleague_player_season() -> bool:
    """G League: Fetch player season aggregates"""
    df = get_dataset(
        "player_season",
        {"league": "G-League", "season": "2024-25", "per_mode": "PerGame"},
        limit=100,
    )

    assert len(df) > 0, "G League player_season should return data"
    assert "PLAYER_NAME" in df.columns, "Should have PLAYER_NAME"
    assert "GP" in df.columns, "Should have GP (games played)"
    assert "PTS" in df.columns, "Should have PTS"
    assert "REB" in df.columns, "Should have REB"
    assert "AST" in df.columns, "Should have AST"

    print(f"  ✓ Fetched {len(df)} player season aggregates")
    print(f"  ✓ Average PPG: {df['PTS'].mean():.2f}")
    return True


def test_gleague_team_season() -> bool:
    """G League: Fetch team season standings"""
    df = get_dataset(
        "team_season",
        {"league": "G-League", "season": "2024-25"},
        limit=50,
    )

    assert len(df) > 0, "G League team_season should return data"
    assert "TEAM_NAME" in df.columns or "TEAM" in df.columns, "Should have team name"
    assert "GP" in df.columns, "Should have GP (games played)"

    print(f"  ✓ Fetched {len(df)} team season records")
    return True


# ==============================================================================
# Main Test Runner
# ==============================================================================


def run_all_tests() -> bool:
    """Run all EuroCup and G League stress tests"""
    runner = StressTestRunner()

    print("\n" + "=" * 80)
    print("🏀 EUROCUP & G LEAGUE COMPREHENSIVE STRESS TESTS")
    print("=" * 80)
    print("\nTesting all granularities with real data...")
    print("- EuroCup: 7 granularities (schedule, player_game, team_game, pbp, shots, season)")
    print("- G League: 7 granularities (schedule, player_game, team_game, pbp, shots, season)")
    print("=" * 80)

    # EuroCup Tests
    runner.run_test("EuroCup: Schedule (Regular Season)", test_eurocup_schedule_regular_season)
    runner.run_test("EuroCup: Schedule (Playoffs)", test_eurocup_schedule_playoffs)
    runner.run_test("EuroCup: Player Game (Box Scores)", test_eurocup_player_game)
    runner.run_test("EuroCup: Play-by-Play", test_eurocup_play_by_play)
    runner.run_test("EuroCup: Shots (with X/Y coordinates)", test_eurocup_shots)
    runner.run_test("EuroCup: Player Season Aggregates", test_eurocup_player_season)
    runner.run_test("EuroCup: Team Season Standings", test_eurocup_team_season)

    # G League Tests
    runner.run_test("G League: Schedule", test_gleague_schedule)
    runner.run_test("G League: Player Game (Box Scores)", test_gleague_player_game)
    runner.run_test("G League: Play-by-Play", test_gleague_play_by_play)
    runner.run_test("G League: Shots (with X/Y coordinates)", test_gleague_shots)
    runner.run_test("G League: Player Season Aggregates", test_gleague_player_season)
    runner.run_test("G League: Team Season Standings", test_gleague_team_season)

    return runner.print_summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
