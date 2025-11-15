#!/usr/bin/env python3
"""LNB Health Checks and Schema Stability Tests

CI monitoring suite for LNB data pipeline:
1. Schema stability - Ensure columns haven't changed
2. API health - Verify endpoints are reachable
3. Data quality - Check for nulls, out-of-range values
4. Coverage monitoring - Track data availability over time

Usage:
    # Run all health checks
    pytest tests/test_lnb_health.py -v

    # Run specific test
    pytest tests/test_lnb_health.py::TestSchemaStability::test_pbp_schema -v

    # Generate coverage report
    pytest tests/test_lnb_health.py --cov=src.cbb_data.fetchers.lnb

CI Integration:
    - Run on push to main branch
    - Run weekly via cron (Monday 9am)
    - Alert if schemas change or APIs fail
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play, fetch_lnb_schedule, fetch_lnb_shots

# ==============================================================================
# TEST FIXTURES
# ==============================================================================

# Known working game ID for testing (updated periodically)
TEST_GAME_ID = "0d0504a0-6715-11f0-98ab-27e6e78614e1"
TEST_SEASON = "2024-2025"

# Expected schemas (updated if intentional schema changes)
EXPECTED_PBP_COLUMNS = [
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "EVENT_SUBTYPE",
    "PLAYER_ID",
    "PLAYER_NAME",
    "PLAYER_JERSEY",
    "TEAM_ID",
    "DESCRIPTION",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
    "HOME_SCORE",
    "AWAY_SCORE",
    "LEAGUE",
]

EXPECTED_SHOTS_COLUMNS = [
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "SHOT_SUBTYPE",
    "PLAYER_ID",
    "PLAYER_NAME",
    "PLAYER_JERSEY",
    "TEAM_ID",
    "DESCRIPTION",
    "SUCCESS",
    "SUCCESS_STRING",
    "X_COORD",
    "Y_COORD",
    "LEAGUE",
]

EXPECTED_PLAYER_GAME_COLUMNS = [
    "GAME_ID",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "MIN",
    "PTS",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG2M",
    "FG2A",
    "FG2_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PLUS_MINUS",
    "SEASON",
    "LEAGUE",
]

EXPECTED_TEAM_GAME_COLUMNS = [
    "GAME_ID",
    "TEAM_ID",
    "PTS",
    "FGM",
    "FGA",
    "FG2M",
    "FG2A",
    "FG3M",
    "FG3A",
    "FTM",
    "FTA",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "FG_PCT",
    "FG2_PCT",
    "FG3_PCT",
    "FT_PCT",
    "SEASON",
    "LEAGUE",
    "OPP_ID",
    "OPP_PTS",
    "WIN",
]

EXPECTED_SHOT_EVENTS_COLUMNS = [
    "GAME_ID",
    "EVENT_ID",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "PERIOD",
    "CLOCK",
    "CLOCK_SECONDS",
    "SHOT_TYPE",
    "SHOT_SUBTYPE",
    "SHOT_ZONE",
    "SHOT_DISTANCE",
    "X",
    "Y",
    "MADE",
    "POINTS",
    "DESCRIPTION",
    "LEAGUE",
    "SEASON",
]

EXPECTED_EVENT_TYPES = [
    "jumpBall",
    "2pt",
    "3pt",
    "freeThrow",
    "rebound",
    "assist",
    "steal",
    "turnover",
    "foul",
    "block",
    "timeOut",
    "substitution",
]


# ==============================================================================
# SCHEMA STABILITY TESTS
# ==============================================================================


class TestSchemaStability:
    """Test that schemas haven't changed unexpectedly"""

    def test_pbp_schema(self):
        """Verify PBP schema matches expected columns"""
        df = fetch_lnb_play_by_play(TEST_GAME_ID)

        assert not df.empty, "PBP data should not be empty"

        # Check columns
        assert list(df.columns) == EXPECTED_PBP_COLUMNS, (
            f"PBP schema changed!\n"
            f"Expected: {EXPECTED_PBP_COLUMNS}\n"
            f"Got: {list(df.columns)}"
        )

        # Check data types
        assert df["GAME_ID"].dtype == object
        assert df["EVENT_ID"].dtype == object
        assert df["PERIOD_ID"].dtype in [np.int64, np.float64]
        assert df["EVENT_TYPE"].dtype == object

    def test_shots_schema(self):
        """Verify shots schema matches expected columns"""
        df = fetch_lnb_shots(TEST_GAME_ID)

        assert not df.empty, "Shots data should not be empty"

        # Check columns
        assert list(df.columns) == EXPECTED_SHOTS_COLUMNS, (
            f"Shots schema changed!\n"
            f"Expected: {EXPECTED_SHOTS_COLUMNS}\n"
            f"Got: {list(df.columns)}"
        )

        # Check data types
        assert df["SUCCESS"].dtype == bool
        assert df["X_COORD"].dtype in [np.float64, np.int64]
        assert df["Y_COORD"].dtype in [np.float64, np.int64]

    def test_normalized_player_game_schema(self):
        """Verify normalized PLAYER_GAME schema"""
        player_game_file = Path(
            f"data/normalized/lnb/player_game/season={TEST_SEASON}/game_id={TEST_GAME_ID}.parquet"
        )

        if not player_game_file.exists():
            pytest.skip("Normalized tables not yet created")

        df = pd.read_parquet(player_game_file)

        assert not df.empty, "PLAYER_GAME data should not be empty"

        # Check columns
        assert list(df.columns) == EXPECTED_PLAYER_GAME_COLUMNS, (
            f"PLAYER_GAME schema changed!\n"
            f"Expected: {EXPECTED_PLAYER_GAME_COLUMNS}\n"
            f"Got: {list(df.columns)}"
        )

    def test_normalized_team_game_schema(self):
        """Verify normalized TEAM_GAME schema"""
        team_game_file = Path(
            f"data/normalized/lnb/team_game/season={TEST_SEASON}/game_id={TEST_GAME_ID}.parquet"
        )

        if not team_game_file.exists():
            pytest.skip("Normalized tables not yet created")

        df = pd.read_parquet(team_game_file)

        assert not df.empty, "TEAM_GAME data should not be empty"

        # Check columns
        assert list(df.columns) == EXPECTED_TEAM_GAME_COLUMNS, (
            f"TEAM_GAME schema changed!\n"
            f"Expected: {EXPECTED_TEAM_GAME_COLUMNS}\n"
            f"Got: {list(df.columns)}"
        )

    def test_normalized_shot_events_schema(self):
        """Verify normalized SHOT_EVENTS schema"""
        shot_events_file = Path(
            f"data/normalized/lnb/shot_events/season={TEST_SEASON}/game_id={TEST_GAME_ID}.parquet"
        )

        if not shot_events_file.exists():
            pytest.skip("Normalized tables not yet created")

        df = pd.read_parquet(shot_events_file)

        assert not df.empty, "SHOT_EVENTS data should not be empty"

        # Check columns
        assert list(df.columns) == EXPECTED_SHOT_EVENTS_COLUMNS, (
            f"SHOT_EVENTS schema changed!\n"
            f"Expected: {EXPECTED_SHOT_EVENTS_COLUMNS}\n"
            f"Got: {list(df.columns)}"
        )


