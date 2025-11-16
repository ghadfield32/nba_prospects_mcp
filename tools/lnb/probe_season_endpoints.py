#!/usr/bin/env python3
"""Comprehensive Atrium API Endpoint Probe for Season Discovery

This script systematically tests multiple API endpoint patterns to find
endpoints that return seasonId metadata for discovering other seasons.

Goal: Find an endpoint that returns available seasons with their seasonIds
      so we can automate discovery for 2023-2024, 2024-2025, 2025-2026.

Approach:
    - Test known patterns: /seasons, /competitions, /leagues, etc.
    - Try variations: singular/plural, nested paths, query params
    - Check response for seasonId or season list data

Usage:
    uv run python tools/lnb/probe_season_endpoints.py
    uv run python tools/lnb/probe_season_endpoints.py --verbose

Created: 2025-11-16
Purpose: Discover seasonIds for multi-season ingestion
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

import requests

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
TIMEOUT = 10

# Known IDs from 2022-23 season
KNOWN_COMPETITION_ID = "5b7857d9-0cbc-11ed-96a7-458862b58368"
KNOWN_SEASON_ID = "717ba1c6-0cbc-11ed-80ed-4b65c29000f2"
EMBED_ID = "12"  # Appears in all working endpoints

# ==============================================================================
# ENDPOINT PATTERNS TO TEST
# ==============================================================================

# Each pattern will be tested with HTTP GET
# Patterns use {comp_id}, {season_id}, {embed_id} as placeholders
ENDPOINT_PATTERNS = [
    # === Season List Endpoints ===
    {
        "name": "seasons_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/seasons",
        "description": "Root seasons endpoint",
    },
    {
        "name": "seasons_by_competition",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/seasons?competitionId={KNOWN_COMPETITION_ID}",
        "description": "Seasons filtered by competition",
    },
    {
        "name": "competition_seasons",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/competition/{KNOWN_COMPETITION_ID}/seasons",
        "description": "Seasons nested under competition",
    },
    {
        "name": "competition_seasons_alt",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/competitions/{KNOWN_COMPETITION_ID}/seasons",
        "description": "Seasons with plural 'competitions'",
    },
    # === Competition List Endpoints ===
    {
        "name": "competitions_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/competitions",
        "description": "Root competitions endpoint",
    },
    {
        "name": "competition_detail",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/competition/{KNOWN_COMPETITION_ID}",
        "description": "Single competition details",
    },
    {
        "name": "competitions_detail_alt",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/competitions/{KNOWN_COMPETITION_ID}",
        "description": "Competition detail (plural path)",
    },
    # === League Endpoints ===
    {
        "name": "leagues_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/leagues",
        "description": "Root leagues endpoint",
    },
    {
        "name": "league_seasons",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/league/{KNOWN_COMPETITION_ID}/seasons",
        "description": "Seasons under league",
    },
    # === Calendar/Schedule Endpoints ===
    {
        "name": "calendar_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/calendar",
        "description": "Root calendar endpoint",
    },
    {
        "name": "calendar_by_competition",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/calendar?competitionId={KNOWN_COMPETITION_ID}",
        "description": "Calendar filtered by competition",
    },
    {
        "name": "schedule_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/schedule",
        "description": "Root schedule endpoint",
    },
    # === Season Detail Endpoints ===
    {
        "name": "season_detail",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/season/{KNOWN_SEASON_ID}",
        "description": "Single season details",
    },
    {
        "name": "seasons_detail_alt",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/seasons/{KNOWN_SEASON_ID}",
        "description": "Season detail (plural path)",
    },
    # === Config/Metadata Endpoints ===
    {
        "name": "config_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/config",
        "description": "Config/metadata endpoint",
    },
    {
        "name": "metadata_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/metadata",
        "description": "Metadata endpoint",
    },
    # === Known Working Endpoint (Baseline) ===
    {
        "name": "fixtures_2022_baseline",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/fixtures?competitionId={KNOWN_COMPETITION_ID}&seasonId={KNOWN_SEASON_ID}",
        "description": "BASELINE - Known working fixtures endpoint",
    },
    # === Experimental Patterns ===
    {
        "name": "standings_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/standings",
        "description": "Standings endpoint (might have season list)",
    },
    {
        "name": "standings_by_competition",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/standings?competitionId={KNOWN_COMPETITION_ID}",
        "description": "Standings filtered by competition",
    },
    {
        "name": "teams_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}/teams",
        "description": "Teams endpoint (might include seasons)",
    },
    {
        "name": "embed_root",
        "url": f"{ATRIUM_API_BASE}/v1/embed/{EMBED_ID}",
        "description": "Root embed endpoint (API discovery)",
    },
    # === Alternative Base Paths ===
    {
        "name": "api_v1_seasons",
        "url": f"{ATRIUM_API_BASE}/v1/seasons",
        "description": "Seasons without embed prefix",
    },
    {
        "name": "api_v1_competitions",
        "url": f"{ATRIUM_API_BASE}/v1/competitions",
        "description": "Competitions without embed prefix",
    },
    {
        "name": "api_v2_seasons",
        "url": f"{ATRIUM_API_BASE}/v2/embed/{EMBED_ID}/seasons",
        "description": "V2 API seasons endpoint",
    },
]


# ==============================================================================
# ENDPOINT TESTING
# ==============================================================================


def probe_endpoint(pattern: dict[str, str], verbose: bool = False) -> dict[str, Any]:
    """Test a single endpoint pattern

    Args:
        pattern: Dict with 'name', 'url', 'description'
        verbose: Print detailed response info

    Returns:
        Dict with test results
    """
    name = pattern["name"]
    url = pattern["url"]
    desc = pattern["description"]

    result = {
        "name": name,
        "url": url,
        "description": desc,
        "status_code": None,
        "success": False,
        "has_data": False,
        "response_keys": [],
        "season_count": 0,
        "error": None,
    }

    try:
        response = requests.get(url, timeout=TIMEOUT)
        result["status_code"] = response.status_code

        if response.status_code == 200:
            result["success"] = True

            # Try to parse JSON
            try:
                data = response.json()
                result["has_data"] = True

                # Analyze response structure
                if isinstance(data, dict):
                    result["response_keys"] = list(data.keys())

                    # Look for season-related data
                    if "data" in data:
                        inner_data = data["data"]
                        if isinstance(inner_data, dict):
                            result["response_keys"].extend([f"data.{k}" for k in inner_data.keys()])

                            # Check for season arrays
                            if "seasons" in inner_data and isinstance(inner_data["seasons"], list):
                                result["season_count"] = len(inner_data["seasons"])

                            # Check for fixtures (baseline)
                            if "fixtures" in inner_data and isinstance(
                                inner_data["fixtures"], list
                            ):
                                result["season_count"] = len(inner_data["fixtures"])

                if verbose:
                    print(f"\n{'='*60}")
                    print(f"Endpoint: {name}")
                    print(f"URL: {url}")
                    print(f"Status: {response.status_code}")
                    print(f"Keys: {result['response_keys']}")
                    if result["season_count"] > 0:
                        print(f"Items found: {result['season_count']}")
                    print(f"Sample response: {json.dumps(data, indent=2)[:500]}")

            except json.JSONDecodeError:
                result["error"] = "Invalid JSON response"

        elif response.status_code == 404:
            result["error"] = "Endpoint not found (404)"
        elif response.status_code == 403:
            result["error"] = "Forbidden (403) - may require auth"
        else:
            result["error"] = f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        result["error"] = "Request timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection error"
    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Probe Atrium API endpoints for season discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed response info")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print("  ATRIUM API SEASON DISCOVERY - COMPREHENSIVE ENDPOINT PROBE")
    print(f"{'='*80}\n")
    print(f"Testing {len(ENDPOINT_PATTERNS)} endpoint patterns...")
    print("Target: Find endpoints that return seasonId metadata\n")

    results = []
    successful = []
    with_data = []

    for i, pattern in enumerate(ENDPOINT_PATTERNS, 1):
        name = pattern["name"]
        print(f"[{i}/{len(ENDPOINT_PATTERNS)}] Testing: {name}...", end=" ")

        result = probe_endpoint(pattern, verbose=args.verbose)
        results.append(result)

        if result["success"]:
            successful.append(result)
            print(f"OK {result['status_code']}")

            if result["has_data"]:
                with_data.append(result)
                if result["season_count"] > 0:
                    print(f"    -> Found {result['season_count']} items!")
        else:
            print(f"FAIL {result.get('error', 'Unknown error')}")

    # Summary
    print(f"\n{'='*80}")
    print("  RESULTS SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total endpoints tested: {len(results)}")
    print(f"Successful (200 OK): {len(successful)}")
    print(f"With JSON data: {len(with_data)}")
    print()

    if with_data:
        print("Endpoints with data:")
        for result in with_data:
            print(f"\n  [{result['name']}]")
            print(f"  URL: {result['url']}")
            print(f"  Keys: {', '.join(result['response_keys'][:5])}")
            if result["season_count"] > 0:
                print(f"  Items: {result['season_count']}")

    # Save results
    output_file = "tools/lnb/endpoint_probe_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "patterns_tested": len(ENDPOINT_PATTERNS),
                "successful": len(successful),
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\n\nResults saved to: {output_file}")

    # Recommendations
    print(f"\n{'='*80}")
    print("  NEXT STEPS")
    print(f"{'='*80}\n")

    if len(with_data) > 1:  # More than just the baseline
        print("SUCCESS: Found working endpoints! Review endpoint_probe_results.json")
        print("  Look for endpoints with 'seasons' arrays or seasonId fields")
    else:
        print("NO SUCCESS: No new endpoints found that return season metadata")
        print("\nRECOMMENDATIONS:")
        print("  1. Use Manual DevTools Investigation (see DEVTOOLS_SEASON_DISCOVERY_GUIDE.md)")
        print("  2. Try date-based grouping fallback (discover_seasons_by_dates.py)")
        print("  3. Contact LNB for API documentation")


if __name__ == "__main__":
    main()
