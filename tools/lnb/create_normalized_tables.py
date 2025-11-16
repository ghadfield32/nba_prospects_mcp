#!/usr/bin/env python3
"""Create normalized LNB tables for forecasting pipeline integration

This script transforms raw PBP and shots data into standardized schemas:
1. LNB_PLAYER_GAME - Player box score per game (compatible with forecasting)
2. LNB_TEAM_GAME - Team box score per game (compatible with forecasting)
3. LNB_SHOT_EVENTS - Unified shot table (compatible with other leagues)

Purpose:
    - Aggregate PBP events into traditional box score stats
    - Standardize column naming across all leagues
    - Enable cross-league forecasting and analysis
    - Support efficient querying via partitioned Parquet

Usage:
    # Transform all seasons
    uv run python tools/lnb/create_normalized_tables.py

    # Transform specific season
    uv run python tools/lnb/create_normalized_tables.py --season 2024-2025

    # Force rebuild (ignore existing normalized tables)
    uv run python tools/lnb/create_normalized_tables.py --force

Output:
    data/normalized/lnb/player_game/season=YYYY-YYYY/game_id=<uuid>.parquet
    data/normalized/lnb/team_game/season=YYYY-YYYY/game_id=<uuid>.parquet
    data/normalized/lnb/shot_events/season=YYYY-YYYY/game_id=<uuid>.parquet
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

# Paths
DATA_DIR = Path("data/raw/lnb")
NORMALIZED_DIR = Path("data/normalized/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"

PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

PLAYER_GAME_DIR = NORMALIZED_DIR / "player_game"
TEAM_GAME_DIR = NORMALIZED_DIR / "team_game"
SHOT_EVENTS_DIR = NORMALIZED_DIR / "shot_events"

# Create output directories
for dir_path in [PLAYER_GAME_DIR, TEAM_GAME_DIR, SHOT_EVENTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def parse_clock_to_seconds(clock_str: str) -> float:
    """Convert PT10M0S format to seconds

    Args:
        clock_str: Clock string in ISO 8601 duration format (e.g., "PT10M0S")

    Returns:
        Seconds remaining in period
    """
    try:
        if pd.isna(clock_str) or not isinstance(clock_str, str):
            return 0.0

        # Remove PT prefix
        time_str = clock_str.replace("PT", "")

        minutes = 0
        seconds = 0

        # Extract minutes
        if "M" in time_str:
            parts = time_str.split("M")
            minutes = int(parts[0])
            time_str = parts[1]

        # Extract seconds
        if "S" in time_str:
            seconds = float(time_str.replace("S", ""))

        return minutes * 60 + seconds

    except Exception:
        return 0.0


def calculate_shot_distance(x: float, y: float) -> float:
    """Calculate shot distance from basket in feet

    Court dimensions: 0-100 scale (percentage-based)
    Basket location: (4.2, 50) in percentage coordinates

    Args:
        x: X coordinate (0-100 scale)
        y: Y coordinate (0-100 scale)

    Returns:
        Distance in feet (using 94ft court length conversion)
    """
    try:
        if pd.isna(x) or pd.isna(y):
            return np.nan

        # Basket location (percentage coordinates)
        basket_x = 4.2
        basket_y = 50.0

        # Calculate distance in percentage points
        dx = x - basket_x
        dy = y - basket_y
        dist_pct = np.sqrt(dx**2 + dy**2)

        # Convert to feet (94ft court length)
        dist_feet = dist_pct * 0.94

        return round(dist_feet, 1)

    except Exception:
        return np.nan


def classify_shot_zone(x: float, y: float, shot_type: str) -> str:
    """Classify shot zone based on coordinates

    Zones: Paint, Mid-Range, Three-Point (Corner), Three-Point (Wing), Three-Point (Top)

    Args:
        x: X coordinate (0-100 scale)
        y: Y coordinate (0-100 scale)
        shot_type: '2pt' or '3pt'

    Returns:
        Shot zone classification
    """
    try:
        if pd.isna(x) or pd.isna(y):
            return "Unknown"

        if shot_type == "3pt":
            # Three-point zones
            if y < 22 or y > 78:
                return "Three-Point (Corner)"
            elif y < 35 or y > 65:
                return "Three-Point (Wing)"
            else:
                return "Three-Point (Top)"
        else:
            # Two-point zones
            if x < 19:  # In the paint (under basket to free throw line)
                return "Paint"
            else:
                return "Mid-Range"

    except Exception:
        return "Unknown"


# ==============================================================================
# TRANSFORMATION FUNCTIONS
# ==============================================================================


def create_player_game_stats(game_id: str, season: str) -> pd.DataFrame:
    """Create player box score from PBP and shots data

    Args:
        game_id: Game UUID
        season: Season string (e.g., "2024-2025")

    Returns:
        DataFrame with player box score stats
    """
    # Load PBP data
    pbp_file = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
    shots_file = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

    if not pbp_file.exists() or not shots_file.exists():
        return pd.DataFrame()

    pbp_df = pd.read_parquet(pbp_file)
    shots_df = pd.read_parquet(shots_file)

    # Initialize stats dictionary
    player_stats = {}

    # Count stats from PBP
    for _, event in pbp_df.iterrows():
        if pd.isna(event["PLAYER_ID"]):
            continue

        player_id = event["PLAYER_ID"]
        event_type = event["EVENT_TYPE"]

        if player_id not in player_stats:
            player_stats[player_id] = {
                "PLAYER_NAME": event["PLAYER_NAME"],
                "TEAM_ID": event["TEAM_ID"],
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TOV": 0,
                "PF": 0,
                "REB": 0,
            }

        # Count events
        if event_type == "assist":
            player_stats[player_id]["AST"] += 1
        elif event_type == "steal":
            player_stats[player_id]["STL"] += 1
        elif event_type == "block":
            player_stats[player_id]["BLK"] += 1
        elif event_type == "turnover":
            player_stats[player_id]["TOV"] += 1
        elif event_type == "foul":
            player_stats[player_id]["PF"] += 1
        elif event_type == "rebound":
            player_stats[player_id]["REB"] += 1

    # Count shooting stats from shots table
    for player_id in shots_df["PLAYER_ID"].unique():
        if pd.isna(player_id):
            continue

        player_shots = shots_df[shots_df["PLAYER_ID"] == player_id]

        if player_id not in player_stats:
            player_stats[player_id] = {
                "PLAYER_NAME": player_shots.iloc[0]["PLAYER_NAME"],
                "TEAM_ID": player_shots.iloc[0]["TEAM_ID"],
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TOV": 0,
                "PF": 0,
                "REB": 0,
            }

        # 2-point stats
        fg2_shots = player_shots[player_shots["SHOT_TYPE"] == "2pt"]
        player_stats[player_id]["FG2M"] = int(fg2_shots["SUCCESS"].sum())
        player_stats[player_id]["FG2A"] = len(fg2_shots)

        # 3-point stats
        fg3_shots = player_shots[player_shots["SHOT_TYPE"] == "3pt"]
        player_stats[player_id]["FG3M"] = int(fg3_shots["SUCCESS"].sum())
        player_stats[player_id]["FG3A"] = len(fg3_shots)

        # Free throws (from PBP events)
        ft_events = pbp_df[
            (pbp_df["PLAYER_ID"] == player_id) & (pbp_df["EVENT_TYPE"] == "freeThrow")
        ]
        player_stats[player_id]["FTM"] = int(ft_events["SUCCESS"].sum())
        player_stats[player_id]["FTA"] = len(ft_events)

    # Convert to DataFrame
    rows = []
    for player_id, stats in player_stats.items():
        # Calculate totals
        fg2m = stats.get("FG2M", 0)
        fg2a = stats.get("FG2A", 0)
        fg3m = stats.get("FG3M", 0)
        fg3a = stats.get("FG3A", 0)
        ftm = stats.get("FTM", 0)
        fta = stats.get("FTA", 0)

        fgm = fg2m + fg3m
        fga = fg2a + fg3a
        pts = (fg2m * 2) + (fg3m * 3) + ftm

        # Calculate percentages
        fg_pct = fgm / fga if fga > 0 else 0.0
        fg2_pct = fg2m / fg2a if fg2a > 0 else 0.0
        fg3_pct = fg3m / fg3a if fg3a > 0 else 0.0
        ft_pct = ftm / fta if fta > 0 else 0.0

        rows.append(
            {
                "GAME_ID": game_id,
                "PLAYER_ID": player_id,
                "PLAYER_NAME": stats["PLAYER_NAME"],
                "TEAM_ID": stats["TEAM_ID"],
                "MIN": 0.0,  # TODO: Calculate from substitution events
                "PTS": pts,
                "FGM": fgm,
                "FGA": fga,
                "FG_PCT": round(fg_pct, 3),
                "FG2M": fg2m,
                "FG2A": fg2a,
                "FG2_PCT": round(fg2_pct, 3),
                "FG3M": fg3m,
                "FG3A": fg3a,
                "FG3_PCT": round(fg3_pct, 3),
                "FTM": ftm,
                "FTA": fta,
                "FT_PCT": round(ft_pct, 3),
                "REB": stats["REB"],
                "AST": stats["AST"],
                "STL": stats["STL"],
                "BLK": stats["BLK"],
                "TOV": stats["TOV"],
                "PF": stats["PF"],
                "PLUS_MINUS": 0,  # TODO: Calculate from score progression
                "SEASON": season,
                "LEAGUE": "LNB_PROA",
            }
        )

    return pd.DataFrame(rows)


def create_team_game_stats(player_game_df: pd.DataFrame, game_id: str, season: str) -> pd.DataFrame:
    """Create team box score from player stats

    Args:
        player_game_df: Player box score DataFrame
        game_id: Game UUID
        season: Season string

    Returns:
        DataFrame with team box score stats
    """
    if player_game_df.empty:
        return pd.DataFrame()

    # Group by team
    team_stats = []

    teams = player_game_df["TEAM_ID"].unique()

    for team_id in teams:
        team_players = player_game_df[player_game_df["TEAM_ID"] == team_id]

        # Sum stats
        team_stat = {
            "GAME_ID": game_id,
            "TEAM_ID": team_id,
            "PTS": int(team_players["PTS"].sum()),
            "FGM": int(team_players["FGM"].sum()),
            "FGA": int(team_players["FGA"].sum()),
            "FG2M": int(team_players["FG2M"].sum()),
            "FG2A": int(team_players["FG2A"].sum()),
            "FG3M": int(team_players["FG3M"].sum()),
            "FG3A": int(team_players["FG3A"].sum()),
            "FTM": int(team_players["FTM"].sum()),
            "FTA": int(team_players["FTA"].sum()),
            "REB": int(team_players["REB"].sum()),
            "AST": int(team_players["AST"].sum()),
            "STL": int(team_players["STL"].sum()),
            "BLK": int(team_players["BLK"].sum()),
            "TOV": int(team_players["TOV"].sum()),
            "PF": int(team_players["PF"].sum()),
        }

        # Calculate percentages
        team_stat["FG_PCT"] = (
            round(team_stat["FGM"] / team_stat["FGA"], 3) if team_stat["FGA"] > 0 else 0.0
        )
        team_stat["FG2_PCT"] = (
            round(team_stat["FG2M"] / team_stat["FG2A"], 3) if team_stat["FG2A"] > 0 else 0.0
        )
        team_stat["FG3_PCT"] = (
            round(team_stat["FG3M"] / team_stat["FG3A"], 3) if team_stat["FG3A"] > 0 else 0.0
        )
        team_stat["FT_PCT"] = (
            round(team_stat["FTM"] / team_stat["FTA"], 3) if team_stat["FTA"] > 0 else 0.0
        )

        team_stat["SEASON"] = season
        team_stat["LEAGUE"] = "LNB_PROA"

        team_stats.append(team_stat)

    # Add opponent stats
    if len(team_stats) == 2:
        team_stats[0]["OPP_ID"] = team_stats[1]["TEAM_ID"]
        team_stats[0]["OPP_PTS"] = team_stats[1]["PTS"]
        team_stats[0]["WIN"] = 1 if team_stats[0]["PTS"] > team_stats[1]["PTS"] else 0

        team_stats[1]["OPP_ID"] = team_stats[0]["TEAM_ID"]
        team_stats[1]["OPP_PTS"] = team_stats[0]["PTS"]
        team_stats[1]["WIN"] = 1 if team_stats[1]["PTS"] > team_stats[0]["PTS"] else 0

    return pd.DataFrame(team_stats)


def create_shot_events(game_id: str, season: str) -> pd.DataFrame:
    """Transform shots data into standardized shot events table

    Args:
        game_id: Game UUID
        season: Season string

    Returns:
        DataFrame with standardized shot events
    """
    shots_file = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

    if not shots_file.exists():
        return pd.DataFrame()

    shots_df = pd.read_parquet(shots_file)

    # Transform to standardized schema
    shot_events = shots_df.copy()

    # Add calculated fields
    shot_events["CLOCK_SECONDS"] = shot_events["CLOCK"].apply(parse_clock_to_seconds)
    shot_events["SHOT_DISTANCE"] = shot_events.apply(
        lambda row: calculate_shot_distance(row["X_COORD"], row["Y_COORD"]), axis=1
    )
    shot_events["SHOT_ZONE"] = shot_events.apply(
        lambda row: classify_shot_zone(row["X_COORD"], row["Y_COORD"], row["SHOT_TYPE"]), axis=1
    )
    shot_events["POINTS"] = shot_events.apply(
        lambda row: (2 if row["SHOT_TYPE"] == "2pt" else 3) if row["SUCCESS"] else 0, axis=1
    )

    # Standardize column names
    shot_events = shot_events.rename(
        columns={"PERIOD_ID": "PERIOD", "SUCCESS": "MADE", "X_COORD": "X", "Y_COORD": "Y"}
    )

    # Select final columns
    final_columns = [
        "GAME_ID",
        "EVENT_ID",
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "PERIOD",
        "CLOCK",
        "CLOCK_SECONDS",
        "SHOT_TYPE",
        "SHOT_SUBTYPE",
        "SHOT_ZONE",
        "SHOT_DISTANCE",
        "X",
        "Y",
        "MADE",
        "POINTS",
        "DESCRIPTION",
        "LEAGUE",
    ]

    shot_events = shot_events[final_columns]
    shot_events["SEASON"] = season

    return shot_events


# ==============================================================================
# TRANSFORMATION PIPELINE
# ==============================================================================


def transform_game(game_id: str, season: str, force: bool = False) -> dict[str, bool]:
    """Transform all normalized tables for a single game

    Args:
        game_id: Game UUID
        season: Season string
        force: If True, rebuild even if already exists

    Returns:
        Dict with success status for each table type
    """
    results = {"player_game": False, "team_game": False, "shot_events": False}

    # Check if already transformed (unless force rebuild)
    season_dir_player = PLAYER_GAME_DIR / f"season={season}"
    season_dir_team = TEAM_GAME_DIR / f"season={season}"
    season_dir_shots = SHOT_EVENTS_DIR / f"season={season}"

    player_file = season_dir_player / f"game_id={game_id}.parquet"
    team_file = season_dir_team / f"game_id={game_id}.parquet"
    shots_file = season_dir_shots / f"game_id={game_id}.parquet"

    if not force and player_file.exists() and team_file.exists() and shots_file.exists():
        print("    [SKIP] Already transformed")
        return {"player_game": True, "team_game": True, "shot_events": True}

    # Create season directories
    for season_dir in [season_dir_player, season_dir_team, season_dir_shots]:
        season_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Create player game stats
        player_game_df = create_player_game_stats(game_id, season)
        if not player_game_df.empty:
            player_game_df.to_parquet(player_file, index=False)
            results["player_game"] = True
            print(f"    [PLAYER_GAME] ✅ {len(player_game_df)} players")

        # Create team game stats
        team_game_df = create_team_game_stats(player_game_df, game_id, season)
        if not team_game_df.empty:
            team_game_df.to_parquet(team_file, index=False)
            results["team_game"] = True
            print(f"    [TEAM_GAME] ✅ {len(team_game_df)} teams")

        # Create shot events
        shot_events_df = create_shot_events(game_id, season)
        if not shot_events_df.empty:
            shot_events_df.to_parquet(shots_file, index=False)
            results["shot_events"] = True
            print(f"    [SHOT_EVENTS] ✅ {len(shot_events_df)} shots")

    except Exception as e:
        print(f"    [ERROR] Transformation failed: {str(e)[:100]}")

    return results


def transform_season(season: str, force: bool = False) -> dict[str, Any]:
    """Transform all games in a season

    Args:
        season: Season string (e.g., "2024-2025")
        force: If True, rebuild even if already exists

    Returns:
        Dict with transformation statistics
    """
    print(f"\n[TRANSFORMING] Season {season}...")

    # Find all games with PBP data
    season_pbp_dir = PBP_DIR / f"season={season}"
    if not season_pbp_dir.exists():
        print(f"  [WARN] No PBP data for season {season}")
        return {"total": 0, "player_game": 0, "team_game": 0, "shot_events": 0}

    pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))

    # Read UUID from data (not filename) to prevent propagating corruption
    game_ids = []
    for pbp_file in pbp_files:
        try:
            df = pd.read_parquet(pbp_file)

            if len(df) == 0:
                print(f"    [WARN] Empty file: {pbp_file.name}")
                continue

            # Extract UUIDs
            data_game_id = str(df["GAME_ID"].iloc[0])
            filename_game_id = pbp_file.stem.replace("game_id=", "")

            # VALIDATE: Filename must match data UUID
            if data_game_id != filename_game_id:
                print(f"    [ERROR] UUID MISMATCH in {pbp_file.name}:")
                print(f"            Filename: {filename_game_id}")
                print(f"            Data:     {data_game_id}")
                print("            SKIPPING - clean up raw data first!")
                continue

            # Use validated UUID from data
            game_ids.append(data_game_id)

        except Exception as e:
            print(f"    [ERROR] Failed to process {pbp_file.name}: {str(e)}")
            continue

    print(f"  Found {len(game_ids)} games to transform")

    stats = {"total": len(game_ids), "player_game": 0, "team_game": 0, "shot_events": 0}

    for idx, game_id in enumerate(game_ids, 1):
        print(f"  [{idx}/{len(game_ids)}] {game_id[:16]}...")

        results = transform_game(game_id, season, force)

        if results["player_game"]:
            stats["player_game"] += 1
        if results["team_game"]:
            stats["team_game"] += 1
        if results["shot_events"]:
            stats["shot_events"] += 1

    return stats


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Create normalized LNB tables for forecasting pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Transform all seasons
    uv run python tools/lnb/create_normalized_tables.py

    # Transform specific season
    uv run python tools/lnb/create_normalized_tables.py --season 2024-2025

    # Force rebuild
    uv run python tools/lnb/create_normalized_tables.py --force

Output:
    data/normalized/lnb/player_game/season=YYYY-YYYY/*.parquet
    data/normalized/lnb/team_game/season=YYYY-YYYY/*.parquet
    data/normalized/lnb/shot_events/season=YYYY-YYYY/*.parquet
        """,
    )

    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help="Season to transform (default: all seasons with PBP data)",
    )

    parser.add_argument("--force", action="store_true", help="Force rebuild even if already exists")

    args = parser.parse_args()

    print(f"{'='*80}")
    print("  LNB NORMALIZED TABLES - TRANSFORMATION")
    print(f"{'='*80}\n")

    # Determine seasons to transform
    if args.season:
        seasons = [args.season]
    else:
        # Find all seasons with PBP data
        if PBP_DIR.exists():
            season_dirs = [d.name.replace("season=", "") for d in PBP_DIR.iterdir() if d.is_dir()]
            seasons = sorted(season_dirs, reverse=True)
        else:
            print("[ERROR] No PBP data directory found")
            sys.exit(1)

    if not seasons:
        print("[ERROR] No seasons found to transform")
        sys.exit(1)

    print(f"Transforming seasons: {seasons}")
    print(f"Force rebuild: {args.force}\n")

    # Transform all seasons
    all_stats = {"total": 0, "player_game": 0, "team_game": 0, "shot_events": 0}

    for season in seasons:
        season_stats = transform_season(season, args.force)

        all_stats["total"] += season_stats["total"]
        all_stats["player_game"] += season_stats["player_game"]
        all_stats["team_game"] += season_stats["team_game"]
        all_stats["shot_events"] += season_stats["shot_events"]

    # Print summary
    print(f"\n{'='*80}")
    print("  TRANSFORMATION SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total games processed:     {all_stats['total']}")
    print(f"Player game success:       {all_stats['player_game']}/{all_stats['total']}")
    print(f"Team game success:         {all_stats['team_game']}/{all_stats['total']}")
    print(f"Shot events success:       {all_stats['shot_events']}/{all_stats['total']}")
    print()

    print(f"{'='*80}")
    print("  TRANSFORMATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
