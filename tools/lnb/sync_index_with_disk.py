#!/usr/bin/env python3
"""Sync game index flags with actual files on disk

This script scans the PBP and shots directories and updates the game index
to accurately reflect which games have been ingested. This is useful when:
- The index was rebuilt and lost track of ingested games
- Manual file cleanup was performed
- You want to verify index accuracy

Usage:
    uv run python tools/lnb/sync_index_with_disk.py

Output:
    Updates data/raw/lnb/lnb_game_index.parquet with correct has_pbp/has_shots flags
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_DIR = Path("data/raw/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"


# ==============================================================================
# SYNC FUNCTIONS
# ==============================================================================


def scan_disk_files(data_dir: Path) -> set[tuple[str, str]]:
    """Scan directory for parquet files and return set of (season, game_id) tuples

    Args:
        data_dir: Directory to scan (PBP_DIR or SHOTS_DIR)

    Returns:
        Set of (season, game_id) tuples for all parquet files found
    """
    files_found = set()

    if not data_dir.exists():
        return files_found

    for file_path in data_dir.rglob("*.parquet"):
        path_str = str(file_path)

        # Extract season from path (format: season=YYYY-YYYY/...)
        if "season=" in path_str:
            season = path_str.split("season=")[1].split("/")[0].split("\\")[0]

            # Extract game_id from filename (format: game_id=<uuid>.parquet)
            if "game_id=" in file_path.name:
                game_id = file_path.name.replace("game_id=", "").replace(".parquet", "")
                files_found.add((season, game_id))

    return files_found


def sync_index_with_disk() -> dict[str, int]:
    """Sync game index flags with actual files on disk

    Returns:
        Dict with sync statistics
    """
    print(f"\n{'='*80}")
    print("  SYNC GAME INDEX WITH DISK")
    print(f"{'='*80}\n")

    # Load index
    if not INDEX_FILE.exists():
        print(f"[ERROR] Game index not found: {INDEX_FILE}")
        print("[ERROR] Run: uv run python tools/lnb/build_game_index.py")
        sys.exit(1)

    print("[1/4] Loading game index...")
    index_df = pd.read_parquet(INDEX_FILE)
    print(f"      Loaded {len(index_df)} games\n")

    # Scan disk for files
    print("[2/4] Scanning disk for PBP files...")
    pbp_files = scan_disk_files(PBP_DIR)
    print(f"      Found {len(pbp_files)} PBP files\n")

    print("[3/4] Scanning disk for shots files...")
    shots_files = scan_disk_files(SHOTS_DIR)
    print(f"      Found {len(shots_files)} shots files\n")

    # Update index flags
    print("[4/4] Updating index flags...")

    # Initialize flags if they don't exist
    if "has_pbp" not in index_df.columns:
        index_df["has_pbp"] = False
    if "has_shots" not in index_df.columns:
        index_df["has_shots"] = False
    if "pbp_fetched_at" not in index_df.columns:
        index_df["pbp_fetched_at"] = None
    if "shots_fetched_at" not in index_df.columns:
        index_df["shots_fetched_at"] = None
    if "last_updated" not in index_df.columns:
        index_df["last_updated"] = None

    stats = {
        "pbp_updated": 0,
        "shots_updated": 0,
        "pbp_cleared": 0,
        "shots_cleared": 0,
    }

    timestamp = datetime.now().isoformat()

    for idx, row in index_df.iterrows():
        season = row["season"]
        game_id = row["game_id"]
        key = (season, game_id)

        # Check PBP
        has_pbp_on_disk = key in pbp_files
        if has_pbp_on_disk and not row.get("has_pbp", False):
            index_df.at[idx, "has_pbp"] = True
            index_df.at[idx, "pbp_fetched_at"] = timestamp
            index_df.at[idx, "last_updated"] = timestamp
            stats["pbp_updated"] += 1
        elif not has_pbp_on_disk and row.get("has_pbp", False):
            index_df.at[idx, "has_pbp"] = False
            index_df.at[idx, "pbp_fetched_at"] = None
            index_df.at[idx, "last_updated"] = timestamp
            stats["pbp_cleared"] += 1

        # Check shots
        has_shots_on_disk = key in shots_files
        if has_shots_on_disk and not row.get("has_shots", False):
            index_df.at[idx, "has_shots"] = True
            index_df.at[idx, "shots_fetched_at"] = timestamp
            index_df.at[idx, "last_updated"] = timestamp
            stats["shots_updated"] += 1
        elif not has_shots_on_disk and row.get("has_shots", False):
            index_df.at[idx, "has_shots"] = False
            index_df.at[idx, "shots_fetched_at"] = None
            index_df.at[idx, "last_updated"] = timestamp
            stats["shots_cleared"] += 1

    # Save updated index
    print("\n[SAVE] Writing updated index...")
    index_df.to_parquet(INDEX_FILE, index=False)
    print(f"       Saved to {INDEX_FILE}\n")

    return stats


def print_summary(stats: dict[str, int]) -> None:
    """Print sync summary

    Args:
        stats: Statistics dict from sync_index_with_disk
    """
    print(f"{'='*80}")
    print("  SYNC SUMMARY")
    print(f"{'='*80}\n")

    print(f"PBP flags set to True:      {stats['pbp_updated']:>5}")
    print(f"PBP flags cleared:          {stats['pbp_cleared']:>5}")
    print()
    print(f"Shots flags set to True:    {stats['shots_updated']:>5}")
    print(f"Shots flags cleared:        {stats['shots_cleared']:>5}")
    print()

    total_changes = sum(stats.values())
    if total_changes == 0:
        print("✅ Index already in sync with disk!")
    else:
        print(f"✅ Updated {total_changes} index entries")

    print()


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    stats = sync_index_with_disk()
    print_summary(stats)

    print(f"{'='*80}")
    print("  SYNC COMPLETE")
    print(f"{'='*80}\n")

    print("Next steps:")
    print("  1. Run validation: uv run python tools/lnb/validate_and_monitor_coverage.py")
    print(
        "  2. Continue ingestion: uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025"
    )
    print()


if __name__ == "__main__":
    main()
