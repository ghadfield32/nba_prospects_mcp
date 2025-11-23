"""LNB League Name Normalization

Ensures consistent canonical league identifiers across all seasons, regardless
of official branding changes (e.g., Pro B → ÉLITE 2 rebrand in 2025-26).

PRINCIPLE: One canonical key, many display names
- Prevents splitting historical data into fake separate leagues
- Enables seamless filtering across branding transitions
- Maintains backward compatibility with old metadata

Canonical League Keys:
- betclic_elite: Top division (historically "LNB", "PRO A", "JEEP ÉLITE")
- elite_2: Second division (historically "PRO B", "Pro B", now "ÉLITE 2")
- espoirs_elite: U21 top division
- espoirs_prob: U21 second division
"""

# ==============================================================================
# CANONICAL LEAGUE KEYS
# ==============================================================================

SECOND_DIVISION_ALIASES = {
    # Historical Pro B variations
    "prob",
    "pro b",
    "pro-b",
    "pro_b",
    "lnb prob",
    "lnb pro b",
    "probetclic",

    # Modern ÉLITE 2 variations
    "elite 2",
    "élite 2",
    "elite2",
    "elite_2",
    "lnb elite 2",
    "betclic elite 2",
}

TOP_DIVISION_ALIASES = {
    # Historical variations
    "pro a",
    "pro-a",
    "pro_a",
    "lnb",
    "lnb pro a",
    "jeep elite",
    "jeep élite",

    # Modern Betclic ÉLITE variations
    "betclic elite",
    "betclic élite",
    "betclicélite",
    "betclic_elite",
    "élite",
    "elite",
}

ESPOIRS_ELITE_ALIASES = {
    "espoirs elite",
    "espoirs élite",
    "espoirs_elite",
    "u21 elite",
    "u21 élite",
}

ESPOIRS_PROB_ALIASES = {
    "espoirs prob",
    "espoirs pro b",
    "espoirs_prob",
    "u21 prob",
    "u21 pro b",
}


def normalize_lnb_league(name: str | None) -> str | None:
    """Normalize LNB league name to canonical key

    Maps all historical and modern variations of league names to a single
    canonical identifier. This prevents data fragmentation when official
    branding changes (e.g., Pro B → ÉLITE 2 in 2025-26).

    Args:
        name: Raw league/competition name from API (e.g., "PROB", "ÉLITE 2")

    Returns:
        Canonical league key (e.g., "elite_2") or None if input is None

    Examples:
        >>> normalize_lnb_league("PROB")
        'elite_2'
        >>> normalize_lnb_league("ÉLITE 2")
        'elite_2'
        >>> normalize_lnb_league("Betclic ÉLITE")
        'betclic_elite'
        >>> normalize_lnb_league("Pro A")
        'betclic_elite'
    """
    if not name:
        return name

    # Normalize for comparison: lowercase, strip whitespace
    key = name.strip().lower()

    # Map to canonical keys
    if key in SECOND_DIVISION_ALIASES:
        return "elite_2"
    elif key in TOP_DIVISION_ALIASES:
        return "betclic_elite"
    elif key in ESPOIRS_ELITE_ALIASES:
        return "espoirs_elite"
    elif key in ESPOIRS_PROB_ALIASES:
        return "espoirs_prob"

    # Unknown league - return normalized snake_case version
    return key.replace(" ", "_").replace("-", "_")


# ==============================================================================
# CLI ARGUMENT CANONICALIZATION
# ==============================================================================

LEAGUE_CANONICAL_MAP = {
    # Second division (all map to elite_2)
    "prob": "elite_2",
    "pro_b": "elite_2",
    "pro-b": "elite_2",
    "elite2": "elite_2",
    "élite2": "elite_2",
    "elite_2": "elite_2",

    # Top division (all map to betclic_elite)
    "proa": "betclic_elite",
    "pro_a": "betclic_elite",
    "pro-a": "betclic_elite",
    "lnb": "betclic_elite",
    "betclic": "betclic_elite",
    "betclic_elite": "betclic_elite",

    # U21 leagues (already canonical)
    "espoirs_elite": "espoirs_elite",
    "espoirs_prob": "espoirs_prob",
}


def canonicalize_requested_leagues(leagues: list[str]) -> list[str]:
    """Canonicalize user-requested league filters

    Normalizes CLI arguments like `--leagues prob` to canonical keys.
    Allows users to request historical names while maintaining internal consistency.

    Args:
        leagues: List of league strings from CLI (e.g., ["prob", "betclic"])

    Returns:
        Deduplicated list of canonical league keys

    Examples:
        >>> canonicalize_requested_leagues(["prob", "pro_b"])
        ['elite_2']
        >>> canonicalize_requested_leagues(["prob", "betclic_elite"])
        ['betclic_elite', 'elite_2']
    """
    canonical = []
    for league in leagues:
        key = league.strip().lower()
        canonical.append(LEAGUE_CANONICAL_MAP.get(key, key))

    # Deduplicate and sort for consistency
    return sorted(set(canonical))


def canonical_mapping_key(season: str, league: str | None) -> str:
    """Generate canonical mapping key for fixture_uuids_by_season.json

    Ensures all mapping keys use canonical league identifiers, preventing
    fragmentation when branding changes.

    Args:
        season: Season string (e.g., "2023-2024")
        league: Raw or canonical league name

    Returns:
        Canonical mapping key (e.g., "2023-2024_elite_2")

    Examples:
        >>> canonical_mapping_key("2023-2024", "PROB")
        '2023-2024_elite_2'
        >>> canonical_mapping_key("2023-2024", "elite_2")
        '2023-2024_elite_2'
        >>> canonical_mapping_key("2023-2024", None)
        '2023-2024'
    """
    if not league:
        return season

    canonical_league = normalize_lnb_league(league)
    return f"{season}_{canonical_league}"


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate_league_normalization(df):
    """Validate that no non-canonical league names appear in final data

    Safety check to ensure normalization is working correctly.
    Should be called after index building.

    Args:
        df: DataFrame with 'league' column

    Raises:
        AssertionError: If non-canonical league names are found
    """
    if "league" not in df.columns:
        return

    # Check for historical names that should have been normalized
    historical_names = ["prob", "pro b", "pro a", "lnb"]
    for name in historical_names:
        matches = df["league"].str.lower() == name
        if matches.any():
            count = matches.sum()
            raise AssertionError(
                f"Found {count} games with non-canonical league '{name}'. "
                f"League normalization failed. All second division games "
                f"should be 'elite_2', not '{name}'."
            )
