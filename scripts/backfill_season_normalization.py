#!/usr/bin/env python3
# ruff: noqa: E402
"""Backfill Season Normalization - Add 5 season columns to all canonical data.

Processes all 65+ canonical parquet files:
- Reads existing data
- Adds 5 season columns via add_season_fields()
- Validates normalization
- Overwrites original file

Safe to re-run (idempotent).

Usage:
    cd /workspace/nba_prospects_mcp
    python scripts/backfill_season_normalization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.identity.season_normalization import add_season_fields, validate_season_normalization

CANON_DIR = PROJECT_ROOT / "data" / "canonical" / "box_player_game"


def backfill_all_canonical_files():
    """Backfill season normalization to all canonical files."""

    print("=" * 80)
    print("SEASON NORMALIZATION BACKFILL")
    print("=" * 80)
    print(f"Source: {CANON_DIR}")
    print()

    if not CANON_DIR.exists():
        print(f"✗ ERROR: Canonical directory not found: {CANON_DIR}")
        return 1

    processed = 0
    skipped = 0
    errors = []

    for league_dir in sorted(CANON_DIR.glob("league=*")):
        league = league_dir.name.split("=", 1)[1]

        for season_dir in sorted(league_dir.glob("season=*")):
            season_raw = season_dir.name.split("=", 1)[1]
            data_file = season_dir / "data.parquet"

            if not data_file.exists():
                continue

            try:
                # Load
                df = pd.read_parquet(data_file)
                original_len = len(df)

                # Check if already normalized
                if all(
                    col in df.columns
                    for col in [
                        "SEASON_RAW",
                        "SEASON",
                        "SEASON_START_YEAR",
                        "SEASON_END_YEAR",
                        "SEASON_TYPE",
                    ]
                ):
                    # Check if SEASON column already in correct format
                    if df["SEASON"].str.match(r"^\d{4}-\d{2}$").all():
                        print(f"  ↻ {league:12} {season_raw:10}  Already normalized, skipping")
                        skipped += 1
                        continue

                # Add season fields
                print(f"  ⋯ {league:12} {season_raw:10}  Processing...", end="", flush=True)

                df = add_season_fields(df, league=league, season_col="SEASON")

                # Validate
                validation = validate_season_normalization(df)

                if not validation["passed"]:
                    print(f"\r  ✗ {league:12} {season_raw:10}  Validation FAILED")
                    print(f"      {validation}")
                    errors.append((league, season_raw, validation))
                    continue

                # Verify row count unchanged
                if len(df) != original_len:
                    print(
                        f"\r  ✗ {league:12} {season_raw:10}  Row count changed! {original_len} → {len(df)}"
                    )
                    errors.append(
                        (league, season_raw, f"Row count changed: {original_len} → {len(df)}")
                    )
                    continue

                # Save
                df.to_parquet(data_file, index=False, compression="snappy")

                print(
                    f"\r  ✓ {league:12} {season_raw:10}  Normalized ({len(df):,} rows, {validation['unique_seasons']} unique seasons)"
                )
                processed += 1

            except Exception as e:
                print(f"\r  ✗ {league:12} {season_raw:10}  ERROR: {str(e)[:60]}")
                errors.append((league, season_raw, str(e)))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Processed: {processed} files")
    print(f"Skipped: {skipped} files (already normalized)")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for league, season, error in errors[:10]:  # Show first 10 errors
            error_msg = str(error)[:100]
            print(f"  {league:12} {season:10}: {error_msg}")

        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

        # Export error report
        error_report_file = PROJECT_ROOT / "data" / "_reports" / "season_normalization_errors.txt"
        error_report_file.parent.mkdir(parents=True, exist_ok=True)

        with open(error_report_file, "w") as f:
            f.write("SEASON NORMALIZATION BACKFILL ERRORS\n")
            f.write("=" * 80 + "\n\n")
            for league, season, error in errors:
                f.write(f"{league:12} {season:10}\n")
                f.write(f"  {error}\n\n")

        print(f"\nFull error report saved to: {error_report_file}")
        return 1

    print("\n✓ All canonical files normalized successfully!")
    print("\nNext steps:")
    print("  1. Verify a few files manually to confirm normalization")
    print("  2. Run build_unified_career_gold_chunked.py to rebuild unified dataset")
    print("  3. Update fetchers to use add_season_fields() for new data")

    return 0


if __name__ == "__main__":
    sys.exit(backfill_all_canonical_files())
