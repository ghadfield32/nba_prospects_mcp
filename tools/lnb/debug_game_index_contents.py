#!/usr/bin/env python3
"""Debug Game Index Contents

Inspect the game index to see what games have been ingested
and identify the source of extra games.

Created: 2025-11-15
"""

import io
import sys
from pathlib import Path

import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")

print("=" * 80)
print("GAME INDEX CONTENTS")
print("=" * 80)
print()

if not INDEX_FILE.exists():
    print(f"❌ Index file does not exist: {INDEX_FILE}")
    sys.exit(1)

# Load index
df = pd.read_parquet(INDEX_FILE)

print(f"Total games in index: {len(df)}")
print()

print("Columns:")
for col in df.columns:
    print(f"  - {col}")
print()

print("=" * 80)
print("GAMES BY SEASON")
print("=" * 80)
print()

if "season" in df.columns:
    for season in sorted(df["season"].unique()):
        season_df = df[df["season"] == season]
        print(f"\n{season} ({len(season_df)} games):")
        print("-" * 80)

        # Show game_id column if it exists
        if "game_id" in df.columns:
            for idx, game_id in enumerate(season_df["game_id"].head(20), 1):
                # Truncate UUID if too long
                game_id_str = str(game_id)
                if len(game_id_str) > 50:
                    game_id_display = game_id_str[:47] + "..."
                else:
                    game_id_display = game_id_str

                print(f"  {idx:2d}. {game_id_display}")

            if len(season_df) > 20:
                print(f"  ... and {len(season_df) - 20} more")
else:
    print("⚠️  No 'season' column in index")

print()
print("=" * 80)
print("GAME ID PATTERNS")
print("=" * 80)
print()

if "game_id" in df.columns:
    # Check for UUID pattern (36 chars with hyphens)
    uuid_pattern_count = (
        df["game_id"]
        .str.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        .sum()
    )

    # Check for LNB_YYYY-YYYY_N pattern
    synthetic_pattern_count = df["game_id"].str.match(r"^LNB_\d{4}-\d{4}_\d+$").sum()

    print(f"UUID format (36-char hex):     {uuid_pattern_count} games")
    print(f"Synthetic format (LNB_...):    {synthetic_pattern_count} games")
    print(
        f"Other formats:                 {len(df) - uuid_pattern_count - synthetic_pattern_count} games"
    )
    print()

    if synthetic_pattern_count > 0:
        print("⚠️  WARNING: Found games with synthetic IDs (LNB_YYYY-YYYY_N)")
        print()
        print("These were likely created by:")
        print("  - A previous version of bulk_ingest_pbp_shots.py")
        print("  - Manual testing or development")
        print()
        print("RECOMMENDATION:")
        print("  These synthetic IDs should be replaced with actual UUIDs")
        print("  from fixture_uuids_by_season.json")

print()
print("=" * 80)
print("COMPARISON WITH fixture_uuids_by_season.json")
print("=" * 80)
print()

# Load fixture UUIDs
import json

fixture_file = Path("tools/lnb/fixture_uuids_by_season.json")

if fixture_file.exists():
    with open(fixture_file, encoding="utf-8") as f:
        fixture_data = json.load(f)
        fixture_mappings = fixture_data.get("mappings", {})

    print("Expected games from fixture_uuids_by_season.json:")
    for season in sorted(fixture_mappings.keys()):
        uuids = fixture_mappings[season]
        print(f"  {season}: {len(uuids)} UUIDs")

    print()
    print("Actual games in index:")
    if "season" in df.columns:
        for season in sorted(df["season"].unique()):
            count = len(df[df["season"] == season])
            print(f"  {season}: {count} games")

    print()
    print("=" * 80)
    print("MISSING GAMES (in fixture file but not in index)")
    print("=" * 80)
    print()

    if "game_id" in df.columns:
        for season, expected_uuids in fixture_mappings.items():
            if season in df["season"].values:
                actual_game_ids = set(df[df["season"] == season]["game_id"].tolist())
                missing = [uuid for uuid in expected_uuids if uuid not in actual_game_ids]

                if missing:
                    print(f"{season}:")
                    for uuid in missing:
                        print(f"  - {uuid}")
                    print()
            else:
                # Entire season missing
                print(f"{season} (entire season missing):")
                for uuid in expected_uuids:
                    print(f"  - {uuid}")
                print()
else:
    print(f"❌ Fixture file not found: {fixture_file}")

print("[DONE]")
