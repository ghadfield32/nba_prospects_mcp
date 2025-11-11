"""
Pydantic models for MCP tool parameter validation.

These models provide type safety and validation for LLM tool calls,
ensuring parameters are valid before execution.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# Type aliases for common enums
LeagueType = Literal["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
PerModeType = Literal["Totals", "PerGame", "Per40"]
DivisionType = Literal["D1", "D2", "D3", "all"]


class BaseToolArgs(BaseModel):
    """Base model with common parameters."""

    league: LeagueType = Field(
        ...,
        description="League identifier: NCAA-MBB, NCAA-WBB, or EuroLeague"
    )

    compact: bool = Field(
        default=False,
        description="Return arrays instead of markdown (saves ~70% tokens)"
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum rows to return (1-10000)"
    )


class GetScheduleArgs(BaseToolArgs):
    """Parameters for get_schedule tool."""

    season: Optional[str] = Field(
        None,
        description="Season year (e.g., '2025') OR natural language ('this season', 'last season', '2024-25')"
    )

    team: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    date_from: Optional[str] = Field(
        None,
        description="Start date (YYYY-MM-DD) OR natural language ('yesterday', 'last week', '3 days ago')"
    )

    date_to: Optional[str] = Field(
        None,
        description="End date (YYYY-MM-DD) OR natural language"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: Optional[str]) -> Optional[str]:
        """Validate season format if not natural language."""
        if v is None:
            return v

        # Allow natural language
        natural_language_seasons = ["this season", "last season", "current season",
                                     "previous season", "next season", "this year",
                                     "last year", "next year"]
        if v.lower() in natural_language_seasons:
            return v

        # Allow YYYY format
        if v.isdigit() and len(v) == 4 and v.startswith("20"):
            return v

        # Allow YYYY-YY format
        if "-" in v and len(v) == 7:
            return v

        raise ValueError(f"Season must be YYYY format (e.g., '2025'), YYYY-YY format (e.g., '2024-25'), or natural language (e.g., 'this season')")


class GetPlayerGameStatsArgs(BaseToolArgs):
    """Parameters for get_player_game_stats tool."""

    season: Optional[str] = Field(
        None,
        description="Season year OR natural language ('this season', 'last season', '2024-25')"
    )

    team: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    player: Optional[List[str]] = Field(
        None,
        description="List of player names to filter"
    )

    game_ids: Optional[List[str]] = Field(
        None,
        description="List of specific game IDs"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: Optional[str]) -> Optional[str]:
        """Validate season format."""
        return GetScheduleArgs.validate_season(v)


class GetTeamGameStatsArgs(BaseToolArgs):
    """Parameters for get_team_game_stats tool."""

    season: Optional[str] = Field(
        None,
        description="Season year OR natural language"
    )

    team: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: Optional[str]) -> Optional[str]:
        """Validate season format."""
        return GetScheduleArgs.validate_season(v)


class GetPlayByPlayArgs(BaseModel):
    """Parameters for get_play_by_play tool."""

    league: LeagueType = Field(
        ...,
        description="League identifier"
    )

    game_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of game IDs (required, at least one)"
    )

    compact: bool = Field(
        default=False,
        description="Return arrays instead of markdown"
    )


class GetShotChartArgs(BaseModel):
    """Parameters for get_shot_chart tool."""

    league: Literal["NCAA-MBB", "EuroLeague"] = Field(
        ...,
        description="League identifier (shot charts only available for NCAA-MBB and EuroLeague)"
    )

    game_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of game IDs (required)"
    )

    player: Optional[List[str]] = Field(
        None,
        description="List of player names to filter"
    )

    compact: bool = Field(
        default=False,
        description="Return arrays instead of markdown"
    )


class GetPlayerSeasonStatsArgs(BaseToolArgs):
    """Parameters for get_player_season_stats tool."""

    season: str = Field(
        ...,
        description="Season year OR natural language ('this season', 'last season', '2024-25') - required"
    )

    team: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    player: Optional[List[str]] = Field(
        None,
        description="List of player names to filter"
    )

    per_mode: PerModeType = Field(
        default="Totals",
        description="Aggregation mode: 'Totals' (cumulative), 'PerGame' (averages), 'Per40' (per 40 minutes)"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: str) -> str:
        """Validate season format."""
        return GetScheduleArgs.validate_season(v)


class GetTeamSeasonStatsArgs(BaseToolArgs):
    """Parameters for get_team_season_stats tool."""

    season: str = Field(
        ...,
        description="Season year OR natural language - required"
    )

    team: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    division: Optional[DivisionType] = Field(
        None,
        description="Division filter for NCAA: D1, D2, D3, or all"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: str) -> str:
        """Validate season format."""
        return GetScheduleArgs.validate_season(v)


class GetPlayerTeamSeasonArgs(BaseToolArgs):
    """Parameters for get_player_team_season tool."""

    season: str = Field(
        ...,
        description="Season year OR natural language - required"
    )

    player: Optional[List[str]] = Field(
        None,
        description="List of player names to filter"
    )

    @field_validator('season')
    @classmethod
    def validate_season(cls, v: str) -> str:
        """Validate season format."""
        return GetScheduleArgs.validate_season(v)


class GetRecentGamesArgs(BaseModel):
    """Parameters for get_recent_games tool."""

    league: LeagueType = Field(
        ...,
        description="League identifier"
    )

    days: str = Field(
        default="2",
        description="Number of days OR natural language ('today', 'last week', 'last 5 days')"
    )

    teams: Optional[List[str]] = Field(
        None,
        description="List of team names to filter"
    )

    compact: bool = Field(
        default=False,
        description="Return arrays instead of markdown"
    )

    @field_validator('days')
    @classmethod
    def validate_days(cls, v: str) -> str:
        """Validate days parameter."""
        # Allow natural language
        natural_language_days = ["today", "yesterday", "last week", "last month",
                                  "this week", "this month"]
        if v.lower() in natural_language_days:
            return v

        # Allow "last N days" pattern
        if v.lower().startswith("last ") and v.lower().endswith(("day", "days")):
            return v

        # Allow numeric strings
        if v.isdigit():
            days_int = int(v)
            if 1 <= days_int <= 365:
                return v
            raise ValueError("Days must be between 1 and 365")

        raise ValueError(f"Days must be a number (1-365) or natural language like 'today', 'last week', 'last 5 days'")


# Model registry for easy lookup
TOOL_MODELS = {
    "get_schedule": GetScheduleArgs,
    "get_player_game_stats": GetPlayerGameStatsArgs,
    "get_team_game_stats": GetTeamGameStatsArgs,
    "get_play_by_play": GetPlayByPlayArgs,
    "get_shot_chart": GetShotChartArgs,
    "get_player_season_stats": GetPlayerSeasonStatsArgs,
    "get_team_season_stats": GetTeamSeasonStatsArgs,
    "get_player_team_season": GetPlayerTeamSeasonArgs,
    "get_recent_games": GetRecentGamesArgs,
}


def validate_tool_args(tool_name: str, args: dict) -> dict:
    """
    Validate tool arguments using Pydantic models.

    Args:
        tool_name: Name of the tool
        args: Dictionary of arguments to validate

    Returns:
        Validated arguments dictionary

    Raises:
        ValueError: If validation fails with detailed error message

    Examples:
        >>> validate_tool_args("get_schedule", {"league": "NCAA-MBB", "season": "this season"})
        {"league": "NCAA-MBB", "season": "this season", "compact": False, "limit": 100}

        >>> validate_tool_args("get_schedule", {"league": "InvalidLeague"})
        ValueError: League must be one of: NCAA-MBB, NCAA-WBB, EuroLeague
    """
    if tool_name not in TOOL_MODELS:
        # Tool doesn't have validation model, return as-is
        return args

    model_class = TOOL_MODELS[tool_name]

    try:
        # Validate and convert to dict
        validated = model_class(**args)
        return validated.model_dump(exclude_none=True)
    except Exception as e:
        raise ValueError(f"Validation failed for {tool_name}: {str(e)}")


# Example usage for documentation
if __name__ == "__main__":
    print("=== Pydantic Model Validation Examples ===\n")

    # Example 1: Valid schedule query
    print("Example 1: Valid schedule query with natural language")
    try:
        result = validate_tool_args("get_schedule", {
            "league": "NCAA-MBB",
            "season": "this season",
            "date_from": "yesterday"
        })
        print(f"[PASS] Valid: {result}\n")
    except ValueError as e:
        print(f"[FAIL] Invalid: {e}\n")

    # Example 2: Invalid league
    print("Example 2: Invalid league")
    try:
        result = validate_tool_args("get_schedule", {
            "league": "NBA",  # Invalid
            "season": "2025"
        })
        print(f"[PASS] Valid: {result}\n")
    except ValueError as e:
        print(f"[FAIL] Invalid: {e}\n")

    # Example 3: Valid recent games with natural language
    print("Example 3: Valid recent games")
    try:
        result = validate_tool_args("get_recent_games", {
            "league": "NCAA-MBB",
            "days": "last week"
        })
        print(f"[PASS] Valid: {result}\n")
    except ValueError as e:
        print(f"[FAIL] Invalid: {e}\n")

    # Example 4: Invalid limit
    print("Example 4: Invalid limit (too high)")
    try:
        result = validate_tool_args("get_schedule", {
            "league": "NCAA-MBB",
            "limit": 50000  # Too high
        })
        print(f"[PASS] Valid: {result}\n")
    except ValueError as e:
        print(f"[FAIL] Invalid: {e}\n")
