"""Test Exposure Events API Accessibility

Quick test to verify if OTE uses Exposure Events platform with public JSON API.
"""

import sys

sys.path.insert(0, "src")

import requests

# Test various potential API endpoints
BASE_URL = "https://overtimeelite.com"
API_ENDPOINTS = [
    "/api/v1/events",
    "/api/v1/games",
    "/api/events",
    "/api/games",
    "/api/schedule",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}

print("=" * 80)
print("Testing Exposure Events API Endpoints")
print("=" * 80)

for endpoint in API_ENDPOINTS:
    url = f"{BASE_URL}{endpoint}"
    print(f"\nTesting: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            print(f"  Content-Type: {response.headers.get('Content-Type')}")
            print(f"  Length: {len(response.text)} bytes")

            # Try to parse as JSON
            try:
                data = response.json()
                print("  ✅ Valid JSON response!")
                print(f"  Type: {type(data)}")
                if isinstance(data, list):
                    print(f"  Items: {len(data)}")
                elif isinstance(data, dict):
                    print(f"  Keys: {list(data.keys())[:5]}")
            except Exception as e:
                print(f"  ❌ Not JSON: {e}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "=" * 80)
print("Testing Complete")
print("=" * 80)
