#!/usr/bin/env python3
"""Bulk ingestion pipeline for LNB play-by-play and shot chart data

This script orchestrates the fetching and storage of PBP and shot data for
all games in the game index. It's designed to be resume-able, with checkpointing
and error logging.

Purpose:
    - Fetch PBP and shots for all completed games
    - Save data in partitioned Parquet format for efficient querying
    - Track progress via game index flags (has_pbp, has_shots)
    - Log errors separately without failing the entire pipeline
    - Support resume (skip already-fetched games)

Usage:
    # Ingest current season
    uv run python tools/lnb/bulk_ingest_pbp_shots.py

    # Ingest specific seasons
    uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025 2023-2024

    # Force re-fetch (ignore existing flags)
    uv run python tools/lnb/bulk_ingest_pbp_shots.py --force-refetch

    # Limit games per season (for testing)
    uv run python tools/lnb/bulk_ingest_pbp_shots.py --max-games 10

Output:
    data/raw/lnb/pbp/season=YYYY-YYYY/game_id=<uuid>.parquet
    data/raw/lnb/shots/season=YYYY-YYYY/game_id=<uuid>.parquet
    data/raw/lnb/ingestion_errors.csv - Error log
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play, fetch_lnb_shots

# ==============================================================================
# CONFIG
# ==============================================================================

# Paths
DATA_DIR = Path("data/raw/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
ERROR_LOG_FILE = DATA_DIR / "ingestion_errors.csv"

# Directories for partitioned data
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

# Rate limiting (respect API limits)
SLEEP_BETWEEN_GAMES = 1.0  # seconds

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def load_game_index() -> pd.DataFrame:
    """Load game index from Parquet

    Returns:
        Game index DataFrame
    """
    if not INDEX_FILE.exists():
        print(f"[ERROR] Game index not found: {INDEX_FILE}")
        print("[ERROR] Run: uv run python tools/lnb/build_game_index.py")
        sys.exit(1)

    try:
        df = pd.read_parquet(INDEX_FILE)
        print(f"[INFO] Loaded game index: {len(df)} games")
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load game index: {e}")
        sys.exit(1)


def save_game_index(df: pd.DataFrame) -> None:
    """Save updated game index

    Args:
        df: Updated game index DataFrame
    """
    try:
        df.to_parquet(INDEX_FILE, index=False)
    except Exception as e:
        print(f"[ERROR] Failed to save game index: {e}")


def save_partitioned_parquet(df: pd.DataFrame, data_type: str, season: str, game_id: str) -> None:
    """Save DataFrame to partitioned Parquet file

    Args:
        df: Data to save
        data_type: 'pbp' or 'shots'
        season: Season string (e.g., "2024-2025")
        game_id: Game UUID
    """
    if data_type == "pbp":
        base_dir = PBP_DIR
    elif data_type == "shots":
        base_dir = SHOTS_DIR
    else:
        raise ValueError(f"Invalid data_type: {data_type}")

    # Create season partition directory
    season_dir = base_dir / f"season={season}"
    season_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = season_dir / f"game_id={game_id}.parquet"
    df.to_parquet(file_path, index=False)


def update_index_flags(
    index_df: pd.DataFrame,
    game_id: str,
    has_pbp: bool | None = None,
    has_shots: bool | None = None,
    has_boxscore: bool | None = None,
) -> pd.DataFrame:
    """Update fetch flags in game index

    Args:
        index_df: Game index DataFrame
        game_id: Game UUID to update
        has_pbp: Update PBP flag
        has_shots: Update shots flag
        has_boxscore: Update boxscore flag

    Returns:
        Updated DataFrame
    """
    mask = index_df["game_id"] == game_id

    if has_pbp is not None:
        index_df.loc[mask, "has_pbp"] = has_pbp
        index_df.loc[mask, "pbp_fetched_at"] = datetime.now().isoformat()

    if has_shots is not None:
        index_df.loc[mask, "has_shots"] = has_shots
        index_df.loc[mask, "shots_fetched_at"] = datetime.now().isoformat()

    if has_boxscore is not None:
        index_df.loc[mask, "has_boxscore"] = has_boxscore
        index_df.loc[mask, "boxscore_fetched_at"] = datetime.now().isoformat()

    index_df.loc[mask, "last_updated"] = datetime.now().isoformat()

    return index_df


def log_error(game_id: str, season: str, data_type: str, error: str) -> None:
    """Log ingestion error to CSV

    Args:
        game_id: Game UUID
        season: Season string
        data_type: 'pbp' or 'shots'
        error: Error message
    """
    error_data = {
        "timestamp": datetime.now().isoformat(),
        "game_id": game_id,
        "season": season,
        "data_type": data_type,
        "error": error[:500],  # Truncate long errors
    }

    error_df = pd.DataFrame([error_data])

    # Append to error log
    if ERROR_LOG_FILE.exists():
        existing_errors = pd.read_csv(ERROR_LOG_FILE)
        error_df = pd.concat([existing_errors, error_df], ignore_index=True)

    error_df.to_csv(ERROR_LOG_FILE, index=False)


# ==============================================================================
# INGESTION FUNCTIONS
# ==============================================================================


def ingest_pbp_for_game(game_id: str, season: str) -> bool:
    """Fetch and save PBP data for a single game

    Args:
        game_id: Game UUID
        season: Season string

    Returns:
        True if successful, False otherwise
    """
    try:
        # Fetch PBP
        pbp_df = fetch_lnb_play_by_play(game_id)

        if pbp_df.empty:
            print(f"    [WARN] Empty PBP data for {game_id}")
            return False

        # Save to partitioned Parquet
        save_partitioned_parquet(pbp_df, "pbp", season, game_id)

        print(f"    [PBP] ✅ {len(pbp_df)} events saved")
        return True

    except Exception as e:
        print(f"    [PBP] ❌ Error: {str(e)[:100]}")
        log_error(game_id, season, "pbp", str(e))
        return False


def ingest_shots_for_game(game_id: str, season: str) -> bool:
    """Fetch and save shots data for a single game

    Args:
        game_id: Game UUID
        season: Season string

    Returns:
        True if successful, False otherwise
    """
    try:
        # Fetch shots
        shots_df = fetch_lnb_shots(game_id)

        if shots_df.empty:
            print(f"    [WARN] Empty shots data for {game_id}")
            return False

        # Save to partitioned Parquet
        save_partitioned_parquet(shots_df, "shots", season, game_id)

        print(f"    [SHOTS] ✅ {len(shots_df)} shots saved")
        return True

    except Exception as e:
        print(f"    [SHOTS] ❌ Error: {str(e)[:100]}")
        log_error(game_id, season, "shots", str(e))
        return False


# ==============================================================================
# BULK INGESTION
# ==============================================================================


def bulk_ingest(
    seasons: list[str], max_games_per_season: int | None = None, force_refetch: bool = False
) -> dict[str, Any]:
    """Bulk ingest PBP and shots data for multiple seasons

    Args:
        seasons: List of season strings
        max_games_per_season: Limit games per season (for testing)
        force_refetch: If True, re-fetch even if already fetched

    Returns:
        Dict with ingestion statistics
    """
    print(f"\n{'='*80}")
    print("  LNB BULK INGESTION - PBP + SHOTS")
    print(f"{'='*80}\n")

    print(f"Seasons: {seasons}")
    print(f"Max games per season: {max_games_per_season or 'All'}")
    print(f"Force re-fetch: {force_refetch}")
    print()

    # Load game index
    index_df = load_game_index()

    # Filter to requested seasons
    if seasons:
        index_df = index_df[index_df["season"].isin(seasons)]
        print(f"[INFO] Filtered to {len(index_df)} games in selected seasons")

    # Filter to games that need fetching
    if force_refetch:
        print("[INFO] Force re-fetch enabled - will fetch all games")
        to_fetch = index_df
    else:
        # Only fetch games that don't have PBP or shots yet
        to_fetch = index_df[(~index_df["has_pbp"]) | (~index_df["has_shots"])]
        print(f"[INFO] {len(to_fetch)} games need fetching (haven't been fetched yet)")

    # Limit games per season if specified
    if max_games_per_season:
        limited = []
        for season in seasons:
            season_games = to_fetch[to_fetch["season"] == season].head(max_games_per_season)
            limited.append(season_games)
        to_fetch = pd.concat(limited, ignore_index=True)
        print(f"[INFO] Limited to {len(to_fetch)} games (max {max_games_per_season} per season)")

    if to_fetch.empty:
        print("\n[INFO] No games to fetch!")
        return {
            "total": 0,
            "pbp_success": 0,
            "shots_success": 0,
            "both_success": 0,
            "pbp_errors": 0,
            "shots_errors": 0,
        }

    # Ingestion stats
    stats = {
        "total": len(to_fetch),
        "pbp_success": 0,
        "shots_success": 0,
        "pbp_errors": 0,
        "shots_errors": 0,
        "both_success": 0,
    }

    # Process each game
    print(f"\n[INFO] Processing {len(to_fetch)} games...\n")

    for idx, row in enumerate(to_fetch.itertuples(), 1):
        print(f"[{idx}/{len(to_fetch)}] {row.season} - {row.game_id[:16]}...")
        print(f"  Home: {row.home_team_name}")
        print(f"  Away: {row.away_team_name}")

        # Fetch PBP (if not already fetched or force_refetch)
        pbp_success = False
        if force_refetch or not row.has_pbp:
            pbp_success = ingest_pbp_for_game(row.game_id, row.season)
            if pbp_success:
                stats["pbp_success"] += 1
                index_df = update_index_flags(index_df, row.game_id, has_pbp=True)
            else:
                stats["pbp_errors"] += 1
        else:
            print("    [PBP] ⏭️  Already fetched")
            pbp_success = True

        # Fetch shots (if not already fetched or force_refetch)
        shots_success = False
        if force_refetch or not row.has_shots:
            shots_success = ingest_shots_for_game(row.game_id, row.season)
            if shots_success:
                stats["shots_success"] += 1
                index_df = update_index_flags(index_df, row.game_id, has_shots=True)
            else:
                stats["shots_errors"] += 1
        else:
            print("    [SHOTS] ⏭️  Already fetched")
            shots_success = True

        # Track both success
        if pbp_success and shots_success:
            stats["both_success"] += 1

        # Save updated index periodically (every 10 games)
        if idx % 10 == 0:
            save_game_index(index_df)

        # Rate limiting
        time.sleep(SLEEP_BETWEEN_GAMES)

        print()

    # Final save of index
    save_game_index(index_df)

    return stats


def print_summary(stats: dict[str, Any]) -> None:
    """Print ingestion summary

    Args:
        stats: Statistics dict from bulk_ingest
    """
    print(f"\n{'='*80}")
    print("  INGESTION SUMMARY")
    print(f"{'='*80}\n")

    total = stats["total"]
    pbp_success = stats["pbp_success"]
    shots_success = stats["shots_success"]
    both_success = stats["both_success"]
    pbp_errors = stats["pbp_errors"]
    shots_errors = stats["shots_errors"]

    print(f"Total games processed:    {total}")
    print(
        f"PBP success:              {pbp_success}/{total} ({pbp_success/total*100:.1f}%)"
        if total > 0
        else "PBP success:              0/0"
    )
    print(
        f"Shots success:            {shots_success}/{total} ({shots_success/total*100:.1f}%)"
        if total > 0
        else "Shots success:            0/0"
    )
    print(
        f"Both PBP + Shots:         {both_success}/{total} ({both_success/total*100:.1f}%)"
        if total > 0
        else "Both PBP + Shots:         0/0"
    )
    print()
    print(f"PBP errors:               {pbp_errors}")
    print(f"Shots errors:             {shots_errors}")
    print()

    if pbp_errors + shots_errors > 0:
        print(f"Error log saved to: {ERROR_LOG_FILE}")
    else:
        print("✅ No errors!")

    print()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Bulk ingest LNB play-by-play and shot chart data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Ingest current season
    python tools/lnb/bulk_ingest_pbp_shots.py

    # Ingest specific seasons
    python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025 2023-2024

    # Force re-fetch all games
    python tools/lnb/bulk_ingest_pbp_shots.py --force-refetch

    # Limit to 10 games per season (for testing)
    python tools/lnb/bulk_ingest_pbp_shots.py --max-games 10
        """,
    )

    parser.add_argument(
        "--seasons", nargs="+", default=None, help="Seasons to process (default: all in index)"
    )

    parser.add_argument(
        "--max-games", type=int, default=None, help="Max games per season (for testing)"
    )

    parser.add_argument(
        "--force-refetch", action="store_true", help="Re-fetch even if already fetched"
    )

    args = parser.parse_args()

    # Determine seasons
    if args.seasons:
        seasons = args.seasons
    else:
        # Use all seasons in index
        index_df = load_game_index()
        seasons = index_df["season"].unique().tolist()

    # Run bulk ingestion
    stats = bulk_ingest(
        seasons=seasons, max_games_per_season=args.max_games, force_refetch=args.force_refetch
    )

    # Print summary
    print_summary(stats)

    print(f"{'='*80}")
    print("  BULK INGESTION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
