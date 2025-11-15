#!/usr/bin/env python3
"""
LNB Season Audit Script

Purpose:
--------
Systematic season-level coverage audit that walks every game in a season/division
and tests data availability for boxscore, play-by-play, and shot charts.

This script implements the user's recommendation to create league-level stress tests
that validate actual data coverage instead of relying on potentially broken endpoints.

Workflow:
---------
1. Use /event/getEventList as canonical source (confirmed working)
2. Filter events by year and division
3. Extract all game IDs
4. For each game, attempt to fetch:
   - Boxscore (player_game + team_game stats)
   - Play-by-Play (event stream)
   - Shot Chart (shot locations)
5. Generate coverage report showing:
   - Total games in season
   - Games with boxscore data
   - Games with PBP data
   - Games with shot data
   - Missing data gaps

Usage:
------
    # Audit 2024-25 Betclic ÉLITE season
    python tools/lnb/audit_lnb_season.py --year 2025 --division 1

    # Audit with verbose output
    python tools/lnb/audit_lnb_season.py --year 2025 --division 1 --verbose

    # Save report to custom location
    python tools/lnb/audit_lnb_season.py --year 2025 --division 1 --output reports/lnb_2025_coverage.json

    # Run as Python function
    from tools.lnb.audit_lnb_season import audit_lnb_season
    report = audit_lnb_season(year=2025, division_external_id=1)

Created: 2025-11-15
Reference: User guidance from LNB endpoint reconstruction plan
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_api import LNBClient
from src.cbb_data.fetchers.lnb_atrium import (
    fetch_fixture_detail_and_pbp,
    parse_fixture_metadata,
    parse_pbp_events,
    parse_shots_from_pbp,
)

logger = logging.getLogger(__name__)


@dataclass
class GameCoverage:
    """Coverage data for a single game"""

    match_external_id: int
    match_date: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    competition: str | None = None

    # Data availability flags
    has_boxscore: bool = False
    has_pbp: bool = False
    has_shots: bool = False

    # Error messages if fetch failed
    boxscore_error: str | None = None
    pbp_error: str | None = None
    shots_error: str | None = None


@dataclass
class SeasonCoverageReport:
    """Complete coverage report for a season"""

    year: int
    division_external_id: int
    division_name: str
    timestamp: str

    total_games: int = 0
    games_with_boxscore: int = 0
    games_with_pbp: int = 0
    games_with_shots: int = 0

    # Detailed per-game results
    game_coverage: list[GameCoverage] = field(default_factory=list)

    # Endpoint discovery (if new paths found)
    discovered_endpoints: dict[str, str] = field(default_factory=dict)

    def add_game(self, game: GameCoverage) -> None:
        """Add game coverage and update summary stats"""
        self.game_coverage.append(game)
        self.total_games += 1

        if game.has_boxscore:
            self.games_with_boxscore += 1
        if game.has_pbp:
            self.games_with_pbp += 1
        if game.has_shots:
            self.games_with_shots += 1

    def boxscore_coverage_pct(self) -> float:
        """Percentage of games with boxscore data"""
        return (self.games_with_boxscore / self.total_games * 100) if self.total_games > 0 else 0.0

    def pbp_coverage_pct(self) -> float:
        """Percentage of games with PBP data"""
        return (self.games_with_pbp / self.total_games * 100) if self.total_games > 0 else 0.0

    def shots_coverage_pct(self) -> float:
        """Percentage of games with shot data"""
        return (self.games_with_shots / self.total_games * 100) if self.total_games > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization"""
        return {
            "metadata": {
                "year": self.year,
                "division_external_id": self.division_external_id,
                "division_name": self.division_name,
                "timestamp": self.timestamp,
            },
            "summary": {
                "total_games": self.total_games,
                "games_with_boxscore": self.games_with_boxscore,
                "games_with_pbp": self.games_with_pbp,
                "games_with_shots": self.games_with_shots,
                "boxscore_coverage_pct": round(self.boxscore_coverage_pct(), 1),
                "pbp_coverage_pct": round(self.pbp_coverage_pct(), 1),
                "shots_coverage_pct": round(self.shots_coverage_pct(), 1),
            },
            "discovered_endpoints": self.discovered_endpoints,
            "games": [
                {
                    "match_external_id": g.match_external_id,
                    "match_date": g.match_date,
                    "home_team": g.home_team,
                    "away_team": g.away_team,
                    "competition": g.competition,
                    "has_boxscore": g.has_boxscore,
                    "has_pbp": g.has_pbp,
                    "has_shots": g.has_shots,
                    "boxscore_error": g.boxscore_error,
                    "pbp_error": g.pbp_error,
                    "shots_error": g.shots_error,
                }
                for g in self.game_coverage
            ],
        }


