"""EuroLeague & EuroCup Fetcher

Official EuroLeague API client wrapper.
Uses the euroleague-api Python package for clean, documented access.

Supports:
- EuroLeague (competition='E')
- EuroCup (competition='U')

Key Features:
- Free, official API
- Comprehensive data (games, box scores, play-by-play, shots)
- Historical data back to 2000-01 season
- Rate limit: 2 req/sec (conservative)

Data Granularities:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores with all stats)
- team_game: ✅ Full (team box scores and game results)
- pbp: ✅ Full (play-by-play with timestamps, scores, players)
- shots: ✅ Full (X/Y coordinates, shot types, made/missed)
- player_season: ✅ Aggregated (from player_game data)
- team_season: ✅ Aggregated (from team_game data)

Documentation: https://github.com/giasemidis/euroleague_api
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Try to import euroleague-api
try:
    from euroleague_api.boxscore_data import BoxScoreData
    from euroleague_api.game_metadata import GameMetadata
    from euroleague_api.play_by_play_data import PlayByPlay
    from euroleague_api.shot_data import ShotData

    EUROLEAGUE_API_AVAILABLE = True
except ImportError:
    EUROLEAGUE_API_AVAILABLE = False
    logger.warning("euroleague-api not installed. Install with: uv pip install euroleague-api")

# Get rate limiter
rate_limiter = get_source_limiter()


def _check_api_available() -> None:
    """Check if EuroLeague API is available"""
    if not EUROLEAGUE_API_AVAILABLE:
        raise ImportError(
            "euroleague-api not installed. " "Install with: uv pip install euroleague-api"
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_euroleague_games(
    season: int,
    phase: str | None = "RS",  # RS = Regular Season, PO = Playoffs
    round_start: int = 1,
    round_end: int | None = None,
    competition: str = "E",  # E = EuroLeague, U = EuroCup
) -> pd.DataFrame:
    """Fetch EuroLeague/EuroCup game schedule

    Note: API always fetches full season data. Use caching + limit at API layer.

    Args:
        season: Season year as integer (e.g., 2024 for 2024-25 season)
        phase: Competition phase ("RS" or "PO")
        round_start: Starting round number
        round_end: Ending round number (None = all remaining rounds)
        competition: Competition code ("E" for EuroLeague, "U" for EuroCup)

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
        - LEAGUE: League identifier (EuroLeague or EuroCup)
    """
    _check_api_available()

    rate_limiter.acquire("euroleague")

    league_name = "EuroLeague" if competition == "E" else "EuroCup"
    logger.info(
        f"Fetching {league_name} games: {season}, {phase}, rounds {round_start}-{round_end}"
    )

    metadata = GameMetadata(competition=competition)

    # Fetch all games for the season
    # Note: API does not support partial fetches - always returns full season
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

    # Rename columns to match our schema
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

    # Select only the columns we need
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

    logger.info(f"Fetched {len(df)} EuroLeague games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_euroleague_box_score(season: int, game_code: int, competition: str = "E") -> pd.DataFrame:
    """Fetch EuroLeague/EuroCup box score for a game

    Args:
        season: Season year as integer (e.g., 2024)
        game_code: Game code as integer (e.g., 1 for first game)
        competition: Competition code ("E" for EuroLeague, "U" for EuroCup)

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_CODE: Game identifier
        - SEASON: Season year
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - STARTER: Is starter (0/1)
        - MIN: Minutes played
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A: 2-point field goals
        - FG3M, FG3A: 3-point field goals
        - FTM, FTA: Free throws
        - OREB, DREB, REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks (blocked shots by player)
        - BLK_AGAINST: Blocks against (player's shots blocked)
        - TOV: Turnovers
        - PF: Personal fouls
        - PF_DRAWN: Fouls drawn
        - PLUS_MINUS: Plus/minus
        - VALUATION: EuroLeague efficiency rating
    """
    _check_api_available()

    rate_limiter.acquire("euroleague")

    league_name = "EuroLeague" if competition == "E" else "EuroCup"
    logger.info(f"Fetching {league_name} box score: {season}, {game_code}")

    boxscore = BoxScoreData(competition=competition)
    df = boxscore.get_player_boxscore_stats_data(season, game_code)

    # Add league identifier
    if not df.empty:
        df["LEAGUE"] = league_name

        # Rename columns to match our schema
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

    logger.info(f"Fetched box score: {len(df)} players")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_euroleague_play_by_play(
    season: int, game_code: int, competition: str = "E"
) -> pd.DataFrame:
    """Fetch EuroLeague/EuroCup play-by-play data

    Args:
        season: Season year as integer (e.g., 2024)
        game_code: Game code as integer (e.g., 1)
        competition: Competition code ("E" for EuroLeague, "U" for EuroCup)

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_CODE: Game identifier
        - SEASON: Season year
        - PLAY_NUMBER: Sequential play number
        - PERIOD: Quarter/period (1-4, 5+ for OT)
        - PLAY_TYPE: Type of play
        - TEAM: Team involved
        - PLAYER: Player name
        - PLAYER_ID: Player ID
        - MINUTE: Game minute
        - MARKER_TIME: Elapsed time marker
        - SCORE_HOME: Home team score
        - SCORE_AWAY: Away team score
        - PLAY_INFO: Play description
    """
    _check_api_available()

    rate_limiter.acquire("euroleague")

    league_name = "EuroLeague" if competition == "E" else "EuroCup"
    logger.info(f"Fetching {league_name} play-by-play: {season}, {game_code}")

    pbp = PlayByPlay(competition=competition)
    df = pbp.get_game_play_by_play_data(season, game_code)

    # Add league identifier
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

        # Deduplicate columns (API returns both CODETEAM and TEAM; after rename we have duplicate TEAM)
        # Keep first occurrence of each column name
        df = df.loc[:, ~df.columns.duplicated()]

        # Ensure GAME_CODE and SEASON are present
        if "GAME_CODE" not in df.columns:
            df["GAME_CODE"] = game_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

    logger.info(f"Fetched play-by-play: {len(df)} events")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_euroleague_shot_data(season: int, game_code: int, competition: str = "E") -> pd.DataFrame:
    """Fetch EuroLeague/EuroCup shot chart data

    Args:
        season: Season year as integer (e.g., 2024)
        game_code: Game code as integer (e.g., 1)
        competition: Competition code ("E" for EuroLeague, "U" for EuroCup)

    Returns:
        DataFrame with shot locations and results

    Columns:
        - GAME_CODE: Game identifier
        - SEASON: Season year
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - SHOT_TYPE: Shot action type
        - POINTS_VALUE: Points value (2 or 3)
        - LOC_X: X coordinate
        - LOC_Y: Y coordinate
        - ZONE: Court zone
        - FASTBREAK: Is fastbreak (0/1)
        - SECOND_CHANCE: Is second chance (0/1)
        - POINTS_OFF_TURNOVER: Points off turnover (0/1)
        - MINUTE: Game minute
        - CLOCK: Game clock
        - SHOT_MADE: Whether shot was made (derived from action)
    """
    _check_api_available()

    rate_limiter.acquire("euroleague")

    league_name = "EuroLeague" if competition == "E" else "EuroCup"
    logger.info(f"Fetching {league_name} shot data: {season}, {game_code}")

    shots = ShotData(competition=competition)
    df = shots.get_game_shot_data(season, game_code)

    # Add league identifier
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

        # Add shot made flag (based on whether POINTS_VALUE > 0)
        if "POINTS_VALUE" in df.columns:
            df["SHOT_MADE"] = df["POINTS_VALUE"] > 0

        # Ensure GAME_CODE and SEASON are present
        if "GAME_CODE" not in df.columns:
            df["GAME_CODE"] = game_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

    logger.info(f"Fetched shot data: {len(df)} shots")
    return df


def fetch_euroleague_full_season(
    season: str,
    phase: str = "RS",
    max_workers: int = 4,
    skip_pbp: bool = False,
    skip_shots: bool = False,
) -> dict[str, pd.DataFrame]:
    """Fetch all data for a EuroLeague season with concurrent fetching

    Uses ThreadPoolExecutor to fetch box scores, PBP, and shots concurrently.
    This reduces fetch time from ~25 minutes to ~3-5 minutes for a full season.

    Args:
        season: Season code (e.g., "E2024")
        phase: Competition phase ("RS" or "PO")
        max_workers: Maximum concurrent threads (default 4, respects 2 req/sec rate limit)
        skip_pbp: Skip play-by-play data (faster if only need box scores)
        skip_shots: Skip shot data (faster if only need box scores)

    Returns:
        Dictionary with:
            - "schedule": All games
            - "box_scores": All player box scores
            - "play_by_play": All play-by-play data (empty if skip_pbp=True)
            - "shots": All shot data (empty if skip_shots=True)

    Note:
        Rate limiting is handled by individual fetch functions.
        max_workers=4 with 2 req/sec limit provides good throughput.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger.info(f"Fetching full EuroLeague season: {season}, {phase} (workers={max_workers})")

    result = {}

    # Get schedule first (single call)
    schedule = fetch_euroleague_games(season, phase)
    result["schedule"] = schedule

    if schedule.empty:
        result["box_scores"] = pd.DataFrame()
        result["play_by_play"] = pd.DataFrame()
        result["shots"] = pd.DataFrame()
        return result

    game_codes = schedule["GAME_CODE"].tolist()
    total_games = len(game_codes)

    # Helper function to fetch all data for a single game
    def fetch_game_data(game_code: int) -> dict[str, Any]:
        """Fetch box score, PBP, and shots for a single game"""
        game_result: dict[str, Any] = {
            "game_code": game_code,
            "box": None,
            "pbp": None,
            "shots": None,
        }

        try:
            # Box score (always fetch)
            game_result["box"] = fetch_euroleague_box_score(season, game_code)

            # Play-by-play (optional)
            if not skip_pbp:
                game_result["pbp"] = fetch_euroleague_play_by_play(season, game_code)

            # Shots (optional)
            if not skip_shots:
                game_result["shots"] = fetch_euroleague_shot_data(season, game_code)

        except Exception as e:
            logger.warning(f"Failed to fetch data for game {game_code}: {e}")

        return game_result

    # Fetch all games concurrently
    box_scores = []
    pbp_data = []
    shot_data = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        futures = {executor.submit(fetch_game_data, gc): gc for gc in game_codes}

        # Collect results as they complete
        for future in as_completed(futures):
            game_code = futures[future]
            try:
                game_result = future.result()

                if game_result["box"] is not None and not game_result["box"].empty:
                    box_scores.append(game_result["box"])

                if game_result["pbp"] is not None and not game_result["pbp"].empty:
                    pbp_data.append(game_result["pbp"])

                if game_result["shots"] is not None and not game_result["shots"].empty:
                    shot_data.append(game_result["shots"])

            except Exception as e:
                logger.error(f"Game {game_code} future failed: {e}")

            completed += 1
            if completed % 50 == 0:
                logger.info(f"Progress: {completed}/{total_games} games fetched")

    # Combine all results
    result["box_scores"] = (
        pd.concat(box_scores, ignore_index=True) if box_scores else pd.DataFrame()
    )
    result["play_by_play"] = pd.concat(pbp_data, ignore_index=True) if pbp_data else pd.DataFrame()
    result["shots"] = pd.concat(shot_data, ignore_index=True) if shot_data else pd.DataFrame()

    logger.info(
        f"Fetched full season: "
        f"{len(result['schedule'])} games, "
        f"{len(result['box_scores'])} player stats, "
        f"{len(result['play_by_play'])} plays, "
        f"{len(result['shots'])} shots"
    )

    return result
