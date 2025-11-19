"""
MCP Tool definitions for basketball data access.

Each tool is a function that wraps the existing get_dataset() or helper
functions, providing an LLM-friendly interface with natural language support.
"""

import logging
from typing import Any

import pandas as pd

# Import existing library functions - NO modifications needed!
from cbb_data.api.datasets import get_dataset, get_recent_games, list_datasets

# Import LNB historical data functions
from cbb_data.api.lnb_historical import (
    get_lnb_historical_fixtures,
    get_lnb_historical_pbp,
    get_lnb_player_season_stats,
    get_lnb_team_season_stats,
)
from cbb_data.api.lnb_historical import (
    list_available_seasons as list_lnb_historical_seasons,
)

# Import natural language parser for LLM-friendly inputs
from cbb_data.utils.natural_language import normalize_filters_for_llm, parse_days_parameter

logger = logging.getLogger(__name__)


# ============================================================================
# Season Readiness Guards
# ============================================================================


def _ensure_lnb_season_ready(season: str) -> None:
    """
    Guard function to ensure LNB season is ready for data access.

    Checks season readiness status and raises clear error if season is not validated.
    This prevents MCP tools from accessing incomplete or unvalidated data.

    Args:
        season: Season string (e.g., "2024-2025")

    Raises:
        ValueError: If season is not ready for modeling or validation hasn't run

    Examples:
        >>> _ensure_lnb_season_ready("2023-2024")  # Ready season - passes
        >>> _ensure_lnb_season_ready("2025-2026")  # Not ready - raises ValueError
    """
    try:
        import json
        from pathlib import Path

        # Load validation status from disk
        # This is the same file the API reads - ensures consistency
        validation_file = (
            Path(__file__).parents[3] / "data" / "raw" / "lnb" / "lnb_last_validation.json"
        )

        if not validation_file.exists():
            raise ValueError(
                "LNB validation status not found. Please run validation first:\n"
                "  uv run python tools/lnb/validate_and_monitor_coverage.py\n"
                "This ensures data quality before access."
            )

        with open(validation_file) as f:
            validation_data = json.load(f)

        # Find the requested season
        season_data = next((s for s in validation_data["seasons"] if s["season"] == season), None)

        if not season_data:
            available = [s["season"] for s in validation_data["seasons"]]
            raise ValueError(
                f"Season '{season}' is not tracked in LNB pipeline.\n"
                f"Available seasons: {', '.join(available)}"
            )

        # Check readiness
        if not season_data["ready_for_modeling"]:
            raise ValueError(
                f"Season '{season}' is NOT READY for data access.\n"
                f"  PBP Coverage: {season_data['pbp_pct']:.1f}% ({season_data['pbp_coverage']}/{season_data['pbp_expected']})\n"
                f"  Shots Coverage: {season_data['shots_pct']:.1f}% ({season_data['shots_coverage']}/{season_data['shots_expected']})\n"
                f"  Critical Issues: {season_data['num_critical_issues']}\n"
                f"\n"
                f"Season must have ≥95% coverage and 0 critical errors.\n"
                f"Run ingestion to complete data: uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons {season}"
            )

        logger.info(
            f"LNB season {season} validated and ready (PBP: {season_data['pbp_pct']:.1f}%, Shots: {season_data['shots_pct']:.1f}%)"
        )

    except ValueError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        raise ValueError(f"Failed to check LNB season readiness: {str(e)}") from e


def _ensure_fiba_season_ready(league: str, season: str) -> None:
    """
    Guard function to ensure FIBA league/season is ready for data access.

    Checks season readiness status and raises clear error if season is not validated.
    Prevents MCP tools from accessing incomplete or unvalidated FIBA data.

    Args:
        league: FIBA league code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")

    Raises:
        ValueError: If season is not ready for modeling or validation hasn't run

    Examples:
        >>> _ensure_fiba_season_ready("LKL", "2023-24")  # Ready - passes
        >>> _ensure_fiba_season_ready("ABA", "2022-23")  # Not ready - raises
    """
    try:
        from cbb_data.validation.fiba import require_fiba_season_ready

        require_fiba_season_ready(league, season, raise_on_not_ready=True)
        logger.info(f"FIBA {league} season {season} validated and ready for access")

    except ValueError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        raise ValueError(f"Failed to check FIBA season readiness: {str(e)}") from e


# ============================================================================
# Helper Functions
# ============================================================================


def _format_dataframe_for_llm(df: pd.DataFrame, max_rows: int = 50) -> str:
    """
    Format DataFrame as a readable string for LLM consumption.

    Args:
        df: Pandas DataFrame to format
        max_rows: Maximum number of rows to include

    Returns:
        Formatted string representation
    """
    if df is None or df.empty:
        return "No data found matching the specified criteria."

    # Limit rows
    if len(df) > max_rows:
        df = df.head(max_rows)
        truncated = True
    else:
        truncated = False

    # Convert to markdown table for readability
    result: str = df.to_markdown(index=False)  # type: ignore[assignment]

    if truncated:
        result += f"\n\n(Showing first {max_rows} of {len(df)} rows)"

    return result


def _safe_execute(
    func_name: str, func: Any, compact: bool = False, **kwargs: Any
) -> dict[str, Any]:
    """
    Safely execute a function and return structured result.

    Args:
        func_name: Name of function being executed
        func: Function to execute
        compact: Return arrays instead of markdown (saves tokens)
        **kwargs: Arguments to pass to function

    Returns:
        Dict with 'success', 'data', and optional 'error' keys
    """
    try:
        result = func(**kwargs)

        # Format DataFrame results
        if isinstance(result, pd.DataFrame):
            if compact:
                # Compact mode: return arrays (70% token savings)
                # Convert datetime columns to strings for JSON serialization
                df_copy = result.copy()
                for col in df_copy.select_dtypes(include=["datetime64", "datetimetz"]).columns:
                    df_copy[col] = df_copy[col].astype(str)

                return {
                    "success": True,
                    "data": {"columns": df_copy.columns.tolist(), "rows": df_copy.values.tolist()},
                    "row_count": len(result),
                }
            else:
                # Regular mode: return markdown table
                formatted = _format_dataframe_for_llm(result)
                return {"success": True, "data": formatted, "row_count": len(result)}
        else:
            return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"Error in {func_name}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ============================================================================
