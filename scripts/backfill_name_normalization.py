#!/usr/bin/env python3
# ruff: noqa: E402
"""Backfill name normalization columns into existing canonical data.

This script:
1. Iterates through all league/season canonical parquet files
2. Checks for contamination (gold columns)
3. Adds normalized name fields if not present
4. Writes updated parquet files (idempotent - safe to run multiple times)

Usage:
    python scripts/backfill_name_normalization.py

After running:
    python scripts/multi_gate_player_matcher.py
    python scripts/build_unified_career_gold_chunked.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.identity.apply_normalization import add_name_fields, assert_no_gold_contamination

CANON_DIR = PROJECT_ROOT / "data" / "canonical" / "box_player_game"


def iter_league_season_files():
    """Yield (league, season, file_path) for all canonical data files."""
    if not CANON_DIR.exists():
        print(f"ERROR: Canonical directory not found: {CANON_DIR}")
        return

    for league_dir in sorted(CANON_DIR.glob("league=*")):
        league = league_dir.name.split("=", 1)[1]

        for season_dir in sorted(league_dir.glob("season=*")):
            season = season_dir.name.split("=", 1)[1]
            data_file = season_dir / "data.parquet"

            if data_file.exists():
                yield league, season, data_file


def main():
    """Main execution."""
    print("=" * 80)
    print("BACKFILL NAME NORMALIZATION INTO CANONICAL DATA")
    print("=" * 80)
    print(f"Canonical directory: {CANON_DIR}")
    print()

    # Columns we expect to add
    EXPECTED_COLUMNS = {
        "PLAYER_NAME_CANONICAL",
        "FIRST_NAME",
        "LAST_NAME",
        "FIRST_INITIAL",
        "NAME_KEY_CANONICAL",
        "NAME_KEY_INITIAL",
    }

    total_files = 0
    updated_files = 0
    skipped_files = 0
    error_files = 0

    for league, season, fpath in iter_league_season_files():
        total_files += 1

        try:
            # Load existing data
            df = pd.read_parquet(fpath)

            # Safety check: no gold columns
            assert_no_gold_contamination(df, context=f"{league}:{season}")

            # Check if already has normalized columns (idempotent)
            if EXPECTED_COLUMNS.issubset(set(df.columns)):
                skipped_files += 1
                continue  # Already normalized

            # Track which columns we're adding
            before_cols = set(df.columns)

            # Apply normalization
            df_norm = add_name_fields(df, league=league, name_col="PLAYER_NAME_RAW")

            # Determine what was added
            after_cols = set(df_norm.columns)
            added_cols = sorted(after_cols - before_cols)

            print(
                f"{league:12} {season:10}  +{len(added_cols)} cols  "
                f"({', '.join(added_cols[:4])}{'...' if len(added_cols) > 4 else ''})"
            )

            # Save updated file
            df_norm.to_parquet(fpath, index=False, compression="snappy")
            updated_files += 1

        except Exception as e:
            print(f"✗ ERROR {league:12} {season:10}  {str(e)[:60]}")
            error_files += 1
            continue

    # Summary
    print("\n" + "=" * 80)
    print("BACKFILL SUMMARY")
    print("=" * 80)
    print(f"Total files processed: {total_files}")
    print(f"  Updated: {updated_files}")
    print(f"  Already normalized: {skipped_files}")
    print(f"  Errors: {error_files}")

    if error_files > 0:
        print(f"\n⚠️  {error_files} files had errors - review output above")
        return 1

    print("\n✓ Backfill complete!")
    print("\nNext steps:")
    print("  1. python scripts/multi_gate_player_matcher.py")
    print("  2. python scripts/build_unified_career_gold_chunked.py")
    print("  3. python scripts/validate_cross_league_players.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
