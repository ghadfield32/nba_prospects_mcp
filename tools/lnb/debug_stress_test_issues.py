#!/usr/bin/env python3
"""Debug script to diagnose stress test issues

This script investigates:
1. What values are actually in the game index "competition" column
2. Why league filtering returns 0 results
3. What the actual file structure looks like
4. Why only 2/446 games have data files

Created: 2025-11-20
Purpose: Root cause analysis for stress test failures
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from src.cbb_data.fetchers.lnb_league_config import (
    LEAGUE_METADATA_REGISTRY,
)

# Paths
DATA_DIR = Path("data/raw/lnb")
GAME_INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

print("=" * 80)
print("  DEBUG ANALYSIS: STRESS TEST ISSUES")
print("=" * 80)

# ==============================================================================
# STEP 1: Load and inspect game index
# ==============================================================================

print("\n[STEP 1] Loading game index...")
if not GAME_INDEX_FILE.exists():
    print(f"❌ Game index not found: {GAME_INDEX_FILE}")
    sys.exit(1)

index_df = pd.read_parquet(GAME_INDEX_FILE)
print(f"✅ Loaded index: {len(index_df)} total games")
print(f"   Columns: {list(index_df.columns)}")

# ==============================================================================
# STEP 2: Inspect competition column values
# ==============================================================================

print("\n[STEP 2] Analyzing 'competition' column values...")
if "competition" in index_df.columns:
    unique_competitions = index_df["competition"].unique()
    print(f"   Unique competition values: {len(unique_competitions)}")
    for comp in sorted(unique_competitions):
        count = len(index_df[index_df["competition"] == comp])
        print(f'     - "{comp}": {count} games')
else:
    print("   ❌ No 'competition' column found!")
    print(f"   Available columns: {list(index_df.columns)}")

# ==============================================================================
# STEP 3: Test league filtering logic
# ==============================================================================

print("\n[STEP 3] Testing league filtering logic...")

for league in ["betclic_elite", "elite_2", "espoirs_elite", "espoirs_prob"]:
    if league not in LEAGUE_METADATA_REGISTRY:
        continue

    display_name = LEAGUE_METADATA_REGISTRY[league]["display_name"]
    print(f"\n  League: {league}")
    print(f'  Display name from config: "{display_name}"')

    # Test exact match
    exact_match = index_df[index_df["competition"] == display_name]
    print(f"  Exact match: {len(exact_match)} games")

    # Test contains (case-sensitive)
    contains_match = index_df[
        index_df["competition"].str.contains(display_name, case=True, na=False)
    ]
    print(f"  Contains (case-sensitive): {len(contains_match)} games")

    # Test contains (case-insensitive) - what stress test uses
    contains_match_ci = index_df[
        index_df["competition"].str.contains(display_name, case=False, na=False)
    ]
    print(f"  Contains (case-insensitive): {len(contains_match_ci)} games")

    # Show sample of competition values that don't match
    if len(contains_match_ci) == 0 and "competition" in index_df.columns:
        print("  ⚠️  No matches! Sample competition values from index:")
        sample_comps = index_df["competition"].head(10).tolist()
        for comp in sample_comps:
            print(f'       "{comp}"')

# ==============================================================================
# STEP 4: Check season distribution
# ==============================================================================

print("\n[STEP 4] Checking season distribution...")
if "season" in index_df.columns:
    season_counts = index_df["season"].value_counts()
    print("   Games per season:")
    for season, count in season_counts.items():
        print(f"     {season}: {count} games")

# ==============================================================================
# STEP 5: Inspect file directory structure
# ==============================================================================

print("\n[STEP 5] Inspecting data directory structure...")

# Check PBP directory
print(f"\n  PBP directory: {PBP_DIR}")
if PBP_DIR.exists():
    season_dirs = list(PBP_DIR.glob("season=*"))
    print(f"  Found {len(season_dirs)} season directories:")
    for season_dir in season_dirs:
        parquet_files = list(season_dir.glob("game_id=*.parquet"))
        print(f"    {season_dir.name}: {len(parquet_files)} files")
else:
    print("  ❌ Directory doesn't exist")

# Check SHOTS directory
print(f"\n  SHOTS directory: {SHOTS_DIR}")
if SHOTS_DIR.exists():
    season_dirs = list(SHOTS_DIR.glob("season=*"))
    print(f"  Found {len(season_dirs)} season directories:")
    for season_dir in season_dirs:
        parquet_files = list(season_dir.glob("game_id=*.parquet"))
        print(f"    {season_dir.name}: {len(parquet_files)} files")
else:
    print("  ❌ Directory doesn't exist")

# ==============================================================================
# STEP 6: Sample a few game IDs and check file paths
# ==============================================================================

print("\n[STEP 6] Testing file path logic for sample games...")

sample_games = index_df.head(5)
for idx, row in sample_games.iterrows():
    game_id = row["game_id"]
    season = row["season"]
    competition = row.get("competition", "N/A")

    pbp_file = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
    shots_file = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

    print(f"\n  Game: {game_id[:16]}...")
    print(f"    Season: {season}")
    print(f"    Competition: {competition}")
    print(f"    PBP file: {pbp_file}")
    print(f"      Exists: {pbp_file.exists()}")
    print(f"    Shots file: {shots_file}")
    print(f"      Exists: {shots_file.exists()}")

# ==============================================================================
# SUMMARY
# ==============================================================================

print("\n" + "=" * 80)
print("  DIAGNOSIS SUMMARY")
print("=" * 80)

print("\n⚠️  FINDINGS:")
print("1. Check if 'competition' column values match expected display names")
print("2. Verify case sensitivity in filtering logic")
print("3. Confirm file structure matches expected paths")
print("4. Determine why only 2 games have data files")

print("\n💡 NEXT STEPS:")
print("1. Fix league filtering logic based on actual competition column values")
print("2. Add ZeroDivisionError protection in summary statistics")
print("3. Investigate why data ingestion didn't complete for 444 games")
print()
