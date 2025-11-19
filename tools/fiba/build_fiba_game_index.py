#!/usr/bin/env python
"""FIBA Master Game Index Builder

Builds a unified game index for all FIBA LiveStats-based leagues.
This is the single source of truth for which FIBA games are available.

Supported Leagues:
- NZN (NZ-NBL): New Zealand National Basketball League
- E (EuroLeague): via euroleague-api
- U (EuroCup): via euroleague-api
- BAL: Basketball Africa League
- L (BCL): Basketball Champions League

Usage:
    python tools/fiba/build_fiba_game_index.py
    python tools/fiba/build_fiba_game_index.py --league NZN
    python tools/fiba/build_fiba_game_index.py --season 2024
    python tools/fiba/build_fiba_game_index.py --output data/raw/fiba/fiba_game_index.parquet

Output Schema:
    - league_code: FIBA league code (NZN, E, U, BAL, L)
    - game_id: FIBA game ID
    - season: Season string (e.g., "2024")
    - game_date: Game date (ISO format)
    - home_team: Home team name
    - away_team: Away team name
    - home_score: Home team final score
    - away_score: Away team final score
    - status: Game status (completed, scheduled, etc.)
    - source: Data source (fiba_livestats, euroleague_api, etc.)
"""

import argparse
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd

# FIBA League configurations
FIBA_LEAGUES = {
    "NZN": {
        "name": "NZ-NBL",
        "region": "New Zealand",
        "source": "fiba_livestats_direct",
        "seasons": ["2024", "2023", "2022", "2021"],
    },
    "E": {
        "name": "EuroLeague",
        "region": "Europe",
        "source": "euroleague_api",
        "seasons": ["2024", "2023", "2022", "2021", "2020"],
    },
    "U": {
        "name": "EuroCup",
        "region": "Europe",
        "source": "euroleague_api",
        "seasons": ["2024", "2023", "2022", "2021", "2020"],
    },
    "BAL": {
        "name": "Basketball Africa League",
        "region": "Africa",
        "source": "fiba_livestats_direct",
        "seasons": ["2024", "2023", "2022", "2021"],
    },
}


def discover_nz_nbl_games(season: str) -> pd.DataFrame:
    """Discover NZ-NBL games for a season."""
    from cbb_data.fetchers import DataUnavailableError, nz_nbl_fiba

    try:
        df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)
        if df.empty:
            return pd.DataFrame()

        # Normalize to standard schema
        result = pd.DataFrame(
            {
                "league_code": "NZN",
                "game_id": df.get("GAME_ID", df.get("game_id", df.get("FIBA_GAME_ID", pd.NA))),
                "season": season,
                "game_date": df.get("GAME_DATE", df.get("game_date", pd.NA)),
                "home_team": df.get("HOME_TEAM", df.get("home_team", pd.NA)),
                "away_team": df.get("AWAY_TEAM", df.get("away_team", pd.NA)),
                "home_score": df.get("HOME_SCORE", df.get("home_score", pd.NA)),
                "away_score": df.get("AWAY_SCORE", df.get("away_score", pd.NA)),
                "status": "completed",
                "source": "fiba_livestats_direct",
            }
        )
        return result
    except DataUnavailableError as e:
        print(f"    NZN {season}: {e.kind}")
        return pd.DataFrame()
    except Exception as e:
        print(f"    NZN {season}: ERROR - {type(e).__name__}")
        return pd.DataFrame()


