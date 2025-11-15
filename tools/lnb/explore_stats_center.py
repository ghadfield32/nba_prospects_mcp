#!/usr/bin/env python3
"""Explore the stats center to find games with play-by-play data

Navigates to the stats center and tries to find working game pages with data.

Usage:
    uv run python tools/lnb/explore_stats_center.py
"""

import io
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 80)
print("  Exploring LNB Stats Center for Play-by-Play")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "stats_center_exploration"
output_dir.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    page = context.new_page()

    # Try different stats center URLs
    stats_urls = [
        "https://lnb.fr/fr/stats-centre",
        "https://lnb.fr/fr/betclic-elite/stats",
        "https://lnb.fr/fr/pro-a/stats",
    ]

    for url in stats_urls:
        print(f"[TRY] {url}")
        try:
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            if response and response.status == 200:
                print("  ✅ Loaded successfully")
                time.sleep(5)

                # Look for match/game links
                print("  [SEARCH] Looking for match links...")

                # Try to find links to individual games
                game_links = page.query_selector_all('a[href*="/match/"]')

                if game_links:
                    print(f"  [FOUND] {len(game_links)} match links")

                    # Get first few game URLs
                    game_urls = []
                    for link in game_links[:10]:
                        href = link.get_attribute("href")
                        if href and "/match/" in href:
                            # Make absolute URL
                            if href.startswith("/"):
                                full_url = f"https://lnb.fr{href}"
                            else:
                                full_url = href

                            game_urls.append(full_url)
                            print(f"    - {full_url}")

                    # Try first game link
                    if game_urls:
                        test_url = game_urls[0]
                        print()
                        print(f"  [TEST] Navigating to: {test_url}")

                        page.goto(test_url, wait_until="networkidle", timeout=30000)
                        time.sleep(5)

                        final_url = page.url
                        print(f"  [URL] Final: {final_url}")

                        if "/match/" in final_url and "404" not in page.content().lower():
                            print("  ✅ Game page loaded successfully!")

                            # Save HTML
                            html = page.content()
                            with open(
                                output_dir / "working_game_page.html", "w", encoding="utf-8"
                            ) as f:
                                f.write(html)

                            page.screenshot(path=str(output_dir / "working_game_page.png"))

                            print("  [SAVED] working_game_page.html")
                            print("  [SAVED] working_game_page.png")

                            # Extract game ID from URL
                            import re

                            match = re.search(r"/match/(\d+)", final_url)
                            if match:
                                game_id = match.group(1)
                                with open(output_dir / "working_game_id.txt", "w") as f:
                                    f.write(game_id)
                                print(f"  [INFO] Game ID: {game_id}")

                            break
                        else:
                            print("  ❌ Game page showed 404 or error")

                break

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")

        print()

    browser.close()

print()
print("=" * 80)
print("  EXPLORATION COMPLETE")
print("=" * 80)
print()

print(f"Results saved to: {output_dir}")
print()
