#!/usr/bin/env python3
"""Debug the actual PBP data structure

The previous debug showed that valid UUID has:
  "pbp_keys": ["1", "2", "3", "4"]

But my code was looking for:
  periods = pbp_data.get("periods", [])  # WRONG!

The structure uses period numbers as keys, not a "periods" array!
"""

import io
import sys
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb import _create_atrium_state

ATRIUM_API_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"

# Test UUIDs
VALID_UUID = "0d0504a0-6715-11f0-98ab-27e6e78614e1"  # Known to have 629 events
INVALID_UUID = "1515cca4-67e6-11f0-908d-9d1d3a927139"  # Returns empty


def get_raw_pbp_structure(uuid: str) -> dict:
    """Get raw PBP structure from Atrium API"""
    state = _create_atrium_state(uuid, "pbp")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    params = {"fixtureId": uuid, "state": state}

    response = requests.get(ATRIUM_API_URL, params=params, headers=headers, timeout=10)

    data = response.json()
    return data.get("data", {}).get("pbp", {})


print("=" * 80)
print("PBP STRUCTURE ANALYSIS")
print("=" * 80)
print()

# Test valid UUID
print("VALID UUID (should have 629 events):")
print(f"UUID: {VALID_UUID}")
print()

valid_pbp = get_raw_pbp_structure(VALID_UUID)
print(f"Type of pbp object: {type(valid_pbp)}")
print(f"Keys in pbp object: {list(valid_pbp.keys())}")
print()

# Count events properly
if isinstance(valid_pbp, dict):
    total_events = 0
    for period_key in valid_pbp.keys():
        period_data = valid_pbp[period_key]
        if isinstance(period_data, dict):
            events = period_data.get("events", [])
            num_events = len(events)
            total_events += num_events
            print(f"  Period {period_key}: {num_events} events")

    print()
    print(f"Total events (correct counting): {total_events}")
print()
print()

# Test invalid UUID
print("INVALID UUID (should have 0 events):")
print(f"UUID: {INVALID_UUID}")
print()

invalid_pbp = get_raw_pbp_structure(INVALID_UUID)
print(f"Type of pbp object: {type(invalid_pbp)}")
print(f"Keys in pbp object: {list(invalid_pbp.keys())}")
print(f"Is empty dict? {invalid_pbp == {}}")
print()

if isinstance(invalid_pbp, dict) and invalid_pbp:
    total_events = 0
    for period_key in invalid_pbp.keys():
        period_data = invalid_pbp[period_key]
        if isinstance(period_data, dict):
            events = period_data.get("events", [])
            num_events = len(events)
            total_events += num_events
            print(f"  Period {period_key}: {num_events} events")

    print()
    print(f"Total events: {total_events}")
else:
    print("  PBP data is empty dict - NO GAME DATA AVAILABLE")

print()
print("=" * 80)
print("CONCLUSION")
print("=" * 80)
print()
print("The PBP structure uses period numbers as KEYS (e.g., '1', '2', '3', '4'),")
print("NOT a 'periods' array!")
print()
print("Valid games have:")
print("  pbp = {'1': {...}, '2': {...}, '3': {...}, '4': {...}}")
print()
print("Invalid games have:")
print("  pbp = {}  (empty dict)")
print()
print("My previous debug script had a bug - it was looking for")
print("pbp_data.get('periods', []) which doesn't exist!")
