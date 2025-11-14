"""
Tests for LKL (Lithuania Basketball League) fetcher.

This serves as the golden template for all FIBA HTML-based league tests.
"""

import sys

# Add src and tests to path
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

import pandas as pd
import pytest
from utils.league_health import (
    assert_league_endpoints_ok,
    assert_pbp_ok,
    assert_player_game_ok,
    assert_schedule_ok,
    assert_team_game_ok,
)

from cbb_data.fetchers import lkl

LEAGUE = "LKL"
TEST_SEASON = "2023-24"


class TestLKLFetcher:
    """Test suite for LKL fetcher functions."""

    def test_lkl_schedule(self):
        """Test LKL schedule fetching."""
        schedule = lkl.fetch_schedule(TEST_SEASON)

        # Basic validation
        assert isinstance(schedule, pd.DataFrame), "Schedule should return DataFrame"
        assert not schedule.empty, "Schedule should not be empty"

        # Health check using utility
        assert_schedule_ok(LEAGUE, TEST_SEASON, schedule, min_games=1, strict=False)

        # LKL-specific checks
        assert "FIBA_COMPETITION" in schedule.columns, "Should have FIBA_COMPETITION column"
        assert "FIBA_PHASE" in schedule.columns, "Should have FIBA_PHASE column"
        assert (
            schedule["SOURCE"] == "fiba_html"
        ).all(), "All games should be from fiba_html source"

    def test_lkl_player_game(self):
        """Test LKL player game stats fetching."""
        schedule = lkl.fetch_schedule(TEST_SEASON)
        player_game = lkl.fetch_player_game(TEST_SEASON)

        # Basic validation
        assert isinstance(player_game, pd.DataFrame), "Player game should return DataFrame"

        # Skip if no data available (expected for sample game IDs)
        if player_game.empty:
            pytest.skip("No player game data available - requires real FIBA game IDs")

        # Health check using utility
        assert_player_game_ok(
            LEAGUE,
            TEST_SEASON,
            schedule,
            player_game,
            min_players_per_game=5,
            strict=False,
        )

        # LKL-specific checks
        assert "PLAYER_ID" in player_game.columns, "Should have PLAYER_ID column"
        assert "PLAYER_NAME" in player_game.columns, "Should have PLAYER_NAME column"
        assert "TEAM_ID" in player_game.columns, "Should have TEAM_ID column"

        # Check player ID format (should be TEAM_PLAYERNAME)
        sample_player_id = player_game["PLAYER_ID"].iloc[0]
        assert "_" in sample_player_id, "Player ID should contain underscore separator"

    def test_lkl_team_game(self):
        """Test LKL team game stats fetching."""
        schedule = lkl.fetch_schedule(TEST_SEASON)
        player_game = lkl.fetch_player_game(TEST_SEASON)
        team_game = lkl.fetch_team_game(TEST_SEASON)

        # Basic validation
        assert isinstance(team_game, pd.DataFrame), "Team game should return DataFrame"

        # Skip if no data available (expected for sample game IDs)
        if team_game.empty:
            pytest.skip("No team game data available - requires real FIBA game IDs")

        # Health check using utility
        assert_team_game_ok(
            LEAGUE,
            TEST_SEASON,
            schedule,
            team_game,
            player_game,
            strict=False,
        )

        # LKL-specific checks
        assert "TEAM_ID" in team_game.columns, "Should have TEAM_ID column"
        assert "TEAM" in team_game.columns, "Should have TEAM column"

        # Check that we have exactly 2 teams per game
        game_counts = team_game.groupby("GAME_ID").size()
        assert (game_counts == 2).all(), "Each game should have exactly 2 teams"

    def test_lkl_pbp(self):
        """Test LKL play-by-play fetching."""
        schedule = lkl.fetch_schedule(TEST_SEASON)
        pbp = lkl.fetch_pbp(TEST_SEASON)

        # Basic validation
        assert isinstance(pbp, pd.DataFrame), "PBP should return DataFrame"

        # Note: PBP might be empty if not available for all games
        if not pbp.empty:
            # Health check using utility
            assert_pbp_ok(LEAGUE, TEST_SEASON, schedule, pbp, strict=False)

            # LKL-specific checks
            assert "EVENT_NUM" in pbp.columns, "Should have EVENT_NUM column"
            assert "PERIOD" in pbp.columns, "Should have PERIOD column"
            assert "PCTIMESTRING" in pbp.columns, "Should have PCTIMESTRING column"

    def test_lkl_team_season(self):
        """Test LKL team season aggregates."""
        team_season = lkl.fetch_team_season(TEST_SEASON)

        # Basic validation
        assert isinstance(team_season, pd.DataFrame), "Team season should return DataFrame"

        # Skip if no data available (expected for sample game IDs)
        if team_season.empty:
            pytest.skip("No team season data available - requires real FIBA game IDs")

        # Check required columns
        assert "TEAM_ID" in team_season.columns, "Should have TEAM_ID column"
        assert "GP" in team_season.columns, "Should have GP (games played) column"
        assert "PTS" in team_season.columns, "Should have PTS column"
        assert "PTS_PG" in team_season.columns, "Should have PTS_PG (points per game) column"

        # Check that GP is positive
        assert (team_season["GP"] > 0).all(), "All teams should have played games"

        # Check that per-game stats are reasonable
        assert (team_season["PTS_PG"] > 0).all(), "All teams should have positive PTS_PG"
        assert (team_season["PTS_PG"] < 200).all(), "PTS_PG should be reasonable (< 200)"

    def test_lkl_player_season(self):
        """Test LKL player season aggregates."""
        player_season = lkl.fetch_player_season(TEST_SEASON)

        # Basic validation
        assert isinstance(player_season, pd.DataFrame), "Player season should return DataFrame"

        # Skip if no data available (expected for sample game IDs)
        if player_season.empty:
            pytest.skip("No player season data available - requires real FIBA game IDs")

        # Check required columns
        assert "PLAYER_ID" in player_season.columns, "Should have PLAYER_ID column"
        assert "PLAYER_NAME" in player_season.columns, "Should have PLAYER_NAME column"
        assert "GP" in player_season.columns, "Should have GP (games played) column"
        assert "PTS" in player_season.columns, "Should have PTS column"
        assert "PTS_PG" in player_season.columns, "Should have PTS_PG (points per game) column"

        # Check that GP is positive
        assert (player_season["GP"] > 0).all(), "All players should have played games"

        # Check that per-game stats are reasonable
        assert (player_season["PTS_PG"] >= 0).all(), "All players should have non-negative PTS_PG"
        assert (player_season["MIN_PG"] >= 0).all(), "All players should have non-negative MIN_PG"

    def test_lkl_season_health(self):
        """
        Comprehensive health test for LKL 2023-24 season.
        This is the golden template test from the user's roadmap.
        """
        season = TEST_SEASON

        # Fetch all endpoints
        schedule = lkl.fetch_schedule(season)
        player_game = lkl.fetch_player_game(season)
        team_game = lkl.fetch_team_game(season)
        pbp = lkl.fetch_pbp(season)

        # Use composite health check
        endpoints = {
            "schedule": schedule,
            "player_game": player_game,
            "team_game": team_game,
        }

        # Add PBP if available
        if not pbp.empty:
            endpoints["pbp"] = pbp

        # Run comprehensive validation
        assert_league_endpoints_ok(LEAGUE, season, endpoints, strict=False)

    def test_lkl_backwards_compatibility(self):
        """Test that backwards-compatible function names work."""
        # Test old naming convention
        schedule_old = lkl.fetch_lkl_schedule(TEST_SEASON)
        schedule_new = lkl.fetch_schedule(TEST_SEASON)

        assert schedule_old.equals(
            schedule_new
        ), "Old and new function names should return same data"

        # Test other endpoints
        player_game_old = lkl.fetch_lkl_player_game(TEST_SEASON)
        player_game_new = lkl.fetch_player_game(TEST_SEASON)
        assert player_game_old.equals(player_game_new), "Player game backwards compatibility"

        team_game_old = lkl.fetch_lkl_team_game(TEST_SEASON)
        team_game_new = lkl.fetch_team_game(TEST_SEASON)
        assert team_game_old.equals(team_game_new), "Team game backwards compatibility"


class TestLKLCaching:
    """Test caching behavior for LKL fetcher."""

    def test_cache_reuse(self):
        """Test that cached data is reused on subsequent calls."""
        import time

        # First call - should hit network
        start = time.time()
        df1 = lkl.fetch_player_game(TEST_SEASON, force_refresh=False)
        first_duration = time.time() - start

        # Second call - should use cache
        start = time.time()
        df2 = lkl.fetch_player_game(TEST_SEASON, force_refresh=False)
        second_duration = time.time() - start

        # Cached call should be faster (at least 2x faster)
        assert second_duration < first_duration / 2, "Cached call should be significantly faster"

        # Data should be identical
        assert df1.equals(df2), "Cached data should match original data"

    def test_force_refresh(self):
        """Test that force_refresh bypasses cache."""
        # Get cached version
        df_cached = lkl.fetch_player_game(TEST_SEASON, force_refresh=False)

        # Force refresh
        df_fresh = lkl.fetch_player_game(TEST_SEASON, force_refresh=True)

        # Should have same shape and columns
        assert df_cached.shape == df_fresh.shape, "Refreshed data should have same shape"
        assert list(df_cached.columns) == list(
            df_fresh.columns
        ), "Refreshed data should have same columns"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
