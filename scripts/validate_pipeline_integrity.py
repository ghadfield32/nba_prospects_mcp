#!/usr/bin/env python3
"""Pipeline Integrity Validator - CI Gate for Data Quality

Performs TRUTHY validations that must always pass:
1. Schema validation (required columns present)
2. Primary key uniqueness
3. Referential integrity (player_map join keys exist)
4. Sanity checks (no negative stats, dates in valid range)
5. Normalization completeness (11 columns present)

Exit code: 0 (pass), 1 (fail)
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GOLD_FILE = PROJECT_ROOT / "data" / "gold" / "player_career_unified_tier1.parquet"
PLAYER_MAP_FILE = PROJECT_ROOT / "data" / "identity" / "player_map.parquet"


def validate_schema(df: pd.DataFrame, required_cols: list) -> dict[str, Any]:
    """Validate required columns are present"""
    missing = [col for col in required_cols if col not in df.columns]
    return {
        "passed": len(missing) == 0,
        "missing_columns": missing,
        "total_columns": len(df.columns),
        "required_columns": len(required_cols),
    }


def validate_primary_key_unique(df: pd.DataFrame, pk_cols: list) -> dict[str, Any]:
    """Validate primary key uniqueness"""
    total_rows = len(df)
    unique_keys = df[pk_cols].drop_duplicates().shape[0]
    duplicates = total_rows - unique_keys

    return {
        "passed": duplicates == 0,
        "total_rows": total_rows,
        "unique_keys": unique_keys,
        "duplicates": duplicates,
        "duplicate_rate": duplicates / total_rows if total_rows > 0 else 0,
    }


def validate_referential_integrity(
    gold_df: pd.DataFrame, player_map: pd.DataFrame
) -> dict[str, Any]:
    """Validate referential integrity between gold data and player_map"""
    gold_uids = set(gold_df["PLAYER_UID"].unique())
    map_uids = set(player_map["PLAYER_UID"].unique())

    orphaned_uids = gold_uids - map_uids
    unused_uids = map_uids - gold_uids

    return {
        "passed": len(orphaned_uids) == 0,
        "gold_unique_uids": len(gold_uids),
        "map_unique_uids": len(map_uids),
        "orphaned_uids": len(orphaned_uids),
        "unused_uids": len(unused_uids),
        "orphaned_uid_samples": list(orphaned_uids)[:5] if orphaned_uids else [],
    }


def validate_player_map_uniqueness(player_map: pd.DataFrame) -> dict[str, Any]:
    """Validate player_map has 1:1 join keys"""
    join_key_cols = ["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]
    total_rows = len(player_map)
    unique_join_keys = player_map[join_key_cols].drop_duplicates().shape[0]
    duplicates = total_rows - unique_join_keys

    return {
        "passed": duplicates == 0,
        "total_mappings": total_rows,
        "unique_join_keys": unique_join_keys,
        "duplicates": duplicates,
        "duplicate_rate": duplicates / total_rows if total_rows > 0 else 0,
    }


def validate_normalization(df: pd.DataFrame) -> dict[str, Any]:
    """Validate all 11 normalization columns are present"""
    season_cols = ["SEASON_RAW", "SEASON", "SEASON_START_YEAR", "SEASON_END_YEAR", "SEASON_TYPE"]
    name_cols = [
        "PLAYER_NAME_RAW",
        "PLAYER_NAME_CANONICAL",
        "FIRST_NAME",
        "LAST_NAME",
        "FIRST_INITIAL",
        "NAME_KEY_CANONICAL",
        "NAME_KEY_INITIAL",
    ]

    season_missing = [col for col in season_cols if col not in df.columns]
    name_missing = [col for col in name_cols if col not in df.columns]

    # Check SEASON format compliance
    season_format_ok = False
    if "SEASON" in df.columns:
        season_format_ok = df["SEASON"].str.match(r"^\d{4}-\d{2}$").all()

    # Check for NULLs in critical columns
    null_checks = {}
    for col in ["SEASON", "PLAYER_NAME_RAW", "LAST_NAME"]:
        if col in df.columns:
            null_count = df[col].isna().sum()
            null_checks[col] = {"null_count": null_count, "null_rate": null_count / len(df)}

    return {
        "passed": len(season_missing) == 0 and len(name_missing) == 0 and season_format_ok,
        "season_cols_present": len(season_cols) - len(season_missing),
        "season_cols_missing": season_missing,
        "name_cols_present": len(name_cols) - len(name_missing),
        "name_cols_missing": name_missing,
        "season_format_valid": season_format_ok,
        "null_checks": null_checks,
    }


def validate_sanity_checks(df: pd.DataFrame) -> dict[str, Any]:
    """Perform sanity checks on data values"""
    issues = []

    # Check for negative stats (use uppercase column names)
    stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    for col in stat_cols:
        if col in df.columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                issues.append(f"{col} has {negative_count} negative values")

    # Check date range
    if "GAME_DATE" in df.columns:
        min_date = df["GAME_DATE"].min()
        max_date = df["GAME_DATE"].max()

        if min_date < pd.Timestamp("2000-01-01"):
            issues.append(f"GAME_DATE min ({min_date}) is before 2000")
        if max_date > pd.Timestamp.now() + pd.Timedelta(days=365):
            issues.append(f"GAME_DATE max ({max_date}) is more than 1 year in future")

    # Check season years
    if "SEASON_START_YEAR" in df.columns and "SEASON_END_YEAR" in df.columns:
        invalid_years = (df["SEASON_START_YEAR"] >= df["SEASON_END_YEAR"]).sum()
        if invalid_years > 0:
            issues.append(f"{invalid_years} rows have SEASON_START_YEAR >= SEASON_END_YEAR")

    # Session 332b enhancement: Check for whitespace in SOURCE_PLAYER_ID
    if "SOURCE_PLAYER_ID" in df.columns:
        # Convert to string for whitespace checks
        source_ids = df["SOURCE_PLAYER_ID"].astype(str)

        # Check for leading whitespace
        leading_ws = source_ids.str.match(r"^\s").sum()
        if leading_ws > 0:
            issues.append(
                f"{leading_ws} SOURCE_PLAYER_IDs have leading whitespace ({leading_ws/len(df)*100:.2f}%)"
            )

        # Check for trailing whitespace
        trailing_ws = source_ids.str.match(r"\s$").sum()
        if trailing_ws > 0:
            issues.append(
                f"{trailing_ws} SOURCE_PLAYER_IDs have trailing whitespace ({trailing_ws/len(df)*100:.2f}%)"
            )

        # Check for internal multiple spaces
        multi_space = source_ids.str.contains(r"  ").sum()
        if multi_space > 0:
            issues.append(f"{multi_space} SOURCE_PLAYER_IDs have multiple consecutive spaces")

    return {"passed": len(issues) == 0, "issues": issues, "total_issues": len(issues)}


def main():
    print("=" * 80)
    print("PIPELINE INTEGRITY VALIDATOR (CI GATE)")
    print("=" * 80)
    print()

    # Check files exist
    if not GOLD_FILE.exists():
        print(f"✗ FAIL: Gold file not found: {GOLD_FILE}")
        return 1

    if not PLAYER_MAP_FILE.exists():
        print(f"✗ FAIL: Player map not found: {PLAYER_MAP_FILE}")
        return 1

    # Load data
    print("Loading data...")
    gold_df = pd.read_parquet(GOLD_FILE)
    player_map = pd.read_parquet(PLAYER_MAP_FILE)
    print(f"  Gold: {len(gold_df):,} records, {gold_df['PLAYER_UID'].nunique():,} players")
    print(f"  Player map: {len(player_map):,} mappings")
    print()

    results = {}

    # 1. Schema validation
    print("1. Schema Validation")
    print("-" * 80)
    required_cols = [
        "PLAYER_UID",
        "SOURCE_LEAGUE",
        "SOURCE_PLAYER_ID",
        "GAME_ID",
        "GAME_DATE",
        "SEASON",
        "SEASON_START_YEAR",
        "PTS",
        "REB",
        "AST",  # Uppercase stat columns
        "PLAYER_NAME_RAW",
        "NAME_KEY_CANONICAL",
    ]
    results["schema"] = validate_schema(gold_df, required_cols)

    if results["schema"]["passed"]:
        print(f"  ✓ PASS - All {results['schema']['required_columns']} required columns present")
    else:
        print(f"  ✗ FAIL - Missing columns: {results['schema']['missing_columns']}")
    print()

    # 2. Primary key uniqueness
    print("2. Primary Key Uniqueness")
    print("-" * 80)
    # NOTE: Primary key includes SEASON because same GAME_ID can appear in multiple seasons
    pk_cols = ["PLAYER_UID", "SOURCE_LEAGUE", "SEASON", "GAME_ID"]
    results["pk_unique"] = validate_primary_key_unique(gold_df, pk_cols)

    if results["pk_unique"]["passed"]:
        print(
            f"  ✓ PASS - All {results['pk_unique']['total_rows']:,} rows have unique primary keys"
        )
    else:
        print(
            f"  ✗ FAIL - Found {results['pk_unique']['duplicates']:,} duplicate keys "
            + f"({results['pk_unique']['duplicate_rate']:.2%})"
        )
        print(f"    Primary key: {pk_cols}")
    print()

    # 3. Player map uniqueness
    print("3. Player Map Join Key Uniqueness")
    print("-" * 80)
    results["map_unique"] = validate_player_map_uniqueness(player_map)

    if results["map_unique"]["passed"]:
        print(
            f"  ✓ PASS - All {results['map_unique']['total_mappings']:,} mappings have unique join keys (1:1)"
        )
    else:
        print(
            f"  ✗ FAIL - Found {results['map_unique']['duplicates']:,} duplicate join keys "
            + f"({results['map_unique']['duplicate_rate']:.2%})"
        )
    print()

    # 4. Referential integrity
    print("4. Referential Integrity")
    print("-" * 80)
    results["ref_integrity"] = validate_referential_integrity(gold_df, player_map)

    if results["ref_integrity"]["passed"]:
        print(
            f"  ✓ PASS - All {results['ref_integrity']['gold_unique_uids']:,} UIDs in gold data exist in player_map"
        )
    else:
        print(f"  ✗ FAIL - Found {results['ref_integrity']['orphaned_uids']:,} orphaned UIDs")
        if results["ref_integrity"]["orphaned_uid_samples"]:
            print(f"    Sample orphaned UIDs: {results['ref_integrity']['orphaned_uid_samples']}")

    if results["ref_integrity"]["unused_uids"] > 0:
        print(
            f"  ⚠️  Note: {results['ref_integrity']['unused_uids']:,} UIDs in player_map not used in gold data"
        )
    print()

    # 5. Normalization completeness
    print("5. Normalization Completeness")
    print("-" * 80)
    results["normalization"] = validate_normalization(gold_df)

    if results["normalization"]["passed"]:
        print("  ✓ PASS - All 11 normalization columns present and valid")
        print(f"    Season columns: {results['normalization']['season_cols_present']}/5")
        print(f"    Name columns: {results['normalization']['name_cols_present']}/7")
        print(
            f"    SEASON format: {'✓ Valid (YYYY-YY)' if results['normalization']['season_format_valid'] else '✗ Invalid'}"
        )
    else:
        print("  ✗ FAIL - Normalization incomplete")
        if results["normalization"]["season_cols_missing"]:
            print(f"    Missing season cols: {results['normalization']['season_cols_missing']}")
        if results["normalization"]["name_cols_missing"]:
            print(f"    Missing name cols: {results['normalization']['name_cols_missing']}")
        if not results["normalization"]["season_format_valid"]:
            print("    SEASON format invalid (expected YYYY-YY)")

    # Show null rates
    if results["normalization"]["null_checks"]:
        print("\n  Null rates:")
        for col, stats in results["normalization"]["null_checks"].items():
            print(f"    {col:20}: {stats['null_count']:6,} ({stats['null_rate']:.1%})")
    print()

    # 6. Sanity checks
    print("6. Data Sanity Checks")
    print("-" * 80)
    results["sanity"] = validate_sanity_checks(gold_df)

    if results["sanity"]["passed"]:
        print("  ✓ PASS - All sanity checks passed")
    else:
        print(f"  ✗ FAIL - Found {results['sanity']['total_issues']} issues:")
        for issue in results["sanity"]["issues"]:
            print(f"    - {issue}")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    all_passed = all(r["passed"] for r in results.values())
    passed_count = sum(1 for r in results.values() if r["passed"])
    total_count = len(results)

    print(f"\nValidation Results: {passed_count}/{total_count} checks passed")
    print()

    for check_name, result in results.items():
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"  {status:10} - {check_name}")

    print()

    if all_passed:
        print("✓✓✓ ALL CHECKS PASSED - Pipeline integrity validated")
        return 0
    else:
        print("✗✗✗ VALIDATION FAILED - Fix issues above before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
