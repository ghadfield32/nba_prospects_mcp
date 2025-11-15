#!/usr/bin/env python3
"""Orchestrate complete historical data pull for LNB Pro A

This script coordinates the full pipeline:
1. Build/update game index
2. Bulk ingest PBP + shots data
3. Transform into normalized tables
4. Validate data quality
5. Generate coverage reports

Purpose:
    - One-command historical data acquisition
    - Idempotent (safe to run multiple times)
    - Resume-able (skips already-fetched data)
    - Comprehensive logging and reporting

Usage:
    # Pull all available seasons
    uv run python tools/lnb/pull_all_historical_data.py

    # Pull specific seasons
    uv run python tools/lnb/pull_all_historical_data.py --seasons 2024-2025 2023-2024

    # Force re-fetch everything
    uv run python tools/lnb/pull_all_historical_data.py --force

    # Dry run (show what would be fetched)
    uv run python tools/lnb/pull_all_historical_data.py --dry-run

Output:
    - Game index: data/raw/lnb/lnb_game_index.parquet
    - PBP data: data/raw/lnb/pbp/season=YYYY-YYYY/*.parquet
    - Shots data: data/raw/lnb/shots/season=YYYY-YYYY/*.parquet
    - Normalized: data/normalized/lnb/{player_game|team_game|shot_events}/
    - Reports: data/reports/lnb_*.csv
"""

from __future__ import annotations

import argparse
import io
import subprocess
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

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

# Paths
TOOLS_DIR = Path("tools/lnb")
DATA_DIR = Path("data/raw/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"

# Available seasons (will be auto-detected or specified)
CURRENT_SEASON = "2024-2025"

# ==============================================================================
# PIPELINE ORCHESTRATION
# ==============================================================================


def run_command(cmd: list[str], description: str, timeout: int = 600) -> bool:
    """Run a subprocess command with logging

    Args:
        cmd: Command list (e.g., ["python", "script.py"])
        description: Human-readable description
        timeout: Timeout in seconds (default: 10 minutes)

    Returns:
        True if successful, False otherwise
    """
    print(f"\n[RUNNING] {description}...")
    print(f"[COMMAND] {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )

        if result.returncode == 0:
            print(f"[SUCCESS] {description} completed")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"[ERROR] {description} failed (exit code {result.returncode})")
            if result.stderr:
                print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] {description} timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"[ERROR] {description} failed: {e}")
        return False


def detect_available_seasons() -> list[str]:
    """Detect available seasons from game index or use default

    Returns:
        List of season strings
    """
    if INDEX_FILE.exists():
        try:
            index_df = pd.read_parquet(INDEX_FILE)
            seasons = index_df["season"].unique().tolist()
            print(f"[INFO] Detected {len(seasons)} seasons from index: {seasons}")
            return sorted(seasons, reverse=True)
        except Exception as e:
            print(f"[WARN] Could not read index: {e}")

    print(f"[INFO] Using default season: {CURRENT_SEASON}")
    return [CURRENT_SEASON]


