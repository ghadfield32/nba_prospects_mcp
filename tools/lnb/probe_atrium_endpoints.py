#!/usr/bin/env python3
"""Probe Atrium API for Calendar/Fixtures Endpoints

This script systematically tests different endpoint patterns to find
the bulk fixtures endpoint that accepts competitionId and seasonId.

We already know:
- Base URL: https://eapi.web.prod.cloud.atriumsports.com
- Working endpoint: /v1/embed/12/fixture_detail?fixtureId=<UUID>
- From fixture_detail: competitionId, seasonId

Goal: Find endpoint that returns ALL fixtures for a season in one call.

Usage:
    uv run python tools/lnb/probe_atrium_endpoints.py

    # Test specific pattern only
    uv run python tools/lnb/probe_atrium_endpoints.py --pattern fixtures

    # Verbose output
    uv run python tools/lnb/probe_atrium_endpoints.py --verbose

Created: 2025-11-16
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from typing import Any

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"

# Known IDs from September 2022 fixture (ca4b3e98-11a0-11ed-8669-c3922075d502)
COMPETITION_ID = "5b7857d9-0cbc-11ed-96a7-458862b58368"
SEASON_ID = "717ba1c6-0cbc-11ed-80ed-4b65c29000f2"
SEASON_NAME = "Betclic ÉLITE 2022"  # 2022-2023 season

# Sample fixture UUID for testing
SAMPLE_FIXTURE_ID = "ca4b3e98-11a0-11ed-8669-c3922075d502"

# Request timeout
TIMEOUT = 10  # seconds

# ==============================================================================
# ENDPOINT PATTERNS TO TEST
# ==============================================================================

ENDPOINT_PATTERNS = {
    # Most likely patterns (REST conventions)
    "fixtures": f"/v1/embed/12/fixtures?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    "season_fixtures": f"/v1/embed/12/season_fixtures?seasonId={SEASON_ID}",
    "competition_season_fixtures": f"/v1/embed/12/competition_season_fixtures?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    # Calendar patterns
    "calendar": f"/v1/embed/12/calendar?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    "season_calendar": f"/v1/embed/12/season_calendar?seasonId={SEASON_ID}",
    "competition_calendar": f"/v1/embed/12/competition_calendar?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    # Schedule patterns
    "schedule": f"/v1/embed/12/schedule?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    "season_schedule": f"/v1/embed/12/season_schedule?seasonId={SEASON_ID}",
    # Match patterns (synonym for fixture)
    "matches": f"/v1/embed/12/matches?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    "season_matches": f"/v1/embed/12/season_matches?seasonId={SEASON_ID}",
    # Nested path patterns (RESTful)
    "competition_fixtures_nested": f"/v1/embed/12/competition/{COMPETITION_ID}/season/{SEASON_ID}/fixtures",
    "season_fixtures_nested": f"/v1/embed/12/season/{SEASON_ID}/fixtures",
    "competition_nested": f"/v1/embed/12/competition/{COMPETITION_ID}/fixtures?seasonId={SEASON_ID}",
    # Alternative parameter names
    "fixtures_alt1": f"/v1/embed/12/fixtures?competition={COMPETITION_ID}&season={SEASON_ID}",
    "fixtures_alt2": f"/v1/embed/12/fixtures?comp_id={COMPETITION_ID}&season_id={SEASON_ID}",
    # Plural/singular variations
    "fixture_list": f"/v1/embed/12/fixture_list?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
    "match_list": f"/v1/embed/12/match_list?competitionId={COMPETITION_ID}&seasonId={SEASON_ID}",
}


# ==============================================================================
# PROBE FUNCTIONS
# ==============================================================================


def probe_endpoint(pattern_name: str, url: str, verbose: bool = False) -> dict[str, Any]:
    """Probe a single endpoint and analyze response.

    Args:
        pattern_name: Name of the pattern being tested
        url: Full URL to probe
        verbose: Print detailed response info

    Returns:
        Dict with probe results:
        - pattern: Pattern name
        - url: Full URL
        - status_code: HTTP status (or None if request failed)
        - success: True if 200 OK
        - error: Error message if failed
        - response_type: "json", "html", "error", etc.
        - data_preview: Preview of response data
        - fixture_count: Number of fixtures found (if applicable)
    """
    result = {
        "pattern": pattern_name,
        "url": url,
        "status_code": None,
        "success": False,
        "error": None,
        "response_type": None,
        "data_preview": None,
        "fixture_count": 0,
    }

    try:
        print(f"\n[TESTING] {pattern_name}")
        print(f"  URL: {url}")

        # Make request
        response = requests.get(url, timeout=TIMEOUT)
        result["status_code"] = response.status_code

        print(f"  Status: {response.status_code}")

        # Success!
        if response.status_code == 200:
            result["success"] = True

            # Try to parse JSON
            try:
                data = response.json()
                result["response_type"] = "json"

                # Analyze structure
                if isinstance(data, dict):
                    # Check for common fixture list patterns
                    fixtures = None

                    # Pattern 1: {data: {fixtures: [...]}}
                    if "data" in data and isinstance(data["data"], dict):
                        if "fixtures" in data["data"]:
                            fixtures = data["data"]["fixtures"]
                        elif "matches" in data["data"]:
                            fixtures = data["data"]["matches"]

                    # Pattern 2: {fixtures: [...]}
                    elif "fixtures" in data:
                        fixtures = data["fixtures"]
                    elif "matches" in data:
                        fixtures = data["matches"]

                    # Pattern 3: {data: [...]}
                    elif "data" in data and isinstance(data["data"], list):
                        fixtures = data["data"]

                    # Pattern 4: Direct array
                    elif isinstance(data, list):
                        fixtures = data

                    if fixtures and isinstance(fixtures, list):
                        result["fixture_count"] = len(fixtures)
                        result["data_preview"] = f"{len(fixtures)} fixtures found"

                        if verbose and len(fixtures) > 0:
                            print(f"  ✅ SUCCESS! Found {len(fixtures)} fixtures")
                            print(f"  Sample fixture keys: {list(fixtures[0].keys())[:10]}")
                    else:
                        result["data_preview"] = f"JSON keys: {list(data.keys())}"
                        if verbose:
                            print(f"  ℹ️  JSON response, keys: {list(data.keys())}")

                elif isinstance(data, list):
                    result["fixture_count"] = len(data)
                    result["data_preview"] = f"{len(data)} items in array"

                    if verbose:
                        print(f"  ✅ Array response with {len(data)} items")
                        if len(data) > 0:
                            print(f"  Sample item keys: {list(data[0].keys())[:10]}")

            except json.JSONDecodeError:
                result["response_type"] = "non-json"
                result["data_preview"] = response.text[:200]

                if verbose:
                    print("  ⚠️  Non-JSON response")
                    print(f"  Preview: {response.text[:200]}")

        # 404 Not Found
        elif response.status_code == 404:
            result["error"] = "Not Found (404)"

            try:
                error_data = response.json()
                if "error" in error_data:
                    result["data_preview"] = error_data["error"].get("message", "Unknown error")
            except (ValueError, json.JSONDecodeError):
                pass

            print("  ❌ Not Found")

        # Other error codes
        else:
            result["error"] = f"HTTP {response.status_code}"
            print(f"  ❌ Error: HTTP {response.status_code}")

    except requests.Timeout:
        result["error"] = "Request timeout"
        print(f"  ❌ Timeout after {TIMEOUT}s")

    except requests.RequestException as e:
        result["error"] = str(e)
        print(f"  ❌ Request failed: {e}")

    return result


def probe_all_endpoints(verbose: bool = False, pattern_filter: str | None = None) -> list[dict]:
    """Probe all endpoint patterns.

    Args:
        verbose: Print detailed output
        pattern_filter: Only test patterns containing this string

    Returns:
        List of probe results
    """
    print(f"\n{'=' * 80}")
    print("  ATRIUM API ENDPOINT PROBE")
    print(f"{'=' * 80}\n")

    print(f"Base URL: {ATRIUM_API_BASE}")
    print(f"Competition ID: {COMPETITION_ID}")
    print(f"Season ID: {SEASON_ID}")
    print(f"Season Name: {SEASON_NAME}")
    print(f"Total patterns to test: {len(ENDPOINT_PATTERNS)}\n")

    if pattern_filter:
        print(f"Filter: Only testing patterns containing '{pattern_filter}'\n")

    results = []
    successful = []

    for pattern_name, endpoint in ENDPOINT_PATTERNS.items():
        # Apply filter if specified
        if pattern_filter and pattern_filter.lower() not in pattern_name.lower():
            continue

        full_url = f"{ATRIUM_API_BASE}{endpoint}"
        result = probe_endpoint(pattern_name, full_url, verbose=verbose)
        results.append(result)

        if result["success"] and result["fixture_count"] > 0:
            successful.append(result)

        # Rate limiting: wait between requests
        time.sleep(0.5)

    # Print summary
    print(f"\n{'=' * 80}")
    print("  PROBE SUMMARY")
    print(f"{'=' * 80}\n")

    print(f"Patterns tested: {len(results)}")
    print(f"Successful (200 OK): {len([r for r in results if r['success']])}")
    print(f"With fixtures found: {len(successful)}\n")

    if successful:
        print(f"🎉 SUCCESS! Found {len(successful)} working endpoint(s):\n")

        for r in successful:
            print(f"  ✅ {r['pattern']}")
            print(f"     URL: {r['url']}")
            print(f"     Fixtures: {r['fixture_count']}")
            print()
    else:
        print("❌ No working endpoints found.")
        print("\n📋 All tested patterns:")
        for r in results:
            status = "✅ 200" if r["success"] else f"❌ {r['status_code'] or 'ERROR'}"
            print(f"  {status} | {r['pattern']}")
            if r["error"]:
                print(f"          Error: {r['error']}")

    return results


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Probe Atrium API for calendar/fixtures endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test all patterns
    python tools/lnb/probe_atrium_endpoints.py

    # Test only patterns containing "fixtures"
    python tools/lnb/probe_atrium_endpoints.py --pattern fixtures

    # Verbose output with response details
    python tools/lnb/probe_atrium_endpoints.py --verbose

Output:
    - Prints test results for each endpoint pattern
    - Shows which endpoints return fixture data
    - Identifies working endpoint for bulk discovery
        """,
    )

    parser.add_argument(
        "--pattern",
        type=str,
        help="Only test patterns containing this string (e.g., 'fixtures', 'calendar')",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed response information",
    )

    parser.add_argument(
        "--save-results",
        type=str,
        help="Save probe results to JSON file",
    )

    args = parser.parse_args()

    # Run probe
    results = probe_all_endpoints(
        verbose=args.verbose,
        pattern_filter=args.pattern,
    )

    # Save results if requested
    if args.save_results:
        with open(args.save_results, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved to: {args.save_results}")

    # Exit code based on success
    successful = [r for r in results if r["success"] and r["fixture_count"] > 0]
    sys.exit(0 if successful else 1)


if __name__ == "__main__":
    main()
