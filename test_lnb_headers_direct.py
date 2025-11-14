#!/usr/bin/env python3
"""Standalone test for LNB API headers (no pandas dependency)"""

import sys
import json
sys.path.insert(0, '/home/user/nba_prospects_mcp')

# Direct import of just what we need
from src.cbb_data.fetchers.lnb_api import LNBClient

def test_headers():
    print("="*60)
    print("LNB API Headers Test")
    print("="*60)

    client = LNBClient()

    # Test 1: Live Match (we know this endpoint works from cURL)
    print("\n[TEST 1] Testing /match/getLiveMatch...")
    try:
        result = client.get_live_match()
        print(f"✅ SUCCESS! Got {len(result) if isinstance(result, list) else 'N/A'} live matches")
        if result:
            print(f"   Sample: {json.dumps(result[0] if isinstance(result, list) else result, indent=2)[:200]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 2: Get All Years
    print("\n[TEST 2] Testing /common/getAllYears...")
    try:
        result = client.get_all_years(end_year=2025)
        print(f"✅ SUCCESS! Got {len(result) if isinstance(result, list) else 'N/A'} years")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 3: Get Main Competitions
    print("\n[TEST 3] Testing /common/getMainCompetition...")
    try:
        result = client.get_main_competitions(year=2024)
        print(f"✅ SUCCESS! Got {len(result) if isinstance(result, list) else 'N/A'} competitions")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_headers()
