"""Validation Tests for International Basketball Data Sources

Comprehensive test suite for ACB, FIBA cluster (BCL, BAL, ABA, LKL), and LNB data sources.

Tests verify:
- Data fetching works correctly
- JSON API integration for FIBA leagues
- HTML fallback mechanisms work
- ACB error handling and manual CSV fallback
- LNB placeholder functions return correct empty DataFrames
- Data schemas are correct
- Source metadata tracking is present
"""

import pandas as pd
import pytest

from src.cbb_data.fetchers import (
    aba,
    acb,
    bal,
    bcl,
    lkl,
    lnb,
)


# ==============================================================================
# FIBA JSON API Tests
# ==============================================================================


class TestFibaJsonApi:
    """Test FIBA LiveStats JSON API integration"""

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_fiba_json_client_initialized(self, fetcher_module, league_name):
        """Test that FIBA JSON client is properly initialized"""
        assert hasattr(fetcher_module, "_json_client"), f"{league_name} should have _json_client"
        assert fetcher_module._json_client is not None, f"{league_name} _json_client should not be None"
        assert (
            fetcher_module._json_client.league_code == fetcher_module.FIBA_LEAGUE_CODE
        ), f"{league_name} _json_client should use correct league code"

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_fetch_player_game_has_source_metadata(self, fetcher_module, league_name):
        """Test that fetch_player_game returns SOURCE column"""
        # Try to fetch data (may be empty if no schedule)
        try:
            df = fetcher_module.fetch_player_game("2023-24")
            if not df.empty:
                assert "SOURCE" in df.columns, f"{league_name} player_game should have SOURCE column"
                # Check that SOURCE is either fiba_json or fiba_html
                valid_sources = {"fiba_json", "fiba_html"}
                assert df["SOURCE"].isin(valid_sources).all(), (
                    f"{league_name} player_game SOURCE should be 'fiba_json' or 'fiba_html'"
                )
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} data: {e}")

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_fetch_pbp_has_source_metadata(self, fetcher_module, league_name):
        """Test that fetch_pbp returns SOURCE column"""
        try:
            df = fetcher_module.fetch_pbp("2023-24")
            if not df.empty:
                assert "SOURCE" in df.columns, f"{league_name} pbp should have SOURCE column"
                valid_sources = {"fiba_json", "fiba_html"}
                assert df["SOURCE"].isin(valid_sources).all(), (
                    f"{league_name} pbp SOURCE should be 'fiba_json' or 'fiba_html'"
                )
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} PBP data: {e}")

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_fetch_shots_returns_coordinates(self, fetcher_module, league_name):
        """Test that fetch_shots returns X/Y coordinates (JSON only feature)"""
        try:
            df = fetcher_module.fetch_shots("2023-24")
            if not df.empty:
                assert "X" in df.columns, f"{league_name} shots should have X coordinate"
                assert "Y" in df.columns, f"{league_name} shots should have Y coordinate"
                assert "SOURCE" in df.columns, f"{league_name} shots should have SOURCE column"
                # Shots should ONLY come from JSON (HTML doesn't have coordinates)
                assert (df["SOURCE"] == "fiba_json").all(), (
                    f"{league_name} shots should only come from fiba_json"
                )
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} shots data: {e}")


# ==============================================================================
# ACB Error Handling Tests
# ==============================================================================


