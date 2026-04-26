#!/usr/bin/env python3
"""Fix EUROLEAGUE SOURCE_PLAYER_ID Trailing Whitespace

Session 332b Priority 1 Fix

ROOT CAUSE:
  EUROLEAGUE fetcher writes player IDs with trailing whitespace (e.g., "P005929   ").
  This breaks exact matches in validators and represents data quality debt.

FIX:
  Strip SOURCE_PLAYER_ID at the source (canonical files) before rebuilding player_map.

AFFECTED:
  581 EUROLEAGUE player IDs (2.06% of player_map) have trailing whitespace.

STEPS:
  1. Backup EUROLEAGUE canonical files
  2. Strip SOURCE_PLAYER_ID and PLAYER_ID columns
  3. Verify no data loss
  4. Report changes

SAFETY:
  - Creates backup before modification
  - Validates row counts unchanged
  - Shows before/after samples
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical" / "box_player_game" / "league=EUROLEAGUE"


def backup_file(file_path: Path) -> Path:
    """Create timestamped backup of file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.parent / f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"

    import shutil

    shutil.copy2(file_path, backup_path)

    return backup_path


def fix_euroleague_whitespace():
    """Fix trailing whitespace in EUROLEAGUE SOURCE_PLAYER_ID"""

    print("=" * 80)
    print("EUROLEAGUE SOURCE_PLAYER_ID WHITESPACE FIX")
    print("=" * 80)
    print(f"\nTarget directory: {CANONICAL_DIR}")

    if not CANONICAL_DIR.exists():
        print(f"\n✗ ERROR: Directory not found: {CANONICAL_DIR}")
        return 1

    # Find all EUROLEAGUE season directories
    season_dirs = sorted(CANONICAL_DIR.glob("season=*"))

    if not season_dirs:
        print(f"\n✗ ERROR: No season directories found in {CANONICAL_DIR}")
        return 1

    print(f"\nFound {len(season_dirs)} EUROLEAGUE seasons: {[d.name for d in season_dirs]}")

    total_files = 0
    total_fixed = 0
    total_records = 0

    for season_dir in season_dirs:
        data_file = season_dir / "data.parquet"

        if not data_file.exists():
            print(f"\n⚠️  Skipping {season_dir.name} - no data.parquet")
            continue

        print(f"\n{'-' * 80}")
        print(f"Processing: {season_dir.name}")
        print(f"{'-' * 80}")

        # Load data
        df = pd.read_parquet(data_file)
        original_len = len(df)
        total_files += 1
        total_records += original_len

        print(f"  Loaded: {original_len:,} records")

        # Check columns that might have whitespace
        id_cols = []
        if "SOURCE_PLAYER_ID" in df.columns:
            id_cols.append("SOURCE_PLAYER_ID")
        if "PLAYER_ID" in df.columns:
            id_cols.append("PLAYER_ID")

        if not id_cols:
            print("  ⚠️  No player ID columns found, skipping")
            continue

        # Check for whitespace before fixing
        changes_needed = False
        for col in id_cols:
            # Count records with trailing whitespace
            has_trailing = df[col].astype(str).str.endswith(" ").sum()
            has_leading = df[col].astype(str).str.startswith(" ").sum()

            if has_trailing > 0 or has_leading > 0:
                changes_needed = True
                print(f"  {col}:")
                print(
                    f"    Trailing whitespace: {has_trailing} records ({has_trailing/original_len*100:.1f}%)"
                )
                print(
                    f"    Leading whitespace:  {has_leading} records ({has_leading/original_len*100:.1f}%)"
                )

                # Show sample
                if has_trailing > 0:
                    sample = df[df[col].astype(str).str.endswith(" ")][col].iloc[0]
                    print(f'    Sample before: "{sample}" (length: {len(sample)})')

        if not changes_needed:
            print("  ✓ No whitespace issues found, skipping")
            continue

        # Create backup
        print("\n  Creating backup...")
        backup_path = backup_file(data_file)
        print(f"    ✓ Backup saved: {backup_path.name}")

        # Fix whitespace
        print("\n  Applying fix...")
        for col in id_cols:
            df[col] = df[col].astype(str).str.strip()

        # Verify row count unchanged
        if len(df) != original_len:
            print(f"\n  ✗ ERROR: Row count changed! {original_len} → {len(df)}")
            print("    Restoring from backup...")
            df_backup = pd.read_parquet(backup_path)
            df_backup.to_parquet(data_file, index=False)
            return 1

        # Show after samples
        for col in id_cols:
            has_trailing_after = df[col].astype(str).str.endswith(" ").sum()
            has_leading_after = df[col].astype(str).str.startswith(" ").sum()

            if has_trailing_after > 0 or has_leading_after > 0:
                print("\n  ✗ ERROR: Whitespace still present after fix!")
                return 1

            print(f"  {col} after:")
            print("    Trailing whitespace: 0 ✓")
            print("    Leading whitespace:  0 ✓")
            sample = df[col].iloc[0]
            print(f'    Sample after: "{sample}" (length: {len(sample)})')

        # Save fixed data
        print("\n  Saving fixed data...")
        df.to_parquet(data_file, index=False, compression="snappy")
        print(f"    ✓ Saved: {len(df):,} records")

        total_fixed += 1

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"\nProcessed: {total_files} files")
    print(f"Fixed: {total_fixed} files")
    print(f"Total records: {total_records:,}")
    print("\n✓✓✓ EUROLEAGUE whitespace fix complete!")
    print("\nNext steps:")
    print("  1. Rebuild player_map: python scripts/multi_gate_player_matcher.py")
    print("  2. Rebuild gold: python scripts/build_unified_career_gold_chunked.py")
    print("  3. Rerun validators: python scripts/validate_known_players.py")

    return 0


if __name__ == "__main__":
    sys.exit(fix_euroleague_whitespace())
