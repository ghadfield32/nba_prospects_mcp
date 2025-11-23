#!/usr/bin/env python3
"""Audit LNB league names and data coverage across all competitions

Checks:
1. League name normalization across seasons (Pro A → Betclic ELITE, etc.)
2. Data coverage for PBP, shots, box score per league/season
3. Naming consistency in index vs fetched data

LNB Competition Canonical IDs:
- LNB_PROA (Betclic ELITE, formerly Pro A / Jeep Élite)
- LNB_ELITE2 (ELITE 2, formerly Pro B)
- LNB_ESPOIRS_ELITE (Espoirs ELITE, U21 tier 1)
- LNB_ESPOIRS_PROB (Espoirs PROB / Espoirs ELITE 2, U21 tier 2)
"""

from pathlib import Path

import pandas as pd

# Load game index
INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")
PBP_DIR = Path("data/raw/lnb/pbp")
SHOTS_DIR = Path("data/raw/lnb/shots")

print("=" * 80)
print("  LNB LEAGUE NAMES & DATA COVERAGE AUDIT")
print("=" * 80)

# Load index
df = pd.read_parquet(INDEX_FILE)

print("\nGAME INDEX OVERVIEW")
print(f"Total games: {len(df)}")
print(f"Seasons: {sorted(df['season'].unique())}")
print(f"Competitions: {sorted(df['competition'].unique())}")

# League name analysis
print("\n" + "=" * 80)
print("1. LEAGUE NAME DISTRIBUTION")
print("=" * 80)

print("\nGames per competition per season:")
comp_season = df.groupby(["competition", "season"]).size().reset_index(name="games")
for _, row in comp_season.iterrows():
    print(f"  {row['competition']:20} | {row['season']:10} | {row['games']:4} games")

# Check for naming inconsistencies
print(f"\n{'='*80}")
print("2. NAMING CONSISTENCY ANALYSIS")
print(f"{'='*80}")

# Identify potential aliases
print("\nPotential name standardization needed:")
comp_names = df["competition"].unique()
issues = []

# Check for Pro A / Betclic ELITE consistency
proa_variants = [
    c
    for c in comp_names
    if "Betclic" in c
    or "Pro A" in c
    or ("ELITE" in c and "ELITE 2" not in c and "Espoirs" not in c)
]
if len(proa_variants) > 1:
    issues.append(f"  WARNING: Tier 1 has multiple names: {proa_variants}")
    issues.append("      -> Should normalize to canonical 'Betclic ELITE'")

# Check for Pro B / ELITE 2 consistency
prob_variants = [
    c for c in comp_names if "Pro B" in c or "ELITE 2" in c or ("PROB" in c and "Espoirs" not in c)
]
if len(prob_variants) > 1:
    issues.append(f"  WARNING: Tier 2 has multiple names: {prob_variants}")
    issues.append("      -> Should normalize to canonical 'ELITE 2'")

# Check Espoirs naming
espoirs_variants = [c for c in comp_names if "Espoirs" in c]
if espoirs_variants:
    print(f"  INFO: Espoirs leagues: {espoirs_variants}")

if not issues:
    print("  OK: League names are consistent!")
else:
    for issue in issues:
        print(issue)

# Data coverage analysis
print(f"\n{'='*80}")
print("3. DATA COVERAGE BY LEAGUE/SEASON")
print(f"{'='*80}")

# Check flags in index
print("\nData availability flags from index:")
coverage = (
    df.groupby(["competition", "season"])
    .agg({"game_id": "count", "has_pbp": "sum", "has_shots": "sum", "has_boxscore": "sum"})
    .reset_index()
)
coverage.columns = ["competition", "season", "total_games", "pbp_count", "shots_count", "box_count"]

for _, row in coverage.iterrows():
    print(f"\n{row['competition']} - {row['season']}:")
    print(f"  Total games: {row['total_games']}")
    print(f"  Has PBP:     {row['pbp_count']:4} ({row['pbp_count']/row['total_games']*100:5.1f}%)")
    print(
        f"  Has Shots:   {row['shots_count']:4} ({row['shots_count']/row['total_games']*100:5.1f}%)"
    )
    print(f"  Has Box:     {row['box_count']:4} ({row['box_count']/row['total_games']*100:5.1f}%)")

# Check actual parquet files on disk
print(f"\n{'='*80}")
print("4. ACTUAL PARQUET FILES ON DISK")
print(f"{'='*80}")

pbp_files = list(PBP_DIR.rglob("*.parquet"))
shots_files = list(SHOTS_DIR.rglob("*.parquet"))

print(f"\nPBP parquet files: {len(pbp_files)}")
print(f"Shots parquet files: {len(shots_files)}")

# Count by season
if pbp_files:
    pbp_by_season = {}
    for f in pbp_files:
        season = f.parent.name.replace("season=", "")
        pbp_by_season[season] = pbp_by_season.get(season, 0) + 1

    print("\nPBP files by season:")
    for season in sorted(pbp_by_season.keys()):
        print(f"  {season}: {pbp_by_season[season]} files")

if shots_files:
    shots_by_season = {}
    for f in shots_files:
        season = f.parent.name.replace("season=", "")
        shots_by_season[season] = shots_by_season.get(season, 0) + 1

    print("\nShots files by season:")
    for season in sorted(shots_by_season.keys()):
        print(f"  {season}: {shots_by_season[season]} files")

# Sample a few parquet files to check LEAGUE column
print(f"\n{'='*80}")
print("5. LEAGUE COLUMN IN FETCHED DATA")
print(f"{'='*80}")

if pbp_files:
    print("\nChecking LEAGUE column in PBP data (sample 3 files):")
    for f in pbp_files[:3]:
        try:
            sample_df = pd.read_parquet(f)
            if "LEAGUE" in sample_df.columns:
                league_val = sample_df["LEAGUE"].iloc[0] if len(sample_df) > 0 else "EMPTY"
                print(f"  {f.name[:30]:30} -> LEAGUE='{league_val}'")
            else:
                print(f"  {f.name[:30]:30} -> WARNING: No LEAGUE column")
        except Exception as e:
            print(f"  {f.name[:30]:30} -> Error: {e}")

# Recommendations
print(f"\n{'='*80}")
print("6. RECOMMENDATIONS")
print(f"{'='*80}")

print("\nCOMPLETED:")
print("  - Multi-league game index built (4 leagues)")
print("  - PBP and shots ingestion pipeline functional")
print("  - League-specific UUID discovery working")

print("\nTODO FOR FULL COVERAGE:")
print("  1. Complete ingestion for all 1,048 past games (currently running)")
print("  2. Add box score fetching (currently has_boxscore=0 for all)")
print("  3. Verify LEAGUE column normalization:")
print("     - LNB_PROA (Betclic ELITE)")
print("     - LNB_ELITE2 (ELITE 2)")
print("     - LNB_ESPOIRS_ELITE (Espoirs ELITE)")
print("     - LNB_ESPOIRS_PROB (Espoirs PROB)")
print("  4. Discover remaining Elite2/Espoirs historical seasons (2022-23, etc.)")

print()
