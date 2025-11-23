"""Smoke tests for LNB play-by-play and shot chart fetchers

These are lightweight CI tests that verify the core functionality works.
For comprehensive coverage testing, use tools/lnb/run_lnb_stress_tests.py
"""

import pandas as pd
import pytest

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# Known working game UUID (Nancy vs Saint-Quentin, 2024-25 Play-In)
SMOKE_GAME_ID = "3522345e-3362-11f0-b97d-7be2bdc7a840"

# Expected column sets
PBP_EXPECTED_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "PLAYER_NAME",
    "TEAM_ID",
    "HOME_SCORE",
    "AWAY_SCORE",
    "LEAGUE",
}

SHOTS_EXPECTED_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "PLAYER_NAME",
    "TEAM_ID",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
    "LEAGUE",
}


@pytest.mark.lnb
def test_lnb_play_by_play_smoke():
    """Smoke test: fetch_lnb_play_by_play returns valid data"""
    df = fetch_lnb_play_by_play(SMOKE_GAME_ID)

    # Should return non-empty DataFrame
    assert isinstance(df, pd.DataFrame), "Should return pandas DataFrame"
    assert len(df) > 0, "Should return non-empty DataFrame"

    # Should have required columns
    actual_columns = set(df.columns)
    assert PBP_EXPECTED_COLUMNS.issubset(
        actual_columns
    ), f"Missing columns: {PBP_EXPECTED_COLUMNS - actual_columns}"

    # Data quality checks
    assert df["GAME_ID"].notna().all(), "GAME_ID should not have nulls"
    assert df["EVENT_TYPE"].notna().all(), "EVENT_TYPE should not have nulls"
    assert df["PERIOD_ID"].notna().all(), "PERIOD_ID should not have nulls"
    assert df["LEAGUE"].eq("LNB_PROA").all(), "LEAGUE should be LNB_PROA"

    # Should have multiple event types
    event_types = df["EVENT_TYPE"].nunique()
    assert event_types >= 8, f"Should have at least 8 event types, got {event_types}"

    # Should have reasonable number of events
    assert len(df) >= 200, f"Should have at least 200 events, got {len(df)}"


@pytest.mark.lnb
def test_lnb_shots_smoke():
    """Smoke test: fetch_lnb_shots returns valid data"""
    df = fetch_lnb_game_shots(SMOKE_GAME_ID)

    # Should return non-empty DataFrame
    assert isinstance(df, pd.DataFrame), "Should return pandas DataFrame"
    assert len(df) > 0, "Should return non-empty DataFrame"

    # Should have required columns
    actual_columns = set(df.columns)
    assert SHOTS_EXPECTED_COLUMNS.issubset(
        actual_columns
    ), f"Missing columns: {SHOTS_EXPECTED_COLUMNS - actual_columns}"

    # Data quality checks
    assert df["GAME_ID"].notna().all(), "GAME_ID should not have nulls"
    assert df["SHOT_TYPE"].notna().all(), "SHOT_TYPE should not have nulls"
    assert df["SUCCESS"].notna().all(), "SUCCESS should not have nulls"
    assert df["X_COORD"].notna().all(), "X_COORD should not have nulls"
    assert df["Y_COORD"].notna().all(), "Y_COORD should not have nulls"
    assert df["LEAGUE"].eq("LNB_PROA").all(), "LEAGUE should be LNB_PROA"

    # Coordinate range validation (0-100 scale)
    assert (df["X_COORD"] >= 0).all(), "X_COORD should be >= 0"
    assert (df["X_COORD"] <= 100).all(), "X_COORD should be <= 100"
    assert (df["Y_COORD"] >= 0).all(), "Y_COORD should be >= 0"
    assert (df["Y_COORD"] <= 100).all(), "Y_COORD should be <= 100"

    # Should have both 2pt and 3pt shots
    shot_types = set(df["SHOT_TYPE"].unique())
    assert "2pt" in shot_types, "Should have 2pt shots"
    assert "3pt" in shot_types, "Should have 3pt shots"

    # Should have reasonable number of shots
    assert len(df) >= 50, f"Should have at least 50 shots, got {len(df)}"

    # FG% should be reasonable (10%-80%)
    fg_pct = df["SUCCESS"].mean()
    assert 0.1 <= fg_pct <= 0.8, f"FG% should be 10-80%, got {fg_pct:.1%}"


@pytest.mark.lnb
def test_lnb_pbp_and_shots_consistency():
    """Verify PBP and shots data are consistent for the same game"""
    pbp_df = fetch_lnb_play_by_play(SMOKE_GAME_ID)
    shots_df = fetch_lnb_game_shots(SMOKE_GAME_ID)

    # Should have same game ID
    assert pbp_df["GAME_ID"].iloc[0] == shots_df["GAME_ID"].iloc[0]

    # Shot events in PBP should roughly match shots DataFrame
    # (PBP includes both made and missed shots)
    pbp_shot_events = pbp_df[pbp_df["EVENT_TYPE"].isin(["2pt", "3pt"])]

    # Allow some tolerance (±10%) due to different data structures
    assert abs(len(pbp_shot_events) - len(shots_df)) / len(shots_df) < 0.1, (
        f"PBP shot events ({len(pbp_shot_events)}) should be close to "
        f"shots DataFrame ({len(shots_df)})"
    )


@pytest.mark.lnb
@pytest.mark.slow
def test_lnb_multiple_games():
    """Test multiple games if available (marked as slow test)"""
    # This would require more game UUIDs
    # For now, just test the one we have multiple times to verify caching works
    for _ in range(3):
        pbp_df = fetch_lnb_play_by_play(SMOKE_GAME_ID)
        shots_df = fetch_lnb_game_shots(SMOKE_GAME_ID)

        assert len(pbp_df) > 0
        assert len(shots_df) > 0
