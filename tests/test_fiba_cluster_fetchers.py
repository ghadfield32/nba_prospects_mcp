"""
Parametrized tests for all FIBA HTML-based league fetchers.

Tests LKL, BAL, BCL, and ABA using shared test logic.
This demonstrates the reusability of the FIBA HTML infrastructure.
"""

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

import pandas as pd
import pytest
from utils.fiba_test_helpers import (
    assert_fiba_metadata,
    get_fiba_game_index_path,
    skip_if_empty_fiba,
    skip_if_no_schedule,
)
from utils.league_health import (
    assert_league_endpoints_ok,
    assert_pbp_ok,
    assert_player_game_ok,
    assert_schedule_ok,
    assert_team_game_ok,
)

from cbb_data.fetchers import aba, bal, bcl, lkl

# ==============================================================================
# Test Configuration
# ==============================================================================

# FIBA leagues to test (league_code, season, fetcher_module)
FIBA_LEAGUES = [
    ("LKL", "2023-24", lkl),  # Lithuania Basketball League
    ("BAL", "2023-24", bal),  # Basketball Africa League
    ("BCL", "2023-24", bcl),  # Basketball Champions League
    ("ABA", "2023-24", aba),  # ABA Adriatic League
]


# ==============================================================================
# Schedule Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_schedule(league, season, mod):
    """Test schedule fetching for FIBA leagues"""
    schedule = mod.fetch_schedule(season)

    # Basic validation
    assert isinstance(schedule, pd.DataFrame), f"{league} schedule should return DataFrame"

    # Skip if no game index exists
    skip_if_no_schedule(schedule, league, season)

    # Validate using health check
    assert_schedule_ok(league, season, schedule, min_games=1, strict=False)

    # FIBA-specific metadata checks
    assert_fiba_metadata(schedule, league, season)

    # FIBA-specific columns
    assert "FIBA_COMPETITION" in schedule.columns, "Should have FIBA_COMPETITION column"
    assert "FIBA_PHASE" in schedule.columns, "Should have FIBA_PHASE column"
    assert (schedule["SOURCE"] == "fiba_html").all(), "All games should be from fiba_html source"


# ==============================================================================
# Player Game Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_player_game(league, season, mod):
    """Test player game stats for FIBA leagues"""
    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    player_game = mod.fetch_player_game(season)

    # Basic validation
    assert isinstance(player_game, pd.DataFrame), f"{league} player_game should return DataFrame"

    # Skip if no data (403 errors, placeholder IDs, etc.)
    skip_if_empty_fiba("player_game", player_game, league, season)

    # Validate using health check
    assert_player_game_ok(
        league, season, schedule, player_game, min_players_per_game=5, strict=False
    )

    # FIBA-specific metadata
    assert_fiba_metadata(player_game, league, season)

    # Check player ID format (should be TEAM_PLAYERNAME)
    sample_player_id = player_game["PLAYER_ID"].iloc[0]
    assert "_" in sample_player_id, f"{league} player ID should contain underscore separator"


# ==============================================================================
# Team Game Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_team_game(league, season, mod):
    """Test team game stats for FIBA leagues"""
    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    player_game = mod.fetch_player_game(season)
    skip_if_empty_fiba("player_game", player_game, league, season)

    team_game = mod.fetch_team_game(season)

    # Basic validation
    assert isinstance(team_game, pd.DataFrame), f"{league} team_game should return DataFrame"

    # Skip if no data
    skip_if_empty_fiba("team_game", team_game, league, season)

    # Validate using health check
    assert_team_game_ok(league, season, schedule, team_game, player_game, strict=False)

    # FIBA-specific metadata
    assert_fiba_metadata(team_game, league, season)

    # Check that we have exactly 2 teams per game
    game_counts = team_game.groupby("GAME_ID").size()
    assert (game_counts == 2).all(), f"{league}: Each game should have exactly 2 teams"


# ==============================================================================
# Play-by-Play Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_pbp(league, season, mod):
    """Test play-by-play for FIBA leagues (when available)"""
    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    pbp = mod.fetch_pbp(season)

    # Basic validation
    assert isinstance(pbp, pd.DataFrame), f"{league} pbp should return DataFrame"

    # PBP may be empty if not available - that's OK
    if not pbp.empty:
        # Validate using health check
        assert_pbp_ok(league, season, schedule, pbp, strict=False)

        # FIBA-specific metadata
        assert_fiba_metadata(pbp, league, season)

        # Check required PBP columns
        assert "EVENT_NUM" in pbp.columns, f"{league} should have EVENT_NUM column"
        assert "PERIOD" in pbp.columns, f"{league} should have PERIOD column"
        assert "PCTIMESTRING" in pbp.columns, f"{league} should have PCTIMESTRING column"


