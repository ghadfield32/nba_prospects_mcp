"""Test REAL ABA Liga game ID from web search"""

import requests

# Real game ID from web search
REAL_GAME_ID = "902695"

# Test both league codes
LEAGUE_CODES = ["ABAL", "ABA"]

print("=" * 70)
print("TESTING REAL ABA LIGA GAME ID: 902695")
print("=" * 70)

for league_code in LEAGUE_CODES:
    print(f"\n{'='*70}")
    print(f"Testing league code: {league_code}")
    print("=" * 70)

    # Test HTML endpoint
    html_url = (
        f"https://fibalivestats.dcd.shared.geniussports.com/u/{league_code}/{REAL_GAME_ID}/bs.html"
    )
    print(f"\nHTML URL: {html_url}")

    try:
        response = requests.get(html_url, timeout=30)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  [SUCCESS] Content-Length: {len(response.text)} bytes")
        else:
            print(f"  [FAILED] HTTP {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Test JSON endpoint
    json_url = f"https://fibalivestats.dcd.shared.geniussports.com/data/{REAL_GAME_ID}/data.json"
    print(f"\nJSON URL: {json_url}")

    try:
        response = requests.get(json_url, timeout=30)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  [SUCCESS] Content-Length: {len(response.text)} bytes")
            data = response.json()
            print(f"  [SUCCESS] JSON keys: {list(data.keys())[:15]}")
        else:
            print(f"  [FAILED] HTTP {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] {e}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("If ABAL works: Need to update league code from 'ABA' to 'ABAL'")
print("If both fail: Need to find current season game IDs")
print("=" * 70)
