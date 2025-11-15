#!/usr/bin/env python3
"""Comprehensive Historical Coverage Stress Test for LNB Data

This script performs an exhaustive test of LNB data availability across multiple
historical seasons to determine:
1. How far back fixture data is available
2. How far back PBP data is available
3. How far back shot data is available
4. Coverage percentages for each dataset by season
5. Data quality metrics (score validation, event counts, etc.)

The test goes back season by season from current to historical, testing:
- LNB calendar API (schedule/fixture list)
- Atrium API (fixture detail + PBP + shots)
- Data completeness and validation

Output:
- Detailed per-season coverage report
- Summary of historical data availability
- Recommendations for reliable data ranges

Usage:
    # Test all seasons back to 2015
    python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2015

    # Test recent 3 seasons only
    python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2022

    # Test with sample size limit
    python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2020 --max-games-per-season 50

Created: 2025-11-15
Purpose: Historical data availability stress testing
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_api import LNBClient
from src.cbb_data.fetchers.lnb_atrium import (
    fetch_fixture_detail_and_pbp,
    parse_fixture_metadata,
    parse_pbp_events,
    parse_shots_from_pbp,
    validate_fixture_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class GameCoverageStats:
    """Coverage statistics for a single game"""

    fixture_uuid: str
    external_id: str | None
    season: str
    division: int

    # Fixture metadata
    has_fixture_metadata: bool = False
    home_team: str = ""
    away_team: str = ""
    home_score: int = 0
    away_score: int = 0
    game_date: str = ""
    status: str = ""

    # PBP coverage
    has_pbp: bool = False
    pbp_events_count: int = 0
    pbp_periods_count: int = 0

    # Shot coverage
    has_shots: bool = False
    shots_count: int = 0
    shots_made_count: int = 0
    shots_2pt_count: int = 0
    shots_3pt_count: int = 0
    shots_ft_count: int = 0

    # Validation
    score_validation_passed: bool = False
    score_validation_errors: list[str] = field(default_factory=list)

    # Errors
    fetch_error: str | None = None
    parse_error: str | None = None


@dataclass
class SeasonCoverageStats:
    """Coverage statistics for an entire season"""

    season: str
    division: int
    division_name: str

    # Games discovered
    games_in_calendar: int = 0
    games_with_uuid: int = 0

    # Fixture metadata
    fixtures_fetched: int = 0
    fixtures_failed: int = 0
    fixture_coverage_pct: float = 0.0

    # PBP coverage
    games_with_pbp: int = 0
    pbp_coverage_pct: float = 0.0
    total_pbp_events: int = 0
    avg_pbp_events_per_game: float = 0.0

    # Shot coverage
    games_with_shots: int = 0
    shot_coverage_pct: float = 0.0
    total_shots: int = 0
    avg_shots_per_game: float = 0.0

    # Validation
    games_validated: int = 0
    validation_pass_rate: float = 0.0

    # Quality metrics
    avg_home_score: float = 0.0
    avg_away_score: float = 0.0
    avg_total_score: float = 0.0

    # Errors
    common_errors: list[str] = field(default_factory=list)

    # Per-game details
    games: list[GameCoverageStats] = field(default_factory=list)


@dataclass
class HistoricalCoverageReport:
    """Complete historical coverage report"""

    test_timestamp: str
    start_year: int
    end_year: int
    total_seasons_tested: int

    # Overall stats
    total_games_discovered: int = 0
    total_fixtures_fetched: int = 0
    total_pbp_events: int = 0
    total_shots: int = 0

    # Coverage by dataset
    overall_fixture_coverage: float = 0.0
    overall_pbp_coverage: float = 0.0
    overall_shot_coverage: float = 0.0

    # Historical cutoffs
    oldest_season_with_fixtures: str | None = None
    oldest_season_with_pbp: str | None = None
    oldest_season_with_shots: str | None = None

    # Recommended ranges
    recommended_fixture_range: str = ""
    recommended_pbp_range: str = ""
    recommended_shot_range: str = ""

    # Per-season details
    seasons: list[SeasonCoverageStats] = field(default_factory=list)


def test_season_coverage(
    year: int,
    division: int = 1,
    max_games: int | None = None,
    verbose: bool = False,
) -> SeasonCoverageStats:
    """
    Test data coverage for a single season.

    NOTE: LNB API uses START year (year=2025 for 2025-26 season, NOT 2024-25)

    Args:
        year: Season START year (e.g., 2025 for 2025-26 season)
        division: Division ID (1 = Betclic ÉLITE)
        max_games: Optional limit on games to test
        verbose: Enable verbose logging

    Returns:
        SeasonCoverageStats with complete coverage data
    """
    # LNB API uses START year (year=2025 for 2025-2026 season)
    season_name = f"{year}-{year+1}"
    division_name = "Betclic ÉLITE" if division == 1 else f"Division {division}"

    logger.info(f"\n{'='*70}")
    logger.info(f"Testing Season: {season_name} ({division_name})")
    logger.info(f"{'='*70}")

    stats = SeasonCoverageStats(
        season=season_name,
        division=division,
        division_name=division_name,
    )

    # Step 1: Get calendar/fixture list
    logger.info(f"[1/3] Fetching calendar for {season_name}...")
    try:
        client = LNBClient()
        games = client.get_calendar_by_division(division_external_id=division, year=year)

        stats.games_in_calendar = len(games)
        logger.info(f"   [OK] Found {len(games)} games in calendar")

        # Extract UUIDs
        games_to_test = []
        for game in games:
            uuid = game.get("match_id") or game.get("fixture_id") or game.get("fixture_uuid")
            if uuid:
                games_to_test.append(
                    {
                        "uuid": uuid,
                        "external_id": game.get("external_id") or game.get("match_external_id"),
                        "game_data": game,
                    }
                )

        stats.games_with_uuid = len(games_to_test)
        logger.info(f"   [OK] Extracted {len(games_to_test)} UUIDs")

        # Limit if requested
        if max_games and len(games_to_test) > max_games:
            logger.info(f"   [INFO] Limiting to first {max_games} games")
            games_to_test = games_to_test[:max_games]

    except Exception as e:
        logger.error(f"   [FAIL] Calendar fetch failed: {e}")
        stats.common_errors.append(f"Calendar fetch: {str(e)}")
        return stats

    # Step 2: Test each game
    logger.info(f"\n[2/3] Testing {len(games_to_test)} games...")

    for idx, game_info in enumerate(games_to_test, 1):
        uuid = game_info["uuid"]
        external_id = game_info["external_id"]

        if verbose:
            logger.info(f"   [{idx}/{len(games_to_test)}] Testing {uuid}...")

        game_stats = GameCoverageStats(
            fixture_uuid=uuid,
            external_id=str(external_id) if external_id else None,
            season=season_name,
            division=division,
        )

        try:
            # Fetch from Atrium API
            payload = fetch_fixture_detail_and_pbp(uuid)

            # Parse fixture metadata
            try:
                metadata = parse_fixture_metadata(payload)
                game_stats.has_fixture_metadata = True
                game_stats.home_team = metadata.home_team_name
                game_stats.away_team = metadata.away_team_name
                game_stats.home_score = metadata.home_score
                game_stats.away_score = metadata.away_score
                game_stats.game_date = metadata.start_time_local
                game_stats.status = metadata.status

                stats.fixtures_fetched += 1

                if verbose:
                    logger.info(
                        f"      Fixture: {metadata.home_team_name} vs {metadata.away_team_name} ({metadata.home_score}-{metadata.away_score})"
                    )

            except Exception as e:
                game_stats.parse_error = f"Metadata parse: {str(e)}"
                if verbose:
                    logger.warning(f"      [WARN] Metadata parse failed: {e}")

            # Parse PBP events
            try:
                pbp_events = parse_pbp_events(payload, uuid)

                if pbp_events:
                    game_stats.has_pbp = True
                    game_stats.pbp_events_count = len(pbp_events)

                    # Count unique periods
                    periods = {e.period_id for e in pbp_events}
                    game_stats.pbp_periods_count = len(periods)

                    stats.total_pbp_events += len(pbp_events)

                    if verbose:
                        logger.info(
                            f"      PBP: {len(pbp_events)} events across {len(periods)} periods"
                        )

                # Parse shots
                shots = parse_shots_from_pbp(pbp_events)

                if shots:
                    game_stats.has_shots = True
                    game_stats.shots_count = len(shots)
                    game_stats.shots_made_count = sum(1 for s in shots if s.made)
                    game_stats.shots_2pt_count = sum(1 for s in shots if s.shot_value == 2)
                    game_stats.shots_3pt_count = sum(1 for s in shots if s.shot_value == 3)
                    game_stats.shots_ft_count = sum(1 for s in shots if s.shot_value == 1)

                    stats.total_shots += len(shots)

                    if verbose:
                        logger.info(
                            f"      Shots: {len(shots)} total ({game_stats.shots_made_count} made)"
                        )

                # Validate scores
                is_valid, errors = validate_fixture_scores(payload, pbp_events)
                game_stats.score_validation_passed = is_valid
                game_stats.score_validation_errors = errors

                if is_valid and pbp_events:
                    stats.games_validated += 1

            except Exception as e:
                game_stats.parse_error = f"PBP parse: {str(e)}"
                if verbose:
                    logger.warning(f"      [WARN] PBP parse failed: {e}")

        except Exception as e:
            game_stats.fetch_error = str(e)
            stats.fixtures_failed += 1
            if verbose:
                logger.warning(f"      [FAIL] Fetch failed: {e}")

        # Track coverage
        if game_stats.has_pbp:
            stats.games_with_pbp += 1
        if game_stats.has_shots:
            stats.games_with_shots += 1

        stats.games.append(game_stats)

    # Step 3: Calculate statistics
    logger.info("\n[3/3] Calculating statistics...")

    if stats.games_with_uuid > 0:
        stats.fixture_coverage_pct = (stats.fixtures_fetched / stats.games_with_uuid) * 100
        stats.pbp_coverage_pct = (stats.games_with_pbp / stats.games_with_uuid) * 100
        stats.shot_coverage_pct = (stats.games_with_shots / stats.games_with_uuid) * 100

    if stats.games_with_pbp > 0:
        stats.avg_pbp_events_per_game = stats.total_pbp_events / stats.games_with_pbp

    if stats.games_with_shots > 0:
        stats.avg_shots_per_game = stats.total_shots / stats.games_with_shots

    if stats.fixtures_fetched > 0:
        stats.validation_pass_rate = (stats.games_validated / stats.fixtures_fetched) * 100

    # Calculate score averages
    games_with_scores = [g for g in stats.games if g.has_fixture_metadata and g.home_score > 0]
    if games_with_scores:
        stats.avg_home_score = sum(g.home_score for g in games_with_scores) / len(games_with_scores)
        stats.avg_away_score = sum(g.away_score for g in games_with_scores) / len(games_with_scores)
        stats.avg_total_score = stats.avg_home_score + stats.avg_away_score

    # Collect common errors
    error_counts = defaultdict(int)
    for game in stats.games:
        if game.fetch_error:
            error_counts[game.fetch_error] += 1
        if game.parse_error:
            error_counts[game.parse_error] += 1

    # Top 5 most common errors
    stats.common_errors = [
        f"{error} (n={count})"
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1])[:5]
    ]

    logger.info(
        f"   [OK] Coverage: Fixtures={stats.fixture_coverage_pct:.1f}%, PBP={stats.pbp_coverage_pct:.1f}%, Shots={stats.shot_coverage_pct:.1f}%"
    )

    return stats


def run_historical_stress_test(
    start_year: int = 2025,
    end_year: int = 2015,
    division: int = 1,
    max_games_per_season: int | None = None,
    output_dir: str = "tools/lnb/stress_results",
    verbose: bool = False,
) -> HistoricalCoverageReport:
    """
    Run comprehensive historical stress test across multiple seasons.

    NOTE: The LNB API uses the season START year as the year parameter.
          year=2025 returns 2025-2026 season (NOT 2024-2025)

    Args:
        start_year: Most recent season START year to test (e.g., 2025 for 2025-26)
        end_year: Oldest season START year to test (e.g., 2015 for 2015-16)
        division: Division ID (1 = Betclic ÉLITE)
        max_games_per_season: Optional limit per season
        output_dir: Directory for output reports
        verbose: Enable verbose logging

    Returns:
        HistoricalCoverageReport with complete findings

    Example:
        # Test current season (2025-26) and 2 previous seasons (2024-25, 2023-24)
        run_historical_stress_test(start_year=2025, end_year=2023)
    """
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print(f"\n{'='*80}")
    print("LNB HISTORICAL DATA COVERAGE STRESS TEST")
    print(f"{'='*80}")
    # LNB API uses START year (year=2025 for 2025-2026 season)
    print(f"Testing Seasons: {end_year}-{end_year+1} through {start_year}-{start_year+1}")
    print(f"Division: {division} (Betclic ÉLITE)" if division == 1 else f"Division: {division}")
    if max_games_per_season:
        print(f"Sample Size: {max_games_per_season} games per season")
    print(f"{'='*80}\n")

    report = HistoricalCoverageReport(
        test_timestamp=datetime.now().isoformat(),
        start_year=start_year,
        end_year=end_year,
        total_seasons_tested=start_year - end_year + 1,
    )

    # Test each season
    for year in range(start_year, end_year - 1, -1):
        season_stats = test_season_coverage(
            year=year,
            division=division,
            max_games=max_games_per_season,
            verbose=verbose,
        )

        report.seasons.append(season_stats)

        # Update totals
        report.total_games_discovered += season_stats.games_with_uuid
        report.total_fixtures_fetched += season_stats.fixtures_fetched
        report.total_pbp_events += season_stats.total_pbp_events
        report.total_shots += season_stats.total_shots

        # Track oldest seasons with data
        if season_stats.fixtures_fetched > 0:
            if not report.oldest_season_with_fixtures:
                report.oldest_season_with_fixtures = season_stats.season

        if season_stats.games_with_pbp > 0:
            if not report.oldest_season_with_pbp:
                report.oldest_season_with_pbp = season_stats.season

        if season_stats.games_with_shots > 0:
            if not report.oldest_season_with_shots:
                report.oldest_season_with_shots = season_stats.season

    # Calculate overall coverage
    if report.total_games_discovered > 0:
        report.overall_fixture_coverage = (
            report.total_fixtures_fetched / report.total_games_discovered
        ) * 100

        total_games_with_pbp = sum(s.games_with_pbp for s in report.seasons)
        report.overall_pbp_coverage = (total_games_with_pbp / report.total_games_discovered) * 100

        total_games_with_shots = sum(s.games_with_shots for s in report.seasons)
        report.overall_shot_coverage = (
            total_games_with_shots / report.total_games_discovered
        ) * 100

    # Determine recommended ranges (seasons with >80% coverage)
    fixture_seasons = [s.season for s in report.seasons if s.fixture_coverage_pct > 80]
    pbp_seasons = [s.season for s in report.seasons if s.pbp_coverage_pct > 80]
    shot_seasons = [s.season for s in report.seasons if s.shot_coverage_pct > 80]

    if fixture_seasons:
        report.recommended_fixture_range = f"{fixture_seasons[-1]} to {fixture_seasons[0]}"
    if pbp_seasons:
        report.recommended_pbp_range = f"{pbp_seasons[-1]} to {pbp_seasons[0]}"
    if shot_seasons:
        report.recommended_shot_range = f"{shot_seasons[-1]} to {shot_seasons[0]}"

    # Save detailed report
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON report
    json_file = output_path / f"historical_coverage_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False)

    logger.info(f"\n[OK] Saved detailed JSON report: {json_file}")

    # Save CSV summary
    csv_file = output_path / f"historical_coverage_summary_{timestamp}.csv"
    df = pd.DataFrame(
        [
            {
                "Season": s.season,
                "Games_in_Calendar": s.games_in_calendar,
                "Games_with_UUID": s.games_with_uuid,
                "Fixtures_Fetched": s.fixtures_fetched,
                "Fixture_Coverage_%": f"{s.fixture_coverage_pct:.1f}",
                "Games_with_PBP": s.games_with_pbp,
                "PBP_Coverage_%": f"{s.pbp_coverage_pct:.1f}",
                "Avg_PBP_Events": f"{s.avg_pbp_events_per_game:.0f}",
                "Games_with_Shots": s.games_with_shots,
                "Shot_Coverage_%": f"{s.shot_coverage_pct:.1f}",
                "Avg_Shots": f"{s.avg_shots_per_game:.0f}",
                "Validation_Pass_Rate_%": f"{s.validation_pass_rate:.1f}",
                "Avg_Total_Score": f"{s.avg_total_score:.1f}",
            }
            for s in report.seasons
        ]
    )

    df.to_csv(csv_file, index=False)
    logger.info(f"[OK] Saved CSV summary: {csv_file}")

    return report


def print_report_summary(report: HistoricalCoverageReport) -> None:
    """Print human-readable summary of stress test results"""

    print(f"\n{'='*80}")
    print("HISTORICAL COVERAGE STRESS TEST - SUMMARY")
    print(f"{'='*80}\n")

    # LNB API uses START year (year=2025 for 2025-2026 season)
    print(
        f"Test Period: {report.end_year}-{report.end_year+1} to {report.start_year}-{report.start_year+1}"
    )
    print(f"Seasons Tested: {report.total_seasons_tested}")
    print(f"Total Games Discovered: {report.total_games_discovered}")
    print(f"Total Fixtures Fetched: {report.total_fixtures_fetched}")
    print(f"Total PBP Events: {report.total_pbp_events:,}")
    print(f"Total Shots: {report.total_shots:,}\n")

    print("Overall Coverage:")
    print(f"  Fixtures: {report.overall_fixture_coverage:.1f}%")
    print(f"  PBP:      {report.overall_pbp_coverage:.1f}%")
    print(f"  Shots:    {report.overall_shot_coverage:.1f}%\n")

    print("Historical Data Availability:")
    print(f"  Oldest Season with Fixtures: {report.oldest_season_with_fixtures or 'None'}")
    print(f"  Oldest Season with PBP:      {report.oldest_season_with_pbp or 'None'}")
    print(f"  Oldest Season with Shots:    {report.oldest_season_with_shots or 'None'}\n")

    print("Recommended Ranges (>80% coverage):")
    print(f"  Fixtures: {report.recommended_fixture_range or 'None'}")
    print(f"  PBP:      {report.recommended_pbp_range or 'None'}")
    print(f"  Shots:    {report.recommended_shot_range or 'None'}\n")

    print(f"{'='*80}")
    print("PER-SEASON BREAKDOWN")
    print(f"{'='*80}\n")

    print(
        f"{'Season':<12} {'Games':<7} {'Fix%':<6} {'PBP%':<6} {'Shot%':<6} {'AvgPBP':<8} {'AvgShots':<9} {'AvgScore':<9}"
    )
    print(f"{'-'*80}")

    for s in report.seasons:
        print(
            f"{s.season:<12} "
            f"{s.games_with_uuid:<7} "
            f"{s.fixture_coverage_pct:>5.1f}% "
            f"{s.pbp_coverage_pct:>5.1f}% "
            f"{s.shot_coverage_pct:>5.1f}% "
            f"{s.avg_pbp_events_per_game:>7.0f} "
            f"{s.avg_shots_per_game:>8.0f} "
            f"{s.avg_total_score:>8.1f}"
        )

    print(f"\n{'='*80}\n")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Comprehensive historical coverage stress test for LNB data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all seasons back to 2015
  python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2015

  # Test recent 3 seasons only
  python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2022

  # Test with sample size limit (faster)
  python tools/lnb/stress_test_historical_coverage.py --start-year 2025 --end-year 2020 --max-games-per-season 20
        """,
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2025,
        help="Most recent season year to test (e.g., 2025 for 2024-25 season)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2015,
        help="Oldest season year to test (e.g., 2015 for 2014-15 season)",
    )
    parser.add_argument(
        "--division", type=int, default=1, help="Division ID (1=Betclic ÉLITE, 2=Pro B)"
    )
    parser.add_argument(
        "--max-games-per-season",
        type=int,
        help="Optional limit on games to test per season (for faster testing)",
    )
    parser.add_argument(
        "--output-dir", default="tools/lnb/stress_results", help="Output directory for reports"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Validate years
    if args.start_year < args.end_year:
        parser.error(f"start-year ({args.start_year}) must be >= end-year ({args.end_year})")

    # Run stress test
    report = run_historical_stress_test(
        start_year=args.start_year,
        end_year=args.end_year,
        division=args.division,
        max_games_per_season=args.max_games_per_season,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )

    # Print summary
    print_report_summary(report)

    print("[OK] Stress test complete!\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
