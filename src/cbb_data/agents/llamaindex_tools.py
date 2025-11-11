"""
LlamaIndex tool adapters for basketball data access.

Provides drop-in tools for LlamaIndex agents with natural language support
and automatic type conversion.

Installation:
    pip install llama-index llama-index-core

Usage:
    from cbb_data.agents import get_llamaindex_tools
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI

    # Get all basketball data tools
    tools = get_llamaindex_tools()

    # Create agent with tools
    llm = OpenAI(model="gpt-4")
    agent = ReActAgent.from_tools(
        tools=tools
        llm=llm
        verbose=True
    )

    # Use agent
    response = agent.chat("Show me Duke's schedule this season")
"""

from __future__ import annotations

from typing import Any

try:
    from llama_index.core.tools import FunctionTool

    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    FunctionTool = None

# Import MCP tools
from cbb_data.servers.mcp.tools import (
    tool_get_player_game_stats,
    tool_get_player_season_stats,
    tool_get_recent_games,
    tool_get_schedule,
    tool_get_team_season_stats,
    tool_list_datasets,
)

# ============================================================================
# Helper Functions
# ============================================================================


def _format_result(result: dict[str, Any]) -> str:
    """Format result for LLM consumption."""
    data = result.get("data")

    # Handle compact mode (dict with columns/rows)
    if isinstance(data, dict) and "columns" in data and "rows" in data:
        columns = data["columns"]
        rows = data["rows"]
        row_count = result.get("row_count", len(rows))

        # Format as markdown table for LLM
        if not rows:
            return "No data found."

        # Header
        output = "| " + " | ".join(str(c) for c in columns) + " |\n"
        output += "| " + " | ".join("---" for _ in columns) + " |\n"

        # Rows (limit to first 50 for readability)
        display_rows = rows[:50]
        for row in display_rows:
            output += "| " + " | ".join(str(v) for v in row) + " |\n"

        if len(rows) > 50:
            output += f"\n... ({row_count} total rows, showing first 50)"

        return output

    # Handle markdown format
    if isinstance(data, str):
        return data

    # Fallback
    return str(data)


# ============================================================================
# LlamaIndex Tool Wrappers
# ============================================================================


