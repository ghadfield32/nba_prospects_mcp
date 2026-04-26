#!/usr/bin/env python
# ruff: noqa: E402
"""Clean Contaminated Gold Columns from ACB Data

The ACB canonical data has PLAYER_UID and other gold columns from a previous run.
This script removes them.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
import pandas as pd

DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=ACB"

# Gold columns to remove
GOLD_COLUMNS = [
    "PLAYER_UID",
    "CANONICAL_PLAYER_ID",
    "CAREER_GAME_NUMBER",
    "LEAGUE_GAME_NUMBER",
    "CONFIDENCE",
    "MATCH_RULE",
]

ACB_SEASONS = [
    "2015-16",
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
]


def clean_season(season: str):
    """Remove contaminated gold columns from a season."""
    print(f"\nCleaning {season}...")

    season_dir = CANONICAL_DIR / f"season={season}"
    data_file = season_dir / "data.parquet"

    if not data_file.exists():
        print(f"  ⚠️  File not found: {data_file}")
        return

    # Load data
    df = pd.read_parquet(data_file)
    print(f"  Loaded {len(df)} records")

    # Check for contaminated columns
    cols_to_drop = [col for col in GOLD_COLUMNS if col in df.columns]

    if not cols_to_drop:
        print("  ✓ No contaminated columns found")
        return

    print(f"  Dropping: {cols_to_drop}")

    # Drop columns
    df = df.drop(columns=cols_to_drop)

    # Save
    df.to_parquet(data_file, index=False, compression="snappy")
    print("  ✓ Saved cleaned data")


def main():
    """Main execution."""
    print("=" * 80)
    print("CLEAN ACB CONTAMINATED COLUMNS")
    print("=" * 80)

    for season in ACB_SEASONS:
        clean_season(season)

    print("\n" + "=" * 80)
    print("CLEANED! Now re-run:")
    print("  python scripts/build_unified_career_gold_chunked.py")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
