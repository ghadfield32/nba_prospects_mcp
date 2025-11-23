"""LNB League Configuration - Centralized Metadata for All Leagues

This module serves as the single source of truth for LNB league and season metadata.
It contains competition IDs, season IDs, and display names for all 4 LNB leagues:
1. Betclic ELITE (formerly Pro A) - Top-tier professional (16 teams)
2. ELITE 2 (formerly Pro B) - Second-tier professional (20 teams)
3. Espoirs ELITE - U21 top-tier youth league
4. Espoirs PROB - U21 second-tier youth league

Metadata source: lnb_leagues_discovered.json (generated 2025-11-18)
Discovery tool: tools/lnb/discover_all_lnb_leagues.py

Usage:
    from cbb_data.fetchers.lnb_league_config import (
        get_season_metadata,
        get_competition_name,
        BETCLIC_ELITE,
    )

    # Get metadata for specific league/season
    meta = get_season_metadata("betclic_elite", "2024-2025")
    comp_id = meta["competition_id"]
    season_id = meta["season_id"]

    # Get display name from competition ID
    name = get_competition_name(comp_id)  # Returns "Betclic ELITE"
"""

from __future__ import annotations

from typing import TypedDict


class SeasonMetadata(TypedDict):
    """Type for season metadata entries."""

    competition_id: str
    season_id: str
    competition_name: str
    source: str


class LeagueEntry(TypedDict):
    """Type for league registry entries."""

    display_name: str
    description: str
    seasons: dict[str, SeasonMetadata]


# ==============================================================================
# LEAGUE IDENTIFIERS (for CLI/API parameters)
# ==============================================================================

BETCLIC_ELITE = "betclic_elite"
ELITE_2 = "elite_2"
ESPOIRS_ELITE = "espoirs_elite"
ESPOIRS_PROB = "espoirs_prob"

ALL_LEAGUES = [BETCLIC_ELITE, ELITE_2, ESPOIRS_ELITE, ESPOIRS_PROB]

# ==============================================================================
# SEASON METADATA BY LEAGUE
# ==============================================================================

# Betclic ELITE (formerly Pro A) - Top-tier professional
BETCLIC_ELITE_SEASONS: dict[str, SeasonMetadata] = {
    "2022-2023": {
        "competition_id": "2cd1ec93-19af-11ee-afb2-8125e5386866",
        "season_id": "418ecaae-19af-11ee-a563-47c909cdfb65",
        "competition_name": "Betclic ÉLITE",
        "source": "Atrium API discovery 2025-11-18",
    },
    "2023-2024": {
        "competition_id": "a2262b45-2fab-11ef-8eb7-99149ebb5652",
        "season_id": "cab2f926-2fab-11ef-8b99-e553c4d56b24",
        "competition_name": "Betclic ÉLITE",
        "source": "Atrium API discovery 2025-11-18",
    },
    "2024-2025": {
        "competition_id": "3f4064bb-51ad-11f0-aaaf-2923c944b404",
        "season_id": "df310a05-51ad-11f0-bd89-c735508e1e09",
        "competition_name": "Betclic ÉLITE 2025",
        "source": "Atrium API discovery 2025-11-18",
    },
}

# ELITE 2 (formerly Pro B) - Second-tier professional
ELITE_2_SEASONS: dict[str, SeasonMetadata] = {
    "2021-2022": {
        "competition_id": "12cc5982-f549-11eb-8476-9ee7b443c3e3",
        "season_id": "53baf994-f549-11eb-b854-ee44c37cacf0",
        "competition_name": "PROB",  # Old name pre-rebrand
        "source": "Real seed bulk discovery 2025-11-21",
    },
    "2022-2023": {
        "competition_id": "50dc7dbd-0bf9-11ed-84a2-771b9cfe4d9c",
        "season_id": "756d1ebc-0bf9-11ed-bcdb-176ad0fc17fa",
        "competition_name": "PROB",  # Old name pre-rebrand
        "source": "Real seed bulk discovery 2025-11-21",
    },
    "2023-2024": {
        "competition_id": "213e021f-19b5-11ee-9190-29c4f278bc32",
        "season_id": "7561dbee-19b5-11ee-affc-23e4d3a88307",
        "competition_name": "PROB",  # Old name pre-rebrand
        "source": "Atrium API discovery 2025-11-18",
    },
    "2024-2025": {
        "competition_id": "4c27df72-51ae-11f0-ab8c-73390bbc2fc6",
        "season_id": "5e31a852-51ae-11f0-b5bf-5988dba0fcf9",
        "competition_name": "ÉLITE 2",  # New name post-rebrand
        "source": "Atrium API discovery 2025-11-18",
    },
}

