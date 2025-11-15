"""NBL Official Data Consistency Tests

Health tests to validate NBL data quality from nblR package.

Test Coverage:
- Player vs team stats consistency (sum of player PTS = team PTS)
- Data completeness checks
- Schema validation
- Cross-dataset referential integrity
"""

import pytest

from src.cbb_data.fetchers import nbl_official

# Test season (use recent season with data)
TEST_SEASON = "2023"  # 2023-24 season


# ==============================================================================
# Data Consistency Tests
# ==============================================================================


def test_nbl_player_vs_team_points_consistent():
    """Validate that sum of player PTS equals team PTS per game

    This is a fundamental consistency check:
    - Sum all player points per (GAME_ID, TEAM)
    - Compare to team box score PTS for same (GAME_ID, TEAM)
    - Allow small tolerance (≤ 2 points) for rounding errors
    """
    # Fetch player and team game data
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)
    team_game = nbl_official.fetch_nbl_team_game(TEST_SEASON)

    # Skip if no data available (R export not run yet)
    if player_game.empty or team_game.empty:
        pytest.skip("NBL data not available. Run: Rscript tools/nbl/export_nbl.R")

    # Aggregate player points by (GAME_ID, TEAM)
    player_pts_by_game = player_game.groupby(["GAME_ID", "TEAM"])["PTS"].sum().reset_index()
    player_pts_by_game.rename(columns={"PTS": "PLAYER_PTS"}, inplace=True)

    # Merge with team stats
    merged = team_game[["GAME_ID", "TEAM", "PTS"]].merge(
        player_pts_by_game, on=["GAME_ID", "TEAM"], how="left"
    )

    # Calculate differences
    merged["PTS_DIFF"] = (merged["PTS"] - merged["PLAYER_PTS"]).abs()

    # Check consistency (allow 2-point tolerance for rounding)
    assert (merged["PTS_DIFF"] <= 2).all(), (
        f"Player vs team points mismatch found:\n"
        f"{merged[merged['PTS_DIFF'] > 2][['GAME_ID', 'TEAM', 'PTS', 'PLAYER_PTS', 'PTS_DIFF']]}"
    )


def test_nbl_player_vs_team_rebounds_consistent():
    """Validate that sum of player REB equals team REB per game"""
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)
    team_game = nbl_official.fetch_nbl_team_game(TEST_SEASON)

    if player_game.empty or team_game.empty:
        pytest.skip("NBL data not available")

    # Aggregate player rebounds
    player_reb_by_game = player_game.groupby(["GAME_ID", "TEAM"])["REB"].sum().reset_index()
    player_reb_by_game.rename(columns={"REB": "PLAYER_REB"}, inplace=True)

    # Merge with team stats
    merged = team_game[["GAME_ID", "TEAM", "REB"]].merge(
        player_reb_by_game, on=["GAME_ID", "TEAM"], how="left"
    )

    # Calculate differences (allow larger tolerance for rebounds due to team rebounds)
    merged["REB_DIFF"] = (merged["REB"] - merged["PLAYER_REB"]).abs()

    # Allow up to 5 rebound difference (team rebounds not attributed to individuals)
    assert (merged["REB_DIFF"] <= 5).all(), (
        f"Player vs team rebounds mismatch found:\n"
        f"{merged[merged['REB_DIFF'] > 5][['GAME_ID', 'TEAM', 'REB', 'PLAYER_REB', 'REB_DIFF']]}"
    )


def test_nbl_player_vs_team_assists_consistent():
    """Validate that sum of player AST equals team AST per game"""
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)
    team_game = nbl_official.fetch_nbl_team_game(TEST_SEASON)

    if player_game.empty or team_game.empty:
        pytest.skip("NBL data not available")

    # Aggregate player assists
    player_ast_by_game = player_game.groupby(["GAME_ID", "TEAM"])["AST"].sum().reset_index()
    player_ast_by_game.rename(columns={"AST": "PLAYER_AST"}, inplace=True)

    # Merge with team stats
    merged = team_game[["GAME_ID", "TEAM", "AST"]].merge(
        player_ast_by_game, on=["GAME_ID", "TEAM"], how="left"
    )

    # Calculate differences
    merged["AST_DIFF"] = (merged["AST"] - merged["PLAYER_AST"]).abs()

    # Allow 1 assist tolerance
    assert (merged["AST_DIFF"] <= 1).all(), (
        f"Player vs team assists mismatch found:\n"
        f"{merged[merged['AST_DIFF'] > 1][['GAME_ID', 'TEAM', 'AST', 'PLAYER_AST', 'AST_DIFF']]}"
    )


# ==============================================================================
# Schema Validation Tests
# ==============================================================================


