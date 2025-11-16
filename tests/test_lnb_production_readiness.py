"""
Tests for LNB production readiness features.

Tests validation pipeline, API endpoints, and season readiness guards.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_validation_status():
    """Mock validation status JSON for testing."""
    return {
        "run_at": "2025-11-16T21:30:12Z",
        "golden_fixtures_passed": True,
        "golden_failures": 0,
        "api_spotcheck_passed": True,
        "api_discrepancies": 0,
        "consistency_errors": 0,
        "consistency_warnings": 0,
        "seasons": [
            {
                "season": "2023-2024",
                "ready_for_modeling": True,
                "pbp_coverage": 306,
                "pbp_expected": 306,
                "pbp_pct": 100.0,
                "shots_coverage": 306,
                "shots_expected": 306,
                "shots_pct": 100.0,
                "num_critical_issues": 0,
            },
            {
                "season": "2024-2025",
                "ready_for_modeling": False,
                "pbp_coverage": 120,
                "pbp_expected": 240,
                "pbp_pct": 50.0,
                "shots_coverage": 120,
                "shots_expected": 240,
                "shots_pct": 50.0,
                "num_critical_issues": 0,
            },
        ],
        "ready_for_live": True,
    }


@pytest.fixture
def sample_pbp_df():
    """Sample PBP DataFrame for testing."""
    return pd.DataFrame(
        {
            "PERIOD_ID": [1, 1, 1, 2, 2],
            "EVENT_TYPE": ["2pt", "3pt", "2pt", "2pt", "3pt"],
            "HOME_SCORE": [2, 5, 7, 9, 12],
            "AWAY_SCORE": [0, 0, 2, 2, 5],
        }
    )


# ============================================================================
# Unit Tests - Validation Functions
# ============================================================================


def test_is_game_played_with_date():
    """Test is_game_played with historical date."""
    from tools.lnb.bulk_ingest_pbp_shots import is_game_played

    # Past date - should be played
    assert is_game_played("2023-01-01") is True

    # Future date - should not be played
    assert is_game_played("2099-01-01") is False


def test_is_game_played_with_live_status():
    """Test is_game_played with live game status."""
    from tools.lnb.bulk_ingest_pbp_shots import is_game_played

    # Live status - should be playable regardless of date
    assert is_game_played("2099-01-01", status="LIVE") is True
    assert is_game_played("2099-01-01", status="IN_PROGRESS") is True
    assert is_game_played("2099-01-01", status="STARTED") is True

    # Non-live status - date rules apply
    assert is_game_played("2099-01-01", status="SCHEDULED") is False


def test_has_parquet_for_game():
    """Test has_parquet_for_game checks file existence."""
    from tools.lnb.bulk_ingest_pbp_shots import has_parquet_for_game

    test_dir = Path("/tmp/test_lnb_data/pbp")
    test_dir.mkdir(parents=True, exist_ok=True)

    season_dir = test_dir / "season=2023-2024"
    season_dir.mkdir(exist_ok=True)

    # Create a test parquet file
    game_file = season_dir / "game_id=test-uuid-123.parquet"
    game_file.touch()

    try:
        # File exists - should return True
        assert has_parquet_for_game(test_dir, "2023-2024", "test-uuid-123") is True

        # File doesn't exist - should return False
        assert has_parquet_for_game(test_dir, "2023-2024", "nonexistent-uuid") is False

        # Season doesn't exist - should return False
        assert has_parquet_for_game(test_dir, "2099-2100", "test-uuid-123") is False
    finally:
        # Cleanup
        game_file.unlink()
        season_dir.rmdir()
        test_dir.rmdir()


def test_compute_per_game_score_from_pbp(sample_pbp_df):
    """Test compute_per_game_score_from_pbp extracts final scores."""
    from tools.lnb.validate_and_monitor_coverage import compute_per_game_score_from_pbp

    home_score, away_score = compute_per_game_score_from_pbp(sample_pbp_df)

    # Last row has HOME_SCORE=12, AWAY_SCORE=5
    assert home_score == 12
    assert away_score == 5

    # Empty DataFrame
    home_score, away_score = compute_per_game_score_from_pbp(pd.DataFrame())
    assert home_score == 0
    assert away_score == 0


def test_compute_per_game_shot_counts_from_pbp(sample_pbp_df):
    """Test compute_per_game_shot_counts_from_pbp counts field goals."""
    from tools.lnb.validate_and_monitor_coverage import (
        compute_per_game_shot_counts_from_pbp,
    )

    shot_count = compute_per_game_shot_counts_from_pbp(sample_pbp_df)

    # 2 two-pointers + 2 three-pointers + 1 more three-pointer = 5 shots
    assert shot_count == 5

    # Empty DataFrame
    shot_count = compute_per_game_shot_counts_from_pbp(pd.DataFrame())
    assert shot_count == 0


def test_check_season_readiness_ready_season():
    """Test check_season_readiness identifies ready season."""
    from tools.lnb.validate_and_monitor_coverage import check_season_readiness

    disk_data = {"pbp": {"2023-2024": 306}, "shots": {"2023-2024": 306}}
    issues = []  # No errors

    readiness = check_season_readiness("2023-2024", disk_data, issues)

    assert readiness["ready_for_modeling"] is True
    assert readiness["pbp_pct"] == 100.0
    assert readiness["shots_pct"] == 100.0
    assert readiness["num_critical_issues"] == 0


def test_check_season_readiness_not_ready_coverage():
    """Test check_season_readiness identifies incomplete season."""
    from tools.lnb.validate_and_monitor_coverage import check_season_readiness

    disk_data = {"pbp": {"2024-2025": 120}, "shots": {"2024-2025": 120}}
    issues = []

    readiness = check_season_readiness("2024-2025", disk_data, issues)

    assert readiness["ready_for_modeling"] is False  # Only 50% coverage
    assert readiness["pbp_pct"] == 50.0
    assert readiness["shots_pct"] == 50.0


def test_check_season_readiness_not_ready_errors():
    """Test check_season_readiness identifies season with errors."""
    from tools.lnb.validate_and_monitor_coverage import check_season_readiness

    disk_data = {"pbp": {"2023-2024": 306}, "shots": {"2023-2024": 306}}
    issues = [{"season": "2023-2024", "level": "error", "code": "SCHEMA_MISSING"}]

    readiness = check_season_readiness("2023-2024", disk_data, issues)

    assert readiness["ready_for_modeling"] is False  # Has critical error
    assert readiness["num_critical_issues"] == 1


# ============================================================================
# Integration Tests - MCP Season Guards
# ============================================================================


def test_mcp_guard_ready_season(mock_validation_status, tmp_path):
    """Test MCP season guard allows ready season."""
    from src.cbb_data.servers.mcp.tools import _ensure_lnb_season_ready

    # Create temporary validation status file
    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        # Ready season - should not raise
        try:
            _ensure_lnb_season_ready("2023-2024")
        except ValueError:
            pytest.fail("Guard should not raise for ready season")


def test_mcp_guard_not_ready_season(mock_validation_status, tmp_path):
    """Test MCP season guard blocks unready season."""
    from src.cbb_data.servers.mcp.tools import _ensure_lnb_season_ready

    # Create temporary validation status file
    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        # Unready season - should raise ValueError
        with pytest.raises(ValueError, match="NOT READY"):
            _ensure_lnb_season_ready("2024-2025")


def test_mcp_guard_invalid_season(mock_validation_status, tmp_path):
    """Test MCP season guard handles invalid season."""
    from src.cbb_data.servers.mcp.tools import _ensure_lnb_season_ready

    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        # Invalid season - should raise ValueError
        with pytest.raises(ValueError, match="not tracked"):
            _ensure_lnb_season_ready("2099-2100")


def test_mcp_guard_validation_not_run(tmp_path):
    """Test MCP season guard when validation hasn't run."""
    from src.cbb_data.servers.mcp.tools import _ensure_lnb_season_ready

    # No validation file - should raise ValueError
    nonexistent_file = tmp_path / "nonexistent.json"

    with patch("pathlib.Path.__truediv__", return_value=nonexistent_file):
        with pytest.raises(ValueError, match="validation status not found"):
            _ensure_lnb_season_ready("2023-2024")


