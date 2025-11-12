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

# Import natural language parser for LLM-friendly inputs
from cbb_data.utils.natural_language import normalize_filters_for_llm, parse_days_parameter

logger = logging.getLogger(__name__)


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
]
