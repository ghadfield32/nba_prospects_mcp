#!/usr/bin/env python
"""Audit current gold table status and compare to plan."""

import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "src")
from pathlib import Path

import pandas as pd

GOLD_PATH = Path("data/gold/player_career_game.parquet")

print("=" * 70)
print("GOLD TABLE STATUS AUDIT")
print("=" * 70)

gold = pd.read_parquet(GOLD_PATH)
print(f"\nTotal rows: {len(gold):,}")
print(f"Unique players (NAME_KEY): {gold['NAME_KEY'].nunique():,}")
print(f"PLAYER_UID coverage: {gold['PLAYER_UID'].notna().mean():.1%}")

print("\n" + "=" * 70)
print("LEAGUE BREAKDOWN")
print("=" * 70)
print(
    f"\n{'League':<15} {'Rows':>10} {'Players':>10} {'Seasons':>8} {'Min Season':<12} {'Max Season':<12}"
)
print("-" * 70)

for league in sorted([lg for lg in gold["LEAGUE"].unique() if lg is not None]):
    league_df = gold[gold["LEAGUE"] == league]
    rows = len(league_df)
    players = league_df["NAME_KEY"].nunique()
    seasons = league_df["SEASON"].nunique()
    min_season = league_df["SEASON"].min()
    max_season = league_df["SEASON"].max()
    print(f"{league:<15} {rows:>10,} {players:>10,} {seasons:>8} {min_season:<12} {max_season:<12}")

print("\n" + "=" * 70)
print("VALIDATION PLAYER CHECK")
print("=" * 70)

validation_players = [
    ("luka_doncic", ["ACB", "EUROLEAGUE"]),
    ("lamelo_ball", ["NBL"]),
    ("jalen_green", ["G_LEAGUE"]),
    ("paolo_banchero", ["NCAA_MBB"]),
    ("victor_wembanyama", ["LNB_PROA"]),
    ("nikola_jokic", ["ABA"]),
    ("scoot_henderson", ["G_LEAGUE"]),
]

print()
for name_key, expected_leagues in validation_players:
    player_df = gold[gold["NAME_KEY"].str.contains(name_key, case=False, na=False)]
    if len(player_df) > 0:
        leagues_found = sorted(player_df["LEAGUE"].unique())
        seasons = sorted(player_df["SEASON"].unique())
        games = len(player_df)
        expected_ok = all(lg in leagues_found for lg in expected_leagues)
        status = "✅" if expected_ok else "⚠️"
        print(f"{status} {name_key}: {games} games in {leagues_found}")
        print(f"   Seasons: {seasons[:5]}{'...' if len(seasons) > 5 else ''}")
    else:
        print(f"❌ {name_key}: NOT FOUND")

print("\n" + "=" * 70)
print("UPDATED LEAGUE JOIN-READINESS MATRIX")
print("=" * 70)

expected_matrix = {
    "NBL": {"target_seasons": "2015-2026", "validation_player": "LaMelo Ball"},
    "LNB_PROA": {"target_seasons": "2021-2026", "validation_player": "Victor Wembanyama"},
    "ABA": {"target_seasons": "2013-2025", "validation_player": "Nikola Jokic"},
    "EUROLEAGUE": {"target_seasons": "2007-2025", "validation_player": "Luka Doncic"},
    "ACB": {"target_seasons": "2015-2024", "validation_player": "Luka Doncic"},
    "G_LEAGUE": {"target_seasons": "2015-2025", "validation_player": "Jalen Green"},
    "NCAA_MBB": {"target_seasons": "2015-2025", "validation_player": "Paolo Banchero"},
    "CEBL": {"target_seasons": "2019-2025", "validation_player": "TBD"},
    "OTE": {"target_seasons": "2022-2025", "validation_player": "Alex Sarr"},
    "BCL": {"target_seasons": "2016-2025", "validation_player": "Alperen Sengun"},
}

print()
print(f"{'League':<12} {'Status':<20} {'Coverage':<25} {'Action Needed'}")
print("-" * 80)

for league, _info in expected_matrix.items():
    league_df = gold[gold["LEAGUE"] == league]
    if len(league_df) > 0:
        seasons = league_df["SEASON"].nunique()
        season_range = f"{league_df['SEASON'].min()}-{league_df['SEASON'].max()}"
        rows = len(league_df)
        status = "✅ IN GOLD"
        coverage = f"{rows:,} rows, {seasons} seasons"
        action = "None" if seasons >= 5 else "Backfill older seasons"
    else:
        status = "❌ MISSING"
        coverage = "0 rows"
        action = "Build canonical + add to gold"
    print(f"{league:<12} {status:<20} {coverage:<25} {action}")

print()
