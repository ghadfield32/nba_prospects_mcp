#!/usr/bin/env python
"""Build game index artifacts from silver layer parquet files.

This script extracts unique game information from the silver layer box_player_game
data and creates standardized game index CSV files.

Usage:
    python scripts/build_game_indexes_from_silver.py --league NCAA_MBB
    python scripts/build_game_indexes_from_silver.py --all
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.parent
UNIFIED_BASE = BASE_DIR.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"

SILVER_DIR = UNIFIED_BASE / "data" / "silver" / "box_player_game"
OUTPUT_DIR = UNIFIED_BASE / "data" / "game_indexes"

# Leagues that need game index artifacts (from silver layer)
LEAGUES_NEEDING_INDEXES = ["NCAA_MBB", "G-League", "CEBL", "OTE"]


def normalize_league_name(league: str) -> str:
    """Normalize league name for file naming."""
    return league.replace("-", "_").upper()


def extract_game_index_from_silver(league: str, season: str, silver_path: Path) -> pd.DataFrame:
    """Extract game index from silver layer box data."""
    parquet_path = silver_path / "data.parquet"
    if not parquet_path.exists():
        logger.warning(f"No parquet file at {parquet_path}")
        return pd.DataFrame()

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        logger.error(f"Failed to read {parquet_path}: {e}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Determine GAME_ID column
    game_id_col = None
    for col in ["GAME_ID", "game_id", "gameId", "GameId"]:
        if col in df.columns:
            game_id_col = col
            break

    if not game_id_col:
        logger.warning(f"No GAME_ID column found in {parquet_path}")
        return pd.DataFrame()

    # Determine GAME_DATE column
    date_col = None
    for col in ["GAME_DATE", "game_date", "gameDate", "Date", "DATE"]:
        if col in df.columns:
            date_col = col
            break

    # Determine TEAM column
    team_col = None
    for col in ["TEAM_KEY", "TEAM", "team", "teamCode", "Team"]:
        if col in df.columns:
            team_col = col
            break

    # Determine opponent column
    opp_col = None
    for col in ["OPPONENT_KEY", "OPPONENT", "opponent", "Opponent", "OPP"]:
        if col in df.columns:
            opp_col = col
            break

    # Extract unique games
    games = []
    for game_id, game_df in df.groupby(game_id_col):
        game_info = {
            "GAME_ID": game_id,
            "SEASON": season,
            "LEAGUE": normalize_league_name(league),
        }

        # Get date if available
        if date_col and date_col in game_df.columns:
            dates = game_df[date_col].dropna()
            if len(dates) > 0:
                game_info["GAME_DATE"] = (
                    pd.to_datetime(dates.iloc[0]).strftime("%Y-%m-%d")
                    if pd.notna(dates.iloc[0])
                    else None
                )

        # Get teams
        if team_col and team_col in game_df.columns:
            teams = game_df[team_col].dropna().unique()
            if len(teams) >= 2:
                game_info["HOME_TEAM"] = teams[0]
                game_info["AWAY_TEAM"] = teams[1]
            elif len(teams) == 1:
                game_info["HOME_TEAM"] = teams[0]
                if opp_col and opp_col in game_df.columns:
                    opps = game_df[opp_col].dropna().unique()
                    if len(opps) > 0:
                        game_info["AWAY_TEAM"] = opps[0]

        games.append(game_info)

    return pd.DataFrame(games)


def build_indexes_for_league(league: str) -> int:
    """Build game indexes for all seasons of a league."""
    league_dir = SILVER_DIR / f"league={league}"

    if not league_dir.exists():
        logger.warning(f"No silver data found for league={league}")
        return 0

    seasons = sorted([d.name.replace("season=", "") for d in league_dir.iterdir() if d.is_dir()])
    logger.info(f"Found {len(seasons)} seasons for {league}: {seasons}")

    total_games = 0
    for season in seasons:
        season_dir = league_dir / f"season={season}"
        index_df = extract_game_index_from_silver(league, season, season_dir)

        if index_df.empty:
            logger.warning(f"No games extracted for {league} {season}")
            continue

        # Save to game_indexes directory
        league_norm = normalize_league_name(league)
        season_norm = season.replace("-", "_")
        output_path = OUTPUT_DIR / f"{league_norm}_{season_norm}.csv"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        index_df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(index_df)} games to {output_path}")
        total_games += len(index_df)

    return total_games


def main():
    parser = argparse.ArgumentParser(description="Build game index artifacts from silver layer")
    parser.add_argument("--league", help="League to process (e.g., NCAA_MBB, G-League, CEBL, OTE)")
    parser.add_argument("--all", action="store_true", help="Process all leagues needing indexes")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed without creating files"
    )

    args = parser.parse_args()

    if args.all:
        leagues = LEAGUES_NEEDING_INDEXES
    elif args.league:
        leagues = [args.league]
    else:
        logger.error("Specify --league or --all")
        return

    logger.info(f"Will process leagues: {leagues}")

    if args.dry_run:
        for league in leagues:
            league_dir = SILVER_DIR / f"league={league}"
            if league_dir.exists():
                seasons = sorted([d.name for d in league_dir.iterdir() if d.is_dir()])
                logger.info(f"  {league}: {len(seasons)} seasons - {seasons}")
            else:
                logger.info(f"  {league}: No silver data found")
        return

    grand_total = 0
    for league in leagues:
        total = build_indexes_for_league(league)
        grand_total += total
        logger.info(f"Completed {league}: {total} total games indexed")

    logger.info(f"Grand total: {grand_total} games indexed across {len(leagues)} leagues")


if __name__ == "__main__":
    main()