def test_nbl_schedule_schema():
    """Validate NBL schedule has expected columns"""
    schedule = nbl_official.fetch_nbl_schedule(TEST_SEASON)

    if schedule.empty:
        pytest.skip("NBL data not available")

    required_cols = ["GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]
    for col in required_cols:
        assert col in schedule.columns, f"Missing required column: {col}"


def test_nbl_player_game_schema():
    """Validate NBL player-game data has expected columns"""
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)

    if player_game.empty:
        pytest.skip("NBL data not available")

    required_cols = [
        "GAME_ID",
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM",
        "PTS",
        "REB",
        "AST",
        "FGM",
        "FGA",
        "FG_PCT",
        "LEAGUE",
    ]
    for col in required_cols:
        assert col in player_game.columns, f"Missing required column: {col}"


def test_nbl_team_game_schema():
    """Validate NBL team-game data has expected columns"""
    team_game = nbl_official.fetch_nbl_team_game(TEST_SEASON)

    if team_game.empty:
        pytest.skip("NBL data not available")

    required_cols = ["GAME_ID", "TEAM", "PTS", "REB", "AST", "FGM", "FGA", "FG_PCT", "LEAGUE"]
    for col in required_cols:
        assert col in team_game.columns, f"Missing required column: {col}"


def test_nbl_pbp_schema():
    """Validate NBL play-by-play data has expected columns"""
    pbp = nbl_official.fetch_nbl_pbp(TEST_SEASON)

    if pbp.empty:
        pytest.skip("NBL data not available")

    required_cols = ["GAME_ID", "PERIOD", "CLOCK", "DESCRIPTION", "LEAGUE"]
    for col in required_cols:
        assert col in pbp.columns, f"Missing required column: {col}"


def test_nbl_shots_schema():
    """Validate NBL shot data has expected columns"""
    shots = nbl_official.fetch_nbl_shots(TEST_SEASON)

    if shots.empty:
        pytest.skip("NBL data not available")

    required_cols = [
        "GAME_ID",
        "PLAYER_NAME",
        "LOC_X",
        "LOC_Y",
        "IS_MAKE",
        "POINTS_VALUE",
        "LEAGUE",
    ]
    for col in required_cols:
        assert col in shots.columns, f"Missing required column: {col}"


# ==============================================================================
# Data Completeness Tests
# ==============================================================================


def test_nbl_schedule_has_games():
    """Verify NBL schedule is not empty for test season"""
    schedule = nbl_official.fetch_nbl_schedule(TEST_SEASON)

    if schedule.empty:
        pytest.skip("NBL data not available")

    # NBL season typically has 100-150 games (regular season + playoffs)
    assert len(schedule) > 50, f"Expected >50 games, got {len(schedule)}"


def test_nbl_player_game_has_data():
    """Verify NBL player-game data is not empty"""
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)

    if player_game.empty:
        pytest.skip("NBL data not available")

    # Should have thousands of player-game records
    assert len(player_game) > 500, f"Expected >500 player-game records, got {len(player_game)}"


def test_nbl_shots_has_coordinates():
    """Verify NBL shot data includes x,y coordinates (the premium feature!)"""
    shots = nbl_official.fetch_nbl_shots(TEST_SEASON)

    if shots.empty:
        pytest.skip("NBL data not available")

    # Verify coordinates are present and non-null
    assert "LOC_X" in shots.columns, "Missing LOC_X (x-coordinate)"
    assert "LOC_Y" in shots.columns, "Missing LOC_Y (y-coordinate)"
    assert shots["LOC_X"].notna().sum() > 0, "All LOC_X values are null"
    assert shots["LOC_Y"].notna().sum() > 0, "All LOC_Y values are null"


# ==============================================================================
# Referential Integrity Tests
# ==============================================================================


def test_nbl_player_game_refers_to_valid_games():
    """Validate all player-game records reference valid games in schedule"""
    schedule = nbl_official.fetch_nbl_schedule(TEST_SEASON)
    player_game = nbl_official.fetch_nbl_player_game(TEST_SEASON)

    if schedule.empty or player_game.empty:
        pytest.skip("NBL data not available")

    valid_game_ids = set(schedule["GAME_ID"])
    player_game_ids = set(player_game["GAME_ID"])

    orphaned_games = player_game_ids - valid_game_ids

    assert len(orphaned_games) == 0, (
        f"Found {len(orphaned_games)} player-game records referencing "
        f"games not in schedule: {list(orphaned_games)[:10]}"
    )


def test_nbl_shots_refer_to_valid_games():
    """Validate all shot records reference valid games in schedule"""
    schedule = nbl_official.fetch_nbl_schedule(TEST_SEASON)
    shots = nbl_official.fetch_nbl_shots(TEST_SEASON)

    if schedule.empty or shots.empty:
        pytest.skip("NBL data not available")

    valid_game_ids = set(schedule["GAME_ID"])
    shot_game_ids = set(shots["GAME_ID"])

    orphaned_shots = shot_game_ids - valid_game_ids

    assert len(orphaned_shots) == 0, (
        f"Found {len(orphaned_shots)} shot records referencing "
        f"games not in schedule: {list(orphaned_shots)[:10]}"
    )
