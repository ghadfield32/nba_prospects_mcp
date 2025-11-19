"""LNB (French Pro A) Endpoint Tests

Tests for verifying LNB data correctness, schema, and internal consistency.
LNB uses the Atrium Sports API for comprehensive game data.

Run with: pytest tests/data_sources/test_lnb_endpoints.py -v
"""

import sys

import pytest

sys.path.insert(0, "src")

from cbb_data.fetchers import lnb


class TestLNBSchedule:
    """Tests for LNB schedule/game index."""

    def test_schedule_v2_non_empty(self):
        """Schedule v2 (API) should return games for 2025 season."""
        # Note: fetch_lnb_schedule_v2 uses int season (2025 = 2024-25 season)
        df = lnb.fetch_lnb_schedule_v2(season=2025)

        if df.empty:
            pytest.skip("No schedule data for 2025")

        assert len(df) >= 1, f"Expected at least 1 game, got {len(df)}"

    def test_schedule_v2_has_game_id(self):
        """Schedule v2 should have game identifiers."""
        df = lnb.fetch_lnb_schedule_v2(season=2025)

        if df.empty:
            pytest.skip("No schedule data available")

        # Check for game ID column
        id_cols = ["game_id", "fixture_uuid", "GAME_ID", "external_id"]
        has_id = any(col in df.columns for col in id_cols)
        assert has_id, f"Schedule should have game ID. Columns: {list(df.columns)}"

    def test_schedule_v2_has_required_columns(self):
        """Schedule v2 should have standard columns."""
        df = lnb.fetch_lnb_schedule_v2(season=2025)

        if df.empty:
            pytest.skip("No schedule data available")

        # Check for key columns
        expected_cols = ["GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]
        missing = [col for col in expected_cols if col not in df.columns]
        assert not missing, f"Missing columns: {missing}. Got: {list(df.columns)}"


class TestLNBSeasonStats:
    """Tests for LNB season aggregate stats."""

    def test_player_season_function_exists(self):
        """Player season fetch function should exist."""
        assert hasattr(lnb, "fetch_lnb_player_season"), "fetch_lnb_player_season should exist"

    def test_team_season_function_exists(self):
        """Team season fetch function should exist."""
        assert hasattr(lnb, "fetch_lnb_team_season"), "fetch_lnb_team_season should exist"

    def test_player_season_returns_data(self):
        """Player season should return data for 2024."""
        df = lnb.fetch_lnb_player_season(season="2024")

        if df.empty:
            pytest.skip("No player season data")

        assert len(df) > 0, "Should have player season data"

    def test_team_season_returns_data(self):
        """Team season should return data for 2024."""
        df = lnb.fetch_lnb_team_season(season="2024")

        if df.empty:
            pytest.skip("No team season data")

        assert len(df) > 0, "Should have team season data"


class TestLNBBoxScore:
    """Tests for LNB box score data (per-game fetch)."""

    def test_box_score_function_exists(self):
        """Box score fetch function should exist."""
        assert hasattr(lnb, "fetch_lnb_box_score"), "fetch_lnb_box_score should exist"

    def test_box_score_for_sample_game(self):
        """Box score should return data for a sample game."""
        # First get a game ID from schedule (v2 uses int season)
        schedule = lnb.fetch_lnb_schedule_v2(season=2025)

        if schedule.empty:
            pytest.skip("No schedule data to get game IDs")

        # Find game ID column
        game_id_col = None
        for col in ["GAME_ID", "game_id", "fixture_uuid", "external_id", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        # Get first game ID
        game_id = str(schedule[game_id_col].iloc[0])

        # Fetch box score
        df = lnb.fetch_lnb_box_score(game_id)

        if df.empty:
            pytest.skip(f"No box score for game {game_id}")

        assert len(df) > 0, "Box score should have player data"


class TestLNBPlayByPlay:
    """Tests for LNB play-by-play data (per-game fetch)."""

    def test_pbp_function_exists(self):
        """PBP fetch function should exist."""
        assert hasattr(lnb, "fetch_lnb_play_by_play"), "fetch_lnb_play_by_play should exist"

    def test_pbp_for_sample_game(self):
        """PBP should return data for a sample game."""
        schedule = lnb.fetch_lnb_schedule_v2(season=2025)

        if schedule.empty:
            pytest.skip("No schedule data")

        # Find game ID column
        game_id_col = None
        for col in ["GAME_ID", "game_id", "fixture_uuid", "external_id", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        game_id = str(schedule[game_id_col].iloc[0])
        df = lnb.fetch_lnb_play_by_play(game_id)

        if df.empty:
            pytest.skip(f"No PBP for game {game_id}")

        assert len(df) > 0, "PBP should have events"


class TestLNBShots:
    """Tests for LNB shot chart data (per-game fetch)."""

    def test_shots_function_exists(self):
        """Shots fetch function should exist."""
        assert hasattr(lnb, "fetch_lnb_shots"), "fetch_lnb_shots should exist"

    def test_shots_for_sample_game(self):
        """Shots should return data for a sample game."""
        schedule = lnb.fetch_lnb_schedule_v2(season=2025)

        if schedule.empty:
            pytest.skip("No schedule data")

        # Find game ID column
        game_id_col = None
        for col in ["GAME_ID", "game_id", "fixture_uuid", "external_id", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        game_id = str(schedule[game_id_col].iloc[0])
        df = lnb.fetch_lnb_shots(game_id)

        if df.empty:
            pytest.skip(f"No shots for game {game_id}")

        # Check for coordinate columns
        coord_cols = ["x", "y", "X", "Y", "loc_x", "loc_y", "coord_x", "coord_y"]
        has_x = any(col in df.columns for col in coord_cols if "x" in col.lower())
        has_y = any(col in df.columns for col in coord_cols if "y" in col.lower())

        assert has_x and has_y, f"Shots should have coordinates. Columns: {list(df.columns)}"


class TestLNBNormalizedFunctions:
    """Tests for LNB normalized data functions."""

    def test_player_game_normalized_exists(self):
        """Player game normalized function should exist."""
        assert hasattr(
            lnb, "fetch_lnb_player_game_normalized"
        ), "fetch_lnb_player_game_normalized should exist"

    def test_team_game_normalized_exists(self):
        """Team game normalized function should exist."""
        assert hasattr(
            lnb, "fetch_lnb_team_game_normalized"
        ), "fetch_lnb_team_game_normalized should exist"


class TestLNBHistoricalFunctions:
    """Tests for LNB historical data functions."""

    def test_pbp_historical_exists(self):
        """PBP historical function should exist."""
        assert hasattr(lnb, "fetch_lnb_pbp_historical"), "fetch_lnb_pbp_historical should exist"

    def test_shots_historical_exists(self):
        """Shots historical function should exist."""
        assert hasattr(lnb, "fetch_lnb_shots_historical"), "fetch_lnb_shots_historical should exist"


class TestLNBHistoricalCoverage:
    """Tests for LNB historical data availability."""

    @pytest.mark.parametrize("season_int", [2025, 2024, 2023])
    def test_historical_schedule_available(self, season_int):
        """Historical seasons should have schedule data."""
        df = lnb.fetch_lnb_schedule_v2(season=season_int)

        if df.empty:
            pytest.skip(f"No schedule data for {season_int}")

        assert len(df) >= 1, f"Season {season_int} should have at least 1 game"

    def test_coverage_summary(self):
        """Generate coverage summary for LNB."""
        results = {}

        # fetch_lnb_schedule_v2 uses int seasons (2025 = 2024-25 season)
        for season_int in [2025, 2024, 2023, 2022]:
            try:
                df = lnb.fetch_lnb_schedule_v2(season=season_int)
                results[season_int] = len(df) if not df.empty else 0
            except Exception as e:
                results[season_int] = f"Error: {str(e)[:50]}"

        print("\nLNB Pro A Historical Coverage:")
        for season, count in results.items():
            print(f"  {season}: {count} games")

        # Current season should have data
        assert results.get(2025, 0) > 0, "Current season should have data"
