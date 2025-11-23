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

# ==============================================================================
# CONFIG
# ==============================================================================

# Default seasons to process (can be overridden by league-specific defaults)
DEFAULT_SEASONS = ["2024-2025"]

# Default leagues to process (all LNB leagues)
# Can be filtered via --league CLI parameter
DEFAULT_LEAGUES = ["betclic_elite", "elite_2", "espoirs_elite", "espoirs_prob"]

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


def _season_keys_for(
    season: str, mappings: dict[str, list[str]], league: str | None = None
) -> list[str]:
    """Expand season into all matching keys (exact + suffixed variants)

    After deduplication, seasons may be stored in league-specific keys like:
      - "2023-2024_betclic_elite"
      - "2023-2024_elite_2"

    This function expands "2023-2024" to find all matching keys.

    Args:
        season: Base season string (e.g., "2023-2024")
        mappings: UUID mappings dict
        league: Optional league filter to restrict to specific league keys

    Returns:
        List of matching mapping keys

    Example:
        >>> _season_keys_for("2023-2024", {"2023-2024_betclic_elite": [...], "2023-2024_elite_2": [...]})
        ["2023-2024_betclic_elite", "2023-2024_elite_2"]
    """
    matching_keys = []

    # Exact match (backward compatibility for non-suffixed keys)
    if season in mappings:
        matching_keys.append(season)

    # Suffixed matches (league-specific keys)
    suffix_pattern = f"{season}_"
    for key in mappings:
        if key.startswith(suffix_pattern):
            # If league filter is specified, only include matching league keys
            if league:
                if key == f"{season}_{league}":
                    matching_keys.append(key)
            else:
                # No league filter - include all suffixed keys for this season
                matching_keys.append(key)

    return matching_keys


