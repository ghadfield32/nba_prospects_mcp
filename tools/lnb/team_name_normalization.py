#!/usr/bin/env python3
"""Team name normalization for schedule reconstruction

Provides robust, transparent team name matching across different public sources
(LNB.fr, Flashscore, Eurobasket, etc.) and Atrium API data.

Strategy:
- Normalize to ASCII, lowercase, remove punctuation
- Remove common stop tokens (BC, Basket, Club, etc.)
- Support manual overrides for edge cases
- Preserve transparency (show normalized vs original)
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Common tokens that don't help distinguish teams
STOP_TOKENS = {
    "bc",
    "basket",
    "club",
    "st",
    "saint",
    "as",
    "us",
    "union",
    "sportive",
    "olympique",
    "aso",
    "jl",
    "bourg",  # Too generic when alone
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching

    Converts team names to a canonical form that's robust to:
    - Accent variations (é → e)
    - Punctuation differences (- vs space)
    - Case differences (ASVEL vs Asvel)
    - Common prefix/suffix variations (BC/Basket/Club)

    Args:
        name: Raw team name (e.g., "JL Bourg-en-Bresse", "ASVEL Basket")

    Returns:
        Normalized name (e.g., "jl bourg en bresse", "asvel")

    Examples:
        >>> normalize_team_name("JL Bourg-en-Bresse")
        'jl bourg en bresse'
        >>> normalize_team_name("ASVEL Basket")
        'asvel'
        >>> normalize_team_name("Élan Béarnais Pau-Orthez")
        'elan bearnais pau orthez'
    """
    if not isinstance(name, str):
        return ""

    # Convert to ASCII (remove accents)
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    s = s.lower()

    # Replace all punctuation with spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)

    # Split into tokens and remove stop words
    tokens = [t for t in s.split() if t and t not in STOP_TOKENS]

    return " ".join(tokens)


def load_team_name_overrides(override_file: Path | str | None = None) -> dict[str, str]:
    """Load manual team name overrides

    For cases where automatic normalization produces false matches or misses,
    provide manual mappings from normalized form to canonical form.

    Args:
        override_file: Path to JSON file with overrides
                      Default: tools/lnb/team_name_overrides.json

    Returns:
        Dict mapping normalized name → canonical override

    Example override file:
        {
          "paris": "paris basketball",
          "nanterre": "nanterre 92",
          "metropolitans": "metropolitans 92"
        }
    """
    if override_file is None:
        override_file = Path(__file__).parent / "team_name_overrides.json"
    else:
        override_file = Path(override_file)

    if not override_file.exists():
        return {}

    try:
        with open(override_file) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] Failed to load team name overrides from {override_file}: {e}")
        return {}


def apply_team_name_override(normalized: str, overrides: dict[str, str]) -> str:
    """Apply manual override if one exists

    Args:
        normalized: Normalized team name
        overrides: Override dictionary from load_team_name_overrides()

    Returns:
        Override value if exists, otherwise original normalized name
    """
    return overrides.get(normalized, normalized)


def normalize_with_overrides(name: str, overrides: dict[str, str] | None = None) -> str:
    """Normalize team name and apply overrides

    Convenience function combining normalization + override lookup.

    Args:
        name: Raw team name
        overrides: Optional override dict (loaded if None)

    Returns:
        Canonical normalized team name

    Example:
        >>> overrides = {"paris": "paris basketball"}
        >>> normalize_with_overrides("Paris BC", overrides)
        'paris basketball'
    """
    if overrides is None:
        overrides = load_team_name_overrides()

    normalized = normalize_team_name(name)
    return apply_team_name_override(normalized, overrides)


# ==============================================================================
# VALIDATION & DEBUGGING
# ==============================================================================


def validate_normalization_quality(
    names: list[str], overrides: dict[str, str] | None = None
) -> dict:
    """Analyze normalization quality for a list of team names

    Useful for debugging when schedule reconstruction has poor match rates.
    Shows which names normalize to the same value (potential collisions).

    Args:
        names: List of raw team names to analyze
        overrides: Optional override dict

    Returns:
        Dict with stats:
            - total: Number of input names
            - unique_normalized: Number of unique normalized forms
            - collisions: List of (normalized_form, [original_names]) for duplicates

    Example:
        >>> names = ["Paris Basketball", "Paris BC", "ASVEL", "ASVEL Basket"]
        >>> stats = validate_normalization_quality(names)
        >>> print(stats['collisions'])
        [('paris', ['Paris Basketball', 'Paris BC']),
         ('asvel', ['ASVEL', 'ASVEL Basket'])]
    """
    if overrides is None:
        overrides = load_team_name_overrides()

    normalized_map = {}
    for name in names:
        norm = normalize_with_overrides(name, overrides)
        if norm not in normalized_map:
            normalized_map[norm] = []
        normalized_map[norm].append(name)

    collisions = [
        (norm, originals) for norm, originals in normalized_map.items() if len(originals) > 1
    ]

    return {
        "total": len(names),
        "unique_normalized": len(normalized_map),
        "collisions": collisions,
    }
