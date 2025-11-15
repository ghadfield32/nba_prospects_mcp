#!/usr/bin/env python3
"""Fix UUID file with correct season labels based on actual match dates

Issue discovered: UUIDs were mislabeled.
- 9 UUIDs labeled as "2022-2023" are actually "2024-2025" (and haven't been played yet)
- Need to organize by ACTUAL season based on match dates
- Separate COMPLETE games (have data) from SCHEDULED games (future, no data yet)
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# UUID analysis results (from previous check)
UUID_ANALYSIS = {
    # 2021-2022 (1 game)
    "7d414bce-f5da-11eb-b3fd-a23ac5ab90da": ("2021-2022", "2021-11-18", "COMPLETE"),
    # 2022-2023 (1 game)
    "cc7e470e-11a0-11ed-8ef5-8d12cdc95909": ("2022-2023", "2022-11-18", "COMPLETE"),
    # 2023-2024 (1 game)
    "3fcea9a1-1f10-11ee-a687-db190750bdda": ("2023-2024", "2023-11-15", "COMPLETE"),
    # 2024-2025 COMPLETE (7 games)
    "0cac6e1b-6715-11f0-a9f3-27e6e78614e1": ("2024-2025", "2025-10-31", "COMPLETE"),
    "0cd1323f-6715-11f0-86f4-27e6e78614e1": ("2024-2025", "2025-11-08", "COMPLETE"),
    "0ce02919-6715-11f0-9d01-27e6e78614e1": ("2024-2025", "2025-11-09", "COMPLETE"),
    "0d0504a0-6715-11f0-98ab-27e6e78614e1": ("2024-2025", "2025-11-14", "COMPLETE"),
    # 2024-2025 SCHEDULED (9 games - future, no data yet)
    "1515cca4-67e6-11f0-908d-9d1d3a927139": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "0d346b41-6715-11f0-b247-27e6e78614e1": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "0d2989af-6715-11f0-b609-27e6e78614e1": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "0d0c88fe-6715-11f0-9d9c-27e6e78614e1": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "14fa0584-67e6-11f0-8cb3-9d1d3a927139": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "0d225fad-6715-11f0-810f-27e6e78614e1": ("2024-2025", "2025-11-16", "SCHEDULED"),
    "0cfdeaf9-6715-11f0-87bc-27e6e78614e1": ("2024-2025", "2025-11-15", "SCHEDULED"),
    "0cf637f3-6715-11f0-b9ed-27e6e78614e1": ("2024-2025", "2025-11-16", "SCHEDULED"),
    "0d141f9e-6715-11f0-bf7e-27e6e78614e1": ("2024-2025", "2025-11-15", "SCHEDULED"),
}

print("=" * 80)
print("FIXING UUID FILE WITH CORRECT SEASONS")
print("=" * 80)
print()

# Organize by season and status
by_season_complete = {}
by_season_scheduled = {}

for uuid, (season, _date, status) in UUID_ANALYSIS.items():
    if status == "COMPLETE":
        if season not in by_season_complete:
            by_season_complete[season] = []
        by_season_complete[season].append(uuid)
    elif status == "SCHEDULED":
        if season not in by_season_scheduled:
            by_season_scheduled[season] = []
        by_season_scheduled[season].append(uuid)

# Create corrected UUID file (COMPLETE games only)
complete_uuids = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "corrected_at": datetime.now().isoformat(),
        "total_seasons": len(by_season_complete),
        "total_games": sum(len(uuids) for uuids in by_season_complete.values()),
        "note": "Contains only COMPLETE games with confirmed PBP/shot data. SCHEDULED games excluded until played.",
        "correction_reason": "Previous file had 9 UUIDs mislabeled as 2022-2023 when they were actually 2024-2025 SCHEDULED games",
    },
    "mappings": by_season_complete,
}

# Save corrected file
output_file = Path(__file__).parent / "fixture_uuids_by_season.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(complete_uuids, f, indent=2, ensure_ascii=False)

print(f"✅ Created corrected UUID file: {output_file.name}")
print()
print("COMPLETE GAMES (have PBP data):")
print("-" * 80)
for season in sorted(by_season_complete.keys()):
    print(f"  {season:15s} {len(by_season_complete[season]):2d} games")

print()
print(f"Total: {complete_uuids['metadata']['total_games']} games")
print()

# Create scheduled games file for reference
scheduled_uuids = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "total_seasons": len(by_season_scheduled),
        "total_games": sum(len(uuids) for uuids in by_season_scheduled.values()),
        "note": "These are SCHEDULED games (not yet played). Check back after match dates for PBP data.",
    },
    "mappings": by_season_scheduled,
}

scheduled_file = Path(__file__).parent / "fixture_uuids_scheduled.json"

with open(scheduled_file, "w", encoding="utf-8") as f:
    json.dump(scheduled_uuids, f, indent=2, ensure_ascii=False)

print(f"ℹ️  Created scheduled games file: {scheduled_file.name}")
print()
print("SCHEDULED GAMES (future, no data yet):")
print("-" * 80)
for season in sorted(by_season_scheduled.keys()):
    print(f"  {season:15s} {len(by_season_scheduled[season]):2d} games")

print()
print(f"Total: {scheduled_uuids['metadata']['total_games']} games")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("✅ Fixed UUID file with correct season labels")
print(f"✅ Separated {complete_uuids['metadata']['total_games']} COMPLETE games (have data)")
print(f"ℹ️  Tracked {scheduled_uuids['metadata']['total_games']} SCHEDULED games (check back later)")
print()
print("ACTUAL SEASON COVERAGE (COMPLETE games):")
print()

for season in ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]:
    count = len(by_season_complete.get(season, []))
    if count > 0:
        print(f"  {season}: {count} games ✅")
    else:
        print(f"  {season}: 0 games (need to discover more UUIDs)")

print()
print("RECOMMENDATIONS:")
print()
print("1. ✅ IMMEDIATE: Run coverage report on corrected file")
print("   uv run python tools/lnb/stress_test_coverage.py --report")
print()
print("2. 📋 EXPAND: Discover more 2024-2025 COMPLETE games")
print("   - Current season is ongoing (many more completed games available)")
print("   - Use discover_historical_fixture_uuids.py for automated discovery")
print()
print("3. 📋 EXPAND: Discover 2023-2024 season games")
print("   - We only have 1 game from this season")
print("   - Last season should have ~300+ games available")
print()
print("4. 📋 EXPAND: Discover 2022-2023 and older seasons")
print("   - Test how far back Atrium API has data")
print("   - Systematically collect UUIDs from each season")
print()
print("5. ⏰ WAIT: Check back for SCHEDULED games after they're played")
print("   - 9 games scheduled for 2025-11-15 and 2025-11-16")
print("   - Will have PBP data after completion")
