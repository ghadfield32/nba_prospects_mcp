#!/usr/bin/env python
"""Build Game Index from Silver Layer Data

For leagues like G-League and NCAA_MBB where box_player_game data exists in the
silver layer but no game_index artifact exists, this script builds the index
from the existing data.

This is a "quick win" that makes these leagues join-ready without external scraping.

Usage:
    python scripts/build_game_index_from_silver.py --league G_LEAGUE
    python scripts/build_game_index_from_silver.py --league NCAA_MBB
    python scripts/build_game_index_from_silver.py --all
"""

import argparse
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

# Constants
BASE_DIR = Path(__file__).parent.parent.parent  # betts_basketball
SILVER_DIR = (
    BASE_DIR
    / "unified_basketball_mcp"
    / "servers"
    / "nba_prospects_mcp"
    / "data"
    / "silver"
    / "box_player_game"
)
GAME_INDEX_DIR = BASE_DIR / "nba_prospects_mcp" / "data" / "game_indexes"

# League name mappings (silver directory name -> standard name)
LEAGUE_MAPPINGS = {
    "G-League": "G_LEAGUE",
    "NCAA_MBB": "NCAA_MBB",
    "NBL": "NBL",
    "EuroLeague": "EUROLEAGUE",
    "CEBL": "CEBL",
    "OTE": "OTE",
}


def build_game_index_from_silver(
    silver_league_name: str, standard_league_name: str
) -> pd.DataFrame:
    """Build a game index from silver layer box_player_game data.

    Args:
        silver_league_name: Directory name in silver layer (e.g., "G-League")
        standard_league_name: Standardized league name (e.g., "G_LEAGUE")

    Returns:
        DataFrame with game index columns
    """
    league_dir = SILVER_DIR / f"league={silver_league_name}"

    if not league_dir.exists():
        print(f"  Silver directory not found: {league_dir}")
        return pd.DataFrame()

    all_games = []

    # Iterate through seasons
    for season_dir in sorted(league_dir.iterdir()):
        if not season_dir.is_dir():
            continue

        season = season_dir.name.replace("season=", "")
        print(f"  Processing season {season}...")

        # Load all parquet files for this season
        parquet_files = list(season_dir.glob("*.parquet"))
        if not parquet_files:
            continue

        season_dfs = []
        for pf in parquet_files:
            try:
                df = pd.read_parquet(pf)
                season_dfs.append(df)
            except Exception as e:
                print(f"    Error reading {pf}: {e}")

        if not season_dfs:
            continue

        season_df = pd.concat(season_dfs, ignore_index=True)

        # Extract unique games
        [c for c in season_df.columns if "DATE" in c.upper()]
        [c for c in season_df.columns if "TEAM" in c.upper() and "ID" not in c.upper()]

        # Try to get game date
        game_date_col = None
        for col in ["GAME_DATE", "game_date", "DATE"]:
            if col in season_df.columns:
                game_date_col = col
                break

        # Build game-level data
        if "GAME_ID" in season_df.columns:
            game_groups = season_df.groupby("GAME_ID")

            for game_id, game_df in game_groups:
                game_record = {
                    "LEAGUE": standard_league_name,
                    "SEASON": season,
                    "GAME_ID": game_id,
                }

                # Try to extract date
                if game_date_col and game_date_col in game_df.columns:
                    dates = game_df[game_date_col].dropna()
                    if len(dates) > 0:
                        game_record["GAME_DATE"] = dates.iloc[0]

                # Extract teams
                team_col = None
                for col in ["TEAM", "TEAM_NAME", "team", "team_name"]:
                    if col in game_df.columns:
                        team_col = col
                        break

                if team_col:
                    teams = game_df[team_col].unique().tolist()
                    if len(teams) >= 2:
                        game_record["HOME_TEAM"] = teams[0]
                        game_record["AWAY_TEAM"] = teams[1]
                    elif len(teams) == 1:
                        game_record["HOME_TEAM"] = teams[0]
                        game_record["AWAY_TEAM"] = None

                # Extract scores from PTS aggregation
                if "PTS" in game_df.columns and team_col:
                    try:
                        team_pts = game_df.groupby(team_col)["PTS"].sum()
                        if len(team_pts) >= 2:
                            teams = team_pts.index.tolist()
                            game_record["HOME_SCORE"] = int(team_pts.iloc[0])
                            game_record["AWAY_SCORE"] = int(team_pts.iloc[1])
                    except Exception:
                        pass

                all_games.append(game_record)

    if not all_games:
        return pd.DataFrame()

    df = pd.DataFrame(all_games)

    # Deduplicate
    df = df.drop_duplicates(subset=["GAME_ID"], keep="first")

    # Sort by date
    if "GAME_DATE" in df.columns:
        df = df.sort_values("GAME_DATE")

    return df


