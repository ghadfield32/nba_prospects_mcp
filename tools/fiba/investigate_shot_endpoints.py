"""Investigate FIBA LiveStats Shot Chart Endpoints

This script tests various possible endpoints for accessing FIBA LiveStats shot chart data
to determine which method works for LKL/ABA/BAL/BCL leagues.

Endpoints to test:
1. JSON API: /data/{competition}/{season}/data/{game_code}/shots.json
2. HTML page: /u/{league_code}/{game_id}/sc.html
3. HTML page alt: /u/{league_code}/{game_id}/shotchart.html
4. HTML page alt2: /u/{league_code}/{game_id}/shots.html
5. Embedded in PBP HTML
6. Embedded in box score HTML
"""

import json
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Test games (real game IDs from 2023-24 season game indexes)
TEST_GAMES = {
    "LKL": {"league_code": "LKL", "game_id": "301234", "season": 2024, "game_code": 301234},
    "ABA": {"league_code": "ABA", "game_id": "601234", "season": 2024, "game_code": 601234},
    "BAL": {"league_code": "BAL", "game_id": "401234", "season": 2024, "game_code": 401234},
    "BCL": {"league_code": "BCL", "game_id": "501234", "season": 2024, "game_code": 501234},
}


def test_json_api(competition: str, season: int, game_code: int) -> dict:
    """Test JSON API endpoint"""
    endpoint = f"/data/{competition}/{season}/data/{game_code}/shots.json"
    url = f"{FIBA_BASE_URL}{endpoint}"

    print(f"\n[TEST] JSON API: {url}")

    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("  ✅ SUCCESS - Got JSON data")
            print(f"  Keys: {list(data.keys())[:5]}")
            return {
                "success": True,
                "method": "json_api",
                "url": url,
                "data_sample": str(data)[:200],
            }
        elif response.status_code == 403:
            print("  ❌ FORBIDDEN - Requires authentication")
            return {"success": False, "method": "json_api", "error": "403 Forbidden"}
        elif response.status_code == 404:
            print("  ❌ NOT FOUND")
            return {"success": False, "method": "json_api", "error": "404 Not Found"}
        else:
            print(f"  ❌ ERROR - Status {response.status_code}")
            return {
                "success": False,
                "method": "json_api",
                "error": f"Status {response.status_code}",
            }
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
        return {"success": False, "method": "json_api", "error": str(e)}


def test_html_endpoint(league_code: str, game_id: str, page_suffix: str) -> dict:
    """Test HTML endpoint"""
    url = f"{FIBA_BASE_URL}/u/{league_code}/{game_id}/{page_suffix}"

    print(f"\n[TEST] HTML Page: {url}")

    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # Check if page has shot data indicators
            has_shot_coords = (
                "loc" in html.lower()
                or "coordinate" in html.lower()
                or '"x"' in html
                or '"y"' in html
            )
            has_shot_table = (
                soup.find("table", class_=lambda x: x and "shot" in x.lower()) if soup else False
            )
            has_canvas = soup.find("canvas") if soup else False

            print("  ✅ SUCCESS - Page exists")
            print(f"  Has coordinates: {has_shot_coords}")
            print(f"  Has shot table: {bool(has_shot_table)}")
            print(f"  Has canvas: {bool(has_canvas)}")
            print(f"  Page size: {len(html)} bytes")

            return {
                "success": True,
                "method": f"html_{page_suffix}",
                "url": url,
                "has_coords": has_shot_coords,
                "has_table": bool(has_shot_table),
                "has_canvas": bool(has_canvas),
                "html_sample": html[:500],
            }
        elif response.status_code == 404:
            print("  ❌ NOT FOUND")
            return {"success": False, "method": f"html_{page_suffix}", "error": "404 Not Found"}
        else:
            print(f"  ❌ ERROR - Status {response.status_code}")
            return {
                "success": False,
                "method": f"html_{page_suffix}",
                "error": f"Status {response.status_code}",
            }
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
        return {"success": False, "method": f"html_{page_suffix}", "error": str(e)}


