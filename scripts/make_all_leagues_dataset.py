#!/usr/bin/env python
"""Unified Cross-League Dataset Builder

Builds a normalized dataset across all healthy basketball leagues.
Uses league_data_health.py results to determine which seasons to ingest.

Usage:
    python scripts/make_all_leagues_dataset.py
    python scripts/make_all_leagues_dataset.py --granularity player_game
    python scripts/make_all_leagues_dataset.py --leagues acb,lnb,euroleague
    python scripts/make_all_leagues_dataset.py --seasons 2023,2024
    python scripts/make_all_leagues_dataset.py --output data/processed/unified

Output Schema (player_game granularity):
    - league: League code (ACB, LNB, NZ-NBL, EURL, NBL)
    - season: Season string
    - game_id: Game identifier
    - game_date: Game date
    - team_id: Team identifier
    - team_name: Team name
    - player_id: Player identifier (where available)
    - player_name: Player name
    - minutes: Minutes played
    - pts: Points
    - reb: Rebounds
    - ast: Assists
    - stl: Steals
    - blk: Blocks
    - tov: Turnovers
    - fgm/fga: Field goals made/attempted
    - fg3m/fg3a: 3-pointers made/attempted
    - ftm/fta: Free throws made/attempted
    - plus_minus: Plus/minus (where available)

Granularities:
    - player_game: Per-player per-game box scores
    - team_game: Per-team per-game aggregates
    - player_season: Player season totals
    - team_season: Team season totals
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd

# Standard column mapping for normalization
STANDARD_COLUMNS = {
    # Identifiers
    "GAME_ID": "game_id",
    "game_code": "game_id",
    "PLAYER_ID": "player_id",
    "PLAYER_NAME": "player_name",
    "player": "player_name",
    "name": "player_name",
    "TEAM_ID": "team_id",
    "TEAM": "team_name",
    "team": "team_name",
    "TEAM_NAME": "team_name",
    # Game info
    "GAME_DATE": "game_date",
    "game_date": "game_date",
    "date": "game_date",
    # Minutes
    "MIN": "minutes",
    "MINS": "minutes",
    "minutes": "minutes",
    "MP": "minutes",
    # Core stats
    "PTS": "pts",
    "pts": "pts",
    "points": "pts",
    "REB": "reb",
    "reb": "reb",
    "rebounds": "reb",
    "AST": "ast",
    "ast": "ast",
    "assists": "ast",
    "STL": "stl",
    "stl": "stl",
    "steals": "stl",
    "BLK": "blk",
    "blk": "blk",
    "blocks": "blk",
    "TOV": "tov",
    "tov": "tov",
    "turnovers": "tov",
    "TO": "tov",
    # Shooting
    "FGM": "fgm",
    "fgm": "fgm",
    "FGA": "fga",
    "fga": "fga",
    "FG3M": "fg3m",
    "fg3m": "fg3m",
    "3PM": "fg3m",
    "FG3A": "fg3a",
    "fg3a": "fg3a",
    "3PA": "fg3a",
    "FTM": "ftm",
    "ftm": "ftm",
    "FTA": "fta",
    "fta": "fta",
    # Advanced
    "PLUS_MINUS": "plus_minus",
    "plus_minus": "plus_minus",
    "+/-": "plus_minus",
}


def normalize_dataframe(df: pd.DataFrame, league: str, season: str) -> pd.DataFrame:
    """Normalize a DataFrame to standard column names."""
    if df.empty:
        return df

    # Add league and season
    result = df.copy()
    result["league"] = league
    result["season"] = season

    # Rename columns to standard names
    rename_map = {}
    for old_name in result.columns:
        if old_name in STANDARD_COLUMNS:
            rename_map[old_name] = STANDARD_COLUMNS[old_name]

    result = result.rename(columns=rename_map)

    return result


def get_healthy_seasons(health_report: dict, league: str) -> list[str]:
    """Extract healthy seasons for a league from health report."""
    if league not in health_report.get("leagues", {}):
        return []

    league_data = health_report["leagues"][league]
    if league_data.get("status") != "OK":
        return []

    # Extract seasons from coverage
    coverage = league_data.get("coverage", {})
    seasons = []
    for key in coverage:
        # Extract season from keys like "2024_games", "2024-25_games"
        if "_" in key:
            season = key.split("_")[0]
            if season not in seasons:
                seasons.append(season)

    return seasons


def fetch_acb_player_game(season: str) -> pd.DataFrame:
    """Fetch ACB player game data for a season."""
    from cbb_data.fetchers import acb

    # Get schedule first
    schedule = acb.fetch_acb_schedule(season=season)
    if schedule.empty:
        return pd.DataFrame()

    # Find game ID column
    game_id_col = None
    for col in ["game_code", "game_id", "GAME_ID", "id"]:
        if col in schedule.columns:
            game_id_col = col
            break

    if game_id_col is None:
        return pd.DataFrame()

    # Fetch box scores for each game
    all_records = []
    for game_id in schedule[game_id_col].unique():
        try:
            box = acb.fetch_acb_box_score(str(game_id))
            if not box.empty:
                box["game_id"] = game_id
                all_records.append(box)
        except Exception:
            pass

    if all_records:
        return pd.concat(all_records, ignore_index=True)
    return pd.DataFrame()


def fetch_lnb_player_game(season: str) -> pd.DataFrame:
    """Fetch LNB player game data for a season."""
    from cbb_data.fetchers import lnb

    # Convert season string to int for API
    try:
        season_int = int(season) + 1
    except ValueError:
        return pd.DataFrame()

    return lnb.fetch_lnb_player_game(season=season_int)


def fetch_euroleague_player_game(season: str) -> pd.DataFrame:
    """Fetch Euroleague player game data for a season."""
    from cbb_data.fetchers import euroleague

    return euroleague.fetch_euroleague_player_game(season=season)


def fetch_nbl_player_game(season: str) -> pd.DataFrame:
    """Fetch NBL (Australia) player game data for a season."""
    from cbb_data.fetchers import nbl

    return nbl.fetch_nbl_player_game(season=season)


def fetch_nz_nbl_player_game(season: str) -> pd.DataFrame:
    """Fetch NZ-NBL player game data for a season."""
    from cbb_data.fetchers import nz_nbl_fiba

    return nz_nbl_fiba.fetch_nz_nbl_player_game(season=season)


# League fetcher mapping
LEAGUE_FETCHERS = {
    "acb": {
        "player_game": fetch_acb_player_game,
        "name": "ACB",
    },
    "lnb": {
        "player_game": fetch_lnb_player_game,
        "name": "LNB",
    },
    "euroleague": {
        "player_game": fetch_euroleague_player_game,
        "name": "EURL",
    },
    "nbl": {
        "player_game": fetch_nbl_player_game,
        "name": "NBL",
    },
    "nz-nbl": {
        "player_game": fetch_nz_nbl_player_game,
        "name": "NZ-NBL",
    },
}


def build_unified_dataset(
    leagues: list[str] | None = None,
    seasons: list[str] | None = None,
    granularity: str = "player_game",
    output_dir: Path = Path("data/processed/unified"),
    health_file: Path | None = None,
) -> pd.DataFrame:
    """Build unified dataset across leagues.

    Args:
        leagues: List of league codes (None = all healthy)
        seasons: List of seasons (None = all healthy)
        granularity: Data granularity (player_game, team_game, etc.)
        output_dir: Output directory
        health_file: Path to health report JSON (optional)

    Returns:
        Combined normalized DataFrame
    """
    # Load or generate health report
    if health_file and health_file.exists():
        with open(health_file) as f:
            health_report = json.load(f)
        print(f"Loaded health report from {health_file}")
    else:
        # Run health check inline
        print("Running health check...")
        from league_data_health import run_health_checks

        health_report = run_health_checks()

    # Determine target leagues
    if leagues:
        target_leagues = [league_str.lower() for league_str in leagues]
    else:
        target_leagues = list(LEAGUE_FETCHERS.keys())

    all_data = []
    summary = {}

    for league_code in target_leagues:
        if league_code not in LEAGUE_FETCHERS:
            print(f"  {league_code}: Unknown league, skipping")
            continue

        fetcher_info = LEAGUE_FETCHERS[league_code]
        league_name = fetcher_info["name"]

        # Get fetcher for granularity
        if granularity not in fetcher_info:
            print(f"  {league_name}: No {granularity} fetcher, skipping")
            continue

        fetcher = fetcher_info[granularity]

        # Determine seasons to fetch
        if seasons:
            target_seasons = seasons
        else:
            # Get healthy seasons from health report
            target_seasons = get_healthy_seasons(health_report, league_code)
            if not target_seasons:
                # Fallback: try common seasons
                target_seasons = ["2024", "2023"]

        print(f"\n{league_name}: Fetching {len(target_seasons)} seasons...")
        league_records = 0

        for season in target_seasons:
            try:
                df = fetcher(season)
                if not df.empty:
                    # Normalize
                    normalized = normalize_dataframe(df, league_name, season)
                    all_data.append(normalized)
                    league_records += len(normalized)
                    print(f"  {season}: {len(normalized)} records")
                else:
                    print(f"  {season}: 0 records")
            except Exception as e:
                print(f"  {season}: ERROR - {type(e).__name__}")

        summary[league_name] = league_records

    # Combine all data
    if all_data:
        unified = pd.concat(all_data, ignore_index=True)

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save to parquet
        output_path = output_dir / f"{granularity}_unified.parquet"
        unified.to_parquet(output_path, index=False)
        print(f"\nSaved {len(unified)} total records to {output_path}")

        # Also save as CSV for inspection
        csv_path = output_dir / f"{granularity}_unified.csv"
        unified.to_csv(csv_path, index=False)
        print(f"Saved CSV to {csv_path}")
    else:
        unified = pd.DataFrame()
        print("\nNo data collected")

    return unified


def main():
    parser = argparse.ArgumentParser(description="Build unified cross-league dataset")
    parser.add_argument(
        "--leagues", help="Comma-separated league codes (acb,lnb,euroleague,nbl,nz-nbl)"
    )
    parser.add_argument("--seasons", help="Comma-separated seasons (2023,2024)")
    parser.add_argument(
        "--granularity",
        default="player_game",
        choices=["player_game", "team_game", "player_season", "team_season"],
        help="Data granularity",
    )
    parser.add_argument("--output", default="data/processed/unified", help="Output directory")
    parser.add_argument("--health-file", help="Path to health report JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("UNIFIED CROSS-LEAGUE DATASET BUILDER")
    print("=" * 70)
    print(f"Granularity: {args.granularity}")
    print()

    start = time.time()

    leagues = args.leagues.split(",") if args.leagues else None
    seasons = args.seasons.split(",") if args.seasons else None
    health_file = Path(args.health_file) if args.health_file else None

    unified = build_unified_dataset(
        leagues=leagues,
        seasons=seasons,
        granularity=args.granularity,
        output_dir=Path(args.output),
        health_file=health_file,
    )

    elapsed = time.time() - start

    print()
    print("=" * 70)
    print("DATASET SUMMARY")
    print("=" * 70)

    if not unified.empty:
        print(f"Total records: {len(unified)}")
        print()
        print("By league:")
        for league in unified["league"].unique():
            count = len(unified[unified["league"] == league])
            print(f"  {league}: {count} records")
        print()
        print("By season:")
        for season in sorted(unified["season"].unique(), reverse=True):
            count = len(unified[unified["season"] == season])
            print(f"  {season}: {count} records")
        print()

        # Show available columns
        standard_cols = ["pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg3m", "fg3a"]
        available = [c for c in standard_cols if c in unified.columns]
        print(f"Available stats: {', '.join(available)}")
    else:
        print("No data in unified dataset")

    print()
    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
