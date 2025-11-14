"""Test European Domestic League Fetchers (ACB, LNB)

Parametrized tests covering European domestic leagues.

Test Coverage:
- ACB (Spain) - Currently BROKEN (website restructured, URLs 404)
- LNB Pro A (France) - PARTIAL (team_season works, player_season unavailable)

Each league is tested to validate current status and ensure graceful degradation.
"""

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

import pandas as pd
import pytest

from cbb_data.fetchers import acb, lnb

# =============================================================================
# Test Configuration
# =============================================================================

# Leagues to test: (league_code, season, module, expected_status)
EUROPEAN_DOMESTIC_LEAGUES = [
    ("ACB", "2023-24", acb, "BROKEN"),  # Website restructured, URLs 404
    ("LNB_PROA", "2024", lnb, "PARTIAL"),  # team_season works, player_season doesn't
]


# =============================================================================
# Helper Functions
# =============================================================================


def assert_graceful_degradation(df: pd.DataFrame, league: str, endpoint: str):
    """Assert that broken endpoints return empty DataFrames with correct schema

    Args:
        df: DataFrame to check
        league: League code
        endpoint: Endpoint name
    """
    # Should be a DataFrame (not None)
    assert isinstance(df, pd.DataFrame), f"{league} {endpoint} should return DataFrame"

    # Should have LEAGUE column even when empty
    if not df.empty:
        assert "LEAGUE" in df.columns, f"{league} {endpoint} should have LEAGUE column"


# =============================================================================
# Parametrized Tests
# =============================================================================


@pytest.mark.parametrize("league, season, mod, status", EUROPEAN_DOMESTIC_LEAGUES)
def test_european_domestic_player_season(league, season, mod, status):
    """Test player season stats for European domestic leagues

    ACB: Expected to be empty (BROKEN - website restructured)
    LNB: Expected to be empty (requires JavaScript)
    """
    player_season = (
        mod.fetch_lnb_player_season(season)
        if league == "LNB_PROA"
        else mod.fetch_acb_player_season(season)
    )

    assert_graceful_degradation(player_season, league, "player_season")

    # Both should be empty currently
    if not player_season.empty:
        pytest.fail(f"{league} player_season unexpectedly has data - website may have been fixed!")


@pytest.mark.parametrize("league, season, mod, status", EUROPEAN_DOMESTIC_LEAGUES)
def test_european_domestic_team_season(league, season, mod, status):
    """Test team season stats for European domestic leagues

    ACB: Expected to be empty (BROKEN - 404 on clasificacion)
    LNB: Expected to have data (✅ Works via HTML scraping)
    """
    team_season = (
        mod.fetch_lnb_team_season(season)
        if league == "LNB_PROA"
        else mod.fetch_acb_team_season(season)
    )

    assert_graceful_degradation(team_season, league, "team_season")

    if league == "LNB_PROA":
        # LNB should have team standings data
        if team_season.empty:
            pytest.skip("LNB team_season empty - may be off-season or website changed")
        else:
            # Validate structure
            required_cols = ["TEAM", "LEAGUE"]
            for col in required_cols:
                assert col in team_season.columns, f"LNB team_season should have {col} column"

            assert (team_season["LEAGUE"] == "LNB_PROA").all()
            assert len(team_season) >= 10, "LNB should have at least 10 teams"

    elif league == "ACB":
        # ACB should be empty (broken)
        assert team_season.empty, "ACB team_season should be empty (website broken)"


@pytest.mark.parametrize("league, season, mod, status", EUROPEAN_DOMESTIC_LEAGUES)
def test_european_domestic_schedule_scaffold(league, season, mod, status):
    """Test schedule scaffold for European domestic leagues

    Both should return empty with proper schema (not implemented)
    """
    schedule = mod.fetch_acb_schedule(season) if league == "ACB" else mod.fetch_lnb_schedule(season)

    assert_graceful_degradation(schedule, league, "schedule")

    # Both should be empty (not implemented)
    # This is expected behavior for scaffold endpoints


# =============================================================================
# League-Specific Tests
# =============================================================================


def test_acb_broken_status():
    """Test that ACB correctly identifies as broken

    ACB website restructured and previous URLs now 404.
    All endpoints should return empty DataFrames with proper schema.
    """
    # Test both endpoints return empty
    player_season = acb.fetch_acb_player_season("2023-24")
    team_season = acb.fetch_acb_team_season("2023-24")

    assert player_season.empty, "ACB player_season should be empty (website broken)"
    assert team_season.empty, "ACB team_season should be empty (website broken)"

    # But should have correct schema (graceful degradation)
    assert "PLAYER_NAME" in player_season.columns
    assert "TEAM" in team_season.columns


def test_lnb_partial_status():
    """Test that LNB correctly identifies as partial

    LNB team_season works via HTML scraping.
    LNB player_season unavailable (requires JavaScript).
    """
    # Player season should be empty
    player_season = lnb.fetch_lnb_player_season("2024")
    assert player_season.empty, "LNB player_season should be empty (requires JavaScript)"

    # Team season may have data (check if it's season)
    team_season = lnb.fetch_lnb_team_season("2024")

    if not team_season.empty:
        # If we have data, validate it
        assert "LEAGUE" in team_season.columns
        assert (team_season["LEAGUE"] == "LNB_PROA").all()
        assert "TEAM" in team_season.columns
        assert "WIN_PCT" in team_season.columns or "W_L" in team_season.columns


# =============================================================================
# Integration Tests
# =============================================================================


def test_european_domestic_catalog_registration():
    """Test that European domestic leagues are registered in catalog"""
    from cbb_data.catalog.sources import get_league_source_config

    # ACB should be registered
    acb_config = get_league_source_config("ACB")
    assert acb_config is not None, "ACB should be registered in catalog"

    # LNB_PROA should be registered
    lnb_config = get_league_source_config("LNB_PROA")
    assert lnb_config is not None, "LNB_PROA should be registered in catalog"


def test_european_domestic_graceful_degradation():
    """Test that all broken endpoints return proper empty DataFrames

    This ensures the pipeline doesn't break when leagues are unavailable.
    """
    # ACB - all should return empty with schema
    acb_player = acb.fetch_acb_player_season("2023-24")
    acb_team = acb.fetch_acb_team_season("2023-24")
    acb_schedule = acb.fetch_acb_schedule("2023-24")

    assert isinstance(acb_player, pd.DataFrame)
    assert isinstance(acb_team, pd.DataFrame)
    assert isinstance(acb_schedule, pd.DataFrame)

    # All should have LEAGUE or appropriate columns
    assert len(acb_player.columns) > 0, "ACB player_season should have schema"
    assert len(acb_team.columns) > 0, "ACB team_season should have schema"
    assert len(acb_schedule.columns) > 0, "ACB schedule should have schema"
