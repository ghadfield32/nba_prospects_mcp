#!/usr/bin/env python3
"""Fix UUID Corruption - Complete Solution

This script implements the complete fix for UUID corruption:
1. Deletes corrupted raw PBP files (wrong filenames)
2. Deletes corrupted normalized files
3. Validates remaining data integrity
4. Prepares for re-normalization

IMPORTANT: Run this BEFORE modifying create_normalized_tables.py
"""

from __future__ import annotations

import io
import json
import sys
from collections import defaultdict
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
RAW_PBP_ROOT = DATA_ROOT / "raw" / "lnb" / "pbp"
RAW_SHOTS_ROOT = DATA_ROOT / "raw" / "lnb" / "shots"
NORMALIZED_ROOT = DATA_ROOT / "normalized" / "lnb"
TOOLS_ROOT = Path("tools/lnb")

# Corrupted files identified by audit
CORRUPTED_RAW_FILES = [
    "data/raw/lnb/pbp/season=2023-2024/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet",
    "data/raw/lnb/pbp/season=2023-2024/game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet",
    "data/raw/lnb/pbp/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
    "data/raw/lnb/pbp/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
]

DRY_RUN = False  # Set to False to actually delete files

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def validate_raw_pbp_file(file_path: Path) -> dict:
    """Validate a raw PBP file

    Args:
        file_path: Path to raw PBP parquet file

    Returns:
        Dict with validation results
    """
    try:
        df = pd.read_parquet(file_path)

        if len(df) == 0:
            return {
                "valid": False,
                "error": "Empty file",
                "file_path": str(file_path),
            }

        # Extract UUIDs
        filename_uuid = file_path.stem.replace("game_id=", "")
        data_uuid = df["GAME_ID"].iloc[0]

        # Check match
        is_match = filename_uuid == data_uuid

        return {
            "valid": is_match,
            "file_path": str(file_path),
            "filename_uuid": filename_uuid,
            "data_uuid": data_uuid,
            "season": file_path.parent.name.replace("season=", ""),
            "row_count": len(df),
            "error": None if is_match else "Filename does not match data UUID",
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "file_path": str(file_path),
        }


def audit_all_raw_files() -> dict:
    """Audit all raw PBP files for UUID corruption

    Returns:
        Dict with audit results
    """
    print(f"\n{'=' * 80}")
    print("AUDITING ALL RAW PBP FILES")
    print(f"{'=' * 80}\n")

    all_files = sorted(RAW_PBP_ROOT.rglob("*.parquet"))
    results = {
        "valid": [],
        "corrupted": [],
        "errors": [],
    }

    for file_path in all_files:
        validation = validate_raw_pbp_file(file_path)

        if validation["valid"]:
            results["valid"].append(validation)
            print(f"✅ VALID: {file_path.name}")
        elif validation.get("error") == "Filename does not match data UUID":
            results["corrupted"].append(validation)
            print(f"❌ CORRUPTED: {file_path.name}")
            print(f"   Filename: {validation['filename_uuid']}")
            print(f"   Data:     {validation['data_uuid']}")
        else:
            results["errors"].append(validation)
            print(f"⚠️  ERROR: {file_path.name} - {validation['error']}")

    print(f"\n{'=' * 80}")
    print("AUDIT SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total files: {len(all_files)}")
    print(f"Valid: {len(results['valid'])}")
    print(f"Corrupted: {len(results['corrupted'])}")
    print(f"Errors: {len(results['errors'])}")

    return results


# ==============================================================================
# CLEANUP FUNCTIONS
# ==============================================================================


