#!/usr/bin/env python3
"""Deep exploration of LNB website for play-by-play and shot chart data

Systematically explores LNB website structure to find:
- Play-by-play data (event logs, timeline, actions)
- Shot chart data (shot locations, coordinates, x/y positions)
- Any other hidden data sources

Usage:
    uv run python tools/lnb/explore_lnb_website.py
"""

import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cbb_data.fetchers.browser_scraper import BrowserScraper

print("=" * 80)
print("  LNB Website Deep Exploration")
print("  Searching for: Play-by-Play & Shot Chart Data")
print("=" * 80)
print()

# Create output directory
output_dir = Path(__file__).parent / "exploration_output"
output_dir.mkdir(exist_ok=True)
print(f"[INFO] Output directory: {output_dir}")
print()


def save_html(html: str, filename: str):
    """Save HTML to file for later inspection"""
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [SAVED] {filepath.name} ({len(html)} chars)")


def extract_network_requests(page):
    """Extract network requests that might contain data"""
    # This would require hooking into browser network events
    # For now, we'll look for data embedded in the page
    pass


# Step 1: Explore main stats page
print("[STEP 1] Exploring main statistics page...")
print("-" * 80)

with BrowserScraper(headless=False, timeout=60000) as scraper:
    # Navigate to main stats page
    url_stats = "https://www.lnb.fr/pro-a/statistiques"
    print(f"[NAVIGATE] {url_stats}")

    html_stats = scraper.get_rendered_html(
        url=url_stats,
        wait_for="body",
        wait_time=5.0,  # Give time for JS to load
    )

    save_html(html_stats, "01_main_stats_page.html")

    # Look for links to game pages
    print()
    print("[SEARCH] Looking for game/match links...")

    # Common patterns for game pages
    game_patterns = [
        "/match/",
        "/rencontre/",
        "/game/",
        "/stats-centre",
        "/live",
        "/boxscore",
    ]

    game_links = []
    for pattern in game_patterns:
        if pattern in html_stats.lower():
            print(f"  [FOUND] Pattern '{pattern}' exists in page")
            # Extract actual URLs (simplified - would need proper HTML parsing)
            import re

            urls = re.findall(
                rf'href=["\']([^"\']*{pattern}[^"\']*)["\']', html_stats, re.IGNORECASE
            )
            for url in urls[:3]:  # First 3 examples
                print(f"    → {url}")
                if url not in game_links:
                    game_links.append(url)

    print(f"\n[RESULT] Found {len(game_links)} potential game page URLs")

    # Step 2: Explore a specific game page
    if game_links:
        print()
        print("[STEP 2] Exploring specific game page...")
        print("-" * 80)

        # Take first game link and make it absolute
        test_game_url = game_links[0]
        if not test_game_url.startswith("http"):
            test_game_url = f"https://www.lnb.fr{test_game_url}"

        print(f"[NAVIGATE] {test_game_url}")

        # Before navigating, set up network monitoring
        # Get the page object directly
        page = scraper._page

        # Track API calls
        api_calls = []

        def handle_request(request):
            url = request.url
            # Look for API endpoints
            if any(
                pattern in url.lower()
                for pattern in ["api", "stats", "data", "json", "pbp", "play", "shot", "event"]
            ):
                api_calls.append(
                    {"url": url, "method": request.method, "resource_type": request.resource_type}
                )
                print(f"  [API] {request.method} {url}")

        page.on("request", handle_request)

        # Navigate to game page
        try:
            page.goto(test_game_url, wait_until="networkidle", timeout=60000)

            # Wait for any stats to load
            import time

            time.sleep(5)

            html_game = page.content()
            save_html(html_game, "02_game_page.html")

            print()
            print(f"[RESULT] Captured {len(api_calls)} API calls")

            # Save API calls
            if api_calls:
                api_file = output_dir / "api_calls.json"
                with open(api_file, "w", encoding="utf-8") as f:
                    json.dump(api_calls, f, indent=2)
                print(f"[SAVED] {api_file.name}")

            # Step 3: Look for play-by-play indicators
            print()
            print("[STEP 3] Searching for play-by-play indicators...")
            print("-" * 80)

            pbp_keywords = [
                "play-by-play",
                "play by play",
                "timeline",
                "événements",  # French: events
                "actions",
                "action de jeu",  # French: game action
                "quart-temps",  # French: quarter
                "temps-mort",  # French: timeout
                "faute",  # French: foul
                "panier",  # French: basket
                "tir",  # French: shot
            ]

            found_pbp = []
            for keyword in pbp_keywords:
                if keyword.lower() in html_game.lower():
                    found_pbp.append(keyword)

            if found_pbp:
                print(f"[FOUND] Play-by-play keywords: {', '.join(found_pbp)}")
            else:
                print("[NOT FOUND] No play-by-play keywords detected")

            # Step 4: Look for shot chart indicators
            print()
            print("[STEP 4] Searching for shot chart indicators...")
            print("-" * 80)

            shot_keywords = [
                "shot chart",
                "shot-chart",
                "shotchart",
                "carte des tirs",  # French: shot map
                "positions de tir",  # French: shot positions
                "x_coord",
                "y_coord",
                "coordinates",
                "coordonnées",  # French: coordinates
                "canvas",  # Often used for drawing shot charts
                "svg",  # SVG graphics for shot charts
            ]

            found_shots = []
            for keyword in shot_keywords:
                if keyword.lower() in html_game.lower():
                    found_shots.append(keyword)

            if found_shots:
                print(f"[FOUND] Shot chart keywords: {', '.join(found_shots)}")
            else:
                print("[NOT FOUND] No shot chart keywords detected")

            # Step 5: Look for JavaScript data objects
            print()
            print("[STEP 5] Searching for embedded JavaScript data...")
            print("-" * 80)

            # Look for common JS data patterns
            js_patterns = [
                r"var\s+(\w+)\s*=\s*\{[^}]*(?:shot|play|event|action)[^}]*\}",
                r"const\s+(\w+)\s*=\s*\{[^}]*(?:shot|play|event|action)[^}]*\}",
                r"window\.(\w+)\s*=\s*\{[^}]*(?:shot|play|event|action)[^}]*\}",
            ]

            import re

            js_data_objects = []

            for pattern in js_patterns:
                matches = re.findall(pattern, html_game, re.IGNORECASE)
                if matches:
                    js_data_objects.extend(matches)

            if js_data_objects:
                print(f"[FOUND] JavaScript data objects: {', '.join(set(js_data_objects[:10]))}")
            else:
                print("[NOT FOUND] No JavaScript data objects detected")

            # Step 6: Look for additional tabs/sections
            print()
            print("[STEP 6] Searching for interactive tabs/sections...")
            print("-" * 80)

            # Look for tab/navigation elements
            tab_selectors = [
                'a[href*="stats"]',
                'a[href*="play"]',
                'a[href*="shot"]',
                "button[data-tab]",
                ".tab",
                ".nav-tab",
                '[role="tab"]',
            ]

            for selector in tab_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        print(f"[FOUND] {len(elements)} elements matching '{selector}'")
                        for i, elem in enumerate(elements[:3]):
                            text = elem.text_content()
                            if text and text.strip():
                                print(f"  → Tab {i+1}: {text.strip()}")
                except Exception:
                    pass

            # Step 7: Try clicking on statistics/advanced stats tabs
            print()
            print("[STEP 7] Attempting to click advanced stats tabs...")
            print("-" * 80)

            # Common French/English tab texts
            tab_texts = [
                "Statistiques avancées",
                "Advanced stats",
                "Play-by-play",
                "Timeline",
                "Shots",
                "Tirs",
                "Actions",
                "Events",
            ]

            for tab_text in tab_texts:
                try:
                    # Try to find and click tab
                    tab = page.query_selector(f'text="{tab_text}"')
                    if tab:
                        print(f"[FOUND] Tab: '{tab_text}' - attempting click...")
                        tab.click()
                        time.sleep(3)  # Wait for content to load

                        # Capture new HTML
                        html_after = page.content()
                        save_html(html_after, f"03_after_click_{tab_text.replace(' ', '_')}.html")

                        # Check for new API calls
                        print("  [INFO] Content updated, checking for new data...")
                except Exception:
                    pass

        except Exception as e:
            print(f"[ERROR] Failed to explore game page: {e}")
            import traceback

            traceback.print_exc()

    # Step 8: Explore stats-centre or live game pages
    print()
    print("[STEP 8] Exploring stats-centre and live pages...")
    print("-" * 80)

    stats_centre_urls = [
        "https://www.lnb.fr/fr/stats-centre",
        "https://www.lnb.fr/stats-centre",
    ]

    for url in stats_centre_urls:
        try:
            print(f"[NAVIGATE] {url}")
            page = scraper._page

            # Set up request monitoring again
            api_calls_stats = []

            def handle_stats_request(request, calls_list=api_calls_stats):
                """Handle request events - captures calls_list to avoid late binding"""
                url_req = request.url
                if any(pattern in url_req.lower() for pattern in ["api", "stats", "data", "json"]):
                    calls_list.append({"url": url_req, "method": request.method})
                    print(f"  [API] {request.method} {url_req}")

            page.on("request", handle_stats_request)

            page.goto(url, wait_until="networkidle", timeout=60000)

            import time

            time.sleep(5)

            html_stats_centre = page.content()
            save_html(html_stats_centre, "04_stats_centre.html")

            if api_calls_stats:
                api_file_stats = output_dir / "api_calls_stats_centre.json"
                with open(api_file_stats, "w", encoding="utf-8") as f:
                    json.dump(api_calls_stats, f, indent=2)
                print(f"[SAVED] {api_file_stats.name}")

            break  # If successful, don't try other URLs

        except Exception as e:
            print(f"[ERROR] Failed to access {url}: {e}")
            continue

# Final summary
print()
print("=" * 80)
print("  EXPLORATION SUMMARY")
print("=" * 80)
print()

print("Files saved to:", output_dir)
print()

print("Next steps:")
print("1. Review HTML files in exploration_output/ folder")
print("2. Review api_calls.json for API endpoints")
print("3. Look for patterns in the captured network requests")
print("4. Search for hidden data attributes in HTML elements")
print("5. Check browser DevTools Network tab during manual exploration")
print()

print("[COMPLETE] Exploration finished")
print()