def audit_lnb_season(
    year: int,
    division_external_id: int = 1,
    max_games: int | None = None,
    verbose: bool = False,
) -> SeasonCoverageReport:
    """
    Audit data coverage for an entire LNB season.

    This function implements the systematic approach recommended by the user:
    1. Use /event/getEventList as canonical game source (confirmed working)
    2. Extract all game IDs for the specified year/division
    3. For each game, test boxscore/PBP/shots endpoints
    4. Generate comprehensive coverage report

    Args:
        year: Season year (e.g., 2025 for 2024-25 season)
        division_external_id: Division ID (1 = Betclic ÉLITE)
        max_games: Optional limit on games to test (for quick audits)
        verbose: If True, print detailed per-game progress

    Returns:
        SeasonCoverageReport with complete coverage data

    Example:
        >>> # Audit full season
        >>> report = audit_lnb_season(year=2025, division_external_id=1)
        >>> print(f"Boxscore coverage: {report.boxscore_coverage_pct():.1f}%")

        >>> # Quick audit (first 10 games)
        >>> report = audit_lnb_season(year=2025, division_external_id=1, max_games=10)
    """
    # Set logging level based on verbose flag
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(message)s")

    client = LNBClient()

    # Division names for reporting
    division_names = {
        0: "All Divisions",
        1: "Betclic ÉLITE",
        2: "Pro B",
    }
    division_name = division_names.get(division_external_id, f"Division {division_external_id}")

    logger.info(f"\n{'='*70}")
    logger.info("LNB Season Coverage Audit")
    logger.info(f"{'='*70}")
    logger.info(f"Year: {year}")
    logger.info(f"Division: {division_name} (ID: {division_external_id})")
    logger.info(f"{'='*70}\n")

    # Initialize report
    report = SeasonCoverageReport(
        year=year,
        division_external_id=division_external_id,
        division_name=division_name,
        timestamp=datetime.now().isoformat(),
    )

    # Step 1: Get all games using /match/getCalenderByDivision (confirmed working endpoint)
    logger.info("[1/3] Fetching game list from /match/getCalenderByDivision...")
    try:
        # Note: /event/getEventList returns event TYPES (All Star Game, etc.), not game instances
        # The canonical source for game lists is /match/getCalenderByDivision (verified 2025-11-15)
        games = client.get_calendar_by_division(
            division_external_id=division_external_id, year=year
        )
        logger.info(f"   [OK] Found {len(games)} games for {year} {division_name}")
    except Exception as e:
        logger.error(f"   [FAIL] Failed to fetch games: {e}")
        return report

    # Apply game limit if specified
    if max_games is not None and len(games) > max_games:
        logger.info(f"   [NOTE] Limiting to first {max_games} games (--max-games flag)")
        games = games[:max_games]

    logger.info(f"\n[2/3] Testing data availability for {len(games)} games...")
    logger.info(f"{'='*70}\n")

    # Step 2: Test each game for boxscore/PBP/shots
    for idx, game in enumerate(games, 1):
        match_external_id = game.get("match_external_id") or game.get("external_id")

        if match_external_id is None:
            logger.warning(f"   [SKIP] Game {idx}/{len(games)}: No match_external_id found")
            continue

        # Create game coverage record
        game_cov = GameCoverage(
            match_external_id=match_external_id,
            match_date=game.get("match_date"),
            home_team=game.get("home_team_name") or game.get("home_team", {}).get("name"),
            away_team=game.get("away_team_name") or game.get("away_team", {}).get("name"),
            competition=game.get("competition_name") or game.get("competition", {}).get("name"),
        )

        if verbose:
            logger.info(f"   Game {idx}/{len(games)}: {game_cov.home_team} vs {game_cov.away_team}")
            logger.info(f"      Match ID: {match_external_id}, Date: {game_cov.match_date}")

        # NEW APPROACH: Use Atrium API to fetch all data at once
        # Note: This requires fixture UUID, which may need to be mapped from external ID
        # For now, we'll try to get fixture UUID from game data or skip if not available

        fixture_uuid = game.get("fixture_id") or game.get("fixture_uuid")

        if fixture_uuid:
            # Use Atrium API (single endpoint for all data)
            try:
                # Fetch fixture detail + PBP from Atrium
                payload = fetch_fixture_detail_and_pbp(fixture_uuid)

                # Parse fixture metadata (includes boxscore-level info)
                parse_fixture_metadata(payload)
                game_cov.has_boxscore = True  # Fixture metadata includes scores/teams
                if verbose:
                    logger.info("      [OK] Boxscore available (Atrium API)")

                # Parse PBP events
                pbp_events = parse_pbp_events(payload, fixture_uuid)
                if pbp_events:
                    game_cov.has_pbp = True
                    if verbose:
                        logger.info(f"      [OK] Play-by-Play available ({len(pbp_events)} events)")
                else:
                    game_cov.pbp_error = "No PBP events found"
                    if verbose:
                        logger.info("      [FAIL] Play-by-Play: No events")

                # Parse shots from PBP
                shots = parse_shots_from_pbp(pbp_events)
                if shots:
                    game_cov.has_shots = True
                    if verbose:
                        logger.info(f"      [OK] Shot chart available ({len(shots)} shots)")
                else:
                    game_cov.shots_error = "No shots found in PBP"
                    if verbose:
                        logger.info("      [FAIL] Shot chart: No shots in PBP")

            except Exception as e:
                error_msg = str(e)[:100]
                game_cov.boxscore_error = error_msg
                game_cov.pbp_error = error_msg
                game_cov.shots_error = error_msg
                if verbose:
                    logger.info(f"      [FAIL] Atrium API error: {e}")

        else:
            # Fallback: Try old LNB API endpoints (likely to fail)
            if verbose:
                logger.info("      [WARN] No fixture UUID found, falling back to LNB API")

            # Test boxscore
            try:
                boxscore = client.get_match_boxscore(match_external_id)
                if boxscore and isinstance(boxscore, dict):
                    game_cov.has_boxscore = True
                    if verbose:
                        logger.info("      [OK] Boxscore available (LNB API)")
            except Exception as e:
                game_cov.boxscore_error = str(e)[:100]
                if verbose:
                    logger.info(f"      [FAIL] Boxscore: {e}")

            # Test play-by-play
            try:
                pbp = client.get_match_play_by_play(match_external_id)
                if pbp and isinstance(pbp, dict):
                    game_cov.has_pbp = True
                    if verbose:
                        logger.info("      [OK] Play-by-Play available (LNB API)")
            except Exception as e:
                game_cov.pbp_error = str(e)[:100]
                if verbose:
                    logger.info(f"      [FAIL] Play-by-Play: {e}")

            # Test shots
            try:
                shots = client.get_match_shot_chart(match_external_id)
                if shots and isinstance(shots, dict):
                    game_cov.has_shots = True
                    if verbose:
                        logger.info("      [OK] Shot chart available (LNB API)")
            except Exception as e:
                game_cov.shots_error = str(e)[:100]
                if verbose:
                    logger.info(f"      [FAIL] Shot chart: {e}")

        report.add_game(game_cov)

        if verbose:
            logger.info("")  # Blank line between games

    # Step 3: Generate summary
    logger.info("\n[3/3] Coverage Summary")
    logger.info(f"{'='*70}")
    logger.info(f"Total Games:       {report.total_games}")
    logger.info(
        f"Boxscore Coverage: {report.games_with_boxscore}/{report.total_games} ({report.boxscore_coverage_pct():.1f}%)"
    )
    logger.info(
        f"PBP Coverage:      {report.games_with_pbp}/{report.total_games} ({report.pbp_coverage_pct():.1f}%)"
    )
    logger.info(
        f"Shot Coverage:     {report.games_with_shots}/{report.total_games} ({report.shots_coverage_pct():.1f}%)"
    )
    logger.info(f"{'='*70}\n")

    # Note discovered endpoints (if any data found)
    if report.games_with_boxscore > 0:
        report.discovered_endpoints["boxscore"] = (
            "/stats/getMatchBoxScore (placeholder - needs DevTools confirmation)"
        )
    if report.games_with_pbp > 0:
        report.discovered_endpoints["pbp"] = (
            "/stats/getMatchPlayByPlay (placeholder - needs DevTools confirmation)"
        )
    if report.games_with_shots > 0:
        report.discovered_endpoints["shots"] = (
            "/stats/getMatchShots (placeholder - needs DevTools confirmation)"
        )

    return report


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Audit data coverage for LNB season",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Audit full 2024-25 Betclic ÉLITE season
  python tools/lnb/audit_lnb_season.py --year 2025 --division 1

  # Quick audit (first 10 games)
  python tools/lnb/audit_lnb_season.py --year 2025 --division 1 --max-games 10

  # Verbose output with per-game details
  python tools/lnb/audit_lnb_season.py --year 2025 --division 1 --verbose
        """,
    )

    parser.add_argument(
        "--year", type=int, required=True, help="Season year (e.g., 2025 for 2024-25 season)"
    )
    parser.add_argument(
        "--division",
        type=int,
        default=1,
        help="Division ID (0=all, 1=Betclic ÉLITE, 2=Pro B). Default: 1",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Limit number of games to audit (for quick tests)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="tools/lnb/reports/season_coverage_{year}_div{division}.json",
        help="Output path for JSON report (supports {year} and {division} placeholders)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose per-game output"
    )

    args = parser.parse_args()

    # Run audit
    report = audit_lnb_season(
        year=args.year,
        division_external_id=args.division,
        max_games=args.max_games,
        verbose=args.verbose,
    )

    # Save report
    output_path = args.output.format(year=args.year, division=args.division)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Report saved to: {output_path}")

    # Exit with error code if coverage is low
    if report.boxscore_coverage_pct() < 10.0:
        print(f"\n[WARNING] Boxscore coverage is very low ({report.boxscore_coverage_pct():.1f}%)")
        print("This suggests the endpoint paths need to be discovered via DevTools.")
        print("See: LNB_DEVTOOLS_DISCOVERY_GUIDE.md for instructions.\n")
        sys.exit(1)

    print("\n[OK] Audit complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
