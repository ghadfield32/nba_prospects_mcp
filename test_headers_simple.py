#!/usr/bin/env python3
"""Simple test of LNB API headers using requests directly"""

import requests
import json

# Load headers from config
with open('/home/user/nba_prospects_mcp/tools/lnb/lnb_headers.json', 'r') as f:
    custom_headers = json.load(f)

# Base headers
headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.lnb.fr/",
}

# Merge custom headers
headers.update(custom_headers)

print("=" * 60)
print("LNB API Headers Test (Direct)")
print("=" * 60)
print(f"\nLoaded {len(custom_headers)} custom headers")
print(f"Total headers: {len(headers)}")

# Test endpoints
base_url = "https://api-prod.lnb.fr"

endpoints = [
    ("/match/getLiveMatch", {}),
    ("/common/getAllYears", {"end_year": 2025}),
    ("/common/getMainCompetition", {"year": 2024}),
]

for path, params in endpoints:
    url = f"{base_url}{path}"
    print(f"\n[TEST] {path}")
    print(f"URL: {url}")
    print(f"Params: {params}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Status: {resp.status_code} {resp.reason}")

        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, dict):
                    print(f"✅ SUCCESS! Keys: {list(data.keys())}")
                    if "data" in data:
                        d = data["data"]
                        if isinstance(d, list):
                            print(f"   Data: list with {len(d)} items")
                        elif isinstance(d, dict):
                            print(f"   Data: dict with keys {list(d.keys())[:5]}")
                elif isinstance(data, list):
                    print(f"✅ SUCCESS! List with {len(data)} items")
            except Exception as e:
                print(f"⚠️  Got 200 but JSON parse failed: {e}")
        else:
            print(f"❌ FAILED: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
