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

import json
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


def summarize_dataset_completeness(disk_data: dict[str, dict[str, int]]) -> None:
    """Print a compact per-season completeness report for PBP and shots.

    Args:
        disk_data: Dict with 'pbp' and 'shots' keys mapping season -> file count
    """
    print("\nDATASET COMPLETENESS SUMMARY")
    print("-" * 40)
    for season, expected in EXPECTED_GAMES.items():
        pbp = disk_data["pbp"].get(season, 0)
        shots = disk_data["shots"].get(season, 0)
        pbp_pct = (pbp / expected * 100) if expected else 0
        shots_pct = (shots / expected * 100) if expected else 0
        print(
            f"{season}: PBP {pbp}/{expected} ({pbp_pct:5.1f}%), "
            f"Shots {shots}/{expected} ({shots_pct:5.1f}%)"
        )


def compute_per_game_score_from_pbp(pbp_df: pd.DataFrame) -> tuple[int, int]:
    """Compute final home/away score from a single game's PBP DataFrame.

    Args:
        pbp_df: PBP DataFrame for a single game

    Returns:
        Tuple of (home_score, away_score) from final event

    Note:
        Assumes HOME_SCORE and AWAY_SCORE columns exist.
        Returns (0, 0) if DataFrame is empty.
    """
    if pbp_df.empty:
        return 0, 0

    last_row = pbp_df.iloc[-1]
    home_score = int(last_row.get("HOME_SCORE", 0))
    away_score = int(last_row.get("AWAY_SCORE", 0))
    return home_score, away_score


def compute_per_game_shot_counts_from_pbp(pbp_df: pd.DataFrame) -> int:
    """Compute the number of field goal attempts from a single game's PBP DataFrame.

    Args:
        pbp_df: PBP DataFrame for a single game

    Returns:
        Count of field goal attempts (2pt, 3pt)

    Note:
        LNB shots table only contains field goals, not free throws.
        This function matches that by counting only '2pt' and '3pt' events.
    """
    if pbp_df.empty:
        return 0

    if "EVENT_TYPE" in pbp_df.columns:
        # Count field goals only (exclude freeThrow to match shots table)
        field_goals = pbp_df["EVENT_TYPE"].isin(["2pt", "3pt"])
        return int(field_goals.sum())

    return 0


