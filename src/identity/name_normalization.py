#!/usr/bin/env python3
"""League-aware player name normalization.

This module provides robust name parsing that handles different league formats:
- EuroLeague/ACB: "DONCIC, LUKA" (LAST, FIRST comma-separated)
- NCAA/G-League: "Z. Williamson" (initial + period + last)
- NBL/CEBL/OTE: "First Last" (standard format)

Key principles:
1. Never fill missing values - parse what exists
2. Store both raw and canonical forms
3. Create multiple name keys for robust matching
4. Handle accents without losing information
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Regex patterns
_WS_RE = re.compile(r"\s+")
_SUFFIX_RE = re.compile(r"\b(jr\.|sr\.|ii|iii|iv|v)\b", re.IGNORECASE)


def strip_accents(s: str) -> str:
    """Remove accents using Unicode normalization (pure stdlib).

    Examples:
        "Luka Dončić" → "Luka Doncic"
        "José" → "Jose"
        "Tazé" → "Taze"
    """
    if not s:
        return ""
    # NFKD = Compatibility Decomposition
    normalized = unicodedata.normalize("NFKD", s)
    # Filter out combining characters (accents)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def clean_spaces(s: str) -> str:
    """Collapse multiple spaces to single space and strip."""
    return _WS_RE.sub(" ", s).strip()


def titleish(s: str) -> str:
    """Smart titlecase that handles apostrophes and hyphens.

    Examples:
        "o'neal" → "O'Neal"
        "caldwell-pope" → "Caldwell-Pope"
        "van gundy" → "Van Gundy"
    """
    if not s:
        return ""

    # Split on apostrophes and hyphens but keep them
    parts = re.split(r"([-'])", s.lower())
    out = []
    for p in parts:
        if p in ["-", "'"]:
            out.append(p)
        elif p:
            # Capitalize first letter
            out.append(p[0].upper() + p[1:] if len(p) > 0 else "")
    return "".join(out)


@dataclass(frozen=True)
class NormalizedName:
    """Result of name normalization with all parsed components."""

    raw: str  # Original unchanged name
    first: str | None  # "Zion" (None if only initial available)
    last: str | None  # "Williamson"
    first_initial: str | None  # "Z"
    canonical_full: str  # "Zion Williamson" or best-effort
    name_key_canonical: str | None  # "zion_williamson"
    name_key_initial: str | None  # "z_williamson"


def _name_key_from_first_last(first: str | None, last: str | None) -> str:
    """Create name key from first and last names.

    Examples:
        ("Zion", "Williamson") → "zion_williamson"
        ("Luka", "Dončić") → "luka_doncic"
        (None, "Williamson") → "williamson"
    """
    f = (first or "").strip().lower()
    ln = (last or "").strip().lower()

    # Strip accents
    f = strip_accents(f)
    ln = strip_accents(ln)

    # Replace non-alphanumeric with underscore
    f = re.sub(r"[^a-z0-9]+", "_", f).strip("_")
    ln = re.sub(r"[^a-z0-9]+", "_", ln).strip("_")

    if f and ln:
        return f"{f}_{ln}"
    if ln:
        return ln
    return ""


def _name_key_from_initial_last(first_initial: str | None, last: str | None) -> str:
    """Create name key from initial and last name.

    Examples:
        ("Z", "Williamson") → "z_williamson"
        ("L", "Dončić") → "l_doncic"
    """
    fi = (first_initial or "").strip().lower()
    ln = (last or "").strip().lower()

    # Strip accents
    fi = strip_accents(fi)
    ln = strip_accents(ln)

    # Keep only first character of initial
    fi = re.sub(r"[^a-z0-9]+", "", fi)[:1]
    ln = re.sub(r"[^a-z0-9]+", "_", ln).strip("_")

    if fi and ln:
        return f"{fi}_{ln}"
    if ln:
        return ln
    return ""


def _parse_last_comma_first(name: str) -> tuple[str | None, str | None]:
    """Parse "LAST, FIRST" format (EuroLeague, ACB).

    Examples:
        "DONCIC, LUKA" → ("Luka", "Doncic")
        "VEZENKOV, ALEKSANDAR" → ("Aleksandar", "Vezenkov")
        "Smith" → (None, None)  # No comma found
    """
    parts = [clean_spaces(p) for p in name.split(",", 1)]
    if len(parts) != 2:
        return None, None

    last = titleish(parts[0])
    first = titleish(parts[1])
    return first, last


def _parse_initial_dot_last(name: str) -> tuple[str | None, str | None, str | None]:
    """Parse "I. Last" format (NCAA, G-League).

    Returns (first, last, first_initial) where first=None when only initial available.

    Examples:
        "Z. Williamson" → (None, "Williamson", "Z")
        "A. Caruso" → (None, "Caruso", "A")
        "Zion Williamson" → (None, None, None)  # Doesn't match pattern
    """
    m = re.match(r"^\s*([A-Za-z])\.\s+(.+?)\s*$", name)
    if not m:
        return None, None, None

    first_initial = m.group(1).upper()
    last = titleish(m.group(2))

    # We do NOT guess full first name here - only return what we have
    return None, last, first_initial


def _parse_first_last(name: str) -> tuple[str | None, str | None]:
    """Parse "First Last" format (standard).

    Best-effort split; does not perfectly handle compound last names.

    Examples:
        "Zion Williamson" → ("Zion", "Williamson")
        "LaMelo Ball" → ("Lamelo", "Ball")
        "Williamson" → (None, "Williamson")  # Single name
    """
    parts = clean_spaces(name).split(" ")
    if len(parts) < 2:
        # Single name - treat as last name
        return None, titleish(parts[0]) if parts else None

    first = titleish(parts[0])
    last = titleish(" ".join(parts[1:]))
    return first, last


# League-specific parsing rules based on observed format patterns
LEAGUE_NAME_FORMAT: dict[str, str] = {
    "EUROLEAGUE": "LAST_COMMA_FIRST",
    "ACB": "LAST_COMMA_FIRST",
    "ABA": "LAST_COMMA_FIRST",  # NOTE: Adriatic League in dataset
    "NCAA_MBB": "INITIAL_DOT_LAST",
    "G_LEAGUE": "INITIAL_DOT_LAST",
    "NBL": "FIRST_LAST",
    "CEBL": "FIRST_LAST",
    "OTE": "FIRST_LAST",
    # Add more leagues as needed
}


def normalize_player_name(league: str, player_name_raw: str) -> NormalizedName:
    """Main normalization function - parses name based on league format.

    Args:
        league: League code (e.g., "NCAA_MBB", "EUROLEAGUE")
        player_name_raw: Raw player name from data source

    Returns:
        NormalizedName with all parsed components and keys

    Examples:
        normalize_player_name("NCAA_MBB", "Z. Williamson")
        → NormalizedName(
            raw="Z. Williamson",
            first=None,
            last="Williamson",
            first_initial="Z",
            canonical_full="Williamson",
            name_key_canonical=None,  # None for initials-only to avoid collisions
            name_key_initial="z_williamson"
        )

        normalize_player_name("EUROLEAGUE", "DONCIC, LUKA")
        → NormalizedName(
            raw="DONCIC, LUKA",
            first="Luka",
            last="Doncic",
            first_initial="L",
            canonical_full="Luka Doncic",
            name_key_canonical="luka_doncic",
            name_key_initial="l_doncic"
        )
    """
    # Handle None/empty input
    raw = "" if player_name_raw is None else str(player_name_raw)
    raw = clean_spaces(raw)

    # Remove suffixes (Jr., Sr., II, III, etc.) for parsing
    raw_no_suffix = clean_spaces(_SUFFIX_RE.sub("", raw))

    # Strip accents for parsing (but keep original in raw)
    raw_ascii = strip_accents(raw_no_suffix)

    # Get league format pattern
    fmt = LEAGUE_NAME_FORMAT.get(league, "FIRST_LAST")

    # Initialize components
    first: str | None = None
    last: str | None = None
    first_initial: str | None = None

    # Try format-specific parsing first
    if fmt == "LAST_COMMA_FIRST" and "," in raw_ascii:
        f, ln = _parse_last_comma_first(raw_ascii)
        if f and ln:
            first, last = f, ln

    # Try initial-dot format if configured or if nothing found yet
    if first is None and fmt == "INITIAL_DOT_LAST":
        f, ln, fi = _parse_initial_dot_last(raw_ascii)
        if ln:  # We at least got a last name
            last = ln
            first_initial = fi
            # first remains None - we don't guess full name from initial

    # Fallback to standard "First Last" parsing
    if first is None and last is None:
        f, ln = _parse_first_last(raw_ascii)
        if ln:
            first, last = f, ln

    # Derive first_initial from first name if we have it
    if first_initial is None and first:
        first_initial = first[0].upper()

    # Build canonical full name
    if first and last:
        canonical_full = clean_spaces(f"{first} {last}")
    elif last:
        canonical_full = last
    else:
        # Edge case: couldn't parse at all, use cleaned raw
        canonical_full = clean_spaces(raw_ascii)

    # Build name keys
    # Session 331/332 FIX: Set NAME_KEY_CANONICAL = None for initials-only names
    # to avoid collision (e.g., "Z. Williamson" and "D. Williamson" both → "williamson")
    if first and last:
        # Full name available: "Zion Williamson" → "zion_williamson"
        name_key_canonical = _name_key_from_first_last(first, last)
    elif first:
        # Only first name: "Zion" → "zion"
        name_key_canonical = _name_key_from_first_last(first, None)
    else:
        # Only last name or initials: set to None to avoid collisions
        # "Z. Williamson" → None (use NAME_KEY_INITIAL instead)
        name_key_canonical = None

    name_key_initial: str | None
    if last and first_initial:
        name_key_initial = _name_key_from_initial_last(first_initial, last)
    else:
        name_key_initial = name_key_canonical

    return NormalizedName(
        raw=raw,
        first=first,
        last=last,
        first_initial=first_initial,
        canonical_full=canonical_full,
        name_key_canonical=name_key_canonical,
        name_key_initial=name_key_initial,
    )


def test_normalization() -> None:
    """Test cases for manual verification."""
    tests = [
        ("NCAA_MBB", "Z. Williamson", "z_williamson", "williamson"),
        ("EUROLEAGUE", "DONCIC, LUKA", "luka_doncic", "l_doncic"),
        ("ACB", "L. Doncic", "l_doncic", "l_doncic"),
        ("NBL", "LaMelo Ball", "lamelo_ball", "l_ball"),
        ("G_LEAGUE", "A. Caruso", "a_caruso", "caruso"),
    ]

    print("Testing name normalization...")
    for league, raw, expected_canonical_key, expected_initial_key in tests:
        result = normalize_player_name(league, raw)
        print(f"\n{league:12} | {raw:20}")
        print(f"  canonical: {result.canonical_full:20} key: {result.name_key_canonical}")
        print(f"  initial:   {result.first_initial or '?':20} key: {result.name_key_initial}")
        assert (
            result.name_key_canonical == expected_canonical_key
            or result.name_key_initial == expected_initial_key
        ), f"Mismatch: got {result.name_key_canonical}/{result.name_key_initial}, expected {expected_canonical_key}/{expected_initial_key}"

    print("\n✓ All tests passed")


if __name__ == "__main__":
    test_normalization()
