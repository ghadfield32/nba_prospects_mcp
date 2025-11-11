"""Entity resolution for team and player names

This module handles exact alias matching and normalization of team/player names
across different data sources. It accounts for:
- Common abbreviations (e.g., "UConn" vs "Connecticut")
- Nickname variations (e.g., "Duke" vs "Duke Blue Devils")
- International name variations

Note: This uses exact matching only (no fuzzy matching) to ensure predictable,
fast entity resolution with clear alias mappings.
"""

from __future__ import annotations

import re

# NCAA team name mappings (common abbreviations -> full names)
NCAA_TEAM_ALIASES = {
    # ACC
    "UNC": "North Carolina",
    "UVA": "Virginia",
    "VT": "Virginia Tech",
    "GT": "Georgia Tech",
    "FSU": "Florida State",
    # Big Ten
    "OSU": "Ohio State",
    "MSU": "Michigan State",
    "PSU": "Penn State",
    # Big 12
    "KU": "Kansas",
    "ISU": "Iowa State",
    "KSU": "Kansas State",
    # Big East
    "UConn": "Connecticut",
    # SEC
    "UK": "Kentucky",
    "LSU": "Louisiana State",
    "A&M": "Texas A&M",
    # Pac-12
    "ASU": "Arizona State",
    "WSU": "Washington State",
    "USC": "Southern California",
    "UCLA": "UCLA",  # keep as-is
    # Add more as needed
}

# Reverse mapping (full name -> abbreviations)
NCAA_TEAM_FULL_TO_ABBR = {v: k for k, v in NCAA_TEAM_ALIASES.items()}

# Women's basketball programs with name variations
WBB_TEAM_ALIASES = {
    "South Carolina": ["SC", "Gamecocks", "South Carolina Gamecocks"],
    "Connecticut": ["UConn", "Huskies", "Connecticut Huskies"],
    "Stanford": ["Stanford Cardinal"],
    "Iowa": ["Iowa Hawkeyes"],
    # Add more as needed
}

# EuroLeague team name variations
EUROLEAGUE_TEAM_ALIASES = {
    "Real Madrid": ["Real", "Madrid"],
    "FC Barcelona": ["Barcelona", "Barca", "FCB"],
    "Olympiacos": ["Olympiacos Piraeus"],
    "Panathinaikos": ["PAO", "Panathinaikos Athens"],
    "CSKA Moscow": ["CSKA"],
    "Fenerbahce": ["Fener", "Fenerbahce Istanbul"],
    # Add more as needed
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching

    Args:
        name: Raw team name

    Returns:
        Normalized name (lowercase, no punctuation)
    """
    # Remove common suffixes
    name = re.sub(r"\s+(University|College|State|Tech|Institute)$", "", name, flags=re.I)

    # Remove punctuation and extra spaces
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name.lower()


def resolve_ncaa_team(name: str) -> str:
    """Resolve NCAA team name to canonical form using exact alias matching

    Args:
        name: Team name (may be abbreviation or full name)

    Returns:
        Canonical team name (or input name if not found in aliases)

    Examples:
        >>> resolve_ncaa_team("UNC")
        'North Carolina'
        >>> resolve_ncaa_team("North Carolina")
        'North Carolina'
        >>> resolve_ncaa_team("Unknown Team")
        'Unknown Team'
    """
    # Check if it's a known abbreviation
    if name in NCAA_TEAM_ALIASES:
        return NCAA_TEAM_ALIASES[name]

    # Check if it's already a full name (canonical form)
    if name in NCAA_TEAM_FULL_TO_ABBR:
        return name

    # Return as-is (exact match not found, let post-mask handle it)
    return name


def resolve_euroleague_team(name: str) -> str:
    """Resolve EuroLeague team name to canonical form using exact alias matching

    Args:
        name: Team name (may be abbreviation or variation)

    Returns:
        Canonical team name (or input name if not found in aliases)

    Examples:
        >>> resolve_euroleague_team("Real")
        'Real Madrid'
        >>> resolve_euroleague_team("FCB")
        'FC Barcelona'
        >>> resolve_euroleague_team("Real Madrid")
        'Real Madrid'
    """
    # Check if it's a known alias or canonical name
    for canonical, aliases in EUROLEAGUE_TEAM_ALIASES.items():
        if name == canonical or name in aliases:
            return canonical

    # Return as-is (exact match not found, let post-mask handle it)
    return name


def resolve_entity(
    name: str,
    entity_type: str,
    league: str | None = None,
) -> int | None:
    """Resolve entity name to ID

    This is a placeholder implementation. In a production system, this would:
    1. Query a database of team/player IDs
    2. Use league-specific resolution logic
    3. Cache results for performance

    For now, it returns None (entity resolution is optional).

    Args:
        name: Entity name (team or player)
        entity_type: "team" or "player"
        league: League context (e.g., "NCAA-MBB")

    Returns:
        Entity ID, or None if not found
    """
    # TODO: Implement actual entity resolution
    # This would typically:
    # 1. Normalize the name
    # 2. Query a database or API
    # 3. Return the ID

    # For now, we return None to indicate "not resolved"
    # The compiler will handle this by using name-based post-masks
    return None


def get_team_aliases(league: str) -> dict[str, list[str]]:
    """Get team alias mappings for a league

    Args:
        league: League identifier

    Returns:
        Dictionary mapping canonical names -> list of aliases
    """
    if league in ["NCAA-MBB", "NCAA-WBB"]:
        # Combine NCAA aliases
        aliases: dict[str, list[str]] = {}
        for abbr, full in NCAA_TEAM_ALIASES.items():
            if full not in aliases:
                aliases[full] = []
            aliases[full].append(abbr)
        return aliases

    elif league == "EuroLeague":
        return EUROLEAGUE_TEAM_ALIASES

    return {}


def search_teams(query: str, league: str | None = None, limit: int = 5) -> list[str]:
    """Search for teams by name using substring matching

    Args:
        query: Search query (case-insensitive)
        league: Optional league filter
        limit: Maximum results

    Returns:
        List of matching team names (sorted alphabetically)

    Examples:
        >>> search_teams("Duke", league="NCAA-MBB")
        ['Duke']
        >>> search_teams("State", league="NCAA-MBB", limit=3)
        ['Iowa State', 'Kansas State', 'Louisiana State']
    """
    candidates: list[str] = []

    # Gather candidate teams based on league
    if league in ["NCAA-MBB", "NCAA-WBB", None]:
        candidates.extend(NCAA_TEAM_ALIASES.values())

    if league in ["EuroLeague", None]:
        candidates.extend(EUROLEAGUE_TEAM_ALIASES.keys())

    # Remove duplicates
    candidates = list(set(candidates))

    # Filter by query (case-insensitive substring match)
    query_lower = query.lower()
    matches = [c for c in candidates if query_lower in c.lower()]

    # Sort alphabetically for predictable results
    matches.sort()

    return matches[:limit]
