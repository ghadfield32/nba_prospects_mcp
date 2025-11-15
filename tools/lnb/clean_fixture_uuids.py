#!/usr/bin/env python3
"""Clean and validate fixture_uuids_by_season.json

Fixes nested structure issues and ensures proper format.
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Load existing file
uuid_file = Path(__file__).parent / "fixture_uuids_by_season.json"

with open(uuid_file, encoding="utf-8") as f:
    data = json.load(f)

# Extract mappings (handle nested structure)
mappings = data.get("mappings", {})

# Clean up nested structure
cleaned_mappings = {}
for key, value in mappings.items():
    if key == "metadata":
        continue  # Skip metadata inside mappings
    if key == "mappings":
        # This is the nested mappings - merge it
        if isinstance(value, dict):
            for season, uuids in value.items():
                if season != "metadata" and isinstance(uuids, list):
                    # Deduplicate with outer level
                    if season not in cleaned_mappings:
                        cleaned_mappings[season] = uuids
    elif isinstance(value, list):
        # This is a season -> UUID list mapping
        cleaned_mappings[key] = value

# Deduplicate UUIDs within each season
for season in cleaned_mappings:
    # Preserve order while deduplicating
    seen = set()
    unique_uuids = []
    for uuid in cleaned_mappings[season]:
        if uuid not in seen:
            seen.add(uuid)
            unique_uuids.append(uuid)
    cleaned_mappings[season] = unique_uuids

# Create clean structure
clean_data = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "total_seasons": len(cleaned_mappings),
        "total_games": sum(len(uuids) for uuids in cleaned_mappings.values()),
    },
    "mappings": cleaned_mappings,
}

# Save cleaned file
with open(uuid_file, "w", encoding="utf-8") as f:
    json.dump(clean_data, f, indent=2, ensure_ascii=False)

print("✅ Cleaned fixture UUID file")
print(f"   Seasons: {clean_data['metadata']['total_seasons']}")
print(f"   Total games: {clean_data['metadata']['total_games']}")
print()

for season, uuids in sorted(cleaned_mappings.items()):
    print(f"   {season}: {len(uuids)} games")
