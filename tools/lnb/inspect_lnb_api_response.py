#!/usr/bin/env python3
"""Inspect actual raw response from LNB API

Previous script showed all responses have empty metadata.
Let's look at the actual JSON structure to understand what's being returned.
"""

import io
import json
import sys
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_endpoints import LNB_API

# Test UUIDs
VALID_UUID = "0d0504a0-6715-11f0-98ab-27e6e78614e1"  # Has 629 PBP events in Atrium
INVALID_UUID = "1515cca4-67e6-11f0-908d-9d1d3a927139"  # No PBP data in Atrium


def get_raw_response(uuid: str) -> dict:
    """Get raw LNB API response"""
    url = LNB_API.match_details(uuid)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    response = requests.get(url, headers=headers, timeout=10)

    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "json": response.json() if response.status_code == 200 else None,
        "text_preview": response.text[:500] if response.status_code != 200 else None,
    }


print("=" * 80)
print("LNB API RAW RESPONSE INSPECTION")
print("=" * 80)
print()

# Test valid UUID
print("VALID UUID (has Atrium data):")
print(f"UUID: {VALID_UUID}")
print()

valid_response = get_raw_response(VALID_UUID)
print(f"Status: {valid_response['status_code']}")
print()

if valid_response["json"]:
    print("JSON Response Structure:")
    print(json.dumps(valid_response["json"], indent=2)[:1000])  # First 1000 chars
    print()
    print(f"Full response has {len(json.dumps(valid_response['json']))} characters")

print()
print("-" * 80)
print()

# Test invalid UUID
print("INVALID UUID (no Atrium data):")
print(f"UUID: {INVALID_UUID}")
print()

invalid_response = get_raw_response(INVALID_UUID)
print(f"Status: {invalid_response['status_code']}")
print()

if invalid_response["json"]:
    print("JSON Response Structure:")
    print(json.dumps(invalid_response["json"], indent=2)[:1000])  # First 1000 chars
    print()
    print(f"Full response has {len(json.dumps(invalid_response['json']))} characters")

print()
print("=" * 80)
print("COMPARISON")
print("=" * 80)
print()

if valid_response["json"] and invalid_response["json"]:
    valid_keys = set(valid_response["json"].keys())
    invalid_keys = set(invalid_response["json"].keys())

    print(f"Valid response keys:   {sorted(valid_keys)}")
    print(f"Invalid response keys: {sorted(invalid_keys)}")
    print()

    if valid_keys == invalid_keys:
        print("✅ Both have same top-level keys")
    else:
        print("❌ Different keys:")
        print(f"   Only in valid:   {sorted(valid_keys - invalid_keys)}")
        print(f"   Only in invalid: {sorted(invalid_keys - valid_keys)}")

# Save full responses for manual inspection
output_dir = Path(__file__).parent / "api_responses"
output_dir.mkdir(exist_ok=True)

with open(output_dir / "lnb_api_valid_uuid.json", "w", encoding="utf-8") as f:
    json.dump(valid_response["json"], f, indent=2, ensure_ascii=False)

with open(output_dir / "lnb_api_invalid_uuid.json", "w", encoding="utf-8") as f:
    json.dump(invalid_response["json"], f, indent=2, ensure_ascii=False)

print()
print(f"Full responses saved to: {output_dir}/")
print("  - lnb_api_valid_uuid.json")
print("  - lnb_api_invalid_uuid.json")
