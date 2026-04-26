#!/usr/bin/env python
"""Batch fetch EuroLeague historical player game data via euroleague-api.

This script fetches box scores from the EuroLeague API for missing seasons
and saves them to canonical format for merging into the gold table.

Usage:
    python scripts/batch_fetch_euroleague.py --seasons 2014 2015 2016 2017
    python scripts/batch_fetch_euroleague.py --all-missing
"""

import argparse
import logging
import time
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.parent
UNIFIED_BASE = BASE_DIR.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"

OUTPUT_DIR = UNIFIED_BASE / "data" / "canonical" / "box_player_game"
GOLD_TABLE_PATH = BASE_DIR / "data" / "gold" / "player_career_game.parquet"

# Missing seasons to backfill (API uses season year, e.g., 2014 = 2014-15 season)
MISSING_SEASONS = [2014, 2015, 2016, 2017]


def season_year_to_display(year: int) -> str:
    """Convert API season year to display format (2014 -> 2014-15)."""
    return f"{year}-{str(year + 1)[-2:]}"


def fetch_season_boxscores(season: int) -> pd.DataFrame:
    """Fetch all player box scores for a season from EuroLeague API."""
    from euroleague_api.boxscore_data import BoxScoreData

    logger.info(f"Fetching EuroLeague season {season} ({season_year_to_display(season)})...")

    try:
        box = BoxScoreData()
        df = box.get_player_boxscore_stats_single_season(season=season)

        if df is None or df.empty:
            logger.warning(f"No data returned for season {season}")
            return pd.DataFrame()

        logger.info(f"Retrieved {len(df)} player-game records for season {season}")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch season {season}: {e}")
        return pd.DataFrame()