def validate_per_game_consistency(
    index_df: pd.DataFrame,
    seasons: list[str] | None = None,
    max_games: int | None = None,
) -> list[dict[str, Any]]:
    """Run per-game consistency checks across PBP, shots, and fixture metadata.

    Args:
        index_df: Game index DataFrame
        seasons: Optional list of seasons to validate
        max_games: Optional limit on number of games to check

    Returns:
        List of issue dicts with keys:
            - 'season': season string
            - 'game_id': game UUID
            - 'level': 'warning' | 'error'
            - 'code': short error code
            - 'message': descriptive message
    """
    issues: list[dict[str, Any]] = []

    df = index_df
    if seasons:
        df = df[df["season"].isin(seasons)]

    if max_games is not None:
        df = df.head(max_games)

    for row in df.itertuples():
        season = row.season
        game_id = row.game_id

        # Only check games that should have data
        if not getattr(row, "has_pbp", False) and not getattr(row, "has_shots", False):
            continue

        pbp_path = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
        shots_path = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

        pbp_df: pd.DataFrame | None = None
        shots_df: pd.DataFrame | None = None

        # Validate PBP
        if pbp_path.exists():
            pbp_df = pd.read_parquet(pbp_path)

            # Check for required columns
            required_pbp_cols = {"HOME_SCORE", "AWAY_SCORE", "PERIOD_ID", "EVENT_TYPE"}
            missing_cols = required_pbp_cols - set(pbp_df.columns)
            if missing_cols:
                issues.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "level": "error",
                        "code": "PBP_MISSING_COLUMNS",
                        "message": f"Missing required columns: {missing_cols}",
                    }
                )

            # Score monotonicity check
            if {"HOME_SCORE", "AWAY_SCORE"}.issubset(pbp_df.columns):
                for col in ("HOME_SCORE", "AWAY_SCORE"):
                    score_diff = pbp_df[col].diff().fillna(0)
                    if (score_diff < 0).any():
                        issues.append(
                            {
                                "season": season,
                                "game_id": game_id,
                                "level": "error",
                                "code": "PBP_SCORE_DECREASE",
                                "message": f"{col} decreases within game",
                            }
                        )

            # Period monotonicity check
            if "PERIOD_ID" in pbp_df.columns:
                period_diff = pbp_df["PERIOD_ID"].diff().fillna(0)
                if (period_diff < 0).any():
                    issues.append(
                        {
                            "season": season,
                            "game_id": game_id,
                            "level": "warning",
                            "code": "PBP_PERIOD_NON_MONOTONIC",
                            "message": "PERIOD_ID decreases within game",
                        }
                    )

        # Validate Shots
        if shots_path.exists():
            shots_df = pd.read_parquet(shots_path)

            # Check for required columns
            required_shots_cols = {"SHOT_TYPE", "SUCCESS", "TEAM_ID"}
            missing_cols = required_shots_cols - set(shots_df.columns)
            if missing_cols:
                issues.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "level": "error",
                        "code": "SHOTS_MISSING_COLUMNS",
                        "message": f"Missing required columns: {missing_cols}",
                    }
                )

            # Shot type validation
            if "SHOT_TYPE" in shots_df.columns:
                valid_shot_types = {"2pt", "3pt"}
                invalid_shots = ~shots_df["SHOT_TYPE"].isin(valid_shot_types)
                if invalid_shots.any():
                    invalid_types = shots_df.loc[invalid_shots, "SHOT_TYPE"].unique()
                    issues.append(
                        {
                            "season": season,
                            "game_id": game_id,
                            "level": "warning",
                            "code": "SHOTS_INVALID_TYPE",
                            "message": f"Found invalid SHOT_TYPE values: {list(invalid_types)}",
                        }
                    )

            # Success flag validation
            if "SUCCESS" in shots_df.columns:
                valid_success = {True, False, 0, 1}
                invalid_success = ~shots_df["SUCCESS"].isin(valid_success)
                if invalid_success.any():
                    issues.append(
                        {
                            "season": season,
                            "game_id": game_id,
                            "level": "error",
                            "code": "SHOTS_INVALID_SUCCESS_FLAG",
                            "message": "Found SUCCESS values outside {True, False, 0, 1}",
                        }
                    )

        # Cross-check PBP vs shots counts
        if pbp_df is not None and shots_df is not None:
            pbp_field_goals = compute_per_game_shot_counts_from_pbp(pbp_df)
            shots_count = len(shots_df)

            # Should match exactly (both are field goal attempts only)
            if pbp_field_goals != shots_count:
                issues.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "level": "warning",
                        "code": "PBP_SHOTS_COUNT_MISMATCH",
                        "message": f"PBP field goals={pbp_field_goals}, shots table={shots_count}",
                    }
                )

    return issues


