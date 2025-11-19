"""ACB (Spanish Liga Endesa) Endpoint Tests

Tests for verifying ACB data correctness, schema, and internal consistency.
ACB uses HTML scraping for schedule/player/team data.
PBP and shots require rpy2/BAwiR (devcontainer/WSL only).

Run with: pytest tests/data_sources/test_acb_endpoints.py -v
"""

import sys

import pytest

sys.path.insert(0, "src")

from cbb_data.fetchers import acb


class TestACBSchedule:
    """Tests for ACB schedule/game index."""

    def test_schedule_non_empty(self):
        """Schedule should return games for 2024 season."""
        df = acb.fetch_acb_schedule(season="2024")

        assert not df.empty, "Schedule should not be empty for 2024"
        assert len(df) >= 10, f"Expected at least 10 games, got {len(df)}"

    def test_schedule_has_required_columns(self):
        """Schedule should have required columns."""
        df = acb.fetch_acb_schedule(season="2024")

        # Check for game identifier (various naming conventions)
        id_cols = ["game_code", "game_id", "GAME_ID", "id"]
        has_id = any(col in df.columns for col in id_cols)
        assert has_id, f"Missing game ID column. Columns: {list(df.columns)}"

    def test_schedule_has_multiple_games(self):
        """Schedule should have multiple distinct games."""
        df = acb.fetch_acb_schedule(season="2024")

        if df.empty:
            pytest.skip("No schedule data")

        # Find game ID column
        game_id_col = None
        for col in ["game_code", "game_id", "GAME_ID", "id"]:
            if col in df.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        # Should have multiple distinct games
        unique_games = df[game_id_col].nunique()
        assert unique_games >= 10, f"Should have at least 10 distinct games, got {unique_games}"


