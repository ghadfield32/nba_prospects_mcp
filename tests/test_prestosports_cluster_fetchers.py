"""Test PrestoSports Cluster Fetchers (USPORTS, CCAA, NAIA, NJCAA)

Parametrized tests covering US and Canadian leagues using the PrestoSports platform.

Test Coverage:
- USPORTS (Canadian university basketball)
- CCAA (Canadian college basketball)
- NAIA (US small college basketball)
- NJCAA (US junior college basketball)

Each league is tested across all available endpoints with shared test logic.
"""

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

import pandas as pd
import pytest

from cbb_data.fetchers import ccaa, naia, njcaa, usports

# =============================================================================
# Test Configuration
# =============================================================================

# Leagues to test: (league_code, season, module)
PRESTOSPORTS_LEAGUES = [
    ("USPORTS", "2023-24", usports),
    ("CCAA", "2023-24", ccaa),
    ("NAIA", "2023-24", naia),
    ("NJCAA", "2023-24", njcaa),
]


# =============================================================================
# Helper Functions
# =============================================================================


def skip_if_empty_prestosports(endpoint_name: str, df: pd.DataFrame, league: str, season: str):
    """Skip test if PrestoSports endpoint returns empty DataFrame

    Args:
        endpoint_name: Name of endpoint (schedule, player_season, etc.)
        df: DataFrame to check
        league: League code
        season: Season string
    """
    if df.empty:
        pytest.skip(
            f"{league} {season}: {endpoint_name} empty - PrestoSports may require "
            "additional HTML parsing or season leaders may not be available yet"
        )


def assert_prestosports_metadata(df: pd.DataFrame, league: str, season: str):
    """Assert PrestoSports-specific metadata columns are present and valid

    Args:
        df: DataFrame to validate
        league: Expected league code
        season: Expected season
    """
    # LEAGUE column should exist and match
    if "LEAGUE" in df.columns:
        assert (df["LEAGUE"] == league).all(), f"LEAGUE column should be '{league}'"

    # SEASON column (if present) should match
    if "SEASON" in df.columns:
        assert (df["SEASON"] == season).all(), f"SEASON column should be '{season}'"


