#!/usr/bin/env python3
"""Monitor network requests when loading a specific game page

Captures all API calls and responses to find play-by-play and shot data.

Usage:
    uv run python tools/lnb/monitor_game_page_requests.py
"""

import io
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 80)
print("  Monitoring Network Requests for Game Page")
print("  Game: 28910 (Cholet vs Nanterre)")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "game_network_monitoring"
output_dir.mkdir(exist_ok=True)

GAME_ID = 28910
GAME_URL = f"https://www.lnb.fr/fr/match/{GAME_ID}"

print(f"Target URL: {GAME_URL}")
print()

# Storage for captured data
captured_responses = []
api_calls = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    page = context.new_page()

    # =================================================================
    # SET UP NETWORK MONITORING
    # =================================================================
    def handle_response(response):
        """Capture all API responses"""
        url = response.url

        # Only capture API calls
        if "api-prod.lnb.fr" in url or "api.lnb.fr" in url or "altrstat" in url:
            try:
                # Try to get response body
                body = None
                try:
                    body = response.json()
                except Exception:
                    try:
                        body = response.text()
                    except Exception:
                        pass

                api_call = {
                    "url": url,
                    "method": response.request.method,
                    "status": response.status,
                    "response_body": body,
                }

                api_calls.append(api_call)

                # Print interesting API calls
                if str(GAME_ID) in url or "match" in url.lower():
                    print(f"[API] {response.request.method} {url} - HTTP {response.status}")
                    if body and isinstance(body, dict):
                        print(f"      Response keys: {list(body.keys())[:10]}")
            except Exception as e:
                print(f"[ERROR] Failed to capture response from {url}: {e}")

    page.on("response", handle_response)

    # =================================================================
    # NAVIGATE TO GAME PAGE
    # =================================================================
    print("[LOAD] Navigating to game page...")
    print("-" * 80)

    try:
        response = page.goto(GAME_URL, wait_until="networkidle", timeout=60000)

        print(f"[STATUS] HTTP {response.status}")
        print(f"[URL] Final URL: {page.url}")

        # Check if we got redirected
        if page.url != GAME_URL:
            print(f"[WARNING] Redirected from {GAME_URL} to {page.url}")

        print()

        # Wait for JavaScript to load
        import time

        time.sleep(5)

        # =================================================================
        # CHECK FOR EMBEDDED JSON DATA IN SCRIPT TAGS
        # =================================================================
        print("[SEARCH] Looking for embedded JSON data in <script> tags...")
        print("-" * 80)

        # Execute JavaScript to find data objects
        embedded_data = page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script');
                const jsonData = [];

                for (const script of scripts) {
                    const text = script.textContent || script.innerText;

                    // Look for common variable patterns
                    const patterns = [
                        /var\\s+(\\w+)\\s*=\\s*(\\{[^;]+\\})/g,
                        /const\\s+(\\w+)\\s*=\\s*(\\{[^;]+\\})/g,
                        /window\\.(\\w+)\\s*=\\s*(\\{[^;]+\\})/g
                    ];

                    for (const pattern of patterns) {
                        const matches = [...text.matchAll(pattern)];
                        for (const match of matches) {
                            if (match[2].includes('match') || match[2].includes('game') ||
                                match[2].includes('event') || match[2].includes('shot')) {
                                jsonData.push({
                                    varName: match[1],
                                    preview: match[2].substring(0, 200)
                                });
                            }
                        }
                    }
                }

                return jsonData;
            }
        """)

        if embedded_data:
            print(f"[FOUND] {len(embedded_data)} potential data objects in <script> tags")
            for item in embedded_data[:5]:
                print(f"  Variable: {item['varName']}")
                print(f"  Preview: {item['preview'][:100]}...")
                print()

            with open(output_dir / "embedded_script_data.json", "w", encoding="utf-8") as f:
                json.dump(embedded_data, f, indent=2, ensure_ascii=False)
            print("[SAVED] embedded_script_data.json")
        else:
            print("[NOT FOUND] No embedded JSON data detected")

        print()

        # =================================================================
        # SCROLL PAGE TO TRIGGER LAZY LOADING
        # =================================================================
        print("[ACTION] Scrolling page to trigger lazy-loaded content...")
        print("-" * 80)

        # Scroll down slowly
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        print("[DONE] Scrolled to bottom, waiting for requests...")
        time.sleep(3)
        print()

        # =================================================================
        # LOOK FOR TABS AND CLICK THEM
        # =================================================================
        print("[ACTION] Looking for and clicking tabs...")
        print("-" * 80)

        # Look for stats/events tabs
        tab_selectors = [
            'button:has-text("Statistiques")',
            'button:has-text("Événements")',
            'button:has-text("Actions")',
            'a:has-text("Statistiques")',
            'a:has-text("Événements")',
        ]

        for selector in tab_selectors:
            try:
                # Find all matching elements
                elements = page.query_selector_all(selector)

                # Filter to visible ones only
                for elem in elements:
                    if elem.is_visible():
                        text = elem.inner_text()
                        print(f"[FOUND] Visible tab: '{text}'")
                        print("[CLICK] Clicking...")

                        elem.click()
                        time.sleep(3)  # Wait for content to load

                        print(f"[SUCCESS] Clicked '{text}' tab")
                        print()
                        break
            except Exception:
                pass

        # =================================================================
        # SAVE RESULTS
        # =================================================================
        print("[SAVE] Saving captured data...")
        print("-" * 80)

        # Save all API calls
        with open(output_dir / "all_api_calls.json", "w", encoding="utf-8") as f:
            json.dump(api_calls, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] all_api_calls.json ({len(api_calls)} API calls)")

        # Save game-specific API calls
        game_api_calls = [call for call in api_calls if str(GAME_ID) in call["url"]]
        if game_api_calls:
            with open(output_dir / f"game_{GAME_ID}_api_calls.json", "w", encoding="utf-8") as f:
                json.dump(game_api_calls, f, indent=2, ensure_ascii=False)
            print(f"[SAVED] game_{GAME_ID}_api_calls.json ({len(game_api_calls)} calls)")

        # Save final HTML
        final_html = page.content()
        with open(output_dir / "final_page.html", "w", encoding="utf-8") as f:
            f.write(final_html)
        print(f"[SAVED] final_page.html ({len(final_html):,} bytes)")

        # Screenshot
        page.screenshot(path=str(output_dir / "final_screenshot.png"))
        print("[SAVED] final_screenshot.png")

    except Exception as e:
        print(f"[ERROR] Failed to load page: {e}")

    browser.close()

print()
print("=" * 80)
print("  MONITORING COMPLETE")
print("=" * 80)
print()

print(f"Results saved to: {output_dir}")
print()

print("Summary:")
print(f"  Total API calls: {len(api_calls)}")
print(f"  Game-specific calls: {len([c for c in api_calls if str(GAME_ID) in c['url']])}")
print()

print("Next steps:")
print("1. Review all_api_calls.json for API endpoints that returned data")
print("2. Check embedded_script_data.json for JavaScript variables")
print("3. Grep final_page.html for play-by-play and shot data")
print()

print("[COMPLETE] Network monitoring finished")
print()