# ==============================================================================
# Season Aggregate Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_team_season(league, season, mod):
    """Test team season aggregates for FIBA leagues"""
    team_season = mod.fetch_team_season(season)

    # Basic validation
    assert isinstance(team_season, pd.DataFrame), f"{league} team_season should return DataFrame"

    # Skip if no data
    skip_if_empty_fiba("team_season", team_season, league, season)

    # FIBA-specific metadata
    assert_fiba_metadata(team_season, league, season)

    # Check required columns
    assert "TEAM_ID" in team_season.columns, f"{league} should have TEAM_ID column"
    assert "GP" in team_season.columns, f"{league} should have GP (games played) column"
    assert "PTS" in team_season.columns, f"{league} should have PTS column"
    assert "PTS_PG" in team_season.columns, f"{league} should have PTS_PG (points per game) column"

    # Check that GP is positive
    assert (team_season["GP"] > 0).all(), f"{league}: All teams should have played games"

    # Check that per-game stats are reasonable
    assert (team_season["PTS_PG"] > 0).all(), f"{league}: All teams should have positive PTS_PG"
    assert (team_season["PTS_PG"] < 200).all(), f"{league}: PTS_PG should be reasonable (< 200)"


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_player_season(league, season, mod):
    """Test player season aggregates for FIBA leagues"""
    player_season = mod.fetch_player_season(season)

    # Basic validation
    assert isinstance(
        player_season, pd.DataFrame
    ), f"{league} player_season should return DataFrame"

    # Skip if no data
    skip_if_empty_fiba("player_season", player_season, league, season)

    # FIBA-specific metadata
    assert_fiba_metadata(player_season, league, season)

    # Check required columns
    assert "PLAYER_ID" in player_season.columns, f"{league} should have PLAYER_ID column"
    assert "PLAYER_NAME" in player_season.columns, f"{league} should have PLAYER_NAME column"
    assert "GP" in player_season.columns, f"{league} should have GP (games played) column"
    assert "PTS" in player_season.columns, f"{league} should have PTS column"
    assert (
        "PTS_PG" in player_season.columns
    ), f"{league} should have PTS_PG (points per game) column"

    # Check that GP is positive
    assert (player_season["GP"] > 0).all(), f"{league}: All players should have played games"

    # Check that per-game stats are reasonable
    assert (
        player_season["PTS_PG"] >= 0
    ).all(), f"{league}: All players should have non-negative PTS_PG"
    assert (
        player_season["MIN_PG"] >= 0
    ).all(), f"{league}: All players should have non-negative MIN_PG"


# ==============================================================================
# Comprehensive Health Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_season_health(league, season, mod):
    """Comprehensive health test for FIBA league season

    Tests all endpoints together and validates cross-endpoint consistency.
    This is the highest-level integration test for each league.
    """
    # Fetch all endpoints
    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    player_game = mod.fetch_player_game(season)
    team_game = mod.fetch_team_game(season)
    pbp = mod.fetch_pbp(season)

    # Build endpoints dict (only include non-empty endpoints)
    endpoints = {"schedule": schedule}

    if not player_game.empty:
        endpoints["player_game"] = player_game

    if not team_game.empty:
        endpoints["team_game"] = team_game

    if not pbp.empty:
        endpoints["pbp"] = pbp

    # Run comprehensive validation
    assert_league_endpoints_ok(league, season, endpoints, strict=False)


# ==============================================================================
# Backwards Compatibility Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_backwards_compatibility(league, season, mod):
    """Test that backwards-compatible function names work

    Each FIBA league provides both:
    - New names: fetch_schedule(), fetch_player_game(), etc.
    - Old names: fetch_lkl_schedule(), fetch_bal_player_game(), etc.
    """
    # Get league prefix (lowercase)
    league_prefix = league.lower()

    # Test schedule backwards compatibility
    old_func = getattr(mod, f"fetch_{league_prefix}_schedule")
    new_func = mod.fetch_schedule

    schedule_old = old_func(season)
    schedule_new = new_func(season)

    assert schedule_old.equals(
        schedule_new
    ), f"{league}: Old and new schedule functions should return same data"

    # Skip remaining tests if no schedule
    skip_if_no_schedule(schedule_old, league, season)

    # Test player_game backwards compatibility
    old_func = getattr(mod, f"fetch_{league_prefix}_player_game")
    new_func = mod.fetch_player_game

    player_game_old = old_func(season)
    player_game_new = new_func(season)

    if not player_game_old.empty:  # Only compare if data exists
        assert player_game_old.equals(
            player_game_new
        ), f"{league}: Old and new player_game functions should return same data"


# ==============================================================================
# Caching Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_cache_reuse(league, season, mod):
    """Test that cached data is reused on subsequent calls"""
    import time

    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    # First call - should hit network
    start = time.time()
    df1 = mod.fetch_player_game(season, force_refresh=False)
    first_duration = time.time() - start

    # Skip if no data
    if df1.empty:
        pytest.skip(f"{league} {season}: No player data available for cache test")

    # Second call - should use cache
    start = time.time()
    df2 = mod.fetch_player_game(season, force_refresh=False)
    second_duration = time.time() - start

    # Cached call should be faster (at least 2x faster)
    assert (
        second_duration < first_duration / 2
    ), f"{league}: Cached call should be significantly faster"

    # Data should be identical
    assert df1.equals(df2), f"{league}: Cached data should match original data"


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_force_refresh(league, season, mod):
    """Test that force_refresh bypasses cache"""
    schedule = mod.fetch_schedule(season)
    skip_if_no_schedule(schedule, league, season)

    # Get cached version
    df_cached = mod.fetch_player_game(season, force_refresh=False)

    # Skip if no data
    if df_cached.empty:
        pytest.skip(f"{league} {season}: No player data available for force refresh test")

    # Force refresh
    df_fresh = mod.fetch_player_game(season, force_refresh=True)

    # Should have same shape and columns
    assert df_cached.shape == df_fresh.shape, f"{league}: Refreshed data should have same shape"
    assert list(df_cached.columns) == list(
        df_fresh.columns
    ), f"{league}: Refreshed data should have same columns"


# ==============================================================================
# Utility Tests
# ==============================================================================


@pytest.mark.parametrize("league, season, mod", FIBA_LEAGUES)
def test_fiba_game_index_path(league, season, mod):
    """Test that game index path is correctly formatted"""
    expected_path = get_fiba_game_index_path(league, season)
    assert (
        "data/game_indexes" in expected_path
    ), "Game index should be in data/game_indexes directory"
    assert league in expected_path, "Game index path should contain league code"
    assert (
        season.replace("-", "_") in expected_path
    ), "Game index path should contain normalized season"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