def discover_euroleague_games(season: str, competition: str = "E") -> pd.DataFrame:
    """Discover EuroLeague/EuroCup games for a season."""
    from cbb_data.fetchers import euroleague

    try:
        if competition == "E":
            df = euroleague.fetch_euroleague_schedule(season=season)
        else:
            df = euroleague.fetch_eurocup_schedule(season=season)

        if df.empty:
            return pd.DataFrame()

        # Normalize to standard schema
        result = pd.DataFrame(
            {
                "league_code": competition,
                "game_id": df.get("GAME_ID", df.get("game_id", pd.NA)),
                "season": season,
                "game_date": df.get("GAME_DATE", df.get("game_date", pd.NA)),
                "home_team": df.get("HOME_TEAM", df.get("home_team", pd.NA)),
                "away_team": df.get("AWAY_TEAM", df.get("away_team", pd.NA)),
                "home_score": df.get("HOME_SCORE", df.get("home_score", pd.NA)),
                "away_score": df.get("AWAY_SCORE", df.get("away_score", pd.NA)),
                "status": "completed",
                "source": "euroleague_api",
            }
        )
        return result
    except Exception as e:
        print(f"    {competition} {season}: ERROR - {type(e).__name__}")
        return pd.DataFrame()


def build_fiba_game_index(
    leagues: list[str] | None = None,
    seasons: list[str] | None = None,
    output_path: Path = Path("data/raw/fiba/fiba_game_index.parquet"),
) -> pd.DataFrame:
    """Build master FIBA game index.

    Args:
        leagues: List of league codes to include (None = all)
        seasons: List of seasons to include (None = all configured)
        output_path: Path to save parquet file

    Returns:
        Combined DataFrame with all discovered games
    """
    # Determine which leagues to process
    if leagues:
        target_leagues = {k: v for k, v in FIBA_LEAGUES.items() if k in leagues}
    else:
        target_leagues = FIBA_LEAGUES

    all_games = []
    summary = {}

    for code, config in target_leagues.items():
        print(f"\nDiscovering {config['name']} ({code})...")
        league_games = []

        # Determine seasons to process
        if seasons:
            target_seasons = [s for s in seasons if s in config["seasons"]]
        else:
            target_seasons = config["seasons"]

        for season in target_seasons:
            # Route to appropriate discoverer
            if code == "NZN":
                df = discover_nz_nbl_games(season)
            elif code in ["E", "U"]:
                df = discover_euroleague_games(season, code)
            else:
                # Placeholder for other leagues
                print(f"    {code} {season}: Not implemented")
                continue

            if not df.empty:
                league_games.append(df)
                print(f"    {season}: {len(df)} games")
            else:
                print(f"    {season}: 0 games")

        # Combine league games
        if league_games:
            combined = pd.concat(league_games, ignore_index=True)
            all_games.append(combined)
            summary[code] = len(combined)
        else:
            summary[code] = 0

    # Combine all leagues
    if all_games:
        master_index = pd.concat(all_games, ignore_index=True)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to parquet
        master_index.to_parquet(output_path, index=False)
        print(f"\nSaved {len(master_index)} games to {output_path}")
    else:
        master_index = pd.DataFrame()
        print("\nNo games discovered")

    return master_index


def main():
    parser = argparse.ArgumentParser(description="Build FIBA master game index")
    parser.add_argument("--league", help="Specific league code (NZN, E, U, BAL, L)")
    parser.add_argument("--season", help="Specific season (e.g., 2024)")
    parser.add_argument(
        "--output", default="data/raw/fiba/fiba_game_index.parquet", help="Output file"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FIBA MASTER GAME INDEX BUILDER")
    print("=" * 70)

    start = time.time()

    leagues = [args.league] if args.league else None
    seasons = [args.season] if args.season else None

    master_index = build_fiba_game_index(
        leagues=leagues,
        seasons=seasons,
        output_path=Path(args.output),
    )

    elapsed = time.time() - start

    print()
    print("=" * 70)
    print("INDEX SUMMARY")
    print("=" * 70)

    if not master_index.empty:
        print(f"Total games: {len(master_index)}")
        print()
        print("By league:")
        for code in master_index["league_code"].unique():
            count = len(master_index[master_index["league_code"] == code])
            print(f"  {code}: {count} games")
        print()
        print("By season:")
        for season in sorted(master_index["season"].unique(), reverse=True):
            count = len(master_index[master_index["season"] == season])
            print(f"  {season}: {count} games")
    else:
        print("No games in index")

    print()
    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
