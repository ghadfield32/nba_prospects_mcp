#!/usr/bin/env python
"""Batch fetch BCL/BAL/LKL player game data via FIBA JSON API.

This script fetches box scores from the FIBA LiveStats JSON API
and saves them to canonical format for merging into the gold table.

Usage:
    python scripts/batch_fetch_fiba_json.py --league BCL --seasons 2024-25
    python scripts/batch_fetch_fiba_json.py --league BCL --all-seasons --limit 100
"""

import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.parent
UNIFIED_BASE = BASE_DIR.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"

GAME_INDEX_DIRS = [
    BASE_DIR / "data" / "game_indexes",
    UNIFIED_BASE / "data" / "game_indexes",
]

OUTPUT_DIR = UNIFIED_BASE / "data" / "canonical" / "box_player_game"
GOLD_TABLE_PATH = BASE_DIR / "data" / "gold" / "player_career_game.parquet"

FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Rate limiting
REQUESTS_PER_SECOND = 2
LAST_REQUEST_TIME = 0


def rate_limit():
    """Simple rate limiter."""
    global LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME
    if elapsed < 1.0 / REQUESTS_PER_SECOND:
        time.sleep(1.0 / REQUESTS_PER_SECOND - elapsed)
    LAST_REQUEST_TIME = time.time()


def extract_numeric_id(game_id: str) -> str | None:
    """Extract numeric portion from FIBA game ID."""
    parts = str(game_id).split("-")
    for part in parts:
        if part.isdigit() and len(part) >= 5:
            return part
    for part in parts:
        if part.isdigit():
            return part
    return None


def fetch_game_json(game_id: str) -> dict | None:
    """Fetch game data from FIBA JSON API."""
    numeric_id = extract_numeric_id(game_id)
    if not numeric_id:
        return None

    url = f"{FIBA_BASE_URL}/data/{numeric_id}/data.json"

    try:
        rate_limit()
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.debug(f"Failed to fetch {game_id}: {e}")

    return None


def parse_game_boxscore(data: dict, game_id: str, league: str, season: str) -> list:
    """Parse FIBA JSON into player records."""
    players = []

    tm_data = data.get("tm", {})

    for team_key in ["1", "2"]:
        team = tm_data.get(team_key, {})
        team.get("name", team.get("shortName", "Unknown"))
        team_code = team.get("code", "")
        team.get("score", 0)

        # Get opponent info
        opp_key = "2" if team_key == "1" else "1"
        opp_team = tm_data.get(opp_key, {})
        opp_name = opp_team.get("code", opp_team.get("shortName", ""))

        pl_data = team.get("pl", {})

        for player_id, pstats in pl_data.items():
            if not pstats.get("active", 1):
                continue

            first_name = pstats.get("firstName", "")
            family_name = pstats.get("familyName", "")
            player_name = f"{first_name} {family_name}".strip()

            # Parse minutes
            min_str = pstats.get("sMinutes", "0:00")
            try:
                if ":" in str(min_str):
                    mins, secs = str(min_str).split(":")
                    minutes = int(mins) + int(secs) / 60
                else:
                    minutes = float(min_str)
            except (ValueError, TypeError):
                minutes = 0

            # Generate NAME_KEY
            name_key = player_name.lower().replace(" ", "_").replace(".", "")
            name_key = "".join(c for c in name_key if c.isalnum() or c == "_")

            players.append(
                {
                    "LEAGUE": league,
                    "SEASON": season,
                    "GAME_ID": game_id,
                    "GAME_DATE": None,  # Would need to fetch from index
                    "TEAM_KEY": team_code,
                    "SOURCE_PLAYER_ID": f"FIBA_{team_code}_{player_id}",
                    "PLAYER_NAME_RAW": player_name,
                    "NAME_KEY": name_key,
                    "OPPONENT_KEY": opp_name,
                    "IS_HOME": team_key == "1",
                    "MIN": round(minutes, 1),
                    "PTS": pstats.get("sPoints", 0),
                    "FGM": pstats.get("sFieldGoalsMade", 0),
                    "FGA": pstats.get("sFieldGoalsAttempted", 0),
                    "FG3M": pstats.get("sThreePointersMade", 0),
                    "FG3A": pstats.get("sThreePointersAttempted", 0),
                    "FTM": pstats.get("sFreeThrowsMade", 0),
                    "FTA": pstats.get("sFreeThrowsAttempted", 0),
                    "OREB": pstats.get("sReboundsOffensive", 0),
                    "DREB": pstats.get("sReboundsDefensive", 0),
                    "TRB": pstats.get("sReboundsTotal", 0),
                    "AST": pstats.get("sAssists", 0),
                    "STL": pstats.get("sSteals", 0),
                    "BLK": pstats.get("sBlocks", 0),
                    "TOV": pstats.get("sTurnovers", 0),
                    "PF": pstats.get("sFoulsPersonal", 0),
                    "PLUS_MINUS": None,
                    "STARTER": 1 if pstats.get("starter", 0) else 0,
                    "DNP_REASON": None,
                    "SOURCE": "fiba_json",
                }
            )

    return players