# MCP Tools
# ============================================================================


def tool_get_schedule(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get game schedules and results with natural language support.

    LLM Usage Examples:
        • "Duke's schedule this season"
          → get_schedule(league="NCAA-MBB", season="this season", team=["Duke"])

        • "Games yesterday"
          → get_schedule(league="NCAA-MBB", date_from="yesterday", date_to="yesterday")

        • "Last week's games"
          → get_schedule(league="NCAA-MBB", date_from="last week")

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season", "2024-25")
        team: List of team names to filter, optional
        date_from: Start date OR natural language ("yesterday", "last week")
        date_to: End date OR natural language
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with game schedule data

    Examples:
        >>> tool_get_schedule("NCAA-MBB", season="this season", team=["Duke"])
        >>> tool_get_schedule("EuroLeague", date_from="yesterday", compact=True)
    """
    # Build filters
    filters = {"league": league, "season": season, "team": team}

    # Add date filters if provided
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Normalize natural language (converts "yesterday" → "2025-11-10", etc.)
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_schedule",
        get_dataset,
        compact=compact,
        grouping="schedule",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_get_player_game_stats(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    player: list[str] | None = None,
    game_ids: list[str] | None = None,
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get per-player per-game box score statistics with natural language support.

    LLM Usage Examples:
        • "Cooper Flagg's recent games"
          → get_player_game_stats(league="NCAA-MBB", season="this season", player=["Cooper Flagg"], limit=10)

        • "Duke players' last 5 games"
          → get_player_game_stats(league="NCAA-MBB", season="this season", team=["Duke"], limit=5)

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season", "2024-25")
        team: List of team names to filter, optional
        player: List of player names to filter, optional
        game_ids: List of specific game IDs, optional
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with player game statistics

    Examples:
        >>> tool_get_player_game_stats("NCAA-MBB", season="this season", team=["Duke"], limit=10)
        >>> tool_get_player_game_stats("NCAA-MBB", player=["Cooper Flagg"], compact=True)
    """
    # Build filters
    filters = {
        "league": league,
        "season": season,
        "team": team,
        "player": player,
        "game_ids": game_ids,
    }

    # Normalize natural language
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_player_game_stats",
        get_dataset,
        compact=compact,
        grouping="player_game",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_get_team_game_stats(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get team-level game results and statistics with natural language support.

    LLM Usage Examples:
        • "Duke's game-by-game results this season"
          → get_team_game_stats(league="NCAA-MBB", season="this season", team=["Duke"])

        • "Top 20 team performances"
          → get_team_game_stats(league="NCAA-MBB", season="this season", limit=20, compact=True)

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season")
        team: List of team names to filter, optional
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with team game statistics
    """
    # Build filters
    filters = {"league": league, "season": season, "team": team}

    # Normalize natural language
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_team_game_stats",
        get_dataset,
        compact=compact,
        grouping="team_game",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_get_play_by_play(
    league: str, game_ids: list[str], compact: bool = False, pre_only: bool = True
) -> dict[str, Any]:
    """
    Get play-by-play event data for specific games.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        game_ids: List of game IDs (required)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with play-by-play events

    Examples:
        >>> tool_get_play_by_play("NCAA-MBB", game_ids=["401635571"])
        >>> tool_get_play_by_play("NCAA-MBB", game_ids=["401635571"], compact=True)
    """
    filters = {"league": league, "game_ids": game_ids}

    return _safe_execute(
        "get_play_by_play",
        get_dataset,
        compact=compact,
        grouping="pbp",
        filters=filters,
        pre_only=pre_only,
    )


def tool_get_shot_chart(
    league: str,
    game_ids: list[str],
    player: list[str] | None = None,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get shot chart data with X/Y coordinates.

    Args:
        league: League identifier (NCAA-MBB, EuroLeague)
        game_ids: List of game IDs (required)
        player: List of player names to filter, optional
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with shot location data
    """
    filters = {"league": league, "game_ids": game_ids}

    if player:
        filters["player"] = player

    return _safe_execute(
        "get_shot_chart",
        get_dataset,
        compact=compact,
        grouping="shots",
        filters=filters,
        pre_only=pre_only,
    )


def tool_get_player_season_stats(
    league: str,
    season: str,
    team: list[str] | None = None,
    player: list[str] | None = None,
    per_mode: str = "Totals",
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get per-player season aggregate statistics with natural language support.

    LLM Usage Examples:
        • "Top scorers this season"
          → get_player_season_stats(league="NCAA-MBB", season="this season", per_mode="PerGame", limit=20)

        • "Duke players stats"
          → get_player_season_stats(league="NCAA-MBB", season="this season", team=["Duke"], compact=True)

        • "Last season's top rebounders"
          → get_player_season_stats(league="NCAA-MBB", season="last season", per_mode="PerGame", limit=20)

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season", "2024-25")
        team: List of team names to filter, optional
        player: List of player names to filter, optional
        per_mode: Aggregation mode - "Totals", "PerGame", or "Per40" (default: "Totals")
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with player season statistics

    Tips:
        • Use per_mode="PerGame" for fair comparisons across players
        • Use compact=True for queries returning >50 rows to save tokens
        • Season "2024-25" is automatically parsed to "2025"

    Examples:
        >>> tool_get_player_season_stats("NCAA-MBB", "this season", per_mode="PerGame", limit=20)
        >>> tool_get_player_season_stats("NCAA-MBB", "last season", team=["Duke"], compact=True)
    """
    # Build filters
    filters = {
        "league": league,
        "season": season,
        "team": team,
        "player": player,
        "per_mode": per_mode,
    }

    # Normalize natural language
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_player_season_stats",
        get_dataset,
        compact=compact,
        grouping="player_season",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_get_team_season_stats(
    league: str,
    season: str,
    team: list[str] | None = None,
    division: str | None = None,
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get per-team season aggregate statistics and standings with natural language support.

    LLM Usage Examples:
        • "Team standings this season"
          → get_team_season_stats(league="NCAA-MBB", season="this season", limit=50)

        • "ACC teams stats"
          → get_team_season_stats(league="NCAA-MBB", season="this season", compact=True)

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season", "2024-25")
        team: List of team names to filter, optional
        division: Division filter for NCAA (D1, D2, D3), optional
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with team season statistics
    """
    # Build filters
    filters = {"league": league, "season": season, "team": team}

    if division:
        filters["Division"] = division

    # Normalize natural language
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_team_season_stats",
        get_dataset,
        compact=compact,
        grouping="team_season",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_get_player_team_season(
    league: str,
    season: str,
    player: list[str] | None = None,
    limit: int | None = 100,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get player statistics split by team with natural language support.

    Useful for tracking mid-season transfers and players who played for multiple teams.

    LLM Usage Examples:
        • "Players who transferred this season"
          → get_player_team_season(league="NCAA-MBB", season="this season", compact=True)

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR natural language ("this season", "last season", "2024-25")
        player: List of player names to filter, optional
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with player×team×season statistics
    """
    # Build filters
    filters = {"league": league, "season": season, "player": player}

    # Normalize natural language
    filters = normalize_filters_for_llm(filters)

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    return _safe_execute(
        "get_player_team_season",
        get_dataset,
        compact=compact,
        grouping="player_team_season",
        filters=filters,
        limit=limit,
        pre_only=pre_only,
    )


def tool_list_datasets(pre_only: bool = True) -> dict[str, Any]:
    """
    List all available datasets with their metadata.

    Args:
        pre_only: If True, filter leagues to pre-NBA/WNBA only (default: True)

    Returns:
        Structured result with list of datasets and their info

    Examples:
        >>> tool_list_datasets()
        >>> tool_list_datasets(pre_only=False)  # Include pro leagues
    """
    return _safe_execute("list_datasets", list_datasets, compact=False, pre_only=pre_only)


def tool_get_recent_games(
    league: str,
    days: str | None = "2",
    teams: list[str] | None = None,
    compact: bool = False,
    pre_only: bool = True,
) -> dict[str, Any]:
    """
    Get recent games with natural language day support.

    LLM Usage Examples:
        • "Games today"
          → get_recent_games(league="NCAA-MBB", days="today")

        • "Last week's games"
          → get_recent_games(league="NCAA-MBB", days="last week")

        • "Duke's games from last 5 days"
          → get_recent_games(league="NCAA-MBB", days="last 5 days", teams=["Duke"])

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        days: Number of days OR natural language ("today", "last week", "last 5 days")
              Default: "2" (yesterday + today)
        teams: List of team names to filter, optional
        compact: Return arrays instead of markdown (saves ~70% tokens)
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        Structured result with recent games

    Examples:
        >>> tool_get_recent_games("NCAA-MBB", days="today")
        >>> tool_get_recent_games("NCAA-MBB", days="last week", teams=["Duke", "UNC"])
        >>> tool_get_recent_games("NCAA-MBB", days="7", compact=True)
    """
    # Parse natural language days parameter
    if days is None:
        days_int = 2  # Default fallback
    elif isinstance(days, str):
        parsed = parse_days_parameter(days)
        days_int = parsed if parsed is not None else 2  # Default fallback
    else:
        days_int = int(days)

    return _safe_execute(
        "get_recent_games",
        get_recent_games,
        compact=compact,
        league=league,
        days=days_int,
        teams=teams,
        pre_only=pre_only,
    )


# ============================================================================
# LNB Historical Data Tools
# ============================================================================


def tool_get_lnb_historical_schedule(
    season: str,
    team: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = 100,
    compact: bool = False,
) -> dict[str, Any]:
    """
    Get LNB (French Pro A) historical game schedules and results.

    Accesses ingested historical data from the LNB data pipeline.
    Available seasons: 2015-2016 through 2025-2026 (depending on ingestion status).

    LLM Usage Examples:
        • "LNB games in 2024-2025 season"
          → get_lnb_historical_schedule(season="2024-2025")

        • "Monaco's fixtures in 2024-2025"
          → get_lnb_historical_schedule(season="2024-2025", team=["Monaco"])

        • "LNB games in November 2024"
          → get_lnb_historical_schedule(season="2024-2025", date_from="2024-11-01", date_to="2024-11-30")

    Args:
        season: Season string in YYYY-YYYY format (e.g., "2024-2025", "2025-2026")
        team: List of team names to filter (optional)
        date_from: Filter games from this date (YYYY-MM-DD format, optional)
        date_to: Filter games to this date (YYYY-MM-DD format, optional)
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)

    Returns:
        Structured result with game fixtures and results

    Examples:
        >>> tool_get_lnb_historical_schedule("2024-2025")
        >>> tool_get_lnb_historical_schedule("2024-2025", team=["Monaco", "ASVEL"])
        >>> tool_get_lnb_historical_schedule("2025-2026", date_from="2025-11-01", compact=True)
    """
    # Enforce season readiness before accessing data
    _ensure_lnb_season_ready(season)

    return _safe_execute(
        "get_lnb_historical_schedule",
        get_lnb_historical_fixtures,
        compact=compact,
        season=season,
        division=1,  # Pro A only for now
        team=team,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


def tool_get_lnb_historical_pbp(
    season: str,
    fixture_uuid: list[str] | None = None,
    team: list[str] | None = None,
    player: list[str] | None = None,
    event_type: list[str] | None = None,
    limit: int | None = 500,
    compact: bool = True,
) -> dict[str, Any]:
    """
    Get LNB (French Pro A) historical play-by-play events.

    Accesses detailed event-level data from ingested historical games.

    LLM Usage Examples:
        • "Play-by-play for a specific LNB game"
          → get_lnb_historical_pbp(season="2024-2025", fixture_uuid=["abc-123..."])

        • "All Monaco shot events in 2024-2025"
          → get_lnb_historical_pbp(season="2024-2025", team=["Monaco"], event_type=["SHOT_MADE", "SHOT_MISSED"])

    Args:
        season: Season string (e.g., "2024-2025")
        fixture_uuid: List of game UUIDs to filter (optional)
        team: List of team names to filter (optional)
        player: List of player names to filter (optional)
        event_type: List of event types to filter (optional)
        limit: Maximum rows to return (default: 500)
        compact: Return arrays instead of markdown (default: True for PBP)

    Returns:
        Structured result with play-by-play events

    Examples:
        >>> tool_get_lnb_historical_pbp("2024-2025", fixture_uuid=["abc-123"])
        >>> tool_get_lnb_historical_pbp("2024-2025", team=["Monaco"], limit=1000)
    """
    # Enforce season readiness before accessing data
    _ensure_lnb_season_ready(season)

    return _safe_execute(
        "get_lnb_historical_pbp",
        get_lnb_historical_pbp,
        compact=compact,
        season=season,
        fixture_uuid=fixture_uuid[0] if fixture_uuid and len(fixture_uuid) == 1 else fixture_uuid,
        team=team,
        player=player,
        event_type=event_type,
        limit=limit,
    )


def tool_get_lnb_historical_player_stats(
    season: str,
    per_mode: str = "Totals",
    team: list[str] | None = None,
    player: list[str] | None = None,
    min_games: int = 1,
    limit: int | None = 100,
    compact: bool = False,
) -> dict[str, Any]:
    """
    Get LNB (French Pro A) historical player season statistics.

    Aggregated from play-by-play data into season totals and averages.

    LLM Usage Examples:
        • "Top LNB scorers in 2024-2025"
          → get_lnb_historical_player_stats(season="2024-2025", per_mode="PerGame", limit=20)

        • "Monaco players stats for 2024-2025"
          → get_lnb_historical_player_stats(season="2024-2025", team=["Monaco"])

        • "LNB players with 15+ games in 2023-2024"
          → get_lnb_historical_player_stats(season="2023-2024", min_games=15, per_mode="PerGame")

    Args:
        season: Season string (e.g., "2024-2025")
        per_mode: Aggregation mode - "Totals", "PerGame", or "Per40" (default: "Totals")
        team: List of team names to filter (optional)
        player: List of player names to filter (optional)
        min_games: Minimum games played to include (default: 1)
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (saves ~70% tokens)

    Returns:
        Structured result with player season statistics

    Examples:
        >>> tool_get_lnb_historical_player_stats("2024-2025", per_mode="PerGame", limit=20)
        >>> tool_get_lnb_historical_player_stats("2024-2025", team=["Monaco"], compact=True)
    """
    # Enforce season readiness before accessing data
    _ensure_lnb_season_ready(season)

    return _safe_execute(
        "get_lnb_historical_player_stats",
        get_lnb_player_season_stats,
        compact=compact,
        season=season,
        per_mode=per_mode,  # type: ignore[arg-type]
        team=team,
        player=player,
        min_games=min_games,
        limit=limit,
    )


def tool_get_lnb_historical_team_stats(
    season: str,
    team: list[str] | None = None,
    limit: int | None = 20,
    compact: bool = False,
) -> dict[str, Any]:
    """
    Get LNB (French Pro A) historical team season statistics and standings.

    Aggregated from fixtures and play-by-play data.

    LLM Usage Examples:
        • "LNB standings for 2024-2025"
          → get_lnb_historical_team_stats(season="2024-2025")

        • "Monaco's season stats for 2024-2025"
          → get_lnb_historical_team_stats(season="2024-2025", team=["Monaco"])

    Args:
        season: Season string (e.g., "2024-2025")
        team: List of team names to filter (optional)
        limit: Maximum rows to return (default: 20)
        compact: Return arrays instead of markdown

    Returns:
        Structured result with team season statistics and standings

    Examples:
        >>> tool_get_lnb_historical_team_stats("2024-2025")
        >>> tool_get_lnb_historical_team_stats("2024-2025", team=["Monaco", "ASVEL"])
    """
    # Enforce season readiness before accessing data
    _ensure_lnb_season_ready(season)

    return _safe_execute(
        "get_lnb_historical_team_stats",
        get_lnb_team_season_stats,
        compact=compact,
        season=season,
        team=team,
        limit=limit,
    )


def tool_list_lnb_historical_seasons() -> dict[str, Any]:
    """
    List all LNB (French Pro A) seasons with available historical data.

    Returns:
        List of season strings with ingested historical data

    Examples:
        >>> tool_list_lnb_historical_seasons()
        {'success': True, 'data': ['2025-2026', '2024-2025', '2023-2024', ...]}
    """
    try:
        seasons = list_lnb_historical_seasons()
        return {
            "success": True,
            "data": seasons,
            "count": len(seasons),
        }
    except Exception as e:
        logger.error(f"Error listing LNB historical seasons: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ============================================================================
# FIBA Cluster Data Tools (LKL, ABA, BAL, BCL)
# ============================================================================


def tool_get_fiba_shots(
    league: str,
    season: str,
    team: list[str] | None = None,
    player: list[str] | None = None,
    shot_type: list[str] | None = None,
    shot_made: bool | None = None,
    period: list[int] | None = None,
    limit: int | None = 500,
    compact: bool = True,
) -> dict[str, Any]:
    """
    Get FIBA cluster shot chart data with coordinates and shot outcomes.

    Supports all 4 FIBA cluster leagues: LKL, ABA, BAL, BCL.
    Enforces season readiness before data access.

    LLM Usage Examples:
        • "LKL made 3-pointers in 2023-24"
          → tool_get_fiba_shots("LKL", "2023-24", shot_type=["3PT"], shot_made=True)

        • "Žalgiris Kaunas shots in 2023-24"
          → tool_get_fiba_shots("LKL", "2023-24", team=["Žalgiris Kaunas"])

        • "Crvena Zvezda missed shots in Q4"
          → tool_get_fiba_shots("ABA", "2023-24", team=["Crvena Zvezda"], shot_made=False, period=[4])

    Args:
        league: FIBA league code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")
        team: Filter by team name(s) (optional)
        player: Filter by player name(s) (optional)
        shot_type: Filter by shot type(s): "2PT", "3PT" (optional)
        shot_made: Filter by shot outcome: True (made), False (missed) (optional)
        period: Filter by period/quarter (optional)
        limit: Maximum rows to return (default: 500)
        compact: Return arrays instead of markdown (default: True)

    Returns:
        Dict with shot data, count, and league/season info

    Examples:
        >>> tool_get_fiba_shots("LKL", "2023-24", limit=100)
        >>> tool_get_fiba_shots("ABA", "2023-24", team=["Partizan"], shot_type=["3PT"])
        >>> tool_get_fiba_shots("BAL", "2023-24", shot_made=True, compact=False)
    """
    try:
        # Validate league
        valid_leagues = ["LKL", "ABA", "BAL", "BCL"]
        if league not in valid_leagues:
            return {
                "success": False,
                "error": f"Invalid league: {league}. Valid: {', '.join(valid_leagues)}",
            }

        # Enforce season readiness
        _ensure_fiba_season_ready(league, season)

        # Import appropriate fetcher
        if league == "LKL":
            from cbb_data.fetchers.lkl import fetch_shot_chart
        elif league == "ABA":
            from cbb_data.fetchers.aba import fetch_shot_chart
        elif league == "BAL":
            from cbb_data.fetchers.bal import fetch_shot_chart
        elif league == "BCL":
            from cbb_data.fetchers.bcl import fetch_shot_chart

        # Fetch shot data (with browser scraping enabled)
        shots_df = fetch_shot_chart(season, use_browser=True)

        if shots_df.empty:
            return {
                "success": True,
                "data": [] if compact else "No shots data available",
                "count": 0,
                "league": league,
                "season": season,
            }

        # Apply filters
        if team:
            shots_df = shots_df[shots_df["TEAM_NAME"].isin(team)]

        if player:
            shots_df = shots_df[shots_df["PLAYER_NAME"].isin(player)]

        if shot_type:
            shots_df = shots_df[shots_df["SHOT_TYPE"].isin(shot_type)]

        if shot_made is not None:
            shots_df = shots_df[shots_df["SHOT_MADE"] == shot_made]

        if period:
            shots_df = shots_df[shots_df["PERIOD"].isin(period)]

        # Apply limit
        if limit:
            shots_df = shots_df.head(limit)

        # Format response
        if compact:
            return {
                "success": True,
                "data": shots_df.to_dict("records"),
                "count": len(shots_df),
                "league": league,
                "season": season,
            }
        else:
            return {
                "success": True,
                "data": shots_df.to_markdown(index=False),
                "count": len(shots_df),
                "league": league,
                "season": season,
            }

    except ValueError as e:
        # Season not ready error from guard
        return {
            "success": False,
            "error": str(e),
            "league": league,
            "season": season,
        }
    except Exception as e:
        logger.error(f"Error fetching FIBA shots for {league} {season}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to fetch shots: {str(e)}",
            "error_type": type(e).__name__,
            "league": league,
            "season": season,
        }


def tool_get_fiba_schedule(
    league: str,
    season: str,
    team: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = 100,
    compact: bool = False,
) -> dict[str, Any]:
    """
    Get FIBA cluster game schedule and results.

    Supports all 4 FIBA cluster leagues: LKL, ABA, BAL, BCL.

    LLM Usage Examples:
        • "LKL games in 2023-24"
          → tool_get_fiba_schedule("LKL", "2023-24")

        • "Žalgiris fixtures in 2023-24"
          → tool_get_fiba_schedule("LKL", "2023-24", team=["Žalgiris Kaunas"])

        • "ABA games in November 2023"
          → tool_get_fiba_schedule("ABA", "2023-24", date_from="2023-11-01", date_to="2023-11-30")

    Args:
        league: FIBA league code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")
        team: Filter by team name(s) (optional)
        date_from: Filter games from this date (YYYY-MM-DD, optional)
        date_to: Filter games to this date (YYYY-MM-DD, optional)
        limit: Maximum rows to return (default: 100)
        compact: Return arrays instead of markdown (default: False)

    Returns:
        Dict with schedule data

    Examples:
        >>> tool_get_fiba_schedule("LKL", "2023-24")
        >>> tool_get_fiba_schedule("ABA", "2023-24", team=["Partizan", "Crvena Zvezda"])
    """
    try:
        # Validate league
        valid_leagues = ["LKL", "ABA", "BAL", "BCL"]
        if league not in valid_leagues:
            return {
                "success": False,
                "error": f"Invalid league: {league}. Valid: {', '.join(valid_leagues)}",
            }

        # Import appropriate fetcher
        if league == "LKL":
            from cbb_data.fetchers.lkl import fetch_schedule
        elif league == "ABA":
            from cbb_data.fetchers.aba import fetch_schedule
        elif league == "BAL":
            from cbb_data.fetchers.bal import fetch_schedule
        elif league == "BCL":
            from cbb_data.fetchers.bcl import fetch_schedule

        # Fetch schedule
        schedule_df = fetch_schedule(season)

        if schedule_df.empty:
            return {
                "success": True,
                "data": [] if compact else "No schedule data available",
                "count": 0,
                "league": league,
                "season": season,
            }

        # Apply filters
        if team:
            schedule_df = schedule_df[
                schedule_df["HOME_TEAM"].isin(team) | schedule_df["AWAY_TEAM"].isin(team)
            ]

        if date_from:
            schedule_df["GAME_DATE"] = pd.to_datetime(schedule_df["GAME_DATE"])
            schedule_df = schedule_df[schedule_df["GAME_DATE"] >= date_from]

        if date_to:
            if (
                "GAME_DATE" not in schedule_df.columns
                or schedule_df["GAME_DATE"].dtype != "datetime64[ns]"
            ):
                schedule_df["GAME_DATE"] = pd.to_datetime(schedule_df["GAME_DATE"])
            schedule_df = schedule_df[schedule_df["GAME_DATE"] <= date_to]

        # Apply limit
        if limit:
            schedule_df = schedule_df.head(limit)

        # Format response
        if compact:
            return {
                "success": True,
                "data": schedule_df.to_dict("records"),
                "count": len(schedule_df),
                "league": league,
                "season": season,
            }
        else:
            return {
                "success": True,
                "data": schedule_df.to_markdown(index=False),
                "count": len(schedule_df),
                "league": league,
                "season": season,
            }

    except Exception as e:
        logger.error(f"Error fetching FIBA schedule for {league} {season}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to fetch schedule: {str(e)}",
            "error_type": type(e).__name__,
            "league": league,
            "season": season,
        }


def tool_list_fiba_leagues() -> dict[str, Any]:
    """
    List all available FIBA cluster leagues with readiness status.

    Returns information about supported FIBA leagues and their validation status.

    Returns:
        Dict with league info and readiness status

    Example:
        >>> tool_list_fiba_leagues()
        {
            "success": True,
            "leagues": [
                {"code": "LKL", "name": "Lithuanian Basketball League", "ready": True},
                {"code": "ABA", "name": "Adriatic League", "ready": False},
                ...
            ],
            "count": 4
        }
    """
    try:
        from cbb_data.validation.fiba import get_fiba_validation_status

        # League definitions
        leagues_info = {
            "LKL": "Lithuanian Basketball League",
            "ABA": "Adriatic League",
            "BAL": "Basketball Africa League",
            "BCL": "Basketball Champions League",
        }

        # Get validation status
        try:
            validation = get_fiba_validation_status()
            league_status = {
                league_entry["league"]: league_entry["ready_for_modeling"]
                for league_entry in validation.get("leagues", [])
            }
        except FileNotFoundError:
            league_status = {}

        # Build league list
        leagues = []
        for code, name in leagues_info.items():
            leagues.append(
                {
                    "code": code,
                    "name": name,
                    "ready": league_status.get(code, False),
                }
            )

        return {
            "success": True,
            "leagues": leagues,
            "count": len(leagues),
        }

    except Exception as e:
        logger.error(f"Error listing FIBA leagues: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to list leagues: {str(e)}",
            "error_type": type(e).__name__,
        }


# ============================================================================
# Tool Registry for MCP Server
# ============================================================================

TOOLS = [
    {
        "name": "get_schedule",
        "description": """Get game schedules and results for a league with natural language support.

LLM Usage Examples:
  • "Duke's schedule this season" → get_schedule(league="NCAA-MBB", season="this season", team=["Duke"])
  • "Games yesterday" → get_schedule(league="NCAA-MBB", date_from="yesterday", date_to="yesterday")
  • "Last week's games" → get_schedule(league="NCAA-MBB", date_from="last week")

Accepts natural language:
  - season: "this season", "last season", "2024-25"
  - dates: "yesterday", "last week", "3 days ago"

Tips: Use compact=True for large result sets to save ~70% tokens.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {
                    "type": "string",
                    "description": "Season year (e.g., '2025') OR natural language ('this season', 'last season', '2024-25')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD) OR natural language ('yesterday', 'last week')",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD) OR natural language",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown (saves ~70% tokens)",
                    "default": False,
                },
            },
            "required": ["league"],
        },
        "handler": tool_get_schedule,
    },
    {
        "name": "get_player_game_stats",
        "description": """Get per-player per-game box score statistics with natural language support.

LLM Usage Examples:
  • "Cooper Flagg's recent games" → get_player_game_stats(league="NCAA-MBB", season="this season", player=["Cooper Flagg"], limit=10)
  • "Duke players' last 5 games" → get_player_game_stats(league="NCAA-MBB", season="this season", team=["Duke"], limit=5)

Accepts natural language:
  - season: "this season", "last season", "2024-25"

Returns: Points, rebounds, assists, minutes, shooting percentages, and more per game.

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {
                    "type": "string",
                    "description": "Season year OR natural language ('this season', 'last season')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter",
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific game IDs",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league"],
        },
        "handler": tool_get_player_game_stats,
    },
    {
        "name": "get_team_game_stats",
        "description": """Get team-level game results and statistics with natural language support.

LLM Usage Examples:
  • "Duke's game results this season" → get_team_game_stats(league="NCAA-MBB", season="this season", team=["Duke"])

Accepts natural language:
  - season: "this season", "last season"

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {"type": "string", "description": "Season year OR natural language"},
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names",
                },
                "limit": {"type": "integer", "default": 100},
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league"],
        },
        "handler": tool_get_team_game_stats,
    },
    {
        "name": "get_play_by_play",
        "description": "Get play-by-play event data for specific games. Requires game IDs. Use compact=True for large event sequences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of game IDs (required)",
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league", "game_ids"],
        },
        "handler": tool_get_play_by_play,
    },
    {
        "name": "get_shot_chart",
        "description": "Get shot chart data with X/Y coordinates for visualization. Use compact=True for large shot datasets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of game IDs (required)",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter",
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league", "game_ids"],
        },
        "handler": tool_get_shot_chart,
    },
    {
        "name": "get_player_season_stats",
        "description": """Get per-player season aggregate statistics with natural language support.

LLM Usage Examples:
  • "Top scorers this season" → get_player_season_stats(league="NCAA-MBB", season="this season", per_mode="PerGame", limit=20)
  • "Duke players stats" → get_player_season_stats(league="NCAA-MBB", season="this season", team=["Duke"])
  • "Last season's leaders" → get_player_season_stats(league="NCAA-MBB", season="last season", per_mode="PerGame", limit=20)

Accepts natural language:
  - season: "this season", "last season", "2024-25"
  - Per-modes: "Totals" (cumulative), "PerGame" (averages), "Per40" (per 40 min)

Tips:
  • Use per_mode="PerGame" for fair comparisons across players
  • Use compact=True for queries returning >50 rows
  • Basketball seasons are named by ending year (2024-25 = "2025")""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {
                    "type": "string",
                    "description": "Season year OR natural language ('this season', 'last season', '2024-25')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names",
                },
                "per_mode": {
                    "type": "string",
                    "enum": ["Totals", "PerGame", "Per40"],
                    "description": "Aggregation mode: Totals (cumulative), PerGame (averages), Per40 (per 40 minutes)",
                    "default": "Totals",
                },
                "limit": {"type": "integer", "default": 100},
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown (saves ~70% tokens)",
                    "default": False,
                },
            },
            "required": ["league", "season"],
        },
        "handler": tool_get_player_season_stats,
    },
    {
        "name": "get_team_season_stats",
        "description": """Get per-team season aggregate statistics and standings with natural language support.

LLM Usage Examples:
  • "Team standings this season" → get_team_season_stats(league="NCAA-MBB", season="this season")
  • "Last season's top teams" → get_team_season_stats(league="NCAA-MBB", season="last season", limit=25)

Accepts natural language:
  - season: "this season", "last season", "2024-25"

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {"type": "string", "description": "Season year OR natural language"},
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names",
                },
                "division": {
                    "type": "string",
                    "enum": ["D1", "D2", "D3", "all"],
                    "description": "Division filter (NCAA only)",
                },
                "limit": {"type": "integer", "default": 100},
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league", "season"],
        },
        "handler": tool_get_team_season_stats,
    },
    {
        "name": "get_player_team_season",
        "description": """Get player statistics split by team with natural language support. Useful for tracking mid-season transfers.

LLM Usage Examples:
  • "Players who transferred this season" → get_player_team_season(league="NCAA-MBB", season="this season")

Accepts natural language:
  - season: "this season", "last season", "2024-25"

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "season": {"type": "string", "description": "Season year OR natural language"},
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names",
                },
                "limit": {"type": "integer", "default": 100},
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league", "season"],
        },
        "handler": tool_get_player_team_season,
    },
    {
        "name": "list_datasets",
        "description": "List all available datasets with their metadata, supported filters, and leagues.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_list_datasets,
    },
    {
        "name": "get_recent_games",
        "description": """Get recent games with natural language day support. Convenience function for quick lookups.

LLM Usage Examples:
  • "Games today" → get_recent_games(league="NCAA-MBB", days="today")
  • "Last week's games" → get_recent_games(league="NCAA-MBB", days="last week")
  • "Duke's recent games" → get_recent_games(league="NCAA-MBB", days="last 5 days", teams=["Duke"])

Accepts natural language:
  - days: "today", "yesterday", "last week", "last 5 days", or any number

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier",
                },
                "days": {
                    "type": "string",
                    "description": "Number of days OR natural language ('today', 'last week', 'last 5 days')",
                    "default": "2",
                },
                "teams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league"],
        },
        "handler": tool_get_recent_games,
    },
    # ==========================================================================
    # LNB Historical Data Tools (French Pro A)
    # ==========================================================================
    {
        "name": "get_lnb_historical_schedule",
        "description": """Get LNB (French Pro A) historical game schedules and results.

LLM Usage Examples:
  • "LNB games in 2024-2025 season" → get_lnb_historical_schedule(season="2024-2025")
  • "Monaco's fixtures in 2024-2025" → get_lnb_historical_schedule(season="2024-2025", team=["Monaco"])
  • "LNB games in November 2024" → get_lnb_historical_schedule(season="2024-2025", date_from="2024-11-01", date_to="2024-11-30")

Accesses ingested historical data from 2015-2016 through 2025-2026 seasons.
Returns: Game dates, teams, scores, status, PBP availability.

Tips: Use compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "season": {
                    "type": "string",
                    "description": "Season string in YYYY-YYYY format (e.g., '2024-2025', '2025-2026')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter (e.g., ['Monaco', 'ASVEL'])",
                },
                "date_from": {
                    "type": "string",
                    "description": "Filter games from this date (YYYY-MM-DD format)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Filter games to this date (YYYY-MM-DD format)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown (saves ~70% tokens)",
                    "default": False,
                },
            },
            "required": ["season"],
        },
        "handler": tool_get_lnb_historical_schedule,
    },
    {
        "name": "get_lnb_historical_pbp",
        "description": """Get LNB (French Pro A) historical play-by-play events.

LLM Usage Examples:
  • "Play-by-play for a specific LNB game" → get_lnb_historical_pbp(season="2024-2025", fixture_uuid=["abc-123..."])
  • "All Monaco shot events in 2024-2025" → get_lnb_historical_pbp(season="2024-2025", team=["Monaco"], event_type=["SHOT_MADE", "SHOT_MISSED"])

Accesses detailed event-level data from ingested historical games.
Returns: Event type, time, team, player, score, coordinates.

Tips: PBP data is large - use compact=True (default) and filter by fixture_uuid or team.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "season": {
                    "type": "string",
                    "description": "Season string (e.g., '2024-2025')",
                },
                "fixture_uuid": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of game UUIDs to filter",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter",
                },
                "event_type": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of event types to filter (e.g., ['SHOT_MADE', 'REBOUND'])",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 500,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown (recommended for PBP)",
                    "default": True,
                },
            },
            "required": ["season"],
        },
        "handler": tool_get_lnb_historical_pbp,
    },
    {
        "name": "get_lnb_historical_player_stats",
        "description": """Get LNB (French Pro A) historical player season statistics.

LLM Usage Examples:
  • "Top LNB scorers in 2024-2025" → get_lnb_historical_player_stats(season="2024-2025", per_mode="PerGame", limit=20)
  • "Monaco players stats for 2024-2025" → get_lnb_historical_player_stats(season="2024-2025", team=["Monaco"])
  • "LNB players with 15+ games" → get_lnb_historical_player_stats(season="2023-2024", min_games=15, per_mode="PerGame")

Aggregated from play-by-play data into season totals and averages.
Returns: Points, rebounds, assists, shooting percentages, minutes, and more.

Per-modes: "Totals" (cumulative), "PerGame" (averages), "Per40" (per 40 min)
Tips: Use per_mode="PerGame" for fair comparisons, compact=True for large result sets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "season": {
                    "type": "string",
                    "description": "Season string (e.g., '2024-2025')",
                },
                "per_mode": {
                    "type": "string",
                    "enum": ["Totals", "PerGame", "Per40"],
                    "description": "Aggregation mode: Totals (cumulative), PerGame (averages), Per40 (per 40 minutes)",
                    "default": "Totals",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter",
                },
                "min_games": {
                    "type": "integer",
                    "description": "Minimum games played to include",
                    "default": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["season"],
        },
        "handler": tool_get_lnb_historical_player_stats,
    },
    {
        "name": "get_lnb_historical_team_stats",
        "description": """Get LNB (French Pro A) historical team season statistics and standings.

LLM Usage Examples:
  • "LNB standings for 2024-2025" → get_lnb_historical_team_stats(season="2024-2025")
  • "Monaco's season stats for 2024-2025" → get_lnb_historical_team_stats(season="2024-2025", team=["Monaco"])

Aggregated from fixtures and play-by-play data.
Returns: Wins, losses, win%, points for/against, point differential, PPG, etc.

Tips: Great for viewing league standings and team performance.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "season": {
                    "type": "string",
                    "description": "Season string (e.g., '2024-2025')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 20,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["season"],
        },
        "handler": tool_get_lnb_historical_team_stats,
    },
    {
        "name": "list_lnb_historical_seasons",
        "description": """List all LNB (French Pro A) seasons with available historical data.

Use this to discover which seasons have been ingested and are available for querying.
Returns: List of season strings (e.g., ['2025-2026', '2024-2025', '2023-2024', ...])

LLM Usage: Call this first to discover available LNB seasons before querying data.""",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_list_lnb_historical_seasons,
    },
    # ==========================================================================
    # FIBA Cluster Data Tools (LKL, ABA, BAL, BCL)
    # ==========================================================================
    {
        "name": "get_fiba_shots",
        "description": """Get FIBA cluster shot chart data with coordinates and shot outcomes.

Supports all 4 FIBA cluster leagues: LKL (Lithuania), ABA (Adriatic), BAL (Africa), BCL (Champions).
Enforces season readiness validation before data access.

LLM Usage Examples:
  • "LKL made 3-pointers in 2023-24" → get_fiba_shots("LKL", "2023-24", shot_type=["3PT"], shot_made=True)
  • "Žalgiris Kaunas shots in 2023-24" → get_fiba_shots("LKL", "2023-24", team=["Žalgiris Kaunas"])
  • "Crvena Zvezda missed shots in Q4" → get_fiba_shots("ABA", "2023-24", team=["Crvena Zvezda"], shot_made=False, period=[4])

Returns: Shot coordinates (SHOT_X, SHOT_Y), shot type (2PT/3PT), made/missed, player, team, period.

Tips: Uses browser scraping for reliable access. compact=True recommended for large datasets.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["LKL", "ABA", "BAL", "BCL"],
                    "description": "FIBA league code: LKL (Lithuania), ABA (Adriatic), BAL (Africa), BCL (Champions)",
                },
                "season": {
                    "type": "string",
                    "description": "Season string (e.g., '2023-24')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by team name(s) (optional)",
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by player name(s) (optional)",
                },
                "shot_type": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["2PT", "3PT"]},
                    "description": "Filter by shot type: 2PT or 3PT (optional)",
                },
                "shot_made": {
                    "type": "boolean",
                    "description": "Filter by shot outcome: true (made), false (missed) (optional)",
                },
                "period": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Filter by quarter/period (1-4, 5+ for OT) (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 500,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown (recommended for shots)",
                    "default": True,
                },
            },
            "required": ["league", "season"],
        },
        "handler": tool_get_fiba_shots,
    },
    {
        "name": "get_fiba_schedule",
        "description": """Get FIBA cluster game schedule and results.

Supports all 4 FIBA cluster leagues: LKL (Lithuania), ABA (Adriatic), BAL (Africa), BCL (Champions).

LLM Usage Examples:
  • "LKL games in 2023-24" → get_fiba_schedule("LKL", "2023-24")
  • "Žalgiris fixtures in 2023-24" → get_fiba_schedule("LKL", "2023-24", team=["Žalgiris Kaunas"])
  • "ABA games in November 2023" → get_fiba_schedule("ABA", "2023-24", date_from="2023-11-01", date_to="2023-11-30")

Returns: Game dates, teams, scores, status.

Tips: Use date filters for specific time periods.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["LKL", "ABA", "BAL", "BCL"],
                    "description": "FIBA league code: LKL (Lithuania), ABA (Adriatic), BAL (Africa), BCL (Champions)",
                },
                "season": {
                    "type": "string",
                    "description": "Season string (e.g., '2023-24')",
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by team name(s) (optional)",
                },
                "date_from": {
                    "type": "string",
                    "description": "Filter games from this date (YYYY-MM-DD format, optional)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Filter games to this date (YYYY-MM-DD format, optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100,
                },
                "compact": {
                    "type": "boolean",
                    "description": "Return arrays instead of markdown",
                    "default": False,
                },
            },
            "required": ["league", "season"],
        },
        "handler": tool_get_fiba_schedule,
    },
    {
        "name": "list_fiba_leagues",
        "description": """List all available FIBA cluster leagues with readiness status.

Returns information about supported FIBA leagues and their validation status.

LLM Usage: Call this to discover which FIBA leagues are available and ready for data access.

Returns:
  - code: League code (LKL, ABA, BAL, BCL)
  - name: Full league name
  - ready: Boolean indicating if league has passed validation (>= 95% coverage)""",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_list_fiba_leagues,
    },
]
