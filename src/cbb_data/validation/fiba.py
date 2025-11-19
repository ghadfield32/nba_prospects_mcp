"""FIBA Cluster Season Readiness Validation

Provides readiness checking for all 4 FIBA cluster leagues:
- LKL (Lithuania)
- ABA (Adriatic)
- BAL (Africa)
- BCL (Champions)

Usage:
    from cbb_data.validation.fiba import require_fiba_season_ready

    # In MCP tool or API endpoint
    require_fiba_season_ready("LKL", "2023-24")
    # Raises ValueError if not ready, returns None if ready
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Validation file location
VALIDATION_FILE = Path("data/raw/fiba/fiba_last_validation.json")

# Valid FIBA leagues
VALID_LEAGUES = ["LKL", "ABA", "BAL", "BCL"]


def require_fiba_season_ready(
    league: str,
    season: str,
    raise_on_not_ready: bool = True,
) -> dict[str, Any] | None:
    """Require that a FIBA league season is ready for data access

    Checks the validation status file to ensure:
    - Season has >= 95% PBP coverage
    - Season has >= 95% shots coverage
    - No critical errors

    Args:
        league: League code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")
        raise_on_not_ready: If True, raise ValueError when not ready (default)
                           If False, return readiness dict instead

    Returns:
        None if ready and raise_on_not_ready=True
        Readiness dict if raise_on_not_ready=False

    Raises:
        ValueError: If league/season is not ready for access (when raise_on_not_ready=True)

    Example:
        >>> # In MCP tool
        >>> require_fiba_season_ready("LKL", "2023-24")
        >>> # Proceed with data access...
        >>>
        >>> # In validation script
        >>> status = require_fiba_season_ready("LKL", "2023-24", raise_on_not_ready=False)
        >>> if not status["ready_for_modeling"]:
        >>>     print(f"Not ready: {status['reason']}")
    """
    # Validate league
    if league not in VALID_LEAGUES:
        raise ValueError(
            f"Invalid FIBA league: {league}. " f"Valid leagues: {', '.join(VALID_LEAGUES)}"
        )

    # Check if validation file exists
    if not VALIDATION_FILE.exists():
        error_msg = (
            "FIBA validation status not found. Please run validation first:\n"
            "  python tools/fiba/validate_and_monitor_coverage.py"
        )
        if raise_on_not_ready:
            raise ValueError(error_msg)
        return {
            "league": league,
            "season": season,
            "ready_for_modeling": False,
            "reason": "No validation file",
        }

    # Load validation data
    try:
        with open(VALIDATION_FILE) as f:
            validation_data = json.load(f)
    except Exception as e:
        error_msg = f"Failed to load FIBA validation file: {e}"
        if raise_on_not_ready:
            raise ValueError(error_msg) from e
        return {
            "league": league,
            "season": season,
            "ready_for_modeling": False,
            "reason": f"Validation file error: {e}",
        }

    # Find matching league/season
    season_data = next(
        (
            s
            for s in validation_data.get("leagues", [])
            if s.get("league") == league and s.get("season") == season
        ),
        None,
    )

    if not season_data:
        error_msg = (
            f"Season '{season}' not found in FIBA validation for {league}. "
            f"Available seasons: {[s['season'] for s in validation_data.get('leagues', []) if s.get('league') == league]}"
        )
        if raise_on_not_ready:
            raise ValueError(error_msg)
        return {
            "league": league,
            "season": season,
            "ready_for_modeling": False,
            "reason": "Season not in validation file",
        }

    # Check readiness
    if not season_data.get("ready_for_modeling", False):
        reason = season_data.get("reason", "Unknown reason")
        pbp_pct = season_data.get("pbp_coverage_pct", 0) * 100
        shots_pct = season_data.get("shots_coverage_pct", 0) * 100

        error_msg = (
            f"Season '{season}' for {league} is NOT READY for data access.\n"
            f"  Reason: {reason}\n"
            f"  PBP coverage: {pbp_pct:.1f}%\n"
            f"  Shots coverage: {shots_pct:.1f}%\n"
            f"\n"
            f"To make this season ready:\n"
            f"  1. Run browser scraping: python tools/fiba/test_browser_scraping.py --league {league}\n"
            f"  2. Fetch data with Playwright: fetch_shot_chart('{season}', use_browser=True)\n"
            f"  3. Re-run validation: python tools/fiba/validate_and_monitor_coverage.py"
        )

        if raise_on_not_ready:
            raise ValueError(error_msg)
        return season_data

    # Season is ready
    if raise_on_not_ready:
        return None
    return season_data


def get_fiba_validation_status() -> dict[str, Any]:
    """Get current FIBA validation status for all leagues

    Returns:
        Validation status dict

    Raises:
        FileNotFoundError: If validation file doesn't exist
    """
    if not VALIDATION_FILE.exists():
        raise FileNotFoundError(
            f"FIBA validation file not found: {VALIDATION_FILE}\n"
            f"Run: python tools/fiba/validate_and_monitor_coverage.py"
        )

    with open(VALIDATION_FILE) as f:
        return json.load(f)


def check_fiba_league_ready(league: str, season: str) -> bool:
    """Quick boolean check if FIBA league/season is ready

    Args:
        league: League code (LKL, ABA, BAL, BCL)
        season: Season string

    Returns:
        True if ready, False otherwise
    """
    try:
        status = require_fiba_season_ready(league, season, raise_on_not_ready=False)
        return status.get("ready_for_modeling", False) if status else False
    except Exception:
        return False