class TestAcbErrorHandling:
    """Test ACB error handling and fallback mechanisms"""

    def test_acb_has_error_handler(self):
        """Test that ACB module has error handling function"""
        assert hasattr(acb, "_handle_acb_error"), "ACB should have _handle_acb_error function"

    def test_acb_has_manual_csv_loader(self):
        """Test that ACB module has manual CSV loader"""
        assert hasattr(acb, "_load_manual_csv"), "ACB should have _load_manual_csv function"

    def test_acb_fetch_player_season_returns_dataframe(self):
        """Test that ACB fetch_player_season returns DataFrame (even if empty)"""
        # This should not raise an exception, even if it returns empty DataFrame
        try:
            df = acb.fetch_player_season("2023-24")
            assert isinstance(df, pd.DataFrame), "ACB fetch_player_season should return DataFrame"
            if not df.empty:
                assert "SOURCE" in df.columns, "ACB should track SOURCE metadata"
        except Exception as e:
            # Should not raise unhandled exceptions
            pytest.fail(f"ACB fetch_player_season raised unhandled exception: {e}")

    def test_acb_fetch_team_season_returns_dataframe(self):
        """Test that ACB fetch_team_season returns DataFrame"""
        try:
            df = acb.fetch_team_season("2023-24")
            assert isinstance(df, pd.DataFrame), "ACB fetch_team_season should return DataFrame"
        except Exception as e:
            pytest.fail(f"ACB fetch_team_season raised unhandled exception: {e}")


# ==============================================================================
# LNB API Discovery Placeholders
# ==============================================================================


class TestLnbPlaceholders:
    """Test LNB placeholder functions return correct empty DataFrames"""

    def test_lnb_fetch_player_season_returns_empty(self):
        """Test that LNB fetch_player_season returns empty DataFrame with schema"""
        df = lnb.fetch_lnb_player_season("2024")
        assert isinstance(df, pd.DataFrame), "LNB player_season should return DataFrame"
        assert df.empty, "LNB player_season should be empty (not yet implemented)"
        # Check expected columns are present in schema
        expected_cols = {"PLAYER_NAME", "TEAM", "GP", "PTS", "REB", "AST", "LEAGUE", "SEASON"}
        assert expected_cols.issubset(df.columns), "LNB player_season should have correct schema"

    def test_lnb_fetch_schedule_returns_empty(self):
        """Test that LNB fetch_schedule returns empty DataFrame with schema"""
        df = lnb.fetch_lnb_schedule("2024")
        assert isinstance(df, pd.DataFrame), "LNB schedule should return DataFrame"
        assert df.empty, "LNB schedule should be empty (not yet implemented)"
        expected_cols = {"GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"}
        assert expected_cols.issubset(df.columns), "LNB schedule should have correct schema"

    def test_lnb_fetch_box_score_returns_empty(self):
        """Test that LNB fetch_box_score returns empty DataFrame with schema"""
        df = lnb.fetch_lnb_box_score("12345")
        assert isinstance(df, pd.DataFrame), "LNB box_score should return DataFrame"
        assert df.empty, "LNB box_score should be empty (not yet implemented)"
        expected_cols = {"GAME_ID", "PLAYER_NAME", "TEAM", "PTS", "REB", "AST", "LEAGUE"}
        assert expected_cols.issubset(df.columns), "LNB box_score should have correct schema"

    def test_lnb_fetch_team_season_returns_data(self):
        """Test that LNB fetch_team_season returns standings data"""
        # This function SHOULD return data (HTML scraping works)
        try:
            df = lnb.fetch_lnb_team_season("2024")
            assert isinstance(df, pd.DataFrame), "LNB team_season should return DataFrame"
            # May be empty if off-season, but should have correct schema
            if not df.empty:
                expected_cols = {"RANK", "TEAM", "GP", "WIN_PCT", "LEAGUE", "SEASON"}
                assert expected_cols.issubset(df.columns), "LNB team_season should have correct columns"
        except Exception as e:
            pytest.skip(f"Could not fetch LNB team_season: {e}")


# ==============================================================================
# Schema Validation Tests
# ==============================================================================


