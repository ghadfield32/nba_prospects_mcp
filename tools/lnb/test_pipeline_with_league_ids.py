#!/usr/bin/env python3
"""Test the updated ingestion pipeline with league ID mapping

This script tests a specific Espoirs ELITE game to verify that:
1. The competition → league ID mapping works
2. The fetchers receive the correct league_id parameter
3. The LEAGUE column in the fetched data has the correct value
"""

from __future__ import annotations

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

from src.cbb_data.fetchers.lnb import (
    fetch_lnb_play_by_play,
    fetch_lnb_shots,
    get_league_id_from_competition,
)

print("=" * 80)
print("  TEST: INGESTION PIPELINE WITH LEAGUE ID MAPPING")
print("=" * 80)

# Load game index
INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")
df_index = pd.read_parquet(INDEX_FILE)

# Find a past Espoirs ELITE game
espoirs_games = df_index[
    (df_index["competition"] == "Espoirs ELITE")
    & (df_index["season"] == "2023-2024")
    & (df_index["game_date"] < "2025-01-01")
].copy()

if espoirs_games.empty:
    print("\n[ERROR] No Espoirs ELITE games found in 2023-2024 season")
    sys.exit(1)

test_game = espoirs_games.iloc[0]

print("\nTest Game:")
print(f"  Game ID: {test_game['game_id']}")
print(f"  Competition: {test_game['competition']}")
print(f"  Season: {test_game['season']}")
print(f"  Date: {test_game['game_date']}")
print(f"  Teams: {test_game['home_team_name']} vs {test_game['away_team_name']}")

# Step 1: Test league ID mapping
print(f"\n{'-' * 80}")
print("STEP 1: Test competition → league ID mapping")
print(f"{'-' * 80}")

league_id = get_league_id_from_competition(test_game["competition"])
print(f"Competition: '{test_game['competition']}'")
print(f"Mapped to league ID: '{league_id}'")
print("Expected: 'LNB_ESPOIRS_ELITE'")

if league_id == "LNB_ESPOIRS_ELITE":
    print("✅ Mapping correct!")
else:
    print(f"❌ Mapping incorrect! Got '{league_id}'")
    sys.exit(1)

# Step 2: Test PBP fetch with league ID
print(f"\n{'-' * 80}")
print("STEP 2: Test PBP fetch with league ID parameter")
print(f"{'-' * 80}")

try:
    pbp_df = fetch_lnb_play_by_play(test_game["game_id"], league_id=league_id)

    if pbp_df.empty:
        print("⚠️  PBP data is empty (game may not have data yet)")
    else:
        print(f"✅ Fetched {len(pbp_df)} PBP events")

        # Check LEAGUE column
        if "LEAGUE" in pbp_df.columns:
            league_val = pbp_df["LEAGUE"].iloc[0]
            print(f"   LEAGUE column value: '{league_val}'")

            if league_val == "LNB_ESPOIRS_ELITE":
                print("   ✅ LEAGUE column correct!")
            else:
                print(
                    f"   ❌ LEAGUE column incorrect! Expected 'LNB_ESPOIRS_ELITE', got '{league_val}'"
                )
        else:
            print("   ❌ No LEAGUE column in data!")

except Exception as e:
    print(f"❌ Error fetching PBP: {e}")

# Step 3: Test shots fetch with league ID
print(f"\n{'-' * 80}")
print("STEP 3: Test shots fetch with league ID parameter")
print(f"{'-' * 80}")

try:
    shots_df = fetch_lnb_shots(test_game["game_id"], league_id=league_id)

    if shots_df.empty:
        print("⚠️  Shots data is empty (game may not have data yet)")
    else:
        print(f"✅ Fetched {len(shots_df)} shots")

        # Check LEAGUE column
        if "LEAGUE" in shots_df.columns:
            league_val = shots_df["LEAGUE"].iloc[0]
            print(f"   LEAGUE column value: '{league_val}'")

            if league_val == "LNB_ESPOIRS_ELITE":
                print("   ✅ LEAGUE column correct!")
            else:
                print(
                    f"   ❌ LEAGUE column incorrect! Expected 'LNB_ESPOIRS_ELITE', got '{league_val}'"
                )
        else:
            print("   ❌ No LEAGUE column in data!")

except Exception as e:
    print(f"❌ Error fetching shots: {e}")

# Step 4: Test mapping for all competitions
print(f"\n{'-' * 80}")
print("STEP 4: Test mapping for all competitions in index")
print(f"{'-' * 80}")

all_competitions = sorted(df_index["competition"].unique())
print("\nCompetitions in index:")
for comp in all_competitions:
    league_id = get_league_id_from_competition(comp)
    print(f"  '{comp}' → '{league_id}'")

print(f"\n{'=' * 80}")
print("  TEST COMPLETE")
print(f"{'=' * 80}\n")
