#!/usr/bin/env python
"""Analyze OTE schedule HTML to debug scraper issues."""

import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

html_path = Path("data/_logs/html_snapshots/ote_schedule.html")
if not html_path.exists():
    print(f"ERROR: {html_path} not found")
    sys.exit(1)

html = html_path.read_text(encoding="utf-8")
print(f"HTML file size: {len(html)} bytes")

# Check for Next.js
print("\n--- Checking for __NEXT_DATA__ ---")
if "__NEXT_DATA__" in html:
    print("Found __NEXT_DATA__ - This is a Next.js site!")
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        json_str = match.group(1)
        print(f"JSON length: {len(json_str)} chars")
        try:
            data = json.loads(json_str)
            print("Successfully parsed JSON!")
            print(f"Top-level keys: {list(data.keys())}")
            if "props" in data:
                print(f"  props keys: {list(data['props'].keys())}")
                if "pageProps" in data["props"]:
                    print(f"  pageProps keys: {list(data['props']['pageProps'].keys())}")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
else:
    print("No __NEXT_DATA__ found")

# Check for team names
print("\n--- Team Names Found ---")
teams = [
    "City Reapers",
    "Blue Checks",
    "Cold Hearts",
    "Diamond Doves",
    "Fear of God",
    "Jelly Fam",
    "YNG Dreamerz",
    "RWE",
]
for team in teams:
    count = html.count(team)
    if count > 0:
        print(f"  {team}: {count} occurrences")

# Check for game links
print("\n--- Game Links Found ---")
game_links = re.findall(r"/games/([a-f0-9\-]+)", html)
unique_games = list(set(game_links))
print(f"Total game link matches: {len(game_links)}")
print(f"Unique game IDs: {len(unique_games)}")
if unique_games[:5]:
    print(f"Sample IDs: {unique_games[:5]}")

# Check for dates
print("\n--- Date Patterns Found ---")
# Common date patterns
date_patterns = [
    r"(\w{3},?\s+\w{3}\s+\d{1,2})",  # Mon, Jan 12
    r"(\d{4}-\d{2}-\d{2})",  # 2024-01-12
    r"(\d{1,2}/\d{1,2}/\d{4})",  # 1/12/2024
]
for pattern in date_patterns:
    matches = re.findall(pattern, html)
    unique_matches = list(set(matches))[:5]
    if unique_matches:
        print(f"  Pattern {pattern}: {len(matches)} matches")
        print(f"    Examples: {unique_matches}")

# Look for scores
print("\n--- Potential Score Patterns ---")
score_patterns = re.findall(r"(\d{2,3})\s*-\s*(\d{2,3})", html)
if score_patterns:
    unique_scores = list(set(score_patterns))[:10]
    print(f"Found {len(score_patterns)} score patterns (format: XX-XX)")
    print(f"Examples: {unique_scores}")
else:
    print("No XX-XX score patterns found")

print("\n--- Analysis Complete ---")
