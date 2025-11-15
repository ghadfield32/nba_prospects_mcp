#!/usr/bin/env python3
"""Capture LNB API responses for analysis and fetcher implementation

This script tests the discovered LNB API endpoints, captures JSON responses,
and saves them for analysis. This allows us to:
1. Understand the exact JSON structure before implementing fetchers
2. Validate that endpoints work and return expected data
3. Discover additional endpoints by analyzing network traffic

Discovered Endpoints:
- https://api-prod.lnb.fr/match/getMatchDetails/{match_uuid}
- https://api-prod.lnb.fr/event/getEventList

Unknown Endpoints (to discover):
- Play-by-play endpoint (suspected: /match/getPlayByPlay or /match/getEvents)
- Shot chart endpoint (suspected: /match/getShots or /match/getShotChart)

Usage:
    # Capture all responses for a specific match
    uv run python tools/lnb/capture_lnb_api_responses.py --match-uuid 3fcea9a1-1f10-11ee-a687-db190750bdda

    # Capture event list only
    uv run python tools/lnb/capture_lnb_api_responses.py --event-list-only

    # Test multiple matches
    uv run python tools/lnb/capture_lnb_api_responses.py --test-all-known-uuids

Output:
    - tools/lnb/sample_responses/match_details_{uuid}.json
    - tools/lnb/sample_responses/event_list.json
    - tools/lnb/sample_responses/play_by_play_{uuid}.json (if found)
    - tools/lnb/sample_responses/shots_{uuid}.json (if found)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIG
# ==============================================================================

# API Base URL
API_BASE = "https://api-prod.lnb.fr"

# Common headers for all API requests (based on network analysis)
COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://lnb.fr",
    "referer": "https://lnb.fr/",
    "language_code": "en",  # Can be "en" or "fr"
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Output directory for captured responses
SAMPLE_RESPONSES_DIR = Path("tools/lnb/sample_responses")
SAMPLE_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

# Known match UUIDs for testing (from multiple seasons)
KNOWN_MATCH_UUIDS = [
    "3fcea9a1-1f10-11ee-a687-db190750bdda",  # 2023-2024 season
    "cc7e470e-11a0-11ed-8ef5-8d12cdc95909",  # 2022-2023 season
    "7d414bce-f5da-11eb-b3fd-a23ac5ab90da",  # 2021-2022 season
    "0d0504a0-6715-11f0-98ab-27e6e78614e1",  # 2024-2025 season
]

# ==============================================================================
# API CLIENT
# ==============================================================================


class LNBAPIClient:
    """Simple API client for LNB endpoints with proper headers"""

    def __init__(self, timeout: int = 30):
        """Initialize API client

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(COMMON_HEADERS)

    def get_match_details(self, match_uuid: str) -> dict[str, Any] | None:
        """Fetch match details (boxscore, metadata)

        Args:
            match_uuid: Match UUID (fixture ID)

        Returns:
            JSON response dict or None if error
        """
        url = f"{API_BASE}/match/getMatchDetails/{match_uuid}"

        # Update referer for this specific match
        headers = COMMON_HEADERS.copy()
        headers["referer"] = f"https://lnb.fr/fr/match-center/{match_uuid}"

        print(f"[GET] {url}")

        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            print(f"  ✅ Success ({len(json.dumps(data))} bytes)")
            return data

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {e}")
            return None

    def get_event_list(self) -> dict[str, Any] | None:
        """Fetch event list (competitions, seasons, events)

        Returns:
            JSON response dict or None if error
        """
        url = f"{API_BASE}/event/getEventList"

        print(f"[GET] {url}")

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            print(f"  ✅ Success ({len(json.dumps(data))} bytes)")
            return data

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {e}")
            return None

    def try_endpoint(self, endpoint: str, match_uuid: str | None = None) -> dict[str, Any] | None:
        """Try a suspected endpoint to see if it exists

        Args:
            endpoint: Endpoint path (e.g., "/match/getPlayByPlay")
            match_uuid: Optional match UUID to append

        Returns:
            JSON response dict or None if error
        """
        if match_uuid:
            url = f"{API_BASE}{endpoint}/{match_uuid}"
            headers = COMMON_HEADERS.copy()
            headers["referer"] = f"https://lnb.fr/fr/match-center/{match_uuid}"
        else:
            url = f"{API_BASE}{endpoint}"
            headers = COMMON_HEADERS.copy()

        print(f"[TRY] {url}")

        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  ✅ Found! ({len(json.dumps(data))} bytes)")
                    return data
                except json.JSONDecodeError:
                    print("  ⚠️  200 OK but not JSON")
                    return None
            elif response.status_code == 404:
                print("  ❌ 404 Not Found")
                return None
            else:
                print(f"  ❌ Status {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {e}")
            return None


# ==============================================================================
# ENDPOINT DISCOVERY
# ==============================================================================


def discover_pbp_endpoint(client: LNBAPIClient, match_uuid: str) -> str | None:
    """Try to discover the play-by-play endpoint

    Args:
        client: API client instance
        match_uuid: Match UUID to test with

    Returns:
        Endpoint path if found, None otherwise
    """
    print("\n[DISCOVERING] Play-by-play endpoint...")

    suspected_endpoints = [
        "/match/getPlayByPlay",
        "/match/getEvents",
        "/match/getPBP",
        "/match/getActions",
        "/match/getTimeline",
    ]

    for endpoint in suspected_endpoints:
        data = client.try_endpoint(endpoint, match_uuid)
        if data:
            return endpoint

    print("  ⚠️  Could not find PBP endpoint")
    return None


