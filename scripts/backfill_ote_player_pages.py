#!/usr/bin/env python3
"""OTE Historical Data Backfill via Player Pages

Uses player season pages instead of scores endpoint to fetch historical data.

Usage:
    python scripts/backfill_ote_player_pages.py [--dry-run]
"""

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Add airflow project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "api" / "src" / "airflow_project"))


def normalize_name(name):
    """Normalize player name for matching."""
    if pd.isna(name) or not name:
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized


def fetch_player_directory() -> list[str]:
    """Fetch all player UUIDs from OTE players directory.

    Returns:
        List of player UUIDs
    """
    print("\nFetching player directory...")
    url = "https://overtimeelite.com/players"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Find all player links
        player_links = soup.find_all("a", href=re.compile(r"/players/[a-f0-9\-]{36}"))

        # Extract UUIDs
        player_uuids = []
        for link in player_links:
            href = link.get("href")
            uuid_match = re.search(r"/players/([a-f0-9\-]{36})", href)
            if uuid_match:
                player_uuids.append(uuid_match.group(1))

        # Deduplicate
        player_uuids = list(set(player_uuids))

        print(f"  Found {len(player_uuids)} unique player UUIDs")
        return player_uuids

    except Exception as e:
        print(f"  ERROR fetching player directory: {e}")
        return []


def fetch_player_season_games(player_uuid: str, season: str = "2021-22") -> pd.DataFrame:
    """Fetch game-by-game data for a player from their season page.

    Args:
        player_uuid: Player UUID
        season: Season string (e.g., "2021-22")

    Returns:
        DataFrame with player-game records
    """
    url = f"https://overtimeelite.com/players/{player_uuid}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Find player name
        player_name = None
        name_elem = soup.find("h1") or soup.find("h2")
        if name_elem:
            player_name = name_elem.text.strip()

        # Find season tabs to determine which table corresponds to which season
        season_tabs = soup.find_all("button", {"role": "tab"})
        season_names = [tab.text.strip() for tab in season_tabs if tab.text.strip()]

        # Find all data tables
        tables = soup.find_all("table")

        if not tables:
            return pd.DataFrame()

        # Try to find the season table (heuristic: find tab index for season, use corresponding table)
        season_table_idx = None
        for idx, tab_name in enumerate(season_names):
            if season in tab_name or season.replace("-", "/") in tab_name:
                season_table_idx = idx
                break

        # If no specific season tab found, try first non-career table
        if season_table_idx is None:
            # Skip "Career" tab, use first season tab
            season_table_idx = 0

        # Use the corresponding table
        if season_table_idx < len(tables):
            table = tables[season_table_idx]
        else:
            table = tables[0]

        # Parse table
        df = pd.read_html(str(table))[0]

        # Add metadata
        df["PLAYER_NAME_RAW"] = player_name
        df["SOURCE_PLAYER_ID"] = player_uuid
        df["SEASON"] = season
        df["LEAGUE"] = "OTE"
        df["NAME_KEY"] = normalize_name(player_name) if player_name else ""

        # Standardize column names (depends on table structure)
        # Common columns: DATE, OPP, MIN, PTS, REB, AST, etc.
        column_map = {
            "DATE": "GAME_DATE",
            "OPP": "OPPONENT",
            "Opponent": "OPPONENT",
            "MIN": "MIN",
            "PTS": "PTS",
            "REB": "REB",
            "AST": "AST",
            "STL": "STL",
            "BLK": "BLK",
            "TO": "TOV",
            "TOV": "TOV",
            "FGM": "FGM",
            "FGA": "FGA",
            "FG%": "FG_PCT",
            "3PM": "FG3M",
            "3PA": "FG3A",
            "3P%": "FG3_PCT",
            "FTM": "FTM",
            "FTA": "FTA",
            "FT%": "FT_PCT",
            "OREB": "OREB",
            "DREB": "DREB",
            "+/-": "PLUS_MINUS",
        }

        for old_col, new_col in column_map.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        # Create synthetic GAME_ID
        if "GAME_DATE" in df.columns:
            df["GAME_ID"] = df.apply(
                lambda row: f"OTE_{season}_{player_uuid[:8]}_{pd.to_datetime(row['GAME_DATE']).strftime('%Y%m%d') if pd.notna(row['GAME_DATE']) else 'UNK'}",
                axis=1,
            )
        else:
            df["GAME_ID"] = [f"OTE_{season}_{player_uuid[:8]}_{i}" for i in range(len(df))]

        return df

    except Exception as e:
        print(f"    ERROR fetching player {player_uuid}: {e}")
        return pd.DataFrame()


