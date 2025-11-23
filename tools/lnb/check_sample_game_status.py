#!/usr/bin/env python3
"""Check status of sample games that were being fetched"""

import pandas as pd

df = pd.read_parquet("data/raw/lnb/lnb_game_index.parquet")

sample_ids = [
    "152b2122-67e6-11f0-a6bf-9d1d3a927139",
    "15326348-67e6-11f0-9d78-9d1d3a927139",
    "15397c6c-67e6-11f0-a7e1-9d1d3a927139",
]

print("Sample games being fetched by ingestion:")
print("=" * 70)

for gid in sample_ids:
    game = df[df["game_id"] == gid]
    if len(game) > 0:
        row = game.iloc[0]
        print(f"\n{gid[:16]}...")
        print(f"  Competition: {row['competition']}")
        print(f"  Season: {row['season']}")
        print(f"  Date: {row['game_date']}")
        print(f"  Status: {row['status']}")
        print(f"  Teams: {row['home_team_name']} vs {row['away_team_name']}")
    else:
        print(f"\n{gid}: NOT FOUND IN INDEX")
