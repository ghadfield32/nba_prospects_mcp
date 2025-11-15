#!/usr/bin/env python3
"""Discover LNB game UUIDs for stress testing

This script discovers game UUIDs by:
1. Fetching schedule data from LNB API
2. Extracting fixture UUIDs from getMatchDetails responses
3. Saving discovered UUIDs to a file for stress testing

Usage:
    uv run python tools/lnb/discover_game_uuids.py

Output:
    tools/lnb/discovered_game_uuids.json - List of game UUIDs with metadata
"""

from __future__ import annotations

import io
import json
import sys
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

from src.cbb_data.fetchers.lnb import fetch_lnb_schedule

# ==============================================================================
# CONFIG
# ==============================================================================

# Seasons to discover games from (2024-25 season)
SEASONS_TO_DISCOVER = ["2024-2025"]

# Competitions to discover (LNB Pro A)
COMPETITIONS = [
    "Betclic ELITE",  # Main Pro A league
    "Leaders Cup Pro A",  # Pro A cup
    "Pro A - Play-In",  # Playoffs
]

OUTPUT_FILE = Path("tools/lnb/discovered_game_uuids.json")

# ==============================================================================
# DISCOVERY LOGIC
# ==============================================================================


def discover_game_uuids(seasons: list[str]) -> list[dict[str, Any]]:
    """Discover game UUIDs from LNB schedule data

    Returns list of dicts with:
        - game_id: UUID for Atrium API
        - numeric_id: Numeric ID from LNB API
        - date: Game date
        - home_team: Home team name
        - away_team: Away team name
        - competition: Competition name
        - season: Season
    """
    discovered_games = []

    for season in seasons:
        print(f"\n{'='*80}")
        print(f"  DISCOVERING GAMES FOR SEASON {season}")
        print(f"{'='*80}\n")

        try:
            # Fetch schedule for the season
            print(f"[INFO] Fetching schedule for {season}...")
            schedule_df = fetch_lnb_schedule(season=season)

            if schedule_df.empty:
                print(f"[WARN] No schedule data found for {season}")
                continue

            print(f"[INFO] Found {len(schedule_df)} games in schedule")

            # Extract unique game IDs
            # The schedule DataFrame should have GAME_ID column
            if "GAME_ID" not in schedule_df.columns:
                print("[ERROR] GAME_ID column not found in schedule")
                print(f"[DEBUG] Available columns: {list(schedule_df.columns)}")
                continue

            # Get unique game IDs
            game_ids = schedule_df["GAME_ID"].dropna().unique()
            print(f"[INFO] Found {len(game_ids)} unique game IDs")

            # Extract metadata for each game
            for game_id in game_ids:
                game_row = schedule_df[schedule_df["GAME_ID"] == game_id].iloc[0]

                game_info = {
                    "game_id": str(game_id),
                    "date": game_row.get("GAME_DATE", "").strftime("%Y-%m-%d")
                    if hasattr(game_row.get("GAME_DATE"), "strftime")
                    else str(game_row.get("GAME_DATE", "")),
                    "home_team": str(game_row.get("HOME_TEAM_NAME", "")),
                    "away_team": str(game_row.get("AWAY_TEAM_NAME", "")),
                    "competition": str(game_row.get("COMPETITION", "")),
                    "season": season,
                }

                discovered_games.append(game_info)

            print(f"[INFO] Extracted {len(game_ids)} games from {season}")

        except Exception as e:
            print(f"[ERROR] Failed to discover games for {season}: {e}")
            import traceback

            traceback.print_exc()

    return discovered_games


def filter_by_competition(
    games: list[dict[str, Any]], competitions: list[str]
) -> list[dict[str, Any]]:
    """Filter games by competition"""
    if not competitions:
        return games

    filtered = [g for g in games if g.get("competition", "") in competitions]
    print(
        f"\n[INFO] Filtered {len(games)} games to {len(filtered)} games in competitions: {competitions}"
    )
    return filtered


def save_discovered_uuids(games: list[dict[str, Any]], output_path: Path) -> None:
    """Save discovered UUIDs to JSON file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "discovered_at": datetime.now().isoformat(),
        "total_games": len(games),
        "games": games,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Saved {len(games)} game UUIDs to {output_path}")


def print_summary(games: list[dict[str, Any]]) -> None:
    """Print summary of discovered games"""
    print(f"\n{'='*80}")
    print("  DISCOVERY SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total games discovered: {len(games)}")

    # Group by season
    by_season = {}
    for game in games:
        season = game.get("season", "Unknown")
        by_season[season] = by_season.get(season, 0) + 1

    print("\nGames by season:")
    for season, count in sorted(by_season.items()):
        print(f"  {season}: {count} games")

    # Group by competition
    by_competition = {}
    for game in games:
        comp = game.get("competition", "Unknown")
        by_competition[comp] = by_competition.get(comp, 0) + 1

    print("\nGames by competition:")
    for comp, count in sorted(by_competition.items(), key=lambda x: -x[1]):
        print(f"  {comp}: {count} games")

    # Show sample games
    print("\nSample games (first 5):")
    for i, game in enumerate(games[:5], 1):
        print(f"\n  {i}. {game.get('home_team', 'Unknown')} vs {game.get('away_team', 'Unknown')}")
        print(f"     Date: {game.get('date', 'Unknown')}")
        print(f"     Competition: {game.get('competition', 'Unknown')}")
        print(f"     UUID: {game.get('game_id', 'Unknown')}")


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    print("=" * 80)
    print("  LNB GAME UUID DISCOVERY")
    print("=" * 80)

    # Discover games
    all_games = discover_game_uuids(SEASONS_TO_DISCOVER)

    if not all_games:
        print("\n[ERROR] No games discovered!")
        return

    # Filter by competition (optional)
    # filtered_games = filter_by_competition(all_games, COMPETITIONS)
    filtered_games = all_games  # Use all games for now

    # Save results
    save_discovered_uuids(filtered_games, OUTPUT_FILE)

    # Print summary
    print_summary(filtered_games)

    print(f"\n{'='*80}")
    print("  NEXT STEPS")
    print(f"{'='*80}")
    print("\n1. Review discovered UUIDs in:")
    print(f"   {OUTPUT_FILE}")
    print("\n2. Update stress test script with discovered UUIDs:")
    print("   tools/lnb/run_lnb_stress_tests.py")
    print("\n3. Run comprehensive stress tests:")
    print("   uv run python tools/lnb/run_lnb_stress_tests.py")
    print()


if __name__ == "__main__":
    main()
