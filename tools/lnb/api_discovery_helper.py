#!/usr/bin/env python3
"""
LNB API Discovery Helper

Interactive helper for discovering LNB (French Basketball) API endpoints using
browser DevTools. Generates skeleton code for discovered endpoints.

Usage:
    python tools/lnb/api_discovery_helper.py --discover
    python tools/lnb/api_discovery_helper.py --test-endpoint "https://lnb.fr/api/stats/players"
    python tools/lnb/api_discovery_helper.py --generate-code
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Known LNB URLs
LNB_SITES = {
    "official": "https://lnb.fr/",
    "stats": "https://lnb.fr/stats/",
    "calendar": "https://lnb.fr/calendrier-resultats/",
    "teams": "https://lnb.fr/equipes/",
}

# Endpoint discovery template
DISCOVERY_INSTRUCTIONS = """
═══════════════════════════════════════════════════════════════════════════════
LNB API DISCOVERY GUIDE
═══════════════════════════════════════════════════════════════════════════════

This guide helps you discover LNB (French Basketball League) API endpoints
using browser DevTools.

STEP 1: SETUP BROWSER DEVTOOLS
───────────────────────────────────────────────────────────────────────────────
1. Open Chrome or Firefox
2. Press F12 to open DevTools
3. Go to "Network" tab
4. Filter by "XHR" or "Fetch" (to show only API calls)
5. Check "Preserve log" to keep requests across page navigations

STEP 2: NAVIGATE TO LNB STATS
───────────────────────────────────────────────────────────────────────────────
Visit these pages and observe Network tab:

A. Player Stats: https://lnb.fr/stats/
   - Select season (e.g., "2024-25")
   - Filter by team, position, etc.
   - Look for requests like:
     * /api/players
     * /api/stats/players
     * /api/season/{season}/players

B. Team Stats: https://lnb.fr/equipes/
   - Look for requests like:
     * /api/teams
     * /api/stats/teams
     * /api/season/{season}/teams

C. Schedule/Results: https://lnb.fr/calendrier-resultats/
   - Look for requests like:
     * /api/games
     * /api/schedule
     * /api/calendar

D. Individual Game Page
   - Click on a specific game
   - Look for:
     * /api/game/{game_id}
     * /api/game/{game_id}/boxscore
     * /api/game/{game_id}/playbyplay

STEP 3: CAPTURE API REQUEST DETAILS
───────────────────────────────────────────────────────────────────────────────
For each API endpoint found:

1. Right-click on the request → "Copy" → "Copy as cURL"
2. Note the response format (JSON, XML, HTML)
3. Check if response contains useful data (player names, stats, etc.)
4. Record:
   ✓ Full URL (including query parameters)
   ✓ Request method (GET/POST)
   ✓ Headers (especially Authorization, Cookie, Referer)
   ✓ Request body (if POST)
   ✓ Response structure (JSON keys, nested objects)

STEP 4: DOCUMENT ENDPOINT
───────────────────────────────────────────────────────────────────────────────
Create a file: tools/lnb/discovered_endpoints.json

Example structure:
{
  "player_season_stats": {
    "url": "https://lnb.fr/api/stats/players",
    "method": "GET",
    "params": {
      "season": "2024-25",
      "competition": "PRO_A"
    },
    "headers": {
      "User-Agent": "Mozilla/5.0 ...",
      "Referer": "https://lnb.fr/stats/"
    },
    "response_structure": {
      "players": [
        {
          "name": "...",
          "team": "...",
          "points": 0,
          "rebounds": 0
        }
      ]
    }
  }
}

STEP 5: TEST ENDPOINT
───────────────────────────────────────────────────────────────────────────────
Use this script to test discovered endpoints:

  python tools/lnb/api_discovery_helper.py --test-endpoint "URL"

Example:
  python tools/lnb/api_discovery_helper.py --test-endpoint "https://lnb.fr/api/stats/players?season=2024"

STEP 6: GENERATE CODE SKELETON
───────────────────────────────────────────────────────────────────────────────
Once endpoints are documented:

  python tools/lnb/api_discovery_helper.py --generate-code

This will create Python code skeletons to add to src/cbb_data/fetchers/lnb.py

═══════════════════════════════════════════════════════════════════════════════
COMMON PATTERNS TO LOOK FOR
═══════════════════════════════════════════════════════════════════════════════

