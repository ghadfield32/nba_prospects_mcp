#!/usr/bin/env python3
"""Fix Espoirs season labels in game index

Espoirs games have game dates from 2024-2025 season but are labeled as "2023-2024" in the index.
This script fixes the season label based on game dates.

Season determination:
- 2024-2025 season: Sep 2024 - Aug 2025
- 2023-2024 season: Sep 2023 - Aug 2024

Usage:
    python tools/lnb/fix_espoirs_season_in_index.py --dry-run  # Preview changes
    python tools/lnb/fix_espoirs_season_in_index.py             # Apply fixes
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd


def determine_season_from_date(game_date: str) -> str:
    """Determine season label from game date

    Season runs Sep-Aug, so:
    - Sep 2024 - Aug 2025 = "2024-2025"
    - Sep 2023 - Aug 2024 = "2023-2024"
    """
    date = pd.to_datetime(game_date)
    year = date.year
    month = date.month

    # If month is Sep-Dec, season starts this year
    # If month is Jan-Aug, season started last year
    if month >= 9:
        return f"{year}-{year+1}"
    else:
        return f"{year-1}-{year}"


def main():
    parser = argparse.ArgumentParser(description="Fix Espoirs season labels in game index")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")
    args = parser.parse_args()

    print("=" * 80)
    print("  FIX ESPOIRS SEASON LABELS IN GAME INDEX")
    print("=" * 80)
    print()

    INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")

    if not INDEX_FILE.exists():
        print(f"❌ Game index not found: {INDEX_FILE}")
        return

    # Load index
    df = pd.read_parquet(INDEX_FILE)

    print(f"Loaded game index: {len(df)} games")
    print()

    # Find Espoirs games
    espoirs_mask = df["competition"].str.contains("Espoirs", na=False)
    espoirs_df = df[espoirs_mask].copy()

    print(f"Found {len(espoirs_df)} Espoirs games:")
    print(espoirs_df.groupby(["competition", "season"]).size())
    print()

    if len(espoirs_df) == 0:
        print("No Espoirs games found, nothing to fix")
        return

    # Determine correct season from game dates
    espoirs_df["correct_season"] = espoirs_df["game_date"].apply(determine_season_from_date)

    # Find games with wrong season
    wrong_season_mask = espoirs_df["season"] != espoirs_df["correct_season"]
    wrong_season_df = espoirs_df[wrong_season_mask]

    print("=" * 80)
    print("SEASON LABEL CORRECTIONS NEEDED")
    print("=" * 80)
    print()

    if len(wrong_season_df) == 0:
        print("✅ All Espoirs games already have correct season labels!")
        return

    print(f"Found {len(wrong_season_df)} games with incorrect season labels:")
    print()

    # Show summary of changes
    for (comp, old_season, new_season), group in wrong_season_df.groupby(
        ["competition", "season", "correct_season"]
    ):
        print(f"  {comp}:")
        print(f"    {old_season} → {new_season}: {len(group)} games")

    print()
    print("Sample game dates to verify:")
    sample = wrong_season_df.head(5)[["competition", "season", "game_date", "correct_season"]]
    for _, row in sample.iterrows():
        print(
            f"  {row['competition']:20} | {row['season']} | {row['game_date']} | → {row['correct_season']}"
        )

    print()

    if args.dry_run:
        print("[DRY RUN] Changes NOT saved. Run without --dry-run to apply fixes.")
        return

    # Apply fixes to main dataframe
    df.loc[espoirs_mask & wrong_season_mask, "season"] = espoirs_df.loc[
        wrong_season_mask, "correct_season"
    ]

    # Save updated index
    print("Saving updated game index...")
    df.to_parquet(INDEX_FILE, index=False)
    print("✅ Game index updated successfully!")
    print()

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("The game index has been updated with correct season labels.")
    print("Now you need to re-ingest the Espoirs games with the correct season:")
    print()
    print(
        "  python tools/lnb/bulk_ingest_pbp_shots.py --leagues espoirs_elite espoirs_prob --seasons 2024-2025 --force"
    )
    print()
    print("This will move the parquet files to the correct season partition directories.")
    print()


if __name__ == "__main__":
    main()
