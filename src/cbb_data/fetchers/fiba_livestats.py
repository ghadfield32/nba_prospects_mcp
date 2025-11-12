"""Unified FIBA LiveStats v7 Client

This module provides a unified interface to FIBA LiveStats leagues via the euroleague-api package.

**IMPORTANT LIMITATION DISCOVERED**:
The euroleague-api package ONLY supports EuroLeague ("E") and EuroCup ("U") competitions.
Other FIBA leagues (BCL, ABA, BAL, etc.) require direct FIBA LiveStats API access or
alternative data sources.

Architecture:
- Uses euroleague-api package as backend
- Currently supports: EuroLeague and EuroCup only
- Shares rate limiting (2 req/sec)

Currently Supported Leagues:
- ✅ EuroLeague (E) - via euroleague-api
- ✅ EuroCup (U) - via euroleague-api

Future Expansion (requires additional implementation):
- ❌ Basketball Champions League (L) - Not supported by euroleague-api
- ❌ FIBA Europe Cup (J) - Not supported by euroleague-api
- ❌ Basketball Africa League (BAL) - Not supported by euroleague-api
- ❌ ABA League (ABA) - Not supported by euroleague-api
- ❌ Domestic European leagues - Not supported by euroleague-api
- ❌ Asian/Oceania leagues - Not supported by euroleague-api

**Path Forward for Additional Leagues**:
1. **Direct FIBA LiveStats API**: Reverse-engineer FIBA LiveStats endpoints (requires auth)
2. **Web Scraping**: Scrape official league websites (BCL, ABA, etc.)
3. **Alternative Packages**: Find league-specific packages (like ceblpy for CEBL)

Data Granularities Available:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores)
- team_game: ✅ Full (team box scores)
- pbp: ✅ Full (play-by-play with timestamps)
- shots: ✅ Full (X/Y coordinates, shot types)
- player_season: ✅ Aggregated (from player_game)
- team_season: ✅ Aggregated (from team_game)

Rate Limiting:
- 2 requests/second shared across all FIBA leagues
- Uses global rate limiter to avoid 429 errors

Dependencies:
- euroleague-api: Backend for API calls
- pandas: Data manipulation
"""

from __future__ import annotations

import logging

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get shared rate limiter for all FIBA LiveStats leagues
rate_limiter = get_source_limiter()

# Try to import euroleague-api (required for FIBA LiveStats access)
try:
    from euroleague_api.boxscore_data import BoxScoreData
    from euroleague_api.game_metadata import GameMetadata
    from euroleague_api.play_by_play_data import PlayByPlay
    from euroleague_api.shot_data import ShotData

    EUROLEAGUE_API_AVAILABLE = True
except ImportError:
    EUROLEAGUE_API_AVAILABLE = False
    logger.warning(
        "euroleague-api not installed. "
        "Install with: uv pip install euroleague-api\n"
        "FIBA LiveStats data fetching requires euroleague-api package."
    )


# ==============================================================================
# COMPETITION CODE MAPPING
# ==============================================================================

FIBA_COMPETITION_CODES = {
    # ONLY SUPPORTED BY euroleague-api package
    "euroleague": "E",
    "eurocup": "U",
}

LEAGUE_NAMES = {
    "E": "EuroLeague",
    "U": "EuroCup",
}

# Leagues NOT supported by euroleague-api (for documentation/future reference)
UNSUPPORTED_LEAGUES = {
    "bcl": "Basketball Champions League (requires FIBA LiveStats API or web scraping)",
    "fiba_europe_cup": "FIBA Europe Cup (requires FIBA LiveStats API)",
    "bal": "Basketball Africa League (requires FIBA LiveStats API)",
    "aba": "ABA League/Adriatic (requires FIBA LiveStats API or web scraping)",
    "greek_a1": "Greek A1/HEBA (requires web scraping)",
    "israeli_winner": "Israeli Winner League (requires web scraping)",
    "lkl": "Lithuanian LKL (requires web scraping)",
    "plk": "Polish PLK (requires web scraping)",
    "bbl": "British BBL (requires web scraping)",
    # ... additional leagues omitted for brevity
}


def _check_api_available() -> None:
    """Check if euroleague-api is available"""
    if not EUROLEAGUE_API_AVAILABLE:
        raise ImportError(
            "euroleague-api not installed. "
            "Install with: uv pip install euroleague-api\n"
            "This package is required for FIBA LiveStats access."
        )