def canonicalize_euroleague(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """Convert EuroLeague API data to canonical schema."""
    if df.empty:
        return pd.DataFrame()

    season_str = season_year_to_display(season)

    # Map EuroLeague API columns to canonical schema
    # API columns: Season, Phase, Round, Gamecode, Date, Home, Away,
    #              Player_ID, Dorsal, Player, Minutes, Points, FieldGoalsMade2,
    #              FieldGoalsAttempted2, FieldGoalsMade3, FieldGoalsAttempted3,
    #              FreeThrowsMade, FreeThrowsAttempted, OffensiveRebounds,
    #              DefensiveRebounds, TotalRebounds, Assistances, Steals,
    #              Turnovers, BlocksFavour, BlocksAgainst, FoulsCommited,
    #              FoulsReceived, Valuation, Team

    records = []

    for _, row in df.iterrows():
        # Parse minutes (format: "MM:SS" or numeric)
        minutes = 0
        if pd.notna(row.get("Minutes")):
            min_val = row["Minutes"]
            if isinstance(min_val, str) and ":" in min_val:
                parts = min_val.split(":")
                minutes = int(parts[0]) + int(parts[1]) / 60
            else:
                try:
                    minutes = float(min_val)
                except (ValueError, TypeError):
                    minutes = 0

        # Generate NAME_KEY from player name
        player_name = str(row.get("Player", "")).strip()
        name_key = player_name.lower().replace(" ", "_").replace(".", "")
        name_key = "".join(c for c in name_key if c.isalnum() or c == "_")

        # Determine home/away
        team = str(row.get("Team", ""))
        home_team = str(row.get("Home", ""))
        away_team = str(row.get("Away", ""))
        is_home = team == home_team
        opponent = away_team if is_home else home_team

        # Calculate FGM/FGA (2PT + 3PT)
        fg2m = int(row.get("FieldGoalsMade2", 0) or 0)
        fg2a = int(row.get("FieldGoalsAttempted2", 0) or 0)
        fg3m = int(row.get("FieldGoalsMade3", 0) or 0)
        fg3a = int(row.get("FieldGoalsAttempted3", 0) or 0)

        records.append(
            {
                "LEAGUE": "EUROLEAGUE",
                "SEASON": season_str,
                "GAME_ID": f"EUROLEAGUE_{row.get('Gamecode', '')}",
                "GAME_DATE": pd.to_datetime(row.get("Date")).strftime("%Y-%m-%d")
                if pd.notna(row.get("Date"))
                else None,
                "TEAM_KEY": team,
                "SOURCE_PLAYER_ID": f"EURO_{row.get('Player_ID', '')}",
                "PLAYER_NAME_RAW": player_name,
                "NAME_KEY": name_key,
                "OPPONENT_KEY": opponent,
                "IS_HOME": is_home,
                "MIN": round(minutes, 1),
                "PTS": int(row.get("Points", 0) or 0),
                "FGM": fg2m + fg3m,
                "FGA": fg2a + fg3a,
                "FG3M": fg3m,
                "FG3A": fg3a,
                "FTM": int(row.get("FreeThrowsMade", 0) or 0),
                "FTA": int(row.get("FreeThrowsAttempted", 0) or 0),
                "OREB": int(row.get("OffensiveRebounds", 0) or 0),
                "DREB": int(row.get("DefensiveRebounds", 0) or 0),
                "TRB": int(row.get("TotalRebounds", 0) or 0),
                "AST": int(row.get("Assistances", 0) or 0),
                "STL": int(row.get("Steals", 0) or 0),
                "BLK": int(row.get("BlocksFavour", 0) or 0),
                "TOV": int(row.get("Turnovers", 0) or 0),
                "PF": int(row.get("FoulsCommited", 0) or 0),
                "PLUS_MINUS": None,
                "STARTER": None,
                "DNP_REASON": None,
                "SOURCE": "euroleague_api",
            }
        )

    return pd.DataFrame(records)


def merge_to_gold(new_df: pd.DataFrame, seasons: list[int]):
    """Merge new data to gold table."""
    if new_df.empty:
        logger.warning("No data to merge")
        return

    # Load existing gold table
    if GOLD_TABLE_PATH.exists():
        gold_df = pd.read_parquet(GOLD_TABLE_PATH)
        logger.info(f"Loaded existing gold table: {len(gold_df)} rows")

        # Remove existing rows for these seasons (replace)
        season_strs = [season_year_to_display(s) for s in seasons]
        mask = ~((gold_df["LEAGUE"] == "EUROLEAGUE") & (gold_df["SEASON"].isin(season_strs)))
        gold_df = gold_df[mask]
        logger.info(f"After removing EUROLEAGUE seasons {season_strs}: {len(gold_df)} rows")

        # Merge
        gold_df = pd.concat([gold_df, new_df], ignore_index=True)
    else:
        gold_df = new_df

    logger.info(f"New gold table: {len(gold_df)} rows")

    # Save
    GOLD_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    gold_df.to_parquet(GOLD_TABLE_PATH, index=False)
    logger.info(f"Saved to {GOLD_TABLE_PATH}")


def save_canonical(df: pd.DataFrame, season: int):
    """Save to canonical format (Hive-partitioned)."""
    if df.empty:
        return

    season_str = season_year_to_display(season)
    output_path = OUTPUT_DIR / "league=EUROLEAGUE" / f"season={season_str}" / "data.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch fetch EuroLeague box scores")
    parser.add_argument(
        "--seasons", nargs="*", type=int, help="Seasons to fetch (e.g., 2014 2015 2016 2017)"
    )
    parser.add_argument(
        "--all-missing", action="store_true", help="Fetch all missing seasons (2014-2017)"
    )
    parser.add_argument("--merge-gold", action="store_true", help="Merge results to gold table")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be fetched without fetching"
    )

    args = parser.parse_args()

    if args.all_missing:
        seasons = MISSING_SEASONS
    elif args.seasons:
        seasons = args.seasons
    else:
        logger.error("Specify --seasons or --all-missing")
        return

    logger.info(f"Will fetch EuroLeague seasons: {seasons}")

    if args.dry_run:
        logger.info("DRY RUN - would fetch:")
        for s in seasons:
            logger.info(f"  - Season {s} ({season_year_to_display(s)})")
        return

    all_records = []

    for season in seasons:
        # Fetch from API
        raw_df = fetch_season_boxscores(season)

        if raw_df.empty:
            continue

        # Canonicalize
        canon_df = canonicalize_euroleague(raw_df, season)

        # Save canonical partition
        save_canonical(canon_df, season)

        all_records.append(canon_df)

        # Rate limit between seasons
        time.sleep(1)

    if not all_records:
        logger.warning("No data fetched")
        return

    combined_df = pd.concat(all_records, ignore_index=True)
    logger.info(
        f"Total fetched: {len(combined_df)} player-game records across {len(seasons)} seasons"
    )

    if args.merge_gold:
        merge_to_gold(combined_df, seasons)


if __name__ == "__main__":
    main()
