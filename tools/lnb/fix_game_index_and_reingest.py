#!/usr/bin/env python3
"""Fix Game Index and Re-ingest Missing Data

This script fixes the issues discovered during debugging:

ISSUES FOUND:
1. Game index has incorrect season labels (built with old fixture mappings)
2. 2021-2022 and 2022-2023 games not ingested to parquet files
3. 23 synthetic game IDs (LNB_YYYY-YYYY_N) polluting the data

FIXES:
1. Backup existing index and data
2. Remove synthetic game IDs from data directories
3. Rebuild game index with corrected fixture_uuids_by_season.json
4. Ingest missing 2021-2022 and 2022-2023 games
5. Validate all games are correctly labeled and accessible

Usage:
    # Dry run (show what would be done)
    uv run python tools/lnb/fix_game_index_and_reingest.py --dry-run

    # Actually fix the issues
    uv run python tools/lnb/fix_game_index_and_reingest.py

    # Aggressive cleanup (removes ALL data and rebuilds from scratch)
    uv run python tools/lnb/fix_game_index_and_reingest.py --clean-slate

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_DIR = Path("data/raw/lnb")
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
BACKUP_DIR = Path("data/backups/lnb") / datetime.now().strftime("%Y%m%d_%H%M%S")

FIXTURE_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def backup_data(dry_run: bool = False) -> None:
    """Backup existing index and data directories

    Args:
        dry_run: If True, only show what would be backed up
    """
    print("=" * 80)
    print("STEP 1: BACKUP EXISTING DATA")
    print("=" * 80)
    print()

    if not INDEX_FILE.exists() and not PBP_DIR.exists() and not SHOTS_DIR.exists():
        print("⚠️  No existing data to backup")
        return

    print(f"Backup location: {BACKUP_DIR}")
    print()

    items_to_backup = []
    if INDEX_FILE.exists():
        items_to_backup.append(("Index file", INDEX_FILE))
    if PBP_DIR.exists():
        items_to_backup.append(("PBP directory", PBP_DIR))
    if SHOTS_DIR.exists():
        items_to_backup.append(("Shots directory", SHOTS_DIR))

    for name, path in items_to_backup:
        if dry_run:
            print(f"  [DRY RUN] Would backup: {name}")
        else:
            print(f"  [BACKUP] {name}... ", end="")
            try:
                dest = BACKUP_DIR / path.name
                dest.parent.mkdir(parents=True, exist_ok=True)

                if path.is_dir():
                    shutil.copytree(path, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(path, dest)

                print("✅")
            except Exception as e:
                print(f"❌ Error: {e}")

    print()


def identify_synthetic_games() -> dict[str, list[str]]:
    """Identify synthetic game IDs that should be removed

    Returns:
        Dict mapping season -> list of synthetic game IDs
    """
    import pandas as pd

    if not INDEX_FILE.exists():
        return {}

    df = pd.read_parquet(INDEX_FILE)

    # Identify synthetic IDs (LNB_YYYY-YYYY_N pattern)
    synthetic_mask = df["game_id"].str.match(r"^LNB_\d{4}-\d{4}_\d+$")
    synthetic_df = df[synthetic_mask]

    synthetic_by_season = {}
    if "season" in synthetic_df.columns:
        for season in synthetic_df["season"].unique():
            season_synthetic = synthetic_df[synthetic_df["season"] == season]["game_id"].tolist()
            synthetic_by_season[season] = season_synthetic

    return synthetic_by_season


def remove_synthetic_games(dry_run: bool = False) -> None:
    """Remove synthetic game IDs from data directories

    Args:
        dry_run: If True, only show what would be removed
    """
    print("=" * 80)
    print("STEP 2: REMOVE SYNTHETIC GAME IDs")
    print("=" * 80)
    print()

    synthetic_games = identify_synthetic_games()

    if not synthetic_games:
        print("✅ No synthetic game IDs found")
        print()
        return

    total_synthetic = sum(len(games) for games in synthetic_games.values())
    print(f"Found {total_synthetic} synthetic game IDs to remove:")
    print()

    for season, game_ids in synthetic_games.items():
        print(f"  {season}: {len(game_ids)} games")
        for game_id in game_ids[:3]:
            print(f"    - {game_id}")
        if len(game_ids) > 3:
            print(f"    ... and {len(game_ids) - 3} more")
        print()

    # Remove from PBP directory
    for season, game_ids in synthetic_games.items():
        season_pbp_dir = PBP_DIR / f"season={season}"
        if season_pbp_dir.exists():
            for game_id in game_ids:
                pbp_file = season_pbp_dir / f"game_id={game_id}.parquet"
                if pbp_file.exists():
                    if dry_run:
                        print(f"  [DRY RUN] Would remove: {pbp_file}")
                    else:
                        pbp_file.unlink()
                        print(f"  [REMOVED] {pbp_file.name}")

    # Remove from shots directory
    for season, game_ids in synthetic_games.items():
        season_shots_dir = SHOTS_DIR / f"season={season}"
        if season_shots_dir.exists():
            for game_id in game_ids:
                shots_file = season_shots_dir / f"game_id={game_id}.parquet"
                if shots_file.exists():
                    if dry_run:
                        print(f"  [DRY RUN] Would remove: {shots_file}")
                    else:
                        shots_file.unlink()
                        print(f"  [REMOVED] {shots_file.name}")

    print()


def clean_slate_removal(dry_run: bool = False) -> None:
    """Remove ALL existing data for a clean rebuild

    Args:
        dry_run: If True, only show what would be removed
    """
    print("=" * 80)
    print("STEP 2: CLEAN SLATE - REMOVE ALL EXISTING DATA")
    print("=" * 80)
    print()

    print("⚠️  WARNING: This will remove ALL existing PBP/shots data!")
    print()

    items_to_remove = []
    if INDEX_FILE.exists():
        items_to_remove.append(("Index file", INDEX_FILE))
    if PBP_DIR.exists():
        items_to_remove.append(("PBP directory", PBP_DIR))
    if SHOTS_DIR.exists():
        items_to_remove.append(("Shots directory", SHOTS_DIR))

    for name, path in items_to_remove:
        if dry_run:
            print(f"  [DRY RUN] Would remove: {name}")
        else:
            print(f"  [REMOVE] {name}... ", end="")
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                print("✅")
            except Exception as e:
                print(f"❌ Error: {e}")

    print()


def rebuild_game_index(dry_run: bool = False) -> None:
    """Rebuild game index with corrected fixture mappings

    Args:
        dry_run: If True, only show what would be done
    """
    print("=" * 80)
    print("STEP 3: REBUILD GAME INDEX")
    print("=" * 80)
    print()

    if not FIXTURE_FILE.exists():
        print(f"❌ Fixture file not found: {FIXTURE_FILE}")
        return

    # Load fixture mappings
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture_data = json.load(f)
        fixture_mappings = fixture_data.get("mappings", {})

    print("Loaded fixture mappings:")
    for season, uuids in sorted(fixture_mappings.items()):
        print(f"  {season}: {len(uuids)} UUIDs")
    print()

    if dry_run:
        print("[DRY RUN] Would rebuild index with these seasons")
        return

    # FIX BUG #3: Delete old index to prevent merge
    if INDEX_FILE.exists():
        print("  [DELETE] Removing old index to force clean rebuild...")
        INDEX_FILE.unlink()
        print("  ✅ Old index deleted")
        print()

    # FIX BUG #1: Pass seasons as separate arguments, not comma-separated string
    import subprocess

    cmd = [
        sys.executable,
        str(project_root / "tools" / "lnb" / "build_game_index.py"),
        "--seasons",
    ] + sorted(fixture_mappings.keys())  # Each season as separate argument

    print(f"Running: build_game_index.py --seasons {' '.join(sorted(fixture_mappings.keys()))}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✅ Index rebuilt successfully")
        else:
            print("❌ Index rebuild failed:")
            print(result.stderr[:500])

    except Exception as e:
        print(f"❌ Error rebuilding index: {e}")

    print()


def ingest_missing_games(dry_run: bool = False) -> None:
    """Ingest PBP/shots data for games missing from data directories

    Args:
        dry_run: If True, only show what would be ingested
    """
    print("=" * 80)
    print("STEP 4: INGEST MISSING GAMES")
    print("=" * 80)
    print()

    if not FIXTURE_FILE.exists():
        print(f"❌ Fixture file not found: {FIXTURE_FILE}")
        return

    # Load fixture mappings
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture_data = json.load(f)
        fixture_mappings = fixture_data.get("mappings", {})

    # Check which seasons need ingestion
    seasons_to_ingest = []
    for season, uuids in sorted(fixture_mappings.items()):
        season_pbp_dir = PBP_DIR / f"season={season}"

        if not season_pbp_dir.exists():
            seasons_to_ingest.append(season)
            print(f"  ⚠️  {season}: No PBP data (needs ingestion)")
        else:
            existing_files = len(list(season_pbp_dir.glob("game_id=*.parquet")))
            expected_count = len(uuids)

            if existing_files < expected_count:
                seasons_to_ingest.append(season)
                print(f"  ⚠️  {season}: {existing_files}/{expected_count} games (needs ingestion)")
            else:
                print(f"  ✅ {season}: {existing_files}/{expected_count} games (complete)")

    print()

    if not seasons_to_ingest:
        print("✅ All games already ingested")
        return

    if dry_run:
        print(f"[DRY RUN] Would ingest: {', '.join(seasons_to_ingest)}")
        return

    # Run bulk_ingest_pbp_shots.py for each missing season
    import subprocess

    for season in seasons_to_ingest:
        cmd = [
            sys.executable,
            str(project_root / "tools" / "lnb" / "bulk_ingest_pbp_shots.py"),
            "--seasons",
            season,
        ]

        print(f"Ingesting {season}...")
        print(f"  Running: {' '.join(cmd[-2:])}")

        try:
            result = subprocess.run(cmd, capture_output=False, text=True, timeout=300)

            if result.returncode == 0:
                print(f"  ✅ {season} ingested successfully")
            else:
                print(f"  ❌ {season} ingestion failed")

        except subprocess.TimeoutExpired:
            print(f"  ❌ {season} ingestion timed out")
        except Exception as e:
            print(f"  ❌ {season} ingestion error: {e}")

        print()

    print()


def validate_fix(dry_run: bool = False) -> None:
    """Validate that all issues are resolved

    Args:
        dry_run: If True, skip validation
    """
    if dry_run:
        return

    print("=" * 80)
    print("STEP 5: VALIDATION")
    print("=" * 80)
    print()

    import pandas as pd

    # Check index exists
    if not INDEX_FILE.exists():
        print("❌ Index file still missing")
        return

    # Load index
    df = pd.read_parquet(INDEX_FILE)

    # Check for synthetic IDs
    synthetic_count = df["game_id"].str.match(r"^LNB_\d{4}-\d{4}_\d+$").sum()
    if synthetic_count > 0:
        print(f"❌ Still has {synthetic_count} synthetic game IDs")
    else:
        print("✅ No synthetic game IDs")

    # Check season coverage
    print()
    print("Season coverage in index:")
    if "season" in df.columns:
        for season in sorted(df["season"].unique()):
            count = len(df[df["season"] == season])
            print(f"  {season}: {count} games")

    # Check fixture mappings match
    print()
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture_data = json.load(f)
        fixture_mappings = fixture_data.get("mappings", {})

    print("Expected coverage (from fixture file):")
    for season, uuids in sorted(fixture_mappings.items()):
        print(f"  {season}: {len(uuids)} games")

    print()
    print("=" * 80)
    print("FIX COMPLETE!")
    print("=" * 80)
    print()


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Fix game index and re-ingest missing data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--clean-slate",
        action="store_true",
        help="Remove ALL data and rebuild from scratch (aggressive cleanup)",
    )

    args = parser.parse_args()

    print()
    print("=" * 80)
    print("LNB DATA FIX - GAME INDEX AND MISSING DATA")
    print("=" * 80)
    print()

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
        print()

    if args.clean_slate:
        print("⚠️  CLEAN SLATE MODE - All data will be removed and rebuilt")
        print()

    # Step 1: Backup
    backup_data(dry_run=args.dry_run)

    # Step 2: Remove bad data
    if args.clean_slate:
        clean_slate_removal(dry_run=args.dry_run)
    else:
        remove_synthetic_games(dry_run=args.dry_run)

    # Step 3: Rebuild index
    rebuild_game_index(dry_run=args.dry_run)

    # Step 4: Ingest missing games
    ingest_missing_games(dry_run=args.dry_run)

    # Step 5: Validate
    validate_fix(dry_run=args.dry_run)

    print()
    print("[DONE]")


if __name__ == "__main__":
    main()
