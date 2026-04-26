#!/usr/bin/env python3
# ruff: noqa: E402
"""Build Player Dimension Table from Canonical Data.

Creates data/identity/player_dim.parquet keyed by (LEAGUE, SOURCE_PLAYER_ID)
containing all available player metadata for:
1. Disambiguation in identity resolution
2. Enrichment of unified dataset
3. Validation and data quality checks

Columns extracted (when available):
- Identity: LEAGUE, SOURCE_PLAYER_ID, PLAYER_NAME_RAW, PLAYER_NAME_CANONICAL
- Parsed: FIRST_NAME, LAST_NAME, FIRST_INITIAL
- Keys: NAME_KEY_CANONICAL, NAME_KEY_INITIAL
- Physical: HEIGHT_CM, WEIGHT_KG, POSITION
- Demographics: BIRTHDATE, BIRTH_YEAR, NATIONALITY
- Other: JERSEY, TEAM_NAME

Usage:
    python scripts/build_player_dim_from_canonical.py

This table can be enriched later with external sources (OTE profiles, ESPN, etc.)
without contaminating canonical game logs.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

CANON_DIR = PROJECT_ROOT / "data" / "canonical" / "box_player_game"
OUTPUT_FILE = PROJECT_ROOT / "data" / "identity" / "player_dim.parquet"


# Columns to extract if present (in order of preference)
IDENTITY_COLS = ["LEAGUE", "SEASON", "SOURCE_PLAYER_ID", "PLAYER_NAME_RAW", "PLAYER_NAME_CANONICAL"]

PARSED_COLS = ["FIRST_NAME", "LAST_NAME", "FIRST_INITIAL"]

KEY_COLS = ["NAME_KEY_CANONICAL", "NAME_KEY_INITIAL"]

PHYSICAL_COLS = ["HEIGHT_CM", "WEIGHT_KG", "POSITION"]

DEMOGRAPHIC_COLS = ["BIRTHDATE", "BIRTH_YEAR", "NATIONALITY"]

OTHER_COLS = ["JERSEY", "TEAM_NAME"]

ALL_POSSIBLE_COLS = (
    IDENTITY_COLS + PARSED_COLS + KEY_COLS + PHYSICAL_COLS + DEMOGRAPHIC_COLS + OTHER_COLS
)


def main():
    """Main execution."""
    print("=" * 80)
    print("BUILD PLAYER DIMENSION TABLE")
    print("=" * 80)
    print(f"Source: {CANON_DIR}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    rows = []
    total_leagues = 0
    total_seasons = 0

    for league_dir in sorted(CANON_DIR.glob("league=*")):
        league = league_dir.name.split("=", 1)[1]
        total_leagues += 1

        for season_dir in sorted(league_dir.glob("season=*")):
            season = season_dir.name.split("=", 1)[1]
            data_file = season_dir / "data.parquet"

            if not data_file.exists():
                continue

            total_seasons += 1

            try:
                df = pd.read_parquet(data_file)

                # Add LEAGUE column if not present
                if "LEAGUE" not in df.columns:
                    df = df.assign(LEAGUE=league)

                # Add SEASON column if not present
                if "SEASON" not in df.columns:
                    df = df.assign(SEASON=season)

                # Keep only columns that exist
                keep_cols = [c for c in ALL_POSSIBLE_COLS if c in df.columns]

                if "SOURCE_PLAYER_ID" not in keep_cols:
                    print(f"  ⚠️  {league:12} {season:10}  Missing SOURCE_PLAYER_ID, skipping")
                    continue

                # Deduplicate by (LEAGUE, SOURCE_PLAYER_ID)
                # Use first occurrence for each player
                player_dim = (
                    df[keep_cols].drop_duplicates(subset=["LEAGUE", "SOURCE_PLAYER_ID"]).copy()
                )

                rows.append(player_dim)

                print(f"  ✓ {league:12} {season:10}  {len(player_dim):5} unique players")

            except Exception as e:
                print(f"  ✗ {league:12} {season:10}  ERROR: {str(e)[:60]}")
                continue

    if not rows:
        print("\n✗ No data found!")
        return 1

    # Combine all
    print(f"\nCombining data from {total_leagues} leagues, {total_seasons} seasons...")
    combined = pd.concat(rows, ignore_index=True)

    print(f"Total rows before deduplication: {len(combined):,}")

    # Final deduplication by (LEAGUE, SOURCE_PLAYER_ID)
    # Keep first occurrence
    combined_dedup = combined.drop_duplicates(
        subset=["LEAGUE", "SOURCE_PLAYER_ID"], keep="first"
    ).copy()

    print(f"Total rows after deduplication: {len(combined_dedup):,}")
    print(f"Unique (LEAGUE, SOURCE_PLAYER_ID) pairs: {len(combined_dedup):,}")

    # Show column coverage
    print("\nColumn coverage:")
    for col in combined_dedup.columns:
        non_null = combined_dedup[col].notna().sum()
        pct = non_null / len(combined_dedup) * 100
        print(f"  {col:25} {non_null:6,} / {len(combined_dedup):6,} ({pct:5.1f}%)")

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined_dedup.to_parquet(OUTPUT_FILE, index=False, compression="snappy")

    print(f"\n✓ Saved to {OUTPUT_FILE}")
    print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("This player_dim table can be enriched with:")
    print("  - OTE player profiles (birth dates, heights)")
    print("  - ESPN player pages")
    print("  - EuroLeague official rosters")
    print("  - Draft combine measurements")
    print()
    print("Enrichment sources should NEVER write back to canonical directories.")
    print("Instead, update this player_dim table and join at gold layer.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
