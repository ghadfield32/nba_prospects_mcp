#!/usr/bin/env python3
"""Test calling Atrium API with minimal state parameters

Test if season ID is truly required, or if we can:
1. Omit it entirely
2. Use a placeholder
3. Get it from first call without state
"""

import base64
import io
import json
import sys
import zlib

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

FIXTURE_ID = "3522345e-3362-11f0-b97d-7be2bdc7a840"  # Nancy vs Saint-Quentin
API_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://lnb.fr/",
}


def create_state(state_obj):
    """Create a compressed+encoded state parameter"""
    json_str = json.dumps(state_obj, separators=(",", ":"))
    compressed = zlib.compress(json_str.encode("utf-8"))
    # Base64url encode
    encoded = base64.b64encode(compressed).decode("ascii")
    # Make it URL-safe
    encoded = encoded.replace("+", "-").replace("/", "_").rstrip("=")
    return encoded


def test_state(test_name, state_obj):
    """Test API call with given state"""
    print("=" * 80)
    print(f"  {test_name}")
    print("=" * 80)
    print()

    state = create_state(state_obj)
    print(f"State object: {state_obj}")
    print(f"Encoded state: {state[:50]}...")
    print()

    params = {"fixtureId": FIXTURE_ID, "state": state}

    try:
        response = requests.get(API_URL, params=params, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for key data
            has_pbp = "pbp" in data.get("data", {})
            has_shots = "shotChart" in data.get("data", {})

            print("✅ Success!")
            print(f"   Has 'pbp': {has_pbp}")
            print(f"   Has 'shotChart': {has_shots}")

            if has_pbp:
                pbp = data["data"]["pbp"]
                total_events = sum(len(p.get("events", [])) for p in pbp.values())
                print(f"   Total PBP events: {total_events}")

            if has_shots:
                shots = data["data"].get("shotChart", {}).get("shots", [])
                print(f"   Total shots: {len(shots)}")

            # Try to extract season ID from response
            season_id = data.get("data", {}).get("banner", {}).get("season", {}).get("id")
            if season_id:
                print(f"   Season ID from response: {season_id}")

            return True, data

        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None

    finally:
        print()


# =============================================================================
# TESTS
# =============================================================================

print("=" * 80)
print("  TESTING MINIMAL STATE PARAMETERS")
print("=" * 80)
print()

# Test 1: Minimal state (just view and fixture)
test_state("TEST 1: Minimal state (view + fixture only)", {"z": "pbp", "f": FIXTURE_ID})

# Test 2: With locale added
test_state("TEST 2: With locale added", {"l": "fr-FR", "z": "pbp", "f": FIXTURE_ID})

# Test 3: Try shots view
test_state("TEST 3: Shots view (minimal)", {"z": "shot_chart", "f": FIXTURE_ID})

# Test 4: Try placeholder season ID
test_state(
    "TEST 4: With placeholder season ID",
    {"s": "00000000-0000-0000-0000-000000000000", "l": "fr-FR", "z": "pbp", "f": FIXTURE_ID},
)

print("=" * 80)
print("  SUMMARY")
print("=" * 80)
print()
print("If any test succeeded, we can generate the state parameter without")
print("needing to know the season ID in advance!")
print()