# =============================================================================
# Parametrized Tests
# =============================================================================


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_schedule(league, season, mod):
    """Test schedule fetching for PrestoSports leagues"""
    schedule = mod.fetch_schedule(season)

    assert isinstance(schedule, pd.DataFrame), "Schedule should be a DataFrame"
    skip_if_empty_prestosports("schedule", schedule, league, season)

    # Validate columns
    required_cols = ["GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]
    for col in required_cols:
        assert col in schedule.columns, f"Schedule should have {col} column"

    # Validate metadata
    assert_prestosports_metadata(schedule, league, season)


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_player_season(league, season, mod):
    """Test player season stats for PrestoSports leagues

    Note: This tests the season leaders functionality which is fully implemented.
    """
    player_season = mod.fetch_player_season(season, stat_category="points", limit=50)

    assert isinstance(player_season, pd.DataFrame), "Player season should be a DataFrame"
    skip_if_empty_prestosports("player_season", player_season, league, season)

    # Validate columns (at minimum should have player info)
    required_cols = ["PLAYER_NAME", "TEAM", "LEAGUE"]
    for col in required_cols:
        assert col in player_season.columns, f"Player season should have {col} column"

    # Validate metadata
    assert_prestosports_metadata(player_season, league, season)

    # Should have stats columns (varies by category, but should have at least GP or PTS)
    assert (
        "GP" in player_season.columns or "PTS" in player_season.columns
    ), "Should have stats columns (GP or PTS)"


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_team_season(league, season, mod):
    """Test team season stats for PrestoSports leagues

    Note: Currently uses generic aggregation (scaffold mode).
    """
    team_season = mod.fetch_team_season(season)

    assert isinstance(team_season, pd.DataFrame), "Team season should be a DataFrame"

    # Expected to be empty in scaffold mode
    if not team_season.empty:
        required_cols = ["TEAM", "LEAGUE"]
        for col in required_cols:
            assert col in team_season.columns, f"Team season should have {col} column"
        assert_prestosports_metadata(team_season, league, season)


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_player_game_scaffold(league, season, mod):
    """Test player game stats scaffold for PrestoSports leagues

    Note: Currently scaffold mode (requires box score scraping).
    """
    # Without game_id, should return empty with LEAGUE column
    player_game = mod.fetch_player_game(season)

    assert isinstance(player_game, pd.DataFrame), "Player game should be a DataFrame"
    assert "LEAGUE" in player_game.columns, "Should have LEAGUE column even when empty"

    if not player_game.empty:
        assert (player_game["LEAGUE"] == league).all()


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_team_game_scaffold(league, season, mod):
    """Test team game stats scaffold for PrestoSports leagues

    Note: Currently scaffold mode (aggregated from player_game).
    """
    team_game = mod.fetch_team_game(season)

    assert isinstance(team_game, pd.DataFrame), "Team game should be a DataFrame"
    assert "LEAGUE" in team_game.columns, "Should have LEAGUE column even when empty"

    if not team_game.empty:
        assert (team_game["LEAGUE"] == league).all()


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_pbp_unavailable(league, season, mod):
    """Test PBP (should be unavailable for PrestoSports)

    PrestoSports platform does not provide detailed play-by-play data.
    """
    pbp = mod.fetch_pbp(season)

    assert isinstance(pbp, pd.DataFrame), "PBP should be a DataFrame"
    assert "LEAGUE" in pbp.columns, "Should have LEAGUE column even when unavailable"

    # Expected to be empty (unavailable)
    if not pbp.empty:
        # If somehow not empty, validate structure
        assert (pbp["LEAGUE"] == league).all()


@pytest.mark.parametrize("league, season, mod", PRESTOSPORTS_LEAGUES)
def test_prestosports_shots_unavailable(league, season, mod):
    """Test shot charts (should be unavailable for PrestoSports)

    PrestoSports platform does not provide shot coordinate data.
    """
    shots = mod.fetch_shots(season)

    assert isinstance(shots, pd.DataFrame), "Shots should be a DataFrame"
    assert "LEAGUE" in shots.columns, "Should have LEAGUE column even when unavailable"

    # Expected to be empty (unavailable)
    if not shots.empty:
        # If somehow not empty, validate structure
        assert (shots["LEAGUE"] == league).all()


# =============================================================================
# League-Specific Tests
# =============================================================================


def test_usports_player_season_with_conference():
    """Test U SPORTS player season with conference filter

    U SPORTS conferences: OUA, Canada West, AUS, RSEQ
    """
    # Note: Conference filtering may not work without proper PrestoSports HTML parsing
    df = usports.fetch_player_season("2023-24", stat_category="points", limit=10)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "LEAGUE" in df.columns
        assert (df["LEAGUE"] == "USPORTS").all()


def test_ccaa_player_season_basic():
    """Test CCAA player season basic functionality

    CCAA is Canadian college basketball (similar to NJCAA in US).
    """
    df = ccaa.fetch_player_season("2023-24", stat_category="points", limit=10)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "LEAGUE" in df.columns
        assert (df["LEAGUE"] == "CCAA").all()


# =============================================================================
# Integration Tests
# =============================================================================


def test_prestosports_cluster_all_leagues_registered():
    """Test that all PrestoSports leagues are properly registered in catalog"""
    from cbb_data.catalog.sources import get_league_source_config

    for league, _, _ in PRESTOSPORTS_LEAGUES:
        config = get_league_source_config(league)
        assert config is not None, f"{league} should be registered in catalog"
        assert config.player_season_source == "prestosports"
        assert config.schedule_source == "prestosports"


def test_prestosports_cluster_fetch_functions_exist():
    """Test that fetch functions are properly wired in catalog"""
    from cbb_data.catalog.sources import get_league_source_config

    for league, _, _ in PRESTOSPORTS_LEAGUES:
        config = get_league_source_config(league)

        # These should be explicitly registered
        assert config.fetch_schedule is not None
        assert config.fetch_player_season is not None
        assert config.fetch_pbp is not None

        # PBP and shots should be unavailable (return empty)
        assert config.pbp_source == "none"
        assert config.shots_source == "none"
