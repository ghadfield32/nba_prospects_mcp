"""LNB API JSON → DataFrame Parsers

This module transforms raw JSON responses from the LNB API into pandas DataFrames
that match the canonical schemas defined in lnb_schemas.py.

Parser Functions:
- parse_calendar(): Schedule data (getCalenderByDivision) → LNBSchedule schema
- parse_standings(): Team standings (getStanding) → LNBTeamSeason schema
- parse_player_performance(): Player stats (getPerformancePersonV2) → LNBPlayerSeason schema
- parse_competitions_by_player(): Player→competitions mapping → Simple DataFrame

Design Principles:
1. All transformations use pandas vectorized operations (avoid loops)
2. Defensive coding: Handle missing fields gracefully (return None/NaN)
3. Type conversions are explicit and safe (str→int, str→float with error handling)
4. Field mappings documented inline for maintainability
5. Return empty DataFrame with correct schema if input is empty/invalid

Created: 2025-11-14
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from .lnb_schemas import (
    get_player_season_columns,
    get_schedule_columns,
    get_team_season_columns,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Helper Functions
# ==============================================================================


def _safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert value to int, return default if conversion fails."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert value to float, return default if conversion fails."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_minutes_french(time_str: str) -> float | None:
    """Parse French time format "18' 46''" to decimal minutes.

    Args:
        time_str: Time string like "18' 46''" or "25' 12''"

    Returns:
        Decimal minutes (e.g., 18.77 for "18' 46''"), or None if parsing fails

    Examples:
        >>> _parse_minutes_french("18' 46''")
        18.766666666666666
        >>> _parse_minutes_french("25' 12''")
        25.2
    """
    match = re.match(r"(\d+)'\s*(\d+)''", time_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes + (seconds / 60.0)
    # Fallback: try to parse as plain number
    return _safe_float(time_str, 0.0)


def _map_status(api_status: str) -> str:
    """Map LNB API match_status to canonical STATUS values.

    Args:
        api_status: Status from API (e.g., "COMPLETE", "SCHEDULED", "LIVE")

    Returns:
        Canonical status: "finished", "scheduled", "live", "postponed"
    """
    status_map = {
        "COMPLETE": "finished",
        "SCHEDULED": "scheduled",
        "LIVE": "live",
        "POSTPONED": "postponed",
        "CANCELLED": "postponed",  # Treat cancelled as postponed
    }
    return status_map.get(api_status.upper(), "scheduled")


# ==============================================================================
# Parser 1: parse_calendar() - Schedule Data
# ==============================================================================


def parse_calendar(
    json_data: Any,
    season: int,
    league: str = "LNB",
) -> pd.DataFrame:
    """Parse LNB calendar/schedule JSON to DataFrame.

    Transforms output from get_calendar_by_division() into LNBSchedule schema.

    Note: The LNBClient._get() method automatically unwraps the API envelope,
    so json_data is a list of games (not a dict with "status" and "data" keys).

    Args:
        json_data: List of game dictionaries from get_calendar_by_division()
        season: Season year (e.g., 2025 for 2024-25 season)
        league: League identifier (default: "LNB")

    Returns:
        DataFrame with columns matching LNBSchedule schema:
        - GAME_ID: match_external_id (int)
        - LEAGUE: "LNB"
        - SEASON: Season year (int)
        - COMPETITION: Competition name (str)
        - COMPETITION_ID: competition_external_id (int)
        - GAME_DATE: ISO 8601 date (str)
        - GAME_TIME_UTC: ISO 8601 datetime (str)
        - GAME_TIME_LOCAL: Local time if available (str or None)
        - HOME_TEAM_ID: Home team external_id (int)
        - HOME_TEAM: Home team name (str)
        - AWAY_TEAM_ID: Away team external_id (int)
        - AWAY_TEAM: Away team name (str)
        - HOME_SCORE: Home team score (int or None if not played)
        - AWAY_SCORE: Away team score (int or None if not played)
        - VENUE: Arena name (str or None)
        - ROUND: Round number (int or None)
        - PHASE: Phase name (str or None)
        - STATUS: Game status ("finished", "scheduled", "live", "postponed")

    Example:
        >>> from src.cbb_data.fetchers.lnb_api import LNBClient
        >>> client = LNBClient()
        >>> json_data = client.get_calendar_by_division(division_external_id=1, year=2025)
        >>> df = parse_calendar(json_data, season=2025)
        >>> print(df[["GAME_ID", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]])
    """
    # Handle empty or invalid input
    # API client unwraps envelope, so json_data is the games list directly
    if not json_data or not isinstance(json_data, list):
        logger.warning("parse_calendar: Empty or invalid input (expected list of games)")
        return pd.DataFrame(columns=get_schedule_columns())

    games = json_data
    logger.info(f"Parsing {len(games)} LNB games from calendar JSON")

    # Build list of game dictionaries
    rows = []
    for game in games:
        # Extract teams (assumes teams[0] = home, teams[1] = away)
        teams = game.get("teams", [])
        if len(teams) < 2:
            logger.warning(f"Game {game.get('match_external_id')} has <2 teams, skipping")
            continue

        home_team = teams[0]
        away_team = teams[1]

        # Parse scores (may be None for upcoming games)
        home_score_str = home_team.get("score_string")
        away_score_str = away_team.get("score_string")
        home_score = _safe_int(home_score_str) if home_score_str else None
        away_score = _safe_int(away_score_str) if away_score_str else None

        # Extract round number from round_description (e.g., "10ème journée" → 10)
        round_desc = game.get("round_description", "")
        round_num = None
        if round_desc:
            match = re.search(r"(\d+)", round_desc)
            if match:
                round_num = int(match.group(1))

        row = {
            # Primary key
            "GAME_ID": game.get("match_external_id") or game.get("external_id"),
            # League/Season
            "LEAGUE": league,
            "SEASON": season,
            "COMPETITION": game.get("competition_name", ""),
            "COMPETITION_ID": game.get("competition_external_id"),
            # Date/Time
            "GAME_DATE": game.get("match_date", ""),
            "GAME_TIME_UTC": game.get("match_time_utc", ""),
            "GAME_TIME_LOCAL": None,  # Not provided in API
            # Teams
            "HOME_TEAM_ID": home_team.get("external_id"),
            "HOME_TEAM": home_team.get("team_name", ""),
            "AWAY_TEAM_ID": away_team.get("external_id"),
            "AWAY_TEAM": away_team.get("team_name", ""),
            # Scores
            "HOME_SCORE": home_score,
            "AWAY_SCORE": away_score,
            # Metadata
            "VENUE": game.get("venue_name"),
            "ROUND": round_num,
            "PHASE": game.get("phase_name"),
            "STATUS": _map_status(game.get("match_status", "SCHEDULED")),
        }
        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows, columns=get_schedule_columns())

    # Type conversions
    df["GAME_ID"] = df["GAME_ID"].astype("Int64")  # Nullable int
    df["SEASON"] = df["SEASON"].astype("Int64")
    df["COMPETITION_ID"] = df["COMPETITION_ID"].astype("Int64")
    df["HOME_TEAM_ID"] = df["HOME_TEAM_ID"].astype("Int64")
    df["AWAY_TEAM_ID"] = df["AWAY_TEAM_ID"].astype("Int64")
    df["HOME_SCORE"] = df["HOME_SCORE"].astype("Int64")  # Nullable (None for upcoming)
    df["AWAY_SCORE"] = df["AWAY_SCORE"].astype("Int64")
    df["ROUND"] = df["ROUND"].astype("Int64")

    logger.info(f"Parsed {len(df)} games successfully")
    return df


# ==============================================================================
# Parser 2: parse_standings() - Team Season Stats
# ==============================================================================


def parse_standings(
    json_data: Any,
    season: int,
    league: str = "LNB",
) -> pd.DataFrame:
    """Parse LNB standings JSON to DataFrame.

    Transforms output from get_standing() into LNBTeamSeason schema.

    Note: The LNBClient._post() method automatically unwraps the API envelope,
    so json_data is a dict with keys like "statistics", "division_external_id", etc.

    Args:
        json_data: Dict from get_standing() containing statistics array
        season: Season year (e.g., 2025 for 2024-25 season)
        league: League identifier (default: "LNB")

    Returns:
        DataFrame with columns matching LNBTeamSeason schema

    Example:
        >>> from src.cbb_data.fetchers.lnb_api import LNBClient
        >>> client = LNBClient()
        >>> json_data = client.get_standing(competition_external_id=302)
        >>> df = parse_standings(json_data, season=2025)
        >>> print(df[["TEAM_NAME", "RANK", "W", "L", "WIN_PCT"]])
    """
    # Handle empty or invalid input
    if not json_data or not isinstance(json_data, dict):
        logger.warning("parse_standings: Empty or invalid input (expected dict)")
        return pd.DataFrame(columns=get_team_season_columns())

    statistics = json_data.get("statistics", [])
    if not statistics:
        logger.warning("parse_standings: No statistics array in response")
        return pd.DataFrame(columns=get_team_season_columns())

    logger.info(f"Parsing standings for {len(statistics)} LNB teams")

    # Extract metadata
    competition_id = json_data.get("competition_external_id")
    year = json_data.get("year", season)

    # Build list of team dictionaries
    rows = []
    for team_stat in statistics:
        team_info = team_stat.get("team", {})

        # Calculate derived metrics
        gp = team_stat.get("s_games", 0)
        wins = team_stat.get("s_wins", 0)
        losses = team_stat.get("s_losses", 0)
        pts = team_stat.get("s_points", 0)
        opp_pts = team_stat.get("s_points_against", 0)

        win_pct = wins / gp if gp > 0 else 0.0
        pts_pg = pts / gp if gp > 0 else 0.0
        opp_pts_pg = opp_pts / gp if gp > 0 else 0.0

        row = {
            # Primary keys
            "TEAM_ID": team_info.get("external_id"),
            "SEASON": year,
            "COMPETITION_ID": competition_id,
            # League
            "LEAGUE": league,
            "TEAM_NAME": team_info.get("team_name", ""),
            # Record
            "GP": gp,
            "W": wins,
            "L": losses,
            "WIN_PCT": win_pct,
            "RANK": team_stat.get("rank"),
            # Totals/Averages
            "PTS": pts,
            "OPP_PTS": opp_pts,
            "PTS_PG": pts_pg,
            "OPP_PTS_PG": opp_pts_pg,
            "PTS_DIFF": team_stat.get("plus_minus", 0),
            # Advanced (not available in this endpoint)
            "ORTG": None,
            "DRTG": None,
            "NET_RTG": None,
            # Home/Away splits
            "HOME_W": team_stat.get("s_home_wins", 0),
            "HOME_L": team_stat.get("s_home_losses", 0),
            "AWAY_W": team_stat.get("s_away_wins", 0),
            "AWAY_L": team_stat.get("s_away_losses", 0),
            # Streaks/Form (not available in this endpoint)
            "STREAK": None,
            "LAST_10": None,
        }
        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows, columns=get_team_season_columns())

    # Type conversions
    df["TEAM_ID"] = df["TEAM_ID"].astype("Int64")
    df["SEASON"] = df["SEASON"].astype("Int64")
    df["COMPETITION_ID"] = df["COMPETITION_ID"].astype("Int64")
    df["GP"] = df["GP"].astype("Int64")
    df["W"] = df["W"].astype("Int64")
    df["L"] = df["L"].astype("Int64")
    df["WIN_PCT"] = df["WIN_PCT"].astype(float)
    df["RANK"] = df["RANK"].astype("Int64")
    df["PTS"] = df["PTS"].astype("Int64")
    df["OPP_PTS"] = df["OPP_PTS"].astype("Int64")
    df["PTS_PG"] = df["PTS_PG"].astype(float)
    df["OPP_PTS_PG"] = df["OPP_PTS_PG"].astype(float)
    df["PTS_DIFF"] = df["PTS_DIFF"].astype("Int64")
    df["HOME_W"] = df["HOME_W"].astype("Int64")
    df["HOME_L"] = df["HOME_L"].astype("Int64")
    df["AWAY_W"] = df["AWAY_W"].astype("Int64")
    df["AWAY_L"] = df["AWAY_L"].astype("Int64")

    logger.info(f"Parsed standings for {len(df)} teams successfully")
    return df


# ==============================================================================
# Parser 3: parse_player_performance() - Player Season Stats
# ==============================================================================


def parse_player_performance(
    json_data: Any,
    season: int,
    competition_id: int,
    league: str = "LNB",
) -> pd.DataFrame:
    """Parse LNB player performance JSON to DataFrame.

    Transforms output from get_player_performance() into LNBPlayerSeason schema.

    Note: This returns a single-row DataFrame for ONE player in ONE competition.
    To get a player's full season stats, call this for each competition they
    participated in and concatenate the results.

    Args:
        json_data: Dict from get_player_performance()
        season: Season year (e.g., 2025)
        competition_id: Competition external ID (e.g., 302)
        league: League identifier (default: "LNB")

    Returns:
        Single-row DataFrame with columns matching LNBPlayerSeason schema

    Example:
        >>> from src.cbb_data.fetchers.lnb_api import LNBClient
        >>> client = LNBClient()
        >>> json_data = client.get_player_performance(
        ...     competition_external_id=302,
        ...     person_external_id=3586
        ... )
        >>> df = parse_player_performance(json_data, season=2025, competition_id=302)
        >>> print(df[["PLAYER_NAME", "GP", "PTS_PG", "REB_PG", "AST_PG"]])
    """
    # Handle empty or invalid input
    if not json_data or not isinstance(json_data, dict):
        logger.warning("parse_player_performance: Empty or invalid input")
        return pd.DataFrame(columns=get_player_season_columns())

    person = json_data.get("person", {})
    team = json_data.get("team", {})
    stat_data = json_data.get("statData", [])

    if not person or not stat_data:
        logger.warning("parse_player_performance: Missing person or statData")
        return pd.DataFrame(columns=get_player_season_columns())

    # Extract player info
    player_id = person.get("external_id")
    first_name = person.get("first_name", "")
    family_name = person.get("family_name", "")
    player_name = f"{first_name} {family_name}".strip()

    team_id = team.get("external_id")
    team_name = team.get("team_name", "")

    # Parse stat sections
    seasonal_avg: dict[str, Any] = {}
    shooting_eff: dict[str, Any] = {}
    # career_totals: dict[str, Any] = {}  # Not currently used (placeholder for future)

    for section in stat_data:
        title = section.get("title", "")
        data = section.get("data", {})

        if "Seasonal Averages" in title:
            seasonal_avg = data
        elif "Shooting Efficiency" in title:
            shooting_eff = data
        # elif "Career Total" in title:
        #     career_totals = data  # Not currently used

    # Extract games played and games started
    gp = _safe_int(seasonal_avg.get("games_played"), 0) or 0
    gs = _safe_int(seasonal_avg.get("first_five"), 0) or 0  # "first_five" = games started

    # Parse minutes (convert "18' 46''" to decimal)
    min_str = seasonal_avg.get("minutes", "0' 0''")
    min_per_game = (
        _parse_minutes_french(min_str) if isinstance(min_str, str) else _safe_float(min_str, 0.0)
    )
    total_min = (min_per_game or 0.0) * gp

    # Extract per-game stats
    pts_pg = _safe_float(seasonal_avg.get("points"), 0.0)
    reb_pg = _safe_float(seasonal_avg.get("rebounds"), 0.0)
    ast_pg = _safe_float(seasonal_avg.get("assists"), 0.0)
    stl_pg = _safe_float(seasonal_avg.get("steals"), 0.0) if "steals" in seasonal_avg else None
    blk_pg = _safe_float(seasonal_avg.get("blocks"), 0.0) if "blocks" in seasonal_avg else None
    tov_pg = (
        _safe_float(seasonal_avg.get("turnovers"), 0.0) if "turnovers" in seasonal_avg else None
    )

    # Calculate totals from per-game (since API provides per-game, not totals)
    pts_total = int((pts_pg or 0.0) * gp)
    reb_total = int((reb_pg or 0.0) * gp)
    ast_total = int((ast_pg or 0.0) * gp)
    stl_total = int((stl_pg or 0.0) * gp) if stl_pg is not None else 0
    blk_total = int((blk_pg or 0.0) * gp) if blk_pg is not None else 0
    tov_total = int((tov_pg or 0.0) * gp) if tov_pg is not None else 0

    # Extract shooting percentages (convert from 48.75 to 0.4875)
    fg_pct = _safe_float(shooting_eff.get("field_goal_per"), None)
    fg_pct = fg_pct / 100.0 if fg_pct is not None else None

    fg3_pct = _safe_float(shooting_eff.get("three_point_per"), None)
    fg3_pct = fg3_pct / 100.0 if fg3_pct is not None else None

    ft_pct = _safe_float(shooting_eff.get("free_throw_per"), None)
    ft_pct = ft_pct / 100.0 if ft_pct is not None else None

    # Note: API does not provide FGM, FGA, FG3M, FG3A, FTM, FTA
    # These would need to be calculated from other endpoints or estimated

    row = {
        # Primary keys
        "PLAYER_ID": player_id,
        "SEASON": season,
        "COMPETITION_ID": competition_id,
        # League/Team
        "LEAGUE": league,
        "TEAM_ID": team_id,
        "TEAM_NAME": team_name,
        # Player info
        "PLAYER_NAME": player_name,
        "POSITION": None,  # Not provided in this endpoint
        # Games
        "GP": gp,
        "GS": gs,
        "MIN": total_min,
        # Totals
        "PTS": pts_total,
        "FGM": None,  # Not provided
        "FGA": None,
        "FG3M": None,
        "FG3A": None,
        "FTM": None,
        "FTA": None,
        "OREB": None,  # Not broken down in this endpoint
        "DREB": None,
        "REB": reb_total,
        "AST": ast_total,
        "TOV": tov_total if tov_total > 0 else None,
        "STL": stl_total if stl_total > 0 else None,
        "BLK": blk_total if blk_total > 0 else None,
        "PF": None,  # Not provided
        # Percentages
        "FG_PCT": fg_pct,
        "FG3_PCT": fg3_pct,
        "FT_PCT": ft_pct,
        "PTS_PG": pts_pg,
        "REB_PG": reb_pg,
        "AST_PG": ast_pg,
        "EFG_PCT": None,  # Cannot calculate without FGM/FG3M/FGA
        "TS_PCT": None,  # Cannot calculate without PTS/FGA/FTA
    }

    # Create single-row DataFrame
    df = pd.DataFrame([row], columns=get_player_season_columns())

    # Type conversions
    df["PLAYER_ID"] = df["PLAYER_ID"].astype("Int64")
    df["SEASON"] = df["SEASON"].astype("Int64")
    df["COMPETITION_ID"] = df["COMPETITION_ID"].astype("Int64")
    df["TEAM_ID"] = df["TEAM_ID"].astype("Int64")
    df["GP"] = df["GP"].astype("Int64")
    df["GS"] = df["GS"].astype("Int64")
    df["MIN"] = df["MIN"].astype(float)
    df["PTS"] = df["PTS"].astype("Int64")
    df["REB"] = df["REB"].astype("Int64")
    df["AST"] = df["AST"].astype("Int64")

    logger.info(f"Parsed player performance for {player_name} successfully")
    return df


# ==============================================================================
# Parser 4: parse_competitions_by_player() - Player→Competitions Mapping
# ==============================================================================


def parse_competitions_by_player(
    json_data: Any,
    player_id: int,
    season: int,
    league: str = "LNB",
) -> pd.DataFrame:
    """Parse player competitions JSON to DataFrame.

    Transforms output from get_competitions_by_player() into a simple mapping table.

    Args:
        json_data: List of competition dicts from get_competitions_by_player()
        player_id: Player external ID (added to each row)
        season: Season year (added to each row)
        league: League identifier (default: "LNB")

    Returns:
        DataFrame with columns:
        - PLAYER_ID: Player external ID
        - SEASON: Season year
        - COMPETITION_ID: Competition external ID
        - COMPETITION_NAME: Competition name
        - LEAGUE: League identifier

    Example:
        >>> from src.cbb_data.fetchers.lnb_api import LNBClient
        >>> client = LNBClient()
        >>> json_data = client.get_competitions_by_player(
        ...     year=2025,
        ...     person_external_id=3586
        ... )
        >>> df = parse_competitions_by_player(json_data, player_id=3586, season=2025)
        >>> print(df[["PLAYER_ID", "COMPETITION_ID", "COMPETITION_NAME"]])
    """
    # Handle empty or invalid input
    if not json_data or not isinstance(json_data, list):
        logger.warning("parse_competitions_by_player: Empty or invalid input (expected list)")
        return pd.DataFrame(
            columns=["PLAYER_ID", "SEASON", "COMPETITION_ID", "COMPETITION_NAME", "LEAGUE"]
        )

    logger.info(f"Parsing {len(json_data)} competitions for player {player_id}")

    # Build list of competition dictionaries
    rows = []
    for comp in json_data:
        row = {
            "PLAYER_ID": player_id,
            "SEASON": season,
            "COMPETITION_ID": comp.get("external_id"),
            "COMPETITION_NAME": comp.get("competition_name", ""),
            "LEAGUE": league,
        }
        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Type conversions
    if len(df) > 0:
        df["PLAYER_ID"] = df["PLAYER_ID"].astype("Int64")
        df["SEASON"] = df["SEASON"].astype("Int64")
        df["COMPETITION_ID"] = df["COMPETITION_ID"].astype("Int64")

    logger.info(f"Parsed {len(df)} competitions successfully")
    return df


# ==============================================================================
# Boxscore Parser (Player Game Stats)
# ==============================================================================


def parse_boxscore(
    json_data: Any,
    game_id: int,
    season: int,
    league: str = "LNB",
) -> pd.DataFrame:
    """Parse LNB boxscore JSON to DataFrame (player game stats).

    ⚠️  FLEXIBLE PARSER: Designed to adapt to discovered endpoint structure.

    This parser handles multiple potential response structures:
    1. List of players directly
    2. Dict with "players" key
    3. Dict with "home_players" and "away_players" keys
    4. Dict with nested team structure

    Once the real endpoint is discovered, update the parsing logic to match
    the actual response structure.

    Args:
        json_data: Boxscore JSON response from get_match_boxscore()
        game_id: Match external ID
        season: Season year
        league: League identifier (default: "LNB")

    Returns:
        DataFrame with columns matching LNBPlayerGame schema (32 columns)

    Expected JSON Structure (Pattern 1 - Simple):
        [
            {
                "person_external_id": 3586,
                "first_name": "Nadir",
                "family_name": "Hifi",
                "team_external_id": 1794,
                "opponent_external_id": 1786,
                "minutes": "18' 46''",
                "points": 20,
                "field_goals_made": 8,
                "field_goals_attempted": 15,
                ...
            }
        ]

    Expected JSON Structure (Pattern 2 - Nested):
        {
            "match_external_id": 28931,
            "players": [
                { ... player stats ... }
            ],
            "teams": [
                { ... team stats ... }
            ]
        }

    Notes:
        - Returns empty DataFrame with correct schema if endpoint not discovered
        - Handles French time format ("18' 46''" → 18.77)
        - Calculates derived metrics (FG_PCT, EFG_PCT, TS_PCT)
        - Requires FGM/FGA/PTS for calculations (may not be in API)
    """
    from .lnb_schemas import get_player_game_columns

    # Handle different response structures
    players_data = []

    if json_data is None or (isinstance(json_data, dict) and not json_data):
        logger.warning(f"parse_boxscore: Empty or None input for game {game_id}")
        return pd.DataFrame(columns=get_player_game_columns())

    # Pattern 1: Direct list of players
    if isinstance(json_data, list):
        players_data = json_data

    # Pattern 2: Dict with "players" key
    elif isinstance(json_data, dict):
        if "players" in json_data:
            players_data = json_data["players"]

        # Pattern 3: Separate home/away player lists
        elif "home_players" in json_data and "away_players" in json_data:
            players_data = json_data["home_players"] + json_data["away_players"]

        # Pattern 4: Nested team structure
        elif "teams" in json_data:
            # Extract players from team objects
            for team in json_data.get("teams", []):
                if "players" in team:
                    players_data.extend(team["players"])

        else:
            logger.warning(
                f"parse_boxscore: Unknown response structure for game {game_id}. "
                f"Keys: {list(json_data.keys())}"
            )
            return pd.DataFrame(columns=get_player_game_columns())

    if not players_data:
        logger.warning(f"parse_boxscore: No player data found for game {game_id}")
        return pd.DataFrame(columns=get_player_game_columns())

    # Build DataFrame rows
    rows = []
    for player in players_data:
        # Basic identifiers
        player_id = player.get("person_external_id") or player.get("player_id")
        first_name = player.get("first_name", "")
        family_name = player.get("family_name", "") or player.get("last_name", "")
        player_name = f"{first_name} {family_name}".strip() or "Unknown"

        team_id = player.get("team_external_id") or player.get("team_id")
        opponent_id = player.get("opponent_external_id") or player.get("opponent_id")

        # Minutes (handle French format)
        minutes_str = player.get("minutes", "0")
        if isinstance(minutes_str, str) and "'" in minutes_str:
            minutes = _parse_minutes_french(minutes_str) or 0.0
        else:
            minutes = _safe_float(minutes_str, 0.0) or 0.0

        # Shooting stats
        pts = _safe_int(player.get("points"), 0) or 0
        fgm = _safe_int(player.get("field_goals_made") or player.get("fgm"), 0) or 0
        fga = _safe_int(player.get("field_goals_attempted") or player.get("fga"), 0) or 0
        fg3m = (
            _safe_int(
                player.get("three_pointers_made")
                or player.get("fg3m")
                or player.get("three_point_made"),
                0,
            )
            or 0
        )
        fg3a = (
            _safe_int(
                player.get("three_pointers_attempted")
                or player.get("fg3a")
                or player.get("three_point_attempted"),
                0,
            )
            or 0
        )
        ftm = _safe_int(player.get("free_throws_made") or player.get("ftm"), 0) or 0
        fta = _safe_int(player.get("free_throws_attempted") or player.get("fta"), 0) or 0

        # Rebounds
        oreb = _safe_int(player.get("offensive_rebounds") or player.get("oreb"), 0) or 0
        dreb = _safe_int(player.get("defensive_rebounds") or player.get("dreb"), 0) or 0
        reb = (
            _safe_int(
                player.get("rebounds") or player.get("reb") or player.get("total_rebounds"), 0
            )
            or 0
        )

        # If total rebounds given but not split, set OREB/DREB to 0 (unknown split)
        if reb > 0 and oreb == 0 and dreb == 0:
            # Keep totals, splits unknown
            pass

        # Playmaking & Defense
        ast = _safe_int(player.get("assists") or player.get("ast"), 0) or 0
        tov = _safe_int(player.get("turnovers") or player.get("tov") or player.get("to"), 0) or 0
        stl = _safe_int(player.get("steals") or player.get("stl"), 0) or 0
        blk = _safe_int(player.get("blocks") or player.get("blk"), 0) or 0
        pf = (
            _safe_int(player.get("fouls") or player.get("pf") or player.get("personal_fouls"), 0)
            or 0
        )

        # Game context
        starter = player.get("starter") or player.get("is_starter") or False
        won = player.get("won") or False
        plus_minus = _safe_int(player.get("plus_minus") or player.get("+/-"), 0) or 0

        # Calculate percentages
        fg_pct = (fgm / fga) if fga > 0 else None
        fg3_pct = (fg3m / fg3a) if fg3a > 0 else None
        ft_pct = (ftm / fta) if fta > 0 else None

        # Calculate derived metrics
        # eFG% = (FGM + 0.5 * FG3M) / FGA
        efg_pct = ((fgm + 0.5 * fg3m) / fga) if fga > 0 else None

        # TS% = PTS / (2 * (FGA + 0.44 * FTA))
        ts_denominator = 2 * (fga + 0.44 * fta)
        ts_pct = (pts / ts_denominator) if ts_denominator > 0 else None

        # Note: We don't have game_date or home_away without schedule lookup
        # These will need to be enriched later or from context

        row = {
            "GAME_ID": game_id,
            "PLAYER_ID": player_id,
            "PLAYER_NAME": player_name,
            "TEAM_ID": team_id,
            "OPPONENT_ID": opponent_id,
            "LEAGUE": league,
            "SEASON": season,
            "GAME_DATE": None,  # Requires schedule lookup
            "HOME_AWAY": None,  # Requires schedule lookup
            "STARTER": starter,
            "WON": won,
            "MIN": minutes,
            "PTS": pts,
            "FGM": fgm,
            "FGA": fga,
            "FG_PCT": fg_pct,
            "FG3M": fg3m,
            "FG3A": fg3a,
            "FG3_PCT": fg3_pct,
            "FTM": ftm,
            "FTA": fta,
            "FT_PCT": ft_pct,
            "OREB": oreb,
            "DREB": dreb,
            "REB": reb,
            "AST": ast,
            "TOV": tov,
            "STL": stl,
            "BLK": blk,
            "PF": pf,
            "PLUS_MINUS": plus_minus,
            "EFG_PCT": efg_pct,
            "TS_PCT": ts_pct,
        }
        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows, columns=get_player_game_columns())

    # Type conversions
    if len(df) > 0:
        df["GAME_ID"] = df["GAME_ID"].astype("Int64")
        df["PLAYER_ID"] = df["PLAYER_ID"].astype("Int64")
        df["TEAM_ID"] = df["TEAM_ID"].astype("Int64")
        df["OPPONENT_ID"] = df["OPPONENT_ID"].astype("Int64")
        df["SEASON"] = df["SEASON"].astype("Int64")

        # Integer stats (nullable)
        for col in [
            "PTS",
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "OREB",
            "DREB",
            "REB",
            "AST",
            "TOV",
            "STL",
            "BLK",
            "PF",
            "PLUS_MINUS",
        ]:
            df[col] = df[col].astype("Int64")

    logger.info(f"Parsed {len(df)} player boxscore rows for game {game_id}")
    return df