def build_index_for_season(
    season: str,
    discovered_uuids: dict[str, list[str]] = None,
    uuid_mappings: dict[str, list[str]] = None,
    league: str | None = None,
) -> pd.DataFrame:
    """Build game index for a single season WITH game date population

    ENHANCEMENT (2025-11-16): Now fetches fixture metadata from Atrium API
    to populate game_date, team names, and status. This enables date-based
    filtering to skip future games during ingestion.

    ENHANCEMENT (2025-11-20): Added league parameter to support multi-league filtering.
    When league is specified, only builds index for that specific league's seasons.

    BUGFIX (2025-11-20): Expand season into all matching keys (exact + suffixed).
    After deduplication, generic season keys like "2023-2024" may be empty while
    league-specific keys like "2023-2024_betclic_elite" contain the actual UUIDs.

    Args:
        season: Season string (e.g., "2024-2025")
        discovered_uuids: Dict of discovered fixture UUIDs by season (legacy)
        uuid_mappings: Dict mapping season -> list of UUIDs from JSON file (preferred)
        league: Optional league filter (e.g., "betclic_elite", "elite_2")
                If None, attempts to find season in any league

    Returns:
        DataFrame with game index for this season, including populated game_date field

    Changes:
        - Added API call to fetch fixture metadata
        - Populates game_date from startTimeLocal field
        - Populates team names and IDs from competitors data
        - Better error handling for API failures
        - Added league parameter for multi-league support
        - Fixed season key expansion to handle suffixed keys (2025-11-20)
    """
    if discovered_uuids is None:
        discovered_uuids = {}
    if uuid_mappings is None:
        uuid_mappings = {}
    print(f"\n[BUILDING] Game index for season {season}...")

    try:
        # Get fixture UUIDs for this season from mapping file (preferred) or legacy source
        # BUGFIX (2025-11-20): Expand season into ALL matching keys (exact + suffixed)
        # This handles cases where deduplication moved UUIDs to league-specific keys
        fixture_uuids = []

        # Expand season into all matching mapping keys
        matching_keys = _season_keys_for(season, uuid_mappings, league)

        # Track which mapping key each UUID came from (for league inference)
        uuid_to_key = {}

        if matching_keys:
            # Collect UUIDs from all matching keys
            for key in matching_keys:
                key_uuids = uuid_mappings[key]
                for uuid in key_uuids:
                    uuid_to_key[uuid] = key  # Track which key this UUID came from
                fixture_uuids.extend(key_uuids)
                print(f"  [INFO] Loaded {len(key_uuids)} fixture UUIDs from key: {key}")

            # Deduplicate in case same UUID appears in multiple keys
            original_count = len(fixture_uuids)
            fixture_uuids = list(set(fixture_uuids))
            if original_count > len(fixture_uuids):
                print(
                    f"  [INFO] Deduplicated {original_count - len(fixture_uuids)} overlapping UUIDs"
                )

            print(f"  [INFO] Total unique fixture UUIDs for {season}: {len(fixture_uuids)}")

        else:
            # No matching keys found - try legacy fallback
            if season == "2024-2025":
                fixture_uuids = discovered_uuids.get("current_season", [])
                if fixture_uuids:
                    print(f"  [INFO] Using {len(fixture_uuids)} UUIDs from legacy discovered_uuids")

        # CRITICAL FIX: Only create index entries for confirmed UUIDs, not schedule placeholders
        # This prevents synthetic IDs from polluting the index
        if not fixture_uuids:
            if league:
                print(f"  [WARN] No fixture UUIDs for {season} (league: {league}) - skipping")
            else:
                print(f"  [WARN] No fixture UUIDs for {season} - skipping")
            return pd.DataFrame()

        # Health check: Warn if UUID count is suspiciously low for a league-specific request
        if league and len(fixture_uuids) < 10:
            print(
                f"  [WARN] Only {len(fixture_uuids)} fixtures found for {season} (league: {league})"
            )
            print("  [WARN] This is unusually low - verify data completeness")

        print(f"  [INFO] Creating index entries for {len(fixture_uuids)} confirmed games")

        # NEW: Fetch fixture metadata from Atrium API to get game dates and team names
        # This enables date-based filtering to skip future games
        fixtures_metadata_map = {}
        try:
            # Import helper function
            # UPDATED 2025-11-18: Import centralized league metadata
            # Now supports all 4 LNB leagues: Betclic ELITE, ELITE 2, Espoirs ELITE, Espoirs PROB
            from src.cbb_data.fetchers.lnb_league_config import (
                BETCLIC_ELITE_SEASONS,
                ELITE_2_SEASONS,
                ESPOIRS_ELITE_SEASONS,
                ESPOIRS_PROB_SEASONS,
                get_season_metadata,
            )
            from tools.lnb.fetch_fixture_metadata_helper import fetch_fixtures_metadata

            # UPDATED 2025-11-20: League-aware season metadata lookup
            # If league is specified, only check that league's seasons
            # If no league specified, check all leagues (backward compatibility)
            SEASON_METADATA = {}

            if league:
                # Use get_season_metadata helper for single league
                season_meta = get_season_metadata(league, season)
                if season_meta:
                    SEASON_METADATA[season] = season_meta
            else:
                # Combine all league seasons for backward compatibility
                # This allows any season from any league to be looked up
                for seasons_dict in [
                    BETCLIC_ELITE_SEASONS,
                    ELITE_2_SEASONS,
                    ESPOIRS_ELITE_SEASONS,
                    ESPOIRS_PROB_SEASONS,
                ]:
                    for season_key, meta in seasons_dict.items():
                        # Use first occurrence if season exists in multiple leagues
                        # (shouldn't happen, but defensive coding)
                        if season_key not in SEASON_METADATA:
                            SEASON_METADATA[season_key] = meta

            if season in SEASON_METADATA:
                print("  [FETCHING] Game dates and team names from Atrium API...")
                metadata_list = fetch_fixtures_metadata(
                    competition_id=SEASON_METADATA[season]["competition_id"],
                    season_id=SEASON_METADATA[season]["season_id"],
                )

                # Create lookup map by fixture_id
                for meta in metadata_list:
                    fixtures_metadata_map[meta["fixture_id"]] = meta

                print(f"  [SUCCESS] Fetched metadata for {len(fixtures_metadata_map)} games")
            else:
                print(f"  [WARN] Season {season} not in SEASON_METADATA, game dates will be empty")

        except Exception as e:
            print(f"  [WARN] Failed to fetch fixture metadata: {e}")
            print("  [WARN] Continuing with empty game dates (can be populated later)")

        # Initialize index DataFrame with proper schema
        index_data = []

        # Create one index entry per confirmed UUID
        for game_id in fixture_uuids:
            # Get metadata from API if available, otherwise use defaults
            meta = fixtures_metadata_map.get(game_id, {})

            # UPDATED 2025-11-18: Dynamic competition name lookup
            # Import competition name mapper
            from src.cbb_data.fetchers.lnb_league_config import get_competition_name
            from src.cbb_data.fetchers.lnb_league_normalization import normalize_lnb_league

            # Get competition_id for this season (if available)
            season_meta = SEASON_METADATA.get(season, {})
            comp_id = season_meta.get("competition_id", "")

            # Map competition_id to display name (e.g., "Betclic ELITE", "ELITE 2")
            # Falls back to "Unknown Competition" if ID not found
            competition_display_name = (
                get_competition_name(comp_id) if comp_id else "Unknown Competition"
            )

            # UPDATED 2025-11-20: Add canonical league key for consistent filtering
            # Determine league from one of three sources (in priority order):
            # 1. League parameter (from --leagues filter)
            # 2. Mapping key the UUID came from (e.g., "2024-2025_elite_2" → "elite_2")
            # 3. Competition display name from API (fallback)
            if league:
                canonical_league = league  # Already canonical from filter
            elif game_id in uuid_to_key:
                # Infer league from mapping key (e.g., "2024-2025_elite_2" → "elite_2")
                mapping_key = uuid_to_key[game_id]
                if "_" in mapping_key:
                    inferred_league = mapping_key.split("_", 1)[1]  # Extract league suffix
                    canonical_league = inferred_league
                else:
                    # No suffix (e.g., "2024-2025") - fall back to competition name
                    canonical_league = normalize_lnb_league(competition_display_name)
            else:
                # Fallback: normalize competition name
                canonical_league = normalize_lnb_league(competition_display_name)

            index_row = {
                "season": season,
                "league": canonical_league,  # Canonical key for filtering
                "competition": competition_display_name,  # Display name for humans
                "game_id": game_id,
                "lnb_match_id": game_id,  # Use UUID as match ID
                "game_date": meta.get("game_date", ""),  # NOW POPULATED!
                "home_team_id": meta.get("home_team_id", ""),
                "home_team_name": meta.get("home_team_name", ""),
                "away_team_id": meta.get("away_team_id", ""),
                "away_team_name": meta.get("away_team_name", ""),
                "status": meta.get("status", "Completed"),
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

        # Show sample of populated dates for verification
        if not index_df.empty and "game_date" in index_df.columns:
            populated_dates = index_df[index_df["game_date"] != ""]["game_date"].nunique()
            print(
                f"  [INFO] Populated game_date for {len(index_df[index_df['game_date'] != ''])} games"
            )
            if populated_dates > 0:
                print(
                    f"  [SAMPLE] Date range: {index_df['game_date'].min()} to {index_df['game_date'].max()}"
                )

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


def build_complete_index(
    seasons: list[str],
    leagues: list[str] | None = None,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Build complete game index for multiple seasons and leagues

    ENHANCEMENT (2025-11-20): Added leagues parameter to support multi-league filtering.
    Can now build index for specific leagues only (e.g., just ELITE 2 and Espoirs ELITE).

    Args:
        seasons: List of season strings (e.g., ["2024-2025", "2023-2024"])
        leagues: Optional list of league identifiers to include
                (e.g., ["betclic_elite", "elite_2"])
                If None, builds index for all leagues with data for the given seasons
        force_rebuild: If True, ignore existing index and rebuild

    Returns:
        Complete game index DataFrame
    """
    print(f"\n{'='*80}")
    print("  BUILDING LNB GAME INDEX")
    print(f"{'='*80}\n")

    print(f"Seasons to process: {seasons}")
    if leagues:
        print(f"Leagues to include: {leagues}")
    else:
        print("Leagues to include: All leagues with data for specified seasons")
    print(f"Force rebuild: {force_rebuild}")
    print()

    # Load discovered fixture UUIDs (legacy approach)
    discovered_uuids = load_discovered_fixture_uuids()

    # Load per-season UUID mappings (new approach for historical coverage)
    uuid_mappings = load_fixture_uuids_by_season()

    # Build index for each season (and optionally each league)
    all_season_data = []

    if leagues:
        # Multi-league mode: build for each league + season combination
        from src.cbb_data.fetchers.lnb_league_config import get_season_metadata

        for league in leagues:
            for season in seasons:
                # Check if this league has data for this season
                if get_season_metadata(league, season) is not None:
                    print(f"\n[BUILDING] {league} - {season}")
                    season_df = build_index_for_season(
                        season, discovered_uuids, uuid_mappings, league=league
                    )
                    if not season_df.empty:
                        all_season_data.append(season_df)
                else:
                    print(f"\n[SKIP] {league} - {season} (no metadata available)")
    else:
        # Legacy mode: build for each season across all leagues
        for season in seasons:
            season_df = build_index_for_season(season, discovered_uuids, uuid_mappings, league=None)
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


def enforce_schema_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce INDEX_SCHEMA dtypes on DataFrame

    This ensures that boolean columns are actually bool type, not float64.
    Critical for preventing type conversion issues during merge operations.

    Args:
        df: Game index DataFrame with potentially incorrect dtypes

    Returns:
        DataFrame with corrected dtypes matching INDEX_SCHEMA
    """
    print("[DEBUG] Enforcing schema dtypes...")
    print(f"  Before: has_pbp={df['has_pbp'].dtype}, has_shots={df['has_shots'].dtype}")

    # Convert float64 boolean flags to actual boolean
    # float64 with values 0.0/1.0 converts cleanly to False/True
    bool_columns = ["has_pbp", "has_shots", "has_boxscore"]
    for col in bool_columns:
        if col in df.columns:
            # Convert: 0.0 → False, 1.0 → True, NaN → False
            df[col] = df[col].fillna(0.0).astype(bool)

    print(f"  After:  has_pbp={df['has_pbp'].dtype}, has_shots={df['has_shots'].dtype}")

    return df


def save_index(df: pd.DataFrame, output_path: Path) -> None:
    """Save game index to Parquet file

    Args:
        df: Game index DataFrame
        output_path: Path to save file
    """
    try:
        # Enforce schema dtypes before saving
        df = enforce_schema_dtypes(df)

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
        description="Build canonical game index for all LNB leagues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build index for current season (all leagues)
    python tools/lnb/build_game_index.py

    # Build for specific seasons (all leagues)
    python tools/lnb/build_game_index.py --seasons 2024-2025 2023-2024 2022-2023

    # Build for specific league only
    python tools/lnb/build_game_index.py --leagues elite_2

    # Build for multiple leagues
    python tools/lnb/build_game_index.py --leagues betclic_elite elite_2

    # Build for specific league + season combination
    python tools/lnb/build_game_index.py --leagues espoirs_elite --seasons 2024-2025

    # Force rebuild (ignore existing index)
    python tools/lnb/build_game_index.py --force-rebuild

Available leagues:
    betclic_elite    - Top-tier professional (formerly Pro A), 16 teams
    elite_2          - Second-tier professional (formerly Pro B), 20 teams
    espoirs_elite    - U21 top-tier youth development
    espoirs_prob     - U21 second-tier youth development
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="Seasons to process (format: YYYY-YYYY)",
    )

    parser.add_argument(
        "--leagues",
        nargs="+",
        default=None,
        help="Leagues to include (default: all leagues). "
        "Options: betclic_elite, elite_2, espoirs_elite, espoirs_prob",
    )

    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore existing index and rebuild from scratch",
    )

    args = parser.parse_args()

    # Canonicalize league arguments (e.g., "prob" → "elite_2")
    # This ensures consistent naming across branding changes (Pro B → ÉLITE 2)
    from src.cbb_data.fetchers.lnb_league_normalization import canonicalize_requested_leagues

    canonical_leagues = None
    if args.leagues:
        canonical_leagues = canonicalize_requested_leagues(args.leagues)
        if canonical_leagues != args.leagues:
            print(f"[INFO] Canonicalized leagues: {args.leagues} → {canonical_leagues}")

    # Build index
    index_df = build_complete_index(
        seasons=args.seasons, leagues=canonical_leagues, force_rebuild=args.force_rebuild
    )

    if index_df.empty:
        print("\n[ERROR] Failed to build game index")
        sys.exit(1)

    # Validate league normalization (safety check)
    from src.cbb_data.fetchers.lnb_league_normalization import validate_league_normalization

    try:
        validate_league_normalization(index_df)
    except AssertionError as e:
        print(f"\n[ERROR] League normalization validation failed: {e}")
        sys.exit(1)

    # Save to Parquet
    save_index(index_df, INDEX_FILE)

    print(f"\n{'='*80}")
    print("  GAME INDEX BUILD COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