# Espoirs ELITE - U21 top-tier youth league
ESPOIRS_ELITE_SEASONS: dict[str, SeasonMetadata] = {
    "2023-2024": {
        "competition_id": "ac2bc8df-2fb4-11ef-9e38-9f35926cbbae",
        "season_id": "c68a19df-2fb4-11ef-bf65-c13f469726eb",
        "competition_name": "Espoirs ELITE",
        "source": "Atrium API discovery 2025-11-18",
    },
    "2024-2025": {
        "competition_id": "a355be55-51ae-11f0-baaa-958a1408092e",
        "season_id": "c8514e7e-51ae-11f0-9446-a5c0bb403783",
        "competition_name": "Espoirs ÉLITE",
        "source": "Atrium API discovery 2025-11-18",
    },
}

# Espoirs PROB - U21 second-tier youth league
ESPOIRS_PROB_SEASONS: dict[str, SeasonMetadata] = {
    "2023-2024": {
        "competition_id": "59512848-2fb5-11ef-9343-f7ede79b7e49",
        "season_id": "702b8520-2fb5-11ef-8f58-ed6f7e8cdcbb",
        "competition_name": "Espoirs PROB",
        "source": "Atrium API discovery 2025-11-18",
    },
}

# ==============================================================================
# COMPETITION NAME MAPPING (for dynamic display names)
# ==============================================================================

# Maps competition_id → user-friendly display name
# Used to populate game index "competition" field dynamically
COMPETITION_NAMES = {
    # Betclic ELITE (3 seasons, competition ID changed each season)
    "2cd1ec93-19af-11ee-afb2-8125e5386866": "Betclic ELITE",  # 2022-2023
    "a2262b45-2fab-11ef-8eb7-99149ebb5652": "Betclic ELITE",  # 2023-2024
    "3f4064bb-51ad-11f0-aaaf-2923c944b404": "Betclic ELITE",  # 2024-2025
    # ELITE 2 (formerly PROB)
    "12cc5982-f549-11eb-8476-9ee7b443c3e3": "ELITE 2 (PROB)",  # 2021-2022
    "50dc7dbd-0bf9-11ed-84a2-771b9cfe4d9c": "ELITE 2 (PROB)",  # 2022-2023
    "213e021f-19b5-11ee-9190-29c4f278bc32": "ELITE 2 (PROB)",  # 2023-2024
    "0847055c-2fb3-11ef-9b30-3333ffdb8385": "ELITE 2 (PROB)",  # 2023-2024 (alt)
    "4c27df72-51ae-11f0-ab8c-73390bbc2fc6": "ELITE 2",  # 2024-2025
    # Espoirs ELITE
    "ac2bc8df-2fb4-11ef-9e38-9f35926cbbae": "Espoirs ELITE",  # 2023-2024
    "a355be55-51ae-11f0-baaa-958a1408092e": "Espoirs ELITE",  # 2024-2025
    # Espoirs PROB
    "59512848-2fb5-11ef-9343-f7ede79b7e49": "Espoirs PROB",  # 2023-2024
}

# ==============================================================================
# LEAGUE METADATA REGISTRY (combines all leagues)
# ==============================================================================

