"""Filter specifications for college and international basketball datasets

This module defines the FilterSpec model that normalizes all query filters
across different data sources (NCAA, EuroLeague, FIBA, NBL, etc.)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

# Type definitions for common enums
SeasonType = Literal[
    "Regular Season", "Playoffs", "Conference Tournament", "Pre Season", "All Star"
]
PerMode = Literal["Totals", "PerGame", "Per40"]  # Per48 not currently implemented in aggregators
League = Literal[
    # NCAA Basketball
    "NCAA-MBB",  # NCAA Men's Basketball (Division I)
    "NCAA-WBB",  # NCAA Women's Basketball (Division I)
    "NCAA-MBB-D2",  # Division II Men
    "NCAA-MBB-D3",  # Division III Men
    "NCAA-WBB-D2",  # Division II Women
    "NCAA-WBB-D3",  # Division III Women
    # NBA Development
    "G-League",  # NBA G League
    # European Professional
    "EuroLeague",  # EuroLeague
    "EuroCup",  # EuroCup
    "ACB",  # Spanish Liga ACB
    "LNB",  # French LNB Pro A
    "LNB_PROA",  # French LNB Pro A (alternative identifier)
    "LNB_ELITE2",  # French LNB Pro B (Elite 2)
    "LNB_ESPOIRS_ELITE",  # French LNB Espoirs Elite (U21 top-tier youth)
    "LNB_ESPOIRS_PROB",  # French LNB Espoirs Pro B (U21 second-tier youth)
    "BBL",  # German Basketball Bundesliga
    "BSL",  # Turkish Basketball Super League
    "LBA",  # Italian Lega Basket Serie A
    "BCL",  # Basketball Champions League
    "ABA",  # ABA League (Adriatic)
    "BAL",  # Basketball Africa League
    "LKL",  # LKL Lithuania
    # International
    "NBL",  # Australia NBL
    "NZ-NBL",  # New Zealand NBL
    "FIBA",  # FIBA competitions (World Cup, Olympics, etc.)
    # North American Alternative
    "OTE",  # Overtime Elite
    "CEBL",  # Canadian Elite Basketball League
    "U-SPORTS",  # U SPORTS (Canada)
    "NJCAA",  # National Junior College Athletic Association
    "NAIA",  # National Association of Intercollegiate Athletics
]


class DateSpan(BaseModel):
    """Date range for filtering games"""

    model_config = ConfigDict(populate_by_name=True)

    start: date | None = Field(default=None, alias="from", description="Start date (inclusive)")
    end: date | None = Field(default=None, alias="to", description="End date (inclusive)")

    @field_validator("end")
    @classmethod
    def _validate_order(cls, v: date | None, info: Any) -> date | None:
        """Ensure end date is not before start date"""
        start = info.data.get("start")
        if v and start and v < start:
            raise ValueError("date.to must be >= date.from")
        return v


class FilterSpec(BaseModel):
    """Unified filter specification for all basketball datasets

    This spec is designed to work across NCAA, EuroLeague, FIBA, NBL, and other sources.
    Not all filters apply to all sources; the compiler will handle source-specific mappings.

    Examples:
        # NCAA Men's Basketball - Duke games in 2024-25 regular season
        >>> FilterSpec(
        ...     league="NCAA-MBB",
        ...     season="2024-25",
        ...     season_type="Regular Season",
        ...     team=["Duke"]
        ... )

        # EuroLeague - Barcelona home games
        >>> FilterSpec(
        ...     league="EuroLeague",
        ...     season="2024",
        ...     team=["Barcelona"],
        ...     home_away="Home"
        ... )

        # Player-level filter - all UConn games for specific player
        >>> FilterSpec(
        ...     league="NCAA-WBB",
        ...     season="2024-25",
        ...     team=["Connecticut"],
        ...     player=["Paige Bueckers"]
        ... )
    """

    # League/competition
    league: League | None = Field(default=None, description="Basketball league or competition")

    # Season & timing
    season: str | None = Field(
        default=None,
        description="Season identifier (e.g., '2024-25' for NCAA, '2024' for EuroLeague)",
    )
    season_type: SeasonType | None = Field(
        default="Regular Season",
        validation_alias=AliasChoices("season_type", "SeasonType"),
        description="Type of season/competition phase",
    )
    date: DateSpan | None = Field(default=None, description="Date range for games")

    # NCAA-specific
    conference: str | None = Field(
        default=None, description="NCAA conference (e.g., 'ACC', 'Big Ten', 'SEC')"
    )
    division: Literal["D-I", "D-II", "D-III"] | None = Field(
        default=None, description="NCAA division (defaults to D-I if league is NCAA-*)"
    )
    tournament: str | None = Field(
        default=None,
        description="Tournament name (e.g., 'NCAA Tournament', 'NIT', 'EuroLeague Playoffs')",
    )

    # Team filters
    team_ids: list[int] | None = Field(
        default=None, description="List of team IDs (source-specific)"
    )
    team: list[str] | None = Field(
        default=None, description="List of team names (resolved to IDs via entity resolver)"
    )
    opponent_ids: list[int] | None = Field(default=None, description="List of opponent team IDs")
    opponent: list[str] | None = Field(default=None, description="List of opponent team names")

    # Player filters
    player_ids: list[int] | None = Field(
        default=None, description="List of player IDs (source-specific)"
    )
    player: list[str] | None = Field(
        default=None, description="List of player names (resolved to IDs via entity resolver)"
    )

    # Game filters
    game_ids: list[str] | None = Field(default=None, description="Specific game IDs to fetch")
    home_away: Literal["Home", "Away"] | None = Field(
        default=None,
        validation_alias=AliasChoices("home_away", "HomeAway"),
        description="Filter by home or away games",
    )
    venue: str | None = Field(default=None, description="Venue name filter")

    # Statistical filters
    per_mode: PerMode | None = Field(
        default=None,
        validation_alias=AliasChoices("per_mode", "PerMode"),
        description="Aggregation mode for statistics",
    )
    last_n_games: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("last_n_games", "LastNGames"),
        description="Limit to last N games",
    )
    min_minutes: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("min_minutes", "MinMinutes"),
        description="Minimum minutes played filter (for player stats)",
    )
    quarter: list[int] | None = Field(
        default=None, description="Filter by specific quarters/periods (1-4, plus OT)"
    )

    # Shot/play-level filters (for shots/pbp datasets)
    context_measure: str | None = Field(
        default=None,
        validation_alias=AliasChoices("context_measure", "ContextMeasure"),
        description="Context for shot charts (e.g., 'FGA', 'FG3A')",
    )

    # Game-minute filters (for shot-level queries)
    # These filter by elapsed game time (e.g., 0-40 for FIBA, 0-48 for NBA)
    # Implementation is dataset-specific; silently ignored if data doesn't support it
    min_game_minute: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("min_game_minute", "MinGameMinute"),
        description="Minimum game minute (elapsed time from game start)",
    )
    max_game_minute: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("max_game_minute", "MaxGameMinute"),
        description="Maximum game minute (elapsed time from game start)",
    )

    # Data quality/completeness
    only_complete: bool | None = Field(
        default=False,
        validation_alias=AliasChoices("only_complete", "OnlyComplete"),
        description="Only return games with complete data (PBP, box scores, etc.)",
    )

    # Convenience: normalize empty lists to None and coerce types
    @field_validator(
        "team", "opponent", "player", "quarter", "team_ids", "opponent_ids", "player_ids"
    )
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        """Convert empty lists to None for cleaner processing"""
        return v if v else None

    @field_validator("game_ids", mode="before")
    @classmethod
    def _coerce_game_ids(cls, v: Any) -> list[str] | None:
        """Convert game_ids to strings and handle empty lists

        Game IDs from DataFrames may be numpy int64 or other types.
        Always convert to strings for consistency.

        Uses mode='before' to run before type validation.
        """
        if not v:
            return None

        # Convert all elements to strings
        return [str(gid) for gid in v]

    @field_validator("season")
    @classmethod
    def _validate_season_format(cls, v: Any) -> str | None:
        """Validate season format

        Accepts multiple formats:
        - NCAA: '2024-25' (YYYY-YY format)
        - International/year-based: '2024' (YYYY format)
        - EuroLeague: 'E2024' (letter prefix + year)
        - Other: Any alphanumeric string for flexibility
        """
        if not v:
            return None

        # Relaxed validation: allow any non-empty string
        # Source-specific logic will handle format requirements
        if not isinstance(v, str):
            return str(v)

        return str(v)

    @field_validator("quarter")
    @classmethod
    def _validate_quarters(cls, v: list[int] | None) -> list[int] | None:
        """Validate quarter numbers (1-4 plus OT periods 5+)"""
        if not v:
            return v
        for q in v:
            if q < 1:
                raise ValueError("Quarter must be >= 1")
        return v

    @field_validator("max_game_minute")
    @classmethod
    def _validate_game_minute_range(cls, v: int | None, info: Any) -> int | None:
        """Ensure max_game_minute >= min_game_minute"""
        if v is None:
            return v
        min_minute = info.data.get("min_game_minute")
        if min_minute is not None and v < min_minute:
            raise ValueError("max_game_minute must be >= min_game_minute")
        return v
