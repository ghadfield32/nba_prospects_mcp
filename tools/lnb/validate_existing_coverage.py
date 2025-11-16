#!/usr/bin/env python3
"""Validate existing LNB historical data coverage

This script validates the integrity and coverage of existing LNB data:
- Normalized box scores (2021-2025): player_game, team_game
- Historical PBP/shots (2025-2026): pbp_events, shots
- Raw schedule data

Enhanced Features:
    - Tracks per-season game IDs for duplicate detection
    - Detects duplicate games across season partitions
    - Summarizes fixture-level coverage (fixtures with/without PBP/shots)
    - Flags potential duplicate PBP/shot events using inferred keys
    - Reports global unique game counts per dataset

Purpose:
    - Verify data integrity (row counts, schemas, null values)
    - Document actual coverage by season
    - Identify data quality issues (duplicates, missing data)
    - Generate comprehensive validation report

Usage:
    uv run python tools/lnb/validate_existing_coverage.py

Output:
    - Console: Comprehensive validation report
    - File: tools/lnb/coverage_validation_report.json
    - File: tools/lnb/coverage_validation_report.txt
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_ROOT = Path("data")
NORMALIZED_ROOT = DATA_ROOT / "normalized" / "lnb"
HISTORICAL_ROOT = DATA_ROOT / "lnb" / "historical"
OUTPUT_DIR = Path("tools/lnb")

SEASONS_TO_VALIDATE = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
HISTORICAL_SEASONS = ["2025-2026"]

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def validate_normalized_season(dataset_name: str, season: str) -> dict:
    """Validate a normalized dataset for a specific season.

    Args:
        dataset_name: "player_game" or "team_game"
        season: Season string (e.g., "2021-2022")

    Returns:
        Dict with validation results, including per-season game IDs.
    """
    season_dir = NORMALIZED_ROOT / dataset_name / f"season={season}"

    result: dict[str, object] = {
        "dataset": dataset_name,
        "season": season,
        "exists": False,
        "file_count": 0,
        "total_rows": 0,
        "columns": [],
        "column_count": 0,
        "null_counts": {},
        "date_range": None,
        "unique_games": 0,
        "unique_players_or_teams": 0,
        # NEW: list of GAME_IDs to enable duplicate analysis across seasons
        "game_ids": [],
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append("Directory does not exist")
        return result

    result["exists"] = True

    parquet_files = list(season_dir.glob("*.parquet"))
    result["file_count"] = len(parquet_files)

    if not parquet_files:
        result["issues"].append("No parquet files found")
        return result

    try:
        df = pd.concat(
            [pd.read_parquet(f) for f in parquet_files],
            ignore_index=True,
        )

        result["total_rows"] = len(df)
        result["columns"] = list(df.columns)
        result["column_count"] = len(df.columns)

        key_cols = ["GAME_ID", "GAME_DATE", "SEASON"]
        if dataset_name == "player_game":
            key_cols.extend(["PLAYER_ID", "PLAYER_NAME", "PTS", "REB", "AST"])
        else:
            key_cols.extend(["TEAM_ID", "PTS", "FG_PCT"])

        for col in key_cols:
            if col in df.columns:
                null_count = int(df[col].isna().sum())
                if null_count > 0:
                    result["null_counts"][col] = null_count

        # Date range (if GAME_DATE exists and is non-null)
        if "GAME_DATE" in df.columns:
            dates = pd.to_datetime(df["GAME_DATE"], errors="coerce").dropna()
            if not dates.empty:
                result["date_range"] = {
                    "earliest": dates.min().isoformat(),
                    "latest": dates.max().isoformat(),
                }

        # Game and entity counts
        if "GAME_ID" in df.columns:
            game_ids = df["GAME_ID"].dropna().astype(str)
            result["unique_games"] = int(game_ids.nunique())
            # Store sorted unique game IDs for duplicate analysis
            result["game_ids"] = sorted(game_ids.unique().tolist())

        if dataset_name == "player_game" and "PLAYER_ID" in df.columns:
            result["unique_players_or_teams"] = int(df["PLAYER_ID"].nunique())
        elif dataset_name == "team_game" and "TEAM_ID" in df.columns:
            result["unique_players_or_teams"] = int(df["TEAM_ID"].nunique())

        if result["total_rows"] == 0:
            result["issues"].append("Zero rows in dataset")

        if result["unique_games"] == 0:
            result["issues"].append("No unique games found")

    except Exception as exc:  # pragma: no cover - defensive logging
        result["issues"].append(f"Error reading parquet files: {str(exc)[:100]}")

    return result


# ==============================================================================
# PBP/SHOT EVENT VALIDATION HELPERS
# ==============================================================================


def _infer_pbp_key_columns(columns: list[str]) -> list[str] | None:
    """Infer a reasonable key for identifying unique PBP events.

    We try several common patterns and fall back to None if nothing fits.

    Args:
        columns: List of column names in the PBP dataframe

    Returns:
        List of column names that form a unique key, or None if no key can be inferred
    """
    col_set = set(columns)

    candidates: list[list[str]] = [
        ["GAME_ID", "EVENT_ID"],
        ["GAME_ID", "EVENT_NUM"],
        ["GAME_ID", "PERIOD", "GAME_CLOCK", "TEAM_ID", "PLAYER_ID", "EVENT_TYPE"],
    ]

    for candidate in candidates:
        if set(candidate).issubset(col_set):
            return candidate

    return None


def _infer_shot_key_columns(columns: list[str]) -> list[str] | None:
    """Infer a reasonable key for identifying unique shot events.

    Args:
        columns: List of column names in the shots dataframe

    Returns:
        List of column names that form a unique key, or None if no key can be inferred
    """
    col_set = set(columns)

    candidates: list[list[str]] = [
        ["GAME_ID", "SHOT_ID"],
        ["GAME_ID", "PERIOD", "GAME_CLOCK", "PLAYER_ID", "SHOT_RESULT"],
    ]

    for candidate in candidates:
        if set(candidate).issubset(col_set):
            return candidate

    return None


def _count_duplicates(df: pd.DataFrame, key_cols: list[str]) -> int:
    """Count potential duplicate rows based on a set of key columns.

    Args:
        df: DataFrame to check for duplicates
        key_cols: List of column names to use as key

    Returns:
        Number of duplicate rows (all instances, not just extras)
    """
    if not key_cols:
        return 0
    dup_mask = df.duplicated(subset=key_cols, keep=False)
    return int(dup_mask.sum())


# ==============================================================================
# HISTORICAL DATA VALIDATION
# ==============================================================================


def validate_historical_season(season: str) -> dict:
    """Validate historical PBP/shots data for a season.

    Args:
        season: Season string (e.g., "2025-2026")

    Returns:
        Dict with validation results, including fixture-level coverage.
    """
    season_dir = HISTORICAL_ROOT / season

    result: dict[str, object] = {
        "season": season,
        "exists": False,
        "fixtures": {"exists": False, "rows": 0},
        "pbp": {"exists": False, "rows": 0},
        "shots": {"exists": False, "rows": 0},
        # NEW: fixture-level coverage summary
        "coverage": {},
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append("Directory does not exist")
        return result

    result["exists"] = True

    fixtures_df: pd.DataFrame | None = None
    pbp_df: pd.DataFrame | None = None
    shots_df: pd.DataFrame | None = None

    # Fixtures
    fixtures_path = season_dir / "fixtures.parquet"
    if fixtures_path.exists():
        result["fixtures"]["exists"] = True
        try:
            fixtures_df = pd.read_parquet(fixtures_path)
            result["fixtures"]["rows"] = len(fixtures_df)
            result["fixtures"]["columns"] = list(fixtures_df.columns)

            if "GAME_ID" in fixtures_df.columns:
                result["fixtures"]["unique_games"] = int(fixtures_df["GAME_ID"].nunique())
        except Exception as exc:
            result["issues"].append(f"Error reading fixtures: {str(exc)[:50]}")

    # PBP
    pbp_path = season_dir / "pbp_events.parquet"
    if pbp_path.exists():
        result["pbp"]["exists"] = True
        try:
            pbp_df = pd.read_parquet(pbp_path)
            result["pbp"]["rows"] = len(pbp_df)
            result["pbp"]["columns"] = list(pbp_df.columns)

            if "GAME_ID" in pbp_df.columns:
                result["pbp"]["unique_games"] = int(pbp_df["GAME_ID"].nunique())

            # Detect potential duplicate PBP events (report only, no mutation)
            key_cols = _infer_pbp_key_columns(list(pbp_df.columns))
            if key_cols is not None:
                dup_events = _count_duplicates(pbp_df, key_cols)
                if dup_events > 0:
                    result["pbp"]["potential_duplicate_events"] = dup_events
                    result["issues"].append(
                        f"PBP: {dup_events} potential duplicate events based on {key_cols}"
                    )
        except Exception as exc:
            result["issues"].append(f"Error reading PBP: {str(exc)[:50]}")

    # Shots
    shots_path = season_dir / "shots.parquet"
    if shots_path.exists():
        result["shots"]["exists"] = True
        try:
            shots_df = pd.read_parquet(shots_path)
            result["shots"]["rows"] = len(shots_df)
            result["shots"]["columns"] = list(shots_df.columns)

            if "GAME_ID" in shots_df.columns:
                result["shots"]["unique_games"] = int(shots_df["GAME_ID"].nunique())

            key_cols = _infer_shot_key_columns(list(shots_df.columns))
            if key_cols is not None:
                dup_shots = _count_duplicates(shots_df, key_cols)
                if dup_shots > 0:
                    result["shots"]["potential_duplicate_shots"] = dup_shots
                    result["issues"].append(
                        f"Shots: {dup_shots} potential duplicate events based on {key_cols}"
                    )
        except Exception as exc:
            result["issues"].append(f"Error reading shots: {str(exc)[:50]}")

    # Fixture-level coverage summary (only if we have fixtures)
    if fixtures_df is not None and "GAME_ID" in fixtures_df.columns:
        fixtures_game_ids = {
            str(gid) for gid in fixtures_df["GAME_ID"].dropna().astype(str).unique().tolist()
        }
        pbp_game_ids: set[str] = set()
        shots_game_ids: set[str] = set()

        if pbp_df is not None and "GAME_ID" in pbp_df.columns:
            pbp_game_ids = {
                str(gid) for gid in pbp_df["GAME_ID"].dropna().astype(str).unique().tolist()
            }

        if shots_df is not None and "GAME_ID" in shots_df.columns:
            shots_game_ids = {
                str(gid) for gid in shots_df["GAME_ID"].dropna().astype(str).unique().tolist()
            }

        fixtures_with_pbp = fixtures_game_ids & pbp_game_ids
        fixtures_with_shots = fixtures_game_ids & shots_game_ids

        result["coverage"] = {
            "fixtures_total": len(fixtures_game_ids),
            "fixtures_with_pbp": len(fixtures_with_pbp),
            "fixtures_with_shots": len(fixtures_with_shots),
            "fixtures_without_pbp": len(fixtures_game_ids - pbp_game_ids),
            "fixtures_without_shots": len(fixtures_game_ids - shots_game_ids),
        }

        # If there are fixtures without PBP/shots, make that explicit
        if result["coverage"]["fixtures_without_pbp"] > 0:
            result["issues"].append(
                f"{result['coverage']['fixtures_without_pbp']} fixtures lack PBP data"
            )
        if result["coverage"]["fixtures_without_shots"] > 0:
            result["issues"].append(
                f"{result['coverage']['fixtures_without_shots']} fixtures lack shot data"
            )

    return result


# ==============================================================================
# DUPLICATE ANALYSIS
# ==============================================================================


def _analyze_duplicate_games(normalized_results: list[dict]) -> dict:
    """Analyze duplicate games across normalized season folders.

    Returns a dict keyed by dataset ("player_game", "team_game") with:
        - total_unique_games
        - duplicates: list of {game_id, seasons}

    Args:
        normalized_results: List of validation results from validate_normalized_season

    Returns:
        Dict mapping dataset name to duplicate analysis
    """
    per_dataset: dict[str, dict[str, set[str]]] = {}

    for result in normalized_results:
        if not result.get("exists"):
            continue

        dataset = str(result.get("dataset"))
        season = str(result.get("season"))
        game_ids = result.get("game_ids") or []

        if dataset not in per_dataset:
            per_dataset[dataset] = {}

        for game_id in game_ids:
            if game_id not in per_dataset[dataset]:
                per_dataset[dataset][game_id] = set()
            per_dataset[dataset][game_id].add(season)

    analysis: dict[str, dict[str, object]] = {}

    for dataset, game_map in per_dataset.items():
        duplicates: list[dict[str, object]] = []

        for game_id, seasons in game_map.items():
            if len(seasons) > 1:
                duplicates.append(
                    {
                        "game_id": game_id,
                        "seasons": sorted(seasons),
                    }
                )

        analysis[dataset] = {
            "total_unique_games": len(game_map),
            "duplicate_games": duplicates,
        }

    return analysis


# ==============================================================================
# REPORT GENERATION
# ==============================================================================


def generate_validation_report(
    normalized_results: list[dict],
    historical_results: list[dict],
) -> dict:
    """Generate comprehensive validation report.

    Args:
        normalized_results: List of normalized dataset validation results
        historical_results: List of historical dataset validation results

    Returns:
        Complete validation report dict
    """
    report: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "validation_type": "LNB Historical Coverage",
        "normalized_data": {
            "seasons_validated": len({r["season"] for r in normalized_results}),
            "datasets": {},
            # NEW: duplicate analysis across seasons
            "duplicate_analysis": {},
        },
        "historical_data": {
            "seasons_validated": len(historical_results),
            "results": historical_results,
        },
        "summary": {
            "total_seasons_covered": 0,
            "total_games": 0,  # optional: can be used later if you want
            "total_player_game_records": 0,
            "total_team_game_records": 0,
            "total_pbp_events": 0,
            "total_shots": 0,
            # NEW: global unique game counts per dataset
            "unique_games_by_dataset": {},
            "issues_found": [],
        },
    }

    # Group normalized results by dataset type
    for result in normalized_results:
        dataset = result["dataset"]
        if dataset not in report["normalized_data"]["datasets"]:
            report["normalized_data"]["datasets"][dataset] = []
        report["normalized_data"]["datasets"][dataset].append(result)

    seasons_covered: set[str] = set()

    # Aggregate normalized data
    for result in normalized_results:
        if result["exists"] and result["total_rows"] > 0:
            seasons_covered.add(str(result["season"]))

            if result["dataset"] == "player_game":
                report["summary"]["total_player_game_records"] += result["total_rows"]  # type: ignore[operator]
            elif result["dataset"] == "team_game":
                report["summary"]["total_team_game_records"] += result["total_rows"]  # type: ignore[operator]

            if result["issues"]:
                for issue in result["issues"]:
                    report["summary"]["issues_found"].append(
                        f"{result['dataset']} {result['season']}: {issue}"
                    )

    # Aggregate historical data
    for result in historical_results:
        if result["exists"]:
            seasons_covered.add(str(result["season"]))

            pbp = result.get("pbp") or {}
            shots = result.get("shots") or {}

            if pbp.get("exists"):
                report["summary"]["total_pbp_events"] += pbp.get("rows", 0)  # type: ignore[operator]
            if shots.get("exists"):
                report["summary"]["total_shots"] += shots.get("rows", 0)  # type: ignore[operator]

            if result["issues"]:
                for issue in result["issues"]:
                    report["summary"]["issues_found"].append(
                        f"Historical {result['season']}: {issue}"
                    )

    report["summary"]["total_seasons_covered"] = len(seasons_covered)

    # Analyze duplicates across seasons for normalized data
    duplicate_analysis = _analyze_duplicate_games(normalized_results)
    report["normalized_data"]["duplicate_analysis"] = duplicate_analysis

    # Fill summary.unique_games_by_dataset and add issues for duplicates
    unique_by_dataset: dict[str, int] = {}
    for dataset, stats in duplicate_analysis.items():
        unique_by_dataset[dataset] = int(stats["total_unique_games"])
        duplicate_games = stats["duplicate_games"]
        if duplicate_games:
            for entry in duplicate_games:
                game_id = entry["game_id"]
                seasons = ", ".join(entry["seasons"])
                report["summary"]["issues_found"].append(
                    f"Duplicate {dataset} game {game_id} appears in seasons: {seasons}"
                )

    report["summary"]["unique_games_by_dataset"] = unique_by_dataset

    return report


def print_validation_report(report: dict) -> None:
    """Print human-readable validation report."""
    print("=" * 80)
    print("LNB PRO A - DATA COVERAGE VALIDATION REPORT")
    print("=" * 80)
    print(f"Generated: {report['generated_at']}")
    print()

    # Normalized Data Section
    print("=" * 80)
    print("NORMALIZED DATA (BOX SCORES)")
    print("=" * 80)
    print()

    for dataset_name, results in report["normalized_data"]["datasets"].items():
        print(f"{dataset_name.upper()}:")
        print(f"{'Season':<15} {'Rows':<10} {'Games':<8} {'Players/Teams':<15} {'Status'}")
        print("-" * 80)

        for r in results:
            if r["exists"]:
                status = "✅ Valid" if not r["issues"] else f"⚠️ {len(r['issues'])} issues"
                print(
                    f"{r['season']:<15} "
                    f"{r['total_rows']:<10} "
                    f"{r['unique_games']:<8} "
                    f"{r['unique_players_or_teams']:<15} "
                    f"{status}"
                )
                if r["null_counts"]:
                    print(f"  └─ Null values: {r['null_counts']}")
            else:
                print(f"{r['season']:<15} {'N/A':<10} {'N/A':<8} {'N/A':<15} ❌ Missing")

        print()

    # Duplicate analysis summary
    duplicate_analysis = report["normalized_data"].get("duplicate_analysis", {})
    if duplicate_analysis:
        print("-" * 80)
        print("GLOBAL UNIQUE GAME COUNTS (NORMALIZED)")
        print("-" * 80)
        for dataset, stats in duplicate_analysis.items():
            total_unique = stats["total_unique_games"]
            duplicates = stats["duplicate_games"]
            print(f"{dataset}: {total_unique} unique games")
            if duplicates:
                print(f"  Duplicates ({len(duplicates)}):")
                for entry in duplicates:
                    game_id = entry["game_id"]
                    seasons = ", ".join(entry["seasons"])
                    print(f"    • {game_id} in seasons [{seasons}]")
        print()

    # Historical Data Section
    print("=" * 80)
    print("HISTORICAL DATA (PBP & SHOTS)")
    print("=" * 80)
    print()

    for r in report["historical_data"]["results"]:
        print(f"Season: {r['season']}")

        if r["exists"]:
            fixtures = r["fixtures"]
            pbp = r["pbp"]
            shots = r["shots"]
            coverage = r.get("coverage") or {}

            print(
                f"  Fixtures:   {'✅' if fixtures['exists'] else '❌'} "
                f"{fixtures.get('rows', 0)} rows"
            )
            print(f"  PBP Events: {'✅' if pbp['exists'] else '❌'} {pbp.get('rows', 0)} events")
            print(f"  Shots:      {'✅' if shots['exists'] else '❌'} {shots.get('rows', 0)} shots")

            if coverage:
                print(
                    f"  Coverage: {coverage.get('fixtures_total', 0)} fixtures | "
                    f"{coverage.get('fixtures_with_pbp', 0)} with PBP | "
                    f"{coverage.get('fixtures_with_shots', 0)} with shots | "
                    f"{coverage.get('fixtures_without_pbp', 0)} without PBP | "
                    f"{coverage.get('fixtures_without_shots', 0)} without shots"
                )

            if r["issues"]:
                print(f"  Issues: {', '.join(r['issues'])}")
        else:
            print("  ❌ Directory not found")

        print()

    # Summary Section
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    summary = report["summary"]
    print(f"Total seasons covered: {summary['total_seasons_covered']}")
    print(f"Total player-game records: {summary['total_player_game_records']:,}")
    print(f"Total team-game records: {summary['total_team_game_records']:,}")
    print(f"Total PBP events: {summary['total_pbp_events']:,}")
    print(f"Total shots: {summary['total_shots']:,}")

    unique_games_by_dataset = summary.get("unique_games_by_dataset") or {}
    if unique_games_by_dataset:
        print()
        print("Unique games (normalized) by dataset:")
        for dataset, count in unique_games_by_dataset.items():
            print(f"  {dataset}: {count} unique games")

    print()

    if summary["issues_found"]:
        print("⚠️ ISSUES FOUND:")
        for issue in summary["issues_found"]:
            print(f"  • {issue}")
    else:
        print("✅ No data quality issues detected")

    print()


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    """Main validation workflow"""
    print("Starting LNB coverage validation...\n")

    # Validate normalized data
    normalized_results = []

    for dataset in ["player_game", "team_game"]:
        for season in SEASONS_TO_VALIDATE:
            print(f"Validating {dataset} {season}...", end=" ")
            result = validate_normalized_season(dataset, season)
            normalized_results.append(result)

            if result["exists"]:
                print(f"✅ {result['total_rows']} rows")
            else:
                print("❌ Missing")

    # Validate historical data
    historical_results = []

    for season in HISTORICAL_SEASONS:
        print(f"\nValidating historical {season}...", end=" ")
        result = validate_historical_season(season)
        historical_results.append(result)

        if result["exists"]:
            print("✅ Found")
        else:
            print("❌ Missing")

    # Generate report
    print("\nGenerating validation report...")
    report = generate_validation_report(normalized_results, historical_results)

    # Save JSON report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "coverage_validation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON report saved: {json_path}")

    # Print report
    print()
    print_validation_report(report)

    # Save text report
    txt_path = OUTPUT_DIR / "coverage_validation_report.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        original_stdout = sys.stdout
        sys.stdout = f
        print_validation_report(report)
        sys.stdout = original_stdout
    print(f"✅ Text report saved: {txt_path}")

    print()
    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