def discover_shots_endpoint(client: LNBAPIClient, match_uuid: str) -> str | None:
    """Try to discover the shot chart endpoint

    Args:
        client: API client instance
        match_uuid: Match UUID to test with

    Returns:
        Endpoint path if found, None otherwise
    """
    print("\n[DISCOVERING] Shot chart endpoint...")

    suspected_endpoints = [
        "/match/getShots",
        "/match/getShotChart",
        "/match/getShooting",
        "/match/getFieldGoals",
    ]

    for endpoint in suspected_endpoints:
        data = client.try_endpoint(endpoint, match_uuid)
        if data:
            return endpoint

    print("  ⚠️  Could not find shots endpoint")
    return None


# ==============================================================================
# RESPONSE CAPTURE
# ==============================================================================


def save_response(data: dict[str, Any], filename: str) -> None:
    """Save JSON response to file

    Args:
        data: JSON data to save
        filename: Filename (will be placed in sample_responses/)
    """
    filepath = SAMPLE_RESPONSES_DIR / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  [SAVED] {filepath.name}")

    except Exception as e:
        print(f"  [ERROR] Failed to save {filename}: {e}")


def capture_match_responses(client: LNBAPIClient, match_uuid: str) -> dict[str, Any]:
    """Capture all API responses for a specific match

    Args:
        client: API client instance
        match_uuid: Match UUID

    Returns:
        Dict with captured data and endpoint discoveries
    """
    print(f"\n{'='*80}")
    print(f"  CAPTURING RESPONSES FOR MATCH: {match_uuid}")
    print(f"{'='*80}\n")

    results = {"match_uuid": match_uuid, "timestamp": datetime.now().isoformat(), "captured": {}}

    # 1. Match details (boxscore)
    print("[1/4] Match Details (Boxscore)...")
    match_details = client.get_match_details(match_uuid)
    if match_details:
        save_response(match_details, f"match_details_{match_uuid[:8]}.json")
        results["captured"]["match_details"] = True
    else:
        results["captured"]["match_details"] = False

    # 2. Try to discover play-by-play endpoint
    print("\n[2/4] Play-by-Play...")
    pbp_endpoint = discover_pbp_endpoint(client, match_uuid)
    if pbp_endpoint:
        pbp_data = client.try_endpoint(pbp_endpoint, match_uuid)
        if pbp_data:
            save_response(pbp_data, f"play_by_play_{match_uuid[:8]}.json")
            results["captured"]["play_by_play"] = pbp_endpoint
        else:
            results["captured"]["play_by_play"] = False
    else:
        results["captured"]["play_by_play"] = False

    # 3. Try to discover shots endpoint
    print("\n[3/4] Shot Chart...")
    shots_endpoint = discover_shots_endpoint(client, match_uuid)
    if shots_endpoint:
        shots_data = client.try_endpoint(shots_endpoint, match_uuid)
        if shots_data:
            save_response(shots_data, f"shots_{match_uuid[:8]}.json")
            results["captured"]["shots"] = shots_endpoint
        else:
            results["captured"]["shots"] = False
    else:
        results["captured"]["shots"] = False

    return results


def capture_event_list(client: LNBAPIClient) -> bool:
    """Capture event list response

    Args:
        client: API client instance

    Returns:
        True if successful
    """
    print(f"\n{'='*80}")
    print("  CAPTURING EVENT LIST")
    print(f"{'='*80}\n")

    event_list = client.get_event_list()
    if event_list:
        save_response(event_list, "event_list.json")
        return True
    else:
        return False


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Capture LNB API responses for analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--match-uuid", type=str, default=None, help="Specific match UUID to capture"
    )

    parser.add_argument(
        "--event-list-only", action="store_true", help="Only capture event list (not match data)"
    )

    parser.add_argument(
        "--test-all-known-uuids", action="store_true", help="Test all known match UUIDs"
    )

    args = parser.parse_args()

    print(f"{'='*80}")
    print("  LNB API RESPONSE CAPTURE")
    print(f"{'='*80}\n")

    print(f"Output directory: {SAMPLE_RESPONSES_DIR}")
    print()

    # Create API client
    client = LNBAPIClient()

    # Capture event list
    if args.event_list_only or not args.match_uuid:
        capture_event_list(client)

    # Capture match responses
    if args.match_uuid:
        capture_match_responses(client, args.match_uuid)

    elif args.test_all_known_uuids:
        print(f"Testing {len(KNOWN_MATCH_UUIDS)} known match UUIDs...\n")

        all_results = []
        for uuid in KNOWN_MATCH_UUIDS:
            results = capture_match_responses(client, uuid)
            all_results.append(results)

        # Summary
        print(f"\n{'='*80}")
        print("  CAPTURE SUMMARY")
        print(f"{'='*80}\n")

        for results in all_results:
            uuid = results["match_uuid"]
            match_ok = "✅" if results["captured"].get("match_details") else "❌"
            pbp_ok = "✅" if results["captured"].get("play_by_play") else "❌"
            shots_ok = "✅" if results["captured"].get("shots") else "❌"

            print(f"{uuid[:16]}... : Details={match_ok} PBP={pbp_ok} Shots={shots_ok}")

    print()


if __name__ == "__main__":
    main()
