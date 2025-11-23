#!/usr/bin/env python3
"""Update game index has_pbp/has_shots flags by scanning filesystem"""

from pathlib import Path

import pandas as pd

# Paths
INDEX_PATH = Path("data/raw/lnb/lnb_game_index.parquet")
PBP_DIR = Path("data/raw/lnb/pbp")
SHOTS_DIR = Path("data/raw/lnb/shots")

print("=" * 80)
print("  UPDATE INDEX FLAGS FROM DISK")
print("=" * 80)

# Load index
print(f"\n[INFO] Loading index from {INDEX_PATH}")
index_df = pd.read_parquet(INDEX_PATH)
print(f"[INFO] Loaded {len(index_df)} games")

# Scan PBP files
print(f"\n[SCANNING] PBP files in {PBP_DIR}")
pbp_games = set()
for season_dir in PBP_DIR.glob("season=*"):
    for pbp_file in season_dir.glob("game_id=*.parquet"):
        game_id = pbp_file.stem.replace("game_id=", "")
        pbp_games.add(game_id)

print(f"[INFO] Found {len(pbp_games)} PBP files")

# Scan shots files
print(f"\n[SCANNING] Shots files in {SHOTS_DIR}")
shots_games = set()
for season_dir in SHOTS_DIR.glob("season=*"):
    for shots_file in season_dir.glob("game_id=*.parquet"):
        game_id = shots_file.stem.replace("game_id=", "")
        shots_games.add(game_id)

print(f"[INFO] Found {len(shots_games)} shots files")

# Update flags
print("\n[UPDATING] Index flags")
index_df["has_pbp"] = index_df["game_id"].isin(pbp_games)
index_df["has_shots"] = index_df["game_id"].isin(shots_games)

# Show stats
pbp_count = index_df["has_pbp"].sum()
shots_count = index_df["has_shots"].sum()
both_count = (index_df["has_pbp"] & index_df["has_shots"]).sum()

print("\n[STATS] Updated flags:")
print(f"  has_pbp:  {pbp_count}/{len(index_df)} ({pbp_count/len(index_df)*100:.1f}%)")
print(f"  has_shots: {shots_count}/{len(index_df)} ({shots_count/len(index_df)*100:.1f}%)")
print(f"  Both:     {both_count}/{len(index_df)} ({both_count/len(index_df)*100:.1f}%)")

# Save updated index
print(f"\n[SAVING] Updated index to {INDEX_PATH}")
index_df.to_parquet(INDEX_PATH, index=False)

print("\n" + "=" * 80)
print("  UPDATE COMPLETE")
print("=" * 80)
