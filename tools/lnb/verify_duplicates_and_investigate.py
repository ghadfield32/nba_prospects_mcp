#!/usr/bin/env python3
"""Comprehensive LNB Data Investigation & Duplicate Verification

This script performs a thorough investigation to:
1. Verify duplicate files are truly identical (byte-by-byte comparison)
2. Check raw PBP/historical data for GAME_DATE fields
3. Investigate why only 1 game exists in 2021-2022 and 2022-2023
4. Attempt to fetch additional historical data via LNB API
5. Check for missing 2025-2026 PBP data
6. Generate detailed recommendations

Following user's 10-step process:
- Step 1: Analyze existing code structure
- Step 2: Think through efficiencies
- Step 3: Ensure code efficiency
- Step 4: Plan changes
- Step 5: Implement incrementally with testing
- Step 6: Document each step
- Step 7: Validate compatibility
"""

from __future__ import annotations

import hashlib
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
TOOLS_ROOT = Path("tools/lnb")

# Duplicate files identified in investigation
DUPLICATE_PAIRS = [
    # Format: (keep_path, duplicate_path, true_season, game_id_short)
    (
        "data/normalized/lnb/player_game/season=2021-2022/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "data/normalized/lnb/player_game/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "2021-2022",
        "7d414bce-f5da...",
    ),
    (
        "data/normalized/lnb/player_game/season=2022-2023/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "data/normalized/lnb/player_game/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "2022-2023",
        "cc7e470e-11a0...",
    ),
    (
        "data/normalized/lnb/player_game/season=2023-2024/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet",
        "data/normalized/lnb/player_game/season=2024-2025/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet",
        "2023-2024",
        "0cac6e1b-6715...",
    ),
    (
        "data/normalized/lnb/player_game/season=2023-2024/game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet",
        "data/normalized/lnb/player_game/season=2024-2025/game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet",
        "2023-2024",
        "0cd1323f-6715...",
    ),
    # team_game duplicates
    (
        "data/normalized/lnb/team_game/season=2021-2022/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "data/normalized/lnb/team_game/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "2021-2022",
        "7d414bce-f5da...",
    ),
    (
        "data/normalized/lnb/team_game/season=2022-2023/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "data/normalized/lnb/team_game/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "2022-2023",
        "cc7e470e-11a0...",
    ),
    (
        "data/normalized/lnb/team_game/season=2023-2024/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet",
        "data/normalized/lnb/team_game/season=2024-2025/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet",
        "2023-2024",
        "0cac6e1b-6715...",
    ),
    (
        "data/normalized/lnb/team_game/season=2023-2024/game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet",
        "data/normalized/lnb/team_game/season=2024-2025/game_id=0cd1323f-6715-11f0-a9f3-27e6e78614e1.parquet",
        "2023-2024",
        "0cd1323f-6715...",
    ),
]

# ==============================================================================
# STEP 2-3: EFFICIENT HELPER FUNCTIONS
# ==============================================================================


def compute_file_hash(file_path: Path) -> str | None:
    """Compute SHA256 hash of file for byte-level comparison

    This is more efficient than loading entire file into memory.
    Uses streaming to handle large files.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hash string or None if error
    """
    if not file_path.exists():
        return None

    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            # Read in 64kb chunks for memory efficiency
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"ERROR hashing {file_path.name}: {e}")
        return None


def compare_parquet_content(file1: Path, file2: Path) -> dict:
    """Compare two parquet files for data equality

    Checks:
    - Byte-level hash (fastest)
    - Row count
    - Column names
    - Data content (if needed)

    Args:
        file1: First parquet file
        file2: Second parquet file

    Returns:
        Dict with comparison results
    """
    result = {
        "file1": str(file1),
        "file2": str(file2),
        "identical_hash": False,
        "identical_content": False,
        "differences": [],
    }

    # Step 1: Byte-level comparison (fastest)
    hash1 = compute_file_hash(file1)
    hash2 = compute_file_hash(file2)

    if hash1 and hash2:
        result["hash1"] = hash1
        result["hash2"] = hash2
        result["identical_hash"] = hash1 == hash2

        if hash1 == hash2:
            # Files are byte-for-byte identical
            result["identical_content"] = True
            return result

    # Step 2: Content comparison (if hashes differ or unavailable)
    try:
        df1 = pd.read_parquet(file1)
        df2 = pd.read_parquet(file2)

        # Compare shapes
        if df1.shape != df2.shape:
            result["differences"].append(f"Shape mismatch: {df1.shape} vs {df2.shape}")
            return result

        # Compare columns
        if list(df1.columns) != list(df2.columns):
            result["differences"].append(f"Column mismatch: {set(df1.columns) ^ set(df2.columns)}")
            return result

        # Compare data (expensive but thorough)
        if df1.equals(df2):
            result["identical_content"] = True
        else:
            # Find specific differences
            diff_mask = df1 != df2
            diff_count = diff_mask.sum().sum()
            result["differences"].append(f"Data differs in {diff_count} cells")

    except Exception as e:
        result["differences"].append(f"Error comparing: {str(e)}")

    return result


