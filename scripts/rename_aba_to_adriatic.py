#!/usr/bin/env python3
"""Rename ABA → ABA_ADRIATIC for Taxonomy Clarity

Session 332b Priority 2 Fix

ROOT CAUSE:
  Dataset contains ABA Adriatic (European league, 2024-25 season), NOT the historical
  American Basketball Association (1970s). Same abbreviation causes confusion.

FIX:
  Rename league code from "ABA" to "ABA_ADRIATIC" throughout:
  1. Canonical directory: league=ABA → league=ABA_ADRIATIC
  2. LEAGUE column in parquet files
  3. Update all references in scripts

AFFECTED:
  - 1 canonical directory (league=ABA)
  - 1 season (2024-25): 5,340 records
  - 264 unique players
  - Multiple Python scripts

STEPS:
  1. Backup canonical directory
  2. Rename directory league=ABA → league=ABA_ADRIATIC
  3. Update LEAGUE/SOURCE_LEAGUE columns in parquet files
  4. Verify no data loss
  5. Report changes

SAFETY:
  - Creates backup before modification
  - Validates row counts unchanged
  - Shows before/after verification
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
CANONICAL_BASE = PROJECT_ROOT / "data" / "canonical" / "box_player_game"
ABA_DIR = CANONICAL_BASE / "league=ABA"
ABA_ADRIATIC_DIR = CANONICAL_BASE / "league=ABA_ADRIATIC"


def backup_directory(dir_path: Path) -> Path:
    """Create timestamped backup of directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = dir_path.parent / f"{dir_path.name}_backup_{timestamp}"

    shutil.copytree(dir_path, backup_path)

    return backup_path


def update_league_column_in_parquet(file_path: Path, old_league: str, new_league: str):
    """Update LEAGUE/SOURCE_LEAGUE column in parquet file"""
    df = pd.read_parquet(file_path)
    original_len = len(df)

    # Update LEAGUE column if it exists
    if "LEAGUE" in df.columns:
        df["LEAGUE"] = df["LEAGUE"].replace(old_league, new_league)

    # Update SOURCE_LEAGUE column if it exists
    if "SOURCE_LEAGUE" in df.columns:
        df["SOURCE_LEAGUE"] = df["SOURCE_LEAGUE"].replace(old_league, new_league)

    # Verify row count unchanged
    assert len(df) == original_len, f"Row count changed! {original_len} → {len(df)}"

    # Save
    df.to_parquet(file_path, index=False, compression="snappy")

    return original_len


def rename_aba_to_adriatic():
    """Rename ABA → ABA_ADRIATIC"""

    print("=" * 80)
    print("RENAME ABA → ABA_ADRIATIC")
    print("=" * 80)
    print()
    print("Purpose: Prevent taxonomy confusion")
    print("  Current: ABA (ambiguous - Adriatic or American?)")
    print("  New: ABA_ADRIATIC (clear - European league)")
    print()

    # Check if ABA directory exists
    if not ABA_DIR.exists():
        print(f"✗ ERROR: ABA directory not found: {ABA_DIR}")
        return 1

    # Check if ABA_ADRIATIC already exists
    if ABA_ADRIATIC_DIR.exists():
        print(f"✗ ERROR: ABA_ADRIATIC directory already exists: {ABA_ADRIATIC_DIR}")
        print("  This rename may have already been completed.")
        return 1

    # Find all season directories
    season_dirs = sorted(ABA_DIR.glob("season=*"))

    if not season_dirs:
        print(f"✗ ERROR: No season directories found in {ABA_DIR}")
        return 1

    print(f"Found {len(season_dirs)} ABA seasons: {[d.name for d in season_dirs]}")
    print()

    # Step 1: Backup
    print("Step 1: Creating backup...")
    backup_path = backup_directory(ABA_DIR)
    print(f"  ✓ Backup created: {backup_path.name}")
    print()

    # Step 2: Update LEAGUE column in all parquet files
    print("Step 2: Updating LEAGUE column in parquet files...")
    total_records = 0

    for season_dir in season_dirs:
        data_file = season_dir / "data.parquet"

        if data_file.exists():
            try:
                record_count = update_league_column_in_parquet(data_file, "ABA", "ABA_ADRIATIC")
                total_records += record_count
                print(f"  ✓ {season_dir.name}: Updated {record_count:,} records")
            except Exception as e:
                print(f"  ✗ ERROR updating {data_file}: {e}")
                print("  Restoring from backup...")
                shutil.rmtree(ABA_DIR)
                shutil.copytree(backup_path, ABA_DIR)
                return 1

    print(f"  Total records updated: {total_records:,}")
    print()

    # Step 3: Rename directory
    print("Step 3: Renaming directory...")
    try:
        ABA_DIR.rename(ABA_ADRIATIC_DIR)
        print(f"  ✓ Renamed: {ABA_DIR.name} → {ABA_ADRIATIC_DIR.name}")
    except Exception as e:
        print(f"  ✗ ERROR renaming directory: {e}")
        print("  Restoring from backup...")
        shutil.copytree(backup_path, ABA_DIR)
        return 1

    print()

    # Step 4: Verification
    print("Step 4: Verification...")

    # Check new directory exists
    if not ABA_ADRIATIC_DIR.exists():
        print(f"  ✗ ERROR: New directory not found: {ABA_ADRIATIC_DIR}")
        return 1

    # Check old directory gone
    if ABA_DIR.exists():
        print(f"  ✗ ERROR: Old directory still exists: {ABA_DIR}")
        return 1

    # Verify record counts
    verify_records = 0
    for season_dir in ABA_ADRIATIC_DIR.glob("season=*"):
        data_file = season_dir / "data.parquet"
        if data_file.exists():
            df = pd.read_parquet(data_file)
            verify_records += len(df)

            # Verify LEAGUE column updated
            if "SOURCE_LEAGUE" in df.columns:
                assert (
                    df["SOURCE_LEAGUE"] == "ABA_ADRIATIC"
                ).all(), f"Found non-ABA_ADRIATIC values in {season_dir.name}"

    assert (
        verify_records == total_records
    ), f"Record count mismatch! Before: {total_records}, After: {verify_records}"

    print("  ✓ Directory renamed successfully")
    print(f"  ✓ All {verify_records:,} records verified with SOURCE_LEAGUE='ABA_ADRIATIC'")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("✓ Renamed league=ABA → league=ABA_ADRIATIC")
    print(f"✓ Updated {total_records:,} records across {len(season_dirs)} seasons")
    print(f"✓ Backup saved: {backup_path}")
    print()
    print("Next steps:")
    print("  1. Update scripts: Replace 'ABA' with 'ABA_ADRIATIC' in tier1_leagues lists")
    print("  2. Rebuild player_map: python scripts/multi_gate_player_matcher.py")
    print("  3. Rebuild gold: python scripts/build_unified_career_gold_chunked.py")
    print("  4. Remove David Thompson test from known_players.yaml")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(rename_aba_to_adriatic())
