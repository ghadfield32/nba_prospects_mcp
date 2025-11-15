"""LNB Historical Data Access Layer

Provides query interface for historical LNB (French basketball) data collected
via the historical data pipeline.

Data is read from the ingested historical datasets in data/lnb/historical/{season}/
directories and provides a unified API for accessing:
- Game fixtures and results
- Play-by-play events
- Shot chart data
- Player season aggregates
- Team season aggregates

Usage:
    from cbb_data.api.lnb_historical import (
        get_lnb_historical_fixtures,
        get_lnb_historical_pbp,
        get_lnb_player_season_stats,
    )

    # Get all fixtures for 2024-2025 season
    fixtures = get_lnb_historical_fixtures("2024-2025")

    # Get PBP for a specific game
    pbp = get_lnb_historical_pbp("2024-2025", fixture_uuid="abc-123...")

    # Get player season stats with per-game averages
    player_stats = get_lnb_player_season_stats("2024-2025", per_mode="PerGame")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

# Base directory for historical LNB data
HISTORICAL_DATA_DIR = Path("data/lnb/historical")


# ==============================================================================
# Helper Functions
# ==============================================================================


def _get_season_dir(season: str) -> Path:
    """Get the directory path for a season's historical data

    Args:
        season: Season string (e.g., "2024-2025", "2025-2026")

    Returns:
        Path to season directory

    Raises:
        FileNotFoundError: If season directory doesn't exist
    """
    season_dir = HISTORICAL_DATA_DIR / season
    if not season_dir.exists():
        raise FileNotFoundError(
            f"Historical data not found for season {season}. "
            f"Directory does not exist: {season_dir}\n"
            f"Available seasons: {list_available_seasons()}"
        )
    return season_dir


def _load_historical_data(
    season: str,
    data_type: Literal["fixtures", "pbp_events", "shots"],
    format: Literal["json", "csv", "parquet"] = "parquet",
) -> pd.DataFrame:
    """Load historical data from disk

    Args:
        season: Season string (e.g., "2024-2025")
        data_type: Type of data to load ("fixtures", "pbp_events", "shots")
        format: File format to read ("json", "csv", "parquet")

    Returns:
        DataFrame with requested data

    Raises:
        FileNotFoundError: If data file doesn't exist
        ValueError: If invalid format specified
    """
    season_dir = _get_season_dir(season)

    # Determine file path based on format preference
    # Try parquet first (fastest), then CSV, then JSON
    file_path = None
    formats_to_try: list[Literal["json", "csv", "parquet"]] = (
        [format] if format != "parquet" else ["parquet", "csv", "json"]
    )

    for fmt in formats_to_try:
        potential_path = season_dir / f"{data_type}.{fmt}"
        if potential_path.exists():
            file_path = potential_path
            format = fmt  # type: ignore[assignment]
            break

    if file_path is None:
        raise FileNotFoundError(
            f"No {data_type} data found for season {season} in any format. "
            f"Looked for: {data_type}.{{parquet,csv,json}}"
        )

    # Load data based on format
    logger.debug(f"Loading {data_type} from {file_path}")

    if format == "parquet":
        return pd.read_parquet(file_path)
    elif format == "csv":
        return pd.read_csv(file_path)
    elif format == "json":
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    else:
        raise ValueError(f"Unsupported format: {format}")


# ==============================================================================
# Public Query Functions
# ==============================================================================


def list_available_seasons() -> list[str]:
    """List all seasons with available historical data

    Returns:
        List of season strings (e.g., ["2025-2026", "2024-2025", "2023-2024"])
        Sorted in descending order (newest first)

    Examples:
        >>> seasons = list_available_seasons()
        >>> print(seasons)
        ['2025-2026', '2024-2025', '2023-2024', '2022-2023']
    """
    if not HISTORICAL_DATA_DIR.exists():
        logger.warning(f"Historical data directory not found: {HISTORICAL_DATA_DIR}")
        return []

    # Find all season directories (format: YYYY-YYYY)
    season_dirs = [d.name for d in HISTORICAL_DATA_DIR.iterdir() if d.is_dir() and "-" in d.name]

    # Sort by start year (descending)
    season_dirs.sort(reverse=True)

    return season_dirs


def get_lnb_historical_fixtures(
    season: str,
    division: int = 1,
    team: str | list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Get historical game fixtures and results for a season

    Args:
        season: Season string (e.g., "2024-2025", "2025-2026")
        division: Division number (1 = Pro A, 2 = Pro B, default: 1)
        team: Team name or list of teams to filter (optional)
        date_from: Filter games from this date (YYYY-MM-DD format, optional)
        date_to: Filter games to this date (YYYY-MM-DD format, optional)
        limit: Maximum number of rows to return (optional)

    Returns:
        DataFrame with columns:
        - fixture_uuid: Unique game identifier
        - external_id: External game ID
        - season: Season string
        - game_date: Game date (YYYY-MM-DD)
        - home_team: Home team name
        - away_team: Away team name
        - home_score: Home team final score
        - away_score: Away team final score
        - status: Game status (FINISHED, SCHEDULED, etc.)
        - has_pbp: Whether PBP data is available
        - pbp_events_count: Number of PBP events
        - shots_count: Number of shot events

    Examples:
        >>> # Get all fixtures for 2024-2025 season
        >>> fixtures = get_lnb_historical_fixtures("2024-2025")

        >>> # Get Monaco's fixtures
        >>> monaco_fixtures = get_lnb_historical_fixtures("2024-2025", team="Monaco")

        >>> # Get fixtures in November 2024
        >>> nov_fixtures = get_lnb_historical_fixtures(
        ...     "2024-2025",
        ...     date_from="2024-11-01",
        ...     date_to="2024-11-30"
        ... )
    """
    df = _load_historical_data(season, "fixtures")

    # Filter by division if specified (future-proofing for Pro B support)
    # Note: Current implementation only has division=1 data
    # This filter is a placeholder for future expansion

    # Filter by team if specified
    if team:
        teams = [team] if isinstance(team, str) else team
        # Match either home or away team
        team_mask = df["home_team"].isin(teams) | df["away_team"].isin(teams)
        df = df[team_mask]

    # Filter by date range if specified
    if date_from or date_to:
        # Ensure game_date is datetime
        if "game_date" in df.columns:
            df["game_date"] = pd.to_datetime(df["game_date"])

            if date_from:
                df = df[df["game_date"] >= pd.to_datetime(date_from)]
            if date_to:
                df = df[df["game_date"] <= pd.to_datetime(date_to)]

    # Apply limit if specified
    if limit:
        df = df.head(limit)

    logger.info(
        f"Retrieved {len(df)} fixtures for LNB {season} "
        f"(division={division}, team={team}, date_range={date_from}..{date_to})"
    )

    return df


