#!/usr/bin/env python3
"""Inspect LNB Calendar Filter Mechanism

Goal: Find the dropdown/filter that switches between leagues on the calendar page.
We discovered that Elite 2 IDs are in the HTML but not rendered by default.

This script will:
1. Extract all dropdown/select elements from the page
2. Find elements with class containing "filter", "league", "competition"
3. Identify the JavaScript that handles league switching
4. Determine how to programmatically trigger Elite 2 filter

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

# ==============================================================================
# FILTER INSPECTION
# ==============================================================================


def extract_filter_elements(html: str) -> dict:
    """Extract all potential filter/dropdown elements from HTML"""
    results = {
        "select_elements": [],
        "filter_classes": [],
        "dropdown_classes": [],
        "competition_refs": [],
        "league_refs": [],
    }

    # 1. Find all <select> elements
    select_pattern = re.compile(
        r"<select[^>]*>(.*?)</select>",
        re.IGNORECASE | re.DOTALL,
    )
    select_matches = select_pattern.findall(html)
    results["select_elements"] = select_matches[:5]  # First 5

    # 2. Find elements with "filter" in class name
    filter_pattern = re.compile(
        r'class="[^"]*filter[^"]*"[^>]*>([^<]*)<',
        re.IGNORECASE,
    )
    filter_matches = filter_pattern.findall(html)
    results["filter_classes"] = list(set(filter_matches))[:10]

    # 3. Find elements with "dropdown" in class name
    dropdown_pattern = re.compile(
        r'class="[^"]*dropdown[^"]*"[^>]*>([^<]*)<',
        re.IGNORECASE,
    )
    dropdown_matches = dropdown_pattern.findall(html)
    results["dropdown_classes"] = list(set(dropdown_matches))[:10]

    # 4. Find "competition" or "league" related data attributes
    comp_pattern = re.compile(
        r'data-[^=]*(?:competition|league)[^=]*="([^"]+)"',
        re.IGNORECASE,
    )
    comp_matches = comp_pattern.findall(html)
    results["competition_refs"] = list(set(comp_matches))[:10]

    # 5. Look for Vue.js / React state with competition data
    state_pattern = re.compile(
        r"(?:competitions?|leagues?)\s*[:=]\s*\[([^\]]+)\]",
        re.IGNORECASE,
    )
    state_matches = state_pattern.findall(html)
    results["league_refs"] = state_matches[:5]

    return results


def find_league_selector_js(html: str) -> list[str]:
    """Find JavaScript code related to league/competition selection"""
    js_patterns = [
        # Function calls with "competition" or "league"
        r"function\s+\w*(?:select|change|switch)\w*Competition\w*\([^)]*\)\s*{[^}]+}",
        r"function\s+\w*(?:select|change|switch)\w*League\w*\([^)]*\)\s*{[^}]+}",
        # Event listeners
        r'addEventListener\(["\'](?:change|click)["\'],\s*function[^{]*{[^}]+competition[^}]+}',
        # Vue/React methods
        r'(?:@click|onClick)="[^"]*(?:competition|league)[^"]*"',
    ]

    found_js = []
    for pattern_str in js_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
        matches = pattern.findall(html)
        if matches:
            found_js.extend(matches[:2])  # First 2 of each type

    return found_js


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("=" * 80)
    print("  LNB CALENDAR FILTER INSPECTION")
    print("=" * 80)
    print()
    print("Goal: Find the UI element that switches between Betclic ELITE and Elite 2")
    print()

    url = "https://www.lnb.fr/elite-2/calendrier"
    print(f"Analyzing: {url}")
    print()

    try:
        with BrowserScraper(headless=True, timeout=30000) as scraper:
            print("[1/3] Fetching page HTML...")
            html = scraper.get_rendered_html(url=url, wait_time=5.0)
            print(f"      HTML size: {len(html):,} characters\n")

            print("[2/3] Extracting filter elements...")
            filters = extract_filter_elements(html)

            print("\n  [SELECT ELEMENTS]")
            if filters["select_elements"]:
                for i, select in enumerate(filters["select_elements"], 1):
                    # Clean up whitespace
                    clean_select = " ".join(select.split())
                    print(f"    {i}. {clean_select[:200]}...")
            else:
                print("    (None found)")

            print("\n  [FILTER CLASS ELEMENTS]")
            if filters["filter_classes"]:
                for text in filters["filter_classes"][:10]:
                    if text.strip():
                        print(f"    - {text.strip()}")
            else:
                print("    (None found)")

            print("\n  [DROPDOWN CLASS ELEMENTS]")
            if filters["dropdown_classes"]:
                for text in filters["dropdown_classes"][:10]:
                    if text.strip():
                        print(f"    - {text.strip()}")
            else:
                print("    (None found)")

            print("\n  [COMPETITION/LEAGUE DATA ATTRIBUTES]")
            if filters["competition_refs"]:
                for ref in filters["competition_refs"][:10]:
                    print(f"    - {ref}")
            else:
                print("    (None found)")

            print("\n  [LEAGUE STATE IN JAVASCRIPT]")
            if filters["league_refs"]:
                for ref in filters["league_refs"][:5]:
                    # Clean up
                    clean_ref = " ".join(ref.split())
                    print(f"    - {clean_ref[:150]}...")
            else:
                print("    (None found)")

            print("\n[3/3] Searching for league selector JavaScript...")
            js_code = find_league_selector_js(html)

            if js_code:
                print(f"\n  Found {len(js_code)} potential JavaScript handlers:")
                for i, code in enumerate(js_code, 1):
                    clean_code = " ".join(code.split())
                    print(f"\n  [{i}] {clean_code[:300]}...")
            else:
                print("\n  (No JavaScript handlers found)")

            # BONUS: Look for specific HTML patterns
            print("\n\n[BONUS] Looking for specific UI patterns...")

            # Check for tabs
            tab_pattern = re.compile(
                r'<(?:div|li)[^>]*class="[^"]*tab[^"]*"[^>]*>([^<]*)<',
                re.IGNORECASE,
            )
            tabs = tab_pattern.findall(html)
            if tabs:
                unique_tabs = list(set(tabs))[:10]
                print(f"\n  [TABS FOUND] {len(unique_tabs)} unique tab labels:")
                for tab in unique_tabs:
                    if tab.strip():
                        print(f"    - {tab.strip()}")

            # Check for buttons with competition/league text
            button_pattern = re.compile(
                r"<button[^>]*>([^<]*(?:elite|pro|competition|league)[^<]*)</button>",
                re.IGNORECASE,
            )
            buttons = button_pattern.findall(html)
            if buttons:
                print(f"\n  [BUTTONS FOUND] {len(buttons)} buttons with league keywords:")
                for btn in buttons[:10]:
                    if btn.strip():
                        print(f"    - {btn.strip()}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("  ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("Next Steps:")
    print("  1. Review the filter elements found above")
    print("  2. Identify which element controls league switching")
    print("  3. Update scraper to interact with that element before extracting UUIDs")
    print()


if __name__ == "__main__":
    main()
