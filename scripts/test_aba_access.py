#!/usr/bin/env python
"""Test if ABA (Adriatic League) is also blocked like BCL."""

import sys
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.fetchers.browser_scraper import BrowserScraper  # noqa: E402

FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"
test_game_id = "1"  # CIB vs ZAD, 69-87, 2024-09-20

print("=" * 70)
print("ABA (ADRIATIC LEAGUE) ACCESS TEST")
print("=" * 70)
print(f"Game ID: {test_game_id}")
print("Expected: CIB vs ZAD, 69-87, 2024-09-20")
print()

# Test 1: HTTP request
print("Test 1: HTTP Request")
print("-" * 70)
url_http = f"{FIBA_BASE_URL}/u/ABA/{test_game_id}/bs.html"
print(f"URL: {url_http}")

try:
    response = requests.get(url_http, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Length: {len(response.text)} chars")

    if response.status_code == 200:
        print("[SUCCESS] HTTP request worked!")
        print(f"Preview: {response.text[:300]}")
        http_success = True
    else:
        print(f"[FAIL] Status {response.status_code}")
        print(f"Response: {response.text[:200]}")
        http_success = False

except Exception as e:
    print(f"[ERROR] {e}")
    http_success = False

print()

# Test 2: Playwright browser
print("Test 2: Playwright Browser Rendering")
print("-" * 70)

try:
    with BrowserScraper(headless=True, timeout=30000) as scraper:
        url_browser = f"{FIBA_BASE_URL}/u/ABA/{test_game_id}/bs.html"
        print(f"URL: {url_browser}")

        # Fetch without waiting for selector (to see what we get)
        html = scraper.get_rendered_html(url_browser, wait_time=5.0)

        print(f"HTML Length: {len(html)} chars")

        # Check if it's a 403 error page
        if "403 Forbidden" in html or "AccessDenied" in html:
            print("[FAIL] Blocked with 403 Forbidden")
            print(f"Response: {html[:300]}")
            playwright_success = False
        elif len(html) < 500:
            print("[FAIL] Response too small (likely error page)")
            print(f"Response: {html[:300]}")
            playwright_success = False
        else:
            print("[SUCCESS] Playwright fetched substantial HTML")
            print(f"Preview: {html[:300]}")

            # Check if player tables exist
            if "teamBoxscore" in html or "player" in html.lower():
                print("[SUCCESS] Found player table indicators")
                playwright_success = True
            else:
                print("[WARN] No player table indicators found")
                playwright_success = False

except Exception as e:
    print(f"[ERROR] {e}")
    playwright_success = False

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"HTTP Request: {'✓ WORKS' if http_success else '✗ BLOCKED'}")
print(f"Playwright:   {'✓ WORKS' if playwright_success else '✗ BLOCKED'}")
print()

if http_success or playwright_success:
    print("CONCLUSION: ABA is ACCESSIBLE (unlike BCL)")
    print("  - At least one method works for fetching data")
else:
    print("CONCLUSION: ABA is also BLOCKED (like BCL)")
    print("  - Entire FIBA LiveStats infrastructure may be restricted")
