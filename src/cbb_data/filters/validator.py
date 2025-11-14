"""Filter validation for dataset queries

This module validates filter combinations before compilation to:
1. Catch unsupported filters early with helpful error messages
2. Warn about filters that will be ignored
3. Suggest alternatives for invalid combinations
4. Ensure dataset/league compatibility
"""

from __future__ import annotations

import logging

from .spec import FilterSpec

logger = logging.getLogger(__name__)


# Filter support matrix: which filters work with which datasets
DATASET_SUPPORTED_FILTERS: dict[str, set[str]] = {
    "schedule": {
        "league",
        "season",
        "season_type",
        "date",
        "game_ids",
        "team",
        "team_ids",
        "opponent",
        "opponent_ids",
        "home_away",
        "venue",
        "conference",
        "tournament",
    },
    "player_game": {
        "league",
        "season",
        "season_type",
        "date",
        "game_ids",
        "team",
        "team_ids",
        "player",
        "player_ids",
        "last_n_games",
        "min_minutes",
        "per_mode",
    },
    "team_game": {
        "league",
        "season",
        "season_type",
        "date",
        "game_ids",
        "team",
        "team_ids",
        "opponent",
        "opponent_ids",
        "home_away",
    },
    "pbp": {"league", "game_ids", "season", "team", "team_ids", "player", "player_ids", "quarter"},
    "shots": {
        "league",
        "game_ids",
        "season",
        "season_type",  # Season type filter (Regular Season, Playoffs, etc.)
        "team",
        "team_ids",
        "opponent",  # Opponent team filter
        "player",
        "player_ids",
        "quarter",  # Period/quarter filter
        "min_game_minute",  # Game-minute range (lower bound)
        "max_game_minute",  # Game-minute range (upper bound)
        "context_measure",  # Shot context (FGA, FG3A, etc.)
    },
    # Phase 3.3: Season Aggregate Datasets
    "player_season": {
        "league",
        "season",
        "season_type",
        "team",
        "team_ids",
        "player",
        "player_ids",
        "per_mode",
        "min_minutes",
    },
    "team_season": {"league", "season", "season_type", "team", "team_ids", "conference"},
    "player_team_season": {
        "league",
        "season",
        "season_type",
        "team",
        "team_ids",
        "player",
        "player_ids",
        "per_mode",
        "min_minutes",
    },
}

# League-specific filter restrictions
LEAGUE_RESTRICTIONS: dict[str, set[str]] = {
    "NCAA-MBB": {"date", "conference", "division", "tournament"},
    "NCAA-WBB": {"date", "conference", "division", "tournament"},
    "EuroLeague": {"season", "season_type"},  # No date filtering for EuroLeague
}

# Filters that require other filters to be present
FILTER_DEPENDENCIES: dict[str, list[str]] = {
    "last_n_games": ["team", "team_ids"],  # Requires team context
    "min_minutes": ["player", "player_ids"],  # Requires player context
}


class FilterValidationError(ValueError):
    """Raised when filter validation fails"""

    pass


class FilterValidationWarning:
    """Container for validation warnings"""

    def __init__(self, message: str, filter_name: str):
        self.message = message
        self.filter_name = filter_name

    def __str__(self) -> str:
        return f"[{self.filter_name}] {self.message}"


