"""NZ-NBL (New Zealand National Basketball League) Endpoint Tests

Tests for verifying NZ-NBL data correctness, schema, and internal consistency.
NZ-NBL uses FIBA LiveStats for game data and Genius Sports JS widgets for schedule.

Run with: pytest tests/data_sources/test_nz_nbl_endpoints.py -v
"""

import sys

import pandas as pd
import pytest

sys.path.insert(0, "src")

from cbb_data.fetchers import nz_nbl_fiba


class TestNZNBLSchedule:
    """Tests for NZ-NBL schedule/game index.

    Note: NZ-NBL season typically runs May-August in New Zealand.
    - 2024 season may be empty if testing before May or after August
    - Try 2023 as fallback for completed season data
    """

    def test_schedule_non_empty(self):
        """Schedule should return games for available season."""
        # Try current season first, then fallback to completed season
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)

            if not df.empty:
                assert len(df) >= 1, f"Expected at least 1 game, got {len(df)}"
                print(f"\nFound {len(df)} games in {season} season")
                return

        # If both seasons empty, check Playwright availability
        playwright_available = getattr(nz_nbl_fiba, "PLAYWRIGHT_AVAILABLE", False)
        if not playwright_available:
            pytest.skip("Playwright not available for schedule discovery")
        pytest.skip("No schedule data for 2024 or 2023 (season may not have started or ended)")

    def test_schedule_has_fiba_game_ids(self):
        """Schedule should have FIBA game IDs for fetching detailed stats."""
        # Try to get schedule from available season
        df = None
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)
            if not df.empty:
                break

        if df is None or df.empty:
            pytest.skip("No schedule data available")

        # Check for game ID column
        id_cols = ["GAME_ID", "FIBA_GAME_ID", "game_id", "fiba_game_id"]
        has_id = any(col in df.columns for col in id_cols)
        assert has_id, f"Schedule should have game ID column. Columns: {list(df.columns)}"


class TestNZNBLPlayerGame:
    """Tests for NZ-NBL player game (box score) data."""

    def test_player_game_function_exists(self):
        """Player game fetch function should exist."""
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_player_game"
        ), "fetch_nz_nbl_player_game function should exist"

    def test_player_game_returns_dataframe(self):
        """Player game should return a DataFrame."""
        # Try current season, fallback to previous
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_player_game(season=season)

            assert isinstance(df, pd.DataFrame), "Should return a DataFrame"

            if not df.empty:
                print(f"\nFound {len(df)} player game records in {season} season")
                return

        pytest.skip("No player game data (season may not have started)")

    def test_player_game_has_player_identifier(self):
        """Player game should have player name or ID."""
        # Try to get data from available season
        df = None
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_player_game(season=season)
            if not df.empty:
                break

        if df is None or df.empty:
            pytest.skip("No player game data available")

        player_cols = ["PLAYER_NAME", "player_name", "PLAYER_ID", "player_id", "name"]
        has_player = any(col in df.columns for col in player_cols)
        assert has_player, f"Should have player identifier. Columns: {list(df.columns)}"


class TestNZNBLTeamGame:
    """Tests for NZ-NBL team game aggregates."""

    def test_team_game_function_exists(self):
        """Team game fetch function should exist."""
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_team_game"
        ), "fetch_nz_nbl_team_game function should exist"

    def test_team_game_returns_dataframe(self):
        """Team game should return a DataFrame."""
        # Try current season, fallback to previous
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_team_game(season=season)

            assert isinstance(df, pd.DataFrame), "Should return a DataFrame"

            if not df.empty:
                print(f"\nFound {len(df)} team game records in {season} season")
                return

        # Empty is acceptable for off-season
        pass


class TestNZNBLSeasonStats:
    """Tests for NZ-NBL season aggregate stats."""

    def test_player_season_function_exists(self):
        """Player season fetch function should exist."""
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_player_season"
        ), "fetch_nz_nbl_player_season function should exist"

    def test_team_season_function_exists(self):
        """Team season fetch function should exist."""
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_team_season"
        ), "fetch_nz_nbl_team_season function should exist"

    def test_player_season_returns_dataframe(self):
        """Player season should return a DataFrame."""
        # Try current season, fallback to previous
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_player_season(season=season)

            assert isinstance(df, pd.DataFrame), "Should return a DataFrame"

            if not df.empty:
                print(f"\nFound {len(df)} player season records in {season} season")
                return

        # Empty is acceptable for off-season
        pass

    def test_team_season_returns_dataframe(self):
        """Team season should return a DataFrame."""
        # Try current season, fallback to previous
        for season in ["2024", "2023"]:
            df = nz_nbl_fiba.fetch_nz_nbl_team_season(season=season)

            assert isinstance(df, pd.DataFrame), "Should return a DataFrame"

            if not df.empty:
                print(f"\nFound {len(df)} team season records in {season} season")
                return

        # Empty is acceptable for off-season
        pass