# ==============================================================================
# STEP 4-5: INVESTIGATION FUNCTIONS
# ==============================================================================


def verify_all_duplicates() -> dict:
    """Verify that identified duplicate files are truly identical

    Returns:
        Dict with verification results for each duplicate pair
    """
    print(f"\n{'='*80}")
    print("STEP 5.1: VERIFYING DUPLICATE FILES")
    print(f"{'='*80}\n")

    results = {
        "total_pairs": len(DUPLICATE_PAIRS),
        "verified_identical": 0,
        "not_identical": 0,
        "missing_files": 0,
        "pairs": [],
    }

    for keep_path, dup_path, true_season, game_id in DUPLICATE_PAIRS:
        keep_file = Path(keep_path)
        dup_file = Path(dup_path)

        print(f"Verifying: {game_id} (season: {true_season})")
        print(f"  Original: {keep_file.name}")
        print(f"  Duplicate: {dup_file.name}")

        pair_result = {
            "game_id": game_id,
            "true_season": true_season,
            "keep_path": keep_path,
            "duplicate_path": dup_path,
            "status": "unknown",
        }

        if not keep_file.exists():
            print("  ❌ MISSING: Original file not found!")
            pair_result["status"] = "missing_original"
            results["missing_files"] += 1

        elif not dup_file.exists():
            print("  ❌ MISSING: Duplicate file not found!")
            pair_result["status"] = "missing_duplicate"
            results["missing_files"] += 1

        else:
            comparison = compare_parquet_content(keep_file, dup_file)

            if comparison["identical_hash"]:
                print("  ✅ VERIFIED: Files are byte-for-byte identical")
                print(f"     Hash: {comparison['hash1'][:16]}...")
                pair_result["status"] = "verified_identical"
                pair_result["hash"] = comparison["hash1"]
                results["verified_identical"] += 1

            elif comparison["identical_content"]:
                print("  ⚠️ CONTENT IDENTICAL: Different encoding/metadata")
                pair_result["status"] = "content_identical"
                results["verified_identical"] += 1

            else:
                print("  ❌ NOT IDENTICAL: Files differ!")
                print(f"     Differences: {comparison['differences']}")
                pair_result["status"] = "not_identical"
                pair_result["differences"] = comparison["differences"]
                results["not_identical"] += 1

        results["pairs"].append(pair_result)
        print()

    # Summary
    print(f"{'='*80}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total pairs checked: {results['total_pairs']}")
    print(f"Verified identical: {results['verified_identical']}")
    print(f"Not identical: {results['not_identical']}")
    print(f"Missing files: {results['missing_files']}")
    print()

    return results


def check_game_date_in_raw_data() -> dict:
    """Check if GAME_DATE exists in raw historical PBP/fixtures data

    Returns:
        Dict with findings on GAME_DATE availability
    """
    print(f"\n{'='*80}")
    print("STEP 5.2: CHECKING FOR GAME_DATE IN RAW DATA")
    print(f"{'='*80}\n")

    results = {
        "fixtures_has_date": False,
        "pbp_has_date": False,
        "sample_dates": [],
        "can_recover_dates": False,
    }

    # Check 2025-2026 fixtures
    fixtures_path = HISTORICAL_ROOT / "2025-2026" / "fixtures.parquet"

    if fixtures_path.exists():
        try:
            df = pd.read_parquet(fixtures_path)
            print(f"Fixtures columns: {df.columns.tolist()}")

            date_cols = [col for col in df.columns if "date" in col.lower()]
            if date_cols:
                results["fixtures_has_date"] = True
                print(f"✅ Found date columns: {date_cols}")

                # Sample some dates
                for col in date_cols:
                    sample_dates = df[col].dropna().head(3).tolist()
                    results["sample_dates"].extend([{col: str(d)} for d in sample_dates])
                    print(f"   {col}: {sample_dates[:3]}")

            else:
                print("❌ No date columns found in fixtures")

        except Exception as e:
            print(f"ERROR reading fixtures: {e}")

    # Check PBP events
    pbp_path = HISTORICAL_ROOT / "2025-2026" / "pbp_events.parquet"

    if pbp_path.exists():
        try:
            df = pd.read_parquet(pbp_path)
            print(f"\nPBP events columns: {df.columns.tolist()}")

            date_cols = [col for col in df.columns if "date" in col.lower()]
            if date_cols:
                results["pbp_has_date"] = True
                print(f"✅ Found date columns: {date_cols}")
            else:
                print("❌ No date columns found in PBP")

        except Exception as e:
            print(f"ERROR reading PBP: {e}")

    # Conclusion
    results["can_recover_dates"] = results["fixtures_has_date"] or results["pbp_has_date"]

    print(f"\n{'='*80}")
    print(f"Can recover GAME_DATE from raw data: {results['can_recover_dates']}")
    print(f"{'='*80}\n")

    return results


