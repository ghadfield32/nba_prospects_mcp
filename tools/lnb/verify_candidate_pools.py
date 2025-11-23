#!/usr/bin/env python3
"""Verify candidate pool builder for both historical Pro B seasons"""

from reconstruct_lnb_uuids import build_candidate_pool

seasons = ["2022-2023", "2023-2024"]

for season in seasons:
    print(f"\n{'='*60}")
    print(f"Testing {season} elite_2")
    print("=" * 60)

    try:
        df = build_candidate_pool(season, "elite_2", force_rebuild=True)
        print(f"\n[SUCCESS] {len(df)} candidates retrieved")

        if len(df) > 0:
            print(f"Date range: {df['game_date'].min()} to {df['game_date'].max()}")
            unique_teams = set(df["home_team"].tolist() + df["away_team"].tolist())
            print(f"Unique teams: {len(unique_teams)}")
            if len(unique_teams) < 50:
                print(f"Teams: {sorted(unique_teams)}")
    except Exception as e:
        print(f"\n[FAILED] {e}")