def load_game_index(league: str) -> pd.DataFrame:
    """Load all game indexes for a league."""
    all_games = []

    for idx_dir in GAME_INDEX_DIRS:
        if not idx_dir.exists():
            continue
        for f in idx_dir.glob(f"{league}*.csv"):
            try:
                df = pd.read_csv(f)
                all_games.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {f}: {e}")

    if not all_games:
        return pd.DataFrame()

    return pd.concat(all_games, ignore_index=True)


def batch_fetch_league(
    league: str, seasons: list[str] | None = None, limit: int | None = None
) -> pd.DataFrame:
    """Fetch all games for a league."""
    # Load game index
    index_df = load_game_index(league)
    if index_df.empty:
        logger.warning(f"No game index found for {league}")
        return pd.DataFrame()

    logger.info(f"Loaded {len(index_df)} games from {league} index")

    # Filter by season if specified
    if seasons and "SEASON" in index_df.columns:
        index_df = index_df[index_df["SEASON"].isin(seasons)]
        logger.info(f"Filtered to {len(index_df)} games for seasons {seasons}")

    # Apply limit
    if limit:
        index_df = index_df.head(limit)
        logger.info(f"Limited to {limit} games")

    all_players = []
    success_count = 0
    fail_count = 0

    for _idx, row in index_df.iterrows():
        game_id = row["GAME_ID"]
        season = row.get("SEASON", "unknown")

        data = fetch_game_json(game_id)
        if data:
            players = parse_game_boxscore(data, game_id, league, season)
            all_players.extend(players)
            success_count += 1
            if success_count % 10 == 0:
                logger.info(f"Fetched {success_count}/{len(index_df)} games...")
        else:
            fail_count += 1

    logger.info(f"Completed: {success_count} success, {fail_count} failed")

    if not all_players:
        return pd.DataFrame()

    return pd.DataFrame(all_players)


def merge_to_gold(new_df: pd.DataFrame, league: str):
    """Merge new data to gold table."""
    if new_df.empty:
        logger.warning("No data to merge")
        return

    # Ensure string types for key columns
    str_cols = [
        "LEAGUE",
        "SEASON",
        "GAME_ID",
        "SOURCE_PLAYER_ID",
        "TEAM_KEY",
        "PLAYER_NAME_RAW",
        "NAME_KEY",
        "OPPONENT_KEY",
        "DNP_REASON",
        "SOURCE",
    ]
    for col in str_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str).replace("None", pd.NA)

    # Load existing gold table
    if GOLD_TABLE_PATH.exists():
        gold_df = pd.read_parquet(GOLD_TABLE_PATH)
        logger.info(f"Loaded existing gold table: {len(gold_df)} rows")

        # Remove existing rows for this league (replace)
        gold_df = gold_df[gold_df["LEAGUE"] != league]
        logger.info(f"After removing {league}: {len(gold_df)} rows")

        # Ensure type consistency in gold_df
        for col in str_cols:
            if col in gold_df.columns:
                gold_df[col] = gold_df[col].astype(str).replace("None", pd.NA)

        # Merge
        gold_df = pd.concat([gold_df, new_df], ignore_index=True)
    else:
        gold_df = new_df

    logger.info(f"New gold table: {len(gold_df)} rows")

    # Save
    GOLD_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    gold_df.to_parquet(GOLD_TABLE_PATH, index=False)
    logger.info(f"Saved to {GOLD_TABLE_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Batch fetch FIBA JSON box scores")
    parser.add_argument(
        "--league", required=True, choices=["BCL", "BAL", "LKL"], help="League to fetch"
    )
    parser.add_argument("--seasons", nargs="*", help="Seasons to fetch (e.g., 2024-25 2023-24)")
    parser.add_argument("--all-seasons", action="store_true", help="Fetch all available seasons")
    parser.add_argument("--limit", type=int, help="Limit number of games to fetch")
    parser.add_argument("--merge-gold", action="store_true", help="Merge results to gold table")

    args = parser.parse_args()

    if not args.seasons and not args.all_seasons:
        logger.error("Specify --seasons or --all-seasons")
        return

    seasons = None if args.all_seasons else args.seasons

    df = batch_fetch_league(args.league, seasons, args.limit)

    if df.empty:
        logger.warning("No data fetched")
        return

    logger.info(f"Fetched {len(df)} player-game records")

    # Save to canonical format
    output_path = OUTPUT_DIR / f"league={args.league}"
    output_path.mkdir(parents=True, exist_ok=True)

    # Save by season
    for season in df["SEASON"].unique():
        season_df = df[df["SEASON"] == season]
        season_path = output_path / f"season={season}" / "data.parquet"
        season_path.parent.mkdir(parents=True, exist_ok=True)
        season_df.to_parquet(season_path, index=False)
        logger.info(f"Saved {len(season_df)} rows to {season_path}")

    if args.merge_gold:
        merge_to_gold(df, args.league)


if __name__ == "__main__":
    main()