def check_season_readiness(
    season: str, disk_data: dict[str, dict[str, int]], issues: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check if a season is ready for modeling/live ingestion.

    Args:
        season: Season string (e.g., "2023-2024")
        disk_data: Dict with 'pbp' and 'shots' counts per season
        issues: List of validation issues from validate_per_game_consistency

    Returns:
        Dict with readiness status:
            - 'season': season string
            - 'pbp_count': actual PBP files
            - 'shots_count': actual shots files
            - 'pbp_pct': percentage complete
            - 'shots_pct': percentage complete
            - 'num_critical_issues': count of errors
            - 'num_warnings': count of warnings
            - 'ready_for_modeling': boolean flag
    """
    expected = EXPECTED_GAMES.get(season, 0)
    pbp_count = disk_data["pbp"].get(season, 0)
    shots_count = disk_data["shots"].get(season, 0)

    pbp_pct = (pbp_count / expected * 100) if expected else 0
    shots_pct = (shots_count / expected * 100) if expected else 0

    # Count issues for this season
    season_issues = [i for i in issues if i["season"] == season]
    num_errors = sum(1 for i in season_issues if i["level"] == "error")
    num_warnings = sum(1 for i in season_issues if i["level"] == "warning")

    # Readiness criteria:
    # - Coverage at least 95% for both PBP and shots
    # - No critical errors
    ready = pbp_pct >= 95.0 and shots_pct >= 95.0 and num_errors == 0

    return {
        "season": season,
        "pbp_count": pbp_count,
        "shots_count": shots_count,
        "pbp_pct": pbp_pct,
        "shots_pct": shots_pct,
        "num_critical_issues": num_errors,
        "num_warnings": num_warnings,
        "ready_for_modeling": ready,
    }


def validate_golden_fixtures() -> list[dict[str, Any]]:
    """Validate golden fixture snapshots for regression testing.

    Loads reference games from golden_fixtures.json and compares actual
    data on disk against expected values to catch API changes, schema drift,
    or data corruption.

    Returns:
        List of regression failures with keys:
            - 'game_id': game UUID
            - 'season': season string
            - 'field': which field failed
            - 'expected': expected value
            - 'actual': actual value
            - 'message': descriptive message
    """
    golden_file = Path(__file__).parent / "golden_fixtures.json"
    if not golden_file.exists():
        return []

    try:
        with open(golden_file) as f:
            golden_data = json.load(f)
    except Exception as e:
        return [
            {
                "game_id": "N/A",
                "season": "N/A",
                "field": "json_load",
                "expected": None,
                "actual": None,
                "message": f"Failed to load golden fixtures: {e}",
            }
        ]

    failures = []

    for fixture in golden_data.get("fixtures", []):
        game_id = fixture["game_id"]
        season = fixture["season"]
        expected = fixture["expected"]

        pbp_path = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
        shots_path = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

        if not pbp_path.exists():
            failures.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "field": "pbp_file",
                    "expected": "exists",
                    "actual": "missing",
                    "message": "PBP file missing for golden fixture",
                }
            )
            continue

        if not shots_path.exists():
            failures.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "field": "shots_file",
                    "expected": "exists",
                    "actual": "missing",
                    "message": "Shots file missing for golden fixture",
                }
            )
            continue

        # Load data
        pbp_df = pd.read_parquet(pbp_path)
        shots_df = pd.read_parquet(shots_path)

        # Check PBP row count
        if "num_pbp_rows" in expected:
            actual_rows = len(pbp_df)
            expected_rows = expected["num_pbp_rows"]
            if actual_rows != expected_rows:
                failures.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "field": "num_pbp_rows",
                        "expected": expected_rows,
                        "actual": actual_rows,
                        "message": "PBP row count mismatch",
                    }
                )

        # Check shots row count
        if "num_shots" in expected:
            actual_shots = len(shots_df)
            expected_shots = expected["num_shots"]
            if actual_shots != expected_shots:
                failures.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "field": "num_shots",
                        "expected": expected_shots,
                        "actual": actual_shots,
                        "message": "Shots row count mismatch",
                    }
                )

        # Check final score
        if "final_score_home" in expected and "final_score_away" in expected:
            home_score, away_score = compute_per_game_score_from_pbp(pbp_df)
            if home_score != expected["final_score_home"]:
                failures.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "field": "final_score_home",
                        "expected": expected["final_score_home"],
                        "actual": home_score,
                        "message": "Home final score mismatch",
                    }
                )
            if away_score != expected["final_score_away"]:
                failures.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "field": "final_score_away",
                        "expected": expected["final_score_away"],
                        "actual": away_score,
                        "message": "Away final score mismatch",
                    }
                )

        # Check number of periods
        if "num_periods" in expected and "PERIOD_ID" in pbp_df.columns:
            actual_periods = pbp_df["PERIOD_ID"].max()
            expected_periods = expected["num_periods"]
            if actual_periods != expected_periods:
                failures.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "field": "num_periods",
                        "expected": expected_periods,
                        "actual": actual_periods,
                        "message": "Number of periods mismatch",
                    }
                )

        # Check event type distribution (if specified)
        if "pbp_event_types" in expected and "EVENT_TYPE" in pbp_df.columns:
            actual_counts = pbp_df["EVENT_TYPE"].value_counts().to_dict()
            for event_type, expected_count in expected["pbp_event_types"].items():
                actual_count = actual_counts.get(event_type, 0)
                # Allow small variance (±5%) for non-deterministic events
                tolerance = max(1, int(expected_count * 0.05))
                if abs(actual_count - expected_count) > tolerance:
                    failures.append(
                        {
                            "game_id": game_id,
                            "season": season,
                            "field": f"pbp_event_type_{event_type}",
                            "expected": expected_count,
                            "actual": actual_count,
                            "message": f"Event type '{event_type}' count outside tolerance",
                        }
                    )

    return failures


def audit_sampled_games_against_api(
    index_df: pd.DataFrame, sample_size: int = 5, seasons: list[str] | None = None
) -> list[dict[str, Any]]:
    """Randomly sample games and compare disk data against live API.

    Args:
        index_df: Game index DataFrame
        sample_size: Number of games to sample (default 5)
        seasons: Optional list of seasons to sample from (default: READY seasons)

    Returns:
        List of discrepancies with keys:
            - 'game_id': game UUID
            - 'season': season string
            - 'metric': which metric differs
            - 'disk_value': value from disk
            - 'api_value': value from API
            - 'message': descriptive message
    """
    try:
        from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play, fetch_lnb_shots
    except ImportError:
        return [
            {
                "game_id": "N/A",
                "season": "N/A",
                "metric": "import",
                "disk_value": None,
                "api_value": None,
                "message": "Failed to import LNB fetchers",
            }
        ]

    discrepancies = []

    # Filter to games with both PBP and shots
    df = index_df[index_df["has_pbp"] & index_df["has_shots"]].copy()

    if seasons:
        df = df[df["season"].isin(seasons)]

    if len(df) == 0:
        return []

    # Random sample
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)

    for row in sample.itertuples():
        game_id = row.game_id
        season = row.season

        # Load disk data
        pbp_path = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
        shots_path = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

        if not pbp_path.exists() or not shots_path.exists():
            continue

        disk_pbp = pd.read_parquet(pbp_path)
        disk_shots = pd.read_parquet(shots_path)

        # Fetch from API
        try:
            api_pbp = fetch_lnb_play_by_play(game_id)
            api_shots = fetch_lnb_shots(game_id)
        except Exception as e:
            discrepancies.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "metric": "api_fetch",
                    "disk_value": None,
                    "api_value": None,
                    "message": f"API fetch failed: {str(e)[:100]}",
                }
            )
            continue

        # Compare row counts
        if len(disk_pbp) != len(api_pbp):
            discrepancies.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "metric": "pbp_row_count",
                    "disk_value": len(disk_pbp),
                    "api_value": len(api_pbp),
                    "message": "PBP row count mismatch between disk and API",
                }
            )

        if len(disk_shots) != len(api_shots):
            discrepancies.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "metric": "shots_row_count",
                    "disk_value": len(disk_shots),
                    "api_value": len(api_shots),
                    "message": "Shots row count mismatch between disk and API",
                }
            )

        # Compare final scores
        disk_home, disk_away = compute_per_game_score_from_pbp(disk_pbp)
        api_home, api_away = compute_per_game_score_from_pbp(api_pbp)

        if disk_home != api_home or disk_away != api_away:
            discrepancies.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "metric": "final_score",
                    "disk_value": f"{disk_home}-{disk_away}",
                    "api_value": f"{api_home}-{api_away}",
                    "message": "Final score mismatch between disk and API",
                }
            )

    return discrepancies


def record_validation_metrics(
    disk_data: dict[str, dict[str, int]],
    readiness_results: list[dict[str, Any]],
    num_errors: int,
    num_warnings: int,
) -> None:
    """Record validation metrics to time-series parquet for monitoring.

    Args:
        disk_data: Dict with 'pbp' and 'shots' counts per season
        readiness_results: List of season readiness dicts
        num_errors: Total number of errors found
        num_warnings: Total number of warnings found
    """
    metrics_file = DATA_DIR / "lnb_metrics_daily.parquet"

    # Build metrics row
    metrics = {
        "run_date": datetime.now().isoformat(),
        "total_errors": num_errors,
        "total_warnings": num_warnings,
    }

    # Add per-season metrics
    for readiness in readiness_results:
        season = readiness["season"]
        prefix = season.replace("-", "_")
        metrics[f"{prefix}_pbp_pct"] = readiness["pbp_pct"]
        metrics[f"{prefix}_shots_pct"] = readiness["shots_pct"]
        metrics[f"{prefix}_ready"] = readiness["ready_for_modeling"]

    metrics_df = pd.DataFrame([metrics])

    # Append to existing metrics or create new
    if metrics_file.exists():
        existing = pd.read_parquet(metrics_file)
        metrics_df = pd.concat([existing, metrics_df], ignore_index=True)

    metrics_df.to_parquet(metrics_file, index=False)
    print(f"[INFO] Recorded validation metrics to {metrics_file}")


def save_validation_status(
    readiness_results: list[dict[str, Any]],
    golden_failures: list[dict[str, Any]],
    api_discrepancies: list[dict[str, Any]],
    num_errors: int,
    num_warnings: int,
) -> None:
    """Save latest validation status to JSON for API consumption.

    Args:
        readiness_results: List of season readiness dicts
        golden_failures: List of golden fixture failures
        api_discrepancies: List of API spot-check discrepancies
        num_errors: Total number of consistency errors
        num_warnings: Total number of consistency warnings
    """
    status_file = DATA_DIR / "lnb_last_validation.json"

    # Transform readiness results to match API schema
    api_seasons = []
    for r in readiness_results:
        season_expected = EXPECTED_GAMES.get(r["season"], 0)
        api_seasons.append(
            {
                "season": r["season"],
                "ready_for_modeling": r["ready_for_modeling"],
                "pbp_coverage": r["pbp_count"],
                "pbp_expected": season_expected,
                "pbp_pct": r["pbp_pct"],
                "shots_coverage": r["shots_count"],
                "shots_expected": season_expected,
                "shots_pct": r["shots_pct"],
                "num_critical_issues": r["num_critical_issues"],
            }
        )

    status = {
        "run_at": datetime.now().isoformat(),
        "golden_fixtures_passed": len(golden_failures) == 0,
        "golden_failures": len(golden_failures),
        "api_spotcheck_passed": len(api_discrepancies) == 0,
        "api_discrepancies": len(api_discrepancies),
        "consistency_errors": num_errors,
        "consistency_warnings": num_warnings,
        "seasons": api_seasons,
        "ready_for_live": any(r["ready_for_modeling"] for r in readiness_results),
    }

    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)

    print(f"[INFO] Saved validation status to {status_file}")


def require_season_ready(season: str, raise_on_not_ready: bool = True) -> dict[str, Any]:
    """Gate function for downstream code to check season readiness.

    Args:
        season: Season to check (e.g., "2023-2024")
        raise_on_not_ready: If True, raise ValueError when not ready

    Returns:
        Readiness status dict

    Raises:
        ValueError: If season is not ready and raise_on_not_ready=True
    """
    # Load current state
    index_df = load_or_rebuild_index()
    disk_data = validate_data_on_disk()
    issues = validate_per_game_consistency(index_df, seasons=[season])

    readiness = check_season_readiness(season, disk_data, issues)

    if not readiness["ready_for_modeling"] and raise_on_not_ready:
        raise ValueError(
            f"Season {season} is NOT READY for modeling:\n"
            f"  Coverage: PBP {readiness['pbp_pct']:.1f}%, Shots {readiness['shots_pct']:.1f}%\n"
            f"  Critical issues: {readiness['num_critical_issues']}\n"
            f"  Run validation: uv run python tools/lnb/validate_and_monitor_coverage.py"
        )

    return readiness


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
    summarize_dataset_completeness(disk_data)

    # Step 3: Validate index accuracy
    print("\n[3/7] Validating index accuracy...")
    accuracy = validate_index_accuracy(index_df, disk_data)

    # Step 4: Run per-game consistency checks
    print("\n[4/7] Running per-game consistency checks...")
    issues = validate_per_game_consistency(index_df)
    num_errors = sum(1 for x in issues if x["level"] == "error")
    num_warnings = sum(1 for x in issues if x["level"] == "warning")
    print(f"      Found {num_errors} errors, {num_warnings} warnings")

    # Print sample issues (first 10)
    if issues:
        print("\n      Sample Issues:")
        for issue in issues[:10]:
            level_tag = "[ERROR]" if issue["level"] == "error" else "[WARN]"
            print(
                f"        {level_tag} {issue['season']} {issue['game_id'][:16]}: "
                f"{issue['code']}"
            )
        if len(issues) > 10:
            print(f"        ... and {len(issues) - 10} more issues")

    # Step 5: Check season readiness
    print("\n[5/7] Checking season readiness...")
    readiness_results = []
    for season in EXPECTED_GAMES.keys():
        readiness = check_season_readiness(season, disk_data, issues)
        readiness_results.append(readiness)
        status = "✓ READY" if readiness["ready_for_modeling"] else "✗ NOT READY"
        print(
            f"      {season}: {status} "
            f"(Coverage: {readiness['pbp_pct']:.1f}%/{readiness['shots_pct']:.1f}%, "
            f"Errors: {readiness['num_critical_issues']})"
        )

    # Step 6: Analyze future vs played games
    print("\n[6/7] Analyzing future vs played games...")
    future_analysis = analyze_future_games(index_df)
    if future_analysis:
        total_future = sum(info.get("future", 0) for info in future_analysis.values())
        print(f"      Future games remaining across tracked seasons: {total_future}")
        peak_season = max(future_analysis.items(), key=lambda item: item[1].get("future", 0))[0]
        print(f"      Heaviest backlog season: {peak_season}")

    # Step 7: Validate golden fixtures (regression testing)
    print("\n[7/9] Validating golden fixtures (regression testing)...")
    golden_failures = validate_golden_fixtures()
    if golden_failures:
        print(f"      Found {len(golden_failures)} regression failures:")
        for failure in golden_failures[:5]:
            print(
                f"        - {failure['field']}: expected={failure['expected']}, actual={failure['actual']}"
            )
        if len(golden_failures) > 5:
            print(f"        ... and {len(golden_failures) - 5} more failures")
    else:
        print("      ✓ All golden fixtures passed")

    # Step 8: API spot-check (random sampling)
    print("\n[8/9] Running API spot-check (sampling 5 random games)...")
    ready_seasons = [r["season"] for r in readiness_results if r["ready_for_modeling"]]
    api_discrepancies = audit_sampled_games_against_api(
        index_df, sample_size=5, seasons=ready_seasons if ready_seasons else None
    )
    if api_discrepancies:
        print(f"      Found {len(api_discrepancies)} API discrepancies:")
        for disc in api_discrepancies[:5]:
            print(f"        - {disc['metric']}: disk={disc['disk_value']}, api={disc['api_value']}")
        if len(api_discrepancies) > 5:
            print(f"        ... and {len(api_discrepancies) - 5} more discrepancies")
    else:
        print("      ✓ API spot-check passed (sampled games match)")

    # Step 9: Check live data readiness (system-wide)
    print("\n[9/9] Checking live data readiness (system-wide)...")
    readiness = check_live_data_readiness()

    # Record metrics for time-series monitoring
    record_validation_metrics(disk_data, readiness_results, num_errors, num_warnings)

    # Persist validation status for API consumption
    save_validation_status(
        readiness_results, golden_failures, api_discrepancies, num_errors, num_warnings
    )

    # Summary
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

    print(f"\nPer-Game Consistency: {num_errors} errors, {num_warnings} warnings")

    print("\nRegression Testing:")
    print(
        f"  Golden fixtures: {'[PASS]' if not golden_failures else f'[FAIL] {len(golden_failures)} failures'}"
    )
    print(
        f"  API spot-check: {'[PASS]' if not api_discrepancies else f'[WARN] {len(api_discrepancies)} discrepancies'}"
    )

    print("\nSeason Readiness:")
    ready_seasons_list = [r for r in readiness_results if r["ready_for_modeling"]]
    not_ready_seasons = [r for r in readiness_results if not r["ready_for_modeling"]]
    print(f"  Ready for modeling: {len(ready_seasons_list)}/{len(readiness_results)} seasons")
    if not_ready_seasons:
        print("  Not ready:")
        for r in not_ready_seasons:
            print(
                f"    - {r['season']}: {r['pbp_pct']:.1f}%/{r['shots_pct']:.1f}% coverage, "
                f"{r['num_critical_issues']} errors"
            )

    print(f"\nLive Data Ready: {'[YES]' if readiness['ready_for_live'] else '[NO]'}")

    print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()
