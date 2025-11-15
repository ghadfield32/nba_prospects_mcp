#!/usr/bin/env python3
"""Test historical coverage of LNB endpoints

This script tests how far back each LNB endpoint goes by:
1. Testing play-by-play and shots across multiple seasons
2. Testing schedule availability for past seasons
3. Testing team/player data availability
4. Documenting what seasons have complete data

Usage:
    uv run python tools/lnb/test_historical_coverage.py

Output:
    - Console report of data availability by season
    - CSV: tools/lnb/historical_coverage_report.csv
    - JSON: tools/lnb/historical_coverage_report.json
"""

from __future__ import annotations

import io
import json
import sys
import time
from dataclasses import asdict, dataclass
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

from src.cbb_data.fetchers.lnb import (
    fetch_lnb_play_by_play,
    fetch_lnb_schedule,
    fetch_lnb_shots,
)

# ==============================================================================
# CONFIG
# ==============================================================================

# Seasons to test (YYYY-YYYY format)
SEASONS_TO_TEST = [
    "2024-2025",  # Current season
    "2023-2024",
    "2022-2023",
    "2021-2022",
    "2020-2021",
    "2019-2020",
    "2018-2019",
    "2017-2018",
    "2016-2017",
    "2015-2016",
]

OUTPUT_DIR = Path("tools/lnb")

# ==============================================================================
# DATA MODELS
# ==============================================================================


@dataclass
class SeasonCoverage:
    """Coverage data for a single season"""

    season: str

    # Schedule
    schedule_available: bool = False
    schedule_games_found: int = 0
    schedule_error: str | None = None

    # Sample game UUIDs for testing
    sample_game_uuids: list[str] = None

    # Play-by-play
    pbp_tested: bool = False
    pbp_available: bool = False
    pbp_games_tested: int = 0
    pbp_games_success: int = 0
    pbp_avg_events: float = 0.0
    pbp_error: str | None = None

    # Shots
    shots_tested: bool = False
    shots_available: bool = False
    shots_games_tested: int = 0
    shots_games_success: int = 0
    shots_avg_shots: float = 0.0
    shots_error: str | None = None

    def __post_init__(self):
        if self.sample_game_uuids is None:
            self.sample_game_uuids = []


# ==============================================================================
# TESTING FUNCTIONS
# ==============================================================================


def test_schedule_coverage(season: str) -> dict[str, Any]:
    """Test if schedule is available for a season"""
    print(f"\n[SCHEDULE] Testing {season}...")

    result = {
        "available": False,
        "games_found": 0,
        "sample_uuids": [],
        "error": None,
    }

    try:
        schedule_df = fetch_lnb_schedule(season=season)

        if not schedule_df.empty:
            result["available"] = True
            result["games_found"] = len(schedule_df)

            # Extract sample game UUIDs (up to 5)
            if "GAME_ID" in schedule_df.columns:
                sample_uuids = schedule_df["GAME_ID"].dropna().unique()[:5].tolist()
                result["sample_uuids"] = [str(uuid) for uuid in sample_uuids]

            print(f"  ✅ Schedule available: {result['games_found']} games")
            if result["sample_uuids"]:
                print(f"  Sample UUIDs: {result['sample_uuids'][:2]}...")
        else:
            result["error"] = "Empty schedule DataFrame"
            print("  ❌ Schedule empty")

    except Exception as e:
        result["error"] = str(e)[:200]
        print(f"  ❌ Schedule error: {str(e)[:100]}")

    return result


def test_pbp_coverage(season: str, game_uuids: list[str], max_test: int = 3) -> dict[str, Any]:
    """Test play-by-play availability for sample games"""
    print(f"\n[PBP] Testing {season}...")

    result = {
        "tested": False,
        "available": False,
        "games_tested": 0,
        "games_success": 0,
        "avg_events": 0.0,
        "error": None,
    }

    if not game_uuids:
        result["error"] = "No game UUIDs to test"
        print("  ⚠️  No game UUIDs available for testing")
        return result

    result["tested"] = True
    test_uuids = game_uuids[:max_test]
    result["games_tested"] = len(test_uuids)

    total_events = 0
    success_count = 0

    for game_id in test_uuids:
        try:
            pbp_df = fetch_lnb_play_by_play(game_id)
            if not pbp_df.empty:
                success_count += 1
                total_events += len(pbp_df)
                print(f"  ✅ Game {game_id[:8]}...: {len(pbp_df)} events")
            else:
                print(f"  ❌ Game {game_id[:8]}...: Empty")
        except Exception as e:
            print(f"  ❌ Game {game_id[:8]}...: {str(e)[:50]}")
            if not result["error"]:
                result["error"] = str(e)[:200]

        time.sleep(0.5)  # Rate limiting

    result["games_success"] = success_count
    result["available"] = success_count > 0

    if success_count > 0:
        result["avg_events"] = total_events / success_count
        print(
            f"  Summary: {success_count}/{result['games_tested']} games, avg {result['avg_events']:.0f} events/game"
        )

    return result