def delete_corrupted_raw_files(audit_results: dict, dry_run: bool = True) -> dict:
    """Delete corrupted raw PBP files

    Args:
        audit_results: Results from audit_all_raw_files()
        dry_run: If True, only simulate deletion

    Returns:
        Dict with deletion results
    """
    print(f"\n{'=' * 80}")
    print(f"DELETING CORRUPTED RAW FILES {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 80}\n")

    deleted = []
    failed = []

    for corrupted_file in audit_results["corrupted"]:
        file_path = Path(corrupted_file["file_path"])

        print(f"🗑️  {'Would delete' if dry_run else 'Deleting'}: {file_path.name}")
        print("   Reason: Filename UUID mismatch")
        print(f"   Filename: {corrupted_file['filename_uuid'][:30]}...")
        print(f"   Data:     {corrupted_file['data_uuid'][:30]}...")

        if not dry_run:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted.append(str(file_path))
                    print("   ✅ Deleted")
                else:
                    print("   ⚠️  File not found")
                    failed.append(str(file_path))
            except Exception as e:
                print(f"   ❌ Error: {e}")
                failed.append(str(file_path))
        else:
            deleted.append(str(file_path))

        # Also delete corresponding shots file if exists
        shots_file = Path(str(file_path).replace("/pbp/", "/shots/"))
        if shots_file.exists():
            print(f"   Also {'would delete' if dry_run else 'deleting'} shots: {shots_file.name}")
            if not dry_run:
                try:
                    shots_file.unlink()
                    print("   ✅ Deleted shots")
                except Exception as e:
                    print(f"   ❌ Error deleting shots: {e}")

        print()

    print(f"{'=' * 80}")
    print(f"DELETION SUMMARY {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 80}")
    print(f"Files {'would be' if dry_run else ''} deleted: {len(deleted)}")
    print(f"Files failed: {len(failed)}")

    return {
        "deleted": deleted,
        "failed": failed,
        "dry_run": dry_run,
    }


def delete_corrupted_normalized_files(dry_run: bool = True) -> dict:
    """Delete corrupted normalized files based on audit

    Args:
        dry_run: If True, only simulate deletion

    Returns:
        Dict with deletion results
    """
    print(f"\n{'=' * 80}")
    print(f"DELETING CORRUPTED NORMALIZED FILES {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 80}\n")

    # Load audit results
    audit_file = TOOLS_ROOT / "complete_uuid_audit.json"
    with open(audit_file) as f:
        audit = json.load(f)

    audit_summary = audit.get("audit_summary", {})
    print("Loaded audit snapshot:")
    print(
        f"  Files scanned: {audit_summary.get('total_files_audited', 'unknown')} | "
        f"Unique UUIDs: {audit_summary.get('total_unique_uuids', 'unknown')}"
    )

    # Strategy: Keep only files where filename_uuid matches data UUID
    # For 2023-2024, keep only game 3fcea9a1-1f10-11ee-a687-db190750bdda

    CORRECT_2023_2024_UUID = "3fcea9a1-1f10-11ee-a687-db190750bdda"
    CORRECT_2023_2024_HASH = "10e4ee163369b9fa"
    print(
        f"  Reference normalized UUID: {CORRECT_2023_2024_UUID} "
        f"(expected hash suffix {CORRECT_2023_2024_HASH})"
    )

    deleted = []
    kept = []

    # Process each dataset
    for dataset_type in ["player_game", "team_game"]:
        dataset_root = NORMALIZED_ROOT / dataset_type
        season_2023_dir = dataset_root / "season=2023-2024"

        if not season_2023_dir.exists():
            print(f"⚠️  Directory not found: {season_2023_dir}")
            continue

        print(f"\nProcessing: {dataset_type}/season=2023-2024")

        parquet_files = sorted(season_2023_dir.glob("*.parquet"))

        for file_path in parquet_files:
            filename_uuid = file_path.stem.replace("game_id=", "")

            # Keep only the correct UUID
            if filename_uuid == CORRECT_2023_2024_UUID:
                kept.append(str(file_path))
                print(f"  ✅ KEEP: {file_path.name}")
            else:
                deleted.append(str(file_path))
                print(f"  🗑️  {'Would delete' if dry_run else 'Deleting'}: {file_path.name}")
                print(f"      Reason: Wrong UUID (should be {CORRECT_2023_2024_UUID[:30]}...)")

                if not dry_run:
                    try:
                        file_path.unlink()
                        print("      ✅ Deleted")
                    except Exception as e:
                        print(f"      ❌ Error: {e}")

    print(f"\n{'=' * 80}")
    print(f"NORMALIZED FILES DELETION SUMMARY {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 80}")
    print(f"Files kept: {len(kept)}")
    print(f"Files {'would be' if dry_run else ''} deleted: {len(deleted)}")

    return {
        "deleted": deleted,
        "kept": kept,
        "dry_run": dry_run,
    }


# ==============================================================================
# VALIDATION POST-CLEANUP
# ==============================================================================