# ============================================================================
# Integration Tests - API Endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_api_readiness_endpoint_success(mock_validation_status, tmp_path):
    """Test /lnb/readiness endpoint returns validation status."""
    from src.cbb_data.api.rest_api.routes import lnb_readiness_check

    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        response = await lnb_readiness_check()

        assert response.any_season_ready is True
        assert "2023-2024" in response.ready_seasons
        assert "2024-2025" not in response.ready_seasons
        assert len(response.seasons) == 2


@pytest.mark.asyncio
async def test_api_readiness_endpoint_no_validation(tmp_path):
    """Test /lnb/readiness endpoint when validation not run."""
    from fastapi import HTTPException

    from src.cbb_data.api.rest_api.routes import lnb_readiness_check

    nonexistent_file = tmp_path / "nonexistent.json"

    with patch("pathlib.Path.__truediv__", return_value=nonexistent_file):
        with pytest.raises(HTTPException) as exc_info:
            await lnb_readiness_check()

        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_api_validation_status_endpoint(mock_validation_status, tmp_path):
    """Test /lnb/validation-status endpoint."""
    from src.cbb_data.api.rest_api.routes import lnb_validation_status

    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        response = await lnb_validation_status()

        assert response.golden_fixtures_passed is True
        assert response.api_spotcheck_passed is True
        assert response.consistency_errors == 0
        assert response.ready_for_live is True


def test_api_require_lnb_season_ready_guard_ready(mock_validation_status, tmp_path):
    """Test require_lnb_season_ready guard allows ready season."""
    from src.cbb_data.api.rest_api.routes import require_lnb_season_ready

    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        # Ready season - should not raise
        try:
            require_lnb_season_ready("2023-2024")
        except Exception:
            pytest.fail("Guard should not raise for ready season")


def test_api_require_lnb_season_ready_guard_not_ready(mock_validation_status, tmp_path):
    """Test require_lnb_season_ready guard blocks unready season."""
    from fastapi import HTTPException

    from src.cbb_data.api.rest_api.routes import require_lnb_season_ready

    validation_file = tmp_path / "lnb_last_validation.json"
    with open(validation_file, "w") as f:
        json.dump(mock_validation_status, f)

    with patch("pathlib.Path.__truediv__", return_value=validation_file):
        # Unready season - should raise 409 Conflict
        with pytest.raises(HTTPException) as exc_info:
            require_lnb_season_ready("2024-2025")

        assert exc_info.value.status_code == 409
