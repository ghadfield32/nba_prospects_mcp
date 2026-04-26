#!/usr/bin/env python
"""Find and fix duplicate PK rows in gold table.

The gold table primary key should be:
(LEAGUE, SEASON, GAME_ID, SOURCE_PLAYER_ID)

This script identifies duplicates and keeps only the first occurrence.

Usage:
    python scripts/fix_gold_duplicate_pks.py --dry-run
    python scripts/fix_gold_duplicate_pks.py --fix
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
GOLD_TABLE_PATH = BASE_DIR / "data" / "gold" / "player_career_game.parquet"

# Primary key columns
PK_COLS = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]


def find_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Find rows with duplicate primary keys."""
    # Find all duplicates (keep=False marks all occurrences)
    dup_mask = df.duplicated(subset=PK_COLS, keep=False)
    return df[dup_mask].sort_values(PK_COLS)


def analyze_duplicates(dups_df: pd.DataFrame) -> dict:
    """Analyze duplicate rows to understand the pattern."""
    if dups_df.empty:
        return {"total": 0, "groups": 0}

    # Group by PK to count duplicates per group
    grouped = dups_df.groupby(PK_COLS).size().reset_index(name="count")

    analysis = {
        "total_dup_rows": len(dups_df),
        "duplicate_groups": len(grouped),
        "max_dups_per_group": grouped["count"].max(),
        "avg_dups_per_group": grouped["count"].mean(),
        "by_league": dups_df.groupby("LEAGUE").size().to_dict(),
    }

    # Show sample duplicates
    sample_groups = grouped.head(5)
    analysis["sample_groups"] = sample_groups.to_dict("records")

    return analysis


def fix_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate PK rows, keeping the first occurrence."""
    before_count = len(df)
    df_fixed = df.drop_duplicates(subset=PK_COLS, keep="first")
    after_count = len(df_fixed)
    removed = before_count - after_count

    logger.info(f"Removed {removed} duplicate rows ({before_count} -> {after_count})")
    return df_fixed


def main():
    parser = argparse.ArgumentParser(description="Find and fix duplicate PK rows in gold table")
    parser.add_argument("--dry-run", action="store_true", help="Analyze duplicates without fixing")
    parser.add_argument("--fix", action="store_true", help="Remove duplicates and save fixed table")
    parser.add_argument(
        "--show-samples", type=int, default=10, help="Number of sample duplicate rows to display"
    )

    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        logger.error("Specify --dry-run or --fix")
        return

    if not GOLD_TABLE_PATH.exists():
        logger.error(f"Gold table not found at {GOLD_TABLE_PATH}")
        return

    # Load gold table
    logger.info(f"Loading gold table from {GOLD_TABLE_PATH}")
    df = pd.read_parquet(GOLD_TABLE_PATH)
    logger.info(f"Loaded {len(df)} rows")

    # Find duplicates
    logger.info("Finding duplicate PK rows...")
    dups_df = find_duplicates(df)

    if dups_df.empty:
        logger.info("No duplicate PK rows found!")
        return

    # Analyze
    analysis = analyze_duplicates(dups_df)
    logger.info(
        f"Found {analysis['total_dup_rows']} rows in {analysis['duplicate_groups']} duplicate groups"
    )
    logger.info(f"By league: {analysis['by_league']}")
    logger.info(f"Max dups per group: {analysis['max_dups_per_group']}")

    # Show sample duplicates
    if args.show_samples > 0:
        logger.info("\nSample duplicate groups:")
        for i, group in enumerate(analysis.get("sample_groups", [])[:5]):
            logger.info(f"  {i+1}. {group}")

        logger.info(f"\nSample duplicate rows ({args.show_samples}):")
        sample = dups_df.head(args.show_samples)[PK_COLS + ["PLAYER_NAME_RAW", "PTS", "SOURCE"]]
        for _idx, row in sample.iterrows():
            logger.info(f"  {row.to_dict()}")

    if args.fix:
        # Fix duplicates
        logger.info("\nFixing duplicates (keeping first occurrence)...")
        df_fixed = fix_duplicates(df)

        # Verify
        remaining_dups = find_duplicates(df_fixed)
        if not remaining_dups.empty:
            logger.error(f"ERROR: {len(remaining_dups)} duplicate rows remain after fix!")
            return

        # Save
        backup_path = GOLD_TABLE_PATH.with_suffix(".bak.parquet")
        logger.info(f"Creating backup at {backup_path}")
        df.to_parquet(backup_path, index=False)

        logger.info(f"Saving fixed table to {GOLD_TABLE_PATH}")
        df_fixed.to_parquet(GOLD_TABLE_PATH, index=False)
        logger.info("Done!")


if __name__ == "__main__":
    main()
