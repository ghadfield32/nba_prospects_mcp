#!/usr/bin/env python3
"""LNB API Header Testing Utility

This script helps you test different header combinations to find the right
authentication for api-prod.lnb.fr.

Usage:
    # Test with default headers
    python3 tools/lnb/test_api_headers.py

    # Test with custom headers from JSON file
    python3 tools/lnb/test_api_headers.py --headers-file my_headers.json

    # Test with cookies from string
    python3 tools/lnb/test_api_headers.py --cookies "session=abc123; token=xyz789"

    # Test specific endpoint
    python3 tools/lnb/test_api_headers.py --endpoint getAllYears

How to capture headers from DevTools:
    1. Open Chrome and go to https://www.lnb.fr/statistiques
    2. Open DevTools (F12) → Network tab → Filter by XHR
    3. Click around the site to trigger API calls
    4. Right-click a request to api-prod.lnb.fr → Copy → Copy as cURL
    5. Paste into headers_curl.txt and run:
       python3 tools/lnb/test_api_headers.py --curl-file headers_curl.txt

Example headers_curl.txt:
    curl 'https://api-prod.lnb.fr/common/getAllYears?end_year=2025' \\
      -H 'accept: application/json' \\
      -H 'origin: https://www.lnb.fr' \\
      -H 'referer: https://www.lnb.fr/statistiques' \\
      -H 'cookie: session=abc123; token=xyz789' \\
      --compressed

Created: 2025-11-14
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api-prod.lnb.fr"

# Test endpoints (simple GET requests)
TEST_ENDPOINTS = {
    "getAllYears": {
        "method": "GET",
        "path": "/common/getAllYears",
        "params": {"end_year": 2025},
    },
    "getMainCompetition": {
        "method": "GET",
        "path": "/common/getMainCompetition",
        "params": {"year": 2024},
    },
    "getLiveMatch": {
        "method": "GET",
        "path": "/stats/getLiveMatch",
        "params": {},
    },
}


def parse_curl_command(curl_text: str) -> Dict[str, Any]:
    """Parse a cURL command copied from DevTools.

    Extracts:
    - URL
    - Headers (-H flags)
    - Cookies (from -H 'cookie: ...' or --cookie)

    Returns:
        Dict with 'url', 'headers', 'cookies'
    """
    lines = curl_text.strip().split("\n")
    headers = {}
    cookies = {}
    url = None

    for line in lines:
        line = line.strip().rstrip("\\").strip()

        # Extract URL
        if line.startswith("curl "):
            parts = line.split()
            for part in parts:
                if part.startswith("http"):
                    url = part.strip("'\"")
                    break

        # Extract headers (-H 'key: value')
        if line.startswith("-H ") or line.startswith("--header"):
            # Remove -H or --header prefix
            header_text = line.replace("-H ", "").replace("--header ", "").strip("'\"")
            if ":" in header_text:
                key, value = header_text.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Special handling for cookie header
                if key.lower() == "cookie":
                    for cookie_pair in value.split(";"):
                        if "=" in cookie_pair:
                            ck, cv = cookie_pair.strip().split("=", 1)
                            cookies[ck] = cv
                else:
                    headers[key] = value

    return {
        "url": url or BASE_URL,
        "headers": headers,
        "cookies": cookies,
    }


def test_endpoint(
    endpoint_name: str,
    headers: Dict[str, str],
    cookies: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Test a single endpoint with given headers and cookies.

    Returns:
        Dict with 'success', 'status_code', 'data', 'error'
    """
    if endpoint_name not in TEST_ENDPOINTS:
        return {
            "success": False,
            "error": f"Unknown endpoint: {endpoint_name}. Choose from: {list(TEST_ENDPOINTS.keys())}",
        }

    endpoint_config = TEST_ENDPOINTS[endpoint_name]
    url = f"{BASE_URL}{endpoint_config['path']}"
    method = endpoint_config["method"]
    params = endpoint_config["params"]

    logger.info(f"\nTesting: {method} {url}")
    logger.info(f"Params: {params}")
    logger.info(f"Headers: {json.dumps(headers, indent=2)}")
    if cookies:
        logger.info(f"Cookies: {len(cookies)} cookies set")

    try:
        session = requests.Session()
        if cookies:
            for key, value in cookies.items():
                session.cookies.set(key, value)

        resp = session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            timeout=15,
        )

        logger.info(f"Response: {resp.status_code} {resp.reason}")

        # Try to parse JSON
        try:
            data = resp.json()
            logger.info(f"Data type: {type(data)}")
            if isinstance(data, dict):
                logger.info(f"Data keys: {list(data.keys())}")
            elif isinstance(data, list):
                logger.info(f"Data length: {len(data)}")
        except Exception:
            data = resp.text[:500]  # First 500 chars

        if resp.status_code == 200:
            logger.info("✅ SUCCESS!")
            return {
                "success": True,
                "status_code": resp.status_code,
                "data": data,
            }
        else:
            logger.error(f"❌ FAILED: {resp.status_code} {resp.reason}")
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": resp.text[:500],
            }

    except Exception as e:
        logger.error(f"❌ EXCEPTION: {e!r}")
        return {
            "success": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Test LNB API headers and authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--endpoint",
        default="getAllYears",
        choices=list(TEST_ENDPOINTS.keys()),
        help="Endpoint to test (default: getAllYears)",
    )

    parser.add_argument(
        "--headers-file",
        type=str,
        help="JSON file with headers (e.g., {'User-Agent': '...', 'Cookie': '...'})",
    )

    parser.add_argument(
        "--cookies",
        type=str,
        help="Cookie string (e.g., 'session=abc123; token=xyz789')",
    )

    parser.add_argument(
        "--curl-file",
        type=str,
        help="File containing cURL command copied from DevTools",
    )

    parser.add_argument(
        "--origin",
        type=str,
        default="https://www.lnb.fr",
        help="Origin header (default: https://www.lnb.fr)",
    )

    parser.add_argument(
        "--referer",
        type=str,
        default="https://www.lnb.fr/statistiques",
        help="Referer header (default: https://www.lnb.fr/statistiques)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("LNB API Header Testing Utility")
    print("=" * 60)

    # Build headers
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": args.origin,
        "Referer": args.referer,
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    }

    cookies = {}

    # Load from cURL file if provided
    if args.curl_file:
        print(f"\n[INFO] Loading headers from cURL file: {args.curl_file}")
        try:
            with open(args.curl_file, "r") as f:
                curl_text = f.read()
            parsed = parse_curl_command(curl_text)
            headers.update(parsed["headers"])
            cookies.update(parsed["cookies"])
            print(f"✅ Parsed {len(parsed['headers'])} headers and {len(parsed['cookies'])} cookies")
        except Exception as e:
            print(f"❌ Failed to parse cURL file: {e}")
            sys.exit(1)

    # Load from headers JSON file if provided
    if args.headers_file:
        print(f"\n[INFO] Loading headers from JSON file: {args.headers_file}")
        try:
            with open(args.headers_file, "r") as f:
                file_headers = json.load(f)
            headers.update(file_headers)
            print(f"✅ Loaded {len(file_headers)} headers")
        except Exception as e:
            print(f"❌ Failed to load headers file: {e}")
            sys.exit(1)

    # Parse cookies string if provided
    if args.cookies:
        print(f"\n[INFO] Parsing cookie string")
        for cookie_pair in args.cookies.split(";"):
            if "=" in cookie_pair:
                key, value = cookie_pair.strip().split("=", 1)
                cookies[key] = value
        print(f"✅ Parsed {len(cookies)} cookies")

    # Test the endpoint
    print(f"\n[TEST] Testing endpoint: {args.endpoint}")
    print("=" * 60)

    result = test_endpoint(
        endpoint_name=args.endpoint,
        headers=headers,
        cookies=cookies,
    )

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)

    if result["success"]:
        print("✅ SUCCESS!")
        print(f"\nStatus: {result['status_code']}")
        print(f"\nData preview:")
        data = result["data"]
        if isinstance(data, dict):
            print(json.dumps(data, indent=2)[:1000])
        elif isinstance(data, list):
            print(f"List with {len(data)} items")
            if data:
                print(json.dumps(data[0], indent=2)[:500])
        else:
            print(str(data)[:500])
    else:
        print("❌ FAILED!")
        print(f"\nStatus: {result.get('status_code', 'N/A')}")
        print(f"\nError: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)

    # Suggest next steps
    if not result["success"]:
        print("\n💡 NEXT STEPS:")
        print("1. Open Chrome and go to: https://www.lnb.fr/statistiques")
        print("2. Open DevTools (F12) → Network tab → Filter by XHR")
        print("3. Click around to trigger API calls to api-prod.lnb.fr")
        print("4. Right-click a successful request → Copy → Copy as cURL")
        print("5. Save to 'headers_curl.txt' and run:")
        print("   python3 tools/lnb/test_api_headers.py --curl-file headers_curl.txt")
        print("\nOR:")
        print("1. In DevTools, click the request → Headers tab")
        print("2. Copy all Request Headers to a JSON file")
        print("3. Run: python3 tools/lnb/test_api_headers.py --headers-file headers.json")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