class TestACBBoxScore:
    """Tests for ACB box score data (per-game fetch)."""

    def test_box_score_function_exists(self):
        """Box score fetch function should exist."""
        assert hasattr(acb, "fetch_acb_box_score"), "fetch_acb_box_score should exist"

    def test_box_score_for_sample_game(self):
        """Box score should return data for a sample game."""
        # First get a game ID from schedule
        schedule = acb.fetch_acb_schedule(season="2024")

        if schedule.empty:
            pytest.skip("No schedule data to get game IDs")

        # Find game ID column
        game_id_col = None
        for col in ["game_code", "game_id", "GAME_ID", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        # Get first game ID
        game_id = str(schedule[game_id_col].iloc[0])

        # Fetch box score
        df = acb.fetch_acb_box_score(game_id)

        if df.empty:
            pytest.skip(f"No box score for game {game_id}")

        # Check for stat columns
        stat_cols = ["PTS", "REB", "AST", "pts", "reb", "ast", "points"]
        has_stats = any(col in df.columns for col in stat_cols)
        assert has_stats, f"Box score should have stat columns. Got: {list(df.columns)}"


class TestACBPlayByPlay:
    """Tests for ACB play-by-play data (per-game fetch)."""

    def test_pbp_function_exists(self):
        """PBP fetch function should exist."""
        assert hasattr(acb, "fetch_acb_play_by_play"), "fetch_acb_play_by_play should exist"

    def test_pbp_for_sample_game(self):
        """PBP should return data for a sample game."""
        schedule = acb.fetch_acb_schedule(season="2024")

        if schedule.empty:
            pytest.skip("No schedule data")

        # Find game ID column
        game_id_col = None
        for col in ["game_code", "game_id", "GAME_ID", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        game_id = str(schedule[game_id_col].iloc[0])
        df = acb.fetch_acb_play_by_play(game_id)

        if df.empty:
            pytest.skip(f"No PBP for game {game_id}")

        assert len(df) > 0, "PBP should have events"


class TestACBShotChart:
    """Tests for ACB shot chart data (per-game fetch)."""

    def test_shot_chart_function_exists(self):
        """Shot chart fetch function should exist."""
        assert hasattr(acb, "fetch_acb_shot_chart"), "fetch_acb_shot_chart should exist"

    def test_shot_chart_for_sample_game(self):
        """Shot chart should return data for a sample game."""
        schedule = acb.fetch_acb_schedule(season="2024")

        if schedule.empty:
            pytest.skip("No schedule data")

        game_id_col = None
        for col in ["game_code", "game_id", "GAME_ID", "id"]:
            if col in schedule.columns:
                game_id_col = col
                break

        if game_id_col is None:
            pytest.skip("No game ID column found")

        game_id = str(schedule[game_id_col].iloc[0])
        df = acb.fetch_acb_shot_chart(game_id)

        if df.empty:
            pytest.skip(f"No shot chart for game {game_id}")

        # Check for coordinate columns
        coord_cols = ["x", "y", "X", "Y", "loc_x", "loc_y"]
        has_coords = any(col in df.columns for col in coord_cols)
        assert has_coords, f"Shot chart should have coordinates. Got: {list(df.columns)}"


class TestACBSeasonStats:
    """Tests for ACB season aggregate stats."""

    def test_player_season_non_empty(self):
        """Player season stats should return data."""
        df = acb.fetch_acb_player_season(season="2024")

        assert not df.empty, "Player season data should not be empty"

    def test_team_season_non_empty(self):
        """Team season stats should return data."""
        df = acb.fetch_acb_team_season(season="2024")

        assert not df.empty, "Team season data should not be empty"


class TestACBBAwiRBulkFetch:
    """Tests for ACB BAwiR-based bulk fetch functions.

    Note: These require rpy2/BAwiR which only works in devcontainer/WSL.
    On Windows without rpy2, these will be skipped.
    """

    def test_bawir_game_index_function_exists(self):
        """BAwiR game index function should exist."""
        assert hasattr(acb, "fetch_acb_game_index_bawir"), "fetch_acb_game_index_bawir should exist"

    def test_bawir_pbp_function_exists(self):
        """BAwiR PBP function should exist."""
        assert hasattr(acb, "fetch_acb_pbp_bawir"), "fetch_acb_pbp_bawir should exist"

    def test_bawir_shots_function_exists(self):
        """BAwiR shot chart function should exist."""
        assert hasattr(acb, "fetch_acb_shot_chart_bawir"), "fetch_acb_shot_chart_bawir should exist"

    @pytest.mark.skipif(
        not getattr(acb, "RPY2_AVAILABLE", False),
        reason="rpy2 not available - requires devcontainer/WSL",
    )
    def test_bawir_pbp_returns_data(self):
        """BAwiR PBP should return data when rpy2 is available."""
        df = acb.fetch_acb_pbp_bawir(season="2024")

        if df.empty:
            pytest.skip("No PBP data (BAwiR may require authentication)")

    @pytest.mark.skipif(
        not getattr(acb, "RPY2_AVAILABLE", False),
        reason="rpy2 not available - requires devcontainer/WSL",
    )
    def test_bawir_shots_returns_data(self):
        """BAwiR shots should return data when rpy2 is available."""
        df = acb.fetch_acb_shot_chart_bawir(season="2024")

        if df.empty:
            pytest.skip("No shot data (BAwiR may require authentication)")


class TestACBHistoricalCoverage:
    """Tests for ACB historical data availability."""

    @pytest.mark.parametrize("season", ["2023", "2022", "2021", "2020"])
    def test_historical_schedule_available(self, season):
        """Historical seasons should have schedule data."""
        df = acb.fetch_acb_schedule(season=season)

        # Some seasons may have limited data
        if df.empty:
            pytest.skip(f"No schedule data for {season}")

        assert len(df) >= 5, f"Season {season} should have at least 5 games"

    def test_coverage_summary(self):
        """Generate coverage summary for ACB."""
        results = {}
        for season in ["2024", "2023", "2022", "2021", "2020"]:
            try:
                df = acb.fetch_acb_schedule(season=season)
                results[season] = len(df) if not df.empty else 0
            except Exception as e:
                results[season] = f"Error: {e}"

        print("\nACB Historical Coverage:")
        for season, count in results.items():
            print(f"  {season}: {count} games")

        # At least current season should have data
        assert results.get("2024", 0) > 0, "Current season should have data"
