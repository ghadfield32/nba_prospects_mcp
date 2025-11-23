#!/usr/bin/env python3
"""Remove duplicate base season keys, keep only league-specific keys"""

import json
from pathlib import Path

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

# Load mappings
with open(MAPPING_FILE, encoding="utf-8") as f:
    data = json.load(f)

print("Cleaning up duplicate base keys...")
print("=" * 80)

# Remove base keys that duplicate league-specific keys
keys_to_remove = []

# Check 2021-2022
if "2021-2022" in data["mappings"] and "2021-2022_elite_2" in data["mappings"]:
    base_count = len(data["mappings"]["2021-2022"])
    league_count = len(data["mappings"]["2021-2022_elite_2"])
    print(f"2021-2022: base has {base_count}, elite_2 has {league_count}")
    if base_count == league_count:
        keys_to_remove.append("2021-2022")
        print("  -> Will remove base key (duplicate)")

# Check 2022-2023
if "2022-2023" in data["mappings"] and "2022-2023_elite_2" in data["mappings"]:
    base_count = len(data["mappings"]["2022-2023"])
    league_count = len(data["mappings"]["2022-2023_elite_2"])
    print(f"\n2022-2023: base has {base_count}, elite_2 has {league_count}")
    if base_count == league_count:
        keys_to_remove.append("2022-2023")
        print("  -> Will remove base key (duplicate)")

# Remove duplicate keys
for key in keys_to_remove:
    del data["mappings"][key]
    print(f"\n[REMOVED] {key}")

# Save
with open(MAPPING_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 80)
print(f"[SUCCESS] Cleaned up {len(keys_to_remove)} duplicate keys")
print(f"Remaining keys: {len(data['mappings'])}")
