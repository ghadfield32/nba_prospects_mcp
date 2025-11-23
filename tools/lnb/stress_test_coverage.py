#!/usr/bin/env python3
"""LNB Data Coverage & Stress Test

Comprehensive coverage reporting and stress testing for LNB data pipeline.

**Purpose**:
- Quantify data coverage per season (details/pbp/shots/normalized tables)
- Stress test API endpoints with concurrent requests
- Validate memory usage and performance
- Generate actionable coverage reports

**Usage**:
    # Coverage report for all seasons
    uv run python tools/lnb/stress_test_coverage.py --report

    # Stress test with 20 concurrent requests
    uv run python tools/lnb/stress_test_coverage.py --stress --concurrent 20

    # Full suite (coverage + stress + memory)
    uv run python tools/lnb/stress_test_coverage.py --full

**Output**:
- Console: Summary tables with coverage percentages
- File: Detailed reports in tools/lnb/reports/

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# ==============================================================================
# CONFIG
# ==============================================================================

FIXTURE_UUID_FILE = Path(__file__).parent / "fixture_uuids_by_season.json"
REPORTS_DIR = Path(__file__).parent / "reports"

# Stress test configuration
DEFAULT_CONCURRENT_REQUESTS = 10
MAX_CONCURRENT_REQUESTS = 50
REQUEST_TIMEOUT = 10.0

# ==============================================================================
# COVERAGE REPORTING
# ==============================================================================


def load_fixture_uuids() -> dict[str, list[str]]:
    """Load fixture UUIDs from mapping file

    Returns:
        Dict mapping season -> list of UUIDs
    """
    if not FIXTURE_UUID_FILE.exists():
        print(f"[ERROR] Fixture UUID file not found: {FIXTURE_UUID_FILE}")
        return {}

    with open(FIXTURE_UUID_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Handle nested structure from discover script
    mappings = data.get("mappings", {})
    if "mappings" in mappings:  # Nested structure
        mappings = mappings["mappings"]

    return mappings


def check_uuid_coverage(season: str, uuids: list[str]) -> dict[str, Any]:
    """Check data coverage for a list of UUIDs

    Args:
        season: Season string (e.g., "2023-2024")
        uuids: List of fixture UUIDs

    Returns:
        Dict with coverage statistics:
        - total_games: Total UUIDs
        - have_pbp: Count with PBP data
        - have_shots: Count with shot data
        - coverage_pbp: Percentage with PBP
        - coverage_shots: Percentage with shots
        - missing_pbp: List of UUIDs missing PBP
        - missing_shots: List of UUIDs missing shots
    """
    print(f"\n[COVERAGE] Checking {season} ({len(uuids)} games)...")

    have_pbp = 0
    have_shots = 0
    missing_pbp = []
    missing_shots = []

    for i, uuid in enumerate(uuids, 1):
        print(f"  [{i}/{len(uuids)}] {uuid[:18]}...", end=" ")

        # Check PBP
        try:
            pbp_df = fetch_lnb_play_by_play(uuid)
            if not pbp_df.empty:
                have_pbp += 1
                print(f"PBP:✅({len(pbp_df)})", end=" ")
            else:
                missing_pbp.append(uuid)
                print("PBP:❌", end=" ")
        except Exception as e:
            missing_pbp.append(uuid)
            print(f"PBP:❌({str(e)[:20]})", end=" ")

        # Check shots
        try:
            shots_df = fetch_lnb_game_shots(uuid)
            if not shots_df.empty:
                have_shots += 1
                print(f"Shots:✅({len(shots_df)})")
            else:
                missing_shots.append(uuid)
                print("Shots:❌")
        except Exception as e:
            missing_shots.append(uuid)
            print(f"Shots:❌({str(e)[:20]})")

        # Rate limiting (500ms between requests)
        time.sleep(0.5)

    return {
        "season": season,
        "total_games": len(uuids),
        "have_pbp": have_pbp,
        "have_shots": have_shots,
        "coverage_pbp": (have_pbp / len(uuids) * 100) if uuids else 0,
        "coverage_shots": (have_shots / len(uuids) * 100) if uuids else 0,
        "missing_pbp": missing_pbp,
        "missing_shots": missing_shots,
    }


def check_dataset_coverage(season: str, uuids: list[str]) -> dict[str, Any]:
    """Check normalized dataset coverage for a list of UUIDs

    Validates that normalized tables exist and contain expected data:
    - player_game: Player box scores aggregated from PBP
    - team_game: Team box scores aggregated from PBP
    - shot_events: Shots in standardized format

    Args:
        season: Season string (e.g., "2023-2024")
        uuids: List of fixture UUIDs

    Returns:
        Dict with dataset coverage statistics and anomalies
    """
    import pandas as pd

    print(f"\n[DATASETS] Checking {season} normalized tables ({len(uuids)} games)...")

    # Paths to normalized data
    normalized_dir = Path("data/normalized/lnb")
    player_game_dir = normalized_dir / "player_game"
    team_game_dir = normalized_dir / "team_game"
    shot_events_dir = normalized_dir / "shot_events"

    have_player = 0
    have_team = 0
    have_shots_normalized = 0
    missing_player = []
    missing_team = []
    missing_shots_normalized = []

    # Anomaly tracking
    anomalies = {
        "zero_players": [],  # Games with no player records
        "zero_teams": [],  # Games with no team records (should be 2)
        "team_count_mismatch": [],  # Games without exactly 2 teams
        "negative_stats": [],  # Games with negative stats (impossible)
        "missing_required_fields": [],  # Games missing required columns
    }

    for i, uuid in enumerate(uuids, 1):
        print(f"  [{i}/{len(uuids)}] {uuid[:18]}...", end=" ")

        # Check player_game table
        try:
            season_path = player_game_dir / f"season={season}"
            game_files = list(season_path.glob(f"game_id={uuid}.parquet"))

            if game_files and game_files[0].exists():
                df = pd.read_parquet(game_files[0])
                if not df.empty:
                    have_player += 1
                    print(f"Players:✅({len(df)})", end=" ")

                    # Anomaly checks
                    if len(df) == 0:
                        anomalies["zero_players"].append(uuid)

                    # Check for negative stats (impossible in basketball)
                    numeric_cols = df.select_dtypes(include=["number"]).columns
                    if (df[numeric_cols] < 0).any().any():
                        anomalies["negative_stats"].append(uuid)

                    # Check required fields
                    required_fields = ["player_id", "team_id", "game_id", "pts", "reb", "ast"]
                    missing_fields = [f for f in required_fields if f not in df.columns]
                    if missing_fields:
                        anomalies["missing_required_fields"].append(
                            (uuid, "player", missing_fields)
                        )
                else:
                    missing_player.append(uuid)
                    anomalies["zero_players"].append(uuid)
                    print("Players:⚠️(0)", end=" ")
            else:
                missing_player.append(uuid)
                print("Players:❌", end=" ")
        except Exception as e:
            missing_player.append(uuid)
            print(f"Players:❌({str(e)[:15]})", end=" ")

        # Check team_game table
        try:
            season_path = team_game_dir / f"season={season}"
            game_files = list(season_path.glob(f"game_id={uuid}.parquet"))

            if game_files and game_files[0].exists():
                df = pd.read_parquet(game_files[0])
                if not df.empty:
                    have_team += 1
                    print(f"Teams:✅({len(df)})", end=" ")

                    # Anomaly checks
                    if len(df) == 0:
                        anomalies["zero_teams"].append(uuid)
                    elif len(df) != 2:
                        anomalies["team_count_mismatch"].append((uuid, len(df)))

                    # Check required fields
                    required_fields = ["team_id", "game_id", "pts", "reb", "ast", "fg_pct"]
                    missing_fields = [f for f in required_fields if f not in df.columns]
                    if missing_fields:
                        anomalies["missing_required_fields"].append((uuid, "team", missing_fields))
                else:
                    missing_team.append(uuid)
                    anomalies["zero_teams"].append(uuid)
                    print("Teams:⚠️(0)", end=" ")
            else:
                missing_team.append(uuid)
                print("Teams:❌", end=" ")
        except Exception as e:
            missing_team.append(uuid)
            print(f"Teams:❌({str(e)[:15]})", end=" ")

        # Check shot_events table
        try:
            season_path = shot_events_dir / f"season={season}"
            game_files = list(season_path.glob(f"game_id={uuid}.parquet"))

            if game_files and game_files[0].exists():
                df = pd.read_parquet(game_files[0])
                if not df.empty:
                    have_shots_normalized += 1
                    print(f"Shots:✅({len(df)})")
                else:
                    missing_shots_normalized.append(uuid)
                    print("Shots:⚠️(0)")
            else:
                missing_shots_normalized.append(uuid)
                print("Shots:❌")
        except Exception as e:
            missing_shots_normalized.append(uuid)
            print(f"Shots:❌({str(e)[:15]})")

    return {
        "season": season,
        "total_games": len(uuids),
        "have_player": have_player,
        "have_team": have_team,
        "have_shots_normalized": have_shots_normalized,
        "coverage_player": (have_player / len(uuids) * 100) if uuids else 0,
        "coverage_team": (have_team / len(uuids) * 100) if uuids else 0,
        "coverage_shots_normalized": (have_shots_normalized / len(uuids) * 100) if uuids else 0,
        "missing_player": missing_player,
        "missing_team": missing_team,
        "missing_shots_normalized": missing_shots_normalized,
        "anomalies": anomalies,
    }


def generate_dataset_coverage_report(output_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    """Generate dataset-level coverage report (normalized tables)

    Args:
        output_dir: Directory to save report

    Returns:
        Dict with overall dataset coverage statistics
    """
    print("\n" + "=" * 80)
    print("LNB DATASET COVERAGE REPORT (Normalized Tables)")
    print("=" * 80)

    # Load UUID mappings
    mappings = load_fixture_uuids()

    if not mappings:
        print("[ERROR] No fixture UUIDs found")
        return {}

    # Check dataset coverage for each season
    all_dataset_coverage = {}

    for season, uuids in sorted(mappings.items()):
        if season == "metadata":  # Skip metadata
            continue

        dataset_cov = check_dataset_coverage(season, uuids)
        all_dataset_coverage[season] = dataset_cov

    # Print summary table
    print("\n" + "=" * 80)
    print("DATASET COVERAGE SUMMARY")
    print("=" * 80 + "\n")

    print(
        f"{'Season':<15s} {'Total':>7s} {'Players':>8s} {'Teams':>7s} {'Shots':>7s} {'Player %':>9s} {'Team %':>8s}"
    )
    print("-" * 90)

    total_games = 0
    total_player = 0
    total_team = 0
    total_shots = 0

    for season, cov in sorted(all_dataset_coverage.items()):
        print(
            f"{season:<15s} "
            f"{cov['total_games']:>7d} "
            f"{cov['have_player']:>8d} "
            f"{cov['have_team']:>7d} "
            f"{cov['have_shots_normalized']:>7d} "
            f"{cov['coverage_player']:>8.1f}% "
            f"{cov['coverage_team']:>7.1f}%"
        )

        total_games += cov["total_games"]
        total_player += cov["have_player"]
        total_team += cov["have_team"]
        total_shots += cov["have_shots_normalized"]

    print("-" * 90)
    print(
        f"{'TOTAL':<15s} "
        f"{total_games:>7d} "
        f"{total_player:>8d} "
        f"{total_team:>7d} "
        f"{total_shots:>7d} "
        f"{(total_player / total_games * 100) if total_games > 0 else 0:>8.1f}% "
        f"{(total_team / total_games * 100) if total_games > 0 else 0:>7.1f}%"
    )

    # Print anomalies if any
    print("\n" + "=" * 80)
    print("ANOMALY DETECTION")
    print("=" * 80 + "\n")

    total_anomalies = 0
    for season, cov in sorted(all_dataset_coverage.items()):
        anomalies = cov.get("anomalies", {})
        season_anomalies = sum(len(v) if isinstance(v, list) else 0 for v in anomalies.values())

        if season_anomalies > 0:
            print(f"\n[{season}] {season_anomalies} anomalies detected:")
            for anomaly_type, items in anomalies.items():
                if items:
                    print(f"  - {anomaly_type}: {len(items)} games")
                    if anomaly_type == "missing_required_fields":
                        for uuid, table, fields in items[:3]:  # Show first 3
                            print(f"      {uuid[:35]} ({table}): {fields}")
                    else:
                        for item in items[:3]:  # Show first 3
                            if isinstance(item, tuple):
                                print(f"      {item}")
                            else:
                                print(f"      {item[:35]}")
            total_anomalies += season_anomalies

    if total_anomalies == 0:
        print("✅ No anomalies detected - all datasets look healthy!")

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"dataset_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total_games": total_games,
                "total_player": total_player,
                "total_team": total_team,
                "total_shots": total_shots,
                "by_season": all_dataset_coverage,
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\n[SAVED] {report_file}")

    return {
        "total_games": total_games,
        "total_player": total_player,
        "total_team": total_team,
        "total_shots": total_shots,
        "by_season": all_dataset_coverage,
    }


def generate_coverage_report(output_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    """Generate comprehensive coverage report for all seasons

    Args:
        output_dir: Directory to save report

    Returns:
        Dict with overall coverage statistics
    """
    print("\n" + "=" * 80)
    print("LNB DATA COVERAGE REPORT (Raw API Data)")
    print("=" * 80)

    # Load UUID mappings
    mappings = load_fixture_uuids()

    if not mappings:
        print("[ERROR] No fixture UUIDs found")
        return {}

    # Check coverage for each season
    all_coverage = {}

    for season, uuids in sorted(mappings.items()):
        if season == "metadata":  # Skip metadata
            continue

        coverage = check_uuid_coverage(season, uuids)
        all_coverage[season] = coverage

    # Print summary table
    print("\n" + "=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80 + "\n")

    print(f"{'Season':<15s} {'Total':>7s} {'PBP':>7s} {'Shots':>7s} {'PBP %':>8s} {'Shots %':>8s}")
    print("-" * 80)

    total_games = 0
    total_pbp = 0
    total_shots = 0

    for season, cov in sorted(all_coverage.items()):
        print(
            f"{season:<15s} "
            f"{cov['total_games']:>7d} "
            f"{cov['have_pbp']:>7d} "
            f"{cov['have_shots']:>7d} "
            f"{cov['coverage_pbp']:>7.1f}% "
            f"{cov['coverage_shots']:>7.1f}%"
        )

        total_games += cov["total_games"]
        total_pbp += cov["have_pbp"]
        total_shots += cov["have_shots"]

    print("-" * 80)
    print(
        f"{'TOTAL':<15s} "
        f"{total_games:>7d} "
        f"{total_pbp:>7d} "
        f"{total_shots:>7d} "
        f"{(total_pbp/total_games*100) if total_games > 0 else 0:>7.1f}% "
        f"{(total_shots/total_games*100) if total_games > 0 else 0:>7.1f}%"
    )
    print()

    # Save detailed report to file
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"coverage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_coverage, f, indent=2, ensure_ascii=False)

    print(f"[SAVED] Detailed report: {report_file}")

    return {
        "total_games": total_games,
        "total_pbp": total_pbp,
        "total_shots": total_shots,
        "coverage_pbp": (total_pbp / total_games * 100) if total_games > 0 else 0,
        "coverage_shots": (total_shots / total_games * 100) if total_games > 0 else 0,
        "seasons": all_coverage,
    }


# ==============================================================================
# STRESS TESTING
# ==============================================================================


def stress_test_endpoint(uuid: str, endpoint_type: str) -> dict[str, Any]:
    """Stress test a single endpoint

    Args:
        uuid: Fixture UUID to test
        endpoint_type: "pbp" or "shots"

    Returns:
        Dict with test results:
        - success: bool
        - duration: float (seconds)
        - rows: int (number of rows returned)
        - error: str (if failed)
    """
    start_time = time.time()

    try:
        if endpoint_type == "pbp":
            df = fetch_lnb_play_by_play(uuid)
        elif endpoint_type == "shots":
            df = fetch_lnb_game_shots(uuid)
        else:
            return {"success": False, "error": f"Unknown endpoint type: {endpoint_type}"}

        duration = time.time() - start_time

        return {
            "success": True,
            "duration": duration,
            "rows": len(df),
            "error": None,
        }

    except Exception as e:
        duration = time.time() - start_time

        return {
            "success": False,
            "duration": duration,
            "rows": 0,
            "error": str(e),
        }


def run_stress_test(
    uuids: list[str],
    concurrent_requests: int = DEFAULT_CONCURRENT_REQUESTS,
    endpoint_type: str = "pbp",
) -> dict[str, Any]:
    """Run concurrent stress test on endpoints

    Args:
        uuids: List of UUIDs to test
        concurrent_requests: Number of concurrent requests
        endpoint_type: "pbp" or "shots"

    Returns:
        Dict with stress test results
    """
    print(f"\n[STRESS TEST] {endpoint_type.upper()} endpoint")
    print(f"  UUIDs: {len(uuids)}")
    print(f"  Concurrent requests: {concurrent_requests}")

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        # Submit all tasks
        futures = {
            executor.submit(stress_test_endpoint, uuid, endpoint_type): uuid for uuid in uuids
        }

        # Collect results as they complete
        for i, future in enumerate(as_completed(futures), 1):
            uuid = futures[future]

            try:
                result = future.result()
                result["uuid"] = uuid

                status = "✅" if result["success"] else "❌"
                print(f"  [{i}/{len(uuids)}] {uuid[:18]}... {status} {result['duration']:.2f}s")

                results.append(result)

            except Exception as e:
                print(f"  [{i}/{len(uuids)}] {uuid[:18]}... ❌ Exception: {e}")
                results.append(
                    {
                        "uuid": uuid,
                        "success": False,
                        "duration": 0,
                        "rows": 0,
                        "error": str(e),
                    }
                )

    total_duration = time.time() - start_time

    # Calculate statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    durations = [r["duration"] for r in successful]
    avg_duration = sum(durations) / len(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    total_rows = sum(r["rows"] for r in successful)

    print("\n[SUMMARY]")
    print(f"  Total requests: {len(results)}")
    print(f"  Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"  Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
    print(f"  Total duration: {total_duration:.2f}s")
    print(f"  Requests/sec: {len(results)/total_duration:.2f}")
    print(f"  Avg request time: {avg_duration:.2f}s")
    print(f"  Min/Max: {min_duration:.2f}s / {max_duration:.2f}s")
    print(f"  Total rows: {total_rows:,}")

    return {
        "endpoint_type": endpoint_type,
        "total_requests": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "success_rate": len(successful) / len(results) * 100,
        "total_duration": total_duration,
        "requests_per_second": len(results) / total_duration,
        "avg_duration": avg_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "total_rows": total_rows,
        "results": results,
    }


# ==============================================================================
# MEMORY/PERFORMANCE VALIDATION
# ==============================================================================


def validate_memory_performance(
    uuids: list[str],
    sample_size: int = 5,
) -> dict[str, Any]:
    """Validate memory usage and performance

    Args:
        uuids: List of UUIDs to test
        sample_size: Number of UUIDs to sample

    Returns:
        Dict with memory/performance statistics
    """
    import os

    import psutil

    print(f"\n[MEMORY] Testing {sample_size} UUIDs...")

    process = psutil.Process(os.getpid())

    # Take initial memory snapshot
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    results = []

    for i, uuid in enumerate(uuids[:sample_size], 1):
        print(f"  [{i}/{sample_size}] {uuid[:18]}...", end=" ")

        # Measure memory before
        mem_before = process.memory_info().rss / 1024 / 1024

        # Fetch PBP
        start_time = time.time()
        try:
            pbp_df = fetch_lnb_play_by_play(uuid)
            pbp_duration = time.time() - start_time
            pbp_rows = len(pbp_df)
        except Exception:
            pbp_duration = 0
            pbp_rows = 0

        # Fetch shots
        start_time = time.time()
        try:
            shots_df = fetch_lnb_game_shots(uuid)
            shots_duration = time.time() - start_time
            shots_rows = len(shots_df)
        except Exception:
            shots_duration = 0
            shots_rows = 0

        # Measure memory after
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_delta = mem_after - mem_before

        print(f"PBP:{pbp_rows}, Shots:{shots_rows}, Mem:+{mem_delta:.1f}MB")

        results.append(
            {
                "uuid": uuid,
                "pbp_rows": pbp_rows,
                "pbp_duration": pbp_duration,
                "shots_rows": shots_rows,
                "shots_duration": shots_duration,
                "memory_delta_mb": mem_delta,
            }
        )

        time.sleep(0.5)  # Rate limiting

    final_memory = process.memory_info().rss / 1024 / 1024
    total_memory_increase = final_memory - initial_memory

    print("\n[SUMMARY]")
    print(f"  Initial memory: {initial_memory:.1f} MB")
    print(f"  Final memory: {final_memory:.1f} MB")
    print(f"  Total increase: {total_memory_increase:.1f} MB")
    print(f"  Avg memory per game: {total_memory_increase/sample_size:.1f} MB")

    return {
        "initial_memory_mb": initial_memory,
        "final_memory_mb": final_memory,
        "total_increase_mb": total_memory_increase,
        "avg_per_game_mb": total_memory_increase / sample_size,
        "results": results,
    }


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="LNB Data Coverage & Stress Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--report", action="store_true", help="Generate coverage report")

    parser.add_argument("--stress", action="store_true", help="Run stress test")

    parser.add_argument("--memory", action="store_true", help="Run memory/performance validation")

    parser.add_argument(
        "--datasets",
        action="store_true",
        help="Validate normalized dataset coverage (player/team/shot tables)",
    )

    parser.add_argument(
        "--full", action="store_true", help="Run full suite (coverage + datasets + stress + memory)"
    )

    parser.add_argument(
        "--concurrent",
        type=int,
        default=DEFAULT_CONCURRENT_REQUESTS,
        help=f"Concurrent requests for stress test (default: {DEFAULT_CONCURRENT_REQUESTS}, max: {MAX_CONCURRENT_REQUESTS})",
    )

    parser.add_argument(
        "--season", type=str, default=None, help='Test specific season only (e.g., "2023-2024")'
    )

    args = parser.parse_args()

    # Validate concurrent requests
    if args.concurrent > MAX_CONCURRENT_REQUESTS:
        print(f"[WARN] Concurrent requests capped at {MAX_CONCURRENT_REQUESTS}")
        args.concurrent = MAX_CONCURRENT_REQUESTS

    # Load UUIDs
    mappings = load_fixture_uuids()

    if not mappings:
        print("[ERROR] No fixture UUIDs found")
        sys.exit(1)

    # Filter by season if specified
    if args.season:
        if args.season not in mappings:
            print(f"[ERROR] Season {args.season} not found in mappings")
            sys.exit(1)
        mappings = {args.season: mappings[args.season]}

    # Get all UUIDs for stress testing
    all_uuids = []
    for season, uuids in mappings.items():
        if season != "metadata":
            all_uuids.extend(uuids)

    # Run tests
    if args.full or args.report:
        generate_coverage_report()

    if args.full or args.datasets:
        generate_dataset_coverage_report()

    if args.full or args.stress:
        # Stress test PBP endpoint
        run_stress_test(all_uuids[:20], concurrent_requests=args.concurrent, endpoint_type="pbp")

        # Stress test shots endpoint
        run_stress_test(all_uuids[:20], concurrent_requests=args.concurrent, endpoint_type="shots")

    if args.full or args.memory:
        validate_memory_performance(all_uuids, sample_size=5)

    print("\n[DONE]")


if __name__ == "__main__":
    main()
