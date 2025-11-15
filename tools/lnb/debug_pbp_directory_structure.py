#!/usr/bin/env python3
"""Debug PBP Directory Structure

This script inspects the actual directory structure of PBP data
to identify why create_normalized_tables.py can't find 2021-2022 and 2022-2023 data.

Expected structure (what create_normalized_tables.py looks for):
  data/raw/lnb/pbp/season=2021-2022/game_id=<UUID>.parquet
  data/raw/lnb/pbp/season=2022-2023/game_id=<UUID>.parquet
  data/raw/lnb/pbp/season=2023-2024/game_id=<UUID>.parquet
  data/raw/lnb/pbp/season=2024-2025/game_id=<UUID>.parquet

This script will:
1. List all subdirectories in data/raw/lnb/pbp/
2. Show files in each subdirectory
3. Compare with expected structure
4. Identify the mismatch

Created: 2025-11-15
"""

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Paths
PBP_DIR = Path("data/raw/lnb/pbp")
SHOTS_DIR = Path("data/raw/lnb/shots")

print("=" * 80)
print("PBP DIRECTORY STRUCTURE DEBUG")
print("=" * 80)
print()

# Check if PBP directory exists
if not PBP_DIR.exists():
    print(f"❌ PBP directory does not exist: {PBP_DIR}")
    print()
    print("RECOMMENDATION:")
    print("  Run bulk_ingest_pbp_shots.py to create PBP data")
    sys.exit(1)

print(f"✅ PBP directory exists: {PBP_DIR}")
print()

# List all subdirectories
print("=" * 80)
print("SUBDIRECTORIES IN data/raw/lnb/pbp/")
print("=" * 80)
print()

subdirs = sorted([d for d in PBP_DIR.iterdir() if d.is_dir()])

if not subdirs:
    print("❌ No subdirectories found!")
    print()
    print("Checking for files at root level...")
    root_files = list(PBP_DIR.glob("*.parquet"))
    if root_files:
        print(
            f"⚠️  Found {len(root_files)} parquet files at root level (should be in season subdirs)"
        )
        for f in root_files[:5]:
            print(f"  - {f.name}")
        if len(root_files) > 5:
            print(f"  ... and {len(root_files) - 5} more")
else:
    print(f"Found {len(subdirs)} subdirectories:")
    print()

    for subdir in subdirs:
        print(f"📁 {subdir.name}/")

        # Count files in this subdirectory
        parquet_files = list(subdir.glob("*.parquet"))

        if parquet_files:
            print(f"   ✅ {len(parquet_files)} parquet files")

            # Show first 3 file names
            for f in parquet_files[:3]:
                print(f"      - {f.name}")
            if len(parquet_files) > 3:
                print(f"      ... and {len(parquet_files) - 3} more")
        else:
            print("   ❌ No parquet files")

        print()

print()
print("=" * 80)
print("EXPECTED VS ACTUAL STRUCTURE")
print("=" * 80)
print()

# Expected seasons from fixture_uuids_by_season.json
expected_seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]

print("Expected subdirectory names (from create_normalized_tables.py):")
for season in expected_seasons:
    expected_dir = f"season={season}"
    actual_path = PBP_DIR / expected_dir

    if actual_path.exists():
        file_count = len(list(actual_path.glob("*.parquet")))
        print(f"  ✅ {expected_dir:<20s} EXISTS ({file_count} files)")
    else:
        print(f"  ❌ {expected_dir:<20s} MISSING")

print()
print("=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print()

# Check for common issues
missing_seasons = []
for season in expected_seasons:
    expected_dir = PBP_DIR / f"season={season}"
    if not expected_dir.exists():
        missing_seasons.append(season)

if missing_seasons:
    print("❌ ISSUE IDENTIFIED: Missing season directories")
    print()
    print(f"Missing seasons: {', '.join(missing_seasons)}")
    print()
    print("Possible causes:")
    print("  1. PBP data was never ingested for these seasons")
    print("  2. Data was ingested with different directory structure")
    print("  3. Ingestion script bug created wrong paths")
    print()
    print("RECOMMENDATIONS:")
    print()
    print("1. Check if PBP data exists elsewhere:")
    print(f"   ls -R {PBP_DIR}")
    print()
    print("2. Check the game index to see what's been ingested:")
    index_file = Path("data/raw/lnb/lnb_game_index.parquet")
    if index_file.exists():
        print(f"   Read {index_file} to see ingested games")

        # Try to read index
        try:
            import pandas as pd

            df = pd.read_parquet(index_file)
            print()
            print("   Index file contents:")
            if "season" in df.columns:
                season_counts = df["season"].value_counts().sort_index()
                for season, count in season_counts.items():
                    print(f"      {season}: {count} games")
            else:
                print(f"      Total games: {len(df)}")
                if len(df) > 0:
                    print(f"      Columns: {df.columns.tolist()}")
        except Exception as e:
            print(f"      [ERROR] Could not read index: {e}")
    else:
        print(f"   ❌ Index file does not exist: {index_file}")
    print()
    print("3. Re-ingest missing seasons:")
    for season in missing_seasons:
        print(f"   uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons {season}")
else:
    print("✅ All expected season directories exist!")

print()
print("=" * 80)
print("SHOTS DIRECTORY CHECK")
print("=" * 80)
print()

if SHOTS_DIR.exists():
    shots_subdirs = sorted([d for d in SHOTS_DIR.iterdir() if d.is_dir()])
    print(f"Shots directory: {len(shots_subdirs)} subdirectories")
    for subdir in shots_subdirs:
        file_count = len(list(subdir.glob("*.parquet")))
        print(f"  📁 {subdir.name:<20s} ({file_count} files)")
else:
    print(f"❌ Shots directory does not exist: {SHOTS_DIR}")

print()
print("[DONE]")
