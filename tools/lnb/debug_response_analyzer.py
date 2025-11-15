#!/usr/bin/env python3
"""Analyze all captured JSON responses to find play-by-play and shot data

Enhanced version that:
- Shows host, page_type, section, response_type for each file
- Uses more generous keyword matching (includes French terms)
- Better heuristics for identifying PBP/shot candidates
"""

import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

output_dir = Path(__file__).parent / "match_center_capture"

print("=" * 80)
print("  Analyzing Captured JSON Responses")
print("=" * 80)
print()

# Get all JSON files
json_files = list(output_dir.glob("*.json"))
print(f"Found {len(json_files)} JSON files")
print()

# Enhanced keywords with French terms
pbp_keywords = [
    "period",
    "quarter",
    "periode",
    "quart",
    "time",
    "minute",
    "second",
    "temps",
    "event",
    "action",
    "play",
    "événement",
    "score",
    "home_score",
    "away_score",
    "points",
    "foul",
    "faute",
    "rebound",
    "rebond",
    "turnover",
    "perte",
    "assist",
    "passe",
    "3pt",
    "2pt",
    "free throw",
    "lancer franc",
    "substitution",
    "timeout",
    "temps mort",
]

shot_keywords = [
    "shot",
    "tir",
    "attempt",
    "tentative",
    "x",
    "y",
    "coord",
    "location",
    "position",
    "made",
    "miss",
    "réussi",
    "raté",
    "success",
    "fg2",
    "fg3",
    "three",
    "two",
    "trois",
    "zone",
    "angle",
    "distance",
    "secteur",
]

print("Analyzing files for play-by-play and shot data...")
print("-" * 80)

pbp_candidates = []
shot_candidates = []

for json_file in sorted(json_files):
    try:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        # Extract metadata from wrapper (if present)
        metadata = {
            "url": data.get("url", "unknown"),
            "host": data.get("host", "unknown"),
            "page_type": data.get("page_type", "unknown"),
            "section": data.get("section", "unknown"),
            "response_type": data.get("response_type", "unknown"),
        }

        # Get the actual response data
        response_data = data.get("data", {})
        if isinstance(response_data, dict):
            response_data = response_data.get("data", response_data)

        # Convert to string for keyword search
        data_str = json.dumps(response_data, ensure_ascii=False).lower()

        # Check for play-by-play keywords
        pbp_matches = sum(1 for kw in pbp_keywords if kw in data_str)
        shot_matches = sum(1 for kw in shot_keywords if kw in data_str)

        # More generous thresholds: 6+ PBP keywords or 5+ shot keywords
        is_pbp_candidate = pbp_matches >= 6
        is_shot_candidate = shot_matches >= 5

        # If significant matches, print details
        if is_pbp_candidate or is_shot_candidate:
            print(f"\n{'='*80}")
            print(f"FILE: {json_file.name}")
            print(f"{'='*80}")
            print(f"Host         : {metadata['host']}")
            print(f"Page type    : {metadata['page_type']}")
            print(f"Section      : {metadata['section']}")
            print(f"Response type: {metadata['response_type']}")
            print(f"PBP keywords matched : {pbp_matches}/{len(pbp_keywords)}")
            print(f"Shot keywords matched: {shot_matches}/{len(shot_keywords)}")
            print(f"URL: {metadata['url']}")

            # Track candidates
            if is_pbp_candidate:
                pbp_candidates.append({"file": json_file.name, "matches": pbp_matches, **metadata})
            if is_shot_candidate:
                shot_candidates.append(
                    {"file": json_file.name, "matches": shot_matches, **metadata}
                )

            # Show data structure
            if isinstance(response_data, dict):
                print("Data type: dict")
                print(f"Top-level keys: {list(response_data.keys())[:15]}")

                # Look for arrays that might be events/shots
                for key, value in response_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        print(f"  Array '{key}': {len(value)} items")
                        if len(value) > 0 and isinstance(value[0], dict):
                            print(f"    First item keys: {list(value[0].keys())[:10]}")
            elif isinstance(response_data, list):
                print(f"Data type: list with {len(response_data)} items")
                if len(response_data) > 0 and isinstance(response_data[0], dict):
                    print(f"First item keys: {list(response_data[0].keys())[:15]}")

            # Sample of the data
            sample = json.dumps(response_data, indent=2, ensure_ascii=False)[:500]
            print("\nData sample:")
            print(sample)
            print("...")

    except Exception as e:
        print(f"Error processing {json_file.name}: {e}")

print()
print("=" * 80)
print("  Analysis Summary")
print("=" * 80)
print()

if pbp_candidates:
    print(f"🎯 Found {len(pbp_candidates)} PLAY-BY-PLAY candidates:")
    for candidate in sorted(pbp_candidates, key=lambda x: x["matches"], reverse=True):
        print(f"  ✓ {candidate['file']}")
        print(
            f"    Section: {candidate['section']} | Matches: {candidate['matches']} | Host: {candidate['host']}"
        )
else:
    print("❌ No play-by-play candidates found")
    print("   Make sure the script clicked the 'PLAY BY PLAY' tab and captured responses!")

print()

if shot_candidates:
    print(f"🎯 Found {len(shot_candidates)} SHOT DATA candidates:")
    for candidate in sorted(shot_candidates, key=lambda x: x["matches"], reverse=True):
        print(f"  ✓ {candidate['file']}")
        print(
            f"    Section: {candidate['section']} | Matches: {candidate['matches']} | Host: {candidate['host']}"
        )
else:
    print("❌ No shot data candidates found")
    print("   Make sure the script clicked the 'POSITIONS TIRS' tab and captured responses!")

print()
print("=" * 80)
print("  Next Steps")
print("=" * 80)
print()
print("1. Review the candidate files above (highest match count first)")
print("2. Open the JSON files to inspect the actual structure")
print("3. Look for arrays of events/plays (PBP) or shot coordinates (shots)")
print("4. Use those structures to implement fetch_lnb_play_by_play() and fetch_lnb_shots()")
print()
