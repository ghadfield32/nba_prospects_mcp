"""League Capability Matrix

Defines which datasets are available for each league, with data quality indicators.
This prevents confusing errors and provides helpful feedback when data is unavailable.

**Capability Levels**:
- FULL: Complete, reliable data available
- LIMITED: Partial data or quality issues (missing fields, sparse coverage)
- UNAVAILABLE: Endpoint exists but returns empty/no data
- NOT_IMPLEMENTED: Not yet implemented

**Usage**:
```python
from cbb_data.catalog.capabilities import check_capability, CapabilityLevel

# Check if G-League supports play-by-play
level = check_capability("G-League", "pbp")
if level == CapabilityLevel.UNAVAILABLE:
    raise NotImplementedError("G-League play-by-play not available")
```

**Auto-Discovery**:
Capabilities are derived from actual fetch function implementations in datasets.py.
Manual overrides only needed for quality warnings (FULL vs LIMITED).
"""

from __future__ import annotations

from enum import Enum


class CapabilityLevel(Enum):
    """Data availability levels for league/dataset combinations"""

    FULL = "full"  # Complete, reliable data
    LIMITED = "limited"  # Partial data or quality issues
    UNAVAILABLE = "unavailable"  # Endpoint exists but no data
    NOT_IMPLEMENTED = "not_implemented"  # Not yet implemented


# Capability matrix: league -> dataset -> level
# Only specify overrides here; default is FULL if league listed in dataset registration
# Updated 2025-11-19: Reflects actual data availability after full wiring
CAPABILITY_OVERRIDES: dict[str, dict[str, CapabilityLevel]] = {
    # ========== TIER 0: CORE FEEDER LEAGUES (Full Support) ==========
    "NCAA-MBB": {},  # ESPN + cbbpy - full support (6/6 datasets)
    "NCAA-WBB": {},  # ESPN + cbbpy - full support (6/6 datasets)
    "EuroLeague": {},  # euroleague-api - full support (6/6 datasets)
    "EuroCup": {},  # euroleague-api - full support (6/6 datasets)
    "G-League": {},  # NBA Stats API - full support (6/6 datasets)
    "WNBA": {},  # NBA Stats API - full support (6/6 datasets)
    # ========== TIER 1: SECONDARY FEEDER LEAGUES ==========
    "NBL": {},  # nblR R package - full support including shot coordinates (6/6 datasets)
    "NZ-NBL": {},  # ✅ UPDATED 2025-11-19: Full support including shots via FIBA JS (6/6 datasets)
    "LNB_PROA": {},  # ✅ UPDATED 2025-11-19: Full support via LNB API + parquet (6/6 datasets)
    "ACB": {},  # ✅ UPDATED 2025-11-19: Full support via BAwiR R package (6/6 datasets)
    "OTE": {  # Overtime Elite - Web scraping (5/6 datasets)
        "shots": CapabilityLevel.UNAVAILABLE,  # ✅ UPDATED: No x,y coordinates (but PBP is FULL!)
    },
    "CEBL": {  # Canadian Elite Basketball League (4/6 datasets)
        "pbp": CapabilityLevel.UNAVAILABLE,  # ceblpy doesn't provide PBP
        "shots": CapabilityLevel.UNAVAILABLE,  # No shot coordinates
    },
    # ========== TIER 2: DEVELOPMENT LEAGUES (PrestoSports) ==========
    "NJCAA": {  # PrestoSports platform (4/6 datasets)
        "pbp": CapabilityLevel.UNAVAILABLE,  # PrestoSports doesn't publish PBP
        "shots": CapabilityLevel.UNAVAILABLE,  # No shot coordinates
    },
    "NAIA": {  # PrestoSports platform (4/6 datasets)
        "pbp": CapabilityLevel.UNAVAILABLE,  # PrestoSports doesn't publish PBP
        "shots": CapabilityLevel.UNAVAILABLE,  # No shot coordinates
    },
    "USPORTS": {  # PrestoSports platform - Canadian university (4/6 datasets)
        "pbp": CapabilityLevel.UNAVAILABLE,  # PrestoSports doesn't publish PBP
        "shots": CapabilityLevel.UNAVAILABLE,  # No shot coordinates
    },
    "CCAA": {  # PrestoSports platform - Canadian college (4/6 datasets)
        "pbp": CapabilityLevel.UNAVAILABLE,  # PrestoSports doesn't publish PBP
        "shots": CapabilityLevel.UNAVAILABLE,  # No shot coordinates
    },
    # ========== FIBA HTML SCRAPING CLUSTER (5/6 datasets each) ==========
    "LKL": {  # Lithuania Basketball League - FIBA HTML
        "shots": CapabilityLevel.UNAVAILABLE,  # FIBA HTML doesn't provide x,y coordinates
    },
    "BAL": {  # Basketball Africa League - FIBA HTML
        "shots": CapabilityLevel.UNAVAILABLE,  # FIBA HTML doesn't provide x,y coordinates
    },
    "BCL": {  # Basketball Champions League - FIBA HTML
        "shots": CapabilityLevel.UNAVAILABLE,  # FIBA HTML doesn't provide x,y coordinates
    },
    "ABA": {  # ABA Adriatic League - FIBA HTML
        "shots": CapabilityLevel.UNAVAILABLE,  # FIBA HTML doesn't provide x,y coordinates
    },
}

