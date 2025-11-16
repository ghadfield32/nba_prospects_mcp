#!/usr/bin/env python3
"""Clean bogus historical mappings from fixture_uuids_by_season.json

This script removes incorrectly assigned historical season mappings that
are actually current-round UUIDs scraped from the main calendar page.

Usage:
    uv run python tools/lnb/clean_bogus_historical_mappings.py
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

# ==============================================================================
# CONFIG
# ==============================================================================

TOOLS_DIR = Path("tools/lnb")
UUID_MAPPING_FILE = TOOLS_DIR / "fixture_uuids_by_season.json"
BACKUP_FILE = TOOLS_DIR / "fixture_uuids_by_season.json.backup"

# Seasons to remove (confirmed to be bogus - same UUIDs as current round)
BOGUS_SEASONS = ["2021-2022", "2022-2023", "2023-2024"]

# ==============================================================================
# MAIN LOGIC
# ==============================================================================


def main():
    print(f"\n{'='*80}")
    print("  CLEANING BOGUS HISTORICAL MAPPINGS")
    print(f"{'='*80}\n")

    if not UUID_MAPPING_FILE.exists():
        print(f"[ERROR] Mapping file not found: {UUID_MAPPING_FILE}")
        return

    # Load current mappings
    with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)

    mappings = data.get("mappings", {})

    print(f"Current mappings: {len(mappings)} seasons")
    print()

    # Create backup
    print(f"[BACKUP] Creating backup: {BACKUP_FILE.name}")
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Analyze duplicate UUIDs
    print("\n[ANALYSIS] Detecting duplicate UUID sets across seasons...")
    season_uuids = {season: set(uuids) for season, uuids in mappings.items()}

    duplicates = []
    for season1, uuids1 in season_uuids.items():
        for season2, uuids2 in season_uuids.items():
            if season1 < season2 and uuids1 == uuids2:
                duplicates.append((season1, season2, len(uuids1)))

    if duplicates:
        print(f"\n[FOUND] {len(duplicates)} duplicate UUID set(s):")
        for s1, s2, count in duplicates:
            print(f"  - {s1} and {s2} have identical {count} UUIDs")
    else:
        print("\n[OK] No duplicate UUID sets found")

    # Extract current-round UUIDs before deleting
    current_round_uuids = None
    if BOGUS_SEASONS[0] in mappings:
        current_round_uuids = mappings[BOGUS_SEASONS[0]]
        print(f"\n[INFO] Extracted {len(current_round_uuids)} current-round UUIDs")

    # Remove bogus seasons
    print(f"\n[CLEANUP] Removing {len(BOGUS_SEASONS)} bogus historical seasons:")
    removed_count = 0
    for season in BOGUS_SEASONS:
        if season in mappings:
            print(f"  ❌ Removing: {season} ({len(mappings[season])} UUIDs)")
            del mappings[season]
            removed_count += 1
        else:
            print(f"  ⚠️  Not found: {season}")

    # Add current-round entry if we extracted UUIDs
    if current_round_uuids:
        print(f"\n[ADD] Adding 'current_round' entry with {len(current_round_uuids)} UUIDs")
        mappings["current_round"] = current_round_uuids

    # Update metadata
    data["metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "total_seasons": len([k for k in mappings.keys() if k != "current_round"]),
        "total_games": sum(
            len(uuids) for season, uuids in mappings.items() if season != "current_round"
        ),
        "current_round_games": len(current_round_uuids) if current_round_uuids else 0,
        "last_cleaned": datetime.now().isoformat(),
    }

    data["mappings"] = mappings

    # Save cleaned file
    print(f"\n[SAVE] Writing cleaned mappings to {UUID_MAPPING_FILE.name}")
    with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print("  CLEANUP COMPLETE")
    print(f"{'='*80}")
    print(f"Seasons removed: {removed_count}")
    print(f"Seasons remaining: {data['metadata']['total_seasons']}")
    print(f"Current round UUIDs: {data['metadata']['current_round_games']}")
    print()
    print("✅ Mapping file cleaned!")
    print(f"📁 Backup saved to: {BACKUP_FILE}")
    print()


if __name__ == "__main__":
    main()
