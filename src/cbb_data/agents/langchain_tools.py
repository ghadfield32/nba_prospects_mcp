"""
LangChain tool adapters for basketball data access.

Provides drop-in tools for LangChain agents with natural language support
and automatic type conversion.

Installation:
    pip install langchain langchain-core

Usage:
    from cbb_data.agents import get_langchain_tools
    from langchain.agents import initialize_agent, AgentType
    from langchain_openai import ChatOpenAI

    # Get all basketball data tools
    tools = get_langchain_tools()

    # Create agent with tools
    llm = ChatOpenAI(temperature=0)
    agent = initialize_agent(
        tools=tools
        llm=llm
        agent=AgentType.OPENAI_FUNCTIONS
        verbose=True
    )

    # Use agent
    response = agent.run("Show me Duke's schedule this season")
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.pydantic_v1 import BaseModel as LCBaseModel
    from langchain_core.pydantic_v1 import Field as LCField
    from langchain_core.tools import tool

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

    # Define placeholder for when LangChain is not installed
    def tool(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
        def decorator(func: Any) -> Any:  # type: ignore[no-untyped-def]
            return func

        # Handle both @tool and @tool(...) syntax
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

    class LCBaseModel:  # type: ignore[no-redef]
        pass

    def LCField(*args: Any, **kwargs: Any) -> None:  # type: ignore[no-untyped-def]
        return None


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
# LangChain Tool Schemas
# ============================================================================


class GetScheduleInput(LCBaseModel):
    """Input for get_schedule tool."""

    league: str = LCField(description="League: NCAA-MBB, NCAA-WBB, or EuroLeague")
    season: str | None = LCField(None, description="Season year OR 'this season', 'last season'")
    team: list[str] | None = LCField(None, description="List of team names")
    date_from: str | None = LCField(None, description="Start date OR 'yesterday', 'last week'")
    date_to: str | None = LCField(None, description="End date OR 'today'")
    limit: int = LCField(100, description="Max rows to return")
    compact: bool = LCField(True, description="Use compact mode (saves tokens)")


class GetPlayerGameStatsInput(LCBaseModel):
    """Input for get_player_game_stats tool."""

    league: str = LCField(description="League identifier")
    season: str | None = LCField(None, description="Season year OR 'this season'")
    team: list[str] | None = LCField(None, description="Team names")
    player: list[str] | None = LCField(None, description="Player names")
    limit: int = LCField(100, description="Max rows")
    compact: bool = LCField(True, description="Use compact mode")


class GetPlayerSeasonStatsInput(LCBaseModel):
    """Input for get_player_season_stats tool."""

    league: str = LCField(description="League identifier")
    season: str = LCField(description="Season year OR 'this season'")
    team: list[str] | None = LCField(None, description="Team names")
    player: list[str] | None = LCField(None, description="Player names")
    per_mode: str = LCField("PerGame", description="Totals, PerGame, or Per40")
    limit: int = LCField(100, description="Max rows")
    compact: bool = LCField(True, description="Use compact mode")


class GetTeamSeasonStatsInput(LCBaseModel):
    """Input for get_team_season_stats tool."""

    league: str = LCField(description="League identifier")
    season: str = LCField(description="Season year OR 'this season'")
    team: list[str] | None = LCField(None, description="Team names")
    limit: int = LCField(100, description="Max rows")
    compact: bool = LCField(True, description="Use compact mode")


class GetRecentGamesInput(LCBaseModel):
    """Input for get_recent_games tool."""

    league: str = LCField(description="League identifier")
    days: str = LCField("2", description="Number of days OR 'today', 'last week'")
    teams: list[str] | None = LCField(None, description="Team names")
    compact: bool = LCField(True, description="Use compact mode")


# ============================================================================
# LangChain Tool Wrappers
# ============================================================================


@tool("get_schedule", args_schema=GetScheduleInput)
def langchain_get_schedule(
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

    Examples:
        • "Duke's schedule this season"
        • "Games yesterday"
        • "Last week's NCAA-MBB games"

    Accepts natural language:
        - season: "this season", "last season", "2024-25"
        - dates: "yesterday", "last week", "3 days ago"
    """
    result = tool_get_schedule(league, season, team, date_from, date_to, limit, compact)

    # Format result for LLM consumption
    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


