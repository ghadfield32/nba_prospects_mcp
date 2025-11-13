"""Create sample NZ-NBL game index

This script creates a sample game index for NZ-NBL with placeholder game IDs.
In production, these would be real FIBA game IDs collected from nznbl.basketball or FIBA LiveStats.
"""

import pandas as pd
from datetime import datetime, timedelta

# Sample NZ-NBL games for 2024 season
# Note: These are placeholder IDs. Real implementation would scrape from nznbl.basketball
games = [
    {
        "SEASON": "2024",
        "GAME_ID": "12345",  # Placeholder FIBA game ID
        "GAME_DATE": datetime(2024, 4, 15, 19, 30),
        "HOME_TEAM": "Auckland Tuatara",
        "AWAY_TEAM": "Wellington Saints",
        "HOME_SCORE": 95,
        "AWAY_SCORE": 88,
    },
    {
        "SEASON": "2024",
        "GAME_ID": "12346",
        "GAME_DATE": datetime(2024, 4, 16, 19, 30),
        "HOME_TEAM": "Canterbury Rams",
        "AWAY_TEAM": "Otago Nuggets",
        "HOME_SCORE": 102,
        "AWAY_SCORE": 97,
    },
    {
        "SEASON": "2024",
        "GAME_ID": "12347",
        "GAME_DATE": datetime(2024, 4, 17, 19, 30),
        "HOME_TEAM": "Manawatu Jets",
        "AWAY_TEAM": "Taranaki Mountainairs",
        "HOME_SCORE": 89,
        "AWAY_SCORE": 91,
    },
    {
        "SEASON": "2024",
        "GAME_ID": "12348",
        "GAME_DATE": datetime(2024, 4, 18, 19, 30),
        "HOME_TEAM": "Hawke's Bay Hawks",
        "AWAY_TEAM": "Southland Sharks",
        "HOME_SCORE": 78,
        "AWAY_SCORE": 82,
    },
    {
        "SEASON": "2024",
        "GAME_ID": "12349",
        "GAME_DATE": datetime(2024, 4, 19, 19, 30),
        "HOME_TEAM": "Nelson Giants",
        "AWAY_TEAM": "Franklin Bulls",
        "HOME_SCORE": 94,
        "AWAY_SCORE": 90,
    },
]

# Create DataFrame
df = pd.DataFrame(games)

# Convert date to datetime
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Save to Parquet
output_path = "data/nz_nbl_game_index.parquet"
df.to_parquet(output_path, index=False)

print(f"Created NZ-NBL game index: {output_path}")
print(f"Total games: {len(df)}")
print("\nSample games:")
print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())
print("\nNote: Game IDs are placeholders. Real IDs must be collected from nznbl.basketball or FIBA LiveStats.")
