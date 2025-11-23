#!/usr/bin/env python3
"""Update Elite 2 mapping file with real Pro B seeds"""

import json
from pathlib import Path

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

# Real Elite 2 seeds provided by user
REAL_SEEDS = {
    "2023-2024_elite_2": [
        "e64f6824-1f34-11ee-a0bb-25b5a787b6b8",
        "e671a226-1f34-11ee-80ec-25b5a787b6b8",
        "e67f3e8f-1f34-11ee-b270-25b5a787b6b8",
        "e6c4cf66-1f34-11ee-80b1-25b5a787b6b8",
        "e6b151d3-1f34-11ee-b78b-25b5a787b6b8",
        # backup: "e710b550-1f34-11ee-abb8-25b5a787b6b8"
    ],
    "2022-2023_elite_2": [
        "8c5e30cd-11b1-11ed-a22a-9116c4e35037",
        "8c803ec2-11b1-11ed-9cc4-9116c4e35037",
        "8c6f5ffc-11b1-11ed-b8f6-9116c4e35037",
        "8c63c72a-11b1-11ed-97fa-9116c4e35037",
        "8c7514c0-11b1-11ed-b8fd-9116c4e35037",
        # backup: "8c9641ae-11b1-11ed-938c-9116c4e35037"
    ],
    "2021-2022_elite_2": [
        "8895cf04-f5da-11eb-9e98-b6300881631e",
        "888c2576-f5da-11eb-9e98-b6300881631e",
        "88879420-f5da-11eb-9e98-b6300881631e",
        "889f324c-f5da-11eb-9e98-b6300881631e",
        "7cc0b8a6-3702-11ec-a79c-1a67641f8d10",
    ],
}

# Load current mappings
with open(MAPPING_FILE, encoding="utf-8") as f:
    data = json.load(f)

# Update Elite 2 seeds
print("Updating Elite 2 seeds...")
for key, seeds in REAL_SEEDS.items():
    old_count = len(data["mappings"].get(key, []))
    data["mappings"][key] = seeds
    print(f"  {key}: {old_count} -> {len(seeds)} seeds")

# Save updated mappings
with open(MAPPING_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n[SUCCESS] Updated {MAPPING_FILE}")
print("Real Pro B seeds now in place for 2021-22, 2022-23, 2023-24")