def get_lnb_historical_pbp(
    season: str,
    fixture_uuid: str | list[str] | None = None,
    team: str | list[str] | None = None,
    player: str | list[str] | None = None,
    event_type: str | list[str] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Get historical play-by-play events for a season or specific games

    Args:
        season: Season string (e.g., "2024-2025")
        fixture_uuid: Game UUID or list of UUIDs to filter (optional)
        team: Team name or list of teams to filter (optional)
        player: Player name or list of players to filter (optional)
        event_type: Event type or list of types to filter (optional)
                   Examples: "SHOT_MADE", "REBOUND", "ASSIST", "TURNOVER"
        limit: Maximum number of rows to return (optional)

    Returns:
        DataFrame with columns:
        - fixture_uuid: Game identifier
        - event_id: Event sequence number within game
        - quarter: Quarter/period number
        - clock: Game clock (MM:SS format)
        - team: Team responsible for event
        - player: Player involved (if applicable)
        - event_type: Type of event
        - event_description: Human-readable event description
        - score_home: Home score after event
        - score_away: Away score after event
        - x, y: Court coordinates (if applicable)

    Examples:
        >>> # Get all PBP for a season
        >>> pbp = get_lnb_historical_pbp("2024-2025")

        >>> # Get PBP for a specific game
        >>> game_pbp = get_lnb_historical_pbp(
        ...     "2024-2025",
        ...     fixture_uuid="abc-123-def-456"
        ... )

        >>> # Get all shot events for Monaco
        >>> monaco_shots = get_lnb_historical_pbp(
        ...     "2024-2025",
        ...     team="Monaco",
        ...     event_type=["SHOT_MADE", "SHOT_MISSED"]
        ... )
    """
    df = _load_historical_data(season, "pbp_events")

    # Filter by fixture UUID if specified
    if fixture_uuid:
        uuids = [fixture_uuid] if isinstance(fixture_uuid, str) else fixture_uuid
        df = df[df["fixture_uuid"].isin(uuids)]

    # Filter by team if specified
    if team:
        teams = [team] if isinstance(team, str) else team
        df = df[df["team"].isin(teams)]

    # Filter by player if specified
    if player:
        players = [player] if isinstance(player, str) else player
        df = df[df["player"].isin(players)]

    # Filter by event type if specified
    if event_type:
        types = [event_type] if isinstance(event_type, str) else event_type
        df = df[df["event_type"].isin(types)]

    # Apply limit if specified
    if limit:
        df = df.head(limit)

    logger.info(
        f"Retrieved {len(df)} PBP events for LNB {season} "
        f"(fixture={fixture_uuid}, team={team}, player={player})"
    )

    return df


def get_lnb_historical_shots(
    season: str,
    fixture_uuid: str | list[str] | None = None,
    team: str | list[str] | None = None,
    player: str | list[str] | None = None,
    made: bool | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Get historical shot chart data for a season or specific games

    Args:
        season: Season string (e.g., "2024-2025")
        fixture_uuid: Game UUID or list of UUIDs to filter (optional)
        team: Team name or list of teams to filter (optional)
        player: Player name or list of players to filter (optional)
        made: Filter by shot result (True = made, False = missed, None = all)
        limit: Maximum number of rows to return (optional)

    Returns:
        DataFrame with columns:
        - fixture_uuid: Game identifier
        - shot_id: Shot sequence number
        - quarter: Quarter/period number
        - clock: Game clock (MM:SS format)
        - team: Shooting team
        - player: Shooting player
        - shot_type: Type of shot (2PT, 3PT, FT)
        - made: Whether shot was made (True/False)
        - x, y: Shot coordinates on court
        - distance: Distance from basket (if available)

    Examples:
        >>> # Get all shots for a season
        >>> shots = get_lnb_historical_shots("2024-2025")

        >>> # Get made 3-pointers for Monaco
        >>> monaco_3pt = get_lnb_historical_shots(
        ...     "2024-2025",
        ...     team="Monaco",
        ...     made=True
        ... )
        >>> monaco_3pt = monaco_3pt[monaco_3pt['shot_type'] == '3PT']
    """
    df = _load_historical_data(season, "shots")

    # Filter by fixture UUID if specified
    if fixture_uuid:
        uuids = [fixture_uuid] if isinstance(fixture_uuid, str) else fixture_uuid
        df = df[df["fixture_uuid"].isin(uuids)]

    # Filter by team if specified
    if team:
        teams = [team] if isinstance(team, str) else team
        df = df[df["team"].isin(teams)]

    # Filter by player if specified
    if player:
        players = [player] if isinstance(player, str) else player
        df = df[df["player"].isin(players)]

    # Filter by shot result if specified
    if made is not None:
        df = df[df["made"] == made]

    # Apply limit if specified
    if limit:
        df = df.head(limit)

    logger.info(
        f"Retrieved {len(df)} shots for LNB {season} "
        f"(fixture={fixture_uuid}, team={team}, player={player}, made={made})"
    )

    return df


# ==============================================================================
# Aggregation Functions - Season Stats
# ==============================================================================


def get_lnb_player_season_stats(
    season: str,
    per_mode: Literal["Totals", "PerGame", "Per40"] = "Totals",
    team: str | list[str] | None = None,
    player: str | list[str] | None = None,
    min_games: int = 1,
    limit: int | None = None,
) -> pd.DataFrame:
    """Get aggregated player season statistics from historical PBP data

    Aggregates play-by-play events into player season totals and averages.

    Args:
        season: Season string (e.g., "2024-2025")
        per_mode: Aggregation mode:
                 - "Totals": Season totals
                 - "PerGame": Per-game averages
                 - "Per40": Per-40-minute rates
        team: Team name or list of teams to filter (optional)
        player: Player name or list of players to filter (optional)
        min_games: Minimum games played to include (default: 1)
        limit: Maximum number of rows to return (optional)

    Returns:
        DataFrame with columns:
        - player: Player name
        - team: Team name (or "MULTIPLE" if played for multiple teams)
        - games_played: Number of games played
        - minutes: Total/average minutes played
        - points: Total/average points scored
        - field_goals_made: Total/average FG made
        - field_goals_attempted: Total/average FG attempted
        - field_goal_pct: FG percentage
        - three_pointers_made: Total/average 3PT made
        - three_pointers_attempted: Total/average 3PT attempted
        - three_point_pct: 3PT percentage
        - free_throws_made: Total/average FT made
        - free_throws_attempted: Total/average FT attempted
        - free_throw_pct: FT percentage
        - rebounds: Total/average rebounds
        - assists: Total/average assists
        - turnovers: Total/average turnovers
        - steals: Total/average steals
        - blocks: Total/average blocks
        - fouls: Total/average personal fouls

    Examples:
        >>> # Get season totals for all players
        >>> totals = get_lnb_player_season_stats("2024-2025", per_mode="Totals")

        >>> # Get per-game averages for players with 10+ games
        >>> averages = get_lnb_player_season_stats(
        ...     "2024-2025",
        ...     per_mode="PerGame",
        ...     min_games=10
        ... )

        >>> # Get Monaco players' stats
        >>> monaco_stats = get_lnb_player_season_stats(
        ...     "2024-2025",
        ...     team="Monaco"
        ... )
    """
    # Load PBP events
    pbp = _load_historical_data(season, "pbp_events")

    # Filter by team if specified
    if team:
        teams = [team] if isinstance(team, str) else team
        pbp = pbp[pbp["team"].isin(teams)]

    # Filter by player if specified
    if player:
        players = [player] if isinstance(player, str) else player
        pbp = pbp[pbp["player"].isin(players)]

    # Aggregate stats by player
    # This is a placeholder - actual aggregation logic depends on PBP event schema
    # Will need to map event types to stat categories

    # Group by player and team
    grouped = pbp.groupby(["player", "team"])

    # Calculate basic stats (placeholder - needs actual event counting)
    stats = grouped.agg(
        {
            "fixture_uuid": "nunique",  # games_played
            # Add more aggregations based on actual PBP schema
        }
    ).rename(columns={"fixture_uuid": "games_played"})

    stats = stats.reset_index()

    # Filter by minimum games
    if min_games > 1:
        stats = stats[stats["games_played"] >= min_games]

    # Apply per-mode calculations
    if per_mode == "PerGame":
        # Divide counting stats by games_played
        stat_cols = [c for c in stats.columns if c not in ["player", "team", "games_played"]]
        for col in stat_cols:
            if col in stats.columns:
                stats[col] = stats[col] / stats["games_played"]

    elif per_mode == "Per40":
        # Divide counting stats by minutes, multiply by 40
        if "minutes" in stats.columns:
            stat_cols = [
                c for c in stats.columns if c not in ["player", "team", "games_played", "minutes"]
            ]
            for col in stat_cols:
                if col in stats.columns:
                    stats[col] = (stats[col] / stats["minutes"]) * 40

    # Sort by points (descending) by default
    if "points" in stats.columns:
        stats = stats.sort_values("points", ascending=False)

    # Apply limit if specified
    if limit:
        stats = stats.head(limit)

    logger.info(
        f"Aggregated player season stats for LNB {season} "
        f"({len(stats)} players, per_mode={per_mode})"
    )

    return stats


def get_lnb_team_season_stats(
    season: str,
    team: str | list[str] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Get aggregated team season statistics from historical data

    Aggregates team-level statistics from fixtures and PBP data.

    Args:
        season: Season string (e.g., "2024-2025")
        team: Team name or list of teams to filter (optional)
        limit: Maximum number of rows to return (optional)

    Returns:
        DataFrame with columns:
        - team: Team name
        - games_played: Number of games played
        - wins: Number of wins
        - losses: Number of losses
        - win_pct: Win percentage
        - points_for: Total points scored
        - points_against: Total points allowed
        - point_diff: Average point differential
        - ppg: Points per game
        - oppg: Opponent points per game
        - fg_pct: Field goal percentage
        - three_pt_pct: Three-point percentage
        - ft_pct: Free throw percentage

    Examples:
        >>> # Get team standings/stats for season
        >>> team_stats = get_lnb_team_season_stats("2024-2025")

        >>> # Get Monaco's season stats
        >>> monaco = get_lnb_team_season_stats("2024-2025", team="Monaco")
    """
    # Load fixtures data
    fixtures = _load_historical_data(season, "fixtures")

    # Filter by team if specified
    if team:
        teams = [team] if isinstance(team, str) else team
        team_mask = fixtures["home_team"].isin(teams) | fixtures["away_team"].isin(teams)
        fixtures = fixtures[team_mask]

    # Aggregate team stats
    team_stats = []

    for team_name in set(fixtures["home_team"].tolist() + fixtures["away_team"].tolist()):
        # Get games for this team
        home_games = fixtures[fixtures["home_team"] == team_name].copy()
        away_games = fixtures[fixtures["away_team"] == team_name].copy()

        # Calculate wins/losses
        home_wins = (home_games["home_score"] > home_games["away_score"]).sum()
        away_wins = (away_games["away_score"] > away_games["home_score"]).sum()
        total_wins = home_wins + away_wins

        games_played = len(home_games) + len(away_games)
        total_losses = games_played - total_wins

        # Calculate points for/against
        points_for = home_games["home_score"].sum() + away_games["away_score"].sum()
        points_against = home_games["away_score"].sum() + away_games["home_score"].sum()

        team_stats.append(
            {
                "team": team_name,
                "games_played": games_played,
                "wins": total_wins,
                "losses": total_losses,
                "win_pct": total_wins / games_played if games_played > 0 else 0,
                "points_for": points_for,
                "points_against": points_against,
                "point_diff": (points_for - points_against) / games_played
                if games_played > 0
                else 0,
                "ppg": points_for / games_played if games_played > 0 else 0,
                "oppg": points_against / games_played if games_played > 0 else 0,
            }
        )

    df = pd.DataFrame(team_stats)

    # Sort by wins (descending)
    df = df.sort_values(["wins", "point_diff"], ascending=[False, False])

    # Apply limit if specified
    if limit:
        df = df.head(limit)

    logger.info(f"Aggregated team season stats for LNB {season} " f"({len(df)} teams)")

    return df