def backfill_ote_season_via_players(season: str, dry_run: bool = False) -> pd.DataFrame:
    """Backfill OTE season by scraping all player pages.

    Args:
        season: Season string (e.g., "2021-22")
        dry_run: If True, fetch but don't save

    Returns:
        DataFrame with all player-game records for the season
    """
    print(f"\n{'='*80}")
    print(f"BACKFILLING OTE SEASON VIA PLAYER PAGES: {season}")
    print(f"{'='*80}")

    # Step 1: Get all player UUIDs
    player_uuids = fetch_player_directory()

    if len(player_uuids) == 0:
        print("  ERROR: No player UUIDs found")
        return pd.DataFrame()

    # Step 2: Fetch each player's season data
    print(f"\nStep 2: Fetching season data for {len(player_uuids)} players...")
    all_player_games = []
    failed_players = []

    for idx, player_uuid in enumerate(player_uuids, 1):
        print(f"  [{idx}/{len(player_uuids)}] Player {player_uuid[:8]}...", end="")

        try:
            player_df = fetch_player_season_games(player_uuid, season)

            if len(player_df) > 0:
                all_player_games.append(player_df)
                print(f" {len(player_df)} games")
            else:
                print(" No data")
                failed_players.append(player_uuid)

            # Rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f" ERROR: {e}")
            failed_players.append(player_uuid)
            continue

    if len(failed_players) > 0:
        print(f"\n  WARNING: {len(failed_players)} players failed")

    if len(all_player_games) == 0:
        print(f"\n  ERROR: No player data fetched for {season}")
        return pd.DataFrame()

    # Step 3: Combine all player-games
    print("\nStep 3: Combining player-games...")
    season_df = pd.concat(all_player_games, ignore_index=True)
    print(f"  Total records: {len(season_df)}")
    print(f"  Unique players: {season_df['SOURCE_PLAYER_ID'].nunique()}")

    # Step 4: Ensure required columns
    print("\nStep 4: Standardizing columns...")
    required_cols = [
        "SOURCE_PLAYER_ID",
        "PLAYER_NAME_RAW",
        "NAME_KEY",
        "GAME_ID",
        "SEASON",
        "LEAGUE",
        "GAME_DATE",
    ]
    for col in required_cols:
        if col not in season_df.columns:
            print(f"    WARNING: Missing column {col}, adding as None")
            season_df[col] = None

    # Step 5: Save
    if not dry_run:
        print("\nStep 5: Saving to canonical directory...")

        output_dir = Path("data/canonical/box_player_game/league=OTE") / f"season={season}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "data.parquet"

        season_df.to_parquet(output_path, index=False, compression="snappy")

        file_size_kb = output_path.stat().st_size / 1024
        print(f"  ✓ Saved to {output_path}")
        print(f"  File size: {file_size_kb:.1f} KB")
    else:
        print(f"\nStep 5: [DRY RUN] Would save {len(season_df)} records")

    # Step 6: Sample data
    print("\nStep 6: Sample players...")
    sample_df = (
        season_df.groupby("SOURCE_PLAYER_ID")
        .agg({"PLAYER_NAME_RAW": "first", "GAME_ID": "count", "PTS": "mean"})
        .reset_index()
    )
    sample_df.columns = ["SOURCE_PLAYER_ID", "PLAYER_NAME", "GAMES", "PPG"]
    sample_df = sample_df.sort_values("GAMES", ascending=False).head(10)

    for _idx, row in sample_df.iterrows():
        print(f"  - {row['PLAYER_NAME']}: {row['GAMES']} games, {row['PPG']:.1f} PPG")

    return season_df


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Backfill OTE via player pages")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't save")
    parser.add_argument("--seasons", nargs="+", help="Specific seasons (e.g., 2021-22 2022-23)")
    parser.add_argument("--test-player", help="Test single player UUID")
    args = parser.parse_args()

    print("=" * 80)
    print("OTE HISTORICAL DATA BACKFILL - PLAYER PAGE METHOD")
    print("=" * 80)

    # Test mode: Single player
    if args.test_player:
        print(f"\nTEST MODE: Fetching single player {args.test_player}")
        test_df = fetch_player_season_games(args.test_player, "2021-22")
        print("\nResults:")
        print(test_df)
        return 0

    # Default seasons
    seasons = args.seasons or [
        "2021-22",  # Thompson twins era
        "2022-23",
        "2023-24",
        "2024-25",
    ]

    print(f"\nSeasons to backfill: {', '.join(seasons)}")
    if args.dry_run:
        print("MODE: DRY RUN")
    else:
        print("MODE: LIVE")

    # Confirm
    if not args.dry_run:
        response = input("\nProceed? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return 0

    # Backfill each season
    all_results = {}
    for season in seasons:
        season_df = backfill_ote_season_via_players(season, dry_run=args.dry_run)
        all_results[season] = len(season_df)

    # Summary
    print("\n" + "=" * 80)
    print("BACKFILL SUMMARY")
    print("=" * 80)

    total_records = sum(all_results.values())

    for season, record_count in all_results.items():
        status = "✓" if record_count > 0 else "✗"
        print(f"  {status} {season}: {record_count:,} records")

    print(f"\n  TOTAL: {total_records:,} records")

    if not args.dry_run:
        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Re-run multi-gate matcher:")
        print("   python scripts/multi_gate_player_matcher.py")
        print("\n2. Re-run unified career dataset builder:")
        print("   python scripts/build_unified_career_gold_chunked.py")
        print("\n3. Validate Thompson twins:")
        print("   Check for amen_thompson and ausar_thompson in player edges")

    return 0


if __name__ == "__main__":
    sys.exit(main())
