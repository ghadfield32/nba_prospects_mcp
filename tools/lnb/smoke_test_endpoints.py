#!/usr/bin/env python3
"""LNB API Endpoint Smoke Test

Tests all discovered LNB API endpoints and saves sample JSON responses.

**Purpose**:
- Validate that endpoints are accessible and return valid JSON
- Capture frozen snapshots of API responses for schema exploration
- Detect endpoint changes (404, schema shifts, etc.)
- Provide sample data for parser development

**Usage**:
    # Test all endpoints with known UUIDs
    uv run python tools/lnb/smoke_test_endpoints.py

    # Test specific UUID
    uv run python tools/lnb/smoke_test_endpoints.py --uuid 3522345e-3362-11f0-b97d-7be2bdc7a840

    # Save responses to custom directory
    uv run python tools/lnb/smoke_test_endpoints.py --output-dir tools/lnb/test_responses

**Output**:
- Saves JSON responses to: tools/lnb/sample_responses/{endpoint}/{uuid}.json
- Prints summary table showing endpoint status (✅/❌/⚠️)

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests

from src.cbb_data.fetchers.lnb import _create_atrium_state
from src.cbb_data.fetchers.lnb_endpoints import ATRIUM_API, LNB_API

# ==============================================================================
# CONFIG
# ==============================================================================

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "sample_responses"

# Known UUIDs from discovered fixtures (from fixture_uuids_by_season.json)
KNOWN_UUIDS = [
    "0cac6e1b-6715-11f0-a9f3-27e6e78614e1",  # 2024-2025
    "0cd1323f-6715-11f0-86f4-27e6e78614e1",  # 2024-2025
    "3fcea9a1-1f10-11ee-a687-db190750bdda",  # 2023-2024
    "cc7e470e-11a0-11ed-8ef5-8d12cdc95909",  # 2023-2024
    "1515cca4-67e6-11f0-908d-9d1d3a927139",  # 2022-2023
]

# Request timeout
TIMEOUT = 10.0

# Rate limiting (sleep between requests)
RATE_LIMIT_SLEEP = 0.5  # 500ms between requests

# ==============================================================================
# ENDPOINT TEST DEFINITIONS
# ==============================================================================


class EndpointTest:
    """Defines a test for a specific endpoint"""

    def __init__(
        self,
        name: str,
        url_template: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        requires_uuid: bool = False,
    ):
        """Initialize endpoint test

        Args:
            name: Test name (used for output directory)
            url_template: URL template (may contain {uuid} placeholder)
            method: HTTP method (GET or POST)
            headers: Custom headers for request
            params: Query parameters
            json_body: JSON body for POST requests
            requires_uuid: If True, test requires UUID parameter
        """
        self.name = name
        self.url_template = url_template
        self.method = method
        self.headers = headers or {}
        self.params = params or {}
        self.json_body = json_body
        self.requires_uuid = requires_uuid

    def build_url(self, uuid: str | None = None) -> str:
        """Build URL with UUID if required"""
        if self.requires_uuid and uuid:
            return self.url_template.format(uuid=uuid)
        return self.url_template

    def execute(self, uuid: str | None = None) -> dict[str, Any]:
        """Execute endpoint test and return result

        Returns:
            Dict with keys:
            - success: bool (True if HTTP 200 and valid JSON)
            - status_code: int
            - response_data: dict (parsed JSON)
            - error: str (error message if failed)
            - response_size: int (bytes)
        """
        url = self.build_url(uuid)

        try:
            # Merge default headers with custom headers
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://lnb.fr/",
            }
            request_headers.update(self.headers)

            # Execute request
            if self.method == "GET":
                response = requests.get(
                    url,
                    headers=request_headers,
                    params=self.params,
                    timeout=TIMEOUT,
                )
            elif self.method == "POST":
                response = requests.post(
                    url,
                    headers=request_headers,
                    params=self.params,
                    json=self.json_body,
                    timeout=TIMEOUT,
                )
            else:
                return {
                    "success": False,
                    "status_code": 0,
                    "error": f"Unsupported method: {self.method}",
                    "response_data": None,
                    "response_size": 0,
                }

            # Check status code
            response.raise_for_status()

            # Parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"Invalid JSON: {e}",
                    "response_data": None,
                    "response_size": len(response.content),
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "response_data": data,
                "error": None,
                "response_size": len(response.content),
            }

        except requests.RequestException as e:
            return {
                "success": False,
                "status_code": getattr(e.response, "status_code", 0)
                if hasattr(e, "response")
                else 0,
                "error": str(e),
                "response_data": None,
                "response_size": 0,
            }


# ==============================================================================
# DEFINE ENDPOINT TESTS
# ==============================================================================


def get_endpoint_tests(uuid: str | None = None) -> list[EndpointTest]:
    """Get list of endpoint tests to execute

    Args:
        uuid: Optional UUID to use for UUID-requiring endpoints

    Returns:
        List of EndpointTest objects
    """
    tests = []

    # ==========================================================================
    # LNB API - Match Details (requires UUID)
    # ==========================================================================

    if uuid:
        tests.append(
            EndpointTest(
                name="match_details",
                url_template=LNB_API.match_details(uuid),
                method="GET",
                requires_uuid=True,
            )
        )

    # ==========================================================================
    # LNB API - Event List
    # ==========================================================================

    tests.append(
        EndpointTest(
            name="event_list",
            url_template=LNB_API.EVENT_LIST,
            method="GET",
        )
    )

    # ==========================================================================
    # Atrium API - Play-by-Play (requires UUID)
    # ==========================================================================

    if uuid:
        pbp_state = _create_atrium_state(uuid, "pbp")
        tests.append(
            EndpointTest(
                name="pbp",
                url_template=ATRIUM_API.FIXTURE_DETAIL,
                method="GET",
                params={"fixtureId": uuid, "state": pbp_state},
                requires_uuid=True,
            )
        )

    # ==========================================================================
    # Atrium API - Shot Chart (requires UUID)
    # ==========================================================================

    if uuid:
        shot_state = _create_atrium_state(uuid, "shot_chart")
        tests.append(
            EndpointTest(
                name="shots",
                url_template=ATRIUM_API.FIXTURE_DETAIL,
                method="GET",
                params={"fixtureId": uuid, "state": shot_state},
                requires_uuid=True,
            )
        )

    # ==========================================================================
    # LNB API - Global Endpoints (no UUID required)
    # ==========================================================================

    tests.append(
        EndpointTest(
            name="all_years",
            url_template=LNB_API.ALL_YEARS,
            method="GET",
            params={"end_year": 2025},
        )
    )

    tests.append(
        EndpointTest(
            name="main_competitions",
            url_template=LNB_API.MAIN_COMPETITIONS,
            method="GET",
            params={"year": 2024},
        )
    )

    tests.append(
        EndpointTest(
            name="live_matches",
            url_template=LNB_API.LIVE_MATCHES,
            method="GET",
        )
    )

    return tests


# ==============================================================================
# SMOKE TEST EXECUTION
# ==============================================================================


def save_response(
    endpoint_name: str,
    uuid: str | None,
    response_data: dict[str, Any],
    output_dir: Path,
) -> None:
    """Save JSON response to file

    Args:
        endpoint_name: Endpoint name (used for subdirectory)
        uuid: UUID (used for filename)
        response_data: Parsed JSON response
        output_dir: Base output directory
    """
    # Create subdirectory for endpoint
    endpoint_dir = output_dir / endpoint_name
    endpoint_dir.mkdir(parents=True, exist_ok=True)

    # Determine filename
    if uuid:
        filename = f"{uuid}.json"
    else:
        filename = f"{endpoint_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    output_path = endpoint_dir / filename

    # Save JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(response_data, f, indent=2, ensure_ascii=False)

    print(f"  [SAVED] {output_path.relative_to(output_dir.parent)}")


def run_smoke_test(
    uuids: list[str],
    output_dir: Path,
    verbose: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Run smoke test for all endpoints

    Args:
        uuids: List of UUIDs to test
        output_dir: Output directory for JSON responses
        verbose: If True, print detailed logs

    Returns:
        Dict mapping endpoint name to list of test results
    """
    print("\n" + "=" * 80)
    print("LNB API ENDPOINT SMOKE TEST")
    print("=" * 80 + "\n")

    print(f"Testing {len(uuids)} UUIDs:")
    for i, uuid in enumerate(uuids, 1):
        print(f"  {i}. {uuid}")
    print()

    print(f"Output directory: {output_dir}")
    print(f"Rate limit: {RATE_LIMIT_SLEEP}s between requests")
    print()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run tests
    results = {}

    for uuid in uuids:
        print(f"\n[UUID] {uuid}")
        print("-" * 80)

        # Get endpoint tests for this UUID
        tests = get_endpoint_tests(uuid=uuid)

        for test in tests:
            # Skip UUID-requiring tests if UUID not provided
            if test.requires_uuid and not uuid:
                continue

            # Execute test
            if verbose:
                print(f"\n[TEST] {test.name}")
                print(f"  URL: {test.build_url(uuid)}")
                print(f"  Method: {test.method}")

            result = test.execute(uuid=uuid)

            # Store result
            if test.name not in results:
                results[test.name] = []

            results[test.name].append(
                {
                    "uuid": uuid,
                    "success": result["success"],
                    "status_code": result["status_code"],
                    "error": result["error"],
                    "response_size": result["response_size"],
                }
            )

            # Save response if successful
            if result["success"] and result["response_data"]:
                save_response(
                    endpoint_name=test.name,
                    uuid=uuid,
                    response_data=result["response_data"],
                    output_dir=output_dir,
                )

                # Print success
                status_icon = "✅"
                print(
                    f"  [{status_icon}] {test.name:20s} {result['status_code']:3d}  {result['response_size']:6d} bytes"
                )
            else:
                # Print failure
                status_icon = "❌"
                print(
                    f"  [{status_icon}] {test.name:20s} {result['status_code']:3d}  Error: {result['error'][:60]}"
                )

            # Rate limiting
            time.sleep(RATE_LIMIT_SLEEP)

    # Also test global endpoints (no UUID)
    print("\n[GLOBAL] Endpoints (no UUID required)")
    print("-" * 80)

    global_tests = get_endpoint_tests(uuid=None)
    for test in global_tests:
        if test.requires_uuid:
            continue

        result = test.execute()

        if test.name not in results:
            results[test.name] = []

        results[test.name].append(
            {
                "uuid": None,
                "success": result["success"],
                "status_code": result["status_code"],
                "error": result["error"],
                "response_size": result["response_size"],
            }
        )

        if result["success"] and result["response_data"]:
            save_response(
                endpoint_name=test.name,
                uuid=None,
                response_data=result["response_data"],
                output_dir=output_dir,
            )

            status_icon = "✅"
            print(
                f"  [{status_icon}] {test.name:20s} {result['status_code']:3d}  {result['response_size']:6d} bytes"
            )
        else:
            status_icon = "❌"
            print(
                f"  [{status_icon}] {test.name:20s} {result['status_code']:3d}  Error: {result['error'][:60]}"
            )

        time.sleep(RATE_LIMIT_SLEEP)

    return results