def test_shots_coverage(season: str, game_uuids: list[str], max_test: int = 3) -> dict[str, Any]:
    """Test shot chart availability for sample games"""
    print(f"\n[SHOTS] Testing {season}...")

    result = {
        "tested": False,
        "available": False,
        "games_tested": 0,
        "games_success": 0,
        "avg_shots": 0.0,
        "error": None,
    }

    if not game_uuids:
        result["error"] = "No game UUIDs to test"
        print("  ⚠️  No game UUIDs available for testing")
        return result

    result["tested"] = True
    test_uuids = game_uuids[:max_test]
    result["games_tested"] = len(test_uuids)

    total_shots = 0
    success_count = 0

    for game_id in test_uuids:
        try:
            shots_df = fetch_lnb_shots(game_id)
            if not shots_df.empty:
                success_count += 1
                total_shots += len(shots_df)
                print(f"  ✅ Game {game_id[:8]}...: {len(shots_df)} shots")
            else:
                print(f"  ❌ Game {game_id[:8]}...: Empty")
        except Exception as e:
            print(f"  ❌ Game {game_id[:8]}...: {str(e)[:50]}")
            if not result["error"]:
                result["error"] = str(e)[:200]

        time.sleep(0.5)  # Rate limiting

    result["games_success"] = success_count
    result["available"] = success_count > 0

    if success_count > 0:
        result["avg_shots"] = total_shots / success_count
        print(
            f"  Summary: {success_count}/{result['games_tested']} games, avg {result['avg_shots']:.0f} shots/game"
        )

    return result


def test_season_coverage(season: str) -> SeasonCoverage:
    """Test all endpoints for a single season"""
    print(f"\n{'='*80}")
    print(f"  TESTING SEASON: {season}")
    print(f"{'='*80}")

    coverage = SeasonCoverage(season=season)

    # Test schedule
    schedule_result = test_schedule_coverage(season)
    coverage.schedule_available = schedule_result["available"]
    coverage.schedule_games_found = schedule_result["games_found"]
    coverage.schedule_error = schedule_result["error"]
    coverage.sample_game_uuids = schedule_result["sample_uuids"]

    # Test PBP (if we have game UUIDs)
    if coverage.sample_game_uuids:
        pbp_result = test_pbp_coverage(season, coverage.sample_game_uuids)
        coverage.pbp_tested = pbp_result["tested"]
        coverage.pbp_available = pbp_result["available"]
        coverage.pbp_games_tested = pbp_result["games_tested"]
        coverage.pbp_games_success = pbp_result["games_success"]
        coverage.pbp_avg_events = pbp_result["avg_events"]
        coverage.pbp_error = pbp_result["error"]

    # Test Shots (if we have game UUIDs)
    if coverage.sample_game_uuids:
        shots_result = test_shots_coverage(season, coverage.sample_game_uuids)
        coverage.shots_tested = shots_result["tested"]
        coverage.shots_available = shots_result["available"]
        coverage.shots_games_tested = shots_result["games_tested"]
        coverage.shots_games_success = shots_result["games_success"]
        coverage.shots_avg_shots = shots_result["avg_shots"]
        coverage.shots_error = shots_result["error"]

    return coverage


# ==============================================================================
# REPORTING
# ==============================================================================