JSON API Endpoints (BEST):
  ✓ /api/... URLs
  ✓ Response Content-Type: application/json
  ✓ Clean structured data
  ✓ Example: {"players": [...], "teams": [...]}

GraphQL Endpoints:
  ✓ /graphql URLs
  ✓ POST requests with query in body
  ✓ Response has "data" wrapper
  ✓ Example: {"data": {"players": [...]}}

REST-like Endpoints:
  ✓ /v1/stats, /v2/players
  ✓ URL patterns with IDs: /players/{player_id}
  ✓ Query parameters: ?season=2024&team=paris

Data Embedded in HTML:
  ✗ No clear API endpoints (harder to parse)
  ✗ Requires HTML scraping
  ✗ Look for <script> tags with JSON data

═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Issue: No API calls visible in Network tab
Solution:
  - Try different browsers (Chrome, Firefox)
  - Disable ad blockers
  - Check if site uses WebSockets
  - Look in "All" filter, not just "XHR"

Issue: API returns 403 Forbidden
Solution:
  - Copy exact headers from browser request
  - Include Referer header
  - Check if cookies/tokens needed
  - Try from different IP (not container)

Issue: API returns empty data
Solution:
  - Check required query parameters
  - Verify season format (2024 vs 2024-25)
  - Check competition ID (PRO_A, PRO_B, etc.)

═══════════════════════════════════════════════════════════════════════════════
READY TO START?
═══════════════════════════════════════════════════════════════════════════════

1. Open https://lnb.fr/stats/ in browser with DevTools
2. Start documenting endpoints you find
3. Test them with this script
4. Generate code skeletons
5. Implement in src/cbb_data/fetchers/lnb.py

