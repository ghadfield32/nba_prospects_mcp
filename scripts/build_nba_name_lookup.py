#!/usr/bin/env python3
"""Build NBA Name Lookup Table

Creates a lookup dictionary to expand player initials using NBA data as source of truth.

Usage:
    python scripts/build_nba_name_lookup.py
"""

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd


def normalize_to_key(name: str) -> str:
    """Quick normalization for dictionary keys (lowercase, no special chars)."""
    if not name or pd.isna(name):
        return ""

    # Unicode normalization
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Lowercase, remove special chars
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized.strip())

    return normalized


def build_nba_name_lookup() -> tuple[dict[str, list[str]], dict[str, str]]:
    """Build NBA name lookup tables from NBA player data.

    Returns:
        Tuple of:
            - last_name_lookup: Dict mapping last_name → list of full names
            - initial_last_lookup: Dict mapping "i_lastname" → full name
    """
    print("Loading NBA player data...")
    nba_path = Path(
        "/workspace/api/src/airflow_project/data/nba_api_data_pull/nba_player_data_final_inflated.parquet"
    )

    if not nba_path.exists():
        print(f"ERROR: NBA data not found at {nba_path}")
        return {}, {}

    nba_df = pd.read_parquet(nba_path)
    print(f"Loaded {len(nba_df):,} NBA records")
    print(f"Unique players: {nba_df['Player'].nunique():,}")

    # Get unique player names
    nba_names = nba_df[["Player", "PlayerID"]].drop_duplicates()

    # Build lookup dictionaries
    last_name_lookup = {}  # last_name → [full names]
    initial_last_lookup = {}  # "i_lastname" → full name

    for _, row in nba_names.iterrows():
        full_name = row["Player"]

        # Normalize for lookup
        normalized_full = normalize_to_key(full_name)

        # Parse name
        parts = normalized_full.split()

        if len(parts) < 2:
            # Single name (e.g., "NENE")
            continue

        # Assume last part is last name
        first_name = parts[0]
        last_name = parts[-1]
        first_initial = first_name[0]

        # Add to last_name lookup
        if last_name not in last_name_lookup:
            last_name_lookup[last_name] = []
        last_name_lookup[last_name].append(normalized_full)

        # Add to initial_last lookup
        initial_last_key = f"{first_initial}_{last_name}"
        if initial_last_key not in initial_last_lookup:
            initial_last_lookup[initial_last_key] = normalized_full
        else:
            # Collision - multiple players with same initial + last name
            # Keep first one, log warning
            existing = initial_last_lookup[initial_last_key]
            if existing != normalized_full:
                print(
                    f"  WARNING: Collision for {initial_last_key}: '{existing}' vs '{normalized_full}'"
                )

    print("\nBuilt lookups:")
    print(f"  - Last name → Full names: {len(last_name_lookup):,} entries")
    print(f"  - Initial + Last → Full name: {len(initial_last_lookup):,} entries")

    # Test lookups
    print("\nTest lookups:")

    # Test: L. Doncic
    test_key = "l_doncic"
    if test_key in initial_last_lookup:
        print(f"  ✓ '{test_key}' → '{initial_last_lookup[test_key]}'")
    else:
        print(f"  ✗ '{test_key}' not found")

    # Test: Z. Williamson
    test_key = "z_williamson"
    if test_key in initial_last_lookup:
        print(f"  ✓ '{test_key}' → '{initial_last_lookup[test_key]}'")
    else:
        print(f"  ✗ '{test_key}' not found")

    return last_name_lookup, initial_last_lookup


def save_lookup_tables(last_name_lookup: dict, initial_last_lookup: dict):
    """Save lookup tables to JSON for use by normalization script."""
    import json

    output_dir = Path("data/mappings")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save last_name lookup
    last_name_path = output_dir / "nba_last_name_lookup.json"
    with open(last_name_path, "w") as f:
        json.dump(last_name_lookup, f, indent=2)
    print(f"\n✓ Saved last_name lookup to {last_name_path}")

    # Save initial_last lookup
    initial_last_path = output_dir / "nba_initial_last_lookup.json"
    with open(initial_last_path, "w") as f:
        json.dump(initial_last_lookup, f, indent=2)
    print(f"✓ Saved initial_last lookup to {initial_last_path}")

    return last_name_path, initial_last_path


def main():
    """Main execution."""
    print("=" * 80)
    print("NBA NAME LOOKUP TABLE BUILDER")
    print("=" * 80)

    last_name_lookup, initial_last_lookup = build_nba_name_lookup()

    if len(initial_last_lookup) == 0:
        print("\nERROR: Failed to build lookup tables")
        return 1

    save_lookup_tables(last_name_lookup, initial_last_lookup)

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Run smart normalization with NBA lookup:")
    print("   python scripts/normalize_player_names_smart.py --test-only")
    print("\n2. Apply to full dataset:")
    print("   python scripts/normalize_player_names_smart.py --apply")

    return 0


if __name__ == "__main__":
    sys.exit(main())
