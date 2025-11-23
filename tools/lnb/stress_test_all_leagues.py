#!/usr/bin/env python3
"""Comprehensive multi-league stress test for LNB data coverage

Validates:
1. Data coverage for all 4 LNB leagues (Betclic ELITE, ELITE 2, Espoirs ELITE, Espoirs PROB)
2. All dataset types (PBP, shots, box score)
3. LEAGUE column values are correct
4. Identifies gaps and provides actionable recommendations
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

print("=" * 80)
print("  MULTI-LEAGUE STRESS TEST: LNB DATA COVERAGE")
print("=" * 80)

# Load game index
INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")
PBP_DIR = Path("data/raw/lnb/pbp")
SHOTS_DIR = Path("data/raw/lnb/shots")

df_index = pd.read_parquet(INDEX_FILE)

print("\nGAME INDEX OVERVIEW")
print(f"Total games: {len(df_index)}")
print(f"Seasons: {sorted(df_index['season'].unique())}")
print(f"Competitions: {sorted(df_index['competition'].unique())}")

# Expected canonical league IDs
EXPECTED_LEAGUE_IDS = {
    "Betclic ELITE": "LNB_PROA",
    "ELITE 2": "LNB_ELITE2",
    "ELITE 2 (PROB)": "LNB_ELITE2",
    "Espoirs ELITE": "LNB_ESPOIRS_ELITE",
    "Espoirs PROB": "LNB_ESPOIRS_PROB",
}

# Get actual files on disk
pbp_files = {f.stem.replace("game_id=", ""): f for f in PBP_DIR.rglob("*.parquet")}
shots_files = {f.stem.replace("game_id=", ""): f for f in SHOTS_DIR.rglob("*.parquet")}

print("\nACTUAL FILES ON DISK")
print(f"PBP files: {len(pbp_files)}")
print(f"Shots files: {len(shots_files)}")

# Split games by past/future
today = pd.Timestamp.today()
df_index["game_datetime"] = pd.to_datetime(df_index["game_date"])
past_games = df_index[df_index["game_datetime"] <= today].copy()
future_games = df_index[df_index["game_datetime"] > today].copy()

print("\nGAME STATUS")
print(f"Past games (should have data): {len(past_games)}")
print(f"Future games (no data expected): {len(future_games)}")

# League-by-league stress test
print(f"\n{'=' * 80}")
print("LEAGUE-BY-LEAGUE STRESS TEST")
print(f"{'=' * 80}")

results = []

for comp in sorted(df_index["competition"].unique()):
    print(f"\n{'-' * 80}")
    print(f"COMPETITION: {comp}")
    print(f"{'-' * 80}")

    expected_league_id = EXPECTED_LEAGUE_IDS.get(comp, "UNKNOWN")
    print(f"Expected canonical ID: {expected_league_id}")

    comp_games = df_index[df_index["competition"] == comp]
    comp_past = comp_games[comp_games["game_datetime"] <= today]
    comp_future = comp_games[comp_games["game_datetime"] > today]

    print("\nGame Counts:")
    print(f"  Total: {len(comp_games)}")
    print(f"  Past: {len(comp_past)}")
    print(f"  Future: {len(comp_future)}")

    # Check seasons
    print("\nGames per season:")
    for season in sorted(comp_games["season"].unique()):
        season_games = comp_games[comp_games["season"] == season]
        season_past = season_games[season_games["game_datetime"] <= today]
        print(f"  {season}: {len(season_games)} total ({len(season_past)} past)")

    # Data coverage for PAST games only
    if len(comp_past) > 0:
        print("\nDATA COVERAGE (Past games only):")

        # PBP coverage
        pbp_count = sum(1 for gid in comp_past["game_id"] if gid in pbp_files)
        pbp_pct = pbp_count / len(comp_past) * 100
        print(f"  PBP:   {pbp_count:4} / {len(comp_past):4} ({pbp_pct:5.1f}%)")

        # Shots coverage
        shots_count = sum(1 for gid in comp_past["game_id"] if gid in shots_files)
        shots_pct = shots_count / len(comp_past) * 100
        print(f"  Shots: {shots_count:4} / {len(comp_past):4} ({shots_pct:5.1f}%)")

        # LEAGUE column validation (sample 3 files)
        print("\nLEAGUE COLUMN VALIDATION:")
        comp_game_ids = [gid for gid in comp_past["game_id"] if gid in pbp_files]

        if len(comp_game_ids) > 0:
            sample_size = min(3, len(comp_game_ids))
            league_values = set()

            for game_id in comp_game_ids[:sample_size]:
                try:
                    pbp_path = pbp_files[game_id]
                    df_pbp = pd.read_parquet(pbp_path)
                    if "LEAGUE" in df_pbp.columns:
                        league_val = df_pbp["LEAGUE"].iloc[0]
                        league_values.add(league_val)
                except Exception as e:
                    print(f"  ERROR reading {game_id[:16]}...: {str(e)[:50]}")

            print(f"  Sample size: {sample_size} files")
            print(f"  LEAGUE values found: {league_values}")

            if len(league_values) == 1 and list(league_values)[0] == expected_league_id:
                print(
                    f"  STATUS: OK - All sampled files have correct LEAGUE='{expected_league_id}'"
                )
            elif len(league_values) == 1:
                print(
                    f"  STATUS: ERROR - Files have LEAGUE='{list(league_values)[0]}' but expected '{expected_league_id}'"
                )
            else:
                print(
                    f"  STATUS: ERROR - Multiple LEAGUE values found! Expected only '{expected_league_id}'"
                )
        else:
            print("  STATUS: NO FILES - Cannot validate LEAGUE column")

        # Record results
        results.append(
            {
                "competition": comp,
                "expected_league_id": expected_league_id,
                "total_games": len(comp_games),
                "past_games": len(comp_past),
                "pbp_files": pbp_count,
                "pbp_coverage_pct": pbp_pct,
                "shots_files": shots_count,
                "shots_coverage_pct": shots_pct,
            }
        )
    else:
        print("\nDATA COVERAGE: No past games yet")
        results.append(
            {
                "competition": comp,
                "expected_league_id": expected_league_id,
                "total_games": len(comp_games),
                "past_games": 0,
                "pbp_files": 0,
                "pbp_coverage_pct": 0,
                "shots_files": 0,
                "shots_coverage_pct": 0,
            }
        )

# Summary table
print(f"\n{'=' * 80}")
print("SUMMARY TABLE")
print(f"{'=' * 80}")

df_results = pd.DataFrame(results)
print("\nCoverage by Competition:")
print(f"{'Competition':<20} {'League ID':<20} {'Past':<6} {'PBP %':<8} {'Shots %':<8}")
print("-" * 80)
for _, row in df_results.iterrows():
    print(
        f"{row['competition']:<20} {row['expected_league_id']:<20} {row['past_games']:<6} "
        f"{row['pbp_coverage_pct']:6.1f}%  {row['shots_coverage_pct']:6.1f}%"
    )

# Identify gaps
print(f"\n{'=' * 80}")
print("GAPS AND RECOMMENDATIONS")
print(f"{'=' * 80}")

gaps_found = False

for _, row in df_results.iterrows():
    if row["past_games"] > 0:
        if row["pbp_coverage_pct"] < 100:
            gaps_found = True
            missing = row["past_games"] - row["pbp_files"]
            print(f"\n{row['competition']}:")
            print(f"  MISSING: {missing} PBP files ({100 - row['pbp_coverage_pct']:.1f}% gap)")
            print("  ACTION: Run bulk ingestion for this competition")

        if row["shots_coverage_pct"] < 100:
            if not gaps_found:
                gaps_found = True
                print(f"\n{row['competition']}:")
            missing = row["past_games"] - row["shots_files"]
            print(f"  MISSING: {missing} shots files ({100 - row['shots_coverage_pct']:.1f}% gap)")
            print("  ACTION: Run bulk ingestion for this competition")

if not gaps_found:
    print("\nOK: 100% coverage for all past games across all competitions!")

# Box score coverage
print(f"\n{'=' * 80}")
print("BOX SCORE COVERAGE")
print(f"{'=' * 80}")

has_box_count = df_index["has_boxscore"].sum()
print(f"\nGames with box score flag: {has_box_count} / {len(df_index)}")

if has_box_count == 0:
    print("WARNING: No box score data has been fetched yet")
    print("ACTION: Implement box score fetching in bulk_ingest_pbp_shots.py")
else:
    print("OK: Box score data is being fetched")

print(f"\n{'=' * 80}")
print("STRESS TEST COMPLETE")
print(f"{'=' * 80}\n")