Good luck! 🏀
═══════════════════════════════════════════════════════════════════════════════
"""


class LNBAPIDiscovery:
    """Helper for discovering LNB API endpoints"""

    def __init__(self):
        self.endpoints: Dict[str, Dict] = {}
        self.endpoints_file = Path("tools/lnb/discovered_endpoints.json")

    def print_instructions(self):
        """Print discovery instructions"""
        print(DISCOVERY_INSTRUCTIONS)

    def test_endpoint(self, url: str, method: str = "GET", headers: Optional[Dict] = None,
                     params: Optional[Dict] = None, data: Optional[Dict] = None):
        """Test an API endpoint"""
        print("\n" + "=" * 70)
        print(f"Testing Endpoint: {url}")
        print("=" * 70)

        # Default headers
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://lnb.fr/stats/"
            }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=15)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=15)

            print(f"\nStatus Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"Response Size: {len(response.content)} bytes")

            # Try to parse as JSON
            try:
                json_data = response.json()
                print("\n✅ Valid JSON Response")
                print("\nResponse Structure:")
                self._print_json_structure(json_data, indent=2)

                # Save sample
                sample_path = Path("tools/lnb/sample_responses")
                sample_path.mkdir(parents=True, exist_ok=True)

                endpoint_name = url.split("/")[-1].split("?")[0]
                sample_file = sample_path / f"{endpoint_name}_sample.json"

                with open(sample_file, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)

                print(f"\n💾 Sample saved to: {sample_file}")

            except ValueError:
                print("\n⚠️  Response is not JSON")
                print(f"First 500 characters of response:")
                print(response.text[:500])

        except requests.RequestException as e:
            print(f"\n❌ Request failed: {e}")

        print("\n" + "=" * 70 + "\n")

    def _print_json_structure(self, data, indent: int = 0, max_depth: int = 3):
        """Print JSON structure recursively"""
        prefix = " " * indent

        if isinstance(data, dict):
            for key, value in list(data.items())[:5]:  # Show first 5 keys
                value_type = type(value).__name__
                if isinstance(value, (dict, list)) and indent < max_depth * 2:
                    print(f"{prefix}{key}: {value_type}")
                    self._print_json_structure(value, indent + 2, max_depth)
                else:
                    print(f"{prefix}{key}: {value_type} = {str(value)[:50]}")

            if len(data) > 5:
                print(f"{prefix}... ({len(data) - 5} more keys)")

        elif isinstance(data, list):
            print(f"{prefix}[{len(data)} items]")
            if data and indent < max_depth * 2:
                print(f"{prefix}First item:")
                self._print_json_structure(data[0], indent + 2, max_depth)

    def load_discovered_endpoints(self) -> Dict:
        """Load discovered endpoints from JSON file"""
        if not self.endpoints_file.exists():
            logger.warning(f"No endpoints file found at {self.endpoints_file}")
            return {}

        try:
            with open(self.endpoints_file, 'r', encoding='utf-8') as f:
                self.endpoints = json.load(f)

            logger.info(f"Loaded {len(self.endpoints)} discovered endpoints")
            return self.endpoints

        except Exception as e:
            logger.error(f"Could not load endpoints file: {e}")
            return {}

    def generate_code_skeleton(self):
        """Generate Python code skeleton for discovered endpoints"""
        if not self.endpoints:
            self.load_discovered_endpoints()

        if not self.endpoints:
            print("\n⚠️  No endpoints discovered yet.")
            print("Please create tools/lnb/discovered_endpoints.json with endpoint details.")
            print("See instructions with: python tools/lnb/api_discovery_helper.py --discover\n")
            return

        print("\n" + "=" * 70)
        print("Generated Code Skeleton for LNB Fetchers")
        print("=" * 70)

        for endpoint_name, endpoint_info in self.endpoints.items():
            function_name = f"fetch_lnb_{endpoint_name}"
            url = endpoint_info.get("url", "")
            method = endpoint_info.get("method", "GET")
            params = endpoint_info.get("params", {})

            print(f"\n# {endpoint_name}")
            print("@retry_on_error(max_attempts=3, backoff_seconds=2.0)")
            print("@cached_dataframe")
            print(f"def {function_name}(season: str = \"2024-25\") -> pd.DataFrame:")
            print(f'    """Fetch LNB {endpoint_name.replace("_", " ")}"""')
            print(f'    logger.info(f"Fetching LNB {endpoint_name}: {{season}}")')
            print()
            print(f'    url = "{url}"')
            print(f"    params = {json.dumps(params, indent=8)}")
            print()
            print("    try:")
            print("        response = requests.get(url, params=params, headers=HEADERS, timeout=15)")
            print("        response.raise_for_status()")
            print()
            print("        data = response.json()")
            print()
            print("        # TODO: Parse JSON structure based on actual response")
            print("        # Example:")
            print("        # items = data.get('players', [])")
            print("        # df = pd.DataFrame([")
            print("        #     {")
            print('        #         "PLAYER_NAME": item.get("name"),')
            print('        #         "TEAM": item.get("team"),')
            print('        #         "PTS": item.get("points"),')
            print("        #         # ... other fields")
            print("        #     }")
            print("        #     for item in items")
            print("        # ])")
            print()
            print("        df = pd.DataFrame()  # Replace with actual parsing")
            print("        return df")
            print()
            print("    except requests.HTTPError as e:")
            print(f'        return _handle_lnb_error(e, "{endpoint_name}", season)')
            print()

        print("\n" + "=" * 70)
        print("\nCopy the code above to src/cbb_data/fetchers/lnb.py")
        print("Replace the TODO sections with actual JSON parsing logic")
        print("=" * 70 + "\n")


def main():
    """Main discovery workflow"""
    parser = argparse.ArgumentParser(
        description="LNB API discovery helper"
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Show API discovery instructions"
    )
    parser.add_argument(
        "--test-endpoint",
        help="Test a specific endpoint URL"
    )
    parser.add_argument(
        "--method",
        default="GET",
        help="HTTP method (default: GET)"
    )
    parser.add_argument(
        "--generate-code",
        action="store_true",
        help="Generate code skeleton from discovered endpoints"
    )

    args = parser.parse_args()

    helper = LNBAPIDiscovery()

    if args.discover:
        helper.print_instructions()

    elif args.test_endpoint:
        helper.test_endpoint(args.test_endpoint, method=args.method)

    elif args.generate_code:
        helper.generate_code_skeleton()

    else:
        print("\nLNB API Discovery Helper")
        print("=" * 70)
        print("\nOptions:")
        print("  --discover         Show detailed discovery instructions")
        print("  --test-endpoint    Test a specific endpoint URL")
        print("  --generate-code    Generate code skeleton from discovered endpoints")
        print("\nExamples:")
        print('  python tools/lnb/api_discovery_helper.py --discover')
        print('  python tools/lnb/api_discovery_helper.py --test-endpoint "https://lnb.fr/api/stats/players"')
        print('  python tools/lnb/api_discovery_helper.py --generate-code')
        print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
