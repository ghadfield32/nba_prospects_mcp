#!/usr/bin/env python3
"""Relocate Pro B fixtures from base season keys to league-specific keys"""

import json
from pathlib import Path

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

# Load mappings
with open(MAPPING_FILE, encoding="utf-8") as f:
    data = json.load(f)

print("Relocating Pro B fixtures to league-specific keys...")
print("=" * 80)

# 2021-2022: Move from "2021-2022" to "2021-2022_elite_2"
if "2021-2022" in data["mappings"]:
    prob_2122 = data["mappings"]["2021-2022"]
    existing_2122 = data["mappings"].get("2021-2022_elite_2", [])

    # Combine and deduplicate
    combined = list(set(prob_2122 + existing_2122))

    print("2021-2022:")
    print(f"  Moved {len(prob_2122)} fixtures from '2021-2022'")
    print(f"  Combined with {len(existing_2122)} existing in '2021-2022_elite_2'")
    print(f"  Total unique: {len(combined)}")

    data["mappings"]["2021-2022_elite_2"] = combined
    del data["mappings"]["2021-2022"]

# 2022-2023: Move from "2022-2023" to "2022-2023_elite_2"
if "2022-2023" in data["mappings"]:
    prob_2223 = data["mappings"]["2022-2023"]
    existing_2223 = data["mappings"].get("2022-2023_elite_2", [])

    # Combine and deduplicate
    combined = list(set(prob_2223 + existing_2223))

    print("\n2022-2023:")
    print(f"  Moved {len(prob_2223)} fixtures from '2022-2023'")
    print(f"  Combined with {len(existing_2223)} existing in '2022-2023_elite_2'")
    print(f"  Total unique: {len(combined)}")

    data["mappings"]["2022-2023_elite_2"] = combined
    del data["mappings"]["2022-2023"]

# Save updated mappings
with open(MAPPING_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 80)
print(f"[SUCCESS] Updated {MAPPING_FILE}")
print("Pro B fixtures now in league-specific keys")