# Season-level capability overrides (for historical data limitations)
# Format: (league, season) -> {dataset -> CapabilityLevel}
# Updated 2025-11-19: LNB/ACB now have full PBP support via API/BAwiR
SEASON_CAPABILITY_OVERRIDES: dict[tuple[str, str], dict[str, CapabilityLevel]] = {
    # NBL shot coordinates only available from 2015-16+
    # (schedule data goes back to 1979, but detailed stats only from 2015-16)
    ("NBL", "2014-15"): {
        "player_game": CapabilityLevel.UNAVAILABLE,
        "team_game": CapabilityLevel.UNAVAILABLE,
        "pbp": CapabilityLevel.UNAVAILABLE,
        "shots": CapabilityLevel.UNAVAILABLE,
        "player_season": CapabilityLevel.UNAVAILABLE,
        "team_season": CapabilityLevel.UNAVAILABLE,
    },
    # Historical data limitations for other leagues will be documented as discovered
}


def check_capability(league: str, dataset: str, season: str | None = None) -> CapabilityLevel:
    """Check if a league supports a dataset (optionally for a specific season)

    Args:
        league: League identifier (e.g., "G-League", "CEBL")
        dataset: Dataset identifier (e.g., "schedule", "pbp")
        season: Optional season string for season-specific checks (e.g., "2015-16")

    Returns:
        CapabilityLevel indicating data availability

    Example:
        >>> check_capability("G-League", "pbp")
        CapabilityLevel.FULL
        >>> check_capability("CEBL", "pbp")
        CapabilityLevel.UNAVAILABLE
        >>> check_capability("LNB_PROA", "pbp", "2015-16")
        CapabilityLevel.UNAVAILABLE  # Historical limitation
        >>> check_capability("LNB_PROA", "pbp", "2020-21")
        CapabilityLevel.LIMITED  # Recent seasons have PBP
    """
    # Check season-specific overrides first (most specific)
    if season:
        season_key = (league, season)
        if season_key in SEASON_CAPABILITY_OVERRIDES:
            season_overrides = SEASON_CAPABILITY_OVERRIDES[season_key]
            if dataset in season_overrides:
                return season_overrides[dataset]

    # Check league-level overrides
    if league in CAPABILITY_OVERRIDES:
        overrides = CAPABILITY_OVERRIDES[league]
        if dataset in overrides:
            return overrides[dataset]

    # Default to FULL if league is registered for this dataset
    # (Will be validated against DatasetRegistry at runtime)
    return CapabilityLevel.FULL


def league_supports(league: str, endpoint: str, season: str | None = None) -> bool:
    """Check if a league supports an endpoint (convenience wrapper)

    Args:
        league: League identifier
        endpoint: Endpoint/dataset identifier
        season: Optional season string

    Returns:
        True if endpoint is FULL or LIMITED, False if UNAVAILABLE or NOT_IMPLEMENTED

    Example:
        >>> league_supports("LKL", "schedule")
        True
        >>> league_supports("LKL", "shots")
        False
        >>> league_supports("NBL", "shots", "2010-11")
        False  # Historical limitation
        >>> league_supports("NBL", "shots", "2020-21")
        True  # Recent seasons have shots
    """
    level = check_capability(league, endpoint, season)
    return level in (CapabilityLevel.FULL, CapabilityLevel.LIMITED)