@tool("get_player_game_stats", args_schema=GetPlayerGameStatsInput)
def langchain_get_player_game_stats(
    league: str,
    season: str | None = None,
    team: list[str] | None = None,
    player: list[str] | None = None,
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get per-player per-game box score statistics.

    Examples:
        • "Cooper Flagg's recent games"
        • "Duke players' last 10 games"

    Accepts natural language:
        - season: "this season", "last season"
    """
    result = tool_get_player_game_stats(league, season, team, player, None, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


@tool("get_player_season_stats", args_schema=GetPlayerSeasonStatsInput)
def langchain_get_player_season_stats(
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

    Examples:
        • "Top scorers this season"
        • "Duke players' season averages"

    Use per_mode='PerGame' for fair comparisons.
    """
    result = tool_get_player_season_stats(league, season, team, player, per_mode, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


@tool("get_team_season_stats", args_schema=GetTeamSeasonStatsInput)
def langchain_get_team_season_stats(
    league: str,
    season: str,
    team: list[str] | None = None,
    limit: int = 100,
    compact: bool = True,
) -> str:
    """
    Get per-team season aggregate statistics and standings.

    Examples:
        • "Team standings this season"
        • "ACC teams' records"
    """
    result = tool_get_team_season_stats(league, season, team, None, limit, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


@tool("get_recent_games", args_schema=GetRecentGamesInput)
def langchain_get_recent_games(
    league: str, days: str = "2", teams: list[str] | None = None, compact: bool = True
) -> str:
    """
    Get recent games with natural language day support.

    Examples:
        • "Games today"
        • "Last week's games"
        • "Duke's recent games"

    Accepts natural language:
        - days: "today", "yesterday", "last week", "last 5 days"
    """
    result = tool_get_recent_games(league, days, teams, compact)

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


@tool("list_datasets")
def langchain_list_datasets() -> str:
    """
    List all available datasets with their metadata.

    Returns information about all datasets including supported filters and leagues.
    """
    result = tool_list_datasets()

    if result.get("success"):
        return _format_result(result)
    else:
        return f"Error: {result.get('error')}"


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
# Main Function
# ============================================================================


def get_langchain_tools() -> list:
    """
    Get all LangChain basketball data tools.

    Returns:
        List of LangChain tools ready for agent use

    Raises:
        ImportError: If langchain is not installed

    Examples:
        >>> tools = get_langchain_tools()
        >>> print(f"Loaded {len(tools)} tools")
        Loaded 6 tools

        >>> # Use with LangChain agent
        >>> from langchain.agents import initialize_agent, AgentType
        >>> from langchain_openai import ChatOpenAI
        >>>
        >>> llm = ChatOpenAI(temperature=0)
        >>> agent = initialize_agent(
        ...     tools=tools
        ...     llm=llm
        ...     agent=AgentType.OPENAI_FUNCTIONS
        ... )
        >>>
        >>> agent.run("Show me Duke's schedule this season")
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            "LangChain is not installed. Install with: pip install langchain langchain-core"
        )

    return [
        langchain_get_schedule,
        langchain_get_player_game_stats,
        langchain_get_player_season_stats,
        langchain_get_team_season_stats,
        langchain_get_recent_games,
        langchain_list_datasets,
    ]


# Example usage
if __name__ == "__main__":
    if LANGCHAIN_AVAILABLE:
        tools = get_langchain_tools()
        print(f"Successfully loaded {len(tools)} LangChain tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:60]}...")
    else:
        print("LangChain is not installed. Install with: pip install langchain langchain-core")