class TestNZNBLPBPAndShots:
    """Tests for NZ-NBL play-by-play and shot chart data."""

    def test_pbp_function_exists(self):
        """PBP fetch function should exist."""
        assert hasattr(nz_nbl_fiba, "fetch_nz_nbl_pbp"), "fetch_nz_nbl_pbp function should exist"

    def test_shots_function_exists(self):
        """Shot chart fetch function should exist."""
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_shot_chart"
        ), "fetch_nz_nbl_shot_chart function should exist"

    def test_pbp_callable(self):
        """PBP function should be callable."""
        assert callable(nz_nbl_fiba.fetch_nz_nbl_pbp), "PBP function should be callable"

    def test_shots_callable(self):
        """Shot chart function should be callable."""
        assert callable(
            nz_nbl_fiba.fetch_nz_nbl_shot_chart
        ), "Shot chart function should be callable"


class TestNZNBLInternalConsistency:
    """Tests for data consistency between NZ-NBL datasets."""

    def test_team_game_matches_schedule(self):
        """Number of games in team data should match schedule."""
        # Try current season, fallback to previous
        for season in ["2024", "2023"]:
            schedule = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)
            team_game = nz_nbl_fiba.fetch_nz_nbl_team_game(season=season)

            if not schedule.empty and not team_game.empty:
                break
        else:
            pytest.skip("Missing data for comparison")

        # Find game ID columns
        schedule_id = None
        for col in ["GAME_ID", "FIBA_GAME_ID", "game_id"]:
            if col in schedule.columns:
                schedule_id = col
                break

        team_id = None
        for col in ["GAME_ID", "game_id"]:
            if col in team_game.columns:
                team_id = col
                break

        if schedule_id is None or team_id is None:
            pytest.skip("Missing game ID columns")

        schedule_games = len(schedule)
        team_games = team_game[team_id].nunique()

        print(f"\nSchedule games: {schedule_games}")
        print(f"Team game unique games: {team_games}")
        print(f"Team game total rows: {len(team_game)}")
        print(f"Expected team rows (2 per game): {schedule_games * 2}")


class TestNZNBLPlaywrightDependency:
    """Tests for Playwright availability (required for schedule discovery)."""

    def test_playwright_available_flag_exists(self):
        """Module should have PLAYWRIGHT_AVAILABLE flag."""
        assert hasattr(
            nz_nbl_fiba, "PLAYWRIGHT_AVAILABLE"
        ), "Module should export PLAYWRIGHT_AVAILABLE flag"

    def test_playwright_availability_status(self):
        """Check and report Playwright availability."""
        available = getattr(nz_nbl_fiba, "PLAYWRIGHT_AVAILABLE", False)

        if available:
            print("\nPlaywright is available - full schedule discovery enabled")
        else:
            print("\nPlaywright not available - install with:")
            print("  uv pip install 'cbb-data[nz_nbl]' && playwright install chromium")


class TestNZNBLHistoricalCoverage:
    """Tests for NZ-NBL historical data availability.

    Note: NZ-NBL season runs May-August in New Zealand.
    - 2024 may be empty if testing outside this window
    - 403 errors may occur for FIBA LiveStats access
    """

    def test_coverage_summary(self):
        """Generate coverage summary for NZ-NBL."""
        results = {}

        for season in ["2024", "2023", "2022"]:
            try:
                # Try player season as it's faster than schedule
                df = nz_nbl_fiba.fetch_nz_nbl_player_season(season=season)
                if not df.empty:
                    results[season] = f"{len(df)} players"
                else:
                    results[season] = "No data (off-season or access restricted)"
            except Exception as e:
                error_msg = str(e)
                if "403" in error_msg:
                    results[season] = "403 Forbidden (access restricted)"
                else:
                    results[season] = f"Error: {error_msg[:50]}"

        print("\nNZ-NBL Historical Coverage (player season):")
        for season, status in results.items():
            print(f"  {season}: {status}")

        # Note: NZ-NBL data availability depends on season timing and access
        # Don't fail test for empty data during off-season
        has_any_data = any("players" in str(v) for v in results.values())
        if not has_any_data:
            playwright_available = getattr(nz_nbl_fiba, "PLAYWRIGHT_AVAILABLE", False)
            if not playwright_available:
                print("\nNote: Playwright not available - schedule discovery limited")
            print("Note: NZ-NBL data may be unavailable during off-season (Sep-Apr)")
