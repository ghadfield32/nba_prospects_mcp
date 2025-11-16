#!/usr/bin/env python3
"""Validate existing LNB historical data coverage

This script validates the integrity and coverage of existing LNB data:
- Normalized box scores (2021-2025): player_game, team_game
- Historical PBP/shots (2025-2026): pbp_events, shots
- Raw schedule data

Purpose:
    - Verify data integrity (row counts, schemas, null values)
    - Document actual coverage by season
    - Identify data quality issues
    - Generate validation report

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
    """Validate a normalized dataset for a specific season

    Args:
        dataset_name: "player_game" or "team_game"
        season: Season string (e.g., "2021-2022")

    Returns:
        Dict with validation results
    """
    season_dir = NORMALIZED_ROOT / dataset_name / f"season={season}"

    result = {
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
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append("Directory does not exist")
        return result

    result["exists"] = True

    # Find all parquet files
    parquet_files = list(season_dir.glob("*.parquet"))
    result["file_count"] = len(parquet_files)

    if not parquet_files:
        result["issues"].append("No parquet files found")
        return result

    # Read all files into single dataframe
    try:
        df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)

        result["total_rows"] = len(df)
        result["columns"] = list(df.columns)
        result["column_count"] = len(df.columns)

        # Check for nulls in key columns
        key_cols = ["GAME_ID", "GAME_DATE", "SEASON"]
        if dataset_name == "player_game":
            key_cols.extend(["PLAYER_ID", "PLAYER_NAME", "PTS", "REB", "AST"])
        else:  # team_game
            key_cols.extend(["TEAM_ID", "PTS", "FG_PCT"])

        for col in key_cols:
            if col in df.columns:
                null_count = int(df[col].isna().sum())
                if null_count > 0:
                    result["null_counts"][col] = null_count

        # Extract metadata
        if "GAME_DATE" in df.columns:
            dates = pd.to_datetime(df["GAME_DATE"], errors="coerce").dropna()
            if not dates.empty:
                result["date_range"] = {
                    "earliest": dates.min().isoformat(),
                    "latest": dates.max().isoformat(),
                }

        if "GAME_ID" in df.columns:
            result["unique_games"] = int(df["GAME_ID"].nunique())

        if dataset_name == "player_game" and "PLAYER_ID" in df.columns:
            result["unique_players_or_teams"] = int(df["PLAYER_ID"].nunique())
        elif dataset_name == "team_game" and "TEAM_ID" in df.columns:
            result["unique_players_or_teams"] = int(df["TEAM_ID"].nunique())

        # Data quality checks
        if result["total_rows"] == 0:
            result["issues"].append("Zero rows in dataset")

        if result["unique_games"] == 0:
            result["issues"].append("No unique games found")

    except Exception as e:
        result["issues"].append(f"Error reading parquet files: {str(e)[:100]}")

    return result


def validate_historical_season(season: str) -> dict:
    """Validate historical PBP/shots data for a season

    Args:
        season: Season string (e.g., "2025-2026")

    Returns:
        Dict with validation results
    """
    season_dir = HISTORICAL_ROOT / season

    result = {
        "season": season,
        "exists": False,
        "fixtures": {"exists": False, "rows": 0},
        "pbp": {"exists": False, "rows": 0},
        "shots": {"exists": False, "rows": 0},
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append("Directory does not exist")
        return result

    result["exists"] = True

    # Check fixtures
    fixtures_path = season_dir / "fixtures.parquet"
    if fixtures_path.exists():
        result["fixtures"]["exists"] = True
        try:
            df = pd.read_parquet(fixtures_path)
            result["fixtures"]["rows"] = len(df)
            result["fixtures"]["columns"] = list(df.columns)

            if "GAME_ID" in df.columns:
                result["fixtures"]["unique_games"] = int(df["GAME_ID"].nunique())
        except Exception as e:
            result["issues"].append(f"Error reading fixtures: {str(e)[:50]}")

    # Check PBP
    pbp_path = season_dir / "pbp_events.parquet"
    if pbp_path.exists():
        result["pbp"]["exists"] = True
        try:
            df = pd.read_parquet(pbp_path)
            result["pbp"]["rows"] = len(df)
            result["pbp"]["columns"] = list(df.columns)

            if "GAME_ID" in df.columns:
                result["pbp"]["unique_games"] = int(df["GAME_ID"].nunique())
        except Exception as e:
            result["issues"].append(f"Error reading PBP: {str(e)[:50]}")

    # Check shots
    shots_path = season_dir / "shots.parquet"
    if shots_path.exists():
        result["shots"]["exists"] = True
        try:
            df = pd.read_parquet(shots_path)
            result["shots"]["rows"] = len(df)
            result["shots"]["columns"] = list(df.columns)

            if "GAME_ID" in df.columns:
                result["shots"]["unique_games"] = int(df["GAME_ID"].nunique())
        except Exception as e:
            result["issues"].append(f"Error reading shots: {str(e)[:50]}")

    return result


def generate_validation_report(
    normalized_results: list[dict], historical_results: list[dict]
) -> dict:
    """Generate comprehensive validation report

    Args:
        normalized_results: List of normalized dataset validation results
        historical_results: List of historical dataset validation results

    Returns:
        Complete validation report dict
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "validation_type": "LNB Historical Coverage",
        "normalized_data": {
            "seasons_validated": len({r["season"] for r in normalized_results}),
            "datasets": {},
        },
        "historical_data": {
            "seasons_validated": len(historical_results),
            "results": historical_results,
        },
        "summary": {
            "total_seasons_covered": 0,
            "total_games": 0,
            "total_player_game_records": 0,
            "total_team_game_records": 0,
            "total_pbp_events": 0,
            "total_shots": 0,
            "issues_found": [],
        },
    }

    # Group normalized results by dataset type
    for result in normalized_results:
        dataset = result["dataset"]
        if dataset not in report["normalized_data"]["datasets"]:
            report["normalized_data"]["datasets"][dataset] = []
        report["normalized_data"]["datasets"][dataset].append(result)

    # Calculate summary statistics
    seasons_covered = set()

    # From normalized data
    for result in normalized_results:
        if result["exists"] and result["total_rows"] > 0:
            seasons_covered.add(result["season"])

            if result["dataset"] == "player_game":
                report["summary"]["total_player_game_records"] += result["total_rows"]
            elif result["dataset"] == "team_game":
                report["summary"]["total_team_game_records"] += result["total_rows"]

            if result["issues"]:
                for issue in result["issues"]:
                    report["summary"]["issues_found"].append(
                        f"{result['dataset']} {result['season']}: {issue}"
                    )

    # From historical data
    for result in historical_results:
        if result["exists"]:
            seasons_covered.add(result["season"])

            if result["pbp"]["exists"]:
                report["summary"]["total_pbp_events"] += result["pbp"]["rows"]

            if result["shots"]["exists"]:
                report["summary"]["total_shots"] += result["shots"]["rows"]

            if result["issues"]:
                for issue in result["issues"]:
                    report["summary"]["issues_found"].append(
                        f"Historical {result['season']}: {issue}"
                    )

    report["summary"]["total_seasons_covered"] = len(seasons_covered)

    return report


def print_validation_report(report: dict) -> None:
    """Print human-readable validation report

    Args:
        report: Validation report dictionary
    """
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

                # Show null counts if any
                if r["null_counts"]:
                    print(f"  └─ Null values: {r['null_counts']}")
            else:
                print(f"{r['season']:<15} {'N/A':<10} {'N/A':<8} {'N/A':<15} ❌ Missing")

        print()

    # Historical Data Section
    print("=" * 80)
    print("HISTORICAL DATA (PBP & SHOTS)")
    print("=" * 80)
    print()

    for r in report["historical_data"]["results"]:
        print(f"Season: {r['season']}")

        if r["exists"]:
            print(
                f"  Fixtures:   {'✅' if r['fixtures']['exists'] else '❌'} "
                f"{r['fixtures'].get('rows', 0)} rows"
            )
            print(
                f"  PBP Events: {'✅' if r['pbp']['exists'] else '❌'} "
                f"{r['pbp'].get('rows', 0)} events"
            )
            print(
                f"  Shots:      {'✅' if r['shots']['exists'] else '❌'} "
                f"{r['shots'].get('rows', 0)} shots"
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
    print()

    if summary["issues_found"]:
        print("⚠️ ISSUES FOUND:")
        for issue in summary["issues_found"]:
            print(f"  • {issue}")
    else:
        print("✅ No data quality issues detected")

    print()


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
