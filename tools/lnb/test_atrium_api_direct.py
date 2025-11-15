#!/usr/bin/env python3
"""Test calling the Atrium Sports API directly

This script tests different approaches to calling the Atrium API:
1. With the full state parameter from capture
2. With just the fixtureId (no state)
3. With an empty/minimal state parameter
"""

import io
import sys
from pprint import pprint

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Test fixture ID from our captures
FIXTURE_ID = "3522345e-3362-11f0-b97d-7be2bdc7a840"  # Nancy vs Saint-Quentin

# State parameter from capture (for reference)
STATE_FROM_CAPTURE = "eJwtjEEKhDAMAL8iORtIGmNbH-AD_EFr2pMH2b0p_l0C3mZgmBv-sAxgXZgKKSoXQ-ZOWC1l3KOoUmrcKMM4wOFx_-G6uV1uZz2du7NoCDJpQ5E5fJscDWNtodoeS5oInhdqtRxC"

API_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"

print("=" * 80)
print("  TESTING ATRIUM SPORTS API ACCESS")
print("=" * 80)
print()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://lnb.fr/",
}

# =============================================================================
# TEST 1: No state parameter (just fixtureId)
# =============================================================================
print("=" * 80)
print("  TEST 1: API call with just fixtureId (no state)")
print("=" * 80)
print()

params = {"fixtureId": FIXTURE_ID}

try:
    print(f"URL: {API_URL}")
    print(f"Params: {params}")
    print()

    response = requests.get(API_URL, params=params, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print()

    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS! Got JSON response")
        print()

        # Check if it has the pbp and shotChart keys
        if "data" in data:
            top_keys = list(data["data"].keys())[:10]
            print(f"Top-level data keys: {top_keys}")

            if "pbp" in data["data"]:
                pbp = data["data"]["pbp"]
                print(f"✅ Has 'pbp' key with {len(pbp)} periods")

                # Count total events
                total_events = sum(len(p.get("events", [])) for p in pbp.values())
                print(f"   Total PBP events: {total_events}")

            if "shotChart" in data["data"]:
                shots = data["data"].get("shotChart", {}).get("shots", [])
                print(f"✅ Has 'shotChart' key with {len(shots)} shots")
        else:
            print("Response structure:")
            pprint(data, depth=2)
    else:
        print(f"❌ FAILED with status {response.status_code}")
        print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"❌ ERROR: {e}")

print()

# =============================================================================
# TEST 2: With the state parameter from capture
# =============================================================================
print("=" * 80)
print("  TEST 2: API call with state parameter from capture")
print("=" * 80)
print()

params = {"fixtureId": FIXTURE_ID, "state": STATE_FROM_CAPTURE}

try:
    print(f"URL: {API_URL}")
    print(f"Params: fixtureId={FIXTURE_ID}, state=<captured_state>")
    print()

    response = requests.get(API_URL, params=params, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print()

    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS! Got JSON response with state parameter")

        # Compare with test 1 to see if state makes a difference
        if "data" in data:
            if "pbp" in data["data"]:
                pbp = data["data"]["pbp"]
                total_events = sum(len(p.get("events", [])) for p in pbp.values())
                print(f"   Total PBP events: {total_events}")

            if "shotChart" in data["data"]:
                shots = data["data"].get("shotChart", {}).get("shots", [])
                print(f"   Total shots: {len(shots)}")
    else:
        print(f"❌ FAILED with status {response.status_code}")

except Exception as e:
    print(f"❌ ERROR: {e}")

print()
print("=" * 80)
print("  SUMMARY")
print("=" * 80)
print()
print("If both tests succeeded, the 'state' parameter is likely optional!")
print("We can simply use fixtureId to get both PBP and shot data.")
print()
