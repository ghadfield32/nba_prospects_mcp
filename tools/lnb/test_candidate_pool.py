#!/usr/bin/env python3
"""Quick test of candidate pool builder"""

from reconstruct_lnb_uuids import build_candidate_pool

# Test building candidate pool for 2024-2025 ELITE 2 (should have full coverage)
print("Testing candidate pool builder for 2024-2025 elite_2...")
df = build_candidate_pool("2024-2025", "elite_2", force_rebuild=True)

print("\nResults:")
print(f"  Total candidates: {len(df)}")
if len(df) > 0:
    print(f"  Date range: {df['game_date'].min()} to {df['game_date'].max()}")
    print("\n  Sample teams (first 5):")
    for i in range(min(5, len(df))):
        row = df.iloc[i]
        print(f"    {row['game_date']}: {row['home_team']} vs {row['away_team']}")
    print("\n  Normalized sample (first 3):")
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        print(f"    Home: '{row['home_team']}' -> '{row['home_norm']}'")
        print(f"    Away: '{row['away_team']}' -> '{row['away_norm']}'")
else:
    print("  No candidates found!")
