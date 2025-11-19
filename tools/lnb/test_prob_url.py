#!/usr/bin/env python3
"""Test if Pro B (old name) URL provides different Elite 2 data

The Elite 2 page shows Betclic ELITE games. Let's check if the old
Pro B URL structure provides actual Elite 2/Pro B games.

URLs to test:
- https://www.lnb.fr/prob/calendrier (old Pro B URL)
- https://www.lnb.fr/elite-2/calendrier (new Elite 2 URL)

Created: 2025-11-18
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.cbb_data.fetchers.browser_scraper import BrowserScraper

UUID_PATTERN = re.compile(
    r"/(?:fr/)?match-center/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def extract_uuids(html: str) -> list[str]:
    """Extract unique UUIDs from HTML"""
    matches = UUID_PATTERN.findall(html)
    seen = set()
    unique = []
    for uuid in matches:
        if uuid not in seen:
            seen.add(uuid)
            unique.append(uuid)
    return unique


def test_url(url: str, name: str) -> dict:
    """Test a URL for Elite 2/Pro B game UUIDs"""
    print(f"\n[TEST] {name}")
    print(f"  URL: {url}")

    result = {
        "url": url,
        "name": name,
        "uuids": [],
        "html_size": 0,
        "error": None,
    }

    try:
        with BrowserScraper(headless=True, timeout=30000) as scraper:
            html = scraper.get_rendered_html(url=url, wait_time=5.0)
            result["html_size"] = len(html)
            result["uuids"] = extract_uuids(html)

            print(f"  HTML size: {len(html):,} chars")
            print(f"  UUIDs found: {len(result['uuids'])}")

            if result["uuids"]:
                print("  First 3 UUIDs:")
                for uuid in result["uuids"][:3]:
                    print(f"    - {uuid}")

    except Exception as e:
        print(f"  [ERROR] {e}")
        result["error"] = str(e)

    return result


def main():
    print("=" * 80)
    print("  PRO B / ELITE 2 URL COMPARISON TEST")
    print("=" * 80)
    print()
    print("Goal: Determine if old Pro B URL provides different data than Elite 2 URL")
    print()

    urls_to_test = [
        ("https://www.lnb.fr/prob/calendrier", "Pro B (old name)"),
        ("https://www.lnb.fr/elite-2/calendrier", "Elite 2 (new name)"),
    ]

    results = []
    for url, name in urls_to_test:
        result = test_url(url, name)
        results.append(result)

    # Compare results
    print("\n" + "=" * 80)
    print("  COMPARISON")
    print("=" * 80)
    print()

    prob_uuids = set(results[0]["uuids"])
    elite2_uuids = set(results[1]["uuids"])

    print(f"Pro B URL UUIDs: {len(prob_uuids)}")
    print(f"Elite 2 URL UUIDs: {len(elite2_uuids)}")
    print()

    if prob_uuids == elite2_uuids:
        print("✗ SAME: Both URLs return identical UUIDs")
        print("  (Pro B and Elite 2 URLs show same data)")
    else:
        print("✓ DIFFERENT: URLs return different UUIDs!")
        prob_only = prob_uuids - elite2_uuids
        elite2_only = elite2_uuids - prob_uuids

        if prob_only:
            print(f"  Pro B exclusive: {len(prob_only)} UUIDs")
            print(f"    Sample: {list(prob_only)[:3]}")

        if elite2_only:
            print(f"  Elite 2 exclusive: {len(elite2_only)} UUIDs")
            print(f"    Sample: {list(elite2_only)[:3]}")

    print()


if __name__ == "__main__":
    main()
