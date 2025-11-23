#!/usr/bin/env python3
"""Validate discovered fixture UUIDs by testing against Atrium API

This script tests each discovered UUID to verify:
1. UUID format is valid (36-char hex with dashes)
2. Atrium API accepts the UUID
3. PBP and shots data are available for the game

Usage:
    # Validate all seasons
    uv run python tools/lnb/validate_discovered_uuids.py

    # Validate specific season
    uv run python tools/lnb/validate_discovered_uuids.py --season 2023-2024

Output:
    - Console report of validation results
    - Updates fixture_uuids_by_season.json to remove invalid UUIDs
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# ==============================================================================
# CONFIG
# ==============================================================================

UUID_MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

# UUID format validation
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def is_valid_uuid_format(uuid: str) -> bool:
    """Check if UUID matches expected format

    Args:
        uuid: String to validate

    Returns:
        True if valid UUID format
    """
    return UUID_PATTERN.match(uuid) is not None


def validate_uuid_against_api(uuid: str) -> tuple[bool, str]:
    """Test UUID against Atrium API

    Args:
        uuid: Fixture UUID to test

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Try to fetch PBP data
        pbp_df = fetch_lnb_play_by_play(uuid)

        if pbp_df.empty:
            return (False, "No PBP data returned")

        # Try to fetch shots data
        shots_df = fetch_lnb_game_shots(uuid)

        if shots_df.empty:
            return (True, f"PBP OK ({len(pbp_df)} events), no shots data")

        return (True, f"PBP OK ({len(pbp_df)} events), Shots OK ({len(shots_df)} shots)")

    except Exception as e:
        return (False, f"API error: {str(e)[:100]}")


def validate_season_uuids(season: str, uuids: list[str]) -> dict[str, any]:
    """Validate all UUIDs for a season

    Args:
        season: Season string (e.g., "2023-2024")
        uuids: List of UUIDs to validate

    Returns:
        Dict with validation results
    """
    print(f"\n[VALIDATING] Season {season} ({len(uuids)} UUIDs)...")

    results = {
        "season": season,
        "total": len(uuids),
        "valid_format": 0,
        "invalid_format": 0,
        "api_success": 0,
        "api_failure": 0,
        "valid_uuids": [],
        "invalid_uuids": [],
    }

    for i, uuid in enumerate(uuids, 1):
        print(f"  [{i}/{len(uuids)}] {uuid[:16]}...", end=" ")

        # Check format
        if not is_valid_uuid_format(uuid):
            print("❌ Invalid format")
            results["invalid_format"] += 1
            results["invalid_uuids"].append(uuid)
            continue

        results["valid_format"] += 1

        # Check API
        success, message = validate_uuid_against_api(uuid)

        if success:
            print(f"✅ {message}")
            results["api_success"] += 1
            results["valid_uuids"].append(uuid)
        else:
            print(f"❌ {message}")
            results["api_failure"] += 1
            results["invalid_uuids"].append(uuid)

    return results


def load_uuid_mappings() -> dict[str, list[str]]:
    """Load UUID mappings from JSON file"""
    if not UUID_MAPPING_FILE.exists():
        print(f"[ERROR] UUID mapping file not found: {UUID_MAPPING_FILE}")
        return {}

    try:
        with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mappings", {})
    except Exception as e:
        print(f"[ERROR] Failed to load UUID mappings: {e}")
        return {}


def save_cleaned_mappings(mappings: dict[str, list[str]]) -> None:
    """Save cleaned UUID mappings (removing invalid UUIDs)"""
    try:
        output = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_seasons": len(mappings),
                "total_games": sum(len(uuids) for uuids in mappings.values()),
            },
            "mappings": mappings,
        }

        with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] Cleaned UUID mappings: {UUID_MAPPING_FILE}")

    except Exception as e:
        print(f"\n[ERROR] Failed to save cleaned mappings: {e}")


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Validate discovered fixture UUIDs against Atrium API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help="Specific season to validate (default: all seasons)",
    )

    parser.add_argument(
        "--remove-invalid", action="store_true", help="Remove invalid UUIDs from mapping file"
    )

    args = parser.parse_args()

    print(f"{'='*80}")
    print("  LNB FIXTURE UUID VALIDATION")
    print(f"{'='*80}\n")

    # Load mappings
    mappings = load_uuid_mappings()

    if not mappings:
        print("[ERROR] No UUID mappings to validate")
        return

    # Filter by season if specified
    if args.season:
        if args.season not in mappings:
            print(f"[ERROR] Season '{args.season}' not found in mappings")
            return
        mappings = {args.season: mappings[args.season]}

    # Validate each season
    all_results = []
    for season, uuids in mappings.items():
        results = validate_season_uuids(season, uuids)
        all_results.append(results)

    # Print summary
    print(f"\n{'='*80}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*80}\n")

    total_uuids = sum(r["total"] for r in all_results)
    total_valid = sum(r["api_success"] for r in all_results)
    total_invalid = sum(r["api_failure"] + r["invalid_format"] for r in all_results)

    print(f"Total UUIDs tested: {total_uuids}")
    print(f"Valid (API confirmed): {total_valid} ({total_valid/total_uuids*100:.1f}%)")
    print(f"Invalid: {total_invalid} ({total_invalid/total_uuids*100:.1f}%)")
    print()

    for results in all_results:
        print(f"{results['season']:12s}: {results['api_success']:3d}/{results['total']:3d} valid")

    # Remove invalid UUIDs if requested
    if args.remove_invalid and total_invalid > 0:
        print(f"\n[CLEANING] Removing {total_invalid} invalid UUIDs...")

        cleaned_mappings = {}
        for results in all_results:
            if results["valid_uuids"]:
                cleaned_mappings[results["season"]] = results["valid_uuids"]

        save_cleaned_mappings(cleaned_mappings)

    print()


if __name__ == "__main__":
    from datetime import datetime

    main()
