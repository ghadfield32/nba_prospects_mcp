"""Dataset API Layer

Public API for accessing college and international basketball datasets.

Main Functions:
- list_datasets(): Get all available datasets with metadata
- get_dataset(): Fetch filtered data from any dataset

All datasets support the unified FilterSpec for consistent querying.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

from .. import fetchers
from ..catalog.levels import (
    LEAGUE_LEVELS,
    filter_leagues_by_level,
    get_excluded_leagues_message,
    get_leagues_by_level,
    is_pre_nba_league,
)
from ..catalog.registry import DatasetRegistry
from ..catalog.sources import _register_league_sources, get_league_source_config
from ..compose.enrichers import (
    add_league_context,
    coerce_common_columns,
)
from ..fetchers import (
    bcl,  # Basketball Champions League
    cbbpy_mbb,  # CBBpy integration for NCAA Men's box scores
    cbbpy_wbb,  # CBBpy integration for NCAA Women's box scores
    cebl,  # Canadian Elite Basketball League
    domestic_euro,  # European domestic leagues (BBL, BSL, LBA)
    gleague,  # G League integration
    nbl_official,  # NBL Australia (official via nblR R package)
    ote,  # Overtime Elite
    prestosports,  # PrestoSports platform (NJCAA, NAIA, U-SPORTS)
)
from ..filters.compiler import apply_post_mask, compile_params
from ..filters.spec import FilterSpec
from ..filters.validator import validate_filters
from ..storage.duckdb_storage import get_storage
from ..utils.entity_resolver import (
    resolve_euroleague_team,
    resolve_ncaa_team,
)

logger = logging.getLogger(__name__)

# Derive all supported leagues from LEAGUE_LEVELS (single source of truth)
ALL_LEAGUES = list(LEAGUE_LEVELS.keys())

# Register all league source configurations (must happen after fetcher imports)
_register_league_sources()


# ==============================================================================
# Helper Functions
# ==============================================================================


def get_current_season(league: str) -> str:
    """Auto-detect current season based on league calendar

    Automatically determines the current season based on:
    - Current month and year
    - League-specific season calendars

    Args:
        league: League identifier ("NCAA-MBB", "NCAA-WBB", "EuroLeague")

    Returns:
        Season string in appropriate format:
        - NCAA: "2024" (for 2024-25 season starting Nov 2024)
        - EuroLeague: "E2024" (for 2024-25 season starting Oct 2024)

    Examples:
        >>> # Called in November 2024
        >>> get_current_season("NCAA-MBB")
        "2024"

        >>> # Called in March 2024
        >>> get_current_season("NCAA-MBB")
        "2023"  # Still in 2023-24 season

        >>> # Called in December 2024
        >>> get_current_season("EuroLeague")
        "E2024"

    Notes:
        - NCAA season runs Nov-April (e.g., "2024" = 2024-25 season)
        - EuroLeague season runs Oct-May (e.g., "E2024" = 2024-25 season)
        - WNBA season runs May-October (e.g., "2024" = 2024 season)
    """
    now = datetime.now()
    month = now.month
    year = now.year

    if league in ["NCAA-MBB", "NCAA-WBB"]:
        # NCAA season: Nov-April
        # Nov-Dec → current year (e.g., Nov 2024 = "2024" for 2024-25 season)
        # Jan-Oct → previous year (e.g., Mar 2024 = "2023" for 2023-24 season)
        if month >= 11:  # Nov-Dec
            return str(year)
        else:  # Jan-Oct
            return str(year - 1)

    elif league == "EuroLeague":
        # EuroLeague season: Oct-May
        # Oct-Dec → current year
        # Jan-Sep → previous year
        if month >= 10:  # Oct-Dec
            return f"E{year}"
        else:  # Jan-Sep
            return f"E{year - 1}"

    elif league == "EuroCup":
        # EuroCup season: Oct-May (same as EuroLeague)
        # Oct-Dec → current year
        # Jan-Sep → previous year
        if month >= 10:  # Oct-Dec
            return f"U{year}"
        else:  # Jan-Sep
            return f"U{year - 1}"

    elif league == "G-League":
        # G League season: Nov-April (same as NBA)
        # Nov-Dec → current year (e.g., Nov 2024 = "2024-25" season)
        # Jan-Oct → previous year (e.g., Mar 2024 = "2023-24" season)
        if month >= 11:  # Nov-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Oct
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    elif league == "WNBA":
        # WNBA season: May-October (single calendar year)
        return str(year)

    elif league in ["BCL", "NBL"]:
        # BCL and NBL: Oct-May season (similar to EuroLeague)
        # Oct-Dec → current year
        # Jan-Sep → previous year
        if month >= 10:  # Oct-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Sep
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    elif league in ["ACB", "LNB", "BBL", "BSL", "LBA"]:
        # European domestic leagues: Oct-May season
        # Oct-Dec → current year
        # Jan-Sep → previous year
        if month >= 10:  # Oct-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Sep
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    elif league in ["NJCAA", "NAIA"]:
        # NJCAA and NAIA: Nov-April (similar to NCAA)
        # Nov-Dec → current year
        # Jan-Oct → previous year
        if month >= 11:  # Nov-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Oct
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    elif league == "CEBL":
        # CEBL: May-August (summer season, single calendar year)
        return str(year)

    elif league == "U-SPORTS":
        # U SPORTS: Nov-March (Canadian university season)
        # Nov-Dec → current year
        # Jan-Oct → previous year
        if month >= 11:  # Nov-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Oct
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    elif league == "OTE":
        # Overtime Elite: Oct-March season
        # Oct-Dec → current year
        # Jan-Sep → previous year
        if month >= 10:  # Oct-Dec
            return f"{year}-{str(year + 1)[-2:]}"  # e.g., "2024-25"
        else:  # Jan-Sep
            return f"{year - 1}-{str(year)[-2:]}"  # e.g., "2023-24"

    else:
        # Default: return current year
        logger.warning(f"Unknown league '{league}', defaulting to current year")
        return str(year)


def get_recent_games(
    league: str,
    days: int = 2,
    teams: list[str] | None = None,
    Division: str | None = None,
    force_fresh: bool = False,
    pre_only: bool = True,
) -> pd.DataFrame:
    """Fetch games from recent days (includes yesterday + today by default)

    Convenience function for fetching recent games without manually specifying date ranges.
    Automatically calculates date range from today backwards.

    Args:
        league: League identifier ("NCAA-MBB", "NCAA-WBB", "EuroLeague")
        days: Number of days to look back (default: 2 = yesterday + today)
        teams: Optional list of team names to filter
        Division: Optional division filter ("D1", "D2", "D3", "all") - NCAA only
        force_fresh: If True, bypass cache and fetch fresh data
        pre_only: If True, restrict to pre-NBA/WNBA leagues (default: True)

    Returns:
        DataFrame with games from the specified date range

    Examples:
        >>> # Get yesterday + today's games
        >>> df = get_recent_games("NCAA-MBB")

        >>> # Get last 7 days of games
        >>> df = get_recent_games("NCAA-MBB", days=7)

        >>> # Get yesterday + today for Duke only
        >>> df = get_recent_games("NCAA-MBB", teams=["Duke"])

        >>> # Get recent games with fresh data (bypass cache)
        >>> df = get_recent_games("NCAA-MBB", days=3, force_fresh=True)

        >>> # Get recent D1 games only
        >>> df = get_recent_games("NCAA-MBB", Division="D1")

    Notes:
        - Default (days=2) fetches yesterday + today
        - Automatically handles date formatting for each league
        - Uses existing caching unless force_fresh=True
        - For NCAA, defaults to Division 1 unless specified otherwise
    """
    from datetime import timedelta

    # Calculate date range
    end_date = datetime.now().date()  # Get date object, not datetime
    start_date = end_date - timedelta(days=days - 1)

    # Build filters with date objects (not strings)
    filters = {"league": league, "date": {"start": start_date, "end": end_date}}

    # Add optional filters
    if teams:
        filters["team"] = teams
    if Division:
        filters["Division"] = Division

    logger.info(
        f"Fetching recent games: {league}, "
        f"date range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} "
        f"({days} days)"
    )

    # Use get_dataset with force_fresh and pre_only parameters
    return get_dataset("schedule", filters, force_fresh=force_fresh, pre_only=pre_only)


def _create_default_name_resolver() -> Callable[[str, str, str | None], int | None]:
    """Create a default name resolver function

    Returns a resolver function that:
    1. Normalizes team names using league-specific resolvers
    2. Returns None for IDs (falls back to name-based post-mask filtering)
    3. Improves name matching consistency

    This is a basic implementation. For full ID resolution, implement
    entity lookup logic in entity_resolver.resolve_entity().
    """

    def resolver(name: str, entity_type: str, league: str | None) -> int | None:
        """Resolve entity name to ID (with name normalization)"""
        if entity_type == "team":
            # Normalize team name based on league
            if league and "NCAA" in league:
                normalized = resolve_ncaa_team(name)
                logger.debug(f"Normalized NCAA team '{name}' → '{normalized}'")
            elif league == "EuroLeague":
                normalized = resolve_euroleague_team(name)
                logger.debug(f"Normalized EuroLeague team '{name}' → '{normalized}'")
            else:
                normalized = name

            # TODO: Look up ID from database/API
            # For now, return None to use name-based post-mask
            return None

        elif entity_type == "player":
            # TODO: Implement player name normalization and ID lookup
            return None

        return None

    return resolver


def _parse_euroleague_season(season_str: str | None) -> int:
    """Convert EuroLeague season string to integer year

    Handles multiple formats:
    - "E2024" → 2024
    - "2024" → 2024
    - "2024-25" → 2024

    Args:
        season_str: Season string in various formats

    Returns:
        Season year as integer
    """
    if not season_str:
        # Default to current year
        return datetime.now().year

    # Remove 'E' prefix if present
    season_str = str(season_str).strip().upper().replace("E", "")

    # If it's a range like "2024-25", take the first year
    if "-" in season_str:
        season_str = season_str.split("-")[0]

    try:
        return int(season_str)
    except ValueError:
        logger.warning(f"Could not parse season '{season_str}', using current year")
        return datetime.now().year


def fetch_with_duckdb_cache(
    dataset: str,
    league: str,
    season: str,
    fetcher_func: Callable[[], pd.DataFrame],
    force_refresh: bool = False,
    enable_cache: bool = True,
) -> pd.DataFrame:
    """Fetch data with DuckDB persistent caching for 1000-4000x speedup on cache hits

    This wrapper function provides transparent persistent caching for slow API calls,
    especially beneficial for EuroLeague schedules (3-7 minutes → <1 second on cache hit).

    Args:
        dataset: Dataset name ('schedule', 'player_game', etc.)
        league: League code ('NCAA-MBB', 'EuroLeague', etc.)
        season: Season string ('2024', '2023', etc.)
        fetcher_func: Function that fetches data from API (callable, no arguments)
        force_refresh: If True, bypass cache and fetch from API
        enable_cache: If False, skip caching entirely (for testing)

    Returns:
        DataFrame: Data from cache (if available) or freshly fetched from API

    Performance:
        - First fetch: Full API time (e.g., 3-7 min for EuroLeague schedule)
        - Subsequent fetches: 0.1-1 second from DuckDB
        - Speedup: 1000-4000x faster on cache hits

    Example:
        # Wrap slow fetcher with caching
        df = fetch_with_duckdb_cache(
            dataset='schedule',
            league='EuroLeague',
            season='2024',
            fetcher_func=lambda: fetchers.euroleague.fetch_euroleague_games(2024)
        )
        # First call: 3-7 minutes (cache miss)
        # Second call: <1 second (cache hit)
    """
    if not enable_cache:
        # Caching disabled - fetch directly
        logger.debug(f"Cache disabled for {dataset}/{league}/{season}")
        return fetcher_func()

    try:
        storage = get_storage()

        # Check cache first (unless force refresh)
        if not force_refresh and storage.has_data(dataset, league, season):
            logger.info(
                f"Loading {dataset}/{league}/{season} from DuckDB cache "
                f"(instant vs 3-7 min API fetch)"
            )
            df = storage.load(dataset, league, season)

            if not df.empty:
                logger.debug(f"Cache hit: {len(df):,} rows loaded in <1 second")
                return df
            else:
                logger.warning("Cache returned empty DataFrame - refetching from API")

        # Cache miss or force refresh - fetch from API
        cache_status = "force refresh" if force_refresh else "cache miss"
        logger.info(f"Fetching {dataset}/{league}/{season} from API ({cache_status})")

        df = fetcher_func()

        # Save to cache for next time (if not empty)
        if not df.empty:
            storage.save(df, dataset, league, season)
            logger.info(f"Saved {len(df):,} rows to DuckDB cache (next fetch will be 1000x faster)")
        else:
            logger.warning("Empty DataFrame - not caching")

        return df

    except Exception as e:
        # If caching fails, fall back to direct fetch
        logger.error(f"DuckDB caching failed ({e}), fetching without cache")
        return fetcher_func()


def validate_fetch_request(dataset: str, filters: dict[str, Any], league: str | None) -> None:
    """Validate request before fetching - fail fast on configuration errors

    This function performs pre-fetch validation to catch errors BEFORE making API calls.
    It complements the existing validate_filters() function by checking:
    1. League validity (must be one of supported leagues)
    2. Season format (must be YYYY format like '2024')
    3. NCAA Division 1 recommendation (warns if groups not specified)
    4. Conflicting filters (e.g., schedule + player is invalid)
    5. Dataset supports requested filters

    Args:
        dataset: Dataset identifier (e.g., 'schedule', 'player_game')
        filters: Filter dictionary from user
        league: League identifier (e.g., 'NCAA-MBB', 'EuroLeague')

    Raises:
        ValueError: If request is invalid (league, season format, conflicting filters)

    Performance:
        - <1ms validation time
        - Prevents minutes of wasted API calls on invalid requests
        - Provides clear error messages to guide users

    Example:
        >>> validate_fetch_request('schedule', {'season': '2024'}, 'NCAA-MBB')
        # Passes validation

        >>> validate_fetch_request('schedule', {'season': 'abc'}, 'NCAA-MBB')
        # Raises ValueError: Invalid season format
    """
    # 1. Check league is valid (get from registered leagues in catalog)
    from ..catalog.levels import LEAGUE_LEVELS

    valid_leagues = list(LEAGUE_LEVELS.keys())
    if league and league not in valid_leagues:
        raise ValueError(f"Invalid league '{league}'. Must be one of: {valid_leagues}")

    # 2. Check season format (must be YYYY format)
    season = filters.get("season")
    if season:
        season_str = str(season).strip()

        # Allow EuroLeague format "E2024" or NCAA format "2024" or range "2024-25"
        # Extract the year portion
        cleaned_season = season_str.upper().replace("E", "").split("-")[0]

        # Verify it's a 4-digit year
        if not cleaned_season.isdigit() or len(cleaned_season) != 4:
            raise ValueError(
                f"Invalid season format '{season}'. "
                f"Expected YYYY format (e.g., '2024' or '2024-25' or 'E2024')"
            )

        # Verify year is reasonable (between 2000 and current year + 1)
        year = int(cleaned_season)
        current_year = datetime.now().year
        if year < 2000 or year > current_year + 1:
            logger.warning(
                f"Season year {year} is outside typical range (2000-{current_year + 1}). "
                f"Proceeding anyway..."
            )

    # 3. NCAA Division 1 recommendation
    # (Note: Actual filtering happens in Priority 3 implementation)
    if league and league.startswith("NCAA"):
        groups = filters.get("groups")
        if groups is None:
            logger.info(
                "NCAA query without 'groups' filter will include all divisions. "
                "For Division 1 only (recommended), add groups='50' to filters."
            )

    # 4. Check for conflicting filters
    # schedule dataset doesn't support player filtering
    if dataset == "schedule" and (filters.get("player") or filters.get("player_ids")):
        raise ValueError(
            "Schedule dataset does not support player filtering. "
            "Use player_game dataset for player-specific queries."
        )

    # player_season and team_season require season parameter
    if dataset in ["player_season", "team_season", "player_team_season"]:
        if not filters.get("season"):
            raise ValueError(
                f"Dataset '{dataset}' requires 'season' parameter. Example: {{'season': '2024'}}"
            )

    # 5. Check dataset exists
    # (This is already done in get_dataset() before this function is called,
    # but we log it here for completeness in case this function is called independently)
    logger.debug(f"Pre-fetch validation passed: {dataset}/{league}/{filters}")


# ==============================================================================
# Dataset Fetch Functions
# ==============================================================================


def _map_division_to_groups(division: str | list[str] | None) -> str:
    """
    Map division parameter to ESPN groups code.

    Args:
        division: Division filter - can be string, list, or None
                  - "D1" or "1" -> "50" (Division 1 only)
                  - "D2" or "2" -> "51" (Non-Division 1)
                  - "D3" or "3" -> "51" (Non-Division 1)
                  - "all" or None -> "50,51" (All divisions)
                  - ["D1", "D2"] -> "50,51" (Multiple divisions)

    Returns:
        str: ESPN groups parameter ("50", "51", or "50,51")

    Examples:
        >>> _map_division_to_groups("D1")
        "50"
        >>> _map_division_to_groups(["D1", "D2"])
        "50,51"
        >>> _map_division_to_groups("all")
        "50,51"
    """
    if division is None or division == "all":
        return "50,51"

    # Handle list of divisions
    if isinstance(division, list):
        divisions_set = set()
        for d in division:
            d_upper = str(d).upper().replace("D", "")
            if d_upper in ["1"]:
                divisions_set.add("50")
            elif d_upper in ["2", "3"]:
                divisions_set.add("51")
        return ",".join(sorted(divisions_set))

    # Handle single division string
    division_upper = str(division).upper().replace("D", "")
    if division_upper == "1":
        return "50"
    elif division_upper in ["2", "3"]:
        return "51"
    else:
        # Default to all divisions
        logger.warning(f"Unknown division '{division}', using all divisions")
        return "50,51"


def _get_season_date_range(season: str, league: str) -> tuple[str, str]:
    """Generate season-aware date range for basketball leagues

    Automatically determines the start and end dates for a basketball season based on the league.
    This enables player_season and other aggregation queries to work without explicit date filters.

    Args:
        season: Season identifier (e.g., "2024" or "2024-25")
        league: League name (e.g., "NCAA-MBB", "NCAA-WBB", "EuroLeague")

    Returns:
        Tuple of (DateFrom, DateTo) as strings in "%m/%d/%Y" format

    Examples:
        >>> _get_season_date_range("2024", "NCAA-MBB")
        ('11/01/2023', '04/30/2024')  # 2023-24 season: Nov 2023 - Apr 2024

        >>> _get_season_date_range("2025", "NCAA-WBB")
        ('11/01/2024', '04/30/2025')  # 2024-25 season: Nov 2024 - Apr 2025

        >>> _get_season_date_range("2024", "EuroLeague")
        ('10/01/2023', '05/31/2024')  # 2023-24 season: Oct 2023 - May 2024

    Season Logic:
        - NCAA seasons are denoted by the ending year (2024 = 2023-24 season)
        - Season "2024" starts November 2023, ends April 2024
        - EuroLeague season "2024" starts October 2023, ends May 2024

    Date Ranges:
        - NCAA (MBB/WBB): November 1 (previous year) to April 30 (season year)
            - Regular season: Nov-March
            - Conference tournaments: Early March
            - NCAA Tournament: Mid-March to early April
        - EuroLeague: October 1 (previous year) to May 31 (season year)
            - Regular season: Oct-April
            - Playoffs: April-May
    """
    # Parse season year (handle both "2024" and "2024-25" formats)
    if "-" in season:
        # Format: "2024-25" → explicit start and end years
        parts = season.split("-")
        start_year = int(parts[0])
        end_year = int(parts[1]) if len(parts[1]) == 4 else int("20" + parts[1])
        use_explicit_years = True
    else:
        # Format: "2024" → ending year (2023-24 season)
        season_year = int(season)
        use_explicit_years = False

    # NCAA seasons (MBB and WBB): November (previous year) - April (season year)
    if league in ["NCAA-MBB", "NCAA-WBB"]:
        # Season "2024" means 2023-24 season
        # Starts: November 1, 2023
        # Ends: April 30, 2024 (includes NCAA Tournament)
        if not use_explicit_years:
            start_year = season_year - 1
            end_year = season_year

        date_from = f"11/01/{start_year}"  # November 1
        date_to = f"04/30/{end_year}"  # April 30

    # EuroLeague: October (previous year) - May (season year)
    elif league == "EuroLeague":
        # Season "2024" means 2023-24 season
        # Starts: October 1, 2023
        # Ends: May 31, 2024 (includes playoffs)
        if not use_explicit_years:
            start_year = season_year - 1
            end_year = season_year

        date_from = f"10/01/{start_year}"  # October 1
        date_to = f"05/31/{end_year}"  # May 31

    else:
        # Default fallback: assume NCAA-style calendar
        logger.warning(f"Unknown league '{league}' for season date range, using NCAA defaults")
        start_year = season_year - 1
        end_year = season_year
        date_from = f"11/01/{start_year}"
        date_to = f"04/30/{end_year}"

    logger.debug(f"Generated season date range for {league} {season}: {date_from} to {date_to}")
    return (date_from, date_to)


def _fetch_schedule(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch schedule/scoreboard data

    Supports: ESPN MBB, ESPN WBB, EuroLeague

    Division filtering (NCAA only):
        - params['Division']: "D1", "D2", "D3", "all", or ["D1", "D2"]
        - Default: "50" (Division 1 only)
    """
    params = compiled["params"]
    post_mask = compiled["post_mask"]
    meta = compiled["meta"]

    league = meta.get("league")

    # Extract and convert division parameter to ESPN groups (NCAA only)
    division = params.get("Division")
    groups = _map_division_to_groups(division) if division is not None else "50"

    if league == "NCAA-MBB":
        # ESPN MBB
        if params.get("DateFrom") and params.get("DateTo"):
            date_from = datetime.strptime(params["DateFrom"], "%m/%d/%Y").date()
            date_to = datetime.strptime(params["DateTo"], "%m/%d/%Y").date()

            df = fetchers.espn_mbb.fetch_schedule_range(
                date_from=date_from, date_to=date_to, season=params.get("Season"), groups=groups
            )
        elif params.get("Season"):
            # Season-aware date range (when Season provided but no explicit DateFrom/DateTo)
            # Automatically generates full season date range (Nov-April for NCAA)
            season = params.get("Season")
            date_from_str, date_to_str = _get_season_date_range(season, league)

            date_from = datetime.strptime(date_from_str, "%m/%d/%Y").date()
            date_to = datetime.strptime(date_to_str, "%m/%d/%Y").date()

            logger.info(
                f"Using season-aware dates for {league} {season}: {date_from_str} to {date_to_str}"
            )

            df = fetchers.espn_mbb.fetch_schedule_range(
                date_from=date_from, date_to=date_to, season=season, groups=groups
            )
        else:
            # Fallback: Today's games (when neither DateFrom/DateTo nor Season provided)
            today = datetime.now().strftime("%Y%m%d")
            df = fetchers.espn_mbb.fetch_espn_scoreboard(date=today, groups=groups)

    elif league == "NCAA-WBB":
        # ESPN WBB
        if params.get("DateFrom") and params.get("DateTo"):
            date_from = datetime.strptime(params["DateFrom"], "%m/%d/%Y").date()
            date_to = datetime.strptime(params["DateTo"], "%m/%d/%Y").date()

            df = fetchers.espn_wbb.fetch_wbb_schedule_range(
                date_from=date_from, date_to=date_to, season=params.get("Season"), groups=groups
            )
        elif params.get("Season"):
            # Season-aware date range (when Season provided but no explicit DateFrom/DateTo)
            # Automatically generates full season date range (Nov-April for NCAA)
            season = params.get("Season")
            date_from_str, date_to_str = _get_season_date_range(season, league)

            date_from = datetime.strptime(date_from_str, "%m/%d/%Y").date()
            date_to = datetime.strptime(date_to_str, "%m/%d/%Y").date()

            logger.info(
                f"Using season-aware dates for {league} {season}: {date_from_str} to {date_to_str}"
            )

            df = fetchers.espn_wbb.fetch_wbb_schedule_range(
                date_from=date_from, date_to=date_to, season=season, groups=groups
            )
        else:
            # Fallback: Today's games (when neither DateFrom/DateTo nor Season provided)
            today = datetime.now().strftime("%Y%m%d")
            df = fetchers.espn_wbb.fetch_espn_wbb_scoreboard(date=today, groups=groups)

    elif league == "EuroLeague":
        # EuroLeague
        # Note: EuroLeague API always fetches full season, relies on caching + limit at API layer
        season_str = params.get("Season", "E2024")
        season = _parse_euroleague_season(season_str)
        phase = "PO" if params.get("SeasonType") == "Playoffs" else "RS"

        # Wrap with DuckDB caching for 1000-4000x speedup on cache hits
        # First fetch: 3-7 minutes, subsequent fetches: <1 second
        df = fetch_with_duckdb_cache(
            dataset="schedule",
            league="EuroLeague",
            season=str(season),
            fetcher_func=lambda: fetchers.euroleague.fetch_euroleague_games(
                season=season, phase=phase, competition="E"
            ),
            force_refresh=params.get("ForceRefresh", False),
        )

    elif league == "EuroCup":
        # EuroCup (uses same API as EuroLeague)
        # Note: EuroCup API always fetches full season, relies on caching + limit at API layer
        season_str = params.get("Season", "U2024")
        season = _parse_euroleague_season(season_str)
        phase = "PO" if params.get("SeasonType") == "Playoffs" else "RS"

        # Wrap with DuckDB caching for 1000-4000x speedup on cache hits
        df = fetch_with_duckdb_cache(
            dataset="schedule",
            league="EuroCup",
            season=str(season),
            fetcher_func=lambda: fetchers.euroleague.fetch_euroleague_games(
                season=season, phase=phase, competition="U"
            ),
            force_refresh=params.get("ForceRefresh", False),
        )

    elif league == "G-League":
        # NBA G League
        season_str = params.get("Season", "2024-25")
        season_type = params.get("SeasonType", "Regular Season")

        # Extract date range if provided
        date_from = params.get("DateFrom")
        date_to = params.get("DateTo")

        # Wrap with DuckDB caching for fast subsequent fetches
        df = fetch_with_duckdb_cache(
            dataset="schedule",
            league="G-League",
            season=season_str,
            fetcher_func=lambda: gleague.fetch_gleague_schedule(
                season=season_str,
                season_type=season_type,
                date_from=date_from,
                date_to=date_to,
            ),
            force_refresh=params.get("ForceRefresh", False),
        )

    elif league == "BCL":
        # Basketball Champions League
        season_str = params.get("Season", "2024-25")
        season_type = params.get("SeasonType", "Regular Season")

        df = bcl.fetch_schedule(season=season_str)

    elif league == "NBL":
        # NBL Australia
        season_str = params.get("Season", "2024-25")
        season_type = params.get("SeasonType", "Regular Season")

        df = nbl_official.fetch_nbl_schedule(season=season_str, season_type=season_type)

    elif league in ["ACB", "LNB", "BBL", "BSL", "LBA"]:
        # European domestic leagues
        season_str = params.get("Season", "2024-25")
        season_type = params.get("SeasonType", "Regular Season")

        df = domestic_euro.fetch_domestic_euro_schedule(
            league=league, season=season_str, season_type=season_type
        )

    elif league in ["NJCAA", "NAIA"]:
        # PrestoSports leagues
        season_str = params.get("Season", "2024-25")
        division = params.get("Division")  # For NJCAA: "div1", "div2", "div3"

        df = prestosports.fetch_prestosports_schedule(
            league=league, season=season_str, division=division
        )

    elif league == "CEBL":
        # Canadian Elite Basketball League
        season_str = params.get("Season", str(datetime.now().year))

        df = cebl.fetch_cebl_schedule(season=season_str)

    elif league == "U-SPORTS":
        # U SPORTS (Canada)
        season_str = params.get("Season", "2024-25")
        conference = params.get("Conference")  # OUA, Canada West, AUS, RSEQ

        df = prestosports.fetch_prestosports_schedule(
            league="U-SPORTS", season=season_str, conference=conference
        )

    elif league == "OTE":
        # Overtime Elite
        season_str = params.get("Season", "2024-25")

        df = ote.fetch_ote_schedule(season=season_str)

    else:
        raise ValueError(f"Unsupported league for schedule: {league}")

    # Normalize column names for consistency across sources
    # ESPN uses HOME_TEAM_NAME, EuroLeague/EuroCup use HOME_TEAM
    if league in ["NCAA-MBB", "NCAA-WBB"]:
        df = coerce_common_columns(df, source="espn")
    # EuroLeague/EuroCup already use standard column names, no normalization needed

    # Apply post-mask filters
    df = apply_post_mask(df, post_mask)

    return df


