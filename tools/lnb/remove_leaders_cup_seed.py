#!/usr/bin/env python3
"""Remove Leaders Cup seed from 2021-22 Elite 2 mapping"""

import json
from pathlib import Path

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")
LEADERS_CUP_UUID = "7cc0b8a6-3702-11ec-a79c-1a67641f8d10"

# Load mappings
with open(MAPPING_FILE, encoding="utf-8") as f:
    data = json.load(f)

# Remove Leaders Cup seed
seeds = data["mappings"]["2021-2022_elite_2"]
if LEADERS_CUP_UUID in seeds:
    seeds.remove(LEADERS_CUP_UUID)
    data["mappings"]["2021-2022_elite_2"] = seeds

    # Save
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("[SUCCESS] Removed Leaders Cup seed")
    print(f"New 2021-2022_elite_2 count: {len(seeds)}")
else:
    print("[INFO] Leaders Cup seed not found in mapping")
