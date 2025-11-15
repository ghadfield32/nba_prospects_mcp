#!/usr/bin/env python3
"""Extract play-by-play structure from LNB game page

Navigates to a specific game and extracts the actual HTML structure
of the play-by-play elements to understand how to parse them.

Usage:
    uv run python tools/lnb/extract_pbp_structure.py
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
print("  Extracting Play-by-Play Structure from LNB Game Page")
print("  Game: 28910 (Cholet vs Nanterre)")
print("=" * 80)
print()

output_dir = Path(__file__).parent / "pbp_structure_analysis"
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

        # Wait for content to load
        import time

        time.sleep(5)

        # =================================================================
        # EXTRACT PLAY-BY-PLAY ELEMENTS
        # =================================================================
        print()
        print("[EXTRACT] Looking for play-by-play elements...")
        print("-" * 80)

        # Find elements with "events" class
        event_elements = page.query_selector_all('[class*="events"]')
        print(f"Found {len(event_elements)} elements with class*='events'")
        print()

        # Extract first few elements to understand structure
        pbp_samples = []
        for i, element in enumerate(event_elements[:10]):  # First 10 samples
            try:
                html = element.inner_html()
                text = element.inner_text()
                classes = element.get_attribute("class")

                pbp_samples.append(
                    {
                        "index": i,
                        "classes": classes,
                        "text": text[:200] if text else "",  # First 200 chars
                        "html_preview": html[:500] if html else "",  # First 500 chars
                    }
                )

                print(f"Element {i}:")
                print(f"  Classes: {classes}")
                print(f"  Text: {text[:100] if text else '(empty)'}...")
                print()
            except Exception as e:
                print(f"Element {i}: Error extracting - {e}")

        # Save samples
        with open(output_dir / "pbp_element_samples.json", "w", encoding="utf-8") as f:
            json.dump(pbp_samples, f, indent=2, ensure_ascii=False)
        print("[SAVED] pbp_element_samples.json")
        print()

        # =================================================================
        # LOOK FOR TABS/BUTTONS TO SWITCH TO PBP VIEW
        # =================================================================
        print("[SEARCH] Looking for tabs/buttons that might show play-by-play...")
        print("-" * 80)

        # Common tab/button patterns
        tab_selectors = [
            'button:has-text("Action")',
            'button:has-text("Événements")',
            'a:has-text("Action")',
            'a:has-text("Événements")',
            '[role="tab"]',
            'button[class*="tab"]',
            'a[class*="tab"]',
        ]

        found_tabs = []
        for selector in tab_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    for elem in elements:
                        text = elem.inner_text()
                        classes = elem.get_attribute("class")
                        found_tabs.append({"selector": selector, "text": text, "classes": classes})
                        print(f"  [FOUND] {selector}: '{text}' (classes: {classes})")
            except Exception:
                pass

        if found_tabs:
            with open(output_dir / "found_tabs.json", "w", encoding="utf-8") as f:
                json.dump(found_tabs, f, indent=2, ensure_ascii=False)
            print(f"[SAVED] found_tabs.json ({len(found_tabs)} tabs)")
        else:
            print("  [NOT FOUND] No tab elements detected")

        print()

        # =================================================================
        # EXTRACT SVG SHOT CHART STRUCTURE
        # =================================================================
        print("[EXTRACT] Analyzing SVG shot chart elements...")
        print("-" * 80)

        svg_elements = page.query_selector_all("svg")
        print(f"Found {len(svg_elements)} SVG elements")
        print()

        # Analyze SVG elements to find shot charts
        shot_chart_candidates = []
        for i, svg in enumerate(svg_elements[:20]):  # First 20 SVGs
            try:
                # Get SVG attributes
                width = svg.get_attribute("width")
                height = svg.get_attribute("height")
                viewbox = svg.get_attribute("viewBox")
                classes = svg.get_attribute("class")

                # Get inner content preview
                inner_html = svg.inner_html()

                # Check if it contains circles (common for shot charts)
                circles = svg.query_selector_all("circle")
                paths = svg.query_selector_all("path")

                info = {
                    "index": i,
                    "width": width,
                    "height": height,
                    "viewBox": viewbox,
                    "classes": classes,
                    "circle_count": len(circles),
                    "path_count": len(paths),
                    "html_preview": inner_html[:300] if inner_html else "",
                }

                # Shot charts typically have multiple circles (shot markers)
                if len(circles) > 5:
                    shot_chart_candidates.append(info)
                    print(f"SVG {i} - POTENTIAL SHOT CHART:")
                    print(f"  Size: {width}x{height}")
                    print(f"  Circles: {len(circles)} (shot markers?)")
                    print(f"  Paths: {len(paths)}")
                    print()
            except Exception as e:
                print(f"SVG {i}: Error - {e}")

        if shot_chart_candidates:
            with open(output_dir / "shot_chart_candidates.json", "w", encoding="utf-8") as f:
                json.dump(shot_chart_candidates, f, indent=2, ensure_ascii=False)
            print(f"[SAVED] shot_chart_candidates.json ({len(shot_chart_candidates)} candidates)")
        else:
            print("  [NOT FOUND] No shot chart SVGs detected (looking for SVGs with >5 circles)")

        print()

        # =================================================================
        # EXTRACT CIRCLE COORDINATES (SHOT LOCATIONS)
        # =================================================================
        if shot_chart_candidates:
            print("[EXTRACT] Extracting shot coordinates from best candidate...")
            print("-" * 80)

            # Use the SVG with most circles as our shot chart
            best_candidate = max(shot_chart_candidates, key=lambda x: x["circle_count"])
            best_svg_index = best_candidate["index"]

            print(
                f"Using SVG index {best_svg_index} (has {best_candidate['circle_count']} circles)"
            )
            print()

            # Re-select that specific SVG
            all_svgs = page.query_selector_all("svg")
            shot_chart_svg = all_svgs[best_svg_index]

            # Extract all circles
            circles = shot_chart_svg.query_selector_all("circle")
            shot_data = []

            for i, circle in enumerate(circles):
                cx = circle.get_attribute("cx")
                cy = circle.get_attribute("cy")
                r = circle.get_attribute("r")
                fill = circle.get_attribute("fill")
                stroke = circle.get_attribute("stroke")
                classes = circle.get_attribute("class")

                shot_data.append(
                    {
                        "index": i,
                        "cx": cx,
                        "cy": cy,
                        "r": r,
                        "fill": fill,
                        "stroke": stroke,
                        "classes": classes,
                    }
                )

                if i < 5:  # Print first 5
                    print(f"Shot {i}: cx={cx}, cy={cy}, r={r}, fill={fill}")

            with open(output_dir / "shot_coordinates.json", "w", encoding="utf-8") as f:
                json.dump(shot_data, f, indent=2, ensure_ascii=False)

            print()
            print(f"[SAVED] shot_coordinates.json ({len(shot_data)} shots)")

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
    print(f"  - {file.name}")

print()
print("[COMPLETE] Structure extraction finished")
print()
