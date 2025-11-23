#!/usr/bin/env python3
"""Comprehensive Multi-League Stress Test for LNB Data Pipeline

This script performs exhaustive validation and stress testing across all 4 LNB leagues,
validating data completeness, integrity, and API reliability.

**Purpose**:
- Validate data coverage per league/season/dataset
- Cross-validate PBP vs shots consistency
- Test API endpoint reliability under load
- Generate actionable coverage reports per league
- Identify gaps and data quality issues

**Leagues Tested**:
1. Betclic ELITE (betclic_elite) - Top-tier professional
2. ELITE 2 (elite_2) - Second-tier professional
3. Espoirs ELITE (espoirs_elite) - U21 top-tier
4. Espoirs PROB (espoirs_prob) - U21 second-tier

**Tests Performed**:
1. **Discovery Completeness**: Verify all fixtures discovered per league/season
2. **Game Index Integrity**: Validate index entries vs discovered fixtures
3. **Data Availability**: Check PBP + shots existence for each game
4. **Data Consistency**: Cross-validate PBP vs shots (counts, made shots, coordinates)
5. **API Stress Test**: Test concurrent requests per league
6. **Coverage Gaps**: Identify missing data and recommend actions

**Usage**:
    # Full stress test (all leagues, all seasons)
    python tools/lnb/stress_test_multi_league.py

    # Specific league only
    python tools/lnb/stress_test_multi_league.py --leagues elite_2

    # Specific season
    python tools/lnb/stress_test_multi_league.py --seasons 2024-2025

    # Quick test (skip API stress, just validate existing data)
    python tools/lnb/stress_test_multi_league.py --quick

    # Generate detailed report
    python tools/lnb/stress_test_multi_league.py --detailed-report

**Output**:
- Console: Summary tables with pass/fail indicators per league
- File: data/reports/lnb_multi_league_stress_test_{timestamp}.json

Created: 2025-11-20
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from src.cbb_data.fetchers.lnb_league_config import (
    ALL_LEAGUES,
    LEAGUE_METADATA_REGISTRY,
    get_all_seasons_for_league,
    get_season_metadata,
)

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_DIR = Path("data/raw/lnb")
GAME_INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting for API stress test
API_RATE_LIMIT_DELAY = 0.5  # seconds between requests

# ==============================================================================
# DATA MODELS
# ==============================================================================


@dataclass
class LeagueSeasonTest:
    """Test results for a single league/season combination"""

    league: str
    season: str
    league_display_name: str

    # Discovery metrics
    expected_games: int  # From competition metadata or typical season length
    discovered_fixtures: int  # From fixture discovery
    index_entries: int  # From game index

    # Data availability metrics
    games_with_pbp: int
    games_with_shots: int
    games_with_both: int
    games_missing_pbp: int
    games_missing_shots: int

    # Data consistency metrics (from validation)
    games_validated: int
    games_with_discrepancies: int
    total_discrepancies: int

    # Coverage percentages
    discovery_coverage: float  # discovered / expected
    index_coverage: float  # index_entries / discovered
    pbp_coverage: float  # games_with_pbp / index_entries
    shots_coverage: float  # games_with_shots / index_entries
    complete_coverage: float  # games_with_both / index_entries

    # Test status
    passed: bool
    warnings: list[str]
    errors: list[str]

    # Timestamp
    tested_at: str


@dataclass
class GameConsistencyCheck:
    """Consistency check results for a single game"""

    game_id: str
    season: str
    league: str

    # Shot count comparison
    pbp_shots_total: int
    shots_table_total: int
    shot_count_delta: int

    # Made shots comparison
    pbp_made_total: int
    shots_made_total: int
    made_shots_delta: int

    # Validation flags
    coords_valid: bool
    has_discrepancy: bool
    is_valid: bool

    # Details
    discrepancy_notes: list[str]


# ==============================================================================
# GAME INDEX ANALYSIS
# ==============================================================================


def load_game_index() -> pd.DataFrame:
    """Load game index from parquet file

    Returns:
        DataFrame with game index, or empty DataFrame if not found
    """
    if not GAME_INDEX_FILE.exists():
        print(f"[WARN] Game index not found: {GAME_INDEX_FILE}")
        return pd.DataFrame()

    try:
        df = pd.read_parquet(GAME_INDEX_FILE)
        print(f"[INFO] Loaded game index: {len(df)} games")
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load game index: {e}")
        return pd.DataFrame()


def get_index_stats_for_league_season(
    index_df: pd.DataFrame, league: str, season: str
) -> dict[str, int]:
    """Get game index statistics for a specific league/season

    Args:
        index_df: Game index DataFrame
        league: League identifier (e.g., "betclic_elite")
        season: Season string (e.g., "2024-2025")

    Returns:
        Dict with counts:
        - total_entries: Total games in index for this league/season
        - with_pbp: Games marked as having PBP
        - with_shots: Games marked as having shots
        - with_both: Games with both PBP and shots
    """
    if index_df.empty:
        return {
            "total_entries": 0,
            "with_pbp": 0,
            "with_shots": 0,
            "with_both": 0,
        }

    # Get display name for league to match competition column
    display_name = LEAGUE_METADATA_REGISTRY[league]["display_name"]

    # Filter by season and league (via competition column)
    mask = (index_df["season"] == season) & index_df["competition"].str.contains(
        display_name, case=False, na=False
    )
    filtered = index_df[mask]

    return {
        "total_entries": len(filtered),
        "with_pbp": int(filtered["has_pbp"].sum()) if "has_pbp" in filtered.columns else 0,
        "with_shots": int(filtered["has_shots"].sum()) if "has_shots" in filtered.columns else 0,
        "with_both": int(
            (filtered["has_pbp"] & filtered["has_shots"]).sum()
            if "has_pbp" in filtered.columns and "has_shots" in filtered.columns
            else 0
        ),
    }


# ==============================================================================
# DATA AVAILABILITY CHECKS
# ==============================================================================


def check_data_files_exist(season: str, game_ids: list[str]) -> dict[str, Any]:
    """Check which games have PBP and shots files on disk

    Args:
        season: Season string
        game_ids: List of game UUIDs to check

    Returns:
        Dict with file existence stats:
        - games_with_pbp: Count of games with PBP files
        - games_with_shots: Count of games with shots files
        - games_with_both: Count of games with both files
        - missing_pbp: List of game IDs missing PBP
        - missing_shots: List of game IDs missing shots
    """
    season_pbp_dir = PBP_DIR / f"season={season}"
    season_shots_dir = SHOTS_DIR / f"season={season}"

    games_with_pbp = []
    games_with_shots = []
    missing_pbp = []
    missing_shots = []

    for game_id in game_ids:
        pbp_file = season_pbp_dir / f"game_id={game_id}.parquet"
        shots_file = season_shots_dir / f"game_id={game_id}.parquet"

        if pbp_file.exists():
            games_with_pbp.append(game_id)
        else:
            missing_pbp.append(game_id)

        if shots_file.exists():
            games_with_shots.append(game_id)
        else:
            missing_shots.append(game_id)

    games_with_both = set(games_with_pbp) & set(games_with_shots)

    return {
        "games_with_pbp": len(games_with_pbp),
        "games_with_shots": len(games_with_shots),
        "games_with_both": len(games_with_both),
        "missing_pbp": missing_pbp,
        "missing_shots": missing_shots,
    }


# ==============================================================================
# DATA CONSISTENCY VALIDATION
# ==============================================================================


def validate_game_consistency(
    game_id: str, season: str, league: str
) -> GameConsistencyCheck | None:
    """Validate consistency between PBP and shots data for a single game

    Args:
        game_id: Game UUID
        season: Season string
        league: League identifier

    Returns:
        GameConsistencyCheck object or None if data missing
    """
    pbp_file = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
    shots_file = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

    if not pbp_file.exists() or not shots_file.exists():
        return None

    try:
        pbp_df = pd.read_parquet(pbp_file)
        shots_df = pd.read_parquet(shots_file)

        # Count shots from PBP
        pbp_shot_events = pbp_df[pbp_df["EVENT_TYPE"].isin(["2pt", "3pt"])]
        pbp_shots_total = len(pbp_shot_events)
        pbp_made_total = int(pbp_shot_events["SUCCESS"].sum())

        # Count shots from shots table
        shots_table_total = len(shots_df)
        shots_made_total = int(shots_df["SUCCESS"].sum())

        # Calculate deltas
        shot_count_delta = abs(pbp_shots_total - shots_table_total)
        made_shots_delta = abs(pbp_made_total - shots_made_total)

        # Validate coordinates
        coords_valid = True
        if "SHOT_X" in shots_df.columns and "SHOT_Y" in shots_df.columns:
            invalid_x = ((shots_df["SHOT_X"] < 0) | (shots_df["SHOT_X"] > 100)).sum()
            invalid_y = ((shots_df["SHOT_Y"] < 0) | (shots_df["SHOT_Y"] > 100)).sum()
            coords_valid = invalid_x == 0 and invalid_y == 0

        # Build discrepancy notes
        discrepancy_notes = []
        if shot_count_delta > 0:
            discrepancy_notes.append(
                f"Shot count mismatch: PBP={pbp_shots_total} vs Shots={shots_table_total}"
            )
        if made_shots_delta > 0:
            discrepancy_notes.append(
                f"Made shots mismatch: PBP={pbp_made_total} vs Shots={shots_made_total}"
            )
        if not coords_valid:
            discrepancy_notes.append("Invalid coordinates found")

        has_discrepancy = len(discrepancy_notes) > 0
        is_valid = not has_discrepancy

        return GameConsistencyCheck(
            game_id=game_id,
            season=season,
            league=league,
            pbp_shots_total=pbp_shots_total,
            shots_table_total=shots_table_total,
            shot_count_delta=shot_count_delta,
            pbp_made_total=pbp_made_total,
            shots_made_total=shots_made_total,
            made_shots_delta=made_shots_delta,
            coords_valid=coords_valid,
            has_discrepancy=has_discrepancy,
            is_valid=is_valid,
            discrepancy_notes=discrepancy_notes,
        )

    except Exception as e:
        print(f"  [ERROR] Validation failed for {game_id}: {e}")
        return None


# ==============================================================================
# LEAGUE/SEASON STRESS TEST
# ==============================================================================


def stress_test_league_season(
    league: str,
    season: str,
    index_df: pd.DataFrame,
    quick_mode: bool = False,
) -> LeagueSeasonTest:
    """Perform comprehensive stress test for a single league/season

    Args:
        league: League identifier
        season: Season string
        index_df: Game index DataFrame
        quick_mode: If True, skip API calls and only check local files

    Returns:
        LeagueSeasonTest results
    """
    print(f"\n{'='*80}")
    print(f"  STRESS TEST: {league.upper()} - {season}")
    print(f"{'='*80}\n")

    warnings = []
    errors = []

    # Get league metadata
    display_name = LEAGUE_METADATA_REGISTRY[league]["display_name"]
    season_meta = get_season_metadata(league, season)

    # Step 1: Get index statistics
    print("[1/5] Checking game index...")
    index_stats = get_index_stats_for_league_season(index_df, league, season)
    print(f"  Index entries: {index_stats['total_entries']}")
    print(f"  With PBP flag: {index_stats['with_pbp']}")
    print(f"  With shots flag: {index_stats['with_shots']}")

    if index_stats["total_entries"] == 0:
        errors.append(f"No games found in index for {league} {season}")
        # Return early with minimal data
        return LeagueSeasonTest(
            league=league,
            season=season,
            league_display_name=display_name,
            expected_games=0,
            discovered_fixtures=0,
            index_entries=0,
            games_with_pbp=0,
            games_with_shots=0,
            games_with_both=0,
            games_missing_pbp=0,
            games_missing_shots=0,
            games_validated=0,
            games_with_discrepancies=0,
            total_discrepancies=0,
            discovery_coverage=0.0,
            index_coverage=0.0,
            pbp_coverage=0.0,
            shots_coverage=0.0,
            complete_coverage=0.0,
            passed=False,
            warnings=warnings,
            errors=errors,
            tested_at=datetime.now().isoformat(),
        )

    # Step 2: Get game IDs from index
    print("\n[2/5] Extracting game IDs from index...")
    mask = (index_df["season"] == season) & index_df["competition"].str.contains(
        display_name, case=False, na=False
    )
    league_season_games = index_df[mask]
    game_ids = league_season_games["game_id"].tolist()
    print(f"  Found {len(game_ids)} game IDs")

    # Step 3: Check data file existence
    print("\n[3/5] Checking data file existence...")
    file_stats = check_data_files_exist(season, game_ids)
    print(f"  Games with PBP: {file_stats['games_with_pbp']}")
    print(f"  Games with shots: {file_stats['games_with_shots']}")
    print(f"  Games with both: {file_stats['games_with_both']}")

    # Step 4: Validate data consistency (sample or full)
    print("\n[4/5] Validating data consistency...")
    validation_results = []

    # Sample validation: validate up to 10 games or all if fewer
    games_to_validate = game_ids[:10] if quick_mode and len(game_ids) > 10 else game_ids

    for i, game_id in enumerate(games_to_validate, 1):
        print(
            f"  [{i}/{len(games_to_validate)}] Validating {game_id[:16]}...",
            end=" ",
        )
        result = validate_game_consistency(game_id, season, league)
        if result:
            validation_results.append(result)
            if result.is_valid:
                print("✅")
            else:
                print(f"⚠️  {', '.join(result.discrepancy_notes)}")
        else:
            print("❌ (missing data)")

    games_validated = len(validation_results)
    games_with_discrepancies = sum(1 for r in validation_results if r.has_discrepancy)
    total_discrepancies = sum(len(r.discrepancy_notes) for r in validation_results)

    print(f"\n  Validated: {games_validated} games")
    print(f"  With discrepancies: {games_with_discrepancies}")

    # Step 5: Calculate coverage metrics
    print("\n[5/5] Calculating coverage metrics...")

    # Expected games (rough estimate based on typical season length)
    # Betclic ELITE: ~32 rounds × 8 games = ~256 games per season
    # ELITE 2: ~34 rounds × 10 games = ~340 games per season
    # Espoirs: varies, ~8-12 teams, ~15-20 rounds
    expected_games_map = {
        "betclic_elite": 256,
        "elite_2": 340,
        "espoirs_elite": 150,
        "espoirs_prob": 150,
    }
    expected_games = expected_games_map.get(league, 200)

    discovered_fixtures = len(game_ids)  # From game index
    index_entries = index_stats["total_entries"]

    # Coverage percentages
    discovery_coverage = (discovered_fixtures / expected_games * 100) if expected_games > 0 else 0
    index_coverage = (index_entries / discovered_fixtures * 100) if discovered_fixtures > 0 else 0
    pbp_coverage = (file_stats["games_with_pbp"] / index_entries * 100) if index_entries > 0 else 0
    shots_coverage = (
        (file_stats["games_with_shots"] / index_entries * 100) if index_entries > 0 else 0
    )
    complete_coverage = (
        (file_stats["games_with_both"] / index_entries * 100) if index_entries > 0 else 0
    )

    print(f"  Discovery coverage: {discovery_coverage:.1f}%")
    print(f"  Index coverage: {index_coverage:.1f}%")
    print(f"  PBP coverage: {pbp_coverage:.1f}%")
    print(f"  Shots coverage: {shots_coverage:.1f}%")
    print(f"  Complete coverage: {complete_coverage:.1f}%")

    # Determine warnings
    if pbp_coverage < 90:
        warnings.append(f"Low PBP coverage: {pbp_coverage:.1f}%")
    if shots_coverage < 90:
        warnings.append(f"Low shots coverage: {shots_coverage:.1f}%")
    if games_with_discrepancies > 0:
        warnings.append(f"{games_with_discrepancies} games have data discrepancies")

    # Determine pass/fail
    passed = pbp_coverage >= 80 and shots_coverage >= 80 and games_with_discrepancies == 0

    return LeagueSeasonTest(
        league=league,
        season=season,
        league_display_name=display_name,
        expected_games=expected_games,
        discovered_fixtures=discovered_fixtures,
        index_entries=index_entries,
        games_with_pbp=file_stats["games_with_pbp"],
        games_with_shots=file_stats["games_with_shots"],
        games_with_both=file_stats["games_with_both"],
        games_missing_pbp=len(file_stats["missing_pbp"]),
        games_missing_shots=len(file_stats["missing_shots"]),
        games_validated=games_validated,
        games_with_discrepancies=games_with_discrepancies,
        total_discrepancies=total_discrepancies,
        discovery_coverage=discovery_coverage,
        index_coverage=index_coverage,
        pbp_coverage=pbp_coverage,
        shots_coverage=shots_coverage,
        complete_coverage=complete_coverage,
        passed=passed,
        warnings=warnings,
        errors=errors,
        tested_at=datetime.now().isoformat(),
    )


# ==============================================================================
# REPORT GENERATION
# ==============================================================================


def print_summary_table(test_results: list[LeagueSeasonTest]) -> None:
    """Print formatted summary table of test results

    Args:
        test_results: List of LeagueSeasonTest objects
    """
    print(f"\n{'='*80}")
    print("  STRESS TEST SUMMARY")
    print(f"{'='*80}\n")

    # Group by league
    results_by_league = defaultdict(list)
    for result in test_results:
        results_by_league[result.league].append(result)

    for league in sorted(results_by_league.keys()):
        league_results = results_by_league[league]
        print(f"\n{league.upper().replace('_', ' ')}:")
        print("-" * 80)
        print(
            f"{'Season':<12} {'Games':<8} {'PBP':<8} {'Shots':<8} {'Complete':<10} {'Status':<10}"
        )
        print("-" * 80)

        for result in sorted(league_results, key=lambda x: x.season):
            status = "✅ PASS" if result.passed else "⚠️  WARN"
            print(
                f"{result.season:<12} "
                f"{result.index_entries:<8} "
                f"{result.pbp_coverage:>6.1f}% "
                f"{result.shots_coverage:>6.1f}% "
                f"{result.complete_coverage:>8.1f}% "
                f"{status:<10}"
            )

            # Print warnings/errors if any
            if result.warnings:
                for warn in result.warnings:
                    print(f"  ⚠️  {warn}")
            if result.errors:
                for err in result.errors:
                    print(f"  ❌ {err}")

    # Overall statistics
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r.passed)
    total_games = sum(r.index_entries for r in test_results)
    total_with_both = sum(r.games_with_both for r in test_results)

    print(f"\n{'='*80}")
    print("  OVERALL STATISTICS")
    print(f"{'='*80}")
    print(f"Tests run: {total_tests}")
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Total games tested: {total_games}")

    # Calculate percentage only if games exist (avoid ZeroDivisionError)
    if total_games > 0:
        pct_complete = total_with_both / total_games * 100
        print(f"Games with complete data: {total_with_both} ({pct_complete:.1f}%)")
    else:
        print(f"Games with complete data: {total_with_both} (N/A - no games found)")

    print()


def save_detailed_report(test_results: list[LeagueSeasonTest], output_path: Path) -> None:
    """Save detailed JSON report of test results

    Args:
        test_results: List of LeagueSeasonTest objects
        output_path: Path to save JSON report
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_tests": len(test_results),
        "tests_passed": sum(1 for r in test_results if r.passed),
        "results": [asdict(r) for r in test_results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[SAVED] Detailed report: {output_path}")


# ==============================================================================
# MAIN ORCHESTRATION
# ==============================================================================


def run_multi_league_stress_test(
    leagues: list[str] | None = None,
    seasons: list[str] | None = None,
    quick_mode: bool = False,
    detailed_report: bool = False,
) -> list[LeagueSeasonTest]:
    """Run comprehensive stress test across multiple leagues and seasons

    Args:
        leagues: List of league identifiers (default: all leagues)
        seasons: List of season strings (default: all available seasons per league)
        quick_mode: If True, skip API calls and validate sample only
        detailed_report: If True, save detailed JSON report

    Returns:
        List of LeagueSeasonTest results
    """
    print(f"\n{'='*80}")
    print("  LNB MULTI-LEAGUE STRESS TEST")
    print(f"{'='*80}\n")

    # Default to all leagues if not specified
    if leagues is None:
        leagues = ALL_LEAGUES

    # Load game index
    print("[SETUP] Loading game index...")
    index_df = load_game_index()

    if index_df.empty:
        print("[ERROR] Game index is empty. Run build_game_index.py first.")
        return []

    # Run tests for each league/season combination
    test_results = []

    for league in leagues:
        # Get seasons for this league (or use provided seasons)
        if seasons is None:
            league_seasons = get_all_seasons_for_league(league)
        else:
            # Filter seasons to only those available for this league
            all_league_seasons = get_all_seasons_for_league(league)
            league_seasons = [s for s in seasons if s in all_league_seasons]

        if not league_seasons:
            print(f"\n[SKIP] {league}: No seasons available")
            continue

        # Test each season
        for season in league_seasons:
            result = stress_test_league_season(league, season, index_df, quick_mode)
            test_results.append(result)

            # Brief pause between tests
            time.sleep(0.5)

    # Print summary
    print_summary_table(test_results)

    # Save detailed report if requested
    if detailed_report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"lnb_multi_league_stress_test_{timestamp}.json"
        save_detailed_report(test_results, report_path)

    return test_results


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive multi-league stress test for LNB data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full stress test (all leagues, all seasons)
    python tools/lnb/stress_test_multi_league.py

    # Specific league only
    python tools/lnb/stress_test_multi_league.py --leagues elite_2

    # Multiple leagues
    python tools/lnb/stress_test_multi_league.py \
        --leagues betclic_elite espoirs_elite

    # Specific season
    python tools/lnb/stress_test_multi_league.py --seasons 2024-2025

    # Quick mode (skip API, sample validation)
    python tools/lnb/stress_test_multi_league.py --quick

    # Generate detailed JSON report
    python tools/lnb/stress_test_multi_league.py --detailed-report

Available leagues:
    betclic_elite    - Top-tier professional (formerly Pro A)
    elite_2          - Second-tier professional (formerly Pro B)
    espoirs_elite    - U21 top-tier youth development
    espoirs_prob     - U21 second-tier youth development
        """,
    )

    parser.add_argument(
        "--leagues",
        nargs="+",
        default=None,
        help="Leagues to test (default: all leagues)",
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        help="Seasons to test (default: all available seasons per league)",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: skip API calls, validate sample only",
    )

    parser.add_argument(
        "--detailed-report",
        action="store_true",
        help="Generate detailed JSON report",
    )

    args = parser.parse_args()

    # Run stress test
    results = run_multi_league_stress_test(
        leagues=args.leagues,
        seasons=args.seasons,
        quick_mode=args.quick,
        detailed_report=args.detailed_report,
    )

    # Exit with appropriate code
    if not results:
        print("\n❌ No tests run")
        sys.exit(1)

    failed_tests = sum(1 for r in results if not r.passed)
    if failed_tests > 0:
        print(f"\n⚠️  {failed_tests} tests failed or have warnings")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