def check_embedded_in_existing(league_code: str, game_id: str, page_type: str) -> dict:
    """Check if shot data is embedded in existing HTML pages (pbp.html or bs.html)"""
    url = f"{FIBA_BASE_URL}/u/{league_code}/{game_id}/{page_type}.html"

    print(f"\n[TEST] Embedded in {page_type}.html: {url}")

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            html = response.text

            # Look for shot data patterns
            patterns = [
                "shotChart",
                "shot_chart",
                "shotData",
                "shot-data",
                '"shots"',
                "LOC_X",
                "LOC_Y",
                "shot_x",
                "shot_y",
                "coordinates",
            ]

            found_patterns = [p for p in patterns if p in html]
            has_shot_data = len(found_patterns) > 0

            print(f"  Status: {response.status_code}")
            print(f"  Has embedded shot data: {has_shot_data}")
            if found_patterns:
                print(f"  Found patterns: {found_patterns}")

            return {
                "success": has_shot_data,
                "method": f"embedded_{page_type}",
                "url": url,
                "patterns_found": found_patterns,
            }
        else:
            print(f"  ❌ ERROR - Status {response.status_code}")
            return {
                "success": False,
                "method": f"embedded_{page_type}",
                "error": f"Status {response.status_code}",
            }
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
        return {"success": False, "method": f"embedded_{page_type}", "error": str(e)}


def main():
    """Run investigation"""
    print("=" * 80)
    print("FIBA LiveStats Shot Chart Endpoint Investigation")
    print("=" * 80)

    results = []

    # Note: We're using placeholder game IDs since we don't have real ones yet
    # In production, we'd need to fetch these from game indexes
    print("\n⚠️  NOTE: Using placeholder game IDs - results may show 404s")
    print("To get real results, replace game IDs with actual FIBA game IDs from game indexes\n")

    for league, config in TEST_GAMES.items():
        print(f"\n{'=' * 80}")
        print(f"Testing {league}")
        print(f"{'=' * 80}")

        # Test JSON API
        result = test_json_api(config["league_code"], config["season"], config["game_code"])
        results.append({"league": league, **result})

        # Test HTML endpoints
        for suffix in ["sc.html", "shotchart.html", "shots.html"]:
            result = test_html_endpoint(config["league_code"], config["game_id"], suffix)
            results.append({"league": league, **result})

        # Check if embedded in existing pages
        for page_type in ["pbp", "bs"]:
            result = check_embedded_in_existing(config["league_code"], config["game_id"], page_type)
            results.append({"league": league, **result})

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    successful_methods = [r for r in results if r.get("success")]

    if successful_methods:
        print(f"\n✅ Found {len(successful_methods)} working method(s):")
        for result in successful_methods:
            print(f"  - {result['league']}: {result['method']} at {result.get('url', 'N/A')}")
    else:
        print("\n❌ No working methods found")
        print("\nPossible reasons:")
        print("  1. Using placeholder game IDs (replace with real IDs from game indexes)")
        print("  2. FIBA LiveStats may require different endpoint structure")
        print("  3. Shot data may be available through JavaScript/AJAX calls")
        print("  4. May need to inspect browser DevTools network tab for actual endpoints")

    # Save results
    output_file = Path(__file__).parent / "shot_endpoint_investigation_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📊 Full results saved to: {output_file}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Get real FIBA game IDs from:")
    print("   - LKL: data/game_indexes/LKL_2023_24.csv (if exists)")
    print("   - Or manually from https://fibalivestats.dcd.shared.geniussports.com/u/LKL/")
    print("\n2. Re-run this script with real game IDs")
    print("\n3. If still blocked, use browser DevTools to:")
    print("   - Visit a FIBA LiveStats game page")
    print("   - Inspect Network tab for shot-related API calls")
    print("   - Copy working endpoint structure")


if __name__ == "__main__":
    main()
