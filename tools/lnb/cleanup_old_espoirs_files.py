#!/usr/bin/env python3
"""Clean up old Espoirs files from season=2023-2024 directories

After fixing the season labels in the game index and re-ingesting Espoirs games
to season=2024-2025, we need to remove the old files from season=2023-2024.

This script:
1. Loads the game index to identify which games are Espoirs
2. Finds those game files in season=2023-2024 directories
3. Deletes them (since correct versions are now in season=2024-2025)

Usage:
    python tools/lnb/cleanup_old_espoirs_files.py --dry-run  # Preview
    python tools/lnb/cleanup_old_espoirs_files.py             # Delete
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


def main():
    parser = argparse.ArgumentParser(description="Clean up old Espoirs files from season=2023-2024")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be deleted without deleting"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("  CLEANUP OLD ESPOIRS FILES FROM SEASON=2023-2024")
    print("=" * 80)
    print()

    # Paths
    INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")
    PBP_OLD_DIR = Path("data/raw/lnb/pbp/season=2023-2024")
    SHOTS_OLD_DIR = Path("data/raw/lnb/shots/season=2023-2024")

    # Load game index to get Espoirs game IDs
    print("Loading game index...")
    df_index = pd.read_parquet(INDEX_FILE)

    # Get Espoirs game IDs that should now be in season=2024-2025
    espoirs_games = df_index[df_index["competition"].str.contains("Espoirs", na=False)][
        "game_id"
    ].tolist()

    print(f"Found {len(espoirs_games)} Espoirs games in index")
    print()

    # Find old files
    old_pbp_files = []
    old_shots_files = []

    if PBP_OLD_DIR.exists():
        for game_id in espoirs_games:
            pbp_file = PBP_OLD_DIR / f"game_id={game_id}.parquet"
            if pbp_file.exists():
                old_pbp_files.append(pbp_file)

    if SHOTS_OLD_DIR.exists():
        for game_id in espoirs_games:
            shots_file = SHOTS_OLD_DIR / f"game_id={game_id}.parquet"
            if shots_file.exists():
                old_shots_files.append(shots_file)

    print("=" * 80)
    print("OLD FILES FOUND IN season=2023-2024")
    print("=" * 80)
    print()
    print(f"PBP files:   {len(old_pbp_files)}")
    print(f"Shots files: {len(old_shots_files)}")
    print(f"Total:       {len(old_pbp_files) + len(old_shots_files)}")
    print()

    if len(old_pbp_files) + len(old_shots_files) == 0:
        print("✅ No old Espoirs files found in season=2023-2024!")
        print("   All files are already in the correct season partition.")
        return

    if args.dry_run:
        print("=" * 80)
        print("DRY RUN - Would delete the following files:")
        print("=" * 80)
        print()

        if old_pbp_files:
            print(f"PBP files ({len(old_pbp_files)}):")
            for f in old_pbp_files[:5]:
                print(f"  {f.name}")
            if len(old_pbp_files) > 5:
                print(f"  ... and {len(old_pbp_files) - 5} more")
            print()

        if old_shots_files:
            print(f"Shots files ({len(old_shots_files)}):")
            for f in old_shots_files[:5]:
                print(f"  {f.name}")
            if len(old_shots_files) > 5:
                print(f"  ... and {len(old_shots_files) - 5} more")
            print()

        print("[DRY RUN] Run without --dry-run to delete these files")
        return

    # Delete files
    print("=" * 80)
    print("DELETING OLD FILES")
    print("=" * 80)
    print()

    deleted_pbp = 0
    deleted_shots = 0

    for f in old_pbp_files:
        try:
            f.unlink()
            deleted_pbp += 1
        except Exception as e:
            print(f"  [ERROR] Could not delete {f.name}: {e}")

    for f in old_shots_files:
        try:
            f.unlink()
            deleted_shots += 1
        except Exception as e:
            print(f"  [ERROR] Could not delete {f.name}: {e}")

    print(f"✅ Deleted {deleted_pbp} PBP files")
    print(f"✅ Deleted {deleted_shots} shots files")
    print(f"✅ Total: {deleted_pbp + deleted_shots} files removed")
    print()

    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print()
    print("All old Espoirs files have been removed from season=2023-2024.")
    print("Correct files are now in season=2024-2025 with proper LEAGUE values.")
    print()


if __name__ == "__main__":
    main()
