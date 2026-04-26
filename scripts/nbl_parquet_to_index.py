#!/usr/bin/env python
"""NBL Parquet to Game Index Converter

Converts existing NBL parquet data to standard game index format.
NBL data already exists in data/nbl_raw/ - we just need to standardize it.

Usage:
    python scripts/nbl_parquet_to_index.py
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, "src")

import pandas as pd

DATA_DIR = Path("data")
NBL_RAW_DIR = DATA_DIR / "nbl_raw"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
GAME_INDEX_DIR.mkdir(parents=True, exist_ok=True)


def process_nbl_results():
    """Process NBL results parquet to game index.

    NBL data has 2 rows per game (one from each team's perspective).
    We need to filter to home team rows and pivot to get both teams.
    """
    results_path = NBL_RAW_DIR / "nbl_results.parquet"

    if not results_path.exists():
        print(f"NBL results not found: {results_path}")
        return

    print(f"Loading NBL results from {results_path}")
    df = pd.read_parquet(results_path)

    print(f"Loaded {len(df)} rows (2 per game)")
    print(f"Columns: {list(df.columns)}")

    # Filter to home team rows only (is_home_competitor == '1' - it's a string)
    home_df = df[df["is_home_competitor"] == "1"].copy()
    print(f"Filtered to {len(home_df)} home team rows (unique games)")

    # Transform to standard game index format
    games = []
    for _, row in home_df.iterrows():
        # Parse date from match_time
        match_time = row.get("match_time")
        game_date = None
        if pd.notna(match_time):
            try:
                game_date = pd.to_datetime(match_time).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Parse scores from score_string (e.g., "62")
        home_score = None
        away_score = None
        try:
            if pd.notna(row.get("score_string")):
                home_score = int(row["score_string"])
            if pd.notna(row.get("opp_score_string")):
                away_score = int(row["opp_score_string"])
        except (ValueError, TypeError):
            pass

        games.append(
            {
                "LEAGUE": "NBL",
                "SEASON": row.get("season"),
                "GAME_ID": row.get("match_id"),
                "GAME_DATE": game_date,
                "HOME_TEAM": row.get("team_name"),
                "AWAY_TEAM": row.get("opp_team_name"),
                "HOME_SCORE": home_score,
                "AWAY_SCORE": away_score,
                "HOME_TEAM_ID": row.get("team_id"),
                "AWAY_TEAM_ID": row.get("opp_team_id"),
                "VENUE": row.get("venue_name"),
                "STATUS": row.get("match_status"),
            }
        )

    result_df = pd.DataFrame(games)
    print(f"Created {len(result_df)} game records")

    # Group by season and write separate files
    for season in result_df["SEASON"].unique():
        season_df = result_df[result_df["SEASON"] == season].copy()

        # Format season for filename
        season_str = str(season).replace("-", "_").replace("/", "_")
        filename = f"NBL_{season_str}.csv"
        filepath = GAME_INDEX_DIR / filename

        season_df.to_csv(filepath, index=False)

        # Validate
        date_pct = round(season_df["GAME_DATE"].notna().mean() * 100, 1)
        score_pct = round(season_df["HOME_SCORE"].notna().mean() * 100, 1)
        print(
            f"Wrote {len(season_df)} games to {filepath} (dates: {date_pct}%, scores: {score_pct}%)"
        )


def main():
    print("=" * 70)
    print("NBL PARQUET TO GAME INDEX CONVERTER")
    print("=" * 70)
    print()

    if not NBL_RAW_DIR.exists():
        print(f"NBL raw data directory not found: {NBL_RAW_DIR}")
        return

    # List available parquet files
    parquet_files = list(NBL_RAW_DIR.glob("*.parquet"))
    print(f"Found {len(parquet_files)} parquet files:")
    for f in parquet_files:
        print(f"  - {f.name}")
    print()

    # Process results
    process_nbl_results()

    print()
    print("Done!")


if __name__ == "__main__":
    main()
