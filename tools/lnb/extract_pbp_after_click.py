#!/usr/bin/env python3
"""Extract play-by-play data AFTER clicking the Événements button

This script:
1. Navigates to game page
2. Clicks "Événements" button to reveal play-by-play
3. Extracts the actual play-by-play event data
4. Also looks for shot chart tabs and data

Usage:
    uv run python tools/lnb/extract_pbp_after_click.py
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
print("  Extracting Play-by-Play Data After Clicking Événements Button")
print("  Game: 28910 (Cholet vs Nanterre)")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "pbp_after_click"
output_dir.mkdir(exist_ok=True)

GAME_ID = 28910
GAME_URL = f"https://www.lnb.fr/fr/match/{GAME_ID}"

print(f"Navigating to: {GAME_URL}")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    page = context.new_page()

    # Navigate to game page
    print("[LOAD] Loading game page...")
    response = page.goto(GAME_URL, wait_until="networkidle", timeout=60000)

    if response and response.status == 200:
        print(f"[SUCCESS] Page loaded (HTTP {response.status})")
        print()

        # Wait for initial content
        import time

        time.sleep(3)

        # =================================================================
        # CLICK ÉVÉNEMENTS BUTTON
        # =================================================================
        print("[ACTION] Looking for Événements button...")
        print("-" * 80)

        # Try to find and click the Événements button
        try:
            # Find the button
            evenements_button = page.query_selector('button:has-text("Événements")')

            if evenements_button:
                button_text = evenements_button.inner_text()
                print(f"[FOUND] Button: '{button_text}'")

                # Click the button
                print("[CLICK] Clicking Événements button...")
                evenements_button.click()

                # Wait for content to load after click
                time.sleep(3)
                print("[SUCCESS] Clicked button, waiting for content to load...")
                print()

                # =================================================================
                # EXTRACT PLAY-BY-PLAY DATA
                # =================================================================
                print("[EXTRACT] Looking for play-by-play content...")
                print("-" * 80)

                # Save full page HTML after click
                html_after_click = page.content()
                with open(output_dir / "page_after_click.html", "w", encoding="utf-8") as f:
                    f.write(html_after_click)
                print("[SAVED] page_after_click.html")

                # Look for common play-by-play patterns
                pbp_selectors = [
                    '[class*="timeline"]',
                    '[class*="event-list"]',
                    '[class*="play-list"]',
                    '[class*="action-list"]',
                    'table[class*="stats"]',
                    'div[class*="action"]',
                    'li[class*="event"]',
                    'div[class*="play"]',
                ]

                pbp_content = []
                for selector in pbp_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            print(f"[FOUND] {len(elements)} elements matching '{selector}'")

                            # Extract content from first few
                            for i, elem in enumerate(elements[:5]):
                                text = elem.inner_text()
                                html = elem.inner_html()
                                classes = elem.get_attribute("class")

                                pbp_content.append(
                                    {
                                        "selector": selector,
                                        "index": i,
                                        "classes": classes,
                                        "text": text[:300] if text else "",
                                        "html_preview": html[:500] if html else "",
                                    }
                                )

                                if i < 2:
                                    print(f"  Element {i}: {text[:100] if text else '(empty)'}...")
                    except Exception as e:
                        print(f"  Error with selector '{selector}': {e}")

                if pbp_content:
                    with open(output_dir / "pbp_content_samples.json", "w", encoding="utf-8") as f:
                        json.dump(pbp_content, f, indent=2, ensure_ascii=False)
                    print()
                    print(f"[SAVED] pbp_content_samples.json ({len(pbp_content)} samples)")
                else:
                    print("[NOT FOUND] No play-by-play content detected")

                print()

                # =================================================================
                # LOOK FOR QUARTER/PERIOD SELECTORS
                # =================================================================
                print("[SEARCH] Looking for quarter/period selectors...")
                print("-" * 80)

                quarter_selectors = [
                    'button:has-text("Q1")',
                    'button:has-text("Q2")',
                    'button:has-text("Q3")',
                    'button:has-text("Q4")',
                    'button:has-text("QT1")',
                    'button:has-text("QT2")',
                    'button:has-text("QT3")',
                    'button:has-text("QT4")',
                    'button:has-text("1er")',
                    'button:has-text("2ème")',
                    'button:has-text("3ème")',
                    'button:has-text("4ème")',
                ]

                quarters_found = []
                for selector in quarter_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            for elem in elements:
                                text = elem.inner_text()
                                quarters_found.append({"selector": selector, "text": text})
                                print(f"  [FOUND] {selector}: '{text}'")
                    except Exception:
                        pass

                if quarters_found:
                    with open(output_dir / "quarter_selectors.json", "w", encoding="utf-8") as f:
                        json.dump(quarters_found, f, indent=2, ensure_ascii=False)
                    print(f"[SAVED] quarter_selectors.json ({len(quarters_found)} quarters)")
                else:
                    print("  [NOT FOUND] No quarter selector buttons")

                print()

            else:
                print("[ERROR] Événements button not found")
                print("  Trying alternative selectors...")

                # Try alternative button selectors
                alt_selectors = [
                    'a:has-text("Événements")',
                    '[role="tab"]:has-text("Événements")',
                    'button:has-text("ÉVÉNEMENTS")',
                ]

                for selector in alt_selectors:
                    try:
                        elem = page.query_selector(selector)
                        if elem:
                            print(f"  [FOUND] Alternative: {selector}")
                            print("  [CLICK] Clicking...")
                            elem.click()
                            time.sleep(3)
                            print("  [SUCCESS] Clicked!")
                            break
                    except Exception as e:
                        print(f"  [FAILED] {selector}: {e}")

        except Exception as e:
            print(f"[ERROR] Failed to click button: {e}")

        print()

        # =================================================================
        # LOOK FOR SHOT CHART TABS
        # =================================================================
        print("[SEARCH] Looking for shot chart tabs/buttons...")
        print("-" * 80)

        shot_selectors = [
            'button:has-text("Tir")',
            'button:has-text("Tirs")',
            'button:has-text("Shot")',
            'button:has-text("Shots")',
            'button:has-text("Carte")',
            'a:has-text("Tir")',
            'a:has-text("Tirs")',
        ]

        shot_tabs = []
        for selector in shot_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    for elem in elements:
                        text = elem.inner_text()
                        shot_tabs.append({"selector": selector, "text": text})
                        print(f"  [FOUND] {selector}: '{text}'")

                        # Try clicking the first shot chart tab
                        if len(shot_tabs) == 1:
                            print("  [CLICK] Clicking shot chart tab...")
                            elem.click()
                            time.sleep(3)
                            print("  [SUCCESS] Clicked!")

                            # Extract shot chart after click
                            shot_html = page.content()
                            with open(
                                output_dir / "page_after_shot_click.html", "w", encoding="utf-8"
                            ) as f:
                                f.write(shot_html)
                            print("  [SAVED] page_after_shot_click.html")
            except Exception as e:
                print(f"  Error with selector '{selector}': {e}")

        if shot_tabs:
            with open(output_dir / "shot_tabs.json", "w", encoding="utf-8") as f:
                json.dump(shot_tabs, f, indent=2, ensure_ascii=False)
            print(f"[SAVED] shot_tabs.json ({len(shot_tabs)} tabs)")
        else:
            print("  [NOT FOUND] No shot chart tabs detected")

        print()

        # Take a screenshot for visual reference
        screenshot_path = output_dir / "screenshot_final.png"
        page.screenshot(path=str(screenshot_path))
        print("[SAVED] screenshot_final.png")

    else:
        print(
            f"[ERROR] Failed to load page (HTTP {response.status if response else 'No response'})"
        )

    browser.close()

print()
print("=" * 80)
print("  EXTRACTION COMPLETE")
print("=" * 80)
print()

print(f"Results saved to: {output_dir}")
print()

print("Files created:")
for file in sorted(output_dir.glob("*")):
    size = file.stat().st_size
    size_str = f"{size:,} bytes" if size < 1024 * 1024 else f"{size/(1024*1024):.1f} MB"
    print(f"  - {file.name} ({size_str})")

print()
print("[COMPLETE] Play-by-play extraction with button clicks finished")
print()
