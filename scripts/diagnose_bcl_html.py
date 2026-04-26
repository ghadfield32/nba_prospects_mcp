#!/usr/bin/env python
"""Diagnose what HTML BCL pages are actually returning."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.fetchers.browser_scraper import BrowserScraper  # noqa: E402

FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"
test_game_id = "119854-VEF-DSK"

print("=" * 70)
print("BCL HTML DIAGNOSTIC")
print("=" * 70)
print()
print(f"Game ID: {test_game_id}")
print(f"URL: {FIBA_BASE_URL}/u/BCL/{test_game_id}/bs.html")
print()

try:
    with BrowserScraper(headless=True, timeout=30000) as scraper:
        url = f"{FIBA_BASE_URL}/u/BCL/{test_game_id}/bs.html"

        # Fetch without waiting for specific selector
        html = scraper.get_rendered_html(url, wait_time=5.0)

        print(f"HTML Length: {len(html)} characters")
        print()
        print("First 2000 characters:")
        print("-" * 70)
        print(html[:2000])
        print("-" * 70)
        print()
        print("Last 500 characters:")
        print("-" * 70)
        print(html[-500:])
        print("-" * 70)

        # Save full HTML for inspection
        output_file = Path(__file__).parent.parent / "cache" / "bcl_diagnostic.html"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding="utf-8")
        print()
        print(f"Full HTML saved to: {output_file}")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
