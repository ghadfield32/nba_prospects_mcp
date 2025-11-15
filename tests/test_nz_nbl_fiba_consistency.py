"""NZ NBL FIBA Data Consistency Tests

Health tests to validate NZ-NBL data quality from FIBA LiveStats HTML scraping.

Test Coverage:
- Player vs team stats consistency (sum of player PTS = team PTS)
- Data completeness checks
- Schema validation
- Game index availability
"""

import pytest

from src.cbb_data.fetchers import nz_nbl_fiba

# Test season (use sample season from game index)
TEST_SEASON = "2024"


# ==============================================================================
# Game Index Tests
# ==============================================================================


def test_nz_nbl_game_index_exists():
    """Verify NZ-NBL game index file exists and is loadable"""
    game_index = nz_nbl_fiba.load_game_index()

    # Should have sample games
    assert (
        not game_index.empty
    ), "Game index is empty. Expected sample games in data/nz_nbl_game_index.csv"


def test_nz_nbl_game_index_schema():
    """Validate game index has expected columns"""
    game_index = nz_nbl_fiba.load_game_index()

    if game_index.empty:
        pytest.skip("NZ-NBL game index not available")

    required_cols = ["SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]
    for col in required_cols:
        assert col in game_index.columns, f"Missing required column in game index: {col}"


# ==============================================================================
# Data Consistency Tests
# ==============================================================================


def test_nz_nbl_player_vs_team_points_consistent():
    """Validate that sum of player PTS equals team PTS per game

    Note: This test will be skipped until HTML parsing is implemented.
    """
    player_game = nz_nbl_fiba.fetch_nz_nbl_player_game(TEST_SEASON)
    team_game = nz_nbl_fiba.fetch_nz_nbl_team_game(TEST_SEASON)

    # Skip if HTML parsing not yet implemented
    if player_game.empty or team_game.empty:
        pytest.skip("NZ-NBL HTML parsing not yet implemented. Scaffold in place.")

    # Aggregate player points by (GAME_ID, TEAM)
    player_pts_by_game = player_game.groupby(["GAME_ID", "TEAM"])["PTS"].sum().reset_index()
    player_pts_by_game.rename(columns={"PTS": "PLAYER_PTS"}, inplace=True)

    # Merge with team stats
    merged = team_game[["GAME_ID", "TEAM", "PTS"]].merge(
        player_pts_by_game, on=["GAME_ID", "TEAM"], how="left"
    )

    # Calculate differences
    merged["PTS_DIFF"] = (merged["PTS"] - merged["PLAYER_PTS"]).abs()

    # Check consistency (allow 2-point tolerance)
    assert (merged["PTS_DIFF"] <= 2).all(), (
        f"Player vs team points mismatch found:\n"
        f"{merged[merged['PTS_DIFF'] > 2][['GAME_ID', 'TEAM', 'PTS', 'PLAYER_PTS', 'PTS_DIFF']]}"
    )


def test_nz_nbl_player_vs_team_rebounds_consistent():
    """Validate that sum of player REB equals team REB per game

    Note: This test will be skipped until HTML parsing is implemented.
    """
    player_game = nz_nbl_fiba.fetch_nz_nbl_player_game(TEST_SEASON)
    team_game = nz_nbl_fiba.fetch_nz_nbl_team_game(TEST_SEASON)

    if player_game.empty or team_game.empty:
        pytest.skip("NZ-NBL HTML parsing not yet implemented")

    # Aggregate player rebounds
    player_reb_by_game = player_game.groupby(["GAME_ID", "TEAM"])["REB"].sum().reset_index()
    player_reb_by_game.rename(columns={"REB": "PLAYER_REB"}, inplace=True)

    # Merge with team stats
    merged = team_game[["GAME_ID", "TEAM", "REB"]].merge(
        player_reb_by_game, on=["GAME_ID", "TEAM"], how="left"
    )

    # Calculate differences
    merged["REB_DIFF"] = (merged["REB"] - merged["PLAYER_REB"]).abs()

    # Allow up to 5 rebound difference (team rebounds)
    assert (merged["REB_DIFF"] <= 5).all(), (
        f"Player vs team rebounds mismatch found:\n"
        f"{merged[merged['REB_DIFF'] > 5][['GAME_ID', 'TEAM', 'REB', 'PLAYER_REB', 'REB_DIFF']]}"
    )


# ==============================================================================
# Schema Validation Tests
# ==============================================================================


def test_nz_nbl_schedule_schema():
    """Validate NZ-NBL schedule has expected columns"""
    schedule = nz_nbl_fiba.fetch_nz_nbl_schedule(TEST_SEASON)

    if schedule.empty:
        pytest.skip("NZ-NBL game index not available")

    required_cols = ["GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]
    for col in required_cols:
        assert col in schedule.columns, f"Missing required column: {col}"

    # Verify LEAGUE is "NZ-NBL"
    assert (schedule["LEAGUE"] == "NZ-NBL").all(), "Expected LEAGUE to be 'NZ-NBL'"


def test_nz_nbl_player_game_schema():
    """Validate NZ-NBL player-game data has expected columns

    Note: This test will be skipped until HTML parsing is implemented.
    """
    player_game = nz_nbl_fiba.fetch_nz_nbl_player_game(TEST_SEASON)

    if player_game.empty:
        pytest.skip("NZ-NBL HTML parsing not yet implemented")

    required_cols = ["GAME_ID", "PLAYER_NAME", "TEAM", "PTS", "REB", "AST", "LEAGUE"]
    for col in required_cols:
        assert col in player_game.columns, f"Missing required column: {col}"

    # Verify LEAGUE is "NZ-NBL"
    assert (player_game["LEAGUE"] == "NZ-NBL").all(), "Expected LEAGUE to be 'NZ-NBL'"


def test_nz_nbl_team_game_schema():
    """Validate NZ-NBL team-game data has expected columns

    Note: This test will be skipped until HTML parsing is implemented.
    """
    team_game = nz_nbl_fiba.fetch_nz_nbl_team_game(TEST_SEASON)

    if team_game.empty:
        pytest.skip("NZ-NBL HTML parsing not yet implemented")

    required_cols = ["GAME_ID", "TEAM", "PTS", "REB", "AST", "LEAGUE"]
    for col in required_cols:
        assert col in team_game.columns, f"Missing required column: {col}"

    # Verify LEAGUE is "NZ-NBL"
    assert (team_game["LEAGUE"] == "NZ-NBL").all(), "Expected LEAGUE to be 'NZ-NBL'"


def test_nz_nbl_pbp_schema():
    """Validate NZ-NBL play-by-play data has expected columns

    Note: This test will be skipped until HTML parsing is implemented.
    """
    pbp = nz_nbl_fiba.fetch_nz_nbl_pbp(TEST_SEASON)

    if pbp.empty:
        pytest.skip("NZ-NBL HTML parsing not yet implemented")

    required_cols = ["GAME_ID", "PERIOD", "CLOCK", "DESCRIPTION", "LEAGUE"]
    for col in required_cols:
        assert col in pbp.columns, f"Missing required column: {col}"

    # Verify LEAGUE is "NZ-NBL"
    assert (pbp["LEAGUE"] == "NZ-NBL").all(), "Expected LEAGUE to be 'NZ-NBL'"


# ==============================================================================
# Data Completeness Tests
# ==============================================================================


def test_nz_nbl_schedule_has_games():
    """Verify NZ-NBL schedule is not empty for test season"""
    schedule = nz_nbl_fiba.fetch_nz_nbl_schedule(TEST_SEASON)

    if schedule.empty:
        pytest.skip("NZ-NBL game index not available")

    # Should have at least sample games
    assert len(schedule) >= 5, f"Expected ≥5 sample games, got {len(schedule)}"


def test_nz_nbl_schedule_league_code():
    """Verify NZ-NBL schedule uses correct FIBA league code"""
    # This is more of a documentation/reference test
    assert nz_nbl_fiba.FIBA_LEAGUE_CODE == "NZN", "Expected FIBA league code 'NZN' for NZ NBL"


# ==============================================================================
# HTML Scraping Configuration Tests
# ==============================================================================


def test_nz_nbl_fiba_urls_format():
    """Verify FIBA LiveStats URL format is correct"""
    base_url = nz_nbl_fiba.FIBA_BASE_URL
    league_code = nz_nbl_fiba.FIBA_LEAGUE_CODE

    # Verify base URL format
    assert base_url.startswith("https://"), "FIBA base URL should use HTTPS"
    assert "fibalivestats" in base_url.lower(), "Expected fibalivestats in base URL"

    # Test URL construction
    game_id = "12345"
    expected_bs_url = f"{base_url}/u/{league_code}/{game_id}/bs.html"
    expected_pbp_url = f"{base_url}/u/{league_code}/{game_id}/pbp.html"

    assert (
        expected_bs_url
        == f"https://fibalivestats.dcd.shared.geniussports.com/u/NZN/{game_id}/bs.html"
    )
    assert (
        expected_pbp_url
        == f"https://fibalivestats.dcd.shared.geniussports.com/u/NZN/{game_id}/pbp.html"
    )


def test_nz_nbl_html_parsing_dependencies():
    """Verify HTML parsing dependencies are available (or gracefully handled)"""
    # This test documents the optional dependency requirement
    from src.cbb_data.fetchers.nz_nbl_fiba import HTML_PARSING_AVAILABLE

    if not HTML_PARSING_AVAILABLE:
        pytest.skip(
            "HTML parsing dependencies not installed. "
            "Install with: uv pip install requests beautifulsoup4\n"
            "This is expected in environments without web scraping support."
        )
    else:
        # If available, verify imports work
        import requests
        from bs4 import BeautifulSoup

        assert requests is not None
        assert BeautifulSoup is not None