def print_coverage_report(results: list[SeasonCoverage]) -> None:
    """Print comprehensive coverage report"""
    print(f"\n\n{'='*80}")
    print("  LNB HISTORICAL COVERAGE REPORT")
    print(f"{'='*80}\n")

    # Summary table
    print("SEASON COVERAGE SUMMARY")
    print("-" * 80)
    print(f"{'Season':<15} {'Schedule':<12} {'PBP':<12} {'Shots':<12} {'Notes':<30}")
    print("-" * 80)

    for result in results:
        schedule_status = (
            f"✅ {result.schedule_games_found} games" if result.schedule_available else "❌ N/A"
        )
        pbp_status = (
            f"✅ {result.pbp_games_success}/{result.pbp_games_tested}"
            if result.pbp_available
            else "❌ N/A"
            if result.pbp_tested
            else "⚠️  Not tested"
        )
        shots_status = (
            f"✅ {result.shots_games_success}/{result.shots_games_tested}"
            if result.shots_available
            else "❌ N/A"
            if result.shots_tested
            else "⚠️  Not tested"
        )

        notes = ""
        if result.schedule_error:
            notes = result.schedule_error[:25]
        elif result.pbp_error:
            notes = result.pbp_error[:25]
        elif result.shots_error:
            notes = result.shots_error[:25]

        print(
            f"{result.season:<15} {schedule_status:<12} {pbp_status:<12} {shots_status:<12} {notes:<30}"
        )

    # Detailed stats
    print(f"\n{'='*80}")
    print("DETAILED STATISTICS")
    print(f"{'='*80}\n")

    # Schedule stats
    schedule_available = [r for r in results if r.schedule_available]
    if schedule_available:
        print("SCHEDULE AVAILABILITY:")
        print(f"  Seasons with schedule: {len(schedule_available)}/{len(results)}")
        print(f"  Total games found: {sum(r.schedule_games_found for r in schedule_available):,}")
        print(
            f"  Avg games per season: {sum(r.schedule_games_found for r in schedule_available) / len(schedule_available):.0f}"
        )
        print(f"  Date range: {schedule_available[-1].season} to {schedule_available[0].season}")

    # PBP stats
    pbp_available = [r for r in results if r.pbp_available]
    if pbp_available:
        print("\nPLAY-BY-PLAY AVAILABILITY:")
        print(f"  Seasons with PBP: {len(pbp_available)}/{len(results)}")
        print(f"  Games tested: {sum(r.pbp_games_tested for r in pbp_available)}")
        print(f"  Games with data: {sum(r.pbp_games_success for r in pbp_available)}")
        print(
            f"  Avg events per game: {sum(r.pbp_avg_events for r in pbp_available) / len(pbp_available):.0f}"
        )
        print(f"  Date range: {pbp_available[-1].season} to {pbp_available[0].season}")

    # Shots stats
    shots_available = [r for r in results if r.shots_available]
    if shots_available:
        print("\nSHOT CHART AVAILABILITY:")
        print(f"  Seasons with shots: {len(shots_available)}/{len(results)}")
        print(f"  Games tested: {sum(r.shots_games_tested for r in shots_available)}")
        print(f"  Games with data: {sum(r.shots_games_success for r in shots_available)}")
        print(
            f"  Avg shots per game: {sum(r.shots_avg_shots for r in shots_available) / len(shots_available):.0f}"
        )
        print(f"  Date range: {shots_available[-1].season} to {shots_available[0].season}")

    print()


def save_coverage_report(results: list[SeasonCoverage]) -> None:
    """Save coverage report to CSV and JSON"""
    # Convert to DataFrame
    df = pd.DataFrame([asdict(r) for r in results])

    # Save CSV
    csv_path = OUTPUT_DIR / "historical_coverage_report.csv"
    df.to_csv(csv_path, index=False)
    print(f"[SAVED] CSV report: {csv_path}")

    # Save JSON
    json_path = OUTPUT_DIR / "historical_coverage_report.json"
    report = {
        "generated_at": datetime.now().isoformat(),
        "seasons_tested": len(results),
        "results": [asdict(r) for r in results],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] JSON report: {json_path}")


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    print("=" * 80)
    print("  LNB HISTORICAL COVERAGE TEST")
    print("=" * 80)
    print(f"\nTesting {len(SEASONS_TO_TEST)} seasons...")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results: list[SeasonCoverage] = []

    for season in SEASONS_TO_TEST:
        coverage = test_season_coverage(season)
        results.append(coverage)
        time.sleep(1)  # Pause between seasons

    # Print report
    print_coverage_report(results)

    # Save report
    save_coverage_report(results)

    print(f"\n{'='*80}")
    print("  TEST COMPLETE")
    print(f"{'='*80}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    main()
