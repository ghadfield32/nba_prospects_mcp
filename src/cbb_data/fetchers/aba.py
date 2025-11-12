"""ABA League (Adriatic League) Fetcher

Official ABA League data via FIBA LiveStats v7 Direct HTTP Client.

ABA League is a premier regional basketball league featuring top clubs from
the Balkans and Eastern Europe (Serbia, Croatia, Slovenia, Montenegro, Bosnia, etc.).

Key Features:
- Uses direct FIBA LiveStats HTTP client
- Comprehensive data (schedules, box scores, play-by-play, shots)
- Historical data back to 2001 founding
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
- 14 teams from 6-7 countries
- Regular season: Double round-robin
- Playoffs: Top 8 teams advance
- Finals: Best-of-5 series
- Typical season: October-June

Historical Context:
- Founded: 2001 (originally "Goodyear League")
- Prominent teams: Crvena Zvezda, Partizan, Olimpija, Cedevita, Budućnost
- High competition level: Many players move to EuroLeague from ABA
- Regional importance: Premier league for Balkan basketball

Documentation: https://www.adriaticbasket.com/

Implementation Status:
✅ COMPLETE - Fully functional via direct FIBA LiveStats HTTP client

Technical Notes:
- Competition code: "ABA"
- Direct HTTP client bypasses euroleague-api limitation
- Regional powerhouse: Develops EuroLeague-caliber talent
"""

from __future__ import annotations

import pandas as pd

from .fiba_livestats_direct import (
    fetch_fiba_direct_box_score,
    fetch_fiba_direct_play_by_play,
    fetch_fiba_direct_schedule,
    fetch_fiba_direct_shot_chart,
)

# ABA League competition code
ABA_COMPETITION_CODE = "ABA"


def fetch_aba_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch ABA League schedule

    Args:
        season: Season year as integer (e.g., 2024 for 2024-25 season)
        phase: Competition phase ("RS" = Regular Season, "PO" = Playoffs)
        round_start: Starting round number (1-indexed)
        round_end: Ending round number (None = fetch all remaining rounds)

    Returns:
        DataFrame with game schedule

    Example:
        >>> # Fetch ABA League 2024-25 season, rounds 1-10
        >>> schedule = fetch_aba_schedule(2024, phase="RS", round_start=1, round_end=10)
        >>> print(f"Fetched {len(schedule)} ABA games")
    """
    return fetch_fiba_direct_schedule(
        competition=ABA_COMPETITION_CODE,
        season=season,
        phase=phase,
        round_start=round_start,
        round_end=round_end,
    )


def fetch_aba_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA League box score for a game

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with player box scores

    Example:
        >>> box_score = fetch_aba_box_score(2024, 100)
        >>> top_scorers = box_score.nlargest(5, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
    """
    return fetch_fiba_direct_box_score(
        competition=ABA_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_aba_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA League play-by-play data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with play-by-play events
    """
    return fetch_fiba_direct_play_by_play(
        competition=ABA_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_aba_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA League shot chart data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with shot data
    """
    return fetch_fiba_direct_shot_chart(
        competition=ABA_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )
