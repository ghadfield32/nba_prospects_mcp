#!/usr/bin/env python3
"""Debug Current Index State After Failed Fix

This script inspects the game index after the fix attempt to understand
why it still has issues.

Created: 2025-11-15
"""

import io
import json
import sys
from pathlib import Path

import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")

print("=" * 80)
print("CURRENT INDEX STATE AFTER FIX ATTEMPT")
print("=" * 80)
print()

if not INDEX_FILE.exists():
    print(f"❌ Index file does not exist: {INDEX_FILE}")
    sys.exit(1)

# Load index
df = pd.read_parquet(INDEX_FILE)

print(f"Total games in index: {len(df)}")
print()

print("=" * 80)
print("ISSUE #1: SEASON NAMES")
print("=" * 80)
print()

if "season" in df.columns:
    unique_seasons = sorted(df["season"].unique())
    print(f"Unique season values ({len(unique_seasons)} total):")
    for season in unique_seasons:
        count = len(df[df["season"] == season])
        # Check if season name contains commas (malformed)
        if "," in season:
            print(f"  ❌ MALFORMED: '{season}' ({count} games)")
        else:
            print(f"  ✅ OK: {season} ({count} games)")
    print()

    # Analyze malformed season
    malformed_seasons = [s for s in unique_seasons if "," in s]
    if malformed_seasons:
        print("DIAGNOSIS:")
        print("  The build_game_index.py script was called with:")
        print("    --seasons 2021-2022,2022-2023,2023-2024,2024-2025")
        print()
        print("  But it interpreted this as a SINGLE season name!")
        print("  Expected: 4 separate seasons")
        print(f"  Actual: 1 season named '{malformed_seasons[0]}'")
        print()

print("=" * 80)
print("ISSUE #2: SYNTHETIC GAME IDs")
print("=" * 80)
print()

if "game_id" in df.columns:
    # Check for synthetic IDs (LNB_YYYY-YYYY_N pattern)
    synthetic_mask = df["game_id"].str.match(r"^LNB_\d{4}-\d{4}_\d+$", na=False)
    synthetic_count = synthetic_mask.sum()

    if synthetic_count > 0:
        print(f"❌ Found {synthetic_count} synthetic game IDs still in index")
        print()

        # Show which seasons
        synthetic_df = df[synthetic_mask]
        if "season" in synthetic_df.columns:
            for season in synthetic_df["season"].unique():
                season_count = len(synthetic_df[synthetic_df["season"] == season])
                print(f"  {season}: {season_count} synthetic IDs")

        print()
        print("DIAGNOSIS:")
        print("  The synthetic files were removed from disk (Step 2)")
        print("  But the index was rebuilt (Step 3) BEFORE removing them")
        print("  So the index still references the deleted files")
    else:
        print("✅ No synthetic game IDs in index")

print()
print("=" * 80)
print("ISSUE #3: EXPECTED vs. ACTUAL UUIDS")
print("=" * 80)
print()

# Load fixture file
fixture_file = Path("tools/lnb/fixture_uuids_by_season.json")
if fixture_file.exists():
    with open(fixture_file, encoding="utf-8") as f:
        fixture_data = json.load(f)
        fixture_mappings = fixture_data.get("mappings", {})

    print("Expected UUIDs from fixture_uuids_by_season.json:")
    for season in sorted(fixture_mappings.keys()):
        uuids = fixture_mappings[season]
        print(f"  {season}: {len(uuids)} UUIDs")
        for uuid in uuids[:3]:
            print(f"    - {uuid[:35]}...")
        if len(uuids) > 3:
            print(f"    ... and {len(uuids) - 3} more")
    print()

    print("Actual UUIDs in index:")
    if "game_id" in df.columns:
        # Filter to real UUIDs only (not synthetic)
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        real_uuid_mask = df["game_id"].str.match(uuid_pattern, na=False)
        real_uuids_df = df[real_uuid_mask]

        if "season" in real_uuids_df.columns:
            # Group by season
            for season in sorted(real_uuids_df["season"].unique()):
                season_df = real_uuids_df[real_uuids_df["season"] == season]
                game_ids = season_df["game_id"].tolist()

                print(f"  {season}: {len(game_ids)} UUIDs")
                for game_id in game_ids[:3]:
                    print(f"    - {game_id[:35]}...")
                if len(game_ids) > 3:
                    print(f"    ... and {len(game_ids) - 3} more")
        print()

        # Check for mismatches
        print("CHECKING FOR MISSING UUIDS:")
        for expected_season, expected_uuids in sorted(fixture_mappings.items()):
            # Find this season in the index (accounting for malformed names)
            matching_seasons = [s for s in real_uuids_df["season"].unique() if expected_season in s]

            if not matching_seasons:
                print(f"  ❌ {expected_season}: Season not found in index!")
                for uuid in expected_uuids:
                    print(f"      Missing: {uuid[:35]}...")
            else:
                # Check if UUIDs match
                for index_season in matching_seasons:
                    actual_uuids = set(
                        real_uuids_df[real_uuids_df["season"] == index_season]["game_id"].tolist()
                    )
                    expected_set = set(expected_uuids)

                    missing = expected_set - actual_uuids
                    extra = actual_uuids - expected_set

                    if missing or extra:
                        print(f"  ⚠️  {expected_season} (as '{index_season}'):")
                        if missing:
                            print(f"      Missing {len(missing)} UUIDs:")
                            for uuid in list(missing)[:3]:
                                print(f"        - {uuid[:35]}...")
                        if extra:
                            print(f"      Extra {len(extra)} UUIDs:")
                            for uuid in list(extra)[:3]:
                                print(f"        - {uuid[:35]}...")
                    else:
                        print(f"  ✅ {expected_season}: All UUIDs present")

print()
print("=" * 80)
print("ROOT CAUSES IDENTIFIED")
print("=" * 80)
print()

print("1. build_game_index.py argument parsing bug:")
print("   - Received: --seasons 2021-2022,2022-2023,2023-2024,2024-2025")
print("   - Interpreted as: Single season named '2021-2022,2022-2023,2023-2024,2024-2025'")
print("   - Should be: 4 separate seasons")
print()

print("2. Index rebuild happened before synthetic ID removal:")
print("   - Step 3 (rebuild index) ran before Step 2 (remove synthetic)")
print("   - Or: build_game_index.py reloaded old index and merged synthetic IDs back")
print()

print("3. bulk_ingest_pbp_shots.py filtering bug:")
print("   - Filters for exact season match: 'season == 2021-2022'")
print("   - But index has: 'season == 2021-2022,2022-2023,2023-2024,2024-2025'")
print("   - Result: 0 games filtered")
print()

print("[DONE]")