def _fetch_player_game(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch player/game data (box scores)

    Supports: ESPN MBB, ESPN WBB, EuroLeague, EuroCup, G-League
    """
    params = compiled["params"]
    post_mask = compiled["post_mask"]
    meta = compiled["meta"]

    league = meta.get("league")

    if league in ["NCAA-MBB", "NCAA-WBB"]:
        # For NCAA, we need to:
        # 1. Get team's schedule
        # 2. Fetch box scores for each game
        # 3. Filter by player

        # DEBUG: Log post_mask contents
        logger.debug(f"_fetch_player_game post_mask keys: {list(post_mask.keys())}")
        # FIX: Check if GAME_ID exists AND is not None before calling len()
        if "GAME_ID" in post_mask and post_mask["GAME_ID"] is not None:
            logger.debug(f"_fetch_player_game GAME_ID count: {len(post_mask['GAME_ID'])}")
        logger.debug(f"_fetch_player_game meta limit: {meta.get('limit')}")

        # This requires team_id or game_ids
        if not (post_mask.get("TEAM_ID") or post_mask.get("GAME_ID")):
            raise ValueError("player_game requires team or game_ids filter for NCAA")

        # Extract season early for CBBpy calls
        season = int(params.get("Season", datetime.now().year))

        frames = []

        if post_mask.get("GAME_ID"):
            # Fetch specific games
            game_id_list = post_mask["GAME_ID"]
            logger.info(f"_fetch_player_game: post_mask GAME_ID has {len(game_id_list)} game IDs")

            # Check if we have a limit in meta - only fetch enough games to satisfy limit
            limit = meta.get("limit")
            games_to_fetch = (
                game_id_list if not limit else game_id_list[: limit * 2]
            )  # Fetch 2x limit to ensure enough data
            logger.info(f"_fetch_player_game: Fetching {len(games_to_fetch)} games (limit={limit})")
            logger.info(f"_fetch_player_game: games_to_fetch first 10: {games_to_fetch[:10]}")

            for game_id in games_to_fetch:
                try:
                    if league == "NCAA-MBB":
                        # Use CBBpy for NCAA-MBB (ESPN API returns empty box scores)
                        box_score = cbbpy_mbb.fetch_cbbpy_box_score(game_id, season)
                        frames.append(box_score)
                    else:  # NCAA-WBB
                        # Use CBBpy for NCAA-WBB (ESPN API doesn't provide player box scores)
                        box_score = cbbpy_wbb.fetch_cbbpy_wbb_box_score(game_id, season)
                        frames.append(box_score)
                except Exception as e:
                    logger.warning(f"Failed to fetch game {game_id}: {e}")

        elif post_mask.get("TEAM_ID"):
            # Fetch team's schedule, then box scores
            team_id = post_mask["TEAM_ID"][0]

            if league == "NCAA-MBB":
                schedule = fetchers.espn_mbb.fetch_team_games(team_id, season)
            else:  # NCAA-WBB
                schedule = fetchers.espn_wbb.fetch_wbb_team_games(team_id, season)

            # Limit to last_n_games if specified
            if params.get("LastNGames"):
                schedule = schedule.head(params["LastNGames"])

            for _, game in schedule.iterrows():
                try:
                    game_id = str(game["GAME_ID"])
                    if league == "NCAA-MBB":
                        # Use CBBpy for NCAA-MBB (ESPN API returns empty box scores)
                        box_score = cbbpy_mbb.fetch_cbbpy_box_score(game_id, season)
                        frames.append(box_score)
                    else:  # NCAA-WBB
                        # Use CBBpy for NCAA-WBB (ESPN API doesn't provide player box scores)
                        box_score = cbbpy_wbb.fetch_cbbpy_wbb_box_score(game_id, season)
                        frames.append(box_score)
                except Exception as e:
                    logger.warning(f"Failed to fetch game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        # FIX: Normalize GAME_ID to string to prevent type mismatch with post_mask filters
        # CBBpy cache can return different dtypes (object vs int64) on subsequent calls
        if "GAME_ID" in df.columns:
            df["GAME_ID"] = df["GAME_ID"].astype(str)

    elif league == "EuroLeague":
        # EuroLeague box scores
        season_str = params.get("Season", "E2024")
        season = _parse_euroleague_season(season_str)
        phase = "PO" if params.get("SeasonType") == "Playoffs" else "RS"

        # Get games first
        games = fetchers.euroleague.fetch_euroleague_games(season, phase, competition="E")

        # Parallel fetching to avoid timeout on large seasons (330 games)
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from tqdm import tqdm

        def fetch_single_game(game_info: dict[str, Any]) -> pd.DataFrame | None:
            """Fetch box score for a single game"""
            game_code = int(game_info["GAME_CODE"])
            try:
                return fetchers.euroleague.fetch_euroleague_box_score(
                    season, game_code, competition="E"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch EuroLeague game {game_code}: {e}")
                return None

        frames = []
        # Use 5 workers to parallelize while respecting rate limits
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            futures = {
                executor.submit(fetch_single_game, game.to_dict()): game["GAME_CODE"]
                for _, game in games.iterrows()
            }

            # Collect results with progress bar
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Fetching EuroLeague {season}",
                unit="game",
            ):
                result = future.result()
                if result is not None and not result.empty:
                    frames.append(result)

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        # FIX: Normalize GAME_CODE to string to prevent type mismatch with post_mask filters
        if "GAME_CODE" in df.columns:
            df["GAME_CODE"] = df["GAME_CODE"].astype(str)

    elif league == "EuroCup":
        # EuroCup box scores (same API as EuroLeague)
        season_str = params.get("Season", "U2024")
        season = _parse_euroleague_season(season_str)
        phase = "PO" if params.get("SeasonType") == "Playoffs" else "RS"

        # Get games first
        games = fetchers.euroleague.fetch_euroleague_games(season, phase, competition="U")

        # Parallel fetching to avoid timeout on large seasons
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from tqdm import tqdm

        def fetch_single_game_eurocup(game_info: dict[str, Any]) -> pd.DataFrame | None:
            """Fetch box score for a single EuroCup game"""
            game_code = int(game_info["GAME_CODE"])
            try:
                return fetchers.euroleague.fetch_euroleague_box_score(
                    season, game_code, competition="U"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch EuroCup game {game_code}: {e}")
                return None

        frames = []
        # Use 5 workers to parallelize while respecting rate limits
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            futures = {
                executor.submit(fetch_single_game_eurocup, game.to_dict()): game["GAME_CODE"]
                for _, game in games.iterrows()
            }

            # Collect results with progress bar
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Fetching EuroCup {season}",
                unit="game",
            ):
                result = future.result()
                if result is not None and not result.empty:
                    frames.append(result)

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        # FIX: Normalize GAME_CODE to string to prevent type mismatch with post_mask filters
        if "GAME_CODE" in df.columns:
            df["GAME_CODE"] = df["GAME_CODE"].astype(str)

    elif league == "G-League":
        # NBA G League box scores
        # G League requires game_ids (similar to NCAA pattern)
        if not post_mask.get("GAME_ID"):
            raise ValueError("player_game requires game_ids filter for G-League")

        frames = []
        game_id_list = post_mask["GAME_ID"]

        logger.info(f"Fetching G League box scores for {len(game_id_list)} games")

        # Fetch box scores for each game
        for game_id in game_id_list:
            try:
                box_score = gleague.fetch_gleague_box_score(game_id)
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch G League game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        # FIX: Normalize GAME_ID to string to prevent type mismatch with post_mask filters
        if "GAME_ID" in df.columns:
            df["GAME_ID"] = df["GAME_ID"].astype(str)

    elif league == "BCL":
        # Basketball Champions League
        if not post_mask.get("GAME_ID"):
            raise ValueError("player_game requires game_ids filter for BCL")

        # Extract season from params
        season_str = params.get("Season", "2024-25")

        # BCL uses fetch_player_game for season-wide data, not per-game
        # Fetch all player games for the season and filter by game_id
        all_games = bcl.fetch_player_game(season=season_str)
        if not all_games.empty and "GAME_ID" in all_games.columns:
            df = all_games[all_games["GAME_ID"].isin(post_mask["GAME_ID"])]
        else:
            df = pd.DataFrame()

    elif league == "NBL":
        # NBL Australia
        season_str = params.get("Season", "2024")

        # Fetch all player games for the season
        df = nbl_official.fetch_nbl_player_game(season=season_str)

        # Filter by game_ids if provided
        if post_mask.get("GAME_ID"):
            df = df[df["GAME_ID"].isin(post_mask["GAME_ID"])]

    elif league in ["ACB", "LNB", "BBL", "BSL", "LBA"]:
        # European domestic leagues
        if not post_mask.get("GAME_ID"):
            raise ValueError(f"player_game requires game_ids filter for {league}")

        frames = []
        for game_id in post_mask["GAME_ID"]:
            try:
                box_score = domestic_euro.fetch_domestic_euro_box_score(league, game_id)
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch {league} game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    elif league in ["NJCAA", "NAIA"]:
        # PrestoSports leagues
        if not post_mask.get("GAME_ID"):
            raise ValueError(f"player_game requires game_ids filter for {league}")

        frames = []
        for game_id in post_mask["GAME_ID"]:
            try:
                box_score = prestosports.fetch_prestosports_box_score(league, game_id)
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch {league} game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    elif league == "CEBL":
        # Canadian Elite Basketball League
        if not post_mask.get("GAME_ID"):
            raise ValueError("player_game requires game_ids filter for CEBL")

        frames = []
        for game_id in post_mask["GAME_ID"]:
            try:
                box_score = cebl.fetch_cebl_box_score(game_id)
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch CEBL game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    elif league == "U-SPORTS":
        # U SPORTS (Canada)
        if not post_mask.get("GAME_ID"):
            raise ValueError("player_game requires game_ids filter for U-SPORTS")

        frames = []
        for game_id in post_mask["GAME_ID"]:
            try:
                box_score = prestosports.fetch_prestosports_box_score(
                    league="U-SPORTS", game_id=str(game_id)
                )
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch U-SPORTS game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    elif league == "OTE":
        # Overtime Elite
        if not post_mask.get("GAME_ID"):
            raise ValueError("player_game requires game_ids filter for OTE")

        frames = []
        for game_id in post_mask["GAME_ID"]:
            try:
                box_score = ote.fetch_ote_box_score(game_id)
                if not box_score.empty:
                    frames.append(box_score)
            except Exception as e:
                logger.warning(f"Failed to fetch OTE game {game_id}: {e}")

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    else:
        raise ValueError(f"Unsupported league for player_game: {league}")

    # Apply post-mask
    df = apply_post_mask(df, post_mask)

    # Add league context
    df = add_league_context(df, league)

    # Apply per_mode aggregation if specified
    per_mode = params.get("PerMode")
    if per_mode and per_mode != "Totals":
        # Import here to avoid circular dependency
        from ..compose.enrichers import aggregate_per_mode

        df = aggregate_per_mode(df, per_mode=per_mode)
        logger.info(f"Aggregated player_game data by {per_mode}: {len(df)} players")

    return df


def _fetch_team_game(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch team/game data (team box scores)

    Currently returns schedule with scores as a proxy for team stats.
    """
    # For now, use schedule as team/game data
    # TODO: Add team-level aggregated stats
    return _fetch_schedule(compiled)


def _fetch_play_by_play(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch play-by-play data

    Supports: NCAA-MBB, NCAA-WBB, EuroLeague, EuroCup, G-League

    Requires game_ids filter.
    """
    params = compiled["params"]
    post_mask = compiled["post_mask"]
    meta = compiled["meta"]

    league = meta.get("league")

    if not post_mask.get("GAME_ID"):
        raise ValueError("play_by_play requires game_ids filter")

    # Extract season for leagues that need it
    season_str = params.get("Season", "2024-25")

    frames = []

    for game_id in post_mask["GAME_ID"]:
        try:
            if league == "NCAA-MBB":
                # Use CBBpy for NCAA-MBB PBP (has shot coordinates ESPN lacks)
                pbp = cbbpy_mbb.fetch_cbbpy_pbp(game_id)
                frames.append(pbp)

            elif league == "NCAA-WBB":
                game_data = fetchers.espn_wbb.fetch_espn_wbb_game_summary(game_id)
                frames.append(game_data["plays"])

            elif league == "EuroLeague":
                season_str = params.get("Season", "E2024")
                season = _parse_euroleague_season(season_str)
                pbp = fetchers.euroleague.fetch_euroleague_play_by_play(
                    season, int(game_id), competition="E"
                )
                frames.append(pbp)

            elif league == "EuroCup":
                season_str = params.get("Season", "U2024")
                season = _parse_euroleague_season(season_str)
                pbp = fetchers.euroleague.fetch_euroleague_play_by_play(
                    season, int(game_id), competition="U"
                )
                frames.append(pbp)

            elif league == "G-League":
                # G League play-by-play via stats.gleague.nba.com
                pbp = gleague.fetch_gleague_play_by_play(game_id)
                frames.append(pbp)

            elif league == "BCL":
                # BCL play-by-play (mostly unavailable)
                pbp = bcl.fetch_pbp(season=season_str)
                frames.append(pbp)

            elif league == "NBL":
                # NBL play-by-play
                pbp = nbl_official.fetch_nbl_pbp(season=season_str, game_id=game_id)
                frames.append(pbp)

            elif league in ["ACB", "LNB", "BBL", "BSL", "LBA"]:
                # European domestic leagues PBP (mostly unavailable)
                pbp = domestic_euro.fetch_domestic_euro_play_by_play(league, game_id)
                frames.append(pbp)

            elif league in ["NJCAA", "NAIA"]:
                # PrestoSports leagues (PBP unavailable)
                pbp = prestosports.fetch_prestosports_play_by_play(league, game_id)
                frames.append(pbp)

            elif league == "CEBL":
                # CEBL play-by-play (unavailable)
                pbp = cebl.fetch_cebl_play_by_play(game_id)
                frames.append(pbp)

            elif league == "U-SPORTS":
                # U SPORTS play-by-play (likely unavailable)
                pbp = prestosports.fetch_prestosports_play_by_play(
                    league="U-SPORTS", game_id=str(game_id)
                )
                frames.append(pbp)

            elif league == "OTE":
                # Overtime Elite play-by-play (AVAILABLE - unique!)
                pbp = ote.fetch_ote_play_by_play(game_id)
                frames.append(pbp)

            else:
                raise ValueError(f"Unsupported league for pbp: {league}")

        except Exception as e:
            logger.warning(f"Failed to fetch PBP for game {game_id}: {e}")

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # Apply post-mask
    df = apply_post_mask(df, post_mask)

    return df


def _fetch_shots(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch shot chart data with flexible filtering

    Supports season-level queries with optional team/player/period/minute filters.
    GAME_ID filtering is now optional (not required).

    Strategy:
    1. Try LeagueSourceConfig.fetch_shots for season-level fetch (preferred)
    2. Fallback to per-game loops for leagues without season-level support
    3. Apply shot-level filters (team, player, quarter, game-minute)

    Supported leagues: NCAA-MBB (CBBpy), EuroLeague, EuroCup, G-League, NBL, etc.
    """
    from ..catalog.sources import get_league_source_config
    from ..compose.shots import apply_shot_filters
    from ..filters.spec import FilterSpec

    params = compiled["params"]
    post_mask = compiled["post_mask"]
    meta = compiled["meta"]

    league = meta.get("league")

    # No longer require game_ids - we can now do season-level queries
    # But we do require at least (league AND season) OR game_ids to avoid
    # accidentally loading entire multi-year datasets
    if not league:
        raise ValueError("shots dataset requires 'league' filter")

    season = params.get("Season")
    game_ids = post_mask.get("GAME_ID")

    if not season and not game_ids:
        raise ValueError(
            "shots dataset requires at least one of: 'season' or 'game_ids' to limit dataset size"
        )

    # Extract season for leagues that need it
    season_str_generic = params.get("Season", "2024-25")
    season_type = params.get("SeasonType", "Regular Season")

    # Try to use LeagueSourceConfig.fetch_shots for season-level fetch (preferred)
    src_cfg = get_league_source_config(league)
    if src_cfg and src_cfg.fetch_shots and season:
        # Modern approach: season-level fetch with DataFrame filtering
        # This is more efficient than per-game loops
        logger.info(f"Fetching shots via LeagueSourceConfig for {league} season {season}")
        try:
            df = src_cfg.fetch_shots(season=season, season_type=season_type)

            # Apply shot-level filters (team, player, quarter, game-minute)
            # Build FilterSpec from compiled params and post_mask
            filter_spec = FilterSpec(
                league=league,
                season=season,
                season_type=season_type,
                team=post_mask.get("TEAM_NAME"),  # post_mask uses TEAM_NAME, not TEAM
                team_ids=post_mask.get("TEAM_ID"),
                opponent=post_mask.get("OPPONENT_NAME"),  # post_mask uses OPPONENT_NAME
                player=post_mask.get("PLAYER_NAME"),
                player_ids=post_mask.get("PLAYER_ID"),
                game_ids=game_ids,  # Optional filter
                quarter=post_mask.get("PERIOD") or post_mask.get("QUARTER"),
                min_game_minute=params.get("MinGameMinute"),
                max_game_minute=params.get("MaxGameMinute"),
            )

            df = apply_shot_filters(df, filter_spec)
            return df

        except Exception as e:
            logger.warning(
                f"Failed to fetch shots via LeagueSourceConfig for {league}: {e}. "
                "Falling back to per-game fetch."
            )
            # Fall through to per-game logic below

    # Fallback: per-game loops for leagues without season-level support
    # OR when season-level fetch failed
    # This requires game_ids
    if not game_ids:
        raise ValueError(
            f"League {league} does not support season-level shot queries. "
            "Please provide game_ids filter."
        )

    frames = []

    if league == "NCAA-MBB":
        # Use CBBpy PBP to extract shots with coordinates
        for game_id in post_mask["GAME_ID"]:
            try:
                pbp = cbbpy_mbb.fetch_cbbpy_pbp(game_id)
                shots = cbbpy_mbb.extract_shots_from_pbp(pbp)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch shots for game {game_id}: {e}")

    elif league == "EuroLeague":
        # EuroLeague shot data
        season_str = params.get("Season", "E2024")
        season = _parse_euroleague_season(season_str)

        for game_code in post_mask["GAME_ID"]:
            try:
                shots = fetchers.euroleague.fetch_euroleague_shot_data(
                    season, int(game_code), competition="E"
                )
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch shots for game {game_code}: {e}")

    elif league == "EuroCup":
        # EuroCup shot data (same API as EuroLeague)
        season_str = params.get("Season", "U2024")
        season = _parse_euroleague_season(season_str)

        for game_code in post_mask["GAME_ID"]:
            try:
                shots = fetchers.euroleague.fetch_euroleague_shot_data(
                    season, int(game_code), competition="U"
                )
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch shots for game {game_code}: {e}")

    elif league == "G-League":
        # G League shot chart data via stats.gleague.nba.com
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = gleague.fetch_gleague_shot_chart(game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch G League shots for game {game_id}: {e}")

    elif league == "BCL":
        # BCL shots (unavailable - requires FIBA LiveStats)
        for game_id in post_mask["GAME_ID"]:
            try:
                # BCL doesn't provide shot chart data (FIBA HTML doesn't include shot coordinates)
                shots = pd.DataFrame()  # Empty DataFrame with proper schema will be added later
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch BCL shots for game {game_id}: {e}")

    elif league == "NBL":
        # NBL shots
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = nbl_official.fetch_nbl_shots(season=season_str_generic, game_id=game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch NBL shots for game {game_id}: {e}")

    elif league in ["ACB", "LNB", "BBL", "BSL", "LBA"]:
        # European domestic leagues shots (mostly unavailable)
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = domestic_euro.fetch_domestic_euro_shot_chart(league, game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch {league} shots for game {game_id}: {e}")

    elif league in ["NJCAA", "NAIA"]:
        # PrestoSports leagues (shots unavailable)
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = prestosports.fetch_prestosports_shot_chart(league, game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch {league} shots for game {game_id}: {e}")

    elif league == "CEBL":
        # CEBL shots (unavailable)
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = cebl.fetch_cebl_shot_chart(game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch CEBL shots for game {game_id}: {e}")

    elif league == "U-SPORTS":
        # U SPORTS shots (unavailable)
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = prestosports.fetch_prestosports_shot_chart(
                    league="U-SPORTS", game_id=str(game_id)
                )
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch U-SPORTS shots for game {game_id}: {e}")

    elif league == "OTE":
        # Overtime Elite shots (coordinates unavailable, but shot info in PBP)
        for game_id in post_mask["GAME_ID"]:
            try:
                shots = ote.fetch_ote_shot_chart(game_id)
                frames.append(shots)
            except Exception as e:
                logger.warning(f"Failed to fetch OTE shots for game {game_id}: {e}")

    else:
        raise ValueError(f"Shot data not available for league: {league}")

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # Apply post-mask (legacy filtering)
    df = apply_post_mask(df, post_mask)

    # Apply shot-level filters (team, player, quarter, game-minute)
    # This ensures consistent filtering for both registry-based and per-game fetching
    filter_spec = FilterSpec(
        league=league,
        season=season,
        season_type=season_type,
        team=post_mask.get("TEAM"),
        team_ids=post_mask.get("TEAM_ID"),
        opponent=post_mask.get("OPP_TEAM"),
        player=post_mask.get("PLAYER_NAME") or post_mask.get("PLAYER"),
        player_ids=post_mask.get("PLAYER_ID"),
        game_ids=game_ids,  # Already applied via per-game loop, but safe to apply again
        quarter=post_mask.get("PERIOD") or post_mask.get("QUARTER"),
        min_game_minute=params.get("MinGameMinute"),
        max_game_minute=params.get("MaxGameMinute"),
    )

    df = apply_shot_filters(df, filter_spec)

    return df


def _fetch_player_season(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch player season aggregates

    Strategy (config-driven):
    1. Check LeagueSourceConfig for league-specific fetch function
    2. If configured, use that (HTML scraper, API client, etc.)
    3. Otherwise, fall back to generic path (aggregate from player_game)

    Supports: All leagues via LeagueSourceConfig
    """
    params = compiled["params"]
    meta = compiled["meta"]
    league = meta.get("league")

    logger.info(f"Fetching player_season for {league}, season {params.get('Season')}")

    # Check if league has a config-driven direct season fetcher
    cfg = get_league_source_config(league)
    if cfg is not None and cfg.fetch_player_season is not None:
        logger.info(f"Using {cfg.player_season_source} source for {league} player_season")
        return cfg.fetch_player_season(
            season=params.get("Season", "2024"),
            per_mode=params.get("PerMode", "Totals"),
        )

    # Fetch all player_game data for this season
    # We remove per_mode from params to get raw game data, then aggregate ourselves
    # IMPORTANT: Use deep copy to avoid polluting the original compiled dict
    # Deep copy ensures nested structures (lists, dicts) are not shared between calls
    game_compiled = copy.deepcopy(compiled)
    # Remove PerMode from params (we'll apply it during aggregation)
    game_compiled["params"].pop("PerMode", None)

    # FIX: For all leagues, fetch schedule first to get game IDs
    # This is required because _fetch_player_game() requires either TEAM_ID or GAME_ID
    # in the post_mask for NCAA leagues (validation at line 203-204)
    # For EuroLeague, this ensures we have all games for the season
    logger.info(f"Fetching season schedule to get all game IDs for {league}")

    # Fetch the season schedule using _fetch_schedule()
    # Use deep copy to prevent state pollution from shared nested structures
    schedule_compiled = {
        "params": copy.deepcopy(params),
        "post_mask": {},  # No filters - want ALL games for the season
        "meta": copy.deepcopy(meta),
    }

    # Get season schedule
    schedule = _fetch_schedule(schedule_compiled)

    if schedule.empty:
        logger.warning(f"No games found in schedule for {league} season {params.get('Season')}")
        return pd.DataFrame()

    # Extract all game IDs from schedule
    # Use league-specific column name: GAME_ID for NCAA, GAME_CODE for EuroLeague
    game_id_col = "GAME_CODE" if league == "EuroLeague" else "GAME_ID"
    # Convert to strings to ensure type consistency (prevent integer/string mismatches)
    game_ids = [str(gid) for gid in schedule[game_id_col].unique().tolist()]
    logger.info(f"Found {len(game_ids)} games in season schedule")

    # Inject game IDs into post_mask so _fetch_player_game() validation passes
    # No need for .copy() since game_compiled is already a deep copy
    game_compiled["post_mask"][game_id_col] = game_ids

    # Fetch player game data (now works for both NCAA and EuroLeague)
    player_games = _fetch_player_game(game_compiled)

    if player_games.empty:
        logger.warning("_fetch_player_season: player_games is empty, returning empty DataFrame")
        return player_games

    # Aggregate to season level using per_mode
    from ..compose.enrichers import aggregate_per_mode

    per_mode = params.get("PerMode", "Totals")

    # Group by player (and season if available)
    group_cols = []
    if "PLAYER_ID" in player_games.columns:
        group_cols.append("PLAYER_ID")
    if "PLAYER_NAME" in player_games.columns and "PLAYER_NAME" not in group_cols:
        group_cols.append("PLAYER_NAME")
    if "SEASON" in player_games.columns:
        group_cols.append("SEASON")

    season_stats = aggregate_per_mode(player_games, per_mode=per_mode, group_by=group_cols)

    logger.info(f"Aggregated {len(player_games)} games into {len(season_stats)} player seasons")

    return season_stats


def _unpivot_schedule_to_team_games(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """Transform schedule data (HOME/AWAY format) into team-game format.

    Creates 2 rows per game: one for home team, one for away team.
    Adds TEAM_NAME, TEAM_ID, OPPONENT_NAME, IS_HOME, WIN columns.

    Args:
        schedule_df: Schedule DataFrame with HOME_TEAM/AWAY_TEAM columns

    Returns:
        DataFrame with TEAM_NAME column and team-level stats
    """
    import pandas as pd

    # FIX: Use .get() to safely handle missing columns (EuroLeague has different column names)
    # Check if this is NCAA-style (HOME_TEAM_ID/AWAY_TEAM_ID) or EuroLeague-style
    if "HOME_TEAM_ID" not in schedule_df.columns:
        # EuroLeague doesn't have separate HOME/AWAY team records in schedule
        # Skip unpivoting - just return as-is
        logger.warning("Schedule data missing HOME_TEAM_ID - cannot unpivot. Returning as-is.")
        return schedule_df

    # Create home team records
    home_games = schedule_df.copy()
    home_games["TEAM_ID"] = home_games.get("HOME_TEAM_ID", "")
    home_games["TEAM_NAME"] = home_games.get("HOME_TEAM", "")
    home_games["TEAM_ABBREVIATION"] = home_games.get("HOME_TEAM_ABBREVIATION", "")
    home_games["OPPONENT_ID"] = home_games.get("AWAY_TEAM_ID", "")
    home_games["OPPONENT_NAME"] = home_games.get("AWAY_TEAM", "")
    home_games["OPPONENT_ABBREVIATION"] = home_games.get("AWAY_TEAM_ABBREVIATION", "")
    home_games["POINTS"] = home_games.get("HOME_SCORE", 0)
    home_games["OPPONENT_POINTS"] = home_games.get("AWAY_SCORE", 0)
    home_games["IS_HOME"] = True

    # Create away team records
    away_games = schedule_df.copy()
    away_games["TEAM_ID"] = away_games.get("AWAY_TEAM_ID", "")
    away_games["TEAM_NAME"] = away_games.get("AWAY_TEAM", "")
    away_games["TEAM_ABBREVIATION"] = away_games.get("AWAY_TEAM_ABBREVIATION", "")
    away_games["OPPONENT_ID"] = away_games.get("HOME_TEAM_ID", "")
    away_games["OPPONENT_NAME"] = away_games.get("HOME_TEAM", "")
    away_games["OPPONENT_ABBREVIATION"] = away_games.get("HOME_TEAM_ABBREVIATION", "")
    away_games["POINTS"] = away_games.get("AWAY_SCORE", 0)
    away_games["OPPONENT_POINTS"] = away_games.get("HOME_SCORE", 0)
    away_games["IS_HOME"] = False

    # Add WIN column (only for completed games)
    for df in [home_games, away_games]:
        df["WIN"] = (df["POINTS"] > df["OPPONENT_POINTS"]) & (df["STATUS"] == "STATUS_FINAL")
        df["LOSS"] = (df["POINTS"] < df["OPPONENT_POINTS"]) & (df["STATUS"] == "STATUS_FINAL")

    # Combine and drop old columns
    team_games = pd.concat([home_games, away_games], ignore_index=True)

    # Drop the original HOME_/AWAY_ columns
    cols_to_drop = [
        "HOME_TEAM_ID",
        "HOME_TEAM",
        "HOME_TEAM_ABBREVIATION",
        "HOME_SCORE",
        "AWAY_TEAM_ID",
        "AWAY_TEAM",
        "AWAY_TEAM_ABBREVIATION",
        "AWAY_SCORE",
    ]
    team_games = team_games.drop(columns=[c for c in cols_to_drop if c in team_games.columns])

    return team_games


def _fetch_team_season(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch team season aggregates

    Strategy (config-driven):
    1. Check LeagueSourceConfig for league-specific fetch function
    2. If configured, use that (HTML scraper, API client, etc.)
    3. Otherwise, fall back to generic path (aggregate from team_game)

    Supports: All leagues via LeagueSourceConfig
    """
    params = compiled["params"]
    meta = compiled["meta"]
    league = meta.get("league")

    logger.info(f"Fetching team_season for {league}, season {params.get('Season')}")

    # Check if league has a config-driven direct season fetcher
    cfg = get_league_source_config(league)
    if cfg is not None and cfg.fetch_team_season is not None:
        logger.info(f"Using {cfg.team_season_source} source for {league} team_season")
        return cfg.fetch_team_season(season=params.get("Season", "2024"))

    # Fetch all team_game data (currently proxied to schedule)
    team_games = _fetch_team_game(compiled)

    if team_games.empty:
        return team_games

    # Check if we need to unpivot schedule data
    if "HOME_TEAM" in team_games.columns and "TEAM_NAME" not in team_games.columns:
        # For schedule-based data, unpivot HOME/AWAY to create TEAM_NAME column
        logger.info("team_season unpivoting schedule data to create TEAM_NAME column")
        team_games = _unpivot_schedule_to_team_games(team_games)

    # Determine grouping columns
    group_cols = []
    if "TEAM_ID" in team_games.columns:
        group_cols.append("TEAM_ID")
    if "TEAM_NAME" in team_games.columns and "TEAM_NAME" not in group_cols:
        group_cols.append("TEAM_NAME")
    if "SEASON" in team_games.columns:
        group_cols.append("SEASON")

    # Aggregate numeric columns
    agg_dict = {}
    for col in team_games.columns:
        if col not in group_cols and pd.api.types.is_numeric_dtype(team_games[col]):
            # Sum for WIN/LOSS, mean for other stats
            if col in ["WIN", "LOSS", "POINTS", "OPPONENT_POINTS"]:
                agg_dict[col] = "sum"
            else:
                agg_dict[col] = "mean"

    if agg_dict:
        season_stats = team_games.groupby(group_cols, as_index=False).agg(agg_dict)

        # Add games played column
        season_stats["GP"] = (
            team_games.groupby([c for c in group_cols if c in team_games.columns]).size().values
        )

        # Add WIN% if we have wins
        if "WIN" in season_stats.columns and "GP" in season_stats.columns:
            season_stats["WIN_PCT"] = season_stats["WIN"] / season_stats["GP"]

        logger.info(f"Aggregated {len(team_games)} games into {len(season_stats)} team seasons")
        return season_stats

    return team_games


def _fetch_player_team_season(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch player × team × season aggregates

    This captures mid-season transfers by grouping by BOTH player AND team.
    If a player played for multiple teams in one season, they'll have multiple rows.

    Strategy:
    1. For NCAA: Fetch season schedule first, extract game IDs, then fetch player_game data
    2. For EuroLeague: Existing logic works
    3. Aggregate by (player, team, season) to capture mid-season transfers

    Supports: NCAA-MBB, NCAA-WBB, EuroLeague
    """
    params = compiled["params"]
    _post_mask = compiled["post_mask"]  # Reserved for future filtering
    meta = compiled["meta"]

    league = meta.get("league")

    logger.info(f"Fetching player_team_season for {league}, season {params.get('Season')}")

    # Fetch all player_game data for this season
    # Use deep copy to prevent state pollution from shared nested structures
    game_compiled = copy.deepcopy(compiled)
    # Remove PerMode from params (we'll apply it during aggregation)
    game_compiled["params"].pop("PerMode", None)

    # FIX: For all leagues, fetch schedule first to get game IDs
    # This is required because _fetch_player_game() requires either TEAM_ID or GAME_ID
    # in the post_mask for NCAA leagues (validation at line 203-204)
    # For EuroLeague, this ensures we have all games for the season
    logger.info(f"Fetching season schedule to get all game IDs for {league}")

    # Fetch the season schedule using _fetch_schedule()
    # Use deep copy to prevent state pollution from shared nested structures
    schedule_compiled = {
        "params": copy.deepcopy(params),
        "post_mask": {},  # No filters - want ALL games for the season
        "meta": copy.deepcopy(meta),
    }

    # Get season schedule
    schedule = _fetch_schedule(schedule_compiled)

    if schedule.empty:
        logger.warning(f"No games found in schedule for {league} season {params.get('Season')}")
        return pd.DataFrame()

    # Extract all game IDs from schedule
    # Use league-specific column name: GAME_ID for NCAA, GAME_CODE for EuroLeague
    game_id_col = "GAME_CODE" if league == "EuroLeague" else "GAME_ID"
    # Convert to strings to ensure type consistency (prevent integer/string mismatches)
    game_ids = [str(gid) for gid in schedule[game_id_col].unique().tolist()]
    logger.info(f"Found {len(game_ids)} games in season schedule")

    # Inject game IDs into post_mask
    # No need for .copy() since game_compiled is already a deep copy
    game_compiled["post_mask"][game_id_col] = game_ids

    # Fetch player game data (now works for both NCAA and EuroLeague)
    player_games = _fetch_player_game(game_compiled)

    if player_games.empty:
        return player_games

    # Aggregate to season level, grouped by BOTH player AND team
    from ..compose.enrichers import aggregate_per_mode

    per_mode = params.get("PerMode", "Totals")

    # Group by player AND team (key difference from player_season)
    group_cols = []
    if "PLAYER_ID" in player_games.columns:
        group_cols.append("PLAYER_ID")
    if "PLAYER_NAME" in player_games.columns and "PLAYER_NAME" not in group_cols:
        group_cols.append("PLAYER_NAME")
    # FIX: CBBpy data uses 'TEAM' column, not 'TEAM_ID' or 'TEAM_NAME'
    # Check for all three possible column names to ensure team context is captured
    if "TEAM_ID" in player_games.columns:
        group_cols.append("TEAM_ID")
    elif "TEAM_NAME" in player_games.columns:
        group_cols.append("TEAM_NAME")
    elif "TEAM" in player_games.columns:
        group_cols.append("TEAM")
    if "SEASON" in player_games.columns:
        group_cols.append("SEASON")

    season_stats = aggregate_per_mode(player_games, per_mode=per_mode, group_by=group_cols)

    logger.info(
        f"Aggregated {len(player_games)} games into {len(season_stats)} player-team seasons "
        f"(captures transfers)"
    )

    return season_stats


def _fetch_prospect_player_season(compiled: dict[str, Any]) -> pd.DataFrame:
    """Fetch unified prospect player season stats across all pre-NBA leagues

    Aggregates player_season data from all college and prepro leagues into a single
    DataFrame with LEAGUE column for league identification. Useful for cross-league
    prospect comparisons (e.g., "Who are the top scorers across all pre-NBA leagues?").

    Strategy:
    1. Get all pre-NBA leagues (college + prepro, excluding WNBA)
    2. For each league, fetch player_season data using existing _fetch_player_season
    3. Add LEAGUE column to each result
    4. Concatenate all results into unified DataFrame
    5. Handle errors gracefully (skip leagues that fail)

    Args:
        compiled: Compiled request parameters (season, season_type, per_mode, etc.)

    Returns:
        DataFrame with unified prospect stats from all pre-NBA leagues

    Example:
        >>> # Get top scorers across all pre-NBA leagues for 2024
        >>> df = get_dataset("prospect_player_season", season="2024", per_mode="PerGame")
        >>> top_scorers = df.nlargest(50, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "LEAGUE", "PTS", "REB", "AST"]])
    """
    params = compiled["params"]
    season = params.get("Season", "2024")
    per_mode = params.get("PerMode", "Totals")

    logger.info(f"Fetching prospect_player_season for season {season}, per_mode {per_mode}")

    # Get all pre-NBA leagues (college + prepro, excluding WNBA)
    college_leagues = get_leagues_by_level("college")
    prepro_leagues = get_leagues_by_level("prepro")
    prospect_leagues = college_leagues + prepro_leagues

    logger.info(
        f"Fetching player_season from {len(prospect_leagues)} leagues: "
        f"{len(college_leagues)} college + {len(prepro_leagues)} prepro"
    )

    frames = []
    successful_leagues = []
    failed_leagues = []

    for league in prospect_leagues:
        try:
            # Create a compiled request for this specific league
            league_compiled = copy.deepcopy(compiled)
            league_compiled["meta"]["league"] = league

            # Fetch player_season for this league
            logger.info(f"Fetching player_season for {league}...")
            df = _fetch_player_season(league_compiled)

            # Only add if we got data
            if not df.empty:
                # Add LEAGUE column to identify source league
                df["LEAGUE"] = league
                frames.append(df)
                successful_leagues.append(league)
                logger.info(f"✓ {league}: {len(df)} player-seasons")
            else:
                logger.info(f"⊘ {league}: empty (scaffold or no data)")

        except Exception as e:
            logger.warning(f"✗ {league} failed: {e}")
            failed_leagues.append(league)

    # Concatenate all successful fetches
    if frames:
        result = pd.concat(frames, ignore_index=True)
        logger.info(
            f"Combined {len(result)} player-seasons from {len(successful_leagues)}/{len(prospect_leagues)} leagues"
        )

        if failed_leagues:
            logger.warning(f"Failed leagues: {', '.join(failed_leagues)}")

        return result
    else:
        logger.warning(f"No data fetched from any of {len(prospect_leagues)} leagues")
        return pd.DataFrame()


# ==============================================================================
# Dataset Registration
# ==============================================================================

DatasetRegistry.register(
    id="schedule",
    keys=["GAME_ID"],
    filters=["season", "season_type", "date", "league", "team", "opponent"],
    fetch=_fetch_schedule,
    description="Game schedules and results",
    sources=["ESPN", "EuroLeague", "NBA Stats", "WNBA Stats", "CEBL", "OTE", "PrestoSports"],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=[
        "GAME_ID",
        "GAME_DATE",
        "HOME_TEAM_NAME",
        "AWAY_TEAM_NAME",
        "HOME_SCORE",
        "AWAY_SCORE",
        "STATUS",
    ],
)

DatasetRegistry.register(
    id="player_game",
    keys=["PLAYER_ID", "GAME_ID"],
    filters=[
        "season",
        "season_type",
        "date",
        "league",
        "team",
        "player",
        "game_ids",
        "last_n_games",
        "min_minutes",
    ],
    fetch=_fetch_player_game,
    description="Per-player per-game statistics (box scores)",
    sources=["ESPN", "EuroLeague", "NBA Stats", "WNBA Stats", "CEBL", "OTE", "PrestoSports"],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=[
        "PLAYER_NAME",
        "TEAM_NAME",
        "GAME_ID",
        "PTS",
        "REB",
        "AST",
        "MIN",
        "FGM",
        "FGA",
    ],
    requires_game_id=False,  # Can use team filter
)

DatasetRegistry.register(
    id="team_game",
    keys=["TEAM_ID", "GAME_ID"],
    filters=["season", "season_type", "date", "league", "team", "opponent", "home_away"],
    fetch=_fetch_team_game,
    description="Per-team per-game results",
    sources=["ESPN", "EuroLeague", "NBA Stats", "WNBA Stats", "CEBL", "OTE", "PrestoSports"],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=["TEAM_NAME", "GAME_ID", "GAME_DATE", "OPPONENT", "HOME_AWAY", "SCORE"],
)

DatasetRegistry.register(
    id="pbp",
    keys=["GAME_ID", "PLAY_ID"],
    filters=["game_ids", "league", "quarter", "team", "player"],
    fetch=_fetch_play_by_play,
    description="Play-by-play event data",
    sources=["ESPN", "EuroLeague", "NBA Stats", "WNBA Stats", "CEBL", "OTE", "PrestoSports"],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=["GAME_ID", "PERIOD", "CLOCK", "PLAY_TYPE", "TEXT", "SCORE"],
    requires_game_id=True,
)

DatasetRegistry.register(
    id="shots",
    keys=["GAME_ID", "SHOT_ID"],
    filters=[
        "game_ids",  # Optional (no longer required!)
        "season",  # Required (or game_ids)
        "season_type",  # Optional (Regular Season, Playoffs, etc.)
        "league",  # Required
        "player",  # Optional
        "team",  # Optional
        "opponent",  # Optional
        "quarter",  # Optional (period/quarter filter)
        "min_game_minute",  # Optional (game-minute range)
        "max_game_minute",  # Optional (game-minute range)
    ],
    fetch=_fetch_shots,
    description=(
        "Shot chart data with X/Y coordinates. "
        "Supports flexible queries by team, player, quarter, and game-minute. "
        "Full data: NCAA-MBB, EuroLeague, EuroCup, G-League, WNBA, NBL. "
        "Limited: CEBL, OTE, PrestoSports."
    ),
    sources=[
        "CBBpy",
        "EuroLeague",
        "NBA Stats",
        "WNBA Stats",
        "NBL (nblR)",
        "CEBL",
        "OTE",
        "PrestoSports",
    ],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=["shot_x", "shot_y", "shooter", "LOC_X", "LOC_Y", "PLAYER_NAME", "SHOT_MADE"],
    # requires_game_id=True,  # REMOVED - no longer required!
)

DatasetRegistry.register(
    id="player_season",
    keys=["PLAYER_ID", "SEASON"],
    filters=["season", "season_type", "league", "team", "player", "per_mode", "min_minutes"],
    fetch=_fetch_player_season,
    description="Per-player season aggregates (totals/averages)",
    sources=[
        "ESPN",
        "EuroLeague",
        "NBA Stats",
        "WNBA Stats",
        "CEBL",
        "OTE",
        "PrestoSports",
        "Web Scraping",
    ],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=["PLAYER_NAME", "SEASON", "GP", "PTS", "REB", "AST", "MIN", "FG_PCT"],
    requires_game_id=False,
)

DatasetRegistry.register(
    id="team_season",
    keys=["TEAM_ID", "SEASON"],
    filters=["season", "season_type", "league", "team", "conference"],
    fetch=_fetch_team_season,
    description="Per-team season aggregates",
    sources=[
        "ESPN",
        "EuroLeague",
        "NBA Stats",
        "WNBA Stats",
        "CEBL",
        "OTE",
        "PrestoSports",
        "Web Scraping",
    ],
    leagues=ALL_LEAGUES,
    levels=["college", "prepro", "pro"],
    sample_columns=["TEAM_NAME", "SEASON", "GP", "W", "L", "PTS", "OPP_PTS"],
    requires_game_id=False,
)

DatasetRegistry.register(
    id="prospect_player_season",
    keys=["PLAYER_ID", "SEASON", "LEAGUE"],
    filters=["season", "season_type", "per_mode", "min_minutes", "team", "player"],
    fetch=_fetch_prospect_player_season,
    description="Unified prospect player season stats across all pre-NBA leagues (college + prepro, excludes WNBA). Aggregates player_season from 18 leagues with LEAGUE column for cross-league comparisons. Note: This dataset does not support league filtering - it always fetches from all pre-NBA leagues.",
    sources=["ESPN", "EuroLeague", "NBA Stats", "CEBL", "OTE", "PrestoSports", "Web Scraping"],
    leagues=["ALL"],  # Special marker: fetches from all college+prepro leagues
    levels=["college", "prepro"],
    sample_columns=["PLAYER_NAME", "LEAGUE", "SEASON", "GP", "PTS", "REB", "AST", "MIN", "FG_PCT"],
    requires_game_id=False,
)

DatasetRegistry.register(
    id="player_team_season",
    keys=["PLAYER_ID", "TEAM_ID", "SEASON"],
    filters=["season", "season_type", "league", "team", "player", "per_mode", "min_minutes"],
    fetch=_fetch_player_team_season,
    description="Per-player per-team season stats (captures mid-season transfers)",
    sources=["ESPN", "EuroLeague"],
    leagues=["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
    levels=["college", "pro"],
    sample_columns=["PLAYER_NAME", "TEAM_NAME", "SEASON", "GP", "PTS", "REB", "AST"],
    requires_game_id=False,
)


# ==============================================================================
# Public API
# ==============================================================================


def list_datasets(pre_only: bool = True) -> list[dict[str, Any]]:
    """List all available datasets with metadata

    Args:
        pre_only: If True, filter leagues to pre-NBA/WNBA only (default: True).
                 Set to False to include pro leagues.

    Returns:
        List of dataset info dictionaries with:
            - id: Dataset identifier
            - keys: Primary key columns
            - supports: Supported filter names
            - description: Dataset description
            - sources: Data sources
            - leagues: Supported leagues (filtered by pre_only)
            - sample_columns: Example columns
            - requires_game_id: Whether game_id filter is required
            - levels: Competition levels included

    Example:
        >>> datasets = list_datasets()
        >>> for ds in datasets:
        ...     print(f"{ds['id']}: {ds['description']}")
        schedule: Game schedules and results
        player_game: Per-player per-game statistics
        ...

        >>> # Include professional leagues
        >>> datasets_all = list_datasets(pre_only=False)
    """
    infos = DatasetRegistry.list_infos()

    # Filter leagues in each dataset based on pre_only
    result = []
    for info in infos:
        info_dict = info.model_dump()
        if pre_only and info_dict.get("leagues"):
            info_dict["leagues"] = filter_leagues_by_level(info_dict["leagues"], pre_only=True)
        result.append(info_dict)

    return result


def get_dataset(
    grouping: str,
    filters: dict[str, Any],
    columns: list[str] | None = None,
    limit: int | None = None,
    as_format: str = "pandas",
    name_resolver: Callable[[str, str, str | None], int | None] | None = None,
    force_fresh: bool = False,
    pre_only: bool = True,
) -> Any:
    """Fetch a dataset with filters

    Args:
        grouping: Dataset ID (e.g., "player_game", "schedule", "pbp")
        filters: Filter dictionary (converted to FilterSpec)
        columns: Optional list of columns to return
        limit: Optional row limit
        as_format: Output format ("pandas", "json", "parquet")
        name_resolver: Optional function to resolve entity names to IDs.
                      If None, uses default resolver with name normalization.
                      Set to False to disable name resolution entirely.
        force_fresh: If True, bypass cache and fetch fresh data (default: False)
        pre_only: If True, exclude professional leagues (default: True).
                 Set to False to include pro leagues (EuroLeague, G-League, WNBA, etc.)

    Returns:
        DataFrame (pandas), list of dicts (json), or dict with path (parquet)

    Raises:
        KeyError: If dataset not found
        ValueError: If required filters missing or league not supported

    Examples:
        # Get schedule for today
        >>> df = get_dataset("schedule", {
        ...     "league": "NCAA-MBB",
        ...     "date": {"from": "2024-11-04", "to": "2024-11-04"}
        ... })

        # Get player stats for Duke last 5 games (name resolution automatic)
        >>> df = get_dataset("player_game", {
        ...     "league": "NCAA-MBB",
        ...     "season": "2025",
        ...     "team": ["Duke"],  # Normalized automatically
        ...     "last_n_games": 5,
        ...     "min_minutes": 10
        ... })

        # Get EuroLeague play-by-play
        >>> df = get_dataset("pbp", {
        ...     "league": "EuroLeague",
        ...     "game_ids": ["RS_ROUND_1_GAME_1"]
        ... })

        # Disable name resolution (use exact name matching only)
        >>> df = get_dataset("schedule", {
        ...     "league": "NCAA-MBB",
        ...     "season": "2025",
        ...     "team": ["Duke"]
        ... }, name_resolver=False)
    """
    # Validate dataset exists
    try:
        entry = DatasetRegistry.get(grouping)
    except KeyError:
        available = DatasetRegistry.list_ids()
        raise KeyError(
            f"Dataset '{grouping}' not found. Available: {', '.join(available)}"
        ) from None

    # Build FilterSpec
    spec = FilterSpec(**filters)

    # SCOPE ENFORCEMENT: Check pre_only filter
    if pre_only and spec.league and not is_pre_nba_league(spec.league):
        excluded_msg = get_excluded_leagues_message([spec.league])
        raise ValueError(
            f"League '{spec.league}' is not in scope (pre-NBA/WNBA prospects only). {excluded_msg}"
        )

    # Validate filters before compilation
    validation_warnings = validate_filters(
        dataset_id=grouping,
        spec=spec,
        dataset_leagues=entry.get("leagues", []),
        strict=False,  # Just warn, don't raise errors
    )

    # Log warnings for unsupported/problematic filters
    for warning in validation_warnings:
        logger.warning(f"Filter validation: {warning}")

    # Check required filters
    if entry.get("requires_game_id") and not spec.game_ids:
        raise ValueError(f"Dataset '{grouping}' requires game_ids filter")

    # Check league specified (for multi-league datasets)
    if not spec.league and len(entry.get("leagues", [])) > 1:
        raise ValueError(
            f"Dataset '{grouping}' supports multiple leagues. "
            f"Please specify 'league' filter: {entry['leagues']}"
        )

    # Handle name resolver parameter
    # - None (default): Use default resolver with name normalization
    # - False: Disable name resolution (exact name matching only)
    # - Function: Use provided resolver
    if name_resolver is None:
        resolver_fn = _create_default_name_resolver()
        logger.debug("Using default name resolver (with normalization)")
    elif name_resolver is False:
        resolver_fn = None
        logger.debug("Name resolution disabled (exact matching only)")
    else:
        resolver_fn = name_resolver
        logger.debug("Using custom name resolver")

    # Compile filters with name resolver
    compiled = compile_params(grouping, spec, name_resolver=resolver_fn)

    # Add limit and force_fresh to compiled params so fetchers can optimize
    if "meta" not in compiled:
        compiled["meta"] = {}
    # FIX: Use "is not None" instead of truthiness check to handle limit=0 correctly
    # Bug: "if limit:" evaluates to False when limit=0, causing limit to be ignored
    # Correct: "if limit is not None:" handles 0, None, and positive values properly
    if limit is not None:
        compiled["meta"]["limit"] = limit
    if force_fresh:
        compiled["params"]["ForceRefresh"] = True
        logger.debug("Force fresh data requested - bypassing cache")

    logger.info(f"Fetching dataset: {grouping}, league: {spec.league}, limit={limit}")

    # PRE-FETCH VALIDATION
    # Validate request BEFORE making API calls to fail fast on configuration errors
    validate_fetch_request(grouping, filters or {}, spec.league)

    # Fetch data
    fetch_fn = entry["fetch"]
    df = fetch_fn(compiled)

    # Select columns
    if columns:
        existing = [c for c in columns if c in df.columns]
        if existing:
            df = df[existing]
        else:
            logger.warning(f"No matching columns found. Available: {list(df.columns)}")

    # Apply limit as fallback (in case fetcher doesn't support it)
    # FIX: Use "is not None" to handle limit=0 correctly (0 is falsy but valid)
    if limit is not None and not df.empty and len(df) > limit:
        df = df.head(limit)

    # Format output
    if as_format == "pandas":
        return df
    elif as_format == "json":
        return df.to_dict(orient="records")
    elif as_format == "parquet":
        import tempfile

        path = tempfile.mkstemp(prefix=f"{grouping}_", suffix=".parquet")[1]
        df.to_parquet(path, index=False)
        return {"path": path, "rows": len(df)}
    else:
        raise ValueError(f"Unsupported format: {as_format}")
