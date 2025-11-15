#!/usr/bin/env python3
"""Interactive script to capture play-by-play and shot data from real game center

This script:
1. Opens the game center (same UI you see in browser)
2. Monitors ALL network requests to api-prod.lnb.fr
3. Lets you manually click PLAY BY PLAY and POSITIONS TIRS tabs
4. Captures the JSON responses (getEventList, shot endpoints, etc.)
5. Saves them for parsing

Usage:
    uv run python tools/lnb/capture_real_game_center.py
"""

import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 80)
print("  INTERACTIVE LNB Game Center Network Capture")
print("  Capturing Play-by-Play and Shot Data")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "real_game_center_capture"
output_dir.mkdir(exist_ok=True)

# We'll try multiple possible game center URL patterns
GAME_ID = 28910  # Cholet vs Nanterre

possible_urls = [
    f"https://lnb.fr/fr/match/{GAME_ID}",
    f"https://lnb.fr/match/{GAME_ID}",
    f"https://lnb.fr/elite/game-center/{GAME_ID}",
    f"https://lnb.fr/game-center/{GAME_ID}",
    f"https://www.lnb.fr/game-center/{GAME_ID}",
    # Based on your screenshot, try to find the actual game center
    "https://lnb.fr/fr",  # Then navigate from home
]

# Storage for all API responses
api_responses = {}
response_count = 0


def save_response(url: str, data: any, response_type: str = "unknown"):
    """Save API response to file"""
    global response_count
    response_count += 1

    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{timestamp}_{response_type}_{response_count}.json"

    output = {"url": url, "type": response_type, "timestamp": timestamp, "data": data}

    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return filename


print("Starting Playwright browser (headless=False so you can interact)...")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    page = context.new_page()

    # =================================================================
    # NETWORK RESPONSE HANDLER
    # =================================================================
    def handle_response(response):
        """Capture all API responses from api-prod.lnb.fr"""
        url = response.url

        # Only capture LNB API calls
        if "api-prod.lnb.fr" not in url:
            return

        try:
            # Check if it's JSON
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return

            # Get the JSON data
            data = response.json()

            # Determine what type of response this is
            response_type = "unknown"
            should_print = False

            if "getEventList" in url or "event" in url.lower():
                response_type = "PLAY_BY_PLAY"
                should_print = True
                print(f"\n{'='*80}")
                print("🎯 FOUND PLAY-BY-PLAY DATA!")
                print(f"{'='*80}")

            elif "shot" in url.lower() or "tir" in url.lower():
                response_type = "SHOTS"
                should_print = True
                print(f"\n{'='*80}")
                print("🎯 FOUND SHOT DATA!")
                print(f"{'='*80}")

            elif "getCalenderByDivision" in url:
                response_type = "calendar"

            elif "getLiveMatch" in url:
                response_type = "live_match"

            elif "getStanding" in url:
                response_type = "standings"

            elif "getPerformance" in url:
                response_type = "performance"

            elif "getCompetition" in url:
                response_type = "competition"

            # Save the response
            filename = save_response(url, data, response_type)

            if should_print:
                print(f"URL: {url}")
                print(f"Status: {response.status}")
                print(f"Saved: {filename}")
                print(f"Data keys: {list(data.keys())[:10]}")

                # Print sample of the data
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        print(f"Number of items: {len(data['data'])}")
                        if data["data"]:
                            print(f"First item keys: {list(data['data'][0].keys())[:10]}")
                print()
            else:
                # Just log other API calls quietly
                print(f"[API] {response_type}: {url.split('/')[-1][:50]}")

        except Exception as e:
            print(f"[ERROR] Failed to process response from {url}: {e}")

    # Attach response handler
    page.on("response", handle_response)

    # =================================================================
    # TRY TO NAVIGATE TO GAME CENTER
    # =================================================================
    print("Attempting to find the game center page...")
    print("-" * 80)

    game_center_found = False

    for url in possible_urls:
        print(f"[TRY] {url}")

        try:
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            final_url = page.url
            page_title = page.title()

            print(f"  Status: {response.status}")
            print(f"  Final URL: {final_url}")
            print(f"  Page title: {page_title}")

            # Check if we're on a game page (not 404, not home)
            page_content = page.content().lower()

            if (
                "404" not in page_content
                and "page introuvable" not in page_content
                and ("cholet" in page_content or "nanterre" in page_content)
            ):
                print("  ✅ Potential game center found!")
                game_center_found = True

                # Take screenshot
                page.screenshot(path=str(output_dir / "game_center_initial.png"))
                print("  [SAVED] game_center_initial.png")

                break
            else:
                print("  ❌ Not the game center (404 or home page)")

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")

        print()

    if not game_center_found:
        print("⚠️  Could not automatically find game center.")
        print("    I'll keep the browser open - navigate manually to the game page.")
        print()

    # =================================================================
    # INTERACTIVE CAPTURE MODE
    # =================================================================
    print("=" * 80)
    print("  INTERACTIVE MODE")
    print("=" * 80)
    print()
    print("The browser is now open and monitoring network requests.")
    print()
    print("Please do the following:")
    print("  1. Navigate to the game center for Cholet vs Nanterre (if not already there)")
    print("  2. Click the 'PLAY BY PLAY' tab")
    print("  3. Click through Q1, Q2, Q3, Q4, TOUTE (all quarters)")
    print("  4. Click the 'POSITIONS TIRS' tab")
    print("  5. Click any filters (teams, players, etc.)")
    print()
    print("As you click, I'll capture the network requests and save them.")
    print()
    print("When you're done exploring, press ENTER here to stop capturing...")
    print()

    # Wait for user input
    input()

    # Take final screenshot
    page.screenshot(path=str(output_dir / "game_center_final.png"))
    print()
    print("[SAVED] game_center_final.png")

    # Save page HTML
    html = page.content()
    with open(output_dir / "game_center_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[SAVED] game_center_page.html")

    # Save final URL
    with open(output_dir / "game_center_url.txt", "w") as f:
        f.write(page.url)
    print(f"[SAVED] game_center_url.txt: {page.url}")

    browser.close()

print()
print("=" * 80)
print("  CAPTURE COMPLETE")
print("=" * 80)
print()

print(f"Captured {response_count} API responses")
print(f"Saved to: {output_dir}")
print()

# Analyze captured responses
print("Analyzing captured data...")
print("-" * 80)

pbp_files = list(output_dir.glob("*PLAY_BY_PLAY*.json"))
shot_files = list(output_dir.glob("*SHOTS*.json"))

if pbp_files:
    print(f"✅ Found {len(pbp_files)} play-by-play response(s):")
    for f in pbp_files:
        print(f"   - {f.name}")
else:
    print("❌ No play-by-play data captured")
    print("   Make sure you clicked the 'PLAY BY PLAY' tab!")

print()

if shot_files:
    print(f"✅ Found {len(shot_files)} shot data response(s):")
    for f in shot_files:
        print(f"   - {f.name}")
else:
    print("❌ No shot data captured")
    print("   Make sure you clicked the 'POSITIONS TIRS' tab!")

print()
print("Next steps:")
print("1. Review the captured JSON files in:", output_dir)
print("2. Look for 'PLAY_BY_PLAY' files to understand PBP structure")
print("3. Look for 'SHOTS' files to understand shot data structure")
print("4. Use those structures to build parsers")
print()
print("[COMPLETE] Interactive capture finished")
print()