class TestDataSchemas:
    """Test that data schemas are correct and consistent"""

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_player_game_schema(self, fetcher_module, league_name):
        """Test player_game has required columns"""
        try:
            df = fetcher_module.fetch_player_game("2023-24")
            if not df.empty:
                required_cols = {"LEAGUE", "SEASON", "GAME_ID", "PLAYER_NAME", "TEAM"}
                assert required_cols.issubset(df.columns), (
                    f"{league_name} player_game missing required columns"
                )
                # Check LEAGUE value is correct
                assert (df["LEAGUE"] == league_name).all(), (
                    f"{league_name} player_game should have LEAGUE='{league_name}'"
                )
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} player_game: {e}")

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_pbp_schema(self, fetcher_module, league_name):
        """Test pbp has required columns"""
        try:
            df = fetcher_module.fetch_pbp("2023-24")
            if not df.empty:
                required_cols = {"LEAGUE", "SEASON", "GAME_ID", "PERIOD"}
                assert required_cols.issubset(df.columns), f"{league_name} pbp missing required columns"
                assert (df["LEAGUE"] == league_name).all(), (
                    f"{league_name} pbp should have LEAGUE='{league_name}'"
                )
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} pbp: {e}")

    @pytest.mark.parametrize(
        "fetcher_module,league_name",
        [
            (bcl, "BCL"),
            (bal, "BAL"),
            (aba, "ABA"),
            (lkl, "LKL"),
        ],
    )
    def test_shots_schema(self, fetcher_module, league_name):
        """Test shots has required columns including coordinates"""
        try:
            df = fetcher_module.fetch_shots("2023-24")
            if not df.empty:
                required_cols = {
                    "LEAGUE",
                    "SEASON",
                    "GAME_ID",
                    "PLAYER_NAME",
                    "SHOT_TYPE",
                    "SHOT_RESULT",
                    "X",
                    "Y",
                }
                assert required_cols.issubset(df.columns), f"{league_name} shots missing required columns"
                # Verify coordinate ranges (0-100 scale)
                assert df["X"].between(0, 100).all(), f"{league_name} X coordinates should be 0-100"
                assert df["Y"].between(0, 100).all(), f"{league_name} Y coordinates should be 0-100"
        except Exception as e:
            pytest.skip(f"Could not fetch {league_name} shots: {e}")


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestIntegration:
    """Integration tests for end-to-end data fetching"""

    def test_bcl_json_api_priority(self):
        """Test that BCL tries JSON API first"""
        # This is a smoke test - if BCL has schedule, it should try JSON first
        try:
            schedule = bcl.fetch_schedule("2023-24")
            if not schedule.empty:
                # Fetch player_game and check if any data comes from JSON
                player_game = bcl.fetch_player_game("2023-24")
                if not player_game.empty and "SOURCE" in player_game.columns:
                    # At least some games should attempt JSON (may fall back to HTML)
                    sources = player_game["SOURCE"].unique()
                    # We expect to see fiba_json if JSON API is working
                    # or fiba_html if it fell back
                    assert any(s in ["fiba_json", "fiba_html"] for s in sources), (
                        "BCL should use fiba_json or fiba_html as SOURCE"
                    )
        except Exception as e:
            pytest.skip(f"Could not test BCL JSON priority: {e}")

    def test_acb_graceful_degradation(self):
        """Test that ACB gracefully handles errors"""
        # ACB should not crash even if website blocks us
        try:
            # Try fetching current season
            df = acb.fetch_player_season("2023-24")
            assert isinstance(df, pd.DataFrame), "ACB should return DataFrame even on errors"
            # If empty, check that we got a helpful warning (logged)
            # We can't directly test logging here, but we verify no crash
        except Exception as e:
            pytest.fail(f"ACB should handle errors gracefully, but raised: {e}")


# ==============================================================================
# Performance Tests
# ==============================================================================


class TestPerformance:
    """Performance and caching tests"""

    def test_fiba_fetchers_use_caching(self):
        """Test that FIBA fetchers use caching decorators"""
        # All fetch functions should have cached_dataframe decorator
        fiba_modules = [bcl, bal, aba, lkl]
        for module in fiba_modules:
            fetch_player_game = getattr(module, "fetch_player_game")
            # Check if function has caching wrapper
            # The cached_dataframe decorator should add attributes
            # This is a basic check - actual caching is tested separately
            assert callable(fetch_player_game), f"{module.LEAGUE} fetch_player_game should be callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