def validate_filters(
    dataset_id: str,
    spec: FilterSpec,
    dataset_leagues: list[str] | None = None,
    strict: bool = False,
) -> list[FilterValidationWarning]:
    """Validate filter specification for a dataset

    Args:
        dataset_id: Dataset being queried (e.g., "schedule", "player_game")
        spec: Filter specification to validate
        dataset_leagues: Leagues supported by this dataset
        strict: If True, raise errors for unsupported filters. If False, just warn.

    Returns:
        List of validation warnings

    Raises:
        FilterValidationError: If validation fails (only in strict mode)

    Example:
        >>> spec = FilterSpec(league="NCAA-MBB", season="2024-25", venue="Cameron")
        >>> warnings = validate_filters("schedule", spec)
        >>> for w in warnings:
        ...     print(w)
        [venue] Filter 'venue' is defined but not fully implemented. Results may be partial.
    """
    warnings: list[FilterValidationWarning] = []

    # Get supported filters for this dataset
    supported = DATASET_SUPPORTED_FILTERS.get(dataset_id, set())

    # Get all non-None filters from spec
    active_filters = _get_active_filters(spec)

    # Check 1: Unsupported filters
    for filter_name in active_filters:
        if filter_name not in supported:
            msg = (
                f"Filter '{filter_name}' is not supported for dataset '{dataset_id}'. "
                f"Supported filters: {', '.join(sorted(supported))}"
            )
            if strict:
                raise FilterValidationError(msg)
            warnings.append(FilterValidationWarning(msg, filter_name))

    # Check 2: League-specific restrictions
    if spec.league:
        restricted = LEAGUE_RESTRICTIONS.get(spec.league, set())
        for filter_name in active_filters:
            if filter_name in restricted:
                # Date filter on EuroLeague
                if filter_name == "date" and spec.league == "EuroLeague":
                    msg = (
                        "Filter 'date' is not supported for EuroLeague. "
                        "Use 'season' filter instead."
                    )
                    warnings.append(FilterValidationWarning(msg, filter_name))

    # Check 3: Filter dependencies
    for filter_name, dependencies in FILTER_DEPENDENCIES.items():
        if filter_name in active_filters:
            if not any(dep in active_filters for dep in dependencies):
                msg = (
                    f"Filter '{filter_name}' requires one of: {', '.join(dependencies)}. "
                    f"Add a dependency filter for this to work correctly."
                )
                warnings.append(FilterValidationWarning(msg, filter_name))

    # Check 4: Conflicting filters
    if "game_ids" in active_filters and "date" in active_filters:
        msg = (
            "Filters 'game_ids' and 'date' are both specified. "
            "Using game_ids filter; date filter will be ignored."
        )
        warnings.append(FilterValidationWarning(msg, "date"))

    # Check 5: Dataset-specific validations
    if dataset_id == "pbp" and "game_ids" not in active_filters:
        msg = "Dataset 'pbp' requires 'game_ids' filter. " "Add game_ids to your query."
        if strict:
            raise FilterValidationError(msg)
        warnings.append(FilterValidationWarning(msg, "game_ids"))

    if dataset_id == "shots":
        # Shots dataset now supports season-level queries OR game-specific queries
        # Require: (season AND league) OR game_ids
        has_season = "season" in active_filters
        has_league = spec.league is not None
        has_game_ids = "game_ids" in active_filters

        if not has_game_ids and not (has_season and has_league):
            msg = (
                "Dataset 'shots' requires either 'game_ids' OR ('season' AND 'league'). "
                "Add these filters to your query."
            )
            if strict:
                raise FilterValidationError(msg)
            warnings.append(FilterValidationWarning(msg, "game_ids"))

        # Shots now supported by multiple leagues (NCAA-MBB, EuroLeague, EuroCup,
        # G-League, WNBA, NBL, CEBL, OTE). No longer EuroLeague-only.

    # Check 6: Partially implemented filters (warn users)
    # NOTE: venue, conference, division, tournament, quarter are FULLY implemented
    # as of Session 10. They are compiled into params (NCAA) and/or post-masks.
    # Verified by tests/test_missing_filters.py
    partially_implemented = {
        "context_measure",  # Shots context - needs verification
        "only_complete",  # Game completion filter - needs verification
    }
    for filter_name in active_filters:
        if filter_name in partially_implemented:
            msg = (
                f"Filter '{filter_name}' is defined but not fully implemented. "
                f"Results may be partial or filter may be ignored."
            )
            warnings.append(FilterValidationWarning(msg, filter_name))

    return warnings


def _get_active_filters(spec: FilterSpec) -> set[str]:
    """Get names of all non-None filters in spec

    Args:
        spec: Filter specification

    Returns:
        Set of filter names that are set (not None)
    """
    active = set()

    # Check all filter fields
    if spec.league:
        active.add("league")
    if spec.season:
        active.add("season")
    if spec.season_type:
        active.add("season_type")
    if spec.date:
        active.add("date")
    if spec.conference:
        active.add("conference")
    if spec.division:
        active.add("division")
    if spec.tournament:
        active.add("tournament")
    if spec.team_ids:
        active.add("team_ids")
    if spec.team:
        active.add("team")
    if spec.opponent_ids:
        active.add("opponent_ids")
    if spec.opponent:
        active.add("opponent")
    if spec.player_ids:
        active.add("player_ids")
    if spec.player:
        active.add("player")
    if spec.game_ids:
        active.add("game_ids")
    if spec.home_away:
        active.add("home_away")
    if spec.venue:
        active.add("venue")
    if spec.per_mode:
        active.add("per_mode")
    if spec.last_n_games:
        active.add("last_n_games")
    if spec.min_minutes is not None:  # 0 is valid
        active.add("min_minutes")
    if spec.quarter:
        active.add("quarter")
    if spec.context_measure:
        active.add("context_measure")
    if spec.only_complete:
        active.add("only_complete")

    return active


def get_supported_filters(dataset_id: str) -> set[str]:
    """Get set of supported filters for a dataset

    Args:
        dataset_id: Dataset identifier

    Returns:
        Set of supported filter names

    Example:
        >>> filters = get_supported_filters("schedule")
        >>> "team" in filters
        True
        >>> "min_minutes" in filters
        False
    """
    return DATASET_SUPPORTED_FILTERS.get(dataset_id, set()).copy()


def get_league_restrictions(league: str) -> set[str]:
    """Get filters that work specifically with this league

    Args:
        league: League identifier

    Returns:
        Set of filter names that work with this league

    Example:
        >>> filters = get_league_restrictions("EuroLeague")
        >>> "date" in filters
        False
        >>> "season" in filters
        True
    """
    return LEAGUE_RESTRICTIONS.get(league, set()).copy()