def write_game_index(df: pd.DataFrame, league: str) -> Path:
    """Write game index CSV files by season.

    Args:
        df: Game index DataFrame
        league: Standard league name

    Returns:
        Path to output directory
    """
    GAME_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if "SEASON" not in df.columns:
        print("  No SEASON column, writing combined file")
        output_path = GAME_INDEX_DIR / f"{league}_combined.csv"
        df.to_csv(output_path, index=False)
        return output_path

    # Write by season
    written_files = []
    for season in df["SEASON"].unique():
        season_df = df[df["SEASON"] == season]

        # Format season for filename (e.g., 2024 -> 2024_25 or 2023-24 -> 2023_24)
        season_str = str(season)
        if "-" in season_str:
            season_file = season_str.replace("-", "_")
        elif len(season_str) == 4:
            # Single year like "2024" - keep as is or convert to range
            season_file = season_str
        else:
            season_file = season_str.replace("-", "_")

        output_path = GAME_INDEX_DIR / f"{league}_{season_file}.csv"
        season_df.to_csv(output_path, index=False)
        written_files.append(output_path)
        print(f"    Wrote {len(season_df)} games to {output_path.name}")

    return GAME_INDEX_DIR


def main():
    parser = argparse.ArgumentParser(description="Build game index from silver layer")
    parser.add_argument("--league", help="Specific league to process (G_LEAGUE, NCAA_MBB, etc.)")
    parser.add_argument("--all", action="store_true", help="Process all leagues with silver data")
    args = parser.parse_args()

    print("=" * 70)
    print("BUILD GAME INDEX FROM SILVER LAYER")
    print("=" * 70)
    print()

    # Check silver directory
    if not SILVER_DIR.exists():
        print(f"Silver directory not found: {SILVER_DIR}")
        return

    # Get available leagues
    available_leagues = [d.name.replace("league=", "") for d in SILVER_DIR.iterdir() if d.is_dir()]
    print(f"Available leagues in silver: {available_leagues}")
    print()

    # Determine which leagues to process
    if args.league:
        # Map standard name to silver name
        standard_name = args.league.upper()
        silver_name = None
        for s_name, std_name in LEAGUE_MAPPINGS.items():
            if std_name == standard_name:
                silver_name = s_name
                break
        if not silver_name:
            silver_name = standard_name  # Try using as-is

        leagues_to_process = [(silver_name, standard_name)]
    elif args.all:
        leagues_to_process = []
        for silver_name in available_leagues:
            std_name = LEAGUE_MAPPINGS.get(silver_name, silver_name.upper().replace("-", "_"))
            leagues_to_process.append((silver_name, std_name))
    else:
        # Default: G-League and NCAA_MBB (leagues with data but no index)
        leagues_to_process = [
            ("G-League", "G_LEAGUE"),
            ("NCAA_MBB", "NCAA_MBB"),
        ]

    # Process each league
    for silver_name, standard_name in leagues_to_process:
        if silver_name not in available_leagues:
            print(f"\nSkipping {standard_name}: not in silver layer")
            continue

        # Check if index already exists
        existing_indexes = list(GAME_INDEX_DIR.glob(f"{standard_name}_*.csv"))
        if existing_indexes:
            print(f"\n{standard_name}: Game index already exists ({len(existing_indexes)} files)")
            continue

        print(f"\nProcessing {standard_name} (silver: {silver_name})...")

        df = build_game_index_from_silver(silver_name, standard_name)

        if df.empty:
            print(f"  No data found for {standard_name}")
            continue

        print(f"  Built index with {len(df)} games")

        # Validate
        date_coverage = df["GAME_DATE"].notna().mean() * 100 if "GAME_DATE" in df.columns else 0
        score_coverage = 0
        if "HOME_SCORE" in df.columns and "AWAY_SCORE" in df.columns:
            score_coverage = ((df["HOME_SCORE"].notna()) & (df["AWAY_SCORE"].notna())).mean() * 100

        print(f"  Date coverage: {date_coverage:.1f}%")
        print(f"  Score coverage: {score_coverage:.1f}%")

        # Write
        write_game_index(df, standard_name)

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