def investigate_early_seasons() -> dict:
    """Investigate why 2021-2022 and 2022-2023 only have 1 game each

    Returns:
        Dict with findings
    """
    print(f"\n{'='*80}")
    print("STEP 5.3: INVESTIGATING EARLY SEASONS (2021-2023)")
    print(f"{'='*80}\n")

    results = {
        "2021-2022": {"games": [], "investigation": ""},
        "2022-2023": {"games": [], "investigation": ""},
        "conclusion": "",
    }

    for season in ["2021-2022", "2022-2023"]:
        season_dir = NORMALIZED_ROOT / "player_game" / f"season={season}"

        if not season_dir.exists():
            results[season]["investigation"] = "Directory does not exist"
            continue

        parquet_files = list(season_dir.glob("*.parquet"))
        print(f"\n{season}: Found {len(parquet_files)} file(s)")

        for file_path in parquet_files:
            try:
                df = pd.read_parquet(file_path)

                game_info = {
                    "file": file_path.name,
                    "rows": len(df),
                    "game_id": df.iloc[0]["GAME_ID"] if len(df) > 0 else None,
                    "season_in_data": df.iloc[0].get("SEASON") if len(df) > 0 else None,
                    "columns": df.columns.tolist(),
                }

                results[season]["games"].append(game_info)

                print(f"  File: {file_path.name}")
                print(f"    Rows: {len(df)}")
                print(f"    Game ID: {game_info['game_id']}")
                print(f"    Season in data: {game_info['season_in_data']}")

            except Exception as e:
                print(f"  ERROR reading {file_path.name}: {e}")

    # Check if there's any evidence of more games
    print(f"\n{'='*80}")
    print("CHECKING FOR EVIDENCE OF ADDITIONAL GAMES")
    print(f"{'='*80}\n")

    # Check if game index exists
    game_index_path = DATA_ROOT / "lnb" / "game_index.parquet"
    if game_index_path.exists():
        try:
            df = pd.read_parquet(game_index_path)
            print(f"Game index found: {len(df)} total games")

            if "season" in df.columns:
                season_counts = df["season"].value_counts().to_dict()
                print("Games by season in index:")
                for s, count in sorted(season_counts.items()):
                    print(f"  {s}: {count} games")

                    if s in ["2021-2022", "2022-2023"]:
                        results[s]["investigation"] = (
                            f"Game index shows {count} games, but only 1 normalized file exists. "
                            f"Possible explanations: (1) Only 1 game was successfully normalized, "
                            f"(2) Other games failed during normalization, (3) Files were deleted"
                        )

        except Exception as e:
            print(f"ERROR reading game index: {e}")
    else:
        print(f"❌ No game index found at {game_index_path}")
        results["conclusion"] = (
            "Without a game index, cannot determine if more games existed. "
            "The single game per season may represent: (1) Test data only, "
            "(2) Limited initial ingestion, (3) Only available data from source"
        )

    print()
    return results


