#!/usr/bin/env python3
"""Extract and document the PBP and shot data structure from captured JSON

This script analyzes the captured Atrium Sports API responses to document:
1. Play-by-play event structure
2. Shot chart data structure
3. API endpoint and parameters
"""

import io
import json
import sys
from pathlib import Path
from pprint import pprint

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

output_dir = Path(__file__).parent / "match_center_capture"

# Files identified by the analyzer
pbp_file = output_dir / "match_center_shots_pbp_unknown_v1_embed_12_fixture_detail_060232_56.json"
shot_file = (
    output_dir / "match_center_shots_shots_unknown_v1_embed_12_fixture_detail_060238_57.json"
)

print("=" * 80)
print("  LNB PLAY-BY-PLAY AND SHOT DATA STRUCTURE ANALYSIS")
print("=" * 80)
print()

# =============================================================================
# PLAY-BY-PLAY ANALYSIS
# =============================================================================
print("=" * 80)
print("  PLAY-BY-PLAY DATA STRUCTURE")
print("=" * 80)
print()

with open(pbp_file, encoding="utf-8") as f:
    pbp_data = json.load(f)

print(f"API Endpoint: {pbp_data['url']}")
print(f"Host: {pbp_data['host']}")
print(f"Path: {pbp_data['path']}")
print()

# Extract the fixture ID from URL
import re

fixture_id_match = re.search(r"fixtureId=([a-f0-9-]+)", pbp_data["url"])
if fixture_id_match:
    print(f"Fixture ID: {fixture_id_match.group(1)}")
print()

# Navigate to the pbp data
pbp = pbp_data["data"]["data"]["pbp"]
print(f"Number of periods: {len(pbp)}")
print(f"Period IDs: {list(pbp.keys())}")
print()

# Show sample events from first period
period_1 = pbp["1"]
print("Period 1 Info:")
print(f"  Duration: {period_1['durationMinutes']} minutes")
print(f"  Elapsed before period: {period_1['elapsedMinutesBeforePeriod']}")
print(f"  Ended: {period_1['ended']}")
print(f"  Number of events: {len(period_1['events'])}")
print()

# Show different event types
event_types = {}
for event in period_1["events"]:
    event_type = event.get("eventType")
    if event_type not in event_types:
        event_types[event_type] = event

print(f"Event types in period 1: {list(event_types.keys())}")
print()

# Show sample of each event type
for event_type, sample_event in list(event_types.items())[:5]:
    print(f"Sample '{event_type}' event:")
    pprint(sample_event, width=120)
    print()

# =============================================================================
# SHOT CHART ANALYSIS
# =============================================================================
print("=" * 80)
print("  SHOT CHART DATA STRUCTURE")
print("=" * 80)
print()

with open(shot_file, encoding="utf-8") as f:
    shot_data = json.load(f)

print(f"API Endpoint: {shot_data['url']}")
print()

# Navigate to shot chart data
shot_chart = shot_data["data"]["data"]["shotChart"]
shots = shot_chart["shots"]

print(f"Total shots: {len(shots)}")
print()

# Group shots by type
shot_types = {}
for shot in shots:
    event_type = shot.get("eventType")
    sub_type = shot.get("subType")
    key = f"{event_type} ({sub_type})"
    if key not in shot_types:
        shot_types[key] = shot

print(f"Shot types: {list(shot_types.keys())[:10]}")
print()

# Show sample shots
print("Sample shots:")
for i, shot in enumerate(shots[:5]):
    print(f"\nShot {i+1}:")
    pprint(shot, width=120)

# Show coordinate ranges
x_coords = [s["x"] for s in shots if "x" in s]
y_coords = [s["y"] for s in shots if "y" in s]

print()
print("=" * 80)
print("  COORDINATE SYSTEM")
print("=" * 80)
print(f"X coordinate range: {min(x_coords):.2f} to {max(x_coords):.2f}")
print(f"Y coordinate range: {min(y_coords):.2f} to {max(y_coords):.2f}")
print()

# Count made vs missed
made = sum(1 for s in shots if s.get("success"))
missed = sum(1 for s in shots if not s.get("success"))
print(f"Made shots: {made}")
print(f"Missed shots: {missed}")
print(f"Total: {made + missed}")
print()

# =============================================================================
# API PATTERN SUMMARY
# =============================================================================
print("=" * 80)
print("  API PATTERN SUMMARY")
print("=" * 80)
print()
print("Endpoint:")
print("  https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail")
print()
print("Required Parameters:")
print("  - state: Encoded state string (base64url?)")
print("  - fixtureId: Game UUID from LNB's getMatchDetails API")
print()
print("Response Structure:")
print("  - data.data.pbp: Play-by-play events nested by period")
print("  - data.data.shotChart.shots: Array of shot attempts with coordinates")
print()
print("Key Fields:")
print("  PBP Events: eventId, eventType, eventSubType, clock, periodId,")
print("              personId, entityId, name, bib, desc, scores")
print()
print("  Shots: eventId, eventType, subType, clock, periodId, personId,")
print("         entityId, name, bib, desc, success, x, y")
print()
print("=" * 80)