LEAGUE_METADATA_REGISTRY: dict[str, LeagueEntry] = {
    BETCLIC_ELITE: {
        "display_name": "Betclic ELITE",
        "description": "Top-tier professional (formerly Pro A), 16 teams",
        "seasons": BETCLIC_ELITE_SEASONS,
    },
    ELITE_2: {
        "display_name": "ELITE 2",
        "description": "Second-tier professional (formerly Pro B), 20 teams",
        "seasons": ELITE_2_SEASONS,
    },
    ESPOIRS_ELITE: {
        "display_name": "Espoirs ELITE",
        "description": "U21 top-tier youth development league",
        "seasons": ESPOIRS_ELITE_SEASONS,
    },
    ESPOIRS_PROB: {
        "display_name": "Espoirs PROB",
        "description": "U21 second-tier youth development league",
        "seasons": ESPOIRS_PROB_SEASONS,
    },
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def get_season_metadata(league: str, season: str) -> SeasonMetadata | None:
    """Get competition/season IDs for a specific league and season

    Args:
        league: League identifier (e.g., "betclic_elite", "elite_2")
        season: Season string (e.g., "2024-2025")

    Returns:
        Dict with competition_id, season_id, competition_name, source
        Returns None if league/season combo not found

    Example:
        >>> meta = get_season_metadata("betclic_elite", "2024-2025")
        >>> meta["competition_id"]
        '3f4064bb-51ad-11f0-aaaf-2923c944b404'
    """
    if league not in LEAGUE_METADATA_REGISTRY:
        return None

    seasons_dict = LEAGUE_METADATA_REGISTRY[league]["seasons"]
    return seasons_dict.get(season)


def get_competition_name(competition_id: str) -> str:
    """Get display name for a competition ID

    Args:
        competition_id: Competition UUID

    Returns:
        User-friendly competition name (e.g., "Betclic ELITE", "ELITE 2")
        Returns "Unknown Competition" if ID not found

    Example:
        >>> get_competition_name("3f4064bb-51ad-11f0-aaaf-2923c944b404")
        'Betclic ELITE'
    """
    return COMPETITION_NAMES.get(competition_id, "Unknown Competition")


def get_all_seasons_for_league(league: str) -> list[str]:
    """Get list of available seasons for a league

    Args:
        league: League identifier

    Returns:
        List of season strings (e.g., ["2022-2023", "2023-2024", "2024-2025"])
        Returns empty list if league not found

    Example:
        >>> get_all_seasons_for_league("betclic_elite")
        ['2022-2023', '2023-2024', '2024-2025']
    """
    if league not in LEAGUE_METADATA_REGISTRY:
        return []

    seasons_dict = LEAGUE_METADATA_REGISTRY[league]["seasons"]
    return sorted(seasons_dict.keys())


def get_all_competition_ids() -> list[str]:
    """Get list of all known competition IDs across all leagues

    Returns:
        List of competition ID UUIDs

    Example:
        >>> ids = get_all_competition_ids()
        >>> len(ids)
        9
    """
    return list(COMPETITION_NAMES.keys())


# ==============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ==============================================================================

# For backward compatibility with existing code that expects SEASON_METADATA dict
# Default to Betclic ELITE (most commonly used league)
SEASON_METADATA = BETCLIC_ELITE_SEASONS

# ==============================================================================
# MODULE INFO
# ==============================================================================

__all__ = [
    # League identifiers
    "BETCLIC_ELITE",
    "ELITE_2",
    "ESPOIRS_ELITE",
    "ESPOIRS_PROB",
    "ALL_LEAGUES",
    # Season metadata dicts
    "BETCLIC_ELITE_SEASONS",
    "ELITE_2_SEASONS",
    "ESPOIRS_ELITE_SEASONS",
    "ESPOIRS_PROB_SEASONS",
    "SEASON_METADATA",  # Backward compatibility (= BETCLIC_ELITE_SEASONS)
    # Competition mapping
    "COMPETITION_NAMES",
    # Registry
    "LEAGUE_METADATA_REGISTRY",
    # Helper functions
    "get_season_metadata",
    "get_competition_name",
    "get_all_seasons_for_league",
    "get_all_competition_ids",
]