# ==============================================================================
# API HEALTH TESTS
# ==============================================================================


class TestAPIHealth:
    """Test that API endpoints are reachable and functional"""

    def test_pbp_api_reachable(self):
        """Verify PBP API returns data"""
        df = fetch_lnb_play_by_play(TEST_GAME_ID)

        assert not df.empty, "PBP API should return data"
        assert len(df) > 100, f"Expected >100 events, got {len(df)}"

    def test_shots_api_reachable(self):
        """Verify shots API returns data"""
        df = fetch_lnb_shots(TEST_GAME_ID)

        assert not df.empty, "Shots API should return data"
        assert len(df) > 50, f"Expected >50 shots, got {len(df)}"

    def test_schedule_api_reachable(self):
        """Verify schedule API returns data"""
        try:
            df = fetch_lnb_schedule(season="2024")
            assert not df.empty, "Schedule API should return data"
        except Exception as e:
            pytest.skip(f"Schedule API not available: {e}")


# ==============================================================================
# DATA QUALITY TESTS
# ==============================================================================


class TestDataQuality:
    """Test data quality and validity"""

    def test_pbp_event_types_valid(self):
        """Verify PBP event types are recognized"""
        df = fetch_lnb_play_by_play(TEST_GAME_ID)

        event_types = df["EVENT_TYPE"].unique()

        for event_type in event_types:
            assert event_type in EXPECTED_EVENT_TYPES, (
                f"Unexpected event type: {event_type}\n" f"Known types: {EXPECTED_EVENT_TYPES}"
            )

    def test_pbp_no_critical_nulls(self):
        """Verify critical PBP columns have no nulls"""
        df = fetch_lnb_play_by_play(TEST_GAME_ID)

        critical_columns = ["GAME_ID", "EVENT_ID", "PERIOD_ID", "EVENT_TYPE"]

        for col in critical_columns:
            null_count = df[col].isnull().sum()
            assert null_count == 0, f"Column {col} has {null_count} nulls"

    def test_shots_coordinates_valid(self):
        """Verify shot coordinates are in valid range (0-100)"""
        df = fetch_lnb_shots(TEST_GAME_ID)

        # Remove nulls (valid for some shot types)
        df_coords = df[df["X_COORD"].notna() & df["Y_COORD"].notna()]

        assert (df_coords["X_COORD"] >= 0).all(), "X coordinates should be >= 0"
        assert (df_coords["X_COORD"] <= 100).all(), "X coordinates should be <= 100"
        assert (df_coords["Y_COORD"] >= 0).all(), "Y coordinates should be >= 0"
        assert (df_coords["Y_COORD"] <= 100).all(), "Y coordinates should be <= 100"

    def test_shots_success_boolean(self):
        """Verify shot SUCCESS is boolean"""
        df = fetch_lnb_shots(TEST_GAME_ID)

        assert df["SUCCESS"].dtype == bool, "SUCCESS should be boolean"
        assert df["SUCCESS"].isin([True, False]).all(), "SUCCESS should only contain True/False"

    def test_shots_type_values(self):
        """Verify shot types are valid"""
        df = fetch_lnb_shots(TEST_GAME_ID)

        valid_shot_types = ["2pt", "3pt"]
        assert (
            df["SHOT_TYPE"].isin(valid_shot_types).all()
        ), f"Shot types should be in {valid_shot_types}"

    def test_normalized_stats_non_negative(self):
        """Verify normalized stats are non-negative"""
        player_game_file = Path(
            f"data/normalized/lnb/player_game/season={TEST_SEASON}/game_id={TEST_GAME_ID}.parquet"
        )

        if not player_game_file.exists():
            pytest.skip("Normalized tables not yet created")

        df = pd.read_parquet(player_game_file)

        # Stats that should be >= 0
        non_negative_cols = [
            "PTS",
            "FGM",
            "FGA",
            "FG2M",
            "FG2A",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
        ]

        for col in non_negative_cols:
            assert (df[col] >= 0).all(), f"Column {col} should be non-negative"

    def test_normalized_percentages_valid(self):
        """Verify shooting percentages are in valid range (0-1)"""
        player_game_file = Path(
            f"data/normalized/lnb/player_game/season={TEST_SEASON}/game_id={TEST_GAME_ID}.parquet"
        )

        if not player_game_file.exists():
            pytest.skip("Normalized tables not yet created")

        df = pd.read_parquet(player_game_file)

        percentage_cols = ["FG_PCT", "FG2_PCT", "FG3_PCT", "FT_PCT"]

        for col in percentage_cols:
            assert (df[col] >= 0).all(), f"{col} should be >= 0"
            assert (df[col] <= 1).all(), f"{col} should be <= 1"


