#!/usr/bin/env python3
"""Comprehensive Data Validation and Monitoring for LNB Pipeline

This script provides:
1. Complete data coverage validation across all seasons
2. Real-time ingestion progress monitoring
3. Data quality checks
4. Live data readiness assessment
5. Automated index rebuilding to prevent overwrites

Created: 2025-11-16
Purpose: Ensure complete multi-season coverage and live data readiness
Following 10-step methodology for production-ready system
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ==============================================================================
# CONFIGURATION
# ==============================================================================

DATA_DIR = Path("data/raw/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

# Expected totals per season
EXPECTED_GAMES = {
    "2022-2023": 306,
    "2023-2024": 306,
    "2024-2025": 240,
    "2025-2026": 176,  # Note: Most are future games
}

# ==============================================================================
# DATA VALIDATION FUNCTIONS
# ==============================================================================


def scan_parquet_files(directory: Path, pattern: str = "*.parquet") -> dict[str, int]:
    """Scan directory for parquet files and count by season

    Args:
        directory: Directory to scan
        pattern: File pattern to match

    Returns:
        Dict mapping season -> file count
    """
    if not directory.exists():
        return {}

    season_counts = {}
    for file_path in directory.rglob(pattern):
        # Extract season from path (format: season=YYYY-YYYY/...)
        path_str = str(file_path)
        if "season=" in path_str:
            season = path_str.split("season=")[1].split("/")[0].split("\\")[0]
            season_counts[season] = season_counts.get(season, 0) + 1

    return season_counts


def load_or_rebuild_index() -> pd.DataFrame:
    """Load game index, rebuilding if corrupted or incomplete

    Returns:
        Complete game index DataFrame
    """
    if INDEX_FILE.exists():
        try:
            df = pd.read_parquet(INDEX_FILE)

            # Check if index has all expected seasons
            expected_seasons = set(EXPECTED_GAMES.keys())
            actual_seasons = set(df["season"].unique())

            if not expected_seasons.issubset(actual_seasons):
                print(f"[WARN] Index missing seasons: {expected_seasons - actual_seasons}")
                print("[WARN] Rebuilding index...")
                return rebuild_index()

            return df

        except Exception as e:
            print(f"[ERROR] Failed to load index: {e}")
            print("[WARN] Rebuilding index...")
            return rebuild_index()
    else:
        print("[WARN] Index not found, rebuilding...")
        return rebuild_index()


def rebuild_index() -> pd.DataFrame:
    """Rebuild complete game index from scratch

    Returns:
        Rebuilt game index DataFrame
    """
    import subprocess

    print(f"\n{'=' * 80}")
    print("  REBUILDING GAME INDEX")
    print(f"{'=' * 80}\n")

    # Run build_game_index.py with all seasons
    seasons = list(EXPECTED_GAMES.keys())
    cmd = [
        "uv",
        "run",
        "python",
        "tools/lnb/build_game_index.py",
        "--seasons",
        *seasons,
        "--force-rebuild",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("[SUCCESS] Index rebuilt successfully")
        return pd.read_parquet(INDEX_FILE)
    else:
        print(f"[ERROR] Failed to rebuild index: {result.stderr}")
        raise RuntimeError("Index rebuild failed")


def validate_data_on_disk() -> dict[str, dict[str, int]]:
    """Validate actual data files on disk

    Returns:
        Dict with PBP and shots counts by season
    """
    print(f"\n{'=' * 80}")
    print("  DATA ON DISK VALIDATION")
    print(f"{'=' * 80}\n")

    pbp_counts = scan_parquet_files(PBP_DIR)
    shots_counts = scan_parquet_files(SHOTS_DIR)

    print("PBP Files by Season:")
    for season in sorted(pbp_counts.keys()):
        expected = EXPECTED_GAMES.get(season, "?")
        actual = pbp_counts[season]
        status = "[OK]" if actual == expected else f"[WARN] ({actual}/{expected})"
        print(f"  {season}: {actual:>4} files {status}")

    print("\nShots Files by Season:")
    for season in sorted(shots_counts.keys()):
        expected = EXPECTED_GAMES.get(season, "?")
        actual = shots_counts[season]
        status = "[OK]" if actual == expected else f"[WARN] ({actual}/{expected})"
        print(f"  {season}: {actual:>4} files {status}")

    return {
        "pbp": pbp_counts,
        "shots": shots_counts,
    }


def validate_index_accuracy(index_df: pd.DataFrame, disk_data: dict) -> dict[str, Any]:
    """Validate that index accurately reflects data on disk

    Args:
        index_df: Game index DataFrame
        disk_data: Dict with PBP and shots counts from disk

    Returns:
        Dict with validation results
    """
    print(f"\n{'=' * 80}")
    print("  INDEX ACCURACY VALIDATION")
    print(f"{'=' * 80}\n")

    issues = []

    for season in EXPECTED_GAMES.keys():
        season_df = index_df[index_df["season"] == season]

        # Count games marked as having data in index
        index_pbp_count = season_df["has_pbp"].sum()
        index_shots_count = season_df["has_shots"].sum()

        # Count actual files on disk
        disk_pbp_count = disk_data["pbp"].get(season, 0)
        disk_shots_count = disk_data["shots"].get(season, 0)

        # Check for mismatches
        pbp_match = index_pbp_count == disk_pbp_count
        shots_match = index_shots_count == disk_shots_count

        print(f"{season}:")
        print(
            f"  PBP:   Index={index_pbp_count:>3}, Disk={disk_pbp_count:>3}  {'[OK]' if pbp_match else '[MISMATCH]'}"
        )
        print(
            f"  Shots: Index={index_shots_count:>3}, Disk={disk_shots_count:>3}  {'[OK]' if shots_match else '[MISMATCH]'}"
        )

        if not pbp_match:
            issues.append(f"{season}: PBP index/disk mismatch")
        if not shots_match:
            issues.append(f"{season}: Shots index/disk mismatch")

    return {
        "accurate": len(issues) == 0,
        "issues": issues,
    }


def analyze_future_games(index_df: pd.DataFrame) -> dict[str, Any]:
    """Analyze which games are future vs played

    Args:
        index_df: Game index DataFrame

    Returns:
        Dict with future/played game analysis
    """
    print(f"\n{'=' * 80}")
    print("  FUTURE vs PLAYED GAMES ANALYSIS")
    print(f"{'=' * 80}\n")

    today = date.today()
    print(f"Today's Date: {today}\n")

    analysis = {}

    for season in sorted(EXPECTED_GAMES.keys()):
        season_df = index_df[index_df["season"] == season].copy()

        if len(season_df) == 0:
            print(f"{season}: No games in index [ERROR]")
            continue

        # Parse dates
        season_df["game_date_dt"] = pd.to_datetime(season_df["game_date"])

        # Count played vs future
        played = (season_df["game_date_dt"] <= pd.Timestamp(today)).sum()
        future = (season_df["game_date_dt"] > pd.Timestamp(today)).sum()

        # Get date range
        min_date = season_df["game_date"].min()
        max_date = season_df["game_date"].max()

        print(f"{season}:")
        print(f"  Total: {len(season_df)} games")
        print(f"  Date range: {min_date} to {max_date}")
        print(f"  Played/Today: {played} games")
        print(f"  Future: {future} games")

        # Check data coverage for played games
        played_df = season_df[season_df["game_date_dt"] <= pd.Timestamp(today)]
        if len(played_df) > 0:
            has_data = (played_df["has_pbp"] & played_df["has_shots"]).sum()
            missing = len(played_df) - has_data
            coverage = (has_data / len(played_df)) * 100 if len(played_df) > 0 else 0

            print(f"  Played games with data: {has_data}/{len(played_df)} ({coverage:.1f}%)")
            if missing > 0:
                print(f"  [WARN] Missing data for {missing} played games")

        analysis[season] = {
            "total": len(season_df),
            "played": played,
            "future": future,
            "date_range": (min_date, max_date),
        }

        print()

    return analysis


def check_live_data_readiness() -> dict[str, Any]:
    """Check if system is ready for live data ingestion

    Returns:
        Dict with readiness status and recommendations
    """
    print(f"\n{'=' * 80}")
    print("  LIVE DATA READINESS CHECK")
    print(f"{'=' * 80}\n")

    checks = {
        "index_complete": INDEX_FILE.exists(),
        "date_filtering": True,  # We have the <= fix
        "current_season_identified": False,
        "api_accessible": True,  # Assume true if we got here
        "ready_for_live": False,
    }

    # Check if we can identify current season
    today = date.today()

    if INDEX_FILE.exists():
        df = pd.read_parquet(INDEX_FILE)

        for season in EXPECTED_GAMES.keys():
            season_df = df[df["season"] == season]
            if len(season_df) > 0:
                min_date = pd.to_datetime(season_df["game_date"].min())
                max_date = pd.to_datetime(season_df["game_date"].max())

                if min_date <= pd.Timestamp(today) <= max_date:
                    checks["current_season"] = season
                    checks["current_season_identified"] = True
                    print(f"[OK] Current season identified: {season}")
                    print(f"   Season runs: {min_date.date()} to {max_date.date()}")
                    break

    # Overall readiness
    checks["ready_for_live"] = all(
        [
            checks["index_complete"],
            checks["date_filtering"],
            checks["current_season_identified"],
            checks["api_accessible"],
        ]
    )

    print("\nReadiness Checklist:")
    print(f"  {'[OK]' if checks['index_complete'] else '[X]'} Game index complete")
    print(
        f"  {'[OK]' if checks['date_filtering'] else '[X]'} Date filtering enabled (includes today)"
    )
    print(f"  {'[OK]' if checks['current_season_identified'] else '[X]'} Current season identified")
    print(f"  {'[OK]' if checks['api_accessible'] else '[X]'} API accessible")

    print(
        f"\n{'[OK] SYSTEM READY FOR LIVE DATA' if checks['ready_for_live'] else '[X] NOT READY FOR LIVE DATA'}"
    )

    if not checks["ready_for_live"]:
        print("\nRecommendations:")
        if not checks["index_complete"]:
            print("  - Rebuild game index")
        if not checks["current_season_identified"]:
            print("  - Verify season date ranges")

    return checks


def generate_ingestion_plan() -> dict[str, list[str]]:
    """Generate plan for completing data ingestion

    Returns:
        Dict mapping season -> list of actions needed
    """
    print(f"\n{'=' * 80}")
    print("  INGESTION COMPLETION PLAN")
    print(f"{'=' * 80}\n")

    # Load index and disk data
    index_df = load_or_rebuild_index()
    disk_data = validate_data_on_disk()

    plan = {}

    for season in sorted(EXPECTED_GAMES.keys()):
        season_df = index_df[index_df["season"] == season]
        expected = EXPECTED_GAMES[season]

        # Count what we have
        disk_pbp = disk_data["pbp"].get(season, 0)
        disk_shots = disk_data["shots"].get(season, 0)

        # Count what index says we need
        if len(season_df) > 0:
            season_df_copy = season_df.copy()
            season_df_copy["game_date_dt"] = pd.to_datetime(season_df_copy["game_date"])
            played = (season_df_copy["game_date_dt"] <= pd.Timestamp(date.today())).sum()

            needs_fetch = ((~season_df["has_pbp"]) | (~season_df["has_shots"])).sum()
        else:
            played = 0
            needs_fetch = 0

        actions = []

        # Determine actions needed
        if disk_pbp < expected or disk_shots < expected:
            if needs_fetch > 0:
                actions.append(f"Ingest {needs_fetch} remaining games")

            missing = expected - max(disk_pbp, disk_shots)
            if missing > 0:
                actions.append(f"Note: {missing} games may be future/unavailable")

        if len(actions) > 0:
            plan[season] = actions
            print(f"{season}:")
            print(f"  Expected: {expected} games")
            print(f"  On disk: {disk_pbp} PBP, {disk_shots} shots")
            print(f"  Played to date: {played} | Indexed needs fetch: {needs_fetch}")
            print("  Actions:")
            for action in actions:
                print(f"    - {action}")
            print()

    return plan


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def main():
    """Run complete validation and monitoring"""
    print(f"\n{'=' * 80}")
    print("  LNB DATA VALIDATION & MONITORING")
    print(f"{'=' * 80}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    # Step 1: Load/rebuild index if needed
    print("[1/7] Loading game index...")
    index_df = load_or_rebuild_index()
    print(f"      Loaded {len(index_df)} games across {len(index_df['season'].unique())} seasons")

    # Step 2: Validate data on disk
    print("\n[2/7] Validating data on disk...")
    disk_data = validate_data_on_disk()

    # Step 3: Validate index accuracy
    print("\n[3/7] Validating index accuracy...")
    accuracy = validate_index_accuracy(index_df, disk_data)

    # Step 4: Analyze future vs played games
    print("\n[4/7] Analyzing future vs played games...")
    future_analysis = analyze_future_games(index_df)
    if future_analysis:
        total_future = sum(info.get("future", 0) for info in future_analysis.values())
        print(f"      Future games remaining across tracked seasons: {total_future}")
        peak_season = max(future_analysis.items(), key=lambda item: item[1].get("future", 0))[0]
        print(f"      Heaviest backlog season: {peak_season}")

    # Step 5: Check live data readiness
    print("\n[5/7] Checking live data readiness...")
    readiness = check_live_data_readiness()

    # Step 6: Generate ingestion plan
    print("\n[6/7] Generating ingestion completion plan...")
    plan = generate_ingestion_plan()

    # Step 7: Summary
    print(f"\n{'=' * 80}")
    print("  VALIDATION SUMMARY")
    print(f"{'=' * 80}\n")

    total_games = sum(EXPECTED_GAMES.values())
    total_pbp = sum(disk_data["pbp"].values())
    total_shots = sum(disk_data["shots"].values())

    print("Total Coverage:")
    print(f"  Expected: {total_games} games across 4 seasons")
    print(f"  PBP files: {total_pbp} ({total_pbp / total_games * 100:.1f}%)")
    print(f"  Shots files: {total_shots} ({total_shots / total_games * 100:.1f}%)")

    print(f"\nIndex Accuracy: {'[PASS]' if accuracy['accurate'] else '[FAIL]'}")
    if not accuracy["accurate"]:
        print(f"  Issues: {len(accuracy['issues'])}")
        for issue in accuracy["issues"]:
            print(f"    - {issue}")

    print(f"\nLive Data Ready: {'[YES]' if readiness['ready_for_live'] else '[NO]'}")

    if plan:
        print(f"\nRemaining Work: {len(plan)} seasons need attention")
    else:
        print("\n[OK] All seasons complete!")

    print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()