def get_competition_code(league: str) -> str:
    """Get FIBA competition code for a league

    Args:
        league: League name (e.g., "euroleague", "eurocup")

    Returns:
        Competition code ("E" or "U")

    Raises:
        ValueError: If league is not supported by euroleague-api

    Examples:
        >>> get_competition_code("euroleague")
        'E'
        >>> get_competition_code("eurocup")
        'U'
    """
    league_lower = league.lower().replace(" ", "_").replace("-", "_")

    # Check if supported
    if league_lower in FIBA_COMPETITION_CODES:
        return FIBA_COMPETITION_CODES[league_lower]

    # If already a competition code, validate it
    if league.upper() in LEAGUE_NAMES:
        return league.upper()

    # Check if it's a known unsupported league
    if league_lower in UNSUPPORTED_LEAGUES:
        raise ValueError(
            f"League '{league}' is not supported by euroleague-api.\n"
            f"{UNSUPPORTED_LEAGUES[league_lower]}\n"
            f"Currently supported: {', '.join(FIBA_COMPETITION_CODES.keys())}"
        )

    # Unknown league
    raise ValueError(
        f"Unknown league: {league}. "
        f"Supported leagues: {', '.join(FIBA_COMPETITION_CODES.keys())}"
    )


def get_league_name(competition_code: str) -> str:
    """Get full league name from competition code

    Args:
        competition_code: FIBA competition code (e.g., "L", "BAL")

    Returns:
        Full league name (e.g., "Basketball Champions League")

    Examples:
        >>> get_league_name("L")
        'Basketball Champions League'
        >>> get_league_name("BAL")
        'Basketball Africa League'
    """
    code = competition_code.upper()
    return LEAGUE_NAMES.get(code, code)


