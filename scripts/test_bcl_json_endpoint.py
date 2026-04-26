#!/usr/bin/env python
"""Test alternative BCL JSON endpoint."""

import requests

FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"
test_game_id = "119854-VEF-DSK"

# Extract numeric ID from game_id
game_id_numeric = test_game_id.split("-")[0]  # "119854"

print("=" * 70)
print("BCL JSON ENDPOINT TEST")
print("=" * 70)
print(f"Game ID: {test_game_id}")
print(f"Numeric ID: {game_id_numeric}")
print()

# Try multiple URL patterns
url_patterns = [
    f"{FIBA_BASE_URL}/data/{game_id_numeric}/data.json",
    f"{FIBA_BASE_URL}/u/BCL/{game_id_numeric}/data.json",
    f"{FIBA_BASE_URL}/data/BCL/{game_id_numeric}/data.json",
    f"{FIBA_BASE_URL}/v1/BCL/games/{game_id_numeric}",
]

for i, url in enumerate(url_patterns, 1):
    print(f"Test {i}: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            print(f"  Content-Type: {response.headers.get('Content-Type')}")
            print(f"  Length: {len(response.text)} chars")
            print(f"  Preview: {response.text[:200]}")
            print("  [SUCCESS] Found working endpoint!")
            break
        else:
            print(f"  Response: {response.text[:200]}")

    except Exception as e:
        print(f"  ERROR: {e}")

    print()