def get_capability_message(league: str, dataset: str, level: CapabilityLevel) -> str:
    """Get user-friendly message explaining capability status

    Args:
        league: League identifier
        dataset: Dataset identifier
        level: Capability level

    Returns:
        Human-readable message with context and alternatives
    """
    if level == CapabilityLevel.FULL:
        return f"{league} {dataset} data is fully available"

    elif level == CapabilityLevel.LIMITED:
        return (
            f"{league} {dataset} data is available but with limitations. "
            f"Some fields may be missing or coverage may be incomplete."
        )

    elif level == CapabilityLevel.UNAVAILABLE:
        # Get alternative datasets
        alternatives = []
        for alt_dataset in ["schedule", "player_game", "team_game", "player_season", "team_season"]:
            if (
                alt_dataset != dataset
                and check_capability(league, alt_dataset) == CapabilityLevel.FULL
            ):
                alternatives.append(alt_dataset)

        alt_msg = (
            f" Try these datasets instead: {', '.join(alternatives[:3])}" if alternatives else ""
        )

        return (
            f"{league} does not provide {dataset} data. "
            f"The {league} data source does not publish this level of detail.{alt_msg}"
        )

    else:  # NOT_IMPLEMENTED
        return (
            f"{league} {dataset} support is not yet implemented. "
            f"This feature may be added in a future release."
        )


def get_supported_datasets(league: str) -> dict[str, CapabilityLevel]:
    """Get all supported datasets for a league with their capability levels

    Args:
        league: League identifier

    Returns:
        Dict mapping dataset -> capability level

    Example:
        >>> get_supported_datasets("CEBL")
        {
            'schedule': CapabilityLevel.FULL,
            'player_game': CapabilityLevel.FULL,
            'pbp': CapabilityLevel.UNAVAILABLE,
            ...
        }
    """
    from .registry import DatasetRegistry

    # Get datasets that list this league
    infos = DatasetRegistry.filter_by_league(league)

    result: dict[str, CapabilityLevel] = {}
    for info in infos:
        dataset_id = info.id
        result[dataset_id] = check_capability(league, dataset_id)

    return result


def validate_league_dataset(league: str, dataset: str) -> tuple[bool, str]:
    """Validate if a league/dataset combination is usable

    Args:
        league: League identifier
        dataset: Dataset identifier

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if dataset is FULL or LIMITED
        - error_message: User-friendly error if not valid

    Example:
        >>> valid, msg = validate_league_dataset("G-League", "pbp")
        >>> assert valid is True
        >>> valid, msg = validate_league_dataset("CEBL", "pbp")
        >>> assert valid is False
        >>> print(msg)
        'CEBL does not provide pbp data...'
    """
    from .registry import DatasetRegistry

    # First check if league is registered for this dataset
    matching_datasets = [info.id for info in DatasetRegistry.filter_by_league(league)]

    if dataset not in matching_datasets:
        return False, (
            f"League '{league}' is not registered for dataset '{dataset}'. "
            f"Available datasets for {league}: {', '.join(matching_datasets)}"
        )

    # Check capability level
    level = check_capability(league, dataset)

    if level in (CapabilityLevel.FULL, CapabilityLevel.LIMITED):
        return True, ""

    # UNAVAILABLE or NOT_IMPLEMENTED
    message = get_capability_message(league, dataset, level)
    return False, message


class DataUnavailableError(Exception):
    """Raised when a dataset is unavailable for a specific league

    This is different from NotImplementedError (feature doesn't exist)
    or ValueError (invalid parameters). It indicates the data source
    simply doesn't provide this level of detail.

    HTTP Status: 501 Not Implemented (service doesn't support this operation)
    """

    def __init__(self, league: str, dataset: str, capability_level: CapabilityLevel):
        self.league = league
        self.dataset = dataset
        self.capability_level = capability_level

        message = get_capability_message(league, dataset, capability_level)
        super().__init__(message)