# ==============================================================================
# UNIFIED FIBA LIVESTATS CLIENT
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_schedule(
    league: str,
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch schedule for any FIBA LiveStats league

    This is a unified interface that works for all 25+ FIBA LiveStats leagues.

    Args:
        league: League identifier (e.g., "bcl", "aba", "bal", "euroleague")
        season: Season year as integer (e.g., 2024 for 2024-25 season)
        phase: Competition phase ("RS" = Regular Season, "PO" = Playoffs)
        round_start: Starting round number
        round_end: Ending round number (None = all remaining rounds)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_CODE: Unique game identifier
        - SEASON: Season year
        - PHASE: Competition phase
        - ROUND: Round number
        - GAME_DATE: Game date/time
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score
        - AWAY_SCORE: Away team score
        - VENUE: Arena name
        - LEAGUE: League name

    Examples:
        >>> # Fetch Basketball Champions League schedule
        >>> schedule = fetch_fiba_schedule("bcl", 2024)
        >>> print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

        >>> # Fetch ABA League schedule
        >>> schedule = fetch_fiba_schedule("aba", 2024, phase="RS")
        >>> print(f"Found {len(schedule)} ABA games")

        >>> # Fetch Basketball Africa League schedule
        >>> schedule = fetch_fiba_schedule("bal", 2024)
        >>> print(schedule[["HOME_TEAM", "AWAY_TEAM", "VENUE"]].head())
    """
    _check_api_available()

    # Get competition code
    competition = get_competition_code(league)
    league_name = get_league_name(competition)

    logger.info(
        f"Fetching {league_name} schedule: {season}, {phase}, rounds {round_start}-{round_end}"
    )

    # Apply rate limiting (shared across all FIBA leagues)
    rate_limiter.acquire("fiba_livestats")

    # Use euroleague-api GameMetadata class
    metadata = GameMetadata(competition=competition)

    # Fetch all games for the season
    games_df = metadata.get_game_metadata_single_season(season)

    # Filter by phase if specified
    if phase:
        phase_map = {
            "RS": "REGULAR SEASON",
            "PO": "PLAYOFFS",
            "Regular Season": "REGULAR SEASON",
            "Playoffs": "PLAYOFFS",
        }
        phase_name = phase_map.get(phase, phase)
        games_df = games_df[games_df["Phase"].str.upper().str.contains(phase_name, na=False)]

    # Filter by round range if specified
    if round_start or round_end:
        if round_end is None:
            round_end = 34 if phase == "RS" else 5  # Typical max rounds
        games_df = games_df[(games_df["Round"] >= round_start) & (games_df["Round"] <= round_end)]

    # Rename columns to standard schema
    df = games_df.rename(
        columns={
            "Gamecode": "GAME_CODE",
            "Season": "SEASON",
            "Phase": "PHASE",
            "Round": "ROUND",
            "Date": "GAME_DATE",
            "TeamA": "HOME_TEAM",
            "TeamB": "AWAY_TEAM",
            "ScoreA": "HOME_SCORE",
            "ScoreB": "AWAY_SCORE",
            "Stadium": "VENUE",
        }
    )

    # Add league identifier
    df["LEAGUE"] = league_name

    # Select only needed columns
    columns_to_keep = [
        "GAME_CODE",
        "SEASON",
        "PHASE",
        "ROUND",
        "GAME_DATE",
        "HOME_TEAM",
        "AWAY_TEAM",
        "HOME_SCORE",
        "AWAY_SCORE",
        "VENUE",
        "LEAGUE",
    ]
    df = df[[col for col in columns_to_keep if col in df.columns]]

    # Coerce types
    if not df.empty:
        df["GAME_CODE"] = df["GAME_CODE"].astype(str)
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], format="%d/%m/%Y", errors="coerce")
        for col in ["ROUND", "HOME_SCORE", "AWAY_SCORE"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info(f"Fetched {len(df)} {league_name} games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_box_score(league: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch box score for any FIBA LiveStats league game

    Args:
        league: League identifier (e.g., "bcl", "aba", "bal")
        season: Season year as integer (e.g., 2024)
        game_code: Game code as integer (e.g., 1 for first game)

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_CODE, SEASON, PLAYER_ID, PLAYER_NAME, TEAM
        - STARTER, MIN, PTS
        - FGM, FGA, FG_PCT, FG2M, FG2A, FG3M, FG3A
        - FTM, FTA, OREB, DREB, REB
        - AST, STL, BLK, BLK_AGAINST, TOV
        - PF, PF_DRAWN, PLUS_MINUS, VALUATION
        - LEAGUE

    Examples:
        >>> box = fetch_fiba_box_score("bcl", 2024, 1)
        >>> top_scorers = box.nlargest(5, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS"]])
    """
    _check_api_available()

    competition = get_competition_code(league)
    league_name = get_league_name(competition)

    logger.info(f"Fetching {league_name} box score: {season}, {game_code}")

    rate_limiter.acquire("fiba_livestats")

    boxscore = BoxScoreData(competition=competition)
    df = boxscore.get_player_boxscore_stats_data(season, game_code)

    if not df.empty:
        df["LEAGUE"] = league_name

        # Rename columns to standard schema
        column_mapping = {
            "Gamecode": "GAME_CODE",
            "Season": "SEASON",
            "Player_ID": "PLAYER_ID",
            "Player": "PLAYER_NAME",
            "Team": "TEAM",
            "IsStarter": "STARTER",
            "Minutes": "MIN",
            "Points": "PTS",
            "FieldGoalsMade2": "FG2M",
            "FieldGoalsAttempted2": "FG2A",
            "FieldGoalsMade3": "FG3M",
            "FieldGoalsAttempted3": "FG3A",
            "FreeThrowsMade": "FTM",
            "FreeThrowsAttempted": "FTA",
            "OffensiveRebounds": "OREB",
            "DefensiveRebounds": "DREB",
            "TotalRebounds": "REB",
            "Assistances": "AST",
            "Steals": "STL",
            "BlocksFavour": "BLK",
            "BlocksAgainst": "BLK_AGAINST",
            "Turnovers": "TOV",
            "FoulsCommited": "PF",
            "FoulsReceived": "PF_DRAWN",
            "Valuation": "VALUATION",
            "Plusminus": "PLUS_MINUS",
        }

        df = df.rename(columns=column_mapping)

        # Add total FG stats
        if "FG2M" in df.columns and "FG3M" in df.columns:
            df["FGM"] = df["FG2M"].fillna(0) + df["FG3M"].fillna(0)
            df["FGA"] = df["FG2A"].fillna(0) + df["FG3A"].fillna(0)
            df["FG_PCT"] = (
                (df["FGM"] / df["FGA"]).replace([float("inf"), -float("inf")], 0).fillna(0)
            )

        # Ensure GAME_CODE and SEASON are present
        if "GAME_CODE" not in df.columns:
            df["GAME_CODE"] = game_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

    logger.info(f"Fetched {len(df)} player stats")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_play_by_play(league: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch play-by-play for any FIBA LiveStats league game

    Args:
        league: League identifier (e.g., "bcl", "aba", "bal")
        season: Season year as integer
        game_code: Game code as integer

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_CODE, SEASON, PLAY_NUMBER, PERIOD
        - PLAY_TYPE, TEAM, PLAYER, PLAYER_ID
        - MINUTE, MARKER_TIME
        - SCORE_HOME, SCORE_AWAY
        - PLAY_INFO, LEAGUE

    Examples:
        >>> pbp = fetch_fiba_play_by_play("bcl", 2024, 1)
        >>> shots = pbp[pbp["PLAY_TYPE"] == "2FGM"]
        >>> print(f"Found {len(shots)} made 2-point shots")
    """
    _check_api_available()

    competition = get_competition_code(league)
    league_name = get_league_name(competition)

    logger.info(f"Fetching {league_name} play-by-play: {season}, {game_code}")

    rate_limiter.acquire("fiba_livestats")

    pbp = PlayByPlay(competition=competition)
    df = pbp.get_game_play_by_play_data(season, game_code)

    if not df.empty:
        df["LEAGUE"] = league_name

        # Rename columns
        column_mapping = {
            "Gamecode": "GAME_CODE",
            "Season": "SEASON",
            "NUMBEROFPLAY": "PLAY_NUMBER",
            "PLAYTYPE": "PLAY_TYPE",
            "CODETEAM": "TEAM",
            "PLAYER_ID": "PLAYER_ID",
            "PLAYER": "PLAYER",
            "PLAYINFO": "PLAY_INFO",
            "PERIOD": "PERIOD",
            "MINUTE": "MINUTE",
            "MARKERTIME": "MARKER_TIME",
            "POINTS_A": "SCORE_HOME",
            "POINTS_B": "SCORE_AWAY",
        }

        df = df.rename(columns=column_mapping)

        # Deduplicate columns (API returns some duplicates)
        df = df.loc[:, ~df.columns.duplicated()]

        # Ensure GAME_CODE and SEASON are present
        if "GAME_CODE" not in df.columns:
            df["GAME_CODE"] = game_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

    logger.info(f"Fetched {len(df)} play-by-play events")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_fiba_shot_data(league: str, season: int, game_code: int) -> pd.DataFrame:
    """Fetch shot chart data for any FIBA LiveStats league game

    Args:
        league: League identifier (e.g., "bcl", "aba", "bal")
        season: Season year as integer
        game_code: Game code as integer

    Returns:
        DataFrame with shot locations and results

    Columns:
        - GAME_CODE, SEASON, PLAYER_ID, PLAYER_NAME, TEAM
        - SHOT_TYPE, POINTS_VALUE
        - LOC_X, LOC_Y, ZONE
        - FASTBREAK, SECOND_CHANCE, POINTS_OFF_TURNOVER
        - MINUTE, CLOCK, SHOT_MADE
        - LEAGUE

    Examples:
        >>> shots = fetch_fiba_shot_data("bcl", 2024, 1)
        >>> made_threes = shots[(shots["POINTS_VALUE"] == 3) & (shots["SHOT_MADE"])]
        >>> print(f"Made {len(made_threes)} three-pointers")
    """
    _check_api_available()

    competition = get_competition_code(league)
    league_name = get_league_name(competition)

    logger.info(f"Fetching {league_name} shot data: {season}, {game_code}")

    rate_limiter.acquire("fiba_livestats")

    shots = ShotData(competition=competition)
    df = shots.get_game_shot_data(season, game_code)

    if not df.empty:
        df["LEAGUE"] = league_name

        # Rename columns
        column_mapping = {
            "Gamecode": "GAME_CODE",
            "Season": "SEASON",
            "ID_PLAYER": "PLAYER_ID",
            "PLAYER": "PLAYER_NAME",
            "TEAM": "TEAM",
            "ACTION": "SHOT_TYPE",
            "POINTS": "POINTS_VALUE",
            "COORD_X": "LOC_X",
            "COORD_Y": "LOC_Y",
            "ZONE": "ZONE",
            "FASTBREAK": "FASTBREAK",
            "SECOND_CHANCE": "SECOND_CHANCE",
            "POINTS_OFF_TURNOVER": "POINTS_OFF_TURNOVER",
            "MINUTE": "MINUTE",
            "CONSOLE": "CLOCK",
        }

        df = df.rename(columns=column_mapping)

        # Add shot made flag
        if "POINTS_VALUE" in df.columns:
            df["SHOT_MADE"] = df["POINTS_VALUE"] > 0

        # Ensure GAME_CODE and SEASON are present
        if "GAME_CODE" not in df.columns:
            df["GAME_CODE"] = game_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

    logger.info(f"Fetched {len(df)} shots")
    return df