def pull_historical_data(
    seasons: list[str] = None,
    force: bool = False,
    dry_run: bool = False,
    max_games_per_season: int = None,
) -> dict[str, Any]:
    """Orchestrate complete historical data pull

    Args:
        seasons: List of seasons to pull (None for all)
        force: Force re-fetch even if already fetched
        dry_run: Show what would be done without executing
        max_games_per_season: Limit games per season (for testing)

    Returns:
        Dict with pipeline execution summary
    """
    print(f"{'='*80}")
    print("  LNB HISTORICAL DATA PULL - FULL PIPELINE")
    print(f"{'='*80}\n")

    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Force mode: {force}")
    print(f"Dry run: {dry_run}")
    if max_games_per_season:
        print(f"Max games per season: {max_games_per_season}")
    print()

    # Determine seasons to process
    if not seasons:
        seasons = detect_available_seasons()

    print(f"Seasons to process: {seasons}\n")

    if dry_run:
        print("[DRY RUN] Would execute the following pipeline:")
        print("1. Build/update game index")
        print(f"2. Bulk ingest PBP + shots for seasons: {seasons}")
        print("3. Transform into normalized tables")
        print("4. Validate data quality")
        print("5. Generate coverage reports")
        return {"dry_run": True}

    # Track results
    results = {"start_time": datetime.now(), "seasons": seasons, "steps": {}}

    # ===========================================================================
    # STEP 1: Build/Update Game Index
    # ===========================================================================
    print(f"\n{'='*80}")
    print("  STEP 1/5: BUILD/UPDATE GAME INDEX")
    print(f"{'='*80}\n")

    cmd = ["uv", "run", "python", str(TOOLS_DIR / "build_game_index.py")]
    if force:
        cmd.append("--force")

    results["steps"]["game_index"] = run_command(cmd, "Build game index", timeout=300)

    # ===========================================================================
    # STEP 2: Bulk Ingest PBP + Shots
    # ===========================================================================
    print(f"\n{'='*80}")
    print("  STEP 2/5: BULK INGEST PBP + SHOTS")
    print(f"{'='*80}\n")

    cmd = ["uv", "run", "python", str(TOOLS_DIR / "bulk_ingest_pbp_shots.py")]
    cmd.extend(["--seasons"] + seasons)
    if force:
        cmd.append("--force-refetch")
    if max_games_per_season:
        cmd.extend(["--max-games", str(max_games_per_season)])

    results["steps"]["bulk_ingest"] = run_command(
        cmd,
        "Bulk ingest PBP and shots",
        timeout=1800,  # 30 minutes for large datasets
    )

    # ===========================================================================
    # STEP 3: Transform Normalized Tables
    # ===========================================================================
    print(f"\n{'='*80}")
    print("  STEP 3/5: TRANSFORM NORMALIZED TABLES")
    print(f"{'='*80}\n")

    cmd = ["uv", "run", "python", str(TOOLS_DIR / "create_normalized_tables.py")]
    if force:
        cmd.append("--force")

    results["steps"]["normalized_tables"] = run_command(
        cmd, "Create normalized tables", timeout=600
    )

    # ===========================================================================
    # STEP 4: Validate Data Quality
    # ===========================================================================
    print(f"\n{'='*80}")
    print("  STEP 4/5: VALIDATE DATA QUALITY")
    print(f"{'='*80}\n")

    cmd = ["uv", "run", "python", str(TOOLS_DIR / "validate_data_consistency.py")]

    results["steps"]["validation"] = run_command(cmd, "Cross-validate PBP and shots", timeout=300)

    # ===========================================================================
    # STEP 5: Generate Coverage Reports
    # ===========================================================================
    print(f"\n{'='*80}")
    print("  STEP 5/5: GENERATE COVERAGE REPORTS")
    print(f"{'='*80}\n")

    cmd = ["uv", "run", "python", str(TOOLS_DIR / "run_lnb_stress_tests.py")]
    cmd.extend(["--max-games-per-season", "10"])  # Quick coverage check

    results["steps"]["coverage_reports"] = run_command(
        cmd, "Generate coverage reports", timeout=300
    )

    # ===========================================================================
    # FINAL SUMMARY
    # ===========================================================================
    results["end_time"] = datetime.now()
    results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()

    print(f"\n\n{'='*80}")
    print("  PIPELINE EXECUTION SUMMARY")
    print(f"{'='*80}\n")

    print(f"Start time:    {results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time:      {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        f"Duration:      {results['duration']:.0f} seconds ({results['duration']/60:.1f} minutes)"
    )
    print()

    print("Pipeline Steps:")
    for step_name, success in results["steps"].items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"  {step_name:25s}: {status}")
    print()

    all_success = all(results["steps"].values())
    if all_success:
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
    else:
        print("⚠️  PIPELINE COMPLETED WITH ERRORS")
        failed_steps = [name for name, success in results["steps"].items() if not success]
        print(f"Failed steps: {', '.join(failed_steps)}")
    print()

    return results


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate complete LNB historical data pull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Pull all available seasons
    uv run python tools/lnb/pull_all_historical_data.py

    # Pull specific seasons
    uv run python tools/lnb/pull_all_historical_data.py --seasons 2024-2025 2023-2024

    # Force re-fetch everything (ignore existing data)
    uv run python tools/lnb/pull_all_historical_data.py --force

    # Dry run (show what would be done)
    uv run python tools/lnb/pull_all_historical_data.py --dry-run

    # Test with limited data (10 games per season)
    uv run python tools/lnb/pull_all_historical_data.py --max-games 10

Pipeline Steps:
    1. Build/update game index (links LNB IDs to fixture UUIDs)
    2. Bulk ingest PBP + shots (raw Parquet storage)
    3. Transform normalized tables (PLAYER_GAME, TEAM_GAME, SHOT_EVENTS)
    4. Validate data quality (cross-validation, schema checks)
    5. Generate coverage reports (seasonal summaries)

Output Locations:
    - Game index:     data/raw/lnb/lnb_game_index.parquet
    - PBP data:       data/raw/lnb/pbp/season=YYYY-YYYY/*.parquet
    - Shots data:     data/raw/lnb/shots/season=YYYY-YYYY/*.parquet
    - Normalized:     data/normalized/lnb/{player_game|team_game|shot_events}/
    - Reports:        data/reports/lnb_*.csv
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        help="Seasons to process (default: auto-detect from index or use current season)",
    )

    parser.add_argument(
        "--force", action="store_true", help="Force re-fetch even if data already exists"
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without executing"
    )

    parser.add_argument(
        "--max-games", type=int, default=None, help="Limit games per season (for testing)"
    )

    args = parser.parse_args()

    # Execute pipeline
    results = pull_historical_data(
        seasons=args.seasons,
        force=args.force,
        dry_run=args.dry_run,
        max_games_per_season=args.max_games,
    )

    # Exit with appropriate code
    if results.get("dry_run"):
        sys.exit(0)

    all_success = all(results.get("steps", {}).values())
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