def validate_post_cleanup() -> dict:
    """Validate data integrity after cleanup

    Returns:
        Dict with validation results
    """
    print(f"\n{'=' * 80}")
    print("POST-CLEANUP VALIDATION")
    print(f"{'=' * 80}\n")

    # Re-audit raw files
    raw_audit = audit_all_raw_files()

    # Check normalized files
    print("\nChecking normalized files...")

    normalized_files = {
        "player_game": sorted((NORMALIZED_ROOT / "player_game").rglob("*.parquet")),
        "team_game": sorted((NORMALIZED_ROOT / "team_game").rglob("*.parquet")),
    }

    print(f"Player game files: {len(normalized_files['player_game'])}")
    print(f"Team game files: {len(normalized_files['team_game'])}")

    # Count by season
    by_season = defaultdict(int)
    for dataset_files in normalized_files.values():
        for f in dataset_files:
            season = f.parent.name.replace("season=", "")
            by_season[season] += 1

    print("\nFiles by season:")
    for season, count in sorted(by_season.items()):
        print(f"  {season}: {count} files")

    return {
        "raw_audit": raw_audit,
        "normalized_files": {k: len(v) for k, v in normalized_files.items()},
        "by_season": dict(by_season),
    }


# ==============================================================================
# MAIN WORKFLOW
# ==============================================================================


def main():
    """Main cleanup workflow"""

    print(f"{'#' * 80}")
    print("# LNB UUID CORRUPTION FIX")
    print(f"# Started: {datetime.now().isoformat()}")
    print(
        f"# Mode: {'DRY RUN (no files will be deleted)' if DRY_RUN else 'LIVE (files WILL be deleted)'}"
    )
    print(f"{'#' * 80}\n")

    # Phase 1: Audit raw files
    print("\n" + "=" * 80)
    print("PHASE 1: AUDIT RAW FILES")
    print("=" * 80)

    raw_audit = audit_all_raw_files()

    if len(raw_audit["corrupted"]) == 0:
        print("\n✅ No corrupted raw files found. Nothing to clean up.")
        return

    # Phase 2: Delete corrupted raw files
    print("\n" + "=" * 80)
    print("PHASE 2: DELETE CORRUPTED RAW FILES")
    print("=" * 80)

    raw_deletion = delete_corrupted_raw_files(raw_audit, dry_run=DRY_RUN)

    # Phase 3: Delete corrupted normalized files
    print("\n" + "=" * 80)
    print("PHASE 3: DELETE CORRUPTED NORMALIZED FILES")
    print("=" * 80)

    normalized_deletion = delete_corrupted_normalized_files(dry_run=DRY_RUN)

    # Phase 4: Validate post-cleanup
    validation_summary: dict | None = None
    if not DRY_RUN:
        print("\n" + "=" * 80)
        print("PHASE 4: POST-CLEANUP VALIDATION")
        print("=" * 80)

        validation = validate_post_cleanup()
        validation_summary = validation

        print("\nValidation snapshot:")
        raw_summary = validation.get("raw_audit", {})
        normalized_summary = validation.get("normalized_files", {})
        print(
            f"  Raw valid/corrupted/errors: "
            f"{len(raw_summary.get('valid', []))}/"
            f"{len(raw_summary.get('corrupted', []))}/"
            f"{len(raw_summary.get('errors', []))}"
        )
        print(
            "  Normalized counts - " + ", ".join(f"{k}: {v}" for k, v in normalized_summary.items())
        )

    # Generate report
    report = {
        "generated_at": datetime.now().isoformat(),
        "dry_run": DRY_RUN,
        "raw_audit": {
            "total_files": len(raw_audit["valid"])
            + len(raw_audit["corrupted"])
            + len(raw_audit["errors"]),
            "valid": len(raw_audit["valid"]),
            "corrupted": len(raw_audit["corrupted"]),
            "errors": len(raw_audit["errors"]),
        },
        "raw_deletion": raw_deletion,
        "normalized_deletion": normalized_deletion,
        "post_cleanup_validation": validation_summary,
    }

    # Save report
    report_file = (
        TOOLS_ROOT
        / f"uuid_fix_report_{'dryrun' if DRY_RUN else 'live'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 80}")
    print("FIX COMPLETE")
    print(f"{'=' * 80}")
    print(f"Report saved: {report_file}")

    if DRY_RUN:
        print("\n⚠️  THIS WAS A DRY RUN - NO FILES WERE ACTUALLY DELETED")
        print("To execute deletion, set DRY_RUN = False in this script")
    else:
        print("\n✅ Files have been deleted")
        print("Next steps:")
        print("  1. Fix create_normalized_tables.py (read UUID from data)")
        print("  2. Re-run normalization: python tools/lnb/create_normalized_tables.py")
        print("  3. Verify data integrity")


if __name__ == "__main__":
    main()