def llamaindex_get_schedule(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get game schedules and results with natural language support.

    Args:
        league: League identifier (NCAA-MBB, NCAA-WBB, EuroLeague)
        season: Season year OR 'this season', 'last season', '2024-25'
        team: List of team names to filter
        date_from: Start date OR 'yesterday', 'last week', '3 days ago'
        date_to: End date OR 'today'
        limit: Maximum rows to return (default: 100)
        compact: Use compact mode to save tokens (default: True)

    Returns:
        Game schedule data formatted as markdown table

    Examples:
        • "Duke's schedule this season" → league="NCAA-MBB", season="this season", team=["Duke"]
        • "Games yesterday" → league="NCAA-MBB", date_from="yesterday", date_to="yesterday"
    """
    result = tool_get_schedule(league, season, team, date_from, date_to, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


def llamaindex_get_player_game_stats(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    player: list[str] | None = None,
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get per-player per-game box score statistics.

    Args:
        league: League identifier
        season: Season year OR 'this season', 'last season'
        team: Team names to filter
        player: Player names to filter
        limit: Max rows (default: 100)
        compact: Use compact mode (default: True)

    Returns:
        Player game statistics as markdown table

    Examples:
        • "Cooper Flagg's recent games"
        • "Duke players' last 10 games"
    """
    result = tool_get_player_game_stats(league, season, team, player, None, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


def llamaindex_get_player_season_stats(
    league: str,
    season: str,
    team: list[str] | None = None,
    player: list[str] | None = None,
    per_mode: str = "PerGame",
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get per-player season aggregate statistics.

    Args:
        league: League identifier
        season: Season year OR 'this season', 'last season'
        team: Team names to filter
        player: Player names to filter
        per_mode: Aggregation mode - Totals, PerGame (default), or Per40
        limit: Max rows (default: 100)
        compact: Use compact mode (default: True)

    Returns:
        Player season statistics as markdown table

    Examples:
        • "Top scorers this season" → per_mode="PerGame", limit=20
        • "Duke players' season averages"
    """
    result = tool_get_player_season_stats(league, season, team, player, per_mode, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


def llamaindex_get_team_season_stats(
    league: str,
    season: str,
    team: list[str] | None = None,
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get per-team season aggregate statistics and standings.

    Args:
        league: League identifier
        season: Season year OR 'this season', 'last season'
        team: Team names to filter
        limit: Max rows (default: 100)
        compact: Use compact mode (default: True)

    Returns:
        Team season statistics as markdown table

    Examples:
        • "Team standings this season"
        • "ACC teams' records"
    """
    result = tool_get_team_season_stats(league, season, team, None, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


def llamaindex_get_recent_games(
    league: str, days: str = "2", teams: list[str] | None = None, compact: bool = True
) -> str:
    """
    Get recent games with natural language day support.

    Args:
        league: League identifier
        days: Number of days OR 'today', 'yesterday', 'last week', 'last 5 days'
        teams: Team names to filter
        compact: Use compact mode (default: True)

    Returns:
        Recent games as markdown table

    Examples:
        • "Games today" → days="today"
        • "Last week's games" → days="last week"
        • "Duke's recent games" → teams=["Duke"], days="last 5 days"
    """
    result = tool_get_recent_games(league, days, teams, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


def llamaindex_list_datasets() -> str:
    """
    List all available datasets with their metadata.

    Returns:
        Dataset information including supported filters and leagues

    Examples:
        • "What datasets are available?"
    """
    result = tool_list_datasets()

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


# ============================================================================
# Main Function
# ============================================================================


def get_llamaindex_tools() -> list:
    """
    Get all LlamaIndex basketball data tools.

    Returns:
        List of LlamaIndex FunctionTool objects ready for agent use

    Raises:
        ImportError: If llama-index is not installed

    Examples:
        >>> tools = get_llamaindex_tools()
        >>> print(f"Loaded {len(tools)} tools")
        Loaded 6 tools

        >>> # Use with LlamaIndex agent
        >>> from llama_index.core.agent import ReActAgent
        >>> from llama_index.llms.openai import OpenAI
        >>>
        >>> llm = OpenAI(model="gpt-4")
        >>> agent = ReActAgent.from_tools(
        ...     tools=tools
        ...     llm=llm
        ...     verbose=True
        ... )
        >>>
        >>> response = agent.chat("Show me Duke's schedule this season")
        >>> print(response)
    """
    if not LLAMAINDEX_AVAILABLE:
        raise ImportError(
            "LlamaIndex is not installed. Install with: pip install llama-index llama-index-core"
        )

    return [
        FunctionTool.from_defaults(
            fn=llamaindex_get_schedule,
            name="get_schedule",
            description="Get game schedules and results. Accepts natural language for seasons ('this season') and dates ('yesterday', 'last week')",
        ),
        FunctionTool.from_defaults(
            fn=llamaindex_get_player_game_stats,
            name="get_player_game_stats",
            description="Get per-player per-game box score statistics including points, rebounds, assists. Accepts natural language seasons",
        ),
        FunctionTool.from_defaults(
            fn=llamaindex_get_player_season_stats,
            name="get_player_season_stats",
            description="Get per-player season aggregate statistics. Use per_mode='PerGame' for fair comparisons. Accepts natural language seasons",
        ),
        FunctionTool.from_defaults(
            fn=llamaindex_get_team_season_stats,
            name="get_team_season_stats",
            description="Get per-team season aggregate statistics and standings. Accepts natural language seasons",
        ),
        FunctionTool.from_defaults(
            fn=llamaindex_get_recent_games,
            name="get_recent_games",
            description="Get recent games. Accepts natural language for days ('today', 'last week', 'last 5 days')",
        ),
        FunctionTool.from_defaults(
            fn=llamaindex_list_datasets,
            name="list_datasets",
            description="List all available datasets with their metadata, supported filters, and leagues",
        ),
    ]


# Example usage
if __name__ == "__main__":
    if LLAMAINDEX_AVAILABLE:
        tools = get_llamaindex_tools()
        print(f"Successfully loaded {len(tools)} LlamaIndex tools:")
        for tool in tools:
            print(f"  - {tool.metadata.name}: {tool.metadata.description[:60]}...")
    else:
        print("LlamaIndex is not installed. Install with: pip install llama-index llama-index-core")