def print_summary(results: dict[str, list[dict[str, Any]]]) -> None:
    """Print summary of test results

    Args:
        results: Dict mapping endpoint name to list of test results
    """
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80 + "\n")

    print(f"{'Endpoint':<25s} {'Total':>7s} {'Success':>7s} {'Failed':>7s} {'Success Rate':>12s}")
    print("-" * 80)

    for endpoint_name, endpoint_results in sorted(results.items()):
        total = len(endpoint_results)
        success = sum(1 for r in endpoint_results if r["success"])
        failed = total - success
        success_rate = (success / total * 100) if total > 0 else 0

        status_icon = "✅" if failed == 0 else ("⚠️" if success > 0 else "❌")

        print(
            f"{endpoint_name:<25s} {total:>7d} {success:>7d} {failed:>7d} {success_rate:>11.1f}%  {status_icon}"
        )

    print()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="LNB API Endpoint Smoke Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test all known UUIDs
    uv run python tools/lnb/smoke_test_endpoints.py

    # Test specific UUID
    uv run python tools/lnb/smoke_test_endpoints.py --uuid 3522345e-3362-11f0-b97d-7be2bdc7a840

    # Save to custom directory
    uv run python tools/lnb/smoke_test_endpoints.py --output-dir tools/lnb/test_responses
        """,
    )

    parser.add_argument(
        "--uuid", type=str, default=None, help="Test single UUID instead of all known UUIDs"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for JSON responses",
    )

    parser.add_argument("--verbose", action="store_true", help="Print detailed logs")

    args = parser.parse_args()

    # Determine UUIDs to test
    if args.uuid:
        uuids = [args.uuid]
    else:
        uuids = KNOWN_UUIDS

    # Run smoke test
    results = run_smoke_test(
        uuids=uuids,
        output_dir=Path(args.output_dir),
        verbose=args.verbose,
    )

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    main()
