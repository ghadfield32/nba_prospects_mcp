"""Basketball Champions League (BCL) Fetcher

Official Basketball Champions League data via FIBA LiveStats v7 Direct HTTP Client.

BCL is Europe's third-tier club competition (after EuroLeague and EuroCup),
organized by FIBA Europe with 32+ teams from across Europe.

Key Features:
- Uses direct FIBA LiveStats HTTP client (bypasses euroleague-api limitation)
- Comprehensive data (schedules, box scores, play-by-play, shots)
- Historical data back to 2016-17 season
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
- Regular Season: 32 teams, 8 groups of 4
- Top 16: Single-elimination knockout rounds
- Final Four: Semi-finals and final
- Typical season: October-May

Historical Context:
- Founded: 2016 (replaced FIBA EuroChallenge)
- Champions: AEK Athens (2018, 2020), Virtus Bologna (2019),
  Hereda San Pablo Burgos (2021, 2022, 2023), Unicaja (2024)

Documentation: https://www.championsleague.basketball/

Implementation Status:
✅ COMPLETE - Fully functional via direct FIBA LiveStats HTTP client

Technical Notes:
- Competition code: "L"
- Switched from euroleague-api (limited to E/U) to direct HTTP client
- Same JSON response structure, better league coverage
"""

from __future__ import annotations

import pandas as pd

from .fiba_livestats_direct import (
    fetch_fiba_direct_box_score,
    fetch_fiba_direct_play_by_play,
    fetch_fiba_direct_schedule,
    fetch_fiba_direct_shot_chart,
)

# BCL competition code
BCL_COMPETITION_CODE = "L"


def fetch_bcl_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch Basketball Champions League schedule

    Args:
        season: Season year as integer (e.g., 2024 for 2024-25 season)
        phase: Competition phase ("RS" = Regular Season, "PO" = Playoffs, "FF" = Final Four)
        round_start: Starting round number (1-indexed)
        round_end: Ending round number (None = fetch all remaining rounds)

    Returns:
        DataFrame with game schedule

    Columns:
        - SEASON: Season year
        - ROUND: Round number
        - GAME_CODE: Unique game identifier
        - GAME_DATE: Game date/time
        - HOME_TEAM_CODE: Home team code
        - HOME_TEAM: Home team name
        - AWAY_TEAM_CODE: Away team code
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (null for upcoming games)
        - AWAY_SCORE: Away team score (null for upcoming games)
        - PHASE_TYPE: Season phase (RS/PO/FF)
        - LEAGUE: "Basketball Champions League"

    Example:
        >>> # Fetch BCL 2024 season, rounds 1-10
        >>> schedule = fetch_bcl_schedule(2024, phase="RS", round_start=1, round_end=10)
        >>> print(f"Fetched {len(schedule)} BCL games")

        >>> # Fetch all playoffs
        >>> playoffs = fetch_bcl_schedule(2024, phase="PO")
    """
    return fetch_fiba_direct_schedule(
        competition=BCL_COMPETITION_CODE,
        season=season,
        phase=phase,
        round_start=round_start,
        round_end=round_end,
    )


def fetch_bcl_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL box score for a game

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with player box scores

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_CODE: Team code
        - TEAM: Team name
        - IS_STARTER: Starting 5 flag (True/False)
        - MIN: Minutes played
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A, FG2_PCT: 2-point field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - PLUS_MINUS: Plus/minus
        - PIR: Performance Index Rating (FIBA metric)
        - LEAGUE: "Basketball Champions League"

    Example:
        >>> box_score = fetch_bcl_box_score(2024, 1)
        >>> top_scorers = box_score.nlargest(5, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
    """
    return fetch_fiba_direct_box_score(
        competition=BCL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_bcl_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL play-by-play data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with play-by-play events

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAY_NUMBER: Play sequence number
        - PERIOD: Quarter/period (1-4, 5+ for OT)
        - CLOCK: Game clock (MM:SS)
        - PLAY_TYPE: Play type (shot, foul, turnover, etc.)
        - PLAY_INFO: Detailed play description
        - TEAM_CODE: Team code
        - TEAM: Team name
        - PLAYER_ID: Player ID
        - PLAYER: Player name
        - HOME_SCORE: Home team score after play
        - AWAY_SCORE: Away team score after play
        - LEAGUE: "Basketball Champions League"

    Example:
        >>> pbp = fetch_bcl_play_by_play(2024, 1)
        >>> scoring_plays = pbp[pbp["PLAY_TYPE"].str.contains("shot|basket", case=False, na=False)]
        >>> print(f"{len(scoring_plays)} scoring plays")
    """
    return fetch_fiba_direct_play_by_play(
        competition=BCL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )


def fetch_bcl_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL shot chart data

    Args:
        season: Season year (e.g., 2024)
        game_code: Game code/ID from schedule

    Returns:
        DataFrame with shot data

    Columns:
        - SEASON: Season year
        - GAME_CODE: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_CODE: Team code
        - TEAM: Team name
        - SHOT_TYPE: Shot type (2PT/3PT)
        - SHOT_RESULT: Made/Missed
        - SHOT_MADE: Boolean flag
        - LOC_X: X coordinate
        - LOC_Y: Y coordinate
        - PERIOD: Quarter/period
        - CLOCK: Game clock
        - POINTS_VALUE: Points value (2 or 3)
        - LEAGUE: "Basketball Champions League"

    Example:
        >>> shots = fetch_bcl_shot_chart(2024, 1)
        >>> made_shots = shots[shots["SHOT_MADE"] == True]
        >>> fg_pct = len(made_shots) / len(shots) * 100
        >>> print(f"Team FG%: {fg_pct:.1f}%")

        >>> # Three-point shooting
        >>> threes = shots[shots["POINTS_VALUE"] == 3]
        >>> three_pct = threes["SHOT_MADE"].sum() / len(threes) * 100
        >>> print(f"Team 3PT%: {three_pct:.1f}%")
    """
    return fetch_fiba_direct_shot_chart(
        competition=BCL_COMPETITION_CODE,
        season=season,
        game_code=game_code,
    )
