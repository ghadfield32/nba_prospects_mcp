#!/usr/bin/env python3
"""Navigate directly to game page using multiple URL patterns

Tries different URL formats to find the working game page URL.

Usage:
    uv run python tools/lnb/navigate_to_game_direct.py
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
print("  Testing Different Game Page URL Patterns")
print("  Game: 28910 (Cholet vs Nanterre)")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "game_page_direct"
output_dir.mkdir(exist_ok=True)

GAME_ID = 28910

# Different URL patterns to try
url_patterns = [
    f"https://lnb.fr/fr/match/{GAME_ID}",
    f"https://www.lnb.fr/fr/match/{GAME_ID}",
    f"https://lnb.fr/match/{GAME_ID}",
    f"https://www.lnb.fr/match/{GAME_ID}",
    f"https://lnb.fr/fr/betclic-elite/match/{GAME_ID}",
    f"https://www.lnb.fr/fr/betclic-elite/match/{GAME_ID}",
    f"https://lnb.fr/fr/pro-a/match/{GAME_ID}",
    f"https://www.lnb.fr/fr/pro-a/match/{GAME_ID}",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    page = context.new_page()

    for i, url in enumerate(url_patterns):
        print(f"[TRY {i+1}/{len(url_patterns)}] {url}")
        print("-" * 80)

        try:
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            final_url = page.url
            status = response.status

            print(f"  HTTP {status}")
            print(f"  Final URL: {final_url}")

            # Check if we got redirected to home page
            if "match" in final_url and str(GAME_ID) in final_url:
                print("  ✅ SUCCESS - Stayed on game page!")
                print()

                # Wait for content
                time.sleep(5)

                # Save HTML
                html = page.content()
                with open(
                    output_dir / f"game_page_{GAME_ID}_success.html", "w", encoding="utf-8"
                ) as f:
                    f.write(html)

                # Screenshot
                page.screenshot(path=str(output_dir / f"game_page_{GAME_ID}_success.png"))

                print(f"  [SAVED] game_page_{GAME_ID}_success.html")
                print(f"  [SAVED] game_page_{GAME_ID}_success.png")
                print()

                # Look for Événements button
                print("  [SEARCH] Looking for Événements content...")
                try:
                    # Look for visible buttons
                    evt_buttons = page.query_selector_all('button:has-text("Événements")')
                    visible_buttons = [b for b in evt_buttons if b.is_visible()]

                    if visible_buttons:
                        print(f"  [FOUND] {len(visible_buttons)} visible Événements buttons")

                        # Click the first one
                        btn = visible_buttons[0]
                        print("  [CLICK] Clicking button...")
                        btn.click(force=True)
                        time.sleep(5)

                        # Save HTML after click
                        html_after = page.content()
                        with open(
                            output_dir / f"game_page_{GAME_ID}_after_click.html",
                            "w",
                            encoding="utf-8",
                        ) as f:
                            f.write(html_after)

                        page.screenshot(
                            path=str(output_dir / f"game_page_{GAME_ID}_after_click.png")
                        )

                        print(f"  [SAVED] game_page_{GAME_ID}_after_click.html")
                        print(f"  [SAVED] game_page_{GAME_ID}_after_click.png")

                    else:
                        print("  [INFO] Événements buttons exist but not visible")

                except Exception as e:
                    print(f"  [ERROR] Failed to click button: {e}")

                print()
                print(f"  🎯 FOUND WORKING URL: {url}")
                break

            elif final_url == "https://lnb.fr/fr" or final_url == "https://www.lnb.fr/fr":
                print("  ❌ FAIL - Redirected to home page")

            else:
                print("  ⚠️  REDIRECTED - Unexpected destination")

        except Exception as e:
            print(f"  ❌ ERROR: {str(e)[:100]}")

        print()

    browser.close()

print("=" * 80)
print("  URL PATTERN TESTING COMPLETE")
print("=" * 80)
print()

print(f"Results saved to: {output_dir}")
print()