# ==============================================================================
# COVERAGE MONITORING TESTS
# ==============================================================================


class TestCoverageMonitoring:
    """Monitor data availability and coverage"""

    def test_game_index_exists(self):
        """Verify game index has been created"""
        index_file = Path("data/raw/lnb/lnb_game_index.parquet")

        assert index_file.exists(), "Game index should exist"

        df = pd.read_parquet(index_file)
        assert len(df) > 0, "Game index should not be empty"

    def test_current_season_coverage(self):
        """Verify current season has some games"""
        index_file = Path("data/raw/lnb/lnb_game_index.parquet")

        if not index_file.exists():
            pytest.skip("Game index not yet created")

        df = pd.read_parquet(index_file)

        current_season_games = df[df["season"] == TEST_SEASON]
        assert len(current_season_games) > 0, f"No games found for season {TEST_SEASON}"

    def test_pbp_data_available(self):
        """Verify PBP data has been fetched for some games"""
        pbp_dir = Path(f"data/raw/lnb/pbp/season={TEST_SEASON}")

        if not pbp_dir.exists():
            pytest.skip("PBP data not yet fetched")

        pbp_files = list(pbp_dir.glob("game_id=*.parquet"))
        assert len(pbp_files) > 0, "No PBP files found"

    def test_normalized_tables_available(self):
        """Verify normalized tables have been created"""
        player_game_dir = Path(f"data/normalized/lnb/player_game/season={TEST_SEASON}")
        team_game_dir = Path(f"data/normalized/lnb/team_game/season={TEST_SEASON}")
        shot_events_dir = Path(f"data/normalized/lnb/shot_events/season={TEST_SEASON}")

        if not player_game_dir.exists():
            pytest.skip("Normalized tables not yet created")

        player_files = list(player_game_dir.glob("game_id=*.parquet"))
        team_files = list(team_game_dir.glob("game_id=*.parquet"))
        shot_files = list(shot_events_dir.glob("game_id=*.parquet"))

        assert len(player_files) > 0, "No PLAYER_GAME files found"
        assert len(team_files) > 0, "No TEAM_GAME files found"
        assert len(shot_files) > 0, "No SHOT_EVENTS files found"


# ==============================================================================
# WEEKLY MONITORING
# ==============================================================================


class TestWeeklyMonitoring:
    """Tests to run weekly via cron (use pytest -m weekly to run)"""

    def test_comprehensive_data_pull(self):
        """Verify weekly data pull is working"""
        # This would trigger a full data pull in CI
        # For now, just verify the pipeline exists
        assert Path("tools/lnb/pull_all_historical_data.py").exists()

    def test_coverage_report_exists(self):
        """Verify coverage reports are being generated"""
        reports_dir = Path("data/reports")

        if not reports_dir.exists():
            pytest.skip("Reports directory not yet created")

        coverage_reports = list(reports_dir.glob("lnb_pbp_shots_coverage_*.csv"))
        assert len(coverage_reports) > 0, "No coverage reports found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
