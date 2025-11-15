#!/usr/bin/env python3
"""Build canonical game index for LNB Pro A

This script creates and maintains the master game index that serves as the
single source of truth for all LNB data pipelines. It combines data from
multiple sources (schedule scraping, UUID discovery) into one unified table.

Purpose:
    - Create canonical table linking LNB game IDs to Atrium fixture UUIDs
    - Track which data has been fetched for each game
    - Support incremental updates without rebuilding from scratch
    - Enable efficient filtering for bulk ingestion pipelines

Usage:
    # Build index for current season
    uv run python tools/lnb/build_game_index.py

    # Build for specific seasons
    uv run python tools/lnb/build_game_index.py --seasons 2024-2025 2023-2024

    # Force rebuild (ignore existing index)
    uv run python tools/lnb/build_game_index.py --force-rebuild

Output:
    data/raw/lnb/lnb_game_index.parquet - Master game index (Parquet format)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from src.cbb_data.fetchers.lnb import fetch_lnb_schedule

# ==============================================================================
# CONFIG
# ==============================================================================

# Default seasons to process
DEFAULT_SEASONS = ["2024-2025"]

# Output paths
OUTPUT_DIR = Path("data/raw/lnb")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = OUTPUT_DIR / "lnb_game_index.parquet"

# Fixture UUID extraction (from tools created earlier)
FIXTURE_UUIDS_FILE = Path("tools/lnb/fixture_uuids_for_stress_test.json")

# Per-season UUID mappings (new approach for historical coverage)
UUID_MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")
TOOLS_DIR = Path("tools/lnb")

# ==============================================================================
# GAME INDEX SCHEMA
# ==============================================================================

INDEX_SCHEMA = {
    "season": "string",  # "2024-2025"
    "competition": "string",  # "Betclic ELITE", "Leaders Cup", etc.
    "game_id": "string",  # Atrium UUID (PRIMARY KEY)
    "lnb_match_id": "string",  # LNB numeric ID (if available)
    "game_date": "string",  # ISO format date
    "home_team_id": "string",
    "home_team_name": "string",
    "away_team_id": "string",
    "away_team_name": "string",
    "status": "string",  # "Final", "Scheduled", etc.
    "has_pbp": "bool",  # Track what's been fetched
    "has_shots": "bool",
    "has_boxscore": "bool",
    "pbp_fetched_at": "string",  # ISO datetime
    "shots_fetched_at": "string",
    "boxscore_fetched_at": "string",
    "last_updated": "string",  # ISO datetime
}

# ==============================================================================
# FIXTURE UUID DISCOVERY
# ==============================================================================


def load_discovered_fixture_uuids() -> dict[str, list[str]]:
    """Load fixture UUIDs from the discovery JSON file

    Returns:
        Dict mapping 'current_season' to list of UUIDs
    """
    if not FIXTURE_UUIDS_FILE.exists():
        print(f"[WARN] Fixture UUIDs file not found: {FIXTURE_UUIDS_FILE}")
        print("[WARN] Run: uv run python tools/lnb/extract_fixture_uuids_from_schedule.py")
        return {}

    try:
        with open(FIXTURE_UUIDS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        uuids = data.get("fixture_uuids", [])
        print(f"[INFO] Loaded {len(uuids)} fixture UUIDs from {FIXTURE_UUIDS_FILE}")

        # For now, we assume these are all current season
        # Future: could parse extracted_at date to determine season
        return {"current_season": uuids}

    except Exception as e:
        print(f"[ERROR] Failed to load fixture UUIDs: {e}")
        return {}


def load_fixture_uuids_by_season() -> dict[str, list[str]]:
    """Load fixture UUID mappings from JSON file

    This loads the per-season UUID mappings created by discover_historical_fixture_uuids.py

    Returns:
        Dict mapping season -> list of fixture UUIDs
        Example: {"2024-2025": ["uuid1", "uuid2"], "2023-2024": ["uuid3"]}
    """
    if not UUID_MAPPING_FILE.exists():
        print(f"[WARN] No UUID mapping file found: {UUID_MAPPING_FILE}")
        print("[WARN] Run: uv run python tools/lnb/discover_historical_fixture_uuids.py")
        return {}

    try:
        with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
            data = json.load(f)
            mappings = data.get("mappings", {})
            print(
                f"[INFO] Loaded UUID mappings for {len(mappings)} seasons from {UUID_MAPPING_FILE.name}"
            )
            for season, uuids in mappings.items():
                print(f"       {season}: {len(uuids)} fixture UUIDs")
            return mappings
    except Exception as e:
        print(f"[ERROR] Failed to load UUID mappings: {e}")
        return {}


# ==============================================================================
# GAME INDEX BUILDER
# ==============================================================================


def build_index_for_season(
    season: str,
    discovered_uuids: dict[str, list[str]] = None,
    uuid_mappings: dict[str, list[str]] = None,
) -> pd.DataFrame:
    """Build game index for a single season

    Args:
        season: Season string (e.g., "2024-2025")
        discovered_uuids: Dict of discovered fixture UUIDs by season (legacy)
        uuid_mappings: Dict mapping season -> list of UUIDs from JSON file (preferred)

    Returns:
        DataFrame with game index for this season
    """
    if discovered_uuids is None:
        discovered_uuids = {}
    if uuid_mappings is None:
        uuid_mappings = {}
    print(f"\n[BUILDING] Game index for season {season}...")

    try:
        # Get fixture UUIDs for this season from mapping file (preferred) or legacy source
        fixture_uuids = []
        if uuid_mappings and season in uuid_mappings:
            fixture_uuids = uuid_mappings[season]
            print(f"  [INFO] Using {len(fixture_uuids)} fixture UUIDs from mapping file")
        else:
            # Fallback: try old discovered_uuids for backward compatibility
            if season == "2024-2025":
                fixture_uuids = discovered_uuids.get("current_season", [])
                if fixture_uuids:
                    print(f"  [INFO] Using {len(fixture_uuids)} UUIDs from legacy discovered_uuids")

        # CRITICAL FIX: Only create index entries for confirmed UUIDs, not schedule placeholders
        # This prevents synthetic IDs from polluting the index
        if not fixture_uuids:
            print(f"  [WARN] No fixture UUIDs for {season} - skipping")
            return pd.DataFrame()

        print(f"  [INFO] Creating index entries for {len(fixture_uuids)} confirmed games")

        # Initialize index DataFrame with proper schema
        index_data = []

        # Create one index entry per confirmed UUID
        for game_id in fixture_uuids:
            # Try to get metadata from schedule if available
            try:
                fetch_lnb_schedule(season=season)
            except Exception:
                pass  # Schedule not critical, we have UUIDs

            # Default metadata (will be populated during ingestion)
            index_row = {
                "season": season,
                "competition": "LNB Pro A",
                "game_id": game_id,
                "lnb_match_id": game_id,  # Use UUID as match ID
                "game_date": "",
                "home_team_id": "",
                "home_team_name": "",
                "away_team_id": "",
                "away_team_name": "",
                "status": "Completed",
                "has_pbp": False,
                "has_shots": False,
                "has_boxscore": False,
                "pbp_fetched_at": "",
                "shots_fetched_at": "",
                "boxscore_fetched_at": "",
                "last_updated": datetime.now().isoformat(),
            }
            index_data.append(index_row)

        index_df = pd.DataFrame(index_data)

        print(f"  [SUCCESS] Built index with {len(index_df)} games")
        return index_df

    except Exception as e:
        print(f"  [ERROR] Failed to build index for {season}: {e}")
        import traceback

        traceback.print_exc()
        return pd.DataFrame()


def merge_with_existing_index(new_df: pd.DataFrame, index_path: Path) -> pd.DataFrame:
    """Merge new data with existing index

    Args:
        new_df: New game index data
        index_path: Path to existing index file

    Returns:
        Merged DataFrame
    """
    if not index_path.exists():
        print("[INFO] No existing index found, creating new one")
        return new_df

    try:
        # Load existing index
        existing_df = pd.read_parquet(index_path)
        print(f"[INFO] Loaded existing index with {len(existing_df)} games")

        # Merge on game_id (primary key)
        # Keep existing rows if they have data fetched
        # Update rows if new data is available

        # Identify games in both
        existing_ids = set(existing_df["game_id"])
        new_ids = set(new_df["game_id"])

        # Games only in existing (keep as-is)
        only_existing = existing_df[~existing_df["game_id"].isin(new_ids)]

        # Games only in new (add)
        only_new = new_df[~new_df["game_id"].isin(existing_ids)]

        # Games in both (merge - prefer existing fetch flags)
        common_ids = existing_ids & new_ids
        common_existing = existing_df[existing_df["game_id"].isin(common_ids)]
        common_new = new_df[new_df["game_id"].isin(common_ids)]

        # For common games, keep fetch flags from existing
        merged_common = common_new.copy()
        for flag_col in [
            "has_pbp",
            "has_shots",
            "has_boxscore",
            "pbp_fetched_at",
            "shots_fetched_at",
            "boxscore_fetched_at",
        ]:
            # Map existing values
            flag_map = dict(
                zip(common_existing["game_id"], common_existing[flag_col], strict=False)
            )
            merged_common[flag_col] = (
                merged_common["game_id"].map(flag_map).fillna(merged_common[flag_col])
            )

        # Update last_updated for common games
        merged_common["last_updated"] = datetime.now().isoformat()

        # Combine all
        final_df = pd.concat([only_existing, only_new, merged_common], ignore_index=True)

        # Sort by season and date
        final_df = final_df.sort_values(["season", "game_date"], ascending=[False, False])

        print(
            f"[INFO] Merged index: {len(existing_df)} existing + {len(only_new)} new = {len(final_df)} total"
        )

        return final_df

    except Exception as e:
        print(f"[ERROR] Failed to merge with existing index: {e}")
        print("[WARN] Using new data only")
        return new_df


def build_complete_index(seasons: list[str], force_rebuild: bool = False) -> pd.DataFrame:
    """Build complete game index for multiple seasons

    Args:
        seasons: List of season strings
        force_rebuild: If True, ignore existing index and rebuild

    Returns:
        Complete game index DataFrame
    """
    print(f"\n{'='*80}")
    print("  BUILDING LNB GAME INDEX")
    print(f"{'='*80}\n")

    print(f"Seasons to process: {seasons}")
    print(f"Force rebuild: {force_rebuild}")
    print()

    # Load discovered fixture UUIDs (legacy approach)
    discovered_uuids = load_discovered_fixture_uuids()

    # Load per-season UUID mappings (new approach for historical coverage)
    uuid_mappings = load_fixture_uuids_by_season()

    # Build index for each season
    all_season_data = []
    for season in seasons:
        season_df = build_index_for_season(season, discovered_uuids, uuid_mappings)
        if not season_df.empty:
            all_season_data.append(season_df)

    if not all_season_data:
        print("\n[ERROR] No data collected for any season")
        return pd.DataFrame()

    # Combine all seasons
    combined_df = pd.concat(all_season_data, ignore_index=True)
    print(f"\n[INFO] Combined data: {len(combined_df)} games across {len(seasons)} seasons")

    # Merge with existing index (unless force rebuild)
    if force_rebuild:
        print("[INFO] Force rebuild enabled - ignoring existing index")
        final_df = combined_df
    else:
        final_df = merge_with_existing_index(combined_df, INDEX_FILE)

    return final_df


def save_index(df: pd.DataFrame, output_path: Path) -> None:
    """Save game index to Parquet file

    Args:
        df: Game index DataFrame
        output_path: Path to save file
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        print(f"\n[SUCCESS] Saved game index to {output_path}")
        print(f"           {len(df)} games")
        print(f"           {df['season'].nunique()} seasons")

        # Print summary by season
        print("\nSummary by season:")
        summary = (
            df.groupby("season")
            .agg({"game_id": "count", "has_pbp": "sum", "has_shots": "sum", "has_boxscore": "sum"})
            .rename(columns={"game_id": "total_games"})
        )
        print(summary.to_string())

    except Exception as e:
        print(f"\n[ERROR] Failed to save index: {e}")
        import traceback

        traceback.print_exc()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Build canonical game index for LNB Pro A",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build index for current season (default)
    python tools/lnb/build_game_index.py

    # Build for specific seasons
    python tools/lnb/build_game_index.py --seasons 2024-2025 2023-2024 2022-2023

    # Force rebuild (ignore existing index)
    python tools/lnb/build_game_index.py --force-rebuild
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="Seasons to process (format: YYYY-YYYY)",
    )

    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore existing index and rebuild from scratch",
    )

    args = parser.parse_args()

    # Build index
    index_df = build_complete_index(seasons=args.seasons, force_rebuild=args.force_rebuild)

    if index_df.empty:
        print("\n[ERROR] Failed to build game index")
        sys.exit(1)

    # Save to Parquet
    save_index(index_df, INDEX_FILE)

    print(f"\n{'='*80}")
    print("  GAME INDEX BUILD COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
