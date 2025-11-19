#!/usr/bin/env python3
"""NZ-NBL Game Discovery Helper Tool

This tool streamlines the process of discovering and adding NZ-NBL games from
FIBA LiveStats to the game index.

Features:
- Test FIBA game IDs to verify they exist
- Bulk-add games from a range of IDs
- Scan for valid game IDs in a range
- Extract game metadata from FIBA LiveStats

Why Manual Discovery?
    FIBA LiveStats uses JavaScript-heavy pages with bot protection,
    making automated scraping difficult without browser automation tools.
    This tool helps streamline the manual discovery process.

Usage:
    # Test if a game ID exists
    python tools/nz_nbl/discover_games.py --test-id 301234

    # Scan a range of IDs to find valid games
    python tools/nz_nbl/discover_games.py --scan-range 301000 301100

    # Add discovered games to index
    python tools/nz_nbl/discover_games.py --add-from-range 301234 301240 --season 2024

Manual Discovery Process:
    1. Visit https://fibalivestats.dcd.shared.geniussports.com/u/NZN/
    2. Find games in the schedule
    3. Click on a game to view stats
    4. Extract game ID from URL (e.g., /u/NZN/301234/bs.html)
    5. Use this tool to verify and add to index

Created: 2025-11-18
Purpose: Streamline NZ-NBL game discovery for historical data collection
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers.nz_nbl_fiba import _scrape_fiba_box_score


def test_game_id(game_id: str) -> dict | None:
    """Test if a FIBA game ID exists and extract metadata

    Args:
        game_id: FIBA game ID to test

    Returns:
        Dictionary with game metadata if found, None otherwise
    """
    print(f"Testing game ID: {game_id}")

    try:
        # Try to fetch box score
        df = _scrape_fiba_box_score(game_id)

        if df.empty:
            print(f"  [FAIL] Game ID {game_id} returned no data")
            return None

        # Extract metadata from box score
        metadata = {
            "game_id": game_id,
            "teams": df["TEAM"].unique().tolist() if "TEAM" in df.columns else [],
            "player_count": len(df),
            "has_stats": "PTS" in df.columns,
        }

        print(f"  [OK] Game ID {game_id} is valid!")
        print(f"       Teams: {', '.join(metadata['teams'])}")
        print(f"       Players: {metadata['player_count']}")

        return metadata

    except Exception as e:
        print(f"  [FAIL] Game ID {game_id} failed: {str(e)[:100]}")
        return None


def scan_id_range(start_id: int, end_id: int, quiet: bool = False) -> list[str]:
    """Scan a range of IDs to find valid FIBA games

    Args:
        start_id: Starting ID (inclusive)
        end_id: Ending ID (inclusive)
        quiet: If True, suppress detailed output

    Returns:
        List of valid game IDs found
    """
    valid_ids = []

    print(f"\nScanning game IDs from {start_id} to {end_id}...")
    print("This may take several minutes depending on range size.\n")

    for game_id in range(start_id, end_id + 1):
        if not quiet:
            print(f"Checking {game_id}...", end=" ")

        try:
            df = _scrape_fiba_box_score(str(game_id))

            if not df.empty:
                valid_ids.append(str(game_id))
                teams = df["TEAM"].unique().tolist() if "TEAM" in df.columns else ["Unknown"]
                if not quiet:
                    print(f"[OK] VALID - {', '.join(teams)}")
                else:
                    print(f"  [OK] Found valid game: {game_id} ({', '.join(teams)})")
            else:
                if not quiet:
                    print("[SKIP] No data")

        except Exception as e:
            if not quiet:
                print(f"[FAIL] Error: {str(e)[:50]}")

    print(f"\n{'='*60}")
    print(f"Scan complete: Found {len(valid_ids)} valid game(s)")
    print(f"Valid IDs: {', '.join(valid_ids)}")

    return valid_ids


def add_games_from_range(
    start_id: int,
    end_id: int,
    season: str,
    index_path: Path,
) -> None:
    """Scan range, find valid games, and add to index

    Args:
        start_id: Starting ID
        end_id: Ending ID
        season: Season string (e.g., "2024")
        index_path: Path to game index file
    """
    print(f"\nScanning and adding games from {start_id} to {end_id}")
    print(f"Season: {season}")
    print(f"Index: {index_path}\n")

    # Scan for valid IDs
    valid_ids = scan_id_range(start_id, end_id, quiet=True)

    if not valid_ids:
        print("\n[WARN] No valid game IDs found in range")
        return

    # Load existing index
    if index_path.exists():
        if index_path.suffix == ".parquet":
            existing = pd.read_parquet(index_path)
        else:
            existing = pd.read_csv(index_path)
            existing["GAME_DATE"] = pd.to_datetime(existing["GAME_DATE"])

        existing_ids = set(existing["GAME_ID"].astype(str).tolist())
    else:
        existing = pd.DataFrame()
        existing_ids = set()

    # Add new games
    new_games = []
    for game_id in valid_ids:
        if game_id in existing_ids:
            print(f"  [SKIP] Game {game_id} already in index")
            continue

        # Fetch game metadata
        try:
            df = _scrape_fiba_box_score(game_id)
            teams = df["TEAM"].unique().tolist() if "TEAM" in df.columns else ["Unknown", "Unknown"]

            # Try to extract game date from box score if available
            # For now, use placeholder - user can update manually
            game_date = datetime.now().strftime("%Y-%m-%d")

            new_game = {
                "SEASON": season,
                "GAME_ID": game_id,
                "GAME_DATE": pd.to_datetime(game_date),
                "HOME_TEAM": teams[0] if len(teams) > 0 else "Unknown",
                "AWAY_TEAM": teams[1] if len(teams) > 1 else "Unknown",
                "HOME_SCORE": None,
                "AWAY_SCORE": None,
            }

            new_games.append(new_game)
            print(f"  [ADD] Game {game_id}: {teams[0]} vs {teams[1]}")

        except Exception as e:
            print(f"  [WARN] Could not add game {game_id}: {e}")

    if not new_games:
        print("\n[INFO] All games already in index")
        return

    # Combine with existing
    new_df = pd.DataFrame(new_games)
    if existing.empty:
        combined = new_df
    else:
        combined = pd.concat([existing, new_df], ignore_index=True)

    # Save
    if index_path.suffix == ".parquet":
        combined.to_parquet(index_path, index=False)
    else:
        combined.to_csv(index_path, index=False)

    print(f"\n[OK] SUCCESS: Added {len(new_games)} new game(s) to {index_path}")
    print(f"Total games in index: {len(combined)}")


def main():
    parser = argparse.ArgumentParser(
        description="NZ-NBL Game Discovery Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--test-id",
        metavar="GAME_ID",
        help="Test if a single game ID exists on FIBA LiveStats",
    )

    parser.add_argument(
        "--scan-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Scan a range of IDs to find valid games (e.g., --scan-range 301000 301100)",
    )

    parser.add_argument(
        "--add-from-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Scan range and automatically add valid games to index",
    )

    parser.add_argument(
        "--season",
        metavar="SEASON",
        help='Season for games when using --add-from-range (e.g., "2024")',
    )

    parser.add_argument(
        "--index",
        metavar="PATH",
        default="data/nz_nbl_game_index.parquet",
        help="Path to game index file (default: data/nz_nbl_game_index.parquet)",
    )

    args = parser.parse_args()

    # Test single ID
    if args.test_id:
        metadata = test_game_id(args.test_id)
        if metadata:
            print("\n[OK] Game ID is valid and can be added to index")
        else:
            print("\n[FAIL] Game ID is not valid or unavailable")
        return

    # Scan range
    if args.scan_range:
        start_id, end_id = args.scan_range
        scan_id_range(start_id, end_id)  # Prints results directly
        print("\nNext steps:")
        print(f"1. Use --add-from-range {start_id} {end_id} --season YYYY to add these games")
        print("2. Or add manually using tools/nz_nbl/create_game_index.py")
        return

    # Add from range
    if args.add_from_range:
        if not args.season:
            print("Error: --season required when using --add-from-range")
            sys.exit(1)

        start_id, end_id = args.add_from_range
        index_path = Path(args.index)
        add_games_from_range(start_id, end_id, args.season, index_path)
        return

    # No action specified
    parser.print_help()
    print("\n" + "=" * 60)
    print("MANUAL DISCOVERY INSTRUCTIONS")
    print("=" * 60)
    print("1. Visit: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/")
    print("2. Navigate to a game in the schedule")
    print("3. Look at the URL when viewing game stats")
    print("4. Extract game ID from URL pattern: /u/NZN/[GAME_ID]/bs.html")
    print("5. Use --test-id to verify the game ID")
    print("6. Use --scan-range to find multiple games in a range")
    print("7. Use --add-from-range to automatically add found games")


if __name__ == "__main__":
    main()
