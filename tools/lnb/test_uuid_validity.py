#!/usr/bin/env python3
"""Test which UUIDs actually have data available"""

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# Load all UUIDs
uuid_file = Path(__file__).parent / "fixture_uuids_by_season.json"
with open(uuid_file) as f:
    data = json.load(f)

mappings = data.get("mappings", {})

print("=" * 80)
print("UUID VALIDITY TEST")
print("=" * 80)
print()

valid_uuids = {}
invalid_uuids = {}

for season, uuids in sorted(mappings.items()):
    print(f"\n{season}:")
    print("-" * 80)

    valid_season = []
    invalid_season = []

    for uuid in uuids:
        print(f"  {uuid[:30]}... ", end="")

        try:
            pbp = fetch_lnb_play_by_play(uuid)
            shots = fetch_lnb_game_shots(uuid)

            if not pbp.empty and not shots.empty:
                print(f"✅ PBP:{len(pbp):3d} Shots:{len(shots):3d}")
                valid_season.append(uuid)
            else:
                print(f"❌ Empty (PBP:{len(pbp)} Shots:{len(shots)})")
                invalid_season.append(uuid)
        except Exception as e:
            print(f"❌ Error: {str(e)[:40]}")
            invalid_season.append(uuid)

    valid_uuids[season] = valid_season
    invalid_uuids[season] = invalid_season

    print(f"\n  Valid: {len(valid_season)}/{len(uuids)}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print()

total_valid = sum(len(v) for v in valid_uuids.values())
total_invalid = sum(len(v) for v in invalid_uuids.values())

for season in sorted(valid_uuids.keys()):
    print(
        f"{season:15s}  Valid: {len(valid_uuids[season]):2d}  Invalid: {len(invalid_uuids[season]):2d}"
    )

print(f"\n{'TOTAL':15s}  Valid: {total_valid:2d}  Invalid: {total_invalid:2d}")

# Save valid UUIDs to new file
if total_valid > 0:
    valid_file = Path(__file__).parent / "fixture_uuids_by_season_VALIDATED.json"
    valid_data = {
        "metadata": {
            "generated_at": data.get("metadata", {}).get("generated_at"),
            "validated_at": "2025-11-15",
            "total_seasons": len([s for s, uuids in valid_uuids.items() if uuids]),
            "total_games": total_valid,
            "validation_method": "Atrium API test (fetch_lnb_play_by_play + fetch_lnb_shots)",
        },
        "mappings": {s: uuids for s, uuids in valid_uuids.items() if uuids},
    }

    with open(valid_file, "w", encoding="utf-8") as f:
        json.dump(valid_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {total_valid} validated UUIDs to: {valid_file.name}")
