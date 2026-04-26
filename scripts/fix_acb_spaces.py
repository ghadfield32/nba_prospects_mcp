#!/usr/bin/env python
# ruff: noqa: E402
"""Fix ACB Player ID Spaces (Session 330d)

Seasons 2021-22, 2022-23, 2023-24 have spaces in player IDs instead of underscores.
This script normalizes all to use underscores.

BEFORE: acb:p busquets
AFTER:  acb:p_busquets
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
import pandas as pd

DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=ACB"

# Seasons with spaces (need fixing)
SEASONS_TO_FIX = ["2021-22", "2022-23", "2023-24"]


def fix_season(season: str):
    """Fix ACB season to replace spaces with underscores in player IDs."""
    print(f"\nFixing {season}...")

    season_dir = CANONICAL_DIR / f"season={season}"
    data_file = season_dir / "data.parquet"

    if not data_file.exists():
        print(f"  ⚠️  File not found: {data_file}")
        return

    # Load data
    df = pd.read_parquet(data_file)
    print(f"  Loaded {len(df)} records")

    # Show before
    sample_before = df["SOURCE_PLAYER_ID"].head(3).tolist()
    print(f"  Before: {sample_before}")

    # Replace spaces with underscores
    df["SOURCE_PLAYER_ID"] = df["SOURCE_PLAYER_ID"].str.replace(" ", "_")

    # Show after
    sample_after = df["SOURCE_PLAYER_ID"].head(3).tolist()
    print(f"  After:  {sample_after}")

    # Save
    df.to_parquet(data_file, index=False, compression="snappy")
    print("  ✓ Saved")


def main():
    """Main execution."""
    print("=" * 80)
    print("FIX ACB PLAYER ID SPACES")
    print("=" * 80)

    for season in SEASONS_TO_FIX:
        fix_season(season)

    print("\n" + "=" * 80)
    print("FIXED! Now re-run:")
    print("  1. python scripts/multi_gate_player_matcher.py")
    print("  2. python scripts/build_unified_career_gold_chunked.py")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
