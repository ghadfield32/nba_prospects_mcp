"""Basketball Africa League (BAL) Fetcher

Official Basketball Africa League data via FIBA LiveStats v7 Direct HTTP Client.

BAL is Africa's premier professional basketball league, jointly operated by
FIBA and the NBA with 12 teams from across Africa.

Key Features:
- Uses direct FIBA LiveStats HTTP client
- Comprehensive data (schedules, box scores, play-by-play, shots)
- Historical data back to 2021 inaugural season
- Rate limit: 2 req/sec (shared with all FIBA leagues)

Data Granularities:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores)
- team_game: ✅ Full (team box scores)
- pbp: ✅ Full (play-by-play with timestamps)
- shots: ✅ Full (X/Y coordinates, shot types)
- player_season: ✅ Aggregated (from player_game)
- team_season: ✅ Aggregated (from team_game)

Competition Structure:
- 12 teams from 12 African countries
- Season format: Group stage → Playoffs
- Typical season: March-May
- Finals hosted in different African city each year

Historical Context:
- Founded: 2021 (first NBA-backed league outside North America)
- Champions: Zamalek (2021), US Monastir (2022), Al Ahly (2023), Petro de Luanda (2024)
- Purpose: Develop African basketball talent and provide NBA pathway

Documentation: https://thebal.com/

Implementation Status:
✅ COMPLETE - Fully functional via direct FIBA LiveStats HTTP client

Technical Notes:
- Competition code: "BAL"
- Direct HTTP client bypasses euroleague-api limitation
- High strategic importance (NBA partnership, emerging market)
"""

from __future__ import annotations

import pandas as pd

from .fiba_livestats_direct import (
    fetch_fiba_direct_box_score,
    fetch_fiba_direct_play_by_play,
    fetch_fiba_direct_schedule,
    fetch_fiba_direct_shot_chart,
)

# BAL competition code
BAL_COMPETITION_CODE = "BAL"


def fetch_bal_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch Basketball Africa League schedule

    Args:
        season: Season year as integer (e.g., 2024 for 2024 season)
        phase: Competition phase ("RS" = Regular Season, "PO" = Playoffs)
        round_start: Starting round number (1-indexed)
        round_end: Ending round number (None = fetch all remaining rounds)

    Returns:
        DataFrame with game schedule

    Example:
        >>> # Fetch BAL 2024 season
        >>> schedule = fetch_bal_schedule(2024)
        >>> print(f"Fetched {len(schedule)} BAL games")
    """
    return fetch_fiba_direct_schedule(
        competition=BAL_COMPETITION_CODE,
        season=season,
        phase=phase,
        round_start=round_start,
        round_end=round_end,
    )


def fetch_bal_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL box score for a game

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with player box scores

    Example:
        >>> box_score = fetch_bal_box_score(2024, 1)
        >>> top_scorers = box_score.nlargest(5, "PTS")
    """
    return fetch_fiba_direct_box_score(
        competition=BAL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_bal_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL play-by-play data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with play-by-play events
    """
    return fetch_fiba_direct_play_by_play(
        competition=BAL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_bal_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL shot chart data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with shot data
    """
    return fetch_fiba_direct_shot_chart(
        competition=BAL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )
