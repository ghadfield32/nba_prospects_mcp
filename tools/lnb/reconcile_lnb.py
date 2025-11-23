#!/usr/bin/env python3
"""Comprehensive Reconciliation Gate for All LNB Leagues

Validates data quality and completeness across all leagues and seasons.

Invariants checked:
1. Coverage: Expected game counts per league/season
2. Correctness: No duplicates, valid dates, proper league assignment
3. Schema: Required columns present, valid data types
4. Reconciliation: Index ↔ Raw files (PBP/Shots) alignment
5. Curated Layer: Index ↔ Curated datasets alignment
6. Cross-league collision: No game_id appears in multiple leagues

Usage:
    python tools/lnb/reconcile_lnb.py
    python tools/lnb/reconcile_lnb.py --season 2023-2024
    python tools/lnb/reconcile_lnb.py --league betclic_elite
    python tools/lnb/reconcile_lnb.py --json-output results.json
"""

import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Expected game counts per league/season (complete seasons only)
EXPECTED_GAMES = {
    ("2021-2022", "elite_2"): 306,
    ("2022-2023", "betclic_elite"): 306,
    ("2022-2023", "elite_2"): 306,
    ("2023-2024", "betclic_elite"): 240,
    ("2023-2024", "espoirs_elite"): 240,
    ("2023-2024", "espoirs_prob"): 260,
}

# Expected date ranges per season (for validation, not strict enforcement)
EXPECTED_DATE_RANGES = {
    "2021-2022": ("2021-09-01", "2022-06-30"),
    "2022-2023": ("2022-09-01", "2023-06-30"),
    "2023-2024": ("2023-09-01", "2024-06-30"),
    "2024-2025": ("2024-09-01", "2025-06-30"),
}

# Schema requirements
REQUIRED_INDEX_COLUMNS = {
    "season",
    "league",
    "competition",
    "game_id",
    "game_date",
    "home_team_name",
    "away_team_name",
    "has_pbp",
    "has_shots",
}

REQUIRED_PBP_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "HOME_SCORE",
    "AWAY_SCORE",
}

REQUIRED_SHOTS_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
}


class ReconciliationError(Exception):
    """Raised when reconciliation invariant fails"""

    pass


def convert_to_json_serializable(obj):
    """Convert numpy/pandas types to native Python types for JSON serialization

    Args:
        obj: Object to convert (can be nested dict/list)

    Returns:
        JSON-serializable version of the object
    """
    import numpy as np

    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    return obj


def load_game_index(
    season_filter: str | None = None, league_filter: str | None = None
) -> pd.DataFrame:
    """Load game index with optional filters"""
    index_path = Path("data/raw/lnb/lnb_game_index.parquet")
    if not index_path.exists():
        raise ReconciliationError(f"Game index not found: {index_path}")

    df = pd.read_parquet(index_path)

    # Apply filters
    if season_filter:
        df = df[df["season"] == season_filter]
    if league_filter:
        df = df[df["league"] == league_filter]

    return df


def check_coverage(index_df: pd.DataFrame, season: str, league: str) -> dict[str, any]:
    """Check coverage for a specific season/league combination"""
    results = {"season": season, "league": league, "checks": {}}

    # Get subset for this season/league
    subset = index_df[(index_df["season"] == season) & (index_df["league"] == league)]

    if len(subset) == 0:
        results["checks"]["games_found"] = {"status": "skip", "message": "No games"}
        return results

    # Check game count if we have expectations
    key = (season, league)
    if key in EXPECTED_GAMES:
        expected_count = EXPECTED_GAMES[key]
        actual_count = len(subset)
        status = "pass" if actual_count == expected_count else "fail"
        results["checks"]["game_count"] = {
            "status": status,
            "expected": expected_count,
            "actual": actual_count,
        }
    else:
        # In-progress or unknown season
        results["checks"]["game_count"] = {
            "status": "skip",
            "actual": len(subset),
            "message": "No expectations for this season/league",
        }

    # Check PBP coverage
    pbp_coverage = subset["has_pbp"].sum()
    pbp_pct = pbp_coverage / len(subset) * 100 if len(subset) > 0 else 0
    pbp_complete = pbp_coverage == len(subset)

    results["checks"]["pbp_coverage"] = {
        "status": "pass" if pbp_complete else "warn",
        "coverage": pbp_coverage,
        "total": len(subset),
        "percentage": round(pbp_pct, 1),
    }

    # Check shots coverage
    shots_coverage = subset["has_shots"].sum()
    shots_pct = shots_coverage / len(subset) * 100 if len(subset) > 0 else 0
    shots_complete = shots_coverage == len(subset)

    results["checks"]["shots_coverage"] = {
        "status": "pass" if shots_complete else "warn",
        "coverage": shots_coverage,
        "total": len(subset),
        "percentage": round(shots_pct, 1),
    }

    return results


def check_correctness(index_df: pd.DataFrame) -> dict[str, any]:
    """Check data correctness across entire index"""
    results = {"checks": {}}

    # Check for duplicate game IDs
    duplicates = index_df[index_df["game_id"].duplicated()]
    results["checks"]["no_duplicates"] = {
        "status": "pass" if len(duplicates) == 0 else "fail",
        "duplicates_found": len(duplicates),
    }

    if len(duplicates) > 0:
        results["checks"]["no_duplicates"]["sample_ids"] = list(duplicates["game_id"].head(5))

    # Check cross-league collision (game_id should map to exactly one league)
    game_league_counts = index_df.groupby("game_id")["league"].nunique().reset_index()
    collisions = game_league_counts[game_league_counts["league"] > 1]

    results["checks"]["no_cross_league_collision"] = {
        "status": "pass" if len(collisions) == 0 else "fail",
        "collisions_found": len(collisions),
    }

    if len(collisions) > 0:
        results["checks"]["no_cross_league_collision"]["sample_ids"] = list(
            collisions["game_id"].head(5)
        )

    # Check date validity per season
    date_checks = []
    for season in index_df["season"].unique():
        season_df = index_df[index_df["season"] == season]

        # Convert game_date to datetime if needed
        if season_df["game_date"].dtype == "object":
            season_df = season_df.copy()
            season_df["game_date"] = pd.to_datetime(season_df["game_date"], errors="coerce")

        # Check for null dates
        null_dates = season_df["game_date"].isna().sum()

        # Check date range
        if season in EXPECTED_DATE_RANGES and null_dates < len(season_df):
            min_date, max_date = EXPECTED_DATE_RANGES[season]
            actual_min = season_df["game_date"].min()
            actual_max = season_df["game_date"].max()

            in_range = pd.to_datetime(min_date) <= actual_min and actual_max <= pd.to_datetime(
                max_date
            )

            date_checks.append(
                {
                    "season": season,
                    "status": "pass" if in_range and null_dates == 0 else "warn",
                    "min_date": str(actual_min.date()) if pd.notna(actual_min) else None,
                    "max_date": str(actual_max.date()) if pd.notna(actual_max) else None,
                    "null_dates": null_dates,
                }
            )

    results["checks"]["date_validity"] = {"seasons": date_checks}

    return results


def check_schema(index_df: pd.DataFrame) -> dict[str, any]:
    """Check schema requirements"""
    results = {"checks": {}}

    # Check index columns
    missing_cols = REQUIRED_INDEX_COLUMNS - set(index_df.columns)
    results["checks"]["index_columns"] = {
        "status": "pass" if len(missing_cols) == 0 else "fail",
        "missing": list(missing_cols) if missing_cols else [],
    }

    # Check data types
    type_checks = {}
    for col in ["has_pbp", "has_shots", "has_boxscore"]:
        if col in index_df.columns:
            actual_type = str(index_df[col].dtype)
            type_checks[col] = {
                "expected": "bool",
                "actual": actual_type,
                "status": "pass" if "bool" in actual_type else "warn",
            }

    results["checks"]["data_types"] = type_checks

    # Sample PBP files across different seasons
    pbp_schema_checks = []
    for season in index_df["season"].unique():
        pbp_dir = Path(f"data/raw/lnb/pbp/season={season}")
        if pbp_dir.exists():
            pbp_files = list(pbp_dir.glob("*.parquet"))
            if pbp_files:
                sample_pbp = pd.read_parquet(pbp_files[0])
                missing_pbp_cols = REQUIRED_PBP_COLUMNS - set(sample_pbp.columns)
                pbp_schema_checks.append(
                    {
                        "season": season,
                        "status": "pass" if len(missing_pbp_cols) == 0 else "fail",
                        "missing": list(missing_pbp_cols) if missing_pbp_cols else [],
                        "sample_file": pbp_files[0].name,
                    }
                )

    results["checks"]["pbp_schema"] = pbp_schema_checks

    # Sample shots files across different seasons
    shots_schema_checks = []
    for season in index_df["season"].unique():
        shots_dir = Path(f"data/raw/lnb/shots/season={season}")
        if shots_dir.exists():
            shots_files = list(shots_dir.glob("*.parquet"))
            if shots_files:
                sample_shots = pd.read_parquet(shots_files[0])
                missing_shots_cols = REQUIRED_SHOTS_COLUMNS - set(sample_shots.columns)
                shots_schema_checks.append(
                    {
                        "season": season,
                        "status": "pass" if len(missing_shots_cols) == 0 else "fail",
                        "missing": (list(missing_shots_cols) if missing_shots_cols else []),
                        "sample_file": shots_files[0].name,
                    }
                )

    results["checks"]["shots_schema"] = shots_schema_checks

    return results


def check_reconciliation(index_df: pd.DataFrame, season: str, league: str) -> dict[str, any]:
    """Check reconciliation for a specific season/league"""
    results = {"season": season, "league": league, "checks": {}}

    subset = index_df[(index_df["season"] == season) & (index_df["league"] == league)]

    if len(subset) == 0:
        results["checks"]["reconciliation"] = {
            "status": "skip",
            "message": "No games",
        }
        return results

    indexed_games = set(subset["game_id"])

    # Get PBP game IDs
    pbp_dir = Path(f"data/raw/lnb/pbp/season={season}")
    pbp_games = set()
    if pbp_dir.exists():
        for pbp_file in pbp_dir.glob("*.parquet"):
            game_id = pbp_file.stem.replace("game_id=", "")
            pbp_games.add(game_id)

    # Get shots game IDs
    shots_dir = Path(f"data/raw/lnb/shots/season={season}")
    shots_games = set()
    if shots_dir.exists():
        for shots_file in shots_dir.glob("*.parquet"):
            game_id = shots_file.stem.replace("game_id=", "")
            shots_games.add(game_id)

    # Check alignment
    missing_pbp = indexed_games - pbp_games
    missing_shots = indexed_games - shots_games
    orphaned_pbp = pbp_games - indexed_games
    orphaned_shots = shots_games - indexed_games

    results["checks"]["pbp_alignment"] = {
        "status": "pass" if len(missing_pbp) == 0 else "warn",
        "missing": len(missing_pbp),
        "orphaned": len(orphaned_pbp),
    }

    results["checks"]["shots_alignment"] = {
        "status": "pass" if len(missing_shots) == 0 else "warn",
        "missing": len(missing_shots),
        "orphaned": len(orphaned_shots),
    }

    return results


def check_curated_layer(index_df: pd.DataFrame, season: str) -> dict[str, any]:
    """Check curated datasets match index expectations for a season

    Validates:
    1. Curated PBP exists if index has games with has_pbp=True
    2. Curated Shots exists if index has games with has_shots=True
    3. Game counts in curated match index expectations
    4. No duplicate game_ids in curated datasets
    5. Quality reports exist and are accurate
    """
    results = {"season": season, "checks": {}}

    season_df = index_df[index_df["season"] == season]

    if len(season_df) == 0:
        results["checks"]["curated_validation"] = {
            "status": "skip",
            "message": "No games in index for this season",
        }
        return results

    # Check PBP curated dataset
    pbp_expected = (season_df["has_pbp"] == True).sum()  # noqa: E712
    pbp_curated_dir = Path(f"data/curated/lnb/pbp/season={season}")
    pbp_curated_file = pbp_curated_dir / "lnb_pbp.parquet"

    if pbp_expected > 0:
        if pbp_curated_dir.exists() and pbp_curated_file.exists():
            try:
                # Load curated PBP
                curated_pbp_df = pd.read_parquet(pbp_curated_file)

                # Check game count
                curated_game_ids = set(curated_pbp_df["GAME_ID"].unique())
                index_game_ids = set(season_df[season_df["has_pbp"] == True]["game_id"])  # noqa: E712

                missing_games = index_game_ids - curated_game_ids
                extra_games = curated_game_ids - index_game_ids

                # Check for metadata inconsistencies (game_id appearing in multiple leagues)
                # Group by GAME_ID and check if each has unique league/season
                metadata_check = curated_pbp_df.groupby("GAME_ID").agg(
                    {"league": "nunique", "season": "nunique"}
                )
                metadata_issues = (
                    (metadata_check["league"] > 1) | (metadata_check["season"] > 1)
                ).sum()

                results["checks"]["pbp_curated"] = {
                    "status": "pass"
                    if len(missing_games) == 0 and len(extra_games) == 0 and metadata_issues == 0
                    else "fail",
                    "expected_games": len(index_game_ids),
                    "actual_games": len(curated_game_ids),
                    "missing_games": len(missing_games),
                    "extra_games": len(extra_games),
                    "metadata_inconsistencies": int(metadata_issues),
                    "total_rows": len(curated_pbp_df),
                }
            except Exception as e:
                results["checks"]["pbp_curated"] = {"status": "fail", "error": str(e)}
        else:
            results["checks"]["pbp_curated"] = {
                "status": "fail",
                "expected_games": pbp_expected,
                "message": "Curated PBP dataset not found",
            }
    else:
        results["checks"]["pbp_curated"] = {
            "status": "skip",
            "message": "No PBP games expected in index",
        }

    # Check Shots curated dataset
    shots_expected = (season_df["has_shots"] == True).sum()  # noqa: E712
    shots_curated_dir = Path(f"data/curated/lnb/shots/season={season}")
    shots_curated_file = shots_curated_dir / "lnb_shots.parquet"

    if shots_expected > 0:
        if shots_curated_dir.exists() and shots_curated_file.exists():
            try:
                # Load curated Shots
                curated_shots_df = pd.read_parquet(shots_curated_file)

                # Check game count
                curated_game_ids = set(curated_shots_df["GAME_ID"].unique())
                index_game_ids = set(season_df[season_df["has_shots"] == True]["game_id"])  # noqa: E712

                missing_games = index_game_ids - curated_game_ids
                extra_games = curated_game_ids - index_game_ids

                # Check for metadata inconsistencies (game_id appearing in multiple leagues)
                # Group by GAME_ID and check if each has unique league/season
                metadata_check = curated_shots_df.groupby("GAME_ID").agg(
                    {"league": "nunique", "season": "nunique"}
                )
                metadata_issues = (
                    (metadata_check["league"] > 1) | (metadata_check["season"] > 1)
                ).sum()

                results["checks"]["shots_curated"] = {
                    "status": "pass"
                    if len(missing_games) == 0 and len(extra_games) == 0 and metadata_issues == 0
                    else "fail",
                    "expected_games": len(index_game_ids),
                    "actual_games": len(curated_game_ids),
                    "missing_games": len(missing_games),
                    "extra_games": len(extra_games),
                    "metadata_inconsistencies": int(metadata_issues),
                    "total_rows": len(curated_shots_df),
                }
            except Exception as e:
                results["checks"]["shots_curated"] = {"status": "fail", "error": str(e)}
        else:
            results["checks"]["shots_curated"] = {
                "status": "fail",
                "expected_games": shots_expected,
                "message": "Curated Shots dataset not found",
            }
    else:
        results["checks"]["shots_curated"] = {
            "status": "skip",
            "message": "No Shots games expected in index",
        }

    # Check quality reports
    reports_dir = Path(f"data/curated/lnb/reports/season={season}")
    pbp_report_file = reports_dir / "pbp_quality_report.json"
    shots_report_file = reports_dir / "shots_quality_report.json"

    report_checks = {}

    # PBP quality report
    if pbp_expected > 0:
        if pbp_report_file.exists():
            try:
                with open(pbp_report_file, encoding="utf-8") as f:
                    pbp_report = json.load(f)
                report_checks["pbp_report"] = {
                    "status": "pass",
                    "exists": True,
                    "valid_games": pbp_report.get("valid_games", 0),
                    "quarantined_games": pbp_report.get("quarantined_games", 0),
                }
            except Exception as e:
                report_checks["pbp_report"] = {
                    "status": "warn",
                    "exists": True,
                    "error": f"Failed to parse: {str(e)}",
                }
        else:
            report_checks["pbp_report"] = {
                "status": "warn",
                "exists": False,
                "message": "Quality report not found",
            }

    # Shots quality report
    if shots_expected > 0:
        if shots_report_file.exists():
            try:
                with open(shots_report_file, encoding="utf-8") as f:
                    shots_report = json.load(f)
                report_checks["shots_report"] = {
                    "status": "pass",
                    "exists": True,
                    "valid_games": shots_report.get("valid_games", 0),
                    "quarantined_games": shots_report.get("quarantined_games", 0),
                }
            except Exception as e:
                report_checks["shots_report"] = {
                    "status": "warn",
                    "exists": True,
                    "error": f"Failed to parse: {str(e)}",
                }
        else:
            report_checks["shots_report"] = {
                "status": "warn",
                "exists": False,
                "message": "Quality report not found",
            }

    results["checks"]["quality_reports"] = report_checks

    return results


def print_results(results: dict, verbose: bool = True):
    """Print reconciliation results in human-readable format"""
    print("\n" + "=" * 80)
    print("  LNB RECONCILIATION GATE - ALL LEAGUES")
    print("=" * 80)

    # Overall summary
    total_checks = 0
    passed_checks = 0
    failed_checks = 0
    warned_checks = 0

    def count_status(check_dict):
        nonlocal total_checks, passed_checks, failed_checks, warned_checks
        if isinstance(check_dict, dict):
            if "status" in check_dict:
                total_checks += 1
                if check_dict["status"] == "pass":
                    passed_checks += 1
                elif check_dict["status"] == "fail":
                    failed_checks += 1
                elif check_dict["status"] == "warn":
                    warned_checks += 1
            for value in check_dict.values():
                if isinstance(value, (dict, list)):
                    count_status(value)
        elif isinstance(check_dict, list):
            for item in check_dict:
                count_status(item)

    count_status(results)

    # Print correctness checks
    if "correctness" in results:
        print("\n" + "=" * 80)
        print("  GLOBAL CORRECTNESS CHECKS")
        print("=" * 80)

        for check_name, check_data in results["correctness"]["checks"].items():
            if isinstance(check_data, dict) and "status" in check_data:
                status_icon = (
                    "✅"
                    if check_data["status"] == "pass"
                    else "❌"
                    if check_data["status"] == "fail"
                    else "⚠️"
                )
                print(f"\n{status_icon} {check_name.replace('_', ' ').title()}")
                if verbose:
                    for key, value in check_data.items():
                        if key != "status":
                            print(f"    {key}: {value}")

    # Print schema checks
    if "schema" in results:
        print("\n" + "=" * 80)
        print("  SCHEMA VALIDATION")
        print("=" * 80)

        for check_name, check_data in results["schema"]["checks"].items():
            if isinstance(check_data, dict) and "status" in check_data:
                status_icon = (
                    "✅"
                    if check_data["status"] == "pass"
                    else "❌"
                    if check_data["status"] == "fail"
                    else "⚠️"
                )
                print(f"\n{status_icon} {check_name.replace('_', ' ').title()}")
            elif isinstance(check_data, list):
                print(f"\n{check_name.replace('_', ' ').title()}:")
                for item in check_data:
                    status_icon = (
                        "✅"
                        if item.get("status") == "pass"
                        else "❌"
                        if item.get("status") == "fail"
                        else "⚠️"
                    )
                    print(f"  {status_icon} {item.get('season', 'unknown')}")
                    if verbose and item.get("missing"):
                        print(f"      Missing: {item['missing']}")

    # Print coverage by season/league
    if "coverage" in results:
        print("\n" + "=" * 80)
        print("  COVERAGE BY SEASON × LEAGUE")
        print("=" * 80)

        for item in results["coverage"]:
            season = item["season"]
            league = item["league"]
            print(f"\n{season} / {league}:")

            for check_name, check_data in item["checks"].items():
                if "status" in check_data:
                    status_icon = (
                        "✅"
                        if check_data["status"] == "pass"
                        else "❌"
                        if check_data["status"] == "fail"
                        else "⚠️"
                        if check_data["status"] == "warn"
                        else "⏭️"
                    )
                    if check_name == "game_count":
                        if "expected" in check_data:
                            print(
                                f"  {status_icon} Games: {check_data['actual']}/{check_data['expected']}"
                            )
                        else:
                            print(
                                f"  {status_icon} Games: {check_data['actual']} (no expectations)"
                            )
                    elif check_name in ["pbp_coverage", "shots_coverage"]:
                        data_type = "PBP" if "pbp" in check_name else "Shots"
                        print(
                            f"  {status_icon} {data_type}: {check_data['coverage']}/{check_data['total']} ({check_data['percentage']}%)"
                        )

    # Print reconciliation results
    if "reconciliation" in results:
        print("\n" + "=" * 80)
        print("  RECONCILIATION (INDEX ↔ DISK)")
        print("=" * 80)

        for item in results["reconciliation"]:
            season = item["season"]
            league = item["league"]
            print(f"\n{season} / {league}:")

            for check_name, check_data in item["checks"].items():
                if "status" in check_data:
                    status_icon = (
                        "✅"
                        if check_data["status"] == "pass"
                        else "❌"
                        if check_data["status"] == "fail"
                        else "⚠️"
                        if check_data["status"] == "warn"
                        else "⏭️"
                    )
                    if check_name == "pbp_alignment":
                        print(
                            f"  {status_icon} PBP: {check_data['missing']} missing, {check_data['orphaned']} orphaned"
                        )
                    elif check_name == "shots_alignment":
                        print(
                            f"  {status_icon} Shots: {check_data['missing']} missing, {check_data['orphaned']} orphaned"
                        )

    # Print curated layer validation
    if "curated" in results:
        print("\n" + "=" * 80)
        print("  CURATED LAYER (INDEX ↔ CURATED)")
        print("=" * 80)

        for item in results["curated"]:
            season = item["season"]
            print(f"\n{season}:")

            for check_name, check_data in item["checks"].items():
                if check_name == "pbp_curated":
                    if "status" in check_data:
                        status_icon = (
                            "✅"
                            if check_data["status"] == "pass"
                            else "❌"
                            if check_data["status"] == "fail"
                            else "⏭️"
                        )
                        if check_data["status"] == "pass":
                            print(
                                f"  {status_icon} PBP Dataset: {check_data['actual_games']}/{check_data['expected_games']} games, "
                                f"{check_data['total_rows']:,} rows"
                            )
                        elif check_data["status"] == "fail":
                            if "message" in check_data:
                                print(f"  {status_icon} PBP Dataset: {check_data['message']}")
                            else:
                                print(
                                    f"  {status_icon} PBP Dataset: {check_data['actual_games']}/{check_data['expected_games']} games "
                                    f"({check_data['missing_games']} missing, {check_data['extra_games']} extra, "
                                    f"{check_data['metadata_inconsistencies']} metadata issues)"
                                )
                        elif check_data["status"] == "skip":
                            print(f"  ⏭️ PBP Dataset: {check_data['message']}")

                elif check_name == "shots_curated":
                    if "status" in check_data:
                        status_icon = (
                            "✅"
                            if check_data["status"] == "pass"
                            else "❌"
                            if check_data["status"] == "fail"
                            else "⏭️"
                        )
                        if check_data["status"] == "pass":
                            print(
                                f"  {status_icon} Shots Dataset: {check_data['actual_games']}/{check_data['expected_games']} games, "
                                f"{check_data['total_rows']:,} rows"
                            )
                        elif check_data["status"] == "fail":
                            if "message" in check_data:
                                print(f"  {status_icon} Shots Dataset: {check_data['message']}")
                            else:
                                print(
                                    f"  {status_icon} Shots Dataset: {check_data['actual_games']}/{check_data['expected_games']} games "
                                    f"({check_data['missing_games']} missing, {check_data['extra_games']} extra, "
                                    f"{check_data['metadata_inconsistencies']} metadata issues)"
                                )
                        elif check_data["status"] == "skip":
                            print(f"  ⏭️ Shots Dataset: {check_data['message']}")

                elif check_name == "quality_reports":
                    for report_name, report_data in check_data.items():
                        if "status" in report_data:
                            status_icon = "✅" if report_data["status"] == "pass" else "⚠️"
                            if report_data.get("exists"):
                                if report_data["status"] == "pass":
                                    print(
                                        f"  {status_icon} {report_name.replace('_', ' ').title()}: "
                                        f"{report_data['valid_games']} valid, {report_data['quarantined_games']} quarantined"
                                    )
                                else:
                                    print(
                                        f"  {status_icon} {report_name.replace('_', ' ').title()}: Parse error"
                                    )
                            else:
                                print(
                                    f"  {status_icon} {report_name.replace('_', ' ').title()}: Not found"
                                )

    # Final summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"\nTotal checks: {total_checks}")
    print(f"  ✅ Passed: {passed_checks}")
    print(f"  ❌ Failed: {failed_checks}")
    print(f"  ⚠️  Warnings: {warned_checks}")
    print(f"  ⏭️  Skipped: {total_checks - passed_checks - failed_checks - warned_checks}")

    if failed_checks == 0:
        print("\n✅ ALL CRITICAL CHECKS PASSED")
    else:
        print(f"\n❌ {failed_checks} CRITICAL FAILURES")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="LNB Reconciliation Gate")
    parser.add_argument("--season", help="Filter to specific season (e.g., 2023-2024)")
    parser.add_argument(
        "--league",
        help="Filter to specific league (e.g., betclic_elite, espoirs_prob)",
    )
    parser.add_argument("--json-output", help="Write results to JSON file", metavar="FILE")
    parser.add_argument("--verbose", action="store_true", help="Show detailed check information")

    args = parser.parse_args()

    try:
        # Load index
        index_df = load_game_index(season_filter=args.season, league_filter=args.league)
        print(f"\n[INFO] Loaded {len(index_df)} games from index")

        # Run checks
        results = {}

        # Global correctness checks
        results["correctness"] = check_correctness(index_df)

        # Global schema checks
        results["schema"] = check_schema(index_df)

        # Coverage checks per season/league
        coverage_results = []
        for (season, league), group in index_df.groupby(["season", "league"]):
            coverage_results.append(check_coverage(index_df, season, league))
        results["coverage"] = coverage_results

        # Reconciliation checks per season/league
        reconciliation_results = []
        for (season, league), group in index_df.groupby(["season", "league"]):
            reconciliation_results.append(check_reconciliation(index_df, season, league))
        results["reconciliation"] = reconciliation_results

        # Curated layer checks per season
        curated_results = []
        for season in index_df["season"].unique():
            curated_results.append(check_curated_layer(index_df, season))
        results["curated"] = curated_results

        # Print results
        print_results(results, verbose=args.verbose)

        # Save JSON if requested
        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as f:
                json_safe_results = convert_to_json_serializable(results)
                json.dump(json_safe_results, f, indent=2, ensure_ascii=False)
            print(f"\n[INFO] Results saved to {args.json_output}")

        # Determine exit code
        failed_checks = sum(
            1
            for item in results.values()
            for check in (item if isinstance(item, list) else [item])
            for check_data in (check.get("checks", {}).values() if isinstance(check, dict) else [])
            if isinstance(check_data, dict) and check_data.get("status") == "fail"
        )

        return 0 if failed_checks == 0 else 1

    except ReconciliationError as e:
        print("\n" + "=" * 80)
        print("  RECONCILIATION FAILED ❌")
        print("=" * 80)
        print(f"\nError: {e}")
        return 1

    except Exception as e:
        print("\n" + "=" * 80)
        print("  UNEXPECTED ERROR ❌")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
