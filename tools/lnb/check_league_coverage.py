#!/usr/bin/env python3
"""Check which leagues actually have data files on disk"""

from pathlib import Path

import pandas as pd

# Load index
df_index = pd.read_parquet("data/raw/lnb/lnb_game_index.parquet")

# Get all PBP file game IDs
pbp_dir = Path("data/raw/lnb/pbp")
pbp_game_ids = {f.stem.replace("game_id=", "") for f in pbp_dir.rglob("*.parquet")}

# Cross-reference with index
games_with_files = df_index[df_index["game_id"].isin(pbp_game_ids)]

print("=" * 70)
print("  LEAGUE COVERAGE - Files on Disk vs Index")
print("=" * 70)

print("\nGames with PBP files on disk by competition:")
coverage = games_with_files.groupby("competition").size().reset_index(name="files_on_disk")
index_counts = df_index.groupby("competition").size().reset_index(name="total_in_index")
merged = coverage.merge(index_counts, on="competition", how="outer").fillna(0)
merged["coverage_pct"] = (merged["files_on_disk"] / merged["total_in_index"] * 100).round(1)

for _, row in merged.iterrows():
    print(
        f"{row['competition']:20} | {int(row['files_on_disk']):4} files | {int(row['total_in_index']):4} total | {row['coverage_pct']:5.1f}%"
    )

print(f"\nTotal games with files: {len(games_with_files)}")
print(f"Total PBP files on disk: {len(pbp_game_ids)}")
print(f"Total games in index: {len(df_index)}")

# Check LEAGUE column for each competition
print(f'\n{"="*70}')
print("  LEAGUE Column Values by Competition")
print("=" * 70)

for comp in sorted(df_index["competition"].unique()):
    comp_games = df_index[df_index["competition"] == comp]
    comp_files = comp_games[comp_games["game_id"].isin(pbp_game_ids)]

    if len(comp_files) > 0:
        # Sample first file
        first_game_id = comp_files.iloc[0]["game_id"]
        file_path = list(pbp_dir.rglob(f"*{first_game_id}*.parquet"))[0]
        df_sample = pd.read_parquet(file_path)
        league_val = (
            df_sample["LEAGUE"].iloc[0] if "LEAGUE" in df_sample.columns else "NO LEAGUE COLUMN"
        )
        print(f"\n{comp}:")
        print(f"  Files on disk: {len(comp_files)}")
        print(f"  Sample LEAGUE value: {league_val}")
        print(f"  Sample game_id: {first_game_id[:36]}...")
    else:
        print(f"\n{comp}:")
        print("  NO FILES ON DISK")
