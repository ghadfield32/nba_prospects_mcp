#!/usr/bin/env python3
"""Check how many games are in the past vs future in the game index"""

from datetime import date

import pandas as pd

df = pd.read_parquet("data/raw/lnb/lnb_game_index.parquet")

# Split by games with/without dates
df_with_dates = df[df["game_date"] != ""]
df_no_dates = df[df["game_date"] == ""]

# Split games with dates into past vs future
past_games = df_with_dates[pd.to_datetime(df_with_dates["game_date"]).dt.date <= date.today()]
future_games = df_with_dates[pd.to_datetime(df_with_dates["game_date"]).dt.date > date.today()]

print(f"Total games in index: {len(df)}")
print(f"\nGames WITH dates populated: {len(df_with_dates)}")
print(f"  - Past/today games (should have data): {len(past_games)}")
print(f"  - Future games (no data expected): {len(future_games)}")
print(f"\nGames WITHOUT dates: {len(df_no_dates)} (may or may not have data)")

print(f'\n{"="*60}')
print("PAST GAMES BY LEAGUE (candidates for ingestion):")
print(f'{"="*60}')
if len(past_games) > 0:
    print(past_games.groupby(["competition", "season"]).size().to_string())
else:
    print("No past games found!")

print(f'\n{"="*60}')
print("FUTURE GAMES BY LEAGUE (will be skipped):")
print(f'{"="*60}')
if len(future_games) > 0:
    print(future_games.groupby(["competition", "season"]).size().to_string())
else:
    print("No future games found!")

print(f'\n{"="*60}')
print("GAMES WITHOUT DATES BY LEAGUE:")
print(f'{"="*60}')
if len(df_no_dates) > 0:
    print(df_no_dates.groupby(["competition", "season"]).size().to_string())
else:
    print("All games have dates!")