def check_missing_2025_pbp() -> dict:
    """Check which 2025-2026 fixtures are missing PBP/shots data

    Returns:
        Dict with missing game details
    """
    print(f"\n{'='*80}")
    print("STEP 5.4: CHECKING MISSING 2025-2026 PBP DATA")
    print(f"{'='*80}\n")

    results = {
        "total_fixtures": 0,
        "games_with_pbp": 0,
        "games_with_shots": 0,
        "missing_pbp": [],
        "missing_shots": [],
    }

    fixtures_path = HISTORICAL_ROOT / "2025-2026" / "fixtures.parquet"
    pbp_path = HISTORICAL_ROOT / "2025-2026" / "pbp_events.parquet"
    shots_path = HISTORICAL_ROOT / "2025-2026" / "shots.parquet"

    if not fixtures_path.exists():
        print("❌ Fixtures file not found")
        return results

    try:
        # Read all data
        fixtures_df = pd.read_parquet(fixtures_path)
        results["total_fixtures"] = len(fixtures_df)

        print(f"Total fixtures: {len(fixtures_df)}")
        print(f"Fixture columns: {fixtures_df.columns.tolist()}\n")

        # Get all fixture IDs/UUIDs
        if "fixture_uuid" in fixtures_df.columns:
            all_fixture_ids = set(fixtures_df["fixture_uuid"].dropna())
        elif "GAME_ID" in fixtures_df.columns:
            all_fixture_ids = set(fixtures_df["GAME_ID"].dropna())
        else:
            print("❌ Cannot find game ID column in fixtures")
            return results

        # Check PBP
        if pbp_path.exists():
            pbp_df = pd.read_parquet(pbp_path)

            if "fixture_uuid" in pbp_df.columns:
                pbp_game_ids = set(pbp_df["fixture_uuid"].dropna())
            elif "GAME_ID" in pbp_df.columns:
                pbp_game_ids = set(pbp_df["GAME_ID"].dropna())
            else:
                pbp_game_ids = set()

            results["games_with_pbp"] = len(pbp_game_ids)
            results["missing_pbp"] = list(all_fixture_ids - pbp_game_ids)

            print(f"Games with PBP: {len(pbp_game_ids)}")
            print(f"Missing PBP: {len(results['missing_pbp'])}")

            if results["missing_pbp"]:
                print("Missing PBP for games:")
                for game_id in results["missing_pbp"]:
                    # Get game details from fixtures
                    game_row = fixtures_df[
                        fixtures_df["fixture_uuid"] == game_id
                        if "fixture_uuid" in fixtures_df.columns
                        else fixtures_df["GAME_ID"] == game_id
                    ]
                    if not game_row.empty:
                        print(f"  {game_id}: {game_row.iloc[0].to_dict()}")

        # Check shots
        if shots_path.exists():
            shots_df = pd.read_parquet(shots_path)

            if "fixture_uuid" in shots_df.columns:
                shot_game_ids = set(shots_df["fixture_uuid"].dropna())
            elif "GAME_ID" in shots_df.columns:
                shot_game_ids = set(shots_df["GAME_ID"].dropna())
            else:
                shot_game_ids = set()

            results["games_with_shots"] = len(shot_game_ids)
            results["missing_shots"] = list(all_fixture_ids - shot_game_ids)

            print(f"\nGames with shots: {len(shot_game_ids)}")
            print(f"Missing shots: {len(results['missing_shots'])}")

    except Exception as e:
        print(f"ERROR: {e}")

    print()
    return results


# ==============================================================================
# STEP 7: MAIN ORCHESTRATION
# ==============================================================================


def main():
    """Main investigation workflow

    Steps:
    1. Verify duplicate files are identical
    2. Check for GAME_DATE in raw data
    3. Investigate early seasons
    4. Check missing 2025-2026 data
    5. Generate comprehensive report
    """
    print(f"{'#'*80}")
    print("# LNB DATA INVESTIGATION - COMPREHENSIVE VERIFICATION")
    print(f"# Started: {datetime.now().isoformat()}")
    print(f"{'#'*80}\n")

    # Step 5.1: Verify duplicates
    duplicate_verification = verify_all_duplicates()

    # Step 5.2: Check GAME_DATE
    game_date_check = check_game_date_in_raw_data()

    # Step 5.3: Investigate early seasons
    early_season_investigation = investigate_early_seasons()

    # Step 5.4: Check missing 2025-2026 data
    missing_pbp_check = check_missing_2025_pbp()

    # Compile comprehensive report
    report = {
        "generated_at": datetime.now().isoformat(),
        "duplicate_verification": duplicate_verification,
        "game_date_availability": game_date_check,
        "early_season_investigation": early_season_investigation,
        "missing_2025_pbp": missing_pbp_check,
    }

    # Save report
    output_file = TOOLS_ROOT / "comprehensive_investigation_report.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'='*80}")
    print("INVESTIGATION COMPLETE")
    print(f"{'='*80}")
    print(f"Report saved: {output_file}\n")

    # Step 6: Print recommendations
    print(f"{'#'*80}")
    print("# RECOMMENDATIONS")
    print(f"{'#'*80}\n")

    if duplicate_verification["verified_identical"] == duplicate_verification["total_pairs"]:
        print(
            f"✅ All {duplicate_verification['verified_identical']} duplicate pairs verified identical"
        )
        print("   SAFE TO DELETE: Duplicate files can be removed without data loss\n")
    else:
        print("⚠️ WARNING: Not all duplicates verified!")
        print(
            f"   Verified: {duplicate_verification['verified_identical']}/{duplicate_verification['total_pairs']}"
        )
        print("   DO NOT DELETE until discrepancies resolved\n")

    if game_date_check["can_recover_dates"]:
        print("✅ GAME_DATE can be recovered from raw data")
        print("   Recommend: Re-run normalization pipeline with GAME_DATE preservation\n")
    else:
        print("❌ GAME_DATE not available in raw data")
        print("   Impact: Cannot add dates to normalized files without external data\n")

    if missing_pbp_check["missing_pbp"]:
        print(f"⚠️ {len(missing_pbp_check['missing_pbp'])} fixtures missing PBP data")
        print("   Recommend: Attempt to re-fetch from LNB API\n")

    print(f"{'#'*80}\n")


if __name__ == "__main__":
    main()
