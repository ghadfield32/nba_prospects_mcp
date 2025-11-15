#!/usr/bin/env python3
"""
Build Competition/Team Index from Event List

Purpose:
--------
Rebuild competition and team indices from working game endpoints when
traditional endpoints (/stats/*, /common/getDivision*) are broken.

This implements the user's recommendation to rebuild indices from canonical sources.
After testing, we discovered:
- /event/getEventList returns event TYPES (All Star Game, etc.), not game instances
- /match/getCalenderByDivision is the canonical source for game lists (verified working)

Workflow:
---------
1. Fetch all games from /match/getCalenderByDivision
2. Extract unique competitions (by competition_external_id)
3. Extract unique teams (by team_id/external_id)
4. Build mappings:
   - competition_id -> competition metadata
   - competition_id -> list of teams
   - competition_id -> list of games
   - team_id -> team metadata
5. Save indices to JSON for reuse

This provides a robust fallback when API endpoints change.

Usage:
------
    # Build index for current season
    python tools/lnb/build_competition_index.py --year 2025

    # Build for specific division
    python tools/lnb/build_competition_index.py --year 2025 --division 1

    # Use as Python function
    from tools.lnb.build_competition_index import build_indices_from_events
    indices = build_indices_from_events(year=2025, division_external_id=1)

Created: 2025-11-15
Reference: User guidance for rebuilding indices from canonical source
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_api import LNBClient

logger = logging.getLogger(__name__)


def build_indices_from_events(
    year: int | None = None,
    division_external_id: int | None = None,
    save_to_file: bool = False,
    output_dir: str = "tools/lnb/indices",
) -> dict[str, Any]:
    """
    Build competition and team indices from /event/getEventList.

    This function provides a robust way to discover competitions and teams
    even when traditional endpoints are broken.

    Args:
        year: Filter to specific year (None = all years)
        division_external_id: Filter to specific division (None = all)
        save_to_file: If True, save indices to JSON files
        output_dir: Directory for saved indices

    Returns:
        Dictionary with:
        - competitions: Dict[comp_id, competition metadata]
        - teams: Dict[team_id, team metadata]
        - competition_teams: Dict[comp_id, List[team_id]]
        - competition_games: Dict[comp_id, List[game_id]]
        - metadata: Build timestamp, filters, counts

    Example:
        >>> # Build index for 2024-25 Betclic ÉLITE
        >>> indices = build_indices_from_events(year=2025, division_external_id=1)
        >>> print(f"Found {len(indices['competitions'])} competitions")
        >>> print(f"Found {len(indices['teams'])} teams")
    """
    logger.info(f"\n{'='*70}")
    logger.info("Building Competition/Team Indices from Event List")
    logger.info(f"{'='*70}")
    logger.info(f"Year filter: {year or 'All years'}")
    logger.info(f"Division filter: {division_external_id or 'All divisions'}")
    logger.info(f"{'='*70}\n")

    client = LNBClient()

    # Step 1: Fetch all games from /match/getCalenderByDivision
    logger.info("[1/3] Fetching games from /match/getCalenderByDivision...")
    try:
        if year is None:
            year = datetime.now().year
        if division_external_id is None:
            division_external_id = 0  # 0 = all divisions

        games = client.get_calendar_by_division(
            division_external_id=division_external_id, year=year
        )
        logger.info(f"   [OK] Fetched {len(games)} games")
    except Exception as e:
        logger.error(f"   [FAIL] Failed to fetch games: {e}")
        return {}

    # Step 2: Extract unique competitions and teams
    logger.info("\n[2/3] Extracting competitions and teams...")

    competitions: dict[int, dict[str, Any]] = {}
    teams: dict[int, dict[str, Any]] = {}
    competition_teams: dict[int, set[int]] = defaultdict(set)
    competition_games: dict[int, list[int]] = defaultdict(list)

    # Debug: Check first game structure
    if games and logger.level <= logging.INFO:
        logger.debug(f"   Sample game structure (first game keys): {list(games[0].keys())}")

    for game in games:
        # Extract competition
        comp_id = game.get("competition_external_id")
        if comp_id and comp_id not in competitions:
            # Store competition metadata
            comp_data = game.get("competition", {})
            competitions[comp_id] = {
                "external_id": comp_id,
                "name": comp_data.get("name") or game.get("competition_name"),
                "division_external_id": comp_data.get("division_external_id")
                or game.get("division_external_id"),
                "year": comp_data.get("year") or game.get("year"),
                "division": comp_data.get("division", {}),
            }

        # Extract home team
        # Try multiple possible field names for team data
        home_team_data = game.get("home_team", {}) or {}
        if not home_team_data and "home_team_id" in game:
            # Fallback: team data might be at root level
            home_team_data = {
                "external_id": game.get("home_team_id") or game.get("home_team_external_id"),
                "name": game.get("home_team_name"),
                "short_name": game.get("home_team_short_name"),
            }

        home_team_id = (
            home_team_data.get("external_id")
            or home_team_data.get("id")
            or game.get("home_team_id")
            or game.get("home_team_external_id")
        )

        if home_team_id and home_team_id not in teams:
            teams[home_team_id] = {
                "external_id": home_team_id,
                "team_id": home_team_data.get("team_id"),
                "name": home_team_data.get("name") or game.get("home_team_name"),
                "short_name": home_team_data.get("short_name") or game.get("home_team_short_name"),
                "city": home_team_data.get("city"),
                "logo_url": home_team_data.get("logo_url"),
            }

        # Extract away team
        away_team_data = game.get("away_team", {}) or {}
        if not away_team_data and "away_team_id" in game:
            # Fallback: team data might be at root level
            away_team_data = {
                "external_id": game.get("away_team_id") or game.get("away_team_external_id"),
                "name": game.get("away_team_name"),
                "short_name": game.get("away_team_short_name"),
            }

        away_team_id = (
            away_team_data.get("external_id")
            or away_team_data.get("id")
            or game.get("away_team_id")
            or game.get("away_team_external_id")
        )

        if away_team_id and away_team_id not in teams:
            teams[away_team_id] = {
                "external_id": away_team_id,
                "team_id": away_team_data.get("team_id"),
                "name": away_team_data.get("name") or game.get("away_team_name"),
                "short_name": away_team_data.get("short_name") or game.get("away_team_short_name"),
                "city": away_team_data.get("city"),
                "logo_url": away_team_data.get("logo_url"),
            }

        # Build mappings
        if comp_id:
            if home_team_id:
                competition_teams[comp_id].add(home_team_id)
            if away_team_id:
                competition_teams[comp_id].add(away_team_id)

            match_id = game.get("match_external_id") or game.get("external_id")
            if match_id:
                competition_games[comp_id].append(match_id)

    logger.info(f"   [OK] Found {len(competitions)} competitions")
    logger.info(f"   [OK] Found {len(teams)} teams")

    # Step 3: Build final index structure
    logger.info("\n[3/3] Building final indices...")

    # Convert sets to lists for JSON serialization
    competition_teams_list = {
        comp_id: sorted(team_ids) for comp_id, team_ids in competition_teams.items()
    }

    indices = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "source_endpoint": "/match/getCalenderByDivision",
            "filters": {
                "year": year,
                "division_external_id": division_external_id,
            },
            "counts": {
                "competitions": len(competitions),
                "teams": len(teams),
                "games": len(games),
            },
        },
        "competitions": competitions,
        "teams": teams,
        "competition_teams": competition_teams_list,
        "competition_games": {
            comp_id: sorted(set(game_ids)) for comp_id, game_ids in competition_games.items()
        },
    }

    logger.info("   [OK] Indices built successfully")

    # Step 4: Save to file if requested
    if save_to_file:
        logger.info(f"\n[4/4] Saving indices to {output_dir}...")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Determine filename
        filename = "lnb_indices"
        if year:
            filename += f"_{year}"
        if division_external_id is not None:
            filename += f"_div{division_external_id}"
        filename += ".json"

        output_path = Path(output_dir) / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(indices, f, indent=2, ensure_ascii=False)

        logger.info(f"   [OK] Saved to: {output_path}")

    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("Index Build Complete")
    logger.info(f"{'='*70}")
    logger.info(f"Competitions: {len(competitions)}")
    logger.info(f"Teams:        {len(teams)}")
    logger.info(f"Games:        {len(games)}")
    logger.info(f"{'='*70}\n")

    return indices


def print_index_summary(indices: dict[str, Any]) -> None:
    """Print human-readable summary of indices"""
    print(f"\n{'='*70}")
    print("Competition Index Summary")
    print(f"{'='*70}\n")

    competitions = indices.get("competitions", {})
    teams = indices.get("teams", {})
    comp_teams = indices.get("competition_teams", {})
    comp_games = indices.get("competition_games", {})

    print(f"Total Competitions: {len(competitions)}")
    print(f"Total Teams:        {len(teams)}\n")

    print("Competitions:")
    print("-" * 70)
    for comp_id, comp in sorted(competitions.items()):
        num_teams = len(comp_teams.get(comp_id, []))
        num_games = len(comp_games.get(comp_id, []))
        comp_name = comp.get("name") or f"Competition {comp_id}"
        print(f"  [{comp_id:3d}] {comp_name:30s} | {num_teams:2d} teams | {num_games:3d} games")

    print()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Build competition/team indices from event list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build index for 2024-25 all divisions
  python tools/lnb/build_competition_index.py --year 2025

  # Build for Betclic ÉLITE only
  python tools/lnb/build_competition_index.py --year 2025 --division 1

  # Build and save to file
  python tools/lnb/build_competition_index.py --year 2025 --division 1 --save
        """,
    )

    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filter to specific year (e.g., 2025 for 2024-25 season)",
    )
    parser.add_argument(
        "--division",
        type=int,
        default=None,
        help="Filter to specific division (1=Betclic ÉLITE, 2=Pro B)",
    )
    parser.add_argument("--save", action="store_true", help="Save indices to JSON file")
    parser.add_argument(
        "--output-dir", default="tools/lnb/indices", help="Directory for saved indices"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Set logging level
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s"
    )

    # Build indices
    indices = build_indices_from_events(
        year=args.year,
        division_external_id=args.division,
        save_to_file=args.save,
        output_dir=args.output_dir,
    )

    if not indices:
        print("[FAIL] Failed to build indices")
        sys.exit(1)

    # Print summary
    print_index_summary(indices)

    print("[OK] Index build complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
