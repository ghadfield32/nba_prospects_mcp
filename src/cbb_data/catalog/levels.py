"""League Level Categorization

Categorizes leagues by competition level to enforce scope (pre-NBA/WNBA prospects only).

**Competition Levels**:
- **college**: NCAA, NJCAA, NAIA, U SPORTS, CCAA (primary scope)
- **prepro**: OTE, EuroLeague, EuroCup, G-League, CEBL (pre-NBA development/international prospects)
- **pro**: WNBA only (women's professional league) - excluded by default

**Default Behavior**:
- APIs default to `pre_only=True` (college + prepro only, includes international pre-NBA leagues)
- WNBA excluded by default unless explicitly requested with `pre_only=False`

**Purpose**:
- Enforces project scope (pre-NBA/WNBA prospects)
- Includes international leagues where NBA prospects play (EuroLeague, EuroCup)
- Includes official development leagues (G-League, CEBL)
- Clear error messages when accessing out-of-scope data

**Usage**:
```python
from cbb_data.catalog.levels import get_league_level, filter_leagues_by_level

# Check league level
level = get_league_level("NCAA-MBB")  # Returns "college"

# Filter to pre-NBA only
leagues = ["NCAA-MBB", "EuroLeague", "OTE"]
pre_leagues = filter_leagues_by_level(leagues, pre_only=True)
# Returns: ["NCAA-MBB", "OTE"]
```
"""

from __future__ import annotations

from typing import Literal

# Type alias for level values
LevelType = Literal["college", "prepro", "pro"]

# League level mappings
LEAGUE_LEVELS: dict[str, LevelType] = {
    # College Basketball (Primary Scope)
    "NCAA-MBB": "college",
    "NCAA-WBB": "college",
    "NJCAA": "college",
    "NAIA": "college",
    "U-SPORTS": "college",  # Canadian university basketball
    "CCAA": "college",  # Canadian college basketball
    # Pre-Professional / Development (Pre-NBA Prospects)
    "OTE": "prepro",  # Overtime Elite (pre-NBA development)
    "EuroLeague": "prepro",  # International league with NBA prospects
    "EuroCup": "prepro",  # EuroLeague's second-tier competition with NBA prospects
    "G-League": "prepro",  # Official NBA development league
    "CEBL": "prepro",  # Canadian Elite Basketball League with NBA prospects
    # European & International Pre-Professional Leagues
    "ABA": "prepro",  # ABA League (Adriatic) - Balkan region pre-NBA prospects
    "ACB": "prepro",  # Liga Endesa (Spain) - Spanish league (Gasol brothers, Ricky Rubio pipeline)
    "BAL": "prepro",  # Basketball Africa League - NBA-operated African league
    "BCL": "prepro",  # Basketball Champions League - FIBA European competition
    "LKL": "prepro",  # LKL Lithuania - Lithuanian league (Sabonis family, Valančiūnas pipeline)
    "LNB_PROA": "prepro",  # LNB Pro A (France) - French top-tier league (Wembanyama, Gobert pipeline)
    "LNB_ELITE2": "prepro",  # LNB Pro B (France) - French second-tier league
    "LNB_ESPOIRS_ELITE": "prepro",  # LNB Espoirs Elite (France) - U21 top-tier youth
    "LNB_ESPOIRS_PROB": "prepro",  # LNB Espoirs Pro B (France) - U21 second-tier youth
    "NBL": "prepro",  # NBL Australia - Australian league (Josh Giddey, Dyson Daniels pipeline)
    "NZ-NBL": "prepro",  # New Zealand NBL - Sal's NBL (developmental league, NZ prospects)
    # Professional Leagues (EXCLUDED by default)
    "WNBA": "pro",  # Women's professional league (not pre-NBA)
}


def get_league_level(league: str) -> LevelType:
    """Get competition level for a league

    Args:
        league: League identifier (e.g., "NCAA-MBB", "EuroLeague")

    Returns:
        Level type ("college", "prepro", or "pro")

    Raises:
        ValueError: If league not recognized

    Example:
        >>> get_league_level("NCAA-MBB")
        'college'
        >>> get_league_level("WNBA")
        'pro'
    """
    if league not in LEAGUE_LEVELS:
        raise ValueError(
            f"Unknown league: {league}. " f"Registered leagues: {list(LEAGUE_LEVELS.keys())}"
        )
    return LEAGUE_LEVELS[league]


def is_pre_nba_league(league: str) -> bool:
    """Check if league is pre-NBA/WNBA (college or prepro)

    Args:
        league: League identifier

    Returns:
        True if college or prepro, False if pro

    Example:
        >>> is_pre_nba_league("NCAA-MBB")
        True
        >>> is_pre_nba_league("WNBA")
        False
    """
    try:
        level = get_league_level(league)
        return level in ("college", "prepro")
    except ValueError:
        return False


def filter_leagues_by_level(leagues: list[str], pre_only: bool = True) -> list[str]:
    """Filter leagues by competition level

    Args:
        leagues: List of league identifiers
        pre_only: If True, exclude professional leagues (default: True)

    Returns:
        Filtered list of leagues

    Example:
        >>> leagues = ["NCAA-MBB", "EuroLeague", "OTE", "WNBA"]
        >>> filter_leagues_by_level(leagues, pre_only=True)
        ['NCAA-MBB', 'OTE']
        >>> filter_leagues_by_level(leagues, pre_only=False)
        ['NCAA-MBB', 'EuroLeague', 'OTE', 'WNBA']
    """
    if not pre_only:
        return leagues

    # Filter to college + prepro only
    return [league for league in leagues if is_pre_nba_league(league)]


def get_leagues_by_level(level: LevelType | None = None) -> list[str]:
    """Get all leagues at a specific level

    Args:
        level: Competition level to filter by (None = all leagues)

    Returns:
        List of league identifiers

    Example:
        >>> get_leagues_by_level("college")
        ['NCAA-MBB', 'NCAA-WBB', 'NJCAA', 'NAIA', 'U-SPORTS', 'CCAA']
        >>> get_leagues_by_level("pro")
        ['EuroLeague', 'EuroCup', 'G-League', 'WNBA', 'CEBL']
    """
    if level is None:
        return list(LEAGUE_LEVELS.keys())

    return [league for league, lvl in LEAGUE_LEVELS.items() if lvl == level]


def get_excluded_leagues_message(excluded: list[str]) -> str:
    """Get user-friendly message explaining why leagues were excluded

    Args:
        excluded: List of excluded league identifiers

    Returns:
        Human-readable explanation

    Example:
        >>> msg = get_excluded_leagues_message(["EuroLeague", "WNBA"])
        >>> print(msg)
        Professional leagues excluded (EuroLeague, WNBA).
        This API focuses on pre-NBA/WNBA prospects (college, prepro).
        To include pro leagues, set pre_only=False in your query.
    """
    if not excluded:
        return ""

    excluded_str = ", ".join(excluded)

    return (
        f"Professional leagues excluded ({excluded_str}). "
        f"This API focuses on pre-NBA/WNBA prospects (college, prepro). "
        f"To include pro leagues, set pre_only=False in your query."
    )
