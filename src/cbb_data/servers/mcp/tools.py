"""
MCP Tool definitions for basketball data access.

Each tool is a function that wraps the existing get_dataset() or helper
functions, providing an LLM-friendly interface.
"""

import logging
from typing import Any, Dict, List, Optional
import pandas as pd

# Import existing library functions - NO modifications needed!
from cbb_data.api.datasets import get_dataset, list_datasets, get_recent_games

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
    result = df.to_markdown(index=False)

    if truncated:
        result += f"\n\n(Showing first {max_rows} of {len(df)} rows)"

    return result


def _safe_execute(func_name: str, func, **kwargs) -> Dict[str, Any]:
    """
    Safely execute a function and return structured result.

    Args:
        func_name: Name of function being executed
        func: Function to execute
        **kwargs: Arguments to pass to function

    Returns:
        Dict with 'success', 'data', and optional 'error' keys
    """
    try:
        result = func(**kwargs)

        # Format DataFrame results
        if isinstance(result, pd.DataFrame):
            formatted = _format_dataframe_for_llm(result)
            return {
                "success": True,
                "data": formatted,
                "row_count": len(result)
            }
        else:
            return {
                "success": True,
                "data": result
            }

    except Exception as e:
        logger.error(f"Error in {func_name}: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


# ============================================================================
# MCP Tools
# ============================================================================

def tool_get_schedule(
    league: str,
    season: Optional[str] = None,
    team: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get game schedules and results for a league.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025"), optional
        team: List of team names to filter, optional
        date_from: Start date (YYYY-MM-DD), optional
        date_to: End date (YYYY-MM-DD), optional
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with game schedule data

    Examples:
        >>> tool_get_schedule("NCAA-MBB", season="2025", team=["Duke"])
        >>> tool_get_schedule("EuroLeague", date_from="2025-01-01", date_to="2025-01-15")
    """
    filters = {"league": league}

    if season:
        filters["season"] = season
    if team:
        filters["team"] = team
    if date_from or date_to:
        date_filter = {}
        if date_from:
            date_filter["start"] = date_from
        if date_to:
            date_filter["end"] = date_to
        filters["date"] = date_filter

    return _safe_execute(
        "get_schedule",
        get_dataset,
        grouping="schedule",
        filters=filters,
        limit=limit
    )


def tool_get_player_game_stats(
    league: str,
    season: Optional[str] = None,
    team: Optional[List[str]] = None,
    player: Optional[List[str]] = None,
    game_ids: Optional[List[str]] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get per-player per-game box score statistics.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025"), optional
        team: List of team names to filter, optional
        player: List of player names to filter, optional
        game_ids: List of specific game IDs, optional
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with player game statistics

    Examples:
        >>> tool_get_player_game_stats("NCAA-MBB", season="2025", team=["Duke"], limit=10)
        >>> tool_get_player_game_stats("NCAA-MBB", player=["Cooper Flagg"], limit=5)
    """
    filters = {"league": league}

    if season:
        filters["season"] = season
    if team:
        filters["team"] = team
    if player:
        filters["player"] = player
    if game_ids:
        filters["game_ids"] = game_ids

    return _safe_execute(
        "get_player_game_stats",
        get_dataset,
        grouping="player_game",
        filters=filters,
        limit=limit
    )


def tool_get_team_game_stats(
    league: str,
    season: Optional[str] = None,
    team: Optional[List[str]] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get team-level game results and statistics.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025"), optional
        team: List of team names to filter, optional
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with team game statistics
    """
    filters = {"league": league}

    if season:
        filters["season"] = season
    if team:
        filters["team"] = team

    return _safe_execute(
        "get_team_game_stats",
        get_dataset,
        grouping="team_game",
        filters=filters,
        limit=limit
    )


def tool_get_play_by_play(
    league: str,
    game_ids: List[str]
) -> Dict[str, Any]:
    """
    Get play-by-play event data for specific games.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        game_ids: List of game IDs (required)

    Returns:
        Structured result with play-by-play events

    Examples:
        >>> tool_get_play_by_play("NCAA-MBB", game_ids=["401635571"])
    """
    filters = {
        "league": league,
        "game_ids": game_ids
    }

    return _safe_execute(
        "get_play_by_play",
        get_dataset,
        grouping="play_by_play",
        filters=filters
    )


def tool_get_shot_chart(
    league: str,
    game_ids: List[str],
    player: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get shot chart data with X/Y coordinates.

    Args:
        league: League identifier (NCAA-MBB, EuroLeague)
        game_ids: List of game IDs (required)
        player: List of player names to filter, optional

    Returns:
        Structured result with shot location data
    """
    filters = {
        "league": league,
        "game_ids": game_ids
    }

    if player:
        filters["player"] = player

    return _safe_execute(
        "get_shot_chart",
        get_dataset,
        grouping="shots",
        filters=filters
    )


def tool_get_player_season_stats(
    league: str,
    season: str,
    team: Optional[List[str]] = None,
    player: Optional[List[str]] = None,
    per_mode: str = "Totals",
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get per-player season aggregate statistics.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025") - required
        team: List of team names to filter, optional
        player: List of player names to filter, optional
        per_mode: Aggregation mode - "Totals", "PerGame", or "Per40" (default: "Totals")
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with player season statistics

    Examples:
        >>> tool_get_player_season_stats("NCAA-MBB", "2025", per_mode="PerGame", limit=20)
        >>> tool_get_player_season_stats("NCAA-MBB", "2025", team=["Duke"])
    """
    filters = {
        "league": league,
        "season": season,
        "per_mode": per_mode
    }

    if team:
        filters["team"] = team
    if player:
        filters["player"] = player

    return _safe_execute(
        "get_player_season_stats",
        get_dataset,
        grouping="player_season",
        filters=filters,
        limit=limit
    )


def tool_get_team_season_stats(
    league: str,
    season: str,
    team: Optional[List[str]] = None,
    division: Optional[str] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get per-team season aggregate statistics and standings.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025") - required
        team: List of team names to filter, optional
        division: Division filter for NCAA (D1, D2, D3), optional
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with team season statistics
    """
    filters = {
        "league": league,
        "season": season
    }

    if team:
        filters["team"] = team
    if division:
        filters["Division"] = division

    return _safe_execute(
        "get_team_season_stats",
        get_dataset,
        grouping="team_season",
        filters=filters,
        limit=limit
    )


def tool_get_player_team_season(
    league: str,
    season: str,
    player: Optional[List[str]] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Get player statistics split by team (useful for tracking transfers).

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year (e.g., "2025") - required
        player: List of player names to filter, optional
        limit: Maximum rows to return (default: 100)

    Returns:
        Structured result with player×team×season statistics
    """
    filters = {
        "league": league,
        "season": season
    }

    if player:
        filters["player"] = player

    return _safe_execute(
        "get_player_team_season",
        get_dataset,
        grouping="player_team_season",
        filters=filters,
        limit=limit
    )


def tool_list_datasets() -> Dict[str, Any]:
    """
    List all available datasets with their metadata.

    Returns:
        Structured result with list of datasets and their info

    Examples:
        >>> tool_list_datasets()
    """
    return _safe_execute("list_datasets", list_datasets)


def tool_get_recent_games(
    league: str,
    days: int = 2,
    teams: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get recent games for a league (convenience function).

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        days: Number of days to look back (default: 2 = yesterday + today)
        teams: List of team names to filter, optional

    Returns:
        Structured result with recent games

    Examples:
        >>> tool_get_recent_games("NCAA-MBB", days=2)
        >>> tool_get_recent_games("NCAA-MBB", days=7, teams=["Duke", "UNC"])
    """
    return _safe_execute(
        "get_recent_games",
        get_recent_games,
        league=league,
        days=days,
        teams=teams
    )


# ============================================================================
# Tool Registry for MCP Server
# ============================================================================

TOOLS = [
    {
        "name": "get_schedule",
        "description": "Get game schedules and results for a league. Returns game dates, teams, scores, and venues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {
                    "type": "string",
                    "description": "Season year (e.g., '2025')",
                    "pattern": "^20[0-9]{2}$"
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter"
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)",
                    "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)",
                    "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100
                }
            },
            "required": ["league"]
        },
        "handler": tool_get_schedule
    },
    {
        "name": "get_player_game_stats",
        "description": "Get per-player per-game box score statistics including points, rebounds, assists, minutes, shooting percentages, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {
                    "type": "string",
                    "description": "Season year (e.g., '2025')"
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter"
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter"
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific game IDs"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 100
                }
            },
            "required": ["league"]
        },
        "handler": tool_get_player_game_stats
    },
    {
        "name": "get_team_game_stats",
        "description": "Get team-level game results and statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {"type": "string", "description": "Season year"},
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names"
                },
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["league"]
        },
        "handler": tool_get_team_game_stats
    },
    {
        "name": "get_play_by_play",
        "description": "Get play-by-play event data for specific games. Requires game IDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of game IDs (required)"
                }
            },
            "required": ["league", "game_ids"]
        },
        "handler": tool_get_play_by_play
    },
    {
        "name": "get_shot_chart",
        "description": "Get shot chart data with X/Y coordinates for visualization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "game_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of game IDs (required)"
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to filter"
                }
            },
            "required": ["league", "game_ids"]
        },
        "handler": tool_get_shot_chart
    },
    {
        "name": "get_player_season_stats",
        "description": "Get per-player season aggregate statistics. Can return totals, per-game averages, or per-40-minutes stats.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {
                    "type": "string",
                    "description": "Season year (e.g., '2025') - required"
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names"
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names"
                },
                "per_mode": {
                    "type": "string",
                    "enum": ["Totals", "PerGame", "Per40"],
                    "description": "Aggregation mode",
                    "default": "Totals"
                },
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["league", "season"]
        },
        "handler": tool_get_player_season_stats
    },
    {
        "name": "get_team_season_stats",
        "description": "Get per-team season aggregate statistics and standings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {
                    "type": "string",
                    "description": "Season year (required)"
                },
                "team": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names"
                },
                "division": {
                    "type": "string",
                    "enum": ["D1", "D2", "D3", "all"],
                    "description": "Division filter (NCAA only)"
                },
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["league", "season"]
        },
        "handler": tool_get_team_season_stats
    },
    {
        "name": "get_player_team_season",
        "description": "Get player statistics split by team (useful for tracking mid-season transfers).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "season": {
                    "type": "string",
                    "description": "Season year (required)"
                },
                "player": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names"
                },
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["league", "season"]
        },
        "handler": tool_get_player_team_season
    },
    {
        "name": "list_datasets",
        "description": "List all available datasets with their metadata, supported filters, and leagues.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": tool_list_datasets
    },
    {
        "name": "get_recent_games",
        "description": "Convenience function to get recent games for a league without manually specifying dates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "league": {
                    "type": "string",
                    "enum": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
                    "description": "League identifier"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 2 = yesterday + today)",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 30
                },
                "teams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team names to filter"
                }
            },
            "required": ["league"]
        },
        "handler": tool_get_recent_games
    }
]
